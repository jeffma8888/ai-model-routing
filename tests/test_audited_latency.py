"""Each audited call's row carries its route entry's time: `audited_results` (DESIGN 8.3 v1.637,
row LAT2), so `select --window` holds a route to a task's latency bar (5.2 v1.628) on the window's
times.

At v1.636 a row copied no `latency_ms`, so on a task with `max_p95_ms` a window's stats held no time:
under `latency_unknown` "allow" a route whose recent calls were slow was admitted on its successes
alone, and under "deny" every route was ruled out as `latency_unknown`, however fast. A plain record's
row now has its record's time, a cascade's the `math.fsum` of its legs', a procedure's its closing
record's alone, which times the whole run; a value that is not a finite number >= 0 gives no time, and
a failed entry before the row's is not added. With no bar every `select --window` and `drift` output
keeps the bytes it prints on the same log with no times, which is what v1.636 read of it."""

import contextlib
import io
import json
import math
from datetime import date
from pathlib import Path

import pytest

import model_routing
from model_routing import (
    Cascade, Completion, Executor, FakeProvider, Model, Monitor, Procedure, ProcedureResult,
    ProviderError, Registry, Router, Stats, Task,
)
from model_routing.cli import main
from model_routing.stats import calibrate_from_results

ROOT = Path(__file__).resolve().parents[1]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
CASCADE = Cascade(CHEAP, MID, "sig")
C = CASCADE.id
NEW = "2026-11-20T00:00:00.000+00:00"
TODAY = date(2026, 11, 24)
MESSAGES = [{"role": "user", "content": "q"}]
REGISTRY = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000),
                     Model(BEST, "large", 10.0, 20.0, 8000)])


def audited(*args, **kwargs):
    return model_routing.audited_results(*args, **kwargs)


def rec(call_id, model, outcome, final=True, attempt=0, latency=5.0, **extra):
    out = {"ts": NEW, "call_id": call_id, "task": "judge", "flavor": "cost_effective",
           "model": model, "family": "fiction", "attempt": attempt, "final": final,
           "outcome": outcome, "error": None, "latency_ms": latency, "input_tokens": 1000,
           "output_tokens": 200, "cost_usd": 0.001, "routing_cost_usd": 0.001,
           "below_bar": False, "basis": "measured", "tags": {}, "slice": None}
    out.update(extra)
    return out


def leg(call_id, model, outcome, escalated, **kwargs):
    return rec(call_id, model, outcome, cascade=C, escalated=escalated, **kwargs)


def call_of(call_id, outcome="ok", **kwargs):          # a model call of a procedure's run
    return rec(call_id, CHEAP, outcome, final=False, procedure="poll", procedure_version="v1",
               **kwargs)


def closing(call_id, outcome="ok", **kwargs):
    fields = dict(attempt=1, procedure="poll", procedure_version="v1", model_calls=1, tool_calls=3,
                  tool_cost_usd=0.0005, input_tokens=0, output_tokens=0, cost_usd=0.0005)
    fields.update(kwargs)
    return rec(call_id, "proc:poll@v1+fiction/cheap", outcome, **fields)


def times(rows):
    return [(r["model"], r["item"], r.get("latency_ms")) for r in rows]


# --- the time of each row ----------------------------------------------------------------------

def test_a_plain_row_carries_its_records_time_as_a_float_before_slice():
    rows = audited([rec("a", CHEAP, "ok", latency=12.5, slice="long"), rec("b", CHEAP, "ok", latency=7)],
                   {"a": True, "b": True})
    assert list(rows[0]) == ["task", "model", "item", "correct", "input_tokens", "output_tokens",
                             "latency_ms", "slice"]
    assert list(rows[1])[-1] == "latency_ms"
    assert times(rows) == [(CHEAP, "a", 12.5), (CHEAP, "b", 7.0)]
    assert type(rows[1]["latency_ms"]) is float


def test_a_call_that_falls_back_gives_each_row_its_own_entrys_time_not_the_sum():
    log = [rec("a", CHEAP, "invalid", final=False, latency=300.0), rec("a", MID, "ok", attempt=1, latency=40.0),
           rec("b", CHEAP, "error", final=False, latency=5000.0), rec("b", MID, "ok", attempt=1, latency=40.0)]
    assert times(audited(log, {"a": True, "b": True})) == [(CHEAP, "a", 300.0), (MID, "a", 40.0),
                                                          (MID, "b", 40.0)]


def test_a_cascade_row_sums_its_legs_and_a_kept_cheap_answer_has_its_own():
    log = [leg("a", CHEAP, "ok", True, final=False, latency=100.0), leg("a", MID, "ok", True, attempt=1,
                                                                       latency=900.0),
           leg("b", CHEAP, "ok", False, latency=100.0),
           leg("c", CHEAP, "ok", True, final=False, latency=0.1), leg("c", MID, "invalid", True, final=False,
                                                                     attempt=1, latency=0.2),
           rec("c", BEST, "ok", attempt=2, latency=3.0)]
    rows = audited(log, dict.fromkeys("abc", True))
    assert times(rows) == [(C, "a", 1000.0), (C, "b", 100.0), (C, "c", math.fsum([0.1, 0.2])), (BEST, "c", 3.0)]
    assert list(rows[0]) == ["task", "model", "item", "correct", "escalated", "latency_ms"]


def test_a_procedure_row_has_its_closing_records_time_alone_since_it_times_the_whole_run():
    rows = audited([call_of("a", latency=250.0), closing("a", latency=1250.0)], {"a": True})
    assert times(rows) == [("proc:poll@v1+fiction/cheap", "a", 1250.0)]
    assert list(rows[0]) == ["task", "model", "item", "correct", "cost_usd", "latency_ms"]
    rows = audited([call_of("a", latency=None), closing("a", latency=1250.0)], {"a": True})
    assert times(rows) == [("proc:poll@v1+fiction/cheap", "a", 1250.0)]   # a model call's time is not read


@pytest.mark.parametrize("value", [None, True, False, -1, -0.5, float("nan"), float("inf"), "5", [5]])
def test_a_time_that_is_no_finite_number_at_or_above_0_gives_a_row_without_one(value):
    log = [rec("a", CHEAP, "ok", latency=value), leg("b", CHEAP, "ok", True, final=False, latency=value),
           leg("b", MID, "ok", True, attempt=1), closing("c", attempt=0, model_calls=0, latency=value)]
    rows = audited(log, dict.fromkeys("abc", True))
    assert [len(rows), [r for r in rows if "latency_ms" in r]] == [3, []]
    assert calibrate_from_results(rows).latencies("judge", CHEAP) == ()


def test_a_missing_time_or_a_sum_past_the_largest_float_gives_none():
    bare = {k: v for k, v in rec("a", CHEAP, "ok").items() if k != "latency_ms"}
    log = [bare, leg("b", CHEAP, "ok", True, final=False, latency=1e308),
           leg("b", MID, "ok", True, attempt=1, latency=1e308)]
    assert times(audited(log, {"a": True, "b": True})) == [(CHEAP, "a", None), (C, "b", None)]


def test_zero_is_a_time_and_calibrate_reads_one_per_row_under_both_keys_of_a_slice():
    log = [rec("a", CHEAP, "ok", latency=0), rec("b", CHEAP, "invalid", latency=800.0, slice="long")]
    stats = calibrate_from_results(audited(log, {"a": True, "b": True}))
    assert stats.latencies("judge", CHEAP) == (0.0, 800.0)
    assert stats.latencies("judge@long", CHEAP) == (800.0,)


# --- a real executor log -----------------------------------------------------------------------

class Clock:
    """The executor's clock, in seconds; each scripted provider call moves it on."""

    def __init__(self):
        self.now = 0.0

    def __call__(self):
        return self.now


def taking(clock, seconds, *texts):
    queue = list(texts)

    def complete(messages):
        clock.now += seconds
        if not queue:
            raise ProviderError("outage")
        return Completion(queue.pop(0), 1000, 200)
    return complete


def executor(clock, script, stats, task=None):
    ids = iter(f"call-{i}" for i in range(1000))
    monitor = Monitor()
    task = task or Task("judge", bar=0.7, min_samples=10, cascades=(CASCADE,))
    run = Executor(Router(REGISTRY, {"judge": task}, stats), FakeProvider(script), monitor=monitor,
                   clock=clock, now=lambda: NEW, id_factory=lambda: next(ids))
    return run, monitor


def entry_stats(entry_id=None, **counts):
    """Each plain model measured; with an entry at 100/100, cheap's 50/100 is under the 0.7 bar, so
    the entry is the primary, mid then best its fallbacks; without one, cheap is the primary."""
    stats = Stats()
    for model_id, successes in ((CHEAP, 100 if entry_id is None else 50), (MID, 95), (BEST, 98)):
        stats.add("judge", model_id, successes, 100)
    if entry_id is not None:
        stats.add("judge", entry_id, 100, 100, **counts)
    return stats


def test_a_real_log_of_plain_calls_gives_each_row_its_records_time():
    clock = Clock()
    run, monitor = executor(clock, {CHEAP: taking(clock, 0.25, "bad", "fine"),
                                    MID: taking(clock, 1.5, "good", "late")}, entry_stats())
    for _ in range(3):
        run.call("judge", MESSAGES, validate=lambda text: text != "bad")
    records = monitor.records
    assert [(r["call_id"], r["model"], r["outcome"], r["latency_ms"]) for r in records] == [
        ("call-0", CHEAP, "invalid", 250.0), ("call-0", MID, "ok", 1500.0), ("call-1", CHEAP, "ok", 250.0),
        ("call-2", CHEAP, "error", 250.0), ("call-2", MID, "ok", 1500.0)]
    rows = audited(records, {"call-0": True, "call-1": False, "call-2": True})
    assert times(rows) == [(CHEAP, "call-0", 250.0), (MID, "call-0", 1500.0), (CHEAP, "call-1", 250.0),
                           (MID, "call-2", 1500.0)]


def test_a_real_log_of_a_cascade_and_a_procedure_gives_their_routes_times():
    clock = Clock()
    run, monitor = executor(clock, {CHEAP: taking(clock, 0.25, "c0", "hand1"), MID: taking(clock, 0.5, "m1")},
                            entry_stats(C, escalated=20))
    for _ in range(2):
        run.call("judge", MESSAGES, signals={"sig": lambda text: text.startswith("hand")})
    rows = audited(monitor.records, {"call-0": True, "call-1": True})
    assert times(rows) == [(C, "call-0", 250.0), (C, "call-1", 750.0)]

    tick = Clock()

    def polling(value, call):
        text = call([{"role": "user", "content": "summarize"}])
        tick.now += 1.0                                  # the run's own tool time
        return ProcedureResult("shaped " + text, tool_calls=3, tool_cost_usd=0.0005)

    proc = Procedure("poll", "v1", polling, max_model_calls=2, max_tool_calls=5, model=CHEAP)
    run, monitor = executor(tick, {CHEAP: taking(tick, 0.25, "x")}, entry_stats(proc.id, cost_usd=0.02))
    run.call("judge", MESSAGES, procedures=[proc])
    assert [r["latency_ms"] for r in monitor.records] == [250.0, 1250.0]
    assert times(audited(monitor.records, {"call-0": True})) == [(proc.id, "call-0", 1250.0)]


# --- select --window and drift -----------------------------------------------------------------

BAR = 1000


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, today=TODAY)
    return code, out.getvalue(), err.getvalue()


def write_tasks(path, **bar):
    path.write_text(json.dumps({"tasks": [{"name": "judge", "bar": 0.8, "min_samples": 30,
                                           "expected_input_tokens": 1000, "expected_output_tokens": 200,
                                           **bar}]}), encoding="utf-8")
    return str(path)


@pytest.fixture
def files(tmp_path):
    """A real executor log: 40 calls on the cheap route at 1.5 s each and 40 on the mid route, the
    cheap one excluded, at 0.25 s, every call audited right; the all-time stats.json has the cheap
    route at 460/500 (0.92) and the mid one at 470/500, with no times."""
    (tmp_path / "models.json").write_text(json.dumps({"models": [
        {"id": CHEAP, "family": "small", "price_in": 1.0, "price_out": 2.0, "context_window": 8000},
        {"id": MID, "family": "medium", "price_in": 3.0, "price_out": 6.0, "context_window": 8000}]}),
        encoding="utf-8")
    stats = Stats()
    stats.add("judge", CHEAP, 460, 500)
    stats.add("judge", MID, 470, 500)
    stats.save(tmp_path / "stats.json")
    clock = Clock()
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000)])
    ids = iter(f"call-{i}" for i in range(1000))
    monitor = Monitor()
    run = Executor(Router(registry, {"judge": Task("judge", bar=0.8, min_samples=30)}, stats),
                   FakeProvider({CHEAP: taking(clock, 1.5, *["c"] * 40), MID: taking(clock, 0.25, *["m"] * 40)}),
                   monitor=monitor, clock=clock, now=lambda: NEW, id_factory=lambda: next(ids))
    for _ in range(40):
        run.call("judge", MESSAGES)
        run.call("judge", MESSAGES, exclude_models=[CHEAP])
    records = monitor.records
    assert [r["model"] for r in records[:2]] == [CHEAP, MID] and len(records) == 80
    write = lambda name, rows: (tmp_path / name).write_text(  # noqa: E731
        "".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    write("calls.jsonl", records)
    write("untimed.jsonl", [{k: v for k, v in r.items() if k != "latency_ms"} for r in records])
    write("audits.jsonl", [{"call_id": r["call_id"], "correct": True} for r in records])
    write_tasks(tmp_path / "tasks.json")
    write_tasks(tmp_path / "bar.json", max_p95_ms=BAR)
    write_tasks(tmp_path / "deny.json", max_p95_ms=BAR, latency_unknown="deny")
    return tmp_path


def select(d, tasks, *extra, log="calls.jsonl"):
    return run_cli(["select", "judge", "--json", "--registry", str(d / "models.json"), "--tasks", str(d / tasks),
                    "--window", "30d", "--log", str(d / log), "--audits", str(d / "audits.jsonl"), *extra])


def reasons(out):
    data = json.loads(out)
    return data["primary"], {c["model_id"]: (c["reason"], c.get("p95_latency_ms")) for c in data["candidates"]}


def test_select_window_rules_out_a_route_whose_window_calls_are_slower_than_the_bar(files):
    code, out, err = select(files, "bar.json")
    assert (code, err) == (0, "")
    assert reasons(out) == (MID, {CHEAP: ("too_slow", 1500.0), MID: ("passes", 250.0)})
    assert reasons(select(files, "tasks.json")[1]) == (CHEAP, {CHEAP: ("passes", None), MID: ("passes", None)})
    all_time = run_cli(["select", "judge", "--json", "--registry", str(files / "models.json"),
                        "--tasks", str(files / "bar.json"), "--stats", str(files / "stats.json")])
    assert reasons(all_time[1]) == (CHEAP, {CHEAP: ("passes", None), MID: ("passes", None)})


def test_under_deny_a_window_with_times_admits_the_fast_route(files):
    code, out, err = select(files, "deny.json")
    assert (code, err) == (0, "")
    assert reasons(out) == (MID, {CHEAP: ("too_slow", 1500.0), MID: ("passes", 250.0)})
    code, out, err = select(files, "deny.json", log="untimed.jsonl")   # all v1.636 read of the log
    assert (code, out) == (3, "") and err.startswith("error: no model clears the bar 0.8 for task 'judge'\n")
    assert [line.split()[-1] for line in err.splitlines()[-2:]] == ["latency_unknown"] * 2


@pytest.mark.parametrize("argv", [
    ["select", "judge", "--tasks", "tasks.json"], ["select", "judge", "--tasks", "tasks.json", "--json"],
    ["select", "judge", "--tasks", "tasks.json", "--flavor", "cost_blind"],
    ["drift", "--tasks", "tasks.json"], ["drift", "--tasks", "tasks.json", "--json"],
    ["drift", "--tasks", "tasks.json", "--stats", "stats.json"],
])
def test_with_no_bar_select_and_drift_print_what_they_print_on_the_log_with_no_times(files, argv):
    def call(log):
        args = [str(files / a) if a.endswith(".json") else a for a in argv]
        if args[0] == "select":
            args += ["--registry", str(files / "models.json")]
        return run_cli(args + ["--window", "30d", "--log", str(files / log), "--audits", str(files / "audits.jsonl")])
    timed, untimed = call("calls.jsonl"), call("untimed.jsonl")
    assert timed == untimed and timed[0] == 0 and timed[1]


def test_from_v1_638_drift_on_a_bar_flags_the_route_whose_window_calls_went_over_it(files):
    """8.3 v1.638 (row LAT3): stats.json holds no times, so under "allow" both routes are on time
    all-time; in the window the cheap route's p95 is 1,500 ms, over the 1,000 ms bar, and the mid
    route's 250 ms. Under "deny" no all-time time is not on time, so the fast route came under."""
    def rows(tasks):
        code, out, err = run_cli(["drift", "--tasks", str(files / tasks), "--stats", str(files / "stats.json"),
                                  "--json", "--window", "30d", "--log", str(files / "calls.jsonl"),
                                  "--audits", str(files / "audits.jsonl")])
        assert (code, err) == (0, "")
        return [(r["route"], r["all_time_p95_ms"], r["window_p95_ms"], r["latency_flag"], r["flag"])
                for r in json.loads(out)["rows"]]
    assert rows("bar.json") == [(CHEAP, None, 1500.0, "went_over", None), (MID, None, 250.0, None, None)]
    assert rows("deny.json") == [(CHEAP, None, 1500.0, None, None), (MID, None, 250.0, "came_under", None)]


# --- the spec and the docs ---------------------------------------------------------------------

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_design_and_the_changelog_state_v1_637():
    design = read("DESIGN.md")
    eight3 = design[design.index("\n### 8.3 "):design.index("\n## 9. ")]
    assert eight3.count("\n- v1.637 `audited_results` gives each row its route entry's time (row LAT2, v1.632, "
                        "v1.636, 4.3 v1.626, 5.2 v1.628, 10 v1.634): ") == 1
    assert eight3.index("\n- v1.636 `audited_results`") < eight3.index("\n- v1.637 `audited_results`")
    assert eight3.count("(4.3 v1.626); from v1.637 (row LAT2) a row carries its route entry's time.") == 1
    four3 = design[design.index("\n### 4.3 "):design.index("\n### 4.4 ")]
    assert four3.count("from 8.3 v1.637 (row LAT2) `audited_results` gives each row the time its route entry "
                       "took to its answer") == 1
    ten = design[design.index("\n## 10. "):design.index("\n## 11. ")]
    assert ten.count("from 8.3 v1.637 (row LAT2) they hold each audited call's time, so a task's latency bar "
                     "(5.2 v1.628) reads the window's times") == 1
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.637 (")]
    assert line.startswith("- v1.637 (2026-11-25): spec, code and tests (8.3, row LAT2). ")
    assert len(line.encode("utf-8")) <= 600


def test_the_readme_drift_paragraph_says_select_window_holds_a_route_to_the_bar():
    # v1.647 (row PROD1g): how a cascade's or a procedure's time is read moved to DESIGN 8.3 v1.637
    assert read("README.md").count(
        " On a task with `max_p95_ms`, `select --window` holds each route to the bar on the window's times, and "
        "each `drift` row") == 1
