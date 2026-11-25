"""DESIGN 5.2 v1.635 (row M1e): the drift check in the docs.

No code changes. README `## Running it in production` ends with a paragraph on `model-routing drift`
and `select --window` (8.3 v1.632 and v1.633, 10 v1.634), right after the one on a task's latency bar:
what the command reads and how it judges each route, which answers count as failures, its flags and
exit code, the window option of `select`, and the stated limits. README Limitations' `No online drift
detection` line says what the check does not do, DESIGN 14 defers only a check that runs, alerts or
re-routes on its own, and research/production-lessons.md's GitHub line says what the library does
in place of its change still planned. Every README transcript keeps its v1.634 bytes, and no evidence
or research script opens a file this slice edits, so every evidence file keeps its bytes.
"""

import contextlib
import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path

from test_readme_production import PRODUCTION, PRODUCTION_CAP, size

from model_routing import Stats
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 24)
OLD, NEW = "2026-10-01T12:00:00.000+00:00", "2026-11-20T12:00:00.000+00:00"
CHEAP, MID = "x/cheap", "x/mid"
LATENCY_START = "A task can also hold its routes to a time. "
GITHUB_QUOTE = ("We also run these tests against our production models every day. If we see degradation, we do some "
                "auditing to find out why the models aren\u2019t performing as well as they used to.")
GITHUB_ANCHOR = "test-a-model-before-the-switch-and-re-run-the-tests-on-the-models-in-production-every-day"
DRIFT_PARAGRAPH = (
    "A route's success can drift while its all-time counts still admit it, since a provider can change the model "
    "behind an ID. `model-routing drift --log PATH --audits PATH [--window 30d]` reads a monitor log's audited calls, "
    "by the audits file `report --audits` reads, and judges each (task, route) against the task's bar twice: on the "
    "audited calls of the last N UTC days, today included, and on all of them, or on the stats file you route on when "
    "you pass it as `--stats FILE`. A call's final `ok` answer counts by its audit, and each answer the task's check "
    "rejected counts as a failure whatever the audit, so a route whose rejected answers a fallback then made good "
    "still pays for them. Each row gives both sides' counts and Wilson bounds, the bar, `min_samples` and a flag: "
    "`fell_below` when the all-time side clears the bar and a window of at least `min_samples` trials does not, "
    "`rose_above` when the window clears it and the all-time side does not, so a window under `min_samples` trials "
    "flags nothing. The command changes no route or file and exits 0 whatever it flags, so a scheduled job reads its "
    "`--json` and alerts on a flag. To route on the window alone, `select --window 30d --log PATH --audits PATH` "
    "reads the window's stats in place of `--stats`, so a route measured at 0.92 all-time whose audited calls in the "
    "window succeed at 0.70 loses admission there. Two limits: when the all-time side comes from the same log, as it "
    "does without `--stats`, the window's calls are among its calls, so the all-time bound moves toward the window's "
    "as the window grows; and each bound is at the task's confidence, so over many routes some flags come by chance, "
    "which makes a flag a reason to audit more calls, not proof of a change. Which calls to audit stays yours, and "
    "audits picked by a rule other than chance bias every route's rate; an audited call that a cascade answered "
    "counts once for the cascade, with whether it handed up, and one that a procedure answered once for the "
    "procedure, at its model calls' and tools' cost (`DESIGN.md` 8.3 and 10). Each audited call's row also carries "
    "its route's time (a cascade's legs summed, a procedure's whole run), so on a task with `max_p95_ms` "
    "`select --window` holds each route to the bar on the window's times. GitHub runs its tests on the "
    "models it serves: "
    f"\"{GITHUB_QUOTE}\" ([production lessons](research/production-lessons.md#{GITHUB_ANCHOR})): a fixed test set run "
    "again, where `drift` reads audited calls of your own traffic, and the post gives no count of the drops it found.")
OLD_LIMITATION = ("- No online drift detection. Re-calibrate from audited samples on a schedule, and when a provider ships "
                  "a new model version\n")
LIMITATION = (
    "- Drift is checked on the calls you audit, when you ask: `model-routing drift` compares each route's audited calls "
    "of a recent window with its all-time counts and flags one that fell below its task's bar or rose above it "
    "([Running it in production](#running-it-in-production)), but it runs only when you run it, alerts no one and "
    "changes no route unless you route with `select --window`. Which calls to audit, and when to re-calibrate, stay "
    "yours: re-calibrate on a schedule, and when a provider ships a new model version\n")  # v1.636 drops a sentence
OLD_FOURTEEN = "- Online drift detection beyond re-calibrating from audited results; "
FOURTEEN = ("- Online drift detection beyond v1.632's `audited_results`, v1.633's `drift_check` and v1.634's `drift` "
            "command and `select --window` (8.3, 10), which judge a recent window of audited calls when the caller runs "
            "them: a check that runs, alerts or re-routes on its own (v1.635, row M1e); budgets and alerts beyond "
            "v1.595's in-process ledger (4.6), ")
GITHUB_LINE_START = "- In this library: the caller calls a task, not a model, "
OLD_NOTE = (", and README's limitations say the library has no online drift detection.",
            " The change still planned: ", "a drift check over audited production calls in a recent window")
NOTE_COUNT = ("so a fall in a model's recent success rate is averaged into its whole count, which is why the drift "
              "check below keeps a recent window apart from it. ")
NOTE_SHIPPED = ("From v1.634 the drift check is `model-routing drift`: it reads a monitor log's audited production "
                "calls in a recent window, kept apart from the all-time counts (v1.632), flags a route whose bound "
                "falls under the bar or rises over it (v1.633), and `select --window` routes on the window's counts "
                "alone; it runs when the caller runs it, on the caller's schedule, and from v1.636 a call that a "
                "cascade or a procedure answered counts for that route too. ")
# v1.634 (808d9fe): sha256 of README's twelve ```text blocks that start with `$ model-routing`, joined
TRANSCRIPTS_SHA256 = "b870064b5eb860c802b7ce92137bccc0d2a67902df6f9abd491739ca1804fb2c"
BLOCK = re.compile(r"```text\n(\$ model-routing .*?)```", re.S)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def run(argv):
    """`main(argv)` at TODAY as (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, today=TODAY)
    return code, out.getvalue(), err.getvalue()


def rec(call_id, model, ts, attempt=0, final=True, outcome="ok"):
    return {"ts": ts, "call_id": call_id, "task": "judge", "flavor": "cost_effective", "model": model,
            "family": "x", "attempt": attempt, "final": final, "outcome": outcome, "error": None,
            "latency_ms": 5.0, "input_tokens": 1000, "output_tokens": 200, "cost_usd": 0.001,
            "routing_cost_usd": 0.001, "below_bar": False, "basis": "measured", "tags": {}, "slice": None}


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return str(path)


def make(d, min_samples=30):
    """30 calls in the window whose cheap answer the check rejected and whose mid fallback was audited
    right, and 60 older calls of the cheap route audited right; stats.json holds the cheap route alone at
    460 of 500."""
    d.mkdir(exist_ok=True)
    (d / "tasks.json").write_text(json.dumps({"tasks": [
        {"name": "judge", "bar": 0.8, "min_samples": min_samples, "expected_input_tokens": 1000,
         "expected_output_tokens": 200}]}), encoding="utf-8")
    stats = Stats()
    stats.add("judge", CHEAP, 460, 500)
    stats.save(d / "stats.json")
    records = [rec(f"old{k}", CHEAP, OLD) for k in range(60)]
    for k in range(30):
        records += [rec(f"c{k}", CHEAP, NEW, final=False, outcome="invalid"), rec(f"c{k}", MID, NEW, attempt=1)]
    write_jsonl(d / "calls.jsonl", records)
    write_jsonl(d / "audits.jsonl", [{"call_id": r["call_id"], "correct": True} for r in records if r["final"]])
    return ["drift", "--log", str(d / "calls.jsonl"), "--audits", str(d / "audits.jsonl"),
            "--tasks", str(d / "tasks.json"), "--json"]


def rows(out):
    return {row["route"]: row for row in json.loads(out)["rows"]}


# --- the facts the paragraph states ------------------------------------------------------------

def test_a_rejected_answer_counts_against_its_route_whatever_the_audit_and_both_flags_show(tmp_path):
    argv = make(tmp_path)
    before = sorted(p.name for p in tmp_path.iterdir())
    code, out, err = run(argv + ["--stats", str(tmp_path / "stats.json")])
    assert (code, err) == (0, "") and sorted(p.name for p in tmp_path.iterdir()) == before
    found = rows(out)
    assert (found[CHEAP]["window_successes"], found[CHEAP]["window_trials"]) == (0, 30)
    assert (found[MID]["window_successes"], found[MID]["window_trials"]) == (30, 30)
    assert (found[CHEAP]["flag"], found[MID]["flag"]) == ("fell_below", "rose_above")


def test_a_window_under_min_samples_flags_nothing(tmp_path):
    code, out, err = run(make(tmp_path, min_samples=31) + ["--stats", str(tmp_path / "stats.json")])
    assert (code, err) == (0, "")
    assert [row["flag"] for row in rows(out).values()] == [None, None]


def test_without_stats_the_windows_calls_are_among_the_all_time_ones(tmp_path):
    code, out, err = run(make(tmp_path))
    assert (code, err) == (0, "")
    found = rows(out)
    assert (found[CHEAP]["all_time_successes"], found[CHEAP]["all_time_trials"]) == (60, 90)
    assert all(row["all_time_trials"] >= row["window_trials"] for row in found.values())
    assert all(row["all_time_successes"] >= row["window_successes"] for row in found.values())


# --- README --------------------------------------------------------------------------------------

def test_the_paragraph_ends_the_section_after_the_latency_one_inside_the_cap():
    text = read("README.md")
    body = text.split(f"\n{PRODUCTION}\n", 1)[1].split("\n## ", 1)[0]
    paragraphs = body.strip().split("\n\n")
    assert text.count(DRIFT_PARAGRAPH) == 1 and paragraphs[-1] == DRIFT_PARAGRAPH
    assert paragraphs[-2].startswith(LATENCY_START)
    assert size(text, PRODUCTION) <= PRODUCTION_CAP
    assert "\u2014" not in DRIFT_PARAGRAPH and "\u2013" not in DRIFT_PARAGRAPH


def test_the_paragraph_quotes_the_notes_github_lesson_word_for_word():
    note = read("research/production-lessons.md")
    heading = "### Test a model before the switch, and re-run the tests on the models in production every day"
    lesson = note.split(f"\n{heading}\n", 1)[1].split("\n### ", 1)[0]
    assert f"\"{GITHUB_QUOTE}\"" in lesson and DRIFT_PARAGRAPH.count("\"") == 2


def test_the_limitations_line_says_what_the_check_does_not_do():
    text = read("README.md")
    limits = text.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    assert OLD_LIMITATION not in text and "No online drift detection" not in text
    assert limits.count(LIMITATION) == 1 and text.count(LIMITATION) == 1


def test_the_twelve_transcripts_keep_their_v1_634_bytes():
    blocks = BLOCK.findall(read("README.md"))
    assert len(blocks) == 12 and not any("$ model-routing drift" in b or "--window" in b for b in blocks)
    assert hashlib.sha256("".join(blocks).encode("utf-8")).hexdigest() == TRANSCRIPTS_SHA256


# --- the note ------------------------------------------------------------------------------------

def test_the_notes_github_line_says_what_the_library_does():
    note = read("research/production-lessons.md")
    [line] = [x for x in note.splitlines() if x.startswith(GITHUB_LINE_START)]
    assert not any(old in note for old in OLD_NOTE)
    assert line.count(NOTE_COUNT) == 1 and line.count(NOTE_SHIPPED) == 1
    assert line.index(NOTE_COUNT) < line.index("from v1.607 a task's `shadow_rate`") < line.index(NOTE_SHIPPED)
    assert line.index(NOTE_SHIPPED) < line.index("Which measure counts as success stays the caller's")
    assert " The change" not in line and " The changes: " not in line
    assert '"' not in NOTE_COUNT and '"' not in NOTE_SHIPPED   # the note reads double-quoted text as a quote


# --- no evidence file can change -------------------------------------------------------------------

def test_no_evidence_or_research_script_opens_a_file_this_slice_edits():
    scripts = [p for folder in ("evidence", "research") for p in (ROOT / folder).rglob("*")
               if p.is_file() and p.suffix in (".py", ".sh")]
    assert len(scripts) >= 20
    opened = re.compile(r"[\"'](README\.md|DESIGN\.md|CHANGELOG\.md)[\"']|production-lessons\.md")
    assert [str(p.relative_to(ROOT)) for p in scripts if opened.search(p.read_text(encoding="utf-8"))] == []


# --- DESIGN and the changelog --------------------------------------------------------------------

def test_design_14_defers_only_a_check_that_runs_on_its_own():
    design = read("DESIGN.md")
    fourteen = design[design.index("## 14. "):design.index("## 15. ")]
    assert OLD_FOURTEEN not in fourteen and fourteen.count(FOURTEEN) == 1
    assert fourteen.count("beyond v1.595's in-process ledger (4.6)") == 1   # tests/test_budget.py


def test_design_and_the_changelog_state_v1_635():
    design = read("DESIGN.md")
    five2 = design[design.index("\n### 5.2 "):design.index("\n### 5.3 ")]
    assert five2.count("\n- v1.635 README, Limitations, 14 and the note (row M1e, 8.3 v1.632 and v1.633, 10 v1.634): ") == 1
    eight3 = design[design.index("\n### 8.3 "):design.index("\n## 9. ")]
    assert eight3.count("restated (row M1e, which v1.635 does, 5.2 and 14)") == 1
    ten = design[design.index("\n## 10. "):design.index("\n## 11. ")]
    assert ten.count("the note's GitHub line (row M1e, which v1.635 adds, 5.2 and 14)") == 1
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.635 (")]
    assert line.startswith("- v1.635 (2026-11-24): docs and tests (5.2, 8.3, 10, 14, row M1e). ")
    assert len(line.encode("utf-8")) <= 600
