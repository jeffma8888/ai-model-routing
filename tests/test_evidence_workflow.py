"""The `evidence` workflow reruns the README regenerate commands of the AutoBench-based
subsections, from v1.55 the tau2-bench one, from v1.65 the LiveCodeBench one, from v1.80 the tau2-bench
delegation one, from v1.84 its pooled run, from v1.168 the LLMRouterBench one, from v1.200 the
LLMRouterBench delegation one and from v1.299 the LLM Routing Response Bank one on GitHub (from
v1.215 running a repeated line once), from v1.397 last the one regenerate line of
evidence/ledger-handoff/RESULTS.md (DESIGN 13.15), which has no README subsection, from v1.443
after it the `## Regenerate` block of evidence/registry-pair/RESULTS.md (DESIGN 12.24), which has
none yet either, from v1.472 that of evidence/registry-pair-delegation/RESULTS.md (DESIGN 13.17) and
from v1.489 that of evidence/longtail-swe/RESULTS.md (DESIGN 12.26), with `pyarrow` installed for
it, from v1.525 the `## Slices` block of evidence/autobench-2026/RESULTS.md (DESIGN 12.27), from v1.530 that
of evidence/livecodebench/RESULTS.md (DESIGN 12.28), from v1.544 the `## Cascades` block of
evidence/tau2-bench/RESULTS.md (DESIGN 12.29), from v1.559 last that of evidence/livecodebench/RESULTS.md
(DESIGN 12.30), and fails when a committed results file changes (DESIGN
12.13, v1.30),
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
lines under 100 columns. From v1.547 `paths` names each file outside `evidence/` and
`model_routing/` that the job's code loads by path, at any depth, found by a fail-closed `ast` read.

The workflow is read with a line parser for its own shape (no YAML library, so this runs in
CI); the run itself is checked on GitHub, not here."""

import ast
import datetime
import math
import os
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
# v1.443 (row E24e): the registry-pair `## Regenerate` block, read from their RESULTS.md, runs after the
# ledger line (DESIGN 12.13); from v1.452 (row E24c) the README `### Registry pair` block is the same block.
REGISTRY_NOTES = "evidence/registry-pair/RESULTS.md"
REGISTRY_LINES = [
    "python evidence/registry-pair/convert.py --out registry-pair-matrix.jsonl",
    "model-routing evaluate --outcomes registry-pair-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json "
    "> registry-pair-evaluate.json",
    "python evidence/routerbench/results.py --evaluate registry-pair-evaluate.json "
    "--out evidence/registry-pair/results.json",
    "python evidence/routerbench/results.py --table evidence/registry-pair/results.json"]
# v1.472 (row E25c): the registry-pair delegation results have no README subsection yet (row E25e);
# their `## Regenerate` block, read from their RESULTS.md, runs after the registry-pair lines, and the
# v1.215 rule leaves out its first line, the 12.23 converter line those lines already ran (DESIGN 12.13,
# 13.17 Workflow bullet).
REGISTRY_DELEGATION_NOTES = "evidence/registry-pair-delegation/RESULTS.md"
REGISTRY_DELEGATION_LINES = [
    "python evidence/registry-pair/convert.py --out registry-pair-matrix.jsonl",
    "python evidence/registry-pair-delegation/results.py --matrix registry-pair-matrix.jsonl "
    "--out evidence/registry-pair-delegation/results.json",
    "python evidence/delegation/results.py --table evidence/registry-pair-delegation/results.json",
    "python evidence/delegation/results.py --table evidence/registry-pair-delegation/results.json "
    "--bar 0.8 --point 0"]
REGISTRY_DELEGATION_RUN = REGISTRY_DELEGATION_LINES[1:]
# v1.489 (row E26d): the Longtail-SWE results have no README subsection yet (row E26e); their `## Regenerate`
# block, read from their RESULTS.md, runs last. It opens with the `evidence` extra's install line, and the
# `Install` step adds that extra's `pyarrow` pin, the 12.25 parquet reader, to the package (DESIGN 12.13).
LONGTAIL_NOTES = "evidence/longtail-swe/RESULTS.md"
LONGTAIL_INSTALL = 'python -m pip install -e ".[evidence]"'
LONGTAIL_LINES = [
    "python evidence/longtail-swe/convert.py --out longtail-swe-matrix.jsonl",
    "model-routing evaluate --outcomes longtail-swe-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json "
    "> longtail-swe-evaluate.json",
    "python evidence/routerbench/results.py --evaluate longtail-swe-evaluate.json "
    "--out evidence/longtail-swe/results.json",
    "python evidence/routerbench/results.py --table evidence/longtail-swe/results.json"]
# v1.525 (row STRAT3g): the README part on slices (row STRAT4, v1.531) holds none of it; the one `bash` block of
# `## Slices` in their RESULTS.md (DESIGN 12.27), which has no install line, runs last, and its four files end Compare.
SLICES_NOTES = "evidence/autobench-2026/RESULTS.md"
SLICE_FILES = ["evidence/autobench-2026/slices-difficulty.json", "evidence/autobench-2026/slices-skill.json",
               "evidence/autobench-2026/slices-difficulty-min10.json", "evidence/autobench-2026/slices-skill-min10.json"]
SLICES_LINES = [
    "python evidence/autobench-2026/convert.py --out autobench-labels.jsonl --task-by all --labels",
    "model-routing evaluate --outcomes autobench-labels.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --slice-by difficulty "
    "--json > autobench-slices-difficulty.json",
    "python evidence/routerbench/results.py --evaluate autobench-slices-difficulty.json "
    "--out evidence/autobench-2026/slices-difficulty.json",
    "model-routing evaluate --outcomes autobench-labels.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --slice-by skill "
    "--json > autobench-slices-skill.json",
    "python evidence/routerbench/results.py --evaluate autobench-slices-skill.json "
    "--out evidence/autobench-2026/slices-skill.json",
    "model-routing evaluate --outcomes autobench-labels.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --slice-by difficulty "
    "--min-samples 10 --json > autobench-slices-difficulty-min10.json",
    "python evidence/routerbench/results.py --evaluate autobench-slices-difficulty-min10.json "
    "--out evidence/autobench-2026/slices-difficulty-min10.json",
    "model-routing evaluate --outcomes autobench-labels.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --slice-by skill "
    "--min-samples 10 --json > autobench-slices-skill-min10.json",
    "python evidence/routerbench/results.py --evaluate autobench-slices-skill-min10.json "
    "--out evidence/autobench-2026/slices-skill-min10.json"]
SLICES_COMPARE = "".join(f" {path}" for path in SLICE_FILES)
# v1.530 (row STRAT3i): the README part on slices (row STRAT4, v1.531) holds none of this either; the one
# `bash` block of `## Slices` in their RESULTS.md (DESIGN 12.28) runs after the AutoBench one, and its file ends Compare.
LCB_SLICES_NOTES = "evidence/livecodebench/RESULTS.md"
LCB_SLICE_FILE = "evidence/livecodebench/slices-difficulty.json"
LCB_SLICES_LINES = [
    "python evidence/livecodebench/convert.py --out livecodebench-labels.jsonl --labels",
    "model-routing evaluate --outcomes livecodebench-labels.jsonl --bar 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 "
    "--seeds 50 --flavor cost_blind --slice-by difficulty --json > livecodebench-slices-difficulty.json",
    "python evidence/routerbench/results.py --evaluate livecodebench-slices-difficulty.json "
    "--out evidence/livecodebench/slices-difficulty.json"]
# v1.544 (row ESC3e): the README part on cascades (DESIGN 7 v1.543, row ESC3d) holds no block either; the one
# `bash` block of `## Cascades` in the tau2-bench RESULTS.md (DESIGN 12.29) runs after the slices ones, and its
# file ends Compare.
CASCADE_NOTES = "evidence/tau2-bench/RESULTS.md"
CASCADE_FILE = "evidence/tau2-bench/cascades.json"
CASCADE_LINES = [
    "python evidence/tau2-bench/cascades.py --out tau2-cascades.jsonl",
    "model-routing evaluate --outcomes tau2-cascades.jsonl --bar 0.3 0.4 0.5 0.6 0.7 0.8 --seeds 50 --json "
    "> tau2-cascades-evaluate.json",
    "python evidence/routerbench/results.py --evaluate tau2-cascades-evaluate.json "
    "--out evidence/tau2-bench/cascades.json"]
# v1.559 (row ESC3i): the one `bash` block of `## Cascades` in the LiveCodeBench RESULTS.md (DESIGN 12.30) runs
# after the tau2-bench one, and its file ends Compare.
LCB_CASCADE_NOTES = "evidence/livecodebench/RESULTS.md"
LCB_CASCADE_FILE = "evidence/livecodebench/cascades.json"
LCB_CASCADE_LINES = [
    "python evidence/livecodebench/cascades.py --out livecodebench-cascades.jsonl",
    "model-routing evaluate --outcomes livecodebench-cascades.jsonl --bar 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 "
    "--seeds 50 --flavor cost_blind --json > livecodebench-cascades-evaluate.json",
    "python evidence/routerbench/results.py --evaluate livecodebench-cascades-evaluate.json "
    "--out evidence/livecodebench/cascades.json"]
# What follows the Longtail-SWE file in Compare: the four AutoBench slice files, then the LiveCodeBench one (v1.530),
# then the tau2-bench cascades one (v1.544) and the LiveCodeBench cascades one (v1.559).
TAIL_COMPARE = SLICES_COMPARE + f" {LCB_SLICE_FILE} {CASCADE_FILE} {LCB_CASCADE_FILE}"
EVIDENCE = "## Evidence: held-out results on public data\n"
SUBSECTIONS = ("AutoBench", "AutoBench judges", "tau2-bench", "LiveCodeBench", "LLMRouterBench",
               "LLM Routing Response Bank", "Delegation on AutoBench", "Delegation on tau2-bench",
               "Delegation on LLMRouterBench", "Delegation on the LLM Routing Response Bank")
INSTALL = "python -m pip install -e ."


def pyarrow_pin():
    """The one `pyarrow` item of the `pyproject.toml` `evidence` extra (v1.489), read by a regex, since
    Python 3.10 has no `tomllib`."""
    text = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    extra = re.findall(r"^evidence = \[(.*)\]$", text, re.M)
    assert len(extra) == 1
    pins = [item for item in re.findall(r'"([^"]+)"', extra[0]) if re.match(r"pyarrow(?![\w.-])", item)]
    assert len(pins) == 1
    return pins[0]


# v1.489 (row E26d): the `Install` line, the README blocks' install line with the `pyarrow` pin added
WORKFLOW_INSTALL = f'{INSTALL} "{pyarrow_pin()}"'
ON = (
    "on:\n"
    "  workflow_dispatch:\n"
    "  push:\n"
    "    branches: [main]\n"
    "    paths:\n"
    "      - \"evidence/**\"\n"
    "      - \"model_routing/**\"\n"
    "      - \"research/escalation_public_tests.py\"\n"  # v1.559 (row ESC3i)
    "      - \"research/escalation_signals.py\"\n"  # v1.547 (row CI28)
    "      - \"research/livecodebench_cost.py\"\n"  # v1.559 (row ESC3i)
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
                   + ", ".join(SUBSECTIONS[:-1]) + f" and {SUBSECTIONS[-1]}, and those of {LEDGER_NOTES}, "
                   f"{REGISTRY_NOTES}, {REGISTRY_DELEGATION_NOTES}, {LONGTAIL_NOTES}, the Slices sections of {SLICES_NOTES} "
                   f"and {LCB_SLICES_NOTES} and the Cascades sections of {CASCADE_NOTES} and {LCB_CASCADE_NOTES}, which")
# v1.489, v1.525, v1.530, v1.544, v1.559
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


def block_commands(notes, install=INSTALL):
    """The lines of the one `bash` block of a RESULTS.md `## Regenerate`, without its install line
    `install` (v1.443, the registry pair; v1.472, its delegation; v1.489, Longtail-SWE, whose block
    opens with the `evidence` extra's install line)."""
    text = (ROOT / notes).read_text(encoding="utf-8")
    section = text.split("\n## Regenerate\n", 1)[1].split("\n## ", 1)[0]
    found = re.findall(r"```bash\n(.*?)```", section, re.S)
    assert len(found) == 1
    block = found[0].rstrip("\n").split("\n")
    assert block[0] == install and not any(line.startswith(INSTALL) for line in block[1:])
    return block[1:]


def registry_commands():
    return block_commands(REGISTRY_NOTES)


def registry_delegation_commands():
    return block_commands(REGISTRY_DELEGATION_NOTES)


def longtail_commands():
    return block_commands(LONGTAIL_NOTES, LONGTAIL_INSTALL)


def slices_commands(notes=SLICES_NOTES, heading="Slices"):
    """The lines of the one `bash` block of the AutoBench RESULTS.md `## Slices` (v1.525, DESIGN 12.27), or from
    v1.530 of the LiveCodeBench one (DESIGN 12.28), or from v1.544 of the tau2-bench `## Cascades` (DESIGN 12.29),
    which, unlike a `## Regenerate` block, opens with no install line."""
    text = (ROOT / notes).read_text(encoding="utf-8")
    assert text.count(f"\n## {heading}\n") == 1
    section = text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]
    found = re.findall(r"```bash\n(.*?)```", section, re.S)
    assert len(found) == 1
    block = found[0].rstrip("\n").split("\n")
    assert not any(line.startswith(INSTALL) for line in block)
    return block


def cascade_commands():
    """The lines of the one `bash` block of the tau2-bench RESULTS.md `## Cascades` (v1.544, DESIGN 12.29)."""
    return slices_commands(CASCADE_NOTES, "Cascades")


def lcb_cascade_commands():
    """The lines of the one `bash` block of the LiveCodeBench RESULTS.md `## Cascades` (v1.559, DESIGN 12.30)."""
    return slices_commands(LCB_CASCADE_NOTES, "Cascades")


def before_slices(run):
    """The `Regenerate` lines before the slices blocks, the AutoBench one (v1.525) and then the LiveCodeBench
    one (v1.530), and the cascades blocks, the tau2-bench one (v1.544) and the LiveCodeBench one (v1.559), which
    end them."""
    tail = SLICES_LINES + LCB_SLICES_LINES + CASCADE_LINES + LCB_CASCADE_LINES
    assert run[-len(tail):] == tail
    return run[:-len(tail)]


def results_md_commands():
    """The RESULTS.md lines the step takes, in order: the ledger one (v1.397), the registry-pair block
    (v1.443), the registry-pair delegation one (v1.472) and the Longtail-SWE one (v1.489)."""
    return [ledger_command()] + registry_commands() + registry_delegation_commands() + longtail_commands()


def readme_commands(text):
    """The lines the README evidence sentence speaks for: the README commands, the ledger line and the
    registry-pair block, whose README subsection holds it (v1.452). The 13.17 and 12.26 blocks join them
    with their own subsections (rows E25e and E26e), so the sentence does not count their results files
    yet (v1.472, v1.489)."""
    return run_once(expected_commands(text) + [ledger_command()] + registry_commands())


def regenerate_commands(text):
    """The lines the workflow reruns: the README commands, the ledger line (v1.397), from v1.452 (row E24c)
    the registry-pair block, which its README subsection holds too (its test requires the two blocks equal),
    from v1.472 (row E25c) the registry-pair delegation block and from v1.489 (row E26d) the Longtail-SWE
    block, then from v1.525 (row STRAT3g) the AutoBench `## Slices` block, from v1.530 (row STRAT3i) the
    LiveCodeBench one, from v1.544 (row ESC3e) the tau2-bench `## Cascades` block and from v1.559 (row ESC3i) the
    LiveCodeBench one, run last. `readme_commands`
    is the part
    the README evidence sentence speaks for (v1.464, row DOC39b, review iter-314 nit 6; again from v1.472)."""
    return run_once(expected_commands(text) + results_md_commands() + slices_commands()
                    + slices_commands(LCB_SLICES_NOTES) + cascade_commands() + lcb_cascade_commands())


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
    # v1.445 (row DOC28b): the sentence counts the results files of the commands it speaks for, which it
    # named one by one to v1.444, so a command that adds or drops an `--out` file changes the count.
    count = len(out_paths(readme_commands(text)))
    return (
        "On GitHub, the `evidence` workflow "
        "([.github/workflows/evidence.yml](.github/workflows/evidence.yml)) reruns the "
        "regenerate commands of the AutoBench, AutoBench judges, tau2-bench, LiveCodeBench, "
        "LLMRouterBench, LLM Routing Response Bank, registry pair and "
        "delegation "
        "subsections and of the ledger hand-off results below, "
        f"downloading the pinned files, and fails if one of the {count} results files those commands write "
        "changes by a byte; RouterBench "
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
    if install["run"] != [WORKFLOW_INSTALL] or "uses" in install:
        found.append("install line differs")
    commands = regenerate_commands(readme_text)
    if regenerate["run"] != commands or "uses" in regenerate:
        found.append("Regenerate is not the README commands in order")
    diff = "git diff --exit-code -- " + " ".join(out_paths(commands))
    if compare["run"] != [diff] or "uses" in compare:
        found.append("Compare is not the diff of the committed results")
    return found


def subsection_of(text, heading):
    """The README part under the `## ` heading `heading`, to the next `## ` heading (v1.544)."""
    assert text.count(f"\n{heading}\n") == 1
    return text.split(f"\n{heading}\n", 1)[1].split("\n## ", 1)[0]


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


def test_regenerate_leaves_out_the_three_repeated_converter_lines():
    commands = expected_commands(readme())
    full = regenerate_commands(readme())
    run = before_slices(full)  # v1.525, v1.530, v1.544, v1.559: the twelve slices lines and the six cascade lines end
    # the step, none of them a repeat
    assert slices_commands() == SLICES_LINES and slices_commands(LCB_SLICES_NOTES) == LCB_SLICES_LINES
    assert cascade_commands() == CASCADE_LINES and lcb_cascade_commands() == LCB_CASCADE_LINES and len(full) == 73
    assert len(commands) == 45 and len(run) == 55 and run[-12] == ledger_command()
    assert run[-11:-7] == registry_commands() == REGISTRY_LINES  # v1.443
    # v1.472: the third repeat is the 12.23 converter line, which opens the 13.17 block too
    assert registry_delegation_commands() == REGISTRY_DELEGATION_LINES
    assert REGISTRY_DELEGATION_LINES[0] == REGISTRY_LINES[0] and run.count(REGISTRY_LINES[0]) == 1
    assert run[-7:-4] == REGISTRY_DELEGATION_RUN
    assert run[-4:] == longtail_commands() == LONGTAIL_LINES  # v1.489, no repeat
    left_out = []
    for repeated, script in ((REPEATED, "llmrouterbench-delegation"), (RB_REPEATED, "response-bank-delegation")):
        assert commands.count(repeated) == 2 and run.count(repeated) == 1
        second = len(commands) - 1 - commands[::-1].index(repeated)
        assert commands[second + 1].startswith(f"python evidence/{script}/results.py --matrix")
        left_out.append(second)
    assert run == ([c for k, c in enumerate(commands) if k not in left_out] + [ledger_command()]
                   + REGISTRY_LINES + REGISTRY_DELEGATION_RUN + LONGTAIL_LINES)
    # The 12.13 count of the lines it takes from `## Regenerate` blocks, and how many it runs
    taken = results_md_commands()
    assert len(taken) == 13 and sum(run.count(line) for line in set(taken)) == 12


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
    "a secret": lambda t: t.replace(f"run: {WORKFLOW_INSTALL}\n",
                                    f"run: {WORKFLOW_INSTALL}\n"
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
    # v1.443: the registry-pair file and its evaluate line
    "the compare step without the registry pair": lambda t: t.replace(
        " evidence/ledger-handoff/results.json evidence/registry-pair/results.json ",
        " evidence/ledger-handoff/results.json ", 1),
    "a registry-pair line dropped": lambda t: with_lines(
        t, lambda ls: [line for line in ls if line.strip() != REGISTRY_LINES[1]]),
    # v1.472: the registry-pair delegation file, last in command order, and its script line
    "the compare step without the registry-pair delegation": lambda t: t.replace(
        " evidence/registry-pair/results.json evidence/registry-pair-delegation/results.json ",
        " evidence/registry-pair/results.json ", 1),
    "a registry-pair delegation line dropped": lambda t: with_lines(
        t, lambda ls: [line for line in ls if line.strip() != REGISTRY_DELEGATION_RUN[0]]),
    # v1.489: the Longtail-SWE file, last in command order, its converter line and the `pyarrow` install
    "the compare step without the Longtail-SWE file": lambda t: t.replace(
        " evidence/registry-pair-delegation/results.json evidence/longtail-swe/results.json ",
        " evidence/registry-pair-delegation/results.json ", 1),
    "a Longtail-SWE line dropped": lambda t: with_lines(
        t, lambda ls: [line for line in ls if line.strip() != LONGTAIL_LINES[0]]),
    "the install line without pyarrow": lambda t: t.replace(f"run: {WORKFLOW_INSTALL}\n", f"run: {INSTALL}\n", 1),
    # v1.525: the last AutoBench slice file, last in command order, and the slices converter line
    "the compare step without a slice file": lambda t: t.replace(
        " evidence/autobench-2026/slices-skill.json evidence/autobench-2026/slices-difficulty-min10.json "
        "evidence/autobench-2026/slices-skill-min10.json ",
        " evidence/autobench-2026/slices-skill.json evidence/autobench-2026/slices-difficulty-min10.json ", 1),
    "the slices converter line dropped": lambda t: with_lines(
        t, lambda ls: [line for line in ls if line.strip() != SLICES_LINES[0]]),
    # v1.530: the LiveCodeBench slice file, last in command order, and its converter line
    "the compare step without the LiveCodeBench slice file": lambda t: t.replace(
        " evidence/autobench-2026/slices-skill-min10.json evidence/livecodebench/slices-difficulty.json ",
        " evidence/autobench-2026/slices-skill-min10.json ", 1),
    "the LiveCodeBench slices converter line dropped": lambda t: with_lines(
        t, lambda ls: [line for line in ls if line.strip() != LCB_SLICES_LINES[0]]),
    # v1.544: the cascades file, last in command order, and the replay line
    "the compare step without the cascades file": lambda t: t.replace(
        " evidence/livecodebench/slices-difficulty.json evidence/tau2-bench/cascades.json ",
        " evidence/livecodebench/slices-difficulty.json ", 1),
    "the cascade replay line dropped": lambda t: with_lines(
        t, lambda ls: [line for line in ls if line.strip() != CASCADE_LINES[0]]),
    # v1.559: the LiveCodeBench cascades file, last in command order, and its replay line
    "the compare step without the LiveCodeBench cascades file": lambda t: t.replace(
        " evidence/tau2-bench/cascades.json evidence/livecodebench/cascades.json\n",
        " evidence/tau2-bench/cascades.json\n", 1),
    "the LiveCodeBench cascade replay line dropped": lambda t: with_lines(
        t, lambda ls: [line for line in ls if line.strip() != LCB_CASCADE_LINES[0]]),
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
    assert len(MUTANTS) == 49  # v1.489: the Longtail-SWE Compare file, its converter line and the pyarrow pin;
    # v1.525: a slice file in Compare and the slices converter line; v1.530: the LiveCodeBench ones; v1.544: the
    # cascades file and the replay line; v1.559: the LiveCodeBench ones
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
                                  "the compare step without the registry-pair delegation",  # v1.472, row E25c
                                  "the compare step without the Longtail-SWE file",  # v1.489, row E26d
                                  "the compare step without a slice file",  # v1.525, row STRAT3g
                                  "the compare step without the LiveCodeBench slice file",  # v1.530, row STRAT3i
                                  "the compare step without the cascades file",  # v1.544, row ESC3e
                                  "the compare step without the LiveCodeBench cascades file",  # v1.559, row ESC3i
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
                            "evidence/registry-pair/results.json "
                            "evidence/registry-pair-delegation/results.json evidence/longtail-swe/results.json"
                            + TAIL_COMPARE)


def test_the_workflow_reruns_the_ledger_handoff_line_after_the_readme_commands():
    # v1.397 (row E23c, DESIGN 13.15 Workflow bullet); from v1.443 the registry-pair block follows it
    assert ledger_command() == LEDGER_LINE
    text = workflow_text()
    run = before_slices([line.strip() for line in regenerate_lines(text)[1]])  # v1.525, v1.530
    assert run[-12] == LEDGER_LINE and run[-14:-12] == RB_TABLES and run.count(LEDGER_LINE) == 1
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert compare.endswith(" evidence/response-bank-delegation/results.json evidence/ledger-handoff/results.json "
                            "evidence/registry-pair/results.json evidence/registry-pair-delegation/results.json "
                            "evidence/longtail-swe/results.json" + TAIL_COMPARE)
    assert (ROOT / "evidence" / "ledger-handoff" / "results.json").is_file()
    ci_text = CI.read_text(encoding="utf-8")
    assert problems(MUTANTS["the ledger line dropped"](text), readme(), ci_text) == [
        "Regenerate is not the README commands in order"]
    design = DESIGN.read_text(encoding="utf-8")
    section = design.split("\n### 12.13 ", 1)[1].split("\n### ", 1)[0]
    assert f"each of {len(MUTANTS)} broken workflows fails the check, the fourteen `Compare` mutants" in section
    assert "then (v1.397) the regenerate line of `evidence/ledger-handoff/RESULTS.md` (13.15)" in section
    assert ("twenty-three files from `evidence/autobench-2026/results.json` to "
            "`evidence/livecodebench/cascades.json`") in section  # v1.544, v1.559
    # v1.401 (row CI21): the basis is the slowest run on main, whatever its lines; v1.407 (row CI22),
    # by its latest attempt.
    assert (f"all on `main` and all successful by their latest attempt, the slowest is run {SLOWEST_RUN_ID} on "
            f"`{SLOWEST_RUN_SHA}`, "
            in section)
    spec = design.split("\n### 13.15 ", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
    bullets = [line for line in spec.split("\n") if line.startswith("- Workflow (v1.397, row E23c): ")]
    assert len(bullets) == 1 and f"`{LEDGER_LINE}`" in bullets[0]
    # Review iter-304 must-fix 1 (v1.443): the ledger file is no longer last in Compare.
    assert ("`Compare` names `evidence/ledger-handoff/results.json` after the files of the README commands, "
            "and from v1.443 the registry-pair file after it (12.13, row E24e);") in bullets[0]
    assert "`evidence/ledger-handoff/results.json` last" not in design
    # Review iter-257 must-fix 1: the sentence states the rule in force, in the present tense (v1.401).
    assert ("The line keeps the time limit and its basis, the slowest successful run of the workflow on `main` "
            "whatever its lines (12.13, v1.401)") in bullets[0]
    # Review iter-267 nit (v1.442, row CI24): the sentence also names the v1.407 rerun rule.
    assert bullets[0].endswith("whatever its lines (12.13, v1.401), a run that was rerun counting by its latest "
                               "attempt from that attempt's start (12.13, v1.407)")


def test_the_workflow_reruns_the_registry_pair_block_after_the_ledger_line():
    # v1.443 (row E24e, DESIGN 12.13 Registry pair bullet): the four lines of the RESULTS.md block, after
    # the ledger line; from v1.472 the registry-pair delegation block follows them.
    assert registry_commands() == REGISTRY_LINES
    text = workflow_text()
    run = before_slices([line.strip() for line in regenerate_lines(text)[1]])  # v1.525, v1.530
    assert run[-11:-7] == REGISTRY_LINES and run[-12] == LEDGER_LINE
    assert all(run.count(line) == 1 for line in REGISTRY_LINES)
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert (" evidence/ledger-handoff/results.json evidence/registry-pair/results.json "
            "evidence/registry-pair-delegation/results.json") in compare
    assert (ROOT / "evidence" / "registry-pair" / "results.json").is_file()
    assert out_paths(readme_commands(readme()))[-1] == "evidence/registry-pair/results.json"
    # v1.452 (row E24c): the README intro counts it, and the README block is the RESULTS.md one.
    assert len(out_paths(readme_commands(readme()))) == 14
    block = re.findall(r"```bash\n(.*?)```", subsection(readme(), "Registry pair"), re.S)
    assert block == ["\n".join([INSTALL] + REGISTRY_LINES) + "\n"]
    ci_text = CI.read_text(encoding="utf-8")
    assert problems(MUTANTS["a registry-pair line dropped"](text), readme(), ci_text) == [
        "Regenerate is not the README commands in order"]
    section = DESIGN.read_text(encoding="utf-8").split("\n### 12.13 ", 1)[1].split("\n### ", 1)[0]
    bullets = [line for line in section.split("\n") if line.startswith("- Registry pair is rerun (v1.443, row E24e): ")]
    assert len(bullets) == 1
    assert ("and (v1.443) the four lines of the `## Regenerate` block of `evidence/registry-pair/RESULTS.md` "
            "without its install line (12.24)") in section


def test_the_workflow_reruns_the_registry_pair_delegation_block_after_the_registry_pair_lines():
    # v1.472 (row E25c, DESIGN 13.17 Workflow bullet): the three lines of its RESULTS.md block the v1.215
    # rule keeps, after the registry-pair lines, and its results file after theirs in Compare (last until
    # v1.489, when the Longtail-SWE block follows it); the README sentence counts that file only once row
    # E25e gives the block a subsection.
    assert registry_delegation_commands() == REGISTRY_DELEGATION_LINES
    assert REGISTRY_DELEGATION_LINES[0] == REGISTRY_LINES[0]  # the 12.23 converter line, left out
    text = workflow_text()
    run = before_slices([line.strip() for line in regenerate_lines(text)[1]])  # v1.525, v1.530
    assert run[-7:-4] == REGISTRY_DELEGATION_RUN and run[-8] == REGISTRY_LINES[-1]
    assert all(run.count(line) == 1 for line in REGISTRY_DELEGATION_RUN)
    assert run.count(REGISTRY_LINES[0]) == 1
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert compare.endswith(" evidence/registry-pair/results.json "
                            "evidence/registry-pair-delegation/results.json evidence/longtail-swe/results.json"
                            + TAIL_COMPARE)
    assert (ROOT / "evidence" / "registry-pair-delegation" / "results.json").is_file()
    at = -5 - len(SLICE_FILES)  # v1.525, v1.530, v1.544, v1.559: the four AutoBench slice files, the LiveCodeBench
    # one and the two cascades ones follow it
    assert out_paths(regenerate_commands(readme()))[at] == "evidence/registry-pair-delegation/results.json"
    assert "evidence/registry-pair-delegation/results.json" not in out_paths(readme_commands(readme()))
    ci_text = CI.read_text(encoding="utf-8")
    assert problems(MUTANTS["a registry-pair delegation line dropped"](text), readme(), ci_text) == [
        "Regenerate is not the README commands in order"]
    design = DESIGN.read_text(encoding="utf-8")
    section = design.split("\n### 12.13 ", 1)[1].split("\n### ", 1)[0]
    bullets = [line for line in section.split("\n")
               if line.startswith("- Registry-pair delegation is rerun (v1.472, row E25c): ")]
    assert len(bullets) == 1 and "about 3 seconds" in bullets[0] and "row E25e" in bullets[0]
    spec = design.split("\n### 13.17 ", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
    workflow_bullets = [line for line in spec.split("\n") if line.startswith("- Workflow (v1.472, row E25c): ")]
    assert len(workflow_bullets) == 1
    # v1.489 (row E26d): the file is no longer last in Compare, the Longtail-SWE file after it.
    assert ("`Compare` names `evidence/registry-pair-delegation/results.json` after the registry-pair file, and "
            "from v1.489 the Longtail-SWE file after it (12.13, row E26d).") in workflow_bullets[0]
    assert "`evidence/registry-pair-delegation/results.json` last" not in design
    assert "row E25e" in workflow_bullets[0] and "unchanged" in workflow_bullets[0]
    # The RESULTS.md download line says the workflow reruns the block (12.13, 13.17).
    notes = (ROOT / REGISTRY_DELEGATION_NOTES).read_text(encoding="utf-8")
    before = notes.split("\n## Regenerate\n", 1)[1].split("```bash", 1)[0]
    assert ("The `evidence` workflow reruns these commands on GitHub and fails if `results.json` changes "
            "by a byte (`DESIGN.md` 12.13, v1.472).") in before


def test_the_workflow_installs_pyarrow_and_reruns_the_longtail_swe_block_before_the_slices():
    # v1.489 (row E26d, DESIGN 12.13 Longtail-SWE bullet): the four lines of its RESULTS.md block after the
    # registry-pair delegation lines, its results file last in Compare until v1.525, and the `pyarrow` pin of the
    # `evidence` extra in the `Install` line, without the extra's pandas, which RouterBench's reason names;
    # the README sentence counts the file only once row E26e gives the block a subsection.
    assert longtail_commands() == LONGTAIL_LINES
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert pyarrow_pin() == "pyarrow>=14" and '"pyarrow>=14"' in pyproject.split("evidence = [", 1)[1].split("]", 1)[0]
    assert WORKFLOW_INSTALL == 'python -m pip install -e . "pyarrow>=14"' and "pandas" not in WORKFLOW_INSTALL
    text = workflow_text()
    assert text.count(f"        run: {WORKFLOW_INSTALL}\n") == 1 and "pandas" not in text.split("\non:\n", 1)[1]
    run = before_slices([line.strip() for line in regenerate_lines(text)[1]])  # v1.525, v1.530
    assert run[-4:] == LONGTAIL_LINES and run[-5] == REGISTRY_DELEGATION_RUN[-1]
    assert all(run.count(line) == 1 for line in LONGTAIL_LINES)
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert compare.endswith(" evidence/registry-pair-delegation/results.json evidence/longtail-swe/results.json"
                            + TAIL_COMPARE)
    assert compare.count(" evidence/") == 16 + len(SLICE_FILES) + 3  # v1.559: the LiveCodeBench cascades file
    assert (ROOT / "evidence" / "longtail-swe" / "results.json").is_file()
    assert out_paths(regenerate_commands(readme()))[-4 - len(SLICE_FILES)] == "evidence/longtail-swe/results.json"
    assert "evidence/longtail-swe/results.json" not in out_paths(readme_commands(readme()))
    assert len(out_paths(readme_commands(readme()))) == 14
    ci_text = CI.read_text(encoding="utf-8")
    assert problems(MUTANTS["a Longtail-SWE line dropped"](text), readme(), ci_text) == [
        "Regenerate is not the README commands in order"]
    assert problems(MUTANTS["the install line without pyarrow"](text), readme(), ci_text) == ["install line differs"]
    design = DESIGN.read_text(encoding="utf-8")
    section = design.split("\n### 12.13 ", 1)[1].split("\n### ", 1)[0]
    bullets = [line for line in section.split("\n") if line.startswith("- Longtail-SWE is rerun (v1.489, row E26d): ")]
    assert len(bullets) == 1 and "236,605,401 bytes (the 12.25 `FILES`)" in bullets[0] and "row E26e" in bullets[0]
    assert f"`Install` (`{WORKFLOW_INSTALL}`, " in section
    assert ("then (v1.489) that block of `evidence/longtail-swe/RESULTS.md` (12.26) without its install line, "
            "then (v1.525)" in section)  # v1.525: the slices block follows it
    # The RESULTS.md download line says the workflow reruns the block (12.13, 12.26).
    notes = (ROOT / LONGTAIL_NOTES).read_text(encoding="utf-8")
    before = notes.split("\n## Regenerate\n", 1)[1]
    assert ("The `evidence` workflow reruns these commands on GitHub and fails if `results.json` changes "
            "by a byte (`DESIGN.md` 12.13, v1.489)") in before
    assert "does not rerun" not in notes


def test_the_workflow_reruns_the_autobench_slices_block_before_the_livecodebench_one():
    # v1.525 (row STRAT3g, DESIGN 12.13 slices bullet, 12.27 Workflow bullet): the nine lines of the
    # `## Slices` block after the Longtail-SWE lines, none a repeat, and its four files after the Longtail-SWE one
    # in Compare, last until v1.530; the README sentence does not count them: the README part on slices links them.
    assert slices_commands() == SLICES_LINES
    assert out_paths(SLICES_LINES) == SLICE_FILES
    text = workflow_text()
    run = [line.strip() for line in regenerate_lines(text)[1]]
    lcb = len(LCB_SLICES_LINES) + len(CASCADE_LINES) + len(LCB_CASCADE_LINES)  # v1.544, v1.559: the cascade lines
    # follow the LiveCodeBench ones
    assert run[-9 - lcb:-lcb] == SLICES_LINES and run[-10 - lcb] == LONGTAIL_LINES[-1]
    assert all(run.count(line) == 1 for line in SLICES_LINES)
    assert regenerate_commands(readme())[-9 - lcb:-lcb] == SLICES_LINES
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert compare.endswith(" evidence/longtail-swe/results.json" + TAIL_COMPARE)
    assert compare.count(" evidence/") == 23
    assert all((ROOT / path).is_file() for path in SLICE_FILES)
    assert out_paths(regenerate_commands(readme()))[-7:-3] == SLICE_FILES
    assert not set(SLICE_FILES) & set(out_paths(readme_commands(readme())))
    assert len(out_paths(readme_commands(readme()))) == 14
    ci_text = CI.read_text(encoding="utf-8")
    assert problems(MUTANTS["the slices converter line dropped"](text), readme(), ci_text) == [
        "Regenerate is not the README commands in order"]
    assert problems(MUTANTS["the compare step without a slice file"](text), readme(), ci_text) == [
        "Compare is not the diff of the committed results"]
    design = DESIGN.read_text(encoding="utf-8")
    section = design.split("\n### 12.13 ", 1)[1].split("\n### ", 1)[0]
    bullets = [line for line in section.split("\n")
               if line.startswith("- Slices are rerun (AutoBench v1.525, row STRAT3g; LiveCodeBench v1.530, row STRAT3i): ")]
    assert len(bullets) == 1 and "nine lines of the 12.27 block, then the three of the 12.28 block, none a repeat" \
        in bullets[0]  # v1.544: no longer last
    assert "row STRAT4" in bullets[0] and "does not count their five files" in bullets[0]
    assert ("then (v1.525) the one `bash` block of `## Slices` of `evidence/autobench-2026/RESULTS.md` (12.27), "
            "which has none, then (v1.530) that of `evidence/livecodebench/RESULTS.md` (12.28), then (v1.544)") in section
    spec = design.split("\n### 12.27 ", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]  # 12.28 follows (v1.528)
    workflow_bullets = [line for line in spec.split("\n") if line.startswith("- Workflow (v1.525, row STRAT3g): ")]
    assert len(workflow_bullets) == 1 and "block last" not in workflow_bullets[0]  # v1.530: no longer last
    assert "12.13 workflow lines" not in spec
    # The RESULTS.md line before the block says the workflow reruns it (12.13, 12.27).
    notes = (ROOT / SLICES_NOTES).read_text(encoding="utf-8")
    before = notes.split("\n## Slices\n", 1)[1].split("```bash", 1)[0].rstrip("\n").split("\n")[-1]
    assert ("the `evidence` workflow reruns them on GitHub and fails if one of the four files changes by a byte "
            "(`DESIGN.md` 12.13, v1.525):") in before


def test_the_workflow_reruns_the_livecodebench_slices_block_before_the_cascades_one():
    # v1.530 (row STRAT3i, DESIGN 12.13 slices bullet, 12.28 Workflow bullet): the three lines of the LiveCodeBench
    # `## Slices` block after the AutoBench slices lines, none a repeat (its converter line is not the v1.65 one),
    # and its file after the AutoBench ones in Compare, last until v1.544; the README sentence does not count it:
    # the README part on slices links it.
    assert slices_commands(LCB_SLICES_NOTES) == LCB_SLICES_LINES
    assert out_paths(LCB_SLICES_LINES) == [LCB_SLICE_FILE]
    text = workflow_text()
    run = [line.strip() for line in regenerate_lines(text)[1]]
    tail = len(CASCADE_LINES) + len(LCB_CASCADE_LINES)  # v1.544, v1.559: the cascade lines follow it
    assert run[-3 - tail:-tail] == LCB_SLICES_LINES and run[-4 - tail] == SLICES_LINES[-1]
    assert all(run.count(line) == 1 for line in LCB_SLICES_LINES)
    assert run.count("python evidence/livecodebench/convert.py --out livecodebench-matrix.jsonl") == 1
    assert regenerate_commands(readme())[-3 - tail:-tail] == LCB_SLICES_LINES
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert compare.endswith(SLICES_COMPARE + f" {LCB_SLICE_FILE} {CASCADE_FILE} {LCB_CASCADE_FILE}")
    assert compare.count(" evidence/") == 23
    assert (ROOT / LCB_SLICE_FILE).is_file()
    assert out_paths(regenerate_commands(readme()))[-3] == LCB_SLICE_FILE
    assert LCB_SLICE_FILE not in out_paths(readme_commands(readme()))
    ci_text = CI.read_text(encoding="utf-8")
    assert problems(MUTANTS["the LiveCodeBench slices converter line dropped"](text), readme(), ci_text) == [
        "Regenerate is not the README commands in order"]
    assert problems(MUTANTS["the compare step without the LiveCodeBench slice file"](text), readme(), ci_text) == [
        "Compare is not the diff of the committed results"]
    design = DESIGN.read_text(encoding="utf-8")
    spec = design.split("\n### 12.28 ", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
    workflow_bullets = [line for line in spec.split("\n") if line.startswith("- Workflow (v1.530, row STRAT3i): ")]
    assert len(workflow_bullets) == 1 and "block last" not in workflow_bullets[0]  # v1.544: no longer last
    assert "12.13 workflow lines" not in spec and "(row STRAT3i) and" not in spec
    # The RESULTS.md line before the block says the workflow reruns it (12.13, 12.28).
    notes = (ROOT / LCB_SLICES_NOTES).read_text(encoding="utf-8")
    before = notes.split("\n## Slices\n", 1)[1].split("```bash", 1)[0].rstrip("\n").split("\n")[-1]
    assert ("the `evidence` workflow reruns them on GitHub and fails if the file changes by a byte "
            "(`DESIGN.md` 12.13, v1.530):") in before


def test_the_workflow_reruns_the_tau2_cascades_block_before_the_livecodebench_one():
    # v1.544 (row ESC3e, DESIGN 12.13 cascades bullet, 12.29 Workflow bullet): the three lines of the tau2-bench
    # `## Cascades` block after the LiveCodeBench slices lines, none a repeat, and its file in Compare after theirs,
    # last until v1.559; the
    # README sentence does not count it: the README part on cascades holds no block.
    assert cascade_commands() == CASCADE_LINES
    assert out_paths(CASCADE_LINES) == [CASCADE_FILE]
    text = workflow_text()
    run = [line.strip() for line in regenerate_lines(text)[1]]
    tail = len(LCB_CASCADE_LINES)  # v1.559: the LiveCodeBench cascade lines follow it
    assert run[-3 - tail:-tail] == CASCADE_LINES and run[-4 - tail] == LCB_SLICES_LINES[-1]
    assert all(run.count(line) == 1 for line in CASCADE_LINES)
    assert run.count("python evidence/tau2-bench/convert.py --out tau2-matrix.jsonl") == 1
    assert regenerate_commands(readme())[-3 - tail:-tail] == CASCADE_LINES
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert compare.endswith(TAIL_COMPARE) and compare.endswith(f" {CASCADE_FILE} {LCB_CASCADE_FILE}")
    assert compare.count(" evidence/") == 23
    assert (ROOT / CASCADE_FILE).is_file()
    assert out_paths(regenerate_commands(readme()))[-2] == CASCADE_FILE
    assert CASCADE_FILE not in out_paths(readme_commands(readme()))
    assert "```bash" not in subsection_of(readme(), "## Start cheap, escalate on a signal")
    ci_text = CI.read_text(encoding="utf-8")
    assert problems(MUTANTS["the cascade replay line dropped"](text), readme(), ci_text) == [
        "Regenerate is not the README commands in order"]
    assert problems(MUTANTS["the compare step without the cascades file"](text), readme(), ci_text) == [
        "Compare is not the diff of the committed results"]
    # The top comment names the section, on lines under 100 columns (the RouterBench bullet of 12.13).
    assert ("and the Cascades sections of evidence/tau2-bench/RESULTS.md and evidence/livecodebench/RESULTS.md, "
            "which") in " ".join(
        line[2:] for line in text.split("\non:\n", 1)[0].split("\n") if line.startswith("# "))
    design = DESIGN.read_text(encoding="utf-8")
    section = design.split("\n### 12.13 ", 1)[1].split("\n### ", 1)[0]
    bullets = [line for line in section.split("\n") if line.startswith("- tau2-bench cascades are rerun (v1.544, row ESC3e): ")]
    assert len(bullets) == 1 and "runs the three lines of the 12.29 block after the slices lines, none a repeat" \
        in bullets[0]  # v1.559: no longer last
    # the replay reads the run files the 12.14 converter line downloaded and downloads the three tools.py files
    import importlib.util
    spec_ = importlib.util.spec_from_file_location("wf_escalation_signals", ROOT / "research" / "escalation_signals.py")
    signals = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(signals)
    size = sum(entry[0] for entry in signals.TOOL_FILES.values())
    assert len(signals.TOOL_FILES) == 3 and f"at the 12.14 revision, {size:,} bytes. " in bullets[0]
    # v1.545 (row ESC3h): fetch_tools retries as the converters do (the time-limit bullet and
    # tests/test_evidence_download_retries.py), so the bullet no longer says one attempt each
    assert "one attempt" not in bullets[0] and "rerunning the job" not in bullets[0] and signals.ATTEMPTS == 3
    assert "does not count its file" in bullets[0] and "(7 v1.543)" in bullets[0]
    assert ("then (v1.530) that of `evidence/livecodebench/RESULTS.md` (12.28), then (v1.544) that of `## Cascades` "
            "of `evidence/tau2-bench/RESULTS.md` (12.29), then (v1.559)") in section
    spec = design.split("\n### 12.29 ", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
    workflow_bullets = [line for line in spec.split("\n") if line.startswith("- Workflow (v1.544, row ESC3e): ")]
    assert len(workflow_bullets) == 1 and "block last" not in workflow_bullets[0]  # v1.559: no longer last
    assert "12.13 workflow lines" not in spec and "(row ESC3e);" not in spec
    # The RESULTS.md line before the block says the workflow reruns it (12.13, 12.29).
    notes = (ROOT / CASCADE_NOTES).read_text(encoding="utf-8")
    before = notes.split("\n## Cascades\n", 1)[1].split("```bash", 1)[0].rstrip("\n").split("\n")[-1]
    assert before.endswith("the `evidence` workflow reruns them on GitHub and fails if the file changes by a byte "
                           "(`DESIGN.md` 12.13, v1.544):")


def test_the_workflow_reruns_the_livecodebench_cascades_block_last():
    # v1.559 (row ESC3i, DESIGN 12.13 LiveCodeBench cascades bullet, 12.30 Workflow bullet): the three lines of the
    # LiveCodeBench `## Cascades` block after the tau2-bench cascade lines, none a repeat, and its file last in
    # Compare; the README sentence does not count it: the README part on cascades holds no block.
    assert lcb_cascade_commands() == LCB_CASCADE_LINES
    assert out_paths(LCB_CASCADE_LINES) == [LCB_CASCADE_FILE]
    text = workflow_text()
    run = [line.strip() for line in regenerate_lines(text)[1]]
    assert run[-3:] == LCB_CASCADE_LINES and run[-4] == CASCADE_LINES[-1]
    assert all(run.count(line) == 1 for line in LCB_CASCADE_LINES)
    assert run.count("python evidence/livecodebench/convert.py --out livecodebench-matrix.jsonl") == 1
    assert regenerate_commands(readme())[-3:] == LCB_CASCADE_LINES
    compare = text.split("      - name: Compare\n", 1)[1].split("\n", 1)[0]
    assert compare.endswith(TAIL_COMPARE) and compare.endswith(f" {LCB_CASCADE_FILE}") and compare.count(" evidence/") == 23
    assert (ROOT / LCB_CASCADE_FILE).is_file()
    assert out_paths(regenerate_commands(readme()))[-1] == LCB_CASCADE_FILE
    assert LCB_CASCADE_FILE not in out_paths(readme_commands(readme()))
    assert len(out_paths(readme_commands(readme()))) == 14
    ci_text = CI.read_text(encoding="utf-8")
    assert problems(MUTANTS["the LiveCodeBench cascade replay line dropped"](text), readme(), ci_text) == [
        "Regenerate is not the README commands in order"]
    assert problems(MUTANTS["the compare step without the LiveCodeBench cascades file"](text), readme(), ci_text) == [
        "Compare is not the diff of the committed results"]
    design = DESIGN.read_text(encoding="utf-8")
    section = design.split("\n### 12.13 ", 1)[1].split("\n### ", 1)[0]
    bullets = [line for line in section.split("\n")
               if line.startswith("- LiveCodeBench cascades are rerun (v1.559, row ESC3i): ")]
    assert len(bullets) == 1 and "runs the three lines of the 12.30 block last, none a repeat" in bullets[0]
    # the replay reads the kept files the 12.16 converter line downloaded and downloads the four release files,
    # each tried up to three times by the retry rule from v1.560 (row ESC3t)
    import importlib.util
    spec_ = importlib.util.spec_from_file_location("wf_public_tests", ROOT / "research" / "escalation_public_tests.py")
    public_tests = importlib.util.module_from_spec(spec_)
    spec_.loader.exec_module(public_tests)
    names = ("test.jsonl", "test2.jsonl", "test3.jsonl", "test4.jsonl")  # the replay's RELEASE, of the six pinned
    lcb = (ROOT / "evidence" / "livecodebench" / "cascades.py").read_text(encoding="utf-8")
    assert f"\nRELEASE = {names!r}\n".replace("'", '"') in lcb
    size = sum(public_tests.RELEASE_FILES[name][0] for name in names)
    assert size == 3_793_992_284
    assert f"downloads the four `release_v4` files of the problem release (7 v1.551), {size:,} bytes, " in bullets[0]
    assert public_tests.ATTEMPTS == 3
    assert ("`fetch_release` tries each missing file up to three times by the retry rule above (v1.560, "
            "row ESC3t). ") in bullets[0]
    # the seconds against the limit: the release bytes at the LLMRouterBench line's rate in the stated run
    assert "run 44903881279 took 256 seconds" in bullets[0] and "the 1,283,503,080-byte 12.18 file" in bullets[0]
    assert round(size / (1_283_503_080 / 42.3)) == 125 and "the release files add about 125 seconds" in bullets[0]
    limit = int(re.search(r"^    timeout-minutes: (\d+)$", text, re.M).group(1))  # 105: 630 restates it (v1.225)
    # review iter-404 should-fix 1: the whole run, not the added seconds, is what the 630 s threshold reads
    added = 125 + 15
    assert round(256 + added, -2) == 400 and "a run of about 400 seconds, " in bullets[0]
    assert f"under the {limit * 6} that restate the limit and far under its {limit * 60:,}, " in bullets[0]
    assert SLOWEST_RUN_SECONDS + added > limit * 6 and (
        f"while one as slow as the {SLOWEST_RUN_SECONDS}-second basis would pass {limit * 6} and restate it "
        "by the rule; ") in bullets[0]
    nocache = [line for line in section.split("\n") if line.startswith("- No cache between runs (v1.251, row CI9): ")]
    total = re.search(r"(\d[\d,]+) bytes in all", nocache[0]).group(1)
    # review iter-404 nit 1: the total is the v1.544 one plus the release files
    assert f"the job then downloads {total} bytes" in bullets[0] and total == f"{4_089_025_877 + size:,}"
    assert "does not count its file" in bullets[0] and "(7 v1.543)" in bullets[0]
    assert ("then (v1.544) that of `## Cascades` of `evidence/tau2-bench/RESULTS.md` (12.29), then (v1.559) that of "
            "`evidence/livecodebench/RESULTS.md` (12.30);") in section
    spec = design.split("\n### 12.30 ", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]
    workflow_bullets = [line for line in spec.split("\n") if line.startswith("- Workflow (v1.559, row ESC3i): ")]
    assert len(workflow_bullets) == 1 and "block last" in workflow_bullets[0]
    assert "12.13 workflow lines" not in spec
    # The RESULTS.md line before the block says the workflow reruns it (12.13, 12.30).
    notes = (ROOT / LCB_CASCADE_NOTES).read_text(encoding="utf-8")
    before = notes.split("\n## Cascades\n", 1)[1].split("```bash", 1)[0].rstrip("\n").split("\n")[-1]
    assert before.endswith("the `evidence` workflow reruns them on GitHub and fails if the file changes by a byte "
                           "(`DESIGN.md` 12.13, v1.559):")

# v1.547 (row CI28, the 12.13 first bullet): `paths` names `evidence/**`, `model_routing/**`, then each file
# outside those two that the job's code loads by path, at any depth, then `pyproject.toml` and the workflow.
# The job's code is each script a `Regenerate` line runs with `python` and the package (`model-routing`).
INSIDE = ("evidence/", "model_routing/")
# v1.559 (row ESC3i): the LiveCodeBench cascade replay loads two more
LOADED_OUTSIDE = ["research/escalation_public_tests.py", "research/escalation_signals.py", "research/livecodebench_cost.py"]
PATHS = ["evidence/**", "model_routing/**", *LOADED_OUTSIDE, "pyproject.toml", ".github/workflows/evidence.yml"]
# review iter-393 should-fix 2b: the loader styles that take no `spec_from_file_location`
DYNAMIC = {"run_path", "import_module", "__import__", "exec", "eval", "SourceFileLoader", "spec_from_loader",
           "load_module", "load_source"}
PATH_CALLS = {"join", "joinpath", "with_name", "Path", "spec_from_file_location"}


def path_of(node, names, here):
    """The path an expression builds from `__file__` with `Path(...)`, `.resolve()`, `.parent`, `.parents[k]`,
    `.with_name("x")`, `/ "x"` and names bound to such paths; None for any other expression."""
    if isinstance(node, ast.Name):
        return here if node.id == "__file__" else names.get(node.id)
    if isinstance(node, ast.Call) and not node.keywords:
        func = node.func
        if isinstance(func, ast.Name) and func.id == "Path" and len(node.args) == 1:
            return path_of(node.args[0], names, here)
        if isinstance(func, ast.Attribute) and func.attr == "resolve" and not node.args:
            return path_of(func.value, names, here)
        if (isinstance(func, ast.Attribute) and func.attr == "with_name" and len(node.args) == 1
                and isinstance(node.args[0], ast.Constant) and isinstance(node.args[0].value, str)):
            base = path_of(func.value, names, here)
            return base.with_name(node.args[0].value) if base else None
    if isinstance(node, ast.Attribute) and node.attr == "parent":
        base = path_of(node.value, names, here)
        return base.parent if base else None
    if (isinstance(node, ast.Subscript) and isinstance(node.value, ast.Attribute) and node.value.attr == "parents"
            and isinstance(node.slice, ast.Constant) and isinstance(node.slice.value, int)):
        base = path_of(node.value.value, names, here)
        return base.parents[node.slice.value] if base else None
    if (isinstance(node, ast.BinOp) and isinstance(node.op, ast.Div) and isinstance(node.right, ast.Constant)
            and isinstance(node.right.value, str)):
        base = path_of(node.left, names, here)
        return base / node.right.value if base else None
    return None


def _name(func):
    return func.id if isinstance(func, ast.Name) else func.attr if isinstance(func, ast.Attribute) else None


def built_paths(source, here):
    """(files, unresolved) for the module `source` at repo path `here`: the repo files other than itself it
    builds a path to, and, failing closed, each load the read cannot follow: a `.py` string it cannot resolve
    used as a path part (a `/` operand or an argument of a PATH_CALLS call; a downloaded file's name, as
    research/escalation_signals.py builds for each `tools.py` it parses, is neither), a `spec_from_file_location`
    whose path is neither resolved nor the parameter of the helper it sits in, a call of such a helper whose
    path is not resolved (called by name, or through an attribute of anything but an imported name), a DYNAMIC
    call, a `sys.path` entry other than the repo root, or an `import` of a top-level repo folder other than the
    package. A name resolves only when the file binds it once, and a path is normalized before it is placed
    (review iter-393 should-fix 1 and 2, nits 2 and 3)."""
    tree = ast.parse(source)
    bound = {}
    for node in ast.walk(tree):
        if isinstance(node, ast.Name) and isinstance(node.ctx, ast.Store):
            bound[node.id] = bound.get(node.id, 0) + 1
        if isinstance(node, ast.arg):
            bound[node.arg] = bound.get(node.arg, 0) + 1
    names = {}
    for _ in range(3):  # a name bound from a name bound later in the file resolves on a later pass
        for node in ast.walk(tree):
            if (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.targets[0], ast.Name)
                    and bound[node.targets[0].id] == 1):
                value = path_of(node.value, names, here)
                if value is not None:
                    names[node.targets[0].id] = value
    files, unresolved, used = set(), [], set()
    for node in ast.walk(tree):
        value = path_of(node, names, here)
        if value is not None:
            used.update(id(n) for n in ast.walk(node))
            value = Path(os.path.normpath(value))
            if value != here and ROOT in value.parents and value.is_file():
                files.add(value.relative_to(ROOT).as_posix())
    parents = {id(child): node for node in ast.walk(tree) for child in ast.iter_child_nodes(node)}
    folders = {p.name for p in ROOT.iterdir() if p.is_dir() and p.name != "model_routing"}
    imported = {(a.asname or a.name).split(".")[0] for n in ast.walk(tree)
                if isinstance(n, (ast.Import, ast.ImportFrom)) for a in n.names}
    helpers, inside = {}, set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            params = [a.arg for a in fn.args.args]
            for call in ast.walk(fn):
                if isinstance(call, ast.Call) and _name(call.func) == "spec_from_file_location":
                    arg = call.args[1] if len(call.args) > 1 else None
                    if isinstance(arg, ast.Name) and arg.id in params:
                        helpers[fn.name] = (params.index(arg.id), arg.id)
                        inside.add(id(call))
    for node in ast.walk(tree):
        if isinstance(node, ast.Constant) and isinstance(node.value, str) and node.value.endswith(".py"):
            parent = parents.get(id(node))
            part = (isinstance(parent, ast.BinOp) and isinstance(parent.op, ast.Div)) or (
                isinstance(parent, ast.Call) and node in parent.args and _name(parent.func) in PATH_CALLS)
            if part and id(node) not in used:
                unresolved.append(f"a .py string it cannot resolve: {node.value!r}")
        if isinstance(node, ast.Call):
            name = _name(node.func)
            if name in DYNAMIC:
                unresolved.append(f"a {name} call")
            if name == "spec_from_file_location":
                arg = node.args[1] if len(node.args) > 1 else None
                if path_of(arg, names, here) is None and id(node) not in inside:
                    unresolved.append(f"a load it cannot resolve: {ast.unparse(node)}")
            via = node.func.value if isinstance(node.func, ast.Attribute) else None
            if name in helpers and not (isinstance(via, ast.Name) and via.id in imported):
                index, param = helpers[name]
                given = [k.value for k in node.keywords if k.arg == param]
                given += node.args[index:index + 1]
                if len(given) != 1 or path_of(given[0], names, here) is None:
                    unresolved.append(f"a {name} call it cannot resolve: {ast.unparse(node)}")
            func = node.func
            if (isinstance(func, ast.Attribute) and func.attr in ("insert", "append", "extend")
                    and isinstance(func.value, ast.Attribute) and func.value.attr == "path"
                    and isinstance(func.value.value, ast.Name) and func.value.value.id == "sys"):
                entry = node.args[-1] if node.args else None
                if isinstance(entry, ast.Call) and _name(entry.func) == "str" and len(entry.args) == 1:
                    entry = entry.args[0]
                value = path_of(entry, names, here)
                if value is None or Path(os.path.normpath(value)) != ROOT:
                    unresolved.append(f"a sys.path entry other than the repo root: {ast.unparse(node)}")
        if isinstance(node, (ast.Import, ast.ImportFrom)) and not getattr(node, "level", 0):
            modules = [a.name for a in node.names] if isinstance(node, ast.Import) else [node.module or ""]
            unresolved += [f"an import of {m}" for m in modules if m.split(".")[0] in folders]
    return files, unresolved


def load_closure(seeds):
    """(files, unresolved): each repo file the seed modules build a path to, followed through every `.py` file
    found, at any depth, with the unresolved loads of every module read, each as (module, what)."""
    todo, seen, files, unresolved = list(seeds), set(), {}, []
    while todo:
        module = todo.pop()
        if module in seen:
            continue
        seen.add(module)
        found, missed = built_paths((ROOT / module).read_text(encoding="utf-8"), ROOT / module)
        unresolved += [(module, what) for what in missed]
        for path in found:
            files.setdefault(path, set()).add(module)
            if path.endswith(".py"):
                todo.append(path)
    return files, unresolved


def job_seeds(text):
    scripts = [line.split()[1] for line in (l.strip() for l in regenerate_lines(text)[1]) if line.startswith("python ")]
    package = sorted(p.relative_to(ROOT).as_posix() for p in (ROOT / "model_routing").rglob("*.py"))
    return sorted(set(scripts)) + package


def paths_entries(text):
    block = dict(top_blocks(text))["on"]
    return re.findall(r'^      - "([^"]+)"$', block.split("    paths:\n", 1)[1], re.M)


def test_paths_name_each_file_outside_evidence_and_the_package_that_the_job_loads():
    text = workflow_text()
    files, unresolved = load_closure(job_seeds(text))
    assert unresolved == []
    outside = sorted(f for f in files if not f.startswith(INSIDE))
    assert outside == LOADED_OUTSIDE
    assert files["research/escalation_signals.py"] == {"evidence/tau2-bench/cascades.py"}
    assert files["research/escalation_public_tests.py"] == {"evidence/livecodebench/cascades.py"}
    assert files["research/livecodebench_cost.py"] == {"evidence/livecodebench/cascades.py"}
    assert paths_entries(text) == PATHS
    for path in LOADED_OUTSIDE:  # v1.559: each of them dropped fails
        assert problems(text.replace(f'      - "{path}"\n', ""), readme(),
                        CI.read_text(encoding="utf-8")) == ["triggers or paths differ"], path


def test_the_load_read_follows_loads_at_depth_two_and_fails_closed():
    # The Longtail-SWE delegation script (row CI27, not yet in Regenerate) loads research/longtail_per_call.py,
    # which loads research/longtail_delegation.py, so its lines need both in `paths`.
    files, unresolved = load_closure(["evidence/longtail-swe-delegation/results.py"])
    assert unresolved == []
    assert sorted(f for f in files if not f.startswith(INSIDE)) == [
        "research/longtail_delegation.py", "research/longtail_per_call.py"]
    here = ROOT / "evidence" / "fake" / "script.py"
    root = "import sys\nfrom pathlib import Path\nROOT = Path(__file__).resolve().parents[2]\n"
    target = 'Path(__file__).resolve().parents[2] / "research" / "escalation_signals.py"'
    helper = ("import importlib.util\nfrom pathlib import Path\n"
              "def _load(name, path):\n    spec = importlib.util.spec_from_file_location(name, path)\n    return spec\n")
    found, missed = built_paths(helper + 'm = _load("m", Path(__file__).resolve().parents[2] / "research" / '
                                '"escalation_signals.py")\n', here)
    assert found == {"research/escalation_signals.py"} and missed == []
    mutants = {
        "an os.path.join": ('import os\nX = os.path.join("research", "escalation_signals.py")\n',
                            "a .py string it cannot resolve: 'escalation_signals.py'"),
        "a helper given an unresolved path": (helper + 'm = _load("m", some_path)\n',
                                              "a _load call it cannot resolve: _load('m', some_path)"),
        "a direct load of an unresolved path": (
            "import importlib.util\ns = importlib.util.spec_from_file_location('m', where)\n",
            "a load it cannot resolve: importlib.util.spec_from_file_location('m', where)"),
        "an import of research": ("import research.escalation_signals\n", "an import of research.escalation_signals"),
        "an import_module": ('import importlib\nm = importlib.import_module("research")\n', "a import_module call"),
        # review iter-393 should-fix 1 and 2a, nit 2: a subfolder on sys.path, a helper called through an
        # attribute, a name bound twice
        "a subfolder on sys.path": (
            root + 'sys.path.insert(0, str(ROOT / "research"))\nimport escalation_signals\n',
            "a sys.path entry other than the repo root: sys.path.insert(0, str(ROOT / 'research'))"),
        "a helper through an attribute": (helper + 'm = obj._load("m", where)\n',
                                          "a _load call it cannot resolve: obj._load('m', where)"),
        "a name bound twice": (
            helper + f"path = {target}\nfor path in where:\n    s = importlib.util.spec_from_file_location('m', path)\n",
            "a load it cannot resolve: importlib.util.spec_from_file_location('m', path)"),
    }
    for source, problem in mutants.values():
        assert built_paths(source, here)[1] == [problem]
    # should-fix 2b: a loader that takes no spec_from_file_location fails on each of its calls
    assert built_paths('from importlib.machinery import SourceFileLoader\nm = SourceFileLoader("m", where).load_module()\n',
                       here)[1] == ["a load_module call", "a SourceFileLoader call"]
    # the repo root on sys.path is the one entry allowed (the Longtail-SWE scripts add it)
    assert built_paths(root + "sys.path.insert(0, str(ROOT))\n", here) == (set(), [])
    # nit 3: a path with `..` parts is placed by where it points, here outside evidence/
    dotdot = 'from pathlib import Path\nP = Path(__file__).resolve().parent / ".." / ".." / "research" / "escalation_signals.py"\n'
    assert built_paths(dotdot, here) == ({"research/escalation_signals.py"}, [])
