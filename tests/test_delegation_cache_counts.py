"""DESIGN 13.2, 13.6 and 13.8 v1.706 (row CACHE4a): the parent's measured cache counts in the inline cost.

On a parent without ``price_tiers`` whose own key on the task holds measured cache counts, each
inline work call holds the parent's rounded-down mean cached reads and writes (5.2 v1.588) inside
its input, so the inline work term is ``P.cost(X, K * S_out, cached_input_tokens=K * M_r,
cache_write_tokens=K * M_w)``, X the v1.41 first argument, while rho still prices the context C
alone, and ``DelegationDecision.inline_cache_counts`` states the counts used. With no count on the
parent's own key, or a tiered parent, every cost is v1.705's; the 960 decisions on the shipped data
that tests/test_policy_delegation.py pins keep their digest, since no shipped stats file holds a
cache count. Committed ahead of the code (v1.706 red commit): the tests of the new costs and field
fail on v1.705, and the guards of what stays pass before and after it.
"""

import dataclasses

import pytest

from model_routing import DelegationDecision, Model, PriceTier, Registry, Router, Stats, Task
from model_routing.delegation import DELEGATE_CHEAPER, INLINE_CHEAPER

PARENT, DELEG, TIERED = "fiction/parent", "fiction/deleg", "fiction/tiered"
# the 4.1 v1.587 worked prices on the parent: 3.0 in, 0.3 cached, 3.75 written, 15.0 out
REGISTRY = Registry([
    Model(PARENT, "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3, price_cache_write=3.75),
    Model(DELEG, "fam-b", 15.0, 75.0, 200_000),
    Model(TIERED, "fam-c", 3.0, 15.0, 400_000, price_tiers=(PriceTier(100_000, 6.0, 22.5),)),
])
TASK = Task("t", bar=0.7, min_samples=10, independent_of_generator=False,
            expected_input_tokens=10_000, expected_output_tokens=500)
OTHER = Task("u", bar=0.7, min_samples=10, independent_of_generator=False,
             expected_input_tokens=10_000, expected_output_tokens=500)
C, B, R = 50_000, 400, 60
N = 20  # trials per key


def _stats(parent_cache=None, deleg_cache=None, other_cache=None, parent=PARENT):
    stats = Stats()
    stats.add("t", parent, N, N, input_tokens=10_000 * N, output_tokens=500 * N,
              **(parent_cache or {}))
    stats.add("t", DELEG, N, N, input_tokens=10_000 * N, output_tokens=500 * N,
              **(deleg_cache or {}))
    if other_cache is not None:
        stats.add("u", parent, N, N, input_tokens=10_000 * N, output_tokens=500 * N, **other_cache)
    return stats


READS_90 = {"cached_input_tokens": 9_000 * N, "cached_trials": N}
WRITES_90 = {"cache_write_tokens": 9_000 * N, "cache_write_trials": N}


def _decide(stats, parent=PARENT, **kw):
    router = Router(REGISTRY, {"t": TASK, "u": OTHER}, stats)
    kw.setdefault("exclude_models", (parent,))  # the delegate is DELEG, never the parent's own model
    return router.decide_delegation("t", parent, context_tokens=C, brief_tokens=B, result_tokens=R, **kw)


def _cost(inp, out, cached=0.0, write=0.0):
    """A call on the parent at its 4.1 v1.587 prices."""
    return ((inp - cached - write) * 3.0 + cached * 0.3 + write * 3.75 + out * 15.0) / 1_000_000


# --- the new costs (fail on v1.705) ----------------------------------------------------------

def test_reads_90_percent_cached_make_inline_cheaper_than_at_rho_1_by_hand():
    plain, cached = _decide(_stats()), _decide(_stats(READS_90))
    rereads = _cost(10_000 + 500, 0)  # (1 + T) * P.cost(K * (S_in + S_out), 0), list price
    assert plain.inline_cost_usd == pytest.approx(_cost(C + 10_000, 500) + rereads, rel=1e-12)
    assert cached.inline_cost_usd == pytest.approx(_cost(C + 10_000, 500, cached=9_000) + rereads,
                                                   rel=1e-12)
    assert cached.inline_cost_usd < plain.inline_cost_usd
    assert plain.inline_cost_usd - cached.inline_cost_usd == pytest.approx(9_000 * 2.7 / 1e6, rel=1e-9)


def test_the_cheaper_inline_path_turns_delegate_cheaper_into_inline_cheaper():
    plain, cached = _decide(_stats()), _decide(_stats(READS_90))
    assert plain.delegate_cost_usd == cached.delegate_cost_usd  # the delegate path keeps v1.705's prices
    assert (plain.mode, plain.reason) == ("delegate", DELEGATE_CHEAPER)
    assert (cached.mode, cached.reason) == ("inline", INLINE_CHEAPER)
    assert cached.inline_cost_usd < cached.delegate_cost_usd < plain.inline_cost_usd


@pytest.mark.parametrize("separate", [True, False])
def test_k_3_holds_the_counts_in_each_of_the_three_work_calls(separate):
    d = _decide(_stats(READS_90), work_calls=3, inline_separate_call=separate)
    w_in, w_out = 6, 3
    base = (3 if separate else 2) * C
    work = _cost(base + w_in * 10_000 + w_out * 500, 3 * 500, cached=3 * 9_000)
    rereads = (1 if separate else 0) * _cost(3 * (10_000 + 500), 0)
    assert d.inline_cost_usd == pytest.approx(work + rereads, rel=1e-12)
    assert d.inline_cache_counts == (9_000, 0)


def test_folded_one_call_holds_the_counts_in_the_next_call():
    d = _decide(_stats(READS_90), inline_separate_call=False)
    assert d.inline_cost_usd == pytest.approx(_cost(10_000, 500, cached=9_000), rel=1e-12)


def test_a_write_premium_raises_the_inline_cost():
    plain, written = _decide(_stats()), _decide(_stats(WRITES_90))
    rereads = _cost(10_500, 0)
    assert written.inline_cost_usd == pytest.approx(_cost(C + 10_000, 500, write=9_000) + rereads, rel=1e-12)
    assert written.inline_cost_usd > plain.inline_cost_usd
    assert written.inline_cache_counts == (0, 9_000)


def test_rho_and_the_counts_each_move_only_their_own_tokens():
    saving = {}
    for rho in (1.0, 0.1, 0.0):
        plain = _decide(_stats(), cached_read_ratio=rho)
        cached = _decide(_stats(READS_90), cached_read_ratio=rho)
        assert cached.inline_cost_usd == pytest.approx(
            _cost(C * rho + 10_000, 500, cached=9_000) + _cost(10_500, 0), rel=1e-12)
        assert cached.inline_cache_counts == (9_000, 0)
        saving[rho] = plain.inline_cost_usd - cached.inline_cost_usd
    # the counts' saving is the same at every rho, and rho's is the same with and without counts
    assert saving[0.1] == pytest.approx(saving[1.0], rel=1e-9)
    assert saving[0.0] == pytest.approx(saving[1.0], rel=1e-9)


def test_the_counts_are_fitted_inside_the_mean_input_the_write_first():
    over = {"cached_input_tokens": 8_000 * N, "cached_trials": N,
            "cache_write_tokens": 4_000 * N, "cache_write_trials": N}
    d = _decide(_stats(over))
    assert d.inline_cache_counts == (6_000, 4_000)
    assert d.inline_cost_usd == pytest.approx(
        _cost(C + 10_000, 500, cached=6_000, write=4_000) + _cost(10_500, 0), rel=1e-12)


def test_measured_zero_counts_are_stated_and_cost_what_no_count_costs():
    zero = {"cached_input_tokens": 0, "cached_trials": N}
    plain, d = _decide(_stats()), _decide(_stats(zero))
    assert d.inline_cache_counts == (0, 0)
    assert d.inline_cost_usd == plain.inline_cost_usd


def test_the_field_is_last_defaults_to_none_and_its_key_is_last_only_when_set():
    last = dataclasses.fields(DelegationDecision)[-1]
    assert (last.name, last.default) == ("inline_cache_counts", None)
    d = _decide(_stats(READS_90), depth=1)
    data = d.to_dict()
    assert list(data)[-2:] == ["depth", "inline_cache_counts"]
    assert data["inline_cache_counts"] == [9_000, 0]
    assert d.inline_cache_counts == (9_000, 0)


# --- what stays (pass before and after v1.706) -----------------------------------------------

def _same(a, b):
    assert a.to_dict() == b.to_dict()
    assert getattr(a, "inline_cache_counts", None) is None and getattr(b, "inline_cache_counts", None) is None


def test_no_count_keeps_the_decision_and_adds_no_key():
    d = _decide(_stats())
    assert "inline_cache_counts" not in d.to_dict()
    assert getattr(d, "inline_cache_counts", None) is None


@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_a_count_on_another_task_never_leaks(flavor):
    _same(_decide(_stats(), flavor=flavor), _decide(_stats(other_cache=READS_90), flavor=flavor))


def test_a_count_on_another_models_key_moves_no_inline_cost():
    plain, other = _decide(_stats()), _decide(_stats(deleg_cache=READS_90))
    assert other.inline_cost_usd == plain.inline_cost_usd
    assert getattr(other, "inline_cache_counts", None) is None


def test_a_tiered_parent_reads_no_count():
    plain = _decide(_stats(parent=TIERED), parent=TIERED)
    counted = _decide(_stats(READS_90, parent=TIERED), parent=TIERED)
    _same(plain, counted)


def test_the_router_stats_are_left_as_they_were():
    stats = _stats(READS_90)
    before = (stats.tokens("t", PARENT), stats.cache_tokens("t", PARENT), stats.get("t", PARENT))
    _decide(stats, work_calls=2)
    assert (stats.tokens("t", PARENT), stats.cache_tokens("t", PARENT), stats.get("t", PARENT)) == before
