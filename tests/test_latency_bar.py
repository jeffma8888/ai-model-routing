"""DESIGN 4.2, 5.1, 5.2, 13.3 and 13.4 v1.628 (row LAT1b): a task's latency bar in `select`.

`Task.max_p95_ms` rules out, after the policy rules 5b to 5d and before rule 6, a route whose p95 on
the call's key is above it (rule 5e, `too_slow`), and with `latency_unknown="deny"` one whose time is
unknown (rule 5f, `latency_unknown`). A time is known once the key holds `min_samples` times, so one
slow outlier among a few does not rule a route out. A cascade and a procedure are judged on their own
key. Under a bar each candidate holds the p95 it was judged on and the decision its bar; with no bar
every decision on the shipped data keeps its v1.627 bytes (a sha256 pin). `decide_delegation`'s
delegate keeps the bar with and without a brief; from v1.631 its inline parent is held to the bar too
(13.4 rule 5, tests/test_latency_parent.py).
"""

import dataclasses
import json
import math

import pytest
from decision_hash import candidate_fields, decision_sha256

import model_routing
from model_routing import (DATA_DIR, Cascade, Model, NoModelClearsBar, Priors, Procedure, ProcedureResult,
                           Registry, Router, Stats, Task, load_tasks)

TOO_SLOW, LATENCY_UNKNOWN = "too_slow", "latency_unknown"  # 5.1 v1.628
N = 30  # each test task's min_samples
BAR = 500.0
CHEAP, MID, PRICEY = "a/cheap", "b/mid", "c/pricey"


def _fn(run):
    return ProcedureResult(output="ok", tool_cost_usd=0.0)


def registry():
    return Registry([Model(CHEAP, "a", 0.1, 0.2, 100_000), Model(MID, "b", 0.5, 1.0, 100_000),
                     Model(PRICEY, "c", 1.0, 2.0, 100_000)])


def times(fast=N, slow=0, fast_ms=100.0, slow_ms=900.0):
    return [fast_ms] * fast + [slow_ms] * slow


def router(stats, **fields):
    task = Task("t", **{"bar": 0.8, "min_samples": N, "max_p95_ms": BAR, **fields})
    return Router(registry(), {"t": task}, stats)


def by_id(decision_or_candidates):
    cands = getattr(decision_or_candidates, "candidates", decision_or_candidates)
    return {c.model_id: c for c in cands}


def measured(slow_cheap=2, pricey_times=None):
    """Three routes at 30 of 30: the cheap one with ``slow_cheap`` of its 30 times at 900 ms."""
    stats = Stats()
    stats.add("t", CHEAP, N, N, latencies_ms=times(N - slow_cheap, slow_cheap))
    stats.add("t", MID, N, N, latencies_ms=times())
    if pricey_times is None:
        stats.add("t", PRICEY, N, N)
    else:
        stats.add("t", PRICEY, N, N, latencies_ms=pricey_times)
    return stats


# --- 4.2 the fields --------------------------------------------------------------------------

def test_the_two_fields_are_the_last_with_their_defaults():
    names = [f.name for f in dataclasses.fields(Task)]
    assert names[-3:] == ["shadow_route", "max_p95_ms", "latency_unknown"]
    task = Task("t", 0.5)
    assert task.max_p95_ms is None and task.latency_unknown == "allow"
    assert Task("t", 0.5, max_p95_ms=250, latency_unknown="deny").max_p95_ms == 250


@pytest.mark.parametrize("value", [0, 0.0, -1.0, True, False, math.nan, math.inf, -math.inf, 10 ** 400,
                                   "500", [500]])  # 10 ** 400 overflows a float
def test_a_bad_bar_is_a_value_error_naming_the_task(value):
    with pytest.raises(ValueError, match="'t'.*max_p95_ms"):
        Task("t", 0.5, max_p95_ms=value)


@pytest.mark.parametrize("value", ["Allow", "", "block", None, 1, True])
def test_a_bad_latency_unknown_is_a_value_error_naming_the_task(value):
    with pytest.raises(ValueError, match="'t'.*latency_unknown"):
        Task("t", 0.5, latency_unknown=value)


def test_load_tasks_reads_both_and_a_row_without_them_gets_the_defaults(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"tasks": [
        {"name": "a", "bar": 0.5, "max_p95_ms": 250, "latency_unknown": "deny"},
        {"name": "b", "bar": 0.5, "max_p95_ms": None},
        {"name": "c", "bar": 0.5}]}), encoding="utf-8")
    tasks = load_tasks(path)
    assert (tasks["a"].max_p95_ms, tasks["a"].latency_unknown) == (250, "deny")
    assert (tasks["b"].max_p95_ms, tasks["b"].latency_unknown) == (None, "allow")
    assert tasks["c"] == Task("c", 0.5)
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "latency_unknown": "never"}]}),
                    encoding="utf-8")
    with pytest.raises(ValueError, match="latency_unknown"):
        load_tasks(path)


def test_the_demo_tasks_file_holds_each_key_only_off_its_default():
    from model_routing.demo import _tasks_json
    assert "max_p95_ms" not in _tasks_json(Task("t", 0.5)) and "latency_unknown" not in _tasks_json(Task("t", 0.5))
    row = json.loads(_tasks_json(Task("t", 0.5, max_p95_ms=250.0, latency_unknown="deny")))["tasks"][0]
    assert (row["max_p95_ms"], row["latency_unknown"]) == (250.0, "deny")


# --- 5.1 the codes, the candidate's time, the decision's bar ------------------------------------

def test_the_codes_are_exported_after_policy_and_the_new_fields_are_last():
    assert (model_routing.TOO_SLOW, model_routing.LATENCY_UNKNOWN) == (TOO_SLOW, LATENCY_UNKNOWN)
    names = model_routing.__all__
    at = names.index("Policy")
    assert names[at + 1:at + 3] == ["TOO_SLOW", "LATENCY_UNKNOWN"]
    assert [f.name for f in dataclasses.fields(model_routing.Candidate)][-1] == "p95_latency_ms"
    assert [f.name for f in dataclasses.fields(model_routing.RouteDecision)][-1] == "max_p95_ms"


# --- 5.2 rules 5e and 5f -------------------------------------------------------------------------

def test_the_cheaper_route_is_too_slow_so_the_other_is_picked_and_its_dict_holds_the_reason_and_p95():
    decision = router(measured()).select("t")
    assert decision.primary == MID and CHEAP not in decision.fallbacks
    slow = by_id(decision)[CHEAP]
    assert (slow.reason, slow.eligible, slow.passes, slow.p95_latency_ms) == (TOO_SLOW, False, False, 900.0)
    data = decision.to_dict()
    assert list(data)[-2:] == ["max_p95_ms", "candidates"] and data["max_p95_ms"] == BAR
    cands = {c["model_id"]: c for c in data["candidates"]}
    assert cands[CHEAP]["reason"] == TOO_SLOW and cands[CHEAP]["p95_latency_ms"] == 900.0
    assert list(cands[CHEAP])[-1] == "p95_latency_ms" and cands[MID]["p95_latency_ms"] == 100.0
    assert cands[PRICEY]["p95_latency_ms"] is None and cands[PRICEY]["reason"] == "passes"
    assert decision.max_p95_ms == BAR


def test_one_slow_outlier_in_thirty_and_a_p95_at_the_bar_do_not_rule_a_route_out():
    # nearest rank: the p95 of 30 times is the 29th, so one slow time is not the p95
    decision = router(measured(slow_cheap=1)).select("t")
    assert decision.primary == CHEAP and by_id(decision)[CHEAP].p95_latency_ms == 100.0
    at_bar = Stats()
    at_bar.add("t", CHEAP, N, N, latencies_ms=times(fast_ms=BAR))
    at_bar.add("t", MID, N, N, latencies_ms=times())
    decision = router(at_bar).select("t")
    assert decision.primary == CHEAP and by_id(decision)[CHEAP].reason == "passes"


@pytest.mark.parametrize("count, out", [(19, True), (20, False)])
def test_one_slow_time_rules_a_route_out_at_a_min_samples_under_20_and_not_at_20(count, out):
    # review iter-481 should-fix 1: by nearest rank the p95 of 19 or fewer times is their slowest
    stats = Stats()
    stats.add("t", CHEAP, count, count, latencies_ms=times(fast=count - 1, slow=1))
    stats.add("t", MID, count, count, latencies_ms=times(fast=count))
    decision = router(stats, min_samples=count, bar=0.5).select("t")
    assert (by_id(decision)[CHEAP].reason == TOO_SLOW) is out
    assert decision.primary == (MID if out else CHEAP)


def test_fewer_times_than_min_samples_is_an_unknown_time_however_slow():
    stats = measured(slow_cheap=0, pricey_times=None)
    few = Stats()
    few.add("t", CHEAP, N, N, latencies_ms=times(fast=0, slow=N - 1))
    few.add("t", MID, N, N, latencies_ms=times())
    decision = router(few).select("t")
    assert decision.primary == CHEAP and by_id(decision)[CHEAP].p95_latency_ms is None
    denied = by_id(router(few, latency_unknown="deny").select("t"))
    assert denied[CHEAP].reason == LATENCY_UNKNOWN and not denied[CHEAP].eligible
    assert denied[PRICEY].reason == LATENCY_UNKNOWN and denied[MID].reason == "passes"
    assert by_id(router(stats).select("t"))[PRICEY].reason == "passes"


def test_the_bar_comes_after_the_task_and_policy_rules_and_before_the_counts():
    stats = Stats()
    stats.add("t", CHEAP, 10, N, latencies_ms=times(fast=0, slow=N))   # below the bar and slow
    stats.add("t", MID, N, N, latencies_ms=times(fast=0, slow=N))      # excluded and slow
    stats.add("t", PRICEY, N, N, latencies_ms=times(fast=0, slow=N))   # outside the policy and slow
    policy = model_routing.Policy(allowed_families=("a", "b"))
    with pytest.raises(NoModelClearsBar) as error:
        router(stats).select("t", exclude_models=(MID,), policy=policy)
    got = {c.model_id: (c.reason, c.p95_latency_ms) for c in error.value.candidates}
    assert got == {CHEAP: (TOO_SLOW, 900.0), MID: ("excluded_model", 900.0), PRICEY: ("policy_excluded", 900.0)}


def test_a_cascade_and_a_procedure_are_judged_on_their_own_key():
    cascade = Cascade(CHEAP, MID, "low")
    proc = Procedure("p", "1", _fn, max_model_calls=1, max_tool_calls=0, model=CHEAP)
    stats = Stats()
    stats.add("t", CHEAP, N, N, latencies_ms=times(fast=0, slow=N))     # the cheap leg is slow
    stats.add("t", MID, N, N, latencies_ms=times())
    stats.add("t", PRICEY, N, N, latencies_ms=times())
    stats.add("t", cascade.id, N, N, escalated=3, latencies_ms=times())  # the cascade is not
    stats.add("t", proc.id, N, N, cost_usd=0.0, latencies_ms=times(fast=0, slow=N))
    r = router(stats, cascades=(cascade,))
    got = by_id(r.select("t", cascades=True, procedures=(proc,)))
    assert (got[cascade.id].reason, got[cascade.id].p95_latency_ms) == ("passes", 100.0)
    assert (got[proc.id].reason, got[proc.id].p95_latency_ms) == (TOO_SLOW, 900.0)
    assert got[CHEAP].reason == TOO_SLOW
    untimed = Stats()
    for key in (CHEAP, MID, PRICEY, cascade.id):
        untimed.add("t", key, N, N, **({"escalated": 3} if ">" in key else {}))
    with pytest.raises(NoModelClearsBar) as error:
        router(untimed, cascades=(cascade,), latency_unknown="deny").select("t", cascades=True)
    assert {c.model_id: c.reason for c in error.value.candidates}[cascade.id] == LATENCY_UNKNOWN


def test_a_slice_reads_its_own_keys_times_and_its_own_min_samples():
    task = Task("t", 0.8, min_samples=N, max_p95_ms=BAR, slices={"deep": {"min_samples": 5, "bar": 0.5}})
    stats = measured(slow_cheap=0)
    stats.add("t@deep", CHEAP, 5, 5, latencies_ms=times(fast=0, slow=5))
    stats.add("t@deep", MID, 5, 5, latencies_ms=times(fast=5))
    r = Router(registry(), {"t": task}, stats)
    assert r.select("t").primary == CHEAP
    deep = r.select("t", slice="deep")
    assert deep.primary == MID and by_id(deep)[CHEAP].reason == TOO_SLOW
    assert by_id(deep)[CHEAP].p95_latency_ms == 900.0 and deep.to_dict()["max_p95_ms"] == BAR


def test_best_available_never_picks_a_route_the_bar_rules_out_and_deny_keeps_priors_off():
    stats = Stats()
    stats.add("t", CHEAP, 25, N, latencies_ms=times(fast=0, slow=N))   # best, but too slow
    stats.add("t", MID, 20, N, latencies_ms=times())
    decision = router(stats, on_no_model="best_available").select("t")
    assert decision.below_bar and decision.primary == MID and CHEAP not in decision.fallbacks
    priors = Priors({"cat": {"scores": {CHEAP: 0.9, MID: 0.8, PRICEY: 0.7}}})
    task = Task("t", 0.8, min_samples=N, max_p95_ms=BAR, on_no_model="best_available", prior_category="cat")
    allow = Router(registry(), {"t": task}, Stats(), priors).select("t")
    assert allow.basis == "prior" and allow.primary == CHEAP
    deny = Router(registry(), {"t": dataclasses.replace(task, latency_unknown="deny")}, Stats(), priors)
    with pytest.raises(NoModelClearsBar) as error:
        deny.select("t")
    assert {c.reason for c in error.value.candidates} == {LATENCY_UNKNOWN}


def test_every_route_too_slow_raises_with_the_times_in_the_candidates():
    stats = Stats()
    for model_id in (CHEAP, MID, PRICEY):
        stats.add("t", model_id, N, N, latencies_ms=times(fast=0, slow=N))
    with pytest.raises(NoModelClearsBar) as error:
        router(stats).select("t")
    assert {(c.reason, c.p95_latency_ms) for c in error.value.candidates} == {(TOO_SLOW, 900.0)}


def test_with_no_bar_no_key_is_written_and_deny_changes_nothing():
    stats = measured()
    for fields in ({"max_p95_ms": None}, {"max_p95_ms": None, "latency_unknown": "deny"}):
        decision = router(stats, **fields).select("t")
        data = decision.to_dict()
        assert decision.primary == CHEAP and "max_p95_ms" not in data
        assert all("p95_latency_ms" not in c for c in data["candidates"])
        assert {c.p95_latency_ms for c in decision.candidates} == {None}


# --- 13.3 and 13.4: the delegate keeps the bar, and from v1.631 the parent is held to it ---------

def _delegation_router():
    stats = Stats()
    tokens = {"input_tokens": 1000 * N, "output_tokens": 200 * N, "token_trials": N}
    stats.add("t", CHEAP, N, N, latencies_ms=times(fast=0, slow=N), **tokens)  # measured slow
    stats.add("t", MID, N, N, latencies_ms=times(), **tokens)
    stats.add("t", PRICEY, N, N, latencies_ms=times(), **tokens)
    return router(stats)


@pytest.mark.parametrize("work", [{"brief_tokens": 0}, {"brief_tokens": 400},
                                  {"brief_tokens": 400, "work_calls": 3}],
                         ids=["no brief", "brief", "brief, K = 3"])
def test_a_measured_slow_route_is_too_slow_in_the_delegate_with_and_without_a_brief(work):
    r = _delegation_router()
    decision = r.decide_delegation("t", PRICEY, context_tokens=20_000, result_tokens=300, **work)
    assert decision.route.primary == MID
    assert by_id(decision.route)[CHEAP].reason == TOO_SLOW
    assert by_id(decision.route)[CHEAP].p95_latency_ms == 900.0


def test_a_slow_parent_cannot_work_inline_from_v1_631():
    """Up to v1.630 this parent worked inline (13.4 v1.628); 13.4 rule 5 now blocks it (row LAT1d)."""
    decision = _delegation_router().decide_delegation("t", CHEAP, context_tokens=20_000, brief_tokens=400,
                                                      result_tokens=300)
    assert (decision.inline_allowed, decision.reason, decision.model) == (False, "parent_too_slow", MID)


# --- defaults: with no bar every decision on the shipped data keeps its v1.627 bytes -------------

# decision_sha256 of the 448 values below, computed on the v1.627 tree (3e03c25), where no task has a bar
V1_627_DIGEST = "3327786ae6b71285f7e94f5c47e194a5ce78be9a9b7d7b05c4db57ed748a4d41"


def _shipped(**task_fields):
    """Every example task, both flavors: three select shapes, a prior pick, and every shipped model as
    the delegating parent at one work call and at three, on stats with times on two models in three."""
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
            stats.add(name, model_id, 90 + i % 10, 100 + 100 * (i % 3), **extra)
        stats.add(name, proc.id, 97, 100, cost_usd=0.001, latencies_ms=[3000.0] * 100)
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


@pytest.mark.parametrize("fields", [{}, {"max_p95_ms": None}, {"latency_unknown": "deny"}],
                         ids=["defaults", "None", "deny without a bar"])
def test_with_no_bar_every_v1_627_decision_on_the_shipped_data_keeps_its_bytes(fields):
    out = _shipped(**fields)
    assert len(out) == 448
    assert {d.get("mode", "select") for d in out} == {"inline", "delegate", "select"}
    assert any("error" in d for d in out)
    assert decision_sha256(out) == V1_627_DIGEST
