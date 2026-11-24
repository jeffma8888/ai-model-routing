"""DESIGN 13 v1.624 (row POL1c): delegation keeps a tenant's policy.

`decide_delegation(..., policy=Policy(...))` runs the delegate's `select` (13.3) under the policy, on
the router it builds for one work call and on the one it builds for K, so neither the delegate nor
a fallback is a model the policy rules out; and a parent whose registry row fails 5.2 rules 5b to 5d
cannot work inline (13.4 rule 4), with `parent_policy_excluded`, `parent_region_unavailable` or
`parent_zdr_required`. `Executor.call_delegated` runs that route as decided. With no policy, or
`Policy()`, every decision keeps its v1.623 bytes on the shipped data, and no evidence or research
script passes a policy, so every delegation results file keeps its bytes.
"""

import dataclasses
import inspect
import itertools
import re
from pathlib import Path

import pytest

from decision_hash import candidate_fields, decision_sha256
from model_routing import (AllModelsFailed, Completion, DATA_DIR, Executor, FakeProvider, Model,
                           NoModelClearsBar, Policy, ProviderError, Registry, Router, Stats, Task,
                           load_tasks)
from model_routing import delegation
from model_routing.router import (CONTEXT_TOO_SMALL, FLAVORS, POLICY_EXCLUDED, REGION_UNAVAILABLE,
                                  ZDR_REQUIRED)

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "brief"}]
REGION = "eu-west"
TS = "2026-11-24T00:00:00Z"


def model(model_id, family, price, regions=(REGION,), zdr=True, window=100_000):
    return Model(model_id, family, price, 2 * price, window, regions=regions, zero_data_retention=zdr)


MODELS = [
    model("x/nowhere", "x", 0.05, regions=()),   # cheapest, states no region
    model("y/cheap", "y", 0.1),                   # the family the tenant disabled
    model("x/keep", "x", 0.3, zdr=None),          # states no retention rule
    model("x/small", "x", 0.5),
    model("x/mid", "x", 1.0),
    model("x/big", "x", 2.0),
    model("z/tiny", "z", 0.4, window=2_000),       # too small for the parent's context (13.4 rule 3)
]
# successes of 100: all pass the 0.8 bar; cost_blind orders x/big, x/keep, x/mid, y/cheap, ...
COUNTS = {"x/nowhere": 96, "y/cheap": 97, "x/keep": 99, "x/small": 95, "x/mid": 98, "x/big": 100,
          "z/tiny": 90}
TENANT = Policy(allowed_families=("x",), region=REGION, require_zdr=True)
RULED_OUT = {"x/nowhere": REGION_UNAVAILABLE, "y/cheap": POLICY_EXCLUDED, "x/keep": ZDR_REQUIRED}
ALLOWED = {"x/small", "x/mid", "x/big"}
# the three 13.4 rule 4 codes, as values, so each test fails on its own on v1.623
PARENT_POLICY_EXCLUDED = "parent_policy_excluded"
PARENT_REGION_UNAVAILABLE = "parent_region_unavailable"
PARENT_ZDR_REQUIRED = "parent_zdr_required"
# a folded inline call with a long brief and result: with no policy the parent works inline
WORK = {"context_tokens": 2000, "brief_tokens": 1000, "result_tokens": 1000, "inline_separate_call": False}


def router(counts=COUNTS, **task_extra):
    fields = dict(bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200)
    fields.update(task_extra)
    stats = Stats()
    for model_id, successes in counts.items():
        stats.add("t", model_id, successes, 100)
    return Router(Registry(MODELS), {"t": Task(name="t", **fields)}, stats)


def reasons(route):
    return {c.model_id: c.reason for c in route.candidates}


# --- the keyword and the codes ----------------------------------------------------------------

@pytest.mark.parametrize("function", [delegation.decide_delegation, Router.decide_delegation],
                         ids=["module", "Router method"])
def test_policy_is_the_last_keyword_after_exclude_models_defaulting_to_none(function):
    params = list(inspect.signature(function).parameters.values())
    assert [p.name for p in params[-2:]] == ["exclude_models", "policy"]
    assert params[-1].kind is inspect.Parameter.KEYWORD_ONLY and params[-1].default is None


def test_the_three_parent_codes_have_their_pinned_values_and_stay_in_the_module():
    import model_routing
    for name in ("PARENT_POLICY_EXCLUDED", "PARENT_REGION_UNAVAILABLE", "PARENT_ZDR_REQUIRED"):
        assert getattr(delegation, name) == name.lower()
        assert name not in model_routing.__all__


@pytest.mark.parametrize("value", [REGION, {"region": REGION}, ("x",), 0])
def test_a_policy_that_is_no_policy_raises_before_the_parent_is_looked_up(value):
    with pytest.raises(ValueError, match="policy"):
        router().decide_delegation("t", "nope/unknown", **WORK, policy=value)
    with pytest.raises(ValueError, match="policy"):
        router().decide_delegation("t", "x/small", **WORK, policy=value)


def test_the_policy_is_checked_after_brief_output_tokens():
    with pytest.raises(ValueError, match="brief_output_tokens"):
        router().decide_delegation("t", "x/small", **WORK, brief_output_tokens=-1, policy="eu-west")


# --- a ruled-out parent -----------------------------------------------------------------------

@pytest.mark.parametrize("parent, policy, reason", [
    ("y/cheap", TENANT, PARENT_POLICY_EXCLUDED),
    ("x/nowhere", TENANT, PARENT_REGION_UNAVAILABLE),
    ("x/keep", TENANT, PARENT_ZDR_REQUIRED),
    ("x/big", Policy(allowed_routes=("x/small", "x/mid")), PARENT_POLICY_EXCLUDED),
])
def test_a_parent_the_policy_rules_out_cannot_work_inline(parent, policy, reason):
    r = router()
    plain = r.decide_delegation("t", parent, **WORK)
    assert (plain.mode, plain.reason, plain.inline_allowed) == ("inline", "inline_cheaper", True)
    got = r.decide_delegation("t", parent, **WORK, policy=policy)
    assert (got.mode, got.reason, got.inline_allowed, got.below_bar) == ("delegate", reason, False, False)
    assert got.model != parent and got.model == got.route.primary == "x/small"
    assert reasons(got.route)[parent] == {PARENT_POLICY_EXCLUDED: POLICY_EXCLUDED,
                                          PARENT_REGION_UNAVAILABLE: REGION_UNAVAILABLE,
                                          PARENT_ZDR_REQUIRED: ZDR_REQUIRED}[reason]
    # the costs and bounds are those of the paths, read as without a policy
    assert got.inline_cost_usd == plain.inline_cost_usd
    assert got.parent_quality_lb == plain.parent_quality_lb


@pytest.mark.parametrize("parent, policy, reason", [
    ("y/both", Policy(allowed_families=("x",), require_zdr=True), PARENT_POLICY_EXCLUDED),  # 5b, not 5d
    ("x/keep", Policy(region="us-east", require_zdr=True), PARENT_REGION_UNAVAILABLE),     # 5c, not 5d
])
def test_the_first_policy_rule_that_applies_is_the_parent_reason(parent, policy, reason):
    extra = [model("y/both", "y", 0.1, zdr=None), model("x/east", "x", 0.6, regions=("us-east",))]
    base = router(counts={**COUNTS, "y/both": 97, "x/east": 95})
    r = Router(Registry([*MODELS, *extra]), base.tasks, base.stats)
    got = r.decide_delegation("t", parent, **WORK, policy=policy)
    assert (got.mode, got.reason, got.inline_allowed) == ("delegate", reason, False)


@pytest.mark.parametrize("task_extra, parent, generator, reason", [
    ({"exclude_families": ("y",)}, "y/cheap", None, delegation.PARENT_EXCLUDED_FAMILY),
    ({"independent_of_generator": True}, "y/cheap", "y/cheap", delegation.PARENT_NOT_INDEPENDENT),
    ({}, "z/tiny", None, delegation.PARENT_CONTEXT_FULL),
])
def test_rules_1_to_3_come_before_the_policy_rule(task_extra, parent, generator, reason):
    got = router(**task_extra).decide_delegation("t", parent, **WORK, generator_model=generator,
                                                 policy=TENANT)
    assert (got.mode, got.reason, got.inline_allowed) == ("delegate", reason, False)
    assert got.model in ALLOWED


def test_a_parent_the_policy_allows_still_works_inline_under_it():
    r = router()
    plain = r.decide_delegation("t", "x/small", **WORK)
    got = r.decide_delegation("t", "x/small", **WORK, policy=TENANT)
    assert (got.mode, got.reason) == (plain.mode, plain.reason) == ("inline", "inline_cheaper")
    assert got.inline_cost_usd == plain.inline_cost_usd
    assert got.route.primary in ALLOWED and set(got.route.fallbacks) <= ALLOWED


def test_no_allowed_route_and_a_ruled_out_parent_raise_no_model_clears_bar_with_the_candidates():
    with pytest.raises(NoModelClearsBar) as error:
        router().decide_delegation("t", "y/cheap", **WORK, policy=Policy(allowed_routes=("q/none",)))
    # rule 5 comes before 5b: z/tiny cannot hold the briefed call
    want = {m.id: POLICY_EXCLUDED for m in MODELS} | {"z/tiny": CONTEXT_TOO_SMALL}
    assert {c.model_id: c.reason for c in error.value.candidates} == want


# --- a ruled-out delegate, at one work call and at K ------------------------------------------

@pytest.mark.parametrize("flavor", FLAVORS)
@pytest.mark.parametrize("work_calls", [1, 3])
def test_the_delegate_and_its_fallbacks_stay_inside_the_allowed_set(flavor, work_calls):
    r = router()
    work = {"context_tokens": 60_000, "brief_tokens": 300, "result_tokens": 200, "work_calls": work_calls}
    plain = r.decide_delegation("t", "x/mid", flavor, **work)
    got = r.decide_delegation("t", "x/mid", flavor, **work, policy=TENANT)
    # without the policy the route leaves the allowed set
    assert not {plain.route.primary, *plain.route.fallbacks} <= ALLOWED
    want = "x/small" if flavor == "cost_effective" else "x/big"
    assert got.route.primary == want
    assert got.route.primary in ALLOWED and set(got.route.fallbacks) <= ALLOWED
    assert {m: reasons(got.route)[m] for m in RULED_OUT} == RULED_OUT
    if got.mode == "delegate":
        assert got.model in ALLOWED


def test_the_rebuilt_routers_leave_the_router_as_it_was():
    r = router()
    tasks, stats = dict(r.tasks), sorted(r.stats.items())
    for k in (1, 3):
        r.decide_delegation("t", "x/mid", **WORK, work_calls=k, policy=TENANT)
    assert r.tasks == tasks and sorted(r.stats.items()) == stats


def test_a_ruled_out_delegate_at_k_calls_is_the_one_a_k_call_router_would_pick_inside_the_set():
    r = router()
    allowed_only = Router(Registry([m for m in MODELS if m.id in ALLOWED]), r.tasks, r.stats)
    work = {"context_tokens": 60_000, "brief_tokens": 300, "result_tokens": 200, "work_calls": 4}
    got = r.decide_delegation("t", "x/mid", **work, policy=TENANT)
    want = allowed_only.decide_delegation("t", "x/mid", **work)
    assert (got.mode, got.model, got.reason) == (want.mode, want.model, want.reason)
    assert (got.delegate_cost_usd, got.delegate_quality_lb) == (want.delegate_cost_usd, want.delegate_quality_lb)


# --- the hand-off -----------------------------------------------------------------------------

def test_call_delegated_runs_the_route_decided_under_the_policy_and_stays_inside():
    r = router()
    decision = r.decide_delegation("t", "y/cheap", **WORK, policy=TENANT)
    assert decision.route.primary == "x/small"

    def fail(messages):
        raise ProviderError("outage")

    provider = FakeProvider({m.id: (fail if m.id in ("x/small", "x/mid") else
                                    (lambda messages: Completion("ok", 1000, 200))) for m in MODELS})
    ticks = itertools.count()
    executor = Executor(r, provider, clock=lambda: float(next(ticks)), now=lambda: TS)
    result = executor.call_delegated(decision, MESSAGES)
    called = [model_id for model_id, _ in provider.calls]
    assert called == ["x/small", "x/mid", "x/big"] and result.model == "x/big"
    everything_fails = FakeProvider({m.id: fail for m in MODELS})
    with pytest.raises(AllModelsFailed):
        Executor(r, everything_fails, clock=lambda: float(next(ticks)), now=lambda: TS).call_delegated(
            decision, MESSAGES)
    assert {model_id for model_id, _ in everything_fails.calls} <= ALLOWED


# --- defaults: no policy, or Policy(), keeps every decision on the shipped data -----------------

# decision_sha256 of the 960 decisions below, computed on a `git archive b20bc4b` copy of the
# package (v1.623), where decide_delegation takes no policy
V1_623_DIGEST = "88298845c3e9beae4bbbe87fe24773ae8a7b49ad92045f4bb92c9fa9d24cefd2"


def _decisions(extra):
    """Every example task, both flavors, every shipped model as the parent, five work shapes."""
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
                        got = r.decide_delegation(name, parent, flavor, **work, **extra).to_dict()
                    except NoModelClearsBar as error:
                        got = {"error": str(error),
                               "candidates": [candidate_fields(c) for c in error.candidates]}
                    out.append(got)
    return out


@pytest.mark.parametrize("extra", [{}, {"policy": None}, {"policy": Policy()}],
                         ids=["no keyword", "None", "Policy()"])
def test_no_policy_and_an_empty_policy_keep_every_v1_623_decision_on_the_shipped_data(extra):
    out = _decisions(extra)
    assert len(out) == 960
    modes = {d.get("mode", "error") for d in out}
    reasons_seen = {d["reason"] for d in out if "reason" in d}
    assert modes == {"inline", "delegate", "error"} and "parent_context_full" in reasons_seen
    assert decision_sha256(out) == V1_623_DIGEST


def test_no_evidence_or_research_script_passes_a_policy():
    passes = re.compile(r"\bpolicy\s*=|\bPolicy\(")
    scripts = [*sorted(ROOT.glob("evidence/*/*.py")), *sorted(ROOT.glob("research/*.py")),
               ROOT / "model_routing" / "delegation_eval.py", ROOT / "model_routing" / "demo.py"]
    assert len(scripts) > 20
    assert [p.relative_to(ROOT).as_posix() for p in scripts if passes.search(p.read_text(encoding="utf-8"))] == []
