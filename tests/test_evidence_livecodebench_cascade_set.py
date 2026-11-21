"""DESIGN 7 v1.550 (row ESC3l): the LiveCodeBench replay's items and cascade set.

evidence/livecodebench/cascades.py names RELEASE, the four release_v4 files; gives each failed first
sample's kind with file_kinds; and builds the cascade set with setting_cascades, one model's lower
reasoning setting before a higher one. These tests were committed before the code under a module-level
strict xfail whose error, AttributeError, is the one a missing attribute of the loaded script raises,
and the implementing commit removed the mark. They use stub records and folder names; one, skipped
unless test3.jsonl and a kept file are cached, counts test3.jsonl's problems by difficulty."""

import ast
import collections
import importlib.util
import json
import random
from pathlib import Path

import pytest

from model_routing import Cascade

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "livecodebench" / "cascades.py"
P, PN = "public-test-failed", "public-test-failed-or-no-test"
UNREAD = ("agentica/deepcoder-14b-preview", "qwen/qwen3-235b-a22b", "qwen/qwq-max-preview")
PAIRS = [
    ("anthropic/claude-opus-4", "anthropic/claude-opus-4-thinking"),
    ("anthropic/claude-sonnet-4", "anthropic/claude-sonnet-4-thinking"),
    ("openai/o1-2024-12-17-low", "openai/o1-2024-12-17-med"),
    ("openai/o1-2024-12-17-low", "openai/o1-2024-12-17-high"),
    ("openai/o1-2024-12-17-med", "openai/o1-2024-12-17-high"),
    ("openai/o3-mini-2025-01-31-low", "openai/o3-mini-2025-01-31-med"),
    ("openai/o3-mini-2025-01-31-low", "openai/o3-mini-2025-01-31-high"),
    ("openai/o3-mini-2025-01-31-med", "openai/o3-mini-2025-01-31-high"),
    ("openai/o4-mini-low", "openai/o4-mini-medium"),
    ("openai/o4-mini-low", "openai/o4-mini-high"),
    ("openai/o4-mini-medium", "openai/o4-mini-high"),
]

_loaded = []


def m():
    if not _loaded:
        spec = importlib.util.spec_from_file_location("livecodebench_cascades_set", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _loaded.append(module)
    return _loaded[0]


def _folders():
    return [name.split("/")[0] for name in m().convert.FILES]


def _ids(cascades):
    return [c.id for c in cascades]


def _expected():
    return sorted(Cascade(cheap, strong, signal).id for cheap, strong in PAIRS for signal in (P, PN))


# --- items -------------------------------------------------------------------------------------------

def test_release_is_the_four_release_v4_files_each_pinned():
    assert m().RELEASE == ("test.jsonl", "test2.jsonl", "test3.jsonl", "test4.jsonl")
    assert all(name in m().public_tests.RELEASE_FILES for name in m().RELEASE)
    gb = sum(m().public_tests.RELEASE_FILES[name][0] for name in m().RELEASE) / 1e9
    assert round(gb, 1) == 3.8


def test_the_three_files_are_loaded_by_path_and_nothing_of_theirs_is_copied():
    mod = m()
    assert Path(mod.convert.__file__).resolve() == ROOT / "evidence" / "livecodebench" / "convert.py"
    assert Path(mod.public_tests.__file__).resolve() == ROOT / "research" / "escalation_public_tests.py"
    assert Path(mod.cost_research.__file__).resolve() == ROOT / "research" / "livecodebench_cost.py"
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    defined = {n.name for n in ast.walk(tree) if isinstance(n, (ast.FunctionDef, ast.ClassDef))}
    assigned = {t.id for n in ast.walk(tree) if isinstance(n, ast.Assign) for t in n.targets
                if isinstance(t, ast.Name)}
    for name in ("classify", "first_metadata", "reduce_file", "read_release", "model_id", "extract"):
        assert name not in defined
    assert "SETTING" not in assigned and "RELEASE_FILES" not in assigned
    assert {"urlopen", "open", "write_text", "read_text"}.isdisjoint(
        {n.attr if isinstance(n, ast.Attribute) else n.id for n in ast.walk(tree)
         if isinstance(n, (ast.Attribute, ast.Name))})


# --- file_kinds ----------------------------------------------------------------------------------------

def _record(qid, passed, meta=None, no_meta=False):
    rec = {"question_id": qid, "contest_date": "2024-06-01T00:00:00", "graded_list": [passed, not passed]}
    if not no_meta:
        rec["metadata"] = [json.dumps(meta if meta is not None else {})]
    return rec


def _release():
    return {qid: {"date": "2024-06-01", "call_based": False, "cases": [("1\n", "2\n"), ("3\n", "4\n")]}
            for qid in ("q1", "q2", "q3", "q4", "q6", "q7")}


def _records():
    return [
        _record("q1", True, {"execution time": 0.1}),
        _record("q2", False, {"inputs": "3\n", "expected": "4\n", "output": "5\n"}),
        _record("q3", False, {"inputs": "9\n", "expected": "8\n", "output": "7\n"}),
        _record("q4", False, {"error_code": -4, "error_message": "Runtime Error"}),
        _record("q5", False, {"inputs": "1\n", "expected": "2\n"}),  # not in the release
        _record("q6", False, {"inputs": "1\n", "expected": "9\n"}),
        _record("q7", False, no_meta=True),
    ]


def test_file_kinds_gives_each_failed_first_sample_of_the_release_its_kind():
    got = m().file_kinds(_records(), "GPT-4-0613", _release())
    model = "openai/gpt-4-0613"
    assert got == {(model, "q2"): "public", (model, "q3"): "other", (model, "q4"): "no_test",
                   (model, "q6"): "input_only", (model, "q7"): "unread"}
    assert list(got) == sorted(got)


def test_file_kinds_counts_what_reduce_file_counts():
    mod = m()
    got = mod.file_kinds(_records(), "GPT-4-0613", _release())
    counts = mod.public_tests.reduce_file(_records(), "GPT-4-0613", _release(), mod.convert)["counts"]
    assert len(got) == counts["failed"]
    tally = collections.Counter(got.values())
    assert all(tally[kind] == counts[kind] for kind in mod.KINDS)


def test_file_kinds_keys_are_sorted_whatever_the_record_order():
    records = _records()
    random.Random(3).shuffle(records)
    assert list(m().file_kinds(records, "GPT-4-0613", _release())) == sorted(
        m().file_kinds(_records(), "GPT-4-0613", _release()))


def test_file_kinds_gives_a_passed_sample_no_entry_and_an_empty_release_none():
    assert m().file_kinds([_record("q1", True, {"inputs": "1\n", "expected": "2\n"})], "GPT-4-0613",
                          _release()) == {}
    assert m().file_kinds(_records(), "GPT-4-0613", {}) == {}


@pytest.mark.parametrize("records, folder, needle", [
    ([_record("q2", False)], "AzeroGPT-64b", "no vendor rule"),
    ([{"question_id": "q2", "contest_date": "2024-06-01", "graded_list": [False],
       "metadata": ["{not json"]}], "GPT-4-0613", "metadata entry 0 is not valid JSON"),
    ([_record("q2", False, {"inputs": 3, "expected": "4\n"})], "GPT-4-0613", "not both strings"),
    ([{"question_id": "q2", "contest_date": "2024-06-01", "graded_list": []}], "GPT-4-0613", "graded_list"),
])
def test_file_kinds_lets_the_errors_of_the_loaded_functions_through(records, folder, needle):
    with pytest.raises(ValueError, match=needle):
        m().file_kinds(records, folder, _release())


# --- setting_cascades ------------------------------------------------------------------------------------

def test_the_kept_folders_give_eleven_pairs_and_twenty_two_cascades():
    got = m().setting_cascades(_folders())
    assert all(isinstance(c, Cascade) for c in got)
    assert _ids(got) == _expected() and len(got) == 22
    assert len({(c.cheap, c.strong) for c in got}) == 11
    assert {c.signal for c in got} == set(m().SIGNALS)


def test_no_cheap_model_is_a_file_with_no_readable_metadata_and_every_model_is_kept():
    got = m().setting_cascades(_folders())
    models = {m().convert.model_id(f) for f in _folders()}
    assert all(c.cheap not in UNREAD for c in got)
    assert all(c.cheap in models and c.strong in models for c in got)
    assert all(c.id not in models for c in got)


def test_the_set_does_not_depend_on_the_folder_order():
    folders = _folders()
    random.Random(7).shuffle(folders)
    assert _ids(m().setting_cascades(folders)) == _expected()
    assert _ids(m().setting_cascades(iter(_folders()))) == _expected()


def test_the_ranks_order_each_scale():
    assert m().RANKS == {"none": 0, "Low": 1, "Med": 2, "Medium": 2, "High": 3, "Thinking": 1}
    got = m().setting_cascades(["O4-Mini (High)", "O4-Mini", "O4-Mini (Low)"])
    assert sorted({(c.cheap, c.strong) for c in got}) == [
        ("openai/o4-mini", "openai/o4-mini-high"), ("openai/o4-mini", "openai/o4-mini-low"),
        ("openai/o4-mini-low", "openai/o4-mini-high")]
    got = m().setting_cascades(["Claude-Opus-4 (Thinking)", "Claude-Opus-4"])
    assert {(c.cheap, c.strong) for c in got} == {("anthropic/claude-opus-4", "anthropic/claude-opus-4-thinking")}


def test_a_lone_run_or_a_folder_with_no_setting_gives_no_cascade():
    assert m().setting_cascades(["O3 (High)", "Grok-3-Mini (High)", "GPT-4-0613", "Kimi-k1.6-IOI",
                                 "Kimi-k1.6-IOI-high"]) == []
    assert m().setting_cascades([]) == []


@pytest.mark.parametrize("folders, needle", [
    (["O4-Mini (Low)", "O4-Mini (High)", "O4-Mini (Low)"], "repeated"),
    (["GPT-9 (Thinking)", "GPT-9 (High)"], "mix"),
    (["GPT-9", "GPT-9 (Thinking)", "GPT-9 (Low)"], "mix"),
    (["GPT-9 (Med)", "GPT-9 (Medium)"], "one rank"),
])
def test_a_bad_group_is_refused_naming_it(folders, needle):
    with pytest.raises(ValueError, match=needle) as err:
        m().setting_cascades(folders)
    assert ("GPT-9" in str(err.value)) or ("O4-Mini (Low)" in str(err.value))


def test_a_folder_no_vendor_rule_takes_is_refused_only_in_a_group():
    assert m().setting_cascades(["AzeroGPT-64b"]) == []
    with pytest.raises(ValueError, match="no vendor rule"):
        m().setting_cascades(["AzeroGPT-64b (Low)", "AzeroGPT-64b (High)"])


def test_the_set_replays_through_cascade_rows():
    mod = m()
    folders = ["O4-Mini (Low)", "O4-Mini (High)"]
    cascades = mod.setting_cascades(folders)
    rows = [{"task": "code_generation", "item": "q1", "model": "openai/o4-mini-low", "correct": False,
             "cost_usd": 0.0, "difficulty": "3-hard"},
            {"task": "code_generation", "item": "q1", "model": "openai/o4-mini-high", "correct": True,
             "cost_usd": 0.0, "difficulty": "3-hard"}]
    out = mod.cascade_rows(rows, {("openai/o4-mini-low", "q1"): "public"}, cascades)
    added = [r for r in out if r["model"] in _ids(cascades)]
    assert [(r["model"], r["correct"], r["escalated"]) for r in added] == [
        (f"openai/o4-mini-low>openai/o4-mini-high@{P}", True, True),
        (f"openai/o4-mini-low>openai/o4-mini-high@{PN}", True, True)]


# --- the spec ----------------------------------------------------------------------------------------------

def test_design_and_changelog_state_the_two_choices():
    assert m().RELEASE
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    mine = [line for line in text.splitlines() if line.startswith("- v1.550 the LiveCodeBench replay's items")]
    assert len(mine) == 1
    for phrase in ("`RELEASE = (\"test.jsonl\", \"test2.jsonl\", \"test3.jsonl\", \"test4.jsonl\")`",
                   "34 `1-easy`, 39 `2-medium` and 28 `3-hard`", "`file_kinds(records, folder, release) -> dict`",
                   "`setting_cascades(folders) -> list[Cascade]`", "11 pairs and 22 cascades",
                   "4,224 pairs and 8,448 cascades", "a rule that reads no label"):
        assert phrase in text, phrase
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert [line for line in log if line.startswith("- v1.550 (")][0].count("(7, row ESC3l)") == 1


def test_test3_alone_leaves_every_level_under_thirty_calibration_problems():
    mod = m()
    root = mod.convert.default_cache_dir()
    name = "O1-Mini-2024-09-12/Scenario.codegeneration_1_0.2_eval_all.json"
    release = root / "release" / "test3.jsonl"
    if not (release.exists() and (root / name).exists()):
        pytest.skip("test3.jsonl or a kept file is not cached")
    size, sha256 = mod.public_tests.RELEASE_FILES["test3.jsonl"]
    mod.convert.verify(release, size, sha256)
    mod.convert.verify(root / name, *mod.convert.FILES[name])
    with open(release, "rb") as f:
        qids = {json.loads(line)["question_id"] for line in f}
    cells = mod.convert.extract(mod.convert.read_file(root / name), name.split("/")[0], labels=True)["cells"]
    counts = collections.Counter(cells[q]["difficulty"] for q in qids)
    assert len(qids) == 101 and dict(counts) == {"1-easy": 34, "2-medium": 39, "3-hard": 28}
    assert all(n * 0.5 < 30 for n in counts.values())
