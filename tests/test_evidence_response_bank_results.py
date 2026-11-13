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

v1.293 (DESIGN 12.21, row E20c): RESULTS.md and the evidence README. The tests build the table,
the single-model sentence and every Reading it number from the committed file and require them
in RESULTS.md, with the dataset's LICENSE quoted and the dataset repository attributed; check the
evidence README against the converter's constants and the 12.20 counts; and, when the four
pinned files are cached, check both against the converter's report and the calibration scores
file. The tests that read the two files were committed before them under strict xfail
(``FileNotFoundError``), removed by the commit that adds them (v1.294).


v1.296 (DESIGN 12.8, row E20e): the README `### LLM Routing Response Bank` subsection. The tests
build its source lines, counts sentence and two tables from the converter and the committed file,
take its Reading it and Limits lines from RESULTS.md under one rewrite, and check its regenerate
line and block, the opening-paragraph label and the Layout line. The tests that read the README
were committed before it under strict xfail (``AssertionError``), removed by the commit that adds
the subsection (v1.297).
"""

import importlib.util
import json
import math
import re
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
    # The 12.1 rows carry no `missing` field: a null `input_tokens` is the only mark a `missing`
    # cell leaves in a row (DESIGN 12.20), so it stands for "a missing cell" here.
    assert all(r["input_tokens"] is None for r in real_rows if r["cost_usd"] == 0)
    assert all(zeros[key] < rows[key] for key in rows)


# --- RESULTS.md and the evidence README (v1.293) --------------------------------------------

RESULTS_MD = FOLDER / "RESULTS.md"
EVIDENCE_README = FOLDER / "README.md"
DATASET_URL = "https://huggingface.co/datasets/Lurume/llm-routing-response-bank"
TABLE_COMMAND = "$ python evidence/routerbench/results.py --table evidence/response-bank/results.json"
REGENERATE = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/response-bank/convert.py --out response-bank-matrix.jsonl\n"
    "model-routing evaluate --outcomes response-bank-matrix.jsonl --bar 0.8 0.9 --seeds 50 --json"
    " > response-bank-evaluate.json\n"
    "python evidence/routerbench/results.py --evaluate response-bank-evaluate.json"
    " --out evidence/response-bank/results.json\n"
    "python evidence/routerbench/results.py --table evidence/response-bank/results.json\n"
    "```\n")
MATRIX_BLOCK = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/response-bank/convert.py --out response-bank-matrix.jsonl\n"
    "```\n")
# The dataset's LICENSE file at the pinned revision (1,480 bytes, read 2026-11-12), every
# paragraph and list item but its title, each joined onto one line (the lead-in from v1.295).
LICENSE_SHA256 = "ebff7b5d9a32da5f04702a29a8b6ce45bbc7b805963cfe45aeb85cd00e0ef6cd"
TERMS = ("Planned license: Open Data Commons Attribution License v4.0 (ODC-BY-4.0, "
         "https://opendatacommons.org/licenses/by/4-0/). Final licensing wording will be attached "
         "at the formal publication of the associated study; until then, you may use, "
         "redistribute, and build on this data under ODC-BY-4.0 terms with attribution to this "
         "dataset repository.")
FAMILY_LEAD = "Per-family terms additionally apply:"
FAMILY_TERMS = {
    "mmlu_pro": "derived from TIGER-Lab/MMLU-Pro (MIT). Retain the upstream notice when redistributing.",
    "livecodebench": ("problems originate from LeetCode, AtCoder, and Codeforces and are republished "
                      "as gathered by the LiveCodeBench benchmark; problem statements remain the "
                      "copyright of their original platforms."),
    "aime": ("AIME 2025 problems are copyright MAA / Art of Problem Solving, reproduced here without "
             "modification for research use."),
    "gpqa_diamond": ("only non-recoverable metadata (task ids, prompt hashes, lengths, outcomes, "
                     "usage, cost) is included. Users must obtain the questions from the gated "
                     "official source under its own terms; the terms of that source (including the "
                     "prohibition on publishing examples in plain text and requests not to train on "
                     "them) bind downstream use."),
}
NO_WARRANTY = ("Model responses are outputs of third-party language models, collected and released "
               "by the dataset compilers. The compilers make no warranty as to accuracy or fitness "
               "for any purpose.")
# The card's evaluation counts per family (its `Families (evaluation counts)` line); the
# calibration split holds the rest of each family's 12.20 items.
EVALUATION = {"aime": 22, "gpqa_diamond": 166, "livecodebench": 967, "mmlu_pro": 11904}
# The 12.20 Default output per family: missing cells, length finishes, length finishes scored 1,
# other finishes.
FINISHES = {"aime": (0, 5, 0, 0), "gpqa_diamond": (0, 71, 0, 6), "livecodebench": (0, 246, 16, 3),
            "mmlu_pro": (6, 128, 1, 12)}
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd", "input_tokens", "output_tokens"]
NOT_KEPT = "no prompt, reference answer, response text or reasoning text"
HOME = re.compile(r"(?m)(^|[\s(])/(Users|home)/")


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


def seeds_cleared(results, bar, task):
    n = task_row(results, bar, "cost_effective", task)["cleared_rate"] * len(results["config"]["seeds"])
    assert abs(n - round(n)) < 1e-9
    return round(n)


def reading_phrases(results):
    """Every number of the RESULTS.md "Reading it" bullets built from the committed file (12.21)."""
    config = results["config"]
    seeds, bars, b0, b9 = len(config["seeds"]), config["bars"], config["bars"][0], config["bars"][-1]
    tasks = list(results["tasks"])
    cells = seeds * len(tasks)
    models, best, cheapest = single_models(results)
    ce = {bar: summary_row(results, bar, "cost_effective", "routed") for bar in bars}
    cb = [summary_row(results, bar, "cost_blind", "routed") for bar in bars]
    boc = {bar: summary_row(results, bar, "cost_effective", "best_on_calibration") for bar in bars}
    low = summary_row(results, b0, "cost_effective", "cheapest")
    oracle = summary_row(results, b0, "cost_effective", "oracle")
    assert all((r["success"], r["cost_usd"]) == (cb[0]["success"], cb[0]["cost_usd"]) for r in cb)
    assert seeds_cleared(results, b0, "aime") == 0, "aime clears on some seed"
    more = "no more" if ce[b0]["success"] <= cheapest["success"] else "more"
    whole = {}
    for t in tasks:
        picks = task_row(results, b0, "cost_effective", t)["routed_models"]
        if len(picks) == 1:
            whole.setdefault(next(iter(picks)), []).append(t)
    assert whole, "no task goes to one model on every seed"
    top_cleared = [(t, seeds_cleared(results, b9, t)) for t in tasks if seeds_cleared(results, b9, t)]
    assert top_cleared, "no task clears at the highest bar"
    assert (ce[b9]["success"], ce[b9]["cost_usd"]) == (boc[b9]["success"], boc[b9]["cost_usd"]), \
        "cost_effective at the highest bar is not best_on_calibration"
    gap = cb[0]["success"] - best["success"]
    assert gap > 0, "cost_blind is not above the best single model"
    largest = max(tasks, key=lambda t: results["tasks"][t]["items"])
    picks = task_row(results, b0, "cost_blind", largest)["routed_models"]
    pick = min(picks, key=lambda m: (-picks[m], m))
    costliest = max(models, key=lambda r: r["cost_usd"])
    assert name(costliest) == pick, "cost_blind's largest-task pick is not the costliest model"
    phrases = [
        f"At bar {b0} a model clears on {round(ce[b0]['cleared_rate'] * cells)} of the {cells} "
        f"(task, seed) cells; of their {seeds} seeds each, it clears on "
        + join([f"{seeds_cleared(results, b0, t)} of `{t}`" for t in tasks]),
        f"spends {ce[b0]['cost_usd'] / best['cost_usd']:.3f} of the best single model's cost for a "
        f"held-out success of {ce[b0]['success']:.3f}, against {best['success']:.3f} for that model "
        f"(`{name(best)}`)",
        f"Always calling the cheapest model, `{name(cheapest)}`, reaches {cheapest['success']:.3f} "
        f"at {cheapest['cost_usd']:.4f} USD, so at bar {b0} the router pays "
        f"{ce[b0]['cost_usd'] / cheapest['cost_usd']:.3f} of that cost for {more} held-out success",
        f"the `cheapest` baseline, which takes the model of lowest mean calibration cost on each "
        f"task, reaches {low['success']:.3f} at {low['cost_usd']:.4f} USD",
        "; ".join(f"it routes every seed of {join(['`' + t + '`' for t in ts])} to `{m}`"
                  for m, ts in sorted(whole.items())),
        f"At bar {b9} a model clears on {round(ce[b9]['cleared_rate'] * cells)} of the {cells} "
        f"cells, " + join([f"{n} {'seed' if n == 1 else 'seeds'} of `{t}`" for t, n in top_cleared]),
        f"`cost_effective` there reaches {ce[b9]['success']:.3f} at "
        f"{ce[b9]['cost_usd'] / best['cost_usd']:.3f} of the best single model's cost, the held-out "
        f"success and cost of `best_on_calibration`",
        f"`cost_blind` reaches {cb[0]['success']:.3f} at {cb[0]['cost_usd'] / best['cost_usd']:.3f} "
        f"of the best single model's cost at every bar, {gap:.4f} above that model's held-out "
        f"success",
        f"the {len(models)} single models' held-out successes run from "
        f"{min(r['success'] for r in models):.3f} to {max(r['success'] for r in models):.3f}",
        f"at bar {b0} it routes {picks[pick]} of the {seeds} `{largest}` seeds to `{pick}`, the "
        f"single model with the highest cost, {costliest['cost_usd']:.4f} USD",
        f"a nominal one-sided {(1 - config['confidence']) / 2:.3f}",
        f"the committed file, {RESULTS.stat().st_size:,} bytes,"]
    for flavor in config["flavors"]:
        for bar in bars:
            row = summary_row(results, bar, flavor, "routed")
            v = row["bar_violation_rate"]
            if v:
                cleared = row["cleared_rate"] * cells
                assert abs(cleared - round(cleared)) < 1e-9
                n = round(cleared)
                assert abs(v * n - round(v * n)) < 1e-9
                phrases.append(f"{v:.3f} at bar {bar} (`{flavor}`) is {round(v * n)} of {n} cleared "
                               f"{'cell' if n == 1 else 'cells'}")
    top = max(r["success"] for r in results["summary"] if r["strategy"] == "routed")
    phrases.append(f"The per-item oracle reaches {oracle['success']:.3f} at {oracle['cost_usd']:.4f} "
                   f"USD, while the highest routed success of either flavor at any bar is {top:.3f}")
    return phrases


def test_results_md_shows_the_table_of_the_committed_results(rs):
    block = "```text\n" + TABLE_COMMAND + "\n" + rs.table(committed()) + "\n```\n"
    assert block in results_md()


def test_results_md_regenerate_block_sources_and_licence(cv):
    text = results_md()
    assert REGENERATE in text
    for needle in [DATASET_URL, f"[`{cv.REVISION}`]({DATASET_URL}/tree/{cv.REVISION})",
                   TERMS, f"\"{FAMILY_LEAD}\"", NO_WARRANTY, LICENSE_SHA256, "1,480 bytes", "ODC-BY-4.0",
                   "(README.md)", "(results.json)", "DESIGN 12.21", "0.767", "0.967",
                   "`z-ai/glm-5.3` on `aime`, 23 of 30", "`deepseek/deepseek-v4-pro` on `aime`, 29 of 30",
                   "only `gpqa_diamond` clears, on 1 seed of 50",
                   "1,018,191,580 bytes", "`~/.cache/ai-model-routing-evidence/response-bank/`",
                   "per family, not per prompt", "To be added.",
                   f"`mmlu_pro` holds {ITEMS['mmlu_pro']:,} of the {sum(ITEMS.values()):,} items"]:
        assert needle in text, needle
    for file, (size, sha256) in cv.FILES.items():
        assert f"`{file}`, {size:,} bytes, sha256 `{sha256}`" in text, file
    for family, terms in FAMILY_TERMS.items():
        assert f"`{family}` subset: \"{terms}\"" in text, family
    for task, items in ITEMS.items():
        assert f"`{task}` {items:,}" in text, task
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text
    assert not HOME.search(text)


def test_results_md_single_model_sentence_is_the_committed_results():
    assert beats_statement(committed()) in results_md()


def test_results_md_reading_numbers_are_the_committed_results():
    text = results_md()
    for phrase in reading_phrases(committed()):
        assert phrase in text, phrase


def test_reading_phrases_say_no_more_when_the_router_does_not_pass_the_cheapest_model():
    fake = json.loads(json.dumps(committed()))
    _, _, cheapest = single_models(fake)
    assert any(p.endswith(" for more held-out success") for p in reading_phrases(fake))
    summary_row(fake, BARS[0], "cost_effective", "routed")["success"] = cheapest["success"]
    assert any(p.endswith(" for no more held-out success") for p in reading_phrases(fake))


def test_reading_phrases_fail_when_cost_blind_is_not_above_the_best_model():
    fake = json.loads(json.dumps(committed()))
    _, best, _ = single_models(fake)
    for bar in BARS:
        summary_row(fake, bar, "cost_blind", "routed")["success"] = best["success"]
    with pytest.raises(AssertionError, match="not above"):
        reading_phrases(fake)


def model_table(cv):
    rows = ["| raw ID | model |", "| --- | --- |"]
    rows += [f"| `{raw}` | `{cv.model_id(raw)}` |" for raw in cv.MODELS]
    return "\n".join(rows) + "\n"


def split_table(items, evaluation):
    rows = ["| task | calibration | evaluation | items |", "| --- | ---: | ---: | ---: |"]
    rows += [f"| `{t}` | {items[t] - evaluation[t]:,} | {evaluation[t]:,} | {items[t]:,} |"
             for t in sorted(items)]
    return "\n".join(rows) + "\n"


def finish_table(finishes):
    rows = ["| task | missing | length | length scored 1 | other finish |",
            "| --- | ---: | ---: | ---: | ---: |"]
    rows += [f"| `{t}` | " + " | ".join(f"{n:,}" for n in finishes[t]) + " |" for t in sorted(finishes)]
    return "\n".join(rows) + "\n"


def test_evidence_readme_states_the_source_models_splits_and_finishes(cv):
    text = evidence_readme()
    assert "(RESULTS.md)" in text and "(results.json)" in text
    for needle in [DATASET_URL, cv.REVISION, TERMS, MATRIX_BLOCK, NOT_KEPT, "To be added."]:
        assert needle in text, needle
    for file, (size, sha256) in cv.FILES.items():
        assert f"`{file}`, {size:,} bytes, sha256 `{sha256}`" in text, file
    assert model_table(cv) in text
    assert split_table(ITEMS, EVALUATION) in text
    assert finish_table(FINISHES) in text
    for key in ROW_KEYS:
        assert f"`{key}`" in text, key
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text
    assert not HOME.search(text)


def test_real_report_matches_the_evidence_readme_and_results_md(cv, response_bank_pinned, real_rows):
    _, out, _, _ = response_bank_pinned
    tasks = json.loads(out)["tasks"]
    assert {t: v["items"] for t, v in tasks.items()} == ITEMS
    assert all(v[k] == 0 for v in tasks.values()
               for k in ("dropped_incomplete", "dropped_unbilled", "dropped_prompt_differs"))
    finishes = {t: (v["missing_cells"], v["length_finishes"], v["length_successes"], v["other_finishes"])
                for t, v in tasks.items()}
    assert finish_table(finishes) in evidence_readme()
    calibration = {}
    for score in cv.read_jsonl(cv.default_cache_dir() / "scores_cal.jsonl", cv.score_record):
        calibration.setdefault(score["family"], set()).add(score["task_id"])
    evaluation = {t: ITEMS[t] - len(calibration[t]) for t in ITEMS}
    assert split_table(ITEMS, evaluation) in evidence_readme()
    text = results_md()
    missing = sum(f[0] for f in finishes.values())
    length = sum(f[1] for f in finishes.values())
    scored = sum(f[2] for f in finishes.values())
    assert f"the {missing} `missing` cells" in text
    assert f"{length} kept cells stopped at their length limit and {scored} of them score 1" in text
    items = {}
    for r in real_rows:
        items.setdefault(r["task"], set()).add(r["item"])
    halves = [len(split_items(sorted(items["aime"]), seed)[0]) for seed in range(50)]
    assert (f"holds {min(halves)} to {max(halves)} of its {len(items['aime'])} items over the 50 "
            f"seeds and is under `min_samples` {CONFIG['min_samples']} on "
            f"{sum(n < CONFIG['min_samples'] for n in halves)} of them") in text


# --- the README subsection (DESIGN 12.8, v1.296) --------------------------------------------

README = ROOT / "README.md"
EVIDENCE_HEADING = "\n## Evidence: held-out results on public data\n"
HEADING = "LLM Routing Response Bank"
HEADINGS = ["RouterBench", "AutoBench", "AutoBench judges", "tau2-bench", "LiveCodeBench",
            "LLMRouterBench", "LLM Routing Response Bank", "Delegation on AutoBench",
            "Delegation on tau2-bench", "Delegation on LLMRouterBench"]
INDENT = " " * 16
LRB_LAYOUT = INDENT + "(LLMRouterBench: evidence/llmrouterbench/RESULTS.md)\n"
LAYOUT = INDENT + "(LLM Routing Response Bank: evidence/response-bank/RESULTS.md)\n"
EVIDENCE_LINK = "[evidence/response-bank/README.md](evidence/response-bank/README.md)"
RESULTS_LINK = "[RESULTS.md](evidence/response-bank/RESULTS.md)"
ATTRIBUTION = ("the data behind these results is the LLM Routing Response Bank, from the dataset "
               "repository https://huggingface.co/datasets/Lurume/llm-routing-response-bank")
LABEL = ("whether the record scored 1 on LLMRouterBench, and whether the response scored 1 on the "
         "LLM Routing Response Bank)")
NUMBER = {4: "four"}
DESIGN_REF = re.compile(r"DESIGN (?=\d)")


def readme_text():
    return README.read_text(encoding="utf-8")


def readme_subsection():
    text = readme_text()
    assert text.count(EVIDENCE_HEADING) == 1
    section = text.split(EVIDENCE_HEADING, 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.*)$", section, re.M) == HEADINGS
    return section.split(f"\n### {HEADING}\n", 1)[1].split("\n### ", 1)[0]


def to_readme(line):
    """The v1.296 rewrite of a RESULTS.md line for the top-level README (DESIGN 12.8)."""
    return DESIGN_REF.sub("`DESIGN.md` ", line)


def results_md_bullets():
    """The five Reading it bullets and the five limits of RESULTS.md, before the size bullet."""
    body = results_md().split("\n## Reading it\n", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in body.splitlines() if line.startswith("- ")]
    assert len(bullets) == 11 and bullets[-1].startswith("- Size: "), bullets
    assert bullets[0].startswith("- `cost_effective`: ") and bullets[4].startswith("- The per-item oracle")
    assert bullets[5].startswith("- Each cost is ") and bullets[9].startswith("- Both splits: ")
    return bullets[:5], bullets[5:10]


def download_bytes(cv):
    return sum(size for size, _ in cv.FILES.values())


def readme_source_lines(cv, results):
    models = len({tuple(v["models"]) for v in results["tasks"].values()}.pop())
    return [
        f"- Dataset: [Lurume/llm-routing-response-bank]({DATASET_URL}) on Hugging Face, pinned at "
        f"revision [`{cv.REVISION[:7]}`]({DATASET_URL}/tree/{cv.REVISION}), {NUMBER[len(cv.FILES)]} "
        f"JSON Lines files of {download_bytes(cv):,} bytes in all, each checked by size and sha256, "
        "then read one line at a time",
        "- Licence: the dataset card names no standard licence and points to the dataset's LICENSE "
        f"file, which says: \"{TERMS}\" Its per-family terms are quoted in {RESULTS_LINK}. This repo "
        "commits no part of the dataset, only numbers derived from it",
        f"- Attribution, as those terms ask: {ATTRIBUTION}",
        f"- Full results, with every one of the {models} single models and the routed rows that beat each "
        f"on both counts: {RESULTS_LINK} and [results.json](evidence/response-bank/results.json); "
        f"source, the models, the tasks, the finishes and missing cells and what a row keeps: {EVIDENCE_LINK}"]


def readme_counts(results):
    config, tasks = results["config"], results["tasks"]
    models = {tuple(v["models"]) for v in tasks.values()}
    assert len(models) == 1 and config["flavors"] == ["cost_effective", "cost_blind"]
    parts = [f"`{t}` {v['items']:,}" + (" items" if i == 0 else "")
             for i, (t, v) in enumerate(tasks.items())]
    return (f"- What was run: {len(models.pop())} models, {len(tasks)} benchmark families, each one "
            f"routing task ({join(parts)}, {sum(v['items'] for v in tasks.values()):,} in all), "
            f"{len(config['seeds'])} seeds; each task is split in half per seed and routed at bars "
            f"{join([str(b) for b in config['bars']])} in both flavors. A success is a response whose "
            "`quality` is 1, the label of an exact-answer parser or, for code, of LiveCodeBench's tests, "
            "and the cost is the response's billed `official_usd`")


def readme_columns(results):
    cells = len(results["config"]["seeds"]) * len(results["tasks"])
    return ("Held-out success is the share of held-out items whose response scored 1, pooled over the "
            f"{len(results['tasks'])} tasks, and cost is the billed cost of answering them, both averaged "
            "over the seeds; the ratio divides that cost by the cost of the best single model. The cleared "
            f"rate is the share of the {cells} (task, seed) cells where some model cleared the bar on the "
            "calibration half, and the bar-violation rate is the share of cleared cells whose held-out "
            "success fell below the bar.")


def readme_tables(results):
    """The two tables of the README `### LLM Routing Response Bank` subsection (DESIGN 12.8, v1.296)."""
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
    rows = [("Per-item oracle: on each item, the cheapest model that scored 1, or the cheapest model, "
             "counted wrong, when none did", summary_row(results, *first, "oracle"))]
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


def regenerate_line(cv):
    return ("Regenerate (the converter downloads the four pinned files, about "
            f"{download_bytes(cv) / 1e9:.2f} GB, into a cache folder outside the repo, and verifying, "
            "reading and converting them takes about 3 seconds once they are cached; the `evidence` "
            "workflow does not rerun these commands yet, while the test suite rebuilds `results.json` "
            "from them only where the four pinned files are cached):")


def test_readme_response_bank_source_counts_and_tables_are_the_committed_results(cv):
    results, section = committed(), readme_subsection()
    lines = readme_source_lines(cv, results)
    assert "\n".join(lines[:3] + [readme_counts(results), lines[3]]) + "\n" in section
    assert readme_columns(results) + "\n\n" + readme_tables(results) in section


def test_readme_response_bank_reading_and_limits_are_results_md_lines():
    section = readme_subsection()
    reading, limits = results_md_bullets()
    block = ("Reading it:\n\n" + "\n".join(to_readme(b) for b in reading) + "\n\nLimits:\n\n"
             + "\n".join(to_readme(b) for b in limits) + "\n")
    assert block in section
    phrases = [p for p in reading_phrases(committed()) if not p.startswith("the committed file,")]
    assert len(phrases) == len(reading_phrases(committed())) - 1
    for phrase in phrases:
        assert to_readme(phrase) in section, phrase
    assert "per family, not per prompt" in section and "DESIGN 1" not in section and "DESIGN 5" not in section
    assert "](README.md)" not in section and "](results.json)" not in section and "../" not in section


def test_readme_response_bank_regenerate_label_and_layout(cv):
    section, text = readme_subsection(), readme_text()
    assert section.rstrip("\n").endswith(regenerate_line(cv) + "\n\n" + REGENERATE.rstrip("\n"))
    assert section.count("```bash\n") == 1 and "\n$ " not in section
    intro = text.split(EVIDENCE_HEADING, 1)[1].split("\n### ", 1)[0]
    assert LABEL in intro.split("\n\n", 1)[0]
    layout = text.split("\n## Layout\n", 1)[1].split("\n## ", 1)[0]
    assert layout.count(LAYOUT) == 1
    assert layout.index(LRB_LAYOUT) + len(LRB_LAYOUT) == layout.index(LAYOUT)
    assert section.isascii() and "\u2013" not in section and "\u2014" not in section
    assert not HOME.search(section)


def test_readme_response_bank_builders_follow_the_file(cv):
    results = committed()
    before = (readme_tables(results), readme_counts(results), readme_source_lines(cv, results),
              regenerate_line(cv))
    assert "| 0.8 | `cost_blind` | 0.874 | 57.4404 | 2.104 | 0.735 | 0.000 |" in before[0]
    assert "| Always `deepseek/deepseek-v4-pro`, the best single model | 0.872 | 27.2956 |" in before[0]
    assert "| Always `z-ai/glm-5.3-flash`, the cheapest single model | 0.845 | 6.2289 |" in before[0]
    assert "| Always `moonshotai/kimi-k2.7-code` | 0.871 | 71.0675 |" in before[0]
    assert "`aime` 30 items, `gpqa_diamond` 198," in before[1] and "13,315 in all), 50 seeds;" in before[1]
    assert "routed at bars 0.8 and 0.9 in both flavors" in before[1]
    assert "four JSON Lines files of 1,018,191,580 bytes in all" in before[2][0]
    assert "[`547beb3`](" in before[2][0] and "every one of the 5 single models" in before[2][3]
    assert "about 1.02 GB" in before[3]
    fake = json.loads(json.dumps(results))
    summary_row(fake, 0.8, "cost_blind", "routed")["success"] = 0.9
    _, best, _ = single_models(fake)
    best["cost_usd"] = 30.0
    after = readme_tables(fake)
    assert after != before[0]
    assert "| 0.8 | `cost_blind` | 0.900 | 57.4404 | 1.915 |" in after
    assert "| Always `deepseek/deepseek-v4-pro`, the best single model | 0.872 | 30.0000 |" in after


def test_to_readme_rewrites_only_the_design_references():
    line = "- a (DESIGN 12.3), b (`x`, DESIGN 5.3), DESIGN.md, the DESIGN, [README.md](README.md)"
    assert to_readme(line) == ("- a (`DESIGN.md` 12.3), b (`x`, `DESIGN.md` 5.3), DESIGN.md, the DESIGN, "
                               "[README.md](README.md)")


def test_results_md_reading_and_limits_hold_no_link():
    reading, limits = results_md_bullets()
    for bullet in reading + limits:
        assert "](" not in bullet, bullet
