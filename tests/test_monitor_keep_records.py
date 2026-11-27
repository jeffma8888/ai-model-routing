"""A Monitor that keeps no record in memory (DESIGN 8.2 v1.656, row PROD1b).

From v1.656 `Monitor(path, keep_records=False)` writes each record to its log alone and keeps none
in `.records`, so a service that runs one monitor for its life holds no record in memory, and the
log's bytes are those a default monitor writes. The spec picks an opt-out over a newest-N bound: a
bound could drop a call's first attempts while keeping its last, and it moves the index of every
kept record. Without a path, or with a value that is not a bool, the constructor raises
`ValueError`; the argument is keyword-only, and the default keeps v1.655's behaviour.
"""

import inspect
import json
import threading
from pathlib import Path

import pytest

from model_routing import (
    Completion, Executor, FakeProvider, Model, Monitor, Registry, Router, Stats, Task,
    load_records, report,
)

ROOT = Path(__file__).resolve().parents[1]
N = 1000
THREADS = 8
MONITOR_SENTENCE = (
    "A monitor that runs for a service's life need not hold every record in memory: "
    "`Monitor(path, keep_records=False)` writes each record to the log at `path` as the default does "
    "but keeps none in `.records`, so `report` reads the log (`load_records(path)` or `--log PATH`), "
    "and without a path it raises `ValueError`, as it would keep no record anywhere (`DESIGN.md` 8.2).")


def many(record_factory):
    """N records of N / 2 two-attempt calls, each with its own tokens, cost and tag."""
    return [record_factory(call_id=f"call-{i // 2}", attempt=i % 2, final=i % 2 == 1,
                           model="fiction/cheap" if i % 2 == 0 else "fiction/best",
                           input_tokens=100 + i, cost_usd=0.0001 * (i + 1),
                           routing_cost_usd=0.0001 * (i + 1), tags={"n": str(i)})
            for i in range(N)]


# --- 8.2 v1.656: the option ----------------------------------------------------------------------

def test_1000_records_reach_the_file_whole_and_none_stay_in_memory(tmp_path, record_factory):
    recs = many(record_factory)
    kept = Monitor(tmp_path / "kept.jsonl")
    lean = Monitor(tmp_path / "lean.jsonl", keep_records=False)
    start = lean.records
    for rec in recs:
        kept.record(rec)
        lean.record(rec)
    assert lean.records == [] and lean.records is start   # the list it starts as, still empty
    assert kept.records == recs
    data = (tmp_path / "lean.jsonl").read_bytes()
    assert data == (tmp_path / "kept.jsonl").read_bytes()  # byte for byte the default's file
    assert data.count(b"\n") == N == len(data.splitlines())
    assert load_records(tmp_path / "lean.jsonl") == recs
    for by in ("model", "task", "tag:n"):
        assert report(load_records(tmp_path / "lean.jsonl"), by=by) == report(kept.records, by=by)
    assert report(lean.records) == []


def test_the_attribute_holds_the_value_and_the_default_keeps_every_record(tmp_path, record_factory):
    assert Monitor().keep_records is True
    assert Monitor(tmp_path / "a.jsonl").keep_records is True
    assert Monitor(tmp_path / "b.jsonl", keep_records=False).keep_records is False
    named = Monitor(tmp_path / "named.jsonl", keep_records=True)
    default = Monitor(tmp_path / "default.jsonl")
    recs = [record_factory(call_id="a"), record_factory(call_id="b")]
    for rec in recs:
        named.record(rec)
        default.record(rec)
    assert named.records == default.records == recs
    assert (tmp_path / "named.jsonl").read_bytes() == (tmp_path / "default.jsonl").read_bytes()
    memory = Monitor(keep_records=True)
    memory.record(recs[0])
    assert memory.records == [recs[0]] and memory.path is None


@pytest.mark.parametrize("make", [lambda: Monitor(keep_records=False),
                                  lambda: Monitor(None, keep_records=False),
                                  lambda: Monitor(path=None, keep_records=False)])
def test_no_path_and_no_list_is_refused(make):
    with pytest.raises(ValueError, match="keep no record anywhere"):
        make()


@pytest.mark.parametrize("value", [0, 1, None, "no", "False", 0.0, [False]])
def test_keep_records_must_be_a_bool(tmp_path, value):
    path = tmp_path / "calls.jsonl"
    with pytest.raises(ValueError, match=r"keep_records must be a bool, got "):
        Monitor(path, keep_records=value)
    assert not path.exists()


def test_keep_records_is_keyword_only_after_path(tmp_path):
    params = inspect.signature(Monitor).parameters
    # v1.692 (row CACHE2a): `tasks` and `on_anomaly` follow it, tests/test_cache_miss.py
    assert list(params)[:2] == ["path", "keep_records"]
    assert params["path"].default is None
    assert params["keep_records"].kind is inspect.Parameter.KEYWORD_ONLY
    assert params["keep_records"].default is True
    with pytest.raises(TypeError):
        Monitor(tmp_path / "calls.jsonl", False)


def test_threads_with_the_option_write_whole_lines_in_each_threads_order(tmp_path):
    path = tmp_path / "calls.jsonl"
    monitor = Monitor(path, keep_records=False)
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
    text = path.read_text(encoding="utf-8")
    assert text.endswith("\n")
    lines = [json.loads(line) for line in text[:-1].split("\n")]  # a mixed line would not parse
    assert len(lines) == THREADS * 200 and monitor.records == []
    for thread in range(THREADS):
        own = [rec["call_id"] for rec in lines if rec["call_id"].startswith(f"t{thread}-")]
        assert own == [f"t{thread}-{index}" for index in range(200)]


def test_an_executor_with_the_option_logs_every_attempt_and_keeps_none(tmp_path):
    cheap, best = "fiction/cheap", "fiction/best"
    registry = Registry([Model(cheap, "small", 1.0, 2.0, 8000), Model(best, "large", 10.0, 20.0, 8000)])
    task = Task("judge", bar=0.7, min_samples=10)
    stats = Stats()
    stats.add(task.name, cheap, 90, 100)
    stats.add(task.name, best, 100, 100)
    provider = FakeProvider({cheap: lambda messages: Completion("cheap", 1000, 200),
                             best: lambda messages: Completion("best", 1000, 200)})
    path = tmp_path / "calls.jsonl"
    monitor = Monitor(path, keep_records=False)
    executor = Executor(Router(registry, {task.name: task}, stats), provider, monitor=monitor)
    results = [executor.call("judge", [{"role": "user", "content": f"item {i}"}]) for i in range(20)]
    logged = load_records(path)
    assert monitor.records == [] and len(logged) == 20
    assert [rec["call_id"] for rec in logged] == [result.call_id for result in results]
    assert all(rec["model"] == cheap and rec["final"] is True for rec in logged)
    [row] = report(logged, by="task")
    assert row["calls"] == 20 and row["input_tokens"] == 20_000


# --- docs ----------------------------------------------------------------------------------------

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_design_8_2_states_v1_656_and_the_changelog_the_version():
    design = read("DESIGN.md")
    start = design.index("\n### 8.2 ")
    eight2 = design[start:design.index("\n### 8.3 ", start)]
    # v1.692 (row CACHE2a): the heading names `tasks` and `on_anomaly` too, tests/test_cache_miss.py
    assert eight2.startswith("\n### 8.2 `Monitor(path=None, *, keep_records=True, tasks=None, on_anomaly=None)`\n")
    [mine] = [line for line in eight2.splitlines() if line.startswith("- v1.656 `keep_records` (row PROD1b): ")]
    for kept in ("a keyword-only `keep_records=True`, after `path`, so `Monitor(path, False)` raises `TypeError`",
                 "`.records` stays the empty list it starts as",
                 "the file's lines are byte for byte those a default monitor writes for the same records",
                 "while `report(monitor.records)` returns `[]`",
                 "It is an opt-out, not a bound such as a `max_records` that keeps the newest N",
                 "a call can lose its first attempts while its last is kept",
                 "each drop moves the index of every kept record",
                 "`keep_records=False` without a path would keep no record anywhere, so the constructor raises "
                 "`ValueError`",
                 "The default keeps v1.655's behaviour"):
        assert mine.count(kept) == 1, kept
    assert eight2.index("\n- v1.620 `load_logs(") < eight2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.656 (")]
    assert line.startswith("- v1.656 (2026-11-25): spec, code, docs and tests (8.2, row PROD1b). ")
    assert "`Monitor(path, keep_records=False)`" in line and "`ValueError`" in line
    assert len(line.encode("utf-8")) <= 600


def test_the_production_section_ends_with_the_monitor_sentence():
    text = read("README.md")
    body = text.split("\n## Running it in production\n", 1)[1].split("\n## ", 1)[0]
    paragraphs = body.strip().split("\n\n")
    assert MONITOR_SENTENCE in paragraphs and text.count(MONITOR_SENTENCE) == 1
    assert ". " not in MONITOR_SENTENCE            # one sentence, as the row asks
    assert "\u2014" not in MONITOR_SENTENCE and "\u2013" not in MONITOR_SENTENCE
    at = paragraphs.index(MONITOR_SENTENCE)
    assert paragraphs[at - 1].startswith("A log also shows where a cheaper route, ")
