"""DESIGN 5.2 v1.675 (row JUDGE2c, the third part of row JUDGE2): the self-consistency minimum in the docs.

No code changes. README `## Running it in production` ends with one paragraph on a task's
`min_self_consistency` (4.2 and 5.2 v1.668), right after the one on consensus labels (v1.663): the
two reasons it gives whatever a route's bound, `inconsistent` and `consistency_unknown`, a results
row's `rerun` key that gives `calibrate` the counts (4.3 v1.667), the inline parent's two codes that
`delegate` names (13.4 rule 6 and 13.7 v1.669), its one pointer to DESIGN.md and a link to the
Harvey lesson on judges. Each claim is checked here on the command line and the library beside the
words that state it. The pin paragraph's clause on rules 5g and 5h is tests/test_pin_docs.py's, the
bytes are tests/test_readme_trim.py's v1.675 block, and every README transcript keeps its bytes
(tests/test_pin_docs.py).
"""

import json
from pathlib import Path

from test_latency_docs import ROWS, TASK, WORK, run
from test_readme_production import PRODUCTION, PRODUCTION_CAP, link_problems, paragraphs, size

from model_routing import Stats
from model_routing.delegation import PARENT_CONSISTENCY_UNKNOWN, PARENT_INCONSISTENT
from model_routing.router import CONSISTENCY_UNKNOWN, INCONSISTENT

ROOT = Path(__file__).resolve().parents[1]
N, LEAST = 30, 0.9
CHEAP, MID, PRICEY = (row["id"] for row in ROWS)
CONSENSUS_LEAD = "A team with no human labels can make them from its reference judges' recorded grades: "
LESSON = "Choose a cheap judge by agreement with strong judges, then batch its criteria"
ANCHOR = "research/production-lessons.md#choose-a-cheap-judge-by-agreement-with-strong-judges-then-batch-its-criteria"
PARAGRAPH = (
    "A judge can also be held to grading alike on reruns. A `tasks.json` row's `\"min_self_consistency\"` rules out "
    "a route, whatever its bound, whose share of items graded alike on every rerun, of those graded on two or more, "
    "is under it, reason `inconsistent`, or that has fewer such items than `min_samples`, reason "
    "`consistency_unknown`. A results row's `rerun`, 0 for an item's trial and above 0 for a rerun, with its "
    "`item`, gives `calibrate` those counts, and an inline parent is held to the minimum too, `delegate` naming "
    "`parent_inconsistent` or `parent_consistency_unknown` (`DESIGN.md` 4.2, 4.3, 5.2, 13.4 and 13.7). Harvey scored "
    f"its candidate graders by self-consistency over three reruns ([production lessons]({ANCHOR})).")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def says(words):
    assert PARAGRAPH.count(words) == 1, words


def results():
    """Every trial correct, so each route's Wilson bound clears the 0.8 bar on its 30 trials. Each item of the cheap
    route is graded on three reruns, 15 of its 30 items two ways; the mid one's 30 alike; the pricey one's rerun
    rows cover 29 items, one fewer than `min_samples`."""
    rows = []
    for model_id, rerun_items in ((CHEAP, N), (MID, N), (PRICEY, N - 1)):
        for i in range(N):
            rows.append({"task": "t", "model": model_id, "item": f"i{i}", "rerun": 0, "correct": True})
            if i < rerun_items:
                for rerun in (1, 2):
                    split = model_id == CHEAP and i < 15 and rerun == 2
                    rows.append({"task": "t", "model": model_id, "item": f"i{i}", "rerun": rerun,
                                 "correct": not split})
    return "".join(json.dumps(row) + "\n" for row in rows)


def make(d, **task):
    d.mkdir(exist_ok=True)
    (d / "models.json").write_text(json.dumps({"models": ROWS}), encoding="utf-8")
    (d / "tasks.json").write_text(json.dumps({"tasks": [{**TASK, **task}]}), encoding="utf-8")
    (d / "results.jsonl").write_text(results(), encoding="utf-8")
    code, _, err = run(["calibrate", "--results", str(d / "results.jsonl"), "--stats", str(d / "stats.json")])
    assert (code, err) == (0, "")
    return ["--registry", str(d / "models.json"), "--tasks", str(d / "tasks.json"), "--stats", str(d / "stats.json")]


def reasons(data):
    return {c["model_id"]: c["reason"] for c in data["candidates"]}


# --- README -------------------------------------------------------------------------------------

def test_the_paragraph_follows_the_one_on_consensus_labels_inside_the_cap():
    text = read("README.md")
    found = paragraphs(text, PRODUCTION)
    # placed by its neighbour (v1.655, row T30); tests/test_readme_trim.py names the section's last paragraph
    assert text.count(PARAGRAPH) == 1 and found.count(PARAGRAPH) == 1
    at = found.index(PARAGRAPH)
    assert at > 0 and found[at - 1].startswith(CONSENSUS_LEAD)
    assert size(text, PRODUCTION) <= PRODUCTION_CAP == 30_000
    assert "\u2014" not in PARAGRAPH and "\u2013" not in PARAGRAPH and "```" not in PARAGRAPH
    assert link_problems(text) == []


def test_the_link_is_the_lesson_that_holds_harvey_s_floor():
    says("Harvey scored its candidate graders by self-consistency over three reruns")
    assert PARAGRAPH.count("](") == 1 and f"]({ANCHOR})" in PARAGRAPH
    note = read("research/production-lessons.md")
    lesson = note.split(f"\n### {LESSON}\n", 1)[1].split("\n### ", 1)[0]
    [mechanism] = [line for line in lesson.splitlines() if line.startswith("- Mechanism: ")]
    assert '"a 98.9% per-criterion self-consistency floor across three reruns"' in mechanism
    # the paragraph quotes nothing, so the note alone holds the quote
    assert '"' not in PARAGRAPH.replace('`"min_self_consistency"`', "")


# --- its claims, each beside its words ------------------------------------------------------------

def test_calibrate_counts_a_results_row_s_reruns(tmp_path):
    says("A results row's `rerun`, 0 for an item's trial and above 0 for a rerun, with its `item`, gives "
         "`calibrate` those counts")
    make(tmp_path)
    saved = Stats.load(tmp_path / "stats.json")
    # a rerun above 0 adds no trial, only its grade (4.3 v1.667)
    assert {m: saved.get("t", m) for m in (CHEAP, MID, PRICEY)} == {CHEAP: (N, N), MID: (N, N), PRICEY: (N, N)}
    assert {m: saved.self_consistency("t", m) for m in (CHEAP, MID)} == {CHEAP: 0.5, MID: 1.0}


def test_the_minimum_rules_out_an_inconsistent_route_and_an_unknown_one_whatever_its_bound(tmp_path):
    says("A `tasks.json` row's `\"min_self_consistency\"` rules out a route, whatever its bound, whose share of items "
         "graded alike on every rerun, of those graded on two or more, is under it, reason `inconsistent`, or that "
         "has fewer such items than `min_samples`, reason `consistency_unknown`.")
    code, out, err = run(["select", "t", "--json", *make(tmp_path, min_self_consistency=LEAST)])
    assert (code, err) == (0, "")
    data = json.loads(out)
    assert reasons(data) == {CHEAP: INCONSISTENT, MID: "passes", PRICEY: CONSISTENCY_UNKNOWN}
    assert (data["primary"], data["fallbacks"]) == (MID, [])
    # without the minimum the same stats admit all three, the cheap one first: the bound does not save it
    plain = json.loads(run(["select", "t", "--json", *make(tmp_path / "none")])[1])
    assert set(reasons(plain).values()) == {"passes"} and plain["primary"] == CHEAP


def test_delegate_names_the_parent_s_two_codes(tmp_path):
    says("an inline parent is held to the minimum too, `delegate` naming `parent_inconsistent` or "
         "`parent_consistency_unknown`")
    base = make(tmp_path, min_self_consistency=LEAST)
    found = {}
    for parent in (CHEAP, PRICEY, MID):
        work = [*WORK[:1], parent, *WORK[2:]]
        code, out, err = run(["delegate", "t", *work, "--json", *base])
        assert (code, err) == (0, ""), parent
        data = json.loads(out)
        found[parent] = (data["reason"], data["inline_allowed"])
    assert found[CHEAP] == (PARENT_INCONSISTENT, False) and found[PRICEY] == (PARENT_CONSISTENCY_UNKNOWN, False)
    assert found[MID][1] is True and not found[MID][0].startswith("parent_")


# --- DESIGN ---------------------------------------------------------------------------------------

def test_the_pointer_names_each_subsection_that_states_a_claim():
    says("(`DESIGN.md` 4.2, 4.3, 5.2, 13.4 and 13.7).")
    design = read("DESIGN.md")
    starts = {"4.2": "### 4.2 ", "4.3": "### 4.3 ", "5.2": "### 5.2 ", "13.4": "### 13.4 ", "13.7": "### 13.7 "}
    ends = {"4.2": "### 4.3 ", "4.3": "### 4.4 ", "5.2": "### 5.3 ", "13.4": "### 13.5 ", "13.7": "### 13.8 "}
    part = {k: design[design.index("\n" + v):design.index("\n" + ends[k], design.index("\n" + v))]
            for k, v in starts.items()}
    assert "`min_self_consistency: float | None = None`" in part["4.2"]
    assert "`rerun`" in part["4.3"] and "`consistent_items`" in part["4.3"]
    assert "5g, `inconsistent`" in part["5.2"] and "5h, `consistency_unknown`" in part["5.2"]
    assert "`parent_inconsistent` (5g)" in part["13.4"] and "`parent_consistency_unknown` (5h)" in part["13.4"]
    assert "prints `parent_inconsistent` or `parent_consistency_unknown` on the `reason:` line" in part["13.7"]
