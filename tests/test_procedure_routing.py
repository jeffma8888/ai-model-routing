"""DESIGN 4.3, 5.1 and 5.2 v1.577 (row PROC1b): a procedure route as a routing candidate.

With `select(..., procedures=[...])` each `Procedure` is one candidate after the registry models
and any cascades, in the order given: `procedure_unknown_model` when the registry lacks its named
model, else rule 1 on its own ID and rules 1 to 5 on that model, then rules 6 to 8 on its own
counts under its `proc:` ID, priced at its measured mean cost per trial, which `Stats` keeps as
`cost_usd`. It never enters on a prior. Without the keyword every decision is v1.576's. The
contract tests were written under strict xfail and the implementing commit removed the marks;
the unmarked guards pin what v1.577 keeps and passed before and after it.
"""

import json
import math
import tempfile
from pathlib import Path

import pytest

from decision_hash import PLATFORM_Z, FixedZ, decision_sha256
import model_routing
from model_routing import (
    DATA_DIR, Cascade, Model, NoModelClearsBar, Priors, Procedure, ProcedureResult, Registry,
    Router, Stats, Task, Variant, calibrate_from_results, load_tasks, run_demo,
    wilson_lower_bound,
)

MODEL, CHEAP, TWIN, NARROW = "fiction/model", "fiction/cheap", "fiction/twin", "fiction/narrow"
REGISTRY = Registry([
    Model(MODEL, "fam-a", 1.0, 2.0, 10_000),    # 0.0014 a call at the task's 1,000 and 200
    Model(CHEAP, "fam-b", 0.1, 0.2, 10_000),    # 0.00014 a call
    Model(TWIN, "fam-b", 0.5, 1.0, 10_000),
    Model(NARROW, "fam-c", 0.1, 0.2, 1_000),    # its window cannot hold 1,000 + 200
])

# the decisions on the demo's files (no generator, then the demo's generator) and on the example
# tasks (empty Stats, packaged priors), both flavors, computed at 2f8de0b before any v1.577 code;
# equal to tests/test_cascade_candidates.py's v1.535 values, so no version since v1.535 has
# changed these decisions; hashed by tests/decision_hash.py (DESIGN 4.3 v1.593, row CI32), so
# each bound rounded to 12 decimals, and recomputed so at 2f8de0b, the same under both platform
# values of `z` (the exact hashes were fed72621... and c48657f0...)
V1_576_DEMO_SELECT_SHA256 = "b3887f8d39abe681f8e317c28f0a8d30f564f71b86a6d5b94ea19d6d95755329"
V1_576_DEMO_GENERATOR_SELECT_SHA256 = (
    "0ecc62acc20a9d9aad7f588b41231cf6c7ef4cf313b5fbd9efe0b9c454cfebe1")
V1_576_EXAMPLE_SELECT_SHA256 = "2369381cc7a44f66de6512014c0ec9c5ca6df5a65074ca9239b14d114255d4da"
DEMO_GENERATOR = "demo/cedar-writer"


def noop(value, call):
    return ProcedureResult("done", tool_calls=1)


def one_call(value, call):
    return ProcedureResult(call([{"role": "user", "content": str(value)}]))


CODE = Procedure("poll", "v1", noop, max_model_calls=0, max_tool_calls=5)       # proc:poll@v1
WITH_CHEAP = Procedure("poll", "v1", one_call, max_model_calls=1, max_tool_calls=5, model=CHEAP)


def task(**fields):
    values = dict(bar=0.8, min_samples=10)
    values.update(fields)
    return Task("t", **values)


def planted(proc=(95, 100, 0.02), route=CODE.id, model=(98, 100)):
    """The model at 98 of 100; the procedure's counts and summed cost under ``route``."""
    stats = Stats()
    stats.add("t", MODEL, *model)
    if proc is not None:
        s, n, cost = proc
        stats.add("t", route, s, n, cost_usd=cost)
    return stats


def router(t=None, stats=None, priors=None, registry=REGISTRY):
    t = task() if t is None else t
    return Router(registry, {t.name: t}, planted() if stats is None else stats, priors)


def by_id(decision_or_candidates):
    candidates = getattr(decision_or_candidates, "candidates", decision_or_candidates)
    return {c.model_id: c for c in candidates}


def route(decision):
    return (decision.primary, *decision.fallbacks)


def sha(value) -> str:
    return decision_sha256(value)


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


# --- Stats: a procedure key (4.3 v1.577) ---------------------------------------------------

def test_a_procedure_key_sums_its_cost_and_gives_its_mean_per_trial():
    stats = Stats()
    stats.add("t", CODE.id, 55, 60, cost_usd=0.01)
    stats.add("t", CODE.id, 40, 40, cost_usd=0.01)
    assert stats.get("t", CODE.id) == (95, 100)
    assert stats.cost("t", CODE.id) == 0.02
    assert stats.mean_cost("t", CODE.id) == 0.02 / 100
    assert stats.tokens("t", CODE.id) == (0, 0, 0)
    assert stats.escalations("t", CODE.id) == 0


def test_an_int_cost_is_stored_as_a_float_and_none_recorded_is_zero_and_none():
    stats = Stats()
    stats.add("t", CODE.id, 1, 2, cost_usd=1)
    assert type(stats.cost("t", CODE.id)) is float and stats.mean_cost("t", CODE.id) == 0.5
    assert stats.cost("t", WITH_CHEAP.id) == 0.0 and stats.mean_cost("t", WITH_CHEAP.id) is None
    stats.add("t", MODEL, 1, 1)
    assert stats.cost("t", MODEL) == 0.0 and stats.mean_cost("t", MODEL) is None
    stats.add("t", WITH_CHEAP.id, 0, 0, cost_usd=0.0)
    assert stats.mean_cost("t", WITH_CHEAP.id) is None


def test_cost_usd_is_required_on_a_procedure_key_and_nothing_is_added_without_it():
    stats = Stats()
    with pytest.raises(ValueError, match="cost_usd"):
        stats.add("t", CODE.id, 1, 1)
    assert stats.get("t", CODE.id) == (0, 0) and stats.items() == []


@pytest.mark.parametrize("key", [MODEL, "fiction/cheap>fiction/model@sig"])
def test_cost_usd_is_refused_on_any_other_key(key):
    with pytest.raises(ValueError, match="cost_usd"):
        Stats().add("t", key, 1, 1, cost_usd=0.0, **({"escalated": 0} if ">" in key else {}))


@pytest.mark.parametrize("cost", [True, False, -0.01, math.nan, math.inf, "0.1", [0.1]])
def test_an_invalid_cost_is_a_value_error(cost):
    stats = Stats()
    with pytest.raises(ValueError, match="cost_usd"):
        stats.add("t", CODE.id, 1, 1, cost_usd=cost)
    assert stats.items() == []


def test_a_cost_never_comes_without_trials():
    stats = Stats()
    with pytest.raises(ValueError, match="cost_usd"):
        stats.add("t", CODE.id, 0, 0, cost_usd=0.5)
    stats.add("t", CODE.id, 0, 0, cost_usd=0.0)
    assert stats.get("t", CODE.id) == (0, 0) and stats.cost("t", CODE.id) == 0.0


def test_a_sum_past_the_largest_float_is_a_value_error_and_adds_nothing(tmp_path):
    # review iter-424 must-fix 1: each cost is finite, their sum is not
    stats = Stats()
    stats.add("t", CODE.id, 1, 1, cost_usd=1e308)
    with pytest.raises(ValueError, match="largest float"):
        stats.add("t", CODE.id, 1, 1, cost_usd=1e308)
    assert stats.get("t", CODE.id) == (1, 1) and stats.cost("t", CODE.id) == 1e308
    with pytest.raises(ValueError, match="largest float"):
        stats.merge(stats)
    row = {"task": "t", "model": CODE.id, "successes": 1, "trials": 1, "cost_usd": 1e308}
    path = tmp_path / "big.json"
    path.write_text(json.dumps({"stats": [row, row]}), encoding="utf-8")
    with pytest.raises(ValueError, match="big.json"):
        Stats.load(path)
    with pytest.raises(ValueError, match="largest float"):
        calibrate_from_results([{"task": "t", "model": CODE.id, "correct": True,
                                 "cost_usd": 1e308}] * 2)


def test_an_int_too_large_for_a_float_is_a_value_error(tmp_path):
    # review iter-424 should-fix 1: never an OverflowError
    with pytest.raises(ValueError, match="cost_usd"):
        Stats().add("t", CODE.id, 1, 1, cost_usd=10 ** 400)
    with pytest.raises(ValueError, match="cost_usd"):
        calibrate_from_results([{"task": "t", "model": CODE.id, "correct": True,
                                 "cost_usd": 10 ** 400}])
    path = tmp_path / "huge.json"
    path.write_text(json.dumps({"stats": [{"task": "t", "model": CODE.id, "successes": 1,
                                           "trials": 1, "cost_usd": 10 ** 400}]}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="huge.json"):
        Stats.load(path)


@pytest.mark.parametrize("extra", [dict(input_tokens=10, output_tokens=5), dict(escalated=0)])
def test_a_procedure_key_holds_no_tokens_and_no_escalations(extra):
    stats = Stats()
    with pytest.raises(ValueError):
        stats.add("t", CODE.id, 1, 1, cost_usd=0.1, **extra)
    assert stats.items() == []


@pytest.mark.parametrize("key", ["proc:", "proc:poll", "proc:poll@", "proc:@v1", "proc:poll@v1+",
                                 "proc:poll@v1+a+b", "proc:poll@v1+proc:x@v2", "proc:po ll@v1",
                                 "proc:poll@v1+a b", "proc:poll@v@1"])
def test_a_proc_key_that_is_no_procedure_id_is_a_value_error(key):
    with pytest.raises(ValueError, match="procedure"):
        Stats().add("t", key, 1, 1, cost_usd=0.1)


def test_a_procedure_key_whose_model_holds_a_gt_is_no_cascade_key():
    stats = Stats()
    stats.add("t", "proc:poll@v1+a>b@s", 1, 1, cost_usd=0.1)
    assert stats.cost("t", "proc:poll@v1+a>b@s") == 0.1


def test_merge_sums_the_costs():
    a, b = Stats(), Stats()
    a.add("t", CODE.id, 5, 10, cost_usd=0.25)
    b.add("t", CODE.id, 5, 10, cost_usd=0.5)
    b.add("t", MODEL, 1, 2)
    merged = a.merge(b)
    assert merged.get("t", CODE.id) == (10, 20) and merged.cost("t", CODE.id) == 0.75
    assert merged.cost("t", MODEL) == 0.0 and a.cost("t", CODE.id) == 0.25


def test_save_writes_cost_usd_right_after_trials_and_load_reads_it(tmp_path):
    stats = Stats()
    stats.add("t", CODE.id, 95, 100, cost_usd=0.02)
    stats.add("t", MODEL, 98, 100, input_tokens=100, output_tokens=50)
    path = tmp_path / "stats.json"
    stats.save(path)
    rows = json.loads(path.read_text(encoding="utf-8"))["stats"]
    assert list(rows[1]) == ["task", "model", "successes", "trials", "cost_usd"]
    assert rows[1]["cost_usd"] == 0.02 and "cost_usd" not in rows[0]
    again = Stats.load(path)
    assert again.cost("t", CODE.id) == 0.02 and again.get("t", CODE.id) == (95, 100)
    again.save(tmp_path / "again.json")
    assert (tmp_path / "again.json").read_bytes() == path.read_bytes()


@pytest.mark.parametrize("row", [
    {"task": "t", "model": CODE.id, "successes": 1, "trials": 1},
    {"task": "t", "model": CODE.id, "successes": 1, "trials": 1, "cost_usd": True},
    {"task": "t", "model": CODE.id, "successes": 1, "trials": 1, "cost_usd": None},
    {"task": "t", "model": CODE.id, "successes": 1, "trials": 1, "cost_usd": 0.1,
                  "input_tokens": 1, "output_tokens": 1, "token_trials": 1},
    # a guard: escalated on a row that is no cascade was refused before v1.577 too
    {"task": "t", "model": CODE.id, "successes": 1, "trials": 1, "cost_usd": 0.1, "escalated": 0},
])
def test_load_refuses_a_bad_procedure_row_naming_the_file(tmp_path, row):
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"stats": [row]}), encoding="utf-8")
    with pytest.raises(ValueError, match="bad.json"):
        Stats.load(path)


def test_guard_load_ignores_cost_usd_on_a_model_row_and_save_drops_it(tmp_path):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps({"stats": [
        {"task": "t", "model": MODEL, "successes": 3, "trials": 4, "cost_usd": 9.5}]}),
        encoding="utf-8")
    stats = Stats.load(path)
    assert stats.get("t", MODEL) == (3, 4)
    stats.save(tmp_path / "out.json")
    assert json.loads((tmp_path / "out.json").read_text(encoding="utf-8")) == {
        "stats": [{"task": "t", "model": MODEL, "successes": 3, "trials": 4}]}


def test_calibrate_reads_a_procedure_rows_cost_and_its_slice():
    rows = [{"task": "t", "model": CODE.id, "correct": True, "cost_usd": 0.001},
            {"task": "t", "model": CODE.id, "correct": False, "cost_usd": 0.003, "slice": "deep"},
            {"task": "t", "model": MODEL, "correct": True}]
    stats = calibrate_from_results(rows)
    assert stats.get("t", CODE.id) == (1, 2) and stats.cost("t", CODE.id) == 0.001 + 0.003
    assert stats.get("t@deep", CODE.id) == (0, 1) and stats.cost("t@deep", CODE.id) == 0.003


@pytest.mark.parametrize("extra", [
    {}, {"cost_usd": True},
    {"cost_usd": -1}, {"cost_usd": "0.1"},
    {"cost_usd": 0.1, "input_tokens": 1, "output_tokens": 1},
    {"cost_usd": 0.1, "escalated": False},  # a guard: refused on a row that is no cascade before
])
def test_calibrate_refuses_a_bad_procedure_row_before_any_stats_exist(extra):
    rows = [{"task": "t", "model": MODEL, "correct": True},
            dict({"task": "t", "model": CODE.id, "correct": True}, **extra)]
    with pytest.raises(ValueError):
        calibrate_from_results(rows)


def test_guard_calibrate_ignores_cost_usd_on_a_model_row():
    stats = calibrate_from_results([{"task": "t", "model": MODEL, "correct": True,
                                     "cost_usd": 0.5}])
    assert stats.items() == [(("t", MODEL), (1, 1))]


# --- the reason code and the keyword (5.1, 5.2 v1.577) -------------------------------------

def test_the_reason_code_is_exported_after_cheaper_per_success():
    assert model_routing.PROCEDURE_UNKNOWN_MODEL == "procedure_unknown_model"
    assert model_routing.router.PROCEDURE_UNKNOWN_MODEL == "procedure_unknown_model"
    names = model_routing.__all__
    assert names.index("PROCEDURE_UNKNOWN_MODEL") == names.index("CHEAPER_PER_SUCCESS") + 1


@pytest.mark.parametrize("value", [None, CODE, "proc:poll@v1", {CODE}, (CODE, "x"), [1],
                                   iter([CODE])])
def test_procedures_that_is_not_a_list_or_tuple_of_procedures_is_a_value_error(value):
    with pytest.raises(ValueError, match="procedures"):
        router().select("t", procedures=value)


def test_the_procedures_check_comes_before_the_task_lookup():
    with pytest.raises(ValueError, match="procedures"):
        router().select("no-such-task", procedures=None)


def test_two_procedures_with_one_id_are_a_value_error():
    twin = Procedure("poll", "v1", one_call, max_model_calls=0, max_tool_calls=0)  # same ID
    with pytest.raises(ValueError, match="proc:poll@v1"):
        router().select("t", procedures=[CODE, twin])


def test_a_registry_id_equal_to_a_procedure_id_is_a_value_error_with_procedures_only():
    registry = Registry([Model(MODEL, "fam-a", 1.0, 2.0, 10_000),
                         Model(CODE.id, "fam-x", 1.0, 2.0, 10_000)])
    r = router(stats=Stats(), registry=registry)
    with pytest.raises(ValueError, match="proc:poll@v1"):
        r.select("t", procedures=[CODE])
    with pytest.raises(NoModelClearsBar):  # without procedures there is no such check
        r.select("t")


# --- the candidate (5.2 v1.577) --------------------------------------------------------------

def test_one_candidate_per_procedure_after_the_models_and_cascades_in_the_order_given():
    t = task(cascades=(Cascade(CHEAP, MODEL, "sig"),))
    v2 = Procedure("poll", "v2", noop, max_model_calls=0, max_tool_calls=5)
    decision = router(t).select("t", cascades=True, procedures=[v2, WITH_CHEAP, CODE])
    ids = [c.model_id for c in decision.candidates]
    assert ids == [MODEL, CHEAP, TWIN, NARROW, t.cascades[0].id, v2.id, WITH_CHEAP.id, CODE.id]


def test_a_planted_procedure_by_hand_cost_effective():
    decision = router().select("t", procedures=[CODE])
    c = by_id(decision)[CODE.id]
    assert (c.successes, c.trials, c.reason, c.eligible, c.passes) == (95, 100, "passes", True, True)
    assert c.quality_lb == wilson_lower_bound(95, 100) and round(c.quality_lb, 6) == 0.88825
    assert c.list_cost == c.routing_cost == 0.02 / 100 and c.family == ""
    assert route(decision) == (CODE.id, MODEL)
    assert decision.basis == "measured" and decision.below_bar is False
    assert set(decision.to_dict()["candidates"][-1]) == {
        "model_id", "family", "successes", "trials", "quality_lb", "routing_cost", "list_cost",
        "eligible", "passes", "reason"}


def test_a_planted_procedure_by_hand_cost_blind():
    decision = router().select("t", "cost_blind", procedures=[CODE])
    c = by_id(decision)[CODE.id]
    assert c.routing_cost == 0.0 and c.list_cost == 0.02 / 100
    assert route(decision) == (MODEL, CODE.id)  # 0.929988 above 0.888250


@pytest.mark.parametrize("counts, cost, passes, first", [
    ((95, 100), 0.02, True, CODE.id),   # clears the bar, 0.0002 a trial: the procedure wins
    ((80, 100), 0.02, False, MODEL),    # below the bar (0.711171): it never wins, however cheap
    ((95, 100), 1.0, True, MODEL),      # clears it at 0.01 a trial, dearer than 0.0014: it loses
    ((9, 9), 0.0, False, MODEL),        # 9 trials under min_samples 10: insufficient_samples
])
def test_a_procedure_wins_only_when_it_clears_the_bar_and_is_cheaper(counts, cost, passes, first):
    decision = router(stats=planted((*counts, cost))).select("t", procedures=[CODE])
    assert decision.primary == first
    assert by_id(decision)[CODE.id].passes is passes


def test_a_new_version_starts_at_zero_trials_and_an_unmeasured_one_costs_one_call():
    v2 = Procedure("poll", "v2", one_call, max_model_calls=1, max_tool_calls=5, model=CHEAP)
    decision = router(stats=planted(route=WITH_CHEAP.id)).select("t", procedures=[v2, CODE])
    new, bare = by_id(decision)[v2.id], by_id(decision)[CODE.id]
    assert (new.trials, new.reason, new.family) == (0, "insufficient_samples", "fam-b")
    assert new.list_cost == REGISTRY.get(CHEAP).cost(1_000, 200)
    assert (bare.trials, bare.list_cost, bare.reason) == (0, 0.0, "insufficient_samples")
    assert decision.primary == MODEL


def test_another_model_is_another_route():
    other = Procedure("poll", "v1", one_call, max_model_calls=1, max_tool_calls=5, model=TWIN)
    decision = router(stats=planted(route=WITH_CHEAP.id)).select(
        "t", procedures=[WITH_CHEAP, other])
    assert by_id(decision)[WITH_CHEAP.id].passes and by_id(decision)[other.id].trials == 0


@pytest.mark.parametrize("kw, fields, reason", [
    (dict(exclude_models=[CHEAP]), {}, "excluded_model"),
    (dict(exclude_models=[WITH_CHEAP.id]), {}, "excluded_model"),
    ({}, dict(exclude_families=("fam-b",)), "excluded_family"),
    (dict(generator_model=CHEAP), dict(independent_of_generator=True), "generator"),
    (dict(generator_model=TWIN), dict(independent_of_generator=True), "generator_family"),
    (dict(prompt_tokens=9_900), {}, "context_too_small"),
])
def test_rules_1_to_5_run_on_the_named_model(kw, fields, reason):
    stats = planted(route=WITH_CHEAP.id)
    try:
        candidates = router(task(**fields), stats).select("t", procedures=[WITH_CHEAP], **kw)
    except NoModelClearsBar as exc:  # at 9,900 tokens no model of REGISTRY can hold the call
        candidates = exc.candidates
    c = by_id(candidates)[WITH_CHEAP.id]
    assert (c.reason, c.eligible, c.passes) == (reason, False, False)


def candidate(proc, t=None, stats=None, registry=REGISTRY, **kw):
    """The procedure's candidate, from the decision or the NoModelClearsBar it raises."""
    try:
        candidates = router(t, stats, registry=registry).select("t", procedures=[proc], **kw)
    except NoModelClearsBar as exc:
        candidates = exc.candidates
    return by_id(candidates)[proc.id]


def test_an_unknown_model_comes_before_the_procedures_own_exclusion():
    ghost = Procedure("poll", "v1", one_call, max_model_calls=1, max_tool_calls=0,
                      model="fiction/ghost")
    assert candidate(ghost, stats=planted(route=ghost.id), exclude_models=[ghost.id]).reason == (
        "procedure_unknown_model")


@pytest.mark.parametrize("kw, fields, reason", [
    # rule 1 on its own ID comes before every rule on its model
    (dict(exclude_models=[WITH_CHEAP.id], generator_model=CHEAP, prompt_tokens=9_900),
     dict(exclude_families=("fam-b",), independent_of_generator=True), "excluded_model"),
    # on the model, rule 1 before 2, 2 before 3, 3 before 4 and 4 before 5
    (dict(exclude_models=[CHEAP]), dict(exclude_families=("fam-b",)), "excluded_model"),
    (dict(generator_model=CHEAP), dict(exclude_families=("fam-b",), independent_of_generator=True),
     "excluded_family"),
    (dict(generator_model=CHEAP, prompt_tokens=9_900), dict(independent_of_generator=True),
     "generator"),
    (dict(generator_model=TWIN, prompt_tokens=9_900), dict(independent_of_generator=True),
     "generator_family"),
])
def test_the_rules_apply_in_their_order(kw, fields, reason):
    # review iter-424 should-fix 3
    assert candidate(WITH_CHEAP, task(**fields), planted(route=WITH_CHEAP.id), **kw).reason == reason


@pytest.mark.parametrize("kw, reason", [
    (dict(exclude_models=[CHEAP]), "excluded_model"),
    (dict(generator_model=CHEAP), "generator"),
    ({}, "passes"),
])
def test_a_variant_named_model_is_ruled_out_by_its_base(kw, reason):
    # review iter-424 should-fix 3: excluding the base, or the base as the generator (5.2 v1.572)
    high = Model(CHEAP + "@high", "fam-b", 0.1, 0.2, 10_000, variant=Variant("high"))
    registry = Registry([*REGISTRY.models, high])
    proc = Procedure("poll", "v1", one_call, max_model_calls=1, max_tool_calls=0, model=high.id)
    t = task(independent_of_generator=True)
    assert candidate(proc, t, planted(route=proc.id), registry, **kw).reason == reason


@pytest.mark.parametrize("kw, match", [(dict(flavor="bad"), "flavor"),
                                       (dict(prompt_tokens=-1), "prompt_tokens"),
                                       (dict(slice="a@b"), "slice"),
                                       (dict(cascades=1), "cascades")])
def test_the_earlier_keyword_checks_come_before_the_procedures_check(kw, match):
    # review iter-424 should-fix 3: procedures is checked right after cascades
    with pytest.raises(ValueError, match=match):
        router().select("t", procedures=None, **kw)


def test_a_window_too_small_for_the_tasks_sizes_rules_out_the_procedure():
    narrow = Procedure("poll", "v1", one_call, max_model_calls=1, max_tool_calls=0, model=NARROW)
    c = by_id(router(stats=planted(route=narrow.id)).select("t", procedures=[narrow]))[narrow.id]
    assert c.reason == "context_too_small"


def test_a_procedure_without_a_model_meets_no_model_rule():
    t = task(independent_of_generator=True, exclude_families=("",))
    decision = router(t).select("t", generator_model=MODEL, prompt_tokens=10 ** 9,
                                procedures=[CODE])
    assert by_id(decision)[CODE.id].reason == "passes" and decision.primary == CODE.id


def test_a_procedure_whose_model_the_registry_lacks():
    ghost = Procedure("poll", "v1", one_call, max_model_calls=1, max_tool_calls=0,
                      model="fiction/ghost")
    c = by_id(router(stats=planted(route=ghost.id)).select("t", procedures=[ghost]))[ghost.id]
    assert (c.reason, c.eligible, c.passes, c.family) == (
        "procedure_unknown_model", False, False, "")
    assert (c.successes, c.trials, c.routing_cost, c.list_cost) == (95, 100, 0.0, 0.0)


def test_the_procedure_reads_its_slice_key_alone():
    stats = planted()
    stats.add("t@deep", CODE.id, 20, 20, cost_usd=0.01)
    stats.add("t@deep", MODEL, 20, 20)
    t = task(slices={"deep": {"bar": 0.8, "min_samples": 15}})
    c = by_id(router(t, stats).select("t", slice="deep", procedures=[CODE]))[CODE.id]
    assert (c.successes, c.trials, c.list_cost) == (20, 20, 0.01 / 20)
    shallow = Procedure("poll", "v9", noop, max_model_calls=0, max_tool_calls=5)
    assert by_id(router(t, stats).select("t", slice="deep", procedures=[shallow]))[
        shallow.id].trials == 0


def test_a_procedure_enters_the_best_available_measured_list():
    t = task(bar=0.99, on_no_model="best_available")
    decision = router(t).select("t", procedures=[CODE])
    assert decision.below_bar is True and route(decision) == (MODEL, CODE.id)


def test_a_procedure_is_a_below_bar_fallback_as_a_model_is():
    t = task(fallback_below_bar=True)
    decision = router(t, planted((80, 100, 0.02))).select("t", procedures=[CODE])
    assert route(decision) == (MODEL, CODE.id) and decision.below_bar_fallbacks == (CODE.id,)


def test_priors_never_admit_a_procedure():
    priors = Priors({"cat": {"scores": {MODEL: 0.5, CODE.id: 0.99}}})
    t = task(on_no_model="best_available", prior_category="cat")
    decision = router(t, Stats(), priors).select("t", procedures=[CODE])
    assert (decision.basis, route(decision)) == ("prior", (MODEL,))
    only = Priors({"cat": {"scores": {CODE.id: 0.99}}})
    with pytest.raises(NoModelClearsBar):
        router(t, Stats(), only).select("t", procedures=[CODE])


def test_no_model_clears_bar_carries_the_procedure_candidates():
    with pytest.raises(NoModelClearsBar) as info:
        router(task(bar=0.99)).select("t", procedures=[CODE])
    assert [c.model_id for c in info.value.candidates][-1] == CODE.id
    assert str(info.value) == "no model clears the bar 0.99 for task 't'"


@pytest.mark.parametrize("flavor, pick_reason", [("cost_effective", "cheaper_per_success"),
                                                 ("cost_blind", None)])
def test_retry_same_puts_a_procedure_cheaper_per_trial_but_dearer_per_success_second(
        flavor, pick_reason):
    # review iter-424 should-fix 2: 0.00084 / 0.502003 is 0.00167330 per success, above the
    # model's 0.0014 / 0.945514, 0.00148068; in cost_blind both are 0 and the bound decides
    stats = planted((60, 100, 0.084), model=(99, 100))
    decision = router(task(bar=0.5, failure_policy="retry_same"), stats).select(
        "t", flavor, procedures=[CODE])
    assert route(decision) == (MODEL, CODE.id) and decision.pick_reason == pick_reason
    per_call = router(task(bar=0.5), stats).select("t", flavor, procedures=[CODE])
    assert route(per_call) == ((CODE.id, MODEL) if flavor == "cost_effective" else (MODEL, CODE.id))


@pytest.mark.parametrize("fields", [dict(failure_policy="retry_same"),
                                    dict(fallback_below_bar=True),
                                    dict(bar=0.99, on_no_model="best_available")])
def test_an_unmeasured_procedure_enters_no_order(fields):
    # review iter-424 should-fix 2: its cost, one call or 0.0, never decides
    stats = planted(proc=None)
    stats.add("t", TWIN, 7, 10)  # a below-bar model with trials, so the fallback list is not empty
    bare_and_named = [CODE, WITH_CHEAP]
    decision = router(task(**fields), stats).select("t", procedures=bare_and_named)
    assert not set(route(decision)) & {CODE.id, WITH_CHEAP.id}
    assert not set(decision.below_bar_fallbacks) & {CODE.id, WITH_CHEAP.id}


def test_retry_same_orders_a_procedure_by_cost_per_success():
    t = task(failure_policy="retry_same")
    decision = router(t).select("t", procedures=[CODE])
    assert decision.primary == CODE.id
    assert decision.expected_cost_per_success_usd == (0.02 / 100) / wilson_lower_bound(95, 100)


# --- unchanged without procedures ------------------------------------------------------------

def test_guard_without_the_keyword_the_demo_and_example_tasks_route_as_v1_576():
    registry, tasks, stats = demo_files()
    assert sha(routes(registry, tasks, stats, None)) == V1_576_DEMO_SELECT_SHA256
    assert sha(routes(registry, tasks, stats, None, generator_model=DEMO_GENERATOR)) == (
        V1_576_DEMO_GENERATOR_SELECT_SHA256)
    registry, tasks, priors = example_files()
    assert sha(routes(registry, tasks, Stats(), priors)) == V1_576_EXAMPLE_SELECT_SHA256


def test_the_v1_576_demo_hashes_are_the_same_under_either_platforms_z(monkeypatch):
    import model_routing.stats as stats_module
    for z in PLATFORM_Z:  # DESIGN 4.3 v1.593, row CI32
        monkeypatch.setattr(stats_module, "NormalDist", FixedZ(z))
        registry, tasks, stats = demo_files()
        assert sha(routes(registry, tasks, stats, None)) == V1_576_DEMO_SELECT_SHA256
        assert sha(routes(registry, tasks, stats, None, generator_model=DEMO_GENERATOR)) == (
            V1_576_DEMO_GENERATOR_SELECT_SHA256)


@pytest.mark.parametrize("empty", [(), []])
def test_an_empty_procedures_routes_the_demo_and_example_tasks_as_v1_576(empty):
    registry, tasks, stats = demo_files()
    assert sha(routes(registry, tasks, stats, None, procedures=empty)) == V1_576_DEMO_SELECT_SHA256
    registry, tasks, priors = example_files()
    assert sha(routes(registry, tasks, Stats(), priors, procedures=empty)) == (
        V1_576_EXAMPLE_SELECT_SHA256)


def test_an_unmeasured_procedure_adds_a_last_candidate_and_changes_no_route():
    registry, tasks, stats = demo_files()
    for name in tasks:
        for flavor in ("cost_effective", "cost_blind"):
            r = Router(registry, tasks, stats)
            try:
                before = r.select(name, flavor).to_dict()
            except NoModelClearsBar:
                with pytest.raises(NoModelClearsBar):
                    r.select(name, flavor, procedures=[CODE])
                continue
            after = r.select(name, flavor, procedures=[CODE]).to_dict()
            last = after["candidates"].pop()
            assert after == before and last["model_id"] == CODE.id and last["trials"] == 0
