"""How far one model's wrong price moves `cost_effective` routing on LLMRouterBench (DESIGN 12.22 v1.403)

Usage:
  python research/price_sensitivity.py --matrix llmrouterbench-matrix.jsonl

Runs `evaluate` (DESIGN 12.3) on the LLMRouterBench matrix that the converter writes, flavor
`cost_effective`, at the lowest and highest bars of evidence/llmrouterbench/results.json with its
seeds and options, and rebuilds each cell's router as 12.3 builds it with one model's mean
calibration cost times 0.5 or 2.0, one model at a time, every other model's as recorded. A scaled
pick is scored at the recorded held-out costs, since a wrong price moves the choice and not the bill.
It prints, per bar, the committed routed success and cost, then per model and factor the (task, seed)
cells whose routed model changes and the held-out success and cost of the new picks against the
committed row, then the range of each. Unscaled, the rebuilt router must pick each cell's routed model
and the pooled rows must be the committed ones. Standard library and the model_routing package. Read
by research/price-sensitivity.md. Exit 0, or 2 with one `error: ...` line on a missing or unreadable
file, a row `load_outcomes` refuses, a missing key, a config without `cost_effective`, a rebuilt
router that does not pick the routed model or a row that is not the committed one.
"""

import argparse
import json
import math
import sys
from pathlib import Path

from model_routing import Router, Stats, Task, evaluate, load_outcomes, split_items
from model_routing.evaluate import _routed_registry

ROOT = Path(__file__).resolve().parents[1]
RESULTS = "evidence/llmrouterbench/results.json"
FLAVOR = "cost_effective"
# powers of two, so a scaled mean is the mean of the scaled costs exactly
FACTORS = (0.5, 2.0)


def calibration(outcomes, tasks, seeds, fraction) -> dict:
    """12.3's calibration sums per (task, seed): (calibration items, {model: items scored 1},
    {model: mean cost})."""
    table = {}
    for o in outcomes:
        table.setdefault(o.task, {}).setdefault(o.item, {})[o.model] = o
    sums = {}
    for task in tasks:
        rows = table[task]
        models = sorted({m for by_model in rows.values() for m in by_model})
        for seed in seeds:
            cal, _held = split_items(rows, seed, fraction)
            sums[task, seed] = (len(cal), {m: sum(rows[i][m].correct for i in cal) for m in models},
                                {m: math.fsum(rows[i][m].cost_usd for i in cal) / len(cal) for m in models})
    return sums


def route(n_cal, succ, mean_cost, task, bar, min_samples, confidence) -> str:
    """The routed model of the router 12.3 builds for one `cost_effective` cell over `mean_cost`."""
    stats = Stats()
    for m in succ:
        stats.add(task, m, succ[m], n_cal)
    spec = Task(name=task, bar=bar, min_samples=min_samples, confidence=confidence,
                independent_of_generator=False, expected_input_tokens=1, expected_output_tokens=0,
                on_no_model="best_available", max_fallbacks=0)
    return Router(_routed_registry(succ, mean_cost), {task: spec}, stats).select(task, FLAVOR).primary


def picks(sums, cells, model, factor, min_samples, confidence) -> dict:
    """{(task, seed): routed model} for `cells` (one bar) with `model`'s mean cost times `factor`."""
    out = {}
    for c in cells:
        n_cal, succ, mean_cost = sums[c["task"], c["seed"]]
        scaled = {m: x * factor if m == model else x for m, x in mean_cost.items()}
        out[c["task"], c["seed"]] = route(n_cal, succ, scaled, c["task"], c["bar"], min_samples, confidence)
    return out


def pooled(cells, seeds, chosen) -> tuple:
    """Means over `seeds` of the pooled held-out success and cost of the models `chosen` names per
    (task, seed), read from each cell's `model:` values, as 12.3's summary pools a row."""
    success, cost = [], []
    for seed in seeds:
        cs = [c for c in cells if c["seed"] == seed]
        right = sum(round(c["success"]["model:" + chosen[c["task"], seed]] * c["held_out_items"]) for c in cs)
        success.append(right / sum(c["held_out_items"] for c in cs))
        cost.append(math.fsum(c["cost_usd"]["model:" + chosen[c["task"], seed]] for c in cs))
    return math.fsum(success) / len(success), math.fsum(cost) / len(cost)


def _check(rel, committed, bar, success, cost):
    rows = [r for r in committed["summary"] if (r["bar"], r["flavor"], r["strategy"]) == (bar, FLAVOR, "routed")]
    if len(rows) != 1:
        raise ValueError(f"{rel}: not one routed row at bar {bar}, {FLAVOR}")
    for mine, key in ((success, "success"), (cost, "cost_usd")):
        if abs(mine - rows[0][key]) > 1e-12 * max(abs(mine), abs(rows[0][key])):
            raise ValueError(f"{rel}: the routed {FLAVOR} row at bar {bar} is not the committed one ({key})")


def report(outcomes, committed, rel=RESULTS) -> list:
    """The printed lines; `committed` is the results file (its config and summary)."""
    config = committed["config"]
    if FLAVOR not in config["flavors"]:
        raise ValueError(f"{rel}: the config has no {FLAVOR} flavor")
    bars = [min(config["bars"]), max(config["bars"])]
    seeds = list(config["seeds"])
    min_samples, confidence = config["min_samples"], config["confidence"]
    result = evaluate(outcomes, bars=bars, seeds=seeds, flavors=[FLAVOR],
                      calibration_fraction=config["calibration_fraction"], min_samples=min_samples,
                      confidence=confidence)
    tasks = result["tasks"]
    models = sorted({m for t in tasks.values() for m in t["models"]})
    sums = calibration(outcomes, tasks, seeds, config["calibration_fraction"])
    lines = [f"LLMRouterBench ({rel}): {len(tasks)} tasks, {len(models)} models, "
             f"{sum(t['items'] for t in tasks.values()):,} items, {len(seeds)} seeds, flavor {FLAVOR}, "
             f"bars {bars[0]} and {bars[1]}, the lowest and highest of {len(config['bars'])}",
             f"the router is built with one model's calibration mean cost times {FACTORS[0]} or {FACTORS[1]}, "
             f"every other model's as recorded, and each pick is scored at the recorded held-out costs"]
    for bar in bars:
        cells = [c for c in result["cells"] if c["bar"] == bar]
        was = {(c["task"], c["seed"]): c["models"]["routed"] for c in cells}
        for (task, seed), m in picks(sums, cells, models[0], 1.0, min_samples, confidence).items():
            if m != was[task, seed]:
                raise ValueError(f"the rebuilt router of {task}, seed {seed}, bar {bar} does not pick its "
                                 f"routed model")
        success, cost = pooled(cells, seeds, was)
        _check(rel, committed, bar, success, cost)
        lines.append(f"bar {bar}: committed routed success {success:.4f}, cost {cost:.4f}; per model and factor, "
                     f"the cells of {len(cells):,} whose routed model changes, the held-out success with its gap "
                     f"and the cost with its ratio to the committed row")
        changed, gaps, ratios = [], [], []
        for model in models:
            parts = []
            for factor in FACTORS:
                now = picks(sums, cells, model, factor, min_samples, confidence)
                k = sum(now[key] != was[key] for key in was)
                s, x = pooled(cells, seeds, now)
                changed.append(k)
                gaps.append(s - success)
                ratios.append(x / cost)
                parts.append(f"times {factor}: {k:,} of {len(cells):,} cells change ({100 * k / len(cells):.1f}%), "
                             f"success {s:.4f} ({s - success:+.4f}), cost {x:.4f} ({x / cost:.3f})")
            lines.append(f"  {model}: " + "; ".join(parts))
        lines.append(f"  over the {len(changed)}: cells changed {min(changed):,} to {max(changed):,}, success gap "
                     f"{min(gaps):+.4f} to {max(gaps):+.4f}, cost ratio {min(ratios):.3f} to {max(ratios):.3f}")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="price_sensitivity.py", description=__doc__.splitlines()[0])
    parser.add_argument("--matrix", required=True, help="the LLMRouterBench converter's output (JSONL)")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root holding evidence/ (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        with open(Path(args.root) / RESULTS, encoding="utf-8") as fh:
            committed = json.load(fh)
        lines = report(load_outcomes(args.matrix), committed)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
