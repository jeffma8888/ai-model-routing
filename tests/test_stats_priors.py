"""Statistical confidence, calibration, persistence, and prior ordering."""

import json
from statistics import NormalDist
from math import sqrt

import pytest
from model_routing import Stats, Priors, calibrate_from_results, wilson_lower_bound


@pytest.mark.parametrize("successes,trials,expected", [
    (27, 30, 0.743789), (45, 50, 0.786398), (90, 100, 0.825634),
    (170, 200, 0.793944), (10, 10, 0.722467), (0, 10, 0.0),
])
def test_wilson_matches_six_pinned_reference_values(successes, trials, expected):
    assert wilson_lower_bound(successes, trials) == pytest.approx(expected, abs=1e-6)


def test_wilson_zero_trials_and_zero_successes_return_zero():
    assert wilson_lower_bound(0, 0) == 0.0
    assert wilson_lower_bound(0, 100) == pytest.approx(0.0, abs=1e-14)
    assert wilson_lower_bound(0, 100) >= 0.0


@pytest.mark.parametrize("successes,trials", [(-1, 10), (0, -1), (11, 10), (1, 0)])
def test_wilson_invalid_counts_raise_valueerror(successes, trials):
    with pytest.raises(ValueError):
        wilson_lower_bound(successes, trials)


def test_wilson_uses_two_sided_configured_confidence():
    p, n = 0.8, 20
    z = NormalDist().inv_cdf(0.9)
    expected = (p + z*z/(2*n) - z*sqrt(p*(1-p)/n + z*z/(4*n*n))) / (1+z*z/n)
    assert wilson_lower_bound(16, 20, confidence=0.8) == pytest.approx(expected)
    assert wilson_lower_bound(16, 20, 0.99) < wilson_lower_bound(16, 20, 0.8)


def test_stats_get_default_and_add_accumulate_without_cross_key_leakage():
    stats = Stats()
    assert stats.get("judge", "fiction/a") == (0, 0)
    stats.add("judge", "fiction/a", 2, 3)
    stats.add("judge", "fiction/a", 4, 5)
    stats.add("other", "fiction/a", 1, 1)
    stats.add("judge", "fiction/b", 0, 2)
    assert stats.get("judge", "fiction/a") == (6, 8)
    assert stats.get("other", "fiction/a") == (1, 1)
    assert stats.get("judge", "fiction/b") == (0, 2)
    stats.add("judge", "fiction/a", 0, 0)
    assert stats.get("judge", "fiction/a") == (6, 8)


@pytest.mark.parametrize("successes,trials", [(-1, 2), (0, -1), (3, 2), (1, 0)])
def test_stats_add_rejects_invalid_increment_even_if_total_would_be_valid(successes, trials):
    stats = Stats()
    stats.add("judge", "fiction/a", 5, 10)
    with pytest.raises(ValueError):
        stats.add("judge", "fiction/a", successes, trials)
    assert stats.get("judge", "fiction/a") == (5, 10)


def test_stats_merge_returns_new_sum_without_mutating_either_operand():
    left, right = Stats(), Stats()
    left.add("judge", "fiction/a", 2, 3)
    right.add("judge", "fiction/a", 4, 5)
    right.add("judge", "fiction/b", 1, 2)
    merged = left.merge(right)
    assert merged is not left and merged is not right
    assert merged.get("judge", "fiction/a") == (6, 8)
    assert merged.get("judge", "fiction/b") == (1, 2)
    assert left.get("judge", "fiction/a") == (2, 3)
    assert left.get("judge", "fiction/b") == (0, 0)
    assert right.get("judge", "fiction/a") == (4, 5)
    merged.add("judge", "fiction/a", 1, 1)
    assert left.get("judge", "fiction/a") == (2, 3)
    assert right.get("judge", "fiction/a") == (4, 5)


def test_stats_save_sorted_schema_and_load_round_trip(tmp_path):
    stats = Stats()
    stats.add("z-task", "fiction/a", 1, 2)
    stats.add("a-task", "fiction/z", 2, 3)
    stats.add("a-task", "fiction/a", 3, 4)
    path = tmp_path / "stats.json"
    stats.save(path)
    expected = [
        {"task": "a-task", "model": "fiction/a", "successes": 3, "trials": 4},
        {"task": "a-task", "model": "fiction/z", "successes": 2, "trials": 3},
        {"task": "z-task", "model": "fiction/a", "successes": 1, "trials": 2},
    ]
    assert json.loads(path.read_text()) == {"stats": expected}
    loaded = Stats.load(path)
    for row in expected:
        assert loaded.get(row["task"], row["model"]) == (row["successes"], row["trials"])
    loaded.save(tmp_path / "again.json")
    assert json.loads((tmp_path / "again.json").read_text()) == {"stats": expected}


def test_stats_empty_round_trip(tmp_path):
    path = tmp_path / "empty.json"
    Stats().save(path)
    assert json.loads(path.read_text()) == {"stats": []}
    assert Stats.load(path).get("x", "y") == (0, 0)


def test_calibration_accepts_both_row_shapes_and_python_equality():
    rows = [
        {"task": "judge", "model": "fiction/a", "correct": True},
        {"task": "judge", "model": "fiction/a", "correct": False},
        {"task": "judge", "model": "fiction/a", "prediction": {"x": [1]}, "gold": {"x": [1]}},
        {"task": "judge", "model": "fiction/a", "prediction": "1", "gold": 1},
        {"task": "other", "model": "fiction/b", "prediction": 1, "gold": True},
    ]
    stats = calibrate_from_results(iter(rows))
    assert stats.get("judge", "fiction/a") == (2, 4)
    assert stats.get("other", "fiction/b") == (1, 1)


@pytest.mark.parametrize("extra", [{}, {"prediction": 1}, {"gold": 1}])
def test_calibration_row_without_complete_result_raises_valueerror(extra):
    with pytest.raises(ValueError):
        calibrate_from_results([dict(task="judge", model="fiction/a", **extra)])


def test_calibration_empty_iterable_returns_empty_stats():
    assert calibrate_from_results([]).get("judge", "fiction/a") == (0, 0)


def test_priors_score_unknowns_and_rank_descending_with_id_tiebreak(priors):
    assert priors.score("judging", "fiction/cheap") == 80
    assert priors.score("missing", "fiction/cheap") is None
    assert priors.score("judging", "fiction/missing") is None
    assert priors.ranked("judging") == ["fiction/best", "fiction/mid", "fiction/cheap"]


def test_priors_load_category_metadata_and_scores(write_json, prior_categories):
    loaded = Priors.load(write_json("priors.json", {"categories": prior_categories}))
    assert loaded.score("judging", "fiction/best") == 90
    assert loaded.ranked("judging") == ["fiction/best", "fiction/mid", "fiction/cheap"]
