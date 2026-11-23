"""DESIGN 7 v1.532 and v1.536 (row ESC2b): cascades, part 2, the candidates and the cost.

With `select(..., cascades=True)` each cascade of the task is one routing candidate after the
registry models, in task order: rules 1 to 5 run on its cheap model and then on its strong one,
`cascade_unknown_model` when the registry lacks either, then its own trials and Wilson bound at
the task's or slice's bar, and its cost is the cheap model's call plus its share of hand-ups,
`cheap.cost(in, out) + p * strong.cost(in + out, out)`. It enters the 5.3 lists as a model does
but never on a prior. Without the keyword every decision is v1.535's. The executor and records
are row ESC2c. The contract tests were written under strict xfail and the implementing commit
removed the marks; the unmarked guards pin what v1.536 keeps and passed before and after it.
"""

import dataclasses
import json
import tempfile
from pathlib import Path

import pytest

from decision_hash import PLATFORM_Z, FixedZ, decision_sha256
import model_routing
from model_routing import (
    DATA_DIR, Cascade, Completion, Executor, FakeProvider, Model, NoModelClearsBar, Priors,
    Registry, Router, Stats, Task, load_tasks, run_demo, wilson_lower_bound,
)


CHEAP, MID, BEST, TWIN, PEER = (
    "fiction/cheap", "fiction/mid", "fiction/best", "fiction/twin", "fiction/peer")
REGISTRY = Registry([
    Model(CHEAP, "fam-a", 1.0, 2.0, 10_000),
    Model(MID, "fam-b", 3.0, 6.0, 10_000),
    Model(BEST, "fam-c", 10.0, 30.0, 100_000),
    Model(TWIN, "fam-a", 2.0, 4.0, 100_000),
    Model(PEER, "fam-c", 5.0, 15.0, 100_000),
])
C = Cascade(CHEAP, BEST, "sig")
D = Cascade(MID, BEST, "other")
CID = "fiction/cheap>fiction/best@sig"

# the decisions on the demo's files (no generator, then the demo's generator) and on the
# example tasks (empty Stats, packaged priors), both flavors, computed in iter 382 at bfad91b
# before any v1.536 code; its router.py is v1.534's, and v1.535 kept every output v1.534's;
# hashed by tests/decision_hash.py (DESIGN 4.3 v1.593, row CI32), so each bound rounded to 12
# decimals, and recomputed so at bfad91b, the same under both platform values of `z` (the exact
# hashes were fed72621... and c48657f0...; the example tasks' hash holds no bound and is exact)
V1_535_DEMO_SELECT_SHA256 = "b3887f8d39abe681f8e317c28f0a8d30f564f71b86a6d5b94ea19d6d95755329"
V1_535_DEMO_GENERATOR_SELECT_SHA256 = (
    "0ecc62acc20a9d9aad7f588b41231cf6c7ef4cf313b5fbd9efe0b9c454cfebe1")
V1_535_EXAMPLE_SELECT_SHA256 = "2369381cc7a44f66de6512014c0ec9c5ca6df5a65074ca9239b14d114255d4da"
DEMO_GENERATOR = "demo/cedar-writer"


def sha(value) -> str:
    return decision_sha256(value)


def planted_stats(cascade=(95, 100, 20)):
    """cheap 60/100 measured at 1200 in and 300 out per call, best 98/100, the cascade's own."""
    stats = Stats()
    stats.add("t", CHEAP, 60, 100, input_tokens=120_000, output_tokens=30_000)
    stats.add("t", BEST, 98, 100)
    if cascade is not None:
        s, n, e = cascade
        stats.add("t", CID, s, n, escalated=e)
    return stats


def task(**fields):
    values = dict(bar=0.8, min_samples=10, cascades=(C,))
    values.update(fields)
    return Task("t", **values)


def router(t=None, stats=None, registry=REGISTRY, priors=None):
    t = task() if t is None else t
    return Router(registry, {t.name: t}, planted_stats() if stats is None else stats, priors)


def by_id(decision_or_candidates):
    candidates = getattr(decision_or_candidates, "candidates", decision_or_candidates)
    return {c.model_id: c for c in candidates}


def route(decision):
    return (decision.primary, *decision.fallbacks)


def candidates_of(r, *args, **kw):
    """The candidates of the decision, or of the NoModelClearsBar it raises."""
    try:
        return r.select(*args, **kw).candidates
    except NoModelClearsBar as exc:
        return exc.candidates


def with_cascades(tasks, registry):
    ids = [m.id for m in registry.models]
    return {name: dataclasses.replace(t, cascades=(Cascade(ids[0], ids[-1], "sig"),
                                                   Cascade(ids[1], ids[0], "other-1")))
            for name, t in tasks.items()}


def routes(registry, tasks, stats, priors, **kw):
    out = []
    for name in tasks:
        for flavor in ("cost_effective", "cost_blind"):
            try:
                out.append(Router(registry, tasks, stats, priors).select(name, flavor, **kw).to_dict())
            except NoModelClearsBar as exc:
                out.append(str(exc))
    return out


def demo_files():
    with tempfile.TemporaryDirectory() as tmp:
        out = Path(tmp) / "demo"
        run_demo(out)
        return (Registry.load(out / "models.json"), load_tasks(out / "tasks.json"),
                Stats.load(out / "stats.json"))


def example_files():
    return (Registry.load(DATA_DIR / "models.json"), load_tasks(DATA_DIR / "example_tasks.json"),
            Priors.load(DATA_DIR / "priors.json"))


# --- the reason code and the keyword ------------------------------------------------------

def test_the_reason_code_is_exported_after_passes():
    from model_routing import CASCADE_UNKNOWN_MODEL
    assert CASCADE_UNKNOWN_MODEL == "cascade_unknown_model"
    assert model_routing.router.CASCADE_UNKNOWN_MODEL == "cascade_unknown_model"
    names = model_routing.__all__
    assert names.index("CASCADE_UNKNOWN_MODEL") == names.index("PASSES") + 1


@pytest.mark.parametrize("value", [1, 0, None, "true", 1.0, (C,)])
def test_a_cascades_that_is_not_a_bool_is_a_value_error(value):
    with pytest.raises(ValueError, match="cascades"):
        router().select("t", cascades=value)


def test_the_cascades_check_comes_before_the_task_lookup():
    with pytest.raises(ValueError, match="cascades"):
        router().select("absent", cascades=1)


def test_a_registry_id_equal_to_a_cascade_id_is_a_value_error_with_cascades_only():
    registry = Registry([*REGISTRY.models, Model(CID, "fam-x", 1.0, 1.0, 100_000)])
    r = router(registry=registry)
    with pytest.raises(ValueError, match="cascade"):
        r.select("t", cascades=True)
    assert r.select("t", cascades=False).primary == r.select("t").primary
    with pytest.raises(KeyError):  # the task lookup comes first
        r.select("absent", cascades=True)


# --- the candidate: order, family, counts, cost -------------------------------------------

def test_one_candidate_per_cascade_after_the_registry_models_in_task_order():
    decision = router(task(cascades=(D, C))).select("t", cascades=True)
    ids = [c.model_id for c in decision.candidates]
    assert ids == [CHEAP, MID, BEST, TWIN, PEER, D.id, CID]
    assert by_id(decision)[D.id].family == "fam-c"  # the strong model's family
    assert by_id(decision)[CID].family == "fam-c"


def test_a_planted_cascade_by_hand_cost_effective():
    decision = router().select("t", cascades=True)
    c = by_id(decision)[CID]
    # cheap at its measured sizes: (1200 * 1.0 + 300 * 2.0) / 1e6 = 0.0018
    # the hand-up: best reads 1200 + 300 and writes 300: (1500 * 10 + 300 * 30) / 1e6 = 0.024
    # p = 20 / 100 = 0.2, so 0.0018 + 0.2 * 0.024 = 0.0066
    assert c.list_cost == pytest.approx(0.0066, rel=1e-12)
    assert c.list_cost == REGISTRY.get(CHEAP).cost(1200, 300) + 0.2 * REGISTRY.get(BEST).cost(1500, 300)
    assert c.routing_cost == c.list_cost
    assert (c.successes, c.trials) == (95, 100)
    assert c.quality_lb == wilson_lower_bound(95, 100, 0.95)
    assert c.quality_lb == pytest.approx(0.8882, abs=5e-4)
    assert (c.eligible, c.passes, c.reason) == (True, True, "passes")
    # best 98/100 passes at 0.016, the cheap model's 60/100 is below the bar: the cascade
    # is the cheapest passing candidate
    assert by_id(decision)[BEST].list_cost == pytest.approx(0.016, rel=1e-12)
    assert by_id(decision)[CHEAP].reason == "below_bar"
    assert route(decision) == (CID, BEST)
    assert (decision.below_bar, decision.basis, decision.below_bar_fallbacks) == (False, "measured", ())


def test_a_planted_cascade_by_hand_cost_blind():
    decision = router().select("t", "cost_blind", cascades=True)
    c = by_id(decision)[CID]
    assert c.routing_cost == 0.0
    assert c.list_cost == pytest.approx(0.0066, rel=1e-12)
    # best's bound (98/100, about 0.930) is above the cascade's (about 0.888)
    assert route(decision) == (BEST, CID)


def test_an_unmeasured_cascade_costs_what_its_cheap_model_does():
    c = by_id(candidates_of(router(stats=Stats()), "t", cascades=True))[CID]
    assert c.list_cost == REGISTRY.get(CHEAP).cost(1000, 200) == pytest.approx(0.0014, rel=1e-12)
    assert (c.successes, c.trials, c.quality_lb) == (0, 0, 0.0)
    assert (c.eligible, c.passes, c.reason) == (True, False, "insufficient_samples")


def test_a_cascade_that_never_escalated_costs_its_cheap_model_at_its_sizes():
    decision = router(stats=planted_stats(cascade=(95, 100, 0))).select("t", cascades=True)
    assert by_id(decision)[CID].list_cost == REGISTRY.get(CHEAP).cost(1200, 300)


def test_the_cascade_reads_its_slice_key_alone():
    t = task(on_no_model="best_available",
             slices={"deep": {"bar": 0.9, "expected_input_tokens": 4000}})
    stats = planted_stats()  # the pooled key: 95/100, 20 escalated
    stats.add("t@deep", CID, 95, 100, escalated=50)
    decision = router(t, stats).select("t", slice="deep", cascades=True)
    c = by_id(decision)[CID]
    # the slice's sizes 4000 and 200, p = 0.5:
    # (4000 * 1 + 200 * 2) / 1e6 + 0.5 * (4200 * 10 + 200 * 30) / 1e6 = 0.0044 + 0.024
    assert c.list_cost == pytest.approx(0.0284, rel=1e-12)
    assert c.reason == "below_bar"  # its bound, about 0.888, is under the slice's 0.9
    assert (decision.task, decision.slice, decision.primary) == ("t", "deep", CID)
    assert (decision.below_bar, decision.basis) == (True, "measured")


# --- rules 1 to 5 on both models, the cheap one first --------------------------------------

@pytest.mark.parametrize("kw, fields, cascade, reason", [
    ({"exclude_models": [CHEAP]}, {}, C, "excluded_model"),
    ({"exclude_models": [BEST]}, {}, C, "excluded_model"),
    ({"exclude_models": [CID]}, {}, C, "excluded_model"),
    # the cascade's own id comes before any rule on its models
    ({"exclude_models": [CID], "prompt_tokens": 20_000}, {}, C, "excluded_model"),
    ({}, {"exclude_families": ("fam-a",)}, C, "excluded_family"),
    ({}, {"exclude_families": ("fam-c",)}, C, "excluded_family"),
    ({"generator_model": CHEAP}, {}, C, "generator"),
    ({"generator_model": BEST}, {}, C, "generator"),
    ({"generator_model": TWIN}, {}, C, "generator_family"),
    ({"generator_model": PEER}, {}, C, "generator_family"),
    ({"prompt_tokens": 20_000}, {}, C, "context_too_small"),  # the cheap model's 10,000 window
    ({"prompt_tokens": 20_000}, {}, Cascade(TWIN, MID, "sig"),
     "context_too_small"),  # the strong model's 10,000 window
    # the cheap model's rule 5 comes before the strong model's rule 1
    ({"prompt_tokens": 20_000, "exclude_models": [BEST]}, {}, C, "context_too_small"),
    # the cheap model's rule 3 comes before the strong model's rule 2
    ({"generator_model": CHEAP}, {"exclude_families": ("fam-c",)}, C, "generator"),
])
def test_rules_1_to_5_run_on_the_cheap_model_then_the_strong_one(kw, fields, cascade, reason):
    r = router(task(cascades=(cascade,), on_no_model="best_available", **fields))
    c = by_id(candidates_of(r, "t", cascades=True, **kw))[cascade.id]
    assert (c.reason, c.eligible, c.passes) == (reason, False, False)


@pytest.mark.parametrize("cascade", [Cascade(CHEAP, "fiction/absent", "sig"),
                                     Cascade("fiction/absent", BEST, "sig")])
def test_a_cascade_with_a_model_the_registry_lacks(cascade):
    stats = planted_stats()
    stats.add("t", cascade.id, 95, 100, escalated=20)
    r = router(task(cascades=(cascade,)), stats)
    # before any other rule: the excluded cascade id and cheap model and the generator do
    # not name it (review iter-382 should-fix 1)
    c = by_id(candidates_of(r, "t", cascades=True, exclude_models=[cascade.id, CHEAP],
                            generator_model=BEST))[cascade.id]
    assert (c.reason, c.family, c.list_cost, c.routing_cost) == ("cascade_unknown_model", "", 0.0, 0.0)
    assert (c.eligible, c.passes, c.successes, c.trials) == (False, False, 95, 100)
    assert c.quality_lb == wilson_lower_bound(95, 100, 0.95)
    decision = r.select("t", cascades=True)
    assert by_id(decision)[cascade.id].reason == "cascade_unknown_model"
    assert route(decision) == (BEST,)


# --- rules 6 to 8 on its own trials, and 5.3 -------------------------------------------------

@pytest.mark.parametrize("counts, reason, eligible", [
    ((5, 5, 1), "insufficient_samples", True),
    ((70, 100, 10), "below_bar", True),
    ((95, 100, 20), "passes", True),
])
def test_its_own_trials_and_bound_decide_rules_6_to_8(counts, reason, eligible):
    decision = router(stats=planted_stats(cascade=counts)).select("t", cascades=True)
    c = by_id(decision)[CID]
    assert (c.reason, c.eligible, c.passes) == (reason, eligible, reason == "passes")


def test_a_cascade_enters_the_best_available_measured_list():
    t = task(bar=0.99, on_no_model="best_available")
    decision = router(t, planted_stats(cascade=(99, 100, 30))).select("t", cascades=True)
    # bounds: cascade 99/100 about 0.946, best 98/100 about 0.930, cheap 60/100 about 0.502
    assert route(decision) == (CID, BEST, CHEAP)
    assert (decision.below_bar, decision.basis) == (True, "measured")
    assert route(router(t, planted_stats(cascade=(99, 100, 30))).select("t")) == (BEST, CHEAP)


def test_a_cascade_is_a_below_bar_fallback_as_a_model_is():
    t = task(bar=0.9, fallback_below_bar=True)
    decision = router(t).select("t", cascades=True)
    # best passes (about 0.930); the cascade (about 0.888) and cheap (about 0.502) do not
    assert route(decision) == (BEST, CID, CHEAP)
    assert decision.below_bar_fallbacks == (CID, CHEAP)
    assert route(router(t).select("t")) == (BEST, CHEAP)


def test_priors_never_admit_a_cascade():
    priors = Priors({"cat": {"scores": {CHEAP: 0.5, BEST: 0.9, CID: 0.99}}})
    t = task(on_no_model="best_available", prior_category="cat")
    r = router(t, Stats(), priors=priors)
    decision = r.select("t", cascades=True)
    assert (decision.basis, decision.below_bar) == ("prior", True)
    assert route(decision) == (BEST, CHEAP)
    assert by_id(decision)[CID].reason == "insufficient_samples"
    assert route(decision) == route(r.select("t"))


def test_no_model_clears_bar_carries_the_cascade_candidates():
    with pytest.raises(NoModelClearsBar) as info:
        router(task(bar=0.99)).select("t", cascades=True)
    assert [c.model_id for c in info.value.candidates] == [CHEAP, MID, BEST, TWIN, PEER, CID]


def test_a_cascade_candidate_dict_has_the_ten_candidate_keys():
    data = router().select("t", cascades=True).to_dict()
    # v1.584 (row SELF1c): the eleventh field, pricing_basis, is None on a cascade, so no key,
    # and v1.588 (row CACHE1b) adds two more a cascade leaves at their defaults
    keys = [f.name for f in dataclasses.fields(model_routing.Candidate)]
    assert len(keys) == 13 and keys[10:] == ["pricing_basis", "cost_breakdown",
                                             "cache_price_unknown"]
    keys = keys[:10]
    assert list(data["candidates"][-1]) == keys
    assert data["candidates"][-1]["model_id"] == CID
    assert data["primary"] == CID
    json.dumps(data)


def test_with_cascades_true_a_task_without_cascades_routes_as_without_the_keyword():
    t = task(cascades=())
    for flavor in ("cost_effective", "cost_blind"):
        assert router(t).select("t", flavor, cascades=True) == router(t).select("t", flavor)


# --- without the keyword, or with False, every decision is v1.535's -----------------------

def test_cascades_false_routes_the_demo_and_example_tasks_as_v1_535():
    registry, tasks, stats = demo_files()
    planted = with_cascades(tasks, registry)
    assert sha(routes(registry, planted, stats, None, cascades=False)) == V1_535_DEMO_SELECT_SHA256
    assert sha(routes(registry, tasks, stats, None, cascades=True)) == V1_535_DEMO_SELECT_SHA256
    assert sha(routes(registry, planted, stats, None, cascades=False,
                      generator_model=DEMO_GENERATOR)) == V1_535_DEMO_GENERATOR_SELECT_SHA256
    registry, tasks, priors = example_files()
    planted = with_cascades(tasks, registry)
    assert sha(routes(registry, planted, Stats(), priors, cascades=False)) == V1_535_EXAMPLE_SELECT_SHA256
    assert sha(routes(registry, tasks, Stats(), priors, cascades=True)) == V1_535_EXAMPLE_SELECT_SHA256


def test_guard_without_the_keyword_the_demo_routes_as_v1_535_with_cascades_set():
    registry, tasks, stats = demo_files()
    assert sha(routes(registry, tasks, stats, None)) == V1_535_DEMO_SELECT_SHA256
    planted = with_cascades(tasks, registry)
    assert sha(routes(registry, planted, stats, None)) == V1_535_DEMO_SELECT_SHA256
    assert sha(routes(registry, planted, stats, None,
                      generator_model=DEMO_GENERATOR)) == V1_535_DEMO_GENERATOR_SELECT_SHA256


def test_the_v1_535_demo_hashes_are_the_same_under_either_platforms_z(monkeypatch):
    import model_routing.stats as stats_module
    live = set()
    for z in PLATFORM_Z:  # DESIGN 4.3 v1.593, row CI32
        monkeypatch.setattr(stats_module, "NormalDist", FixedZ(z))
        registry, tasks, stats = demo_files()
        assert sha(routes(registry, tasks, stats, None)) == V1_535_DEMO_SELECT_SHA256
        assert sha(routes(registry, tasks, stats, None, generator_model=DEMO_GENERATOR)) == (
            V1_535_DEMO_GENERATOR_SELECT_SHA256)
        live.add(wilson_lower_bound(37, 40))
    assert len(live) == 2  # the patch reached the bound (review iter-441 nit 1)


def test_guard_without_the_keyword_the_example_tasks_route_as_v1_535_with_cascades_set():
    registry, tasks, priors = example_files()
    assert sha(routes(registry, with_cascades(tasks, registry), Stats(), priors)) == (
        V1_535_EXAMPLE_SELECT_SHA256)


def test_guard_without_the_keyword_a_planted_cascade_is_no_candidate():
    decision = router().select("t")
    assert [c.model_id for c in decision.candidates] == [CHEAP, MID, BEST, TWIN, PEER]
    assert decision == router(task(cascades=())).select("t")
    assert route(decision) == (BEST,)


def test_decide_delegation_passes_no_cascades_and_keeps_a_cascade_key():
    # the stats hold token counts on the task and a cascade key, and the brief is not empty,
    # so decide_delegation briefs a copy of them (13.3); v1.535 dropped the escalation count
    # from that copy and raised ValueError (review iter-382 nit 2)
    kw = dict(context_tokens=1000, brief_tokens=100, result_tokens=50)
    decision = router().decide_delegation("t", BEST, **kw)
    plain = router(task(cascades=()), planted_stats(cascade=None)).decide_delegation("t", BEST, **kw)
    assert decision == plain
    assert decision.route is not None
    assert [c.model_id for c in decision.route.candidates] == [CHEAP, MID, BEST, TWIN, PEER]


def test_guard_the_executor_without_signals_passes_no_cascades():
    script = {m.id: (lambda messages: Completion("done", 10, 5)) for m in REGISTRY.models}
    executor = Executor(router(), FakeProvider(script), now=lambda: "2026-11-20T00:00:00Z",
                        id_factory=lambda: "call-1")
    result = executor.call("t", [{"role": "user", "content": "hi"}])
    assert result.model == BEST
    assert [c.model_id for c in result.decision.candidates] == [CHEAP, MID, BEST, TWIN, PEER]
