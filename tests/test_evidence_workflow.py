"""The `evidence` workflow reruns the README regenerate commands of the AutoBench-based
subsections on GitHub and fails when a committed results file changes (DESIGN 12.13, v1.30).

The workflow is read with a line parser for its own shape (no YAML library, so this runs in
CI); the run itself is checked on GitHub, not here."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "evidence.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
README = ROOT / "README.md"
ROUTERBENCH_CONVERT = ROOT / "evidence" / "routerbench" / "convert.py"
EVIDENCE = "## Evidence: held-out results on public data\n"
SUBSECTIONS = ("AutoBench", "AutoBench judges", "Delegation on AutoBench")
INSTALL = "python -m pip install -e ."
ON = (
    "on:\n"
    "  workflow_dispatch:\n"
    "  push:\n"
    "    branches: [main]\n"
    "    paths:\n"
    "      - \"evidence/**\"\n"
    "      - \"model_routing/**\"\n"
    "      - \"pyproject.toml\"\n"
    "      - \".github/workflows/evidence.yml\"\n")
STEP_NAMES = [None, None, "Install", "Regenerate", "Compare"]


def readme():
    return README.read_text(encoding="utf-8")


def subsection(text, heading):
    section = text.split(EVIDENCE, 1)[1].split("\n## ", 1)[0]
    marker = f"\n### {heading}\n"
    assert section.count(marker) == 1, heading
    return section.split(marker, 1)[1].split("\n### ", 1)[0]


def readme_blocks(text):
    """Each AutoBench-based subsection's one regenerate block, as a list of lines."""
    blocks = []
    for heading in SUBSECTIONS:
        found = re.findall(r"```bash\n(.*?)```", subsection(text, heading), re.S)
        assert len(found) == 1, heading
        blocks.append(found[0].rstrip("\n").split("\n"))
    return blocks


def expected_commands(text):
    commands = []
    for block in readme_blocks(text):
        assert block[0] == INSTALL
        assert INSTALL not in block[1:]
        commands += block[1:]
    return commands


def out_paths(commands):
    paths = []
    for line in commands:
        args = line.split()
        paths += [args[i + 1] for i, a in enumerate(args[:-1])
                  if a == "--out" and args[i + 1].startswith("evidence/")]
    return paths


def routerbench_size():
    found = re.findall(r"^SIZE = (\d+)$", ROUTERBENCH_CONVERT.read_text(encoding="utf-8"), re.M)
    assert len(found) == 1
    return int(found[0])


def readme_sentence(text):
    paths = out_paths(expected_commands(text))
    named = ", ".join(f"`{p}`" for p in paths[:-1]) + f" or `{paths[-1]}`"
    return (
        "On GitHub, the `evidence` workflow "
        "([.github/workflows/evidence.yml](.github/workflows/evidence.yml)) reruns the "
        "regenerate commands of the AutoBench, AutoBench judges and delegation subsections, "
        f"downloading the pinned files, and fails if {named} changes by a byte; RouterBench "
        f"is left out of it, since its source is a {routerbench_size():,}-byte pickle that "
        "needs pandas and its evaluate step takes about 70 seconds.")


def top_blocks(text):
    """Top-level keys in file order, each with its text (comment and blank lines dropped)."""
    blocks = []
    for line in text.split("\n"):
        if not line.strip() or line.lstrip().startswith("#"):
            continue
        if not line.startswith(" "):
            blocks.append([line.split(":", 1)[0], ""])
        blocks[-1][1] += line + "\n"
    return blocks


def parse_steps(job):
    """The job's steps as dicts: `name`, `uses`, `with` (dict) and `run` (list of lines)."""
    lines = job.split("\n")
    start = lines.index("    steps:")
    steps, block = [], None
    for line in lines[start + 1:]:
        if not line:
            continue
        if line.startswith("      - "):
            steps.append({"with": {}, "run": []})
            line = "        " + line[len("      - "):]
        step = steps[-1]
        if block is not None and line.startswith(" " * 10):
            if block == "with":
                key, value = line.strip().split(": ", 1)
                step["with"][key] = value
            else:
                step["run"].append(line[10:])
            continue
        block = None
        assert line.startswith("        ") and not line.startswith("         "), line
        key, _, value = line.strip().partition(":")
        value = value.strip()
        if key == "with" and not value:
            block = "with"
        elif key == "run" and value == "|":
            block = "run"
        elif key == "run":
            step["run"] = [value]
        else:
            assert key not in step, key
            step[key] = value
    return steps


def ci_uses(ci_text):
    return re.findall(r"^\s+- uses: (\S+)$", ci_text, re.M)


def problems(text, readme_text, ci_text):
    """Every way the workflow text breaks DESIGN 12.13 (an empty list when it holds)."""
    found = []
    if re.search(r"secrets", text, re.I):
        found.append("names a secret")
    if "pull_request_target" in text:
        found.append("has a pull_request_target trigger")
    if re.search(r":\s*write\b", text):
        found.append("grants a write permission")
    head = text.split("\n\non:\n", 1)[0]
    if "RouterBench" not in head or f"{routerbench_size():,}-byte" not in head:
        found.append("the top comment does not say why RouterBench is left out")
    blocks = top_blocks(text)
    keys = [k for k, _ in blocks]
    if keys != ["name", "on", "permissions", "defaults", "jobs"]:
        return found + [f"top-level keys {keys}"]
    block = dict(blocks)
    if block["name"] != "name: evidence\n":
        found.append("name is not evidence")
    if block["on"] != ON:
        found.append("triggers or paths differ")
    if block["permissions"] != "permissions:\n  contents: read\n":
        found.append("permissions are not contents: read")
    if block["defaults"] != "defaults:\n  run:\n    shell: bash\n":
        found.append("default shell is not bash")
    job = block["jobs"]
    jobs = re.findall(r"^  (\S[^:]*):$", job, re.M)
    if jobs != ["regenerate"]:
        return found + [f"jobs {jobs}"]
    ci_runs_on = re.findall(r"^    runs-on: (\S+)$", ci_text, re.M)
    if re.findall(r"^    runs-on: (\S+)$", job, re.M) != ci_runs_on or len(ci_runs_on) != 1:
        found.append("runs-on differs from ci.yml")
    try:
        steps = parse_steps(job)
    except (AssertionError, ValueError) as error:
        return found + [f"steps do not parse: {error}"]
    if [s.get("name") for s in steps] != STEP_NAMES:
        return found + [f"step names {[s.get('name') for s in steps]}"]
    checkout, python, install, regenerate, compare = steps
    if [checkout.get("uses"), python.get("uses")] != ci_uses(ci_text):
        found.append("actions differ from ci.yml")
    if checkout["with"] != {"persist-credentials": "false"} or checkout["run"]:
        found.append("checkout keeps credentials")
    versions = re.findall(r'"(\d+\.\d+)"', ci_text.split("python-version: [", 1)[1].split("]")[0])
    version = python["with"].get("python-version", "").strip('"')
    if set(python["with"]) != {"python-version"} or version not in versions or python["run"]:
        found.append("setup-python is not one ci.yml Python")
    if install["run"] != [INSTALL] or "uses" in install:
        found.append("install line differs")
    commands = expected_commands(readme_text)
    if regenerate["run"] != commands or "uses" in regenerate:
        found.append("Regenerate is not the README commands in order")
    diff = "git diff --exit-code -- " + " ".join(out_paths(commands))
    if compare["run"] != [diff] or "uses" in compare:
        found.append("Compare is not the diff of the committed results")
    return found


def workflow_text():
    assert WORKFLOW.is_file(), "the evidence workflow is missing"
    return WORKFLOW.read_text(encoding="utf-8")


def test_workflow_reruns_the_readme_commands_and_compares_the_results():
    assert problems(workflow_text(), readme(), CI.read_text(encoding="utf-8")) == []


def test_readme_commands_are_the_three_autobench_blocks():
    commands = expected_commands(readme())
    assert len(commands) == 4 + 4 + 4
    assert out_paths(commands) == ["evidence/autobench-2026/results.json",
                                   "evidence/autobench-judges/results.json",
                                   "evidence/delegation/results.json"]
    assert all((ROOT / p).is_file() for p in out_paths(commands))
    assert not any("routerbench-matrix" in c for c in commands)


def test_readme_evidence_intro_names_the_workflow():
    text = readme()
    intro = text.split(EVIDENCE, 1)[1].strip("\n").split("\n\n", 1)[0]
    assert intro.startswith("Each dataset here already holds")
    assert intro.endswith(" " + readme_sentence(text))
    assert text.count("(.github/workflows/evidence.yml)") == 1


def swap(lines, i, j):
    lines = list(lines)
    lines[i], lines[j] = lines[j], lines[i]
    return lines


def regenerate_lines(text):
    head, rest = text.split("        run: |\n", 1)
    body = rest.split("      - name: Compare\n", 1)
    return head, body[0].rstrip("\n").split("\n"), body[1]


def with_lines(text, change):
    head, lines, tail = regenerate_lines(text)
    return head + "        run: |\n" + "\n".join(change(lines)) + "\n      - name: Compare\n" + tail


MUTANTS = {
    "a command dropped": lambda t: with_lines(t, lambda ls: ls[:3] + ls[4:]),
    "two commands swapped": lambda t: with_lines(t, lambda ls: swap(ls, 0, 4)),
    "an extra command": lambda t: with_lines(t, lambda ls: ls + ["          echo extra"]),
    "a path filter dropped": lambda t: t.replace('      - "pyproject.toml"\n', "", 1),
    "a write permission": lambda t: t.replace("  contents: read\n", "  contents: write\n", 1),
    "a secret": lambda t: t.replace("run: python -m pip install -e .\n",
                                    "run: python -m pip install -e .\n"
                                    "        env:\n          TOKEN: ${{ secrets.TOKEN }}\n", 1),
    "the compare step on two files": lambda t: t.replace(
        " evidence/delegation/results.json\n", "\n", 1),
    "checkout with credentials": lambda t: t.replace("persist-credentials: false",
                                                     "persist-credentials: true", 1),
}


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_a_broken_workflow_fails_the_check(name):
    text = workflow_text()
    mutant = MUTANTS[name](text)
    assert mutant != text, name
    assert problems(mutant, readme(), CI.read_text(encoding="utf-8")), name
