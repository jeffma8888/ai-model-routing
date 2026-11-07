"""v1.27 judge results on AutoBench (DESIGN 12.12), written before the results were committed.

The committed ``evidence/autobench-judges/results.json`` is the 12.11 judge matrix at its
default options, evaluated at bars 0.6 to 0.9 with 50 seeds and reduced by the RouterBench
results script, ``evidence/routerbench/results.py``, reused unchanged. The first tests need no
download: they check the committed file and RESULTS.md against each other, and every prose
number of RESULTS.md is built here from the committed file. The last two read the pinned
AutoBench files only when they are already in the default cache and skip otherwise (CI never
downloads them): one rebuilds results.json and requires the committed bytes, the other rebuilds
every sensitivity line of RESULTS.md. v1.28 adds the README `### AutoBench judges` subsection
(DESIGN 12.8): its tables, counts, Reading it bullets and limits are built here from the
committed file, the 12.11 defaults and the evidence README counts. v1.29 compares the intro,
the header and the Caveats of RESULTS.md as whole paragraphs, and, on the cached files, checks
seed by seed that the routed judge is the one 5.3 picks from the calibration-half Wilson lower
bounds, which is what the "highest lower bound" bullets say.
"""

import hashlib
import importlib.util
import json
import re
from collections import Counter
from math import fsum
from pathlib import Path

import pytest

from model_routing import Registry, evaluate, outcomes_from_rows, wilson_lower_bound

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
README = ROOT / "README.md"
EVIDENCE_README = ROOT / "evidence" / "autobench-2026" / "README.md"
HEADINGS = ["RouterBench", "AutoBench", "AutoBench judges", "tau2-bench", "Delegation on AutoBench"]
RESULTS_LINK = "([AutoBench results](../autobench-2026/RESULTS.md))"


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


def only_task(results):
    assert list(results["tasks"]) == ["all"], list(results["tasks"])
    return "all"


def intro_paragraph(results, jm):
    """The whole RESULTS.md intro paragraph (DESIGN 12.12, v1.29)."""
    return ("What `model-routing evaluate` measures when the router chooses a judge model on "
            "public data. The outcome matrix is the one `evidence/autobench-2026/judges.py` "
            "builds, at its default options, from the per-judge grades the AutoBench Router "
            "Benchmark 2026 publishes (DESIGN 12.11, and the [judge section of the evidence "
            f"README]({SECTION_LINK})). {intro(results, jm.DEFAULT_TOLERANCE)} the answers are "
            "split in half by a seeded hash; the router calibrates on one half at a bar and is "
            "scored on the other half, next to the oracle, the best judge on the calibration "
            "half, the cheapest judge and every single judge (DESIGN 12.3). The answers are "
            f"pooled into one task, `{only_task(results)}`. The file behind every number here is "
            "[results.json](results.json): the summary rows and the routed per-task rows, "
            f"including how many of the {seeds(results)} seeds routed to each judge. It is made "
            "by the RouterBench results script, `evidence/routerbench/results.py`, which does not "
            "depend on the dataset.")


def header_paragraph(results):
    """The whole paragraph above the RESULTS.md table (DESIGN 12.12, v1.29)."""
    return ("Routed rows: `success` is the share of held-out answers on which the judge agrees "
            "with the committee, `cost_usd` is the list-price estimate of judging them (both "
            f"averaged over the {seeds(results)} seeds), {header(results)}, `cleared_rate` is the "
            "share of seeds where some judge cleared the bar on the calibration half, and "
            "`bar_violation_rate` is the share of cleared seeds whose held-out success fell below "
            "the bar. Baseline rows do not depend on the bar or the flavor.")


def caveats(results, jm):
    """The whole RESULTS.md Caveats list (DESIGN 12.12, v1.29)."""
    k = len(results["tasks"][only_task(results)]["models"])
    assert k == jm.DEFAULT_SIZE and jm.DEFAULT_ANSWER_TOKENS == "visible"
    cv = jm.convert
    return "\n".join("- " + c for c in [
        "The label is a committee label, not a human gold label: a judge succeeds when it agrees "
        "with the other judges on the same answer. A judge that always grades as the committee "
        "does scores 1.0 whether or not the committee is right, and a judge that is right where "
        "the committee is wrong scores lower",
        "The cost is a list-price estimate at the pool's list prices, never a billed cost: a "
        "judge call is assumed to read the question, the visible answer and a "
        f"{jm.DEFAULT_RUBRIC_TOKENS}-token rubric, and to write a {jm.DEFAULT_GRADE_TOKENS}-token "
        "grade (DESIGN 12.11)",
        f"The {k} candidates are the pool judges whose set keeps the most answers, not the best "
        "or the cheapest judges; a judge outside them is not compared here",
        "Answers to the same question are separate items, so a seed's split can put answers to "
        "one question in both halves",
        "Data: CC-BY-4.0, Autobench, Autobench Router Benchmark 2026, "
        f"https://huggingface.co/datasets/{cv.DATASET} at revision {cv.REVISION}. Pinned files, "
        "sha256 values, the citation the card asks for and what the converter drops are in the "
        "[evidence README](../autobench-2026/README.md)"])


def between(text, start, end):
    assert text.count(start) == 1, start
    rest = text.split(start, 1)[1]
    assert end in rest, end
    return rest.split(end, 1)[0]


def prose(text):
    """The intro, the header and the Caveats of a RESULTS.md text, each whole."""
    return {"intro": between(text, "# AutoBench judge results\n\n", "\n\n## Results\n"),
            "header": between(text, "\n## Results\n\n", "\n\n```text\n"),
            "caveats": between(text, "\n## Caveats\n\n", "\n\n## ")}


def prose_problems(text, results, jm):
    want = {"intro": intro_paragraph(results, jm), "header": header_paragraph(results),
            "caveats": caveats(results, jm)}
    got = prose(text)
    return [name for name in want if got[name] != want[name]]


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
    rest = 1 - o["success"]
    if rest > 0:
        assert f"{rest:.3f}" != "0.000", rest
        takes = ("the cheapest candidate that agrees with the committee, or, where none agrees "
                 f"({rest:.3f} of the held-out answers), the cheapest candidate on that answer, "
                 "counted wrong")
    else:
        takes = ("the cheapest candidate that agrees with the committee, and some candidate "
                 "agrees on every held-out answer")
    return (f"The oracle, {o['success']:.3f} at {o['cost_usd']:.4f} USD, takes on each held-out "
            f"answer {takes}: a hindsight bound, next to {best(results)[1]['success']:.3f} for "
            "the best single judge")


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


def test_results_md_intro_header_and_caveats_are_whole_paragraphs(jm):
    assert prose_problems(results_md(), committed(), jm) == []


def test_whole_paragraph_check_catches_an_added_number(jm):
    results, text = committed(), results_md()
    for name, paragraph in prose(text).items():
        assert text.count(paragraph) == 1, name
        mutant = text.replace(paragraph, paragraph + " (about 0.999 of them)", 1)
        assert prose_problems(mutant, results, jm) == [name]
    intro_ = prose(text)["intro"]
    mutant = text.replace(intro_, intro_ + " (about 0.999 of them)", 1)
    assert intro(results, jm.DEFAULT_TOLERANCE) in mutant, "the old substring check passes it"


def test_results_md_reading_it_is_the_committed_results():
    text = results_md()
    for bullet in reading_it(committed()):
        assert "- " + bullet + "\n" in text, bullet


def test_results_md_sensitivity_names_both_options():
    results, text = committed(), results_md()
    sensitivity = between(text, "\n## Sensitivity\n\n", "\n## Caveats\n")
    assert sensitivity.count(f"At bar 0.8 with {seeds(results)} seeds:\n") == 2
    assert sensitivity.startswith("Tolerance. With `--tolerance 1.0` a grade within one point")
    assert "\nReasoning tokens. With `--answer-tokens output` the judge is charged" in sensitivity


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


def test_oracle_bullet_names_the_fallback_only_when_some_answer_has_no_agreeing_judge():
    assert "counted wrong" in oracle(committed())
    fake = committed()
    for r in fake["summary"]:
        if r["strategy"] == "oracle":
            r["success"] = 1.0
    text = oracle(fake)
    assert "some candidate agrees on every held-out answer" in text
    assert "counted wrong" not in text


def test_cost_blind_bullet_says_close_when_not_level():
    fake = committed()
    for r in fake["summary"]:
        if r["strategy"] == "best_on_calibration":
            r["cost_usd"] *= 2
    assert "close to `best_on_calibration`" in cost_blind(fake)
    assert "level with" not in cost_blind(fake)


# --- the README subsection (DESIGN 12.8, v1.28) ---------------------------------------------

def readme():
    return README.read_text(encoding="utf-8")


def judges_subsection():
    heading = "\n## Evidence: held-out results on public data\n"
    text = readme()
    assert text.count(heading) == 1
    section = text.split(heading, 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.*)$", section, re.M) == HEADINGS
    return section.split("\n### AutoBench judges\n", 1)[1].split("\n### ", 1)[0]


def oracle_label(results):
    if row(results, *first(results), "oracle")["success"] < 1:
        return ("Per-answer oracle: on each answer, the cheapest judge that agrees with the "
                "committee, or the cheapest judge, counted wrong, when none does")
    return ("Per-answer oracle: on each answer, the cheapest judge that agrees with the "
            "committee (some judge agrees on every answer)")


def readme_tables(results):
    """The two tables of the README judge subsection (DESIGN 12.8, v1.28)."""
    bar0, flavor0 = first(results)
    name, top = best(results)
    low = row(results, bar0, flavor0, "cheapest")
    lines = ["| Bar | Flavor | Held-out success | Cost (USD) | Cost / best single judge "
             "| Cost / cheapest judge | Cleared rate | Bar-violation rate |",
             "|---|---|---|---|---|---|---|---|"]
    for bar in results["config"]["bars"]:
        for flavor in results["config"]["flavors"]:
            r = row(results, bar, flavor, "routed")
            lines.append(f"| {bar} | `{flavor}` | {r['success']:.3f} | {r['cost_usd']:.4f} "
                         f"| {r['cost_usd'] / top['cost_usd']:.3f} "
                         f"| {r['cost_usd'] / low['cost_usd']:.1f} "
                         f"| {rate(r['cleared_rate'])} | {rate(r['bar_violation_rate'])} |")
    baselines = [(oracle_label(results), "oracle"),
                 (f"Best single judge (`{name}`)", f"model:{name}"),
                 ("Best judge on the calibration half", "best_on_calibration"),
                 ("Cheapest judge on the calibration half", "cheapest")]
    lines += ["", "| Baseline | Held-out success | Cost (USD) |", "|---|---|---|"]
    for label, strategy in baselines:
        r = row(results, bar0, flavor0, strategy)
        lines.append(f"| {label} | {r['success']:.3f} | {r['cost_usd']:.4f} |")
    return "\n".join(lines) + "\n"


def readme_price(results):
    """The RESULTS.md price bullet with its link pointed at the README `#autobench`."""
    text = price(results)
    if LUNA in text:
        assert text.count(RESULTS_LINK) == 1
        text = text.replace(RESULTS_LINK, "([AutoBench](#autobench))")
    return text


def readme_reading_it(results):
    """Four of the RESULTS.md Reading it bullets (DESIGN 12.8, v1.28)."""
    return [all_clear(results), violations(results), oracle(results), readme_price(results)]


def counts_sentence(results, tolerance):
    task, config = results["tasks"]["all"], results["config"]
    return (f"What was run: {task['items']:,} graded answers in one pooled task, "
            f"{len(task['models'])} candidate judges, {seeds(results)} seeds; the answers are "
            f"split in half per seed and routed at bars {config['bars'][0]} to "
            f"{config['bars'][-1]} in both flavors. A success is a judge's grade within "
            f"{tolerance} of the mean of the other judges' grades on that answer, leaving out "
            "the judge itself and the model that wrote the answer")


def evidence_counts():
    text = EVIDENCE_README.read_text(encoding="utf-8")
    section = text.split("\n## Judge evidence: one item per graded answer\n", 1)[1]
    by_candidate = re.findall(r"^- Answers by a candidate: ([\d,]+)\.", section, re.M)
    missing = re.findall(r"^- Answers some candidate did not grade \(not among that answer's "
                         r"judges, or a null grade\): ([\d,]+),", section, re.M)
    kept = re.findall(r"^Kept: ([\d,]+) of the ([\d,]+) scored answers", section, re.M)
    assert len(by_candidate) == len(missing) == len(kept) == 1
    return by_candidate[0], missing[0], kept[0][0], kept[0][1]


def limits(results, jm):
    by_candidate, missing, kept, scored = evidence_counts()
    assert kept == f"{results['tasks']['all']['items']:,}", kept
    k = len(results["tasks"]["all"]["models"])
    return [
        "- The label is agreement with the other judges, which are models, not a human gold "
        "label: a judge that always grades as the committee does scores 1.0 "
        "whether or not the committee is right",
        "- Each cost is an estimate at the pool's list prices, never a billed cost: a judge call "
        "is assumed to read the question, the visible answer and a "
        f"{jm.DEFAULT_RUBRIC_TOKENS}-token rubric and to write a {jm.DEFAULT_GRADE_TOKENS}-token "
        "grade",
        f"- The {k} candidates are the pool judges whose set keeps the most answers, chosen for "
        f"that and not for quality or price. {kept} of the {scored} scored answers are kept: the "
        f"converter drops the {by_candidate} answered by a candidate, since no model grades its "
        f"own answer, and the {missing} that some candidate did not grade, so every candidate "
        "grades every item",
        "- Answers to the same question are separate items, so a seed's split can put answers "
        "to one question in both halves"]


def test_readme_judges_tables_are_the_committed_results():
    assert "\n" + readme_tables(committed()) + "\n" in judges_subsection()


def test_readme_judges_counts_and_reading_it_are_the_committed_results(jm):
    results, section = committed(), judges_subsection()
    assert counts_sentence(results, jm.DEFAULT_TOLERANCE) in section
    bullets = readme_reading_it(results)
    assert "\nReading it:\n\n" + "".join(f"- {b}\n" for b in bullets) + "\n" in section
    assert all("../" not in b for b in bullets)
    text = results_md()
    for b in bullets[:3]:
        assert "- " + b + "\n" in text, b


def test_readme_judges_limits_links_and_commands(jm):
    results, section = committed(), judges_subsection()
    assert "\nLimits:\n\n" + "\n".join(limits(results, jm)) + "\n\n" in section
    revision = jm.convert.REVISION
    for needle in ("[AutoBench/router-benchmark-2026-10]"
                   "(https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10)",
                   f"[`{revision[:7]}`](https://huggingface.co/datasets/AutoBench/"
                   f"router-benchmark-2026-10/tree/{revision})",
                   "[CC-BY-4.0](https://creativecommons.org/licenses/by/4.0/)",
                   "Attribution: Autobench, Autobench Router Benchmark 2026",
                   "[RESULTS.md](evidence/autobench-judges/RESULTS.md)",
                   "[results.json](evidence/autobench-judges/results.json)",
                   "(evidence/autobench-2026/README.md#judge-evidence-one-item-per-graded-answer)",
                   "the share of held-out answers on which the routed judge agrees with the "
                   "committee", "list-price estimate",
                   "The two ratios divide that cost by the cost of the best single judge and of "
                   "the cheapest judge on the calibration half in the baseline table",
                   "and a `-` means that no seed cleared."):
        assert needle in section, needle
    regenerate = results_md().split("## Regenerate\n\n```bash\n", 1)[1].split("```", 1)[0]
    assert "```bash\n" + regenerate + "```" == REGENERATE.rstrip("\n")
    assert "\n" + REGENERATE in section


def test_readme_judge_pointers_link_the_subsection():
    text = readme()
    judge = text.split("\n### Judge and eval calls, the first-class case\n", 1)[1]
    judge = judge.split("\n## ", 1)[0]
    assert "no public judge benchmark with a row for the current generation of models" in judge
    assert "publishes each judge model's grade of each answer it graded" in judge
    assert "[AutoBench judges](#autobench-judges)" in judge
    bullets = [line for line in text.splitlines()
               if line.startswith("- None of these are judge benchmarks")]
    assert len(bullets) == 1
    assert "[AutoBench judges](#autobench-judges)" in bullets[0]
    assert "agreement with other model judges, not with experts" in bullets[0]


def test_readme_judges_helpers_follow_the_numbers():
    fake = committed()
    for r in fake["summary"]:
        if r["strategy"] == "oracle":
            r["success"] = 1.0
        if (r["bar"], r["flavor"], r["strategy"]) == (0.6, "cost_blind", "routed"):
            r["bar_violation_rate"] = None
    tables = readme_tables(fake)
    assert "(some judge agrees on every answer) | 1.000 |" in tables
    assert "counted wrong" not in tables
    assert [line for line in tables.split("\n") if "| 0.6 | `cost_blind` |" in line][0] \
        .endswith(" | - |")
    assert "counted wrong, when none does |" in readme_tables(committed())
    for r in fake["summary"]:
        if r["strategy"] == f"model:{LUNA}":
            r["cost_usd"] = 0.0
    assert "#autobench" not in readme_price(fake)
    assert "([AutoBench](#autobench))" in readme_price(committed())


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


def calibration_half(items, seed, fraction):
    """The 12.2 calibration items, the hash rule re-derived here and not imported."""
    return sorted(i for i in set(items) if int.from_bytes(
        hashlib.sha256(f"{seed}:{i}".encode("utf-8")).digest()[:8], "big") < fraction * 2 ** 64)


def test_real_routed_judge_has_the_highest_lower_bound(jm, tmp_path):
    matrix, pool, registry = pinned(jm, tmp_path)
    rows, _ = jm.judge_matrix(matrix, pool)
    outcomes = outcomes_from_rows(rows, registry)
    result = evaluate(outcomes, bars=CONFIG["bars"], seeds=range(50))
    config = result["config"]
    assert config == CONFIG
    grid = {}
    for o in outcomes:
        assert o.task == "all"
        grid.setdefault(o.model, {})[o.item] = o
    assert sorted(grid) == CANDIDATES
    items = sorted(grid[CANDIDATES[0]])
    counts, not_cheapest = Counter(), Counter()
    for cell in result["cells"]:
        where = (cell["bar"], cell["flavor"], cell["seed"])
        half = calibration_half(items, cell["seed"], config["calibration_fraction"])
        assert len(half) == cell["calibration_items"] >= config["min_samples"], where
        lb, mean, cost = {}, {}, {}
        for m in CANDIDATES:
            wins = sum(grid[m][i].correct for i in half)
            lb[m] = wilson_lower_bound(wins, len(half), config["confidence"])
            mean[m] = fsum(grid[m][i].cost_usd for i in half) / len(half)
            cost[m] = 0.0 if cell["flavor"] == "cost_blind" else mean[m]
        passing = [m for m in CANDIDATES if lb[m] >= cell["bar"]]
        if passing:
            want = min(passing, key=lambda m: (cost[m], -lb[m], m))
        else:
            want = min(CANDIDATES, key=lambda m: (-lb[m], cost[m], m))
        assert cell["cleared"] == bool(passing), where
        assert cell["models"]["routed"] == want, where
        claim = ("cost_blind" if cell["flavor"] == "cost_blind"
                 else "fallback" if not passing else None)
        if claim:
            # The bullets' words; this follows from the two sorts above, so the check that
            # carries weight is routed == want, cell by cell.
            assert lb[want] == max(lb.values()), where
            not_cheapest[claim] += want != min(CANDIDATES, key=lambda m: (mean[m], m))
        counts[(cell["bar"], cell["flavor"], want)] += 1
    # Each claim must be tested on cells where the cheapest judge is not the one it names.
    assert not_cheapest["fallback"] and not_cheapest["cost_blind"], not_cheapest
    for bar in CONFIG["bars"]:
        for flavor in CONFIG["flavors"]:
            got = {m: n for (b, f, m), n in counts.items() if (b, f) == (bar, flavor)}
            assert got == routed_models(committed(), bar, flavor), (bar, flavor)


def sensitivity_line(r):
    return (f"- bar {r['bar']}, `{r['flavor']}`: routed success {r['success']:.3f} at "
            f"{r['cost_usd']:.4f} USD, cleared_rate {rate(r['cleared_rate'])}, "
            f"bar_violation_rate {rate(r['bar_violation_rate'])}")


def test_real_sensitivity_numbers_are_in_results_md(jm, tmp_path):
    matrix, pool, registry = pinned(jm, tmp_path)
    text, name = results_md(), best(committed())[0]
    base, _ = jm.judge_matrix(matrix, pool)
    keys = [(b["task"], b["item"], b["model"]) for b in base]
    needles = ["so more of the judges' grades count as successes. At bar 0.8 with 50 seeds:",
               "Every grade keeps its label, and in the three lines below held-out success, "
               "cleared and bar-violation rates are those of the default run and only the costs "
               "rise. At bar 0.8 with 50 seeds:"]
    for options in ({"tolerance": 1.0}, {"answer_tokens": "output"}):
        rows, _ = jm.judge_matrix(matrix, pool, **options)
        assert [(r["task"], r["item"], r["model"]) for r in rows] == keys, options
        if options == {"tolerance": 1.0}:
            assert all(r["correct"] for r, b in zip(rows, base) if b["correct"])
            assert sum(r["correct"] for r in rows) > sum(b["correct"] for b in base)
        else:
            assert [r["correct"] for r in rows] == [b["correct"] for b in base]
            assert all(r["input_tokens"] >= b["input_tokens"] for r, b in zip(rows, base))
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
            default = row(committed(), 0.8, "cost_effective", f"model:{name}")
            assert alone[0]["success"] == default["success"]
            assert alone[0]["cost_usd"] > default["cost_usd"]
            assert all(r["cost_usd"] > row(committed(), 0.8, r["flavor"], "routed")["cost_usd"]
                       for r in summary if r["strategy"] == "routed")
    assert len(needles) == 2 + 2 * 3
    for needle in needles:
        assert needle + "\n" in text, needle
