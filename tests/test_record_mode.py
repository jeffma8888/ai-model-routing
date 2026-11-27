"""DESIGN 7, 8.1 and 8.3 v1.687 (row DEL2): a mode record of what the agent did beside what
`decide_delegation` advised, and every log reader passing it by.

`Executor.record_mode(decision, actual_mode, input_tokens, tags=None)` writes one mode record, a
record with an `advised_mode` key (8.1 v1.687), and returns a copy of it, with no router, provider
or ledger call. `report`, `opportunities`, `budget_report`, `shadow_pairs`, `pair_results` with
`records` and `audited_results` drop mode records before reading any (8.3 v1.687), so each gives
on a log with mode records what it gives on the same log without them. The scenario logs and the
8.1 table reader are tests/test_record_keys.py's.
"""

import dataclasses
import re
from pathlib import Path

import pytest

import model_routing
from model_routing import (Budget, BudgetLedger, DelegationDecision, Executor, Monitor, audited_results,
                           budget_report, load_records, opportunities, pair_results, report, shadow_pairs)
from model_routing import monitor as monitor_module
from test_record_keys import COUNTS, JSON_TYPES, MODELS, Run, model, ok, router, scenarios, table

ROOT = Path(__file__).resolve().parents[1]
# a day no record of the scenarios has: theirs are all 2026-11-25 (tests/test_record_keys.py TS)
DAY2 = "2026-11-26T09:00:00Z"
KEYS = ["ts", "call_id", "task", "flavor", "parent", "advised_mode", "actual_mode", "reason", "work_input_tokens",
        "tags"]


def delegated():
    """tests/test_record_keys.py's delegated scenario: the parent under the bar, so the work is handed off."""
    other = MODELS + [model("y/cheap", 0.1, family="y")]
    route = router(models=other, counts=dict(COUNTS, **{"y/cheap": 60}))
    decision = route.decide_delegation("t", "y/cheap", context_tokens=2000, brief_tokens=1000, result_tokens=1000,
                                       inline_separate_call=False)
    assert (decision.mode, decision.reason) == ("delegate", "parent_below_bar") and decision.route is not None
    return route, decision


class Counted:
    """An executor whose ``now`` and ``id_factory`` count their calls, and whose provider is None."""

    def __init__(self, route, monitor=None, ledger=None):
        self.now_calls, self.id_calls = 0, 0
        self.ex = Executor(route, None, monitor=monitor, now=self.now, id_factory=self.new_id, ledger=ledger)

    def now(self):
        self.now_calls += 1
        return DAY2

    def new_id(self):
        self.id_calls += 1
        return f"mode-{self.id_calls}"


# --- 7 v1.687: the record ------------------------------------------------------------------------

def test_record_mode_logs_the_advised_and_the_taken_mode_and_returns_a_copy(tmp_path):
    route, decision = delegated()
    path = tmp_path / "log.jsonl"
    run = Counted(route, Monitor(path))
    tags = {"team": "a"}
    rec = run.ex.record_mode(decision, "inline", 4000, tags=tags)
    expected = {"ts": DAY2, "call_id": "mode-1", "task": "t", "flavor": "cost_effective", "parent": "y/cheap",
                "advised_mode": "delegate", "actual_mode": "inline", "reason": "parent_below_bar",
                "work_input_tokens": 4000, "tags": {"team": "a"}}
    assert rec == expected and list(rec) == KEYS
    assert (run.now_calls, run.id_calls) == (1, 1)
    assert load_records(path) == [expected] and run.ex.monitor.records == [expected]
    rec["tags"]["team"] = "b"
    rec["actual_mode"] = "delegate"
    tags["team"] = "c"
    assert run.ex.monitor.records == [expected]


def test_record_mode_with_no_monitor_returns_the_record_alone():
    route, decision = delegated()
    run = Counted(route)
    assert run.ex.record_mode(decision, "delegate", 0) == {
        "ts": DAY2, "call_id": "mode-1", "task": "t", "flavor": "cost_effective", "parent": "y/cheap",
        "advised_mode": "delegate", "actual_mode": "delegate", "reason": "parent_below_bar", "work_input_tokens": 0,
        "tags": {}}


def test_a_hand_built_inline_decision_is_logged_field_for_field():
    route, _ = delegated()
    decision = DelegationDecision(task="t", flavor="cost_blind", parent="x/big", mode="inline", model="x/big",
                                  reason="inline_as_good", below_bar=False, inline_allowed=True,
                                  inline_cost_usd=0.01, delegate_cost_usd=0.02, parent_quality_lb=0.9,
                                  delegate_quality_lb=0.85, route=None)
    rec = Counted(route).ex.record_mode(decision, "delegate", 120_000, {"run": "r1"})
    assert [rec[key] for key in KEYS] == [DAY2, "mode-1", "t", "cost_blind", "x/big", "inline", "delegate",
                                          "inline_as_good", 120_000, {"run": "r1"}]


def test_record_mode_makes_no_provider_call_and_no_hold_under_a_ledger(tmp_path):
    # a refuse budget no call fits: a hold would raise, and the provider is None, so a call would too
    route, decision = delegated()
    path = tmp_path / "log.jsonl"
    run = Counted(route, Monitor(path), BudgetLedger([Budget("cap", 0.0000001, "refuse")]))
    run.ex.record_mode(decision, "inline", 4000)
    assert [list(r) for r in load_records(path)] == [KEYS]


BAD = [
    ("decision", "a RouteDecision", lambda d: d.route, "inline", 1, None, "decision must be a DelegationDecision"),
    ("decision", "a dict", lambda d: d.to_dict(), "inline", 1, None, "decision must be a DelegationDecision"),
    ("decision.mode", "another mode", lambda d: dataclasses.replace(d, mode="shadow"), "inline", 1, None,
     "decision mode"),
    ("actual_mode", "another word", None, "skipped", 1, None, "actual_mode"),
    ("actual_mode", "None", None, None, 1, None, "actual_mode"),
    ("input_tokens", "negative", None, "inline", -1, None, "input_tokens"),
    ("input_tokens", "a bool", None, "inline", True, None, "input_tokens"),
    ("input_tokens", "a float", None, "inline", 1.0, None, "input_tokens"),
    ("tags", "a list", None, "inline", 1, ["a"], "tags"),
    ("tags", "an int value", None, "inline", 1, {"a": 1}, "tags"),
    ("tags", "an int key", None, "inline", 1, {1: "a"}, "tags"),
]


@pytest.mark.parametrize("name,what,change,actual,tokens,tags,message", BAD, ids=[f"{b[0]} {b[1]}" for b in BAD])
def test_each_bad_argument_raises_before_any_id_or_record(tmp_path, name, what, change, actual, tokens, tags,
                                                          message):
    route, decision = delegated()
    if change is not None:
        decision = change(decision)
    path = tmp_path / "log.jsonl"
    run = Counted(route, Monitor(path))
    with pytest.raises(ValueError, match=re.escape(message)):
        run.ex.record_mode(decision, actual, tokens, tags)
    assert (run.now_calls, run.id_calls, run.ex.monitor.records, path.exists()) == (0, 0, [], False)


def test_the_checks_run_in_their_order():
    route, decision = delegated()
    ex = Counted(route).ex
    with pytest.raises(ValueError, match="decision must be a DelegationDecision"):
        ex.record_mode(decision.to_dict(), "skipped", -1, ["a"])
    with pytest.raises(ValueError, match="decision mode"):
        ex.record_mode(dataclasses.replace(decision, mode="shadow"), "skipped", -1, ["a"])
    with pytest.raises(ValueError, match="actual_mode"):
        ex.record_mode(decision, "skipped", -1, ["a"])
    with pytest.raises(ValueError, match="input_tokens"):
        ex.record_mode(decision, "inline", -1, ["a"])


# --- 8.1 v1.687: the table -----------------------------------------------------------------------

def test_the_mode_table_equals_the_code_list_and_every_key_is_on_every_mode_record():
    listed = getattr(monitor_module, "MODE_RECORD_KEYS", None)
    assert isinstance(listed, tuple)
    rows = table("Mode records:")
    assert [(key, types) for key, types, _, _ in rows] == list(listed)
    assert [key for key, _ in listed] == KEYS
    assert all(since == "v1.687" and re.fullmatch(r"every mode record(: .*)?", carried)
               for _, _, since, carried in rows)
    assert all(set(types) <= set(JSON_TYPES) for _, types in listed)
    assert "MODE_RECORD_KEYS" not in model_routing.__all__
    route, decision = delegated()
    rec = Counted(route).ex.record_mode(decision, "inline", 7, {"k": "v"})
    assert list(rec) == [key for key, _ in listed]
    assert all(any(JSON_TYPES[name](rec[key]) for name in types) for key, types in listed)


def test_8_1_names_the_mode_record_and_its_place():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    eight1 = design[design.index("### 8.1 "):design.index("### 8.2 ")]
    bullet = next(line for line in eight1.splitlines() if line.startswith("- v1.687 "))
    assert "a record with an `advised_mode` key is a mode record" in bullet
    assert "`MODE_RECORD_KEYS`" in bullet
    assert eight1.index("\nBudget records:\n") < eight1.index("\nMode records:\n")


# --- 8.3 v1.687: every reader passes mode records by -----------------------------------------------

def mode(call_id, ts, **extra):
    rec = {"ts": ts, "call_id": call_id, "task": "t", "flavor": "cost_effective", "parent": "x/big",
           "advised_mode": "delegate", "actual_mode": "inline", "reason": "delegate_cheaper", "work_input_tokens": 5000,
           "tags": {"team": "a"}}
    rec.update(extra)
    return rec


MODES = [mode("mode-1", DAY2), mode("mode-2", "2026-11-25T00:00:00Z", actual_mode="delegate", tags={}),
         mode("mode-3", DAY2, task="other", parent="y/cheap")]


def mixed(records):
    """``records`` with a mode record before, among and after them."""
    return [MODES[0]] + records[:1] + [MODES[1]] + records[1:] + [MODES[2]]


def result(fn, records):
    try:
        return ("ok", fn(records))
    except ValueError as exc:
        return ("ValueError", str(exc))


def readers(clean):
    audits = {rec["call_id"]: True for rec in clean if isinstance(rec.get("call_id"), str)}
    audits.update({"mode-1": True, "mode-2": False})
    budgets = [Budget("day", 1.0, "warn", window="day"), Budget("month", 1.0, "warn", window="month"),
               Budget("all", 1.0, "warn")]
    out = {f"report by {by}": (lambda r, by=by: report(r, by=by))
           for by in ("model", "task", "flavor", "family", "basis", "policy", "tag:team")}
    out.update({
        "report audits": lambda r: report(r, audits=audits),
        "report cache": lambda r: report(r, cache=True),
        "report shadow": lambda r: report(r, shadow=True),
        "opportunities": lambda r: opportunities(r),
        "opportunities audits": lambda r: opportunities(r, audits=audits, target_cost_per_call=0.0001),
        "budget_report": lambda r: budget_report(r, budgets),
        "shadow_pairs": lambda r: shadow_pairs(r),
        "shadow_pairs audits": lambda r: shadow_pairs(r, audits=audits),
        "pair_results records": lambda r: pair_results(shadow_pairs(clean, audits=audits), records=r),
        "audited_results": lambda r: audited_results(r, audits),
        "audited_results window": lambda r: audited_results(r, audits, since="2026-11-25T00:00:00Z",
                                                            until="2026-11-27T00:00:00Z"),
    })
    return out


@pytest.fixture(scope="module")
def logs(tmp_path_factory):
    return scenarios(tmp_path_factory.mktemp("record-mode"))


READERS = list(readers([]))


@pytest.mark.parametrize("reader", READERS)
def test_each_reader_gives_on_a_log_with_mode_records_what_it_gives_without_them(logs, reader):
    differ, filled = [], []
    for name, clean in logs.items():
        fn = readers(clean)[reader]
        found = result(fn, clean)
        if result(fn, mixed(clean)) != found:
            differ.append(name)
        if found[0] == "ok" and found[1]:
            filled.append(name)
    assert differ == []
    assert filled  # review iter-546 nit 4: not two equal errors on every scenario


def test_shadow_pairs_and_pair_results_pass_by_a_record_with_an_advised_mode_key_whatever_it_holds(logs):
    # review iter-546 should-fix 2: a mode record holds no pair key, so these two readers would pass it by
    # without their filter; a copy of every record of a shadowed log, marked as a mode record, pins it
    filled = []
    for name in ("shadowed", "shadow's refused budget"):
        clean = logs[name]
        audits = {rec["call_id"]: True for rec in clean}
        marked = clean + [dict(rec, advised_mode="delegate") for rec in clean]
        for labels in ({}, {"audits": audits}):
            assert shadow_pairs(marked, **labels) == shadow_pairs(clean, **labels)
        pairs = shadow_pairs(clean, audits=audits)
        rows = pair_results(pairs, records=clean)
        assert pair_results(pairs, records=marked) == rows
        filled.append(bool(pairs) and bool(rows))
    assert filled[0]


def test_a_log_of_mode_records_alone_gives_no_row():
    assert report(MODES) == [] and opportunities(MODES) == [] and shadow_pairs(MODES) == []
    assert audited_results(MODES, {"mode-1": True}) == []
    assert budget_report(MODES, [Budget("day", 1.0, "warn", window="day")]) == []


def test_a_real_log_of_a_hand_off_and_its_mode_record_reports_the_hand_off_alone(tmp_path):
    route, decision = delegated()
    run = Run(tmp_path / "log.jsonl", route, {m.id: ok for m in MODELS + [model("y/cheap", 0.1, family="y")]})
    run.ex.call_delegated(decision, [{"role": "user", "content": "brief"}], tags={"team": "a"})
    calls = run.records
    run.ex.record_mode(decision, "delegate", 4000, tags={"team": "a"})
    records = run.records
    assert len(records) == len(calls) + 1 and list(records[-1]) == KEYS
    assert records[-1]["call_id"] != calls[-1]["call_id"]
    assert report(records, by="tag:team") == report(calls, by="tag:team")
    assert report(records, by="tag:team")[0]["calls"] == 1


# --- docs ----------------------------------------------------------------------------------------

def test_the_production_lessons_line_says_the_log_ships_and_the_report_is_still_a_change():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    section = text[text.index("### Under-delegation is a failure you can measure"):]
    line = next(l for l in section.splitlines() if l.startswith("- In this library:"))
    assert "from v1.687 `Executor.record_mode` logs the mode it advised beside the mode the agent took" in line
    assert "The changes: report the share of advised hand-offs the agent skipped, and a cap on delegation depth." \
        in line
    assert "log the advised mode" not in line


def test_design_states_v1_687_in_7_8_1_and_8_3_and_the_changelog_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    seven = design[design.index("## 7. "):design.index("## 8. ")]
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert seven.count("\n- v1.687 `.record_mode(decision, actual_mode, input_tokens, tags=None) -> dict`") == 1
    assert eight3.count("\n- v1.687 mode records in a log (row DEL2, 8.1 v1.687)") == 1
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.687 (2026-11-27): ") == 1
