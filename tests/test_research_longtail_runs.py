"""Longtail-SWE runs 0, 1 and 2 side by side (DESIGN 12.22 v1.490, row E26h): research/longtail-runs.md and
its script research/longtail_runs.py. CI has neither `pyarrow` nor the four pinned files, so the tests that run
the script on them skip there; the others read the note, DESIGN.md, research/README.md and the committed run-0
file evidence/longtail-swe/results.json."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "research" / "longtail-runs.md"
SCRIPT = ROOT / "research" / "longtail_runs.py"
COMMITTED = ROOT / "evidence" / "longtail-swe" / "results.json"
DESIGN = ROOT / "DESIGN.md"
RESEARCH_README = ROOT / "research" / "README.md"
BULLET = "- Longtail-SWE runs 0, 1 and 2 (v1.490, row E26h): "
SOL61 = "openai/gpt-6.1-sol"
NUMBER = re.compile(r"\d+(?:[.,]\d+)*")


def load():
    if not SCRIPT.is_file():
        raise FileNotFoundError(f"no script at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("longtail_runs_for_tests", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def note():
    return NOTE.read_text(encoding="utf-8")


def results_block(text):
    found = re.findall(r"\n## Results\n\n```text\n(.*?)```\n", text, re.S)
    assert len(found) == 1
    return found[0]


def section(text, heading):
    start = text.index(f"\n## {heading}\n") + 1
    end = text.find("\n## ", start + 1)
    return text[start:] if end < 0 else text[start:end + 1]


def committed_summary():
    return json.loads(COMMITTED.read_text(encoding="utf-8"))["summary"]


def test_design_12_22_specifies_the_note_and_12_26_names_it():
    design = DESIGN.read_text(encoding="utf-8")
    lines = [line for line in design.split("\n") if line.startswith(BULLET)]
    assert len(lines) == 1
    start = design.index("\n### 12.22 ")
    assert start < design.index(lines[0]) < design.index("\n### 12.23 ")
    for phrase in ("`research/longtail-runs.md` and its script `research/longtail_runs.py`",
                   "a bad option exits 2 with one `error:` line", "requires run 0 to be the committed "
                   "`evidence/longtail-swe/results.json` byte for byte", "the 4 unscored runs (1, 1 and 2, all "
                   f"`{SOL61}`)", "`research/README.md` lists the note"):
        assert phrase in lines[0], phrase
    assert ("- Runs 1 and 2 (row E26h): the 12.22 note `research/longtail-runs.md` (v1.490) holds them beside run 0. "
            "Not in this version: the README subsection (row E26e, after its room row E26i)") in design
    assert "\u2013" not in lines[0] and "\u2014" not in lines[0]


@pytest.mark.xfail(strict=True, raises=FileNotFoundError)
def test_research_readme_lists_the_note():
    note()  # FileNotFoundError until the note exists
    text = RESEARCH_README.read_text(encoding="utf-8")
    assert text.count("| [longtail-runs.md](longtail-runs.md) | ") == 1
    assert text.count("[longtail_runs.py](longtail_runs.py)") == 1
    assert text.count("\n- `research/longtail-runs.md` ") == 1


@pytest.mark.xfail(strict=True, raises=FileNotFoundError)
def test_run_0_lines_of_the_block_are_built_from_the_committed_file():
    lt, block = load(), results_block(note())
    summary = committed_summary()
    models = json.loads(COMMITTED.read_text(encoding="utf-8"))["models"]
    lines = lt.routed_lines(0, summary) + lt.model_lines(0, summary, models) + [lt.baseline_line(0, summary)]
    assert len(lines) == 8 + 4 + 1
    for line in lines:
        assert block.count(line + "\n") == 1, line


@pytest.mark.xfail(strict=True, raises=FileNotFoundError)
def test_the_committed_model_rows_and_baseline_are_the_same_at_every_bar_and_flavor():
    lt = load()
    summary = committed_summary()
    for strategy in ["best_on_calibration"] + [r["strategy"] for r in summary if r["strategy"].startswith("model:")]:
        rows = [(r["success"], r["cost_usd"]) for r in summary if r["strategy"] == strategy]
        assert len(rows) == len(lt.BARS) * len(lt.FLAVORS) and len(set(rows)) == 1, strategy


@pytest.mark.xfail(strict=True, raises=FileNotFoundError)
def test_each_reading_it_number_is_in_the_block():
    text = note()
    block = set(NUMBER.findall(results_block(text)))
    reading = section(text, "Reading it")
    found = NUMBER.findall(reading)
    assert len(found) >= 10
    assert [n for n in found if n not in block] == []


@pytest.mark.xfail(strict=True, raises=FileNotFoundError)
def test_a_bad_option_exits_2_with_one_error_line(capsys):
    lt = load()
    assert lt.main(["--bogus"]) == 2
    out, err = capsys.readouterr()
    assert out == "" and err.startswith("error: ") and err.count("\n") == 1


# --- the pinned files, only with pyarrow and when already cached (the script's collect, once) ----------

@pytest.fixture(scope="module")
def data():
    lt = load()
    pytest.importorskip("pyarrow")
    cache = lt.CONVERT.default_cache_dir()
    if not all((cache / name).is_file() for name in lt.CONVERT.FILES):
        pytest.skip("the pinned files are not in the default cache")
    return lt, lt.collect(lt.records())


@pytest.mark.xfail(strict=True, raises=FileNotFoundError)
def test_note_results_block_is_the_script_output(data):
    lt, runs = data
    assert results_block(note()) == lt.block(runs)


@pytest.mark.xfail(strict=True, raises=FileNotFoundError)
def test_run_0_is_the_committed_results_file(data):
    _, runs = data
    assert json.dumps(runs[0][1], indent=2) + "\n" == COMMITTED.read_text(encoding="utf-8")


@pytest.mark.xfail(strict=True, raises=FileNotFoundError)
def test_each_run_has_one_model_row_and_baseline_at_every_bar_and_flavor(data):
    lt, runs = data
    for run, (report, reduced) in runs.items():
        assert report["run"] == run and report["tasks"] == {lt.CONVERT.TASK: {"items": 194}}
        for strategy in ["best_on_calibration"] + [f"model:{m}" for m in report["models"]]:
            rows = {(r["success"], r["cost_usd"]) for r in reduced["summary"] if r["strategy"] == strategy}
            assert len(rows) == 1, (run, strategy)


@pytest.mark.xfail(strict=True, raises=FileNotFoundError)
def test_the_unscored_runs_are_four_all_one_model(data):
    _, runs = data
    counts = [{m: len(v) for m, v in report["unscored"].items() if v} for report, _ in runs.values()]
    assert counts == [{SOL61: 1}, {SOL61: 1}, {SOL61: 2}]
