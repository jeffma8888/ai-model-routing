"""DESIGN 8.3 and 10 v1.693 (row CACHE2b): `report` counts the anomaly records a monitor writes.

From v1.692 a `Monitor` given the tasks writes an anomaly record (`anomaly: cache_miss`) when a task and model's
prompt-cache hit rate over its last attempts falls under the task's floor, and every log reader drops it.
`report(records, ..., anomalies=True)` and `model-routing report --anomalies` read those records back: each row
gains, last, `cache_miss_anomalies`, the group's count of them, by `model` or `task` alone, since an anomaly
record holds no other key `report` groups by. Without the keyword every row and every byte of the CLI output is
v1.692's. The scenario is tests/test_cache_miss.py's: 20 cached attempts, then 10 uncached, floor 0.5, window 10.
"""

import contextlib
import copy
import hashlib
import inspect
import io
import json
import re
from pathlib import Path

import pytest

from model_routing import report
from model_routing.cli import main
from test_cache_miss import expected, run, stream, watched

ROOT = Path(__file__).resolve().parents[1]
V1_692_KEYS = ["group", "attempts", "ok", "errors", "invalid", "input_tokens", "output_tokens", "cost_usd",
               "routing_cost_usd", "calls", "failed_calls", "fallback_calls", "fallback_rate", "p50_latency_ms",
               "p95_latency_ms", "below_bar_calls"]
AUDIT_KEYS = ["audited_calls", "correct_calls", "cost_per_success_usd", "successes_per_100k_tokens"]
CACHE_KEYS = ["cached_input_tokens", "cache_counted_input_tokens", "cache_hit_rate"]
SHADOW_KEYS = ["shadow_calls", "shadow_failed_calls", "shadow_cost_usd"]


def scenario():
    """x/a: 20 attempts with 1,000 of 1,000 input tokens cached, then 10 with none, so the window of 10 reads
    (10 - k) / 10 after the k-th uncached attempt, first under 0.5 at k = 6 (c-25, 0.4); x/b: 5 cached attempts,
    a window never full. One anomaly record, right after c-25."""
    return run(watched(), stream([1000] * 20 + [0] * 10) + stream([800] * 5, start=30, model="x/b"))


def anomaly_records(records):
    return [rec for rec in records if "anomaly" in rec]


def rows_by_group(rows):
    return {row["group"]: row for row in rows}


# --- 8.3 v1.693: the keyword ---------------------------------------------------------------------

def test_the_keyword_is_the_last_and_off_by_default():
    params = inspect.signature(report).parameters
    assert list(params)[-3:] == ["cache", "shadow", "anomalies"]
    assert params["anomalies"].default is False


def test_the_scenario_holds_one_anomaly_at_the_hand_computed_attempt():
    records = scenario()
    [flag] = anomaly_records(records)
    after = records[records.index(flag) - 1]
    assert after["call_id"] == "c-25" and flag == expected(after, 0.4, 4000, 10000)
    assert len(records) == 36


def test_its_model_row_and_its_task_row_count_one_and_another_model_zero():
    records = scenario()
    by_model = rows_by_group(report(records, anomalies=True))
    assert list(by_model) == ["x/a", "x/b"]   # 0.030 then 0.005 of spend
    assert (by_model["x/a"]["cache_miss_anomalies"], by_model["x/b"]["cache_miss_anomalies"]) == (1, 0)
    [task] = report(records, by="task", anomalies=True)
    assert (task["group"], task["cache_miss_anomalies"]) == ("t", 1)


def test_two_runs_of_misses_give_two():
    # c-25 (0.4) disarms; c-34 reads 5 of 10 cached, 0.5, at the floor, and arms; c-45 reads c-36 to c-39 cached
    # and c-40 to c-45 not, 0.4, the second record
    records = run(watched(), stream([1000] * 20 + [0] * 10 + [1000] * 10 + [0] * 10))
    assert [records[records.index(rec) - 1]["call_id"] for rec in anomaly_records(records)] == ["c-25", "c-45"]
    [row] = report(records, anomalies=True)
    assert row["cache_miss_anomalies"] == 2
    [row] = report(records, by="task", anomalies=True)
    assert row["cache_miss_anomalies"] == 2


def test_the_key_is_last_after_every_other_option():
    rows = report(scenario(), audits={"c-0": True}, cache=True, shadow=True, anomalies=True)
    for row in rows:
        assert list(row) == V1_692_KEYS + AUDIT_KEYS + CACHE_KEYS + SHADOW_KEYS + ["cache_miss_anomalies"]
    assert list(report(scenario(), anomalies=True)[0]) == V1_692_KEYS + ["cache_miss_anomalies"]


@pytest.mark.parametrize("by", ["model", "task"])
@pytest.mark.parametrize("options", [{}, {"cache": True}, {"shadow": True},
                                     {"audits": {"c-0": True, "c-30": False}, "cache": True, "shadow": True}])
def test_every_other_key_keeps_its_value(by, options):
    records = scenario()
    with_count = report(records, by=by, anomalies=True, **options)
    assert [{k: v for k, v in row.items() if k != "cache_miss_anomalies"} for row in with_count] \
        == report(records, by=by, **options)


@pytest.mark.parametrize("by", ["model", "task"])
def test_without_the_keyword_every_row_keeps_its_v1_692_keys(by):
    records = scenario()
    rows = report(records, by=by)
    assert rows == report(records, by=by, anomalies=False)
    assert rows == report([rec for rec in records if "anomaly" not in rec], by=by)
    assert all(list(row) == V1_692_KEYS for row in rows)


def test_a_group_only_anomaly_records_reach_has_a_row_of_zeros():
    [flag] = anomaly_records(scenario())
    [row] = report([flag], audits={}, cache=True, shadow=True, anomalies=True)
    assert row == {"group": "x/a", "attempts": 0, "ok": 0, "errors": 0, "invalid": 0, "input_tokens": 0,
                   "output_tokens": 0, "cost_usd": 0.0, "routing_cost_usd": 0.0, "calls": 0, "failed_calls": 0,
                   "fallback_calls": 0, "fallback_rate": 0.0, "p50_latency_ms": None, "p95_latency_ms": None,
                   "below_bar_calls": 0, "audited_calls": 0, "correct_calls": 0, "cost_per_success_usd": None,
                   "successes_per_100k_tokens": None, "cached_input_tokens": 0, "cache_counted_input_tokens": 0,
                   "cache_hit_rate": None, "shadow_calls": 0, "shadow_failed_calls": 0, "shadow_cost_usd": 0.0,
                   "cache_miss_anomalies": 1}
    assert report([flag]) == [] and report([flag], by="task", anomalies=True)[0]["group"] == "t"


def test_rows_still_sort_by_spend_with_a_group_of_anomalies_alone_last():
    records = scenario()
    [flag] = anomaly_records(records)
    other = dict(flag, model="x/c", call_id="c-99")
    rows = report(records + [other], anomalies=True)
    assert [(r["group"], r["cache_miss_anomalies"]) for r in rows] == [("x/a", 1), ("x/b", 0), ("x/c", 1)]


def test_a_record_with_another_anomaly_adds_to_no_key_and_makes_no_row():
    records = scenario()
    [flag] = anomaly_records(records)
    odd = [dict(flag, anomaly="cache_write", model="x/c"), dict(flag, anomaly=None, model="x/d"),
           dict(flag, anomaly=["cache_miss"], model="x/e")]
    assert report(records + odd, anomalies=True) == report(records, anomalies=True)


def test_report_changes_no_record():
    records = scenario()
    before = copy.deepcopy(records)
    report(records, audits={"c-0": True}, cache=True, shadow=True, anomalies=True)
    assert records == before


def test_a_generator_is_read_once():
    rows = report(iter(scenario()), anomalies=True)
    assert [r["cache_miss_anomalies"] for r in rows] == [1, 0]


# --- 8.3 v1.693: the checks, before any record is read -------------------------------------------

def unread():
    raise AssertionError("a record was read")
    yield  # pragma: no cover


@pytest.mark.parametrize("value", [1, 0, "true", None, 1.0])
def test_an_anomalies_that_is_not_a_bool_is_a_value_error(value):
    with pytest.raises(ValueError, match=r"^anomalies must be True or False, got "):
        report(unread(), anomalies=value)


def test_the_shadow_check_comes_first_then_anomalies_then_an_unknown_by():
    with pytest.raises(ValueError, match="^shadow must be True or False"):
        report(unread(), by="nope", shadow=1, anomalies=1)
    with pytest.raises(ValueError, match="^anomalies must be True or False"):
        report(unread(), by="nope", anomalies=1)
    with pytest.raises(ValueError, match="^unknown report key 'nope'"):
        report(unread(), by="nope", anomalies=True)


@pytest.mark.parametrize("by", ["flavor", "family", "pricing_basis", "basis", "pinned_by", "policy", "tag:team"])
def test_another_by_is_a_value_error(by):
    message = ("anomalies=True groups by model or task alone, since an anomaly record holds no other key report "
               f"groups by, got by={by!r}")
    with pytest.raises(ValueError) as caught:
        report(unread(), by=by, anomalies=True)
    assert str(caught.value) == message
    assert report(scenario(), by=by)   # without the keyword the key is read as before


# --- 10 v1.693: the CLI --------------------------------------------------------------------------

def cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def write_log(tmp_path, records=None):
    path = tmp_path / "calls.jsonl"
    path.write_text("".join(json.dumps(rec) + "\n" for rec in (scenario() if records is None else records)),
                    encoding="utf-8")
    return str(path)


def test_the_table_gains_the_column_last(tmp_path):
    code, out, err = cli(["report", "--log", write_log(tmp_path), "--anomalies"])
    lines = out.splitlines()
    assert (code, err) == (0, "")
    assert lines[0].split() == ["model", "calls", "attempts", "errors", "invalid", "fallback_calls", "fallback_rate",
                                "cost_usd", "routing_cost_usd", "p50_ms", "p95_ms", "cache_miss_anomalies"]
    assert lines[2].split() == ["x/a", "30", "30", "0", "0", "0", "0.000", "0.030000", "0.030000", "5.0", "5.0", "1"]
    assert lines[3].split() == ["x/b", "5", "5", "0", "0", "0", "0.000", "0.005000", "0.005000", "5.0", "5.0", "0"]
    assert len(lines) == 4


def test_the_column_follows_audits_cache_and_shadow(tmp_path):
    audits = tmp_path / "audits.jsonl"
    audits.write_text(json.dumps({"call_id": "c-0", "correct": True}) + "\n", encoding="utf-8")
    code, out, err = cli(["report", "--log", write_log(tmp_path), "--by", "task", "--audits", str(audits),
                          "--cache", "--shadow", "--anomalies"])
    header, _, row = out.splitlines()
    assert (code, err) == (0, "")
    assert header.split()[-8:] == ["successes_per_100k_tokens", "cached_input_tokens", "cache_counted_input_tokens",
                                   "cache_hit_rate", "shadow_calls", "shadow_failed_calls", "shadow_cost_usd",
                                   "cache_miss_anomalies"]
    # t: 20 x 1,000 + 5 x 800 = 24,000 cached of 35 x 1,000 = 35,000, 0.686 to 3 decimals
    assert header.split()[0] == "task" and row.split()[0] == "t"
    assert row.split()[-7:] == ["24000", "35000", "0.686", "0", "0", "0.000000", "1"]


@pytest.mark.parametrize("by", [[], ["--by", "model"], ["--by", "task"]])
def test_json_prints_report_rows_with_the_key(tmp_path, by):
    code, out, err = cli(["report", "--log", write_log(tmp_path), "--anomalies", "--json"] + by)
    assert (code, err) == (0, "")
    key = "model" if by in ([], ["--by", "model"]) else "task"
    assert json.loads(out) == report(scenario(), by=key, anomalies=True)
    assert out == json.dumps(report(scenario(), by=key, anomalies=True), indent=2) + "\n"


@pytest.mark.parametrize("by", ["flavor", "family", "policy", "tag:team", "nope"])
def test_another_by_exits_2_before_any_path_is_read(tmp_path, by):
    code, out, err = cli(["report", "--log", str(tmp_path / "missing.jsonl"), "--by", by, "--anomalies"])
    assert (code, out) == (2, "")
    assert err == f"error: --anomalies counts records that hold only a task and a model, so it takes no --by {by}\n"


def test_a_flag_without_its_report_is_named_first(tmp_path):
    code, out, err = cli(["report", "--log", str(tmp_path / "missing.jsonl"), "--by", "family", "--anomalies",
                          "--stats", "s.json"])
    assert (code, out) == (2, "")
    assert err == "error: --stats needs --opportunities: only the savings report reads it\n"


def test_delegation_with_anomalies_exits_2_before_any_path_is_read(tmp_path):
    code, out, err = cli(["report", "--log", str(tmp_path / "missing.jsonl"), "--delegation", "--anomalies"])
    assert (code, out, err) == (2, "", "error: --delegation reads mode records alone, so it takes no --anomalies\n")
    code, out, err = cli(["report", "--log", str(tmp_path / "missing.jsonl"), "--delegation", "--anomalies",
                          "--registry", "r.json"])
    assert err == "error: --delegation reads mode records alone, so it takes no --registry\n"


def test_opportunities_with_anomalies_exits_2_before_any_path_is_read(tmp_path):
    code, out, err = cli(["report", "--log", str(tmp_path / "missing.jsonl"), "--opportunities", "--anomalies"])
    assert (code, out, err) == (2, "", "error: --opportunities groups by task alone, so it takes no --anomalies\n")
    code, out, err = cli(["report", "--log", str(tmp_path / "missing.jsonl"), "--opportunities", "--anomalies",
                          "--shadow"])
    assert err == "error: --opportunities groups by task alone, so it takes no --shadow\n"


def test_a_missing_log_exits_2(tmp_path):
    code, out, err = cli(["report", "--log", str(tmp_path / "missing.jsonl"), "--anomalies"])
    assert (code, out) == (2, "") and "missing.jsonl" in err and err.count("\n") == 1


# sha256 of f"{code}\n{stdout}\n{stderr}" for each run below, `cli` on `write_log`'s scenario log with its one
# anomaly record, computed with the v1.692 package (`git archive 5237e54 model_routing`), before v1.693 changed
# `report` and the CLI (review iter-553 nit 2)
V1_692 = [
    ([], "b21a567e8e96a43a143a86771b49282663873295f1ace8dba43535665a9f79ec"),
    (["--json"], "70f18a4e8063acaa898d849945b4b666e6b3806edd79af13e0082238f51ded47"),
    (["--by", "task"], "1b9110f78bb5aa29ec55f09f290c91aad85159324390b53f743225249e8eb96a"),
    (["--cache"], "f963c2788416ee0e444fa4f071d98e957d8fa9e3ac3a8a9595d287d3a11abd33"),
    (["--shadow"], "8f70acb3aee515b79ce7d4d23a78a92649184365adb6d72a7a86e6c3fb56e1ad"),
    (["--by", "task", "--cache", "--shadow", "--json"],
     "3d034b00b6672e63010c8cd935d1b80c5c67b0fd28a4e2a43395b3eea557e294"),
    (["--by", "family"], "57a05468155ed845d2f0909dc51a708224d45aec40932cb60d2b9cfb331a8818"),
    (["--opportunities"], "fa6979fb721bc20cd22f993ac31cd873342fcd12df8012fa481f4e01ea790a2d"),
    (["--opportunities", "--json"], "de3441492b0ea1772fb5ea0c79deb29e42a9e04ace004b17d6cf9116bb5cc031"),
    (["--delegation"], "28a497d99511cdf8d64d828fb02bc9c612a9d55cd20cc6e85179303e9c01120e"),
]


@pytest.mark.parametrize("extra, digest", V1_692)
def test_without_the_flag_each_report_keeps_its_v1_692_bytes(tmp_path, extra, digest):
    code, out, err = cli(["report", "--log", write_log(tmp_path)] + extra)
    assert hashlib.sha256(f"{code}\n{out}\n{err}".encode()).hexdigest() == digest


# --- the docs ------------------------------------------------------------------------------------

def test_report_help_names_the_flag():
    out = io.StringIO()
    with contextlib.redirect_stdout(out), pytest.raises(SystemExit) as stop:
        main(["report", "--help"])
    assert stop.value.code == 0 and "--anomalies" in out.getvalue()


def test_design_states_v1_693_in_8_3_and_10_and_the_changelog_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    eight2 = design[design.index("### 8.2 "):design.index("### 8.3 ")]
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    lead = ("- v1.693 `report(records, by=\"model\", audits=None, cache=False, shadow=False, anomalies=False)` "
            "(row CACHE2b, 8.1 and 8.2 v1.692): ")
    lines = eight3.splitlines()
    [mine] = [line for line in lines if line.startswith(lead)]
    at = lines.index(mine)
    assert lines[at - 1].startswith("- v1.692 anomaly records in a log (row CACHE2a, 8.1 v1.692): ")
    subs = lines[at + 1:at + 6]
    names = [line.split(":", 1)[0].split(",")[0].split(" (")[0] for line in subs]
    assert names == ["  - Count", "  - Rows", "  - Checks", "  - Tests", "  - Not in this version"]
    for kept in ("`cache_miss_anomalies`", "the string `cache_miss`", "a `by` other than `model` or `task`",
                 # v1.694 (row CACHE2c) adds the README sentence, tests/test_cache_miss_docs.py
                 "the README sentence (row CACHE2c, which v1.694 adds in 5.2)"):
        assert sum(line.count(kept) for line in [mine] + subs) >= 1, kept
    # v1.694 (row CACHE2c) adds the README sentence, tests/test_cache_miss_docs.py
    assert ("  - Not in this version: the anomaly count in `report` and the CLI (row CACHE2b, which 8.3 and 10 "
            "v1.693 add) and the README sentence (row CACHE2c, which v1.694 adds in 5.2).") in eight2
    [cli_line] = [line for line in ten.splitlines() if line.startswith(
        "  - v1.693 `report --log PATH [--by model|task] --anomalies` (row CACHE2b, 8.3 v1.693): ")]
    ten_lines = ten.splitlines()
    assert ten_lines[ten_lines.index(cli_line) - 1].startswith("  - v1.689 `report --log PATH --delegation ")
    # review iter-553 nit 1: an unknown key gets the CLI's message, before report's
    for kept in ("`error: --anomalies counts records that hold only a task and a model, so it takes no --by KEY`",
                 "known or not (so an unknown key gets this message, not `report`'s)",
                 "`error: --delegation reads mode records alone, so it takes no --anomalies`",
                 "`error: --opportunities groups by task alone, so it takes no --anomalies`",
                 "Without the option every output keeps its bytes"):
        assert cli_line.count(kept) == 1, kept
    assert "- `report --log PATH [--by KEY] [--json] [--audits PATH] [--cache] [--shadow] [--anomalies]`" in ten
    for line in [mine, cli_line] + subs:
        assert len(line.encode("utf-8")) <= 6_000 and "\u2014" not in line and "\u2013" not in line
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    [entry] = [line for line in changelog if line.startswith("- v1.693 (")]
    assert entry.startswith("- v1.693 (2026-11-27): spec, code and tests (8.3, 10, row CACHE2b). ")
    assert len(entry.encode("utf-8")) <= 600
    # v1.693 or a later version tops the Status line (it pinned v1.693 until v1.694, row CACHE2c, came next)
    status = design.splitlines()[2]
    assert re.match(r"Status: v1\.(\d+), ", status) and int(re.match(r"Status: v1\.(\d+), ", status)[1]) >= 693
    assert status.count("; v1.693, spec, code and tests: `report(..., anomalies=True)` ") == 1
