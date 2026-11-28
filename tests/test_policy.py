"""DESIGN 4.1, 5.1 and 5.2 v1.622 (row POL1a): a tenant's policy rules routes out before cost.

A registry row may state `regions` and `zero_data_retention`. `Router.select(..., policy=Policy(...))`
applies rules 5b to 5d after rule 5a: a route outside the allowed routes or families is
`policy_excluded`, one not served in the policy's region is `region_unavailable`, and one that does
not state zero data retention when the policy requires it is `zdr_required`. A value the registry
leaves out fails closed. With no policy, or `Policy()`, every decision keeps its v1.621 bytes.
"""

import dataclasses
import hashlib
import json

import pytest
from decision_hash import candidate_fields

import model_routing
from model_routing import (CASCADE_UNKNOWN_MODEL, CONTEXT_TOO_SMALL, DATA_DIR, EXCLUDED_MODEL, PASSES, Cascade,
                           Model, NoModelClearsBar, Priors, Procedure, ProcedureResult, Registry, Router, Stats,
                           Task, Variant, load_tasks)

REGION = "eu-west"


def policy(**fields):
    return model_routing.Policy(**fields)


def codes():
    return (model_routing.POLICY_EXCLUDED, model_routing.REGION_UNAVAILABLE, model_routing.ZDR_REQUIRED)


def model(model_id, family, price, regions=(REGION,), zdr=True, **extra):
    return Model(model_id, family, price, 2 * price, 100_000, regions=regions,
                 zero_data_retention=zdr, **extra)


def tenant_models():
    return [
        model("x/nowhere", "x", 0.05, regions=()),           # cheapest, states no region
        model("y/cheap", "y", 0.1),                           # the family the tenant disabled
        model("x/us", "x", 0.2, regions=("us-east",)),        # served elsewhere only
        model("x/keep", "x", 0.3, zdr=None),                  # states no retention rule
        model("x/small", "x", 0.5, regions=("us-east", REGION)),
        model("x/big", "x", 2.0),
    ]


def task(name="t", **extra):
    fields = dict(bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200)
    fields.update(extra)
    return Task(name=name, **fields)


def router(models, counts=(95, 100), **task_extra):
    stats = Stats()
    for m in models:
        stats.add("t", m.id, *counts)
    return Router(Registry(models), {"t": task(**task_extra)}, stats)


def reasons(decision_or_error):
    return {c.model_id: c.reason for c in decision_or_error.candidates}


TENANT = dict(allowed_families=("x",), region=REGION, require_zdr=True)


# --- the contract: a tenant gets the cheapest allowed route, and fallbacks stay inside ---------

def test_a_tenant_in_one_region_with_one_family_disabled_gets_the_cheapest_allowed_route():
    r = router(tenant_models())
    assert r.select("t").primary == "x/nowhere"  # without a policy, cost alone decides
    decision = r.select("t", policy=policy(**TENANT))
    assert (decision.primary, decision.fallbacks) == ("x/small", ("x/big",))
    assert reasons(decision) == {"x/nowhere": model_routing.REGION_UNAVAILABLE,
                                 "y/cheap": model_routing.POLICY_EXCLUDED,
                                 "x/us": model_routing.REGION_UNAVAILABLE,
                                 "x/keep": model_routing.ZDR_REQUIRED,
                                 "x/small": PASSES, "x/big": PASSES}
    for c in decision.candidates:
        assert c.eligible == c.passes == (c.reason == PASSES)


def test_cost_blind_keeps_the_policy_too():
    models = tenant_models()
    stats = Stats()
    for m in models:
        stats.add("t", m.id, 99 if m.id == "y/cheap" else 95, 100)
    r = Router(Registry(models), {"t": task()}, stats)
    assert r.select("t", "cost_blind").primary == "y/cheap"
    # x/small and x/big tie on their lower bound, so cost_blind takes the lower model ID (5.3)
    assert r.select("t", "cost_blind", policy=policy(**TENANT)).primary == "x/big"


def test_below_bar_fallbacks_and_the_best_available_path_never_leave_the_allowed_set():
    models = tenant_models()
    stats = Stats()
    for m in models:
        stats.add("t", m.id, 95 if m.id == "x/small" else 60, 100)
    r = Router(Registry(models), {"t": task(fallback_below_bar=True)}, stats)
    decision = r.select("t", policy=policy(**TENANT))
    assert (decision.primary, decision.fallbacks, decision.below_bar_fallbacks) == ("x/small", ("x/big",), ("x/big",))
    stats2 = Stats()
    for m in models:
        stats2.add("t", m.id, 60, 100)
    r = Router(Registry(models), {"t": task(on_no_model="best_available")}, stats2)
    decision = r.select("t", policy=policy(**TENANT))
    assert decision.below_bar and {decision.primary, *decision.fallbacks} == {"x/small", "x/big"}


def test_a_prior_pick_never_leaves_the_allowed_set():
    models = tenant_models()
    priors = Priors({"c": {"scores": {"y/cheap": 0.99, "x/small": 0.5, "x/big": 0.6}}})
    r = Router(Registry(models), {"t": task(on_no_model="best_available", prior_category="c")}, Stats(), priors)
    assert (r.select("t").primary, r.select("t").basis) == ("y/cheap", "prior")
    decision = r.select("t", policy=policy(**TENANT))
    assert (decision.primary, decision.fallbacks, decision.basis) == ("x/big", ("x/small",), "prior")


def test_no_allowed_route_raises_no_model_clears_bar_with_the_policy_reasons():
    r = router(tenant_models())
    with pytest.raises(NoModelClearsBar) as error:
        r.select("t", policy=policy(allowed_routes=()))
    assert set(reasons(error.value).values()) == {model_routing.POLICY_EXCLUDED}
    with pytest.raises(NoModelClearsBar):
        r.select("t", policy=policy(region="ap-south"))


# --- each rule ------------------------------------------------------------------------------

def test_allowed_routes_reads_the_id_and_the_base_id():
    base = model("v/m", "v", 0.1)
    lean = dataclasses.replace(base, id="v/m@lean", variant=Variant("lean", harness="agent 2"))
    other = model("v/o", "v", 0.2)
    r = router([base, lean, other])
    by_base = r.select("t", policy=policy(allowed_routes=("v/m",)))
    assert reasons(by_base) == {"v/m": PASSES, "v/m@lean": PASSES, "v/o": model_routing.POLICY_EXCLUDED}
    by_variant = r.select("t", policy=policy(allowed_routes=["v/m@lean"]))
    assert reasons(by_variant) == {"v/m": model_routing.POLICY_EXCLUDED, "v/m@lean": PASSES,
                                   "v/o": model_routing.POLICY_EXCLUDED}
    assert by_variant.primary == "v/m@lean"


def test_allowed_families_and_allowed_routes_both_apply():
    r = router(tenant_models())
    decision = r.select("t", policy=policy(allowed_routes=("x/small", "y/cheap"), allowed_families=("x",)))
    assert decision.primary == "x/small" and decision.fallbacks == ()
    assert reasons(decision)["y/cheap"] == model_routing.POLICY_EXCLUDED


def test_an_unstated_region_or_retention_fails_closed_and_a_stated_false_too():
    r = router([model("a/none", "a", 0.1, regions=(), zdr=None), model("a/off", "a", 0.2, zdr=False),
                model("a/on", "a", 0.3)])
    assert reasons(r.select("t", policy=policy(region=REGION))) == {
        "a/none": model_routing.REGION_UNAVAILABLE, "a/off": PASSES, "a/on": PASSES}
    assert reasons(r.select("t", policy=policy(require_zdr=True))) == {
        "a/none": model_routing.ZDR_REQUIRED, "a/off": model_routing.ZDR_REQUIRED, "a/on": PASSES}


def test_the_policy_rules_follow_rule_5a_and_keep_the_earlier_reasons():
    small = Model("x/tiny", "x", 0.01, 0.02, 500)  # rule 5: too small, and in no region
    scoped = model("x/scoped", "x", 0.02, regions=(), scope_tasks=("other",))
    r = router([small, scoped, model("x/ok", "x", 0.5)])
    with pytest.raises(NoModelClearsBar) as error:
        r.select("t", exclude_models=("x/ok",), policy=policy(region=REGION, require_zdr=True))
    assert reasons(error.value) == {"x/tiny": CONTEXT_TOO_SMALL, "x/scoped": model_routing.OUT_OF_SCOPE,
                                    "x/ok": EXCLUDED_MODEL}
    # 5b before 5c before 5d on one model
    bad = model("y/bad", "y", 0.1, regions=(), zdr=None)
    r = router([bad])
    order = [(dict(allowed_families=("x",), region=REGION, require_zdr=True), model_routing.POLICY_EXCLUDED),
             (dict(region=REGION, require_zdr=True), model_routing.REGION_UNAVAILABLE),
             (dict(require_zdr=True), model_routing.ZDR_REQUIRED)]
    for fields, want in order:
        with pytest.raises(NoModelClearsBar) as error:
            r.select("t", policy=policy(**fields))
        assert reasons(error.value) == {"y/bad": want}


# --- cascades and procedures ----------------------------------------------------------------

def cascade_router(cheap_regions=(REGION,)):
    cheap = model("c/cheap", "c", 0.1, regions=cheap_regions)
    strong = model("c/strong", "c", 1.0)
    cascade = Cascade("c/cheap", "c/strong", "sig")
    stats = Stats()
    stats.add("t", cheap.id, 95, 100)
    stats.add("t", strong.id, 95, 100)
    stats.add("t", cascade.id, 95, 100, escalated=10)
    return Router(Registry([cheap, strong]), {"t": task(cascades=(cascade,))}, stats), cascade


def test_a_cascade_meets_the_policy_on_each_leg_and_needs_its_own_id_allowed():
    r, cascade = cascade_router()
    assert reasons(r.select("t", cascades=True, policy=policy(region=REGION)))[cascade.id] == PASSES
    legs_only = policy(allowed_routes=("c/cheap", "c/strong"))
    assert reasons(r.select("t", cascades=True, policy=legs_only))[cascade.id] == model_routing.POLICY_EXCLUDED
    both = policy(allowed_routes=("c/cheap", "c/strong", cascade.id))
    assert reasons(r.select("t", cascades=True, policy=both))[cascade.id] == PASSES
    no_strong = policy(allowed_routes=("c/cheap", cascade.id))
    assert reasons(r.select("t", cascades=True, policy=no_strong))[cascade.id] == model_routing.POLICY_EXCLUDED
    r, cascade = cascade_router(cheap_regions=("us-east",))
    decision = r.select("t", cascades=True, policy=policy(region=REGION))
    assert reasons(decision)[cascade.id] == model_routing.REGION_UNAVAILABLE
    assert decision.primary == "c/strong" and cascade.id not in decision.fallbacks


def test_the_cascade_id_check_comes_before_any_rule_on_its_legs():
    r, cascade = cascade_router(cheap_regions=("us-east",))
    legs_only = policy(allowed_routes=("c/cheap", "c/strong"), region=REGION)
    got = reasons(r.select("t", cascades=True, policy=legs_only))
    assert (got[cascade.id], got["c/cheap"]) == (model_routing.POLICY_EXCLUDED, model_routing.REGION_UNAVAILABLE)
    r, cascade = cascade_router()
    unallowed = r.select("t", cascades=True, exclude_models=("c/strong",),
                         policy=policy(allowed_routes=("c/cheap", "c/strong")))
    assert reasons(unallowed)[cascade.id] == model_routing.POLICY_EXCLUDED
    allowed = r.select("t", cascades=True, exclude_models=("c/strong",),
                       policy=policy(allowed_routes=("c/cheap", "c/strong", cascade.id)))
    assert reasons(allowed)[cascade.id] == EXCLUDED_MODEL  # a leg's rule 1 before its policy rules


def test_an_unknown_cascade_model_still_comes_first():
    cheap = model("c/cheap", "c", 0.1)
    cascade = Cascade("c/cheap", "c/missing", "sig")
    stats = Stats()
    stats.add("t", cheap.id, 95, 100)
    r = Router(Registry([cheap]), {"t": task(cascades=(cascade,))}, stats)
    with pytest.raises(NoModelClearsBar) as error:
        r.select("t", cascades=True, policy=policy(allowed_routes=()))
    assert reasons(error.value)[cascade.id] == CASCADE_UNKNOWN_MODEL


def test_rule_1_on_a_cascade_id_comes_before_its_policy_id_check():
    r, cascade = cascade_router()
    with pytest.raises(NoModelClearsBar) as error:
        r.select("t", cascades=True, exclude_models=(cascade.id,), policy=policy(allowed_routes=()))
    assert reasons(error.value)[cascade.id] == EXCLUDED_MODEL


def _fn(run):
    return ProcedureResult(output="ok", tool_cost_usd=0.0)


def procedure_router(proc):
    stats = Stats()
    stats.add("t", proc.id, 95, 100, cost_usd=0.5)
    m = model("p/m", "p", 0.1, zdr=None)
    stats.add("t", m.id, 95, 100)
    return Router(Registry([m]), {"t": task()}, stats)


def test_a_procedure_meets_the_policy_on_its_model_and_needs_its_own_id_allowed():
    proc = Procedure("triage", "1", _fn, max_model_calls=1, max_tool_calls=0, model="p/m")
    r = procedure_router(proc)
    with pytest.raises(NoModelClearsBar) as error:
        r.select("t", procedures=[proc], policy=policy(require_zdr=True))
    assert reasons(error.value) == {"p/m": model_routing.ZDR_REQUIRED, proc.id: model_routing.ZDR_REQUIRED}
    assert reasons(r.select("t", procedures=[proc], policy=policy(allowed_routes=("p/m",))))[proc.id] \
        == model_routing.POLICY_EXCLUDED
    assert reasons(r.select("t", procedures=[proc], policy=policy(allowed_routes=("p/m", proc.id))))[proc.id] \
        == PASSES


def test_a_procedure_without_a_model_meets_only_the_id_check():
    proc = Procedure("parse", "2", _fn, max_model_calls=0, max_tool_calls=1)
    r = procedure_router(proc)
    decision = r.select("t", procedures=(proc,), policy=policy(region="nowhere", require_zdr=True,
                                                              allowed_families=()))
    assert decision.primary == proc.id and reasons(decision)[proc.id] == PASSES
    decision = r.select("t", procedures=(proc,), policy=policy(allowed_routes=("p/m",)))
    assert decision.primary == "p/m" and reasons(decision)[proc.id] == model_routing.POLICY_EXCLUDED


# --- the registry fields --------------------------------------------------------------------

def test_the_two_fields_are_the_last_and_default_to_unstated():
    names = [f.name for f in dataclasses.fields(Model)]
    # the last two fields until v1.697 adds `cache_ttl_s` after them (DESIGN 4.1)
    assert names[-4:] == ["price_cache_write", "regions", "zero_data_retention", "cache_ttl_s"]
    plain = Model("v/m", "v", 1.0, 2.0, 100_000)
    assert (plain.regions, plain.zero_data_retention) == ((), None)
    assert list(dataclasses.asdict(plain))[-3:-1] == ["regions", "zero_data_retention"]
    kept = Model("v/m", "v", 1.0, 2.0, 100_000, regions=("b", "a", "b"), zero_data_retention=False)
    assert (kept.regions, kept.zero_data_retention) == (("b", "a", "b"), False)


@pytest.mark.parametrize("fields", [
    {"regions": ["eu-west"]}, {"regions": "eu-west"}, {"regions": ("",)}, {"regions": (1,)},
    {"regions": None}, {"zero_data_retention": 1}, {"zero_data_retention": "yes"},
    {"zero_data_retention": 0},
])
def test_a_bad_field_is_refused_at_construction(fields):
    with pytest.raises(ValueError):
        Model("v/m", "v", 1.0, 2.0, 100_000, **fields)


def _load(tmp_path, rows):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": rows}), encoding="utf-8")
    return Registry.load(path)


ROW = {"id": "v/m", "family": "v", "price_in": 1.0, "price_out": 2.0, "context_window": 100_000}


def test_registry_load_reads_both_keys_and_a_row_s_variants_have_them(tmp_path):
    registry = _load(tmp_path, [dict(ROW, regions=["eu-west", "us-east"], zero_data_retention=True,
                                     variants={"lean": {"harness": "agent 2"}}),
                                dict(ROW, id="v/n", regions=None, zero_data_retention=None)])
    for model_id in ("v/m", "v/m@lean"):
        got = registry.get(model_id)
        assert (got.regions, got.zero_data_retention) == (("eu-west", "us-east"), True)
    assert (registry.get("v/n").regions, registry.get("v/n").zero_data_retention) == ((), None)
    back = _load(tmp_path, [dataclasses.asdict(m) for m in registry.models if m.variant is None])
    assert [dataclasses.asdict(m) for m in back.models] == [dataclasses.asdict(registry.get("v/m")),
                                                            dataclasses.asdict(registry.get("v/n"))]


@pytest.mark.parametrize("extra", [{"regions": "eu-west"}, {"regions": {"eu": 1}}, {"regions": [""]},
                                   {"zero_data_retention": "yes"}, {"zero_data_retention": 1}])
def test_registry_load_refuses_a_bad_value_naming_the_file(tmp_path, extra):
    with pytest.raises(ValueError, match="models.json"):
        _load(tmp_path, [dict(ROW, **extra)])


def test_the_shipped_registry_states_neither_key():
    registry = Registry.load(DATA_DIR / "models.json")
    assert all(m.regions == () and m.zero_data_retention is None for m in registry.models)
    rows = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))["models"]
    assert not any("regions" in row or "zero_data_retention" in row for row in rows)


# --- the Policy type and the exports --------------------------------------------------------

def test_policy_defaults_limit_nothing_and_lists_are_stored_as_tuples():
    empty = policy()
    assert (empty.allowed_routes, empty.allowed_families, empty.region, empty.require_zdr) == (None, None, None, False)
    built = policy(allowed_routes=["a/b"], allowed_families=("a",), region="eu", require_zdr=True)
    assert (built.allowed_routes, built.allowed_families) == (("a/b",), ("a",))
    assert policy(allowed_routes=[]).allowed_routes == ()
    with pytest.raises(dataclasses.FrozenInstanceError):
        built.region = "us"


@pytest.mark.parametrize("fields", [
    {"allowed_routes": "a/b"}, {"allowed_routes": ("",)}, {"allowed_routes": (1,)}, {"allowed_routes": {"a/b"}},
    {"allowed_families": "a"}, {"allowed_families": [None]}, {"region": ""}, {"region": 1},
    {"require_zdr": 1}, {"require_zdr": None}, {"require_zdr": "yes"},
])
def test_a_bad_policy_is_refused(fields):
    with pytest.raises(ValueError):
        policy(**fields)


def test_the_codes_and_policy_are_exported_after_out_of_scope():
    assert codes() == ("policy_excluded", "region_unavailable", "zdr_required")
    names = model_routing.__all__
    at = names.index("OUT_OF_SCOPE")
    assert names[at + 1:at + 5] == ["POLICY_EXCLUDED", "REGION_UNAVAILABLE", "ZDR_REQUIRED", "Policy"]


def test_select_refuses_a_policy_that_is_no_policy_after_the_procedures_check():
    r = router(tenant_models())
    with pytest.raises(ValueError, match="policy"):
        r.select("t", policy={"region": REGION})
    with pytest.raises(ValueError, match="procedures"):
        r.select("t", procedures="p", policy="x")


# --- defaults: no policy, or Policy(), keeps every decision's bytes ------------------------

# sha256 of the 160 decisions below, computed on the v1.621 tree (0c8233a), where select takes no policy
V1_621_DIGEST = "f00882e06e0638c8d7f869f7178e3fe715089fcc6c63edfc519de85f43a8a156"


def _decisions(extra):
    """Every example task, both flavors, five call shapes, measured and on priors (one string each)."""
    registry = Registry.load(DATA_DIR / "models.json")
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    first = registry.models[0].id
    proc = Procedure("p", "1", _fn, max_model_calls=1, max_tool_calls=0, model=first)
    measured = Stats()
    for name in tasks:
        for i, m in enumerate(registry.models):
            measured.add(name, m.id, 90 + i % 10, 100)
        measured.add(name, proc.id, 97, 100, cost_usd=0.001)
    routers = (Router(registry, tasks, measured),
               Router(registry, {n: dataclasses.replace(t, on_no_model="best_available") for n, t in tasks.items()},
                      Stats(), Priors.load(DATA_DIR / "priors.json")))
    cases = ({}, {"prompt_tokens": 150_000}, {"exclude_models": (first,)}, {"generator_model": first},
             {"procedures": (proc,)})
    out = []
    for r in routers:
        for name in r.tasks:
            for flavor in ("cost_effective", "cost_blind"):
                for case in cases:
                    try:
                        got = json.dumps(r.select(name, flavor, **case, **extra).to_dict(), sort_keys=True)
                    except NoModelClearsBar as error:
                        got = repr([candidate_fields(c) for c in error.candidates])  # v1.628: no bar, no time
                    out.append(got)
    return out


@pytest.mark.parametrize("extra", [{}, {"policy": None}, {"policy": model_routing.Policy()}],
                         ids=["no keyword", "None", "Policy()"])
def test_no_policy_and_an_empty_policy_keep_every_v1_621_decision_on_the_shipped_data(extra):
    out = _decisions(extra)
    assert len(out) == 160
    assert hashlib.sha256("\n".join(out).encode("utf-8")).hexdigest() == V1_621_DIGEST
