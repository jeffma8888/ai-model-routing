"""research/livecodebench-cost.md and research/livecodebench_cost.py (DESIGN 12.17 v1.96).

The note's `text` block is the script's output on the 67 pinned LiveCodeBench files, compared byte
for byte when they are already in the default cache (CI never downloads them). Every number of the
note's prose must be in that block, so the other tests need no download; the script's reduction,
report and error exit are checked on small stubs.
"""

import ast
import contextlib
import importlib.util
import io
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "livecodebench_cost.py"
NOTE = ROOT / "research" / "livecodebench-cost.md"
INDEX = ROOT / "research" / "README.md"
CONVERT = ROOT / "evidence" / "livecodebench" / "convert.py"
COMMAND = "$ python research/livecodebench_cost.py"
SECTIONS = ["## Facts", "## Method", "## Results", "## Reading it", "## Limits", "## Regenerate"]
# DESIGN section numbers: the only numbers of the note's prose that are not in the script's output
ALLOWED = {"12.16", "12.17"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?%?")
URL = re.compile(r"https?://\S+")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lcc():
    return _load("research_livecodebench_cost", SCRIPT)


def rec(qid, text, outputs):
    return {"question_id": qid, "question_content": text, "output_list": outputs}


def test_reduce_file_reads_the_first_sample_and_counts_an_empty_string(lcc):
    cells = lcc.reduce_file([rec("a", "xyz", ["abcd</think>", "z" * 50]), rec("b", "pq", "")], "F")
    assert cells == {"a": (3, 12, True, False), "b": (2, 0, False, True)}


@pytest.mark.parametrize("records", [
    [], None, {"a": 1}, ["x"],
    [rec("a", "x", ["y"]), rec("a", "x", ["y"])],
    [{"question_content": "x", "output_list": ["y"]}],
    [rec("", "x", ["y"])],
    [rec("a", 5, ["y"])],
    [rec("a", "x", [])],
    [rec("a", "x", [1])],
    [rec("a", "x", None)],
    [rec("a", "x", "y")],
])
def test_reduce_file_rejects_what_it_cannot_read(lcc, records):
    with pytest.raises(ValueError, match="^F: "):
        lcc.reduce_file(records, "F")


def stub(differ=False):
    """Four folders: a (Low)/(High) pair, and a bare folder with a (Thinking) run; q9 is in one only."""
    reduced = {
        "M (Low)": {"q1": (10, 100, False, False), "q2": (30, 300, False, False), "q3": (20, 200, False, False)},
        "M (High)": {"q1": (10, 110, False, False), "q2": (30, 95, False, False), "q3": (20, 0, False, True)},
        "N": {"q1": (11 if differ else 10, 40, False, False), "q2": (30, 41, False, False),
              "q3": (20, 42, False, False), "q9": (5, 1, False, False)},
        "N (Thinking)": {"q1": (10, 4000, True, False), "q2": (30, 4100, True, False), "q3": (20, 900, False, False)},
    }
    return reduced


def model_of(folder):
    return "v/" + folder.lower().replace(" (", "-").replace(")", "")


def test_report_on_a_stub(lcc):
    lines = lcc.report(stub(), model_of)
    assert lines[:5] == [
        "4 files, 3 question ids in every file",
        "problem text: median 20 characters, from 10 to 30; files whose text differs from M (High)'s on some id: 0",
        "first samples recorded as an empty string, counted as 0 characters: 1 (in 1 files)",
        "output tokens estimated at 4 characters per token",
        "",
    ]
    assert lines[5].split() == ["model", "median_output_chars", "think_marker", "est_output_tokens"]
    assert set(lines[6]) == {"-", " "}
    assert [line.split() for line in lines[7:11]] == [
        ["v/m-high", "95", "0.000", "24"],
        ["v/m-low", "200", "0.000", "50"],
        ["v/n", "41", "0.000", "10"],
        ["v/n-thinking", "4,000", "0.667", "1,000"],
    ]
    assert lines[11:] == [
        "",
        "models with the marker in at least half their first samples: 1 of 4",
        "median output characters per model: from 41 to 4,000 (97.6 times)",
        "",
        "runs of one model at more than one reasoning setting (median output characters):",
        "  M: High 95  Low 200 (longest over shortest 2.11)",
        "  N: none 41  Thinking 4,000 (longest over shortest 97.56)",
    ]


def test_report_counts_a_file_whose_problem_text_differs(lcc):
    assert lcc.report(stub(differ=True), model_of)[1].endswith("files whose text differs from M (High)'s on some id: 1")


def test_main_turns_a_fetch_error_into_one_line_and_exit_2(lcc, tmp_path, monkeypatch, capsys):
    fake = tmp_path / "convert.py"
    fake.write_text("FILES = {}\n\ndef fetch(cache_dir=None):\n    raise OSError('x.json: download failed: boom')\n",
                    encoding="utf-8")
    monkeypatch.setattr(lcc, "CONVERT", fake)
    assert lcc.main(["--cache", str(tmp_path)]) == 2
    out, err = capsys.readouterr()
    assert (out, err) == ("", "error: x.json: download failed: boom\n")


def test_script_is_standard_library_only():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add(node.module.split(".")[0])
    stdlib = getattr(sys, "stdlib_module_names", None) or {
        "__future__", "argparse", "importlib", "re", "statistics", "sys", "pathlib"}
    assert names and names <= set(stdlib) | {"__future__"}


def _note():
    return NOTE.read_text(encoding="utf-8")


def _results_block(text):
    section = text.split("\n## Results\n", 1)[1].split("\n## ", 1)[0]
    return section.split("```text\n", 1)[1].split("\n```", 1)[0]


def test_note_sections_in_order():
    headings = [line for line in _note().splitlines() if line.startswith("## ")]
    assert headings == SECTIONS


def test_note_results_block_starts_with_the_command():
    assert _results_block(_note()).splitlines()[0] == COMMAND


def test_note_prose_numbers_are_in_the_results_block():
    text = _note()
    block = _results_block(text)
    prose = text.replace(block, "").split("\n## Regenerate\n", 1)[0]
    prose = DATE.sub(" ", URL.sub(" ", prose))
    known = set(NUMBER.findall(block)) | ALLOWED
    missing = sorted({n for n in NUMBER.findall(prose)} - known)
    assert not missing


def test_note_regenerate_block():
    section = _note().split("\n## Regenerate\n", 1)[1]
    commands = section.split("```bash\n", 1)[1].split("\n```", 1)[0].splitlines()
    assert commands == [COMMAND[2:]]


def test_research_index_links_the_note():
    index = INDEX.read_text(encoding="utf-8")
    assert "| [livecodebench-cost.md](livecodebench-cost.md) |" in index


def _cached():
    convert = _load("livecodebench_convert_for_cost", CONVERT)
    root = convert.default_cache_dir()
    return all((root / name).exists() for name in convert.FILES)


@pytest.mark.skipif(not _cached(), reason="the 67 pinned LiveCodeBench files are not in the default cache")
def test_note_results_block_is_the_script_output(lcc):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert lcc.main([]) == 0
    assert _results_block(_note()) == COMMAND + "\n" + out.getvalue().rstrip("\n")
