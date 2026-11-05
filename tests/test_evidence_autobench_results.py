"""v1.16 AutoBench results contract (DESIGN 12.10), written before the results were committed.

The committed ``evidence/autobench-2026/results.json`` is made and printed by the
RouterBench results script, ``evidence/routerbench/results.py``, reused unchanged. The
first tests need no download: they check the committed file and RESULTS.md against each
other. The last two read the pinned AutoBench files only when they are already in the
default cache and skip otherwise (CI never downloads them): one rebuilds results.json and
requires the committed bytes, the other rebuilds every sensitivity number in RESULTS.md.
v1.17 adds the README `### AutoBench` subsection (DESIGN 12.8), rebuilt from the committed
file, and the card quotes RESULTS.md uses for what the card graded, checked against the
pinned card when it is cached.
"""

import hashlib
import importlib.util
import json
import re
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows, split_items, wilson_lower_bound

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "autobench-2026"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
README = ROOT / "README.md"
CARD_SHA256 = "30f119c55031ca3c70f740ff3dfc395e580fe633bd513be94891a9c3acfdd168"
CARD_QUOTES = ("Seven routers were then graded by lookup: a router only names a model; we read "
               "that cell", "The published board", "28 passes")
TABLE_COMMAND = ("$ python evidence/routerbench/results.py --table "
                 "evidence/autobench-2026/results.json")
REGENERATE = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/autobench-2026/convert.py --out autobench-matrix.jsonl --task-by all\n"
    "model-routing evaluate --outcomes autobench-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50"
    " --json > autobench-evaluate.json\n"
    "python evidence/routerbench/results.py --evaluate autobench-evaluate.json"
    " --out evidence/autobench-2026/results.json\n"
    "python evidence/routerbench/results.py --table evidence/autobench-2026/results.json\n"
    "```\n")
CARD = ("no commercial pass beats always calling GPT-5.6 Luna on quality and cost together")
LUNA = "model:openai/gpt-5.6-luna"
OFFICIAL_WIDTH = 0.3011090610836323
MODELS = [
    "anthropic/claude-sonnet-5", "deepseek/deepseek-v4-flash-0731", "google/gemini-3.7-flash",
    "google/gemma-4-31b-it", "meta/muse-glimmer-30b", "meta/muse-spark-1.2",
    "minimax/minimax-m3", "moonshotai/kimi-k2.6", "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3.5-lightning", "openai/gpt-5.6-luna", "openai/gpt-5.6-sol",
    "openai/gpt-oss-120b", "qwen/qwen3.5-9b", "qwen/qwen3.8-max", "tencent/hy3",
    "xai/grok-4.3", "xai/grok-4.6", "zai/glm-5.2", "zai/glm-5.3"]
CONFIG = {"bars": [0.6, 0.7, 0.8, 0.9], "seeds": list(range(50)),
          "flavors": ["cost_effective", "cost_blind"], "calibration_fraction": 0.5,
          "min_samples": 30, "confidence": 0.95}


def load(name, path):
    if not path.is_file():
        raise ModuleNotFoundError(f"no script at {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def rs():
    return load("routerbench_results", ROOT / "evidence" / "routerbench" / "results.py")


@pytest.fixture()
def cv():
    return load("autobench_convert", FOLDER / "convert.py")


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


def luna_statement(results):
    """The sentence RESULTS.md must carry about the dataset card's headline (DESIGN 12.10)."""
    config = results["config"]
    luna = summary_row(results, config["bars"][0], config["flavors"][0], LUNA)
    beats = []
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            r = summary_row(results, bar, flavor, "routed")
            if (r["success"] >= luna["success"] and r["cost_usd"] <= luna["cost_usd"]
                    and (r["success"] > luna["success"] or r["cost_usd"] < luna["cost_usd"])):
                beats.append(f"bar {bar} `{flavor}`")
    head = (f"always calling `openai/gpt-5.6-luna` reaches held-out success "
            f"{luna['success']:.3f} at {luna['cost_usd']:.4f} USD")
    if not beats:
        return (f"On the same matrix no routed row beats it on both counts: {head}, and every "
                f"routed row in the table has lower held-out success or a higher cost.")
    return f"On the same matrix {head}, and these routed rows beat it on both counts: " \
        + ", ".join(beats) + "."


def sensitivity_line(row):
    return (f"- bar {row['bar']}, `{row['flavor']}`: routed success {row['success']:.3f} at "
            f"{row['cost_usd']:.4f} USD, cleared_rate {rate(row['cleared_rate'])}, "
            f"bar_violation_rate {rate(row['bar_violation_rate'])}")


def luna_line(summary, bar, flavor):
    rows = [r for r in summary if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, LUNA)]
    return (f"- `openai/gpt-5.6-luna` alone: held-out success {rows[0]['success']:.3f} at "
            f"{rows[0]['cost_usd']:.4f} USD")


def reading_phrases(results):
    """The numbers of the RESULTS.md "Reading it" bullets and the file size, from the file."""
    config, seeds = results["config"], len(results["config"]["seeds"])
    first = [r for r in results["summary"]
             if (r["bar"], r["flavor"]) == (config["bars"][0], config["flavors"][0])]
    best = min((r for r in first if r["strategy"].startswith("model:")),
               key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    boc = summary_row(results, config["bars"][0], config["flavors"][0], "best_on_calibration")
    ce = {bar: summary_row(results, bar, "cost_effective", "routed") for bar in config["bars"]}
    cb = [summary_row(results, bar, "cost_blind", "routed") for bar in config["bars"]]
    assert ce[0.6]["cleared_rate"] == 1.0 and ce[0.9]["cleared_rate"] == 0.0
    assert all((r["success"], r["cost_usd"]) == (cb[0]["success"], cb[0]["cost_usd"]) for r in cb)
    phrases = [
        f"At bar 0.6 every seed clears and it spends {ce[0.6]['cost_usd'] / best['cost_usd']:.3f} "
        f"of the best single model's cost for a held-out success of {ce[0.6]['success']:.3f} "
        f"against that model's {best['success']:.3f}",
        f"At 0.8 a model clears on {round(ce[0.8]['cleared_rate'] * seeds)} of the {seeds} seeds",
        f"the cost rises to {ce[0.8]['cost_usd'] / best['cost_usd']:.3f} of the best single model",
        f"(the best single model's held-out success is {best['success']:.3f}), so no seed clears",
        f"success {cb[0]['success']:.3f} at {cb[0]['cost_usd'] / best['cost_usd']:.3f} of the best "
        f"single model's cost at every bar, close to `best_on_calibration` "
        f"({boc['success']:.3f} at {boc['cost_usd'] / best['cost_usd']:.3f})",
        f"a nominal one-sided {(1 - config['confidence']) / 2:.3f}",
        f"the committed file, {RESULTS.stat().st_size:,} bytes,"]
    for bar in (0.7, 0.8):
        cleared = round(ce[bar]["cleared_rate"] * seeds)
        violated = round(ce[bar]["bar_violation_rate"] * cleared)
        phrases.append(f"{ce[bar]['bar_violation_rate']:.3f} at bar {bar} is {violated} of the "
                       f"{cleared} seeds that cleared")
    return phrases


# --- the committed file and RESULTS.md ------------------------------------------------------

def test_committed_results_are_small_reduced_and_pinned(rs):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    results = json.loads(text)
    assert text == json.dumps(rs.reduce(results), indent=2) + "\n"
    assert results["config"] == CONFIG
    assert results["tasks"] == {"all": {"items": 203, "models": MODELS}}
    keys = {(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]}
    assert len(results["summary"]) == len(keys) == 4 * 2 * (4 + len(MODELS))
    task_keys = {(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]}
    assert len(results["per_task"]) == len(task_keys) == 4 * 2
    assert all(r["strategy"] == "routed" and r["task"] == "all" for r in results["per_task"])
    assert all(sum(r["routed_models"].values()) == 50 and set(r["routed_models"]) <= set(MODELS)
               for r in results["per_task"])


def test_results_md_shows_the_table_of_the_committed_results(rs):
    block = "```text\n" + TABLE_COMMAND + "\n" + rs.table(committed()) + "\n```\n"
    assert block in results_md()


def test_results_md_regenerate_block_and_width_in_prose():
    text = results_md()
    assert REGENERATE in text
    assert "0.2007" in text and "0.20073937405575484" not in text
    for needle in ["https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10",
                   "43755180be7d8097068982d7a3f37fc04cd15379", "CC-BY-4.0", "(README.md)",
                   "(results.json)", "--task-by all", "not an absolute acceptance check"]:
        assert needle in text, needle


def test_results_md_puts_the_card_headline_next_to_the_router():
    results, text = committed(), results_md()
    assert CARD in text
    assert luna_statement(results) in text
    row = [r for r in results["per_task"] if (r["bar"], r["flavor"]) == (0.7, "cost_effective")]
    seeds = row[0]["routed_models"].get("openai/gpt-5.6-luna", 0)
    assert f"routes {seeds} of the 50 seeds to `openai/gpt-5.6-luna`" in text


def test_results_md_reading_numbers_are_the_committed_results():
    results, text = committed(), results_md()
    for phrase in reading_phrases(results):
        assert phrase in text, phrase
    # "the other seeds to weaker models ..., so it ends a little below that model on success
    # and a little above it on cost"
    luna = summary_row(results, 0.6, "cost_effective", LUNA)
    routed = summary_row(results, 0.7, "cost_effective", "routed")
    assert routed["success"] < luna["success"] and routed["cost_usd"] > luna["cost_usd"]
    row = [r for r in results["per_task"] if (r["bar"], r["flavor"]) == (0.7, "cost_effective")]
    others = set(row[0]["routed_models"]) - {"openai/gpt-5.6-luna"}
    assert others and all(summary_row(results, 0.6, "cost_effective", f"model:{m}")["success"]
                          < luna["success"] for m in others)
    assert "and the other seeds to weaker models that cleared the bar" in text


def test_luna_statement_names_a_row_that_beats_it():
    results = committed()
    fake = json.loads(json.dumps(results))
    luna = summary_row(fake, 0.6, "cost_effective", LUNA)
    routed = summary_row(fake, 0.8, "cost_blind", "routed")
    routed["success"], routed["cost_usd"] = luna["success"], luna["cost_usd"] / 2
    assert luna_statement(fake).endswith("beat it on both counts: bar 0.8 `cost_blind`.")
    routed["cost_usd"] = luna["cost_usd"]
    assert "no routed row beats it" in luna_statement(fake)


def test_results_md_says_what_the_card_graded_in_the_card_words():
    text = results_md()
    for quote in CARD_QUOTES:
        assert f'"{quote}"' in text, quote
    assert 'it describes `scoreboard.json` as "The published board", with "28 passes"' in text
    assert "commercial routers that the paper audited" not in text


# --- the README subsection (DESIGN 12.8, v1.17) ---------------------------------------------

def autobench_subsection():
    readme = README.read_text(encoding="utf-8")
    heading = "\n## Evidence: held-out results on public data\n"
    assert readme.count(heading) == 1
    section = readme.split(heading, 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.*)$", section, re.M) == ["RouterBench", "AutoBench"]
    return section.split("\n### AutoBench\n", 1)[1].split("\n### ", 1)[0]


def test_readme_evidence_intro_names_both_labels():
    readme = README.read_text(encoding="utf-8")
    section = readme.split("\n## Evidence: held-out results on public data\n", 1)[1]
    intro = section.split("\n### ", 1)[0]
    assert ("(right or wrong on RouterBench, a Delta-Hit from a judge committee's scores on "
            "AutoBench)") in intro


def readme_tables(results):
    """The two AutoBench tables of the README evidence section (DESIGN 12.8, v1.17)."""
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == first and r["strategy"].startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    cheapest = summary_row(results, *first, "cheapest")
    lines = ["| Bar | Flavor | Held-out success | Cost (USD) | Cost / best single model "
             "| Cost / cheapest model | Cleared rate | Bar-violation rate |",
             "|---|---|---|---|---|---|---|---|"]
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            r = summary_row(results, bar, flavor, "routed")
            lines.append(f"| {bar} | `{flavor}` | {r['success']:.3f} | {r['cost_usd']:.4f} "
                         f"| {r['cost_usd'] / best['cost_usd']:.3f} "
                         f"| {r['cost_usd'] / cheapest['cost_usd']:.1f} "
                         f"| {rate(r['cleared_rate'])} | {rate(r['bar_violation_rate'])} |")
    assert summary_row(results, *first, "oracle")["success"] == 1.0
    baselines = [
        ("Per-question oracle: on each question, the cheapest model with a Delta-Hit on it "
         "(some model has one on every question)", "oracle"),
        (f"Best single model (`{best['strategy'][len('model:'):]}`)", best["strategy"]),
        ("The model the dataset card's headline names (`openai/gpt-5.6-luna`)", LUNA),
        ("Best model on the calibration half", "best_on_calibration"),
        ("Cheapest model on the calibration half", "cheapest")]
    lines += ["", "| Baseline | Held-out success | Cost (USD) |", "|---|---|---|"]
    for label, strategy in baselines:
        r = summary_row(results, *first, strategy)
        lines.append(f"| {label} | {r['success']:.3f} | {r['cost_usd']:.4f} |")
    return "\n".join(lines) + "\n"


def test_readme_autobench_tables_are_the_committed_results():
    results, section = committed(), autobench_subsection()
    assert "\n" + readme_tables(results) in section
    config, task = results["config"], results["tasks"]["all"]
    assert list(results["tasks"]) == ["all"]
    counts = (f"{len(task['models'])} models, {task['items']} of the 252 questions in one "
              f"pooled task (`--task-by all`), {len(config['seeds'])} seeds")
    assert counts in section
    assert f"routed at bars {config['bars'][0]} to {config['bars'][-1]} in both flavors" in section
    assert CARD in section
    assert luna_statement(results) in section


def test_readme_tables_helper_prints_a_dash_for_no_rate():
    fake = json.loads(json.dumps(committed()))
    summary_row(fake, 0.6, "cost_blind", "routed")["bar_violation_rate"] = None
    row = [line for line in readme_tables(fake).split("\n") if "| 0.6 | `cost_blind` |" in line]
    assert len(row) == 1 and row[0].endswith(" | - |")


def test_readme_autobench_links_source_licence_limits_and_commands(cv):
    section = autobench_subsection()
    revision = cv.REVISION
    read = [name for name in cv.FILES if name != "SHA256SUMS"]
    words = {3: "three", 4: "four", 5: "five", 6: "six"}
    assert f"the {words[len(read)]} files the converter reads" in section
    for needle in ("https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10",
                   f"[`{revision[:7]}`](https://huggingface.co/datasets/AutoBench/"
                   f"router-benchmark-2026-10/tree/{revision})",
                   "[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)",
                   "Attribution: Autobench, Autobench Router Benchmark 2026",
                   "(evidence/autobench-2026/RESULTS.md)", "(evidence/autobench-2026/results.json)",
                   "(evidence/autobench-2026/README.md)",
                   "at the converter's default width, the dataset's `delta_signal` of 0.2007",
                   "frozen on 2026-08-29", "not an absolute acceptance check",
                   "12 to 33 questions", "the 49 questions with an unscored pool cell (107 cells)",
                   "the 388 rows for 13 models outside the 20-model pool"):
        assert needle in section, needle
    assert "0.20073937405575484" not in section
    regenerate = results_md().split("## Regenerate\n\n```bash\n", 1)[1].split("```", 1)[0]
    assert regenerate.count("\n") == 5
    assert "```bash\n" + regenerate + "```" in section
    assert REGENERATE.rstrip("\n") == "```bash\n" + regenerate + "```"


# --- the pinned files, only when already cached ---------------------------------------------

def pinned(cv):
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("pinned AutoBench files are not in the default cache")
    for name, (size, sha) in cv.FILES.items():
        cv.verify(folder / name, size, sha)
    params = json.loads((folder / "frozen_params.json").read_text(encoding="utf-8"))
    pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
    return (cv.read_csv(folder / "matrix.csv"), cv.read_csv(folder / "questions.csv"), pool,
            params)


def test_real_results_regenerate_byte_identical(rs, cv):
    matrix, questions, pool, params = pinned(cv)
    rows, report = cv.convert(matrix, questions, pool, params["delta_signal"], params["top_k"],
                              task_by="all")
    assert report["models"] == MODELS and report["kept"] == {"all": 203}
    result = evaluate(outcomes_from_rows(rows), bars=CONFIG["bars"], seeds=range(50))
    result.pop("cells")
    assert json.dumps(rs.reduce(result), indent=2) + "\n" == RESULTS.read_text(encoding="utf-8")


def test_real_sensitivity_numbers_are_in_results_md(cv):
    matrix, questions, pool, params = pinned(cv)
    text = results_md()
    rows, _ = cv.convert(matrix, questions, pool, OFFICIAL_WIDTH, params["top_k"], task_by="all")
    official = evaluate(outcomes_from_rows(rows), bars=[0.8], seeds=range(50))["summary"]
    rows, report = cv.convert(matrix, questions, pool, params["delta_signal"], params["top_k"])
    assert len(report["kept"]) == 10
    domain = evaluate(outcomes_from_rows(rows), bars=[0.6, 0.8], seeds=range(50),
                      min_samples=5)["summary"]
    needles = [luna_line(official, 0.8, "cost_effective"),
               luna_line(domain, 0.6, "cost_effective")]
    needles += [sensitivity_line(r) for r in official + domain if r["strategy"] == "routed"]
    assert len(needles) == 2 + 2 + 4
    for needle in needles:
        assert needle + "\n" in text, needle
    # RESULTS.md: "Neither run beats `openai/gpt-5.6-luna` alone on both counts."
    for summary, bars in ((official, [0.8]), (domain, [0.6, 0.8])):
        fake = {"config": {"bars": bars, "flavors": CONFIG["flavors"]}, "summary": summary}
        assert "no routed row beats it" in luna_statement(fake)
    assert "Neither run beats `openai/gpt-5.6-luna` alone on both counts." in text


def test_real_split_sizes_are_in_results_md(cv):
    matrix, questions, pool, params = pinned(cv)
    text = results_md()
    rows, _ = cv.convert(matrix, questions, pool, params["delta_signal"], params["top_k"],
                         task_by="all")
    items = {r["item"] for r in rows}
    pooled = [len(split_items(items, seed)[0]) for seed in CONFIG["seeds"]]
    assert (f"{len(items)} questions, with {min(pooled)} to {max(pooled)} in the calibration "
            f"half over the 50 seeds") in text
    assert (f"At 0.9 no model's lower bound on a calibration half of {min(pooled)} to "
            f"{max(pooled)} questions reaches the bar") in text
    rows, _ = cv.convert(matrix, questions, pool, params["delta_signal"], params["top_k"])
    by_task = {}
    for r in rows:
        by_task.setdefault(r["task"], set()).add(r["item"])
    halves = [len(split_items(v, seed)[0]) for v in by_task.values() for seed in CONFIG["seeds"]]
    assert max(halves) < CONFIG["min_samples"]
    assert (f"a calibration half holds from {min(halves)} to {max(halves)} questions over the "
            f"{len(halves)} (domain, seed) splits") in text
    need = next(n for n in range(1, 100) if wilson_lower_bound(n, n, 0.95) >= 0.8)
    assert (f"a perfect score needs at least {need} calibration questions for a Wilson lower "
            f"bound of 0.8 or more, and {sum(h < need for h in halves)} of the {len(halves)} "
            f"halves hold fewer") in text


def test_card_quotes_are_in_the_pinned_card_when_cached(cv):
    path = cv.default_cache_dir() / "README.md"
    if not path.is_file() or hashlib.sha256(path.read_bytes()).hexdigest() != CARD_SHA256:
        pytest.skip("the dataset card at the pinned revision is not in the default cache")
    card = path.read_text(encoding="utf-8").replace("**", "")
    for quote in CARD_QUOTES + (CARD,):
        assert quote in card, quote
    board = [line for line in card.splitlines() if line.startswith("| `scoreboard.json` |")]
    assert len(board) == 1 and "The published board" in board[0] and "28 passes" in board[0]
