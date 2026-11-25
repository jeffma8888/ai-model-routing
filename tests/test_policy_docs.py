"""DESIGN 5.2 v1.644 (row POL2c): a policy's name and the `policy` key in the docs.

No code changes. README `## Running it in production`'s policy paragraph (v1.625) shows `Policy`'s
last field, `name=None` (5.1 v1.642), and its last sentence gains that a call's records name its
policy as `policy`, its name or else a digest of its rules (7 and 8.1 v1.642), so `report --by
policy` gives each tenant's spend a row (8.3 and 10 v1.643), and that `call_delegated` names none
(7 v1.642). To stay inside the v1.629 cap the paragraph names its two commands without
`model-routing `, as the section's latency paragraph names its own. research/production-lessons.md's
Harvey line on tenant policy says the same after its v1.625 sentence. Each claim is checked on the
library beside the words that state it. 7 v1.642's and 8.3 v1.643's Not-in-this-version sub-bullets
name v1.644 in place of row POL2c. Every README transcript keeps its v1.640 bytes, and no evidence or
research script opens a file this slice edits. The paragraph and the note's line are pinned whole in
tests/test_policy_cli.py.
"""

import dataclasses
import hashlib
import re
from pathlib import Path

import pytest
import test_policy_records as records_
import test_report_policy as tenants
from test_pin_docs import BLOCK, TRANSCRIPTS_SHA256
from test_policy_cli import HARVEY_LINE, POLICY_PARAGRAPH
from test_readme_production import PRODUCTION, PRODUCTION_CAP, size

from model_routing import Budget, BudgetLedger, Monitor, Policy, report

ROOT = Path(__file__).resolve().parents[1]
POLICY_START = "A tenant's rules hold whatever a route costs. "
SIGNATURE = "`Policy(allowed_routes=None, allowed_families=None, region=None, require_zdr=False, name=None)`"
COMMANDS = "a JSON object of those keys in a file to `select --policy FILE` or `delegate --policy FILE`, "
SENTENCE = ("On one shared `Executor` each call may carry its own tenant's policy, and its records name it as "
            "`policy`, its `name` or else a digest of its rules, so `report --by policy` gives each tenant's "
            "spend a row; `call_delegated` names none.")
OLD_SENTENCE = "On one shared `Executor` each call may carry its own tenant's policy."
SECTION_BYTES = 29_996
NOTE_SENTENCE = ("From v1.642 every record of a call under a policy with a rule or a name names it, by its name or "
                 "else a digest of its rules, from v1.643 `report --by policy` gives each tenant's spend a row, and "
                 "a hand-off run with `call_delegated` names none.")
CLAUSE = "- v1.644 README and note (row POL2c, 5.1, 7 and 8.1 v1.642, 8.3 and 10 v1.643): "
NOT_IN_7 = ("  - Not in this version: `report --by policy`, and `select --policy FILE` and `delegate --policy FILE` "
            "reading `name` (row POL2b, which v1.643 adds, 8.3, 10 and 13.7); the README sentence, which v1.644 "
            "adds (5.2).")
NOT_IN_8_3 = "  - Not in this version: the README sentence, which v1.644 adds (5.2). `model_routing.__all__` is unchanged."
# words the sentence and the v1.644 clause both hold
SHARED = ("`policy`", "a digest of its rules", "`report --by policy` gives each tenant's spend a row",
          "`call_delegated` names none")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def production_paragraphs(text):
    body = text.split(f"\n{PRODUCTION}\n", 1)[1].split("\n## ", 1)[0]
    return body.strip().split("\n\n")


# --- README --------------------------------------------------------------------------------------

def test_the_policy_paragraph_ends_with_the_sentence_inside_the_cap():
    text = read("README.md")
    [paragraph] = [p for p in production_paragraphs(text) if p.startswith(POLICY_START)]
    assert paragraph == POLICY_PARAGRAPH and paragraph.endswith(" " + SENTENCE)
    assert text.count(SENTENCE) == 1 and OLD_SENTENCE not in text
    assert size(text, PRODUCTION) == SECTION_BYTES <= PRODUCTION_CAP
    assert "\u2014" not in SENTENCE and "\u2013" not in SENTENCE


def test_the_signature_is_the_fields_of_policy_in_order_with_their_defaults():
    built = "`Policy(" + ", ".join(f"{f.name}={f.default!r}" for f in dataclasses.fields(Policy)) + ")`"
    assert built == SIGNATURE and POLICY_PARAGRAPH.count(SIGNATURE) == 1


def test_the_two_commands_are_named_bare_as_the_latency_paragraph_names_its_own():
    text = read("README.md")
    assert POLICY_PARAGRAPH.count(COMMANDS) == 1 and "model-routing select --policy" not in text
    [latency] = [p for p in production_paragraphs(text) if p.startswith("A task can also hold its routes to a time. ")]
    assert latency.count("`select --json` and `delegate --json`") == 1


# --- each claim on the library, beside its words -------------------------------------------------

def test_two_tenants_records_name_their_policies_and_report_gives_each_a_row():
    assert SENTENCE.count("its records name it as `policy`, its `name` or else a digest of its rules") == 1
    records = tenants.tenants_log(Monitor())
    named, unnamed = tenants.TENANT_A, tenants.TENANT_B
    assert (named.name, named.label, unnamed.name) == ("tenant-a", "tenant-a", None)
    assert unnamed.label.startswith("sha256:") and len(unnamed.label) == len("sha256:") + 64
    assert sorted({r.get("policy") or "" for r in records}) == sorted({"", "tenant-a", unnamed.label})
    assert SENTENCE.count("so `report --by policy` gives each tenant's spend a row") == 1
    rows = {r["group"]: r["calls"] for r in report(records, by="policy")}
    assert rows == {"tenant-a": 2, unnamed.label: 1, "(none)": 3}


@pytest.mark.parametrize("policy, label", [
    (records_.TENANT, "sha256:" + records_.TENANT_DIGEST),
    (dataclasses.replace(records_.TENANT, name="acme"), "acme"),
    (Policy(), None),
], ids=["unnamed", "named", "Policy()"])
def test_every_record_of_a_call_names_its_policy_and_an_empty_one_none(policy, label):
    # "its records": the attempt, its shadow's and each budget record; Policy() is left to the spec
    ex, monitor = records_.make(records_.router(shadow_rate=1.0),
                                ledger=BudgetLedger([Budget("note", 0.0000001, "warn")]), random=lambda: 0.0)
    ex.call("t", records_.MESSAGES, policy=policy)
    kinds = [("shadow" if r.get("shadow") else "budget" if "budget_event" in r else "attempt") for r in monitor.records]
    assert sorted(set(kinds)) == ["attempt", "budget", "shadow"]
    assert [r.get("policy") for r in monitor.records] == [label] * len(kinds)
    assert all(("policy" in r) == (label is not None) for r in monitor.records)


def test_call_delegated_names_none():
    assert SENTENCE.endswith("; `call_delegated` names none.")
    r = records_.router(models=records_.MODELS + [records_.model("y/cheap", 0.1, family="y")],
                        counts=dict(records_.COUNTS, **{"y/cheap": 97}))
    decision = r.decide_delegation("t", "y/cheap", context_tokens=2000, brief_tokens=1000, result_tokens=1000,
                                   inline_separate_call=False,
                                   policy=dataclasses.replace(records_.TENANT, name="acme"))
    ex, monitor = records_.make(r, {m: records_.ok for m in ("x/small", "x/mid", "x/big", "y/cheap")})
    ex.call_delegated(decision, records_.MESSAGES)
    assert monitor.records and not any("policy" in rec for rec in monitor.records)
    assert [row["group"] for row in report(monitor.records, by="policy")] == ["(none)"]


# --- the note, DESIGN and the changelog ----------------------------------------------------------

def test_the_note_says_the_records_name_the_policy():
    note = read("research/production-lessons.md")
    assert HARVEY_LINE.count(NOTE_SENTENCE) == 1 and note.count(NOTE_SENTENCE) == 1
    assert HARVEY_LINE.index("read one from a JSON file. ") < HARVEY_LINE.index(NOTE_SENTENCE)
    assert '"' not in NOTE_SENTENCE   # the note reads double-quoted text as a quote


def test_design_states_v1_644_and_the_two_sub_bullets_name_it():
    design = read("DESIGN.md")
    five2 = design.split("\n### 5.2 ", 1)[1].split("\n### 5.3 ", 1)[0]
    [clause] = [line for line in five2.splitlines() if line.startswith(CLAUSE)]
    assert design.count(CLAUSE) == 1 and five2.splitlines()[-1] == clause
    for words in SHARED:
        assert SENTENCE.count(words) == 1 and clause.count(words) >= 1, words
    for words in ("`name=None`", "`Policy()`", f"{SECTION_BYTES:,} of its {PRODUCTION_CAP:,} bytes",
                  "with no double quote in the line", "(96b08f7)", "tests/test_policy_docs.py"):
        assert clause.count(words) >= 1, words
    seven = design[design.index("## 7. "):design.index("## 8. ")]
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert seven.count(f"\n{NOT_IN_7}\n") == 1 and eight3.count(f"\n{NOT_IN_8_3}\n") == 1
    assert "the README sentence (row POL2c)" not in design
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.644 (")]
    assert line.startswith("- v1.644 (2026-11-25): docs and tests (5.2, row POL2c). ")
    assert line.endswith(" With no code change every output keeps its bytes.") and len(line.encode("utf-8")) <= 600


# --- what keeps its bytes ------------------------------------------------------------------------

def test_the_twelve_transcripts_keep_their_v1_640_bytes():
    blocks = BLOCK.findall(read("README.md"))
    assert len(blocks) == 12 and not any("--policy" in b or "policy" in b.split("\n", 1)[0] for b in blocks)
    assert hashlib.sha256("".join(blocks).encode("utf-8")).hexdigest() == TRANSCRIPTS_SHA256


def test_no_evidence_or_research_script_opens_a_file_this_slice_edits():
    scripts = [p for folder in ("evidence", "research") for p in (ROOT / folder).rglob("*")
               if p.is_file() and p.suffix in (".py", ".sh")]
    assert len(scripts) >= 20
    opened = re.compile(r"[\"'](README\.md|DESIGN\.md|CHANGELOG\.md)[\"']|production-lessons")
    assert [str(p.relative_to(ROOT)) for p in scripts if opened.search(p.read_text(encoding="utf-8"))] == []
