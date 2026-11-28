"""DESIGN 5.1, 5.2 and 7 v1.591 (row CACHE1e): a cascade's legs and a procedure's model at their
measured cache counts.

A cascade prices its cheap leg at the cheap model's measured cache counts on the call's key and
its hand-up read, the input plus the cheap model's output, at the strong model's own counts,
fitted inside that read with the write first, never at the cheap model's cached share. A
procedure without a mean cost prices its model's one call at the task's expected sizes at that
model's counts, undivided. Either carries the four-part `cost_breakdown` and the unknown cache
prices of 5.1 v1.588 when a leg or its model has counts. Without a cache count every decision is
v1.590's. The contract tests were written under strict xfail and the implementing commit removed
the marks; the unmarked guards pin what v1.591 keeps and passed before and after it.
"""

import hashlib
import json
import math
from pathlib import Path

import pytest

from decision_hash import PLATFORM_Z, FixedZ, decision_sha256
from model_routing import (Cascade, Model, Procedure, ProcedureResult, Registry, Router, Stats,
                           Task, Variant)

ROOT = Path(__file__).resolve().parents[1]
CHEAP, STRONG = "fiction/cheap", "fiction/strong"
# the 5.2 v1.591 example: the cheap model at 1.0 in, 0.1 cached, 1.25 written and 4.0 out, the
# strong one at 3.0 in, 0.3 cached, 3.75 written and 15.0 out
REGISTRY = Registry([
    Model(CHEAP, "fam-b", 1.0, 4.0, 200_000, price_cached_in=0.1, price_cache_write=1.25),
    Model(STRONG, "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3, price_cache_write=3.75),
])
CASCADE = Cascade(CHEAP, STRONG, "sig")
CID = CASCADE.id


def _noop(value, call):
    return ProcedureResult("done", tool_calls=1)


def _one_call(value, call):
    return ProcedureResult(call([{"role": "user", "content": str(value)}]))


ON_CHEAP = Procedure("poll", "v1", _one_call, max_model_calls=1, max_tool_calls=5, model=CHEAP)
MEASURED = Procedure("poll", "v2", _one_call, max_model_calls=1, max_tool_calls=5, model=CHEAP)
BARE = Procedure("tool", "v1", _noop, max_model_calls=0, max_tool_calls=5)


def _task(**fields):
    values = dict(bar=0.7, min_samples=10, independent_of_generator=False,
                  expected_input_tokens=10_000, expected_output_tokens=500, cascades=(CASCADE,))
    values.update(fields)
    return Task("t", **values)


def _stats(key="t", cheap=None, strong=None, sizes=(10_000, 500), strong_sizes=None,
           escalated=20):
    """Both models at 100 trials with token totals, each with the cache kwargs given, the cascade
    at 90 of 100 with ``escalated`` hand-ups, all under ``key``."""
    stats = Stats()
    for model_id, cache, (tin, tout) in ((CHEAP, cheap, sizes),
                                          (STRONG, strong, strong_sizes or sizes)):
        stats.add(key, model_id, 95, 100, input_tokens=tin * 100, output_tokens=tout * 100,
                  **(cache or {}))
    stats.add(key, CID, 90, 100, escalated=escalated)
    return stats


def _select(stats, task=None, registry=REGISTRY, **kw):
    task = _task() if task is None else task
    kw.setdefault("cascades", True)
    return Router(registry, {task.name: task}, stats).select(task.name, **kw)


def _by_id(decision):
    return {c.model_id: c for c in decision.candidates}


def _dicts(decision):
    return {c["model_id"]: c for c in decision.to_dict()["candidates"]}


def _cost(model_id, size_in, size_out, cached=0, write=0, registry=REGISTRY):
    return registry.get(model_id).cost(size_in, size_out, cached_input_tokens=cached,
                                       cache_write_tokens=write)


# --- 5.2 v1.591: a cascade's legs ----------------------------------------------------------

def test_a_cascade_whose_cheap_leg_is_90_percent_cached_costs_less_than_unmeasured():
    plain = _by_id(_select(_stats()))[CID]
    cached = _by_id(_select(_stats(cheap={"cached_input_tokens": 900_000})))[CID]
    assert plain.list_cost == pytest.approx(0.0198, abs=1e-12)  # 0.012 + 0.2 * 0.039
    assert cached.list_cost == pytest.approx(0.0117, abs=1e-12)  # 0.0039 + 0.2 * 0.039
    assert cached.list_cost == pytest.approx(
        _cost(CHEAP, 10_000, 500, cached=9_000) + 0.2 * _cost(STRONG, 10_500, 500), abs=1e-15)
    assert cached.routing_cost == cached.list_cost < plain.list_cost


def test_the_hand_up_read_is_never_priced_at_the_cheap_models_cached_share():
    candidate = _by_id(_select(_stats(cheap={"cached_input_tokens": 900_000})))[CID]
    # the strong leg's parts are its uncached read of 10,500 and its 500 out, times p
    assert candidate.cost_breakdown == pytest.approx(
        (1_000 * 1.0 / 1e6 + 0.2 * 10_500 * 3.0 / 1e6, 9_000 * 0.1 / 1e6, 0.0,
         500 * 4.0 / 1e6 + 0.2 * 500 * 15.0 / 1e6))


def test_the_strong_leg_is_priced_at_its_own_counts():
    candidate = _by_id(_select(_stats(strong={"cached_input_tokens": 900_000})))[CID]
    # 0.012 + 0.2 * (1,500 * 3.0 + 9,000 * 0.3 + 500 * 15.0) / 1e6
    assert candidate.list_cost == pytest.approx(0.01494, abs=1e-12)
    assert candidate.cost_breakdown == pytest.approx(
        (10_000 * 1.0 / 1e6 + 0.2 * 1_500 * 3.0 / 1e6, 0.2 * 9_000 * 0.3 / 1e6, 0.0,
         500 * 4.0 / 1e6 + 0.2 * 500 * 15.0 / 1e6))


@pytest.mark.parametrize("strong, strong_sizes, cached, write", [
    # the strong model reads 20,000 a call, 18,000 of them cached: the hand-up reads 10,500, all cached
    ({"cached_input_tokens": 1_800_000}, (20_000, 500), 10_500, 0),
    # 9,000 cached and 2,000 written do not fit in 10,500: the write whole, the read cut to 8,500
    ({"cached_input_tokens": 900_000, "cache_write_tokens": 200_000}, (12_000, 500), 8_500, 2_000),
])
def test_the_strong_legs_counts_are_fitted_inside_the_hand_up_read(strong, strong_sizes, cached,
                                                                   write):
    candidate = _by_id(_select(_stats(strong=strong, strong_sizes=strong_sizes)))[CID]
    assert candidate.list_cost == pytest.approx(
        _cost(CHEAP, 10_000, 500) + 0.2 * _cost(STRONG, 10_500, 500, cached, write), abs=1e-15)
    parts = candidate.cost_breakdown
    assert parts[1] == pytest.approx(0.2 * cached * 0.3 / 1e6)
    assert parts[2] == pytest.approx(0.2 * write * 3.75 / 1e6)


def test_the_strong_legs_counts_are_first_fitted_inside_its_own_mean():
    # review iter-439 nit 2: means of 8 cached and 10 written over one reporting call each, inside
    # a mean input of 12 over two calls, fit as 2 and 10 before the hand-up read of 10,500
    stats = Stats()
    stats.add("t", CHEAP, 95, 100, input_tokens=1_000_000, output_tokens=50_000)
    stats.add("t", STRONG, 95, 100, input_tokens=24, output_tokens=2, token_trials=2,
              cached_input_tokens=8, cached_trials=1, cache_write_tokens=10,
              cache_write_trials=1)
    stats.add("t", CID, 90, 100, escalated=20)
    candidate = _by_id(_select(stats))[CID]
    assert candidate.list_cost == pytest.approx(
        _cost(CHEAP, 10_000, 500) + 0.2 * _cost(STRONG, 10_500, 500, cached=2, write=10),
        abs=1e-15)
    assert candidate.cost_breakdown[1] == pytest.approx(0.2 * 2 * 0.3 / 1e6)
    assert candidate.cost_breakdown[2] == pytest.approx(0.2 * 10 * 3.75 / 1e6)


def test_a_cascades_breakdown_sums_to_its_cost_and_follows_its_reason():
    decision = _select(_stats(cheap={"cached_input_tokens": 900_000},
                              strong={"cached_input_tokens": 600_000,
                                      "cache_write_tokens": 100_000}))
    data = _dicts(decision)[CID]
    keys = list(data)
    assert keys[keys.index("reason") + 1:] == ["cost_breakdown"]
    assert list(data["cost_breakdown"]) == ["uncached_input_usd", "cached_read_usd",
                                            "cache_write_usd", "output_usd"]
    assert math.isclose(math.fsum(data["cost_breakdown"].values()), data["list_cost"],
                        rel_tol=1e-12)
    assert data["list_cost"] == pytest.approx(
        _cost(CHEAP, 10_000, 500, cached=9_000)
        + 0.2 * _cost(STRONG, 10_500, 500, cached=6_000, write=1_000), abs=1e-15)
    json.dumps(decision.to_dict())


def test_a_cascade_names_each_cache_price_either_leg_needs_whatever_p_is():
    registry = Registry([Model(CHEAP, "fam-b", 1.0, 4.0, 200_000, price_cached_in=0.1),
                         Model(STRONG, "fam-a", 3.0, 15.0, 200_000, price_cache_write=3.75)])
    stats = _stats(cheap={"cache_write_tokens": 100_000}, strong={"cached_input_tokens": 500_000},
                   escalated=0)
    decision = _select(stats, registry=registry)
    candidate = _by_id(decision)[CID]
    assert candidate.cache_price_unknown == ("price_cached_in", "price_cache_write")
    # p is 0, so the cost is the cheap leg's, its 1,000 written read at its input price
    assert candidate.list_cost == pytest.approx(_cost(CHEAP, 10_000, 500, write=1_000,
                                                      registry=registry), abs=1e-15)
    assert _dicts(decision)[CID]["cache_price_unknown"] == ["price_cached_in", "price_cache_write"]
    # the legs' own candidates name each model's
    assert _by_id(decision)[CHEAP].cache_price_unknown == ("price_cache_write",)
    assert _by_id(decision)[STRONG].cache_price_unknown == ("price_cached_in",)


def test_cost_blind_keeps_a_cascades_breakdown_and_a_zero_routing_cost():
    candidate = _by_id(_select(_stats(cheap={"cached_input_tokens": 900_000}),
                               flavor="cost_blind"))[CID]
    assert candidate.routing_cost == 0.0
    assert candidate.list_cost == pytest.approx(0.0117, abs=1e-12)
    assert candidate.cost_breakdown is not None


def test_a_sliced_call_reads_the_legs_counts_on_its_slice_key():
    stats = _stats(key="t@deep", cheap={"cached_input_tokens": 900_000})
    stats.add("t", CHEAP, 95, 100, input_tokens=1_000_000, output_tokens=50_000)
    stats.add("t", STRONG, 95, 100, input_tokens=1_000_000, output_tokens=50_000)
    stats.add("t", CID, 90, 100, escalated=20)
    assert _by_id(_select(stats, slice="deep"))[CID].list_cost == pytest.approx(0.0117, abs=1e-12)
    unsliced = _by_id(_select(stats))[CID]
    assert unsliced.cost_breakdown is None
    assert unsliced.list_cost == pytest.approx(0.0198, abs=1e-12)


# --- 5.2 v1.591: a procedure's model -------------------------------------------------------

def test_an_unmeasured_procedure_prices_its_models_call_at_its_counts():
    decision = _select(_stats(cheap={"cached_input_tokens": 900_000}), procedures=[ON_CHEAP])
    candidate = _by_id(decision)[ON_CHEAP.id]
    assert candidate.trials == 0
    assert candidate.list_cost == pytest.approx(0.0039, abs=1e-12)
    assert candidate.cost_breakdown == pytest.approx((1_000 * 1.0 / 1e6, 9_000 * 0.1 / 1e6, 0.0,
                                                      500 * 4.0 / 1e6))
    assert list(_dicts(decision)[ON_CHEAP.id])[-1] == "cost_breakdown"


def test_a_procedures_counts_are_fitted_inside_the_tasks_expected_input():
    task = _task(expected_input_tokens=4_000)
    candidate = _by_id(_select(_stats(cheap={"cached_input_tokens": 900_000,
                                             "cache_write_tokens": 50_000}),
                               task=task, procedures=[ON_CHEAP]))[ON_CHEAP.id]
    # the mean write 500 first, then the mean read 9,000 cut to the 3,500 left
    assert candidate.list_cost == pytest.approx(_cost(CHEAP, 4_000, 500, cached=3_500, write=500),
                                                abs=1e-15)
    assert candidate.cost_breakdown == pytest.approx((0.0, 3_500 * 0.1 / 1e6, 500 * 1.25 / 1e6,
                                                      500 * 4.0 / 1e6))


def test_a_procedure_on_a_batch_variant_prices_its_call_undivided():
    route = f"{CHEAP}@batch"
    registry = Registry([Model(route, "fam-b", 1.0, 4.0, 200_000, price_cached_in=0.1,
                               price_cache_write=1.25, variant=Variant("batch", items_per_call=4))])
    proc = Procedure("poll", "v1", _one_call, max_model_calls=1, max_tool_calls=5, model=route)
    stats = Stats()
    stats.add("t", route, 95, 100, input_tokens=1_000_000, output_tokens=50_000,
              cached_input_tokens=900_000)
    decision = _select(stats, task=_task(cascades=()), registry=registry, cascades=False,
                       procedures=[proc])
    candidate = _by_id(decision)[proc.id]
    assert candidate.list_cost == pytest.approx(0.0039, abs=1e-12)  # one call, not over 4
    assert candidate.cost_breakdown == pytest.approx((0.001, 0.0009, 0.0, 0.002))
    assert _by_id(decision)[route].list_cost == pytest.approx(0.0039 / 4, abs=1e-12)


# --- unchanged ------------------------------------------------------------------------------

def test_a_measured_procedure_keeps_its_mean_cost_and_no_breakdown():
    stats = _stats(cheap={"cached_input_tokens": 900_000})
    stats.add("t", MEASURED.id, 95, 100, cost_usd=0.5)
    candidate = _by_id(_select(stats, procedures=[MEASURED, BARE]))[MEASURED.id]
    assert candidate.list_cost == 0.005
    assert candidate.cost_breakdown is None and candidate.cache_price_unknown == ()
    bare = _by_id(_select(stats, procedures=[MEASURED, BARE]))[BARE.id]
    assert bare.list_cost == 0.0 and bare.cost_breakdown is None


def test_an_unknown_leg_or_model_keeps_both_defaults():
    stats = _stats(cheap={"cached_input_tokens": 900_000})
    lone = Registry([REGISTRY.get(CHEAP)])
    decision = _select(stats, registry=lone, procedures=[Procedure(
        "poll", "v1", _one_call, max_model_calls=1, max_tool_calls=5, model=STRONG)])
    for candidate in decision.candidates[1:]:
        assert candidate.reason in ("cascade_unknown_model", "procedure_unknown_model")
        assert candidate.list_cost == 0.0
        assert candidate.cost_breakdown is None and candidate.cache_price_unknown == ()


def _guard_decisions(stats):
    out = []
    for slice_name in (None, "deep"):
        for flavor in ("cost_effective", "cost_blind"):
            decision = _select(stats, flavor=flavor, slice=slice_name,
                               procedures=[ON_CHEAP, MEASURED, BARE])
            out.append(decision.to_dict())
    return out


def _guard_stats(tokens):
    stats = Stats()
    for key in ("t", "t@deep"):
        for model_id, (tin, tout) in ((CHEAP, (10_000, 500)), (STRONG, (12_000, 700))):
            sizes = dict(input_tokens=tin * 40, output_tokens=tout * 40) if tokens else {}
            stats.add(key, model_id, 37, 40, **sizes)
        stats.add(key, CID, 36, 40, escalated=9)
        stats.add(key, MEASURED.id, 35, 40, cost_usd=0.12)
    return stats


# the guard decisions (two flavors, unsliced and on the slice `deep`, each with the cascade and
# the three procedures), with and without token totals, computed at 3ef5af9 before any v1.591 code,
# each `quality_lb` rounded to 12 decimals by tests/decision_hash.py (DESIGN 4.3 v1.592 and v1.593,
# rows CI31 and CI32: `z`'s last bit differs by platform, so the exact v1.590 hashes were
# 7122ae1a... and e1535a82... on the machine that wrote them and 27deaa3e... and 7d528bac... on the
# CI runners); the same under both values of `z`
V1_590_TOKENS_SHA256 = "315b61635d00ab990e40cc6acbdb160e4f5df3ac4f70119dd139d8fab309a674"
V1_590_NO_TOKENS_SHA256 = "1f57f2e0f57193a1461101ee68c1a15120e7da4f0e437c8aadabae3e1c982041"


def _sha(value):
    return decision_sha256(value)


@pytest.mark.parametrize("tokens, expected", [(True, V1_590_TOKENS_SHA256),
                                              (False, V1_590_NO_TOKENS_SHA256)])
def test_guard_without_a_cache_count_every_decision_keeps_v1_590s_bytes(tokens, expected):
    decisions = _guard_decisions(_guard_stats(tokens))
    assert _sha(decisions) == expected
    assert "cache" not in json.dumps(decisions)


@pytest.mark.parametrize("tokens, expected", [(True, V1_590_TOKENS_SHA256),
                                              (False, V1_590_NO_TOKENS_SHA256)])
def test_the_guard_hash_is_the_same_under_either_platforms_z(monkeypatch, tokens, expected):
    import model_routing.stats as stats_module
    exact, bounds = set(), set()
    for z in PLATFORM_Z:
        monkeypatch.setattr(stats_module, "NormalDist", FixedZ(z))
        decisions = _guard_decisions(_guard_stats(tokens))
        assert _sha(decisions) == expected
        exact.add(hashlib.sha256(json.dumps(decisions, sort_keys=True).encode()).hexdigest())
        bounds.add(decisions[0]["candidates"][0]["quality_lb"])
    assert len(exact) == 2 and len(bounds) == 2  # the exact bytes, and a bound, do differ


# --- the spec and the note ------------------------------------------------------------------

def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    five = design[design.index("### 5.2 "):design.index("### 5.3 ")]
    assert five.count("- v1.591 cache counts in a cascade's legs and a procedure's model "
                      "(row CACHE1e): ") == 1
    assert "and the cascade's legs and the procedure's model row CACHE1e (done in v1.591, 5.2 and 7)" in five
    seven = design[design.index("## 7. "):design.index("## 8. ")]
    assert seven.count("  - v1.591 the legs at their cache counts (row CACHE1e): ") == 1
    one = design[design.index("### 5.1 "):design.index("### 5.2 ")]
    assert "A cascade's and a procedure's candidate keep both defaults (until v1.591, 5.2)." in one
    # review iter-439 must-fix 1: the divisor of a cascade's and a procedure's parts is stated
    assert ("Each part of a registry model's candidate is `count * price / (1_000_000 * "
            "items_per_call)` as Python divides, and from v1.591 each part of a cascade's or a "
            "procedure's is `count * price / 1_000_000`, undivided") in one
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.591 (")]
    assert len(mine) == 1 and "(5.1, 5.2, 7, row CACHE1e)" in mine[0]


def test_the_production_note_says_a_cascade_and_a_procedure_pass_their_counts():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    for gone in ("A cascade's legs, a procedure's model and the delegation decision pass none",
                 "a cascade's legs, a procedure's model and the delegation decision pass no count"):
        assert gone not in note, gone
    for kept in ("A cascade is priced at each leg's own measured counts, the strong model's "
                 "re-read never at the cheap model's cached share, and a procedure not yet "
                 "measured at its model's; the delegation decision prices the parent's inline "
                 "work at the parent's own measured counts on the task, and the delegate's work and "
                 "model choice at each delegate's own",  # v1.706 and v1.707 (rows CACHE4a and CACHE4b)
                 "and a cascade's legs and a procedure's model at their own models' means, as the "
                 "Uber lesson on cache writes asks, while the delegation decision passes the parent's "
                 "counts to its inline work and each delegate's to its own work and model choice, beside "
                 "its cached-read ratio"):
        assert note.count(kept) == 1, kept
