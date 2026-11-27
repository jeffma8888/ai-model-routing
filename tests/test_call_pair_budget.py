"""DESIGN 7 v1.681 (row DEL1g): a pair call under a budget ledger.

`Executor.call_pair` runs on an executor with a `ledger`: before each pair's harness call it holds the
pair's list-price estimate, the root's cost plus the leaf's at the task's expected sizes or at the pair
key's mean side tokens, and after it settles the attempt's side cost, so warn, refuse, downgrade and
strict budgets meet a pair as they meet `.call` (7 v1.595 to v1.598). The fixture is DEL1a's
(tests/test_select_pair.py), whose cost-effective route is r/strong+l/cheap, r/strong+l/mid and
r/good+l/dear, and whose cost-blind route is r/strong+l/dear, r/strong+l/mid and r/good+l/dear.
"""

import itertools
import math
from pathlib import Path

import pytest

from model_routing import (AllModelsFailed, Budget, BudgetExceeded, BudgetLedger, Executor, FakeProvider,
                           Monitor, Policy, ProviderError)
from model_routing.monitor import BUDGET_RECORD_KEYS, RECORD_KEYS
from test_call_pair import FIRST, KEYS, MESSAGES, SIDES, TS, harness, side_cost
from test_select_pair import LEAVES, PAIRS, ROOTS, cost, router

ROOT = Path(__file__).resolve().parents[1]
SECOND = "r/strong+l/mid"
BLIND = "r/strong+l/dear"
# the pair estimate at the task's expected sizes, 1000 input and 200 output tokens on each side
EST = {pair: cost(pair.split("+")[0]) + cost(pair.split("+")[1])
       for pair in (FIRST, SECOND, BLIND, "r/good+l/dear")}


def executor(budgets, route=None, now=lambda: TS):
    ticks, ids = itertools.count(), itertools.count()
    monitor = Monitor()
    ledger = BudgetLedger(budgets)
    ex = Executor(route or router(), FakeProvider({}), monitor=monitor, clock=lambda: float(next(ticks)),
                  now=now, id_factory=lambda: f"call-{next(ids)}", ledger=ledger)
    return ex, monitor, ledger


def in_order(record):
    listed = BUDGET_RECORD_KEYS if "budget_event" in record else RECORD_KEYS
    order = [key for key, _ in listed]
    return all(key in order for key in record) and list(record) == sorted(record, key=order.index)


def test_the_estimates_by_hand():
    assert math.isclose(EST[FIRST], (1000 * 10.0 + 200 * 30.0 + 1000 * 0.1 + 200 * 0.3) / 1e6)
    assert math.isclose(EST[SECOND], 0.0176) and math.isclose(EST[BLIND], 0.032)
    assert math.isclose(EST["r/good+l/dear"], 0.0208)
    assert math.isclose(side_cost("r/strong", "l/cheap"), 0.02174)


# --- 7 v1.681: hold and settle ------------------------------------------------------------------

def test_a_warn_budget_holds_the_estimate_settles_the_side_cost_and_records_the_crossing_first():
    ex, monitor, ledger = executor([Budget("cap", 0.04, "warn")])
    held = []

    def run(root, leaf, messages):
        held.append(ledger.held_usd("cap"))
        return {"text": "answer", **SIDES}

    result = ex.call_pair("t", ROOTS, LEAVES, MESSAGES, run)
    assert result.model == FIRST and held == [EST[FIRST]]
    warn, attempt = monitor.records
    assert warn == {"ts": TS, "call_id": "call-0", "task": "t", "tags": {}, "budget_event": "warn",
                    "budget": "cap", "mode": "warn", "window": None, "share": 0.5,
                    "spent_usd": side_cost("r/strong", "l/cheap"), "limit_usd": 0.04}
    assert list(attempt) == KEYS and attempt["cost_usd"] == side_cost("r/strong", "l/cheap")
    assert ledger.spent_usd("cap") == attempt["cost_usd"] and ledger.held_usd("cap") == 0.0
    assert all(in_order(r) for r in monitor.records)


def test_the_settled_spend_is_the_attempts_cost_after_an_outage_and_a_failed_check():
    ex, monitor, ledger = executor([Budget("cap", 10.0, "warn")])
    result = ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness([], {FIRST: "outage", SECOND: "bad"}),
                          validate=lambda text: text != "bad")
    assert [a.outcome for a in result.attempts] == ["error", "invalid", "ok"]
    attempts = [r for r in monitor.records if "budget_event" not in r]
    assert [r["cost_usd"] for r in attempts] == [a.cost_usd for a in result.attempts]
    assert ledger.spent_usd("cap") == math.fsum(a.cost_usd for a in result.attempts) > 0
    assert ledger.held_usd("cap") == 0.0


def test_the_hold_reads_the_pair_keys_side_tokens_when_it_holds_them():
    extra = {("r/strong", "l/cheap"): {"root_input_tokens": 2000, "root_output_tokens": 500,
                                       "leaf_input_tokens": 30000, "leaf_output_tokens": 3000,
                                       "side_trials": 10}}
    route = router(pair_extra=extra)
    assert route.stats.mean_side_tokens("t", FIRST) == ((200, 50), (3000, 300))
    # under the 0.005 limit, the pair at its side tokens is held where the task's sizes would be refused
    ex, monitor, ledger = executor([Budget("cap", 0.005, "refuse")], route)
    held = []

    def run(root, leaf, messages):
        held.append(ledger.held_usd("cap"))
        return {"text": "answer", **SIDES}

    assert ex.call_pair("t", ROOTS, LEAVES, MESSAGES, run).model == FIRST
    assert held == [cost("r/strong", 200, 50) + cost("l/cheap", 3000, 300)]
    assert math.isclose(held[0], (200 * 10.0 + 50 * 30.0 + 3000 * 0.1 + 300 * 0.3) / 1e6)
    assert EST[FIRST] > 0.005


def test_a_harness_bug_or_a_bad_return_settles_at_zero_and_propagates_with_no_record():
    for bad in (RuntimeError("bug"), {"text": "answer"}):
        ex, monitor, ledger = executor([Budget("cap", 1.0, "warn")])

        def run(root, leaf, messages, bad=bad):
            if isinstance(bad, Exception):
                raise bad
            return bad

        with pytest.raises((RuntimeError, ValueError)):
            ex.call_pair("t", ROOTS, LEAVES, MESSAGES, run)
        assert monitor.records == [] and ledger.spent_usd("cap") == 0.0 and ledger.held_usd("cap") == 0.0


# --- 7 v1.681: refusal and downgrade ------------------------------------------------------------

def test_a_refuse_budget_raises_before_the_harness_with_its_refused_record():
    ex, monitor, ledger = executor([Budget("cap", 0.01, "refuse")])
    calls = []
    with pytest.raises(BudgetExceeded) as info:
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness(calls))
    exc = info.value
    assert calls == [] and exc.attempts == () and exc.decision.primary == FIRST
    assert (exc.model, exc.estimate_usd, exc.spent_usd, exc.held_usd, exc.unbounded) == (
        FIRST, EST[FIRST], 0.0, 0.0, False)
    [refused] = monitor.records
    assert refused == {"ts": TS, "call_id": "call-0", "task": "t", "tags": {}, "budget_event": "refused",
                       "budget": "cap", "mode": "refuse", "window": None, "model": FIRST, "spent_usd": 0.0,
                       "held_usd": 0.0, "estimate_usd": EST[FIRST], "limit_usd": 0.01, "unbounded": False}
    assert ledger.held_usd("cap") == 0.0


def test_a_refusal_after_an_outage_keeps_the_attempt_so_far_none_final():
    ex, monitor, ledger = executor([Budget("cap", 0.017, "refuse")])  # FIRST held, SECOND refused
    calls = []
    with pytest.raises(BudgetExceeded) as info:
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness(calls, {FIRST: "outage"}))
    assert [f"{c[0]}+{c[1]}" for c in calls] == [FIRST]
    assert [a.outcome for a in info.value.attempts] == ["error"] and info.value.model == SECOND
    error, refused = monitor.records
    assert (error["outcome"], error["final"], refused["budget_event"], refused["model"]) == (
        "error", False, "refused", SECOND)


def test_a_downgrade_budget_moves_the_call_to_the_next_pair_with_budget_moves():
    ex, monitor, ledger = executor([Budget("cap", 0.025, "downgrade")])
    calls = []
    result = ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness(calls), flavor="cost_blind")
    assert result.decision.primary == BLIND and result.model == SECOND
    assert [f"{c[0]}+{c[1]}" for c in calls] == [SECOND]
    refused, attempt = monitor.records
    assert (refused["budget_event"], refused["mode"], refused["model"], refused["estimate_usd"]) == (
        "refused", "downgrade", BLIND, EST[BLIND])
    assert attempt["budget_moves"] == [{"entry": BLIND, "model": BLIND, "budget": "cap"}]
    assert list(attempt) == KEYS + ["budget_moves"] and (attempt["attempt"], attempt["final"]) == (0, True)
    assert ledger.spent_usd("cap") == attempt["cost_usd"] == side_cost("r/strong", "l/mid")
    assert ledger.held_usd("cap") == 0.0 and all(in_order(r) for r in monitor.records)


def test_a_downgrade_refusing_every_pair_raises_the_last_refusal():
    ex, monitor, ledger = executor([Budget("cap", 0.001, "downgrade")])
    calls = []
    with pytest.raises(BudgetExceeded) as info:
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness(calls), flavor="cost_blind")
    order = [info.value.decision.primary, *info.value.decision.fallbacks]
    assert calls == [] and info.value.model == order[-1] and info.value.attempts == ()
    assert [r["model"] for r in monitor.records] == order
    assert all(r["budget_event"] == "refused" for r in monitor.records)


def test_a_downgrade_never_lands_on_a_pair_under_the_bar():
    pairs = {**PAIRS, ("r/strong", "l/mid"): 30, ("r/strong", "l/dear"): 30, ("r/good", "l/dear"): 30}
    route = router(pairs=pairs, fallback_below_bar=True)
    decision = route.select_pair("t", ROOTS, LEAVES)
    assert decision.primary == FIRST and decision.fallbacks == decision.below_bar_fallbacks != ()
    ex, monitor, ledger = executor([Budget("cap", 0.01, "downgrade")], route)
    calls = []
    with pytest.raises(BudgetExceeded) as info:
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness(calls))
    assert calls == [] and info.value.model == FIRST and info.value.attempts == ()
    assert info.value.decision.below_bar_fallbacks == decision.below_bar_fallbacks
    assert [r["budget_event"] for r in monitor.records] == ["refused"]


def test_a_budget_exceeded_from_the_harness_propagates_with_no_move_and_no_budget_record():
    ex, monitor, ledger = executor([Budget("cap", 1.0, "downgrade")])
    inner = BudgetExceeded(Budget("inner", 1.0, "downgrade"), 0.0, 0.0, 2.0, "x/inner")
    calls = []

    def run(root, leaf, messages):
        calls.append(f"{root}+{leaf}")
        raise inner

    with pytest.raises(BudgetExceeded) as info:
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, run)
    assert info.value is inner and inner.attempts == () and inner.decision is None
    assert calls == [FIRST] and monitor.records == []
    assert ledger.spent_usd("cap") == 0.0 and ledger.held_usd("cap") == 0.0


# --- 7 v1.681: strict budgets -------------------------------------------------------------------

@pytest.mark.parametrize("mode", ["refuse", "downgrade"])
def test_a_strict_budget_that_applies_refuses_every_pair_as_unbounded(mode):
    ex, monitor, ledger = executor([Budget("cap", 100.0, mode, strict=True)])
    calls = []
    with pytest.raises(BudgetExceeded) as info:
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness(calls))
    assert calls == [] and info.value.unbounded is True
    refused = monitor.records
    assert all(r["unbounded"] is True and r["mode"] == mode for r in refused)
    assert [r["model"] for r in refused] == ([FIRST] if mode == "refuse" else
                                             [info.value.decision.primary, *info.value.decision.fallbacks])


def test_a_strict_budget_that_does_not_apply_holds_nothing_and_a_bug_releases_the_hold():
    budgets = [Budget("strict", 1.0, "refuse", task="other", strict=True), Budget("all", 1.0, "warn")]
    ex, monitor, ledger = executor(budgets)
    result = ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness([]))
    assert result.model == FIRST and ledger.spent_usd("all") == side_cost("r/strong", "l/cheap")
    assert ledger.spent_usd("strict") == 0.0

    def bug(root, leaf, messages):
        raise RuntimeError("bug")

    with pytest.raises(RuntimeError):
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, bug)
    assert ledger.spent_usd("all") == side_cost("r/strong", "l/cheap") and ledger.held_usd("all") == 0.0


# --- 7 v1.681: windows and labels ---------------------------------------------------------------

def test_a_day_budget_reads_its_window_from_now_and_a_label_tops_the_budget_record():
    stamps = iter(["2026-11-26T23:59:59Z"] + ["2026-11-27T08:00:00Z"] * 10)
    ex, monitor, ledger = executor([Budget("daily", 0.04, "warn", window="day")], now=lambda: next(stamps))
    ex.call_pair("t", ROOTS, LEAVES, MESSAGES, harness([]), policy=Policy(name="acme"))
    assert ledger.spent_usd("daily", at="2026-11-26T12:00:00Z") == side_cost("r/strong", "l/cheap")
    assert ledger.spent_usd("daily", at="2026-11-27T12:00:00Z") == 0.0
    warn, attempt = monitor.records
    assert (warn["window"], warn["policy"], attempt["policy"]) == ("2026-11-26", "acme", "acme")
    assert list(warn)[:5] == ["ts", "call_id", "task", "policy", "tags"]
    assert all(in_order(r) for r in monitor.records)


def test_every_pair_failing_under_a_ledger_raises_all_models_failed_with_nothing_held():
    ex, monitor, ledger = executor([Budget("cap", 10.0, "warn")])

    def down(root, leaf, messages):
        raise ProviderError("outage")

    with pytest.raises(AllModelsFailed):
        ex.call_pair("t", ROOTS, LEAVES, MESSAGES, down)
    assert ledger.spent_usd("cap") == 0.0 and ledger.held_usd("cap") == 0.0
    assert [r["outcome"] for r in monitor.records] == ["error"] * 3


# --- the spec -----------------------------------------------------------------------------------

def test_design_and_changelog_state_v1_681():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert design.count("\n- v1.681 a pair call under a budget ledger (row DEL1g, 7 v1.678, v1.595 to v1.598): ") == 1
    assert design.count("(until v1.681, row DEL1g, which holds and settles each pair attempt on the ledger's "
                        "budgets)") == 1
    assert design.count("a budget (row DEL1g, which v1.681 adds in 7), a shadow, signals") == 1
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.681 (2026-11-27): spec, code and tests (7, row DEL1g). ") == 1
