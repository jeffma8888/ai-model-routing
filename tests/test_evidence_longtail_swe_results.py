"""Longtail-SWE results contract (DESIGN 12.26, v1.481), written before the results were committed.

The committed ``evidence/longtail-swe/results.json`` is made by the RouterBench results script,
``evidence/routerbench/results.py``, reused unchanged, from ``model-routing evaluate`` at the
RouterBench config (bars 0.6 to 0.9, 50 seeds) in both flavors, on the 12.25 matrix of the four
registry models at run 0. The first tests need no download: they check the committed file alone. The
last ones run the converter's ``main`` in process on the four pinned files, once per module, and skip
when ``pyarrow`` is not installed or any file is not in the default cache (CI has neither). They
rebuild results.json and require the committed bytes, and rebuild the success span, the
calibration-half sizes, the cleared seeds at 0.8 and the tie seeds DESIGN 12.26 states.

The tests that read the committed file were committed before it under strict xfail
(``FileNotFoundError``), removed by the commit that adds it (v1.482); the spec, span, half-size,
cleared-seed and tie tests read only DESIGN.md and the pinned files.
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
FOLDER = ROOT / "evidence" / "longtail-swe"
RESULTS = FOLDER / "results.json"
DESIGN = ROOT / "DESIGN.md"
HEADING = "### 12.26 Longtail-SWE results (`evidence/longtail-swe/results.json`, v1.481)"
BARS = [0.6, 0.7, 0.8, 0.9]
FLAVORS = ["cost_effective", "cost_blind"]
SEEDS = 50
CONFIG = {"bars": BARS, "seeds": list(range(SEEDS)), "flavors": FLAVORS,
          "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95}
OPUS, LUNA, SOL, SOL61 = ("anthropic/claude-opus-5.5", "openai/gpt-5.6-luna", "openai/gpt-5.6-sol",
                          "openai/gpt-6.1-sol")
MODELS = [OPUS, LUNA, SOL, SOL61]
STRATEGIES = ["routed", "oracle", "best_on_calibration", "cheapest"]
TASK, ITEMS = "issue_resolution", 194
RATES = ("cleared_rate", "bar_violation_rate", "below_bar_rate")
pending = pytest.mark.xfail(strict=True, raises=FileNotFoundError,
                            reason="evidence/longtail-swe/results.json lands in v1.482")


def load(name, path):
    if not path.is_file():
        raise ModuleNotFoundError(f"no script at {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rs():
    return load("routerbench_results_for_longtail_swe", ROOT / "evidence" / "routerbench" / "results.py")


def committed():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def body():
    text = DESIGN.read_text(encoding="utf-8")
    start = text.index(HEADING)
    return text[start:text.index("\n## 13. ", start)]


def summary_row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"] if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1
    return rows[0]


def join(words):
    words = [str(w) for w in words]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def cells_of(rate):
    """A rate over the 50 seeds of the one task as a count of cells (an exact count over 50)."""
    count = round(rate * SEEDS)
    assert count / SEEDS == rate
    return count


# --- the spec ---------------------------------------------------------------------------------

def test_design_specifies_the_results_file_and_its_bars():
    text = body()
    for phrase in ("bars `0.6 0.7 0.8 0.9`, 50 seeds, `calibration_fraction` 0.5, `min_samples` 30 and confidence 0.95",
                   "would give only `0.8`, one bar",
                   "(12.25: run 0, the 4 models, 1 task, `issue_resolution`, of 194 items, 776 rows)",
                   "`python evidence/longtail-swe/convert.py --out longtail-swe-matrix.jsonl`",
                   "`model-routing evaluate --outcomes longtail-swe-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json"
                   " > longtail-swe-evaluate.json`",
                   "`python evidence/routerbench/results.py --evaluate longtail-swe-evaluate.json"
                   " --out evidence/longtail-swe/results.json`",
                   "so 64 rows, and 4 times 2 times 1 task, 8 rows",
                   "`pytest.mark.xfail(strict=True, raises=FileNotFoundError)`", "(row E26g)", "(row E26h)"):
        assert phrase in text, phrase
    assert "\u2013" not in text and "\u2014" not in text


# --- the committed file -----------------------------------------------------------------------

@pending
def test_committed_results_are_small_and_reduced(rs):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    assert text == json.dumps(rs.reduce(json.loads(text)), indent=2) + "\n"


@pending
def test_committed_results_have_the_config_task_and_models():
    results = committed()
    assert results["config"] == CONFIG
    assert results["tasks"] == {TASK: {"items": ITEMS, "models": MODELS}}


@pending
def test_committed_results_rows_are_unique_routed_and_costed():
    results = committed()
    keys = [(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]]
    assert len(keys) == len(set(keys)) == len(BARS) * len(FLAVORS) * (len(STRATEGIES) + len(MODELS)) == 64
    assert set(keys) == {(b, f, s) for b in BARS for f in FLAVORS for s in STRATEGIES + ["model:" + m for m in MODELS]}
    task_keys = [(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]]
    assert len(task_keys) == len(set(task_keys)) == len(BARS) * len(FLAVORS) * 1 == 8
    assert set(task_keys) == {(b, f, TASK) for b in BARS for f in FLAVORS}
    for r in results["per_task"]:
        assert r["strategy"] == "routed"
        assert sum(r["routed_models"].values()) == SEEDS and set(r["routed_models"]) <= set(MODELS)
        whole = summary_row(results, r["bar"], r["flavor"], "routed")
        assert [r[k] for k in ("success", "cost_usd") + RATES] == [whole[k] for k in ("success", "cost_usd") + RATES]
    assert all(r["cost_usd"] > 0 for r in results["summary"] + results["per_task"])


@pending
def test_committed_cost_blind_is_one_row_above_best_on_calibration():
    results = committed()
    blind = [summary_row(results, bar, "cost_blind", "routed") for bar in BARS]
    assert len({(r["success"], r["cost_usd"]) for r in blind}) == 1
    best = {summary_row(results, bar, flavor, "best_on_calibration")["success"] for bar in BARS for flavor in FLAVORS}
    assert len(best) == 1 and blind[0]["success"] > best.pop()
    boc = summary_row(results, BARS[0], "cost_blind", "best_on_calibration")["success"]
    assert (f"`cost_blind`'s routed row is the same at every bar (success {blind[0]['success']:.3f}), but unlike "
            f"12.24's it is not `best_on_calibration`'s ({boc:.3f})") in body()


@pending
def test_design_bars_bullet_is_the_committed_file():
    results = committed()
    ce = {bar: summary_row(results, bar, "cost_effective", "routed") for bar in BARS}
    phrase = (f"the routed `cost_effective` cleared rate is {ce[0.6]['cleared_rate']:.3f} at 0.6, "
              f"{ce[0.7]['cleared_rate']:.3f} at 0.7, {ce[0.8]['cleared_rate']:.3f} at 0.8 and "
              f"{ce[0.9]['cleared_rate']:.3f} at 0.9. The file of the four bars is "
              f"{RESULTS.stat().st_size:,} bytes, under the 300,000")
    assert phrase in body()


@pending
def test_design_halves_bullet_rates_are_the_committed_file():
    results = committed()
    at = {(bar, flavor): summary_row(results, bar, flavor, "routed") for bar in (0.7, 0.8) for flavor in FLAVORS}
    high = {flavor: at[(0.8, flavor)] for flavor in FLAVORS}
    assert len({(r["cleared_rate"], r["bar_violation_rate"]) for r in high.values()}) == 1
    cleared = cells_of(high["cost_effective"]["cleared_rate"])
    assert high["cost_effective"]["bar_violation_rate"] == 1.0
    ce, cb = at[(0.7, "cost_effective")], at[(0.7, "cost_blind")]
    ce_n, cb_n = cells_of(ce["cleared_rate"]), cells_of(cb["cleared_rate"])
    ce_bad = round(ce["bar_violation_rate"] * ce_n)
    assert ce_bad / ce_n == ce["bar_violation_rate"] and cb["bar_violation_rate"] == 0
    text = body()
    assert (f"clears on {cleared} of the 50 seeds") in text
    assert (f"each of the {cleared} cleared cells is under the bar, a bar-violation rate of "
            f"{high['cost_effective']['bar_violation_rate']:.3f} against the nominal one-sided 0.025") in text
    assert (f"At 0.7 `cost_effective` clears {ce_n} cells and {ce_bad} is under the bar "
            f"({ce['bar_violation_rate']:.3f}); `cost_blind` clears {cb_n} with none under") in text


# --- the pinned files, only with pyarrow and when already cached (the converter's main, once) ----

@pytest.fixture(scope="module")
def real_run(tmp_path_factory):
    cv = load("longtail_swe_convert_for_results", FOLDER / "convert.py")
    pytest.importorskip("pyarrow")
    cache = cv.default_cache_dir()
    if not all((cache / name).is_file() for name in cv.FILES):
        pytest.skip("the pinned files are not in the default cache")
    out = tmp_path_factory.mktemp("longtail-swe-results") / "rows.jsonl"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = cv.main(["--out", str(out)])
    assert code == 0
    report = json.loads(buf.getvalue())
    assert report["rows"] == ITEMS * len(MODELS) and report["tasks"] == {TASK: {"items": ITEMS}}
    with open(out, encoding="utf-8") as f:
        rows = [json.loads(line) for line in f]
    return rows, evaluate(outcomes_from_rows(rows), bars=BARS, seeds=range(SEEDS))


@pytest.fixture(scope="module")
def real_rows(real_run):
    return real_run[0]


@pytest.fixture(scope="module")
def real_result(real_run):
    return real_run[1]


def calibration_counts(rows, seed):
    items = sorted({r["item"] for r in rows})
    half = set(split_items(items, seed)[0])
    counts = {m: sum(r["correct"] for r in rows if r["model"] == m and r["item"] in half) for m in MODELS}
    return counts, len(half)


@pending
def test_real_results_regenerate_byte_identical(rs, real_result):
    reduced = rs.reduce({k: v for k, v in real_result.items() if k != "cells"})
    assert json.dumps(reduced, indent=2) + "\n" == RESULTS.read_text(encoding="utf-8")


def test_real_success_span_and_the_12_17_rule(real_rows):
    hits = {m: [r["correct"] for r in real_rows if r["model"] == m] for m in MODELS}
    assert {m: len(v) for m, v in hits.items()} == {m: ITEMS for m in MODELS}
    rate = {m: sum(v) / len(v) for m, v in hits.items()}
    low, high = min(rate, key=rate.get), max(rate, key=rate.get)
    assert (low, sum(hits[low]), high, sum(hits[high])) == (LUNA, 140, OPUS, 162)
    phrase = (f"run from {rate[low]:.3f} (`{low}`, {sum(hits[low])} of {ITEMS}) to {rate[high]:.3f} "
              f"(`{high}`, {sum(hits[high])} of {ITEMS})")
    assert phrase in body()
    rule = [k / 10 for k in range(math.floor(rate[low] * 10) + 1, math.ceil(rate[high] * 10))]
    assert rule == [0.8] and set(rule) < set(BARS)
    assert min(BARS) < max(BARS[:2]) < rate[low] and rate[high] < max(BARS)
    assert f"the model's rate on the pool is {rate[OPUS]:.3f}" in body()


def test_real_calibration_halves_are_the_design_sizes(real_rows):
    items = sorted({r["item"] for r in real_rows})
    assert len(items) == ITEMS
    sizes = [len(split_items(items, seed)[0]) for seed in range(SEEDS)]
    assert min(sizes) >= CONFIG["min_samples"]
    assert (f"calibration half holds {min(sizes)} to {max(sizes)} of the {ITEMS} items, so `min_samples` 30 is met "
            f"on every seed") in body()


def test_real_cleared_seeds_at_0_8_are_complementary(real_rows, real_result):
    for flavor in FLAVORS:
        cells = [c for c in real_result["cells"] if c["bar"] == 0.8 and c["flavor"] == flavor and c["cleared"]]
        assert {c["models"]["routed"] for c in cells} == {OPUS}
        assert all(c["success"]["routed"] < 0.8 for c in cells)
        seeds = [c["seed"] for c in cells]
        if flavor == "cost_effective":
            first = seeds
        assert seeds == first
    pool = sum(r["correct"] for r in real_rows if r["model"] == OPUS)
    cal, held, rates = [], [], []
    for cell in [c for c in real_result["cells"] if c["bar"] == 0.8 and c["flavor"] == "cost_effective" and c["cleared"]]:
        counts, size = calibration_counts(real_rows, cell["seed"])
        kept = pool - counts[OPUS]
        assert kept / cell["held_out_items"] == cell["success"]["routed"] and size + cell["held_out_items"] == ITEMS
        cal.append(f"{counts[OPUS]} of {size}")
        held.append(f"{kept} of {cell['held_out_items']}")
        rates.append(f"{cell['success']['routed']:.3f}")
    phrase = (f"clears on {len(first)} of the 50 seeds, {join(first)}, with {join(cal)} resolved, which leave it "
              f"{join(held)} held out ({join(rates)})")
    assert phrase in body()


def test_real_tie_seeds_split_cost_blind_from_best_on_calibration(real_rows, real_result):
    cells = [c for c in real_result["cells"] if c["bar"] == 0.9 and c["flavor"] == "cost_blind"]
    assert len(cells) == SEEDS and not any(c["cleared"] for c in cells)
    apart = [c for c in cells if c["models"]["routed"] != c["models"]["best_on_calibration"]]
    for cell in apart:
        counts, _ = calibration_counts(real_rows, cell["seed"])
        assert (cell["models"]["routed"], cell["models"]["best_on_calibration"]) == (OPUS, SOL61)
        assert counts[OPUS] == counts[SOL61] == max(counts.values())
    seeds = [c["seed"] for c in apart]
    assert (f"on {len(seeds)} seeds, {join(seeds)}, `{OPUS}` and `{SOL61}` tie on the calibration count") in body()
    blind = {c["models"]["routed"] for c in real_result["cells"] if c["flavor"] == "cost_blind"
             and c["seed"] in seeds}
    assert blind == {OPUS}
