"""Whether the re-read share and the brief's output size move a committed delegation decision (DESIGN 12.22 v1.413, row R38).

Usage:
  python research/reread_sensitivity.py --matrix autobench-tokens.jsonl --registry autobench-pool.json [--root PATH]
  python research/reread_sensitivity.py --dataset llmrouterbench --matrix llmrouterbench-matrix.jsonl [--root PATH]
  python research/reread_sensitivity.py --dataset response-bank --matrix response-bank-matrix.jsonl [--root PATH]
  python research/reread_sensitivity.py --dataset tau2-bench --matrix tau2-calls.jsonl [--root PATH]
  python research/reread_sensitivity.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl [--root PATH]

Runs `evaluate_delegation` (DESIGN 13.9) on the AutoBench 2026 converter's `--task-by all --tokens`
matrix and `--registry` pool on the base grid and on the variant grid, as evidence/delegation/
results.py makes results.json and variants.json (its bars, seeds and points), and checks that each
run's config, tasks and summary are the committed file's. With `--dataset llmrouterbench` (v1.414, row
R38b) it runs instead the 13.13 grid of evidence/llmrouterbench-delegation/results.py on the LLMRouterBench
converter's default matrix, on the rows that script's `select_rows` keeps for the committed registry.json
(no `--registry`), and checks it against results.json; `--dataset response-bank` (v1.415, row R38c) does the
same with the 13.14 grid of evidence/response-bank-delegation/results.py, the response-bank converter's
default matrix and that folder's registry.json; `--dataset tau2-bench` (`tau2-bench-pooled`, v1.416, row
R38d) runs the 13.12 grid of evidence/tau2-bench-delegation/results.py on the tau2-bench converter's
`--calls` (`--calls --task-by all`) matrix and that folder's registry.json, and checks it against
results.json (pooled.json). Those rows carry per-call sizes (13.9 v1.74), each item's work its own calls,
and `call_cost` prices them; the decision's `work_calls` is the calibration half's median call count, as in
13.9. Every committed result keeps the re-read
share sigma (`output_reread_share`) at 1.0 and the brief's output W (`brief_output_tokens`) at B
(DESIGN 13.1), so the script then re-decides every cell with the run's own calibration half and router
(13.9 `_calibrate` and `_router`), first at sigma 1.0 and W = B, where each cell's mode and model and
the held-out correct count and cost of its decision, of always inline and of always delegating must
be the run's, then at sigma 0, sigma 0.5 and
W = 2 B, where it re-decides every `cost_effective` cell while each `cost_blind` cell keeps its committed pick
(v1.438, row T14): neither sigma nor W can move it, since both enter only costs, never a context check (13.2
v1.404, 13.1 v1.405), a candidate's 5.2 `routing_cost` is 0.0 outside `cost_effective` and every 13.5 row that
compares costs is a `cost_effective` one, so the cut prints what re-deciding every cell prints, in half the
settings' decisions. A cell's decision changes when its mode or its model does. Both picks are scored on the cell's
held-out half at that setting's 13.2 list-price costs (sigma scales each re-read of a work call's
output and nothing else, W is the decision turn's output on the delegated path), so the comparison is
the one a caller sees whose model really re-reads that share or writes that much: the committed pick
against the one the decision makes once told. Per file, flavor, bar and setting it prints the cells,
the changed cells, their share, how many changed to inline, the changed cells' held-out success gap
(new correct minus committed correct over their held-out items) and cost ratio (new over committed),
and the cost ratio over all the cells, then per file and setting the changed cells by point, and by
the committed decision's 13.5 reason, with how many seeds and parents they fall on and the parent most
of them have; on a run of more than one task (LLMRouterBench, the Response Bank) the header names the task
count and a last line per setting gives the changed cells by task, in the run's task order.

Standard library and the model_routing package. Read by research/reread-sensitivity.md. Exit 0, or 2
with one `error: ...` line on a missing or unreadable file, a row 13.9 refuses, a model with price
tiers, a row with per-call sizes outside the tau2-bench runs or one without them in those runs (not priced
here), a run whose config, tasks or summary is not the
committed file's, a re-decided cell or held-out sum at sigma 1.0 and W = B that is not the run's,
`--dataset autobench` without `--registry` or another dataset with it.
"""

import argparse
import importlib.util
import json
import sys
from math import fsum
from pathlib import Path

from collections import Counter

from model_routing import Registry, evaluate_delegation, split_items
from model_routing.delegation_eval import _calibrate, _router, _row

ROOT = Path(__file__).resolve().parents[1]
# dataset: its name in the report, the folder of its delegation results script, and each committed file
# with its grid in that script (`base` is its `points()`, `variants` its `variant_points()`)
DATASETS = {
    "autobench": ("AutoBench 2026", "evidence/delegation",
                  (("results.json", "base"), ("variants.json", "variants"))),
    "llmrouterbench": ("LLMRouterBench", "evidence/llmrouterbench-delegation", (("results.json", "base"),)),
    "response-bank": ("LLM Routing Response Bank", "evidence/response-bank-delegation", (("results.json", "base"),)),
    "tau2-bench": ("tau2-bench per domain", "evidence/tau2-bench-delegation", (("results.json", "base"),)),
    "tau2-bench-pooled": ("tau2-bench pooled", "evidence/tau2-bench-delegation", (("pooled.json", "base"),)),
}
# the datasets whose results script keeps rows by `select_rows`, and those whose rows carry per-call sizes
SELECTED = ("llmrouterbench", "response-bank")
PER_CALL = ("tau2-bench", "tau2-bench-pooled")
# label, sigma, W as a multiple of B
SETTINGS = (("sigma 0", 0.0, 1), ("sigma 0.5", 0.5, 1), ("W = 2 B", 1.0, 2))
# the flavors whose cells a setting re-decides; a `cost_blind` cell keeps its committed pick, which neither sigma
# nor W can move (v1.438, row T14); the tests set both flavors to run the v1.413 to v1.437 re-decision of every cell
REDECIDED = ("cost_effective",)
HEADER = ("  flavor          bar  setting    changed / cells  share  to inline  "
          "success gap  cost ratio  all cost ratio")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def read_rows(path):
    try:
        with open(path, encoding="utf-8") as handle:
            return [json.loads(line) for line in handle if line.strip()]
    except FileNotFoundError:
        raise ValueError(f"{path}: no such file") from None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: not a JSON lines file ({exc})") from None


def read_object(path):
    try:
        value = json.loads(Path(path).read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{path}: no such file") from None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{path}: not a JSON file ({exc})") from None
    if not isinstance(value, dict):
        raise ValueError(f"{path}: not a JSON object")
    return value


def item_cost(p, d, point, path, tin, tout, sigma, w):
    """13.2's list cost of one held-out item on one path at re-read share sigma and brief output W.

    The 13.9 expressions on a model without tiers and a row without per-call sizes, with each read
    `w_out * S_out` as `w_out * sigma * S_out` and each `K * (S_in + S_out)` as `K * (S_in + sigma *
    S_out)` (13.2 v1.404), and the decision turn's brief as `P.cost(0, W)` (v1.405, v1.410); at sigma
    1.0 and W = B each is the 13.9 cost bit for bit, which `rerun` checks on every cell.
    """
    c, b, r, t = (point[k] for k in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns"))
    k = point.get("work_calls", 1)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    if path == "delegate":
        return (p.base_cost(0, w) + d.base_cost(k * b + w_in * tin + w_out * sigma * tout, k * tout)
                + (1 + t) * p.base_cost(b + r, 0))
    separate = point["inline_separate_call"]
    reads = k * c if separate else (k - 1) * c
    if "cached_read_ratio" in point:
        reads = reads * point["cached_read_ratio"]
    shared = (1 + t) if separate else t
    return (p.base_cost(reads + w_in * tin + w_out * sigma * tout, k * tout)
            + shared * p.base_cost(k * (tin + sigma * tout), 0))


def call_cost(p, d, point, path, calls, sigma, w):
    """13.2's list cost of one held-out item with per-call sizes (13.9 v1.74) at sigma and W.

    Call j reads a_1 to a_j and b_1 to b_(j-1), each b re-read at sigma (13.2 v1.404), so the K calls read
    sum (K - j + 1) a_j + sigma * sum (K - j) b_j, and each later read of the work, A + O, is A + sigma * O;
    the decision turn's brief is `P.cost(0, W)`. At sigma 1.0 and W = B each is the 13.9 cost bit for bit.
    """
    k, _rd, a, o, ins, outs = calls
    c, b, r, t = (point[x] for x in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns"))
    rd = sum((k - j) * x for j, x in enumerate(ins)) + sigma * sum((k - j - 1) * y for j, y in enumerate(outs))
    if path == "delegate":
        return p.base_cost(0, w) + d.base_cost(k * b + rd, o) + (1 + t) * p.base_cost(b + r, 0)
    separate = point["inline_separate_call"]
    base = k * c if separate else (k - 1) * c
    if "cached_read_ratio" in point:
        base = base * point["cached_read_ratio"]
    return p.base_cost(base + rd, o) + ((1 + t) if separate else t) * p.base_cost(a + sigma * o, 0)


class Run:
    """One grid's run and what re-deciding its cells needs."""

    def __init__(self, rows, registry, grid, dr, per_call=False):
        self.registry = registry
        self.per_call = per_call
        self.table = {}
        for raw in rows:
            task, item, model, row = _row(raw)
            if (row[3] is not None) != per_call:
                raise ValueError(f"task {task!r}: rows with{'out' if per_call else ''} per-call sizes are not "
                                 "priced here")
            self.table.setdefault((task, item), {})[model] = row
        points = dr.points() if grid == "base" else dr.variant_points()
        self.result = evaluate_delegation(rows, registry, bars=list(dr.BARS), points=points,
                                          seeds=range(dr.SEEDS))
        config = self.result["config"]
        self.models = sorted({m for by_model in self.table.values() for m in by_model})
        for m in self.models:
            if registry.get(m).price_tiers:
                raise ValueError(f"model {m!r} has price tiers, which are not priced here")
        items = {}
        for task, item in self.table:
            items.setdefault(task, []).append(item)
        self.calibrated = {}
        for task in sorted(items):
            for seed in config["seeds"]:
                cal, held = split_items(items[task], seed, config["calibration_fraction"])
                self.calibrated[task, seed] = _calibrate(self.table, self.models, task, cal, held, per_call)
        self.routers = {(task, seed, bar): _router(registry, task, self.calibrated[task, seed], bar,
                                                   config["min_samples"], config["confidence"])
                        for (task, seed) in self.calibrated for bar in config["bars"]}
        self.items = items
        self.costs = {}  # each item's cost by path and setting
        self.correct = {}  # the held-out correct count by task, seed and model
        self.sums = {}  # the held-out sums by path, setting and seed: a cell of another bar or flavor shares them

    def held_sum(self, cell, point, mode, model, sigma, w):
        task, seed = cell["task"], cell["seed"]
        key = (task, cell["point"], cell["parent"], mode, model, sigma, w)
        if (key, seed) in self.sums:
            return self.sums[key, seed]
        held = self.calibrated[task, seed]["held"]
        if key not in self.costs:
            p, d = self.registry.get(cell["parent"]), self.registry.get(model)
            rows = {i: self.table[task, i][model] for i in self.items[task]}
            self.costs[key] = {i: call_cost(p, d, point, mode, row[3], sigma, w) if self.per_call
                               else item_cost(p, d, point, mode, row[1], row[2], sigma, w) for i, row in rows.items()}
        if (task, seed, model) not in self.correct:
            self.correct[task, seed, model] = sum(self.table[task, i][model][0] for i in held)
        self.sums[key, seed] = (self.correct[task, seed, model], fsum(map(self.costs[key].__getitem__, held)),
                                len(held))
        return self.sums[key, seed]

    def decide(self, cell, point, sigma, w):
        router = self.routers[cell["task"], cell["seed"], cell["bar"]]
        k = self.calibrated[cell["task"], cell["seed"]].get("k")
        decision = router.decide_delegation(cell["task"], cell["parent"], cell["flavor"],
                                            **(point if k is None else dict(point, work_calls=k)),
                                            output_reread_share=sigma, brief_output_tokens=w)
        return decision.mode, decision.model


def checked(rows, registry, root, name, grid, dr, dataset="autobench"):
    """The run of one committed file's grid, its config, tasks and summary as JSON values and the file's path:
    exit 2 unless those are the file's and each cell re-decided at sigma 1.0 and W = B keeps its pick and
    held-out sums (research/delegation_price_sensitivity.py, v1.424, runs the same check)."""
    _title, folder, _files = DATASETS[dataset]
    rel = f"{folder}/{name}"
    committed = read_object(Path(root) / rel)
    run = Run(rows, registry, grid, dr, dataset in PER_CALL)
    got = json.loads(json.dumps({k: run.result[k] for k in ("config", "tasks", "summary")}))
    for key in ("config", "tasks", "summary"):
        if got[key] != committed.get(key):
            raise ValueError(f"{rel}: the run's {key} is not the committed one")
    config = got["config"]
    cells = run.result["cells"]
    for cell in cells:
        point = config["points"][cell["point"]]
        b = point["brief_tokens"]
        if run.decide(cell, point, 1.0, b) != (cell["mode"], cell["model"]):
            raise ValueError(f"{rel}: a cell re-decided at sigma 1.0 and W = B is not the run's: "
                             f"{cell['flavor']}, bar {cell['bar']}, point {cell['point']}, "
                             f"parent {cell['parent']}, seed {cell['seed']}")
        paths = {"decision": (cell["mode"], cell["model"]), "inline": ("inline", cell["parent"]),
                 "delegate": ("delegate", cell["delegate"])}
        if any(run.held_sum(cell, point, *pick, 1.0, b)[:2] != (cell["correct"][s], cell["cost_usd"][s])
               for s, pick in paths.items()):
            raise ValueError(f"{rel}: a held-out sum at sigma 1.0 and W = B is not the run's: "
                             f"{cell['flavor']}, bar {cell['bar']}, point {cell['point']}, "
                             f"parent {cell['parent']}, seed {cell['seed']}")
    return run, got, rel


def rerun(rows, registry, root, name, grid, dr, dataset="autobench"):
    """The report lines of one committed file: the check at sigma 1.0 and W = B, then the settings."""
    title = DATASETS[dataset][0]
    run, got, rel = checked(rows, registry, root, name, grid, dr, dataset)
    config = got["config"]
    cells = run.result["cells"]
    tasks = list(got["tasks"])
    lines = [f"{title}, {grid} grid (`{rel}`): {len(cells):,} cells, "
             + (f"{len(tasks)} tasks, " if len(tasks) > 1 else "") + f"{len(config['bars'])} bars, "
             f"{len(config['flavors'])} flavors, {len(config['points'])} points, "
             f"{len(config['parents'])} parents, {len(config['seeds'])} seeds; every cell's decision and "
             "held-out sum reproduced at sigma 1.0 and W = B", HEADER]
    by_point = {label: [0] * len(config["points"]) for label, _, _ in SETTINGS}
    by_task = {label: dict.fromkeys(tasks, 0) for label, _, _ in SETTINGS}
    why = {label: [] for label, _, _ in SETTINGS}  # (committed reason, seed, parent) of each changed cell
    for flavor in config["flavors"]:
        for bar in config["bars"]:
            sel = [c for c in cells if c["flavor"] == flavor and c["bar"] == bar]
            for label, sigma, factor in SETTINGS:
                changed = inline = 0
                gap = [0, 0, 0]  # new correct, committed correct, held-out items, on the changed cells
                new_cost, old_cost, all_new, all_old = [], [], [], []
                for cell in sel:
                    point = config["points"][cell["point"]]
                    w = factor * point["brief_tokens"]
                    old = run.held_sum(cell, point, cell["mode"], cell["model"], sigma, w)
                    pick = (run.decide(cell, point, sigma, w) if flavor in REDECIDED
                            else (cell["mode"], cell["model"]))
                    new = old if pick == (cell["mode"], cell["model"]) else run.held_sum(
                        cell, point, pick[0], pick[1], sigma, w)
                    all_new.append(new[1])
                    all_old.append(old[1])
                    if pick != (cell["mode"], cell["model"]):
                        changed += 1
                        inline += pick[0] == "inline"
                        by_point[label][cell["point"]] += 1
                        by_task[label][cell["task"]] += 1
                        why[label].append((cell["reason"], cell["seed"], cell["parent"]))
                        gap = [gap[0] + new[0], gap[1] + old[0], gap[2] + old[2]]
                        new_cost.append(new[1])
                        old_cost.append(old[1])
                if changed:
                    success = f"{(gap[0] - gap[1]) / gap[2]:+.4f}"
                    ratio = f"{fsum(new_cost) / fsum(old_cost):.3f}"
                else:
                    success = ratio = "-"
                share = f"{100 * changed / len(sel):.1f}%"
                lines.append(f"  {flavor:<14}  {bar:<3}  {label:<9}  {changed:>7} / {len(sel):<5,}  "
                             f"{share:>5}  {inline:>9}  {success:>11}  {ratio:>10}  "
                             f"{fsum(all_new) / fsum(all_old):>14.3f}")
    for label, _, _ in SETTINGS:
        lines.append(f"  changed cells by point, {label}: "
                     + ", ".join(f"{i}: {n}" for i, n in enumerate(by_point[label])))
    for label, _, _ in SETTINGS:
        lines.append(f"  changed cells by reason, {label}: " + reasons(why[label]))
    if len(tasks) > 1:
        for label, _, _ in SETTINGS:
            lines.append(f"  changed cells by task, {label}: "
                         + ", ".join(f"{t} {n}" for t, n in by_task[label].items()))
    return lines


def reasons(changed):
    """The committed reasons of the changed cells, most first, then their seeds and parents."""
    if not changed:
        return "none"
    count = sorted(Counter(r for r, _, _ in changed).items(), key=lambda kv: (-kv[1], kv[0]))
    parents = sorted(Counter(p for _, _, p in changed).items(), key=lambda kv: (-kv[1], kv[0]))
    seeds = len({s for _, s, _ in changed})
    return (", ".join(f"{r} {n}" for r, n in count) + f"; {seeds} seed{'' if seeds == 1 else 's'}, "
            f"{len(parents)} parent{'' if len(parents) == 1 else 's'}, the most {parents[0][1]} of {parents[0][0]}")


def inputs(matrix, registry=None, root=ROOT, dataset="autobench"):
    """What a run of one dataset reads: its title, its committed files with their grids, its results script,
    its rows and its registry. `registry` is the AutoBench pool file, and None for the others, whose committed
    registry.json is read from `root`; on LLMRouterBench and the Response Bank the rows are those the
    dataset's `select_rows` keeps for it, and on tau2-bench every row of the matrix."""
    if dataset not in DATASETS:
        raise ValueError(f"dataset must be one of {', '.join(DATASETS)}, got {dataset!r}")
    if dataset == "autobench" and registry is None:
        raise ValueError("--dataset autobench needs --registry")
    if dataset != "autobench" and registry is not None:
        raise ValueError("--registry is only used with --dataset autobench")
    title, folder, files = DATASETS[dataset]
    dr = _load(f"research_reread_{dataset}_results", Path(root) / folder / "results.py")
    rows = read_rows(matrix)
    path = Path(root) / folder / "registry.json" if registry is None else registry
    try:
        pool = Registry.load(path)
    except FileNotFoundError:
        raise ValueError(f"{path}: no such file") from None
    if dataset in SELECTED:
        rows, _dropped = dr.select_rows(rows, [m.id for m in pool.models])
    return title, files, dr, rows, pool


def run(matrix, registry=None, root=ROOT, dataset="autobench"):
    """The report lines of one dataset, on what `inputs` reads."""
    title, files, dr, rows, pool = inputs(matrix, registry, root, dataset)
    lines = [f"The re-read share and the brief's output on the {title} delegation results: each cell "
             "re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs"]
    for name, grid in files:
        lines += rerun(rows, pool, root, name, grid, dr, dataset)
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--matrix", required=True,
                        help="the AutoBench converter's --task-by all --tokens matrix, or with --dataset "
                             "llmrouterbench or response-bank that dataset's converter's default output, or with "
                             "tau2-bench (tau2-bench-pooled) the tau2-bench converter's --calls (--calls --task-by "
                             "all) output")
    parser.add_argument("--registry", help="with --dataset autobench: the AutoBench converter's --registry pool")
    parser.add_argument("--dataset", choices=tuple(DATASETS), default="autobench",
                        help="the delegation results to re-decide (default: autobench, DESIGN 13.10; "
                             "llmrouterbench, 13.13; response-bank, 13.14; tau2-bench and tau2-bench-pooled, "
                             "13.12 results.json and pooled.json)")
    parser.add_argument("--root", default=str(ROOT), help="the repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        lines = run(args.matrix, args.registry, Path(args.root), args.dataset)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    sys.stdout.write("\n".join(lines) + "\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
