"""DESIGN 15 v1.159 (row DOC10): the Status line of DESIGN.md names the highest changelog
version first, with the date of the last changelog line of that version, and its parenthesis
opens with a clause on that same version.

The changelog is the `- vX.Y (YYYY-MM-DD` lines after the `## 15. Changelog` heading; earlier
sections hold `- v1.N` sub-bullets (for example `- v1.114, packaging: ...`) that are not
changelog entries, so only the lines after the heading count. After the heading, a bullet that
looks like an entry in another form (`* v1.2 (...`, `-  v1.2 (...`, `- v1.x`) is a problem, not
skipped, so a new entry in another bullet form cannot leave a stale Status line green (v1.160,
review iter-132 nit 1)."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "DESIGN.md"
HEADING = "## 15. Changelog"
ENTRY = re.compile(r"^- v(\d+)\.(\d+) \((\d{4}-\d{2}-\d{2})[,)]")
STATUS = re.compile(r"^Status: v(\d+)\.(\d+), (\d{4}-\d{2}-\d{2}) \(v(\d+)\.(\d+)[ ,]")
LOOKALIKE = re.compile(r"^\s*[-*+]\s+v\d")


def status_problems(text):
    """Every way the Status line disagrees with the changelog, as one line each; [] when none."""
    lines = text.split("\n")
    if lines.count(HEADING) != 1:
        return [f"DESIGN.md has {lines.count(HEADING)} {HEADING!r} lines, not one"]
    start = lines.index(HEADING)
    problems = []
    latest = {}
    for line in lines[start + 1:]:
        if not LOOKALIKE.match(line):
            continue
        found = ENTRY.match(line)
        if found is None:
            problems.append(f"changelog line not in the `- vX.Y (YYYY-MM-DD` form: {line[:60]!r}")
            continue
        latest[(int(found[1]), int(found[2]))] = found[3]
    if not latest:
        return problems + ["the changelog has no `- vX.Y (YYYY-MM-DD` line"]
    top = max(latest)
    top_date = latest[top]
    status = [k for k, line in enumerate(lines) if line.startswith("Status:")]
    if len(status) != 1:
        return problems + [f"DESIGN.md has {len(status)} Status lines, not one"]
    first_heading = next(k for k, line in enumerate(lines) if line.startswith("## "))
    if status[0] > first_heading:
        problems.append("the Status line comes after the first section heading")
    found = STATUS.match(lines[status[0]])
    if found is None:
        return problems + ["the Status line is not in the `Status: vX.Y, YYYY-MM-DD (vX.Y ` form"]
    named = (int(found[1]), int(found[2]))
    shown = lambda v: f"v{v[0]}.{v[1]}"
    if named != top:
        problems.append(
            f"Status names {shown(named)} but the highest changelog version is {shown(top)}")
    if found[3] != top_date:
        problems.append(
            f"Status is dated {found[3]} but the last {shown(top)} changelog line is dated {top_date}")
    opening = (int(found[4]), int(found[5]))
    if opening != named:
        problems.append(f"Status names {shown(named)} but its parenthesis opens with {shown(opening)}")
    return problems


def read():
    return DESIGN.read_text(encoding="utf-8")


def test_the_status_line_names_the_last_changelog_version():
    assert status_problems(read()) == []


def _status_line(text):
    return next(line for line in text.split("\n") if line.startswith("Status:"))


def _swap_status(text, new_line):
    old = _status_line(text)
    assert text.count(old) == 1
    return text.replace(old, new_line, 1)


def _older_status(text):
    found = STATUS.match(_status_line(text))
    minor = int(found[2]) - 1
    line = _status_line(text)
    return _swap_status(text, line.replace(f"v{found[1]}.{found[2]},", f"v{found[1]}.{minor},", 1))


def _other_date(text):
    found = STATUS.match(_status_line(text))
    return _swap_status(text, _status_line(text).replace(f", {found[3]} (", ", 2000-01-01 (", 1))


def _other_opening(text):
    found = STATUS.match(_status_line(text))
    line = _status_line(text)
    head = f"(v{found[4]}.{found[5]}"
    return _swap_status(text, line.replace(head, f"(v{found[4]}.{int(found[5]) - 1}", 1))


def _top(text):
    changelog = text.split("\n" + HEADING + "\n", 1)[1]
    return max((int(m[1]), int(m[2])) for m in re.finditer(ENTRY.pattern, changelog, re.M))


def _newer_entry(text):
    top = _top(text)
    found = STATUS.match(_status_line(text))
    return text.rstrip("\n") + f"\n- v{top[0]}.{top[1] + 1} ({found[3]}): a later entry\n"


def _later_date_on_the_top_version(text):
    top = _top(text)
    return text.rstrip("\n") + f"\n- v{top[0]}.{top[1]} (2999-12-31, review): a later line of it\n"


def _no_status(text):
    return text.replace(_status_line(text) + "\n", "", 1)


def _two_status(text):
    return text.replace(_status_line(text), _status_line(text) + "\n\n" + _status_line(text), 1)


def _broken_entry(text):
    return text.rstrip("\n") + "\n- v1.x (soon): not a version\n"


def _star_entry(text):
    top = _top(text)
    return text.rstrip("\n") + f"\n* v{top[0]}.{top[1] + 1} (2026-11-09): a later entry as a star bullet\n"


def _wide_entry(text):
    top = _top(text)
    return text.rstrip("\n") + f"\n-  v{top[0]}.{top[1] + 1} (2026-11-09): a later entry after two spaces\n"


BROKEN = {
    "the Status version one lower": _older_status,
    "another Status date": _other_date,
    "the parenthesis opens with another version": _other_opening,
    "a higher changelog version": _newer_entry,
    "a later-dated line of the top version": _later_date_on_the_top_version,
    "no Status line": _no_status,
    "two Status lines": _two_status,
    "a changelog line in another form": _broken_entry,
    "a higher version as a star bullet": _star_entry,
    "a higher version after two spaces": _wide_entry,
}


@pytest.mark.parametrize("name", sorted(BROKEN))
def test_a_broken_design_fails_the_check(name):
    text = read()
    mutant = BROKEN[name](text)
    assert mutant != text
    assert status_problems(mutant) != []


def test_sub_bullets_before_the_changelog_do_not_count():
    text = "\n".join([
        "# Design: x",
        "",
        "Status: v1.2, 2026-01-02 (v1.2 does a thing; v1.1 did one)",
        "",
        "## 4. Section",
        "- v1.9, a sub-bullet that is not a changelog entry",
        "- v1.10 (2030-01-01): a changelog-form line before the heading does not count",
        "",
        HEADING,
        "- v1.0 (2026-01-01): first",
        "- v1.1 (2026-01-01): second",
        "- v1.2 (2026-01-01): third",
        "- v1.2 (2026-01-02, review): its review line",
        "",
    ])
    assert status_problems(text) == []
    assert status_problems(text.replace("Status: v1.2, 2026-01-02", "Status: v1.2, 2026-01-01")) != []
    assert status_problems(text.replace("(v1.2 does", "(v1.1 does")) != []


def test_minor_versions_compare_as_numbers():
    doc = "\n".join([
        "# Design: x",
        "",
        "Status: v1.10, 2026-01-03 (v1.10 is newer than v1.9)",
        "",
        "## 1. Problem",
        "",
        HEADING,
        "- v1.9 (2026-01-02): nine",
        "- v1.10 (2026-01-03): ten",
        "",
    ])
    assert status_problems(doc) == []
    older = doc.replace("Status: v1.10, 2026-01-03 (v1.10", "Status: v1.9, 2026-01-02 (v1.9")
    assert status_problems(older) == ["Status names v1.9 but the highest changelog version is v1.10",
                                      "Status is dated 2026-01-02 but the last v1.10 changelog line is dated 2026-01-03"]
