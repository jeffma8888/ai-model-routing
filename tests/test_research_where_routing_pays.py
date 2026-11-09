"""research/where-routing-pays.md and research/where_routing_pays.py (DESIGN 12.8 v1.124).

The script reads only the five committed routing results files, so the note's Results block is
compared byte for byte with a fresh run on every machine, CI included. Its report is also checked
on a small hand-made file, where each number can be worked out by hand.
"""

import ast
import contextlib
import importlib.util
import io
import json
import re
from pathlib import Path

import pytest

from model_routing.stats import wilson_lower_bound

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "where_routing_pays.py"
NOTE = ROOT / "research" / "where-routing-pays.md"
INDEX = ROOT / "research" / "README.md"
COMMAND = "$ python research/where_routing_pays.py"
SECTIONS = ["## Facts", "## Method", "## Results", "## Reading it", "## What your own data needs",
            "## Limits", "## Regenerate"]
FILES = ["evidence/routerbench/results.json", "evidence/autobench-2026/results.json",
         "evidence/autobench-judges/results.json", "evidence/tau2-bench/results.json",
         "evidence/livecodebench/results.json"]
# DESIGN section numbers: the only numbers of the note's prose that are not in the script's output
ALLOWED = {"5.3", "12.2", "12.3", "12.7", "12.8", "12.10", "12.12", "12.15", "12.17"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?%?")


def _load():
    spec = importlib.util.spec_from_file_location("research_where_routing_pays", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def wrp():
    return _load()


def run(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture(scope="module")
def output(wrp):
    code, out, err = run(wrp, ["--root", str(ROOT)])
    assert (code, err) == (0, "")
    return out


def note():
    return NOTE.read_text(encoding="utf-8")


def results_block(text):
    section = text.split("\n## Results\n", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"^```text\n(.*?)^```$", section, re.M | re.S)
    assert len(blocks) == 1, "one text block in ## Results"
    return blocks[0]


def test_note_results_block_is_the_script_output(output):
    assert results_block(note()) == COMMAND + "\n" + output


def test_note_sections_in_order():
    headings = re.findall(r"^## .*$", note(), re.M)
    assert headings == SECTIONS
    assert note().split("\n## ", 1)[0].count("\n") >= 1


def test_prose_numbers_are_in_the_output(output):
    text = note()
    prose = re.sub(r"^```text\n.*?^```$", "", text, flags=re.M | re.S)
    prose = re.sub(r"https?://\S+", "", prose)
    known = set(NUMBER.findall(output)) | ALLOWED
    stray = sorted(set(NUMBER.findall(prose)) - known)
    assert not stray, stray


def test_regenerate_section_states_the_command():
    section = note().split("\n## Regenerate\n", 1)[1]
    assert "python -m pip install -e ." in section
    assert COMMAND[2:] in section


def test_note_names_each_results_file_it_reads():
    for rel in FILES:
        assert f"`{rel}`" in note(), rel


def test_research_index_row_and_bullet():
    text = INDEX.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| [where-routing-pays.md](where-routing-pays.md) | ")]
    assert len(rows) == 1
    assert "[where_routing_pays.py](where_routing_pays.py)" in rows[0]
    assert sum(1 for line in text.splitlines() if line.startswith("- `research/where-routing-pays.md` ")) == 1


def test_script_imports_only_the_standard_library_and_the_stats_module():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module if node.module.startswith("model_routing") else node.module.split(".")[0])
    assert names <= {"argparse", "json", "sys", "collections", "pathlib", "statistics",
                     "model_routing.stats"}, names


def test_a_missing_file_is_one_error_line(wrp, tmp_path):
    code, out, err = run(wrp, ["--root", str(tmp_path)])
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1


def small(best_cost=2.0):
    """Two tasks, three seeds, one flavor, one bar: worked out by hand in the test below."""
    summary = []
    for strategy, success, cost in [("routed", 0.7, 1.0), ("best_on_calibration", 0.75, 1.5),
                                    ("model:a/one", 0.8, best_cost), ("model:b/two", 0.6, 0.5)]:
        summary.append({"bar": 0.5, "flavor": "cost_effective", "strategy": strategy, "success": success,
                        "cost_usd": cost, "cleared_rate": 0.5})
    per_task = [
        {"bar": 0.5, "flavor": "cost_effective", "task": "t1", "routed_models": {"a/one": 3}},
        {"bar": 0.5, "flavor": "cost_effective", "task": "t2", "routed_models": {"a/one": 1, "b/two": 2}},
    ]
    return {"config": {"bars": [0.5], "seeds": [0, 1, 2], "flavors": ["cost_effective"],
                       "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95},
            "tasks": {"t1": {"items": 41, "models": ["a/one", "b/two"]},
                      "t2": {"items": 120, "models": ["a/one", "b/two"]}},
            "summary": summary, "per_task": per_task}


def test_report_on_a_small_file(wrp):
    lines = wrp.report("Small", "x/results.json", small())
    assert lines[0] == ("Small (x/results.json): 2 tasks, 2 models, 3 seeds, calibration_fraction 0.5, "
                        "min_samples 30, confidence 0.95")
    # int(41 * 0.5) = 20 is below min_samples 30, int(120 * 0.5) = 60 is not
    assert lines[1] == ("  items per task: t1 41, t2 120; expected calibration half: 20, 60; "
                        "tasks whose half is below min_samples: 1")
    # the median of 41 and 120 items is 80.5, so the median half is int(40.25) = 40
    low = 0.8 - wilson_lower_bound(16, 20, 0.95)
    mid = 0.8 - wilson_lower_bound(32, 40, 0.95)
    assert lines[2] == (f"  best single model: a/one, held-out success 0.800 at 2.0000 USD; Wilson shortfall "
                        f"of that success: {low:.3f} at a half of 20, {mid:.3f} at 40")
    assert lines[3].endswith("held-out success 0.750 at 1.5000 USD")
    # picks over 2 tasks x 3 seeds: a/one 4, b/two 2, so 2 models, 1 task with two, top share 4/6
    assert lines[-1].split() == ["0.5", "cost_effective", "0.700", "1.0000", "0.500", "0.500", "2", "1",
                                 "0.667"]


def test_a_zero_best_cost_prints_a_dash(wrp):
    assert wrp.report("Small", "x", small(best_cost=0.0))[-1].split()[4] == "-"


def test_a_best_model_that_differs_by_flavor_is_an_error(wrp, tmp_path):
    data = small()
    data["config"]["flavors"] = ["cost_effective", "cost_blind"]
    for r in list(data["summary"]):
        twin = dict(r, flavor="cost_blind")
        if r["strategy"] == "model:b/two":
            twin["success"] = 0.9
        data["summary"].append(twin)
    data["per_task"] += [dict(p, flavor="cost_blind") for p in data["per_task"]]
    with pytest.raises(ValueError, match="best single model differs"):
        wrp.report("Small", "x", data)


def test_a_repeated_summary_row_is_an_error(wrp):
    data = small()
    data["summary"].append(dict(data["summary"][0]))
    with pytest.raises(ValueError, match="2 summary rows"):
        wrp.report("Small", "x", data)
