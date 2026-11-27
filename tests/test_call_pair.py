"""DESIGN 7, 8.1 and 8.3 v1.678 (row DEL1e): a pair through the executor and back into calibration.

`Executor.call_pair(task, roots, leaves, messages, harness)` routes with `select_pair`, runs the caller's
harness on the root and the leaf of each pair of the route in turn, falling back on a `ProviderError` or a
failed `validate`, and writes one record per attempt whose `model` is the pair ID, with the four side token
keys of 4.3 v1.672. `audited_results` carries such a record and its grade into a `calibrate_from_results`
row, so the pair's key gains the trial and its side trial. The fixture is DEL1a's (tests/test_select_pair.py).
"""

import itertools
from pathlib import Path

import pytest

from model_routing import (AllModelsFailed, Budget, BudgetLedger, Executor, FakeProvider, Monitor, Policy,
                           ProviderError, audited_results, calibrate_from_results)
from test_select_pair import LEAVES, ROOTS, cost, router

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "review the data room"}]
TS = "2026-11-26T00:00:00Z"
FIRST = "r/strong+l/cheap"
SIDES = {"root_input_tokens": 1200, "root_output_tokens": 300, "leaf_input_tokens": 5000,
         "leaf_output_tokens": 800}
KEYS = ["ts", "call_id", "task", "flavor", "model", "family", "attempt", "final", "outcome", "error",
        "latency_ms", "input_tokens", "output_tokens", "cost_usd", "routing_cost_usd", "below_bar", "basis",
        "tags", "slice", *SIDES]


def executor(route=None, **kwargs):
    ticks, ids = itertools.count(), itertools.count()
    monitor = Monitor()
    ex = Executor(route or router(), FakeProvider({}), monitor=monitor, clock=lambda: float(next(ticks)),
                  now=lambda: TS, id_factory=lambda: f"call-{next(ids)}", **kwargs)
    return ex, monitor


def harness(calls, script=None):
    """Each pair's run: ``outage`` raises ``ProviderError``, a string is the answer, else ``answer``."""
    def run(root, leaf, messages):
        calls.append((root, leaf, messages))
        step = (script or {}).get(f"{root}+{leaf}")
        if step == "outage":
            raise ProviderError("outage")
        return {"text": step or "answer", **SIDES, "note": "not read"}
    return run


def side_cost(root, leaf):
    return cost(root, SIDES["root_input_tokens"], SIDES["root_output_tokens"]) \
        + cost(leaf, SIDES["leaf_input_tokens"], SIDES["leaf_output_tokens"])


# --- 7 v1.678: the call and its record ----------------------------------------------------------

def test_the_pair_call_its_record_and_its_grade_calibrated_round_trip():
    ex, monitor = executor()
    calls = []
    result = ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness(calls))
    assert (result.call_id, result.text, result.model) == ("call-0", "answer", FIRST)
    assert result.decision.primary == FIRST
    assert calls == [("r/strong", "l/cheap", MESSAGES)]
    [record] = monitor.records
    assert list(record) == KEYS
    assert (record["model"], record["family"], record["outcome"], record["final"]) == (FIRST, "strong", "ok", True)
    assert (record["input_tokens"], record["output_tokens"]) == (6200, 1100)
    assert record["cost_usd"] == record["routing_cost_usd"] == side_cost("r/strong", "l/cheap")
    assert {key: record[key] for key in SIDES} == SIDES
    assert (record["latency_ms"], record["basis"], record["slice"], record["tags"]) == (1000.0, "measured", None, {})
    [row] = audited_results(monitor.records, {"call-0": True})
    assert row == {"task": "t", "model": FIRST, "item": "call-0", "correct": True, "input_tokens": 6200,
                   "output_tokens": 1100, **SIDES, "latency_ms": 1000.0}
    stats = calibrate_from_results([row])
    assert stats.get("t", FIRST) == (1, 1)
    assert stats.side_tokens("t", FIRST) == (1200, 300, 5000, 800, 1)
    assert stats.mean_side_tokens("t", FIRST) == ((1200, 300), (5000, 800))


def test_cost_blind_routes_the_best_bound_and_spends_nothing_on_routing():
    ex, monitor = executor()
    result = ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness([]), flavor="cost_blind", tags={"team": "a"})
    [record] = monitor.records
    assert record["model"] == result.model == result.decision.primary
    assert (record["flavor"], record["routing_cost_usd"], record["tags"]) == ("cost_blind", 0.0, {"team": "a"})
    root, leaf = result.model.split("+")
    assert record["cost_usd"] == side_cost(root, leaf)


def test_a_provider_error_falls_back_to_the_next_pair_and_its_record_holds_zero_sides():
    ex, monitor = executor()
    calls = []
    result = ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness(calls, {FIRST: "outage"}))
    second = result.decision.fallbacks[0]
    assert result.model == second and [f"{c[0]}+{c[1]}" for c in calls] == [FIRST, second]
    error, ok = monitor.records
    assert (error["outcome"], error["error"], error["final"], error["attempt"]) == (
        "error", "ProviderError: outage", False, 0)
    assert (error["input_tokens"], error["output_tokens"], error["cost_usd"]) == (0, 0, 0.0)
    assert [error[key] for key in SIDES] == [0, 0, 0, 0]
    assert (ok["outcome"], ok["final"], ok["attempt"], ok["model"]) == ("ok", True, 1, second)
    assert [a.outcome for a in result.attempts] == ["error", "ok"]
    rows = audited_results(monitor.records, {"call-0": False})
    assert [(r["model"], r["correct"]) for r in rows] == [(second, False)]


def test_a_failed_check_is_invalid_and_calibrates_false_with_its_sides():
    ex, monitor = executor()
    result = ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness([], {FIRST: "bad"}),
                          validate=lambda text: text != "bad")
    invalid, ok = monitor.records
    assert (invalid["outcome"], invalid["error"], invalid["model"]) == ("invalid", "validation failed", FIRST)
    assert {key: invalid[key] for key in SIDES} == SIDES
    assert invalid["cost_usd"] == side_cost("r/strong", "l/cheap")
    rows = audited_results(monitor.records, {"call-0": True})
    assert [(r["model"], r["correct"]) for r in rows] == [(FIRST, False), (result.model, True)]
    assert all({key: r[key] for key in SIDES} == SIDES for r in rows)


def test_every_pair_failing_raises_all_models_failed_with_each_attempt():
    ex, monitor = executor()
    calls = []

    def down(root, leaf, messages):
        calls.append(f"{root}+{leaf}")
        raise ProviderError("outage")

    with pytest.raises(AllModelsFailed) as info:
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, down)
    order = [info.value.decision.primary, *info.value.decision.fallbacks]
    assert calls == order and len(info.value.attempts) == len(order) > 1
    assert [r["final"] for r in monitor.records] == [False] * (len(order) - 1) + [True]


def test_a_labelled_policy_names_itself_on_the_record_before_tags():
    ex, monitor = executor()
    policy = Policy(name="acme")
    ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness([]), policy=policy)
    [record] = monitor.records
    keys = list(record)
    assert record["policy"] == policy.label == "acme" and keys.index("policy") == keys.index("tags") - 1


# --- 7 v1.678: the checks -----------------------------------------------------------------------

def test_a_harness_that_is_not_callable_and_a_ledger_raise_before_any_id_or_record():
    ex, monitor = executor()
    with pytest.raises(ValueError, match="harness"):
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, "not callable")
    ex2, monitor2 = executor(ledger=BudgetLedger([Budget("cap", 1.0, "warn")]))
    selected = []
    for each in (ex, ex2):  # review iter-536 nit 1: both raise before select_pair
        each.router.select_pair = lambda *args, _real=each.router.select_pair, **kw: (
            selected.append(args), _real(*args, **kw))[1]
    calls = []
    with pytest.raises(ValueError, match="harness"):
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, "not callable")
    with pytest.raises(ValueError, match="ledger"):
        ex2.call_pair("t", ROOTS, LEAVES, MESSAGES, harness(calls))
    assert monitor.records == monitor2.records == [] and calls == [] and selected == []
    assert ex2.id_factory() == "call-0"
    assert ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness([])).call_id == "call-0" and len(selected) == 1


def plus_router():
    """Model IDs that hold ``+``: the pairs v/a+v/b with v/c and v/a with v/b+v/c share one ID."""
    from model_routing import Model, Registry, Router, Stats, Task
    reg = Registry([Model(m, "f", 1.0, 2.0, 100_000) for m in ("v/a", "v/a+v/b", "v/c", "v/b+v/c")])
    stats = Stats()
    stats.add("t", "v/a+v/b+v/c", 40, 40)
    return Router(reg, {"t": Task("t", bar=0.5, min_samples=30)}, stats)


def test_two_pairs_with_one_id_raise_before_the_id_and_the_harness():
    ex, monitor = executor(plus_router())
    calls = []
    with pytest.raises(ValueError, match="one ID"):
        ex.call_pair("t", ["v/a+v/b", "v/a"], ["v/c", "v/b+v/c"], MESSAGES, harness(calls))
    assert calls == [] and monitor.records == []
    assert ex.id_factory() == "call-0"


def test_a_root_whose_id_holds_a_plus_is_run_as_given_never_split():
    # review iter-536 nit 2: a split at the first "+" would call the harness with v/a and v/b+v/c
    ex, monitor = executor(plus_router())
    calls = []
    result = ex.call_pair("t", ["v/a+v/b"], ["v/c"], MESSAGES, harness(calls))
    assert result.model == "v/a+v/b+v/c" and [c[:2] for c in calls] == [("v/a+v/b", "v/c")]
    [record] = monitor.records
    assert record["family"] == "f" and record["cost_usd"] == (6200 * 1.0 + 1100 * 2.0) / 1_000_000


def test_select_pair_errors_propagate_before_the_harness():
    ex, monitor = executor()
    calls = []
    with pytest.raises(KeyError):
        ex.call_pair("t", ["r/none"], LEAVES, MESSAGES, harness(calls))
    with pytest.raises(ValueError):
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness(calls), flavor="cheap")
    assert calls == [] and monitor.records == []


@pytest.mark.parametrize("bad", [
    None, "answer", {"text": "answer"}, {**SIDES}, {"text": 7, **SIDES},
    {"text": "answer", **SIDES, "root_input_tokens": -1}, {"text": "answer", **SIDES, "leaf_output_tokens": True},
    {"text": "answer", **SIDES, "leaf_input_tokens": 1.0}])
def test_a_return_value_that_is_not_the_mapping_raises_with_no_record(bad):
    ex, monitor = executor()
    with pytest.raises(ValueError, match="harness"):
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, lambda root, leaf, messages: bad)
    assert monitor.records == []


def test_call_writes_no_side_key():
    ex, monitor = executor()
    from test_select_pair import PRICES
    script = {m: (lambda messages: __import__("model_routing").Completion("ok", 1000, 200)) for m in PRICES}
    ex.provider = FakeProvider(script)
    ex.call("t", MESSAGES)
    assert monitor.records and all(not set(SIDES) & set(r) for r in monitor.records)


# --- 8.3 v1.678: a record with only some of the four ----------------------------------------------

def test_a_record_with_some_sides_or_a_bad_count_gives_its_row_without_any():
    ex, monitor = executor()
    ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness([]))
    [record] = monitor.records
    for change in ({"root_input_tokens": None}, {"leaf_output_tokens": True}, {"leaf_input_tokens": -2}):
        changed = dict(record, **change)
        [row] = audited_results([changed], {"call-0": True})
        assert not set(SIDES) & set(row) and row["input_tokens"] == 6200
    partial = {k: v for k, v in record.items() if k != "root_output_tokens"}
    [row] = audited_results([partial], {"call-0": True})
    assert not set(SIDES) & set(row)


# --- the spec -----------------------------------------------------------------------------------

def test_design_and_changelog_state_v1_678():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert design.count("\n- v1.678 a pair through the executor (row DEL1e, 5.2 v1.670): `.call_pair(") == 1
    assert design.count("\n- v1.678 `root_input_tokens`, `root_output_tokens`, `leaf_input_tokens` and "
                        "`leaf_output_tokens` (int), in that order right after `slice`") == 1
    assert design.count("\n- v1.678 a pair's row (row DEL1e, 7 and 8.1 v1.678): `audited_results` ") == 1
    assert design.count("a pair in the executor and the monitor (row DEL1e, which v1.678 adds in 7 and 8)") == 2
    assert "the executor or the monitor" not in design
    assert design.split("\n", 3)[2].startswith("Status: v1.678, 2026-11-26 (v1.678, ")
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.678 (2026-11-26): spec, code and tests (7, 8.1, 8.3, row DEL1e). ") == 1
