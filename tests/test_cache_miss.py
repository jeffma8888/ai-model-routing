"""DESIGN 4.2, 8.1, 8.2 and 8.3 v1.692 (row CACHE2a): a monitor given the tasks flags a cache that stops hitting.

`Task.min_cache_hit_rate` (None, no floor) and `Task.cache_miss_calls` (10) set a floor on a route's prompt-cache
hit rate and the window it is read over. `Monitor(path=None, *, keep_records=True, tasks=None, on_anomaly=None)`
keeps, per task and model, the cached and input tokens of the last `cache_miss_calls` attempt records that carry a
cached-token count, and when a full window's rate, cached over input tokens as `report --cache` sums them, falls
under the floor it writes one anomaly record (`anomaly: cache_miss`) right after the attempt record, once per run
of misses, and calls `on_anomaly` with a copy once its lock is released. Every log reader drops anomaly records
(8.3 v1.692). With no floor every record and file line keeps its bytes. The scenario logs, the 8.1 table reader and
the readers are tests/test_record_keys.py's and tests/test_record_mode.py's.
"""

import dataclasses
import inspect
import json
import re
from pathlib import Path

import pytest

import model_routing
from model_routing import Completion, Executor, FakeProvider, Monitor, Task, load_tasks
from model_routing import demo
from model_routing import monitor as monitor_module
from test_record_keys import JSON_TYPES, router, scenarios, table
from test_record_mode import DAY2, readers, result

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["ts", "call_id", "task", "model", "anomaly", "cache_hit_rate", "min_cache_hit_rate", "cache_miss_calls",
        "cached_input_tokens", "cache_counted_input_tokens"]


def attempt(n, cached, size=1000, task="t", model="x/a", **extra):
    """A hand-built attempt record, ``cached`` None for one without a cached-token count."""
    rec = {"ts": f"2026-11-25T00:00:{n:02d}Z", "call_id": f"c-{n}", "task": task, "flavor": "cost_effective",
           "model": model, "family": "x", "attempt": 0, "final": True, "outcome": "ok", "error": None,
           "latency_ms": 5.0, "input_tokens": size, "output_tokens": 10}
    if cached is not None:
        rec["cached_input_tokens"] = cached
    rec.update(cost_usd=0.001, routing_cost_usd=0.001, below_bar=False, basis="routed", tags={}, slice=None)
    rec.update(extra)
    return rec


def stream(counts, start=0, **extra):
    return [attempt(start + n, cached, **extra) for n, cached in enumerate(counts)]


def anomalies(records):
    return [rec for rec in records if "anomaly" in rec]


def watched(path=None, floor=0.5, calls=10, on_anomaly=None, **more):
    tasks = {"t": Task("t", 0.5, min_cache_hit_rate=floor, cache_miss_calls=calls), **more}
    return Monitor(path, tasks=tasks, on_anomaly=on_anomaly)


def run(monitor, records):
    for rec in records:
        monitor.record(rec)
    return monitor.records


def expected(rec, rate, cached, counted, floor=0.5, calls=10, model="x/a"):
    return {"ts": rec["ts"], "call_id": rec["call_id"], "task": "t", "model": model, "anomaly": "cache_miss",
            "cache_hit_rate": rate, "min_cache_hit_rate": floor, "cache_miss_calls": calls,
            "cached_input_tokens": cached, "cache_counted_input_tokens": counted}


# --- 4.2 v1.692: the fields ---------------------------------------------------------------------

def test_the_two_fields_are_the_last_with_their_defaults():
    names = [f.name for f in dataclasses.fields(Task)]
    assert names[-3:] == ["max_delegation_depth", "min_cache_hit_rate", "cache_miss_calls"]
    task = Task("t", 0.5)
    assert (task.min_cache_hit_rate, task.cache_miss_calls) == (None, 10)
    for value in (0, 1, 0.0, 0.7, 1.0):
        assert Task("t", 0.5, min_cache_hit_rate=value).min_cache_hit_rate == value
    for value in (1, 10, 50):
        assert Task("t", 0.5, cache_miss_calls=value).cache_miss_calls == value


@pytest.mark.parametrize("value", [True, False, -0.01, 1.01, float("nan"), float("inf"), "0.5", [0.5]])
def test_a_bad_floor_is_a_value_error_naming_the_task(value):
    with pytest.raises(ValueError, match=r"task 't': min_cache_hit_rate must be None or a finite number in \[0, 1\]"):
        Task("t", 0.5, min_cache_hit_rate=value)


@pytest.mark.parametrize("value", [0, -1, True, 2.0, "10", None])
def test_a_bad_window_is_a_value_error_naming_the_task(value):
    with pytest.raises(ValueError, match=r"task 't': cache_miss_calls must be an int >= 1 that is not a bool"):
        Task("t", 0.5, cache_miss_calls=value)


def test_load_tasks_reads_both_and_a_row_without_them_gets_the_defaults(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "min_cache_hit_rate": 0.6, "cache_miss_calls": 4},
                                          {"name": "b", "bar": 0.5, "min_cache_hit_rate": None}]}), encoding="utf-8")
    tasks = load_tasks(path)
    assert (tasks["a"].min_cache_hit_rate, tasks["a"].cache_miss_calls) == (0.6, 4)
    assert (tasks["b"].min_cache_hit_rate, tasks["b"].cache_miss_calls) == (None, 10)


def test_the_demo_tasks_file_holds_each_key_only_when_it_is_not_its_default():
    plain = json.loads(demo._tasks_json(Task("t", 0.5)))["tasks"][0]
    assert "min_cache_hit_rate" not in plain and "cache_miss_calls" not in plain
    floored = json.loads(demo._tasks_json(Task("t", 0.5, min_cache_hit_rate=0.4, cache_miss_calls=3)))["tasks"][0]
    assert (floored["min_cache_hit_rate"], floored["cache_miss_calls"]) == (0.4, 3)


# --- 8.2 v1.692: the check ------------------------------------------------------------------------

def test_the_parameters_are_keyword_only_after_keep_records():
    params = inspect.signature(Monitor).parameters
    assert list(params) == ["path", "keep_records", "tasks", "on_anomaly"]
    for name in ("tasks", "on_anomaly"):
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY and params[name].default is None


def test_twenty_cached_attempts_then_ten_uncached_give_one_anomaly(tmp_path):
    path = tmp_path / "calls.jsonl"
    monitor = watched(path)
    records = stream([900] * 20 + [0] * 10)
    out = run(monitor, records)
    # after the k-th uncached attempt the window holds (10 - k) * 900 cached of 10,000 input tokens: 0.54 at k = 4,
    # 0.45 at k = 5, the first under 0.5, so the record follows attempt 24 and the run gives no second one
    assert anomalies(out) == [expected(records[24], 0.45, 4500, 10000)]
    assert out[:25] == records[:25] and out[25] == anomalies(out)[0] and out[26:] == records[25:]
    assert [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()] == out


def test_a_window_that_recovers_arms_the_check_again():
    records = stream([900] * 20 + [0] * 10 + [900] * 10 + [0] * 10)
    found = anomalies(run(watched(), records))
    # the second run of misses starts after ten cached attempts filled the window at 0.9 again
    assert found == [expected(records[24], 0.45, 4500, 10000), expected(records[44], 0.45, 4500, 10000)]


def test_a_rate_at_the_floor_is_no_miss():
    records = stream([900] * 20 + [0] * 10)
    # 0.45 at k = 5 equals the floor; 3,600 of 10,000 at k = 6 is under it
    assert anomalies(run(watched(floor=0.45), records)) == [expected(records[25], 0.36, 3600, 10000, floor=0.45)]


def test_a_window_not_yet_full_gives_none():
    assert anomalies(run(watched(), stream([0] * 9))) == []
    records = stream([0] * 10)
    assert anomalies(run(watched(), records)) == [expected(records[9], 0.0, 0, 10000)]


def test_a_window_whose_input_sums_to_zero_has_no_rate():
    assert anomalies(run(watched(calls=3), stream([0] * 5, size=0))) == []


def test_an_attempt_without_a_count_leaves_the_window_as_it_was():
    records = stream([900] * 20 + [None] * 10 + [0] * 5)
    # the ten unknown attempts are passed by, so at the fifth uncached one the window is 5 cached and 5 uncached
    assert anomalies(run(watched(), records)) == [expected(records[34], 0.45, 4500, 10000)]


def test_each_task_and_model_has_its_own_window():
    records = []
    for n in range(10):
        records += [attempt(3 * n, 0, model="x/a"), attempt(3 * n + 1, 1000, model="x/b"),
                    attempt(3 * n + 2, 0, task="u", model="x/a")]
    records += [attempt(40 + n, 0, task="v") for n in range(10)]
    monitor = watched(u=Task("u", 0.5))
    # x/a's misses alone; task u has no floor and task v is not in `tasks`
    assert anomalies(run(monitor, records)) == [expected(records[27], 0.0, 0, 10000)]


def test_a_shadow_record_counts_by_its_model_and_a_slice_with_its_task():
    records = stream([0] * 5, slice="deep") + stream([0] * 5, start=5)
    records += stream([0] * 10, start=10, model="x/shadow", shadow=True)
    found = anomalies(run(watched(), records))
    assert found == [expected(records[9], 0.0, 0, 10000), expected(records[19], 0.0, 0, 10000, model="x/shadow")]


def test_a_budget_mode_or_anomaly_record_is_stored_and_read_by_no_window():
    others = [{"ts": "x", "call_id": "b", "task": "t", "budget_event": "warn", "model": "x/a", "input_tokens": 1000,
               "cached_input_tokens": 0},
              {"ts": "x", "call_id": "m", "task": "t", "model": "x/a", "advised_mode": "inline", "input_tokens": 1000,
               "cached_input_tokens": 0},
              dict(expected(attempt(0, 0), 0.0, 0, 10000), input_tokens=1000)]
    records = stream([900] * 10) + others * 4 + stream([0] * 4, start=10)
    assert run(watched(), records) == records


def test_a_record_of_a_floored_task_with_a_bad_count_is_a_value_error_before_it_is_stored(tmp_path):
    path = tmp_path / "calls.jsonl"
    for bad in (dict(cached_input_tokens=1001), dict(cached_input_tokens=-1), dict(cached_input_tokens=True),
                dict(cached_input_tokens=1.0), dict(input_tokens="1000"), dict(input_tokens=-1, cached_input_tokens=0)):
        monitor = watched(path)
        with pytest.raises(ValueError, match=r"call_id 'c-0': "):
            monitor.record(attempt(0, 0, **bad))
        assert monitor.records == [] and not path.exists()
    # a task without a floor reads no count, so the same record is stored as before
    plain = Monitor(tasks={"t": Task("t", 0.5)})
    plain.record(attempt(0, 0, cached_input_tokens=1001))
    assert len(plain.records) == 1


def test_the_callback_gets_a_copy_once_the_lock_is_released():
    seen = []

    def hook(rec):
        assert not monitor._lock.locked()
        seen.append(rec)
        rec["anomaly"] = "changed"

    monitor = watched(on_anomaly=hook)
    records = stream([0] * 12)
    out = run(monitor, records)
    assert anomalies(out) == [expected(records[9], 0.0, 0, 10000)]
    assert seen == [dict(expected(records[9], 0.0, 0, 10000), anomaly="changed")]


def test_an_exception_from_the_callback_propagates_once_both_records_are_written(tmp_path):
    path = tmp_path / "calls.jsonl"

    def hook(rec):
        raise RuntimeError("alert failed")

    monitor = watched(path, on_anomaly=hook)
    records = stream([0] * 10)
    run(monitor, records[:9])
    with pytest.raises(RuntimeError, match="alert failed"):
        monitor.record(records[9])
    assert monitor.records == records + [expected(records[9], 0.0, 0, 10000)]
    assert len(path.read_text(encoding="utf-8").splitlines()) == 11


@pytest.mark.parametrize("kwargs,message", [
    (dict(tasks=[Task("t", 0.5)]), "tasks must be None or a mapping of str to Task"),
    (dict(tasks={"t": "t"}), "tasks must be None or a mapping of str to Task"),
    (dict(tasks={1: Task("t", 0.5)}), "tasks must be None or a mapping of str to Task"),
    (dict(tasks={}, on_anomaly=5), "on_anomaly must be None or a callable"),
    (dict(on_anomaly=print), "on_anomaly needs tasks"),
])
def test_each_bad_argument_is_a_value_error_at_construction(tmp_path, kwargs, message):
    path = tmp_path / "calls.jsonl"
    with pytest.raises(ValueError, match=re.escape(message)):
        Monitor(path, **kwargs)
    assert not path.exists()


def test_with_no_floor_every_record_and_line_keeps_its_bytes(tmp_path):
    records = stream([900] * 20 + [0] * 10 + [None] * 3)
    lines = []
    for n, kwargs in enumerate(({}, dict(tasks={}), dict(tasks={"t": Task("t", 0.5)}),
                                dict(tasks={"t": Task("t", 0.5, cache_miss_calls=1)}, on_anomaly=print))):
        path = tmp_path / f"calls-{n}.jsonl"
        assert run(Monitor(path, **kwargs), records) == records
        lines.append(path.read_bytes())
    assert len(set(lines)) == 1


def test_an_executor_with_a_watching_monitor_writes_the_record_after_the_attempt_that_tips_it():
    route = router(min_cache_hit_rate=0.5, cache_miss_calls=3)
    counts = iter([800, 800, 800, 0, 0, 0])
    provider = FakeProvider({"x/small": lambda messages: Completion("ok", 1000, 200, cached_input_tokens=next(counts))})
    seen = []
    monitor = Monitor(tasks=route.tasks, on_anomaly=seen.append)
    ids = iter(f"call-{n}" for n in range(6))
    executor = Executor(route, provider, monitor=monitor, now=lambda: "2026-11-25T00:00:00Z",
                        id_factory=lambda: next(ids))
    for _ in range(6):
        assert executor.call("t", [{"role": "user", "content": "hi"}]).model == "x/small"
    kinds = ["anomaly" if "anomaly" in rec else rec["call_id"] for rec in monitor.records]
    assert kinds == ["call-0", "call-1", "call-2", "call-3", "call-4", "anomaly", "call-5"]
    # the window of calls 2 to 4 holds 800 cached of 3,000 input tokens; calls 1 to 3 held 1,600, 0.533333
    assert seen == [{"ts": "2026-11-25T00:00:00Z", "call_id": "call-4", "task": "t", "model": "x/small",
                     "anomaly": "cache_miss", "cache_hit_rate": 0.266667, "min_cache_hit_rate": 0.5,
                     "cache_miss_calls": 3, "cached_input_tokens": 800, "cache_counted_input_tokens": 3000}]
    assert monitor.records[5] == seen[0]


def test_no_script_data_file_or_workflow_names_the_fields_and_the_demo_builds_no_watching_monitor():
    files = [p for d in ("evidence", "research") for p in (ROOT / d).rglob("*.py")]
    files += list((ROOT / "model_routing" / "data").glob("*.json")) + list((ROOT / ".github").rglob("*.yml"))
    assert files
    for path in files:
        text = path.read_text(encoding="utf-8")
        assert "min_cache_hit_rate" not in text and "cache_miss_calls" not in text and "on_anomaly" not in text, path
    built = re.findall(r"Monitor\(([^)]*)\)", (ROOT / "model_routing" / "demo.py").read_text(encoding="utf-8"))
    assert built and all("tasks" not in args for args in built)


# --- 8.1 v1.692: the table ------------------------------------------------------------------------

def test_the_anomaly_table_equals_the_code_list_and_a_record_holds_its_keys_in_order():
    listed = getattr(monitor_module, "ANOMALY_RECORD_KEYS", None)
    assert isinstance(listed, tuple)
    rows = table("Anomaly records:")
    assert [(key, types) for key, types, _, _ in rows] == list(listed)
    assert [key for key, _ in listed] == KEYS
    assert all(since == "v1.692" for _, _, since, _ in rows)
    assert "ANOMALY_RECORD_KEYS" not in model_routing.__all__
    [rec] = anomalies(run(watched(), stream([0] * 10)))
    assert list(rec) == KEYS
    assert all(any(JSON_TYPES[name](rec[key]) for name in types) for key, types in listed)


def test_an_attempt_without_a_string_ts_or_call_id_gives_a_record_without_them():
    records = [{k: v for k, v in attempt(n, 0).items() if k not in ("ts", "call_id")} for n in range(9)]
    records.append(dict(attempt(9, 0), ts=None, call_id=7))
    [rec] = anomalies(run(watched(), records))
    assert list(rec) == KEYS[2:]


def test_8_1_names_the_anomaly_record_and_its_place():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    eight1 = design[design.index("### 8.1 "):design.index("### 8.2 ")]
    [bullet] = [line for line in eight1.splitlines() if line.startswith("- v1.692 anomaly records (row CACHE2a")]
    assert "a record with an `anomaly` key is an anomaly record" in bullet and "`ANOMALY_RECORD_KEYS`" in bullet
    assert eight1.index("\nMode records:\n") < eight1.index("\nAnomaly records:\n")


# --- 8.3 v1.692: every reader passes anomaly records by --------------------------------------------

@pytest.fixture(scope="module")
def logs(tmp_path_factory):
    return scenarios(tmp_path_factory.mktemp("cache-miss"))


def marks(clean):
    """Anomaly records: one on a call of the log, on a day no record has, one audited, one with no ts or call_id."""
    first = next((rec["call_id"] for rec in clean if isinstance(rec.get("call_id"), str)), "none")
    base = expected(attempt(0, 0), 0.0, 0, 10000, model="x/small")
    return [dict(base, ts=DAY2, call_id=first), dict(base, call_id="mode-1"),
            {k: v for k, v in base.items() if k not in ("ts", "call_id")}]


def mixed(records):
    found = marks(records)
    return [found[0]] + records[:1] + [found[1]] + records[1:] + [found[2]]


@pytest.mark.parametrize("reader", list(readers([])))
def test_each_reader_gives_on_a_log_with_anomaly_records_what_it_gives_without_them(logs, reader):
    differ, filled = [], []
    for name, clean in logs.items():
        fn = readers(clean)[reader]
        found = result(fn, clean)
        if result(fn, mixed(clean)) != found:
            differ.append(name)
        if found[0] == "ok" and found[1]:
            filled.append(name)
    assert differ == []
    assert filled


def test_delegation_follow_reads_mode_records_alone(logs):
    for clean in logs.values():
        assert model_routing.delegation_follow(mixed(clean)) == model_routing.delegation_follow(clean)


# --- the spec -------------------------------------------------------------------------------------

def test_design_states_v1_692_in_4_2_8_1_8_2_and_8_3_and_the_changelog_once():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for opening in ("- v1.692 cache hit floor (row CACHE2a): `Task` gains two last fields, after `max_delegation_depth`",
                    "- v1.692 anomaly records (row CACHE2a, 8.2 v1.692): ",
                    "- v1.692 the cache-miss check (row CACHE2a; ",
                    "- v1.692 anomaly records in a log (row CACHE2a, 8.1 v1.692): "):
        assert sum(line.startswith(opening) for line in design.splitlines()) == 1, opening
    assert "\n### 8.2 `Monitor(path=None, *, keep_records=True, tasks=None, on_anomaly=None)`\n" in design
    [line] = [x for x in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if x.startswith("- v1.692 (")]
    assert line.startswith("- v1.692 (2026-11-27): spec, code and tests (4.2, 8.1, 8.2, 8.3, row CACHE2a). ")
    assert len(line.encode("utf-8")) <= 600
