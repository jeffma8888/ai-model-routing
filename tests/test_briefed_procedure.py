"""DESIGN 13.3 v1.627 (row BRIEF1, review iter-478 should-fix 3): a brief keeps a procedure key.

`decide_delegation` with a brief (B > 0) on a task whose stats hold token totals runs its
delegate's `select` at one work call on a private copy of the task's stats, B added to each input
total (v1.33). From v1.627 that copy holds each procedure key (4.3 v1.577) with its counts and
summed `cost_usd` as they are, so a procedure trial on the task no longer makes `Stats.add` raise,
and the decision is the one the same stats without that key give, since that `select` is passed
no procedures. The router built for K > 1 reads the router's stats itself and is unchanged. With
no procedure key every decision keeps its v1.626 bytes (the 960 decisions on the shipped data that
tests/test_policy_delegation.py pins, which keep that digest here with a procedure trial on every
task too).
"""

import itertools
from pathlib import Path

import pytest

from decision_hash import candidate_fields, decision_sha256
from model_routing import (DATA_DIR, Model, NoModelClearsBar, Registry, Router, Stats, Task,
                           load_tasks)
from model_routing import delegation
from model_routing.router import FLAVORS

ROOT = Path(__file__).resolve().parents[1]
MODELS = [Model("x/small", "x", 0.5, 1.0, 100_000), Model("x/mid", "x", 1.0, 2.0, 100_000),
          Model("y/big", "y", 2.0, 4.0, 100_000)]
WORK = {"context_tokens": 2000, "brief_tokens": 300, "result_tokens": 100}
# (procedure ID, successes, trials, summed cost): with a model, without one, and with no trials
PROCEDURES = [("proc:lookup@1+x/small", 50, 50, 0.25), ("proc:rules@2", 40, 45, 0.0),
              ("proc:lookup@1", 0, 0, 0)]


def _stats(procedure=None):
    stats = Stats()
    stats.add("t", "x/small", 95, 100, input_tokens=120_000, output_tokens=21_000)
    stats.add("t", "x/mid", 98, 100, input_tokens=90_000, output_tokens=15_000, token_trials=80)
    stats.add("t", "y/big", 99, 100)
    stats.add("other", "x/small", 9, 10, input_tokens=5_000, output_tokens=900)
    if procedure is not None:
        model_id, successes, trials, cost = procedure
        stats.add("t", model_id, successes, trials, cost_usd=cost)
    return stats


def _router(stats):
    task = Task(name="t", bar=0.8, min_samples=30, expected_input_tokens=1000,
                expected_output_tokens=200)
    return Router(Registry(MODELS), {"t": task}, stats)


@pytest.mark.parametrize("procedure", PROCEDURES, ids=[p[0] + f" {p[2]} trials" for p in PROCEDURES])
@pytest.mark.parametrize("flavor", FLAVORS)
@pytest.mark.parametrize("parent", [m.id for m in MODELS])
@pytest.mark.parametrize("separate", [True, False], ids=["separate", "folded"])
def test_a_procedure_trial_on_the_task_leaves_the_decision_the_stats_without_it_give(
        procedure, flavor, parent, separate):
    work = dict(WORK, inline_separate_call=separate)
    want = _router(_stats()).decide_delegation("t", parent, flavor, **work).to_dict()
    got = _router(_stats(procedure)).decide_delegation("t", parent, flavor, **work).to_dict()
    assert got == want


def test_both_paths_are_reached_with_a_procedure_trial_on_the_task():
    seen = set()
    for flavor, parent, separate in itertools.product(FLAVORS, [m.id for m in MODELS], [True, False]):
        decision = _router(_stats(PROCEDURES[0])).decide_delegation(
            "t", parent, flavor, **WORK, inline_separate_call=separate)
        seen.add(decision.mode)
    assert seen == {"inline", "delegate"}


def test_the_briefed_copy_keeps_each_procedure_key_as_it_is():
    stats = _stats()
    stats.add("t", "proc:sum@1", 1, 1, cost_usd=0.1, latencies_ms=[40.0])
    stats.add("t", "proc:sum@1", 1, 2, cost_usd=0.2)  # summed: 0.30000000000000004
    stats.add("t", "proc:none@1", 0, 0, cost_usd=0)
    stats.add("other", "proc:sum@1", 3, 3, cost_usd=0.5)
    stats.add("t", "z/cached", 5, 5, input_tokens=5_000, output_tokens=500,
              cached_input_tokens=2_000, cached_trials=5)
    copy = delegation._briefed_stats(stats, "t", 300)
    assert copy is not stats
    assert copy.get("t", "proc:sum@1") == (2, 3)
    assert copy.cost("t", "proc:sum@1") == 0.1 + 0.2
    assert copy.mean_cost("t", "proc:sum@1") == stats.mean_cost("t", "proc:sum@1")
    assert copy.tokens("t", "proc:sum@1") == (0, 0, 0)
    assert copy.get("t", "proc:none@1") == (0, 0) and copy.mean_cost("t", "proc:none@1") is None
    assert copy.cost("t", "proc:none@1") == 0.0
    # the models' input totals gain B per token trial, as v1.33 states; other tasks stay out
    assert copy.tokens("t", "x/small") == (120_000 + 300 * 100, 21_000, 100)
    assert copy.tokens("t", "x/mid") == (90_000 + 300 * 80, 15_000, 80)
    assert copy.get("t", "y/big") == (99, 100) and copy.tokens("t", "y/big") == (0, 0, 0)
    # from 13.3 v1.628 (row LAT1b, review iter-479 nit 2) the copy keeps the times (4.3 v1.626) as
    # they are, while it still holds no cache counts (v1.588)
    assert stats.latencies("t", "proc:sum@1") == (40.0,) and copy.latencies("t", "proc:sum@1") == (40.0,)
    assert stats.cache_tokens("t", "z/cached") == (2_000, 5, 0, 0)
    assert copy.cache_tokens("t", "z/cached") == (0, 0, 0, 0)
    assert copy.tokens("t", "z/cached") == (5_000 + 300 * 5, 500, 5)
    assert {key for key, _ in copy.items()} == {
        ("t", "x/small"), ("t", "x/mid"), ("t", "y/big"), ("t", "z/cached"), ("t", "proc:sum@1"),
        ("t", "proc:none@1")}


def test_the_router_stats_save_the_same_bytes_after_the_call(tmp_path):
    stats = _stats(PROCEDURES[0])
    before, after = tmp_path / "before.json", tmp_path / "after.json"
    stats.save(before)
    _router(stats).decide_delegation("t", "y/big", **WORK)
    stats.save(after)
    assert after.read_bytes() == before.read_bytes()


@pytest.mark.parametrize("flavor", FLAVORS)
def test_k_work_calls_give_the_same_decision_with_and_without_a_procedure_trial(flavor):
    work = dict(WORK, work_calls=3)
    want = _router(_stats()).decide_delegation("t", "y/big", flavor, **work).to_dict()
    assert _router(_stats(PROCEDURES[0])).decide_delegation("t", "y/big", flavor, **work).to_dict() == want


# decision_sha256 of the 960 decisions that tests/test_policy_delegation.py pins (computed there on
# a `git archive b20bc4b` copy, v1.623; v1.624 to v1.626 kept those bytes), here with a procedure
# trial on every example task as well
V1_623_DIGEST = "88298845c3e9beae4bbbe87fe24773ae8a7b49ad92045f4bb92c9fa9d24cefd2"


def _decisions_with_a_procedure_trial():
    """tests/test_policy_delegation.py's 960 decisions, a procedure key added on every task."""
    registry = Registry.load(DATA_DIR / "models.json")
    ids = [m.id for m in registry.models]
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    stats = Stats()
    for name in tasks:
        for i, model_id in enumerate(ids):
            tokens = {}
            if i % 2:  # half the models with measured sizes, so the briefed stats are used
                tokens = {"input_tokens": 900 * (i + 1) * 100, "output_tokens": 150 * (i + 1) * 100,
                          "token_trials": 100}
            stats.add(name, model_id, 90 + i % 10, 100 + 100 * (i % 3), **tokens)
        stats.add(name, f"proc:lookup@1+{ids[0]}", 60, 60, cost_usd=0.012)
    r = Router(registry, tasks, stats)
    shapes = ({}, {"work_calls": 3}, {"inline_separate_call": False, "cached_read_ratio": 0.5},
              {"generator_model": ids[4], "exclude_models": (ids[2],)}, {"context_tokens": 600_000})
    out = []
    for name in tasks:
        for flavor in FLAVORS:
            for parent in ids:
                for shape in shapes:
                    work = {"context_tokens": 20_000, "brief_tokens": 400, "result_tokens": 300, **shape}
                    try:
                        got = r.decide_delegation(name, parent, flavor, **work).to_dict()
                    except NoModelClearsBar as error:
                        got = {"error": str(error),
                               "candidates": [candidate_fields(c) for c in error.candidates]}
                    out.append(got)
    return out


def test_a_procedure_trial_on_every_task_keeps_the_960_shipped_decisions():
    out = _decisions_with_a_procedure_trial()
    assert len(out) == 960
    assert {d.get("mode", "error") for d in out} == {"inline", "delegate", "error"}
    assert "parent_context_full" in {d["reason"] for d in out if "reason" in d}  # review iter-479 nit 1
    assert decision_sha256(out) == V1_623_DIGEST


def test_the_builder_matches_the_policy_test_one_but_for_the_procedure_line():
    """The decisions above are tests/test_policy_delegation.py's, so its pin covers them."""
    here = (ROOT / "tests" / "test_briefed_procedure.py").read_text(encoding="utf-8")
    there = (ROOT / "tests" / "test_policy_delegation.py").read_text(encoding="utf-8")
    def body(text, start):
        block = text[text.index(start):]
        block = block[block.index("    registry = "):block.index("    return out\n")]
        return [line for line in block.splitlines() if "proc:" not in line]
    theirs = [line.replace(", **extra)", ")") for line in body(there, "def _decisions(extra)")]
    assert len(theirs) > 20
    assert body(here, "def _decisions_with_a_procedure_trial") == theirs


def test_design_and_changelog_state_v1_627():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert "- v1.627 procedure keys (row BRIEF1, review iter-478 should-fix 3):" in design
    assert "  - Tests (tests/test_briefed_procedure.py):" in design
    [line] = [x for x in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
              if x.startswith("- v1.627 (")]
    assert line.startswith("- v1.627 (2026-11-24): spec, code and tests (13.3, row BRIEF1, "
                           "review iter-478 should-fix 3).")
