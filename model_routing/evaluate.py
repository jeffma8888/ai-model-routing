"""Offline evaluation of task-level routing on a public outcome matrix (DESIGN 12)."""

from __future__ import annotations

import hashlib
import json
from dataclasses import dataclass
from math import fsum, isfinite
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .registry import Model, Registry
from .router import FLAVORS, Router
from .stats import Stats
from .tasks import Task

PathLike = Union[str, Path]


@dataclass(frozen=True)
class Outcome:
    """One model's result on one item of one task: was it accepted, and what it cost."""

    task: str
    item: str
    model: str
    correct: bool
    cost_usd: float


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _row_to_outcome(row, registry: Optional[Registry]) -> Outcome:
    if not isinstance(row, dict):
        raise ValueError(f"outcome row must be an object, got {row!r}")
    for key in ("task", "item", "model"):
        if not isinstance(row.get(key), str) or not row.get(key):
            raise ValueError(f"outcome row needs a non-empty string {key!r}: {row!r}")
    if "correct" not in row or type(row["correct"]) is not bool:
        raise ValueError(f"'correct' must be true or false: {row!r}")
    if "cost_usd" in row:
        cost = row["cost_usd"]
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not isfinite(cost) \
                or cost < 0:
            raise ValueError(f"'cost_usd' must be a finite number >= 0: {row!r}")
        cost = float(cost)
    elif "input_tokens" in row and "output_tokens" in row:
        tin, tout = row["input_tokens"], row["output_tokens"]
        if not (_is_int(tin) and _is_int(tout)) or tin < 0 or tout < 0:
            raise ValueError(f"token counts must be integers >= 0: {row!r}")
        if registry is None or row["model"] not in registry:
            raise ValueError(f"token-form row needs a registry that has {row['model']!r}")
        cost = registry.get(row["model"]).cost(tin, tout)
    else:
        raise ValueError(f"outcome row needs 'cost_usd' or both token counts: {row!r}")
    return Outcome(row["task"], row["item"], row["model"], row["correct"], cost)


def outcomes_from_rows(rows: Iterable[dict], registry: Optional[Registry] = None
                       ) -> Tuple[Outcome, ...]:
    """Validate outcome-matrix rows (DESIGN 12.1) and return them as Outcomes in input order."""
    out: List[Outcome] = []
    seen = set()
    for row in rows:
        o = _row_to_outcome(row, registry)
        key = (o.task, o.item, o.model)
        if key in seen:
            raise ValueError(f"repeated outcome for task {o.task!r}, item {o.item!r}, "
                             f"model {o.model!r}")
        seen.add(key)
        out.append(o)
    return tuple(out)


def load_outcomes(path: PathLike, registry: Optional[Registry] = None) -> Tuple[Outcome, ...]:
    """Read an outcome-matrix JSONL file; errors name ``<path>:<line>``."""
    rows = []
    with open(path, encoding="utf-8") as fh:
        for n, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{n}: invalid JSON: {exc.msg}") from None
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{n}: expected a JSON object")
            rows.append(value)
    return outcomes_from_rows(rows, registry)


def _check_fraction(f: float) -> None:
    if not 0.0 < f < 1.0:
        raise ValueError(f"calibration_fraction must be in (0, 1), got {f}")


def split_items(items: Iterable[str], seed: int, calibration_fraction: float = 0.5
                ) -> Tuple[Tuple[str, ...], Tuple[str, ...]]:
    """Split item IDs into (calibration, held_out) by a seeded sha256 of each ID (DESIGN 12.2)."""
    _check_fraction(calibration_fraction)
    threshold = calibration_fraction * 2 ** 64
    cal, held = [], []
    for item in sorted(set(items)):
        v = int.from_bytes(hashlib.sha256(f"{seed}:{item}".encode("utf-8")).digest()[:8], "big")
        (cal if v < threshold else held).append(item)
    return tuple(cal), tuple(held)


def _check_run_options(bars: list, seeds: list, flavors: list, min_samples, confidence,
                       calibration_fraction) -> None:
    """The bar, seed, flavor and bound checks shared by evaluate and evaluate_delegation (12.3)."""
    if not bars or any(isinstance(b, bool) or not isinstance(b, (int, float))
                       or not isfinite(b) or not 0.0 <= b <= 1.0 for b in bars) \
            or len(set(bars)) != len(bars):
        raise ValueError(f"bars must be distinct finite numbers in [0, 1], got {bars}")
    if not seeds or any(isinstance(x, bool) or not isinstance(x, int) for x in seeds) \
            or len(set(seeds)) != len(seeds):
        raise ValueError(f"seeds must be distinct integers, got {seeds}")
    if not flavors or any(f not in FLAVORS for f in flavors) or len(set(flavors)) != len(flavors):
        raise ValueError(f"flavors must be distinct names from {FLAVORS}")
    if not _is_int(min_samples) or min_samples < 1:
        raise ValueError(f"min_samples must be an integer >= 1, got {min_samples!r}")
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) \
            or not isfinite(confidence) or not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be a finite number in (0, 1), got {confidence!r}")
    _check_fraction(calibration_fraction)


def _strategies(models: Sequence[str]) -> List[str]:
    return ["routed", "oracle", "best_on_calibration", "cheapest"] + [f"model:{m}" for m in models]


def evaluate(outcomes, bars, seeds=range(10), flavors=("cost_effective", "cost_blind"),
             calibration_fraction=0.5, min_samples=30, confidence=0.95) -> dict:
    """Calibrate on one split, route each flavor at each bar, score on the other (DESIGN 12.3).

    Returns ``config``, ``tasks``, ``cells``, ``summary`` and ``per_task``; the
    routed choice comes from ``Router.select`` so the shipped rules are what is
    measured. Deterministic for the same outcomes in any order.
    """
    outcomes = tuple(outcomes)
    bars, seeds, flavors = list(bars), list(seeds), list(flavors)
    if not outcomes:
        raise ValueError("no outcomes")
    _check_run_options(bars, seeds, flavors, min_samples, confidence, calibration_fraction)

    table: Dict[Tuple[str, str], Dict[str, Outcome]] = {}
    models = sorted({o.model for o in outcomes})
    for o in outcomes:
        by_model = table.setdefault((o.task, o.item), {})
        if o.model in by_model:
            # v1.261: as outcomes_from_rows (12.1), never the last one winning
            raise ValueError(f"repeated outcome for task {o.task!r}, item {o.item!r}, "
                             f"model {o.model!r}")
        by_model[o.model] = o
    for (task, item), by_model in sorted(table.items()):
        for m in models:
            if m not in by_model:
                raise ValueError(f"incomplete matrix: no row for task {task!r}, item {item!r}, "
                                 f"model {m!r}")
    task_items: Dict[str, List[str]] = {}
    for task, item in table:
        task_items.setdefault(task, []).append(item)
    tasks = sorted(task_items)
    splits = {}
    for task in tasks:
        for seed in seeds:
            cal, held = split_items(task_items[task], seed, calibration_fraction)
            if not cal or not held:
                raise ValueError(f"task {task!r}, seed {seed}: the calibration or held-out "
                                 f"split is empty")
            splits[task, seed] = (cal, held)

    strategies = _strategies(models)
    # v1.135: a (task, seed)'s sums, filled by the first cell that needs them and read by every
    # cell of that (task, seed) at any bar or flavor; local to this call
    sums: Dict[Tuple[str, int], dict] = {}
    cells = []
    for bar in bars:
        for flavor in flavors:
            for seed in seeds:
                for task in tasks:
                    if (task, seed) not in sums:
                        cal, held = splits[task, seed]
                        sums[task, seed] = _split_sums(table, models, task, cal, held)
                    cells.append(_cell(sums[task, seed], models, strategies, task, bar, flavor,
                                       seed, min_samples, confidence))
    return {
        "config": {"bars": bars, "seeds": seeds, "flavors": flavors,
                   "calibration_fraction": calibration_fraction, "min_samples": min_samples,
                   "confidence": confidence},
        "tasks": {t: {"items": len(task_items[t]), "models": models} for t in tasks},
        "cells": cells,
        "summary": _summary(cells, bars, flavors, seeds, tasks, strategies),
        "per_task": _per_task(cells, bars, flavors, seeds, tasks, strategies),
    }


def _split_sums(table, models, task, cal, held) -> dict:
    """The sums of one (task, seed) that neither the bar nor the flavor enters (12.3, v1.135):
    calibration counts and mean costs, each model's held-out success and cost, the oracle's
    held-out pair, and the two baselines' picks."""
    n_cal, n = len(cal), len(held)
    succ = {m: sum(table[task, i][m].correct for i in cal) for m in models}
    mean_cost = {m: fsum(table[task, i][m].cost_usd for i in cal) / n_cal for m in models}
    held_success = {m: sum(table[task, i][m].correct for i in held) / n for m in models}
    held_cost = {m: fsum(table[task, i][m].cost_usd for i in held) for m in models}
    ok, spend = 0, []
    for i in held:
        row = table[task, i]
        right = [row[m].cost_usd for m in models if row[m].correct]
        ok += bool(right)
        spend.append(min(right) if right else min(row[m].cost_usd for m in models))
    return {"n_cal": n_cal, "n_held": n, "succ": succ, "mean_cost": mean_cost,
            "held_success": held_success, "held_cost": held_cost,
            "oracle": (ok / n, fsum(spend)),
            "cheapest": min(models, key=lambda m: (mean_cost[m], m)),
            "best": min(models, key=lambda m: (-succ[m] / n_cal, mean_cost[m], m))}


@dataclass(frozen=True)
class _CalibrationPriced(Model):
    """A model of the routed registry (DESIGN 12.3, v1.263): a call of any size costs its mean
    calibration cost exactly. Its ``price_in``, the mean times 1e6 per million input tokens, prices a
    one-token call at the mean, but ``Model.cost`` at it is ``(mean * 1e6) / 1e6``, which can merge
    two means one ulp apart into one cost."""

    mean_cost: float = 0.0

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return self.mean_cost


def _routed_registry(models, mean_cost) -> Registry:
    """The registry ``routed`` is chosen over (12.3): each model of ``models``, in that order, costing
    ``mean_cost[model]`` a call, with a window no call reaches, so rules 1 to 5 of 5.2 exclude none.
    research/check_fallback.py and research/below_bar_fallback.py rebuild a cell's router over it."""
    return Registry([_CalibrationPriced(m, m, mean_cost[m] * 1_000_000, 0.0, 2 ** 62,
                                        mean_cost=mean_cost[m]) for m in models])


def _cell(split, models, strategies, task, bar, flavor, seed, min_samples, confidence) -> dict:
    n_cal, succ, mean_cost = split["n_cal"], split["succ"], split["mean_cost"]
    stats = Stats()
    for m in models:
        stats.add(task, m, succ[m], n_cal)
    registry = _routed_registry(models, mean_cost)
    t = Task(name=task, bar=bar, min_samples=min_samples, confidence=confidence,
             independent_of_generator=False, expected_input_tokens=1, expected_output_tokens=0,
             on_no_model="best_available", max_fallbacks=0)
    decision = Router(registry, {task: t}, stats).select(task, flavor)
    chosen = {"routed": decision.primary, "best_on_calibration": split["best"],
              "cheapest": split["cheapest"]}
    success, cost = {}, {}
    for s in strategies:
        if s == "oracle":
            success[s], cost[s] = split["oracle"]
            continue
        m = chosen[s] if s in chosen else s[len("model:"):]
        success[s], cost[s] = split["held_success"][m], split["held_cost"][m]
    return {"bar": bar, "flavor": flavor, "seed": seed, "task": task,
            "calibration_items": n_cal, "held_out_items": split["n_held"],
            "cleared": not decision.below_bar, "models": chosen,
            "success": success, "cost_usd": cost}


def _rates(cells, strategy, bar):
    below = sum(c["success"][strategy] < bar for c in cells) / len(cells)
    if strategy != "routed":
        return below, None, None
    cleared = [c for c in cells if c["cleared"]]
    violation = (sum(c["success"]["routed"] < bar for c in cleared) / len(cleared)
                 if cleared else None)
    return below, len(cleared) / len(cells), violation


def _summary(cells, bars, flavors, seeds, tasks, strategies):
    rows = []
    for bar in bars:
        for flavor in flavors:
            group = [c for c in cells if c["bar"] == bar and c["flavor"] == flavor]
            for s in strategies:
                per_seed_success, per_seed_cost = [], []
                for seed in seeds:
                    cs = [c for c in group if c["seed"] == seed]
                    correct = sum(round(c["success"][s] * c["held_out_items"]) for c in cs)
                    total = sum(c["held_out_items"] for c in cs)
                    per_seed_success.append(correct / total)
                    per_seed_cost.append(fsum(c["cost_usd"][s] for c in cs))
                below, cleared, violation = _rates(group, s, bar)
                rows.append({"bar": bar, "flavor": flavor, "strategy": s,
                             "success": fsum(per_seed_success) / len(seeds),
                             "cost_usd": fsum(per_seed_cost) / len(seeds),
                             "below_bar_rate": below, "cleared_rate": cleared,
                             "bar_violation_rate": violation})
    return rows


def _per_task(cells, bars, flavors, seeds, tasks, strategies):
    rows = []
    for bar in bars:
        for flavor in flavors:
            for task in tasks:
                group = [c for c in cells if c["bar"] == bar and c["flavor"] == flavor
                         and c["task"] == task]
                for s in strategies:
                    below, cleared, violation = _rates(group, s, bar)
                    routed_models = None
                    if s == "routed":
                        routed_models = {}
                        for c in group:
                            m = c["models"]["routed"]
                            routed_models[m] = routed_models.get(m, 0) + 1
                        routed_models = dict(sorted(routed_models.items()))
                    rows.append({"bar": bar, "flavor": flavor, "task": task, "strategy": s,
                                 "success": fsum(c["success"][s] for c in group) / len(group),
                                 "cost_usd": fsum(c["cost_usd"][s] for c in group) / len(group),
                                 "below_bar_rate": below, "cleared_rate": cleared,
                                 "bar_violation_rate": violation,
                                 "routed_models": routed_models})
    return rows
