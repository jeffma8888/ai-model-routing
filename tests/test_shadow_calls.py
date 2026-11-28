"""Shadow calls (DESIGN 4.2, 7 and 8.1 v1.607, row CANARY1a; cascade and procedure primaries,
row CANARY1f; a below-bar shadow route's record, 8.1 v1.608, row CANARY1g; a shadow that
repeats the routed answer, 7 and 8.1 v1.609, rows CANARY1h and CANARY1i)."""

import dataclasses
import inspect
import json
import math

import pytest
from model_routing import (
    AllModelsFailed, Budget, BudgetLedger, Cascade, Completion, Executor, FakeProvider, Model,
    Monitor, Procedure, ProcedureResult, ProviderError, Registry, Router, Stats, Task,
    load_tasks, report,
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
    # v1.628 (row LAT1b): the two latency fields follow them
    assert names[names.index("failure_policy"):][:5] == ["failure_policy", "shadow_rate", "shadow_route",
                                                       "max_p95_ms", "latency_unknown"]
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

def test_random_follows_ledger_and_defaults_to_none():
    params = list(inspect.signature(Executor).parameters.values())
    assert [p.name for p in params[-4:-2]] == ["ledger", "random"]  # 7 v1.617 and v1.704: then shadow_runner, max_sessions
    assert params[-3].default is None


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


def test_the_pair_keys_follow_slice_in_order():  # 8.1 v1.618: checked after shadow
    base, shadowed = Monitor(), Monitor()
    make(router(), provider(), base).call("judge", MESSAGES, tags={"team": "a"})
    make(router(shadow_rate=1.0), provider(), shadowed, random=Draws(0.5)).call(
        "judge", MESSAGES, tags={"team": "a"})
    keys = list(base.records[0])
    at = keys.index("slice") + 1
    assert list(shadowed.records[0]) == keys[:at] + ["pair_id", "shadow", "checked"] + keys[at:]
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
    assert warns and all(list(rec)[:7] == ["ts", "call_id", "task", "tags", "pair_id", "shadow",
                                          "checked"] for rec in warns)
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


# --- 7 a cascade or a procedure primary (review iter-456 should-fix 2, row CANARY1f) -----------

CASCADE = Cascade(CHEAP, MID, "sig")  # fiction/cheap>fiction/mid@sig
PROC_KEYS = ("procedure", "procedure_version", "model_calls", "tool_calls", "tool_cost_usd")


def entry_stats(entry_id, **counts):
    """cheap 50/100 is under the 0.7 bar and off the route, so the entry, the cheapest passing
    candidate, leads cost_effective's route (mid, best after it); at 100/100 its bound is the
    highest, above best's 98/100 and mid's 95/100, so a default that took a route entry for a
    registry model would pick the primary (review iter-457 nit 1)."""
    stats = Stats()
    for model_id, successes in ((CHEAP, 50), (MID, 95), (BEST, 98)):
        stats.add("judge", model_id, successes, 100)
    stats.add("judge", entry_id, 100, 100, **counts)
    return stats


def cascade_router(**fields):
    task = Task("judge", bar=0.7, min_samples=10, cascades=(CASCADE,), shadow_rate=1.0, **fields)
    return Router(REGISTRY, {"judge": task}, entry_stats(CASCADE.id, escalated=20))


def procedure_router(proc, **fields):
    task = Task("judge", bar=0.7, min_samples=10, shadow_rate=1.0, **fields)
    return Router(REGISTRY, {"judge": task}, entry_stats(proc.id, cost_usd=0.02))


def outage(messages):
    raise ProviderError("outage")


def polling(value, call):
    """One model call, then the procedure's own copy of the messages grows."""
    text = call([{"role": "user", "content": "summarize"}])
    value.append({"role": "tool", "content": "polled"})
    return ProcedureResult("shaped " + text, tool_calls=3, tool_cost_usd=0.0005)


def shaping(value, call):
    return ProcedureResult("shaped in code", tool_calls=2)


def crashing(value, call):
    raise RuntimeError("boom")


POLLING = Procedure("poll", "v1", polling, max_model_calls=2, max_tool_calls=5, model=CHEAP)
SHAPING = Procedure("shape", "v2", shaping, max_model_calls=0, max_tool_calls=2)
CRASHING = Procedure("crash", "v1", crashing, max_model_calls=1, max_tool_calls=1, model=CHEAP)


def check_shadow(shadow, plain_keys):
    """The shadow's one record: a plain entry of best under its own ID, paired with call-0."""
    assert (shadow["model"], shadow["call_id"], shadow["pair_id"], shadow["shadow"]) == (
        BEST, "call-1", "call-0", True)
    assert (shadow["attempt"], shadow["final"], shadow["outcome"]) == (0, True, "ok")
    assert shadow["tags"] == {"shadow": "true"}
    assert list(shadow) == plain_keys  # no cascade, escalated or procedure key


@pytest.mark.parametrize("way, signal, cheap, routed, text", [
    ("kept", False, answer("cheap"), [CHEAP], "cheap"),
    ("signal", True, answer("cheap"), [CHEAP, MID], "mid"),
    ("error", False, outage, [CHEAP, MID], "mid"),
])
def test_a_cascade_primary_s_shadow_goes_to_the_default_route_after_its_attempts(
        way, signal, cheap, routed, text):
    route = cascade_router()
    decision = route.select("judge", cascades=True)
    bounds = {c.model_id: c.quality_lb for c in decision.candidates}
    assert decision.primary == CASCADE.id == max(bounds, key=bounds.get)
    assert decision.fallbacks == (MID, BEST)  # review iter-457 nit 2
    monitor, prov, draws = Monitor(), provider(**{CHEAP: cheap}), Draws(0.0)
    result = make(route, prov, monitor, random=draws).call(
        "judge", MESSAGES, signals={"sig": lambda output: signal})
    assert draws.calls == 1  # review iter-457 nit 3
    assert (result.call_id, result.model, result.text) == ("call-0", routed[-1], text)
    assert [attempt.model for attempt in result.attempts] == routed  # never the shadow's
    assert [model for model, _ in prov.calls] == routed + [BEST]
    assert all(messages is MESSAGES for _, messages in prov.calls)
    *legs, shadow = monitor.records
    assert [rec["model"] for rec in legs] == routed
    assert [rec["final"] for rec in legs] == [False] * (len(routed) - 1) + [True]
    assert legs[0]["outcome"] == ("error" if way == "error" else "ok")
    for rec in legs:
        assert (rec["call_id"], rec["pair_id"], rec["shadow"]) == ("call-0", "call-0", False)
        assert (rec["cascade"], rec["escalated"]) == (CASCADE.id, way != "kept")
        keys = list(rec)
        at = keys.index("slice") + 1
        assert keys[at:at + 5] == ["pair_id", "shadow", "checked", "cascade", "escalated"]
    check_shadow(shadow, [key for key in legs[-1] if key not in ("cascade", "escalated")])


@pytest.mark.parametrize("proc, routed, model, text", [
    (POLLING, [CHEAP, POLLING.id], POLLING.id, "shaped cheap"),
    (SHAPING, [SHAPING.id], SHAPING.id, "shaped in code"),
    (CRASHING, [CRASHING.id, MID], MID, "mid"),  # the entry errs and falls back
])
def test_a_procedure_primary_s_shadow_goes_to_the_default_route_after_its_closing_record(
        proc, routed, model, text):
    route = procedure_router(proc)
    decision = route.select("judge", procedures=[proc])
    bounds = {c.model_id: c.quality_lb for c in decision.candidates}
    assert decision.primary == proc.id == max(bounds, key=bounds.get)
    assert decision.fallbacks == (MID, BEST)  # review iter-457 nit 2
    monitor, prov, draws = Monitor(), provider(), Draws(0.0)
    result = make(route, prov, monitor, random=draws).call(
        "judge", MESSAGES, procedures=[proc])
    assert draws.calls == 1  # review iter-457 nit 3
    assert (result.call_id, result.model, result.text) == ("call-0", model, text)
    assert [attempt.model for attempt in result.attempts] == routed  # never the shadow's
    assert [m for m, _ in prov.calls] == [m for m in routed if m in REGISTRY] + [BEST]
    assert prov.calls[-1][1] is MESSAGES and MESSAGES == [{"role": "user", "content": "judge"}]
    *legs, shadow = monitor.records
    assert [rec["model"] for rec in legs] == routed
    assert [rec["final"] for rec in legs] == [False] * (len(routed) - 1) + [True]
    closing = [rec["model"] for rec in legs].index(proc.id)  # the entry's closing record
    assert legs[closing]["outcome"] == ("error" if proc is CRASHING else "ok")
    for position, rec in enumerate(legs):
        assert (rec["call_id"], rec["pair_id"], rec["shadow"]) == ("call-0", "call-0", False)
        keys = list(rec)
        at = keys.index("slice") + 1
        if position <= closing:  # the handle's model calls and the closing record
            assert keys[at:at + 5] == ["pair_id", "shadow", "checked", "procedure",
                                       "procedure_version"]
            assert (rec["procedure"], rec["procedure_version"]) == (proc.name, proc.version)
        else:  # a fallback entry after the procedure: a plain record
            assert keys[at:at + 3] == ["pair_id", "shadow", "checked"]
            assert not set(PROC_KEYS) & set(keys)
    assert legs[closing]["model_calls"] == closing
    check_shadow(shadow, [key for key in legs[closing] if key not in PROC_KEYS])


@pytest.mark.parametrize("kind", ["cascade", "procedure"])
def test_a_shadow_route_naming_a_cascade_or_a_procedure_is_a_value_error_before_any_call(kind):
    if kind == "cascade":
        route = cascade_router(shadow_route=CASCADE.id)
        kwargs = {"signals": {"sig": lambda output: False}}
    else:
        route = procedure_router(POLLING, shadow_route=POLLING.id)
        kwargs = {"procedures": [POLLING]}
    monitor, prov = Monitor(), provider()
    with pytest.raises(ValueError, match="is not a registry model"):
        make(route, prov, monitor, random=never).call("judge", MESSAGES, **kwargs)
    assert prov.calls == [] and monitor.records == []


# --- 8.1 v1.608 a below-bar shadow route's record -----------------------------------------

def under_bar_calls(records):
    return {row["group"]: row["below_bar_calls"] for row in report(records)}


HELD = {"fallback_below_bar": True, "max_fallbacks": 3}  # the route ends with small


@pytest.mark.parametrize("fields, held, small, outcome", [
    (HELD, True, answer("small"), "ok"),
    (HELD, True, outage, "error"),  # keyed, and no below_bar_calls: the attempt is not ok
    ({"max_fallbacks": 3}, False, answer("small"), "ok"),  # the option off
    ({"fallback_below_bar": True}, False, answer("small"), "ok"),  # past two fallbacks
])
def test_a_named_below_bar_shadow_carries_below_bar_fallback_only_when_the_route_holds_it(
        fields, held, small, outcome):
    route = router(shadow_rate=1.0, shadow_route=SMALL, **fields)  # 50 of 100, under the bar
    decision = route.select("judge", prompt_tokens=2)
    assert decision.primary == CHEAP and not decision.below_bar
    assert decision.below_bar_fallbacks == ((SMALL,) if held else ())
    monitor = Monitor()
    result = make(route, provider(**{SMALL: small}), monitor,
                  random=Draws(0.0)).call("judge", MESSAGES)
    assert result.text == "cheap"
    routed, shadow = monitor.records
    assert (routed["model"], shadow["model"], shadow["shadow"]) == (CHEAP, SMALL, True)
    assert (routed["outcome"], shadow["outcome"]) == ("ok", outcome)
    assert routed["prompt_tokens"] == shadow["prompt_tokens"] == 2
    assert routed["below_bar"] is False  # the decision's flag
    assert shadow["below_bar"] is False
    assert "below_bar_fallback" not in routed
    keys = list(routed)
    if held:
        assert shadow["below_bar_fallback"] is True
        at = keys.index("below_bar") + 1
        assert list(shadow) == keys[:at] + ["below_bar_fallback"] + keys[at:]
    else:
        assert "below_bar_fallback" not in shadow and list(shadow) == keys
    # with shadow=False, its default, report counts the shadow as a call of its own (8.3 v1.611)
    assert under_bar_calls(monitor.records) == {CHEAP: 0, SMALL: int(held and outcome == "ok")}


def test_a_named_shadow_s_below_bar_is_the_decision_s_when_nothing_clears_the_bar():
    task = Task("judge", bar=0.99, min_samples=10, on_no_model="best_available",
                fallback_below_bar=True, shadow_rate=1.0, shadow_route=CHEAP)
    stats = Stats()
    stats.add("judge", CHEAP, 50, 100)
    stats.add("judge", MID, 60, 100)
    route = Router(REGISTRY, {"judge": task}, stats)
    decision = route.select("judge", prompt_tokens=2)
    assert (decision.primary, decision.fallbacks) == (MID, (CHEAP,))
    assert decision.below_bar and decision.below_bar_fallbacks == ()
    monitor = Monitor()
    make(route, provider(), monitor, random=Draws(0.0)).call("judge", MESSAGES)
    routed, shadow = monitor.records
    assert (routed["model"], shadow["model"], shadow["shadow"]) == (MID, CHEAP, True)
    assert routed["below_bar"] is True
    assert shadow["below_bar"] is True
    assert "below_bar_fallback" not in routed and "below_bar_fallback" not in shadow
    assert list(shadow) == list(routed)
    assert under_bar_calls(monitor.records) == {MID: 1, CHEAP: 1}


# --- 7 and 8.1 v1.609 a shadow that repeats the routed answer (rows CANARY1h and CANARY1i) ----

TO_BEST = Cascade(CHEAP, BEST, "sig")  # its strong leg is the default shadow route


def shadow_records(records):
    return [rec for rec in records if rec.get("shadow") is True]


def test_the_cascade_fixture_s_strong_leg_is_the_default_shadow_route():
    task = Task("judge", bar=0.7, min_samples=10, cascades=(TO_BEST,), shadow_rate=1.0)
    decision = Router(REGISTRY, {"judge": task},
                      entry_stats(TO_BEST.id, escalated=10)).select("judge", cascades=True)
    assert (decision.primary, decision.fallbacks) == (TO_BEST.id, (MID, BEST))
    passing = [c for c in decision.candidates if c.passes and c.model_id in REGISTRY]
    assert max(passing, key=lambda c: c.quality_lb).model_id == BEST == TO_BEST.strong


@pytest.mark.parametrize("way, signal, cheap, routed, sent", [
    ("kept", False, answer("cheap"), [CHEAP], True),  # best never answered: shadowed
    ("signal", True, answer("cheap"), [CHEAP, BEST], False),  # handed up onto best
    ("error", False, outage, [CHEAP, BEST], False),
])
def test_a_cascade_hand_up_onto_the_shadow_route_sends_no_shadow(way, signal, cheap, routed,
                                                                 sent):
    task = Task("judge", bar=0.7, min_samples=10, cascades=(TO_BEST,), shadow_rate=1.0)
    route = Router(REGISTRY, {"judge": task}, entry_stats(TO_BEST.id, escalated=10))
    monitor, prov, draws = Monitor(), provider(**{CHEAP: cheap}), Draws(0.0, 0.0)
    executor = make(route, prov, monitor, random=draws)
    result = executor.call("judge", MESSAGES, signals={"sig": lambda output: signal})
    assert draws.calls == 1  # drawn before any provider call, sent or not
    assert (result.call_id, result.model) == ("call-0", routed[-1])
    assert [model for model, _ in prov.calls] == routed + ([BEST] if sent else [])
    legs = [rec for rec in monitor.records if rec["call_id"] == "call-0"]
    assert [rec["model"] for rec in legs] == routed
    assert all((rec["pair_id"], rec["shadow"]) == ("call-0", False) for rec in legs)
    shadows = shadow_records(monitor.records)
    assert len(monitor.records) == len(routed) + len(shadows)
    if sent:
        check_shadow(shadows[0], [key for key in legs[-1] if key not in ("cascade", "escalated")])
    else:
        assert shadows == []
        # the skipped shadow took call-1, so the next call is call-2 (7 v1.609)
        assert executor.call("judge", MESSAGES,
                             signals={"sig": lambda output: False}).call_id == "call-2"
        assert draws.calls == 2


POLL_BEST = Procedure("pollbest", "v1", polling, max_model_calls=2, max_tool_calls=5, model=BEST)


@pytest.mark.parametrize("proc, named, routed, sent", [
    (POLL_BEST, None, [BEST, POLL_BEST.id], BEST),  # its model is the default shadow route
    (CRASHING, MID, [CRASHING.id, MID], None),  # it errs and falls back onto the shadow route
])
def test_a_procedure_s_answer_is_no_repeat_but_its_fallback_onto_the_shadow_route_is(
        proc, named, routed, sent):
    route = procedure_router(proc, **({} if named is None else {"shadow_route": named}))
    monitor, prov, draws = Monitor(), provider(), Draws(0.0)
    result = make(route, prov, monitor, random=draws).call("judge", MESSAGES, procedures=[proc])
    assert draws.calls == 1
    assert result.model == routed[-1]
    assert [attempt.model for attempt in result.attempts] == routed
    registry_calls = [m for m in routed if m in REGISTRY]
    assert [m for m, _ in prov.calls] == registry_calls + ([sent] if sent else [])
    shadows = shadow_records(monitor.records)
    if sent:  # the handle sent the procedure's messages, the shadow the call's
        assert prov.calls[0][1] == [{"role": "user", "content": "summarize"}]
        assert prov.calls[-1][1] is MESSAGES
        assert [(rec["model"], rec["outcome"]) for rec in shadows] == [(BEST, "ok")]
    else:
        assert shadows == []
    assert len(monitor.records) == len(routed) + len(shadows)


def test_a_fallback_onto_the_named_shadow_route_sends_no_shadow():
    route = router(shadow_rate=1.0, shadow_route=MID)
    monitor, prov = Monitor(), provider(**{CHEAP: outage})
    result = make(route, prov, monitor, random=Draws(0.0)).call("judge", MESSAGES)
    assert (result.model, result.text) == (MID, "mid")
    assert [m for m, _ in prov.calls] == [CHEAP, MID]
    assert [(r["call_id"], r["model"], r["attempt"], r["outcome"], r["pair_id"], r["shadow"])
            for r in monitor.records] == [("call-0", CHEAP, 0, "error", "call-0", False),
                                          ("call-0", MID, 1, "ok", "call-0", False)]
    calls = {row["group"]: row["calls"] for row in report(monitor.records)}
    assert calls == {CHEAP: 0, MID: 1}  # one call, counted under the model that answered


def test_a_below_bar_fallback_onto_the_named_shadow_route_sends_no_shadow():
    route = router(shadow_rate=1.0, shadow_route=SMALL, **HELD)
    prov = provider(**{CHEAP: outage, MID: outage, BEST: outage, SMALL: answer("small")})
    monitor = Monitor()
    result = make(route, prov, monitor, random=Draws(0.0)).call("judge", MESSAGES)
    assert (result.model, result.text) == (SMALL, "small")
    assert [m for m, _ in prov.calls] == [CHEAP, MID, BEST, SMALL]
    *failed, last = monitor.records
    assert [rec["outcome"] for rec in failed] == ["error"] * 3
    assert (last["call_id"], last["model"], last["attempt"], last["shadow"]) == (
        "call-0", SMALL, 3, False)
    assert last["below_bar_fallback"] is True
    assert shadow_records(monitor.records) == []
    assert under_bar_calls(monitor.records) == {CHEAP: 0, MID: 0, BEST: 0, SMALL: 1}
    assert {row["group"]: row["calls"] for row in report(monitor.records)}[SMALL] == 1


@pytest.mark.parametrize("named, overrides, routed, outcome", [
    (None, {}, [CHEAP], "ok"),  # a plain primary answers: the default shadow, as in v1.607
    (MID, {}, [CHEAP], "ok"),
    (MID, {CHEAP: outage, MID: outage}, [CHEAP, MID, BEST], "error"),  # tried and left
])
def test_a_call_whose_answer_is_not_the_shadow_route_s_is_shadowed_as_in_v1_608(
        named, overrides, routed, outcome):
    fields = {} if named is None else {"shadow_route": named}
    route = router(shadow_rate=1.0, **fields)
    monitor, prov = Monitor(), provider(**overrides)
    result = make(route, prov, monitor, random=Draws(0.0)).call("judge", MESSAGES)
    assert result.model == routed[-1] != (named or BEST)
    target = named or BEST
    assert [m for m, _ in prov.calls] == routed + [target]
    *legs, shadow = monitor.records
    assert [rec["model"] for rec in legs] == routed
    assert (shadow["model"], shadow["call_id"], shadow["pair_id"], shadow["shadow"]) == (
        target, "call-1", "call-0", True)
    assert (shadow["attempt"], shadow["final"], shadow["outcome"]) == (0, True, outcome)
    assert shadow["tags"] == {"shadow": "true"}
