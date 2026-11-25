"""DESIGN 5.2 v1.641 (row PIN1c): pinned calls in the docs.

No code changes. README `## Running it in production` ends with a paragraph on pinned calls (5.2,
7 and 8.1 v1.639, 8.3 and 10 v1.640), right after the one on drift (v1.635): what `pin_route`,
`pinned_by` and `allow_below_bar` do, that the hard checks (rules 1 to 5f) refuse a pin whatever
`allow_below_bar` says, that a pin runs alone with no fallback and no shadow, the record's `basis`
`pinned` and `pinned_by`, the two `report` keys, and where a pin sits next to README Limitations'
first bullet on what reacts per call (review iter-493 nit 3), whose bytes do not change. Each claim
is checked on the library beside the words that state it, and every hard rule's reason in
model_routing/router.py has its words in the paragraph (review iter-495 must-fix 1 and should-fix
1). DESIGN 5.2 v1.639's and 8.3 v1.640's Not-in-this-version sub-bullets name v1.641 in place of
row PIN1c. Every README transcript keeps its v1.640 bytes, and no evidence or research script opens
a file this slice edits, so every evidence file keeps its bytes.
"""

import hashlib
import inspect
import itertools
import re
from pathlib import Path

import pytest
from test_pin import COUNTS, MESSAGES, MODELS, TAG, TS, Ids, called, everyone, make, reasons, router
from test_readme_production import PRODUCTION, PRODUCTION_CAP, link_problems, size

import model_routing.router as router_module
from model_routing import (AllModelsFailed, Budget, BudgetExceeded, BudgetLedger, Cascade, Executor, FakeProvider,
                           Model, Monitor, NoModelClearsBar, Policy, Procedure, ProcedureResult, Registry, Router,
                           Stats, Task, report)
from model_routing.router import (BELOW_BAR, CASCADE_UNKNOWN_MODEL, CHEAPER_PER_SUCCESS, CONTEXT_TOO_SMALL,
                                  EXCLUDED_FAMILY, EXCLUDED_MODEL, GENERATOR, GENERATOR_FAMILY,
                                  INSUFFICIENT_SAMPLES, LATENCY_UNKNOWN, OUT_OF_SCOPE, PASSES, POLICY_EXCLUDED,
                                  PROCEDURE_UNKNOWN_MODEL, REGION_UNAVAILABLE, TOO_SLOW, ZDR_REQUIRED)

ROOT = Path(__file__).resolve().parents[1]
DRIFT_START = "A route's success can drift while its all-time counts still admit it, "
PIN_PARAGRAPH = (
    "A call can also pin its route. `Executor.call(..., pin_route=ROUTE, pinned_by=TAG)` runs ROUTE, a registry "
    "model, a cascade of the task (with `signals`) or one of the call's `procedures`, without ranking the routes, "
    "and `select(..., pin_route=ROUTE)` returns it as the decision's only entry, with `basis` `pinned`. A pin keeps "
    "the hard checks, rules 1 to 5f of `DESIGN.md` 5.2, so it raises `NoModelClearsBar`, whatever `allow_below_bar` "
    "says, when it is excluded, the generator or of its family, out of scope, ruled out by the policy's allowed "
    "routes or families, its `region` or its `require_zdr`, too slow or of unknown time under `deny`, when its "
    "context window is too small for the call, or when it is a cascade or procedure whose model is unknown. One "
    "under the bar or with too few trials is refused too unless `allow_below_bar=True`, and then runs with "
    "`below_bar` `true` on its decision and records. A pinned call runs its route alone, with no fallback and no "
    "shadow, so a failed or rejected answer ends it in `AllModelsFailed` and a `downgrade` budget refuses it "
    "instead of moving it on. `.call` needs `pinned_by` with a pin and refuses it without one: a tag that names "
    "who or what pinned the call, a contract or a ticket for example, which each attempt record carries beside "
    "`basis` `pinned`. `report --by basis` puts the pinned calls' spend in a row beside the routed `measured` and "
    "`prior` rows, and `report --by pinned_by` gives one row per tag beside `(none)` (`DESIGN.md` 5.2, 7, 8.1, 8.3 "
    "and 10). Next to the first bullet of [Limitations](#limitations-and-non-goals-v1), a pin is a choice the "
    "caller makes for one call before it runs, not one the router makes from the prompt, and it gives up the "
    "fallback that bullet names, while a cascade pin keeps its hand-up.")
LIMITS = "\n## Limitations and non-goals (v1)\n"
# v1.640 (96b08f7): README Limitations' first bullet, which a pin leaves true (review iter-493 nit 3)
FIRST_BULLET_SHA256, FIRST_BULLET_BYTES = "b21639def7528a8146d6a271c08da252abc4b727f8f526f994e0c56b493f1ffb", 1292
# v1.640 (96b08f7): sha256 of README's twelve ```text blocks that start with `$ model-routing`, joined
TRANSCRIPTS_SHA256 = "b870064b5eb860c802b7ce92137bccc0d2a67902df6f9abd491739ca1804fb2c"
BLOCK = re.compile(r"```text\n(\$ model-routing .*?)```", re.S)
NOT_IN_5_2 = ("  - Not in this version: `report` putting pinned spend apart from routed spend (row PIN1b, which "
              "v1.640 adds, 8.3 and 10); the README paragraph, which v1.641 adds (5.2).")
NOT_IN_8_3 = "  - Not in this version: the README paragraph, which v1.641 adds (5.2). `model_routing.__all__` is unchanged."
# review iter-495 should-fix 3: words the paragraph and the v1.641 clause both hold
SHARED = ("pin_route=ROUTE", "`pinned_by`", "`allow_below_bar`", "`NoModelClearsBar`", "`region`", "`require_zdr`",
          "`below_bar` `true`", "no fallback and no shadow", "`AllModelsFailed`", "`downgrade`", "`basis` `pinned`",
          "`report --by basis`", "`report --by pinned_by`", "hand-up")
# a candidate's reasons that are no hard check: rules 6 to 8 and the decision's own reason
NOT_HARD = {PASSES, INSUFFICIENT_SAMPLES, BELOW_BAR, CHEAPER_PER_SUCCESS}


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def production_paragraphs(text):
    body = text.split(f"\n{PRODUCTION}\n", 1)[1].split("\n## ", 1)[0]
    return body.strip().split("\n\n")


def says(words):
    assert PIN_PARAGRAPH.count(words) >= 1, words


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


def test_no_evidence_or_research_script_opens_a_file_this_slice_edits():
    # review iter-495 should-fix 2: the v1.641 clause cites this file for it
    scripts = [p for folder in ("evidence", "research") for p in (ROOT / folder).rglob("*")
               if p.is_file() and p.suffix in (".py", ".sh")]
    assert len(scripts) >= 20
    opened = re.compile(r"[\"'](README\.md|DESIGN\.md|CHANGELOG\.md)[\"']")
    assert [str(p.relative_to(ROOT)) for p in scripts if opened.search(p.read_text(encoding="utf-8"))] == []


# --- the hard checks: every reason, its words, refused whatever allow_below_bar says ----------------

def scoped_router():
    scoped = Model("z/scoped", "z", 0.4, 0.8, 100_000, scope_tasks=("other",))
    stats = Stats()
    for model_id, successes in {**COUNTS, "z/scoped": 99}.items():
        stats.add("t", model_id, successes, 100)
    task = Task(name="t", bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200)
    return Router(Registry(MODELS + [scoped]), {"t": task}, stats)


def shape(value, call):
    return ProcedureResult(call(value), tool_calls=0)


UNKNOWN_CASCADE = Cascade("x/cheap", "z/none", "sig")
UNKNOWN_PROCEDURE = Procedure("shape", "v1", shape, max_model_calls=1, max_tool_calls=0, model="z/none")
# reason: (the paragraph's words for it, the router, the pin, select's keywords)
HARD = {
    EXCLUDED_MODEL: ("when it is excluded, ", router, "x/mid", dict(exclude_models=["x/mid"])),
    EXCLUDED_FAMILY: ("when it is excluded, ", lambda: router(exclude_families=("y",)), "y/other", {}),
    GENERATOR: ("the generator or of its family", router, "y/other", dict(generator_model="y/other")),
    GENERATOR_FAMILY: ("the generator or of its family", router, "x/mid", dict(generator_model="x/cheap")),
    OUT_OF_SCOPE: ("out of scope", scoped_router, "z/scoped", {}),
    POLICY_EXCLUDED: ("ruled out by the policy's allowed routes or families", router, "y/other",
                      dict(policy=Policy(allowed_families=("x",)))),
    REGION_UNAVAILABLE: ("its `region`", router, "x/mid", dict(policy=Policy(region="test-region-1"))),
    ZDR_REQUIRED: ("its `require_zdr`", router, "x/mid", dict(policy=Policy(require_zdr=True))),
    TOO_SLOW: ("too slow", lambda: router(latencies={"x/mid": [2000.0] * 30}, max_p95_ms=1000.0), "x/mid", {}),
    LATENCY_UNKNOWN: ("of unknown time under `deny`", lambda: router(max_p95_ms=1000.0, latency_unknown="deny"),
                      "x/mid", {}),
    CONTEXT_TOO_SMALL: ("when its context window is too small for the call", router, "x/tiny", {}),
    CASCADE_UNKNOWN_MODEL: ("when it is a cascade or procedure whose model is unknown",
                            lambda: router(cascades=(UNKNOWN_CASCADE,)), UNKNOWN_CASCADE.id, dict(cascades=True)),
    PROCEDURE_UNKNOWN_MODEL: ("when it is a cascade or procedure whose model is unknown", router,
                              UNKNOWN_PROCEDURE.id, dict(procedures=(UNKNOWN_PROCEDURE,))),
}


def test_every_reason_of_the_router_is_a_hard_check_with_its_words_or_one_the_paragraph_reads_apart():
    found = set(re.findall(r'^[A-Z_]+ = "([a-z_]+)"', inspect.getsource(router_module), re.M))
    assert found == set(HARD) | NOT_HARD   # a new reason needs its words in the paragraph, or a place here


@pytest.mark.parametrize("reason", sorted(HARD))
@pytest.mark.parametrize("allow", [False, True])
def test_each_hard_check_refuses_a_pin_whatever_allow_below_bar_says(reason, allow):
    words, make_router, pin, kwargs = HARD[reason]
    says(words)
    with pytest.raises(NoModelClearsBar, match=f"^pinned route '{re.escape(pin)}' is {reason} for task 't'; ") \
            as caught:
        make_router().select("t", pin_route=pin, allow_below_bar=allow, **kwargs)
    assert reasons(caught.value.candidates)[pin] == reason


# --- the paragraph's other claims, each beside its words ----------------------------------------------

def test_a_pin_under_the_bar_or_with_too_few_trials_runs_only_when_allowed_and_is_marked():
    says("One under the bar or with too few trials is refused too unless `allow_below_bar=True`, and then runs "
         "with `below_bar` `true` on its decision and records.")
    for pin in ("x/low", "x/new"):
        with pytest.raises(NoModelClearsBar):
            router().select("t", pin_route=pin)
        assert router().select("t", pin_route=pin, allow_below_bar=True).below_bar is True
        provider, monitor = FakeProvider(everyone()), Monitor()
        make(router(), provider, monitor).call("t", MESSAGES, pin_route=pin, pinned_by=TAG, allow_below_bar=True)
        assert [(r["below_bar"], r["basis"]) for r in monitor.records] == [(True, "pinned")]


def test_a_pin_runs_alone_so_a_failed_or_rejected_answer_ends_the_call_and_no_shadow_is_sent():
    says("A pinned call runs its route alone, with no fallback and no shadow, so a failed or rejected answer ends "
         "it in `AllModelsFailed`")
    failed, rejected = FakeProvider({}), FakeProvider(everyone())
    with pytest.raises(AllModelsFailed):
        make(router(), failed).call("t", MESSAGES, pin_route="x/mid", pinned_by=TAG)
    with pytest.raises(AllModelsFailed):
        make(router(), rejected).call("t", MESSAGES, pin_route="x/mid", pinned_by=TAG, validate=lambda text: False)
    assert called(failed) == called(rejected) == ["x/mid"]
    shadowed, monitor = FakeProvider(everyone()), Monitor()
    make(router(shadow_rate=1.0), shadowed, monitor, random=lambda: 0.0).call("t", MESSAGES, pin_route="x/mid",
                                                                              pinned_by=TAG)
    assert called(shadowed) == ["x/mid"] and all("shadow" not in r for r in monitor.records)


def test_a_downgrade_budget_refuses_a_pin_instead_of_moving_it_on():
    says("and a `downgrade` budget refuses it instead of moving it on.")
    provider, ticks = FakeProvider(everyone()), itertools.count()
    executor = Executor(router(), provider, monitor=Monitor(), clock=lambda: float(next(ticks)), now=lambda: TS,
                        id_factory=Ids(), ledger=BudgetLedger([Budget("d", 1e-9, "downgrade")]))
    with pytest.raises(BudgetExceeded) as caught:
        executor.call("t", MESSAGES, pin_route="x/mid", pinned_by=TAG)
    assert (caught.value.model, provider.calls) == ("x/mid", [])


def test_call_needs_pinned_by_with_a_pin_and_refuses_it_without_one():
    says("`.call` needs `pinned_by` with a pin and refuses it without one")
    for kwargs in (dict(pin_route="x/mid"), dict(pinned_by=TAG)):
        provider = FakeProvider(everyone())
        with pytest.raises(ValueError):
            make(router(), provider).call("t", MESSAGES, **kwargs)
        assert provider.calls == []
    assert "pinned_by" not in inspect.signature(Router.select).parameters


def test_a_cascade_pin_keeps_its_hand_up():
    says("while a cascade pin keeps its hand-up.")
    cascade = Cascade("x/cheap", "x/mid", "sig")
    route = router(cascades=(cascade,))
    route.stats.add("t", cascade.id, 99, 100, escalated=50)
    provider = FakeProvider(everyone())
    result = make(route, provider).call("t", MESSAGES, signals={"sig": lambda text: True}, pin_route=cascade.id,
                                        pinned_by=TAG)
    assert (result.model, called(provider)) == ("x/mid", ["x/cheap", "x/mid"])


def test_a_pinned_call_runs_alone_and_report_puts_it_beside_the_routed_ones():
    says("`report --by basis` puts the pinned calls' spend in a row beside the routed `measured` and `prior` rows, "
         "and `report --by pinned_by` gives one row per tag beside `(none)`")
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
    assert "for review iter-493 nit 3" in clause and "(tests/test_pin_docs.py, review iter-495 should-fix 2)" in clause
    assert [w for w in SHARED if w not in clause or w not in PIN_PARAGRAPH] == []
    assert design.count(NOT_IN_5_2 + "\n") == 1 and eight3.count(NOT_IN_8_3 + "\n") == 1
    assert "the README paragraph (row PIN1c)" not in design
    # v1.642: no pin of the Status line, which each later version moves; tests/test_design_status.py
    # keeps the Status rule (as 4460d73 did for v1.638)
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.641 (")]
    assert line.startswith("- v1.641 (2026-11-25): docs and tests (5.2, 8.3, row PIN1c). ")
    assert len(line.encode("utf-8")) <= 600
