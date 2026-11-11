"""research/delegation_reasons.py and its section of research/where-delegation-pays.md (DESIGN 13.8 v1.253, row R19).

The script counts each 13.9 run's cells per (flavor, point) by the 13.5 row and reason that chose
their path, after a condition from 13.2: with inline work in a call of its own, a separate inline
call costs more than delegating at every size when `slack * p_in > B * p_out`, with
`slack = K * (rho * C - B) - (1 + T) * (B + R)`. The tests run it on a hand-built matrix on which
13.5 rows 1, 2, 3, 4, 5 and 7 each choose at least once (the cells are worked by hand in
`HAND_LINES` below), check the condition at hand-worked points and at its strict boundary, and on
every `cost_effective` cell of that run, and compare the note's four results blocks with the
script's output where the pinned files are cached. v1.253 commits them ahead of the script and the
note, each a strict xfail but the one that reads the DESIGN bullet.
"""

import collections
import contextlib
import dataclasses
import importlib.util
import io
import json
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation
from model_routing.registry import PriceTier

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "delegation_reasons.py"
NOTE = ROOT / "research" / "where-delegation-pays.md"
DESIGN = ROOT / "DESIGN.md"
SECTION = "## Which 13.5 row chose"
COMMANDS = {
    "llmrouterbench": "$ python research/delegation_reasons.py --matrix llmrouterbench-matrix.jsonl",
    "autobench": ("$ python research/delegation_reasons.py --dataset autobench --matrix autobench-tokens.jsonl"
                  " --registry autobench-pool.json"),
    "tau2-bench": "$ python research/delegation_reasons.py --dataset tau2-bench --matrix tau2-calls.jsonl",
    "tau2-bench-pooled": "$ python research/delegation_reasons.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl",
}
NOT_YET = pytest.mark.xfail(strict=True, raises=FileNotFoundError,
                            reason="v1.253: research/delegation_reasons.py lands in v1.254")

# Prices per 1M tokens. good and small answer every item of task t; on task u only small does; bad
# answers none. small's window is 1,000 tokens, so it is full at point 1 (row 1) and, at point 2,
# whose brief is 2,000 tokens, it is out of the delegate's select, which makes it the only model
# that clears u there (row 5) and leaves no passing delegate for the other parents on u (row 7).
GOOD = Model("v/good", "fam-g", 1.0, 2.0, 1_000_000)
BAD = Model("v/bad", "fam-b", 0.5, 2.0, 1_000_000)
SMALL = Model("v/small", "fam-s", 2.0, 4.0, 1_000)
POINTS = [
    {"context_tokens": 100, "brief_tokens": 10, "result_tokens": 10, "carry_turns": 0, "inline_separate_call": True},
    {"context_tokens": 5000, "brief_tokens": 10, "result_tokens": 10, "carry_turns": 0, "inline_separate_call": True},
    {"context_tokens": 0, "brief_tokens": 2000, "result_tokens": 0, "carry_turns": 0, "inline_separate_call": True},
    {"context_tokens": 100, "brief_tokens": 10, "result_tokens": 10, "carry_turns": 0, "inline_separate_call": False},
]
RIGHT = {("t", "v/good"), ("t", "v/small"), ("u", "v/small")}

# Worked by hand (each cost in tokens times the price per 1M tokens; S_in = S_out = 10 for every model):
# point 0, cost_effective: good on t delegates to good, 80 against 150 inline; small on t to good,
# 120 against 300; small on u to small, 160 against 300; the three other (parent, task) pairs are
# below the bar with a passing delegate (row 2). Point 1: small is full (row 1). Point 2: good on t
# and small on t are inline_cheaper (50 against 8,030; 100 against 14,030), small on u is
# only_parent_clears, and good and bad on u fall to row 7 with bad, the cheaper at the equal bound
# 0, as the primary, 7,025 and 6,025 against 50 and 35 inline, so inline. Point 3 (folded): inline
# costs 30, 60 and 60 against 80, 120 and 160. cost_blind ties every bound of good and small, so
# both stay inline (row 4) where both clear.
HAND_LINES = [
    "Which 13.5 row chose each cell's path on hand: the cells of the 13.9 run by flavor, point, row and reason",
    "run: 96 cells (1 bar, 2 flavors, 4 points, 3 parents, 2 seeds, 2 tasks)",
    "condition (DESIGN.md 13.8 v1.253): a separate inline call costs more than delegating at every size when "
    "slack * p_in > B * p_out, slack = K * (rho * C - B) - (1 + T) * (B + R)",
    "  point 0: C 100, B 10, R 10, T 0, separate, K 1, rho 1: slack 70, slack / B 7.0000; met by 3 of 3 parents, "
    "highest ratio 4.0000 (v/bad)",
    "  point 1: C 5,000, B 10, R 10, T 0, separate, K 1, rho 1: slack 4,970, slack / B 497.0000; met by 3 of 3 parents, "
    "highest ratio 4.0000 (v/bad)",
    "  point 2: C 0, B 2,000, R 0, T 0, separate, K 1, rho 1: slack -4,000, slack / B -2.0000; met by 0 of 3 parents",
    "  point 3: C 100, B 10, R 10, T 0, folded, K 1, rho 1: does not apply (folded)",
    "cells by 13.5 row and reason",
    "  cost_effective  point 0  12 cells: row 2 parent_below_bar delegate 6; row 3 delegate_cheaper delegate 6",
    "  cost_effective  point 1  12 cells: row 1 parent_context_full delegate 4; row 2 parent_below_bar delegate 6; "
    "row 3 delegate_cheaper delegate 2",
    "  cost_effective  point 2  12 cells: row 2 parent_below_bar delegate 2; row 3 inline_cheaper inline 4; "
    "row 5 only_parent_clears inline 2; row 7 none_clear inline 4",
    "  cost_effective  point 3  12 cells: row 2 parent_below_bar delegate 6; row 3 inline_cheaper inline 6",
    "  cost_blind      point 0  12 cells: row 2 parent_below_bar delegate 6; row 4 inline_as_good inline 6",
    "  cost_blind      point 1  12 cells: row 1 parent_context_full delegate 4; row 2 parent_below_bar delegate 6; "
    "row 4 inline_as_good inline 2",
    "  cost_blind      point 2  12 cells: row 2 parent_below_bar delegate 2; row 4 inline_as_good inline 4; "
    "row 5 only_parent_clears inline 2; row 7 none_clear inline 4",
    "  cost_blind      point 3  12 cells: row 2 parent_below_bar delegate 6; row 4 inline_as_good inline 6",
    "check, cost_effective: 24 cells at a separate point whose parent meets the condition, 24 of them delegate",
]


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _drs():
    return _load("research_delegation_reasons", SCRIPT)


def _hand():
    rows = [{"task": task, "item": f"{task}{j:02d}", "model": m.id, "correct": (task, m.id) in RIGHT,
             "input_tokens": 10, "output_tokens": 10}
            for task in ("t", "u") for j in range(40) for m in (GOOD, BAD, SMALL)]
    registry = Registry([GOOD, BAD, SMALL])
    full = evaluate_delegation(rows, registry, bars=[0.5], points=POINTS, seeds=range(2), min_samples=10)
    return registry, full


def test_design_bullet_states_the_condition_and_the_tests():
    section = DESIGN.read_text(encoding="utf-8").split("\n### 13.8 ", 1)[1].split("\n### ", 1)[0]
    bullets = [line for line in section.splitlines() if line.startswith("- v1.253, which 13.5 row chose (row R19): ")]
    assert len(bullets) == 1
    for phrase in ("`research/delegation_reasons.py`", "`slack * p_in > B * p_out`",
                   "`slack = K * (rho * C - B) - (1 + T) * (B + R)`", "every cell delegates",
                   "5,500, 61,500 and 197,500 tokens, ratios 11, 123 and 395", "`## Which 13.5 row chose`",
                   "rows 1, 2, 3, 4, 5 and 7", "strict xfail", "No library code change", "`rerun`"):
        assert phrase in bullets[0], phrase


@NOT_YET
def test_row_of_maps_every_reason():
    drs = _drs()
    rows = {"parent_excluded_family": 1, "parent_not_independent": 1, "parent_context_full": 1,
            "parent_below_bar": 2, "delegate_cheaper": 3, "inline_cheaper": 3, "only_parent_clears": 5,
            "none_clear": 7}
    for flavor in ("cost_effective", "cost_blind"):
        for reason, row in rows.items():
            assert drs.row_of(reason, flavor) == row, (reason, flavor)
    for reason in ("delegate_better", "inline_as_good"):
        assert drs.row_of(reason, "cost_effective") == 3
        assert drs.row_of(reason, "cost_blind") == 4
    with pytest.raises(ValueError, match="unknown reason 'cheaper'"):
        drs.row_of("cheaper", "cost_effective")


@NOT_YET
def test_condition_at_hand_worked_points():
    drs = _drs()
    base = {"context_tokens": 8000, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
            "inline_separate_call": True}
    assert drs.slack(base) == 5500
    assert [drs.slack(dict(base, context_tokens=c)) for c in (64000, 200000)] == [61500, 197500]
    # 5,500 * 1 > 500 * 10, while 5,500 * 1 > 500 * 11 is false: the inequality is strict
    assert drs.meets(base, Model("v/a", "f", 1.0, 10.0, 1_000_000)) is True
    assert drs.meets(base, Model("v/a", "f", 1.0, 11.0, 1_000_000)) is False
    assert drs.meets(base, Model("v/a", "f", 0.0, 1.0, 1_000_000)) is False
    assert drs.slack(dict(base, inline_separate_call=False)) is None
    assert drs.meets(dict(base, inline_separate_call=False), GOOD) is None
    # K = 2 at rho 0.5 and C = 64,000: 2 * (32,000 - 500) - 2 * 1,000
    assert drs.slack(dict(base, context_tokens=64000, work_calls=2, cached_read_ratio=0.5)) == 61000
    assert drs.meets(dict(base, context_tokens=2000), GOOD) is False   # slack -1,000


@NOT_YET
def test_hand_run_reaches_every_row_and_counts_by_brute_force():
    drs = _drs()
    _registry, full = _hand()
    counts = drs.counts(full)
    brute = collections.Counter()
    for cell in full["cells"]:
        brute[cell["flavor"], cell["point"], drs.row_of(cell["reason"], cell["flavor"]), cell["reason"], cell["mode"]] += 1
    assert {(f, p, *k): n for (f, p), c in counts.items() for k, n in c.items()} == dict(brute)
    assert list(counts) == [(f, p) for f in ("cost_effective", "cost_blind") for p in range(4)]
    assert {k[0] for c in counts.values() for k in c} == {1, 2, 3, 4, 5, 7}
    assert all(sum(c.values()) == 12 for c in counts.values())


@NOT_YET
def test_condition_holds_on_every_cell_of_the_hand_run():
    drs = _drs()
    registry, full = _hand()
    met = [c for c in full["cells"] if c["flavor"] == "cost_effective"
           and drs.meets(POINTS[c["point"]], registry.get(c["parent"]))]
    assert len(met) == 24 and all(c["mode"] == "delegate" for c in met)
    assert {c["reason"] for c in met} == {"parent_context_full", "parent_below_bar", "delegate_cheaper"}


@NOT_YET
def test_report_lines_on_the_hand_run():
    drs = _drs()
    registry, full = _hand()
    assert drs.report(full, registry, name="hand") == HAND_LINES


@NOT_YET
def test_refusals():
    drs = _drs()
    registry, full = _hand()
    tiered = Registry([dataclasses.replace(GOOD, price_tiers=(PriceTier(200_000, 2.0, 4.0),)), BAD, SMALL])
    with pytest.raises(ValueError, match="has price tiers"):
        drs.report(full, tiered, name="hand")
    odd = json.loads(json.dumps(full))
    odd["cells"][0]["reason"] = "cheaper"
    with pytest.raises(ValueError, match="unknown reason 'cheaper'"):
        drs.report(odd, registry, name="hand")


@NOT_YET
def test_main_exits_2_with_one_error_line(tmp_path):
    drs = _drs()
    err, out = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        assert drs.main(["--matrix", str(tmp_path / "missing.jsonl")]) == 2
    assert out.getvalue() == ""
    assert err.getvalue().count("\n") == 1 and err.getvalue().startswith("error: ")


@pytest.mark.xfail(strict=True, raises=(AssertionError, IndexError),
                   reason="v1.253: the note's section lands in v1.254")
def test_note_section_states_the_condition_before_the_blocks():
    note = NOTE.read_text(encoding="utf-8")
    assert note.count("\n" + SECTION + "\n") == 1
    section = note.split("\n" + SECTION + "\n", 1)[1].split("\n## ", 1)[0]
    assert note.index("\n## Reading it\n") < note.index("\n" + SECTION + "\n") < note.index("\n## Recommendation\n")
    first = min(section.index("```text\n" + c + "\n") for c in COMMANDS.values())
    assert "slack * p_in > B * p_out" in section[:first]
    for command in COMMANDS.values():
        assert section.count("```text\n" + command + "\n") == 1, command
    regenerate = note.split("\n## Regenerate\n", 1)[1]
    for command in COMMANDS.values():
        assert command[2:] in regenerate, command


def _block(dataset):
    note = NOTE.read_text(encoding="utf-8")
    return note.split("```text\n" + COMMANDS[dataset] + "\n", 1)[1].split("\n```", 1)[0].split("\n")


@NOT_YET
def test_note_llmrouterbench_block_is_the_script_output(llmrouterbench_delegation_full):
    drs = _drs()
    _kept, _dropped, full = llmrouterbench_delegation_full
    registry = Registry.load(ROOT / "evidence" / "llmrouterbench-delegation" / "registry.json")
    assert drs.report(full, registry, name="LLMRouterBench") == _block("llmrouterbench")


@NOT_YET
def test_note_autobench_block_is_the_script_output(tmp_path):
    drs = _drs()
    cv = _load("research_drs_autobench_convert", ROOT / "evidence" / "autobench-2026" / "convert.py")
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
    assert drs.run(matrix, ROOT, dataset="autobench", registry=registry) == _block("autobench")


@pytest.fixture(scope="module")
def tau2_matrices():
    """The tau2-bench converter's --calls matrices, per domain and pooled, from the 12 pinned files."""
    cv = _load("research_drs_tau2_convert", ROOT / "evidence" / "tau2-bench" / "convert.py")
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("the 12 pinned tau2-bench run files are not in the default cache")
    extracts = []
    for n, (size, sha) in cv.FILES.items():
        cv.verify(folder / n, size, sha)
        extracts.append(cv.extract(cv.read_run(folder / n), trial=0, tokens=True, calls=True))
    return {"tau2-bench": cv.convert(extracts)[0], "tau2-bench-pooled": cv.convert(extracts, task_by="all")[0]}


@NOT_YET
@pytest.mark.parametrize("dataset", ["tau2-bench", "tau2-bench-pooled"])
def test_note_tau2_blocks_are_the_script_output(tau2_matrices, tmp_path, dataset):
    drs = _drs()
    matrix = tmp_path / "tau2.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in tau2_matrices[dataset]), encoding="utf-8")
    assert drs.run(matrix, ROOT, dataset=dataset) == _block(dataset)
