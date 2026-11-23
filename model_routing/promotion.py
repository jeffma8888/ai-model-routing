"""Paired promotion checks: a challenger route against the current one on the same items (DESIGN 4.7).

A route the Wilson bound admits may still do worse than the route it would replace on the same
items. `paired_promotion` compares the two routes' outcomes on the items both were graded on and
says `promote`, `hold` or `insufficient_overlap`. It is advisory: it changes no route, stats or
file, and it complements the task's bar, never replaces it.
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import NormalDist
from typing import Optional

PROMOTE = "promote"
HOLD = "hold"
INSUFFICIENT_OVERLAP = "insufficient_overlap"


@dataclass(frozen=True)
class PromotionCheck:
    """The outcome of `paired_promotion`, fields in DESIGN 4.7's order."""

    decision: str
    basis: Optional[str]
    pairs: int
    unpaired: int
    current_only: int
    challenger_only: int
    current_rate: Optional[float]
    challenger_rate: Optional[float]
    difference: Optional[float]
    p_value: Optional[float]
    lower_bound: Optional[float]
    margin: float
    cheaper: bool
    alpha: float
    min_pairs: int


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _outcomes(name: str, outcomes) -> Mapping:
    if not isinstance(outcomes, Mapping):
        raise ValueError(f"{name} must be a mapping of item ID to true or false, got {outcomes!r}")
    for item, outcome in outcomes.items():
        if not isinstance(item, str) or not item:
            raise ValueError(f"{name}: an item ID must be a non-empty string, got {item!r}")
        if type(outcome) is not bool:
            raise ValueError(f"{name}: the outcome of {item!r} must be true or false, got {outcome!r}")
    return outcomes


def _mcnemar_p(b: int, c: int) -> float:
    """The exact two-sided McNemar p of `b` and `c` discordant pairs, one integer division."""
    m = b + c
    tail = sum(math.comb(m, k) for k in range(min(b, c) + 1))
    return min(1.0, (2 * tail) / (2 ** m))


def _paired_lower_bound(b: int, c: int, n: int, alpha: float) -> float:
    """Lower limit of a two-sided 1 - alpha interval for the challenger's rate minus the current's.

    The Wald interval for paired outcomes with one added to each discordant count and two to the
    pairs (DESIGN 4.7), clipped at -1.0.
    """
    z = NormalDist().inv_cdf(1 - alpha / 2)
    bt = (b + 1) / (n + 2)
    ct = (c + 1) / (n + 2)
    return max(-1.0, (ct - bt) - z * math.sqrt((bt + ct - (ct - bt) ** 2) / (n + 2)))


def paired_promotion(current, challenger, *, margin, cheaper=False, alpha=0.05,
                     min_pairs=30) -> PromotionCheck:
    """Compare a challenger route with the current one on the items both were graded on.

    `current` and `challenger` map item ID to that route's outcome, True or False. The first rule
    that applies decides: fewer than `min_pairs` shared items gives `insufficient_overlap`; more
    challenger-only successes with an exact two-sided McNemar p at most `alpha` gives `promote`
    (basis `superior`); a `cheaper` challenger whose paired lower bound is over `-margin` gives
    `promote` (basis `non_inferior`); anything else gives `hold` (DESIGN 4.7).
    """
    _outcomes("current", current)
    _outcomes("challenger", challenger)
    if not _number(margin) or not math.isfinite(margin) or not 0 <= margin < 1:
        raise ValueError(f"margin must be a number in [0, 1), got {margin!r}")
    if type(cheaper) is not bool:
        raise ValueError(f"cheaper must be true or false, got {cheaper!r}")
    if not _number(alpha) or not 0 < alpha < 1:
        raise ValueError(f"alpha must be a number strictly between 0 and 1, got {alpha!r}")
    if not isinstance(min_pairs, int) or isinstance(min_pairs, bool) or min_pairs < 1:
        raise ValueError(f"min_pairs must be an integer of at least 1, got {min_pairs!r}")
    margin = float(margin)

    shared = [item for item in current if item in challenger]
    n = len(shared)
    unpaired = len(current) + len(challenger) - 2 * n
    both = sum(1 for item in shared if current[item] and challenger[item])
    b = sum(1 for item in shared if current[item] and not challenger[item])
    c = sum(1 for item in shared if challenger[item] and not current[item])

    if n < min_pairs:
        return PromotionCheck(INSUFFICIENT_OVERLAP, None, n, unpaired, b, c, None, None, None, None,
                              None, margin, cheaper, alpha, min_pairs)
    p_value = _mcnemar_p(b, c)
    lower = _paired_lower_bound(b, c, n, alpha)
    if c > b and p_value <= alpha:
        decision, basis = PROMOTE, "superior"
    elif cheaper and lower > -margin:
        decision, basis = PROMOTE, "non_inferior"
    else:
        decision, basis = HOLD, None
    return PromotionCheck(decision, basis, n, unpaired, b, c, (both + b) / n, (both + c) / n,
                          (c - b) / n, p_value, lower, margin, cheaper, alpha, min_pairs)
