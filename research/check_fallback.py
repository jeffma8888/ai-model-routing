"""What the executor's fallback on a failed check buys on LLMRouterBench (DESIGN 12.8 v1.181)

Usage:
  python research/check_fallback.py --matrix llmrouterbench-matrix.jsonl

Runs `evaluate` (DESIGN 12.3) on the LLMRouterBench matrix that the converter writes, at the lowest
and highest bars of evidence/llmrouterbench/results.json with its seeds, flavors and options,
rebuilds each cell's route as 12.3 builds its router, with `max_fallbacks` 0, 2 and every listed
model, and replays the executor's fallback (DESIGN 7) on each held-out item: the route's models in
turn until a record scores 1, every attempt's cost spent. It prints, per flavor and bar, each
route's pooled held-out success and cost, its attempts per item and the share of the routed to
oracle success gap it recovers, then per task at the highest bar. Each route's primary must be its
cell's routed model, and with no fallback each row must be the committed one. Standard library and
the model_routing package. Read by research/check-fallback.md. Exit 0, or 2 with one `error: ...`
line on a missing or unreadable file, a row `load_outcomes` refuses, a missing key, a route that
does not start with the routed model or a row that is not the committed one.
"""

import argparse
import json
import math
import sys
from pathlib import Path

from model_routing import Model, Registry, Router, Stats, Task, evaluate, load_outcomes, split_items

ROOT = Path(__file__).resolve().parents[1]
RESULTS = "evidence/llmrouterbench/results.json"


def calibration(rows, cal, models) -> tuple:
    """12.3's calibration counts and mean costs on the items `cal`; `rows` maps an item to its
    {model: Outcome}: ({model: items scored 1}, {model: mean cost})."""
    succ = {m: sum(rows[i][m].correct for i in cal) for m in models}
    mean_cost = {m: math.fsum(rows[i][m].cost_usd for i in cal) / len(cal) for m in models}
    return succ, mean_cost


def route(succ, mean_cost, n_cal, task, flavor, bar, min_samples, confidence, max_fallbacks) -> tuple:
    """(primary, *fallbacks) of the router 12.3 builds for one cell, with `max_fallbacks`."""
    stats = Stats()
    for m in succ:
        stats.add(task, m, succ[m], n_cal)
    registry = Registry([Model(m, m, mean_cost[m] * 1_000_000, 0.0, 2 ** 62) for m in succ])
    spec = Task(name=task, bar=bar, min_samples=min_samples, confidence=confidence,
                independent_of_generator=False, expected_input_tokens=1, expected_output_tokens=0,
                on_no_model="best_available", max_fallbacks=max_fallbacks)
    decision = Router(registry, {task: spec}, stats).select(task, flavor)
    return (decision.primary, *decision.fallbacks)


def attempts(row, path) -> tuple:
    """One item down `path` in the executor's order, stopping at the first record that scores 1:
    (some attempt scored 1, attempts made, their costs)."""
    costs = []
    for m in path:
        costs.append(row[m].cost_usd)
        if row[m].correct:
            return True, len(costs), costs
    return False, len(costs), costs


def replay(rows, held, path) -> tuple:
    """`path` on every item of `held`: (items scored 1, attempts, every attempt's cost in order)."""
    correct, tries, spent = 0, 0, []
    for i in held:
        ok, k, costs = attempts(rows[i], path)
        correct += ok
        tries += k
        spent.extend(costs)
    return correct, tries, spent


def oracle(rows, held, models) -> tuple:
    """12.3's oracle on `held`: (items some model scores 1 on, the cost of each item)."""
    correct, spent = 0, []
    for i in held:
        right = [rows[i][m].cost_usd for m in models if rows[i][m].correct]
        correct += bool(right)
        spent.append(min(right) if right else min(rows[i][m].cost_usd for m in models))
    return correct, spent


def share(mine, base, top):
    """The share of the base to top success gap that `mine` recovers; None when there is no gap."""
    return None if top == base else (mine - base) / (top - base)


def _mean(values):
    return math.fsum(values) / len(values)


def _row(rows, rel, bar, flavor, strategy, task=None):
    hit = [r for r in rows if (r["bar"], r["flavor"], r["strategy"], r.get("task")) == (bar, flavor, strategy, task)]
    if len(hit) != 1:
        raise ValueError(f"{rel}: not one {strategy} row at bar {bar}, {flavor}" + (f", {task}" if task else ""))
    return hit[0]


def _check(rel, row, success, cost, what):
    for mine, key in ((success, "success"), (cost, "cost_usd")):
        if abs(mine - row[key]) > 1e-12 * max(abs(mine), abs(row[key])):
            raise ValueError(f"{rel}: {what} is not the committed one ({key})")


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
            sums[task, seed] = calibration(table[task], halves[task, seed][0], models)
    limits = (0, 2, len(models) - 1)
    # (flavor, bar, limit, seed, task) -> (items scored 1, held-out items, attempts, cost)
    got, lengths = {}, {}
    for c in result["cells"]:
        task, seed, bar, flavor = c["task"], c["seed"], c["bar"], c["flavor"]
        cal, held = halves[task, seed]
        succ, mean_cost = sums[task, seed]
        for limit in limits:
            path = route(succ, mean_cost, len(cal), task, flavor, bar, min_samples, confidence, limit)
            if path[0] != c["models"]["routed"]:
                raise ValueError(f"the rebuilt route of {task}, seed {seed}, bar {bar}, {flavor} does not "
                                 f"start with its routed model")
            correct, tries, spent = replay(table[task], held, path)
            got[flavor, bar, limit, seed, task] = (correct, len(held), tries, math.fsum(spent))
            lengths.setdefault((flavor, bar, limit), set()).add(len(path))
            lengths.setdefault((task, bar, limit), set()).add(len(path))
    best = {}
    for (task, seed), (cal, held) in halves.items():
        correct, spent = oracle(table[task], held, models)
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
        return _mean(success), _mean(cost), _mean(per)

    top, top_cost, _ = pooled(lambda seed, t: best[seed, t])
    for bar in bars:
        for flavor in flavors:
            _check(rel, _row(committed["summary"], rel, bar, flavor, "oracle"), top, top_cost,
                   f"the oracle {flavor} row at bar {bar}")
    lines = [f"LLMRouterBench ({rel}): {len(tasks)} tasks, {len(models)} models, "
             f"{sum(t['items'] for t in tasks.values()):,} items, {len(seeds)} seeds, bars {bars[0]} and {bars[1]}, "
             f"the lowest and highest of {len(config['bars'])}",
             "a route is the router's primary then its next max_fallbacks models (5.3); each held-out item is "
             "tried down its route until a record scores 1, and every attempt's cost is spent",
             f"oracle: success {top:.4f}, cost {top_cost:.4f}"]
    for flavor in flavors:
        for bar in bars:
            lines.append(f"{flavor} bar {bar}:")
            for limit in limits:
                success, cost, per = pooled(lambda seed, t: got[flavor, bar, limit, seed, t])
                if limit == 0:
                    base, base_cost = success, cost
                    _check(rel, _row(committed["summary"], rel, bar, flavor, "routed"), success, cost,
                           f"the routed {flavor} row at bar {bar}")
                    for task in tasks:
                        ts, tc, _ = pooled(lambda seed, t: got[flavor, bar, 0, seed, t], task)
                        _check(rel, _row(committed["per_task"], rel, bar, flavor, "routed", task), ts, tc,
                               f"the routed {flavor} {task} row at bar {bar}")
                part = share(success, base, top)
                n = sorted(lengths[flavor, bar, limit])
                lines.append(f"  max_fallbacks {limit}: success {success:.4f}, cost {cost:.4f}, "
                             f"{cost / base_cost:.3f} times no fallback's, attempts per item {per:.3f}, "
                             f"routes of {n[0]} to {n[-1]} models, gap to the oracle recovered "
                             f"{'-' if part is None else f'{part:.3f}'}")
    every = limits[-1]
    lines.append(f"per task at bar {bars[1]}, held-out success with max_fallbacks 0 and {every}, and the oracle's:")
    for task in tasks:
        parts = [f"{flavor} from {pooled(lambda seed, t: got[flavor, bars[1], 0, seed, t], task)[0]:.4f} "
                 f"to {pooled(lambda seed, t: got[flavor, bars[1], every, seed, t], task)[0]:.4f}"
                 for flavor in flavors]
        n = sorted(lengths[task, bars[1], every])
        lines.append(f"  {task} ({tasks[task]['items']:,} items): {', '.join(parts)}, routes of {n[0]} to {n[-1]} "
                     f"models; "
                     f"oracle {pooled(lambda seed, t: best[seed, t], task)[0]:.4f}")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="check_fallback.py", description=__doc__.splitlines()[0])
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
