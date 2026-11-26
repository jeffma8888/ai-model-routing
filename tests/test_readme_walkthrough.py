"""DESIGN 5.2 v1.659 (row PROD1): README `## Running it in production` opens with a walk-through.

After the section's lead sentence (v1.604) come INTRO, one sentence that names the production lessons note
with no link (the README links it once, tests/test_research_production_lessons.py), and a numbered list of ten steps from a first call to steady state, in TOPICS' order, each naming what to use
and linking one lesson of that note by its heading's anchor, a different lesson for each step; the seven v1.604
paragraphs follow the list (tests/test_readme_production.py). Each `model-routing` command a step names is a
subcommand of the parser, each option it gives is one of that subcommand's, followed by the metavar the parser
gives that option where it gives one, and a command that gives any option gives every option its subcommand
requires; each such command runs, exit 0, on the files a fresh `model-routing demo` run writes, with its
placeholders bound to them, while the one bare command, `model-routing promote`, is the command of a README
transcript. A step gives no number but its own and the percents of `budget.WARN_SHARES`. The walk-through adds
no transcript. These tests fail on v1.658's README and pass on v1.659's.
"""

import argparse
import dataclasses
import inspect
import json
import re
from pathlib import Path

import pytest

import model_routing
from model_routing import main
from model_routing.budget import WARN_SHARES
from model_routing.cli import _build_parser
from model_routing.executor import Executor
from model_routing.tasks import Task
from test_readme_production import LEAD, MOVED, PRODUCTION, anchors, paragraphs, read

ROOT = Path(__file__).resolve().parents[1]
NOTE = "research/production-lessons.md"
INTRO = ("From a first call to steady state, in order, each step with one lesson from the production lessons "
         "note and its detail in the paragraphs below:")
LINK = re.compile(r"\[[^\]]+\]\(([^)\s]+)\)")
COMMAND = re.compile(r"`(model-routing [^`]+)`")
# each step's names, in the row's order: the task and its check; calibrate before routing, new routes cold;
# a route per setup, compared on cost per success; a procedure; a self-hosted row kept to its tasks; cache
# reads; warn budgets first, never below the bar; shadow and promote on the same data; prices and calibration
# on a schedule; what the library leaves to the caller
TOPICS = [
    ("`tasks.json`", "`bar`", "`min_samples`", "`Executor.call(..., validate=...)`", "`invalid`"),
    # review iter-515 should-fix 1: `insufficient_samples` only under `min_samples`, then `below_bar` until the bound clears
    ("`model-routing plan --success P --bar B`", "`model-routing calibrate --results FILE --stats FILE`", "cold",
     "`insufficient_samples` under `min_samples` trials", "admitted only once its own bound clears the bar"),
    ("`variants`", "`model-routing evaluate --outcomes FILE --cost-per-correct`", "cost per correct item"),
    ("`Procedure`", "`procedures=[...]`", "the agent"),
    ('`"pricing_basis": "self_hosted"`', '`"scope_tasks"`'),
    ("`cached_input_tokens`", "`model-routing report --log PATH --cache`", "prompt prefix"),
    ('`Budget(name, limit_usd, "warn")`', "`refuse`", "`downgrade`", "below the bar"),
    ("`shadow_rate`", "`model-routing pairs --log PATH --out FILE`", "`model-routing promote`", "the same items"),
    ("On a schedule", "`models.json`", "`price_valid_until`", "calibrate again",
     "`model-routing drift --log PATH --audits PATH --json`"),
    ("your own code and scheduler", "`price_cache_write`", "loaded only when needed", "precomputing offline"),
]


def walkthrough(text=None):
    found = paragraphs(read("README.md") if text is None else text, PRODUCTION)
    at = found.index(INTRO)
    return found[at], found[at + 1].split("\n")


def subparsers():
    for action in _build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return action.choices
    raise AssertionError("cli.py defines no subcommands")


def command_problems(command, choices=None):
    """What is wrong with one `model-routing ...` command as a step writes it, by the CLI's own parser."""
    choices = subparsers() if choices is None else choices
    words = command.split()
    if words[0] != "model-routing" or len(words) < 2 or words[1] not in choices:
        return [f"{command}: no such subcommand"]
    options = {flag: action for action in choices[words[1]]._actions for flag in action.option_strings}
    problems, given, at = [], [], 2
    while at < len(words):
        flag = words[at]
        if flag not in options:
            return problems + [f"{command}: {flag} is no option of {words[1]}"]
        action, at = options[flag], at + 1
        given.append(flag)
        if action.nargs == 0:
            continue
        if at >= len(words) or words[at].startswith("--"):
            return problems + [f"{command}: {flag} has no value"]
        if action.metavar is not None and words[at] != action.metavar:
            problems.append(f"{command}: {flag} {words[at]}, where the parser gives {action.metavar}")
        at += 1
    required = [action.option_strings[-1] for action in choices[words[1]]._actions
                if action.required and action.option_strings]
    missing = [flag for flag in required if flag not in given]
    if given and missing:
        problems.append(f"{command}: lacks {', '.join(missing)}")
    return problems


# --- the place and the shape ------------------------------------------------------------------

def test_the_walkthrough_follows_the_lead_and_precedes_the_seven():
    found = paragraphs(read("README.md"), PRODUCTION)
    assert found[0] == LEAD and found[1] == INTRO and found[2].startswith("1. ")
    assert found[3].startswith(MOVED[0][0])
    assert sum(p == INTRO for p in found) == 1 and read("README.md").count(INTRO) == 1


def test_the_list_is_ten_numbered_steps_each_linking_a_different_lesson_of_the_note():
    intro, steps = walkthrough()
    assert len(steps) == len(TOPICS) == 10
    # the README links the note itself once (tests/test_research_production_lessons.py), so INTRO names it unlinked
    assert LINK.findall(intro) == [] and "production lessons note" in intro
    lessons = anchors((ROOT / NOTE).read_text(encoding="utf-8"))
    seen = []
    for number, step in enumerate(steps, 1):
        assert step.startswith(f"{number}. ") and not step[len(f"{number}. "):][:1].isdigit(), step
        [target] = LINK.findall(step)
        page, _, anchor = target.partition("#")
        assert page == NOTE and anchor in lessons, step
        seen.append(anchor)
    assert len(set(seen)) == 10


def test_each_step_names_its_topic_in_the_rows_order():
    _, steps = walkthrough()
    for step, names in zip(steps, TOPICS):
        for name in names:
            assert step.count(name) == 1, (name, step[:60])


def test_each_api_and_field_a_step_names_is_the_librarys():
    assert {"Procedure", "Budget", "Executor"} <= set(model_routing.__all__)
    assert "validate" in inspect.signature(Executor.call).parameters
    assert "procedures" in inspect.signature(Executor.call).parameters
    assert list(inspect.signature(model_routing.Budget).parameters)[:3] == ["name", "limit_usd", "mode"]
    fields = {field.name for field in dataclasses.fields(Task)}
    assert {"bar", "min_samples", "shadow_rate"} <= fields
    registry = (ROOT / "model_routing" / "registry.py").read_text(encoding="utf-8")
    for key in ("pricing_basis", "self_hosted", "scope_tasks", "variants", "price_cache_write", "price_valid_until"):
        assert f'"{key}"' in registry, key
    budget = (ROOT / "model_routing" / "budget.py").read_text(encoding="utf-8")
    for mode in ("warn", "refuse", "downgrade"):
        assert f'"{mode}"' in budget, mode
    assert model_routing.INSUFFICIENT_SAMPLES == "insufficient_samples"


def test_a_step_gives_no_number_but_its_own_and_the_warn_shares():
    _, steps = walkthrough()
    numbers = []
    for number, step in enumerate(steps, 1):
        body = LINK.sub("", step[len(f"{number}. "):])
        numbers += re.findall(r"\d+", body)
    assert numbers == [str(round(100 * share)) for share in WARN_SHARES] == ["50", "80", "100"]


def test_the_walkthrough_adds_no_transcript():
    intro, steps = walkthrough()
    assert "```" not in intro and not any("```" in step for step in steps)
    blocks = re.findall(r"```text\n\$ model-routing ", read("README.md"))
    assert len(blocks) == 12


# --- the commands -----------------------------------------------------------------------------

def test_every_command_a_step_names_is_the_parsers():
    _, steps = walkthrough()
    commands = [command for step in steps for command in COMMAND.findall(step)]
    assert [c.split()[1] for c in commands] == ["plan", "calibrate", "evaluate", "report", "pairs", "promote",
                                                "drift"]
    for command in commands:
        assert command_problems(command) == [], command


@pytest.mark.parametrize("command, problem", [
    ("model-routing prices --check", "model-routing prices --check: no such subcommand"),
    ("model-routing report --log PATH --cached", "model-routing report --log PATH --cached: --cached is no option of report"),
    ("model-routing pairs --log FILE --out FILE",
     "model-routing pairs --log FILE --out FILE: --log FILE, where the parser gives PATH"),
    ("model-routing drift --log PATH --json", "model-routing drift --log PATH --json: lacks --audits"),
    ("model-routing calibrate --results --stats FILE", "model-routing calibrate --results --stats FILE: --results has no value"),
])
def test_a_wrong_command_is_named(command, problem):
    assert command_problems(command) == [problem]


def test_a_bare_subcommand_needs_no_option():
    assert command_problems("model-routing promote") == []
    assert command_problems("model-routing promote --task T") == [
        "model-routing promote --task T: lacks --challenger, --margin, --outcomes"]


def bound(command, run):
    """The command's words with each placeholder bound to a file of the demo run in `run`."""
    values = {("plan", "--success"): "0.95", ("plan", "--bar"): "0.85",
              ("calibrate", "--results"): str(run / "outcomes.jsonl"),
              ("calibrate", "--stats"): str(run / "walk-stats.json"),
              ("evaluate", "--outcomes"): str(run / "outcomes.jsonl"),
              ("report", "--log"): str(run / "calls.jsonl"),
              ("pairs", "--log"): str(run / "calls.jsonl"), ("pairs", "--out"): str(run / "walk-pairs.jsonl"),
              ("drift", "--log"): str(run / "calls.jsonl"), ("drift", "--audits"): str(run / "walk-audits.jsonl")}
    words = command.split()[1:]
    out = [words[0]]
    for at, word in enumerate(words[1:], 1):
        key = (words[0], words[at - 1])
        out.append(values.pop(key) if key in values else word)
    assert not [w for w in out[1:] if w.isupper()], out
    return out


def test_every_command_a_step_names_runs_on_the_demos_files(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["demo", "--out", "demo-run"]) == 0
    run = tmp_path / "demo-run"
    ids = []
    for line in (run / "calls.jsonl").read_text(encoding="utf-8").splitlines():
        call_id = json.loads(line).get("call_id")
        if call_id and call_id not in ids:
            ids.append(call_id)
    assert ids
    (run / "walk-audits.jsonl").write_text(
        "".join(json.dumps({"call_id": call_id, "correct": True}) + "\n" for call_id in ids), encoding="utf-8")
    capsys.readouterr()
    _, steps = walkthrough()
    ran, bare = [], []
    for command in (c for step in steps for c in COMMAND.findall(step)):
        if len(command.split()) == 2:
            bare.append(command)
            continue
        args = bound(command, run)
        assert main(args) == 0, command
        out = capsys.readouterr().out
        assert out.strip(), command
        ran.append(args[0])
    assert ran == ["plan", "calibrate", "evaluate", "report", "pairs", "drift"]
    assert bare == ["model-routing promote"]
    transcripts = re.findall(r"```text\n\$ model-routing (\S+)", read("README.md"))
    assert "promote" in transcripts


# --- DESIGN and the changelog -----------------------------------------------------------------

def test_design_states_v1_659_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = design[design.index("### 5.2 "):design.index("### 5.3 ")]
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.659 README walk-through (row PROD1): ")]
    for kept in ("opens, after its lead sentence (v1.604), with a walk-through from a first call to steady state",
                 "(rule 7; review iter-515 should-fix 1)",
                 "a numbered list of ten steps in this order",
                 "linking one lesson of that note by its heading's anchor, a different lesson for each step",
                 "the 50, 80 and 100 percent of `budget.WARN_SHARES` (4.6)",
                 "names no row not yet shipped",
                 "a command that gives any option gives every option its subcommand requires",
                 "runs, exit 0, on the files a fresh `model-routing demo` run writes",
                 "the one bare command, `model-routing promote`, is the command of a README transcript (12.5)",
                 "the section is 29,356 bytes by the 12.8 measure, 644 under v1.629's 30,000-byte cap, which stays",
                 "tests/test_readme_trim.py's `LATER` gains the two paragraphs, 145 and 3,366 bytes",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    assert five2.index("\n- v1.655 README paragraph places (") < five2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.659 (")]
    assert line.startswith("- v1.659 (2026-11-26): docs and tests (5.2, row PROD1). ")
    assert len(line.encode("utf-8")) <= 600
