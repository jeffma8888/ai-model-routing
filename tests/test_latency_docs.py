"""DESIGN 5.2 and 10 v1.630 (row LAT1c): a task's latency bar on the command line and in the docs.

No code changes. The bar is a task's (4.2 v1.628) and a route's times come from the stats file
(4.3 v1.626), so the command line needs no option: results rows with `latency_ms` go through
`calibrate`, and `select --json` and `delegate --json` show the bar and each candidate's p95, while
the text table names the reason under the header it has without a bar. README `## Running it in
production` ends with a paragraph on the bar, right after the one on a tenant's policy: where a
time comes from, the nearest-rank p95, and how a bar is read off a log without its shadow calls,
which by default `report` counts in its percentiles. research/production-lessons.md's Harvey and Uber
lines say the library applies the bar. With no bar every output keeps its bytes.
"""

import contextlib
import io
import json
import re
from datetime import date
from pathlib import Path

import pytest
from test_readme_production import PRODUCTION, PRODUCTION_CAP, size

from model_routing import DATA_DIR, Stats, report
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 24)
N, BAR = 30, 500
CHEAP, MID, PRICEY = "a/cheap", "b/mid", "c/pricey"
ROWS = [{"id": model_id, "family": model_id[0], "price_in": price, "price_out": 2 * price, "context_window": 100_000}
        for model_id, price in ((CHEAP, 0.1), (MID, 0.5), (PRICEY, 1.0))]
TASK = {"name": "t", "bar": 0.8, "min_samples": N, "expected_input_tokens": 1000, "expected_output_tokens": 200}
WORK = ["--parent", PRICEY, "--context-tokens", "2000", "--brief-tokens", "1000", "--result-tokens", "1000"]

POLICY_START = "A tenant's rules hold whatever a route costs. "
LATENCY_PARAGRAPH = (
    "A task can also hold its routes to a time. A `tasks.json` row's `\"max_p95_ms\"`, in milliseconds, rules out "
    "a route whose 95th-percentile time on the task is above it, reason `too_slow`, after the task's and the "
    "policy's rules and before the success bar, and a cascade or a procedure is held to it on its own times, not "
    "its models'. A route's time is known once it has as many timed trials on the task as the task's "
    "`min_samples`; until then the bar lets it through, or, with `\"latency_unknown\": \"deny\"`, rules it out as "
    "`latency_unknown`. The p95 is by nearest rank, the time at index `ceil(0.95 * n) - 1` of the `n` sorted times, "
    "so it is a time a trial took, and below 20 trials it is the slowest of them. A trial's time is yours to "
    "measure, from your call to its answer: a results row's `latency_ms`, which `model-routing calibrate` keeps in "
    "the stats file, or `Stats.add(..., latencies_ms=[...])`. A monitor record's `latency_ms` is one attempt's, and "
    "a call that falls back makes several. To read a bar off a log, use `report(records, shadow=True)` or "
    "`model-routing report --shadow`, whose p50 and p95 leave shadow calls out, or drop the records whose `shadow` "
    "is JSON `true`: by default `report` puts a shadow attempt's time in its group's percentiles. Under a bar "
    "`select --json` and `delegate --json` print it as `max_p95_ms` and each candidate's time as `p95_latency_ms`, "
    "`null` when unknown; the delegate keeps the bar, while a parent working inline is held to no time. A task with "
    "no bar routes as before.")
HARVEY_LINE = (
    "- In this library: from v1.628 a task's `max_p95_ms` is a latency bar on each route's measured "
    "95th-percentile time on the task, applied like the success bar: `select` rules out a route whose time is above "
    "it as `too_slow`, before cost, once the route has as many timed trials as the task's `min_samples`, and a task "
    "that sets `latency_unknown` to `deny` rules out a route with fewer. The monitor reports p50 and p95 latency per "
    "group, and a task sets a timeout per call. The change: the same bar on a parent's inline work in the "
    "delegation decision.")
OLD_HARVEY = "but no task can exclude a model for being too slow"
UBER_TAIL = ("Its quality is a success rate on the task's acceptance check, not F1, and from v1.628 admission can also "
             "read a route's measured p95 time, the latency bar of the Harvey lessons above.")
OLD_UBER = "latency is not part of admission yet"
KEYS = ("max_p95_ms", "latency_unknown", "p95_latency_ms")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def run(argv):
    """`main(argv)` at TODAY as (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, today=TODAY)
    return code, out.getvalue(), err.getvalue()


def results():
    """30 correct trials per route: the cheap one with two of its times at 900 ms, the pricey one untimed."""
    rows = [{"task": "t", "model": CHEAP, "correct": True, "latency_ms": 900.0 if i < 2 else 100.0} for i in range(N)]
    rows += [{"task": "t", "model": MID, "correct": True, "latency_ms": 100.0} for _ in range(N)]
    rows += [{"task": "t", "model": PRICEY, "correct": True} for _ in range(N)]
    return "".join(json.dumps(row) + "\n" for row in rows)


def make(d, **task):
    d.mkdir(exist_ok=True)
    (d / "models.json").write_text(json.dumps({"models": ROWS}), encoding="utf-8")
    (d / "tasks.json").write_text(json.dumps({"tasks": [{**TASK, **task}]}), encoding="utf-8")
    (d / "results.jsonl").write_text(results(), encoding="utf-8")
    code, _, err = run(["calibrate", "--results", str(d / "results.jsonl"), "--stats", str(d / "stats.json")])
    assert (code, err) == (0, "")
    return ["--registry", str(d / "models.json"), "--tasks", str(d / "tasks.json"), "--stats", str(d / "stats.json")]


def candidates(data):
    return {c["model_id"]: c for c in data["candidates"]}


# --- 10 v1.630: the command line ------------------------------------------------------------------

def test_calibrate_keeps_the_times_so_select_json_names_the_slow_route_and_each_p95(tmp_path):
    base = make(tmp_path, max_p95_ms=BAR)
    saved = Stats.load(tmp_path / "stats.json")
    assert saved.latencies("t", CHEAP) == (100.0,) * 28 + (900.0,) * 2 and saved.latencies("t", PRICEY) == ()
    code, out, err = run(["select", "t", "--json", *base])
    assert (code, err) == (0, "")
    data = json.loads(out)
    assert (data["primary"], data["fallbacks"], data["max_p95_ms"]) == (MID, [PRICEY], BAR)
    assert list(data)[-2:] == ["max_p95_ms", "candidates"]
    found = candidates(data)
    assert {m: c["reason"] for m, c in found.items()} == {CHEAP: "too_slow", MID: "passes", PRICEY: "passes"}
    assert {m: c["p95_latency_ms"] for m, c in found.items()} == {CHEAP: 900.0, MID: 100.0, PRICEY: None}
    assert all(list(c)[-1] == "p95_latency_ms" for c in data["candidates"])


def test_the_text_table_names_the_reason_under_the_header_it_has_without_a_bar(tmp_path):
    code, out, err = run(["select", "t", *make(tmp_path / "bar", max_p95_ms=BAR)])
    plain = run(["select", "t", *make(tmp_path / "none")])[1]
    assert (code, err) == (0, "")
    header = [line for line in out.splitlines() if line.startswith("model ")]
    assert header == [line for line in plain.splitlines() if line.startswith("model ")]
    assert header[0].split()[-1] == "reason" and "p95" not in out
    reasons = {line.split()[0]: line.split()[-1] for line in out.splitlines() if line.split()[:1] in ([CHEAP], [MID])}
    assert reasons == {CHEAP: "too_slow", MID: "passes"} and "primary:   b/mid" in out


def test_delegate_json_holds_the_bar_and_the_times_in_its_route(tmp_path):
    code, out, err = run(["delegate", "t", *WORK, "--json", *make(tmp_path, max_p95_ms=BAR)])
    assert (code, err) == (0, "")
    route = json.loads(out)["route"]
    assert (route["primary"], route["max_p95_ms"]) == (MID, BAR)
    assert {m: (c["reason"], c["p95_latency_ms"]) for m, c in candidates(route).items()} == {
        CHEAP: ("too_slow", 900.0), MID: ("passes", 100.0), PRICEY: ("passes", None)}


def test_deny_rules_the_untimed_route_out_as_latency_unknown(tmp_path):
    code, out, err = run(["select", "t", "--json", *make(tmp_path, max_p95_ms=BAR, latency_unknown="deny")])
    assert (code, err) == (0, "")
    data = json.loads(out)
    assert (data["primary"], data["fallbacks"]) == (MID, [])
    assert candidates(data)[PRICEY]["reason"] == "latency_unknown"


@pytest.mark.parametrize("command", [["select", "t"], ["select", "t", "--json"], ["delegate", "t", *WORK],
                                     ["delegate", "t", *WORK, "--json"]])
def test_a_row_whose_bar_is_null_prints_the_bytes_of_a_row_without_the_keys(tmp_path, command):
    plain = run([*command, *make(tmp_path / "plain")])
    for i, fields in enumerate(({"max_p95_ms": None}, {"max_p95_ms": None, "latency_unknown": "deny"})):
        assert run([*command, *make(tmp_path / f"null{i}", **fields)]) == plain
    assert plain[0] == 0 and not any(key in plain[1] for key in KEYS)


# --- 5.2 v1.630: the facts the paragraph states ------------------------------------------------------

def test_a_slow_shadow_is_in_report_s_p95_by_default_and_out_of_it_with_shadow():
    def rec(i, latency, shadow):
        return {"call_id": f"c{i}", "task": "t", "flavor": "cost_effective", "model": MID if shadow else CHEAP,
                "family": "b" if shadow else "a", "attempt": 0, "final": True, "outcome": "ok",
                "latency_ms": latency, "input_tokens": 10, "output_tokens": 5, "cost_usd": 0.1,
                "routing_cost_usd": 0.1, "below_bar": False, "tags": {}, "pair_id": "c0" if shadow else None,
                "shadow": shadow}
    records = [rec(i, 100.0, False) for i in range(10)] + [rec(10, 5000.0, True)]
    [default] = report(records, by="task")
    [routed] = report(records, by="task", shadow=True)
    [dropped] = report([r for r in records if r["shadow"] is not True], by="task")
    assert default["p95_latency_ms"] == 5000.0
    assert routed["p95_latency_ms"] == dropped["p95_latency_ms"] == 100.0
    assert routed["shadow_calls"] == 1


def test_below_20_times_the_p95_is_the_slowest_and_at_20_the_second_slowest():
    for n in range(1, 21):
        stats = Stats()
        stats.add("t", CHEAP, n, n, latencies_ms=[float(i) for i in range(1, n + 1)])
        assert stats.p95_latency_ms("t", CHEAP) == float(n if n < 20 else 19)


# --- 5.2 v1.630: README and the note ------------------------------------------------------------

def test_the_readme_paragraph_follows_the_policy_one_inside_the_cap():
    text = read("README.md")
    body = text.split(f"\n{PRODUCTION}\n", 1)[1].split("\n## ", 1)[0]
    paragraphs = body.strip().split("\n\n")
    assert text.count(LATENCY_PARAGRAPH) == 1 and LATENCY_PARAGRAPH in paragraphs
    at = paragraphs.index(LATENCY_PARAGRAPH)
    assert paragraphs[at - 1].startswith(POLICY_START)
    assert size(text, PRODUCTION) <= PRODUCTION_CAP
    assert "\u2014" not in LATENCY_PARAGRAPH and "\u2013" not in LATENCY_PARAGRAPH


def test_the_note_says_the_library_applies_the_bar():
    note = read("research/production-lessons.md")
    lesson = note.split("\n### Latency moves work to smaller models\n", 1)[1].split("\n### ", 1)[0]
    [line] = [x for x in lesson.splitlines() if x.startswith("- In this library: ")]
    assert line == HARVEY_LINE and note.count(HARVEY_LINE) == 1
    assert note.count(UBER_TAIL) == 1
    assert OLD_HARVEY not in note and OLD_UBER not in note
    assert '"' not in HARVEY_LINE and '"' not in UBER_TAIL   # the note reads double-quoted text as a quote


def test_no_shipped_input_or_transcript_sets_a_bar():
    """With no bar every transcript and evidence file keeps its bytes (5.2 v1.628 gives v1.627's decisions)."""
    shipped = [DATA_DIR / name for name in ("example_tasks.json", "models.json", "priors.json")]
    shipped += sorted((ROOT / "evidence").glob("*/*.json")) + sorted((ROOT / "evidence").glob("*/*.py"))
    assert len(shipped) > 30
    for path in shipped:
        text = path.read_text(encoding="utf-8")
        assert not any(key in text for key in KEYS), path
    blocks = re.findall(r"```text\n(\$ model-routing .*?)```", read("README.md"), re.S)
    assert len(blocks) >= 12 and not any(key in block for block in blocks for key in KEYS)


def test_design_and_the_changelog_state_v1_630():
    design = read("DESIGN.md")
    five2 = design.split("\n### 5.2 ", 1)[1].split("\n### 5.3 ", 1)[0]
    assert five2.count("`select --json` and the README are row LAT1c (which v1.630 adds, 5.2 and 10)") == 1
    assert five2.count("\n- v1.630 README and note (row LAT1c): ") == 1
    ten = design.split("\n## 10. ", 1)[1].split("\n## 11. ", 1)[0]
    assert ten.count("\n- v1.630 the latency bar (row LAT1c, 5.2 v1.628): no option is added, ") == 1
    assert ten.count("\n  - Tests (tests/test_latency_docs.py): ") == 1
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.630 (")]
    assert line.startswith("- v1.630 (2026-11-24): docs and tests (5.2, 10, row LAT1c). ")
