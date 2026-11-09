"""LLMRouterBench converter contract (DESIGN 12.18, v1.154), written before the converter and kept as its tests.

The converter is a standard-library script outside the package (``evidence/llmrouterbench/convert.py``),
so it is loaded from its path by an autouse fixture. Every test uses small synthetic result files,
packed into a gzip tarball in a temporary folder where a test needs one, except one module-scoped
CLI run on the pinned file, which runs only when it is in the default cache and skips otherwise
(CI never downloads it).
"""

import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import math
import tarfile
import urllib.request
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "llmrouterbench" / "convert.py"
REVISION = "b95870f9e60c589e82f7972c91ffa8de9ca89f85"
SIZE = 1283503080
SHA256 = "b79f8cde1a6f029c2efa663a3a3b6f7748defb22341fe59f328cebef6648c8f1"
POOL_IDS = {
    "claude-sonnet-4": "anthropic/claude-sonnet-4",
    "deepseek-r1-0528": "deepseek/deepseek-r1-0528",
    "deepseek-v3-0324": "deepseek/deepseek-v3-0324",
    "deepseek-v3.1-terminus": "deepseek/deepseek-v3.1-terminus",
    "gemini-2.5-flash": "google/gemini-2.5-flash",
    "gemini-2.5-pro": "google/gemini-2.5-pro",
    "glm-4.6": "z-ai/glm-4.6",
    "gpt-5": "openai/gpt-5",
    "gpt-5-chat": "openai/gpt-5-chat",
    "intern-s1": "internlm/intern-s1",
    "kimi-k2-0905": "moonshotai/kimi-k2-0905",
    "qwen3-235b-a22b-2507": "qwen/qwen3-235b-a22b-2507",
    "qwen3-235b-a22b-thinking-2507": "qwen/qwen3-235b-a22b-thinking-2507",
}
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd", "input_tokens", "output_tokens"]

pytestmark = pytest.mark.xfail(strict=True, raises=ModuleNotFoundError, reason="converter not written yet (v1.154 red)")


def load_cv():
    if not SCRIPT.is_file():
        raise ModuleNotFoundError(f"no converter at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("lrb_convert", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def cv():
    return load_cv()


def record(index, score=1.0, cost=0.01, pt=10, ct=20, query="q", **extra):
    rec = {"index": index, "origin_query": f"{query}{index}", "prompt": "prompt text", "prompt_tokens": pt,
           "completion_tokens": ct, "cost": cost, "score": score, "prediction": ["p"], "ground_truth": "g",
           "raw_output": "raw text"}
    rec.update(extra)
    return rec


def doc(records):
    return {"performance": 0.5, "prompt_tokens": 1, "completion_tokens": 1, "cost": 0.1, "counts": len(records),
            "model_name": "m", "dataset_name": "d", "split": "test", "demo": False, "records": records}


def ext(cv, bench, split, folder, records):
    return cv.extract(doc(records), bench, split, folder)


POOL2 = ["openai/gpt-5", "google/gemini-2.5-pro"]


# --- source pins -------------------------------------------------------------------------

def test_source_pins(cv):
    assert cv.REVISION == REVISION and cv.LICENCE == "MIT" and cv.FILE == "bench-release.tar.gz"
    assert cv.SIZE == SIZE and cv.SHA256 == SHA256
    assert cv.URL == f"https://huggingface.co/datasets/NPULH/LLMRouterBench/resolve/{REVISION}/bench-release.tar.gz"


def test_pool_is_the_13_folders_ascending(cv):
    assert list(cv.POOL) == sorted(POOL_IDS) and len(cv.POOL) == 13


@pytest.mark.parametrize("folder, mid", sorted(POOL_IDS.items()))
def test_model_id_of_each_pool_folder(cv, folder, mid):
    assert cv.model_id(folder) == mid


@pytest.mark.parametrize("bad", [None, "", 5, "a/b", "gpt-\u00e9", "Qwen3-8B", "openrouter", "gpt-5 copy", "-gpt"])
def test_model_id_refuses(cv, bad):
    with pytest.raises(ValueError):
        cv.model_id(bad)


def test_default_cache_dir(cv):
    assert cv.default_cache_dir() == Path.home() / ".cache" / "ai-model-routing-evidence" / "llmrouterbench"


# --- member_path -------------------------------------------------------------------------

@pytest.mark.parametrize("name, key", [
    ("bench-release/arenahard/gpt-5/arenahard-test-gpt-5-1.json", ("arenahard", "", "gpt-5")),
    ("bench-release/hle/test/gpt-5/hle-test-gpt-5-1.json", ("hle", "test", "gpt-5")),
])
def test_member_path_reads_both_layouts(cv, name, key):
    assert cv.member_path(name) == key


@pytest.mark.parametrize("name", [
    None, "bench-release", "bench-release/hle", "bench-release/hle/gpt-5", "bench-release/hle/gpt-5/x.txt",
    "other/hle/test/gpt-5/x.json", "bench-release/hle/test/extra/gpt-5/x.json", "bench-release/hle//gpt-5/x.json",
    "bench-release/../test/gpt-5/x.json", "bench-release/hle/./gpt-5/x.json", "bench-release/hle/gpt-5/.json",
])
def test_member_path_none_for_other_members(cv, name):
    assert cv.member_path(name) is None


# --- extract -----------------------------------------------------------------------------

def test_extract_keeps_only_what_the_matrix_needs(cv):
    ex = ext(cv, "hle", "test", "gpt-5", [record(2, score=0.0, cost=-0.0), record(1, score=None, ct=-52)])
    assert list(ex) == ["benchmark", "split", "model", "cells"]
    assert (ex["benchmark"], ex["split"], ex["model"]) == ("hle", "test", "openai/gpt-5")
    assert list(ex["cells"]) == [1, 2]
    one, two = ex["cells"][1], ex["cells"][2]
    assert list(one) == ["score", "cost_usd", "input_tokens", "output_tokens", "query"]
    assert one["score"] is None and one["output_tokens"] is None and one["input_tokens"] == 10
    assert two["score"] == 0.0 and type(two["score"]) is float
    assert two["cost_usd"] == 0.0 and math.copysign(1, two["cost_usd"]) == 1.0
    assert one["query"] == hashlib.sha256(json.dumps("q1", ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    assert "raw text" not in json.dumps(ex) and "prompt text" not in json.dumps(ex) and '"q1"' not in json.dumps(ex)


def test_query_digest_is_canonical_json(cv):
    assert cv.query_digest({"b": 1, "a": "\u00e9"}) == hashlib.sha256('{"a": "\u00e9", "b": 1}'.encode()).hexdigest()


@pytest.mark.parametrize("score", [0, 0.5, 1, 0.0, 1.0])
def test_extract_accepts_scores(cv, score):
    assert ext(cv, "b", "", "gpt-5", [record(0, score=score)])["cells"][0]["score"] == float(score)


@pytest.mark.parametrize("change", [
    {"index": -1}, {"index": True}, {"index": "1"}, {"index": 1.0}, {"score": 0.3}, {"score": True}, {"score": "1"},
    {"cost": -0.01}, {"cost": float("nan")}, {"cost": float("inf")}, {"cost": True}, {"cost": "0.1"}, {"cost": None},
    {"prompt_tokens": 1.0}, {"completion_tokens": None}, {"prompt_tokens": False},
])
def test_extract_refuses_bad_fields(cv, change):
    with pytest.raises(ValueError):
        ext(cv, "b", "", "gpt-5", [record(0, **change)])


@pytest.mark.parametrize("missing", ["index", "cost", "prompt_tokens", "completion_tokens", "origin_query"])
def test_extract_refuses_missing_fields(cv, missing):
    rec = record(0)
    del rec[missing]
    with pytest.raises(ValueError):
        ext(cv, "b", "", "gpt-5", [rec])


@pytest.mark.parametrize("bad_doc", [None, [], {}, {"records": []}, {"records": {}}, {"records": [5]}])
def test_extract_refuses_bad_docs(cv, bad_doc):
    with pytest.raises(ValueError):
        cv.extract(bad_doc, "b", "", "gpt-5")


@pytest.mark.parametrize("bench, split, folder", [("", "", "gpt-5"), ("a|b", "", "gpt-5"), (None, "", "gpt-5"),
                                                  ("b", "t|1", "gpt-5"), ("b", None, "gpt-5"), ("b", "", "openrouter")])
def test_extract_refuses_bad_names(cv, bench, split, folder):
    with pytest.raises(ValueError):
        cv.extract(doc([record(0)]), bench, split, folder)


def test_extract_refuses_a_repeated_index(cv):
    with pytest.raises(ValueError, match="repeats"):
        ext(cv, "b", "", "gpt-5", [record(0), record(0)])


# --- convert -----------------------------------------------------------------------------

def two_model(cv, bench="b", split="test", a=None, b=None):
    a = a if a is not None else [record(0), record(1, score=0.0)]
    b = b if b is not None else [record(0, score=0.5), record(1)]
    return [ext(cv, bench, split, "gpt-5", a), ext(cv, bench, split, "gemini-2.5-pro", b)]


def test_convert_rows_and_report(cv):
    rows, report = cv.convert(two_model(cv), pool=POOL2)
    assert [list(r) for r in rows] == [ROW_KEYS] * 4
    assert [(r["item"], r["model"], r["correct"]) for r in rows] == [
        ("b|0", "google/gemini-2.5-pro", False), ("b|0", "openai/gpt-5", True),
        ("b|1", "google/gemini-2.5-pro", True), ("b|1", "openai/gpt-5", False)]
    assert all(r["task"] == "b" and r["cost_usd"] == 0.01 and r["input_tokens"] == 10 and r["output_tokens"] == 20 for r in rows)
    assert list(report) == ["models", "tasks", "dropped_benchmarks", "lacking", "rows"]
    assert report["models"] == sorted(POOL2) and report["rows"] == 4
    assert report["tasks"] == {"b": {"split": "test", "items": 2, "dropped_incomplete": 0, "dropped_unscored": 0,
                                     "dropped_question_differs": 0, "half_scores": 1, "null_tokens": 0}}
    assert report["dropped_benchmarks"] == {} and report["lacking"] == {}


def test_convert_drops_incomplete_unscored_and_differing_items_in_that_order(cv):
    a = [record(0), record(1), record(2, score=None), record(3), record(4)]
    b = [record(0), record(2, query="other"), record(3, query="other"), record(4, score=None, query="other")]
    rows, report = cv.convert(two_model(cv, a=a, b=b), pool=POOL2)
    assert sorted({r["item"] for r in rows}) == ["b|0"]
    t = report["tasks"]["b"]
    assert (t["items"], t["dropped_incomplete"], t["dropped_unscored"], t["dropped_question_differs"]) == (1, 1, 2, 1)


def test_convert_counts_null_tokens_and_writes_null(cv):
    rows, report = cv.convert(two_model(cv, a=[record(0, ct=-3), record(1)], b=[record(0), record(1)]), pool=POOL2)
    assert report["tasks"]["b"]["null_tokens"] == 1
    assert [r["output_tokens"] for r in rows if r["item"] == "b|0" and r["model"] == "openai/gpt-5"] == [None]


def test_convert_drops_subset_benchmarks(cv):
    ex = two_model(cv, bench="arenahard", split="") + two_model(cv, bench="arenahard_math", split="")
    rows, report = cv.convert(ex, pool=POOL2)
    assert list(report["tasks"]) == ["arenahard"] and {r["task"] for r in rows} == {"arenahard"}
    assert report["dropped_benchmarks"] == {"arenahard_math": "subset of arenahard"}


def test_convert_chooses_the_split_every_pool_model_has(cv):
    ex = two_model(cv, bench="hle", split="test") + [ext(cv, "hle", "subset_500", "gpt-5", [record(0)])]
    rows, report = cv.convert(ex, pool=POOL2)
    assert report["tasks"]["hle"]["split"] == "test" and report["rows"] == 4


def test_convert_drops_a_benchmark_no_split_completes(cv):
    ex = two_model(cv, bench="b") + [ext(cv, "tau2", "test", "gpt-5", [record(0)]),
                                     ext(cv, "tau2", "v2", "gemini-2.5-pro", [record(0)])]
    rows, report = cv.convert(ex, pool=POOL2)
    assert list(report["tasks"]) == ["b"]
    assert report["dropped_benchmarks"] == {"tau2": "no split holds every pool model"}
    assert report["lacking"] == {"tau2": {"test": ["google/gemini-2.5-pro"], "v2": ["openai/gpt-5"]}}


def test_convert_refuses_two_complete_splits(cv):
    with pytest.raises(ValueError, match="splits"):
        cv.convert(two_model(cv, split="a") + two_model(cv, split="b"), pool=POOL2)


def test_convert_ignores_models_outside_the_pool(cv):
    ex = two_model(cv) + [ext(cv, "b", "test", "claude-sonnet-4", [record(5)]),
                          ext(cv, "only", "test", "claude-sonnet-4", [record(0)])]
    rows, report = cv.convert(ex, pool=POOL2)
    assert report["rows"] == 4 and list(report["tasks"]) == ["b"] and report["dropped_benchmarks"] == {}


def test_convert_does_not_depend_on_order_and_does_not_modify_input(cv):
    ex = two_model(cv) + two_model(cv, bench="c")
    before = copy.deepcopy(ex)
    rows1, rep1 = cv.convert(ex, pool=POOL2)
    rows2, rep2 = cv.convert(list(reversed(ex)), pool=POOL2)
    assert ex == before and rows1 == rows2 and rep1 == rep2
    assert [r["task"] for r in rows1] == ["b"] * 4 + ["c"] * 4


def test_convert_sorts_items_as_strings(cv):
    recs = [record(i) for i in (2, 10, 1)]
    rows, _ = cv.convert(two_model(cv, a=recs, b=copy.deepcopy(recs)), pool=POOL2)
    assert [r["item"] for r in rows][::2] == ["b|1", "b|10", "b|2"]


@pytest.mark.parametrize("pool", [[], (), "openai/gpt-5", ["a", "a"], ["a", ""], [None], 5])
def test_convert_refuses_bad_pools(cv, pool):
    with pytest.raises(ValueError):
        cv.convert(two_model(cv), pool=pool)


@pytest.mark.parametrize("extracts", [[], (), None, "x"])
def test_convert_refuses_bad_extracts(cv, extracts):
    with pytest.raises(ValueError):
        cv.convert(extracts, pool=POOL2)


def test_convert_refuses_a_repeated_extract(cv):
    with pytest.raises(ValueError, match="two files"):
        cv.convert(two_model(cv) + two_model(cv)[:1], pool=POOL2)


def test_convert_refuses_when_no_row_is_kept(cv):
    with pytest.raises(ValueError):
        cv.convert(two_model(cv, a=[record(0)], b=[record(1)]), pool=POOL2)


def test_convert_default_pool_is_the_13(cv):
    ex = [ext(cv, "b", "test", f, [record(0)]) for f in POOL_IDS]
    rows, report = cv.convert(ex)
    assert report["models"] == sorted(POOL_IDS.values()) and report["rows"] == 13


def test_rows_feed_the_evaluator(cv):
    a = [record(i, score=1.0 if i % 4 else 0.0, cost=0.02) for i in range(80)]
    b = [record(i, score=1.0 if i % 2 else 0.0, cost=0.01) for i in range(80)]
    rows, _ = cv.convert(two_model(cv, a=a, b=b), pool=POOL2)
    outcomes = outcomes_from_rows(rows)
    assert len(outcomes) == 160
    result = evaluate(outcomes, bars=[0.5], seeds=range(2))
    assert result["config"]["bars"] == [0.5]


# --- read_archive ------------------------------------------------------------------------

def make_tar(path, members):
    with tarfile.open(path, "w:gz") as tar:
        for name, data in members:
            if data is None:
                info = tarfile.TarInfo(name)
                info.type = tarfile.DIRTYPE
                tar.addfile(info)
                continue
            info = tarfile.TarInfo(name)
            info.size = len(data)
            tar.addfile(info, io.BytesIO(data))
    return path


def jbytes(records):
    return json.dumps(doc(records)).encode()


def test_read_archive_reads_pool_members_in_order_and_skips_the_rest(cv, tmp_path):
    path = make_tar(tmp_path / "a.tar.gz", [
        ("bench-release", None),
        ("bench-release/hle/test/gpt-5/f.json", jbytes([record(0)])),
        ("bench-release/hle/test/Qwen3-8B/f.json", b"not json, never parsed"),
        ("bench-release/hle/test/gpt-5/notes.txt", b"not a result"),
        ("bench-release/arenahard/gemini-2.5-pro/f.json", jbytes([record(3)])),
    ])
    out = cv.read_archive(path)
    assert [(e["benchmark"], e["split"], e["model"]) for e in out] == [
        ("hle", "test", "openai/gpt-5"), ("arenahard", "", "google/gemini-2.5-pro")]
    assert not any(p.name != "a.tar.gz" for p in tmp_path.iterdir())


def test_read_archive_folders_argument(cv, tmp_path):
    path = make_tar(tmp_path / "a.tar.gz", [("bench-release/hle/test/gpt-5/f.json", jbytes([record(0)])),
                                            ("bench-release/hle/test/glm-4.6/f.json", jbytes([record(0)]))])
    assert [e["model"] for e in cv.read_archive(path, folders=("glm-4.6",))] == ["z-ai/glm-4.6"]


@pytest.mark.parametrize("data", [b"{not json", b"\xff\xfe", b"[" * 100000])
def test_read_archive_names_a_bad_pool_member(cv, tmp_path, data):
    path = make_tar(tmp_path / "a.tar.gz", [("bench-release/hle/test/gpt-5/f.json", data)])
    with pytest.raises(ValueError, match="bench-release/hle/test/gpt-5/f.json"):
        cv.read_archive(path)


def test_read_archive_refuses_a_file_that_is_not_a_gzip_tarball(cv, tmp_path):
    path = tmp_path / "x.tar.gz"
    path.write_bytes(b"plain bytes")
    with pytest.raises(ValueError, match="x.tar.gz"):
        cv.read_archive(path)


# --- fetch and verify --------------------------------------------------------------------

def pin(cv, monkeypatch, data):
    monkeypatch.setattr(cv, "SIZE", len(data))
    monkeypatch.setattr(cv, "SHA256", hashlib.sha256(data).hexdigest())


def test_fetch_keeps_a_verified_file_and_downloads_nothing(cv, tmp_path, monkeypatch):
    (tmp_path / "bench-release.tar.gz").write_bytes(b"abc")
    pin(cv, monkeypatch, b"abc")
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded"))
    assert cv.fetch(tmp_path) == tmp_path / "bench-release.tar.gz"


def test_fetch_refuses_a_bad_cached_file_and_leaves_it(cv, tmp_path, monkeypatch):
    (tmp_path / "bench-release.tar.gz").write_bytes(b"abd")
    pin(cv, monkeypatch, b"abc")
    with pytest.raises(ValueError, match="sha256"):
        cv.fetch(tmp_path)
    assert (tmp_path / "bench-release.tar.gz").read_bytes() == b"abd"


def test_fetch_downloads_verifies_and_renames(cv, tmp_path, monkeypatch):
    pin(cv, monkeypatch, b"abc")
    seen = []

    def fake(url, timeout):
        seen.append((url, timeout))
        return contextlib.closing(io.BytesIO(b"abc"))

    monkeypatch.setattr(urllib.request, "urlopen", fake)
    cache = tmp_path / "new"
    assert cv.fetch(cache) == cache / "bench-release.tar.gz"
    assert seen == [(cv.URL, 60)] and sorted(p.name for p in cache.iterdir()) == ["bench-release.tar.gz"]


def test_fetch_removes_the_part_file_on_a_mismatch(cv, tmp_path, monkeypatch):
    pin(cv, monkeypatch, b"abc")
    monkeypatch.setattr(urllib.request, "urlopen", lambda url, timeout: contextlib.closing(io.BytesIO(b"abd")))
    with pytest.raises(ValueError):
        cv.fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_fetch_turns_a_failed_download_into_oserror(cv, tmp_path, monkeypatch):
    def boom(url, timeout):
        raise TimeoutError("slow")

    monkeypatch.setattr(urllib.request, "urlopen", boom)
    with pytest.raises(OSError, match="bench-release.tar.gz: download failed"):
        cv.fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []


def test_verify_checks_size_first(cv, tmp_path):
    f = tmp_path / "f"
    f.write_bytes(b"abc")
    with pytest.raises(ValueError, match="size 3, expected 4"):
        cv.verify(f, 4, "0" * 64)


# --- CLI ---------------------------------------------------------------------------------

@pytest.mark.parametrize("out", ["", ".", "/", "dir/"])
def test_main_refuses_a_bad_out_before_fetching(cv, monkeypatch, capsys, out):
    monkeypatch.setattr(cv, "fetch", lambda *a: pytest.fail("fetched"))
    assert cv.main(["--out", out]) == 2
    assert capsys.readouterr().err.startswith("error: --out must end in a file name")


def test_main_writes_rows_and_prints_the_report(cv, tmp_path, monkeypatch, capsys):
    members = [(f"bench-release/b/test/{f}/x.json", jbytes([record(0), record(1, score=0.0)])) for f in POOL_IDS]
    path = make_tar(tmp_path / "bench-release.tar.gz", members)
    monkeypatch.setattr(cv, "fetch", lambda cache=None: path)
    out = tmp_path / "rows.jsonl"
    assert cv.main(["--out", str(out)]) == 0
    report = json.loads(capsys.readouterr().out)
    lines = out.read_text().splitlines()
    assert report["rows"] == len(lines) == 26 and not (tmp_path / "rows.jsonl.part").exists()
    assert list(json.loads(lines[0])) == ROW_KEYS


def test_main_reports_one_error_line_and_leaves_no_part(cv, tmp_path, monkeypatch, capsys):
    path = make_tar(tmp_path / "bench-release.tar.gz", [("bench-release/b/test/gpt-5/x.json", b"{bad\nline")])
    monkeypatch.setattr(cv, "fetch", lambda cache=None: path)
    out = tmp_path / "rows.jsonl"
    (tmp_path / "rows.jsonl.part").write_text("stale")
    assert cv.main(["--out", str(out)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ") and err.count("\n") == 1
    assert not out.exists() and not (tmp_path / "rows.jsonl.part").exists()


# --- the pinned file, only when cached ---------------------------------------------------

@pytest.fixture(scope="module")
def pinned_run(tmp_path_factory):
    module = load_cv()
    if not (module.default_cache_dir() / module.FILE).is_file():
        pytest.skip("the pinned LLMRouterBench file is not in the default cache")
    out = tmp_path_factory.mktemp("lrb") / "rows.jsonl"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = module.main(["--out", str(out)])
    return code, json.loads(buf.getvalue()) if code == 0 else None, out


def test_pinned_file_default_output(pinned_run):
    code, report, out = pinned_run
    assert code == 0
    items = {"aime": ("hybrid", 60), "arc-agi": ("v1", 400), "arenahard": ("", 749), "gpqa": ("test", 198),
             "hle": ("test", 2157), "livecodebench": ("test", 1055), "livemathbench": ("test", 121),
             "mmlupro": ("test_3000", 3000), "simpleqa": ("test", 4326)}
    assert {t: (v["split"], v["items"]) for t, v in report["tasks"].items()} == items
    assert sum(v["items"] for v in report["tasks"].values()) == 12066 and report["rows"] == 156858
    assert {t: v["dropped_question_differs"] for t, v in report["tasks"].items() if v["dropped_question_differs"]} == {"arenahard": 1, "hle": 1}
    assert all(v["dropped_incomplete"] == v["dropped_unscored"] == 0 for v in report["tasks"].values())
    assert {t: v["half_scores"] for t, v in report["tasks"].items() if v["half_scores"]} == {"arenahard": 2144}
    assert {t: v["null_tokens"] for t, v in report["tasks"].items() if v["null_tokens"]} == {"hle": 5, "simpleqa": 5}
    assert report["dropped_benchmarks"] == {
        "arenahard_coding": "subset of arenahard", "arenahard_creative_writing": "subset of arenahard",
        "arenahard_math": "subset of arenahard", "humaneval": "no split holds every pool model",
        "swe-bench": "no split holds every pool model", "tau2": "no split holds every pool model"}
    assert report["lacking"]["swe-bench"] == {"verified": ["qwen/qwen3-235b-a22b-thinking-2507"]}
    assert report["lacking"]["tau2"] == {"test": ["openai/gpt-5-chat"]}
    assert set(POOL_IDS.values()) - set(report["lacking"]["humaneval"]["test"]) == {"openai/gpt-5-chat"}


def test_pinned_file_rows_hold_no_text(pinned_run):
    code, report, out = pinned_run
    with open(out, encoding="utf-8") as f:
        for n, line in enumerate(f):
            row = json.loads(line)
            assert list(row) == ROW_KEYS
            if n > 2000:
                break
    assert out.stat().st_size < 30_000_000
