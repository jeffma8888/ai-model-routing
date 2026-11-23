"""Budget records in the monitor log and budget_report (DESIGN 4.6, 7, 8.1 and 8.3 v1.598, row B1e)."""

import math
from pathlib import Path

import pytest
import model_routing
from model_routing import (
    Budget, BudgetExceeded, BudgetLedger, Completion, Executor, FakeProvider, Model, Monitor,
    Procedure, ProcedureResult, Registry, Router, Stats, Task, report,
)

ROOT = Path(__file__).resolve().parent.parent
MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
REGISTRY = Registry([
    Model(CHEAP, "small", 1.0, 2.0, 8000),
    Model(MID, "medium", 3.0, 6.0, 8000),
    Model(BEST, "large", 10.0, 20.0, 8000),
])
WARN_KEYS = ["ts", "call_id", "task", "tags", "budget_event", "budget", "mode", "window",
             "share", "spent_usd", "limit_usd"]
REFUSED_KEYS = ["ts", "call_id", "task", "tags", "budget_event", "budget", "mode", "window",
                "model", "spent_usd", "held_usd", "estimate_usd", "limit_usd", "unbounded"]


def cost(model_id):
    """A hold at 1,000 prompt tokens and the task's 200 output: 0.0014, 0.0042 and 0.014."""
    return REGISTRY.get(model_id).cost(1000, 200)


def ok(messages):
    return Completion("ok", 1000, 200)


def router(flavor_order_best_first=False):
    """cost_effective routes cheap first; cost_blind routes (best, mid, cheap)."""
    task = Task("judge", bar=0.7, min_samples=10)
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (MID, (95, 100)), (BEST, (100, 100))):
        stats.add(task.name, model_id, successes, trials)
    return Router(REGISTRY, {task.name: task}, stats)


def make(route, provider, ledger, monitor=None, now=None):
    ticks = iter(float(i) for i in range(1000))
    return Executor(route, provider, monitor=monitor, clock=lambda: next(ticks),
                    now=now if now is not None else (lambda: "2026-11-22T00:00:00Z"),
                    id_factory=lambda: "call-1", ledger=ledger)


def attempts_of(records):
    return [rec for rec in records if "budget_event" not in rec]


def budget_records(records):
    return [rec for rec in records if "budget_event" in rec]


# --- the ledger ---------------------------------------------------------------------------

def test_settle_and_charge_return_the_warn_events_their_add_appended():
    ledger = BudgetLedger([Budget("w", 2.0, "warn"), Budget("r", 9.0, "refuse")])
    hold = ledger.reserve("t", {}, 1.0)
    first = ledger.settle(hold, 1.0)
    assert first == ({"budget": "w", "share": 0.5, "spent_usd": 1.0, "limit_usd": 2.0},)
    assert ledger.charge("t", {}, 1.0) == (
        {"budget": "w", "share": 0.8, "spent_usd": 2.0, "limit_usd": 2.0},
        {"budget": "w", "share": 1.0, "spent_usd": 2.0, "limit_usd": 2.0})
    assert ledger.settle(ledger.reserve("t", {}, 0.5), 0.5) == ()
    assert ledger.settle_unpriced(ledger.reserve("t", {}, 0.5)) == ()
    assert ledger.events == first + ledger.events[1:3] and len(ledger.events) == 3
    first[0]["share"] = 9
    assert ledger.events[0]["share"] == 0.5                       # a new dict, not the entry


def test_a_refusal_names_the_window_its_check_read():
    for window, label in (("total", None), ("day", "2026-11-22"), ("month", "2026-11")):
        ledger = BudgetLedger([Budget("b", 1.0, "refuse", window=window)])
        with pytest.raises(BudgetExceeded) as caught:
            ledger.reserve("t", {}, 2.0, "m", at="2026-11-22T10:00:00Z")
        assert caught.value.window == label
    plain = BudgetExceeded(Budget("b", 1.0, "refuse"), 0.0, 0.0, 2.0, "m")
    assert plain.window is None


# --- the executor's records ----------------------------------------------------------------

def test_a_refusal_that_ends_the_call_writes_one_refused_record():
    ledger = BudgetLedger([Budget("two", 2 * cost(CHEAP), "refuse")])
    monitor = Monitor()
    ex = make(router(), FakeProvider({CHEAP: ok}), ledger, monitor)
    for _ in range(2):
        ex.call("judge", MESSAGES, prompt_tokens=1000, tags={"s": "t"})
    with pytest.raises(BudgetExceeded):
        ex.call("judge", MESSAGES, prompt_tokens=1000, tags={"s": "t"})
    assert len(attempts_of(monitor.records)) == 2
    [refused] = budget_records(monitor.records)
    assert monitor.records[-1] is refused
    assert list(refused) == REFUSED_KEYS
    assert refused == {
        "ts": "2026-11-22T00:00:00Z", "call_id": "call-1", "task": "judge", "tags": {"s": "t"},
        "budget_event": "refused", "budget": "two", "mode": "refuse", "window": None,
        "model": CHEAP, "spent_usd": cost(CHEAP) + cost(CHEAP), "held_usd": 0.0,
        "estimate_usd": cost(CHEAP), "limit_usd": 2 * cost(CHEAP), "unbounded": False}


def test_each_warn_crossing_is_written_right_after_the_settle_that_made_it():
    ledger = BudgetLedger([Budget("two", 2 * cost(CHEAP), "warn", window="day")])
    monitor = Monitor()
    ex = make(router(), FakeProvider({CHEAP: ok}), ledger, monitor)
    for _ in range(3):
        ex.call("judge", MESSAGES, prompt_tokens=1000)
    kinds = [rec.get("budget_event", "attempt") for rec in monitor.records]
    assert kinds == ["warn", "attempt", "warn", "warn", "attempt", "attempt"]
    warns = budget_records(monitor.records)
    assert all(list(rec) == WARN_KEYS for rec in warns)
    assert warns[0] == {
        "ts": "2026-11-22T00:00:00Z", "call_id": "call-1", "task": "judge", "tags": {},
        "budget_event": "warn", "budget": "two", "mode": "warn", "window": "2026-11-22",
        "share": 0.5, "spent_usd": cost(CHEAP), "limit_usd": 2 * cost(CHEAP)}
    assert [rec["share"] for rec in warns] == [0.5, 0.8, 1.0]
    assert [{k: v for k, v in rec.items() if k not in ("ts", "call_id", "task", "tags",
                                                        "budget_event", "mode")}
            for rec in warns] == [dict(event, window=event["window"]) for event in ledger.events]


def test_a_downgrade_move_writes_one_refused_record_before_the_moved_attempt():
    ledger = BudgetLedger([Budget("d", 0.005, "downgrade")])
    monitor = Monitor()
    result = make(router(), FakeProvider({BEST: ok, MID: ok}), ledger, monitor).call(
        "judge", MESSAGES, flavor="cost_blind", prompt_tokens=1000)
    assert result.model == MID
    refused, attempt = monitor.records
    assert (refused["budget_event"], refused["mode"], refused["model"]) == ("refused", "downgrade", BEST)
    assert refused["estimate_usd"] == cost(BEST) and refused["unbounded"] is False
    assert "budget_event" not in attempt and attempt["budget_moves"] == [
        {"entry": BEST, "model": BEST, "budget": "d"}]


def test_a_strict_refusal_of_a_procedure_entry_is_written_unbounded():
    def poll(value, call):
        call([{"role": "user", "content": "hi"}])
        return ProcedureResult("shaped", tool_calls=1, tool_cost_usd=0.0005)

    proc = Procedure("poll", "v1", poll, max_model_calls=2, max_tool_calls=5, model=CHEAP)
    stats = Stats()
    stats.add("t", BEST, 98, 100)
    stats.add("t", proc.id, 95, 100, cost_usd=0.001)
    route = Router(REGISTRY, {"t": Task("t", bar=0.8, min_samples=10)}, stats)
    assert route.select("t", procedures=[proc]).primary == proc.id
    monitor = Monitor()
    with pytest.raises(BudgetExceeded):
        make(route, FakeProvider({CHEAP: ok, BEST: ok}),
             BudgetLedger([Budget("s", 1.0, "refuse", strict=True)]), monitor).call(
            "t", MESSAGES, procedures=[proc])
    [refused] = monitor.records
    assert (refused["model"], refused["unbounded"], refused["estimate_usd"]) == (proc.id, True, 0.0)


def test_a_budget_exceeded_the_provider_raises_writes_no_record():
    foreign = BudgetExceeded(Budget("elsewhere", 1.0, "refuse"), 0.0, 0.0, 2.0, "m")

    def raises(messages):
        raise foreign

    monitor = Monitor()
    with pytest.raises(BudgetExceeded) as caught:
        make(router(), FakeProvider({CHEAP: raises}),
             BudgetLedger([Budget("d", 1.0, "downgrade")]), monitor).call(
            "judge", MESSAGES, prompt_tokens=1000)
    assert caught.value is foreign and budget_records(monitor.records) == []


def test_without_a_monitor_the_ledger_still_runs_and_nothing_is_written():
    ledger = BudgetLedger([Budget("two", 2 * cost(CHEAP), "warn")])
    ex = make(router(), FakeProvider({CHEAP: ok}), ledger)
    for _ in range(3):
        ex.call("judge", MESSAGES, prompt_tokens=1000)
    assert len(ledger.events) == 3


# --- report and budget_report --------------------------------------------------------------

def _log():
    ledger = BudgetLedger([Budget("w", 2 * cost(CHEAP), "warn"),
                           Budget("r", 3 * cost(CHEAP), "refuse", tags={"tool": "a"})])
    monitor = Monitor()
    ex = make(router(), FakeProvider({CHEAP: ok}), ledger, monitor)
    for _ in range(4):
        try:
            ex.call("judge", MESSAGES, prompt_tokens=1000, tags={"tool": "a"})
        except BudgetExceeded:
            pass
    ex.call("judge", MESSAGES, prompt_tokens=1000, tags={"tool": "b"})
    return ledger, monitor.records


def test_report_reads_the_attempt_records_alone():
    _, records = _log()
    assert budget_records(records) and len(attempts_of(records)) == 4
    audits = {"call-1": True}
    for by in ("model", "task", "flavor", "family", "pricing_basis", "tag:tool"):
        assert report(records, by=by) == report(attempts_of(records), by=by)
    assert report(records, audits=audits, cache=True) == report(
        attempts_of(records), audits=audits, cache=True)


def test_budget_report_gives_the_total_budgets_spend_and_counts():
    ledger, records = _log()
    budgets = list(ledger.budgets)
    rows = model_routing.budget_report(records, budgets)
    spent_w = math.fsum([cost(CHEAP)] * 4)
    spent_r = math.fsum([cost(CHEAP)] * 3)
    assert rows == [
        {"budget": "w", "window": None, "mode": "warn", "limit_usd": 2 * cost(CHEAP),
         "spent_usd": round(spent_w, 6), "budget_used_pct": round(100 * spent_w / (2 * cost(CHEAP)), 6),
         "warn_records": 3, "refused_records": 0},
        {"budget": "r", "window": None, "mode": "refuse", "limit_usd": 3 * cost(CHEAP),
         "spent_usd": round(spent_r, 6), "budget_used_pct": round(100 * spent_r / (3 * cost(CHEAP)), 6),
         "warn_records": 0, "refused_records": 1},
    ]
    assert rows[0]["budget_used_pct"] == 200.0 and rows[1]["budget_used_pct"] == 100.0
    assert list(rows[0]) == ["budget", "window", "mode", "limit_usd", "spent_usd",
                             "budget_used_pct", "warn_records", "refused_records"]


def test_budget_report_splits_a_day_budget_by_each_records_ts():
    records = [
        {"ts": "2026-11-23T00:00:01Z", "call_id": "b", "task": "t", "tags": {}, "cost_usd": 0.25},
        {"ts": "2026-11-22T23:59:59Z", "call_id": "a", "task": "t", "tags": {}, "cost_usd": 0.5},
        {"ts": "2026-11-22T12:00:00+02:00", "call_id": "c", "task": "t", "tags": {}},
        {"ts": "x", "call_id": "d", "task": "t", "budget_event": "refused", "budget": "day",
         "mode": "refuse", "window": "2026-11-24"},
        {"ts": "x", "call_id": "e", "task": "t", "budget_event": "warn", "budget": "gone",
         "mode": "warn", "window": None},
        {"ts": "2026-11-22T00:00:00Z", "call_id": "f", "task": "other", "tags": {}, "cost_usd": 9.0},
    ]
    rows = model_routing.budget_report(records, (Budget("day", 1.0, "refuse", task="t",
                                                         window="day"),))
    assert [(r["window"], r["spent_usd"], r["budget_used_pct"], r["refused_records"])
            for r in rows] == [("2026-11-22", 0.5, 50.0, 0), ("2026-11-23", 0.25, 25.0, 0),
                               ("2026-11-24", 0.0, 0.0, 1)]
    month = model_routing.budget_report(records, [Budget("m", 2.0, "warn", window="month")])
    assert [(r["window"], r["spent_usd"]) for r in month] == [("2026-11", 9.75)]
    assert model_routing.budget_report([], [Budget("m", 2.0, "warn", window="month")]) == []
    assert model_routing.budget_report([], [Budget("t", 2.0, "warn")])[0]["spent_usd"] == 0.0


def test_budget_report_refuses_bad_budgets_and_an_unreadable_ts():
    for budgets in ("b", [Budget("a", 1.0, "warn"), Budget("a", 2.0, "refuse")], [object()]):
        with pytest.raises(ValueError):
            model_routing.budget_report([], budgets)
    bad = [{"ts": "yesterday", "call_id": "q1", "task": "t", "tags": {}, "cost_usd": 0.1}]
    assert model_routing.budget_report(bad, [Budget("t", 1.0, "warn")])[0]["spent_usd"] == 0.1
    with pytest.raises(ValueError, match="q1"):
        model_routing.budget_report(bad, [Budget("d", 1.0, "warn", window="day")])


# --- exports, spec and the note -------------------------------------------------------------

def test_budget_report_is_exported_after_report():
    names = model_routing.__all__
    assert names[names.index("report") + 1] == "budget_report"
    assert model_routing.budget_report is model_routing.monitor.budget_report


def test_design_and_the_note_state_the_records_as_shipped():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four6 = text[text.index("### 4.6 Budgets"):text.index("## 5. ")]
    assert four6.count("  - v1.598 records (row B1e): ") == 1
    assert "- Not in this version: a CLI option and exit code for a refusal (row B1f) and the " \
        "README paragraph (row B1d);" in four6
    assert text[text.index("## 7. "):text.index("## 8. ")].count("- v1.598 budget records (row B1e): ") == 1
    eight = text[text.index("## 8. "):text.index("## 9. ")]
    assert eight.count("- v1.598 budget records (row B1e") == 2
    assert "  monitor.py      Monitor, load_records, load_audits, report, budget_report (v1.598)\n" in text
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    [spend] = [line for line in note.splitlines()
               if line.startswith("- In this library: ") and "`BudgetExceeded`" in line]
    assert "The change still planned: warn crossings and refusals" not in spend
    assert spend.endswith("From v1.598 the executor writes each warn crossing and each refusal "
                          "to the monitor log as a budget record, which `report` skips, and "
                          "`budget_report` gives each budget's spend in each window as a percent "
                          "of its limit.")
    [line] = [line for line in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
              if line.startswith("- v1.598 (2026-11-23): ")]
    assert "row B1e" in line


def test_no_evidence_script_or_demo_runs_a_ledger_so_their_outputs_keep_their_bytes():
    paths = [ROOT / "model_routing" / "demo.py", ROOT / "model_routing" / "cli.py",
             *sorted((ROOT / "evidence").rglob("*.py")), *sorted((ROOT / "research").rglob("*.py"))]
    assert len(paths) > 2
    for path in paths:
        source = path.read_text(encoding="utf-8")
        assert "BudgetLedger" not in source and "budget_report" not in source, path
