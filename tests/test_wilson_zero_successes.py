"""DESIGN 4.3 v1.568 (row CI29): the Wilson lower bound is exactly 0.0 at 0 successes.

Computed in floating point the formula's two terms can leave a residue near 1e-17 at 0
successes, and its size depends on the last bits of `z`, so it differs by platform: on the CI
runners `(0, 10)` at 0.95 left about 2.0e-17, so a `retry_same` route passing on 0 of 10 got a
finite per-success estimate (DESIGN 5.3 v1.567) where tests/test_cost_per_success.py expects
`None`. Bounds at 1 or more successes keep their bits.
"""

import json
from datetime import date
from math import sqrt
from statistics import NormalDist, StatisticsError

import pytest

from model_routing import Model, Registry, Router, Stats, Task, wilson_lower_bound
from model_routing.cli import main

A, B = "fiction/a", "fiction/b"
CONFIDENCES = (0.5, 0.8, 0.9, 0.95, 0.99)


def _formula(successes, trials, confidence):
    """DESIGN 4.3's formula as written, clamped to >= 0.0, with no exact-zero rule."""
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    n = trials
    p = successes / n
    lb = (p + z * z / (2 * n) - z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    return max(0.0, lb)


def test_the_bound_at_0_successes_is_exactly_0_for_every_count_and_confidence():
    residues = [(n, c, wilson_lower_bound(0, n, c))
                for c in CONFIDENCES for n in range(1, 201)
                if wilson_lower_bound(0, n, c) != 0.0]
    assert residues == []


def test_the_bound_at_0_successes_is_a_float_zero():
    value = wilson_lower_bound(0, 15)
    assert type(value) is float and value == 0.0
    assert wilson_lower_bound(0, 0) == 0.0


def test_bounds_at_1_or_more_successes_keep_their_bits():
    for c in CONFIDENCES:
        for n in (1, 2, 7, 10, 15, 30, 100, 200):
            for k in range(1, n + 1):
                assert wilson_lower_bound(k, n, c) == _formula(k, n, c), (k, n, c)


def test_the_reference_values_hold():
    expected = {(27, 30): 0.743789, (45, 50): 0.786398, (90, 100): 0.825634,
                (170, 200): 0.793944, (10, 10): 0.722467, (0, 10): 0.0}
    for (k, n), value in expected.items():
        assert round(wilson_lower_bound(k, n), 6) == value


@pytest.mark.parametrize("successes,trials", [(-1, 10), (0, -1), (11, 10)])
def test_bad_counts_still_raise(successes, trials):
    with pytest.raises(ValueError):
        wilson_lower_bound(successes, trials)


@pytest.mark.parametrize("confidence", [1.0, 1.5, -1.0])
def test_a_bad_confidence_raises_at_0_successes_as_before(confidence):
    # z is computed before the exact-zero return, so a confidence inv_cdf rejects still raises
    with pytest.raises(StatisticsError):
        wilson_lower_bound(0, 10, confidence)


def _registry():
    return Registry([
        Model(id=A, family="small", price_in=0.6, price_out=1.2, context_window=8000),
        Model(id=B, family="large", price_in=1.0, price_out=2.0, context_window=8000),
    ])


def _stats():
    stats = Stats()
    stats.add("t", A, 0, 15)
    stats.add("t", B, 99, 100)
    return stats


def test_a_route_passing_on_0_of_15_has_no_per_success_estimate():
    # 0 of 15 at 0.95 is a count whose formula leaves a residue here (2.2e-17)
    assert _formula(0, 15, 0.95) > 0.0
    task = Task(name="t", bar=0.0, min_samples=10, failure_policy="retry_same")
    router = Router(_registry(), {"t": task}, _stats())
    decision = router.select("t", exclude_models=(B,))
    assert decision.primary == A
    assert decision.expected_cost_per_success_usd is None
    assert decision.to_dict()["expected_cost_per_success_usd"] is None
    both = router.select("t")
    assert (both.primary, both.fallbacks, both.pick_reason) == (B, (A,), "cheaper_per_success")


def test_select_prints_n_a_at_0_of_15(tmp_path, capsys):
    models = [{"id": m.id, "family": m.family, "price_in": m.price_in, "price_out": m.price_out,
               "context_window": m.context_window, "source": "https://example.org/prices"}
              for m in _registry().models]
    (tmp_path / "models.json").write_text(json.dumps(
        {"version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models}))
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [
        {"name": "t", "bar": 0.0, "min_samples": 10, "failure_policy": "retry_same"}]}))
    _stats().save(tmp_path / "stats.json")
    files = ["--registry", str(tmp_path / "models.json"), "--tasks", str(tmp_path / "tasks.json"),
             "--stats", str(tmp_path / "stats.json"), "--priors", str(tmp_path / "none.json")]
    assert main(["select", "t", "--exclude", B, *files], today=date(2026, 1, 2)) == 0
    lines = capsys.readouterr().out.splitlines()
    at = lines.index("below_bar: false")
    assert lines[at + 1] == ("policy:    retry_same, expected cost per success n/a "
                             "(an estimate assuming independent retries)")
