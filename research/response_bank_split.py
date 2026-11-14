"""The LLM Routing Response Bank on the release's own split (DESIGN 12.21 v1.375, row R27).

Calibrates on the release's 256 calibration tasks (`scores_cal.jsonl`) and scores on its 13,059
evaluation tasks, one fixed split, in place of the 12.2 seeded halves of the committed run, and
prints it beside the committed 50-seed means of evidence/response-bank/results.json. Each cell is
the evaluator's own (`_split_sums`, `_cell` and `_summary` of model_routing/evaluate.py, private
names this script may use as research/check_fallback.py uses `_routed_registry`, 12.3 v1.263), at
the committed file's bars, `min_samples` and confidence, so only the split differs. Reads the
converter's default matrix (`--matrix`) and the pinned `scores_cal.jsonl` from the converter's cache
folder (`--cache`), checked against its pinned size and sha256. Exit 0, or 2 with one `error: ...`
line, a carriage return or newline escaped.

  python evidence/response-bank/convert.py --out response-bank-matrix.jsonl
  python research/response_bank_split.py --matrix response-bank-matrix.jsonl [--cache DIR] [--root PATH]
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from model_routing import load_outcomes
from model_routing.evaluate import _cell, _split_sums, _strategies, _summary
from model_routing.stats import wilson_lower_bound

ROOT = Path(__file__).resolve().parents[1]
CONVERTER = "evidence/response-bank/convert.py"
RESULTS = "evidence/response-bank/results.json"
CALIBRATION_FILE = "scores_cal.jsonl"
SEED = "release"


def _converter(root):
    spec = importlib.util.spec_from_file_location("response_bank_convert_split", root / CONVERTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def calibration_ids(converter, cache):
    """The `task_id`s of the release's calibration scores file, after its pinned size and sha256."""
    path = Path(cache) / CALIBRATION_FILE
    if not path.is_file():
        raise ValueError(f"{path} is missing: run {CONVERTER} first, which downloads it")
    size, sha256 = converter.FILES[CALIBRATION_FILE]
    converter.verify(path, size, sha256)
    return {r["task_id"] for r in converter.read_jsonl(path, converter.score_record)}


def release_split(outcomes, calibration, config):
    """Each task's (calibration, evaluation) items by the release's split, and the evaluator's cells
    and summary on that one split at the committed config."""
    table, task_items = {}, {}
    for o in outcomes:
        by_model = table.setdefault((o.task, o.item), {})
        if o.model in by_model:
            raise ValueError(f"repeated outcome for task {o.task!r}, item {o.item!r}, model {o.model!r}")
        by_model[o.model] = o
        task_items.setdefault(o.task, set()).add(o.item)
    models = sorted({o.model for o in outcomes})
    for (task, item), by_model in sorted(table.items()):
        lacking = [m for m in models if m not in by_model]
        if lacking:
            raise ValueError(f"incomplete matrix: no row for task {task!r}, item {item!r}, model {lacking[0]!r}")
    unknown = calibration - {item for items in task_items.values() for item in items}
    if unknown:
        raise ValueError(f"{len(unknown)} calibration task_ids are not in the matrix, such as {min(unknown)!r}")
    tasks = sorted(task_items)
    splits, sums = {}, {}
    for task in tasks:
        cal = tuple(sorted(task_items[task] & calibration))
        held = tuple(sorted(task_items[task] - calibration))
        if not cal or not held:
            raise ValueError(f"task {task!r}: the release's calibration or evaluation split is empty")
        splits[task] = (cal, held)
        sums[task, SEED] = _split_sums(table, models, task, cal, held)
    strategies = _strategies(models)
    bars, flavors = config["bars"], config["flavors"]
    cells = [_cell(sums[task, SEED], models, strategies, task, bar, flavor, SEED,
                   config["min_samples"], config["confidence"])
             for bar in bars for flavor in flavors for task in tasks]
    summary = _summary(cells, sums, bars, flavors, [SEED], tasks, strategies)
    return models, tasks, splits, sums, cells, summary


def _row(summary, bar, flavor, strategy):
    rows = [r for r in summary if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    if len(rows) != 1:
        raise ValueError(f"{len(rows)} summary rows for {(bar, flavor, strategy)}")
    return rows[0]


def best_single(summary, bar, flavor):
    """The single model with the highest held-out success, then the lower cost, then the ID (12.7)."""
    rows = [r for r in summary if (r["bar"], r["flavor"]) == (bar, flavor) and r["strategy"].startswith("model:")]
    return min(rows, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))


def report(outcomes, calibration, committed):
    config = committed["config"]
    models, tasks, splits, sums, cells, summary = release_split(outcomes, calibration, config)
    items = {t: len(cal) + len(held) for t, (cal, held) in splits.items()}
    want = {t: committed["tasks"][t]["items"] for t in committed["tasks"]}
    if items != want:
        raise ValueError(f"the matrix tasks and items {items} are not the committed file's {want}")
    floor, confidence = config["min_samples"], config["confidence"]
    lines = [f"LLM Routing Response Bank on the release's own split ({CALIBRATION_FILE} calibrates, "
             f"the evaluation tasks score): {len(tasks)} task{'' if len(tasks) == 1 else 's'}, "
             f"{len(models)} model{'' if len(models) == 1 else 's'}, bars "
             + " ".join(str(b) for b in config["bars"])
             + f", min_samples {floor}, confidence {confidence} ({RESULTS} config)",
             "  task           calibration  evaluation  committed half  below min_samples  "
             "highest calibration bound (every model at it)"]
    fraction = config["calibration_fraction"]
    for task in tasks:
        cal, held = splits[task]
        half = int(committed["tasks"][task]["items"] * fraction)
        succ = sums[task, SEED]["succ"]
        most = max(succ.values())
        top = ", ".join(m for m in models if succ[m] == most)
        bound = wilson_lower_bound(most, len(cal), confidence)
        lines.append(f"  {task:<14} {len(cal):<12,} {len(held):<11,} {half:<15,} "
                     f"{'yes' if len(cal) < floor else 'no':<18} {bound:.3f} ({top}, {most:,} of {len(cal):,})")
    n_cal = sum(len(c) for c, _ in splits.values())
    n_held = sum(len(h) for _, h in splits.values())
    lines.append(f"  all            {n_cal:<12,} {n_held:,}")
    first = (config["bars"][0], config["flavors"][0])
    best, best_committed = best_single(summary, *first), best_single(committed["summary"], *first)
    lines.append("  single models on the evaluation split, held-out success and cost (USD):")
    for m in models:
        r = _row(summary, *first, f"model:{m}")
        lines.append(f"    {m:<28} {r['success']:.3f}  {r['cost_usd']:.4f}")
    lines.append(f"  best single model: {best['strategy'][len('model:'):]} {best['success']:.3f} here; "
                 f"{best_committed['strategy'][len('model:'):]} {best_committed['success']:.3f} in the "
                 f"committed means over {len(config['seeds'])} seeds")
    for s in ("oracle", "best_on_calibration", "cheapest"):
        r, c = _row(summary, *first, s), _row(committed["summary"], *first, s)
        lines.append(f"  {s}: {r['success']:.3f} at {r['cost_usd'] / best['cost_usd']:.3f} of the best's cost here; "
                     f"{c['success']:.3f} at {c['cost_usd'] / best_committed['cost_usd']:.3f} committed")
    lines.append("  bar  flavor          routed  cost (USD)  cost / best  cleared  committed routed  "
                 "committed cost / best  committed cleared")
    for flavor in config["flavors"]:
        for bar in config["bars"]:
            r, c = _row(summary, bar, flavor, "routed"), _row(committed["summary"], bar, flavor, "routed")
            cleared = [x["task"] for x in cells if (x["bar"], x["flavor"]) == (bar, flavor) and x["cleared"]]
            lines.append(f"  {bar:<4} {flavor:<15} {r['success']:.3f}   {r['cost_usd']:<11.4f} "
                         f"{r['cost_usd'] / best['cost_usd']:<12.3f} {len(cleared)} of {len(tasks)}   "
                         f"{c['success']:.3f}             {c['cost_usd'] / best_committed['cost_usd']:<22.3f} "
                         f"{c['cleared_rate']:.3f}")
    lines.append("  routed picks per task (* cleared, else the best available fallback):")
    for flavor in config["flavors"]:
        for bar in config["bars"]:
            picks = [f"{x['task']} {x['models']['routed']}{'*' if x['cleared'] else ''}"
                     for x in cells if (x["bar"], x["flavor"]) == (bar, flavor)]
            lines.append(f"    {bar} {flavor}: " + ", ".join(picks))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(prog="response_bank_split.py", description=__doc__.splitlines()[0])
    parser.add_argument("--matrix", required=True, help="the response-bank converter's default output")
    parser.add_argument("--cache", type=Path, help="folder holding scores_cal.jsonl (default: the converter's)")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        outcomes = load_outcomes(args.matrix)
        with open(args.root / RESULTS, encoding="utf-8") as fh:
            committed = json.load(fh)
        converter = _converter(args.root)
        cache = args.cache if args.cache is not None else converter.default_cache_dir()
        calibration = calibration_ids(converter, cache)
        lines = report(outcomes, calibration, committed)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
