"""Shadow calls (DESIGN 4.2, 7 and 8.1 v1.607, row CANARY1a)."""

import dataclasses
import inspect
import json
import math

import pytest
from model_routing import (
    AllModelsFailed, Budget, BudgetLedger, Completion, Executor, FakeProvider, Model, Monitor,
    ProviderError, Registry, Router, Stats, Task, load_tasks,
)
from model_routing.demo import _tasks_json

MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, MID, BEST, SMALL = "fiction/cheap", "fiction/mid", "fiction/best", "fiction/small"
REGISTRY = Registry([
    Model(CHEAP, "small", 1.0, 2.0, 8000),
    Model(MID, "medium", 3.0, 6.0, 8000),
    Model(BEST, "large", 10.0, 20.0, 8000),
    Model(SMALL, "tiny", 0.5, 1.0, 600),
])


def router(**fields):
    """cost_effective routes cheap first; the default shadow route is best (bound highest)."""
    task = Task("judge", bar=0.7, min_samples=10, **fields)
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (MID, (95, 100)),
                                          (BEST, (100, 100)), (SMALL, (50, 100))):
        stats.add(task.name, model_id, successes, trials)
    return Router(REGISTRY, {task.name: task}, stats)


def answer(text):
    return lambda messages: Completion(text, 1000, 200)


def provider(**overrides):
    script = {CHEAP: answer("cheap"), MID: answer("mid"), BEST: answer("best")}
    script.update(overrides)
    return FakeProvider({k: v for k, v in script.items() if v is not None})


class Draws:
    """An injected random source: returns the given values in order, counting its calls."""

    def __init__(self, *values):
        self.values, self.calls = list(values), 0

    def __call__(self):
        self.calls += 1
        return self.values.pop(0)


def never():
    raise AssertionError("random was called")


def make(route, prov, monitor, random=None, ledger=None):
    ticks = iter(float(i) for i in range(10_000))
    ids = iter(f"call-{i}" for i in range(10_000))
    kwargs = {} if random is None else {"random": random}
    return Executor(route, prov, monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: "2026-11-23T00:00:00Z", id_factory=lambda: next(ids),
                    ledger=ledger, **kwargs)


def attempts_of(records):
    return [rec for rec in records if "budget_event" not in rec]


# --- 4.2 the fields --------------------------------------------------------------------------

def test_the_fields_follow_failure_policy_with_their_defaults():
    names = [f.name for f in dataclasses.fields(Task)]
    assert names[-3:] == ["failure_policy", "shadow_rate", "shadow_route"]
    task = Task("t", 0.5)
    assert task.shadow_rate == 0.0 and task.shadow_route is None


@pytest.mark.parametrize("value", [True, False, -0.1, 1.5, math.nan, math.inf, -math.inf,
                                   10 ** 400, "0.5", None])  # 10 ** 400 overflows a float
def test_a_bad_shadow_rate_is_a_value_error_naming_the_task(value):
    with pytest.raises(ValueError, match="'t'"):
        Task("t", 0.5, shadow_rate=value)


@pytest.mark.parametrize("value", [0, 1, 0.25, 1.0, 0.0])
def test_a_shadow_rate_in_the_closed_unit_interval_is_kept(value):
    assert Task("t", 0.5, shadow_rate=value).shadow_rate == value


@pytest.mark.parametrize("value", ["", 3, (BEST,), b"x"])
def test_a_bad_shadow_route_is_a_value_error_naming_the_task(value):
    with pytest.raises(ValueError, match="'t'"):
        Task("t", 0.5, shadow_route=value)


def test_load_tasks_reads_the_fields_and_a_row_without_them_gets_the_defaults(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"tasks": [
        {"name": "a", "bar": 0.5, "shadow_rate": 0.1, "shadow_route": BEST},
        {"name": "b", "bar": 0.5, "shadow_route": None},
        {"name": "c", "bar": 0.5}]}), encoding="utf-8")
    tasks = load_tasks(path)
    assert (tasks["a"].shadow_rate, tasks["a"].shadow_route) == (0.1, BEST)
    assert (tasks["b"].shadow_rate, tasks["b"].shadow_route) == (0.0, None)
    assert (tasks["c"].shadow_rate, tasks["c"].shadow_route) == (0.0, None)
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "shadow_rate": 2}]}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="'a'"):
        load_tasks(path)


def test_the_demo_tasks_file_holds_each_key_only_when_it_is_not_its_default():
    plain = json.loads(_tasks_json(Task("t", 0.5)))["tasks"][0]
    assert "shadow_rate" not in plain and "shadow_route" not in plain
    shadowed = json.loads(_tasks_json(Task("t", 0.5, shadow_rate=0.2, shadow_route=BEST)))
    assert shadowed["tasks"][0]["shadow_rate"] == 0.2
    assert shadowed["tasks"][0]["shadow_route"] == BEST


def test_a_slice_takes_the_task_s_shadow_fields():
    task = Task("t", 0.5, slices={"deep": {"bar": 0.9}}, shadow_rate=0.3)
    with pytest.raises(ValueError):
        Task("t", 0.5, slices={"deep": {"shadow_rate": 0.9}})
    assert task.shadow_rate == 0.3


# --- 7 the random source -------------------------------------------------------------------

def test_random_is_the_last_parameter_and_defaults_to_none():
    params = list(inspect.signature(Executor).parameters.values())
    assert [p.name for p in params[-2:]] == ["ledger", "random"]
    assert params[-1].default is None


@pytest.mark.parametrize("value", [0.5, "random", 1])
def test_a_random_that_is_not_callable_is_a_value_error(value):
    with pytest.raises(ValueError, match="random"):
        Executor(router(), provider(), random=value)


# --- 7 the shadow ---------------------------------------------------------------------------

def test_rate_one_on_ten_calls_logs_twenty_attempts_ten_of_them_shadow():
    monitor = Monitor()
    prov = provider()
    executor = make(router(shadow_rate=1.0), prov, monitor, random=Draws(*[0.0] * 10))
    results = [executor.call("judge", MESSAGES) for _ in range(10)]
    records = monitor.records
    assert len(records) == 20
    assert sum(rec["shadow"] for rec in records) == 10
    for k, result in enumerate(results):
        routed, shadow = records[2 * k], records[2 * k + 1]
        assert result.text == "cheap" and result.model == CHEAP and len(result.attempts) == 1
        assert result.call_id == routed["call_id"] == f"call-{2 * k}"
        assert (routed["model"], routed["shadow"], routed["pair_id"]) == (CHEAP, False, result.call_id)
        assert (shadow["model"], shadow["shadow"], shadow["pair_id"]) == (BEST, True, result.call_id)
        assert shadow["call_id"] == f"call-{2 * k + 1}" != routed["call_id"]
        assert (shadow["attempt"], shadow["final"], shadow["outcome"]) == (0, True, "ok")
        assert shadow["tags"] == {"shadow": "true"} and routed["tags"] == {}
    assert [model for model, _ in prov.calls] == [CHEAP, BEST] * 10
    assert all(messages is MESSAGES for _, messages in prov.calls)


def test_rate_zero_never_draws_and_writes_the_records_of_v1_606():
    plain, shadowless = Monitor(), Monitor()
    make(router(), provider(), plain).call("judge", MESSAGES, tags={"shadow": "yes"})
    make(router(shadow_route=BEST), provider(), shadowless, random=never).call(
        "judge", MESSAGES, tags={"shadow": "yes"})
    assert plain.records == shadowless.records and len(plain.records) == 1
    assert "pair_id" not in plain.records[0] and "shadow" not in plain.records[0]


def test_the_two_keys_follow_slice_in_order():
    base, shadowed = Monitor(), Monitor()
    make(router(), provider(), base).call("judge", MESSAGES, tags={"team": "a"})
    make(router(shadow_rate=1.0), provider(), shadowed, random=Draws(0.5)).call(
        "judge", MESSAGES, tags={"team": "a"})
    keys = list(base.records[0])
    at = keys.index("slice") + 1
    assert list(shadowed.records[0]) == keys[:at] + ["pair_id", "shadow"] + keys[at:]
    assert list(shadowed.records[1]) == list(shadowed.records[0])
    assert shadowed.records[1]["tags"] == {"team": "a", "shadow": "true"}


def test_a_shadow_provider_error_never_fails_the_routed_call():
    monitor = Monitor()
    result = make(router(shadow_rate=1.0), provider(**{BEST: None}), monitor,
                  random=Draws(0.0)).call("judge", MESSAGES)
    assert result.text == "cheap" and len(result.attempts) == 1
    shadow = monitor.records[1]
    assert (shadow["shadow"], shadow["outcome"], shadow["cost_usd"]) == (True, "error", 0.0)
    assert shadow["error"].startswith("ProviderError")


def test_an_invalid_shadow_output_never_fails_the_routed_call():
    monitor = Monitor()
    result = make(router(shadow_rate=1.0), provider(), monitor, random=Draws(0.0)).call(
        "judge", MESSAGES, validate=lambda text: text == "cheap")
    assert result.text == "cheap"
    shadow = monitor.records[1]
    assert (shadow["outcome"], shadow["error"]) == ("invalid", "validation failed")
    assert shadow["cost_usd"] == REGISTRY.get(BEST).cost(1000, 200)


def test_a_bug_in_the_shadow_s_provider_call_propagates():
    def bug(messages):
        raise RuntimeError("bug")
    with pytest.raises(RuntimeError, match="bug"):
        make(router(shadow_rate=1.0), provider(**{BEST: bug}), Monitor(),
             random=Draws(0.0)).call("judge", MESSAGES)


@pytest.mark.parametrize("mode", ["refuse", "downgrade"])
def test_a_budget_refusal_of_the_shadow_never_fails_the_routed_call(mode):
    monitor = Monitor()
    ledger = BudgetLedger([Budget("shadows", 0.001, mode, tags={"shadow": "true"})])
    result = make(router(shadow_rate=1.0), provider(), monitor, random=Draws(0.0),
                  ledger=ledger).call("judge", MESSAGES)
    assert result.text == "cheap"
    assert len(monitor.records) == 2
    routed, refused = monitor.records
    assert routed["model"] == CHEAP and routed["pair_id"] == "call-0"
    assert refused["budget_event"] == "refused" and refused["model"] == BEST
    assert (refused["call_id"], refused["pair_id"], refused["shadow"]) == ("call-1", "call-0", True)
    assert refused["tags"] == {"shadow": "true"}
    assert ledger.spent_usd("shadows") == 0.0


def test_the_ledger_holds_the_shadow_under_its_shadow_tag():
    ledger = BudgetLedger([Budget("all", 100.0, "refuse"),
                           Budget("shadows", 100.0, "warn", tags={"shadow": "true"})])
    make(router(shadow_rate=1.0), provider(), Monitor(), random=Draws(0.0),
         ledger=ledger).call("judge", MESSAGES)
    cheap, best = REGISTRY.get(CHEAP).cost(1000, 200), REGISTRY.get(BEST).cost(1000, 200)
    assert ledger.spent_usd("shadows") == best
    assert ledger.spent_usd("all") == cheap + best


def test_a_primary_that_is_the_shadow_route_draws_nothing():
    monitor = Monitor()
    make(router(shadow_rate=1.0), provider(), monitor, random=never).call(
        "judge", MESSAGES, flavor="cost_blind")
    assert [rec["model"] for rec in monitor.records] == [BEST]
    assert "pair_id" not in monitor.records[0]


def test_a_named_shadow_route_is_used_and_need_not_clear_the_bar():
    monitor = Monitor()
    route = router(shadow_rate=1.0, shadow_route=MID)
    make(route, provider(), monitor, random=Draws(0.0)).call("judge", MESSAGES)
    assert [rec["model"] for rec in monitor.records] == [CHEAP, MID]
    monitor = Monitor()
    below = router(shadow_rate=1.0, shadow_route=SMALL)  # 50 of 100, under the bar
    make(below, provider(**{SMALL: answer("small")}), monitor, random=Draws(0.0)).call(
        "judge", MESSAGES)
    assert [rec["model"] for rec in monitor.records] == [CHEAP, SMALL]
    assert monitor.records[1]["outcome"] == "ok"


def test_a_shadow_route_outside_the_registry_is_a_value_error_before_any_call():
    monitor, prov = Monitor(), provider()
    with pytest.raises(ValueError, match="fiction/none"):
        make(router(shadow_rate=0.5, shadow_route="fiction/none"), prov, monitor,
             random=never).call("judge", MESSAGES)
    assert prov.calls == [] and monitor.records == []


def test_a_caller_tag_named_shadow_is_a_value_error_before_any_call():
    monitor, prov = Monitor(), provider()
    with pytest.raises(ValueError, match="shadow"):
        make(router(shadow_rate=0.5), prov, monitor, random=never).call(
            "judge", MESSAGES, tags={"shadow": "true"})
    assert prov.calls == [] and monitor.records == []


def test_an_ineligible_shadow_route_draws_nothing():
    monitor = Monitor()
    make(router(shadow_rate=1.0, shadow_route=MID, exclude_families=("medium",)), provider(),
         monitor, random=never).call("judge", MESSAGES)
    assert [rec["model"] for rec in monitor.records] == [CHEAP]
    monitor = Monitor()
    make(router(shadow_rate=1.0, shadow_route=SMALL), provider(), monitor,
         random=never).call("judge", MESSAGES, prompt_tokens=1000)  # 600-token window
    assert [rec["model"] for rec in monitor.records] == [CHEAP]


def test_a_draw_below_the_rate_shadows_and_one_at_or_above_does_not():
    monitor = Monitor()
    draws = Draws(0.4, 0.6, 0.5)
    executor = make(router(shadow_rate=0.5), provider(), monitor, random=draws)
    for _ in range(3):
        executor.call("judge", MESSAGES)
    assert draws.calls == 3
    assert [rec["model"] for rec in monitor.records] == [CHEAP, BEST, CHEAP, CHEAP]
    assert ["pair_id" in rec for rec in monitor.records] == [True, True, False, False]


def test_no_default_shadow_route_when_no_model_passes():
    task = Task("judge", bar=0.99, min_samples=10, on_no_model="best_available",
                shadow_rate=1.0)
    stats = Stats()
    stats.add("judge", CHEAP, 50, 100)
    stats.add("judge", MID, 60, 100)
    monitor = Monitor()
    make(Router(REGISTRY, {"judge": task}, stats), provider(), monitor, random=never).call(
        "judge", MESSAGES)
    assert len(monitor.records) == 1 and "pair_id" not in monitor.records[0]


def test_a_routed_call_that_raises_sends_no_shadow_and_keeps_its_pair_keys():
    monitor, prov = Monitor(), provider(**{CHEAP: None, MID: None, BEST: None})
    task_router = router(shadow_rate=1.0, max_fallbacks=0)
    with pytest.raises(AllModelsFailed):
        make(task_router, prov, monitor, random=Draws(0.0)).call("judge", MESSAGES)
    assert [model for model, _ in prov.calls] == [CHEAP]
    assert [(rec["shadow"], rec["pair_id"]) for rec in monitor.records] == [(False, "call-0")]


def test_without_a_monitor_the_shadow_still_runs():
    prov = provider()
    result = make(router(shadow_rate=1.0), prov, None, random=Draws(0.0)).call(
        "judge", MESSAGES)
    assert result.text == "cheap" and [m for m, _ in prov.calls] == [CHEAP, BEST]


def test_the_budget_records_of_both_calls_carry_the_pair_keys_after_tags():
    monitor = Monitor()
    cheap = REGISTRY.get(CHEAP).cost(1000, 200)
    ledger = BudgetLedger([Budget("w", cheap, "warn")])
    make(router(shadow_rate=1.0), provider(), monitor, random=Draws(0.0),
         ledger=ledger).call("judge", MESSAGES)
    warns = [rec for rec in monitor.records if rec.get("budget_event") == "warn"]
    assert warns and all(list(rec)[:6] == ["ts", "call_id", "task", "tags", "pair_id", "shadow"]
                         for rec in warns)
    assert {(rec["call_id"], rec["shadow"]) for rec in warns} == {("call-0", False)}
    assert all(rec["pair_id"] == "call-0" for rec in monitor.records)
    assert [rec["shadow"] for rec in attempts_of(monitor.records)] == [False, True]


# --- review iter-456 must-fix 1 and 2, should-fix 1 and 2 ------------------------------------

def test_an_id_factory_that_repeats_the_call_s_id_raises_before_any_call():
    monitor, prov = Monitor(), provider()
    executor = Executor(router(shadow_rate=1.0), prov, monitor=monitor,
                        id_factory=lambda: "same", random=Draws(0.0))
    with pytest.raises(ValueError, match="same"):
        executor.call("judge", MESSAGES)
    assert prov.calls == [] and monitor.records == []
    plain = Executor(router(shadow_rate=0.5), provider(), monitor=Monitor(),
                     id_factory=lambda: "same", random=Draws(0.9))
    assert plain.call("judge", MESSAGES).text == "cheap"  # not shadowed, so one ID is taken


@pytest.mark.parametrize("value", [-0.1, 1.0, 1.5, math.nan, False, True, "0", None])
def test_a_draw_outside_the_unit_interval_raises_before_any_call(value):
    monitor, prov = Monitor(), provider()
    with pytest.raises(ValueError, match="random"):
        make(router(shadow_rate=0.5), prov, monitor, random=Draws(value)).call("judge", MESSAGES)
    assert prov.calls == [] and monitor.records == []


def test_a_draw_of_zero_as_an_int_is_a_number_in_the_interval():
    monitor = Monitor()
    make(router(shadow_rate=0.5), provider(), monitor, random=Draws(0)).call("judge", MESSAGES)
    assert [rec["model"] for rec in monitor.records] == [CHEAP, BEST]


def test_a_monitor_error_on_the_shadow_s_refusal_record_propagates():
    from model_routing import BudgetExceeded

    class Raising(Monitor):
        def record(self, rec):
            if rec.get("budget_event") == "refused":
                raise BudgetExceeded(Budget("other", 1.0, "refuse"), 0.0, 0.0, 2.0, BEST)
            super().record(rec)

    ledger = BudgetLedger([Budget("shadows", 0.001, "refuse", tags={"shadow": "true"})])
    with pytest.raises(BudgetExceeded) as caught:
        make(router(shadow_rate=1.0), provider(), Raising(), random=Draws(0.0),
             ledger=ledger).call("judge", MESSAGES)
    assert caught.value.budget.name == "other"


def test_a_budget_exceeded_from_the_shadow_s_provider_propagates():
    from model_routing import BudgetExceeded

    def raises(messages):
        raise BudgetExceeded(Budget("theirs", 1.0, "refuse"), 0.0, 0.0, 2.0, BEST)
    ledger = BudgetLedger([Budget("all", 100.0, "refuse")])
    with pytest.raises(BudgetExceeded) as caught:
        make(router(shadow_rate=1.0), provider(**{BEST: raises}), Monitor(), random=Draws(0.0),
             ledger=ledger).call("judge", MESSAGES)
    assert caught.value.budget.name == "theirs"


def test_an_excluded_or_generator_family_shadow_route_draws_nothing():
    monitor = Monitor()  # the default skips an excluded model: the next bound, mid, is shadowed
    make(router(shadow_rate=1.0), provider(), monitor, random=Draws(0.0)).call(
        "judge", MESSAGES, exclude_models=[BEST])
    assert [rec["model"] for rec in monitor.records] == [CHEAP, MID]
    monitor = Monitor()
    make(router(shadow_rate=1.0, shadow_route=BEST), provider(), monitor, random=never).call(
        "judge", MESSAGES, exclude_models=[BEST])
    assert [rec["model"] for rec in monitor.records] == [CHEAP]
    monitor = Monitor()
    make(router(shadow_rate=1.0, shadow_route=MID), provider(), monitor, random=never).call(
        "judge", MESSAGES, generator_model=MID)
    assert [rec["model"] for rec in monitor.records] == [CHEAP]


def test_a_sliced_call_s_shadow_holds_the_slice_s_output_and_names_the_slice():
    task = Task("judge", bar=0.7, min_samples=10, shadow_rate=1.0,
                slices={"deep": {"expected_output_tokens": 400}})
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (BEST, (100, 100))):
        stats.add("judge@deep", model_id, successes, trials)
    monitor = Monitor()
    ledger = BudgetLedger([Budget("shadows", 100.0, "refuse", tags={"shadow": "true"})])
    executor = make(Router(REGISTRY, {"judge": task}, stats), provider(), monitor,
                    random=Draws(0.0), ledger=ledger)
    seen = []
    reserve = ledger.reserve

    def spy(name, tags, estimate, model=None, **extra):
        seen.append((tags.get("shadow"), estimate))
        return reserve(name, tags, estimate, model, **extra)
    ledger.reserve = spy
    executor.call("judge", MESSAGES, slice="deep", prompt_tokens=100)
    assert [rec["slice"] for rec in monitor.records] == ["deep", "deep"]
    assert seen[-1] == ("true", REGISTRY.get(BEST).cost(100, 400))


def test_a_strict_budget_holds_the_shadow_s_billing_bound():
    from model_routing import Variant, billing_bound
    capped = BEST + "@capped"
    bounded = Model(capped, "large", 10.0, 20.0, 8000,
                    variant=Variant("capped", provider_options={"max_tokens": 500}))
    registry = Registry([REGISTRY.get(CHEAP), REGISTRY.get(BEST), bounded])
    stats = Stats()
    stats.add("judge", CHEAP, 90, 100)
    stats.add("judge", capped, 100, 100)
    route = Router(registry, {"judge": Task("judge", 0.7, min_samples=10, shadow_rate=1.0)},
                   stats)
    seen = []
    ledger = BudgetLedger([Budget("s", 100.0, "refuse", tags={"team": "x"}, strict=True)])
    reserve = ledger.reserve

    def spy(name, tags, estimate, model=None, **extra):
        seen.append((model, tags.get("shadow"), extra.get("bound_usd")))
        return reserve(name, tags, estimate, model, **extra)
    ledger.reserve = spy
    make(route, provider(**{capped: answer("capped")}), Monitor(), random=Draws(0.0),
         ledger=ledger).call("judge", MESSAGES)
    assert billing_bound(bounded) is not None
    assert seen == [(CHEAP, None, None), (capped, "true", billing_bound(bounded))]
