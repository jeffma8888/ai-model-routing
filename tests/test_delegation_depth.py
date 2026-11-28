"""DESIGN 4.2, 7, 13.1, 13.5 and 13.6 v1.691 (row DEL3): a cap on how deep hand-offs go.

`Task.max_delegation_depth` (None, no cap) and `decide_delegation(..., depth=None)`: at a depth at or past an
enabled cap (None counting as 0) the decision is inline, reason `depth_cap`, when inline is allowed and the
parent clears the bar, and otherwise `NoModelClearsBar` naming `depth_cap`. The decision keeps its `depth`
(`to_dict()` only when it is not None), and `.call_delegated` tags each record `depth` with the depth its
sub-agent runs at, `decision.depth + 1`. The plain scenario is tests/test_record_keys.py's router, the pair
one tests/test_call_delegated_pair.py's.
"""

import dataclasses
import inspect
import itertools
import json
import math
from pathlib import Path

import pytest

import model_routing
from model_routing import DelegationDecision, Executor, FakeProvider, Monitor, NoModelClearsBar, Task, load_tasks
from model_routing import delegation as dl
from model_routing.delegation import decide_delegation
from model_routing.demo import _tasks_json
from test_record_keys import COUNTS, MODELS, model, ok, router
import test_call_delegated_pair as pair_case

ROOT = Path(__file__).resolve().parents[1]
FIELDS = ["task", "flavor", "parent", "mode", "model", "reason", "below_bar", "inline_allowed", "inline_cost_usd",
          "delegate_cost_usd", "parent_quality_lb", "delegate_quality_lb", "route"]
# x/big clears the bar and costs more inline over its 50,000-token context: uncapped, it hands the work off
CHEAPER = dict(context_tokens=50_000, brief_tokens=1000, result_tokens=1000)
# y/cheap is under the bar: uncapped, its work goes to a model that clears it (tests/test_record_mode.py)
BELOW = dict(context_tokens=2000, brief_tokens=1000, result_tokens=1000, inline_separate_call=False)
WEAK = MODELS + [model("y/cheap", 0.1, family="y")]
WEAK_COUNTS = dict(COUNTS, **{"y/cheap": 60})


def clears(**task):
    return router(**task)


def weak(**task):
    return router(models=WEAK, counts=WEAK_COUNTS, **task)


def strip(decision):
    """The decision as v1.690 holds it: every field but `depth`."""
    return dataclasses.replace(decision, depth=None)


# --- 13.1 v1.691: the keyword ---------------------------------------------------------------------

def test_depth_is_the_last_keyword_of_the_function_and_the_method_defaulting_to_none():
    for fn in (decide_delegation, model_routing.Router.decide_delegation):
        params = inspect.signature(fn).parameters
        assert list(params)[-1] == "depth"
        assert params["depth"].default is None and params["depth"].kind is inspect.Parameter.KEYWORD_ONLY


@pytest.mark.parametrize("value", [-1, True, False, 1.0, "1", [1], math.nan])
def test_a_bad_depth_is_a_value_error_naming_depth(value):
    with pytest.raises(ValueError, match="depth"):
        clears().decide_delegation("t", "x/big", depth=value, **CHEAPER)


def test_depth_is_checked_after_the_pair_keywords_and_before_the_parent_lookup():
    with pytest.raises(ValueError, match="delegate_roots and delegate_leaves"):
        clears().decide_delegation("t", "x/big", depth=-1, delegate_roots=["x/big"], **CHEAPER)
    with pytest.raises(ValueError, match="depth"):
        clears().decide_delegation("t", "nope/none", depth=-1, **CHEAPER)
    with pytest.raises(KeyError):
        clears().decide_delegation("t", "nope/none", depth=0, **CHEAPER)


# --- 13.5 v1.691: no cap, and under the cap ------------------------------------------------------

def test_with_no_cap_a_depth_changes_nothing_but_the_field():
    plain = clears().decide_delegation("t", "x/big", **CHEAPER)
    assert (plain.mode, plain.reason, plain.depth) == ("delegate", "delegate_cheaper", None)
    for depth in (0, 1, 7):
        deep = clears().decide_delegation("t", "x/big", depth=depth, **CHEAPER)
        assert deep.depth == depth and strip(deep) == plain
    assert clears().decide_delegation("t", "x/big", depth=None, **CHEAPER) == plain


@pytest.mark.parametrize("cap, depth", [(1, 0), (1, None), (2, 1), (5, 4)])
def test_under_the_cap_the_decision_is_the_uncapped_one(cap, depth):
    for route, parent, sizes in ((clears, "x/big", CHEAPER), (weak, "y/cheap", BELOW)):
        plain = route().decide_delegation("t", parent, **sizes)
        capped = route(max_delegation_depth=cap).decide_delegation("t", parent, depth=depth, **sizes)
        assert capped.mode == "delegate" and capped.depth == depth and strip(capped) == plain


# --- 13.5 v1.691: at the cap ---------------------------------------------------------------------

@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_at_the_cap_a_parent_that_clears_works_inline_with_depth_cap(flavor):
    plain = clears().decide_delegation("t", "x/big", flavor, **CHEAPER)
    # uncapped, cost_effective hands off (delegate_cheaper) and cost_blind keeps it (inline_as_good): at the
    # cap the reason is depth_cap whichever row would have decided
    assert (plain.mode, plain.reason) == {"cost_effective": ("delegate", "delegate_cheaper"),
                                          "cost_blind": ("inline", "inline_as_good")}[flavor]
    capped = clears(max_delegation_depth=1).decide_delegation("t", "x/big", flavor, depth=1, **CHEAPER)
    assert (capped.mode, capped.model, capped.reason, capped.below_bar) == ("inline", "x/big", "depth_cap", False)
    assert capped.reason == dl.DEPTH_CAP and capped.inline_allowed and capped.depth == 1
    # both paths' costs, bounds and the delegate's route as with no cap
    keep = ("inline_cost_usd", "delegate_cost_usd", "parent_quality_lb", "delegate_quality_lb", "route")
    assert {k: getattr(capped, k) for k in keep} == {k: getattr(plain, k) for k in keep}


def test_past_the_cap_and_at_a_cap_of_zero_with_no_depth_the_parent_works_inline():
    past = clears(max_delegation_depth=1).decide_delegation("t", "x/big", depth=3, **CHEAPER)
    zero = clears(max_delegation_depth=0).decide_delegation("t", "x/big", **CHEAPER)
    assert (past.mode, past.reason, past.depth) == ("inline", "depth_cap", 3)
    assert (zero.mode, zero.reason, zero.depth) == ("inline", "depth_cap", None)


@pytest.mark.parametrize("on_no_model", ["refuse", "best_available"])
def test_at_the_cap_a_parent_under_the_bar_is_refused_naming_depth_cap(on_no_model):
    plain = weak(on_no_model=on_no_model).decide_delegation("t", "y/cheap", **BELOW)
    assert (plain.mode, plain.reason) == ("delegate", "parent_below_bar")
    with pytest.raises(NoModelClearsBar, match="depth_cap") as caught:
        weak(on_no_model=on_no_model, max_delegation_depth=1).decide_delegation("t", "y/cheap", depth=1, **BELOW)
    assert caught.value.candidates == plain.route.candidates


def test_at_the_cap_a_parent_inline_is_blocked_for_is_refused_even_when_it_clears():
    full = dict(CHEAPER, context_tokens=99_000)  # 99,000 + 1,000 + 200 is over x/big's 100,000 window
    plain = clears().decide_delegation("t", "x/big", **full)
    assert (plain.mode, plain.reason, plain.inline_allowed) == ("delegate", "parent_context_full", False)
    with pytest.raises(NoModelClearsBar, match="depth_cap") as caught:
        clears(max_delegation_depth=1).decide_delegation("t", "x/big", depth=1, **full)
    assert caught.value.candidates == plain.route.candidates


def test_at_the_cap_with_no_route_the_refusal_carries_the_failed_selects_candidates():
    with pytest.raises(NoModelClearsBar) as uncapped:
        clears(exclude_families=("x",)).decide_delegation("t", "x/big", **CHEAPER)
    with pytest.raises(NoModelClearsBar, match="depth_cap") as caught:
        clears(exclude_families=("x",), max_delegation_depth=0).decide_delegation("t", "x/big", **CHEAPER)
    assert caught.value.candidates == uncapped.value.candidates


def test_a_pair_decision_at_the_cap_refuses_as_a_plain_one_does():
    rt = pair_case.router(solo=False)
    plain = pair_case.decide(rt)
    assert plain.mode == "delegate" and plain.reason == "parent_below_bar"
    rt.tasks["t"] = dataclasses.replace(rt.tasks["t"], max_delegation_depth=1)
    with pytest.raises(NoModelClearsBar, match="depth_cap") as caught:
        pair_case.decide(rt, depth=1)
    assert caught.value.candidates == plain.route.candidates
    assert strip(pair_case.decide(rt, depth=0)) == plain


# --- 13.6 v1.691: the field ------------------------------------------------------------------------

def test_the_decision_gains_a_last_depth_field_and_to_dict_holds_it_only_when_set():
    # v1.706 (row CACHE4a) adds `inline_cache_counts` after it, and v1.707 (row CACHE4b) `delegate_cache_counts`
    assert [f.name for f in dataclasses.fields(DelegationDecision)] == FIELDS + ["depth", "inline_cache_counts", "delegate_cache_counts"]
    plain = clears().decide_delegation("t", "x/big", **CHEAPER)
    assert list(plain.to_dict()) == FIELDS
    for depth in (0, 2):
        data = clears().decide_delegation("t", "x/big", depth=depth, **CHEAPER).to_dict()
        assert list(data) == FIELDS + ["depth"] and data["depth"] == depth
        assert {k: v for k, v in data.items() if k != "depth"} == plain.to_dict()
        assert json.loads(json.dumps(data)) == data
    built = DelegationDecision("t", "cost_blind", "x/big", "inline", "x/big", "only_parent_clears", False, True,
                               0.1, None, 0.9, None, None)
    assert built.depth is None and list(built.to_dict()) == FIELDS


def test_the_reason_code_is_a_module_constant_not_exported():
    assert dl.DEPTH_CAP == "depth_cap"
    assert "DEPTH_CAP" not in model_routing.__all__


# --- 4.2 v1.691: the task field -------------------------------------------------------------------

def test_the_task_field_follows_min_delegation_follow_with_its_default():
    names = [f.name for f in dataclasses.fields(Task)]
    # v1.692 (row CACHE2a): `min_cache_hit_rate` and `cache_miss_calls` follow it, tests/test_cache_miss.py
    assert names[names.index("min_delegation_follow"):][:2] == ["min_delegation_follow", "max_delegation_depth"]
    assert Task("t", 0.5).max_delegation_depth is None
    for value in (0, 1, 3):
        assert Task("t", 0.5, max_delegation_depth=value).max_delegation_depth == value


@pytest.mark.parametrize("value", [-1, True, False, 1.0, "1", [1], math.nan, math.inf])
def test_a_bad_cap_is_a_value_error_naming_the_task(value):
    with pytest.raises(ValueError, match="'t'.*max_delegation_depth"):
        Task("t", 0.5, max_delegation_depth=value)


def test_load_tasks_reads_the_cap_and_a_row_without_it_gets_none(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "max_delegation_depth": 1},
                                          {"name": "b", "bar": 0.5, "max_delegation_depth": None},
                                          {"name": "c", "bar": 0.5}]}), encoding="utf-8")
    loaded = load_tasks(path)
    assert [loaded[n].max_delegation_depth for n in "abc"] == [1, None, None]
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "max_delegation_depth": "1"}]}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="max_delegation_depth"):
        load_tasks(path)


def test_no_packaged_task_has_it_and_the_demo_tasks_file_holds_it_only_when_set():
    packaged = load_tasks(model_routing.DATA_DIR / "example_tasks.json")
    assert packaged and all(task.max_delegation_depth is None for task in packaged.values())
    assert "max_delegation_depth" not in _tasks_json(Task("t", 0.5))
    row = json.loads(_tasks_json(Task("t", 0.5, max_delegation_depth=2)))["tasks"][0]
    assert row["max_delegation_depth"] == 2


# --- 7 v1.691: the depth tag -----------------------------------------------------------------------

class Counted:
    """An executor on the plain scenario whose ``id_factory`` counts its calls."""

    def __init__(self, route):
        self.ids = 0
        ticks = itertools.count()
        self.monitor = Monitor()
        self.ex = Executor(route, FakeProvider({m.id: ok for m in WEAK}), monitor=self.monitor,
                           clock=lambda: float(next(ticks)), now=lambda: "2026-11-27T09:00:00Z",
                           id_factory=self.new_id)

    def new_id(self):
        self.ids += 1
        return f"call-{self.ids}"


BRIEF = [{"role": "user", "content": "the brief"}]


def test_a_decision_with_a_depth_tags_each_record_with_the_sub_agents_depth_last():
    for depth, tag in ((0, "1"), (1, "2"), (6, "7")):
        route = weak()
        decision = route.decide_delegation("t", "y/cheap", depth=depth, **BELOW)
        run = Counted(route)
        run.ex.call_delegated(decision, BRIEF, tags={"team": "a"})
        [record] = run.monitor.records
        assert record["tags"] == {"team": "a", "delegated": "true", "parent": "y/cheap", "depth": tag}
        assert list(record["tags"]) == ["team", "delegated", "parent", "depth"]


def test_a_decision_with_no_depth_writes_the_v1_690_record_and_passes_a_callers_depth_tag_on():
    route = weak()
    decision = route.decide_delegation("t", "y/cheap", **BELOW)
    plain, deep = Counted(route), Counted(route)
    plain.ex.call_delegated(decision, BRIEF, tags={"team": "a"})
    deep.ex.call_delegated(route.decide_delegation("t", "y/cheap", depth=0, **BELOW), BRIEF, tags={"team": "a"})
    [one], [two] = plain.monitor.records, deep.monitor.records
    assert one["tags"] == {"team": "a", "delegated": "true", "parent": "y/cheap"}
    assert {k: v for k, v in two.items() if k != "tags"} == {k: v for k, v in one.items() if k != "tags"}
    passed = Counted(route)
    passed.ex.call_delegated(decision, BRIEF, tags={"depth": "mine"})
    assert passed.monitor.records[0]["tags"] == {"depth": "mine", "delegated": "true", "parent": "y/cheap"}


def test_a_callers_depth_tag_beside_a_decisions_depth_is_refused_before_any_id():
    route = weak()
    run = Counted(route)
    decision = route.decide_delegation("t", "y/cheap", depth=1, **BELOW)
    with pytest.raises(ValueError, match="depth"):
        run.ex.call_delegated(decision, BRIEF, tags={"depth": "mine"})
    assert run.ids == 0 and run.monitor.records == []


@pytest.mark.parametrize("value", [-1, True, 1.0, "1"])
def test_a_bad_decision_depth_is_refused_before_any_id(value):
    route = weak()
    run = Counted(route)
    decision = dataclasses.replace(route.decide_delegation("t", "y/cheap", **BELOW), depth=value)
    with pytest.raises(ValueError, match="depth"):
        run.ex.call_delegated(decision, BRIEF)
    assert run.ids == 0 and run.monitor.records == []


def test_a_pair_decision_with_a_depth_tags_its_harness_record_too():
    d = pair_case.decide(depth=2)
    ex, monitor, ids = pair_case.executor()
    ex.call_delegated(d, pair_case.BRIEF, harness=pair_case.harness([]))
    [record] = monitor.records
    assert record["tags"] == {**pair_case.TAGS, "depth": "3"}


def test_a_mode_record_holds_no_depth():
    route = weak()
    run = Counted(route)
    rec = run.ex.record_mode(route.decide_delegation("t", "y/cheap", depth=1, **BELOW), "delegate", 100)
    assert "depth" not in rec and rec["tags"] == {}


# --- docs --------------------------------------------------------------------------------------------

def test_the_production_lessons_line_says_the_cap_ships():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    section = text[text.index("### Under-delegation is a failure you can measure"):]
    line = next(l for l in section.splitlines() if l.startswith("- In this library:"))
    assert line.endswith(" From v1.691 a task's `max_delegation_depth` caps how deep hand-offs go: at the cap "
                         "`decide_delegation(..., depth=N)` keeps the work inline when the parent clears the task's "
                         "bar and otherwise refuses with `depth_cap`, and `Executor.call_delegated` tags each record "
                         "with the depth its sub-agent runs at.")
    assert "The change" not in line


def test_design_states_v1_691_in_4_2_7_13_1_13_5_and_13_6_and_the_changelog_once():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for opening in ("- v1.691 delegation depth cap (row DEL3): `Task` gains a last field, after "
                    "`min_delegation_follow`",
                    "- v1.691 the depth in a hand-off's tags (row DEL3, 13.1 and 13.6 v1.691): ",
                    "- `depth` (v1.691, row DEL3, default None): ",
                    "- v1.691 the depth cap (row DEL3, 4.2 and 13.1 v1.691): before row 1, ",
                    "- v1.691 (row DEL3): `DelegationDecision` gains a last field, `depth: int | None = None`"):
        assert sum(line.startswith(opening) for line in design.splitlines()) == 1, opening
    assert "delegate_roots=None, delegate_leaves=None, depth=None) -> DelegationDecision`" in design
    [line] = [x for x in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if x.startswith("- v1.691 (")]
    assert line.startswith("- v1.691 (2026-11-27): spec, code and tests (4.2, 7, 13, row DEL3). ")
    assert len(line.encode("utf-8")) <= 600
