"""Offline evidence for the inline-or-sub-agent decision on a public outcome matrix (DESIGN 13.9).

No public dataset records inline-versus-sub-agent outcomes, so this combines what
a matrix does measure (each model's acceptance and token counts on each item)
with a stated grid of what it does not (the parent's context and the hand-off
sizes). The decision comes from ``Router.decide_delegation`` on calibration-half
stats, and each held-out item is costed at list price from its own tokens.
"""

from __future__ import annotations

import statistics
from math import fsum
from typing import Dict, List, Optional, Sequence, Tuple

from .evaluate import _check_run_options, _is_int, split_items
from .registry import Registry
from .router import NoModelClearsBar, Router
from .stats import Stats
from .tasks import Task

POINT_KEYS = ("context_tokens", "brief_tokens", "result_tokens", "carry_turns",
              "inline_separate_call")
STRATEGIES = ("decision", "inline", "delegate")

# (correct, input_tokens, output_tokens) of one model's row for one item
Row = Tuple[bool, int, int]


def _row(row) -> Tuple[str, str, str, Row]:
    if not isinstance(row, dict):
        raise ValueError(f"outcome row must be an object, got {row!r}")
    for key in ("task", "item", "model"):
        if not isinstance(row.get(key), str) or not row.get(key):
            raise ValueError(f"outcome row needs a non-empty string {key!r}: {row!r}")
    if "correct" not in row or type(row["correct"]) is not bool:
        raise ValueError(f"'correct' must be true or false: {row!r}")
    for key in ("input_tokens", "output_tokens"):
        if key not in row or not _is_int(row[key]) or row[key] < 0:
            raise ValueError(f"{key!r} must be an integer >= 0: {row!r}")
    return (row["task"], row["item"], row["model"],
            (row["correct"], row["input_tokens"], row["output_tokens"]))


def _points(points) -> List[dict]:
    out = []
    for p in list(points):
        if not isinstance(p, dict) or set(p) != set(POINT_KEYS):
            raise ValueError(f"a point needs exactly the keys {list(POINT_KEYS)}: {p!r}")
        for key in POINT_KEYS[:4]:
            if not _is_int(p[key]) or p[key] < 0:
                raise ValueError(f"{key!r} must be an integer >= 0: {p!r}")
        if not isinstance(p["inline_separate_call"], bool):
            raise ValueError(f"'inline_separate_call' must be true or false: {p!r}")
        out.append({k: p[k] for k in POINT_KEYS})
    if not out:
        raise ValueError("no points")
    if len({tuple(p.values()) for p in out}) != len(out):
        raise ValueError("points must be distinct")
    return out


def _parents(parents, models: Sequence[str]) -> List[str]:
    if parents is None:
        return list(models)
    parents = list(parents)
    if not parents or any(p not in models for p in parents) or len(set(parents)) != len(parents):
        raise ValueError(f"parents must be distinct models of the matrix, got {parents}")
    return parents


def evaluate_delegation(rows, registry: Registry, bars, points, seeds=range(10),
                        flavors=("cost_effective", "cost_blind"), parents=None,
                        calibration_fraction=0.5, min_samples=30, confidence=0.95) -> dict:
    """Score the 13.5 decision, always inline and always delegating on held-out items.

    Returns ``config``, ``tasks``, ``cells`` and ``summary`` (DESIGN 13.9).
    Deterministic for the same rows in any order.
    """
    rows = list(rows)
    if not rows:
        raise ValueError("no rows")
    table: Dict[Tuple[str, str], Dict[str, Row]] = {}
    for raw in rows:
        task, item, model, row = _row(raw)
        by_model = table.setdefault((task, item), {})
        if model in by_model:
            raise ValueError(f"repeated outcome for task {task!r}, item {item!r}, "
                             f"model {model!r}")
        by_model[model] = row
    models = sorted({m for by_model in table.values() for m in by_model})
    for m in models:
        if m not in registry:
            raise ValueError(f"model {m!r} is not in the registry")
    for (task, item), by_model in sorted(table.items()):
        for m in models:
            if m not in by_model:
                raise ValueError(f"incomplete matrix: no row for task {task!r}, item {item!r}, "
                                 f"model {m!r}")
    bars, seeds, flavors = list(bars), list(seeds), list(flavors)
    _check_run_options(bars, seeds, flavors, min_samples, confidence, calibration_fraction)
    points = _points(points)
    parents = _parents(parents, models)

    task_items: Dict[str, List[str]] = {}
    for task, item in table:
        task_items.setdefault(task, []).append(item)
    tasks = sorted(task_items)
    calibrated = {}
    for task in tasks:
        for seed in seeds:
            cal, held = split_items(task_items[task], seed, calibration_fraction)
            if not cal or not held:
                raise ValueError(f"task {task!r}, seed {seed}: the calibration or held-out "
                                 f"split is empty")
            calibrated[task, seed] = _calibrate(table, models, task, cal, held)

    cells = []
    for bar in bars:
        routers = {(task, seed): _router(registry, task, calibrated[task, seed], bar,
                                         min_samples, confidence)
                   for task in tasks for seed in seeds}
        for flavor in flavors:
            for index, point in enumerate(points):
                for parent in parents:
                    for seed in seeds:
                        for task in tasks:
                            cells.append(_cell(table, registry, routers[task, seed],
                                               calibrated[task, seed], task, bar, flavor,
                                               index, point, parent, seed))
    return {
        "config": {"bars": bars, "seeds": seeds, "flavors": flavors, "points": points,
                   "parents": parents, "calibration_fraction": calibration_fraction,
                   "min_samples": min_samples, "confidence": confidence},
        "tasks": {t: {"items": len(task_items[t]), "models": models} for t in tasks},
        "cells": cells,
        "summary": _summary(cells, seeds),
    }


def _calibrate(table, models, task, cal, held) -> dict:
    """Calibration-half stats and median sizes, which do not depend on bar, flavor or point."""
    stats = Stats()
    for m in models:
        stats.add(task, m, sum(table[task, i][m][0] for i in cal), len(cal))
    return {
        "cal": cal, "held": held, "stats": stats,
        "s_in": statistics.median_low([table[task, i][m][1] for i in cal for m in models]),
        "s_out": statistics.median_low([table[task, i][m][2] for i in cal for m in models]),
    }


def _router(registry, task, calibration, bar, min_samples, confidence) -> Router:
    t = Task(name=task, bar=bar, min_samples=min_samples, confidence=confidence,
             independent_of_generator=False, expected_input_tokens=calibration["s_in"],
             expected_output_tokens=calibration["s_out"], on_no_model="best_available",
             max_fallbacks=0)
    return Router(registry, {task: t}, calibration["stats"])


def _cell(table, registry, router, calibration, task, bar, flavor, index, point, parent,
          seed) -> dict:
    where = f"task {task!r}, parent {parent!r}, point {index}"
    try:
        decision = router.decide_delegation(task, parent, flavor, **point)
    except NoModelClearsBar:
        raise ValueError(f"no model fits the delegated work: {where}") from None
    if decision.route is None:
        raise ValueError(f"no model fits the delegated work: {where}")
    held = calibration["held"]
    p = registry.get(parent)
    d = registry.get(decision.route.primary)
    c, b, r, t = (point[k] for k in POINT_KEYS[:4])

    def inline_cost(item: str) -> float:
        _, tin, tout = table[task, item][p.id]
        if point["inline_separate_call"]:
            return p.cost(c + tin, tout) + (1 + t) * p.cost(tin + tout, 0)
        return p.cost(tin, tout) + t * p.cost(tin + tout, 0)

    def delegate_cost(item: str) -> float:
        _, tin, tout = table[task, item][d.id]
        return p.cost(0, b) + d.cost(b + tin, tout) + (1 + t) * p.cost(b + r, 0)

    inline, delegate = (p.id, inline_cost), (d.id, delegate_cost)
    plans = {"decision": inline if decision.mode == "inline" else delegate,
             "inline": inline, "delegate": delegate}
    correct, success, cost = {}, {}, {}
    for s in STRATEGIES:
        model, item_cost = plans[s]
        correct[s] = sum(table[task, i][model][0] for i in held)
        success[s] = correct[s] / len(held)
        cost[s] = fsum(item_cost(i) for i in held)
    return {"bar": bar, "flavor": flavor, "point": index, "parent": parent, "seed": seed,
            "task": task, "calibration_items": len(calibration["cal"]),
            "held_out_items": len(held), "expected_input_tokens": calibration["s_in"],
            "expected_output_tokens": calibration["s_out"], "mode": decision.mode,
            "model": decision.model, "reason": decision.reason,
            "below_bar": decision.below_bar, "inline_allowed": decision.inline_allowed,
            "delegate": decision.route.primary, "correct": correct, "success": success,
            "cost_usd": cost}


def _summary(cells, seeds) -> List[dict]:
    groups: Dict[tuple, List[dict]] = {}
    for c in cells:
        groups.setdefault((c["bar"], c["flavor"], c["point"], c["parent"]), []).append(c)
    out = []
    for (bar, flavor, index, parent), group in groups.items():
        by_seed = {seed: [c for c in group if c["seed"] == seed] for seed in seeds}
        for s in STRATEGIES:
            seed_success = [sum(c["correct"][s] for c in cs) / sum(c["held_out_items"] for c in cs)
                            for cs in by_seed.values()]
            seed_cost = [fsum(c["cost_usd"][s] for c in cs) for cs in by_seed.values()]
            delegate_rate: Optional[float] = None
            if s == "decision":
                delegate_rate = sum(c["mode"] == "delegate" for c in group) / len(group)
            out.append({
                "bar": bar, "flavor": flavor, "point": index, "parent": parent, "strategy": s,
                "success": fsum(seed_success) / len(seeds),
                "cost_usd": fsum(seed_cost) / len(seeds),
                "below_bar_rate": sum(c["success"][s] < bar for c in group) / len(group),
                "delegate_rate": delegate_rate,
            })
    return out
