"""Registry-pair converter contract (DESIGN 12.23, v1.431), written before the converter and kept as its tests.

The converter is a standard-library script outside the package (``evidence/registry-pair/convert.py``), so it is
loaded from its path by an autouse fixture. Every test uses small synthetic records or files in a temporary
folder, except one CLI run on the three pinned files, which runs only when all three are in the default cache
and skips otherwise (CI never downloads them).
"""

import ast
import contextlib
import copy
import hashlib
import importlib.util
import inspect
import io
import json
import random
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

pytestmark = pytest.mark.xfail(strict=True, raises=ModuleNotFoundError)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "registry-pair" / "convert.py"
DESIGN = ROOT / "DESIGN.md"
REVISION = "63336f25fc54597a8e161a7245613f91bd60177e"
FILES = {
    "pair.json": (2473, "4b4cc5f936fe8a8018b6845bfa9bd29b7d18ec428489d15ebab62554c4cd11b4"),
    "recordings/grades-calibration.json": (3777170, "2f47b9df61b131879f30b4ea36693a8ce8bc43e46afd17d7fbd5d7a93922e8ac"),
    "recordings/grades-final.json": (3742778, "8d66442ad94b5e846a856084adfaba7a2915bab6253008e93ed44348dc264a5f"),
}
LUNA, SOL = "openai/gpt-6-luna", "openai/gpt-6.1-sol"
IDS = {"cheap": LUNA, "strong": SOL}
RECORD_KEYS = ["task", "item", "family", "split", "model", "correct", "cost_usd", "valid"]
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd"]
TASK_KEYS = ["items", "calibration", "final", "invalid_cells"]
FAMILY_KEYS = ["families", "shared_families", "shared_items", "in_both_splits", "across_tasks"]
STDLIB = {"argparse", "hashlib", "json", "math", "os", "sys", "urllib", "pathlib"}


def load(path, name):
    if not path.is_file():
        raise ModuleNotFoundError(f"no script at {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def cv():
    return load(SCRIPT, "registry_pair_convert")


def pair(**over):
    out = {"format": "routerbench-openai-pair-v1",
           "arms": {"cheap": {"arm": "luna", "model": "gpt-6-luna"}, "strong": {"arm": "sol", "model": "gpt-6.1-sol"}},
           "prices_usd_per_million": {"gpt-6-luna": {"input": "0.10", "output": "0.50", "cached_input": "0.01"},
                                      "gpt-6.1-sol": {"input": "2", "output": "10", "cached_input": "0.10"}}}
    out.update(over)
    return out


def registry(luna=(0.1, 0.5), sol=(2, 10)):
    return {"version": "t", "models": [
        {"id": SOL, "family": "openai", "price_in": sol[0], "price_out": sol[1]},
        {"id": LUNA, "family": "openai", "price_in": luna[0], "price_out": luna[1]},
        {"id": "openai/gpt-6-astra", "family": "openai", "price_in": 10, "price_out": 50}]}


def row(item, split="calibration", dataset="bbh", task="date understanding", family=None,
        cheap=(1, 0.0001, True), strong=(1, 0.001, True)):
    out = {"id": item, "role": split, "dataset": dataset, "task": task, "family": family or f"fam-{item}",
           "cheap_record_sha256": "a" * 64, "strong_usage_sha256": "b" * 64}
    for arm, (correct, cost, valid) in (("cheap", cheap), ("strong", strong)):
        out.update({f"{arm}_correct": correct, f"{arm}_cost_usd": cost, f"{arm}_valid": valid})
    return out


def grades(split, rows):
    return {"format": "routerbench-paired-grades-v1", "split": split, "rows": rows}


def records(cv, split, rows):
    return cv.grade_rows(grades(split, rows), split, IDS)


def sample(cv):
    cal = records(cv, "calibration", [row("bbh:d:1", family="f1"), row("bbh:d:2", family="f1", cheap=(0, 0.0002, True)),
                                      row("mmlupro:test:3", dataset="mmlupro", task="computer science",
                                          strong=(0, 0.002, False))])
    final = records(cv, "final", [row("bbh:d:4", "final", family="f2"), row("bbh:d:5", "final", family="f1")])
    return cal, final


# Constants and the source pin


def test_pins(cv):
    assert cv.DATASET == "superlinked/train-a-router-reasoning"
    assert cv.REVISION == REVISION
    assert cv.LICENCE == "mixed-mit-and-apache-2.0"
    assert cv.FILES == FILES and list(cv.FILES) == sorted(FILES)


def test_files_are_the_research_scripts(cv):
    research = load(ROOT / "research" / "registry_pair.py", "registry_pair_research")
    assert cv.FILES == research.FILES and cv.REVISION == research.REVISION
    assert cv.default_cache_dir() == research.default_cache_dir()


def test_url(cv):
    for name in FILES:
        assert cv.url(name) == f"https://huggingface.co/datasets/superlinked/train-a-router-reasoning/resolve/{REVISION}/{name}"
    with pytest.raises(ValueError):
        cv.url("recordings/grades-train.json")


def test_default_cache_dir(cv):
    assert cv.default_cache_dir() == Path.home() / ".cache" / "ai-model-routing-evidence" / "registry-pair"


def test_standard_library_only_and_no_package_import(cv):
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module.split(".")[0])
    assert names <= STDLIB and "model_routing" not in names


def test_registry_is_this_checkouts(cv):
    assert cv.REGISTRY == ROOT / "model_routing" / "data" / "models.json"


def test_check_out_is_the_shared_check(cv):
    other = load(ROOT / "evidence" / "llmrouterbench" / "convert.py", "registry_pair_llmrouterbench")
    assert inspect.getsource(cv._check_out) == inspect.getsource(other._check_out)


# check_pair


def test_check_pair_gives_the_registry_ids(cv):
    assert cv.check_pair(pair(), registry()) == {"cheap": LUNA, "strong": SOL}


def test_check_pair_takes_number_prices(cv):
    p = pair(prices_usd_per_million={"gpt-6-luna": {"input": 0.1, "output": 0.5}, "gpt-6.1-sol": {"input": 2, "output": 10.0}})
    assert cv.check_pair(p, registry()) == IDS


def test_check_pair_on_the_committed_registry(cv):
    reg = json.loads((ROOT / "model_routing" / "data" / "models.json").read_text(encoding="utf-8"))
    assert cv.check_pair(pair(), reg) == IDS


def test_check_pair_does_not_modify_its_input(cv):
    p, r = pair(), registry()
    before = copy.deepcopy((p, r))
    cv.check_pair(p, r)
    assert (p, r) == before


def _bad_pairs():
    arms = pair()["arms"]
    prices = pair()["prices_usd_per_million"]
    yield "pair format", pair(format="routerbench-openai-pair-v2"), registry()
    yield "pair format", [], registry()
    yield "registry:", pair(), {"models": "x"}
    yield "registry:", pair(), []
    yield "registry:", pair(), {"models": [1]}
    yield "pair:", pair(arms={"cheap": arms["cheap"]}), registry()
    yield "pair:", pair(arms={"cheap": {"arm": "luna"}, "strong": arms["strong"]}), registry()
    yield "pair:", pair(prices_usd_per_million={"gpt-6.1-sol": prices["gpt-6.1-sol"]}), registry()
    yield "pair:", pair(prices_usd_per_million={**prices, "gpt-6-luna": {"input": "0.10"}}), registry()
    yield "model not in the registry", pair(), {"models": [m for m in registry()["models"] if m["id"] != SOL]}
    for value in (True, None, "abc", "nan", "inf", "-1", -0.5, [1]):
        yield "pair price", pair(prices_usd_per_million={**prices, "gpt-6-luna": {"input": value, "output": "0.50"}}), registry()
    yield "price differs", pair(), registry(luna=(0.2, 0.5))
    yield "price differs", pair(), registry(sol=(2, 12))
    same = {"cheap": arms["strong"], "strong": arms["strong"]}
    yield "same model in both arms", pair(arms=same), registry()


@pytest.mark.parametrize("opening,p,r", list(_bad_pairs()))
def test_check_pair_refusals(cv, opening, p, r):
    with pytest.raises(ValueError) as exc:
        cv.check_pair(p, r)
    assert str(exc.value).startswith(opening)


# grade_rows


def test_grade_rows_records(cv):
    out = records(cv, "calibration", [row("bbh:d:1", cheap=(0, 1e-4, True), strong=(1, 2, True))])
    assert [list(r) for r in out] == [RECORD_KEYS, RECORD_KEYS]
    assert out[0] == {"task": "bbh/date_understanding", "item": "bbh:d:1", "family": "fam-bbh:d:1", "split": "calibration",
                      "model": LUNA, "correct": False, "cost_usd": 1e-4, "valid": True}
    assert out[1]["model"] == SOL and out[1]["correct"] is True
    assert type(out[1]["cost_usd"]) is float and out[1]["cost_usd"] == 2.0


def test_grade_rows_keeps_file_order_cheap_first(cv):
    out = records(cv, "final", [row("z", "final"), row("a", "final")])
    assert [(r["item"], r["model"]) for r in out] == [("z", LUNA), ("z", SOL), ("a", LUNA), ("a", SOL)]


def test_grade_rows_every_space_an_underscore(cv):
    out = records(cv, "final", [row("x", "final", dataset="mmlupro", task="computer  science one")])
    assert out[0]["task"] == "mmlupro/computer__science_one"


def test_grade_rows_invalid_miss_kept(cv):
    out = records(cv, "final", [row("x", "final", cheap=(0, 0.5, False))])
    assert (out[0]["correct"], out[0]["cost_usd"], out[0]["valid"]) == (False, 0.5, False)


def _bad_rows():
    yield "no rows", []
    yield "calibration row 0: not an object", [1]
    for key in ("id", "dataset", "task", "family"):
        for value in (None, "", 3):
            r = row("x")
            r[key] = value
            yield "", [r]
    yield "row role", [row("x", split="final")]
    yield "", [row("x", dataset="b/b")]
    for value in (True, False, 1.0, 2, -1, "1", None):
        yield "", [row("x", cheap=(value, 0.1, True))]
    for value in (True, -0.1, float("nan"), float("inf"), "0.1", None):
        yield "", [row("x", strong=(1, value, True))]
    for value in (1, None, "true"):
        yield "", [row("x", cheap=(0, 0.1, value))]
    yield "invalid cell scored 1", [row("x", strong=(1, 0.1, False))]


@pytest.mark.parametrize("opening,rows", list(_bad_rows()))
def test_grade_rows_refusals(cv, opening, rows):
    with pytest.raises(ValueError) as exc:
        records(cv, "calibration", rows)
    assert str(exc.value).startswith(opening)


@pytest.mark.parametrize("key,value", [("id", ""), ("dataset", None), ("task", 3), ("family", "")])
def test_grade_rows_text_message(cv, key, value):
    r = row("x")
    r[key] = value
    with pytest.raises(ValueError, match="must be a non-empty string"):
        records(cv, "calibration", [r])


@pytest.mark.parametrize("g", [
    {"format": "routerbench-paired-grades-v2", "split": "calibration", "rows": [row("x")]},
    {"format": "routerbench-paired-grades-v1", "split": "final", "rows": [row("x")]},
    [row("x")],
])
def test_grade_rows_format(cv, g):
    with pytest.raises(ValueError) as exc:
        cv.grade_rows(g, "calibration", IDS)
    assert str(exc.value).startswith("grades format")


# convert


def test_convert_rows(cv):
    rows, report = cv.convert(*sample(cv))
    assert all(list(r) == ROW_KEYS for r in rows)
    assert [(r["task"], r["item"], r["model"]) for r in rows] == sorted((r["task"], r["item"], r["model"]) for r in rows)
    assert len(rows) == 10 and report["rows"] == 10
    by = {(r["item"], r["model"]): r for r in rows}
    assert by["bbh:d:2", LUNA] == {"task": "bbh/date_understanding", "item": "bbh:d:2", "model": LUNA,
                                   "correct": False, "cost_usd": 0.0002}
    assert by["mmlupro:test:3", SOL]["correct"] is False and by["mmlupro:test:3", SOL]["cost_usd"] == 0.002


def test_convert_report(cv):
    _, report = cv.convert(*sample(cv))
    assert list(report) == ["models", "tasks", "families", "rows"]
    assert report["models"] == [LUNA, SOL]
    assert list(report["tasks"]) == ["bbh/date_understanding", "mmlupro/computer_science"]
    assert all(list(t) == TASK_KEYS for t in report["tasks"].values())
    assert report["tasks"]["bbh/date_understanding"] == {"items": 4, "calibration": 2, "final": 2, "invalid_cells": 0}
    assert report["tasks"]["mmlupro/computer_science"] == {"items": 1, "calibration": 1, "final": 0, "invalid_cells": 1}
    assert list(report["families"]) == FAMILY_KEYS
    assert report["families"] == {"families": 3, "shared_families": 1, "shared_items": 3, "in_both_splits": 1,
                                  "across_tasks": 0}


def test_convert_families_across_tasks(cv):
    cal = records(cv, "calibration", [row("a", family="f"), row("b", task="navigate", family="f"), row("c")])
    _, report = cv.convert(cal, records(cv, "final", [row("d", "final")]))
    assert report["families"] == {"families": 3, "shared_families": 1, "shared_items": 2, "in_both_splits": 0,
                                  "across_tasks": 1}


def test_convert_does_not_depend_on_order_or_modify_input(cv):
    cal, final = sample(cv)
    before = copy.deepcopy((cal, final))
    expected = cv.convert(cal, final)
    assert (cal, final) == before
    rng = random.Random(7)
    for _ in range(5):
        a, b = list(cal), list(final)
        rng.shuffle(a)
        rng.shuffle(b)
        assert cv.convert(tuple(a), b) == expected


def test_convert_rows_are_an_outcome_matrix(cv):
    cal = records(cv, "calibration", [row(f"c{i}", cheap=(int(i % 3 > 0), 1e-4, True)) for i in range(40)])
    final = records(cv, "final", [row(f"f{i}", "final", cheap=(int(i % 4 > 0), 1e-4, True)) for i in range(40)])
    rows, _ = cv.convert(cal, final)
    outcomes = outcomes_from_rows(rows)
    assert len(outcomes) == 160
    result = evaluate(outcomes, bars=[0.5], seeds=[0, 1], min_samples=10)
    assert result["tasks"] == {"bbh/date_understanding": {"items": 80, "models": [LUNA, SOL]}}


def _bad_converts(cv):
    cal, final = sample(cv)
    yield "calibration must be a non-empty list or tuple", [], final
    yield "calibration must be a non-empty list or tuple", None, final
    yield "final must be a non-empty list or tuple", cal, ()
    yield "final must be a non-empty list or tuple", cal, {"a": 1}
    moved = records(cv, "final", [row("bbh:d:1", "final", family="f1")])
    yield "item in both splits", cal, final + moved
    yield "repeated cell", cal + cal[:1], final
    other = copy.deepcopy(cal[1])
    other["task"] = "bbh/navigate"
    yield "item task differs", [cal[0], other] + cal[2:], final
    fam = copy.deepcopy(cal[1])
    fam["family"] = "f9"
    yield "item task differs", [cal[0], fam] + cal[2:], final
    yield "incomplete item", cal[1:], final


def test_convert_refusals(cv):
    cases = list(_bad_converts(cv))
    assert len(cases) == 9
    for opening, cal, final in cases:
        with pytest.raises(ValueError) as exc:
            cv.convert(cal, final)
        assert str(exc.value).startswith(opening), (opening, str(exc.value))


def test_convert_incomplete_item_names_the_model(cv):
    cal, final = sample(cv)
    with pytest.raises(ValueError) as exc:
        cv.convert(cal[1:], final)
    assert "'bbh:d:1'" in str(exc.value) and repr(LUNA) in str(exc.value)


# verify, fetch and read_json


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _pin(monkeypatch, cv, files):
    monkeypatch.setattr(cv, "FILES", {name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in files.items()})


FAKE = {"pair.json": b'{"a": 1}', "recordings/grades-calibration.json": b"[1]", "recordings/grades-final.json": b"[2]"}


def test_verify(cv, tmp_path):
    p = _write(tmp_path / "f", b"abc")
    cv.verify(p, 3, hashlib.sha256(b"abc").hexdigest())
    with pytest.raises(ValueError, match="size"):
        cv.verify(p, 4, hashlib.sha256(b"abc").hexdigest())
    with pytest.raises(ValueError, match="sha256"):
        cv.verify(p, 3, "0" * 64)


def test_fetch_present_files(cv, tmp_path, monkeypatch):
    _pin(monkeypatch, cv, FAKE)
    for name, data in FAKE.items():
        _write(tmp_path / name, data)
    monkeypatch.setattr(cv.urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded"))
    out = cv.fetch(tmp_path)
    assert list(out) == sorted(FAKE) and all(out[n] == tmp_path / n for n in FAKE)


def test_fetch_bad_present_file_left_in_place(cv, tmp_path, monkeypatch):
    _pin(monkeypatch, cv, FAKE)
    bad = _write(tmp_path / "pair.json", b'{"a": 2}')
    with pytest.raises(ValueError):
        cv.fetch(tmp_path)
    assert bad.read_bytes() == b'{"a": 2}'


def test_fetch_downloads_into_subfolders(cv, tmp_path, monkeypatch):
    _pin(monkeypatch, cv, FAKE)
    urls = []

    def opener(u, timeout):
        urls.append((u, timeout))
        return contextlib.closing(io.BytesIO(FAKE[u.rsplit(f"/{cv.REVISION}/", 1)[1]]))

    monkeypatch.setattr(cv.urllib.request, "urlopen", opener)
    out = cv.fetch(tmp_path / "cache")
    assert [u for u, _ in urls] == [cv.url(n) for n in sorted(FAKE)] and {t for _, t in urls} == {cv.TIMEOUT}
    assert all(out[n].read_bytes() == FAKE[n] for n in FAKE)
    assert not list((tmp_path / "cache").rglob("*.part"))


def test_fetch_retries_then_fails_and_removes_part(cv, tmp_path, monkeypatch):
    _pin(monkeypatch, cv, FAKE)
    calls = []

    def opener(u, timeout):
        calls.append(u)
        raise OSError("down")

    monkeypatch.setattr(cv.urllib.request, "urlopen", opener)
    with pytest.raises(OSError, match="pair.json: download failed"):
        cv.fetch(tmp_path)
    assert len(calls) == cv.ATTEMPTS == 3
    assert not list(tmp_path.rglob("*.part")) and not (tmp_path / "pair.json").exists()


def test_fetch_wrong_download_removed(cv, tmp_path, monkeypatch):
    _pin(monkeypatch, cv, FAKE)
    monkeypatch.setattr(cv.urllib.request, "urlopen", lambda u, timeout: contextlib.closing(io.BytesIO(b"x")))
    with pytest.raises(ValueError):
        cv.fetch(tmp_path)
    assert not list(tmp_path.rglob("*")) or not list(tmp_path.rglob("*.part"))
    assert not (tmp_path / "pair.json").exists()


@pytest.mark.parametrize("data", [b"{", b"\xff\xfe", b"[" * 100000])
def test_read_json_errors_name_the_file(cv, tmp_path, data):
    p = _write(tmp_path / "grades-final.json", data)
    with pytest.raises(ValueError) as exc:
        cv.read_json(p)
    assert str(exc.value).startswith("grades-final.json: invalid JSON")


def test_read_json_name(cv, tmp_path):
    p = _write(tmp_path / "x.json", b"{")
    with pytest.raises(ValueError, match="^pair.json: "):
        cv.read_json(p, "pair.json")
    assert cv.read_json(_write(tmp_path / "y.json", b'{"a": [1]}')) == {"a": [1]}


# CLI


def _cache(tmp_path, cal_rows, final_rows):
    cache = tmp_path / "cache"
    _write(cache / "pair.json", json.dumps(pair()).encode())
    _write(cache / "recordings" / "grades-calibration.json", json.dumps(grades("calibration", cal_rows)).encode())
    _write(cache / "recordings" / "grades-final.json", json.dumps(grades("final", final_rows)).encode())
    reg = _write(tmp_path / "models.json", json.dumps(registry()).encode())
    return {name: cache / name for name in sorted(FILES)}, reg


def _run(cv, argv, capsys):
    code = cv.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def test_cli_writes_rows_and_prints_report(cv, tmp_path, monkeypatch, capsys):
    paths, reg = _cache(tmp_path, [row("a"), row("b", family="fam-a")], [row("c", "final", cheap=(0, 0.3, False))])
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: paths)
    monkeypatch.setattr(cv, "REGISTRY", reg)
    out = tmp_path / "rows.jsonl"
    code, stdout, err = _run(cv, ["--out", str(out)], capsys)
    assert (code, err) == (0, "")
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 6 and all(list(r) == ROW_KEYS for r in rows)
    report = json.loads(stdout)
    assert report["tasks"] == {"bbh/date_understanding": {"items": 3, "calibration": 2, "final": 1, "invalid_cells": 1}}
    assert report["families"]["shared_items"] == 2 and stdout == json.dumps(report, indent=2) + "\n"
    assert not (tmp_path / "rows.jsonl.part").exists()


def test_cli_passes_cache(cv, tmp_path, monkeypatch, capsys):
    paths, reg = _cache(tmp_path, [row("a")], [row("c", "final")])
    seen = []
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: seen.append(cache_dir) or paths)
    monkeypatch.setattr(cv, "REGISTRY", reg)
    assert _run(cv, ["--out", str(tmp_path / "o.jsonl"), "--cache", "somewhere"], capsys)[0] == 0
    assert seen == ["somewhere"]


def test_cli_price_mismatch_writes_nothing(cv, tmp_path, monkeypatch, capsys):
    paths, _ = _cache(tmp_path, [row("a")], [row("c", "final")])
    reg = _write(tmp_path / "other.json", json.dumps(registry(sol=(3, 10))).encode())
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: paths)
    monkeypatch.setattr(cv, "REGISTRY", reg)
    out = tmp_path / "o.jsonl"
    code, stdout, err = _run(cv, ["--out", str(out)], capsys)
    assert code == 2 and stdout == "" and err.startswith("error: price differs") and err.count("\n") == 1
    assert not out.exists() and not (tmp_path / "o.jsonl.part").exists()


def test_cli_error_escapes_newlines(cv, tmp_path, monkeypatch, capsys):
    def boom(cache_dir=None):
        raise OSError("a\nb\rc")

    monkeypatch.setattr(cv, "fetch", boom)
    code, _, err = _run(cv, ["--out", str(tmp_path / "o.jsonl")], capsys)
    assert code == 2 and err == "error: a\\nb\\rc\n"


@pytest.mark.parametrize("make", [
    lambda t: str(t) + "/",
    lambda t: str(t / "missing" / "o.jsonl"),
    lambda t: str(t / "d"),
    lambda t: str(t / "e"),
])
def test_cli_bad_out_downloads_nothing(cv, tmp_path, monkeypatch, capsys, make):
    (tmp_path / "d").mkdir()
    (tmp_path / "e.part").mkdir()
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: pytest.fail("fetched"))
    code, stdout, err = _run(cv, ["--out", make(tmp_path)], capsys)
    assert code == 2 and stdout == "" and err.startswith("error: --out")


def test_cli_needs_out(cv, monkeypatch, capsys):
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: pytest.fail("fetched"))
    code, _, err = _run(cv, [], capsys)
    assert code == 2 and err.startswith("error: ")


def test_cli_print_failure_leaves_no_out(cv, tmp_path, monkeypatch, capsys):
    paths, reg = _cache(tmp_path, [row("a")], [row("c", "final")])
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: paths)
    monkeypatch.setattr(cv, "REGISTRY", reg)

    def broken(text):
        raise OSError("closed")

    monkeypatch.setattr(cv, "print_report", broken)
    out = tmp_path / "o.jsonl"
    assert _run(cv, ["--out", str(out)], capsys)[0] == 2
    assert not out.exists() and not (tmp_path / "o.jsonl.part").exists()


# The spec


def test_design_specifies_the_converter_and_its_split():
    text = DESIGN.read_text(encoding="utf-8")
    start = text.index("### 12.23 Public evidence: the registry-pair converter (`evidence/registry-pair/convert.py`, v1.431)")
    body = text[start:text.index("\n## 13. ", start)]
    for phrase in ("12.2 draws its halves by seed", "808 of the 6,099 items", "the family-held check",
                   "A fixed-split option for 12.3 would be a package change", f"`REVISION = \"{REVISION}\"`",
                   "`LICENCE = \"mixed-mit-and-apache-2.0\"`", "12,198 rows, 1,630,121 bytes"):
        assert phrase in body, phrase


# The pinned files (skipped unless all three are in the default cache)


@pytest.fixture(scope="module")
def pinned(tmp_path_factory):
    cvm = load(SCRIPT, "registry_pair_convert_pinned")
    cache = cvm.default_cache_dir()
    if not all((cache / name).is_file() for name in FILES):
        pytest.skip("the pinned files are not in the default cache")
    out = tmp_path_factory.mktemp("registry-pair") / "rows.jsonl"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cvm.main(["--out", str(out)])
    return code, json.loads(buf.getvalue()) if code == 0 else None, out


def test_pinned_files_default_output(pinned):
    code, report, out = pinned
    assert code == 0
    assert report["models"] == [LUNA, SOL] and report["rows"] == 12198
    tasks = report["tasks"]
    assert len(tasks) == 31 and sum(t["items"] for t in tasks.values()) == 6099
    assert (sum(t["calibration"] for t in tasks.values()), sum(t["final"] for t in tasks.values())) == (3056, 3043)
    assert {k: t["invalid_cells"] for k, t in tasks.items() if t["invalid_cells"]} == {"korbench/cipher": 1}
    assert tasks["korbench/logic"]["items"] == 20
    assert sorted({k.split("/")[0] for k in tasks}) == ["bbh", "korbench", "mmlupro"]
    assert report["families"] == {"families": 5567, "shared_families": 276, "shared_items": 808,
                                  "in_both_splits": 0, "across_tasks": 0}
    assert out.stat().st_size == 1630121
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 12198 and not any(r["cost_usd"] == 0.0 for r in rows)
