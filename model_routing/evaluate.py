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
from .tasks import Task, is_slice_name

PathLike = Union[str, Path]


@dataclass(frozen=True)
class Outcome:
    """One model's result on one item of one task: was it accepted, and what it cost."""

    task: str
    item: str
    model: str
    correct: bool
    cost_usd: float
    slice: Optional[str] = None  # v1.514: last, so five positional arguments keep their meaning


def _is_int(v) -> bool:
    return isinstance(v, int) and not isinstance(v, bool)


def _row_to_outcome(row, registry: Optional[Registry], slice_by: Optional[str] = None
                    ) -> Outcome:
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
    name = None if slice_by is None else row.get(slice_by)
    if name is not None:
        # v1.514: a slice is a 4.2 slice name, on a task whose name holds no '@' (as 4.3)
        if not is_slice_name(name) or "@" in row["task"]:
            raise ValueError(f"a slice must be a non-empty string without '@' on a task "
                             f"without '@': {row!r}")
    return Outcome(row["task"], row["item"], row["model"], row["correct"], cost, name)


def _check_slice_by(slice_by) -> None:
    if slice_by is not None and (not isinstance(slice_by, str) or not slice_by):
        raise ValueError(f"slice_by must be a non-empty string, got {slice_by!r}")


def outcomes_from_rows(rows: Iterable[dict], registry: Optional[Registry] = None, *,
                       slice_by: Optional[str] = None) -> Tuple[Outcome, ...]:
    """Validate outcome-matrix rows (DESIGN 12.1) and return them as Outcomes in input order.

    ``slice_by`` names the row key that holds each row's slice (v1.514); without it every
    Outcome's slice is None and a ``slice`` key is an extra key.
    """
    _check_slice_by(slice_by)
    out: List[Outcome] = []
    seen = set()
    for row in rows:
        o = _row_to_outcome(row, registry, slice_by)
        key = (o.task, o.item, o.model)
        if key in seen:
            raise ValueError(f"repeated outcome for task {o.task!r}, item {o.item!r}, "
                             f"model {o.model!r}")
        seen.add(key)
        out.append(o)
    return tuple(out)


def load_outcomes(path: PathLike, registry: Optional[Registry] = None, *,
                  slice_by: Optional[str] = None) -> Tuple[Outcome, ...]:
    """Read an outcome-matrix JSONL file; errors name ``<path>:<line>``."""
    _check_slice_by(slice_by)
    return outcomes_from_rows(_read_rows(path), registry, slice_by=slice_by)


def _read_rows(path: PathLike) -> List[dict]:
    """The objects of an outcome-matrix JSONL file, blank lines skipped (DESIGN 12.1).

    Private: ``model-routing evaluate`` reads the file once with it and keeps which rows are in
    token form for its price expiry warnings (DESIGN 10 and 12.4, v1.411).
    """
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
    return rows


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
    measured. Deterministic for the same outcomes in any order. When outcomes name
    slices (v1.514), each cell of a sliced task also scores the pooled and the sliced
    route per slice, and ``per_slice`` and ``slice_summary`` follow ``per_task``.
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
    groups = _slice_groups(table, tasks, task_items)
    for task, by_slice in groups.items():
        for seed in seeds:
            cal, held = (set(part) for part in splits[task, seed])
            for name, items in by_slice.items():
                if cal.isdisjoint(items) or held.isdisjoint(items):
                    raise ValueError(f"task {task!r} slice {name!r}, seed {seed}: the calibration "
                                     f"or held-out split is empty")

    strategies = _strategies(models)
    # v1.135: a (task, seed)'s sums, filled by the first cell that needs them and read by every
    # cell of that (task, seed) at any bar or flavor; local to this call
    sums: Dict[Tuple[str, int], dict] = {}
    # v1.514: a sliced (task, seed)'s sums on C_S and H_S per slice, filled once as v1.135
    slice_sums: Dict[Tuple[str, int], Dict[str, dict]] = {}
    cells = []
    for bar in bars:
        for flavor in flavors:
            for seed in seeds:
                for task in tasks:
                    if (task, seed) not in sums:
                        cal, held = splits[task, seed]
                        sums[task, seed] = _split_sums(table, models, task, cal, held)
                        if task in groups:
                            slice_sums[task, seed] = {
                                name: _split_sums(table, models, task,
                                                  [i for i in cal if i in items],
                                                  [i for i in held if i in items])
                                for name, items in groups[task].items()}
                    cell = _cell(sums[task, seed], models, strategies, task, bar, flavor,
                                 seed, min_samples, confidence)
                    if task in groups:
                        cell["slices"] = _slice_entries(slice_sums[task, seed], models, cell,
                                                        min_samples, confidence)
                    cells.append(cell)
    task_info = {t: {"items": len(task_items[t]), "models": models} for t in tasks}
    for t, by_slice in groups.items():
        task_info[t]["slices"] = {name: len(items) for name, items in by_slice.items()}
    result = {
        "config": {"bars": bars, "seeds": seeds, "flavors": flavors,
                   "calibration_fraction": calibration_fraction, "min_samples": min_samples,
                   "confidence": confidence},
        "tasks": task_info,
        "cells": cells,
        "summary": _summary(cells, sums, bars, flavors, seeds, tasks, strategies),
        "per_task": _per_task(cells, bars, flavors, seeds, tasks, strategies),
    }
    if groups:
        result["per_slice"] = _per_slice(cells, bars, flavors, groups)
        result["slice_summary"] = _slice_summary(cells, table, splits, groups, slice_sums, bars,
                                                 flavors, seeds)
    return result


def _split_sums(table, models, task, cal, held) -> dict:
    """The sums of one (task, seed) that neither the bar nor the flavor enters (12.3, v1.135):
    calibration counts and mean costs, each model's held-out success, correct count and cost, the
    oracle's held-out pair and correct count, and the two baselines' picks; ``best`` is ranked on the
    calibration count, since ``n_cal`` is one number per (task, seed) (v1.266)."""
    n_cal, n = len(cal), len(held)
    succ = {m: sum(table[task, i][m].correct for i in cal) for m in models}
    mean_cost = {m: fsum(table[task, i][m].cost_usd for i in cal) / n_cal for m in models}
    held_correct = {m: sum(table[task, i][m].correct for i in held) for m in models}
    held_success = {m: held_correct[m] / n for m in models}
    held_cost = {m: fsum(table[task, i][m].cost_usd for i in held) for m in models}
    ok, spend = 0, []
    for i in held:
        row = table[task, i]
        right = [row[m].cost_usd for m in models if row[m].correct]
        ok += bool(right)
        spend.append(min(right) if right else min(row[m].cost_usd for m in models))
    return {"n_cal": n_cal, "n_held": n, "succ": succ, "mean_cost": mean_cost,
            "held_success": held_success, "held_cost": held_cost, "held_correct": held_correct,
            "oracle": (ok / n, fsum(spend)), "oracle_correct": ok,
            "cheapest": min(models, key=lambda m: (mean_cost[m], m)),
            "best": min(models, key=lambda m: (-succ[m], mean_cost[m], m))}


@dataclass(frozen=True)
class _CalibrationPriced(Model):
    """A model of the routed registry (DESIGN 12.3, v1.263): a call of any size costs its mean
    calibration cost exactly, by ``cost`` and ``base_cost`` alike (v1.265). Its ``price_in``, the
    mean times 1e6 per million input tokens, prices a one-token call at the mean, but ``Model.cost``
    at it is ``(mean * 1e6) / 1e6``, which can merge two means one ulp apart into one cost."""

    mean_cost: float = 0.0

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        return self.mean_cost

    def base_cost(self, input_tokens: int, output_tokens: int) -> float:
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


def _held_correct(split, cell, strategy) -> int:
    """The held-out correct count of ``strategy`` in ``cell`` (12.3, v1.266): an integer from its
    (task, seed) sums, for the model the strategy names or for the oracle, never read back from
    the cell's rate."""
    if strategy == "oracle":
        return split["oracle_correct"]
    m = cell["models"][strategy] if strategy in cell["models"] else strategy[len("model:"):]
    return split["held_correct"][m]


def _summary(cells, sums, bars, flavors, seeds, tasks, strategies):
    rows = []
    for bar in bars:
        for flavor in flavors:
            group = [c for c in cells if c["bar"] == bar and c["flavor"] == flavor]
            for s in strategies:
                per_seed_success, per_seed_cost = [], []
                for seed in seeds:
                    cs = [c for c in group if c["seed"] == seed]
                    correct = sum(_held_correct(sums[c["task"], c["seed"]], c, s) for c in cs)
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


_SLICE_STRATEGIES = ("pooled", "sliced")


def _slice_groups(table, tasks, task_items) -> Dict[str, Dict[str, frozenset]]:
    """``{task: {slice: items}}`` for each sliced task, slices ascending (12.3, v1.514), after the
    checks that every row of an item names one slice and that a task is all sliced or all not."""
    slice_of = {}
    for (task, item), by_model in sorted(table.items()):
        names = {o.slice for o in by_model.values()}
        if len(names) > 1:
            raise ValueError(f"task {task!r}, item {item!r}: its rows name different slices")
        slice_of[task, item] = names.pop()
    groups = {}
    for task in tasks:
        items = sorted(task_items[task])
        if all(slice_of[task, i] is None for i in items):
            continue
        none = [i for i in items if slice_of[task, i] is None]
        if none:
            raise ValueError(f"task {task!r}: item {none[0]!r} has no slice while other items "
                             f"have one")
        by_slice: Dict[str, set] = {}
        for i in items:
            by_slice.setdefault(slice_of[task, i], set()).add(i)
        groups[task] = {name: frozenset(by_slice[name]) for name in sorted(by_slice)}
    return groups


def _slice_entries(slice_split, models, cell, min_samples, confidence) -> dict:
    """A sliced cell's ``slices`` (12.3, v1.514): per slice, the cell's ``routed`` model as
    ``pooled`` and, as ``sliced``, the primary of ``select(slice=S)`` on C_S's counts and mean
    costs, each scored on H_S."""
    task, bar, flavor = cell["task"], cell["bar"], cell["flavor"]
    pooled = cell["models"]["routed"]
    t = Task(name=task, bar=bar, min_samples=min_samples, confidence=confidence,
             independent_of_generator=False, expected_input_tokens=1, expected_output_tokens=0,
             on_no_model="best_available", max_fallbacks=0)
    out = {}
    for name, split in slice_split.items():
        stats = Stats()
        for m in models:
            stats.add(f"{task}@{name}", m, split["succ"][m], split["n_cal"])
        decision = Router(_routed_registry(models, split["mean_cost"]), {task: t}, stats).select(
            task, flavor, slice=name)
        chosen = {"pooled": pooled, "sliced": decision.primary}
        out[name] = {"calibration_items": split["n_cal"], "held_out_items": split["n_held"],
                     "cleared": not decision.below_bar, "models": chosen,
                     "success": {k: split["held_success"][m] for k, m in chosen.items()},
                     "cost_usd": {k: split["held_cost"][m] for k, m in chosen.items()}}
    return out


def _slice_cleared(cell, entry, strategy) -> bool:
    """``pooled`` clears when the cell does, ``sliced`` when the slice's own decision does."""
    return cell["cleared"] if strategy == "pooled" else entry["cleared"]


def _slice_rates(units, bar):
    """``below_bar_rate``, ``cleared_rate`` and ``bar_violation_rate`` over (cleared, success)
    units, as ``_rates`` gives them for ``routed``."""
    below = sum(success < bar for _, success in units) / len(units)
    cleared = [success for ok, success in units if ok]
    violation = sum(success < bar for success in cleared) / len(cleared) if cleared else None
    return below, len(cleared) / len(units), violation


def _per_slice(cells, bars, flavors, groups):
    rows = []
    for bar in bars:
        for flavor in flavors:
            for task in sorted(groups):
                group = [c for c in cells if c["bar"] == bar and c["flavor"] == flavor
                         and c["task"] == task]
                for name in groups[task]:
                    pairs = [(c, c["slices"][name]) for c in group]
                    for st in _SLICE_STRATEGIES:
                        units = [(_slice_cleared(c, e, st), e["success"][st]) for c, e in pairs]
                        below, cleared, violation = _slice_rates(units, bar)
                        routed: Dict[str, int] = {}
                        for _, e in pairs:
                            routed[e["models"][st]] = routed.get(e["models"][st], 0) + 1
                        rows.append({"bar": bar, "flavor": flavor, "task": task, "slice": name,
                                     "strategy": st,
                                     "success": fsum(e["success"][st] for _, e in pairs)
                                     / len(pairs),
                                     "cost_usd": fsum(e["cost_usd"][st] for _, e in pairs)
                                     / len(pairs),
                                     "below_bar_rate": below, "cleared_rate": cleared,
                                     "bar_violation_rate": violation,
                                     "routed_models": dict(sorted(routed.items()))})
    return rows


def _slice_summary(cells, table, splits, groups, slice_sums, bars, flavors, seeds):
    rows = []
    for bar in bars:
        for flavor in flavors:
            group = [c for c in cells if c["bar"] == bar and c["flavor"] == flavor
                     and "slices" in c]
            for st in _SLICE_STRATEGIES:
                per_seed_success, per_seed_cost, units = [], [], []
                met = missed = 0
                for seed in seeds:
                    correct = total = 0
                    spend = []
                    for c in (c for c in group if c["seed"] == seed):
                        split = slice_sums[c["task"], seed]
                        held = splits[c["task"], seed][1]
                        right, every_cleared, some_below = 0, True, False
                        for name, e in c["slices"].items():
                            ok = _slice_cleared(c, e, st)
                            m = e["models"][st]
                            right += split[name]["held_correct"][m]
                            # v1.517: the items' costs, so the seed's total is one exact fsum
                            spend.extend(table[c["task"], i][m].cost_usd for i in held
                                         if i in groups[c["task"]][name])
                            units.append((ok, e["success"][st]))
                            every_cleared = every_cleared and ok
                            some_below = some_below or e["success"][st] < bar
                        correct += right
                        total += c["held_out_items"]
                        # v1.514, v1.515: the task's held-out success from integer counts
                        if every_cleared and right / c["held_out_items"] >= bar:
                            met += 1
                            missed += some_below
                    per_seed_success.append(correct / total)
                    per_seed_cost.append(fsum(spend))
                below, cleared, violation = _slice_rates(units, bar)
                rows.append({"bar": bar, "flavor": flavor, "strategy": st,
                             "success": fsum(per_seed_success) / len(seeds),
                             "cost_usd": fsum(per_seed_cost) / len(seeds),
                             "below_bar_rate": below, "cleared_rate": cleared,
                             "bar_violation_rate": violation,
                             "slice_miss_rate": missed / met if met else None})
    return rows
