"""DESIGN 4.3 and 10, v1.140: `items_needed`, the labelled calibration items a model needs
on a task before its Wilson lower bound clears the bar at a given success rate, and the
`plan` subcommand that prints it."""

import math
from fractions import Fraction
from statistics import NormalDist

import pytest

import model_routing
from model_routing import main, wilson_lower_bound

def needed(*args, **kwargs):
    from model_routing import items_needed
    return items_needed(*args, **kwargs)


def by_definition(success, bar, confidence, top):
    """4.3 read literally: the smallest n whose every count from n to top clears, or None."""
    s = Fraction(repr(float(success)))
    clears = [wilson_lower_bound(math.floor(n * s), n, confidence) >= bar
              for n in range(1, top + 1)]
    return next((n for n in range(1, top + 1) if all(clears[n - 1:])), None)


def test_items_needed_is_public_and_lives_in_stats():
    from model_routing import items_needed, stats
    assert "items_needed" in model_routing.__all__
    assert items_needed is stats.items_needed


def test_every_item_right_needs_nine_z_squared_at_bar_0_9():
    # p = 1 makes the Wilson lower bound n / (n + z*z), which is >= 0.9 from n >= 9 z*z
    z = NormalDist().inv_cdf(0.975)
    assert 34 < 9 * z * z < 35
    assert round(35 / (35 + z * z), 6) == 0.901099
    assert round(34 / (34 + z * z), 6) == 0.898485
    assert needed(1.0, 0.9) == 35
    assert needed(1, 0.9) == 35
    assert needed(1.0, 0.9, max_items=35) == 35
    assert needed(1.0, 0.9, max_items=34) is None


def test_a_smaller_count_can_clear_where_a_larger_one_does_not():
    # floor(0.9 n) is 61 at 68, 65 at 73 (65.7) and 66 at 74 (66.6)
    assert [math.floor(Fraction("0.9") * n) for n in (68, 73, 74)] == [61, 65, 66]
    assert round(wilson_lower_bound(61, 68), 6) == 0.802421
    assert round(wilson_lower_bound(65, 73), 6) == 0.798374
    assert round(wilson_lower_bound(66, 74), 6) == 0.800912
    assert needed(0.9, 0.8) == 74
    assert all(wilson_lower_bound(math.floor(Fraction("0.9") * n), n) >= 0.8
               for n in range(74, 10_001))


class _Rate(float):
    """A float subclass whose repr is not a bare decimal, as numpy 2's np.float64 is."""

    def __repr__(self):
        return f"_Rate({float.__repr__(self)})"


def test_a_float_subclass_reads_as_its_float():
    assert repr(_Rate(0.9)) == "_Rate(0.9)"
    assert needed(_Rate(0.9), 0.8) == 74
    assert needed(_Rate(0.29), 0.205, max_items=100) == 100


def test_successes_are_the_floor_of_the_exact_decimal():
    # floating 0.29 * 100 is 28.999999999999996, so a float floor would count 28
    assert math.floor(0.29 * 100) == 28
    assert wilson_lower_bound(29, 100) >= 0.205 > wilson_lower_bound(28, 100)
    assert wilson_lower_bound(28, 99) < 0.205
    assert needed(0.29, 0.205, max_items=100) == 100


def test_the_limit_decides_none_near_the_bar():
    assert needed(0.81, 0.8) == 6338
    assert round(wilson_lower_bound(5133, 6338), 6) == 0.80003
    assert wilson_lower_bound(5132, 6337) < 0.8
    assert needed(0.81, 0.8, max_items=6337) is None
    assert needed(0.81, 0.8, max_items=6338) == 6338


@pytest.mark.parametrize("success, bar", [(0.8, 0.8), (0.7, 0.8), (1.0, 1.0), (0.0, 0.5),
                                          (0.5, 1.0)])
def test_no_count_clears_at_or_below_the_bar(success, bar):
    assert needed(success, bar) is None


@pytest.mark.parametrize("success", [0.0, 0.5, 1.0])
def test_bar_zero_needs_one_item(success):
    assert needed(success, 0.0) == 1
    assert needed(success, 0) == 1


def test_confidence_and_other_values():
    assert needed(0.9, 0.8, confidence=0.9) == 55
    assert needed(0.95, 0.8) == 33
    assert needed(0.9, 0.7) == 25
    assert needed(0.85, 0.8) == 276


@pytest.mark.parametrize("success, bar, confidence", [
    (0.9, 0.8, 0.95), (0.9, 0.8, 0.9), (0.95, 0.9, 0.95), (0.8, 0.7, 0.8), (0.6, 0.5, 0.95),
    (1.0, 0.95, 0.95), (0.73, 0.6, 0.99), (0.5, 0.5, 0.95), (0.3, 0.0, 0.95)])
def test_matches_the_definition_up_to_300(success, bar, confidence):
    assert needed(success, bar, confidence=confidence, max_items=300) == \
        by_definition(success, bar, confidence, 300)


@pytest.mark.parametrize("kwargs", [
    {"success": True}, {"success": "0.9"}, {"success": None}, {"success": float("nan")},
    {"success": float("inf")}, {"success": -0.1}, {"success": 1.1},
    {"bar": False}, {"bar": "0.8"}, {"bar": float("nan")}, {"bar": -0.01}, {"bar": 1.01},
    {"confidence": True}, {"confidence": 0}, {"confidence": 1}, {"confidence": 1.0},
    {"confidence": -0.5}, {"confidence": float("nan")}, {"confidence": "0.95"},
    {"max_items": 0}, {"max_items": -5}, {"max_items": True}, {"max_items": 10.0},
    {"max_items": "100"}, {"max_items": None}])
def test_argument_errors(kwargs):
    args = {"success": 0.9, "bar": 0.8, "confidence": 0.95, "max_items": 100}
    args.update(kwargs)
    with pytest.raises(ValueError):
        needed(**args)


def test_plan_prints_the_count_successes_and_bound(capsys):
    assert main(["plan", "--success", "0.9", "--bar", "0.8"]) == 0
    captured = capsys.readouterr()
    assert captured.out.split("\n") == [
        "success:     0.9",
        "bar:         0.8",
        "confidence:  0.95",
        "items:       74",
        "successes:   66",
        "lower_bound: 0.800912",
        "",
    ]
    assert captured.err == ""


def test_plan_options(capsys):
    assert main(["plan", "--success", "0.90", "--bar", "0.8", "--confidence", "0.9",
                 "--max-items", "500"]) == 0
    out = capsys.readouterr().out.split("\n")
    assert out[:5] == ["success:     0.9", "bar:         0.8", "confidence:  0.9",
                       "items:       55", "successes:   49"]
    assert out[5] == f"lower_bound: {wilson_lower_bound(49, 55, 0.9):.6f}"


@pytest.mark.parametrize("argv, limit", [
    (["--success", "0.8", "--bar", "0.8"], 10000),
    (["--success", "0.9", "--bar", "0.8", "--max-items", "73"], 73)])
def test_plan_exits_3_when_no_count_clears(capsys, argv, limit):
    assert main(["plan", *argv]) == 3
    captured = capsys.readouterr()
    lines = captured.out.split("\n")
    assert lines[3:] == [f"items:       none up to --max-items {limit}", ""]
    assert lines[0] == f"success:     {float(argv[1])}"
    assert captured.err == ""


@pytest.mark.parametrize("argv, named", [
    (["--success", "1.5", "--bar", "0.8"], "success"),
    (["--success", "nan", "--bar", "0.8"], "success"),
    (["--success", "0.9", "--bar", "-1"], "bar"),
    (["--success", "0.9", "--bar", "0.8", "--confidence", "1"], "confidence"),
    (["--success", "0.9", "--bar", "0.8", "--max-items", "0"], "max_items"),
    (["--success", "0.9", "--bar", "0.8", "--max-items", "ten"], "--max-items"),
    (["--success", "0.9"], "--bar"),
    (["--bar", "0.8"], "--success")])
def test_plan_bad_input_exits_2_with_one_error_line(capsys, argv, named):
    assert main(["plan", *argv]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    errors = [line for line in captured.err.split("\n") if line.startswith("error: ")]
    assert len(errors) == 1
    assert "invalid choice" not in errors[0] and named in errors[0]
