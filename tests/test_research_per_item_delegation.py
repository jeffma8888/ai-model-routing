"""research/per-item-delegation.md and research/per_item_delegation.py (DESIGN 13.8 v1.227, row R18).

The script's counts are checked against a brute-force count on a hand-built two-model matrix whose
per-item costs are worked by hand below, including an exact cost tie, and its refusals on a moved
cost, a tiered model and per-call rows. The note's results block is the script's output on the
LLMRouterBench matrix, compared byte for byte when the pinned file is cached (the session fixture
`llmrouterbench_delegation_full` of tests/conftest.py, which CI never fills). v1.227 committed these
tests ahead of the script and the note, every test but the one that reads the DESIGN bullet a
strict xfail; v1.228 lands both and removes the markers.

v1.230 (row R18b) adds the AutoBench 2026 run (`--dataset autobench --registry POOL`): a hand-built
matrix run end to end through `main` against a root whose committed 13.10 summary is that matrix's,
the usage errors, the title line, and the note's AutoBench block, compared byte for byte when the
pinned AutoBench files are cached. v1.230 committed these ahead of the script change and the
note, each a strict xfail but the one that reads the v1.230 bullet; v1.231 lands both and
removes the markers.

v1.233 (row R18c) adds the two tau2-bench runs (`--dataset tau2-bench` and `tau2-bench-pooled`),
whose rows carry per-call sizes: the 13.9 v1.74 per-call costs on a hand-built per-call matrix with
an exact cost tie at each of the parent's call counts, checked by brute force on integer cost
numerators; one-call rows tallied as the rows without the keys; both runs end to end through `main`
against a root whose committed 13.12 files are the hand matrix's; and the note's two tau2-bench
blocks, compared byte for byte when the 12 pinned tau2-bench files are cached. v1.233 commits these
ahead of the script change and the note, each a strict xfail but the one that reads the v1.233
bullet, and drops the v1.227 refusal of per-call rows from `test_refusals`; v1.234 lands both and
removes the markers, and moves the one-call tie to a held-out item with a delegate record that
differs from the parent's on both ties, so a tie taken on the wrong path changes the success.
"""

import contextlib
import copy
import dataclasses
import importlib.util
import io
import json
import re
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation, split_items
from model_routing.registry import PriceTier

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "per_item_delegation.py"
NOTE = ROOT / "research" / "per-item-delegation.md"
INDEX = ROOT / "research" / "README.md"
DESIGN = ROOT / "DESIGN.md"
REGISTRY = ROOT / "evidence" / "llmrouterbench-delegation" / "registry.json"
COMMAND = "$ python research/per_item_delegation.py --matrix llmrouterbench-matrix.jsonl"

# --- the hand-built matrix --------------------------------------------------------------------
# Parent v/p at 1 and 2 USD per million input and output tokens, delegate v/d at 1 and 1. One
# folded point, C = 0, B = R = 10, T = 0, so by 13.9 for a single-call row:
#   inline(j)   = p(0 + 10, x) + 0 * p(...)      = (10 + 2x) / 1e6, x = j % 40 the parent's output
#   delegate(j) = p(0, 10) + d(10 + 10, 20) + 1 * p(20, 0) = (20 + 40 + 20) / 1e6 = 80 / 1e6
# so inline is cheaper for x < 35, dearer for x > 35, and ties exactly at x = 35 (checked below).
# The parent is right on j % 4 != 0, the delegate on j % 5 != 0. A cell whose delegate is the
# parent itself pays delegate(j) = p(0, 10) + p(10 + 10, x) + p(20, 0) = (60 + 2x) / 1e6, so
# there inline is cheaper on every item.
P = Model("v/p", "fam-p", 1.0, 2.0, 1_000_000)
D = Model("v/d", "fam-d", 1.0, 1.0, 1_000_000)
POINT = {"context_tokens": 0, "brief_tokens": 10, "result_tokens": 10, "carry_turns": 0,
         "inline_separate_call": False}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows():
    rows = []
    for j in range(80):
        rows.append({"task": "t", "item": f"i{j:02d}", "model": "v/p", "correct": j % 4 != 0,
                     "input_tokens": 10, "output_tokens": j % 40})
        rows.append({"task": "t", "item": f"i{j:02d}", "model": "v/d", "correct": j % 5 != 0,
                     "input_tokens": 10, "output_tokens": 20})
    return rows


@pytest.fixture(scope="module")
def pid():
    return _load("research_per_item_delegation", SCRIPT)


@pytest.fixture(scope="module")
def tiny():
    registry = Registry([P, D])
    rows = _rows()
    full = evaluate_delegation(rows, registry, bars=[0.5], points=[POINT], seeds=range(3),
                               min_samples=10, parents=["v/p"])
    return rows, registry, full


def test_design_bullet_states_the_rule():
    text = DESIGN.read_text(encoding="utf-8")
    section = text.split("### 13.8 ", 1)[1].split("### 13.9 ", 1)[0]
    bullet = [line for line in section.splitlines() if line.startswith("- v1.227, per-item delegation paths")]
    assert len(bullet) == 1
    b = bullet[0]
    for phrase in ("`research/per_item_delegation.py`", "`research/per-item-delegation.md`",
                   "the cell's mode on an exact tie", "`pick` on every cell",
                   "`delegate_cheaper` or `inline_cheaper`", "fails unless the run's `summary` equals",
                   "No library code", "a later backlog row", "row R18"):
        assert phrase in b, phrase


def test_hand_costs_and_the_tie(pid):
    assert [pid._inline(P, POINT, 10, x) for x in (34, 35, 36)] == [78 / 1e6, 80 / 1e6, 82 / 1e6]
    assert pid._delegate(P, D, POINT, 10, 20) == 80 / 1e6
    assert pid._inline(P, POINT, 10, 35) == pid._delegate(P, D, POINT, 10, 20)


def _brute(rows, full):
    """Per (flavor, strategy): switched and held-out items, by the rule on x = j % 40 alone."""
    held = {s: split_items([f"i{j:02d}" for j in range(80)], s, 0.5)[1] for s in range(3)}
    out = {}
    for c in full["cells"]:
        for s in ("pick", "size rule"):
            if s == "size rule" and c["reason"] not in ("delegate_cheaper", "inline_cheaper"):
                continue
            xs = [int(i[1:]) % 40 for i in held[c["seed"]]]
            if c["delegate"] == "v/p":
                n = 0 if c["mode"] == "inline" else len(xs)
            else:
                n = sum(x > 35 for x in xs) if c["mode"] == "inline" else sum(x < 35 for x in xs)
            acc = out.setdefault((c["flavor"], s), [0, 0])
            acc[0] += n
            acc[1] += len(xs)
    return out


def test_switched_counts_are_the_brute_force_ones(pid, tiny):
    rows, registry, full = tiny
    out, pairs = pid.tally(rows, registry, full)
    # one pair per (task, point, parent, delegate, seed): 6 cells, the two flavors of a seed sharing
    # the delegate v/d on seeds 0 and 1, while on seed 2 `cost_blind` delegates to the parent itself
    assert pairs == len({(c["task"], c["point"], c["parent"], c["delegate"], c["seed"])
                         for c in full["cells"]}) == 4
    assert sorted((c["flavor"], c["seed"], c["delegate"], c["mode"]) for c in full["cells"]) == [
        ("cost_blind", 0, "v/d", "delegate"), ("cost_blind", 1, "v/d", "delegate"),
        ("cost_blind", 2, "v/p", "inline"), ("cost_effective", 0, "v/d", "inline"),
        ("cost_effective", 1, "v/d", "inline"), ("cost_effective", 2, "v/d", "inline")]
    got = {}
    for (_bar, flavor, _point, _parent), row in out.items():
        for s in ("pick", "size rule"):
            acc = got.setdefault((flavor, s), [0, 0])
            acc[0] += row[s]["switched"]
            acc[1] += row[s]["items"]
    brute = _brute(rows, full)
    assert {k: v for k, v in got.items() if v[1]} == brute
    # every cost_effective cell compares costs (inline cheaper at the mean sizes), no cost_blind one
    assert all(c["reason"] == "inline_cheaper" for c in full["cells"] if c["flavor"] == "cost_effective")
    assert got["cost_blind", "size rule"] == [0, 0]


def test_decision_rows_are_the_summary_and_pick_is_a_cost_floor(pid, tiny):
    rows, registry, full = tiny
    out, _ = pid.tally(rows, registry, full)
    summary = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r for r in full["summary"]}
    for key, row in out.items():
        assert (row["decision"]["success"], row["decision"]["cost_usd"]) == (
            summary[key + ("decision",)]["success"], summary[key + ("decision",)]["cost_usd"])
        floor = min(summary[key + ("inline",)]["cost_usd"], summary[key + ("delegate",)]["cost_usd"])
        assert row["pick"]["cost_usd"] <= floor + 1e-15
        assert row["pick"]["cost_usd"] <= row["size rule"]["cost_usd"] <= row["decision"]["cost_usd"] + 1e-15


def test_report_lines(pid, tiny):
    rows, registry, full = tiny
    lines = pid.report(rows, registry, full)
    assert lines[1] == ("matrix: 160 rows, 80 items, 1 task, 2 models; 6 cells, 4 path pairs rebuilt, "
                        "each equal to its cell's inline and delegate costs and correct counts")
    assert lines[2] == pid.HEADER
    assert len(lines) == 3 + 2 * 1 * 2 + 2 + 2 * 2
    assert lines[3].split()[:3] == ["cost_effective", "0.5", "pick"]
    blind_rule = lines[6].split()
    assert blind_rule[:4] == ["cost_blind", "0.5", "size", "rule"] and blind_rule[4:] == [
        "0", "0", "/", "0", "-", "1.0000", "+0.0000", "0"]
    assert lines[-1] == "  largest cost cut at no less success, size rule, cost_blind: no row"


def test_refusals(pid, tiny):
    rows, registry, full = tiny
    moved = copy.deepcopy(full)
    moved["cells"][0]["cost_usd"]["inline"] += 1e-12
    with pytest.raises(ValueError, match="rebuilt costs are not the cell's"):
        pid.tally(rows, registry, moved)
    recount = copy.deepcopy(full)
    recount["cells"][0]["correct"]["delegate"] += 1
    with pytest.raises(ValueError, match="rebuilt correct counts"):
        pid.tally(rows, registry, recount)
    tiered = Registry([dataclasses.replace(P, price_tiers=(PriceTier(200_000, 2.0, 4.0),)), D])
    with pytest.raises(ValueError, match="price tiers"):
        pid.tally(rows, tiered, full)


def test_main_exits_2_with_one_error_line(pid, tmp_path):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert pid.main(["--matrix", str(tmp_path / "missing.jsonl")]) == 2
    assert err.getvalue().startswith("error: ") and err.getvalue().count("\n") == 1


def test_note_states_the_rule_first_and_is_indexed():
    note = NOTE.read_text(encoding="utf-8")
    assert note.startswith("# ") and "\n## Facts\n" in note
    method = note.index("## Method")
    assert method < note.index("## Results") and not re.search(r"\d\.\d{4}", note[:method])
    assert COMMAND in note and "evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl" in note
    assert "(research/per-item-delegation.md)" in INDEX.read_text(encoding="utf-8") or \
        "`research/per-item-delegation.md`" in INDEX.read_text(encoding="utf-8")


def test_note_results_block_is_the_script_output(pid, llmrouterbench_delegation_full):
    kept, _dropped, full = llmrouterbench_delegation_full
    lines = pid.report(kept, Registry.load(REGISTRY), full)
    note = NOTE.read_text(encoding="utf-8")
    block = note.split(COMMAND + "\n", 1)[1].split("\n```", 1)[0]
    assert block.split("\n") == lines



def test_pick_and_size_rule_success_and_cost_are_the_brute_force_ones(pid, tiny):
    """Each row's strategies by hand: x = j % 40, inline (10 + 2x) / 1e6 against 80 / 1e6 to v/d or
    (60 + 2x) / 1e6 to the parent itself, compared on the integer numerators, the mode on a tie;
    success is the parent's record on inline and the delegate's on delegate, as 13.9 averages it."""
    rows, registry, full = tiny
    out, _ = pid.tally(rows, registry, full)
    held = {s: split_items([f"i{j:02d}" for j in range(80)], s, 0.5)[1] for s in range(3)}
    want = {}
    for c in full["cells"]:
        right, costs = 0, []
        for item in held[c["seed"]]:
            j = int(item[1:])
            x = j % 40
            ci = 10 + 2 * x
            cd = 80 if c["delegate"] == "v/d" else 60 + 2 * x
            inline = ci < cd or (ci == cd and c["mode"] == "inline")
            ok = (j % 4 != 0) if inline or c["delegate"] == "v/p" else (j % 5 != 0)
            right += ok
            costs.append(min(ci, cd) / 1e6)
        pick = (right / len(held[c["seed"]]), sum(costs))
        decision = (c["success"]["decision"], c["cost_usd"]["decision"])
        key = (c["bar"], c["flavor"], c["point"], c["parent"])
        rule = pick if c["reason"] in ("delegate_cheaper", "inline_cheaper") else decision
        for s, pair in (("pick", pick), ("size rule", rule)):
            want.setdefault((key, s), []).append(pair)
    for (key, s), pairs in want.items():
        assert out[key][s]["success"] == pytest.approx(sum(p[0] for p in pairs) / 3, rel=1e-12)
        assert out[key][s]["cost_usd"] == pytest.approx(sum(p[1] for p in pairs) / 3, rel=1e-12)
    # the hand matrix moves both: pick differs from the decision in success and cost in each flavor
    for (key, s), pairs in want.items():
        if s == "pick":
            assert out[key]["pick"]["success"] != out[key]["decision"]["success"]
            assert out[key]["pick"]["cost_usd"] < out[key]["decision"]["cost_usd"]


# --- v1.230 (row R18b): the AutoBench 2026 run ------------------------------------------------
AB_COMMAND = ("$ python research/per_item_delegation.py --dataset autobench --matrix autobench-tokens.jsonl"
              " --registry autobench-pool.json")
AB_FOLDER = ROOT / "evidence" / "delegation"
AB_CONVERT = ("python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens"
              " --registry autobench-pool.json")


def test_design_bullet_v1230_states_the_autobench_run():
    text = DESIGN.read_text(encoding="utf-8")
    section = text.split("### 13.8 ", 1)[1].split("### 13.9 ", 1)[0]
    bullet = [line for line in section.splitlines()
              if line.startswith("- v1.230, per-item delegation paths on AutoBench: ")]
    assert len(bullet) == 1
    for phrase in ("`--dataset NAME`", "`--registry POOL`", "`evidence/delegation/results.py`",
                   "`evidence/delegation/results.json`", "refuses `--registry`", "`AutoBench 2026`",
                   "LLMRouterBench's unchanged", "row R18b", "No library code"):
        assert phrase in bullet[0], phrase


def test_report_title_names_the_dataset(pid, tiny):
    rows, registry, full = tiny
    default = pid.report(rows, registry, full)
    assert default[0].startswith("Per-item delegation paths on LLMRouterBench: ")
    lines = pid.report(rows, registry, full, name="AutoBench 2026")
    assert lines[0] == ("Per-item delegation paths on AutoBench 2026: each held-out item's cheaper path by "
                        "list price at its own sizes, against the per-task decision")
    assert lines[1:] == default[1:]


def _registry_file(path, models):
    entries = [dict(dataclasses.asdict(m), source="https://example.org/prices") for m in models]
    for e in entries:
        if not e["price_tiers"]:
            del e["price_tiers"]
    path.write_text(json.dumps({"version": "1", "as_of": "2026-01-01", "currency": "USD",
                                "models": entries}), encoding="utf-8")
    return path


def _autobench_root(tmp_path, rows, registry):
    """A root holding the 13.10 script and the results.json it writes from the hand matrix."""
    dr = _load("research_pid_autobench_results", AB_FOLDER / "results.py")
    folder = tmp_path / "root" / "evidence" / "delegation"
    folder.mkdir(parents=True)
    (folder / "results.py").write_text((AB_FOLDER / "results.py").read_text(encoding="utf-8"),
                                       encoding="utf-8")
    results = folder / "results.json"
    results.write_text(json.dumps(dr.run(rows, registry), indent=2) + "\n", encoding="utf-8")
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return dr, tmp_path / "root", matrix, _registry_file(tmp_path / "pool.json", registry.models), results


def test_autobench_run_on_a_hand_matrix(pid, tmp_path):
    rows, registry = _rows(), Registry([P, D])
    dr, root, matrix, pool, results = _autobench_root(tmp_path, rows, registry)
    argv = ["--dataset", "autobench", "--matrix", str(matrix), "--registry", str(pool), "--root", str(root)]
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert pid.main(argv) == 0
    full = evaluate_delegation(rows, registry, bars=list(dr.BARS), points=dr.points(), seeds=range(dr.SEEDS))
    want = pid.report(rows, registry, full, name="AutoBench 2026")
    assert out.getvalue() == "\n".join(want) + "\n"
    assert want[0].startswith("Per-item delegation paths on AutoBench 2026: ")
    assert want[1].startswith("matrix: 160 rows, 80 items, 1 task, 2 models; 1,600 cells, ")
    # a committed summary that the run does not give stops it
    moved = json.loads(results.read_text(encoding="utf-8"))
    moved["summary"][0]["cost_usd"] += 1e-12
    results.write_text(json.dumps(moved, indent=2) + "\n", encoding="utf-8")
    err = io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        assert pid.main(argv) == 2
    assert err.getvalue() == "error: the run's summary is not the one in evidence/delegation/results.json\n"


@pytest.mark.parametrize("argv, message", [
    (["--dataset", "autobench", "--matrix", "m.jsonl"], "--dataset autobench needs --registry"),
    (["--matrix", "m.jsonl", "--registry", "r.json"], "--registry is only used with --dataset autobench"),
])
def test_dataset_usage_errors(pid, argv, message):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert pid.main(argv) == 2
    assert err.getvalue() == f"error: {message}\n"


def test_note_has_both_blocks_and_the_autobench_regenerate():
    note = NOTE.read_text(encoding="utf-8")
    assert note.count("```text\n" + COMMAND + "\n") == 1
    assert note.count("```text\n" + AB_COMMAND + "\n") == 1
    assert note.index(COMMAND) < note.index(AB_COMMAND) < note.index("## Reading it")
    regenerate = note.split("## Regenerate", 1)[1]
    assert AB_CONVERT in regenerate and AB_COMMAND[2:] in regenerate


def test_note_autobench_block_is_the_script_output(pid, tmp_path):
    cv = _load("research_pid_autobench_convert", ROOT / "evidence" / "autobench-2026" / "convert.py")
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("pinned AutoBench files are not in the default cache")
    for name, (size, sha) in cv.FILES.items():
        cv.verify(folder / name, size, sha)
    params = json.loads((folder / "frozen_params.json").read_text(encoding="utf-8"))
    pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
    rows, _report = cv.convert(cv.read_csv(folder / "matrix.csv"), cv.read_csv(folder / "questions.csv"),
                               pool, params["delta_signal"], params["top_k"], task_by="all", tokens=True)
    matrix = tmp_path / "autobench-tokens.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    registry = tmp_path / "autobench-pool.json"
    registry.write_text(json.dumps(cv.pool_registry(pool)), encoding="utf-8")
    lines = pid.run(matrix, ROOT, dataset="autobench", registry=registry)
    note = NOTE.read_text(encoding="utf-8")
    block = note.split(AB_COMMAND + "\n", 1)[1].split("\n```", 1)[0]
    assert block.split("\n") == lines


# --- v1.233 (row R18c): the tau2-bench runs, rows with per-call sizes -------------------------
T2_FOLDER = ROOT / "evidence" / "tau2-bench-delegation"
T2_COMMAND = "$ python research/per_item_delegation.py --dataset tau2-bench --matrix tau2-calls.jsonl"
T2_POOLED_COMMAND = "$ python research/per_item_delegation.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl"
T2_CONVERT = "python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls"
T2_POOLED_CONVERT = "python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all"


def _call_row(task, item, model, correct, a, b):
    """A 13.9 v1.74 per-call row whose counts are what its calls read (Rd) and write (O)."""
    k = len(a)
    rd = sum((k - j) * a[j] + (k - j - 1) * b[j] for j in range(k))
    return {"task": task, "item": item, "model": model, "correct": correct, "input_tokens": rd,
            "output_tokens": sum(b), "call_input_tokens": list(a), "call_output_tokens": list(b)}


# The hand-built per-call matrix, at P, D and POINT above (C = 0, B = R = 10, T = 0, folded), by
# 13.9 v1.74 for a model without tiers, x = j % 40:
#   parent, j >= 40, one call a = [10], b = [2x]: K = 1, Rd = 10, A = 10, O = 2x, so
#     inline(j) = p((1 - 1) * 0 + 10, 2x) + 0 * p(...)  = (10 + 4x) / 1e6
#   parent, j < 40, two calls a = [10, 0], b = [x, x]: K = 2, Rd = 2 * 10 + 0 + x = 20 + x, O = 2x,
#     inline(j) = p((2 - 1) * 0 + 20 + x, 2x)           = (20 + 5x) / 1e6
#   delegate v/d, two calls a = [5, 0], b = [5, 10]: K = 2, Rd = 2 * 5 + 0 + 5 = 15, O = 15,
#     delegate(j) = p(0, 10) + d(2 * 10 + 15, 15) + 1 * p(20, 0) = (20 + 50 + 20) / 1e6 = 90 / 1e6
# so the cost ties exactly at x = 20 with one call (j = 60) and at x = 14 with two (j = 14), both
# exact in floating point (checked below) and both held out on some seed of 0 to 2. A cell whose delegate is the parent itself pays
#   p(0, 10) + p(10K + Rd, O) + p(20, 0) = (40 + 10K + Rd + 2O) / 1e6: (60 + 4x) / 1e6 or (80 + 5x) / 1e6,
# so there inline is cheaper on every item. The parent is right on j % 4 != 0, the delegate on j % 7 != 0,
# so the two records differ on both ties (i14: right inline only, i60: right delegated only).
def _call_rows(task=lambda j: "t"):
    rows = []
    for j in range(80):
        x = j % 40
        a, b = ([10, 0], [x, x]) if j < 40 else ([10], [2 * x])
        rows.append(_call_row(task(j), f"i{j:02d}", "v/p", j % 4 != 0, a, b))
        rows.append(_call_row(task(j), f"i{j:02d}", "v/d", j % 7 != 0, [5, 0], [5, 10]))
    return rows


def _numerators(j, delegate):
    """(inline, delegate) cost of item j in millionths of a USD, by the hand expressions above."""
    x = j % 40
    if j >= 40:
        return 10 + 4 * x, (90 if delegate == "v/d" else 60 + 4 * x)
    return 20 + 5 * x, (90 if delegate == "v/d" else 80 + 5 * x)


def test_design_bullet_v1233_states_the_tau2_runs():
    text = DESIGN.read_text(encoding="utf-8")
    section = text.split("### 13.8 ", 1)[1].split("### 13.9 ", 1)[0]
    bullet = [line for line in section.splitlines()
              if line.startswith("- v1.233, per-item delegation paths on tau2-bench: ")]
    assert len(bullet) == 1
    for phrase in ("`tau2-bench-pooled`", "`evidence/tau2-bench-delegation/results.py`", "`pooled.json`",
                   "`--calls --task-by all`", "13.9 v1.74", "refuse `--registry`", "no longer refused",
                   "`tau2-bench per domain`", "`tau2-bench pooled`", "an exact cost tie", "row R18c",
                   "No library code"):
        assert phrase in bullet[0], phrase


def test_per_call_hand_costs_and_the_ties(pid):
    assert pid._calls({"call_input_tokens": [1, 9], "call_output_tokens": [2, 2]}) == (2, 13, 10, 4)
    assert pid._calls({"input_tokens": 3, "output_tokens": 4}) is None
    one = [pid._inline_calls(P, POINT, 1, 10, 10, 2 * x) for x in (19, 20, 21)]
    two = [pid._inline_calls(P, POINT, 2, 20 + x, 10, 2 * x) for x in (13, 14, 15)]
    assert one == [86 / 1e6, 90 / 1e6, 94 / 1e6] and two == [85 / 1e6, 90 / 1e6, 95 / 1e6]
    assert pid._delegate_calls(P, D, POINT, 2, 15, 15) == 90 / 1e6 == one[1] == two[1]
    # a separate inline call at C = 100 reads K * C first; the cached ratio prices only that read
    sep = dict(POINT, context_tokens=100, inline_separate_call=True, carry_turns=1)
    assert pid._inline_calls(P, sep, 2, 34, 10, 28) == P.base_cost(200 + 34, 28) + 2 * P.base_cost(38, 0)
    cached = dict(sep, cached_read_ratio=0.5)
    assert pid._inline_calls(P, cached, 2, 34, 10, 28) == P.base_cost(100.0 + 34, 28) + 2 * P.base_cost(38, 0)
    assert pid._delegate_calls(P, D, sep, 2, 15, 15) == (P.base_cost(0, 10) + D.base_cost(35, 15)
                                                         + 2 * P.base_cost(20, 0))


@pytest.fixture(scope="module")
def tiny_calls():
    registry = Registry([P, D])
    rows = _call_rows()
    full = evaluate_delegation(rows, registry, bars=[0.5], points=[POINT], seeds=range(3),
                               min_samples=10, parents=["v/p"])
    return rows, registry, full


def test_per_call_tally_is_the_brute_force_one(pid, tiny_calls):
    rows, registry, full = tiny_calls
    out, pairs = pid.tally(rows, registry, full)
    assert pairs == len({(c["task"], c["point"], c["parent"], c["delegate"], c["seed"])
                         for c in full["cells"]}) == 3
    # every cell delegates to v/d, so the two ties stay delegated: by cost in cost_effective (13.5
    # row 3, which `size rule` may change), by success in cost_blind (which it keeps)
    assert sorted((c["flavor"], c["seed"], c["delegate"], c["mode"], c["reason"]) for c in full["cells"]) == [
        ("cost_blind", 0, "v/d", "delegate", "delegate_better"),
        ("cost_blind", 1, "v/d", "delegate", "delegate_better"),
        ("cost_blind", 2, "v/d", "delegate", "delegate_better"),
        ("cost_effective", 0, "v/d", "delegate", "delegate_cheaper"),
        ("cost_effective", 1, "v/d", "delegate", "delegate_cheaper"),
        ("cost_effective", 2, "v/d", "delegate", "delegate_cheaper")]
    held = {s: split_items([f"i{j:02d}" for j in range(80)], s, full["config"]["calibration_fraction"])[1]
            for s in range(3)}
    ties = {item for c in full["cells"] if c["mode"] == "delegate" for item in held[c["seed"]]
            if _numerators(int(item[1:]), c["delegate"])[0] == _numerators(int(item[1:]), c["delegate"])[1]}
    assert ties == {"i14", "i60"}
    want = {}
    for c in full["cells"]:
        right, costs, switched = 0, [], 0
        for item in held[c["seed"]]:
            j = int(item[1:])
            ci, cd = _numerators(j, c["delegate"])
            inline = ci < cd or (ci == cd and c["mode"] == "inline")
            switched += inline != (c["mode"] == "inline")
            right += (j % 4 != 0) if inline or c["delegate"] == "v/p" else (j % 7 != 0)
            costs.append(min(ci, cd) / 1e6)
        n = len(held[c["seed"]])
        pick = (right / n, sum(costs), switched, n)
        key = (c["bar"], c["flavor"], c["point"], c["parent"])
        compared = c["reason"] in ("delegate_cheaper", "inline_cheaper")
        rule = pick if compared else (c["success"]["decision"], c["cost_usd"]["decision"], 0, 0)
        for s, four in (("pick", pick), ("size rule", rule)):
            want.setdefault((key, s), []).append(four)
    for (key, s), fours in want.items():
        assert out[key][s]["switched"] == sum(f[2] for f in fours)
        assert out[key][s]["items"] == sum(f[3] for f in fours)
        assert out[key][s]["success"] == pytest.approx(sum(f[0] for f in fours) / 3, rel=1e-12)
        assert out[key][s]["cost_usd"] == pytest.approx(sum(f[1] for f in fours) / 3, rel=1e-12)
    effective = (0.5, "cost_effective", 0, "v/p")
    assert out[effective]["pick"]["switched"] > 0
    assert out[effective]["pick"]["cost_usd"] < out[effective]["decision"]["cost_usd"]


def test_one_call_rows_tally_as_the_rows_without_the_keys(pid, tiny):
    rows, registry, full = tiny
    calls = [dict(r, call_input_tokens=[r["input_tokens"]], call_output_tokens=[r["output_tokens"]])
             for r in rows]
    assert pid.tally(calls, registry, full) == pid.tally(rows, registry, full)


def _tau2_root(tmp_path, registry):
    """A root holding the 13.12 and 13.10 scripts, a registry and the results.json and pooled.json
    that the 13.12 script writes from the hand per-call matrix, per domain (two tasks) and pooled."""
    td = _load("research_pid_tau2_results", T2_FOLDER / "results.py")
    root = tmp_path / "root"
    for folder in ("tau2-bench-delegation", "delegation"):
        (root / "evidence" / folder).mkdir(parents=True)
        (root / "evidence" / folder / "results.py").write_text(
            (ROOT / "evidence" / folder / "results.py").read_text(encoding="utf-8"), encoding="utf-8")
    folder = root / "evidence" / "tau2-bench-delegation"
    _registry_file(folder / "registry.json", registry.models)
    runs = {}
    for name, rows in (("results.json", _call_rows(lambda j: "t1" if j % 2 else "t2")),
                       ("pooled.json", _call_rows(lambda j: "all"))):
        (folder / name).write_text(json.dumps(td.run(rows, registry), indent=2) + "\n", encoding="utf-8")
        matrix = tmp_path / ("all.jsonl" if name == "pooled.json" else "domain.jsonl")
        matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        runs[name] = (rows, matrix)
    return td, root, runs


def test_tau2_runs_on_a_hand_root(pid, tmp_path):
    registry = Registry([P, D])
    td, root, runs = _tau2_root(tmp_path, registry)
    for dataset, name, title in (("tau2-bench", "results.json", "tau2-bench per domain"),
                                 ("tau2-bench-pooled", "pooled.json", "tau2-bench pooled")):
        rows, matrix = runs[name]
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            assert pid.main(["--dataset", dataset, "--matrix", str(matrix), "--root", str(root)]) == 0
        full = evaluate_delegation(rows, registry, bars=list(td.BARS), points=td.points(), seeds=range(td.SEEDS))
        want = pid.report(rows, registry, full, name=title)
        assert out.getvalue() == "\n".join(want) + "\n"
        assert want[0].startswith(f"Per-item delegation paths on {title}: ")
        tasks = "2 tasks" if name == "results.json" else "1 task"
        assert want[1].startswith(f"matrix: 160 rows, 80 items, {tasks}, 2 models; ")
    # each run checks the summary of its own file: the per-domain matrix is not the pooled run
    err = io.StringIO()
    argv = ["--dataset", "tau2-bench-pooled", "--matrix", str(runs["results.json"][1]), "--root", str(root)]
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(io.StringIO()):
        assert pid.main(argv) == 2
    assert err.getvalue() == "error: the run's summary is not the one in evidence/tau2-bench-delegation/pooled.json\n"


@pytest.mark.parametrize("dataset", ["tau2-bench", "tau2-bench-pooled"])
def test_tau2_runs_refuse_a_registry(pid, dataset):
    err = io.StringIO()
    with contextlib.redirect_stderr(err):
        assert pid.main(["--dataset", dataset, "--matrix", "m.jsonl", "--registry", "r.json"]) == 2
    assert err.getvalue() == "error: --registry is only used with --dataset autobench\n"


def test_note_has_the_tau2_blocks_regenerate_and_a_three_dataset_recommendation():
    note = NOTE.read_text(encoding="utf-8")
    for command in (T2_COMMAND, T2_POOLED_COMMAND):
        assert note.count("```text\n" + command + "\n") == 1
    assert note.index(AB_COMMAND) < note.index(T2_COMMAND) < note.index(T2_POOLED_COMMAND) < note.index("## Reading it")
    regenerate = note.split("## Regenerate", 1)[1]
    for line in (T2_CONVERT, T2_COMMAND[2:], T2_POOLED_CONVERT, T2_POOLED_COMMAND[2:]):
        assert line in regenerate, line
    recommendation = note.split("## Recommendation", 1)[1].split("## Regenerate", 1)[0]
    for name in ("LLMRouterBench", "AutoBench 2026", "tau2-bench"):
        assert name in recommendation, name
    assert "not measured yet" not in INDEX.read_text(encoding="utf-8")


@pytest.fixture(scope="module")
def tau2_matrices():
    """The tau2-bench converter's --calls matrices, per domain and pooled, from the 12 pinned files."""
    cv = _load("research_pid_tau2_convert", ROOT / "evidence" / "tau2-bench" / "convert.py")
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("the 12 pinned tau2-bench run files are not in the default cache")
    extracts = []
    for n, (size, sha) in cv.FILES.items():
        cv.verify(folder / n, size, sha)
        extracts.append(cv.extract(cv.read_run(folder / n), trial=0, tokens=True, calls=True))
    return {"tau2-bench": cv.convert(extracts)[0], "tau2-bench-pooled": cv.convert(extracts, task_by="all")[0]}


@pytest.mark.parametrize("dataset, command", [("tau2-bench", T2_COMMAND), ("tau2-bench-pooled", T2_POOLED_COMMAND)])
def test_note_tau2_blocks_are_the_script_output(pid, tau2_matrices, tmp_path, dataset, command):
    matrix = tmp_path / "tau2.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in tau2_matrices[dataset]), encoding="utf-8")
    lines = pid.run(matrix, ROOT, dataset=dataset)
    note = NOTE.read_text(encoding="utf-8")
    block = note.split(command + "\n", 1)[1].split("\n```", 1)[0]
    assert block.split("\n") == lines
