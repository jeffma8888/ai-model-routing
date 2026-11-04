"""Command line interface: ``model-routing select|calibrate|report|demo``."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import List, Optional

from . import DATA_DIR
from .demo import run_demo
from .monitor import load_records, report
from .priors import Priors
from .registry import Registry
from .router import NoModelClearsBar, Router
from .stats import Stats, calibrate_from_results, wilson_lower_bound
from .tasks import load_tasks

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_NO_MODEL = 3


class _BadInput(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        self.print_usage(sys.stderr)
        raise _BadInput(message)


def _build_parser() -> argparse.ArgumentParser:
    parser = _Parser(prog="model-routing",
                     description="Route each repeated kind of model call to the cheapest "
                                 "model that clears a measured bar, or the best one.")
    sub = parser.add_subparsers(dest="command", parser_class=_Parser)
    sub.required = True

    select = sub.add_parser("select", help="choose a primary model and fallbacks for a task")
    select.add_argument("task")
    select.add_argument("--flavor", default="cost_effective",
                        help="cost_effective or cost_blind")
    select.add_argument("--generator", default=None)
    select.add_argument("--exclude", nargs="+", action="extend", default=[])
    select.add_argument("--registry", default=str(DATA_DIR / "models.json"))
    select.add_argument("--tasks", default=str(DATA_DIR / "example_tasks.json"))
    select.add_argument("--stats", default="stats.json")
    select.add_argument("--priors", default=str(DATA_DIR / "priors.json"))
    select.add_argument("--json", action="store_true")

    calibrate = sub.add_parser("calibrate", help="merge labeled results into a stats file")
    calibrate.add_argument("--results", required=True)
    calibrate.add_argument("--stats", required=True)

    rep = sub.add_parser("report", help="aggregate a calls.jsonl log")
    rep.add_argument("--log", required=True)
    rep.add_argument("--by", default="model")
    rep.add_argument("--json", action="store_true")

    demo = sub.add_parser("demo", help="run the offline demo with fictional models")
    demo.add_argument("--out", default="model-routing-demo")
    return parser


def _table(headers: List[str], rows: List[List[object]]) -> str:
    cells = [[str(c) for c in row] for row in [headers] + rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip()
             for row in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def _candidate_table(candidates) -> str:
    rows = [[c.model_id, c.family, f"{c.successes}/{c.trials}", f"{c.quality_lb:.3f}",
             f"{c.list_cost:.6f}", f"{c.routing_cost:.6f}", c.reason] for c in candidates]
    return _table(["model", "family", "measured", "quality_lb", "list_cost",
                   "routing_cost", "reason"], rows)


def _cmd_select(args) -> int:
    registry = Registry.load(args.registry)
    tasks = load_tasks(args.tasks)
    stats = Stats.load(args.stats) if Path(args.stats).exists() else Stats()
    priors = Priors.load(args.priors) if Path(args.priors).exists() else None
    for model_id in [args.generator, *args.exclude]:
        if model_id is not None:
            registry.get(model_id)
    router = Router(registry, tasks, stats, priors)
    try:
        decision = router.select(args.task, flavor=args.flavor,
                                 generator_model=args.generator,
                                 exclude_models=tuple(args.exclude))
    except NoModelClearsBar as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(_candidate_table(exc.candidates), file=sys.stderr)
        return EXIT_NO_MODEL
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
        return EXIT_OK
    print(f"task:      {decision.task}")
    print(f"flavor:    {decision.flavor}")
    print(f"primary:   {decision.primary}")
    print(f"fallbacks: {', '.join(decision.fallbacks) or '(none)'}")
    print(f"basis:     {decision.basis}")
    print(f"below_bar: {str(decision.below_bar).lower()}")
    print()
    print(_candidate_table(decision.candidates))
    return EXIT_OK


def _cmd_calibrate(args) -> int:
    new = calibrate_from_results(load_records(args.results))
    stats_path = Path(args.stats)
    existing = Stats.load(stats_path) if stats_path.exists() else Stats()
    merged = existing.merge(new)
    merged.save(stats_path)
    table = [[task, model_id, s, t, f"{wilson_lower_bound(s, t):.4f}"]
             for (task, model_id), (s, t) in merged.items()]
    print(_table(["task", "model", "successes", "trials", "lower_bound_95"], table))
    print(f"\nwrote {stats_path}")
    return EXIT_OK


def _cmd_report(args) -> int:
    rows = report(load_records(args.log), by=args.by)
    if args.json:
        print(json.dumps(rows, indent=2))
        return EXIT_OK

    def fmt(value):
        return "-" if value is None else f"{value:.1f}"
    table = [[r["group"], r["calls"], r["attempts"], r["errors"], r["invalid"],
              r["fallback_calls"], f"{r['fallback_rate']:.3f}", f"{r['cost_usd']:.6f}",
              f"{r['routing_cost_usd']:.6f}", fmt(r["p50_latency_ms"]),
              fmt(r["p95_latency_ms"])] for r in rows]
    print(_table([args.by, "calls", "attempts", "errors", "invalid", "fallback_calls",
                  "fallback_rate", "cost_usd", "routing_cost_usd", "p50_ms", "p95_ms"],
                 table))
    return EXIT_OK


def _cmd_demo(args) -> int:
    summary = run_demo(args.out)
    print("model-routing demo (fictional demo/ models, simulated outages)")
    for flavor, s in summary.items():
        print()
        print(f"{flavor}:")
        print(f"  primary:        {s['primary']}")
        print(f"  fallbacks:      {', '.join(s['fallbacks']) or '(none)'}")
        print(f"  calls:          {s['calls']}")
        print(f"  fallback calls: {s['fallback_calls']}")
        print(f"  list-price USD: {s['cost_usd']:.4f}")
    ce, cb = summary["cost_effective"]["cost_usd"], summary["cost_blind"]["cost_usd"]
    if cb > 0:
        print(f"\ncost_effective spent {ce / cb:.0%} of what cost_blind spent")
    print(f"log: {Path(args.out) / 'calls.jsonl'}")
    return EXIT_OK


_COMMANDS = {"select": _cmd_select, "calibrate": _cmd_calibrate,
             "report": _cmd_report, "demo": _cmd_demo}


def main(argv: Optional[List[str]] = None) -> int:
    """Run the CLI and return its exit code: 0 ok, 2 bad input, 3 no model clears the bar."""
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        return _COMMANDS[args.command](args)
    except _BadInput as exc:
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BAD_INPUT
    except (OSError, ValueError, KeyError, TypeError) as exc:
        message = exc.args[0] if isinstance(exc, KeyError) and exc.args else exc
        print(f"error: {message}", file=sys.stderr)
        return EXIT_BAD_INPUT


if __name__ == "__main__":
    sys.exit(main())
