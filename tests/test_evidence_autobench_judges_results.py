"""v1.27 judge results on AutoBench (DESIGN 12.12), written before the results were committed.

The committed ``evidence/autobench-judges/results.json`` is the 12.11 judge matrix at its
default options, evaluated at bars 0.6 to 0.9 with 50 seeds and reduced by the RouterBench
results script, ``evidence/routerbench/results.py``, reused unchanged. The first tests need no
download: they check the committed file and RESULTS.md against each other, and every prose
number of RESULTS.md is built here from the committed file. The last two read the pinned
AutoBench files only when they are already in the default cache and skip otherwise (CI never
downloads them): one rebuilds results.json and requires the committed bytes, the other rebuilds
every sensitivity line of RESULTS.md.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from model_routing import Registry, evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "autobench-judges"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
TABLE_COMMAND = ("$ python evidence/routerbench/results.py --table "
                 "evidence/autobench-judges/results.json")
REGENERATE = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/autobench-2026/judges.py --out autobench-judges.jsonl"
    " --registry autobench-models.json\n"
    "model-routing evaluate --outcomes autobench-judges.jsonl --registry autobench-models.json"
    " --bar 0.6 0.7 0.8 0.9 --seeds 50 --json > autobench-judges-evaluate.json\n"
    "python evidence/routerbench/results.py --evaluate autobench-judges-evaluate.json"
    " --out evidence/autobench-judges/results.json\n"
    "python evidence/routerbench/results.py --table evidence/autobench-judges/results.json\n"
    "```\n")
SENSITIVITY = (
    "```bash\n"
    "python evidence/autobench-2026/judges.py --out autobench-judges-tolerance-1.jsonl"
    " --tolerance 1.0\n"
    "model-routing evaluate --outcomes autobench-judges-tolerance-1.jsonl"
    " --registry autobench-models.json --bar 0.8 --seeds 50\n"
    "python evidence/autobench-2026/judges.py --out autobench-judges-output.jsonl"
    " --answer-tokens output\n"
    "model-routing evaluate --outcomes autobench-judges-output.jsonl"
    " --registry autobench-models.json --bar 0.8 --seeds 50\n"
    "```\n")
CANDIDATES = ["deepseek/deepseek-v4-flash-0731", "google/gemma-4-31b-it", "meta/muse-glimmer-30b",
              "openai/gpt-5.6-luna", "tencent/hy3"]
CONFIG = {"bars": [0.6, 0.7, 0.8, 0.9], "seeds": list(range(50)),
          "flavors": ["cost_effective", "cost_blind"], "calibration_fraction": 0.5,
          "min_samples": 30, "confidence": 0.95}
LUNA = "openai/gpt-5.6-luna"
SECTION_LINK = "../autobench-2026/README.md#judge-evidence-one-item-per-graded-answer"


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


@pytest.fixture()
def jm():
    return load("autobench_judges", ROOT / "evidence" / "autobench-2026" / "judges.py")


def committed():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def results_md():
    return RESULTS_MD.read_text(encoding="utf-8")


def rate(value):
    return "-" if value is None else f"{value:.3f}"


def row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"]
            if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1, (bar, flavor, strategy)
    return rows[0]


def routed_models(results, bar, flavor):
    rows = [r for r in results["per_task"] if (r["bar"], r["flavor"]) == (bar, flavor)]
    assert len(rows) == 1, (bar, flavor)
    return rows[0]["routed_models"]


def first(results):
    return results["config"]["bars"][0], results["config"]["flavors"][0]


def models(results):
    bar, flavor = first(results)
    return [r for r in results["summary"]
            if (r["bar"], r["flavor"]) == (bar, flavor) and r["strategy"].startswith("model:")]


def best(results):
    r = min(models(results), key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    return r["strategy"][len("model:"):], r


def cheapest(results):
    r = min(models(results), key=lambda r: (r["cost_usd"], r["strategy"]))
    return r["strategy"][len("model:"):], r


def seeds(results):
    return len(results["config"]["seeds"])


def ratio(results, cost):
    return f"{cost / best(results)[1]['cost_usd']:.3f}"


def bars_text(bars):
    if len(bars) == 1:
        return f"bar {bars[0]}"
    return "bars " + ", ".join(str(b) for b in bars[:-1]) + f" and {bars[-1]}"


def routes(counts):
    parts = [f"{n} to `{m}`" for m, n in sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))]
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def intro(results, tolerance):
    task = results["tasks"]["all"]
    return (f"An item is one graded answer, {task['items']:,} of them, and a model is one of "
            f"the {len(task['models'])} candidate judges; a judge's grade is a success when it "
            f"is within {tolerance} of the mean of the other judges' grades on that answer. For "
            f"each of {seeds(results)} seeds")


def header(results):
    return ("`vs_best_model` is that cost divided by the cost of the best single judge "
            f"(`{best(results)[0]}`)")


def all_clear(results):
    n = seeds(results)
    bars = [b for b in results["config"]["bars"]
            if row(results, b, "cost_effective", "routed")["cleared_rate"] == 1.0
            and len(routed_models(results, b, "cost_effective")) == 1]
    assert bars, "no bar at which cost_effective clears on every seed with one judge"
    judges = {next(iter(routed_models(results, b, "cost_effective"))) for b in bars}
    assert judges == {cheapest(results)[0]}, judges
    rows = [row(results, b, "cost_effective", "routed") for b in bars]
    assert len({(r["success"], r["cost_usd"]) for r in rows}) == 1
    name, top = best(results)
    return (f"At {bars_text(bars)} every seed clears and `cost_effective` routes all {n} seeds "
            f"to `{cheapest(results)[0]}`, the cheapest candidate: held-out success "
            f"{rows[0]['success']:.3f} at {ratio(results, rows[0]['cost_usd'])} of the cost of "
            f"the best single judge, `{name}` ({top['success']:.3f} at {top['cost_usd']:.4f} USD)")


def partly_and_never(results):
    n = seeds(results)
    bars = results["config"]["bars"]
    part = [b for b in bars
            if 0 < row(results, b, "cost_effective", "routed")["cleared_rate"] < 1]
    never = [b for b in bars if row(results, b, "cost_effective", "routed")["cleared_rate"] == 0]
    assert part and never, (part, never)
    r = row(results, part[0], "cost_effective", "routed")
    cleared = round(r["cleared_rate"] * n)
    return (f"At bar {part[0]} a judge clears on {cleared} of the {n} seeds, and `cost_effective` "
            f"routes {routes(routed_models(results, part[0], 'cost_effective'))}: held-out "
            f"success {r['success']:.3f} at {ratio(results, r['cost_usd'])} of the best single "
            f"judge's cost. At bar {never[0]} no seed clears (the best single judge's held-out "
            f"success is {best(results)[1]['success']:.3f}), so the router falls back on every "
            "seed to the judge with the highest lower bound")


def cost_blind(results):
    bars = results["config"]["bars"]
    rows = [row(results, b, "cost_blind", "routed") for b in bars]
    assert len({(r["success"], r["cost_usd"]) for r in rows}) == 1
    counts = [routed_models(results, b, "cost_blind") for b in bars]
    assert all(c == counts[0] for c in counts)
    boc = [row(results, b, "cost_blind", "best_on_calibration") for b in bars]
    level = all((r["success"], r["cost_usd"]) == (o["success"], o["cost_usd"])
                for r, o in zip(rows, boc))
    o = boc[0]
    tail = ("level with `best_on_calibration` at full precision" if level else
            f"close to `best_on_calibration` ({o['success']:.3f} at "
            f"{ratio(results, o['cost_usd'])})")
    return (f"`cost_blind` routes to the judge with the highest lower bound: held-out success "
            f"{rows[0]['success']:.3f} at {ratio(results, rows[0]['cost_usd'])} of the best "
            f"single judge's cost at every bar, routing {routes(counts[0])}, {tail}")


def violations(results):
    n = seeds(results)
    parts = []
    for bar in results["config"]["bars"]:
        for flavor in results["config"]["flavors"]:
            r = row(results, bar, flavor, "routed")
            if r["bar_violation_rate"]:
                cleared = round(r["cleared_rate"] * n)
                broke = round(r["bar_violation_rate"] * cleared)
                assert broke / cleared == r["bar_violation_rate"], (bar, flavor)
                parts.append(f"`{flavor}` at bar {bar}, {r['bar_violation_rate']:.3f}, is {broke} "
                             f"of the {cleared} seeds that cleared")
    assert parts
    confidence = results["config"]["confidence"]
    return ("There is one task, so each rate counts seeds: " + "; ".join(parts)
            + f". Read them next to a nominal one-sided {(1 - confidence) / 2:.3f} for a "
            f"{confidence:.0%} Wilson bound on one judge, as a resampling estimate for this "
            "matrix and never as a guarantee (DESIGN 12.3)")


def oracle(results):
    o = row(results, *first(results), "oracle")
    return (f"The oracle, {o['success']:.3f} at {o['cost_usd']:.4f} USD, takes on each held-out "
            "answer the cheapest candidate that agrees with the committee: a hindsight bound, "
            f"next to {best(results)[1]['success']:.3f} for the best single judge")


def price(results):
    rows = models(results)
    dear = sorted(rows, key=lambda r: (-r["cost_usd"], r["strategy"]))[:2]
    least = sorted(rows, key=lambda r: (r["success"], r["strategy"]))[:2]
    named = [f"`{r['strategy'][len('model:'):]}` ({r['success']:.3f} at {r['cost_usd']:.4f} USD)"
             for r in dear]
    if {r["strategy"] for r in dear} == {r["strategy"] for r in least}:
        text = f"The two costliest candidates agree with the committee least: {named[0]} and " \
            f"{named[1]}, so a higher price did not buy more agreement"
    else:
        text = f"The two costliest candidates are {named[0]} and {named[1]}"
    if f"model:{LUNA}" in {r["strategy"] for r in dear}:
        text += (f". `{LUNA}` is the answer model of the dataset card's headline, which no "
                 "commercial router beat on quality and cost together "
                 "([AutoBench results](../autobench-2026/RESULTS.md))")
    return text


def reading_it(results):
    return [all_clear(results), partly_and_never(results), cost_blind(results),
            violations(results), oracle(results), price(results)]


# --- the committed file and RESULTS.md ------------------------------------------------------

def test_committed_results_are_small_reduced_and_pinned(rs):
    assert RESULTS.stat().st_size < 300_000
    text = RESULTS.read_text(encoding="utf-8")
    results = json.loads(text)
    assert text == json.dumps(rs.reduce(results), indent=2) + "\n"
    assert results["config"] == CONFIG
    assert results["tasks"] == {"all": {"items": 756, "models": CANDIDATES}}
    keys = {(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]}
    assert len(results["summary"]) == len(keys) == 4 * 2 * (4 + len(CANDIDATES))
    task_keys = {(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]}
    assert len(results["per_task"]) == len(task_keys) == 4 * 2
    assert all(r["strategy"] == "routed" and r["task"] == "all" for r in results["per_task"])
    assert all(sum(r["routed_models"].values()) == 50
               and set(r["routed_models"]) <= set(CANDIDATES) for r in results["per_task"])


def test_results_md_shows_the_table_of_the_committed_results(rs):
    block = "```text\n" + TABLE_COMMAND + "\n" + rs.table(committed()) + "\n```\n"
    assert block in results_md()


def test_results_md_regenerate_blocks_and_file_size():
    text = results_md()
    assert REGENERATE in text and SENSITIVITY in text
    assert f"the committed file, {RESULTS.stat().st_size:,} bytes," in text


def test_results_md_intro_and_header_are_the_committed_results(jm):
    results, text = committed(), results_md()
    assert intro(results, jm.DEFAULT_TOLERANCE) in text
    assert header(results) in text


def test_results_md_reading_it_is_the_committed_results():
    text = results_md()
    for bullet in reading_it(committed()):
        assert "- " + bullet + "\n" in text, bullet


def test_results_md_caveats_and_links(jm):
    text = results_md()
    for needle in ["https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10",
                   jm.convert.REVISION, "CC-BY-4.0", "(results.json)", f"({SECTION_LINK})",
                   "not a human gold label", "list-price estimate", "never a billed cost",
                   f"{jm.DEFAULT_RUBRIC_TOKENS}-token rubric",
                   f"{jm.DEFAULT_GRADE_TOKENS}-token grade", "`--tolerance 1.0`",
                   "`--answer-tokens output`", "in both halves"]:
        assert needle in text, needle


def test_results_md_other_numbers_are_pinned():
    results, text = committed(), results_md()
    n, k = seeds(results), len(results["tasks"]["all"]["models"])
    assert text.count(f"At bar 0.8 with {n} seeds:\n") == 2
    for needle in [f"how many of the {n} seeds routed to each judge",
                   f"(both averaged over the {n} seeds)", f"- The {k} candidates are the pool judges",
                   "Router Benchmark 2026 publishes (DESIGN 12.11, and the [judge section",
                   "`evidence/autobench-2026/judges.py` builds", "every single judge (DESIGN 12.3).",
                   "scores 1.0 whether or not", "-token grade (DESIGN 12.11)\n",
                   "Autobench Router Benchmark 2026, https://", "Pinned files, sha256 values,",
                   "[evidence README](../autobench-2026/README.md)\n"]:
        assert needle in text, needle


def test_price_bullet_follows_the_numbers():
    fake = committed()
    for r in fake["summary"]:
        if r["strategy"] == f"model:{LUNA}":
            r["success"] = 0.99
    assert price(fake).startswith("The two costliest candidates are ")
    for r in fake["summary"]:
        if r["strategy"] == f"model:{LUNA}":
            r["cost_usd"] = 0.0
    assert LUNA not in price(fake)


def test_cost_blind_bullet_says_close_when_not_level():
    fake = committed()
    for r in fake["summary"]:
        if r["strategy"] == "best_on_calibration":
            r["cost_usd"] *= 2
    assert "close to `best_on_calibration`" in cost_blind(fake)
    assert "level with" not in cost_blind(fake)


# --- the pinned files, only when already cached ---------------------------------------------

def pinned(jm, tmp_path):
    cv = jm.convert
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("pinned AutoBench files are not in the default cache")
    for name, (size, sha) in cv.FILES.items():
        cv.verify(folder / name, size, sha)
    pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
    path = tmp_path / "autobench-models.json"
    path.write_text(json.dumps(cv.pool_registry(pool), indent=2) + "\n", encoding="utf-8")
    return cv.read_csv(folder / "matrix.csv"), pool, Registry.load(path)


def test_real_results_regenerate_byte_identical(rs, jm, tmp_path):
    matrix, pool, registry = pinned(jm, tmp_path)
    rows, report = jm.judge_matrix(matrix, pool)
    assert report["kept"] == {"all": 756}
    result = evaluate(outcomes_from_rows(rows, registry), bars=CONFIG["bars"], seeds=range(50))
    result.pop("cells")
    assert json.dumps(rs.reduce(result), indent=2) + "\n" == RESULTS.read_text(encoding="utf-8")


def sensitivity_line(r):
    return (f"- bar {r['bar']}, `{r['flavor']}`: routed success {r['success']:.3f} at "
            f"{r['cost_usd']:.4f} USD, cleared_rate {rate(r['cleared_rate'])}, "
            f"bar_violation_rate {rate(r['bar_violation_rate'])}")


def test_real_sensitivity_numbers_are_in_results_md(jm, tmp_path):
    matrix, pool, registry = pinned(jm, tmp_path)
    text, name = results_md(), best(committed())[0]
    needles = []
    for options in ({"tolerance": 1.0}, {"answer_tokens": "output"}):
        rows, _ = jm.judge_matrix(matrix, pool, **options)
        outcomes = outcomes_from_rows(rows, registry)
        summary = evaluate(outcomes, bars=[0.8], seeds=range(50))["summary"]
        alone = [r for r in summary if (r["flavor"], r["strategy"]) == ("cost_effective",
                                                                       f"model:{name}")]
        needles.append(f"- `{name}` alone: held-out success {alone[0]['success']:.3f} at "
                       f"{alone[0]['cost_usd']:.4f} USD")
        needles += [sensitivity_line(r) for r in summary if r["strategy"] == "routed"]
        if options == {"answer_tokens": "output"}:
            same = [(r["success"], r["cleared_rate"], r["bar_violation_rate"])
                    for r in summary if r["strategy"] == "routed"]
            assert same == [(row(committed(), 0.8, f, "routed")["success"],
                             row(committed(), 0.8, f, "routed")["cleared_rate"],
                             row(committed(), 0.8, f, "routed")["bar_violation_rate"])
                            for f in CONFIG["flavors"]]
    assert len(needles) == 2 * 3
    for needle in needles:
        assert needle + "\n" in text, needle
