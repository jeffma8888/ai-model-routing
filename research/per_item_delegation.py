"""Whether held-out items' cheaper delegation paths differ from the per-task decision (DESIGN 13.8 v1.227)

Usage:
  python research/per_item_delegation.py --matrix llmrouterbench-matrix.jsonl [--root PATH]

Runs `evaluate_delegation` (DESIGN 13.9) on the LLMRouterBench matrix that the converter writes, as
evidence/llmrouterbench-delegation/results.py does (its `select_rows`, registry, bars, seeds and
points), checks that the run's summary is the committed results.json one, and rebuilds, for every
held-out item of every cell, the list-price cost 13.9 charges always inline (the parent at its own
sizes on that item) and always delegating (the cell's delegate at its own sizes); each pair of
rebuilt sums must equal its cell's costs and correct counts exactly. An item's cheaper path is the
one with the lower rebuilt cost, the decision's mode on a tie. Two strategies take it: `pick` on
every cell, and `size rule` only on the cells where the decision compared the two paths' costs
(13.5 row 3, reason `delegate_cheaper` or `inline_cheaper`), every other cell keeping its mode.
Each item's success is the record of the path it takes, so on cost `pick` is a floor for any rule
that sees each item's sizes before the call. Standard library and the model_routing package. Read
by research/per-item-delegation.md. Exit 0, or 2 with one `error: ...` line on a missing or
unreadable file, a row the 13.13 script or 13.9 refuses, a summary that is not the committed one, a
rebuilt cost or count that is not its cell's, or a tiered model or per-call rows (not rebuilt here).
"""

import argparse
import importlib.util
import json
import sys
from itertools import compress
from math import fsum
from pathlib import Path

from model_routing import Registry, evaluate_delegation, split_items

ROOT = Path(__file__).resolve().parents[1]
FOLDER = "evidence/llmrouterbench-delegation"
STRATEGIES = ("pick", "size rule")
COMPARED = ("delegate_cheaper", "inline_cheaper")
HEADER = "  flavor          bar  strategy    cells  switched / items     share  cost / decision  success - decision  better"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _inline(p, point, tin, tout):
    """13.9 always inline for one held-out item of a single-call row, a model without tiers."""
    c, t = point["context_tokens"], point["carry_turns"]
    k = point.get("work_calls", 1)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    reads = k * c if point["inline_separate_call"] else (k - 1) * c
    if "cached_read_ratio" in point:
        reads = reads * point["cached_read_ratio"]
    if point["inline_separate_call"]:
        return (p.base_cost(reads + w_in * tin + w_out * tout, k * tout)
                + (1 + t) * p.base_cost(k * (tin + tout), 0))
    return (p.base_cost(reads + w_in * tin + w_out * tout, k * tout)
            + t * p.base_cost(k * (tin + tout), 0))


def _delegate(p, d, point, tin, tout):
    """13.9 always delegate for one held-out item of a single-call row, models without tiers."""
    b, r, t = point["brief_tokens"], point["result_tokens"], point["carry_turns"]
    k = point.get("work_calls", 1)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    return (p.base_cost(0, b) + d.base_cost(k * b + w_in * tin + w_out * tout, k * tout)
            + (1 + t) * p.base_cost(b + r, 0))


def _mask(flags):
    return sum(1 << j for j, f in enumerate(flags) if f)


def tally(rows, registry, full):
    """Per summary row (bar, flavor, point, parent) and strategy: the decision's and the strategy's
    (success, cost) as 13.9 aggregates them, and the switched and held-out items of the cells the
    strategy may change. Also returns the number of path pairs rebuilt. Raises ValueError on a
    rebuilt cost or count that is not its cell's, a tiered model or a row with per-call sizes."""
    config = full["config"]
    points, seeds, fraction = config["points"], config["seeds"], config["calibration_fraction"]
    table, order = {}, {}
    for r in rows:
        if "call_input_tokens" in r or "call_output_tokens" in r:
            raise ValueError("a row has per-call sizes, which this script does not rebuild")
        if (r["task"], r["item"]) not in table:
            order.setdefault(r["task"], []).append(r["item"])
        table.setdefault((r["task"], r["item"]), {})[r["model"]] = (
            r["correct"], r["input_tokens"], r["output_tokens"])
    for m in registry.models:
        if m.price_tiers:
            raise ValueError(f"model {m.id!r} has price tiers, which this script does not rebuild")
    held = {}
    for task, items in order.items():
        for seed in seeds:
            chosen = set(split_items(items, seed, fraction)[1])
            flags = [i in chosen for i in items]
            held[task, seed] = (flags, _mask(flags), sum(flags))
    ok = {(task, m): _mask(table[task, i][m][0] for i in items)
          for task, items in order.items() for m in {m for i in items for m in table[task, i]}}
    vectors, pairs = {}, {}
    out = {}
    for cell in full["cells"]:
        task, seed, index, parent, d = (cell[k] for k in ("task", "seed", "point", "parent", "delegate"))
        key = (task, index, parent, d)
        if key not in vectors:
            p, dm, point = registry.get(parent), registry.get(d), points[index]
            ci = [_inline(p, point, *table[task, i][parent][1:]) for i in order[task]]
            cd = [_delegate(p, dm, point, *table[task, i][d][1:]) for i in order[task]]
            vectors[key] = (ci, cd, [min(a, b) for a, b in zip(ci, cd)],
                            _mask(a < b for a, b in zip(ci, cd)), _mask(a > b for a, b in zip(ci, cd)))
        ci, cd, low, lt, gt = vectors[key]
        flags, hm, n = held[task, seed]
        pair = key + (seed,)
        if pair not in pairs:
            pairs[pair] = (fsum(compress(ci, flags)), fsum(compress(cd, flags)),
                           (hm & ok[task, parent]).bit_count(), (hm & ok[task, d]).bit_count(),
                           fsum(compress(low, flags)))
        cost_i, cost_d, ok_i, ok_d, cost_pick = pairs[pair]
        if (cost_i, cost_d) != (cell["cost_usd"]["inline"], cell["cost_usd"]["delegate"]):
            raise ValueError(f"rebuilt costs are not the cell's: task {task!r}, seed {seed}, "
                             f"point {index}, parent {parent!r}")
        if (ok_i, ok_d) != (cell["correct"]["inline"], cell["correct"]["delegate"]):
            raise ValueError(f"rebuilt correct counts are not the cell's: task {task!r}, seed {seed}, "
                             f"point {index}, parent {parent!r}")
        if cell["mode"] == "inline":
            take_i = hm & ~gt
            switched = (hm & gt).bit_count()
        else:
            take_i = hm & lt
            switched = (hm & lt).bit_count()
        right = (take_i & ok[task, parent]).bit_count() + ((hm & ~take_i) & ok[task, d]).bit_count()
        row = out.setdefault((cell["bar"], cell["flavor"], index, parent), {
            s: {"seeds": {}, "switched": 0, "items": 0, "cells": 0} for s in ("decision",) + STRATEGIES})
        for s in ("decision",) + STRATEGIES:
            if s == "decision" or (s == "size rule" and cell["reason"] not in COMPARED):
                c_ok, c_cost = cell["correct"]["decision"], cell["cost_usd"]["decision"]
            else:
                c_ok, c_cost = right, cost_pick
                row[s]["switched"] += switched
                row[s]["items"] += n
                row[s]["cells"] += 1
            acc = row[s]["seeds"].setdefault(seed, [0, 0, []])
            acc[0] += c_ok
            acc[1] += n
            acc[2].append(c_cost)
    for row in out.values():
        for s in row.values():
            per_seed = [s["seeds"][seed] for seed in seeds]
            s["success"] = fsum(a / b for a, b, _ in per_seed) / len(seeds)
            s["cost_usd"] = fsum(fsum(c) for _, _, c in per_seed) / len(seeds)
            del s["seeds"]
    return out, len(pairs)


def _count(n, noun):
    return f"{n:,} {noun}" + ("" if n == 1 else "s")


def _share(top, bottom):
    return f"{top / bottom:.4f}" if bottom else "-"


def report(rows, registry, full) -> list:
    """The lines the script prints, from the matrix rows, the registry and the 13.9 run on them."""
    rows = list(rows)
    out, pairs = tally(rows, registry, full)
    for (bar, flavor, index, parent), row in out.items():
        for r in full["summary"]:
            if (r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]) == (bar, flavor, index, parent, "decision"):
                if (r["success"], r["cost_usd"]) != (row["decision"]["success"], row["decision"]["cost_usd"]):
                    raise ValueError(f"the decision row is not the summary's: bar {bar}, {flavor}, "
                                     f"point {index}, parent {parent!r}")
    items = {(r["task"], r["item"]) for r in rows}
    config = full["config"]
    lines = [
        "Per-item delegation paths on LLMRouterBench: each held-out item's cheaper path by list price at its own sizes, against the per-task decision",
        f"matrix: {len(rows):,} rows, {len(items):,} items, {_count(len(full['tasks']), 'task')}, "
        f"{_count(len(registry.models), 'model')}; {len(full['cells']):,} cells, {pairs:,} path pairs rebuilt, "
        "each equal to its cell's inline and delegate costs and correct counts",
        HEADER,
    ]
    for flavor in config["flavors"]:
        for bar in config["bars"]:
            group = [row for (b, f, _, _), row in out.items() if (b, f) == (bar, flavor)]
            dec_cost = fsum(row["decision"]["cost_usd"] for row in group)
            for s in STRATEGIES:
                cells = sum(row[s]["cells"] for row in group)
                switched = sum(row[s]["switched"] for row in group)
                n = sum(row[s]["items"] for row in group)
                cost = fsum(row[s]["cost_usd"] for row in group)
                gain = fsum(row[s]["success"] - row["decision"]["success"] for row in group) / len(group)
                better = sum(row[s]["success"] >= row["decision"]["success"]
                             and row[s]["cost_usd"] < row["decision"]["cost_usd"] for row in group)
                lines.append(f"  {flavor:<14}  {bar:<3}  {s:<10}  {cells:>5}  {switched:>8,} / {n:<9,}  "
                             f"{_share(switched, n):>6}  {_share(cost, dec_cost):>15}  {gain:>+18.4f}  {better:>6}")
    for flavor in config["flavors"]:
        parts = []
        for index in range(len(config["points"])):
            group = [row for (_, f, i, _), row in out.items() if (f, i) == (flavor, index)]
            parts.append(f"{index}: {_share(sum(r['pick']['switched'] for r in group), sum(r['pick']['items'] for r in group))}")
        lines.append(f"  pick, switched share by point, {flavor}: " + ", ".join(parts))
    for flavor in config["flavors"]:
        for s in STRATEGIES:
            best = None
            for (bar, f, index, parent), row in out.items():
                if f != flavor or row[s]["success"] < row["decision"]["success"]:
                    continue
                cut = row["decision"]["cost_usd"] - row[s]["cost_usd"]
                if cut > 0 and (best is None or cut > best[0]):
                    best = (cut, bar, index, parent, row)
            if best is None:
                lines.append(f"  largest cost cut at no less success, {s}, {flavor}: no row")
                continue
            _, bar, index, parent, row = best
            lines.append(f"  largest cost cut at no less success, {s}, {flavor}: bar {bar}, point {index}, "
                         f"parent {parent}: decision {row['decision']['success']:.4f} at "
                         f"{row['decision']['cost_usd']:.4f} USD, {s} {row[s]['success']:.4f} at "
                         f"{row[s]['cost_usd']:.4f}")
    return lines


def _read_rows(path):
    rows = []
    try:
        with open(path, encoding="utf-8") as fh:
            for number, line in enumerate(fh, 1):
                if line.strip():
                    try:
                        rows.append(json.loads(line))
                    except ValueError as exc:
                        raise ValueError(f"{path}:{number}: invalid JSON: {exc}") from None
    except (OSError, UnicodeDecodeError) as exc:
        raise ValueError(f"{path}: cannot read ({exc})") from None
    return rows


def run(matrix, root=ROOT) -> list:
    """The 13.13 run on the matrix, checked against the committed summary, then `report`."""
    root = Path(root)
    script = _load("research_per_item_delegation_lrb", root / FOLDER / "results.py")
    try:
        registry = Registry.load(root / FOLDER / "registry.json")
        committed = json.loads((root / FOLDER / "results.json").read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{FOLDER}: cannot read ({exc})") from None
    rows, _dropped = script.select_rows(_read_rows(matrix), [m.id for m in registry.models])
    full = evaluate_delegation(rows, registry, bars=list(script.BARS), points=script.points(),
                               seeds=range(script.SEEDS))
    if full["summary"] != committed.get("summary"):
        raise ValueError(f"the run's summary is not the one in {FOLDER}/results.json")
    return report(rows, registry, full)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="per_item_delegation.py", description=__doc__.splitlines()[0])
    parser.add_argument("--matrix", required=True, help="the LLMRouterBench converter's output (JSONL)")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        lines = run(args.matrix, args.root)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
