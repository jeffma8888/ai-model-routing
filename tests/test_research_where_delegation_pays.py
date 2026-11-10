"""research/where-delegation-pays.md and research/where_delegation_pays.py (DESIGN 13.8 v1.206).

The script reads only the four committed delegation results files, so the note's Results block is
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
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "where_delegation_pays.py"
NOTE = ROOT / "research" / "where-delegation-pays.md"
INDEX = ROOT / "research" / "README.md"
DESIGN = ROOT / "DESIGN.md"
COMMAND = "$ python research/where_delegation_pays.py"
SECTIONS = ["## Facts", "## Method", "## Results", "## Reading it", "## Recommendation", "## Limits",
            "## Regenerate"]
FILES = ["evidence/delegation/results.json", "evidence/tau2-bench-delegation/results.json",
         "evidence/tau2-bench-delegation/pooled.json", "evidence/llmrouterbench-delegation/results.json"]
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


def test_note_sections_in_order():
    assert re.findall(r"^## .*$", note(), re.M) == SECTIONS


def test_prose_numbers_are_in_the_output(output):
    prose = re.sub(r"^```text\n.*?^```$", "", note(), flags=re.M | re.S)
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


def test_report_on_small_files(wdp, tmp_path):
    root = write_root(tmp_path, [SMALL] * 4)
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
    assert lines[-3:] == ["All four files", wdp.HEADER,
                          "  cost_effective  all     16           4         4       0"
                          "                  4               0          4            4"]
    assert len(lines) == 1 + 4 * 6 + 3


def test_no_changed_row_and_task_plural(wdp, tmp_path):
    document = small_file(triple(0.5, "cost_effective", 0, "a/p", (0.5, 2.0), (0.4, 3.0), (0.5, 2.0), 1.0),
                          parents=("a/p",))
    document["tasks"]["u"] = {"items": 5, "models": ["a/p"]}
    code, out, err = run(wdp, ["--root", str(write_root(tmp_path, [document] * 4))])
    assert (code, err) == (0, "")
    lines = out.splitlines()
    assert lines[1].endswith(": 1 rows, 2 tasks, bars 0.5, 2 points, 1 parents")
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
    "not JSON": "{",
    "not an object": "[]",
}


@pytest.mark.parametrize("case", sorted(BAD))
def test_a_bad_file_is_one_error_line(wdp, tmp_path, case):
    root = write_root(tmp_path, [SMALL, SMALL, BAD[case], SMALL])
    code, out, err = run(wdp, ["--root", str(root)])
    assert (code, out) == (2, "")
    assert err.count("\n") == 1 and err.startswith("error: evidence/tau2-bench-delegation/pooled.json: "), err


def test_a_missing_file_is_one_error_line(wdp, tmp_path):
    root = write_root(tmp_path, [SMALL, SMALL, SMALL])
    code, out, err = run(wdp, ["--root", str(root)])
    assert (code, out) == (2, "")
    assert err == "error: evidence/llmrouterbench-delegation/results.json: no such file\n"


def committed(wdp):
    for name, rel in wdp.DATASETS:
        results = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        yield name, results, wdp.rows_of(results, rel)


def test_the_script_reads_the_four_files_in_order(wdp):
    assert [rel for _, rel in wdp.DATASETS] == FILES


def test_cost_effective_changes_only_where_inline_folds(wdp):
    """Reading it: every cost_effective row at a separate-call point is `= delegate`."""
    for name, results, groups in committed(wdp):
        points = results["config"]["points"]
        for key, group in groups.items():
            kind = wdp.classify(group["decision"], group["inline"], group["delegate"])
            if key[1] == "cost_effective" and points[key[2]]["inline_separate_call"]:
                assert kind == "= delegate", (name, key, kind)


def test_no_row_is_better_than_both(wdp):
    """Facts: on no row of either flavor is the decision better than both fixed policies."""
    for name, _, groups in committed(wdp):
        for key, group in groups.items():
            assert wdp.classify(group["decision"], group["inline"], group["delegate"]) != "better", (name, key)


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
    code, out, err = run(wdp, ["--root", str(write_root(tmp_path, [document] * 4))])
    assert (code, err) == (0, "")
    assert out.splitlines()[5] == ("  against always delegate, cost_effective: 1 changed rows, 0 cheaper "
                                   "(0 of them at no less success), 1 not cheaper")
