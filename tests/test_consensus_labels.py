"""DESIGN 4.3 v1.660 (row JUDGE1a): `consensus_labels` builds a judge task's labels from the
recorded grades of two or more reference judges, keeping an item only where every rerun of every
reference judge gave the same grade, and gives each task's share kept against `min_agreement`.

The grades here are synthetic, with a known truth per item, so each kept item, each dropped item
and each rate is computed by hand. No model is called."""

import copy
import json
import math
from pathlib import Path

import pytest

import model_routing
from model_routing import Model, Registry, calibrate_from_results

ROOT = Path(__file__).resolve().parents[1]
A, B, C = "vendor-a/judge-large", "vendor-b/judge-large", "vendor-c/judge-small"
GEN = "vendor-g/writer"


def consensus_labels(*args, **kwargs):
    from model_routing.stats import consensus_labels as fn  # red until v1.660 lands
    return fn(*args, **kwargs)


def grades_for(task, item, by_judge, reruns=3):
    """One row per judge and rerun; ``by_judge`` maps a judge to one grade or a list per rerun."""
    rows = []
    for judge, grade in by_judge.items():
        per_rerun = grade if isinstance(grade, list) else [grade] * reruns
        assert len(per_rerun) == reruns
        rows += [{"task": task, "item": item, "judge": judge, "rerun": r, "grade": g}
                 for r, g in enumerate(per_rerun)]
    return rows


# Ten items with a known truth. A and B agree on every rerun of q1 to q8 (q8 wrongly: both say
# "fail" where the truth is "pass"); on q9 one rerun of B differs, on q10 A and B differ.
TRUTH = {f"q{i}": ("pass" if i % 2 else "fail") for i in range(1, 11)}
TRUTH["q8"] = "pass"


def synthetic(task="faithfulness"):
    rows = []
    for i in range(1, 11):
        item = f"q{i}"
        truth = TRUTH[item]
        other = "fail" if truth == "pass" else "pass"
        if i <= 7:
            by = {A: truth, B: truth}
        elif i == 8:
            by = {A: other, B: other}
        elif i == 9:
            by = {A: truth, B: [truth, other, truth]}
        else:
            by = {A: truth, B: other}
        rows += grades_for(task, item, by)
    return rows


def registry():
    return Registry([Model(A, "fam-a", 1.0, 2.0, 100_000), Model(B, "fam-b", 1.0, 2.0, 100_000),
                     Model(C, "fam-c", 0.1, 0.2, 100_000), Model(GEN, "fam-g", 3.0, 15.0, 100_000),
                     Model("vendor-g/judge", "fam-g", 1.0, 2.0, 100_000)])


# --- kept items, labels and the rate ------------------------------------------------------------

def test_kept_items_are_those_every_rerun_of_every_judge_graded_alike():
    result = consensus_labels(synthetic(), [A, B], reruns=3)
    assert [label["item"] for label in result["labels"]] == [f"q{i}" for i in range(1, 9)]
    assert [label["gold"] for label in result["labels"]] == [TRUTH[f"q{i}"] for i in range(1, 8)] + ["fail"]
    assert result["tasks"] == [{"task": "faithfulness", "items": 10, "kept": 8, "agreement": 0.8,
                                "passes": False}]
    assert result["passes"] is False and result["min_agreement"] == 0.9


def test_an_item_all_judges_grade_wrong_alike_is_kept_with_the_wrong_label():
    labels = {label["item"]: label["gold"] for label in consensus_labels(synthetic(), [A, B], reruns=3)["labels"]}
    assert TRUTH["q8"] == "pass" and labels["q8"] == "fail"  # agreement between models, not correctness
    assert sum(labels[item] == TRUTH[item] for item in labels) == 7


def test_the_label_row_and_the_result_keys_in_order():
    result = consensus_labels(synthetic(), [B, A], reruns=3)
    assert list(result) == ["passes", "min_agreement", "tasks", "labels"]
    assert list(result["tasks"][0]) == ["task", "items", "kept", "agreement", "passes"]
    first = result["labels"][0]
    assert list(first) == ["task", "item", "gold", "label_source", "consensus_models", "reruns", "agreement"]
    assert first == {"task": "faithfulness", "item": "q1", "gold": "pass", "label_source": "consensus",
                     "consensus_models": [B, A], "reruns": 3, "agreement": 0.8}
    assert type(first["consensus_models"]) is list


def test_label_rows_are_returned_for_a_task_that_does_not_pass():
    result = consensus_labels(synthetic(), (A, B), reruns=3, min_agreement=0.95)
    assert result["passes"] is False and len(result["labels"]) == 8


@pytest.mark.parametrize("kept, minimum, passes", [
    (9, 0.9, True),    # Fraction(0.9) as a binary float is above 9/10; the decimal repr is not
    (8, 0.9, False),
    (1, 0.1, True),    # Fraction(0.1) as a binary float is above 1/10 too
    (10, 1, True),
    (9, 1.0, False),
    (0, 0, True),
    (0, 0.1, False),
])
def test_the_rate_is_compared_exactly_at_and_under_the_minimum(kept, minimum, passes):
    rows = []
    for i in range(10):
        by = {A: "yes", B: "yes"} if i < kept else {A: "yes", B: "no"}
        rows += grades_for("t", f"i{i}", by, reruns=2)
    result = consensus_labels(rows, [A, B], reruns=2, min_agreement=minimum)
    assert result["tasks"][0]["kept"] == kept and result["tasks"][0]["agreement"] == kept / 10
    assert result["tasks"][0]["passes"] is passes and result["passes"] is passes
    assert result["min_agreement"] == float(minimum) and type(result["min_agreement"]) is float


def test_each_task_is_rated_on_its_own_and_every_task_must_pass():
    rows = synthetic("second") + grades_for("first", "x1", {A: 3, B: 3}) + grades_for("first", "x2", {A: 4, B: 4})
    result = consensus_labels(rows, [A, B], reruns=3, min_agreement=0.8)
    assert [t["task"] for t in result["tasks"]] == ["second", "first"]  # order of the first row
    assert [(t["items"], t["kept"], t["passes"]) for t in result["tasks"]] == [(10, 8, True), (2, 2, True)]
    assert result["passes"] is True
    assert [label["agreement"] for label in result["labels"]] == [0.8] * 8 + [1.0, 1.0]
    worse = consensus_labels(rows, [A, B], reruns=3, min_agreement=0.81)
    assert [t["passes"] for t in worse["tasks"]] == [False, True] and worse["passes"] is False


def test_labels_follow_each_items_first_reference_row():
    rows = synthetic()
    rows = rows[30:] + rows[:30]  # q6 to q10 first, then q1 to q5
    items = [label["item"] for label in consensus_labels(rows, [A, B], reruns=3)["labels"]]
    assert items == ["q6", "q7", "q8", "q1", "q2", "q3", "q4", "q5"]


def test_grades_of_another_type_never_agree():
    rows = grades_for("t", "i1", {A: True, B: 1}) + grades_for("t", "i2", {A: 1, B: 1}) \
        + grades_for("t", "i3", {A: "1", B: 1}) + grades_for("t", "i4", {A: False, B: False})
    result = consensus_labels(rows, [A, B], reruns=3, min_agreement=0)
    assert [(label["item"], label["gold"]) for label in result["labels"]] == [("i2", 1), ("i4", False)]
    assert type(result["labels"][0]["gold"]) is int and result["labels"][1]["gold"] is False


def test_three_reference_judges_must_all_agree():
    rows = grades_for("t", "i1", {A: "a", B: "a", C: "a"}) + grades_for("t", "i2", {A: "a", B: "a", C: "b"})
    result = consensus_labels(rows, [A, B, C], reruns=3, min_agreement=0)
    assert [label["item"] for label in result["labels"]] == ["i1"]
    two = consensus_labels(rows, [A, B], reruns=3, min_agreement=0)  # C's rows are ignored
    assert [label["item"] for label in two["labels"]] == ["i1", "i2"]


def test_one_rerun_is_allowed():
    rows = grades_for("t", "i1", {A: "a", B: "a"}, reruns=1)
    assert consensus_labels(rows, [A, B], reruns=1)["labels"][0]["reruns"] == 1


def test_rows_of_other_judges_are_ignored_and_rows_are_not_changed():
    rows = synthetic() + grades_for("faithfulness", "q1", {C: "fail"}) + grades_for("other", "z", {C: "pass"})
    before = copy.deepcopy(rows)
    with_c = consensus_labels(rows, [A, B], reruns=3)
    assert with_c == consensus_labels(synthetic(), [A, B], reruns=3)
    assert rows == before


def test_extra_keys_on_a_row_are_ignored():
    rows = [dict(row, note="x", slice="deep") for row in synthetic()]
    assert consensus_labels(rows, [A, B], reruns=3) == consensus_labels(synthetic(), [A, B], reruns=3)


def test_any_iterable_of_rows():
    assert consensus_labels(iter(synthetic()), [A, B], reruns=3) == consensus_labels(synthetic(), [A, B], reruns=3)


# --- the labels calibrate a candidate judge, one trial per item ---------------------------------

def test_labels_calibrate_a_candidate_judge_one_trial_per_item():
    labels = consensus_labels(synthetic(), [A, B], reruns=3)["labels"]
    candidate = {"q1": "pass", "q2": "fail", "q3": "fail", "q4": "fail", "q5": "pass", "q6": "fail",
                 "q7": "pass", "q8": "pass", "q9": "pass", "q10": "fail"}
    results = [{"task": label["task"], "model": C, "prediction": candidate[label["item"]], "gold": label["gold"]}
               for label in labels]
    stats = calibrate_from_results(results)
    # q3 (truth pass) and q8 (consensus fail) disagree with the labels: 6 of 8, one trial per item
    assert stats.get("faithfulness", C) == (6, 8)


# --- generator isolation ------------------------------------------------------------------------

def test_a_generator_outside_the_judges_families_passes():
    result = consensus_labels(synthetic(), [A, B], reruns=3, registry=registry(), generator_model=GEN)
    assert result == consensus_labels(synthetic(), [A, B], reruns=3)


@pytest.mark.parametrize("judge", [GEN, "vendor-g/judge"])
def test_a_reference_judge_that_is_the_generator_or_of_its_family_is_refused(judge):
    rows = [dict(row, judge=judge) if row["judge"] == B else row for row in synthetic()]
    assert consensus_labels(rows, [A, judge], reruns=3)["tasks"][0]["kept"] == 8  # no generator, no check
    with pytest.raises(ValueError) as caught:
        consensus_labels(rows, [A, judge], reruns=3, registry=registry(), generator_model=GEN)
    assert judge in str(caught.value) and "fam-g" in str(caught.value)


def test_a_variant_of_the_generator_is_of_its_family(tmp_path):
    path = tmp_path / "models.json"
    row = {"family": "fam-g", "price_in": 3.0, "price_out": 15.0, "context_window": 100_000}
    path.write_text(json.dumps({"models": [dict(row, id=A, family="fam-a"),
                                           dict(row, id=GEN, variants={"careful": {"items_per_call": 2}})]}),
                    encoding="utf-8")
    reg = Registry.load(path)
    variant = GEN + "@careful"
    assert reg.get(variant).family == "fam-g"
    rows = grades_for("t", "i1", {A: "a", variant: "a"})
    for generator in (GEN, variant):
        with pytest.raises(ValueError, match="fam-g"):
            consensus_labels(rows, [A, variant], reruns=3, registry=reg, generator_model=generator)


@pytest.mark.parametrize("judges, generator", [([A, "vendor-x/unknown"], GEN), ([A, B], "vendor-x/unknown")])
def test_a_judge_or_generator_outside_the_registry_is_refused(judges, generator):
    rows = grades_for("t", "i1", {judges[0]: "a", judges[1]: "a"})
    with pytest.raises(ValueError, match="vendor-x/unknown"):
        consensus_labels(rows, judges, reruns=3, registry=registry(), generator_model=generator)


@pytest.mark.parametrize("reg, generator", [  # review iter-516 must-fix 2
    (object(), GEN), ({GEN: "fam-g"}, GEN), ([], GEN), (registry(), []), (registry(), ""), (registry(), 3),
    (registry(), ("vendor-g/writer",)),
])
def test_a_registry_or_generator_of_the_wrong_kind_is_a_value_error(reg, generator):
    with pytest.raises(ValueError):
        consensus_labels(synthetic(), [A, B], reruns=3, registry=reg, generator_model=generator)


@pytest.mark.parametrize("kwargs", [{"registry": registry()}, {"generator_model": GEN}])
def test_registry_and_generator_come_together(kwargs):
    with pytest.raises(ValueError):
        consensus_labels(synthetic(), [A, B], reruns=3, **kwargs)


# --- complete and unique ------------------------------------------------------------------------

def test_a_missing_rerun_is_refused_naming_task_item_judge_and_rerun():
    rows = [row for row in synthetic() if not (row["item"] == "q4" and row["judge"] == B and row["rerun"] == 2)]
    with pytest.raises(ValueError) as caught:
        consensus_labels(rows, [A, B], reruns=3)
    message = str(caught.value)
    assert "faithfulness" in message and "'q4'" in message and B in message and "2" in message


def test_a_judge_missing_from_an_item_is_refused():
    rows = [row for row in synthetic() if not (row["item"] == "q10" and row["judge"] == A)]
    with pytest.raises(ValueError, match="q10"):
        consensus_labels(rows, [A, B], reruns=3)


def test_a_repeated_row_is_refused_even_with_the_same_grade():
    rows = synthetic()
    with pytest.raises(ValueError, match="q2"):
        consensus_labels(rows + [dict(rows[7])], [A, B], reruns=3)


@pytest.mark.parametrize("rerun", [3, -1, 7])
def test_a_rerun_outside_the_range_is_refused(rerun):
    rows = synthetic() + [{"task": "faithfulness", "item": "q1", "judge": A, "rerun": rerun, "grade": "pass"}]
    with pytest.raises(ValueError, match="rerun"):
        consensus_labels(rows, [A, B], reruns=3)


def test_fewer_reruns_in_the_file_than_asked_is_refused():
    with pytest.raises(ValueError, match="rerun"):
        consensus_labels(synthetic(), [A, B], reruns=4)


def test_no_row_of_any_reference_judge_is_refused():
    with pytest.raises(ValueError):
        consensus_labels(grades_for("t", "i1", {C: "a", GEN: "a"}), [A, B], reruns=3)
    with pytest.raises(ValueError):
        consensus_labels([], [A, B], reruns=3)


# --- row and argument checks --------------------------------------------------------------------

GOOD = {"task": "t", "item": "i1", "judge": A, "rerun": 0, "grade": "a"}


@pytest.mark.parametrize("bad", [
    {"grade": 0.5}, {"grade": None}, {"grade": ["a"]}, {"grade": {"a": 1}}, {"grade": float("nan")},
    {"rerun": True}, {"rerun": 0.0}, {"rerun": "0"}, {"rerun": None},
    {"task": ""}, {"task": 1}, {"item": ""}, {"item": None},
])
@pytest.mark.parametrize("judge", [A, C])  # a reference judge's row and another judge's row alike
def test_a_bad_row_is_refused(bad, judge):
    # review iter-516 nit 1: A's bad row replaces its good one, so no duplicate cell can raise instead,
    # and the message names the key that is bad
    rows = grades_for("t", "i1", {A: "a", B: "a"}, reruns=1)
    row = dict(GOOD, judge=judge, **bad)
    rows = [row if r["judge"] == A else r for r in rows] if judge == A else rows + [row]
    assert consensus_labels(grades_for("t", "i1", {A: "a", B: "a"}, reruns=1), [A, B], reruns=1)["passes"]
    (key,) = bad
    with pytest.raises(ValueError, match=repr(key)):
        consensus_labels(rows, [A, B], reruns=1)


@pytest.mark.parametrize("judge", ["", 3, None])
def test_a_row_with_a_bad_judge_is_refused(judge):
    rows = grades_for("t", "i1", {A: "a", B: "a"}, reruns=1) + [dict(GOOD, judge=judge)]
    with pytest.raises(ValueError, match="'judge'"):
        consensus_labels(rows, [A, B], reruns=1)


@pytest.mark.parametrize("missing", ["task", "item", "judge", "rerun", "grade"])
def test_a_row_missing_a_key_is_refused(missing):
    row = {k: v for k, v in GOOD.items() if k != missing}
    with pytest.raises(ValueError):
        consensus_labels(grades_for("t", "i1", {A: "a", B: "a"}, reruns=1) + [row], [A, B], reruns=1)


@pytest.mark.parametrize("row", [None, "row", ["t", "i1"], 3])
def test_a_row_that_is_not_a_dict_is_refused(row):
    with pytest.raises(ValueError):
        consensus_labels(grades_for("t", "i1", {A: "a", B: "a"}, reruns=1) + [row], [A, B], reruns=1)


def test_a_bad_row_after_the_good_ones_still_refuses_the_whole_call():
    rows = synthetic() + [dict(GOOD, judge=C, grade=1.5)]
    with pytest.raises(ValueError):
        consensus_labels(rows, [A, B], reruns=3)


@pytest.mark.parametrize("judges", [[A], [A, A], (A, A, B), [A, ""], [A, 3], f"{A},{B}", {A, B}, None, []])
def test_judges_are_two_or_more_distinct_names_in_a_list_or_tuple(judges):
    with pytest.raises(ValueError):
        consensus_labels(synthetic(), judges, reruns=3)


@pytest.mark.parametrize("reruns", [0, -1, True, 3.0, "3", None])
def test_reruns_is_a_positive_int(reruns):
    with pytest.raises(ValueError):
        consensus_labels(synthetic(), [A, B], reruns=reruns)


@pytest.mark.parametrize("minimum", [True, False, -0.01, 1.01, math.nan, math.inf, "0.9", None,
                                     2, -1, 10 ** 1000, -10 ** 1000])  # review iter-516 must-fix 1
def test_min_agreement_is_a_finite_number_in_0_1(minimum):
    with pytest.raises(ValueError):
        consensus_labels(synthetic(), [A, B], reruns=3, min_agreement=minimum)


def test_reruns_is_keyword_only_and_required_and_the_minimum_defaults_to_0_9():
    with pytest.raises(TypeError):
        consensus_labels(synthetic(), [A, B], 3)
    with pytest.raises(TypeError):
        consensus_labels(synthetic(), [A, B])
    rows = []
    for i in range(10):
        rows += grades_for("t", f"i{i}", {A: "y", B: "y" if i < 9 else "n"}, reruns=1)
    assert consensus_labels(rows, [A, B], reruns=1)["passes"] is True


# --- exports, spec and the production note ------------------------------------------------------

def test_consensus_labels_is_exported_after_pair_outcomes():
    names = model_routing.__all__
    assert names[names.index("pair_outcomes") + 1] == "consensus_labels"
    assert model_routing.consensus_labels is model_routing.stats.consensus_labels


def test_design_and_changelog_name_the_contract():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert ("  stats.py        wilson_lower_bound, items_needed (v1.140), Stats, calibrate_from_results, "
            "item_outcomes (v1.602, 4.3), consensus_labels (v1.660, 4.3)\n") in design
    four3 = design[design.index("### 4.3 "):design.index("### 4.4 ")]
    assert ("- v1.660 consensus labels (row JUDGE1a): `consensus_labels(grades: Iterable[dict], judges: Sequence[str], "
            "*, reruns: int, min_agreement: float = 0.9, registry: Registry | None = None, "
            "generator_model: str | None = None) -> dict`") in four3
    assert "`Fraction(kept, items) >= Fraction(repr(float(min_agreement)))`" in four3
    assert "consensus is agreement between models, not human correctness" in four3
    assert "never an `OverflowError` (review iter-516 must-fix 1)" in four3
    assert "never an `AttributeError` or a `TypeError` (review iter-516 must-fix 2)" in four3
    assert "under which `true` equals `1`, so a candidate judge's grades are given the reference judges' type first" in four3
    assert ("  - not in this version: the `consensus-labels` command and `label_source` in stats and `select` "
            "(row JUDGE1b). `model_routing.__all__` gains `consensus_labels`, after `pair_outcomes`\n") in four3
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert sum(line.startswith("- v1.660 (2026-11-26): spec, code, docs and tests (3, 4.3, row JUDGE1a). ")
               for line in changelog) == 1


def test_the_production_note_states_the_function_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert "The changes: labels built from the items where every run of the chosen strong judges agrees" not in text
    line = [line for line in text.splitlines() if line.startswith("- In this library: judge calls are its first case")]
    assert len(line) == 1
    assert ("For a team with no human labels, from v1.660 `consensus_labels` builds labels from the reference "
            "judges' recorded grades, keeping an item only where every rerun of every one of them gave the same "
            "grade, gives each task's share of items kept against a minimum, and refuses a reference judge of the "
            "generator's family; its labels measure agreement with those judges, not correctness. ") in line[0]
    # v1.661 (row JUDGE1ba) restates what follows (tests/test_consensus_labels_cli.py)
