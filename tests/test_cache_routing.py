"""DESIGN 4.3, 5.1 and 5.2 v1.588 (row CACHE1b): measured cache counts in a route's price.

`Stats` holds, per `(task, model_id)`, the cached reads and the cache writes measured on the
trials that reported them, each with its own trial count, and `.select` prices a registry model's
candidate at their rounded-down means through `Model.cost`, so a model that is cheaper per token
but never hits the cache can lose to a pricier one whose reads are 90% cached, and a write at a
premium can make the caching route the dearer one on a prompt read once. A candidate with
measured counts carries a four-part `cost_breakdown` and names any cache price that was unknown
and so read as the call's input price. A cascade's legs, a procedure's model, the delegation
costs and the attempt records pass no count yet, so every decision from a stats file without the
new keys keeps its bytes. The contract tests were written under strict xfail and the implementing
commit removed the marks; the unmarked guards pin what v1.588 keeps and passed before and after it.
"""

import json
import math

import pytest

from model_routing import (
    Cascade, Model, Registry, Router, Stats, Task, Variant, calibrate_from_results,
)

RED = pytest.mark.xfail(strict=True, reason="v1.588 (row CACHE1b) is not implemented yet")

PRICEY, CHEAP = "fiction/pricey", "fiction/cheap"
# the 4.1 v1.587 worked example: 3.0 in, 0.3 cached, 3.75 written, 15.0 out, against 2.0 in
REGISTRY = Registry([
    Model(PRICEY, "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3, price_cache_write=3.75),
    Model(CHEAP, "fam-b", 2.0, 15.0, 200_000),
])
TASK = Task("t", bar=0.7, min_samples=10, independent_of_generator=False,
            expected_input_tokens=10_000, expected_output_tokens=500)


def _router(stats, registry=REGISTRY, task=TASK):
    return Router(registry, {task.name: task}, stats)


def _stats(**per_model):
    """One key per model: ``model_id=(input, output, trials, cache kwargs)``."""
    stats = Stats()
    for model_id, (tin, tout, trials, cache) in per_model.items():
        stats.add("t", model_id.replace("_", "/"), trials, trials,
                  input_tokens=tin * trials, output_tokens=tout * trials, **cache)
    return stats


def _by_id(decision):
    return {c.model_id: c for c in decision.candidates}


def _dicts(decision):
    return {c["model_id"]: c for c in decision.to_dict()["candidates"]}


# --- 4.3: the totals, their trials and their means ------------------------------------------

@RED
def test_nothing_is_recorded_until_a_count_is_given():
    stats = Stats()
    stats.add("t", PRICEY, 1, 1, input_tokens=100, output_tokens=10)
    assert stats.cache_tokens("t", PRICEY) == (0, 0, 0, 0)
    assert stats.mean_cache_tokens("t", PRICEY) == (None, None)
    assert stats.cache_tokens("t", "fiction/absent") == (0, 0, 0, 0)


@RED
def test_the_totals_accumulate_with_their_own_trial_counts():
    stats = Stats()
    stats.add("t", PRICEY, 2, 2, input_tokens=200, output_tokens=20,
              cached_input_tokens=120, cache_write_tokens=20)
    stats.add("t", PRICEY, 1, 1, input_tokens=100, output_tokens=10, cached_input_tokens=30)
    assert stats.cache_tokens("t", PRICEY) == (150, 3, 20, 2)
    assert stats.mean_cache_tokens("t", PRICEY) == (50, 10)


@RED
def test_a_mean_is_rounded_down_and_a_count_no_trial_reported_is_unknown():
    stats = Stats()
    stats.add("t", PRICEY, 2, 2, input_tokens=2001, output_tokens=200,
              cached_input_tokens=2001)
    assert stats.mean_tokens("t", PRICEY) == (1001, 100)  # rounded up, as v1.33
    assert stats.mean_cache_tokens("t", PRICEY) == (1000, None)  # rounded down, write unknown


@RED
def test_a_count_covers_the_trials_it_is_given_not_every_token_trial():
    stats = Stats()
    stats.add("t", PRICEY, 4, 4, input_tokens=400, output_tokens=40,
              cached_input_tokens=60, cached_trials=2)
    assert stats.cache_tokens("t", PRICEY) == (60, 2, 0, 0)
    assert stats.mean_cache_tokens("t", PRICEY) == (30, None)


@RED
@pytest.mark.parametrize("kwargs, named", [
    ({"cached_input_tokens": 1.0}, "cached_input_tokens"),
    ({"cached_input_tokens": True}, "cached_input_tokens"),
    ({"cached_input_tokens": -1}, "cached_input_tokens"),
    ({"cache_write_tokens": "10"}, "cache_write_tokens"),
    ({"cached_trials": 1}, "cached_trials"),
    ({"cache_write_trials": 2}, "cache_write_trials"),
    ({"cached_input_tokens": 10, "cached_trials": 0}, "cached_trials"),
    ({"cached_input_tokens": 10, "cached_trials": 3}, "cached_trials"),
    ({"cache_write_tokens": 10, "cache_write_trials": True}, "cache_write_trials"),
])
def test_a_bad_count_or_trial_raises_and_adds_nothing(kwargs, named):
    stats = Stats()
    with pytest.raises(ValueError) as exc:
        stats.add("t", PRICEY, 2, 2, input_tokens=200, output_tokens=20, **kwargs)
    assert named in str(exc.value)
    assert stats.get("t", PRICEY) == (0, 0)
    assert stats.cache_tokens("t", PRICEY) == (0, 0, 0, 0)


@RED
def test_a_cache_count_needs_the_token_totals():
    stats = Stats()
    with pytest.raises(ValueError) as exc:
        stats.add("t", PRICEY, 1, 1, cached_input_tokens=10)
    assert "input_tokens" in str(exc.value)
    assert stats.cache_tokens("t", PRICEY) == (0, 0, 0, 0)


@RED
def test_the_counts_given_fit_inside_the_input_tokens():
    stats = Stats()
    with pytest.raises(ValueError) as exc:
        stats.add("t", PRICEY, 1, 1, input_tokens=100, output_tokens=10,
                  cached_input_tokens=60, cache_write_tokens=41)
    assert "input_tokens" in str(exc.value)
    stats.add("t", PRICEY, 1, 1, input_tokens=100, output_tokens=10,
              cached_input_tokens=60, cache_write_tokens=40)
    assert stats.cache_tokens("t", PRICEY) == (60, 1, 40, 1)


@RED
@pytest.mark.parametrize("model_id", ["fiction/cheap>fiction/pricey@sig", "proc:p@1"])
def test_a_cascade_or_procedure_key_takes_no_cache_count(model_id):
    stats = Stats()
    extra = {"cost_usd": 0.5} if model_id.startswith("proc:") else {"escalated": 1}
    with pytest.raises(ValueError):
        stats.add("t", model_id, 1, 1, input_tokens=100, output_tokens=10,
                  cached_input_tokens=10, **extra)
    assert stats.cache_tokens("t", model_id) == (0, 0, 0, 0)


@RED
def test_save_and_load_round_trip_the_four_values(tmp_path):
    stats = Stats()
    stats.add("t", PRICEY, 4, 4, input_tokens=400, output_tokens=40,
              cached_input_tokens=60, cached_trials=2, cache_write_tokens=8)
    stats.add("t", CHEAP, 1, 1, input_tokens=100, output_tokens=10)
    path = tmp_path / "stats.json"
    stats.save(path)
    rows = {row["model"]: row for row in json.loads(path.read_text(encoding="utf-8"))["stats"]}
    assert list(rows[PRICEY])[-4:] == ["cached_input_tokens", "cached_trials",
                                       "cache_write_tokens", "cache_write_trials"]
    assert rows[PRICEY]["cached_input_tokens"] == 60 and rows[PRICEY]["cached_trials"] == 2
    assert rows[PRICEY]["cache_write_tokens"] == 8 and rows[PRICEY]["cache_write_trials"] == 4
    assert not any(key.startswith("cach") for key in rows[CHEAP])
    back = Stats.load(path)
    assert back.cache_tokens("t", PRICEY) == (60, 2, 8, 4)
    assert back.cache_tokens("t", CHEAP) == (0, 0, 0, 0)
    assert back.items() == stats.items()


@RED
@pytest.mark.parametrize("row", [
    {"cached_input_tokens": 10},
    {"cached_trials": 1},
    {"cache_write_tokens": 10},
    {"cache_write_trials": 1},
    {"cached_input_tokens": True, "cached_trials": 1},
    {"cached_input_tokens": 10, "cached_trials": 9},
])
def test_load_refuses_a_half_pair_a_bad_value_or_no_token_keys(tmp_path, row):
    full = {"task": "t", "model": PRICEY, "successes": 2, "trials": 2}
    if "cached_trials" in row or "cache_write_trials" in row or len(row) > 1:
        full.update(input_tokens=200, output_tokens=20, token_trials=2)
    path = tmp_path / "stats.json"
    path.write_text(json.dumps({"stats": [dict(full, **row)]}), encoding="utf-8")
    with pytest.raises(ValueError) as exc:
        Stats.load(path)
    assert "stats.json" in str(exc.value)


@RED
def test_merge_sums_the_cache_totals():
    a = Stats()
    a.add("t", PRICEY, 1, 1, input_tokens=100, output_tokens=10, cached_input_tokens=40)
    b = Stats()
    b.add("t", PRICEY, 1, 1, input_tokens=100, output_tokens=10, cached_input_tokens=60,
          cache_write_tokens=20)
    merged = a.merge(b)
    assert merged.cache_tokens("t", PRICEY) == (100, 2, 20, 1)
    assert merged.mean_cache_tokens("t", PRICEY) == (50, 20)
    assert a.cache_tokens("t", PRICEY) == (40, 1, 0, 0)


@RED
def test_calibrate_from_results_reads_a_rows_own_counts():
    stats = calibrate_from_results([
        {"task": "t", "model": PRICEY, "correct": True, "input_tokens": 100,
         "output_tokens": 10, "cached_input_tokens": 90},
        {"task": "t", "model": PRICEY, "correct": False, "input_tokens": 100,
         "output_tokens": 10, "cached_input_tokens": 70, "cache_write_tokens": 10},
        {"task": "t", "model": CHEAP, "correct": True, "input_tokens": 100, "output_tokens": 10},
    ])
    assert stats.cache_tokens("t", PRICEY) == (160, 2, 10, 1)
    assert stats.cache_tokens("t", CHEAP) == (0, 0, 0, 0)
    with pytest.raises(ValueError):
        calibrate_from_results([{"task": "t", "model": PRICEY, "correct": True,
                                 "cached_input_tokens": 10}])


# --- 5.2: the price of a route, and 5.1: the record ------------------------------------------

@RED
def test_a_pricier_model_at_90_percent_reads_beats_a_cheaper_one_that_misses():
    stats = _stats(fiction_pricey=(10_000, 500, 100, {"cached_input_tokens": 900_000}),
                   fiction_cheap=(10_000, 500, 100, {"cached_input_tokens": 0}))
    decision = _router(stats).select("t")
    assert decision.primary == PRICEY
    priced = _by_id(decision)
    assert priced[PRICEY].list_cost == pytest.approx(0.0132, abs=1e-12)
    assert priced[CHEAP].list_cost == pytest.approx(0.0275, abs=1e-12)
    assert priced[CHEAP].cost_breakdown is not None  # a measured 0 is a 0% hit rate, not unknown


@RED
def test_a_write_premium_makes_caching_lose_on_a_one_shot_task():
    stats = _stats(fiction_pricey=(10_000, 500, 100, {"cache_write_tokens": 900_000}),
                   fiction_cheap=(10_000, 500, 100, {}))
    decision = _router(stats).select("t")
    assert decision.primary == CHEAP
    priced = _by_id(decision)
    assert priced[PRICEY].list_cost == pytest.approx(0.04425, abs=1e-12)
    assert priced[CHEAP].list_cost == pytest.approx(0.0275, abs=1e-12)
    assert priced[CHEAP].cost_breakdown is None  # no count on either side: v1.587's price


@RED
def test_the_route_is_priced_at_the_rounded_down_means_inside_the_rounded_up_input():
    stats = Stats()
    stats.add("t", PRICEY, 2, 2, input_tokens=2004, output_tokens=1000,
              cached_input_tokens=2001, cache_write_tokens=3)
    candidate = _by_id(_router(stats).select("t"))[PRICEY]
    # mean input 1002 (up), cached 1000 and written 1 (down), so 1 token at the input price
    assert candidate.cost_breakdown == pytest.approx(
        (1 * 3.0 / 1e6, 1000 * 0.3 / 1e6, 1 * 3.75 / 1e6, 500 * 15.0 / 1e6))
    assert candidate.list_cost == pytest.approx(
        (1 * 3.0 + 1000 * 0.3 + 1 * 3.75 + 500 * 15.0) / 1e6, abs=1e-15)


@RED
def test_the_write_is_fitted_first_when_the_means_do_not_fit():
    stats = Stats()
    stats.add("t", PRICEY, 2, 2, input_tokens=24, output_tokens=2,
              cached_input_tokens=8, cached_trials=1, cache_write_tokens=10,
              cache_write_trials=1)
    candidate = _by_id(_router(stats).select("t"))[PRICEY]
    # mean input 12, means cached 8 and written 10: the write whole, the read cut to 2
    assert candidate.cost_breakdown == pytest.approx(
        (0.0, 2 * 0.3 / 1e6, 10 * 3.75 / 1e6, 1 * 15.0 / 1e6))


@RED
def test_the_candidate_dict_holds_the_four_parts_after_its_reason():
    stats = _stats(fiction_pricey=(10_000, 500, 100, {"cached_input_tokens": 900_000}),
                   fiction_cheap=(10_000, 500, 100, {}))
    decision = _router(stats).select("t")
    data = _dicts(decision)[PRICEY]
    keys = list(data)
    assert keys[keys.index("reason") + 1] == "cost_breakdown"
    assert list(data["cost_breakdown"]) == ["uncached_input_usd", "cached_read_usd",
                                            "cache_write_usd", "output_usd"]
    assert data["cost_breakdown"] == pytest.approx(
        {"uncached_input_usd": 1000 * 3.0 / 1e6, "cached_read_usd": 9000 * 0.3 / 1e6,
         "cache_write_usd": 0.0, "output_usd": 500 * 15.0 / 1e6})
    assert math.isclose(math.fsum(data["cost_breakdown"].values()), data["list_cost"],
                        rel_tol=1e-12)
    assert "cache_price_unknown" not in data
    assert "cost_breakdown" not in _dicts(decision)[CHEAP]


@RED
def test_an_unknown_cache_price_is_named_and_read_at_the_input_price():
    registry = Registry([Model(PRICEY, "fam-a", 3.0, 15.0, 200_000, price_cache_write=3.75),
                         Model(CHEAP, "fam-b", 2.0, 15.0, 200_000)])
    stats = _stats(fiction_pricey=(10_000, 500, 100,
                                   {"cached_input_tokens": 900_000, "cache_write_tokens": 50_000}))
    decision = _router(stats, registry=registry).select("t")
    candidate = _by_id(decision)[PRICEY]
    assert candidate.cache_price_unknown == ("price_cached_in",)
    assert candidate.list_cost == pytest.approx(
        (500 * 3.0 + 9000 * 3.0 + 500 * 3.75 + 500 * 15.0) / 1e6, abs=1e-15)
    assert _dicts(decision)[PRICEY]["cache_price_unknown"] == ["price_cached_in"]


@RED
def test_cost_blind_keeps_the_routing_cost_zero_and_the_breakdown():
    stats = _stats(fiction_pricey=(10_000, 500, 100, {"cached_input_tokens": 900_000}),
                   fiction_cheap=(10_000, 500, 100, {}))
    candidate = _by_id(_router(stats).select("t", flavor="cost_blind"))[PRICEY]
    assert candidate.routing_cost == 0.0
    assert candidate.list_cost == pytest.approx(0.0132, abs=1e-12)
    assert candidate.cost_breakdown is not None


@RED
def test_a_variants_breakdown_is_per_item():
    route = f"{PRICEY}@batch"
    registry = Registry([Model(route, "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3,
                               price_cache_write=3.75,
                               variant=Variant("batch", items_per_call=4))])
    stats = Stats()
    stats.add("t", route, 100, 100, input_tokens=1_000_000, output_tokens=50_000,
              cached_input_tokens=900_000)
    candidate = _by_id(_router(stats, registry=registry).select("t"))[route]
    assert candidate.list_cost == pytest.approx(0.0132 / 4, abs=1e-12)
    assert candidate.cost_breakdown == pytest.approx(
        (1000 * 3.0 / 4e6, 9000 * 0.3 / 4e6, 0.0, 500 * 15.0 / 4e6))


@RED
def test_a_cascades_legs_are_not_priced_at_their_cache_counts():
    cascade = Cascade(CHEAP, PRICEY, "sig")
    task = Task("t", bar=0.7, min_samples=10, independent_of_generator=False,
                expected_input_tokens=10_000, expected_output_tokens=500,
                cascades=(cascade,))
    stats = Stats()
    for model_id in (CHEAP, PRICEY):
        stats.add("t", model_id, 100, 100, input_tokens=1_000_000, output_tokens=50_000,
                  cached_input_tokens=900_000)
    stats.add("t", cascade.id, 90, 100, escalated=20)
    decision = _router(stats, task=task).select("t", cascades=True)
    candidate = _by_id(decision)[cascade.id]
    cheap, pricey = REGISTRY.get(CHEAP), REGISTRY.get(PRICEY)
    assert candidate.list_cost == pytest.approx(
        cheap.cost(10_000, 500) + 0.2 * pricey.cost(10_500, 500), abs=1e-15)
    assert candidate.cost_breakdown is None and candidate.cache_price_unknown == ()
    assert "cost_breakdown" not in _dicts(decision)[cascade.id]


def test_without_a_cache_count_every_candidate_keeps_its_keys():
    stats = _stats(fiction_pricey=(10_000, 500, 100, {}), fiction_cheap=(10_000, 500, 100, {}))
    decision = _router(stats).select("t")
    data = decision.to_dict()
    assert "cache" not in json.dumps(data)
    assert _by_id(decision)[PRICEY].list_cost == pytest.approx(
        (10_000 * 3.0 + 500 * 15.0) / 1e6, abs=1e-15)
    for candidate in data["candidates"]:
        assert list(candidate) == ["model_id", "family", "successes", "trials", "quality_lb",
                                   "routing_cost", "list_cost", "eligible", "passes", "reason"]
