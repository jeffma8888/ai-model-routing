"""Longtail-SWE runs 0, 1 and 2 side by side (DESIGN 12.22, v1.490, row E26h).

The release holds three agent runs per (task, model). evidence/longtail-swe/results.json (12.26) is
run 0 alone; this script builds the 12.25 matrix at each run with the converter, evaluates each with
the 12.26 config and prints, per run, each model's resolved count, the unscored runs, each model
alone, the `best_on_calibration` baseline and the routed rows per bar and flavor, then the spread of
the routed success and cost over the three runs. It reads the four pinned files from `--cache`
(default: the converter's), each checked by size and sha256 (an absent one is downloaded), and needs
`pyarrow` as the converter does. Run: python research/longtail_runs.py
"""
import argparse
import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model_routing import evaluate, outcomes_from_rows  # noqa: E402

RUNS = (0, 1, 2)
BARS = [0.6, 0.7, 0.8, 0.9]  # the 12.26 config
SEEDS = 50
FLAVORS = ["cost_effective", "cost_blind"]


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONVERT = load("longtail_swe_convert_for_runs", ROOT / "evidence" / "longtail-swe" / "convert.py")
RESULTS = load("routerbench_results_for_runs", ROOT / "evidence" / "routerbench" / "results.py")


def records(cache=None) -> list:
    """The converter's records of the four pinned files, in `FILES` order."""
    paths = CONVERT.fetch(cache)
    registry = json.loads(CONVERT.REGISTRY.read_text(encoding="utf-8"))
    out = []
    for name in CONVERT.FILES:
        try:
            out += CONVERT.run_records(CONVERT.read_rows(paths[name]), registry)
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from None
    return out


def collect(recs) -> dict:
    """Per run, the converter's report and the reduced 12.26 result of its matrix."""
    out = {}
    for run in RUNS:
        rows, report = CONVERT.convert(recs, run)
        result = evaluate(outcomes_from_rows(rows), bars=BARS, seeds=range(SEEDS))
        out[run] = (report, RESULTS.reduce({k: v for k, v in result.items() if k != "cells"}))
    return out


def num(value, places=3) -> str:
    return "-" if value is None else f"{value:.{places}f}"


def row_of(summary, bar, flavor, strategy) -> dict:
    found = [r for r in summary if r["bar"] == bar and r["flavor"] == flavor and r["strategy"] == strategy]
    if len(found) != 1:
        raise ValueError(f"{len(found)} summary rows for {bar} {flavor} {strategy}, not one")
    return found[0]


def routed_lines(run, summary) -> list:
    """The routed rows of one run, one line per bar and flavor."""
    lines = []
    for bar in BARS:
        for flavor in FLAVORS:
            r = row_of(summary, bar, flavor, "routed")
            lines.append(f"{run:<4} {bar:<4} {flavor:<15} {num(r['success']):>7} {num(r['cost_usd'], 2):>8} "
                         f"{num(r['cleared_rate']):>7} {num(r['below_bar_rate']):>9} {num(r['bar_violation_rate']):>9}")
    return lines


def model_lines(run, summary, models) -> list:
    """Each model alone in one run, at the first bar and flavor (a model row is the same at every one)."""
    lines = []
    for m in models:
        r = row_of(summary, BARS[0], FLAVORS[0], f"model:{m}")
        lines.append(f"{run:<4} {m:<27} {num(r['success']):>7} {num(r['cost_usd'], 2):>8}")
    return lines


def baseline_line(run, summary) -> str:
    """The `best_on_calibration` row of one run, at the first bar and flavor."""
    r = row_of(summary, BARS[0], FLAVORS[0], "best_on_calibration")
    return f"{run:<4} {num(r['success']):>7} {num(r['cost_usd'], 2):>8}"


def block(data) -> str:
    """The note's `## Results` block from `collect`'s output."""
    first = data[RUNS[0]][0]
    models = first["models"]
    out = [f"Runs {', '.join(map(str, RUNS[:-1]))} and {RUNS[-1]}, each the 12.25 matrix ({first['tasks'][CONVERT.TASK]['items']} "
           f"items, {len(models)} models) under the 12.26 config (bars {' '.join(map(str, BARS))}, {SEEDS} seeds, both flavors)",
           "", "Resolved per model (unscored runs, a miss that keeps its charge, in brackets)"]
    out.append("run  " + "  ".join(models))
    for run in RUNS:
        report = data[run][0]
        cells = [f"{report['resolved'][m]} ({len(report['unscored'][m])})".ljust(len(m)) for m in models]
        out.append(f"{run:<4} " + "  ".join(cells).rstrip())
    out += ["", f"Each model alone, held-out success and cost in USD over {SEEDS} seeds (bar {BARS[0]}, {FLAVORS[0]})"]
    out.append("run  model                       success     cost")
    for run in RUNS:
        out += model_lines(run, data[run][1]["summary"], models)
    out += ["", "best_on_calibration (the same at every bar and flavor)", "run  success     cost"]
    for run in RUNS:
        out.append(baseline_line(run, data[run][1]["summary"]))
    out += ["", "Routed", "run  bar  flavor          success     cost cleared below_bar violation"]
    for run in RUNS:
        out += routed_lines(run, data[run][1]["summary"])
    out += ["", f"Routed spread over runs {RUNS[0]} to {RUNS[-1]}: lowest to highest",
            "bar  flavor          success        cost              violation"]
    for bar in BARS:
        for flavor in FLAVORS:
            rows = [row_of(data[run][1]["summary"], bar, flavor, "routed") for run in RUNS]
            s = sorted(r["success"] for r in rows)
            c = sorted(r["cost_usd"] for r in rows)
            v = sorted(r["bar_violation_rate"] for r in rows if r["bar_violation_rate"] is not None)
            vs = f"{num(v[0])} to {num(v[-1])}" if v else "-"
            out.append(f"{bar:<4} {flavor:<15} {num(s[0])} to {num(s[-1])}  {num(c[0], 2)} to {num(c[-1], 2)}  {vs}")
    return "\n".join(out) + "\n"


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None) -> int:
    parser = _Parser(prog="longtail_runs.py", description="Longtail-SWE runs 0 to 2 under the 12.26 config")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {CONVERT.default_cache_dir()})")
    try:
        args = parser.parse_args(argv)
        text = block(collect(records(args.cache)))
    except (ValueError, OSError, ImportError) as exc:
        msg = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {msg}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
