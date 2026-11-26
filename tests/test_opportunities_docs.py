"""DESIGN 5.2 v1.654 (row OPP1c): the savings report in the docs.

No code changes. README `## Running it in production` ends with one sentence on `report --opportunities`
(8.3 and 10 v1.645 and v1.646), right after the paragraph on pinned calls (v1.641): that a log shows where a
cheaper route, such as a procedure or a model of your own, would save most; the columns it gives each task;
that a target ranks the tasks by what each would save a day; that `--stats` adds the route `select` admits
and its list cost and, with `--audits` and a target, the labelled items a route at the target needs; and that
each saving is hypothetical, no return on what training, hosting or building that route costs. Each claim is
checked on the library and on the 8.3 or 10 line that states it. The sentence goes into the room row PROD1g
made under v1.629's 30,000-byte cap, so no paragraph is trimmed, and the v1.652 and v1.653 tests hold the
section less its paragraph to the bytes they set (tests/test_readme_trim.py). 8.3 v1.645's and v1.646's
Not-in-this-version sub-bullets name v1.654 in place of row OPP1c. Every README transcript keeps its v1.640
bytes, and no evidence or research script opens a file this slice edits.
"""

import contextlib
import hashlib
import io
import re
from pathlib import Path

import pytest
from test_opportunities_route import AUDITS, LOG, build
from test_pin_docs import BLOCK, PIN_PARAGRAPH, TRANSCRIPTS_SHA256
from test_readme_production import PRODUCTION, PRODUCTION_CAP, link_problems, paragraphs, size

from model_routing import opportunities
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
SAVINGS_LEAD = "A log also shows where a cheaper route, such as a procedure or a model of your own, would save most: "
SAVINGS_PARAGRAPH = (
    SAVINGS_LEAD + "`model-routing report --log PATH --opportunities` gives each task its calls per day, share of "
    "spend and cost per call; `--target-cost-per-call USD` ranks the tasks by what each would save a day if a route "
    "at that cost served all its calls and cleared the bar; `--stats FILE` adds the route `select` admits under "
    "`cost_effective` and its list cost and, with `--audits PATH` and a target, the labelled items that a route at "
    "the target, at the task's "
    "audited success rate, needs to be admitted; each saving is hypothetical, no return on what training, hosting or "
    "building that route costs (`DESIGN.md` 8.3 and 10).")
SECTION_BYTES = 24_690   # at v1.654: v1.653's 23,976 plus the paragraph's 712 bytes and its blank line
CLAUSE = "- v1.654 README savings report (row OPP1c, 8.3 and 10 v1.645 and v1.646): "
NOT_IN_V1_645 = ("  - Not in this version: the cost per call of the route `select` admits for the task and the labelled "
                 "items `plan` says a route at the target needs to be admitted, which v1.646 adds (row OPP1b), and the "
                 "README sentence, which v1.654 adds (5.2). `model_routing.__all__` gains `opportunities`, after "
                 "`drift_check`.")
NOT_IN_V1_646 = "  - Not in this version: the README sentence, which v1.654 adds (5.2). `model_routing.__all__` is unchanged."
# each claim of the sentence, as it says it, and the 8.3 or 10 line's phrase that states it
CLAIMS = [
    ("gives each task its calls per day, share of spend and cost per call", "### 8.3 ",
     "`calls_per_day`, `calls / days`; `cost_usd`; `spend_share`"),
    ("ranks the tasks by what each would save a day", "### 8.3 ",
     "Sort: with a target, by descending `saving_per_day_usd`"),
    ("if a route at that cost served all its calls and cleared the bar", "### 8.3 ",
     "if a route at the target cost per call served every one of them and cleared the task's bar"),
    ("adds the route `select` admits under `cost_effective`", "### 8.3 ",
     "for each row, `router.select(task, \"cost_effective\")` with no other argument"),  # review iter-509 should-fix 1
    ("adds the route `select` admits", "### 8.3 ",
     "`route` is the decision's `primary` when its `below_bar` is false, the route that clears the task's bar"),
    ("`cost_effective` and its list cost", "### 8.3 ",
     "`route_list_cost_usd` is that primary candidate's `list_cost` (5.1)"),  # review iter-509 nit 5
    ("the labelled items that a route at the target, at the task's audited success rate, needs to be admitted",
     "### 8.3 ", "`items_to_admit` is how many labelled items a route at the target needs on the task before "
     "`select` admits it, if its success rate there were the task's audited rate in the log"),
    ("each saving is hypothetical, no return on what training, hosting or building that route costs", "### 8.3 ",
     "nothing is set against what training, hosting or building that route costs, so it is no return on that cost"),
    ("`model-routing report --log PATH --opportunities`", "## 10. ",
     "  - v1.645 `report --log PATH --opportunities [--target-cost-per-call USD] [--audits PATH] [--json]`"),
    ("`--stats FILE` adds", "## 10. ", "  - v1.646 `report --log PATH --opportunities --stats PATH [--registry PATH]"),
]
ENDS = {"### 8.3 ": "\n## 9. ", "## 10. ": "\n## 11. "}


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def subsection(design, heading):
    start = design.index("\n" + heading)
    return design[start:design.index(ENDS[heading], start)]


# --- README --------------------------------------------------------------------------------------

def test_the_sentence_ends_the_section_after_the_pin_paragraph_inside_the_cap():
    text = read("README.md")
    found = paragraphs(text, PRODUCTION)
    assert found[-1] == SAVINGS_PARAGRAPH and text.count(SAVINGS_LEAD) == 1
    assert found[-2] == PIN_PARAGRAPH
    assert size(text, PRODUCTION) == SECTION_BYTES <= PRODUCTION_CAP == 30_000
    assert len(SAVINGS_PARAGRAPH.encode("utf-8")) == 712
    # one sentence: no full stop inside it, and it ends at its DESIGN pointer
    assert ". " not in SAVINGS_PARAGRAPH and SAVINGS_PARAGRAPH.endswith(" (`DESIGN.md` 8.3 and 10).")
    assert "\u2014" not in SAVINGS_PARAGRAPH and "\u2013" not in SAVINGS_PARAGRAPH
    assert link_problems(text) == []


def test_each_option_it_names_is_an_option_of_report():
    out = io.StringIO()
    with contextlib.redirect_stdout(out), pytest.raises(SystemExit) as stop:
        main(["report", "--help"])
    assert stop.value.code == 0
    named = re.findall(r"`(--[a-z-]+)", SAVINGS_PARAGRAPH) + re.findall(r" (--[a-z-]+)", SAVINGS_PARAGRAPH)
    assert sorted(set(named)) == ["--audits", "--log", "--opportunities", "--stats", "--target-cost-per-call"]
    for option in named:
        assert option in out.getvalue(), option


# --- each claim on the library -------------------------------------------------------------------

def test_the_columns_and_the_sort_by_daily_saving():
    plain = opportunities(LOG)
    assert all({"calls_per_day", "spend_share", "cost_per_call_usd"} <= set(row) for row in plain)
    # without a target the rows go by spend a day; a target ranks them by what each would save a day
    assert [r["task"] for r in plain] == ["classify", "summarize", "draft", "extract"]
    target = opportunities(LOG, target_cost_per_call=0.001)
    assert [(r["task"], r["saving_per_day_usd"]) for r in target] == [
        ("classify", 0.036), ("summarize", 0.005), ("extract", 0.001), ("draft", 0.0)]
    # by hand: calls a day times what each call costs over the target, 4 * (0.01 - 0.001) for classify
    by = {r["task"]: r for r in target}
    assert by["classify"]["calls_per_day"] == 4.0 and by["classify"]["cost_per_call_usd"] == 0.01
    assert by["draft"]["cost_per_call_usd"] == 0.001   # at the target, so it saves nothing


def test_stats_add_the_admitted_route_and_audits_with_a_target_the_items():
    router = build()
    rows = {r["task"]: r for r in opportunities(LOG, router=router)}
    # under `cost_effective` (review iter-509 should-fix 1): with 60 more right on extract the dearer model
    # has the higher bound, so `cost_blind` would pick it, while the row keeps the cheapest passing route
    blind = build()
    blind.stats.add("extract", "fiction/mid", 60, 60)
    assert blind.select("extract", "cost_blind").primary == "fiction/mid"
    assert {r["task"]: r["route"] for r in opportunities(LOG, router=blind)}["extract"] == "fiction/cheap"
    assert rows["classify"]["route"] == router.select("classify", "cost_effective").primary == "fiction/mid"
    assert rows["classify"]["route_list_cost_usd"] == 0.0063 and "items_to_admit" not in rows["classify"]
    # the items need a router, a target and audits: without audits the key is there and None
    no_audits = {r["task"]: r for r in opportunities(LOG, router=router, target_cost_per_call=0.001)}
    assert {t: r["items_to_admit"] for t, r in no_audits.items()} == dict.fromkeys(no_audits, None)
    audited = {r["task"]: r for r in opportunities(LOG, router=router, audits=AUDITS, target_cost_per_call=0.001)}
    # rate 1.0: 35 items clear 0.9 and 16 clear 0.8 (4.3), raised to min_samples 50 and 30 while extract's 16 is over
    # its 10 and stands; draft's 2/3 never clears 0.8 (review iter-509 nit 1)
    assert {t: r["items_to_admit"] for t, r in audited.items()} == {
        "classify": 50, "summarize": 30, "extract": 16, "draft": None}


def test_design_states_each_claim():
    design = read("DESIGN.md")
    assert len(CLAIMS) == 10
    for words, heading, phrase in CLAIMS:
        assert SAVINGS_PARAGRAPH.count(words) == 1, words
        assert subsection(design, heading).count(phrase) == 1, phrase


# --- DESIGN and the changelog --------------------------------------------------------------------

def test_design_states_v1_654_and_the_two_sub_bullets_name_it():
    design = read("DESIGN.md")
    five2 = design.split("\n### 5.2 ", 1)[1].split("\n### 5.3 ", 1)[0]
    [clause] = [line for line in five2.splitlines() if line.startswith(CLAUSE)]
    assert design.count(CLAUSE) == 1
    assert five2.index("\n- v1.653 README caveats (row PROD1h, ") < five2.index(f"\n{CLAUSE}")
    for words in ("ends with one sentence on `report --opportunities`, after the paragraph on pinned calls (v1.641)",
                  "no return on what training, hosting or building that route costs (8.3 v1.645's Hypothetical "
                  "sub-bullet)",
                  f"The sentence takes 714 bytes of the room row PROD1g made, so the section is {SECTION_BYTES:,} "
                  f"bytes by the 12.8 measure, under v1.629's {PRODUCTION_CAP:,}-byte cap, which stays, and no "
                  "paragraph is trimmed",
                  "the v1.652 and v1.653 tests hold the section less this sentence's paragraph to the bytes they set, "
                  "at most 24,000 and 23,976",
                  "No package module, evidence file or README transcript changes."):
        assert clause.count(words) == 1, words
    assert len(clause.encode("utf-8")) <= 6_000
    eight3 = subsection(design, "### 8.3 ")
    assert eight3.count(f"\n{NOT_IN_V1_645}\n") == 1 and eight3.count(f"\n{NOT_IN_V1_646}\n") == 1
    assert "(row OPP1c)" not in eight3
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.654 (")]
    assert line.startswith("- v1.654 (2026-11-25): docs and tests (5.2, row OPP1c). ")
    assert line.endswith(f" The section is {SECTION_BYTES:,} bytes, under its 30,000-byte cap; every transcript "
                         "keeps its bytes.")
    assert len(line.encode("utf-8")) <= 600


# --- what keeps its bytes ------------------------------------------------------------------------

def test_the_twelve_transcripts_keep_their_v1_640_bytes():
    blocks = BLOCK.findall(read("README.md"))
    assert len(blocks) == 12 and not any("--opportunities" in b for b in blocks)
    assert hashlib.sha256("".join(blocks).encode("utf-8")).hexdigest() == TRANSCRIPTS_SHA256


def test_no_evidence_or_research_script_opens_a_file_this_slice_edits():
    scripts = [p for folder in ("evidence", "research") for p in (ROOT / folder).rglob("*")
               if p.is_file() and p.suffix in (".py", ".sh")]
    assert len(scripts) >= 20
    opened = re.compile(r"[\"'](README\.md|DESIGN\.md|CHANGELOG\.md)[\"']")
    assert [str(p.relative_to(ROOT)) for p in scripts if opened.search(p.read_text(encoding="utf-8"))] == []
