"""v1.63 LiveCodeBench results contract (DESIGN 12.17), written before the results were committed.

The committed ``evidence/livecodebench/results.json`` is made and printed by the RouterBench
results script, ``evidence/routerbench/results.py``, reused unchanged, from
``model-routing evaluate --flavor cost_blind`` (12.4, v1.63): the submissions record no cost,
so ``cost_effective`` is never run on them. The first tests need no download: they check the
committed file, RESULTS.md and the evidence README against each other. The last ones read the
67 pinned files only when they are already in the default cache and skip otherwise (CI never
downloads them): they rebuild results.json and require the committed bytes, rebuild the split
sizes and the success span behind the bars, check cell by cell the two zero-cost identities
RESULTS.md states, and build its sentence on the seeds that clear a bar they then miss.
From v1.65 (DESIGN 12.8) the README `### LiveCodeBench` subsection is checked against the same
file and RESULTS.md.
"""

import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows, split_items

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "livecodebench"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
EVIDENCE_README = FOLDER / "README.md"
TABLE_COMMAND = ("$ python evidence/routerbench/results.py --table "
                 "evidence/livecodebench/results.json")
BARS = [0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]
TASK = "code_generation"
ITEMS = 713
REGENERATE = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/livecodebench/convert.py --out livecodebench-matrix.jsonl\n"
    "model-routing evaluate --outcomes livecodebench-matrix.jsonl"
    " --bar 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 --seeds 50 --flavor cost_blind"
    " --json > livecodebench-evaluate.json\n"
    "python evidence/routerbench/results.py --evaluate livecodebench-evaluate.json"
    " --out evidence/livecodebench/results.json\n"
    "python evidence/routerbench/results.py --table evidence/livecodebench/results.json\n"
    "```\n")
CONFIG = {"bars": BARS, "seeds": list(range(50)), "flavors": ["cost_blind"],
          "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95}
ZERO_COST = ("Every `cost_usd` is 0.0000 and every `vs_best_model` is `-`, because no cost is "
             "recorded (DESIGN 12.7 prints `-` when the best model's cost is 0)")
NOT_RUN = ("`cost_effective` is not run: with every cost 0 its routing sorts reduce to "
           "`cost_blind`'s (DESIGN 5.3), so its rows would only repeat the `cost_blind` rows")
SAME_PICK = ("with no cost the router takes the model with the highest Wilson lower bound on the "
             "calibration half, and with the same number of calibration problems for every model "
             "that is the model with the highest calibration success, so the two pick the same "
             "model on every seed")
COMPLEMENT = ("The split cuts one pool of 713 problems in two, so a model's rate on all of them is "
              "the mean of its two halves weighted by size, and a calibration half that comes out "
              "above it leaves the held-out half below it")
CAVEATS = ["the contamination LiveCodeBench dates its problems to expose",
           "they drew 1, 4 or 10 samples per problem",
           "The problems come from LeetCode, AtCoder and Codeforces",
           "With no cost, this matrix says which model clears a bar, never what it costs"]


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
    return load("livecodebench_convert_for_results", FOLDER / "convert.py")


def model_ids(cv):
    return sorted(cv.model_id(path.split("/", 1)[0]) for path in cv.FILES)


def committed():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def results_md():
    return RESULTS_MD.read_text(encoding="utf-8")


def summary_row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"]
            if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1, (bar, flavor, strategy)
    return rows[0]


def task_row(results, bar, flavor, task):
    rows = [r for r in results["per_task"] if (r["bar"], r["flavor"], r["task"]) == (bar, flavor, task)]
    assert len(rows) == 1 and rows[0]["strategy"] == "routed", (bar, flavor, task)
    return rows[0]


def join(words):
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def bar_range(bars):
    return f"bar {bars[0]}" if len(bars) == 1 else f"bars {bars[0]} to {bars[-1]}"


def reading_phrases(results):
    """The numbers of the RESULTS.md text and "Reading it" bullets, built from the file."""
    config = results["config"]
    assert config["flavors"] == ["cost_blind"]
    flavor, seeds, bars, b0 = "cost_blind", len(config["seeds"]), config["bars"], config["bars"][0]
    routed = {bar: summary_row(results, bar, flavor, "routed") for bar in bars}
    r0 = routed[b0]
    assert all(r["success"] == r0["success"] for r in routed.values())
    assert all(summary_row(results, bar, flavor, "best_on_calibration")["success"] == r0["success"]
               for bar in bars)
    picks = [task_row(results, bar, flavor, TASK)["routed_models"] for bar in bars]
    assert all(p == picks[0] for p in picks)
    order = sorted(picks[0].items(), key=lambda kv: (-kv[1], kv[0]))
    parts = [f"{n} of the {seeds} seeds to `{m}`" if i == 0 else f"{n} to `{m}`"
             for i, (m, n) in enumerate(order)]
    phrases = [f"`cost_blind` reaches a held-out success of {r0['success']:.3f} at every bar, the "
               f"same as `best_on_calibration`",
               f"It routes {join(parts)}, at every bar"]
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == (b0, flavor) and r["strategy"].startswith("model:")]
    assert all(m["success"] != r0["success"] for m in models)
    above = sorted((m for m in models if m["success"] > r0["success"]),
                   key=lambda m: (-m["success"], m["strategy"]))
    assert above, "no single model above the routed success"
    said = [f"always calling `{m['strategy'][6:]}` reaches {m['success']:.3f}" if i == 0 else
            f"always calling `{m['strategy'][6:]}` {m['success']:.3f}" for i, m in enumerate(above)]
    phrases.append(f"Against single models: {join(said)}; the other {len(models) - len(above)} of "
                   f"the {len(models)} single models reach less than the routed {r0['success']:.3f}")
    clear_run = []
    for bar in bars:
        if (routed[bar]["cleared_rate"], routed[bar]["bar_violation_rate"]) != (1.0, 0.0):
            break
        clear_run.append(bar)
    assert clear_run, "no lowest bar clears every seed"
    phrases.append(f"at {bar_range(clear_run)} a model clears on every one of the {seeds} seeds "
                   f"and no cleared seed falls below the bar on held-out")
    violated_bars = [bar for bar in bars if routed[bar]["bar_violation_rate"]]
    assert violated_bars, "no bar has a bar violation"
    for bar in violated_bars:
        r = routed[bar]
        cleared = round(r["cleared_rate"] * seeds)
        violated = round(r["bar_violation_rate"] * cleared)
        below = round(r["below_bar_rate"] * seeds)
        assert below >= violated
        phrases.append(f"{r['bar_violation_rate']:.3f} at bar {bar} is {violated} of the {cleared} "
                       f"seeds that cleared, against {below - violated} of the {seeds - cleared} "
                       f"seeds that did not clear")
    phrases.append(f"a nominal one-sided {(1 - config['confidence']) / 2:.3f}")
    oracle = summary_row(results, b0, flavor, "oracle")
    assert oracle["success"] - r0["success"] >= 0.05
    phrases.append(f"The per-item oracle reaches {oracle['success']:.3f}, against the routed "
                   f"{r0['success']:.3f}")
    lowest = min(m["strategy"] for m in models)
    cheapest = summary_row(results, b0, flavor, "cheapest")
    assert cheapest["success"] == summary_row(results, b0, flavor, lowest)["success"]
    phrases.append(f"the `cheapest` baseline is the model with the lowest ID, `{lowest[6:]}`")
    phrases.append(f"its {cheapest['success']:.3f} is that model's success")
    phrases.append(f"the committed file, {RESULTS.stat().st_size:,} bytes,")
    return phrases


# --- the committed file, RESULTS.md and the evidence README ---------------------------------

def test_committed_results_are_small_reduced_and_pinned(rs, cv):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    results = json.loads(text)
    assert text == json.dumps(rs.reduce(results), indent=2) + "\n"
    assert results["config"] == CONFIG
    models = model_ids(cv)
    assert len(models) == 67
    assert results["tasks"] == {TASK: {"items": ITEMS, "models": models}}
    keys = {(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]}
    assert len(results["summary"]) == len(keys) == 9 * 1 * (4 + len(models)) == 639
    task_keys = {(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]}
    assert len(results["per_task"]) == len(task_keys) == 9
    assert all(r["strategy"] == "routed" for r in results["per_task"])
    assert all(sum(r["routed_models"].values()) == 50 and set(r["routed_models"]) <= set(models)
               for r in results["per_task"])
    rows = results["summary"] + results["per_task"]
    assert all(r["flavor"] == "cost_blind" and r["cost_usd"] == 0 for r in rows)


def test_results_md_shows_the_table_of_the_committed_results(rs):
    table = rs.table(committed())
    assert "\n" + TABLE_COMMAND + "\n" + table + "\n```\n" in results_md()
    routed = table.split("\n\n")[0].split("\n")[2:]
    assert routed and all(line.split()[3:5] == ["0.0000", "-"] for line in routed)
    assert "cost_effective" not in table


def test_results_md_regenerate_block_sources_and_zero_cost_sentences(cv):
    text = results_md()
    assert REGENERATE in text
    for needle in ["https://github.com/LiveCodeBench/submissions", cv.REVISION, "MIT",
                   "Copyright (c) 2025 LiveCodeBench", "(README.md)", "(results.json)",
                   "DESIGN 12.17", "`graded_list[0]`", "`code_generation`", ZERO_COST, NOT_RUN,
                   SAME_PICK, COMPLEMENT, *CAVEATS]:
        assert needle in text, needle
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text


def test_results_md_reading_numbers_are_the_committed_results():
    results, text = committed(), results_md()
    for phrase in reading_phrases(results):
        assert phrase in text, phrase


def test_reading_phrases_follow_the_file():
    fake = json.loads(json.dumps(committed()))
    for r in fake["summary"]:
        if r["strategy"] == "model:" + fake["tasks"][TASK]["models"][-1]:
            r["success"] = 0.999
    said = [p for p in reading_phrases(fake) if p.startswith("Against single models: ")]
    assert len(said) == 1
    assert said[0].startswith(f"Against single models: always calling "
                              f"`{fake['tasks'][TASK]['models'][-1]}` reaches 0.999")
    summary_row(fake, 0.1, "cost_blind", "routed")["bar_violation_rate"] = 0.5
    with pytest.raises(AssertionError):
        reading_phrases(fake)


def test_evidence_readme_links_the_results():
    text = EVIDENCE_README.read_text(encoding="utf-8")
    assert "(RESULTS.md)" in text and "(results.json)" in text
    assert "`--flavor cost_blind`" in text
    assert "not committed yet" not in text
    assert "it is not the command for this matrix" not in text


# --- the README subsection (DESIGN 12.8, v1.65) ---------------------------------------------

README = ROOT / "README.md"
HEADINGS = ["RouterBench", "AutoBench", "AutoBench judges", "tau2-bench", "LiveCodeBench",
            "Delegation on AutoBench"]
LIMITS = ["The models date from 2023 to 2025 and the 713 problems from 2023-05-07 to 2024-10-05, "
          "so many problems predate a model's training data: the contamination LiveCodeBench "
          "dates its problems to expose", *CAVEATS[1:]]
ORACLE = ("Per-item oracle: on each problem, a model whose first sample solved it, or a model "
          "counted wrong when none did")


def readme_subsection():
    text = README.read_text(encoding="utf-8")
    heading = "\n## Evidence: held-out results on public data\n"
    assert text.count(heading) == 1
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.*)$", section, re.M) == HEADINGS
    return section.split("\n### LiveCodeBench\n", 1)[1].split("\n### ", 1)[0]


def rate(value):
    return "-" if value is None else f"{value:.3f}"


def readme_tables(results):
    """The two tables of the README `### LiveCodeBench` subsection (DESIGN 12.8, v1.65): no
    cost column, since every cost is 0, and no `cheapest` row, the lowest model ID."""
    config = results["config"]
    assert config["flavors"] == ["cost_blind"]
    b0 = config["bars"][0]
    lines = ["| Bar | Flavor | Held-out success | Cleared rate | Bar-violation rate |",
             "|---|---|---|---|---|"]
    for bar in config["bars"]:
        r = summary_row(results, bar, "cost_blind", "routed")
        lines.append(f"| {bar} | `cost_blind` | {r['success']:.3f} | {rate(r['cleared_rate'])} "
                     f"| {rate(r['bar_violation_rate'])} |")
    routed = summary_row(results, b0, "cost_blind", "routed")
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == (b0, "cost_blind") and r["strategy"].startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    above = sorted((m for m in models if m["success"] > routed["success"]),
                   key=lambda m: (-m["success"], m["strategy"]))
    assert above and above[0] is best
    lines += ["", "| Baseline | Held-out success |", "|---|---|"]
    rows = [(ORACLE, summary_row(results, b0, "cost_blind", "oracle"))]
    rows += [(f"Always `{m['strategy'][6:]}`" + (" (best single model)" if m is best else ""), m)
             for m in above]
    rows.append(("Best model on the calibration half",
                 summary_row(results, b0, "cost_blind", "best_on_calibration")))
    lines += [f"| {label} | {r['success']:.3f} |" for label, r in rows]
    return "\n".join(lines) + "\n"


def readme_counts(results):
    config, tasks = results["config"], results["tasks"]
    assert list(tasks) == [TASK]
    bars = config["bars"]
    return (f"{len(tasks[TASK]['models'])} models, one routing task, `{TASK}`, of "
            f"{tasks[TASK]['items']} problems, {len(config['seeds'])} seeds; the problems are split "
            f"in half per seed and routed at bars {bars[0]} to {bars[-1]}, `cost_blind` only")


def test_readme_livecodebench_tables_and_counts_are_the_committed_results():
    results, section = committed(), readme_subsection()
    assert "\n" + readme_tables(results) in section
    assert readme_counts(results) in section
    assert "| cheapest" not in section.lower() and "Cost (USD)" not in section


def test_readme_livecodebench_reading_numbers_are_the_committed_results():
    section = readme_subsection()
    phrases = [p for p in reading_phrases(committed()) if not p.startswith("the committed file,")]
    assert len(phrases) == len(reading_phrases(committed())) - 1
    for phrase in phrases + [SAME_PICK, COMPLEMENT]:
        assert phrase in section, phrase


def test_readme_livecodebench_links_source_licence_limits_and_commands(cv):
    section, md = readme_subsection(), results_md()
    revision = cv.REVISION
    for needle in ("[LiveCodeBench/submissions](https://github.com/LiveCodeBench/submissions)",
                   f"[`{revision[:7]}`](https://github.com/LiveCodeBench/submissions/tree/"
                   f"{revision})", "MIT", '"Copyright (c) 2025 LiveCodeBench"',
                   "(evidence/livecodebench/RESULTS.md)", "(evidence/livecodebench/results.json)",
                   "(evidence/livecodebench/README.md)", "`graded_list[0]`", NOT_RUN,
                   f"the {len(cv.FILES)} files the converter reads",
                   f"the {len(cv.FILES)} pinned files, the {len(cv.DROPPED)} dropped ones",
                   f"downloads the {len(cv.FILES)} pinned files, about "
                   f"{sum(size for size, _ in cv.FILES.values()) / 1e9:.2f} GB,"):
        assert needle in section, needle
    for phrase in LIMITS:
        assert phrase in section and phrase in md, phrase
    assert REGENERATE in section and REGENERATE in md
    assert section.count("`cost_effective`") == NOT_RUN.count("`cost_effective`")
    assert section.isascii() and "\u2013" not in section and "\u2014" not in section


def test_readme_livecodebench_tables_follow_the_file():
    fake = json.loads(json.dumps(committed()))
    summary_row(fake, 0.9, "cost_blind", "routed")["bar_violation_rate"] = None
    row = [line for line in readme_tables(fake).split("\n") if line.startswith("| 0.9 |")]
    assert len(row) == 1 and row[0].endswith(" | - |")
    for r in fake["summary"]:
        if r["strategy"] == "model:openai/o4-mini-high":
            r["success"] = 0.5
    assert "`openai/o4-mini-high`" not in readme_tables(fake)
    assert "| Always `deepseek/deepseek-r1-0528` (best single model) | 0.904 |" in readme_tables(fake)


# --- the pinned files, only when already cached ---------------------------------------------

@pytest.fixture(scope="module")
def real(cv):
    """Rows of the converter's default matrix and its cost_blind evaluate with cells."""
    folder = cv.default_cache_dir()
    if not all((folder / path).is_file() for path in cv.FILES):
        pytest.skip("the 67 pinned LiveCodeBench files are not in the default cache")
    extracts = []
    for path, (size, sha) in cv.FILES.items():
        cv.verify(folder / path, size, sha)
        extracts.append(cv.extract(cv.read_file(folder / path), path.split("/", 1)[0]))
    rows, report = cv.convert(extracts)
    result = evaluate(outcomes_from_rows(rows), bars=BARS, seeds=range(50), flavors=("cost_blind",))
    return rows, report, result


def without_cells(result):
    return {k: v for k, v in result.items() if k != "cells"}


def test_real_results_regenerate_byte_identical(rs, cv, real):
    _, report, result = real
    assert report["models"] == model_ids(cv) and report["items"] == ITEMS
    assert json.dumps(rs.reduce(without_cells(result)), indent=2) + "\n" == RESULTS.read_text(
        encoding="utf-8")


def test_real_split_sizes_and_success_span_are_in_results_md(real):
    rows, _, _ = real
    text = results_md()
    items = sorted({r["item"] for r in rows})
    sizes = [len(split_items(items, seed)[0]) for seed in range(50)]
    assert min(sizes) >= CONFIG["min_samples"]
    assert (f"Calibration halves hold {min(sizes)} to {max(sizes)} problems over the 50 seeds, "
            f"never under `min_samples` {CONFIG['min_samples']}") in text
    hits = {}
    for r in rows:
        hits.setdefault(r["model"], []).append(r["correct"])
    rates = [sum(v) / len(v) for v in hits.values()]
    low, high = min(rates), max(rates)
    assert BARS == [k / 10 for k in range(math.floor(low * 10) + 1, math.ceil(high * 10))]
    assert f"the models' rates run from {low:.3f} to {high:.3f}" in text


def test_real_routed_is_best_on_calibration_and_cost_effective_repeats_cost_blind(real):
    rows, _, result = real
    assert len(result["cells"]) == len(BARS) * 50
    for cell in result["cells"]:
        assert cell["models"]["routed"] == cell["models"]["best_on_calibration"], cell["seed"]
    effective = evaluate(outcomes_from_rows(rows), bars=BARS, seeds=range(50),
                         flavors=("cost_effective",))

    def strip(rows_):
        return [{k: v for k, v in r.items() if k != "flavor"} for r in rows_]
    assert strip(effective["summary"]) == strip(result["summary"])
    assert strip(effective["per_task"]) == strip(result["per_task"])


def test_real_cleared_seeds_sentence_is_in_results_md(real):
    rows, _, result = real
    text = results_md()
    hits = {}
    for r in rows:
        hits.setdefault(r["model"], {})[r["item"]] = r["correct"]
    said = 0
    for bar in BARS:
        cleared = [c for c in result["cells"] if c["bar"] == bar and c["cleared"]]
        if not cleared or all(c["success"]["routed"] >= bar for c in cleared):
            continue
        picked = sorted({c["models"]["routed"] for c in cleared})
        assert len(picked) == 1, picked
        model = picked[0]
        mine = hits[model]
        whole = sum(mine.values()) / len(mine)
        cal_rates, held_rates = [], []
        for c in cleared:
            cal, held = split_items(mine, c["seed"])
            cal_rates.append(sum(mine[i] for i in cal) / len(cal))
            held_rates.append(sum(mine[i] for i in held) / len(held))
            assert held_rates[-1] == c["success"]["routed"]
        assert min(cal_rates) > whole > max(held_rates)
        sentence = (f"On the {len(cleared)} seeds that cleared bar {bar} the router took `{model}`, "
                    f"whose rate on all {len(mine)} problems is {whole:.3f}: its calibration-half "
                    f"rate was {min(cal_rates):.3f} to {max(cal_rates):.3f} and its held-out rate "
                    f"{min(held_rates):.3f} to {max(held_rates):.3f}")
        assert sentence in text
        assert sentence in readme_subsection()  # v1.65 (DESIGN 12.8)
        said += 1
    assert said >= 1
