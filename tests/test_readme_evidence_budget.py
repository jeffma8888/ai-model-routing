"""The README evidence section's size budget (DESIGN 12.8 v1.334 and v1.335; added by v1.337, row DOC19a).

Each measure is the UTF-8 bytes from a heading line, included, through the line before the next
heading of the same or a higher level, each line with its newline: the section runs from its
``## `` line to the next ``## `` line, its opening to its first ``### `` line, and each subsection to
the next ``### `` or ``## `` line. The section is at most 70,000 bytes, its opening at most 8,000,
each routing subsection at most 6,500 and each delegation subsection at most 7,500. Rows DOC19a to
DOC19k trim one subsection each; until a row trims it, a subsection is in ``PENDING`` with its size
at 0b3e142, and is held at most that size, never required at most its cap. The section total is
required only once ``PENDING`` is empty.
"""
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SECTION = "## Evidence: held-out results on public data"
SECTION_CAP, OPENING_CAP = 70_000, 8_000
CAPS = {"routing": 6_500, "delegation": 7_500}
# Every `###` heading of the section and its class; a heading this table lacks fails.
CLASS = {
    "RouterBench": "routing",
    "AutoBench": "routing",
    "AutoBench judges": "routing",
    "tau2-bench": "routing",
    "LiveCodeBench": "routing",
    "LLMRouterBench": "routing",
    "LLM Routing Response Bank": "routing",
    "Delegation on AutoBench": "delegation",
    "Delegation on tau2-bench": "delegation",
    "Delegation on LLMRouterBench": "delegation",
    "Delegation on the LLM Routing Response Bank": "delegation",
}
# The untrimmed subsections and their sizes at 0b3e142 (12.8 v1.334); each of rows DOC19b to DOC19k
# removes one name.
PENDING = {
    "RouterBench": 4_731,
    "AutoBench": 5_078,
    "AutoBench judges": 5_691,
    "tau2-bench": 7_310,
    "LiveCodeBench": 6_194,
    "LLMRouterBench": 8_093,
    "LLM Routing Response Bank": 8_173,
    "Delegation on AutoBench": 13_715,
    "Delegation on LLMRouterBench": 12_881,
    "Delegation on the LLM Routing Response Bank": 11_204,
}


def size(lines):
    return sum(len(line.encode("utf-8")) for line in lines)


def measure(text):
    """The section, its opening and each `###` subsection in order, as (name, bytes) pairs, the
    section first as (None, bytes) and the opening second as ("", bytes)."""
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == SECTION]
    if len(starts) != 1:
        raise ValueError(f"README has {len(starts)} `{SECTION}` lines, not one")
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    body = lines[start:end]
    heads = [i for i, line in enumerate(body) if line.startswith("### ")]
    first = heads[0] if heads else len(body)
    parts = [(None, size(body)), ("", size(body[:first]))]
    for at, upto in zip(heads, heads[1:] + [len(body)]):
        parts.append((body[at][4:].rstrip("\r\n"), size(body[at:upto])))
    return parts


def problems(text, classes=CLASS, pending=PENDING):
    """Every way `text` breaks the budget, as messages; empty when it keeps it."""
    parts = measure(text)
    (_, section), (_, opening), subsections = parts[0], parts[1], parts[2:]
    found = []
    if opening > OPENING_CAP:
        found.append(f"the opening is {opening:,} bytes, over {OPENING_CAP:,}")
    names = [name for name, _ in subsections]
    if len(set(names)) != len(names):
        found.append("a `###` heading of the section appears twice")
    for name in pending:
        if name not in names:
            found.append(f"PENDING names `{name}`, which is no `###` heading of the section")
    for name, got in subsections:
        if name not in classes:
            found.append(f"`### {name}` has no class in CLASS")
            continue
        cap = CAPS[classes[name]]
        if name in pending:
            if got > pending[name]:
                found.append(f"`### {name}` is {got:,} bytes, over its pending size {pending[name]:,}")
        elif got > cap:
            found.append(f"`### {name}` is {got:,} bytes, over its {classes[name]} cap {cap:,}")
    if not pending and section > SECTION_CAP:
        found.append(f"the section is {section:,} bytes, over {SECTION_CAP:,}")
    return found


def test_the_readme_keeps_the_budget():
    assert problems(README.read_text(encoding="utf-8")) == []


def test_the_tables_name_every_heading_once_and_pending_names_only_headings():
    names = [name for name, _ in measure(README.read_text(encoding="utf-8"))[2:]]
    assert names == list(CLASS)
    assert set(PENDING) <= set(CLASS)
    assert set(CLASS.values()) == set(CAPS)


def test_delegation_on_tau2_bench_is_trimmed():
    # Row DOC19a: out of PENDING and at most its cap (14,187 bytes at 0b3e142).
    sizes = dict(measure(README.read_text(encoding="utf-8"))[2:])
    assert "Delegation on tau2-bench" not in PENDING
    assert sizes["Delegation on tau2-bench"] <= CAPS["delegation"]


def test_each_measure_runs_from_its_heading_to_the_next_of_its_level_or_higher():
    text = ("# Title\n\nintro\n\n## Evidence: held-out results on public data\n\nopen\n\n"
            "### A\n\nab\n\n### B\n\nc\u00e9\n\n## Next\n\nend\n")
    assert measure(text) == [
        (None, len("## Evidence: held-out results on public data\n\nopen\n\n### A\n\nab\n\n### B\n\nc\u00e9\n\n".encode())),
        ("", len("## Evidence: held-out results on public data\n\nopen\n\n")),
        ("A", len("### A\n\nab\n\n")),
        ("B", len("### B\n\nc\u00e9\n\n".encode())),
    ]
    # The last section runs to the end of the text, and the e-acute counts two bytes.
    assert measure("## Evidence: held-out results on public data\n### C\n\u00e9\n")[2] == ("C", 9)


def small(opening=1, a=1, b=1, extra=""):
    return (f"## Evidence: held-out results on public data\n{'o' * opening}\n### A\n{'a' * a}\n"
            f"### B\n{'b' * b}\n{extra}## Next\n")


SMALL = {"A": "routing", "B": "delegation"}


@pytest.mark.parametrize("text, pending, message", [
    (small(opening=8_000), {}, "the opening is 8,046 bytes, over 8,000"),  # 45 + 8,001
    (small(a=6_500), {}, "`### A` is 6,507 bytes, over its routing cap 6,500"),
    (small(b=7_500), {}, "`### B` is 7,507 bytes, over its delegation cap 7,500"),
    (small(a=101), {"A": 107}, "`### A` is 108 bytes, over its pending size 107"),
    (small(), {"C": 10}, "PENDING names `C`, which is no `###` heading of the section"),
    (small(extra="### D\nd\n"), {}, "`### D` has no class in CLASS"),
    (small(extra="### A\na\n"), {}, "a `###` heading of the section appears twice"),
    (small(a=34_000, b=34_000, opening=2_000), {}, None),
])
def test_a_broken_budget_is_named(text, pending, message):
    found = problems(text, classes=SMALL, pending=pending)
    if message is None:
        # Over its own caps too, but the section total is named as well, since PENDING is empty.
        assert found[-1].startswith("the section is ") and found[-1].endswith(", over 70,000")
    else:
        assert message in found


def test_the_section_total_waits_for_an_empty_pending_and_a_pending_one_may_exceed_its_cap():
    text = small(a=36_000, b=36_000)
    found = problems(text, classes=SMALL, pending={"A": 36_007, "B": 36_007})
    assert found == []
    assert problems(small(a=6_493, b=7_493), classes=SMALL, pending={}) == []


def test_a_readme_without_the_section_is_an_error():
    with pytest.raises(ValueError, match="has 0 `## Evidence"):
        measure("# Title\n\n## Other\n")
