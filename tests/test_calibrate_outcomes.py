"""Per-item outcomes from labeled results (DESIGN 4.3 and 10 v1.602, row GATE1b).

`item_outcomes` gives one record per result row, with the sha256 of the labeled file, so that two
routes can later be paired on the same items (4.7, row GATE1c); `calibrate --outcomes FILE` appends
them to FILE. The stats file and the output without the option are v1.601's bytes, pinned here as
v1.601's code wrote them.
"""

import hashlib
import json
from pathlib import Path

import pytest

import model_routing
from model_routing import Stats, calibrate_from_results, item_outcomes
from model_routing.cli import main

ROOT = Path(__file__).resolve().parent.parent
HASH = hashlib.sha256(b"labeled file").hexdigest()

PIN_ROWS = [
    {"task": "judge", "model": "fiction/a", "correct": True, "input_tokens": 100, "output_tokens": 10},
    {"task": "judge", "model": "fiction/a", "prediction": "yes", "gold": "no"},
    {"task": "judge", "model": "fiction/b", "correct": True, "slice": "deep"},
]
# v1.601's bytes for PIN_ROWS calibrated into a new stats file (captured from 16a8fd6)
PIN_STATS = ('{\n  "stats": [\n    {\n      "task": "judge",\n      "model": "fiction/a",\n'
             '      "successes": 1,\n      "trials": 2,\n      "input_tokens": 100,\n'
             '      "output_tokens": 10,\n      "token_trials": 1\n    },\n    {\n'
             '      "task": "judge",\n      "model": "fiction/b",\n      "successes": 1,\n'
             '      "trials": 1\n    },\n    {\n      "task": "judge@deep",\n'
             '      "model": "fiction/b",\n      "successes": 1,\n      "trials": 1\n    }\n  ]\n}\n')
PIN_STDOUT = ("task        model      successes  trials  lower_bound_95\n"
              "----------  ---------  ---------  ------  --------------\n"
              "judge       fiction/a  1          2       0.0945\n"
              "judge       fiction/b  1          1       0.2065\n"
              "judge@deep  fiction/b  1          1       0.2065\n"
              "\nwrote <STATS>\n")


def with_items(rows):
    return [dict(row, item=f"q{n}") for n, row in enumerate(rows)]


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def calibrate(tmp_path, rows, *extra, results=None, stats=None):
    results = results or tmp_path / "results.jsonl"
    stats = stats or tmp_path / "stats.json"
    if rows is not None:
        write_jsonl(results, rows)
    return main(["calibrate", "--results", str(results), "--stats", str(stats), *extra]), results, stats


# --- item_outcomes --------------------------------------------------------------------------------

def test_one_record_per_row_in_row_order_with_the_keys_in_order():
    rows = [
        {"task": "judge", "model": "fiction/a", "item": "q1", "correct": True},
        {"task": "judge", "model": "fiction/b", "item": "q1", "prediction": "yes", "gold": "no"},
        {"task": "judge", "model": "fiction/b", "item": "q2", "prediction": "no", "gold": "no", "slice": "deep"},
        {"task": "judge", "model": "fiction/a@terse", "item": "q2", "correct": False, "slice": None},
        {"task": "judge", "model": "fiction/a>fiction/b@sig", "item": "q3", "correct": True, "escalated": True},
        {"task": "judge", "model": "proc:review@1", "item": "q4", "correct": False, "cost_usd": 0.5},
    ]
    records = item_outcomes(rows, dataset_sha256=HASH)
    assert records == [
        {"task": "judge", "slice": None, "route": "fiction/a", "item": "q1", "correct": True, "dataset_sha256": HASH},
        {"task": "judge", "slice": None, "route": "fiction/b", "item": "q1", "correct": False, "dataset_sha256": HASH},
        {"task": "judge", "slice": "deep", "route": "fiction/b", "item": "q2", "correct": True, "dataset_sha256": HASH},
        {"task": "judge", "slice": None, "route": "fiction/a@terse", "item": "q2", "correct": False,
         "dataset_sha256": HASH},
        {"task": "judge", "slice": None, "route": "fiction/a>fiction/b@sig", "item": "q3", "correct": True,
         "dataset_sha256": HASH},
        {"task": "judge", "slice": None, "route": "proc:review@1", "item": "q4", "correct": False,
         "dataset_sha256": HASH},
    ]
    for record in records:
        assert list(record) == ["task", "slice", "route", "item", "correct", "dataset_sha256"]
        assert type(record["correct"]) is bool


def test_a_sliced_row_gives_one_record_while_the_stats_count_it_twice():
    rows = [{"task": "judge", "model": "fiction/a", "item": "q1", "correct": True, "slice": "deep"}]
    assert len(item_outcomes(rows, dataset_sha256=HASH)) == 1
    stats = calibrate_from_results(rows)
    assert stats.get("judge", "fiction/a") == (1, 1) and stats.get("judge@deep", "fiction/a") == (1, 1)


def test_the_records_hold_exactly_the_trials_the_stats_count():
    rows = []
    for n in range(40):
        route = ("fiction/a", "fiction/b", "fiction/c")[n % 3]
        row = {"task": ("judge", "extract")[n % 2], "model": route, "item": f"q{n % 7}", "correct": n % 5 != 0}
        if n % 4 == 0:
            row["slice"] = "deep"
        rows.append(row)
    records = item_outcomes(rows, dataset_sha256=HASH)
    stats = calibrate_from_results(rows)
    for (task, route), (successes, trials) in stats.items():
        if "@" in task:
            base, slice_name = task.split("@")
            mine = [r for r in records if r["task"] == base and r["slice"] == slice_name and r["route"] == route]
        else:
            mine = [r for r in records if r["task"] == task and r["route"] == route]
        assert (sum(r["correct"] for r in mine), len(mine)) == (successes, trials)
    assert len(records) == len(rows)


def test_a_provider_error_is_what_its_row_says():
    rows = [{"task": "judge", "model": "fiction/a", "item": "q1", "correct": False, "error": "timeout"}]
    assert item_outcomes(rows, dataset_sha256=HASH)[0]["correct"] is False
    assert item_outcomes([], dataset_sha256=HASH) == []


def test_an_iterable_is_read_once_and_no_row_is_changed():
    rows = with_items(PIN_ROWS)
    before = json.dumps(rows, sort_keys=True)
    records = item_outcomes(iter(rows), dataset_sha256=HASH)
    assert [r["item"] for r in records] == ["q0", "q1", "q2"]
    assert json.dumps(rows, sort_keys=True) == before
    records[0]["correct"] = "changed"
    assert rows[0]["correct"] is True


@pytest.mark.parametrize("key, value", [
    ("item", None), ("item", ""), ("item", 7), ("item", ["q1"]),
    ("task", ""), ("task", 3), ("model", ""), ("model", 3),
])
def test_task_model_and_item_must_be_non_empty_strings(key, value):
    good = {"task": "judge", "model": "fiction/a", "item": "q1", "correct": True}
    bad = dict(good, **{key: value})
    with pytest.raises(ValueError, match=f"needs a non-empty string '{key}'"):
        item_outcomes([good, bad], dataset_sha256=HASH)


def test_a_row_without_an_item_is_refused_only_here():
    rows = [{"task": "judge", "model": "fiction/a", "correct": True}]
    assert calibrate_from_results(rows).get("judge", "fiction/a") == (1, 1)
    with pytest.raises(ValueError, match="needs a non-empty string 'item'"):
        item_outcomes(rows, dataset_sha256=HASH)


@pytest.mark.parametrize("row", [
    {"task": "judge", "model": "fiction/a", "item": "q1", "correct": "true"},
    {"task": "judge", "model": "fiction/a", "item": "q1"},
    {"task": "judge", "model": "fiction/a", "item": "q1", "correct": True, "slice": "a@b"},
    {"task": "judge", "model": "fiction/a", "item": "q1", "correct": True, "input_tokens": 3},
    {"task": "judge", "model": "fiction/a>fiction/b@sig", "item": "q1", "correct": True},
    "not a row",
])
def test_every_row_is_checked_as_calibrate_checks_it_before_a_record_is_returned(row):
    good = {"task": "judge", "model": "fiction/a", "item": "q0", "correct": True}
    with pytest.raises(ValueError) as calibrate_error:
        calibrate_from_results([good, row])
    with pytest.raises(ValueError) as outcomes_error:
        item_outcomes([good, row], dataset_sha256=HASH)
    assert str(outcomes_error.value) == str(calibrate_error.value)


@pytest.mark.parametrize("value", [HASH.upper(), HASH[:-1], HASH + "0", "g" * 64, None, 7,
                                   HASH.encode(), " " + HASH[1:]])
def test_the_hash_is_64_lowercase_hex_digits(value):
    with pytest.raises(ValueError, match="dataset_sha256"):
        item_outcomes([{"task": "judge", "model": "fiction/a", "item": "q1", "correct": True}],
                      dataset_sha256=value)


def test_the_hash_is_keyword_only():
    with pytest.raises(TypeError):
        item_outcomes([], HASH)


# --- the calibrate command -----------------------------------------------------------------------

def test_without_the_option_the_stats_file_and_output_are_v1_601_bytes(tmp_path, capsys):
    code, _, stats = calibrate(tmp_path, PIN_ROWS)
    assert code == 0
    assert stats.read_text(encoding="utf-8") == PIN_STATS
    captured = capsys.readouterr()
    assert captured.out == PIN_STDOUT.replace("<STATS>", str(stats)) and captured.err == ""


def test_with_the_option_the_stats_file_is_the_same_and_one_line_is_added(tmp_path, capsys):
    outcomes = tmp_path / "outcomes.jsonl"
    code, results, stats = calibrate(tmp_path, with_items(PIN_ROWS), "--outcomes", str(outcomes))
    assert code == 0
    assert stats.read_text(encoding="utf-8") == PIN_STATS
    digest = hashlib.sha256(results.read_bytes()).hexdigest()
    captured = capsys.readouterr()
    assert captured.out == (PIN_STDOUT.replace("<STATS>", str(stats))
                            + f"appended 3 outcomes to {outcomes}, dataset_sha256 {digest}\n")
    assert captured.err == ""


def test_the_outcomes_file_holds_one_json_dumps_per_record_with_the_file_hash(tmp_path):
    outcomes = tmp_path / "outcomes.jsonl"
    rows = with_items(PIN_ROWS)
    code, results, _ = calibrate(tmp_path, rows, "--outcomes", str(outcomes))
    assert code == 0
    digest = hashlib.sha256(results.read_bytes()).hexdigest()
    expected = item_outcomes(rows, dataset_sha256=digest)
    assert outcomes.read_text(encoding="utf-8") == "".join(json.dumps(r) + "\n" for r in expected)
    assert [json.loads(line)["dataset_sha256"] for line in outcomes.read_text().splitlines()] == [digest] * 3


def test_the_hash_is_of_the_file_bytes_so_a_blank_line_changes_it(tmp_path):
    rows = with_items(PIN_ROWS)
    first = tmp_path / "first.jsonl"
    code, results, _ = calibrate(tmp_path, rows, "--outcomes", str(first))
    assert code == 0
    results.write_text(results.read_text(encoding="utf-8") + "\n", encoding="utf-8")
    second = tmp_path / "second.jsonl"
    assert main(["calibrate", "--results", str(results), "--stats", str(tmp_path / "s2.json"),
                 "--outcomes", str(second)]) == 0
    one = {json.loads(x)["dataset_sha256"] for x in first.read_text().splitlines()}
    two = {json.loads(x)["dataset_sha256"] for x in second.read_text().splitlines()}
    assert len(one) == len(two) == 1 and one != two
    assert two == {hashlib.sha256(results.read_bytes()).hexdigest()}


def test_a_second_run_appends_as_the_stats_merge(tmp_path):
    outcomes = tmp_path / "outcomes.jsonl"
    rows = with_items(PIN_ROWS)
    assert calibrate(tmp_path, rows, "--outcomes", str(outcomes))[0] == 0
    once = outcomes.read_text(encoding="utf-8")
    code, _, stats = calibrate(tmp_path, rows, "--outcomes", str(outcomes))
    assert code == 0
    assert outcomes.read_text(encoding="utf-8") == once + once
    assert Stats.load(stats).get("judge", "fiction/a") == (2, 4)


def test_a_newline_is_written_first_when_the_file_does_not_end_in_one(tmp_path):
    outcomes = tmp_path / "outcomes.jsonl"
    outcomes.write_text('{"kept": true}', encoding="utf-8")
    rows = with_items(PIN_ROWS[:1])
    code, results, _ = calibrate(tmp_path, rows, "--outcomes", str(outcomes))
    assert code == 0
    digest = hashlib.sha256(results.read_bytes()).hexdigest()
    lines = outcomes.read_text(encoding="utf-8").split("\n")
    assert lines[0] == '{"kept": true}' and lines[2] == ""
    assert json.loads(lines[1]) == {"task": "judge", "slice": None, "route": "fiction/a", "item": "q0",
                                    "correct": True, "dataset_sha256": digest}
    empty = tmp_path / "empty.jsonl"
    empty.write_text("", encoding="utf-8")
    assert calibrate(tmp_path, rows, "--outcomes", str(empty))[0] == 0
    assert empty.read_text(encoding="utf-8").count("\n") == 1 and not empty.read_text().startswith("\n")


def test_a_row_without_an_item_exits_two_and_writes_nothing(tmp_path, capsys):
    outcomes = tmp_path / "outcomes.jsonl"
    code, _, stats = calibrate(tmp_path, PIN_ROWS, "--outcomes", str(outcomes))
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ") and captured.err.count("\n") == 1 and "item" in captured.err
    assert not stats.exists() and not outcomes.exists()
    assert calibrate(tmp_path, PIN_ROWS)[0] == 0


def test_a_refused_row_leaves_existing_files_unchanged(tmp_path):
    outcomes = tmp_path / "outcomes.jsonl"
    assert calibrate(tmp_path, with_items(PIN_ROWS), "--outcomes", str(outcomes))[0] == 0
    stats_before = (tmp_path / "stats.json").read_bytes()
    outcomes_before = outcomes.read_bytes()
    rows = with_items(PIN_ROWS) + [{"task": "judge", "model": "fiction/a", "correct": True}]
    assert calibrate(tmp_path, rows, "--outcomes", str(outcomes))[0] == 2
    assert (tmp_path / "stats.json").read_bytes() == stats_before and outcomes.read_bytes() == outcomes_before


@pytest.mark.parametrize("target", ["results", "stats"])
def test_an_outcomes_file_naming_the_results_or_the_stats_file_is_refused(tmp_path, capsys, target):
    results, stats = tmp_path / "results.jsonl", tmp_path / "stats.json"
    write_jsonl(results, with_items(PIN_ROWS))
    stats.write_text(PIN_STATS, encoding="utf-8")
    results_before, stats_before = results.read_bytes(), stats.read_bytes()
    named = {"results": results, "stats": stats}[target]
    alias = tmp_path / "." / named.name
    code = main(["calibrate", "--results", str(results), "--stats", str(stats), "--outcomes", str(alias)])
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("error: ") and captured.err.count("\n") == 1
    assert results.read_bytes() == results_before and stats.read_bytes() == stats_before


# --- exports, spec and the production note -------------------------------------------------------

def test_item_outcomes_is_exported_after_promotion_check():
    names = model_routing.__all__
    assert names[names.index("PromotionCheck") + 1] == "item_outcomes"
    assert model_routing.item_outcomes is model_routing.stats.item_outcomes


def test_design_names_the_contract():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    # review iter-453 nit 1: the Status line keeps five versions (tests/test_design_status.py), so the
    # version is pinned by its changelog line, which stays
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert sum(line.startswith("- v1.602 (2026-11-23): spec, code and tests (3, 4.3, 4.7, 10, row GATE1b). ")
               for line in changelog) == 1
    assert ("  stats.py        wilson_lower_bound, items_needed (v1.140), Stats, calibrate_from_results, "
            "item_outcomes (v1.602, 4.3)\n") in design
    four3 = design[design.index("### 4.3 "):design.index("### 4.4 ")]
    assert ("- v1.602 per-item outcomes (row GATE1b): `item_outcomes(rows: Iterable[dict], *, dataset_sha256: str) "
            "-> list[dict]` gives one outcome record per result row, in row order") in four3
    assert "(review iter-449 should-fix 3(c))" in four3
    assert "`model_routing.__all__` gains `item_outcomes`, after `PromotionCheck`\n" in four3
    four7 = design[design.index("### 4.7 "):design.index("## 5. ")]
    assert "(row GATE1b), which v1.602 adds (4.3 and 10); " in four7
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    assert "  - v1.602 `calibrate ... [--outcomes FILE]` (row GATE1b): " in ten
    assert "`appended N outcomes to FILE, dataset_sha256 HEX`" in ten


def test_the_changelog_line_names_the_row():
    lines = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in lines if line.startswith("- v1.602 (2026-11-23): ")]
    assert len(mine) == 1
    assert "(3, 4.3, 4.7, 10, row GATE1b)" in mine[0]


def test_the_note_names_the_hash_as_shipped():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    locked = note[note.index("### Switch models only on locked data and a significant result"):]
    line = [x for x in locked.splitlines() if x.startswith("- In this library: ")][0]
    assert ("From v1.602 `calibrate --outcomes FILE` writes each labeled row's outcome with the sha256 of the "
            "results file to a file kept apart from the stats. ") in line
    assert "The change still planned" not in line  # the command shipped at v1.603 (row GATE1c)
    assert "record the labeled file's hash with the stats" not in note
