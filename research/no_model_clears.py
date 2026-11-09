"""When no model clears the bar in `cost_effective`: the 5.3 fallback or the cheapest model (DESIGN 12.8 v1.144).

Usage:
  python research/no_model_clears.py --routerbench MATRIX.jsonl --autobench MATRIX.jsonl \
      --judges MATRIX.jsonl --judges-registry MODELS.json --tau2 MATRIX.jsonl

Runs `evaluate` (DESIGN 12.3) on the `cost_effective` flavor of the four routing datasets that
record a cost, with the bars, seeds and options of each committed results file, and prints, per
bar, the cells on which no model clears and, on them, the held-out success and cost of the
router's fallback (5.3 `best_available`: the highest calibration bound), of the cheapest model and
of `best_on_calibration`; then the bar's whole row as routed and with the cheapest model as the
fallback. The as-routed row must be the committed results file's. Standard library and the
model_routing package. Read by research/no-model-clears.md. Exit 0, or 2 with one `error: ...`
line on a missing or unreadable file, a row `load_outcomes` refuses, a missing key or a routed
row that is not the committed one.
"""

import argparse
import json
import math
import sys
from pathlib import Path

from model_routing import Registry, evaluate, load_outcomes

ROOT = Path(__file__).resolve().parents[1]
# name, committed results file, matrix option
DATASETS = (("RouterBench", "evidence/routerbench/results.json", "routerbench"),
            ("AutoBench", "evidence/autobench-2026/results.json", "autobench"),
            ("AutoBench judges", "evidence/autobench-judges/results.json", "judges"),
            ("tau2-bench", "evidence/tau2-bench/results.json", "tau2"))
# printed label, 12.3 strategy
ROWS = (("fallback", "routed"), ("cheapest", "cheapest"), ("best_on_calibration", "best_on_calibration"))
FLAVOR = "cost_effective"


def whole_row(cells, seeds, pick):
    """12.3's summary of one bar and flavor with `pick(cell)` naming each cell's strategy:
    the mean over seeds of each seed's pooled held-out success and of its summed cost."""
    success, cost = [], []
    for seed in seeds:
        cs = [c for c in cells if c["seed"] == seed]
        correct = sum(round(c["success"][pick(c)] * c["held_out_items"]) for c in cs)
        success.append(correct / sum(c["held_out_items"] for c in cs))
        cost.append(math.fsum(c["cost_usd"][pick(c)] for c in cs))
    return math.fsum(success) / len(seeds), math.fsum(cost) / len(seeds)


def _close(a, b) -> bool:
    return abs(a - b) <= 1e-12 * max(abs(a), abs(b))


def report(name, rel, outcomes, committed) -> list:
    """The printed lines for one dataset; `committed` is its results file (config and summary)."""
    config = committed["config"]
    bars, seeds = list(config["bars"]), list(config["seeds"])
    result = evaluate(outcomes, bars=bars, seeds=seeds, flavors=[FLAVOR],
                      calibration_fraction=config["calibration_fraction"],
                      min_samples=config["min_samples"], confidence=config["confidence"])
    tasks = sorted(result["tasks"])
    models = sorted({m for t in result["tasks"].values() for m in t["models"]})
    routed = {r["bar"]: r for r in committed["summary"]
              if r["flavor"] == FLAVOR and r["strategy"] == "routed"}
    lines = [f"{name} ({rel}): {len(tasks)} {'task' if len(tasks) == 1 else 'tasks'}, "
             f"{len(models)} models, bars {', '.join(str(b) for b in bars)}, {len(seeds)} seeds"]
    for bar in bars:
        cells = [c for c in result["cells"] if c["bar"] == bar]
        none = [c for c in cells if not c["cleared"]]
        s0, c0 = whole_row(cells, seeds, lambda c: "routed")
        if not (_close(s0, routed[bar]["success"]) and _close(c0, routed[bar]["cost_usd"])):
            raise ValueError(f"{rel}: the routed {FLAVOR} row at bar {bar} is not the committed one")
        head = (f"  bar {bar}: no model clears on {len(none):,} of {len(cells):,} {FLAVOR} cells "
                f"({len(none) / len(cells):.1%})")
        if not none:
            lines.append(head)
            continue
        held = sum(c["held_out_items"] for c in none)
        if len(tasks) <= 5:
            where = "by task: " + ", ".join(f"{t} {sum(c['task'] == t for c in none)}" for t in tasks)
        else:
            where = f"tasks with such a cell: {len({c['task'] for c in none})} of {len(tasks)}"
        lines.append(f"{head}, {held:,} held-out items; {where}")
        boc = sum(c["models"]["routed"] == c["models"]["best_on_calibration"] for c in none)
        cheap = sum(c["models"]["routed"] == c["models"]["cheapest"] for c in none)
        lines.append(f"    the routed model is best_on_calibration's on {boc:,} and the cheapest "
                     f"model's on {cheap:,}")
        for label, strategy in ROWS:
            correct = sum(round(c["success"][strategy] * c["held_out_items"]) for c in none)
            cost = math.fsum(c["cost_usd"][strategy] for c in none)
            met = sum(c["success"][strategy] >= bar for c in none)
            lines.append(f"    {label:<20} success {correct / held:.3f}  cost per item {cost / held:.6f} USD  "
                         f"at the bar or above on {met:,} ({met / len(none):.1%})")
        s1, c1 = whole_row(cells, seeds, lambda c: "routed" if c["cleared"] else "cheapest")
        change = f"{c1 / c0 - 1:+.1%}" if c0 else "-"
        lines.append(f"    whole row: routed success {s0:.3f} at {c0:.4f} USD; with the cheapest model as "
                     f"the fallback {s1:.3f} at {c1:.4f} USD (success {s1 - s0:+.3f}, cost {change})")
    return lines


def run(outcomes, root=ROOT) -> list:
    """Every dataset's lines in DATASETS order, a blank line between datasets."""
    lines = []
    for name, rel, _ in DATASETS:
        with open(Path(root) / rel, encoding="utf-8") as fh:
            committed = json.load(fh)
        if lines:
            lines.append("")
        lines.extend(report(name, rel, outcomes[name], committed))
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="no_model_clears.py", description=__doc__.splitlines()[0])
    parser.add_argument("--routerbench", required=True)
    parser.add_argument("--autobench", required=True)
    parser.add_argument("--judges", required=True)
    parser.add_argument("--judges-registry", required=True)
    parser.add_argument("--tau2", required=True)
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root holding evidence/ (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        registry = Registry.load(args.judges_registry)
        outcomes = {name: load_outcomes(getattr(args, option), registry if option == "judges" else None)
                    for name, _, option in DATASETS}
        lines = run(outcomes, args.root)
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
