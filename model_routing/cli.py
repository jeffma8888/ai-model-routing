"""Command line interface: ``model-routing select|calibrate|report|demo|evaluate|delegate``."""

from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path
from typing import List, Optional

from . import DATA_DIR
from .demo import run_demo
from .monitor import load_records, report
from .priors import Priors
from .registry import Registry
from .router import FLAVORS, NoModelClearsBar, Router
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

    ev = sub.add_parser("evaluate",
                        help="score routing on a held-out split of an outcome matrix")
    ev.add_argument("--outcomes", required=True)
    # default None, not [0.8]: "extend" would append the given bars to a list default
    ev.add_argument("--bar", type=float, nargs="+", action="extend", default=None)
    ev.add_argument("--seeds", type=int, default=10)
    ev.add_argument("--flavor", nargs="+", action="extend", default=None,
                    help="flavors to run, in order (default cost_effective cost_blind)")
    ev.add_argument("--calibration-fraction", type=float, default=0.5)
    ev.add_argument("--min-samples", type=int, default=30)
    ev.add_argument("--confidence", type=float, default=0.95)
    ev.add_argument("--registry", default=str(DATA_DIR / "models.json"))
    ev.add_argument("--json", action="store_true")

    dg = sub.add_parser("delegate",
                        help="do work of one or more calls of a task inline in the parent "
                             "or hand it to a sub-agent")
    dg.add_argument("task")
    dg.add_argument("--parent", required=True, help="the model of the agent doing the work")
    dg.add_argument("--context-tokens", required=True, type=int,
                    help="tokens already in the parent's context")
    dg.add_argument("--brief-tokens", required=True, type=int,
                    help="tokens the parent writes to hand the work off")
    dg.add_argument("--result-tokens", required=True, type=int,
                    help="tokens the parent reads back from the sub-agent")
    dg.add_argument("--carry-turns", type=int, default=0,
                    help="parent calls after the next one that still re-read this work")
    dg.add_argument("--work-calls", type=int, default=1,
                    help="successive calls of the task the work takes (default 1)")
    dg.add_argument("--cached-read-ratio", type=float, default=1.0,
                    help="price of the parent's cached reads of its context in inline "
                         "work, as a fraction of its list input price (default 1.0)")
    dg.add_argument("--fold-inline", action="store_true",
                    help="inline work goes into the parent's next call, not a call of its own")
    dg.add_argument("--flavor", default="cost_effective", help="cost_effective or cost_blind")
    dg.add_argument("--generator", default=None)
    dg.add_argument("--exclude", nargs="+", action="extend", default=[])
    dg.add_argument("--registry", default=str(DATA_DIR / "models.json"))
    dg.add_argument("--tasks", default=str(DATA_DIR / "example_tasks.json"))
    dg.add_argument("--stats", default="stats.json")
    dg.add_argument("--priors", default=str(DATA_DIR / "priors.json"))
    dg.add_argument("--json", action="store_true")
    return parser


def _table(headers: List[str], rows: List[List[object]]) -> str:
    cells = [[str(c) for c in row] for row in [headers] + rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip()
             for row in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def _warn_expired_prices(registry: Registry, today: date) -> None:
    """One stderr line per registry model whose stated price end date has passed (DESIGN 10)."""
    expired = registry.expired_prices(today)
    if not expired:
        return
    sys.stdout.flush()
    for model in expired:
        print(f"warning: list price of {model.id} was stated valid through "
              f"{model.price_valid_until}; check the vendor page and update the registry",
              file=sys.stderr)


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
        _warn_expired_prices(registry, args.today)
        return EXIT_NO_MODEL
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
        _warn_expired_prices(registry, args.today)
        return EXIT_OK
    print(f"task:      {decision.task}")
    print(f"flavor:    {decision.flavor}")
    print(f"primary:   {decision.primary}")
    print(f"fallbacks: {', '.join(decision.fallbacks) or '(none)'}")
    print(f"basis:     {decision.basis}")
    print(f"below_bar: {str(decision.below_bar).lower()}")
    print()
    print(_candidate_table(decision.candidates))
    _warn_expired_prices(registry, args.today)
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
    hand_offs = [s["delegation"] for s in summary.values()]
    print(f"\ninline or sub-agent, a {hand_offs[0]['parent']} parent at "
          f"{hand_offs[0]['context_tokens']:,} context tokens:")
    for flavor, d in zip(summary, hand_offs):
        where = (f"delegate to {d['model']}" if d["mode"] == "delegate"
                 else f"inline on {d['model']}")
        delegate = "-" if d["delegate_cost_usd"] is None else f"{d['delegate_cost_usd']:.6f}"
        print(f"  {flavor + ':':<15} {where} ({d['reason']}), "
              f"inline {d['inline_cost_usd']:.6f} vs delegate {delegate} USD")
    print(f"  hand-off calls: {sum(d['hand_off_calls'] for d in hand_offs)}, "
          f"list-price USD {sum(d['hand_off_cost_usd'] for d in hand_offs):.4f}")
    print(f"log: {Path(args.out) / 'calls.jsonl'}")
    return EXIT_OK


def _cmd_evaluate(args) -> int:
    from .evaluate import evaluate, load_outcomes
    if args.seeds < 1:
        raise ValueError("--seeds must be >= 1")
    registry = Registry.load(args.registry)
    result = evaluate(load_outcomes(args.outcomes, registry), bars=args.bar or [0.8],
                      seeds=range(args.seeds), flavors=args.flavor or FLAVORS,
                      calibration_fraction=args.calibration_fraction,
                      min_samples=args.min_samples, confidence=args.confidence)
    result.pop("cells")
    if args.json:
        print(json.dumps(result, indent=2))
        return EXIT_OK

    def fmt(value):
        return "-" if value is None else f"{value:.3f}"
    blocks = []
    for bar in result["config"]["bars"]:
        for flavor in result["config"]["flavors"]:
            rows = [[r["strategy"], fmt(r["success"]), f"{r['cost_usd']:.4f}",
                     fmt(r["below_bar_rate"]), fmt(r["cleared_rate"]),
                     fmt(r["bar_violation_rate"])]
                    for r in result["summary"] if r["bar"] == bar and r["flavor"] == flavor]
            blocks.append(f"bar {bar}, {flavor}\n" + _table(
                ["strategy", "success", "cost_usd", "below_bar_rate", "cleared_rate",
                 "bar_violation_rate"], rows))
    print("\n\n".join(blocks))
    return EXIT_OK


def _cmd_delegate(args) -> int:
    registry = Registry.load(args.registry)
    tasks = load_tasks(args.tasks)
    stats = Stats.load(args.stats) if Path(args.stats).exists() else Stats()
    priors = Priors.load(args.priors) if Path(args.priors).exists() else None
    for model_id in [args.parent, args.generator, *args.exclude]:
        if model_id is not None:
            registry.get(model_id)
    router = Router(registry, tasks, stats, priors)
    try:
        decision = router.decide_delegation(
            args.task, args.parent, args.flavor, context_tokens=args.context_tokens,
            brief_tokens=args.brief_tokens, result_tokens=args.result_tokens,
            carry_turns=args.carry_turns, work_calls=args.work_calls,
            inline_separate_call=not args.fold_inline,
            cached_read_ratio=args.cached_read_ratio,
            generator_model=args.generator, exclude_models=tuple(args.exclude))
    except NoModelClearsBar as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(_candidate_table(exc.candidates), file=sys.stderr)
        _warn_expired_prices(registry, args.today)
        return EXIT_NO_MODEL
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
        _warn_expired_prices(registry, args.today)
        return EXIT_OK

    def fmt(value, digits):
        return "-" if value is None else f"{value:.{digits}f}"
    print(f"mode:                {decision.mode}")
    print(f"model:               {decision.model}")
    print(f"reason:              {decision.reason}")
    print(f"below_bar:           {str(decision.below_bar).lower()}")
    print(f"inline_cost_usd:     {fmt(decision.inline_cost_usd, 6)}")
    print(f"delegate_cost_usd:   {fmt(decision.delegate_cost_usd, 6)}")
    print(f"parent_quality_lb:   {fmt(decision.parent_quality_lb, 3)}")
    print(f"delegate_quality_lb: {fmt(decision.delegate_quality_lb, 3)}")
    _warn_expired_prices(registry, args.today)
    return EXIT_OK


_COMMANDS = {"select": _cmd_select, "calibrate": _cmd_calibrate, "report": _cmd_report,
             "demo": _cmd_demo, "evaluate": _cmd_evaluate, "delegate": _cmd_delegate}


def main(argv: Optional[List[str]] = None, *, today: Optional[date] = None) -> int:
    """Run the CLI and return its exit code: 0 ok, 2 bad input, 3 no model clears the bar.

    ``today`` dates the price expiry check of ``select`` and ``delegate``; ``None``
    means ``datetime.date.today()``.
    """
    if today is None:
        today = date.today()
    elif not isinstance(today, date):
        raise TypeError(f"today must be a datetime.date, got {type(today).__name__}")
    parser = _build_parser()
    try:
        args = parser.parse_args(argv)
        args.today = today
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
