"""Row ESC1a (DESIGN 7 v1.532): research/escalation.md and the escalation spec it points to.

The note says why a cascade (a cheap model, a signal the caller computes, a strong model) is one
routing candidate with its own calibration, which converted public datasets record a signal a
replay can compute, and which dataset and signal row ESC3 runs first. DESIGN 7 v1.532 is the spec
row ESC2 implements; no code reads it yet. These tests read only committed text."""

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "research" / "escalation.md"
DESIGN = ROOT / "DESIGN.md"
RESEARCH_README = ROOT / "research" / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"

SECTIONS = [
    "Facts",
    "Why a cascade is one candidate",
    "Signals the public data can test",
    "What row ESC3 runs",
    "What row ESC2 implements",
    "Not settled here (row ESC1b)",
]


def note():
    return NOTE.read_text(encoding="utf-8")


def section(text, name):
    """The body of the `## name` section, up to the next `## ` heading."""
    head = f"\n## {name}\n"
    assert text.count(head) == 1, name
    body = text.split(head, 1)[1]
    return body.split("\n## ", 1)[0]


def design_7():
    text = DESIGN.read_text(encoding="utf-8")
    start = text.index("\n## 7. Execution with fallback (`executor.py`)\n")
    end = text.index("\n## 8. ", start)
    return text[start:end]


def escalation_spec():
    part = design_7()
    start = part.index("\n- v1.532 escalation (row ESC1a;")
    return part[start:]


def test_the_note_is_ascii_with_its_sections_in_order():
    text = note()
    assert text.isascii()
    assert "\u2013" not in text and "\u2014" not in text
    assert text.startswith("# Escalation: start on a cheap model, hand up on a signal (2026-11-20)\n")
    heads = re.findall(r"^## (.+)$", text, flags=re.M)
    assert heads == SECTIONS


def test_the_short_answer_states_the_guarantee_the_cost_and_the_pick():
    first = note().split("\n## ", 1)[0]
    for phrase in ("one routing candidate with calibration rows of its own",
                   "never inherits the strong model's pass",
                   "the measured escalation share times the strong model's cost",
                   "`DESIGN.md` 7 v1.532",
                   "tau2-bench", "\"more than N agent calls\"", "row ESC1b"):
        assert phrase in first, phrase


def test_the_note_names_the_dataset_and_signal_for_esc3():
    body = section(note(), "What row ESC3 runs")
    assert "- Dataset: tau2-bench, the 12 pinned run files of 12.14, trial 0" in body
    assert "the signal `calls-over-N`" in body
    assert "escalated when the cheap run makes more than N agent calls" in body
    assert "uncached input" in body and "the strong run's list-price cost" in body
    assert "a signal measured on a benchmark may not exist in your product" in body


def test_the_signal_table_covers_every_converted_dataset_once():
    body = section(note(), "Signals the public data can test")
    rows = [line for line in body.splitlines() if line.startswith("| ") and not line.startswith("| Dataset")]
    assert len(rows) == 7
    firsts = [row.split(" | ", 1)[0][2:] for row in rows]
    assert firsts == [
        "tau2-bench (12.14)", "Longtail-SWE (12.25)", "LiveCodeBench (12.16)", "LLMRouterBench (12.18)",
        "RouterBench, AutoBench 2026, the response bank, the registry pair (12.6, 12.9, 12.20, 12.23)",
        "TRAIL (13.11)", "AgentsSci ([hand-off-data.md](hand-off-data.md), not converted)",
    ]
    uses = [row.rstrip(" |").rsplit(" | ", 1)[1] for row in rows]
    assert uses[0] == "ESC3 first"
    assert uses[2].startswith("ESC3 second, success only")
    assert all(use.startswith("no") for use in uses[3:])


def test_the_design_numbers_the_note_cites_are_design_headings():
    text = DESIGN.read_text(encoding="utf-8")
    for number in ("12.6", "12.9", "12.14", "12.15", "12.16", "12.18", "12.20", "12.23", "12.25", "12.27",
                   "12.28", "13.11"):
        assert f"\n### {number} " in text, number


def test_the_note_links_resolve_inside_research():
    for target in re.findall(r"\]\(([^)#]+)\)", note()):
        assert not target.startswith(("/", "http")), target
        assert (NOTE.parent / target).is_file(), target


def test_the_spec_is_in_design_7_after_the_slices_bullet():
    part = design_7()
    assert part.index("- v1.511 slices (row STRAT1):") < part.index("- v1.532 escalation (row ESC1a;")
    assert part.count("- v1.532 escalation (row ESC1a;") == 1


def test_the_spec_holds_each_contract_item():
    spec = escalation_spec()
    for phrase in (
        "spec only: row ESC2 implements it, so until then no code reads it",
        "`research/escalation.md`",
        "never inherits the strong model's pass",
        "`@dataclass(frozen=True) class Cascade`, exported: `cheap: str`, `strong: str`, `signal: str`",
        "`.id` is `f\"{cheap}>{strong}@{signal}\"`",
        "`cheap == strong`, a model ID containing `>` or `@`",
        "`[a-z0-9][a-z0-9._-]*`",
        "`cascades: tuple[Cascade, ...] = ()`, after `slices` (4.2)",
        "one trial of a cascade is one item run through the whole cascade",
        "an `escalated` key on cascade rows only",
        "`select` gains a keyword `cascades=False`",
        "`CASCADE_UNKNOWN_MODEL = \"cascade_unknown_model\"`",
        "priors never admit it",
        "`list_cost = cheap.cost(in, out) + p * strong.cost(in + out, out)`",
        "`p = escalated / trials`",
        "`signals: Mapping[str, Callable[[str], bool]] | None = None`",
        "`select(..., cascades=signals is not None)`",
        "the strong model is called with the same `messages`",
        "`.call_delegated` is unchanged",
        "gains `cascade` (its `id`) and `escalated`",
        "a cascade of more than two models",
    ):
        assert phrase in spec, phrase


def test_the_research_readme_lists_the_note():
    text = RESEARCH_README.read_text(encoding="utf-8")
    assert text.count("| [escalation.md](escalation.md) |") == 1
    assert text.index("| [escalation.md](escalation.md) |") < text.index("| [prior-art.md](prior-art.md) |")
    assert text.count("- `research/escalation.md` is why") == 1


def test_the_changelog_line_names_the_row():
    lines = CHANGELOG.read_text(encoding="utf-8").splitlines()
    mine = [line for line in lines if line.startswith("- v1.532 (")]
    assert len(mine) == 1
    assert "(7, row ESC1a)" in mine[0] and "tests/test_research_escalation.py" in mine[0]
