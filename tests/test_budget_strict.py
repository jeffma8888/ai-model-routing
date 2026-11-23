"""Strict budgets: a billing bound held before each provider call (DESIGN 4.6 and 7 v1.597, row B1c)."""

import json
from pathlib import Path

import pytest
import model_routing
from model_routing import (
    Budget, BudgetExceeded, BudgetLedger, Completion, Executor, FakeProvider, Model, Monitor,
    PriceTier, Procedure, ProcedureResult, Registry, Router, Stats, Task, Variant, load_budgets,
)

ROOT = Path(__file__).resolve().parent.parent
MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, BEST = "fiction/cheap", "fiction/best"
CAPPED, BEST_CAPPED = "fiction/cheap@capped", "fiction/best@capped"


def attempts(monitor):
    """The monitor's attempt records: from v1.598 a ledger also writes budget records (8.1)."""
    return [rec for rec in monitor.records if "budget_event" not in rec]


def model(model_id=CHEAP, price_in=1.0, price_out=2.0, options=None, **kwargs):
    family = "small" if model_id.startswith(CHEAP) else "large"
    variant = None
    if options is not None:
        variant = Variant(model_id.split("@", 1)[1], provider_options=options)
    return Model(id=model_id, family=family, price_in=price_in, price_out=price_out,
                 context_window=8000, variant=variant, **kwargs)


REGISTRY = Registry([
    model(), model(CAPPED, options={"max_tokens": 500}),
    model(BEST, 10.0, 20.0), model(BEST_CAPPED, 10.0, 20.0, options={"max_tokens": 500}),
])


def bound():
    return model_routing.billing_bound


def ok(input_tokens=1000, output_tokens=200, calls=None, during=None):
    def script(messages):
        if calls is not None:
            calls.append(messages)
        if during is not None:
            during()
        return Completion("ok", input_tokens, output_tokens)
    return script


def router(*measured):
    stats = Stats()
    for model_id, successes in measured:
        stats.add("t", model_id, successes, 100)
    return Router(REGISTRY, {"t": Task("t", bar=0.7, min_samples=10)}, stats)


def make(route, provider, ledger, monitor=None):
    ticks = iter(float(i) for i in range(1000))
    return Executor(route, provider, monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: "2026-11-23T00:00:00Z", id_factory=lambda: "call-1",
                    ledger=ledger)


# --- Budget.strict and load_budgets -----------------------------------------------------

def test_strict_is_false_unless_set():
    assert Budget("a", 1.0, "refuse").strict is False
    assert Budget("a", 1.0, "refuse", strict=True).strict is True
    assert Budget("a", 1.0, "downgrade", strict=True).strict is True


@pytest.mark.parametrize("kwargs", [
    {"mode": "warn", "strict": True}, {"strict": 1}, {"strict": 0}, {"strict": "yes"},
    {"strict": None},
])
def test_a_bad_strict_raises(kwargs):
    fields = dict({"name": "b", "limit_usd": 1.0, "mode": "refuse"}, **kwargs)
    with pytest.raises(ValueError):
        Budget(**fields)


def test_a_warn_budget_may_say_strict_false():
    assert Budget("w", 1.0, "warn", strict=False).strict is False


def test_load_budgets_reads_strict(tmp_path):
    path = tmp_path / "budgets.json"
    path.write_text(json.dumps({"budgets": [
        {"name": "cap", "limit_usd": 2, "mode": "refuse", "strict": True},
        {"name": "soft", "limit_usd": 2, "mode": "refuse", "strict": False},
    ]}), encoding="utf-8")
    assert load_budgets(path) == (Budget("cap", 2.0, "refuse", strict=True),
                                  Budget("soft", 2.0, "refuse"))


# --- billing_bound -----------------------------------------------------------------------

def test_a_model_without_an_output_maximum_has_no_bound():
    assert bound()(REGISTRY.get(CHEAP)) is None


def test_the_bound_prices_the_output_maximum_and_the_input_the_window_leaves():
    capped = REGISTRY.get(CAPPED)
    assert bound()(capped) == capped.cost(7500, 500) == pytest.approx(0.0085)


def test_the_largest_of_the_three_keys_caps_the_output():
    m = model(CAPPED, options={"max_tokens": 400, "max_completion_tokens": 1000})
    assert bound()(m) == m.cost(7000, 1000)
    m = model(CAPPED, options={"max_output_tokens": 300})
    assert bound()(m) == m.cost(7700, 300)


@pytest.mark.parametrize("options", [
    {"max_tokens": True}, {"max_tokens": 0}, {"max_tokens": 1.5}, {"max_tokens": "500"},
    {"max_tokens": 500, "max_output_tokens": None}, {"temperature": 0},
])
def test_an_output_maximum_that_is_no_positive_int_gives_no_bound(options):
    assert bound()(model(CAPPED, options=options)) is None


def test_a_maximum_past_the_window_leaves_no_input():
    m = model(CAPPED, options={"max_tokens": 9000})
    assert bound()(m) == m.cost(0, 9000) == pytest.approx(0.018)


def test_a_cheaper_tier_never_lowers_the_bound():
    cheaper = model(CAPPED, options={"max_tokens": 500},
                    price_tiers=(PriceTier(4000, 0.5, 1.0),))
    assert bound()(cheaper) == cheaper.cost(4000, 500) == pytest.approx(0.005)
    dearer = model(CAPPED, options={"max_tokens": 500}, price_tiers=(PriceTier(4000, 2.0, 4.0),))
    assert bound()(dearer) == dearer.cost(7500, 500) == pytest.approx(0.017)


def test_a_dearer_cache_price_raises_the_bound():
    write = model(CAPPED, options={"max_tokens": 500}, price_cache_write=3.0)
    assert bound()(write) == write.cost(7500, 500, cache_write_tokens=7500)
    read = model(CAPPED, options={"max_tokens": 500}, price_cached_in=5.0, price_cache_write=0.1)
    assert bound()(read) == read.cost(7500, 500, cached_input_tokens=7500)
    cheap = model(CAPPED, options={"max_tokens": 500}, price_cached_in=0.1)
    assert bound()(cheap) == cheap.cost(7500, 500)


# --- the ledger ---------------------------------------------------------------------------

def test_a_strict_budget_holds_the_bound_and_others_the_estimate():
    ledger = BudgetLedger([Budget("s", 0.01, "refuse", strict=True), Budget("w", 1.0, "warn")])
    hold = ledger.reserve("t", {}, 0.001, CAPPED, bound_usd=0.008)
    assert ledger.held_usd("s") == 0.008 and ledger.held_usd("w") == 0.001
    with pytest.raises(BudgetExceeded) as caught:
        ledger.reserve("t", {}, 0.001, CAPPED, bound_usd=0.008)
    assert caught.value.budget.name == "s" and caught.value.estimate_usd == 0.008
    assert caught.value.unbounded is False
    ledger.settle(hold, 0.002)
    assert ledger.spent_usd("s") == 0.002 and ledger.spent_usd("w") == 0.002
    assert ledger.held_usd("s") == 0.0 and ledger.held_usd("w") == 0.0


def test_a_strict_budget_refuses_a_call_with_no_bound_and_holds_nothing():
    for mode in ("refuse", "downgrade"):
        ledger = BudgetLedger([Budget("w", 1.0, "warn"), Budget("s", 1.0, mode, strict=True)])
        with pytest.raises(BudgetExceeded) as caught:
            ledger.reserve("t", {}, 0.001, CHEAP)
        assert caught.value.unbounded is True and caught.value.budget.mode == mode
        assert caught.value.model == CHEAP and "strict" in str(caught.value)
        assert ledger.held_usd("w") == 0.0 and ledger.held_usd("s") == 0.0


def test_a_budget_out_of_scope_or_not_strict_ignores_the_bound():
    ledger = BudgetLedger([Budget("s", 1e-9, "refuse", task="other", strict=True),
                           Budget("r", 0.01, "refuse")])
    hold = ledger.reserve("t", {}, 0.001, CHEAP, bound_usd=None)
    assert ledger.held_usd("r") == 0.001
    ledger.settle(hold, 0.001)
    hold = ledger.reserve("t", {}, 0.001, CHEAP, bound_usd=5.0)
    assert ledger.held_usd("r") == 0.001


def test_a_refuse_budget_still_refuses_before_a_strict_downgrade_one():
    ledger = BudgetLedger([Budget("d", 1.0, "downgrade", strict=True),
                           Budget("r", 1e-9, "refuse")])
    with pytest.raises(BudgetExceeded) as caught:
        ledger.reserve("t", {}, 0.001, CHEAP)
    assert caught.value.budget.name == "r" and caught.value.unbounded is False


@pytest.mark.parametrize("value", [-1.0, True, float("nan"), "0.1"])
def test_a_bad_bound_raises(value):
    ledger = BudgetLedger([Budget("s", 1.0, "refuse", strict=True)])
    with pytest.raises(ValueError):
        ledger.reserve("t", {}, 0.001, CAPPED, bound_usd=value)


def test_an_unknown_cost_settles_at_the_strict_bound_and_zero_elsewhere():
    ledger = BudgetLedger([Budget("s", 1.0, "refuse", strict=True), Budget("w", 1.0, "warn"),
                           Budget("r", 1.0, "refuse")])
    hold = ledger.reserve("t", {}, 0.001, CAPPED, bound_usd=0.6)
    with pytest.raises(ValueError):
        ledger.settle(hold, None)
    ledger.settle_unpriced(hold)
    assert ledger.spent_usd("s") == 0.6
    assert ledger.spent_usd("w") == 0.0 and ledger.spent_usd("r") == 0.0
    assert ledger.events == () and ledger.held_usd("s") == 0.0
    with pytest.raises(ValueError):
        ledger.settle_unpriced(hold)


def test_an_unpriced_strict_hold_settles_in_its_window():
    ledger = BudgetLedger([Budget("s", 1.0, "refuse", window="day", strict=True)])
    hold = ledger.reserve("t", {}, 0.001, CAPPED, at="2026-11-23T23:59:59Z", bound_usd=0.5)
    ledger.settle_unpriced(hold)
    assert ledger.spent_usd("s", at="2026-11-23T12:00:00Z") == 0.5
    assert ledger.spent_usd("s", at="2026-11-24T00:00:01Z") == 0.0


# --- the executor ------------------------------------------------------------------------

def test_a_strict_refuse_budget_refuses_an_unbounded_route_before_any_call():
    ledger = BudgetLedger([Budget("s", 1.0, "refuse", strict=True)])
    calls, monitor = [], Monitor()
    with pytest.raises(BudgetExceeded) as caught:
        make(router((CHEAP, 95)), FakeProvider({CHEAP: ok(calls=calls)}), ledger,
             monitor).call("t", MESSAGES)
    assert caught.value.unbounded is True and caught.value.model == CHEAP
    assert calls == [] and attempts(monitor) == [] and ledger.spent_usd("s") == 0.0


def test_a_strict_budget_holds_the_bound_during_the_call_and_spends_the_cost():
    ledger = BudgetLedger([Budget("s", 1.0, "refuse", strict=True), Budget("w", 1.0, "warn")])
    seen = []
    during = lambda: seen.append((ledger.held_usd("s"), ledger.held_usd("w")))  # noqa: E731
    result = make(router((CAPPED, 95)), FakeProvider({CAPPED: ok(during=during)}),
                  ledger).call("t", MESSAGES, prompt_tokens=1000)
    assert result.model == CAPPED
    capped = REGISTRY.get(CAPPED)
    assert seen == [(capped.cost(7500, 500), capped.cost(1000, 200))]
    assert ledger.spent_usd("s") == capped.cost(1000, 200) == ledger.spent_usd("w")
    assert ledger.held_usd("s") == 0.0


def test_a_strict_refuse_budget_refuses_when_the_bound_does_not_fit():
    capped = REGISTRY.get(CAPPED)
    ledger = BudgetLedger([Budget("s", capped.cost(7500, 500) * 0.99, "refuse", strict=True)])
    with pytest.raises(BudgetExceeded) as caught:
        make(router((CAPPED, 95)), FakeProvider({CAPPED: ok()}), ledger).call(
            "t", MESSAGES, prompt_tokens=1000)
    assert caught.value.unbounded is False and caught.value.estimate_usd == capped.cost(7500, 500)


def test_a_strict_downgrade_budget_moves_an_unbounded_entry_to_a_bounded_one():
    ledger = BudgetLedger([Budget("s", 1.0, "downgrade", strict=True)])
    monitor = Monitor()
    route = router((CHEAP, 95), (BEST_CAPPED, 99))
    assert route.select("t").primary == CHEAP
    result = make(route, FakeProvider({CHEAP: ok(), BEST_CAPPED: ok()}), ledger,
                  monitor).call("t", MESSAGES)
    assert result.model == BEST_CAPPED
    assert [r["budget_moves"] for r in attempts(monitor)] == [
        [{"entry": CHEAP, "model": CHEAP, "budget": "s"}]]


def _poll(seen):
    def poll(value, call):
        seen.append(value)
        return ProcedureResult("shaped " + call([{"role": "user", "content": "hi"}]))
    return Procedure("poll", "v1", poll, max_model_calls=2, max_tool_calls=5, model=CAPPED)


def _procedure_route(proc):
    stats = Stats()
    stats.add("t", BEST_CAPPED, 98, 100)
    stats.add("t", proc.id, 95, 100, cost_usd=0.0001)
    route = Router(REGISTRY, {"t": Task("t", bar=0.8, min_samples=10)}, stats)
    decision = route.select("t", procedures=[proc])
    assert (decision.primary, decision.fallbacks) == (proc.id, (BEST_CAPPED,))
    return route


def test_a_strict_refuse_budget_refuses_a_procedure_entry_before_its_run():
    seen = []
    proc = _poll(seen)
    ledger = BudgetLedger([Budget("s", 1.0, "refuse", strict=True)])
    with pytest.raises(BudgetExceeded) as caught:
        make(_procedure_route(proc), FakeProvider({CAPPED: ok(), BEST_CAPPED: ok()}),
             ledger).call("t", MESSAGES, procedures=[proc])
    assert caught.value.unbounded is True and caught.value.model == proc.id
    assert caught.value.estimate_usd == 0.0 and caught.value.attempts == ()
    assert caught.value.decision is not None and caught.value.decision.primary == proc.id
    assert seen == [] and ledger.spent_usd("s") == 0.0


def test_a_strict_downgrade_budget_moves_a_procedure_entry_on():
    seen = []
    proc = _poll(seen)
    ledger = BudgetLedger([Budget("s", 1.0, "downgrade", strict=True)])
    monitor = Monitor()
    result = make(_procedure_route(proc), FakeProvider({CAPPED: ok(), BEST_CAPPED: ok()}),
                  ledger, monitor).call("t", MESSAGES, procedures=[proc])
    assert result.model == BEST_CAPPED and seen == []
    assert [r["budget_moves"] for r in attempts(monitor)] == [
        [{"entry": proc.id, "model": proc.id, "budget": "s"}]]


def test_a_budget_that_is_not_strict_meets_a_procedure_entry_as_in_v1_596():
    seen = []
    proc = _poll(seen)
    ledger = BudgetLedger([Budget("s", 1.0, "refuse", task="other", strict=True),
                           Budget("r", 0.001, "refuse")])
    ledger.charge("t", {}, 0.002)  # past its limit before the call
    with pytest.raises(BudgetExceeded) as caught:
        make(_procedure_route(proc), FakeProvider({CAPPED: ok(), BEST_CAPPED: ok()}),
             ledger).call("t", MESSAGES, procedures=[proc])
    assert caught.value.budget.name == "r" and caught.value.unbounded is False
    assert len(seen) == 1  # the run started, as in v1.596, and its model call was refused


class _OddCompletion:
    text, input_tokens, output_tokens = "ok", 100, 10
    cached_input_tokens, cache_write_tokens = 500, None  # a count Model.cost refuses


class _OddProvider:
    def complete(self, model_id, messages, timeout_s, options=None):
        return _OddCompletion()


def test_a_call_whose_cost_raises_settles_at_the_strict_bound():
    ledger = BudgetLedger([Budget("s", 1.0, "refuse", strict=True), Budget("w", 1.0, "warn")])
    with pytest.raises(ValueError):
        make(router((CAPPED, 95)), _OddProvider(), ledger).call("t", MESSAGES)
    assert ledger.spent_usd("s") == REGISTRY.get(CAPPED).cost(7500, 500)
    assert ledger.spent_usd("w") == 0.0 and ledger.held_usd("s") == 0.0


class _Spy(BudgetLedger):
    def __init__(self, budgets):
        super().__init__(budgets)
        self.calls = []

    def reserve(self, *args, **kwargs):
        self.calls.append(("reserve", args, kwargs))
        return super().reserve(*args, **kwargs)

    def settle(self, hold, cost_usd):
        self.calls.append(("settle", cost_usd))
        return super().settle(hold, cost_usd)

    def settle_unpriced(self, hold):
        self.calls.append(("settle_unpriced",))
        return super().settle_unpriced(hold)


def test_without_a_strict_budget_the_executor_calls_the_ledger_as_in_v1_596():
    spy = _Spy([Budget("r", 1.0, "refuse"), Budget("w", 1.0, "warn")])
    with pytest.raises(ValueError):
        make(router((CAPPED, 95)), _OddProvider(), spy).call("t", MESSAGES, prompt_tokens=1000)
    capped = REGISTRY.get(CAPPED)
    assert spy.calls == [("reserve", ("t", {}, capped.cost(1000, 200), CAPPED), {}),
                         ("settle", 0.0)]


def test_a_strict_budget_out_of_scope_lets_an_unbounded_call_run():
    ledger = BudgetLedger([Budget("s", 1.0, "refuse", task="other", strict=True)])
    assert make(router((CHEAP, 95)), FakeProvider({CHEAP: ok()}), ledger).call(
        "t", MESSAGES).model == CHEAP


# --- exports and spec ------------------------------------------------------------------------

def test_billing_bound_follows_load_budgets():
    names = model_routing.__all__
    assert names[names.index("load_budgets") + 1] == "billing_bound"
    assert model_routing.billing_bound is model_routing.budget.billing_bound


def test_design_specifies_strict_budgets_and_defers_rows_b1e_and_b1f():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four = text[text.index("### 4.6 Budgets"):text.index("## 5. ")]
    assert four.count("  - v1.597 strict (row B1c): ") == 1
    assert "`max_tokens`, `max_completion_tokens` and `max_output_tokens`" in four
    assert ("- Not in this version: the README paragraph (row B1d); the crossings and refusals in "
            "the monitor log and `budget_used_pct` are v1.598's (7 and 8, row B1e), and the "
            "`demo --budgets FILE` option with exit code 4 on a refusal v1.599's (10 and 11, row "
            "B1f).") in four   # v1.598 and v1.599 restate it
    seven = text[text.index("## 7. "):text.index("## 8. ")]
    assert seven.count("- v1.597 strict (row B1c): ") == 1
    fourteen = text[text.index("## 14. "):text.index("## 15. ")]
    assert fourteen.count("v1.597's strict caps and v1.598's budget records") == 1
    lines = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    [line] = [l for l in lines if l.startswith("- v1.597 (2026-11-23): ")]
    assert "row B1c" in line
