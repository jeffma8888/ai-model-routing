"""DESIGN 12.13 v1.118: the Python versions `ci.yml` tests, the floor `pyproject.toml` states
and the README Development line agree with the list the DESIGN bullet writes.

ci.yml is read as text (no YAML library, so this runs in CI); the jobs themselves are checked on
GitHub, not here."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FILES = {
    "ci": ROOT / ".github" / "workflows" / "ci.yml",
    "design": ROOT / "DESIGN.md",
    "readme": ROOT / "README.md",
    "pyproject": ROOT / "pyproject.toml",
}
BULLET = "- Python versions (v1.118): the `ci.yml` matrix is `["
MATRIX = re.compile(r"^\s+python-version: \[(.*)\]\s*$", re.M)
ITEM = re.compile(r'"(\d+)\.(\d+)"')
README_LINE = re.compile(
    r"^- Run `pytest -q`\. CI runs the suite and the demo on Python (\d+\.\d+) to (\d+\.\d+)$", re.M)
FLOOR = re.compile(r'^requires-python = ">=(\d+\.\d+)"$', re.M)


def texts():
    return {key: path.read_text(encoding="utf-8") for key, path in FILES.items()}


def versions(inner):
    """The `X.Y` strings of a bracket list's inner text, or None if an item is not a quoted X.Y."""
    items = [item.strip() for item in inner.split(",")]
    found = [ITEM.fullmatch(item) for item in items]
    if not items or not all(found):
        return None
    return [(int(m.group(1)), int(m.group(2))) for m in found]


def problems(t):
    """Every way the four files break the v1.118 clause (an empty list when it holds)."""
    found = []
    lists = MATRIX.findall(t["ci"])
    if len(lists) != 1:
        return [f"ci.yml has {len(lists)} python-version lists, not one"]
    matrix = lists[0]
    bullets = [line for line in t["design"].splitlines() if line.startswith(BULLET)]
    if len(bullets) != 1:
        return [f"DESIGN.md has {len(bullets)} v1.118 Python versions bullets, not one"]
    design = bullets[0][len(BULLET):].split("]`", 1)[0]
    if matrix != design:
        found.append(f"the ci.yml matrix [{matrix}] is not the DESIGN list [{design}]")
    parsed = versions(matrix)
    if parsed is None:
        return found + [f"a matrix item is not a quoted X.Y: [{matrix}]"]
    majors = {major for major, _ in parsed}
    minors = [minor for _, minor in parsed]
    if majors != {3} or minors != list(range(minors[0], minors[0] + len(minors))):
        found.append(f"the matrix is not consecutive ascending 3.x versions: [{matrix}]")
    first, last = (f"{major}.{minor}" for major, minor in (parsed[0], parsed[-1]))
    floors = FLOOR.findall(t["pyproject"])
    if floors != [first]:
        found.append(f"requires-python floors {floors}, not the first matrix version {first}")
    readme = README_LINE.findall(t["readme"])
    if readme != [(first, last)]:
        found.append(f"README Development line names {readme}, not {first} to {last}")
    return found


def test_the_ci_pythons_are_the_design_list():
    assert problems(texts()) == []


def test_the_design_list_is_the_one_v1118_states():
    bullets = [line for line in texts()["design"].splitlines() if line.startswith(BULLET)]
    assert len(bullets) == 1
    assert bullets[0].startswith(BULLET + '"3.10", "3.11", "3.12", "3.13", "3.14"]`')


def edit(key, old, new):
    def apply(t):
        assert old in t[key], f"{key}: {old!r} not found"
        out = dict(t)
        out[key] = t[key].replace(old, new, 1)
        return out
    return apply


def both(*edits):
    def apply(t):
        for one in edits:
            t = one(t)
        return t
    return apply


NEW = '"3.10", "3.11", "3.12", "3.13", "3.14"'
MUTANTS = {
    "3.14 dropped from the matrix": edit("ci", NEW, '"3.10", "3.11", "3.12", "3.13"'),
    "3.15 added to the matrix": edit("ci", NEW, NEW + ', "3.15"'),
    "3.12 dropped from the matrix and the DESIGN list": both(
        edit("ci", '"3.11", "3.12", ', '"3.11", '), edit("design", '"3.11", "3.12", ', '"3.11", ')),
    "two versions swapped in both": both(
        edit("ci", '"3.13", "3.14"', '"3.14", "3.13"'),
        edit("design", '"3.13", "3.14"', '"3.14", "3.13"')),
    "3.10 dropped while requires-python stays": both(
        edit("ci", '"3.10", ', ""), edit("design", '"3.10", ', ""),
        edit("readme", "on Python 3.10 to", "on Python 3.11 to")),
    "requires-python raised with 3.10 kept": edit(
        "pyproject", 'requires-python = ">=3.10"', 'requires-python = ">=3.11"'),
    "the README naming 3.13 as the last": edit("readme", "3.10 to 3.14", "3.10 to 3.13"),
    "a second python-version list": edit(
        "ci", "    steps:\n", '        python-version: ["3.9"]\n    steps:\n'),
    "an unquoted version in both": both(
        edit("ci", '"3.11"', "3.11"), edit("design", '"3.11", "3.12"', '3.11, "3.12"')),
    "the DESIGN bullet renamed": edit("design", BULLET, BULLET.replace("Python versions", "Pythons")),
}


def test_the_mutant_count_is_the_one_design_states():
    assert len(MUTANTS) == 10
    assert "each of 10 broken variants of those four files fails the check" in texts()["design"]


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_a_broken_python_list_fails_the_check(name):
    t = texts()
    mutant = MUTANTS[name](t)
    assert mutant != t, name
    assert problems(mutant), name
