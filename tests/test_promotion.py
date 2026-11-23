"""The paired promotion check (DESIGN 4.7 v1.601, row GATE1a).

`paired_promotion` compares a challenger route with the current one on the items both were
graded on. The expected p-values below are the exact two-sided McNemar values computed here
with `fractions.Fraction` from `math.comb`, and the bounds the adjusted paired Wald limit of
4.7 computed by hand in each test; a bound's last bits may differ by platform (4.7), so bounds
are compared with `pytest.approx`.
"""

import math
from dataclasses import FrozenInstanceError, fields
from fractions import Fraction
from pathlib import Path
from statistics import NormalDist

import pytest

import model_routing
from model_routing import PromotionCheck, paired_promotion

ROOT = Path(__file__).resolve().parent.parent
Z = NormalDist().inv_cdf(0.975)


def pairs(both=0, current_only=0, challenger_only=0, neither=0, start=0):
    """Two outcome mappings over the same items, with the four counts of a 2x2 table."""
    current, challenger = {}, {}
    k = start
    for count, cur, cha in ((both, True, True), (current_only, True, False),
                            (challenger_only, False, True), (neither, False, False)):
        for _ in range(count):
            current[f"item-{k}"] = cur
            challenger[f"item-{k}"] = cha
            k += 1
    return current, challenger


def exact_p(b, c):
    m = b + c
    tail = sum(math.comb(m, k) for k in range(min(b, c) + 1))
    return float(min(Fraction(1), Fraction(2 * tail, 2 ** m)))


def hand_bound(b, c, n, z=Z):
    bt = (b + 1) / (n + 2)
    ct = (c + 1) / (n + 2)
    return max(-1.0, (ct - bt) - z * math.sqrt((bt + ct - (ct - bt) ** 2) / (n + 2)))


# --- the four cases of the row ------------------------------------------------------------

def test_a_clear_win_promotes_as_superior():
    current, challenger = pairs(both=150, current_only=5, challenger_only=25, neither=20)
    check = paired_promotion(current, challenger, margin=0.02)
    assert check.decision == "promote"
    assert check.basis == "superior"
    assert (check.pairs, check.unpaired, check.current_only, check.challenger_only) == (200, 0, 5, 25)
    assert check.current_rate == 155 / 200
    assert check.challenger_rate == 175 / 200
    assert check.difference == 20 / 200
    # T = 1 + 30 + 435 + 4060 + 27405 + 142506 = 174437 over 2**30
    assert check.p_value == 348874 / 1073741824
    assert check.p_value == exact_p(5, 25)
    assert check.lower_bound == pytest.approx(0.04584798397747727, rel=1e-12)


def test_a_cheaper_challenger_within_the_margin_promotes_as_non_inferior():
    current, challenger = pairs(both=360, current_only=6, challenger_only=4, neither=30)
    check = paired_promotion(current, challenger, margin=0.03, cheaper=True)
    assert check.decision == "promote"
    assert check.basis == "non_inferior"
    assert check.difference == -2 / 400
    assert check.p_value == 772 / 1024
    # bt = 7/402, ct = 5/402: -2/402 - 1.96 * sqrt((12/402 - (2/402)**2) / 402)
    assert check.lower_bound == pytest.approx(-0.021857460026894066, rel=1e-12)
    assert check.lower_bound > -0.03


def test_the_same_challenger_holds_when_not_cheaper_or_the_margin_is_tighter():
    current, challenger = pairs(both=360, current_only=6, challenger_only=4, neither=30)
    assert paired_promotion(current, challenger, margin=0.03).decision == "hold"
    tight = paired_promotion(current, challenger, margin=0.02, cheaper=True)
    assert (tight.decision, tight.basis) == ("hold", None)
    assert tight.lower_bound < -0.02


def test_a_low_power_tie_holds_even_for_a_cheaper_challenger():
    current, challenger = pairs(both=20, current_only=2, challenger_only=2, neither=6)
    check = paired_promotion(current, challenger, margin=0.05, cheaper=True)
    assert (check.decision, check.basis) == ("hold", None)
    assert check.pairs == 30
    assert check.p_value == 1.0
    assert check.difference == 0.0
    # bt = ct = 3/32: -1.96 * sqrt((6/32) / 32)
    assert check.lower_bound == pytest.approx(-Z * math.sqrt((6 / 32) / 32), rel=1e-12)
    assert check.lower_bound == pytest.approx(-0.15002848988610337, rel=1e-12)


def test_too_few_pairs_is_insufficient_overlap_with_no_statistics():
    current, challenger = pairs(both=0, current_only=0, challenger_only=29)
    current["only-current"] = True
    challenger["only-challenger-1"] = False
    challenger["only-challenger-2"] = True
    check = paired_promotion(current, challenger, margin=0.05, cheaper=True)
    assert check.decision == "insufficient_overlap"
    assert check.basis is None
    assert (check.pairs, check.unpaired, check.current_only, check.challenger_only) == (29, 3, 0, 29)
    assert (check.current_rate, check.challenger_rate, check.difference,
            check.p_value, check.lower_bound) == (None, None, None, None, None)


def test_no_shared_item_at_all_is_insufficient_overlap():
    check = paired_promotion({"a": True}, {"b": True}, margin=0.0, min_pairs=1)
    assert (check.decision, check.pairs, check.unpaired) == ("insufficient_overlap", 0, 2)
    empty = paired_promotion({}, {}, margin=0.0)
    assert (empty.decision, empty.pairs, empty.unpaired) == ("insufficient_overlap", 0, 0)


# --- the rules one at a time ---------------------------------------------------------------

def test_the_p_value_boundary_is_at_most_alpha():
    six = paired_promotion(*pairs(both=20, challenger_only=6, neither=4), margin=0.0)
    assert six.p_value == 2 / 64
    assert (six.decision, six.basis) == ("promote", "superior")
    five = paired_promotion(*pairs(both=20, challenger_only=5, neither=5), margin=0.0)
    assert five.p_value == 2 / 32
    assert five.decision == "hold"
    exactly = paired_promotion(*pairs(both=20, challenger_only=5, neither=5), margin=0.0, alpha=0.0625)
    assert exactly.p_value == exactly.alpha == 0.0625
    assert (exactly.decision, exactly.basis) == ("promote", "superior")


def test_a_significant_loss_never_promotes():
    current, challenger = pairs(both=20, current_only=6, neither=4)
    check = paired_promotion(current, challenger, margin=0.0)
    assert check.p_value == 2 / 64
    assert check.decision == "hold"
    assert check.lower_bound == pytest.approx(hand_bound(6, 0, 30), rel=1e-12)
    assert paired_promotion(current, challenger, margin=0.3, cheaper=True).decision == "hold"


def test_superior_wins_over_non_inferior_when_both_hold():
    current, challenger = pairs(both=150, current_only=5, challenger_only=25, neither=20)
    check = paired_promotion(current, challenger, margin=0.05, cheaper=True)
    assert (check.decision, check.basis) == ("promote", "superior")


def test_a_cheaper_challenger_not_significant_promotes_on_the_bound_alone():
    current, challenger = pairs(both=20, challenger_only=5, neither=5)
    check = paired_promotion(current, challenger, margin=0.0, cheaper=True)
    assert check.p_value == 2 / 32
    assert check.lower_bound == pytest.approx(0.0035110988803895293, rel=1e-12)
    assert (check.decision, check.basis) == ("promote", "non_inferior")


def test_the_bound_must_clear_the_margin_strictly():
    current, challenger = pairs(both=20, current_only=2, challenger_only=2, neither=6)
    bound = paired_promotion(current, challenger, margin=0.0).lower_bound
    assert paired_promotion(current, challenger, margin=-bound, cheaper=True).decision == "hold"
    nudged = math.nextafter(-bound, 1.0)
    assert paired_promotion(current, challenger, margin=nudged, cheaper=True).decision == "promote"


def test_min_pairs_and_alpha_move_the_rules():
    current, challenger = pairs(both=8, challenger_only=6)
    assert paired_promotion(current, challenger, margin=0.0).decision == "insufficient_overlap"
    small = paired_promotion(current, challenger, margin=0.0, min_pairs=14)
    assert (small.decision, small.min_pairs) == ("promote", 14)
    strict = paired_promotion(current, challenger, margin=0.0, min_pairs=14, alpha=0.01)
    assert strict.decision == "hold"
    z99 = NormalDist().inv_cdf(1 - 0.01 / 2)
    assert strict.lower_bound == pytest.approx(hand_bound(0, 6, 14, z=z99), rel=1e-12)


def test_unpaired_items_change_nothing_but_their_count():
    current, challenger = pairs(both=150, current_only=5, challenger_only=25, neither=20)
    base = paired_promotion(current, challenger, margin=0.02)
    current.update({f"extra-{k}": False for k in range(40)})
    challenger.update({f"other-{k}": True for k in range(7)})
    more = paired_promotion(current, challenger, margin=0.02)
    assert more.unpaired == 47
    assert [getattr(more, f.name) for f in fields(more) if f.name != "unpaired"] == \
           [getattr(base, f.name) for f in fields(base) if f.name != "unpaired"]


def test_the_p_value_is_exact_at_large_counts():
    for b, c in ((500, 600), (0, 1100), (700, 700), (1, 2000)):
        current, challenger = pairs(current_only=b, challenger_only=c)
        check = paired_promotion(current, challenger, margin=0.0, min_pairs=1)
        assert check.p_value == exact_p(b, c), (b, c)
    assert exact_p(500, 600) == pytest.approx(0.0028195449914364275, rel=1e-12)
    assert exact_p(700, 700) == 1.0


@pytest.mark.parametrize("b,c,n", [(5, 25, 200), (6, 4, 400), (0, 0, 30), (3, 12, 60), (40, 0, 40)])
def test_the_bound_is_the_adjusted_paired_wald_limit(b, c, n):
    current, challenger = pairs(both=n - b - c - (n - b - c) // 2, current_only=b, challenger_only=c,
                                neither=(n - b - c) // 2)
    check = paired_promotion(current, challenger, margin=0.0)
    assert check.pairs == n
    assert check.lower_bound == pytest.approx(hand_bound(b, c, n), rel=1e-12)
    assert check.lower_bound >= -1.0


def test_the_bound_is_clipped_at_minus_one():
    current, challenger = pairs(current_only=1)
    check = paired_promotion(current, challenger, margin=0.0, min_pairs=1, alpha=1e-12)
    assert check.lower_bound == -1.0


def test_the_inputs_are_not_changed_and_the_result_is_frozen():
    current, challenger = pairs(both=150, current_only=5, challenger_only=25, neither=20)
    before = (dict(current), dict(challenger))
    check = paired_promotion(current, challenger, margin=0.02)
    assert (current, challenger) == before
    with pytest.raises(FrozenInstanceError):
        check.decision = "hold"


def test_the_fields_are_in_the_spec_order_and_echo_the_arguments():
    assert [f.name for f in fields(PromotionCheck)] == [
        "decision", "basis", "pairs", "unpaired", "current_only", "challenger_only",
        "current_rate", "challenger_rate", "difference", "p_value", "lower_bound",
        "margin", "cheaper", "alpha", "min_pairs"]
    check = paired_promotion(*pairs(both=30), margin=0, cheaper=True, alpha=0.1, min_pairs=30)
    assert (check.margin, check.cheaper, check.alpha, check.min_pairs) == (0.0, True, 0.1, 30)
    assert type(check.margin) is float


# --- the checks -----------------------------------------------------------------------------

GOOD = pairs(both=30)


@pytest.mark.parametrize("current", [None, [("a", True)], "a", 3])
def test_a_mapping_is_required(current):
    with pytest.raises(ValueError):
        paired_promotion(current, GOOD[1], margin=0.0)
    with pytest.raises(ValueError):
        paired_promotion(GOOD[0], current, margin=0.0)


@pytest.mark.parametrize("key", ["", 7, None, ("a",)])
def test_an_item_id_is_a_non_empty_string(key):
    bad = dict(GOOD[1])
    bad[key] = True
    with pytest.raises(ValueError):
        paired_promotion(GOOD[0], bad, margin=0.0)


@pytest.mark.parametrize("value", [1, 0, None, "true", 1.0])
def test_an_outcome_is_a_real_bool_even_on_an_unpaired_item(value):
    bad = dict(GOOD[0])
    bad["unpaired-item"] = value
    with pytest.raises(ValueError):
        paired_promotion(bad, GOOD[1], margin=0.0)


@pytest.mark.parametrize("margin", [True, False, -0.01, 1.0, 1, float("nan"), float("inf"), "0.02", None])
def test_a_bad_margin_raises(margin):
    with pytest.raises(ValueError):
        paired_promotion(*GOOD, margin=margin)


def test_the_margin_is_required():
    with pytest.raises(TypeError):
        paired_promotion(*GOOD)


@pytest.mark.parametrize("cheaper", [1, 0, None, "yes"])
def test_a_bad_cheaper_raises(cheaper):
    with pytest.raises(ValueError):
        paired_promotion(*GOOD, margin=0.0, cheaper=cheaper)


@pytest.mark.parametrize("alpha", [0, 1, 0.0, 1.0, -0.05, 1.5, True, float("nan"), "0.05", None])
def test_a_bad_alpha_raises(alpha):
    with pytest.raises(ValueError):
        paired_promotion(*GOOD, margin=0.0, alpha=alpha)


@pytest.mark.parametrize("min_pairs", [0, -1, True, 30.0, "30", None])
def test_a_bad_min_pairs_raises(min_pairs):
    with pytest.raises(ValueError):
        paired_promotion(*GOOD, margin=0.0, min_pairs=min_pairs)


def test_the_two_routes_are_positional_and_the_rest_keyword_only():
    with pytest.raises(TypeError):
        paired_promotion(GOOD[0], GOOD[1], 0.02)


# --- exports and spec ------------------------------------------------------------------------

def test_the_exports_follow_billing_bound():
    names = model_routing.__all__
    at = names.index("billing_bound")
    assert names[at + 1:at + 3] == ["paired_promotion", "PromotionCheck"]
    assert model_routing.promotion.__file__ == str(ROOT / "model_routing" / "promotion.py")
    assert model_routing.paired_promotion is model_routing.promotion.paired_promotion


def test_design_specifies_the_check_and_defers_the_rest_of_gate1():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert text.count("### 4.7 Promotion checks (`promotion.py`, v1.601, row GATE1a)") == 1
    layout = text[text.index("## 3. "):text.index("## 4. ")]
    assert "  promotion.py    paired_promotion, PromotionCheck (v1.601, 4.7), pair_outcomes (v1.603, 4.7)" in layout
    seven = text[text.index("### 4.7 Promotion checks"):text.index("## 5. ")]
    assert "`paired_promotion(current, challenger, *, margin, cheaper=False, alpha=0.05, min_pairs=30) -> PromotionCheck`" in seven
    assert "`min(1.0, 2 * T / 2 ** (b + c))`" in seven
    assert "`max(-1.0, (ct - bt) - z * math.sqrt((bt + ct - (ct - bt) ** 2) / (n + 2)))`" in seven
    assert "- `model_routing.__all__` gains `paired_promotion` and `PromotionCheck`, after `billing_bound`." in seven
    assert "(row GATE1b)" in seven and "(row GATE1c)" in seven and "(row GATE1d)" in seven
    assert "Both rules are one-sided at `alpha / 2` (review iter-449 should-fix 2): " in seven
    assert "`alpha` is not the false-promotion rate of several checks of one route (row GATE1c)." in seven


def test_the_changelog_line_names_the_row():
    last = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in last if line.startswith("- v1.601 (2026-11-23): ")]
    assert len(mine) == 1
    assert "(3, 4.7, row GATE1a)" in mine[0]


def test_the_note_names_the_check_as_shipped():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    locked = note[note.index("### Switch models only on locked data and a significant result"):]
    line = [x for x in locked.splitlines() if x.startswith("- In this library: ")][0]
    assert "From v1.601 `paired_promotion` compares a challenger with the current route on the items both were graded on" in line
    assert "The change still planned" not in line  # restated at v1.603, row GATE1c: the command ships
    assert "an advisory paired check of a challenger" not in note
    assert ", `hold` otherwise or `insufficient_overlap` on too few shared items, and changes nothing. " in line
    # v1.605 (row GATE1d, review iter-454 must-fix 1): the GitHub line names the paired check as shipped, not
    # among its changes (tests/test_promote_docs.py)
    assert note.count("by `paired_promotion` (v1.601), after the bar admits the challenger, ") == 1
    layout = (ROOT / "README.md").read_text(encoding="utf-8")
    assert layout.count("\n  promotion.py  a challenger route against the current one on the same items (advisory)\n") == 1


def test_the_module_adds_no_public_name_but_the_three_exports():
    public = sorted(name for name in vars(model_routing.promotion)
                    if not name.startswith("_") and name not in {"annotations", "math", "Mapping", "dataclass",
                                                                  "NormalDist", "Optional"})
    assert public == ["PromotionCheck", "pair_outcomes", "paired_promotion"]  # pair_outcomes v1.603
