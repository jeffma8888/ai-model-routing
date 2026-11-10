"""Offline evidence for the inline-or-sub-agent decision on a public outcome matrix (DESIGN 13.9).

No public dataset records inline-versus-sub-agent outcomes, so this combines what
a matrix does measure (each model's acceptance and token counts on each item)
with a stated grid of what it does not (the parent's context and the hand-off
sizes). The decision comes from ``Router.decide_delegation`` on calibration-half
stats that hold each model's token totals, so each model is priced at its own mean
sizes, and each held-out item is costed at list price from its own tokens. A point
may also carry ``work_calls`` (K work calls per path) and ``cached_read_ratio`` (the
parent's reads of its context in the inline work calls at that fraction of its list input
price), both assumed like the rest of the grid. A row may instead carry each of its work
calls, ``call_input_tokens`` and ``call_output_tokens``, so a multi-call item is priced on
its own calls by position, each path at the calls of the model doing the work (v1.74).
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
OPTIONAL_KEYS = ("work_calls", "cached_read_ratio")
CALL_KEYS = ("call_input_tokens", "call_output_tokens")
STRATEGIES = ("decision", "inline", "delegate")

# (K, Rd, A, O) of a row's per-call sizes: its number of work calls, what they read, their
# new input and what they write (DESIGN 13.9 v1.74)
Calls = Tuple[int, int, int, int]
# (correct, input_tokens, output_tokens, calls) of one model's row for one item, calls
# None on a row without per-call sizes
Row = Tuple[bool, int, int, Optional[Calls]]


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
            (row["correct"], row["input_tokens"], row["output_tokens"], _calls(row)))


def _calls(row: dict) -> Optional[Calls]:
    """A row's per-call sizes, checked, or None without them (DESIGN 13.9 v1.74).

    Call j reads a_1 to a_j and b_1 to b_(j-1), so the K calls read
    Rd = sum (K - j + 1) a_j + (K - j) b_j, which ``input_tokens`` must equal, and
    write O = sum b_j, which ``output_tokens`` must equal.
    """
    if not any(key in row for key in CALL_KEYS):
        return None
    if not all(key in row for key in CALL_KEYS):
        raise ValueError(f"'call_input_tokens' and 'call_output_tokens' go together: {row!r}")
    for key in CALL_KEYS:
        v = row[key]
        if not isinstance(v, list) or not v or any(not _is_int(x) or x < 0 for x in v):
            raise ValueError(f"{key!r} must be a non-empty list of integers >= 0: {row!r}")
    a, b = row["call_input_tokens"], row["call_output_tokens"]
    if len(a) != len(b):
        raise ValueError("'call_input_tokens' and 'call_output_tokens' must have the same "
                         f"length: {row!r}")
    k = len(a)
    rd = sum((k - j) * x for j, x in enumerate(a)) + sum((k - j - 1) * y for j, y in enumerate(b))
    o = sum(b)
    if row["input_tokens"] != rd or row["output_tokens"] != o:
        raise ValueError(f"'input_tokens' must be what the row's calls read, {rd}, and "
                         f"'output_tokens' what they write, {o}: {row!r}")
    return k, rd, sum(a), o


def _points(points) -> List[dict]:
    out = []
    for p in list(points):
        if not isinstance(p, dict) or set(p) - set(OPTIONAL_KEYS) != set(POINT_KEYS):
            raise ValueError(f"a point needs exactly the keys {list(POINT_KEYS)}, and "
                             f"optionally 'work_calls' and 'cached_read_ratio': {p!r}")
        for key in POINT_KEYS[:4]:
            if not _is_int(p[key]) or p[key] < 0:
                raise ValueError(f"{key!r} must be an integer >= 0: {p!r}")
        if not isinstance(p["inline_separate_call"], bool):
            raise ValueError(f"'inline_separate_call' must be true or false: {p!r}")
        if "work_calls" in p and (not _is_int(p["work_calls"]) or p["work_calls"] < 1):
            raise ValueError(f"'work_calls' must be an integer >= 1: {p!r}")
        if "cached_read_ratio" in p:
            rho = p["cached_read_ratio"]
            if isinstance(rho, bool) or not isinstance(rho, (int, float)) or not 0 <= rho <= 1:
                raise ValueError(f"'cached_read_ratio' must be a number from 0 to 1: {p!r}")
        q = {k: p[k] for k in POINT_KEYS}
        for key in OPTIONAL_KEYS:
            if key in p:
                q[key] = p[key]
        out.append(q)
    if not out:
        raise ValueError("no points")
    if len({tuple(p[k] for k in POINT_KEYS) + (p.get("work_calls", 1), p.get("cached_read_ratio", 1.0))
            for p in out}) != len(out):
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
    kinds: Dict[str, set] = {}
    for (task, _), by_model in table.items():
        kinds.setdefault(task, set()).update(r[3] is not None for r in by_model.values())
    for task in sorted(kinds):
        if len(kinds[task]) == 2:
            raise ValueError(f"task {task!r}: either every row or no row carries per-call sizes")
    per_call = sorted(task for task in kinds if kinds[task] == {True})
    bars, seeds, flavors = list(bars), list(seeds), list(flavors)
    _check_run_options(bars, seeds, flavors, min_samples, confidence, calibration_fraction)
    points = _points(points)
    for index, p in enumerate(points):
        if p.get("work_calls", 1) > 1 and per_call:
            raise ValueError(f"point {index} sets 'work_calls' above 1 and task "
                             f"{per_call[0]!r} has per-call sizes")
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
            calibrated[task, seed] = _calibrate(table, models, task, cal, held,
                                                task in per_call)

    cells = []
    # (task, seed, point, parent, path, model) -> (correct, cost_usd) on the held-out half:
    # neither the bar nor the flavor enters a held-out sum (DESIGN 13.9 v1.132)
    paths: Dict[tuple, Tuple[int, float]] = {}
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
                                               index, point, parent, seed, paths))
    return {
        "config": {"bars": bars, "seeds": seeds, "flavors": flavors, "points": points,
                   "parents": parents, "calibration_fraction": calibration_fraction,
                   "min_samples": min_samples, "confidence": confidence},
        "tasks": {t: {"items": len(task_items[t]), "models": models} for t in tasks},
        "cells": cells,
        "summary": _summary(cells, seeds),
    }


def _calibrate(table, models, task, cal, held, per_call=False) -> dict:
    """Calibration-half stats with token totals, and median sizes, independent of bar, flavor and point.

    The stats hold each model's token totals over the half, so ``decide_delegation``
    prices it at its own mean sizes; the pooled medians are the task's expected sizes,
    which only the context checks read (DESIGN 13.9, v1.35). On a task with per-call
    sizes (v1.74) the sizes are rounded-up means per call and ``k``, the median call count,
    is the decision's ``work_calls``: a forecast that no held-out cost uses.
    """
    stats = Stats()
    if per_call:
        def up(x: int, y: int) -> int:
            return -(-x // y)
        for m in models:
            calls = [table[task, i][m][3] for i in cal]
            k_c = sum(r[0] for r in calls)
            stats.add(task, m, sum(table[task, i][m][0] for i in cal), len(cal),
                      input_tokens=len(cal) * up(sum(r[2] for r in calls), k_c),
                      output_tokens=len(cal) * up(sum(r[3] for r in calls), k_c))
        rows = [table[task, i][m][3] for i in cal for m in models]
        return {"cal": cal, "held": held, "stats": stats,
                "s_in": statistics.median_low([up(r[2], r[0]) for r in rows]),
                "s_out": statistics.median_low([up(r[3], r[0]) for r in rows]),
                "k": statistics.median_low([r[0] for r in rows])}
    for m in models:
        stats.add(task, m, sum(table[task, i][m][0] for i in cal), len(cal),
                  input_tokens=sum(table[task, i][m][1] for i in cal),
                  output_tokens=sum(table[task, i][m][2] for i in cal))
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
          seed, paths) -> dict:
    where = f"task {task!r}, parent {parent!r}, point {index}"
    k_dec = calibration.get("k")
    try:
        decision = router.decide_delegation(
            task, parent, flavor, **(point if k_dec is None else dict(point, work_calls=k_dec)))
    except NoModelClearsBar:
        raise ValueError(f"no model fits the delegated work: {where}") from None
    if decision.route is None:
        raise ValueError(f"no model fits the delegated work: {where}")
    held = calibration["held"]
    p = registry.get(parent)
    d = registry.get(decision.route.primary)
    c, b, r, t = (point[k] for k in POINT_KEYS[:4])
    k = point.get("work_calls", 1)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    reads = k * c if point["inline_separate_call"] else (k - 1) * c
    if "cached_read_ratio" in point:
        reads = reads * point["cached_read_ratio"]

    def inline_calls(item: str) -> float:
        kp, rd, a, o = table[task, item][p.id][3]
        base = kp * c if point["inline_separate_call"] else (kp - 1) * c
        if "cached_read_ratio" in point:
            base = base * point["cached_read_ratio"]
        if point["inline_separate_call"]:
            return p.base_cost(base + rd, o) + (1 + t) * p.base_cost(a + o, 0)
        return p.base_cost(base + rd, o) + t * p.base_cost(a + o, 0)

    def delegate_calls(item: str) -> float:
        kd, rd, _, o = table[task, item][d.id][3]
        return p.base_cost(0, b) + d.base_cost(kd * b + rd, o) + (1 + t) * p.base_cost(b + r, 0)

    def inline_cost(item: str) -> float:
        if k_dec is not None:
            return inline_calls(item)
        _, tin, tout, _ = table[task, item][p.id]
        if point["inline_separate_call"]:
            return (p.base_cost(reads + w_in * tin + w_out * tout, k * tout)
                    + (1 + t) * p.base_cost(k * (tin + tout), 0))
        return (p.base_cost(reads + w_in * tin + w_out * tout, k * tout)
                + t * p.base_cost(k * (tin + tout), 0))

    def delegate_cost(item: str) -> float:
        if k_dec is not None:
            return delegate_calls(item)
        _, tin, tout, _ = table[task, item][d.id]
        return (p.base_cost(0, b) + d.base_cost(k * b + w_in * tin + w_out * tout, k * tout)
                + (1 + t) * p.base_cost(b + r, 0))

    inline, delegate = ("inline", p.id, inline_cost), ("delegate", d.id, delegate_cost)
    plans = {"decision": inline if decision.mode == "inline" else delegate,
             "inline": inline, "delegate": delegate}
    correct, success, cost = {}, {}, {}
    for s in STRATEGIES:
        path, model, item_cost = plans[s]
        # p.id is `parent` and `index` names one point of the run's checked list, so the key
        # fixes every input of the pair: held from (task, seed), P, D = model on a delegated
        # path, the point's sizes and, on a per-call task, k_dec from (task, seed)
        key = (task, seed, index, parent, path, model)
        if key not in paths:
            paths[key] = (sum(table[task, i][model][0] for i in held),
                          fsum(item_cost(i) for i in held))
        correct[s], cost[s] = paths[key]
        success[s] = correct[s] / len(held)
    out = {"bar": bar, "flavor": flavor, "point": index, "parent": parent, "seed": seed,
           "task": task, "calibration_items": len(calibration["cal"]),
           "held_out_items": len(held), "expected_input_tokens": calibration["s_in"],
           "expected_output_tokens": calibration["s_out"]}
    if k_dec is not None:
        out["expected_work_calls"] = k_dec
    out.update({"mode": decision.mode, "model": decision.model, "reason": decision.reason,
                "below_bar": decision.below_bar, "inline_allowed": decision.inline_allowed,
                "delegate": decision.route.primary, "correct": correct, "success": success,
                "cost_usd": cost})
    return out


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
