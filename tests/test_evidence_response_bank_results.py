"""v1.291 response-bank results contract (DESIGN 12.21), written before the results were committed.

The committed ``evidence/response-bank/results.json`` is made by the RouterBench results script,
``evidence/routerbench/results.py``, reused unchanged, from ``model-routing evaluate`` in both
flavors, since every row of the 12.20 matrix has a ``cost_usd`` (6 of them 0.0, the ``missing``
cells, but no (task, model) pair 0.0 on every item). The first tests need no download: they check
the committed file alone. The last ones use the converter's CLI run on the four pinned files, the
session fixture ``response_bank_pinned`` of tests/conftest.py that the converter tests share, so
the suite reads the files at most once; they skip when any is not in the default cache (CI never
downloads them). They rebuild results.json and require the committed bytes, and rebuild the
success span behind the bars, the calibration-half sizes and the zero costs DESIGN 12.21 states.

The tests that read the committed file were committed before it under strict xfail
(``FileNotFoundError``), removed by the commit that adds it (v1.292); the span, split-size and
zero-cost tests read only the pinned files.
"""

import importlib.util
import json
import math
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows, split_items

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "response-bank"
RESULTS = FOLDER / "results.json"
BARS = [0.8, 0.9]
FLAVORS = ["cost_effective", "cost_blind"]
CONFIG = {"bars": BARS, "seeds": list(range(50)), "flavors": FLAVORS,
          "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95}
ITEMS = {"aime": 30, "gpqa_diamond": 198, "livecodebench": 1055, "mmlu_pro": 12032}
STRATEGIES = ["routed", "oracle", "best_on_calibration", "cheapest"]


def load(name, path):
    if not path.is_file():
        raise ModuleNotFoundError(f"no script at {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rs():
    return load("routerbench_results_for_response_bank", ROOT / "evidence" / "routerbench" / "results.py")


@pytest.fixture(scope="module")
def cv():
    return load("response_bank_convert_for_results", FOLDER / "convert.py")


def model_ids(cv):
    return sorted(cv.model_id(raw) for raw in cv.MODELS)


def committed():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


# --- the committed file -----------------------------------------------------------------------

def test_committed_results_are_small_and_reduced(rs):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    assert text == json.dumps(rs.reduce(json.loads(text)), indent=2) + "\n"


def test_committed_results_have_the_config_tasks_and_models(cv):
    results = committed()
    assert results["config"] == CONFIG
    models = model_ids(cv)
    assert len(models) == 5
    assert results["tasks"] == {task: {"items": n, "models": models} for task, n in ITEMS.items()}
    assert list(results["tasks"]) == sorted(ITEMS)


def test_committed_results_rows_are_unique_routed_and_costed(cv):
    results = committed()
    models = model_ids(cv)
    keys = {(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]}
    assert len(results["summary"]) == len(keys) == len(BARS) * len(FLAVORS) * (len(STRATEGIES) + 5) == 36
    assert keys == {(b, f, s) for b in BARS for f in FLAVORS
                    for s in STRATEGIES + ["model:" + m for m in models]}
    task_keys = {(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]}
    assert len(results["per_task"]) == len(task_keys) == len(BARS) * len(FLAVORS) * len(ITEMS) == 16
    assert task_keys == {(b, f, t) for b in BARS for f in FLAVORS for t in ITEMS}
    assert all(r["strategy"] == "routed" for r in results["per_task"])
    assert all(sum(r["routed_models"].values()) == 50 and set(r["routed_models"]) <= set(models)
               for r in results["per_task"])
    assert all(r["cost_usd"] > 0 for r in results["summary"] + results["per_task"])


def test_committed_aime_never_clears():
    rows = [r for r in committed()["per_task"] if r["task"] == "aime"]
    assert len(rows) == len(BARS) * len(FLAVORS) and all(r["cleared_rate"] == 0 for r in rows)


# --- the pinned files, only when already cached (one session read, tests/conftest.py) ---------

@pytest.fixture(scope="module")
def real_rows(response_bank_pinned):
    code, out, err, path = response_bank_pinned
    assert (code, err) == (0, "") and json.loads(out)["rows"] == 66575
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def without_cells(result):
    return {k: v for k, v in result.items() if k != "cells"}


def test_real_results_regenerate_byte_identical(rs, real_rows):
    result = evaluate(outcomes_from_rows(real_rows), bars=BARS, seeds=range(50))
    assert json.dumps(rs.reduce(without_cells(result)), indent=2) + "\n" == RESULTS.read_text(
        encoding="utf-8")


def test_real_bars_are_every_tenth_strictly_inside_the_success_span(real_rows):
    hits = {}
    for r in real_rows:
        hits.setdefault((r["task"], r["model"]), []).append(r["correct"])
    rates = {key: (sum(v), len(v)) for key, v in hits.items()}
    assert len(rates) == 4 * 5 and {t: n for (t, _), (_, n) in rates.items()} == ITEMS
    low = min(rates, key=lambda k: rates[k][0] / rates[k][1])
    high = max(rates, key=lambda k: rates[k][0] / rates[k][1])
    assert (low, rates[low]) == (("aime", "z-ai/glm-5.3"), (23, 30))
    assert (high, rates[high]) == (("aime", "deepseek/deepseek-v4-pro"), (29, 30))
    lo, hi = 23 / 30, 29 / 30
    assert f"{lo:.3f} {hi:.3f}" == "0.767 0.967"
    assert BARS == [k / 10 for k in range(math.floor(lo * 10) + 1, math.ceil(hi * 10))]


def test_real_calibration_halves_are_the_design_sizes(real_rows):
    items = {}
    for r in real_rows:
        items.setdefault(r["task"], set()).add(r["item"])
    sizes = {task: [len(split_items(sorted(v), seed)[0]) for seed in range(50)]
             for task, v in items.items()}
    aime = sizes["aime"]
    assert (min(aime), max(aime), sum(n < CONFIG["min_samples"] for n in aime)) == (10, 21, 50)
    others = {task: (min(v), max(v)) for task, v in sizes.items() if task != "aime"}
    assert others == {"gpqa_diamond": (82, 119), "livecodebench": (481, 590), "mmlu_pro": (5904, 6116)}


def test_real_zero_costs_are_the_missing_cells_and_never_fill_a_pair(real_rows):
    zeros, rows = {}, {}
    for r in real_rows:
        key = (r["task"], r["model"])
        rows[key] = rows.get(key, 0) + 1
        zeros[key] = zeros.get(key, 0) + (r["cost_usd"] == 0)
    assert all(r["cost_usd"] >= 0 for r in real_rows)
    assert {key: n for key, n in zeros.items() if n} == {("mmlu_pro", "z-ai/glm-5.3"): 3,
                                                         ("mmlu_pro", "z-ai/glm-5.3-flash"): 3}
    assert all(r["input_tokens"] is None for r in real_rows if r["cost_usd"] == 0)
    assert all(zeros[key] < rows[key] for key in rows)
