"""Reduce an evaluator result to the committed RouterBench results and print its tables (DESIGN 12.7).

Usage:
  python evidence/routerbench/results.py --evaluate FULL.json --out results.json
  python evidence/routerbench/results.py --table results.json

Standard library only. ``--evaluate`` reads the output of ``model-routing evaluate --json``
and keeps the summary and the routed per-task rows; ``--table`` prints the two tables
that RESULTS.md shows.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KEYS = ("config", "tasks", "summary", "per_task")


def reduce(result: dict) -> dict:
    for key in KEYS:
        if key not in result:
            raise ValueError(f"result has no {key!r} key")
    out = {key: result[key] for key in KEYS[:3]}
    out["per_task"] = [row for row in result["per_task"] if row["strategy"] == "routed"]
    return out


def _layout(headers, rows) -> list[str]:
    cells = [[str(c) for c in row] for row in [headers] + rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip()
             for row in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return lines


def _rate(value) -> str:
    return "-" if value is None else f"{value:.3f}"


def table(results: dict) -> str:
    for key in ("config", "summary"):
        if key not in results:
            raise ValueError(f"results have no {key!r} key")
    config, summary = results["config"], results["summary"]
    blocks = [(bar, flavor) for bar in config["bars"] for flavor in config["flavors"]]
    if not blocks:
        raise ValueError("config has no (bar, flavor)")
    first = [r for r in summary if (r["bar"], r["flavor"]) == blocks[0]]
    models = [r for r in first if r["strategy"].startswith("model:")]
    if not models:
        raise ValueError(f"no model: summary row for bar {blocks[0][0]}, {blocks[0][1]}")
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    routed_rows = []
    for bar, flavor in blocks:
        routed = [r for r in summary
                  if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, "routed")]
        if not routed:
            raise ValueError(f"no routed summary row for bar {bar}, {flavor}")
        row = routed[0]
        ratio = None if best["cost_usd"] == 0 else row["cost_usd"] / best["cost_usd"]
        routed_rows.append([str(bar), flavor, _rate(row["success"]), f"{row['cost_usd']:.4f}",
                            _rate(ratio), _rate(row["cleared_rate"]),
                            _rate(row["bar_violation_rate"])])
    baseline_rows = [[r["strategy"], _rate(r["success"]), f"{r['cost_usd']:.4f}"]
                     for r in first if r["strategy"] != "routed"]
    lines = _layout(["bar", "flavor", "success", "cost_usd", "vs_best_model", "cleared_rate",
                     "bar_violation_rate"], routed_rows)
    lines += [""] + _layout(["strategy", "success", "cost_usd"], baseline_rows)
    return "\n".join(lines)


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def _read_object(path: str) -> dict:
    with open(path, encoding="utf-8") as fh:
        try:
            value = json.load(fh)
        except json.JSONDecodeError as exc:
            raise ValueError(f"{path}: invalid JSON: {exc}") from None
    if not isinstance(value, dict):
        raise ValueError(f"{path}: expected a JSON object, got {type(value).__name__}")
    return value


def main(argv=None) -> int:
    parser = _Parser(prog="results.py", description="RouterBench results file and tables")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--evaluate", help="output of model-routing evaluate --json")
    mode.add_argument("--table", help="a results file to print the tables of")
    parser.add_argument("--out", help="results file to write (with --evaluate only)")
    try:
        args = parser.parse_args(argv)
        if args.evaluate is not None and args.out is None:
            raise _UsageError("--evaluate needs --out")
        if args.table is not None and args.out is not None:
            raise _UsageError("--out is only used with --evaluate")
        if args.evaluate is not None:
            text = json.dumps(reduce(_read_object(args.evaluate)), indent=2) + "\n"
            out = Path(args.out)
            part = out.with_name(out.name + ".part")
            try:
                part.write_text(text, encoding="utf-8")
                part.replace(out)
            finally:
                part.unlink(missing_ok=True)
            return 0
        text = table(_read_object(args.table))
    except (_UsageError, ValueError, KeyError, TypeError, OSError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
