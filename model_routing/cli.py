"""Command line interface: ``model-routing select|calibrate|report|demo|evaluate|delegate|plan|promote|pairs``."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import stat
import sys
from collections import Counter
from dataclasses import asdict
from datetime import date
from pathlib import Path
from typing import List, Optional

from . import DATA_DIR
from .budget import BudgetExceeded, load_budgets
from .demo import run_demo
from .monitor import (budget_report, load_audits, load_logs, load_records, pair_results, report,
                      shadow_pairs)
from .priors import Priors
from .promotion import pair_outcomes, paired_promotion
from .registry import Registry
from .router import FLAVORS, NoModelClearsBar, Router
from .stats import (Stats, _planned_successes, calibrate_from_results, item_outcomes,
                    items_needed, wilson_lower_bound)
from .tasks import is_slice_name, load_tasks

EXIT_OK = 0
EXIT_BAD_INPUT = 2
EXIT_NO_MODEL = 3
EXIT_BUDGET = 4  # DESIGN 10 v1.599: a BudgetExceeded ended a call of demo --budgets


class _BadInput(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message: str):
        self.print_usage(sys.stderr)
        raise _BadInput(message)


def _seed_count(text: str) -> int:
    """``evaluate --seeds K`` (DESIGN 12.4, v1.266): an integer >= 1, else a usage error."""
    try:
        value = int(text)
    except ValueError:
        value = None
    if value is None or value < 1:
        raise argparse.ArgumentTypeError(f"must be an integer >= 1, got {text!r}")
    return value


def _prompt_token_count(text: str) -> int:
    """``select --prompt-tokens N`` (DESIGN 10, v1.507): an integer >= 0, else a usage error."""
    try:
        value = int(text)
    except ValueError:
        value = None
    if value is None or value < 0:
        raise argparse.ArgumentTypeError(f"must be an integer >= 0, got {text!r}")
    return value


def _slice_name(text: str) -> str:
    """``select --slice S`` (DESIGN 10, v1.511): a non-empty name without '@'."""
    if not is_slice_name(text):
        raise argparse.ArgumentTypeError(f"must be a non-empty name without '@', got {text!r}")
    return text


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
    select.add_argument("--prompt-tokens", type=_prompt_token_count, default=None, metavar="N")
    select.add_argument("--slice", type=_slice_name, default=None, metavar="S")
    select.add_argument("--registry", default=str(DATA_DIR / "models.json"))
    select.add_argument("--tasks", default=str(DATA_DIR / "example_tasks.json"))
    select.add_argument("--stats", default="stats.json")
    select.add_argument("--priors", default=str(DATA_DIR / "priors.json"))
    select.add_argument("--json", action="store_true")

    calibrate = sub.add_parser("calibrate", help="merge labeled results into a stats file")
    calibrate.add_argument("--results", required=True)
    calibrate.add_argument("--stats", required=True)
    calibrate.add_argument("--outcomes", default=None, metavar="FILE",
                           help="append one outcome per row, with the results file's sha256")

    rep = sub.add_parser("report", help="aggregate a calls.jsonl log")
    rep.add_argument("--log", required=True, action="append",
                     help="a monitor log; give --log once per log to read them together")
    rep.add_argument("--by", default="model")
    rep.add_argument("--json", action="store_true")
    rep.add_argument("--audits", default=None, metavar="PATH",
                     help="a JSONL file of {call_id, correct} audits: adds cost per success")
    rep.add_argument("--cache", action="store_true",
                     help="adds each group's cache hit rate, from the records that carry a cached count")
    rep.add_argument("--shadow", action="store_true",
                     help="keeps shadow calls out of the routed columns and adds their calls and spend")

    demo = sub.add_parser("demo", help="run the offline demo with fictional models")
    demo.add_argument("--out", default="model-routing-demo")
    demo.add_argument("--budgets", default=None, metavar="FILE",
                      help="a budgets JSON file: one ledger for every demo call; a refused call "
                           "exits 4")

    ev = sub.add_parser("evaluate",
                        help="score routing on a held-out split of an outcome matrix")
    ev.add_argument("--outcomes", required=True)
    # default None, not [0.8]: "extend" would append the given bars to a list default
    ev.add_argument("--bar", type=float, nargs="+", action="extend", default=None)
    ev.add_argument("--seeds", type=_seed_count, default=10)
    ev.add_argument("--flavor", nargs="+", action="extend", default=None,
                    help="flavors to run, in order (default cost_effective cost_blind)")
    ev.add_argument("--calibration-fraction", type=float, default=0.5)
    ev.add_argument("--min-samples", type=int, default=30)
    ev.add_argument("--confidence", type=float, default=0.95)
    ev.add_argument("--registry", default=str(DATA_DIR / "models.json"))
    ev.add_argument("--slice-by", default=None, metavar="FIELD",
                    help="the outcome-row key that names each row's slice (DESIGN 12.4 v1.514)")
    ev.add_argument("--cost-per-correct", action="store_true",
                    help="add each strategy's held-out cost per correct item (DESIGN 12.4 v1.570)")
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
    dg.add_argument("--output-reread-share", type=float, default=1.0,
                    help="share of each work call's output that later calls re-read, "
                         "from 0 to 1 (default 1.0, the whole output)")
    dg.add_argument("--brief-output-tokens", type=int, default=None,
                    help="output tokens of the call that writes the brief, its reasoning "
                         "included (default: the --brief-tokens value)")
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

    plan = sub.add_parser("plan", help="labelled items per model before a success rate "
                                       "clears a bar")
    plan.add_argument("--success", required=True, type=float,
                      help="the success rate you expect the model to have on the task")
    plan.add_argument("--bar", required=True, type=float)
    plan.add_argument("--confidence", type=float, default=0.95)
    plan.add_argument("--max-items", type=int, default=10_000)

    pr = sub.add_parser("promote", help="whether a challenger route should replace a task's "
                                        "current route, on the items both were graded on")
    pr.add_argument("--task", required=True)
    pr.add_argument("--challenger", required=True, metavar="ROUTE")
    pr.add_argument("--margin", required=True, type=float, metavar="M",
                    help="the loss in success rate a cheaper challenger may have, declared first")
    pr.add_argument("--outcomes", required=True, metavar="FILE",
                    help="the outcomes file calibrate --outcomes appends to")
    pr.add_argument("--slice", type=_slice_name, default=None, metavar="S")
    pr.add_argument("--flavor", default="cost_effective", help="cost_effective or cost_blind")
    pr.add_argument("--dataset-sha256", default=None, metavar="HEX",
                    help="pair on the outcomes of this labeled file only")
    pr.add_argument("--alpha", type=float, default=0.05, metavar="A")
    pr.add_argument("--registry", default=str(DATA_DIR / "models.json"))
    pr.add_argument("--tasks", default=str(DATA_DIR / "example_tasks.json"))
    pr.add_argument("--stats", default="stats.json")
    pr.add_argument("--priors", default=str(DATA_DIR / "priors.json"))
    pr.add_argument("--json", action="store_true")

    pa = sub.add_parser("pairs", help="write the pair file of a monitor log's shadow calls")
    pa.add_argument("--log", required=True, metavar="PATH", action="append",
                    help="a monitor log; give --log once per log to read them together")
    pa.add_argument("--out", required=True, metavar="FILE",
                    help="the pair file, written whole: one JSON object per pair")
    pa.add_argument("--checked", action="store_true",
                    help="every call of the log ran with an acceptance check: label by it")
    pa.add_argument("--audits", default=None, metavar="PATH",
                    help="a JSONL file of {call_id, correct} audits: label by them")
    pa.add_argument("--results", default=None, metavar="RESULTS",
                    help="also write the pairs' labeled results rows, each with its cost_usd")
    pa.add_argument("--routes", nargs=2, default=None, metavar=("ROUTED", "SHADOW"),
                    help="with --results: write the rows of this route pair's pairs alone")
    return parser


def _table(headers: List[str], rows: List[List[object]]) -> str:
    cells = [[str(c) for c in row] for row in [headers] + rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(headers))]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths)).rstrip()
             for row in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return "\n".join(lines)


def _warn_expired_prices(registry: Registry, today: date, used) -> None:
    """One stderr line per model of ``used`` whose stated price end date has passed, in registry
    file order (DESIGN 10; from v1.411 only the models whose price the run can use)."""
    used = set(used)
    expired = [model for model in registry.expired_prices(today) if model.id in used]
    if not expired:
        return
    sys.stdout.flush()
    for model in expired:
        print(f"warning: list price of {model.id} was stated valid through "
              f"{model.price_valid_until}; check the vendor page and update the registry",
              file=sys.stderr)


def _eligible(candidates) -> set:
    """The models 5.2 rules 1 to 5 leave eligible: the only ones whose price a choice reads."""
    return {c.model_id for c in candidates if c.eligible}


PER_ITEM_LINE = ("list_cost and routing_cost are per item; items is how many items one call of "
                 "the route handles")


def _candidate_table(candidates, registry=None) -> str:
    """The candidate table; with an ``items`` column and the per-item line when some route of
    ``registry`` handles more than one item a call (DESIGN 10 v1.573), and a ``pricing_basis``
    column when some candidate is self-hosted (v1.584)."""
    items = {} if registry is None else {
        c.model_id: registry.get(c.model_id).items_per_call
        for c in candidates if c.model_id in registry}
    per_item = any(k > 1 for k in items.values())
    hosted = any(c.pricing_basis == "self_hosted" for c in candidates)
    rows = [[c.model_id, c.family, f"{c.successes}/{c.trials}", f"{c.quality_lb:.3f}"]
            + ([items.get(c.model_id, 1)] if per_item else [])
            + ([c.pricing_basis or "-"] if hosted else [])
            + [f"{c.list_cost:.6f}", f"{c.routing_cost:.6f}", c.reason] for c in candidates]
    table = _table(["model", "family", "measured", "quality_lb"]
                   + (["items"] if per_item else []) + (["pricing_basis"] if hosted else [])
                   + ["list_cost", "routing_cost", "reason"], rows)
    return table + "\n" + PER_ITEM_LINE if per_item else table


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
                                 exclude_models=tuple(args.exclude),
                                 prompt_tokens=args.prompt_tokens, slice=args.slice)
    except NoModelClearsBar as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(_candidate_table(exc.candidates, registry), file=sys.stderr)
        _warn_expired_prices(registry, args.today, _eligible(exc.candidates))
        return EXIT_NO_MODEL
    used = _eligible(decision.candidates)
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
        _warn_expired_prices(registry, args.today, used)
        return EXIT_OK
    print(f"task:      {decision.task}")
    if decision.slice is not None:
        print(f"slice:     {decision.slice}")
    print(f"flavor:    {decision.flavor}")
    print(f"primary:   {decision.primary}")
    marked = [m + " (below bar)" if m in decision.below_bar_fallbacks else m
              for m in decision.fallbacks]
    print(f"fallbacks: {', '.join(marked) or '(none)'}")
    print(f"basis:     {decision.basis}")
    print(f"below_bar: {str(decision.below_bar).lower()}")
    if decision.failure_policy != "none":  # DESIGN 10 v1.567
        value = decision.expected_cost_per_success_usd
        shown = "n/a" if value is None else f"${value:.6f}"
        print(f"policy:    {decision.failure_policy}, expected cost per success {shown} "
              "(an estimate assuming independent retries)")
        if decision.pick_reason is not None:
            print(f"pick:      {decision.pick_reason}")
    print()
    print(_candidate_table(decision.candidates, registry))
    _warn_expired_prices(registry, args.today, used)
    return EXIT_OK


def _cmd_calibrate(args) -> int:
    rows = load_records(args.results)
    new = calibrate_from_results(rows)
    stats_path = Path(args.stats)
    records = None
    if args.outcomes is not None:  # DESIGN 10 v1.602: every check before any write
        outcomes_path = Path(args.outcomes)
        if outcomes_path.resolve() in (Path(args.results).resolve(), stats_path.resolve()):
            raise _BadInput(f"--outcomes {args.outcomes} names the results or the stats file")
        digest = hashlib.sha256(Path(args.results).read_bytes()).hexdigest()
        records = item_outcomes(rows, dataset_sha256=digest)
    existing = Stats.load(stats_path) if stats_path.exists() else Stats()
    merged = existing.merge(new)
    merged.save(stats_path)
    table = [[task, model_id, s, t, f"{wilson_lower_bound(s, t):.4f}"]
             for (task, model_id), (s, t) in merged.items()]
    print(_table(["task", "model", "successes", "trials", "lower_bound_95"], table))
    print(f"\nwrote {stats_path}")
    if records is not None:
        _append_outcomes(outcomes_path, records)
        print(f"appended {len(records)} outcomes to {outcomes_path}, dataset_sha256 {digest}")
    return EXIT_OK


def _append_outcomes(path: Path, records) -> None:
    """Append one ``json.dumps`` per record, a newline first after a last line without one."""
    lead = ""
    if path.exists() and path.stat().st_size:
        with path.open("rb") as handle:
            handle.seek(-1, 2)
            if handle.read(1) != b"\n":
                lead = "\n"
    with path.open("a", encoding="utf-8") as handle:
        handle.write(lead + "".join(json.dumps(record) + "\n" for record in records))


def _cmd_report(args) -> int:
    audits = None if args.audits is None else load_audits(args.audits)
    rows = report(load_logs(args.log), by=args.by, audits=audits, cache=args.cache,
                  shadow=args.shadow)
    if args.json:
        print(json.dumps(rows, indent=2))
        return EXIT_OK

    def fmt(value):
        return "-" if value is None else f"{value:.1f}"

    def na(value, places):
        return "n/a" if value is None else f"{value:.{places}f}"
    # DESIGN 10 v1.569: four columns after p95_ms only with --audits
    audited = audits is not None
    # DESIGN 10 v1.203: the below_bar_calls column only when some row counts one
    under = any(r["below_bar_calls"] > 0 for r in rows)
    table = [[r["group"], r["calls"], r["attempts"], r["errors"], r["invalid"],
              r["fallback_calls"], f"{r['fallback_rate']:.3f}"]
             + ([r["below_bar_calls"]] if under else [])
             + [f"{r['cost_usd']:.6f}", f"{r['routing_cost_usd']:.6f}",
                fmt(r["p50_latency_ms"]), fmt(r["p95_latency_ms"])]
             + ([r["audited_calls"], r["correct_calls"], na(r["cost_per_success_usd"], 6),
                 na(r["successes_per_100k_tokens"], 3)] if audited else [])
             # DESIGN 10 v1.590: three columns after those only with --cache
             + ([r["cached_input_tokens"], r["cache_counted_input_tokens"],
                 na(r["cache_hit_rate"], 3)] if args.cache else [])
             # DESIGN 10 v1.611: three columns after those only with --shadow
             + ([r["shadow_calls"], r["shadow_failed_calls"], f"{r['shadow_cost_usd']:.6f}"]
                if args.shadow else []) for r in rows]
    print(_table([args.by, "calls", "attempts", "errors", "invalid", "fallback_calls",
                  "fallback_rate"] + (["below_bar_calls"] if under else [])
                 + ["cost_usd", "routing_cost_usd", "p50_ms", "p95_ms"]
                 + (["audited_calls", "correct_calls", "cost_per_success_usd",
                     "successes_per_100k_tokens"] if audited else [])
                 + (["cached_input_tokens", "cache_counted_input_tokens", "cache_hit_rate"]
                    if args.cache else [])
                 + (["shadow_calls", "shadow_failed_calls", "shadow_cost_usd"]
                    if args.shadow else []), table))
    return EXIT_OK


def _cmd_demo(args) -> int:
    # DESIGN 10 v1.599: the file is read before the demo writes anything
    budgets = None if args.budgets is None else load_budgets(args.budgets)
    try:  # without the option, v1.598's call
        summary = run_demo(args.out) if budgets is None else run_demo(args.out, budgets=budgets)
    except BudgetExceeded as exc:  # the message names the budget, on one line
        print(f"error: {exc}", file=sys.stderr)
        return EXIT_BUDGET
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
    if budgets is not None:  # DESIGN 10 v1.599: each budget's spend per window, from the log
        rows = budget_report(load_records(Path(args.out) / "calls.jsonl"), budgets)
        print()
        print("budgets:")
        print(_table(["budget", "window", "mode", "limit_usd", "spent_usd", "budget_used_pct",
                      "warn_records", "refused_records"],
                     [[r["budget"], "total" if r["window"] is None else r["window"], r["mode"],
                       f"{r['limit_usd']:.6f}", f"{r['spent_usd']:.6f}",
                       f"{r['budget_used_pct']:.1f}", r["warn_records"], r["refused_records"]]
                      for r in rows]))
    print(f"log: {Path(args.out) / 'calls.jsonl'}")
    return EXIT_OK


def _cmd_evaluate(args) -> int:
    from .evaluate import _read_rows, evaluate, outcomes_from_rows
    registry = Registry.load(args.registry)
    matrix_rows = _read_rows(args.outcomes)
    outcomes = outcomes_from_rows(matrix_rows, registry, slice_by=args.slice_by)
    # DESIGN 10 and 12.4 v1.411: a valid row without cost_usd was priced from the registry
    token_priced = {row["model"] for row in matrix_rows if "cost_usd" not in row}
    result = evaluate(outcomes, bars=args.bar or [0.8],
                      seeds=range(args.seeds), flavors=args.flavor or FLAVORS,
                      calibration_fraction=args.calibration_fraction,
                      min_samples=args.min_samples, confidence=args.confidence,
                      cost_per_correct=args.cost_per_correct)
    result.pop("cells")
    if args.json:
        print(json.dumps(result, indent=2))
        _warn_expired_prices(registry, args.today, token_priced)
        return EXIT_OK

    def fmt(value):
        return "-" if value is None else f"{value:.3f}"
    # v1.538: an escalation_share column only when the outcomes hold a cascade row
    escalation = ["escalation_share"] if "escalation_share" in result["summary"][0] else []
    # v1.570: a cost_per_correct_usd column last, to 6 decimals, only with --cost-per-correct
    per_correct = ["cost_per_correct_usd"] if args.cost_per_correct else []

    def fmt6(value):
        return "-" if value is None else f"{value:.6f}"
    blocks = []
    for bar in result["config"]["bars"]:
        for flavor in result["config"]["flavors"]:
            rows = [[r["strategy"], fmt(r["success"]), f"{r['cost_usd']:.4f}",
                     fmt(r["below_bar_rate"]), fmt(r["cleared_rate"]),
                     fmt(r["bar_violation_rate"])] + [fmt(r[k]) for k in escalation]
                    + [fmt6(r[k]) for k in per_correct]
                    for r in result["summary"] if r["bar"] == bar and r["flavor"] == flavor]
            blocks.append(f"bar {bar}, {flavor}\n" + _table(
                ["strategy", "success", "cost_usd", "below_bar_rate", "cleared_rate",
                 "bar_violation_rate"] + escalation + per_correct, rows))
            if "slice_summary" in result:
                # v1.514: the (bar, flavor)'s slice_summary rows, slice_miss_rate last
                rows = [[r["strategy"], fmt(r["success"]), f"{r['cost_usd']:.4f}",
                         fmt(r["below_bar_rate"]), fmt(r["cleared_rate"]),
                         fmt(r["bar_violation_rate"]), fmt(r["slice_miss_rate"])]
                        for r in result["slice_summary"]
                        if r["bar"] == bar and r["flavor"] == flavor]
                blocks.append(f"bar {bar}, {flavor}, slices\n" + _table(
                    ["strategy", "success", "cost_usd", "below_bar_rate", "cleared_rate",
                     "bar_violation_rate", "slice_miss_rate"], rows))
    print("\n\n".join(blocks))
    _warn_expired_prices(registry, args.today, token_priced)
    return EXIT_OK


def _cmd_delegate(args) -> int:
    registry = Registry.load(args.registry)
    tasks = load_tasks(args.tasks)
    stats = Stats.load(args.stats) if Path(args.stats).exists() else Stats()
    priors = Priors.load(args.priors) if Path(args.priors).exists() else None
    for model_id in [args.parent, args.generator, *args.exclude]:
        if model_id is not None:
            registry.get(model_id)
    parent = registry.get(args.parent).id
    router = Router(registry, tasks, stats, priors)
    try:
        decision = router.decide_delegation(
            args.task, args.parent, args.flavor, context_tokens=args.context_tokens,
            brief_tokens=args.brief_tokens, result_tokens=args.result_tokens,
            carry_turns=args.carry_turns, work_calls=args.work_calls,
            inline_separate_call=not args.fold_inline,
            cached_read_ratio=args.cached_read_ratio,
            output_reread_share=args.output_reread_share,
            brief_output_tokens=args.brief_output_tokens,
            generator_model=args.generator, exclude_models=tuple(args.exclude))
    except NoModelClearsBar as exc:
        print(f"error: {exc}", file=sys.stderr)
        print(_candidate_table(exc.candidates), file=sys.stderr)
        _warn_expired_prices(registry, args.today, {parent} | _eligible(exc.candidates))
        return EXIT_NO_MODEL
    # DESIGN 10 v1.411: the parent prices the inline path; with no route no delegate was priced
    route = decision.route
    used = {parent} | (_eligible(route.candidates) if route is not None else set())
    if args.json:
        print(json.dumps(decision.to_dict(), indent=2))
        _warn_expired_prices(registry, args.today, used)
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
    _warn_expired_prices(registry, args.today, used)
    return EXIT_OK


def _cmd_plan(args) -> int:
    n = items_needed(args.success, args.bar, args.confidence, args.max_items)
    print(f"success:     {args.success}")
    print(f"bar:         {args.bar}")
    print(f"confidence:  {args.confidence}")
    if n is None:
        print(f"items:       none up to --max-items {args.max_items}")
        return EXIT_NO_MODEL
    k = _planned_successes(args.success, n)
    print(f"items:       {n}")
    print(f"successes:   {k}")
    print(f"lower_bound: {wilson_lower_bound(k, n, args.confidence):.6f}")
    return EXIT_OK


def _cmd_promote(args) -> int:
    """DESIGN 10 v1.603: advisory, it writes no file; every check in the spec's order."""
    paired_promotion({}, {}, margin=args.margin, alpha=args.alpha)  # checks M and A first
    registry = Registry.load(args.registry)
    tasks = load_tasks(args.tasks)
    stats = Stats.load(args.stats) if Path(args.stats).exists() else Stats()
    priors = Priors.load(args.priors) if Path(args.priors).exists() else None
    if args.task not in tasks:
        raise _BadInput(f"unknown task: {args.task!r}")
    registry.get(args.challenger)
    records = load_records(args.outcomes)
    where = f"task {args.task}" + ("" if args.slice is None else f" slice {args.slice}")
    try:
        decision = Router(registry, tasks, stats, priors).select(
            args.task, flavor=args.flavor, slice=args.slice)
        candidates = decision.candidates
    except NoModelClearsBar as exc:
        decision, candidates = None, exc.candidates
    challenger = next(c for c in candidates if c.model_id == args.challenger)
    if decision is None or not challenger.passes:
        print(f"error: challenger {args.challenger} is not admitted on {where}: "
              f"{challenger.reason}", file=sys.stderr)
        return EXIT_NO_MODEL
    current = next(c for c in candidates if c.model_id == decision.primary)
    mine, theirs, digest = pair_outcomes(records, task=args.task, current=current.model_id,
                                         challenger=challenger.model_id, slice=args.slice,
                                         dataset_sha256=args.dataset_sha256)
    task = tasks[args.task]
    min_pairs = task.slices.get(args.slice, {}).get("min_samples", task.min_samples) \
        if args.slice is not None else task.min_samples
    check = paired_promotion(mine, theirs, margin=args.margin,
                             cheaper=challenger.list_cost < current.list_cost, alpha=args.alpha,
                             min_pairs=min_pairs)
    data = {"task": args.task, "slice": args.slice, "flavor": args.flavor,
            "current": current.model_id, "challenger": challenger.model_id,
            "dataset_sha256": digest, "current_list_cost": current.list_cost,
            "challenger_list_cost": challenger.list_cost, **asdict(check)}
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        six = {"current_list_cost", "challenger_list_cost", "current_rate", "challenger_rate",
               "difference", "p_value", "lower_bound"}
        for key, value in data.items():
            if key == "slice" and value is None:
                continue
            if value is None:
                shown = "n/a"
            elif key in six:
                shown = f"{value:.6f}"
            elif isinstance(value, bool):
                shown = str(value).lower()
            else:
                shown = str(value)
            print(f"{key + ':':<22}{shown}")
    _warn_expired_prices(registry, args.today, _eligible(candidates))
    return EXIT_OK


def _cmd_pairs(args) -> int:
    """DESIGN 10 v1.612 and v1.615: every check before FILE or RESULTS is written, then each
    written whole."""
    if args.checked and args.audits is not None:
        raise _BadInput("pass --checked or --audits, not both: their labels could disagree")
    routes = None if args.routes is None else tuple(args.routes)
    if routes is not None:
        if args.results is None:
            raise _BadInput("--routes needs --results: it picks the route pair of the rows "
                            "--results writes")
        if not all(routes) or routes[0] == routes[1]:
            raise _BadInput(f"--routes needs two different non-empty routes, got {routes[0]!r} "
                            f"{routes[1]!r}")
    out = Path(args.out)
    inputs = [Path(log) for log in args.log] + ([] if args.audits is None else [Path(args.audits)])
    if out.resolve() in [path.resolve() for path in inputs]:
        raise _BadInput(f"--out {args.out} names the log or the audits file")
    results = None if args.results is None else Path(args.results)
    if results is not None and results.resolve() in [path.resolve() for path in inputs + [out]]:
        raise _BadInput(f"--results {args.results} names the log, the audits file or --out")
    records = load_logs(args.log)  # DESIGN 10 v1.620: --log once per log
    audits = None if args.audits is None else load_audits(args.audits)
    pairs = shadow_pairs(records, checked=args.checked, audits=audits)
    files = [(out, "".join(json.dumps(pair) + "\n" for pair in pairs))]
    if results is not None:
        rows = pair_results(pairs, records=records, routes=routes)
        files.append((results, "".join(json.dumps(row) + "\n" for row in rows)))
    _write_whole(files)
    labelled = [pair for pair in pairs
                if pair["routed_correct"] is not None and pair["shadow_correct"] is not None]
    print(f"wrote {len(pairs)} pairs to {out}: {len(labelled)} with both sides labelled")
    if results is None:
        return EXIT_OK
    if routes is None:
        print(f"wrote {len(rows)} results rows to {results}")
        return EXIT_OK
    print(f"wrote {len(rows)} results rows to {results}: routed {routes[0]}, shadow {routes[1]}")
    others = Counter((pair["routed_route"], pair["shadow_route"]) for pair in labelled
                     if (pair["routed_route"], pair["shadow_route"]) != routes)
    print(f"labelled pairs of other route pairs left out: {sum(others.values())}")
    for (routed, shadow), count in sorted(others.items()):
        print(f"  routed {routed}, shadow {shadow}: {count}")
    return EXIT_OK


def _write_whole(files) -> None:
    """Open each ``(path, text)``'s path without changing it, a missing file created empty, then
    replace each whole with its text (DESIGN 10 v1.615): a path that cannot be opened leaves
    every file as it was, removing a file this call created, a dangling symlink's target and
    never the link (review iter-466 should-fix 3). Only a regular file is truncated, so a device
    such as ``/dev/null`` serves as v1.612's ``open("w")`` let it (should-fix 4)."""
    handles, created = [], []
    try:
        for path, _ in files:
            target = None if path.exists() else path.resolve()
            handles.append(path.open("a", encoding="utf-8", newline=""))
            if target is not None:
                created.append(target)
    except OSError:
        for handle in handles:
            handle.close()
        for target in created:
            target.unlink()
        raise
    try:
        for handle, (_, text) in zip(handles, files):
            if stat.S_ISREG(os.fstat(handle.fileno()).st_mode):
                handle.truncate(0)
            handle.write(text)
    finally:  # review iter-466 nit 1: every handle closed, a write error too
        for handle in handles:
            handle.close()


_COMMANDS = {"select": _cmd_select, "calibrate": _cmd_calibrate, "report": _cmd_report,
             "demo": _cmd_demo, "evaluate": _cmd_evaluate, "delegate": _cmd_delegate,
             "plan": _cmd_plan, "promote": _cmd_promote, "pairs": _cmd_pairs}


def main(argv: Optional[List[str]] = None, *, today: Optional[date] = None) -> int:
    """Run the CLI and return its exit code: 0 ok, 2 bad input, 3 no model clears the bar (or,
    from v1.603, ``promote``'s challenger is not admitted), 4 a budget refused a call
    (``demo --budgets``, v1.599).

    ``today`` dates the price expiry check of ``select``, ``delegate`` and, from v1.411,
    ``evaluate``; ``None`` means ``datetime.date.today()``.
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
