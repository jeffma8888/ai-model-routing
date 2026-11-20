"""DESIGN 12.16 v1.526 (row STRAT3c): the LiveCodeBench converter keeps each problem's difficulty.

With ``labels=True`` (``convert.py --labels``) ``extract`` keeps each problem's ``difficulty`` as the
last cell key and ``convert`` writes it on every row after ``cost_usd``, so ``model-routing evaluate
--slice-by difficulty`` (DESIGN 12.3 v1.514) can score each level as a slice of the one task. The
three levels map to ``1-easy``, ``2-medium`` and ``3-hard``, so the evaluator's ascending slice order
is difficulty order. Written under strict xfail with v1.526; the guards, which check what v1.62 keeps,
pass before and after it. Every test uses small synthetic problem lists except the last, which reads
the pinned files only when all 67 are already in the default cache and skips otherwise.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "livecodebench" / "convert.py"
EVIDENCE_README = ROOT / "evidence" / "livecodebench" / "README.md"
DESIGN = ROOT / "DESIGN.md"

RED = pytest.mark.xfail(strict=True, reason="DESIGN 12.16 v1.526, implemented by v1.527 (row STRAT3c)")
MAPPING = {"easy": "1-easy", "medium": "2-medium", "hard": "3-hard"}
CELL_KEYS = ["correct", "contest_date", "samples"]
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd"]
REPORT_KEYS = ["models", "task", "items", "contest_dates", "dropped_not_common", "samples", "rows"]
HAIKU, O3 = "Claude-3-Haiku", "O3 (High)"


def load_cv():
    spec = importlib.util.spec_from_file_location("lcb_convert_labels", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cv():
    return load_cv()


def problem(qid, difficulty="easy", graded=(True,), date="2024-01-02T00:00:00", **extra):
    rec = {"question_title": "t", "question_content": "problem text", "platform": "atcoder",
           "question_id": qid, "contest_id": "c", "contest_date": date, "starter_code": "",
           "difficulty": difficulty, "output_list": ["code out"] * len(graded),
           "code_list": ["code"] * len(graded), "graded_list": list(graded),
           "pass@1": sum(graded) / len(graded) if graded else 0.0, "metadata": ["{}"] * len(graded)}
    rec.update(extra)
    return rec


def files():
    """Two models; p3 is only in the first file, so it is not kept and its difficulty counts nowhere."""
    a = [problem("p2", "hard", graded=(False,)), problem("p1", "medium"), problem("p3", "hard")]
    b = [problem("p1", "medium", graded=(False, True)), problem("p2", "hard")]
    return {HAIKU: a, O3: b}


def extracts(cv, **kw):
    return [cv.extract(recs, folder, **kw) for folder, recs in files().items()]


# --- guards: what v1.62 keeps, before and after v1.526 -------------------------------------

def test_default_cells_rows_and_report_keep_the_v1_62_keys(cv):
    exs = extracts(cv)
    assert all(list(cell) == CELL_KEYS for ex in exs for cell in ex["cells"].values())
    rows, report = cv.convert(exs)
    assert [list(r) for r in rows] == [ROW_KEYS] * 4
    assert list(report) == REPORT_KEYS


def test_without_labels_a_bad_difficulty_is_never_read(cv):
    for bad in ("", "Easy", None, 3):
        ex = cv.extract([problem("p1", bad)], HAIKU)
        assert ex["cells"]["p1"] == {"correct": True, "contest_date": "2024-01-02", "samples": 1}
    del_rec = problem("p1")
    del del_rec["difficulty"]
    assert list(cv.extract([del_rec], HAIKU)["cells"]["p1"]) == CELL_KEYS


# --- extract -------------------------------------------------------------------------------

@RED
def test_difficulty_mapping_is_the_three_levels_in_order(cv):
    assert cv.DIFFICULTY == MAPPING
    assert sorted(MAPPING.values()) == list(MAPPING.values())


@RED
def test_extract_labels_adds_difficulty_as_the_last_cell_key(cv):
    ex = cv.extract(files()[HAIKU], HAIKU, labels=True)
    assert list(ex) == ["folder", "model", "cells"] and list(ex["cells"]) == ["p1", "p2", "p3"]
    assert all(list(cell) == CELL_KEYS + ["difficulty"] for cell in ex["cells"].values())
    assert {q: c["difficulty"] for q, c in ex["cells"].items()} == {"p1": "2-medium", "p2": "3-hard", "p3": "3-hard"}
    assert ex["cells"]["p2"] == {"correct": False, "contest_date": "2024-01-02", "samples": 1, "difficulty": "3-hard"}


@RED
def test_extract_labels_false_is_the_default(cv):
    for folder, recs in files().items():
        assert cv.extract(recs, folder, labels=False) == cv.extract(recs, folder)


@RED
@pytest.mark.parametrize("bad", ["", "Easy", "easy ", "very hard", None, 1, ["easy"], "missing"])
def test_extract_labels_refuses_a_bad_difficulty_naming_folder_question_and_key(cv, bad):
    rec = problem("q9", bad)
    if bad == "missing":
        del rec["difficulty"]
    with pytest.raises(ValueError) as info:
        cv.extract([problem("a1"), rec], HAIKU, labels=True)
    message = str(info.value)
    assert HAIKU in message and "q9" in message and "difficulty" in message


@RED
def test_extract_labels_checks_difficulty_after_graded_list(cv):
    with pytest.raises(ValueError, match="graded_list"):
        cv.extract([problem("q9", "very hard", graded_list=[1])], HAIKU, labels=True)


@RED
@pytest.mark.parametrize("labels", [1, 0, "yes", None])
def test_labels_must_be_a_bool(cv, labels):
    with pytest.raises(ValueError, match="labels must be a bool"):
        cv.extract(files()[HAIKU], HAIKU, labels=labels)
    with pytest.raises(ValueError, match="labels must be a bool"):
        cv.convert(extracts(cv), labels=labels)


@RED
def test_labels_is_checked_first(cv):
    with pytest.raises(ValueError, match="labels must be a bool"):
        cv.extract([], "AzeroGPT-64b", labels="yes")
    with pytest.raises(ValueError, match="labels must be a bool"):
        cv.convert([], labels="yes")


# --- convert -------------------------------------------------------------------------------

@RED
def test_convert_labels_adds_difficulty_after_cost_and_a_last_report_key(cv):
    rows, report = cv.convert(extracts(cv, labels=True), labels=True)
    assert [list(r) for r in rows] == [ROW_KEYS + ["difficulty"]] * 4
    assert [(r["item"], r["model"], r["difficulty"]) for r in rows] == [
        ("p1", "anthropic/claude-3-haiku", "2-medium"), ("p1", "openai/o3-high", "2-medium"),
        ("p2", "anthropic/claude-3-haiku", "3-hard"), ("p2", "openai/o3-high", "3-hard")]
    assert list(report) == REPORT_KEYS + ["labels"]
    assert report["labels"] == {"difficulty": {"2-medium": 1, "3-hard": 1}}


@RED
def test_convert_labels_leave_every_other_value_as_it_was(cv):
    plain_rows, plain_report = cv.convert(extracts(cv))
    rows, report = cv.convert(extracts(cv, labels=True), labels=True)
    assert [{k: r[k] for k in ROW_KEYS} for r in rows] == plain_rows
    assert {k: report[k] for k in plain_report} == plain_report
    assert cv.convert(extracts(cv), labels=False) == (plain_rows, plain_report)
    assert cv.convert(extracts(cv, labels=True)) == (plain_rows, plain_report)


@RED
def test_convert_labels_counts_levels_in_ascending_order(cv):
    a = [problem(f"p{i}", level) for i, level in enumerate(["hard", "easy", "medium", "easy"])]
    exs = [cv.extract(a, HAIKU, labels=True), cv.extract(a, O3, labels=True)]
    _, report = cv.convert(exs, labels=True)
    assert report["labels"] == {"difficulty": {"1-easy": 2, "2-medium": 1, "3-hard": 1}}
    assert list(report["labels"]["difficulty"]) == ["1-easy", "2-medium", "3-hard"]


@RED
def test_convert_labels_refuses_an_extract_made_without_labels(cv):
    recs = files()
    exs = [cv.extract(recs[HAIKU], HAIKU, labels=True), cv.extract(recs[O3], O3)]
    with pytest.raises(ValueError) as info:
        cv.convert(exs, labels=True)
    assert "openai/o3-high" in str(info.value) and "p1" in str(info.value) and "difficulty" in str(info.value)


@RED
def test_convert_labels_refuses_two_difficulties_for_one_question(cv):
    exs = [cv.extract([problem("p1", "easy")], HAIKU, labels=True), cv.extract([problem("p1", "hard")], O3, labels=True)]
    with pytest.raises(ValueError, match="p1"):
        cv.convert(exs, labels=True)
    assert cv.convert([cv.extract([problem("p1", "easy")], HAIKU), cv.extract([problem("p1", "hard")], O3)])[1]["items"] == 1


@RED
def test_the_evaluator_slices_labelled_rows_by_difficulty(cv):
    a, b = [], []
    for i in range(80):
        hard = i % 2 == 0
        a.append(problem(f"p{i:02d}", "hard" if hard else "easy", graded=(True,)))
        b.append(problem(f"p{i:02d}", "hard" if hard else "easy", graded=(not hard,)))
    rows, report = cv.convert([cv.extract(a, HAIKU, labels=True), cv.extract(b, O3, labels=True)], labels=True)
    assert report["labels"]["difficulty"] == {"1-easy": 40, "3-hard": 40}
    result = evaluate(outcomes_from_rows(rows, slice_by="difficulty"), [0.5], seeds=[0], flavors=("cost_blind",))
    assert result["tasks"]["code_generation"]["slices"] == {"1-easy": 40, "3-hard": 40}
    assert {r["slice"] for r in result["per_slice"]} == {"1-easy", "3-hard"}


# --- CLI and docs --------------------------------------------------------------------------

def write_cache(cv, monkeypatch, root):
    names = {}
    for folder, recs in files().items():
        name = f"{folder}/Scenario.codegeneration_1_0.2_eval_all.json"
        (root / folder).mkdir(parents=True, exist_ok=True)
        (root / name).write_text(json.dumps(recs), encoding="utf-8")
        names[name] = (0, "")
    monkeypatch.setattr(cv, "FILES", names)
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: root)


@RED
def test_cli_labels_writes_the_difficulty_key(cv, monkeypatch, tmp_path, capsys):
    write_cache(cv, monkeypatch, tmp_path / "c")
    out = tmp_path / "o.jsonl"
    assert cv.main(["--out", str(out), "--labels"]) == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [list(r) for r in rows] == [ROW_KEYS + ["difficulty"]] * 4
    assert json.loads(capsys.readouterr().out)["labels"] == {"difficulty": {"2-medium": 1, "3-hard": 1}}
    assert cv.main(["--out", str(out)]) == 0
    assert [list(json.loads(line)) for line in out.read_text(encoding="utf-8").splitlines()] == [ROW_KEYS] * 4
    assert "labels" not in json.loads(capsys.readouterr().out)


README_LINES = [
    "python evidence/livecodebench/convert.py --out livecodebench-labels.jsonl --labels",
    "model-routing evaluate --outcomes livecodebench-labels.jsonl --bar 0.6 --flavor cost_blind --slice-by difficulty",
]
README_COUNTS = "238 `1-easy`, 279 `2-medium` and 196 `3-hard` of the 713"


@RED
def test_the_synopses_and_the_readme_name_labels():
    usage = SCRIPT.read_text(encoding="utf-8").split('"""')[1]
    assert "Usage: python evidence/livecodebench/convert.py --out PATH [--cache DIR] [--labels]" in usage
    assert "`python evidence/livecodebench/convert.py --out PATH [--cache DIR] [--labels]`" in DESIGN.read_text(encoding="utf-8")
    readme = EVIDENCE_README.read_text(encoding="utf-8")
    heading = "## Problem difficulty (for the slice evidence)"
    assert readme.count(heading) == 1 and readme.index(heading) < readme.index("## Reading it")
    section = readme[readme.index(heading):readme.index("## Reading it")]
    for needle in README_LINES + [README_COUNTS, "DESIGN 12.3", "`min_samples = 30`"]:
        assert needle in section, needle
    for raw, name in MAPPING.items():
        assert f"`{raw}` to `{name}`" in section
    assert readme.isascii() and "\u2013" not in readme and "\u2014" not in readme


# --- the pinned files, when cached ---------------------------------------------------------

@RED
def test_pinned_files_give_the_stated_difficulty_counts(cv):
    cache = cv.default_cache_dir()
    if not all((cache / name).is_file() for name in cv.FILES):
        pytest.skip("the 67 pinned LiveCodeBench files are not in the default cache")
    root = cv.fetch()
    exs, objects = [], 0
    for name in cv.FILES:
        records = cv.read_file(root / name)
        objects += len(records)
        exs.append(cv.extract(records, name.split("/")[0], labels=True))
    rows, report = cv.convert(exs, labels=True)
    assert len(exs) == 67 and objects == 62_552
    assert report["items"] == 713 and len(rows) == 47_771
    assert report["labels"] == {"difficulty": {"1-easy": 238, "2-medium": 279, "3-hard": 196}}
    levels = report["labels"]["difficulty"]
    built = (f"{levels['1-easy']} `1-easy`, {levels['2-medium']} `2-medium` and {levels['3-hard']} `3-hard` "
             f"of the {report['items']}")
    assert built == README_COUNTS
    plain_rows, _ = cv.convert([{**ex, "cells": {q: {k: c[k] for k in CELL_KEYS} for q, c in ex["cells"].items()}} for ex in exs])
    assert [{k: r[k] for k in ROW_KEYS} for r in rows] == plain_rows
