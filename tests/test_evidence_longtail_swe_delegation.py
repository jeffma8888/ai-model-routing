"""evidence/longtail-swe-delegation/results.py and results.json (DESIGN 13.18 v1.498, row E27a).

The 13.9 harness on Longtail-SWE's agent runs, nebius/Longtail-SWE-trajectories at the 12.25 pin: the release
records each run's token totals only, so research/longtail_per_call.py (13.16 v1.496) splits each run into its
model calls by a stated rule, an assumption, and the script scores the split rows at the note's bars and points.
Offline, `inputs` is checked on hand-made pairs, `run` and the CLI on stand-ins, and the committed file's shape and
its agreement with the note's Results block; when `pyarrow` and the four pinned files are in the default cache,
the script runs in process once per module and its output equals the committed file byte for byte (never a
download here)."""

import importlib.util
import json
import os
import re
import statistics
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "longtail-swe-delegation"
SCRIPT = FOLDER / "results.py"
RESULTS = FOLDER / "results.json"
CONFIG = ROOT / "evidence" / "longtail-swe" / "results.json"
REGISTRY = ROOT / "model_routing" / "data" / "models.json"
NOTE = ROOT / "research" / "longtail-per-call.md"
DESIGN = ROOT / "DESIGN.md"
MODELS = ["anthropic/claude-opus-5.5", "openai/gpt-5.6-luna", "openai/gpt-5.6-sol", "openai/gpt-6.1-sol"]
FLAVORS = ["cost_effective", "cost_blind"]
STRATEGIES = ["decision", "inline", "delegate"]
BARS = [0.7, 0.8]
SIZE = 55_416  # 13.18 Committed
SPLIT = {"runs_refused": 0, "items_dropped": [], "rows": 776}
ROW = re.compile(r"(cost_effective|cost_blind) +(0\.\d+) +(\d) +(\S+) +(\d\.\d\d) +(.*)")


def load():
    if not SCRIPT.is_file():
        raise FileNotFoundError(f"no script at {SCRIPT.relative_to(ROOT)}")
    spec = importlib.util.spec_from_file_location("longtail_swe_delegation_results_for_tests", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def committed():
    if not RESULTS.is_file():
        raise FileNotFoundError(f"no results file at {RESULTS.relative_to(ROOT)}")
    return RESULTS.read_text(encoding="utf-8")


def subsection():
    design = DESIGN.read_text(encoding="utf-8")
    start = design.index("\n### 13.18 ")
    return design[start:design.index("\n## 14. ", start)]


def note_block():
    found = re.findall(r"\n## Results\n\n```text\n(.*?)```\n", NOTE.read_text(encoding="utf-8"), re.S)
    assert len(found) == 1
    return found[0]


# --- the spec (13.18) ---------------------------------------------------------------------------------------

def test_design_13_18_follows_13_17_and_names_the_contract():
    design = DESIGN.read_text(encoding="utf-8")
    assert design.index("\n### 13.17 ") < design.index("\n### 13.18 ") < design.index("\n## 14. ")
    text = subsection()
    for phrase in ("(`evidence/longtail-swe-delegation/results.py`, v1.498)", "an assumption the release cannot check",
                   "`research/longtail_per_call.py`, loaded by file path (`PC`)", "`PC.per_call`, the rule of 13.16 v1.496",
                   "`inputs(pairs) -> (rows, points, split)`", "`run(rows, points, split, registry, config) -> dict`",
                   "Bars 0.7 and 0.8 (`BARS`)", "192 summary rows", f"{SIZE:,} bytes",
                   "`python evidence/longtail-swe-delegation/results.py --out evidence/longtail-swe-delegation/results.json`",
                   "exit 2 before any file is read, written or removed", "`tests/test_evidence_longtail_swe_delegation.py`",
                   "RESULTS.md, which states the split as an assumption and links that note"):
        assert phrase in text, phrase


def test_the_bars_are_the_notes_and_its_below_bar_counts_are_the_spec_reason():
    block = note_block()
    for flavor in FLAVORS:
        line = [l for l in block.split("\n") if l.startswith(f"  {flavor}, cells whose decision is below the bar: ")]
        assert line == [f"  {flavor}, cells whose decision is below the bar: bar 0.7 48 of 800; bar 0.8 736 of 800"]
    assert "bars 0.7 0.8, 50 seeds" in block
    text = subsection()
    assert "at 0.7 the decision is below the bar on 48 of 800 cells per flavor" in text
    assert "at 0.8 on 736 of 800" in text
    assert list(load().BARS) == BARS


# --- inputs and run -------------------------------------------------------------------------------------------

def _pair(item, model, tin, tout, calls, brief, result):
    row = {"task": "issue_resolution", "item": item, "model": model, "correct": True,
           "input_tokens": tin, "output_tokens": tout}
    return row, {"input": tin, "output": tout, "calls": calls, "brief": brief, "result": result}


def test_inputs_split_hand_pairs_and_drop_a_refused_runs_item(monkeypatch):
    m = load()
    kept = [_pair("a", "x/one", 100, 10, 2, 7, 40), _pair("a", "x/two", 12, 3, 1, 9, 50),
            _pair("b", "x/one", 5, 30, 3, 11, 60), _pair("b", "x/two", 50, 0, 1, 13, 70)]
    one = [row for row, _ in kept]
    monkeypatch.setattr(m.LD, "matrix", lambda pairs: (one, {"models": ["x/one", "x/two"]}, kept))
    rows, points, split = m.inputs("pairs")
    # 100 in, 10 out, 2 calls: outputs 5 and 5, L = 100 - 5 = 95, T = 3, a = 31, r = 2, so 32 and 31;
    # 5 in, 30 out, 3 calls: L = 5 - (2 * 10 + 10) < 0, refused, so item b goes for both models
    assert split == {"runs_refused": 1, "items_dropped": ["b"], "rows": 2}
    assert [(r["item"], r["model"], r["call_input_tokens"], r["call_output_tokens"]) for r in rows] == [
        ("a", "x/one", [32, 31], [5, 5]), ("a", "x/two", [12], [3])]
    assert 32 + (32 + 5 + 31) == 100
    assert points == m.LD.points(statistics.median_low([7, 9, 11, 13]), statistics.median_low([40, 50, 60, 70]))
    assert [(p["context_tokens"], p["inline_separate_call"], p["brief_tokens"], p["result_tokens"]) for p in points] == [
        (8000, True, 9, 50), (64000, True, 9, 50), (200000, True, 9, 50), (8000, False, 9, 50)]


def test_run_passes_the_bars_points_and_config_and_keeps_the_keys(monkeypatch):
    m = load()
    seen = {}

    def fake(rows, registry, **kwargs):
        seen.update(rows=rows, registry=registry, **kwargs)
        return {"config": "c", "tasks": "t", "summary": "s", "cells": "dropped"}

    monkeypatch.setattr(m, "evaluate_delegation", fake)
    config = {"seeds": [3, 4], "flavors": ["cost_blind"], "calibration_fraction": 0.4, "min_samples": 5,
              "confidence": 0.9, "bars": [0.1]}
    split = {"runs_refused": 0, "items_dropped": [], "rows": 1}
    got = m.run(["row"], ["point"], split, "registry", config)
    assert got == {"config": "c", "tasks": "t", "summary": "s", "split": split}
    assert list(got) == ["config", "tasks", "summary", "split"]
    assert seen == {"rows": ["row"], "registry": "registry", "bars": BARS, "points": ["point"], "seeds": [3, 4],
                    "flavors": ["cost_blind"], "calibration_fraction": 0.4, "min_samples": 5, "confidence": 0.9}
    assert m.KEYS == ("config", "tasks", "summary")
    assert m.CONFIG == CONFIG and m.REGISTRY == REGISTRY
    assert Path(m.PC.__file__).resolve() == ROOT / "research" / "longtail_per_call.py"


# --- the CLI ---------------------------------------------------------------------------------------------------

def _no_fetch(m, monkeypatch):
    calls = []
    monkeypatch.setattr(m.CONVERT, "fetch", lambda cache=None: calls.append(cache) or {})
    return calls


@pytest.mark.parametrize("target", ["config", "registry", "pinned"])
def test_an_out_naming_an_input_is_a_usage_error(target, tmp_path, monkeypatch, capsys):
    m = load()
    calls = _no_fetch(m, monkeypatch)
    cache = tmp_path / "cache"
    if target == "pinned":
        out = cache / sorted(m.CONVERT.FILES)[0]
        label = f"the pinned file {sorted(m.CONVERT.FILES)[0]}"
    else:
        out = tmp_path / "link.json"
        os.symlink(CONFIG if target == "config" else REGISTRY, out)
        label = "the config" if target == "config" else "the registry"
    before = sorted(p.name for p in tmp_path.rglob("*"))
    assert m.main(["--out", str(out), "--cache", str(cache)]) == 2
    err = capsys.readouterr().err.strip().split("\n")
    assert err == [f"error: --out (or its .part file) names the same file as {label}"]
    assert calls == [] and sorted(p.name for p in tmp_path.rglob("*")) == before


def test_an_error_is_one_escaped_line_and_leaves_no_file(tmp_path, monkeypatch, capsys):
    m = load()

    def broken(cache=None):
        raise OSError("down\nload\rfailed")

    monkeypatch.setattr(m.CONVERT, "fetch", broken)
    out = tmp_path / "out.json"
    assert m.main(["--out", str(out), "--cache", str(tmp_path / "cache")]) == 1
    assert capsys.readouterr().err == "error: down\\nload\\rfailed\n"
    assert list(tmp_path.iterdir()) == []


def test_success_writes_the_run_through_a_part_file(tmp_path, monkeypatch):
    m = load()
    calls = _no_fetch(m, monkeypatch)
    monkeypatch.setattr(m.LD, "read", lambda paths, raw: ("pairs", paths, sorted(raw)))
    seen = []
    split = {"runs_refused": 0, "items_dropped": [], "rows": 2}
    monkeypatch.setattr(m, "inputs", lambda pairs: seen.append(pairs) or (["r"], ["p"], split))
    monkeypatch.setattr(m, "evaluate_delegation", lambda *a, **k: {"config": 1, "tasks": 2, "summary": [3]})
    out = tmp_path / "out.json"
    assert m.main(["--out", str(out), "--cache", str(tmp_path / "cache")]) == 0
    assert calls == [str(tmp_path / "cache")]
    assert seen == [("pairs", {}, sorted(json.loads(REGISTRY.read_text(encoding="utf-8"))))]
    want = {"config": 1, "tasks": 2, "summary": [3], "split": split}
    assert out.read_text(encoding="utf-8") == json.dumps(want, indent=2) + "\n"
    assert sorted(p.name for p in tmp_path.iterdir()) == ["out.json"]


def test_an_unknown_option_exits_2():
    with pytest.raises(SystemExit) as exc:
        load().main(["--bogus"])
    assert exc.value.code == 2


# --- the committed file (13.18 Committed) ---------------------------------------------------------------------

def test_the_committed_file_is_small_and_its_own_dump():
    text = committed()
    assert len(text.encode("utf-8")) == SIZE < 300_000
    assert text == json.dumps(json.loads(text), indent=2) + "\n"


def test_the_committed_file_holds_the_config_task_split_and_summary():
    data = json.loads(committed())
    assert list(data) == ["config", "tasks", "summary", "split"]
    base = json.loads(CONFIG.read_text(encoding="utf-8"))["config"]
    config = data["config"]
    assert config["bars"] == BARS and config["parents"] == MODELS
    for key in ("seeds", "flavors", "calibration_fraction", "min_samples", "confidence"):
        assert config[key] == base[key], key
    assert len(config["seeds"]) == 50 and config["flavors"] == FLAVORS
    assert [(p["context_tokens"], p["inline_separate_call"], p["brief_tokens"], p["result_tokens"], p["carry_turns"])
            for p in config["points"]] == [(8000, True, 1244, 4863, 1), (64000, True, 1244, 4863, 1),
                                           (200000, True, 1244, 4863, 1), (8000, False, 1244, 4863, 1)]
    assert data["tasks"] == {"issue_resolution": {"items": 194, "models": MODELS}}
    assert data["split"] == SPLIT
    keys = [(s["flavor"], s["bar"], s["point"], s["parent"], s["strategy"]) for s in data["summary"]]
    assert len(keys) == len(set(keys)) == 192
    assert set(keys) == {(f, b, p, m, s) for f in FLAVORS for b in BARS for p in range(4) for m in MODELS
                         for s in STRATEGIES}


def test_the_committed_summary_equals_the_notes_results_rows():
    data = json.loads(committed())
    at = {(s["flavor"], s["bar"], s["point"], s["parent"], s["strategy"]): s for s in data["summary"]}
    rows = [ROW.fullmatch(line) for line in note_block().split("\n") if ROW.fullmatch(line)]
    assert len(rows) == 64
    for match in rows:
        flavor, bar, point, parent, rate, rest = match.groups()
        key = (flavor, float(bar), int(point), parent)
        got = [f"{at[key + ('decision',)]['delegate_rate']:.2f}"]
        for strategy in STRATEGIES:
            s = at[key + (strategy,)]
            got += [f"{s['success']:.3f}", f"{s['cost_usd']:,.0f}"]
        assert got == [rate] + rest.split(), match.group(0)


# --- the cached files (never a download here) -----------------------------------------------------------------

@pytest.fixture(scope="module")
def fresh(tmp_path_factory):
    pytest.importorskip("pyarrow")
    m = load()
    cache = m.CONVERT.default_cache_dir()
    if not all((cache / name).is_file() for name in m.CONVERT.FILES):
        pytest.skip("the four pinned Longtail-SWE files are not cached")
    out = tmp_path_factory.mktemp("longtail_swe_delegation") / "results.json"
    assert m.main(["--out", str(out)]) == 0
    return out.read_text(encoding="utf-8")


def test_the_committed_file_is_a_fresh_run_on_the_cached_files(fresh):
    assert fresh == committed()
