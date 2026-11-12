"""LLM Routing Response Bank converter contract (DESIGN 12.20, v1.288), written before the converter and kept as its tests.

The converter is a standard-library script outside the package (``evidence/response-bank/convert.py``),
so it is loaded from its path by an autouse fixture. Every test uses small synthetic records or files in a
temporary folder, except one CLI run on the four pinned files, which runs only when all four are in the
default cache and skips otherwise (CI never downloads them).
"""

import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import random
import urllib.request
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

pytestmark = pytest.mark.xfail(strict=True, raises=ModuleNotFoundError)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "response-bank" / "convert.py"
REVISION = "547beb31ecd8f12b116b87eb4f56feee73edda6c"
FILES = {
    "responses_cal.jsonl": (62806440, "31262ff3c39cf66c17332bdc3f104bdf25c4abedd8dc75767297fa67c2a08de5"),
    "responses_eval.jsonl": (942083749, "c0b9df2c194730cd24757001878a1e24648b4990747d60157261b60818e42305"),
    "scores_cal.jsonl": (349266, "58826526608edd7ffaa16540fb0393ef631ee428cb708da92dae32d690a995cd"),
    "scores_eval.jsonl": (12952125, "09b7376e7964a85aee77644af64188b8b14156fab6201e6f3e80852ea6e42b4b"),
}
MODEL_IDS = {
    "deepseek-v4-flash": "deepseek/deepseek-v4-flash",
    "deepseek-v4-pro": "deepseek/deepseek-v4-pro",
    "glm-5-3-flash": "z-ai/glm-5.3-flash",
    "glm-5.3": "z-ai/glm-5.3",
    "kimi-k2.7-code": "moonshotai/kimi-k2.7-code",
}
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd", "input_tokens", "output_tokens"]
TASK_KEYS = ["items", "dropped_incomplete", "dropped_unbilled", "dropped_prompt_differs", "missing_cells",
             "length_finishes", "length_successes", "other_finishes"]
SHA_A = "a" * 64
SHA_B = "b" * 64


def load_cv():
    if not SCRIPT.is_file():
        raise ModuleNotFoundError(f"no converter at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("response_bank_convert", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def cv():
    return load_cv()


def score(task_id, model="deepseek-v4-pro", quality=1.0, missing=None, dataset=None):
    evaluator = {"entrypoint": "helm exact-answer parser"}
    if missing is not None:
        evaluator["missing"] = missing
    return {"task_id": task_id, "dataset": dataset or task_id.split(":")[0], "model_id": model,
            "quality": quality, "evaluator": evaluator, "kind": "helm_model_quality_score"}


def response(task_id, model="deepseek-v4-pro", usd=0.001, inp=10, out=20, finish="stop", sample=0,
             prompt=SHA_A, dataset=None):
    return {"task_id": task_id, "dataset": dataset or task_id.split(":")[0], "model_id": model,
            "sample_index": sample, "prompt_sha256": prompt, "response_sha256": SHA_B,
            "text": "the visible answer", "reasoning_content": "the hidden reasoning", "finish_reason": finish,
            "usage": {"input": inp, "output": out, "cache_read": 0, "reasoning_tokens": 5,
                      "total_tokens": inp + out},
            "official_usd": usd, "requested_max_tokens": 32768, "reasoning_effort": "high"}


def raw_of(model):
    return {v: k for k, v in MODEL_IDS.items()}[model]


def matrix(cv, tasks, models=("deepseek-v4-pro", "kimi-k2.7-code")):
    """Scores and responses records for every (task_id, model): model k is right on task n when n + k is even."""
    scores, responses = [], []
    for n, task_id in enumerate(tasks):
        for k, m in enumerate(models):
            scores.append(cv.score_record(score(task_id, m, quality=float((n + k) % 2 == 0))))
            responses.append(cv.response_record(response(task_id, m, usd=0.001 * (k + 1), inp=10 + n, out=20 + k)))
    return scores, responses


# --- constants -------------------------------------------------------------------------------------------

def test_pinned_constants(cv):
    assert cv.DATASET == "Lurume/llm-routing-response-bank"
    assert cv.REVISION == REVISION
    assert cv.LICENCE == "ODC-BY-4.0"
    assert cv.FILES == FILES
    assert list(cv.FILES) == sorted(FILES)
    assert cv.TIMEOUT == 60


@pytest.mark.parametrize("name", sorted(FILES))
def test_url_of_each_pinned_file(cv, name):
    assert cv.url(name) == f"https://huggingface.co/datasets/Lurume/llm-routing-response-bank/resolve/{REVISION}/{name}"


@pytest.mark.parametrize("name", ["tasks_eval.jsonl", "LICENSE", "", None, "../scores_cal.jsonl"])
def test_url_refuses_a_file_not_pinned(cv, name):
    with pytest.raises(ValueError):
        cv.url(name)


def test_models_are_the_five_raw_ids_ascending(cv):
    assert list(cv.MODELS) == sorted(MODEL_IDS)


def test_default_cache_dir(cv):
    assert cv.default_cache_dir() == Path.home() / ".cache" / "ai-model-routing-evidence" / "response-bank"


def test_script_is_standard_library_only():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    assert names <= {"argparse", "hashlib", "json", "math", "os", "re", "sys", "urllib", "pathlib"}


# --- model_id --------------------------------------------------------------------------------------------

@pytest.mark.parametrize("raw", sorted(MODEL_IDS))
def test_model_id_of_each_pinned_model(cv, raw):
    assert cv.model_id(raw) == MODEL_IDS[raw]


@pytest.mark.parametrize("raw, expected", [
    ("glm-4-6", "z-ai/glm-4.6"),
    ("glm-5-3", "z-ai/glm-5.3"),
    ("glm-10-2-air", "z-ai/glm-10.2-air"),
    ("glm-5-flash", "z-ai/glm-5-flash"),
    ("glm-5-3b", "z-ai/glm-5-3b"),
    ("deepseek-v4-3-pro", "deepseek/deepseek-v4-3-pro"),
    ("kimi-k3", "moonshotai/kimi-k3"),
])
def test_model_id_reads_a_dashed_glm_version_only(cv, raw, expected):
    assert cv.model_id(raw) == expected


@pytest.mark.parametrize("raw", ["", "gpt-6-sol", "GLM-5.3", "glm/5.3", "deepseek", "kimi", "-glm-5.3",
                                 "glm-5.3 ", "glm-5\u00b73", None, 3, ["glm-5.3"]])
def test_model_id_refuses_anything_else(cv, raw):
    with pytest.raises(ValueError):
        cv.model_id(raw)


# --- score_record ----------------------------------------------------------------------------------------

def test_score_record_keeps_the_key_and_label(cv):
    out = cv.score_record(score("aime:aime25_i:I-1", "glm-5-3-flash", quality=1.0))
    assert out == {"task_id": "aime:aime25_i:I-1", "family": "aime", "model": "z-ai/glm-5.3-flash",
                   "correct": True, "missing": None}
    assert list(out) == ["task_id", "family", "model", "correct", "missing"]


@pytest.mark.parametrize("quality, correct", [(1.0, True), (0.0, False), (1, True), (0, False)])
def test_score_record_quality_is_zero_or_one(cv, quality, correct):
    assert cv.score_record(score("mmlu_pro:1", quality=quality))["correct"] is correct


def test_score_record_keeps_a_missing_reason(cv):
    out = cv.score_record(score("mmlu_pro:7872", "glm-5.3", quality=0.0, missing="provider refusal"))
    assert out["missing"] == "provider refusal"
    assert out["correct"] is False


@pytest.mark.parametrize("change", [
    lambda r: r.update(quality=0.5),
    lambda r: r.update(quality=True),
    lambda r: r.update(quality="1"),
    lambda r: r.update(quality=None),
    lambda r: r.pop("quality"),
    lambda r: r.update(evaluator="parser"),
    lambda r: r.update(evaluator={"missing": ""}),
    lambda r: r.update(evaluator={"missing": 3}),
    lambda r: r.update(evaluator={"missing": None}),
    lambda r: r.update(evaluator={"missing": "filter"}),
    lambda r: r.update(dataset="gpqa_diamond"),
    lambda r: r.update(task_id="mmlu_pro:"),
    lambda r: r.update(task_id="mmlu_pro"),
    lambda r: r.update(task_id=7),
    lambda r: r.update(dataset=""),
    lambda r: r.update(dataset="mmlu|pro", task_id="mmlu|pro:1"),
    lambda r: r.update(model_id="gpt-6-sol"),
])
def test_score_record_refuses(cv, change):
    record = score("mmlu_pro:1", quality=1.0)
    change(record)
    with pytest.raises(ValueError):
        cv.score_record(record)


@pytest.mark.parametrize("value", [None, [], "row", 3])
def test_score_record_refuses_a_non_object(cv, value):
    with pytest.raises(ValueError):
        cv.score_record(value)


# --- response_record -------------------------------------------------------------------------------------

def test_response_record_keeps_only_key_finish_cost_and_tokens(cv):
    out = cv.response_record(response("livecodebench:1873_A", "kimi-k2.7-code", usd=0.25, inp=140, out=533,
                                      finish="length"))
    assert out == {"task_id": "livecodebench:1873_A", "family": "livecodebench", "model": "moonshotai/kimi-k2.7-code",
                   "sample_index": 0, "prompt_sha256": SHA_A, "finish_reason": "length", "cost_usd": 0.25,
                   "input_tokens": 140, "output_tokens": 533}
    assert list(out) == ["task_id", "family", "model", "sample_index", "prompt_sha256", "finish_reason",
                         "cost_usd", "input_tokens", "output_tokens"]
    assert "the visible answer" not in json.dumps(out) and "the hidden reasoning" not in json.dumps(out)


def test_response_record_cost_is_a_float_and_negative_zero_is_zero(cv):
    out = cv.response_record(response("aime:x:1", usd=0))
    assert out["cost_usd"] == 0.0 and isinstance(out["cost_usd"], float)
    out = cv.response_record(response("aime:x:1", usd=-0.0))
    assert json.dumps(out["cost_usd"]) == "0.0"


@pytest.mark.parametrize("finish", ["stop", "length", "content_filter", None])
def test_response_record_finish_reason_is_a_string_or_null(cv, finish):
    assert cv.response_record(response("aime:x:1", finish=finish))["finish_reason"] == finish


def test_response_record_ignores_the_other_usage_fields(cv):
    record = response("aime:x:1", inp=7, out=9)
    record["usage"].update(cache_read=100, total_tokens=1, reasoning_tokens=50)
    out = cv.response_record(record)
    assert (out["input_tokens"], out["output_tokens"]) == (7, 9)


@pytest.mark.parametrize("change", [
    lambda r: r.update(sample_index=-1),
    lambda r: r.update(sample_index=True),
    lambda r: r.update(sample_index="0"),
    lambda r: r.pop("sample_index"),
    lambda r: r.update(official_usd=-0.01),
    lambda r: r.update(official_usd=float("nan")),
    lambda r: r.update(official_usd=float("inf")),
    lambda r: r.update(official_usd=True),
    lambda r: r.update(official_usd=None),
    lambda r: r.update(official_usd="0.1"),
    lambda r: r.update(official_usd=10**400),
    lambda r: r.update(usage=None),
    lambda r: r["usage"].update(input=-1),
    lambda r: r["usage"].update(output=True),
    lambda r: r["usage"].update(output=2.0),
    lambda r: r["usage"].pop("input"),
    lambda r: r.update(prompt_sha256="A" * 64),
    lambda r: r.update(prompt_sha256="a" * 63),
    lambda r: r.update(prompt_sha256=None),
    lambda r: r.update(finish_reason=1),
    lambda r: r.update(dataset="aime", task_id="gpqa_diamond:x"),
    lambda r: r.update(model_id="glm_5.3"),
])
def test_response_record_refuses(cv, change):
    record = response("aime:x:1")
    change(record)
    with pytest.raises(ValueError):
        cv.response_record(record)


# --- read_jsonl ------------------------------------------------------------------------------------------

def test_read_jsonl_parses_each_line_and_skips_blank_ones(cv, tmp_path):
    path = tmp_path / "scores_eval.jsonl"
    lines = [json.dumps(score("aime:x:1")), "", "   ", json.dumps(score("aime:x:2", quality=0.0))]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    out = cv.read_jsonl(path, cv.score_record)
    assert [(r["task_id"], r["correct"]) for r in out] == [("aime:x:1", True), ("aime:x:2", False)]


@pytest.mark.parametrize("bad", ["{not json", json.dumps(score("aime:x:2", quality=0.5)), "[1, 2]"])
def test_read_jsonl_names_the_file_and_line(cv, tmp_path, bad):
    path = tmp_path / "scores_cal.jsonl"
    path.write_text(json.dumps(score("aime:x:1")) + "\n\n" + bad + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"scores_cal\.jsonl:3"):
        cv.read_jsonl(path, cv.score_record)


def test_read_jsonl_refuses_invalid_utf8(cv, tmp_path):
    path = tmp_path / "responses_cal.jsonl"
    path.write_bytes(b'{"task_id": "\xff"}\n')
    with pytest.raises(ValueError, match=r"responses_cal\.jsonl:1"):
        cv.read_jsonl(path, cv.response_record)


# --- convert ---------------------------------------------------------------------------------------------

def test_convert_rows_and_report(cv):
    scores, responses = matrix(cv, ["aime:a:1", "aime:a:2", "mmlu_pro:5"])
    rows, report = cv.convert(scores, responses)
    assert [list(r) for r in rows] == [ROW_KEYS] * 6
    assert [(r["task"], r["item"], r["model"], r["correct"]) for r in rows] == [
        ("aime", "aime:a:1", "deepseek/deepseek-v4-pro", True),
        ("aime", "aime:a:1", "moonshotai/kimi-k2.7-code", False),
        ("aime", "aime:a:2", "deepseek/deepseek-v4-pro", False),
        ("aime", "aime:a:2", "moonshotai/kimi-k2.7-code", True),
        ("mmlu_pro", "mmlu_pro:5", "deepseek/deepseek-v4-pro", True),
        ("mmlu_pro", "mmlu_pro:5", "moonshotai/kimi-k2.7-code", False),
    ]
    assert [(r["cost_usd"], r["input_tokens"], r["output_tokens"]) for r in rows[:2]] == [(0.001, 10, 20), (0.002, 10, 21)]
    assert list(report) == ["models", "tasks", "ignored_samples", "rows"]
    assert report["models"] == ["deepseek/deepseek-v4-pro", "moonshotai/kimi-k2.7-code"]
    assert list(report["tasks"]) == ["aime", "mmlu_pro"]
    assert all(list(t) == TASK_KEYS for t in report["tasks"].values())
    assert report["tasks"]["aime"] == {**dict.fromkeys(TASK_KEYS, 0), "items": 2}
    assert report["tasks"]["mmlu_pro"]["items"] == 1
    assert (report["ignored_samples"], report["rows"]) == (0, 6)


def test_convert_rows_load_as_outcomes_and_evaluate(cv):
    scores, responses = matrix(cv, [f"aime:a:{n}" for n in range(8)])
    rows, _ = cv.convert(scores, responses)
    outcomes = outcomes_from_rows(rows)
    assert len(outcomes) == 16
    result = evaluate(outcomes, [0.5], seeds=range(2), min_samples=1)
    assert result["config"]["bars"] == [0.5]


def test_convert_counts_a_missing_cell_as_a_miss_at_no_cost(cv):
    scores, responses = matrix(cv, ["mmlu_pro:1", "mmlu_pro:2"])
    scores = [s for s in scores if (s["task_id"], s["model"]) != ("mmlu_pro:2", "moonshotai/kimi-k2.7-code")]
    scores.append(cv.score_record(score("mmlu_pro:2", "kimi-k2.7-code", quality=0.0, missing="content filter")))
    responses = [r for r in responses if (r["task_id"], r["model"]) != ("mmlu_pro:2", "moonshotai/kimi-k2.7-code")]
    rows, report = cv.convert(scores, responses)
    cell = [r for r in rows if r["item"] == "mmlu_pro:2" and r["model"] == "moonshotai/kimi-k2.7-code"]
    assert cell == [{"task": "mmlu_pro", "item": "mmlu_pro:2", "model": "moonshotai/kimi-k2.7-code",
                     "correct": False, "cost_usd": 0.0, "input_tokens": None, "output_tokens": None}]
    assert report["tasks"]["mmlu_pro"]["missing_cells"] == 1
    assert report["tasks"]["mmlu_pro"]["items"] == 2


def test_convert_a_missing_cell_with_a_response_keeps_its_bill(cv):
    scores, responses = matrix(cv, ["mmlu_pro:1"])
    scores[1] = cv.score_record(score("mmlu_pro:1", "kimi-k2.7-code", quality=0.0, missing="refusal"))
    rows, report = cv.convert(scores, responses)
    assert (rows[1]["correct"], rows[1]["cost_usd"], rows[1]["input_tokens"]) == (False, 0.002, 10)
    assert report["tasks"]["mmlu_pro"]["missing_cells"] == 1


def test_convert_scores_a_length_finish_as_the_scores_file_does(cv):
    scores, responses = matrix(cv, ["livecodebench:1", "livecodebench:2"])
    responses = [cv.response_record(response(r["task_id"], raw_of(r["model"]), finish="length"))
                 if r["task_id"] == "livecodebench:1" else r for r in responses]
    rows, report = cv.convert(scores, responses)
    assert [r["correct"] for r in rows if r["item"] == "livecodebench:1"] == [True, False]
    t = report["tasks"]["livecodebench"]
    assert (t["length_finishes"], t["length_successes"], t["other_finishes"], t["items"]) == (2, 1, 0, 2)


@pytest.mark.parametrize("finish", [None, "content_filter", "engine_overloaded"])
def test_convert_counts_other_finishes(cv, finish):
    scores, responses = matrix(cv, ["gpqa_diamond:r1"])
    responses[0] = cv.response_record(response("gpqa_diamond:r1", "deepseek-v4-pro", finish=finish))
    _, report = cv.convert(scores, responses)
    t = report["tasks"]["gpqa_diamond"]
    assert (t["other_finishes"], t["length_finishes"]) == (1, 0)


def test_convert_drops_an_item_some_model_has_no_score_for(cv):
    scores, responses = matrix(cv, ["aime:a:1", "aime:a:2"])
    scores = [s for s in scores if (s["task_id"], s["model"]) != ("aime:a:2", "moonshotai/kimi-k2.7-code")]
    responses = [r for r in responses if (r["task_id"], r["model"]) != ("aime:a:2", "moonshotai/kimi-k2.7-code")]
    rows, report = cv.convert(scores, responses)
    assert {r["item"] for r in rows} == {"aime:a:1"}
    assert (report["tasks"]["aime"]["items"], report["tasks"]["aime"]["dropped_incomplete"]) == (1, 1)


def test_convert_drops_a_scored_cell_with_no_bill(cv):
    scores, responses = matrix(cv, ["aime:a:1", "aime:a:2"])
    responses = [r for r in responses if (r["task_id"], r["model"]) != ("aime:a:2", "deepseek/deepseek-v4-pro")]
    rows, report = cv.convert(scores, responses)
    assert {r["item"] for r in rows} == {"aime:a:1"}
    assert report["tasks"]["aime"]["dropped_unbilled"] == 1


def test_convert_drops_an_item_whose_prompt_differs(cv):
    scores, responses = matrix(cv, ["aime:a:1", "aime:a:2"])
    responses[3] = cv.response_record(response("aime:a:2", "kimi-k2.7-code", prompt="c" * 64))
    rows, report = cv.convert(scores, responses)
    assert {r["item"] for r in rows} == {"aime:a:1"}
    assert report["tasks"]["aime"]["dropped_prompt_differs"] == 1


def test_convert_drop_order_incomplete_then_unbilled_then_prompt(cv):
    scores, responses = matrix(cv, ["aime:a:1", "aime:a:2"])
    scores = [s for s in scores if (s["task_id"], s["model"]) != ("aime:a:2", "moonshotai/kimi-k2.7-code")]
    responses = [r for r in responses if (r["task_id"], r["model"]) != ("aime:a:2", "moonshotai/kimi-k2.7-code")]
    responses = [r for r in responses if (r["task_id"], r["model"]) != ("aime:a:2", "deepseek/deepseek-v4-pro")]
    _, report = cv.convert(scores, responses)
    t = report["tasks"]["aime"]
    assert (t["dropped_incomplete"], t["dropped_unbilled"], t["dropped_prompt_differs"]) == (1, 0, 0)


def test_convert_ignores_a_response_at_another_sample_index(cv):
    scores, responses = matrix(cv, ["aime:a:1"])
    extra = cv.response_record(response("aime:a:1", "deepseek-v4-pro", usd=9.0, sample=1))
    rows, report = cv.convert(scores, responses + [extra])
    assert rows[0]["cost_usd"] == 0.001
    assert report["ignored_samples"] == 1


def test_convert_only_a_sample_one_response_leaves_the_cell_unbilled(cv):
    scores, responses = matrix(cv, ["aime:a:1", "aime:a:2"])
    responses[0] = cv.response_record(response("aime:a:1", "deepseek-v4-pro", sample=1))
    rows, report = cv.convert(scores, responses)
    assert {r["item"] for r in rows} == {"aime:a:2"}
    assert (report["tasks"]["aime"]["dropped_unbilled"], report["ignored_samples"]) == (1, 1)


def test_convert_a_task_with_every_item_dropped_stays_in_the_report(cv):
    scores, responses = matrix(cv, ["aime:a:1", "mmlu_pro:1"])
    responses = [r for r in responses if r["task_id"] != "mmlu_pro:1" or r["model"] != "deepseek/deepseek-v4-pro"]
    rows, report = cv.convert(scores, responses)
    assert {r["task"] for r in rows} == {"aime"}
    assert report["tasks"]["mmlu_pro"] == {**dict.fromkeys(TASK_KEYS, 0), "dropped_unbilled": 1}


def test_convert_does_not_depend_on_input_order_or_modify_input(cv):
    scores, responses = matrix(cv, ["aime:a:1", "aime:a:2", "mmlu_pro:5", "gpqa_diamond:r"])
    before = copy.deepcopy((scores, responses))
    expected = cv.convert(scores, responses)
    assert (scores, responses) == before
    rng = random.Random(7)
    for _ in range(3):
        s, r = list(scores), list(responses)
        rng.shuffle(s)
        rng.shuffle(r)
        assert cv.convert(s, r) == expected


def test_convert_models_are_every_scored_model(cv):
    scores, responses = matrix(cv, ["aime:a:1"], models=tuple(MODEL_IDS))
    rows, report = cv.convert(scores, responses)
    assert report["models"] == sorted(MODEL_IDS.values())
    assert [r["model"] for r in rows] == sorted(MODEL_IDS.values())


REFUSALS = {
    "no scores": r"^scores must be a non-empty list or tuple",
    "no responses": r"^responses must be a non-empty list or tuple",
    "scores not a list": r"^scores must be a non-empty list or tuple",
    "repeated score": r"^repeated score ",
    "repeated response": r"^repeated response ",
    "response without a score": r"^response without a score",
    "no row kept": r"^no row kept$",
}


@pytest.mark.parametrize("case", list(REFUSALS))
def test_convert_refuses(cv, case):
    scores, responses = matrix(cv, ["aime:a:1"])
    if case == "no scores":
        scores = []
    elif case == "no responses":
        responses = []
    elif case == "scores not a list":
        scores = iter(scores)
    elif case == "repeated score":
        scores = scores + [scores[0]]
    elif case == "repeated response":
        responses = responses + [responses[0]]
    elif case == "response without a score":
        responses = responses + [cv.response_record(response("aime:a:9"))]
    elif case == "no row kept":
        responses = responses[:1]
    with pytest.raises(ValueError, match=REFUSALS[case]):
        cv.convert(scores, responses)


# --- verify and fetch ------------------------------------------------------------------------------------

def small_files(monkeypatch, cv, contents):
    """Point FILES at small synthetic contents, ascending by name, and return the contents."""
    monkeypatch.setattr(cv, "FILES", {n: (len(b), hashlib.sha256(b).hexdigest()) for n, b in sorted(contents.items())})
    return contents


def test_verify(cv, tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_bytes(b"abc")
    cv.verify(path, 3, hashlib.sha256(b"abc").hexdigest())
    with pytest.raises(ValueError, match="size"):
        cv.verify(path, 4, hashlib.sha256(b"abc").hexdigest())
    with pytest.raises(ValueError, match="sha256"):
        cv.verify(path, 3, hashlib.sha256(b"abd").hexdigest())


class FakeResponse(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        self.close()


def test_fetch_downloads_each_missing_file_and_verifies_it(cv, tmp_path, monkeypatch):
    files = small_files(monkeypatch, cv, {"scores_cal.jsonl": b"s\n", "responses_cal.jsonl": b"r\n"})
    calls = []

    def urlopen(address, timeout=None):
        calls.append((address, timeout))
        return FakeResponse(files[address.rsplit("/", 1)[-1]])

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    out = cv.fetch(tmp_path / "cache")
    assert out == {n: tmp_path / "cache" / n for n in sorted(files)}
    assert all(p.read_bytes() == files[n] for n, p in out.items())
    assert calls == [(cv.url(n), 60) for n in sorted(files)]
    assert sorted(p.name for p in (tmp_path / "cache").iterdir()) == sorted(files)


def test_fetch_uses_a_cached_file_without_downloading(cv, tmp_path, monkeypatch):
    files = small_files(monkeypatch, cv, {"scores_cal.jsonl": b"s\n"})
    (tmp_path / "scores_cal.jsonl").write_bytes(files["scores_cal.jsonl"])
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded"))
    assert cv.fetch(tmp_path) == {"scores_cal.jsonl": tmp_path / "scores_cal.jsonl"}


def test_fetch_refuses_a_cached_file_that_fails_verify_and_leaves_it(cv, tmp_path, monkeypatch):
    small_files(monkeypatch, cv, {"scores_cal.jsonl": b"s\n"})
    (tmp_path / "scores_cal.jsonl").write_bytes(b"t\n")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded"))
    with pytest.raises(ValueError, match="scores_cal.jsonl"):
        cv.fetch(tmp_path)
    assert (tmp_path / "scores_cal.jsonl").read_bytes() == b"t\n"


def test_fetch_removes_the_part_file_when_a_download_fails_verify(cv, tmp_path, monkeypatch):
    small_files(monkeypatch, cv, {"scores_cal.jsonl": b"s\n"})
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: FakeResponse(b"t\n"))
    with pytest.raises(ValueError, match="sha256"):
        cv.fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_fetch_a_failed_download_is_an_oserror_naming_the_file(cv, tmp_path, monkeypatch):
    small_files(monkeypatch, cv, {"scores_cal.jsonl": b"s\n"})

    def urlopen(*a, **k):
        raise TimeoutError("timed out")

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    with pytest.raises(OSError, match="scores_cal.jsonl"):
        cv.fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []


# --- CLI -------------------------------------------------------------------------------------------------

def synthetic_cache(tmp_path, monkeypatch, cv):
    def lines(records):
        return "".join(json.dumps(r) + "\n" for r in records).encode("utf-8")

    pair = ("deepseek-v4-pro", "glm-5.3")
    contents = {
        "scores_cal.jsonl": lines([score("aime:c:1", m) for m in pair]),
        "scores_eval.jsonl": lines([score("mmlu_pro:1", m, quality=0.0) for m in pair]),
        "responses_cal.jsonl": lines([response("aime:c:1", m) for m in pair]),
        "responses_eval.jsonl": lines([response("mmlu_pro:1", m, finish="length") for m in pair]),
    }
    small_files(monkeypatch, cv, contents)
    cache = tmp_path / "cache"
    cache.mkdir()
    for name, data in contents.items():
        (cache / name).write_bytes(data)
    return cache


def run(cv, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cv.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_cli_writes_the_rows_and_prints_the_report(cv, tmp_path, monkeypatch):
    cache = synthetic_cache(tmp_path, monkeypatch, cv)
    target = tmp_path / "matrix.jsonl"
    code, out, err = run(cv, ["--out", str(target), "--cache", str(cache)])
    assert (code, err) == (0, "")
    rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines()]
    assert [(r["task"], r["item"], r["model"], r["correct"]) for r in rows] == [
        ("aime", "aime:c:1", "deepseek/deepseek-v4-pro", True),
        ("aime", "aime:c:1", "z-ai/glm-5.3", True),
        ("mmlu_pro", "mmlu_pro:1", "deepseek/deepseek-v4-pro", False),
        ("mmlu_pro", "mmlu_pro:1", "z-ai/glm-5.3", False),
    ]
    report = json.loads(out)
    assert out == json.dumps(report, indent=2) + "\n"
    assert report["rows"] == 4
    assert report["tasks"]["mmlu_pro"]["length_finishes"] == 2
    assert not target.with_name("matrix.jsonl.part").exists()


@pytest.mark.parametrize("argv", [[], ["--out"], ["--out", "{tmp}/no-such-folder/m.jsonl"], ["--out", "{tmp}"],
                                  ["--out", "{tmp}/"], ["--out", "{tmp}/m.jsonl", "--bogus"]])
def test_cli_a_bad_option_downloads_nothing(cv, tmp_path, monkeypatch, argv):
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded"))
    cache = tmp_path / "cache"
    code, out, err = run(cv, [a.replace("{tmp}", str(tmp_path)) for a in argv] + ["--cache", str(cache)])
    assert code == 2 and out == ""
    assert err.startswith("error: ") and err.count("\n") == 1
    assert not cache.exists()


def test_cli_a_bad_record_is_one_error_line_and_no_output(cv, tmp_path, monkeypatch):
    cache = synthetic_cache(tmp_path, monkeypatch, cv)
    bad = (cache / "scores_eval.jsonl").read_bytes().replace(b'"quality": 0.0', b'"quality": 0.5', 1)
    (cache / "scores_eval.jsonl").write_bytes(bad)
    monkeypatch.setattr(cv, "FILES", {**cv.FILES, "scores_eval.jsonl": (len(bad), hashlib.sha256(bad).hexdigest())})
    target = tmp_path / "matrix.jsonl"
    code, out, err = run(cv, ["--out", str(target), "--cache", str(cache)])
    assert code == 2 and out == ""
    assert err.startswith("error: scores_eval.jsonl:1") and err.count("\n") == 1
    assert not target.exists() and not target.with_name("matrix.jsonl.part").exists()


# --- the pinned files ------------------------------------------------------------------------------------

DEFAULT_TASKS = {
    "aime": {"items": 30, "length_finishes": 5},
    "gpqa_diamond": {"items": 198, "length_finishes": 71, "other_finishes": 6},
    "livecodebench": {"items": 1055, "length_finishes": 246, "length_successes": 16, "other_finishes": 3},
    "mmlu_pro": {"items": 12032, "missing_cells": 6, "length_finishes": 128, "length_successes": 1,
                 "other_finishes": 12},
}


@pytest.fixture(scope="module")
def pinned_run(tmp_path_factory):
    cv = load_cv()
    cache = cv.default_cache_dir()
    if not all((cache / name).is_file() for name in FILES):
        pytest.skip("the four pinned files are not in the default cache")
    target = tmp_path_factory.mktemp("response-bank") / "matrix.jsonl"
    code, out, err = run(cv, ["--out", str(target)])
    return code, out, err, target


def test_pinned_files_default_output(pinned_run):
    code, out, err, target = pinned_run
    assert (code, err) == (0, "")
    report = json.loads(out)
    assert report["models"] == sorted(MODEL_IDS.values())
    assert report["tasks"] == {t: {**dict.fromkeys(TASK_KEYS, 0), **v} for t, v in DEFAULT_TASKS.items()}
    assert (report["ignored_samples"], report["rows"]) == (0, 66575)


def test_pinned_files_rows(pinned_run):
    rows = [json.loads(line) for line in pinned_run[3].read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 66575 and len({r["item"] for r in rows}) == 13315
    unbilled = [r for r in rows if r["input_tokens"] is None]
    assert len(unbilled) == 6 and {r["task"] for r in unbilled} == {"mmlu_pro"}
    assert all(r["cost_usd"] == 0.0 and not r["correct"] for r in unbilled)
    assert {r["model"] for r in unbilled} == {"z-ai/glm-5.3", "z-ai/glm-5.3-flash"}
    assert all(r["cost_usd"] > 0 for r in rows if r["input_tokens"] is not None)
