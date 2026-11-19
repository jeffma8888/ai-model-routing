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

From v1.483 (row E26g) the module also builds ``evidence/longtail-swe/RESULTS.md`` and checks the
folder README: the opening, Results, Reading it and Regenerate sections are built whole from the
committed file, ``models.json``, ``FILES`` and the 12.25 report's counts, which the cached-file test
pins. The tests that read the two files were committed before them under strict xfail
(``FileNotFoundError``), removed by the commit that adds them (v1.484).
"""

import contextlib
import importlib.util
import io
import json
import math
import re
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
                   "`pytest.mark.xfail(strict=True, raises=FileNotFoundError)`", "- RESULTS.md (v1.483, row E26g): ",
                   "(row E26h)"):
        assert phrase in text, phrase
    assert "\u2013" not in text and "\u2014" not in text


# --- the committed file -----------------------------------------------------------------------

def test_committed_results_are_small_and_reduced(rs):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    assert text == json.dumps(rs.reduce(json.loads(text)), indent=2) + "\n"


def test_committed_results_have_the_config_task_and_models():
    results = committed()
    assert results["config"] == CONFIG
    assert results["tasks"] == {TASK: {"items": ITEMS, "models": MODELS}}


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
        assert all(type(n) is int and n >= 0 for n in r["routed_models"].values())  # review iter-344 should-fix 1
        whole = summary_row(results, r["bar"], r["flavor"], "routed")
        assert [r[k] for k in ("success", "cost_usd") + RATES] == [whole[k] for k in ("success", "cost_usd") + RATES]
    assert all(r["cost_usd"] > 0 for r in results["summary"] + results["per_task"])


def test_committed_cost_blind_has_one_success_and_cost_above_best_on_calibration():
    results = committed()
    blind = [summary_row(results, bar, "cost_blind", "routed") for bar in BARS]
    assert len({(r["success"], r["cost_usd"]) for r in blind}) == 1
    best = {summary_row(results, bar, flavor, "best_on_calibration")["success"] for bar in BARS for flavor in FLAVORS}
    assert len(best) == 1 and blind[0]["success"] > best.pop()
    boc = summary_row(results, BARS[0], "cost_blind", "best_on_calibration")["success"]
    assert (f"`cost_blind`'s routed success and cost are the same at every bar (success {blind[0]['success']:.3f}; "
            f"its rates are not, v1.483, review iter-344 nit 1), but unlike 12.24's they are not "
            f"`best_on_calibration`'s ({boc:.3f})") in body()
    assert len({(r["cleared_rate"], r["bar_violation_rate"]) for r in blind}) > 1


def test_design_bars_bullet_is_the_committed_file():
    results = committed()
    ce = {bar: summary_row(results, bar, "cost_effective", "routed") for bar in BARS}
    phrase = (f"the routed `cost_effective` cleared rate is {ce[0.6]['cleared_rate']:.3f} at 0.6, "
              f"{ce[0.7]['cleared_rate']:.3f} at 0.7, {ce[0.8]['cleared_rate']:.3f} at 0.8 and "
              f"{ce[0.9]['cleared_rate']:.3f} at 0.9. The file of the four bars is "
              f"{RESULTS.stat().st_size:,} bytes, under the 300,000")
    assert phrase in body()


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
    return rows, evaluate(outcomes_from_rows(rows), bars=BARS, seeds=range(SEEDS)), report


@pytest.fixture(scope="module")
def real_rows(real_run):
    return real_run[0]


@pytest.fixture(scope="module")
def real_result(real_run):
    return real_run[1]


@pytest.fixture(scope="module")
def real_report(real_run):
    return real_run[2]


def calibration_counts(rows, seed):
    items = sorted({r["item"] for r in rows})
    half = set(split_items(items, seed)[0])
    counts = {m: sum(r["correct"] for r in rows if r["model"] == m and r["item"] in half) for m in MODELS}
    return counts, len(half)


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


# --- v1.483 (row E26g): RESULTS.md and the folder README (DESIGN 12.26 RESULTS.md bullets) --------

RESULTS_MD = FOLDER / "RESULTS.md"
EVIDENCE_README = FOLDER / "README.md"
REGISTRY = ROOT / "model_routing" / "data" / "models.json"
DATASET = "nebius/Longtail-SWE-trajectories"
DATASET_URL = "https://huggingface.co/datasets/" + DATASET
REVISION = "dfd6075c56b7841b9c254cc70a57e39c1df0076c"
TABLE_COMMAND = "$ python evidence/routerbench/results.py --table evidence/longtail-swe/results.json"
INSTALL = 'python -m pip install -e ".[evidence]"\n'
CONVERT = "python evidence/longtail-swe/convert.py --out longtail-swe-matrix.jsonl\n"
REGENERATE = (
    "```bash\n" + INSTALL + CONVERT +
    "model-routing evaluate --outcomes longtail-swe-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json"
    " > longtail-swe-evaluate.json\n"
    "python evidence/routerbench/results.py --evaluate longtail-swe-evaluate.json"
    " --out evidence/longtail-swe/results.json\n"
    "python evidence/routerbench/results.py --table evidence/longtail-swe/results.json\n"
    "```\n")
MATRIX_BLOCK = "```bash\n" + INSTALL + CONVERT + "```\n"
# The dataset card (README.md) and LEGAL.md at REVISION, read 2026-11-18: (bytes, sha256), the card's
# licence line and the first two sentences of its License section, and the second paragraph of each of
# LEGAL.md's sections 1, 2 and 3, each joined onto one line.
CARD = (5537, "5c6bc2f63f280f468c8551c712b4193ea1cb85e7b3f09df34499c37b72454c2d")
CARD_LICENCE = "`license: cc-by-4.0`"
CARD_TEXT = ("The dataset compilation is licensed under CC BY 4.0. Source repositories retain their own licenses, "
             "and model and tool outputs may be subject to provider terms.")
LEGAL = (3853, "818eae55bd8d9ec60e743b870bad10437ee9f56484d03f6e0896f868ee9240a3")
LEGAL_URL = f"{DATASET_URL}/blob/{REVISION}/LEGAL.md"
LEGAL_TEXT = (
    "This license applies to the dataset compilation and to original material authored by Nebius. It does "
    "**not** override or extend to the rights in third-party material referenced or included within the "
    "dataset, which remain governed by their own respective terms (see Sections 2 and 3).",
    "Material originating from a source repository (including code, issue text, diffs, and patches that "
    "appear within trajectories) continues to be governed by that repository's license. Users who reuse, "
    "modify, or redistribute such material are responsible for identifying and complying with the "
    "applicable upstream license for each instance.",
    "These generated outputs may be subject to the **usage terms, license agreements, acceptable-use "
    "policies, and output-ownership or redistribution provisions** of the respective model providers. Such "
    "terms vary between providers and may change over time. Nebius makes **no representation or warranty** "
    "as to the licensing status, ownership, or permitted uses of any third-party model output contained in "
    "this dataset.")
# v1.492 (row E26j, review iter-345 nit 5): the third paragraph of LEGAL.md section 3, joined onto one line,
# names evaluation use and holds two em dashes, so RESULTS.md paraphrases it in a bullet of its own after the
# three quotes instead of quoting it; the test keeps the paragraph only to check the paraphrase is not a copy.
LEGAL_S3_P3 = (
    "Before using this dataset \u2014 particularly for training, fine-tuning, evaluation, or redistribution "
    "\u2014 users are solely responsible for reviewing and complying with the applicable terms of every model "
    "and tool whose outputs may be present. If you are uncertain whether a particular use is permitted, seek "
    "your own legal counsel.")
LEGAL_PARAPHRASE = (
    "- LEGAL.md's section 3 also asks (paraphrased, not quoted) that anyone using the dataset, above all to "
    "train, fine-tune, evaluate or redistribute, first check and follow the terms of each model or tool whose "
    "output it may hold")
SHARED_RUN = 4  # the paraphrase may share no run of this many words or more with LEGAL_S3_P3
CC_BY = "https://creativecommons.org/licenses/by/4.0/"
PAPER = ("Longtail-SWE: High-Quality SWE Tasks for Underrepresented Languages",
         "https://arxiv.org/abs/2611.10304")
# The 12.25 Default output on the four pinned files at run 0 (test_real_report_is_the_readme_constants pins it).
LANGUAGES = {"Clojure": 12, "Dart": 13, "Elixir": 22, "Erlang": 12, "F#": 16, "Haskell": 13, "Julia": 26,
             "Kotlin": 11, "Lua": 13, "OCaml": 12, "R": 14, "Scala": 17, "Swift": 13}
RESOLVED = {OPUS: 162, LUNA: 140, SOL: 152, SOL61: 155}
DROPPED = 8
UNSCORED = {SOL61: ["babashka__cli-162"]}
SECTIONS = ["## Source and licence", "## Results", "## Reading it", "## Regenerate"]
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd"]
NOT_KEPT = "no prompt, message, tool call, patch or token count"
HOME = re.compile(r"(?m)(^|[\s(])/(Users|home)/")


def results_md():
    return RESULTS_MD.read_text(encoding="utf-8")


def evidence_readme():
    return EVIDENCE_README.read_text(encoding="utf-8")


def section(text, heading):
    """The body of one `## ` section, between its heading line and the next `## ` heading."""
    start = text.index("\n" + heading + "\n") + len(heading) + 2
    end = text.find("\n## ", start)
    return text[start:end if end >= 0 else len(text)].strip("\n")


def name(row):
    return row["strategy"][len("model:"):]


def single_models(results):
    """The model rows of the first (bar, flavor), with the best (12.7) and the cheapest (12.15)."""
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == first and r["strategy"].startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    cheapest = min(models, key=lambda r: (r["cost_usd"], -r["success"], r["strategy"]))
    return models, best, cheapest


def beats_statement(results):
    """The 12.15 sentence on routed rows against single models, `single models` for `agents`."""
    config = results["config"]
    models, _, _ = single_models(results)
    beaten = []
    for m in models:
        rows = []
        for bar in config["bars"]:
            for flavor in config["flavors"]:
                r = summary_row(results, bar, flavor, "routed")
                if (r["success"] >= m["success"] and r["cost_usd"] <= m["cost_usd"]
                        and (r["success"] > m["success"] or r["cost_usd"] < m["cost_usd"])):
                    rows.append(f"bar {bar} `{flavor}`")
        if rows:
            beaten.append(f"`{name(m)}` (by " + ", ".join(rows) + ")")
    if not beaten:
        return (f"No routed row beats any of the {len(models)} single models on both counts: "
                f"against each of them, every routed row in the table has lower held-out success "
                f"or a higher cost.")
    return "Routed rows beat these single models on both counts: " + "; ".join(beaten) + "."


def prices():
    rows = {m["id"]: m for m in json.loads(REGISTRY.read_text(encoding="utf-8"))["models"]}
    return {m: (rows[m]["price_in"], rows[m]["price_out"]) for m in MODELS}


def plural(n, word):
    return f"{n} {word if n == 1 else word + 's'}"


def the_task(results):
    (task, info), = results["tasks"].items()
    assert sum(LANGUAGES.values()) == info["items"], "the languages do not add up to the items"
    return task, info["items"], info["models"]


def opening(results):
    """The two paragraphs before `## Source and licence`, every count from the file or the 12.25 report."""
    config = results["config"]
    seeds, bars = len(config["seeds"]), config["bars"]
    task, items, models = the_task(results)
    low = min(RESOLVED, key=lambda m: (RESOLVED[m], m))
    high = max(RESOLVED, key=lambda m: (RESOLVED[m], m))
    lo, hi = RESOLVED[low] / items, RESOLVED[high] / items
    rule = [k / 10 for k in range(math.floor(lo * 10) + 1, math.ceil(hi * 10))]
    assert rule != bars and set(rule) < set(bars), "the bars are the 12.17 rule's"
    under = [b for b in bars if b < lo]
    above = [b for b in bars if b > hi]
    assert under and above and len(under) + len(rule) + len(above) == len(bars), "a bar sits inside the span"
    return (
        f"What `model-routing evaluate` measures on {DATASET}, a public release of coding-agent runs on issues "
        f"of open-source repositories: {join(f'`{m}`' for m in models)}, each run by the release's `swelike` "
        f"scaffold on the same {items} issues in {len(LANGUAGES)} languages, as one routing task, `{task}`. A "
        f"success is a run whose saved evaluation marks the issue `resolved` by the task's own tests, at run 0 "
        f"of the release's three runs per issue and model, and the cost of a run is its input and output "
        f"tokens at the registry's list prices with no cache discount, an estimate and not a bill (DESIGN "
        f"12.25). See [README.md](README.md) for what the converter reads and keeps, and DESIGN 12.26 for this "
        f"file's contract. For each of {seeds} seeds the {items} issues are split in half by a seeded hash; the "
        f"router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best "
        f"model on the calibration half, the cheapest model and each single model (DESIGN 12.3). The file "
        f"behind every number here is [results.json](results.json): the summary rows and the routed per-task "
        f"rows, including how many of the {seeds} seeds routed to each model. It is made by the RouterBench "
        f"results script, `evidence/routerbench/results.py`, which does not depend on the dataset.\n\n"
        f"The bars are {join(bars)}, the bars of the RouterBench results. On the pool of {items} issues the "
        f"models resolve from {RESOLVED[low]} (`{low}`, {lo:.3f}) to {RESOLVED[high]} (`{high}`, {hi:.3f}), so "
        f"every tenth strictly inside that span would give only {join(rule)} (DESIGN 12.26), too few bars to "
        f"show a trade of success for cost as the bar moves. The others are kept, {join(under)} under every "
        f"model's rate on the pool and {join(above)} above it, and since a model clears on its calibration "
        f"bound, not its rate, they give different rows.")


def results_section(rs, results):
    """The `## Results` section: the column sentence, the table block and the single-model sentence."""
    config = results["config"]
    _, best, _ = single_models(results)
    seeds, ntasks = len(config["seeds"]), len(results["tasks"])
    return (
        f"Routed rows: `success` is the share of held-out issues whose run is `resolved`, `cost_usd` is the "
        f"estimated cost of those runs (both averaged over the {seeds} seeds), `vs_best_model` is that cost "
        f"divided by the cost of the best single model (`{name(best)}`), `cleared_rate` is the share of the "
        f"{seeds * ntasks} (task, seed) cells where some model cleared the bar on the calibration half, and "
        f"`bar_violation_rate` is the share of cleared cells whose held-out success fell below the bar, `-` "
        f"where no cell cleared. Baseline rows do not depend on the bar or the flavor.\n\n"
        f"```text\n{TABLE_COMMAND}\n{rs.table(results)}\n```\n\n{beats_statement(results)}")


def regenerate_section(cv):
    """The `## Regenerate` section: the five commands and the download line, its bytes from FILES."""
    return (f"{REGENERATE}\nThe converter downloads the four pinned files "
            f"({sum(size for size, _ in cv.FILES.values()):,} bytes) into "
            f"`~/.cache/ai-model-routing-evidence/longtail-swe/` on its first run and checks each against its "
            f"pinned size and sha256; the `evidence` extra installs `pyarrow`, the parquet reader it needs, and "
            f"converting the cached files takes about 4 seconds. The `evidence` workflow reruns these commands "
            f"on GitHub and fails if `results.json` changes by a byte (`DESIGN.md` 12.13, v1.489), while the "
            f"test suite rebuilds `results.json` only where `pyarrow` is installed and the four files are "
            f"cached.")


def reading_bullets(results):
    """The `## Reading it` section of RESULTS.md, built whole from the committed file (12.26 v1.483)."""
    config = results["config"]
    seeds, bars, b0, flavors = len(config["seeds"]), config["bars"], config["bars"][0], config["flavors"]
    task, items, _ = the_task(results)
    models, best, cheapest = single_models(results)
    ce = {bar: summary_row(results, bar, "cost_effective", "routed") for bar in bars}
    cb = [summary_row(results, bar, "cost_blind", "routed") for bar in bars]
    assert len({(r["success"], r["cost_usd"]) for r in cb}) == 1, "cost_blind's success or cost differs between bars"
    picks = {(r["bar"], r["flavor"]): r["routed_models"] for r in results["per_task"]}
    assert all(picks[(bar, "cost_blind")] == picks[(b0, "cost_blind")] for bar in bars), \
        "cost_blind's seeds per model differ between bars"
    boc = summary_row(results, b0, "cost_effective", "best_on_calibration")
    oracle = summary_row(results, b0, "cost_effective", "oracle")

    def cleared(row):
        n = row["cleared_rate"] * seeds
        assert abs(n - round(n)) < 1e-9
        return round(n)

    def share(row):
        return row["cost_usd"] / best["cost_usd"]

    def routing(counts):
        order = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
        return join(f"{plural(n, 'seed')} to `{m}`" for m, n in order)

    more = "more" if ce[b0]["success"] > cheapest["success"] else "no more"
    gap = cb[0]["success"] - best["success"]
    assert gap != 0, "cost_blind ties the best single model"
    d = cb[0]["success"] - boc["success"]
    if d == 0:
        against = "the held-out success of `best_on_calibration`"
    elif d > 0:
        # True on this file: DESIGN 12.26 names the 6 tie seeds, and the cached-file test
        # test_real_tie_seeds_split_cost_blind_from_best_on_calibration pins them (review iter-345 nit 3).
        against = (f"{d:.4f} above `best_on_calibration`'s {boc['success']:.3f}: on seeds where two models tie on "
                   f"the calibration count, `best_on_calibration` takes the cheaper one and `cost_blind` the lower "
                   f"model ID (DESIGN 12.26)")
    else:
        against = f"{-d:.4f} below `best_on_calibration`'s {boc['success']:.3f}"
    violated = []
    for flavor in flavors:
        for bar in bars:
            row = summary_row(results, bar, flavor, "routed")
            v, n = row["bar_violation_rate"], cleared(row)
            if v:
                assert abs(v * n - round(v * n)) < 1e-9
                violated.append(f"{v:.3f} at bar {bar} (`{flavor}`) is {round(v * n)} of {n} cleared "
                                f"{'cell' if n == 1 else 'cells'}")
    nominal = (1 - config["confidence"]) / 2
    full = [bar for bar in bars if all(summary_row(results, bar, f, "routed")["bar_violation_rate"] == 1.0
                                       for f in flavors)]
    assert full, "no bar has every cleared cell under it in both flavors"
    counts = []
    for bar in full:
        n = {cleared(summary_row(results, bar, f, "routed")) for f in flavors}
        assert len(n) == 1, "the flavors clear different numbers of cells"
        count = n.pop()  # the bars named, review iter-345 should-fix 1
        counts.append(f"{count} of {count} cells" + (f" at bar {bar}" if len(full) > 1 else ""))
    most = max(RESOLVED, key=lambda m: (RESOLVED[m], m))
    assert RESOLVED[most] / items > max(full), "no model's rate on the pool is above the bar"
    second = max((m for m in models if m is not best), key=lambda r: (r["success"], -r["cost_usd"], r["strategy"]))
    reach = [bar for bar in bars if ce[bar]["success"] >= second["success"]]
    assert reach, "no routed cost_effective row reaches the second-best model's success"
    at = ce[reach[0]]
    assert all(ce[bar]["cost_usd"] > second["cost_usd"] for bar in reach), \
        "a routed cost_effective row reaches the second-best model's success at no more than its cost"
    top = max(r["success"] for r in results["summary"] if r["strategy"] == "routed")
    price = prices()
    unscored = [(m, i) for m, ids in sorted(UNSCORED.items()) for i in ids]
    bullets = [
        f"`cost_effective`: at bar {b0} a model clears on {cleared(ce[b0])} of the {seeds} seeds, and the router "
        f"spends {share(ce[b0]):.3f} of the cost of the best single model, `{name(best)}`, for a held-out "
        f"success of {ce[b0]['success']:.3f}, against {best['success']:.3f} for that model. Always calling the "
        f"cheapest model, `{name(cheapest)}`, reaches {cheapest['success']:.3f} at {cheapest['cost_usd']:.4f} "
        f"USD, so at bar {b0} the router pays {ce[b0]['cost_usd'] / cheapest['cost_usd']:.3f} of that cost for "
        f"{more} held-out success, routing {routing(picks[(b0, 'cost_effective')])}",
        "At the higher bars `cost_effective` reaches " + "; ".join(
            f"{ce[bar]['success']:.3f} at {share(ce[bar]):.3f} of the best single model's cost at bar {bar}, "
            f"{plural(cleared(ce[bar]), 'seed')} cleared" for bar in bars[1:])
        + "; a seed on which no model clears falls back to the model with the highest Wilson lower bound on its "
          "calibration half (`on_no_model=\"best_available\"`, DESIGN 5.3)",
        f"`cost_blind` reaches {cb[0]['success']:.3f} at {share(cb[0]):.3f} of the best single model's cost at "
        f"every bar, {abs(gap):.4f} {'above' if gap > 0 else 'below'} that model's held-out success, routing "
        f"{routing(picks[(b0, 'cost_blind')])} at every bar, {against}",
        ("Bar violations: " + "; ".join(violated) + f", against a nominal one-sided {nominal:.3f} for the "
         f"{config['confidence']} Wilson bound (DESIGN 12.3)") if violated
        else "Bar violations: none, in any row (DESIGN 12.3)",
        f"Complementary halves: with one task, each seed's two halves split one pool of {items} issues, so a "
        f"model's held-out count is its count on the pool less its calibration count. At "
        f"{'bar' if len(full) == 1 else 'bars'} {join(full)} every cleared cell is under the bar in both "
        f"flavors, {join(counts)}, though `{most}` resolves {RESOLVED[most]} of the "
        f"{items} issues ({RESOLVED[most] / items:.3f}) on the pool: a calibration half lucky enough to clear "
        f"leaves an unlucky held-out half, the re-split correlation that DESIGN 12.3 names, and DESIGN 12.26 "
        f"gives the seeds and their counts",
        f"`{name(second)}` alone reaches {second['success']:.3f} at {share(second):.3f} of the best single model's "
        f"cost, while the first routed `cost_effective` row at or above that success, at bar {reach[0]}, reaches "
        f"{at['success']:.3f} at {share(at):.3f}: {at['success'] - second['success']:.4f} more held-out success "
        f"for {at['cost_usd'] / second['cost_usd']:.3f} times that model's cost",
        f"The per-item oracle reaches {oracle['success']:.3f} at {share(oracle):.3f} of the best single model's "
        f"cost, while the highest routed success of either flavor at any bar is {top:.3f}: with one task, each "
        f"seed's router sends every held-out issue to one model, so it cannot pick per issue",
        f"Each cost is a run's input tokens, cached ones included, at the model's input price and its output "
        f"tokens, reasoning included, at its output price, with no cache discount (DESIGN 12.25): an estimate at "
        f"list prices and not a bill, since the vendors' cache rates, which the registry does not hold, would "
        f"lower it wherever cache reads outweigh a cache-write premium. The prices are "
        + join(f"`{m}` {price[m][0]:g} and {price[m][1]:g}" for m in MODELS)
        + " USD per million input and output tokens in `models.json`",
        f"One task of {items} issues in {len(LANGUAGES)} languages at run 0 alone, of the release's three runs "
        f"per issue and model (DESIGN 12.26 leaves runs 1 and 2 out of this file); the {DROPPED} issues whose "
        f"initial statement differs from the release's are dropped for every model, and the "
        f"{plural(len(unscored), 'run')} with no saved result ("
        + join(f"`{m}` on `{i}`" for m, i in unscored)
        + f") {'counts' if len(unscored) == 1 else 'count'} as a miss with its charge (DESIGN 12.25)",
        f"Size: the committed file, {RESULTS.stat().st_size:,} bytes, holds only the summary and the routed "
        f"per-task rows (DESIGN 12.7)"]
    return "\n".join("- " + b for b in bullets)


def models_table():
    price = prices()
    rows = ["| model | input | output | resolved |", "| --- | ---: | ---: | ---: |"]
    rows += [f"| `{m}` | {price[m][0]:g} | {price[m][1]:g} | {RESOLVED[m]} |" for m in MODELS]
    return "\n".join(rows) + "\n"


def language_table():
    rows = ["| language | items |", "| --- | ---: |"]
    rows += [f"| {lang} | {n} |" for lang, n in sorted(LANGUAGES.items())]
    return "\n".join(rows) + "\n"


def test_results_md_shows_the_table_of_the_committed_results(rs):
    block = "```text\n" + TABLE_COMMAND + "\n" + rs.table(committed()) + "\n```\n"
    assert block in results_md()


def test_results_md_source_and_licence_strings():
    full = results_md()
    text = section(full, "## Source and licence")
    for needle in [DATASET_URL, f"[`{REVISION}`]({DATASET_URL}/tree/{REVISION})", CARD_LICENCE, CARD_TEXT,
                   f"{CARD[0]:,} bytes, sha256 `{CARD[1]}`", f"[LEGAL.md]({LEGAL_URL})",
                   f"{LEGAL[0]:,} bytes, sha256 `{LEGAL[1]}`", "read on 2026-11-18", CC_BY,
                   f"[{PAPER[0]}]({PAPER[1]})", "(README.md)", "(results.json)",
                   # review iter-345 should-fix 2: the attribution's parts and the no-part sentence
                   f"these results derive from Longtail-SWE Trajectories by Nebius, {DATASET} at revision `{REVISION}`, "
                   f"licensed under CC BY 4.0. Changes made: ", "This repo commits no part of the dataset: ",
                   "no prompt, message, tool call, patch or trajectory text of the release"]:
        assert needle in text, needle
    for quote in LEGAL_TEXT:
        assert f'  - "{quote}"\n' in text + "\n", quote[:40]
    cv = load("longtail_swe_convert_for_md", FOLDER / "convert.py")
    for file, (size, sha256) in cv.FILES.items():
        assert f"`{file}`, {size:,} bytes, sha256 `{sha256}`" in text, file
    assert full.isascii() and "\u2013" not in full and "\u2014" not in full
    assert not HOME.search(full)


def _words(text):
    return re.findall(r"[a-z0-9]+(?:[-'][a-z0-9]+)*", text.lower())


def _longest_shared_run(a, b):
    """The length of the longest run of consecutive words that the word lists a and b share."""
    best, prev = 0, [0] * (len(b) + 1)
    for x in a:
        cur = [0] * (len(b) + 1)
        for j, y in enumerate(b, 1):
            if x == y:
                cur[j] = prev[j - 1] + 1
                best = max(best, cur[j])
        prev = cur
    return best


def test_results_md_paraphrases_legal_section_3_evaluation_use():
    """v1.492 (row E26j): the paraphrase is a bullet of its own right after the third quote, not a quote."""
    text = section(results_md(), "## Source and licence") + "\n"
    assert f'  - "{LEGAL_TEXT[2]}"\n{LEGAL_PARAPHRASE}\n' in text
    assert text.count(LEGAL_PARAPHRASE) == 1 and '"' not in LEGAL_PARAPHRASE
    for use in ("train", "fine-tune", "evaluate", "redistribute"):
        assert use in _words(LEGAL_PARAPHRASE), use
    assert _longest_shared_run(_words(LEGAL_PARAPHRASE), _words(LEGAL_S3_P3)) < SHARED_RUN
    assert _longest_shared_run(_words("a b c d e"), _words("x b c d y")) == 3


def test_results_md_opening_results_reading_and_regenerate_are_built(rs):
    text, results = results_md(), committed()
    cv = load("longtail_swe_convert_for_sections", FOLDER / "convert.py")
    head = "# Longtail-SWE results\n\n"
    assert text.startswith(head)
    assert text[len(head):text.index("\n## Source and licence\n")].strip("\n") == opening(results)
    assert section(text, "## Results") == results_section(rs, results)
    assert section(text, "## Reading it") == reading_bullets(results)
    assert section(text, "## Regenerate") == regenerate_section(cv)


def test_results_md_sections_in_order():
    heads = [line for line in results_md().split("\n") if line.startswith("## ")]
    assert heads == SECTIONS


def test_evidence_readme_states_the_source_models_languages_and_row_keys():
    text = evidence_readme()
    assert "(RESULTS.md)" in text and "(results.json)" in text
    for needle in [DATASET_URL, REVISION, CARD_LICENCE, MATRIX_BLOCK, NOT_KEPT, models_table(), language_table(),
                   f"{ITEMS} items in all, {ITEMS * len(MODELS)} rows ({len(MODELS)} per item)",
                   f"the {DROPPED} issues whose initial statement", "`babashka__cli-162`",
                   f"bars {BARS[0]} to {BARS[-1]} over {SEEDS} seeds"]:
        assert needle in text, needle
    cv = load("longtail_swe_convert_for_readme", FOLDER / "convert.py")
    for file, (size, sha256) in cv.FILES.items():
        assert f"`{file}`, {size:,} bytes, sha256 `{sha256}`" in text, file
    for key in ROW_KEYS:
        assert f"`{key}`" in text, key
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text
    assert not HOME.search(text)


def test_reading_builder_follows_the_file():
    results = committed()
    built = reading_bullets(results)
    assert built.count("\n- ") == 9
    assert ("`openai/gpt-6.1-sol` alone reaches 0.804 at 0.205 of the best single model's cost, while the first "
            "routed `cost_effective` row at or above that success, at bar 0.7, reaches 0.805 at 0.576") in built
    assert "above `best_on_calibration`'s 0.823" in built
    assert "At bar 0.8 every cleared cell is under the bar in both flavors, 4 of 4 cells, though" in built
    tied = json.loads(json.dumps(results))
    boc = summary_row(tied, BARS[0], "cost_effective", "best_on_calibration")["success"]
    for bar in BARS:
        summary_row(tied, bar, "cost_blind", "routed")["success"] = boc
    assert "the held-out success of `best_on_calibration`" in reading_bullets(tied)
    fake = json.loads(json.dumps(results))
    summary_row(fake, BARS[-1], "cost_blind", "routed")["success"] -= 0.001
    with pytest.raises(AssertionError, match="differs between bars"):
        reading_bullets(fake)
    cheap = json.loads(json.dumps(results))
    summary_row(cheap, 0.7, "cost_effective", "routed")["cost_usd"] = 1.0
    with pytest.raises(AssertionError, match="no more than its cost"):
        reading_bullets(cheap)
    later = json.loads(json.dumps(results))
    summary_row(later, 0.9, "cost_effective", "routed")["cost_usd"] = 1.0
    with pytest.raises(AssertionError, match="no more than its cost"):
        reading_bullets(later)


def test_opening_builder_follows_the_file():
    fake = json.loads(json.dumps(committed()))
    fake["config"]["seeds"] = list(range(51))
    assert "For each of 51 seeds" in opening(fake) and "how many of the 51 seeds" in opening(fake)
    assert "would give only 0.8 (DESIGN 12.26)" in opening(committed())
    fake["config"]["bars"] = [0.8]
    with pytest.raises(AssertionError, match="12.17 rule"):
        opening(fake)


def test_real_report_is_the_readme_constants(real_report):
    assert real_report["languages"] == LANGUAGES
    assert len(real_report["dropped_statement"]) == DROPPED
    assert real_report["resolved"] == RESOLVED
    assert {m: ids for m, ids in real_report["unscored"].items() if ids} == UNSCORED
