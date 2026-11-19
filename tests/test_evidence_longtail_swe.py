"""Longtail-SWE converter contract (DESIGN 12.25, v1.478), written before the converter and kept as its tests.

The converter is a script outside the package (``evidence/longtail-swe/convert.py``), standard library only but
for ``pyarrow``, which only ``read_rows`` imports, so it is loaded from its path by an autouse fixture. Every test
uses small synthetic rows, files in a temporary folder or committed files, except one CLI run on the four pinned
files, which runs
only when ``pyarrow`` is installed and all four are in the default cache, and skips otherwise (CI never downloads
them).
"""

import ast
import contextlib
import copy
import hashlib
import importlib.util
import inspect
import io
import json
import math
import random
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "longtail-swe" / "convert.py"
DESIGN = ROOT / "DESIGN.md"
REVISION = "dfd6075c56b7841b9c254cc70a57e39c1df0076c"
FILES = {
    "data/swelike__claude-opus-5.5-high.parquet":
        (36213846, "45b9323ae1b33c7301e60a266594202e6f6684de4386c9d50356783b113bea91"),
    "data/swelike__gpt-5.6-luna-xhigh.parquet":
        (94695456, "144ac5b635135d0df37eae6edf2d40148e58f8832d8d59b492a865a98dd99093"),
    "data/swelike__gpt-5.6-sol-high.parquet":
        (56147793, "af2e3bcaf8625d131d467cb4a55164fd63f561d7ee6125db6217cfe603511b57"),
    "data/swelike__gpt-6.1-sol-high.parquet":
        (49548306, "52441cc627aa6688150be052044549b0fe6b2e1215f676a254602919f4bc2fff"),
}
COLUMNS = ("instance_id", "programming_language", "canonical_model", "run_index", "resolved",
           "initial_statement_matches_release", "trajectory")
OPUS, LUNA, SOL56, SOL61 = "anthropic/claude-opus-5.5", "openai/gpt-5.6-luna", "openai/gpt-5.6-sol", "openai/gpt-6.1-sol"
PRICES = {OPUS: (4, 20), LUNA: (0.2, 1.2), SOL56: (4, 20), SOL61: (2, 10)}
RECORD_KEYS = ["task", "item", "language", "run", "model", "correct", "scored", "statement_matches", "cost_usd"]
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd"]
REPORT_KEYS = ["models", "run", "tasks", "languages", "dropped_statement", "resolved", "unscored", "rows"]
STDLIB = {"argparse", "hashlib", "json", "math", "os", "re", "sys", "urllib", "pathlib"}
TASK = "issue_resolution"


def load(path, name):
    if not path.is_file():
        raise ModuleNotFoundError(f"no script at {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def cv():
    return load(SCRIPT, "longtail_swe_convert")


def registry(**over):
    models = [{"id": mid, "family": mid.split("/")[0], "price_in": p[0], "price_out": p[1]} for mid, p in PRICES.items()]
    models.append({"id": "openai/gpt-6-astra", "family": "openai", "price_in": 10, "price_out": 50})
    for mid, changes in over.items():
        row = next(m for m in models if m["id"] == mid)
        row.update(changes)
    return {"version": "t", "models": models}


def traj(input=1_000_000, output=100_000, total=None, cached=800_000, creation=None, **tokens):
    record = {"input": input, "cached_input": cached, "cache_creation": creation, "output": output,
              "reasoning": 0, "total": input + output if total is None else total,
              "source": "harness_reported", "note": "Token counter semantics are provider- and harness-specific."}
    record.update(tokens)
    return json.dumps({"steps": [{"role": "user", "content": "never read"}],
                       "usage": {"cost_usd": None, "tokens": record}})


def prow(item="org__repo-1", language="Julia", canonical="gpt-6.1-sol", run=0, resolved=1, matches=True, **tok):
    return {"instance_id": item, "programming_language": language, "canonical_model": canonical, "run_index": run,
            "resolved": resolved, "initial_statement_matches_release": matches, "trajectory": traj(**tok)}


def records(cv, rows, reg=None):
    return cv.run_records(rows, registry() if reg is None else reg)


def sample(cv, items=("a__x-1", "b__y-2", "c__z-3"), runs=(0, 1), models=("gpt-6.1-sol", "gpt-5.6-luna")):
    out = []
    for canonical in models:
        rows = [prow(item, "Lua" if item.startswith("a") else "R", canonical, run, resolved=(i + run) % 2)
                for run in runs for i, item in enumerate(items)]
        out += records(cv, rows)
    return out


# The pins


def test_pins(cv):
    assert (cv.DATASET, cv.REVISION, cv.LICENCE) == ("nebius/Longtail-SWE-trajectories", REVISION, "cc-by-4.0")
    assert cv.FILES == FILES and list(cv.FILES) == sorted(FILES)
    assert tuple(cv.COLUMNS) == COLUMNS


def test_files_total_is_stated(cv):
    total = sum(size for size, _ in cv.FILES.values())
    body = DESIGN.read_text(encoding="utf-8").split("### 12.25 ", 1)[1].split("\n## 13. ", 1)[0]
    assert total == 236605401 and f"{total:,} bytes in all" in body
    assert f"so their {837610490 - total:,} bytes are not downloaded" in body


def test_url(cv):
    name = "data/swelike__gpt-6.1-sol-high.parquet"
    assert cv.url(name) == f"https://huggingface.co/datasets/nebius/Longtail-SWE-trajectories/resolve/{REVISION}/{name}"
    with pytest.raises(ValueError):
        cv.url("data/swelike__kimi-k3-max.parquet")


def test_default_cache_dir(cv):
    assert cv.default_cache_dir() == Path.home() / ".cache" / "ai-model-routing-evidence" / "longtail-swe"


def test_standard_library_only_but_pyarrow_in_read_rows(cv):
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    top, inside = set(), {}
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            for sub in ast.walk(node):
                if isinstance(sub, (ast.Import, ast.ImportFrom)):
                    names = [a.name for a in sub.names] if isinstance(sub, ast.Import) else [sub.module]
                    inside.setdefault(node.name, set()).update(n.split(".")[0] for n in names)
    for node in tree.body:
        if isinstance(node, ast.Import):
            top |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            top.add(node.module.split(".")[0])
    assert top <= STDLIB and "model_routing" not in top
    assert inside == {"read_rows": {"pyarrow"}}


def test_registry_is_this_checkouts(cv):
    assert cv.REGISTRY == ROOT / "model_routing" / "data" / "models.json"


def test_check_out_is_the_shared_check(cv):
    other = load(ROOT / "evidence" / "llmrouterbench" / "convert.py", "longtail_swe_llmrouterbench")
    assert inspect.getsource(cv._check_out) == inspect.getsource(other._check_out)


# model_id


@pytest.mark.parametrize("canonical, expected", [
    ("claude-opus-5.5", OPUS), ("gpt-6.1-sol", SOL61), ("gpt-5.6-luna", LUNA), ("claude-x", "anthropic/claude-x"),
])
def test_model_id(cv, canonical, expected):
    assert cv.model_id(canonical) == expected


@pytest.mark.parametrize("canonical", [
    "kimi-k3", "deepseek-v4.1-flash", "qwen3.8-27b", "Claude-opus-5.5", "gpt-", "claude-opus 5.5", "gpt-6.1-sol\n",
    "openai/gpt-6.1-sol", "", None, 5,
])
def test_model_id_refusals(cv, canonical):
    with pytest.raises(ValueError) as exc:
        cv.model_id(canonical)
    assert str(exc.value).startswith("model name")


# tokens


def test_tokens(cv):
    assert cv.tokens(traj(1234, 56, cached=1000)) == (1234, 56)
    assert cv.tokens(traj(10, 2, cached=None, creation=None)) == (10, 2)
    assert cv.tokens(traj(10, 2, cached=4, creation=6)) == (10, 2)
    assert type(cv.tokens(traj(10, 2, cached=0))) is tuple


@pytest.mark.parametrize("opening, trajectory", [
    ("trajectory", 5),
    ("trajectory", None),
    ("trajectory", "{"),
    ("trajectory", "[1]"),
    ("no tokens", "{}"),
    ("no tokens", '{"usage": 1}'),
    ("no tokens", '{"usage": {}}'),
    ("no tokens", '{"usage": {"tokens": []}}'),
    ("token count", traj(input=-1, total=99_999)),
    ("token count", traj(input=True, total=100_001)),
    ("token count", traj(output=1.0, total=1_000_001)),
    ("token count", traj(output=None, total=1_000_000)),
    ("token count", json.dumps({"usage": {"tokens": {"input": 1, "output": 1, "total": None}}})),
    ("token count", traj(total=True)),
    ("token total", traj(total=1_100_001)),
    ("token total", traj(total=1_000_000)),
    ("cached tokens", traj(cached=-1)),
    ("cached tokens", traj(cached=True)),
    ("cached tokens", traj(creation="7")),
    ("cached tokens", traj(cached=900_000, creation=100_001)),
    ("cached tokens", traj(cached=1_000_001)),
])
def test_tokens_refusals(cv, opening, trajectory):
    with pytest.raises(ValueError) as exc:
        cv.tokens(trajectory)
    assert str(exc.value).startswith(opening)


def test_tokens_cached_at_the_input_is_taken(cv):
    assert cv.tokens(traj(cached=900_000, creation=100_000)) == (1_000_000, 100_000)


# run_records


def test_run_records(cv):
    got = records(cv, [prow("o__r-1", "F#", "gpt-6.1-sol", 2, 1), prow("o__r-2", "Lua", "claude-opus-5.5", 0, None),
                       prow("o__r-3", "R", "gpt-5.6-luna", 1, 0, False, input=10, output=5, cached=None)])
    assert all(list(r) == RECORD_KEYS for r in got)
    assert [(r["task"], r["item"], r["language"], r["run"], r["model"], r["correct"], r["scored"],
             r["statement_matches"]) for r in got] == [
        (TASK, "o__r-1", "F#", 2, SOL61, True, True, True),
        (TASK, "o__r-2", "Lua", 0, OPUS, False, False, True),
        (TASK, "o__r-3", "R", 1, LUNA, False, True, False)]
    # (1,000,000 * 2 + 100,000 * 10) / 1e6; (1,000,000 * 4 + 100,000 * 20) / 1e6; (10 * 0.2 + 5 * 1.2) / 1e6
    assert [r["cost_usd"] for r in got] == [3.0, 6.0, pytest.approx(8e-6, rel=1e-12)]


def test_run_records_charge_every_input_token_at_price_in(cv):
    # The cached part is inside `input` and has no price of its own in the registry (12.25 v1.478 Choices).
    (a,), (b,) = records(cv, [prow(cached=0)]), records(cv, [prow(cached=1_000_000)])
    assert a["cost_usd"] == b["cost_usd"] == 3.0


def test_run_records_does_not_modify_its_input(cv):
    rows, reg = [prow(), prow("o__r-2", resolved=0)], registry()
    before = copy.deepcopy((rows, reg))
    cv.run_records(rows, reg)
    assert (rows, reg) == before


def _bad_rows():
    def change(**over):
        out = prow()
        out.update(over)
        return out

    return [
        ("not an object", 5),
        ("instance_id", change(instance_id="")),
        ("instance_id", change(instance_id=3)),
        ("programming_language", change(programming_language=None)),
        ("programming_language", change(programming_language="")),
        ("run_index", change(run_index=-1)),
        ("run_index", change(run_index=True)),
        ("run_index", change(run_index=0.0)),
        ("resolved", change(resolved=2)),
        ("resolved", change(resolved=True)),
        ("resolved", change(resolved=1.0)),
        ("initial_statement_matches_release", change(initial_statement_matches_release=None)),
        ("initial_statement_matches_release", change(initial_statement_matches_release=1)),
        ("model name", change(canonical_model="kimi-k3")),
        ("model not in the registry", change(canonical_model="gpt-9-nova")),
        ("trajectory", change(trajectory="{")),
        ("token total", change(trajectory=traj(total=7))),
        ("instance_id", change(instance_id="", resolved=2)),
    ]


@pytest.mark.parametrize("case, bad", _bad_rows())
def test_run_records_refusals(cv, case, bad):
    with pytest.raises(ValueError) as exc:
        records(cv, [prow(), bad])
    msg = str(exc.value)
    assert msg.startswith("row 1") and case in msg and "row 0" not in msg


@pytest.mark.parametrize("case, over", [
    ("price tiers", {"price_tiers": [{"above": 200_000, "price_in": 4, "price_out": 15}]}),
    ("registry price", {"price_in": -1}),
    ("registry price", {"price_in": True}),
    ("registry price", {"price_out": math.inf}),
    ("registry price", {"price_out": "10"}),
])
def test_run_records_registry_refusals(cv, case, over):
    with pytest.raises(ValueError) as exc:
        records(cv, [prow()], registry(**{SOL61: over}))
    msg = str(exc.value)
    assert msg.startswith("row 0") and case in msg


def test_run_records_on_the_committed_registry(cv):
    reg = json.loads((ROOT / "model_routing" / "data" / "models.json").read_text(encoding="utf-8"))
    got = cv.run_records([prow(canonical=c, input=1_000_000, output=1_000_000, cached=0)
                          for c in ("claude-opus-5.5", "gpt-5.6-luna", "gpt-5.6-sol", "gpt-6.1-sol")], reg)
    by_id = {m["id"]: m for m in reg["models"]}
    assert [r["cost_usd"] for r in got] == [by_id[m]["price_in"] + by_id[m]["price_out"]
                                            for m in (OPUS, LUNA, SOL56, SOL61)]


# convert


def test_convert_rows(cv):
    rows, report = cv.convert(sample(cv))
    assert all(list(r) == ROW_KEYS for r in rows) and len(rows) == 6 == report["rows"]
    assert [(r["item"], r["model"]) for r in rows] == sorted((r["item"], r["model"]) for r in rows)
    assert {r["task"] for r in rows} == {TASK}
    # run 0 alone: resolved is (i + 0) % 2, so b__y-2 is correct for both models, a__x-1 and c__z-3 are not
    assert [r["correct"] for r in rows] == [False, False, True, True, False, False]


def test_convert_report(cv):
    _, report = cv.convert(sample(cv))
    assert list(report) == REPORT_KEYS
    assert report["models"] == [LUNA, SOL61] and report["run"] == 0
    assert report["tasks"] == {TASK: {"items": 3}}
    assert report["languages"] == {"Lua": 1, "R": 2} and list(report["languages"]) == ["Lua", "R"]
    assert report["dropped_statement"] == [] and report["resolved"] == {LUNA: 1, SOL61: 1}
    assert report["unscored"] == {LUNA: [], SOL61: []}


def test_convert_other_run(cv):
    rows, report = cv.convert(sample(cv), run=1)
    assert report["run"] == 1 and report["resolved"] == {LUNA: 2, SOL61: 2}
    assert [r["correct"] for r in rows] == [True, True, False, False, True, True]


def test_convert_drops_a_changed_statement_for_every_model(cv):
    recs = sample(cv)
    for r in recs:
        if (r["item"], r["model"], r["run"]) == ("c__z-3", LUNA, 0):
            r["statement_matches"] = False
        if (r["item"], r["run"]) == ("a__x-1", 1):  # another run's flag does not drop run 0's item
            r["statement_matches"] = False
    rows, report = cv.convert(recs)
    assert sorted({r["item"] for r in rows}) == ["a__x-1", "b__y-2"] and report["dropped_statement"] == ["c__z-3"]
    assert report["tasks"] == {TASK: {"items": 2}} and report["languages"] == {"Lua": 1, "R": 1}
    assert cv.convert(recs, run=1)[1]["dropped_statement"] == ["a__x-1"]


def test_convert_unscored_is_a_miss_that_keeps_its_charge(cv):
    recs = sample(cv)
    target = next(r for r in recs if (r["item"], r["model"], r["run"]) == ("b__y-2", SOL61, 0))
    target.update(correct=False, scored=False)
    rows, report = cv.convert(recs)
    cell = next(r for r in rows if (r["item"], r["model"]) == ("b__y-2", SOL61))
    assert cell["correct"] is False and cell["cost_usd"] == target["cost_usd"] == 3.0
    assert report["unscored"] == {LUNA: [], SOL61: ["b__y-2"]} and report["resolved"] == {LUNA: 1, SOL61: 0}


def test_convert_does_not_depend_on_order_or_modify_input(cv):
    recs = sample(cv, items=tuple(f"i__{n}-{n}" for n in range(12)))
    before = copy.deepcopy(recs)
    shuffled = recs[:]
    random.Random(7).shuffle(shuffled)
    assert cv.convert(tuple(shuffled)) == cv.convert(recs)
    assert recs == before


def test_convert_rows_are_an_outcome_matrix(cv):
    recs = sample(cv, items=tuple(f"i__{n}-{n}" for n in range(40)), runs=(0,))
    rows, _ = cv.convert(recs)
    outcomes = outcomes_from_rows(rows)
    assert len(outcomes) == 80
    result = evaluate(outcomes, bars=[0.5], seeds=[0, 1], min_samples=10)
    assert result["tasks"] == {TASK: {"items": 40, "models": [LUNA, SOL61]}}


def test_convert_refusals(cv):
    recs = sample(cv)
    cases = [
        ("records must be a non-empty list or tuple", [], 0),
        ("records must be a non-empty list or tuple", "abc", 0),
        ("records must be a non-empty list or tuple", None, 0),
        ("run must be an int >= 0", recs, -1),
        ("run must be an int >= 0", recs, True),
        ("run must be an int >= 0", recs, "0"),
        ("repeated run", recs + [dict(recs[0])], 0),
        # review iter-342 should-fix 2: one fault per case, a fresh run of one item in another language
        ("item language differs", recs + [dict(recs[0], language="Dart", run=2)], 0),
        ("incomplete item", [r for r in recs if (r["item"], r["model"], r["run"]) != ("b__y-2", LUNA, 0)], 0),
    ]
    for opening, given, run in cases:
        with pytest.raises(ValueError) as exc:
            cv.convert(given, run=run)
        assert str(exc.value).startswith(opening), (opening, str(exc.value))


def test_convert_incomplete_item_names_the_item_and_a_model(cv):
    recs = [r for r in sample(cv) if (r["item"], r["model"], r["run"]) != ("b__y-2", LUNA, 0)]
    with pytest.raises(ValueError) as exc:
        cv.convert(recs)
    assert "b__y-2" in str(exc.value) and LUNA in str(exc.value)


def test_convert_a_run_no_record_has_is_an_incomplete_item(cv):
    # review iter-342 should-fix 3: the items are every item any record names, at any run
    with pytest.raises(ValueError) as exc:
        cv.convert(sample(cv), run=5)
    assert str(exc.value).startswith("incomplete item")


def test_convert_every_item_dropped_is_no_items(cv):
    recs = [dict(r, statement_matches=False) if r["run"] == 0 and r["model"] == LUNA else r for r in sample(cv)]
    with pytest.raises(ValueError) as exc:
        cv.convert(recs)
    assert str(exc.value).startswith("no items")
    assert cv.convert(recs, run=1)[1]["tasks"] == {TASK: {"items": 3}}


# verify, fetch and read_rows


def _write(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(data)
    return path


def _pin(monkeypatch, cv, files):
    monkeypatch.setattr(cv, "FILES", {name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in files.items()})


FAKE = {name: name.encode() for name in FILES}


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


def test_fetch_downloads_into_the_subfolder(cv, tmp_path, monkeypatch):
    _pin(monkeypatch, cv, FAKE)
    urls = []

    def opener(u, timeout):
        urls.append((u, timeout))
        return contextlib.closing(io.BytesIO(FAKE[u.rsplit(f"/{cv.REVISION}/", 1)[1]]))

    monkeypatch.setattr(cv.urllib.request, "urlopen", opener)
    out = cv.fetch(tmp_path / "cache")
    assert [u for u, _ in urls] == [cv.url(n) for n in sorted(FAKE)] and {t for _, t in urls} == {cv.TIMEOUT}
    assert all(out[n].read_bytes() == FAKE[n] for n in FAKE) and (tmp_path / "cache" / "data").is_dir()
    assert not list((tmp_path / "cache").rglob("*.part"))


def test_fetch_retries_then_fails_and_removes_part(cv, tmp_path, monkeypatch):
    _pin(monkeypatch, cv, FAKE)
    calls = []

    def opener(u, timeout):
        calls.append(u)
        raise OSError("down")

    monkeypatch.setattr(cv.urllib.request, "urlopen", opener)
    with pytest.raises(OSError, match="swelike__claude-opus-5.5-high.parquet: download failed"):
        cv.fetch(tmp_path)
    assert len(calls) == cv.ATTEMPTS == 3
    assert not list(tmp_path.rglob("*.part"))


def test_fetch_bad_present_file_left_in_place(cv, tmp_path, monkeypatch):
    # review iter-342 should-fix 5: `fetch` as 12.20, a present file that fails `verify` refused and kept
    _pin(monkeypatch, cv, FAKE)
    name = sorted(FAKE)[0]
    bad = _write(tmp_path / name, b"changed")
    monkeypatch.setattr(cv.urllib.request, "urlopen", lambda *a, **k: pytest.fail("downloaded"))
    with pytest.raises(ValueError):
        cv.fetch(tmp_path)
    assert bad.read_bytes() == b"changed"


def test_fetch_wrong_download_removed_and_not_retried(cv, tmp_path, monkeypatch):
    _pin(monkeypatch, cv, FAKE)
    calls = []

    def opener(u, timeout):
        calls.append(u)
        return contextlib.closing(io.BytesIO(b"x"))

    monkeypatch.setattr(cv.urllib.request, "urlopen", opener)
    with pytest.raises(ValueError):
        cv.fetch(tmp_path)
    assert calls == [cv.url(sorted(FAKE)[0])]
    assert not list(tmp_path.rglob("*.part")) and not (tmp_path / sorted(FAKE)[0]).exists()


def test_read_rows_without_pyarrow_says_to_install_the_extra(cv, tmp_path, monkeypatch):
    import sys

    monkeypatch.setitem(sys.modules, "pyarrow", None)
    monkeypatch.setitem(sys.modules, "pyarrow.parquet", None)
    with pytest.raises(ValueError) as exc:
        cv.read_rows(_write(tmp_path / "f.parquet", b"x"))
    assert "evidence" in str(exc.value)


def _parquet(path, rows, columns=COLUMNS + ("model_patch",)):
    pa = pytest.importorskip("pyarrow")
    pq = pytest.importorskip("pyarrow.parquet")
    table = pa.table({c: [r.get(c, "diff --git a b") for r in rows] for c in columns})
    path.parent.mkdir(parents=True, exist_ok=True)
    pq.write_table(table, path)
    return path


def test_read_rows_reads_the_columns_alone(cv, tmp_path):
    rows = [prow(), prow("o__r-2", resolved=None, run=1)]
    got = cv.read_rows(_parquet(tmp_path / "data" / "x.parquet", rows))
    assert got == rows and all(list(r) == list(COLUMNS) for r in got)


def test_read_rows_names_the_file(cv, tmp_path):
    missing = _parquet(tmp_path / "short.parquet", [prow()], COLUMNS[:-1])
    with pytest.raises(ValueError, match="short.parquet"):
        cv.read_rows(missing)
    pytest.importorskip("pyarrow")
    with pytest.raises(ValueError, match="junk.parquet"):
        cv.read_rows(_write(tmp_path / "junk.parquet", b"not parquet"))


# The CLI


def _cache(tmp_path, per_file):
    paths = {name: _write(tmp_path / "cache" / name, b"x") for name in sorted(FILES)}
    reg = _write(tmp_path / "models.json", json.dumps(registry()).encode())
    rows = {paths[name]: per_file.get(name, []) for name in paths}
    return paths, reg, rows


def _two_models(items=("a__x-1", "b__y-2"), runs=(0, 1)):
    return {"data/swelike__gpt-6.1-sol-high.parquet":
            [prow(i, "Lua", "gpt-6.1-sol", run, 1) for run in runs for i in items],
            "data/swelike__gpt-5.6-luna-xhigh.parquet":
            [prow(i, "Lua", "gpt-5.6-luna", run, run % 2) for run in runs for i in items]}


def _run(cv, argv, capsys):
    code = cv.main(argv)
    out, err = capsys.readouterr()
    return code, out, err


def _patch(monkeypatch, cv, paths, reg, rows):
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: paths)
    monkeypatch.setattr(cv, "REGISTRY", reg)
    monkeypatch.setattr(cv, "read_rows", lambda path: rows[Path(path)])


def test_cli_writes_rows_and_prints_report(cv, tmp_path, monkeypatch, capsys):
    paths, reg, rows = _cache(tmp_path, _two_models())
    _patch(monkeypatch, cv, paths, reg, rows)
    out = tmp_path / "rows.jsonl"
    code, stdout, err = _run(cv, ["--out", str(out)], capsys)
    assert (code, err) == (0, "")
    got = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(got) == 4 and all(list(r) == ROW_KEYS for r in got)
    report = json.loads(stdout)
    assert stdout == json.dumps(report, indent=2) + "\n" and report["run"] == 0
    assert report["resolved"] == {LUNA: 0, SOL61: 2} and report["tasks"] == {TASK: {"items": 2}}
    assert not (tmp_path / "rows.jsonl.part").exists()


def test_cli_run_and_cache(cv, tmp_path, monkeypatch, capsys):
    paths, reg, rows = _cache(tmp_path, _two_models())
    _patch(monkeypatch, cv, paths, reg, rows)
    seen = []
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: seen.append(cache_dir) or paths)
    code, stdout, _ = _run(cv, ["--out", str(tmp_path / "o.jsonl"), "--cache", "somewhere", "--run", "1"], capsys)
    assert code == 0 and seen == ["somewhere"] and json.loads(stdout)["resolved"] == {LUNA: 2, SOL61: 2}


def test_cli_model_not_in_registry_writes_nothing(cv, tmp_path, monkeypatch, capsys):
    per_file = _two_models()
    per_file["data/swelike__gpt-6.1-sol-high.parquet"][0]["canonical_model"] = "gpt-9-nova"
    paths, reg, rows = _cache(tmp_path, per_file)
    _patch(monkeypatch, cv, paths, reg, rows)
    out = tmp_path / "o.jsonl"
    code, stdout, err = _run(cv, ["--out", str(out)], capsys)
    # v1.479 (review iter-342 nit 2): the file is named before the row within it
    assert err.startswith("error: data/swelike__gpt-6.1-sol-high.parquet: row 0: model not in the registry")
    assert code == 2 and stdout == "" and err.count("\n") == 1
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


# v1.486 (review iter-343 nit 2): `int` would take "+1", " 1", "1 ", "1\n" and the Arabic-Indic three; ASCII digits only
@pytest.mark.parametrize("value", ["-1", "x", "1.5", "", "+1", " 1", "1 ", "\u0663", "\u00b2", "1\n"])
def test_cli_bad_run_downloads_nothing(cv, tmp_path, monkeypatch, capsys, value):
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: pytest.fail("fetched"))
    code, stdout, err = _run(cv, ["--out", str(tmp_path / "o.jsonl"), "--run", value], capsys)
    assert code == 2 and stdout == "" and err.startswith("error: --run must be decimal digits only, got ") and err.count("\n") == 1


def test_cli_needs_out(cv, monkeypatch, capsys):
    monkeypatch.setattr(cv, "fetch", lambda cache_dir=None: pytest.fail("fetched"))
    code, _, err = _run(cv, [], capsys)
    assert code == 2 and err.startswith("error: ")


def test_cli_print_failure_leaves_no_out(cv, tmp_path, monkeypatch, capsys):
    paths, reg, rows = _cache(tmp_path, _two_models())
    _patch(monkeypatch, cv, paths, reg, rows)

    def broken(text):
        raise OSError("closed")

    monkeypatch.setattr(cv, "print_report", broken)
    out = tmp_path / "o.jsonl"
    assert _run(cv, ["--out", str(out)], capsys)[0] == 2
    assert not out.exists() and not (tmp_path / "o.jsonl.part").exists()


# The spec


def test_design_specifies_the_converter_and_its_rules():
    text = DESIGN.read_text(encoding="utf-8")
    start = text.index("### 12.25 Public evidence: the Longtail-SWE converter (`evidence/longtail-swe/convert.py`, v1.478)")
    body = text[start:text.index("\n## 13. ", start)]
    for phrase in (f"`REVISION = \"{REVISION}\"`", "`LICENCE = \"cc-by-4.0\"`", "the four registry models alone",
                   "run 0 by default, so 12.2's seeded halves split by `instance_id`",
                   "misses that keep their charge", "with no cache discount", "one routing task, `issue_resolution`",
                   "`model_patch` is not read", "776 rows", "prefixed by that file's `FILES` name and `: `"):
        assert phrase in body, phrase
    for name, (size, _) in FILES.items():
        assert f"`{name}` ({size:,}" in body, name


# The pinned files (skipped unless pyarrow is installed and all four are in the default cache)

# Run 0 of the 194 kept items, summed per model by a private read of the four files (2026-11-18).
TOKENS = {OPUS: (841582971, 6901742), LUNA: (2477599520, 9853330), SOL56: (567723252, 4124286),
          SOL61: (337843991, 4055635)}


@pytest.fixture(scope="module")
def pinned(tmp_path_factory):
    cvm = load(SCRIPT, "longtail_swe_convert_pinned")
    pytest.importorskip("pyarrow")
    cache = cvm.default_cache_dir()
    if not all((cache / name).is_file() for name in FILES):
        pytest.skip("the pinned files are not in the default cache")
    out = tmp_path_factory.mktemp("longtail-swe") / "rows.jsonl"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cvm.main(["--out", str(out)])
    return code, json.loads(buf.getvalue()) if code == 0 else None, out


def test_pinned_files_default_output(pinned):
    code, report, out = pinned
    assert code == 0
    assert report["models"] == [OPUS, LUNA, SOL56, SOL61] and report["run"] == 0 and report["rows"] == 776
    assert report["tasks"] == {TASK: {"items": 194}}
    assert report["languages"] == {"Clojure": 12, "Dart": 13, "Elixir": 22, "Erlang": 12, "F#": 16, "Haskell": 13,
                                   "Julia": 26, "Kotlin": 11, "Lua": 13, "OCaml": 12, "R": 14, "Scala": 17, "Swift": 13}
    assert len(report["dropped_statement"]) == 8 and report["dropped_statement"] == sorted(report["dropped_statement"])
    assert report["resolved"] == {OPUS: 162, LUNA: 140, SOL56: 152, SOL61: 155}
    assert report["unscored"] == {OPUS: [], LUNA: [], SOL56: [], SOL61: ["babashka__cli-162"]}
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 776 and not any(r["cost_usd"] == 0.0 for r in rows)
    for model, (tin, tout) in TOKENS.items():
        got = math.fsum(r["cost_usd"] for r in rows if r["model"] == model)
        assert got == pytest.approx((tin * PRICES[model][0] + tout * PRICES[model][1]) / 1_000_000, rel=1e-9), model
