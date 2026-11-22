"""DESIGN 8.2, 8.3 and 10 v1.569 (row CPS1b): cost per success in the report, from audits.

`load_audits` reads one `call_id` and `correct` per audited call; `report(..., audits=...)` and
`model-routing report --audits PATH` join them to each call's final attempt and add
`audited_calls`, `correct_calls`, `cost_per_success_usd` and `successes_per_100k_tokens`, which are
`None` (`n/a`), never 0, until every call of the group is audited. Without audits every row and
every byte of the CLI output is v1.568's.
"""

import contextlib
import io
import json
from pathlib import Path

import pytest

import model_routing
from model_routing import monitor, report
from model_routing.cli import main

RED = pytest.mark.xfail(strict=True, reason="v1.569 lands in the implementing commit (row CPS1b)")
A, B = "fiction/a", "fiction/b"
NOTE = Path(__file__).resolve().parent.parent / "research" / "production-lessons.md"
V1_568_KEYS = ["group", "attempts", "ok", "errors", "invalid", "input_tokens", "output_tokens",
               "cost_usd", "routing_cost_usd", "calls", "failed_calls", "fallback_calls",
               "fallback_rate", "p50_latency_ms", "p95_latency_ms", "below_bar_calls"]
NEW_KEYS = ["audited_calls", "correct_calls", "cost_per_success_usd", "successes_per_100k_tokens"]
AUDITS = {"c1": True, "c2": True, "c3": False, "c4": True}


def _rec(call_id, model, attempt, final, outcome, cost, tokens_in, tokens_out, **extra):
    record = {"ts": "2026-01-01T00:00:00Z", "call_id": call_id, "task": "judge",
              "flavor": "cost_effective", "model": model, "family": model.split("/")[1],
              "attempt": attempt, "final": final, "outcome": outcome, "error": None,
              "latency_ms": 10.0, "input_tokens": tokens_in, "output_tokens": tokens_out,
              "cost_usd": cost, "routing_cost_usd": cost, "below_bar": False,
              "basis": "measured", "tags": {}}
    record.update(extra)
    return record


def _records():
    """c1 and c3 end ok on A; c2 fails on A then ends ok on B; c4 ends invalid on B."""
    return [
        _rec("c1", A, 0, True, "ok", 0.1, 100, 10),
        _rec("c2", A, 0, False, "error", 0.05, 50, 0),
        _rec("c2", B, 1, True, "ok", 0.3, 200, 20),
        _rec("c3", A, 0, True, "ok", 0.1, 100, 10),
        _rec("c4", B, 0, True, "invalid", 0.2, 100, 5),
    ]


def _tail(row):
    return tuple(row[key] for key in NEW_KEYS)


def _by_group(rows):
    return {row["group"]: _tail(row) for row in rows}


# ---- 8.3 report(records, by, audits) ----------------------------------------------------------

def test_without_audits_every_row_keeps_the_v1_568_keys():
    assert [list(row) for row in report(_records())] == [V1_568_KEYS, V1_568_KEYS]


@RED
def test_audits_none_is_the_default():
    assert report(_records(), audits=None) == report(_records())


@RED
def test_the_hand_computed_case_by_model():
    rows = report(_records(), audits=AUDITS)
    assert [list(row) for row in rows] == [V1_568_KEYS + NEW_KEYS] * 2
    # B: c2 (0.05 on A, then 0.3 on B, ok, audited correct) and c4 (invalid, audited correct,
    # which never counts): (0.05 + 0.3 + 0.2) / 1; tokens 50 + 0 + 200 + 20 + 100 + 5 = 375.
    # A: c1 (correct) and c3 (audited wrong): (0.1 + 0.1) / 1; tokens 110 + 110 = 220.
    assert _by_group(rows) == {B: (2, 1, 0.55, 266.666667), A: (2, 1, 0.2, 454.545455)}
    assert [row["group"] for row in rows] == [B, A]
    assert rows[1]["cost_usd"] == 0.25  # the attempt sums are unchanged: c2's 0.05 stays on A


@RED
def test_the_hand_computed_case_by_task():
    (row,) = report(_records(), by="task", audits=AUDITS)
    # 0.75 over 2 correct calls (c1, c2); 2 * 100000 / 595 tokens.
    assert _tail(row) == (4, 2, 0.375, 336.134454)


@RED
def test_incomplete_coverage_gives_none_never_zero():
    audits = {key: value for key, value in AUDITS.items() if key != "c3"}
    assert _by_group(report(_records(), audits=audits)) == {
        B: (2, 1, 0.55, 266.666667), A: (1, 1, None, None)}


@RED
def test_no_success_gives_no_cost_per_success_and_zero_successes_per_tokens():
    audits = dict(AUDITS, c1=False)
    assert _by_group(report(_records(), audits=audits))[A] == (2, 0, None, 0.0)


@RED
def test_an_unaudited_ok_never_counts():
    assert _by_group(report(_records(), audits={})) == {
        B: (0, 0, None, None), A: (0, 0, None, None)}


@RED
@pytest.mark.parametrize("value", [1, "true", None, 1.0])
def test_only_true_counts_as_correct(value):
    audits = dict(AUDITS, c1=value)
    assert _by_group(report(_records(), audits=audits))[A] == (2, 0, None, 0.0)


@RED
def test_a_failed_call_never_counts_whatever_its_audit():
    records = [_rec("c4", B, 0, True, "invalid", 0.2, 100, 5),
               _rec("c5", B, 0, True, "error", 0.0, 0, 0, error="ProviderError: outage")]
    assert _by_group(report(records, audits={"c4": True, "c5": True})) == {B: (2, 0, None, 0.0)}


@RED
@pytest.mark.parametrize("change", [
    lambda r: r.pop("output_tokens"), lambda r: r.pop("input_tokens"),
    lambda r: r.update(output_tokens=None),
])
def test_a_missing_token_count_gives_no_successes_per_tokens(change):
    records = _records()
    change(records[3])  # c3, an attempt of a call of group A
    assert _by_group(report(records, audits=AUDITS))[A] == (2, 1, 0.2, None)


@RED
def test_zero_tokens_gives_no_successes_per_tokens():
    records = [_rec("c1", A, 0, True, "ok", 0.1, 0, 0)]
    assert _by_group(report(records, audits={"c1": True})) == {A: (1, 1, 0.1, None)}


@RED
def test_audits_of_unknown_calls_are_ignored():
    audits = dict(AUDITS, elsewhere=True)
    assert report(_records(), audits=audits) == report(_records(), audits=AUDITS)


@RED
def test_attempts_of_a_call_with_no_final_record_belong_to_no_call():
    records = _records() + [_rec("c5", A, 0, False, "error", 1.0, 10, 10)]
    rows = {row["group"]: row for row in report(records, audits=dict(AUDITS, c5=True))}
    assert _tail(rows[A]) == (2, 1, 0.2, 454.545455)
    assert rows[A]["cost_usd"] == 1.25


@RED
def test_a_group_with_no_calls():
    records = [_rec("c2", A, 0, False, "error", 0.05, 50, 0), _rec("c2", B, 1, True, "ok", 0.3, 200, 20)]
    # B: (0.05 + 0.3) / 1 and 100000 / 270
    assert _by_group(report(records, audits={"c2": True})) == {
        B: (1, 1, 0.35, 370.37037), A: (0, 0, None, None)}


@RED
def test_two_final_records_with_one_call_id_raise_with_audits_only():
    records = _records() + [_rec("c1", B, 0, True, "ok", 0.1, 100, 10)]
    assert len(report(records)) == 2
    with pytest.raises(ValueError, match="c1"):
        report(records, audits=AUDITS)


# ---- 8.2 load_audits ----------------------------------------------------------------------------

def _write(tmp_path, lines, name="audits.jsonl"):
    path = tmp_path / name
    path.write_text("".join(line + "\n" for line in lines), encoding="utf-8")
    return path


@RED
def test_load_audits_reads_each_line_skips_blanks_and_ignores_other_keys(tmp_path):
    path = _write(tmp_path, [json.dumps({"call_id": "c1", "correct": True, "grader": "x"}), "",
                             "   ", json.dumps({"correct": False, "call_id": "c3"})])
    audits = monitor.load_audits(path)
    assert audits == {"c1": True, "c3": False} and list(audits) == ["c1", "c3"]
    assert monitor.load_audits(str(path)) == audits


@RED
@pytest.mark.parametrize("bad", [
    "not json", "[1, 2]", '{"correct": true}', '{"call_id": "c2"}', '{"call_id": "", "correct": true}',
    '{"call_id": 7, "correct": true}', '{"call_id": "c2", "correct": 1}',
    '{"call_id": "c2", "correct": "true"}', '{"call_id": "c2", "correct": null}',
    '{"call_id": "c1", "correct": false}',
])
def test_load_audits_rejects_a_bad_line_with_path_and_number(tmp_path, bad):
    path = _write(tmp_path, ['{"call_id": "c1", "correct": true}', "", bad])
    with pytest.raises(ValueError, match=r"audits\.jsonl:3"):
        monitor.load_audits(path)


@RED
def test_load_audits_is_exported_right_after_load_records():
    names = model_routing.__all__
    assert names[names.index("load_records") + 1] == "load_audits"
    assert model_routing.load_audits is monitor.load_audits


# ---- 10 the CLI ---------------------------------------------------------------------------------

def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def _log(tmp_path, records=None):
    path = tmp_path / "calls.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in (records or _records())), encoding="utf-8")
    return path


V1_568_TEXT = (
    "model      calls  attempts  errors  invalid  fallback_calls  fallback_rate  cost_usd  "
    "routing_cost_usd  p50_ms  p95_ms\n"
    "---------  -----  --------  ------  -------  --------------  -------------  --------  "
    "----------------  ------  ------\n"
    "fiction/b  2      2         0       1        1               0.500          0.500000  "
    "0.500000          10.0    10.0\n"
    "fiction/a  2      3         1       0        0               0.000          0.250000  "
    "0.250000          10.0    10.0\n")


def test_the_cli_without_audits_prints_v1_568_bytes(tmp_path):
    assert _run(["report", "--log", str(_log(tmp_path))]) == (0, V1_568_TEXT, "")


@RED
def test_the_cli_table_gains_four_columns_after_p95_with_n_a(tmp_path):
    audits = _write(tmp_path, [json.dumps({"call_id": k, "correct": v})
                               for k, v in AUDITS.items() if k != "c3"])
    code, out, err = _run(["report", "--log", str(_log(tmp_path)), "--audits", str(audits)])
    assert (code, err) == (0, "")
    assert out == (
        "model      calls  attempts  errors  invalid  fallback_calls  fallback_rate  cost_usd  "
        "routing_cost_usd  p50_ms  p95_ms  audited_calls  correct_calls  cost_per_success_usd  "
        "successes_per_100k_tokens\n"
        "---------  -----  --------  ------  -------  --------------  -------------  --------  "
        "----------------  ------  ------  -------------  -------------  --------------------  "
        "-------------------------\n"
        "fiction/b  2      2         0       1        1               0.500          0.500000  "
        "0.500000          10.0    10.0    2              1              0.550000              "
        "266.667\n"
        "fiction/a  2      3         1       0        0               0.000          0.250000  "
        "0.250000          10.0    10.0    1              1              n/a                   "
        "n/a\n")


@RED
def test_the_cli_json_has_the_four_keys_with_null(tmp_path):
    audits = _write(tmp_path, [json.dumps({"call_id": k, "correct": v})
                               for k, v in AUDITS.items() if k != "c3"])
    code, out, err = _run(["report", "--log", str(_log(tmp_path)), "--audits", str(audits), "--json"])
    assert (code, err) == (0, "")
    rows = json.loads(out)
    assert [list(row) for row in rows] == [V1_568_KEYS + NEW_KEYS] * 2
    assert _by_group(rows) == {B: (2, 1, 0.55, 266.666667), A: (1, 1, None, None)}


@RED
@pytest.mark.parametrize("lines,where", [
    (['{"call_id": "c1", "correct": true}', '{"call_id": "c2", "correct": "yes"}'], "audits.jsonl:2"),
    (None, "audits.jsonl"),
])
def test_a_bad_or_missing_audits_file_exits_2_with_one_error_line(tmp_path, lines, where):
    path = _write(tmp_path, lines) if lines is not None else tmp_path / "audits.jsonl"
    code, out, err = _run(["report", "--log", str(_log(tmp_path)), "--audits", str(path)])
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1 and where in err


# ---- the note ---------------------------------------------------------------------------------

@RED
def test_the_uber_line_names_the_shipped_report_columns():
    text = NOTE.read_text(encoding="utf-8")
    uber = text[text.index("### Hold the model fixed, and count cost per finished outcome"):]
    line = next(line for line in uber.splitlines() if line.startswith("- In this library: "))
    assert "The change named in the Harvey lesson on finished work adds cost per success" not in line
    for phrase in ("`report --audits`", "cost per success", "successes per 100,000 tokens",
                   "fallbacks included", "`n/a`"):
        assert phrase in line, phrase
