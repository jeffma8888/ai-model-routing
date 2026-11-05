"""v1.16 AutoBench results contract (DESIGN 12.10), written before the results were committed.

The committed ``evidence/autobench-2026/results.json`` is made and printed by the
RouterBench results script, ``evidence/routerbench/results.py``, reused unchanged. The
first tests need no download: they check the committed file and RESULTS.md against each
other. The last two read the pinned AutoBench files only when they are already in the
default cache and skip otherwise (CI never downloads them): one rebuilds results.json and
requires the committed bytes, the other rebuilds every sensitivity number in RESULTS.md.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "autobench-2026"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
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


def test_luna_statement_names_a_row_that_beats_it():
    results = committed()
    fake = json.loads(json.dumps(results))
    luna = summary_row(fake, 0.6, "cost_effective", LUNA)
    routed = summary_row(fake, 0.8, "cost_blind", "routed")
    routed["success"], routed["cost_usd"] = luna["success"], luna["cost_usd"] / 2
    assert luna_statement(fake).endswith("beat it on both counts: bar 0.8 `cost_blind`.")
    routed["cost_usd"] = luna["cost_usd"]
    assert "no routed row beats it" in luna_statement(fake)


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
