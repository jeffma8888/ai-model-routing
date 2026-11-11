"""research/per-item-delegation.md and research/per_item_delegation.py (DESIGN 13.8 v1.227, row R18).

The script's counts are checked against a brute-force count on a hand-built two-model matrix whose
per-item costs are worked by hand below, including an exact cost tie, and its refusals on a moved
cost, a tiered model and per-call rows. The note's results block is the script's output on the
LLMRouterBench matrix, compared byte for byte when the pinned file is cached (the session fixture
`llmrouterbench_delegation_full` of tests/conftest.py, which CI never fills). v1.227 committed these
tests ahead of the script and the note, every test but the one that reads the DESIGN bullet a
strict xfail; v1.228 lands both and removes the markers.
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
        for s in ("decision", "inline", "delegate")[:1]:
            assert (row[s]["success"], row[s]["cost_usd"]) == (summary[key + (s,)]["success"],
                                                               summary[key + (s,)]["cost_usd"])
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
