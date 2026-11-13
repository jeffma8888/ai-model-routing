"""DESIGN 15 v1.326 (row DOC18): from v1.327 the changelog is CHANGELOG.md at the repo root.

It opens with HEADER, `# Changelog` and one paragraph saying it continues section 15 of
DESIGN.md and keeps its version numbers; every line after the header is a changelog line in the
`- vX.Y (YYYY-MM-DD` form, and their versions ascend: no line's version is lower than the one
before it, so a new line goes at the end and the last line holds the highest version. DESIGN.md's
`## 15. Changelog` stays its last section and holds one line, POINTER_LINE. The Status line is
checked against the file's versions in tests/test_design_status.py (v1.159, v1.247)."""

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
]
ENTRY = re.compile(r"^- v(\d+)\.(\d+) \((\d{4}-\d{2}-\d{2})[,)]")
RED = pytest.mark.xfail(strict=True, reason="v1.326 red: CHANGELOG.md and the pointer line land in v1.327")


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


@RED
def test_the_changelog_file_has_its_header_and_ascending_versions():
    assert changelog_problems(read(CHANGELOG)) == []


@RED
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
    before = next(k for k in reversed(rows) if ENTRY.match(lines[k])[1:3] != top[1:3])
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
    "no final newline": lambda text: text.rstrip("\n"),
    "two final newlines": lambda text: text + "\n",
}


@RED
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


@RED
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
    assert changelog_problems(bad) == ["CHANGELOG.md line 6 has v1.9 after v1.10"]
    assert changelog_problems(head) != []


def test_a_good_section_15_passes():
    text = "# Design: x\n\n## 14. Non-goals\n- one\n\n" + HEADING + "\n" + POINTER_LINE + "\n"
    assert section_problems(text) == []
    assert section_problems(text.replace(POINTER_LINE, POINTER_LINE + "\n- v1.0 (2026-01-01): x")) != []
