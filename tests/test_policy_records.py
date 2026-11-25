"""DESIGN 5.1, 7 and 8.1 v1.642 (row POL2a): a call under a policy names it on every record.

`Policy` gains a last field `name` and a read-only `label`: None for `Policy()`, else the name, else
`sha256:` and the digest of its four rule fields, each list sorted with its repeats dropped. Every
record of a call under a policy whose label is not None carries `policy`, right after `basis` and any
`pinned_by` on an attempt record and right after `task` on a budget record, the shadow's records
included; with no policy or `Policy()` no record has it, and neither has a hand-off's record.
"""

import dataclasses
import hashlib
import itertools
import json

import pytest

from model_routing import (AllModelsFailed, Budget, BudgetExceeded, BudgetLedger, Cascade, Completion,
                           Executor, FakeProvider, Model, Monitor, Policy, Procedure, ProcedureResult,
                           ProviderError, Registry, Router, Stats, Task)

MESSAGES = [{"role": "user", "content": "judge"}]
REGION = "eu-west"
TS = "2026-11-25T00:00:00Z"
TENANT = Policy(allowed_families=("x",), region=REGION, require_zdr=True)
# 5.1 v1.642, written out: the JSON the digest is taken of, and its SHA-256 by hashlib on 2026-11-25
TENANT_JSON = '{"allowed_families":["x"],"allowed_routes":null,"region":"eu-west","require_zdr":true}'
TENANT_DIGEST = "2bc97f7a27b5a7f303b267a880f2130680c31244343fe0df1ccf57f5ac6b6d8e"
KEEPS = Policy(region=REGION)   # every model below is served in the region, so the route stays


def model(model_id, price, family="x"):
    return Model(model_id, family, price, 2 * price, 100_000, regions=(REGION,), zero_data_retention=True)


MODELS = [model("x/small", 0.5), model("x/mid", 1.0), model("x/big", 2.0)]
COUNTS = {"x/small": 95, "x/mid": 98, "x/big": 100}


def router(models=MODELS, counts=COUNTS, extra_stats=(), **task_extra):
    fields = dict(bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200)
    fields.update(task_extra)
    stats = Stats()
    for model_id, successes in counts.items():
        stats.add("t", model_id, successes, 100)
    for args, kwargs in extra_stats:
        stats.add("t", *args, **kwargs)
    return Router(Registry(models), {"t": Task(name="t", **fields)}, stats)


def ok(messages):
    return Completion("ok", 1000, 200)


def outage(messages):
    raise ProviderError("outage")


def make(route, script=None, ledger=None, **kwargs):
    ticks, ids, monitor = itertools.count(), itertools.count(), Monitor()
    provider = FakeProvider(script if script is not None else {m.id: ok for m in MODELS})
    ex = Executor(route, provider, monitor=monitor, clock=lambda: float(next(ticks)), now=lambda: TS,
                  id_factory=lambda: f"call-{next(ids)}", ledger=ledger, **kwargs)
    return ex, monitor


def after(record, key):
    keys = list(record)
    return keys[keys.index(key) + 1]


def without_policy(records):
    return [{k: v for k, v in rec.items() if k != "policy"} for rec in records]


# --- the field and the label ------------------------------------------------------------------

def test_name_is_the_last_field_and_defaults_to_none():
    assert [f.name for f in dataclasses.fields(Policy)] == [
        "allowed_routes", "allowed_families", "region", "require_zdr", "name"]
    assert Policy().name is None
    positional = Policy(("a/b",), ("a",), "eu", True)   # a v1.641 construction keeps its meaning
    assert (positional.allowed_routes, positional.region, positional.require_zdr, positional.name) == (
        ("a/b",), "eu", True, None)
    assert Policy(name="tenant-a").name == "tenant-a"


@pytest.mark.parametrize("name", ["", 1, b"acme", ("acme",), "sha256:", "sha256:" + TENANT_DIGEST])
def test_a_bad_name_is_refused_at_construction(name):
    with pytest.raises(ValueError, match="name"):
        Policy(name=name)


def test_the_label_is_none_for_policy_and_the_name_when_one_is_given():
    assert Policy().label is None and Policy(require_zdr=False).label is None
    assert Policy(name="acme").label == "acme"
    assert dataclasses.replace(TENANT, name="acme").label == "acme"


def test_an_unnamed_policy_is_labelled_by_the_digest_of_its_rules():
    want = json.dumps({"allowed_routes": None, "allowed_families": ["x"], "region": REGION, "require_zdr": True},
                      sort_keys=True, separators=(",", ":"))
    assert want == TENANT_JSON
    assert hashlib.sha256(TENANT_JSON.encode("utf-8")).hexdigest() == TENANT_DIGEST
    assert TENANT.label == "sha256:" + TENANT_DIGEST


def test_lists_in_another_order_or_with_repeats_share_a_label():
    assert Policy(allowed_routes=("b/2", "a/1", "a/1")).label == Policy(allowed_routes=["a/1", "b/2"]).label
    assert Policy(allowed_families=["y", "x", "y"], region=REGION).label == \
        Policy(allowed_families=("x", "y"), region=REGION).label


def test_different_rules_get_different_labels():
    policies = [Policy(allowed_routes=()), Policy(allowed_families=()), Policy(allowed_routes=("a/1",)),
                Policy(allowed_families=("a/1",)), Policy(allowed_routes=("a/1", "b/2")), Policy(region="eu"),
                Policy(region="us"), Policy(require_zdr=True), Policy(region="eu", require_zdr=True),
                Policy(allowed_routes=(), allowed_families=()), TENANT]
    labels = [p.label for p in policies]
    assert len(set(labels)) == len(policies)
    assert all(label.startswith("sha256:") and len(label) == 71 for label in labels)
    assert all(c in "0123456789abcdef" for label in labels for c in label[7:])


def test_the_label_is_read_only():
    with pytest.raises(AttributeError):
        TENANT.label = "other"


@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_a_named_policy_gives_the_decisions_of_its_unnamed_copy(flavor):
    r = router(models=MODELS + [model("y/cheap", 0.1, family="y")], counts=dict(COUNTS, **{"y/cheap": 97}))
    named = dataclasses.replace(TENANT, name="acme")
    assert r.select("t", flavor, policy=named).to_dict() == r.select("t", flavor, policy=TENANT).to_dict()
    work = dict(context_tokens=2000, brief_tokens=1000, result_tokens=1000, inline_separate_call=False)
    got = r.decide_delegation("t", "y/cheap", flavor, **work, policy=named)
    want = r.decide_delegation("t", "y/cheap", flavor, **work, policy=TENANT)
    assert (got.mode, got.model, got.reason, got.route.to_dict()) == (want.mode, want.model, want.reason,
                                                                      want.route.to_dict())


# --- the records ------------------------------------------------------------------------------

def test_every_attempt_record_carries_the_label_right_after_basis_a_fallback_included():
    ex, monitor = make(router(), {"x/small": outage, "x/mid": ok, "x/big": ok})
    assert ex.call("t", MESSAGES, policy=TENANT).model == "x/mid"
    assert [rec["model"] for rec in monitor.records] == ["x/small", "x/mid"]
    for rec in monitor.records:
        assert rec["policy"] == "sha256:" + TENANT_DIGEST
        assert after(rec, "basis") == "policy" and after(rec, "policy") == "tags"


@pytest.mark.parametrize("kwargs", [{}, {"flavor": "cost_blind"}, {"validate": lambda text: False}])
def test_a_policy_that_keeps_the_route_writes_the_records_of_no_policy_and_its_label(kwargs):
    out = []
    for extra in ({}, {"policy": KEEPS}, {"policy": dataclasses.replace(KEEPS, name="acme")}):
        ex, monitor = make(router())
        try:
            ex.call("t", MESSAGES, **kwargs, **extra)
        except AllModelsFailed:
            pass
        out.append(monitor.records)
    plain, ruled, named = out
    assert plain and not any("policy" in rec for rec in plain)
    assert [rec["policy"] for rec in ruled] == [KEEPS.label] * len(plain)
    assert [rec["policy"] for rec in named] == ["acme"] * len(plain)
    for records in (ruled, named):
        assert without_policy(records) == plain
        assert [list(rec) for rec in without_policy(records)] == [list(rec) for rec in plain]


def test_a_pinned_call_under_a_policy_writes_basis_pinned_by_policy_and_tags_in_order():
    ex, monitor = make(router())
    ex.call("t", MESSAGES, policy=Policy(region=REGION, name="acme"), pin_route="x/mid", pinned_by="ops")
    (rec,) = monitor.records
    keys = list(rec)
    at = keys.index("basis")
    assert keys[at:at + 4] == ["basis", "pinned_by", "policy", "tags"]
    assert (rec["basis"], rec["pinned_by"], rec["policy"]) == ("pinned", "ops", "acme")


def test_a_cascade_legs_and_a_procedure_records_carry_the_label():
    cascade = Cascade("x/small", "x/big", "sig")
    proc = Procedure("shape", "1", lambda value, call: ProcedureResult("shaped " + call(value), tool_calls=1,
                                                                       tool_cost_usd=0.0001),
                     max_model_calls=1, max_tool_calls=1, model="x/small")
    # x/small under the bar and x/mid with no trials, so the cascade (cheap plus half of strong) is cheapest
    r = router(counts={"x/small": 50, "x/big": 100}, cascades=(cascade,),
               extra_stats=[((cascade.id, 99, 100), {"escalated": 50})])
    ex, monitor = make(r)
    ex.call("t", MESSAGES, policy=TENANT, signals={"sig": lambda text: True})
    assert [(rec["model"], rec["cascade"]) for rec in monitor.records] == [("x/small", cascade.id),
                                                                         ("x/big", cascade.id)]
    r = router(counts={"x/small": 50, "x/big": 100}, extra_stats=[((proc.id, 100, 100), {"cost_usd": 0.0001})])
    ex2, monitor2 = make(r)
    ex2.call("t", MESSAGES, policy=TENANT, procedures=(proc,))
    assert [rec["model"] for rec in monitor2.records] == ["x/small", proc.id]
    for rec in monitor.records + monitor2.records:
        assert rec["policy"] == TENANT.label and after(rec, "basis") == "policy"


def test_the_shadow_record_carries_the_label_inline_and_from_a_job():
    ex, monitor = make(router(shadow_rate=1.0), random=lambda: 0.0)
    ex.call("t", MESSAGES, policy=TENANT)
    assert [(rec["model"], rec["shadow"]) for rec in monitor.records] == [("x/small", False), ("x/big", True)]
    jobs = []
    ex2, monitor2 = make(router(shadow_rate=1.0), random=lambda: 0.0, shadow_runner=jobs.append)
    ex2.call("t", MESSAGES, policy=TENANT)
    assert len(monitor2.records) == 1
    jobs[0]()
    assert [(rec["model"], rec["shadow"]) for rec in monitor2.records] == [("x/small", False), ("x/big", True)]
    for rec in monitor.records + monitor2.records:
        assert rec["policy"] == TENANT.label and after(rec, "basis") == "policy"


def test_warn_and_refused_budget_records_carry_the_label_right_after_task():
    ex, monitor = make(router(), ledger=BudgetLedger([Budget("note", 0.0000001, "warn")]))
    ex.call("t", MESSAGES, policy=TENANT)
    warned = [rec for rec in monitor.records if "budget_event" in rec]
    assert warned and {rec["budget_event"] for rec in warned} == {"warn"}
    ex2, monitor2 = make(router(), ledger=BudgetLedger([Budget("cap", 0.0000001, "refuse")]))
    with pytest.raises(BudgetExceeded):
        ex2.call("t", MESSAGES, policy=TENANT)
    (refused,) = monitor2.records
    assert refused["budget_event"] == "refused"
    # holds are priced on the estimated prompt: the routed one (x/small, about 0.0002) fits 0.001, and
    # the shadow's (x/big, about 0.0008) does not once the routed call has spent 0.0007
    ex3, monitor3 = make(router(shadow_rate=1.0), ledger=BudgetLedger([Budget("cap", 0.001, "refuse")]),
                         random=lambda: 0.0)
    assert ex3.call("t", MESSAGES, policy=TENANT).model == "x/small"
    shadow_refused = [rec for rec in monitor3.records if "budget_event" in rec]
    assert [(rec["budget_event"], rec["shadow"], rec["model"]) for rec in shadow_refused] == [
        ("refused", True, "x/big")]
    for rec in warned + [refused] + shadow_refused:
        assert list(rec)[:5] == ["ts", "call_id", "task", "policy", "tags"]
        assert rec["policy"] == TENANT.label
    assert all(rec["policy"] == TENANT.label for rec in monitor.records + monitor3.records)


def test_two_tenants_on_one_executor_write_two_labels():
    ex, monitor = make(router())
    ex.call("t", MESSAGES, policy=Policy(region=REGION, name="tenant-a"))
    ex.call("t", MESSAGES, policy=Policy(allowed_routes=("x/mid", "x/big"), name="tenant-b"))
    ex.call("t", MESSAGES, policy=Policy(allowed_routes=("x/mid", "x/big")))
    ex.call("t", MESSAGES)
    assert [(rec["model"], rec.get("policy")) for rec in monitor.records] == [
        ("x/small", "tenant-a"), ("x/mid", "tenant-b"),
        ("x/mid", Policy(allowed_routes=("x/big", "x/mid")).label), ("x/small", None)]


@pytest.mark.parametrize("extra", [{}, {"policy": None}, {"policy": Policy()}], ids=["no keyword", "None", "Policy()"])
def test_no_policy_and_an_empty_policy_write_no_key(extra):
    ex, monitor = make(router(shadow_rate=1.0), ledger=BudgetLedger([Budget("note", 0.0000001, "warn")]),
                       random=lambda: 0.0)
    ex.call("t", MESSAGES, **extra)
    assert monitor.records and not any("policy" in rec for rec in monitor.records)


def test_a_hand_off_writes_no_policy_key_whatever_its_decision_ran_under():
    r = router(models=MODELS + [model("y/cheap", 0.1, family="y")], counts=dict(COUNTS, **{"y/cheap": 97}))
    decision = r.decide_delegation("t", "y/cheap", context_tokens=2000, brief_tokens=1000, result_tokens=1000,
                                   inline_separate_call=False, policy=dataclasses.replace(TENANT, name="acme"))
    ex, monitor = make(r, {m: ok for m in ("x/small", "x/mid", "x/big", "y/cheap")})
    assert ex.call_delegated(decision, MESSAGES).model == "x/small"
    assert monitor.records and not any("policy" in rec for rec in monitor.records)
