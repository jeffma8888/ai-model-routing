"""Which 13.5 row chose each delegation cell's path, after a 13.2 condition on prices and sizes (DESIGN 13.8 v1.253)

Usage:
  python research/delegation_reasons.py --matrix llmrouterbench-matrix.jsonl [--root PATH]
  python research/delegation_reasons.py --dataset autobench --matrix autobench-tokens.jsonl --registry autobench-pool.json [--root PATH]
  python research/delegation_reasons.py --dataset tau2-bench --matrix tau2-calls.jsonl [--root PATH]
  python research/delegation_reasons.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl [--root PATH]

Reruns a committed delegation run as research/per_item_delegation.py does (its `rerun`: the same
13.9 run on the same matrix, checked against the same committed summary), then counts the run's
cells per (flavor, point) by the 13.5 row and `reason` that chose their path. Before the counts it
states the condition: with inline work in a call of its own, a separate inline call costs more than
delegating at every work size when slack * p_in > B * p_out, slack = K * (rho * C - B) - (1 + T) *
(B + R) tokens, p_in and p_out the parent's list prices; per point it prints the slack and how many
of the run's parents meet it, and a check line counts the `cost_effective` cells at a separate
point whose parent meets it and how many of them delegate. Standard library and the model_routing
package. Read by research/where-delegation-pays.md. Exit 0, or 2 with one `error: ...` line on what
research/per_item_delegation.py refuses, a tiered model, or an unknown reason.
"""

import argparse
import importlib.util
import sys
from collections import Counter
from fractions import Fraction
from pathlib import Path

from model_routing import delegation as dl

ROOT = Path(__file__).resolve().parents[1]
PER_ITEM = Path(__file__).resolve().with_name("per_item_delegation.py")
# the 13.6 reason constants in their order, each with its 13.5 row (`None`: row 3 or 4 by flavor)
REASONS = {dl.PARENT_EXCLUDED_FAMILY: 1, dl.PARENT_NOT_INDEPENDENT: 1, dl.PARENT_CONTEXT_FULL: 1,
           dl.PARENT_BELOW_BAR: 2, dl.DELEGATE_CHEAPER: 3, dl.INLINE_CHEAPER: 3, dl.DELEGATE_BETTER: None,
           dl.INLINE_AS_GOOD: None, dl.ONLY_PARENT_CLEARS: 5, dl.NONE_CLEAR: 7}
ORDER = {reason: j for j, reason in enumerate(REASONS)}
MODES = {dl.DELEGATE: 0, dl.INLINE: 1}
CONDITION = ("condition (DESIGN.md 13.8 v1.253): a separate inline call costs more than delegating at every size "
             "when slack * p_in > B * p_out, slack = K * (rho * C - B) - (1 + T) * (B + R)")


def _per_item():
    spec = importlib.util.spec_from_file_location("research_delegation_reasons_per_item", PER_ITEM)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def row_of(reason, flavor) -> int:
    """The 13.5 row that gives `reason` in `flavor`."""
    if reason not in REASONS:
        raise ValueError(f"unknown reason {reason!r}")
    row = REASONS[reason]
    if row is None:
        return 3 if flavor == "cost_effective" else 4
    return row


def slack(point):
    """K * (rho * C - B) - (1 + T) * (B + R) in tokens, exact, for a point whose inline work is a
    call of its own; None for a folded point. An int when it is a whole number."""
    if not point["inline_separate_call"]:
        return None
    k, rho = point.get("work_calls", 1), Fraction(point.get("cached_read_ratio", 1))
    c, b, r, t = (point[key] for key in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns"))
    value = k * (rho * c - b) - (1 + t) * (b + r)
    return int(value) if value.denominator == 1 else value


def meets(point, model):
    """Whether `slack * p_in > B * p_out` for `model` as the parent, in exact arithmetic on its list
    prices; None for a folded point."""
    s = slack(point)
    if s is None:
        return None
    return Fraction(s) * Fraction(model.price_in) > point["brief_tokens"] * Fraction(model.price_out)


def counts(full) -> dict:
    """{(flavor, point): Counter of (row, reason, mode)}, flavors and points in config order."""
    config = full["config"]
    out = {(f, p): Counter() for f in config["flavors"] for p in range(len(config["points"]))}
    for cell in full["cells"]:
        out[cell["flavor"], cell["point"]][row_of(cell["reason"], cell["flavor"]), cell["reason"], cell["mode"]] += 1
    return out


def _count(n, noun):
    return f"{n:,} {noun}" + ("" if n == 1 else "s")


def _tokens(value):
    return f"{value:,}" if isinstance(value, int) else f"{float(value):,.4f}"


def _ratio(model):
    return model.price_out / model.price_in if model.price_in else float("inf")


def report(full, registry, name) -> list:
    """The lines the script prints for one 13.9 run on `registry`; `name` is the dataset's."""
    for m in registry.models:
        if m.price_tiers:
            raise ValueError(f"model {m.id!r} has price tiers, which this script does not check")
    config = full["config"]
    points, parents = config["points"], [registry.get(p) for p in config["parents"]]
    found = counts(full)
    lines = [
        f"Which 13.5 row chose each cell's path on {name}: the cells of the 13.9 run by flavor, point, row and reason",
        f"run: {len(full['cells']):,} cells ({_count(len(config['bars']), 'bar')}, "
        f"{_count(len(config['flavors']), 'flavor')}, {_count(len(points), 'point')}, "
        f"{_count(len(parents), 'parent')}, {_count(len(config['seeds']), 'seed')}, "
        f"{_count(len(full['tasks']), 'task')})",
        CONDITION,
    ]
    for index, point in enumerate(points):
        c, b, r, t = (point[key] for key in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns"))
        head = (f"  point {index}: C {c:,}, B {b:,}, R {r:,}, T {t}, "
                f"{'separate' if point['inline_separate_call'] else 'folded'}, K {point.get('work_calls', 1)}, "
                f"rho {point.get('cached_read_ratio', 1):g}: ")
        s = slack(point)
        if s is None:
            lines.append(head + "does not apply (folded)")
            continue
        met = [m for m in parents if meets(point, m)]
        line = (head + f"slack {_tokens(s)}, slack / B {float(Fraction(s) / b):.4f}" if b else
                head + f"slack {_tokens(s)}, slack / B -")
        line += f"; met by {len(met)} of {len(parents)} parents"
        if met:
            top = max(_ratio(m) for m in met)
            first = min(m.id for m in met if _ratio(m) == top)
            line += f", highest ratio {top:.4f} ({first})"
        lines.append(line)
    lines.append("cells by 13.5 row and reason")
    for (flavor, index), tally in found.items():
        parts = [f"row {row} {reason} {mode} {n:,}" for (row, reason, mode), n in
                 sorted(tally.items(), key=lambda kv: (kv[0][0], ORDER[kv[0][1]], MODES[kv[0][2]]))]
        lines.append(f"  {flavor:<14}  point {index}  {_count(sum(tally.values()), 'cell')}: " + "; ".join(parts))
    checked = [cell for cell in full["cells"] if cell["flavor"] == "cost_effective"
               and meets(points[cell["point"]], registry.get(cell["parent"]))]
    delegated = sum(cell["mode"] == dl.DELEGATE for cell in checked)
    lines.append(f"check, cost_effective: {len(checked):,} cells at a separate point whose parent meets the "
                 f"condition, {delegated:,} of them delegate")
    return lines


def run(matrix, root=ROOT, dataset="llmrouterbench", registry=None) -> list:
    """research/per_item_delegation.py's `rerun` on the matrix, then `report`."""
    pid = _per_item()
    _rows, pool, full = pid.rerun(matrix, root, dataset, registry)
    return report(full, pool, pid.NAMES[dataset])


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="delegation_reasons.py", description=__doc__.splitlines()[0])
    parser.add_argument("--matrix", required=True,
                        help="the converter's output (JSONL), as for research/per_item_delegation.py")
    parser.add_argument("--dataset", choices=("llmrouterbench", "autobench", "tau2-bench", "tau2-bench-pooled"),
                        default="llmrouterbench", help="the delegation evidence to rerun (default: llmrouterbench)")
    parser.add_argument("--registry", help="with --dataset autobench: the AutoBench converter's --registry output")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        lines = run(args.matrix, args.root, args.dataset, args.registry)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
