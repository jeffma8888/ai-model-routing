"""The README evidence section's size budget (DESIGN 12.8 v1.334 and v1.335; added by v1.337, row DOC19a).

Each measure is the UTF-8 bytes from a heading line, included, through the line before the next
heading of the same or a higher level, each line with its newline: the section runs from its
``## `` line to the next ``## `` line, its opening to its first ``### `` line, and each subsection to
the next ``### `` or ``## `` line. The section is at most 70,000 bytes, its opening at most 7,500,
each routing subsection at most 5,000 and each delegation subsection at most 5,500 (8,000, 6,500 and
7,500 to v1.443), the opening cap raised to 7,862 by v1.452 (row E24c) for the registry pair's Results at a
glance bullet. Rows DOC19a to
DOC19k trim one subsection each; until a row trims it, a subsection is in ``PENDING`` with its size
at 0b3e142, and is held at most that size, never required at most its cap. The section total is
required only once ``PENDING`` is empty.

DESIGN 12.8 v1.344 (row DOC20): 12.8 itself, measured the same way from its ``### 12.8 `` line to
the next ``#``, ``##`` or ``###`` line, is at most ``DESIGN_12_8_CEILINGS[len(PENDING)]``; the row
that removes a ``PENDING`` name adds the entry for the new count, the size its trim leaves, and an
entry for a smaller count is smaller, so 12.8 shrinks with each trim.

DESIGN 12.8 v1.444 (row DOC28a): each part over its v1.444 cap at ce21e81 was put in ``HELD`` with its
size there (the opening as ``""``), held at most that size until its row (DOC28b to DOC28h) trims it; a held
entry at or under its cap fails, so its row removes it, and while ``HELD`` is not empty the projection,
each held part at its cap and the rest as they are, is at most ``PROJECTED_CAP``, 63,000 bytes. A row that
trims a part moves its entry to ``TRIMMED`` (the opening, v1.445, row DOC28b; ``LLMRouterBench``, v1.446,
row DOC28c; ``LLM Routing Response Bank``, v1.447, row DOC28d; ``Delegation on AutoBench``, v1.448, row
DOC28e; ``Delegation on LLMRouterBench``, v1.449, row DOC28f; ``Delegation on the LLM Routing Response
Bank``, v1.450, row DOC28g; ``tau2-bench``, v1.451, row DOC28h), so the two hold the plan. v1.451 emptied
``HELD``, so the projection is the section itself, and it is held at most ``PROJECTED_CAP`` while ``CLASS``
names ``ROOM_HEADINGS`` (eleven) headings, so the room is kept for a twelfth subsection.

DESIGN 12.8 v1.452 (row E24c): ``Registry pair`` is that twelfth heading, so ``CLASS`` names twelve and the
hold is lifted; the section is over ``PROJECTED_CAP`` and at most ``SECTION_CAP``, and the hold is checked on
the README without the new subsection and its glance bullet (``eleven``). ``OPENING_CAP`` rose by that
bullet's line and newline, 362 bytes, to 7,862, at most the 8,000 the room bullet allows.

DESIGN 12.8 v1.454 (row DOC41, review iter-314 should-fix 3): the figures the 12.8 size-budget bullet and
room bullet state, the section, opening and subsection caps, the count of routing and delegation
subsections, the 8,000 ceiling, the ordinal of the registry pair's heading, the hold, the glance bullet's
bytes and the raised cap, are each this module's constant or the README's measure (``stated_problems``).

DESIGN 12.8 v1.473 (row DOC44a): the caps fall to 4,600 (routing) and 5,000 (delegation) so a thirteenth subsection,
the registry-pair delegation one (row E25e), fits with its glance bullet. ``HELD`` holds the ten parts over them at
their a531339 sizes until rows DOC44b to DOC44j trim each to its cap and move it to ``RETRIMMED``; while ``HELD`` is
not empty the projection is at most ``HOLD_CAP``, 64,500 bytes, and once it is empty the section itself is, while
``CLASS`` names twelve headings. ``TRIMMED`` keeps the v1.444 plan, each part at most its ``V1_444_CAPS`` cap.
"""
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
SECTION = "## Evidence: held-out results on public data"
SECTION_CAP, OPENING_CAP = 70_000, 7_862  # the opening 8,000 to v1.443, 7,500 to v1.451
# v1.452 (row E24c): the room bullet raises the opening cap by the registry pair's Results at a glance
# bullet, its line and newline, to at most 8,000.
BASE_OPENING_CAP, GLANCE_BULLET = 7_500, "- [Registry pair](#registry-pair): "
OPENING_CEILING = 8_000  # v1.444: the row that adds the next subsection may raise the opening cap to this
CAPS = {"routing": 4_600, "delegation": 5_000}  # 5,000 and 5,500 to v1.472, 6,500 and 7,500 to v1.443
V1_444_CAPS = {"routing": 5_000, "delegation": 5_500}  # the v1.444 plan's caps, which each TRIMMED part met
# Every `###` heading of the section and its class; a heading this table lacks fails.
CLASS = {
    "RouterBench": "routing",
    "AutoBench": "routing",
    "AutoBench judges": "routing",
    "tau2-bench": "routing",
    "LiveCodeBench": "routing",
    "LLMRouterBench": "routing",
    "LLM Routing Response Bank": "routing",
    "Registry pair": "routing",  # v1.452, row E24c, the twelfth heading
    "Delegation on AutoBench": "delegation",
    "Delegation on tau2-bench": "delegation",
    "Delegation on LLMRouterBench": "delegation",
    "Delegation on the LLM Routing Response Bank": "delegation",
}
# The untrimmed subsections and their sizes at 0b3e142 (12.8 v1.334); each of rows DOC19b to DOC19k
# removed one name, the last (`RouterBench`, 4,731 bytes) v1.373, row DOC19k, so the section total is
# now required.
PENDING = {}
# DESIGN 12.8 v1.444 (row DOC28a): each part still over its v1.444 cap and its size at ce21e81; empty from
# v1.451 (row DOC28h). With the opening's 427, LLMRouterBench's 1,469, LLM Routing Response Bank's 1,462,
# Delegation on AutoBench's 1,199, Delegation on LLMRouterBench's 880, Delegation on the LLM Routing Response
# Bank's 867 and tau2-bench's 776 (TRIMMED) the ce21e81 projection is 69,678 - 7,080 = 62,598.
# v1.473 (row DOC44a): each part over the v1.473 caps and its size at a531339, until its row trims it.
HELD = {"AutoBench": 4_664, "AutoBench judges": 4_742, "tau2-bench": 4_993, "LiveCodeBench": 4_929,
        "LLMRouterBench": 4_993, "LLM Routing Response Bank": 4_997, "Registry pair": 4_957,
        "Delegation on AutoBench": 5_499, "Delegation on LLMRouterBench": 5_494,
        "Delegation on the LLM Routing Response Bank": 5_498}
# The row that trims each held part (v1.473); it moves the part to RETRIMMED as (its a531339 size, its row).
PLAN_ROWS = {"AutoBench": "DOC44b", "AutoBench judges": "DOC44b", "tau2-bench": "DOC44c", "LiveCodeBench": "DOC44d",
             "LLMRouterBench": "DOC44e", "LLM Routing Response Bank": "DOC44f", "Registry pair": "DOC44g",
             "Delegation on AutoBench": "DOC44h", "Delegation on LLMRouterBench": "DOC44i",
             "Delegation on the LLM Routing Response Bank": "DOC44j"}
RETRIMMED = {}
# v1.473: the section at a531339, and with each held part at its cap; HOLD_CAP leaves room under SECTION_CAP for
# a subsection at the delegation cap and GLANCE_ROOM bytes for its glance bullet, its line and newline.
PLAN_SECTION, PLAN_PROJECTION, HOLD_CAP, GLANCE_ROOM = 67_878, 64_312, 64_500, 500
# Each part a DOC28 row has trimmed, with its ce21e81 size and its row: out of HELD, at most its cap.
TRIMMED = {"": (7_927, "DOC28b"), "LLMRouterBench": (6_469, "DOC28c"),
           "LLM Routing Response Bank": (6_462, "DOC28d"), "Delegation on AutoBench": (6_699, "DOC28e"),
           "Delegation on LLMRouterBench": (6_380, "DOC28f"),
           "Delegation on the LLM Routing Response Bank": (6_367, "DOC28g"), "tau2-bench": (5_776, "DOC28h")}
PROJECTED_CAP = 63_000
# v1.451 (row DOC28h): with HELD empty the section itself is at most PROJECTED_CAP while CLASS names this
# many headings, the eleven of ce21e81, so the room is for a twelfth. The check is `==`, not `<=` (review
# iter-313 nit 2, kept at v1.464): `<=` would also bind the two-heading SMALL texts over 63,000 that
# test_a_broken_budget_is_named and the pending-total test use, and since the room is spent it binds only
# the eleven-heading replay of eleven().
ROOM_HEADINGS = 11
DESIGN = ROOT / "DESIGN.md"
DESIGN_12_8 = "### 12.8 "
SAME_OR_HIGHER = re.compile(r"#{1,3} ")
# DESIGN 12.8 v1.344: the ceiling on 12.8 in bytes for each count of PENDING names. The row that removes
# a PENDING name adds the entry for the new count, the size its trim leaves (v1.344: 98,443 bytes; v1.345,
# from review, 99,206, its size after the review's clauses; v1.346, row DOC20a, 96,239; v1.347,
# from review, 96,365; for 9 names, v1.348, row DOC19b, 96,312; for 8 names, v1.350, row DOC19c, 95,933,
# and v1.352, from review, 96,008; for 7 names, v1.353, row DOC19d, 95,632; for 6 names, v1.355,
# row DOC19e, 95,561, and v1.357, from review, 95,620; for 5 names, v1.358, row DOC19f, 95,429;
# for 4 names, v1.362, row DOC19g, 95,282; for 3 names, v1.365, row DOC19h, 95,193; for 2 names,
# v1.368, row DOC19i, 94,685; for 1 name, v1.370, row DOC19j, 94,563; for 0 names, v1.372, row DOC19k,
# 94,335; lowered to the size each part of the DESIGN 12 v1.386 trim leaves, v1.388, row DOC21m,
# 90,830, v1.389, row DOC21n, 84,351, and v1.390, row DOC21o, 45,002; raised by v1.444, row DOC28a, for
# its room bullet to 46,992; raised by v1.452, row E24c, for the registry pair to 47,609; raised by v1.473, row
# DOC44a, for its plan bullet to 49,016, the entry in force).
DESIGN_12_8_CEILINGS = {0: 49_016, 1: 94_563, 2: 94_685, 3: 95_193, 4: 95_282, 5: 95_429, 6: 95_620, 7: 95_632, 8: 96_008,
                        9: 96_312, 10: 96_365}


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


def projection(parts, classes=CLASS, held=HELD, opening_cap=OPENING_CAP, caps=CAPS):
    """The section's bytes with each held part cut to its cap and the rest as they are (v1.444)."""
    over = 0
    for name, got in parts[1:]:
        if name in held and (name == "" or name in classes):
            over += max(0, got - (opening_cap if name == "" else caps[classes[name]]))
    return parts[0][1] - over


def problems(text, classes=CLASS, pending=PENDING, held=HELD, caps=CAPS, hold_cap=HOLD_CAP):
    """Every way `text` breaks the budget, as messages; empty when it keeps it."""
    parts = measure(text)
    (_, section), (_, opening), subsections = parts[0], parts[1], parts[2:]
    found = []
    if "" in held:
        if opening > held[""]:
            found.append(f"the opening is {opening:,} bytes, over its held size {held['']:,}")
        elif opening <= OPENING_CAP:
            found.append(f"the opening is {opening:,} bytes, at or under its cap {OPENING_CAP:,}: remove it from HELD")
    elif opening > OPENING_CAP:
        found.append(f"the opening is {opening:,} bytes, over {OPENING_CAP:,}")
    names = [name for name, _ in subsections]
    if len(set(names)) != len(names):
        found.append("a `###` heading of the section appears twice")
    for name in pending:
        if name not in names:
            found.append(f"PENDING names `{name}`, which is no `###` heading of the section")
    for name in held:
        if name and name not in names:
            found.append(f"HELD names `{name}`, which is no `###` heading of the section")
    for name, got in subsections:
        if name not in classes:
            found.append(f"`### {name}` has no class in CLASS")
            continue
        cap = caps[classes[name]]
        if name in pending:
            if got > pending[name]:
                found.append(f"`### {name}` is {got:,} bytes, over its pending size {pending[name]:,}")
        elif name in held:
            if got > held[name]:
                found.append(f"`### {name}` is {got:,} bytes, over its held size {held[name]:,}")
            elif got <= cap:
                found.append(f"`### {name}` is {got:,} bytes, at or under its {classes[name]} cap {cap:,}: "
                             "remove it from HELD")
        elif got > cap:
            found.append(f"`### {name}` is {got:,} bytes, over its {classes[name]} cap {cap:,}")
    if not pending and section > SECTION_CAP:
        found.append(f"the section is {section:,} bytes, over {SECTION_CAP:,}")
    if held and projection(parts, classes, held, caps=caps) > hold_cap:
        found.append(f"with each held part at its cap the section would be "
                     f"{projection(parts, classes, held, caps=caps):,} bytes, over {hold_cap:,}")
    elif not held and len(classes) == ROOM_HEADINGS and section > PROJECTED_CAP:
        found.append(f"the section is {section:,} bytes, over {PROJECTED_CAP:,} while CLASS names {ROOM_HEADINGS} "
                     "headings")
    elif not held and len(classes) == ROOM_HEADINGS + 1 and section > hold_cap:  # v1.473
        found.append(f"the section is {section:,} bytes, over {hold_cap:,} while CLASS names {ROOM_HEADINGS + 1} "
                     "headings")
    return found


def design_12_8(text):
    """The UTF-8 bytes of DESIGN 12.8: its `### 12.8 ` line, included, through the line before the
    next heading of the same or a higher level (or the end of the text), each line with its newline."""
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.startswith(DESIGN_12_8)]
    if len(starts) != 1:
        raise ValueError(f"DESIGN.md has {len(starts)} `{DESIGN_12_8.strip()}` lines, not one")
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines)) if SAME_OR_HIGHER.match(lines[i])), len(lines))
    return size(lines[start:end])


def design_problems(text, ceilings=DESIGN_12_8_CEILINGS, pending=PENDING):
    """Every way DESIGN.md `text` breaks the 12.8 ceiling rule, as messages; empty when it keeps it."""
    found = []
    counts = sorted(ceilings)
    for smaller, larger in zip(counts, counts[1:]):
        if ceilings[smaller] >= ceilings[larger]:
            found.append(f"the 12.8 ceiling for {smaller} PENDING names, {ceilings[smaller]:,}, is not below "
                         f"the one for {larger}, {ceilings[larger]:,}")
    count, got = len(pending), design_12_8(text)
    if count not in ceilings:
        # v1.345, from review: the message gives 12.8's size, the entry the trimming row adds.
        found.append(f"no 12.8 ceiling for {count} PENDING names: the row that removed a name adds one "
                     f"(12.8 is {got:,} bytes)")
    else:
        if got > ceilings[count]:
            found.append(f"DESIGN 12.8 is {got:,} bytes, over its ceiling {ceilings[count]:,} for {count} PENDING names")
    return found


def pad_12_8(text, extra):
    """`text` with `extra` bytes more in 12.8, at the start of the line after its heading."""
    head = text.index("\n" + DESIGN_12_8) + 1
    after = text.index("\n", head) + 1
    return text[:after] + "x" * extra + text[after:]


def limit(name):
    """A subsection's ceiling: its held size while `HELD` names it (v1.444), else its cap."""
    return HELD.get(name, CAPS[CLASS[name]])


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
    assert sizes["Delegation on tau2-bench"] <= limit("Delegation on tau2-bench")


def test_delegation_on_autobench_is_trimmed():
    # Row DOC19b: out of PENDING and at most its cap (13,715 bytes at 0b3e142).
    sizes = dict(measure(README.read_text(encoding="utf-8"))[2:])
    assert "Delegation on AutoBench" not in PENDING
    assert sizes["Delegation on AutoBench"] <= limit("Delegation on AutoBench")


def test_delegation_on_llmrouterbench_is_trimmed():
    # Row DOC19c: out of PENDING and at most its cap (12,881 bytes at 0b3e142).
    sizes = dict(measure(README.read_text(encoding="utf-8"))[2:])
    assert "Delegation on LLMRouterBench" not in PENDING
    assert sizes["Delegation on LLMRouterBench"] <= limit("Delegation on LLMRouterBench")


def test_delegation_on_the_response_bank_is_trimmed():
    # Row DOC19d: out of PENDING and at most its cap (11,204 bytes at 0b3e142).
    sizes = dict(measure(README.read_text(encoding="utf-8"))[2:])
    assert "Delegation on the LLM Routing Response Bank" not in PENDING
    assert sizes["Delegation on the LLM Routing Response Bank"] <= limit("Delegation on the LLM Routing Response Bank")


def test_response_bank_is_trimmed():
    # Row DOC19e: out of PENDING and at most its cap (8,173 bytes at 0b3e142).
    sizes = dict(measure(README.read_text(encoding="utf-8"))[2:])
    assert "LLM Routing Response Bank" not in PENDING
    assert sizes["LLM Routing Response Bank"] <= limit("LLM Routing Response Bank")


def test_llmrouterbench_is_trimmed():
    # Row DOC19f: out of PENDING and at most its cap (8,093 bytes at 0b3e142).
    sizes = dict(measure(README.read_text(encoding="utf-8"))[2:])
    assert "LLMRouterBench" not in PENDING
    assert sizes["LLMRouterBench"] <= limit("LLMRouterBench")


def test_tau2_bench_is_trimmed():
    # Row DOC19g: out of PENDING and at most its cap (7,310 bytes at 0b3e142).
    sizes = dict(measure(README.read_text(encoding="utf-8"))[2:])
    assert "tau2-bench" not in PENDING
    assert sizes["tau2-bench"] <= limit("tau2-bench")


def test_livecodebench_is_trimmed():
    # Row DOC19h: out of PENDING and at most its cap (6,194 bytes at 0b3e142, under its cap already).
    sizes = dict(measure(README.read_text(encoding="utf-8"))[2:])
    assert "LiveCodeBench" not in PENDING
    assert sizes["LiveCodeBench"] <= limit("LiveCodeBench")


def test_autobench_judges_is_trimmed():
    # Row DOC19i: out of PENDING and at most its cap (5,691 bytes at 0b3e142, under its cap already).
    sizes = dict(measure(README.read_text(encoding="utf-8"))[2:])
    assert "AutoBench judges" not in PENDING
    assert sizes["AutoBench judges"] <= limit("AutoBench judges")


def test_autobench_is_trimmed():
    # Row DOC19j: out of PENDING and at most its cap (5,078 bytes at 0b3e142, under its cap already).
    sizes = dict(measure(README.read_text(encoding="utf-8"))[2:])
    assert "AutoBench" not in PENDING
    assert sizes["AutoBench"] <= limit("AutoBench")


def test_routerbench_is_trimmed_and_the_section_total_is_required():
    # Row DOC19k: out of PENDING and at most its cap (4,731 bytes at 0b3e142, under its cap already);
    # with PENDING empty, the section is held at most 70,000 bytes.
    parts = measure(README.read_text(encoding="utf-8"))
    sizes = dict(parts[2:])
    assert PENDING == {}
    assert sizes["RouterBench"] <= limit("RouterBench")
    assert parts[0][1] <= SECTION_CAP


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
    (small(opening=7_862), {}, "the opening is 7,908 bytes, over 7,862"),  # 45 + 7,863 (7,500 to v1.451)
    (small(a=4_600), {}, "`### A` is 4,607 bytes, over its routing cap 4,600"),  # 5,000 and 5,500 to v1.472
    (small(b=5_000), {}, "`### B` is 5,007 bytes, over its delegation cap 5,000"),
    (small(a=101), {"A": 107}, "`### A` is 108 bytes, over its pending size 107"),
    (small(), {"C": 10}, "PENDING names `C`, which is no `###` heading of the section"),
    (small(extra="### D\nd\n"), {}, "`### D` has no class in CLASS"),
    (small(extra="### A\na\n"), {}, "a `###` heading of the section appears twice"),
    (small(a=34_000, b=34_000, opening=2_000), {}, None),
])
def test_a_broken_budget_is_named(text, pending, message):
    found = problems(text, classes=SMALL, pending=pending, held={})
    if message is None:
        # Over its own caps too, but the section total is named as well, since PENDING is empty.
        assert found[-1].startswith("the section is ") and found[-1].endswith(", over 70,000")
    else:
        assert message in found


def test_the_section_total_waits_for_an_empty_pending_and_a_pending_one_may_exceed_its_cap():
    text = small(a=36_000, b=36_000)
    found = problems(text, classes=SMALL, pending={"A": 36_007, "B": 36_007}, held={})
    assert found == []
    assert problems(small(a=4_593, b=4_993), classes=SMALL, pending={}, held={}) == []


def test_a_readme_without_the_section_is_an_error():
    with pytest.raises(ValueError, match="has 0 `## Evidence"):
        measure("# Title\n\n## Other\n")


def test_design_12_8_keeps_its_ceiling():
    assert design_problems(DESIGN.read_text(encoding="utf-8")) == []


def test_one_byte_over_the_ceiling_in_design_12_8_fails():
    # While the present entry is 12.8's size, as at v1.344, the padding is one byte.
    text = DESIGN.read_text(encoding="utf-8")
    ceiling = DESIGN_12_8_CEILINGS[len(PENDING)]
    at_ceiling = pad_12_8(text, ceiling - design_12_8(text))
    assert design_12_8(at_ceiling) == ceiling and design_problems(at_ceiling) == []
    over = pad_12_8(text, ceiling - design_12_8(text) + 1)
    assert design_problems(over) == [
        f"DESIGN 12.8 is {ceiling + 1:,} bytes, over its ceiling {ceiling:,} for {len(PENDING)} PENDING names"]


def test_the_12_8_measure_runs_to_the_next_heading_of_its_level_or_higher():
    text = "# T\n## 12. S\n### 12.7 A\na\n### 12.8 B\nb\u00e9\n#### C\nc\n\n### 12.9 D\nd\n"
    assert design_12_8(text) == len("### 12.8 B\nb\u00e9\n#### C\nc\n\n".encode())
    assert design_12_8(text.replace("### 12.9", "## 13.")) == design_12_8(text)
    assert design_12_8("### 12.8 B\nb\n") == len("### 12.8 B\nb\n")
    for bad in ("### 12.7 A\n", "### 12.8 B\n### 12.8 B\n"):
        with pytest.raises(ValueError, match="`### 12.8` lines, not one"):
            design_12_8(bad)


def test_a_broken_12_8_ceiling_table_is_named():
    text = "### 12.8 B\n" + "b" * 99 + "\n"  # 111 bytes
    assert design_problems(text, ceilings={2: 111}, pending={"A": 1, "B": 1}) == []
    assert design_problems(text, ceilings={2: 110}, pending={"A": 1, "B": 1}) == [
        "DESIGN 12.8 is 111 bytes, over its ceiling 110 for 2 PENDING names"]
    assert design_problems(text, ceilings={2: 111}, pending={"A": 1}) == [
        "no 12.8 ceiling for 1 PENDING names: the row that removed a name adds one (12.8 is 111 bytes)"]
    # Both faults at once: the table and the missing count are named, with the size to set.
    assert design_problems(text, ceilings={2: 100, 3: 100}, pending={"A": 1}) == [
        "the 12.8 ceiling for 2 PENDING names, 100, is not below the one for 3, 100",
        "no 12.8 ceiling for 1 PENDING names: the row that removed a name adds one (12.8 is 111 bytes)"]
    assert design_problems(text, ceilings={1: 111, 2: 111}, pending={"A": 1}) == [
        "the 12.8 ceiling for 1 PENDING names, 111, is not below the one for 2, 111"]
    assert design_problems(text, ceilings={1: 111, 2: 112}, pending={"A": 1}) == []


def test_the_12_8_clause_states_the_ceiling_in_force():
    # DESIGN 12.8 v1.390 (row DOC21o): the shrink bullet gives the entry for 0 names, the one in force,
    # raised by v1.444 (row DOC28a) for its room bullet.
    text = DESIGN.read_text(encoding="utf-8")
    lines = [line for line in text.splitlines() if line.startswith("  - 12.8 shrinks with each trim (v1.344, row DOC20): ")]
    assert len(lines) == 1
    # v1.452 (row E24c): raised again, for the registry pair's subsection, its at-a-glance bullet and opening cap.
    # v1.473 (row DOC44a): raised again, for the plan bullet that makes room for a thirteenth subsection.
    stated = re.findall(r"The entry in force, for 0 names, is this section's size after v1\.473 \(row DOC44a\), "
                        r"([\d,]+) bytes \(47,609 after v1\.452, row E24c, 46,992 after v1\.444, row DOC28a, and 45,002 "
                        r"after v1\.390, row DOC21o\); ", lines[0])
    assert len(stated) == 1 and int(stated[0].replace(",", "")) == DESIGN_12_8_CEILINGS[0]
    assert PENDING == {} and design_12_8(text) <= DESIGN_12_8_CEILINGS[0] <= 50_000


def test_held_is_empty_and_the_room_bullet_names_each_trim():
    # Row DOC28a (v1.444): every held part was the opening or a heading, over its v1.444 cap at ce21e81 at
    # the size held, and the 12.8 room bullet gave each name and size. v1.445 (row DOC28b) to v1.451 (row
    # DOC28h) each moved one entry to TRIMMED; v1.451 emptied HELD, and the bullet says so, names each row
    # and version, and names the section hold that follows.
    # v1.473 (row DOC44a): HELD holds the next plan (test_the_v1_473_plan_holds_each_part_over_the_new_caps), so
    # the v1.444 plan is read from TRIMMED, all seven of its parts.
    assert len(TRIMMED) == 7 and ROOM_HEADINGS == 11 and len(CLASS) == 12
    lines = [line for line in DESIGN.read_text(encoding="utf-8").splitlines()
             if line.startswith("  - Room for one more subsection (v1.444, row DOC28a): ")]
    assert len(lines) == 1
    assert "`HELD` held each part over its cap at its ce21e81 size and is empty from v1.451 to v1.472. " in lines[0]
    assert (f"is at most {PROJECTED_CAP:,} bytes ({HOLD_CAP:,} from v1.473, the next bullet); once it is empty, the "
            "section itself is, while `CLASS` names eleven headings (v1.451). ") in lines[0]
    assert "at ce21e81 the section is 69,678 bytes and its opening 7,927, " in lines[0]
    assert ("Rows DOC28b (the opening, v1.445), DOC28c (`LLMRouterBench`, v1.446), DOC28d (`LLM Routing Response "
            "Bank`, v1.447), DOC28e (`Delegation on AutoBench`, v1.448), DOC28f (`Delegation on LLMRouterBench`, "
            "v1.449), DOC28g (`Delegation on the LLM Routing Response Bank`, v1.450) and DOC28h (`tau2-bench`, "
            "v1.451) trimmed one part each.") in lines[0]
    # v1.447 (row DOC28d, review iter-306 nit 1): the bullet names TRIMMED, where a held entry's row moves it.
    assert "a held entry at or under its cap fails (its row moves it to `TRIMMED`, which v1.445 added), " in lines[0]
    # v1.446 (row DOC28c): a part whose pair does not fit with the second shed keeps its second instead.
    assert "then its second Reading-it bullet (its first instead where only that fits, v1.446), " in lines[0]


def test_trimmed_parts_are_out_of_held_and_at_most_their_caps():
    # Row DOC28b (v1.445): the opening, 7,927 bytes at ce21e81, is at most its 7,500-byte cap and out of
    # HELD; row DOC28c (v1.446): so is `LLMRouterBench`, 6,469 there, at most its 5,000-byte routing cap;
    # row DOC28d (v1.447): so is `LLM Routing Response Bank`, 6,462 there, at most the same cap; row DOC28e
    # (v1.448): so is `Delegation on AutoBench`, 6,699 there, at most its 5,500-byte delegation cap; row
    # DOC28f (v1.449): so is `Delegation on LLMRouterBench`, 6,380 there, at most the same cap; row DOC28g
    # (v1.450): so is `Delegation on the LLM Routing Response Bank`, 6,367 there, at most the same cap; row
    # DOC28h (v1.451): so is `tau2-bench`, 5,776 there, at most its 5,000-byte routing cap.
    # HELD and TRIMMED together are the seven parts of the v1.444 plan, each over its cap there.
    parts = measure(README.read_text(encoding="utf-8"))
    sizes = dict(parts[1:])
    assert TRIMMED == {"": (7_927, "DOC28b"), "LLMRouterBench": (6_469, "DOC28c"),
                       "LLM Routing Response Bank": (6_462, "DOC28d"),
                       "Delegation on AutoBench": (6_699, "DOC28e"),
                       "Delegation on LLMRouterBench": (6_380, "DOC28f"),
                       "Delegation on the LLM Routing Response Bank": (6_367, "DOC28g"),
                       "tau2-bench": (5_776, "DOC28h")}
    # v1.473 (row DOC44a): six of them are held again, under the lower caps; each stays at most its v1.444 cap.
    assert len(TRIMMED) == 7
    for name, (was, _) in TRIMMED.items():
        cap = OPENING_CAP if name == "" else V1_444_CAPS[CLASS[name]]
        assert was > cap >= sizes[name]


def test_the_projection_has_room_for_the_largest_subsection():
    # v1.444: with each held part at its cap the section leaves room under 70,000 for a subsection the
    # size of the largest at ce21e81 (`Delegation on AutoBench`, 6,699 bytes).
    # v1.451 (row DOC28h): with HELD empty the projection is the section, held only while CLASS names
    # ROOM_HEADINGS headings (test_the_section_keeps_the_room_while_class_names_eleven_headings).
    # v1.452 (row E24c, review nit): the room is spent, so the hold no longer binds the real README; the
    # projection is the section itself, over PROJECTED_CAP and at most SECTION_CAP, and the hold is checked
    # on the README without the new subsection in the room test above.
    # v1.473 (row DOC44a): HELD holds the next plan, so the projection is at most HOLD_CAP; the v1.444 replay
    # reads TRIMMED alone, at the v1.444 caps.
    parts = measure(README.read_text(encoding="utf-8"))
    assert PROJECTED_CAP <= SECTION_CAP - 6_699
    assert PROJECTED_CAP < projection(parts) <= HOLD_CAP < parts[0][1] <= SECTION_CAP
    assert projection(measure(eleven(README.read_text(encoding="utf-8"))[0]), held={}) <= PROJECTED_CAP
    # ce21e81 itself: 69,678 bytes less the 7,080 its seven held parts (TRIMMED) were over their caps.
    plan = {name: was for name, (was, _) in TRIMMED.items()}
    # The opening at its v1.444 cap, 7,500, which v1.452 (row E24c) raised for the registry pair's bullet.
    assert projection([(None, 69_678)] + list(plan.items()), held=plan, opening_cap=BASE_OPENING_CAP,
                      caps=V1_444_CAPS) == 62_598


def eleven(text):
    """The README `text` without the `### Registry pair` subsection and its glance bullet, and CLASS without
    its name: the eleven headings of v1.451 (row E24c, v1.452)."""
    start = text.index("\n### Registry pair\n") + 1
    end = text.index("\n### ", start) + 1
    lines = [line for line in text[:start].split("\n") if not line.startswith(GLANCE_BULLET)]
    return "\n".join(lines) + text[end:], {k: v for k, v in CLASS.items() if k != "Registry pair"}


def test_the_section_keeps_the_room_while_class_names_eleven_headings():
    # v1.451 (row DOC28h): HELD is empty, so the projection is the section itself. The margin is
    # PROJECTED_CAP less the section; one byte more in `### RouterBench` fails the room hold, the only
    # problem named, since the grown subsection stays under its cap (4,800 bytes at v1.451) and the section
    # under 70,000 (review iter-313 nit 1; test_a_broken_hold_is_named has a projection-only failure with a
    # held part), and one byte less passes it. A twelfth heading in CLASS lifts the hold, so the
    # room can be spent on it, the section still at most SECTION_CAP.
    # v1.452 (row E24c): the twelfth is `Registry pair`, so the hold is checked on the README without it.
    # v1.473 (row DOC44a): the replay holds nothing and lifts the caps, so the hold is the one check that can
    # fire: the next plan's trims widen the margin past any one part's room under its cap.
    text, classes = eleven(README.read_text(encoding="utf-8"))
    replay = {"held": {}, "caps": {"routing": SECTION_CAP, "delegation": SECTION_CAP}}
    assert len(classes) == ROOM_HEADINGS
    margin = PROJECTED_CAP - measure(text)[0][1]
    assert margin >= 0 and projection(measure(text), classes, held={}) == measure(text)[0][1]
    grown = text.replace("### RouterBench\n", "### RouterBench\n" + "x" * margin + "\n", 1)
    assert measure(grown)[0][1] == PROJECTED_CAP + 1
    assert problems(grown, classes=classes, **replay) == [f"the section is {PROJECTED_CAP + 1:,} bytes, over "
                                                          f"{PROJECTED_CAP:,} while CLASS names {ROOM_HEADINGS} headings"]
    at = text.replace("### RouterBench\n", "### RouterBench\n" + "x" * (margin - 1) + "\n", 1)
    assert not any("while CLASS names" in found for found in problems(at, classes=classes, **replay))
    twelve = {**classes, "Twelfth": "routing"}
    with_twelfth = grown.replace("\n### RouterBench\n", "\n### Twelfth\n\nx\n\n### RouterBench\n", 1)
    assert PROJECTED_CAP < measure(with_twelfth)[0][1] <= HOLD_CAP
    assert not any("while CLASS names" in found for found in problems(with_twelfth, classes=twelve, **replay))
    assert any("while CLASS names" in found
               for found in problems(with_twelfth.replace("### Twelfth\n", "", 1), classes=classes, **replay))


def test_the_registry_pair_spends_the_room_and_raises_the_opening_cap():
    # v1.452 (row E24c): the twelfth heading lifts the room hold, so the section is over 63,000 and at
    # most 70,000; the opening cap is 7,500 plus the registry pair's glance bullet line and its newline,
    # at most 8,000, and one byte more in the opening fails it.
    text = README.read_text(encoding="utf-8")
    parts = measure(text)
    assert len(CLASS) == ROOM_HEADINGS + 1 and problems(text) == []
    assert PROJECTED_CAP < parts[0][1] <= SECTION_CAP
    bullets = [line for line in text.split("\n") if line.startswith(GLANCE_BULLET)]
    assert len(bullets) == 1
    assert OPENING_CAP == BASE_OPENING_CAP + len((bullets[0] + "\n").encode("utf-8")) <= OPENING_CEILING
    margin = OPENING_CAP - parts[1][1]
    assert margin >= 0
    over = text.replace(GLANCE_BULLET, GLANCE_BULLET + "x" * (margin + 1), 1)
    assert f"the opening is {OPENING_CAP + 1:,} bytes, over {OPENING_CAP:,}" in problems(over)
    assert eleven(text)[0].count(GLANCE_BULLET) == 0 and "### Registry pair" not in eleven(text)[0]


# v1.454 (row DOC41, review iter-314 should-fix 3): the 12.8 sentences whose figures are this module's.
SIZE_BULLET = "- Size budget (v1.334, row DOC19): "
ROOM_BULLET = "  - Room for one more subsection (v1.444, row DOC28a): "
SIZE_STATED = re.compile(r"The budget: the section at most ([\d,]+) bytes, its opening at most ([\d,]+) \(([\d,]+) to "
                         r"v1\.451, the room bullet below\), each routing subsection \(the first (\w+)\) at most "
                         r"([\d,]+) and each delegation subsection \(the last (\w+)\) at most ([\d,]+) ")
CEILING_STATED = re.compile(r"may raise the opening cap by its Results at a glance bullet, to at most ([\d,]+)\. ")
RAISED_STATED = re.compile(r"Row E24c \(v1\.452\) spent the room on `Registry pair`, the (\w+) heading, which lifts "
                           r"the ([\d,]+) hold, and raised `OPENING_CAP` by that bullet's ([\d,]+) bytes, its line and "
                           r"newline, to ([\d,]+)$")
WORDS = {"four": 4, "eight": 8, "eleventh": 11, "twelfth": 12, "thirteenth": 13}


def stated_problems(design, readme, classes=CLASS):
    """Every figure of the 12.8 size-budget and room bullets in DESIGN.md `design` that disagrees with this
    module's constants or the README `readme`, as messages; [] when all agree. The registry pair's heading
    is the one after the ROOM_HEADINGS the room was kept for, a count a later heading does not change; the
    room tests pin len(CLASS) to it today (review iter-317 nit 4)."""
    lines = design.split("\n")
    size_lines = [line for line in lines if line.startswith(SIZE_BULLET)]
    room_lines = [line for line in lines if line.startswith(ROOM_BULLET)]
    if len(size_lines) != 1 or len(room_lines) != 1:
        return [f"DESIGN.md has {len(size_lines)} size-budget and {len(room_lines)} room bullets, not one each"]
    sized = SIZE_STATED.findall(size_lines[0])
    ceiling, raised = CEILING_STATED.findall(room_lines[0]), RAISED_STATED.findall(room_lines[0])
    if [len(sized), len(ceiling), len(raised)] != [1, 1, 1]:
        return [f"the 12.8 budget, ceiling and raised-cap sentences are found {len(sized)}, {len(ceiling)} and "
                f"{len(raised)} times, not once each"]
    bullets = [line for line in readme.split("\n") if line.startswith(GLANCE_BULLET)]
    measured = len((bullets[0] + "\n").encode("utf-8")) if len(bullets) == 1 else None
    kinds = list(classes.values())
    want = {"the section cap": SECTION_CAP, "the opening cap": OPENING_CAP,
            "the opening cap to v1.451": BASE_OPENING_CAP, "the routing count": kinds.count("routing"),
            "the routing cap": CAPS["routing"], "the delegation count": kinds.count("delegation"),
            "the delegation cap": CAPS["delegation"], "the opening ceiling": OPENING_CEILING,
            "the registry pair's heading": ROOM_HEADINGS + 1, "the hold": PROJECTED_CAP,
            "the glance bullet's bytes": measured, "the raised opening cap": OPENING_CAP}
    got = [*sized[0], ceiling[0], *raised[0]]
    found = []
    # strict: a regex that gains or loses a group fails here (review iter-317 nit 3); a word or a form
    # such as `12th` that is neither digits nor in WORDS is named, not raised (nit 2).
    for (label, value), text in zip(want.items(), got, strict=True):
        digits = text.replace(",", "")
        number = int(digits) if digits.isdigit() else WORDS.get(text)
        if number != value:
            found.append(f"12.8 states {label} as {text}, but it is {'none' if value is None else f'{value:,}'}")
    return found


def test_the_12_8_figures_are_the_constants_and_the_readme():
    design, readme = DESIGN.read_text(encoding="utf-8"), README.read_text(encoding="utf-8")
    assert stated_problems(design, readme) == []
    # The glance bullet's 362 bytes are its line and newline, and the raised cap is the base plus them.
    assert OPENING_CAP - BASE_OPENING_CAP == 362 and len(CLASS) == ROOM_HEADINGS + 1


@pytest.mark.parametrize("old, new, message", [
    ("to 7,862", "to 7,863", "12.8 states the raised opening cap as 7,863, but it is 7,862"),
    ("bullet's 362 bytes", "bullet's 361 bytes", "12.8 states the glance bullet's bytes as 361, but it is 362"),
    ("`Registry pair`, the twelfth heading", "`Registry pair`, the eleventh heading",
     "12.8 states the registry pair's heading as eleventh, but it is 12"),
    ("`Registry pair`, the twelfth heading", "`Registry pair`, the 12th heading",
     "12.8 states the registry pair's heading as 12th, but it is 12"),
    ("lifts the 63,000 hold", "lifts the 62,000 hold", "12.8 states the hold as 62,000, but it is 63,000"),
    ("to at most 8,000. ", "to at most 8,100. ", "12.8 states the opening ceiling as 8,100, but it is 8,000"),
    ("its opening at most 7,862 (", "its opening at most 7,500 (", "12.8 states the opening cap as 7,500, but it is 7,862"),
    ("(the first eight)", "(the first seven)", None),
    ("(the last four)", "(the last five)", None),
    ("at most 70,000 bytes, its opening", "at most 69,000 bytes, its opening",
     "12.8 states the section cap as 69,000, but it is 70,000"),
    ("Row E24c (v1.452) spent the room", "Row E24c spent the room",
     "the 12.8 budget, ceiling and raised-cap sentences are found 1, 1 and 0 times, not once each"),
])
def test_a_12_8_figure_that_drifts_is_named(old, new, message):
    design, readme = DESIGN.read_text(encoding="utf-8"), README.read_text(encoding="utf-8")
    assert design.count(old) == 1
    found = stated_problems(design.replace(old, new), readme)
    if message is None:  # a count word outside WORDS, or a wrong one, names its count
        assert len(found) == 1 and found[0].startswith("12.8 states the ") and "count as " in found[0]
    else:
        assert found == [message]


def test_a_changed_glance_bullet_or_class_is_named():
    design, readme = DESIGN.read_text(encoding="utf-8"), README.read_text(encoding="utf-8")
    longer = readme.replace(GLANCE_BULLET, GLANCE_BULLET + "x", 1)
    assert stated_problems(design, longer) == ["12.8 states the glance bullet's bytes as 362, but it is 363"]
    assert stated_problems(design, readme.replace(GLANCE_BULLET, "- [Registry](#registry-pair): ", 1)) == [
        "12.8 states the glance bullet's bytes as 362, but it is none"]
    # A thirteenth routing heading changes the routing count the size-budget bullet states, not the ordinal.
    assert stated_problems(design, readme, classes={**CLASS, "Thirteenth": "routing"}) == [
        "12.8 states the routing count as eight, but it is 9"]


@pytest.mark.parametrize("text, held, message", [
    (small(a=5_050), {"A": 5_100}, None),
    (small(a=5_094), {"A": 5_100}, "`### A` is 5,101 bytes, over its held size 5,100"),
    (small(a=4_593), {"A": 5_100}, "`### A` is 4,600 bytes, at or under its routing cap 4,600: remove it from HELD"),
    (small(), {"C": 10}, "HELD names `C`, which is no `###` heading of the section"),
    (small(opening=7_915), {"": 7_962}, None),  # 45 + 7,916 = 7,961 (7,600 against 7,500 to v1.451)
    (small(opening=7_917), {"": 7_962}, "the opening is 7,963 bytes, over its held size 7,962"),
    (small(opening=7_816), {"": 7_962}, "the opening is 7,862 bytes, at or under its cap 7,862: remove it from HELD"),
    # v1.473: 61 + a + 8,993 less the 4,000 `B` is over its 5,000 cap, against 64,500 (63,000 and 5,500 to v1.472)
    (small(a=59_500, b=8_993), {"B": 9_000}, "with each held part at its cap the section would be 64,554 bytes, over 64,500"),
    (small(a=59_000, b=8_993), {"B": 9_000}, None),
])
def test_a_broken_hold_is_named(text, held, message):
    # A pending `A` lets the last two texts carry a large unheld part without its cap firing; the
    # section total waits for an empty PENDING, so the projection is the one total named.
    pending = {"A": 60_000} if len(text) > 60_000 else {}
    found = problems(text, classes=SMALL, pending=pending, held=held)
    assert found == ([] if message is None else [message])


# v1.464 (row DOC39b, review iter-313 nit 3): `This repo` for `The repo` in three licence bullets grew
# `### tau2-bench` and `### LLMRouterBench` by a byte each, and 12.15 and 12.19 give each size from v1.464.
TRIM_SIZES = {"tau2-bench": ("12.15", "from v1.464 the README subsection `### tau2-bench` is {:,} bytes by the 12.8 "
                                      "measure (4,992 from v1.451, "),
              "LLMRouterBench": ("12.19", "from v1.464 the subsection is {:,} bytes by that measure (4,992 from "
                                          "v1.446, ")}


def design_subsection(text, number):
    """DESIGN.md `text` from its `### <number> ` line to the next `#`, `##` or `###` line (review iter-328
    should-fix 1: each size clause is found in its own subsection, not anywhere in the file)."""
    lines = text.split("\n")
    starts = [i for i, line in enumerate(lines) if line.startswith(f"### {number} ")]
    assert len(starts) == 1, f"DESIGN.md has {len(starts)} `### {number}` lines, not one"
    end = next((i for i in range(starts[0] + 1, len(lines)) if SAME_OR_HIGHER.match(lines[i])), len(lines))
    return "\n".join(lines[starts[0]:end])


def test_the_12_15_and_12_19_trim_bullets_give_the_subsections_size():
    readme, design = README.read_text(encoding="utf-8"), DESIGN.read_text(encoding="utf-8")
    sizes = dict(measure(readme)[1:])
    for name, (number, clause) in TRIM_SIZES.items():
        stated = clause.format(sizes[name])
        assert design.count(stated) == 1 and design_subsection(design, number).count(stated) == 1, name
        assert sizes[name] <= limit(name)  # v1.473: held, until rows DOC44c and DOC44e
    # The 12.15 bullet moved to the end of 12.19 is in the file once but no longer in its own subsection.
    tau2 = TRIM_SIZES["tau2-bench"][1].format(sizes["tau2-bench"])
    line = next(line for line in design.split("\n") if tau2 in line)
    moved = design.replace(line + "\n", "", 1).replace("\n### 12.20 ", "\n" + line + "\n### 12.20 ", 1)
    assert moved.count(tau2) == 1 and design_subsection(moved, "12.15").count(tau2) == 0
    assert design_subsection(moved, "12.19").count(tau2) == 1
    assert readme.count("This repo commits only derived numbers\n") == 3 and "The repo commits" not in readme
    grown = readme.replace("\n### tau2-bench\n", "\n### tau2-bench\nx\n", 1)
    assert design.count(TRIM_SIZES["tau2-bench"][1].format(dict(measure(grown)[1:])["tau2-bench"])) == 0


# v1.473 (row DOC44a): the plan that makes room for a thirteenth subsection.
PLAN_BULLET = "  - Room for a thirteenth subsection (v1.473, row DOC44a): "


def test_the_v1_473_plan_holds_each_part_over_the_new_caps():
    parts = measure(README.read_text(encoding="utf-8"))
    sizes = dict(parts[1:])
    plan = {**{name: was for name, (was, _) in RETRIMMED.items()}, **HELD}
    # Each planned part was over its v1.473 cap at a531339 and has its row; a held part is still over it, and a
    # retrimmed one is at most it. Every other part was, and is, at most its cap, so none is left out.
    assert not set(RETRIMMED) & set(HELD) and set(plan) == set(PLAN_ROWS) and "" not in plan
    assert all(was > CAPS[CLASS[name]] for name, was in plan.items())
    assert all(sizes[name] <= CAPS[CLASS[name]] and row == PLAN_ROWS[name] for name, (_, row) in RETRIMMED.items())
    assert all(got <= CAPS[CLASS[name]] for name, got in sizes.items() if name and name not in plan)
    assert sizes[""] <= OPENING_CAP
    # a531339: 67,878 bytes less the 3,566 its ten held parts are over their caps, at most HOLD_CAP, which leaves
    # room under 70,000 for a subsection at the delegation cap and its glance bullet.
    assert projection([(None, PLAN_SECTION)] + list(plan.items()), held=plan) == PLAN_PROJECTION <= HOLD_CAP
    assert HOLD_CAP == SECTION_CAP - CAPS["delegation"] - GLANCE_ROOM
    assert len(CLASS) == ROOM_HEADINGS + 1 and problems(README.read_text(encoding="utf-8")) == []


def test_the_v1_473_plan_bullet_names_each_part_its_size_and_its_row():
    lines = [line for line in DESIGN.read_text(encoding="utf-8").splitlines() if line.startswith(PLAN_BULLET)]
    assert len(lines) == 1
    plan = {**{name: was for name, (was, _) in RETRIMMED.items()}, **HELD}
    names = list(PLAN_ROWS)
    clauses = []
    for i, name in enumerate(names):
        row = PLAN_ROWS[name]
        last_of_row = i + 1 == len(names) or PLAN_ROWS[names[i + 1]] != row
        tag = f" ({'row ' if row == PLAN_ROWS[names[0]] else ''}{row})" if last_of_row else ""
        clauses.append(f"`{name}` {plan[name]:,}{tag}")
    listed = ", ".join(clauses[:-1]) + " and " + clauses[-1]
    listed = listed.replace("`AutoBench` 4,664, `AutoBench judges`", "`AutoBench` 4,664 and `AutoBench judges`", 1)
    assert f": {listed}. " in lines[0]
    assert (f"The caps fall to {CAPS['routing']:,} (routing) and {CAPS['delegation']:,} (delegation), and `HELD` "
            "holds the ten parts over them at their a531339 sizes ") in lines[0] and len(plan) == 10
    assert (f"at a531339 the section is {PLAN_SECTION:,} bytes, so the registry-pair delegation subsection (row "
            f"E25e) at the {V1_444_CAPS['delegation']:,}-byte delegation cap of v1.444 would take it past "
            f"{SECTION_CAP:,}. ") in lines[0]
    assert (f"While `HELD` is not empty the projection is at most {HOLD_CAP:,} bytes ({PLAN_PROJECTION:,} at "
            "a531339), and once it is empty the section itself is, while `CLASS` names twelve headings: "
            f"{SECTION_CAP:,} less the {CAPS['delegation']:,} delegation cap and {GLANCE_ROOM} bytes for the new "
            "subsection's Results at a glance bullet, its line and newline, by which row E25e may raise the opening "
            "cap. ") in lines[0]
    assert lines[0].endswith("`TRIMMED` keeps the v1.444 plan, each part at most its v1.444 cap")


@pytest.mark.parametrize("held, message", [
    ({**HELD, "Registry pair": 4_956}, "`### Registry pair` is 4,957 bytes, over its held size 4,956"),
    ({k: v for k, v in HELD.items() if k != "AutoBench"}, "`### AutoBench` is 4,664 bytes, over its routing cap 4,600"),
    ({**HELD, "Delegation on tau2-bench": 4_962},
     "`### Delegation on tau2-bench` is 4,962 bytes, at or under its delegation cap 5,000: remove it from HELD"),
])
def test_a_broken_v1_473_plan_is_named(held, message):
    # A held part grown past its held size, a part over its new cap left out of HELD, and a part under its
    # cap put in HELD each fail the README's budget, the only problem named.
    assert problems(README.read_text(encoding="utf-8"), held=held) == [message]


def test_a_large_part_left_out_of_the_v1_473_plan_also_breaks_the_projection():
    # `Delegation on AutoBench` left out is over its cap, and its 499 bytes over are no longer cut from the
    # projection: 64,312 + 499 = 64,811, over HOLD_CAP (`AutoBench`'s 64 stay under it, the case above).
    held = {k: v for k, v in HELD.items() if k != "Delegation on AutoBench"}
    assert problems(README.read_text(encoding="utf-8"), held=held) == [
        "`### Delegation on AutoBench` is 5,499 bytes, over its delegation cap 5,000",
        f"with each held part at its cap the section would be {PLAN_PROJECTION + 499:,} bytes, over {HOLD_CAP:,}"]


def test_a_twelve_heading_section_over_the_hold_is_named_once_held_is_empty():
    # v1.473: with HELD empty and CLASS naming twelve headings, the section itself is at most HOLD_CAP; the
    # caps are lifted here so the hold is the one check that can fire, and a thirteenth heading lifts it.
    classes = {**SMALL, **{f"P{i}": "routing" for i in range(10)}}
    text = small(extra="".join(f"### P{i}\np\n" for i in range(10)))
    caps = {"routing": SECTION_CAP, "delegation": SECTION_CAP}
    assert len(classes) == ROOM_HEADINGS + 1
    over = text.replace("### A\n", "### A\n" + "x" * (HOLD_CAP - measure(text)[0][1]) + "\n", 1)
    assert measure(over)[0][1] == HOLD_CAP + 1
    assert problems(over, classes=classes, pending={}, held={}, caps=caps) == [
        f"the section is {HOLD_CAP + 1:,} bytes, over {HOLD_CAP:,} while CLASS names {ROOM_HEADINGS + 1} headings"]
    at = text.replace("### A\n", "### A\n" + "x" * (HOLD_CAP - measure(text)[0][1] - 1) + "\n", 1)
    assert measure(at)[0][1] == HOLD_CAP and problems(at, classes=classes, pending={}, held={}, caps=caps) == []
    thirteen = over.replace("## Next\n", "### Q\nq\n## Next\n", 1)
    assert problems(thirteen, classes={**classes, "Q": "delegation"}, pending={}, held={}, caps=caps) == []
