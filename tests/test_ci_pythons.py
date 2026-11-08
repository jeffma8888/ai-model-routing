"""DESIGN 12.13 v1.118: the Python versions `ci.yml` tests, the floor `pyproject.toml` states
and the README Development line agree with the list the DESIGN bullet writes; v1.120 (review):
the matrix block holds only that list, so no `include` or `exclude` changes the jobs.

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
MATRIX_HEAD = "      matrix:"
MATRIX_READ = re.compile(r"^\s+python-version: \$\{\{ matrix\.python-version \}\}\s*$")


def texts():
    return {key: path.read_text(encoding="utf-8") for key, path in FILES.items()}


def versions(inner):
    """The `X.Y` strings of a bracket list's inner text, or None if an item is not a quoted X.Y."""
    items = [item.strip() for item in inner.split(",")]
    found = [ITEM.fullmatch(item) for item in items]
    if not items or not all(found):
        return None
    return [(int(m.group(1)), int(m.group(2))) for m in found]


def matrix_problems(ci):
    """v1.120: one `matrix:` block holding only the python-version list, and no other line that
    names python-version but the reads of `matrix.python-version`: the setup-python input
    `python-version: ${{ matrix.python-version }}` and an `if:` that compares it."""
    found = []
    lines = ci.splitlines()
    heads = [i for i, line in enumerate(lines) if line.lstrip().startswith("matrix:")]
    if len(heads) != 1 or lines[heads[0]] != MATRIX_HEAD:
        return [f"ci.yml has {len(heads)} matrix keys, not one block {MATRIX_HEAD.strip()!r}"]
    block = []
    for line in lines[heads[0] + 1:]:
        if line.strip() and len(line) - len(line.lstrip()) <= len(MATRIX_HEAD) - len("matrix:"):
            break
        if line.strip():
            block.append(line)
    if len(block) != 1 or not MATRIX.fullmatch(block[0]):
        found.append(f"the matrix block is {block}, not the one python-version list")
    for n, line in enumerate(lines, 1):
        if line.lstrip().startswith("#") or MATRIX.fullmatch(line) or MATRIX_READ.fullmatch(line):
            continue
        if "python-version" in line.replace("matrix.python-version", ""):
            found.append(f"ci.yml:{n} names python-version outside the matrix list: {line.strip()!r}")
    return found


def development(readme):
    """The README `## Development` section, or None when it is not there once."""
    parts = readme.split("\n## Development\n")
    return parts[1].split("\n## ", 1)[0] if len(parts) == 2 else None


def problems(t):
    """Every way the four files break the v1.118 clause (an empty list when it holds)."""
    found = matrix_problems(t["ci"])
    lists = MATRIX.findall(t["ci"])
    if len(lists) != 1:
        return found + [f"ci.yml has {len(lists)} python-version lists, not one"]
    matrix = lists[0]
    bullets = [line for line in t["design"].splitlines() if line.startswith(BULLET)]
    if len(bullets) != 1:
        return found + [f"DESIGN.md has {len(bullets)} v1.118 Python versions bullets, not one"]
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
    readme = README_LINE.findall(development(t["readme"]) or "")
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


def moved(t):
    """The README line taken out of Development and put at the end of the file."""
    line = '- Run `pytest -q`. CI runs the suite and the demo on Python 3.10 to 3.14\n'
    assert t["readme"].count(line) == 1, "the README line is not there once"
    out = dict(t)
    out["readme"] = t["readme"].replace(line, "", 1) + "\n" + line
    return out


NEW = '"3.10", "3.11", "3.12", "3.13", "3.14"'
MATRIX_LINE = '        python-version: [' + NEW + ']\n'
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
    "an include entry adding 3.15": edit(
        "ci", MATRIX_LINE, MATRIX_LINE + '        include:\n          - python-version: "3.15"\n'),
    "an exclude entry dropping 3.14": edit(
        "ci", MATRIX_LINE, MATRIX_LINE + '        exclude:\n          - python-version: "3.14"\n'),
    "a second matrix key": edit("ci", MATRIX_LINE, MATRIX_LINE + "        os: [ubuntu-24.04]\n"),
    "the README line moved out of Development": moved,
}


def test_the_mutant_count_is_the_one_design_states():
    assert len(MUTANTS) == 14
    assert "each of 14 broken variants (10 to v1.119) of those four files fails the check" in texts()["design"]


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_a_broken_python_list_fails_the_check(name):
    t = texts()
    mutant = MUTANTS[name](t)
    assert mutant != t, name
    assert problems(mutant), name
