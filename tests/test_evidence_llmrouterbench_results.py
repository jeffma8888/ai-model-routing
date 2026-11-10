"""v1.156 LLMRouterBench results contract (DESIGN 12.19), written before the results were committed.

The committed ``evidence/llmrouterbench/results.json`` is made by the RouterBench results script,
``evidence/routerbench/results.py``, reused unchanged, from ``model-routing evaluate`` in both
flavors, since every row of the 12.18 matrix has a ``cost_usd`` (2,410 of them 0.0, but no
(task, model) pair 0.0 on every item). The first tests need no
download: they check the committed file alone. The last ones use the converter's CLI run on the
pinned file, the session fixture ``llmrouterbench_pinned`` of tests/conftest.py that the converter
tests share, so the suite reads the tarball at most once; they skip when it is not in the default
cache (CI never downloads it). They rebuild results.json and require the committed bytes, and
rebuild the success span behind the bars and the calibration-half sizes DESIGN 12.19 states.

The tests that read the committed file were committed before it under strict xfail
(``FileNotFoundError``), removed by the commit that adds it (v1.157); the span and split-size
tests read only the pinned file.

v1.161 (DESIGN 12.19, row E16c): RESULTS.md and the evidence README. The tests build the table,
the single-model sentence and every Reading it number from the committed file and require them
in RESULTS.md, check the evidence README against the converter's constants and the 12.18
counts, and, when the pinned file is cached, against the converter's report. The tests that
read the two files were committed before them under strict xfail (``FileNotFoundError``),
removed by the commit that adds them (v1.162).


v1.164 (DESIGN 12.8, row E16e): the README ``### LLMRouterBench`` subsection. The tests build
its counts sentence and two tables from the committed file, require its Reading it and Limits
lines to be RESULTS.md's under two stated rewrites, and check its links, licence, regenerate
line and block and the Layout line. They were committed before the subsection under strict
xfail (``AssertionError``), removed by the commit that adds it.
"""

import importlib.util
import json
import math
import re
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
RESULTS_MD = FOLDER / "RESULTS.md"
EVIDENCE_README = FOLDER / "README.md"
DATASETS_NOTE = ROOT / "research" / "datasets.md"
TABLE_COMMAND = ("$ python evidence/routerbench/results.py --table "
                 "evidence/llmrouterbench/results.json")
REGENERATE = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl\n"
    "model-routing evaluate --outcomes llmrouterbench-matrix.jsonl"
    " --bar 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 --seeds 50 --json > llmrouterbench-evaluate.json\n"
    "python evidence/routerbench/results.py --evaluate llmrouterbench-evaluate.json"
    " --out evidence/llmrouterbench/results.json\n"
    "python evidence/routerbench/results.py --table evidence/llmrouterbench/results.json\n"
    "```\n")
MATRIX_BLOCK = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl\n"
    "```\n")
SPLITS = {"aime": "hybrid", "arc-agi": "v1", "arenahard": "", "gpqa": "test", "hle": "test",
          "livecodebench": "test", "livemathbench": "test", "mmlupro": "test_3000",
          "simpleqa": "test"}
DROPPED = {"arenahard_coding": "subset of arenahard",
           "arenahard_creative_writing": "subset of arenahard",
           "arenahard_math": "subset of arenahard",
           "humaneval": "no split holds every pool model",
           "swe-bench": "no split holds every pool model",
           "tau2": "no split holds every pool model"}
IN_SAMPLE = "Each task's own best model reaches 0.6240 (+0.0250)"
IN_SAMPLE_GAIN = 0.0250
COPYRIGHT = "Copyright (c) 2025-2026 LLMRouterBench contributors"
SCOPE = ("This license applies to the original code and benchmark data contributions of "
         "LLMRouterBench, to the extent of the contributors' rights. Third-party datasets, code, "
         "and other incorporated materials retain their original licenses.")
HALF_SCORES = "2,144 kept `arenahard` cells"


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

def test_committed_results_are_small_and_reduced(rs):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    assert text == json.dumps(rs.reduce(json.loads(text)), indent=2) + "\n"


def test_committed_results_have_the_config_tasks_and_pool(cv):
    results = committed()
    assert results["config"] == CONFIG
    models = model_ids(cv)
    assert len(models) == 13
    assert results["tasks"] == {task: {"items": n, "models": models} for task, n in ITEMS.items()}
    assert list(results["tasks"]) == sorted(ITEMS)


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


def test_real_zero_costs_never_fill_a_task_model_pair(real_rows):
    zeros, rows = {}, {}
    for r in real_rows:
        key = (r["task"], r["model"])
        rows[key] = rows.get(key, 0) + 1
        zeros[key] = zeros.get(key, 0) + (r["cost_usd"] == 0)
    assert all(r["cost_usd"] >= 0 for r in real_rows)
    assert sum(zeros.values()) == 2410
    assert len({t for (t, _), n in zeros.items() if n}) == 8
    assert len({m for (_, m), n in zeros.items() if n}) == 9
    assert all(zeros[key] < rows[key] for key in rows)


# --- RESULTS.md and the evidence README (v1.161) --------------------------------------------

def results_md():
    return RESULTS_MD.read_text(encoding="utf-8")


def evidence_readme():
    return EVIDENCE_README.read_text(encoding="utf-8")


def summary_row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"]
            if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1, (bar, flavor, strategy)
    return rows[0]


def task_row(results, bar, flavor, task):
    rows = [r for r in results["per_task"] if (r["bar"], r["flavor"], r["task"]) == (bar, flavor, task)]
    assert len(rows) == 1 and rows[0]["strategy"] == "routed", (bar, flavor, task)
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


def join(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


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


def reading_phrases(results):
    """Every number of the RESULTS.md "Reading it" bullets built from the committed file."""
    config = results["config"]
    seeds, bars, b0, b9 = len(config["seeds"]), config["bars"], config["bars"][0], config["bars"][-1]
    tasks = list(results["tasks"])
    cells = seeds * len(tasks)
    _, best, cheapest = single_models(results)
    ce = {bar: summary_row(results, bar, "cost_effective", "routed") for bar in bars}
    cb = [summary_row(results, bar, "cost_blind", "routed") for bar in bars]
    boc = summary_row(results, b0, "cost_effective", "best_on_calibration")
    oracle = summary_row(results, b0, "cost_effective", "oracle")
    assert all((r["success"], r["cost_usd"]) == (cb[0]["success"], cb[0]["cost_usd"]) for r in cb)
    assert all(ce[a]["cleared_rate"] >= ce[b]["cleared_rate"] and ce[a]["cost_usd"] <= ce[b]["cost_usd"]
               for a, b in zip(bars, bars[1:]))
    short = [t for t in tasks if task_row(results, b0, "cost_effective", t)["cleared_rate"] < 1]
    assert len(short) == 1, short
    short_cleared = task_row(results, b0, "cost_effective", short[0])["cleared_rate"] * seeds
    assert abs(short_cleared - round(short_cleared)) < 1e-9
    more = "no more" if ce[b0]["success"] <= cheapest["success"] else "more"
    gap = cb[0]["success"] - best["success"]
    assert gap > 0, "cost_blind is not above the best single model"
    others = {}
    for t in tasks:
        picks = task_row(results, b0, "cost_blind", t)["routed_models"]
        if len(picks) == 1 and next(iter(picks)) != name(best):
            others.setdefault(next(iter(picks)), []).append(t)
    assert len(others) == 1, others
    (other, other_tasks), = others.items()
    split = [t for t in tasks if len(task_row(results, b0, "cost_blind", t)["routed_models"]) > 1]
    assert len(split) + len(other_tasks) + sum(
        task_row(results, b0, "cost_blind", t)["routed_models"] == {name(best): seeds} for t in tasks
    ) == len(tasks)
    phrases = [
        f"At bar {b0} a model clears on {round(ce[b0]['cleared_rate'] * cells)} of the {cells} "
        f"(task, seed) cells: on all {seeds} seeds of every task but `{short[0]}`, and on "
        f"{round(short_cleared)} of `{short[0]}`'s",
        f"spends {ce[b0]['cost_usd'] / best['cost_usd']:.3f} of the best single model's cost for a "
        f"held-out success of {ce[b0]['success']:.3f}, against {best['success']:.3f} for that model "
        f"(`{name(best)}`)",
        f"Always calling the cheapest model, `{name(cheapest)}`, reaches {cheapest['success']:.3f} "
        f"at {cheapest['cost_usd']:.4f} USD, so at bar {b0} the router pays "
        f"{ce[b0]['cost_usd'] / cheapest['cost_usd']:.1f} times as much for {more} held-out success",
        f"at bar {b9} it reaches {ce[b9]['success']:.3f} at "
        f"{ce[b9]['cost_usd'] / best['cost_usd']:.3f} of the best single model's cost",
        f"`cost_blind` reaches {cb[0]['success']:.3f} at {cb[0]['cost_usd'] / best['cost_usd']:.3f} "
        f"of the best single model's cost at every bar, {gap:.4f} above that model's held-out "
        f"success, against `best_on_calibration`'s {boc['success']:.3f} at "
        f"{boc['cost_usd'] / best['cost_usd']:.3f}",
        f"at bar {b0} it routes every seed of {join(['`' + t + '`' for t in other_tasks])} to "
        f"`{other}`",
        f"while the other {len(split)} tasks split their seeds among two or more models",
        f"The {gap:.4f} is {gap / IN_SAMPLE_GAIN:.2f} of the in-sample gain of "
        f"{IN_SAMPLE_GAIN:.4f}",
        f"a nominal one-sided {(1 - config['confidence']) / 2:.3f}",
        f"the committed file, {RESULTS.stat().st_size:,} bytes,"]
    for flavor in config["flavors"]:
        for bar in bars:
            row = summary_row(results, bar, flavor, "routed")
            v = row["bar_violation_rate"]
            if v:
                cleared = row["cleared_rate"] * cells
                assert abs(cleared - round(cleared)) < 1e-9 and abs(v * round(cleared) - round(v * round(cleared))) < 1e-9
                phrases.append(f"{v:.3f} at bar {bar} (`{flavor}`) is {round(v * round(cleared))} of "
                               f"the {round(cleared)} cells that cleared")
    top = max(r["success"] for r in results["summary"] if r["strategy"] == "routed")
    assert oracle["success"] - top >= 0.1
    phrases.append(f"The per-item oracle reaches {oracle['success']:.3f} at {oracle['cost_usd']:.4f} "
                   f"USD, while the highest routed success of either flavor at any bar is {top:.3f}")
    return phrases


def test_results_md_shows_the_table_of_the_committed_results(rs):
    block = "```text\n" + TABLE_COMMAND + "\n" + rs.table(committed()) + "\n```\n"
    assert block in results_md()


def test_results_md_regenerate_block_and_sources(cv):
    text = results_md()
    assert REGENERATE in text
    for needle in ["https://huggingface.co/datasets/NPULH/LLMRouterBench",
                   f"(https://huggingface.co/datasets/NPULH/LLMRouterBench/tree/{cv.REVISION})",
                   f"`{cv.FILE}`", f"{cv.SIZE:,} bytes", cv.SHA256, "MIT", COPYRIGHT, SCOPE,
                   "(README.md)", "(results.json)", "DESIGN 12.19", "0.036", "0.883",
                   "`deepseek/deepseek-v3-0324` on `hle`", "`openai/gpt-5` on `aime`",
                   HALF_SCORES, "0.853 to 1.502", "`~/.cache/ai-model-routing-evidence/llmrouterbench/`",
                   "per benchmark, not per prompt"]:
        assert needle in text, needle
    for task, items in ITEMS.items():
        assert f"`{task}` {items:,}" in text, task
    for dropped in DROPPED:
        assert f"`{dropped}`" in text, dropped
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text
    assert not re.search(r"(?m)(^|[\s(])/(Users|home)/", text)


def test_results_md_single_model_sentence_is_the_committed_results():
    assert beats_statement(committed()) in results_md()


def test_beats_statement_drops_a_row_that_loses_on_cost():
    fake = json.loads(json.dumps(committed()))
    _, best, _ = single_models(fake)
    assert f"`{name(best)}` (by bar 0.1 `cost_blind`" in beats_statement(fake)
    for bar in BARS:
        for flavor in FLAVORS:
            row = summary_row(fake, bar, flavor, "routed")
            row["cost_usd"] = max(row["cost_usd"], best["cost_usd"] * 2)
    assert f"`{name(best)}` (by" not in beats_statement(fake)


def test_results_md_reading_numbers_are_the_committed_results():
    text = results_md()
    for phrase in reading_phrases(committed()):
        assert phrase in text, phrase


def test_in_sample_gain_is_the_datasets_note():
    assert IN_SAMPLE in DATASETS_NOTE.read_text(encoding="utf-8")


def test_reading_phrases_fail_when_cost_blind_is_not_above_the_best_model():
    fake = json.loads(json.dumps(committed()))
    _, best, _ = single_models(fake)
    for bar in BARS:
        summary_row(fake, bar, "cost_blind", "routed")["success"] = best["success"]
    with pytest.raises(AssertionError, match="not above"):
        reading_phrases(fake)


def pool_table(cv):
    rows = ["| folder | model |", "| --- | --- |"]
    rows += [f"| `{folder}` | `{cv.model_id(folder)}` |" for folder in cv.POOL]
    return "\n".join(rows) + "\n"


def task_table(splits, items):
    rows = ["| task | split | items |", "| --- | --- | ---: |"]
    rows += [f"| `{t}` | {('`' + splits[t] + '`') if splits[t] else '(none)'} | {items[t]:,} |"
             for t in sorted(items)]
    return "\n".join(rows) + "\n"


def test_evidence_readme_states_the_source_pool_and_tasks(cv):
    text = evidence_readme()
    assert "(RESULTS.md)" in text and "(results.json)" in text
    for needle in ["https://huggingface.co/datasets/NPULH/LLMRouterBench", cv.REVISION,
                   f"`{cv.FILE}`", f"{cv.SIZE:,} bytes", cv.SHA256, COPYRIGHT, SCOPE, MATRIX_BLOCK]:
        assert needle in text, needle
    assert pool_table(cv) in text
    assert task_table(SPLITS, ITEMS) in text
    for dropped, reason in DROPPED.items():
        assert f"- `{dropped}`: {reason}" in text, dropped
    for column in ["task", "item", "model", "correct", "cost_usd", "input_tokens", "output_tokens"]:
        assert f"`{column}`" in text, column
    assert "no question, prompt, prediction, ground truth or output text" in text
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text
    assert not re.search(r"(?m)(^|[\s(])/(Users|home)/", text)
    assert "10 of `openai/gpt-5`'s" in text and "(749 after the question check)" in text


def test_real_report_matches_the_evidence_readme_and_results_md(llmrouterbench_pinned, real_rows):
    code, report, _ = llmrouterbench_pinned
    assert code == 0
    tasks = report["tasks"]
    assert task_table({t: v["split"] for t, v in tasks.items()},
                      {t: v["items"] for t, v in tasks.items()}) in evidence_readme()
    assert report["dropped_benchmarks"] == DROPPED
    assert {t: v["half_scores"] for t, v in tasks.items() if v["half_scores"]} == {"arenahard": 2144}
    assert HALF_SCORES.replace("2,144", f"{tasks['arenahard']['half_scores']:,}") in results_md()
    results = committed()
    items = {}
    for r in real_rows:
        items.setdefault(r["task"], set()).add(r["item"])
    b0 = results["config"]["bars"][0]
    for task, v in items.items():
        under = sum(len(split_items(sorted(v), seed)[0]) < CONFIG["min_samples"] for seed in range(50))
        uncleared = round((1 - task_row(results, b0, "cost_effective", task)["cleared_rate"]) * 50)
        assert under == uncleared, task
    nulls = {}
    for r in real_rows:
        if r["input_tokens"] is None or r["output_tokens"] is None:
            nulls[r["model"]] = nulls.get(r["model"], 0) + 1
    assert nulls == {"openai/gpt-5": 10}
    halves = [len(split_items(sorted(items["aime"]), seed)[0]) for seed in range(50)]
    assert (f"holds {min(halves)} to {max(halves)} of its {len(items['aime'])} items over the 50 "
            f"seeds and is under `min_samples` {CONFIG['min_samples']} on "
            f"{sum(n < CONFIG['min_samples'] for n in halves)} of them") in results_md()


# --- the README subsection (DESIGN 12.8, v1.164) --------------------------------------------

README = ROOT / "README.md"
EVIDENCE_HEADING = "\n## Evidence: held-out results on public data\n"
HEADINGS = ["RouterBench", "AutoBench", "AutoBench judges", "tau2-bench", "LiveCodeBench",
            "LLMRouterBench", "Delegation on AutoBench", "Delegation on tau2-bench",
            "Delegation on LLMRouterBench"]
INDENT = " " * 16
LCB_LAYOUT = INDENT + "(LiveCodeBench: evidence/livecodebench/RESULTS.md)\n"
LAYOUT = INDENT + "(LLMRouterBench: evidence/llmrouterbench/RESULTS.md)\n"
REGENERATE_LINE = (
    "Regenerate (the converter downloads the pinned file, about 1.28 GB, into a cache folder outside "
    "the repo, and verifying, reading and converting it takes about 13 seconds once it is cached; the "
    "`evidence` workflow reruns these commands on GitHub and fails if `results.json` changes by a byte, "
    "while the test suite rebuilds `results.json` from them only where the pinned file is cached):")
EVIDENCE_LINK = "[evidence/llmrouterbench/README.md](evidence/llmrouterbench/README.md)"
def readme_text():
    return README.read_text(encoding="utf-8")


def readme_subsection():
    text = readme_text()
    assert text.count(EVIDENCE_HEADING) == 1
    section = text.split(EVIDENCE_HEADING, 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.*)$", section, re.M) == HEADINGS
    return section.split("\n### LLMRouterBench\n", 1)[1].split("\n### ", 1)[0]


def to_readme(line):
    """The two v1.164 rewrites of a RESULTS.md line for the top-level README (DESIGN 12.8)."""
    return line.replace("DESIGN 12.", "`DESIGN.md` 12.").replace("[README.md](README.md)", EVIDENCE_LINK)


def results_md_bullets():
    """The five Reading it bullets and the three limits of RESULTS.md, before the size bullet."""
    body = results_md().split("\n## Reading it\n", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in body.splitlines() if line.startswith("- ")]
    assert len(bullets) == 9 and bullets[-1].startswith("- Size: "), bullets
    assert bullets[0].startswith("- `cost_effective`: ") and bullets[4].startswith("- The per-item oracle")
    assert bullets[5].startswith("- Half scores: ") and bullets[7].startswith("- Dropped by the converter")
    return bullets[:5], bullets[5:8]


def whole_task_model(results):
    """The one model other than the best single one that `cost_blind` takes on every seed of whole
    tasks at the lowest bar, and how many tasks (as the RESULTS.md Reading it test finds it)."""
    b0, seeds = results["config"]["bars"][0], len(results["config"]["seeds"])
    _, best, _ = single_models(results)
    others = {}
    for t in results["tasks"]:
        picks = task_row(results, b0, "cost_blind", t)["routed_models"]
        if len(picks) == 1 and next(iter(picks)) != name(best):
            assert next(iter(picks.values())) == seeds
            others.setdefault(next(iter(picks)), []).append(t)
    assert len(others) == 1, others
    (other, tasks), = others.items()
    return other, len(tasks)


def readme_counts(results):
    config, tasks = results["config"], results["tasks"]
    models = {tuple(v["models"]) for v in tasks.values()}
    assert len(models) == 1 and config["flavors"] == ["cost_effective", "cost_blind"]
    parts = [f"`{t}` {v['items']:,}" + (" items" if i == 0 else "")
             for i, (t, v) in enumerate(tasks.items())]
    bars = config["bars"]
    return (f"- What was run: {len(models.pop())} API models from 2025, {len(tasks)} benchmarks, each one "
            f"routing task ({join(parts)}, {sum(v['items'] for v in tasks.values()):,} in all), "
            f"{len(config['seeds'])} seeds; each task is split in half per seed and routed at bars "
            f"{bars[0]} to {bars[-1]} in both flavors. A success is a record's score of 1, so a 0.5 from "
            f"the `arenahard` judge is a miss, and the cost is the record's own `cost`")


def readme_columns(results):
    cells = len(results["config"]["seeds"]) * len(results["tasks"])
    return ("Held-out success is the share of held-out items whose record scored 1, pooled over the "
            f"{len(results['tasks'])} tasks, and cost is the recorded cost of answering them, both averaged "
            "over the seeds; the ratio divides that cost by the cost of the best single model. The cleared "
            f"rate is the share of the {cells} (task, seed) cells where some model cleared the bar on the "
            "calibration half, and the bar-violation rate is the share of cleared cells whose held-out "
            "success fell below the bar.")


def readme_tables(results):
    """The two tables of the README `### LLMRouterBench` subsection (DESIGN 12.8, v1.164)."""
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    _, best, cheapest = single_models(results)
    lines = ["| Bar | Flavor | Held-out success | Cost (USD) | Cost / best single model | Cleared rate "
             "| Bar-violation rate |", "|---|---|---|---|---|---|---|"]
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            r = summary_row(results, bar, flavor, "routed")
            v = r["bar_violation_rate"]
            lines.append(f"| {bar} | `{flavor}` | {r['success']:.3f} | {r['cost_usd']:.4f} | "
                         f"{r['cost_usd'] / best['cost_usd']:.3f} | {r['cleared_rate']:.3f} | "
                         f"{'-' if v is None else format(v, '.3f')} |")
    other, n = whole_task_model(results)
    rows = [("Per-item oracle: on each item, the cheapest model that scored 1, or the cheapest model, "
             "counted wrong, when none did", summary_row(results, *first, "oracle")),
            (f"Best single model (`{name(best)}`)", best),
            (f"Always `{other}`, which `cost_blind` takes on every seed of {n} tasks at bar {first[0]}",
             summary_row(results, *first, f"model:{other}")),
            (f"Cheapest single model (`{name(cheapest)}`)", cheapest),
            ("Best model on the calibration half, per task",
             summary_row(results, *first, "best_on_calibration")),
            ("Cheapest model on the calibration half, per task", summary_row(results, *first, "cheapest"))]
    lines += ["", "| Baseline | Held-out success | Cost (USD) |", "|---|---|---|"]
    lines += [f"| {label} | {r['success']:.3f} | {r['cost_usd']:.4f} |" for label, r in rows]
    return "\n".join(lines) + "\n"


def readme_source_lines(cv, results):
    models = len({tuple(v["models"]) for v in results["tasks"].values()}.pop())
    return [
        f"- Dataset: [NPULH/LLMRouterBench](https://huggingface.co/datasets/NPULH/LLMRouterBench) on "
        f"Hugging Face, pinned at revision [`{cv.REVISION[:7]}`](https://huggingface.co/datasets/"
        f"NPULH/LLMRouterBench/tree/{cv.REVISION}), one file `{cv.FILE}` of {cv.SIZE:,} bytes, checked "
        "by size and sha256 before it is read as a stream, with nothing extracted to disk",
        f"- Licence: MIT, as the dataset's LICENSE file states, with the line \"{COPYRIGHT}\"; its scope "
        "paragraph keeps third-party material, such as the benchmarks' own questions, under its own "
        "licence. This repo commits no part of the dataset, only numbers derived from it",
        f"- Full results, with every one of the {models} single models and the routed rows that beat each "
        "on both counts: [RESULTS.md](evidence/llmrouterbench/RESULTS.md) and "
        "[results.json](evidence/llmrouterbench/results.json); source, the pool, the kept and dropped "
        f"benchmarks and what a row keeps: {EVIDENCE_LINK}"]


def test_readme_llmrouterbench_counts_and_tables_are_the_committed_results(cv):
    results, section = committed(), readme_subsection()
    lines = readme_source_lines(cv, results)
    assert "\n".join(lines[:2] + [readme_counts(results), lines[2]]) + "\n" in section
    assert readme_columns(results) + "\n\n" + readme_tables(results) in section


def test_readme_llmrouterbench_reading_and_limits_are_results_md_lines():
    section = readme_subsection()
    reading, limits = results_md_bullets()
    block = ("Reading it:\n\n" + "\n".join(to_readme(b) for b in reading) + "\n\nLimits:\n\n"
             + "\n".join(to_readme(b) for b in limits) + "\n")
    assert block in section
    phrases = [p for p in reading_phrases(committed()) if not p.startswith("the committed file,")]
    assert len(phrases) == len(reading_phrases(committed())) - 1
    for phrase in phrases:
        assert to_readme(phrase) in section, phrase
    assert HALF_SCORES in section and "per benchmark, not per prompt" in section
    assert "](README.md)" not in section and "](results.json)" not in section and "../" not in section


def test_readme_llmrouterbench_regenerate_and_layout():
    section, text = readme_subsection(), readme_text()
    assert section.rstrip("\n").endswith(REGENERATE_LINE + "\n\n" + REGENERATE.rstrip("\n"))
    assert section.count("```bash\n") == 1 and "\n$ " not in section
    layout = text.split("\n## Layout\n", 1)[1].split("\n## ", 1)[0]
    assert layout.count(LAYOUT) == 1
    assert layout.index(LCB_LAYOUT) + len(LCB_LAYOUT) == layout.index(LAYOUT)
    assert section.isascii() and "\u2013" not in section and "\u2014" not in section
    assert not re.search(r"(?m)(^|[\s(])/(Users|home)/", section)


def test_readme_llmrouterbench_tables_follow_the_file(cv):
    results = committed()
    before = readme_tables(results), readme_counts(results), readme_source_lines(cv, results)
    fake = json.loads(json.dumps(results))
    summary_row(fake, 0.8, "cost_blind", "routed")["success"] = 0.6
    _, best, _ = single_models(fake)
    best["cost_usd"] = 400.0
    summary_row(fake, 0.1, "cost_effective", "oracle")["success"] = 0.9
    after = readme_tables(fake)
    assert after != before[0]
    assert "| 0.8 | `cost_blind` | 0.600 | 173.4190 | 0.434 |" in after
    assert "| Per-item oracle: on each item, the cheapest model that scored 1, or the cheapest model, " \
           "counted wrong, when none did | 0.900 | 33.6900 |" in after
    assert "| Always `openai/gpt-5`, which `cost_blind` takes on every seed of 4 tasks at bar 0.1 " \
           "| 0.591 | 191.4699 |" in before[0]
    assert "`aime` 60 items, `arc-agi` 400," in before[1] and "12,066 in all), 50 seeds;" in before[1]
    assert "every one of the 13 single models" in before[2][2]
    task_row(fake, 0.1, "cost_blind", "hle")["routed_models"] = {"google/gemini-2.5-flash": 50}
    with pytest.raises(AssertionError):
        readme_tables(fake)


def test_to_readme_rewrites_only_the_design_and_readme_links():
    line = "- a (DESIGN 12.3), b (see [README.md](README.md)), [results.json](results.json)"
    assert to_readme(line) == ("- a (`DESIGN.md` 12.3), b (see [evidence/llmrouterbench/README.md]"
                               "(evidence/llmrouterbench/README.md)), [results.json](results.json)")
