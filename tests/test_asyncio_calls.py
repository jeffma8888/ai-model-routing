"""An asyncio service calls the executor on worker threads (DESIGN 7 v1.657, row PROD1e).

From v1.657 DESIGN 7 states how a coroutine calls one `Executor`: it awaits
`asyncio.to_thread(executor.call, ...)`, or `loop.run_in_executor(pool, functools.partial(...))`,
so the call blocks only the worker thread that runs it and the event loop keeps serving other
coroutines. v1.616's rules for threads hold for those worker threads unchanged. A `shadow_runner`
may be a thread pool's `submit`, whose pool is shut down before the log is read. An await that
times out or is cancelled does not stop a call that has started: the call runs on to its end on its
worker thread, writes its records and settles its hold, while a call still queued for a worker is
cancelled with its await and never runs (review iter-513 should-fix 1). Native async execution stays
a DESIGN 14 non-goal, and the tests need no code change, so the slice has no red commit.
"""

import asyncio
import functools
import json
import threading
from concurrent.futures import ThreadPoolExecutor
from math import fsum, isclose
from pathlib import Path

from model_routing import (
    Budget, BudgetLedger, Completion, Executor, FakeProvider, Model, Monitor, Registry, Router,
    Stats, Task, report, shadow_pairs,
)

ROOT = Path(__file__).resolve().parents[1]
CALLS = 50
CHEAP, BEST = "fiction/cheap", "fiction/best"
REGISTRY = Registry([
    Model(CHEAP, "small", 1.0, 2.0, 8000),
    Model(BEST, "large", 10.0, 20.0, 8000),
])
MESSAGES = [[{"role": "user", "content": f"m-{index}"}] for index in range(CALLS)]
VARYING = ("call_id", "ts", "latency_ms")  # each run's own: an ID, a wall time and a measured time


def router(**fields):
    """cost_effective routes cheap first; both models clear the bar."""
    task = Task("judge", bar=0.7, min_samples=10, **fields)
    stats = Stats()
    stats.add(task.name, CHEAP, 90, 100)
    stats.add(task.name, BEST, 100, 100)
    return Router(REGISTRY, {task.name: task}, stats)


def tokens(messages):
    """Each call's input size from its message, so the calls' costs differ."""
    return 1000 + int(messages[0]["content"].split("-")[1]) % 97


class SafeProvider:
    """A `FakeProvider` behind a lock, since a provider of the caller's own is the caller's to guard
    (7 v1.616). `hold(model_id, messages)` runs before the lock, so it can keep one call on its
    worker thread while the others go on."""

    def __init__(self, hold=None):
        self.fake = FakeProvider({
            CHEAP: lambda messages: Completion("cheap", tokens(messages), 200),
            BEST: lambda messages: Completion("best", tokens(messages), 200),
        })
        self.lock = threading.Lock()
        self.hold = hold

    def complete(self, model_id, messages, timeout_s, *, options=None):
        if self.hold is not None:
            self.hold(model_id, messages)
        with self.lock:
            return self.fake.complete(model_id, messages, timeout_s, options=options)


def check(index):
    """Every fifth call's cheap answer fails its check, so that call falls back to the best model."""
    return lambda text: text != "cheap" or index % 5 != 0


EXPECTED_MODELS = [BEST if index % 5 == 0 else CHEAP for index in range(CALLS)]


def build(tmp_path, name, hold=None, **executor_fields):
    monitor = Monitor(tmp_path / f"{name}.jsonl")
    ledger = BudgetLedger([Budget("all", 100.0, "refuse")])
    task_fields = executor_fields.pop("task_fields", {})
    executor = Executor(router(**task_fields), SafeProvider(hold), monitor=monitor, ledger=ledger,
                        **executor_fields)
    return executor, monitor, ledger


def whole_lines(path):
    """Every line of the log, each parsed on its own: a mixed line would not parse."""
    text = Path(path).read_text(encoding="utf-8")
    assert text.endswith("\n")
    return [json.loads(line) for line in text[:-1].split("\n")]


def stripped(records):
    """The records as a multiset, less the keys that differ from run to run."""
    return sorted(json.dumps({key: value for key, value in rec.items() if key not in VARYING}, sort_keys=True)
                  for rec in records)


def totals(records):
    """`report`'s per-model rows less their measured times."""
    return [{key: value for key, value in row.items() if "latency" not in key}
            for row in report(records, by="model")]


def one_after_another(tmp_path):
    """The same 50 calls made one after another on one thread, the baseline."""
    executor, monitor, ledger = build(tmp_path, "sequential")
    results = [executor.call("judge", MESSAGES[index], validate=check(index)) for index in range(CALLS)]
    assert [result.model for result in results] == EXPECTED_MODELS
    return monitor.records, ledger.spent_usd("all")


# --- 7 v1.657: a coroutine awaits the call on a worker thread ----------------------------------

def test_50_calls_gathered_over_to_thread_give_the_records_and_totals_of_the_same_calls_in_turn(tmp_path):
    executor, monitor, ledger = build(tmp_path, "gathered")

    async def main():
        return await asyncio.gather(*(asyncio.to_thread(executor.call, "judge", MESSAGES[index],
                                                        validate=check(index))
                                      for index in range(CALLS)))

    results = asyncio.run(main())
    assert [result.model for result in results] == EXPECTED_MODELS   # gather keeps the calls' order
    for index, result in enumerate(results):                         # each result is its own call's
        assert result.attempts[-1].input_tokens == tokens(MESSAGES[index])
    lines = whole_lines(tmp_path / "gathered.jsonl")
    assert lines == monitor.records and len(lines) == CALLS + CALLS // 5   # 10 calls fell back
    finals = [rec for rec in lines if rec["final"] is True]
    assert len(finals) == CALLS and len({rec["call_id"] for rec in lines}) == CALLS
    assert {rec["call_id"] for rec in finals} == {result.call_id for result in results}
    assert all(rec["outcome"] == "ok" for rec in finals)

    baseline, baseline_spent = one_after_another(tmp_path)
    assert totals(monitor.records) == totals(baseline)
    assert [row["group"] for row in totals(baseline)] == [BEST, CHEAP]
    assert stripped(monitor.records) == stripped(baseline)
    assert isclose(ledger.spent_usd("all"), baseline_spent, rel_tol=1e-12)
    assert isclose(ledger.spent_usd("all"), fsum(rec["cost_usd"] for rec in lines), rel_tol=1e-12)
    assert ledger.held_usd("all") == 0.0


def test_run_in_executor_takes_the_call_with_its_keywords_as_a_partial(tmp_path):
    executor, monitor, _ = build(tmp_path, "partial")

    async def main(pool):
        loop = asyncio.get_running_loop()
        # run_in_executor passes positional arguments only, so the keywords ride in a partial
        return await asyncio.gather(*(loop.run_in_executor(pool, functools.partial(
            executor.call, "judge", MESSAGES[index], validate=check(index))) for index in range(CALLS)))

    with ThreadPoolExecutor(max_workers=8) as pool:
        results = asyncio.run(main(pool))
    assert [result.model for result in results] == EXPECTED_MODELS
    baseline, _ = one_after_another(tmp_path)
    assert stripped(monitor.records) == stripped(baseline)


def test_a_call_held_on_its_worker_thread_leaves_the_event_loop_free(tmp_path):
    held, release = threading.Event(), threading.Event()

    def hold(model_id, messages):
        if messages[0]["content"] == "m-0":
            held.set()
            assert release.wait(10), "the held call was never released"

    executor, monitor, _ = build(tmp_path, "held", hold=hold)

    async def main():
        first = asyncio.create_task(asyncio.to_thread(executor.call, "judge", MESSAGES[0]))
        assert await asyncio.to_thread(held.wait, 10)
        # the loop goes on while the first call waits in its provider: a second call is answered
        second = await asyncio.to_thread(executor.call, "judge", MESSAGES[1])
        first_done = first.done()
        release.set()
        return first_done, second, await first

    first_done, second, first = asyncio.run(main())
    assert first_done is False and second.model == first.model == CHEAP
    # the second call's record is written first, so a reader joins records by call_id, not position
    assert [rec["call_id"] for rec in monitor.records] == [second.call_id, first.call_id]


def test_an_await_that_times_out_leaves_its_call_to_end_write_its_record_and_settle(tmp_path):
    held, release = threading.Event(), threading.Event()

    def hold(model_id, messages):
        held.set()
        assert release.wait(10), "the held call was never released"

    executor, monitor, ledger = build(tmp_path, "timeout", hold=hold)

    async def main():
        call = asyncio.create_task(asyncio.to_thread(executor.call, "judge", MESSAGES[0]))
        # the call is in its provider, its hold placed, before the await's clock starts (review iter-513
        # should-fix 2): it cannot end before release, so the timeout is certain whatever the load
        assert await asyncio.to_thread(held.wait, 10)
        try:
            await asyncio.wait_for(call, 0.05)
        except asyncio.TimeoutError:
            timed_out = True
        else:
            timed_out = False
        state = (timed_out, len(monitor.records), ledger.held_usd("all"))
        release.set()
        return state

    # asyncio.run ends by shutting down its default executor, so it returns once the call has ended
    timed_out, records_then, held_then = asyncio.run(main())
    assert timed_out is True and records_then == 0 and held_then > 0.0
    [rec] = monitor.records
    assert rec["final"] is True and rec["outcome"] == "ok" and rec["model"] == CHEAP
    assert whole_lines(tmp_path / "timeout.jsonl") == [rec]
    assert ledger.held_usd("all") == 0.0
    assert isclose(ledger.spent_usd("all"), rec["cost_usd"], rel_tol=1e-12)


def test_a_timed_out_gather_cancels_the_calls_still_queued_for_a_worker(tmp_path):
    # review iter-513 should-fix 1: a call that has not started is cancelled with its await and never runs
    held, release = threading.Event(), threading.Event()

    def hold(model_id, messages):
        if messages[0]["content"] == "m-0":
            held.set()
            assert release.wait(10), "the held call was never released"

    executor, monitor, ledger = build(tmp_path, "queued", hold=hold)

    async def main(pool):
        loop = asyncio.get_running_loop()
        calls = asyncio.gather(*(loop.run_in_executor(pool, functools.partial(executor.call, "judge", MESSAGES[index]))
                                 for index in range(3)))
        assert await asyncio.to_thread(held.wait, 10)   # call 0 holds the one worker; calls 1 and 2 wait for it
        try:
            await asyncio.wait_for(calls, 0.05)
        except asyncio.TimeoutError:
            timed_out = True
        else:
            timed_out = False
        state = (timed_out, len(monitor.records), ledger.held_usd("all"))
        release.set()
        return state

    with ThreadPoolExecutor(max_workers=1) as pool:   # its shutdown waits for the started call
        timed_out, records_then, held_then = asyncio.run(main(pool))
    assert timed_out is True and records_then == 0 and held_then > 0.0
    # only the started call ran: one provider call, one record, and its hold the only one settled
    assert [messages for _, messages in executor.provider.fake.calls] == [MESSAGES[0]]
    [rec] = whole_lines(tmp_path / "queued.jsonl")
    assert rec == monitor.records[0] and rec["final"] is True and rec["input_tokens"] == tokens(MESSAGES[0])
    assert ledger.held_usd("all") == 0.0
    assert isclose(ledger.spent_usd("all"), rec["cost_usd"], rel_tol=1e-12)


def test_a_pool_submit_shadow_runner_gives_100_records_once_the_pool_is_shut_down(tmp_path):
    with ThreadPoolExecutor(max_workers=4) as pool:   # every shadow job has run once the pool is shut down
        executor, monitor, ledger = build(tmp_path, "shadowed", shadow_runner=pool.submit,
                                          task_fields={"shadow_rate": 1.0, "shadow_route": BEST})

        async def main():
            return await asyncio.gather(*(asyncio.to_thread(executor.call, "judge", MESSAGES[index])
                                          for index in range(CALLS)))

        results = asyncio.run(main())   # the calls have returned before the pool shuts down (review iter-513 nit 4)
    assert [result.model for result in results] == [CHEAP] * CALLS
    lines = whole_lines(tmp_path / "shadowed.jsonl")
    assert lines == monitor.records and len(lines) == 2 * CALLS
    assert len({rec["call_id"] for rec in lines}) == 2 * CALLS
    assert sum(rec["shadow"] is True for rec in lines) == CALLS
    pairs = shadow_pairs(monitor.records)
    assert len(pairs) == CALLS
    assert {pair["pair_id"] for pair in pairs} == {result.call_id for result in results}
    assert all((pair["routed_route"], pair["shadow_route"]) == (CHEAP, BEST) for pair in pairs)
    assert isclose(ledger.spent_usd("all"), fsum(rec["cost_usd"] for rec in lines), rel_tol=1e-12)
    assert ledger.held_usd("all") == 0.0


# --- the documents -------------------------------------------------------------------------------

COROUTINE_SENTENCE = (
    "A service built on an asyncio event loop calls the executor from a coroutine with "
    "`await asyncio.to_thread(executor.call, task_name, messages, ...)`, so each call blocks only the worker "
    "thread that runs it and the rules for request threads above hold there, while an await that times out or "
    "is cancelled stops waiting but not a call that has started, which still runs to its end, writes its records "
    "and settles its budget hold (`DESIGN.md` 7).")
LIMITS_SENTENCE = ("No async execution or streaming. A coroutine can still await `.call` on a worker thread with "
                   "`asyncio.to_thread` ([Running it in production](#running-it-in-production)). ")
NO_DASH = ("\u2014", "\u2013")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_design_7_states_v1_657_and_14_points_at_it():
    design = read("DESIGN.md")
    seven = design.split("\n## 7. ", 1)[1].split("\n## 8. ", 1)[0]
    lines = seven.splitlines()
    [head] = [i for i, line in enumerate(lines) if line.startswith("- v1.657 a coroutine (row PROD1e): ")]
    block = [lines[head]] + [line for line in lines[head + 1:head + 8] if line.startswith("  - ")]
    assert [line.split(":", 1)[0] for line in block[1:]] == [
        "  - Threads", "  - Shadows", "  - Timeouts and cancellation", "  - Tests (tests/test_asyncio_calls.py)",
        "  - README", "  - Not in this version"]
    text = "\n".join(block)
    for kept in ("with no new API",
                 "a coroutine awaits `asyncio.to_thread(executor.call, task_name, messages, ...)`",
                 "`loop.run_in_executor(pool, functools.partial(executor.call, task_name, messages, ...))`",
                 "since `run_in_executor` passes positional arguments only",
                 "so each blocks only the worker thread that runs it",
                 "the worker threads are request threads in v1.616's sense, so its rules hold unchanged",
                 "a `shadow_runner` may be a thread pool's `submit` (v1.617)",
                 "so a coroutine awaits `asyncio.to_thread(pool.shutdown)`",
                 "stops waiting but does not stop a call that has started, since a running thread cannot be cancelled",
                 "A call still queued for a worker is cancelled with its await and never runs, so it makes no "
                 "provider call, places no hold and writes no record",
                 "once its calls have returned, since a `submit` on a pool that is shut down raises out of `.call`",
                 "while a call on a pool of the caller's own is waited on by that pool's `shutdown`",
                 "its records are written and its hold is settled",
                 "A deadline for a provider call is the task's `timeout_s` (4.2)",
                 "from Python 3.12 for at most 300 seconds, after which it warns and returns",
                 "they pass on v1.656's code (4b59c1e), so the slice has no red commit",
                 "the third entry of tests/test_readme_trim.py's `LATER` (5.2 v1.655)",
                 "native async, that is `async def` methods or an async provider, and streaming (14)"):
        assert text.count(kept) == 1, kept
    assert seven.index("\n- v1.642 a call's policy on its records (") < seven.index("\n" + lines[head])
    # the last clause of section 7 until v1.678 (row DEL1e), whose pair call follows it
    assert lines[lines.index(block[-1]) + 1].startswith("- v1.678 a pair through the executor (row DEL1e, ")
    assert all(len(line.encode("utf-8")) <= 6_000 and not any(d in line for d in NO_DASH) for line in block)
    fourteen = design.split("\n## 14. ", 1)[1]
    assert fourteen.count("\n- Native vendor SDK adapters (the OpenAI-compatible adapter covers gateways), async "
                          "execution (a coroutine awaits the blocking `.call` on a worker thread, 7 v1.657), "
                          "streaming\n") == 1


def test_the_changelog_names_v1_657():
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.657 (")]
    assert line.startswith("- v1.657 (2026-11-25): docs and tests (7, 14, row PROD1e). ")
    assert "`asyncio.to_thread(executor.call, ...)`" in line and "no package module or transcript changes" in line
    assert "does not stop a call that has started" in line and "while a queued call never runs" in line
    assert len(line.encode("utf-8")) <= 600 and not any(d in line for d in NO_DASH)


def test_the_production_section_ends_with_the_coroutine_sentence():
    text = read("README.md")
    body = text.split("\n## Running it in production\n", 1)[1].split("\n## ", 1)[0]
    paragraphs = body.strip().split("\n\n")
    assert COROUTINE_SENTENCE in paragraphs and text.count(COROUTINE_SENTENCE) == 1
    assert ". " not in COROUTINE_SENTENCE                 # one sentence, as the row asks
    assert not any(d in COROUTINE_SENTENCE for d in NO_DASH)
    at = paragraphs.index(COROUTINE_SENTENCE)
    assert paragraphs[at - 1].startswith("A monitor that runs for a service's life need not hold every record ")
    assert len(COROUTINE_SENTENCE.encode("utf-8")) == 443   # tests/test_readme_trim.py's LATER entry, less 2


def test_the_limitations_gain_one_sentence_after_the_async_clause():
    limits = read("README.md").split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    assert limits.count(LIMITS_SENTENCE) == 1 and limits.count("asyncio") == 1
    assert limits.count(LIMITS_SENTENCE + "The OpenAI-compatible adapter covers gateways; ") == 1
