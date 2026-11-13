"""When neither path clears the bar: DESIGN 13.5 row 7 on the committed delegation runs.

Usage:
  python research/no_path_clears.py --autobench MATRIX.jsonl --autobench-registry POOL.json \
      --tau2 CALLS.jsonl --tau2-pooled CALLS_ALL.jsonl \
      --llmrouterbench LRB_MATRIX.jsonl --response-bank BANK_MATRIX.jsonl

Reruns the five committed delegation runs in process, keeping the cells that their results
files drop (evidence/delegation/results.json, evidence/tau2-bench-delegation/results.json and
pooled.json, evidence/llmrouterbench-delegation/results.json and
evidence/response-bank-delegation/results.json; the last two on the rows their scripts'
`select_rows` keeps, each run's config, tasks and summary checked against its committed file),
and prints, per run and flavor, how many cells 13.5 row 7 (`none_clear`) decides
and, on those cells, the held-out success and cost of its choice beside always inline, always
delegating and taking the path whose forecast cost is lower. The forecast costs are not kept
in a cell, so each row 7 cell's decision is rebuilt from its calibration half as DESIGN 13.9
states it, and the rebuilt mode, model and reason must equal the cell's. Standard library and
the model_routing package. Read by research/no-path-clears.md.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

from model_routing import Registry, Router, Stats, Task, evaluate_delegation, split_items

_ROOT = Path(__file__).resolve().parents[1]
TAU2_REGISTRY = _ROOT / "evidence" / "tau2-bench-delegation" / "registry.json"
# the runs read on the rows their script's select_rows keeps: (option, label, folder, module name)
SELECTED = (("llmrouterbench", "LLMRouterBench (13.13 results.json)", "llmrouterbench-delegation", "_r30_lrb"),
            ("response_bank", "LLM Routing Response Bank (13.14 results.json)", "response-bank-delegation",
             "_r30_rb"))


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_rows(path: str) -> list:
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def _up(x: int, y: int) -> int:
    return -(-x // y)


def _calibration(rows, task, seed, fraction=0.5):
    """The 13.9 calibration half of one task and seed: its stats, S_in, S_out and (per-call) K_dec."""
    by_item = {}
    for r in rows:
        if r["task"] == task:
            by_item.setdefault(r["item"], {})[r["model"]] = r
    cal, _ = split_items(list(by_item), seed, fraction)
    models = sorted({m for v in by_item.values() for m in v})
    per_call = "call_input_tokens" in next(iter(by_item.values()))[models[0]]
    stats = Stats()
    if per_call:
        def calls(r):
            return len(r["call_input_tokens"]), sum(r["call_input_tokens"]), sum(r["call_output_tokens"])
        for m in models:
            got = [calls(by_item[i][m]) for i in cal]
            k_c = sum(g[0] for g in got)
            stats.add(task, m, sum(bool(by_item[i][m]["correct"]) for i in cal), len(cal),
                      input_tokens=len(cal) * _up(sum(g[1] for g in got), k_c),
                      output_tokens=len(cal) * _up(sum(g[2] for g in got), k_c))
        got = [calls(by_item[i][m]) for i in cal for m in models]
        return stats, (statistics.median_low([_up(a, k) for k, a, _ in got]),
                       statistics.median_low([_up(o, k) for k, _, o in got]),
                       statistics.median_low([k for k, _, _ in got]))
    for m in models:
        stats.add(task, m, sum(bool(by_item[i][m]["correct"]) for i in cal), len(cal),
                  input_tokens=sum(by_item[i][m]["input_tokens"] for i in cal),
                  output_tokens=sum(by_item[i][m]["output_tokens"] for i in cal))
    return stats, (statistics.median_low([by_item[i][m]["input_tokens"] for i in cal for m in models]),
                   statistics.median_low([by_item[i][m]["output_tokens"] for i in cal for m in models]),
                   None)


def rebuild(rows, registry, result, cell, cache):
    """The cell's DelegationDecision, rebuilt from its calibration half (DESIGN 13.9)."""
    key = (cell["task"], cell["seed"])
    if key not in cache:
        cache[key] = _calibration(rows, *key, result["config"]["calibration_fraction"])
    stats, (s_in, s_out, k) = cache[key]
    cfg = result["config"]
    task = Task(name=cell["task"], bar=cell["bar"], min_samples=cfg["min_samples"],
                confidence=cfg["confidence"], independent_of_generator=False,
                expected_input_tokens=s_in, expected_output_tokens=s_out,
                on_no_model="best_available", max_fallbacks=0)
    point = dict(cfg["points"][cell["point"]])
    if k is not None:
        point["work_calls"] = k
    decision = Router(registry, {cell["task"]: task}, stats).decide_delegation(
        cell["task"], cell["parent"], cell["flavor"], **point)
    assert (decision.mode, decision.model, decision.reason) == (cell["mode"], cell["model"], cell["reason"])
    return decision


def rerun_selected(path, folder, name):
    """The 13.13 or 13.14 run in process: (kept rows, registry, result with its cells).

    Reads the matrix at ``path``, keeps the rows the folder's ``select_rows`` keeps for the
    models of its committed registry and runs 13.9 at that script's bars, base points and seeds.
    Raises ValueError unless the run's config, tasks and summary are the committed file's, and
    passes on the ValueError of a row that ``select_rows`` refuses; main reports either as an
    `error:` line on stderr, exit 1, with nothing on stdout.
    """
    script = _load(_ROOT / "evidence" / folder / "results.py", name)
    registry = Registry.load(_ROOT / "evidence" / folder / "registry.json")
    rows, _dropped = script.select_rows(read_rows(path), [m.id for m in registry.models])
    result = evaluate_delegation(rows, registry, bars=list(script.BARS), points=script.points(),
                                 seeds=range(script.SEEDS))
    committed = json.loads((_ROOT / "evidence" / folder / "results.json").read_text(encoding="utf-8"))
    if {key: result[key] for key in script.KEYS} != committed:
        raise ValueError(f"the rerun is not evidence/{folder}/results.json")
    return rows, registry, result


def report(label, rows, registry, result) -> list:
    """The printed lines for one run: per flavor, the row 7 share and what each path gives on those cells."""
    cells = result["cells"]
    lines = [f"{label}: {len(cells):,} cells, bars {', '.join(str(b) for b in result['config']['bars'])}"]
    cache = {}
    for flavor in result["config"]["flavors"]:
        mine = [c for c in cells if c["flavor"] == flavor]
        row7 = [c for c in mine if c["reason"] == "none_clear"]
        lines.append(f"  {flavor}: none_clear on {len(row7):,} of {len(mine):,} cells ({len(row7) / len(mine):.1%})")
        if not row7:
            continue
        for bar in result["config"]["bars"]:  # per bar (v1.338): the row 7 cells and how many met the bar
            at = [c for c in mine if c["bar"] == bar]
            hit = [c for c in row7 if c["bar"] == bar]
            line = f"    bar {bar}: none_clear on {len(hit):,} of {len(at):,} cells"
            if hit:
                met = sum(c["success"]["decision"] >= bar for c in hit)
                line += f", the decision's held-out success at the bar or above on {met:,} ({met / len(hit):.1%})"
            lines.append(line)
        modes = Counter(c["mode"] for c in row7)
        held = sum(c["held_out_items"] for c in row7)
        lines.append(f"    decision delegates on {modes['delegate']:,} and works inline on {modes['inline']:,}; "
                     f"{held:,} held-out items")
        choice = {"decision": [c["mode"] for c in row7], "inline": ["inline"] * len(row7),
                  "delegate": ["delegate"] * len(row7)}
        if flavor == "cost_effective":
            cheaper = []
            for c in row7:
                d = rebuild(rows, registry, result, c, cache)
                cheaper.append("delegate" if d.delegate_cost_usd < d.inline_cost_usd else "inline")
            choice["cheaper"] = cheaper
            lines.append(f"    forecast cost lower for delegating on {cheaper.count('delegate'):,}, "
                         f"for inline on {cheaper.count('inline'):,}")
        scored = {}
        for name, picks in choice.items():
            correct = sum(c["correct"][p] for c, p in zip(row7, picks))
            cost = math.fsum(c["cost_usd"][p] for c, p in zip(row7, picks))
            met = sum(c["success"][p] >= c["bar"] for c, p in zip(row7, picks))
            scored[name] = (correct / held, cost / held)
            lines.append(f"    {name:<8}  success {correct / held:.3f}  cost per item {cost / held:.6f} USD  "
                         f"held-out success at the bar or above on {met:,} ({met / len(row7):.1%})")
        if "cheaper" in scored:
            (s0, c0), (s1, c1) = scored["decision"], scored["cheaper"]
            lines.append(f"    cheaper against decision: success {s1 - s0:+.3f}, cost per item {c1 / c0 - 1:+.1%}")
        best = sum(c["success"]["decision"] >= max(c["success"]["inline"], c["success"]["delegate"])
                   for c in row7)
        lines.append(f"    decision's held-out success at least the better path's on {best:,} ({best / len(row7):.1%})")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="no_path_clears.py", description=__doc__.splitlines()[0])
    parser.add_argument("--autobench", required=True)
    parser.add_argument("--autobench-registry", required=True)
    parser.add_argument("--tau2", required=True)
    parser.add_argument("--tau2-pooled", required=True)
    parser.add_argument("--llmrouterbench", required=True)
    parser.add_argument("--response-bank", required=True)
    args = parser.parse_args(argv)
    ab = _load(_ROOT / "evidence" / "delegation" / "results.py", "_r5_ab")
    t2 = _load(_ROOT / "evidence" / "tau2-bench-delegation" / "results.py", "_r5_t2")
    runs = [("AutoBench (13.10 results.json)", args.autobench, Registry.load(args.autobench_registry), ab.BARS, ab.points()),
            ("tau2-bench per domain (13.12 results.json)", args.tau2, Registry.load(TAU2_REGISTRY), t2.BARS, t2.points()),
            ("tau2-bench pooled (13.12 pooled.json)", args.tau2_pooled, Registry.load(TAU2_REGISTRY), t2.BARS, t2.points())]
    lines = []
    for label, path, registry, bars, points in runs:
        rows = read_rows(path)
        result = evaluate_delegation(rows, registry, bars=list(bars), points=points, seeds=range(50))
        lines += report(label, rows, registry, result)
    for option, label, folder, name in SELECTED:
        try:
            rows, registry, result = rerun_selected(getattr(args, option), folder, name)
        except ValueError as exc:  # nothing is printed to stdout (v1.338)
            print(f"error: {exc}", file=sys.stderr)
            return 1
        lines += report(label, rows, registry, result)
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
