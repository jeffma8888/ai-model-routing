"""research/where-routing-pays.md and research/where_routing_pays.py (DESIGN 12.8 v1.124, v1.166).

The script reads only the committed routing results files, six since v1.166, so the note's Results block is
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
MANY = "## Many-task data: LLMRouterBench (2026-11-09)"
SECTIONS = ["## Facts", "## Method", "## Results", "## Reading it", MANY, "## What your own data needs",
            "## Limits", "## Regenerate"]
FILES = ["evidence/routerbench/results.json", "evidence/autobench-2026/results.json",
         "evidence/autobench-judges/results.json", "evidence/tau2-bench/results.json",
         "evidence/livecodebench/results.json", "evidence/llmrouterbench/results.json"]
# DESIGN section numbers: the only numbers of the note's prose that are not in the script's output
ALLOWED = {"5.3", "12.2", "12.3", "12.7", "12.8", "12.10", "12.12", "12.15", "12.17", "12.19"}
README = ROOT / "README.md"
# v1.166: the opening of the dated section, before any number
FINDING = ("The finding of the first five files does not hold on LLMRouterBench: routing passes the best "
           "single model's held-out success there")
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
    # v1.167: an ISO date, such as the dated section's, is no claim
    prose = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", prose)
    # a code span holds a model ID, a path or a name, whose digits are not a claim (review iter-115)
    prose = re.sub(r"`[^`\n]*`", "", prose)
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


def test_no_routed_row_reaches_the_best_single_model(wrp):
    """The note's main claim (Facts bullet 3), checked on the files, not only on the printed digits:
    on the first five files since v1.166, LLMRouterBench being the sixth."""
    for _, rel in wrp.DATASETS[:5]:
        results = json.loads((ROOT / rel).read_text(encoding="utf-8"))
        config = results["config"]
        best = wrp.best_single(results, config["bars"][0], config["flavors"][0])
        boc = wrp.summary_row(results, config["bars"][0], config["flavors"][0], "best_on_calibration")
        routed = [wrp.summary_row(results, bar, flavor, "routed")
                  for bar in config["bars"] for flavor in config["flavors"]]
        assert max(r["success"] for r in routed) < best["success"], rel
        assert boc["success"] < best["success"], rel
    assert "no routed row at any bar or flavor reaches the best single model's held-out success" in note()


# not an object (TypeError), not JSON (ValueError), no key (KeyError), a list for `tasks` (AttributeError)
WRONG_TASKS = json.dumps({"config": {"bars": [0.5], "seeds": [0], "flavors": ["cost_blind"],
                                     "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95},
                          "tasks": [], "summary": [], "per_task": []})


@pytest.mark.parametrize("document", ["[]", "{", "{}", WRONG_TASKS])
def test_a_bad_document_is_one_error_line(wrp, tmp_path, document):
    path = tmp_path / "evidence" / "routerbench" / "results.json"
    path.parent.mkdir(parents=True)
    path.write_text(document, encoding="utf-8")
    code, out, err = run(wrp, ["--root", str(tmp_path)])
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1


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
    # picks over 2 tasks x 3 seeds: a/one 4, b/two 2, so 2 models, 1 task with two, top share 4/6;
    # v1.166: t2 picks b/two on some seed (off best 1), no task never picks a/one, gain 0.7 - 0.8
    assert lines[-1].split() == ["0.5", "cost_effective", "0.700", "1.0000", "0.500", "0.500", "2", "1",
                                 "0.667", "1", "0", "-0.1000"]


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


# --- v1.166: LLMRouterBench, the tasks off the best model and the in-sample gain -------------

def committed(rel):
    return json.loads((ROOT / rel).read_text(encoding="utf-8"))


def section(text, heading):
    return text.split("\n" + heading + "\n", 1)[1].split("\n## ", 1)[0]


def test_the_script_reads_the_six_files_in_order(wrp):
    assert [rel for _, rel in wrp.DATASETS] == FILES
    assert [name for name, _ in wrp.DATASETS][5] == "LLMRouterBench"


def test_llmrouterbench_routing_passes_the_best_single_model(wrp):
    """The dated section's finding, checked on the file: best_on_calibration and every cost_blind
    routed row pass the best single model, the cost_effective rows that pass are the highest bars,
    each passing row costs under half that model's cost, and cost_blind keeps over half the gain."""
    results = committed(FILES[5])
    config = results["config"]
    best = wrp.best_single(results, config["bars"][0], config["flavors"][0])
    boc = wrp.summary_row(results, config["bars"][0], config["flavors"][0], "best_on_calibration")
    assert boc["success"] > best["success"]
    passing = {}
    for flavor in config["flavors"]:
        rows = [wrp.summary_row(results, bar, flavor, "routed") for bar in config["bars"]]
        passing[flavor] = [r["bar"] for r in rows if r["success"] > best["success"]]
        assert all(r["cost_usd"] < 0.5 * best["cost_usd"] for r in rows if r["success"] > best["success"])
    assert passing["cost_blind"] == config["bars"]
    assert passing["cost_effective"] and passing["cost_effective"] == config["bars"][-len(passing["cost_effective"]):]
    source, model, gain = wrp.IN_SAMPLE["LLMRouterBench"]
    assert best["strategy"] == "model:" + model
    blind = [wrp.summary_row(results, bar, "cost_blind", "routed")["success"] for bar in config["bars"]]
    assert min(blind) - best["success"] > 0.5 * gain
    text = section(note(), MANY)
    opening = text.strip("\n").split("\n\n", 1)[0]
    assert opening.startswith(FINDING)
    assert not re.search(r"\d", opening), opening


def test_report_counts_the_tasks_off_the_best_model(wrp):
    data = small()
    data["per_task"][0]["routed_models"] = {"b/two": 3}
    # t1 never picks a/one and t2 picks b/two on 2 seeds: off best 2, never best 1;
    # picks a/one 1, b/two 5, so top share 5/6
    assert wrp.report("Small", "x", data)[-1].split() == [
        "0.5", "cost_effective", "0.700", "1.0000", "0.500", "0.500", "2", "1", "0.833", "2", "1", "-0.1000"]


def test_in_sample_line_on_a_small_file(wrp, monkeypatch):
    monkeypatch.setitem(wrp.IN_SAMPLE, "Small", ("x.md", "a/one", 0.2))
    lines = wrp.report("Small", "x", small())
    # best_on_calibration 0.75 - 0.8 = -0.05, over 0.2 is -0.25; routed 0.7 - 0.8 = -0.1, so -0.50
    assert lines[4] == ("  in-sample per-task gain over a/one on all items (x.md): 0.2000; share of it kept "
                        "on the held-out halves: best_on_calibration -0.25, routed cost_effective -0.50")
    assert lines[5].startswith("  not in the file: ")
    assert not any(line.startswith("  in-sample") for line in wrp.report("Other", "x", small()))


def test_in_sample_range_over_the_bars(wrp, monkeypatch):
    data = small()
    data["config"]["bars"] = [0.5, 0.6]
    for r in list(data["summary"]):
        twin = dict(r, bar=0.6)
        if r["strategy"] == "routed":
            twin["success"] = 0.9
        data["summary"].append(twin)
    data["per_task"] += [dict(p, bar=0.6) for p in data["per_task"]]
    monkeypatch.setitem(wrp.IN_SAMPLE, "Small", ("x.md", "a/one", 0.2))
    # routed gains -0.1 and +0.1 over 0.2: -0.50 to 0.50
    assert wrp.report("Small", "x", data)[4].endswith("routed cost_effective -0.50 to 0.50")


def test_in_sample_model_must_be_the_best_single_model(wrp, monkeypatch):
    monkeypatch.setitem(wrp.IN_SAMPLE, "Small", ("x.md", "b/two", 0.2))
    with pytest.raises(ValueError, match="best single model is a/one"):
        wrp.report("Small", "x", small())


def test_in_sample_gain_is_the_datasets_note(wrp):
    source, model, gain = wrp.IN_SAMPLE["LLMRouterBench"]
    assert list(wrp.IN_SAMPLE) == ["LLMRouterBench"]
    lines = [x for x in (ROOT / source).read_text(encoding="utf-8").splitlines()
             if x.startswith(f"  - Performance-cost pool: best single model `{model}`")]
    assert len(lines) == 1
    assert f"Each task's own best model reaches 0.6240 (+{gain:.4f})" in lines[0]
    assert f"(+{gain:.4f})" in lines[0]


WORDS = {5: "five", 6: "six", 7: "seven"}


def limitations_bullet(wrp):
    """README Limitations bullet 2 (v1.166), its dataset names and counts built from the files."""
    passing = []
    for name, rel in wrp.DATASETS:
        results = committed(rel)
        config = results["config"]
        best = wrp.best_single(results, config["bars"][0], config["flavors"][0])
        if any(wrp.summary_row(results, bar, flavor, "routed")["success"] > best["success"]
               for bar in config["bars"] for flavor in config["flavors"]):
            passing.append(name)
    assert passing == ["LLMRouterBench"], passing
    n = len(wrp.DATASETS)
    gap, ratio = response_bank_gap(wrp, committed("evidence/response-bank/results.json"))
    return ("- Routing per task pays in held-out success only where tasks differ in their best model and "
            "each task's calibration half can tell the models apart. Of the first "
            f"{WORDS[n]} routing datasets above, {passing[0]} alone has a routed row above the best single "
            f"model's held-out success; on the other {WORDS[n - 1]}, routing pays at most in cost, at a bar "
            "below that success ([research/where-routing-pays.md](research/where-routing-pays.md)). The "
            f"{ORDINAL[n + 1]}, the LLM Routing Response Bank, which that note does not read yet, has one too: "
            f"`cost_blind` routing, {gap:.4f} above that model's held-out success at {ratio:.3f} times its cost")


ORDINAL = {7: "seventh"}


def response_bank_gap(wrp, results):
    """v1.296 (DESIGN 12.8): `cost_blind`'s one success and cost at every bar against the best
    single model of 12.7, as the gap in success and the ratio of cost."""
    config = results["config"]
    best = wrp.best_single(results, config["bars"][0], config["flavors"][0])
    blind = [wrp.summary_row(results, bar, "cost_blind", "routed") for bar in config["bars"]]
    assert all((r["success"], r["cost_usd"]) == (blind[0]["success"], blind[0]["cost_usd"]) for r in blind), \
        "the cost_blind rows differ between bars"
    assert blind[0]["success"] > best["success"], "cost_blind is not above the best single model"
    return blind[0]["success"] - best["success"], blind[0]["cost_usd"] / best["cost_usd"]


def test_response_bank_gap_is_the_committed_file(wrp):
    results = committed("evidence/response-bank/results.json")
    gap, ratio = response_bank_gap(wrp, results)
    assert (f"{gap:.4f}", f"{ratio:.3f}") == ("0.0022", "2.104")
    fake = json.loads(json.dumps(results))
    wrp.summary_row(fake, 0.9, "cost_blind", "routed")["success"] = 0.5
    with pytest.raises(AssertionError, match="differ between bars"):
        response_bank_gap(wrp, fake)
    for bar in (0.8, 0.9):
        wrp.summary_row(fake, bar, "cost_blind", "routed")["success"] = 0.5
    with pytest.raises(AssertionError, match="not above"):
        response_bank_gap(wrp, fake)


def test_readme_limitations_and_the_index_say_where_routing_passes(wrp):
    readme = README.read_text(encoding="utf-8")
    limits = readme.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in limits.splitlines() if line.startswith("- ")]
    assert bullets[1] == limitations_bullet(wrp)
    assert sum("(research/where-routing-pays.md)" in b for b in bullets) == 1
    rows = [x for x in INDEX.read_text(encoding="utf-8").splitlines()
            if x.startswith("| [where-routing-pays.md](where-routing-pays.md) | ")]
    assert len(rows) == 1 and "On LLMRouterBench" in rows[0] and "three of the five" not in rows[0]
