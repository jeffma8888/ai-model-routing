"""v1.33 per-model measured token counts in the cost estimate (DESIGN 4.3, 5.2, 13.2 to
13.4), written before the code.

The new behaviour is held under strict xfail markers, each naming what the v1.32 code
raises: ``TypeError`` where a test passes the new ``Stats.add`` keywords,
``AttributeError`` where it reads the new ``Stats.tokens`` or ``Stats.mean_tokens``, and
``AssertionError`` where v1.32 silently ignores the new keys. The implementing commit
removes the markers (DESIGN 13.8). The unmarked tests pin that a Stats with no token
totals prices, routes, delegates and saves exactly as v1.32 does; they pass before and
after.
"""

import json
from pathlib import Path

import pytest

import model_routing
from model_routing import Model, Registry, Router, Stats, Task, calibrate_from_results
from model_routing.router import CONTEXT_TOO_SMALL, PASSES
from model_routing.tasks import load_tasks

NEW_ADD = pytest.mark.xfail(strict=True, raises=TypeError,
                            reason="v1.33 Stats.add token keywords not implemented (P3b)")
NEW_METHOD = pytest.mark.xfail(strict=True, raises=AttributeError,
                               reason="v1.33 Stats.tokens and mean_tokens not implemented (P3b)")
KEYS_IGNORED = pytest.mark.xfail(strict=True, raises=AssertionError,
                                 reason="v1.32 ignores the v1.33 token keys (P3b)")

TASK = "review"
S_IN, S_OUT = 2000, 500
WORK = {"context_tokens": 20_000, "brief_tokens": 300, "result_tokens": 200}
DATA = Path(model_routing.__file__).parent / "data"


def models(windows=None):
    """cheap 1/2, mid 3/6, best 10/20 USD per 1M tokens; 100,000-token windows unless set."""
    w = windows or {}
    return [Model("fiction/cheap", "small", 1.0, 2.0, w.get("fiction/cheap", 100_000)),
            Model("fiction/mid", "medium", 3.0, 6.0, w.get("fiction/mid", 100_000)),
            Model("fiction/best", "large", 10.0, 20.0, w.get("fiction/best", 100_000))]


def build_stats(rows, task=TASK):
    """``rows`` maps a model to (successes, trials) or (successes, trials, in, out[, n])."""
    stats = Stats()
    for model_id, row in rows.items():
        successes, trials, *tokens = row
        if tokens:
            extra = {"token_trials": tokens[2]} if len(tokens) == 3 else {}
            stats.add(task, model_id, successes, trials, input_tokens=tokens[0],
                      output_tokens=tokens[1], **extra)
        else:
            stats.add(task, model_id, successes, trials)
    return stats


def make_router(rows, windows=None, **task_fields):
    fields = {"name": TASK, "bar": 0.8, "min_samples": 30,
              "expected_input_tokens": S_IN, "expected_output_tokens": S_OUT}
    fields.update(task_fields)
    task = Task(**fields)
    return Router(Registry(models(windows)), {task.name: task}, build_stats(rows))


def by_id(decision):
    return {c.model_id: c for c in decision.candidates}


def load_error(path):
    try:
        Stats.load(path)
    except ValueError as exc:
        return str(exc)
    return None


def calibration_error(rows):
    try:
        calibrate_from_results(rows)
    except ValueError as exc:
        return str(exc)
    return None


# ---- 4.3 Stats: token totals ------------------------------------------------------------

@NEW_ADD
def test_add_records_token_totals_over_trials_and_accumulates():
    stats = Stats()
    stats.add(TASK, "fiction/cheap", 9, 10, input_tokens=20_000, output_tokens=5_001)
    assert stats.tokens(TASK, "fiction/cheap") == (20_000, 5_001, 10)
    stats.add(TASK, "fiction/cheap", 3, 5, input_tokens=100, output_tokens=7, token_trials=2)
    assert stats.tokens(TASK, "fiction/cheap") == (20_100, 5_008, 12)
    stats.add(TASK, "fiction/cheap", 4, 4)
    assert stats.get(TASK, "fiction/cheap") == (16, 19)
    assert stats.tokens(TASK, "fiction/cheap") == (20_100, 5_008, 12)
    assert stats.tokens(TASK, "fiction/mid") == (0, 0, 0)
    assert stats.tokens("other", "fiction/cheap") == (0, 0, 0)
    assert stats.items() == [((TASK, "fiction/cheap"), (16, 19))]


@NEW_ADD
def test_mean_tokens_rounds_each_mean_up_in_integer_arithmetic():
    stats = Stats()
    stats.add(TASK, "a", 1, 3, input_tokens=10, output_tokens=9)
    stats.add(TASK, "b", 2, 2, input_tokens=0, output_tokens=1)
    stats.add(TASK, "c", 1, 3, input_tokens=3 * 10**17 + 1, output_tokens=3 * 10**17)
    stats.add(TASK, "d", 5, 5)
    assert stats.mean_tokens(TASK, "a") == (4, 3)
    assert stats.mean_tokens(TASK, "b") == (0, 1)
    # a float division gives 1e17 here, so only integer arithmetic rounds this up
    assert stats.mean_tokens(TASK, "c") == (10**17 + 1, 10**17)
    assert all(type(v) is int for v in stats.mean_tokens(TASK, "c"))
    assert stats.mean_tokens(TASK, "d") is None
    assert stats.mean_tokens(TASK, "unknown") is None


@NEW_ADD
@pytest.mark.parametrize("successes,trials,kwargs", [
    (3, 5, {"input_tokens": 10}),
    (3, 5, {"output_tokens": 10}),
    (3, 5, {"token_trials": 1}),
    (3, 5, {"input_tokens": None, "output_tokens": 10}),
    (3, 5, {"input_tokens": -1, "output_tokens": 0}),
    (3, 5, {"input_tokens": 0, "output_tokens": -1}),
    (3, 5, {"input_tokens": True, "output_tokens": 0}),
    (3, 5, {"input_tokens": 0, "output_tokens": False}),
    (3, 5, {"input_tokens": 1.0, "output_tokens": 0}),
    (3, 5, {"input_tokens": "1", "output_tokens": 0}),
    (3, 5, {"input_tokens": 1, "output_tokens": 1, "token_trials": 0}),
    (3, 5, {"input_tokens": 1, "output_tokens": 1, "token_trials": 6}),
    (3, 5, {"input_tokens": 1, "output_tokens": 1, "token_trials": True}),
    (3, 5, {"input_tokens": 1, "output_tokens": 1, "token_trials": 2.0}),
    (0, 0, {"input_tokens": 0, "output_tokens": 0}),
    (6, 5, {"input_tokens": 1, "output_tokens": 1}),
])
def test_add_rejects_invalid_token_arguments_and_adds_nothing(successes, trials, kwargs):
    stats = Stats()
    stats.add(TASK, "m", 1, 2, input_tokens=10, output_tokens=4)
    with pytest.raises(ValueError):
        stats.add(TASK, "m", successes, trials, **kwargs)
    assert stats.get(TASK, "m") == (1, 2)
    assert stats.tokens(TASK, "m") == (10, 4, 2)


@NEW_ADD
def test_merge_sums_token_totals_without_mutating_either_operand():
    a = Stats()
    a.add(TASK, "m", 1, 2, input_tokens=10, output_tokens=4)
    b = Stats()
    b.add(TASK, "m", 3, 3, input_tokens=5, output_tokens=6, token_trials=1)
    b.add(TASK, "n", 1, 1)
    merged = a.merge(b)
    assert merged.get(TASK, "m") == (4, 5)
    assert merged.tokens(TASK, "m") == (15, 10, 3)
    assert merged.tokens(TASK, "n") == (0, 0, 0)
    assert a.tokens(TASK, "m") == (10, 4, 2)
    assert b.tokens(TASK, "m") == (5, 6, 1)


@NEW_ADD
def test_save_writes_token_keys_only_for_keys_with_tokens_and_round_trips(tmp_path):
    stats = Stats()
    stats.add(TASK, "b", 1, 2, input_tokens=10, output_tokens=4, token_trials=1)
    stats.add(TASK, "a", 3, 4)
    path = tmp_path / "stats.json"
    stats.save(path)
    rows = json.loads(path.read_text(encoding="utf-8"))["stats"]
    assert rows == [
        {"task": TASK, "model": "a", "successes": 3, "trials": 4},
        {"task": TASK, "model": "b", "successes": 1, "trials": 2,
         "input_tokens": 10, "output_tokens": 4, "token_trials": 1},
    ]
    assert list(rows[1]) == ["task", "model", "successes", "trials",
                             "input_tokens", "output_tokens", "token_trials"]
    loaded = Stats.load(path)
    assert loaded.items() == stats.items()
    assert loaded.tokens(TASK, "b") == (10, 4, 1)
    assert loaded.tokens(TASK, "a") == (0, 0, 0)
    again = tmp_path / "again.json"
    loaded.save(again)
    assert again.read_bytes() == path.read_bytes()


@NEW_METHOD
def test_load_reads_the_optional_token_keys_and_accumulates_rows(write_json):
    path = write_json("stats.json", {"stats": [
        {"task": TASK, "model": "a", "successes": 3, "trials": 4,
         "input_tokens": 40, "output_tokens": 9, "token_trials": 3},
        {"task": TASK, "model": "b", "successes": 1, "trials": 1},
        {"task": TASK, "model": "a", "successes": 1, "trials": 1,
         "input_tokens": 2, "output_tokens": 3, "token_trials": 1},
    ]})
    stats = Stats.load(path)
    assert stats.get(TASK, "a") == (4, 5)
    assert stats.tokens(TASK, "a") == (42, 12, 4)
    assert stats.mean_tokens(TASK, "a") == (11, 3)
    assert stats.tokens(TASK, "b") == (0, 0, 0)


@KEYS_IGNORED
@pytest.mark.parametrize("tokens", [
    {"input_tokens": 1, "output_tokens": 1},
    {"input_tokens": 1, "token_trials": 1},
    {"output_tokens": 1, "token_trials": 1},
    {"token_trials": 1},
    {"input_tokens": True, "output_tokens": 1, "token_trials": 1},
    {"input_tokens": 1.0, "output_tokens": 1, "token_trials": 1},
    {"input_tokens": "1", "output_tokens": 1, "token_trials": 1},
    {"input_tokens": None, "output_tokens": 1, "token_trials": 1},
    {"input_tokens": -1, "output_tokens": 1, "token_trials": 1},
    {"input_tokens": 1, "output_tokens": -1, "token_trials": 1},
    {"input_tokens": 1, "output_tokens": 1, "token_trials": 0},
    {"input_tokens": 1, "output_tokens": 1, "token_trials": 5},
    {"input_tokens": 1, "output_tokens": 1, "token_trials": False},
    {"input_tokens": 1, "output_tokens": 1, "token_trials": None},
])
def test_load_rejects_a_partial_or_invalid_token_set_naming_the_file(write_json, tokens):
    path = write_json("stats.json", {"stats": [
        {"task": TASK, "model": "a", "successes": 3, "trials": 4, **tokens}]})
    error = load_error(path)
    assert error is not None and str(path) in error


@NEW_METHOD
def test_calibration_counts_one_token_trial_per_row_with_token_counts():
    stats = calibrate_from_results([
        {"task": TASK, "model": "a", "correct": True, "input_tokens": 100, "output_tokens": 7},
        {"task": TASK, "model": "a", "correct": False, "input_tokens": 101, "output_tokens": 8},
        {"task": TASK, "model": "a", "prediction": 1, "gold": 1},
        {"task": TASK, "model": "b", "correct": True},
    ])
    assert stats.get(TASK, "a") == (2, 3)
    assert stats.tokens(TASK, "a") == (201, 15, 2)
    assert stats.mean_tokens(TASK, "a") == (101, 8)
    assert stats.tokens(TASK, "b") == (0, 0, 0)


@KEYS_IGNORED
@pytest.mark.parametrize("tokens", [
    {"input_tokens": 1},
    {"output_tokens": 1},
    {"input_tokens": True, "output_tokens": 1},
    {"input_tokens": 1, "output_tokens": -1},
    {"input_tokens": 1.5, "output_tokens": 1},
    {"input_tokens": None, "output_tokens": 1},
    {"input_tokens": 1, "output_tokens": None},
    {"input_tokens": "1", "output_tokens": 1},
])
def test_calibration_rejects_a_partial_or_invalid_token_pair(tokens):
    rows = [{"task": TASK, "model": "a", "correct": True},
            {"task": TASK, "model": "a", "correct": True, **tokens}]
    assert calibration_error(rows) is not None


# ---- 5.2 select: each measured model at its own mean tokens --------------------------------

# cheap: means (2101, 801) from 210,001 and 80,050 over 100 calls; mid: no tokens;
# best: means (1900, 300)
PRICED = {"fiction/cheap": (95, 100, 210_001, 80_050), "fiction/mid": (96, 100),
          "fiction/best": (99, 100, 190_000, 30_000)}


@NEW_ADD
@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_a_model_with_token_totals_is_priced_at_its_own_rounded_up_means(flavor):
    router = make_router(PRICED)
    cands = by_id(router.select(TASK, flavor=flavor))
    reg = router.registry
    expected = {"fiction/cheap": reg.get("fiction/cheap").cost(2101, 801),
                "fiction/mid": reg.get("fiction/mid").cost(S_IN, S_OUT),
                "fiction/best": reg.get("fiction/best").cost(1900, 300)}
    for model_id, cost in expected.items():
        assert cands[model_id].list_cost == cost
        assert cands[model_id].routing_cost == (cost if flavor == "cost_effective" else 0.0)
        assert cands[model_id].reason == PASSES


# cheap is cheapest per token but writes 5,000 tokens a call on this task
LONG_WRITER = {"fiction/cheap": (95, 100, 200_000, 500_000), "fiction/mid": (96, 100),
               "fiction/best": (99, 100)}


def test_without_tokens_the_cheapest_per_token_model_is_the_cost_effective_primary():
    plain = {m: row[:2] for m, row in LONG_WRITER.items()}
    decision = make_router(plain).select(TASK)
    assert (decision.primary, decision.fallbacks) == ("fiction/cheap", ("fiction/mid", "fiction/best"))


@NEW_ADD
def test_a_model_that_writes_long_loses_the_cost_effective_primary():
    router = make_router(LONG_WRITER)
    decision = router.select(TASK)
    # cheap 0.012 at (2000, 5000) against mid 0.009 and best 0.03 at (2000, 500)
    assert (decision.primary, decision.fallbacks) == ("fiction/mid", ("fiction/cheap", "fiction/best"))
    assert router.select(TASK, flavor="cost_blind").primary == "fiction/best"


@NEW_ADD
def test_rule_5_checks_the_task_sizes_not_the_measured_means():
    # cheap fits 2000 + 500 but not its means 2000 + 1000; mid does not fit 2000 + 500
    # but would fit its means 1000 + 100
    rows = {"fiction/cheap": (95, 100, 200_000, 100_000), "fiction/mid": (96, 100, 100_000, 10_000),
            "fiction/best": (99, 100)}
    router = make_router(rows, windows={"fiction/cheap": 2_600, "fiction/mid": 2_499})
    cands = by_id(router.select(TASK))
    assert cands["fiction/cheap"].reason == PASSES
    assert cands["fiction/mid"].reason == CONTEXT_TOO_SMALL
    assert cands["fiction/mid"].list_cost == router.registry.get("fiction/mid").cost(1000, 100)


def test_without_tokens_best_available_breaks_a_quality_tie_on_cost():
    rows = {"fiction/cheap": (70, 100), "fiction/mid": (70, 100), "fiction/best": (10, 100)}
    router = make_router(rows, on_no_model="best_available")
    assert router.select(TASK).primary == "fiction/cheap"


@NEW_ADD
@pytest.mark.parametrize("flavor,primary", [("cost_effective", "fiction/mid"),
                                            ("cost_blind", "fiction/cheap")])
def test_best_available_breaks_a_quality_tie_on_the_measured_cost(flavor, primary):
    rows = {"fiction/cheap": (70, 100, 200_000, 500_000), "fiction/mid": (70, 100),
            "fiction/best": (10, 100)}
    decision = make_router(rows, on_no_model="best_available").select(TASK, flavor=flavor)
    assert decision.below_bar is True
    assert decision.primary == primary


@NEW_ADD
def test_token_totals_of_another_task_do_not_change_this_tasks_price():
    router = make_router({"fiction/cheap": (95, 100), "fiction/mid": (96, 100),
                          "fiction/best": (99, 100)})
    router.stats.add("other", "fiction/cheap", 95, 100, input_tokens=1, output_tokens=1)
    cands = by_id(router.select(TASK))
    assert cands["fiction/cheap"].list_cost == router.registry.get("fiction/cheap").cost(S_IN, S_OUT)


def test_without_token_totals_every_candidate_is_priced_at_the_task_sizes():
    registry = Registry.load(DATA / "models.json")
    tasks = load_tasks(DATA / "example_tasks.json")
    stats = Stats()
    for name in tasks:
        for model in registry.models:
            stats.add(name, model.id, 1000, 1000)
    router = Router(registry, tasks, stats)
    checked = 0
    for name, task in tasks.items():
        for flavor in ("cost_effective", "cost_blind"):
            for c in router.select(name, flavor=flavor).candidates:
                cost = registry.get(c.model_id).cost(task.expected_input_tokens,
                                                     task.expected_output_tokens)
                assert c.list_cost == cost
                assert c.routing_cost == (cost if flavor == "cost_effective" else 0.0)
                checked += 1
    assert checked == 2 * len(tasks) * len(registry.models) > 0


# ---- 13.2 to 13.4 decide_delegation: each path at its model's sizes -----------------------

@NEW_ADD
@pytest.mark.parametrize("separate,turns", [(True, 0), (True, 2), (False, 0), (False, 3)])
def test_each_path_is_charged_at_the_sizes_of_the_model_doing_it(separate, turns):
    router = make_router(PRICED)
    before = router.stats.tokens(TASK, "fiction/cheap")
    d = router.decide_delegation(TASK, "fiction/best", carry_turns=turns,
                                 inline_separate_call=separate, **WORK)
    reg = router.registry
    p, c, b, r = reg.get("fiction/best"), WORK["context_tokens"], WORK["brief_tokens"], WORK["result_tokens"]
    p_in, p_out = 1900, 300
    if separate:
        inline = p.cost(c + p_in, p_out) + (1 + turns) * p.cost(p_in + p_out, 0)
    else:
        inline = p.cost(p_in, p_out) + turns * p.cost(p_in + p_out, 0)
    assert d.inline_cost_usd == inline
    # the delegate select prices each model at its input size plus the brief
    route = by_id(d.route)
    assert route["fiction/cheap"].list_cost == reg.get("fiction/cheap").cost(2101 + b, 801)
    assert route["fiction/mid"].list_cost == reg.get("fiction/mid").cost(S_IN + b, S_OUT)
    assert route["fiction/best"].list_cost == p.cost(1900 + b, 300)
    assert d.route.primary == "fiction/cheap"
    delegate = (p.cost(0, b) + reg.get("fiction/cheap").cost(b + 2101, 801)
                + (1 + turns) * p.cost(b + r, 0))
    assert d.delegate_cost_usd == delegate
    assert router.stats.tokens(TASK, "fiction/cheap") == before
    assert router.tasks[TASK].expected_input_tokens == S_IN


@NEW_ADD
@pytest.mark.parametrize("window,allowed", [(22_500, True), (22_499, False)])
def test_the_inline_context_check_uses_the_task_sizes_not_the_parents_means(window, allowed):
    # the parent's means (2000, 1000) do not fit 22,500 and (1000, 100) fit 22,499
    out_total = 100_000 if allowed else 10_000
    in_total = 200_000 if allowed else 100_000
    rows = {"fiction/cheap": (95, 100), "fiction/mid": (96, 100),
            "fiction/best": (99, 100, in_total, out_total)}
    router = make_router(rows, windows={"fiction/best": window})
    d = router.decide_delegation(TASK, "fiction/best", **WORK)
    assert d.inline_allowed is allowed
    assert (d.reason == "parent_context_full") is (not allowed)


# mid as the parent, delegating to its own model; folded inline work, 3 later turns
FLIP = {"context_tokens": 20_000, "brief_tokens": 300, "result_tokens": 200,
        "carry_turns": 3, "inline_separate_call": False,
        "exclude_models": ("fiction/cheap", "fiction/best")}
FLIP_TASK = {"expected_input_tokens": 500, "expected_output_tokens": 100}


def test_without_tokens_a_short_writing_parent_stays_inline_when_folded():
    router = make_router({"fiction/cheap": (95, 100), "fiction/mid": (96, 100),
                          "fiction/best": (99, 100)}, **FLIP_TASK)
    d = router.decide_delegation(TASK, "fiction/mid", **FLIP)
    assert (d.mode, d.model, d.reason) == ("inline", "fiction/mid", "inline_cheaper")


@NEW_ADD
def test_a_parent_that_writes_long_delegates_to_its_own_model_when_folded():
    # mid writes 2,000 tokens a call: 3 later turns re-reading 2,500 tokens cost more
    # than writing and re-reading a 300-token brief and a 200-token result
    router = make_router({"fiction/cheap": (95, 100), "fiction/mid": (96, 100, 50_000, 200_000),
                          "fiction/best": (99, 100)}, **FLIP_TASK)
    d = router.decide_delegation(TASK, "fiction/mid", **FLIP)
    p = router.registry.get("fiction/mid")
    assert d.inline_cost_usd == p.cost(500, 2000) + 3 * p.cost(500 + 2000, 0)
    assert d.delegate_cost_usd == p.cost(0, 300) + p.cost(300 + 500, 2000) + 4 * p.cost(300 + 200, 0)
    assert (d.mode, d.model, d.reason) == ("delegate", "fiction/mid", "delegate_cheaper")


@pytest.mark.parametrize("parent", ["fiction/cheap", "fiction/mid", "fiction/best"])
@pytest.mark.parametrize("separate,turns", [(True, 0), (True, 2), (False, 0), (False, 3)])
def test_without_token_totals_delegation_costs_are_the_v1_32_expressions(parent, separate, turns):
    router = make_router({"fiction/cheap": (95, 100), "fiction/mid": (96, 100),
                          "fiction/best": (99, 100)})
    d = router.decide_delegation(TASK, parent, carry_turns=turns,
                                 inline_separate_call=separate, **WORK)
    reg = router.registry
    p, c, b, r = reg.get(parent), WORK["context_tokens"], WORK["brief_tokens"], WORK["result_tokens"]
    if separate:
        inline = p.cost(c + S_IN, S_OUT) + (1 + turns) * p.cost(S_IN + S_OUT, 0)
    else:
        inline = p.cost(S_IN, S_OUT) + turns * p.cost(S_IN + S_OUT, 0)
    assert d.inline_cost_usd == inline
    for cand in d.route.candidates:
        assert cand.list_cost == reg.get(cand.model_id).cost(S_IN + b, S_OUT)
    delegate = reg.get(d.route.primary)
    assert d.delegate_cost_usd == (p.cost(0, b) + delegate.cost(b + S_IN, S_OUT)
                                   + (1 + turns) * p.cost(b + r, 0))


# ---- 4.3 files without tokens stay v1.32 files -----------------------------------------

def test_a_stats_file_without_token_keys_loads_and_saves_byte_identical(tmp_path):
    rows = [{"task": TASK, "model": "a", "successes": 3, "trials": 4},
            {"task": TASK, "model": "b", "successes": 0, "trials": 2}]
    path = tmp_path / "old.json"
    path.write_text(json.dumps({"stats": rows}, indent=2) + "\n", encoding="utf-8")
    again = tmp_path / "again.json"
    Stats.load(path).save(again)
    assert again.read_bytes() == path.read_bytes()


def test_calibration_rows_without_token_keys_save_only_the_four_count_keys(tmp_path):
    stats = calibrate_from_results([{"task": TASK, "model": "a", "correct": True},
                                    {"task": TASK, "model": "a", "prediction": 1, "gold": 2}])
    path = tmp_path / "stats.json"
    stats.save(path)
    assert json.loads(path.read_text(encoding="utf-8")) == {
        "stats": [{"task": TASK, "model": "a", "successes": 1, "trials": 2}]}
