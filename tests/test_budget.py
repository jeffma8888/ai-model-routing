"""In-process budgets: the ledger and the executor's holds (DESIGN 4.6 and 7 v1.595, row B1a)."""

import json
import math
from dataclasses import FrozenInstanceError
from pathlib import Path

import pytest
import model_routing
from model_routing import (
    Budget, BudgetExceeded, BudgetLedger, Completion, Executor, FakeProvider, Model, Monitor,
    Procedure, ProcedureResult, ProviderError, Registry, Router, Stats, Task, load_budgets,
)

ROOT = Path(__file__).resolve().parent.parent
MESSAGES = [{"role": "user", "content": "judge"}]


def ok(input_tokens=1000, output_tokens=200, calls=None):
    def script(messages):
        if calls is not None:
            calls.append(messages)
        return Completion("ok", input_tokens, output_tokens)
    return script


def fail(messages):
    raise ProviderError("outage")


def executor(router, provider, ledger=None, monitor=None):
    ticks = iter(float(i) for i in range(1000))
    return Executor(router, provider, monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: "2026-11-22T00:00:00Z", id_factory=lambda: "call-1",
                    ledger=ledger)


@pytest.fixture
def unit(registry):
    """fiction/cheap at the task's 1,000 prompt tokens and 200 output: 1000 * 1 + 200 * 2 per 1e6."""
    c = registry.get("fiction/cheap").cost(1000, 200)
    assert c == pytest.approx(0.0014)
    return c


# --- Budget -----------------------------------------------------------------------------

def test_a_budget_has_its_defaults_and_is_frozen():
    budget = Budget("team", 1, "warn")
    assert (budget.name, budget.limit_usd, budget.mode, budget.window, budget.task,
            budget.tags) == ("team", 1.0, "warn", "total", None, {})
    assert type(budget.limit_usd) is float
    with pytest.raises(FrozenInstanceError):
        budget.limit_usd = 2.0


def test_a_budget_copies_its_tags():
    tags = {"tool": "a"}
    budget = Budget("a", 1.0, "refuse", tags=tags)
    tags["tool"] = "b"
    assert budget.tags == {"tool": "a"}


@pytest.mark.parametrize("kwargs", [
    {"name": ""}, {"name": 3}, {"limit_usd": 0}, {"limit_usd": -1.0}, {"limit_usd": True},
    {"limit_usd": float("nan")}, {"limit_usd": float("inf")}, {"limit_usd": "1"},
    {"limit_usd": 10 ** 400}, {"mode": "downgrade"}, {"mode": "WARN"}, {"window": "day"},
    {"window": "month"}, {"task": ""}, {"task": 3}, {"tags": {"tool": 1}}, {"tags": {1: "a"}},
    {"tags": ["tool"]}, {"tags": None},
])
def test_a_bad_budget_raises_at_construction(kwargs):
    fields = dict({"name": "b", "limit_usd": 1.0, "mode": "refuse"}, **kwargs)
    with pytest.raises(ValueError):
        Budget(**fields)


def test_applies_reads_the_task_and_every_tag_pair():
    assert Budget("all", 1.0, "warn").applies("judge", {})
    on_task = Budget("t", 1.0, "warn", task="judge")
    assert on_task.applies("judge", {"x": "y"}) and not on_task.applies("other", {})
    on_tags = Budget("g", 1.0, "warn", tags={"tool": "a", "team": "t"})
    assert on_tags.applies("any", {"tool": "a", "team": "t", "more": "z"})
    assert not on_tags.applies("any", {"tool": "a"})
    assert not on_tags.applies("any", {"tool": "b", "team": "t"})
    both = Budget("b", 1.0, "warn", task="judge", tags={"tool": "a"})
    assert both.applies("judge", {"tool": "a"}) and not both.applies("other", {"tool": "a"})


# --- load_budgets -----------------------------------------------------------------------

def test_load_budgets_reads_every_field(tmp_path):
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps({"budgets": [
        {"name": "pool", "limit_usd": 1500, "mode": "warn"},
        {"name": "tool-a", "limit_usd": 0.5, "mode": "refuse", "window": "total",
         "task": None, "tags": {"tool": "a"}},
        {"name": "judge", "limit_usd": 2.0, "mode": "refuse", "task": "judge"},
    ]}), encoding="utf-8")
    assert load_budgets(path) == (
        Budget("pool", 1500.0, "warn"),
        Budget("tool-a", 0.5, "refuse", tags={"tool": "a"}),
        Budget("judge", 2.0, "refuse", task="judge"),
    )
    assert load_budgets(str(path))[0].name == "pool"


@pytest.mark.parametrize("data", [
    [], {"budget": []}, {"budgets": {}}, {"budgets": ["pool"]},
    {"budgets": [{"name": "a", "limit_usd": 1, "mode": "warn", "scope": "tag"}]},
    {"budgets": [{"name": "a", "limit_usd": 1, "mode": "warn"},
                 {"name": "a", "limit_usd": 2, "mode": "refuse"}]},
    {"budgets": [{"name": "a", "mode": "warn"}]},
    {"budgets": [{"name": "a", "limit_usd": 1, "mode": "warn", "window": "day"}]},
])
def test_load_budgets_refuses_a_bad_file(tmp_path, data):
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    with pytest.raises(ValueError):
        load_budgets(path)


# --- BudgetLedger -----------------------------------------------------------------------

@pytest.mark.parametrize("budgets", [
    "pool", {"name": "a"}, [Budget("a", 1.0, "warn"), "b"],
    [Budget("a", 1.0, "warn"), Budget("a", 2.0, "refuse")], None,
])
def test_a_ledger_takes_a_list_or_tuple_of_budgets_with_unique_names(budgets):
    with pytest.raises(ValueError):
        BudgetLedger(budgets)


def test_a_new_ledger_has_spent_and_held_nothing():
    ledger = BudgetLedger([Budget("a", 1.0, "warn"), Budget("b", 2.0, "refuse")])
    assert ledger.budgets == (Budget("a", 1.0, "warn"), Budget("b", 2.0, "refuse"))
    assert BudgetLedger().budgets == ()
    assert (ledger.spent_usd("a"), ledger.held_usd("b"), ledger.events) == (0.0, 0.0, ())
    with pytest.raises(ValueError):
        ledger.spent_usd("c")
    with pytest.raises(ValueError):
        ledger.held_usd("c")


@pytest.mark.parametrize("value", [-0.1, float("nan"), float("inf"), True, "0.1", None])
def test_reserve_settle_and_charge_refuse_a_bad_amount(value):
    ledger = BudgetLedger([Budget("a", 1.0, "refuse")])
    with pytest.raises(ValueError):
        ledger.reserve("t", {}, value)
    hold = ledger.reserve("t", {}, 0.1)
    with pytest.raises(ValueError):
        ledger.settle(hold, value)
    with pytest.raises(ValueError):
        ledger.charge("t", {}, value)


def test_a_hold_counts_until_settled_and_settles_once():
    budget = Budget("a", 1.0, "refuse")
    ledger = BudgetLedger([budget])
    first = ledger.reserve("t", {}, 0.6, "m1")
    assert ledger.held_usd("a") == 0.6
    with pytest.raises(BudgetExceeded) as caught:
        ledger.reserve("t", {}, 0.5, "m2")   # 0 + 0.6 + 0.5 > 1.0
    exc = caught.value
    assert (exc.budget, exc.spent_usd, exc.held_usd, exc.estimate_usd, exc.model) == (
        budget, 0.0, 0.6, 0.5, "m2")
    assert (exc.attempts, exc.decision) == ((), None)
    assert ledger.held_usd("a") == 0.6       # the refused reservation held nothing
    ledger.settle(first, 0.4)
    assert (ledger.spent_usd("a"), ledger.held_usd("a")) == (0.4, 0.0)
    with pytest.raises(ValueError):
        ledger.settle(first, 0.4)
    ledger.settle(ledger.reserve("t", {}, 0.6), 0.6)   # 0.4 + 0.6 is not over 1.0
    assert ledger.spent_usd("a") == 1.0
    ledger.charge("t", {}, 0.25)              # spent without a hold: never refused
    assert ledger.spent_usd("a") == 1.25


def test_a_refusal_names_the_first_refusing_budget_and_holds_on_none():
    ledger = BudgetLedger([Budget("w", 0.1, "warn"), Budget("r1", 1.0, "refuse"),
                           Budget("r2", 0.5, "refuse"), Budget("r3", 0.4, "refuse")])
    with pytest.raises(BudgetExceeded) as caught:
        ledger.reserve("t", {}, 0.45)
    assert caught.value.budget.name == "r3"
    assert [ledger.held_usd(n) for n in ("w", "r1", "r2", "r3")] == [0.0] * 4
    with pytest.raises(BudgetExceeded) as caught:
        ledger.reserve("t", {}, 0.6)
    assert caught.value.budget.name == "r2"
    hold = ledger.reserve("t", {}, 0.4)       # the warn budget at 0.1 never refuses
    assert [ledger.held_usd(n) for n in ("w", "r1", "r2", "r3")] == [0.4] * 4
    ledger.settle(hold, 0.0)
    assert [ledger.spent_usd(n) for n in ("w", "r1", "r2", "r3")] == [0.0] * 4


def test_out_of_scope_budgets_hold_and_spend_nothing():
    ledger = BudgetLedger([Budget("a", 1.0, "refuse", tags={"tool": "a"}),
                           Budget("judge", 1.0, "refuse", task="judge")])
    ledger.settle(ledger.reserve("other", {"tool": "b"}, 5.0), 5.0)
    assert (ledger.spent_usd("a"), ledger.spent_usd("judge")) == (0.0, 0.0)


def test_each_warn_share_fires_once_in_order():
    ledger = BudgetLedger([Budget("w", 10.0, "warn"), Budget("r", 10.0, "refuse")])
    ledger.charge("t", {}, 4.0)
    assert ledger.events == ()
    ledger.charge("t", {}, 4.5)               # 8.5: crosses 0.5 and 0.8 at once
    ledger.charge("t", {}, 1.0)               # 9.5
    ledger.charge("t", {}, 0.5)               # 10.0: at the limit is a crossing
    ledger.charge("t", {}, 5.0)               # past it: nothing new
    assert ledger.events == (
        {"budget": "w", "share": 0.5, "spent_usd": 8.5, "limit_usd": 10.0},
        {"budget": "w", "share": 0.8, "spent_usd": 8.5, "limit_usd": 10.0},
        {"budget": "w", "share": 1.0, "spent_usd": 10.0, "limit_usd": 10.0},
    )
    ledger.events[0]["share"] = 9
    assert ledger.events[0]["share"] == 0.5   # a copy each time


# --- the executor -----------------------------------------------------------------------

@pytest.mark.parametrize("value", ["ledger", [Budget("a", 1.0, "warn")], object()])
def test_the_executor_refuses_a_ledger_that_is_not_one(router, value):
    with pytest.raises(ValueError):
        Executor(router, FakeProvider({}), ledger=value)


def test_without_a_ledger_or_with_no_budget_every_record_is_as_before(router):
    logs = []
    for ledger in (None, BudgetLedger(), BudgetLedger([Budget("x", 1.0, "refuse", task="none")])):
        monitor = Monitor()
        provider = FakeProvider({"fiction/cheap": fail, "fiction/mid": ok()})
        executor(router, provider, ledger, monitor).call("judge", MESSAGES, tags={"s": "t"})
        logs.append(monitor.records)
    plain = Monitor()
    ticks = iter(float(i) for i in range(1000))
    Executor(router, FakeProvider({"fiction/cheap": fail, "fiction/mid": ok()}), monitor=plain,
             clock=lambda: next(ticks), now=lambda: "2026-11-22T00:00:00Z",
             id_factory=lambda: "call-1").call("judge", MESSAGES, tags={"s": "t"})
    assert logs[0] == logs[1] == logs[2] == plain.records
    assert len(plain.records) == 2


def test_refuse_runs_two_calls_of_a_two_call_budget_and_refuses_the_third(router, unit):
    calls = []
    ledger = BudgetLedger([Budget("two", 2 * unit, "refuse")])
    monitor = Monitor()
    ex = executor(router, FakeProvider({"fiction/cheap": ok(calls=calls)}), ledger, monitor)
    for _ in range(2):
        assert ex.call("judge", MESSAGES, prompt_tokens=1000).model == "fiction/cheap"
    with pytest.raises(BudgetExceeded) as caught:
        ex.call("judge", MESSAGES, prompt_tokens=1000)
    exc = caught.value
    assert (exc.spent_usd, exc.held_usd, exc.estimate_usd, exc.model) == (
        2 * unit, 0.0, unit, "fiction/cheap")
    assert exc.attempts == () and exc.decision.primary == "fiction/cheap"
    assert len(calls) == 2 and len(monitor.records) == 2
    assert ledger.spent_usd("two") == 2 * unit == math.fsum(r["cost_usd"] for r in monitor.records)
    assert ledger.held_usd("two") == 0.0


def test_warn_runs_all_three_calls_and_fires_each_share_once(router, unit):
    ledger = BudgetLedger([Budget("two", 2 * unit, "warn")])
    ex = executor(router, FakeProvider({"fiction/cheap": ok()}), ledger)
    for _ in range(3):
        ex.call("judge", MESSAGES, prompt_tokens=1000)
    assert ledger.spent_usd("two") == unit + unit + unit
    assert ledger.events == (
        {"budget": "two", "share": 0.5, "spent_usd": unit, "limit_usd": 2 * unit},
        {"budget": "two", "share": 0.8, "spent_usd": 2 * unit, "limit_usd": 2 * unit},
        {"budget": "two", "share": 1.0, "spent_usd": 2 * unit, "limit_usd": 2 * unit},
    )


def test_the_hold_is_the_call_prompt_and_the_task_output_at_list_price(router, registry):
    seen = []

    class Spy(BudgetLedger):
        def reserve(self, task, tags, estimate_usd, model=None):
            seen.append((task, dict(tags), estimate_usd, model))
            return super().reserve(task, tags, estimate_usd, model)

    ledger = Spy([Budget("a", 1.0, "warn")])
    # the completion's 1,234 and 56 tokens are what the record and the spend use
    ex = executor(router, FakeProvider({"fiction/cheap": ok(1234, 56)}), ledger)
    ex.call("judge", MESSAGES, prompt_tokens=700, tags={"k": "v"})
    ex.call("judge", [{"role": "user", "content": "x" * 400}])   # estimated at 100 tokens
    cheap = registry.get("fiction/cheap")
    assert seen == [("judge", {"k": "v"}, cheap.cost(700, 200), "fiction/cheap"),
                    ("judge", {}, cheap.cost(100, 200), "fiction/cheap")]
    assert ledger.spent_usd("a") == 2 * cheap.cost(1234, 56)


def test_a_slice_output_size_sets_the_hold(registry, measured_stats):
    task = Task("judge", bar=0.7, min_samples=10, slices={"long": {"expected_output_tokens": 900}})
    stats = Stats()
    for model_id, successes in [("fiction/cheap", 90), ("fiction/mid", 95), ("fiction/best", 100)]:
        stats.add("judge", model_id, successes, 100)
        stats.add("judge@long", model_id, successes, 100)
    router = Router(registry, {"judge": task}, stats)
    seen = []

    class Spy(BudgetLedger):
        def reserve(self, task, tags, estimate_usd, model=None):
            seen.append(estimate_usd)
            return super().reserve(task, tags, estimate_usd, model)

    ex = executor(router, FakeProvider({"fiction/cheap": ok()}), Spy())
    ex.call("judge", MESSAGES, prompt_tokens=10, slice="long")
    ex.call("judge", MESSAGES, prompt_tokens=10)
    cheap = registry.get("fiction/cheap")
    assert seen == [cheap.cost(10, 900), cheap.cost(10, 200)]


def test_a_fallback_holds_again_and_an_error_settles_at_zero(router, registry, unit):
    mid = registry.get("fiction/mid").cost(1000, 200)            # 0.0042
    ledger = BudgetLedger([Budget("r", mid, "refuse")])
    monitor = Monitor()
    ex = executor(router, FakeProvider({"fiction/cheap": fail, "fiction/mid": ok()}), ledger,
                  monitor)
    assert ex.call("judge", MESSAGES, prompt_tokens=1000).model == "fiction/mid"
    assert ledger.spent_usd("r") == mid and ledger.held_usd("r") == 0.0
    assert [r["outcome"] for r in monitor.records] == ["error", "ok"]


def test_a_refused_fallback_ends_the_call_with_the_attempts_before_it(router, registry, unit):
    mid = registry.get("fiction/mid").cost(1000, 200)
    ledger = BudgetLedger([Budget("r", mid / 2, "refuse")])      # fits cheap's 0.0014 only
    monitor = Monitor()
    provider = FakeProvider({"fiction/cheap": fail, "fiction/mid": ok(), "fiction/best": ok()})
    ex = executor(router, provider, ledger, monitor)
    with pytest.raises(BudgetExceeded) as caught:
        ex.call("judge", MESSAGES, prompt_tokens=1000)
    exc = caught.value
    assert exc.model == "fiction/mid" and exc.estimate_usd == mid
    assert [a.outcome for a in exc.attempts] == ["error"]
    assert [(r["model"], r["final"]) for r in monitor.records] == [("fiction/cheap", False)]
    assert ledger.spent_usd("r") == 0.0 and ledger.held_usd("r") == 0.0


def test_a_call_in_flight_holds_its_estimate_against_another(router, unit):
    ledger = BudgetLedger([Budget("pool", 1.5 * unit, "refuse")])
    other = executor(router, FakeProvider({"fiction/cheap": ok()}), ledger)
    refused = []

    def nested(messages):
        with pytest.raises(BudgetExceeded) as caught:
            other.call("judge", MESSAGES, prompt_tokens=1000)
        refused.append(caught.value)
        return Completion("ok", 1000, 200)

    executor(router, FakeProvider({"fiction/cheap": nested}), ledger).call(
        "judge", MESSAGES, prompt_tokens=1000)
    assert refused[0].held_usd == unit and refused[0].spent_usd == 0.0
    assert ledger.spent_usd("pool") == unit and ledger.held_usd("pool") == 0.0


def test_a_provider_bug_releases_the_hold(router, unit):
    ledger = BudgetLedger([Budget("r", 2 * unit, "refuse")])

    def bug(messages):
        raise KeyError("not an outage")

    with pytest.raises(KeyError):
        executor(router, FakeProvider({"fiction/cheap": bug}), ledger).call(
            "judge", MESSAGES, prompt_tokens=1000)
    assert ledger.spent_usd("r") == 0.0 and ledger.held_usd("r") == 0.0


def test_per_tool_and_pooled_scopes_are_independent(router, unit):
    ledger = BudgetLedger([Budget("tool-a", unit, "refuse", tags={"tool": "a"}),
                           Budget("pool", 4 * unit, "warn")])
    ex = executor(router, FakeProvider({"fiction/cheap": ok()}), ledger)
    for tool in ("a", "b", "b"):
        ex.call("judge", MESSAGES, prompt_tokens=1000, tags={"tool": tool})
    with pytest.raises(BudgetExceeded) as caught:
        ex.call("judge", MESSAGES, prompt_tokens=1000, tags={"tool": "a"})
    assert caught.value.budget.name == "tool-a"
    ex.call("judge", MESSAGES, prompt_tokens=1000, tags={"tool": "b"})
    assert ledger.spent_usd("tool-a") == unit
    assert ledger.spent_usd("pool") == unit + unit + unit + unit
    assert [(e["budget"], e["share"]) for e in ledger.events] == [
        ("pool", 0.5), ("pool", 0.8), ("pool", 1.0)]


def test_a_delegated_call_counts_to_the_run_budget_with_its_parent(router):
    ledger = BudgetLedger([Budget("run", 1.0, "refuse", tags={"run": "r1"})])
    monitor = Monitor()
    ex = executor(router, FakeProvider({"fiction/cheap": ok(), "fiction/best": ok(300, 40)}),
                  ledger, monitor)
    ex.call("judge", MESSAGES, prompt_tokens=1000, tags={"run": "r1"}, exclude_models=[
        "fiction/cheap", "fiction/mid"])
    decision = router.decide_delegation("judge", "fiction/best", "cost_effective",
                                        context_tokens=5000, brief_tokens=100, result_tokens=20)
    assert decision.mode == "delegate"
    ex.call_delegated(decision, [{"role": "user", "content": "brief"}], tags={"run": "r1"})
    assert monitor.records[1]["tags"] == {"run": "r1", "delegated": "true",
                                          "parent": "fiction/best"}
    assert ledger.spent_usd("run") == math.fsum(r["cost_usd"] for r in monitor.records)
    assert ledger.spent_usd("run") > 0


CHEAP, BEST = "fiction/cheap", "fiction/best"
PROC_REGISTRY = Registry([Model(CHEAP, "fam-b", 0.1, 0.2, 10_000),
                          Model(BEST, "fam-c", 10.0, 30.0, 100_000)])


def poll(value, call):
    text = call([{"role": "user", "content": "summarize: hi"}])   # 13 characters, 4 tokens
    return ProcedureResult("shaped " + text, tool_calls=3, tool_cost_usd=0.0005)


POLL = Procedure("poll", "v1", poll, max_model_calls=2, max_tool_calls=5, model=CHEAP)


def proc_router():
    stats = Stats()
    stats.add("t", BEST, 98, 100)
    stats.add("t", POLL.id, 95, 100, cost_usd=0.02)
    return Router(PROC_REGISTRY, {"t": Task("t", bar=0.8, min_samples=10)}, stats)


def test_a_procedure_holds_its_model_call_and_charges_its_tool_cost():
    seen = []

    class Spy(BudgetLedger):
        def reserve(self, task, tags, estimate_usd, model=None):
            seen.append((estimate_usd, model))
            return super().reserve(task, tags, estimate_usd, model)

    ledger = Spy([Budget("all", 1.0, "refuse")])
    monitor = Monitor()
    ex = executor(proc_router(), FakeProvider({CHEAP: ok(4000, 1000)}), ledger, monitor)
    result = ex.call("t", [{"role": "user", "content": "hi"}], procedures=[POLL])
    assert result.model == POLL.id
    assert seen == [(PROC_REGISTRY.get(CHEAP).cost(4, 200), CHEAP)]
    costs = [r["cost_usd"] for r in monitor.records]
    assert costs == [PROC_REGISTRY.get(CHEAP).cost(4000, 1000), 0.0005]
    assert ledger.spent_usd("all") == math.fsum(costs)


def test_a_refused_procedure_call_propagates_after_the_run_with_no_record():
    ledger = BudgetLedger([Budget("tiny", 1e-9, "refuse")])
    monitor = Monitor()
    calls = []
    ex = executor(proc_router(), FakeProvider({CHEAP: ok(calls=calls), BEST: ok()}), ledger,
                  monitor)
    with pytest.raises(BudgetExceeded) as caught:
        ex.call("t", [{"role": "user", "content": "hi"}], procedures=[POLL])
    assert caught.value.model == CHEAP and caught.value.attempts == ()
    assert calls == [] and monitor.records == []


# --- exports, spec and the note -----------------------------------------------------------

def test_the_exports_follow_procedure_limit_error():
    names = model_routing.__all__
    at = names.index("ProcedureLimitError")
    assert names[at + 1:at + 5] == ["Budget", "BudgetLedger", "BudgetExceeded", "load_budgets"]
    assert model_routing.budget.__file__ == str(ROOT / "model_routing" / "budget.py")


def test_design_specifies_the_ledger_and_lifts_part_of_the_deferral():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert text.count("### 4.6 Budgets (`budget.py`, v1.595, row B1a)") == 1
    layout = text[text.index("## 3. "):text.index("## 4. ")]
    assert "  budget.py       Budget, BudgetLedger, BudgetExceeded, load_budgets (v1.595, 4.6)" in layout
    seven = text[text.index("## 7. "):text.index("## 8. ")]
    assert seven.count("- v1.595 budgets (row B1a): ") == 1
    fourteen = text[text.index("## 14. "):text.index("## 15. ")]
    assert "- Online drift detection beyond re-calibrating from audited results; budgets and alerts\n" \
        not in fourteen
    assert fourteen.count("beyond v1.595's in-process ledger (4.6)") == 1
    last = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()[-1]
    assert last.startswith("- v1.595 (2026-11-22): ") and "row B1a" in last


def test_the_note_states_the_budget_as_shipped_and_what_stays_planned():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert "no budget today" not in note and "It has no budget and no rate limit." not in note
    lines = [line for line in note.splitlines() if line.startswith("- In this library: ")]
    spend = [line for line in lines if "`BudgetExceeded`" in line]
    assert len(spend) == 1
    assert "The change still planned: a window of a day or a month" in spend[0]
    assert sum("It has an in-process budget (v1.595) but no rate limit." in line
               for line in lines) == 1
