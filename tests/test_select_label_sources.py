"""DESIGN 10 and 13.3 v1.663 (row JUDGE1bbb, the third part of JUDGE1b): label sources in `select` and the README.

When the stats `select` routed on hold label sources (4.3 v1.662) for the chosen route's key, the task's with
the primary (`TASK@S` with `--slice S`), the text output gains `labels:    S N, ... of T trials` right before
the blank line that precedes the candidate table, and `--json` gains `label_sources` right before
`candidates`. A primary whose key holds no source prints v1.662's bytes, text and `--json`, so a fallback's
sources, or a base key's on a sliced call, never show, and an exit-3 run prints no line. The private stats copy
a delegate routes on keeps each key's sources (13.3 v1.663, review iter-518 nit 3). README `## Running it in
production` ends with a paragraph on `consensus-labels` and what its labels measure, inside v1.629's cap. The
counts are synthetic, so each line is written by hand.
"""

import contextlib
import io
import json
from datetime import date
from pathlib import Path

import pytest

from model_routing import Stats
from model_routing.cli import main
from model_routing.delegation import _briefed_stats
from test_readme_production import PRODUCTION, PRODUCTION_CAP, paragraphs, read, size
from test_readme_walkthrough import command_problems

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 26)
CHEAP, BIG = "x/cheap", "x/big"
TWO = {"human": 30, "consensus": 60}  # sorted by name on the line: consensus, then human
LEAD = "A team with no human labels can make them from its reference judges' recorded grades: "
COMMAND = "model-routing consensus-labels --grades FILE --judges A,B --reruns N --out FILE"
FORMAT_LEAD = "A store that loads the log (a warehouse table or a dashboard) builds its schema from the record format: "


def run(argv):
    """`main(argv)` at TODAY as (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, today=TODAY)
    return code, out.getvalue(), err.getvalue()


def model(model_id, price):
    return {"id": model_id, "family": "x", "price_in": price, "price_out": 2 * price, "context_window": 100_000}


@pytest.fixture
def files(tmp_path):
    (tmp_path / "models.json").write_text(json.dumps({"models": [model(CHEAP, 0.1), model(BIG, 1.0)]}),
                                          encoding="utf-8")
    common = {"min_samples": 30, "expected_input_tokens": 1000, "expected_output_tokens": 200}
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [
        dict(common, name="t", bar=0.8),
        dict(common, name="r", bar=0.8, failure_policy="retry_same"),
        dict(common, name="b", bar=0.99, on_no_model="best_available"),
        dict(common, name="high", bar=0.99),
        dict(common, name="lat", bar=0.8, max_p95_ms=500.0)]}), encoding="utf-8")
    return tmp_path


def write_stats(path, sources=None, task="t", extra=()):
    """CHEAP 98 of 100 and BIG 100 of 100 on `task`, with `sources` mapping a model to its label sources."""
    stats = Stats()
    for model_id, successes in ((CHEAP, 98), (BIG, 100)):
        stats.add(task, model_id, successes, 100, label_sources=(sources or {}).get(model_id))
    for key, model_id, successes, trials, more in extra:
        stats.add(key, model_id, successes, trials, **more)
    stats.save(path)
    return str(path)


def select(files, name, task, *more):
    return run(["select", task, "--registry", str(files / "models.json"), "--tasks", str(files / "tasks.json"),
                "--stats", str(files / name), "--priors", str(files / "none.json"), *more])


def with_line(plain, line):
    """`plain` with `line` right before its first blank line, the one before the candidate table."""
    lines = plain.split("\n")
    at = lines.index("")
    return "\n".join(lines[:at] + [line] + lines[at:])


# --- the text line ----------------------------------------------------------------------------

@pytest.mark.parametrize("sources, line", [
    ({"consensus": 98}, "labels:    consensus 98 of 100 trials"),
    (TWO, "labels:    consensus 60, human 30 of 100 trials"),
    ({"consensus": 1}, "labels:    consensus 1 of 100 trials"),
])
def test_the_line_names_each_source_of_the_primary_after_below_bar(files, sources, line):
    write_stats(files / "plain.json")
    write_stats(files / "tagged.json", {CHEAP: sources})
    code, plain, err = select(files, "plain.json", "t")
    assert (code, err) == (0, "") and "labels:" not in plain
    assert plain.split("\n")[:6] == ["task:      t", "flavor:    cost_effective", f"primary:   {CHEAP}",
                                     f"fallbacks: {BIG}", "basis:     measured", "below_bar: false"]
    code, tagged, err = select(files, "tagged.json", "t")
    assert (code, err) == (0, "")
    assert tagged == with_line(plain, line)
    assert tagged.split("\n")[6:8] == [line, ""]


def test_cost_blind_shows_its_own_primarys_sources(files):
    write_stats(files / "plain.json")
    write_stats(files / "tagged.json", {CHEAP: TWO, BIG: {"human": 100}})
    _, plain, _ = select(files, "plain.json", "t", "--flavor", "cost_blind")
    code, tagged, err = select(files, "tagged.json", "t", "--flavor", "cost_blind")
    assert (code, err) == (0, "") and f"primary:   {BIG}" in tagged
    assert tagged == with_line(plain, "labels:    human 100 of 100 trials")


def test_the_line_follows_the_policy_lines_of_a_retry_task(files):
    write_stats(files / "plain.json", task="r")
    write_stats(files / "tagged.json", {CHEAP: TWO}, task="r")
    _, plain, _ = select(files, "plain.json", "r")
    code, tagged, err = select(files, "tagged.json", "r")
    assert (code, err) == (0, "")
    assert tagged == with_line(plain, "labels:    consensus 60, human 30 of 100 trials")
    lines = tagged.split("\n")
    at = lines.index("labels:    consensus 60, human 30 of 100 trials")
    assert lines[at - 1].startswith(("policy:    retry_same, ", "pick:      ")) and lines[at + 1] == ""


def test_a_below_bar_primary_shows_its_sources(files):
    write_stats(files / "plain.json", task="b")
    write_stats(files / "tagged.json", {BIG: {"consensus": 100}}, task="b")
    _, plain, _ = select(files, "plain.json", "b")
    code, tagged, err = select(files, "tagged.json", "b")
    assert (code, err) == (0, "") and "below_bar: true" in tagged and f"primary:   {BIG}" in tagged
    assert tagged == with_line(plain, "labels:    consensus 100 of 100 trials")


def test_the_line_from_a_calibrate_of_consensus_label_rows(files):
    results = files / "results.jsonl"
    rows = [{"task": "t", "model": CHEAP, "item": f"q{k}", "prediction": "pass", "gold": "pass",
             "label_source": "consensus"} for k in range(40)]
    results.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    code, _, err = run(["calibrate", "--results", str(results), "--stats", str(files / "cal.json")])
    assert (code, err) == (0, "")
    code, out, err = select(files, "cal.json", "t")
    assert (code, err) == (0, "") and f"primary:   {CHEAP}" in out
    # 40 of 40 by Wilson: 40 / (40 + 1.96^2) = 0.9124 > 0.8, and BIG has no trials
    assert out.split("\n")[6:8] == ["labels:    consensus 40 of 40 trials", ""]


def test_a_sliced_call_reads_the_slice_key(files):
    slice_rows = [("t@hard", CHEAP, 98, 100, {"label_sources": {"consensus": 50}}),
                  ("t@hard", BIG, 100, 100, {})]
    write_stats(files / "plain.json", extra=[(k, m, s, t, {}) for k, m, s, t, _ in slice_rows])
    write_stats(files / "tagged.json", extra=slice_rows)
    _, plain, _ = select(files, "plain.json", "t", "--slice", "hard")
    code, tagged, err = select(files, "tagged.json", "t", "--slice", "hard")
    assert (code, err) == (0, "") and tagged.split("\n")[:2] == ["task:      t", "slice:     hard"]
    assert tagged == with_line(plain, "labels:    consensus 50 of 100 trials")


# --- v1.662's bytes ---------------------------------------------------------------------------

def test_a_base_keys_sources_never_show_on_a_sliced_call(files):
    slice_rows = [("t@hard", CHEAP, 98, 100, {}), ("t@hard", BIG, 100, 100, {})]
    write_stats(files / "plain.json", extra=slice_rows)
    write_stats(files / "tagged.json", {CHEAP: TWO, BIG: TWO}, extra=slice_rows)
    for more in ([], ["--json"]):
        assert select(files, "tagged.json", "t", "--slice", "hard", *more) == \
            select(files, "plain.json", "t", "--slice", "hard", *more)


def test_a_fallbacks_sources_never_show(files):
    write_stats(files / "plain.json")
    write_stats(files / "tagged.json", {BIG: TWO})
    for more in ([], ["--json"]):
        plain = select(files, "plain.json", "t", *more)
        assert plain[0] == 0 and select(files, "tagged.json", "t", *more) == plain


def test_an_exit_3_run_prints_no_line(files):
    write_stats(files / "tagged.json", {CHEAP: TWO, BIG: TWO}, task="high")
    write_stats(files / "plain.json", task="high")
    code, out, err = select(files, "tagged.json", "high")
    assert (code, out) == (3, "") and err.startswith("error: no model clears the bar 0.99 for task 'high'")
    assert "labels:" not in err and (code, out, err) == select(files, "plain.json", "high")


# --- --json -----------------------------------------------------------------------------------

def test_json_gains_label_sources_right_before_candidates(files):
    write_stats(files / "plain.json")
    write_stats(files / "tagged.json", {CHEAP: TWO})
    code, out, err = select(files, "tagged.json", "t", "--json")
    assert (code, err) == (0, "")
    data, plain = json.loads(out), json.loads(select(files, "plain.json", "t", "--json")[1])
    assert list(data) == list(plain)[:-1] + ["label_sources", "candidates"]
    assert list(plain)[-1] == "candidates" and "label_sources" not in plain
    assert data["label_sources"] == {"consensus": 60, "human": 30}
    assert list(data["label_sources"]) == ["consensus", "human"]
    assert {k: v for k, v in data.items() if k != "label_sources"} == plain
    assert out == json.dumps(data, indent=2) + "\n"


def test_json_puts_label_sources_after_max_p95_ms_under_a_latency_bar(files):
    # review iter-519 nit 1: under a bar `max_p95_ms` (v1.630) is then no longer the key right before `candidates`
    times = {"latencies_ms": [100.0] * 100}
    rows = [("lat", CHEAP, 98, 100, dict(times, label_sources={"consensus": 98})), ("lat", BIG, 100, 100, times)]
    write_stats(files / "plain.json", extra=[(k, m, s, t, {"latencies_ms": more["latencies_ms"]})
                                             for k, m, s, t, more in rows])
    write_stats(files / "tagged.json", extra=rows)
    plain = json.loads(select(files, "plain.json", "lat", "--json")[1])
    code, out, err = select(files, "tagged.json", "lat", "--json")
    data = json.loads(out)
    assert (code, err) == (0, "") and data["primary"] == CHEAP and plain["max_p95_ms"] == 500.0
    assert list(plain)[-2:] == ["max_p95_ms", "candidates"]
    assert list(data)[-3:] == ["max_p95_ms", "label_sources", "candidates"]
    assert {k: v for k, v in data.items() if k != "label_sources"} == plain


# --- 13.3 v1.663: the delegate's private copy -------------------------------------------------

def test_the_briefed_copy_keeps_each_keys_sources():
    stats = Stats()
    stats.add("t", CHEAP, 98, 100, input_tokens=100_000, output_tokens=20_000, label_sources=TWO)
    stats.add("t", BIG, 100, 100, input_tokens=100_000, output_tokens=20_000)
    stats.add("other", CHEAP, 5, 5, label_sources={"consensus": 5})
    copy = _briefed_stats(stats, "t", 500)
    assert copy is not stats
    assert copy.tokens("t", CHEAP) == (100_000 + 500 * 100, 20_000, 100)
    assert copy.label_sources("t", CHEAP) == {"consensus": 60, "human": 30}
    assert copy.label_sources("t", BIG) == {}
    assert copy.items() == [(("t", BIG), (100, 100)), (("t", CHEAP), (98, 100))]
    assert _briefed_stats(stats, "t", 0) is stats


# --- README and docs --------------------------------------------------------------------------

def paragraph():
    found = paragraphs(read("README.md"), PRODUCTION)
    return found, [p for p in found if p.startswith(LEAD)]


def test_readme_ends_its_production_section_with_the_paragraph():
    found, [mine] = paragraph()
    assert found[-1] == mine and found[-2].startswith(FORMAT_LEAD)
    assert size(read("README.md"), PRODUCTION) <= PRODUCTION_CAP == 30_000
    for words in (f"`{COMMAND}`", "`--min-agreement`", "agreement between models, not human correctness",
                  "`label_source`", "`calibrate`", "`select`", "`labels:`"):
        assert mine.count(words) == 1, words
    assert command_problems(COMMAND) == []
    assert "```" not in mine


def test_design_and_changelog_state_v1_663():
    design = read("DESIGN.md")
    ten = design[design.index("\n## 10. "):design.index("\n## 11. ")]
    assert ten.count("\n- v1.663 `select` label sources (row JUDGE1bbb, 4.3 v1.662): ") == 1
    assert ten.index("\n- v1.663 `select` label sources") < ten.index("\n- `calibrate --results PATH --stats PATH`:")
    for words in ("`labels:    consensus 60, human 30 of 100 trials`", "`--json` gains `label_sources`, that dict, "
                  "right before `candidates`", "Only the primary's key is read", "prints v1.662's bytes",
                  "not on human correctness (4.3 v1.660)", "the seventh entry of tests/test_readme_trim.py's `LATER`",
                  "under a latency bar it comes after `max_p95_ms`, which is then no longer the key right before",
                  "stdout gets the same table and is flushed"):
        assert ten.count(words) == 1, words
    thirteen3 = design[design.index("\n### 13.3 "):design.index("\n### 13.4 ")]
    assert thirteen3.count("\n- v1.663 label sources (row JUDGE1bbb, review iter-518 nit 3): that private copy also "
                           "holds each key's label sources as they are (4.3 v1.662)") == 1
    assert thirteen3.count("it holds the times from v1.628 and the label sources from v1.663, and still no cache "
                           "counts (review iter-519 nit 2)") == 1
    four3 = design[design.index("### 4.3 "):design.index("### 4.4 ")]
    assert "(row JUDGE1bbb; both ship in 10 v1.663). " in four3
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.663 (")]
    assert line.startswith("- v1.663 (2026-11-26): spec, code, docs and tests (4.3, 10, 13.3, row JUDGE1b, third part). ")
    assert len(line.encode("utf-8")) <= 600


def test_the_production_note_states_select_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    [line] = [x for x in text.splitlines() if x.startswith("- In this library: judge calls are its first case")]
    assert "The changes: `select` printing" not in line
    assert line.endswith("so stats built on those labels say so. From v1.663 `select` prints where the chosen "
                         "route's labels came from. The change: a self-consistency minimum, so a judge whose "
                         "reruns disagree is excluded whatever its bound.")
