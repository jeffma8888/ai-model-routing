"""DESIGN 12.9 v1.518 (row STRAT3a): the AutoBench converter keeps each question's labels.

With ``labels=True`` (``convert.py --labels``) every row also carries its question's
``difficulty``, ``skill`` and ``domain``, so ``model-routing evaluate --slice-by difficulty``
(DESIGN 12.3 v1.514) can score each difficulty as a slice of the pooled task. The five written
difficulty levels map to ``1-very-simple`` to ``5-very-difficult``, so the evaluator's ascending
slice order is difficulty order. Written under strict xfail with v1.518; v1.519 implements it,
so every test runs unmarked, and the two that guarded what v1.518 keeps passed before and after
it. Every test uses tiny in-memory tables except the last, which
reads the pinned files only when they are already in the default cache and skips otherwise.
"""

import csv
import importlib.util
import json
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "autobench-2026" / "convert.py"
EVIDENCE_README = ROOT / "evidence" / "autobench-2026" / "README.md"
DESIGN = ROOT / "DESIGN.md"

POOL = {"members": [
    {"display_id": "Alpha-1", "openrouter_id": "x-ai/alpha-1", "family": "A"},
    {"display_id": "Beta-2", "openrouter_id": "acme/beta-2", "family": "B"},
]}
MAPPING = {"a very simple": "1-very-simple", "a simple": "2-simple", "a": "3-unmarked",
           "a difficult": "4-difficult", "a very difficult": "5-very-difficult"}
BASE_KEYS = ["task", "item", "model", "correct", "cost_usd"]
LABEL_KEYS = ["difficulty", "skill", "domain"]


def load_cv():
    spec = importlib.util.spec_from_file_location("autobench_convert_labels", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def cv():
    return load_cv()


def question(pid, difficulty="a", skill="coding", domain="9 History"):
    return {"prompt_id": pid, "question": "text", "ddc_domain": domain, "difficulty": difficulty,
            "intended_skill": skill}


def cell(pid, model, score, cost="0.001"):
    return {"prompt_id": pid, "model": model, "score": score, "cost": cost, "input_tokens": "10.0",
            "output_tokens": "20.0", "source": "original"}


def small():
    """Three questions; q/3 has an unscored cell, so it is dropped and its labels count nowhere."""
    questions = [question("q/1", "a very difficult", "math_reasoning", "5 Science"),
                 question("q/2", "a simple", "coding", "9 History"),
                 question("q/3", "a very difficult", "coding", "9 History")]
    matrix = [cell("q/1", "Alpha-1", "5"), cell("q/1", "Beta-2", "4"),
              cell("q/2", "Alpha-1", "3"), cell("q/2", "Beta-2", "4.5"),
              cell("q/3", "Alpha-1", "4"), cell("q/3", "Beta-2", "")]
    return matrix, questions


def test_rows_without_labels_have_the_v1_21_keys(cv):
    matrix, questions = small()
    rows, report = cv.convert(matrix, questions, POOL, 0.5, 1, "all")
    assert [list(r) for r in rows] == [BASE_KEYS] * 4
    assert "labels" not in report
    rows, report = cv.convert(matrix, questions, POOL, 0.5, 1, "all", True)
    assert [list(r) for r in rows] == [BASE_KEYS + ["input_tokens", "output_tokens"]] * 4
    assert "labels" not in report


def test_difficulty_mapping_is_the_five_written_levels(cv):
    assert cv.DIFFICULTY == MAPPING
    assert sorted(MAPPING.values()) == list(MAPPING.values())


def test_labels_add_three_keys_after_cost(cv):
    matrix, questions = small()
    rows, _ = cv.convert(matrix, questions, POOL, 0.5, 1, "all", labels=True)
    assert [list(r) for r in rows] == [BASE_KEYS + LABEL_KEYS] * 4
    by_item = {r["item"]: (r["difficulty"], r["skill"], r["domain"]) for r in rows}
    assert by_item == {"q/1": ("5-very-difficult", "math_reasoning", "5 Science"),
                       "q/2": ("2-simple", "coding", "9 History")}


def test_labels_follow_the_token_counts(cv):
    matrix, questions = small()
    rows, _ = cv.convert(matrix, questions, POOL, 0.5, 1, "all", tokens=True, labels=True)
    assert [list(r) for r in rows] == [BASE_KEYS + ["input_tokens", "output_tokens"] + LABEL_KEYS] * 4
    assert rows[0]["input_tokens"] == 10 and rows[0]["output_tokens"] == 20


def test_labels_leave_every_other_value_as_it_was(cv):
    matrix, questions = small()
    for task_by in ("all", "domain"):
        plain, plain_report = cv.convert(matrix, questions, POOL, 0.5, 1, task_by)
        labelled, report = cv.convert(matrix, questions, POOL, 0.5, 1, task_by, labels=True)
        assert [{k: r[k] for k in BASE_KEYS} for r in labelled] == plain
        assert list(report) == list(plain_report) + ["labels"]
        assert {k: report[k] for k in plain_report} == plain_report
        assert cv.convert(matrix, questions, POOL, 0.5, 1, task_by, labels=False) == (plain, plain_report)


def test_report_counts_kept_questions_per_label(cv):
    matrix, questions = small()
    _, report = cv.convert(matrix, questions, POOL, 0.5, 1, "all", labels=True)
    assert report["labels"] == {"difficulty": {"2-simple": 1, "5-very-difficult": 1},
                                "skill": {"coding": 1, "math_reasoning": 1},
                                "domain": {"5 Science": 1, "9 History": 1}}
    assert list(report["labels"]) == LABEL_KEYS


@pytest.mark.parametrize("change, column", [
    ({"difficulty": "a medium"}, "difficulty"),
    ({"difficulty": ""}, "difficulty"),
    ({"intended_skill": ""}, "intended_skill"),
    ({"intended_skill": "co@ding"}, "intended_skill"),
    ({"ddc_domain": "9 Hist@ory"}, "ddc_domain"),
    ({"ddc_domain": ""}, "ddc_domain"),
])
def test_a_bad_label_names_the_question_and_the_column(cv, change, column):
    matrix, questions = small()
    questions[1] = {**questions[1], **change}
    matrix.append(cell("q/none", "Alpha-1", "4"))  # names no question: the label check comes first
    with pytest.raises(ValueError) as info:
        cv.convert(matrix, questions, POOL, 0.5, 1, "all", labels=True)
    assert "'q/2'" in str(info.value) and column in str(info.value)


def test_without_labels_a_bad_label_is_never_read(cv):
    matrix, questions = small()
    questions[1] = {**questions[1], "difficulty": "a medium", "intended_skill": ""}
    rows, _ = cv.convert(matrix, questions, POOL, 0.5, 1, "all")
    assert len(rows) == 4


@pytest.mark.parametrize("labels", [1, "yes", None])
def test_labels_must_be_a_bool(cv, labels):
    matrix, questions = small()
    with pytest.raises(ValueError, match="labels must be a bool"):
        cv.convert(matrix, questions, POOL, 0.5, 1, "all", labels=labels)


def test_the_evaluator_slices_labelled_rows_by_difficulty(cv):
    questions, matrix = [], []
    for i in range(40):
        pid = f"q/{i:02d}"
        hard = i % 2 == 0
        questions.append(question(pid, "a very difficult" if hard else "a very simple"))
        matrix += [cell(pid, "Alpha-1", "5", "0.004"), cell(pid, "Beta-2", "1" if hard else "5", "0.001")]
    rows, report = cv.convert(matrix, questions, POOL, 0.5, 1, "all", labels=True)
    assert report["labels"]["difficulty"] == {"1-very-simple": 20, "5-very-difficult": 20}
    result = evaluate(outcomes_from_rows(rows, slice_by="difficulty"), [0.5], seeds=[0])
    assert result["tasks"]["all"]["slices"] == {"1-very-simple": 20, "5-very-difficult": 20}
    assert {r["slice"] for r in result["per_slice"]} == {"1-very-simple", "5-very-difficult"}


def write_folder(folder, matrix, questions):
    folder.mkdir(parents=True, exist_ok=True)
    for name, table in (("matrix.csv", matrix), ("questions.csv", questions)):
        with (folder / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(table[0]))
            w.writeheader()
            w.writerows(table)
    (folder / "pool.json").write_text(json.dumps(POOL), encoding="utf-8")
    (folder / "frozen_params.json").write_text(json.dumps({"delta_signal": 0.5, "top_k": 1}), encoding="utf-8")


def test_cli_labels_writes_the_label_keys(cv, monkeypatch, tmp_path, capsys):
    matrix, questions = small()
    write_folder(tmp_path / "c", matrix, questions)
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: tmp_path / "c")
    out = tmp_path / "o.jsonl"
    assert cv.main(["--out", str(out), "--task-by", "all", "--labels"]) == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [list(r) for r in rows] == [BASE_KEYS + LABEL_KEYS] * 4
    assert json.loads(capsys.readouterr().out)["labels"]["difficulty"] == {"2-simple": 1, "5-very-difficult": 1}
    assert cv.main(["--out", str(out), "--task-by", "all"]) == 0
    assert [list(json.loads(line)) for line in out.read_text(encoding="utf-8").splitlines()] == [BASE_KEYS] * 4


def test_the_synopses_and_the_readme_name_labels():
    usage = SCRIPT.read_text(encoding="utf-8").split('"""')[1]
    assert "[--labels]" in usage
    design = DESIGN.read_text(encoding="utf-8")
    assert "[--task-by {domain,all}] [--tokens] [--labels] [--registry PATH]`" in design
    readme = EVIDENCE_README.read_text(encoding="utf-8")
    assert "python evidence/autobench-2026/convert.py --out autobench-labels.jsonl --task-by all --labels" in readme
    for name in MAPPING.values():
        assert f"`{name}`" in readme


PINNED = ("matrix.csv", "questions.csv", "pool.json", "frozen_params.json", "SHA256SUMS")


def test_pinned_files_give_the_stated_label_counts(cv):
    folder = cv.default_cache_dir()
    if not all((folder / name).is_file() for name in PINNED):
        pytest.skip("the pinned AutoBench files are not in the default cache")
    folder = cv.fetch()
    params = json.loads((folder / "frozen_params.json").read_text(encoding="utf-8"))
    pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
    rows, report = cv.convert(cv.read_csv(folder / "matrix.csv"), cv.read_csv(folder / "questions.csv"), pool,
                              params["delta_signal"], params["top_k"], "all", labels=True)
    assert len(rows) == 4060
    assert report["labels"]["difficulty"] == {"1-very-simple": 48, "2-simple": 50, "3-unmarked": 42,
                                              "4-difficult": 33, "5-very-difficult": 30}
    assert report["labels"]["skill"] == {"coding": 15, "creative_synthesis": 23, "math_reasoning": 43,
                                         "planning_agentic": 31, "world_knowledge": 91}
    assert sum(report["labels"]["domain"].values()) == 203 and len(report["labels"]["domain"]) == 10
