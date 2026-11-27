"""DESIGN 4.3 v1.667 (row JUDGE2a, the first part of JUDGE2): self-consistency in stats.

Beside its counts, `Stats` keeps, per `(task, model_id)`, how many items were graded on two or
more reruns (`rerun_items`) and on how many of them every rerun gave the same grade
(`consistent_items`). A `calibrate_from_results` row may carry `rerun`, an int that is not a
bool, at least 0, and then needs `item`; the rerun 0 row is the item's trial, and a row whose
rerun is above 0 is checked as any row is and adds only its grade. A row's grade is its
`prediction` when it has one, else its `correct`, compared by type and value. `.add`,
`.consistency`, `.self_consistency`, `.merge`, `.save` and `.load` carry the counts, and a
`Stats` without them saves v1.666's bytes. No rule of 5.2 reads them yet (row JUDGE2b). The rows
are synthetic, so each count is computed by hand.
"""

import json
from pathlib import Path

import pytest

from model_routing import Registry, Router, Stats, Task, calibrate_from_results, item_outcomes

ROOT = Path(__file__).resolve().parents[1]
JUDGE = "vendor-c/judge-small"
SHA = "0" * 64


def row(item, rerun, prediction, gold="pass", **more):
    return dict({"task": "faithfulness", "model": JUDGE, "item": item, "rerun": rerun,
                 "prediction": prediction, "gold": gold}, **more)


def judge_rows(items=10, inconsistent=1, reruns=3):
    """`items` items graded `reruns` times, each rerun right, but the last rerun of the first
    `inconsistent` items says "fail"."""
    rows = []
    for i in range(items):
        for r in range(reruns):
            grade = "fail" if i < inconsistent and r == reruns - 1 else "pass"
            rows.append(row(f"q{i}", r, grade))
    return rows


# --- calibration --------------------------------------------------------------------------


def test_three_reruns_with_one_item_split_give_nine_of_ten():
    stats = calibrate_from_results(judge_rows())
    assert stats.get("faithfulness", JUDGE) == (10, 10)  # one trial per item, its rerun 0
    assert stats.consistency("faithfulness", JUDGE) == (10, 9)
    assert stats.self_consistency("faithfulness", JUDGE) == 0.9


def test_the_trial_is_the_rerun_0_row_whatever_the_order():
    rows = [row("q1", 2, "pass"), row("q1", 1, "pass"), row("q1", 0, "fail")]
    stats = calibrate_from_results(rows)
    assert stats.get("faithfulness", JUDGE) == (0, 1)
    assert stats.consistency("faithfulness", JUDGE) == (1, 0)


def test_a_later_rerun_adds_no_trial_token_time_or_source():
    rows = [row("q1", 0, "pass", input_tokens=100, output_tokens=10, latency_ms=5.0,
                label_source="consensus", cached_input_tokens=40),
            row("q1", 1, "pass", input_tokens=900, output_tokens=90, latency_ms=50.0,
                label_source="human", cached_input_tokens=400, cache_write_tokens=10)]
    stats = calibrate_from_results(rows)
    assert stats.get("faithfulness", JUDGE) == (1, 1)
    assert stats.tokens("faithfulness", JUDGE) == (100, 10, 1)
    assert stats.cache_tokens("faithfulness", JUDGE) == (40, 1, 0, 0)
    assert stats.latencies("faithfulness", JUDGE) == (5.0,)
    assert stats.label_sources("faithfulness", JUDGE) == {"consensus": 1}
    assert stats.consistency("faithfulness", JUDGE) == (1, 1)


def test_a_later_rerun_is_still_checked_as_any_row():
    rows = [row("q1", 0, "pass"),
            row("q1", 1, "pass", input_tokens=10, output_tokens=1, cached_input_tokens=11)]
    with pytest.raises(ValueError):
        calibrate_from_results(rows)
    with pytest.raises(ValueError, match="label_source"):
        calibrate_from_results([row("q1", 0, "pass"), row("q1", 1, "pass", label_source="")])


def test_an_item_graded_once_adds_nothing_to_consistency():
    stats = calibrate_from_results([row("q1", 0, "pass"), row("q2", 0, "fail")])
    assert stats.get("faithfulness", JUDGE) == (1, 2)
    assert stats.consistency("faithfulness", JUDGE) == (0, 0)
    assert stats.self_consistency("faithfulness", JUDGE) is None


def test_a_sliced_row_counts_under_both_keys():
    rows = [row("q1", 0, "pass", slice="deep"), row("q1", 1, "fail", slice="deep"),
            row("q2", 0, "pass"), row("q2", 1, "pass")]
    stats = calibrate_from_results(rows)
    assert stats.consistency("faithfulness", JUDGE) == (2, 1)
    assert stats.consistency("faithfulness@deep", JUDGE) == (1, 0)


def test_items_are_kept_apart_by_model():
    other = "vendor-d/judge-tiny"
    rows = [row("q1", 0, "pass"), row("q1", 1, "pass"),
            dict(row("q1", 0, "pass"), model=other), dict(row("q1", 1, "fail"), model=other)]
    stats = calibrate_from_results(rows)
    assert stats.consistency("faithfulness", JUDGE) == (1, 1)
    assert stats.consistency("faithfulness", other) == (1, 0)


@pytest.mark.parametrize("first, second", [(True, 1), (1, 1.0), ("1", 1), (0, False)])
def test_grades_of_another_type_disagree(first, second):
    stats = calibrate_from_results([row("q1", 0, first, gold=first), row("q1", 1, second, gold=first)])
    assert stats.consistency("faithfulness", JUDGE) == (1, 0)


def test_without_prediction_the_grade_is_correct():
    base = {"task": "faithfulness", "model": JUDGE, "item": "q1"}
    same = [dict(base, rerun=0, correct=False), dict(base, rerun=1, correct=False)]
    split = [dict(base, rerun=0, correct=True), dict(base, rerun=1, correct=False)]
    assert calibrate_from_results(same).consistency("faithfulness", JUDGE) == (1, 1)
    assert calibrate_from_results(split).consistency("faithfulness", JUDGE) == (1, 0)


def test_with_prediction_the_grade_is_the_prediction_not_correct():
    # two wrong grades that differ are inconsistent, though both reruns are wrong
    rows = [row("q1", 0, "fail", gold="pass"), row("q1", 1, "unsure", gold="pass")]
    stats = calibrate_from_results(rows)
    assert stats.get("faithfulness", JUDGE) == (0, 1)
    assert stats.consistency("faithfulness", JUDGE) == (1, 0)


def test_a_cascade_or_procedure_key_counts_its_reruns():
    cascade, proc = "vendor-a/small>vendor-b/large@low_confidence", "proc:review@1"
    rows = [dict(row("q1", 0, "pass"), model=cascade, escalated=True),
            dict(row("q1", 1, "pass"), model=cascade, escalated=False),
            dict(row("q1", 0, "pass"), model=proc, cost_usd=0.5),
            dict(row("q1", 1, "fail"), model=proc, cost_usd=0.25)]
    stats = calibrate_from_results(rows)
    assert stats.get("faithfulness", cascade) == (1, 1)
    assert stats.escalations("faithfulness", cascade) == 1
    assert stats.consistency("faithfulness", cascade) == (1, 1)
    assert stats.cost("faithfulness", proc) == 0.5
    assert stats.consistency("faithfulness", proc) == (1, 0)
    with pytest.raises(ValueError, match="escalated"):  # a later rerun is checked as any row
        calibrate_from_results([rows[0], dict(row("q1", 1, "pass"), model=cascade)])


def test_reruns_with_a_gap_are_counted():
    stats = calibrate_from_results([row("q1", 0, "pass"), row("q1", 2, "pass")])
    assert stats.consistency("faithfulness", JUDGE) == (1, 1)


@pytest.mark.parametrize("rerun", [True, False, -1, 1.0, "0", None, [0]])
def test_a_bad_rerun_raises(rerun):
    # review iter-524 should-fix 1: the row check's own message, with a rerun 0 row beside it, so
    # the item's missing rerun 0 cannot stand in for it
    with pytest.raises(ValueError, match=r"^'rerun' must be an integer >= 0, got "):
        calibrate_from_results([row("q1", 0, "pass"), row("q1", rerun, "pass")])


@pytest.mark.parametrize("item", [None, "", 1, ["q1"]])
def test_a_rerun_row_without_a_string_item_raises(item):
    bad = row("q1", 0, "pass")
    bad["item"] = item
    with pytest.raises(ValueError, match=r"^a row with 'rerun' needs a non-empty string 'item': "):
        calibrate_from_results([bad])
    del bad["item"]
    with pytest.raises(ValueError, match=r"^a row with 'rerun' needs a non-empty string 'item': "):
        calibrate_from_results([bad])


def test_a_rerun_given_twice_raises():
    with pytest.raises(ValueError, match="rerun 1 is given twice"):
        calibrate_from_results([row("q1", 0, "pass"), row("q1", 1, "pass"), row("q1", 1, "pass")])


def test_an_item_without_rerun_0_raises():
    with pytest.raises(ValueError, match="no rerun 0"):
        calibrate_from_results([row("q1", 1, "pass"), row("q1", 2, "pass")])


def test_rerun_rows_that_mix_prediction_and_none_raise():
    no_prediction = {"task": "faithfulness", "model": JUDGE, "item": "q1", "rerun": 1, "correct": True}
    with pytest.raises(ValueError, match="some rerun rows carry 'prediction' and some do not"):
        calibrate_from_results([row("q1", 0, "pass"), no_prediction])


def test_a_plain_row_naming_a_rerun_item_raises():
    plain = {"task": "faithfulness", "model": JUDGE, "item": "q1", "correct": True}
    with pytest.raises(ValueError, match="second trial"):
        calibrate_from_results([row("q1", 0, "pass"), row("q1", 1, "pass"), plain])
    with pytest.raises(ValueError, match="second trial"):
        calibrate_from_results([plain, row("q1", 0, "pass")])
    # another item, or another model's item, is no clash
    other = dict(plain, item="q2")
    assert calibrate_from_results([row("q1", 0, "pass"), other]).get("faithfulness", JUDGE) == (2, 2)
    another = dict(plain, model="vendor-d/judge-tiny")
    assert calibrate_from_results([row("q1", 0, "pass"), another]).get("faithfulness", JUDGE) == (1, 1)


def test_rows_without_rerun_are_read_as_before():
    rows = [{"task": "faithfulness", "model": JUDGE, "item": "q1", "correct": True},
            {"task": "faithfulness", "model": JUDGE, "item": "q1", "correct": False}]
    stats = calibrate_from_results(rows)
    assert stats.get("faithfulness", JUDGE) == (1, 2)
    assert stats.consistency("faithfulness", JUDGE) == (0, 0)


def test_item_outcomes_still_gives_one_record_per_row():
    records = item_outcomes([row("q1", 0, "pass"), row("q1", 1, "fail")], dataset_sha256=SHA)
    assert [r["correct"] for r in records] == [True, False]
    with pytest.raises(ValueError, match="no rerun 0"):
        item_outcomes([row("q1", 1, "pass")], dataset_sha256=SHA)


# --- Stats ---------------------------------------------------------------------------------


def test_add_sums_the_counts_per_key():
    stats = Stats()
    stats.add("t", JUDGE, 3, 4, rerun_items=2, consistent_items=1)
    stats.add("t", JUDGE, 1, 1, rerun_items=3, consistent_items=3)
    assert stats.consistency("t", JUDGE) == (5, 4)
    assert stats.self_consistency("t", JUDGE) == 0.8
    with pytest.raises(ValueError, match="rerun_items"):  # 6 rerun items on the key's 5 trials
        stats.add("t", JUDGE, 0, 0, rerun_items=1, consistent_items=0)
    stats.add("t", JUDGE, 0, 1, rerun_items=1, consistent_items=0)
    assert stats.consistency("t", JUDGE) == (6, 4)


@pytest.mark.parametrize("pair", [(1, None), (None, 0), (0, 0), (True, 1), (1, True), (2, 3), (1, -1),
                                  (1.0, 1), (1, 1.0), ("1", 1), (7, 0)])
def test_bad_counts_raise_and_add_nothing(pair):
    stats = Stats()
    stats.add("t", JUDGE, 4, 5)
    rerun_items, consistent_items = pair
    with pytest.raises(ValueError, match="rerun_items|consistent_items"):
        stats.add("t", JUDGE, 1, 1, rerun_items=rerun_items, consistent_items=consistent_items)
    assert stats.get("t", JUDGE) == (4, 5)
    assert stats.consistency("t", JUDGE) == (0, 0)


def test_merge_sums_both_sides():
    a, b = Stats(), Stats()
    a.add("t", JUDGE, 3, 3, rerun_items=3, consistent_items=2)
    b.add("t", JUDGE, 2, 2, rerun_items=2, consistent_items=2)
    b.add("u", JUDGE, 1, 1)
    merged = a.merge(b)
    assert merged.consistency("t", JUDGE) == (5, 4)
    assert merged.consistency("u", JUDGE) == (0, 0)
    assert a.consistency("t", JUDGE) == (3, 2)


def test_save_writes_the_counts_after_sources_and_before_times_and_loads_back(tmp_path):
    stats = Stats()
    stats.add("t", JUDGE, 2, 3, latencies_ms=[5.0], label_sources={"consensus": 3},
              rerun_items=3, consistent_items=2)
    path = tmp_path / "stats.json"
    stats.save(path)
    [saved] = json.loads(path.read_text(encoding="utf-8"))["stats"]
    assert list(saved) == ["task", "model", "successes", "trials", "label_sources", "rerun_items",
                           "consistent_items", "latencies_ms"]
    assert (saved["rerun_items"], saved["consistent_items"]) == (3, 2)
    loaded = Stats.load(path)
    assert loaded.consistency("t", JUDGE) == (3, 2)
    assert loaded.label_sources("t", JUDGE) == {"consensus": 3}


def test_a_stats_without_the_counts_saves_v1666_bytes(tmp_path):
    stats = Stats()
    stats.add("t", JUDGE, 2, 3, latencies_ms=[5.0])
    path = tmp_path / "stats.json"
    stats.save(path)
    assert path.read_text(encoding="utf-8") == (
        '{\n  "stats": [\n    {\n      "task": "t",\n      "model": "vendor-c/judge-small",\n'
        '      "successes": 2,\n      "trials": 3,\n      "latencies_ms": [\n        5.0\n      ]\n'
        '    }\n  ]\n}\n')


@pytest.mark.parametrize("more", [{"rerun_items": 1}, {"consistent_items": 0},
                                  {"rerun_items": None, "consistent_items": None},
                                  {"rerun_items": 1, "consistent_items": None},
                                  {"rerun_items": True, "consistent_items": 1},
                                  {"rerun_items": "1", "consistent_items": 1},
                                  {"rerun_items": 4, "consistent_items": 1},
                                  {"rerun_items": 2, "consistent_items": 3},
                                  {"rerun_items": 0, "consistent_items": 0}])
def test_load_refuses_bad_counts_naming_the_file(tmp_path, more):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps({"stats": [dict({"task": "t", "model": JUDGE, "successes": 2,
                                                "trials": 3}, **more)]}), encoding="utf-8")
    with pytest.raises(ValueError, match="stats.json"):
        Stats.load(path)


def test_no_rule_reads_the_counts_yet():
    registry = Registry.load(ROOT / "model_routing" / "data" / "models.json")
    task = Task(name="faithfulness", bar=0.5, min_samples=10)
    models = [m.id for m in registry.models][:3]
    plain, counted = Stats(), Stats()
    for i, model_id in enumerate(models):
        plain.add("faithfulness", model_id, 18 + i, 20)
        counted.add("faithfulness", model_id, 18 + i, 20, rerun_items=20, consistent_items=i)
    tasks = {"faithfulness": task}
    for flavor in ("cost_effective", "cost_blind"):
        before = Router(registry, tasks, plain).select("faithfulness", flavor).to_dict()
        after = Router(registry, tasks, counted).select("faithfulness", flavor).to_dict()
        assert before == after


# --- spec and scripts ----------------------------------------------------------------------


def test_design_and_changelog_state_v1_667():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four3 = design[design.index("### 4.3 "):design.index("### 4.4 ")]
    assert four3.count("\n- v1.667 self-consistency (row JUDGE2a, the first part of JUDGE2): ") == 1
    assert four3.index("\n- v1.662 label sources") < four3.index("\n- v1.667 self-consistency")
    for words in ("`.add(task, model_id, successes, trials, *, ..., rerun_items=None, consistent_items=None)`",
                  "The rerun 0 row is the item's trial", "since a rerun is not an independent trial",
                  "after any `label_sources` and before `latencies_ms`", "saves v1.666's bytes",
                  "as `inconsistent` whatever its bound (row JUDGE2b)", "(row JUDGE2c, which v1.675 adds)",
                  "self-consistency says a judge repeats its own grades, not that they are right"):
        assert four3.count(words) == 1, words
    [line] = [x for x in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
              if x.startswith("- v1.667 (")]
    assert line.startswith("- v1.667 (2026-11-26): spec, code and tests (4.3, row JUDGE2, first part). ")
    assert len(line.encode("utf-8")) <= 600


def test_no_transcript_or_script_writes_rerun_into_a_results_row():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    blocks = readme.split("```")[1::2]
    assert blocks and not any('"rerun"' in block for block in blocks)
    for folder in ("evidence", "research", ".github", "examples"):
        if not (ROOT / folder).is_dir():
            continue
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and path.suffix in (".py", ".yml", ".yaml", ".sh", ".json", ".jsonl"):
                text = path.read_text(encoding="utf-8")
                assert '"rerun"' not in text and "'rerun'" not in text, path


def test_the_production_note_states_the_counts():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    [line] = [x for x in text.splitlines() if x.startswith("- In this library: judge calls are its first case")]
    # v1.668 (row JUDGE2b) states the gate as shipped, pinned in tests/test_self_consistency_gate.py
    assert ("From v1.663 `select` prints where the chosen route's labels came from. From v1.667, "
            "calibrated on rows that number each grade's rerun, stats count the items each judge "
            "graded on two or more reruns and those every rerun graded alike, its "
            "self-consistency.") in line
