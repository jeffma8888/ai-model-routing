"""DESIGN 4.2 and 8.3 v1.688 (row DEL2a): `delegation_follow(records, *, tasks=None)`, one row per task and
parent of a log's mode records (8.1 v1.687), and a task's `min_delegation_follow` flagging a row under it.

A mode record holds the mode `decide_delegation` advised (`advised_mode`) beside the mode the agent took
(`actual_mode`) and the work's input size (`work_input_tokens`). Each row counts the delegate and inline
advice, the share of each the agent took, and the point-biserial correlation of handing off with input size.
The scenario logs are tests/test_record_keys.py's, the hand-off decision tests/test_record_mode.py's.
"""

import dataclasses
import json
import math
from pathlib import Path

import pytest

import model_routing
from model_routing import Executor, Monitor, Task, delegation_follow, load_records, load_tasks
from model_routing.demo import _tasks_json
from test_record_keys import router, scenarios
from test_record_mode import delegated

ROOT = Path(__file__).resolve().parents[1]
KEYS = ["task", "parent", "records", "delegate_advised", "delegate_followed", "delegate_follow_share",
        "inline_advised", "inline_followed", "inline_follow_share", "delegate_size_correlation"]
FLAGGED = KEYS + ["min_delegation_follow", "below_follow"]


def mode(n, advised, actual, size, task="t", parent="x/big", **extra):
    """A mode record as `Executor.record_mode` writes one (8.1 v1.687)."""
    rec = {"ts": "2026-11-27T09:00:00Z", "call_id": f"mode-{n}", "task": task, "flavor": "cost_effective",
           "parent": parent, "advised_mode": advised, "actual_mode": actual, "reason": "parent_below_bar",
           "work_input_tokens": size, "tags": {}}
    rec.update(extra)
    return rec


def hand_offs(taken, advised=10, task="t", parent="x/big", start=0):
    """``advised`` delegate advice of which the agent took the first ``taken``, then 2 inline advice followed."""
    recs = [mode(start + i, "delegate", "delegate" if i < taken else "inline", 1000 + 100 * i, task, parent)
            for i in range(advised)]
    return recs + [mode(start + advised + i, "inline", "inline", 200, task, parent) for i in range(2)]


def pearson(xs, ys):
    """The textbook Pearson correlation, from the means, as a hand computation does it."""
    n = len(xs)
    mx, my = sum(xs) / n, sum(ys) / n
    cov = sum((x - mx) * (y - my) for x, y in zip(xs, ys))
    return cov / math.sqrt(sum((x - mx) ** 2 for x in xs) * sum((y - my) ** 2 for y in ys))


def tasks(**fields):
    return {"t": Task("t", 0.8, **fields)}


# --- 8.3 v1.688: the rows --------------------------------------------------------------------------

def test_an_agent_that_took_3_of_10_advised_hand_offs_is_flagged_under_a_minimum_of_one_half():
    recs = hand_offs(3)
    rows = delegation_follow(recs, tasks=tasks(min_delegation_follow=0.5))
    assert len(rows) == 1 and list(rows[0]) == FLAGGED
    row = rows[0]
    assert (row["task"], row["parent"], row["records"]) == ("t", "x/big", 12)
    assert (row["delegate_advised"], row["delegate_followed"], row["delegate_follow_share"]) == (10, 3, 0.3)
    assert (row["inline_advised"], row["inline_followed"], row["inline_follow_share"]) == (2, 2, 1.0)
    xs = [rec["actual_mode"] == "delegate" for rec in recs]
    assert row["delegate_size_correlation"] == round(pearson(xs, [rec["work_input_tokens"] for rec in recs]), 6)
    assert row["min_delegation_follow"] == 0.5 and type(row["min_delegation_follow"]) is float
    assert row["below_follow"] is True


def test_an_agent_that_took_every_advised_hand_off_is_not_flagged():
    row, = delegation_follow(hand_offs(10), tasks=tasks(min_delegation_follow=0.5))
    assert (row["delegate_advised"], row["delegate_followed"], row["delegate_follow_share"]) == (10, 10, 1.0)
    assert row["below_follow"] is False


@pytest.mark.parametrize("taken, least, below", [(5, 0.5, False), (5, 0.51, True), (9, 1, True), (10, 1, False),
                                                 (0, 0, False), (1, 0.1, False)])
def test_the_flag_is_a_share_under_the_minimum_not_at_it(taken, least, below):
    row, = delegation_follow(hand_offs(taken), tasks=tasks(min_delegation_follow=least))
    assert row["below_follow"] is below
    assert row["min_delegation_follow"] == float(least) and type(row["min_delegation_follow"]) is float


def test_the_correlation_is_the_hand_computed_point_biserial_value():
    sizes = [(900, "delegate"), (1200, "delegate"), (600, "delegate"), (100, "inline"), (300, "inline")]
    recs = [mode(i, "delegate", actual, size) for i, (size, actual) in enumerate(sizes)]
    row, = delegation_follow(recs)
    # point-biserial by hand: means 900 (delegate) and 200 (inline), population SD sqrt(788000 / 5), p = 0.6
    hand = (900 - 200) / math.sqrt(788000 / 5) * math.sqrt(0.6 * 0.4)
    assert row["delegate_size_correlation"] == round(hand, 6) == 0.863825
    flipped = [dict(rec, actual_mode="inline" if rec["actual_mode"] == "delegate" else "delegate") for rec in recs]
    assert delegation_follow(flipped)[0]["delegate_size_correlation"] == -0.863825


@pytest.mark.parametrize("recs", [
    [mode(0, "delegate", "delegate", 900)],
    [mode(0, "delegate", "inline", 900), mode(1, "inline", "inline", 100)],
    [mode(0, "delegate", "delegate", 500), mode(1, "inline", "inline", 500)],
], ids=["one record", "one mode", "one size"])
def test_the_correlation_is_none_on_one_record_one_mode_or_one_size(recs):
    assert delegation_follow(recs)[0]["delegate_size_correlation"] is None


def test_two_points_correlate_fully_and_no_spread_in_the_sum_is_zero():
    two = [mode(0, "delegate", "inline", 5000), mode(1, "delegate", "delegate", 9000)]
    assert delegation_follow(two)[0]["delegate_size_correlation"] == 1.0
    even = [mode(0, "delegate", "delegate", 100), mode(1, "delegate", "inline", 100),
            mode(2, "delegate", "delegate", 300), mode(3, "delegate", "inline", 300)]
    assert delegation_follow(even)[0]["delegate_size_correlation"] == 0.0


def test_a_size_too_large_for_a_float_raises_nothing():
    big = 10 ** 400
    recs = [mode(0, "delegate", "delegate", big), mode(1, "delegate", "inline", 0),
            mode(2, "delegate", "delegate", 2 * big)]
    assert delegation_follow(recs)[0]["delegate_size_correlation"] == round(pearson([1, 0, 1], [1, 0, 2]), 6)


def test_each_task_and_parent_has_its_own_row_in_order():
    recs = (hand_offs(1, task="b", parent="p2") + hand_offs(4, task="a", parent="p2", start=20)
            + hand_offs(7, task="a", parent="p1", start=40))
    recs = recs[::2] + recs[1::2]  # interleaved
    rows = delegation_follow(recs)
    assert [(r["task"], r["parent"], r["delegate_followed"], r["delegate_advised"]) for r in rows] == [
        ("a", "p1", 7, 10), ("a", "p2", 4, 10), ("b", "p2", 1, 10)]
    assert all(list(r) == KEYS for r in rows)


def test_a_row_with_no_delegate_advice_has_no_share_and_no_flag_value():
    recs = [mode(0, "inline", "inline", 100), mode(1, "inline", "delegate", 900), mode(2, "inline", "inline", 50)]
    row, = delegation_follow(recs, tasks=tasks(min_delegation_follow=0.5))
    assert (row["delegate_advised"], row["delegate_followed"], row["delegate_follow_share"]) == (0, 0, None)
    assert (row["inline_advised"], row["inline_followed"], row["inline_follow_share"]) == (3, 2, 0.666667)
    assert row["below_follow"] is None
    only = delegation_follow(hand_offs(3)[:10])[0]
    assert (only["inline_advised"], only["inline_follow_share"]) == (0, None)


def test_no_flag_key_without_tasks_without_a_minimum_or_for_a_task_not_given():
    recs = hand_offs(3) + hand_offs(3, task="u", start=20)
    for given in (None, {}, tasks(), {"u": Task("u", 0.8)}):
        assert all(list(r) == KEYS for r in delegation_follow(recs, tasks=given)), given
    rows = delegation_follow(recs, tasks=tasks(min_delegation_follow=0.5))
    assert [list(r) for r in rows] == [FLAGGED, KEYS]
    bare = delegation_follow(recs)
    assert [{k: r[k] for k in KEYS} for r in rows] == bare


# --- 8.3 v1.688: the records it reads ----------------------------------------------------------------

@pytest.fixture(scope="module")
def logs(tmp_path_factory):
    return scenarios(tmp_path_factory.mktemp("delegation-follow"))


def test_a_log_with_no_mode_record_gives_no_row(logs):
    assert delegation_follow([]) == []
    budget = [rec for clean in logs.values() for rec in clean if "budget_event" in rec]
    assert budget  # the scenarios hold budget records
    for name, clean in logs.items():
        assert delegation_follow(clean) == [], name


def test_attempt_and_budget_records_are_passed_by(logs):
    alone = delegation_follow(hand_offs(3))
    for name, clean in logs.items():
        assert delegation_follow(clean[:1] + hand_offs(3) + clean[1:]) == alone, name


def test_records_written_by_record_mode_and_read_back_give_their_row(tmp_path):
    route, decision = delegated()
    path = tmp_path / "log.jsonl"
    ex = Executor(route, None, monitor=Monitor(path))
    ex.record_mode(decision, "inline", 5000)
    ex.record_mode(decision, "delegate", 9000, tags={"team": "a"})
    row, = delegation_follow(load_records(path), tasks={"t": dataclasses.replace(route.tasks["t"],
                                                                                 min_delegation_follow=0.75)})
    assert (row["task"], row["parent"]) == (decision.task, decision.parent)
    assert (row["delegate_advised"], row["delegate_followed"], row["delegate_follow_share"]) == (2, 1, 0.5)
    assert row["delegate_size_correlation"] == 1.0 and row["below_follow"] is True


# --- 8.3 v1.688: the checks ----------------------------------------------------------------------

@pytest.mark.parametrize("given", [[], "t", {"t": "task"}, {"t": None}, {1: Task("t", 0.8)}],
                         ids=["list", "str", "str value", "None value", "int key"])
def test_bad_tasks_are_a_value_error(given):
    with pytest.raises(ValueError, match="tasks"):
        delegation_follow(hand_offs(3), tasks=given)


@pytest.mark.parametrize("bad", [{"task": 1}, {"parent": None}, {"advised_mode": "Delegate"},
                                 {"advised_mode": None}, {"actual_mode": "skip"}, {"actual_mode": ["inline"]},
                                 {"work_input_tokens": -1}, {"work_input_tokens": True},
                                 {"work_input_tokens": 1.5}, {"work_input_tokens": "100"},
                                 {"work_input_tokens": None}])
def test_a_record_that_is_no_mode_record_is_a_value_error_naming_its_call_id(bad):
    recs = hand_offs(3) + [mode("bad", "delegate", "delegate", 100, **bad)]
    with pytest.raises(ValueError, match="mode-bad"):
        delegation_follow(recs)


def test_a_mode_record_missing_a_key_is_a_value_error():
    rec = mode("gone", "delegate", "delegate", 100)
    for key in ("task", "parent", "actual_mode", "work_input_tokens"):
        with pytest.raises(ValueError, match="mode-gone"):
            delegation_follow([{k: v for k, v in rec.items() if k != key}])


# --- 4.2 v1.688: the field ----------------------------------------------------------------------

def test_the_field_is_the_last_with_its_default():
    names = [f.name for f in dataclasses.fields(Task)]
    assert names[-2:] == ["min_self_consistency", "min_delegation_follow"]
    assert Task("t", 0.5).min_delegation_follow is None
    for value in (0, 1, 0.0, 0.7, 1.0):
        assert Task("t", 0.5, min_delegation_follow=value).min_delegation_follow == value


@pytest.mark.parametrize("value", [-0.01, 1.01, -1, 2, True, False, math.nan, math.inf, -math.inf, 10 ** 400,
                                   "0.5", [0.5]])
def test_a_bad_minimum_is_a_value_error_naming_the_task(value):
    with pytest.raises(ValueError, match="'t'.*min_delegation_follow"):
        Task("t", 0.5, min_delegation_follow=value)


def test_load_tasks_reads_the_minimum_and_a_row_without_it_gets_none(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "min_delegation_follow": 0.7},
                                          {"name": "b", "bar": 0.5, "min_delegation_follow": None},
                                          {"name": "c", "bar": 0.5}]}), encoding="utf-8")
    loaded = load_tasks(path)
    assert [loaded[n].min_delegation_follow for n in "abc"] == [0.7, None, None]
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "min_delegation_follow": "0.7"}]}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="min_delegation_follow"):
        load_tasks(path)


def test_no_packaged_task_has_it_and_the_demo_tasks_file_holds_it_only_when_set():
    packaged = load_tasks(model_routing.DATA_DIR / "example_tasks.json")
    assert packaged and all(task.min_delegation_follow is None for task in packaged.values())
    assert "min_delegation_follow" not in _tasks_json(Task("t", 0.5))
    row = json.loads(_tasks_json(Task("t", 0.5, min_delegation_follow=0.7)))["tasks"][0]
    assert row["min_delegation_follow"] == 0.7


def test_the_minimum_routes_nothing():
    plain, flagged = router(), router(min_delegation_follow=0.9)
    for flavor in ("cost_effective", "cost_blind"):
        assert flagged.select("t", flavor) == plain.select("t", flavor)
    kwargs = dict(context_tokens=2000, brief_tokens=1000, result_tokens=1000, inline_separate_call=False)
    for parent in ("x/small", "x/big"):
        assert flagged.decide_delegation("t", parent, **kwargs) == plain.decide_delegation("t", parent, **kwargs)


# --- exports and docs ---------------------------------------------------------------------------

def test_delegation_follow_is_exported_after_opportunities():
    names = model_routing.__all__
    assert names[names.index("opportunities") + 1] == "delegation_follow"
    assert model_routing.delegation_follow is model_routing.monitor.delegation_follow


def test_no_evidence_or_research_script_workflow_or_readme_calls_it():
    paths = [p for d in ("evidence", "research") for p in (ROOT / d).rglob("*.py")]
    paths += list((ROOT / ".github" / "workflows").glob("*.yml")) + [ROOT / "README.md"]
    assert len(paths) > 10
    for path in paths:
        text = path.read_text(encoding="utf-8")
        assert "delegation_follow" not in text and "min_delegation_follow" not in text, path


def test_design_states_v1_688_in_4_2_and_8_3_and_the_changelog_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four2 = design[design.index("### 4.2 "):design.index("### 4.3 ")]
    seven = design[design.index("## 7. "):design.index("## 8. ")]
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert four2.count("\n- v1.688 delegation follow minimum (row DEL2a): `Task` gains a last field") == 1
    assert eight3.count("\n- v1.688 `delegation_follow(records, *, tasks=None) -> list[dict]` (row DEL2a") == 1
    assert "`below_follow` flag (row DEL2a), which v1.688 adds (4.2, 8.3); " in seven
    assert "  - Not in this version: a reader of mode records (row DEL2a), which v1.688 adds. " in eight3
    assert "  - Not in this version: `report --delegation` and the README sentence (row DEL2b). " in eight3
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.688 (2026-11-27): ") == 1


def test_the_production_lessons_line_says_the_report_ships_and_the_cli_and_the_cap_are_changes():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    section = text[text.index("### Under-delegation is a failure you can measure"):]
    line = next(l for l in section.splitlines() if l.startswith("- In this library:"))
    assert "from v1.688 `delegation_follow` reads those records back, per task and parent" in line
    assert "flags a share under a task's `min_delegation_follow`" in line
    assert line.endswith("The changes: that report on the command line, and a cap on delegation depth.")
    assert "nothing yet reads those records back" not in line
