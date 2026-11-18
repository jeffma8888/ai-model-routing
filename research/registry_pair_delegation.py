"""The registry's own pair as delegation evidence: superlinked/train-a-router-reasoning (DESIGN 13.16 v1.466, row R42).

Reads the three files research/registry_pair.py pins, through its `fetch`, `check_pair` and `outcomes`
(loaded from its own folder by path), and asks whether the pair can score the 13.5 inline-or-sub-agent
decision, each of the two models as the parent. A row records each model's correctness and USD cost and
no token counts, and both models list output at five times input, so a row's cost fixes E = cost /
price_in, its input-equivalent tokens, which is in + 5 * out, but not in + out, what the inline path's
later calls re-read (13.2): that lies between E / 5 and E. So the script prices every row at both ends,
`low` (out = E // 5 and in = E % 5, the fewest tokens that cost E) and `high` (in = E, out = 0), E
rounded to the nearest whole token, and scores both with the 13.9 harness's own cell (`_calibrate`,
`_router`, `_cell` and `_summary` of model_routing/delegation_eval.py, private names a research script
may use, as research/delegation_price_sensitivity.py does) on the release's split, the calibration
split calibrating and the final split scoring, one task per (dataset, task) pair, at the bars, flavors,
points, `min_samples` and confidence of the committed evidence/response-bank-delegation/results.json.
Standard library and `model_routing` only. Exit 0, or 2 with one `error: ...` line, a carriage return or
newline escaped.

  python research/registry_pair_delegation.py [--cache DIR] [--root PATH]
"""

import argparse
import importlib.util
import json
import statistics
import sys
from fractions import Fraction
from pathlib import Path

from model_routing import Registry
from model_routing.delegation_eval import _calibrate, _cell, _router, _summary

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "evidence/response-bank-delegation/results.json"
SEED = "release"
ASSUMPTIONS = ("low", "high")
STRATEGIES = ("decision", "inline", "delegate")
RATIO = 5  # each model's output price over its input price, which `check_ratio` checks


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


RP = _load("research_registry_pair_for_delegation", Path(__file__).resolve().parent / "registry_pair.py")


def check_ratio(registry, ids):
    """Each model's output price is RATIO times its input price, and no model has price tiers."""
    for model in ids.values():
        m = registry.get(model)
        if m.price_tiers or Fraction(str(m.price_out)) != RATIO * Fraction(str(m.price_in)):
            raise ValueError(f"{model}: output price {m.price_out} is not {RATIO} times input price "
                             f"{m.price_in}, or the model has price tiers")


def tokens(outcome, registry):
    """(E, the cost change of rounding E to a whole token in USD, the low row's tokens, the high row's)."""
    price = Fraction(str(registry.get(outcome.model).price_in))
    exact = Fraction(repr(outcome.cost_usd)) * 10 ** 6 / price
    e = round(exact)
    return exact, abs(e - exact) * price / 10 ** 6, (e % RATIO, e // RATIO), (e, 0)


def table_for(rows, registry, assumption):
    """The 13.9 matrix of the rows, each as (correct, input tokens, output tokens, no per-call sizes)."""
    table = {}
    for o in rows:
        _, _, low, high = tokens(o, registry)
        size = low if assumption == "low" else high
        table.setdefault((o.task, o.item), {})[o.model] = (o.correct, size[0], size[1], None)
    return table


def run(calibration, final, registry, config, assumption):
    """The models, the tasks, the 13.9 cells and their summary, every row priced at one end."""
    rows = calibration + final
    table = table_for(rows, registry, assumption)
    models = sorted({o.model for o in rows})
    items = {}
    for part, group in (("cal", calibration), ("held", final)):
        for o in group:
            items.setdefault(o.task, {"cal": set(), "held": set()})[part].add(o.item)
    tasks = sorted(items)
    calibrated = {t: _calibrate(table, models, t, sorted(items[t]["cal"]), sorted(items[t]["held"]))
                  for t in tasks}
    points = config["points"]
    cells, paths, sums = [], {}, ({}, {})
    for bar in config["bars"]:
        routers = {t: _router(registry, t, calibrated[t], bar, config["min_samples"], config["confidence"])
                   for t in tasks}
        for flavor in config["flavors"]:
            for index, point in enumerate(points):
                for parent in models:
                    for t in tasks:
                        cells.append(_cell(table, registry, routers[t], calibrated[t], t, bar, flavor, index,
                                           point, parent, SEED, paths, sums))
    return models, tasks, cells, _summary(cells, [SEED])



def label(point):
    return (f"C {point['context_tokens']:,} " + ("separate" if point["inline_separate_call"] else "folded"))


def report(pair, ids, grades_calibration, grades_final, registry, config):
    check_ratio(registry, ids)
    calibration = RP.outcomes(grades_calibration, "calibration", ids)
    final = RP.outcomes(grades_final, "final", ids)
    rows = calibration + final
    points = config["points"]
    lines = [f"{RP.REPO} at {RP.REVISION[:7]} as delegation evidence (grades-calibration.json calibrates, "
             f"grades-final.json scores): bars " + " ".join(str(b) for b in config["bars"])
             + f", min_samples {config['min_samples']}, confidence {config['confidence']}, the points of {CONFIG}"]
    for i, p in enumerate(points):
        lines.append(f"  point {i}: context {p['context_tokens']:,}, brief {p['brief_tokens']}, result "
                     f"{p['result_tokens']}, carry turns {p['carry_turns']}, inline "
                     + ("in a separate call" if p["inline_separate_call"] else "folded into the next call"))
    for arm in RP.ARMS:
        m = registry.get(ids[arm])
        sizes = [tokens(o, registry)[0] for o in rows if o.model == ids[arm]]
        lines.append(f"  {arm}: {ids[arm]} at {m.price_in} and {m.price_out} USD per million input and output "
                     f"tokens, output {RATIO} times input; median E {float(statistics.median(sizes)):,.1f} "
                     f"input-equivalent tokens a question")
    exact = [tokens(o, registry) for o in rows]
    odd = [x for x in exact if x[0].denominator != 1]
    lines.append(f"  E not a whole token: {len(odd)} of {len(rows):,} row costs; the largest cost change of "
                 f"rounding {float(max(x[1] for x in exact)):.9f} USD")
    lines.append(f"  ends: low prices a row as in = E % {RATIO} and out = E // {RATIO}, high as in = E and out = 0")
    lines.append("  end   parent              flavor          bar  point              decision     cost (USD)  "
                 "delegated  inline  cost (USD)   delegate  cost (USD)  other delegate")
    picks = {}
    for assumption in ASSUMPTIONS:
        models, tasks, cells, summary = run(calibration, final, registry, config, assumption)
        picks[assumption] = {(c["bar"], c["flavor"], c["point"], c["parent"], c["task"]): (c["mode"], c["delegate"])
                             for c in cells}
        for parent in models:
            for flavor in config["flavors"]:
                for bar in config["bars"]:
                    for index, point in enumerate(points):
                        got = {r["strategy"]: r for r in summary
                               if (r["bar"], r["flavor"], r["point"], r["parent"]) == (bar, flavor, index, parent)}
                        group = [c for c in cells
                                 if (c["bar"], c["flavor"], c["point"], c["parent"]) == (bar, flavor, index, parent)]
                        delegated = sum(c["mode"] == "delegate" for c in group)
                        other = sum(c["delegate"] != parent for c in group)
                        d, i, g = got["decision"], got["inline"], got["delegate"]
                        lines.append(f"  {assumption:<5} {parent:<19} {flavor:<15} {bar:<4} {label(point):<18} "
                                     f"{d['success']:.3f}  {d['cost_usd']:>12.6f}  {delegated:>2} of {len(tasks)}"
                                     f"   {i['success']:.3f}  {i['cost_usd']:>11.6f}  {g['success']:.3f}  "
                                     f"{g['cost_usd']:>11.6f}  {other:>2} of {len(tasks)}")
    moved = {}
    for key, pick in picks["low"].items():
        moved.setdefault(key[:4], 0)
        moved[key[:4]] += pick != picks["high"][key]
    lines.append(f"  ends compared: {sum(n > 0 for n in moved.values())} of {len(moved)} (parent, flavor, bar, point) "
                 f"groups have a task whose mode or delegate differs between the ends, at most "
                 f"{max(moved.values())} of {len(tasks)} tasks in one group, at point "
                 + " and ".join(str(i) for i in sorted({k[2] for k, n in moved.items() if n})))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(prog="registry_pair_delegation.py", description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, help="folder for the pinned files (default: the evidence cache)")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        paths = RP.fetch(args.cache if args.cache is not None else RP.default_cache_dir())
        read = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
        with open(args.root / CONFIG, encoding="utf-8") as fh:
            config = json.load(fh)["config"]
        registry = Registry.load(args.root / "model_routing" / "data" / "models.json")
        ids = RP.check_pair(read["pair.json"], registry)
        lines = report(read["pair.json"], ids, read["recordings/grades-calibration.json"],
                       read["recordings/grades-final.json"], registry, config)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ZeroDivisionError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
