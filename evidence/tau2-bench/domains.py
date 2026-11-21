"""Reduce the tau2-bench cascade run to its per-domain model rows and print their table (DESIGN 12.29 v1.555).

Usage:
  python evidence/tau2-bench/domains.py --evaluate FULL.json --out cascades-domains.json
  python evidence/tau2-bench/domains.py --table cascades-domains.json

Standard library only. ``--evaluate`` reads the output of ``model-routing evaluate --json`` on the
matrix that ``evidence/tau2-bench/cascades.py --out`` writes and keeps ``config``, ``tasks`` and the
``per_task`` rows of the ``model:`` strategies at the first (bar, flavor) of ``config``, the rows the
12.7 script drops. A ``model:`` row's ``success``, ``cost_usd`` and ``escalation_share`` are the same
at every bar and flavor (its ``below_bar_rate`` depends on the bar), which ``reduce`` checks, so one
block stands for all and a file it wrote reduces to itself. ``--table`` prints, per domain, the best
single agent by DESIGN 12.15's rule (highest held-out success, then lower cost, then name) and every
cascade whose row beats it on both counts (success at least as high and cost at most as high, one of
them strictly), by highest success, then lower cost, then name.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

KEYS = ("config", "tasks", "per_task")
SAME = ("success", "cost_usd", "escalation_share")
PREFIX = "model:"


def reduce(result: dict) -> dict:
    for key in KEYS:
        if key not in result:
            raise ValueError(f"result has no {key!r} key")
    config = result["config"]
    if not config["bars"] or not config["flavors"]:
        raise ValueError("config has no (bar, flavor)")
    first = (config["bars"][0], config["flavors"][0])
    rows = [row for row in result["per_task"] if row["strategy"].startswith(PREFIX)]
    kept = {}
    for row in rows:
        if (row["bar"], row["flavor"]) == first:
            key = (row["task"], row["strategy"])
            if key in kept:
                raise ValueError(f"two rows for {key[0]}, {key[1]} at bar {first[0]}, {first[1]}")
            kept[key] = row
    for row in rows:
        key = (row["task"], row["strategy"])
        if key not in kept:
            raise ValueError(f"no row for {key[0]}, {key[1]} at bar {first[0]}, {first[1]}")
        for name in SAME:
            if row[name] != kept[key][name]:
                raise ValueError(f"{key[0]}, {key[1]}: {name} differs at bar {row['bar']}, {row['flavor']}")
    if not kept:
        raise ValueError(f"no {PREFIX} per_task row at bar {first[0]}, {first[1]}")
    return {"config": config, "tasks": result["tasks"], "per_task": list(kept.values())}


def beats(a: dict, b: dict) -> bool:
    return (a["success"] >= b["success"] and a["cost_usd"] <= b["cost_usd"]
            and (a["success"] > b["success"] or a["cost_usd"] < b["cost_usd"]))


def domain(rows: list[dict], task: str) -> tuple[dict, list[dict]]:
    """The best single agent of `task` and the cascades that beat it on both counts, in table order."""
    mine = [r for r in rows if r["task"] == task]
    agents = [r for r in mine if ">" not in r["strategy"]]
    if not agents:
        raise ValueError(f"no single-agent row for {task}")
    best = min(agents, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    winners = sorted((r for r in mine if ">" in r["strategy"] and beats(r, best)),
                     key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    return best, winners


def _rate(value) -> str:
    return "-" if value is None else f"{value:.3f}"


def _layout(headers, rows) -> list[str]:
    cells = [[str(c) for c in row] for row in [headers] + rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip() for row in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return lines


def table(results: dict) -> str:
    for key in KEYS:
        if key not in results:
            raise ValueError(f"results have no {key!r} key")
    out = []
    for task in results["tasks"]:
        best, winners = domain(results["per_task"], task)
        for r in [best] + winners:
            ratio = None if best["cost_usd"] == 0 else r["cost_usd"] / best["cost_usd"]
            out.append([task, r["strategy"][len(PREFIX):], _rate(r["success"]), f"{r['cost_usd']:.4f}",
                        _rate(ratio), _rate(r["escalation_share"])])
    return "\n".join(_layout(["task", "candidate", "success", "cost_usd", "vs_agent", "escalation_share"], out))


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
    parser = _Parser(prog="domains.py", description="tau2-bench per-domain cascade rows and their table")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--evaluate", help="output of model-routing evaluate --json")
    mode.add_argument("--table", help="a per-domain file to print the table of")
    parser.add_argument("--out", help="per-domain file to write (with --evaluate only)")
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
