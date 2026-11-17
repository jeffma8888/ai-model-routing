"""Registry-pair results contract (DESIGN 12.24, v1.433), written before the results were committed.

The committed ``evidence/registry-pair/results.json`` is made by the RouterBench results script,
``evidence/routerbench/results.py``, reused unchanged, from ``model-routing evaluate`` at the
RouterBench config (bars 0.6 to 0.9, 50 seeds) in both flavors, on the 12.23 matrix of the registry's
own pair. The first tests need no download: they check the committed file alone. The last ones run
the converter's ``main`` in process on the three pinned files, once per module, and skip when any is
not in the default cache (CI never downloads them). They rebuild results.json and require the
committed bytes, and rebuild the success span and the calibration-half sizes DESIGN 12.24 states.

The tests that read the committed file were committed before it under strict xfail
(``FileNotFoundError``), removed by the commit that adds it (v1.434); the spec, span and split-size
tests read only DESIGN.md and the pinned files.
"""

import contextlib
import importlib.util
import io
import json
import math
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows, split_items

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "registry-pair"
RESULTS = FOLDER / "results.json"
DESIGN = ROOT / "DESIGN.md"
HEADING = "### 12.24 Registry-pair results (`evidence/registry-pair/results.json`, v1.433)"
BARS = [0.6, 0.7, 0.8, 0.9]
FLAVORS = ["cost_effective", "cost_blind"]
CONFIG = {"bars": BARS, "seeds": list(range(50)), "flavors": FLAVORS,
          "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95}
LUNA, SOL = "openai/gpt-6-luna", "openai/gpt-6.1-sol"
MODELS = [LUNA, SOL]
STRATEGIES = ["routed", "oracle", "best_on_calibration", "cheapest"]
FILES = ("pair.json", "recordings/grades-calibration.json", "recordings/grades-final.json")
# The 12.23 converter's report on the pinned files: items per task (the cached-file test pins it).
ITEMS = {
    "bbh/boolean_expressions": 92,
    "bbh/date_understanding": 92,
    "bbh/formal_fallacies": 92,
    "bbh/logical_deduction_five_objects": 92,
    "bbh/logical_deduction_seven_objects": 92,
    "bbh/logical_deduction_three_objects": 92,
    "bbh/navigate": 93,
    "bbh/object_counting": 92,
    "bbh/reasoning_about_colored_objects": 92,
    "bbh/temporal_sequences": 92,
    "bbh/tracking_shuffled_objects_five_objects": 92,
    "bbh/tracking_shuffled_objects_seven_objects": 93,
    "bbh/tracking_shuffled_objects_three_objects": 92,
    "bbh/web_of_lies": 92,
    "korbench/cipher": 80,
    "korbench/counterfactual": 80,
    "korbench/logic": 20,
    "mmlupro/biology": 274,
    "mmlupro/business": 303,
    "mmlupro/chemistry": 440,
    "mmlupro/computer_science": 151,
    "mmlupro/economics": 323,
    "mmlupro/engineering": 375,
    "mmlupro/health": 312,
    "mmlupro/history": 141,
    "mmlupro/law": 428,
    "mmlupro/math": 526,
    "mmlupro/other": 357,
    "mmlupro/philosophy": 186,
    "mmlupro/physics": 507,
    "mmlupro/psychology": 306,
}
RED = pytest.mark.xfail(strict=True, raises=FileNotFoundError)  # v1.433: removed by v1.434


def load(name, path):
    if not path.is_file():
        raise ModuleNotFoundError(f"no script at {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rs():
    return load("routerbench_results_for_registry_pair", ROOT / "evidence" / "routerbench" / "results.py")


def committed():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def body():
    text = DESIGN.read_text(encoding="utf-8")
    start = text.index(HEADING)
    return text[start:text.index("\n## 13. ", start)]


def routed(results, bar, flavor):
    rows = [r for r in results["summary"] if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, "routed")]
    assert len(rows) == 1
    return rows[0]


# --- the spec ---------------------------------------------------------------------------------

def test_items_are_the_converter_default():
    assert len(ITEMS) == 31 and sum(ITEMS.values()) == 6099 and list(ITEMS) == sorted(ITEMS)
    assert ITEMS["korbench/logic"] == 20 and ITEMS["bbh/logical_deduction_three_objects"] == 92


def test_design_specifies_the_results_file_and_its_bars():
    text = body()
    for phrase in ("bars `0.6 0.7 0.8 0.9`, 50 seeds, `calibration_fraction` 0.5, `min_samples` 30 and confidence 0.95",
                   "would give only `0.8 0.9`", "a family-held counterpart at its bar",
                   "`python evidence/registry-pair/convert.py --out registry-pair-matrix.jsonl`",
                   "`model-routing evaluate --outcomes registry-pair-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json"
                   " > registry-pair-evaluate.json`",
                   "`python evidence/routerbench/results.py --evaluate registry-pair-evaluate.json"
                   " --out evidence/registry-pair/results.json`",
                   "so 48 rows, and 4 times 2 times 31 tasks, 248 rows",
                   "`pytest.mark.xfail(strict=True, raises=FileNotFoundError)`", "(row E24d:"):
        assert phrase in text, phrase
    assert "\u2013" not in text and "\u2014" not in text


# --- the committed file -----------------------------------------------------------------------

@RED
def test_committed_results_are_small_and_reduced(rs):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    assert text == json.dumps(rs.reduce(json.loads(text)), indent=2) + "\n"


@RED
def test_committed_results_have_the_config_tasks_and_models():
    results = committed()
    assert results["config"] == CONFIG
    assert results["tasks"] == {task: {"items": n, "models": MODELS} for task, n in ITEMS.items()}
    assert list(results["tasks"]) == sorted(ITEMS)


@RED
def test_committed_results_rows_are_unique_routed_and_costed():
    results = committed()
    keys = {(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]}
    assert len(results["summary"]) == len(keys) == len(BARS) * len(FLAVORS) * (len(STRATEGIES) + 2) == 48
    assert keys == {(b, f, s) for b in BARS for f in FLAVORS for s in STRATEGIES + ["model:" + m for m in MODELS]}
    task_keys = {(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]}
    assert len(results["per_task"]) == len(task_keys) == len(BARS) * len(FLAVORS) * len(ITEMS) == 248
    assert task_keys == {(b, f, t) for b in BARS for f in FLAVORS for t in ITEMS}
    assert all(r["strategy"] == "routed" for r in results["per_task"])
    assert all(sum(r["routed_models"].values()) == 50 and set(r["routed_models"]) <= set(MODELS)
               for r in results["per_task"])
    assert all(r["cost_usd"] > 0 for r in results["summary"] + results["per_task"])


@RED
def test_committed_korbench_logic_never_clears_and_falls_back():
    rows = [r for r in committed()["per_task"] if r["task"] == "korbench/logic"]
    assert len(rows) == len(BARS) * len(FLAVORS) and all(r["cleared_rate"] == 0 for r in rows)
    picks = {json.dumps(r["routed_models"], sort_keys=True) for r in rows}
    assert len(picks) == 1
    pick = rows[0]["routed_models"]
    assert (f"takes `{LUNA}` on {pick[LUNA]} seeds and `{SOL}` on {pick[SOL]};") in body()


@RED
def test_design_bars_bullet_is_the_committed_file():
    results = committed()
    ce = {bar: routed(results, bar, "cost_effective") for bar in BARS}
    phrase = (f"the routed `cost_effective` cleared rate is {ce[0.6]['cleared_rate']:.3f} at 0.6, "
              f"{ce[0.7]['cleared_rate']:.3f} at 0.7 and {ce[0.8]['cleared_rate']:.3f} at 0.8, and at 0.7 its "
              f"bar-violation rate is {ce[0.7]['bar_violation_rate']:.3f}. The file of the four bars is "
              f"{RESULTS.stat().st_size:,} bytes, under the 300,000")
    assert phrase in body()


# --- the pinned files, only when already cached (the converter's main, once per module) --------

@pytest.fixture(scope="module")
def real_rows(tmp_path_factory):
    cv = load("registry_pair_convert_for_results", FOLDER / "convert.py")
    cache = cv.default_cache_dir()
    if not all((cache / name).is_file() for name in FILES):
        pytest.skip("the pinned files are not in the default cache")
    out = tmp_path_factory.mktemp("registry-pair-results") / "rows.jsonl"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cv.main(["--out", str(out)])
    assert code == 0
    report = json.loads(buf.getvalue())
    assert report["rows"] == 12198 and {t: v["items"] for t, v in report["tasks"].items()} == ITEMS
    with open(out, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def without_cells(result):
    return {k: v for k, v in result.items() if k != "cells"}


@RED
def test_real_results_regenerate_byte_identical(rs, real_rows):
    result = evaluate(outcomes_from_rows(real_rows), bars=BARS, seeds=range(50))
    assert json.dumps(rs.reduce(without_cells(result)), indent=2) + "\n" == RESULTS.read_text(encoding="utf-8")


def test_real_success_span_and_the_12_17_rule(real_rows):
    hits = {}
    for r in real_rows:
        hits.setdefault((r["task"], r["model"]), []).append(r["correct"])
    rates = {key: (sum(v), len(v)) for key, v in hits.items()}
    assert len(rates) == 31 * 2 and {t: n for (t, _), (_, n) in rates.items()} == ITEMS
    low = min(rates, key=lambda k: rates[k][0] / rates[k][1])
    assert (low, rates[low]) == (("mmlupro/law", LUNA), (304, 428))
    full = sorted(k for k, (s, n) in rates.items() if s == n)
    tasks = sorted({t for t, _ in full})
    assert all(t.startswith("bbh/") for t in tasks)
    lo, hi = 304 / 428, 1.0
    phrase = (f"run from {lo:.3f} (`{LUNA}` on `mmlupro/law`, 304 of 428) to {hi:.3f} ({len(full)} (task, model) "
              f"pairs on {len(tasks)} `bbh` tasks)")
    assert phrase in body()
    rule = [k / 10 for k in range(math.floor(lo * 10) + 1, math.ceil(hi * 10))]
    assert rule == [0.8, 0.9] and rule != BARS and set(rule) < set(BARS)


def test_real_calibration_halves_are_the_design_sizes(real_rows):
    items = {}
    for r in real_rows:
        items.setdefault(r["task"], set()).add(r["item"])
    sizes = {task: [len(split_items(sorted(v), seed)[0]) for seed in range(50)] for task, v in items.items()}
    floor = CONFIG["min_samples"]
    logic, three = sizes["korbench/logic"], sizes["bbh/logical_deduction_three_objects"]
    assert (min(logic), max(logic), sum(n < floor for n in logic)) == (5, 14, 50)
    assert (min(three), max(three), sum(n < floor for n in three)) == (28, 57, 1)
    rest = {task: min(v) for task, v in sizes.items() if task not in ("korbench/logic", "bbh/logical_deduction_three_objects")}
    least = min(rest, key=lambda t: (rest[t], t))
    assert (least, rest[least]) == ("korbench/counterfactual", 31)
    text = body()
    assert f"`korbench/logic` (20 items) holds {min(logic)} to {max(logic)} items, under `min_samples` 30 on every seed" in text
    assert f"(92 items) holds {min(three)} to {max(three)} items, under 30 on 1 seed" in text
    assert f"at least {rest[least]} items (`{least}`) on every seed" in text
