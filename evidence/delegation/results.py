"""Delegation results on the AutoBench 2026 matrix and their tables (DESIGN 13.10).

Usage:
  python evidence/delegation/results.py --matrix MATRIX.jsonl --registry POOL.json --out results.json
  python evidence/delegation/results.py --table results.json
  python evidence/delegation/results.py --table results.json --bar 0.8 --point 1

``--matrix`` runs ``evaluate_delegation`` (DESIGN 13.9) on the converter's ``--task-by all
--tokens`` matrix and ``--registry`` pool, at the bars, seeds and grid points named below,
and keeps the config, tasks and summary (no cells). ``--table`` prints the mean over
parents of each (bar, flavor, point); with ``--bar`` and ``--point`` it prints one row per
(flavor, parent) for that bar and point. Standard library and the model_routing package.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

from model_routing import Registry, evaluate_delegation

BARS = (0.7, 0.8)
SEEDS = 50
CONTEXT_TOKENS = (8000, 64000, 200000)
BRIEF_TOKENS = 500
RESULT_TOKENS = 500
CARRY_TURNS = 1
INLINE_SEPARATE_CALL = True
STRATEGIES = ("decision", "inline", "delegate")
KEYS = ("config", "tasks", "summary")


def points() -> list:
    return [{"context_tokens": c, "brief_tokens": BRIEF_TOKENS, "result_tokens": RESULT_TOKENS,
             "carry_turns": CARRY_TURNS, "inline_separate_call": INLINE_SEPARATE_CALL}
            for c in CONTEXT_TOKENS]


def run(rows, registry) -> dict:
    result = evaluate_delegation(rows, registry, bars=list(BARS), points=points(),
                                 seeds=range(SEEDS))
    return {key: result[key] for key in KEYS}


def _layout(headers, rows) -> list:
    cells = [[str(c) for c in row] for row in [headers] + rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip()
             for row in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return lines


def _index(results: dict) -> dict:
    for key in ("config", "summary"):
        if key not in results:
            raise ValueError(f"results have no {key!r} key")
    rows = {}
    for row in results["summary"]:
        key = (row["bar"], row["flavor"], row["point"], row["parent"], row["strategy"])
        if key in rows:
            raise ValueError(f"repeated summary row {key}")
        rows[key] = row
    return rows


def _get(rows, bar, flavor, point, parent, strategy) -> dict:
    key = (bar, flavor, point, parent, strategy)
    if key not in rows:
        raise ValueError(f"no summary row for bar {bar}, {flavor}, point {point}, "
                         f"parent {parent}, {strategy}")
    return rows[key]


def _cells(found: list) -> list:
    """success, cost of each strategy in STRATEGIES order, then the decision's delegate rate."""
    out = []
    for strategy in STRATEGIES:
        out += [f"{found[strategy]['success']:.3f}", f"{found[strategy]['cost_usd']:.4f}"]
    return out


HEADERS = ["dec_success", "dec_cost", "inl_success", "inl_cost", "del_success", "del_cost"]


def table(results: dict) -> str:
    rows = _index(results)
    config = results["config"]
    lines = []
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            for index, point in enumerate(config["points"]):
                found = {s: [_get(rows, bar, flavor, index, p, s) for p in config["parents"]]
                         for s in STRATEGIES}
                mean = {s: {k: math.fsum(r[k] for r in found[s]) / len(found[s])
                            for k in ("success", "cost_usd")} for s in STRATEGIES}
                rate = math.fsum(r["delegate_rate"] for r in found["decision"]) / len(
                    found["decision"])
                lines.append([str(bar), flavor, str(point["context_tokens"])] + _cells(mean)
                             + [f"{rate:.3f}"])
    if not lines:
        raise ValueError("config has no (bar, flavor, point)")
    return "\n".join(_layout(["bar", "flavor", "context"] + HEADERS + ["delegated"], lines))


def parent_table(results: dict, bar, point: int) -> str:
    rows = _index(results)
    config = results["config"]
    if bar not in config["bars"]:
        raise ValueError(f"bar {bar} is not in the config bars {config['bars']}")
    if not 0 <= point < len(config["points"]):
        raise ValueError(f"point {point} is not an index into the {len(config['points'])} "
                         "config points")
    lines = []
    for flavor in config["flavors"]:
        for parent in config["parents"]:
            found = {s: _get(rows, bar, flavor, point, parent, s) for s in STRATEGIES}
            lines.append([flavor, parent, f"{found['decision']['delegate_rate']:.3f}"]
                         + _cells(found))
    return "\n".join(_layout(["flavor", "parent", "delegated"] + HEADERS, lines))


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


def _read_rows(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON: {exc}") from None
    return rows


def main(argv=None) -> int:
    parser = _Parser(prog="results.py", description="delegation results file and tables")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--matrix", help="converter output with --task-by all --tokens")
    mode.add_argument("--table", help="a results file to print the tables of")
    parser.add_argument("--registry", help="converter --registry output (with --matrix only)")
    parser.add_argument("--out", help="results file to write (with --matrix only)")
    parser.add_argument("--bar", type=float, help="with --table and --point: one row per parent")
    parser.add_argument("--point", type=int, help="with --table and --bar: a config point index")
    try:
        args = parser.parse_args(argv)
        if args.matrix is not None:
            if args.registry is None or args.out is None:
                raise _UsageError("--matrix needs --registry and --out")
            if args.bar is not None or args.point is not None:
                raise _UsageError("--bar and --point are only used with --table")
            result = run(_read_rows(args.matrix), Registry.load(args.registry))
            text = json.dumps(result, indent=2) + "\n"
            out = Path(args.out)
            part = out.with_name(out.name + ".part")
            try:
                part.write_text(text, encoding="utf-8")
                part.replace(out)
            finally:
                part.unlink(missing_ok=True)
            return 0
        if args.registry is not None or args.out is not None:
            raise _UsageError("--registry and --out are only used with --matrix")
        if (args.bar is None) != (args.point is None):
            raise _UsageError("--bar and --point go together")
        results = _read_object(args.table)
        if args.bar is None:
            text = table(results)
        else:
            text = parent_table(results, args.bar, args.point)
    except (_UsageError, ValueError, KeyError, TypeError, OSError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    print(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
