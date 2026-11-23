"""Budget windows and the downgrade mode (DESIGN 4.6, 7 and 8.1 v1.596, row B1b)."""

import json
from pathlib import Path

import pytest
from model_routing import (
    Budget, BudgetExceeded, BudgetLedger, Cascade, Completion, Executor, FakeProvider, Model,
    Monitor, Procedure, ProcedureResult, ProviderError, Registry, Router, Stats, Task,
    load_budgets,
)

ROOT = Path(__file__).resolve().parent.parent
MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
REGISTRY = Registry([
    Model(CHEAP, "small", 1.0, 2.0, 8000),
    Model(MID, "medium", 3.0, 6.0, 8000),
    Model(BEST, "large", 10.0, 20.0, 8000),
])
C = Cascade(CHEAP, BEST, "sig")
CID = "fiction/cheap>fiction/best@sig"


def cost(model_id):
    """A hold at 1,000 prompt tokens and the task's 200 output: 0.0014, 0.0042 and 0.014."""
    return REGISTRY.get(model_id).cost(1000, 200)


def ok(input_tokens=1000, output_tokens=200, calls=None):
    def script(messages):
        if calls is not None:
            calls.append(messages)
        return Completion("ok", input_tokens, output_tokens)
    return script


def fail(messages):
    raise ProviderError("outage")


def router(cheap=(90, 100), task=None):
    """cost_blind routes (best, mid, cheap); with cheap at 50/100 and fallback_below_bar
    cheap is the one below-bar fallback; with bar 0.99 and best_available all are below it."""
    task = Task("judge", bar=0.7, min_samples=10) if task is None else task
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, cheap), (MID, (95, 100)), (BEST, (100, 100))):
        stats.add(task.name, model_id, successes, trials)
    return Router(REGISTRY, {task.name: task}, stats)


def make(route, provider, ledger, monitor=None, now=None):
    ticks = iter(float(i) for i in range(1000))
    return Executor(route, provider, monitor=monitor, clock=lambda: next(ticks),
                    now=now if now is not None else (lambda: "2026-11-22T00:00:00Z"),
                    id_factory=lambda: "call-1", ledger=ledger)


# --- Budget and load_budgets ------------------------------------------------------------

@pytest.mark.parametrize("mode", ["warn", "refuse", "downgrade"])
@pytest.mark.parametrize("window", ["total", "day", "month"])
def test_every_mode_and_window_makes_a_budget(mode, window):
    budget = Budget("b", 1, mode, window=window)
    assert (budget.mode, budget.window) == (mode, window)


def test_load_budgets_reads_a_window_and_the_downgrade_mode(tmp_path):
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps({"budgets": [
        {"name": "d", "limit_usd": 2, "mode": "downgrade", "window": "day"},
        {"name": "m", "limit_usd": 50, "mode": "warn", "window": "month"},
    ]}), encoding="utf-8")
    assert load_budgets(path) == (Budget("d", 2.0, "downgrade", window="day"),
                                  Budget("m", 50.0, "warn", window="month"))


# --- the ledger's windows ---------------------------------------------------------------

@pytest.mark.parametrize("at", [3, b"2026-11-22T00:00:00Z", "", "noon",
                                "2026-13-01T00:00:00Z", "2026-11-22T25:00:00Z"])
def test_a_bad_at_raises_value_error_and_changes_nothing(at):
    ledger = BudgetLedger([Budget("t", 1.0, "warn"), Budget("d", 1.0, "warn", window="day")])
    for act in (lambda: ledger.reserve("judge", {}, 0.1, at=at),
                lambda: ledger.charge("judge", {}, 0.1, at=at),
                lambda: ledger.spent_usd("t", at=at), lambda: ledger.held_usd("d", at=at)):
        with pytest.raises(ValueError):
            act()
    assert ledger.spent_usd("t") == ledger.held_usd("t") == 0.0
    assert ledger.spent_usd("d", "2026-11-22T00:00:00Z") == 0.0


def test_a_day_budget_keeps_each_utc_day_apart():
    ledger = BudgetLedger([Budget("day", 1.0, "refuse", window="day")])
    late, next_day = "2026-11-22T23:59:59.999Z", "2026-11-23T00:00:00.000Z"
    ledger.settle(ledger.reserve("judge", {}, 0.75, at=late), 0.75)
    with pytest.raises(BudgetExceeded) as caught:
        ledger.reserve("judge", {}, 0.5, at="2026-11-22T12:00:00Z")
    assert (caught.value.spent_usd, caught.value.held_usd) == (0.75, 0.0)
    hold = ledger.reserve("judge", {}, 0.5, at=next_day)
    assert ledger.held_usd("day", next_day) == 0.5 and ledger.held_usd("day", late) == 0.0
    ledger.settle(hold, 0.5)
    assert [ledger.spent_usd("day", at) for at in (late, next_day, "2026-11-24T00:00:00Z")] == [
        0.75, 0.5, 0.0]


def test_a_month_budget_keeps_each_utc_month_apart_across_a_year():
    ledger = BudgetLedger([Budget("month", 1.0, "refuse", window="month")])
    for at in ("2026-11-01T00:00:00Z", "2026-11-30T23:59:59Z"):
        ledger.charge("judge", {}, 0.5, at=at)
    with pytest.raises(BudgetExceeded):
        ledger.reserve("judge", {}, 0.01, at="2026-11-15T00:00:00Z")
    for at in ("2026-12-01T00:00:00Z", "2027-01-01T00:00:00Z"):
        ledger.settle(ledger.reserve("judge", {}, 1.0, at=at), 1.0)
    assert [ledger.spent_usd("month", at) for at in (
        "2026-11-02T00:00:00Z", "2026-12-31T23:59:59Z", "2027-01-31T00:00:00Z",
        "2026-10-31T23:59:59Z")] == [1.0, 1.0, 1.0, 0.0]


def test_an_offset_is_converted_to_utc_and_no_offset_is_read_as_utc():
    ledger = BudgetLedger([Budget("day", 1.0, "warn", window="day")])
    ledger.charge("judge", {}, 0.25, at="2026-11-22T20:00:00-08:00")   # 04:00 on the 23rd, UTC
    ledger.charge("judge", {}, 0.125, at="2026-11-23T03:00:00")          # read as UTC
    assert ledger.spent_usd("day", "2026-11-23T12:00:00+00:00") == 0.375
    assert ledger.spent_usd("day", "2026-11-22T12:00:00Z") == 0.0


def test_a_hold_is_spent_in_the_window_it_was_held_in_and_counts_only_there():
    ledger = BudgetLedger([Budget("day", 1.0, "refuse", window="day"),
                           Budget("all", 10.0, "refuse")])
    first = ledger.reserve("judge", {}, 0.75, at="2026-11-22T23:59:00Z")
    second = ledger.reserve("judge", {}, 0.75, at="2026-11-23T00:01:00Z")  # not the 22nd's hold
    assert ledger.held_usd("all") == 1.5 and ledger.held_usd("day", "2026-11-23T05:00:00Z") == 0.75
    ledger.settle(second, 0.25)
    ledger.settle(first, 0.5)                                           # settled on the 23rd
    assert ledger.spent_usd("day", "2026-11-22T00:00:00Z") == 0.5
    assert ledger.spent_usd("day", "2026-11-23T00:00:00Z") == 0.25
    assert ledger.spent_usd("all") == 0.75 == ledger.spent_usd("all", "1999-01-01T00:00:00Z")


def test_each_warn_share_fires_once_per_window_with_the_window_label():
    ledger = BudgetLedger([Budget("day", 1.0, "warn", window="day"), Budget("all", 4.0, "warn")])
    for at in ("2026-11-22T01:00:00Z", "2026-11-22T02:00:00Z", "2026-11-23T01:00:00Z"):
        ledger.charge("judge", {}, 1.0, at=at)
    day = [{"budget": "day", "share": share, "spent_usd": 1.0, "limit_usd": 1.0}
           for share in (0.5, 0.8, 1.0)]
    assert ledger.events == (
        *(dict(event, window="2026-11-22") for event in day),
        {"budget": "all", "share": 0.5, "spent_usd": 2.0, "limit_usd": 4.0},
        *(dict(event, window="2026-11-23") for event in day),
    )
    month = BudgetLedger([Budget("m", 2.0, "warn", window="month")])
    month.charge("judge", {}, 1.0, at="2026-11-30T23:00:00Z")
    month.charge("judge", {}, 1.0, at="2026-12-01T00:00:00Z")
    assert [(e["share"], e["window"]) for e in month.events] == [(0.5, "2026-11"), (0.5, "2026-12")]


def test_a_refuse_budget_is_checked_before_a_downgrade_budget_and_neither_warns():
    ledger = BudgetLedger([Budget("move", 1.0, "downgrade"), Budget("stop", 1.0, "refuse")])
    with pytest.raises(BudgetExceeded) as caught:
        ledger.reserve("judge", {}, 2.0, "a/m")
    assert caught.value.budget.name == "stop"
    with pytest.raises(BudgetExceeded) as caught:
        BudgetLedger([Budget("move", 1.0, "downgrade")]).reserve("judge", {}, 2.0, "a/m")
    assert (caught.value.budget.mode, caught.value.model) == ("downgrade", "a/m")
    hold = ledger.reserve("judge", {}, 0.5)
    assert ledger.held_usd("move") == 0.5 == ledger.held_usd("stop")
    ledger.settle(hold, 1.0)
    assert ledger.spent_usd("move") == 1.0 and ledger.events == ()


# --- the executor: windows from its now -------------------------------------------------

def test_the_executor_reads_each_hold_window_from_its_now():
    when = {"at": "2026-11-22T10:00:00Z"}
    ledger = BudgetLedger([Budget("day", cost(CHEAP), "refuse", window="day")])
    monitor = Monitor()
    ex = make(router(), FakeProvider({CHEAP: ok()}), ledger, monitor, now=lambda: when["at"])
    assert ex.call("judge", MESSAGES, prompt_tokens=1000).model == CHEAP
    with pytest.raises(BudgetExceeded):
        ex.call("judge", MESSAGES, prompt_tokens=1000)                 # the same UTC day
    when["at"] = "2026-11-23T00:00:00Z"
    assert ex.call("judge", MESSAGES, prompt_tokens=1000).model == CHEAP
    assert ledger.spent_usd("day", "2026-11-22T00:00:00Z") == cost(CHEAP)
    assert ledger.spent_usd("day", "2026-11-23T00:00:00Z") == cost(CHEAP)
    assert [r["ts"] for r in monitor.records] == ["2026-11-22T10:00:00Z", "2026-11-23T00:00:00Z"]


def test_now_is_called_once_more_per_hold_only_with_a_windowed_budget():
    counts = []
    for budgets in (None, [Budget("t", 1.0, "warn")], [Budget("d", 1.0, "warn", window="day")]):
        stamps = []

        def now():
            stamps.append(1)
            return "2026-11-22T00:00:00Z"

        ledger = None if budgets is None else BudgetLedger(budgets)
        make(router(), FakeProvider({CHEAP: fail, MID: ok()}), ledger, Monitor(),
             now=now).call("judge", MESSAGES)
        counts.append(len(stamps))
    assert counts == [2, 2, 4]


def test_the_executor_reads_a_month_window_from_its_now_across_a_year():
    # review iter-444 must-fix 2: the month boundary through the executor's injected now
    when = {"at": "2026-12-31T23:59:59.999Z"}
    ledger = BudgetLedger([Budget("month", cost(CHEAP), "refuse", window="month")])
    monitor = Monitor()
    ex = make(router(), FakeProvider({CHEAP: ok()}), ledger, monitor, now=lambda: when["at"])
    assert ex.call("judge", MESSAGES, prompt_tokens=1000).model == CHEAP
    when["at"] = "2026-12-01T00:00:00Z"
    with pytest.raises(BudgetExceeded) as caught:
        ex.call("judge", MESSAGES, prompt_tokens=1000)                 # the same UTC month
    assert caught.value.spent_usd == cost(CHEAP)
    when["at"] = "2027-01-01T00:00:00.000Z"
    assert ex.call("judge", MESSAGES, prompt_tokens=1000).model == CHEAP
    assert ledger.spent_usd("month", "2026-12-15T00:00:00Z") == cost(CHEAP)
    assert ledger.spent_usd("month", "2027-01-15T00:00:00Z") == cost(CHEAP)
    assert [r["ts"] for r in monitor.records] == ["2026-12-31T23:59:59.999Z",
                                                  "2027-01-01T00:00:00.000Z"]


def test_a_call_held_before_midnight_is_spent_that_day():
    # review iter-444 should-fix 2: now() before the hold, then again for the record
    stamps = iter(["2026-11-22T23:59:59Z", "2026-11-23T00:00:01Z"])
    ledger = BudgetLedger([Budget("day", 1.0, "warn", window="day")])
    monitor = Monitor()
    make(router(), FakeProvider({CHEAP: ok()}), ledger, monitor,
         now=lambda: next(stamps)).call("judge", MESSAGES, prompt_tokens=1000)
    assert monitor.records[0]["ts"] == "2026-11-23T00:00:01Z"
    assert ledger.spent_usd("day", "2026-11-22T12:00:00Z") == cost(CHEAP)
    assert ledger.spent_usd("day", "2026-11-23T12:00:00Z") == 0.0


def test_a_procedure_closing_charge_reads_its_own_now():
    def poll(value, call):
        call([{"role": "user", "content": "hi"}])
        return ProcedureResult("shaped", tool_calls=1, tool_cost_usd=0.0005)

    proc = Procedure("poll", "v1", poll, max_model_calls=2, max_tool_calls=5, model=CHEAP)
    stats = Stats()
    stats.add("t", BEST, 98, 100)
    stats.add("t", proc.id, 95, 100, cost_usd=0.001)
    route = Router(REGISTRY, {"t": Task("t", bar=0.8, min_samples=10)}, stats)
    # the model call's hold, its record, the closing charge, the closing record
    stamps = iter(["2026-11-30T23:59:59Z", "2026-11-30T23:59:59Z", "2026-12-01T00:00:00Z",
                   "2026-12-01T00:00:00Z"])
    ledger = BudgetLedger([Budget("month", 1.0, "warn", window="month")])
    monitor = Monitor()
    ex = make(route, FakeProvider({CHEAP: ok(100, 10)}), ledger, monitor,
              now=lambda: next(stamps))
    assert ex.call("t", MESSAGES, procedures=[proc]).model == proc.id
    assert [r["cost_usd"] for r in monitor.records] == [REGISTRY.get(CHEAP).cost(100, 10), 0.0005]
    assert ledger.spent_usd("month", "2026-11-01T00:00:00Z") == REGISTRY.get(CHEAP).cost(100, 10)
    assert ledger.spent_usd("month", "2026-12-01T00:00:00Z") == 0.0005


def test_a_delegated_call_is_spent_in_its_own_window():
    when = {"at": "2026-11-22T12:00:00Z"}
    route = router()
    ledger = BudgetLedger([Budget("run", 1.0, "refuse", window="day", tags={"run": "r1"})])
    monitor = Monitor()
    ex = make(route, FakeProvider({CHEAP: ok(), BEST: ok(300, 40)}), ledger, monitor,
              now=lambda: when["at"])
    ex.call("judge", MESSAGES, prompt_tokens=1000, tags={"run": "r1"})
    decision = route.decide_delegation("judge", BEST, "cost_effective", context_tokens=5000,
                                       brief_tokens=100, result_tokens=20)
    assert decision.mode == "delegate"
    when["at"] = "2026-11-23T12:00:00Z"
    ex.call_delegated(decision, [{"role": "user", "content": "brief"}], tags={"run": "r1"})
    first, second = (r["cost_usd"] for r in monitor.records)
    assert monitor.records[1]["tags"]["delegated"] == "true" and second > 0
    assert ledger.spent_usd("run", "2026-11-22T00:00:00Z") == first
    assert ledger.spent_usd("run", "2026-11-23T00:00:00Z") == second


FOREIGN = BudgetExceeded(Budget("elsewhere", 1.0, "downgrade"), 0.0, 0.0, 2.0, "other/model")


def raise_foreign(*args):
    raise FOREIGN


@pytest.mark.parametrize("ledger", [
    None, [Budget("w", 1.0, "warn")], [Budget("move", 1.0, "downgrade", window="day")]])
@pytest.mark.parametrize("source", ["validate", "provider", "signal"])
def test_a_budget_exceeded_the_reservation_did_not_raise_never_moves_the_call(source, ledger):
    # review iter-444 must-fix 1: v1.595 propagates it after the first model; so does v1.596
    calls = []
    scripts = {m: ok(calls=calls) for m in (CHEAP, MID, BEST)}
    kwargs = {"prompt_tokens": 1000}
    if source == "validate":
        route, kwargs["validate"] = router(), raise_foreign
    elif source == "provider":
        route = router()
        scripts[CHEAP] = lambda messages: (calls.append(messages), raise_foreign())
    else:
        route, kwargs["signals"] = cascade_router(), {"sig": raise_foreign}
    task = "t" if source == "signal" else "judge"
    monitor = Monitor()
    ex = make(route, FakeProvider(scripts), None if ledger is None else BudgetLedger(ledger),
              monitor)
    with pytest.raises(BudgetExceeded) as caught:
        ex.call(task, MESSAGES, **kwargs)
    assert caught.value is FOREIGN and len(calls) == 1 and monitor.records == []


# --- the executor: downgrade ------------------------------------------------------------

def test_downgrade_moves_the_call_to_the_next_entry_that_fits():
    ledger = BudgetLedger([Budget("move", cost(MID), "downgrade")])
    monitor = Monitor()
    calls = []
    ex = make(router(), FakeProvider({BEST: ok(calls=calls), MID: ok()}), ledger, monitor)
    result = ex.call("judge", MESSAGES, flavor="cost_blind", prompt_tokens=1000)
    assert result.decision.primary == BEST and calls == []
    assert result.model == MID and [a.model for a in result.attempts] == [MID]
    [record] = monitor.records
    assert (record["model"], record["final"]) == (MID, True)
    assert record["budget_moves"] == [{"entry": BEST, "model": BEST, "budget": "move"}]
    keys = list(record)
    assert keys[keys.index("slice") + 1:keys.index("slice") + 3] == [
        "budget_moves", "prompt_tokens"]
    assert ledger.spent_usd("move") == cost(MID) and ledger.held_usd("move") == 0.0


def test_downgrade_refuses_when_no_entry_fits():
    ledger = BudgetLedger([Budget("move", cost(CHEAP) / 2, "downgrade")])
    monitor = Monitor()
    calls = []
    provider = FakeProvider({m: ok(calls=calls) for m in (BEST, MID, CHEAP)})
    with pytest.raises(BudgetExceeded) as caught:
        make(router(), provider, ledger, monitor).call("judge", MESSAGES, flavor="cost_blind",
                                                       prompt_tokens=1000)
    exc = caught.value
    assert (exc.budget.name, exc.model, exc.estimate_usd) == ("move", CHEAP, cost(CHEAP))
    assert exc.attempts == () and exc.decision.primary == BEST
    assert calls == [] and monitor.records == []
    assert ledger.spent_usd("move") == 0.0 == ledger.held_usd("move")


def test_downgrade_never_moves_a_call_to_a_below_bar_fallback():
    route = router(cheap=(50, 100),
                   task=Task("judge", bar=0.7, min_samples=10, fallback_below_bar=True))
    decision = route.select("judge", flavor="cost_blind")
    assert (decision.fallbacks, decision.below_bar_fallbacks) == ((MID, CHEAP), (CHEAP,))
    ledger = BudgetLedger([Budget("move", cost(CHEAP), "downgrade")])  # only cheap's fits
    calls = []
    provider = FakeProvider({m: ok(calls=calls) for m in (BEST, MID, CHEAP)})
    with pytest.raises(BudgetExceeded) as caught:
        make(route, provider, ledger, Monitor()).call("judge", MESSAGES, flavor="cost_blind",
                                                      prompt_tokens=1000)
    assert caught.value.model == MID and caught.value.attempts == () and calls == []


def test_downgrade_never_moves_a_call_whose_route_is_below_the_bar():
    route = router(task=Task("judge", bar=0.99, min_samples=10, on_no_model="best_available"))
    assert route.select("judge", flavor="cost_blind").below_bar
    ledger = BudgetLedger([Budget("move", cost(MID), "downgrade")])
    calls = []
    provider = FakeProvider({m: ok(calls=calls) for m in (BEST, MID, CHEAP)})
    with pytest.raises(BudgetExceeded) as caught:
        make(route, provider, ledger, Monitor()).call("judge", MESSAGES, flavor="cost_blind",
                                                      prompt_tokens=1000)
    assert caught.value.model == BEST and calls == []


def test_a_moved_call_falls_back_on_an_error_as_before_below_bar_included():
    route = router(cheap=(50, 100),
                   task=Task("judge", bar=0.7, min_samples=10, fallback_below_bar=True))
    ledger = BudgetLedger([Budget("move", cost(MID), "downgrade")])
    monitor = Monitor()
    ex = make(route, FakeProvider({MID: fail, CHEAP: ok()}), ledger, monitor)
    assert ex.call("judge", MESSAGES, flavor="cost_blind", prompt_tokens=1000).model == CHEAP
    move = [{"entry": BEST, "model": BEST, "budget": "move"}]
    assert [(r["model"], r["outcome"], r["budget_moves"]) for r in monitor.records] == [
        (MID, "error", move), (CHEAP, "ok", move)]
    assert monitor.records[1]["below_bar_fallback"] is True
    assert ledger.spent_usd("move") == cost(CHEAP)


def test_a_refuse_budget_ends_the_call_even_where_a_downgrade_budget_would_move_it():
    ledger = BudgetLedger([Budget("move", cost(MID), "downgrade"),
                           Budget("stop", cost(MID), "refuse")])
    calls = []
    provider = FakeProvider({m: ok(calls=calls) for m in (BEST, MID, CHEAP)})
    with pytest.raises(BudgetExceeded) as caught:
        make(router(), provider, ledger, Monitor()).call("judge", MESSAGES, flavor="cost_blind",
                                                         prompt_tokens=1000)
    assert (caught.value.budget.name, caught.value.model) == ("stop", BEST) and calls == []


def cascade_router():
    """cost_blind routes (best, the cascade): best 98/100, the cascade 95/100, cheap 60/100."""
    task = Task("t", bar=0.8, min_samples=10, cascades=(C,))
    stats = Stats()
    stats.add("t", CHEAP, 60, 100)
    stats.add("t", BEST, 98, 100)
    stats.add("t", CID, 95, 100, escalated=20)
    return Router(REGISTRY, {"t": task}, stats)


@pytest.mark.parametrize("escalate", [False, True])
def test_a_move_onto_a_cascade_and_off_its_strong_leg(escalate):
    ledger = BudgetLedger([Budget("move", 2 * cost(CHEAP), "downgrade")])
    monitor = Monitor()
    ex = make(cascade_router(), FakeProvider({CHEAP: ok(), BEST: ok()}), ledger, monitor)
    run = lambda: ex.call("t", MESSAGES, flavor="cost_blind", prompt_tokens=1000,  # noqa: E731
                          signals={"sig": lambda text: escalate})
    first = {"entry": BEST, "model": BEST, "budget": "move"}
    if not escalate:
        assert run().model == CHEAP
    else:                                     # the strong leg's hold moves it off the route
        with pytest.raises(BudgetExceeded) as caught:
            run()
        assert caught.value.model == BEST and [a.model for a in caught.value.attempts] == [CHEAP]
    [record] = monitor.records
    assert (record["cascade"], record["escalated"], record["final"]) == (CID, escalate,
                                                                          not escalate)
    assert record["budget_moves"] == [first]
    keys = list(record)
    assert keys[keys.index("escalated") + 1] == "budget_moves"
    assert ledger.spent_usd("move") == cost(CHEAP)


def test_a_downgrade_refusal_inside_a_procedure_ends_the_call():
    def poll(value, call):
        return ProcedureResult("shaped " + call([{"role": "user", "content": "hi"}]))

    proc = Procedure("poll", "v1", poll, max_model_calls=2, max_tool_calls=5, model=CHEAP)
    stats = Stats()
    stats.add("t", BEST, 98, 100)
    stats.add("t", proc.id, 95, 100, cost_usd=0.001)
    route = Router(REGISTRY, {"t": Task("t", bar=0.8, min_samples=10)}, stats)
    assert route.select("t", procedures=[proc]).fallbacks == (BEST,)
    ledger = BudgetLedger([Budget("move", 1e-9, "downgrade")])
    calls = []
    with pytest.raises(BudgetExceeded) as caught:
        make(route, FakeProvider({CHEAP: ok(calls=calls), BEST: ok(calls=calls)}), ledger,
             Monitor()).call("t", MESSAGES, procedures=[proc])
    assert caught.value.model == CHEAP and calls == []


def test_without_a_downgrade_or_windowed_budget_no_record_has_budget_moves():
    for ledger in (None, BudgetLedger([Budget("r", 1.0, "refuse"), Budget("w", 1.0, "warn")])):
        monitor = Monitor()
        make(router(), FakeProvider({BEST: fail, MID: ok()}), ledger, monitor).call(
            "judge", MESSAGES, flavor="cost_blind", prompt_tokens=1000)
        assert [r["model"] for r in monitor.records] == [BEST, MID]
        assert all("budget_moves" not in r for r in monitor.records)


# --- spec and the note ------------------------------------------------------------------

def test_design_specifies_windows_and_downgrade_and_defers_only_row_b1c():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four = text[text.index("### 4.6 Budgets"):text.index("## 5. ")]
    assert four.count("  - v1.596 windows (row B1b): ") == 1
    assert "(row B1b); a strict mode" not in four and "- Not in this version: a strict mode" in four
    seven = text[text.index("## 7. "):text.index("## 8. ")]
    assert seven.count("- v1.596 windows and downgrade (row B1b): ") == 1
    eight = text[text.index("### 8.1 "):text.index("### 8.2 ")]
    assert eight.count("- v1.596 `budget_moves` (row B1b, 7 v1.596): ") == 1
    fourteen = text[text.index("## 14. "):text.index("## 15. ")]
    assert "rows B1b and B1c" not in fourteen
    assert fourteen.count("and v1.596's windows and `downgrade` mode, whose strict caps and "
                          "logged crossings are row B1c") == 1
    last = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()[-1]
    assert last.startswith("- v1.596 (2026-11-22): ") and "row B1b" in last


def test_the_note_states_windows_and_downgrade_as_shipped():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    lines = [line for line in note.splitlines() if line.startswith("- In this library: ")]
    for planned in ("The change still planned: a window of a day or a month",
                    "The changes: the budget's day and month windows",
                    "there is no budget", "and an in-process budget that refuses a call, or moves"):
        assert all(planned not in line for line in lines), planned
    [spend] = [line for line in lines if "`BudgetExceeded`" in line]
    assert "From v1.596 a budget's window can also be a UTC day or month, and a `downgrade` " \
        "budget" in spend
    assert sum("with the day and month windows of the Uber lesson on spend tiers (v1.596) but "
               "no rate limit." in line for line in lines) == 1
