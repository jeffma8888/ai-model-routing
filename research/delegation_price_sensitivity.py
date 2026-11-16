"""How far one model's wrong list price moves a committed delegation decision (DESIGN 12.22 v1.424, row R39).

Usage:
  python research/delegation_price_sensitivity.py --matrix autobench-tokens.jsonl --registry autobench-pool.json [--root PATH]

Runs the AutoBench 2026 converter's `--task-by all --tokens` matrix and `--registry` pool on the 13.10 base
and variant grids, as evidence/delegation/results.py makes results.json and variants.json, through
research/reread_sensitivity.py's `inputs` and `checked`: each run's config, tasks and summary must be the
committed file's, and each cell's decision and held-out sums re-decided at the committed prices (sigma 1.0
and W = B) the run's. Then, for each model of the run in ID order and each factor 0.5 and 2.0, it rebuilds
every cell's router (13.9 `_router`, on the run's own calibration half) on a registry whose one change is
that model's `price_in` and `price_out` times the factor, and re-decides the cell. A cell's decision changes
when its mode or its model does. Both picks are scored on the cell's held-out half at the committed
registry's 13.2 costs: the error is in the price the decision believes, and the bill is at the list price,
as research/price-sensitivity.md scores routing. A run is one model and one factor. Per file, flavor and bar
it prints how many of the runs change a cell, the most cells one run changes and that run's share, how many
of them go inline, their held-out success gap (new correct minus committed correct over their held-out
items) and cost ratio (new over committed), the run's cost ratio over all the cells, and the run: the first,
in model and factor order, of those that change the most. Then per file the changed cells of all runs by
point, and each model's changed cells over every flavor and bar at each factor, with how many go inline.

Standard library and the model_routing package. Read by research/delegation-price-sensitivity.md. Exit 0, or
2 with one `error: ...` line where research/reread_sensitivity.py exits 2: a missing or unreadable file, a
row 13.9 refuses, a model with price tiers, a row with per-call sizes, a run whose config, tasks or summary
is not the committed file's, or a re-decided cell or held-out sum at the committed prices that is not the
run's.
"""

import argparse
import dataclasses
import importlib.util
import sys
from math import fsum
from pathlib import Path

from model_routing import Registry
from model_routing.delegation_eval import _router

ROOT = Path(__file__).resolve().parents[1]
FACTORS = (0.5, 2.0)
HEADER = ("  flavor          bar  runs moving  most changed / cells  share  to inline  success gap  cost ratio  "
          "all cost ratio  by")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RS = _load("research_delegation_price_reread", Path(__file__).resolve().parent / "reread_sensitivity.py")


def scaled(registry, model, factor):
    """The registry with one model's input and output prices times `factor` and every other model as it is."""
    return Registry(dataclasses.replace(m, price_in=m.price_in * factor, price_out=m.price_out * factor)
                    if m.id == model else m for m in registry.models)


def picks(run, config, registry):
    """Each cell's (mode, model) re-decided by the 13.9 router rebuilt on `registry`, in the run's cell order."""
    routers = {}
    out = []
    for cell in run.result["cells"]:
        key = (cell["task"], cell["seed"], cell["bar"])
        if key not in routers:
            routers[key] = _router(registry, cell["task"], run.calibrated[cell["task"], cell["seed"]], cell["bar"],
                                   config["min_samples"], config["confidence"])
        point = config["points"][cell["point"]]
        k = run.calibrated[cell["task"], cell["seed"]].get("k")
        decision = routers[key].decide_delegation(cell["task"], cell["parent"], cell["flavor"],
                                                  **(point if k is None else dict(point, work_calls=k)))
        out.append((decision.mode, decision.model))
    return out


def report(rows, pool, root, name, grid, dr, title):
    """The report lines of one committed file: the check, then each model's price times each factor."""
    run, got, rel = RS.checked(rows, pool, root, name, grid, dr)
    config = got["config"]
    cells = run.result["cells"]
    runs = [(m, f) for m in run.models for f in FACTORS]
    lines = [f"{title}, {grid} grid (`{rel}`): {len(cells):,} cells, {len(config['bars'])} bars, "
             f"{len(config['flavors'])} flavors, {len(config['points'])} points, {len(config['parents'])} parents, "
             f"{len(config['seeds'])} seeds, {len(run.models)} models, so {len(runs)} runs; every cell's decision "
             "and held-out sum reproduced at the committed prices", HEADER]
    held = []  # each cell's committed pick and held-out (correct, cost, items) at the committed prices
    for cell in cells:
        point = config["points"][cell["point"]]
        was = (cell["mode"], cell["model"])
        held.append((was, run.held_sum(cell, point, *was, 1.0, point["brief_tokens"])))
    new = {r: picks(run, config, scaled(pool, *r)) for r in runs}
    by_point = [0] * len(config["points"])
    by_model = {r: [0, 0] for r in runs}  # changed cells, of them to inline
    for flavor in config["flavors"]:
        for bar in config["bars"]:
            sel = [i for i, c in enumerate(cells) if c["flavor"] == flavor and c["bar"] == bar]
            moving, best = 0, None  # best: (changed, run, inline, gap, ratio, all ratio)
            for r in runs:
                changed = inline = 0
                gap = [0, 0, 0]
                new_cost, old_cost, all_new, all_old = [], [], [], []
                for i in sel:
                    cell, (was, old) = cells[i], held[i]
                    pick = new[r][i]
                    now = old if pick == was else run.held_sum(cell, config["points"][cell["point"]], *pick, 1.0,
                                                               config["points"][cell["point"]]["brief_tokens"])
                    all_new.append(now[1])
                    all_old.append(old[1])
                    if pick != was:
                        changed += 1
                        inline += pick[0] == "inline"
                        by_point[cell["point"]] += 1
                        gap = [gap[0] + now[0], gap[1] + old[0], gap[2] + old[2]]
                        new_cost.append(now[1])
                        old_cost.append(old[1])
                by_model[r][0] += changed
                by_model[r][1] += inline
                if changed:
                    moving += 1
                    if best is None or changed > best[0]:
                        best = (changed, r, inline, f"{(gap[0] - gap[1]) / gap[2]:+.4f}",
                                f"{fsum(new_cost) / fsum(old_cost):.3f}", f"{fsum(all_new) / fsum(all_old):.3f}")
            if best is None:
                best = (0, None, 0, "-", "-", "1.000")
            changed, r, inline, gap, ratio, all_ratio = best
            by = "-" if r is None else f"{r[0]} times {r[1]}"
            lines.append(f"  {flavor:<14}  {bar:<3}  {moving:>6} / {len(runs):<3}  {changed:>12,} / {len(sel):<5,}  "
                         f"{100 * changed / len(sel):>4.1f}%  {inline:>9}  {gap:>11}  {ratio:>10}  "
                         f"{all_ratio:>14}  {by}")
    lines.append(f"  changed cells by point, all {len(runs)} runs: "
                 + ", ".join(f"{i}: {n:,}" for i, n in enumerate(by_point)))
    for m in run.models:
        (a, ai), (b, bi) = by_model[m, FACTORS[0]], by_model[m, FACTORS[1]]
        lines.append(f"  {m}: times {FACTORS[0]} changes {a:,} cells ({ai:,} to inline), "
                     f"times {FACTORS[1]} changes {b:,} ({bi:,} to inline)")
    return lines


def run(matrix, registry, root=ROOT):
    """The report lines of the AutoBench 2026 delegation results, on what research/reread_sensitivity.py's
    `inputs` reads for them."""
    title, files, dr, rows, pool = RS.inputs(matrix, registry, root, "autobench")
    lines = [f"One model's list price halved or doubled on the {title} delegation results: each cell re-decided "
             f"with that model's input and output prices times {FACTORS[0]} or {FACTORS[1]}, both picks scored at "
             "the committed prices"]
    for name, grid in files:
        lines += report(rows, pool, root, name, grid, dr, title)
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--matrix", required=True, help="the AutoBench converter's --task-by all --tokens matrix")
    parser.add_argument("--registry", required=True, help="the AutoBench converter's --registry pool")
    parser.add_argument("--root", default=str(ROOT), help="the repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        lines = run(args.matrix, args.registry, Path(args.root))
    except (ValueError, KeyError, TypeError, OSError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
