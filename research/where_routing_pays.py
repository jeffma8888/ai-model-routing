"""Where task-level routing pays on the committed evidence (DESIGN 12.8 v1.124, v1.166).

Reads only the six committed routing results files under evidence/ and prints, per dataset: the
tasks routed, the items per task and the expected calibration half, the best single model and the
per-task `best_on_calibration` baseline, how far a Wilson lower bound sits below the best single
model's success at that half, and, per flavor and bar, the routed row against the best single
model with the models routing picks across tasks and seeds, the tasks it routes off that model and
its gain over it, and, where a note measured it, the share of the in-sample per-task gain the
held-out halves keep. Standard library and
`model_routing.stats.wilson_lower_bound`, the bound the router uses. Exit 0, or 2 with one
`error: ...` line when a file is missing, is not JSON or lacks a key the report reads.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path
from statistics import median

from model_routing.stats import wilson_lower_bound

ROOT = Path(__file__).resolve().parents[1]
DATASETS = (
    ("RouterBench", "evidence/routerbench/results.json"),
    ("AutoBench", "evidence/autobench-2026/results.json"),
    ("AutoBench judges", "evidence/autobench-judges/results.json"),
    ("tau2-bench", "evidence/tau2-bench/results.json"),
    ("LiveCodeBench", "evidence/livecodebench/results.json"),
    ("LLMRouterBench", "evidence/llmrouterbench/results.json"),
)
# The in-sample per-task gain over the best single model on all items, from the note that measured
# it (this script does not read the note; tests/test_research_where_routing_pays.py ties the two)
IN_SAMPLE = {"LLMRouterBench": ("research/datasets.md", "google/gemini-2.5-pro", 0.0250)}
# What the committed files do not hold, so the note cannot report it
LACKS = ("each task's single-model rows (per_task holds the routed rows only) and each seed's "
         "calibration size (the seeded hash split of 12.2 varies it)")
HEADER = ("  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  "
          "tasks with 2+  top pick share  off best  never best  gain")


def summary_row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"]
            if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    if len(rows) != 1:
        raise ValueError(f"{len(rows)} summary rows for {(bar, flavor, strategy)}")
    return rows[0]


def best_single(results, bar, flavor):
    """The single model with the highest held-out success, then the lower cost, then the ID (12.7)."""
    rows = [r for r in results["summary"]
            if (r["bar"], r["flavor"]) == (bar, flavor) and r["strategy"].startswith("model:")]
    return min(rows, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))


def shortfall(success, n, confidence):
    """How far the Wilson lower bound sits below a success rate observed on n items."""
    return success - wilson_lower_bound(round(success * n), n, confidence)


def picks(results, bar, flavor, best_model):
    """Routed picks summed over tasks and seeds, the number of tasks whose pick changes by seed, and
    the numbers of tasks that pick another model than `best_model` on some seed and on every seed."""
    rows = [p for p in results["per_task"] if (p["bar"], p["flavor"]) == (bar, flavor)]
    if len(rows) != len(results["tasks"]):
        raise ValueError(f"{len(rows)} per_task rows at {(bar, flavor)} for {len(results['tasks'])} tasks")
    total = Counter()
    for p in rows:
        total.update(p["routed_models"])
    off = sum(1 for p in rows if set(p["routed_models"]) - {best_model})
    never = sum(1 for p in rows if best_model not in p["routed_models"])
    return total, sum(1 for p in rows if len(p["routed_models"]) > 1), off, never


def kept(gains, in_sample):
    """The share of the in-sample gain each held-out gain keeps: one value, or the lowest to the highest."""
    low, high = f"{min(gains) / in_sample:.2f}", f"{max(gains) / in_sample:.2f}"
    return low if low == high else f"{low} to {high}"


def report(name, rel, results):
    config = results["config"]
    tasks = results["tasks"]
    fraction = config["calibration_fraction"]
    confidence = config["confidence"]
    items = {task: tasks[task]["items"] for task in sorted(tasks)}
    halves = {task: int(n * fraction) for task, n in items.items()}
    models = sorted({m for t in tasks.values() for m in t["models"]})
    plural = "task" if len(tasks) == 1 else "tasks"
    below = sum(1 for h in halves.values() if h < config["min_samples"])
    lines = [f"{name} ({rel}): {len(tasks)} {plural}, {len(models)} models, "
             f"{len(config['seeds'])} seeds, calibration_fraction {fraction}, "
             f"min_samples {config['min_samples']}, confidence {confidence}"]
    if len(tasks) <= 5:
        lines.append("  items per task: " + ", ".join(f"{t} {n}" for t, n in items.items())
                     + "; expected calibration half: " + ", ".join(str(h) for h in halves.values())
                     + f"; tasks whose half is below min_samples: {below}")
    else:
        counts = sorted(items.values())
        lines.append(f"  items per task: {counts[0]} to {counts[-1]}, median {median(counts):g}; "
                     f"expected calibration half: {int(counts[0] * fraction)} to "
                     f"{int(counts[-1] * fraction)}, median {int(median(counts) * fraction)}; "
                     f"tasks whose half is below min_samples: {below}")
    first = (config["bars"][0], config["flavors"][0])
    best = best_single(results, *first)
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            other = best_single(results, bar, flavor)
            if (other["strategy"], other["success"], other["cost_usd"]) != (
                    best["strategy"], best["success"], best["cost_usd"]):
                raise ValueError(f"the best single model differs at {(bar, flavor)}")
    boc = summary_row(results, *first, "best_on_calibration")
    smallest = min(halves.values())
    mid = int(median(sorted(items.values())) * fraction)
    gaps = f"{shortfall(best['success'], smallest, confidence):.3f} at a half of {smallest}"
    if mid != smallest:
        gaps += f", {shortfall(best['success'], mid, confidence):.3f} at {mid}"
    lines.append(f"  best single model: {best['strategy'][len('model:'):]}, held-out success "
                 f"{best['success']:.3f} at {best['cost_usd']:.4f} USD; Wilson shortfall of that "
                 f"success: {gaps}")
    lines.append(f"  best_on_calibration (each task's best model on its half, no bar): held-out "
                 f"success {boc['success']:.3f} at {boc['cost_usd']:.4f} USD")
    best_model = best["strategy"][len("model:"):]
    if name in IN_SAMPLE:
        source, model, gain = IN_SAMPLE[name]
        if model != best_model:
            raise ValueError(f"the best single model is {best_model}, not the in-sample note's {model}")
        shares = [f"best_on_calibration {kept([boc['success'] - best['success']], gain)}"]
        for flavor in config["flavors"]:
            gains = [summary_row(results, bar, flavor, "routed")["success"] - best["success"]
                     for bar in config["bars"]]
            shares.append(f"routed {flavor} {kept(gains, gain)}")
        lines.append(f"  in-sample per-task gain over {model} on all items ({source}): {gain:.4f}; share "
                     f"of it kept on the held-out halves: " + ", ".join(shares))
    lines.append(f"  not in the file: {LACKS}")
    lines.append(HEADER)
    for flavor in config["flavors"]:
        for bar in config["bars"]:
            r = summary_row(results, bar, flavor, "routed")
            total, varying, off, never = picks(results, bar, flavor, best_model)
            ratio = f"{r['cost_usd'] / best['cost_usd']:.3f}" if best["cost_usd"] else "-"
            lines.append(f"  {bar:<4} {flavor:<15} {r['success']:.3f}   {r['cost_usd']:<11.4f} "
                         f"{ratio:<12} {r['cleared_rate']:.3f}    {len(total):<14} {varying:<14} "
                         f"{max(total.values()) / sum(total.values()):<15.3f} {off:<9} {never:<11} "
                         f"{r['success'] - best['success']:+.4f}")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root holding evidence/ (default: this checkout)")
    args = parser.parse_args(argv)
    out = []
    try:
        for name, rel in DATASETS:
            with open(args.root / rel, encoding="utf-8") as fh:
                out.extend(report(name, rel, json.load(fh)))
            out.append("")
    except (OSError, ValueError, KeyError, TypeError, AttributeError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(out).rstrip("\n"))
    return 0


if __name__ == "__main__":
    sys.exit(main())
