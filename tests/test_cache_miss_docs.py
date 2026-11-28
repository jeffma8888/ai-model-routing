"""DESIGN 5.2 v1.694 (row CACHE2c, the remainder of row CACHE2): the cache-miss check in README
`## Running it in production`.

No code changes. One paragraph of at most 300 bytes comes right after the one on the prompt cache (v1.673) and
before the first on budgets: `Monitor(path, tasks=..., on_anomaly=...)` (8.2 v1.692) writes a `cache_miss` anomaly
record (8.1 v1.692) and calls `on_anomaly` when a model's hit rate over its last `cache_miss_calls` counted attempts
on a task, those with a cached-token count, falls under the task's `min_cache_hit_rate` (4.2 v1.692), and
`report --anomalies` (10 v1.693) counts those records (8.3 v1.693), with one pointer to DESIGN.md. Each claim is
checked here on the library and the command line beside the words that state it, on tests/test_cache_miss.py's
scenario: 20 attempts with 900 of 1,000 input tokens cached, then 10 with none, a floor of 0.5 and a window of 10.
The bytes are tests/test_readme_trim.py's v1.694 block, and every README transcript keeps its bytes (gates.py).
"""

import argparse
import inspect
import json
from pathlib import Path

from test_cache_miss import expected, stream, watched
from test_readme_production import PRODUCTION, PRODUCTION_CAP, link_problems, paragraphs, size
from test_report_anomalies import cli

from model_routing import Monitor, load_records, report
from model_routing.cli import _build_parser

ROOT = Path(__file__).resolve().parents[1]
CACHE_LEAD = "A prompt cache changes what a call costs, so a route is priced at the cache hits it measured. "
BUDGET_LEAD = "A budget tracks what the executor spends and can warn, refuse or move a call. "
SESSION_LEAD = "A switch mid-session starts cold: "
PARAGRAPH = (
    "A `Monitor(path, tasks=..., on_anomaly=...)` writes a `cache_miss` anomaly record and calls `on_anomaly` "
    "when a model's hit rate over its last `cache_miss_calls` counted attempts on a task falls under the task's "
    "`min_cache_hit_rate`; `report --anomalies` counts them (`DESIGN.md` 4.2, 8 and 10).")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def says(words):
    assert PARAGRAPH.count(words) == 1, words


def logged(tmp_path, records, floor=0.5):
    """``records`` given to a monitor of task t's floor that logs to a file and collects each callback; returns the
    records it holds, the log's path and the callback's arguments."""
    seen = []
    path = tmp_path / "calls.jsonl"
    monitor = watched(path, floor=floor, on_anomaly=seen.append)
    for rec in records:
        monitor.record(rec)
    return monitor.records, str(path), seen


def flags(records):
    return [rec for rec in records if "anomaly" in rec]


# --- README -------------------------------------------------------------------------------------

def test_the_paragraph_follows_the_prompt_cache_one_inside_the_cap():
    text = read("README.md")
    found = paragraphs(text, PRODUCTION)
    # placed by its neighbours (v1.655, row T30); tests/test_readme_trim.py names the section's last paragraph
    assert text.count(PARAGRAPH) == 1 and found.count(PARAGRAPH) == 1
    at = found.index(PARAGRAPH)
    # v1.703 (row CACHE3d): the paragraph on a session's switch comes between this one and the first on budgets
    # (tests/test_session_cli.py)
    assert found[at - 1].startswith(CACHE_LEAD) and found[at + 1].startswith(SESSION_LEAD)
    assert found[at + 2].startswith(BUDGET_LEAD)
    assert len(PARAGRAPH.encode("utf-8")) == 295 <= 300
    assert size(text, PRODUCTION) <= PRODUCTION_CAP == 30_000
    assert "\u2014" not in PARAGRAPH and "\u2013" not in PARAGRAPH and "```" not in PARAGRAPH
    assert link_problems(text) == []


def test_it_names_the_monitor_the_record_the_two_task_fields_and_the_option():
    for name in ("`Monitor(path, tasks=..., on_anomaly=...)`", "`cache_miss`", "calls `on_anomaly`",
                 "`cache_miss_calls`", "`min_cache_hit_rate`", "`report --anomalies`"):
        says(name)
    # README.md named none of them before v1.694 (row CACHE2c), and this paragraph names each where it says
    text = read("README.md")
    assert text.count("min_cache_hit_rate") == text.count("cache_miss_calls") == 1
    assert text.count("on_anomaly") == 2 and text.count("--anomalies") == 1
    assert text.count("`cache_miss`") == 1 and text.count("anomaly record") == 1
    # it links nothing: the paragraph before it links the lesson on the cache hit rate
    assert "](" not in PARAGRAPH and '"' not in PARAGRAPH


def test_the_monitor_s_signature_is_the_one_it_names():
    says("`Monitor(path, tasks=..., on_anomaly=...)`")
    params = inspect.signature(Monitor).parameters
    assert list(params) == ["path", "keep_records", "tasks", "on_anomaly"]
    assert params["path"].kind is inspect.Parameter.POSITIONAL_OR_KEYWORD
    for name in ("tasks", "on_anomaly"):
        assert params[name].kind is inspect.Parameter.KEYWORD_ONLY and params[name].default is None


def test_the_option_is_the_parser_s():
    says("`report --anomalies`")
    parser = _build_parser()
    [sub] = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    options = {o: a for a in sub.choices["report"]._actions for o in a.option_strings}
    assert isinstance(options["--anomalies"], argparse._StoreTrueAction) and not options["--anomalies"].required


# --- its claims, each beside its words ------------------------------------------------------------

def test_it_writes_a_cache_miss_anomaly_record_and_calls_on_anomaly(tmp_path):
    says("writes a `cache_miss` anomaly record and calls `on_anomaly`")
    records = stream([900] * 20 + [0] * 10)
    held, log, seen = logged(tmp_path, records)
    # after the k-th uncached attempt the window holds (10 - k) * 900 cached of 10,000 input tokens: 0.54 at k = 4,
    # 0.45 at k = 5, the first under 0.5, so the one record follows c-24
    want = expected(records[24], 0.45, 4500, 10000)
    assert flags(held) == [want] and want["anomaly"] == "cache_miss"
    assert load_records(log) == held and held[25] == want and held[24] == records[24]
    # the callback gets a copy of the record written, once
    assert seen == [want] and seen[0] is not held[25]


def test_the_window_is_the_model_s_last_counted_attempts_on_the_task(tmp_path):
    says("when a model's hit rate over its last `cache_miss_calls` counted attempts on a task")
    # an attempt without a cached-token count after each uncached one, and another model's fully cached attempt
    # after each of those: neither enters x/a's window, so the k-th uncached attempt of x/a is c-(20 + 3k - 3)
    # and its rate 0.45 at k = 5, c-32, as in the plain scenario
    records = stream([900] * 20)
    for k in range(10):
        n = 20 + 3 * k
        records += stream([0], start=n) + stream([None], start=n + 1) + stream([1000], start=n + 2, model="x/b")
    held, _, seen = logged(tmp_path, records)
    assert records[32]["call_id"] == "c-32" and "cached_input_tokens" not in records[33]
    assert flags(held) == seen == [expected(records[32], 0.45, 4500, 10000)]


def test_it_flags_a_rate_under_the_floor_and_not_one_at_it(tmp_path):
    says("falls under the task's `min_cache_hit_rate`")
    records = stream([900] * 20 + [0] * 10)
    # at a floor of 0.45, k = 5 reads 0.45, the floor, no miss; k = 6 reads 3,600 of 10,000, 0.36, under it
    held, _, seen = logged(tmp_path, records, floor=0.45)
    assert flags(held) == seen == [expected(records[25], 0.36, 3600, 10000, floor=0.45)]


def test_report_anomalies_counts_them(tmp_path):
    says("`report --anomalies` counts them")
    records = stream([900] * 20 + [0] * 10) + stream([800] * 5, start=30, model="x/b")
    held, log, _ = logged(tmp_path, records)
    code, out, err = cli(["report", "--log", log, "--anomalies", "--json"])
    assert (code, err) == (0, "")
    rows = {row["group"]: row["cache_miss_anomalies"] for row in json.loads(out)}
    assert rows == {"x/a": 1, "x/b": 0}
    assert json.loads(out) == report(held, anomalies=True)
    code, out, err = cli(["report", "--log", log, "--by", "task", "--anomalies", "--json"])
    assert (code, err) == (0, "") and [(r["group"], r["cache_miss_anomalies"]) for r in json.loads(out)] == [("t", 1)]


# --- DESIGN ---------------------------------------------------------------------------------------

def test_the_pointer_names_each_part_that_states_a_claim():
    says("(`DESIGN.md` 4.2, 8 and 10).")
    assert PARAGRAPH.endswith("(`DESIGN.md` 4.2, 8 and 10).")
    design = read("DESIGN.md")
    starts = {"4.2": "### 4.2 ", "8": "## 8. ", "10": "## 10. "}
    ends = {"4.2": "### 4.3 ", "8": "## 9. ", "10": "## 11. "}
    part = {k: design[design.index("\n" + v):design.index("\n" + ends[k], design.index("\n" + v))]
            for k, v in starts.items()}
    assert "\n- v1.692 cache hit floor (row CACHE2a): `Task` gains two last fields" in part["4.2"]
    assert "\n- v1.692 anomaly records (row CACHE2a, 8.2 v1.692): " in part["8"]
    assert "\n- v1.692 the cache-miss check (row CACHE2a; " in part["8"]
    assert "\n- v1.693 `report(records, by=\"model\", audits=None, cache=False, shadow=False, anomalies=False)` " in part["8"]
    assert "\n  - v1.693 `report --log PATH [--by model|task] --anomalies` (row CACHE2b, " in part["10"]
    five2 = design[design.index("\n### 5.2 "):design.index("\n### 5.3 ", design.index("\n### 5.2 "))]
    assert "\n- v1.694 README cache-miss check (row CACHE2c, " in five2
    # the Not-in-this-version clauses that named the README sentence's row name the version that adds it
    eight2 = part["8"][part["8"].index("\n### 8.2 "):part["8"].index("\n### 8.3 ")]
    eight3 = part["8"][part["8"].index("\n### 8.3 "):]
    for clause in (eight2, eight3):
        assert clause.count("the README sentence (row CACHE2c, which v1.694 adds in 5.2)") == 1
    assert "(row CACHE2c)." not in design
