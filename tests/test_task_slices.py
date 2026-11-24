"""DESIGN 4.2, 4.3, 5.1, 5.2, 7, 8.1 and 10 v1.511 (row STRAT1): task slices.

A call can name a slice of its task, a part of its items the caller knows before the call.
`Router.select(slice=...)` then routes on that slice's own counts, kept in `Stats` under the
task key `<task>@<slice>`, with the `bar`, `min_samples` and token sizes the task's `slices`
give it (the task's own where it gives none); pooled counts never clear a slice's bar. A
calibration row can carry `slice`, which adds its trial under the task and the slice key,
`Executor.call(slice=...)` passes it on, every record gains `slice`, and `select --slice S`
names it on the command line. Row STRAT1a wrote these tests under strict xfail and row
STRAT1b implemented v1.511; the guards pinned what v1.511 keeps and passed before and after.

The planted mix is the row's example: on `support`, 400 quick items and 100 deep ones.
fiction/cheap answers 396 quick and 64 deep (pooled 460 of 500, Wilson lower bound 0.892894,
clearing 0.85; deep alone 0.542354), fiction/mid 392 and 95 (deep 0.888250, under a 0.9 bar),
fiction/best every item (deep 0.963007), fiction/weak half of each.
"""

import dataclasses
import json

import pytest

from model_routing import (
    Completion, Executor, FakeProvider, Monitor, NoModelClearsBar, Registry, Router, Stats,
    Task, calibrate_from_results, load_tasks, wilson_lower_bound,
)
from model_routing.cli import main
from model_routing.demo import _tasks_json

V1_506_KEYS = ["ts", "call_id", "task", "flavor", "model", "family", "attempt", "final",
               "outcome", "error", "latency_ms", "input_tokens", "output_tokens", "cost_usd",
               "routing_cost_usd", "below_bar", "basis", "tags"]
SIZE_KEYS = ["prompt_tokens", "prompt_tokens_estimated"]

# (model, quick successes of 400, deep successes of 100)
MIX = [("fiction/cheap", 396, 64), ("fiction/mid", 392, 95), ("fiction/best", 400, 100),
       ("fiction/weak", 200, 50)]


@pytest.fixture
def slice_registry(model_factory):
    return Registry([
        model_factory("fiction/cheap", "small", 1.0, 2.0, 2000),
        model_factory("fiction/mid", "medium", 3.0, 6.0, 8000),
        model_factory("fiction/best", "large", 10.0, 20.0, 8000),
        model_factory("fiction/weak", "tiny", 0.5, 1.0, 8000),
    ])


def mix_rows():
    rows = []
    for model, quick, deep in MIX:
        for name, right, total in (("quick", quick, 400), ("deep", deep, 100)):
            rows += [{"task": "support", "model": model, "correct": i < right, "slice": name}
                     for i in range(total)]
    return rows


def mix_stats():
    stats = Stats()
    for model, quick, deep in MIX:
        stats.add("support", model, quick + deep, 500)
        stats.add("support@quick", model, quick, 400)
        stats.add("support@deep", model, deep, 100)
    return stats


def support_task(**overrides):
    fields = {"name": "support", "bar": 0.85, "min_samples": 30}
    fields.update(overrides)
    return Task(**fields)


def make_router(registry, stats=None, **overrides):
    task = support_task(**overrides)
    return Router(registry, {task.name: task}, mix_stats() if stats is None else stats)


def reasons(decision_or_candidates):
    candidates = getattr(decision_or_candidates, "candidates", decision_or_candidates)
    return {c.model_id: c.reason for c in candidates}


def route(decision):
    return (decision.primary, *decision.fallbacks)


def executor_for(router, monitor, script=None):
    ticks = iter(float(t) for t in range(100))
    script = script or {m: (lambda messages: Completion("done", 10, 5)) for m, _, _ in MIX}
    return Executor(router, FakeProvider(script), monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: "2026-01-02T03:04:05Z", id_factory=lambda: "fixed-call")


MESSAGES = [{"role": "user", "content": "the ticket"}]


# --- guards: what v1.511 keeps -------------------------------------------------------------

def test_the_planted_numbers_are_the_docstring_ones():
    assert round(wilson_lower_bound(460, 500), 6) == 0.892894
    assert round(wilson_lower_bound(64, 100), 6) == 0.542354
    assert round(wilson_lower_bound(95, 100), 6) == 0.888250
    assert round(wilson_lower_bound(100, 100), 6) == 0.963007


def test_without_a_slice_the_pooled_route_takes_the_cheap_model(slice_registry):
    decision = make_router(slice_registry).select("support")
    assert route(decision) == ("fiction/cheap", "fiction/mid", "fiction/best")
    assert reasons(decision)["fiction/weak"] == "below_bar"
    assert "slice" not in decision.to_dict()


def test_rows_without_a_slice_count_once_under_the_task():
    rows = [{"task": "support", "model": "m/a", "correct": True},
            {"task": "support", "model": "m/a", "correct": False, "slice": None}]
    stats = calibrate_from_results(rows)
    assert stats.get("support", "m/a") == (1, 2)
    assert dict(stats.items()) == {("support", "m/a"): (1, 2)}


# --- 4.2 the field -------------------------------------------------------------------------

def test_slices_follows_fallback_below_bar_and_is_empty_by_default():
    names = [f.name for f in dataclasses.fields(Task)]
    # cascades: v1.535; failure_policy: v1.567; shadow_rate and shadow_route: v1.607
    at = names.index("fallback_below_bar")
    assert names[at:at + 4] == ["fallback_below_bar", "slices", "cascades", "failure_policy"]
    assert Task("t", 0.5).slices == {}


def test_the_task_stores_a_copy_and_stays_hashable():
    given = {"deep": {"bar": 0.9}}
    task = Task("t", 0.5, slices=given)
    given["deep"]["bar"] = 0.1
    given["quick"] = {}
    assert task.slices == {"deep": {"bar": 0.9}}
    assert isinstance(hash(task), int)
    assert task == Task("t", 0.5, slices={"deep": {"bar": 0.9}})
    assert task != Task("t", 0.5)


@pytest.mark.parametrize("slices", [
    {"deep": {"bar": 0.9, "min_samples": 50, "expected_input_tokens": 3000,
              "expected_output_tokens": 600}},
    {"deep": {}},
    {"deep": {"bar": 1}, "quick": {"bar": 0.0}},
])
def test_valid_slices_are_accepted(slices):
    assert Task("t", 0.5, slices=slices).slices == slices


@pytest.mark.parametrize("slices", [
    [("deep", {})], "deep", {"deep": [("bar", 0.9)]}, {"": {}}, {"a@b": {}}, {3: {}},
    {"deep": {"confidence": 0.9}}, {"deep": {"bar": 1.5}}, {"deep": {"bar": -0.1}},
    {"deep": {"bar": float("nan")}}, {"deep": {"bar": True}}, {"deep": {"bar": "0.9"}},
    {"deep": {"min_samples": 0}}, {"deep": {"min_samples": 2.0}},
    {"deep": {"min_samples": True}}, {"deep": {"expected_input_tokens": -1}},
    {"deep": {"expected_output_tokens": 1.5}}, {"deep": {"expected_input_tokens": None}},
])
def test_an_invalid_slice_raises_valueerror_naming_the_task(slices):
    with pytest.raises(ValueError, match="'t'"):
        Task("t", 0.5, slices=slices)


def test_a_task_whose_name_holds_an_at_sign_has_no_slices():
    assert Task("a@b", 0.5).slices == {}
    with pytest.raises(ValueError, match="a@b"):
        Task("a@b", 0.5, slices={"deep": {}})


def test_load_tasks_reads_slices(write_json):
    path = write_json("tasks.json", {"tasks": [
        {"name": "support", "bar": 0.85, "slices": {"deep": {"bar": 0.9}}},
        {"name": "other", "bar": 0.5}]})
    tasks = load_tasks(path)
    assert tasks["support"].slices == {"deep": {"bar": 0.9}}
    assert tasks["other"].slices == {}


def test_the_demo_tasks_file_names_no_empty_slices():
    assert "slices" not in json.loads(_tasks_json(support_task()))["tasks"][0]


def test_the_demo_tasks_file_writes_slices_that_are_not_empty(tmp_path):
    text = _tasks_json(support_task(slices={"deep": {"bar": 0.9}}))
    assert json.loads(text)["tasks"][0]["slices"] == {"deep": {"bar": 0.9}}
    path = tmp_path / "tasks.json"
    path.write_text(text, encoding="utf-8")
    assert load_tasks(path)["support"] == support_task(slices={"deep": {"bar": 0.9}})


# --- 4.3 calibration rows ------------------------------------------------------------------

def test_a_sliced_row_counts_under_the_task_and_the_slice_key():
    stats = calibrate_from_results(mix_rows())
    for model, quick, deep in MIX:
        assert stats.get("support", model) == (quick + deep, 500)
        assert stats.get("support@quick", model) == (quick, 400)
        assert stats.get("support@deep", model) == (deep, 100)
    assert stats.get("support@deep", "fiction/cheap") == mix_stats().get(
        "support@deep", "fiction/cheap")


def test_a_sliced_row_carries_its_tokens_to_both_keys():
    rows = [{"task": "support", "model": "m/a", "correct": True, "slice": "deep",
             "input_tokens": 300, "output_tokens": 40},
            {"task": "support", "model": "m/a", "correct": True,
             "input_tokens": 100, "output_tokens": 20}]
    stats = calibrate_from_results(rows)
    assert stats.tokens("support", "m/a") == (400, 60, 2)
    assert stats.tokens("support@deep", "m/a") == (300, 40, 1)


@pytest.mark.parametrize("row", [
    {"task": "support", "model": "m/a", "correct": True, "slice": ""},
    {"task": "support", "model": "m/a", "correct": True, "slice": "a@b"},
    {"task": "support", "model": "m/a", "correct": True, "slice": 3},
    {"task": "support", "model": "m/a", "correct": True, "slice": True},
    {"task": "support", "model": "m/a", "correct": True, "slice": ["deep"]},
    {"task": "a@b", "model": "m/a", "correct": True, "slice": "deep"},
])
def test_an_invalid_slice_in_a_row_raises_valueerror(row):
    good = {"task": "support", "model": "m/a", "correct": True}
    with pytest.raises(ValueError):
        calibrate_from_results([good, row])


# --- 5.1 and 5.2 routing on a slice --------------------------------------------------------

def test_the_deep_slice_routes_past_the_model_the_pooled_rate_admits(slice_registry):
    router = make_router(slice_registry)
    assert router.select("support").primary == "fiction/cheap"
    deep = router.select("support", slice="deep")
    assert route(deep) == ("fiction/mid", "fiction/best")
    assert reasons(deep) == {"fiction/cheap": "below_bar", "fiction/mid": "passes",
                             "fiction/best": "passes", "fiction/weak": "below_bar"}
    cheap = {c.model_id: c for c in deep.candidates}["fiction/cheap"]
    assert (cheap.successes, cheap.trials) == (64, 100)
    assert cheap.quality_lb == wilson_lower_bound(64, 100)
    assert (deep.task, deep.slice, deep.below_bar, deep.basis) == (
        "support", "deep", False, "measured")


def test_the_quick_slice_keeps_the_cheap_model(slice_registry):
    quick = make_router(slice_registry).select("support", slice="quick")
    assert route(quick) == ("fiction/cheap", "fiction/mid", "fiction/best")
    assert quick.slice == "quick"


def test_a_slice_bar_of_its_own(slice_registry):
    router = make_router(slice_registry, slices={"deep": {"bar": 0.9}})
    deep = router.select("support", slice="deep")
    assert route(deep) == ("fiction/best",)
    assert reasons(deep)["fiction/mid"] == "below_bar"
    assert router.select("support", slice="quick").primary == "fiction/cheap"
    assert router.select("support").primary == "fiction/cheap"


def test_a_slice_min_samples_of_its_own(slice_registry):
    router = make_router(slice_registry, slices={"deep": {"min_samples": 101}})
    with pytest.raises(NoModelClearsBar,
                       match=r"^no model clears the bar 0\.85 for task 'support' slice 'deep'$"
                       ) as caught:
        router.select("support", slice="deep")
    assert set(reasons(caught.value.candidates).values()) == {"insufficient_samples"}


def test_the_refusal_names_the_slice_and_its_bar(slice_registry):
    router = make_router(slice_registry, slices={"deep": {"bar": 0.99}})
    with pytest.raises(NoModelClearsBar) as caught:
        router.select("support", slice="deep")
    assert str(caught.value) == "no model clears the bar 0.99 for task 'support' slice 'deep'"
    cold = make_router(slice_registry, stats=Stats(), on_no_model="best_available")
    with pytest.raises(NoModelClearsBar) as caught:
        cold.select("support", slice="deep")
    assert str(caught.value) == (
        "no eligible measured or prior-scored model for task 'support' slice 'deep'")
    with pytest.raises(NoModelClearsBar) as caught:
        cold.select("support")
    assert str(caught.value) == "no eligible measured or prior-scored model for task 'support'"


def test_pooled_counts_never_clear_a_slice(slice_registry):
    pooled = Stats()
    for model, _, _ in MIX:
        pooled.add("support", model, 500, 500)
    router = make_router(slice_registry, stats=pooled)
    assert router.select("support").primary == "fiction/weak"
    with pytest.raises(NoModelClearsBar) as caught:
        router.select("support", slice="deep")
    assert set(reasons(caught.value.candidates).values()) == {"insufficient_samples"}


def test_slice_counts_never_reach_a_call_without_a_slice(slice_registry):
    sliced = Stats()
    for model, _, _ in MIX:
        sliced.add("support@deep", model, 100, 100)
    router = make_router(slice_registry, stats=sliced)
    assert router.select("support", slice="deep").primary == "fiction/weak"
    with pytest.raises(NoModelClearsBar):
        router.select("support")


def test_on_no_model_applies_on_the_slice_as_without_one(slice_registry, priors):
    router = make_router(slice_registry, on_no_model="best_available",
                         slices={"deep": {"bar": 0.99}})
    deep = router.select("support", slice="deep")
    assert (deep.primary, deep.below_bar, deep.basis, deep.slice) == (
        "fiction/best", True, "measured", "deep")
    task = support_task(on_no_model="best_available", prior_category="judging")
    cold = Router(slice_registry, {"support": task}, Stats(), priors)
    decision = cold.select("support", slice="deep")
    assert (decision.basis, decision.below_bar, decision.slice) == ("prior", True, "deep")


def test_the_slice_sizes_stand_for_the_task_in_rule_5_and_in_the_price(slice_registry):
    # fiction/cheap's window of 2,000 holds 1,000 + 200 but not 1,900 + 200
    router = make_router(slice_registry,
                         slices={"quick": {"expected_input_tokens": 1900}})
    quick = router.select("support", slice="quick")
    assert reasons(quick)["fiction/cheap"] == "context_too_small"
    assert quick.primary == "fiction/mid"
    mid = {c.model_id: c for c in quick.candidates}["fiction/mid"]
    assert mid.list_cost == slice_registry.get("fiction/mid").cost(1900, 200)
    assert router.select("support").primary == "fiction/cheap"
    small = router.select("support", slice="quick", prompt_tokens=500)
    assert small.primary == "fiction/cheap"


def test_measured_slice_tokens_price_the_slice(slice_registry):
    stats = mix_stats()
    stats.add("support@deep", "fiction/mid", 0, 1, input_tokens=3000, output_tokens=600)
    stats.add("support", "fiction/mid", 0, 1, input_tokens=100, output_tokens=20)
    deep = make_router(slice_registry, stats=stats).select("support", slice="deep")
    mid = {c.model_id: c for c in deep.candidates}["fiction/mid"]
    assert mid.list_cost == slice_registry.get("fiction/mid").cost(3000, 600)


def test_the_decision_names_the_slice_after_the_task(slice_registry):
    names = [f.name for f in dataclasses.fields(type(make_router(slice_registry)
                                                     .select("support")))]
    # v1.567 (row CPS1a): the three cost-per-success fields come after it
    # v1.628 (row LAT1b): the latency bar, max_p95_ms, comes after them
    assert names[-5:] == ["slice", "failure_policy", "expected_cost_per_success_usd", "pick_reason",
                          "max_p95_ms"]
    deep = make_router(slice_registry).select("support", slice="deep")
    assert list(deep.to_dict()) == ["task", "slice", "flavor", "primary", "fallbacks",
                                    "below_bar", "basis", "candidates"]
    assert deep.to_dict()["slice"] == "deep"
    assert make_router(slice_registry).select("support").slice is None


@pytest.mark.parametrize("value", ["", "a@b", 3, True, b"deep"])
def test_an_invalid_slice_raises_valueerror_before_the_task_lookup(slice_registry, value):
    router = make_router(slice_registry)
    with pytest.raises(ValueError):
        router.select("support", slice=value)
    with pytest.raises(ValueError):
        router.select("no_such_task", slice=value)


def test_a_slice_key_that_another_task_owns_raises_valueerror(slice_registry):
    tasks = {"support": support_task(), "support@deep": support_task(name="support@deep"),
             "a@b": support_task(name="a@b")}
    router = Router(slice_registry, tasks, mix_stats())
    with pytest.raises(ValueError, match="support@deep"):
        router.select("support", slice="deep")
    with pytest.raises(ValueError, match="a@b"):
        router.select("a@b", slice="deep")
    assert router.select("support", slice="quick").primary == "fiction/cheap"
    # the task named support@deep reads the very counts a deep slice of support would
    assert router.select("support@deep").primary == "fiction/mid"


# --- 7 and 8.1 the executor and the records ------------------------------------------------

def test_a_sliced_call_runs_the_slice_route_and_records_the_slice(slice_registry):
    monitor = Monitor()
    executor = executor_for(make_router(slice_registry), monitor,
                            {"fiction/mid": lambda m: Completion("{", 10, 5),
                             "fiction/best": lambda m: Completion("done", 10, 5)})
    result = executor.call("support", MESSAGES, slice="deep",
                           validate=lambda text: text == "done")
    assert [m for m, _ in executor.provider.calls] == ["fiction/mid", "fiction/best"]
    assert (result.model, result.decision.slice) == ("fiction/best", "deep")
    for record in monitor.records:
        assert list(record) == V1_506_KEYS + ["slice"] + SIZE_KEYS
        assert record["slice"] == "deep" and record["task"] == "support"


def test_a_call_without_a_slice_records_null(slice_registry):
    monitor = Monitor()
    executor_for(make_router(slice_registry), monitor).call("support", MESSAGES)
    assert [list(r) for r in monitor.records] == [V1_506_KEYS + ["slice"] + SIZE_KEYS]
    assert monitor.records[0]["slice"] is None
    assert monitor.records[0]["model"] == "fiction/cheap"


def test_an_invalid_slice_in_a_call_reaches_no_provider_and_no_record(slice_registry):
    monitor = Monitor()
    executor = executor_for(make_router(slice_registry), monitor)
    with pytest.raises(ValueError):
        executor.call("support", MESSAGES, slice="a@b")
    assert executor.provider.calls == [] and monitor.records == []


def test_a_delegated_call_records_a_null_slice(slice_registry):
    router = make_router(slice_registry)
    decision = router.decide_delegation("support", "fiction/weak", context_tokens=1000,
                                        brief_tokens=100, result_tokens=20)
    assert decision.mode == "delegate" and decision.route.slice is None
    monitor = Monitor()
    executor_for(router, monitor).call_delegated(decision, MESSAGES)
    assert monitor.records and all(list(r) == V1_506_KEYS + ["slice"] for r in monitor.records)
    assert all(r["slice"] is None for r in monitor.records)


# --- 10 the CLI ----------------------------------------------------------------------------

@pytest.fixture
def slice_files(write_json, slice_registry, tmp_path):
    models = [dict(dataclasses.asdict(m), source="https://example.org/prices")
              for m in slice_registry.models]
    paths = {"registry": write_json("models.json", {
        "version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models}),
        "tasks": write_json("tasks.json", {"tasks": [{"name": "support", "bar": 0.85,
                                                      "min_samples": 30}]}),
        "stats": tmp_path / "stats.json", "priors": tmp_path / "no-priors.json"}
    mix_stats().save(paths["stats"])
    return paths


def select_argv(files, *extra):
    return ["select", "support", "--registry", str(files["registry"]), "--tasks",
            str(files["tasks"]), "--stats", str(files["stats"]), "--priors",
            str(files["priors"]), *extra]


def test_select_slice_prints_the_slice_route(slice_files, capsys):
    assert main(select_argv(slice_files, "--slice", "deep")) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[:3] == ["task:      support", "slice:     deep", "flavor:    cost_effective"]
    assert "primary:   fiction/mid" in out
    assert main(select_argv(slice_files, "--slice", "deep", "--json")) == 0
    data = json.loads(capsys.readouterr().out)
    assert (data["slice"], data["primary"]) == ("deep", "fiction/mid")


def test_select_without_slice_prints_no_slice_line(slice_files, capsys):
    assert main(select_argv(slice_files)) == 0
    out = capsys.readouterr().out.splitlines()
    assert out[:2] == ["task:      support", "flavor:    cost_effective"]
    assert "primary:   fiction/cheap" in out


@pytest.mark.parametrize("text", ["", "a@b"])
def test_select_slice_usage_error(slice_files, capsys, text):
    assert main(select_argv(slice_files, "--slice", text)) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines()[0].startswith("usage: model-routing select")
    assert captured.err.splitlines()[-1] == (
        f"error: argument --slice: must be a non-empty name without '@', got {text!r}")


def test_select_slice_on_a_task_whose_key_collides_exits_2(slice_files, write_json, capsys):
    write_json("tasks.json", {"tasks": [{"name": "support", "bar": 0.85},
                                        {"name": "support@deep", "bar": 0.85}]})
    assert main(select_argv(slice_files, "--slice", "deep")) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert len(lines) == 1 and lines[0].startswith("error: ") and "support@deep" in lines[0]


def test_calibrate_writes_the_slice_keys(write_json, tmp_path, capsys):
    results = tmp_path / "results.jsonl"
    results.write_text("".join(json.dumps(r) + "\n" for r in mix_rows()), encoding="utf-8")
    stats_path = tmp_path / "out-stats.json"
    assert main(["calibrate", "--results", str(results), "--stats", str(stats_path)]) == 0
    stats = Stats.load(stats_path)
    assert stats.get("support@deep", "fiction/cheap") == (64, 100)
    assert stats.get("support", "fiction/cheap") == (460, 500)
    assert "support@deep" in capsys.readouterr().out
