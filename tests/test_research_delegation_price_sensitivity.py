"""research/delegation-price-sensitivity.md and research/delegation_price_sensitivity.py (DESIGN 12.22 v1.424,
row R39).

The script's report on a hand-built AutoBench-shaped matrix of three models, run end to end through `main`
against a root whose committed 13.10 files are that matrix's, is checked against a brute force that rebuilds
each cell's router from the public API on a registry with one model's prices scaled, and prices each held-out
item at the committed prices in exact fractions; `scaled` changes one model's two prices and nothing else; the
script exits 2 where research/reread_sensitivity.py's `checked` does. The note's Results block is the script's
output on the pinned AutoBench files, compared byte for byte when they are cached, which CI never does; every
number of the note's prose is in a Facts bullet this file builds from that block, or a DESIGN section number.

v1.425 (row R39b) adds `--dataset llmrouterbench`: a hand-built matrix of two tasks and three models, with an item
that `select_rows` drops and a row of a model the registry lacks, is checked against the same brute force, which
then names the task count and gives the changed cells by task; a stub `picks` makes two runs tie for the most, so
the tie-break (the first run in model, then factor, order) is run, and the hand matrix moves a committed inline
cell to a delegate (review iter-285 nit 8). The note's LLMRouterBench block is compared with the script's output
on the pinned file when it is cached (the session fixture `llmrouterbench_pinned` of tests/conftest.py), and its
Facts bullets are built from that block.

v1.426 (row R39c) adds `--dataset response-bank`, checked as `--dataset llmrouterbench` is: the same hand matrix on
a root whose committed 13.14 files are its run, at the 13.14 bars, against the same brute force. The note's Response
Bank block is compared with the script's output on the pinned files when they are cached (the session fixture
`response_bank_pinned` of tests/conftest.py), its Facts bullets are built from that block, and its Facts, Reading
it and Recommendation claims are checked against it and the re-read note's Response Bank block.

v1.427 (row R39d) adds `--dataset tau2-bench` and `tau2-bench-pooled`, the 13.12 runs, whose rows carry per-call
sizes: a hand matrix of three tasks and three models, one task with two calls on every item so the decision's
`work_calls` is above one, runs on a root whose committed 13.12 file is its run, against the brute force with
each model's calibration sizes its rounded-up means per call, `work_calls` the half's median call count and
each held-out item priced one call at a time. The note's two tau2-bench blocks are compared with the script's
output on the 12 pinned run files when they are cached, their Facts bullets are built from them, and the Facts,
Reading it and Recommendation claims about them are checked against them, the other blocks and the re-read note.

v1.428 (row DOC36, DESIGN 9): README Limitations' prices bullet gives, right after its routing sentence, the
largest share of a bar's `cost_effective` cells one run changes on each of the four delegation datasets, built
here from the note's five blocks, and links the note; the 9 clause, the 12.22 bullet's pointer to it and the
note's Recommendation are pinned.
"""

import contextlib
import dataclasses
import importlib.util
import io
import json
import re
import statistics
from fractions import Fraction
from pathlib import Path

import pytest

from model_routing import Model, Registry, Router, Stats, Task, evaluate_delegation, split_items

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "delegation_price_sensitivity.py"
NOTE = ROOT / "research" / "delegation-price-sensitivity.md"
INDEX = ROOT / "research" / "README.md"
DESIGN = ROOT / "DESIGN.md"
FOLDER = ROOT / "evidence" / "delegation"
LRB = ROOT / "evidence" / "llmrouterbench-delegation"
RB = ROOT / "evidence" / "response-bank-delegation"
T2 = ROOT / "evidence" / "tau2-bench-delegation"
COMMAND = ("$ python research/delegation_price_sensitivity.py --matrix autobench-tokens.jsonl"
           " --registry autobench-pool.json")
LRB_COMMAND = ("$ python research/delegation_price_sensitivity.py --dataset llmrouterbench"
               " --matrix llmrouterbench-matrix.jsonl")
RB_COMMAND = ("$ python research/delegation_price_sensitivity.py --dataset response-bank"
              " --matrix response-bank-matrix.jsonl")
T2_COMMAND = "$ python research/delegation_price_sensitivity.py --dataset tau2-bench --matrix tau2-calls.jsonl"
T2_POOLED_COMMAND = ("$ python research/delegation_price_sensitivity.py --dataset tau2-bench-pooled"
                     " --matrix tau2-calls-all.jsonl")
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens"
    " --registry autobench-pool.json",
    COMMAND[2:],
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl",
    LRB_COMMAND[2:],
    "python evidence/response-bank/convert.py --out response-bank-matrix.jsonl",
    RB_COMMAND[2:],
    "python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls",
    T2_COMMAND[2:],
    "python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all",
    T2_POOLED_COMMAND[2:],
]
SECTIONS = ["Facts", "Method", "Results", "Reading it", "Recommendation", "Limits", "Regenerate"]
BULLET = "- A price error in a delegation decision, on AutoBench (v1.424, row R39): "
ALLOWED = {"12.22", "13.2", "13.5", "13.9", "13.10", "13.12", "13.13", "13.14"}
NUMBER = re.compile(r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
FACTORS = (0.5, 2.0)
TITLE = ("One model's list price halved or doubled on the AutoBench 2026 delegation results: each cell re-decided "
         "with that model's input and output prices times 0.5 or 2.0, both picks scored at the committed prices")
LRB_TITLE = TITLE.replace("AutoBench 2026", "LLMRouterBench")
RB_TITLE = TITLE.replace("AutoBench 2026", "LLM Routing Response Bank")
REREAD = ROOT / "research" / "reread-sensitivity.md"
REREAD_COMMAND = "$ python research/reread_sensitivity.py --matrix autobench-tokens.jsonl --registry autobench-pool.json"
REREAD_LRB_COMMAND = "$ python research/reread_sensitivity.py --dataset llmrouterbench --matrix llmrouterbench-matrix.jsonl"
REREAD_RB_COMMAND = "$ python research/reread_sensitivity.py --dataset response-bank --matrix response-bank-matrix.jsonl"
REREAD_T2_COMMANDS = ("$ python research/reread_sensitivity.py --dataset tau2-bench --matrix tau2-calls.jsonl",
                      "$ python research/reread_sensitivity.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl")
HEADER = ("  flavor          bar  runs moving  most changed / cells  share  to inline  success gap  cost ratio  "
          "all cost ratio  by")

# Parent v/p at 1 and 2 USD per million input and output tokens, delegates v/d at 1 and 1 and v/e at 0.8 and
# 0.8, each right on most items, so at bar 0.7 `cost_effective` hands work to v/e, the cheapest delegate
# that clears, until v/d's prices are halved or v/e's doubled; at the folded point 3 inline and delegating
# cost about the same for v/p, so halving or doubling v/p's prices moves some cells between the two paths.
P = Model("v/p", "fam-p", 1.0, 2.0, 1_000_000)
D = Model("v/d", "fam-d", 1.0, 1.0, 1_000_000)
E = Model("v/e", "fam-e", 0.8, 0.8, 1_000_000)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ps():
    return _load("research_delegation_price_sensitivity", SCRIPT)


@pytest.fixture(scope="module")
def dr():
    return _load("research_delegation_price_results", FOLDER / "results.py")


@pytest.fixture(scope="module")
def lrb():
    return _load("research_delegation_price_lrb_results", LRB / "results.py")


@pytest.fixture(scope="module")
def rb():
    return _load("research_delegation_price_rb_results", RB / "results.py")


@pytest.fixture(scope="module")
def t2():
    return _load("research_delegation_price_t2_results", T2 / "results.py")


def _rows():
    rows = []
    for j in range(80):
        item = f"i{j:02d}"
        rows.append({"task": "t", "item": item, "model": "v/p", "correct": j % 10 != 0,
                     "input_tokens": 100, "output_tokens": 1200 + 40 * (j % 11)})
        rows.append({"task": "t", "item": item, "model": "v/d", "correct": j % 20 != 0,
                     "input_tokens": 100, "output_tokens": 100})
        rows.append({"task": "t", "item": item, "model": "v/e", "correct": j % 8 != 3,
                     "input_tokens": 100, "output_tokens": 110 + 10 * (j % 3)})
    return rows


def _registry_file(path, registry):
    entries = [dict(dataclasses.asdict(m), source="https://example.org/prices") for m in registry.models]
    for e in entries:
        del e["price_tiers"]
    path.write_text(json.dumps({"version": "1", "as_of": "2026-01-01", "currency": "USD", "models": entries}),
                    encoding="utf-8")
    return path


def _root(tmp_path, dr, rows, registry):
    folder = tmp_path / "root" / "evidence" / "delegation"
    folder.mkdir(parents=True)
    (folder / "results.py").write_text((FOLDER / "results.py").read_text(encoding="utf-8"), encoding="utf-8")
    for name, grid in (("results.json", "base"), ("variants.json", "variants")):
        (folder / name).write_text(json.dumps(dr.run(rows, registry, grid), indent=2) + "\n", encoding="utf-8")
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return tmp_path / "root", matrix, _registry_file(tmp_path / "pool.json", registry)


def _lrb_rows():
    """Two tasks, `u` listed before `t`, each built as `_rows` with v/p's output sizes of its own; item `t80` has a
    null output count for v/p, so `select_rows` drops it, and `v/x`, a model the registry lacks, has one row.

    On `t` v/p writes about 1,080 output tokens, so at the folded point 3 its inline path costs a little less than
    delegating to v/e (13.2: 200 + 3 * 1,080 = 3,440 against 1,000 + 576 + 2,000 = 3,576 millionths of a USD) and
    a run that halves a delegate's prices, or doubles v/p's, sends those committed inline cells to a delegate."""
    rows = []
    for task, base, step, mod in (("u", 1200, 40, 11), ("t", 1050, 10, 7)):
        for j in range(80):
            item = f"{task}{j:02d}"
            rows.append({"task": task, "item": item, "model": "v/p", "correct": j % 10 != 0,
                         "input_tokens": 100, "output_tokens": base + step * (j % mod)})
            rows.append({"task": task, "item": item, "model": "v/d", "correct": j % 20 != 0,
                         "input_tokens": 100, "output_tokens": 100})
            rows.append({"task": task, "item": item, "model": "v/e", "correct": j % 8 != 3,
                         "input_tokens": 100, "output_tokens": 110 + 10 * (j % 3)})
    for model, out in (("v/p", None), ("v/d", 100), ("v/e", 110)):
        rows.append({"task": "t", "item": "t80", "model": model, "correct": True, "input_tokens": 100,
                     "output_tokens": out})
    rows.append({"task": "u", "item": "u00", "model": "v/x", "correct": True, "input_tokens": 1, "output_tokens": 1})
    return rows


def _lrb_root(tmp_path, lrb, rows, registry, target=LRB):
    """A root whose committed 13.13 files (or, with `target` RB, 13.14 files) are the run on `rows`; the 13.13
    script reads its base points from the 13.10 script beside it, and the 13.14 script reads those and the 13.13
    `select_rows`, so those are copied too."""
    root = tmp_path / "root"
    for source in dict.fromkeys((FOLDER, LRB, target)):
        folder = root / "evidence" / source.name
        folder.mkdir(parents=True)
        (folder / "results.py").write_text((source / "results.py").read_text(encoding="utf-8"), encoding="utf-8")
    folder = root / "evidence" / target.name
    _registry_file(folder / "registry.json", registry)
    kept, _dropped = lrb.select_rows(rows, [m.id for m in registry.models])
    (folder / "results.json").write_text(json.dumps(lrb.run(kept, registry), indent=2) + "\n", encoding="utf-8")
    matrix = tmp_path / "lrb.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return root, matrix


def _kept(rows, registry):
    """The 13.13 rows, kept here apart from `select_rows`: the registry's models, less every item on which one of
    them has a null token count."""
    names = {m.id for m in registry.models}
    null = {r["item"] for r in rows if r["model"] in names and None in (r["input_tokens"], r["output_tokens"])}
    kept = [r for r in rows if r["model"] in names and r["item"] not in null]
    assert null == {"t80"} and len(kept) == len(rows) - 4
    return kept


def _main(ps, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ps.main(argv)
    return code, out.getvalue(), err.getvalue()


# --- the brute force -------------------------------------------------------------------------
def _cost(m, i, o):
    return (Fraction(i) * Fraction(m.price_in) + Fraction(o) * Fraction(m.price_out)) / 1_000_000


def _exact(p, d, point, path, tin, tout):
    """13.2 (the 13.9 cost) in fractions, written apart from the scripts' float expressions."""
    c, b, r, t = (point[k] for k in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns"))
    k = point.get("work_calls", 1)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    if path == "delegate":
        return _cost(p, 0, b) + _cost(d, k * b + w_in * tin + w_out * tout, k * tout) + (1 + t) * _cost(p, b + r, 0)
    separate = point["inline_separate_call"]
    reads = Fraction(k * c if separate else (k - 1) * c) * Fraction(point.get("cached_read_ratio", 1))
    work = _cost(p, reads + w_in * tin + w_out * tout, k * tout)
    return work + ((1 + t) if separate else t) * _cost(p, k * (tin + tout), 0)


def _exact_calls(p, d, point, path, a, b):
    """13.2 (the 13.9 v1.74 cost) on a row with per-call sizes, in fractions, one call at a time: call j reads the
    path's base, a_1 to a_j and b_1 to b_(j-1)."""
    c, brief, r, t = (point[k] for k in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns"))
    k = len(a)
    reads = [sum(a[:j + 1]) + sum(b[:j]) for j in range(k)]
    if path == "delegate":
        return _cost(p, 0, brief) + _cost(d, k * brief + sum(reads), sum(b)) + (1 + t) * _cost(p, brief + r, 0)
    separate = point["inline_separate_call"]
    base = Fraction(k * c if separate else (k - 1) * c) * Fraction(point.get("cached_read_ratio", 1))
    return _cost(p, base + sum(reads), sum(b)) + ((1 + t) if separate else t) * _cost(p, sum(a) + sum(b), 0)


def _up(x, y):
    return -(-x // y)


def _expected(rows, registry, dr, grid, name, title="AutoBench 2026", folder="evidence/delegation", per_call=False):
    """The report lines of one committed file: each run's routers rebuilt from the public API per task, seed and
    bar on a registry built here with one model's prices scaled, each held-out sum in fractions at the committed
    prices. With `per_call` (v1.427) each model's calibration sizes are its rounded-up means per call, the
    decision's `work_calls` the half's median call count (13.9 v1.74), and each item is priced by `_exact_calls`."""
    points = dr.points() if grid == "base" else dr.variant_points()
    result = evaluate_delegation(rows, registry, bars=list(dr.BARS), points=points, seeds=range(dr.SEEDS))
    cells, tasks = result["cells"], list(result["tasks"])
    by = {(r["task"], r["item"], r["model"]): r for r in rows}
    items = {t: list(dict.fromkeys(r["item"] for r in rows if r["task"] == t)) for t in tasks}
    models = sorted({r["model"] for r in rows})
    halves = {(t, seed): split_items(items[t], seed, 0.5) for t in tasks for seed in range(dr.SEEDS)}
    runs = [(m, f) for m in models for f in FACTORS]

    works = {}

    def router(prices, tk, seed, bar):
        cal = halves[tk, seed][0]
        stats = Stats()
        each = [by[tk, i, m] for i in cal for m in models]
        for m in models:
            hits = [by[tk, i, m] for i in cal]
            if per_call:
                k = sum(len(h["call_input_tokens"]) for h in hits)
                stats.add(tk, m, sum(h["correct"] for h in hits), len(cal),
                          input_tokens=len(cal) * _up(sum(sum(h["call_input_tokens"]) for h in hits), k),
                          output_tokens=len(cal) * _up(sum(h["output_tokens"] for h in hits), k))
            else:
                stats.add(tk, m, sum(h["correct"] for h in hits), len(cal),
                          input_tokens=sum(h["input_tokens"] for h in hits),
                          output_tokens=sum(h["output_tokens"] for h in hits))
        if per_call:
            sizes = ([_up(sum(h["call_input_tokens"]), len(h["call_input_tokens"])) for h in each],
                     [_up(h["output_tokens"], len(h["call_input_tokens"])) for h in each])
            works[tk, seed] = statistics.median_low([len(h["call_input_tokens"]) for h in each])
        else:
            sizes = ([h["input_tokens"] for h in each], [h["output_tokens"] for h in each])
        task = Task(name=tk, bar=bar, min_samples=30, confidence=0.95, independent_of_generator=False,
                    expected_input_tokens=statistics.median_low(sizes[0]),
                    expected_output_tokens=statistics.median_low(sizes[1]),
                    on_no_model="best_available", max_fallbacks=0)
        return Router(prices, {tk: task}, stats)

    sums = {}

    def held(cell, pick):
        key = (cell["task"], cell["seed"], cell["point"], cell["parent"], pick)
        if key not in sums:
            point = points[cell["point"]]
            p, d = registry.get(cell["parent"]), registry.get(pick[1])
            hits = [by[cell["task"], i, pick[1]] for i in halves[cell["task"], cell["seed"]][1]]
            sums[key] = (sum(h["correct"] for h in hits), len(hits),
                         sum(_exact_calls(p, d, point, pick[0], h["call_input_tokens"], h["call_output_tokens"])
                             if per_call else _exact(p, d, point, pick[0], h["input_tokens"], h["output_tokens"])
                             for h in hits))
        return sums[key]

    new = {}
    for m, f in runs:
        prices = Registry([Model(x.id, x.family, x.price_in * f, x.price_out * f, x.context_window) if x.id == m
                           else x for x in registry.models])
        routers = {(t, s, b): router(prices, t, s, b) for t in tasks for s in range(dr.SEEDS) for b in dr.BARS}
        new[m, f] = [routers[c["task"], c["seed"], c["bar"]].decide_delegation(
            c["task"], c["parent"], c["flavor"],
            **(dict(points[c["point"]], work_calls=works[c["task"], c["seed"]]) if per_call else points[c["point"]]))
                     for c in cells]
    lines = [f"{title}, {grid} grid (`{folder}/{name}`): {len(cells):,} cells, "
             + (f"{len(tasks)} tasks, " if len(tasks) > 1 else "") + f"{len(dr.BARS)} bars, "
             f"2 flavors, {len(points)} points, {len(models)} parents, {dr.SEEDS} seeds, {len(models)} models, so "
             f"{len(runs)} runs; every cell's decision and held-out sum reproduced at the committed prices", HEADER]
    by_point, by_model = [0] * len(points), {r: [0, 0] for r in runs}
    by_task = dict.fromkeys(tasks, 0)
    for flavor in ("cost_effective", "cost_blind"):
        for bar in dr.BARS:
            sel = [i for i, c in enumerate(cells) if (c["flavor"], c["bar"]) == (flavor, bar)]
            stats = []
            for r in runs:
                changed = inline = hits_new = hits_old = n = 0
                cost_new = cost_old = all_new = all_old = Fraction(0)
                for i in sel:
                    was = (cells[i]["mode"], cells[i]["model"])
                    pick = (new[r][i].mode, new[r][i].model)
                    old, now = held(cells[i], was), held(cells[i], pick)
                    all_new, all_old = all_new + now[2], all_old + old[2]
                    if pick != was:
                        changed += 1
                        inline += pick[0] == "inline"
                        by_point[cells[i]["point"]] += 1
                        by_task[cells[i]["task"]] += 1
                        hits_new, hits_old, n = hits_new + now[0], hits_old + old[0], n + old[1]
                        cost_new, cost_old = cost_new + now[2], cost_old + old[2]
                by_model[r][0] += changed
                by_model[r][1] += inline
                stats.append((changed, r, inline, f"{(hits_new - hits_old) / n:+.4f}" if changed else "-",
                              f"{float(cost_new / cost_old):.3f}" if changed else "-", f"{float(all_new / all_old):.3f}"))
            moving = sum(s[0] > 0 for s in stats)
            top = max(stats, key=lambda s: s[0])  # the first of the largest, in run order
            if top[0] == 0:
                top = (0, None, 0, "-", "-", "1.000")
            by_run = "-" if top[1] is None else f"{top[1][0]} times {top[1][1]}"
            lines.append(f"  {flavor:<14}  {bar:<3}  {moving:>6} / {len(runs):<3}  {top[0]:>12,} / {len(sel):<5,}  "
                         f"{100 * top[0] / len(sel):>4.1f}%  {top[2]:>9}  {top[3]:>11}  {top[4]:>10}  {top[5]:>14}  "
                         f"{by_run}")
    lines.append(f"  changed cells by point, all {len(runs)} runs: " + ", ".join(f"{i}: {n:,}" for i, n in enumerate(by_point)))
    if len(tasks) > 1:
        lines.append(f"  changed cells by task, all {len(runs)} runs: " + ", ".join(f"{t} {n:,}" for t, n in by_task.items()))
    for m in models:
        (a, ai), (b, bi) = by_model[m, 0.5], by_model[m, 2.0]
        lines.append(f"  {m}: times 0.5 changes {a:,} cells ({ai:,} to inline), times 2.0 changes {b:,} ({bi:,} to inline)")
    return lines


@pytest.fixture(scope="module")
def hand(ps, dr, tmp_path_factory):
    rows, registry = _rows(), Registry([P, D, E])
    root, matrix, pool = _root(tmp_path_factory.mktemp("hand"), dr, rows, registry)
    code, out, err = _main(ps, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    return rows, registry, root, matrix, pool, code, out, err


def test_report_on_a_hand_matrix_is_the_brute_force(dr, hand):
    rows, registry, _, _, _, code, out, err = hand
    assert (code, err) == (0, "")
    want = [TITLE] + _expected(rows, registry, dr, "base", "results.json") + _expected(rows, registry, dr, "variants",
                                                                                      "variants.json")
    assert out.split("\n") == want + [""]


def test_the_hand_matrix_moves_cells_both_ways_and_no_cost_blind_cell(hand):
    out = hand[6].split("\n")
    table = _table("\n".join(out))
    effective = [v for k, v in table.items() if k[1] == "cost_effective"]
    assert all(v["moving"] > 0 for v in effective)
    assert all(v["most"] == 0 and v["by"] is None for k, v in table.items() if k[1] == "cost_blind")
    base = [line for line in out[1:out.index(next(x for x in out if x.startswith("AutoBench 2026, variants")))]]
    changes = {m: (int(a), int(ai), int(b), int(bi)) for m, a, ai, b, bi in
               (re.match(MODEL_LINE, x).groups() for x in base if re.match(MODEL_LINE, x))}
    # the delegates' errors move work between delegates; the parent's moves it between the paths
    assert changes["v/d"][0] > 0 and changes["v/e"][2] > 0 and changes["v/d"][1] == changes["v/e"][3] == 0
    assert changes["v/p"][1] + changes["v/p"][3] > 0


@pytest.fixture(scope="module")
def lrb_hand(ps, lrb, tmp_path_factory):
    rows, registry = _lrb_rows(), Registry([P, D, E])
    root, matrix = _lrb_root(tmp_path_factory.mktemp("lrb"), lrb, rows, registry)
    code, out, err = _main(ps, ["--dataset", "llmrouterbench", "--matrix", str(matrix), "--root", str(root)])
    return rows, registry, root, matrix, code, out, err


def test_llmrouterbench_report_on_a_hand_matrix_is_the_brute_force(lrb, lrb_hand):
    rows, registry, _, _, code, out, err = lrb_hand
    assert (code, err) == (0, "")
    want = [LRB_TITLE] + _expected(_kept(rows, registry), registry, lrb, "base", "results.json", "LLMRouterBench",
                                   "evidence/llmrouterbench-delegation")
    assert out.split("\n") == want + [""]


def test_the_llmrouterbench_hand_matrix_moves_cells_of_both_tasks(lrb_hand):
    out = lrb_hand[5].split("\n")
    assert out[1].startswith("LLMRouterBench, base grid (`evidence/llmrouterbench-delegation/results.json`): "
                             "9,600 cells, 2 tasks, 4 bars, 2 flavors, 4 points, 3 parents, 50 seeds, 3 models, so 6 "
                             "runs; ")
    line = next(x for x in out if x.startswith("  changed cells by task, all 6 runs: "))
    counts = [x.rsplit(" ", 1) for x in line.split(": ", 1)[1].split(", ")]
    # the run's task order, as `evaluate_delegation` gives it, not the matrix's
    assert [t for t, _ in counts] == ["t", "u"] and all(int(n.replace(",", "")) > 0 for _, n in counts), line
    assert all(v["most"] == 0 for k, v in _table(lrb_hand[5]).items() if k[1] == "cost_blind")


@pytest.fixture(scope="module")
def rb_hand(ps, rb, tmp_path_factory):
    rows, registry = _lrb_rows(), Registry([P, D, E])
    root, matrix = _lrb_root(tmp_path_factory.mktemp("rb"), rb, rows, registry, RB)
    code, out, err = _main(ps, ["--dataset", "response-bank", "--matrix", str(matrix), "--root", str(root)])
    return rows, registry, root, matrix, code, out, err


def test_response_bank_report_on_a_hand_matrix_is_the_brute_force(rb, rb_hand):
    rows, registry, _, _, code, out, err = rb_hand
    assert (code, err) == (0, "")
    want = [RB_TITLE] + _expected(_kept(rows, registry), registry, rb, "base", "results.json",
                                  "LLM Routing Response Bank", "evidence/response-bank-delegation")
    assert out.split("\n") == want + [""]


def test_the_response_bank_hand_matrix_moves_cells_of_both_tasks(rb_hand):
    out = rb_hand[5].split("\n")
    assert out[1].startswith("LLM Routing Response Bank, base grid (`evidence/response-bank-delegation/results.json`): "
                             "4,800 cells, 2 tasks, 2 bars, 2 flavors, 4 points, 3 parents, 50 seeds, 3 models, so 6 "
                             "runs; ")
    line = next(x for x in out if x.startswith("  changed cells by task, all 6 runs: "))
    counts = [x.rsplit(" ", 1) for x in line.split(": ", 1)[1].split(", ")]
    assert [t for t, _ in counts] == ["t", "u"] and all(int(n.replace(",", "")) > 0 for _, n in counts), line
    table = _table(rb_hand[5])
    assert all(v["moving"] > 0 for k, v in table.items() if k[1] == "cost_effective")
    assert all(v["most"] == 0 for k, v in table.items() if k[1] == "cost_blind")


def _call_row(task, item, model, correct, a, b):
    """A 13.9 v1.74 per-call row whose counts are what its calls read and write."""
    k = len(a)
    return {"task": task, "item": item, "model": model, "correct": correct,
            "input_tokens": sum((k - j) * a[j] + (k - j - 1) * b[j] for j in range(k)),
            "output_tokens": sum(b), "call_input_tokens": list(a), "call_output_tokens": list(b)}


def _t2_rows(pooled=False):
    """Three tasks, `u`, `t` and `s`, or with `pooled` the same rows as one task `all`, items named `task|j` as the
    tau2-bench converter names them `domain|id`. On `u` and `t` each model writes `_lrb_rows`' outputs in one call,
    a = [100], b = [o], except v/d, which writes 50 in each of two calls on j % 5 == 0; on `s` every model writes in
    two calls, a = [100, 0], so that task's median call count is 2 and the decision's `work_calls` is above one,
    while pooled it stays 1."""
    rows = []
    for task, base, step, mod in (("u", 1200, 40, 11), ("t", 1050, 10, 7), ("s", 600, 20, 5)):
        for j in range(80):
            item, name, o, two = f"{task}|{j:02d}", "all" if pooled else task, base + step * (j % mod), task == "s"
            rows.append(_call_row(name, item, "v/p", j % 10 != 0, *(([100, 0], [o, o]) if two else ([100], [o]))))
            rows.append(_call_row(name, item, "v/d", j % 20 != 0,
                                  *(([100, 0], [50, 50]) if two or j % 5 == 0 else ([100], [100]))))
            e = ([100, 0], [55, 55 + 10 * (j % 3)]) if two else ([100], [110 + 10 * (j % 3)])
            rows.append(_call_row(name, item, "v/e", j % 8 != 3, *e))
    return rows


def _t2_root(tmp_path, t2, rows, registry, name):
    """A root whose committed 13.12 file `name` (results.json or pooled.json) is the run on `rows`; the 13.12 script
    reads the base points from the 13.10 script, so that is copied too."""
    root = tmp_path / "root"
    for source in (FOLDER, T2):
        folder = root / "evidence" / source.name
        folder.mkdir(parents=True)
        (folder / "results.py").write_text((source / "results.py").read_text(encoding="utf-8"), encoding="utf-8")
    folder = root / "evidence" / T2.name
    _registry_file(folder / "registry.json", registry)
    (folder / name).write_text(json.dumps(t2.run(rows, registry), indent=2) + "\n", encoding="utf-8")
    matrix = tmp_path / "t2.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return root, matrix


T2_RUNS = {"tau2-bench": (False, "results.json", "tau2-bench per domain"),
           "tau2-bench-pooled": (True, "pooled.json", "tau2-bench pooled")}


@pytest.fixture(scope="module", params=sorted(T2_RUNS))
def t2_hand(ps, t2, tmp_path_factory, request):
    pooled, name, _title = T2_RUNS[request.param]
    rows, registry = _t2_rows(pooled), Registry([P, D, E])
    root, matrix = _t2_root(tmp_path_factory.mktemp("t2"), t2, rows, registry, name)
    code, out, err = _main(ps, ["--dataset", request.param, "--matrix", str(matrix), "--root", str(root)])
    return request.param, rows, registry, root, matrix, code, out, err


def test_tau2_report_on_a_hand_matrix_is_the_brute_force(t2, t2_hand):
    dataset, rows, registry, _, _, code, out, err = t2_hand
    assert (code, err) == (0, "")
    _, name, title = T2_RUNS[dataset]
    want = [TITLE.replace("AutoBench 2026", title)]
    want += _expected(rows, registry, t2, "base", name, title, "evidence/tau2-bench-delegation", per_call=True)
    assert out.split("\n") == want + [""]


def test_the_tau2_hand_matrix_moves_cells_at_every_bar_and_no_cost_blind_cell(t2_hand):
    dataset, *_, out, _err = t2_hand
    table = _table(out)
    assert sorted({k[2] for k in table}) == ["0.3", "0.4", "0.5", "0.6", "0.7", "0.8"]
    assert all(v["most"] > 0 for k, v in table.items() if k[1] == "cost_effective")
    assert all(v["moving"] == 0 and v["most"] == 0 for k, v in table.items() if k[1] == "cost_blind")
    if dataset == "tau2-bench":
        line = next(x for x in out.split("\n") if x.startswith("  changed cells by task, all 6 runs: "))
        counts = dict(x.rsplit(" ", 1) for x in line.split(": ", 1)[1].split(", "))
        assert list(counts) == ["s", "t", "u"] and all(int(n.replace(",", "")) > 0 for n in counts.values()), line
        # the parent's error moves cells between the paths
        assert sum(c[1] + c[3] for c in _grids(out)["base"][1].values()) > 0


def test_the_tau2_hand_matrix_forecasts_two_work_calls_on_one_task():
    """The calibration half's median call count over the three models' rows: 2 on `s` and 1 on `t`, `u` and pooled,
    on every seed, so the hand run checks a decision's `work_calls` above one."""
    for pooled, want in ((False, {"s": {2}, "t": {1}, "u": {1}}), (True, {"all": {1}})):
        rows = _t2_rows(pooled)
        got = {}
        for task in dict.fromkeys(r["task"] for r in rows):
            mine = [r for r in rows if r["task"] == task]
            items = list(dict.fromkeys(r["item"] for r in mine))
            for seed in range(50):
                cal = set(split_items(items, seed, 0.5)[0])
                got.setdefault(task, set()).add(statistics.median_low(
                    [len(r["call_input_tokens"]) for r in mine if r["item"] in cal]))
        assert got == want, pooled


def test_a_hand_matrix_run_moves_a_committed_inline_cell_to_a_delegate(ps, lrb_hand):
    """The report counts the changed cells whose new mode is inline; this checks the other way round on the hand
    matrix, from `picks` itself (review iter-285 nit 8)."""
    _, _, root, matrix = lrb_hand[:4]
    title, files, dr13, rows, pool = ps.RS.inputs(matrix, None, root, "llmrouterbench")
    run, got, _rel = ps.RS.checked(rows, pool, root, "results.json", "base", dr13, "llmrouterbench")
    cells = run.result["cells"]
    moves = {}
    for m in run.models:
        for f in FACTORS:
            new = ps.picks(run, got["config"], ps.scaled(pool, m, f))
            moves[m, f] = sum(c["mode"] == "inline" and pick[0] == "delegate" for c, pick in zip(cells, new))
    assert all(moves[m, 0.5] > 0 for m in ("v/d", "v/e")) and moves["v/p", 2.0] > 0, moves


def test_the_most_names_the_first_tied_run_in_model_then_factor_order(ps, hand, monkeypatch):
    """A stub `picks` sends the same three `cost_effective` bar 0.7 cells inline in the runs v/d times 2.0 and v/e
    times 0.5, and two of them in v/p times 0.5, so two runs tie for the most; `by` names v/d times 2.0, the first in
    model, then factor, order, where the last tied run or a factor-first order would name v/e times 0.5."""
    _, _, root, matrix, pool = hand[:5]
    title, _files, dr10, rows, registry = ps.RS.inputs(matrix, pool, root, "autobench")
    flips = {("v/d", 2.0): 3, ("v/e", 0.5): 3, ("v/p", 0.5): 2}

    def stub(run, config, scaled):
        moved = [m.id for m in scaled.models if m != run.registry.get(m.id)]
        assert len(moved) == 1
        factor = scaled.get(moved[0]).price_in / run.registry.get(moved[0]).price_in
        left = flips.get((moved[0], factor), 0)
        out = []
        for c in run.result["cells"]:
            pick = (c["mode"], c["model"])
            if left and (c["flavor"], c["bar"]) == ("cost_effective", 0.7) and pick != ("inline", c["parent"]):
                pick, left = ("inline", c["parent"]), left - 1
            out.append(pick)
        assert left == 0
        return out

    monkeypatch.setattr(ps, "picks", stub)
    lines = ps.report(rows, registry, root, "results.json", "base", dr10, title)
    row = _table("\n".join(lines))["base", "cost_effective", "0.7"]
    assert (row["moving"], row["runs"], row["most"], row["inline"], row["by"]) == (3, 6, 3, 3, ["v/d", "2.0"])
    assert _table("\n".join(lines))["base", "cost_effective", "0.8"]["by"] is None
    per_model = _grids("\n".join(lines))["base"][1]
    assert per_model == {"v/d": (0, 0, 3, 3), "v/e": (3, 3, 0, 0), "v/p": (2, 2, 0, 0)}


def test_the_dataset_and_registry_options_exit_2_together(ps, hand, lrb_hand, rb_hand, t2, tmp_path):
    _, _, root, matrix, pool = hand[:5]
    code, out, err = _main(ps, ["--matrix", str(matrix), "--root", str(root)])
    assert (code, out, err) == (2, "", "error: --dataset autobench needs --registry\n")
    _, _, l_root, l_matrix = lrb_hand[:4]
    code, out, err = _main(ps, ["--dataset", "llmrouterbench", "--matrix", str(l_matrix), "--registry", str(pool),
                                "--root", str(l_root)])
    assert (code, out, err) == (2, "", "error: --registry is only used with --dataset autobench\n")
    _, _, r_root, r_matrix = rb_hand[:4]
    code, out, err = _main(ps, ["--dataset", "response-bank", "--matrix", str(r_matrix), "--registry", str(pool),
                                "--root", str(r_root)])
    assert (code, out, err) == (2, "", "error: --registry is only used with --dataset autobench\n")
    t_root, t_matrix = _t2_root(tmp_path, t2, _t2_rows(), Registry([P, D, E]), "results.json")
    for dataset in ("tau2-bench", "tau2-bench-pooled"):
        code, out, err = _main(ps, ["--dataset", dataset, "--matrix", str(t_matrix), "--registry", str(pool),
                                    "--root", str(t_root)])
        assert (code, out, err) == (2, "", "error: --registry is only used with --dataset autobench\n")
    # pooled.json is absent from this root, and a matrix without per-call sizes is refused as the re-read check does
    code, out, err = _main(ps, ["--dataset", "tau2-bench-pooled", "--matrix", str(t_matrix), "--root", str(t_root)])
    assert (code, out, err) == (2, "", f"error: {t_root / 'evidence' / T2.name / 'pooled.json'}: no such file\n")
    code, out, err = _main(ps, ["--dataset", "tau2-bench", "--matrix", str(matrix), "--root", str(t_root)])
    assert (code, out, err) == (2, "", "error: task 't': rows without per-call sizes are not priced here\n")
    with pytest.raises(ValueError, match="^dataset must be one of autobench, llmrouterbench, response-bank, "
                                         "tau2-bench, tau2-bench-pooled, got 'routerbench'$"):
        ps.run(l_matrix, None, l_root, "routerbench")
    assert ps.DATASETS == ("autobench", "llmrouterbench", "response-bank", "tau2-bench", "tau2-bench-pooled")


def test_scaled_changes_one_models_prices_only(ps):
    registry = Registry([P, D, dataclasses.replace(E, aliases={"x": "e"}, price_valid_until="2026-12-01")])
    for factor in FACTORS:
        got = ps.scaled(registry, "v/e", factor)
        assert [m.id for m in got.models] == ["v/p", "v/d", "v/e"]
        assert got.get("v/p") == P and got.get("v/d") == D
        assert got.get("v/e") == dataclasses.replace(registry.get("v/e"), price_in=0.8 * factor, price_out=0.8 * factor)


def test_exits_2_where_the_reread_check_does(ps, dr, tmp_path):
    root, matrix, pool = _root(tmp_path, dr, _rows(), Registry([P, D, E]))
    path = root / "evidence" / "delegation" / "variants.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["summary"][0]["cost_usd"] *= 2
    path.write_text(json.dumps(data), encoding="utf-8")
    code, out, err = _main(ps, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    assert (code, out, err) == (2, "", "error: evidence/delegation/variants.json: the run's summary is not the committed one\n")
    code, out, err = _main(ps, ["--matrix", str(tmp_path / "none.jsonl"), "--registry", str(pool), "--root", str(root)])
    assert (code, out, err) == (2, "", f"error: {tmp_path / 'none.jsonl'}: no such file\n")


def test_script_is_standard_library_and_model_routing():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^\s*(?:from|import) (\S+)", text, flags=re.M)}
    assert imports == {"argparse", "dataclasses", "importlib", "sys", "math", "pathlib", "model_routing"}
    assert '"reread_sensitivity.py"' in text


# --- the note --------------------------------------------------------------------------------
TABLE_LINE = (r"  (cost_\w+) +(0\.\d) +(\d+) / (\d+) +([\d,]+) / ([\d,]+) +([\d.]+)% +([\d,]+) +(\S+) +(\S+) +(\S+)  "
              r"(-|\S+ times (?:0\.5|2\.0))$")
MODEL_LINE = r"  (\S+): times 0\.5 changes ([\d,]+) cells \(([\d,]+) to inline\), times 2\.0 changes ([\d,]+) \(([\d,]+) to inline\)$"
GRID_LINE = (r"(?:AutoBench 2026|LLMRouterBench|LLM Routing Response Bank|tau2-bench per domain|tau2-bench pooled), "
             r"(base|variants) grid \(`evidence/[\w-]+/\w+\.json`\): ([\d,]+) "
             r"cells, (?:\d+ tasks, )?(\d+) bars, (\d+) flavors, (\d+) points, (\d+) parents, (\d+) seeds, (\d+) "
             r"models, so (\d+) runs; ")
TASK_LINE = r"  changed cells by task, all \d+ runs: (.+)$"
POINT_LINE = r"  changed cells by point, all \d+ runs: (.+)$"


def _section(note, name):
    return note.split(f"\n## {name}\n", 1)[1].split("\n## ", 1)[0]


def _prose(note):
    return re.sub(r"```.*?```", "", note, flags=re.S)


def _block(note, command=COMMAND):
    return note.split(command + "\n", 1)[1].split("\n```", 1)[0]


def _table(block):
    """{(grid, flavor, bar): the row's values}, the grid as the header line names it."""
    rows, grid = {}, None
    for line in block.split("\n"):
        found = re.match(GRID_LINE, line)
        if found:
            grid = found.group(1)
        found = re.match(TABLE_LINE, line)
        if found:
            f, bar, moving, runs, most, cells, share, inline, gap, ratio, whole, by = found.groups()
            rows[grid, f, bar] = {"moving": int(moving), "runs": int(runs), "most": most, "cells": cells,
                                  "share": share, "inline": int(inline.replace(",", "")), "gap": gap, "ratio": ratio,
                                  "all": whole, "by": None if by == "-" else by.rsplit(" times ", 1)}
            rows[grid, f, bar]["most"] = int(most.replace(",", ""))
            rows[grid, f, bar]["most_text"] = most
    return rows


def _grids(block):
    """{grid: (header values, {model: (halved, halved to inline, doubled, doubled to inline)})}."""
    out, grid = {}, None
    for line in block.split("\n"):
        found = re.match(GRID_LINE, line)
        if found:
            grid = found.group(1)
            out[grid] = (found.groups()[1:], {})
        found = re.match(MODEL_LINE, line)
        if found:
            out[grid][1][found.group(1)] = tuple(int(x.replace(",", "")) for x in found.groups()[1:])
    return out


def _verb(factor):
    return {"0.5": "halving", "2.0": "doubling"}[factor]


def _inline(n):
    return "none to inline" if n == 0 else f"{n:,} of them to inline"


def _bar_parts(table, grid, bars):
    """One clause per `cost_effective` bar: the runs that move a cell and the run that moves the most."""
    parts = []
    for bar in bars:
        v = table[grid, "cost_effective", bar]
        model, factor = v["by"]
        parts.append(f"at bar {bar} {v['moving']} of the {v['runs']} runs move a cell, and the most, "
                     f"{_verb(factor)} `{model}`'s prices, moves {v['most_text']} of {v['cells']} cells "
                     f"({v['share']}%), {_inline(v['inline'])}, for a held-out success gap of {v['gap']} at "
                     f"{v['ratio']} times their cost and {v['all']} times the cost over all the bar's cells")
    return parts


def lrb_facts(note):
    """The LLMRouterBench Facts bullets, built from the note's LLMRouterBench block; the claims of its Reading it
    bullet are checked on the way."""
    block = _block(note, LRB_COMMAND)
    table, grids = _table(block), _grids(block)
    bars = sorted({k[2] for k in table})
    assert set(grids) == {"base"} and len(table) == 2 * len(bars) and bars == ["0.1", "0.3", "0.5", "0.8"]
    assert all(v["moving"] == 0 and v["most"] == 0 for k, v in table.items() if k[1] == "cost_blind")
    (cells, b, flavors, points, parents, seeds, models, runs), by_model = grids["base"]
    assert int(b) == len(bars) and int(runs) == 2 * int(models)
    tasks = re.search(r" cells, (\d+) tasks, ", block).group(1)
    by_task = [x.rsplit(" ", 1) for x in re.search(TASK_LINE, block, flags=re.M).group(1).split(", ")]
    by_task = {t: int(n.replace(",", "")) for t, n in by_task}
    assert len(by_task) == int(tasks)
    out = [f"- LLMRouterBench data: the rows and registry that evidence/llmrouterbench-delegation/results.py runs, its "
           f"one grid ({cells} cells: {tasks} tasks, {b} bars, {flavors} flavors, {points} points, {parents} parents, "
           f"{seeds} seeds), with the {models} models of its registry, each model's input and output prices times 0.5 "
           f"and times 2.0 in turn, so {runs} runs; every cell's decision and held-out sum is reproduced at the "
           "committed prices before any price is scaled"]
    out.append("- LLMRouterBench, `cost_effective`: " + "; ".join(_bar_parts(table, "base", bars)))
    moved = [m for m, c in by_model.items() if c[0] or c[2]]
    who = (f"every one of the {models} models moves a cell at one factor or the other" if len(moved) == int(models)
           else f"{len(moved)} of the {models} models move a cell at one factor or the other and "
                f"{int(models) - len(moved)} move none at either")
    totals = sorted(((c[i], m, f) for m, c in by_model.items() for i, f in ((0, "0.5"), (2, "2.0"))),
                    key=lambda x: (-x[0], x[1], x[2]))
    changed = sum(c[0] + c[2] for c in by_model.values())
    inline = sum(c[1] + c[3] for c in by_model.values())
    ranked = sorted(by_task.items(), key=lambda kv: (-kv[1], kv[0]))
    by_point = [int(x.split(": ")[1].replace(",", "")) for x in
                re.search(POINT_LINE, block, flags=re.M).group(1).split(", ")]
    assert changed == sum(by_task.values()) == sum(by_point) and len(by_point) == int(points)
    some = "every task has changed cells" if ranked[-1][1] else f"{sum(n > 0 for _, n in ranked)} of the {tasks} tasks have changed cells"
    out.append(f"- LLMRouterBench by model and task: {who}; over every flavor and bar the runs that move the most are "
               f"{_verb(totals[0][2])} `{totals[0][1]}`'s prices ({totals[0][0]:,} cells) and {_verb(totals[1][2])} "
               f"`{totals[1][1]}`'s ({totals[1][0]:,}); of the {changed:,} cells its runs change, {inline:,} go inline; "
               f"{some}, {ranked[0][0]} the most ({ranked[0][1]:,}) and {ranked[-1][0]} the fewest ({ranked[-1][1]:,})")
    # Reading it: the share the top run moves falls as the bar rises, the moved picks cost more at every bar, the
    # success gap's sign varies, and over all of a bar's cells the cost rises by a few thousandths at most, far less
    # than on AutoBench, where each cost_effective bar's top run raises it too
    rows = [table["base", "cost_effective", bar] for bar in bars]
    assert [r["most"] for r in rows] == sorted((r["most"] for r in rows), reverse=True)
    assert all(float(r["ratio"]) > 1 for r in rows)
    assert {r["gap"][0] for r in rows} == {"+", "-"}
    lrb_all = [float(r["all"]) for r in rows]
    ab = _table(_block(note))
    ab_all = [float(v["all"]) for k, v in ab.items() if k[1] == "cost_effective"]
    assert all(x > 1 for x in lrb_all + ab_all) and max(lrb_all) - 1 < (min(ab_all) - 1) / 4
    # the Recommendation: on LLMRouterBench the bill moves about as little as the re-read note's inputs move it
    # there, every all-cells ratio of both within 0.01 of 1, while on AutoBench it rises far more than they move it
    # (review iter-286 should-fix 1)
    reread = REREAD.read_text(encoding="utf-8")
    moved = {}
    for command in (REREAD_COMMAND, REREAD_LRB_COMMAND):
        rows_ = [line.split() for line in _block(reread, command).split("\n") if line.startswith("  cost_")]
        assert rows_, command
        moved[command] = [abs(float(r[-1]) - 1) for r in rows_]
    assert max(lrb_all) - 1 < 0.01 and max(moved[REREAD_LRB_COMMAND]) < 0.01
    assert min(ab_all) - 1 > 4 * max(moved[REREAD_COMMAND])
    return out


def _changed_at(block, label, bar):
    """A re-read note block's `cost_effective` changed cells at one setting and bar."""
    for line in block.split("\n"):
        if line.startswith(f"  cost_effective  {bar}  {label} "):
            return int(line[len(f"  cost_effective  {bar}  {label} "):].split()[0].replace(",", ""))
    raise AssertionError((label, bar))


def rb_facts(note):
    """The Response Bank Facts bullets, built from the note's Response Bank block; the claims the Facts, Reading it
    and Recommendation make about it are checked on the way, against the other two blocks and the re-read note's
    Response Bank block."""
    block = _block(note, RB_COMMAND)
    table, grids = _table(block), _grids(block)
    bars = sorted({k[2] for k in table})
    assert set(grids) == {"base"} and len(table) == 2 * len(bars) and bars == ["0.8", "0.9"]
    assert all(v["moving"] == 0 and v["most"] == 0 for k, v in table.items() if k[1] == "cost_blind")
    (cells, b, flavors, points, parents, seeds, models, runs), by_model = grids["base"]
    assert int(b) == len(bars) and int(runs) == 2 * int(models)
    tasks = re.search(r" cells, (\d+) tasks, ", block).group(1)
    by_task = [x.rsplit(" ", 1) for x in re.search(TASK_LINE, block, flags=re.M).group(1).split(", ")]
    by_task = {t: int(n.replace(",", "")) for t, n in by_task}
    by_point = [int(x.split(": ")[1].replace(",", "")) for x in
                re.search(POINT_LINE, block, flags=re.M).group(1).split(", ")]
    moved = [m for m, c in by_model.items() if c[0] or c[2]]
    counts = [c[i] for c in by_model.values() for i in (0, 2) if c[i]]
    changed, inline = sum(counts), sum(c[1] + c[3] for c in by_model.values())
    some, none = [t for t, n in by_task.items() if n], [t for t, n in by_task.items() if not n]
    # the Facts and Reading it claims: some models move no cell, the runs that move a cell each change the same
    # number, all of one task, at every point, none of them inline
    assert len(by_task) == int(tasks) and len(by_point) == int(points)
    assert 0 < len(moved) < int(models) and len(set(counts)) == 1 and len(some) == 1 and inline == 0
    assert changed == sum(by_task.values()) == sum(by_point) and all(n > 0 for n in by_point)
    out = [f"- Response Bank data: the rows and registry that evidence/response-bank-delegation/results.py runs, its "
           f"one grid ({cells} cells: {tasks} tasks, {b} bars, {flavors} flavors, {points} points, {parents} parents, "
           f"{seeds} seeds), with the {models} models of its registry, each model's input and output prices times 0.5 "
           f"and times 2.0 in turn, so {runs} runs; every cell's decision and held-out sum is reproduced at the "
           "committed prices before any price is scaled"]
    out.append("- Response Bank, `cost_effective`: " + "; ".join(_bar_parts(table, "base", bars)))
    out.append(f"- Response Bank by model and task: {len(moved)} of the {models} models move a cell at one factor or "
               f"the other and {int(models) - len(moved)} move none at either; {len(counts)} of the {runs} runs move a "
               f"cell, each {counts[0]:,} cells over every flavor and bar, so {changed:,} in all, none of them inline; "
               f"only {some[0]} has changed cells, and {', '.join(none[:-1])} and {none[-1]} have none")
    # Reading it: at each bar the run that moves the most sends the work to picks that cost more and are right less
    # often, far fewer cells than on the other two datasets, and a zero re-read share moves more cells than it does;
    # the Recommendation: the bill over all the bar's cells is unchanged at the block's three decimals
    rows = [table["base", "cost_effective", bar] for bar in bars]
    assert all(r["gap"].startswith("-") and float(r["ratio"]) > 1 and r["all"] == "1.000" for r in rows)
    others = [v for command in (COMMAND, LRB_COMMAND) for k, v in _table(_block(note, command)).items()
              if k[1] == "cost_effective"]
    assert 4 * max(float(r["share"]) for r in rows) < min(float(v["share"]) for v in others)
    reread = _block(REREAD.read_text(encoding="utf-8"), REREAD_RB_COMMAND)
    assert all(_changed_at(reread, "sigma 0", bar) > table["base", "cost_effective", bar]["most"] for bar in bars)
    return out


def t2_facts(note):
    """The tau2-bench Facts bullets, built from the note's two tau2-bench blocks; the claims the Facts, Reading it and
    Recommendation make about them are checked on the way, against the other blocks and the re-read note's
    tau2-bench blocks."""
    blocks = {"per domain": _block(note, T2_COMMAND), "pooled": _block(note, T2_POOLED_COMMAND)}
    tables = {k: _table(b) for k, b in blocks.items()}
    grids = {k: _grids(b) for k, b in blocks.items()}
    bars = ["0.3", "0.4", "0.5", "0.6", "0.7", "0.8"]
    head = {}
    for k in blocks:
        assert set(grids[k]) == {"base"} and sorted({x[2] for x in tables[k]}) == bars and len(tables[k]) == 12
        assert all(v["moving"] == 0 and v["most"] == 0 for x, v in tables[k].items() if x[1] == "cost_blind")
        head[k] = grids[k]["base"][0]
        assert int(head[k][1]) == len(bars) and int(head[k][7]) == 2 * int(head[k][6])
    (cells, b, flavors, points, parents, seeds, models, runs), (p_cells, *_rest) = head["per domain"], head["pooled"]
    assert head["pooled"][1:] == head["per domain"][1:]
    tasks = re.search(r" cells, (\d+) tasks, ", blocks["per domain"]).group(1)
    assert re.search(r" cells, \d+ tasks, ", blocks["pooled"]) is None
    out = [f"- tau2-bench data: the rows and registry that evidence/tau2-bench-delegation/results.py runs, its grid per "
           f"domain ({cells} cells: {tasks} tasks, {b} bars, {flavors} flavors, {points} points, {parents} parents, "
           f"{seeds} seeds) and pooled ({p_cells} cells, one task), with the {models} models of its registry, each "
           f"model's input and output prices times 0.5 and times 2.0 in turn, so {runs} runs per grid; each held-out "
           "item is priced call by call from its per-call sizes, and every cell's decision and held-out sum is "
           "reproduced at the committed prices before any price is scaled"]
    for k in blocks:
        still = [bar for bar in bars if tables[k]["base", "cost_effective", bar]["by"] is None]
        moving = [bar for bar in bars if bar not in still]
        lead = (f"at bars {', '.join(still[:-1])} and {still[-1]} no run moves a cell; " if len(still) > 1 else
                f"at bar {still[0]} no run moves a cell; " if still else "")
        out.append(f"- tau2-bench {k}, `cost_effective`: " + lead + "; ".join(_bar_parts(tables[k], "base", moving)))
    by_task = [x.rsplit(" ", 1) for x in re.search(TASK_LINE, blocks["per domain"], flags=re.M).group(1).split(", ")]
    by_task = {t: int(n.replace(",", "")) for t, n in by_task}
    assert len(by_task) == int(tasks)
    movers = {}
    for k in blocks:
        by_model = grids[k]["base"][1]
        movers[k] = sorted((m, f, c[i]) for m, c in by_model.items() for i, f in ((0, "0.5"), (2, "2.0")) if c[i])
        assert sum(c[1] + c[3] for c in by_model.values()) == 0
        by_point = [int(x.split(": ")[1].replace(",", "")) for x in
                    re.search(POINT_LINE, blocks[k], flags=re.M).group(1).split(", ")]
        assert sum(n for *_x, n in movers[k]) == sum(by_point) and len(by_point) == int(points)
    # the same two runs move cells per domain and pooled, each the same count, and the third model moves none
    assert [(m, f) for m, f, _ in movers["per domain"]] == [(m, f) for m, f, _ in movers["pooled"]]
    assert len(movers["pooled"]) == 2 and all(len({n for *_x, n in movers[k]}) == 1 for k in blocks)
    (m1, f1, n1), (m2, f2, n2) = movers["per domain"]
    # Reading it: halving the first model's prices or doubling the second's, so each makes the first look cheaper
    # against the second; cells move at every bar per domain and at all but the two lowest pooled
    assert (f1, f2) == ("0.5", "2.0")
    assert [bar for bar in bars if tables["per domain"]["base", "cost_effective", bar]["by"] is None] == []
    assert [bar for bar in bars if tables["pooled"]["base", "cost_effective", bar]["by"] is None] == bars[:2]
    rest = sorted(set(grids["per domain"]["base"][1]) - {m1, m2})
    assert len(rest) == 1 and sum(by_task.values()) == 2 * n1
    some = sorted(((t, n) for t, n in by_task.items() if n), key=lambda kv: (-kv[1], kv[0]))
    none = [t for t, n in by_task.items() if not n]
    assert len(some) == 2 and len(none) == 1
    out.append(f"- tau2-bench by model and task: per domain and pooled 2 of the {models} models move a cell, "
               f"{_verb(f1)} `{m1}`'s prices or {_verb(f2)} `{m2}`'s, each run the same number of cells "
               f"({n1:,} per domain, {movers['pooled'][0][2]:,} pooled), and `{rest[0]}` moves none at either factor; "
               f"none of the changed cells go inline; per domain {some[0][0]} has the most changed cells "
               f"({some[0][1]:,}), {some[1][0]} {some[1][1]:,} and {none[0]} none")
    # Reading it and the Recommendation: on tau2-bench, where the re-read note moves no cell, the run that moves the
    # most at each bar where one does sends the work to delegated picks that cost more than twice as much at the
    # list price, the bill over all the bar's cells rising by more than on LLMRouterBench; per domain the success
    # gap's sign varies, pooled the moved picks are right more often; per domain it moves up to about a fifth of a
    # bar's cells
    rows = {k: [tables[k]["base", "cost_effective", bar] for bar in bars if tables[k]["base", "cost_effective", bar]["by"]]
            for k in blocks}
    lrb_all = [float(v["all"]) for x, v in _table(_block(note, LRB_COMMAND)).items() if x[1] == "cost_effective"]
    for k in blocks:
        assert all(float(r["ratio"]) > 2 and float(r["all"]) > max(lrb_all) for r in rows[k])
    assert {r["gap"][0] for r in rows["per domain"]} == {"+", "-"} and {r["gap"][0] for r in rows["pooled"]} == {"+"}
    assert 15 < max(float(r["share"]) for r in rows["per domain"]) < 25
    reread = REREAD.read_text(encoding="utf-8")
    for command in REREAD_T2_COMMANDS:
        block = _block(reread, command)
        moved = [line.split() for line in block.split("\n") if line.startswith("  cost_")]
        assert len(moved) == 36 and all(r[r.index("/") - 1] == "0" for r in moved), command
    return out


def facts(note):
    """The Facts bullets that hold numbers, built from the note's Results blocks."""
    block = _block(note)
    table, grids = _table(block), _grids(block)
    assert set(grids) == {"base", "variants"} and len(table) == 8
    # no run moves a cost_blind cell, on either grid or bar
    assert all(v["moving"] == 0 and v["most"] == 0 for k, v in table.items() if k[1] == "cost_blind")
    (cells, bars, flavors, points, parents, seeds, models, runs), _ = grids["base"]
    (v_cells, _b, _f, v_points, _p, _s, v_models, v_runs), _ = grids["variants"]
    assert (models, runs) == (v_models, v_runs) and int(runs) == 2 * int(models)
    out = [f"- AutoBench data: the AutoBench 2026 matrix and pool that evidence/delegation/results.py runs, its base grid "
           f"({cells} cells: {bars} bars, {flavors} flavors, {points} points, {parents} parents, {seeds} seeds) and its "
           f"variant grid ({v_cells} cells, {v_points} points), with the {models} models of the pool, each model's "
           f"input and output prices times 0.5 and times 2.0 in turn, so {runs} runs per grid; every cell's decision "
           "and held-out sum is reproduced at the committed prices before any price is scaled"]
    for grid, name in (("base", "AutoBench base grid"), ("variants", "AutoBench variant grid")):
        out.append(f"- {name}, `cost_effective`: " + "; ".join(_bar_parts(table, grid, ("0.7", "0.8"))))
    by_model = grids["base"][1]
    moved = [m for m, c in by_model.items() if c[0] or c[2]]
    v_moved = [m for m, c in grids["variants"][1].items() if c[0] or c[2]]
    totals = sorted(((c[i], m, f) for m, c in by_model.items() for i, f in ((0, "0.5"), (2, "2.0"))),
                    key=lambda x: (-x[0], x[1], x[2]))
    inline = sum(c[1] + c[3] for c in by_model.values())
    changed = sum(c[0] + c[2] for c in by_model.values())
    v_inline = sum(c[1] + c[3] for c in grids["variants"][1].values())
    v_changed = sum(c[0] + c[2] for c in grids["variants"][1].values())
    out.append(f"- AutoBench by model: {len(moved)} of the {models} models move a base-grid cell at one factor or the other "
               f"and {int(models) - len(moved)} move none at either; on the variant grid {len(v_moved)} move a cell. "
               f"Over every flavor and bar of the base grid the runs that move the most are {_verb(totals[0][2])} "
               f"`{totals[0][1]}`'s prices ({totals[0][0]:,} cells) and {_verb(totals[1][2])} `{totals[1][1]}`'s "
               f"({totals[1][0]:,})")
    out.append(f"- On AutoBench, of the {changed:,} cells the base grid's runs change, {inline:,} go inline; of the variant grid's "
               f"{v_changed:,}, {v_inline:,}; the rest go to a delegated pick")
    return out + lrb_facts(note) + rb_facts(note) + t2_facts(note)


def test_note_has_its_sections_command_and_regenerate():
    note = NOTE.read_text(encoding="utf-8")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == SECTIONS
    for command in (COMMAND, LRB_COMMAND, RB_COMMAND, T2_COMMAND, T2_POOLED_COMMAND):
        assert _section(note, "Results").count("```text\n" + command + "\n") == 1, command
    assert "```bash\n" + "\n".join(REGENERATE) + "\n```" in _section(note, "Regenerate")
    for link in ("../evidence/delegation/RESULTS.md", "../evidence/llmrouterbench-delegation/RESULTS.md",
                 "../evidence/response-bank-delegation/RESULTS.md", "../evidence/tau2-bench-delegation/RESULTS.md",
                 "price-sensitivity.md", "reread-sensitivity.md", "delegation_price_sensitivity.py"):
        assert f"]({link})" in note, link


def test_facts_states_the_finding_before_any_number():
    first = _section(NOTE.read_text(encoding="utf-8"), "Facts").strip().split("\n")[0]
    assert first.startswith("- ") and NUMBER.findall(first) == [], first


def test_the_facts_bullets_are_built_from_the_block():
    note = NOTE.read_text(encoding="utf-8")
    bullets = _section(note, "Facts").strip().split("\n")
    for bullet in facts(note):
        assert bullet in bullets, bullet


def test_every_number_of_the_prose_is_in_a_built_bullet_or_allowed():
    """Outside the built bullets the prose holds no result: only DESIGN section numbers, the exit status, and the
    block's parameters (its title's dataset year and factors, and its bars); a code span is a name, not a number."""
    note = NOTE.read_text(encoding="utf-8")
    parameters = set()
    for command in (COMMAND, LRB_COMMAND, RB_COMMAND, T2_COMMAND, T2_POOLED_COMMAND):
        block = _block(note, command)
        parameters |= set(NUMBER.findall(block.split("\n", 1)[0])) | {k[2] for k in _table(block)}
    assert parameters == {"2026", "0.1", "0.3", "0.4", "0.5", "0.6", "2.0", "0.7", "0.8", "0.9"}
    prose = _prose(note)
    for bullet in facts(note):
        assert prose.count(bullet) == 1, bullet
        prose = prose.replace(bullet, "")
    prose = re.sub(r"`[^`]*`", "", prose)
    assert sorted({n for n in NUMBER.findall(prose) if n not in ALLOWED | parameters | {"2"}}) == []
    assert re.findall(r"(?<![\w.])2(?![\w.])", prose) == ["2"] and "the script exits 2" in prose


def test_the_note_says_no_cost_blind_cell_moves_and_how_picks_are_scored():
    note = NOTE.read_text(encoding="utf-8")
    # the block counts the changed cells that go inline, not those that were inline before, so a delegated new
    # pick is not said to be another delegate; and no committed file holds per-delegate cell counts
    # (review iter-285 should-fix 1 and 2)
    assert "another delegate" not in note and "cells in evidence/delegation/results.json" not in note
    # the bill rises far more than the re-read inputs move it on AutoBench only (review iter-286 should-fix 1)
    assert "raises the bill, far more than" not in note
    assert "on AutoBench by far more than those inputs move it and on LLMRouterBench by about as little" in note
    assert "- No run moves a `cost_blind` cell, on any grid or bar of the four datasets" in _section(note, "Facts")
    # the Limits and the Recommendation name the four datasets measured, so none is left (rows R39c, R39d)
    assert ("- Four datasets, AutoBench 2026, LLMRouterBench, the LLM Routing Response Bank and tau2-bench, per domain "
            "and pooled, every committed delegation results file") in _section(note, "Limits")
    assert "not measured yet" not in note and "- Measure the tau2-bench" not in note
    rec = _section(note, "Recommendation")
    assert "on the Response Bank it moves a few decisions of one task" in rec
    assert "on tau2-bench, where neither input the re-read note varies moves a cell, it moves up to about a fifth" in rec
    assert "no one bound holds across the four delegation datasets" in rec
    method = _section(note, "Method")
    for phrase in ("`price_in` and `price_out`", "committed prices", "`_router`", "`checked`", "`call_cost`",
                   "median call count"):
        assert phrase in method, phrase


def test_the_research_index_lists_the_note():
    index = INDEX.read_text(encoding="utf-8")
    assert index.count("| [delegation-price-sensitivity.md](delegation-price-sensitivity.md) | ") == 1
    assert index.count("- `research/delegation-price-sensitivity.md` ") == 1


def test_the_design_bullet_is_in_12_22():
    text = DESIGN.read_text(encoding="utf-8")
    section = text.split("\n### 12.22 ", 1)[1].split("\n## 13. ", 1)[0]
    bullet = [line for line in section.splitlines() if line.startswith(BULLET)]
    assert len(bullet) == 1
    for phrase in ("`research/delegation-price-sensitivity.md`", "`research/delegation_price_sensitivity.py`",
                   "`research/reread_sensitivity.py`, loaded from its own folder by path", "`inputs` and `checked`",
                   "exit 2", "at the committed prices", "0.5 and 2.0", "`price_in` and `price_out` times the factor",
                   "committed 13.2 costs", "tests/test_research_delegation_price_sensitivity.py", "`## Results` block",
                   "`--dataset llmrouterbench` (v1.425, row R39b) runs the 13.13 grid", "refuses `--registry`",
                   "names the task count", "one block per dataset",
                   "`--dataset response-bank` (v1.426, row R39c) runs the 13.14 grid",
                   "`--dataset tau2-bench` and `--dataset tau2-bench-pooled` (v1.427, row R39d) run the 13.12 grid",
                   "priced by its `call_cost`", "median call count (13.9 v1.74)", "two for tau2-bench"):
        assert phrase in bullet[0], phrase
    # the last bullet of 12.22, after the re-read bullet
    lines = section.rstrip("\n").split("\n")
    assert lines[-1] == bullet[0] and lines[-2].startswith("- The re-read share and the brief's output, ")
    # it names the 9 clause that specifies the README Limitations sentence linking the note (v1.428, row DOC36),
    # as the routing price-error bullet names 9 v1.417
    assert bullet[0].endswith("; README Limitations links it (9 v1.428)")
    assert bullet[0].count("README Limitations") == 1


# --- README Limitations' prices bullet: the delegation price error (DESIGN 9 v1.428, row DOC36) ------------

README = ROOT / "README.md"
PRICES = "- Prices are a dated snapshot. "
ROUTING_END = "(the note measures what a wrong price does, not how often prices change, so it sets no fixed interval). "
DESIGN_9 = (
    "- v1.428 a price error in a delegation decision in the README (row DOC36, the Recommendation of the 12.22 v1.424 "
    "note): README Limitations' prices bullet gives, in one sentence right after the v1.417 one, how far a wrong price "
    "moves `cost_effective` delegation decisions, from `research/delegation-price-sensitivity.md`, which it links: with "
    "one model's prices halved or doubled, one model at a time, the largest share of a bar's `cost_effective` cells "
    "that a run changes on each of the four delegation datasets, over all of its grids, from the least moved to the "
    "most, the Response Bank's saying that all of its changed cells are on one task, and that no `cost_blind` cell "
    "moves, since that flavor compares no costs; then that a small effect on one dataset bounds none on another. Each "
    "share is the one the note's Results blocks print, which tests/test_research_delegation_price_sensitivity.py reads "
    "from them to build the sentence, pinned once in that place, checking on the way that the order is from the least "
    "to the most and that the Response Bank's changed cells are all of one task; the note's Recommendation says that "
    "README Limitations links it. No code, cost, committed result or README transcript changes\n")


def delegation_price_sentence():
    """The README Limitations sentence on a price error in a delegation decision, built from the note's five blocks."""
    note = NOTE.read_text(encoding="utf-8")
    commands = (COMMAND, LRB_COMMAND, RB_COMMAND, T2_COMMAND, T2_POOLED_COMMAND)
    tables = {command: _table(_block(note, command)) for command in commands}
    assert [len(tables[c]) for c in commands] == [8, 8, 4, 12, 12]
    # no run moves a cost_blind cell in any block
    assert all(v["moving"] == 0 and v["most"] == 0
               for table in tables.values() for k, v in table.items() if k[1] == "cost_blind")

    def top(*names):
        """The largest share a run changes over the blocks' `cost_effective` rows, as the block prints it."""
        rows = [v for name in names for k, v in tables[name].items() if k[1] == "cost_effective"]
        return max((v["share"] for v in rows), key=float)

    autobench, lrb, rb = top(COMMAND), top(LRB_COMMAND), top(RB_COMMAND)
    t2 = top(T2_COMMAND, T2_POOLED_COMMAND)
    # the sentence lists them from the least moved to the most
    assert float(rb) < float(t2) < float(lrb) < float(autobench)
    # all of the Response Bank's changed cells are of one task
    block = _block(note, RB_COMMAND)
    by_task = [x.rsplit(" ", 1) for x in re.search(TASK_LINE, block, flags=re.M).group(1).split(", ")]
    assert len(by_task) > 1 and len([t for t, n in by_task if int(n.replace(",", ""))]) == 1
    return (
        "A wrong price also moves `cost_effective` delegation decisions, by an amount that depends on the dataset: on "
        "the four delegation datasets ([research/delegation-price-sensitivity.md](research/delegation-price-sensitivity.md)), "
        f"one model's prices halved or doubled, one model at a time, changed at most {rb}% of a bar's `cost_effective` "
        f"cells on the LLM Routing Response Bank, all on one task, {t2}% on tau2-bench, {lrb}% on LLMRouterBench and "
        f"{autobench}% on AutoBench 2026, and no `cost_blind` cell, since that flavor compares no costs; a small "
        "effect on one dataset bounds none on another. ")


def test_readme_limitations_give_the_delegation_price_error_after_the_routing_one():
    sentence = delegation_price_sentence()
    readme = README.read_text(encoding="utf-8")
    limits = readme.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    [bullet] = [x for x in limits.split("\n") if x.startswith(PRICES)]
    assert bullet.count(sentence) == 1
    # right after the routing sentence (9 v1.417), which ends at its interval, and before the end-date one
    at = bullet.index(sentence)
    assert bullet[:at].endswith(ROUTING_END) and bullet.count(ROUTING_END) == 1
    assert bullet[at + len(sentence):].startswith("A row whose vendor states an end date ")
    # the README links the note in this sentence alone
    assert readme.count("(research/delegation-price-sensitivity.md)") == 1


def test_design_9_states_the_delegation_sentence_after_the_routing_clause():
    text = DESIGN.read_text(encoding="utf-8")
    s9 = text[text.index("\n## 9. Data files\n"):text.index("\n## 10. ")]
    assert s9.count(DESIGN_9) == 1
    # right after the v1.417 clause, as the sentence follows that clause's sentence in the README
    lines = s9.split("\n")
    at = lines.index(DESIGN_9.rstrip("\n"))
    assert lines[at - 1].startswith("- v1.417 a price error in the README (row DOC30, ")
    # no number of the sentence is written into the clause, so the clause cannot go stale
    assert NUMBER.findall(DESIGN_9.split(": README Limitations' prices bullet", 1)[1]) == []


def test_the_recommendation_says_readme_limitations_link_the_note():
    rec = _section(NOTE.read_text(encoding="utf-8"), "Recommendation")
    assert rec.count("README Limitations' prices bullet links this note and gives the range") == 1
    assert "should link this note" not in rec
    assert "right after its routing sentence on a stale price, which stays as it is" in rec


@pytest.fixture(scope="module")
def output(ps, tmp_path_factory):
    cv = _load("research_delegation_price_autobench_convert", ROOT / "evidence" / "autobench-2026" / "convert.py")
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("pinned AutoBench files are not in the default cache")
    for name, (size, sha) in cv.FILES.items():
        cv.verify(folder / name, size, sha)
    params = json.loads((folder / "frozen_params.json").read_text(encoding="utf-8"))
    pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
    rows, _report = cv.convert(cv.read_csv(folder / "matrix.csv"), cv.read_csv(folder / "questions.csv"),
                               pool, params["delta_signal"], params["top_k"], task_by="all", tokens=True)
    tmp = tmp_path_factory.mktemp("pinned")
    matrix = tmp / "autobench-tokens.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    registry = tmp / "autobench-pool.json"
    registry.write_text(json.dumps(cv.pool_registry(pool)), encoding="utf-8")
    return ps.run(matrix, registry, ROOT)


def test_note_results_block_is_the_script_output(output):
    assert _block(NOTE.read_text(encoding="utf-8")).split("\n") == output


@pytest.fixture(scope="module")
def lrb_output(ps, llmrouterbench_pinned):
    code, _report, path = llmrouterbench_pinned
    assert code == 0
    return ps.run(path, None, ROOT, "llmrouterbench")


def test_note_llmrouterbench_block_is_the_script_output(lrb_output):
    assert _block(NOTE.read_text(encoding="utf-8"), LRB_COMMAND).split("\n") == lrb_output


@pytest.fixture(scope="module")
def rb_output(ps, response_bank_pinned):
    code, _stdout, _stderr, path = response_bank_pinned
    assert code == 0
    return ps.run(path, None, ROOT, "response-bank")


def test_note_response_bank_block_is_the_script_output(rb_output):
    assert _block(NOTE.read_text(encoding="utf-8"), RB_COMMAND).split("\n") == rb_output


@pytest.fixture(scope="module")
def t2_output(ps, tmp_path_factory):
    """The script's lines on the tau2-bench converter's --calls matrices, per domain and pooled, built from the 12
    pinned run files as tests/test_research_reread_sensitivity.py builds them."""
    cv = _load("research_delegation_price_tau2_convert", ROOT / "evidence" / "tau2-bench" / "convert.py")
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("the 12 pinned tau2-bench run files are not in the default cache")
    extracts = []
    for n, (size, sha) in cv.FILES.items():
        cv.verify(folder / n, size, sha)
        extracts.append(cv.extract(cv.read_run(folder / n), trial=0, tokens=True, calls=True))
    tmp, out = tmp_path_factory.mktemp("t2-pinned"), {}
    for dataset, task_by in (("tau2-bench", "domain"), ("tau2-bench-pooled", "all")):
        matrix = tmp / f"{dataset}.jsonl"
        matrix.write_text("".join(json.dumps(r) + "\n" for r in cv.convert(extracts, task_by=task_by)[0]),
                          encoding="utf-8")
        out[dataset] = ps.run(matrix, None, ROOT, dataset)
    return out


@pytest.mark.parametrize("dataset, command", [("tau2-bench", T2_COMMAND), ("tau2-bench-pooled", T2_POOLED_COMMAND)])
def test_note_tau2_blocks_are_the_script_output(t2_output, dataset, command):
    assert _block(NOTE.read_text(encoding="utf-8"), command).split("\n") == t2_output[dataset]
