"""A shadow off the caller's path (DESIGN 7 v1.617, row CANARY1j).

From v1.617 `Executor(..., shadow_runner=None)` takes a callable that runs one job with no
argument, for example the `submit` of a `concurrent.futures.ThreadPoolExecutor`. With one, a
shadowed call hands its shadow to the runner as one job and returns without waiting for the
shadow's provider call; the job writes the inline shadow's records when it runs, on a deep copy of
the messages, runs once, and keeps the shadow's errors from the caller. With None the shadow runs
on the caller's thread before `.call` returns, as in v1.609.
"""

import inspect
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from math import fsum, isclose
from types import SimpleNamespace

import pytest
from model_routing import (
    AllModelsFailed, Budget, BudgetLedger, Completion, Executor, FakeProvider, Model, Monitor,
    ProviderError, Registry, Router, Stats, Task, shadow_pairs,
)
from model_routing.delegation import DELEGATE

MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
REGISTRY = Registry([
    Model(CHEAP, "small", 1.0, 2.0, 8000),
    Model(MID, "medium", 3.0, 6.0, 8000),
    Model(BEST, "large", 10.0, 20.0, 8000),
])


def router(**fields):
    """cost_effective routes cheap first; the default shadow route is best (bound highest)."""
    task = Task("judge", bar=0.7, min_samples=10, **fields)
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (MID, (95, 100)),
                                          (BEST, (100, 100))):
        stats.add(task.name, model_id, successes, trials)
    return Router(REGISTRY, {task.name: task}, stats)


def answer(text):
    return lambda messages: Completion(text, 1000, 200)


def provider(**overrides):
    script = {CHEAP: answer("cheap"), MID: answer("mid"), BEST: answer("best")}
    script.update(overrides)
    return FakeProvider({k: v for k, v in script.items() if v is not None})


def outage(messages):
    raise ProviderError("down")


class Draws:
    """An injected random source: returns the given values in order."""

    def __init__(self, *values):
        self.values = list(values)

    def __call__(self):
        return self.values.pop(0)


class Deferring:
    """A runner that keeps each job for the test to run later."""

    def __init__(self):
        self.jobs = []

    def __call__(self, job):
        self.jobs.append(job)
        return "ignored"  # what the runner returns is not read


def refuse(job):
    raise AssertionError("the runner was called")


def make(route, prov, monitor, draws, **kwargs):
    """Deterministic clock, timestamps and IDs, so two executors' records can be compared."""
    ticks = iter(float(i) for i in range(10_000))
    stamps = iter(f"2026-11-24T00:00:{i:02d}Z" for i in range(60))
    ids = iter(f"call-{i}" for i in range(10_000))
    return Executor(route, prov, monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: next(stamps), id_factory=lambda: next(ids), random=draws, **kwargs)


def attempts(records):
    return [rec for rec in records if "budget_event" not in rec]


# --- the parameter ----------------------------------------------------------------------------

def test_shadow_runner_is_the_last_parameter_and_defaults_to_none():
    params = list(inspect.signature(Executor).parameters.values())
    assert [p.name for p in params[-3:]] == ["ledger", "random", "shadow_runner"]
    assert params[-1].default is None


@pytest.mark.parametrize("value", [0.5, "submit", object(), [print]])
def test_a_runner_that_is_not_callable_is_a_value_error_when_the_executor_is_built(value):
    with pytest.raises(ValueError, match="shadow_runner"):
        Executor(router(), provider(), shadow_runner=value)


def test_with_no_runner_the_shadow_runs_inline_as_in_v1_609():
    default, explicit = Monitor(), Monitor()
    first, second = provider(), provider()
    make(router(shadow_rate=1.0), first, default, Draws(0.0)).call("judge", MESSAGES)
    make(router(shadow_rate=1.0), second, explicit, Draws(0.0), shadow_runner=None).call(
        "judge", MESSAGES)
    assert default.records == explicit.records and len(default.records) == 2
    assert [m for m, _ in first.calls] == [m for m, _ in second.calls] == [CHEAP, BEST]


# --- the job ----------------------------------------------------------------------------------

def test_a_deferred_shadow_writes_the_inline_records_once_its_job_runs():
    inline, deferred = Monitor(), Monitor()
    inline_prov, deferred_prov = provider(), provider()
    runner = Deferring()
    plain = make(router(shadow_rate=1.0), inline_prov, inline, Draws(0.0, 0.0, 0.0))
    handed = make(router(shadow_rate=1.0), deferred_prov, deferred, Draws(0.0, 0.0, 0.0),
                  shadow_runner=runner)
    for k in range(3):
        want = plain.call("judge", MESSAGES, tags={"team": "a"})
        got = handed.call("judge", MESSAGES, tags={"team": "a"})
        assert got == want and got.attempts == want.attempts and len(got.attempts) == 1
        # .call has returned: the routed call's record alone, and one job kept
        assert len(runner.jobs) == 1
        assert [rec["shadow"] for rec in deferred.records[2 * k:]] == [False]
        assert [m for m, _ in deferred_prov.calls[k * 2:]] == [CHEAP]
        assert runner.jobs.pop()() is None
        assert [rec["shadow"] for rec in deferred.records[2 * k:]] == [False, True]
    assert deferred.records == inline.records and len(inline.records) == 6
    assert [rec["ts"] for rec in inline.records] == [f"2026-11-24T00:00:{i:02d}Z" for i in range(6)]
    assert [(m, msgs) for m, msgs in deferred_prov.calls] == [(m, msgs) for m, msgs in inline_prov.calls]
    assert [m for m, _ in deferred_prov.calls] == [CHEAP, BEST] * 3


def test_a_change_to_the_callers_messages_after_the_call_does_not_reach_the_shadow():
    seen = []
    prov = provider(**{BEST: lambda messages: seen.append(messages) or Completion("best", 1000, 200)})
    runner = Deferring()
    messages = [{"role": "user", "content": "judge"}]
    make(router(shadow_rate=1.0), prov, Monitor(), Draws(0.0), shadow_runner=runner).call(
        "judge", messages)
    messages[0]["content"] = "changed"
    messages.append({"role": "user", "content": "more"})
    runner.jobs.pop()()
    assert seen == [[{"role": "user", "content": "judge"}]]
    assert seen[0] is not messages and seen[0][0] is not messages[0]


def test_a_job_that_is_never_run_sends_holds_and_writes_nothing():
    monitor, prov, runner = Monitor(), provider(), Deferring()
    ledger = BudgetLedger([Budget("all", 100.0, "refuse")])
    result = make(router(shadow_rate=1.0), prov, monitor, Draws(0.0), shadow_runner=runner,
                  ledger=ledger).call("judge", MESSAGES)
    assert len(runner.jobs) == 1 and [m for m, _ in prov.calls] == [CHEAP]
    assert [(rec["pair_id"], rec["shadow"]) for rec in monitor.records] == [(result.call_id, False)]
    assert ledger.held_usd("all") == 0.0
    assert isclose(ledger.spent_usd("all"), result.attempts[0].cost_usd, rel_tol=1e-12)
    assert shadow_pairs(monitor.records) == []


def test_a_job_runs_its_shadow_once():
    monitor, prov, runner = Monitor(), provider(), Deferring()
    make(router(shadow_rate=1.0), prov, monitor, Draws(0.0), shadow_runner=runner).call(
        "judge", MESSAGES)
    job = runner.jobs.pop()
    job()
    before = (list(monitor.records), list(prov.calls))
    with pytest.raises(RuntimeError, match="already run"):
        job()
    assert (monitor.records, prov.calls) == before and len(monitor.records) == 2
    assert len(shadow_pairs(monitor.records)) == 1


# --- failures ---------------------------------------------------------------------------------

@pytest.mark.parametrize("case", ["error", "invalid"])
def test_a_shadow_failure_ends_its_job_with_no_exception(case):
    monitor, runner = Monitor(), Deferring()
    prov = provider(**{BEST: None}) if case == "error" else provider()
    result = make(router(shadow_rate=1.0), prov, monitor, Draws(0.0), shadow_runner=runner).call(
        "judge", MESSAGES, validate=lambda text: text != "best")
    assert (result.text, result.model) == ("cheap", CHEAP)
    assert runner.jobs.pop()() is None
    shadow = monitor.records[1]
    assert (shadow["shadow"], shadow["outcome"], shadow["pair_id"]) == (True, case, result.call_id)


def test_a_bug_in_the_shadow_leaves_its_job_and_never_the_call():
    def bug(messages):
        raise RuntimeError("a bug in the provider")

    monitor, runner = Monitor(), Deferring()
    result = make(router(shadow_rate=1.0), provider(**{BEST: bug}), monitor, Draws(0.0),
                  shadow_runner=runner).call("judge", MESSAGES)
    assert (result.text, result.model) == ("cheap", CHEAP)
    job = runner.jobs.pop()
    with pytest.raises(RuntimeError, match="a bug in the provider"):
        job()
    with pytest.raises(RuntimeError, match="already run"):  # a retry of a failed job is refused
        job()
    assert [rec["shadow"] for rec in attempts(monitor.records)] == [False]


def test_a_runner_s_own_exception_leaves_the_call_after_the_routed_records():
    pool = ThreadPoolExecutor(max_workers=1)
    pool.shutdown()  # its submit now raises RuntimeError
    monitor, prov = Monitor(), provider()
    executor = make(router(shadow_rate=1.0), prov, monitor, Draws(0.0), shadow_runner=pool.submit)
    with pytest.raises(RuntimeError, match="shutdown"):
        executor.call("judge", MESSAGES)
    assert [m for m, _ in prov.calls] == [CHEAP]
    assert [(rec["call_id"], rec["shadow"], rec["outcome"]) for rec in monitor.records] == [
        ("call-0", False, "ok")]


def test_a_deep_copy_that_raises_leaves_the_call_with_no_shadow_sent():  # review iter-468 nit 1
    class Uncopyable:
        def __deepcopy__(self, memo):
            raise TypeError("this content cannot be copied")

    monitor, prov, runner = Monitor(), provider(), Deferring()
    executor = make(router(shadow_rate=1.0), prov, monitor, Draws(0.0), shadow_runner=runner)
    with pytest.raises(TypeError, match="cannot be copied"):
        executor.call("judge", [{"role": "user", "content": "judge", "extra": Uncopyable()}])
    assert runner.jobs == [] and [m for m, _ in prov.calls] == [CHEAP]
    assert [(rec["shadow"], rec["outcome"]) for rec in monitor.records] == [(False, "ok")]


def test_a_runner_that_runs_its_job_at_once_makes_the_call_wait_and_passes_a_bug_on():
    # review iter-468 should-fix 1: the library cannot tell such a runner from one on a thread
    def bug(messages):
        raise RuntimeError("a bug in the provider")

    inline, at_once = Monitor(), Monitor()
    make(router(shadow_rate=1.0), provider(), inline, Draws(0.0)).call("judge", MESSAGES)
    prov = provider()
    make(router(shadow_rate=1.0), prov, at_once, Draws(0.0),
         shadow_runner=lambda job: job()).call("judge", MESSAGES)
    assert at_once.records == inline.records and [m for m, _ in prov.calls] == [CHEAP, BEST]
    with pytest.raises(RuntimeError, match="a bug in the provider"):
        make(router(shadow_rate=1.0), provider(**{BEST: bug}), Monitor(), Draws(0.0),
             shadow_runner=lambda job: job()).call("judge", MESSAGES)


@pytest.mark.parametrize("case", ["rate zero", "draw at the rate", "answer from the shadow route",
                                  "routed call raises", "delegated"])
def test_a_call_that_is_not_shadowed_never_calls_the_runner(case):
    monitor = Monitor()
    if case == "rate zero":
        result = make(router(shadow_route=BEST), provider(), monitor, Draws(),
                      shadow_runner=refuse).call("judge", MESSAGES)
        assert "pair_id" not in monitor.records[0]
    elif case == "draw at the rate":
        result = make(router(shadow_rate=0.5), provider(), monitor, Draws(0.5),
                      shadow_runner=refuse).call("judge", MESSAGES)
        assert "pair_id" not in monitor.records[0]
    elif case == "answer from the shadow route":  # v1.609: a fallback onto it
        result = make(router(shadow_rate=1.0, shadow_route=MID), provider(**{CHEAP: outage}),
                      monitor, Draws(0.0), shadow_runner=refuse).call("judge", MESSAGES)
        assert result.model == MID
        assert [rec["shadow"] for rec in monitor.records] == [False, False]
    elif case == "routed call raises":
        with pytest.raises(AllModelsFailed):
            make(router(shadow_rate=1.0, max_fallbacks=0), provider(**{CHEAP: None}), monitor,
                 Draws(0.0), shadow_runner=refuse).call("judge", MESSAGES)
        assert [rec["shadow"] for rec in monitor.records] == [False]
    else:
        route = router(shadow_rate=1.0)
        decision = SimpleNamespace(mode=DELEGATE, route=route.select("judge"), parent="call-p",
                                   task="judge")
        result = make(route, provider(), monitor, Draws(), shadow_runner=refuse).call_delegated(
            decision, MESSAGES)
        assert result.model == CHEAP and len(monitor.records) == 1


# --- a thread pool ----------------------------------------------------------------------------

def test_a_thread_pool_runner_over_50_shadowed_calls_returns_before_each_shadow(tmp_path):
    path = tmp_path / "calls.jsonl"
    monitor = Monitor(path)
    ledger = BudgetLedger([Budget("all", 100.0, "refuse")])
    gate, entered = threading.Event(), threading.Event()

    def held(messages):  # each shadow's provider call waits until all 50 calls have returned
        entered.set()
        if not gate.wait(10):
            raise AssertionError("the shadow ran on the caller's path")
        return Completion("best", 1000 + int(messages[0]["content"]), 200)

    prov = provider(**{CHEAP: lambda messages: Completion("cheap", 1000 + int(messages[0]["content"]),
                                                          200),
                       BEST: held})
    pool = ThreadPoolExecutor(max_workers=4)
    try:
        executor = Executor(router(shadow_rate=1.0), prov, monitor=monitor, ledger=ledger,
                            shadow_runner=pool.submit)
        results = [executor.call("judge", [{"role": "user", "content": str(k)}],
                                 validate=lambda text: True) for k in range(50)]  # 8.3 v1.618
        # every call has returned while its shadow waits: 50 routed records, shadows in flight
        assert [rec["shadow"] for rec in monitor.records] == [False] * 50
        assert entered.wait(10)  # a shadow holds its estimate before its provider call
        assert ledger.held_usd("all") > 0.0
    finally:
        gate.set()
        pool.shutdown(wait=True)
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    lines = [json.loads(line) for line in text[:-1].split("\n")]
    assert lines == monitor.records and len(lines) == 100
    assert len({rec["call_id"] for rec in lines}) == 100
    pairs = shadow_pairs(monitor.records, checked=True)
    assert len(pairs) == 50
    assert {pair["pair_id"] for pair in pairs} == {result.call_id for result in results}
    by_id = {rec["call_id"]: rec for rec in lines}
    for pair in pairs:  # each shadow ran its own call's messages
        assert by_id[pair["shadow_call_id"]]["input_tokens"] == by_id[pair["pair_id"]]["input_tokens"]
        assert (pair["routed_correct"], pair["shadow_correct"]) == (True, True)
    assert ledger.held_usd("all") == 0.0
    assert isclose(ledger.spent_usd("all"), fsum(rec["cost_usd"] for rec in lines), rel_tol=1e-12)
