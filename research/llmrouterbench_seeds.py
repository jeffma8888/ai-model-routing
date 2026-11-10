"""Does the LLMRouterBench success gain hold seed by seed? (DESIGN 12.8 v1.177)

Usage:
  python research/llmrouterbench_seeds.py --matrix llmrouterbench-matrix.jsonl

Runs `evaluate` (DESIGN 12.3) on the LLMRouterBench matrix that the converter writes, with the
bars, seeds, flavors and options of evidence/llmrouterbench/results.json, and prints, for
`best_on_calibration` and for the routed row of each flavor at each bar, on how many seeds its
pooled held-out success is above, equal to and below the best single model's on the same halves,
the lowest, median, highest and mean gap, and its cost over that model's. The mean over seeds of
each row's success and cost must be the committed one. Standard library and the model_routing package. Read by
research/llmrouterbench-seeds.md. Exit 0, or 2 with one `error: ...` line on a missing or
unreadable file, a row `load_outcomes` refuses, a missing key or a row that is not the committed one.
"""

import argparse
import json
import math
import statistics
import sys
from pathlib import Path

from model_routing import evaluate, load_outcomes

ROOT = Path(__file__).resolve().parents[1]
RESULTS = "evidence/llmrouterbench/results.json"


def best_single_model(summary) -> str:
    """12.7: the `model:` summary row with the highest held-out success, then lower cost, then ID;
    an error when it differs between bars or flavors."""
    picks = set()
    for key in sorted({(r["bar"], r["flavor"]) for r in summary}):
        rows = [r for r in summary if (r["bar"], r["flavor"]) == key and r["strategy"].startswith("model:")]
        if not rows:
            raise ValueError(f"{RESULTS}: no model: rows at bar {key[0]}, {key[1]}")
        best = min(rows, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
        picks.add(best["strategy"][len("model:"):])
    if len(picks) != 1:
        raise ValueError(f"{RESULTS}: the best single model differs between bars or flavors")
    return picks.pop()


def per_seed(cells, seeds, strategy) -> list:
    """One (correct held-out items, held-out items, cost) per seed, in seed order, for `strategy`
    pooled over the seed's tasks, as 12.3's summary pools them."""
    out = []
    for seed in seeds:
        cs = [c for c in cells if c["seed"] == seed]
        out.append((sum(round(c["success"][strategy] * c["held_out_items"]) for c in cs),
                    sum(c["held_out_items"] for c in cs),
                    math.fsum(c["cost_usd"][strategy] for c in cs)))
    return out


def gap_line(label, mine, base) -> str:
    """`mine` against `base`, two per_seed lists on the same halves: the seeds above, equal and
    below by correct items; the gap in success, lowest, median, highest and mean; and the cost
    over the base's, lowest to highest (`-` when a base cost is 0)."""
    diffs = [m[0] - b[0] for m, b in zip(mine, base)]
    gaps = [(m[0] - b[0]) / m[1] for m, b in zip(mine, base)]
    if any(b[2] == 0 for b in base):
        ratio = "-"
    else:
        ratios = [m[2] / b[2] for m, b in zip(mine, base)]
        ratio = f"{min(ratios):.3f} to {max(ratios):.3f}"
    return (f"{label}: above on {sum(d > 0 for d in diffs)}, equal on {sum(d == 0 for d in diffs)}, "
            f"below on {sum(d < 0 for d in diffs)} of {len(diffs)} seeds; gap lowest {min(gaps):+.4f}, "
            f"median {statistics.median(gaps):+.4f}, highest {max(gaps):+.4f}, "
            f"mean {math.fsum(gaps) / len(gaps):+.4f}; cost over the best single model's {ratio}")


def _check(rel, committed, bar, flavor, strategy, counts):
    rows = [r for r in committed["summary"]
            if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    if len(rows) != 1:
        raise ValueError(f"{rel}: not one {strategy} row at bar {bar}, {flavor}")
    success = math.fsum(c / n for c, n, _ in counts) / len(counts)
    cost = math.fsum(x for _, _, x in counts) / len(counts)
    for mine, key in ((success, "success"), (cost, "cost_usd")):
        if abs(mine - rows[0][key]) > 1e-12 * max(abs(mine), abs(rows[0][key])):
            raise ValueError(f"{rel}: the {strategy} {flavor} row at bar {bar} is not the committed one ({key})")


def report(outcomes, committed, rel=RESULTS) -> list:
    """The printed lines; `committed` is the results file (its config and summary)."""
    config = committed["config"]
    bars, seeds, flavors = list(config["bars"]), list(config["seeds"]), list(config["flavors"])
    best = best_single_model(committed["summary"])
    result = evaluate(outcomes, bars=bars, seeds=seeds, flavors=flavors,
                      calibration_fraction=config["calibration_fraction"],
                      min_samples=config["min_samples"], confidence=config["confidence"])
    tasks, cells = result["tasks"], result["cells"]
    models = sorted({m for t in tasks.values() for m in t["models"]})
    at = {(bar, flavor): [c for c in cells if (c["bar"], c["flavor"]) == (bar, flavor)]
          for bar in bars for flavor in flavors}
    for (bar, flavor), mine in at.items():
        for strategy in (f"model:{best}", "best_on_calibration", "routed"):
            _check(rel, committed, bar, flavor, strategy, per_seed(mine, seeds, strategy))
    first = at[(bars[0], flavors[0])]
    base = per_seed(first, seeds, f"model:{best}")
    held = [n for _, n, _ in base]
    lines = [f"LLMRouterBench ({rel}): {len(tasks)} tasks, {len(models)} models, "
             f"{sum(t['items'] for t in tasks.values()):,} items, bars {', '.join(str(b) for b in bars)}, "
             f"{len(seeds)} seeds, held-out items per seed {min(held):,} to {max(held):,}",
             f"best single model (12.7): {best}; a gap is a row's pooled held-out success on a seed minus "
             f"{best}'s on the same halves",
             gap_line("best_on_calibration (every bar and flavor)", per_seed(first, seeds, "best_on_calibration"),
                      base)]
    for flavor in flavors:
        lines.append(f"{flavor} routed:")
        signs = [set() for _ in seeds]
        picks = {}
        for bar in bars:
            mine = per_seed(at[(bar, flavor)], seeds, "routed")
            for k, (m, b) in enumerate(zip(mine, base)):
                signs[k].add((m[0] > b[0]) - (m[0] < b[0]))
            for c in at[(bar, flavor)]:
                picks.setdefault((c["task"], c["seed"]), set()).add(c["models"]["routed"])
            lines.append(gap_line(f"  bar {bar}", mine, base))
        lines.append(f"  seeds whose gap has one sign at every bar: {sum(len(s) == 1 for s in signs)} of "
                     f"{len(seeds)}; (task, seed) cells routed to one model at every bar: "
                     f"{sum(len(p) == 1 for p in picks.values()):,} of {len(picks):,}")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="llmrouterbench_seeds.py", description=__doc__.splitlines()[0])
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
