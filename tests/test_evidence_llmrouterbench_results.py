"""v1.156 LLMRouterBench results contract (DESIGN 12.19), written before the results were committed.

The committed ``evidence/llmrouterbench/results.json`` is made by the RouterBench results script,
``evidence/routerbench/results.py``, reused unchanged, from ``model-routing evaluate`` in both
flavors, since every row of the 12.18 matrix has a recorded cost. The first tests need no
download: they check the committed file alone. The last ones use the converter's CLI run on the
pinned file, the session fixture ``llmrouterbench_pinned`` of tests/conftest.py that the converter
tests share, so the suite reads the tarball at most once; they skip when it is not in the default
cache (CI never downloads it). They rebuild results.json and require the committed bytes, and
rebuild the success span behind the bars and the calibration-half sizes DESIGN 12.19 states.

The tests that read the committed file were committed before it under strict xfail
(``FileNotFoundError``), removed by the commit that adds it (v1.157); the span and split-size
tests read only the pinned file.
"""

import importlib.util
import json
import math
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows, split_items

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "llmrouterbench"
RESULTS = FOLDER / "results.json"
BARS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
FLAVORS = ["cost_effective", "cost_blind"]
CONFIG = {"bars": BARS, "seeds": list(range(50)), "flavors": FLAVORS,
          "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95}
ITEMS = {"aime": 60, "arc-agi": 400, "arenahard": 749, "gpqa": 198, "hle": 2157,
         "livecodebench": 1055, "livemathbench": 121, "mmlupro": 3000, "simpleqa": 4326}
STRATEGIES = ["routed", "oracle", "best_on_calibration", "cheapest"]
RED = pytest.mark.xfail(strict=True, raises=FileNotFoundError,
                        reason="evidence/llmrouterbench/results.json lands in v1.157")


def load(name, path):
    if not path.is_file():
        raise ModuleNotFoundError(f"no script at {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rs():
    return load("routerbench_results_for_lrb", ROOT / "evidence" / "routerbench" / "results.py")


@pytest.fixture(scope="module")
def cv():
    return load("llmrouterbench_convert_for_results", FOLDER / "convert.py")


def model_ids(cv):
    return sorted(cv.model_id(folder) for folder in cv.POOL)


def committed():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


# --- the committed file -----------------------------------------------------------------------

@RED
def test_committed_results_are_small_and_reduced(rs):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    assert text == json.dumps(rs.reduce(json.loads(text)), indent=2) + "\n"


@RED
def test_committed_results_have_the_config_tasks_and_pool(cv):
    results = committed()
    assert results["config"] == CONFIG
    models = model_ids(cv)
    assert len(models) == 13
    assert results["tasks"] == {task: {"items": n, "models": models} for task, n in ITEMS.items()}
    assert list(results["tasks"]) == sorted(ITEMS)


@RED
def test_committed_results_rows_are_unique_routed_and_costed(cv):
    results = committed()
    models = model_ids(cv)
    keys = {(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]}
    assert len(results["summary"]) == len(keys) == len(BARS) * len(FLAVORS) * (len(STRATEGIES) + 13) == 272
    assert keys == {(b, f, s) for b in BARS for f in FLAVORS
                    for s in STRATEGIES + ["model:" + m for m in models]}
    task_keys = {(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]}
    assert len(results["per_task"]) == len(task_keys) == len(BARS) * len(FLAVORS) * len(ITEMS) == 144
    assert task_keys == {(b, f, t) for b in BARS for f in FLAVORS for t in ITEMS}
    assert all(r["strategy"] == "routed" for r in results["per_task"])
    assert all(sum(r["routed_models"].values()) == 50 and set(r["routed_models"]) <= set(models)
               for r in results["per_task"])
    assert all(r["cost_usd"] > 0 for r in results["summary"] + results["per_task"])


# --- the pinned file, only when already cached (one session read, tests/conftest.py) ----------

@pytest.fixture(scope="module")
def real_rows(llmrouterbench_pinned):
    code, report, out = llmrouterbench_pinned
    assert code == 0 and report["rows"] == 156858
    with open(out, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def without_cells(result):
    return {k: v for k, v in result.items() if k != "cells"}


@RED
def test_real_results_regenerate_byte_identical(rs, real_rows):
    result = evaluate(outcomes_from_rows(real_rows), bars=BARS, seeds=range(50))
    assert json.dumps(rs.reduce(without_cells(result)), indent=2) + "\n" == RESULTS.read_text(
        encoding="utf-8")


def test_real_bars_are_every_tenth_strictly_inside_the_success_span(real_rows):
    hits = {}
    for r in real_rows:
        hits.setdefault((r["task"], r["model"]), []).append(r["correct"])
    rates = {key: (sum(v), len(v)) for key, v in hits.items()}
    assert len(rates) == 9 * 13 and {t: n for (t, _), (_, n) in rates.items()} == ITEMS
    low = min(rates, key=lambda k: rates[k][0] / rates[k][1])
    high = max(rates, key=lambda k: rates[k][0] / rates[k][1])
    assert (low, rates[low]) == (("hle", "deepseek/deepseek-v3-0324"), (78, 2157))
    assert (high, rates[high]) == (("aime", "openai/gpt-5"), (53, 60))
    lo, hi = 78 / 2157, 53 / 60
    assert f"{lo:.3f} {hi:.3f}" == "0.036 0.883"
    assert BARS == [k / 10 for k in range(math.floor(lo * 10) + 1, math.ceil(hi * 10))]


def test_real_calibration_halves_are_the_design_sizes(real_rows):
    items = {}
    for r in real_rows:
        items.setdefault(r["task"], set()).add(r["item"])
    sizes = {task: [len(split_items(sorted(v), seed)[0]) for seed in range(50)]
             for task, v in items.items()}
    aime = sizes["aime"]
    assert (min(aime), max(aime), sum(n < CONFIG["min_samples"] for n in aime)) == (22, 42, 25)
    others = {task: (min(v), max(v)) for task, v in sizes.items() if task != "aime"}
    assert min(low for low, _ in others.values()) == 50
    assert others["livemathbench"] == (50, 73)
