"""Delegation results on the AutoBench 2026 matrix and their tables (DESIGN 13.10).

Usage:
  python evidence/delegation/results.py --matrix MATRIX.jsonl --registry POOL.json --out results.json
  python evidence/delegation/results.py --matrix MATRIX.jsonl --registry POOL.json --grid variants --out variants.json
  python evidence/delegation/results.py --table results.json
  python evidence/delegation/results.py --table results.json --bar 0.8 --point 1
  python evidence/delegation/results.py --breakeven results.json --bar 0.8 --point 1

``--matrix`` runs ``evaluate_delegation`` (DESIGN 13.9) on the converter's ``--task-by all
--tokens`` matrix and ``--registry`` pool, at the bars, seeds and grid points named below,
and keeps the config, tasks and summary (no cells). Points 0 to 2 put inline work in a
parent call of its own at three context sizes; point 3 folds it into the parent's next call.
With ``--grid variants`` it runs the variant points instead, which change a knob the base grid
holds fixed (variant point 0: folded work of two calls at 64,000 context tokens; variant
point 1: point 2 with the parent's reads of the context at 0.1 of its list input price;
variant point 2: variant point 0 at 15 work calls, the median run size of TRAIL's sub-agents).
``--table`` prints the mean over parents of each (bar, flavor, point); with ``--bar`` and ``--point`` it prints one row per
(flavor, parent) for that bar and point. ``--breakeven`` with ``--bar`` and ``--point`` prints,
per (flavor, parent), how much held-out success a lossy hand-off may lose before delegating
does no better than working inline. Standard library and the model_routing package.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from pathlib import Path

from model_routing import Registry, evaluate_delegation

BARS = (0.7, 0.8)
SEEDS = 50
CONTEXT_TOKENS = (8000, 64000, 200000)
FOLDED_CONTEXT_TOKENS = 8000
BRIEF_TOKENS = 500
RESULT_TOKENS = 500
CARRY_TURNS = 1
STRATEGIES = ("decision", "inline", "delegate")
KEYS = ("config", "tasks", "summary")
VARIANT_CONTEXT_TOKENS = 64000
VARIANT_WORK_CALLS = 2
VARIANT_CACHED_READ_RATIO = 0.1
VARIANT_OBSERVED_WORK_CALLS = 15
GRIDS = ("base", "variants")


def points() -> list:
    """Points 0 to 2 with inline work in a call of its own, then point 3 with it folded.

    At K = 1 a folded point's costs do not read C, which enters only the parent's context
    check, so one folded point stands for every C that leaves every parent room (DESIGN 13.10).
    """
    grid = [(c, True) for c in CONTEXT_TOKENS] + [(FOLDED_CONTEXT_TOKENS, False)]
    return [{"context_tokens": c, "brief_tokens": BRIEF_TOKENS, "result_tokens": RESULT_TOKENS,
             "carry_turns": CARRY_TURNS, "inline_separate_call": separate}
            for c, separate in grid]


def variant_points() -> list:
    """Variant point 0: folded work of two calls at 64,000 context tokens; variant point 1:
    base point 2 with ``cached_read_ratio`` 0.1, an assumed ratio; variant point 2: variant
    point 0 with ``work_calls`` 15, the rounded-up median of the runs' model calls in
    evidence/trail/summary.json, held here as a literal (DESIGN 13.10)."""
    first = {"context_tokens": VARIANT_CONTEXT_TOKENS, "brief_tokens": BRIEF_TOKENS,
             "result_tokens": RESULT_TOKENS, "carry_turns": CARRY_TURNS,
             "inline_separate_call": False, "work_calls": VARIANT_WORK_CALLS}
    return [first, dict(points()[2], cached_read_ratio=VARIANT_CACHED_READ_RATIO),
            dict(first, work_calls=VARIANT_OBSERVED_WORK_CALLS)]


def run(rows, registry, grid="base") -> dict:
    if grid not in GRIDS:
        raise ValueError(f"grid must be 'base' or 'variants', got {grid!r}")
    grid_points = points() if grid == "base" else variant_points()
    result = evaluate_delegation(rows, registry, bars=list(BARS), points=grid_points,
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
    if not config["parents"]:
        raise ValueError("config has no parents")
    multi = any("work_calls" in point for point in config["points"])
    cached = any("cached_read_ratio" in point for point in config["points"])
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
                calls = [str(point.get("work_calls", 1))] if multi else []
                calls += [str(point.get("cached_read_ratio", 1.0))] if cached else []
                lines.append([str(bar), flavor, str(point["context_tokens"]),
                              str(point["inline_separate_call"])] + calls + _cells(mean)
                             + [f"{rate:.3f}"])
    if not lines:
        raise ValueError("config has no (bar, flavor, point)")
    columns = (["bar", "flavor", "context", "separate"] + (["calls"] if multi else [])
               + (["cached"] if cached else []))
    return "\n".join(_layout(columns + HEADERS + ["delegated"], lines))


def _check_bar_point(config: dict, bar, point: int) -> None:
    if bar not in config["bars"]:
        raise ValueError(f"bar {bar} is not in the config bars {config['bars']}")
    if not 0 <= point < len(config["points"]):
        raise ValueError(f"point {point} is not an index into the {len(config['points'])} "
                         "config points")


def parent_table(results: dict, bar, point: int) -> str:
    rows = _index(results)
    config = results["config"]
    _check_bar_point(config, bar, point)
    lines = []
    for flavor in config["flavors"]:
        for parent in config["parents"]:
            found = {s: _get(rows, bar, flavor, point, parent, s) for s in STRATEGIES}
            lines.append([flavor, parent, f"{found['decision']['delegate_rate']:.3f}"]
                         + _cells(found))
    return "\n".join(_layout(["flavor", "parent", "delegated"] + HEADERS, lines))


def _signed(value: float) -> str:
    """Three decimals with the sign kept, and a value that rounds to zero as 0.000."""
    text = f"{value:.3f}"
    return "0.000" if text == "-0.000" else text


BREAKEVEN_HEADERS = ["flavor", "parent", "delegated", "dec_success", "inl_success",
                     "del_success", "del_margin", "dec_breakeven"]


def breakeven_table(results: dict, bar, point: int) -> str:
    """Per (flavor, parent): the held-out success a lossy hand-off may lose (DESIGN 13.10).

    ``del_margin`` is always delegating's success minus always inline's; ``dec_breakeven`` is
    the decision's success minus always inline's over its delegate rate, the uniform drop on
    the delegated seeds at which the decision falls to inline's success (exact for one task,
    for the stored success: the mean over seeds of each seed's held-out rate).
    """
    rows = _index(results)
    config = results["config"]
    _check_bar_point(config, bar, point)
    lines = []
    for flavor in config["flavors"]:
        for parent in config["parents"]:
            found = {s: _get(rows, bar, flavor, point, parent, s) for s in STRATEGIES}
            dec, inl, dlg = (found[s]["success"] for s in STRATEGIES)
            rate = found["decision"]["delegate_rate"]
            breakeven = "-" if rate == 0 else _signed((dec - inl) / rate)
            lines.append([flavor, parent, f"{rate:.3f}", f"{dec:.3f}", f"{inl:.3f}",
                          f"{dlg:.3f}", _signed(dlg - inl), breakeven])
    return "\n".join(_layout(BREAKEVEN_HEADERS, lines))


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def clashing_input(out, inputs):
    """The option of the first ``(option, path)`` of ``inputs`` that names ``out`` or ``<out>.part``, else None.

    Two paths name the same file when their ``os.path.realpath`` values are equal (another
    spelling, or a symbolic link and the file it reaches), or when both exist and
    ``os.path.samefile`` says so (a hard link); an ``OSError`` from ``samefile`` counts as not
    the same. Opens, writes and removes no file (DESIGN 13.10 v1.269).
    """
    out = Path(out)
    targets = (out, out.with_name(out.name + ".part"))
    for option, path in inputs:
        for target in targets:
            if os.path.realpath(path) == os.path.realpath(target):
                return option
            if os.path.exists(path) and os.path.exists(target):
                try:
                    if os.path.samefile(path, target):
                        return option
                except OSError:
                    pass
    return None


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
    mode.add_argument("--breakeven", help="a results file to print the break-even table of "
                                          "(with --bar and --point)")
    parser.add_argument("--registry", help="converter --registry output (with --matrix only)")
    parser.add_argument("--out", help="results file to write (with --matrix only)")
    parser.add_argument("--grid", choices=GRIDS,
                        help="with --matrix: the base grid (default) or the variant points")
    parser.add_argument("--bar", type=float,
                        help="with --point and --table or --breakeven: one row per parent")
    parser.add_argument("--point", type=int,
                        help="with --bar and --table or --breakeven: a config point index")
    try:
        args = parser.parse_args(argv)
        if args.matrix is not None:
            if args.registry is None or args.out is None:
                raise _UsageError("--matrix needs --registry and --out")
            if args.bar is not None or args.point is not None:
                raise _UsageError("--bar and --point are only used with --table or --breakeven")
            out = Path(args.out)
            part = out.with_name(out.name + ".part")
            clash = clashing_input(out, [("--matrix", args.matrix), ("--registry", args.registry)])
            if clash is not None:
                raise _UsageError(f"--out (or its .part file) names the same file as {clash}")
            try:
                result = run(_read_rows(args.matrix), Registry.load(args.registry),
                             grid=args.grid or "base")
                text = json.dumps(result, indent=2) + "\n"
                part.write_text(text, encoding="utf-8")
                part.replace(out)
            finally:
                try:
                    part.unlink(missing_ok=True)
                except OSError:
                    pass
            return 0
        if args.registry is not None or args.out is not None:
            raise _UsageError("--registry and --out are only used with --matrix")
        if args.grid is not None:
            raise _UsageError("--grid is only used with --matrix")
        if args.breakeven is not None:
            if args.bar is None or args.point is None:
                raise _UsageError("--breakeven needs --bar and --point")
            text = breakeven_table(_read_object(args.breakeven), args.bar, args.point)
            print(text)
            return 0
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
