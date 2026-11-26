"""DESIGN 4.3 v1.662 (row JUDGE1bba, the second part of JUDGE1b): label sources in stats.

Beside its counts, `Stats` keeps, per `(task, model_id)`, how many of its trials came from
results rows that name each label source. A `calibrate_from_results` row may carry
`label_source`, a non-empty string, and adds one trial of that source under its key (both keys
for a sliced row); on such a row `prediction` and `gold` agree only when they have the same type
and are equal (review iter-516 should-fix 1), and a row without the key keeps v1.661's `==`.
`.add(..., label_sources=...)`, `.label_sources`, `.merge`, `.save` and `.load` carry the counts,
and a `Stats` without one saves v1.661's bytes. The rows are synthetic, so each count is computed
by hand. No README transcript, evidence or research script or workflow writes `label_source`,
so every transcript and evidence file keeps its bytes.
"""

import contextlib
import io
import json
from pathlib import Path

import pytest

from model_routing import Stats, calibrate_from_results, item_outcomes
from model_routing.cli import main
from model_routing.stats import consensus_labels

ROOT = Path(__file__).resolve().parents[1]
JUDGE = "vendor-c/judge-small"
A, B = "vendor-a/judge-large", "vendor-b/judge-large"
SHA = "0" * 64


def run(argv):
    """`main(argv)` as (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def row(item, prediction, gold, **more):
    return dict({"task": "faithfulness", "model": JUDGE, "item": item, "prediction": prediction,
                 "gold": gold}, **more)


# --- calibration --------------------------------------------------------------------------


def test_a_row_with_label_source_adds_a_trial_of_that_source():
    rows = [row("q1", "pass", "pass", label_source="consensus"),
            row("q2", "fail", "pass", label_source="consensus"),
            row("q3", "pass", "pass")]
    stats = calibrate_from_results(rows)
    assert stats.get("faithfulness", JUDGE) == (2, 3)
    assert stats.label_sources("faithfulness", JUDGE) == {"consensus": 2}


def test_sources_are_counted_apart_and_given_in_source_order():
    rows = [row("q1", "pass", "pass", label_source="human"),
            row("q2", "pass", "pass", label_source="consensus"),
            row("q3", "pass", "pass", label_source="human")]
    sources = calibrate_from_results(rows).label_sources("faithfulness", JUDGE)
    assert sources == {"consensus": 1, "human": 2}
    assert list(sources) == ["consensus", "human"]


def test_a_sliced_row_adds_its_source_under_both_keys():
    stats = calibrate_from_results([row("q1", "pass", "pass", label_source="consensus", slice="long")])
    assert stats.label_sources("faithfulness", JUDGE) == {"consensus": 1}
    assert stats.label_sources("faithfulness@long", JUDGE) == {"consensus": 1}


def test_a_key_with_no_source_gives_an_empty_dict():
    stats = calibrate_from_results([row("q1", "pass", "pass")])
    assert stats.label_sources("faithfulness", JUDGE) == {}
    assert Stats().label_sources("faithfulness", JUDGE) == {}


def test_label_sources_returns_a_new_dict():
    stats = calibrate_from_results([row("q1", "pass", "pass", label_source="consensus")])
    stats.label_sources("faithfulness", JUDGE)["consensus"] = 99
    assert stats.label_sources("faithfulness", JUDGE) == {"consensus": 1}


@pytest.mark.parametrize("prediction, gold", [(1, True), (True, 1), (0, False), (False, 0)])
def test_with_label_source_another_type_is_a_wrong_trial(prediction, gold):
    # review iter-516 should-fix 1: consensus_labels treats `true` and `1` as different grades
    stats = calibrate_from_results([row("q1", prediction, gold, label_source="consensus")])
    assert stats.get("faithfulness", JUDGE) == (0, 1)


@pytest.mark.parametrize("prediction, gold", [(1, True), (True, 1), (0, False), (False, 0)])
def test_without_label_source_equal_values_still_agree(prediction, gold):
    # v1.661's `==`, under which `true` equals `1`, for every file without the key
    stats = calibrate_from_results([row("q1", prediction, gold)])
    assert stats.get("faithfulness", JUDGE) == (1, 1)


@pytest.mark.parametrize("value", [True, 1, "pass", 0, False])
def test_with_label_source_the_same_type_and_value_agree(value):
    stats = calibrate_from_results([row("q1", value, value, label_source="consensus")])
    assert stats.get("faithfulness", JUDGE) == (1, 1)


def test_a_row_with_correct_is_read_as_before():
    rows = [{"task": "faithfulness", "model": JUDGE, "correct": True, "label_source": "consensus"},
            {"task": "faithfulness", "model": JUDGE, "correct": False, "label_source": "consensus"}]
    stats = calibrate_from_results(rows)
    assert stats.get("faithfulness", JUDGE) == (1, 2)
    assert stats.label_sources("faithfulness", JUDGE) == {"consensus": 2}


@pytest.mark.parametrize("value", [None, "", 1, True, ["consensus"], {"consensus": 1}])
def test_a_bad_label_source_raises(value):
    rows = [row("q1", "pass", "pass"), row("q2", "pass", "pass", label_source=value)]
    # review iter-518 nit 2: the message's own words, not the row's repr, name the check
    with pytest.raises(ValueError, match=r"^'label_source' must be a non-empty string, got "):
        calibrate_from_results(rows)


def test_consensus_labels_calibrate_a_candidate_judge_on_agreement():
    """Ten items: A and B agree on q1 to q9 (truth: odd items pass), so 9 labels; the candidate
    gives the label on q1 to q7 and the other grade on q8 and q9, so 7 of 9, every trial
    a consensus one."""
    grades = []
    for i in range(1, 11):
        truth = "pass" if i % 2 else "fail"
        other = "fail" if truth == "pass" else "pass"
        for judge in (A, B):
            grade = other if (i == 10 and judge == B) else truth
            grades += [{"task": "faithfulness", "item": f"q{i}", "judge": judge, "rerun": r, "grade": grade}
                       for r in range(2)]
    labels = consensus_labels(grades, [A, B], reruns=2)["labels"]
    assert len(labels) == 9
    flipped = {"pass": "fail", "fail": "pass"}
    results = [dict(label, model=JUDGE, prediction=label["gold"] if int(label["item"][1:]) <= 7
                    else flipped[label["gold"]]) for label in labels]
    stats = calibrate_from_results(results)
    assert stats.get("faithfulness", JUDGE) == (7, 9)
    assert stats.label_sources("faithfulness", JUDGE) == {"consensus": 9}


# --- item_outcomes --------------------------------------------------------------------------


def test_item_outcomes_reads_correct_by_the_same_rule():
    rows = [row("q1", 1, True, label_source="consensus"), row("q2", 1, True), row("q3", True, True,
                                                                                  label_source="consensus")]
    records = item_outcomes(rows, dataset_sha256=SHA)
    assert [r["correct"] for r in records] == [False, True, True]
    assert list(records[0]) == ["task", "slice", "route", "item", "correct", "dataset_sha256"]


def test_item_outcomes_refuses_a_bad_label_source():
    with pytest.raises(ValueError, match=r"^'label_source' must be a non-empty string, got ''"):
        item_outcomes([row("q1", "pass", "pass", label_source="")], dataset_sha256=SHA)


# --- Stats.add and merge --------------------------------------------------------------------


def test_add_sums_sources_per_key():
    stats = Stats()
    stats.add("t", JUDGE, 3, 4, label_sources={"consensus": 4})
    stats.add("t", JUDGE, 1, 2, label_sources={"consensus": 1, "human": 1})
    stats.add("t", JUDGE, 1, 1)
    assert stats.get("t", JUDGE) == (5, 7)
    assert stats.label_sources("t", JUDGE) == {"consensus": 5, "human": 1}


@pytest.mark.parametrize("value", [{}, {"": 1}, {1: 1}, {"consensus": 0}, {"consensus": -1},
                                   {"consensus": True}, {"consensus": 1.0}, {"consensus": "1"},
                                   {"consensus": 3}, {"consensus": 2, "human": 1}, ["consensus"],
                                   "consensus", 2])
def test_a_bad_label_sources_raises_and_adds_nothing(value):
    stats = Stats()
    with pytest.raises(ValueError, match=r"^label_sources (must be a dict|keys must be|counts must be|counts sum)"):
        stats.add("t", JUDGE, 1, 2, label_sources=value)
    assert stats.get("t", JUDGE) == (0, 0)
    assert stats.label_sources("t", JUDGE) == {}
    assert stats.items() == []


def test_merge_sums_the_sources_of_both_sides():
    left, right = Stats(), Stats()
    left.add("t", JUDGE, 1, 2, label_sources={"consensus": 2})
    right.add("t", JUDGE, 1, 3, label_sources={"consensus": 1, "human": 2})
    right.add("u", JUDGE, 1, 1)
    merged = left.merge(right)
    assert merged.label_sources("t", JUDGE) == {"consensus": 3, "human": 2}
    assert merged.label_sources("u", JUDGE) == {}
    assert left.label_sources("t", JUDGE) == {"consensus": 2}


# --- files --------------------------------------------------------------------------------


def test_save_writes_sources_before_the_times_and_loads_back(tmp_path):
    stats = Stats()
    stats.add("t", JUDGE, 2, 3, input_tokens=30, output_tokens=6, cached_input_tokens=10,
              label_sources={"human": 1, "consensus": 2}, latencies_ms=[5.0, 7.0])
    path = tmp_path / "stats.json"
    stats.save(path)
    saved = json.loads(path.read_text(encoding="utf-8"))["stats"][0]
    assert list(saved) == ["task", "model", "successes", "trials", "input_tokens", "output_tokens",
                           "token_trials", "cached_input_tokens", "cached_trials", "label_sources",
                           "latencies_ms"]
    assert saved["label_sources"] == {"consensus": 2, "human": 1}
    assert list(saved["label_sources"]) == ["consensus", "human"]
    again = tmp_path / "again.json"
    Stats.load(path).save(again)
    assert again.read_bytes() == path.read_bytes()
    assert Stats.load(path).label_sources("t", JUDGE) == {"consensus": 2, "human": 1}


def test_a_stats_without_sources_saves_v1661_bytes(tmp_path):
    stats = Stats()
    stats.add("t", JUDGE, 2, 3, latencies_ms=[5.0])
    path = tmp_path / "stats.json"
    stats.save(path)
    assert path.read_text(encoding="utf-8") == (
        '{\n  "stats": [\n    {\n      "task": "t",\n      "model": "vendor-c/judge-small",\n'
        '      "successes": 2,\n      "trials": 3,\n      "latencies_ms": [\n        5.0\n      ]\n'
        '    }\n  ]\n}\n')
    assert "label_sources" not in path.read_text(encoding="utf-8")


@pytest.mark.parametrize("value", [None, [], {}, {"": 1}, {"consensus": 0}, {"consensus": True},
                                   {"consensus": 1.5}, {"consensus": "1"}, {"consensus": 3},
                                   {"consensus": 1, "human": 2}, "consensus"])
def test_load_refuses_a_bad_label_sources_naming_the_file(tmp_path, value):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps({"stats": [{"task": "t", "model": JUDGE, "successes": 1, "trials": 2,
                                           "label_sources": value}]}), encoding="utf-8")
    with pytest.raises(ValueError) as info:
        Stats.load(path)
    # review iter-518 nit 2: the file, then the check's own words, before the row's repr
    assert str(info.value).startswith(f"{path}: label_sources ")


# --- the calibrate command ------------------------------------------------------------------


def test_calibrate_writes_the_sources_and_prints_the_same_table(tmp_path):
    rows = [row("q1", "pass", "pass"), row("q2", "fail", "pass"), row("q3", "pass", "pass")]
    plain, tagged = tmp_path / "plain.jsonl", tmp_path / "tagged.jsonl"
    plain.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    tagged.write_text("".join(json.dumps(dict(r, label_source="consensus")) + "\n" for r in rows),
                      encoding="utf-8")
    code_p, out_p, err_p = run(["calibrate", "--results", str(plain), "--stats", str(tmp_path / "p.json")])
    code_t, out_t, err_t = run(["calibrate", "--results", str(tagged), "--stats", str(tmp_path / "t.json")])
    assert (code_p, err_p, code_t, err_t) == (0, "", 0, "")
    assert out_t.replace("t.json", "p.json") == out_p
    plain_rows = json.loads((tmp_path / "p.json").read_text(encoding="utf-8"))["stats"]
    tagged_rows = json.loads((tmp_path / "t.json").read_text(encoding="utf-8"))["stats"]
    assert "label_sources" not in plain_rows[0]
    assert tagged_rows == [dict(plain_rows[0], label_sources={"consensus": 3})]


def test_calibrate_with_a_bad_label_source_leaves_the_stats_file(tmp_path):
    results = tmp_path / "results.jsonl"
    results.write_text(json.dumps(row("q1", "pass", "pass", label_source=None)) + "\n", encoding="utf-8")
    stats = tmp_path / "stats.json"
    code, stdout, stderr = run(["calibrate", "--results", str(results), "--stats", str(stats)])
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: 'label_source' must be a non-empty string, got None")
    assert not stats.exists()


# --- docs and the files that keep their bytes ---------------------------------------------


def test_design_and_changelog_state_the_sources():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four3 = design[design.index("### 4.3 "):design.index("### 4.4 ")]
    assert "\n- v1.662 label sources (row JUDGE1bba, the second part of JUDGE1b): " in four3
    assert ("`.add(task, model_id, successes, trials, *, ..., label_sources=None)`: `None`, no source, or a "
            "`dict` of one or more entries") in four3
    assert "a candidate judge's `1` against a consensus label's `true` is a wrong trial (review iter-516 should-fix 1)" in four3
    assert ("  - not in this version: `select` printing a route's label sources and README's sentence on the "
            "`consensus-labels` command (row JUDGE1bbb; both ship in 10 v1.663). ") in four3
    # v1.663 (row JUDGE1bbb) adds where `select` and README ship to DESIGN 10 v1.661's line
    assert "(row JUDGE1bb; from 4.3 v1.662 the stats carry it, and from 10 v1.663 `select` prints it" in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert sum(line.startswith("- v1.662 (2026-11-26): spec, code, docs and tests (4.3, row JUDGE1b, second part). ")
               for line in changelog) == 1


def test_the_production_note_states_the_sources_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    line = [line for line in text.splitlines() if line.startswith("- In this library: judge calls are its first case")]
    assert len(line) == 1
    assert "The changes: stats that say where their labels came from" not in line[0]
    # v1.663 (row JUDGE1bbb) restates what follows; tests/test_select_label_sources.py pins it
    assert (
        "the minimum. From v1.662 stats calibrated on rows that name a label source count each "
        "route's trials per source, so stats built on those labels say so. ") in line[0]


def test_no_transcript_or_script_writes_label_source():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # v1.663 (row JUDGE1bbb): README's production paragraph names the key, and no transcript holds it
    blocks = readme.split("```")[1::2]
    assert blocks and not any("label_source" in block for block in blocks)
    assert readme.count("label_source") == 1
    for folder in ("evidence", "research", ".github"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and path.suffix in (".py", ".yml", ".yaml", ".sh", ".json", ".jsonl", ".md"):
                assert "label_source" not in path.read_text(encoding="utf-8"), path
