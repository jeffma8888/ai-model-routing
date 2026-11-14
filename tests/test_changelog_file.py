"""DESIGN 15 v1.326 (row DOC18): from v1.327 the changelog is CHANGELOG.md at the repo root.

It opens with HEADER, `# Changelog` and one paragraph saying it continues section 15 of
DESIGN.md and keeps its version numbers; every line after the header is a changelog line in the
`- vX.Y (YYYY-MM-DD` form, and their versions ascend: no line's version is lower than the one
before it, so a new line goes at the end and the last line holds the highest version. DESIGN.md's
`## 15. Changelog` stays its last section and holds one line, POINTER_LINE. The Status line is
checked against the file's versions in tests/test_design_status.py (v1.159, v1.247).

DESIGN 15 v1.361 (row DOC24): the header gains a second paragraph, so every line from v1.361 on
(FIRST_CAPPED) is at most CAP bytes in UTF-8 without its newline and opens with LEAD: version,
date and an optional note, a kind made of KINDS words joined by `, ` and ` and `, then the
sections and the row in parentheses, with anything after the row (the review it answers), and
`. `; the change after the lead is at most two sentences, a `. ` ending each but the last, which
ends at the line's final full stop. The lines before v1.361 keep their length, so they are not
checked."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "DESIGN.md"
CHANGELOG = ROOT / "CHANGELOG.md"
HEADING = "## 15. Changelog"
POINTER_LINE = ("The changelog is in [CHANGELOG.md](CHANGELOG.md), from v1.0, oldest first, with the "
                "version numbers it had here, so a `15 vX.Y` reference names its line there.")
HEADER = [
    "# Changelog",
    "",
    "This file continues section 15 (Changelog) of [DESIGN.md](DESIGN.md) and keeps its version "
    "numbers, so a `DESIGN 15 vX.Y` reference names the line of version vX.Y here. One line per "
    "change, `- vX.Y (YYYY-MM-DD...): ...`, oldest first; a new line goes at the end.",
    "",
    "From v1.361 a line is at most 600 bytes in UTF-8, without its newline, and holds, in this "
    "order: the version and the date (a note may follow the date after a comma), the kind of "
    "change (`spec`, `code`, `tests`, `docs`, `data` or `CI`, joined by `, ` and ` and `), the "
    "DESIGN sections and the row in parentheses, with any review it answers after the row, and "
    "then the change in at most two sentences, each ending at a `. ` or the line's final full "
    "stop: `- v1.361 (2026-11-14): docs and tests (15, row DOC24). The change.`. Byte counts, "
    "bullet lists and test names stay in DESIGN, the tests and the commit message; the lines "
    "before v1.361 keep their length.",
    "",
]
ENTRY = re.compile(r"^- v(\d+)\.(\d+) \((\d{4}-\d{2}-\d{2})[,)]")
FIRST_CAPPED = (1, 361)
CAP = 600
KINDS = ("spec", "code", "tests", "docs", "data", "CI")
_KIND = "(?:" + "|".join(KINDS) + ")"
LEAD = re.compile(
    r"^- v\d+\.\d+ \(\d{4}-\d{2}-\d{2}(?:, [^()]+)?\): "
    + _KIND + r"(?:(?:, | and )" + _KIND + r")* "
    r"\((?:\d+(?:\.\d+)*, )+row [A-Z]+\d+[a-z]?(?:, [^()]+)?\)\. (?P<change>.+)$"
)


def shown(version):
    return f"v{version[0]}.{version[1]}"


def changelog_problems(text):
    """Every way CHANGELOG.md breaks v1.326, one line each; [] when none."""
    if not text.endswith("\n") or text.endswith("\n\n"):
        return ["CHANGELOG.md does not end with one newline"]
    lines = text[:-1].split("\n")
    if lines[:len(HEADER)] != HEADER:
        return ["CHANGELOG.md does not open with its header"]
    problems = []
    highest = None
    for number, line in enumerate(lines[len(HEADER):], start=len(HEADER) + 1):
        found = ENTRY.match(line)
        if found is None:
            problems.append(f"CHANGELOG.md line {number} is not a `- vX.Y (YYYY-MM-DD` line: {line[:60]!r}")
            continue
        version = (int(found[1]), int(found[2]))
        if highest is not None and version < highest:
            problems.append(f"CHANGELOG.md line {number} has {shown(version)} after {shown(highest)}")
        highest = version if highest is None else max(highest, version)
    if highest is None:
        problems.append("CHANGELOG.md has no changelog line")
    return problems


def capped_line_problems(text):
    """Every way a line from FIRST_CAPPED on breaks v1.361, one line each; [] when none."""
    problems = []
    for number, line in enumerate(text.split("\n"), start=1):
        found = ENTRY.match(line)
        if found is None or (int(found[1]), int(found[2])) < FIRST_CAPPED:
            continue
        version = f"v{found[1]}.{found[2]}"
        size = len(line.encode("utf-8"))
        if size > CAP:
            problems.append(f"CHANGELOG.md line {number} ({version}) is {size} bytes, over the {CAP}-byte cap")
        lead = LEAD.match(line)
        if lead is None:
            problems.append(f"CHANGELOG.md line {number} ({version}) does not open with `<kind> (<sections>, row <ID>). `")
            continue
        change = lead["change"]
        if not change.endswith("."):
            problems.append(f"CHANGELOG.md line {number} ({version}) does not end with a full stop")
        sentences = change.count(". ") + 1
        if sentences > 2:
            problems.append(f"CHANGELOG.md line {number} ({version}) has {sentences} sentences after its lead, not at most 2")
    return problems


def section_problems(text):
    """Every way DESIGN.md's section 15 breaks v1.326, one line each; [] when none."""
    lines = text.split("\n")
    if lines.count(HEADING) != 1:
        return [f"DESIGN.md has {lines.count(HEADING)} {HEADING!r} lines, not one"]
    after = lines[lines.index(HEADING) + 1:]
    if after != [POINTER_LINE, ""]:
        return [f"{HEADING!r} is followed by {len(after) - 1} line(s), not the one pointer line and the end"]
    return []


def read(path):
    return path.read_text(encoding="utf-8")


def test_the_changelog_file_has_its_header_and_ascending_versions():
    assert changelog_problems(read(CHANGELOG)) == []


def test_design_15_is_the_one_pointer_line():
    assert section_problems(read(DESIGN)) == []


def _entries(text):
    return [k for k, line in enumerate(text.split("\n")) if ENTRY.match(line)]


def _swapped(text):
    """The last two lines of different versions swapped, so the later version comes first."""
    lines = text.split("\n")
    rows = _entries(text)
    last = rows[-1]
    top = ENTRY.match(lines[last])
    before = next(k for k in reversed(rows) if ENTRY.match(lines[k]).group(1, 2) != top.group(1, 2))
    lines[before], lines[last] = lines[last], lines[before]
    return "\n".join(lines)


def _blank_line(text):
    lines = text.split("\n")
    rows = _entries(text)
    lines.insert(rows[len(rows) // 2], "")
    return "\n".join(lines)


CHANGELOG_BROKEN = {
    "the last two versions swapped": _swapped,
    "a blank line among the lines": _blank_line,
    "a line in another form": lambda text: text + "* v1.999 (2026-11-13): a star bullet\n",
    "a version below the last": lambda text: text + "- v1.1 (2026-11-13): an old version at the end\n",
    "the header dropped": lambda text: text.split("\n", len(HEADER))[len(HEADER)],
    "the header paragraph changed": lambda text: text.replace("keeps its version numbers", "renumbers", 1),
    "the cap paragraph changed": lambda text: text.replace("at most 600 bytes", "at most 900 bytes", 1),
    "no final newline": lambda text: text.rstrip("\n"),
    "two final newlines": lambda text: text + "\n",
}


@pytest.mark.parametrize("name", sorted(CHANGELOG_BROKEN))
def test_a_broken_changelog_file_fails_the_check(name):
    text = read(CHANGELOG)
    assert changelog_problems(text) == []
    mutant = CHANGELOG_BROKEN[name](text)
    assert mutant != text
    assert changelog_problems(mutant) != []


SECTION_BROKEN = {
    "a changelog line left after the pointer": lambda text: text + "- v1.0 (2026-10-29): initial contract\n",
    "the pointer line dropped": lambda text: text.replace(POINTER_LINE + "\n", "", 1),
    "the pointer line changed": lambda text: text.replace("oldest first", "newest first", 1),
    "a section after 15": lambda text: text + "\n## 16. Later\n",
    "a second 15 heading": lambda text: text.replace("\n## 14. ", f"\n{HEADING}\n\n## 14. ", 1),
}


@pytest.mark.parametrize("name", sorted(SECTION_BROKEN))
def test_a_broken_section_15_fails_the_check(name):
    text = read(DESIGN)
    assert section_problems(text) == []
    mutant = SECTION_BROKEN[name](text)
    assert mutant != text
    assert section_problems(mutant) != []


def test_minor_versions_ascend_as_numbers():
    head = "\n".join(HEADER) + "\n"
    good = head + "- v1.9 (2026-01-02): nine\n- v1.9 (2026-01-03, review): its review\n- v1.10 (2026-01-03): ten\n"
    assert changelog_problems(good) == []
    bad = head + "- v1.10 (2026-01-03): ten\n- v1.9 (2026-01-02): nine\n"
    assert changelog_problems(bad) == [f"CHANGELOG.md line {len(HEADER) + 2} has v1.9 after v1.10"]
    assert changelog_problems(head) != []


def test_a_good_section_15_passes():
    text = "# Design: x\n\n## 14. Non-goals\n- one\n\n" + HEADING + "\n" + POINTER_LINE + "\n"
    assert section_problems(text) == []
    assert section_problems(text.replace(POINTER_LINE, POINTER_LINE + "\n- v1.0 (2026-01-01): x")) != []


def test_the_lines_from_v1_361_meet_the_cap_and_the_form():
    text = read(CHANGELOG)
    assert capped_line_problems(text) == []
    capped = [line for line in text.split("\n") if ENTRY.match(line)
              and (int(ENTRY.match(line)[1]), int(ENTRY.match(line)[2])) >= FIRST_CAPPED]
    assert capped, "no changelog line from v1.361 on, so the cap checks nothing"


def _last_line(text, change):
    """The text with its last changelog line replaced by change(line)."""
    lines = text.split("\n")
    last = _entries(text)[-1]
    lines[last] = change(lines[last])
    return "\n".join(lines)


def _padded(line, size):
    """The line lengthened to size bytes inside its last sentence, its form kept."""
    have = len(line.encode("utf-8"))
    assert have < size
    return line[:-1] + " " + "x" * (size - have - 1) + "."


def _three_sentences(line):
    have = LEAD.match(line)["change"].count(". ") + 1
    return line + " More." * (3 - have)


LINE_BROKEN = {
    "the last line one byte over the cap": (lambda line: _padded(line, CAP + 1), "over the 600-byte cap"),
    "a third sentence": (_three_sentences, "3 sentences after its lead"),
    "no row": (lambda line: re.sub(r", row [A-Z]+\d+[a-z]?(?=[,)])", "", line, count=1), "does not open with"),
    "a kind outside KINDS": (lambda line: re.sub(r"\): [^(]+ \(", "): misc (", line, count=1), "does not open with"),
    "no sections": (lambda line: re.sub(r"\((?:\d+(?:\.\d+)*, )+row", "(row", line, count=1), "does not open with"),
    "no final full stop": (lambda line: line[:-1], "does not end with a full stop"),
}


@pytest.mark.parametrize("name", sorted(LINE_BROKEN))
def test_a_broken_new_line_fails_the_cap_check(name):
    text = read(CHANGELOG)
    assert capped_line_problems(text) == []
    change, expected = LINE_BROKEN[name]
    mutant = _last_line(text, change)
    assert mutant != text
    problems = capped_line_problems(mutant)
    assert any(expected in problem for problem in problems), problems


def test_a_new_line_over_the_cap_at_the_end_fails():
    text = read(CHANGELOG)
    extra = "- v1.999 (2026-11-14): docs (15, row DOC24). " + "y" * CAP + ".\n"
    assert capped_line_problems(text + extra) == [
        f"CHANGELOG.md line {len(text.split(chr(10)))} (v1.999) is {len(extra) - 1} bytes, over the 600-byte cap"]


def test_the_cap_is_inclusive_and_the_earlier_lines_are_not_checked():
    head = "\n".join(HEADER) + "\n"
    old = "- v1.360 (2026-11-14): tests (3, row DOC23). " + "z" * 700 + ".\n"
    new = "- v1.361 (2026-11-14, review): docs and tests (15, row DOC24, from review iter-232 nit 1). One. Two."
    at_cap = _padded(new, CAP)
    assert len(at_cap.encode("utf-8")) == CAP
    assert changelog_problems(head + old + at_cap + "\n") == []
    assert capped_line_problems(head + old + at_cap + "\n") == []
    assert capped_line_problems(head + old + _padded(new, CAP + 1) + "\n") != []
    assert capped_line_problems(head + "- v1.361 (2026-11-14): CI (12.13, row CI15). One.\n") == []
    assert capped_line_problems(head + "- v1.361 (2026-11-14): code, docs and tests (4.2, 12.8, row E5c). One.\n") == []
