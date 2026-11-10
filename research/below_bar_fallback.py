"""Whether a route should go on below the bar after its clearing models fail, on LLMRouterBench (DESIGN 12.8 v1.191)

Usage:
  python research/below_bar_fallback.py --matrix llmrouterbench-matrix.jsonl

Runs `evaluate` (DESIGN 12.3) on the LLMRouterBench matrix that the converter writes, at the lowest
and highest bars of evidence/llmrouterbench/results.json with its seeds, flavors and options, and
rebuilds each cell's router as research/check_fallback.py does. Two routes per cell and per
`max_fallbacks` of 2 and every listed model: the 5.3 route, the router's primary then its next
`max_fallbacks` models, which come from the clearing models alone when one clears; and the
below-bar route, the same list then every other eligible measured model in the `best_available`
order (5.3), cut to the same `max_fallbacks`. Each held-out item is tried down a route until a
record scores 1 (DESIGN 7 with a check as good as the record's score), every attempt's cost spent.
It prints, per flavor and bar, both routes' pooled held-out success and cost and what the below-bar
route adds, then per task at each bar with every listed model. Each route's primary must be its
cell's routed model, and with no fallback each row must be the committed one. Standard library,
the model_routing package and research/check_fallback.py. Read by research/below-bar-fallback.md.
Exit 0, or 2 with one `error: ...` line on a missing or unreadable file, a row `load_outcomes`
refuses, a missing key, a route that does not start with the routed model or a row that is not the
committed one.
"""

import argparse
import importlib.util
import json
import math
import sys
from pathlib import Path

from model_routing import Model, Registry, Router, Stats, Task, evaluate, load_outcomes, split_items

ROOT = Path(__file__).resolve().parents[1]
RESULTS = "evidence/llmrouterbench/results.json"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CF = _load("research_check_fallback_for_below_bar", Path(__file__).resolve().with_name("check_fallback.py"))


def decide(succ, mean_cost, n_cal, task, flavor, bar, min_samples, confidence):
    """The decision of the router 12.3 builds for one cell, with every other model a fallback."""
    stats = Stats()
    for m in succ:
        stats.add(task, m, succ[m], n_cal)
    registry = Registry([Model(m, m, mean_cost[m] * 1_000_000, 0.0, 2 ** 62) for m in succ])
    spec = Task(name=task, bar=bar, min_samples=min_samples, confidence=confidence,
                independent_of_generator=False, expected_input_tokens=1, expected_output_tokens=0,
                on_no_model="best_available", max_fallbacks=len(succ) - 1)
    return Router(registry, {task: spec}, stats).select(task, flavor)


def routes(decision, max_fallbacks) -> tuple:
    """(the 5.3 route, the below-bar route) with `max_fallbacks`: the 5.3 list cut after the primary
    and `max_fallbacks` more; the same list then every other eligible measured model, sorted by
    5.3's `best_available` key (-quality_lb, routing_cost, model_id), cut the same way."""
    whole = (decision.primary, *decision.fallbacks)
    rest = sorted((c for c in decision.candidates if c.eligible and c.trials > 0 and c.model_id not in whole),
                  key=lambda c: (-c.quality_lb, c.routing_cost, c.model_id))
    below = whole + tuple(c.model_id for c in rest)
    return whole[:1 + max_fallbacks], below[:1 + max_fallbacks]


def _ratio(top, bottom):
    return "-" if bottom == 0 else f"{top / bottom:.3f}"


def report(outcomes, committed, rel=RESULTS) -> list:
    """The printed lines; `committed` is the results file (its config, summary and per_task)."""
    config = committed["config"]
    bars = [min(config["bars"]), max(config["bars"])]
    seeds, flavors = list(config["seeds"]), list(config["flavors"])
    fraction, min_samples, confidence = config["calibration_fraction"], config["min_samples"], config["confidence"]
    result = evaluate(outcomes, bars=bars, seeds=seeds, flavors=flavors, calibration_fraction=fraction,
                      min_samples=min_samples, confidence=confidence)
    tasks = result["tasks"]
    models = sorted({m for t in tasks.values() for m in t["models"]})
    table = {}
    for o in outcomes:
        table.setdefault(o.task, {}).setdefault(o.item, {})[o.model] = o
    halves, sums = {}, {}
    for task in tasks:
        for seed in seeds:
            halves[task, seed] = split_items(table[task], seed, fraction)
            sums[task, seed] = CF.calibration(table[task], halves[task, seed][0], models)
    every = len(models) - 1
    limits = (2, every)
    # (flavor, bar, kind, limit, seed, task) -> (items scored 1, held-out items, attempts, cost)
    got, lengths, clears, below = {}, {}, {}, {}
    for c in result["cells"]:
        task, seed, bar, flavor = c["task"], c["seed"], c["bar"], c["flavor"]
        cal, held = halves[task, seed]
        succ, mean_cost = sums[task, seed]
        decision = decide(succ, mean_cost, len(cal), task, flavor, bar, min_samples, confidence)
        if decision.primary != c["models"]["routed"]:
            raise ValueError(f"the rebuilt route of {task}, seed {seed}, bar {bar}, {flavor} does not "
                             f"start with its routed model")
        clears[flavor, bar] = clears.get((flavor, bar), 0) + (not decision.below_bar)
        for limit in (0, *limits):
            pair = routes(decision, limit)
            for kind, path in zip(("5.3", "below"), pair):
                correct, tries, spent = CF.replay(table[task], held, path)
                got[flavor, bar, kind, limit, seed, task] = (correct, len(held), tries, math.fsum(spent))
                lengths.setdefault((flavor, bar, kind, limit), set()).add(len(path))
            for key in ((flavor, bar, limit), (task, bar, limit)):
                below[key] = below.get(key, 0) + (pair[0] != pair[1])
    best = {}
    for (task, seed), (cal, held) in halves.items():
        correct, spent = CF.oracle(table[task], held, models)
        best[seed, task] = (correct, len(held), len(held), math.fsum(spent))

    def pooled(pick, only=None):
        """Means over seeds of (success, cost, attempts per item), pooled over the tasks or `only`."""
        success, cost, per = [], [], []
        for seed in seeds:
            cs = [pick(seed, t) for t in ([only] if only else tasks)]
            n = sum(x[1] for x in cs)
            success.append(sum(x[0] for x in cs) / n)
            cost.append(math.fsum(x[3] for x in cs))
            per.append(sum(x[2] for x in cs) / n)
        return CF._mean(success), CF._mean(cost), CF._mean(per)

    top, top_cost, _ = pooled(lambda seed, t: best[seed, t])
    for bar in bars:
        for flavor in flavors:
            CF._check(rel, CF._row(committed["summary"], rel, bar, flavor, "oracle"), top, top_cost,
                      f"the oracle {flavor} row at bar {bar}")
    n_cells = len(tasks) * len(seeds)
    lines = [f"LLMRouterBench ({rel}): {len(tasks)} tasks, {len(models)} models, "
             f"{sum(t['items'] for t in tasks.values()):,} items, {len(seeds)} seeds, bars {bars[0]} and {bars[1]}, "
             f"the lowest and highest of {len(config['bars'])}",
             "the 5.3 route is the router's primary then its next max_fallbacks models, from the clearing models "
             "alone when one clears; the below-bar route goes on after those to every other eligible measured "
             "model in the best_available order, up to max_fallbacks fallbacks; each held-out item is tried down "
             "a route until a record scores 1, and every attempt's cost is spent",
             f"oracle: success {top:.4f}, cost {top_cost:.4f}"]
    for flavor in flavors:
        for bar in bars:
            base, base_cost, _ = pooled(lambda seed, t: got[flavor, bar, "5.3", 0, seed, t])
            CF._check(rel, CF._row(committed["summary"], rel, bar, flavor, "routed"), base, base_cost,
                      f"the routed {flavor} row at bar {bar}")
            for task in tasks:
                ts, tc, _ = pooled(lambda seed, t: got[flavor, bar, "5.3", 0, seed, t], task)
                CF._check(rel, CF._row(committed["per_task"], rel, bar, flavor, "routed", task), ts, tc,
                          f"the routed {flavor} {task} row at bar {bar}")
            lines.append(f"{flavor} bar {bar}: no fallback success {base:.4f}, cost {base_cost:.4f}; "
                         f"a model clears the bar in {clears[flavor, bar]} of {n_cells} cells")
            for limit in limits:
                s1, c1, _ = pooled(lambda seed, t: got[flavor, bar, "5.3", limit, seed, t])
                s2, c2, p2 = pooled(lambda seed, t: got[flavor, bar, "below", limit, seed, t])
                n1, n2 = sorted(lengths[flavor, bar, "5.3", limit]), sorted(lengths[flavor, bar, "below", limit])
                part = CF.share(s2, s1, top)
                lines.append(f"  max_fallbacks {limit}: 5.3 route success {s1:.4f}, cost {c1:.4f}, routes of "
                             f"{n1[0]} to {n1[-1]} models; below-bar route success {s2:.4f}, cost {c2:.4f}, "
                             f"routes of {n2[0]} to {n2[-1]} models, attempts per item {p2:.3f}; it differs in "
                             f"{below[flavor, bar, limit]} of {n_cells} cells, adds success {s2 - s1:.4f} at "
                             f"{_ratio(c2, c1)} times the cost and recovers "
                             f"{'-' if part is None else f'{part:.3f}'} of the 5.3 route's gap to the oracle")
    lines.append(f"per task with max_fallbacks {every}, held-out success with the 5.3 route and the below-bar "
                 f"route, the cost of the second over the first's, and the oracle's:")
    for bar in bars:
        lines.append(f"bar {bar}:")
        for task in tasks:
            parts = []
            for flavor in flavors:
                s1, c1, _ = pooled(lambda seed, t: got[flavor, bar, "5.3", every, seed, t], task)
                s2, c2, _ = pooled(lambda seed, t: got[flavor, bar, "below", every, seed, t], task)
                parts.append(f"{flavor} from {s1:.4f} to {s2:.4f} at {_ratio(c2, c1)} times")
            lines.append(f"  {task} ({tasks[task]['items']:,} items): {', '.join(parts)}, the routes differ in "
                         f"{below[task, bar, every]} of {len(seeds) * len(flavors)} cells; "
                         f"oracle {pooled(lambda seed, t: best[seed, t], task)[0]:.4f}")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="below_bar_fallback.py", description=__doc__.splitlines()[0])
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
