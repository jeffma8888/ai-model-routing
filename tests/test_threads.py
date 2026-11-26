"""One Executor, Monitor and BudgetLedger shared by many threads (DESIGN 7 and 8.2 v1.616, row PROD1c).

From v1.616 one process may share one `Executor`, its `Router`, one `Monitor` and one `BudgetLedger`
across threads. The ledger already works under one lock (4.6); `Monitor.record` holds a lock of its own
from its append to `.records` through the close of the file, so each record is one whole line and
`.records` and the file hold the records in one order. The provider, the callables a caller passes and
a change to the stats while calls run are the caller's to guard, and README `## Running it in
production` ends with one sentence that says so.

On c2859bf a record's line was one write of a file opened in append mode, so the whole-line checks
may pass without the lock (a race need not show); the one-order checks are the ones a missing lock fails.
"""

import json
import threading
from math import fsum, isclose
from pathlib import Path

from model_routing import (
    Budget, BudgetLedger, Completion, Executor, FakeProvider, Model, Monitor, Registry, Router,
    Stats, Task, load_records, report, shadow_pairs,
)

ROOT = Path(__file__).resolve().parents[1]
THREADS, CALLS = 8, 50
CHEAP, BEST = "fiction/cheap", "fiction/best"
REGISTRY = Registry([
    Model(CHEAP, "small", 1.0, 2.0, 8000),
    Model(BEST, "large", 10.0, 20.0, 8000),
])
THREADS_SENTENCE = (
    "One `Executor`, with its `Monitor` and `BudgetLedger`, can serve every request thread of a process: "
    "the ledger and the monitor each work under a lock, so a budget counts the calls in flight on all "
    "threads and each record is one whole line of the log, while your provider, any `id_factory`, "
    "`random`, `now` or `clock` you pass and any change to the stats while calls run are yours to guard, "
    "and each process needs a log of its own, which `report` and `pairs` "
    "read together when given `--log PATH` once per log, refusing "
    "a record found in two of them.")  # v1.620, row PROD1d; v1.653 (row PROD1h): the order and the reason are DESIGN 8.2's


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


def provider():
    return FakeProvider({
        CHEAP: lambda messages: Completion("cheap", tokens(messages), 200),
        BEST: lambda messages: Completion("best", tokens(messages), 200),
    })


def run_threads(executor):
    """THREADS threads of CALLS calls each, started together; each call's CallResult by message."""
    start = threading.Barrier(THREADS)
    results, errors = {}, []

    def work(thread):
        start.wait()
        try:
            for index in range(CALLS):
                content = f"t{thread}-{thread * CALLS + index}"
                results[content] = executor.call("judge", [{"role": "user", "content": content}])
        except BaseException as exc:  # a failure on a thread must fail the test
            errors.append(exc)

    workers = [threading.Thread(target=work, args=(t,)) for t in range(THREADS)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert errors == []
    return results


def whole_lines(path):
    """Every line of the log, each parsed on its own: a mixed line would not parse."""
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    return [json.loads(line) for line in text[:-1].split("\n")]


def attempts(records):
    return [rec for rec in records if "budget_event" not in rec]


# --- 8.2: the monitor alone ---------------------------------------------------------------------

def test_a_shared_monitor_writes_whole_lines_in_the_order_of_its_records(tmp_path):
    path = tmp_path / "calls.jsonl"
    monitor = Monitor(path)
    start = threading.Barrier(THREADS)

    def work(thread):
        start.wait()
        for index in range(200):  # a long line, so a mixed one shows
            monitor.record({"call_id": f"t{thread}-{index}", "tags": {"pad": "x" * 2000}})

    workers = [threading.Thread(target=work, args=(t,)) for t in range(THREADS)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    lines = whole_lines(path)
    assert len(lines) == len(monitor.records) == THREADS * 200
    assert lines == monitor.records          # one order: what a missing lock breaks
    assert load_records(path) == monitor.records
    for thread in range(THREADS):            # each thread's own records keep its order
        own = [rec["call_id"] for rec in monitor.records if rec["call_id"].startswith(f"t{thread}-")]
        assert own == [f"t{thread}-{index}" for index in range(200)]


def test_a_monitor_without_a_path_keeps_every_record():
    monitor = Monitor()
    start = threading.Barrier(THREADS)

    def work(thread):
        start.wait()
        for index in range(500):
            monitor.record({"call_id": f"t{thread}-{index}"})

    workers = [threading.Thread(target=work, args=(t,)) for t in range(THREADS)]
    for worker in workers:
        worker.start()
    for worker in workers:
        worker.join()
    assert sorted(rec["call_id"] for rec in monitor.records) == sorted(
        f"t{t}-{i}" for t in range(THREADS) for i in range(500))


# --- 7: one executor, monitor and ledger --------------------------------------------------------

def test_400_calls_on_8_threads_share_one_executor_monitor_and_ledger(tmp_path):
    path = tmp_path / "calls.jsonl"
    monitor = Monitor(path)
    ledger = BudgetLedger([Budget("all", 100.0, "refuse"), Budget("watch", 0.5, "warn")])
    prov = provider()
    results = run_threads(Executor(router(), prov, monitor=monitor, ledger=ledger))
    assert len(results) == THREADS * CALLS == 400 and len(prov.calls) == 400
    assert len(prov.call_options) == 400     # review iter-467 nit 2
    costs = [result.attempts[0].cost_usd for result in results.values()]
    assert all(len(result.attempts) == 1 and result.model == CHEAP for result in results.values())

    lines = whole_lines(path)
    assert lines == monitor.records and load_records(path) == monitor.records
    calls = attempts(monitor.records)
    assert len(calls) == 400 and all(rec["final"] is True for rec in calls)
    assert len({rec["call_id"] for rec in calls}) == 400
    assert {rec["call_id"] for rec in calls} == {result.call_id for result in results.values()}
    by_id = {rec["call_id"]: rec for rec in calls}
    for result in results.values():            # each record is its own call's
        assert by_id[result.call_id]["input_tokens"] == result.attempts[0].input_tokens
        assert by_id[result.call_id]["cost_usd"] == result.attempts[0].cost_usd

    [row] = report(monitor.records, by="task")
    assert (row["calls"], row["attempts"], row["failed_calls"]) == (400, 400, 0)
    assert abs(row["cost_usd"] - fsum(costs)) <= 1e-6   # report rounds to 6 decimals
    assert isclose(ledger.spent_usd("all"), fsum(costs), rel_tol=1e-12)
    assert isclose(ledger.spent_usd("watch"), fsum(costs), rel_tol=1e-12)
    assert ledger.held_usd("all") == ledger.held_usd("watch") == 0.0
    # each warn crossing once, whichever thread's settle crossed it (4.6, 8.1 v1.598)
    warns = [rec for rec in monitor.records if rec.get("budget_event") == "warn"]
    assert sorted(rec["share"] for rec in warns) == [0.5, 0.8, 1.0]
    assert [event["share"] for event in ledger.events] == [0.5, 0.8, 1.0]
    assert len(lines) == 403


def test_400_shadowed_calls_on_8_threads_pair_each_routed_call_with_its_own_shadow(tmp_path):
    path = tmp_path / "calls.jsonl"
    monitor = Monitor(path)
    prov = provider()
    results = run_threads(Executor(router(shadow_rate=1.0, shadow_route=BEST), prov, monitor=monitor))
    assert len(prov.calls) == 800
    lines = whole_lines(path)
    assert lines == monitor.records and len(lines) == 800
    assert len({rec["call_id"] for rec in lines}) == 800
    pairs = shadow_pairs(monitor.records)  # 8.3 v1.618: these calls ran no validate
    assert len(pairs) == 400
    assert {pair["pair_id"] for pair in pairs} == {result.call_id for result in results.values()}
    shadows = {rec["call_id"]: rec for rec in lines if rec["shadow"] is True}
    routed = {rec["call_id"]: rec for rec in lines if rec["shadow"] is False}
    for pair in pairs:                         # the shadow ran the same messages as its routed call
        assert (pair["routed_route"], pair["shadow_route"]) == (CHEAP, BEST)
        shadow = shadows[pair["shadow_call_id"]]
        assert shadow["pair_id"] == pair["pair_id"]
        assert shadow["input_tokens"] == routed[pair["pair_id"]]["input_tokens"]


# --- the documents -------------------------------------------------------------------------------

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_design_7_and_8_2_hold_the_v1_616_clauses():
    design = read("DESIGN.md")
    seven = design.split("\n## 7. ", 1)[1].split("\n## 8. ", 1)[0]
    monitor = design.split("\n### 8.2 ", 1)[1].split("\n### 8.3 ", 1)[0]
    assert seven.count("\n- v1.616 threads (row PROD1c): one process may share one `Executor`") == 1
    assert "\n  - The caller's to guard: a provider of its own" in seven
    assert monitor.count("\n- v1.616 threads (row PROD1c, 7 v1.616): a `Monitor` holds a "
                         "`threading.Lock`") == 1
    [line] = [line for line in read("CHANGELOG.md").split("\n") if line.startswith("- v1.616 (")]
    assert line.startswith("- v1.616 (2026-11-23): spec, code, docs and tests (7, 8.2, row PROD1c). ")


def test_the_production_section_holds_the_sentence_on_threads_then_the_policy():
    text = read("README.md")
    body = text.split("\n## Running it in production\n", 1)[1].split("\n## ", 1)[0]
    paragraphs = body.strip().split("\n\n")
    # v1.625 (row POL1d): the paragraph on a tenant's policy follows it (tests/test_policy_cli.py)
    assert THREADS_SENTENCE in paragraphs and text.count(THREADS_SENTENCE) == 1  # v1.630: anchored on content
    assert paragraphs[paragraphs.index(THREADS_SENTENCE) + 1].startswith("A tenant's rules hold whatever a route costs. ")
    # v1.619 (row CANARY1e): the two paragraphs on shadow calls sit between the promotion check and it
    at = paragraphs.index(THREADS_SENTENCE)
    assert paragraphs[at - 2].startswith("A share of routed calls can also go to a reference route, ")
    assert paragraphs[at - 1].startswith("Every record of a shadowed call carries `pair_id`, ")
    assert paragraphs[at - 3].endswith("and `promote` changed no route or file.")
    assert ". " not in THREADS_SENTENCE      # one sentence, as the row asks
