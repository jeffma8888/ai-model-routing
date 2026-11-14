"""The size budget of DESIGN.md sections 12 and 13 (DESIGN 12 v1.386, row DOC21; added by v1.387,
row DOC21a).

Measure, as the 12.8 size budget (v1.335): a subsection is the UTF-8 bytes from its ``### 12.N ``
or ``### 13.N `` heading line, included, through the line before the next ``#``, ``##`` or ``###``
heading (or the end of the text), each line with its newline, so a ``####`` line stays inside it and
the blank line before the next heading counts; a section runs from its ``## 12. `` or ``## 13. `` line
to the next ``#`` or ``##`` line (DESIGN.md's one ``# `` line is its title, so this is the next ``##``
line); a line is measured without its newline. On 12.8 this is tests/test_readme_evidence_budget.py
``design_12_8``.

Each subsection number has a class in CLASS, and each class a cap in CAPS; a number CLASS lacks
fails, as does a ``###`` line of a section that is no ``### 12.N`` or ``### 13.N`` heading of that
section. A subsection in PENDING, the eleven over their caps at v1.386, is held at most its size when
DOC21a landed (the sizes at 6c79574 that v1.386 lists, which v1.386 and v1.387 leave unchanged),
never required at most its cap, and must stay over its cap: the row that trims it removes its number.
Each line of the two sections is at most LINE_CAP bytes but the ones PENDING_LINES names by their
opening text, each held at most its size and required to stay over LINE_CAP; an opening must open
exactly one line. The section totals, SECTION_CAPS, are required once PENDING is empty.
"""
import re
from pathlib import Path

import pytest

from test_readme_evidence_budget import design_12_8

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "DESIGN.md"
SECTIONS = ("12", "13")
SECTION_CAPS = {"12": 260_000, "13": 185_000}
LINE_CAP = 6_000
# The class of each subsection number (DESIGN 12 v1.386 Caps bullet) and the cap of each class.
GROUPS = {
    "contract": ("12.1", "12.2", "12.3", "12.4", "12.5", "13.1", "13.2", "13.3", "13.4", "13.5", "13.6", "13.7"),
    "converter": ("12.6", "12.9", "12.11", "12.14", "12.16", "12.18", "12.20", "13.11"),
    "routing results": ("12.7", "12.10", "12.12", "12.15", "12.17", "12.19", "12.21"),
    "delegation results": ("13.10", "13.12", "13.13", "13.14"),
    "README evidence": ("12.8",),
    "workflow": ("12.13",),
    "limits and test status": ("13.8",),
    "delegation evaluator": ("13.9",),
}
CAPS = {
    "contract": 16_000,
    "converter": 15_000,
    "routing results": 15_000,
    "delegation results": 22_000,
    "README evidence": 50_000,
    "workflow": 25_000,
    "limits and test status": 20_000,
    "delegation evaluator": 25_000,
}
CLASS = {number: kind for kind, numbers in GROUPS.items() for number in numbers}
# The subsections over their caps and their sizes when DOC21a landed; each trim row removes its number
# (12.8 DOC21b, 12.13 DOC21c, 13.8 DOC21d, 13.10 DOC21e, 13.9 DOC21f, 12.21 DOC21g, 12.17 DOC21h,
# 12.14 DOC21i, 13.12 DOC21j, 13.14 DOC21k, 13.11 DOC21l).
PENDING = {
    "12.8": 93_918,
    "12.13": 51_685,
    "13.8": 40_244,
    "13.10": 37_657,
    "13.9": 39_997,
    "12.21": 28_793,
    "12.17": 23_987,
    "12.14": 22_463,
    "13.12": 28_327,
    "13.14": 25_202,
    "13.11": 16_853,
}
# The lines over LINE_CAP, by their opening text, and their sizes when DOC21a landed: the 12.13 time
# limit (DOC26) and two 12.8 bullets (DOC21b).
PENDING_LINES = {
    "- Time limit and retries (v1.152, ": 17_019,
    "- Where routing pays (v1.124): ": 8_660,
    "- Where delegation pays at a glance (v1.258, row DOC15): ": 6_027,
}
SECTION_END = re.compile(r"#{1,2} ")
HEADING = re.compile(r"#{1,3} ")
SUBSECTION = re.compile(r"### (\d+)\.(\d+) ")


def size(lines):
    return sum(len(line.encode("utf-8")) for line in lines)


def measure(text):
    """Sections 12 and 13 of DESIGN.md `text` as (sections, subsections, lines, strays): sections maps
    "12" and "13" to their bytes; subsections lists (number, bytes) in text order; lines lists
    (line number, bytes without its newline, the line) for each line of the two sections; strays lists
    (line number, the line) for each `###` line of a section that is no `### N.M ` heading of it."""
    lines = text.splitlines(keepends=True)
    sections, subsections, measured, strays = {}, [], [], []
    for number in SECTIONS:
        starts = [i for i, line in enumerate(lines) if line.startswith(f"## {number}. ")]
        if len(starts) != 1:
            raise ValueError(f"DESIGN.md has {len(starts)} `## {number}.` lines, not one")
        start = starts[0]
        end = next((i for i in range(start + 1, len(lines)) if SECTION_END.match(lines[i])), len(lines))
        sections[number] = size(lines[start:end])
        for i in range(start, end):
            line = lines[i]
            measured.append((i + 1, len(line.rstrip("\r\n").encode("utf-8")), line))
            if not line.startswith("### "):
                continue
            found = SUBSECTION.match(line)
            if found is None or found[1] != number:
                strays.append((i + 1, line.rstrip("\r\n")))
                continue
            upto = next((j for j in range(i + 1, len(lines)) if HEADING.match(lines[j])), len(lines))
            subsections.append((f"{found[1]}.{found[2]}", size(lines[i:upto])))
    return sections, subsections, measured, strays


def problems(text, classes=CLASS, pending=PENDING, pending_lines=PENDING_LINES):
    """Every way DESIGN.md `text` breaks the budget of sections 12 and 13, as messages; empty when it
    keeps it."""
    sections, subsections, lines, strays = measure(text)
    found = [f"line {at} is a `###` line of its section but no `### N.M ` heading of it: {line[:60]!r}"
             for at, line in strays]
    numbers = [number for number, _ in subsections]
    for number in sorted(set(numbers)):
        if numbers.count(number) > 1:
            found.append(f"`### {number}` appears {numbers.count(number)} times")
    for number in pending:
        if number not in numbers:
            found.append(f"PENDING names `{number}`, which is no `###` heading of sections 12 and 13")
    for number, got in subsections:
        if number not in classes:
            found.append(f"`### {number}` has no class in CLASS")
            continue
        kind = classes[number]
        cap = CAPS[kind]
        if number in pending:
            if got > pending[number]:
                found.append(f"`### {number}` is {got:,} bytes, over its pending size {pending[number]:,}")
            elif got <= cap:
                found.append(f"`### {number}` is {got:,} bytes, at or under its {kind} cap {cap:,}: "
                             f"remove it from PENDING")
        elif got > cap:
            found.append(f"`### {number}` is {got:,} bytes, over its {kind} cap {cap:,}")
    for opening in pending_lines:
        count = sum(1 for _, _, line in lines if line.startswith(opening))
        if count != 1:
            found.append(f"PENDING_LINES names `{opening.strip()}`, which opens {count} lines of sections "
                         f"12 and 13, not one")
    for at, got, line in lines:
        opening = next((o for o in pending_lines if line.startswith(o)), None)
        if opening is None:
            if got > LINE_CAP:
                found.append(f"line {at} is {got:,} bytes, over the line cap {LINE_CAP:,}: {line[:60]!r}")
        elif got > pending_lines[opening]:
            found.append(f"line {at}, `{opening.strip()}`, is {got:,} bytes, over its pending size "
                         f"{pending_lines[opening]:,}")
        elif got <= LINE_CAP:
            found.append(f"line {at}, `{opening.strip()}`, is {got:,} bytes, at or under the line cap "
                         f"{LINE_CAP:,}: remove it from PENDING_LINES")
    if not pending:
        for number in SECTIONS:
            if sections[number] > SECTION_CAPS[number]:
                found.append(f"`## {number}.` is {sections[number]:,} bytes, over {SECTION_CAPS[number]:,}")
    return found


def test_design_keeps_the_budget():
    assert problems(DESIGN.read_text(encoding="utf-8")) == []


def test_the_class_table_names_every_heading_once_in_order():
    _, subsections, _, strays = measure(DESIGN.read_text(encoding="utf-8"))
    numbers = [number for number, _ in subsections]
    by_number = sorted(CLASS, key=lambda n: tuple(int(part) for part in n.split(".")))
    assert numbers == by_number
    assert len(CLASS) == sum(len(group) for group in GROUPS.values()) == 35
    assert set(GROUPS) == set(CAPS)
    assert strays == []


def test_pending_holds_exactly_the_subsections_and_lines_over_their_caps():
    _, subsections, lines, _ = measure(DESIGN.read_text(encoding="utf-8"))
    over = {number for number, got in subsections if got > CAPS[CLASS[number]]}
    assert over == set(PENDING)
    long_lines = {line[:200] for _, got, line in lines if got > LINE_CAP}
    assert len(long_lines) == len(PENDING_LINES)
    assert all(any(line.startswith(o) for o in PENDING_LINES) for line in long_lines)


LISTED = re.compile(r"(1[23]\.\d+) ([\d,]+)(?: bytes)?, ([\d,]+) over \(")
# How the v1.386 bullet names each long line's size (review iter-245 nit 2: tied to the line).
LINE_LISTED = {
    "- Time limit and retries (v1.152, ": re.compile(r"its time-limit bullet, a line of ([\d,]+) bytes"),
    "- Where routing pays (v1.124): ": re.compile(r"`Where routing pays` bullet, ([\d,]+) bytes"),
    "- Where delegation pays at a glance (v1.258, row DOC15): ": re.compile(
        r"`Where delegation pays at a glance`, ([\d,]+), "),
}


def number_of(shown):
    return int(shown.replace(",", ""))


def test_pending_sizes_are_at_most_the_ones_v1_386_lists():
    # The DESIGN 12 `Over a cap at v1.386` bullet gives each subsection over its cap with its size and
    # excess at 6c79574, and the three long lines' sizes. Each PENDING entry is at most its listed size,
    # whose excess over the CAPS value of its class is the listed one, and each PENDING_LINES entry at
    # most its listed size; so an entry is never raised, and a partial trim (DOC26 in 12.13) may lower
    # one (review iter-245 should-fix 1).
    bullets = [line for line in DESIGN.read_text(encoding="utf-8").splitlines()
               if line.startswith("- Over a cap at v1.386")]
    assert len(bullets) == 1
    listed = {number: (number_of(held), number_of(excess)) for number, held, excess in LISTED.findall(bullets[0])}
    assert len(listed) == 11
    for number, held in PENDING.items():
        listed_size, listed_excess = listed[number]
        assert held <= listed_size
        assert listed_excess == listed_size - CAPS[CLASS[number]]
    assert set(PENDING_LINES) <= set(LINE_LISTED)
    for opening, held in PENDING_LINES.items():
        found = LINE_LISTED[opening].findall(bullets[0])
        assert len(found) == 1 and held <= number_of(found[0])


def test_the_measure_is_design_12_8_on_12_8():
    text = DESIGN.read_text(encoding="utf-8")
    assert dict(measure(text)[1])["12.8"] == design_12_8(text)
    small_text = "# T\n## 12. S\n### 12.7 A\na\n### 12.8 B\nb\u00e9\n#### C\nc\n\n### 12.9 D\nd\n## 13. U\n"
    assert dict(measure(small_text)[1])["12.8"] == design_12_8(small_text) == len(
        "### 12.8 B\nb\u00e9\n#### C\nc\n\n".encode())


def test_each_measure_runs_from_its_heading_to_the_next_of_its_level_or_higher():
    text = ("# T\n## 11. Before\nx\n## 12. Twelve\no\n### 12.1 A\na\n#### deeper\n\n### 12.2 B\nb\u00e9\n"
            "## 13. Thirteen\n### 13.1 C\nc\n")
    sections, subsections, lines, strays = measure(text)
    assert sections == {
        "12": len("## 12. Twelve\no\n### 12.1 A\na\n#### deeper\n\n### 12.2 B\nb\u00e9\n".encode()),
        "13": len("## 13. Thirteen\n### 13.1 C\nc\n"),  # the last section runs to the end of the text
    }
    assert subsections == [("12.1", len("### 12.1 A\na\n#### deeper\n\n")), ("12.2", 15), ("13.1", 13)]
    # Lines are numbered from 1 in the whole text and measured without their newline; e-acute is 2 bytes.
    assert [(at, got) for at, got, _ in lines] == [(4, 13), (5, 1), (6, 10), (7, 1), (8, 11), (9, 0), (10, 10),
                                                    (11, 3), (12, 15), (13, 10), (14, 1)]
    assert strays == []
    # A `#` line ends a section and a subsection too, as in `design_12_8`.
    appendix = text + "# Appendix\nq\n"
    assert measure(appendix)[0] == sections and measure(appendix)[1] == subsections
    assert dict(measure(appendix)[1])["13.1"] == len("### 13.1 C\nc\n")


def pad(count):
    """`count` bytes of `x` lines, each at most 5,000 bytes with its newline."""
    assert count >= 1
    full, rest = divmod(count, 5_000)
    return ("x" * 4_999 + "\n") * full + ("x" * (rest - 1) + "\n" if rest else "")


def sub(number, total, name="S"):
    """A `### number` subsection of exactly `total` bytes."""
    head = f"### {number} {name}\n"
    return head + pad(total - len(head))


def small(twelve="", thirteen="", opening=""):
    """Sections 12 and 13 between an 11 and a 14; `opening` is the 12 text before its first `###` line,
    from line 5."""
    return (f"# T\n## 11. Before\nx\n## 12. Twelve\n{opening}{twelve}## 13. Thirteen\n{thirteen}"
            f"## 14. After\nz\n")


SMALL = {"12.1": "contract", "12.2": "converter", "12.3": "README evidence",
         **{f"12.{n}": "contract" for n in range(4, 21)},
         **{f"13.{n}": "delegation results" for n in range(1, 10)}}
LONG = "- Long (v1.1): "
HELD = {"12.3": 50_001}


def long_line(total, opening=LONG):
    return opening + "y" * (total - len(opening)) + "\n"


@pytest.mark.parametrize("text, pending, pending_lines, message", [
    # One byte over a cap, for two classes.
    (small(sub("12.1", 16_001), sub("13.1", 1_000)), {}, {}, "`### 12.1` is 16,001 bytes, over its contract cap 16,000"),
    (small(sub("12.1", 100), sub("13.1", 22_001)), {}, {},
     "`### 13.1` is 22,001 bytes, over its delegation results cap 22,000"),
    # One byte over a pending size, and a pending one no longer over its cap.
    (small(sub("12.3", 50_002), sub("13.1", 100)), HELD, {}, "`### 12.3` is 50,002 bytes, over its pending size 50,001"),
    (small(sub("12.3", 50_000), sub("13.1", 100)), HELD, {},
     "`### 12.3` is 50,000 bytes, at or under its README evidence cap 50,000: remove it from PENDING"),
    # A pending number that is no heading, a number with no class, one heading twice, a stray `###` line.
    (small(sub("12.1", 100), sub("13.1", 100)), {"12.9": 10}, {},
     "PENDING names `12.9`, which is no `###` heading of sections 12 and 13"),
    (small(sub("12.1", 100), sub("13.20", 100)), {}, {}, "`### 13.20` has no class in CLASS"),
    (small(sub("12.1", 100) + sub("12.1", 100), sub("13.1", 100)), {}, {}, "`### 12.1` appears 2 times"),
    (small(sub("12.1", 100) + "### Notes\n", sub("13.1", 100)), {}, {},
     "line 7 is a `###` line of its section but no `### N.M ` heading of it: '### Notes'"),
    (small(sub("12.1", 100), sub("12.2", 100)), {}, {},
     "line 8 is a `###` line of its section but no `### N.M ` heading of it: '### 12.2 S'"),
    # One byte over the line cap, over a pending line's size, a pending line at the cap, an opening
    # that opens no line.
    (small(sub("12.1", 100), sub("13.1", 100), opening="y" * 6_001 + "\n"), {}, {},
     "line 5 is 6,001 bytes, over the line cap 6,000: '" + "y" * 60 + "'"),
    (small(sub("12.1", 100), sub("13.1", 100), opening=long_line(7_001)), {}, {LONG: 7_000},
     "line 5, `- Long (v1.1):`, is 7,001 bytes, over its pending size 7,000"),
    (small(sub("12.1", 100), sub("13.1", 100), opening=long_line(6_000)), {}, {LONG: 7_000},
     "line 5, `- Long (v1.1):`, is 6,000 bytes, at or under the line cap 6,000: remove it from PENDING_LINES"),
    (small(sub("12.1", 100), sub("13.1", 100)), {}, {LONG: 7_000},
     "PENDING_LINES names `- Long (v1.1):`, which opens 0 lines of sections 12 and 13, not one"),
    (small(sub("12.1", 100), sub("13.1", 100), opening=long_line(6_500) + long_line(6_500)), {}, {LONG: 7_000},
     "PENDING_LINES names `- Long (v1.1):`, which opens 2 lines of sections 12 and 13, not one"),
])
def test_a_broken_budget_is_named(text, pending, pending_lines, message):
    assert message in problems(text, classes=SMALL, pending=pending, pending_lines=pending_lines)


def test_at_each_cap_and_size_the_budget_holds():
    text = small(sub("12.1", 16_000) + sub("12.2", 15_000) + sub("12.3", 50_001), sub("13.1", 22_000),
                 opening=long_line(7_000) + "y" * 6_000 + "\n")
    assert measure(text)[1] == [("12.1", 16_000), ("12.2", 15_000), ("12.3", 50_001), ("13.1", 22_000)]
    assert problems(text, classes=SMALL, pending=HELD, pending_lines={LONG: 7_000}) == []


def test_the_section_totals_wait_for_an_empty_pending():
    # Sixteen 16,000-byte contract subsections and one of 3,986 make `## 12.` 14 + 256,000 + 3,986 =
    # 260,000 bytes, at its cap; one byte more is over it, but only once PENDING is empty.
    twelve = "".join(sub(f"12.{n}", 16_000) for n in range(4, 20)) + sub("12.20", 3_986)
    # Eight 22,000-byte delegation results subsections and one of 8,984 make `## 13.` 16 + 176,000 +
    # 8,984 = 185,000 bytes, at its cap.
    thirteen = "".join(sub(f"13.{n}", 22_000) for n in range(1, 9)) + sub("13.9", 8_984)
    at_caps = small(twelve, thirteen)
    assert measure(at_caps)[0] == {"12": 260_000, "13": 185_000}
    assert problems(at_caps, classes=SMALL, pending={}, pending_lines={}) == []
    over = small(twelve + "\n", thirteen + "\n")
    assert problems(over, classes=SMALL, pending={}, pending_lines={}) == [
        "`## 12.` is 260,001 bytes, over 260,000", "`## 13.` is 185,001 bytes, over 185,000"]
    held = small(twelve + "\n" + sub("12.3", 50_001), thirteen + "\n")
    assert problems(held, classes=SMALL, pending=HELD, pending_lines={}) == []


def test_a_text_without_one_section_line_each_is_an_error():
    with pytest.raises(ValueError, match="has 0 `## 12.` lines, not one"):
        measure("# T\n## 13. U\n")
    with pytest.raises(ValueError, match="has 2 `## 13.` lines, not one"):
        measure("# T\n## 12. S\n## 13. U\n## 13. U\n")
