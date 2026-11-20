"""Row ESC1c (DESIGN 7 v1.534): research/escalation_public_tests.py and the note section it feeds.

The script reads one pinned LiveCodeBench problem release file and the runner's two files at a pinned
commit, and matches each kept file's failed first samples, by the failing test the runner recorded,
against the problem's public test cases. research/escalation.md `## Public tests matched (row ESC1c)`
holds its output, compared byte for byte when the submission, release and runner files are already in
the default cache (CI never downloads them), and every number of that section's prose is in the block,
so the other tests need no download; the parts are checked on small stubs."""

import ast
import contextlib
import importlib.util
import io
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "escalation_public_tests.py"
NOTE = ROOT / "research" / "escalation.md"
DESIGN = ROOT / "DESIGN.md"
CHANGELOG = ROOT / "CHANGELOG.md"
CONVERT = ROOT / "evidence" / "livecodebench" / "convert.py"
COMMAND = "$ python research/escalation_public_tests.py"
MATCHED = "Public tests matched (row ESC1c)"
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
VERSION = re.compile(r"\bv\d+\.\d+\b")
MARK = "...(truncated) ..."


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def pt():
    return _load("research_escalation_public_tests", SCRIPT)


@pytest.fixture(scope="module")
def convert():
    return _load("livecodebench_convert_for_public_tests", CONVERT)


def test_truncate_copies_the_runner_truncatefn(pt):
    assert pt.truncate("abc") == "abc"
    assert pt.truncate("x" * 300) == "x" * 300
    assert pt.truncate("a" * 150 + "b" + "c" * 150) == "a" * 150 + MARK + "c" * 150
    assert pt.truncate(12) == "12"
    # the runner slices s[-length // 2:], which for an odd length keeps one more character at the end
    assert pt.truncate("abcdefgh", 5) == "ab" + MARK + "fgh"


LONG = "9" * 400


def case(i, o, kind="stdin"):
    return {"input": i, "output": o, "testtype": kind}


def line(qid, date, cases):
    return json.dumps({"question_id": qid, "contest_date": date, "public_test_cases": json.dumps(cases),
                       "private_test_cases": "eJw=", "difficulty": "easy"})


LINES = [
    line("q2", "2024-08-10T00:00:00", [case("a", "b", "functional")]),
    line("q1", "2024-06-01T00:00:00", [case("1\n", "2\n"), case(LONG, "3\n"), case("5\n", "6\n")]),
]


def test_read_release_keeps_each_problem_date_and_truncated_public_cases(pt):
    got = pt.read_release(LINES, "t.jsonl")
    assert list(got) == ["q1", "q2"]
    assert got["q1"] == {"date": "2024-06-01",
                         "cases": [("1\n", "2\n"), ("9" * 150 + MARK + "9" * 150, "3\n"), ("5\n", "6\n")]}
    assert got["q2"] == {"date": "2024-08-10", "cases": [("a", "b")]}


@pytest.mark.parametrize("lines", [
    [],
    ["not json"],
    ["[1]"],
    [json.dumps({"contest_date": "2024-06-01", "public_test_cases": "[]"})],
    [LINES[0], LINES[0]],
    [line("q1", "June", [case("1", "2")])],
    [line("q1", "2024-06-01", [])],
    [line("q1", "2024-06-01", [{"input": "1"}])],
    [json.dumps({"question_id": "q1", "contest_date": "2024-06-01", "public_test_cases": "nope"})],
    [json.dumps({"question_id": "q1", "contest_date": "2024-06-01"})],
])
def test_read_release_rejects_what_it_cannot_read(pt, lines):
    with pytest.raises(ValueError, match="^t.jsonl"):
        pt.read_release(lines, "t.jsonl")


@pytest.mark.parametrize("record, want", [
    ({"metadata": [json.dumps({"a": 1})]}, {"a": 1}),
    ({"metadata": [{"a": 1}, "x"]}, {"a": 1}),
    ({}, None),
    ({"metadata": "{}"}, None),
    ({"metadata": []}, None),
])
def test_first_metadata_reads_the_first_sample_entry(pt, record, want):
    assert pt.first_metadata(record, "at") == want


@pytest.mark.parametrize("record", [{"metadata": ["[1]"]}, {"metadata": ["{bad"]}, {"metadata": [3]}])
def test_first_metadata_rejects_an_entry_it_cannot_read(pt, record):
    with pytest.raises(ValueError, match="^at: "):
        pt.first_metadata(record, "at")


CASES = [("1\n", "2\n"), ("x", "y")]


@pytest.mark.parametrize("meta, want", [
    (None, ("unread", None)),
    ({"error_code": -4, "error_message": "boom"}, ("no_test", None)),
    ({"inputs": "x", "expected": "y", "output": "z"}, ("public", 1)),
    ({"inputs": "1\n", "expected": "2\n", "error": "t"}, ("public", 0)),
    ({"inputs": "x", "expected": "z"}, ("input_only", None)),
    ({"inputs": "q", "expected": "y"}, ("other", None)),
])
def test_classify_names_how_a_failing_test_matched(pt, meta, want):
    assert pt.classify(meta, CASES, "at") == want


@pytest.mark.parametrize("meta", [{"inputs": 3, "expected": "y"}, {"inputs": "x"}])
def test_classify_rejects_a_test_it_cannot_compare(pt, meta):
    with pytest.raises(ValueError, match="^at: "):
        pt.classify(meta, CASES, "at")


def rec(qid, ok, *meta):
    r = {"question_id": qid, "contest_date": "2024-06-01T00:00:00", "graded_list": [ok, True]}
    if meta:
        r["metadata"] = meta[0]
    return r


FILE_A = [rec("q1", False, [json.dumps({"inputs": "9" * 150 + MARK + "9" * 150, "expected": "3\n", "output": "4\n",
                                         "error_code": -2})]),
          rec("q2", False, [{"inputs": "a", "expected": "c", "error_code": -2}]),
          rec("q3", False, [json.dumps({"inputs": "a", "expected": "b"})])]
FILE_B = [rec("q1", False, [json.dumps({"error_code": -4, "error_message": "x"})]), rec("q2", True, "{}")]
FILE_C = [rec("q1", False), rec("q2", False, [json.dumps({"inputs": "z", "expected": "b"})]),
          rec("q3", True, [json.dumps({"execution time": 1.0})])]


def reduced(pt, convert):
    release = pt.read_release(LINES, "t.jsonl")
    return [pt.reduce_file(FILE_A, "GPT-4-0613", release, convert),
            pt.reduce_file(FILE_B, "Claude-3-Haiku", release, convert),
            pt.reduce_file(FILE_C, "Qwen2-Ins-72B", release, convert)], release


def test_reduce_file_counts_each_kind_over_the_sample_problems(pt, convert):
    (a, b, c), _ = reduced(pt, convert)
    assert a == {"model": "openai/gpt-4-0613", "items": {"q1", "q2", "q3"}, "index": {1: 1},
                 "counts": {"problems": 2, "failed": 2, "public": 1, "other": 0, "input_only": 1, "no_test": 0,
                            "unread": 0}}
    assert b["counts"] == {"problems": 2, "failed": 1, "public": 0, "other": 0, "input_only": 0, "no_test": 1,
                           "unread": 0}
    assert c["counts"] == {"problems": 2, "failed": 2, "public": 0, "other": 1, "input_only": 0, "no_test": 0,
                           "unread": 1}
    assert b["index"] == c["index"] == {}


def test_report_on_a_stub(pt, convert):
    rows, release = reduced(pt, convert)
    lines = pt.report(rows, release, ("r" * 40, "u" * 40, "s" * 40))
    assert lines[:5] == [
        f"problem release livecodebench/code_generation_lite at {'r' * 40}, read: test3.jsonl",
        f"runner LiveCodeBench/LiveCodeBench at {'u' * 40}: public cases before private ones "
        "(get_evaluation_sample), the failing case recorded by truncatefn at 300 characters",
        f"submissions at {'s' * 40}: 3 kept files, 2 problems in every one (the 12.16 kept problems)",
        "sample problems: 2, contest dates 2024-06-01 to 2024-08-10, public cases per problem 1 to 3 (median 2), "
        "among the 12.16 kept problems: 2",
        "",
    ]
    assert lines[5].split() == ["model", "problems", "failed", "public", "other", "input_only", "no_test", "unread",
                                "public_share", "public_of_tested"]
    assert [row.split() for row in lines[7:11]] == [
        ["anthropic/claude-3-haiku", "2", "1", "0", "0", "0", "1", "0", "0.000", "n/a"],
        ["openai/gpt-4-0613", "2", "2", "1", "0", "1", "0", "0", "0.500", "0.500"],
        ["qwen/qwen2-ins-72b", "2", "2", "0", "1", "0", "0", "1", "0.000", "0.000"],
        ["all", "6", "5", "1", "1", "1", "1", "1", "0.200", "0.333"],
    ]
    assert lines[11:] == ["", "public matches by the 0-based index of the matched case: 1: 1"]


def test_report_says_none_when_no_sample_matched_a_public_case(pt, convert):
    release = pt.read_release(LINES, "t.jsonl")
    lines = pt.report([pt.reduce_file(FILE_B, "Claude-3-Haiku", release, convert)], release, ("r", "u", "s"))
    assert lines[-1] == "public matches by the 0-based index of the matched case: none"


RUNNER_OK = {
    "lcb_runner/benchmarks/code_generation.py":
        "x = [t.input\n for t in self.public_test_cases + self.private_test_cases]\n"
        "y = [t.output\n for t in self.public_test_cases + self.private_test_cases]\n",
    "lcb_runner/evaluation/testing_util.py": "def truncatefn(s, length=300):\n    return s\n",
}


def test_check_runner_reads_the_order_and_the_truncation(pt):
    pt.check_runner(RUNNER_OK)
    one = dict(RUNNER_OK)
    one["lcb_runner/benchmarks/code_generation.py"] = "for t in self.private_test_cases + self.public_test_cases\n" * 2
    with pytest.raises(ValueError, match="^code_generation.py: "):
        pt.check_runner(one)
    two = dict(RUNNER_OK)
    two["lcb_runner/evaluation/testing_util.py"] = "def truncatefn(s, length=200):\n"
    with pytest.raises(ValueError, match="^testing_util.py: "):
        pt.check_runner(two)


def test_main_turns_a_fetch_error_into_one_line_and_exit_2(pt, tmp_path, monkeypatch, capsys):
    fake = tmp_path / "convert.py"
    fake.write_text("FILES = {}\n\ndef fetch(cache_dir=None):\n    raise OSError('x.json: download failed: boom')\n",
                    encoding="utf-8")
    monkeypatch.setattr(pt, "CONVERT", fake)
    assert pt.main(["--cache", str(tmp_path)]) == 2
    assert capsys.readouterr() == ("", "error: x.json: download failed: boom\n")


def test_release_and_runner_files_are_pinned(pt):
    assert list(pt.RELEASE_FILES) == ["test.jsonl", "test2.jsonl", "test3.jsonl", "test4.jsonl", "test5.jsonl",
                                      "test6.jsonl"]
    for size, sha256 in list(pt.RELEASE_FILES.values()) + list(pt.RUNNER_FILES.values()):
        assert isinstance(size, int) and size > 0 and re.fullmatch(r"[0-9a-f]{64}", sha256)
    assert pt.SAMPLE == ("test3.jsonl",)
    assert pt.RELEASE_FILES["test3.jsonl"][0] == 623360766
    assert list(pt.RUNNER_FILES) == ["lcb_runner/benchmarks/code_generation.py", "lcb_runner/evaluation/testing_util.py"]
    for rev in (pt.RELEASE_REVISION, pt.RUNNER_REVISION):
        assert re.fullmatch(r"[0-9a-f]{40}", rev)


def test_script_is_standard_library_only_and_imports_no_pickle():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add(node.module.split(".")[0])
    stdlib = getattr(sys, "stdlib_module_names", None) or {
        "__future__", "argparse", "importlib", "json", "re", "statistics", "sys", "urllib", "pathlib"}
    assert names and names <= set(stdlib) | {"__future__"}
    assert not names & {"pickle", "zlib", "base64", "marshal", "shelve"}


def _note():
    return NOTE.read_text(encoding="utf-8")


def _matched():
    text = _note()
    head = f"\n## {MATCHED}\n"
    assert text.count(head) == 1
    return text.split(head, 1)[1].split("\n## ", 1)[0]


def _block(section):
    return section.split("```text\n", 1)[1].split("\n```", 1)[0]


def test_matched_block_starts_with_the_command():
    assert _block(_matched()).splitlines()[0] == COMMAND


def test_matched_prose_number_tokens_appear_in_the_block():
    section = _matched()
    block = _block(section)
    prose = VERSION.sub(" ", DATE.sub(" ", section.replace(block, "")))
    known = set(NUMBER.findall(block)) | {"7", "12.16", "12.14"}
    assert not sorted(set(NUMBER.findall(prose)) - known)


def test_matched_section_keeps_livecodebench_for_esc3():
    section = _matched()
    for phrase in ("- Decision for row ESC3:", "`public-test-failed`", "success only", "`test.jsonl` to `test4.jsonl`",
                   "never wrong when it fires", "a `no_test` sample both ways", "public cases before its private ones"):
        assert phrase in section, phrase
    plan = _note().split("\n## What row ESC3 runs\n", 1)[1].split("\n## ", 1)[0]
    assert "`public-test-failed`" in plan
    assert "Not settled here" not in _note()


def test_the_spec_bullet_follows_the_signals_bullet_in_design_7():
    text = DESIGN.read_text(encoding="utf-8")
    start = text.index("\n## 7. Execution with fallback (`executor.py`)\n")
    part = text[start:text.index("\n## 8. ", start)]
    head = "- v1.534 public tests matched (row ESC1c; research only, no package change):"
    assert part.count(head) == 1 and part.index("- v1.533 escalation signals measured (row ESC1b;") < part.index(head)
    spec = part[part.index(head):]
    for phrase in ("`research/escalation_public_tests.py`", "`RELEASE_FILES`", "`SAMPLE = (\"test3.jsonl\",)`",
                   "`RUNNER_FILES`", "`for t in self.public_test_cases + self.private_test_cases` twice",
                   "`def truncatefn(s, length=300):`", "imports no `pickle`", "`input_only`", "`no_test`", "`unread`",
                   "`public_share`", "`public_of_tested`", "`public-test-failed`", "`test.jsonl` to `test4.jsonl`"):
        assert phrase in spec, phrase


def test_the_changelog_line_names_the_row():
    mine = [line for line in CHANGELOG.read_text(encoding="utf-8").splitlines() if line.startswith("- v1.534 (")]
    assert len(mine) == 1 and "(7, row ESC1c)" in mine[0] and "`research/escalation_public_tests.py`" in mine[0]


def _cached():
    convert = _load("livecodebench_convert_cached_check", CONVERT)
    pt = _load("research_escalation_public_tests_cached_check", SCRIPT) if SCRIPT.exists() else None
    root = convert.default_cache_dir()
    if not pt or not all((root / name).exists() for name in convert.FILES):
        return False
    runner = [root / "runner" / name.rsplit("/", 1)[1] for name in pt.RUNNER_FILES]
    return all((root / "release" / name).exists() for name in pt.SAMPLE) and all(p.exists() for p in runner)


@pytest.mark.skipif(not _cached(), reason="the pinned LiveCodeBench submission, release and runner files are not in the default cache")
def test_note_matched_block_is_the_script_output(pt):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert pt.main([]) == 0
    assert _block(_matched()) == COMMAND + "\n" + out.getvalue().rstrip("\n")
