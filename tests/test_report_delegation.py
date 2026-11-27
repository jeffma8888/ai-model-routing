"""DESIGN 10 v1.689 (row DEL2b, 8.3 v1.688): `model-routing report --log PATH --delegation [--tasks PATH] [--json]`.

It prints `delegation_follow(records, tasks=...)` instead of `report`'s rows: one row per task and parent of a log's
mode records, with the delegate and inline advice counted, the share of each the agent took and the point-biserial
correlation of handing off with input size, and with `--tasks` a task's `min_delegation_follow` and `below_follow`.
The log here is tests/test_opportunities.py's attempt and budget records with mode records among them, built as
tests/test_delegation_follow.py builds one.
"""

import contextlib
import hashlib
import io
import json
from pathlib import Path

import pytest

from model_routing import delegation_follow, load_logs, load_tasks
from model_routing.cli import main
from test_delegation_follow import mode, pearson
from test_opportunities import LOG, run, write_log

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["task", "parent", "records", "delegate_advised", "delegate_followed", "delegate_follow_share",
        "inline_advised", "inline_followed", "inline_follow_share", "delegate_size_correlation"]

# By hand. summarize under x/big: 4 delegate advice, the agent took the last (8000 tokens) and did 5000, 6000 and
# 7000 itself, and 2 inline advice followed (300, 400): 1 of 4 taken, 0.25, and 2 of 2, 1.0. summarize under x/mid:
# 2 delegate advice both taken (9000, 9500), and 1 inline advice the agent handed off anyway (100): 1.0 and 0.0, and
# every record handed off, so no correlation. extract under x/big: 3 inline advice followed (100, 200, 300), no
# delegate advice, so no delegate share, and no hand-off, so no correlation.
BIG = [mode(1, "delegate", "inline", 5000, "summarize"), mode(2, "delegate", "inline", 6000, "summarize"),
       mode(3, "delegate", "inline", 7000, "summarize"), mode(4, "delegate", "delegate", 8000, "summarize"),
       mode(5, "inline", "inline", 300, "summarize"), mode(6, "inline", "inline", 400, "summarize")]
MID = [mode(7, "delegate", "delegate", 9000, "summarize", "x/mid"),
       mode(8, "delegate", "delegate", 9500, "summarize", "x/mid"),
       mode(9, "inline", "delegate", 100, "summarize", "x/mid")]
EXTRACT = [mode(10 + i, "inline", "inline", 100 * (i + 1), "extract") for i in range(3)]
MODES = BIG + MID + EXTRACT
# the mode records among the attempt and budget records, not after them
MIXED = LOG[:3] + BIG + LOG[3:6] + MID + LOG[6:] + EXTRACT
CORRELATION = pearson([r["actual_mode"] == "delegate" for r in BIG], [r["work_input_tokens"] for r in BIG])
TASKS = {"tasks": [{"name": "summarize", "bar": 0.8, "min_delegation_follow": 0.5}, {"name": "extract", "bar": 0.8}]}

ROWS = [
    {"task": "extract", "parent": "x/big", "records": 3, "delegate_advised": 0, "delegate_followed": 0,
     "delegate_follow_share": None, "inline_advised": 3, "inline_followed": 3, "inline_follow_share": 1.0,
     "delegate_size_correlation": None},
    {"task": "summarize", "parent": "x/big", "records": 6, "delegate_advised": 4, "delegate_followed": 1,
     "delegate_follow_share": 0.25, "inline_advised": 2, "inline_followed": 2, "inline_follow_share": 1.0,
     "delegate_size_correlation": 0.522308, "min_delegation_follow": 0.5, "below_follow": True},
    {"task": "summarize", "parent": "x/mid", "records": 3, "delegate_advised": 2, "delegate_followed": 2,
     "delegate_follow_share": 1.0, "inline_advised": 1, "inline_followed": 0, "inline_follow_share": 0.0,
     "delegate_size_correlation": None, "min_delegation_follow": 0.5, "below_follow": False},
]
TABLE = "\n".join([
    "task       parent  records  delegate_advised  delegate_followed  delegate_follow_share  inline_advised  "
    "inline_followed  inline_follow_share  delegate_size_correlation  min_delegation_follow  below_follow",
    "---------  ------  -------  ----------------  -----------------  ---------------------  --------------  "
    "---------------  -------------------  -------------------------  ---------------------  ------------",
    "extract    x/big   3        0                 0                  n/a                    3               "
    "3                1.000                n/a                        -                      -",
    "summarize  x/big   6        4                 1                  0.250                  2               "
    "2                1.000                0.522                      0.5                    true",
    "summarize  x/mid   3        2                 2                  1.000                  1               "
    "0                0.000                n/a                        0.5                    false",
]) + "\n"
HEADER = ("task  parent  records  delegate_advised  delegate_followed  delegate_follow_share  inline_advised  "
          "inline_followed  inline_follow_share  delegate_size_correlation\n"
          "----  ------  -------  ----------------  -----------------  ---------------------  --------------  "
          "---------------  -------------------  -------------------------\n")


def files(tmp_path, records=MIXED, tasks=TASKS):
    log = write_log(tmp_path, records)
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps(tasks), encoding="utf-8")
    return log, str(path)


# --- the table and the JSON ----------------------------------------------------------------------

def test_the_hand_rows_are_delegation_follow_s(tmp_path):
    assert round(CORRELATION, 6) == 0.522308
    _, tasks = files(tmp_path)
    assert delegation_follow(MIXED, tasks=load_tasks(tasks)) == ROWS


def test_the_table_with_tasks_by_hand(tmp_path):
    log, tasks = files(tmp_path)
    assert run(["report", "--log", log, "--delegation", "--tasks", tasks]) == (0, TABLE, "")


def test_the_json_with_tasks_by_hand(tmp_path):
    log, tasks = files(tmp_path)
    code, out, err = run(["report", "--log", log, "--delegation", "--tasks", tasks, "--json"])
    assert (code, err) == (0, "") and json.loads(out) == ROWS
    assert out == json.dumps(ROWS, indent=2) + "\n"
    assert '"below_follow": true' in out and '"delegate_follow_share": null' in out


def test_without_tasks_no_row_has_the_two_columns(tmp_path):
    log, _ = files(tmp_path)
    code, out, err = run(["report", "--log", log, "--delegation"])
    lines = TABLE.split("\n")
    # the same rows, the last two columns and the two spaces before them gone, as `_table` pads to its widest cell
    width = len("delegate_size_correlation")
    start = lines[0].index("delegate_size_correlation")
    cut = [line[:start + width].rstrip() for line in lines[:-1]]
    assert (code, err) == (0, "") and out == "\n".join(cut) + "\n"
    assert "min_delegation_follow" not in out and "below_follow" not in out
    code, out, _ = run(["report", "--log", log, "--delegation", "--json"])
    assert json.loads(out) == [{k: row[k] for k in KEYS} for row in ROWS]


def test_a_log_with_no_mode_record_prints_the_header_alone(tmp_path):
    log, tasks = files(tmp_path, records=LOG)
    assert run(["report", "--log", log, "--delegation"]) == (0, HEADER, "")
    assert run(["report", "--log", log, "--delegation", "--tasks", tasks]) == (0, HEADER, "")
    assert run(["report", "--log", log, "--delegation", "--json"]) == (0, "[]\n", "")


def test_two_logs_are_read_together(tmp_path):
    _, tasks = files(tmp_path)
    first = write_log(tmp_path, MIXED[:10], "a.jsonl")
    second = write_log(tmp_path, MIXED[10:], "b.jsonl")
    assert run(["report", "--log", first, "--log", second, "--delegation", "--tasks", tasks]) == (0, TABLE, "")
    assert delegation_follow(load_logs([first, second])) == delegation_follow(MIXED)


def test_a_task_with_no_minimum_or_not_in_the_file_shows_a_dash(tmp_path):
    log, tasks = files(tmp_path, tasks={"tasks": [{"name": "summarize", "bar": 0.8, "min_delegation_follow": 0.5}]})
    assert run(["report", "--log", log, "--delegation", "--tasks", tasks]) == (0, TABLE, "")


def test_a_row_with_no_delegate_advice_prints_n_a_for_its_flag(tmp_path):
    log, tasks = files(tmp_path, tasks={"tasks": [{"name": "extract", "bar": 0.8, "min_delegation_follow": 0.25}]})
    code, out, _ = run(["report", "--log", log, "--delegation", "--tasks", tasks])
    lines = out.split("\n")
    assert code == 0 and lines[0].endswith("delegate_size_correlation  min_delegation_follow  below_follow")
    assert lines[2].split() == ["extract", "x/big", "3", "0", "0", "n/a", "3", "3", "1.000", "n/a", "0.25", "n/a"]
    assert lines[3].split()[-3:] == ["0.522", "-", "-"] and lines[4].split()[-3:] == ["n/a", "-", "-"]


# --- exit 2 --------------------------------------------------------------------------------------

@pytest.mark.parametrize("extra, flag", [
    (["--opportunities"], "--opportunities"),
    (["--by", "task"], "--by"),
    (["--audits", "a.jsonl"], "--audits"),
    (["--cache"], "--cache"),
    (["--shadow"], "--shadow"),
    (["--target-cost-per-call", "0.001"], "--target-cost-per-call"),
    (["--stats", "s.json"], "--stats"),
    (["--registry", "r.json"], "--registry"),
    (["--shadow", "--opportunities", "--by", "model"], "--opportunities"),
])
def test_a_flag_it_takes_none_of_exits_2_before_any_path_is_read(tmp_path, extra, flag):
    missing = str(tmp_path / "missing.jsonl")
    code, out, err = run(["report", "--log", missing, "--delegation", "--tasks", str(tmp_path / "none.json")] + extra)
    assert (code, out) == (2, "")
    assert err == f"error: --delegation reads mode records alone, so it takes no {flag}\n"


def test_tasks_without_either_report_names_both(tmp_path):
    code, out, err = run(["report", "--log", str(tmp_path / "missing.jsonl"), "--tasks", "t.json"])
    assert (code, out) == (2, "")
    assert err == ("error: --tasks needs --opportunities or --delegation: only the savings and delegation reports "
                   "read it\n")


def test_a_missing_tasks_file_exits_2_before_any_log_is_read(tmp_path):
    code, out, err = run(["report", "--log", str(tmp_path / "missing.jsonl"), "--delegation",
                          "--tasks", str(tmp_path / "none.json")])
    assert (code, out) == (2, "") and "none.json" in err and "missing.jsonl" not in err and err.count("\n") == 1


def test_a_bad_tasks_file_exits_2(tmp_path):
    log, tasks = files(tmp_path, tasks={"tasks": [{"name": "summarize", "bar": 0.8, "min_delegation_follow": 1.5}]})
    code, out, err = run(["report", "--log", log, "--delegation", "--tasks", tasks])
    assert (code, out) == (2, "") and err.startswith("error: ") and err.count("\n") == 1


def test_a_missing_log_exits_2(tmp_path):
    code, out, err = run(["report", "--log", str(tmp_path / "missing.jsonl"), "--delegation"])
    assert (code, out) == (2, "") and "missing.jsonl" in err and err.count("\n") == 1


def test_a_mode_record_delegation_follow_refuses_exits_2_with_its_message(tmp_path):
    log, _ = files(tmp_path, records=MIXED + [mode(20, "maybe", "inline", 10, "summarize")])
    code, out, err = run(["report", "--log", log, "--delegation"])
    assert (code, out) == (2, "")
    assert err == "error: mode record 'mode-20': advised_mode must be 'inline' or 'delegate', got 'maybe'\n"


# --- without --delegation every output keeps its bytes ---------------------------------------------

# sha256 of f"{code}\n{stdout}\n{stderr}" for each run at v1.688 (d3f46b9), on tests/test_opportunities.py's LOG with
# one delegate and one inline mode record after it (loop-side scratch script, the same log and runs as below)
V1_688 = [
    ([], "386480fe80dc3dda571d59c5a44c0bf340550314dda0683f363433919f90d525"),
    (["--json"], "2d24de144454e6f46cc088a024b0f83e3decb4e1286b01a1557353c1824ca753"),
    (["--by", "task"], "b2e7e3079b3d425fe9efad633f8818ef84ea8980a4e4877f5cb572ac3732da54"),
    (["--cache"], "b49ad953843e658f818170cba93b4a261398fe1a553a723158e36dd6efc1daee"),
    (["--shadow"], "ff43597a12c6b7297a3bb1136a931992746bf3aa403a47f6ae8dd133dd89fd9c"),
    (["--by", "task", "--shadow", "--json"], "59f36d3905d86f5a0a67a8225feb8a470f88dcefc2633d52e3c109a8a3ae566c"),
    (["--opportunities"], "d8b13a5d0dd0707fb9b5807547a028c9db1e2869e405da6ccb466828e7c0c58f"),
    (["--opportunities", "--json"], "e9757ac67da7823c18a6be160018ff074563a36bc4dd5db49094f700e4a6942a"),
    (["--opportunities", "--target-cost-per-call", "0.001"],
     "8c74b1144476fe64bd5db76008e1aa96d4e6cf00e157bd1a4bbe4eb3b192d1da"),
]


@pytest.mark.parametrize("extra, digest", V1_688)
def test_without_the_flag_each_report_keeps_its_v1_688_bytes(tmp_path, extra, digest):
    log = write_log(tmp_path, LOG + [mode(1, "delegate", "inline", 5000, "summarize"),
                                     mode(2, "inline", "inline", 300, "extract")])
    code, out, err = run(["report", "--log", log] + extra)
    assert code == 0 and hashlib.sha256(f"{code}\n{out}\n{err}".encode()).hexdigest() == digest


# --- the docs ------------------------------------------------------------------------------------

def test_report_help_names_the_flag():
    out = io.StringIO()
    with contextlib.redirect_stdout(out), pytest.raises(SystemExit) as stop:
        main(["report", "--help"])
    assert stop.value.code == 0 and "--delegation" in out.getvalue()


def test_design_states_v1_689_in_10_and_the_changelog_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    seven = design[design.index("## 7. "):design.index("## 8. ")]
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    lead = "  - v1.689 `report --log PATH --delegation [--tasks PATH] [--json]` (row DEL2b, 8.3 v1.688): "
    [mine] = [line for line in ten.splitlines() if line.startswith(lead)]
    lines = ten.splitlines()
    assert lines[lines.index(mine) - 1].startswith("  - v1.646 `report --log PATH --opportunities --stats PATH ")
    for kept in ("`error: --delegation reads mode records alone, so it takes no FLAG`",
                 "`error: --tasks needs --opportunities or --delegation: only the savings and delegation reports "
                 "read it`", "a None as `n/a` and a key the row lacks as `-`",
                 "Without `--delegation` every other output keeps its bytes",
                 # v1.690 (row DEL2c) adds the README sentence, tests/test_delegation_follow_docs.py
                 "Not in this version: the README sentence (row DEL2c, which v1.690 adds in 5.2)."):
        assert mine.count(kept) == 1, kept
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    assert ("`report --delegation` (row DEL2b), which v1.689 adds (10), and the README sentence (row DEL2c, which "
            "v1.690 adds in 5.2). ") in seven
    assert ("  - Not in this version: `report --delegation` (row DEL2b), which v1.689 adds (10), and the README "
            "sentence (row DEL2c, which v1.690 adds in 5.2). ") in eight3
    [line] = [x for x in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if x.startswith("- v1.689 (")]
    assert line.startswith("- v1.689 (2026-11-27): spec, code, tests and docs (10, row DEL2b). ")
    assert len(line.encode("utf-8")) <= 600


def test_the_production_lessons_line_says_the_command_ships_and_the_cap_is_the_change():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    section = text[text.index("### Under-delegation is a failure you can measure"):]
    line = next(l for l in section.splitlines() if l.startswith("- In this library:"))
    assert ("; and from v1.689 `model-routing report --log PATH --delegation` prints that report, with "
            "`--tasks FILE` for the minimum.") in line
    assert line.endswith(" The change: a cap on delegation depth.")
    assert "that report on the command line" not in line


def test_no_evidence_or_research_script_or_workflow_runs_it_and_readme_names_it_once():
    paths = [p for d in ("evidence", "research") for p in (ROOT / d).rglob("*.py")]
    paths += list((ROOT / ".github" / "workflows").glob("*.yml"))
    assert len(paths) > 10
    for path in paths:
        assert "--delegation" not in path.read_text(encoding="utf-8"), path
    # v1.690 (row DEL2c): README names it once, in the paragraph on following delegation advice, in no transcript,
    # tests/test_delegation_follow_docs.py
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    [line] = [l for l in readme.splitlines() if "--delegation" in l]
    assert line.startswith("An agent's hand-offs can be checked against the advice: ")
    assert line.count("--delegation") == 1
    assert "$ model-routing report" not in line
