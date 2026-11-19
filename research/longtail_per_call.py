"""Longtail-SWE per call: the 13.5 decision scored on each run split into its model calls by a stated rule
(DESIGN 13.16 v1.496, row R50b)

Loads research/longtail_delegation.py from its own folder by path; its `read`, `matrix` and `points` give the
12.26 matrix (run 0), each run's counts (no dataset text) and the four points of research/longtail-delegation.md.
The release holds each run's token totals only, so the split is an assumption: a run of K calls, input total I
and output total O gives call j the output b_j = O // K, call 1 also O % K, and each call the same new input
a = L // T, where T = K (K + 1) / 2 and L = I - sum (K - j) b_j, the remainder r = L % T going r // K to call 1
and r % K to call K. Then sum (K - j + 1) a_j = L, so the calls read I and write O as the 13.9 per-call mode
(v1.74) checks. A run with L below 0 is refused and its item dropped for every model. It prints the split's
counts, per model the rows whose last call is over the context window, and what `evaluate_delegation` gives on
the split rows; it exits 2 if the harness refuses them. Needs `pyarrow` as the converter does. Exit 0, or 2 with
one `error: ...` line, a carriage return or newline escaped.

  python research/longtail_per_call.py [--cache DIR]
"""
import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent))
from model_routing import Registry, evaluate_delegation  # noqa: E402


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


LD = _load("longtail_delegation_for_per_call", HERE / "longtail_delegation.py")
STRATEGIES = ("decision", "inline", "delegate")


def _count(value) -> bool:
    return type(value) is int and value >= 0


def split(tin, tout, calls):
    """(new input a call, output a call) of a run by the stated rule, or None when its input is below its
    outputs' re-reads."""
    if type(calls) is not int or calls < 1:
        raise ValueError(f"calls must be an int >= 1, got {calls!r}")
    if not _count(tin) or not _count(tout):
        raise ValueError(f"input and output must be ints >= 0, got {tin!r} and {tout!r}")
    q, rem = divmod(tout, calls)
    outs = [q + rem] + [q] * (calls - 1)
    left = tin - sum((calls - 1 - j) * b for j, b in enumerate(outs))
    if left < 0:
        return None
    a, r = divmod(left, calls * (calls + 1) // 2)
    ins = [a] * calls
    ins[0] += r // calls
    ins[-1] += r % calls
    return ins, outs


def per_call(kept):
    """The one-call harness rows of (row, counts) pairs with their split calls, the refused runs, and the
    dropped items in first-seen order; a refused run drops its item for every model."""
    parts, refused, dropped = [], 0, []
    for row, c in kept:
        got = split(c["input"], c["output"], c["calls"])
        if got is None:
            refused += 1
            if row["item"] not in dropped:
                dropped.append(row["item"])
        parts.append((row, got))
    rows = [dict(row, call_input_tokens=got[0], call_output_tokens=got[1])
            for row, got in parts if row["item"] not in dropped]
    return rows, refused, dropped


def spread(values) -> str:
    return LD.spread(values)


def _range(values, fmt="{:,}") -> str:
    lo, hi = min(values), max(values)
    return fmt.format(lo) if lo == hi else f"{fmt.format(lo)} to {fmt.format(hi)}"


def block(pairs, registry, config) -> str:
    one, report, kept = LD.matrix(pairs)
    models = report["models"]
    brief = statistics.median_low([c["brief"] for _, c in kept])
    result = statistics.median_low([c["result"] for _, c in kept])
    pts = LD.points(brief, result)
    rows, refused, dropped = per_call([(r, c) for r, (_, c) in zip(one, kept)])
    last = [(r["model"], sum(r["call_input_tokens"]) + sum(r["call_output_tokens"])) for r in rows]
    out = [f"{LD.CONVERT.DATASET} at {LD.CONVERT.REVISION[:7]}: the 12.26 matrix (run 0, "
           f"{report['tasks'][LD.CONVERT.TASK]['items']} items, {len(models)} models, {len(kept)} rows), each run split "
           "into its model calls",
           f"Split: runs refused (input below their outputs' re-reads) {refused}, items dropped {len(dropped)}, "
           f"rows kept {len(rows)}",
           f"  new input a call: {spread([x for r in rows for x in r['call_input_tokens']])}",
           f"  output a call: {spread([x for r in rows for x in r['call_output_tokens']])}",
           f"  last call's read plus write: {spread([x for _, x in last])}",
           "Context window against the last call's read plus write",
           "model                      window      over  median last call"]
    for m in models:
        mine = [x for mm, x in last if mm == m]
        window = registry.get(m).context_window
        out.append(f"{m:<26} {window:>9,}  {sum(x > window for x in mine):>3} of {len(mine)}  "
                   f"{statistics.median_low(mine):>16,}")
    try:
        res = evaluate_delegation(rows, registry, bars=LD.BARS, points=pts, seeds=config["seeds"],
                                  flavors=config["flavors"], calibration_fraction=config["calibration_fraction"],
                                  min_samples=config["min_samples"], confidence=config["confidence"])
    except ValueError as exc:
        raise ValueError(f"the 13.9 harness refused the split rows: {exc}") from None
    cells = res["cells"]
    held = {c["held_out_items"] for c in cells}
    out.append(f"13.9 harness per call, bars {' '.join(map(str, LD.BARS))}, {len(config['seeds'])} seeds, "
               f"{_range(sorted(held))} held-out items, points (carry turns {LD.CARRY}, brief {brief:,}, "
               f"result {result:,}): " + "; ".join(
                   f"{i} context {p['context_tokens']:,} " + ("separate" if p["inline_separate_call"] else "folded")
                   for i, p in enumerate(pts)))
    out.append(f"  decision sizes over the cells: new input a call {_range([c['expected_input_tokens'] for c in cells])}, "
               f"output a call {_range([c['expected_output_tokens'] for c in cells])}, "
               f"work calls {_range([c['expected_work_calls'] for c in cells])}")
    flavors, bars = res["config"]["flavors"], res["config"]["bars"]
    for flavor in flavors:
        out.append(f"  {flavor}, cells whose decision is below the bar: " + "; ".join(
            f"bar {bar} {sum(c['below_bar'] for c in cells if (c['flavor'], c['bar']) == (flavor, bar))} of "
            f"{sum((c['flavor'], c['bar']) == (flavor, bar) for c in cells)}" for bar in bars))
    out.append("success and cost (USD summed over the held-out items), means over seeds")
    out.append("flavor          bar  point  parent                     delegated  decision        inline          "
               "delegate")
    summary = {(s["flavor"], s["bar"], s["point"], s["parent"], s["strategy"]): s for s in res["summary"]}
    tally = {f: [0, 0, 0] for f in flavors}
    for flavor in flavors:
        for bar in bars:
            for index in range(len(pts)):
                for parent in res["config"]["parents"]:
                    got = {s: summary[flavor, bar, index, parent, s] for s in STRATEGIES}
                    dec, inl, dlg = (got[s] for s in STRATEGIES)
                    tally[flavor][0] += 1
                    tally[flavor][1] += (dec["success"], dec["cost_usd"]) == (dlg["success"], dlg["cost_usd"])
                    tally[flavor][2] += dec["success"] >= inl["success"] and dec["cost_usd"] < inl["cost_usd"]
                    out.append(f"{flavor:<15} {bar:<4} {index:<6} {parent:<26} {dec['delegate_rate']:>9.2f}  "
                               + "  ".join(f"{got[s]['success']:.3f} {got[s]['cost_usd']:>8,.0f}" for s in STRATEGIES))
    for flavor in flavors:
        n, same, cheaper = tally[flavor]
        out.append(f"{flavor}: decision = always delegating on {same} of {n} rows; at or above always inline's "
                   f"success for less cost on {cheaper}")
    return "\n".join(out) + "\n"


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None) -> int:
    parser = _Parser(prog="longtail_per_call.py", description="Longtail-SWE per call, under a stated split")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {LD.CONVERT.default_cache_dir()})")
    try:
        args = parser.parse_args(argv)
        config = json.loads(LD.CONFIG.read_text(encoding="utf-8"))["config"]
        registry = Registry.load(LD.CONVERT.REGISTRY)
        raw = json.loads(LD.CONVERT.REGISTRY.read_text(encoding="utf-8"))
        text = block(LD.read(LD.CONVERT.fetch(args.cache), raw), registry, config)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        msg = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {msg}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
