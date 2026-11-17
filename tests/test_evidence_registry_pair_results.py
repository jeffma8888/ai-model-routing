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
tests read only DESIGN.md and the pinned files. From v1.435 (row E24d) the RESULTS.md and evidence
README tests build the Reading it and Family-held check sections whole from the committed file and the
Results block of research/registry-pair.md; the ones that read either file were committed before them
under strict xfail (``FileNotFoundError``), removed by the commit that adds both (v1.436).
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
                   "`pytest.mark.xfail(strict=True, raises=FileNotFoundError)`", "RESULTS.md (v1.435, row E24d)"):
        assert phrase in text, phrase
    assert "\u2013" not in text and "\u2014" not in text


# --- the committed file -----------------------------------------------------------------------

def test_committed_results_are_small_and_reduced(rs):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    assert text == json.dumps(rs.reduce(json.loads(text)), indent=2) + "\n"


def test_committed_results_have_the_config_tasks_and_models():
    results = committed()
    assert results["config"] == CONFIG
    assert results["tasks"] == {task: {"items": n, "models": MODELS} for task, n in ITEMS.items()}
    assert list(results["tasks"]) == sorted(ITEMS)


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


def test_committed_korbench_logic_never_clears_and_falls_back():
    rows = [r for r in committed()["per_task"] if r["task"] == "korbench/logic"]
    assert len(rows) == len(BARS) * len(FLAVORS) and all(r["cleared_rate"] == 0 for r in rows)
    picks = {json.dumps(r["routed_models"], sort_keys=True) for r in rows}
    assert len(picks) == 1
    pick = rows[0]["routed_models"]
    assert (f"takes `{LUNA}` on {pick[LUNA]} seeds and `{SOL}` on {pick[SOL]};") in body()


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
def real_run(tmp_path_factory):
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
        return report, [json.loads(line) for line in f]


@pytest.fixture(scope="module")
def real_rows(real_run):
    return real_run[1]


def without_cells(result):
    return {k: v for k, v in result.items() if k != "cells"}


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
    assert SPAN == {"low": (LUNA, "mmlupro/law", 304, 428), "high": hi, "high_pairs": len(full), "high_tasks": len(tasks)}
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


# --- RESULTS.md and the evidence README (DESIGN 12.24 v1.435, row E24d) -----------------------

RESULTS_MD = FOLDER / "RESULTS.md"
EVIDENCE_README = FOLDER / "README.md"
NOTE = ROOT / "research" / "registry-pair.md"
REGISTRY = ROOT / "model_routing" / "data" / "models.json"
DATASET_URL = "https://huggingface.co/datasets/superlinked/train-a-router-reasoning"
REVISION = "63336f25fc54597a8e161a7245613f91bd60177e"
TABLE_COMMAND = "$ python evidence/routerbench/results.py --table evidence/registry-pair/results.json"
REGENERATE = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/registry-pair/convert.py --out registry-pair-matrix.jsonl\n"
    "model-routing evaluate --outcomes registry-pair-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json"
    " > registry-pair-evaluate.json\n"
    "python evidence/routerbench/results.py --evaluate registry-pair-evaluate.json"
    " --out evidence/registry-pair/results.json\n"
    "python evidence/routerbench/results.py --table evidence/registry-pair/results.json\n"
    "```\n")
MATRIX_BLOCK = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/registry-pair/convert.py --out registry-pair-matrix.jsonl\n"
    "```\n")
# The dataset card (README.md) at REVISION, 4,824 bytes, read 2026-11-16: its two licence metadata
# lines, its `## Licenses` paragraph, the five rows of its component table and the paragraph after
# it, each paragraph joined onto one line.
CARD_SHA256 = "8d707ef4ee5bf8b272335e4561294628fc0072c2122bf3ded4c3cb349ecad0eb"
CARD_META = ("`license: other`", "`license_name: mixed-mit-and-apache-2.0`")
LICENSES = ("This is a collection with multiple upstream licenses, not a relicensing of its components. "
            "Preserve the included notices when redistributing them.")
COMPONENTS = [
    ("MMLU-Pro questions", "[TIGER-Lab/MMLU-Pro](https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro), MIT"),
    ("BIG-Bench Hard questions",
     "[suzgunmirac/BIG-Bench-Hard](https://github.com/suzgunmirac/BIG-Bench-Hard), MIT"),
    ("KOR-Bench questions", "[KOR-Bench/KOR-Bench](https://github.com/KOR-Bench/KOR-Bench), Apache-2.0"),
    ("Laya original and adapted weights",
     "[convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya), Apache-2.0"),
    ("Example code and study-specific metadata",
     "[superlinked/sie](https://github.com/superlinked/sie), Apache-2.0"),
]
NOTICES = ("Exact source notices and revisions are included under `source/notices/` and "
           "`source/source-plan.json`. Please cite the upstream benchmarks and Laya when using these "
           "artifacts in research, and identify the immutable artifact revision used for a reported "
           "reproduction.")
# The 12.23 Default output on the pinned files (the cached-file test below requires the report's).
# The per-task, per-model success span on the pinned files (12.24 Bars; the cached span test pins it).
SPAN = {"low": (LUNA, "mmlupro/law", 304, 428), "high": 1.0, "high_pairs": 18, "high_tasks": 12}
FAMILIES = {"families": 5567, "shared_families": 276, "shared_items": 808, "in_both_splits": 0, "across_tasks": 0}
INVALID = {"korbench/cipher": 1}
DOWNLOAD = 2473 + 3777170 + 3742778
SECTIONS = ["## Source and licence", "## Results", "## Reading it", "## Family-held check", "## Regenerate"]
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd"]
NOT_KEPT = "no question, answer, usage hash or token count"
HOME = re.compile(r"(?m)(^|[\s(])/(Users|home)/")
NOTE_START = "```text\n$ python research/registry_pair.py\n"
NOTE_ROW = re.compile(r"^  (0\.\d)  (cost_effective|cost_blind) +(\d\.\d{3}) +(\d+\.\d{6}) +(\d\.\d{3}) +"
                      r"(\d+) of (\d+) +(\d+) +(\d+)$")
NOTE_SINGLE = re.compile(r"^    (openai/\S+) +(\d\.\d{3}) +(\d+\.\d{6})$")
NOTE_TASK = re.compile(r"^  ([a-z]+/\S+) +(\d+) +(\d+) +(yes|no) ")


def results_md():
    return RESULTS_MD.read_text(encoding="utf-8")


def evidence_readme():
    return EVIDENCE_README.read_text(encoding="utf-8")


def section(text, heading):
    """The body of one `## ` section, between its heading line and the next `## ` heading."""
    start = text.index("\n" + heading + "\n") + len(heading) + 2
    end = text.find("\n## ", start)
    return text[start:end if end >= 0 else len(text)].strip("\n")


def summary_row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"] if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1, (bar, flavor, strategy)
    return rows[0]


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


def join(words):
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def opening(results):
    """The two paragraphs before `## Source and licence`, every count from the file or SPAN (v1.437)."""
    config = results["config"]
    tasks, seeds, bars = results["tasks"], len(config["seeds"]), config["bars"]
    models = sorted({m for v in tasks.values() for m in v["models"]})
    groups = {}
    for task in tasks:
        groups[task.split("/")[0]] = groups.get(task.split("/")[0], 0) + 1
    model, low_task, hits, items = SPAN["low"]
    lo, hi = hits / items, SPAN["high"]
    rule = [k / 10 for k in range(math.floor(lo * 10) + 1, math.ceil(hi * 10))]
    assert rule != bars and set(rule) < set(bars), "the bars are the 12.17 rule's"
    return (
        f"What `model-routing evaluate` measures on superlinked/train-a-router-reasoning, the public release "
        f"whose two models and their prices are the registry's own: {join(f'`{m}`' for m in models)}, each "
        f"graded on the same {sum(v['items'] for v in tasks.values()):,} questions of MMLU-Pro, BIG-Bench Hard "
        f"and KOR-Bench, as {len(tasks)} routing tasks, one per (dataset, task) pair "
        f"({join(f'{n} `{g}`' for g, n in sorted(groups.items()))} tasks), a success when the release's "
        f"strict declared-label equality marks the answer right, and the release's estimated cost of the "
        f"call, from its token counts at the registry's list prices, as its cost. See [README.md](README.md) "
        f"for what the converter reads and keeps, and DESIGN 12.24 for this file's contract. For each of "
        f"{seeds} seeds the items of each task are split in half by a seeded hash; the router calibrates on "
        f"one half at a bar and is scored on the other half, next to the oracle, the best model on the "
        f"calibration half, the cheapest model and each single model (DESIGN 12.3). The file behind every "
        f"number here is [results.json](results.json): the summary rows and the routed per-task rows, "
        f"including how many of the {seeds} seeds routed to each model. It is made by the RouterBench "
        f"results script, `evidence/routerbench/results.py`, which does not depend on the dataset.\n\n"
        f"The bars are {join(str(b) for b in bars)}, the bars of the RouterBench results. Every tenth strictly "
        f"inside the span of the per-task, per-model success rates, which runs from {lo:.3f} (`{model}` on "
        f"`{low_task}`, {hits} of {items}) to {hi:.3f} ({SPAN['high_pairs']} (task, model) pairs on "
        f"{SPAN['high_tasks']} `bbh` tasks), would give only {join(str(b) for b in rule)} (DESIGN 12.24). The "
        f"two lower bars are kept so that each row has a counterpart in the family-held check below, and "
        f"since a task clears on its calibration bound, not its rate, they still give different rows.")


def results_section(rs, results):
    """The `## Results` section: the column sentence, the table block and the single-model sentence."""
    config = results["config"]
    _, best, _ = single_models(results)
    seeds, ntasks = len(config["seeds"]), len(results["tasks"])
    return (
        f"Routed rows: `success` is the share of held-out items whose answer the release marks right, pooled "
        f"over the {ntasks} tasks, `cost_usd` is the estimated cost of those calls (both averaged over the "
        f"{seeds} seeds), `vs_best_model` is that cost divided by the cost of the best single model "
        f"(`{name(best)}`), `cleared_rate` is the share of the {seeds * ntasks:,} (task, seed) cells where some "
        f"model cleared the bar on the calibration half, and `bar_violation_rate` is the share of cleared "
        f"cells whose held-out success fell below the bar. Baseline rows do not depend on the bar or the "
        f"flavor.\n\n```text\n{TABLE_COMMAND}\n{rs.table(results)}\n```\n\n{beats_statement(results)}")


def regenerate_section(cv):
    """The `## Regenerate` section: the five commands and the download line, its bytes from FILES, which from
    v1.443 (row E24e) also says the `evidence` workflow reruns them."""
    return (f"{REGENERATE}\nThe converter downloads the three pinned files "
            f"({sum(size for size, _ in cv.FILES.values()):,} bytes) into "
            f"`~/.cache/ai-model-routing-evidence/registry-pair/` on its first run, the folder "
            f"`research/registry_pair.py` also reads, and checks each against its pinned size and sha256; "
            f"converting them takes under a second once they are cached. The `evidence` workflow reruns "
            f"these commands on GitHub and fails if `results.json` changes by a byte (DESIGN.md 12.13, v1.443).")


def prices():
    rows = {m["id"]: m for m in json.loads(REGISTRY.read_text(encoding="utf-8"))["models"]}
    return {m: (rows[m]["price_in"], rows[m]["price_out"]) for m in MODELS}


def reading_bullets(results):
    """The `## Reading it` section of RESULTS.md, built whole from the committed file (12.24 v1.435)."""
    config = results["config"]
    seeds, bars, b0 = len(config["seeds"]), config["bars"], config["bars"][0]
    tasks = results["tasks"]
    cells = seeds * len(tasks)
    models, best, cheapest = single_models(results)
    ce = {bar: summary_row(results, bar, "cost_effective", "routed") for bar in bars}
    cb = [summary_row(results, bar, "cost_blind", "routed") for bar in bars]
    boc = summary_row(results, b0, "cost_effective", "best_on_calibration")
    assert all((r["success"], r["cost_usd"]) == (boc["success"], boc["cost_usd"]) for r in cb), \
        "cost_blind is not best_on_calibration at every bar"
    oracle = summary_row(results, b0, "cost_effective", "oracle")

    def cleared(row):
        n = row["cleared_rate"] * cells
        assert abs(n - round(n)) < 1e-9
        return round(n)

    def share(row):
        return row["cost_usd"] / best["cost_usd"]

    more = "more" if ce[b0]["success"] > cheapest["success"] else "no more"
    gap = cb[0]["success"] - best["success"]
    assert gap != 0, "cost_blind ties the best single model"
    blind = [t for t in tasks if next(r for r in results["per_task"] if (r["bar"], r["flavor"], r["task"])
                                      == (b0, "cost_blind", t))["routed_models"] == {name(cheapest): seeds}]
    violated = []
    for flavor in config["flavors"]:
        for bar in bars:
            row = summary_row(results, bar, flavor, "routed")
            v, n = row["bar_violation_rate"], cleared(row)
            if v:
                assert abs(v * n - round(v * n)) < 1e-9
                violated.append(f"{v:.3f} at bar {bar} (`{flavor}`) is {round(v * n)} of {n:,} cleared "
                                f"{'cell' if n == 1 else 'cells'}")
    nominal = (1 - config["confidence"]) / 2
    top = max(r["success"] for r in results["summary"] if r["strategy"] == "routed")
    logic = [r for r in results["per_task"] if r["task"] == "korbench/logic"]
    assert logic and all(r["cleared_rate"] == 0 and r["routed_models"] == logic[0]["routed_models"] for r in logic), \
        "korbench/logic clears or changes its fallback"
    picks = logic[0]["routed_models"]
    price = prices()
    mmlupro = [t for t in tasks if t.startswith("mmlupro/")]
    share_mmlupro = sum(tasks[t]["items"] for t in mmlupro)
    total = sum(v["items"] for v in tasks.values())
    assert 2 * share_mmlupro > total, "mmlupro is not most of the items"
    bullets = [
        f"`cost_effective`: at bar {b0} a model clears on {cleared(ce[b0]):,} of the {cells:,} (task, seed) "
        f"cells, and the router spends {share(ce[b0]):.3f} of the cost of the best single model, "
        f"`{name(best)}`, for a held-out success of {ce[b0]['success']:.3f}, against {best['success']:.3f} "
        f"for that model. Always calling the cheapest model, `{name(cheapest)}`, reaches "
        f"{cheapest['success']:.3f} at {cheapest['cost_usd']:.4f} USD, so at bar {b0} the router pays "
        f"{ce[b0]['cost_usd'] / cheapest['cost_usd']:.3f} of that cost for {more} held-out success",
        "At the higher bars `cost_effective` reaches " + "; ".join(
            f"{ce[bar]['success']:.3f} at {share(ce[bar]):.3f} of the best single model's cost at bar {bar}, "
            f"{cleared(ce[bar]):,} cells cleared" for bar in bars[1:]),
        f"`cost_blind` reaches {cb[0]['success']:.3f} at {share(cb[0]):.3f} of the best single model's cost "
        f"at every bar, the held-out success and cost of `best_on_calibration`, {abs(gap):.4f} "
        f"{'above' if gap > 0 else 'below'} that model's held-out success; at bar {b0} it routes every seed "
        f"of {len(blind)} of the {len(tasks)} tasks to `{name(cheapest)}`",
        ("Bar violations: " + "; ".join(violated) + f", against a nominal one-sided {nominal:.3f} for the "
         f"{config['confidence']} Wilson bound (DESIGN 12.3)") if violated
        else "Bar violations: none, in any row (DESIGN 12.3)",
        f"The per-item oracle reaches {oracle['success']:.3f} at {share(oracle):.3f} of the best single "
        f"model's cost, while the highest routed success of either flavor at any bar is {top:.3f}: routing "
        f"per task, not per question, cannot pick per item",
        f"`korbench/logic` ({tasks['korbench/logic']['items']} items) never clears: its calibration half is "
        f"under `min_samples` {config['min_samples']} on every seed (DESIGN 12.24), so the router falls back "
        f"to the model with the higher Wilson lower bound on that half (`on_no_model=\"best_available\"`, "
        f"DESIGN 5.3), `{LUNA}` on {picks.get(LUNA, 0)} seeds and `{SOL}` on {picks.get(SOL, 0)}, the same "
        f"counts at every bar in both flavors",
        f"Each cost is the release's estimate from the call's token counts at the list prices its "
        f"`pair.json` names, which the converter checks are the registry's (DESIGN 12.23): `{LUNA}` "
        f"{price[LUNA][0]:g} and {price[LUNA][1]:g}, `{SOL}` {price[SOL][0]:g} and {price[SOL][1]:g} USD "
        f"per million input and output tokens in `models.json`",
        f"Two models from one vendor, so each task has one choice, the cheaper or the stronger; `mmlupro` "
        f"holds {share_mmlupro:,} of the {total:,} items in {len(mmlupro)} tasks, so the pooled rows mostly "
        f"measure it",
        f"Size: the committed file, {RESULTS.stat().st_size:,} bytes, holds only the summary and the routed "
        f"per-task rows (DESIGN 12.7)"]
    return "\n".join("- " + b for b in bullets)


def note_block(text=None):
    text = NOTE.read_text(encoding="utf-8") if text is None else text
    start = text.index(NOTE_START)
    return text[start:text.index("\n```\n", start + len(NOTE_START))]


def note_rows(block):
    """The note's routed rows by (bar, flavor), its single models and its per-task split counts."""
    lines = block.split("\n")
    rows, singles, splits = {}, {}, {}
    for line in lines:
        if m := NOTE_ROW.match(line):
            rows[(float(m[1]), m[2])] = {"success": float(m[3]), "share": float(m[5]), "cleared": int(m[6]),
                                         "of": int(m[7]), "below": int(m[9])}
        elif m := NOTE_SINGLE.match(line):
            singles[m[1]] = float(m[2])
        elif m := NOTE_TASK.match(line):
            splits[m[1]] = (int(m[2]), int(m[3]))
    return rows, singles, splits


def family_held_section(results, block):
    """The `## Family-held check` section of RESULTS.md, from the note's Results block and the file."""
    config = results["config"]
    rows, singles, splits = note_rows(block)
    keys = [(bar, flavor) for flavor in config["flavors"] for bar in config["bars"]]
    assert sorted(rows) == sorted(keys), "the note's routed rows are not the committed bars and flavors"
    assert sorted(singles) == MODELS and sorted(splits) == sorted(results["tasks"]), "the note lacks a model or task"
    assert all(r["below"] == 0 for r in rows.values()), "a cleared task fell below its bar on the final split"
    models, best, _ = single_models(results)
    assert name(best) == SOL, "the best single model is not the strong model"
    alone = {name(m): m["success"] for m in models}
    seeds, ntasks = len(config["seeds"]), len(results["tasks"])
    cal, fin = (sum(v[k] for v in splits.values()) for k in (0, 1))
    lines = [
        f"The release keeps each family of related questions in one split, and the seeded halves of "
        f"[results.json](results.json) do not: {FAMILIES['shared_items']} of the {cal + fin:,} items are in "
        f"the {FAMILIES['shared_families']} families of two or more, so a question can be scored while a "
        f"relative of it calibrates (DESIGN 12.23). [research/registry-pair.md](../../research/registry-pair.md) "
        f"runs the same bars, `min_samples` {config['min_samples']} and confidence {config['confidence']} on "
        f"the release's own split, its {cal:,} calibration questions calibrating and its {fin:,} final ones "
        f"scoring, one split in place of {seeds} seeded halves. Its costs are sums over the final split, so "
        f"only shares of `{SOL}`'s cost compare, and a committed `cleared_rate` is a share of "
        f"{seeds * ntasks:,} (task, seed) cells, not of {ntasks} tasks:", ""]
    lines.append("- alone: " + "; ".join(f"`{m}` {singles[m]:.3f} on the final split, {alone[m]:.3f} in the "
                                         f"committed means" for m in MODELS))
    diffs, worst = [], 0.0
    for bar, flavor in keys:
        n, c = rows[(bar, flavor)], summary_row(results, bar, flavor, "routed")
        diffs.append(n["success"] - c["success"])
        worst = max(worst, c["bar_violation_rate"])
        lines.append(f"- bar {bar}, `{flavor}`: release split {n['success']:.3f} at {n['share']:.3f} of "
                     f"`{SOL}`'s cost, {n['cleared']} of {n['of']} tasks cleared, {n['below']} of them below "
                     f"the bar on the final split; committed means {c['success']:.3f} at "
                     f"{c['cost_usd'] / best['cost_usd']:.3f}, cleared_rate {c['cleared_rate']:.3f}, "
                     f"bar_violation_rate {c['bar_violation_rate']:.3f}")
    nominal = (1 - config["confidence"]) / 2
    assert min(diffs) > 0 and all(singles[m] > alone[m] for m in MODELS), \
        "a committed row is not below the release split's"
    assert worst < nominal, "a committed bar-violation rate reaches the nominal rate"
    lines += ["", f"On all {len(keys)} rows the committed routed success is below the release split's, by "
              f"{min(diffs):.3f} to {max(diffs):.3f}, and so is each model's alone. The two readings score "
              f"different questions, so each gap mixes how hard the final split is with what the halves do: "
              f"this check cannot isolate an effect of related questions in both seeded halves, and shows "
              f"only that no committed row is above its release-split counterpart. No cleared task fell below "
              f"its bar on the final split, and the "
              f"committed bar-violation rates are at most {worst:.3f}, under the nominal one-sided "
              f"{nominal:.3f}."]
    return "\n".join(lines)


def pair_table():
    price = prices()
    rows = ["| arm | model | input | output |", "| --- | --- | ---: | ---: |"]
    rows += [f"| {arm} | `{m}` | {price[m][0]:g} | {price[m][1]:g} |" for arm, m in (("cheap", LUNA), ("strong", SOL))]
    return "\n".join(rows) + "\n"


def split_table(splits):
    assert sorted(splits) == sorted(ITEMS) and all(sum(splits[t]) == ITEMS[t] for t in ITEMS), \
        "the split counts are not the 12.23 items"
    rows = ["| task | calibration | final | items |", "| --- | ---: | ---: | ---: |"]
    rows += [f"| `{t}` | {c:,} | {f:,} | {ITEMS[t]:,} |" for t, (c, f) in sorted(splits.items())]
    return "\n".join(rows) + "\n"


def report_sentence(families, invalid):
    where = ", ".join(f"{n} on `{t}`" for t, n in sorted(invalid.items()))
    total = sum(invalid.values())
    return (f"The converter's report on the pinned files counts {total} invalid "
            f"{'cell' if total == 1 else 'cells'} ({where}), kept as a miss with its charge, and "
            f"{families['families']:,} question families, {families['shared_families']} of them with two or "
            f"more items, {families['shared_items']} items in all, {families['in_both_splits']} in both "
            f"release splits and {families['across_tasks']} across tasks (DESIGN 12.23).")


def test_results_md_shows_the_table_of_the_committed_results(rs):
    block = "```text\n" + TABLE_COMMAND + "\n" + rs.table(committed()) + "\n```\n"
    assert block in results_md()


def test_results_md_regenerate_block_sources_and_licence():
    full = results_md()
    text = section(full, "## Source and licence")
    for needle in [DATASET_URL, f"[`{REVISION}`]({DATASET_URL}/tree/{REVISION})", LICENSES, NOTICES, CARD_SHA256,
                   "4,824 bytes", "read on 2026-11-16", *CARD_META, "(README.md)", "(results.json)"]:
        assert needle in text, needle
    text = full
    for file in FILES:
        size, sha256 = load("registry_pair_convert_for_md", FOLDER / "convert.py").FILES[file]
        assert f"`{file}`, {size:,} bytes, sha256 `{sha256}`" in text, file
    for component, cell in COMPONENTS:
        assert f"  - {component}: {cell}\n" in text, component
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text
    assert not HOME.search(text)


def test_results_md_single_model_sentence_is_the_committed_results():
    assert beats_statement(committed()) in results_md()


def test_results_md_reading_it_is_built_from_the_committed_file():
    assert section(results_md(), "## Reading it") == reading_bullets(committed())


def test_results_md_family_held_check_is_the_note_beside_the_file():
    assert section(results_md(), "## Family-held check") == family_held_section(committed(), note_block())


def test_results_md_sections_in_order():
    heads = [line for line in results_md().split("\n") if line.startswith("## ")]
    assert heads == SECTIONS


def test_reading_builder_fails_where_cost_blind_is_not_best_on_calibration():
    fake = json.loads(json.dumps(committed()))
    assert reading_bullets(fake).count("\n- ") == 8
    summary_row(fake, BARS[-1], "cost_blind", "routed")["success"] -= 0.001
    with pytest.raises(AssertionError, match="not best_on_calibration"):
        reading_bullets(fake)


def test_family_held_builder_fails_on_a_note_row_below_its_bar():
    block = note_block()
    assert family_held_section(committed(), block).count("\n- ") == 9
    line = next(line for line in block.split("\n") if NOTE_ROW.match(line) and "0.8  cost_effective" in line)
    assert line.endswith("   0")
    with pytest.raises(AssertionError, match="below its bar"):
        family_held_section(committed(), block.replace(line, line[:-1] + "1"))
    with pytest.raises(AssertionError, match="not the committed bars"):
        family_held_section(committed(), block.replace(line + "\n", ""))


def test_evidence_readme_states_the_source_pair_tasks_and_row_keys():
    text = evidence_readme()
    assert "(RESULTS.md)" in text and "(results.json)" in text
    for needle in [DATASET_URL, REVISION, LICENSES, CARD_META[1], MATRIX_BLOCK, NOT_KEPT,
                   report_sentence(FAMILIES, INVALID)]:
        assert needle in text, needle
    cv = load("registry_pair_convert_for_readme", FOLDER / "convert.py")
    for file, (size, sha256) in cv.FILES.items():
        assert f"`{file}`, {size:,} bytes, sha256 `{sha256}`" in text, file
    assert pair_table() in text
    assert split_table(note_rows(note_block())[2]) in text
    total = sum(ITEMS.values())
    for needle in [f"the same {total:,} questions", f"{total:,} items in all, {2 * total:,} rows (2 per item)",
                   f"bars {BARS[0]} to {BARS[-1]} over {len(CONFIG['seeds'])} seeds"]:
        assert needle in text, needle
    for key in ROW_KEYS:
        assert f"`{key}`" in text, key
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text
    assert not HOME.search(text)


def test_real_report_matches_the_evidence_readme(real_run):
    report, _ = real_run
    tasks = report["tasks"]
    assert split_table({t: (v["calibration"], v["final"]) for t, v in tasks.items()}) in evidence_readme()
    assert report["families"] == FAMILIES
    assert {t: v["invalid_cells"] for t, v in tasks.items() if v["invalid_cells"]} == INVALID


def test_results_md_opening_results_and_regenerate_sections_are_built():
    text, results = results_md(), committed()
    cv = load("registry_pair_convert_for_sections", FOLDER / "convert.py")
    rs = load("routerbench_results_for_sections", ROOT / "evidence" / "routerbench" / "results.py")
    head = "# Registry-pair results\n\n"
    assert text.startswith(head) and text[len(head):text.index("\n## Source and licence\n")].strip("\n") == opening(results)
    assert section(text, "## Results") == results_section(rs, results)
    assert section(text, "## Regenerate") == regenerate_section(cv)
    assert sum(size for size, _ in cv.FILES.values()) == DOWNLOAD


def test_opening_builder_follows_the_file_and_span():
    fake = json.loads(json.dumps(committed()))
    fake["config"]["seeds"] = list(range(51))
    fake["tasks"]["bbh/extra"] = {"items": 1, "models": MODELS}
    text = opening(fake)
    assert "For each of 51 seeds" in text and "(15 `bbh`, 3 `korbench` and 14 `mmlupro` tasks)" in text
    assert "as 32 routing tasks" in text and "6,100 questions" in text
    fake["config"]["bars"] = [0.8, 0.9]
    with pytest.raises(AssertionError, match="12.17 rule"):
        opening(fake)


# --- v1.452 (row E24c): the README `### Registry pair` subsection (DESIGN 12.24 README bullet, 12.8) ------

README = ROOT / "README.md"
EVIDENCE_HEADING = "\n## Evidence: held-out results on public data\n"
README_HEADING = "Registry pair"
README_RESULTS = "[RESULTS.md](evidence/registry-pair/RESULTS.md)"
README_EVIDENCE = "[evidence/registry-pair/README.md](evidence/registry-pair/README.md)"
NUMBER = {3: "three"}
# The kept bullets are the first and third of `## Reading it` (`cost_effective` and `cost_blind`); the link
# line names the other seven and the family-held check.
README_LINK_LINE = (
    "The higher bars, bar violations, oracle, `korbench/logic` fallback, costs, one vendor, `mmlupro` share "
    "and size are in [RESULTS.md](evidence/registry-pair/RESULTS.md#reading-it) `## Reading it`, and the "
    "release's own split in [`## Family-held check`](evidence/registry-pair/RESULTS.md#family-held-check).")


def readme_text():
    return README.read_text(encoding="utf-8")


def readme_subsection(text=None):
    text = readme_text() if text is None else text
    assert text.count(EVIDENCE_HEADING) == 1
    part = text.split(EVIDENCE_HEADING, 1)[1].split("\n## ", 1)[0]
    marker = f"\n### {README_HEADING}\n"
    assert part.count(marker) == 1
    return part.split(marker, 1)[1].split("\n### ", 1)[0]


def readme_source_lines(results):
    """The four source lines: the dataset, the licence, what was run and the full-results links."""
    config, tasks = results["config"], results["tasks"]
    models = sorted({m for v in tasks.values() for m in v["models"]})
    groups = {}
    for task in tasks:
        groups[task.split("/")[0]] = groups.get(task.split("/")[0], 0) + 1
    bars = config["bars"]
    return [
        f"- Dataset: [superlinked/train-a-router-reasoning]({DATASET_URL}), pinned at revision "
        f"[`{REVISION[:7]}`]({DATASET_URL}/tree/{REVISION}), {NUMBER[len(FILES)]} files of {DOWNLOAD:,} bytes "
        "in all, each checked by size and sha256",
        f"- Licence: {CARD_META[0]} and {CARD_META[1]} on the card, which says: \"{LICENSES}\" Its "
        f"component licences and citation request are quoted in {README_RESULTS}. The repo commits only "
        "derived numbers",
        f"- What was run: the registry's own {len(models)} models at its prices, "
        f"{join(f'`{m}`' for m in models)}, on {len(tasks)} routing tasks, one per (dataset, task) of "
        f"MMLU-Pro, BIG-Bench Hard and KOR-Bench ({join(f'{n} `{g}`' for g, n in sorted(groups.items()))}, "
        f"{sum(v['items'] for v in tasks.values()):,} items in all), {len(config['seeds'])} seeds, bars "
        f"{bars[0]} to {bars[-1]}, both flavors. A success is the release's strict declared-label match, the "
        "cost its estimate from token counts at those prices",
        f"- Full results: {README_RESULTS} and [results.json](evidence/registry-pair/results.json); source, "
        f"prices, release splits and row keys: {README_EVIDENCE}"]


def readme_columns(results):
    cells = len(results["config"]["seeds"]) * len(results["tasks"])
    return ("Held-out success is the share of held-out items whose answer the release marks right, pooled over "
            f"the {len(results['tasks'])} tasks, and cost is the estimated cost of answering them, both averaged "
            "over the seeds; the ratio divides that cost by the cost of the best single model. The cleared rate "
            f"is the share of the {cells:,} (task, seed) cells where some model cleared the bar on the "
            "calibration half, and the bar-violation rate is the share of cleared cells whose held-out success "
            "fell below the bar.")


def readme_tables(results):
    """The two tables, in the columns of `### LLM Routing Response Bank` (DESIGN 12.8, 12.24 v1.452)."""
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    models, best, cheapest = single_models(results)
    lines = ["| Bar | Flavor | Held-out success | Cost (USD) | Cost / best single model | Cleared rate "
             "| Bar-violation rate |", "|---|---|---|---|---|---|---|"]
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            r = summary_row(results, bar, flavor, "routed")
            v = r["bar_violation_rate"]
            lines.append(f"| {bar} | `{flavor}` | {r['success']:.3f} | {r['cost_usd']:.4f} | "
                         f"{r['cost_usd'] / best['cost_usd']:.3f} | {r['cleared_rate']:.3f} | "
                         f"{'-' if v is None else format(v, '.3f')} |")
    rows = [("Per-item oracle: on each item, the cheapest model marked right, or the cheapest model, counted "
             "wrong, when neither was", summary_row(results, *first, "oracle"))]
    for m in models:
        mark = (", the best single model" if m is best else "") + \
               (", the cheapest single model" if m is cheapest else "")
        rows.append((f"Always `{name(m)}`{mark}", m))
    rows += [("Best model on the calibration half, per task",
              summary_row(results, *first, "best_on_calibration")),
             ("Cheapest model on the calibration half, per task", summary_row(results, *first, "cheapest"))]
    lines += ["", "| Baseline | Held-out success | Cost (USD) |", "|---|---|---|"]
    lines += [f"| {label} | {r['success']:.3f} | {r['cost_usd']:.4f} |" for label, r in rows]
    return "\n".join(lines) + "\n"


def readme_regenerate_line():
    return ("Regenerate (the converter downloads the three pinned files, about "
            f"{DOWNLOAD / 1e6:.1f} MB, into a cache folder outside the repo and converts them in under a second "
            "once they are cached; the `evidence` workflow reruns these commands on GitHub and fails if "
            "`results.json` changes by a byte, while the test suite rebuilds it only where the files are "
            "cached):")


def readme_reading(results):
    """The kept Reading it bullets, the first and third of RESULTS.md, and the other seven."""
    bullets = reading_bullets(results).split("\n")
    assert len(bullets) == 9 and bullets[0].startswith("- `cost_effective`: ") and \
        bullets[2].startswith("- `cost_blind` reaches ")
    return [bullets[0], bullets[2]], bullets[1:2] + bullets[3:]


def readme_body(results):
    """The whole subsection after its heading line, built from the committed file and the constants."""
    kept, _ = readme_reading(results)
    return ("\n" + "\n".join(readme_source_lines(results)) + "\n\n" + readme_columns(results) + "\n\n"
            + readme_tables(results) + "\n" + beats_statement(results) + "\n\nReading it:\n\n"
            + "\n".join(kept) + "\n\n" + README_LINK_LINE + "\n\n" + readme_regenerate_line() + "\n\n"
            + REGENERATE)


def test_readme_registry_pair_subsection_is_built_from_the_committed_file():
    # v1.452 (row E24c): every line of the subsection, its source lines, tables, single-model sentence,
    # two Reading it bullets, link line and regenerate paragraph and block, is built here; the section
    # runs to the blank line before the next `###` heading.
    assert readme_subsection() == readme_body(committed())


def test_readme_registry_pair_keeps_two_results_md_bullets_and_links_the_rest():
    sub, text = readme_subsection(), results_md()
    kept, dropped = readme_reading(committed())
    assert all(bullet in text for bullet in kept + dropped)
    assert all(sub.count(bullet + "\n") == 1 for bullet in kept)
    assert not any(bullet[2:] in sub for bullet in dropped)
    assert sub.count("](evidence/registry-pair/RESULTS.md#reading-it)") == 1
    assert "\n## Reading it\n" in text and "\n## Family-held check\n" in text
    # The regenerate block is the RESULTS.md one, which the `evidence` workflow reruns (12.13 v1.443).
    assert sub.endswith(REGENERATE) and sub.count("```bash\n") == 1
    assert section(text, "## Regenerate").startswith(REGENERATE)


def test_readme_registry_pair_builders_follow_the_file():
    seeds = json.loads(json.dumps(committed()))
    seeds["config"]["seeds"] = list(range(51))
    assert "51 seeds" in readme_source_lines(seeds)[2] and "1,581 (task, seed) cells" in readme_columns(seeds)
    fake = json.loads(json.dumps(committed()))
    summary_row(fake, 0.6, "cost_effective", "routed")["cost_usd"] = 0.4632
    assert "| 0.6 | `cost_effective` | 0.885 | 0.4632 | 0.108 |" in readme_tables(fake)
    assert readme_body(fake) != readme_body(committed())
