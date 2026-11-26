"""DESIGN 4.2, 5.1, 5.2, 13.3 and 13.4 v1.668 (row JUDGE2b, the second part of JUDGE2): the gate.

`Task.min_self_consistency` rules out, after rule 5f and before rule 6, a route whose share of rerun
items every rerun graded alike (4.3 v1.667) is under it (rule 5g, `inconsistent`) or unknown, its key
holding fewer than `min_samples` rerun items (rule 5h, `consistency_unknown`), whatever its Wilson bound.
A cascade and a procedure are judged on their own key, a slice on its own key and `min_samples`. The
delegate keeps the minimum with and without a brief, and the inline parent reads no share (row JUDGE2d).
With no minimum every decision on the shipped data keeps its v1.627 bytes, rerun counts or not.
"""

import dataclasses
import json
import math
from pathlib import Path

import pytest
from decision_hash import candidate_fields, decision_sha256

import model_routing
from model_routing import (DATA_DIR, Cascade, Model, NoModelClearsBar, Policy, Priors, Procedure,
                           ProcedureResult, Registry, Router, Stats, Task, calibrate_from_results, load_tasks)

ROOT = Path(__file__).resolve().parents[1]
INCONSISTENT, CONSISTENCY_UNKNOWN = "inconsistent", "consistency_unknown"  # 5.1 v1.668
N = 30  # each test task's min_samples
CHEAP, MID, PRICEY = "a/cheap", "b/mid", "c/pricey"


def _fn(run):
    return ProcedureResult(output="ok", tool_cost_usd=0.0)


def registry():
    return Registry([Model(CHEAP, "a", 0.1, 0.2, 100_000), Model(MID, "b", 0.5, 1.0, 100_000),
                     Model(PRICEY, "c", 1.0, 2.0, 100_000)])


def router(stats, **fields):
    task = Task("t", **{"bar": 0.8, "min_samples": N, "min_self_consistency": 0.98, **fields})
    return Router(registry(), {"t": task}, stats)


def by_id(decision_or_candidates):
    cands = getattr(decision_or_candidates, "candidates", decision_or_candidates)
    return {c.model_id: c for c in cands}


def judges(cheap_alike=27, **more):
    """Three judges at 30 of 30, each with 30 rerun items: the cheap one with ``cheap_alike`` alike."""
    stats = Stats()
    stats.add("t", CHEAP, N, N, rerun_items=N, consistent_items=cheap_alike, **more)
    stats.add("t", MID, N, N, rerun_items=N, consistent_items=N, **more)
    stats.add("t", PRICEY, N, N, rerun_items=N, consistent_items=N, **more)
    return stats


# --- 4.2 the field -------------------------------------------------------------------------------

def test_the_field_is_the_last_with_its_default():
    names = [f.name for f in dataclasses.fields(Task)]
    assert names[-2:] == ["latency_unknown", "min_self_consistency"]
    assert Task("t", 0.5).min_self_consistency is None
    for value in (0, 1, 0.0, 0.85, 1.0):
        assert Task("t", 0.5, min_self_consistency=value).min_self_consistency == value


@pytest.mark.parametrize("value", [-0.01, 1.01, -1, 2, True, False, math.nan, math.inf, -math.inf, 10 ** 400,
                                   "0.9", [0.9]])
def test_a_bad_minimum_is_a_value_error_naming_the_task(value):
    with pytest.raises(ValueError, match="'t'.*min_self_consistency"):
        Task("t", 0.5, min_self_consistency=value)


def test_load_tasks_reads_it_and_a_row_without_it_gets_none(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "min_self_consistency": 0.9},
                                          {"name": "b", "bar": 0.5, "min_self_consistency": None},
                                          {"name": "c", "bar": 0.5}]}), encoding="utf-8")
    tasks = load_tasks(path)
    assert [tasks[n].min_self_consistency for n in "abc"] == [0.9, None, None]
    assert tasks["c"] == Task("c", 0.5)
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "min_self_consistency": "high"}]}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="min_self_consistency"):
        load_tasks(path)


def test_no_packaged_task_sets_it_and_the_demo_tasks_file_holds_it_only_when_set():
    from model_routing.demo import _tasks_json
    assert all(t.min_self_consistency is None for t in load_tasks(DATA_DIR / "example_tasks.json").values())
    assert "min_self_consistency" not in _tasks_json(Task("t", 0.5))
    row = json.loads(_tasks_json(Task("t", 0.5, min_self_consistency=0.9)))["tasks"][0]
    assert row["min_self_consistency"] == 0.9 and list(row)[-1] == "min_self_consistency"


# --- 5.1 the codes -------------------------------------------------------------------------------

def test_the_codes_are_exported_after_latency_unknown():
    from model_routing import router as router_module
    assert (router_module.INCONSISTENT, router_module.CONSISTENCY_UNKNOWN) == (INCONSISTENT, CONSISTENCY_UNKNOWN)
    assert (getattr(model_routing, "INCONSISTENT"), getattr(model_routing, "CONSISTENCY_UNKNOWN")) \
        == (INCONSISTENT, CONSISTENCY_UNKNOWN)
    names = model_routing.__all__
    at = names.index("LATENCY_UNKNOWN")
    assert names[at + 1:at + 3] == ["INCONSISTENT", "CONSISTENCY_UNKNOWN"]
    assert [f.name for f in dataclasses.fields(model_routing.Candidate)][-1] == "p95_latency_ms"
    assert [f.name for f in dataclasses.fields(model_routing.RouteDecision)][-1] == "max_p95_ms"


# --- 5.2 rules 5g and 5h -------------------------------------------------------------------------

def test_an_accurate_judge_at_0_9_is_excluded_at_0_98_and_admitted_at_0_85():
    stats = judges(cheap_alike=27)
    assert stats.self_consistency("t", CHEAP) == 0.9
    strict = router(stats, min_self_consistency=0.98).select("t")
    cheap = by_id(strict)[CHEAP]
    assert strict.primary == MID and CHEAP not in strict.fallbacks
    assert (cheap.reason, cheap.eligible, cheap.passes) == (INCONSISTENT, False, False)
    assert cheap.quality_lb > 0.8  # whatever its Wilson bound
    data = strict.to_dict()
    assert {c["model_id"]: c["reason"] for c in data["candidates"]}[CHEAP] == INCONSISTENT
    assert all(list(c)[-1] == "reason" for c in data["candidates"])  # no new key
    loose = router(stats, min_self_consistency=0.85).select("t")
    assert loose.primary == CHEAP and by_id(loose)[CHEAP].reason == "passes"
    assert router(stats, min_self_consistency=0.9).select("t").primary == CHEAP  # at the minimum


def test_the_share_from_calibrated_reruns_drives_the_rule():
    rows = []
    for model_id, flips in ((CHEAP, 3), (MID, 0)):
        for j in range(N):
            for rerun in range(3):
                grade = "no" if j < flips and rerun == 2 else "yes"
                rows.append({"task": "t", "model": model_id, "item": f"i{j}", "rerun": rerun,
                             "prediction": grade, "gold": "yes"})
    stats = calibrate_from_results(rows)
    assert stats.get("t", CHEAP) == (N, N) and stats.consistency("t", CHEAP) == (N, N - 3)
    decision = router(stats).select("t")
    assert decision.primary == MID and by_id(decision)[CHEAP].reason == INCONSISTENT
    assert router(stats, min_self_consistency=0.85).select("t").primary == CHEAP


def test_fewer_rerun_items_than_min_samples_is_an_unknown_share_and_refused():
    stats = Stats()
    stats.add("t", CHEAP, N, N, rerun_items=N - 1, consistent_items=N - 1)  # all alike, one item short
    stats.add("t", MID, N, N, rerun_items=N, consistent_items=N)
    stats.add("t", PRICEY, N, N)                                              # no rerun data
    got = by_id(router(stats, min_self_consistency=0.0).select("t"))
    assert got[CHEAP].reason == CONSISTENCY_UNKNOWN and not got[CHEAP].eligible
    assert got[PRICEY].reason == CONSISTENCY_UNKNOWN and got[MID].reason == "passes"
    assert by_id(router(stats, min_self_consistency=None).select("t"))[CHEAP].reason == "passes"


def test_too_few_trials_is_consistency_unknown_not_insufficient_samples():
    stats = Stats()
    stats.add("t", CHEAP, 5, 5, rerun_items=5, consistent_items=5)
    stats.add("t", MID, N, N, rerun_items=N, consistent_items=N)
    got = by_id(router(stats).select("t"))
    assert got[CHEAP].reason == CONSISTENCY_UNKNOWN and got[PRICEY].reason == CONSISTENCY_UNKNOWN
    assert by_id(router(stats, min_self_consistency=None).select("t"))[CHEAP].reason == "insufficient_samples"


def test_the_minimum_comes_after_the_task_policy_and_latency_rules_and_before_the_counts():
    stats = Stats()
    slow = [900.0] * N
    stats.add("t", CHEAP, 10, N, rerun_items=N, consistent_items=N)                   # below the bar
    stats.add("t", MID, N, N, rerun_items=N, consistent_items=0)                      # excluded
    stats.add("t", PRICEY, N, N, rerun_items=N, consistent_items=0, latencies_ms=slow)  # slow
    with pytest.raises(NoModelClearsBar) as error:
        router(stats, max_p95_ms=500.0).select("t", exclude_models=(MID,))
    got = {c.model_id: c.reason for c in error.value.candidates}
    assert got == {CHEAP: "below_bar", MID: "excluded_model", PRICEY: "too_slow"}
    with pytest.raises(NoModelClearsBar) as error:
        router(stats).select("t", policy=Policy(allowed_families=("a", "c")))
    got = {c.model_id: c.reason for c in error.value.candidates}
    assert got == {CHEAP: "below_bar", MID: "policy_excluded", PRICEY: INCONSISTENT}


def test_a_cascade_and_a_procedure_are_judged_on_their_own_key():
    cascade = Cascade(CHEAP, MID, "low")
    proc = Procedure("p", "1", _fn, max_model_calls=1, max_tool_calls=0, model=CHEAP)
    stats = judges(cheap_alike=0)                                                  # the cheap leg repeats nothing
    stats.add("t", cascade.id, N, N, escalated=3, rerun_items=N, consistent_items=N)
    stats.add("t", proc.id, N, N, cost_usd=0.0, rerun_items=N, consistent_items=N - 6)
    got = by_id(router(stats, cascades=(cascade,)).select("t", cascades=True, procedures=(proc,)))
    assert got[cascade.id].reason == "passes" and got[proc.id].reason == INCONSISTENT
    assert got[CHEAP].reason == INCONSISTENT
    bare = judges(cheap_alike=N)
    bare.add("t", cascade.id, N, N, escalated=3)
    got = by_id(router(bare, cascades=(cascade,)).select("t", cascades=True))
    assert got[cascade.id].reason == CONSISTENCY_UNKNOWN


def test_a_slice_reads_its_own_keys_counts_and_its_own_min_samples():
    task = Task("t", 0.8, min_samples=N, min_self_consistency=0.98, slices={"deep": {"min_samples": 5, "bar": 0.5}})
    stats = judges(cheap_alike=N)
    stats.add("t@deep", CHEAP, 5, 5, rerun_items=5, consistent_items=4)
    stats.add("t@deep", MID, 5, 5, rerun_items=5, consistent_items=5)
    r = Router(registry(), {"t": task}, stats)
    assert r.select("t").primary == CHEAP
    deep = r.select("t", slice="deep")
    assert deep.primary == MID and by_id(deep)[CHEAP].reason == INCONSISTENT
    assert by_id(deep)[PRICEY].reason == CONSISTENCY_UNKNOWN


def test_best_available_never_picks_a_route_the_minimum_rules_out_and_priors_are_off():
    stats = Stats()
    stats.add("t", CHEAP, 28, N, rerun_items=N, consistent_items=20)   # best, but inconsistent
    stats.add("t", MID, 20, N, rerun_items=N, consistent_items=N)
    decision = router(stats, on_no_model="best_available").select("t")
    assert decision.below_bar and decision.primary == MID and CHEAP not in decision.fallbacks
    priors = Priors({"cat": {"scores": {CHEAP: 0.9, MID: 0.8, PRICEY: 0.7}}})
    task = Task("t", 0.8, min_samples=N, on_no_model="best_available", prior_category="cat")
    assert Router(registry(), {"t": task}, Stats(), priors).select("t").basis == "prior"
    gated = dataclasses.replace(task, min_self_consistency=0.5)
    with pytest.raises(NoModelClearsBar) as error:
        Router(registry(), {"t": gated}, Stats(), priors).select("t")
    assert {c.reason for c in error.value.candidates} == {CONSISTENCY_UNKNOWN}


def test_a_pin_of_an_inconsistent_route_is_refused_whatever_allow_below_bar_says():
    r = router(judges(cheap_alike=27))
    for allow in (False, True):
        with pytest.raises(NoModelClearsBar, match="'a/cheap' is inconsistent .*a pin keeps rules 1 to 5h"):
            r.select("t", pin_route=CHEAP, allow_below_bar=allow)
    assert r.select("t", pin_route=MID).basis == "pinned"
    unknown = Stats()
    unknown.add("t", CHEAP, N, N)
    for allow in (False, True):
        with pytest.raises(NoModelClearsBar, match="'a/cheap' is consistency_unknown .*a pin keeps rules 1 to 5h"):
            router(unknown).select("t", pin_route=CHEAP, allow_below_bar=allow)


# --- 13.3 and 13.4: the delegate keeps the minimum, the parent reads none (row JUDGE2d) ----------

def _delegation_router():
    tokens = {"input_tokens": 1000 * N, "output_tokens": 200 * N, "token_trials": N}
    return router(judges(cheap_alike=27, **tokens))


@pytest.mark.parametrize("work", [{"brief_tokens": 0}, {"brief_tokens": 400},
                                  {"brief_tokens": 400, "work_calls": 3}],
                         ids=["no brief", "brief", "brief, K = 3"])
def test_an_inconsistent_route_is_inconsistent_in_the_delegate_with_and_without_a_brief(work):
    r = _delegation_router()
    decision = r.decide_delegation("t", PRICEY, context_tokens=20_000, result_tokens=300, **work)
    assert decision.route.primary == MID and by_id(decision.route)[CHEAP].reason == INCONSISTENT


def test_the_briefed_copy_keeps_each_keys_rerun_counts():
    from model_routing.delegation import _briefed_stats
    r = _delegation_router()
    copy = _briefed_stats(r.stats, "t", 400)
    assert copy is not r.stats
    assert {m: copy.consistency("t", m) for m in (CHEAP, MID, PRICEY)} == \
        {CHEAP: (N, 27), MID: (N, N), PRICEY: (N, N)}


def test_an_inconsistent_parent_may_still_work_inline_until_row_judge2d():
    decision = _delegation_router().decide_delegation("t", CHEAP, context_tokens=20_000, brief_tokens=400,
                                                      result_tokens=300)
    assert decision.inline_allowed is True and decision.route.primary == MID
    assert by_id(decision.route)[CHEAP].reason == INCONSISTENT


# --- defaults: with no minimum every decision on the shipped data keeps its v1.627 bytes ---------

# tests/test_latency_bar.py's pin, computed on the v1.627 tree (3e03c25), with no rerun count in its stats
V1_627_DIGEST = "3327786ae6b71285f7e94f5c47e194a5ce78be9a9b7d7b05c4db57ed748a4d41"


def _shipped(**task_fields):
    """tests/test_latency_bar.py's 448 values, on stats that also hold rerun counts on most keys."""
    reg = Registry.load(DATA_DIR / "models.json")
    ids = [m.id for m in reg.models]
    tasks = {n: dataclasses.replace(t, **task_fields) for n, t in load_tasks(DATA_DIR / "example_tasks.json").items()}
    proc = Procedure("p", "1", _fn, max_model_calls=1, max_tool_calls=0, model=ids[0])
    stats = Stats()
    for name in tasks:
        for i, model_id in enumerate(ids):
            extra = {}
            if i % 2:
                extra = {"input_tokens": 900 * (i + 1) * 100, "output_tokens": 150 * (i + 1) * 100,
                         "token_trials": 100}
            if i % 3:
                extra["latencies_ms"] = [50.0 * (i + j % 7) for j in range(100)]
            if i % 4:
                extra.update(rerun_items=60, consistent_items=60 - 7 * (i % 5))
            stats.add(name, model_id, 90 + i % 10, 100 + 100 * (i % 3), **extra)
        stats.add(name, proc.id, 97, 100, cost_usd=0.001, latencies_ms=[3000.0] * 100,
                  rerun_items=100, consistent_items=50)
    r = Router(reg, tasks, stats)
    priors = Router(reg, {n: dataclasses.replace(t, on_no_model="best_available") for n, t in tasks.items()},
                    Stats(), Priors.load(DATA_DIR / "priors.json"))

    def attempt(call):
        try:
            return call().to_dict()
        except NoModelClearsBar as error:
            return {"error": str(error), "candidates": [candidate_fields(c) for c in error.candidates]}

    out = []
    for name in tasks:
        for flavor in ("cost_effective", "cost_blind"):
            for case in ({}, {"prompt_tokens": 150_000}, {"procedures": (proc,)}):
                out.append(attempt(lambda: r.select(name, flavor, **case)))
            out.append(attempt(lambda: priors.select(name, flavor)))
            for parent in ids:
                for shape in ({}, {"work_calls": 3}):
                    work = {"context_tokens": 20_000, "brief_tokens": 400, "result_tokens": 300, **shape}
                    out.append(attempt(lambda: r.decide_delegation(name, parent, flavor, **work)))
    return out


@pytest.mark.parametrize("fields", [{}, {"min_self_consistency": None}], ids=["default", "None"])
def test_with_no_minimum_every_v1_627_decision_on_the_shipped_data_keeps_its_bytes(fields):
    out = _shipped(**fields)
    assert len(out) == 448 and any("error" in d for d in out)
    assert decision_sha256(out) == V1_627_DIGEST


def test_a_minimum_changes_the_shipped_decisions():
    assert decision_sha256(_shipped(min_self_consistency=0.9)) != V1_627_DIGEST


# --- spec and the note ---------------------------------------------------------------------------

def _section(text, start, end):
    return text[text.index(start):text.index(end)]


def test_design_and_changelog_state_v1_668():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    parts = {"4.2": _section(design, "### 4.2 ", "### 4.3 "), "5.1": _section(design, "### 5.1 ", "### 5.2 "),
             "5.2": _section(design, "### 5.2 ", "### 5.3 "), "13.3": _section(design, "### 13.3 ", "### 13.4 "),
             "13.4": _section(design, "### 13.4 ", "### 13.5 ")}
    heads = {"4.2": "\n- v1.668 self-consistency minimum (row JUDGE2b, the second part of JUDGE2): `Task` gains a last field",
             "5.1": "\n- v1.668 self-consistency minimum (row JUDGE2b): `INCONSISTENT = \"inconsistent\"` and ",
             "5.2": "\n- v1.668 self-consistency minimum (row JUDGE2b, the second part of JUDGE2): on a call whose task",
             "13.3": "\n- v1.668 rerun counts (row JUDGE2b): beside what v1.663 lists, that private copy also holds",
             "13.4": "\n- v1.668 (row JUDGE2b): no rule reads the parent's self-consistency"}
    for name, head in heads.items():
        assert parts[name].count(head) == 1, name
    assert parts["4.2"].index("\n- v1.628 latency bar") < parts["4.2"].index("\n- v1.668 ")
    for words in ("5g, `inconsistent`, when the route's share is known and under the minimum",
                  "5h, `consistency_unknown`, when its share is unknown",
                  "known only when that key's `rerun_items` is at least `min_samples`",
                  "Unlike 5f, an unknown share has no `allow`", "a pin keeps rules 1 to 5h",
                  "With no minimum every decision is v1.667's bit for bit", "(row JUDGE2c, after row PROD1i)"):
        assert parts["5.2"].count(words) == 1, words
    assert design.split("\n")[2].startswith("Status: v1.668, 2026-11-26 (v1.668, spec, code and tests: ")
    [line] = [x for x in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
              if x.startswith("- v1.668 (")]
    assert line.startswith("- v1.668 (2026-11-26): spec, code and tests (4.2, 5.1, 5.2, 13.3, 13.4, row JUDGE2, "
                           "second part). ")
    assert len(line.encode("utf-8")) <= 600


def test_the_production_note_states_the_minimum_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    [line] = [x for x in text.splitlines() if x.startswith("- In this library: judge calls are its first case")]
    assert "The change: a self-consistency minimum" not in line
    assert line.endswith("its self-consistency. From v1.668 a task's `min_self_consistency` excludes a judge whose "
                         "share of rerun items graded alike is under it, or that has fewer rerun items than the "
                         "task's `min_samples`, whatever its bound.")
