"""DESIGN 5.2 v1.647 (row PROD1g, first part): room in README `## Running it in production`.

From v1.647 the section's paragraph on `promote` (v1.605) and the one on `drift` (v1.635), its two
longest at 2,847 and 3,046 bytes, are cut, so later versions have room under v1.629's 30,000-byte cap
(tests/test_readme_production.py), which stays. Each keeps its lead claim, every API, command and
option name it gave, its quote and its links. Each clause it dropped is stated in DESIGN 4.7, 8.3 or
10: DROPPED pins it to the subsection and a phrase found there, the two that no subsection stated
(a chain of promotions losing up to k times the margin, and the pairs a margin needs) being added to
4.7 as v1.647. DROPPED was made from a word diff of v1.646's two paragraphs (8c53538) against v1.647's:
every run of words the diff shows as removed is in an entry, as v1.646 wrote it, and what the diff
keeps is the lead sentences, the names in NAMES, the quotes and links in LINKS and the clauses
tests/test_promote_docs.py and tests/test_drift_docs.py pin (review iter-502 must-fix 1, should-fix 2).
The README pins of the docs modules that read the two paragraphs are restated to the new text, and
each fails on v1.646's README. A docs slice: no package module, evidence file or README transcript
changes; these tests failed on v1.646's README and pass on v1.647's.
"""

from pathlib import Path

from test_readme_production import PRODUCTION, PRODUCTION_CAP, paragraphs, size

ROOT = Path(__file__).resolve().parents[1]
PROMOTE_LEAD = "Judge a challenger route against the current one only on the items both were graded on. "
DRIFT_LEAD = ("A route's success can drift while its all-time counts still admit it, since a provider can change "
              "the model behind an ID. ")
# v1.646 (8c53538): each paragraph's UTF-8 bytes and its names in backticks, in their first order
OLD_BYTES = {PROMOTE_LEAD: 2_847, DRIFT_LEAD: 3_046}
NAMES = {
    PROMOTE_LEAD: ["calibrate --outcomes FILE",
                   "model-routing promote --task T --challenger ROUTE --margin M --outcomes FILE", "select",
                   "promote", "--alpha", "-M", "hold", "insufficient_overlap", "min_samples", "DESIGN.md",
                   "pair_outcomes", "current", "paired_promotion", "cost_effective", "cost_blind", "retry_same"],
    DRIFT_LEAD: ["model-routing drift --log PATH --audits PATH [--window 30d]", "report --audits", "--stats FILE",
                 "ok", "min_samples", "fell_below", "rose_above", "--json",
                 "select --window 30d --log PATH --audits PATH", "--stats", "DESIGN.md", "max_p95_ms",
                 "select --window", "drift", "latency_flag", "went_over", "came_under"],
}
LINKS = {
    PROMOTE_LEAD: ["(https://doi.org/10.3102/1076998611411915)",
                   "(research/production-lessons.md#switch-models-only-on-locked-data-and-a-significant-result)",
                   "Harvey compares models on fixed sets: \"once a collection of evaluation samples is \u201cpublished,\u201d"],
    DRIFT_LEAD: ["(research/production-lessons.md#test-a-model-before-the-switch-and-re-run-the-tests-on-the-models-in-"
                 "production-every-day)",
                 "GitHub runs its tests on the models it serves: \"We also run these tests against our production "
                 "models every day."],
}
# Each clause v1.647 dropped, as v1.646's paragraph wrote it, the DESIGN subsection that states it, and
# a phrase of that subsection that says it.
DROPPED = [
    (PROMOTE_LEAD, "and two routes measured on different labeled items cannot be told apart by their bounds", "### 4.7 ",
     "two success rates measured on different labeled items cannot be told apart by their bounds"),
    (PROMOTE_LEAD, "to FILE, apart from the stats, and", "## 10. ",
     "Then it writes the stats file as it does without the option and appends each record to FILE"),
    (PROMOTE_LEAD, "so two routes pair only when one results file graded both", "### 4.7 ",
     "so two routes pair only when that one file graded both"),
    (PROMOTE_LEAD, "cheaper per item at list prices", "## 10. ", "so at list prices in either flavor and per item"),
    (PROMOTE_LEAD, "(the adjusted Wald interval of [Bonett and Price, 2012]", "### 4.7 ",
     "the adjusted Wald interval of Bonett and Price (2012)"),
    (PROMOTE_LEAD, "each promotion against the route before it can lose up to M by the interval's reading", "### 4.7 ",
     "can lose up to `margin` at each step by the interval's reading, so k of them up to k times `margin` against "
     "the first route"),
    (PROMOTE_LEAD, "`promote` always pairs with `select`'s primary", "### 4.7 ",
     "since `promote` (10 v1.603) pairs with `select`'s primary"),
    (PROMOTE_LEAD, "at 30 pairs it is -0.0866 with no discordant pair and -0.1500 with two each way", "### 4.7 ",
     "it is -0.0866 at 30 pairs with no discordant pair and -0.1500 with two each way"),
    (PROMOTE_LEAD, "a cheaper challenger needs 91 pairs to clear a margin of 0.03 with no discordant pair and 442 with "
     "5% of the pairs going each way, and never fewer than the task's `min_samples`", "### 4.7 ",
     "gives `promote` from 91 pairs with no discordant pair and from 442 with 5% of the pairs going each way"),
    (PROMOTE_LEAD, "whose primary is the cheapest per success", "## 10. ",
     "whose primary is the cheapest per success (5.3 v1.567)"),
    (PROMOTE_LEAD, "Calibrate each labeled file once, since a second run doubles the trials the admission reads while "
     "the pairs count each item once", "## 10. ",
     "A results file calibrated twice counts its trials twice in the stats (v1.602 above) while `pair_outcomes` "
     "counts each repeated item once"),
    (PROMOTE_LEAD, "at a false-promotion rate of at most about 0.05", "## 10. ",
     "at a family-wise rate of at most about A passes `--alpha` A / k (Bonferroni)"),
    (DRIFT_LEAD, "the last N UTC days, today included,", "## 10. ", "the N UTC days that end with the command's date"),
    # review iter-502 must-fix 1: the next three are pinned to the `audited_results` bullets `drift` reads
    (DRIFT_LEAD, "so a route whose rejected answers a fallback then made good still pays for them", "### 8.3 ",
     "So a route whose answers the check rejects, and a fallback then answers, counts those trials too"),
    (DRIFT_LEAD, "so a window under `min_samples` trials flags nothing", "### 8.3 ",
     "So a window under `min_samples` trials flags nothing"),
    (DRIFT_LEAD, "so a route measured at 0.92 all-time whose audited calls in the window succeed at 0.70 loses "
     "admission there", "## 10. ",
     "so a route measured at 0.92 all-time whose audited calls in the window succeed at 0.70 loses admission there"),
    (DRIFT_LEAD, "the window's calls are among its calls, so the all-time bound moves toward the window's as the "
     "window grows", "### 8.3 ", "so the all-time bound moves toward the window's as the window grows"),
    (DRIFT_LEAD, "audits picked by a rule other than chance bias every route's rate", "### 8.3 ",
     "an audit file that picks calls by a rule other than chance biases every route's rate"),
    (DRIFT_LEAD, "counts once for the cascade, with whether it handed up", "### 8.3 ",
     "`item`, `correct`, `escalated` the record's"),
    (DRIFT_LEAD, "at its model calls' and tools' cost", "### 8.3 ",
     "for a procedure, the records of its model calls and its closing record, which holds its tool cost"),
    (DRIFT_LEAD, "Each audited call's row also carries its route's time", "### 8.3 ",
     "Each row now carries `latency_ms`, which `calibrate_from_results` reads as its one trial's time"),
    (DRIFT_LEAD, "(a cascade's legs summed,", "### 8.3 ",
     "a cascade's row the `math.fsum`, in log order, of the `latency_ms` of the entry's records that v1.636 checks"),
    (DRIFT_LEAD, " a procedure's whole run)", "### 8.3 ",
     "a procedure's row its closing record's alone, which times the whole run"),
    (DRIFT_LEAD, "`latency_flag`, kept apart from the success flag: `went_over` when the window's p95, over at least "
     "`min_samples` timed calls, is over the bar while the all-time side keeps the route in", "### 8.3 ",
     "`latency_flag` is `went_over` when the all-time side is on time and the window's p95, not None, is over the bar"),
    (DRIFT_LEAD, "`came_under` the other way", "### 8.3 ",
     "`came_under` when the all-time side is not on time (its p95 over the bar, or none under `\"deny\"`)"),
    (DRIFT_LEAD, ", kept apart from the success flag:", "## 10. ",
     "the table gains, after `flag`, the columns `all_time_p95_ms`, `window_p95_ms`"),
    (DRIFT_LEAD, "when the all-time side comes from the same log, as it does without `--stats`,", "### 8.3 ",
     "when both `Stats` come from one log, the window's calls are among the all-time ones"),
    (DRIFT_LEAD, "and each bound is at the task's confidence", "### 8.3 ",
     "each row's bounds are each at the task's confidence, so over many keys some flags come by chance"),
    (PROMOTE_LEAD, "once a challenger is promoted on non-inferiority, check the next one against the first route, not "
     "the promoted one", "### 4.7 ", "a caller checks each later challenger against the first route"),
    (PROMOTE_LEAD, "The bound is wide on few pairs:", "### 4.7 ", "The bound is wide on few pairs: at the default `alpha`"),
]
ENDS = {"### 4.7 ": "\n## 5. ", "### 8.3 ": "\n## 9. ", "## 10. ": "\n## 11. "}


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def paragraph(lead):
    [found] = [p for p in paragraphs(read("README.md"), PRODUCTION) if p.startswith(lead)]
    return found


def subsection(design, heading):
    start = design.index("\n" + heading)
    return design[start:design.index(ENDS[heading], start)]


def test_the_two_paragraphs_are_shorter_and_the_section_under_its_cap():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES}
    assert found == {PROMOTE_LEAD: 1_902, DRIFT_LEAD: 2_032}
    assert sum(OLD_BYTES.values()) - sum(found.values()) == 1_959
    assert size(read("README.md"), PRODUCTION) <= PRODUCTION_CAP == 30_000


def test_each_keeps_its_lead_its_names_its_quote_and_its_links():
    for lead in OLD_BYTES:
        text = paragraph(lead)
        names = []
        for name in text.split("`")[1::2]:
            if name not in names:
                names.append(name)
        assert [n for n in NAMES[lead] if n not in names] == [], lead
        for link in LINKS[lead]:
            assert text.count(link) == 1, link
        assert "\u2014" not in text and "\u2013" not in text


def test_each_dropped_clause_is_gone_and_its_design_subsection_states_it():
    design = read("DESIGN.md")
    assert len(DROPPED) == 30
    for lead, clause, heading, phrase in DROPPED:
        assert clause not in paragraph(lead), clause
        assert phrase in subsection(design, heading), (heading, phrase)


def test_the_check_fails_on_a_clause_still_there_or_a_phrase_design_lacks():
    design = read("DESIGN.md")
    assert "complements the bar and never replaces it" in paragraph(PROMOTE_LEAD)
    assert "k times M against the first route" not in subsection(design, "## 10. ")
    assert "-0.0866" not in subsection(design, "## 10. ") and "-0.0866" in subsection(design, "### 4.7 ")


def test_design_states_the_trim_the_two_new_clauses_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = design[design.index("\n### 5.2 "):design.index("\n### 5.3 ")]
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.647 README trim (row PROD1g, first part; ")]
    for kept in ("is cut from 2,847 to 1,902 bytes and the one on `drift` (v1.635) from 3,046 to 2,032",
                 "under v1.629's 30,000-byte cap, which stays",
                 "each clause it drops is stated in 4.7, 8.3 or 10",
                 "tests/test_readme_trim.py pins each dropped clause to its subsection and a phrase found there",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    four7 = subsection(design, "### 4.7 ")
    [new] = [line for line in four7.splitlines() if line.startswith("- v1.647 (row PROD1g, 5.2 v1.647: ")]
    # before v1.601's Not-in-this-version line, which tests/test_promote_docs.py pins as 4.7's last
    assert four7.index(new) < four7.index("\n- Not in this version: the labeled file's hash")
    assert len(new.encode("utf-8")) <= 6_000 and len(mine.encode("utf-8")) <= 6_000
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.647 (")]
    assert line.startswith("- v1.647 (2026-11-25): docs and tests (4.7, 5.2, row PROD1g). ")
    assert len(line.encode("utf-8")) <= 600
