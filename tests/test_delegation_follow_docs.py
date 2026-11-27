"""DESIGN 5.2 v1.690 (row DEL2c, the remainder of row DEL2b): following delegation advice in README
`## Running it in production`.

No code changes. The section ends with one paragraph of at most 600 bytes, right after the one on the pair route
(v1.680, v1.682), on checking whether an agent takes the hand-offs it is advised to: `Executor.record_mode` (7 v1.687)
logs the mode `decide_delegation` advised beside the mode the agent took and the work's input size, and
`model-routing report --log PATH --delegation [--tasks PATH]` (10 v1.689) gives per task and parent the share of
advised hand-offs taken and the correlation of handing off with input size (8.3 v1.688), flagging a share under a
task's `"min_delegation_follow"` (4.2 v1.688), with one pointer to DESIGN.md and a link to the Harvey lesson on
under-delegation. Each claim is checked here on the library and the command line beside the words that state it,
on tests/test_record_mode.py's delegated scenario: four mode records of one delegate decision, the agent doing the
first two itself (1,000 and 2,000 tokens) and handing off the last two (6,000 and 8,000). The bytes are
tests/test_readme_trim.py's v1.690 block, and every README transcript keeps its bytes (gates.py).
"""

import argparse
import json
import math
from pathlib import Path

from test_opportunities import run
from test_readme_production import PRODUCTION, PRODUCTION_CAP, link_problems, paragraphs, size
from test_record_mode import delegated

from model_routing import Executor, Monitor, load_records
from model_routing.cli import _build_parser

ROOT = Path(__file__).resolve().parents[1]
PAIR_LEAD = "A delegating harness's root and sub-agent models can be routed as a pair: "
LESSON = "Under-delegation is a failure you can measure, and depth needs a cap"
ANCHOR = "research/production-lessons.md#under-delegation-is-a-failure-you-can-measure-and-depth-needs-a-cap"
PARAGRAPH = (
    "An agent's hand-offs can be checked against the advice: `Executor.record_mode` logs the mode "
    "`decide_delegation` advised beside the mode the agent took and the work's input size, and "
    "`model-routing report --log PATH --delegation [--tasks PATH]` gives per task and parent the share of advised "
    "hand-offs taken and the correlation of handing off with input size, flagging a share under a task's "
    "`\"min_delegation_follow\"` (`DESIGN.md` 4.2, 7, 8.3 and 10). "
    f"For Harvey [under-delegation can be measured]({ANCHOR}).")
TAKEN = [("inline", 1000), ("inline", 2000), ("delegate", 6000), ("delegate", 8000)]
# by hand, handing off as 0 or 1 against the input size: the means are 0.5 and 4,250, the deviations' products sum
# to 0.5 * (3250 + 2250 + 1750 + 3750) = 5,500, the squared deviations to 1 and 3250^2 + 2250^2 + 1750^2 + 3750^2
# = 32,750,000, so r = 5500 / sqrt(32,750,000)
CORRELATION = 5500 / math.sqrt(32_750_000)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def says(words):
    assert PARAGRAPH.count(words) == 1, words


def logged(tmp_path, minimum=None):
    """The scenario's four mode records written to a log by `record_mode`, and a tasks file for its task, with
    ``minimum`` as its `min_delegation_follow` when given; returns the decision, the records, the log and the file."""
    route, decision = delegated()
    tmp_path.mkdir(exist_ok=True)
    log = tmp_path / "log.jsonl"
    ex = Executor(route, None, monitor=Monitor(log))
    records = [ex.record_mode(decision, actual, tokens) for actual, tokens in TAKEN]
    task = {"name": decision.task, "bar": 0.8, **({} if minimum is None else {"min_delegation_follow": minimum})}
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps({"tasks": [task]}), encoding="utf-8")
    return decision, records, str(log), str(tasks)


def report(argv):
    code, out, err = run(["report", *argv, "--delegation", "--json"])
    assert (code, err) == (0, "")
    return json.loads(out)


# --- README -------------------------------------------------------------------------------------

def test_the_paragraph_follows_the_one_on_the_pair_route_inside_the_cap():
    text = read("README.md")
    found = paragraphs(text, PRODUCTION)
    # placed by its neighbour (v1.655, row T30); tests/test_readme_trim.py names the section's last paragraph
    assert text.count(PARAGRAPH) == 1 and found.count(PARAGRAPH) == 1
    at = found.index(PARAGRAPH)
    assert at > 0 and found[at - 1].startswith(PAIR_LEAD)
    assert len(PARAGRAPH.encode("utf-8")) == 598 <= 600
    assert size(text, PRODUCTION) <= PRODUCTION_CAP == 30_000
    assert "\u2014" not in PARAGRAPH and "\u2013" not in PARAGRAPH and "```" not in PARAGRAPH
    assert link_problems(text) == []


def test_it_names_the_method_the_command_and_the_task_key():
    for name in ("`Executor.record_mode`", "`decide_delegation`",
                 "`model-routing report --log PATH --delegation [--tasks PATH]`", "`\"min_delegation_follow\"`"):
        says(name)
    # README.md named neither the method, the option nor the task key before v1.690 (row DEL2c), and names
    # `delegation_follow` only inside the task key
    text = read("README.md")
    assert text.count("record_mode") == 1 and text.count("--delegation") == 1
    assert text.count("delegation_follow") == text.count("min_delegation_follow") == 1


def test_the_link_is_the_lesson_that_holds_harvey_s_findings():
    says("For Harvey [under-delegation can be measured]")
    assert PARAGRAPH.count("](") == 1 and PARAGRAPH.endswith(f"]({ANCHOR}).")
    note = read("research/production-lessons.md")
    lesson = note.split(f"\n### {LESSON}\n", 1)[1].split("\n### ", 1)[0]
    [result] = [line for line in lesson.splitlines() if line.startswith("- Result: ")]
    assert "neither spawns sub-agents despite having the ability to." in result
    assert "The post-trained root makes 64% more sub-agent calls per data room." in result
    # the paragraph quotes no source, so the note alone holds the quotes: its one pair of double quotes is the
    # task key's
    assert '"' not in PARAGRAPH.replace('`"min_delegation_follow"`', "")


def test_the_command_and_its_options_are_the_parser_s():
    says("`model-routing report --log PATH --delegation [--tasks PATH]`")
    parser = _build_parser()
    [sub] = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    options = {o: a for a in sub.choices["report"]._actions for o in a.option_strings}
    # `--log` is required and may be given more than once; `--delegation` is a switch; `--tasks` is optional with
    # the metavar PATH
    assert options["--log"].required and isinstance(options["--log"], argparse._AppendAction)
    assert isinstance(options["--delegation"], argparse._StoreTrueAction) and not options["--delegation"].required
    assert options["--tasks"].metavar == "PATH" and not options["--tasks"].required


# --- its claims, each beside its words ------------------------------------------------------------

def test_record_mode_logs_the_advised_mode_beside_the_mode_taken_and_the_input_size(tmp_path):
    says("`Executor.record_mode` logs the mode `decide_delegation` advised beside the mode the agent took and the "
         "work's input size")
    decision, records, log, _ = logged(tmp_path)
    assert decision.mode == "delegate"
    saved = load_records(log)
    assert saved == records and len(saved) == len(TAKEN)
    assert [(r["advised_mode"], r["actual_mode"], r["work_input_tokens"]) for r in saved] == [
        ("delegate", actual, tokens) for actual, tokens in TAKEN]


def test_the_report_gives_per_task_and_parent_the_share_taken_and_the_correlation(tmp_path):
    says("gives per task and parent the share of advised hand-offs taken and the correlation of handing off with "
         "input size")
    decision, _, log, _ = logged(tmp_path)
    [row] = report(["--log", log])
    assert (row["task"], row["parent"]) == (decision.task, decision.parent) == ("t", "y/cheap")
    # 2 of the 4 advised hand-offs taken
    assert (row["delegate_advised"], row["delegate_followed"], row["delegate_follow_share"]) == (4, 2, 0.5)
    assert round(CORRELATION, 6) == 0.961074
    assert abs(row["delegate_size_correlation"] - CORRELATION) < 1e-6
    # without `--tasks` no row is flagged
    assert "below_follow" not in row and "min_delegation_follow" not in row


def test_tasks_flags_a_share_under_the_task_s_minimum(tmp_path):
    says("flagging a share under a task's `\"min_delegation_follow\"`")
    _, _, log, tasks = logged(tmp_path / "under", minimum=0.6)
    [row] = report(["--log", log, "--tasks", tasks])
    assert (row["delegate_follow_share"], row["min_delegation_follow"], row["below_follow"]) == (0.5, 0.6, True)
    _, _, log, tasks = logged(tmp_path / "at", minimum=0.5)
    [row] = report(["--log", log, "--tasks", tasks])
    assert (row["min_delegation_follow"], row["below_follow"]) == (0.5, False)
    # a task with no minimum gives no flag key
    _, _, log, tasks = logged(tmp_path / "none")
    [row] = report(["--log", log, "--tasks", tasks])
    assert "below_follow" not in row and "min_delegation_follow" not in row


# --- DESIGN ---------------------------------------------------------------------------------------

def test_the_pointer_names_each_subsection_that_states_a_claim():
    says("(`DESIGN.md` 4.2, 7, 8.3 and 10).")
    design = read("DESIGN.md")
    starts = {"4.2": "### 4.2 ", "7": "## 7. ", "8.3": "### 8.3 ", "10": "## 10. "}
    ends = {"4.2": "### 4.3 ", "7": "## 8. ", "8.3": "## 9. ", "10": "## 11. "}
    part = {k: design[design.index("\n" + v):design.index("\n" + ends[k], design.index("\n" + v))]
            for k, v in starts.items()}
    assert "\n- v1.688 delegation follow minimum (row DEL2a): `Task` gains a last field" in part["4.2"]
    assert "\n- v1.687 `.record_mode(decision, actual_mode, input_tokens, tags=None) -> dict` (row DEL2, " in part["7"]
    assert "\n- v1.688 `delegation_follow(records, *, tasks=None) -> list[dict]` (row DEL2a, " in part["8.3"]
    assert "\n  - v1.689 `report --log PATH --delegation [--tasks PATH] [--json]` (row DEL2b, " in part["10"]
    # review iter-549 nit 1: bounded by 5.3, as the four above are by their next headings
    five2 = design[design.index("\n### 5.2 "):design.index("\n### 5.3 ", design.index("\n### 5.2 "))]
    assert "\n- v1.690 README delegation follow (row DEL2c, " in five2
    # the Not-in-this-version clauses that named the README sentence's row name the version that adds it
    for k in ("7", "8.3", "10"):
        assert part[k].count("the README sentence (row DEL2c, which v1.690 adds in 5.2)") == 1, k
    assert "(row DEL2c)." not in design
