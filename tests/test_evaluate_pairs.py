"""v1.677 (DESIGN 12.1 and 12.3, row DEL1d, the last part of row DEL1): the evaluator's root and
leaf sensitivity table.

With ``pairs=(roots, leaves)`` ``evaluate`` gains a last key, ``pair_sensitivity``: per task, the
spread in success over roots with the leaf held and over leaves with the root held, over all of
the task's items. Every expected number below is worked by hand from CORRECT: a pair's success is
its correct count over the task's 40 items; a leaf's root spread is its highest correct count over
its roots less its lowest, over 40; a mean is the sum of those differences over 40 times the
number of sides with a spread.
"""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]

ROOTS = ("r/a", "r/b", "r/c", "r/d")
LEAVES = ("l/x", "l/y", "l/z")
ITEMS = 40
# correct items out of 40 for each pair, root-major; item k of a task is correct when k < count
CORRECT = {
    # the DEL1 fixture: the root moves success far more than the leaf does
    "diligence": {
        ("r/a", "l/x"): 20, ("r/a", "l/y"): 21, ("r/a", "l/z"): 22,
        ("r/b", "l/x"): 28, ("r/b", "l/y"): 29, ("r/b", "l/z"): 30,
        ("r/c", "l/x"): 32, ("r/c", "l/y"): 33, ("r/c", "l/z"): 34,
        ("r/d", "l/x"): 36, ("r/d", "l/y"): 37, ("r/d", "l/z"): 39,
    },
    # the reverse: the leaf moves success, the root barely does
    "triage": {
        ("r/a", "l/x"): 10, ("r/a", "l/y"): 20, ("r/a", "l/z"): 30,
        ("r/b", "l/x"): 11, ("r/b", "l/y"): 21, ("r/b", "l/z"): 31,
        ("r/c", "l/x"): 12, ("r/c", "l/y"): 22, ("r/c", "l/z"): 32,
        ("r/d", "l/x"): 13, ("r/d", "l/y"): 23, ("r/d", "l/z"): 33,
    },
}
SOLO = 30  # a single model of the matrix, never a pair
COST = {"r/a": 0.001, "r/b": 0.002, "r/c": 0.003, "r/d": 0.004,
        "l/x": 0.001, "l/y": 0.003, "l/z": 0.006}
RUN = {"bars": [0.6, 0.8], "seeds": range(3), "min_samples": 5}

DILIGENCE = {
    "task": "diligence",
    "items": 40,
    "roots": ["r/a", "r/b", "r/c", "r/d"],
    "leaves": ["l/x", "l/y", "l/z"],
    "success": {"r/a+l/x": 20 / 40, "r/a+l/y": 21 / 40, "r/a+l/z": 22 / 40,
                "r/b+l/x": 28 / 40, "r/b+l/y": 29 / 40, "r/b+l/z": 30 / 40,
                "r/c+l/x": 32 / 40, "r/c+l/y": 33 / 40, "r/c+l/z": 34 / 40,
                "r/d+l/x": 36 / 40, "r/d+l/y": 37 / 40, "r/d+l/z": 39 / 40},
    # l/x: 36 - 20 = 16; l/y: 37 - 21 = 16; l/z: 39 - 22 = 17
    "root_spread": {"l/x": 16 / 40, "l/y": 16 / 40, "l/z": 17 / 40},
    # r/a: 22 - 20 = 2; r/b: 30 - 28 = 2; r/c: 34 - 32 = 2; r/d: 39 - 36 = 3
    "leaf_spread": {"r/a": 2 / 40, "r/b": 2 / 40, "r/c": 2 / 40, "r/d": 3 / 40},
    "mean_root_spread": (16 + 16 + 17) / (40 * 3),
    "mean_leaf_spread": (2 + 2 + 2 + 3) / (40 * 4),
}
TRIAGE = {
    "task": "triage",
    "items": 40,
    "roots": ["r/a", "r/b", "r/c", "r/d"],
    "leaves": ["l/x", "l/y", "l/z"],
    "success": {"r/a+l/x": 10 / 40, "r/a+l/y": 20 / 40, "r/a+l/z": 30 / 40,
                "r/b+l/x": 11 / 40, "r/b+l/y": 21 / 40, "r/b+l/z": 31 / 40,
                "r/c+l/x": 12 / 40, "r/c+l/y": 22 / 40, "r/c+l/z": 32 / 40,
                "r/d+l/x": 13 / 40, "r/d+l/y": 23 / 40, "r/d+l/z": 33 / 40},
    # each leaf: 13 - 10 = 23 - 20 = 33 - 30 = 3
    "root_spread": {"l/x": 3 / 40, "l/y": 3 / 40, "l/z": 3 / 40},
    # each root: 30 - 10 = 31 - 11 = 32 - 12 = 33 - 13 = 20
    "leaf_spread": {"r/a": 20 / 40, "r/b": 20 / 40, "r/c": 20 / 40, "r/d": 20 / 40},
    "mean_root_spread": (3 + 3 + 3) / (40 * 3),
    "mean_leaf_spread": (20 + 20 + 20 + 20) / (40 * 4),
}
ROW_KEYS = ["task", "items", "roots", "leaves", "success", "root_spread", "leaf_spread",
            "mean_root_spread", "mean_leaf_spread"]
# sha256 of json.dumps(evaluate(_outcomes(), **RUN), sort_keys=True), taken on e8dd6ac (v1.676)
DIGEST = "bfba1fe745794866f7d39f57652d2cb00da35b39e820dd0008e791b0af274bdf"


def _rows(correct=None, solo=True, part=False):
    rows = []
    for task, pairs in (CORRECT if correct is None else correct).items():
        for k in range(ITEMS):
            item = f"{task[0]}{k:02d}"
            extra = {"part": "early" if k % 2 else "late"} if part else {}
            for (root, leaf), count in pairs.items():
                rows.append({"task": task, "item": item, "model": f"{root}+{leaf}",
                             "correct": k < count, "cost_usd": COST[root] + COST[leaf], **extra})
            if solo:
                rows.append({"task": task, "item": item, "model": "s/solo", "correct": k < SOLO,
                             "cost_usd": 0.002, **extra})
    return rows


def _outcomes(**kwargs):
    return outcomes_from_rows(_rows(**kwargs))


def test_the_sensitivity_table_is_the_hand_computed_one():
    result = evaluate(_outcomes(), **RUN, pairs=(ROOTS, LEAVES))
    assert list(result)[-1] == "pair_sensitivity"
    assert result["pair_sensitivity"] == [DILIGENCE, TRIAGE]
    for row in result["pair_sensitivity"]:
        assert list(row) == ROW_KEYS
        assert list(row["success"]) == [f"{r}+{l}" for r in ROOTS for l in LEAVES]
        assert list(row["root_spread"]) == list(LEAVES)
        assert list(row["leaf_spread"]) == list(ROOTS)
        assert type(row["items"]) is int
        for value in (*row["success"].values(), *row["root_spread"].values(),
                      *row["leaf_spread"].values(), row["mean_root_spread"],
                      row["mean_leaf_spread"]):
            assert type(value) is float


def test_the_root_spread_is_larger_on_the_del1_fixture_and_smaller_on_its_reverse():
    diligence, triage = evaluate(_outcomes(), **RUN, pairs=(ROOTS, LEAVES))["pair_sensitivity"]
    assert diligence["mean_root_spread"] > diligence["mean_leaf_spread"]
    assert min(diligence["root_spread"].values()) > max(diligence["leaf_spread"].values())
    assert triage["mean_root_spread"] < triage["mean_leaf_spread"]


def test_roots_leaves_and_pairs_keep_the_order_given():
    roots, leaves = ROOTS[::-1], list(LEAVES[::-1])
    row = evaluate(_outcomes(), **RUN, pairs=[list(roots), leaves])["pair_sensitivity"][0]
    assert row["roots"] == list(roots) and row["leaves"] == leaves
    assert list(row["success"]) == [f"{r}+{l}" for r in roots for l in leaves]
    assert list(row["root_spread"]) == leaves and list(row["leaf_spread"]) == list(roots)
    assert row["success"] == DILIGENCE["success"]
    assert row["root_spread"] == DILIGENCE["root_spread"]
    assert row["leaf_spread"] == DILIGENCE["leaf_spread"]
    assert row["mean_root_spread"] == DILIGENCE["mean_root_spread"]


def test_a_partial_grid_leaves_out_absent_pairs_and_a_side_with_one_pair_has_no_spread():
    correct = {"diligence": {("r/a", "l/x"): 20, ("r/a", "l/y"): 21, ("r/b", "l/x"): 28}}
    result = evaluate(_outcomes(correct=correct), **RUN,
                      pairs=(("r/a", "r/b", "r/e"), ("l/x", "l/y", "l/w")))
    assert result["pair_sensitivity"] == [{
        "task": "diligence",
        "items": 40,
        "roots": ["r/a", "r/b"],
        "leaves": ["l/x", "l/y"],
        "success": {"r/a+l/x": 20 / 40, "r/a+l/y": 21 / 40, "r/b+l/x": 28 / 40},
        "root_spread": {"l/x": (28 - 20) / 40, "l/y": None},
        "leaf_spread": {"r/a": (21 - 20) / 40, "r/b": None},
        "mean_root_spread": 8 / (40 * 1),
        "mean_leaf_spread": 1 / (40 * 1),
    }]


def test_one_pair_has_no_spread_and_no_mean():
    row = evaluate(_outcomes(), **RUN, pairs=(["r/a"], ["l/x"]))["pair_sensitivity"][1]
    assert row == {"task": "triage", "items": 40, "roots": ["r/a"], "leaves": ["l/x"],
                   "success": {"r/a+l/x": 10 / 40}, "root_spread": {"l/x": None},
                   "leaf_spread": {"r/a": None}, "mean_root_spread": None,
                   "mean_leaf_spread": None}


def test_the_table_reads_no_seed_bar_flavor_or_row_order():
    pairs = (ROOTS, LEAVES)
    first = evaluate(_outcomes(), [0.6], seeds=[0], flavors=["cost_blind"], min_samples=5,
                     pairs=pairs)
    second = evaluate(outcomes_from_rows(_rows()[::-1]), [0.9, 0.7], seeds=range(4),
                      calibration_fraction=0.3, pairs=pairs)
    assert json.dumps(first["pair_sensitivity"]) == json.dumps(second["pair_sensitivity"])
    assert first["pair_sensitivity"] == [DILIGENCE, TRIAGE]


@pytest.mark.parametrize("options", [{}, {"cost_per_correct": True}])
def test_every_other_key_is_the_run_without_pairs(options):
    without = evaluate(_outcomes(), **RUN, **options)
    with_pairs = evaluate(_outcomes(), **RUN, **options, pairs=(ROOTS, LEAVES))
    assert list(with_pairs) == list(without) + ["pair_sensitivity"]
    for key in without:
        assert with_pairs[key] == without[key]


def test_a_sliced_run_keeps_its_slice_keys_and_the_table_comes_last():
    outcomes = outcomes_from_rows(_rows(part=True), slice_by="part")
    without = evaluate(outcomes, **RUN)
    with_pairs = evaluate(outcomes, **RUN, pairs=(ROOTS, LEAVES))
    assert list(without)[-2:] == ["per_slice", "slice_summary"]
    assert list(with_pairs) == list(without) + ["pair_sensitivity"]
    assert all(with_pairs[key] == without[key] for key in without)
    assert with_pairs["pair_sensitivity"] == [DILIGENCE, TRIAGE]


def test_without_pairs_the_dict_keeps_its_v1_676_bytes():
    result = evaluate(_outcomes(), **RUN)
    assert "pair_sensitivity" not in result
    digest = hashlib.sha256(json.dumps(result, sort_keys=True).encode("utf-8")).hexdigest()
    assert digest == DIGEST
    assert evaluate(_outcomes(), **RUN, pairs=None) == result


@pytest.mark.parametrize("pairs", [
    True, "r/a+l/x", ["r/a"], (ROOTS,), (ROOTS, LEAVES, LEAVES), {"r/a": "l/x"},
    ((), LEAVES), (ROOTS, []), ("r/a", LEAVES), (ROOTS, "l/x"), (set(ROOTS), LEAVES),
    (("r/a", "r/a"), LEAVES), (ROOTS, ("l/x", "l/y", "l/x")), (("r/a", 1), LEAVES),
    (ROOTS, (None,)),
])
def test_a_malformed_pairs_is_a_value_error(pairs):
    with pytest.raises(ValueError, match=r"^pairs"):
        evaluate(_outcomes(), **RUN, pairs=pairs)


def test_two_pairs_with_one_id_are_a_value_error():
    with pytest.raises(ValueError, match=r"^pairs: .*'a\+b\+c'"):
        evaluate(_outcomes(), **RUN, pairs=(("a", "a+b"), ("b+c", "c")))


def test_pairs_naming_no_model_of_the_matrix_is_a_value_error():
    with pytest.raises(ValueError, match=r"^pairs: no pair .* is a model of the outcomes"):
        evaluate(_outcomes(), **RUN, pairs=(("r/q",), ("l/q",)))


def test_the_checks_come_in_the_order_the_spec_gives():
    with pytest.raises(ValueError, match=r"^cost_per_correct must be True or False"):
        evaluate(_outcomes(), **RUN, cost_per_correct="yes", pairs="bad")
    incomplete = _outcomes()[1:]
    with pytest.raises(ValueError, match=r"^pairs"):
        evaluate(incomplete, **RUN, pairs="bad")
    with pytest.raises(ValueError, match=r"^incomplete matrix"):
        evaluate(incomplete, **RUN, pairs=(("r/q",), ("l/q",)))


def _subsection(design, heading):
    return design.split(f"\n### {heading} ", 1)[1].split("\n### ", 1)[0]


def test_design_and_changelog_state_v1_677():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    lead = "- v1.677 pairs (row DEL1d, the last part of row DEL1): "
    assert design.count(lead) == 1 and lead in _subsection(design, "12.1")
    assert ("- v1.677 pairs (row DEL1d): a last keyword, `pairs=None`, adds a last key, "
            "`pair_sensitivity`, as 12.1 v1.677 says\n") in _subsection(design, "12.3")
    assert design.count("(row DEL1d, which v1.677 adds in 12.1)") == 3
    # the Status line names the row as each version does; below it no clause says DEL1d is to come
    assert "(row DEL1d);" not in design.split("\n", 3)[3]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.677 (2026-11-26): spec, code and tests (12.1, 12.3, row DEL1d, "
                           "the last part of row DEL1). ") == 1


def test_the_note_s_orchestrator_line_states_the_table_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    lesson = text.split("### The orchestrator gets the strong model; the readers can be cheap\n", 1)[1]
    line = next(l for l in lesson.split("\n") if l.startswith("- In this library:"))
    assert "is planned" not in line
    assert line.endswith("; and from v1.677 `evaluate(..., pairs=(roots, leaves))` gives each "
                         "task's spread in success over roots with the leaf held and over leaves "
                         "with the root held, the two gaps the result above reports.")
