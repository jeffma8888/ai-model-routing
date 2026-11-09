"""DESIGN 12.13 v1.137: each workflow, `ci.yml` and `evidence.yml`, sets its own token
permissions, one top-level `permissions` block of `contents: read`, and no job sets its own, so
the read-only `GITHUB_TOKEN` holds by the file and not by a repository setting.

Both files are read with the `top_blocks` reader of tests/test_evidence_workflow.py (no YAML
library, so this runs in CI); the token a run gets is checked on GitHub, not here."""

import re
from pathlib import Path

import pytest

from test_evidence_workflow import top_blocks

ROOT = Path(__file__).resolve().parents[1]
WORKFLOWS = {name: ROOT / ".github" / "workflows" / name for name in ("ci.yml", "evidence.yml")}
BLOCK = "permissions:\n  contents: read\n"
# By substring and in any letter case, so it fails closed: a job's block, a flow-style key or a
# comment that names permissions fails, as the `secrets` check of the evidence workflow does.
WORD = re.compile(r"permission", re.I)
NOT_ONE_BLOCK = "not one top-level permissions block of contents: read"
OUTSIDE = "names permissions outside its top-level block"

RED = pytest.mark.xfail(strict=True, raises=AssertionError,
                        reason="v1.137 spec: ci.yml sets no permissions until the change lands")


def texts():
    return {name: path.read_text(encoding="utf-8") for name, path in WORKFLOWS.items()}


def permission_problems(by_name):
    """Every way the workflow texts break the v1.137 permissions clause (an empty list when it
    holds). A column-0 `permissions` line is read by the block check alone."""
    found = []
    for name, text in by_name.items():
        blocks = [body for key, body in top_blocks(text) if key == "permissions"]
        if blocks != [BLOCK]:
            found.append(f"{name}: {NOT_ONE_BLOCK}")
        others = [line for line in text.split("\n")
                  if WORD.search(line) and not line.startswith("permissions")]
        if others:
            found.append(f"{name}: {OUTSIDE} {others!r}")
    return found


@RED
def test_each_workflow_sets_contents_read_at_the_top_level_and_no_job_sets_its_own():
    assert permission_problems(texts()) == []


def drop_block(text):
    return text.replace("\n" + BLOCK, "\n", 1)


def block_as(new):
    return lambda text: text.replace(BLOCK, new, 1)


def job_block(text):
    return text.replace("    runs-on: ubuntu-24.04\n",
                        "    runs-on: ubuntu-24.04\n    permissions:\n      contents: write\n", 1)


# Each broken pair changes one file and names the one problem the check must report for it.
MUTANTS = {
    "ci.yml without the block": ("ci.yml", drop_block, NOT_ONE_BLOCK),
    "evidence.yml without the block": ("evidence.yml", drop_block, NOT_ONE_BLOCK),
    "ci.yml with contents: write": (
        "ci.yml", block_as("permissions:\n  contents: write\n"), NOT_ONE_BLOCK),
    "evidence.yml with contents: write": (
        "evidence.yml", block_as("permissions:\n  contents: write\n"), NOT_ONE_BLOCK),
    "ci.yml with a second scope": (
        "ci.yml", block_as(BLOCK + "  pull-requests: write\n"), NOT_ONE_BLOCK),
    "ci.yml with write-all": ("ci.yml", block_as("permissions: write-all\n"), NOT_ONE_BLOCK),
    "evidence.yml with read-all": (
        "evidence.yml", block_as("permissions: read-all\n"), NOT_ONE_BLOCK),
    "a ci.yml job with its own permissions": ("ci.yml", job_block, OUTSIDE),
    "an evidence.yml job with its own permissions": ("evidence.yml", job_block, OUTSIDE),
    "a second top-level block at the end of ci.yml": (
        "ci.yml", lambda text: text + "permissions:\n  contents: write\n", NOT_ONE_BLOCK),
}


def test_the_permission_mutant_count_is_the_one_design_states():
    assert len(MUTANTS) == 10


@RED
@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_a_widened_or_missing_permission_fails_the_check(name):
    committed = texts()
    assert permission_problems(committed) == []
    which, change, problem = MUTANTS[name]
    mutant = dict(committed, **{which: change(committed[which])})
    assert mutant[which] != committed[which], name
    found = permission_problems(mutant)
    assert len(found) == 1 and found[0].startswith(f"{which}: {problem}"), (name, found)
