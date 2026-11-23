"""Paired promotion checks: a challenger route against the current one on the same items (DESIGN 4.7).

A route the Wilson bound admits may still do worse than the route it would replace on the same
items. `paired_promotion` compares the two routes' outcomes on the items both were graded on and
says `promote`, `hold` or `insufficient_overlap`. It is advisory: it changes no route, stats or
file, and it complements the task's bar, never replaces it. `pair_outcomes` reads the two
mappings from outcome records as `calibrate --outcomes` writes them (v1.603).
"""

from __future__ import annotations

import math
from collections.abc import Mapping
from dataclasses import dataclass
from statistics import NormalDist
from typing import Optional

_PROMOTE = "promote"
_HOLD = "hold"
_INSUFFICIENT_OVERLAP = "insufficient_overlap"
_HEX = frozenset("0123456789abcdef")
_RECORD_KEYS = ("task", "slice", "route", "item", "correct", "dataset_sha256")


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


def _name(value) -> bool:
    return isinstance(value, str) and bool(value)


def _slice(value) -> bool:
    return value is None or (_name(value) and "@" not in value)


def _sha256(value) -> bool:
    return isinstance(value, str) and len(value) == 64 and set(value) <= _HEX


def _check_record(position: int, record) -> None:
    where = f"outcome record {position}"
    if not isinstance(record, Mapping):
        raise ValueError(f"{where} must be a mapping, got {record!r}")
    for key in _RECORD_KEYS:
        if key not in record:
            raise ValueError(f"{where} has no {key!r}")
    for key in ("task", "route", "item"):
        if not _name(record[key]):
            raise ValueError(f"{where}: {key} must be a non-empty string, got {record[key]!r}")
    if not _slice(record["slice"]):
        raise ValueError(f"{where}: slice must be null or a non-empty string without '@', "
                         f"got {record['slice']!r}")
    if type(record["correct"]) is not bool:
        raise ValueError(f"{where}: correct must be true or false, got {record['correct']!r}")
    if not _sha256(record["dataset_sha256"]):
        raise ValueError(f"{where}: dataset_sha256 must be 64 lowercase hexadecimal digits, "
                         f"got {record['dataset_sha256']!r}")


def pair_outcomes(records, *, task, current, challenger, slice=None, dataset_sha256=None):
    """The current route's and the challenger's outcome mappings on one labeled file, and its hash.

    `records` are outcome records as `item_outcomes` gives them. Every record and argument is
    checked first; a record is read when it is of `task`, of one of the two routes and, with a
    `slice`, of that slice. The records read must carry one hash between them, or `dataset_sha256`
    picks the ones that carry it; a route with none, two hashes and two disagreeing outcomes of
    one item raise `ValueError` (DESIGN 4.7 v1.603).
    """
    for key, value in (("task", task), ("current", current), ("challenger", challenger)):
        if not _name(value):
            raise ValueError(f"{key} must be a non-empty string, got {value!r}")
    if current == challenger:
        raise ValueError(f"current and challenger must differ, both are {current!r}")
    if not _slice(slice):
        raise ValueError(f"slice must be None or a non-empty string without '@', got {slice!r}")
    if dataset_sha256 is not None and not _sha256(dataset_sha256):
        raise ValueError("dataset_sha256 must be 64 lowercase hexadecimal digits, "
                         f"got {dataset_sha256!r}")
    records = list(records)
    for position, record in enumerate(records, start=1):
        _check_record(position, record)
    read = [r for r in records if r["task"] == task and r["route"] in (current, challenger)
            and (slice is None or r["slice"] == slice)]
    if dataset_sha256 is not None:
        read = [r for r in read if r["dataset_sha256"] == dataset_sha256]
    else:
        hashes = sorted({r["dataset_sha256"] for r in read})
        if len(hashes) > 1:
            raise ValueError(f"the outcomes of {current!r} and {challenger!r} on task {task!r} "
                             f"carry {len(hashes)} dataset hashes ({', '.join(hashes)}); "
                             "name one with dataset_sha256")
    where = f"task {task!r}" + ("" if slice is None else f" slice {slice!r}")
    mappings = []
    for route in (current, challenger):
        outcomes = {}
        for r in read:
            if r["route"] != route:
                continue
            seen = outcomes.setdefault(r["item"], r["correct"])
            if seen is not r["correct"]:
                raise ValueError(f"route {route!r} has conflicting outcomes for item "
                                 f"{r['item']!r} on task {task!r}")
        if not outcomes:
            raise ValueError(f"route {route!r} has no outcome on {where}"
                             + ("" if dataset_sha256 is None
                                else f" with dataset_sha256 {dataset_sha256}"))
        mappings.append(outcomes)
    return mappings[0], mappings[1], read[0]["dataset_sha256"]


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
        return PromotionCheck(_INSUFFICIENT_OVERLAP, None, n, unpaired, b, c, None, None, None, None,
                              None, margin, cheaper, alpha, min_pairs)
    p_value = _mcnemar_p(b, c)
    lower = _paired_lower_bound(b, c, n, alpha)
    if c > b and p_value <= alpha:
        decision, basis = _PROMOTE, "superior"
    elif cheaper and lower > -margin:
        decision, basis = _PROMOTE, "non_inferior"
    else:
        decision, basis = _HOLD, None
    return PromotionCheck(decision, basis, n, unpaired, b, c, (both + b) / n, (both + c) / n,
                          (c - b) / n, p_value, lower, margin, cheaper, alpha, min_pairs)
