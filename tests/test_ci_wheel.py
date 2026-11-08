"""DESIGN 3 v1.116: the last `ci.yml` step builds a wheel, installs it into a fresh venv and,
from outside the checkout, runs the demo and checks what the wheel carries; the README says how
another project installs the package.

ci.yml is read with the line parser of tests/test_evidence_workflow.py (no YAML library, so this
runs in CI); the run itself is checked on GitHub, not here."""

import re
from pathlib import Path

import pytest

from test_evidence_workflow import parse_steps, top_blocks

ROOT = Path(__file__).resolve().parents[1]
CI = ROOT / ".github" / "workflows" / "ci.yml"
README = ROOT / "README.md"
PYPROJECT = ROOT / "pyproject.toml"

NAME = "Built wheel runs outside the checkout (one Python version)"
VERSION = "3.12"
RUN = [
    'python -m pip wheel . --no-deps -w "$RUNNER_TEMP/dist"',
    'python -m venv "$RUNNER_TEMP/wheel-venv"',
    '"$RUNNER_TEMP/wheel-venv/bin/python" -m pip install "$RUNNER_TEMP"/dist/*.whl',
    'cd "$RUNNER_TEMP"',
    '"$RUNNER_TEMP/wheel-venv/bin/model-routing" demo --out "$RUNNER_TEMP/wheel-demo"',
    '"$RUNNER_TEMP/wheel-venv/bin/python" - <<\'EOF\'',
    "import importlib.metadata, importlib.resources, os, pathlib, sys",
    "import model_routing",
    "here = pathlib.Path(model_routing.__file__).resolve().parent",
    'checkout = pathlib.Path(os.environ["GITHUB_WORKSPACE"]).resolve()',
    "if not here.is_relative_to(pathlib.Path(sys.prefix).resolve()) or here.is_relative_to(checkout):",
    '    sys.exit(f"model_routing imports from {here}, not from the wheel venv")',
    'if importlib.metadata.version("ai-model-routing") != model_routing.__version__:',
    '    sys.exit("the wheel metadata version differs from model_routing.__version__")',
    'names = sorted("data/" + p.name for p in (checkout / "model_routing" / "data").glob("*.json"))',
    "if not names:",
    '    sys.exit("the checkout has no model_routing/data/*.json")',
    'packaged = importlib.resources.files("model_routing")',
    'for name in names + ["py.typed"]:',
    "    found = packaged.joinpath(name)",
    '    if not found.is_file() or found.read_bytes() != (checkout / "model_routing" / name).read_bytes():',
    '        sys.exit(f"the wheel does not carry model_routing/{name} as the checkout has it")',
    'print(f"wheel ok: model_routing {model_routing.__version__} from {here}, '
    '{len(names)} data files and py.typed")',
    "EOF",
]


def ci_text():
    return CI.read_text(encoding="utf-8")


def wheel_problems(text):
    """Every way ci.yml breaks the v1.116 wheel step clause (an empty list when it holds)."""
    blocks = dict(top_blocks(text))
    if "jobs" not in blocks:
        return ["no jobs"]
    try:
        header, steps = parse_steps(blocks["jobs"])
    except (AssertionError, ValueError) as error:
        return [f"steps do not parse: {error}"]
    found = []
    if header[:2] != ["jobs:", "  test:"]:
        found.append(f"the job is not test: {header[:2]}")
    named = [s for s in steps if s.get("name") == NAME]
    if len(named) != 1:
        return found + [f"{len(named)} steps named {NAME!r}"]
    step = named[0]
    if steps[-1] is not step:
        found.append("the wheel step is not the last step")
    if step["keys"] != ["name", "if", "run"]:
        found.append(f"step keys {step['keys']}")
    lists = [re.fullmatch(r"\s+python-version: \[(.*)\]", line) for line in header]
    versions = [v for m in lists if m for v in re.findall(r'"(\d+\.\d+)"', m.group(1))]
    if step.get("if") != f"matrix.python-version == '{VERSION}'" or VERSION not in versions:
        found.append("the wheel step does not run on the matrix's 3.12")
    if step["run"] != RUN:
        found.append("the run lines differ")
    return found


def test_the_last_ci_step_installs_the_wheel_and_runs_it_outside_the_checkout():
    assert wheel_problems(ci_text()) == []


def step_lines(text, change):
    """Apply change to the wheel step's run lines (as YAML lines, 10-space indent kept)."""
    head, rest = text.split(f"      - name: {NAME}\n", 1)
    first, body = rest.split("        run: |\n", 1)
    lines = body.rstrip("\n").split("\n")
    return (head + f"      - name: {NAME}\n" + first + "        run: |\n"
            + "\n".join(change(lines)) + "\n")


def replace_line(old, new):
    def change(lines):
        assert lines.count(" " * 10 + old) == 1, old
        return [(" " * 10 + new) if line == " " * 10 + old else line for line in lines]
    return change


def drop_line(old):
    def change(lines):
        assert lines.count(" " * 10 + old) == 1, old
        return [line for line in lines if line != " " * 10 + old]
    return change


def before(anchor, new):
    def change(lines):
        i = lines.index(" " * 10 + anchor)
        return lines[:i] + [" " * 10 + new] + lines[i:]
    return change


IF = f"        if: matrix.python-version == '{VERSION}'\n"
STEP_HEAD = f"      - name: {NAME}\n{IF}"

MUTANTS = {
    "the step removed": lambda t: t.split(f"      - name: {NAME}\n", 1)[0],
    "its cd dropped": lambda t: step_lines(t, drop_line('cd "$RUNNER_TEMP"')),
    "a cd back to the checkout before the check": lambda t: step_lines(
        t, before(RUN[5], 'cd "$GITHUB_WORKSPACE"')),
    "the demo from the PATH": lambda t: step_lines(t, replace_line(
        RUN[4], 'model-routing demo --out "$RUNNER_TEMP/wheel-demo"')),
    "an editable install in place of the wheel": lambda t: step_lines(t, replace_line(
        RUN[2], '"$RUNNER_TEMP/wheel-venv/bin/python" -m pip install -e .')),
    "a venv with the system site packages": lambda t: step_lines(t, replace_line(
        RUN[1], 'python -m venv --system-site-packages "$RUNNER_TEMP/wheel-venv"')),
    "the check without py.typed": lambda t: step_lines(t, replace_line(
        RUN[18], "for name in names:")),
    "an if naming a Python outside the matrix": lambda t: t.replace(
        STEP_HEAD, f"      - name: {NAME}\n        if: matrix.python-version == '3.9'\n", 1),
    "3.12 dropped from the matrix": lambda t: t.replace(
        '"3.11", "3.12", ', '"3.11", ', 1),
    "a continue-on-error": lambda t: t.replace(
        STEP_HEAD, STEP_HEAD + "        continue-on-error: true\n", 1),
    "a working-directory": lambda t: t.replace(
        STEP_HEAD, STEP_HEAD + "        working-directory: ${{ github.workspace }}\n", 1),
    "a step after it": lambda t: t + "      - name: Later\n        run: echo later\n",
}


def test_the_mutant_count_is_the_one_design_states():
    assert len(MUTANTS) == 12


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_a_broken_wheel_step_fails_the_check(name):
    text = ci_text()
    mutant = MUTANTS[name](text)
    assert mutant != text, name
    assert wheel_problems(mutant), name


# --- the README paragraph -------------------------------------------------------------------

def quickstart():
    text = README.read_text(encoding="utf-8")
    assert text.count("\n## Quickstart\n") == 1
    return text.split("\n## Quickstart\n", 1)[1].split("\n## ", 1)[0]


def project_name():
    found = re.findall(r'^name = "([^"]+)"$', PYPROJECT.read_text(encoding="utf-8"), re.M)
    assert len(found) == 1
    return found[0]


def expected_paragraph(section):
    clone = re.findall(r"^git clone (https://\S+\.git)$", section, re.M)
    assert len(clone) == 1
    return (
        "To use the library from another project instead of a clone, install it from this "
        "repository pinned to a commit, with the full SHA of a commit you have checked in place "
        f'of `<commit>`: `pip install "{project_name()} @ git+{clone[0]}@<commit>"`. On each '
        "push, CI builds a wheel, installs it into a fresh virtual environment and, from outside "
        "the checkout, runs the demo and checks that the data files and the `py.typed` marker "
        "came with it.")


def test_readme_quickstart_says_how_another_project_installs_it():
    section = quickstart()
    paragraph = expected_paragraph(section)
    first_block = re.search(r"```bash\n.*?\n```\n\n", section, re.S)
    assert first_block, "Quickstart has no bash block"
    assert section[first_block.end():].startswith(paragraph + "\n\n")
    assert README.read_text(encoding="utf-8").count(paragraph) == 1


def test_the_readme_paragraph_names_this_repository_and_distribution():
    paragraph = expected_paragraph(quickstart())
    assert ('`pip install "ai-model-routing @ '
            'git+https://github.com/jeffma8888/ai-model-routing.git@<commit>"`') in paragraph
