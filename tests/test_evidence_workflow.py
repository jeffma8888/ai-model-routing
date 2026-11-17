"""The `evidence` workflow reruns the README regenerate commands of the AutoBench-based
subsections, from v1.55 the tau2-bench one, from v1.65 the LiveCodeBench one, from v1.80 the tau2-bench
delegation one, from v1.84 its pooled run, from v1.168 the LLMRouterBench one, from v1.200 the
LLMRouterBench delegation one and from v1.299 the LLM Routing Response Bank one on GitHub (from
v1.215 running a repeated line once), from v1.397 last the one regenerate line of
evidence/ledger-handoff/RESULTS.md (DESIGN 13.15), which has no README subsection, from v1.443
after it the `## Regenerate` block of evidence/registry-pair/RESULTS.md (DESIGN 12.24), which has
none yet either, and fails when a committed results file changes (DESIGN 12.13, v1.30),
and both workflows run on one pinned runner image with a dated comment (v1.49), and the job
has a time limit of ten times its slowest run, rounded up to whole five minutes, with no download
retry until v1.406 (v1.152; 25 minutes, restated as 30 at v1.170, as 40 at v1.217, whose basis was the
slowest run on the `Regenerate` lines in force, as 50 at v1.225, as 55 at v1.268, as 40 at
v1.301, on the first run of the v1.299 lines, as 50 at v1.302, on the slower of the first
two, as 35 at v1.321, on the slower of the first two runs of the v1.317 lines, as 50 at
v1.374, on the slowest of the first eight, as 60 at v1.395, on the slowest of the first
eleven, as 25 at v1.398, on the first run of the v1.397 lines, as 30 at v1.399, on the slower
of the first two, as 60 at v1.401, on the slowest run on main whatever its lines, as 65 at
v1.407, on a rerun, counted by its latest attempt, and as 105 at v1.442, on a run whose
LLMRouterBench converter line took 429 s). From v1.278
the top comment names the rerun subsections (eight, nine from v1.299) in README heading order, on
lines under 100 columns.

The workflow is read with a line parser for its own shape (no YAML library, so this runs in
CI); the run itself is checked on GitHub, not here."""

import datetime
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github" / "workflows" / "evidence.yml"
CI = ROOT / ".github" / "workflows" / "ci.yml"
README = ROOT / "README.md"
DESIGN = ROOT / "DESIGN.md"
CHANGELOG = ROOT / "CHANGELOG.md"
LLMROUTERBENCH = ROOT / "evidence" / "llmrouterbench" / "convert.py"
ROUTERBENCH_CONVERT = ROOT / "evidence" / "routerbench" / "convert.py"
# v1.397 (row E23c): the ledger hand-off results have no README subsection; their one regenerate
# line, read from their RESULTS.md, runs after the README commands (DESIGN 13.15 Workflow bullet).
LEDGER_NOTES = "evidence/ledger-handoff/RESULTS.md"
LEDGER_LINE = "python evidence/ledger-handoff/results.py --out evidence/ledger-handoff/results.json"
# v1.443 (row E24e): the registry-pair results have no README subsection yet (row E24c); their
# `## Regenerate` block, read from their RESULTS.md, runs after the ledger line (DESIGN 12.13).
REGISTRY_NOTES = "evidence/registry-pair/RESULTS.md"
REGISTRY_LINES = [
    "python evidence/registry-pair/convert.py --out registry-pair-matrix.jsonl",
    "model-routing evaluate --outcomes registry-pair-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json "
    "> registry-pair-evaluate.json",
    "python evidence/routerbench/results.py --evaluate registry-pair-evaluate.json "
    "--out evidence/registry-pair/results.json",
    "python evidence/routerbench/results.py --table evidence/registry-pair/results.json"]
EVIDENCE = "## Evidence: held-out results on public data\n"
SUBSECTIONS = ("AutoBench", "AutoBench judges", "tau2-bench", "LiveCodeBench", "LLMRouterBench",
               "LLM Routing Response Bank", "Delegation on AutoBench", "Delegation on tau2-bench",
               "Delegation on LLMRouterBench", "Delegation on the LLM Routing Response Bank")
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
# The job's time limit, by the v1.152 rule: ten times the slowest run, rounded up to a whole
# five minutes. The v1.442 value (row CI24): the slowest successful run of the workflow on main,
# whatever its Regenerate lines, a run that was rerun counting by its latest attempt from that
# attempt's start, is run 43988047634 on 73538b7 among the 105 to 2026-11-17 (all on main, all
# successful by their latest attempt, 43751236072 the one rerun), 601 s on attempt 1, so 105; by
# its log the first lines of its six converters took 524.9 s, 225.2 s more than in the v1.407
# basis run, 205.1 s more on the LLMRouterBench line (428.96 s against 223.85; 55.29 s in the
# next run, 44001799439 on fbcf6ff), most likely its download, and the ledger line 1.5 s. At
# v1.407 (row CI22), run 43751236072 on 937399a among the 97 to 2026-11-15, 371 s on attempt 2,
# a rerun, so 65; by its log the first lines of its six converters took 299.7 s, 30.9 s more
# than in the v1.401 basis run, 65.0 s more on the LLMRouterBench line, and the ledger line
# 1.5 s. At v1.401 (row CI21), with a line change
# keeping the value, run 43689201551 on 2c31a98 among the 93 then (all on main, all
# successful), 338 s, so 60; by its log the first lines of its six converters took 268.8 s (it
# ran before the ledger line). At v1.399, the
# slowest run on the Regenerate lines in force, from v1.397 those with the ledger hand-off line
# last, was the slower of the two such runs among the 92 to
# 2026-11-15 (149 and 178 s from start to last update), run 43707930726, 178 s, so 30; by its
# log the first lines of its six converters took 114.6 s, 34.3 s more than in the v1.398 basis
# run, 26.3 s of it the LiveCodeBench line, most likely the downloads, and the ledger line 1.3 s.
# At v1.398, the one such run then, run 43702821166, 149 s, so 25; by its log the first lines of
# its six converters took 80.3 s, 188.5 s less than in the v1.395 basis run, 119.0 s of it the
# LLMRouterBench line, and the ledger line 0.9 s. At v1.395, the
# slowest of the eleven runs of the v1.317 lines (those with the three response-bank delegation
# lines) among the 88 to 2026-11-14 (151 to 338 s), run 43689201551, 338 s,
# so 60; by its log the first lines of its six converters took 268.8 s, 47.3 s more than in the
# v1.374 basis run, 33.3 s of it the LiveCodeBench line and 9.4 s the tau2-bench line, most
# likely their downloads. At v1.374, the slowest of the first eight such runs (151 to 291 s),
# run 43608998651, 291 s, so 50; by its log its two converter lines took 179.7 s, 105.4 s more
# than in the v1.321 basis run, most likely the LLMRouterBench download. At v1.321, the slower
# of the first two such runs (204 and 206 s), run 43439800863, 206 s, so 35, the second value
# the rule lowered; by the logs the new lines took 9.4 and 10.6 s. At v1.302,
# on the v1.299 lines (the four response-bank lines), the slower of the two such runs among the
# 74 to 2026-11-12 (213 and 281 s), run 43363202337, 281 s, so 50; by the log its two converter
# lines took 76.5 and 32.5 s more than in the first run, most likely the downloads. At v1.301,
# the one such run then, 213 s (run 43357001972), so 40, the first value
# the rule lowered (a change of the lines then started the basis again, v1.218). At v1.268, the
# slowest of the 11 runs of the v1.215 lines (121 to 312 s), 312 s (run 43054947572), so 55; its
# converter line took 178.7 s by the log, most likely the LLMRouterBench download again. At
# v1.225, the slowest of the four such runs then (213, 219, 290 and 275 s), 290 s (run
# 42904515973), so 50, its extra time most likely the same download. At v1.217, the one such run
# then, 213 s, so 40; the four runs of v1.200 to v1.214 (up to 278 s) also ran the converter
# line twice. At v1.170, 158 s over 45 runs, so 30; at v1.152, 140 s over 40 runs, so 25.
SLOWEST_RUN_SECONDS = 601
SLOWEST_RUN_ID = 43988047634
SLOWEST_RUN_SHA = "73538b7"  # review iter-254 nit 3
# v1.407 (row CI22): the attempt of the basis run whose time counts, its latest; above 1, a rerun.
SLOWEST_RUN_ATTEMPT = 1
# v1.391 (row DOC26): the versions of the DESIGN 12.13 time-limit bullet's history pointer, whose
# CHANGELOG.md lines hold the earlier bases, and those bases' runs, which the bullet no longer names.
TIME_LIMIT_HISTORY = ("v1.152, v1.168, v1.170, v1.215, v1.217, v1.218, v1.225, v1.226, v1.268, v1.299, v1.301, "
                      "v1.302, v1.317, v1.321, v1.374, v1.395, v1.398, v1.399, v1.401, v1.407, v1.442")
# v1.401 (row CI21): 43689201551, the v1.395 basis, was the basis again and left this list; v1.407
# (row CI22) replaces it, so it comes back; v1.442 (row CI24) replaces 43751236072, now first.
EARLIER_BASIS_RUNS = ("43751236072", "43689201551", "43707930726", "43702821166", "43608998651", "43439800863",
                      "43433217023", "43363202337", "43357001972", "43054947572", "42904515973",
                      "42883099079", "42717985363", "42445989566")
# Review iter-249 nit 4 (v1.395, row CI16): the CHANGELOG.md half of the v1.391 rule. The restating
# version ends the history pointer, and its line names the new basis run and the one it replaces,
# each with its seconds; the replaced run is the first of EARLIER_BASIS_RUNS.
RESTATING_VERSION = "v1.442"
REPLACED_BASIS = ("v1.407", 43751236072, 371, "937399a")
TIMEOUT_MINUTES = 105
LIMIT_LINE = f"    timeout-minutes: {TIMEOUT_MINUTES}"
LIMIT_SENTENCE = (f"The job's time limit of {TIMEOUT_MINUTES} minutes is about ten times its slowest run, "
                  "and a failed download is retried by rerunning the job (DESIGN.md 12.13).")
LIMIT_PROBLEM = f"the job's time limit is not {TIMEOUT_MINUTES} minutes"
SENTENCE_PROBLEM = "the comment above jobs: does not end with the time-limit sentence"


def readme():
    return README.read_text(encoding="utf-8")


def subsection(text, heading):
    section = text.split(EVIDENCE, 1)[1].split("\n## ", 1)[0]
    marker = f"\n### {heading}\n"
    assert section.count(marker) == 1, heading
    return section.split(marker, 1)[1].split("\n### ", 1)[0]


# v1.84: the tau2-bench delegation subsection holds two regenerate blocks, the per-domain one and
# the pooled one; every other rerun subsection holds one.
BLOCKS = {"Delegation on tau2-bench": 2}


def readme_blocks(text):
    """Each rerun subsection's regenerate blocks, in README heading order, joined in order into
    one list of lines per subsection."""
    blocks = []
    for heading in SUBSECTIONS:
        found = re.findall(r"```bash\n(.*?)```", subsection(text, heading), re.S)
        assert len(found) == BLOCKS.get(heading, 1), heading
        blocks.append([line for block in found for line in block.rstrip("\n").split("\n")])
    return blocks


def expected_commands(text):
    commands = []
    for block in readme_blocks(text):
        assert block[0] == INSTALL
        assert INSTALL not in block[1:]
        commands += block[1:]
    return commands


# v1.215 (row CI8): `Regenerate` leaves out a README line identical to one it has already run when
# the line names a .json or .jsonl file, names each once, appends to none, and no line run since
# its last run names a file of the same base name other than right after a flag that only reads.
# The README blocks stay whole.
READ_FLAGS = ("--outcomes", "--matrix", "--evaluate", "--table")
DATA_FILE = re.compile(r"[^\s=<>|;&'\"]+\.jsonl?(?![\w.])")
REPEATED = "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl"
# v1.316: the response-bank converter line, repeated in the response-bank delegation block
RB_REPEATED = "python evidence/response-bank/convert.py --out response-bank-matrix.jsonl"
REPEAT_SENTENCE = ("A README line identical to one already run in the step is not run again when no line "
                   "between them names one of its files except to read it (DESIGN.md 12.13).")
REPEAT_PROBLEM = "the top comment does not give the repeated-line rule"
# v1.278 (row T4): the top comment names the rerun subsections in README heading order, and every
# line above `on:` is under 100 columns; the comment checks join its lines, so a reflow is safe.
SUBSECTION_LIST = ("Reruns the regenerate commands of the README subsections "
                   + ", ".join(SUBSECTIONS[:-1]) + f" and {SUBSECTIONS[-1]}, and those of {LEDGER_NOTES} and "
                   f"{REGISTRY_NOTES}, which")
SUBSECTION_PROBLEM = "the top comment does not name the rerun subsections in README heading order"
WIDTH = 100
WIDTH_PROBLEM = f"a line above on: is {WIDTH} columns or wider"


def data_files(line):
    """The base names of the .json and .jsonl files a line names, in order, repeats kept."""
    return [Path(found).name for found in DATA_FILE.findall(line)]


def unread(line):
    """The line without each flag that only reads a file and the argument after it."""
    args = line.split()
    return " ".join(a for i, a in enumerate(args)
                    if a not in READ_FLAGS and not (i and args[i - 1] in READ_FLAGS))


def run_once(commands):
    """The commands in order, without each repeat the v1.215 rule leaves out."""
    run = []
    for line in commands:
        files = data_files(line)
        if line in run and files and len(set(files)) == len(files) and ">>" not in line:
            last = len(run) - 1 - run[::-1].index(line)
            if not any(set(files) & set(data_files(unread(between))) for between in run[last + 1:]):
                continue
        run.append(line)
    return run


def ledger_command():
    """The command of the one `- Regenerate (...)` bullet of the ledger hand-off RESULTS.md (v1.397)."""
    found = re.findall(r"^- Regenerate \(.*\): `([^`]+)`$", (ROOT / LEDGER_NOTES).read_text(encoding="utf-8"), re.M)
    assert len(found) == 1
    return found[0]


def registry_commands():
    """The lines of the one `bash` block of the registry-pair RESULTS.md `## Regenerate`, without its
    install line (v1.443)."""
    text = (ROOT / REGISTRY_NOTES).read_text(encoding="utf-8")
    section = text.split("\n## Regenerate\n", 1)[1].split("\n## ", 1)[0]
    found = re.findall(r"```bash\n(.*?)```", section, re.S)
    assert len(found) == 1
    block = found[0].rstrip("\n").split("\n")
    assert block[0] == INSTALL and INSTALL not in block[1:]
    return block[1:]


def readme_commands(text):
    """The lines the README evidence intro speaks for: the README commands and the ledger line (v1.397).
    The registry-pair block joins them with its README subsection (row E24c)."""
    return run_once(expected_commands(text) + [ledger_command()])


def regenerate_commands(text):
    return run_once(expected_commands(text) + [ledger_command()] + registry_commands())


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
    paths = out_paths(readme_commands(text))
    named = ", ".join(f"`{p}`" for p in paths[:-1]) + f" or `{paths[-1]}`"
    return (
        "On GitHub, the `evidence` workflow "
        "([.github/workflows/evidence.yml](.github/workflows/evidence.yml)) reruns the "
        "regenerate commands of the AutoBench, AutoBench judges, tau2-bench, LiveCodeBench, "
        "LLMRouterBench, LLM Routing Response Bank and "
        "delegation "
        "subsections and of the ledger hand-off results below, "
        f"downloading the pinned files, and fails if {named} changes by a byte; RouterBench "
        f"is left out of it, since its source is a {routerbench_size():,}-byte pickle that "
        "needs pandas and its evaluate step takes about 70 seconds.")


def top_blocks(text):
    """Top-level keys in file order, each with its text. Only top-level comment lines and the
    blank lines that end a block are dropped, so a comment or blank line inside a block is part
    of it and an exact comparison fails on it."""
    blocks = []
    for line in text.split("\n"):
        if line.startswith("#") or (not blocks and not line):
            continue
        if line and not line.startswith(" "):
            blocks.append([line.split(":", 1)[0], ""])
        blocks[-1][1] += line + "\n"
    return [[key, body.rstrip("\n") + "\n"] for key, body in blocks]


def parse_steps(job):
    """The job's header lines (before `steps:`) and its steps as dicts: `keys` (every key of
    the step, in order), `name`, `uses`, `with` (dict) and `run` (list of lines). A line this
    file's shape does not have, a blank line outside a `run` block included, raises."""
    lines = job.rstrip("\n").split("\n")
    start = lines.index("    steps:")
    steps, block = [], None
    for line in lines[start + 1:]:
        if line.startswith("      - "):
            steps.append({"keys": [], "with": {}, "run": []})
            line = "        " + line[len("      - "):]
        assert steps, line
        step = steps[-1]
        if block == "run" and (not line or line.startswith(" " * 10)):
            step["run"].append(line[10:])
            continue
        if block == "with" and line.startswith(" " * 10):
            key, value = line.strip().split(": ", 1)
            step["with"][key] = value
            continue
        block = None
        assert line.startswith("        ") and not line.startswith("         "), repr(line)
        key, _, value = line.strip().partition(":")
        value = value.strip()
        assert key not in step["keys"], key
        step["keys"].append(key)
        if key == "with" and not value:
            block = "with"
        elif key == "run" and value == "|":
            block = "run"
        elif key == "run":
            step["run"] = [value]
        else:
            step[key] = value
    return lines[:start], steps


def ci_uses(ci_text):
    return re.findall(r"^\s+- uses: (\S+)$", ci_text, re.M)


def problems(text, readme_text, ci_text):
    """Every way the workflow text breaks DESIGN 12.13 (an empty list when it holds)."""
    found = []
    # Substring checks, so they fail closed: a comment that says "secrets" or ": write" fails too.
    if re.search(r"secrets", text, re.I):
        found.append("names a secret")
    if "pull_request_target" in text:
        found.append("has a pull_request_target trigger")
    if re.search(r":\s*write\b", text):
        found.append("grants a write permission")
    head = text.split("\n\non:\n", 1)[0].split("\n")
    comment = " ".join(line[2:] for line in head if line.startswith("# "))
    if readme_sentence(readme_text).split("; ", 1)[1] not in comment:
        found.append("the top comment does not give the README's RouterBench reason")
    if REPEAT_SENTENCE not in comment:
        found.append(REPEAT_PROBLEM)
    if SUBSECTION_LIST not in comment:
        found.append(SUBSECTION_PROBLEM)
    if any(len(line) >= WIDTH for line in head):
        found.append(WIDTH_PROBLEM)
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
    try:
        header, steps = parse_steps(job)
    except (AssertionError, ValueError) as error:
        return found + [f"steps do not parse: {error}"]
    if [line for line in header if "timeout" in line] != [LIMIT_LINE]:
        found.append(LIMIT_PROBLEM)
    if not comment_above_jobs(text).endswith(" " + LIMIT_SENTENCE):
        found.append(SENTENCE_PROBLEM)
    if len(ci_runs_on) != 1 or header != ["jobs:", "  regenerate:", f"    runs-on: {ci_runs_on[0]}", LIMIT_LINE]:
        found.append("the job holds more than runs-on, its time limit and steps, or runs-on differs from ci.yml")
    if [s.get("name") for s in steps] != STEP_NAMES:
        return found + [f"step names {[s.get('name') for s in steps]}"]
    if [s["keys"] for s in steps] != [["uses", "with"]] * 2 + [["name", "run"]] * 3:
        found.append(f"step keys {[s['keys'] for s in steps]}")
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
    commands = regenerate_commands(readme_text)
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


def test_readme_commands_are_the_ten_rerun_subsections():
    commands = expected_commands(readme())
    assert len(commands) == 4 + 4 + 4 + 4 + 4 + 4 + 6 + 4 + 3 + 4 + 4
    assert out_paths(commands) == ["evidence/autobench-2026/results.json",
                                   "evidence/autobench-judges/results.json",
                                   "evidence/tau2-bench/results.json",
                                   "evidence/livecodebench/results.json",
                                   "evidence/llmrouterbench/results.json",
                                   "evidence/response-bank/results.json",
                                   "evidence/delegation/results.json",
                                   "evidence/delegation/variants.json",
                                   "evidence/tau2-bench-delegation/results.json",
                                   "evidence/tau2-bench-delegation/pooled.json",
                                   "evidence/llmrouterbench-delegation/results.json",
                                   "evidence/response-bank-delegation/results.json"]
    assert all((ROOT / p).is_file() for p in out_paths(commands))
    # v1.168: RouterBench stays out; `llmrouterbench-matrix.jsonl` holds its matrix name as a substring.
    assert not any(re.search(r"\brouterbench-matrix", c) for c in commands)
    assert not any("evidence/routerbench/convert.py" in c for c in commands)
    assert any("llmrouterbench-matrix.jsonl" in c for c in commands)
    # v1.299: the response-bank lines come right after the LLMRouterBench ones.
    at = commands.index("python evidence/response-bank/convert.py --out response-bank-matrix.jsonl")
    assert commands[at - 1] == "python evidence/routerbench/results.py --table evidence/llmrouterbench/results.json"


RUN_ONCE_CASES = [
    # (commands, the commands run): a file only read between the two copies leaves the repeat out
    (["a --out x.jsonl", "b --outcomes x.jsonl --out y.json", "a --out x.jsonl"],
     ["a --out x.jsonl", "b --outcomes x.jsonl --out y.json"]),
    (["a --out x.jsonl", "b --out x.jsonl", "a --out x.jsonl"],
     ["a --out x.jsonl", "b --out x.jsonl", "a --out x.jsonl"]),
    (["a --out x.jsonl", "b --out=x.jsonl", "a --out x.jsonl"],
     ["a --out x.jsonl", "b --out=x.jsonl", "a --out x.jsonl"]),
    (["a --out x.jsonl", "b --matrix y.jsonl >x.jsonl", "a --out x.jsonl"],
     ["a --out x.jsonl", "b --matrix y.jsonl >x.jsonl", "a --out x.jsonl"]),
    (["a --out x.jsonl", "b --registry x.jsonl", "a --out x.jsonl"],
     ["a --out x.jsonl", "b --registry x.jsonl", "a --out x.jsonl"]),
    (["a --out x.jsonl", "b --out tmp/x.jsonl", "a --out x.jsonl"],
     ["a --out x.jsonl", "b --out tmp/x.jsonl", "a --out x.jsonl"]),
    (["echo x", "echo x"], ["echo x", "echo x"]),
    (["a --matrix x.jsonl --out x.jsonl", "a --matrix x.jsonl --out x.jsonl"],
     ["a --matrix x.jsonl --out x.jsonl", "a --matrix x.jsonl --out x.jsonl"]),
    (["a >> x.jsonl", "a >> x.jsonl"], ["a >> x.jsonl", "a >> x.jsonl"]),
    # v1.216 (review): a read flag joined to its file by `=` is a mention, and `x.json.bak` names no file
    (["a --out x.jsonl", "b --outcomes=x.jsonl", "a --out x.jsonl"],
     ["a --out x.jsonl", "b --outcomes=x.jsonl", "a --out x.jsonl"]),
    (["a --out x.json.bak", "a --out x.json.bak"], ["a --out x.json.bak", "a --out x.json.bak"]),
    # a third copy is compared with the last copy run, not the first
    (["a --out x.jsonl", "w --out x.jsonl", "a --out x.jsonl", "r --table x.jsonl", "a --out x.jsonl"],
     ["a --out x.jsonl", "w --out x.jsonl", "a --out x.jsonl", "r --table x.jsonl"]),
]


@pytest.mark.parametrize("commands, run", RUN_ONCE_CASES)
def test_a_repeat_is_left_out_only_when_nothing_between_names_its_files_but_to_read(commands, run):
    assert run_once(commands) == run


def test_the_hand_built_list_count_is_the_one_design_states():
    assert len(RUN_ONCE_CASES) == 12


def test_regenerate_leaves_out_the_two_repeated_converter_lines():
    commands = expected_commands(readme())
    run = regenerate_commands(readme())
    assert len(commands) == 45 and len(run) == 48 and run[-5] == ledger_command()
    assert run[-4:] == registry_commands() == REGISTRY_LINES  # v1.443
    left_out = []
    for repeated, script in ((REPEATED, "llmrouterbench-delegation"), (RB_REPEATED, "response-bank-delegation")):
        assert commands.count(repeated) == 2 and run.count(repeated) == 1
        second = len(commands) - 1 - commands[::-1].index(repeated)
        assert commands[second + 1].startswith(f"python evidence/{script}/results.py --matrix")
        left_out.append(second)
    assert run == [c for k, c in enumerate(commands) if k not in left_out] + [ledger_command()] + REGISTRY_LINES


def test_the_rerun_subsections_are_in_readme_heading_order():
    # v1.278: SUBSECTIONS, which the top comment check and readme_blocks read, is the order of the
    # rerun subsections within the README headings (RouterBench, not rerun, is among them).
    section = readme().split(EVIDENCE, 1)[1].split("\n## ", 1)[0]
    headings = re.findall(r"^### (.+)$", section, re.M)
    assert [h for h in headings if h in SUBSECTIONS] == list(SUBSECTIONS)


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


def llmrouterbench_sha256():
    """The LLMRouterBench converter's pinned `SHA256`, read from its source (standard library only)."""
    found = re.findall(r'^SHA256 = "([0-9a-f]{64})"$', LLMROUTERBENCH.read_text(encoding="utf-8"), re.M)
    assert len(found) == 1
    return found[0]


def with_repeat(lines):
    """The Regenerate lines with the repeated converter line run again before the 13.13 script."""
    at = [k for k, line in enumerate(lines) if "llmrouterbench-delegation/results.py --matrix" in line]
    assert len(at) == 1
    return lines[:at[0]] + ["          " + REPEATED] + lines[at[0]:]


MUTANTS = {
    "a command dropped": lambda t: with_lines(t, lambda ls: ls[:3] + ls[4:]),
    "two commands swapped": lambda t: with_lines(t, lambda ls: swap(ls, 0, 4)),
    "an extra command": lambda t: with_lines(t, lambda ls: ls + ["          echo extra"]),
    "a path filter dropped": lambda t: t.replace('      - "pyproject.toml"\n', "", 1),
    "a write permission": lambda t: t.replace("  contents: read\n", "  contents: write\n", 1),
    "a secret": lambda t: t.replace("run: python -m pip install -e .\n",
                                    "run: python -m pip install -e .\n"
                                    "        env:\n          TOKEN: ${{ secrets.TOKEN }}\n", 1),
    "the compare step without variants.json": lambda t: t.replace(
        "evidence/delegation/variants.json evidence/tau2-bench-delegation/results.json",
        "evidence/tau2-bench-delegation/results.json", 1),
    "the compare step without llmrouterbench": lambda t: t.replace(
        "evidence/livecodebench/results.json evidence/llmrouterbench/results.json",
        "evidence/livecodebench/results.json", 1),
    "the compare step without pooled.json": lambda t: t.replace(
        "evidence/tau2-bench-delegation/results.json evidence/tau2-bench-delegation/pooled.json ",
        "evidence/tau2-bench-delegation/results.json ", 1),
    # v1.200: the LLMRouterBench delegation file, last in command order
    "the compare step without llmrouterbench delegation": lambda t: t.replace(
        "evidence/tau2-bench-delegation/pooled.json evidence/llmrouterbench-delegation/results.json ",
        "evidence/tau2-bench-delegation/pooled.json ", 1),
    # v1.316: the response-bank delegation file, now last in command order
    "the compare step without the response-bank delegation": lambda t: t.replace(
        "evidence/llmrouterbench-delegation/results.json evidence/response-bank-delegation/results.json ",
        "evidence/llmrouterbench-delegation/results.json ", 1),
    # v1.397: the ledger hand-off file and its line, after the README ones
    "the compare step without the ledger hand-off": lambda t: t.replace(
        "evidence/response-bank-delegation/results.json evidence/ledger-handoff/results.json ",
        "evidence/response-bank-delegation/results.json ", 1),
    "the ledger line dropped": lambda t: with_lines(t, lambda ls: [line for line in ls if line.strip() != LEDGER_LINE]),
    # v1.443: the registry-pair file, last in command order, and its evaluate line
    "the compare step without the registry pair": lambda t: t.replace(
        " evidence/ledger-handoff/results.json evidence/registry-pair/results.json\n",
        " evidence/ledger-handoff/results.json\n", 1),
    "a registry-pair line dropped": lambda t: with_lines(
        t, lambda ls: [line for line in ls if line.strip() != REGISTRY_LINES[1]]),
    # v1.299: the response-bank file, directly after the LLMRouterBench one
    "the compare step without the response bank": lambda t: t.replace(
        "evidence/llmrouterbench/results.json evidence/response-bank/results.json ",
        "evidence/llmrouterbench/results.json ", 1),
    "checkout with credentials": lambda t: t.replace("persist-credentials: false",
                                                     "persist-credentials: true", 1),
    "a job shell without pipefail": lambda t: t.replace(
        "    runs-on: ubuntu-24.04\n",
        "    runs-on: ubuntu-24.04\n    defaults:\n      run:\n        shell: bash -e\n", 1),
    "a skipped Regenerate": lambda t: t.replace(
        "      - name: Regenerate\n", "      - name: Regenerate\n        if: false\n", 1),
    "a Compare that may fail": lambda t: t.replace(
        "      - name: Compare\n", "      - name: Compare\n        continue-on-error: true\n", 1),
    "Regenerate in another folder": lambda t: t.replace(
        "      - name: Regenerate\n",
        "      - name: Regenerate\n        working-directory: elsewhere\n", 1),
    "a step shell override": lambda t: t.replace(
        "      - name: Compare\n", "      - name: Compare\n        shell: sh\n", 1),
    "a comment in Regenerate": lambda t: with_lines(t, lambda ls: ls[:1] + ["          # x"] + ls[1:]),
    "a job after the steps": lambda t: t + "  other:\n    runs-on: ubuntu-24.04\n",
    "the RouterBench reason dropped": lambda t: t.replace(" about 70 seconds.\n", "\n", 1),
    "the time limit dropped": lambda t: t.replace(LIMIT_LINE + "\n", "", 1),
    "the time limit raised by a minute": lambda t: t.replace(
        LIMIT_LINE + "\n", f"    timeout-minutes: {TIMEOUT_MINUTES + 1}\n", 1),
    "the time limit at GitHub's default": lambda t: t.replace(
        LIMIT_LINE + "\n", "    timeout-minutes: 360\n", 1),
    "the time limit on Regenerate instead": lambda t: t.replace(LIMIT_LINE + "\n", "", 1).replace(
        "      - name: Regenerate\n", f"      - name: Regenerate\n        timeout-minutes: {TIMEOUT_MINUTES}\n", 1),
    "the time-limit sentence dropped": lambda t: t.replace(
        f"# The job's time limit of {TIMEOUT_MINUTES} minutes", "# The job's limit", 1),
    # v1.215: the repeated-line rule
    "the repeated converter line kept": lambda t: with_lines(t, with_repeat),
    "the repeated-line sentence dropped": lambda t: t.replace(
        "# A README line identical to one already run in the step is not run again when no line\n"
        "# between them names one of its files except to read it (DESIGN.md 12.13).\n", "", 1),
    # v1.251: no cache between runs, so each run checks that the sources still serve the pinned files
    "a cache step before Install": lambda t: t.replace(
        "      - name: Install\n",
        "      - uses: actions/cache@v5\n        with:\n"
        "          path: ~/.cache/ai-model-routing-evidence/llmrouterbench\n"
        f"          key: llmrouterbench-{llmrouterbench_sha256()}\n"
        "      - name: Install\n", 1),
    "a pip cache on setup-python": lambda t: t.replace(
        '          python-version: "3.12"\n', '          python-version: "3.12"\n          cache: pip\n', 1),
    # v1.278: the top comment's list of the rerun subsections, and its width
    "a subsection dropped from the top comment": lambda t: t.replace(
        "# tau2-bench, LiveCodeBench, LLMRouterBench,", "# tau2-bench, LLMRouterBench,", 1),
    "two top comment lines joined": lambda t: t.replace(
        "AutoBench judges,\n# tau2-bench,", "AutoBench judges, tau2-bench,", 1),
}
CACHE_MUTANTS = {
    "a cache step before Install": f"step names {[None, None, None] + STEP_NAMES[2:]}",
    "a pip cache on setup-python": "setup-python is not one ci.yml Python",
}
REPEAT_MUTANTS = {
    "the repeated converter line kept": "Regenerate is not the README commands in order",
    "the repeated-line sentence dropped": REPEAT_PROBLEM,
}
COMMENT_MUTANTS = {
    "a subsection dropped from the top comment": SUBSECTION_PROBLEM,
    "two top comment lines joined": WIDTH_PROBLEM,
}
TIME_LIMIT_MUTANTS = {
    "the time limit dropped": LIMIT_PROBLEM,
    "the time limit raised by a minute": LIMIT_PROBLEM,
    "the time limit at GitHub's default": LIMIT_PROBLEM,
    "the time limit on Regenerate instead": LIMIT_PROBLEM,
    "the time-limit sentence dropped": SENTENCE_PROBLEM,
}


def test_the_mutant_count_is_the_one_design_states():
    assert len(MUTANTS) == 36
    assert len(CACHE_MUTANTS) == 2 and set(CACHE_MUTANTS) <= set(MUTANTS)
    assert len(TIME_LIMIT_MUTANTS) == 5 and set(TIME_LIMIT_MUTANTS) <= set(MUTANTS)
    assert len(REPEAT_MUTANTS) == 2 and set(REPEAT_MUTANTS) <= set(MUTANTS)
    assert len(COMMENT_MUTANTS) == 2 and set(COMMENT_MUTANTS) <= set(MUTANTS)


@pytest.mark.parametrize("name", sorted(REPEAT_MUTANTS))
def test_a_repeat_mutant_fails_on_the_one_check_it_names(name):
    text = workflow_text()
    mutant = MUTANTS[name](text)
    assert mutant != text, name
    assert problems(mutant, readme(), CI.read_text(encoding="utf-8")) == [REPEAT_MUTANTS[name]], name


@pytest.mark.parametrize("name", sorted(COMMENT_MUTANTS))
def test_a_comment_mutant_fails_on_the_one_check_it_names(name):
    # v1.278 (row T4): the joined lines leave the joined comment as it was, so width alone fails.
    text = workflow_text()
    mutant = MUTANTS[name](text)
    assert mutant != text, name
    assert problems(mutant, readme(), CI.read_text(encoding="utf-8")) == [COMMENT_MUTANTS[name]], name


@pytest.mark.parametrize("name", sorted(CACHE_MUTANTS))
def test_a_cache_mutant_fails_on_the_one_check_it_names(name):
    # v1.251 (row CI9): the workflow keeps no cache between runs, and the step checks hold it.
    text = workflow_text()
    mutant = MUTANTS[name](text)
    assert mutant != text, name
    assert problems(mutant, readme(), CI.read_text(encoding="utf-8")) == [CACHE_MUTANTS[name]], name


def test_the_design_no_cache_bullet_names_the_converter_sha256_constant():
    bullets = [line for line in DESIGN.read_text(encoding="utf-8").split("\n")
               if line.startswith("- No cache between runs (v1.251, row CI9): ")]
    assert len(bullets) == 1
    assert "the workflow keeps no cache, by choice" in bullets[0]
    assert "keyed on the LLMRouterBench converter's pinned `SHA256`" in bullets[0]
    # v1.252 (review iter-173 nit 2): the committed workflow holds no key on the pinned file.
    assert llmrouterbench_sha256() not in workflow_text()


def test_the_time_limit_is_ten_times_the_slowest_run_in_whole_five_minutes():
    assert TIMEOUT_MINUTES == 5 * math.ceil(10 * SLOWEST_RUN_SECONDS / 60 / 5)
    assert TIMEOUT_MINUTES < 360


def test_the_design_time_limit_bullet_gives_the_value_and_its_basis_run():
    bullets = [line for line in DESIGN.read_text(encoding="utf-8").split("\n")
               if line.startswith("- Time limit and retries (")]
    assert len(bullets) == 1
    bullet = bullets[0]
    assert f"sets `timeout-minutes: {TIMEOUT_MINUTES}`" in bullet
    # v1.374 (review iter-238 must-fix 1): the Tests sentence names the same limit line.
    assert f"the `runs-on` line and `{LIMIT_LINE}`, in that order" in bullet
    _, marker, rest = bullet.partition(
        "Basis (v1.217, row E17h; restated v1.225, row E17i, v1.268, row CI10, v1.301, row CI11, "
        "v1.302, row CI12, v1.321, row CI14, v1.374, row CI15, v1.395, row CI16, v1.398, row CI18, "
        "v1.399, row CI19, v1.401, row CI21, v1.407, row CI22, and v1.442, row CI24): ")
    assert marker
    # v1.391 (row DOC26): the basis ends at the one history pointer; the earlier bases, their runs and
    # where their time went are in CHANGELOG.md, so the bullet holds no history sentence and none of
    # the earlier basis runs (v1.152 to v1.321), and a restatement moves the basis it replaces there.
    basis, pointer, _ = rest.partition(f" (history: CHANGELOG.md {TIME_LIMIT_HISTORY}). ")
    assert pointer and bullet.count("(history: CHANGELOG.md ") == 1
    assert not re.search(r"The v1\.\d+ basis (?:was|is)|Where the time went", bullet)
    for run in EARLIER_BASIS_RUNS:
        assert run not in bullet, run
    assert ("A change of the value states its new basis in this bullet in the same commit, and the basis it "
            "replaces goes to that commit's CHANGELOG.md line, its version joining this bullet's history pointer, "
            "never to a history sentence here (v1.391, row DOC26)") in basis
    assert len(bullet.encode("utf-8")) <= 6_000
    # v1.401 (row CI21): the basis is the slowest run on main whatever its lines, so the bullet names no
    # line set, a change of the lines keeps the value, and the bullet says why an overstated limit is cheap.
    # Review iter-261 should-fix 2: a failed or cancelled run is no basis, so the limit stays under 360.
    assert basis.startswith("the slowest successful run of this workflow on `main`, whatever `Regenerate` lines it ran "
                            "(v1.401, row CI21). ")
    assert "a change of the lines keeps the value and its basis" in basis
    assert "it only bounds a stalled download, far under GitHub's 360-minute default" in basis
    for gone in ("lines in force", "on these lines", "starts the basis again", "`### "):
        assert gone not in bullet, gone
    assert re.search(rf"run {SLOWEST_RUN_ID} on `{SLOWEST_RUN_SHA}`, which took {SLOWEST_RUN_SECONDS} seconds "
                     "from its start to its last update", basis)
    # v1.407 (row CI22): a run that was rerun counts by its latest attempt, timed from that attempt's
    # start, and the basis names the attempt when it is a rerun.
    assert ("(v1.401, row CI21). A run that was rerun counts by its latest attempt, the one `gh run list` "
            "reports, from that attempt's start, since a rerun downloads every file again (v1.407, row CI22). "
            ) in basis
    assert "all on `main` and all successful by their latest attempt, the slowest is " in basis
    rerun = f"to its last update (attempt {SLOWEST_RUN_ATTEMPT}, a rerun; its `regenerate` job "
    assert (rerun in basis) == (SLOWEST_RUN_ATTEMPT > 1), rerun
    assert SLOWEST_RUN_ATTEMPT > 1 or "a rerun; its" not in basis
    tenfold = 10 * SLOWEST_RUN_SECONDS
    assert f"{tenfold:,} seconds is {tenfold / 60:.1f} minutes, so {TIMEOUT_MINUTES}." in basis
    # v1.225: the run length past which the rule gives more than the value in force, six times
    # the value in seconds, so the next restatement is named in step with the value.
    assert f"so a run over {6 * TIMEOUT_MINUTES} seconds restates the value (v1.225), and no run lowers it" in basis
    assert 5 * math.ceil(10 * 6 * TIMEOUT_MINUTES / 60 / 5) == TIMEOUT_MINUTES
    assert 5 * math.ceil(10 * (6 * TIMEOUT_MINUTES + 1) / 60 / 5) == TIMEOUT_MINUTES + 5
    # v1.400 (row T9, review iter-258 should-fix 1): the seconds, runs and minutes of the Tests, band and
    # comment sentences are the constants', so a restatement that leaves one stale fails, and the basis
    # names one count of the runs it read in both places it gives it.
    assert (f"By the rule {6 * TIMEOUT_MINUTES + 1} to {6 * (TIMEOUT_MINUTES + 5)} seconds gives "
            f"{TIMEOUT_MINUTES + 5}, so a run over {6 * TIMEOUT_MINUTES} seconds") in basis
    assert f"ends, after the runner sentences, with the sentence `{LIMIT_SENTENCE}` Tests in " in bullet
    tests = bullet.split(" Tests in `tests/test_evidence_workflow.py` require ", 1)[1]
    for pinned in (f"ten times the recorded {SLOWEST_RUN_SECONDS} seconds rounded up to whole five minutes "
                   "and under 360,",
                   f"the run {SLOWEST_RUN_ID} and its {SLOWEST_RUN_SECONDS} seconds in one clause (v1.218), "
                   f"the arithmetic to {TIMEOUT_MINUTES} and",
                   f"six times the value in seconds ({6 * TIMEOUT_MINUTES}),",
                   f"each of {len(TIME_LIMIT_MUTANTS)} broken workflows fails the time-limit check it names",
                   f"raised by a minute (to {TIMEOUT_MINUTES + 1}), set to 360,",
                   "(v1.401, row CI21) the rule to name no line set, a line change to keep the value and the "
                   "replaced basis run to be the faster, and (v1.407, row CI22) a rerun to count by its latest "
                   "attempt;"):
        assert pinned in tests, pinned
    counts = re.findall(r"\b[Oo]f the ([\d,]+) runs\b", bullet)
    assert len(counts) == 2 and counts[0] == counts[1], counts


def test_the_restating_changelog_line_names_the_new_basis_and_the_one_it_replaces():
    versions = TIME_LIMIT_HISTORY.split(", ")
    version, run, seconds, sha = REPLACED_BASIS
    assert versions[-1] == RESTATING_VERSION and version in versions[:-1]
    assert EARLIER_BASIS_RUNS[0] == str(run) and str(SLOWEST_RUN_ID) not in EARLIER_BASIS_RUNS
    assert seconds < SLOWEST_RUN_SECONDS  # v1.401 (row CI21): no run lowers the value
    lines = [line for line in CHANGELOG.read_text(encoding="utf-8").split("\n")
             if line.startswith(f"- {RESTATING_VERSION} (")]
    assert len(lines) == 1
    line = lines[0]
    old_minutes = 5 * math.ceil(10 * seconds / 60 / 5)
    assert f"`timeout-minutes` goes from {old_minutes} to {TIMEOUT_MINUTES}, " in line
    assert f"ten times the {SLOWEST_RUN_SECONDS} seconds of run {SLOWEST_RUN_ID} on `{SLOWEST_RUN_SHA}`, " in line
    assert f"The {version} basis it replaces is the {seconds} seconds of run {run} on `{sha}`, " in line
    assert f"over {6 * TIMEOUT_MINUTES} seconds restates it" in line


@pytest.mark.parametrize("name", sorted(TIME_LIMIT_MUTANTS))
def test_a_time_limit_mutant_fails_on_the_check_it_names(name):
    text = workflow_text()
    mutant = MUTANTS[name](text)
    assert mutant != text, name
    assert TIME_LIMIT_MUTANTS[name] in problems(mutant, readme(), CI.read_text(encoding="utf-8")), name


@pytest.mark.parametrize("name", ["the compare step without llmrouterbench",
                                  "the compare step without llmrouterbench delegation",
                                  "the compare step without pooled.json",
                                  "the compare step without the response bank",
                                  "the compare step without the ledger hand-off",  # v1.397, row E23c
                                  "the compare step without the registry pair",  # v1.443, row E24e
                                  "the compare step without the response-bank delegation",  # v1.392, row DOC21c
                                  "the compare step without variants.json"])
def test_a_compare_mutant_fails_on_the_compare_line_alone(name):
    # v1.85 review: a mutant that broke a Regenerate line instead would pass the test below.
    mutant = MUTANTS[name](workflow_text())
    assert problems(mutant, readme(), CI.read_text(encoding="utf-8")) == [
        "Compare is not the diff of the committed results"], name


@pytest.mark.parametrize("name", sorted(MUTANTS))
def test_a_broken_workflow_fails_the_check(name):
    text = workflow_text()
    mutant = MUTANTS[name](text)
    assert mutant != text, name
    assert problems(mutant, readme(), CI.read_text(encoding="utf-8")), name


# --- v1.49: one pinned runner image for both workflows --------------------------------------

PINNED = re.compile(r"^    runs-on: (ubuntu-\d\d\.\d\d)$", re.M)


def comment_above_jobs(text):
    """The column-0 `# ` comment lines directly above `jobs:`, joined with spaces."""
    lines = []
    for line in reversed(text.split("\njobs:\n", 1)[0].split("\n")):
        if not line.startswith("# "):
            break
        lines.insert(0, line[2:])
    return " ".join(lines)


def is_date(text):
    try:
        datetime.date.fromisoformat(text)
    except ValueError:
        return False
    return True


def runner_problems(ci_text, text):
    """Every way the two workflows break the v1.49 runner clause of DESIGN 12.13."""
    found, labels = [], []
    for name, body in (("ci.yml", ci_text), ("evidence.yml", text)):
        runs_on = re.findall(r"^\s*runs-on:.*$", body, re.M)
        pinned = PINNED.findall(body)
        if len(runs_on) != 1 or len(pinned) != 1:
            found.append(f"{name} does not run on one versioned ubuntu image")
            continue
        labels.append(pinned[0])
        dated = re.search(rf"pinned to the {re.escape(pinned[0])} image \((\d{{4}}-\d\d-\d\d), ",
                          comment_above_jobs(body))
        if not dated or not is_date(dated.group(1)):
            found.append(f"{name} has no dated comment above jobs: naming {pinned[0]}")
    if len(set(labels)) > 1:
        found.append("the two workflows run on different images")
    return found


def test_both_workflows_run_on_one_pinned_image():
    ci_text = CI.read_text(encoding="utf-8")
    assert runner_problems(ci_text, workflow_text()) == []
    assert PINNED.findall(ci_text) == PINNED.findall(workflow_text()) == ["ubuntu-24.04"]
    assert "ubuntu-latest" in comment_above_jobs(ci_text)


def pin(label):
    return lambda t: t.replace("    runs-on: ubuntu-24.04\n", f"    runs-on: {label}\n", 1)


RUNNER_MUTANTS = {
    "ci.yml back on ubuntu-latest": ("ci", pin("ubuntu-latest")),
    "evidence.yml back on ubuntu-latest": ("evidence", pin("ubuntu-latest")),
    "the two files on different images": ("evidence", pin("ubuntu-26.04")),
    "the ci.yml comment dropped": ("ci", lambda t: re.sub(
        r"(?m)^# .*\n(?=(?:# .*\n)*jobs:\n)", "", t)),
    "the evidence.yml comment without its date": ("evidence", lambda t: t.replace(
        "image (2026-11-06, ", "image (", 1)),
    "the ci.yml comment with a date that does not exist": ("ci", lambda t: t.replace(
        "image (2026-11-06, ", "image (2026-99-99, ", 1)),
}


@pytest.mark.parametrize("name", sorted(RUNNER_MUTANTS))
def test_a_runner_left_unpinned_or_undated_fails_the_check(name):
    texts = {"ci": CI.read_text(encoding="utf-8"), "evidence": workflow_text()}
    which, change = RUNNER_MUTANTS[name]
    mutant = dict(texts, **{which: change(texts[which])})
    assert mutant[which] != texts[which], name
    assert runner_problems(mutant["ci"], mutant["evidence"]), name


# v1.316 (row E21d): the response-bank delegation block is rerun after the LLMRouterBench delegation one
RB_DELEGATION_LINE = ("python evidence/response-bank-delegation/results.py --matrix response-bank-matrix.jsonl "
                      "--registry evidence/response-bank-delegation/registry.json "
                      "--out evidence/response-bank-delegation/results.json")
RB_TABLES = ["python evidence/delegation/results.py --table evidence/response-bank-delegation/results.json",
             "python evidence/delegation/results.py --table evidence/response-bank-delegation/results.json "
             "--bar 0.8 --point 0"]


def test_the_workflow_reruns_the_response_bank_delegation_block():
    assert SUBSECTIONS[-1] == "Delegation on the LLM Routing Response Bank"
    text = workflow_text()
    run = [line.strip() for line in regenerate_lines(text)[1]]
    assert RB_DELEGATION_LINE in run
    at = run.index(RB_DELEGATION_LINE)
    assert run[at - 1] == ("python evidence/delegation/results.py --table "
                           "evidence/llmrouterbench-delegation/results.json --bar 0.1 --point 0")
    assert run[at + 1:at + 3] == RB_TABLES
    assert run.count("python evidence/response-bank/convert.py --out response-bank-matrix.jsonl") == 1
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert compare.endswith(" evidence/llmrouterbench-delegation/results.json "
                            "evidence/response-bank-delegation/results.json evidence/ledger-handoff/results.json "
                            "evidence/registry-pair/results.json")


def test_the_workflow_reruns_the_ledger_handoff_line_after_the_readme_commands():
    # v1.397 (row E23c, DESIGN 13.15 Workflow bullet); from v1.443 the registry-pair block follows it
    assert ledger_command() == LEDGER_LINE
    text = workflow_text()
    run = [line.strip() for line in regenerate_lines(text)[1]]
    assert run[-5] == LEDGER_LINE and run[-7:-5] == RB_TABLES and run.count(LEDGER_LINE) == 1
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert compare.endswith(" evidence/response-bank-delegation/results.json evidence/ledger-handoff/results.json "
                            "evidence/registry-pair/results.json")
    assert (ROOT / "evidence" / "ledger-handoff" / "results.json").is_file()
    ci_text = CI.read_text(encoding="utf-8")
    assert problems(MUTANTS["the ledger line dropped"](text), readme(), ci_text) == [
        "Regenerate is not the README commands in order"]
    design = DESIGN.read_text(encoding="utf-8")
    section = design.split("\n### 12.13 ", 1)[1].split("\n### ", 1)[0]
    assert f"each of {len(MUTANTS)} broken workflows fails the check, the eight `Compare` mutants" in section
    assert "then (v1.397) the regenerate line of `evidence/ledger-handoff/RESULTS.md` (13.15)" in section
    assert "fourteen files from `evidence/autobench-2026/results.json` to `evidence/registry-pair/results.json`" in section
    # v1.401 (row CI21): the basis is the slowest run on main, whatever its lines; v1.407 (row CI22),
    # by its latest attempt.
    assert (f"all on `main` and all successful by their latest attempt, the slowest is run {SLOWEST_RUN_ID} on "
            f"`{SLOWEST_RUN_SHA}`, "
            in section)
    spec = design.split("\n### 13.15 ", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in spec.split("\n") if line.startswith("- Workflow (v1.397, row E23c): ")]
    assert len(bullets) == 1 and f"`{LEDGER_LINE}`" in bullets[0]
    # Review iter-257 must-fix 1: the sentence states the rule in force, in the present tense (v1.401).
    assert ("The line keeps the time limit and its basis, the slowest successful run of the workflow on `main` "
            "whatever its lines (12.13, v1.401)") in bullets[0]
    # Review iter-267 nit (v1.442, row CI24): the sentence also names the v1.407 rerun rule.
    assert bullets[0].endswith("whatever its lines (12.13, v1.401), a run that was rerun counting by its latest "
                               "attempt from that attempt's start (12.13, v1.407)")


def test_the_workflow_reruns_the_registry_pair_block_last():
    # v1.443 (row E24e, DESIGN 12.13 Registry pair bullet): the four lines of the RESULTS.md block, after
    # the ledger line, and the results file last in Compare; the README intro names it only with E24c.
    assert registry_commands() == REGISTRY_LINES
    text = workflow_text()
    run = [line.strip() for line in regenerate_lines(text)[1]]
    assert run[-4:] == REGISTRY_LINES and run[-5] == LEDGER_LINE
    assert all(run.count(line) == 1 for line in REGISTRY_LINES)
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert compare.endswith(" evidence/ledger-handoff/results.json evidence/registry-pair/results.json")
    assert (ROOT / "evidence" / "registry-pair" / "results.json").is_file()
    assert out_paths(regenerate_commands(readme()))[-1] == "evidence/registry-pair/results.json"
    assert "evidence/registry-pair/results.json" not in out_paths(readme_commands(readme()))
    ci_text = CI.read_text(encoding="utf-8")
    assert problems(MUTANTS["a registry-pair line dropped"](text), readme(), ci_text) == [
        "Regenerate is not the README commands in order"]
    section = DESIGN.read_text(encoding="utf-8").split("\n### 12.13 ", 1)[1].split("\n### ", 1)[0]
    bullets = [line for line in section.split("\n") if line.startswith("- Registry pair is rerun (v1.443, row E24e): ")]
    assert len(bullets) == 1
    assert ("and (v1.443) the four lines of the `## Regenerate` block of `evidence/registry-pair/RESULTS.md` "
            "without its install line (12.24)") in section
