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
    calls = [dict(r, call_input_tokens=[r["input_tokens"]], call_output_tokens=[r["output_tokens"]])
             for r in rows]
    with pytest.raises(ValueError, match="per-call sizes"):
        pid.tally(calls, registry, full)


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
