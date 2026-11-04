"""v1.14 AutoBench 2026 converter contract (DESIGN 12.9), written before the converter exists.

The converter is a standard-library script outside the package
(``evidence/autobench-2026/convert.py``), so it is loaded from its path by an autouse
fixture before any other test code runs. Every test uses tiny in-memory tables except
the two at the end, which read the pinned files only when they are already in the
default cache and skip otherwise (CI never downloads them).
"""

import ast
import csv
import hashlib
import importlib.util
import io
import json
import math
import random
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "autobench-2026" / "convert.py"
EVIDENCE_README = ROOT / "evidence" / "autobench-2026" / "README.md"
REVISION = "43755180be7d8097068982d7a3f37fc04cd15379"
PINNED_FILES = {
    "matrix.csv": (1899644, "56d7a5c0a586364c8a0c0d5d737d0a4fde2a311a806b93beee38300e668ba28c"),
    "questions.csv": (298329, "c09fff8818218333bb5773e5f96754b41a312c8aa733972cb68f6be024afccb2"),
    "pool.json": (6582, "86c83dcbab072a912a1f61f79c76f32d394fad4e2ecccdbc0c80c2a5b40f67a8"),
    "frozen_params.json": (2042, "53b27f66d85f820637e9bb6215a80d9364b14707c3ff52b1632c1fe4221d76b7"),
    "SHA256SUMS": (1198, "2bb56265da42a3743a493f6b27e2e100597a78ec1724ae4a288fe585ec56b08a"),
}
BASE_URL = f"https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10/resolve/{REVISION}/"

POOL = {"members": [
    {"display_id": "Alpha-1", "openrouter_id": "x-ai/alpha-1", "family": "A"},
    {"display_id": "Beta-2", "openrouter_id": "acme/beta-2", "family": "B"},
    {"display_id": "Gamma-3", "openrouter_id": "z-ai/gamma-3", "family": "G"},
    {"display_id": "Delta-4", "openrouter_id": "acme/delta-4", "family": "D"},
]}
MODELS = ["acme/beta-2", "acme/delta-4", "xai/alpha-1", "zai/gamma-3"]
DISPLAY = ["Alpha-1", "Beta-2", "Gamma-3", "Delta-4"]


def load_cv():
    if not SCRIPT.is_file():
        raise ModuleNotFoundError(f"no converter at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("autobench_convert", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def cv():
    return load_cv()


def question(pid, domain="9 History"):
    return {"prompt_id": pid, "source_run": "r", "question": "text, with a comma", "ddc_domain": domain,
            "difficulty": "a", "intended_skill": "s"}


def cell(pid, model, score, cost="0.001", source="original"):
    return {"prompt_id": pid, "model": model, "score": score, "score_sd": "0.1", "n_judges": "10",
            "cost": cost, "input_tokens": "10", "output_tokens": "20", "reasoning_tokens": "0",
            "judges_json": "{}", "source": source, "has_answer": "true"}


def small():
    """Two complete questions, one with an unscored pool cell, two rows outside the pool."""
    questions = [question("q/1"), question("q/2", "A Agentic tool use"), question("q/3")]
    matrix = [
        cell("q/1", "Alpha-1", "5", "0.004"), cell("q/1", "Beta-2", "4.5", "0.002"),
        cell("q/1", "Gamma-3", "4.0", "0.001"), cell("q/1", "Delta-4", "3.5", "0.0005"),
        cell("q/2", "Alpha-1", "2", "0.003"), cell("q/2", "Beta-2", "3", "0.002"),
        cell("q/2", "Gamma-3", "4", "0.001"), cell("q/2", "Delta-4", "4", "0"),
        cell("q/3", "Alpha-1", "5"), cell("q/3", "Beta-2", "5"), cell("q/3", "Gamma-3", "", "0"),
        cell("q/3", "Delta-4", "5"),
        cell("q/1", "Outside-9", "4.9", "0.01", "fill_7_4"), cell("q/2", "Outside-9", "1", "0.01", "fill_7_4"),
    ]
    return matrix, questions


def row(task, item, model, correct, cost):
    return {"task": task, "item": item, "model": model, "correct": correct, "cost_usd": cost}


SMALL_ROWS = [
    row("9 History", "q/1", "acme/beta-2", True, 0.002),
    row("9 History", "q/1", "acme/delta-4", False, 0.0005),
    row("9 History", "q/1", "xai/alpha-1", True, 0.004),
    row("9 History", "q/1", "zai/gamma-3", False, 0.001),
    row("A Agentic tool use", "q/2", "acme/beta-2", False, 0.002),
    row("A Agentic tool use", "q/2", "acme/delta-4", True, 0.0),
    row("A Agentic tool use", "q/2", "xai/alpha-1", False, 0.003),
    row("A Agentic tool use", "q/2", "zai/gamma-3", True, 0.001),
]
SMALL_REPORT = {"models": MODELS, "width": 0.25, "top_k": 3, "task_by": "domain",
                "kept": {"9 History": 1, "A Agentic tool use": 1}, "dropped_unscored": {"9 History": 1},
                "unscored_cells": 1, "dropped_out_of_pool": {"Outside-9": 2}, "rows": 8}


# --- pins and layout ---------------------------------------------------------------------

def test_pins(cv):
    assert cv.REVISION == REVISION
    assert cv.FILES == PINNED_FILES
    assert list(cv.FILES) == list(PINNED_FILES)
    assert cv.BASE_URL == BASE_URL
    assert cv.default_cache_dir() == Path.home() / ".cache" / "ai-model-routing-evidence" / "autobench-2026"


def test_standard_library_only():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(a.name.split(".")[0] for a in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module.split(".")[0])
    assert names <= {"__future__", "argparse", "csv", "hashlib", "json", "math", "re", "sys",
                     "urllib", "pathlib"}


# --- model IDs and the pool ----------------------------------------------------------------

@pytest.mark.parametrize("given, want", [
    ("x-ai/grok-4.6", "xai/grok-4.6"), ("z-ai/glm-5.3", "zai/glm-5.3"),
    ("openai/gpt-5.6-luna", "openai/gpt-5.6-luna"), ("a-b-c/m-1", "abc/m-1"),
    ("moonshotai/kimi-k2.6", "moonshotai/kimi-k2.6")])
def test_model_id(cv, given, want):
    assert cv.model_id(given) == want


@pytest.mark.parametrize("bad", ["grok", "a/b/c", "/m", "v/", "-/m", "--/m", "", None, 3])
def test_model_id_rejects(cv, bad):
    with pytest.raises(ValueError):
        cv.model_id(bad)


def test_pool_models(cv):
    got = cv.pool_models(POOL)
    assert got == {"Alpha-1": "xai/alpha-1", "Beta-2": "acme/beta-2", "Gamma-3": "zai/gamma-3",
                   "Delta-4": "acme/delta-4"}
    assert list(got) == DISPLAY


@pytest.mark.parametrize("bad", [
    [], {}, {"members": []}, {"members": "x"}, {"members": ["x"]},
    {"members": [{"display_id": "", "openrouter_id": "a/b"}]},
    {"members": [{"display_id": "A", "openrouter_id": 7}]},
    {"members": [{"openrouter_id": "a/b"}]},
    {"members": [{"display_id": "A", "openrouter_id": "a/b"}, {"display_id": "A", "openrouter_id": "a/c"}]},
    {"members": [{"display_id": "A", "openrouter_id": "x-ai/m"}, {"display_id": "B", "openrouter_id": "xai/m"}]},
    {"members": [{"display_id": "A", "openrouter_id": "nope"}]},
])
def test_pool_models_rejects(cv, bad):
    with pytest.raises(ValueError):
        cv.pool_models(bad)


# --- Delta-Hit ------------------------------------------------------------------------------

def test_delta_hit_known_answers(cv):
    scores = [5.0, 4.5, 4.0, 3.0, 1.0]  # top three mean 4.5
    assert cv.delta_hit(4.25, scores, 0.25, 3) is True  # on the boundary counts
    assert cv.delta_hit(4.0, scores, 0.25, 3) is False
    assert cv.delta_hit(4.0, scores, 0.5, 3) is True
    assert cv.delta_hit(4.75, scores, 0.25, 1) is True  # top 1 = the best
    assert cv.delta_hit(4.5, scores, 0.25, 1) is False
    assert cv.delta_hit(3.0, scores, 0.5, 5) is True  # top 5 mean 3.5


def test_delta_hit_uses_fsum_and_ignores_order(cv):
    scores = [0.1] * 10 + [1e16, -1e16]
    a = cv.delta_hit(0.0, scores, 1e-9, 12)
    shuffled = scores[:]
    random.Random(3).shuffle(shuffled)
    assert cv.delta_hit(0.0, shuffled, 1e-9, 12) is a
    # fsum: (1e16 - 1e16 + 10 * 0.1) / 12 = 1/12, so 0.0 misses and 1/12 hits
    assert a is False
    assert cv.delta_hit(math.fsum(scores) / 12, scores, 1e-9, 12) is True


# --- convert --------------------------------------------------------------------------------

def test_convert_known_answer(cv):
    matrix, questions = small()
    rows, report = cv.convert(matrix, questions, POOL, 0.25)
    assert rows == SMALL_ROWS
    assert [list(r) for r in rows] == [["task", "item", "model", "correct", "cost_usd"]] * 8
    assert all(type(r["cost_usd"]) is float and type(r["correct"]) is bool for r in rows)
    assert report == SMALL_REPORT
    assert list(report) == list(SMALL_REPORT)


def test_convert_task_by_all(cv):
    matrix, questions = small()
    rows, report = cv.convert(matrix, questions, POOL, 0.25, task_by="all")
    assert rows == [dict(r, task="all") for r in SMALL_ROWS]
    assert report["kept"] == {"all": 2} and report["dropped_unscored"] == {"all": 1}
    assert report["task_by"] == "all"


def test_convert_task_by_all_ignores_domain(cv):
    matrix, questions = small()
    questions[0]["ddc_domain"] = ""
    rows, _ = cv.convert(matrix, questions, POOL, 0.25, task_by="all")
    assert len(rows) == 8
    with pytest.raises(ValueError):
        cv.convert(matrix, questions, POOL, 0.25)


def test_convert_width_and_top_k(cv):
    matrix, questions = small()
    rows, report = cv.convert(matrix, questions, POOL, 0.5, top_k=1)
    # q/1: best 5, so >= 4.5 hits; q/2: best 4, so >= 3.5 hits
    assert [r["correct"] for r in rows] == [True, False, True, False, False, True, False, True]
    assert report["width"] == 0.5 and report["top_k"] == 1


def test_missing_pool_row_counts_as_unscored(cv):
    matrix, questions = small()
    matrix = [r for r in matrix if not (r["prompt_id"] == "q/2" and r["model"] == "Beta-2")]
    rows, report = cv.convert(matrix, questions, POOL, 0.25)
    assert [r["item"] for r in rows] == ["q/1"] * 4
    assert report["kept"] == {"9 History": 1}
    assert report["dropped_unscored"] == {"9 History": 1, "A Agentic tool use": 1}
    assert report["unscored_cells"] == 2


def test_question_with_no_rows_is_dropped(cv):
    matrix, questions = small()
    questions.append(question("q/4", "5 Science"))
    _, report = cv.convert(matrix, questions, POOL, 0.25)
    assert report["dropped_unscored"] == {"5 Science": 1, "9 History": 1}
    assert report["unscored_cells"] == 5


def test_out_of_pool_rows_are_not_validated(cv):
    matrix, questions = small()
    matrix.append(cell("q/3", "Outside-8", "not a number", "-1", "fill_7_4"))
    rows, report = cv.convert(matrix, questions, POOL, 0.25)
    assert rows == SMALL_ROWS
    assert report["dropped_out_of_pool"] == {"Outside-8": 1, "Outside-9": 2}


def test_unscored_pool_cell_cost_is_not_validated(cv):
    matrix, questions = small()
    for r in matrix:
        if r["prompt_id"] == "q/3" and r["model"] == "Gamma-3":
            r["cost"] = ""
    rows, _ = cv.convert(matrix, questions, POOL, 0.25)
    assert rows == SMALL_ROWS


def test_negative_zero_cost(cv):
    matrix, questions = small()
    for r in matrix:
        if r["prompt_id"] == "q/2" and r["model"] == "Delta-4":
            r["cost"] = "-0.0"
    rows, _ = cv.convert(matrix, questions, POOL, 0.25)
    cost = [r["cost_usd"] for r in rows if r["item"] == "q/2" and r["model"] == "acme/delta-4"][0]
    assert cost == 0.0 and math.copysign(1.0, cost) == 1.0


def test_row_order_does_not_matter(cv):
    matrix, questions = small()
    want = cv.convert(matrix, questions, POOL, 0.25)
    for seed in range(5):
        rng = random.Random(seed)
        m, q = matrix[:], questions[:]
        rng.shuffle(m)
        rng.shuffle(q)
        assert cv.convert(m, q, POOL, 0.25) == want


def test_inputs_not_modified(cv):
    matrix, questions = small()
    before = json.dumps([matrix, questions, POOL])
    cv.convert(matrix, questions, POOL, 0.25)
    assert json.dumps([matrix, questions, POOL]) == before


@pytest.mark.parametrize("source", ["original", "fill_7_4"])
def test_repeated_pair_is_refused(cv, source):
    matrix, questions = small()
    matrix.append(cell("q/1", "Alpha-1", "5", "0.004", source))
    with pytest.raises(ValueError, match="q/1"):
        cv.convert(matrix, questions, POOL, 0.25)


def test_repeated_out_of_pool_pair_is_refused(cv):
    matrix, questions = small()
    matrix.append(cell("q/1", "Outside-9", "4.9", "0.01", "fill_7_4"))
    with pytest.raises(ValueError, match="Outside-9"):
        cv.convert(matrix, questions, POOL, 0.25)


@pytest.mark.parametrize("width", [True, "0.2", None, float("nan"), float("inf"), 0, 0.0, -0.1])
def test_bad_width(cv, width):
    matrix, questions = small()
    with pytest.raises(ValueError):
        cv.convert(matrix, questions, POOL, width)


@pytest.mark.parametrize("top_k", [True, 0, -1, 5, 1.0, "3", None])
def test_bad_top_k(cv, top_k):
    matrix, questions = small()
    with pytest.raises(ValueError):
        cv.convert(matrix, questions, POOL, 0.25, top_k=top_k)


def test_top_k_equal_to_pool_size_is_allowed(cv):
    matrix, questions = small()
    rows, _ = cv.convert(matrix, questions, POOL, 0.25, top_k=4)
    assert len(rows) == 8


@pytest.mark.parametrize("task_by", ["difficulty", "", None, "Domain"])
def test_bad_task_by(cv, task_by):
    matrix, questions = small()
    with pytest.raises(ValueError):
        cv.convert(matrix, questions, POOL, 0.25, task_by=task_by)


def test_bad_pool_in_convert(cv):
    matrix, questions = small()
    with pytest.raises(ValueError):
        cv.convert(matrix, questions, {"members": []}, 0.25)


@pytest.mark.parametrize("change", [
    lambda q: q[0].update(prompt_id=""), lambda q: q[0].pop("prompt_id"),
    lambda q: q.append(question("q/1")), lambda q: q[1].update(ddc_domain=""),
    lambda q: q[1].pop("ddc_domain"),
])
def test_bad_question(cv, change):
    matrix, questions = small()
    change(questions)
    with pytest.raises(ValueError):
        cv.convert(matrix, questions, POOL, 0.25)


@pytest.mark.parametrize("pid, model, field, value, needle", [
    ("q/1", "Alpha-1", "prompt_id", "q/9", "q/9"),
    ("q/1", "Alpha-1", "prompt_id", "", None),
    ("q/1", "Alpha-1", "model", "", None),
    ("q/1", "Alpha-1", "score", "abc", "Alpha-1"),
    ("q/1", "Beta-2", "score", "nan", "Beta-2"),
    ("q/2", "Gamma-3", "score", "inf", "q/2"),
    ("q/1", "Alpha-1", "cost", "-0.1", "Alpha-1"),
    ("q/1", "Alpha-1", "cost", "nan", "q/1"),
    ("q/2", "Delta-4", "cost", "", "Delta-4"),
    ("q/2", "Delta-4", "cost", "1e400", "q/2"),
])
def test_bad_matrix_row(cv, pid, model, field, value, needle):
    matrix, questions = small()
    for r in matrix:
        if r["prompt_id"] == pid and r["model"] == model:
            r[field] = value
    with pytest.raises(ValueError) as info:
        cv.convert(matrix, questions, POOL, 0.25)
    if needle:
        assert needle in str(info.value)


def test_output_feeds_the_evaluator(cv):
    questions = [question(f"q/{i:03d}") for i in range(60)]
    matrix = []
    for i in range(60):
        pid = f"q/{i:03d}"
        matrix += [cell(pid, "Alpha-1", "5", "0.004"), cell(pid, "Beta-2", "3" if i % 3 == 0 else "4.9", "0.002"),
                   cell(pid, "Gamma-3", "4", "0.001"), cell(pid, "Delta-4", "1", "0.0001")]
    rows, report = cv.convert(matrix, questions, POOL, 0.25)
    assert report["rows"] == 240 and report["kept"] == {"9 History": 60}
    result = evaluate(outcomes_from_rows(rows), bars=[0.6], seeds=range(3), min_samples=5)
    assert result["tasks"] == {"9 History": {"items": 60, "models": MODELS}}


# --- files, sums and fetch ------------------------------------------------------------------

def sums_text(files):
    return "".join(f"{sha}  {name}\n" for name, (_, sha) in files.items() if name != "SHA256SUMS")


def test_check_sums_accepts_the_pins(cv):
    text = "\n" + sums_text(PINNED_FILES) + "0" * 64 + "  answers.csv\n\n"
    cv.check_sums(text)


def test_check_sums_missing_entry(cv):
    text = "".join(line + "\n" for line in sums_text(PINNED_FILES).splitlines() if "pool.json" not in line)
    with pytest.raises(ValueError, match="pool.json"):
        cv.check_sums(text)


def test_check_sums_differing_entry(cv):
    text = sums_text(PINNED_FILES).replace(PINNED_FILES["matrix.csv"][1], "f" * 64)
    with pytest.raises(ValueError, match="matrix.csv"):
        cv.check_sums(text)


@pytest.mark.parametrize("bad", ["not a sums line\n", "abc  matrix.csv\n", "0" * 64 + " one-space.csv\n",
                                 "0" * 63 + "G  x.csv\n"])
def test_check_sums_malformed_line(cv, bad):
    with pytest.raises(ValueError):
        cv.check_sums(sums_text(PINNED_FILES) + bad)


def test_verify(cv, tmp_path):
    p = tmp_path / "f.csv"
    p.write_bytes(b"abc")
    sha = hashlib.sha256(b"abc").hexdigest()
    cv.verify(p, 3, sha)
    with pytest.raises(ValueError, match="4"):
        cv.verify(p, 4, sha)
    with pytest.raises(ValueError, match=sha):
        cv.verify(p, 3, "0" * 64)


FAKE = {"matrix.csv": b"m,1\n", "questions.csv": b"q\n", "pool.json": b"{}", "frozen_params.json": b"{}\n"}


def fake_files(sums=None):
    contents = dict(FAKE)
    files = {name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in contents.items()}
    contents["SHA256SUMS"] = (sums if sums is not None else sums_text(files)).encode()
    files["SHA256SUMS"] = (len(contents["SHA256SUMS"]), hashlib.sha256(contents["SHA256SUMS"]).hexdigest())
    return files, contents


def serve(monkeypatch, cv, contents, calls):
    def urlopen(url, timeout=None):
        calls.append(url)
        assert url.startswith(BASE_URL)
        return io.BytesIO(contents[url[len(BASE_URL):]])
    monkeypatch.setattr(cv.urllib.request, "urlopen", urlopen)


def test_fetch_downloads_verifies_and_renames(cv, tmp_path, monkeypatch):
    files, contents = fake_files()
    monkeypatch.setattr(cv, "FILES", files)
    calls = []
    serve(monkeypatch, cv, contents, calls)
    got = cv.fetch(tmp_path / "cache")
    assert got == tmp_path / "cache"
    assert calls == [BASE_URL + name for name in files]
    for name, data in contents.items():
        assert (got / name).read_bytes() == data
    assert not list(got.glob("*.part"))
    calls.clear()
    assert cv.fetch(tmp_path / "cache") == got
    assert calls == []


def test_fetch_keeps_a_bad_cached_file(cv, tmp_path, monkeypatch):
    files, contents = fake_files()
    monkeypatch.setattr(cv, "FILES", files)
    serve(monkeypatch, cv, contents, [])
    (tmp_path / "matrix.csv").write_bytes(b"tampered")
    with pytest.raises(ValueError, match="matrix.csv"):
        cv.fetch(tmp_path)
    assert (tmp_path / "matrix.csv").read_bytes() == b"tampered"


def test_fetch_removes_a_bad_download(cv, tmp_path, monkeypatch):
    files, contents = fake_files()
    monkeypatch.setattr(cv, "FILES", files)
    contents["questions.csv"] = b"other\n"
    serve(monkeypatch, cv, contents, [])
    with pytest.raises(ValueError, match="questions.csv"):
        cv.fetch(tmp_path)
    assert not (tmp_path / "questions.csv").exists()
    assert not (tmp_path / "questions.csv.part").exists()


def test_fetch_checks_the_dataset_sums(cv, tmp_path, monkeypatch):
    files, _ = fake_files()
    bad = sums_text(files).replace(files["pool.json"][1], "0" * 64)
    files, contents = fake_files(sums=bad)
    monkeypatch.setattr(cv, "FILES", files)
    serve(monkeypatch, cv, contents, [])
    with pytest.raises(ValueError, match="pool.json"):
        cv.fetch(tmp_path)


def test_read_csv(cv, tmp_path):
    p = tmp_path / "t.csv"
    p.write_text('a,b\n1,"x, y"\n2,\n', encoding="utf-8")
    assert cv.read_csv(p) == [{"a": "1", "b": "x, y"}, {"a": "2", "b": ""}]


# --- CLI ------------------------------------------------------------------------------------

def write_folder(folder, matrix, questions, params=None):
    folder.mkdir(parents=True, exist_ok=True)
    for name, table in (("matrix.csv", matrix), ("questions.csv", questions)):
        with (folder / name).open("w", encoding="utf-8", newline="") as f:
            w = csv.DictWriter(f, fieldnames=list(table[0]))
            w.writeheader()
            w.writerows(table)
    (folder / "pool.json").write_text(json.dumps(POOL), encoding="utf-8")
    params = params if params is not None else {"delta_signal": 0.25, "delta_official": 0.5, "top_k": 3}
    (folder / "frozen_params.json").write_text(json.dumps(params), encoding="utf-8")
    return folder


@pytest.fixture
def folder(cv, tmp_path, monkeypatch):
    matrix, questions = small()
    data = write_folder(tmp_path / "data", matrix, questions)
    seen = []

    def fetch(cache_dir=None):
        seen.append(cache_dir)
        return data
    monkeypatch.setattr(cv, "fetch", fetch)
    return data, seen


def test_main_writes_the_matrix(cv, tmp_path, folder, capsys):
    _, seen = folder
    out = tmp_path / "out.jsonl"
    assert cv.main(["--out", str(out)]) == 0
    captured = capsys.readouterr()
    assert captured.out == json.dumps(SMALL_REPORT, indent=2) + "\n"
    assert captured.err == ""
    assert out.read_text(encoding="utf-8") == "".join(json.dumps(r) + "\n" for r in SMALL_ROWS)
    assert not (tmp_path / "out.jsonl.part").exists()
    assert seen == [None]


def test_main_options(cv, tmp_path, folder, capsys):
    _, seen = folder
    out = tmp_path / "out.jsonl"
    assert cv.main(["--out", str(out), "--cache", str(tmp_path / "c"), "--width", "0.5",
                    "--task-by", "all"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["width"] == 0.5 and report["task_by"] == "all" and report["kept"] == {"all": 2}
    assert seen == [str(tmp_path / "c")]


def test_main_reads_top_k_from_params(cv, tmp_path, monkeypatch, capsys):
    matrix, questions = small()
    data = write_folder(tmp_path / "data", matrix, questions, {"delta_signal": 0.5, "top_k": 1})
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: data)
    assert cv.main(["--out", str(tmp_path / "o.jsonl")]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["width"] == 0.5 and report["top_k"] == 1


@pytest.mark.parametrize("argv", [[], ["--width", "0"], ["--width", "nan"], ["--width", "x"],
                                  ["--width", "-1"], ["--task-by", "difficulty"], ["--bogus"]])
def test_main_bad_options_never_fetch(cv, tmp_path, folder, capsys, argv):
    _, seen = folder
    full = argv if argv == [] else ["--out", str(tmp_path / "o.jsonl")] + argv
    assert cv.main(full) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1 and captured.err.startswith("error: ")
    assert seen == []


def test_main_bad_data(cv, tmp_path, monkeypatch, capsys):
    matrix, questions = small()
    matrix.append(cell("q/1", "Alpha-1", "5"))
    data = write_folder(tmp_path / "data", matrix, questions)
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: data)
    out = tmp_path / "o.jsonl"
    assert cv.main(["--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and len(captured.err.splitlines()) == 1 and captured.err.startswith("error: ")
    assert not out.exists() and not (tmp_path / "o.jsonl.part").exists()


def test_main_fetch_error(cv, tmp_path, monkeypatch, capsys):
    def fetch(cache_dir=None):
        raise ValueError("matrix.csv: expected 1 bytes, got 2")
    monkeypatch.setattr(cv, "fetch", fetch)
    assert cv.main(["--out", str(tmp_path / "o.jsonl")]) == 2
    assert capsys.readouterr().err == "error: matrix.csv: expected 1 bytes, got 2\n"


# --- docs -----------------------------------------------------------------------------------

def test_evidence_readme():
    text = EVIDENCE_README.read_text(encoding="utf-8")
    for needle in ["https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10", REVISION,
                   "CC-BY-4.0", "Do LLM Routers Pay for Themselves?",
                   "python evidence/autobench-2026/convert.py --out", "--width 0.3011090610836323",
                   "--task-by all", "not an absolute acceptance check", "203 of 252", "4,060 rows",
                   "6,291"]:
        assert needle in text, needle


# --- the pinned files, only when already cached ---------------------------------------------

def cached(cv, names):
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in names):
        pytest.skip("pinned AutoBench files are not in the default cache")
    return folder


def test_real_files_default_options(cv):
    folder = cached(cv, PINNED_FILES)
    for name, (size, sha) in PINNED_FILES.items():
        cv.verify(folder / name, size, sha)
    cv.check_sums((folder / "SHA256SUMS").read_text(encoding="utf-8"))
    params = json.loads((folder / "frozen_params.json").read_text(encoding="utf-8"))
    pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
    matrix, questions = cv.read_csv(folder / "matrix.csv"), cv.read_csv(folder / "questions.csv")
    rows, report = cv.convert(matrix, questions, pool, params["delta_signal"], params["top_k"])
    assert len(report["models"]) == 20 and report["rows"] == 4060 == len(rows)
    assert sum(report["kept"].values()) == 203 and len(report["kept"]) == 10
    assert min(report["kept"].values()) == 12 and max(report["kept"].values()) == 33
    assert sum(report["dropped_unscored"].values()) == 49 and report["unscored_cells"] == 107
    assert sum(report["dropped_out_of_pool"].values()) == 388 and len(report["dropped_out_of_pool"]) == 13
    assert "xai/grok-4.6" in report["models"] and "zai/glm-5.3" in report["models"]
    assert round(sum(r["correct"] for r in rows) / len(rows), 3) == 0.667
    official, _ = cv.convert(matrix, questions, pool, params["delta_official"], params["top_k"])
    assert round(sum(r["correct"] for r in official) / len(official), 3) == 0.762
    outcomes_from_rows(rows)


def test_real_delta_hit_reproduces_the_dataset_labels(cv):
    folder = cached(cv, list(PINNED_FILES) + ["decisions.csv"])
    sums = dict(reversed(line.split("  ", 1)) for line in
                (folder / "SHA256SUMS").read_text(encoding="utf-8").splitlines() if line)
    if hashlib.sha256((folder / "decisions.csv").read_bytes()).hexdigest() != sums["decisions.csv"]:
        pytest.skip("cached decisions.csv does not match the dataset's SHA256SUMS")
    params = json.loads((folder / "frozen_params.json").read_text(encoding="utf-8"))
    pool = set(cv.pool_models(json.loads((folder / "pool.json").read_text(encoding="utf-8"))))
    by_question = {}
    for r in cv.read_csv(folder / "matrix.csv"):
        if r["model"] in pool and r["score"]:
            by_question.setdefault(r["prompt_id"], []).append(float(r["score"]))
    checked = 0
    for d in cv.read_csv(folder / "decisions.csv"):
        if d["delta_hit_signal"] in ("True", "False"):
            got = cv.delta_hit(float(d["score"]), by_question[d["prompt_id"]], params["delta_signal"],
                               params["top_k"])
            assert got == (d["delta_hit_signal"] == "True"), d["prompt_id"]
            checked += 1
    assert checked == 6291
