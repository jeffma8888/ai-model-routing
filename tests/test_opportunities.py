"""DESIGN 8.3 and 10 v1.645 (row OPP1a): the savings report, one row per task from a log.

`opportunities(records, *, audits=None, target_cost_per_call=None)` drops budget and shadow records,
groups the rest by `task` as `report(records, by="task", audits=audits, shadow=True)` does, and adds
the task's span in UTC dates, its calls and spend per day, its share of spend, its cost per call and,
with a target cost per call, the hypothetical daily saving if a route at that cost served the task.
`report --opportunities [--target-cost-per-call USD]` prints it.
"""

import contextlib
import io
import json
import math
from pathlib import Path

import pytest

import model_routing
from model_routing import report
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["task", "calls", "days", "calls_per_day", "cost_usd", "spend_share", "cost_per_call_usd",
        "cost_per_day_usd"]


def opportunities(*args, **kwargs):
    return model_routing.opportunities(*args, **kwargs)


def rec(call_id, task, attempt, final, outcome, model, cost, ts, **extra):
    out = {"call_id": call_id, "task": task, "flavor": "cost_effective", "model": model, "family": "x",
           "attempt": attempt, "final": final, "outcome": outcome, "latency_ms": 10.0,
           "input_tokens": 100, "output_tokens": 20, "cost_usd": cost, "routing_cost_usd": 0.0,
           "ts": ts}
    out.update(extra)
    return out


# By hand. extract: 3 calls on 2026-11-01 to 11-03 (3 days), e1 an error on x/cheap then a fallback
# answer on x/mid (0.001 + 0.004), e2 0.002, e3 0.003: 0.010 in all, 1.0 a day, 0.003333 a call.
# summarize: 2 calls on 2026-11-02 UTC (1 day; s2's -08:00 stamp is 07:30Z that day), s2 invalid:
# 0.03, 2.0 a day, 0.015 a call; s1's shadow (0.5, on 11-09) and the budget record are dropped.
# classify: 4 calls of 0.001 on 2026-11-05: 0.004, 4.0 a day, 0.001 a call. Spend 0.044 in all.
LOG = [
    rec("e1", "extract", 0, False, "error", "x/cheap", 0.001, "2026-11-01T09:00:00Z"),
    rec("e1", "extract", 1, True, "ok", "x/mid", 0.004, "2026-11-01T09:00:01Z"),
    rec("e2", "extract", 0, True, "ok", "x/cheap", 0.002, "2026-11-02T10:00:00Z"),
    rec("s1", "summarize", 0, True, "ok", "x/mid", 0.02, "2026-11-02T08:00:00Z"),
    rec("s1", "summarize", 0, True, "ok", "x/strong", 0.5, "2026-11-09T00:00:00Z", shadow=True),
    rec("s2", "summarize", 0, True, "invalid", "x/mid", 0.01, "2026-11-01T23:30:00-08:00"),
    rec("e3", "extract", 0, True, "ok", "x/cheap", 0.003, "2026-11-03T23:59:59Z"),
    {"budget_event": "refused", "call_id": "b1", "task": "classify", "ts": "not a time", "cost_usd": 9.0},
] + [rec(f"c{n}", "classify", 0, True, "ok", "x/cheap", 0.001, f"2026-11-05T0{n}:00:00Z")
     for n in range(1, 5)]

EXTRACT = {"task": "extract", "calls": 3, "days": 3, "calls_per_day": 1.0, "cost_usd": 0.01,
           "spend_share": 0.227273, "cost_per_call_usd": 0.003333, "cost_per_day_usd": 0.003333}
SUMMARIZE = {"task": "summarize", "calls": 2, "days": 1, "calls_per_day": 2.0, "cost_usd": 0.03,
             "spend_share": 0.681818, "cost_per_call_usd": 0.015, "cost_per_day_usd": 0.03}
CLASSIFY = {"task": "classify", "calls": 4, "days": 1, "calls_per_day": 4.0, "cost_usd": 0.004,
            "spend_share": 0.090909, "cost_per_call_usd": 0.001, "cost_per_day_usd": 0.004}


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def write_log(tmp_path, records, name="calls.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return str(path)


# --- the function ------------------------------------------------------------------------------

def test_rows_by_hand_sorted_by_spend_per_day():
    rows = opportunities(LOG)
    assert rows == [SUMMARIZE, CLASSIFY, EXTRACT]
    assert [list(r) for r in rows] == [KEYS] * 3


def test_a_target_adds_the_saving_and_sorts_by_it():
    rows = opportunities(LOG, target_cost_per_call=0.001)
    # summarize 2.0 * (0.015 - 0.001) = 0.028; extract 1.0 * (0.01 / 3 - 0.001) = 0.002333;
    # classify is at the target, so it saves 0
    assert [r["task"] for r in rows] == ["summarize", "extract", "classify"]
    assert [r["saving_per_day_usd"] for r in rows] == [0.028, 0.002333, 0.0]
    assert all(r["target_cost_per_call_usd"] == 0.001 for r in rows)
    assert [list(r) for r in rows] == [KEYS + ["target_cost_per_call_usd", "saving_per_day_usd"]] * 3
    assert rows[0] == dict(SUMMARIZE, target_cost_per_call_usd=0.001, saving_per_day_usd=0.028)


def test_an_int_target_is_a_float_and_ties_fall_back_to_spend_per_day():
    rows = opportunities(LOG, target_cost_per_call=1)
    assert [r["task"] for r in rows] == ["summarize", "classify", "extract"]
    assert [r["saving_per_day_usd"] for r in rows] == [0.0, 0.0, 0.0]
    assert type(rows[0]["target_cost_per_call_usd"]) is float


def test_audits_add_cost_per_success_before_the_target_keys():
    audits = {"e1": True, "e2": False, "e3": True, "s1": True}
    rows = opportunities(LOG, audits=audits, target_cost_per_call=0.001)
    by_task = {r["task"]: r for r in rows}
    assert by_task["extract"]["cost_per_success_usd"] == 0.005   # 0.01 over e1 and e3
    assert by_task["summarize"]["cost_per_success_usd"] is None   # s2 is not audited
    assert by_task["classify"]["cost_per_success_usd"] is None
    assert list(rows[0]) == KEYS + ["cost_per_success_usd", "target_cost_per_call_usd", "saving_per_day_usd"]


def test_calls_spend_and_cost_per_success_agree_with_report_by_task_shadow():
    audits = {"e1": True, "e2": False, "e3": True}
    mine = {r["task"]: r for r in opportunities(LOG, audits=audits)}
    for row in report(LOG, by="task", audits=audits, shadow=True):
        assert mine[row["group"]]["calls"] == row["calls"]
        assert mine[row["group"]]["cost_usd"] == row["cost_usd"]
        assert mine[row["group"]]["cost_per_success_usd"] == row["cost_per_success_usd"]


def test_a_task_with_no_final_record_has_no_cost_per_call_or_saving():
    log = [rec("d1", "draft", 0, False, "error", "x/cheap", 0.002, "2026-11-04T00:00:00Z"),
           rec("k1", "keep", 0, True, "ok", "x/cheap", 0.001, "2026-11-04T00:00:00Z")]
    rows = opportunities(log, target_cost_per_call=0.0)
    assert [r["task"] for r in rows] == ["keep", "draft"]   # a None saving sorts last
    draft = rows[1]
    assert (draft["calls"], draft["days"], draft["calls_per_day"]) == (0, 1, 0.0)
    assert draft["cost_per_call_usd"] is None and draft["saving_per_day_usd"] is None
    assert draft["cost_per_day_usd"] == 0.002
    assert rows[0]["saving_per_day_usd"] == 0.001


def test_a_task_only_shadow_records_reach_has_no_row():
    # review iter-499 must-fix 1: report --shadow gives it a row of routed zeros; it has nothing to save
    log = [rec("r1", "routed", 0, True, "ok", "x/cheap", 0.001, "2026-11-04T00:00:00Z"),
           rec("w1", "watched", 0, True, "ok", "x/big", 0.3, "2026-11-04T00:00:00Z", shadow=True)]
    assert sorted(r["group"] for r in report(log, by="task", shadow=True)) == ["routed", "watched"]
    assert [r["task"] for r in opportunities(log)] == ["routed"]
    assert opportunities(log)[0]["spend_share"] == 1.0


def test_a_large_int_target_is_a_float():
    (row,) = opportunities([rec("k1", "t", 0, True, "ok", "x/cheap", 0.001, "2026-11-04T00:00:00Z")],
                           target_cost_per_call=10 ** 30)
    assert row["target_cost_per_call_usd"] == 1e30 and row["saving_per_day_usd"] == 0.0


def test_no_spend_gives_no_share():
    log = [rec("z1", "free", 0, True, "ok", "x/cheap", 0.0, "2026-11-04T00:00:00Z")]
    (row,) = opportunities(log)
    assert row["spend_share"] is None and row["cost_per_call_usd"] == 0.0


def test_an_empty_log_gives_no_rows():
    assert opportunities([]) == [] and opportunities([], target_cost_per_call=0.5) == []


def test_days_count_utc_dates_both_ends():
    log = [rec("u1", "t", 0, True, "ok", "x/cheap", 0.001, "2026-11-01T23:59:59-08:00"),   # 11-02 UTC
           rec("u2", "t", 0, True, "ok", "x/cheap", 0.001, "2026-11-02T00:00:01"),         # no offset: UTC
           rec("u3", "t", 0, True, "ok", "x/cheap", 0.001, "2026-11-04T00:00:00Z")]
    (row,) = opportunities(log)
    assert row["days"] == 3 and row["calls_per_day"] == 1.0


@pytest.mark.parametrize("ts", ["yesterday", None, 20261101, "2026-13-01T00:00:00Z"])
def test_a_ts_that_cannot_be_read_is_a_value_error_naming_the_call(ts):
    log = [rec("ok1", "t", 0, True, "ok", "x/cheap", 0.001, "2026-11-01T00:00:00Z"),
           rec("bad1", "t", 0, True, "ok", "x/cheap", 0.001, ts)]
    with pytest.raises(ValueError, match="'bad1'"):
        opportunities(log)


def test_a_shadow_record_with_a_bad_ts_is_dropped_before_it_is_read():
    log = [rec("s1", "t", 0, True, "ok", "x/cheap", 0.001, "2026-11-01T00:00:00Z"),
           rec("s1", "t", 0, True, "ok", "x/big", 0.3, "never", shadow=True)]
    assert opportunities(log)[0]["days"] == 1


@pytest.mark.parametrize("target", [-0.001, math.nan, math.inf, -math.inf, True, False, "0.1", [0.1],
                                    10 ** 309, -(10 ** 309)])   # review iter-499 should-fix 1
def test_a_bad_target_is_a_value_error_before_any_record_is_read(target):
    with pytest.raises(ValueError, match="target_cost_per_call"):
        opportunities([{"task": "t", "ts": "never", "final": True}], target_cost_per_call=target)


def test_it_is_exported_after_drift_check():
    names = model_routing.__all__
    assert names[names.index("drift_check") + 1] == "opportunities"
    assert model_routing.opportunities is model_routing.monitor.opportunities


# --- the CLI -----------------------------------------------------------------------------------

def test_cli_table_and_json(tmp_path):
    log = write_log(tmp_path, LOG)
    code, out, err = run(["report", "--log", log, "--opportunities"])
    assert (code, err) == (0, "")
    lines = out.rstrip("\n").split("\n")
    assert lines[0].split() == KEYS
    body = [line.split() for line in lines[1:] if not set(line) <= set("-+| ")]
    assert body[0] == ["summarize", "2", "1", "2.000", "0.030000", "0.682", "0.015000", "0.030000"]
    assert [row[0] for row in body] == ["summarize", "classify", "extract"]
    assert len(lines) == len(body) + 2 and set(lines[1]) <= set("-+| ")   # review iter-499 nit 3
    code, out, err = run(["report", "--log", log, "--opportunities", "--json"])
    assert (code, err) == (0, "") and json.loads(out) == opportunities(LOG)


def test_cli_audits_and_target(tmp_path):
    log = write_log(tmp_path, LOG)
    audits = tmp_path / "audits.jsonl"
    audits.write_text("".join(json.dumps({"call_id": c, "correct": v}) + "\n"
                              for c, v in [("e1", True), ("e2", False), ("e3", True)]), encoding="utf-8")
    argv = ["report", "--log", log, "--opportunities", "--audits", str(audits),
            "--target-cost-per-call", "0.001"]
    code, out, err = run(argv)
    assert (code, err) == (0, "")
    lines = out.rstrip("\n").split("\n")
    assert lines[0].split() == KEYS + ["cost_per_success_usd", "target_cost_per_call_usd", "saving_per_day_usd"]
    body = [line.split() for line in lines[1:] if not set(line) <= set("-+| ")]
    assert body[0][0] == "summarize" and body[0][-3:] == ["n/a", "0.001000", "0.028000"]
    assert body[1][0] == "extract" and body[1][-3:] == ["0.005000", "0.001000", "0.002333"]
    code, out, _ = run(argv + ["--json"])
    assert json.loads(out) == opportunities(LOG, audits={"e1": True, "e2": False, "e3": True},
                                            target_cost_per_call=0.001)


@pytest.mark.parametrize("extra, word", [
    (["--opportunities", "--by", "task"], "--by"),
    (["--opportunities", "--by", "model"], "--by"),
    (["--opportunities", "--cache"], "--cache"),
    (["--opportunities", "--shadow"], "--shadow"),
    (["--target-cost-per-call", "0.1"], "--target-cost-per-call"),
])
def test_cli_flag_conflicts_exit_2_before_any_path_is_read(tmp_path, extra, word):
    code, out, err = run(["report", "--log", str(tmp_path / "missing.jsonl")] + extra)
    assert code == 2 and out == ""
    assert err.count("\n") == 1 and err.startswith("error: ") and word in err
    assert "missing.jsonl" not in err


@pytest.mark.parametrize("target", ["nan", "-1", "inf"])
def test_cli_bad_target_exits_2_before_any_log_is_read(tmp_path, target):
    code, out, err = run(["report", "--log", str(tmp_path / "missing.jsonl"), "--opportunities",
                          "--target-cost-per-call", target])
    assert code == 2 and out == ""
    assert err.count("\n") == 1 and "target_cost_per_call" in err and "missing.jsonl" not in err


def test_cli_a_log_with_no_routed_record_prints_the_header_alone(tmp_path):
    # review iter-499 nit 1
    log = write_log(tmp_path, [rec("w1", "t", 0, True, "ok", "x/big", 0.3, "2026-11-04T00:00:00Z", shadow=True)])
    code, out, err = run(["report", "--log", log, "--opportunities", "--target-cost-per-call", "0"])
    assert (code, err) == (0, "")
    lines = out.rstrip("\n").split("\n")
    assert lines[0].split() == KEYS + ["target_cost_per_call_usd", "saving_per_day_usd"]
    assert all(set(line) <= set("-+| ") for line in lines[1:])
    code, out, _ = run(["report", "--log", log, "--opportunities", "--json"])
    assert (code, json.loads(out)) == (0, [])


def test_cli_bad_ts_exits_2(tmp_path):
    log = write_log(tmp_path, [rec("bad1", "t", 0, True, "ok", "x/cheap", 0.001, "soon")])
    code, out, err = run(["report", "--log", log, "--opportunities"])
    assert code == 2 and out == "" and "'bad1'" in err and err.count("\n") == 1


def test_cli_report_without_the_flag_keeps_its_default_key(tmp_path):
    log = write_log(tmp_path, LOG)
    code, out, _ = run(["report", "--log", log])
    assert code == 0 and out.split("\n")[0].split()[0] == "model"
    code, out, _ = run(["report", "--log", log, "--json"])
    assert json.loads(out) == report(LOG)


# --- the spec and the note ---------------------------------------------------------------------

def test_design_and_changelog_state_v1_645():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert "- v1.645 `opportunities(records, *, audits=None, target_cost_per_call=None) -> list[dict]` (row OPP1a)" in eight3
    assert "`model_routing.__all__` gains `opportunities`, after `drift_check`." in eight3
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    assert "  - v1.645 `report --log PATH --opportunities [--target-cost-per-call USD] [--audits PATH] [--json]` (row OPP1a)" in ten
    assert ten.index("  - v1.643 `--by policy`") < ten.index("  - v1.645 `report --log PATH --opportunities")
    # v1.646 (row OPP1b) adds a later line, so the v1.645 line is found by its version
    [line] = [x for x in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").split("\n") if x.startswith("- v1.645 (")]
    assert line.startswith("- v1.645 (2026-11-25): spec, code and tests (8.3, 10, row OPP1a).")
    assert len(line.encode()) <= 600


# v1.646 (row OPP1b) restates each line's closing words for the route and the items it adds
NOTE_UBER = ("- In this library: `report` shows spend, failures and fallbacks per group, and `below_bar_calls` "
             "counts the calls answered by a model under the bar. From v1.645 `report --opportunities` is the "
             "savings report: per task from the log, its calls per day, share of spend, cost per call and per "
             "day and, with audits, per success, and with `--target-cost-per-call` the daily saving if a route at "
             "that cost served the task and cleared its bar, which the report assumes and does not check, its "
             "savings labeled hypothetical. From v1.646, with `--stats`, it also names for each task the route "
             "`select` admits and that route's list cost, `n/a` when no route clears the bar.\n")
NOTE_REPLIT = ("Which job to train for is the caller's; from v1.645 the savings report, `report --opportunities` "
               "run with `--target-cost-per-call`, shows by task the daily saving if a route at that cost "
               "served it and cleared the bar, which it assumes and does not check, and from v1.646, with `--stats` "
               "and `--audits` too, how many labelled items such a route would need to be admitted at the task's "
               "audited success rate. ")


def test_the_note_says_what_the_savings_report_does():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert note.count(NOTE_UBER) == 1
    assert note.count(NOTE_REPLIT) == 1
    assert "the planned savings report" not in note and "The change: a savings report" not in note


def test_no_evidence_or_research_script_or_workflow_runs_it():
    paths = [p for p in (ROOT / "evidence").rglob("*.py")] + [p for p in (ROOT / "research").rglob("*.py")]
    paths += list((ROOT / ".github" / "workflows").glob("*.yml"))
    assert paths
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "opportunities" not in text and "--opportunities" not in text, path
