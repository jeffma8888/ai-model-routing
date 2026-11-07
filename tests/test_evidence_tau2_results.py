"""v1.53 tau2-bench results contract (DESIGN 12.15), written before the results were committed.

The committed ``evidence/tau2-bench/results.json`` is made and printed by the RouterBench
results script, ``evidence/routerbench/results.py``, reused unchanged. The first tests need
no download: they check the committed file and RESULTS.md against each other. The last three
read the 12 pinned run files only when they are already in the default cache and skip
otherwise (CI never downloads them): one rebuilds results.json and requires the committed
bytes, one rebuilds the split sizes and the success span behind the bars, and one rebuilds
every sensitivity line in RESULTS.md. The README part (v1.55, DESIGN 12.8) builds the
`### tau2-bench` subsection's tables, counts, single-agent sentence and Reading it numbers from
the committed file, and requires each limit phrase it takes from RESULTS.md in both files.
"""

import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows, split_items

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "tau2-bench"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
README = ROOT / "README.md"
TABLE_COMMAND = ("$ python evidence/routerbench/results.py --table "
                 "evidence/tau2-bench/results.json")
BARS = [0.3, 0.4, 0.5, 0.6, 0.7, 0.8]
REGENERATE = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/tau2-bench/convert.py --out tau2-matrix.jsonl\n"
    "model-routing evaluate --outcomes tau2-matrix.jsonl --bar 0.3 0.4 0.5 0.6 0.7 0.8 --seeds 50"
    " --json > tau2-evaluate.json\n"
    "python evidence/routerbench/results.py --evaluate tau2-evaluate.json"
    " --out evidence/tau2-bench/results.json\n"
    "python evidence/routerbench/results.py --table evidence/tau2-bench/results.json\n"
    "```\n")
MODELS = ["anthropic/claude-3-7-sonnet-20250219", "openai/gpt-4.1-2025-04-14",
          "openai/gpt-4.1-mini-2025-04-14", "openai/o4-mini-2025-04-16"]
TASKS = {"airline": 50, "retail": 114, "telecom": 114}
CONFIG = {"bars": BARS, "seeds": list(range(50)), "flavors": ["cost_effective", "cost_blind"],
          "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95}


def load(name, path):
    if not path.is_file():
        raise ModuleNotFoundError(f"no script at {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def rs():
    return load("routerbench_results", ROOT / "evidence" / "routerbench" / "results.py")


@pytest.fixture(scope="module")
def cv():
    return load("tau2_convert_for_results", FOLDER / "convert.py")


def committed():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def results_md():
    return RESULTS_MD.read_text(encoding="utf-8")


def rate(value):
    return "-" if value is None else f"{value:.3f}"


def summary_row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"]
            if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1, (bar, flavor, strategy)
    return rows[0]


def task_row(results, bar, flavor, task):
    rows = [r for r in results["per_task"] if (r["bar"], r["flavor"], r["task"]) == (bar, flavor, task)]
    assert len(rows) == 1 and rows[0]["strategy"] == "routed", (bar, flavor, task)
    return rows[0]


def single_models(results):
    """The model rows of the first (bar, flavor), with the best and the cheapest of them."""
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == first and r["strategy"].startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    cheapest = min(models, key=lambda r: (r["cost_usd"], -r["success"], r["strategy"]))
    return models, best, cheapest


def name(row):
    return row["strategy"][len("model:"):]


def beats_statement(results):
    """The RESULTS.md sentence on routed rows against single agents (DESIGN 12.15)."""
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
        return (f"No routed row beats any of the {len(models)} single agents on both counts: "
                f"against each of them, every routed row in the table has lower held-out success "
                f"or a higher cost.")
    return "Routed rows beat these single agents on both counts: " + "; ".join(beaten) + "."


def join(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def reading_phrases(results):
    """The numbers of the RESULTS.md "Reading it" bullets and the file size, from the file."""
    config = results["config"]
    seeds, bars, b0 = len(config["seeds"]), config["bars"], config["bars"][0]
    cells = seeds * len(results["tasks"])
    _, best, cheapest = single_models(results)
    ce = {bar: summary_row(results, bar, "cost_effective", "routed") for bar in bars}
    cb = [summary_row(results, bar, "cost_blind", "routed") for bar in bars]
    boc = summary_row(results, b0, "cost_effective", "best_on_calibration")
    oracle = summary_row(results, b0, "cost_effective", "oracle")
    assert all((r["success"], r["cost_usd"]) == (cb[0]["success"], cb[0]["cost_usd"]) for r in cb)
    more = "no more" if ce[b0]["success"] <= cheapest["success"] else "more"
    # "As the bar rises fewer cells clear ... and its cost rises toward that of best_on_calibration"
    assert all(ce[a]["cleared_rate"] >= ce[b]["cleared_rate"] and ce[a]["cost_usd"] <= ce[b]["cost_usd"]
               for a, b in zip(bars, bars[1:]))
    assert ce[bars[-1]]["cost_usd"] == boc["cost_usd"]
    phrases = [
        f"At bar {b0} a model clears on {round(ce[b0]['cleared_rate'] * cells)} of the {cells} "
        f"(domain, seed) cells",
        f"spends {ce[b0]['cost_usd'] / best['cost_usd']:.3f} of the best single agent's cost for a "
        f"held-out success of {ce[b0]['success']:.3f}, against {best['success']:.3f} for that agent "
        f"(`{name(best)}`)",
        f"Always calling the cheapest agent, `{name(cheapest)}`, reaches {cheapest['success']:.3f} "
        f"at {cheapest['cost_usd']:.4f} USD, so at bar {b0} the router pays "
        f"{ce[b0]['cost_usd'] / cheapest['cost_usd']:.1f} times as much for {more} held-out success",
        f"`cost_blind` reaches {cb[0]['success']:.3f} at {cb[0]['cost_usd'] / best['cost_usd']:.3f} "
        f"of the best single agent's cost at every bar, against `best_on_calibration`'s "
        f"{boc['success']:.3f} at {boc['cost_usd'] / best['cost_usd']:.3f}",
        f"a nominal one-sided {(1 - config['confidence']) / 2:.3f}",
        f"the committed file, {RESULTS.stat().st_size:,} bytes,"]
    # retail: the run of lowest bars at which every seed goes to the cheapest agent
    all_cheap = []
    for bar in bars:
        if task_row(results, bar, "cost_effective", "retail")["routed_models"] != {name(cheapest): seeds}:
            break
        all_cheap.append(bar)
    assert all_cheap, "no bar routes every retail seed to the cheapest agent"
    retail = task_row(results, all_cheap[0], "cost_effective", "retail")
    retail_cb = task_row(results, all_cheap[0], "cost_blind", "retail")
    assert all((task_row(results, bar, "cost_effective", "retail")["success"],
                task_row(results, bar, "cost_effective", "retail")["cost_usd"])
               == (retail["success"], retail["cost_usd"]) for bar in all_cheap)
    phrases.append(
        f"On retail at bar{'s' if len(all_cheap) > 1 else ''} {join([str(b) for b in all_cheap])} "
        f"`cost_effective` routes all {seeds} seeds to `{name(cheapest)}`, for a held-out success "
        f"of {retail['success']:.3f} at {retail['cost_usd']:.4f} USD, against `cost_blind`'s "
        f"{retail_cb['success']:.3f} at {retail_cb['cost_usd']:.4f} USD there")
    airline = task_row(results, b0, "cost_effective", "airline")
    none_bar = next(bar for bar in bars
                    if task_row(results, bar, "cost_effective", "airline")["cleared_rate"] == 0)
    phrases.append(f"on airline a model clears on {round(airline['cleared_rate'] * seeds)} of the "
                   f"{seeds} seeds at bar {b0} and on none from bar {none_bar}")
    for bar in bars:
        v = ce[bar]["bar_violation_rate"]
        if v:
            cleared = round(ce[bar]["cleared_rate"] * cells)
            phrases.append(f"{v:.3f} at bar {bar} is {round(v * cleared)} of the {cleared} cells "
                           f"that cleared")
    top = max(r["success"] for r in results["summary"] if r["strategy"] == "routed")
    assert oracle["success"] - top >= 0.1
    phrases.append(f"The per-item oracle reaches {oracle['success']:.3f} at {oracle['cost_usd']:.4f} "
                   f"USD, while the highest routed success of either flavor at any bar is {top:.3f}")
    return phrases


def sensitivity_line(prefix, row):
    return (f"- {prefix}, bar {row['bar']}, `{row['flavor']}`: routed success {row['success']:.3f} "
            f"at {row['cost_usd']:.4f} USD, cleared_rate {rate(row['cleared_rate'])}, "
            f"bar_violation_rate {rate(row['bar_violation_rate'])}")


def trial_models_line(trial, result):
    _, best, cheapest = single_models(result)
    return (f"- trial {trial}: best single agent `{name(best)}` {best['success']:.3f} at "
            f"{best['cost_usd']:.4f} USD, cheapest agent `{name(cheapest)}` "
            f"{cheapest['success']:.3f} at {cheapest['cost_usd']:.4f} USD")


# --- the committed file and RESULTS.md ------------------------------------------------------

def test_committed_results_are_small_reduced_and_pinned(rs):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    results = json.loads(text)
    assert text == json.dumps(rs.reduce(results), indent=2) + "\n"
    assert results["config"] == CONFIG
    assert results["tasks"] == {task: {"items": n, "models": MODELS} for task, n in TASKS.items()}
    keys = {(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]}
    assert len(results["summary"]) == len(keys) == 6 * 2 * (4 + len(MODELS)) == 96
    task_keys = {(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]}
    assert len(results["per_task"]) == len(task_keys) == 6 * 2 * 3 == 36
    assert all(r["strategy"] == "routed" for r in results["per_task"])
    assert all(sum(r["routed_models"].values()) == 50 and set(r["routed_models"]) <= set(MODELS)
               for r in results["per_task"])


def test_results_md_shows_the_table_of_the_committed_results(rs):
    block = "```text\n" + TABLE_COMMAND + "\n" + rs.table(committed()) + "\n```\n"
    assert block in results_md()


def test_results_md_regenerate_block_and_sources(cv):
    text = results_md()
    assert REGENERATE in text
    for needle in ["https://github.com/sierra-research/tau2-bench", cv.REVISION,
                   "`data/tau2/results/final`", "MIT", "Copyright (c) 2025 Sierra Research",
                   "(README.md)", "(results.json)", "--task-by all", "--trial", "DESIGN 12.15",
                   "airline: 29 tasks differ, retail: 114", "openai/gpt-4.1-2025-04-14",
                   "`user_cost`", "`agent_cost`", "`reward_info.reward`"]:
        assert needle in text, needle
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text


def test_results_md_single_agent_sentence_is_the_committed_results():
    assert beats_statement(committed()) in results_md()


def test_beats_statement_names_a_row_that_beats_an_agent():
    fake = json.loads(json.dumps(committed()))
    _, best, _ = single_models(fake)
    routed = summary_row(fake, 0.5, "cost_blind", "routed")
    routed["success"], routed["cost_usd"] = best["success"], best["cost_usd"] / 2
    assert beats_statement(fake).startswith("Routed rows beat these single agents on both counts: ")
    assert f"`{name(best)}` (by bar 0.5 `cost_blind`)" in beats_statement(fake)
    routed["cost_usd"] = best["cost_usd"]
    assert f"`{name(best)}` (by" not in beats_statement(fake)


def test_results_md_reading_numbers_are_the_committed_results():
    results, text = committed(), results_md()
    for phrase in reading_phrases(results):
        assert phrase in text, phrase


def test_evidence_readme_links_the_results():
    text = (FOLDER / "README.md").read_text(encoding="utf-8")
    assert "(RESULTS.md)" in text and "(results.json)" in text
    assert "not committed yet" not in text


# --- the README subsection (DESIGN 12.8, v1.55) ---------------------------------------------

HEADINGS = ["RouterBench", "AutoBench", "AutoBench judges", "tau2-bench", "Delegation on AutoBench"]
LIMITS = ["date from 2025, and the costs are those the runs recorded at the prices of their time",
          '("airline: 29 tasks differ, retail: 114")',
          "plays the user in every conversation",
          "the airline calibration half holds 16 to 35 tasks over the 50 seeds, under "
          "`min_samples` 30 on 40 of them",
          "holds on trials 1 and 3 but not on trial 2"]


def readme_subsection():
    text = README.read_text(encoding="utf-8")
    heading = "\n## Evidence: held-out results on public data\n"
    assert text.count(heading) == 1
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.*)$", section, re.M) == HEADINGS
    return section.split("\n### tau2-bench\n", 1)[1].split("\n### ", 1)[0]


def readme_tables(results):
    """The two tables of the README `### tau2-bench` subsection (DESIGN 12.8, v1.55)."""
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    models, best, cheapest_agent = single_models(results)
    cheapest = summary_row(results, *first, "cheapest")
    lines = ["| Bar | Flavor | Held-out success | Cost (USD) | Cost / best single agent "
             "| Cost / cheapest agent | Cleared rate | Bar-violation rate |",
             "|---|---|---|---|---|---|---|---|"]
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            r = summary_row(results, bar, flavor, "routed")
            lines.append(f"| {bar} | `{flavor}` | {r['success']:.3f} | {r['cost_usd']:.4f} "
                         f"| {r['cost_usd'] / best['cost_usd']:.3f} "
                         f"| {r['cost_usd'] / cheapest['cost_usd']:.1f} "
                         f"| {rate(r['cleared_rate'])} | {rate(r['bar_violation_rate'])} |")
    assert summary_row(results, *first, "oracle")["success"] < 1.0
    marks = {best["strategy"]: " (best single agent)", cheapest_agent["strategy"]: " (cheapest single agent)"}
    baselines = [("Per-item oracle: on each task, the cheapest agent that succeeded on it, or the "
                  "cheapest agent, counted wrong, when none did", "oracle")]
    baselines += [(f"Always `{name(m)}`{marks.get(m['strategy'], '')}", m["strategy"]) for m in models]
    baselines += [("Best agent on the calibration half, per domain", "best_on_calibration"),
                  ("Cheapest agent on the calibration half, per domain", "cheapest")]
    lines += ["", "| Baseline | Held-out success | Cost (USD) |", "|---|---|---|"]
    for label, strategy in baselines:
        r = summary_row(results, *first, strategy)
        lines.append(f"| {label} | {r['success']:.3f} | {r['cost_usd']:.4f} |")
    return "\n".join(lines) + "\n"


def readme_counts(results):
    tasks, config = results["tasks"], results["config"]
    models = {tuple(t["models"]) for t in tasks.values()}
    assert len(models) == 1
    sizes = [f"{task} {t['items']}" for task, t in tasks.items()]
    sizes[0] += " tasks"
    return (f"{len(models.pop())} agents, one routing task per domain ({', '.join(sizes)}), "
            f"trial 0 of the 4 trials, {len(config['seeds'])} seeds; each domain is split in half "
            f"per seed and routed at bars {config['bars'][0]} to {config['bars'][-1]} in both "
            f"flavors")


def test_readme_tau2_tables_counts_and_single_agent_sentence_are_the_committed_results():
    results, section = committed(), readme_subsection()
    assert "\n" + readme_tables(results) in section
    assert readme_counts(results) in section
    assert beats_statement(results) in section


def test_readme_tau2_reading_numbers_are_the_committed_results():
    section = readme_subsection()
    phrases = [p for p in reading_phrases(committed()) if not p.startswith("the committed file,")]
    assert len(phrases) == len(reading_phrases(committed())) - 1
    for phrase in phrases:
        assert phrase in section, phrase


def test_readme_tau2_links_source_licence_limits_and_commands(cv):
    section, md = readme_subsection(), results_md()
    revision = cv.REVISION
    for needle in ("[sierra-research/tau2-bench](https://github.com/sierra-research/tau2-bench)",
                   f"[`{revision[:7]}`](https://github.com/sierra-research/tau2-bench/tree/"
                   f"{revision})", "`data/tau2/results/final`", "MIT",
                   '"Copyright (c) 2025 Sierra Research"', "(evidence/tau2-bench/RESULTS.md)",
                   "(evidence/tau2-bench/results.json)", "(evidence/tau2-bench/README.md)",
                   "`reward_info.reward`", "`agent_cost`", "`user_cost`",
                   "chosen after a first run at 0.6 to 0.9"):
        assert needle in section, needle
    for phrase in LIMITS:
        assert phrase in section and phrase in md, phrase
    assert REGENERATE in section and REGENERATE in md
    assert section.isascii()


def test_readme_tau2_tables_print_a_dash_for_no_rate():
    fake = json.loads(json.dumps(committed()))
    summary_row(fake, 0.3, "cost_blind", "routed")["bar_violation_rate"] = None
    row = [line for line in readme_tables(fake).split("\n") if "| 0.3 | `cost_blind` |" in line]
    assert len(row) == 1 and row[0].endswith(" | - |")


# --- the pinned files, only when already cached ---------------------------------------------

@pytest.fixture(scope="module")
def extracts(cv):
    """Per trial, the 12 extracts of the pinned run files, each file read once."""
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("the 12 pinned tau2-bench run files are not in the default cache")
    by_trial = {trial: [] for trial in range(4)}
    for n, (size, sha) in cv.FILES.items():
        cv.verify(folder / n, size, sha)
        run = cv.read_run(folder / n)
        for trial in by_trial:
            by_trial[trial].append(cv.extract(run, trial=trial))
    return by_trial


def run_evaluate(rows):
    result = evaluate(outcomes_from_rows(rows), bars=BARS, seeds=range(50))
    result.pop("cells")
    return result


def test_real_results_regenerate_byte_identical(rs, cv, extracts):
    rows, report = cv.convert(extracts[0])
    assert report["models"] == MODELS and report["kept"] == TASKS
    assert json.dumps(rs.reduce(run_evaluate(rows)), indent=2) + "\n" == RESULTS.read_text(
        encoding="utf-8")


def test_real_split_sizes_and_success_span_are_in_results_md(cv, extracts):
    rows, _ = cv.convert(extracts[0])
    text = results_md()
    sizes = {}
    for task in TASKS:
        items = {r["item"] for r in rows if r["task"] == task}
        sizes[task] = [len(split_items(items, seed)[0]) for seed in range(50)]
    under = sum(1 for n in sizes["airline"] if n < CONFIG["min_samples"])
    assert under > 0 and all(min(sizes[t]) >= CONFIG["min_samples"] for t in ("retail", "telecom"))
    assert (f"the airline calibration half holds {min(sizes['airline'])} to "
            f"{max(sizes['airline'])} tasks over the 50 seeds, under `min_samples` "
            f"{CONFIG['min_samples']} on {under} of them; retail holds {min(sizes['retail'])} to "
            f"{max(sizes['retail'])} and telecom {min(sizes['telecom'])} to "
            f"{max(sizes['telecom'])}") in text
    rates = []
    for task in TASKS:
        for model in MODELS:
            got = [r["correct"] for r in rows if (r["task"], r["model"]) == (task, model)]
            rates.append(sum(got) / len(got))
    low, high = min(rates), max(rates)
    assert BARS == [k / 10 for k in range(math.floor(low * 10), math.ceil(high * 10) + 1)]
    assert (f"the agents' per-domain success rates at trial 0 run from {low:.3f} to {high:.3f}"
            in text)


def test_real_sensitivity_lines_are_in_results_md(cv, extracts):
    text = results_md()
    rows, report = cv.convert(extracts[0], task_by="all")
    assert report["kept"] == {"all": sum(TASKS.values())}
    pooled = run_evaluate(rows)
    needles = [sensitivity_line("pooled", summary_row(pooled, bar, "cost_effective", "routed"))
               for bar in BARS]
    for trial in (1, 2, 3):
        rows, report = cv.convert(extracts[trial])
        assert report["kept"] == TASKS and report["trial"] == trial
        result = run_evaluate(rows)
        needles += [sensitivity_line(f"trial {trial}", summary_row(result, BARS[0], flavor, "routed"))
                    for flavor in CONFIG["flavors"]]
        needles.append(trial_models_line(trial, result))
        needles.append(f"- trial {trial}, single agents: {beats_statement(result)}")
    assert len(needles) == 6 + 3 * 4
    for needle in needles:
        assert needle + "\n" in text, needle
