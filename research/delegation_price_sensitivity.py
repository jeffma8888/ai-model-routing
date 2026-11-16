"""How far one model's wrong list price moves a committed delegation decision (DESIGN 12.22 v1.424, row R39).

Usage:
  python research/delegation_price_sensitivity.py --matrix autobench-tokens.jsonl --registry autobench-pool.json [--root PATH]
  python research/delegation_price_sensitivity.py --dataset llmrouterbench --matrix llmrouterbench-matrix.jsonl [--root PATH]
  python research/delegation_price_sensitivity.py --dataset response-bank --matrix response-bank-matrix.jsonl [--root PATH]
  python research/delegation_price_sensitivity.py --dataset tau2-bench --matrix tau2-calls.jsonl [--root PATH]
  python research/delegation_price_sensitivity.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl [--root PATH]

Runs the AutoBench 2026 converter's `--task-by all --tokens` matrix and `--registry` pool on the 13.10 base
and variant grids, as evidence/delegation/results.py makes results.json and variants.json, through
research/reread_sensitivity.py's `inputs` and `checked`: each run's config, tasks and summary must be the
committed file's, and each cell's decision and held-out sums re-decided at the committed prices (sigma 1.0
and W = B) the run's. Then, for each model of the run in ID order and each factor 0.5 and 2.0, it rebuilds
the router (13.9 `_router`, on the run's own calibration half) of each cell on a registry whose one change is
that model's `price_in` and `price_out` times the factor, and re-decides every `cost_effective` cell, while
each `cost_blind` cell keeps its committed pick (v1.429, row T15): no price can move it, since a candidate's
5.2 `routing_cost` is 0.0 outside `cost_effective` and every 13.5 row that compares costs is a `cost_effective`
one, so the cut prints what re-deciding every cell prints, in half the decisions. A cell's decision changes
when its mode or its model does. Both picks are scored on the cell's held-out half at the committed
registry's 13.2 costs: the error is in the price the decision believes, and the bill is at the list price,
as research/price-sensitivity.md scores routing. A run is one model and one factor. Per file, flavor and bar
it prints how many of the runs change a cell, the most cells one run changes and that run's share, how many
of them go inline, their held-out success gap (new correct minus committed correct over their held-out
items) and cost ratio (new over committed), the run's cost ratio over all the cells, and the run: the first,
in model ID, then factor, order, of those that change the most. Then per file the changed cells of all runs by
point, and each model's changed cells over every flavor and bar at each factor, with how many go inline.
With `--dataset llmrouterbench` (v1.425, row R39b) it runs instead the 13.13 grid on the LLMRouterBench
converter's default matrix, on the rows evidence/llmrouterbench-delegation/results.py's `select_rows` keeps for
that folder's committed registry.json (no `--registry`), checked against its results.json, as
research/reread_sensitivity.py's `--dataset llmrouterbench` reads and checks it; on a run of more than one task
the header names the task count and a line after the changed cells by point gives them by task, in the run's
task order. `--dataset response-bank` (v1.426, row R39c) runs the 13.14 grid of evidence/response-bank-delegation/
results.py in the same way, on the response-bank converter's default matrix and that folder's registry.json,
checked against its results.json, as research/reread_sensitivity.py's `--dataset response-bank` reads and checks it.
`--dataset tau2-bench` (`tau2-bench-pooled`, v1.427, row R39d) runs the 13.12 grid of evidence/tau2-bench-delegation/
results.py on the tau2-bench converter's `--calls` (`--calls --task-by all`) matrix and that folder's registry.json,
checked against results.json (pooled.json), as research/reread_sensitivity.py's same options read and check it; those
rows carry per-call sizes (13.9 v1.74), so each held-out item is priced by that script's `call_cost` and each
decision's `work_calls` is the calibration half's median call count.

Standard library and the model_routing package. Read by research/delegation-price-sensitivity.md. Exit 0, or
2 with one `error: ...` line where research/reread_sensitivity.py exits 2: a missing or unreadable file, a
row 13.9 refuses, a model with price tiers, a row with per-call sizes outside the tau2-bench runs or one without
them in those runs, a run whose config, tasks or summary is not the committed file's, a re-decided cell or held-out sum at the committed prices that is not the
run's, `--dataset autobench` without `--registry` or another dataset with it.
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
# the datasets this script measures, as research/reread_sensitivity.py's DATASETS names them
DATASETS = ("autobench", "llmrouterbench", "response-bank", "tau2-bench", "tau2-bench-pooled")
# the flavors whose cells a run re-decides; a `cost_blind` cell keeps its committed pick, which no price can move
# (v1.429, row T15); the tests set both flavors to run the v1.424 to v1.428 re-decision of every cell
REDECIDED = ("cost_effective",)
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
    """Each cell's (mode, model) re-decided by the 13.9 router rebuilt on `registry`, in the run's cell order; a
    cell of a flavor outside `REDECIDED` keeps its committed pick (v1.429)."""
    routers = {}
    out = []
    for cell in run.result["cells"]:
        if cell["flavor"] not in REDECIDED:
            out.append((cell["mode"], cell["model"]))
            continue
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


def report(rows, pool, root, name, grid, dr, title, dataset="autobench"):
    """The report lines of one committed file: the check, then each model's price times each factor."""
    run, got, rel = RS.checked(rows, pool, root, name, grid, dr, dataset)
    config = got["config"]
    cells = run.result["cells"]
    tasks = list(got["tasks"])
    runs = [(m, f) for m in run.models for f in FACTORS]
    lines = [f"{title}, {grid} grid (`{rel}`): {len(cells):,} cells, "
             + (f"{len(tasks)} tasks, " if len(tasks) > 1 else "") + f"{len(config['bars'])} bars, "
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
    by_task = dict.fromkeys(tasks, 0)
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
                        by_task[cell["task"]] += 1
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
    if len(tasks) > 1:
        lines.append(f"  changed cells by task, all {len(runs)} runs: "
                     + ", ".join(f"{t} {n:,}" for t, n in by_task.items()))
    for m in run.models:
        (a, ai), (b, bi) = by_model[m, FACTORS[0]], by_model[m, FACTORS[1]]
        lines.append(f"  {m}: times {FACTORS[0]} changes {a:,} cells ({ai:,} to inline), "
                     f"times {FACTORS[1]} changes {b:,} ({bi:,} to inline)")
    return lines


def run(matrix, registry=None, root=ROOT, dataset="autobench"):
    """The report lines of one dataset's delegation results, on what research/reread_sensitivity.py's
    `inputs` reads for them."""
    if dataset not in DATASETS:
        raise ValueError(f"dataset must be one of {', '.join(DATASETS)}, got {dataset!r}")
    title, files, dr, rows, pool = RS.inputs(matrix, registry, root, dataset)
    lines = [f"One model's list price halved or doubled on the {title} delegation results: each cell re-decided "
             f"with that model's input and output prices times {FACTORS[0]} or {FACTORS[1]}, both picks scored at "
             "the committed prices"]
    for name, grid in files:
        lines += report(rows, pool, root, name, grid, dr, title, dataset)
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--matrix", required=True,
                        help="the AutoBench converter's --task-by all --tokens matrix, or with --dataset "
                             "llmrouterbench or response-bank that dataset's converter's default output, or with "
                             "tau2-bench (tau2-bench-pooled) the tau2-bench converter's --calls (--calls --task-by "
                             "all) output")
    parser.add_argument("--registry", help="with --dataset autobench: the AutoBench converter's --registry pool")
    parser.add_argument("--dataset", choices=DATASETS, default="autobench",
                        help="the delegation results to re-decide (default: autobench, DESIGN 13.10; "
                             "llmrouterbench, 13.13; response-bank, 13.14; tau2-bench and tau2-bench-pooled, "
                             "13.12 results.json and pooled.json)")
    parser.add_argument("--root", default=str(ROOT), help="the repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        lines = run(args.matrix, args.registry, Path(args.root), args.dataset)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
