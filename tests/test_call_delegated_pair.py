"""DESIGN 7 v1.685 (row DEL1l): `.call_delegated` runs a pair decision through a harness.

`decide_delegation(..., delegate_roots=..., delegate_leaves=...)` returns a `delegate` decision whose route
is a pair (13.3 v1.684). From v1.685 `Executor.call_delegated(decision, messages, ..., harness=run)` runs
that route as `.call_pair` runs its own (7 v1.678 and v1.681), with no second `select_pair`, each record
tagged `delegated` and `parent`, and each refusal before any ID or record. The fixture is DEL1a's
(tests/test_select_pair.py), whose pair delegate route is r/strong+l/cheap, r/strong+l/mid, r/good+l/dear.
"""

import dataclasses
import inspect
import itertools
from pathlib import Path

import pytest

from model_routing import (AllModelsFailed, Budget, BudgetExceeded, BudgetLedger, Completion, Executor,
                           FakeProvider, Model, Monitor, ProviderError)
from decision_hash import decision_sha256
from test_call_pair import FIRST, KEYS, SIDES, TS, harness, side_cost
from test_select_pair import LEAVES, ROOTS, cost, registry, router

ROOT = Path(__file__).resolve().parents[1]
BRIEF = [{"role": "user", "content": "the brief"}]
PAIR = dict(delegate_roots=ROOTS, delegate_leaves=LEAVES)
SIZES = dict(context_tokens=5000, brief_tokens=300, result_tokens=150, carry_turns=2)
ROUTE = (FIRST, "r/strong+l/mid", "r/good+l/dear")
TAGS = {"delegated": "true", "parent": "r/weak"}
# taken on v1.684 (1cadc41) by `bytes_grid` below, before `harness` existed (DESIGN 7 v1.685 Unchanged)
GRID_SHA256 = "2fabd50c1e4403db31496f57bf626eb3f20977a0e041d5b5dc8e4eef494775b6"


def decide(rt=None, parent="r/weak", **kwargs):
    return (rt or router(solo=False)).decide_delegation("t", parent, **{**SIZES, **PAIR, **kwargs})


def executor(rt=None, provider=None, **kwargs):
    ticks, ids = itertools.count(), []
    monitor = Monitor()

    def new_id():
        ids.append(len(ids))
        return f"call-{len(ids) - 1}"

    ex = Executor(rt or router(solo=False), provider or FakeProvider({}), monitor=monitor,
                  clock=lambda: float(next(ticks)), now=lambda: TS, id_factory=new_id, **kwargs)
    return ex, monitor, ids


# --- 7 v1.685: the keyword -----------------------------------------------------------------------

def test_call_delegated_ends_with_a_keyword_only_harness_defaulting_to_none():
    params = inspect.signature(Executor.call_delegated).parameters
    assert list(params) == ["self", "decision", "messages", "tags", "validate", "harness"]
    assert params["harness"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["harness"].default is None


# --- 7 v1.685: the run -------------------------------------------------------------------------

def test_a_pair_decision_runs_its_primary_through_the_harness_tagged_as_call_pair_would_record_it():
    d = decide()
    assert (d.mode, d.route.primary, (d.route.primary, *d.route.fallbacks)) == ("delegate", FIRST, ROUTE)
    ex, monitor, ids = executor()
    calls = []
    result = ex.call_delegated(d, BRIEF, tags={"team": "x"}, harness=harness(calls))
    assert (result.call_id, result.text, result.model) == ("call-0", "answer", FIRST)
    assert result.decision is d.route and len(result.attempts) == 1
    assert calls == [("r/strong", "l/cheap", BRIEF)] and ids == [0]
    [record] = monitor.records
    assert list(record) == KEYS
    assert record["tags"] == {"team": "x", **TAGS} and list(record["tags"]) == ["team", "delegated", "parent"]
    assert {key: record[key] for key in SIDES} == SIDES
    assert record["cost_usd"] == record["routing_cost_usd"] == side_cost("r/strong", "l/cheap")
    assert (record["model"], record["family"], record["outcome"], record["final"]) == (FIRST, "strong", "ok", True)
    # .call_pair on the same route with the same tags writes this record byte for byte
    same, by_pair, _ = executor()
    assert same.call_pair("t", ROOTS, LEAVES, BRIEF, harness([]), tags={"team": "x", **TAGS}).model == FIRST
    assert by_pair.records == monitor.records


def test_the_route_is_used_as_decided_with_no_second_select_pair():
    rt = router(solo=False)
    d = decide(rt)
    rt.stats.add("t", FIRST, 0, 400)  # the primary no longer clears on the router's stats

    def refuse(*args, **kwargs):
        raise AssertionError("select_pair called again")

    rt.select_pair = refuse
    ex, monitor, _ = executor(rt)
    assert ex.call_delegated(d, BRIEF, harness=harness([])).model == FIRST
    assert [r["model"] for r in monitor.records] == [FIRST]


def test_a_provider_error_and_a_failed_check_fall_back_along_the_decided_route():
    ex, monitor, _ = executor()
    calls = []
    run = harness(calls, {FIRST: "outage", "r/strong+l/mid": "bad"})
    result = ex.call_delegated(decide(), BRIEF, validate=lambda text: text != "bad", harness=run)
    assert result.model == "r/good+l/dear" and [a.outcome for a in result.attempts] == ["error", "invalid", "ok"]
    assert [(r, l) for r, l, _ in calls] == [("r/strong", "l/cheap"), ("r/strong", "l/mid"), ("r/good", "l/dear")]
    assert [(r["model"], r["attempt"], r["final"], r["outcome"]) for r in monitor.records] == [
        (FIRST, 0, False, "error"), ("r/strong+l/mid", 1, False, "invalid"), ("r/good+l/dear", 2, True, "ok")]
    assert monitor.records[0]["error"] == "ProviderError: outage" and monitor.records[0]["cost_usd"] == 0.0
    assert monitor.records[1]["cost_usd"] == side_cost("r/strong", "l/mid")
    assert all(r["tags"] == TAGS and list(r)[-4:] == list(SIDES) for r in monitor.records)


def test_every_pair_failing_raises_all_models_failed_on_the_route():
    d = decide()
    ex, monitor, _ = executor()
    run = harness([], {pair: "outage" for pair in ROUTE})
    with pytest.raises(AllModelsFailed, match="all 3 routed pairs failed") as raised:
        ex.call_delegated(d, BRIEF, harness=run)
    assert raised.value.decision is d.route and len(raised.value.attempts) == 3
    assert [r["final"] for r in monitor.records] == [False, False, True]


def test_a_ledger_holds_the_pair_estimate_settles_its_cost_and_tags_its_budget_records():
    ledger = BudgetLedger([Budget("cap", 0.04, "warn")])
    ex, monitor, _ = executor(ledger=ledger)
    held = []

    def run(root, leaf, messages):
        held.append(ledger.held_usd("cap"))
        return {"text": "answer", **SIDES}

    assert ex.call_delegated(decide(), BRIEF, harness=run).model == FIRST
    # 7 v1.681's hold: each side at the task's expected 1000 and 200 tokens on this router's stats
    assert held == [cost("r/strong") + cost("l/cheap")]
    warn, attempt = monitor.records
    assert (warn["budget_event"], warn["tags"], attempt["tags"]) == ("warn", TAGS, TAGS)
    assert ledger.spent_usd("cap") == attempt["cost_usd"] == side_cost("r/strong", "l/cheap")
    assert ledger.held_usd("cap") == 0.0


def test_a_refuse_budget_raises_before_the_harness_with_its_tagged_record():
    ex, monitor, _ = executor(ledger=BudgetLedger([Budget("cap", 0.001, "refuse")]))
    calls = []
    with pytest.raises(BudgetExceeded) as raised:
        ex.call_delegated(decide(), BRIEF, harness=harness(calls))
    assert calls == [] and raised.value.attempts == ()
    [refused] = monitor.records
    assert (refused["budget_event"], refused["model"], refused["tags"]) == ("refused", FIRST, TAGS)


# --- 7 v1.685: each refusal before any ID, hold, harness call or record ---------------------------

def two_ways():
    """A registry where v/a+v/b+v/c splits into v/a and v/b+v/c, and into v/a+v/b and v/c."""
    extra = tuple(Model(model_id, "v", 1.0, 2.0, 100_000) for model_id in ("v/a", "v/b+v/c", "v/a+v/b", "v/c"))
    return router(solo=False, reg=registry(extra=extra))


def refusals():
    d = decide()
    solo = router().decide_delegation("t", "r/strong", **{**SIZES, "context_tokens": 50_000})
    inline = decide(parent="r/weak", context_tokens=2000, rt=router())
    assert (solo.mode, solo.route.primary, inline.mode) == ("delegate", "l/cheap", "inline")
    mixed = dataclasses.replace(d, route=dataclasses.replace(d.route, fallbacks=(ROUTE[1], "r/weak")))
    ambiguous = dataclasses.replace(d, route=dataclasses.replace(d.route, primary="v/a+v/b+v/c"))
    run = harness([])
    return [
        ("inline", None, inline, {"harness": run}, "inline work"),
        ("not callable", None, d, {"harness": "run", "tags": {"parent": "x"}}, "harness must be None or a callable"),
        ("no harness", None, d, {}, "pass it as harness or run it with call_pair"),
        ("no pair", None, solo, {"harness": run}, "harness runs a pair decision"),
        ("a model entry", None, mixed, {"harness": run}, "route entry 'r/weak'"),
        ("two splits", two_ways(), ambiguous, {"harness": run}, "route entry 'v/a\\+v/b\\+v/c'"),
        ("reserved tag", None, d, {"harness": run, "tags": {"parent": "x"}}, "tag names parent"),
    ]


@pytest.mark.parametrize("case", range(7), ids=[case[0] for case in refusals()])
def test_each_refusal_comes_before_any_id_hold_harness_call_or_record(case):
    _, rt, decision, kwargs, message = refusals()[case]
    calls, ledger = [], BudgetLedger([Budget("cap", 10.0, "warn")])
    ex, monitor, ids = executor(rt, ledger=ledger)
    if "harness" in kwargs and callable(kwargs["harness"]):
        kwargs = {**kwargs, "harness": harness(calls)}
    with pytest.raises(ValueError, match=message):
        ex.call_delegated(decision, BRIEF, **kwargs)
    assert (ids, calls, monitor.records, ledger.held_usd("cap"), ledger.spent_usd("cap")) == ([], [], [], 0.0, 0.0)


def test_one_split_reads_as_a_pair_whatever_the_rest_of_the_registry_holds():
    # v/a+v/c has one `+` and so one split, v/a and v/c, on the registry where v/a+v/b+v/c has two
    d = decide()
    one = dataclasses.replace(d, route=dataclasses.replace(d.route, primary="v/a+v/c", fallbacks=()))
    ex, monitor, _ = executor(two_ways())
    calls = []
    assert ex.call_delegated(one, BRIEF, harness=harness(calls)).model == "v/a+v/c"
    assert [(r, l) for r, l, _ in calls] == [("v/a", "v/c")]
    assert monitor.records[0]["family"] == "v"


# --- unchanged: .call_pair and every call_delegated without a harness -----------------------------

def bytes_grid():
    """Records of .call_pair and of a non-pair .call_delegated, both flavors, outages and a ledger."""
    out = []
    for flavor in ("cost_effective", "cost_blind"):
        for script in ({}, {FIRST: "outage", "r/strong+l/mid": "bad", "r/strong+l/dear": "outage"},
                       {pair: "outage" for pair in (*ROUTE, "r/strong+l/dear")}):
            for budgets in (None, [Budget("cap", 0.03, "warn")], [Budget("cap", 0.001, "downgrade")]):
                ledger = None if budgets is None else BudgetLedger(budgets)
                ex, monitor, _ = executor(ledger=ledger)
                try:
                    out.append(ex.call_pair("t", ROOTS, LEAVES, BRIEF, harness([], script), flavor,
                                            tags={"k": "v"}, validate=lambda text: text != "bad").model)
                except Exception as exc:
                    out.append(type(exc).__name__)
                out.append(monitor.records)
    answer = {"l/cheap": lambda m: Completion("ok", 900, 120), "r/weak": lambda m: Completion("ok", 50, 5)}
    for script in (answer, {"r/weak": answer["r/weak"]}, {}):
        for budgets in (None, [Budget("cap", 0.0001, "warn")]):
            rt = router()
            d = rt.decide_delegation("t", "r/strong", **{**SIZES, "context_tokens": 50_000})
            ex, monitor, _ = executor(rt, FakeProvider(dict(script)),
                                      ledger=None if budgets is None else BudgetLedger(budgets))
            try:
                out.append(ex.call_delegated(d, BRIEF, tags={"k": "v"}).model)
            except Exception as exc:
                out.append(type(exc).__name__)
            out.append(monitor.records)
    return out


def test_call_pair_and_a_call_delegated_without_a_harness_keep_their_v1_684_bytes():
    grid = bytes_grid()
    assert len(grid) == 48
    assert decision_sha256(grid, sort_keys=False) == GRID_SHA256


# --- the spec --------------------------------------------------------------------------------------

def test_design_states_the_harness_in_7_and_points_to_it_from_v1_684():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    s7 = design[design.index("## 7. "):design.index("## 8. ")]
    s13_3 = design[design.index("### 13.3 "):design.index("### 13.4 ")]
    assert "- v1.685 a pair decision run by `.call_delegated` (row DEL1l, 7 v1.684, v1.678, v1.681):" in s7
    assert "`.call_delegated(decision, messages, tags=None, validate=None, *, harness=None) -> CallResult`" in s7
    assert "  - Tests (tests/test_call_delegated_pair.py):" in s7
    assert "running it there is row DEL1l" not in s7
    assert "and in `.call_delegated` (row DEL1l, which v1.685 adds)" in s7
    assert "(row DEL1l; 7 v1.684 refuses one)" not in s13_3
    assert "(row DEL1l, which 7 v1.685 adds with `harness`)" in s13_3
