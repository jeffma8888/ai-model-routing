"""v1.24 AutoBench judge committee converter contract (DESIGN 12.11), committed before the script and now its tests.

v1.26 adds ``answer_tokens``: the judge reads the visible answer, output less reasoning tokens, by default.

The script lives outside the package (``evidence/autobench-2026/judges.py``) and loads
convert.py from its own folder, so it is loaded from its path by an autouse fixture. Every
test uses tiny in-memory tables, except the two evidence README tests, which read that README,
and the three at the end, which read the pinned files only when they are already in the default
cache and skip otherwise (CI never downloads them).
"""

import ast
import csv
import importlib.util
import inspect
import itertools
import json
import math
import random
import re
from pathlib import Path

import pytest

from model_routing import Registry, evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "autobench-2026" / "judges.py"
CONVERT = ROOT / "evidence" / "autobench-2026" / "convert.py"
EVIDENCE_README = ROOT / "evidence" / "autobench-2026" / "README.md"
REVISION = "43755180be7d8097068982d7a3f37fc04cd15379"

POOL = {"members": [
    {"display_id": "Alpha-1", "openrouter_id": "x-ai/alpha-1", "family": "A",
     "input_cost_per_mtok": 0.5, "output_cost_per_mtok": 1.5, "context_window": 100000},
    {"display_id": "Beta-2", "openrouter_id": "acme/beta-2", "family": "B",
     "input_cost_per_mtok": 0.25, "output_cost_per_mtok": 0.75, "context_window": 100000},
    {"display_id": "Gamma-3", "openrouter_id": "z-ai/gamma-3", "family": "G",
     "input_cost_per_mtok": 2.0, "output_cost_per_mtok": 8.0, "context_window": 100000},
    {"display_id": "Delta-4", "openrouter_id": "acme/delta-4", "family": "D",
     "input_cost_per_mtok": 1.0, "output_cost_per_mtok": 3.0, "context_window": 100000},
    {"display_id": "Eps-5", "openrouter_id": "acme/eps-5", "family": "E",
     "input_cost_per_mtok": 0.1, "output_cost_per_mtok": 0.2, "context_window": 100000},
    {"display_id": "Zeta-6", "openrouter_id": "acme/zeta-6", "family": "Z",
     "input_cost_per_mtok": 0.3, "output_cost_per_mtok": 0.6, "context_window": 100000},
]}
COLUMNS = ["prompt_id", "model", "score", "score_sd", "n_judges", "cost", "input_tokens", "output_tokens",
           "reasoning_tokens", "judges_json", "source", "has_answer"]
ROW_KEYS = ["task", "item", "model", "correct", "input_tokens", "output_tokens"]
REPORT_KEYS = ["candidates", "candidates_by", "tolerance", "min_committee", "rubric_tokens", "grade_tokens",
               "answer_tokens", "task_by", "scored_cells", "kept", "dropped_self_graded", "dropped_missing_candidate",
               "dropped_small_committee", "self_graded_cells", "unscored_cells", "dropped_out_of_pool", "rows"]


def load_jm():
    if not SCRIPT.is_file():
        raise ModuleNotFoundError(f"no judge converter at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("autobench_judges", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def jm():
    return load_jm()


def cell(pid, model, grades, score="4.5", inp="100.0", out="50.0", source="original", rea="0.0"):
    text = grades if isinstance(grades, str) else json.dumps(grades)
    return {"prompt_id": pid, "model": model, "score": score, "score_sd": "0.5", "n_judges": "10",
            "cost": "0.001", "input_tokens": inp, "output_tokens": out, "reasoning_tokens": rea,
            "judges_json": text, "source": source, "has_answer": "true"}


def committee(**grades):
    return {"Out-7": 4, "Out-8": 4, "Out-9": 4, **grades}


# --- the label ---------------------------------------------------------------------------------

def test_leave_one_out_label_with_exact_boundary(jm):
    # Gamma-3 answered; its own grade 1 never enters a committee
    graders = {"Alpha-1": 4, "Beta-2": 5, "Delta-4": 4, "Eps-5": 5, "Out-9": 4, "Gamma-3": 1}
    rows, report = jm.judge_matrix([cell("q1", "Gamma-3", graders)], POOL, candidates=["Alpha-1", "Beta-2"])
    got = {r["model"]: r["correct"] for r in rows}
    # Alpha: committee Beta 5, Delta 4, Eps 5, Out 4 -> 4.5, |4 - 4.5| = 0.5 <= 0.5
    # Beta: committee Alpha 4, Delta 4, Eps 5, Out 4 -> 4.25, |5 - 4.25| = 0.75
    assert got == {"xai/alpha-1": True, "acme/beta-2": False}
    rows, _ = jm.judge_matrix([cell("q1", "Gamma-3", graders)], POOL, tolerance=0.25,
                              candidates=["Alpha-1", "Beta-2"])
    assert {r["model"]: r["correct"] for r in rows} == {"xai/alpha-1": False, "acme/beta-2": False}
    rows, _ = jm.judge_matrix([cell("q1", "Gamma-3", graders)], POOL, tolerance=0.75,
                              candidates=["Alpha-1", "Beta-2"])
    assert {r["model"]: r["correct"] for r in rows} == {"xai/alpha-1": True, "acme/beta-2": True}
    assert report["self_graded_cells"] == 1 and report["kept"] == {"all": 1}


def test_answer_models_own_grade_is_not_in_the_committee(jm):
    # with Delta's self-grade 0 the committee mean would be 3 and Alpha's 3 would agree
    graders = {"Alpha-1": 3, "Beta-2": 4, "Gamma-3": 4, "Eps-5": 4, "Delta-4": 0}
    rows, _ = jm.judge_matrix([cell("q1", "Delta-4", graders)], POOL, candidates=["Alpha-1"])
    assert [r["correct"] for r in rows] == [False]


def test_null_grades_are_not_graders(jm):
    # with the null counted as 0 the mean would be 3.375 and Alpha would disagree
    graders = {"Alpha-1": 4.5, "Beta-2": 4, "Gamma-3": 5, "Out-9": 4.5, "Delta-4": None}
    rows, report = jm.judge_matrix([cell("q1", "Zeta-6", graders)], POOL, candidates=["Alpha-1"])
    assert [r["correct"] for r in rows] == [True]
    graders["Alpha-1"] = None
    rows, report = jm.judge_matrix([cell("q1", "Zeta-6", graders)], POOL, candidates=["Alpha-1"])
    assert rows == [] and report["dropped_missing_candidate"] == 1


def test_committee_mean_is_fsum_and_the_tolerance_has_no_epsilon(jm):
    # math.fsum gives 1.2333333333333334 and |grade - mean| == 0.5; a left-to-right sum gives
    # 1.2333333333333332 and a distance just above 0.5
    graders = {"Alpha-1": 1.7333333333333334, "Beta-2": 1.1, "Gamma-3": 1.2, "Delta-4": 1.4}
    rows, _ = jm.judge_matrix([cell("q1", "Zeta-6", graders)], POOL, candidates=["Alpha-1"])
    assert [r["correct"] for r in rows] == [True]
    # one ulp past the tolerance is outside it
    graders = {"Alpha-1": math.nextafter(4.5, 5.0), "Beta-2": 4, "Gamma-3": 4, "Delta-4": 4}
    rows, _ = jm.judge_matrix([cell("q1", "Zeta-6", graders)], POOL, candidates=["Alpha-1"])
    assert [r["correct"] for r in rows] == [False]


def test_committee_includes_other_candidates_and_judges_outside_the_pool(jm):
    graders = {"Alpha-1": 2, "Beta-2": 2, "Out-8": 2, "Out-9": 2}
    rows, _ = jm.judge_matrix([cell("q1", "Zeta-6", graders)], POOL, candidates=["Alpha-1", "Beta-2"])
    assert [r["correct"] for r in rows] == [True, True]


# --- dropped answers ------------------------------------------------------------------------------

def test_drop_rules_in_order_and_counted(jm):
    full = committee(**{"Alpha-1": 4, "Beta-2": 4, "Gamma-3": 4})
    matrix = [
        cell("q1", "Alpha-1", {"Beta-2": 4, "Out-9": 4}),  # self-graded first, though Alpha is missing too
        cell("q2", "Beta-2", full),                         # self-graded
        cell("q3", "Zeta-6", committee(**{"Alpha-1": 4})),  # Beta missing
        cell("q4", "Zeta-6", {"Alpha-1": 4, "Beta-2": 4, "Gamma-3": 4}),  # 3 graders < min_committee + 1
        cell("q5", "Gamma-3", full),                        # kept, self-graded but Gamma is no candidate
        cell("q6", "Zeta-6", full),                         # kept
    ]
    rows, report = jm.judge_matrix(matrix, POOL, candidates=["Alpha-1", "Beta-2"])
    assert report["scored_cells"] == 6
    assert report["dropped_self_graded"] == 2
    assert report["dropped_missing_candidate"] == 1
    assert report["dropped_small_committee"] == 1
    assert report["kept"] == {"all": 2}
    assert report["self_graded_cells"] == 2  # q2 and q5; q1's Alpha did not grade
    assert sorted({r["item"] for r in rows}) == ["q5|zai/gamma-3", "q6|acme/zeta-6"]
    assert report["rows"] == len(rows) == 4
    total = report["dropped_self_graded"] + report["dropped_missing_candidate"] + report["dropped_small_committee"]
    assert report["scored_cells"] == sum(report["kept"].values()) + total


def test_min_committee_bound(jm):
    graders = {"Alpha-1": 4, "Beta-2": 4, "Gamma-3": 4}  # Alpha's committee is Beta and Gamma
    _, report = jm.judge_matrix([cell("q1", "Zeta-6", graders)], POOL, candidates=["Alpha-1"], min_committee=2)
    assert report["kept"] == {"all": 1} and report["dropped_small_committee"] == 0
    _, report = jm.judge_matrix([cell("q1", "Zeta-6", graders)], POOL, candidates=["Alpha-1"], min_committee=3)
    assert report["kept"] == {} and report["dropped_small_committee"] == 1
    # the answer model's own grade does not count towards the committee
    graders["Zeta-6"] = 4
    _, report = jm.judge_matrix([cell("q1", "Zeta-6", graders)], POOL, candidates=["Alpha-1"], min_committee=3)
    assert report["dropped_small_committee"] == 1


def test_out_of_pool_and_unscored_rows_are_counted_before_anything_is_read(jm):
    matrix = [
        cell("q1", "Stranger-7", "not json", inp="x"),
        cell("q2", "Stranger-7", "not json"),
        cell("q1", "Other-0", "[]", source="fill_7_4"),
        cell("q1", "Alpha-1", "{}", score="", inp="bad"),
        cell("q2", "Zeta-6", committee(**{"Alpha-1": 4})),
    ]
    rows, report = jm.judge_matrix(matrix, POOL, candidates=["Alpha-1"])
    assert report["dropped_out_of_pool"] == {"Other-0": 1, "Stranger-7": 2}
    assert list(report["dropped_out_of_pool"]) == ["Other-0", "Stranger-7"]
    assert report["unscored_cells"] == 1 and report["scored_cells"] == 1 and len(rows) == 1


# --- candidates -----------------------------------------------------------------------------------

def default_matrix():
    return [
        cell("q1", "Zeta-6", committee(**{"Beta-2": 4, "Delta-4": 4, "Alpha-1": 4})),
        cell("q2", "Zeta-6", committee(**{"Beta-2": 4, "Delta-4": 4})),
        cell("q3", "Zeta-6", committee(**{"Alpha-1": 4, "Gamma-3": 4})),
    ]


def test_default_candidates_keep_the_most_answers(jm):
    rows, report = jm.judge_matrix(default_matrix(), POOL, size=2)
    assert report["candidates"] == ["acme/beta-2", "acme/delta-4"]
    assert report["candidates_by"] == "most_cells"
    assert report["kept"] == {"all": 2} and report["dropped_missing_candidate"] == 1
    assert {r["model"] for r in rows} == {"acme/beta-2", "acme/delta-4"}


def test_default_candidates_tie_goes_to_the_first_sorted_set(jm):
    _, report = jm.judge_matrix(default_matrix()[0:1] + default_matrix()[2:], POOL, size=2)
    assert report["candidates"] == ["acme/beta-2", "xai/alpha-1"]  # display IDs Alpha-1, Beta-2
    _, report = jm.judge_matrix(default_matrix(), POOL, size=1)
    assert report["candidates"] == ["xai/alpha-1"]  # Alpha, Beta and Delta each keep two


def test_judges_outside_the_pool_are_never_candidates(jm):
    # Out-7, Out-8 and Out-9 grade every answer, but have no price
    _, report = jm.judge_matrix(default_matrix(), POOL, size=2)
    assert all(not c.startswith("Out") for c in report["candidates"])


def test_default_candidates_respect_the_self_graded_rule(jm):
    # Beta and Delta grade both answers, but Beta answered one of them
    matrix = [cell("q1", "Beta-2", committee(**{"Beta-2": 4, "Delta-4": 4, "Gamma-3": 4})),
              cell("q2", "Zeta-6", committee(**{"Beta-2": 4, "Delta-4": 4, "Gamma-3": 4}))]
    _, report = jm.judge_matrix(matrix, POOL, size=2)
    assert report["candidates"] == ["acme/delta-4", "zai/gamma-3"]
    assert report["kept"] == {"all": 2}


def brute_force_candidates(jm, matrix, pool, size, min_committee):
    """The v1.128 search: every candidate set tried on every answer, the first strictly highest count wins.

    Returns the chosen mapped IDs and each set's count in ``itertools.combinations`` order, or None when
    ``size`` is more than the pool judges that grade a scored answer."""
    names = jm.convert.pool_models(pool)
    cells = [(r["model"], jm.parse_grades(r["judges_json"], r["prompt_id"], r["model"])) for r in matrix
             if r["model"] in names and r["score"] not in (None, "")]
    judges = sorted({j for _, graders in cells for j in graders if j in names})
    if size > len(judges):
        return None
    counts = [(combo, sum(1 for answer, graders in cells
                          if jm._fate(answer, graders, combo, min_committee) == "kept"))
              for combo in itertools.combinations(judges, size)]
    best = max(n for _, n in counts)
    first = next(combo for combo, n in counts if n == best)
    return sorted(names[c] for c in first), counts


def random_matrix(rng):
    displays = [m["display_id"] for m in POOL["members"]]
    matrix = []
    for q in range(rng.randint(1, 8)):
        for answer in rng.sample(displays, rng.randint(1, 3)):
            grades = {}
            for judge in displays + ["Out-7", "Out-8"]:
                draw = rng.random()
                if draw < 0.55:
                    grades[judge] = rng.choice([3, 4, 4.5, 5])
                elif draw < 0.65:
                    grades[judge] = None
            matrix.append(cell(f"q{q}", answer, grades, score="" if rng.random() < 0.05 else "4.5"))
    return matrix


def test_default_search_matches_trying_every_set_on_every_answer(jm):
    # v1.129: the grouped search must choose what the v1.128 search over every answer chose
    rng = random.Random(117)
    seen = {"tie": 0, "later_wins": 0, "none_kept": 0, "size_too_big": 0}
    for _ in range(300):
        matrix = random_matrix(rng)
        size, min_committee = rng.randint(1, 4), rng.randint(1, 4)
        want = brute_force_candidates(jm, matrix, POOL, size, min_committee)
        if want is None:
            with pytest.raises(ValueError, match=f"size {size} is more than"):
                jm.judge_matrix(matrix, POOL, size=size, min_committee=min_committee)
            seen["size_too_big"] += 1
            continue
        chosen, counts = want
        _, report = jm.judge_matrix(matrix, POOL, size=size, min_committee=min_committee)
        assert report["candidates"] == chosen, (size, min_committee, counts)
        assert report["candidates_by"] == "most_cells"
        best = max(n for _, n in counts)
        seen["tie"] += best > 0 and sum(1 for _, n in counts if n == best) > 1
        seen["later_wins"] += counts[0][1] < best
        seen["none_kept"] += best == 0
    assert all(seen.values()), seen


def test_default_candidates_when_no_set_keeps_an_answer(jm):
    # two graders besides the answer model each: too small a committee for any set, so the first set is chosen
    matrix = [cell("q1", "Zeta-6", {"Alpha-1": 4, "Beta-2": 4, "Delta-4": 4}),
              cell("q2", "Zeta-6", {"Alpha-1": 4, "Beta-2": 4, "Delta-4": 5})]
    rows, report = jm.judge_matrix(matrix, POOL, size=2)
    assert report["candidates"] == ["acme/beta-2", "xai/alpha-1"]  # display IDs Alpha-1, Beta-2
    assert rows == [] and report["kept"] == {} and report["dropped_small_committee"] == 2


@pytest.mark.xfail(strict=True, raises=AssertionError,
                   reason="v1.129 spec ahead of the code: the v1.128 search runs the drop rules per answer per set")
def test_default_search_runs_the_drop_rules_once_per_answer(jm, monkeypatch):
    calls = []
    fate = jm._fate

    def counted(*args):
        calls.append(args)
        return fate(*args)

    monkeypatch.setattr(jm, "_fate", counted)
    _, report = jm.judge_matrix(default_matrix(), POOL, candidates=["Beta-2", "Delta-4"])
    assert len(calls) == report["scored_cells"] == 3
    calls.clear()
    _, report = jm.judge_matrix(default_matrix(), POOL, size=2)  # 6 sets of the 4 pool judges
    assert report["candidates"] == ["acme/beta-2", "acme/delta-4"]
    assert len(calls) == report["scored_cells"] == 3


def test_size_larger_than_the_pool_judges(jm):
    with pytest.raises(ValueError, match="size 5"):
        jm.judge_matrix(default_matrix(), POOL, size=5)  # Alpha, Beta, Delta, Gamma grade


def test_answer_with_no_graders_and_a_candidate_that_grades_nothing(jm):
    rows, report = jm.judge_matrix([cell("q1", "Zeta-6", {}), cell("q2", "Zeta-6", {"Alpha-1": None})], POOL,
                                   candidates=["Alpha-1"])
    assert rows == [] and report["dropped_missing_candidate"] == 2 and report["kept"] == {}
    rows, report = jm.judge_matrix(default_matrix(), POOL, candidates=["Eps-5"])
    assert rows == [] and report["kept"] == {} and report["dropped_missing_candidate"] == 3
    assert report["candidates"] == ["acme/eps-5"] and report["rows"] == 0


def test_questions_are_not_read_with_task_by_all(jm):
    want = jm.judge_matrix(default_matrix(), POOL, size=2)
    assert jm.judge_matrix(default_matrix(), POOL, size=2, questions="not a list") == want
    assert jm.judge_matrix(default_matrix(), POOL, size=2, questions=[{"prompt_id": ""}, 7]) == want


def test_size_is_checked_even_with_given_candidates(jm):
    with pytest.raises(ValueError, match="size"):
        jm.judge_matrix(default_matrix(), POOL, candidates=["Alpha-1"], size=0)
    with pytest.raises(ValueError, match="size"):
        jm.judge_matrix(default_matrix(), POOL, candidates=["Alpha-1"], size=True)


def test_given_candidates_ignore_size(jm):
    _, report = jm.judge_matrix(default_matrix(), POOL, candidates=("Gamma-3",), size=99)
    assert report["candidates"] == ["zai/gamma-3"] and report["candidates_by"] == "given"


# --- rows and report ------------------------------------------------------------------------------

def test_rows_tokens_keys_and_order(jm):
    matrix = [cell("q2", "Zeta-6", committee(**{"Alpha-1": 4, "Beta-2": 4}), inp="303.0", out="1912.0"),
              cell("q1", "Gamma-3", committee(**{"Alpha-1": 4, "Beta-2": 4}), inp="7", out="0.0")]
    rows, report = jm.judge_matrix(matrix, POOL, candidates=["Beta-2", "Alpha-1"])
    assert all(list(r) == ROW_KEYS for r in rows)
    assert [(r["item"], r["model"]) for r in rows] == [
        ("q1|zai/gamma-3", "acme/beta-2"), ("q1|zai/gamma-3", "xai/alpha-1"),
        ("q2|acme/zeta-6", "acme/beta-2"), ("q2|acme/zeta-6", "xai/alpha-1")]
    assert [(r["input_tokens"], r["output_tokens"]) for r in rows] == [(407, 200)] * 2 + [(2615, 200)] * 2
    assert all(type(r["input_tokens"]) is int and type(r["output_tokens"]) is int for r in rows)
    assert all(r["task"] == "all" and r["correct"] is True for r in rows)
    rows, report = jm.judge_matrix(matrix, POOL, candidates=["Beta-2", "Alpha-1"], rubric_tokens=0, grade_tokens=50)
    assert [(r["input_tokens"], r["output_tokens"]) for r in rows] == [(7, 50)] * 2 + [(2215, 50)] * 2
    assert list(report) == REPORT_KEYS
    assert report["candidates"] == ["acme/beta-2", "xai/alpha-1"]
    assert (report["tolerance"], report["min_committee"], report["rubric_tokens"], report["grade_tokens"],
            report["task_by"]) == (0.5, 3, 0, 50, "all")


def test_defaults(jm):
    _, report = jm.judge_matrix([cell("q1", "Zeta-6", committee(**{"Alpha-1": 4}))], POOL, candidates=["Alpha-1"])
    assert (report["tolerance"], report["min_committee"], report["rubric_tokens"], report["grade_tokens"],
            report["answer_tokens"], report["task_by"]) == (0.5, 3, 400, 200, "visible", "all")
    assert (jm.DEFAULT_TOLERANCE, jm.DEFAULT_SIZE, jm.DEFAULT_MIN_COMMITTEE, jm.DEFAULT_RUBRIC_TOKENS,
            jm.DEFAULT_GRADE_TOKENS, jm.DEFAULT_ANSWER_TOKENS) == (0.5, 5, 3, 400, 200, "visible")


def test_answer_tokens_is_the_last_parameter_so_positional_calls_keep_their_meaning(jm):
    params = inspect.signature(jm.judge_matrix).parameters
    assert list(params)[-3:] == ["task_by", "questions", "answer_tokens"]
    assert params["answer_tokens"].default == "visible"
    matrix = [cell("q1", "Zeta-6", committee(**{"Alpha-1": 4}), out="90", rea="30")]
    assert (jm.judge_matrix(matrix, POOL, 0.5, ["Alpha-1"], 5, 3, 400, 200, "all", None)
            == jm.judge_matrix(matrix, POOL, candidates=["Alpha-1"]))


def test_visible_answer_is_output_less_reasoning_floored_at_zero(jm):
    matrix = [cell("q1", "Zeta-6", committee(**{"Alpha-1": 4}), inp="303.0", out="1912.0", rea="1500.0"),
              cell("q2", "Zeta-6", committee(**{"Alpha-1": 2}), inp="7", out="50.0", rea="60.0"),
              cell("q3", "Zeta-6", committee(**{"Alpha-1": 4}), inp="9", out="40", rea="40"),
              cell("q4", "Zeta-6", committee(**{"Alpha-1": 4}), inp="11", out="0.0", rea="0")]
    rows, report = jm.judge_matrix(matrix, POOL, candidates=["Alpha-1"])
    assert [r["input_tokens"] for r in rows] == [303 + 412 + 400, 7 + 0 + 400, 9 + 0 + 400, 11 + 0 + 400]
    assert all(type(r["input_tokens"]) is int and r["output_tokens"] == 200 for r in rows)
    assert report["answer_tokens"] == "visible"
    full, full_report = jm.judge_matrix(matrix, POOL, candidates=["Alpha-1"], answer_tokens="output")
    assert [r["input_tokens"] for r in full] == [303 + 1912 + 400, 7 + 50 + 400, 9 + 40 + 400, 11 + 0 + 400]
    assert full_report["answer_tokens"] == "output" and list(full_report) == REPORT_KEYS
    assert ([{k: v for k, v in r.items() if k != "input_tokens"} for r in rows]
            == [{k: v for k, v in r.items() if k != "input_tokens"} for r in full])
    assert [r["correct"] for r in rows] == [True, False, True, True]
    assert ({k: v for k, v in report.items() if k != "answer_tokens"}
            == {k: v for k, v in full_report.items() if k != "answer_tokens"})
    rows, _ = jm.judge_matrix(matrix, POOL, candidates=["Alpha-1"], rubric_tokens=0, answer_tokens="visible")
    assert [r["input_tokens"] for r in rows] == [715, 7, 9, 11]


@pytest.mark.parametrize("value", ["1.5", "-1", "", "x", "nan", None])
def test_reasoning_tokens_are_read_only_for_the_visible_answer(jm, value):
    row = cell("q7", "Zeta-6", committee(**{"Alpha-1": 4}))
    if value is None:
        del row["reasoning_tokens"]
    else:
        row["reasoning_tokens"] = value
    rows, _ = jm.judge_matrix([row], POOL, candidates=["Alpha-1"], answer_tokens="output")
    assert [r["input_tokens"] for r in rows] == [100 + 50 + 400]
    with pytest.raises(ValueError, match="q7.*reasoning_tokens"):
        jm.judge_matrix([row], POOL, candidates=["Alpha-1"])


def test_reasoning_tokens_are_not_read_on_dropped_rows(jm):
    matrix = [cell("q1", "Stranger-7", "{}", rea=""), cell("q1", "Alpha-1", "{}", score="", rea="bad"),
              cell("q2", "Zeta-6", committee(**{"Alpha-1": 4}), rea="20")]
    rows, report = jm.judge_matrix(matrix, POOL, candidates=["Alpha-1"])
    assert report["unscored_cells"] == 1 and report["dropped_out_of_pool"] == {"Stranger-7": 1}
    assert [r["input_tokens"] for r in rows] == [100 + 30 + 400]


def test_task_by_domain(jm):
    questions = [{"prompt_id": "q1", "ddc_domain": "9 History"}, {"prompt_id": "q2", "ddc_domain": "5 Science"},
                 {"prompt_id": "q3", "ddc_domain": "5 Science"}]
    matrix = [cell(p, "Zeta-6", committee(**{"Alpha-1": 4})) for p in ("q1", "q2", "q3")]
    rows, report = jm.judge_matrix(matrix, POOL, candidates=["Alpha-1"], task_by="domain", questions=questions)
    assert report["kept"] == {"5 Science": 2, "9 History": 1} and list(report["kept"]) == ["5 Science", "9 History"]
    assert [r["task"] for r in rows] == ["5 Science", "5 Science", "9 History"]
    with pytest.raises(ValueError, match="q3"):
        jm.judge_matrix(matrix, POOL, candidates=["Alpha-1"], task_by="domain", questions=questions[:2])


def test_result_does_not_depend_on_row_order(jm):
    matrix = default_matrix() + [cell("q4", "Gamma-3", committee(**{"Beta-2": 5, "Delta-4": 3, "Gamma-3": 1})),
                                 cell("q4", "Stranger-7", "{}")]
    want = jm.judge_matrix(matrix, POOL, size=2)
    for seed in range(5):
        shuffled = list(matrix)
        random.Random(seed).shuffle(shuffled)
        assert jm.judge_matrix(shuffled, POOL, size=2) == want


def test_rows_feed_the_evaluator_at_pool_list_prices(jm, tmp_path):
    matrix = [cell(f"q{i}", "Zeta-6", committee(**{"Alpha-1": 4 if i % 3 else 2, "Beta-2": 4}),
                   inp=f"{100 + i}.0", out="20.0") for i in range(40)]
    rows, _ = jm.judge_matrix(matrix, POOL, candidates=["Alpha-1", "Beta-2"])
    path = tmp_path / "registry.json"
    path.write_text(json.dumps(jm.convert.pool_registry(POOL)), encoding="utf-8")
    registry = Registry.load(path)
    outcomes = outcomes_from_rows(rows, registry)
    by = {(o.item, o.model): o for o in outcomes}
    first = by[("q1|acme/zeta-6", "xai/alpha-1")]
    assert first.cost_usd == registry.get("xai/alpha-1").cost(101 + 20 + 400, 200)
    result = evaluate(outcomes, bars=[0.7], seeds=range(3), min_samples=5)
    assert result["tasks"] == {"all": {"items": 40, "models": ["acme/beta-2", "xai/alpha-1"]}}


# --- errors ---------------------------------------------------------------------------------------

GOOD = [cell("q1", "Zeta-6", committee(**{"Alpha-1": 4}))]


@pytest.mark.parametrize("kwargs, message", [
    ({"tolerance": True}, "tolerance"), ({"tolerance": -0.1}, "tolerance"), ({"tolerance": math.nan}, "tolerance"),
    ({"tolerance": math.inf}, "tolerance"), ({"tolerance": "0.5"}, "tolerance"),
    ({"candidates": []}, "candidates"), ({"candidates": "Alpha-1"}, "candidates"),
    ({"candidates": ["Nope-0"]}, "Nope-0"), ({"candidates": ["Out-9"]}, "Out-9"),
    ({"candidates": ["Alpha-1", "Alpha-1"]}, "Alpha-1"), ({"candidates": [1]}, "1"),
    ({"size": 0}, "size"), ({"size": True}, "size"), ({"size": 1.0}, "size"),
    ({"min_committee": 0}, "min_committee"), ({"min_committee": False}, "min_committee"),
    ({"rubric_tokens": -1}, "rubric_tokens"), ({"rubric_tokens": True}, "rubric_tokens"),
    ({"rubric_tokens": 1.5}, "rubric_tokens"), ({"grade_tokens": -1}, "grade_tokens"),
    ({"answer_tokens": "reasoning"}, "answer_tokens"), ({"answer_tokens": None}, "answer_tokens"),
    ({"answer_tokens": ["visible"]}, "answer_tokens"), ({"answer_tokens": "Visible"}, "answer_tokens"),
    ({"task_by": "judge"}, "task_by"), ({"task_by": "domain"}, "questions"),
    ({"task_by": "domain", "questions": [{"prompt_id": "q1"}]}, "ddc_domain"),
    ({"task_by": "domain", "questions": [{"prompt_id": "q1", "ddc_domain": "A"}] * 2}, "repeated"),
])
def test_invalid_options(jm, kwargs, message):
    with pytest.raises(ValueError, match=re.escape(message)):
        jm.judge_matrix(GOOD, POOL, **kwargs)


def test_pool_is_checked_first(jm):
    with pytest.raises(ValueError, match="pool"):
        jm.judge_matrix(GOOD, {}, tolerance=-1)
    with pytest.raises(ValueError, match="tolerance"):
        jm.judge_matrix(GOOD, POOL, tolerance=-1, size=0)
    with pytest.raises(ValueError, match="grade_tokens"):
        jm.judge_matrix(GOOD, POOL, grade_tokens=-1, answer_tokens="x")
    with pytest.raises(ValueError, match="answer_tokens"):
        jm.judge_matrix(GOOD, POOL, answer_tokens="x", task_by="judge")


@pytest.mark.parametrize("text", ["not json", "[1, 2]", '{"Alpha-1": true}', '{"Alpha-1": "4"}',
                                  '{"Alpha-1": NaN}', '{"Alpha-1": Infinity}', '{"": 4}', ""])
def test_invalid_judges_json(jm, text):
    with pytest.raises(ValueError, match="q7"):
        jm.judge_matrix([cell("q7", "Zeta-6", text)], POOL, candidates=["Alpha-1"])


@pytest.mark.parametrize("field, value", [("input_tokens", "1.5"), ("output_tokens", "-1"), ("input_tokens", ""),
                                          ("reasoning_tokens", "2.5"), ("reasoning_tokens", "-3")])
def test_invalid_token_counts(jm, field, value):
    row = cell("q7", "Zeta-6", committee(**{"Alpha-1": 4}))
    row[field] = value
    with pytest.raises(ValueError, match="q7"):
        jm.judge_matrix([row], POOL, candidates=["Alpha-1"])


@pytest.mark.parametrize("bad, answer_tokens, named", [
    (("input_tokens", "output_tokens"), "output", "input_tokens"),
    (("input_tokens", "output_tokens"), "visible", "input_tokens"),
    (("input_tokens", "output_tokens", "reasoning_tokens"), "visible", "input_tokens"),
    (("output_tokens", "reasoning_tokens"), "visible", "output_tokens"),
])
def test_a_row_with_several_bad_counts_names_the_first_in_input_output_reasoning_order(jm, bad, answer_tokens, named):
    row = cell("q7", "Zeta-6", committee(**{"Alpha-1": 4}))
    for field in bad:
        row[field] = "y"
    with pytest.raises(ValueError, match=rf"q7, Zeta-6: {named} 'y'"):
        jm.judge_matrix([row], POOL, candidates=["Alpha-1"], answer_tokens=answer_tokens)


def test_invalid_matrix_rows(jm):
    with pytest.raises(ValueError, match="repeated"):
        jm.judge_matrix(GOOD + GOOD, POOL, candidates=["Alpha-1"])
    with pytest.raises(ValueError, match="repeated"):
        jm.judge_matrix([cell("q1", "Stranger-7", "{}")] * 2, POOL, candidates=["Alpha-1"])
    with pytest.raises(ValueError, match="prompt_id"):
        jm.judge_matrix([{"model": "Zeta-6"}], POOL, candidates=["Alpha-1"])
    with pytest.raises(ValueError, match="prompt_id"):
        jm.judge_matrix(["q1"], POOL, candidates=["Alpha-1"])


# --- reuse of the converter -------------------------------------------------------------------

def test_reuses_the_converter_and_holds_no_pins(jm):
    assert Path(jm.convert.__file__).resolve() == CONVERT.resolve()
    assert jm.convert.REVISION == REVISION
    source = SCRIPT.read_text(encoding="utf-8")
    assert not re.search(r"[0-9a-f]{64}", source)
    imported = set()
    for node in ast.walk(ast.parse(source)):
        if isinstance(node, ast.Import):
            imported |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            imported.add((node.module or "").split(".")[0])
    assert imported <= {"__future__", "argparse", "csv", "importlib", "itertools", "json", "math", "sys",
                        "pathlib"}
    assert "fetch" not in {n.name for n in ast.walk(ast.parse(source)) if isinstance(n, ast.FunctionDef)}


# --- CLI ------------------------------------------------------------------------------------------

def write_folder(folder, matrix, questions=None, pool=None):
    folder.mkdir(parents=True, exist_ok=True)
    with (folder / "matrix.csv").open("w", encoding="utf-8", newline="") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS)
        w.writeheader()
        w.writerows(matrix)
    if questions is not None:
        with (folder / "questions.csv").open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=["prompt_id", "ddc_domain"])
            w.writeheader()
            w.writerows(questions)
    (folder / "pool.json").write_text(json.dumps(POOL if pool is None else pool), encoding="utf-8")
    return folder


@pytest.fixture
def folder(jm, tmp_path, monkeypatch):
    questions = [{"prompt_id": f"q{i}", "ddc_domain": "9 History" if i < 2 else "5 Science"} for i in range(1, 4)]
    data = write_folder(tmp_path / "data", default_matrix(), questions)
    seen = []

    def fetch(cache_dir=None):
        seen.append(cache_dir)
        return data
    monkeypatch.setattr(jm.convert, "fetch", fetch)
    return data, seen


def test_main_writes_the_matrix(jm, tmp_path, folder, capsys):
    _, seen = folder
    out = tmp_path / "out.jsonl"
    assert jm.main(["--out", str(out), "--size", "2"]) == 0
    captured = capsys.readouterr()
    rows, report = jm.judge_matrix(default_matrix(), POOL, size=2)
    assert captured.out == json.dumps(report, indent=2) + "\n" and captured.err == ""
    assert out.read_text(encoding="utf-8") == "".join(json.dumps(r) + "\n" for r in rows)
    assert not (tmp_path / "out.jsonl.part").exists()
    assert seen == [None]


def test_main_options(jm, tmp_path, folder, capsys):
    _, seen = folder
    out = tmp_path / "out.jsonl"
    assert jm.main(["--out", str(out), "--cache", str(tmp_path / "c"), "--tolerance", "0.25",
                    "--candidates", "Gamma-3,Alpha-1", "--min-committee", "2", "--rubric-tokens", "0",
                    "--grade-tokens", "10", "--task-by", "domain"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["candidates"] == ["xai/alpha-1", "zai/gamma-3"] and report["candidates_by"] == "given"
    assert (report["tolerance"], report["min_committee"], report["rubric_tokens"], report["grade_tokens"],
            report["task_by"]) == (0.25, 2, 0, 10, "domain")
    assert report["kept"] == {"5 Science": 1}
    assert seen == [str(tmp_path / "c")]


def test_main_answer_tokens(jm, tmp_path, monkeypatch, capsys):
    matrix = [cell(f"q{i}", "Zeta-6", committee(**{"Alpha-1": 4}), inp="10", out="300", rea="200") for i in (1, 2)]
    data = write_folder(tmp_path / "data", matrix)
    monkeypatch.setattr(jm.convert, "fetch", lambda cache_dir=None: data)
    out = tmp_path / "out.jsonl"
    for args, name, answer in [([], "visible", 100), (["--answer-tokens", "output"], "output", 300),
                               (["--answer-tokens", "visible"], "visible", 100)]:
        assert jm.main(["--out", str(out), "--candidates", "Alpha-1"] + args) == 0
        assert json.loads(capsys.readouterr().out)["answer_tokens"] == name
        lines = out.read_text(encoding="utf-8").splitlines()
        assert [json.loads(line)["input_tokens"] for line in lines] == [10 + answer + 400] * 2


def test_main_registry_matches_the_converter(jm, tmp_path, folder, capsys):
    out, reg = tmp_path / "out.jsonl", tmp_path / "reg.json"
    assert jm.main(["--out", str(out), "--registry", str(reg), "--size", "2"]) == 0
    assert reg.read_text(encoding="utf-8") == json.dumps(jm.convert.pool_registry(POOL), indent=2) + "\n"
    assert out.exists() and not (tmp_path / "reg.json.part").exists()


@pytest.mark.parametrize("args", [
    ["--tolerance", "-1"], ["--tolerance", "nan"], ["--size", "0"], ["--size", "x"], ["--min-committee", "0"],
    ["--rubric-tokens", "-1"], ["--grade-tokens", "1.5"], ["--task-by", "judge"],
    ["--candidates", "Alpha-1,,Beta-2"], ["--candidates", "Nope-0"], ["--size", "9"],
    ["--answer-tokens", "reasoning"], ["--answer-tokens"],
    ["--registry", "OUT"], ["--registry", "OUT.part"],
])
def test_main_errors_exit_2_with_one_line_and_no_file(jm, tmp_path, folder, capsys, args):
    out = tmp_path / "out.jsonl"
    args = [str(out) + a[3:] if a.startswith("OUT") else a for a in args]
    assert jm.main(["--out", str(out)] + args) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ") and err.count("\n") == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data"]


def test_main_write_failure_keeps_an_existing_output(jm, tmp_path, folder, capsys, monkeypatch):
    out, reg = tmp_path / "out.jsonl", tmp_path / "reg.json"
    out.write_text("old\n", encoding="utf-8")

    def broken(rows, path):
        Path(path).write_text("partial", encoding="utf-8")
        raise OSError("disk full")
    monkeypatch.setattr(jm.convert, "write_jsonl", broken)
    assert jm.main(["--out", str(out), "--registry", str(reg), "--size", "2"]) == 2
    assert capsys.readouterr().err == "error: disk full\n"
    assert out.read_text(encoding="utf-8") == "old\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data", "out.jsonl"]


def test_main_registry_write_failure_writes_nothing(jm, tmp_path, folder, capsys, monkeypatch):
    out, reg = tmp_path / "out.jsonl", tmp_path / "reg.json"
    real = Path.write_text

    def write_text(self, *args, **kwargs):
        if self.name == "reg.json.part":
            real(self, "partial", encoding="utf-8")
            raise OSError("no space")
        return real(self, *args, **kwargs)
    monkeypatch.setattr(Path, "write_text", write_text)
    assert jm.main(["--out", str(out), "--registry", str(reg), "--size", "2"]) == 2
    assert capsys.readouterr().err == "error: no space\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data"]


class BrokenStdout:
    """A closed pipe: every write and flush raises."""

    def write(self, text):
        raise BrokenPipeError(32, "Broken pipe")

    def flush(self):
        raise BrokenPipeError(32, "Broken pipe")


class BufferedBrokenStdout(BrokenStdout):
    """A buffered closed pipe: the write is kept, so only the flush raises."""

    def write(self, text):
        return len(text)


@pytest.mark.parametrize("stdout", [BrokenStdout, BufferedBrokenStdout])
def test_main_failed_stdout_is_one_error_line_and_leaves_both_files(jm, tmp_path, folder, capsys, monkeypatch,
                                                                     stdout):
    out, reg = tmp_path / "out.jsonl", tmp_path / "reg.json"
    out.write_text("old\n")
    reg.write_text("old registry\n")
    monkeypatch.setattr("sys.stdout", stdout())
    assert jm.main(["--out", str(out), "--registry", str(reg), "--size", "2"]) == 2
    err = capsys.readouterr().err
    assert len(err.splitlines()) == 1 and err.startswith("error: ")
    assert out.read_text() == "old\n" and reg.read_text() == "old registry\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data", "out.jsonl", "reg.json"]


def test_main_second_rename_failure_leaves_out_renamed(jm, tmp_path, folder, capsys, monkeypatch):
    out, reg = tmp_path / "out.jsonl", tmp_path / "reg.json"
    real = Path.replace

    def replace(self, target):
        if Path(target).name == "reg.json":
            raise OSError("rename failed")
        return real(self, target)
    monkeypatch.setattr(Path, "replace", replace)
    assert jm.main(["--out", str(out), "--registry", str(reg), "--size", "2"]) == 2
    captured = capsys.readouterr()
    assert captured.err == "error: rename failed\n"
    rows, report = jm.judge_matrix(default_matrix(), POOL, size=2)
    # the report is printed before the renames (v1.94), so a failed rename is the one failure with it on stdout
    assert captured.out == json.dumps(report, indent=2) + "\n"
    assert out.read_text(encoding="utf-8") == "".join(json.dumps(r) + "\n" for r in rows)
    assert sorted(p.name for p in tmp_path.iterdir()) == ["data", "out.jsonl"]


def test_main_needs_out(jm, folder, capsys):
    assert jm.main([]) == 2
    assert capsys.readouterr().err.startswith("error: ")


# --- docs -----------------------------------------------------------------------------------------

# The evidence README's judge counts as written (DESIGN 12.11); test_pinned_readme_counts builds
# the same phrases from the report on the pinned files
README_JUDGE_COUNTS = [
    "707 of the 756 kept answers report some reasoning tokens, and their `reasoning_tokens` sum to 0.738 of their "
    "`output_tokens` "
    "(on 14 of them `reasoning_tokens` is above `output_tokens`, by at most 10%, so the two counts are not exact)",
    "the floor gives those 14 an answer of 0 tokens. By default the judges read 1,218,584 input tokens per "
    "candidate over the kept answers, 0.406 of the 3,001,074 that `--answer-tokens output` counts",
    "the five are `deepseek/deepseek-v4-flash-0731`, `google/gemma-4-31b-it`, `meta/muse-glimmer-30b`, "
    "`openai/gpt-5.6-luna` and `tencent/hy3`",
    "(1,191 at 4, 756 at 5, 460 at 6)",
    "Answers by a candidate: 1,252.",
    "In all, 2,478 answers carry a grade from their own answer model",
    "(not among that answer's judges, or a null grade): 2,925,",
    "Answers with too small a committee: 0",
    "The 107 unscored cells and the 388 rows outside the pool",
    "Kept: 756 of the 4,933 scored answers, 3,780 rows (one per candidate), mean success 0.735 over the rows."]


def test_evidence_readme_judge_section():
    text = EVIDENCE_README.read_text(encoding="utf-8")
    section = text.split("## Judge evidence: one item per graded answer\n", 1)[1]
    assert "](#judge-evidence-one-item-per-graded-answer)" in text.split("\n## ", 1)[0]
    for needle in [
            "python evidence/autobench-2026/judges.py --out autobench-judges.jsonl --registry autobench-models.json",
            "model-routing evaluate --outcomes autobench-judges.jsonl --registry autobench-models.json --bar 0.8\n",
            "like it is standard library only, so no extra is needed",
            "a judge outcome matrix in the format `model-routing evaluate` reads (DESIGN 12.11)",
            "not a human gold label", "scores 1.0 whether or not the committee is right",
            "never enters a committee", "Tolerance 0.5 on the 1 to 5 scale (`--tolerance`)", "no epsilon",
            "at least 3 judges (`--min-committee`)", "an estimate at the pool's list prices, never a billed cost",
            "an assumed 400-token rubric (`--rubric-tokens`)", "an assumed 200-token grade (`--grade-tokens`)",
            "by default the 5 pool judges (`--size`) whose set keeps the most answers",
            "ties to the set whose sorted display IDs come first", "`--candidates` names them instead",
            "never candidates, since they have no price", "in both halves", "`--task-by domain`",
            "Generator isolation", "a judge never reads the reasoning", "floored at 0",
            "`--answer-tokens output` counts the reasoning too, an upper bound", *README_JUDGE_COUNTS]:
        assert needle in section, needle
    assert f"within {jm_defaults()['tolerance']} of the mean of the other judges' grades" in section


def jm_defaults():
    module = load_jm()
    return {"tolerance": module.DEFAULT_TOLERANCE, "size": module.DEFAULT_SIZE,
            "min_committee": module.DEFAULT_MIN_COMMITTEE, "rubric_tokens": module.DEFAULT_RUBRIC_TOKENS,
            "grade_tokens": module.DEFAULT_GRADE_TOKENS, "answer_tokens": module.DEFAULT_ANSWER_TOKENS}


def test_evidence_readme_states_the_defaults():
    section = EVIDENCE_README.read_text(encoding="utf-8").split("## Judge evidence", 1)[1]
    d = jm_defaults()
    for needle in [f"Tolerance {d['tolerance']} ", f"at least {d['min_committee']} judges",
                   f"{d['rubric_tokens']}-token rubric", f"{d['grade_tokens']}-token grade",
                   f"by default the {d['size']} pool judges", f"so {d['size']} trades the number of judges",
                   f"(`--answer-tokens {d['answer_tokens']}`, the default)"]:
        assert needle in section, needle


# --- the pinned files, only when cached ------------------------------------------------------------

def cached_folder(jm):
    folder = jm.convert.default_cache_dir()
    for name, (size, _) in jm.convert.FILES.items():
        path = folder / name
        if not path.is_file() or path.stat().st_size != size:
            pytest.skip("pinned AutoBench files are not cached")
    return folder


PINNED_CANDIDATES = ["deepseek/deepseek-v4-flash-0731", "google/gemma-4-31b-it", "meta/muse-glimmer-30b",
                     "openai/gpt-5.6-luna", "tencent/hy3"]


def test_pinned_default_report(jm, tmp_path, capsys):
    folder = cached_folder(jm)
    out = tmp_path / "judges.jsonl"
    assert jm.main(["--out", str(out), "--cache", str(folder)]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["candidates"] == PINNED_CANDIDATES and report["candidates_by"] == "most_cells"
    assert report["scored_cells"] == 4933 and report["kept"] == {"all": 756}
    assert (report["dropped_self_graded"], report["dropped_missing_candidate"],
            report["dropped_small_committee"]) == (1252, 2925, 0)
    assert report["self_graded_cells"] == 2478 and report["unscored_cells"] == 107
    assert sum(report["dropped_out_of_pool"].values()) == 388 and len(report["dropped_out_of_pool"]) == 13
    assert report["rows"] == 3780 == len(out.read_text(encoding="utf-8").splitlines())


def test_pinned_rows_feed_the_evaluator(jm, tmp_path, capsys):
    folder = cached_folder(jm)
    out, reg = tmp_path / "judges.jsonl", tmp_path / "registry.json"
    assert jm.main(["--out", str(out), "--cache", str(folder), "--registry", str(reg),
                    "--candidates", ",".join(["Deepseek-v4-flash-0731", "Gemma-4-31b-it", "Hy3",
                                              "Muse-glimmer-30b", "Gpt-5.6-luna"])]) == 0
    capsys.readouterr()
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    outcomes = outcomes_from_rows(rows, Registry.load(reg))
    result = evaluate(outcomes, bars=[0.8], seeds=range(2))
    assert result["tasks"] == {"all": {"items": 756, "models": PINNED_CANDIDATES}}


def test_pinned_readme_counts(jm):
    folder = cached_folder(jm)
    pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
    matrix = jm.convert.read_csv(folder / "matrix.csv")
    rows, report = jm.judge_matrix(matrix, pool)
    names = jm.convert.pool_models(pool)
    items = {r["item"] for r in rows}
    kept = [r for r in matrix if r["model"] in names and f"{r['prompt_id']}|{names[r['model']]}" in items]
    assert len(kept) == sum(report["kept"].values()) == len(items)
    reasoning = [float(r["reasoning_tokens"] or 0) for r in kept]
    output = [float(r["output_tokens"]) for r in kept]
    over = [x / y for x, y in zip(reasoning, output) if x > y]
    assert over, "no kept answer reports more reasoning than output tokens: reword the README caveat"
    by_size = {k: sum(jm.judge_matrix(matrix, pool, size=k)[1]["kept"].values()) for k in (4, 6)}
    display = {v: k for k, v in names.items()}
    full = jm.judge_matrix(matrix, pool, candidates=[display[c] for c in report["candidates"]],
                           answer_tokens="output")[0]
    judge_input = {}
    for label, these in (("visible", rows), ("output", full)):
        per = {c: sum(r["input_tokens"] for r in these if r["model"] == c) for c in report["candidates"]}
        assert len(set(per.values())) == 1, per
        judge_input[label] = per[report["candidates"][0]]
    by_size[5] = sum(report["kept"].values())
    assert by_size[4] > by_size[5] > by_size[6]
    out = report["dropped_out_of_pool"]
    ids = [f"`{c}`" for c in report["candidates"]]
    built = [
        f"{sum(1 for x in reasoning if x > 0):,} of the {len(kept):,} kept answers report some reasoning tokens, "
        f"and their "
        f"`reasoning_tokens` sum to {math.fsum(reasoning) / math.fsum(output):.3f} of their `output_tokens` "
        f"(on {len(over)} of them `reasoning_tokens` is above `output_tokens`, by at most "
        f"{math.ceil(100 * (max(over) - 1))}%, so the two counts are not exact)",
        f"the floor gives those {len(over)} an answer of 0 tokens. By default the judges read "
        f"{judge_input['visible']:,} input tokens per candidate over the kept answers, "
        f"{judge_input['visible'] / judge_input['output']:.3f} of the {judge_input['output']:,} that "
        f"`--answer-tokens output` counts",
        f"the five are {', '.join(ids[:-1])} and {ids[-1]}",
        f"({by_size[4]:,} at 4, {by_size[5]:,} at 5, {by_size[6]:,} at 6)",
        f"Answers by a candidate: {report['dropped_self_graded']:,}.",
        f"In all, {report['self_graded_cells']:,} answers carry a grade from their own answer model",
        f"(not among that answer's judges, or a null grade): {report['dropped_missing_candidate']:,},",
        f"Answers with too small a committee: {report['dropped_small_committee']:,}",
        f"The {report['unscored_cells']:,} unscored cells and the {sum(out.values()):,} rows outside the pool",
        f"Kept: {sum(report['kept'].values()):,} of the {report['scored_cells']:,} scored answers, "
        f"{report['rows']:,} rows (one per candidate), mean success "
        f"{sum(r['correct'] for r in rows) / len(rows):.3f} over the rows."]
    assert built == README_JUDGE_COUNTS
