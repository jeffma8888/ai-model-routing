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

import json
from pathlib import Path

import pytest

from decision_hash import decision_sha256
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
# sha256 of json.dumps(evaluate(_outcomes(), **RUN), sort_keys=True), taken on e8dd6ac (v1.676);
# the dict holds no Wilson bound, so decision_sha256 (tests/decision_hash.py) gives the same digest
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
    assert decision_sha256(result, sort_keys=True) == DIGEST
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


@pytest.mark.parametrize("pairs, label", [
    ((("r/a", "r/b>r/c"), LEAVES), "roots 'r/b>r/c'"),
    ((ROOTS, ("l/x>l/y",)), "leaves 'l/x>l/y'"),
])
def test_a_side_holding_a_cascade_mark_is_a_value_error(pairs, label):
    # review iter-535 should-fix 1: a model holding `>` is a cascade (12.1 v1.538), never a side
    with pytest.raises(ValueError, match=rf"^pairs: {label} holds '>'"):
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


# v1.679 (DESIGN 12.4, row DEL1f): the pair table in `model-routing evaluate`. Every table below
# is written by hand from the dicts above, in the rates' format: 16/40 is 0.400, 17/40 0.425,
# (16 + 16 + 17)/120 0.408, 2/40 0.050, 3/40 0.075, (2 + 2 + 2 + 3)/160 0.056; on triage 3/40,
# 9/120 0.075, 20/40 and 80/160 0.500.

PAIR_TEXT = """\
pairs, diligence
varies  held  spread
------  ----  ------
root    l/x   0.400
root    l/y   0.400
root    l/z   0.425
root    mean  0.408
leaf    r/a   0.050
leaf    r/b   0.050
leaf    r/c   0.050
leaf    r/d   0.075
leaf    mean  0.056

pairs, triage
varies  held  spread
------  ----  ------
root    l/x   0.075
root    l/y   0.075
root    l/z   0.075
root    mean  0.075
leaf    r/a   0.500
leaf    r/b   0.500
leaf    r/c   0.500
leaf    r/d   0.500
leaf    mean  0.500
"""
PAIR_OPTIONS = ["--root", *ROOTS, "--leaf", *LEAVES]
# sha256 of the command's stdout without --root and --leaf, taken on 2e0ab44 (v1.678)
CLI_DIGESTS = {
    "text": "28dae78c9ea2452d4985739418f7c346d273ef89ae24ab64343c427926dd0a58",
    "json": "f75530a46396c7c4b55d071b98c7dfcb79323bb1d4b1f49c0cc8fa8f033b4c6f",
    "slices-text": "3cb217f7493c6c6672b59b416321d761475b000c5001104598d89edd7eead597",
    "slices-json": "6c1612dd5251b465f419c92c3dab4c9117127f9afde5bd5794e51ed911ee0817",
}
USAGE_ERRORS = {
    "--root": "error: --root needs --leaf: the pair table reads each root with each leaf",
    "--leaf": "error: --leaf needs --root: the pair table reads each root with each leaf",
}


def _cli(capsys, tmp_path, *extra, rows=None, outcomes=None):
    from datetime import date

    from model_routing.cli import main
    if outcomes is None:
        outcomes = tmp_path / "m.jsonl"
        outcomes.write_text("".join(json.dumps(r) + "\n" for r in (_rows() if rows is None else rows)),
                            encoding="utf-8")
    code = main(["evaluate", "--outcomes", str(outcomes), "--bar", "0.6", "0.8", "--seeds", "3",
                 "--min-samples", "5", *extra], today=date(2026, 11, 26))
    out = capsys.readouterr()
    return code, out.out, out.err


@pytest.mark.parametrize("name, part, extra", [
    ("text", False, ()), ("json", False, ("--json",)),
    ("slices-text", True, ("--slice-by", "part")), ("slices-json", True, ("--slice-by", "part", "--json")),
])
def test_cli_without_the_options_keeps_its_v1_678_bytes(capsys, tmp_path, name, part, extra):
    import hashlib
    code, out, err = _cli(capsys, tmp_path, *extra, rows=_rows(part=part))
    assert (code, err) == (0, "")
    assert hashlib.sha256(out.encode("utf-8")).hexdigest() == CLI_DIGESTS[name]


def test_cli_text_gains_a_pair_table_per_task_after_the_strategy_tables(capsys, tmp_path):
    _, without, _ = _cli(capsys, tmp_path)
    code, out, err = _cli(capsys, tmp_path, *PAIR_OPTIONS)
    assert (code, err) == (0, "")
    assert out == without[:-1] + "\n\n" + PAIR_TEXT


def test_cli_text_puts_the_pair_tables_after_the_last_slices_table(capsys, tmp_path):
    rows = _rows(part=True)
    _, without, _ = _cli(capsys, tmp_path, "--slice-by", "part", rows=rows)
    assert without.rstrip("\n").split("\n\n")[-1].startswith("bar 0.8, cost_blind, slices\n")
    code, out, err = _cli(capsys, tmp_path, "--slice-by", "part", *PAIR_OPTIONS, rows=rows)
    assert (code, err) == (0, "")
    assert out == without[:-1] + "\n\n" + PAIR_TEXT


def test_cli_text_with_cost_per_correct_keeps_its_tables(capsys, tmp_path):
    _, without, _ = _cli(capsys, tmp_path, "--cost-per-correct")
    code, out, _ = _cli(capsys, tmp_path, "--cost-per-correct", *PAIR_OPTIONS)
    assert code == 0 and out == without[:-1] + "\n\n" + PAIR_TEXT


def test_cli_json_keeps_pair_sensitivity_last(capsys, tmp_path):
    _, without, _ = _cli(capsys, tmp_path, "--json")
    code, out, err = _cli(capsys, tmp_path, "--json", *PAIR_OPTIONS)
    assert (code, err) == (0, "")
    plain, result = json.loads(without), json.loads(out)
    assert list(result) == list(plain) + ["pair_sensitivity"]
    assert all(result[key] == plain[key] for key in plain)
    assert result["pair_sensitivity"] == [DILIGENCE, TRIAGE]


def test_cli_options_may_be_repeated_and_keep_the_order_given(capsys, tmp_path):
    code, out, _ = _cli(capsys, tmp_path, "--json", "--root", "r/d", "r/c", "--leaf", "l/z",
                        "--root", "r/b", "r/a", "--leaf", "l/y", "l/x")
    assert code == 0
    row = json.loads(out)["pair_sensitivity"][0]
    assert row["roots"] == ["r/d", "r/c", "r/b", "r/a"] and row["leaves"] == ["l/z", "l/y", "l/x"]
    assert list(row["success"])[:2] == ["r/d+l/z", "r/d+l/y"]
    code, out, _ = _cli(capsys, tmp_path, "--root", "r/d", "r/c", "r/b", "r/a",
                        "--leaf", "l/z", "l/y", "l/x")
    table = out.split("\n\npairs, diligence\n", 1)[1].split("\n\n", 1)[0].splitlines()
    assert [line.split()[:2] for line in table[2:]] == [
        ["root", "l/z"], ["root", "l/y"], ["root", "l/x"], ["root", "mean"],
        ["leaf", "r/d"], ["leaf", "r/c"], ["leaf", "r/b"], ["leaf", "r/a"], ["leaf", "mean"]]


def test_cli_text_prints_a_dash_for_none(capsys, tmp_path):
    correct = {"diligence": {("r/a", "l/x"): 20, ("r/a", "l/y"): 21, ("r/b", "l/x"): 28}}
    rows = _rows(correct=correct)
    code, out, _ = _cli(capsys, tmp_path, "--root", "r/a", "r/b", "r/e",
                        "--leaf", "l/x", "l/y", "l/w", rows=rows)
    assert code == 0
    # l/x: (28 - 20)/40 = 0.200, l/y one root; r/a: (21 - 20)/40 = 0.025, r/b one leaf
    assert out.endswith("\n\npairs, diligence\n"
                        "varies  held  spread\n"
                        "------  ----  ------\n"
                        "root    l/x   0.200\n"
                        "root    l/y   -\n"
                        "root    mean  0.200\n"
                        "leaf    r/a   0.025\n"
                        "leaf    r/b   -\n"
                        "leaf    mean  0.025\n")
    code, out, _ = _cli(capsys, tmp_path, "--root", "r/a", "--leaf", "l/x")
    one = ("varies  held  spread\n------  ----  ------\nroot    l/x   -\nroot    mean  -\n"
           "leaf    r/a   -\nleaf    mean  -\n")
    assert code == 0 and out.endswith(f"\n\npairs, diligence\n{one}\npairs, triage\n{one}")


@pytest.mark.parametrize("given", ["--root", "--leaf"])
def test_one_option_without_the_other_is_a_usage_error_before_any_file_is_read(capsys, tmp_path,
                                                                                given):
    code, out, err = _cli(capsys, tmp_path, given, "r/a", outcomes=tmp_path / "missing.jsonl")
    lines = err.splitlines()
    assert (code, out) == (2, "")
    assert lines[0].startswith("usage: model-routing evaluate ")
    assert lines[-1] == USAGE_ERRORS[given]
    assert "missing.jsonl" not in err


@pytest.mark.parametrize("options, message", [
    (["--root", "r/q", "--leaf", "l/q"],
     "error: pairs: no pair of the roots and leaves given is a model of the outcomes"),
    (["--root", "r/a", "r/a", "--leaf", "l/x"],
     "error: pairs: roots must be a non-empty list or tuple of model IDs with no ID twice, "
     "got ['r/a', 'r/a']"),
    (["--root", "r/a>r/b", "--leaf", "l/x"],
     "error: pairs: roots 'r/a>r/b' holds '>', which names a cascade (12.1 v1.538), never one "
     "side of a pair"),
])
def test_a_bad_pairs_is_one_error_line_and_exit_2(capsys, tmp_path, options, message):
    code, out, err = _cli(capsys, tmp_path, *options)
    assert (code, out, err) == (2, "", message + "\n")


def test_design_and_changelog_state_v1_679():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    cli_spec = _subsection(design, "12.4")
    assert cli_spec.count("- v1.679 `--root MODEL [MODEL ...]` and `--leaf MODEL [MODEL ...]` "
                          "(row DEL1f): ") == 1
    assert "[--root MODEL [MODEL ...] --leaf MODEL [MODEL ...]] [--json]`" in cli_spec
    for message in USAGE_ERRORS.values():
        assert f"`{message}`" in cli_spec
    assert ("the table in `model-routing evaluate` (row DEL1f, which v1.679 adds in 12.4); "
            in _subsection(design, "12.1"))
    assert "(row DEL1f);" not in design.split("\n", 3)[3]
    assert _subsection(design, "12.5").count("- v1.679: `tests/test_evaluate_pairs.py` gains the "
                                             "CLI contract (12.4)") == 1
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.679 (2026-11-26): spec, code and tests (12.4, row DEL1f). ") == 1
