"""Each RouterBench eval's own best model: the ceiling of per-task routing (DESIGN 12.8 v1.146).

Usage: python research/routerbench_per_task.py [--cache DIR] [--root DIR]

Reads the pinned RouterBench file from the converter's cache folder through the checked reader of
evidence/routerbench/convert.py (size and sha256, then the restricted unpickler; reading the frame
needs pandas, the `evidence` extra) and never downloads it. Runs `evaluate` (DESIGN 12.3) with the
config of the committed evidence/routerbench/results.json at its first bar on `cost_blind`, and
prints, per eval, its best model on all its items against the best single model, the margin and
the Wilson shortfall at its calibration half; the evals where another model leads; and the held-out
success and cost of the best single model, the router, `best_on_calibration`, the per-eval best and
the oracle over all evals, the `mmlu` evals and the rest. The rows the committed file holds must be
its own, else the script stops. Read by research/routerbench-per-task.md. Exit 0, or 2 with one
`error: ...` line.
"""

import argparse
import importlib.util
import json
import math
import pickle
import sys
from collections import Counter
from pathlib import Path
from statistics import median_low

from model_routing import evaluate, outcomes_from_rows
from model_routing.stats import items_needed, wilson_lower_bound

ROOT = Path(__file__).resolve().parents[1]
CONVERTER = ROOT / "evidence" / "routerbench" / "convert.py"
RESULTS = "evidence/routerbench/results.json"
FLAVOR = "cost_blind"
# what another dataset needs: a success level, margins over the best single model and a gain
NEEDS_SUCCESS, MARGINS, GAIN = 0.8, (0.02, 0.05, 0.1), 0.01
WIDTHS = ((40, "<"), (5, ">"), (4, ">"), (33, "<"), (4, ">"), (7, "<"), (6, "<"), (6, "<"), (9, "<"),
          (5, ">"), (6, ">"))
GROUP_WIDTHS = ((6, "<"), (5, ">"), (35, "<"), (7, "<"), (10, "<"), (9, ">"))
LEGEND = ("per eval: its items and calibration half (median over seeds), its best model on all its items, "
          "the models tied on that count, that model's success and the best single model's on all items, "
          "the margin, the Wilson shortfall of that success at the half, the seeds on which it is also the "
          "best on the held-out half, and the models that are that best on some seed")


def converter():
    """evidence/routerbench/convert.py, loaded from its path (it is not part of the package)."""
    spec = importlib.util.spec_from_file_location("routerbench_convert", CONVERTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load_rows(cache) -> list:
    """The 12.6 default matrix from the pinned file in `cache`, checked before it is unpickled."""
    conv = converter()
    path = Path(cache) / conv.FILENAME
    conv.verify(path)
    return conv.convert(conv.frame_columns(conv.load_frame(path)))[0]


def _fmt(values, widths) -> str:
    return "  " + "  ".join(f"{v:{a}{w}}" for v, (w, a) in zip(values, widths))


def _close(a, b) -> bool:
    return abs(a - b) <= 1e-12 * max(abs(a), abs(b))


def _held_best(cell, models):
    """The model with the highest held-out success on the cell, then the lower held-out cost, then ID."""
    return min(models, key=lambda m: (-cell["success"]["model:" + m], cell["cost_usd"]["model:" + m], m))


def _row(cells, seeds, tasks, pick, single):
    """12.3's summary over `tasks` with `pick(cell)` naming each cell's strategy, and the mean
    correct held-out items per seed minus the best single model's."""
    success, cost, gap = [], [], []
    for seed in seeds:
        cs = [cells[t, seed] for t in tasks]
        right = sum(round(c["success"][pick(c)] * c["held_out_items"]) for c in cs)
        success.append(right / sum(c["held_out_items"] for c in cs))
        cost.append(math.fsum(c["cost_usd"][pick(c)] for c in cs))
        gap.append(right - sum(round(c["success"][single] * c["held_out_items"]) for c in cs))
    return math.fsum(success) / len(seeds), math.fsum(cost) / len(seeds), sum(gap) / len(seeds)


def report(rows, committed, source) -> list:
    """The printed lines; `committed` is the RouterBench results file (config and summary)."""
    config = committed["config"]
    bar, seeds = config["bars"][0], list(config["seeds"])
    result = evaluate(outcomes_from_rows(rows), bars=[bar], seeds=seeds, flavors=[FLAVOR],
                      calibration_fraction=config["calibration_fraction"],
                      min_samples=config["min_samples"], confidence=config["confidence"])
    summary = {r["strategy"]: r for r in result["summary"]}
    kept = {r["strategy"]: r for r in committed["summary"] if (r["bar"], r["flavor"]) == (bar, FLAVOR)}
    for strategy, r in summary.items():
        if strategy not in kept or not (_close(r["success"], kept[strategy]["success"])
                                        and _close(r["cost_usd"], kept[strategy]["cost_usd"])):
            raise ValueError(f"{RESULTS}: the {strategy} row at bar {bar} on {FLAVOR} is not the committed one")
    tasks = sorted(result["tasks"])
    models = sorted({m for t in result["tasks"].values() for m in t["models"]})
    cells = {(c["task"], c["seed"]): c for c in result["cells"]}
    confidence = config["confidence"]
    single = min((r for s, r in summary.items() if s.startswith("model:")),
                 key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    best_single = single["strategy"][len("model:"):]
    ok, cost = Counter(), {}
    for r in rows:
        ok[r["task"], r["model"]] += bool(r["correct"])
        cost.setdefault((r["task"], r["model"]), []).append(r["cost_usd"])
    items = {t: result["tasks"][t]["items"] for t in tasks}
    lines = [f"RouterBench ({source}): {len(tasks)} evals, {len(models)} models, {sum(items.values()):,} items, "
             f"{len(seeds)} seeds, calibration_fraction {config['calibration_fraction']}, confidence {confidence}",
             f"best single model (12.7): {best_single}, held-out success {single['success']:.4f} at "
             f"{single['cost_usd']:.4f} USD",
             LEGEND,
             _fmt(("eval", "items", "half", "best on all items", "tied", "success", "single", "margin",
                   "shortfall", "seeds", "models"), WIDTHS)]
    best, lead = {}, {}
    for t in tasks:
        top = min(models, key=lambda m: (-ok[t, m], math.fsum(cost[t, m]), m))
        best[t], n = top, items[t]
        half = median_low([cells[t, s]["calibration_items"] for s in seeds])
        sb, sg = ok[t, top] / n, ok[t, best_single] / n
        sf = sb - wilson_lower_bound(round(sb * half), half, confidence)
        held = Counter(_held_best(cells[t, s], models) for s in seeds)
        lead[t] = (sb - sg, sf, ok[t, top] > ok[t, best_single])
        lines.append(_fmt((t, n, half, top, sum(ok[t, m] == ok[t, top] for m in models), f"{sb:.3f}",
                           f"{sg:.3f}", f"{sb - sg:+.3f}", f"{sf:.3f}", held[top], len(held)), WIDTHS))
    others = [t for t in tasks if best[t] != best_single]
    higher = [t for t in others if lead[t][2]]
    lines.append(f"evals whose best model on all items is not {best_single}: {len(others)} "
                 f"({', '.join(others) if others else 'none'}); with a higher success than it: {len(higher)}; "
                 f"higher by more than the shortfall: {sum(lead[t][0] > lead[t][1] for t in higher)}")
    if higher:
        t = max(higher, key=lambda x: (lead[x][0], x))
        lines.append(f"largest margin: {lead[t][0]:+.3f} on {t} ({best[t]}), shortfall {lead[t][1]:.3f}")
    else:
        lines.append("largest margin: none above 0")
    moved = {k: [key for key, c in cells.items() if c["models"][k] != best_single]
             for k in ("routed", "best_on_calibration")}
    moved_evals = sorted({t for t, _ in moved["routed"]})
    varied = [t for t in moved_evals if len({cells[t, s]["models"]["routed"] for s in seeds}) > 1]
    halves = [median_low([cells[t, s]["calibration_items"] for s in seeds]) for t in moved_evals]
    span = f"calibration halves {min(halves)} to {max(halves)}" if halves else "no calibration half"
    lines.append(f"routed ({FLAVOR}, bar {bar}) takes another model on {len(moved['routed']):,} of {len(cells):,} "
                 f"eval and seed cells, on {len(moved_evals)} evals ({len(varied)} of them with two or more picks "
                 f"across seeds, {span}); best_on_calibration on "
                 f"{len(moved['best_on_calibration']):,}, on {len({t for t, _ in moved['best_on_calibration']})} evals")
    lines.append(f"held-out success and cost over {len(seeds)} seeds, as 12.3's summary computes them; vs single: "
                 "the mean correct held-out items per seed minus the best single model's")
    lines.append(_fmt(("group", "evals", "strategy", "success", "cost (USD)", "vs single"), GROUP_WIDTHS))
    strategies = (("best single model", lambda c: single["strategy"]),
                  (f"routed ({FLAVOR}, bar {bar})", lambda c: "routed"),
                  ("best_on_calibration", lambda c: "best_on_calibration"),
                  ("per-eval best on all items", lambda c: "model:" + best[c["task"]]),
                  ("per-eval best on each held-out half", lambda c: "model:" + _held_best(c, models)),
                  ("oracle (per prompt)", lambda c: "oracle"))
    groups = (("all", tasks), ("mmlu", [t for t in tasks if t.startswith("mmlu")]),
              ("other", [t for t in tasks if not t.startswith("mmlu")]))
    for group, members in groups:
        if not members:
            continue
        for label, pick in strategies:
            s, c, gap = _row(cells, seeds, members, pick, single["strategy"])
            lines.append(_fmt((group, len(members), label, f"{s:.4f}", f"{c:.4f}", f"{gap:+.1f}"), GROUP_WIDTHS))
    lines.append(f"what another dataset needs, at a success of {NEEDS_SUCCESS}: the calibration half from which "
                 "the Wilson shortfall is within the margin (items_needed, 4.3), and the share of items that evals "
                 f"with that margin over the best single model must hold for a gain of {GAIN} in success")
    for margin in MARGINS:
        n = items_needed(NEEDS_SUCCESS, round(NEEDS_SUCCESS - margin, 2), confidence)
        lines.append(f"  margin {margin}: half {'none up to 10,000' if n is None else f'{n:,}'}; "
                     f"share of items {GAIN / margin:.2f}")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="routerbench_per_task.py", description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, default=None,
                        help="folder holding the pinned file (default: the converter's cache folder)")
    parser.add_argument("--root", type=Path, default=ROOT,
                        help="repository root holding evidence/ (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        conv = converter()
        rows = load_rows(args.cache if args.cache is not None else conv.default_cache_dir())
        with open(args.root / RESULTS, encoding="utf-8") as fh:
            committed = json.load(fh)
        lines = report(rows, committed, f"{conv.FILENAME} at revision {conv.REVISION}")
    except (OSError, ValueError, KeyError, TypeError, AttributeError, pickle.UnpicklingError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
