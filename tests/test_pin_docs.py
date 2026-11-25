"""DESIGN 5.2 v1.641 (row PIN1c): pinned calls in the docs.

No code changes. README `## Running it in production` ends with a paragraph on pinned calls (5.2,
7 and 8.1 v1.639, 8.3 and 10 v1.640), right after the one on drift (v1.635): what `pin_route`,
`pinned_by` and `allow_below_bar` do, that the hard checks (rules 1 to 5f) refuse a pin whatever
`allow_below_bar` says, that a pin runs alone with no fallback and no shadow, the record's `basis`
`pinned` and `pinned_by`, the two `report` keys, and where a pin sits next to README Limitations'
first bullet on what reacts per call (review iter-493 nit 3), whose bytes do not change. DESIGN 5.2
v1.639's and 8.3 v1.640's Not-in-this-version sub-bullets name v1.641 in place of row PIN1c. Every
README transcript keeps its v1.640 bytes, and no evidence or research script opens a file this
slice edits, so every evidence file keeps its bytes.
"""

import hashlib
import re
from pathlib import Path

from test_pin import MESSAGES, TAG, called, everyone, make, router
from test_readme_production import PRODUCTION, PRODUCTION_CAP, link_problems, size

from model_routing import FakeProvider, Monitor, report

ROOT = Path(__file__).resolve().parents[1]
DRIFT_START = "A route's success can drift while its all-time counts still admit it, "
PIN_PARAGRAPH = (
    "A call can also pin its route. `Executor.call(..., pin_route=ROUTE, pinned_by=TAG)` runs ROUTE, a registry "
    "model, a cascade of the task (with `signals`) or one of the call's `procedures`, without ranking the routes, "
    "and `select(..., pin_route=ROUTE)` returns it as the decision's only entry, with `basis` `pinned`. A pin keeps "
    "the hard checks, rules 1 to 5f of `DESIGN.md` 5.2, so it raises `NoModelClearsBar`, whatever `allow_below_bar` "
    "says, when it is excluded, the generator or of its family, out of scope, ruled out by the policy, too slow or "
    "of unknown time under `deny`, when its context window is too small for the call, or when it is a cascade or "
    "procedure whose model is unknown. One under the bar or with too few trials is refused too unless "
    "`allow_below_bar=True`, and then runs with `below_bar` `true` on its decision and records. A pinned call runs "
    "its route alone, with no fallback and no shadow, so a failed or rejected answer ends it in `AllModelsFailed` "
    "and a `downgrade` budget refuses it instead of moving it on. `.call` needs `pinned_by`, a tag that names who or "
    "what pinned the call, a contract or a ticket for example, and each attempt record carries it beside `basis` "
    "`pinned`: `report --by basis` puts the pinned calls' spend in a row beside the routed `measured` and `prior` "
    "rows, and `report --by pinned_by` gives one row per tag beside `(none)` (`DESIGN.md` 5.2, 7, 8.1, 8.3 and 10). "
    "Next to the first bullet of [Limitations](#limitations-and-non-goals-v1), a pin is a choice the caller makes "
    "for one call before it runs, not one the router makes from the prompt, and it gives up the fallback that "
    "bullet names, while a cascade pin keeps its hand-up.")
LIMITS = "\n## Limitations and non-goals (v1)\n"
# v1.640 (96b08f7): README Limitations' first bullet, which a pin leaves true (review iter-493 nit 3)
FIRST_BULLET_SHA256, FIRST_BULLET_BYTES = "b21639def7528a8146d6a271c08da252abc4b727f8f526f994e0c56b493f1ffb", 1292
# v1.640 (96b08f7): sha256 of README's twelve ```text blocks that start with `$ model-routing`, joined
TRANSCRIPTS_SHA256 = "b870064b5eb860c802b7ce92137bccc0d2a67902df6f9abd491739ca1804fb2c"
BLOCK = re.compile(r"```text\n(\$ model-routing .*?)```", re.S)
NOT_IN_5_2 = ("  - Not in this version: `report` putting pinned spend apart from routed spend (row PIN1b, which "
              "v1.640 adds, 8.3 and 10); the README paragraph, which v1.641 adds (5.2).")
NOT_IN_8_3 = "  - Not in this version: the README paragraph, which v1.641 adds (5.2). `model_routing.__all__` is unchanged."


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def production_paragraphs(text):
    body = text.split(f"\n{PRODUCTION}\n", 1)[1].split("\n## ", 1)[0]
    return body.strip().split("\n\n")


# --- README --------------------------------------------------------------------------------------

def test_the_paragraph_ends_the_section_after_the_drift_one_inside_the_cap():
    text = read("README.md")
    paragraphs = production_paragraphs(text)
    assert text.count(PIN_PARAGRAPH) == 1 and paragraphs[-1] == PIN_PARAGRAPH
    assert paragraphs[-2].startswith(DRIFT_START)
    assert size(text, PRODUCTION) <= PRODUCTION_CAP
    assert "\u2014" not in PIN_PARAGRAPH and "\u2013" not in PIN_PARAGRAPH


def test_the_limitations_link_resolves_and_the_first_bullet_keeps_its_bytes():
    text = read("README.md")
    assert "(#limitations-and-non-goals-v1)" in PIN_PARAGRAPH and link_problems(text) == []
    limits = text.split(LIMITS, 1)[1].split("\n## ", 1)[0]
    first = [line for line in limits.split("\n") if line.startswith("- ")][0]
    assert first.startswith("- Routes per task, or per slice a call names, not per prompt: ")
    assert (hashlib.sha256(first.encode("utf-8")).hexdigest(), len(first.encode("utf-8"))) == (
        FIRST_BULLET_SHA256, FIRST_BULLET_BYTES)


def test_the_twelve_transcripts_keep_their_v1_640_bytes():
    blocks = BLOCK.findall(read("README.md"))
    assert len(blocks) == 12 and not any("pin_route" in b or "pinned_by" in b for b in blocks)
    assert hashlib.sha256("".join(blocks).encode("utf-8")).hexdigest() == TRANSCRIPTS_SHA256


# --- the facts the paragraph states, on one executor's log ----------------------------------------

def test_a_pinned_call_runs_alone_and_report_puts_it_beside_the_routed_ones():
    route, provider, monitor = router(), FakeProvider(everyone()), Monitor()
    executor = make(route, provider, monitor)
    routed = executor.call("t", MESSAGES)
    pinned = executor.call("t", MESSAGES, pin_route="x/mid", pinned_by=TAG)
    # the executor sizes the short message itself, so x/tiny, the cheapest, holds the routed call
    assert (routed.model, pinned.model, called(provider)) == ("x/tiny", "x/mid", ["x/tiny", "x/mid"])
    assert [(r["model"], r["basis"], r.get("pinned_by")) for r in monitor.records] == [
        ("x/tiny", "measured", None), ("x/mid", "pinned", TAG)]
    by_basis = {r["group"]: (r["calls"], r["cost_usd"]) for r in report(monitor.records, by="basis")}
    by_tag = {r["group"]: (r["calls"], r["cost_usd"]) for r in report(monitor.records, by="pinned_by")}
    costs = [r["cost_usd"] for r in monitor.records]
    assert by_basis == {"measured": (1, costs[0]), "pinned": (1, costs[1])}
    assert by_tag == {"(none)": (1, costs[0]), TAG: (1, costs[1])}


# --- DESIGN and the changelog --------------------------------------------------------------------

def test_design_states_v1_641_in_5_2_and_the_two_sub_bullets_name_it():
    design = read("DESIGN.md")
    five2 = design[design.index("\n### 5.2 "):design.index("\n### 5.3 ")]
    eight3 = design[design.index("\n### 8.3 "):design.index("\n## 9. ")]
    head = "\n- v1.641 README (row PIN1c, 5.2, 7 and 8.1 v1.639, 8.3 and 10 v1.640): "
    assert five2.count(head) == 1 and design.count(head) == 1
    assert five2.index("\n- v1.639 a pinned route (row PIN1a): ") < five2.index(NOT_IN_5_2) < five2.index(head)
    clause = five2[five2.index(head):].split("\n", 2)[1]
    assert "for review iter-493 nit 3" in clause and "(tests/test_pin_docs.py)" in clause
    assert design.count(NOT_IN_5_2 + "\n") == 1 and eight3.count(NOT_IN_8_3 + "\n") == 1
    assert "the README paragraph (row PIN1c)" not in design
    [status] = [x for x in design.splitlines() if x.startswith("Status: ")]
    assert status.startswith("Status: v1.641, 2026-11-25 (v1.641, docs and tests: README `## Running it in production` "
                             "ends with a paragraph on pinned calls, ")
    assert status.count("(row PIN1c); v1.640, spec, code and tests: ") == 1
    line = read("CHANGELOG.md").rstrip("\n").rsplit("\n", 1)[1]
    assert line.startswith("- v1.641 (2026-11-25): docs and tests (5.2, 8.3, row PIN1c). ")
    assert len(line.encode("utf-8")) <= 600
