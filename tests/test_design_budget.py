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
DOC21a landed (the sizes at 6c79574 that v1.386 lists, which v1.386 and v1.387 leave unchanged)
or the smaller size a part of its trim leaves (v1.388),
never required at most its cap, and must stay over its cap: the row that trims it removes its number.
Each line of the two sections is at most LINE_CAP bytes but the ones PENDING_LINES names by their
opening text, each held at most its size and required to stay over LINE_CAP; an opening must open
exactly one line. The section totals, SECTION_CAPS, bind each section as measured once PENDING is empty,
and until then each section with every PENDING subsection cut to its cap (v1.456).

History pointers (v1.388, row DOC21m): each ``(history: CHANGELOG.md ...)`` pointer of the two sections
lists ``vX.Y`` and ``vX.Y to vX.Z`` items joined by ``, ``, each version (both ends of a range) with a
CHANGELOG.md line, and POINTERS names, by the opening of its line, each pointer a trim wrote with the list
it gives, so a pointer that is moved, changed or added without an entry fails.

Research notes out of 12.8 (v1.390, row DOC21o): the seven research-note bullets of 12.8, with the README
sub-bullet of the first, are 12.22, a research-notes spec with a cap of 40,000 bytes, in the same order
(RESEARCH_NOTES); 12.8 holds none of them and leaves PENDING, and the `## 12.` total is 300,000 bytes
(330,000 from v1.456, 345,000 from v1.478, 360,000 from v1.481, 375,000 from v1.523, 390,000 from v1.528, 405,000 from v1.541).

The time-limit line (v1.391, row DOC26): the 12.13 time-limit bullet keeps its contract and puts its earlier
bases behind one history pointer (POINTERS), so it is at most LINE_CAP and PENDING_LINES is empty; 12.13
stayed in PENDING at the smaller size the trim left, for DOC21c.

The rest of 12.13 (v1.392, row DOC21c): each changed line of 12.13 keeps its contract in force, stated from
the workflow and the tests as they are, and its history behind one pointer (POINTERS), so 12.13 is at most
its workflow cap and leaves PENDING; the heading keeps one tag per clause, and the restatements of the time
limit it dropped are in the time-limit bullet's pointer.

The ledger runs (v1.394, row E23): 13.15, the ledger hand-off converter, is a converter.

Room in 12.22 (v1.421, row DOC34): the eight research-note lines of v1.124 to v1.191 drop the scope
sentences of the slices that added them (`No change under ...`), their explanatory clauses and the
definitions they restated from 12.3, each keeping its contract with one history pointer (POINTERS).
v1.422 (row DOC34b): the same lines restate their contract in fewer words; each rule several of them repeated
is stated once and the others name the line that holds it (BORROWED).
v1.457 (row DOC38a): 12.22 drops its explanatory clauses (why a rule holds, what another section
defines, what a later slice would do), each contract item staying; the seed by seed line takes the
best single model from the where-routing-pays line (BORROWED), and the versions the dropped clauses
named have their CHANGELOG.md lines (DOC38A_DROPPED).
v1.460 (row DOC38b): the per-task ceiling, seed by seed, check fallback and below-bar lines restate their
contract in fewer words, and the where-routing-pays and no-model-clears lines their test and output
sentences, each contract item staying (DOC38B_DROPPED); the seed by seed exit list names a best single
model that differs between bars or flavors (review iter-321 nit 3, BORROWED).

The registry pair (v1.431, row E24): 12.23, the registry-pair converter, is a converter.
Delegation research notes (v1.461, row DOC38c): the four 12.22 lines that specify delegation research notes,
or the README paragraph that links two, are 13.16, word for word and in the same order (DELEGATION_NOTES), a
research-notes subsection with 12.22's cap, which raises the `## 13.` total by 40,000 to 240,000; the tests of
the eight lines of v1.124 to v1.191 (DOC34_LINES) and of the wordings v1.457 and v1.460 dropped read both.
12.24, the registry-pair results (v1.433, row E24b), is a routing results subsection; 13.17, the registry-pair
delegation results (v1.468, row E25a), a delegation results subsection, which raises the `## 13.` total by 22,000.
Longtail-SWE (v1.478, row E26a): 12.25, the Longtail-SWE converter, is a converter, which raises the `## 12.`
total by 15,000 to 345,000; 12.26, the Longtail-SWE results (v1.481, row E26c), is a routing results
subsection, which raises it by 15,000 to 360,000; 12.27, the AutoBench slice results (v1.523, row
STRAT3f), is a routing results subsection, which raises it by 15,000 to 375,000; 12.28, the LiveCodeBench
slice results (v1.528, row STRAT3h), is a routing results subsection, which raises it by 15,000 to 390,000;
12.29, the tau2-bench cascade results (v1.541, row ESC3c), is a routing results subsection, which raises it by
15,000 to 405,000.
Longtail-SWE delegation (v1.498, row E27a): 13.18, the Longtail-SWE delegation results, is a delegation results
subsection, which raises the `## 13.` total by 22,000 to 284,000.

The registry pair in the workflow (v1.443, row E24e): three `is rerun` lines of 12.13 drop what the Steps,
RouterBench and Tests lines already state for every rerun block (its place in `Regenerate`, `Compare` and the
top comment, and the test reading it), so 12.13 has room for the registry pair's lines.
The registry-pair delegation in the workflow (v1.472, row E25c): the no-cache, repeated-line and two delegation
`is rerun` lines of 12.13 drop the reasons they gave against a cache, the restatements of the repeated-line
rule and what that rule and the Steps line state, so 12.13 has room for the delegation block's bullet.
Longtail-SWE in the workflow (v1.489, row E26d): the runner, token-permissions, no-cache, Steps and three
`is rerun` lines of 12.13 drop asides, the reasons against a cache that are not the purpose, the tau2-bench
run-file detail and what the Steps line states of each block's lines, so 12.13 has room for the Longtail-SWE
bullet and the `pyarrow` install.
The AutoBench slices in the workflow (v1.525, row STRAT3g): the runner, token-permissions, no-cache, Steps,
repeated-line and two `is rerun` lines of 12.13 drop asides and reasons that are not the contract, so 12.13 has
room for the slices bullet and grows by 16 bytes, leaving rows CI27 and T21 the room they had.
The LiveCodeBench slices in the workflow (v1.530, row STRAT3i): the workflow, no-cache, RouterBench and
registry-pair delegation lines of 12.13 drop asides, the growth history of their lists and what the Steps line
states, so 12.13 has room for the LiveCodeBench block in the slices bullet and grows by 9 bytes.
The tau2-bench cascades in the workflow (v1.544, row ESC3e): the runner line drops the reason the workflow's
runner comment gives, the repeated-line, RouterBench and Python-versions lines an aside each and the no-cache
line restates the caching reference in fewer words, so 12.13 has room for the cascades bullet and grows by 198
bytes.

The section totals (v1.456, row DOC37): each total is the one last set with the subsections it counted,
`## 12.` 300,000 at v1.390 with 12.1 to 12.22 and `## 13.` 185,000 at v1.386 with 13.1 to 13.14
(TOTAL_BASES), raised by the cap of each subsection added after them (12.23 and 12.24, 13.15, from v1.461,
13.16, from v1.468, 13.17, from v1.478, 12.25, from v1.481, 12.26, from v1.498, 13.18, from v1.523, 12.27,
from v1.528, 12.28 and, from v1.541, 12.29), so 405,000 and
284,000. While PENDING is not empty, each section with every PENDING subsection cut to its cap
(`projected`) must fit its total; the DESIGN 12 Caps bullet names each subsection of GROUPS in its class,
with that class's cap, and states the totals (CAPS_CLAUSES, `caps_bullet_problems`). So a subsection
added without a class, a Caps clause or a raised total fails in its own slice, not at the last trim.
"""
import re
from pathlib import Path

import pytest

from test_readme_evidence_budget import design_12_8

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "DESIGN.md"
SECTIONS = ("12", "13")
SECTION_CAPS = {"12": 405_000, "13": 284_000}  # v1.456, 12 v1.541 (390,000 at v1.528, 375,000 at v1.523, 360,000 at v1.481, 345,000 at v1.478, 330,000 at v1.456), 13 v1.498 (262,000 at v1.468, 240,000 at v1.461); 12 300,000 at v1.390 and 260,000 at v1.386, 13 185,000
# The total each section had when it last counted its subsections, the version that set it, and the last
# subsection number it counted (12 v1.390 with 12.1 to 12.22, 13 v1.386 with 13.1 to 13.14); each
# subsection numbered after it raises its section's total by the cap of its class (v1.456, row DOC37).
TOTAL_BASES = {"12": (300_000, "v1.390", 22), "13": (185_000, "v1.386", 14)}
LINE_CAP = 6_000
# The class of each subsection number (DESIGN 12 v1.386 Caps bullet; research notes v1.390) and the cap of each class.
GROUPS = {
    "contract": ("12.1", "12.2", "12.3", "12.4", "12.5", "13.1", "13.2", "13.3", "13.4", "13.5", "13.6", "13.7"),
    "converter": ("12.6", "12.9", "12.11", "12.14", "12.16", "12.18", "12.20", "12.23", "12.25", "13.11", "13.15"),
    "routing results": ("12.7", "12.10", "12.12", "12.15", "12.17", "12.19", "12.21", "12.24", "12.26", "12.27",
                        "12.28", "12.29"),
    "delegation results": ("13.10", "13.12", "13.13", "13.14", "13.17", "13.18"),
    "README evidence": ("12.8",),
    "workflow": ("12.13",),
    "limits and test status": ("13.8",),
    "delegation evaluator": ("13.9",),
    "research notes": ("12.22", "13.16"),
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
    "research notes": 40_000,
}
CLASS = {number: kind for kind, numbers in GROUPS.items() for number in numbers}
# The subsections over their caps and their sizes when DOC21a landed; each trim row removes its number
# (12.8 DOC21b, split into DOC21m to DOC21o, the last of which, v1.390, removed it at 45,002 bytes, 12.13 DOC26
# then DOC21c, which removed it, v1.392, 13.8 DOC21d, 13.10 DOC21e, 13.9 DOC21f, 12.21 DOC21g, 12.17 DOC21h,
# 12.14 DOC21i, 13.12 DOC21j, 13.14 DOC21k, 13.11 DOC21l).
PENDING = {
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
# The lines over LINE_CAP, by their opening text, and their sizes when DOC21a landed: none left. DOC21m
# (v1.388) brought the two 12.8 bullets, 8,660 and 6,027 bytes, under LINE_CAP, and DOC26 (v1.391) the
# 12.13 time-limit bullet, 17,019 bytes.
PENDING_LINES = {}
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


def projected(sections, subsections, classes=CLASS, pending=PENDING):
    """Each section's bytes with every `pending` subsection cut to exactly its cap and the rest as measured
    (v1.456, row DOC37), from the `sections` and `subsections` that `measure` gives; a pending subsection
    at or under its cap, or with no class, takes nothing off."""
    totals = dict(sections)
    for number, got in subsections:
        if number in pending and number in classes:
            totals[number.split(".")[0]] -= max(0, got - CAPS[classes[number]])
    return totals


def problems(text, classes=CLASS, pending=PENDING, pending_lines=PENDING_LINES, section_caps=SECTION_CAPS):
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
            if sections[number] > section_caps[number]:
                found.append(f"`## {number}.` is {sections[number]:,} bytes, over {section_caps[number]:,}")
    else:
        # v1.456 (row DOC37): until then, each section with every pending subsection cut to its cap.
        totals = projected(sections, subsections, classes, pending)
        for number in SECTIONS:
            if totals[number] > section_caps[number]:
                found.append(f"`## {number}.` would be {totals[number]:,} bytes with each PENDING subsection "
                             f"at its cap, over {section_caps[number]:,}")
    return found


def test_design_keeps_the_budget():
    assert problems(DESIGN.read_text(encoding="utf-8")) == []


def test_the_class_table_names_every_heading_once_in_order():
    _, subsections, _, strays = measure(DESIGN.read_text(encoding="utf-8"))
    numbers = [number for number, _ in subsections]
    by_number = sorted(CLASS, key=lambda n: tuple(int(part) for part in n.split(".")))
    assert numbers == by_number
    assert len(CLASS) == sum(len(group) for group in GROUPS.values()) == 47  # 36 before 13.15 (v1.394), 37 before 12.23 (v1.431), 38 before 12.24 (v1.433), 39 before 13.16 (v1.461), 40 before 13.17 (v1.468), 41 before 12.25 (v1.478), 42 before 12.26 (v1.481), 43 before 13.18 (v1.498), 44 before 12.27 (v1.523), 45 before 12.28 (v1.528), 46 before 12.29 (v1.541)
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
# How the v1.386 bullet names each long line's size (review iter-245 nit 2: tied to the line). PENDING_LINES
# is empty from v1.391, so these are read for no entry now; they stay as the form a pending line's listed
# size takes, and a line over LINE_CAP later is a new problem, never a PENDING_LINES entry (v1.392).
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
         **{f"12.{n}": "contract" for n in range(4, 23)},
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


def test_the_section_totals_bind_the_projection_until_pending_is_empty():
    # Eighteen 16,000-byte contract subsections and one of 11,986 make `## 12.` 14 + 288,000 + 11,986 =
    # 300,000 bytes, at a total of 300,000; one byte more is over it.
    twelve = "".join(sub(f"12.{n}", 16_000) for n in range(4, 22)) + sub("12.22", 11_986)
    # Eight 22,000-byte delegation results subsections and one of 8,984 make `## 13.` 16 + 176,000 +
    # 8,984 = 185,000 bytes, at a total of 185,000.
    thirteen = "".join(sub(f"13.{n}", 22_000) for n in range(1, 9)) + sub("13.9", 8_984)
    totals = {"12": 300_000, "13": 185_000}
    at_caps = small(twelve, thirteen)
    assert measure(at_caps)[0] == totals
    assert problems(at_caps, classes=SMALL, pending={}, pending_lines={}, section_caps=totals) == []
    over = small(twelve + "\n", thirteen + "\n")
    assert problems(over, classes=SMALL, pending={}, pending_lines={}, section_caps=totals) == [
        "`## 12.` is 300,001 bytes, over 300,000", "`## 13.` is 185,001 bytes, over 185,000"]
    # v1.456 (row DOC37): while PENDING is not empty a total binds its section with each pending subsection
    # cut to its cap. 12.3, held at 50,001 of its 50,000, counts 50,000, so beside it fifteen contract
    # subsections and one of 9,986 make 14 + 50,000 + 240,000 + 9,986 = 300,000, though 300,001 are measured.
    room = sub("12.3", 50_001) + "".join(sub(f"12.{n}", 16_000) for n in range(4, 19)) + sub("12.22", 9_986)
    held = small(room, thirteen)
    sections, subsections, _, _ = measure(held)
    assert sections == {"12": 300_001, "13": 185_000}
    assert projected(sections, subsections, classes=SMALL, pending=HELD) == totals
    assert projected(sections, subsections, classes=SMALL, pending={}) == sections
    assert problems(held, classes=SMALL, pending=HELD, pending_lines={}, section_caps=totals) == []
    assert problems(small(room + "\n", thirteen + "\n"), classes=SMALL, pending=HELD, pending_lines={},
                    section_caps=totals) == [
        "`## 12.` would be 300,001 bytes with each PENDING subsection at its cap, over 300,000",
        "`## 13.` would be 185,001 bytes with each PENDING subsection at its cap, over 185,000"]
    # With nothing pending, the same text has 12.3 over its cap and `## 12.` over its total as measured.
    assert problems(held, classes=SMALL, pending={}, pending_lines={}, section_caps=totals) == [
        "`### 12.3` is 50,001 bytes, over its README evidence cap 50,000", "`## 12.` is 300,001 bytes, over 300,000"]


def test_a_text_without_one_section_line_each_is_an_error():
    with pytest.raises(ValueError, match="has 0 `## 12.` lines, not one"):
        measure("# T\n## 13. U\n")
    with pytest.raises(ValueError, match="has 2 `## 13.` lines, not one"):
        measure("# T\n## 12. S\n## 13. U\n## 13. U\n")


# --- history pointers (DESIGN 12 v1.388, row DOC21m) ----------------------------------------------

CHANGELOG = ROOT / "CHANGELOG.md"
POINTER = re.compile(r"\(history: CHANGELOG\.md (v\d[^)]*)\)")
POINTER_ITEM = re.compile(r"v(\d+\.\d+)(?: to v(\d+\.\d+))?")
CHANGELOG_LINE = re.compile(r"^- v(\d+\.\d+) \(", re.M)
# Each pointer a trim wrote, by the opening of the line that holds it, and the list it gives: the
# versions the sentences it dropped name (DOC21m: four of the seven research-note bullets of 12.8, in 12.22
# from v1.390; DOC21n: thirteen lines of its dataset-subsection bullets; DOC21o: two lines of its size budget clause;
# DOC26: the 12.13 time-limit bullet, tests/test_evidence_workflow.py TIME_LIMIT_HISTORY; DOC21c: the
# other sixteen lines of 12.13 it changed, its heading holding no pointer; DOC34, v1.421: the other four
# research-note lines of v1.124 to v1.177 gain one, and the four that had one extend it).
POINTERS = {
    "- Where routing pays (v1.124): ": "v1.124, v1.305",
    "  - README.md and research/README.md (v1.124, v1.166, v1.303): ": "v1.124, v1.164, v1.166, v1.296, v1.303",
    "- Where delegation pays at a glance (v1.258, row DOC15): ": "v1.258, v1.260, v1.315, v1.316, v1.322, v1.323, v1.328",
    "- When no model clears (v1.144; six datasets from v1.341, row R32, seven from v1.459, row R44): ": "v1.144, v1.341",
    "- Per-task ceiling on RouterBench (v1.146): ": "v1.146",
    "- Seed by seed on LLMRouterBench (v1.177): ": "v1.177, v1.179",
    "- Fallback on a failed check, on LLMRouterBench (v1.181): ": "v1.181 to v1.185",
    "- Below-bar fallback, on LLMRouterBench (v1.191): ": "v1.182, v1.191, v1.201",
    "- README.md has a section `## Evidence: held-out results on public data`, ":
        "v1.17, v1.22, v1.28, v1.30, v1.48, v1.55, v1.65, v1.80, v1.84",
    "- Results at a glance (v1.23): ": "v1.28, v1.32, v1.55, v1.65, v1.80",
    "- LLMRouterBench (v1.164, row E16e): ": "v1.164, v1.168",
    "  - Limits: none from v1.446 (to v1.445 the seventh RESULTS.md bullet), ": "v1.167, v1.168",
    "  - Results at a glance: a bullet, after LiveCodeBench, ": "v1.164, v1.166",
    "  - Tests: `tests/test_evidence_llmrouterbench_results.py` ": "v1.164, v1.166",
    "- Delegation on tau2-bench (v1.80): ": "v1.92, v1.336, v1.337",
    "- Delegation on LLMRouterBench (v1.200, row E17d): ": "v1.200, v1.316",
    "- LLM Routing Response Bank (v1.296, row E20e): ": "v1.296, v1.299",
    "  - Limits: none from v1.447 (to v1.446 the sixth RESULTS.md bullet, the billed cost), ": "v1.296, v1.299",
    "  - Results at a glance: a seventh bullet, ": "v1.166, v1.303",
    "  - Tests: `tests/test_evidence_response_bank_results.py` ": "v1.296",
    "- Delegation on the LLM Routing Response Bank (v1.316, row E21d): ": "v1.258, v1.316, v1.317, v1.323, v1.324",
    "- Size budget (v1.334, row DOC19): ": "v1.334 to v1.373",
    "  - 12.8 shrinks with each trim (v1.344, row DOC20): ": "v1.344 to v1.372, v1.386, v1.388, v1.389",
    "- Time limit and retries (v1.152, ": ("v1.152, v1.168, v1.170, v1.215, v1.217, v1.218, v1.225, v1.226, v1.268, "
                                           "v1.299, v1.301, v1.302, v1.317, v1.321, v1.374, v1.395, v1.398, "
                                           "v1.399, v1.401, v1.407, v1.442"),
    "Purpose: a reader can see the twenty-two results files of the `Compare` step below ":
        "v1.55, v1.65, v1.80, v1.84, v1.168, v1.200, v1.299",
    "- The workflow `.github/workflows/evidence.yml`, `name: evidence`, ":
        "v1.54, v1.55, v1.65, v1.80, v1.84, v1.168, v1.200, v1.299",
    "- Runner (v1.49): ": "v1.48, v1.49",
    "- No cache between runs (v1.251, row CI9): ": "v1.225, v1.226, v1.268, v1.301, v1.302, v1.317, v1.321",
    "- Token permissions (v1.137): ": "v1.138, v1.139",
    "- Python versions (v1.118): ": "v1.117, v1.118, v1.119",
    "- Steps, in this order: ": "v1.48, v1.54, v1.55, v1.64, v1.65, v1.80, v1.84, v1.168, v1.200, v1.299",
    "- RouterBench stays out: ": "v1.55, v1.65, v1.80, v1.168, v1.200, v1.299",  # review iter-251 must-fix 1
    "- LiveCodeBench is rerun (v1.65) ": "v1.65",
    "- LLMRouterBench is rerun (v1.168, row E16d): ": "v1.152, v1.167, v1.168, v1.169, v1.170",
    "- LLMRouterBench delegation is rerun (v1.200, row E17d): ": (
        "v1.168, v1.170, v1.200, v1.214, v1.215, v1.217, v1.225, v1.268, v1.299, v1.301, v1.302, v1.317, v1.321"),
    "- LLM Routing Response Bank is rerun (v1.298, row E20f; the lines v1.299): ":
        "v1.297, v1.299, v1.301, v1.302, v1.317, v1.321",
    "- Response-bank delegation is rerun (v1.316, row E21d; the 13.14 Workflow bullet): ": "v1.218, v1.316, v1.321",
    "- One run of a repeated line (v1.215, row CI8): ":
        "v1.200, v1.217, v1.225, v1.268, v1.299, v1.301, v1.302, v1.317, v1.321",  # review iter-251 must-fix 2
    "- README: the evidence section's opening paragraph (12.8) ":
        "v1.47, v1.48, v1.55, v1.65, v1.80, v1.84, v1.168, v1.200, v1.298, v1.299",
    "- Tests, in `tests/test_evidence_workflow.py` (standard library only, so they run in CI): ":
        "v1.84, v1.85, v1.152, v1.168, v1.200, v1.215, v1.251, v1.278, v1.299",
}


def pointer_problems(text, changelog, pointers=POINTERS):
    """What breaks the history pointers of sections 12 and 13 of `text` against `changelog`."""
    _, _, lines, _ = measure(text)
    logged = set(CHANGELOG_LINE.findall(changelog))
    found, held = [], {}
    for number, _, line in lines:
        for listed in POINTER.findall(line):
            held.setdefault(number, []).append(listed)
            for item in listed.split(", "):
                parts = POINTER_ITEM.fullmatch(item)
                if parts is None:
                    found.append(f"line {number}: history pointer item `{item}` is no `vX.Y` or `vX.Y to vX.Z`")
                    continue
                low, high = parts.groups()
                if high is not None and tuple(map(int, high.split("."))) <= tuple(map(int, low.split("."))):
                    found.append(f"line {number}: history pointer range `{item}` does not rise")
                for version in parts.groups():
                    if version is not None and version not in logged:
                        found.append(f"line {number}: history pointer names v{version}, which has no CHANGELOG.md line")
    named = set()
    for opening, listed in pointers.items():
        at = [number for number, _, line in lines if line.startswith(opening)]
        if len(at) != 1:
            found.append(f"POINTERS names `{opening.strip()}`, which opens {len(at)} lines of sections 12 and 13, "
                         "not one")
            continue
        named.add(at[0])
        if held.get(at[0]) != [listed]:
            found.append(f"line {at[0]}, `{opening.strip()}`, holds the history pointers {held.get(at[0], [])}, "
                         f"not [{listed!r}]")
    for number in sorted(set(held) - named):
        found.append(f"line {number} holds a history pointer that POINTERS lacks")
    return found


def test_each_history_pointer_names_logged_versions_where_its_trim_put_it():
    assert pointer_problems(DESIGN.read_text(encoding="utf-8"), CHANGELOG.read_text(encoding="utf-8")) == []


def test_each_pointer_version_has_its_own_changelog_line():
    # By hand, without the parser: each version the trimmed sentences named opens a CHANGELOG.md line.
    changelog = CHANGELOG.read_text(encoding="utf-8")
    for version in ("1.124", "1.164", "1.166", "1.296", "1.303", "1.258", "1.315", "1.316", "1.322", "1.323",
                    "1.328", "1.181", "1.184", "1.191", "1.201", "1.17", "1.22", "1.28", "1.30", "1.48", "1.55",
                    "1.65", "1.80", "1.84", "1.32", "1.167", "1.168", "1.92", "1.336", "1.337", "1.200", "1.299",
                    "1.317", "1.324", "1.334", "1.335", "1.344", "1.345", "1.346", "1.347", "1.348", "1.350", "1.352",
                    "1.353", "1.355", "1.357", "1.358", "1.362", "1.365", "1.368", "1.370", "1.372", "1.373", "1.386",
                    "1.388", "1.389",  # 1.388: review iter-248 nit 2
                    # DOC26 (v1.391): every version the 12.13 time-limit bullet named through v1.390.
                    "1.152", "1.170", "1.214", "1.215", "1.217", "1.218", "1.225", "1.226", "1.251", "1.268",
                    "1.301", "1.302", "1.321", "1.374",
                    # DOC21c (v1.392): the versions the other changed lines of 12.13 named, not listed above.
                    "1.47", "1.49", "1.54", "1.64", "1.85", "1.117", "1.118", "1.119", "1.138", "1.139", "1.169",
                    "1.278", "1.297", "1.298",
                    # DOC34 (v1.421): the versions the eight 12.22 lines it trimmed name, not listed above.
                    "1.144", "1.146", "1.177", "1.179", "1.182", "1.185", "1.260", "1.305", "1.341"):
        assert f"\n- v{version} (" in changelog, version


def test_the_time_limit_bullet_is_under_the_line_cap_with_one_pointer():
    # DOC26 (v1.391): the 12.13 time-limit bullet, 17,019 bytes at v1.386, is at most LINE_CAP and out of
    # PENDING_LINES, with one history pointer, the one POINTERS gives it.
    opening = "- Time limit and retries (v1.152, "
    found = [(got, line) for _, got, line in measure(DESIGN.read_text(encoding="utf-8"))[2] if line.startswith(opening)]
    assert len(found) == 1
    got, line = found[0]
    assert got <= LINE_CAP and opening not in PENDING_LINES  # review iter-249 nit 3
    assert POINTER.findall(line) == [POINTERS[opening]]


TINY_LOG = "- v1.1 (2026-01-01): a\n- v1.2 (2026-01-02): b\n- v1.4 (2026-01-04): d\n"
TINY = ("# T\n## 12. S\n### 12.1 A\n- A (v1.1): a (history: CHANGELOG.md v1.1, v1.2)\n"
         "- B (v1.4): b (history: CHANGELOG.md v1.1 to v1.4)\n## 13. D\n### 13.1 E\ne\n## 14. N\n")
TINY_POINTERS = {"- A (v1.1): ": "v1.1, v1.2", "- B (v1.4): ": "v1.1 to v1.4"}


@pytest.mark.parametrize("old, new, pointers, message", [
    ("", "", TINY_POINTERS, None),
    ("\ne\n", "\n- T (v1.4): the form `(history: CHANGELOG.md vX.Y to vX.Z)`\n", TINY_POINTERS, None),
    ("v1.1, v1.2)", "v1.1, v1.3)", {**TINY_POINTERS, "- A (v1.1): ": "v1.1, v1.3"},
     "line 4: history pointer names v1.3, which has no CHANGELOG.md line"),
    ("v1.1 to v1.4)", "v1.1 to v1.5)", {**TINY_POINTERS, "- B (v1.4): ": "v1.1 to v1.5"},
     "line 5: history pointer names v1.5, which has no CHANGELOG.md line"),
    ("v1.1 to v1.4)", "v1.3 to v1.4)", {**TINY_POINTERS, "- B (v1.4): ": "v1.3 to v1.4"},
     "line 5: history pointer names v1.3, which has no CHANGELOG.md line"),
    ("v1.1, v1.2)", "v1.1 and v1.2)", {**TINY_POINTERS, "- A (v1.1): ": "v1.1 and v1.2"},
     "line 4: history pointer item `v1.1 and v1.2` is no `vX.Y` or `vX.Y to vX.Z`"),
    ("v1.1, v1.2)", "v1.1)", TINY_POINTERS,
     "line 4, `- A (v1.1):`, holds the history pointers ['v1.1'], not ['v1.1, v1.2']"),
    (" (history: CHANGELOG.md v1.1, v1.2)", "", TINY_POINTERS,
     "line 4, `- A (v1.1):`, holds the history pointers [], not ['v1.1, v1.2']"),
    ("\ne\n", "\n- C (v1.2): c (history: CHANGELOG.md v1.2)\n", TINY_POINTERS,
     "line 8 holds a history pointer that POINTERS lacks"),
    ("v1.1 to v1.4)", "v1.4 to v1.1)", {**TINY_POINTERS, "- B (v1.4): ": "v1.4 to v1.1"},
     "line 5: history pointer range `v1.4 to v1.1` does not rise"),
    ("\ne\n", "\n- A (v1.1): again\n", TINY_POINTERS,
     ("POINTERS names `- A (v1.1):`, which opens 2 lines of sections 12 and 13, not one",
      "line 4 holds a history pointer that POINTERS lacks")),
    ("", "", {**TINY_POINTERS, "- Z (v1.9): ": "v1.9"},
     "POINTERS names `- Z (v1.9):`, which opens 0 lines of sections 12 and 13, not one"),
])
def test_a_broken_history_pointer_is_named(old, new, pointers, message):
    text = TINY.replace(old, new, 1) if old else TINY
    assert old == "" or TINY.count(old) == 1
    expected = [] if message is None else list(message) if isinstance(message, tuple) else [message]
    assert pointer_problems(text, TINY_LOG, pointers) == expected


# --- research notes out of 12.8 (DESIGN 12 v1.390, row DOC21o) ------------------------------------

# The opening of each line of the research-note bullets, the first with its README sub-bullet, in
# their order in 12.22.
RESEARCH_NOTES = (
    "- Where routing pays (v1.124): ",
    "  - README.md and research/README.md (v1.124, v1.166, v1.303): ",
    "- When no model clears (v1.144; six datasets from v1.341, row R32, seven from v1.459, row R44): ",
    "- Per-task ceiling on RouterBench (v1.146): ",
    "- Seed by seed on LLMRouterBench (v1.177): ",
    "- Fallback on a failed check, on LLMRouterBench (v1.181): ",
    "- Below-bar fallback, on LLMRouterBench (v1.191): ",
    "- A price error, on LLMRouterBench (v1.403, row R35): ",
    "- The registry's own pair, on superlinked/train-a-router-reasoning (v1.430, row R40): ",
    "  - Training split (v1.467, row R41): ",
    "- Longtail-SWE runs 0, 1 and 2 (v1.490, row E26h): ",  # v1.490
    "- Longtail-SWE's other configs at their vendors' list prices (v1.497, row R53): ",  # v1.497
)
# v1.461 (row DOC38c): the four 12.22 lines that specify delegation research notes are 13.16, in this order.
DELEGATION_NOTES = (
    "- Where delegation pays at a glance (v1.258, row DOC15): ",
    "- The 13.2 re-read rule against measured tokens (v1.402, row R37): ",
    "- The re-read share and the brief's output, on AutoBench, LLMRouterBench, the response bank and tau2-bench (v1.413, row R38): ",
    "- A price error in a delegation decision, on AutoBench (v1.424, row R39): ",
)
# v1.466 (row R42): the bullets of later delegation research notes follow the four, in the order they land.
LATER_DELEGATION_NOTES = (
    "- The registry's own pair as delegation evidence, on superlinked/train-a-router-reasoning (v1.466, row R42): ",
    "- Longtail-SWE as delegation evidence, on nebius/Longtail-SWE-trajectories (v1.495, row R50): ",
    "- Longtail-SWE per call, under a stated split of each run's totals (v1.496, row R50b): ",
)
# The eight lines of v1.124 to v1.191 that DOC34 (v1.421) trimmed, seven in 12.22 and one in 13.16 from v1.461.
DOC34_LINES = RESEARCH_NOTES[:7] + DELEGATION_NOTES[:1]


def subsection_body(text, number):
    """The lines of `### number` after its heading line, through the line before the next heading."""
    lines = text.splitlines()
    starts = [i for i, line in enumerate(lines) if line.startswith(f"### {number} ")]
    assert len(starts) == 1, number
    upto = next((j for j in range(starts[0] + 1, len(lines)) if HEADING.match(lines[j])), len(lines))
    return lines[starts[0] + 1:upto]


def notes_body(text):
    """The lines of 12.22 and 13.16 after their headings: the research-note lines (v1.461, row DOC38c)."""
    return subsection_body(text, "12.22") + subsection_body(text, "13.16")


def test_the_research_notes_are_12_22_and_12_8_holds_none():
    text = DESIGN.read_text(encoding="utf-8")
    body = subsection_body(text, "12.22")
    assert body[0].startswith("Purpose: the research-note bullets 12.8 held through v1.389, in the same order "
                              "(12 v1.390): ")
    assert body[0].endswith(" A reference to one of them as 12.8, `12.8 vX.Y` or `12.8` alone, in this file, a "
                            "test or a research note, names its bullet here or, for the four, in 13.16.")
    # review iter-248 nit 1; v1.465 (row DOC43, review iter-325 nit 2): `for the four`
    assert len(body) == len(RESEARCH_NOTES) + 2 and body[-1] == ""
    for line, opening in zip(body[1:-1], RESEARCH_NOTES):
        assert line.startswith(opening), (line[:60], opening)
    twelve_eight = subsection_body(text, "12.8")
    assert [line[:60] for line in twelve_eight if line.startswith(RESEARCH_NOTES)] == []
    glance = [line for line in twelve_eight if line.startswith("- Results at a glance (v1.23): ")]
    assert len(glance) == 1
    assert ("then (v1.124) a blank line and the one paragraph of the where-routing-pays bullet of 12.22, then "
            "(v1.258) a blank line and the one paragraph of the where-delegation-pays-at-a-glance bullet of 13.16, "
            "then (v1.396) a blank line and the 13.15 README paragraph, and by nothing else.") in glance[0]
    assert "12.8" not in PENDING and dict(measure(text)[1])["12.8"] <= CAPS["README evidence"]


def test_the_delegation_notes_are_13_16_and_12_22_holds_none():
    # v1.461 (row DOC38c)
    text = DESIGN.read_text(encoding="utf-8")
    assert text.count("\n### 13.16 Research notes on delegation (`research/`, out of 12.22 v1.461)\n") == 1
    body = subsection_body(text, "13.16")
    assert body[0].startswith("Purpose: the four 12.22 lines that specify delegation research notes, or the README "
                              "paragraph that links two of them, word for word and in the same order (13 v1.461, "
                              "row DOC38c): ")
    assert body[0].endswith(" A reference to one of them as 12.8 or 12.22, with or without a version, in this file, "
                            "a test, a script or a research note, names its bullet here.")
    assert (" From v1.466 (row R42) the bullets of later delegation research notes follow the four, in the order "
            "they land. ") in body[0]
    assert len(body) == len(DELEGATION_NOTES) + len(LATER_DELEGATION_NOTES) + 2 and body[-1] == ""
    for line, opening in zip(body[1:-1], DELEGATION_NOTES + LATER_DELEGATION_NOTES):
        assert line.startswith(opening), (line[:60], opening)
    assert [line[:60] for line in subsection_body(text, "12.22") if line.startswith(DELEGATION_NOTES)] == []
    assert (" From v1.461 (row DOC38c) the four that specify delegation notes, or the README paragraph that links "
            "two, are 13.16. ") in subsection_body(text, "12.22")[0]
    # 13.16 follows 13.15, the last subsection of 13 before it, and closes section 13
    assert text.index("\n### 13.15 ") < text.index("\n### 13.16 ") < text.index("\n## 14. ")
    assert CLASS["13.16"] == CLASS["12.22"] == "research notes"
    sizes = dict(measure(text)[1])
    assert sizes["13.16"] <= CAPS["research notes"] and sizes["12.22"] <= CAPS["research notes"]


def test_the_references_to_the_13_16_lines_name_13_16():
    """v1.465 (row DOC43, review iter-325 nits 1 and 2): DESIGN, the research scripts and notes refer to the four
    13.16 lines as 13.16, never as the 12.8 or 12.22 they were before v1.390 or v1.461; the redirects of the 12.22
    and 13.16 Purpose lines stay for references elsewhere."""
    stale = re.compile(r"(?:12\.8|12\.22) v1\.(?:258|402|413|424)\b")
    research = ROOT / "research"
    for path in [DESIGN, *sorted(research.glob("*.py")), *sorted(research.glob("*.md"))]:
        assert not stale.search(path.read_text(encoding="utf-8")), path.name
    pointers = {"reread_sensitivity.py": "(DESIGN 13.16 v1.413, row R38)",
                "delegation_price_sensitivity.py": "(DESIGN 13.16 v1.424, row R39)",
                "ledger_cost_model.py": "(DESIGN 13.16 v1.402)"}
    for name, pointer in pointers.items():
        docstring = (research / name).read_text(encoding="utf-8").split('"""', 2)[1]
        assert pointer in docstring and "DESIGN 12.22" not in docstring, name
    note = (research / "delegation-price-sensitivity.md").read_text(encoding="utf-8")
    assert "([DESIGN.md](../DESIGN.md) 13.16)" in note and "([DESIGN.md](../DESIGN.md) 12.22)" not in note
    text = DESIGN.read_text(encoding="utf-8")
    v1328 = [line for line in subsection_body(text, "13.8")
             if line.startswith("- v1.328, per-item delegation paths on the response bank (row R29): ")]
    assert len(v1328) == 1 and "the Where delegation pays at a glance paragraph (13.16 v1.258) " in v1328[0]


def test_the_12_opening_gives_the_research_notes_cap_and_the_12_total():
    opening = DESIGN.read_text(encoding="utf-8").split("\n## 12. ", 1)[1].split("\n### ", 1)[0].splitlines()
    caps = [line for line in opening if line.startswith("- Caps, each a ceiling ")]
    assert len(caps) == 1
    assert "; the research notes 12.22 (v1.390, row DOC21o) and 13.16 (v1.461, row DOC38c), 40,000 each;" in caps[0]
    assert ("; and the totals `## 12.` 405,000 and `## 13.` 284,000 (v1.456, row DOC37, v1.461, row DOC38c, v1.468, "
            "row E25a, v1.478, row E26a, v1.481, row E26c, v1.498, row E27a, v1.523, row STRAT3f, v1.528, row "
            "STRAT3h, and v1.541, row ESC3c), "
            in caps[0])
    assert (CAPS["research notes"], SECTION_CAPS["12"], SECTION_CAPS["13"]) == (40_000, 405_000, 284_000)
    moved = [line for line in opening if line.startswith("- Research notes out of 12.8 (v1.390, row DOC21o): ")]
    assert len(moved) == 1
    for words in ("are 12.22, a research-notes spec with a cap of 40,000 bytes, in the same order",
                  # review iter-325 should-fix 1 (v1.461)
                  "in the same order (the at-a-glance one 13.16 from v1.461, row DOC38c), since",
                  "The `## 12.` total was 300,000 bytes from v1.390 to v1.455: the 260,000 of v1.386 counted these "
                  "bullets inside the "
                  "50,000 of 12.8, and they now have a cap of their own, 40,000"):
        assert words in moved[0], words


# --- the section totals (DESIGN 12 v1.456, row DOC37) ---------------------------------------------

CAPS_OPENING = ("- Caps, each a ceiling that stops a subsection from growing back, while the keep rules below "
                "set its size: ")
# The opening of each class's clause in the Caps bullet, whose clauses are joined by `; `.
CAPS_CLAUSES = {
    "contract": "the contract, ",
    "converter": "a converter spec, ",
    "routing results": "a routing results spec, ",
    "delegation results": "a delegation results spec, ",
    "README evidence": "the README evidence spec ",
    "research notes": "the research notes ",
    "workflow": "the workflow ",
    "limits and test status": "the limits and test status ",
    "delegation evaluator": "the delegation evaluator ",
}
NAMED = re.compile(r"(?<![\d.])(1[23])\.(\d+)(?: to \1\.(\d+))?(?!\d)")
# An amount ends before a digit or a comma and a digit, so `50,000, with` gives 50,000.
AMOUNT = re.compile(r"(?<![\d.,])\d{1,3}(?:,\d{3})+(?!,?\d)")
TOTAL = re.compile(r"`## (1[23])\.` (\d{1,3}(?:,\d{3})+)")


def by_number(number):
    return tuple(int(part) for part in number.split("."))


def caps_bullet(text):
    """The one Caps bullet of the DESIGN 12 opening in `text`."""
    opening = text.split("\n## 12. ", 1)[1].split("\n### ", 1)[0].splitlines()
    caps = [line for line in opening if line.startswith(CAPS_OPENING)]
    assert len(caps) == 1
    return caps[0]


def caps_bullet_problems(bullet, groups=GROUPS, caps=CAPS, section_caps=SECTION_CAPS):
    """Every way the Caps bullet disagrees with `groups`, `caps` and `section_caps`, as messages: each class
    has one clause, which names exactly the subsections of its class (`12.1 to 12.5` names five) and gives
    its cap as its first amount, and the bullet gives each section total once, as `## N.` and the amount."""
    if not bullet.startswith(CAPS_OPENING):
        return ["the Caps bullet does not open with its opening"]
    parts = bullet[len(CAPS_OPENING):].split("; ")
    found = []
    for kind, opening in CAPS_CLAUSES.items():
        clauses = [part for part in parts if part.startswith(opening)]
        if len(clauses) != 1:
            found.append(f"the Caps bullet has {len(clauses)} clauses opening `{opening.strip()}`, not one")
            continue
        named = set()
        for section, first, last in NAMED.findall(clauses[0]):
            named.update(f"{section}.{n}" for n in range(int(first), int(last or first) + 1))
        missing = sorted(set(groups[kind]) - named, key=by_number)
        extra = sorted(named - set(groups[kind]), key=by_number)
        if missing:
            found.append(f"the {kind} clause lacks {', '.join(missing)}")
        if extra:
            found.append(f"the {kind} clause names {', '.join(extra)}, not of its class")
        amounts = AMOUNT.findall(clauses[0])
        if not amounts or number_of(amounts[0]) != caps[kind]:
            found.append(f"the {kind} clause gives {amounts[0] if amounts else 'no amount'}, not its cap "
                         f"{caps[kind]:,}")
    # Review iter-319 nit 3: the line cap's clause too, which no class clause holds.
    if [part for part in parts if part.startswith("any line of 12 or 13 ")] != [f"any line of 12 or 13 {LINE_CAP:,}"]:
        found.append(f"the Caps bullet does not give the line cap once as `any line of 12 or 13 {LINE_CAP:,}`")
    for section in SECTIONS:
        given = [amount for number, amount in TOTAL.findall(bullet) if number == section]
        if len(given) != 1:
            found.append(f"the Caps bullet gives `## {section}.` {len(given)} times, not once")
        elif number_of(given[0]) != section_caps[section]:
            found.append(f"the Caps bullet gives `## {section}.` {given[0]}, not {section_caps[section]:,}")
    return found


def test_the_caps_bullet_names_each_subsection_in_its_class_and_the_totals():
    assert set(CAPS_CLAUSES) == set(GROUPS)
    assert caps_bullet_problems(caps_bullet(DESIGN.read_text(encoding="utf-8"))) == []


@pytest.mark.parametrize("old, new, message", [
    (", the registry-pair converter 12.23 (v1.431)", "", ["the converter clause lacks 12.23"]),
    (" and the ledger hand-off converter 13.15 (v1.394)", "", ["the converter clause lacks 13.15"]),
    ("12.21, the registry-pair results 12.24 (v1.433), the Longtail-SWE results 12.26 (v1.481), the AutoBench slice "
     "results 12.27 (v1.523), the LiveCodeBench slice results 12.28 (v1.528) and the tau2-bench cascade results 12.29 "
     "(v1.541)", "12.21, 12.24, 12.25, 12.26, 12.27, 12.28 and 12.29",
     ["the routing results clause names 12.25, not of its class"]),
    ("the contract, 12.1 to 12.5 and", "the contract, 12.1 to 12.4 and",
     ["the contract clause lacks 12.5"]),
    ("16,000 bytes each", "15,000 bytes each", ["the contract clause gives 15,000, not its cap 16,000"]),
    ("; the workflow 12.13 25,000", "", ["the Caps bullet has 0 clauses opening `the workflow`, not one"]),
    ("`## 12.` 405,000", "`## 12.` 390,000", ["the Caps bullet gives `## 12.` 390,000, not 405,000"]),
    # v1.478 (row E26a)
    (", the Longtail-SWE converter 12.25 (v1.478)", "", ["the converter clause lacks 12.25"]),
    # v1.481 (row E26c)
    (", the Longtail-SWE results 12.26 (v1.481)", "", ["the routing results clause lacks 12.26"]),
    # v1.523 (row STRAT3f)
    (", the AutoBench slice results 12.27 (v1.523)", "", ["the routing results clause lacks 12.27"]),
    # v1.528 (row STRAT3h)
    (", the LiveCodeBench slice results 12.28 (v1.528)", "", ["the routing results clause lacks 12.28"]),
    # v1.541 (row ESC3c)
    (" and the tau2-bench cascade results 12.29 (v1.541)", "", ["the routing results clause lacks 12.29"]),
    ("`## 13.` 284,000", "`## 13.` 262,000", ["the Caps bullet gives `## 13.` 262,000, not 284,000"]),
    (" and `## 13.` 284,000", "", ["the Caps bullet gives `## 13.` 0 times, not once"]),
    # v1.468 (row E25a)
    (", the registry-pair delegation results 13.17 (v1.468)", "", ["the delegation results clause lacks 13.17"]),
    # v1.498 (row E27a)
    (" and the Longtail-SWE delegation results 13.18 (v1.498)", "", ["the delegation results clause lacks 13.18"]),
    # v1.461 (row DOC38c)
    (" and 13.16 (v1.461, row DOC38c)", "", ["the research notes clause lacks 13.16"]),
    ("; any line of 12 or 13 6,000", "",
     ["the Caps bullet does not give the line cap once as `any line of 12 or 13 6,000`"]),
    ("any line of 12 or 13 6,000", "any line of 12 or 13 8,000",
     ["the Caps bullet does not give the line cap once as `any line of 12 or 13 6,000`"]),
])
def test_a_broken_caps_bullet_is_named(old, new, message):
    bullet = caps_bullet(DESIGN.read_text(encoding="utf-8"))
    assert bullet.count(old) == 1, old
    assert caps_bullet_problems(bullet.replace(old, new, 1)) == message


def test_each_total_is_its_base_raised_by_the_cap_of_each_subsection_added_after_it():
    raised, added = {}, []
    for section, (base, _, last) in TOTAL_BASES.items():
        later = [number for number in CLASS if number.split(".")[0] == section and by_number(number)[1] > last]
        added += later
        raised[section] = base + sum(CAPS[CLASS[number]] for number in later)
    assert sorted(added, key=by_number) == ["12.23", "12.24", "12.25", "12.26", "12.27", "12.28", "12.29", "13.15",
                                                "13.16", "13.17", "13.18"]
    assert raised == SECTION_CAPS == {"12": 405_000, "13": 284_000}


def test_the_projected_totals_fit_the_totals_the_caps_bullet_states():
    # v1.456 (row DOC37): before it, the 12.23, 12.24 and 13.15 growth left the projected totals over the
    # stated 300,000 and 185,000, which only the last trim would have found.
    text = DESIGN.read_text(encoding="utf-8")
    stated = {number: number_of(amount) for number, amount in TOTAL.findall(caps_bullet(text))}
    assert PENDING and stated == SECTION_CAPS
    sections, subsections, _, _ = measure(text)
    totals = projected(sections, subsections)
    assert {number: (totals[number], stated[number]) for number in SECTIONS if totals[number] > stated[number]} == {}


def test_the_section_totals_bullet_gives_each_base_and_each_raise():
    opening = DESIGN.read_text(encoding="utf-8").split("\n## 12. ", 1)[1].split("\n### ", 1)[0].splitlines()
    bullets = [line for line in opening if line.startswith("- Section totals (v1.456, row DOC37): ")]
    assert len(bullets) == 1
    (base12, set12, last12), (base13, set13, last13) = TOTAL_BASES["12"], TOTAL_BASES["13"]
    for words in (f"`## 12.` the {base12:,} of {set12}, which counts 12.1 to 12.{last12}, plus 15,000 for each of "
                  f"12.23 (v1.431), 12.24 (v1.433), 12.25 (v1.478), 12.26 (v1.481), 12.27 (v1.523), 12.28 (v1.528) and "
                  f"12.29 (v1.541), "
                  f"so {SECTION_CAPS['12']:,}",
                  f"`## 13.` the {base13:,} of {set13}, which counts 13.1 to 13.{last13}, plus 15,000 for 13.15 "
                  f"(v1.394), 40,000 for 13.16 (v1.461) and 22,000 for each of 13.17 (v1.468) and 13.18 (v1.498), "
                  f"so {SECTION_CAPS['13']:,}",
                  "once `PENDING` is empty and, until then, the section with each `PENDING` subsection cut to "
                  "exactly its cap and the rest as measured"):
        assert words in bullets[0], words
    assert (CAPS["converter"], CAPS["routing results"]) == (15_000, 15_000)


def test_the_12_8_size_budget_clause_holds_no_history():
    # v1.390: the 0b3e142 sizes, the DOC19a to DOC19k plan and the ceilings' history are in CHANGELOG.md,
    # behind the clause's two pointers (POINTERS).
    body = subsection_body(DESIGN.read_text(encoding="utf-8"), "12.8")
    start = [i for i, line in enumerate(body) if line.startswith("- Size budget (v1.334, row DOC19): ")]
    assert len(start) == 1
    clause = body[start[0]:]
    # Ten lines to v1.443; v1.444 (row DOC28a) adds the room bullet, and v1.473 (row DOC44a) the plan bullet.
    assert clause[-1] == "" and all(line.startswith("  - ") for line in clause[1:-1]) and len(clause) == 12
    for words in ("0b3e142", "DOC19a to DOC19k", "from review", "This clause changes no README text",
                  "for 10 names", "v1.346 and v1.347"):
        assert not [line[:60] for line in clause if words in line], words


def test_the_12_22_lines_of_v1_124_to_v1_191_hold_no_scope_or_restated_history():
    # DOC34 (v1.421): what the trim dropped stays out, and each of the eight lines keeps one pointer.
    body = notes_body(DESIGN.read_text(encoding="utf-8"))
    trimmed = [line for line in body if line.startswith(DOC34_LINES)]
    assert len(trimmed) == 8
    for words in ("No change under", "no transcript changes", "the bound the router uses", "hash split varies",
                  "review iter-", "the mean over seeds of each seed's pooled success", "two middle gaps",
                  "the cost ratios rest", "no committed row measures", "confidence cascade",
                  "So the 5.3 route is always", "as on the pooled line", "every attempt's recorded cost spent",
                  "and from v1.341", "`, from v1.341 `", "no committed file holds a seed's value",
                  "five of v1.124", "seven in all", "round(success * half)",
                  "as does a `cost_blind` `better` row"):  # the last four: review iter-282 nit 2
        assert not [line[:60] for line in trimmed if words in line], words
    for line in trimmed:
        assert len(POINTER.findall(line)) == 1, line[:60]


# DOC34b (v1.422): each phrase a 12.22 line uses for a rule another line states, with the opening of
# the line that states it and the words that state it, which that line alone holds among the eight.
BORROWED = (
    ("its prose numbers obey the per-task ceiling bullet's rule", "- Per-task ceiling on RouterBench (v1.146): ",
     "every number of its prose outside the block, a link target and a code span is in that output or is a "
     "DESIGN section number"),
    ("compared as in the seed by seed bullet", "- Seed by seed on LLMRouterBench (v1.177): ",
     "compared byte for byte with the script's lines on the matrix that the 12.19 session fixture "
     "`llmrouterbench_pinned` writes when the pinned file is cached, skipped otherwise"),
    # v1.460 (row DOC38b, review iter-321 nit 3): the exit list names the best single model's error
    ("on what stops the seed by seed script", "- Seed by seed on LLMRouterBench (v1.177): ",
     "Exit 0, or 2 with one `error: ` line on a missing or unreadable file, a row `load_outcomes` refuses, a "
     "missing key, a best single model that differs between bars or flavors or a row that differs from the "
     "committed one."),
    ("`max_fallbacks` M as there", "- Fallback on a failed check, on LLMRouterBench (v1.181): ",
     "`max_fallbacks` of 0, 2 and M, the number of pool models minus one, M giving the whole list that 5.3 sorts"),
    ("pass that bullet's checks against the committed rows", "- Fallback on a failed check, on LLMRouterBench (v1.181): ",
     "It stops unless, at both bars and in each flavor, `max_fallbacks` 0's success and cost are the committed "
     "summary's `routed` row and each task's are the committed `per_task` `routed` row, and the oracle's (12.3) "
     "the committed `oracle` row, each within a relative 1e-12."),
    # v1.457 (row DOC38a)
    ("The best single model is the where-routing-pays bullet's", "- Where routing pays (v1.124): ",
     "the best single model of 12.7 (highest held-out success, then lower cost, then ID; a file where it differs "
     "between bars or flavors is an error)"),
)


def test_the_12_22_lines_that_borrow_a_rule_find_it_in_the_line_they_name():
    body = notes_body(DESIGN.read_text(encoding="utf-8"))
    trimmed = [line for line in body if line.startswith(DOC34_LINES)]
    assert len(trimmed) == 8
    for phrase, lender, rule in BORROWED:
        borrowers = [line[:40] for line in trimmed if phrase in line]
        assert borrowers and all(not b.startswith(lender[:40]) for b in borrowers), phrase
        # v1.457: by the whole opening, since the where-routing-pays one is shorter than 40 characters
        holders = [line for line in trimmed if rule in line]
        assert len(holders) == 1 and holders[0].startswith(lender), rule[:60]
    # the words v1.422 dropped: explanations, a restated 12.3 seed value, and the rules now borrowed
    for words in ("its script `research/", "so a file added later moves the range", "the note's main claim",
                  "a code span holds a model ID", "instead of being skipped", "so the README test runs in CI",
                  "The second finding names", "checked reader", "with the whole list", "whole-list route",
                  "and so is the attempts per held-out item", "correct held-out items over held-out items"):
        assert not [line[:60] for line in trimmed if words in line], words


# --- room in 12.22 again (v1.457, row DOC38a) ------------------------------------------------------

# Each clause v1.457 dropped from 12.22, with the versions it named (each must keep its CHANGELOG.md line):
# explanations of why a rule holds, definitions another section owns, and what a later slice would do.
DOC38A_DROPPED = (
    ("a note the script does not read", ()),
    ("(the highest calibration bound)", ()),
    ("(size and sha256)", ()),
    ("(the restricted unpickler)", ()),
    ("so the matrix is the 12.6 default one", ()),
    ("from which the shortfall at that success is within the margin", ()),
    ("the one of the committed routing files (the v1.166 clauses", ("v1.166",)),
    ("(the `model:` row with the highest held-out success, then lower cost, then ID; a file where it differs", ()),
    ("(the same at every one, 12.3 v1.135)", ("v1.135",)),
    ("which the README's LLMRouterBench lines rest on", ()),
    ("since LLMRouterBench records every pool model on every item", ()),
    ("`split_items` halves of the matrix, then 12.3's registry and `Task`", ()),
    ("(every passing model when one passes, else every eligible measured one)", ()),
    ("which 5.3 does not do by default", ()),
    ("come from the passing list alone", ()),  # review iter-321 nit 1
    ("whose 5.2 `routing_cost` is 0.0", ()),
    ("so that decision is one it makes anyway", ()),
    ("since 13.2 prices both paths at the parent's and the primary's prices alone", ()),
    ("policies frozen before the final answers", ()),
)


def test_12_22_holds_none_of_the_clauses_v1_457_dropped():
    text = DESIGN.read_text(encoding="utf-8")
    body = "\n".join(notes_body(text))  # 13.16 too from v1.461 (row DOC38c)
    logged = set(CHANGELOG_LINE.findall(CHANGELOG.read_text(encoding="utf-8")))
    for words, versions in DOC38A_DROPPED:
        assert words not in body, words
        for version in versions:
            assert version[1:] in logged, version
    # what stays of the clauses it shortened
    for words in ("which 5.3 does only with the task's `fallback_below_bar` (4.2, v1.201) on.",
                  "The best single model is the where-routing-pays bullet's, read from the committed summary.",
                  "the release's own protocol (each question family in one split, which the script counts)"):
        assert body.count(words) == 1, words
    assert dict(measure(text)[1])["12.22"] <= CAPS["research notes"]


# --- room in 12.22, second part (v1.460, row DOC38b) ----------------------------------------------

# Each wording v1.460 replaced with a shorter one stating the same contract (none names a version).
DOC38B_DROPPED = (
    "(the `model:` summary row with the highest held-out success, then lower cost, then ID)",
    "one line with the file, its revision",
    "the matrix of the 12.19 commands",
    "the repository root that holds",
    "replaying a check as good as the record's score",
    "one line saying what a route and an attempt are",
    "whose first bullet says, as the check fallback note's does,",
    "(its success minus the 5.3 route's) over (the oracle's minus the 5.3 route's)",
    "A second test checks that on LLMRouterBench",
    "A fourth test checks that the registry pair",
    "in option order with a blank line between datasets",
    # review iter-324 must-fix 1: the script prints the cells' held-out items in all, and per task the cells
    "with their held-out items per task",
)


def test_12_22_holds_none_of_the_wordings_v1_460_replaced():
    text = DESIGN.read_text(encoding="utf-8")
    body = "\n".join(notes_body(text))  # 13.16 too from v1.461 (row DOC38c)
    for words in DOC38B_DROPPED:
        assert words not in body, words
    # what replaced them, each once
    for words in ("and runs `evaluate` (12.3) on `cost_blind` alone at the first bar",
                  "whose best single model is 12.7's.",
                  "the 12.18 converter's output that the 12.19 commands write",
                  "buys on public data, for a check as good as the record's score.",
                  "`## Facts` (its first bullet: every number is an upper bound, as in the check fallback note)",
                  "and tests check: (v1.126) on the first five files (v1.166) and the eighth (v1.458), that no routed",
                  "Per dataset, in option order, a blank line between, it prints",
                  "with their held-out items in all and their count by task for at most five tasks, else the count "
                  "of tasks with such a cell"):
        assert body.count(words) == 1, words
    assert dict(measure(text)[1])["12.22"] <= CAPS["research notes"]


# --- the rest of 12.13 (DESIGN 12 v1.392, row DOC21c) ---------------------------------------------

def test_12_13_states_its_contract_as_it_is_and_holds_no_growth_history():
    import test_evidence_workflow as workflow
    text = DESIGN.read_text(encoding="utf-8")
    body = subsection_body(text, "12.13")
    joined = "\n".join(body)
    assert "12.13" not in PENDING and dict(measure(text)[1])["12.13"] <= CAPS["workflow"]
    # The counts are the ones the workflow and its tests hold now.
    compare = [line for line in workflow.workflow_text().splitlines() if "git diff --exit-code --" in line]
    # ledger v1.397, registry pair v1.443, its delegation v1.472, Longtail-SWE v1.489, AutoBench slices v1.525,
    # LiveCodeBench slices v1.530, tau2-bench cascades v1.544
    assert len(compare) == 1 and compare[0].count(" evidence/") == 22
    assert body[0].startswith("Purpose: a reader can see the twenty-two results files of the `Compare` step below ")
    assert f"each of {len(workflow.MUTANTS)} broken workflows fails the check" in joined
    commands, run = workflow.expected_commands(workflow.readme()), workflow.regenerate_commands(workflow.readme())
    # v1.397 (row E23c): after the README commands it runs, the ledger RESULTS.md line, from v1.443
    # (row E24e) the registry-pair RESULTS.md block, from v1.472 (row E25c) its delegation one and from
    # v1.489 (row E26d) the Longtail-SWE one
    taken = workflow.results_md_commands()
    registry, delegation = workflow.registry_commands(), workflow.registry_delegation_commands()
    longtail = workflow.longtail_commands()
    assert taken == [workflow.ledger_command()] + registry + delegation + longtail and len(taken) == 13
    # the 13.17 block opens with the 12.23 converter line the registry-pair lines already ran
    kept = [workflow.ledger_command()] + registry + delegation[1:] + longtail
    # v1.525 (row STRAT3g): the 12.27 `## Slices` block, no `## Regenerate` block, all nine lines, and from v1.530
    # (row STRAT3i) the three of the 12.28 one, then from v1.544 (row ESC3e) the three of the 12.29 `## Cascades`
    # block, run last
    slices = (workflow.slices_commands() + workflow.slices_commands(workflow.LCB_SLICES_NOTES)
              + workflow.cascade_commands())
    assert run[-len(kept) - len(slices):] == kept + slices and not set(taken + slices) & set(commands)
    readme_run = len(run) - len(kept) - len(slices)
    assert f"so the README holds {len(commands)} rerun commands and `Regenerate` runs {readme_run} of them, " \
           f"and of the {len(taken)} lines it takes from `## Regenerate` blocks, {len(kept)}." in joined
    # Review iter-251 should-fix 2: the other counts, each from the list or file it counts.
    import test_ci_permissions as permissions
    import test_ci_pythons as pythons
    words = {6: "6", 10: "ten", 11: "eleven", 12: "12", 14: "14"}
    blocks = sum(workflow.BLOCKS.get(name, 1) for name in workflow.SUBSECTIONS)
    assert blocks == len(workflow.SUBSECTIONS) + 1  # two blocks in `### Delegation on tau2-bench`
    for shown in (f"a command in one of the {words[blocks]} README regenerate blocks the workflow reruns",
                  f"names the {words[len(workflow.SUBSECTIONS)]} subsections whose commands it reruns",
                  f"then the {words[len(workflow.SUBSECTIONS)]} names in README heading order",
                  f"the README holds those {words[len(workflow.SUBSECTIONS)]} `### ` headings in that order",
                  f"check it on {words[len(workflow.RUN_ONCE_CASES)]} hand-built lists",
                  f"each of {words[len(workflow.RUNNER_MUTANTS)]} broken pairs fails it",
                  f"each of {words[len(pythons.MUTANTS)]} broken variants of those four files fails the check",
                  f"each of {len(permissions.MUTANTS)} broken pairs fails with the one problem it names"):
        assert shown in joined, shown
    # The steps bullet names every rerun subsection, in order, the response-bank delegation one too.
    steps = [line for line in body if line.startswith("- Steps, in this order: ")]
    assert len(steps) == 1
    at = [steps[0].index(f"`### {name}`") for name in workflow.SUBSECTIONS]
    assert at == sorted(at)
    # The history sentences the trim dropped (v1.391 text) are behind the pointers.
    for words in ("When v1.65 was written", "On one laptop", "Expected time", "Measured (v1.301", "(10 to v1.119)",
                  "(11 from v1.139)", "In run 42814244636", "In run 43008722362", "three to v1.54"):
        assert words not in joined, words
    heading = [line for line in text.splitlines() if line.startswith("### 12.13 ")]
    # v1.397 (row E23c): the heading names no entry a bullet of 12.13 opens with, and ends with the ledger
    # line; from v1.443 (row E24e) with the registry pair, from v1.472 (row E25c) with its delegation and
    # from v1.489 (row E26d) with Longtail-SWE
    assert len(heading) == 1 and heading[0].endswith(
        "; ledger hand-off v1.397; registry pair v1.443; registry-pair delegation v1.472; Longtail-SWE v1.489"
        "; AutoBench slices v1.525; LiveCodeBench slices v1.530; tau2-bench cascades v1.544)")
    # v1.544 (row ESC3e): the reason and the aside two lines dropped stay out
    for words in ("which GitHub moves to Ubuntu 26.04", "so leaving it out changes only the log",
                  "which a reflow keeps", "the same manifest lists 3.15.2", "would go unseen until a run missed"):
        assert words not in joined, words
    # v1.530 (row STRAT3i): the asides and growth history four lines dropped stay out
    for words in ("(so a failing command stops the step)", "(one per rerun subsection and two in",
                  "from v1.299 12.20", "the registry pair v1.443, its delegation v1.472",
                  "after the registry-pair lines, `Regenerate`", "reads the matrix those lines write"):
        assert words not in joined, words
    # v1.443: the restatements the three `is rerun` lines dropped stay out
    for words in ("directly after `pooled.json`", "names it next to last", "after the four `### LLMRouterBench` lines",
                  "`SUBSECTIONS` holds it after"):
        assert words not in joined, words
    for words in ("pinned runner v1.49", "Python versions v1.118", "token permissions v1.137", "time limit v1.152",
                  "one run of a repeated line v1.215", "no cache between runs v1.251"):
        assert words not in heading[0], words
    assert "restated" not in heading[0] and "(history: " not in heading[0]
