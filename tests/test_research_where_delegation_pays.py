"""research/where-delegation-pays.md and research/where_delegation_pays.py (DESIGN 13.8 v1.206).

The script reads only the five committed delegation results files (v1.323, row R28: the response bank's
fifth), so the note's Results block is
compared byte for byte with a fresh run on every machine, CI included. Its classes are also checked
on hand-made pairs and its report on a small hand-made set of files, where each count can be worked
out by hand.
"""

import ast
import contextlib
import importlib.util
import io
import json
import re
from collections import Counter
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "where_delegation_pays.py"
NOTE = ROOT / "research" / "where-delegation-pays.md"
INDEX = ROOT / "research" / "README.md"
DESIGN = ROOT / "DESIGN.md"
COMMAND = "$ python research/where_delegation_pays.py"
# v1.323 (row R28): the dated section on the fifth file
BANK = "## Fifth file: LLM Routing Response Bank (2026-11-13)"
SECTIONS = ["## Facts", "## Method", "## Results", "## Reading it", BANK, "## Which 13.5 row chose",
            "## Recommendation", "## Limits", "## Regenerate"]
FILES = ["evidence/delegation/results.json", "evidence/tau2-bench-delegation/results.json",
         "evidence/tau2-bench-delegation/pooled.json", "evidence/llmrouterbench-delegation/results.json",
         "evidence/response-bank-delegation/results.json"]
BANK_RESULTS = ROOT / "evidence" / "response-bank-delegation" / "RESULTS.md"
BANK_SCRIPT = ROOT / "evidence" / "response-bank-delegation" / "results.py"
BANK_REGISTRY = ROOT / "evidence" / "response-bank-delegation" / "registry.json"
RED = pytest.mark.xfail(strict=True, reason="v1.323: the script reads the fifth file (row R28)")
# DESIGN section numbers and the two delegate_rate values of the rule: the only numbers of the
# note's prose that are not in the script's output
ALLOWED = {"13.2", "13.4", "13.5", "13.8", "13.9", "13.10", "1.0", "0.0"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?%?")


def _load():
    spec = importlib.util.spec_from_file_location("research_where_delegation_pays", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def wdp():
    return _load()


def run(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture(scope="module")
def output(wdp):
    code, out, err = run(wdp, ["--root", str(ROOT)])
    assert (code, err) == (0, "")
    return out


def note():
    return NOTE.read_text(encoding="utf-8")


def results_block(text):
    section = text.split("\n## Results\n", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"^```text\n(.*?)^```$", section, re.M | re.S)
    assert len(blocks) == 1, "one text block in ## Results"
    return blocks[0]


def test_design_specifies_the_note_and_the_script():
    text = DESIGN.read_text(encoding="utf-8")
    bullets = [line for line in text.splitlines() if line.startswith("- v1.206, where delegation pays: ")]
    assert len(bullets) == 1
    for name in ("`research/where-delegation-pays.md`", "`research/where_delegation_pays.py`",
                 "`= delegate`", "`= inline`", "`better`", "`beaten on success`", "`beaten on cost`",
                 "`trade-off`", "`top success`", "`delegate_rate`"):
        assert name in bullets[0], name
    for rel in FILES:
        assert rel.rsplit("/", 1)[0] in bullets[0], rel
    section = text.split("\n### 13.8 ", 1)[1].split("\n### ", 1)[0]
    assert bullets[0] in section


def test_note_results_block_is_the_script_output(output):
    assert results_block(note()) == COMMAND + "\n" + output


@RED
def test_note_sections_in_order():
    assert re.findall(r"^## .*$", note(), re.M) == SECTIONS


def test_prose_numbers_are_in_the_output(output):
    # the `## Which 13.5 row chose` section (v1.254) reads other output, checked in
    # tests/test_research_delegation_reasons.py, and the fifth file's (v1.323) is checked on that file below
    text = re.sub(r"^## Which 13\.5 row chose\n.*?(?=^## )", "", note(), flags=re.M | re.S)
    text = re.sub(r"^## Fifth file: .*?(?=^## )", "", text, flags=re.M | re.S)
    prose = re.sub(r"^```text\n.*?^```$", "", text, flags=re.M | re.S)
    prose = re.sub(r"https?://\S+", "", prose)
    prose = re.sub(r"`[^`\n]*`", "", prose)
    stray = sorted(set(NUMBER.findall(prose)) - set(NUMBER.findall(output)) - ALLOWED)
    assert not stray, stray


def test_rule_comes_before_any_count():
    text = note()
    method = text.split("\n## Method\n", 1)[1].split("\n## ", 1)[0]
    for name in ("`= delegate`", "`better`", "`beaten on success`", "`beaten on cost`", "`trade-off`"):
        assert name in method, name
    assert text.index("The rule, stated before the counts it gives.") < text.index("\n## Results\n")


@RED
def test_regenerate_section_and_files():
    assert COMMAND[2:] in note().split("\n## Regenerate\n", 1)[1]
    for rel in FILES:
        assert f"`{rel}`" in note(), rel


def test_research_index_row_and_bullet():
    text = INDEX.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines()
            if line.startswith("| [where-delegation-pays.md](where-delegation-pays.md) | ")]
    assert len(rows) == 1
    assert "[where_delegation_pays.py](where_delegation_pays.py)" in rows[0]
    assert sum(1 for line in text.splitlines() if line.startswith("- `research/where-delegation-pays.md` ")) == 1


def test_script_imports_only_the_standard_library():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module.split(".")[0])
    assert names <= {"argparse", "json", "sys", "collections", "pathlib"}, names


def s(success, cost):
    return {"success": success, "cost_usd": cost}


@pytest.mark.parametrize("decision, inline, delegate, expected", [
    ((0.5, 2.0), (0.4, 1.0), (0.5, 2.0), "= delegate"),
    ((0.4, 1.0), (0.4, 1.0), (0.5, 2.0), "= inline"),
    ((0.5, 1.0), (0.5, 1.0), (0.5, 1.0), "= delegate"),
    ((0.6, 1.0), (0.5, 1.5), (0.6, 1.0 + 1e-12), "better"),
    ((0.6, 1.0), (0.6, 1.0 + 1e-12), (0.5, 3.0), "better"),
    ((0.5, 2.0), (0.6, 2.0), (0.4, 1.0), "beaten on success"),
    ((0.5, 2.0), (0.4, 3.0), (0.5 + 1e-12, 1.0), "beaten on success"),
    ((0.5, 2.0), (0.5, 1.9), (0.4, 1.0), "beaten on cost"),
    ((0.5, 2.0), (0.4, 1.0), (0.6, 3.0), "trade-off"),
    ((0.7, 2.0), (0.4, 1.0), (0.6, 3.0), "trade-off"),
    ((0.5, 2.0), (0.5, 2.5), (0.4, 1.0), "trade-off"),
])
def test_classify(wdp, decision, inline, delegate, expected):
    assert wdp.classify(s(*decision), s(*inline), s(*delegate)) == expected


def row(bar, flavor, point, parent, strategy, success, cost, rate=None):
    return {"bar": bar, "flavor": flavor, "point": point, "parent": parent, "strategy": strategy,
            "success": success, "cost_usd": cost, "below_bar_rate": 0.0, "delegate_rate": rate}


def triple(bar, flavor, point, parent, decision, inline, delegate, rate):
    return [row(bar, flavor, point, parent, "decision", *decision, rate=rate),
            row(bar, flavor, point, parent, "inline", *inline), row(bar, flavor, point, parent, "delegate", *delegate)]


POINTS = [{"context_tokens": 8000, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
           "inline_separate_call": flag} for flag in (True, False)]


def small_file(summary, bars=(0.5,), flavors=("cost_effective",), parents=("a/p", "b/q")):
    return {"config": {"bars": list(bars), "seeds": [0], "flavors": list(flavors), "points": POINTS,
                       "parents": list(parents)},
            "tasks": {"t": {"items": 10, "models": ["a/p", "b/q"]}}, "summary": summary}


def write_root(tmp_path, documents):
    for rel, document in zip(FILES, documents):
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(document if isinstance(document, str) else json.dumps(document), encoding="utf-8")
    return tmp_path


SMALL = small_file(
    triple(0.5, "cost_effective", 0, "a/p", (0.5, 2.0), (0.4, 3.0), (0.5, 2.0), 1.0)
    + triple(0.5, "cost_effective", 0, "b/q", (0.4, 1.0), (0.4, 1.0), (0.5, 2.0), 0.0)
    + triple(0.5, "cost_effective", 1, "a/p", (0.7, 1.5), (0.4, 1.0), (0.6, 3.0), 0.5)
    + triple(0.5, "cost_effective", 1, "b/q", (0.5, 2.0), (0.6, 2.0), (0.4, 1.0), 0.5))


@RED
def test_report_on_small_files(wdp, tmp_path):
    root = write_root(tmp_path, [SMALL] * 5)
    code, out, err = run(wdp, ["--root", str(root)])
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert lines[1] == ("AutoBench (`evidence/delegation/results.json`): 4 rows, 1 task, bars 0.5, "
                        "2 points, 2 parents")
    assert lines[2] == wdp.HEADER
    # rows 4: point 0 a/p = delegate, point 0 b/q = inline, point 1 b/q beaten on success (inline 0.6 at
    # the same 2.0), point 1 a/p a trade-off (inline cheaper, delegate dearer) and the one top success row
    assert lines[3] == ("  cost_effective  0.5      4           1         1       0"
                        "                  1               0          1            1")
    assert lines[4] == "  changed rows by point, cost_effective: 0: 0, 1: 2"
    # point 1, a/p: 1.5 < 3.0 and 0.7 >= 0.6; point 1, b/q: 2.0 > 1.0
    assert lines[5] == ("  against always delegate, cost_effective: 2 changed rows, 1 cheaper "
                        "(1 of them at no less success), 1 not cheaper")
    assert lines[6] == ("  largest gain, cost_effective: bar 0.5, point 1, parent a/p: decision 0.7000 at "
                        "1.5000 USD, inline 0.4000 at 1.0000, delegate 0.6000 at 3.0000, gain +0.1000")
    assert lines[-3:] == ["All five files", wdp.HEADER,
                          "  cost_effective  all     20           5         5       0"
                          "                  5               0          5            5"]
    assert len(lines) == 1 + 5 * 6 + 3


def test_no_changed_row_and_task_plural(wdp, tmp_path):
    document = small_file(triple(0.5, "cost_effective", 0, "a/p", (0.5, 2.0), (0.4, 3.0), (0.5, 2.0), 1.0),
                          parents=("a/p",))
    document["tasks"]["u"] = {"items": 5, "models": ["a/p"]}
    code, out, err = run(wdp, ["--root", str(write_root(tmp_path, [document] * 5))])
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert lines[1].endswith(": 1 row, 2 tasks, bars 0.5, 2 points, 1 parent")
    assert lines[4:7] == ["  changed rows by point, cost_effective: 0: 0, 1: 0",
                          "  against always delegate, cost_effective: no changed row",
                          "  largest gain, cost_effective: no changed row"]


BAD = {
    "missing strategy": small_file(triple(0.5, "cost_effective", 0, "a/p", (0.5, 2.0), (0.4, 3.0), (0.5, 2.0),
                                          1.0)[:2]),
    "repeated strategy": small_file(triple(0.5, "cost_effective", 0, "a/p", (0.5, 2.0), (0.4, 3.0), (0.5, 2.0),
                                           1.0) + [row(0.5, "cost_effective", 0, "a/p", "inline", 0.4, 3.0)]),
    "equal with a rate below 1.0": small_file(triple(0.5, "cost_effective", 0, "a/p", (0.5, 2.0), (0.4, 3.0),
                                                     (0.5, 2.0), 0.98)),
    "a rate of 0.0 but not equal to inline": small_file(triple(0.5, "cost_effective", 0, "a/p", (0.5, 2.0),
                                                               (0.4, 3.0), (0.6, 1.0), 0.0)),
    "no summary": {"config": SMALL["config"], "tasks": SMALL["tasks"]},
    "no success": small_file([{k: v for k, v in r.items() if k != "success"} for r in SMALL["summary"]]),
    "a success that is not a number": small_file(triple(0.5, "cost_effective", 0, "a/p", (None, 2.0),
                                                        (0.4, 3.0), (None, 2.0), 1.0)),
    "a bool cost": small_file(triple(0.5, "cost_effective", 0, "a/p", (0.5, 2.0), (0.4, True), (0.5, 2.0), 1.0)),
    "not JSON": "{",
    "not an object": "[]",
}


@pytest.mark.parametrize("case", sorted(BAD))
def test_a_bad_file_is_one_error_line(wdp, tmp_path, case):
    root = write_root(tmp_path, [SMALL, SMALL, BAD[case], SMALL, SMALL])
    code, out, err = run(wdp, ["--root", str(root)])
    assert (code, out) == (2, "")
    assert err.count("\n") == 1 and err.startswith("error: evidence/tau2-bench-delegation/pooled.json: "), err


@RED
def test_a_missing_file_is_one_error_line(wdp, tmp_path):
    root = write_root(tmp_path, [SMALL, SMALL, SMALL, SMALL])
    code, out, err = run(wdp, ["--root", str(root)])
    assert (code, out) == (2, "")
    assert err == "error: evidence/response-bank-delegation/results.json: no such file\n"


def committed(wdp):
    for name, rel in wdp.DATASETS:
        results = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        yield name, results, wdp.rows_of(results, rel)


@RED
def test_the_script_reads_the_five_files_in_order(wdp):
    assert [rel for _, rel in wdp.DATASETS] == FILES


def test_cost_effective_changes_only_where_inline_folds(wdp):
    """Reading it: every cost_effective row at a separate-call point is `= delegate`."""
    for name, results, groups in committed(wdp):
        points = results["config"]["points"]
        # the note's "points 0, 1 and 2" and "point 3" (review iter-153 nit 6)
        assert [p["inline_separate_call"] for p in points] == [True, True, True, False], name
        for key, group in groups.items():
            kind = wdp.classify(group["decision"], group["inline"], group["delegate"])
            if key[1] == "cost_effective" and points[key[2]]["inline_separate_call"]:
                assert kind == "= delegate", (name, key, kind)


def better_rows(wdp):
    """(dataset name, key, group) of every `better` row of the committed files, in file order."""
    return [(name, key, group) for name, _, groups in committed(wdp) for key, group in groups.items()
            if wdp.classify(group["decision"], group["inline"], group["delegate"]) == "better"]


@RED
def test_the_better_rows_are_the_response_banks_at_always_delegatings_success(wdp):
    """Facts (v1.323): the decision is better than both fixed policies on two rows, each a `cost_effective` row of
    the response bank at the folded point, at always delegating's held-out success and a cost below both."""
    rows = better_rows(wdp)
    assert [(name, key[1]) for name, key, _ in rows] == [("LLM Routing Response Bank", "cost_effective")] * 2, rows
    for _, key, group in rows:
        assert key[2] == 3, key
        decision, inline, delegate = (pair(group[s]) for s in wdp.STRATEGIES)
        assert decision[0] == delegate[0] > inline[0], key
        assert decision[1] < min(inline[1], delegate[1]), key


def test_top_success_rows_are_trade_offs(wdp):
    """A changed row with a positive gain can be neither beaten nor better, so it is a trade-off."""
    seen = 0
    for _, _, groups in committed(wdp):
        for group in groups.values():
            if wdp.gain(group) > 0:
                seen += 1
                assert wdp.classify(group["decision"], group["inline"], group["delegate"]) == "trade-off"
    assert seen == 3


def test_a_changed_row_at_always_delegates_cost_is_not_cheaper(wdp, tmp_path):
    """Cheaper than always delegate is strictly cheaper: an equal cost is counted with the rest."""
    document = small_file(triple(0.5, "cost_effective", 1, "a/p", (0.4, 2.0), (0.5, 1.0), (0.5, 2.0), 0.5),
                          parents=("a/p",))
    code, out, err = run(wdp, ["--root", str(write_root(tmp_path, [document] * 5))])
    assert (code, err) == (0, "")
    assert out.splitlines()[5] == ("  against always delegate, cost_effective: 1 changed row, 0 cheaper "
                                   "(0 of them at no less success), 1 not cheaper")


# --- README Limitations (DESIGN 13.8 v1.209, row DOC12) ----------------------------------------

README = ROOT / "README.md"
NOTE_LINK = "([research/where-delegation-pays.md](research/where-delegation-pays.md))"


def test_design_specifies_the_readme_line():
    text = DESIGN.read_text(encoding="utf-8")
    bullets = [line for line in text.splitlines()
               if line.startswith("- v1.209, where delegation pays in the README (row DOC12): ")]
    assert len(bullets) == 1
    for name in ("`research/where-delegation-pays.md`", "`research/where_delegation_pays.py`", "`All five files`",
                 "`= delegate`", "`inline_separate_call`", "`beaten on success`", "`better`"):
        assert name in bullets[0], name
    section = text.split("\n### 13.8 ", 1)[1].split("\n### ", 1)[0]
    assert bullets[0] in section


def all_files(wdp, output):
    """{flavor: {column: count}} from the script's `All five files` lines (`All four files` to v1.322)."""
    lines = output.split("\nAll five files\n", 1)[1].splitlines()
    assert lines[0] == wdp.HEADER
    columns = ("rows",) + wdp.CLASSES + ("top success",)
    totals = {}
    for line in lines[1:]:
        flavor, bar, *counts = line.split()
        assert bar == "all" and len(counts) == len(columns), line
        totals[flavor] = dict(zip(columns, map(int, counts)))
    assert sorted(totals) == ["cost_blind", "cost_effective"], totals
    return totals


def separate_call_rows(wdp):
    """Per file, the cost_effective rows at a point whose inline work is a parent call of its own; each must be
    `= delegate`."""
    counts = {}
    for name, results, groups in committed(wdp):
        points = results["config"]["points"]
        counts[name] = 0
        for key, group in groups.items():
            if key[1] == "cost_effective" and points[key[2]]["inline_separate_call"]:
                kind = wdp.classify(group["decision"], group["inline"], group["delegate"])
                assert kind == "= delegate", (name, key, kind)
                counts[name] += 1
    return counts


def limitations_bullet(wdp, output):
    """The README Limitations bullet of v1.209 (v1.323: five files), its counts from the script's output on the
    committed files."""
    totals = all_files(wdp, output)
    effective, blind = totals["cost_effective"], totals["cost_blind"]
    # v1.323: every `better` row is a cost_effective row of the response bank at always delegating's success and a
    # cost below both fixed policies' (checked in the test above), and no cost_blind row is better
    assert blind["better"] == 0, totals
    better = better_rows(wdp)
    assert len(better) == effective["better"] and all(name == "LLM Routing Response Bank" for name, _, _ in better)
    for _, _, group in better:
        decision, inline, delegate = (pair(group[s]) for s in wdp.STRATEGIES)
        assert decision[0] == delegate[0] and decision[1] < min(inline[1], delegate[1]), group
    separate = separate_call_rows(wdp)
    # each file has such rows, so the claim is about every file (review iter-154 should-fix 1)
    assert len(separate) == len(FILES) and all(separate.values()), separate
    assert sum(separate.values()) <= effective["= delegate"]
    return ("- On the five delegation results files of AutoBench 2026, tau2-bench, LLMRouterBench and the LLM Routing "
            "Response Bank the per-task decision is close to a "
            f"fixed policy. The `cost_effective` decision equals always delegating on {effective['= delegate']:,} "
            f"of their {effective['rows']:,} (bar, point, parent) rows, every row at a point where inline work takes "
            "a parent call of its own among them, while in `cost_blind` a fixed policy, always inline or always "
            f"delegate, has more held-out success at no more cost on {blind['beaten on success']:,} of "
            f"{blind['rows']:,}, and the decision is better than both fixed policies on {effective['better']:,} rows, "
            "each a `cost_effective` row of the response bank at always delegating's held-out success for less cost "
            "than either. "
            "So the evidence shows how the decision prices the two paths at the stated sizes, not a gain in success "
            "from choosing per task; such a gain needs work whose cheaper path differs from item to item, as where it "
            f"folds into the parent's next call {NOTE_LINK}")


@RED
def test_readme_counts_are_the_notes_recommendation(wdp, output):
    """The counts the README bullet gives are the ones the note's Recommendation gives."""
    totals = all_files(wdp, output)
    effective, blind = totals["cost_effective"], totals["cost_blind"]
    recommendation = note().split("\n## Recommendation\n", 1)[1].split("\n## ", 1)[0]
    first = [line for line in recommendation.splitlines() if line.startswith("- ")][0]
    assert f"on {effective['= delegate']} of {effective['rows']} rows" in first
    assert f"on {blind['beaten on success']} of {blind['rows']}" in first
    assert f"better than both fixed policies on {effective['better']}, " in first


@RED
def test_readme_limitations_say_what_the_per_task_decision_adds(wdp, output):
    readme = README.read_text(encoding="utf-8")
    limits = readme.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in limits.splitlines() if line.startswith("- ")]
    datasets = [i for i, b in enumerate(bullets) if b.startswith("- The delegation evidence reads four datasets")]
    assert len(datasets) == 1
    assert bullets[datasets[0] + 1] == limitations_bullet(wdp, output)
    assert sum(NOTE_LINK in b for b in bullets) == 1


# --- the fifth file (DESIGN 13.8 v1.323, row R28) ----------------------------------------------

def section(text, heading):
    return text.split("\n" + heading + "\n", 1)[1].split("\n## ", 1)[0]


def test_design_specifies_the_fifth_file_section():
    text = DESIGN.read_text(encoding="utf-8")
    bullets = [line for line in text.splitlines()
               if line.startswith("- v1.323, where delegation pays on the response bank (row R28): ")]
    assert len(bullets) == 1
    for name in (f"`{BANK}`", "`= delegate`", "`better`", "`delegate_rate`", "`inline_separate_call`",
                 "`evidence/response-bank-delegation/RESULTS.md`", "route primary", "opening sentence holds no digit",
                 "strict xfails"):
        assert name in bullets[0], name
    section_838 = text.split("\n### 13.8 ", 1)[1].split("\n### ", 1)[0]
    assert bullets[0] in section_838


REASONS = re.compile(r"Of the ([\d,]+) `cost_effective` cells, ([\d,]+) `none_clear`, ([\d,]+) `delegate_cheaper`, "
                     r"([\d,]+) `parent_below_bar` and ([\d,]+) `inline_cheaper`\.")


def bank(wdp):
    """The fifth file, its groups, the (task, seed) cells of a row, and its cost_effective inline cells per row."""
    results = json.loads((ROOT / FILES[4]).read_text(encoding="utf-8"))
    groups = wdp.rows_of(results, FILES[4])
    cells = len(results["tasks"]) * len(results["config"]["seeds"])
    inline = {}
    for key, group in groups.items():
        if key[1] == "cost_effective":
            count = (1 - group["decision"]["delegate_rate"]) * cells
            assert abs(count - round(count)) < 1e-9, (key, count)
            if round(count):
                inline[key] = round(count)
    return results, groups, cells, inline


def results_reasons():
    found = REASONS.findall(BANK_RESULTS.read_text(encoding="utf-8"))
    assert len(found) == 1, found
    total, none_clear, delegate_cheaper, below_bar, inline_cheaper = (int(v.replace(",", "")) for v in found[0])
    assert total == none_clear + delegate_cheaper + below_bar + inline_cheaper
    return total, inline_cheaper


@RED
def test_fifth_file_section_on_the_committed_file(wdp):
    """v1.323: each count and pair the dated section gives, rebuilt from the committed file and its RESULTS.md."""
    results, groups, cells, inline = bank(wdp)
    text = section(note(), BANK)
    opening = text.strip("\n").split("\n\n", 1)[0]
    assert not re.search(r"\d", opening), opening
    assert "better than both fixed policies" in opening
    kinds = {flavor: Counter() for flavor in results["config"]["flavors"]}
    points = results["config"]["points"]
    for key, group in groups.items():
        kind = wdp.classify(group["decision"], group["inline"], group["delegate"])
        kinds[key[1]][kind] += 1
        if key[1] == "cost_effective" and points[key[2]]["inline_separate_call"]:
            assert kind == "= delegate", key
    effective, blind = kinds["cost_effective"], kinds["cost_blind"]
    rows = sum(effective.values())
    assert rows == sum(blind.values()) == 40
    assert effective["beaten on success"] == effective["beaten on cost"] == effective["= inline"] == 0, effective
    assert effective["= delegate"] + effective["better"] == rows, effective
    assert f"{effective['= delegate']} of its {rows} rows are `= delegate`, every row at points 0, 1 and 2" in text
    assert "no fixed policy beats the decision on success or on cost alone" in text
    better = [(key, group) for key, group in groups.items()
              if wdp.classify(group["decision"], group["inline"], group["delegate"]) == "better"]
    assert sorted(inline) == sorted(key for key, _ in better), (inline, better)
    for key, group in better:
        decision, inline_pair, delegate = (pair(group[s]) for s in wdp.STRATEGIES)
        assert decision[0] == delegate[0] and decision[1] < min(inline_pair[1], delegate[1]), key
        assert f"at bar {key[0]} with `{key[3]}`" in text, key
        for value in decision + inline_pair + delegate:
            assert f"{value:.4f}" in text, (key, value)
        assert format(group["decision"]["delegate_rate"], "g") in text, key
    first, second = (inline[key] for key, _ in better)
    assert f"of their {cells} (task, seed) cells each, so {first} and {second} cells go inline, {first + second} in all" \
        in text
    total, inline_cheaper = results_reasons()
    assert total == len(results["config"]["bars"]) * len(points) * len(results["config"]["parents"]) * cells
    assert f"of the {total:,} `cost_effective` cells" in text
    assert f"counts {inline_cheaper} `inline_cheaper` (13.5 row 3)" in text
    assert f"so the other {first + second - inline_cheaper} inline cells are `none_clear` (row 7)" in text
    assert blind["better"] == blind["= inline"] == 0, blind
    assert (f"{blind['= delegate']} of its {rows} rows are `= delegate`, {blind['beaten on success']} beaten on "
            f"success, {blind['beaten on cost']} beaten on cost alone and {blind['trade-off']} trade-offs, and none is "
            "`better`") in text


@RED
def test_fifth_file_inline_cells_on_the_pinned_run(wdp, response_bank_pinned):
    """v1.323: where the pinned files are cached, a rerun of the 13.14 run gives each inline cost_effective cell's
    task, reason and route primary as the dated section states them."""
    from model_routing import Registry, evaluate_delegation

    code, _, err, path = response_bank_pinned
    assert code == 0, err
    with open(path, encoding="utf-8") as f:
        matrix = [json.loads(line) for line in f if line.strip()]
    spec = importlib.util.spec_from_file_location("response_bank_delegation_for_wdp", BANK_SCRIPT)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    kept, _ = script.select_rows(matrix, list(script.POOL))
    full = evaluate_delegation(kept, Registry.load(BANK_REGISTRY), bars=list(script.BARS), points=script.points(),
                               seeds=range(script.SEEDS))
    cells = [c for c in full["cells"] if c["flavor"] == "cost_effective" and c["mode"] == "inline"]
    _, _, _, inline = bank(wdp)
    assert Counter((c["bar"], c["flavor"], c["point"], c["parent"]) for c in cells) == inline
    assert {c["task"] for c in cells} == {"mmlu_pro"}
    assert all(c["delegate"] == c["parent"] == c["model"] for c in cells)
    reasons = {key: {c["reason"] for c in cells if (c["bar"], c["flavor"], c["point"], c["parent"]) == key}
               for key in inline}
    (low, low_count), (high, high_count) = sorted(inline.items())
    assert reasons == {low: {"inline_cheaper"}, high: {"none_clear"}}, reasons
    _, inline_cheaper = results_reasons()
    assert low_count == inline_cheaper
    text = section(note(), BANK)
    assert (f"puts all {low_count + high_count} on `mmlu_pro`, the {low_count} of row 3 on the bar {low[0]} row and "
            f"the {high_count} of row 7 on the bar {high[0]} row") in text
    assert "the route primary, the model always delegating sends the work to, is the parent's own model" in text
