"""Whether held-out items' cheaper delegation paths differ from the per-task decision (DESIGN 13.8 v1.227, v1.230, v1.233, v1.328, v1.331)

Usage:
  python research/per_item_delegation.py --matrix llmrouterbench-matrix.jsonl [--root PATH]
  python research/per_item_delegation.py --dataset autobench --matrix autobench-tokens.jsonl --registry autobench-pool.json [--root PATH]
  python research/per_item_delegation.py --dataset tau2-bench --matrix tau2-calls.jsonl [--root PATH]
  python research/per_item_delegation.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl [--root PATH]
  python research/per_item_delegation.py --dataset response-bank --matrix response-bank-matrix.jsonl [--root PATH]

Runs `evaluate_delegation` (DESIGN 13.9) on the LLMRouterBench matrix that the converter writes, as
evidence/llmrouterbench-delegation/results.py does (its `select_rows`, registry, bars, seeds and
points), or with `--dataset autobench` on the AutoBench 2026 converter's `--task-by all --tokens`
matrix and `--registry` pool, as evidence/delegation/results.py does on its base grid (v1.230),
or with `--dataset tau2-bench` (`tau2-bench-pooled`) on the tau2-bench converter's `--calls`
(`--calls --task-by all`) matrix and the committed registry, as evidence/tau2-bench-delegation/
results.py makes results.json (pooled.json) (v1.233), or with `--dataset response-bank` on the
response-bank converter's default matrix, after evidence/response-bank-delegation/results.py's
`select_rows`, and the committed registry, as that script makes results.json (v1.328), checks that
the run's summary is the committed one, and rebuilds, for every held-out item of every cell, the list-price cost 13.9
charges always inline (the parent at its own sizes on that item, or on its own calls on a row with
per-call sizes, 13.9 v1.74) and always delegating (the cell's delegate likewise); each pair of
rebuilt sums must equal its cell's costs and correct counts exactly. An item's cheaper path is the
one with the lower rebuilt cost, the decision's mode on a tie. Two strategies take it: `pick` on
every cell, and `size rule` only on the cells where the decision compared the two paths' costs
(13.5 row 3, reason `delegate_cheaper` or `inline_cheaper`), every other cell keeping its mode.
Each item's success is the record of the path it takes, so on cost `pick` is a floor for any rule
that sees each item's sizes before the call. With `--dataset response-bank` the report ends with a
third strategy, `input rule` (v1.331): on the cells `size rule` may change, inline on the held-out
items whose parent input tokens are under a threshold set on the cell's calibration half alone,
printed by bar and point beside `size rule`. Standard library and the model_routing package. Read
by research/per-item-delegation.md. Exit 0, or 2 with one `error: ...` line on a missing or
unreadable file, a row the 13.13 script or 13.9 refuses, a summary that is not the committed one, a
rebuilt cost or count that is not its cell's, a tiered model (not rebuilt here), a row with
per-call sizes where the input rule is computed, or `--dataset autobench` without `--registry` or
`--registry` without it.
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
AUTOBENCH_FOLDER = "evidence/delegation"
TAU2_FOLDER = "evidence/tau2-bench-delegation"
RESPONSE_BANK_FOLDER = "evidence/response-bank-delegation"
DATASETS = ("llmrouterbench", "autobench", "tau2-bench", "tau2-bench-pooled", "response-bank")
NAMES = {"llmrouterbench": "LLMRouterBench", "autobench": "AutoBench 2026",
         "tau2-bench": "tau2-bench per domain", "tau2-bench-pooled": "tau2-bench pooled",
         "response-bank": "the LLM Routing Response Bank"}
# dataset: (folder of its 13.13, 13.10, 13.12 or 13.14 script, the committed file whose summary it gives)
SOURCES = {"llmrouterbench": (FOLDER, "results.json"), "autobench": (AUTOBENCH_FOLDER, "results.json"),
           "tau2-bench": (TAU2_FOLDER, "results.json"), "tau2-bench-pooled": (TAU2_FOLDER, "pooled.json"),
           "response-bank": (RESPONSE_BANK_FOLDER, "results.json")}
# the datasets whose script drops the items with a null token count first (13.13 and, v1.328, 13.14)
SELECTED = ("llmrouterbench", "response-bank")
STRATEGIES = ("pick", "size rule")
# v1.331: the rule that reads only each item's input size, measured where `size rule` may switch
INPUT_RULE = "input rule"
# the datasets whose report gives it (v1.331): the one where `size rule`, its cost floor, cuts a measurable share
INPUT_RULE_DATASETS = ("response-bank",)
COMPARED = ("delegate_cheaper", "inline_cheaper")
HEADER = "  flavor          bar  strategy    cells  switched / items     share  cost / decision  success - decision  better"
INPUT_HEADER = "  bar  point  strategy    cells  switched / items     share  cost / decision  success - decision  better"


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


def _inline_calls(p, point, k, rd, a, o):
    """13.9 v1.74 always inline for one held-out item of a row with per-call sizes, a model without
    tiers: its k calls read rd and write o, and leave a + o in the context."""
    c, t = point["context_tokens"], point["carry_turns"]
    base = k * c if point["inline_separate_call"] else (k - 1) * c
    if "cached_read_ratio" in point:
        base = base * point["cached_read_ratio"]
    if point["inline_separate_call"]:
        return p.base_cost(base + rd, o) + (1 + t) * p.base_cost(a + o, 0)
    return p.base_cost(base + rd, o) + t * p.base_cost(a + o, 0)


def _delegate_calls(p, d, point, k, rd, o):
    """13.9 v1.74 always delegate for one held-out item of a row with per-call sizes, models
    without tiers: the delegate's k calls read rd and write o after the brief."""
    b, r, t = point["brief_tokens"], point["result_tokens"], point["carry_turns"]
    return p.base_cost(0, b) + d.base_cost(k * b + rd, o) + (1 + t) * p.base_cost(b + r, 0)


def _calls(r):
    """(K, Rd, A, O) of a row with per-call sizes (13.9 v1.74), or None without them."""
    if "call_input_tokens" not in r and "call_output_tokens" not in r:
        return None
    a, b = r["call_input_tokens"], r["call_output_tokens"]
    k = len(a)
    rd = sum((k - j) * x for j, x in enumerate(a)) + sum((k - j - 1) * y for j, y in enumerate(b))
    return k, rd, sum(a), sum(b)


def _inline_item(p, point, row):
    return _inline(p, point, row[1], row[2]) if row[3] is None else _inline_calls(p, point, *row[3])


def _delegate_item(p, d, point, row):
    if row[3] is None:
        return _delegate(p, d, point, row[1], row[2])
    k, rd, _a, o = row[3]
    return _delegate_calls(p, d, point, k, rd, o)


def _mask(flags):
    return sum(1 << j for j, f in enumerate(flags) if f)


def _exact(values):
    """Each float as an integer numerator over one common power of two, so sums of them compare exactly."""
    ratios = [v.as_integer_ratio() for v in values]
    top = max((d for _, d in ratios), default=1)
    return [n * (top // d) for n, d in ratios]


def threshold(ranked, xs, diffs, flags, inline_mode):
    """The input rule's threshold on one cell (DESIGN 13.8 v1.331): the rule takes inline on an item
    whose parent input size x is under it and delegates the rest. `ranked` lists the task's item
    positions by ascending x, `diffs` each item's exact inline minus delegate cost, `flags` the
    held-out positions. Candidates are 0 (every item delegated), each distinct x of a calibration
    item above the smallest, and None (no bound, every item inline); the threshold is the one whose
    calibration items' summed cost is lowest, compared exactly, and on a tie the one that switches
    the fewest calibration items from the cell's mode. Held-out items are never read."""
    cal = [j for j in ranked if not flags[j]]
    n = len(cal)
    best = best_tau = None
    total = k = 0
    while True:
        key = (total, n - k if inline_mode else k)
        if best is None or key < best:
            best, best_tau = key, (0 if k == 0 else xs[cal[k]] if k < n else None)
        if k == n:
            return best_tau
        x = xs[cal[k]]
        while k < n and xs[cal[k]] == x:
            total += diffs[cal[k]]
            k += 1


def tally(rows, registry, full, input_rule=False):
    """Per summary row (bar, flavor, point, parent) and strategy: the decision's and the strategy's
    (success, cost) as 13.9 aggregates them, and the switched and held-out items of the cells the
    strategy may change. Also returns the number of path pairs rebuilt. A row with per-call sizes
    is priced on its own calls (13.9 v1.74). With `input_rule` each row also has the `input rule`
    strategy (v1.331) on the cells `size rule` may change. Raises ValueError on a rebuilt cost or
    count that is not its cell's, a tiered model, or, with `input_rule`, a row with per-call sizes."""
    config = full["config"]
    points, seeds, fraction = config["points"], config["seeds"], config["calibration_fraction"]
    table, order = {}, {}
    for r in rows:
        if (r["task"], r["item"]) not in table:
            order.setdefault(r["task"], []).append(r["item"])
        table.setdefault((r["task"], r["item"]), {})[r["model"]] = (
            r["correct"], r["input_tokens"], r["output_tokens"], _calls(r))
    for m in registry.models:
        if m.price_tiers:
            raise ValueError(f"model {m.id!r} has price tiers, which this script does not rebuild")
    if input_rule and any(v[3] is not None for models in table.values() for v in models.values()):
        raise ValueError("the input rule reads single-call rows only, and the matrix has per-call sizes")
    held = {}
    for task, items in order.items():
        for seed in seeds:
            chosen = set(split_items(items, seed, fraction)[1])
            flags = [i in chosen for i in items]
            held[task, seed] = (flags, _mask(flags), sum(flags))
    ok = {(task, m): _mask(table[task, i][m][0] for i in items)
          for task, items in order.items() for m in {m for i in items for m in table[task, i]}}
    vectors, pairs = {}, {}
    ranks, exact, rules = {}, {}, {}
    names = ("decision",) + STRATEGIES + ((INPUT_RULE,) if input_rule else ())
    out = {}
    for cell in full["cells"]:
        task, seed, index, parent, d = (cell[k] for k in ("task", "seed", "point", "parent", "delegate"))
        key = (task, index, parent, d)
        if key not in vectors:
            p, dm, point = registry.get(parent), registry.get(d), points[index]
            ci = [_inline_item(p, point, table[task, i][parent]) for i in order[task]]
            cd = [_delegate_item(p, dm, point, table[task, i][d]) for i in order[task]]
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
            s: {"seeds": {}, "switched": 0, "items": 0, "cells": 0} for s in names})
        compared = cell["reason"] in COMPARED
        if input_rule and compared:
            rule = pair + (cell["mode"],)
            if rule not in rules:
                if (task, parent) not in ranks:
                    xs = [table[task, i][parent][1] for i in order[task]]
                    ranks[task, parent] = (xs, sorted(range(len(xs)), key=xs.__getitem__))
                xs, ranked = ranks[task, parent]
                if key not in exact:
                    both = _exact(ci + cd)
                    exact[key] = [a - b for a, b in zip(both[:len(ci)], both[len(ci):])]
                tau = threshold(ranked, xs, exact[key], flags, cell["mode"] == "inline")
                below = [tau is None or x < tau for x in xs]
                take = hm & _mask(below)
                moved = (hm & ~take).bit_count() if cell["mode"] == "inline" else take.bit_count()
                rules[rule] = ((take & ok[task, parent]).bit_count() + ((hm & ~take) & ok[task, d]).bit_count(),
                               fsum(a if b else c for a, c, b, f in zip(ci, cd, below, flags) if f), moved)
        for s in names:
            if s == "decision" or (s != "pick" and not compared):
                c_ok, c_cost = cell["correct"]["decision"], cell["cost_usd"]["decision"]
            else:
                if s == INPUT_RULE:
                    c_ok, c_cost, moved = rules[pair + (cell["mode"],)]
                    row[s]["switched"] += moved
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


def _columns(group, s):
    """The columns from `cells` to `better` of strategy `s` over a group of rows."""
    cells = sum(row[s]["cells"] for row in group)
    switched = sum(row[s]["switched"] for row in group)
    n = sum(row[s]["items"] for row in group)
    cost = fsum(row[s]["cost_usd"] for row in group)
    dec_cost = fsum(row["decision"]["cost_usd"] for row in group)
    gain = fsum(row[s]["success"] - row["decision"]["success"] for row in group) / len(group)
    better = sum(row[s]["success"] >= row["decision"]["success"]
                 and row[s]["cost_usd"] < row["decision"]["cost_usd"] for row in group)
    return (f"{cells:>5}  {switched:>8,} / {n:<9,}  "
            f"{_share(switched, n):>6}  {_share(cost, dec_cost):>15}  {gain:>+18.4f}  {better:>6}")


def _largest(out, flavor, s):
    """The line naming the row of `flavor` with the largest cost cut of `s` at no less success."""
    best = None
    for (bar, f, index, parent), row in out.items():
        if f != flavor or row[s]["success"] < row["decision"]["success"]:
            continue
        cut = row["decision"]["cost_usd"] - row[s]["cost_usd"]
        if cut > 0 and (best is None or cut > best[0]):
            best = (cut, bar, index, parent, row)
    if best is None:
        return f"  largest cost cut at no less success, {s}, {flavor}: no row"
    _, bar, index, parent, row = best
    return (f"  largest cost cut at no less success, {s}, {flavor}: bar {bar}, point {index}, "
            f"parent {parent}: decision {row['decision']['success']:.4f} at "
            f"{row['decision']['cost_usd']:.4f} USD, {s} {row[s]['success']:.4f} at "
            f"{row[s]['cost_usd']:.4f}")


def _input_rule_lines(out, config):
    """v1.331: per flavor where `size rule` may change a cell, `size rule` and `input rule` by bar and point."""
    lines = []
    for flavor in config["flavors"]:
        if not any(row["size rule"]["cells"] for (_, f, _, _), row in out.items() if f == flavor):
            continue
        lines.append(f"  input rule, {flavor}: on the cells size rule may change, inline when the parent's input "
                     "tokens on the item are under a threshold set on the cell's calibration half")
        lines.append(INPUT_HEADER)
        for bar in config["bars"]:
            for index in list(range(len(config["points"]))) + ["all"]:
                group = [row for (b, f, i, _), row in out.items()
                         if (b, f) == (bar, flavor) and index in (i, "all")]
                for s in ("size rule", INPUT_RULE):
                    lines.append(f"  {bar:<3}  {index:<5}  {s:<10}  {_columns(group, s)}")
        lines.append(_largest(out, flavor, INPUT_RULE))
    return lines


def report(rows, registry, full, name="LLMRouterBench", input_rule=False) -> list:
    """The lines the script prints, from the matrix rows, the registry and the 13.9 run on them;
    `name` is the dataset's in the title line. With `input_rule` the lines end with the v1.331
    input rule's table."""
    rows = list(rows)
    out, pairs = tally(rows, registry, full, input_rule)
    for (bar, flavor, index, parent), row in out.items():
        for r in full["summary"]:
            if (r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]) == (bar, flavor, index, parent, "decision"):
                if (r["success"], r["cost_usd"]) != (row["decision"]["success"], row["decision"]["cost_usd"]):
                    raise ValueError(f"the decision row is not the summary's: bar {bar}, {flavor}, "
                                     f"point {index}, parent {parent!r}")
    items = {(r["task"], r["item"]) for r in rows}
    config = full["config"]
    lines = [
        f"Per-item delegation paths on {name}: each held-out item's cheaper path by list price at its own sizes, against the per-task decision",
        f"matrix: {len(rows):,} rows, {len(items):,} items, {_count(len(full['tasks']), 'task')}, "
        f"{_count(len(registry.models), 'model')}; {len(full['cells']):,} cells, {pairs:,} path pairs rebuilt, "
        "each equal to its cell's inline and delegate costs and correct counts",
        HEADER,
    ]
    for flavor in config["flavors"]:
        for bar in config["bars"]:
            group = [row for (b, f, _, _), row in out.items() if (b, f) == (bar, flavor)]
            for s in STRATEGIES:
                lines.append(f"  {flavor:<14}  {bar:<3}  {s:<10}  {_columns(group, s)}")
    for flavor in config["flavors"]:
        parts = []
        for index in range(len(config["points"])):
            group = [row for (_, f, i, _), row in out.items() if (f, i) == (flavor, index)]
            parts.append(f"{index}: {_share(sum(r['pick']['switched'] for r in group), sum(r['pick']['items'] for r in group))}")
        lines.append(f"  pick, switched share by point, {flavor}: " + ", ".join(parts))
    for flavor in config["flavors"]:
        for s in STRATEGIES:
            lines.append(_largest(out, flavor, s))
    if input_rule:
        lines.extend(_input_rule_lines(out, config))
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


def rerun(matrix, root=ROOT, dataset="llmrouterbench", registry=None) -> tuple:
    """The 13.13 run on the matrix (with `dataset="autobench"` the 13.10 base-grid run on it and the
    `registry` pool file; with `"tau2-bench"` or `"tau2-bench-pooled"` the 13.12 run on it and the
    committed registry; with `"response-bank"` the 13.14 run on the rows its `select_rows` keeps and
    the committed registry, v1.328), checked against the committed summary: (rows, registry, run).
    Shared with research/delegation_reasons.py (DESIGN 13.8 v1.253)."""
    root = Path(root)
    if dataset not in DATASETS:
        raise ValueError(f"dataset must be one of {', '.join(DATASETS)}, got {dataset!r}")
    if dataset == "autobench" and registry is None:
        raise ValueError("--dataset autobench needs --registry")
    if dataset != "autobench" and registry is not None:
        raise ValueError("--registry is only used with --dataset autobench")
    folder, name = SOURCES[dataset]
    script = _load(f"research_per_item_delegation_{dataset.replace('-', '_')}", root / folder / "results.py")
    try:
        pool = Registry.load(root / folder / "registry.json" if registry is None else registry)
        committed = json.loads((root / folder / name).read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        where = folder if registry is None else f"{folder} or {registry}"
        raise ValueError(f"{where}: cannot read ({exc})") from None
    rows = _read_rows(matrix)
    if dataset in SELECTED:
        rows, _dropped = script.select_rows(rows, [m.id for m in pool.models])
    full = evaluate_delegation(rows, pool, bars=list(script.BARS), points=script.points(),
                               seeds=range(script.SEEDS))
    if full["summary"] != committed.get("summary"):
        raise ValueError(f"the run's summary is not the one in {folder}/{name}")
    return rows, pool, full


def run(matrix, root=ROOT, dataset="llmrouterbench", registry=None) -> list:
    """`rerun`, then `report` on its rows, registry and run."""
    rows, pool, full = rerun(matrix, root, dataset, registry)
    return report(rows, pool, full, name=NAMES[dataset], input_rule=dataset in INPUT_RULE_DATASETS)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="per_item_delegation.py", description=__doc__.splitlines()[0])
    parser.add_argument("--matrix", required=True,
                        help="the converter's output (JSONL): LLMRouterBench, AutoBench 2026 with --dataset autobench, "
                             "tau2-bench --calls with --dataset tau2-bench or tau2-bench-pooled, the response "
                             "bank's default output with --dataset response-bank")
    parser.add_argument("--dataset", choices=DATASETS, default="llmrouterbench",
                        help="the delegation evidence to rerun (default: llmrouterbench, DESIGN 13.13; autobench, 13.10; "
                             "tau2-bench and tau2-bench-pooled, 13.12 results.json and pooled.json; response-bank, "
                             "13.14)")
    parser.add_argument("--registry", help="with --dataset autobench: the AutoBench converter's --registry output")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        lines = run(args.matrix, args.root, args.dataset, args.registry)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
