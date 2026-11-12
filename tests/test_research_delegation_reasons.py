"""research/delegation_reasons.py and its section of research/where-delegation-pays.md (DESIGN 13.8 v1.253, row R19).

The script counts each 13.9 run's cells per (flavor, point) by the 13.5 row and reason that chose
their path, after a condition from 13.2: with inline work in a call of its own, a separate inline
call costs more than delegating at every size when `slack * p_in > B * p_out`, with
`slack = K * (rho * C - B) - (1 + T) * (B + R)`. The tests run it on a hand-built matrix on which
13.5 rows 1, 2, 3, 4, 5 and 7 each choose at least once (the cells are worked by hand in
`HAND_LINES` below), check the condition at hand-worked points and at its strict boundary, and on
every `cost_effective` cell of that run, and compare the note's four results blocks with the
script's output where the pinned files are cached. v1.253 commits them ahead of the script and the
note, each a strict xfail but the one that reads the DESIGN bullet; v1.254 lands both and removes
the markers.

v1.256 (row DOC16) adds the README `Inline or sub-agent` paragraph that states the condition in the
`delegate` flags' names, built here from the note's results blocks (the point 0 line the four
blocks share, their title lines and their check lines), so the README test runs where the pinned
files are not cached. v1.256 commits it ahead of the paragraph as a strict xfail; v1.257 lands the
paragraph. v1.281 (row DOC17) splits that 157-word sentence in two after the general condition.
"""

import collections
import contextlib
import dataclasses
import decimal
import importlib.util
import io
import json
import re
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


def test_condition_holds_on_every_cell_of_the_hand_run():
    drs = _drs()
    registry, full = _hand()
    met = [c for c in full["cells"] if c["flavor"] == "cost_effective"
           and drs.meets(POINTS[c["point"]], registry.get(c["parent"]))]
    assert len(met) == 24 and all(c["mode"] == "delegate" for c in met)
    assert {c["reason"] for c in met} == {"parent_context_full", "parent_below_bar", "delegate_cheaper"}


def test_report_lines_on_the_hand_run():
    drs = _drs()
    registry, full = _hand()
    assert drs.report(full, registry, name="hand") == HAND_LINES


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


def test_main_exits_2_with_one_error_line(tmp_path):
    drs = _drs()
    err, out = io.StringIO(), io.StringIO()
    with contextlib.redirect_stderr(err), contextlib.redirect_stdout(out):
        assert drs.main(["--matrix", str(tmp_path / "missing.jsonl")]) == 2
    assert out.getvalue() == ""
    assert err.getvalue().count("\n") == 1 and err.getvalue().startswith("error: ")


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


def test_note_llmrouterbench_block_is_the_script_output(llmrouterbench_delegation_full):
    drs = _drs()
    _kept, _dropped, full = llmrouterbench_delegation_full
    registry = Registry.load(ROOT / "evidence" / "llmrouterbench-delegation" / "registry.json")
    assert drs.report(full, registry, name="LLMRouterBench") == _block("llmrouterbench")


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


@pytest.mark.parametrize("dataset", ["tau2-bench", "tau2-bench-pooled"])
def test_note_tau2_blocks_are_the_script_output(tau2_matrices, tmp_path, dataset):
    drs = _drs()
    matrix = tmp_path / "tau2.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in tau2_matrices[dataset]), encoding="utf-8")
    assert drs.run(matrix, ROOT, dataset=dataset) == _block(dataset)


# --- the section's prose (v1.254) --------------------------------------------------------------
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?")
SEPARATE_LINE = re.compile(r"^  cost_effective  point [012]  [\d,]+ cells: (.*)$")
# DESIGN section numbers the prose cites
CITED = {"13.2", "13.3", "13.5", "13.9", "5.3"}


def _section():
    return NOTE.read_text(encoding="utf-8").split("\n" + SECTION + "\n", 1)[1].split("\n## ", 1)[0]


def _separate_totals():
    """Per (row, reason, mode), the cost_effective cells at points 0 to 2 summed over the four blocks."""
    totals = collections.Counter()
    for dataset in COMMANDS:
        for line in _block(dataset):
            found = SEPARATE_LINE.match(line)
            if found:
                for part in found[1].split("; "):
                    _row, row, reason, mode, n = part.split(" ")
                    totals[int(row), reason, mode] += int(n.replace(",", ""))
    return totals


def _value(text):
    return decimal.Decimal(text.replace(",", ""))


def test_reading_totals_are_the_blocks_sums():
    totals = _separate_totals()
    assert {mode for _row, _reason, mode in totals} == {"delegate"}
    reading = [b for b in _section().split("\n```\n")[-1].splitlines() if b.startswith("- `cost_effective`: ")]
    assert len(reading) == 1
    by_row = {row: n for (row, _reason, _mode), n in totals.items()}
    assert f"those {sum(totals.values()):,} cells are row 3 `delegate_cheaper` on {by_row[3]:,}, row 7 `none_clear` on " \
           f"{by_row[7]:,}, row 1 `parent_context_full` on {by_row[1]:,} and row 2 `parent_below_bar` on " \
           f"{by_row[2]:,}" in reading[0]
    assert 3 * by_row[3] < sum(totals.values())   # "under a third"
    checks = [_block(d)[-1] for d in COMMANDS]
    assert all(re.fullmatch(r"check, cost_effective: ([\d,]+) cells .*, \1 of them delegate", c) for c in checks)


def test_section_prose_numbers_are_in_its_blocks():
    section = _section()
    prose = re.sub(r"^```text\n.*?^```$", "", section, flags=re.M | re.S)
    prose = re.sub(r"`[^`\n]*`", "", prose)
    # the recommended README sentence quotes its own sizes
    prose = prose.split("Recommended for the README", 1)[0]
    blocks = "\n".join(line for d in COMMANDS for line in _block(d))
    known = {_value(n) for n in NUMBER.findall(blocks)} | {_value(f"{n:,}") for n in _separate_totals().values()}
    known.add(_value(f"{sum(_separate_totals().values()):,}"))
    stray = sorted({n for n in NUMBER.findall(prose) if n not in CITED and _value(n) not in known})
    assert stray == []


# --- README Inline or sub-agent (DESIGN 13.8 v1.256, row DOC16) ---------------------------------
README = ROOT / "README.md"
PAYS_LINK = "([research/where-delegation-pays.md](research/where-delegation-pays.md))"
PUBLIC_DATA = "On public data, [Delegation on AutoBench](#delegation-on-autobench) "
TITLE = re.compile(r"^Which 13\.5 row chose each cell's path on (.+): the cells of the 13\.9 run by flavor, point, row and reason$")
POINT_0 = re.compile(r"^  point 0: C ([\d,]+), B ([\d,]+), R ([\d,]+), T (\d+), separate, K 1, rho 1: slack ([\d,]+), ")
CHECK = re.compile(r"^check, cost_effective: ([\d,]+) cells at a separate point whose parent meets the condition, "
                   r"([\d,]+) of them delegate$")


def test_design_specifies_the_readme_paragraph():
    section = DESIGN.read_text(encoding="utf-8").split("\n### 13.8 ", 1)[1].split("\n### ", 1)[0]
    bullets = [line for line in section.splitlines()
               if line.startswith("- v1.256, which 13.5 row chose in the README (row DOC16): ")]
    assert len(bullets) == 1
    for phrase in ("`### Inline or sub-agent`", "`On public data, ...`", "`--context-tokens`", "`--carry-turns`",
                   "no `--fold-inline`", "`--work-calls 1`", "no `--cached-read-ratio`",
                   "`C - B - (1 + T) * (B + R)` is above `B * p_out / p_in`", "`C > X + B * p_out / p_in`",
                   "`separate, K 1, rho 1`", "X = B + (1 + T) * (B + R)", "N cells of which N delegate",
                   "strict xfail", "No library code", "v1.281 (row DOC17", "two sentences",
                   "`since that call re-reads the parent's whole context.`",
                   "\"At a B-token brief and result and `--carry-turns T`, the condition holds for any\"",
                   "recommended sentence stays one sentence"):
        assert phrase in bullets[0], phrase


def _int(text):
    return int(text.replace(",", ""))


def readme_figures():
    """(B, T, X, run names, cells) for the README paragraph, read from the note's four results blocks."""
    shared, names, cells = set(), [], 0
    for dataset in COMMANDS:
        block = _block(dataset)
        title = TITLE.match(block[0])
        assert title, dataset
        names.append(title[1])
        point_0 = [line for line in block if line.startswith("  point 0: ")]
        assert len(point_0) == 1 and POINT_0.match(point_0[0]), dataset
        shared.add(POINT_0.match(point_0[0])[0])  # its sizes and slack; the parents differ by pool
        check = CHECK.match(block[-1])
        assert check and check[1] == check[2] and _int(check[1]) > 0, dataset
        cells += _int(check[1])
    assert len(shared) == 1                       # the four runs share point 0's sizes and slack
    c, b, r, t, slack = (_int(v) for v in POINT_0.match(shared.pop()).groups())
    x = c - slack
    assert b == r and x == b + (1 + t) * (b + r)  # "a B-token brief and result", K = 1, rho = 1
    return b, t, x, names, cells


def readme_paragraph():
    """The README paragraph of v1.256, in the two sentences of v1.281."""
    b, t, x, names, cells = readme_figures()
    runs = ", ".join(names[:-1]) + " and " + names[-1]
    return ("In numbers, with C, B, R and T the `--context-tokens`, `--brief-tokens`, `--result-tokens` and "
            "`--carry-turns` values and `p_out / p_in` the parent's output price over its input price: for work in a "
            "call of its own (no `--fold-inline`), in one work call (`--work-calls 1`) with full-price reads of the "
            "context (no `--cached-read-ratio`), from a parent with stats for the task that the router does not "
            "exclude as a delegate and with no `price_tiers` in `models.json`, `cost_effective` delegates whenever "
            "`C - B - (1 + T) * (B + R)` is above `B * p_out / p_in`, whatever the size of the work itself, since "
            f"that call re-reads the parent's whole context. At a {b:,}-token brief and result and `--carry-turns {t}`, "
            f"the condition holds for any `C > {x:,} + {b:,} * p_out / p_in`, and on the four committed delegation runs "
            f"({runs}) all "
            f"{cells:,} `cost_effective` cells at such a point delegate {PAYS_LINK}.")


SENTENCE_END = re.compile(r"\. (?=[A-Z])")
REASON = "since that call re-reads the parent's whole context."


def test_readme_paragraph_is_two_sentences():
    # v1.281: the general condition and its reason, then the point 0 form with the cell count and the link
    first, second = SENTENCE_END.split(readme_paragraph())   # exactly two, or the unpacking fails
    assert (first + ".").endswith(REASON) and REASON not in second
    assert second.startswith("At a 500-token brief and result and `--carry-turns 1`, the condition holds for any ")
    assert second.endswith(PAYS_LINK + ".") and PAYS_LINK not in first


def test_note_recommends_the_same_form():
    b, t, x, names, cells = readme_figures()
    assert (b, t, x, len(names)) == (500, 1, 2_500, 4) and cells > 0
    recommended = [line for line in _section().splitlines() if line.startswith("- Recommended for the README ")]
    assert len(recommended) == 1
    assert f"at a {b:,}-token brief and result and one later call, any `C > {x:,} + {b:,} * p_out / p_in`" \
        in recommended[0]
    assert "`C - B - (1 + T) * (B + R)` is above `B` times the parent's output price over its input price" \
        in recommended[0]


def test_readme_inline_subsection_states_when_a_separate_call_delegates():
    readme = README.read_text(encoding="utf-8")
    inline = readme.split("\n### Inline or sub-agent\n", 1)[1].split("\n## ", 1)[0]
    paragraphs = [p.strip("\n") for p in inline.split("\n\n")]
    public = [i for i, p in enumerate(paragraphs) if p.startswith(PUBLIC_DATA)]
    assert len(public) == 1
    assert public[0] + 1 < len(paragraphs) and paragraphs[public[0] + 1] == readme_paragraph()
    assert readme.count(readme_paragraph()) == 1
