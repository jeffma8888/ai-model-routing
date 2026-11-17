"""research/reread-sensitivity.md and research/reread_sensitivity.py (DESIGN 12.22 v1.413, row R38).

The script's item costs are checked against costs worked by hand at sigma 0.5 and W = 2 B; its report
on a hand-built AutoBench-shaped matrix, run end to end through `main` against a root whose committed
13.10 files are that matrix's, against a brute force that rebuilds each cell's router from the public
API and prices each held-out item in exact fractions; its exits on a summary that is not the committed
one, a re-decided cell or a held-out sum that is not the run's, a tiered model and per-call rows. The
note's results block is the script's output on the pinned AutoBench files, compared byte for byte when
they are cached, which CI never does; every number of the note's prose is in that block.

v1.414 (row R38b) adds `--dataset llmrouterbench`: a hand-built matrix of two tasks, with an item that
has a null token count and a model the registry lacks, run through `main` against a root whose committed
13.13 files are that matrix's, against the same brute force on the rows the brute force itself keeps; its
refusals of `--registry`, of a missing one for AutoBench and of a summary that is not the committed one;
and the note's LLMRouterBench block, compared byte for byte when the pinned file is cached (the session
fixture `llmrouterbench_pinned` of tests/conftest.py), whose Facts claims a test checks against it.

v1.415 (row R38c) adds `--dataset response-bank`, checked as `--dataset llmrouterbench` is: the same hand
matrix through `main` against a root whose committed 13.14 files are that matrix's, against the brute
force; its refusal of `--registry` and of a summary that is not the committed one; and the note's
Response Bank block, compared byte for byte when the four pinned files are cached (the session fixture
`response_bank_pinned`), with the Facts and Recommendation claims checked against it.

v1.416 (row R38d) adds `--dataset tau2-bench` and `tau2-bench-pooled`, the 13.12 runs, whose rows carry
per-call sizes (13.9 v1.74): `call_cost` is checked against costs worked by hand at sigma 0.5 and W = 2 B;
a hand-built per-call matrix of two tasks, and the same rows pooled into one, run through `main` against a
root whose committed 13.12 file is that matrix's, against the brute force with each call's reads summed one
call at a time in exact fractions; the refusals of `--registry`, of rows without per-call sizes and of a
summary that is not the committed one; and the note's two tau2-bench blocks, compared byte for byte when
the 12 pinned tau2-bench files are cached, with the Facts claims checked against them.

v1.420 (row DOC33): README Limitations' inline-or-delegate cost bullet gives the note's bounds in the
sentence after the `brief_output_tokens` one and links the note, which the test builds from the five
Results blocks, and the note's Recommendation and DESIGN 13.1 say so.

v1.438 (row T14): at sigma 0, sigma 0.5 and W = 2 B a run re-decides only the `cost_effective` cells, as the
script's `REDECIDED` names them, and each `cost_blind` cell keeps its committed pick, which neither sigma nor W can
move (both enter only costs, a candidate's 5.2 `routing_cost` is 0.0 outside `cost_effective` and every 13.5 cost
comparison is under `cost_effective`): `Run.decide` is called once per `cost_blind` cell, by the check, and four
times per `cost_effective` cell; on the hand matrices the cut prints what re-deciding every cell prints, byte for
byte; and the premise is run, sigma 0 to 1 and W from B to 1000 B + 1 moving no `cost_blind` decision of the
AutoBench and tau2-bench hand matrices.
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
SCRIPT = ROOT / "research" / "reread_sensitivity.py"
NOTE = ROOT / "research" / "reread-sensitivity.md"
INDEX = ROOT / "research" / "README.md"
DESIGN = ROOT / "DESIGN.md"
FOLDER = ROOT / "evidence" / "delegation"
LRB = ROOT / "evidence" / "llmrouterbench-delegation"
RB = ROOT / "evidence" / "response-bank-delegation"
T2 = ROOT / "evidence" / "tau2-bench-delegation"
COMMAND = ("$ python research/reread_sensitivity.py --matrix autobench-tokens.jsonl"
           " --registry autobench-pool.json")
LRB_COMMAND = "$ python research/reread_sensitivity.py --dataset llmrouterbench --matrix llmrouterbench-matrix.jsonl"
RB_COMMAND = "$ python research/reread_sensitivity.py --dataset response-bank --matrix response-bank-matrix.jsonl"
T2_COMMAND = "$ python research/reread_sensitivity.py --dataset tau2-bench --matrix tau2-calls.jsonl"
T2_POOLED_COMMAND = "$ python research/reread_sensitivity.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl"
COMMANDS = (COMMAND, LRB_COMMAND, RB_COMMAND, T2_COMMAND, T2_POOLED_COMMAND)
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
BULLET = ("- The re-read share and the brief's output, on AutoBench, LLMRouterBench, the response bank and "
          "tau2-bench (v1.413, row R38): ")
# DESIGN section numbers: the only numbers of the note's prose not in the script's lines
ALLOWED = {"12.22", "13.1", "13.2", "13.5", "13.9", "13.10", "13.12", "13.13", "13.14"}
NUMBER = re.compile(r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
SETTINGS = (("sigma 0", 0.0, 1), ("sigma 0.5", 0.5, 1), ("W = 2 B", 1.0, 2))

# Parent v/p at 1 and 2 USD per million input and output tokens, delegate v/d at 1 and 1. At the
# folded base point 3 (C = 8,000, B = R = 500, T = 1, K = 1) inline costs P(S_in, S_out) +
# P(S_in + sigma * S_out, 0) = 2 * 100 + (2 + sigma) * S_out and delegating P(0, W) + D(500 + 100,
# 100) + 2 * P(1,000, 0) = 2 W + 2,700, so with v/p's outputs about 1,400 the parent's pick moves
# from delegate to inline as sigma falls to 0 or W doubles, and sits at a tie near sigma 0.5.
P = Model("v/p", "fam-p", 1.0, 2.0, 1_000_000)
D = Model("v/d", "fam-d", 1.0, 1.0, 1_000_000)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rs():
    return _load("research_reread_sensitivity", SCRIPT)


@pytest.fixture(scope="module")
def dr():
    return _load("research_reread_results", FOLDER / "results.py")


@pytest.fixture(scope="module")
def lrb():
    return _load("research_reread_lrb_results", LRB / "results.py")


@pytest.fixture(scope="module")
def rb():
    return _load("research_reread_rb_results", RB / "results.py")


@pytest.fixture(scope="module")
def t2():
    return _load("research_reread_t2_results", T2 / "results.py")


def _rows():
    rows = []
    for j in range(80):
        rows.append({"task": "t", "item": f"i{j:02d}", "model": "v/p", "correct": j % 10 != 0,
                     "input_tokens": 100, "output_tokens": 1200 + 40 * (j % 11)})
        rows.append({"task": "t", "item": f"i{j:02d}", "model": "v/d", "correct": j % 20 != 0,
                     "input_tokens": 100, "output_tokens": 100})
    return rows


def _lrb_rows():
    """Two tasks, `u` listed before `t`, each built as `_rows` with output sizes of its own; item `t80` has a
    null output count, so `select_rows` drops it, and `v/x`, a model the registry lacks, has one row."""
    rows = []
    for task, base, step, mod in (("u", 1200, 40, 11), ("t", 1180, 30, 13)):
        for j in range(80):
            item = f"{task}{j:02d}"
            rows.append({"task": task, "item": item, "model": "v/p", "correct": j % 10 != 0,
                         "input_tokens": 100, "output_tokens": base + step * (j % mod)})
            rows.append({"task": task, "item": item, "model": "v/d", "correct": j % 20 != 0,
                         "input_tokens": 100, "output_tokens": 100})
    rows.append({"task": "t", "item": "t80", "model": "v/p", "correct": True, "input_tokens": 100,
                 "output_tokens": None})
    rows.append({"task": "t", "item": "t80", "model": "v/d", "correct": True, "input_tokens": 100,
                 "output_tokens": 100})
    rows.append({"task": "u", "item": "u00", "model": "v/x", "correct": True, "input_tokens": 1, "output_tokens": 1})
    return rows


def _registry_file(path, models):
    entries = [dict(dataclasses.asdict(m), source="https://example.org/prices") for m in models]
    for e in entries:
        if not e["price_tiers"]:
            del e["price_tiers"]
    path.write_text(json.dumps({"version": "1", "as_of": "2026-01-01", "currency": "USD",
                                "models": entries}), encoding="utf-8")
    return path


def _root(tmp_path, dr, rows, registry):
    folder = tmp_path / "root" / "evidence" / "delegation"
    folder.mkdir(parents=True)
    (folder / "results.py").write_text((FOLDER / "results.py").read_text(encoding="utf-8"), encoding="utf-8")
    for name, grid in (("results.json", "base"), ("variants.json", "variants")):
        (folder / name).write_text(json.dumps(dr.run(rows, registry, grid), indent=2) + "\n", encoding="utf-8")
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return tmp_path / "root", matrix, _registry_file(tmp_path / "pool.json", registry.models)


def _lrb_root(tmp_path, lrb, rows, registry, target=LRB):
    """A root whose committed 13.13 files (or, with `target` RB, 13.14 files) are the run on `rows`; the
    13.13 script reads the base points from the 13.10 script beside it, and the 13.14 script reads those and
    the 13.13 `select_rows`, so those are copied too."""
    root = tmp_path / "root"
    for source in dict.fromkeys((FOLDER, LRB, target)):
        folder = root / "evidence" / source.name
        folder.mkdir(parents=True)
        (folder / "results.py").write_text((source / "results.py").read_text(encoding="utf-8"), encoding="utf-8")
    folder = root / "evidence" / target.name
    _registry_file(folder / "registry.json", registry.models)
    kept, _dropped = lrb.select_rows(rows, [m.id for m in registry.models])
    (folder / "results.json").write_text(json.dumps(lrb.run(kept, registry), indent=2) + "\n", encoding="utf-8")
    matrix = tmp_path / "lrb.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return root, matrix


def _main(rs, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = rs.main(argv)
    return code, out.getvalue(), err.getvalue()


# --- the item costs, worked by hand ----------------------------------------------------------
# K = 2, C = 100, B = 10, R = 20, T = 1, S_in = 30, S_out = 40, sigma = 0.5, W = 20, so w_in = 3,
# w_out = 1 and each work call's re-read of the earlier output is 0.5 * 40 = 20 tokens:
#   delegate         = P(0, 20) + D(2 * 10 + 3 * 30 + 20, 2 * 40) + 2 * P(30, 0) = 40 + 210 + 60 = 310
#   inline, separate = P(2 * 100 + 90 + 20, 80) + 2 * P(2 * (30 + 20), 0) = 470 + 200 = 670
#   inline, folded   = P(100 + 90 + 20, 80) + 1 * P(100, 0) = 370 + 100 = 470
#   separate, rho 0.5 = P(100 + 90 + 20, 80) + 2 * P(100, 0) = 370 + 200 = 570
# each in millionths of a USD.
HAND = {"context_tokens": 100, "brief_tokens": 10, "result_tokens": 20, "carry_turns": 1,
        "inline_separate_call": True, "work_calls": 2}


@pytest.mark.parametrize("path, point, want", [
    ("delegate", HAND, 310),
    ("inline", HAND, 670),
    ("inline", dict(HAND, inline_separate_call=False), 470),
    ("inline", dict(HAND, cached_read_ratio=0.5), 570),
])
def test_item_cost_by_hand(rs, path, point, want):
    assert rs.item_cost(P, D, point, path, 30, 40, 0.5, 20) == pytest.approx(want / 1e6, rel=1e-12)


# Per-call sizes (v1.416): two calls with new input a = (30, 10) and output b = (40, 20), at C = 100, B = 10,
# R = 20, T = 1, sigma = 0.5 and W = 20. Call 1 reads 30 and call 2 reads 30 + 10 + 0.5 * 40, so the calls
# read 90 and write 60, and each later read of the work is A + sigma * O = 40 + 30 = 70:
#   delegate          = P(0, 20) + D(2 * 10 + 90, 60) + 2 * P(30, 0) = 40 + 170 + 60 = 270
#   inline, separate  = P(2 * 100 + 90, 60) + 2 * P(70, 0) = 410 + 140 = 550
#   inline, folded    = P(100 + 90, 60) + 1 * P(70, 0) = 310 + 70 = 380
#   separate, rho 0.5 = P(100 + 90, 60) + 2 * P(70, 0) = 310 + 140 = 450
CALLS_POINT = {k: v for k, v in HAND.items() if k != "work_calls"}
CALLS = (2, 2 * 30 + 10 + 40, 40, 60, (30, 10), (40, 20))


@pytest.mark.parametrize("path, point, want", [
    ("delegate", CALLS_POINT, 270),
    ("inline", CALLS_POINT, 550),
    ("inline", dict(CALLS_POINT, inline_separate_call=False), 380),
    ("inline", dict(CALLS_POINT, cached_read_ratio=0.5), 450),
])
def test_call_cost_by_hand(rs, path, point, want):
    assert rs.call_cost(P, D, point, path, CALLS, 0.5, 20) == pytest.approx(want / 1e6, rel=1e-12)


# --- the brute force -------------------------------------------------------------------------
def _cost(m, i, o):
    return (Fraction(i) * Fraction(m.price_in) + Fraction(o) * Fraction(m.price_out)) / 1_000_000


def _exact(p, d, point, path, tin, tout, sigma, w):
    """13.2 at sigma and W in fractions, written apart from the script's float expression."""
    c, b, r, t = (point[k] for k in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns"))
    k, s = point.get("work_calls", 1), Fraction(sigma)
    reread = Fraction(k * (k - 1) // 2) * s * tout
    if path == "delegate":
        return _cost(p, 0, w) + _cost(d, k * b + k * (k + 1) // 2 * tin + reread, k * tout) + (1 + t) * _cost(p, b + r, 0)
    separate = point["inline_separate_call"]
    reads = Fraction(k * c if separate else (k - 1) * c) * Fraction(point.get("cached_read_ratio", 1))
    work = _cost(p, reads + k * (k + 1) // 2 * tin + reread, k * tout)
    return work + ((1 + t) if separate else t) * _cost(p, k * (tin + s * tout), 0)


def _exact_calls(p, d, point, path, a, b, sigma, w):
    """13.2 at sigma and W on a row with per-call sizes (v1.416), in fractions, one call at a time: call j
    reads the path's base and a_1 to a_j and, at sigma, b_1 to b_(j-1)."""
    c, brief, r, t = (point[k] for k in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns"))
    s, k = Fraction(sigma), len(a)
    reads = [sum(a[:j + 1]) + s * sum(b[:j]) for j in range(k)]
    if path == "delegate":
        return _cost(p, 0, w) + _cost(d, k * brief + sum(reads), sum(b)) + (1 + t) * _cost(p, brief + r, 0)
    separate = point["inline_separate_call"]
    base = Fraction(k * c if separate else (k - 1) * c) * Fraction(point.get("cached_read_ratio", 1))
    work = _cost(p, base + sum(reads), sum(b))
    return work + ((1 + t) if separate else t) * _cost(p, sum(a) + s * sum(b), 0)


def _up(x, y):
    return -(-x // y)


def _expected(rows, registry, dr, grid, name, title="AutoBench 2026", folder="evidence/delegation", per_call=False):
    """The report lines of one committed file, by a router rebuilt from the public API per task, seed and
    bar (one per cell before v1.414), each held-out sum in fractions per task, seed, point, parent, pick
    and setting. With `per_call` (v1.416) each model's calibration sizes are its rounded-up means per call
    and the decision's `work_calls` the half's median call count, as 13.9 v1.74 states them, and each item
    is priced by `_exact_calls`."""
    points = dr.points() if grid == "base" else dr.variant_points()
    full = evaluate_delegation(rows, registry, bars=list(dr.BARS), points=points, seeds=range(dr.SEEDS))
    by = {(r["task"], r["item"], r["model"]): r for r in rows}
    tasks = sorted({r["task"] for r in rows})
    items = {t: list(dict.fromkeys(r["item"] for r in rows if r["task"] == t)) for t in tasks}
    models = sorted({r["model"] for r in rows})
    halves = {(t, seed): split_items(items[t], seed, 0.5) for t in tasks for seed in range(dr.SEEDS)}
    routers, sums, works = {}, {}, {}

    def decide(cell, point, sigma, w):
        t = cell["task"]
        if (t, cell["seed"], cell["bar"]) not in routers:
            cal = halves[t, cell["seed"]][0]
            stats = Stats()
            if per_call:
                for m in models:
                    calls = [by[t, i, m] for i in cal]
                    k = sum(len(h["call_input_tokens"]) for h in calls)
                    stats.add(t, m, sum(h["correct"] for h in calls), len(cal),
                              input_tokens=len(cal) * _up(sum(sum(h["call_input_tokens"]) for h in calls), k),
                              output_tokens=len(cal) * _up(sum(h["output_tokens"] for h in calls), k))
                each = [by[t, i, m] for i in cal for m in models]
                sizes = ([_up(sum(h["call_input_tokens"]), len(h["call_input_tokens"])) for h in each],
                         [_up(h["output_tokens"], len(h["call_input_tokens"])) for h in each])
                works[t, cell["seed"]] = statistics.median_low([len(h["call_input_tokens"]) for h in each])
            else:
                for m in models:
                    stats.add(t, m, sum(by[t, i, m]["correct"] for i in cal), len(cal),
                              input_tokens=sum(by[t, i, m]["input_tokens"] for i in cal),
                              output_tokens=sum(by[t, i, m]["output_tokens"] for i in cal))
                sizes = ([by[t, i, m]["input_tokens"] for i in cal for m in models],
                         [by[t, i, m]["output_tokens"] for i in cal for m in models])
            task = Task(name=t, bar=cell["bar"], min_samples=30, confidence=0.95, independent_of_generator=False,
                        expected_input_tokens=statistics.median_low(sizes[0]),
                        expected_output_tokens=statistics.median_low(sizes[1]),
                        on_no_model="best_available", max_fallbacks=0)
            routers[t, cell["seed"], cell["bar"]] = Router(registry, {t: task}, stats)
        if per_call:
            point = dict(point, work_calls=works[t, cell["seed"]])
        got = routers[t, cell["seed"], cell["bar"]].decide_delegation(
            t, cell["parent"], cell["flavor"], **point, output_reread_share=sigma, brief_output_tokens=w)
        return got.mode, got.model

    def held(cell, point, pick, sigma, w):
        key = (cell["task"], cell["seed"], cell["point"], cell["parent"], pick, sigma, w)
        if key not in sums:
            p, d = registry.get(cell["parent"]), registry.get(pick[1])
            hits = [by[cell["task"], i, pick[1]] for i in halves[cell["task"], cell["seed"]][1]]
            sums[key] = (sum(h["correct"] for h in hits), len(hits),
                         sum(_exact_calls(p, d, point, pick[0], h["call_input_tokens"], h["call_output_tokens"], sigma, w)
                             if per_call else
                             _exact(p, d, point, pick[0], h["input_tokens"], h["output_tokens"], sigma, w) for h in hits))
        return sums[key]

    cells = full["cells"]
    for cell in cells:
        point = points[cell["point"]]
        assert decide(cell, point, 1.0, point["brief_tokens"]) == (cell["mode"], cell["model"])
    many = len(tasks) > 1
    lines = [f"{title}, {grid} grid (`{folder}/{name}`): {len(cells):,} cells, "
             + (f"{len(tasks)} tasks, " if many else "")
             + f"{len(dr.BARS)} bars, 2 flavors, {len(points)} points, 2 parents, {dr.SEEDS} seeds; every cell's decision "
             "and held-out sum reproduced at sigma 1.0 and W = B",
             "  flavor          bar  setting    changed / cells  share  to inline  success gap  cost ratio  all cost ratio"]
    by_point = {label: [0] * len(points) for label, _, _ in SETTINGS}
    by_task = {label: dict.fromkeys(tasks, 0) for label, _, _ in SETTINGS}
    why = {label: [] for label, _, _ in SETTINGS}
    for flavor in ("cost_effective", "cost_blind"):
        for bar in dr.BARS:
            sel = [c for c in cells if (c["flavor"], c["bar"]) == (flavor, bar)]
            for label, sigma, factor in SETTINGS:
                changed = inline = new_hits = old_hits = n = 0
                new_cost = old_cost = all_new = all_old = Fraction(0)
                for cell in sel:
                    point = points[cell["point"]]
                    w = factor * point["brief_tokens"]
                    was = (cell["mode"], cell["model"])
                    pick = decide(cell, point, sigma, w)
                    old, new = held(cell, point, was, sigma, w), held(cell, point, pick, sigma, w)
                    all_new, all_old = all_new + new[2], all_old + old[2]
                    if pick != was:
                        changed += 1
                        inline += pick[0] == "inline"
                        by_point[label][cell["point"]] += 1
                        by_task[label][cell["task"]] += 1
                        why[label].append((cell["reason"], cell["seed"], cell["parent"]))
                        new_hits, old_hits, n = new_hits + new[0], old_hits + old[0], n + old[1]
                        new_cost, old_cost = new_cost + new[2], old_cost + old[2]
                gap = f"{(new_hits - old_hits) / n:+.4f}" if changed else "-"
                ratio = f"{float(new_cost / old_cost):.3f}" if changed else "-"
                lines.append(f"  {flavor:<14}  {bar:<3}  {label:<9}  {changed:>7} / {len(sel):<5,}  "
                             f"{100 * changed / len(sel):>4.1f}%  {inline:>9}  {gap:>11}  {ratio:>10}  "
                             f"{float(all_new / all_old):>14.3f}")
    for label, _, _ in SETTINGS:
        lines.append(f"  changed cells by point, {label}: " + ", ".join(f"{i}: {n}" for i, n in enumerate(by_point[label])))
    for label, _, _ in SETTINGS:
        changed = why[label]
        if not changed:
            lines.append(f"  changed cells by reason, {label}: none")
            continue
        reasons = {r: sum(x[0] == r for x in changed) for r in {x[0] for x in changed}}
        parents = {p: sum(x[2] == p for x in changed) for p in {x[2] for x in changed}}
        top = min(parents, key=lambda p: (-parents[p], p))
        seeds = len({x[1] for x in changed})
        lines.append(f"  changed cells by reason, {label}: "
                     + ", ".join(f"{r} {reasons[r]}" for r in sorted(reasons, key=lambda r: (-reasons[r], r)))
                     + f"; {seeds} seed{'s' * (seeds != 1)}, {len(parents)} parent{'s' * (len(parents) != 1)}, "
                     f"the most {parents[top]} of {top}")
    if many:
        for label, _, _ in SETTINGS:
            lines.append(f"  changed cells by task, {label}: " + ", ".join(f"{t} {by_task[label][t]}" for t in tasks))
    return lines


@pytest.fixture(scope="module")
def hand(rs, dr, tmp_path_factory):
    rows, registry = _rows(), Registry([P, D])
    root, matrix, pool = _root(tmp_path_factory.mktemp("hand"), dr, rows, registry)
    code, out, err = _main(rs, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    return rows, registry, root, matrix, pool, code, out, err


def test_report_on_a_hand_matrix_is_the_brute_force(rs, dr, hand):
    rows, registry, _, _, _, code, out, err = hand
    assert (code, err) == (0, "")
    want = ["The re-read share and the brief's output on the AutoBench 2026 delegation results: each cell "
            "re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs"]
    want += _expected(rows, registry, dr, "base", "results.json")
    want += _expected(rows, registry, dr, "variants", "variants.json")
    assert out.split("\n") == want + [""]


def test_the_hand_matrix_moves_a_decision_at_each_setting(hand):
    out = hand[6]
    for label in ("sigma 0", "sigma 0.5", "W = 2 B"):
        line = next(x for x in out.split("\n") if x.startswith(f"  changed cells by point, {label}: "))
        counts = [int(x.split(": ")[1]) for x in line.split(": ", 1)[1].split(", ")]
        assert counts[3] > 0 and counts[:3] == [0, 0, 0], line


@pytest.fixture(scope="module")
def lrb_hand(rs, lrb, tmp_path_factory):
    rows, registry = _lrb_rows(), Registry([P, D])
    root, matrix = _lrb_root(tmp_path_factory.mktemp("lrb"), lrb, rows, registry)
    code, out, err = _main(rs, ["--dataset", "llmrouterbench", "--matrix", str(matrix), "--root", str(root)])
    return rows, registry, root, matrix, code, out, err


def _kept(rows, registry):
    """The 13.13 rows (13.14 takes the same rule), kept here apart from `select_rows`: the registry's models,
    less every item on which one of them has a null token count."""
    names = {m.id for m in registry.models}
    null = {r["item"] for r in rows if r["model"] in names and None in (r["input_tokens"], r["output_tokens"])}
    kept = [r for r in rows if r["model"] in names and r["item"] not in null]
    assert null == {"t80"} and len(kept) == len(rows) - 3
    return kept


def test_llmrouterbench_report_on_a_hand_matrix_is_the_brute_force(lrb, lrb_hand):
    rows, registry, _, _, code, out, err = lrb_hand
    assert (code, err) == (0, "")
    kept = _kept(rows, registry)
    want = ["The re-read share and the brief's output on the LLMRouterBench delegation results: each cell "
            "re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs"]
    want += _expected(kept, registry, lrb, "base", "results.json", "LLMRouterBench",
                      "evidence/llmrouterbench-delegation")
    assert out.split("\n") == want + [""]


def test_the_llmrouterbench_hand_matrix_moves_cells_of_both_tasks(lrb_hand):
    out = lrb_hand[5].split("\n")
    assert out[1].startswith("LLMRouterBench, base grid (`evidence/llmrouterbench-delegation/results.json`): "
                             "6,400 cells, 2 tasks, 4 bars, 2 flavors, 4 points, 2 parents, 50 seeds; ")
    for label in ("sigma 0", "sigma 0.5", "W = 2 B"):
        line = next(x for x in out if x.startswith(f"  changed cells by task, {label}: "))
        counts = [x.rsplit(" ", 1) for x in line.split(": ", 1)[1].split(", ")]
        assert [t for t, _ in counts] == ["t", "u"] and all(int(n) > 0 for _, n in counts), line


@pytest.fixture(scope="module")
def rb_hand(rs, rb, tmp_path_factory):
    rows, registry = _lrb_rows(), Registry([P, D])
    root, matrix = _lrb_root(tmp_path_factory.mktemp("rb"), rb, rows, registry, RB)
    code, out, err = _main(rs, ["--dataset", "response-bank", "--matrix", str(matrix), "--root", str(root)])
    return rows, registry, root, matrix, code, out, err


def test_response_bank_report_on_a_hand_matrix_is_the_brute_force(rb, rb_hand):
    rows, registry, _, _, code, out, err = rb_hand
    assert (code, err) == (0, "")
    want = ["The re-read share and the brief's output on the LLM Routing Response Bank delegation results: each "
            "cell re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs"]
    want += _expected(_kept(rows, registry), registry, rb, "base", "results.json", "LLM Routing Response Bank",
                      "evidence/response-bank-delegation")
    assert out.split("\n") == want + [""]


def test_the_response_bank_hand_matrix_moves_cells_of_both_tasks(rb_hand):
    out = rb_hand[5].split("\n")
    assert out[1].startswith("LLM Routing Response Bank, base grid (`evidence/response-bank-delegation/results.json`): "
                             "3,200 cells, 2 tasks, 2 bars, 2 flavors, 4 points, 2 parents, 50 seeds; ")
    for label in ("sigma 0", "sigma 0.5", "W = 2 B"):
        line = next(x for x in out if x.startswith(f"  changed cells by task, {label}: "))
        counts = [x.rsplit(" ", 1) for x in line.split(": ", 1)[1].split(", ")]
        assert [t for t, _ in counts] == ["t", "u"] and all(int(n) > 0 for _, n in counts), line


# --- v1.416 (row R38d): the tau2-bench runs, rows with per-call sizes ---------------------------
def _call_row(task, item, model, correct, a, b):
    """A 13.9 v1.74 per-call row whose counts are what its calls read and write."""
    k = len(a)
    return {"task": task, "item": item, "model": model, "correct": correct,
            "input_tokens": sum((k - j) * a[j] + (k - j - 1) * b[j] for j in range(k)),
            "output_tokens": sum(b), "call_input_tokens": list(a), "call_output_tokens": list(b)}


def _t2_rows(pooled=False):
    """Three tasks, `u`, `t` and `s`, or with `pooled` the same rows as one task `all`, items named `task|j` as
    the converter names them `domain|id`. On `u` and `t` each is `_lrb_rows`' outputs per call: v/p writes
    o = 1,200 + 40 * (j % 11) (`u`) or 1,180 + 30 * (j % 13) (`t`), in one call, a = [100], b = [o], or on
    j % 4 == 0 in two, a = [100, 0], b = [o, o], so its second call re-reads the first one's output; v/d writes
    100 in one call, or on j % 5 == 0 50 in each of two. Their median call count is 1, so the decision prices
    one work call at the half's means per call, while each two-call item's held-out cost reads b_1 again at
    sigma (and, inline, the context once more), so the two kinds of cost differ, as on the pinned
    conversations. On `s` v/p writes o = 1,190 + 20 * (j % 7) in two calls on every item, so that task's median
    call count is 2 and the decision's `work_calls` is above one, as on every pinned domain (review iter-277
    should-fix 1); pooled, the median stays 1."""
    rows = []
    for task, base, step, mod in (("u", 1200, 40, 11), ("t", 1180, 30, 13), ("s", 1190, 20, 7)):
        for j in range(80):
            item, name, o = f"{task}|{j:02d}", "all" if pooled else task, base + step * (j % mod)
            a, b = ([100, 0], [o, o]) if j % 4 == 0 or task == "s" else ([100], [o])
            rows.append(_call_row(name, item, "v/p", j % 10 != 0, a, b))
            a, b = ([100, 0], [50, 50]) if j % 5 == 0 else ([100], [100])
            rows.append(_call_row(name, item, "v/d", j % 20 != 0, a, b))
    return rows


def _t2_root(tmp_path, t2, rows, registry, name):
    """A root whose committed 13.12 file `name` (results.json or pooled.json) is the run on `rows`; the 13.12
    script reads the base points from the 13.10 script, so that is copied too."""
    root = tmp_path / "root"
    for source in (FOLDER, T2):
        folder = root / "evidence" / source.name
        folder.mkdir(parents=True)
        (folder / "results.py").write_text((source / "results.py").read_text(encoding="utf-8"), encoding="utf-8")
    folder = root / "evidence" / T2.name
    _registry_file(folder / "registry.json", registry.models)
    (folder / name).write_text(json.dumps(t2.run(rows, registry), indent=2) + "\n", encoding="utf-8")
    matrix = tmp_path / "t2.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return root, matrix


T2_RUNS = {"tau2-bench": (False, "results.json", "tau2-bench per domain"),
           "tau2-bench-pooled": (True, "pooled.json", "tau2-bench pooled")}


@pytest.fixture(scope="module", params=sorted(T2_RUNS))
def t2_hand(rs, t2, tmp_path_factory, request):
    pooled, name, title = T2_RUNS[request.param]
    rows, registry = _t2_rows(pooled), Registry([P, D])
    root, matrix = _t2_root(tmp_path_factory.mktemp("t2"), t2, rows, registry, name)
    code, out, err = _main(rs, ["--dataset", request.param, "--matrix", str(matrix), "--root", str(root)])
    return request.param, rows, registry, root, matrix, code, out, err


def test_tau2_report_on_a_hand_matrix_is_the_brute_force(t2, t2_hand):
    dataset, rows, registry, _, _, code, out, err = t2_hand
    assert (code, err) == (0, "")
    _, name, title = T2_RUNS[dataset]
    want = [f"The re-read share and the brief's output on the {title} delegation results: each cell "
            "re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs"]
    want += _expected(rows, registry, t2, "base", name, title, "evidence/tau2-bench-delegation", per_call=True)
    assert out.split("\n") == want + [""]


def test_the_tau2_hand_matrix_moves_cells_at_each_setting(t2_hand):
    dataset, *_, out, _err = t2_hand
    out = out.split("\n")
    cells = "14,400 cells, 3 tasks, " if dataset == "tau2-bench" else "4,800 cells, "
    assert out[1].endswith(f"`): {cells}6 bars, 2 flavors, 4 points, 2 parents, 50 seeds; every cell's decision "
                           "and held-out sum reproduced at sigma 1.0 and W = B"), out[1]
    for label in ("sigma 0", "sigma 0.5", "W = 2 B"):
        line = next(x for x in out if x.startswith(f"  changed cells by point, {label}: "))
        counts = [int(x.split(": ")[1]) for x in line.split(": ", 1)[1].split(", ")]
        assert counts[3] > 0 and counts[:3] == [0, 0, 0], line
        if dataset == "tau2-bench":
            line = next(x for x in out if x.startswith(f"  changed cells by task, {label}: "))
            counts = dict(x.rsplit(" ", 1) for x in line.split(": ", 1)[1].split(", "))
            assert list(counts) == ["s", "t", "u"] and int(counts["t"]) > 0 and int(counts["u"]) > 0, line


def test_the_tau2_hand_matrix_forecasts_two_work_calls_on_one_task():
    """The calibration half's median call count over both models' rows, as 13.9 v1.74 forecasts the work: 2
    on `s` and 1 on `t`, `u` and pooled, on every seed, so the hand runs check the decision's `work_calls`
    above one (review iter-277 should-fix 1)."""
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


def test_call_cost_re_reads_each_earlier_output_at_sigma(rs):
    """A two-call parent item of the hand matrix, folded at point 3, against the one-call-at-a-time brute
    force at three sigmas; from sigma 1 to 0 the cost falls by the second call's re-read of b_1 (1,200) and
    the later call's read of O (2,400), each at v/p's input price."""
    row = _call_row("u", "u|00", "v/p", False, [100, 0], [1200, 1200])
    calls = (2, row["input_tokens"], 100, 2400, (100, 0), (1200, 1200))
    point = {"context_tokens": 8000, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
             "inline_separate_call": False}
    for sigma in (0.0, 0.5, 1.0):
        want = float(_exact_calls(P, D, point, "inline", [100, 0], [1200, 1200], sigma, 500))
        assert rs.call_cost(P, D, point, "inline", calls, sigma, 500) == pytest.approx(want, rel=1e-12)
    assert (rs.call_cost(P, D, point, "inline", calls, 1.0, 500) - rs.call_cost(P, D, point, "inline", calls, 0.0, 500)
            == pytest.approx(1200 * 1e-6 + 2400 * 1e-6, rel=1e-12))


def test_tau2_refusals(rs, t2, tmp_path, hand):
    pool = hand[4]
    root, matrix = _t2_root(tmp_path, t2, _t2_rows(), Registry([P, D]), "results.json")
    plain = tmp_path / "plain.jsonl"
    plain.write_text("".join(json.dumps(r) + "\n" for r in _rows()), encoding="utf-8")
    for argv, want in [
        (["--dataset", "tau2-bench", "--matrix", str(matrix), "--registry", str(pool)],
         "error: --registry is only used with --dataset autobench\n"),
        (["--dataset", "tau2-bench", "--matrix", str(plain)], "error: task 't': rows without per-call sizes are not priced here\n"),
        (["--dataset", "tau2-bench-pooled", "--matrix", str(matrix)],
         f"error: {root / 'evidence' / T2.name / 'pooled.json'}: no such file\n"),
    ]:
        code, out, err = _main(rs, argv + ["--root", str(root)])
        assert (code, out, err) == (2, "", want), argv
    path = root / "evidence" / T2.name / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["summary"][0]["cost_usd"] *= 2
    path.write_text(json.dumps(data), encoding="utf-8")
    code, out, err = _main(rs, ["--dataset", "tau2-bench", "--matrix", str(matrix), "--root", str(root)])
    assert (code, out, err) == (2, "", "error: evidence/tau2-bench-delegation/results.json: the run's summary is not "
                                        "the committed one\n")


def test_dataset_refusals(rs, hand, lrb_hand, rb_hand):
    pool = hand[4]
    for (root, matrix), dataset in (((lrb_hand[2], lrb_hand[3]), "llmrouterbench"),
                                    ((rb_hand[2], rb_hand[3]), "response-bank")):
        for argv, want in [
            (["--dataset", dataset, "--matrix", str(matrix), "--registry", str(pool)],
             "error: --registry is only used with --dataset autobench\n"),
            (["--matrix", str(matrix)], "error: --dataset autobench needs --registry\n"),
        ]:
            code, out, err = _main(rs, argv + ["--root", str(root)])
            assert (code, out, err) == (2, "", want), argv


@pytest.mark.parametrize("dataset, target", [("llmrouterbench", LRB), ("response-bank", RB)])
def test_a_many_task_dataset_exits_2_when_the_summary_is_not_the_committed_one(rs, tmp_path, dataset, target):
    script = _load(f"research_reread_{target.name}_summary", target / "results.py")
    root, matrix = _lrb_root(tmp_path, script, _lrb_rows(), Registry([P, D]), target)
    path = root / "evidence" / target.name / "results.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["summary"][0]["cost_usd"] *= 2
    path.write_text(json.dumps(data), encoding="utf-8")
    code, out, err = _main(rs, ["--dataset", dataset, "--matrix", str(matrix), "--root", str(root)])
    assert (code, out) == (2, "")
    assert err == f"error: evidence/{target.name}/results.json: the run's summary is not the committed one\n"


def _edited(tmp_path, root, name, edit):
    path = root / "evidence" / "delegation" / name
    data = json.loads(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_exits_2_when_a_summary_is_not_the_committed_one(rs, dr, tmp_path):
    root, matrix, pool = _root(tmp_path, dr, _rows(), Registry([P, D]))
    _edited(tmp_path, root, "variants.json", lambda d: d["summary"][0].update(cost_usd=d["summary"][0]["cost_usd"] * 2))
    code, out, err = _main(rs, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    assert (code, out) == (2, "")
    assert err == "error: evidence/delegation/variants.json: the run's summary is not the committed one\n"


def test_exits_2_when_a_cell_re_decided_at_the_defaults_moves(rs, hand, monkeypatch):
    _, _, root, matrix, pool, *_ = hand
    real = rs.Run.decide
    monkeypatch.setattr(rs.Run, "decide", lambda self, cell, point, sigma, w: (
        ("inline", cell["parent"]) if cell["point"] == 1 and cell["seed"] == 3 else real(self, cell, point, sigma, w)))
    code, out, err = _main(rs, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    assert (code, out) == (2, "")
    assert err == ("error: evidence/delegation/results.json: a cell re-decided at sigma 1.0 and W = B is not "
                   "the run's: cost_effective, bar 0.7, point 1, parent v/d, seed 3\n")


def test_exits_2_when_a_held_out_sum_at_the_defaults_moves(rs, hand, monkeypatch):
    _, _, root, matrix, pool, *_ = hand
    real = rs.item_cost
    monkeypatch.setattr(rs, "item_cost", lambda *a: real(*a) * (1 + 1e-9))
    code, out, err = _main(rs, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    assert (code, out) == (2, "")
    assert err.startswith("error: evidence/delegation/results.json: a held-out sum at sigma 1.0 and W = B is not "
                          "the run's: ") and err.count("\n") == 1


def test_refusals(rs, dr, tmp_path):
    rows = _rows()
    root, matrix, pool = _root(tmp_path, dr, rows, Registry([P, D]))
    tiered = json.loads(pool.read_text(encoding="utf-8"))
    tiered["models"][1]["price_tiers"] = [{"above_input_tokens": 500_000, "price_in": 2.0, "price_out": 4.0}]
    (tmp_path / "tiered.json").write_text(json.dumps(tiered), encoding="utf-8")
    calls = tmp_path / "calls.jsonl"
    calls.write_text("".join(json.dumps(dict(r, call_input_tokens=[r["input_tokens"]],
                                             call_output_tokens=[r["output_tokens"]])) + "\n" for r in rows),
                     encoding="utf-8")
    for argv, want in [
        (["--matrix", str(tmp_path / "none.jsonl"), "--registry", str(pool)], f"error: {tmp_path / 'none.jsonl'}: no such file\n"),
        (["--matrix", str(matrix), "--registry", str(tmp_path / "tiered.json")], "error: model 'v/d' has price tiers, which are not priced here\n"),
        (["--matrix", str(calls), "--registry", str(pool)], "error: task 't': rows with per-call sizes are not priced here\n"),
    ]:
        code, out, err = _main(rs, argv + ["--root", str(root)])
        assert (code, out, err) == (2, "", want), argv


def test_script_is_standard_library_and_model_routing():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^\s*(?:from|import) (\S+)", text, flags=re.M)}
    assert imports == {"argparse", "collections", "importlib", "json", "sys", "math", "pathlib", "model_routing"}


# --- the note --------------------------------------------------------------------------------
def _section(note, name):
    return note.split(f"\n## {name}\n", 1)[1].split("\n## ", 1)[0]


def _prose(note):
    return re.sub(r"```.*?```", "", note, flags=re.S)


def _block(note, command):
    return note.split(command + "\n", 1)[1].split("\n```", 1)[0]


def test_note_has_its_sections_command_and_regenerate():
    note = NOTE.read_text(encoding="utf-8")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == SECTIONS
    results = _section(note, "Results")
    assert results.count("```text\n" + COMMAND + "\n") == 1
    assert results.count("```text\n" + LRB_COMMAND + "\n") == 1
    for command in COMMANDS:
        assert results.count("```text\n" + command + "\n") == 1, command
    regenerate = _section(note, "Regenerate")
    assert "```bash\n" + "\n".join(REGENERATE) + "\n```" in regenerate
    for link in ("../evidence/delegation/RESULTS.md", "../evidence/llmrouterbench-delegation/RESULTS.md",
                 "../evidence/response-bank-delegation/RESULTS.md", "../evidence/tau2-bench-delegation/RESULTS.md",
                 "ledger-cost-model.md"):
        assert f"]({link})" in note, link


def test_facts_states_the_finding_before_any_number():
    first = _section(NOTE.read_text(encoding="utf-8"), "Facts").strip().split("\n")[0]
    assert first.startswith("- ") and NUMBER.findall(first) == [], first


def test_every_number_of_the_prose_is_in_the_output_or_allowed():
    note = NOTE.read_text(encoding="utf-8")
    printed = {n for command in COMMANDS for n in NUMBER.findall(_block(note, command))}
    assert sorted({n for n in NUMBER.findall(_prose(note)) if n not in printed and n not in ALLOWED}) == []


def _table(block):
    """{(grid, flavor, bar, setting): (changed, cells, to inline, all cost ratio)} and the by-point lines."""
    rows, points, grid = {}, {}, None
    for line in block.split("\n"):
        if line.startswith("AutoBench 2026, "):
            grid = line.split(", ", 2)[1].split(" ")[0]
        found = re.match(r"  (cost_\w+) +(0\.\d) +(sigma 0\.5|sigma 0|W = 2 B) +(\d+) / ([\d,]+) +[\d.]+% +(\d+) .* ([\d.]+)$", line)
        if found:
            f, bar, label, changed, cells, inline, ratio = found.groups()
            rows[grid, f, bar, label] = (int(changed), int(cells.replace(",", "")), int(inline), float(ratio))
        found = re.match(r"  changed cells by point, (.+?): (.+)$", line)
        if found:
            points[grid, found.group(1)] = [int(x.split(": ")[1]) for x in found.group(2).split(", ")]
    return rows, points


def test_the_facts_claims_hold_in_the_block():
    note = NOTE.read_text(encoding="utf-8")
    rows, points = _table(note.split(COMMAND + "\n", 1)[1].split("\n```", 1)[0])
    assert len(rows) == 24 and len(points) == 6
    # no cost_blind cell moves; every base-grid change is to inline and at point 3; no variant change is
    # to inline, W = 2 B changes no variant cell, and every variant change is at variant point 2
    assert all(v[0] == 0 for k, v in rows.items() if k[1] == "cost_blind")
    assert all(v[2] == v[0] for k, v in rows.items() if k[0] == "base")
    assert all(p[:3] == [0, 0, 0] for (g, _), p in points.items() if g == "base")
    assert all(v[2] == 0 for k, v in rows.items() if k[0] == "variants")
    assert all(v[0] == 0 for k, v in rows.items() if k[0] == "variants" and k[3] == "W = 2 B")
    assert all(p[:2] == [0, 0] for (g, _), p in points.items() if g == "variants")
    # the Recommendation's bounds: at most 0.7% of a file, flavor and bar's cells, all-cells ratio 1.000 to 1.003
    assert max(round(100 * v[0] / v[1], 1) for v in rows.values()) == 0.7
    assert (min(v[3] for v in rows.values()), max(v[3] for v in rows.values())) == (1.0, 1.003)
    rec = _section(note, "Recommendation")
    assert "more than 0.7% of the cells of an AutoBench file" in rec and ", 2.6% of LLMRouterBench's" in rec


def _lrb_table(block):
    """{(flavor, bar, setting): (changed, cells, to inline, success gap, cost ratio, all cost ratio)}, with
    None for a `-`, and the by-point and by-task lines."""
    rows, points, tasks = {}, {}, {}
    for line in block.split("\n"):
        found = re.match(r"  (cost_\w+) +(0\.\d) +(sigma 0\.5|sigma 0|W = 2 B) +(\d+) / ([\d,]+) +[\d.]+% +(\d+) +(\S+)"
                         r" +(\S+) +([\d.]+)$", line)
        if found:
            f, bar, label, changed, cells, inline, gap, ratio, whole = found.groups()
            rows[f, bar, label] = (int(changed), int(cells.replace(",", "")), int(inline),
                                   None if gap == "-" else float(gap), None if ratio == "-" else float(ratio),
                                   float(whole))
        found = re.match(r"  changed cells by point, (.+?): (.+)$", line)
        if found:
            points[found.group(1)] = [int(x.split(": ")[1]) for x in found.group(2).split(", ")]
        found = re.match(r"  changed cells by task, (.+?): (.+)$", line)
        if found:
            tasks[found.group(1)] = {t: int(n) for t, n in (x.rsplit(" ", 1) for x in found.group(2).split(", "))}
    return rows, points, tasks


def test_the_llmrouterbench_facts_claims_hold_in_its_block():
    note = NOTE.read_text(encoding="utf-8")
    rows, points, tasks = _lrb_table(_block(note, LRB_COMMAND))
    assert len(rows) == 24 and len(points) == 3 and len(tasks) == 3
    changed = [v for v in rows.values() if v[0]]
    # no cost_blind cell moves; every change is to inline, and on the changed cells the new picks cost less
    assert all(v[0] == 0 for k, v in rows.items() if k[0] == "cost_blind")
    assert changed and all(v[2] == v[0] and v[4] < 1 for v in changed)
    assert (min(v[4] for v in changed), max(v[4] for v in changed)) == (0.834, 0.975)
    assert (min(v[3] for v in changed), max(v[3] for v in changed)) == (-0.0282, 0.0734)
    # at most 2.6% of a flavor and bar's cells, at W = 2 B; all-cells cost ratio 0.997 to 1.000
    top = max(round(100 * v[0] / v[1], 1) for v in rows.values())
    assert top == 2.6 and {k[2] for k, v in rows.items() if round(100 * v[0] / v[1], 1) == top} == {"W = 2 B"}
    assert (min(v[5] for v in rows.values()), max(v[5] for v in rows.values())) == (0.997, 1.0)
    # sigma moves only point 3, the folded one; W = 2 B moves points 0 and 3
    assert points["sigma 0"][:3] == points["sigma 0.5"][:3] == [0, 0, 0] and points["sigma 0"][3] > 0
    assert points["W = 2 B"][1:3] == [0, 0] and points["W = 2 B"][0] > 0 and points["W = 2 B"][3] > 0
    # mmlupro and simpleqa change no cell at either sigma; every task changes some at W = 2 B
    assert all(tasks[label][t] == 0 for label in ("sigma 0", "sigma 0.5") for t in ("mmlupro", "simpleqa"))
    assert all(n > 0 for n in tasks["W = 2 B"].values())


def test_the_response_bank_facts_claims_hold_in_its_block():
    note = NOTE.read_text(encoding="utf-8")
    rows, points, tasks = _lrb_table(_block(note, RB_COMMAND))
    assert len(rows) == 12 and len(points) == 3 and len(tasks) == 3
    changed = [v for v in rows.values() if v[0]]
    # no cost_blind cell moves; every change is to inline and at point 3, the folded one
    assert all(v[0] == 0 for k, v in rows.items() if k[0] == "cost_blind")
    assert changed and all(v[2] == v[0] for v in changed)
    assert all(p[:3] == [0, 0, 0] and p[3] > 0 for p in points.values())
    # on the changed cells the new picks cost 0.877 to 1.028 times the committed ones, for a held-out
    # success gap of +0.0000 to +0.0104, never below the committed picks'
    assert (min(v[4] for v in changed), max(v[4] for v in changed)) == (0.877, 1.028)
    assert (min(v[3] for v in changed), max(v[3] for v in changed)) == (0.0, 0.0104)
    # at most 3.9% of a flavor and bar's cells, at sigma 0 at both bars; all-cells cost ratio 0.996 to 1.000
    top = max(round(100 * v[0] / v[1], 1) for v in rows.values())
    assert top == 3.9 and {k for k, v in rows.items() if round(100 * v[0] / v[1], 1) == top} == {
        ("cost_effective", "0.8", "sigma 0"), ("cost_effective", "0.9", "sigma 0")}
    assert (min(v[5] for v in rows.values()), max(v[5] for v in rows.values())) == (0.996, 1.0)
    # at sigma 0.5 and W = 2 B only mmlu_pro changes; at sigma 0 every task changes some
    assert all(n == 0 for label in ("sigma 0.5", "W = 2 B") for t, n in tasks[label].items() if t != "mmlu_pro")
    assert all(n > 0 for n in tasks["sigma 0"].values())
    # the Recommendation's bounds over the three datasets' blocks: the largest share of each and the
    # all-cells cost ratio range over all of them
    whole = [float(x) for command in COMMANDS
             for x in re.findall(r"^  cost_\w+ .* ([\d.]+)$", _block(note, command), flags=re.M)]
    assert len(whole) == 24 + 24 + 12 + 36 + 36
    rec = _section(note, "Recommendation")
    assert ", 3.9% of the Response Bank's or none of tau2-bench's, per domain or pooled," in rec
    assert (min(whole), max(whole)) == (0.996, 1.003)
    assert f"a factor of {min(whole):.3f} to {max(whole):.3f}" in rec


def test_the_tau2_facts_claims_hold_in_its_blocks():
    note = NOTE.read_text(encoding="utf-8")
    for command, tasks_lines in ((T2_COMMAND, 3), (T2_POOLED_COMMAND, 0)):
        rows, points, tasks = _lrb_table(_block(note, command))
        assert len(rows) == 36 and len(points) == 3 and len(tasks) == tasks_lines, command
        # no cell of either run changes at any setting, so every all-cells cost ratio is 1.000
        assert all(v[0] == 0 and v[3] is None and v[4] is None and v[5] == 1.0 for v in rows.values()), command
        assert all(p == [0, 0, 0, 0] for p in points.values()) and all(set(n.values()) == {0} for n in tasks.values())
        assert "  changed cells by reason, sigma 0: none" in _block(note, command).split("\n")
    facts = _section(note, "Facts")
    assert "- tau2-bench: no cell changes at any setting, per domain (21,600 cells) or pooled (7,200)" in facts


def test_the_note_says_from_13_2_which_terms_sigma_scales():
    method = _section(NOTE.read_text(encoding="utf-8"), "Method")
    for phrase in ("`w_out * sigma * S_out`", "`K * (S_in + sigma * S_out)`", "`P.cost(0, W)`",
                   "`sum (K - j + 1) a_j + sigma * sum (K - j) b_j`", "`A + sigma * O`"):
        assert phrase in method, phrase


def test_the_research_index_lists_the_note():
    index = INDEX.read_text(encoding="utf-8")
    assert index.count("| [reread-sensitivity.md](reread-sensitivity.md) | ") == 1
    assert index.count("- `research/reread-sensitivity.md` ") == 1


# --- v1.438 (row T14): a setting re-decides only the `cost_effective` cells -------------------------------------

EVERY = ("cost_effective", "cost_blind")


def _decide_calls(rs, monkeypatch, argv):
    """`main` on argv with `Run.decide` counted: (code, out, err, [(flavor, sigma, w, B) per call])."""
    calls = []
    real = rs.Run.decide

    def counted(self, cell, point, sigma, w):
        calls.append((cell["flavor"], sigma, w, point["brief_tokens"]))
        return real(self, cell, point, sigma, w)

    monkeypatch.setattr(rs.Run, "decide", counted)
    return (*_main(rs, argv), calls)


def test_a_setting_calls_the_decision_for_the_cost_effective_cells_only(rs, hand, monkeypatch):
    assert rs.REDECIDED == ("cost_effective",)
    argv = ["--matrix", str(hand[3]), "--registry", str(hand[4]), "--root", str(hand[2])]
    code, out, err, calls = _decide_calls(rs, monkeypatch, argv)
    assert (code, out, err) == (0, hand[6], "")
    blind = [c for c in calls if c[0] == "cost_blind"]
    effective = [c for c in calls if c[0] == "cost_effective"]
    # the check decides every cell once at sigma 1.0 and W = B; the three settings decide the cost_effective ones
    assert blind and all(c[1:3] == (1.0, c[3]) for c in blind)
    assert len(effective) == 4 * len(blind)
    assert sorted({(c[1], c[2] // c[3]) for c in effective}) == [(0.0, 1), (0.5, 1), (1.0, 1), (1.0, 2)]
    # with both flavors named, as v1.413 to v1.437 ran, every cell is re-decided at each setting, to the same lines
    monkeypatch.setattr(rs, "REDECIDED", EVERY)
    code, every, err, calls = _decide_calls(rs, monkeypatch, argv)
    assert (code, every, err) == (0, out, "")
    assert sum(c[0] == "cost_blind" for c in calls) == 4 * len(blind)


@pytest.mark.parametrize("which, dataset", [("lrb_hand", "llmrouterbench"), ("rb_hand", "response-bank")])
def test_the_cut_prints_what_re_deciding_every_cell_prints(rs, which, dataset, request, monkeypatch):
    root, matrix, code, cut, err = request.getfixturevalue(which)[2:]
    assert (code, err) == (0, "")
    assert any(line.startswith("  cost_blind ") for line in cut.split("\n"))
    monkeypatch.setattr(rs, "REDECIDED", EVERY)
    assert _main(rs, ["--dataset", dataset, "--matrix", str(matrix), "--root", str(root)]) == (0, cut, "")


def test_the_cut_prints_what_re_deciding_every_cell_prints_on_tau2_bench(rs, t2_hand, monkeypatch):
    dataset, _rows, _registry, root, matrix, code, cut, err = t2_hand
    assert (code, err) == (0, "")
    monkeypatch.setattr(rs, "REDECIDED", EVERY)
    assert _main(rs, ["--dataset", dataset, "--matrix", str(matrix), "--root", str(root)]) == (0, cut, "")


def _premise(rs, matrix, registry, root, dataset):
    """Each cell of the dataset's first committed file re-decided at sigma 0, 0.5, 1 and W = B, 2 B, 1000 B + 1:
    a `cost_blind` one must keep its pick; returns how many `cost_effective` decisions moved."""
    _title, files, dr_, rows, pool = rs.inputs(matrix, registry, root, dataset)
    run, got, _rel = rs.checked(rows, pool, root, *files[0], dr_, dataset)
    cells, moved = run.result["cells"], 0
    assert {c["mode"] for c in cells if c["flavor"] == "cost_blind"} == {"inline", "delegate"}
    for cell in cells:
        point = got["config"]["points"][cell["point"]]
        b = point["brief_tokens"]
        for sigma in (0.0, 0.5, 1.0):
            for w in (b, 2 * b, 1000 * b + 1):
                pick = run.decide(cell, point, sigma, w)
                if cell["flavor"] == "cost_blind":
                    assert pick == (cell["mode"], cell["model"]), (cell, sigma, w)
                else:
                    moved += pick != (cell["mode"], cell["model"])
    return moved


def test_no_setting_moves_a_cost_blind_decision(rs, hand, t2_hand):
    assert _premise(rs, hand[3], hand[4], hand[2], "autobench") > 0
    dataset, _rows, _registry, root, matrix = t2_hand[:5]
    _premise(rs, matrix, None, root, dataset)


def test_the_docstring_and_the_note_say_which_cells_are_re_decided(rs):
    doc = " ".join(rs.__doc__.split())
    for phrase in ("re-decides every `cost_effective` cell while each `cost_blind` cell keeps its committed pick "
                   "(v1.438, row T14)", "`routing_cost` is 0.0 outside `cost_effective`",
                   "never a context check"):
        assert phrase in doc, phrase
    method = NOTE.read_text(encoding="utf-8").split("\n## Method\n", 1)[1].split("\n## ", 1)[0]
    assert "only the `cost_effective` cells are re-decided, and a `cost_blind` cell keeps its committed pick " \
           "(v1.438)" in method


def test_the_design_bullet_is_in_12_22():
    text = DESIGN.read_text(encoding="utf-8")
    section = text.split("\n### 12.22 ", 1)[1].split("\n## 13. ", 1)[0]
    bullet = [line for line in section.splitlines() if line.startswith(BULLET)]
    assert len(bullet) == 1
    for phrase in ("`research/reread-sensitivity.md`", "`research/reread_sensitivity.py`", "sigma 1.0 and W = B",
                   "sigma 0, sigma 0.5 and W = 2 B", "13.2 costs", "`## Results` blocks",
                   "or with `--dataset llmrouterbench` (v1.414) or `response-bank` (v1.415) the 13.13 or 13.14 run",
                   "or with `tau2-bench` or `tau2-bench-pooled` (v1.416) the 13.12 run",
                   "pricing each call's re-read of an earlier output at sigma",
                   "then re-decide each `cost_effective` cell (v1.438: no sigma or W moves a `cost_blind` pick) at "
                   "sigma 0, sigma 0.5 and W = 2 B"):
        assert phrase in bullet[0], phrase
    # it points to the 13.1 clause that specifies the README Limitations sentence linking the note
    # (v1.423, row DOC35), as the price-error bullet points to 9 v1.417
    assert bullet[0].endswith("; README Limitations links it (13.1 v1.420)")
    assert bullet[0].count("README Limitations") == 1


# README Limitations: the note's bounds after the brief's-output sentence (v1.420, row DOC33)

def reread_sentence():
    """The README Limitations sentence on the committed delegation results, built from the five blocks."""
    note = NOTE.read_text(encoding="utf-8")
    autobench, _points = _table(_block(note, COMMAND))
    others = {command: _lrb_table(_block(note, command))[0] for command in COMMANDS[1:]}
    tables = [autobench, *others.values()]
    assert len(autobench) == 24 and [len(t) for t in others.values()] == [24, 12, 36, 36]
    # every block runs the three settings the sentence names, and no cost_blind cell changes in any of them
    assert [s[1:] for s in SETTINGS] == [(0.0, 1), (0.5, 1), (1.0, 2)]
    assert all({k[-1] for k in t} == {s[0] for s in SETTINGS} for t in tables)
    assert all(v[0] == 0 for t in tables for k, v in t.items() if "cost_blind" in k)
    # tau2-bench changes no cell, per domain or pooled
    assert all(v[0] == 0 for command in (T2_COMMAND, T2_POOLED_COMMAND) for v in others[command].values())

    def top(rows):
        return max(round(100 * v[0] / v[1], 1) for v in rows.values())

    whole = [v[3] for v in autobench.values()] + [v[5] for t in others.values() for v in t.values()]
    return (
        "The committed delegation results keep both defaults, and re-deciding every cell of them at a re-read "
        "share of 0 and 0.5 and at twice the brief's size for that call's output, each with the other input at "
        "its default ([research/reread-sensitivity.md](research/reread-sensitivity.md)), changes at most "
        f"{top(autobench):.1f}% of the cells of an AutoBench 2026 file, flavor and bar, "
        f"{top(others[LRB_COMMAND]):.1f}% of LLMRouterBench's, {top(others[RB_COMMAND]):.1f}% of the LLM Routing "
        "Response Bank's and none of tau2-bench's, none in `cost_blind`, which compares no costs, and moves the "
        f"cost over all of a file, flavor and bar's cells by a factor of {min(whole):.3f} to {max(whole):.3f}.")


def test_readme_limitations_give_the_bounds_after_the_brief_output_sentence():
    sentence = reread_sentence()
    readme = ROOT.joinpath("README.md").read_text(encoding="utf-8")
    limits = readme.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in limits.split("\n")
               if line.startswith("- The inline-or-delegate cost is a list-price approximation.")]
    assert len(bullets) == 1 and bullets[0].count(sentence) == 1
    # right after the `brief_output_tokens` sentence, which ends at the note calls' depths, and before the
    # cached-read one
    at = bullets[0].index(sentence)
    before = bullets[0][:at]
    assert "`brief_output_tokens` (`--brief-output-tokens`" in before.rsplit(". ", 2)[-2]
    assert re.search(r"at depths \d+ to \d+\. $", before)
    assert bullets[0][at + len(sentence):].startswith(" Prompt caching is costed only")
    # the README links the note in this sentence alone
    assert readme.count("(research/reread-sensitivity.md)") == 1


def test_the_recommendation_says_readme_limitations_link_the_note():
    rec = _section(NOTE.read_text(encoding="utf-8"), "Recommendation")
    assert rec.count("\n- README Limitations' inline-or-delegate cost bullet gives these bounds, after its "
                     "sentences on the two inputs, and links this note") == 1
    assert "as they are" not in rec


def test_design_13_1_states_the_reread_sentence():
    design = DESIGN.read_text(encoding="utf-8")
    s13_1 = design.split("\n### 13.1 Inputs\n", 1)[1].split("\n### 13.2 ", 1)[0]
    clause = (
        "From v1.420 (row DOC33, the Recommendation of the 12.22 v1.413 note) the sentence after that one says "
        "that the committed delegation results keep sigma and W at their defaults and how far re-deciding their "
        "cells at sigma 0, sigma 0.5 and W = 2 B, each with the other input at its default, moves them, from `research/reread-sensitivity.md`, which it "
        "links: the largest share of a file, flavor and bar's cells that changes on AutoBench 2026, "
        "LLMRouterBench and the LLM Routing Response Bank, none on tau2-bench and none in `cost_blind`, which "
        "compares no costs, and the range of the cost over all of a file, flavor and bar's cells as a factor of "
        "the committed picks', each number read by tests/test_research_reread_sensitivity.py from the note's "
        "Results blocks to build the sentence, pinned once in that place; the note's Recommendation says that "
        "README Limitations links it")
    bullet = [line for line in s13_1.split("\n") if line.startswith("- `brief_output_tokens`")]
    assert len(bullet) == 1 and bullet[0].count(clause) == 1
    # beside DOC31's clause, after it
    assert bullet[0].index("From v1.412 (row DOC31)") < bullet[0].index(clause)
    assert bullet[0].endswith(clause)


@pytest.fixture(scope="module")
def output(rs, tmp_path_factory):
    cv = _load("research_reread_autobench_convert", ROOT / "evidence" / "autobench-2026" / "convert.py")
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
    return rs.run(matrix, registry, ROOT)


def test_note_results_block_is_the_script_output(output):
    assert _block(NOTE.read_text(encoding="utf-8"), COMMAND).split("\n") == output


@pytest.fixture(scope="module")
def lrb_output(rs, llmrouterbench_pinned):
    code, _report, path = llmrouterbench_pinned
    assert code == 0
    return rs.run(path, None, ROOT, "llmrouterbench")


def test_note_llmrouterbench_block_is_the_script_output(lrb_output):
    assert _block(NOTE.read_text(encoding="utf-8"), LRB_COMMAND).split("\n") == lrb_output


@pytest.fixture(scope="module")
def rb_output(rs, response_bank_pinned):
    code, _stdout, _stderr, path = response_bank_pinned
    assert code == 0
    return rs.run(path, None, ROOT, "response-bank")


def test_note_response_bank_block_is_the_script_output(rb_output):
    assert _block(NOTE.read_text(encoding="utf-8"), RB_COMMAND).split("\n") == rb_output


@pytest.fixture(scope="module")
def t2_output(rs, tmp_path_factory):
    """The script's lines on the tau2-bench converter's --calls matrices, per domain and pooled, built from the
    12 pinned run files as tests/test_research_per_item_delegation.py builds them."""
    cv = _load("research_reread_tau2_convert", ROOT / "evidence" / "tau2-bench" / "convert.py")
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
        out[dataset] = rs.run(matrix, None, ROOT, dataset)
    return out


@pytest.mark.parametrize("dataset, command", [("tau2-bench", T2_COMMAND), ("tau2-bench-pooled", T2_POOLED_COMMAND)])
def test_note_tau2_blocks_are_the_script_output(t2_output, dataset, command):
    assert _block(NOTE.read_text(encoding="utf-8"), command).split("\n") == t2_output[dataset]
