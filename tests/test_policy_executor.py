"""DESIGN 7 v1.623 (row POL1b): the executor keeps a tenant's policy.

`Executor.call(..., policy=Policy(...))` passes the policy to `select` (5.2 v1.622), so every entry
the call can reach, its primary, its fallbacks, a cascade's two models and a procedure's named
model, is one the policy allows: no provider call goes to a ruled-out model, a budget's `downgrade`
moves only along that route, and a shadow route the policy rules out is not sent, with no draw, no
shadow ID and no pair keys. Until v1.642 the records gained no key (row POL2a adds `policy`), and
with no policy, or `Policy()`, every record and result keeps its v1.622 bytes on the shipped data.
"""

import dataclasses
import inspect
import itertools

import pytest

from decision_hash import candidate_fields, decision_sha256
from model_routing import (AllModelsFailed, Budget, BudgetExceeded, BudgetLedger, Cascade, Completion,
                           DATA_DIR, Executor, FakeProvider, Model, Monitor, NoModelClearsBar, Policy,
                           Procedure, ProcedureResult, ProviderError, Registry, Router, Stats, Task,
                           load_tasks)
from model_routing.router import POLICY_EXCLUDED, REGION_UNAVAILABLE, ZDR_REQUIRED

MESSAGES = [{"role": "user", "content": "judge"}]
REGION = "eu-west"
TS = "2026-11-24T00:00:00Z"


def model(model_id, family, price, regions=(REGION,), zdr=True):
    return Model(model_id, family, price, 2 * price, 100_000, regions=regions, zero_data_retention=zdr)


MODELS = [
    model("x/nowhere", "x", 0.05, regions=()),   # cheapest, states no region
    model("y/cheap", "y", 0.1),                   # the family the tenant disabled
    model("x/keep", "x", 0.3, zdr=None),          # states no retention rule
    model("x/small", "x", 0.5),
    model("x/mid", "x", 1.0),
    model("x/big", "x", 2.0),
]
# successes of 100: all pass the 0.8 bar; cost_blind orders x/big, x/keep, x/mid, y/cheap, ...
COUNTS = {"x/nowhere": 96, "y/cheap": 97, "x/keep": 99, "x/small": 95, "x/mid": 98, "x/big": 100}
TENANT = Policy(allowed_families=("x",), region=REGION, require_zdr=True)
RULED_OUT = {"x/nowhere", "y/cheap", "x/keep"}


def router(counts=COUNTS, **task_extra):
    fields = dict(bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200)
    fields.update(task_extra)
    stats = Stats()
    for model_id, successes in counts.items():
        stats.add("t", model_id, successes, 100)
    return Router(Registry(MODELS), {"t": Task(name="t", **fields)}, stats)


def answer(text="ok"):
    return lambda messages: Completion(text, 1000, 200)


def everyone(text="ok"):
    return {m.id: answer(text) for m in MODELS}


def never():
    raise AssertionError("random was called")


class Ids:
    def __init__(self):
        self.taken = []

    def __call__(self):
        self.taken.append(f"call-{len(self.taken)}")
        return self.taken[-1]


def make(route, provider, monitor=None, ledger=None, random=None, ids=None):
    ticks = itertools.count()
    kwargs = {} if random is None else {"random": random}
    return Executor(route, provider, monitor=monitor, clock=lambda: float(next(ticks)), now=lambda: TS,
                    id_factory=ids if ids is not None else Ids(), ledger=ledger, **kwargs)


def models_called(provider):
    return [model_id for model_id, _ in provider.calls]


# --- the keyword -----------------------------------------------------------------------------

def test_policy_is_the_last_keyword_after_procedures_defaulting_to_none():
    params = list(inspect.signature(Executor.call).parameters.values())
    names = [p.name for p in params]   # v1.639: pin_route, pinned_by, allow_below_bar follow (row PIN1a)
    assert names[names.index("procedures") + 1] == "policy"
    policy = params[names.index("policy")]
    assert policy.kind is inspect.Parameter.KEYWORD_ONLY and policy.default is None


def test_guard_call_delegated_takes_no_policy():
    # its route was decided by decide_delegation, which row POL1c gives a policy
    assert "policy" not in inspect.signature(Executor.call_delegated).parameters


@pytest.mark.parametrize("value", ["eu-west", {"region": REGION}, ("x",), 0])
def test_a_policy_that_is_no_policy_raises_before_any_id_provider_call_or_record(value):
    provider, monitor, ids = FakeProvider(everyone()), Monitor(), Ids()
    with pytest.raises(ValueError, match="^policy must be None or a Policy, got "):
        make(router(), provider, monitor, ids=ids).call("t", MESSAGES, policy=value)
    assert (provider.calls, monitor.records, ids.taken) == ([], [], [])


def test_no_allowed_route_raises_no_model_clears_bar_before_any_call():
    provider, monitor, ids = FakeProvider(everyone()), Monitor(), Ids()
    with pytest.raises(NoModelClearsBar) as caught:
        make(router(), provider, monitor, ids=ids).call("t", MESSAGES, policy=Policy(allowed_families=("z",)))
    assert {c.reason for c in caught.value.candidates} == {POLICY_EXCLUDED}
    assert (provider.calls, monitor.records, ids.taken) == ([], [], [])


# --- the route: primary and fallbacks keep the policy ------------------------------------------

def test_a_call_whose_allowed_routes_all_fail_raises_without_trying_a_ruled_out_model():
    provider, monitor = FakeProvider({}), Monitor()   # every model raises ProviderError
    with pytest.raises(AllModelsFailed) as caught:
        make(router(), provider, monitor).call("t", MESSAGES, policy=TENANT)
    error = caught.value
    assert models_called(provider) == ["x/small", "x/mid", "x/big"]
    assert [a.model for a in error.attempts] == ["x/small", "x/mid", "x/big"]
    assert {a.outcome for a in error.attempts} == {"error"}
    assert [rec["model"] for rec in monitor.records] == ["x/small", "x/mid", "x/big"]
    assert (error.decision.primary, error.decision.fallbacks) == ("x/small", ("x/mid", "x/big"))
    assert {c.model_id: c.reason for c in error.decision.candidates if c.model_id in RULED_OUT} == {
        "x/nowhere": REGION_UNAVAILABLE, "y/cheap": POLICY_EXCLUDED, "x/keep": ZDR_REQUIRED}
    # without the policy the same call goes to the three ruled-out models first
    plain = FakeProvider({})
    with pytest.raises(AllModelsFailed):
        make(router(), plain).call("t", MESSAGES)
    assert models_called(plain) == ["x/nowhere", "y/cheap", "x/keep"]


@pytest.mark.parametrize("flavor, route", [("cost_effective", ["x/small", "x/mid"]),
                                           ("cost_blind", ["x/big", "x/mid"])])
def test_a_fallback_answers_inside_the_allowed_set(flavor, route):
    script = everyone("fine")
    script[route[0]] = lambda messages: (_ for _ in ()).throw(ProviderError("outage"))
    provider = FakeProvider(script)
    result = make(router(), provider).call("t", MESSAGES, flavor=flavor, policy=TENANT)
    assert (result.model, result.text) == (route[1], "fine")
    assert models_called(provider) == route and not RULED_OUT & set(models_called(provider))


def test_one_executor_serves_two_tenants_each_call_under_its_own_policy():
    provider = FakeProvider(everyone())
    ex = make(router(), provider)
    assert ex.call("t", MESSAGES, policy=TENANT).model == "x/small"
    assert ex.call("t", MESSAGES, policy=Policy(allowed_routes=("x/keep", "x/big"))).model == "x/keep"
    assert ex.call("t", MESSAGES).model == "x/nowhere"
    assert models_called(provider) == ["x/small", "x/keep", "x/nowhere"]


def test_a_cascade_with_a_ruled_out_leg_is_never_run():
    registry = Registry([Model("a/cheap", "a", 0.1, 0.2, 100_000), Model("b/strong", "b", 1.0, 2.0, 100_000),
                         Model("a/strong", "a", 2.0, 4.0, 100_000)])
    cascade = Cascade("a/cheap", "b/strong", "sig")
    stats = Stats()
    for model_id, successes in (("a/cheap", 50), ("b/strong", 95), ("a/strong", 95)):
        stats.add("t", model_id, successes, 100)
    stats.add("t", cascade.id, 95, 100, escalated=50)
    task = Task("t", bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200,
                cascades=(cascade,))
    route = Router(registry, {"t": task}, stats)
    signals = {"sig": lambda text: True}
    script = {m: answer(m) for m in ("a/cheap", "b/strong", "a/strong")}
    plain = FakeProvider(script)
    assert make(route, plain).call("t", MESSAGES, signals=signals).model == "b/strong"
    assert models_called(plain) == ["a/cheap", "b/strong"]   # the cascade is the primary without it
    provider, monitor = FakeProvider(script), Monitor()
    result = make(route, provider, monitor).call("t", MESSAGES, signals=signals,
                                                 policy=Policy(allowed_families=("a",)))
    assert (result.model, result.decision.primary, result.decision.fallbacks) == ("a/strong", "a/strong", ())
    assert {c.model_id: c.reason for c in result.decision.candidates}[cascade.id] == POLICY_EXCLUDED
    assert models_called(provider) == ["a/strong"]
    assert all("cascade" not in rec for rec in monitor.records)


def test_a_procedure_whose_model_is_ruled_out_never_runs():
    ran = []

    def fn(value, call):
        ran.append(value)
        return ProcedureResult(call(value), tool_calls=0)

    proc = Procedure("shape", "v1", fn, max_model_calls=1, max_tool_calls=0, model="y/cheap")
    route = router()
    route.stats.add("t", proc.id, 99, 100, cost_usd=0.000001)
    plain = FakeProvider(everyone())
    assert make(route, plain).call("t", MESSAGES, procedures=(proc,)).model == proc.id
    assert models_called(plain) == ["y/cheap"] and len(ran) == 1
    provider = FakeProvider(everyone())
    result = make(route, provider).call("t", MESSAGES, procedures=(proc,), policy=TENANT)
    assert result.model == "x/small" and models_called(provider) == ["x/small"] and len(ran) == 1
    assert {c.model_id: c.reason for c in result.decision.candidates}[proc.id] == POLICY_EXCLUDED


# --- a budget's downgrade moves only along the policy's route ----------------------------------

def test_downgrade_moves_along_the_allowed_route_only():
    limit = Registry(MODELS).get("x/mid").cost(1000, 200)
    script = everyone()
    plain = FakeProvider(script)
    moved = make(router(), plain, ledger=BudgetLedger([Budget("move", limit, "downgrade")])).call(
        "t", MESSAGES, flavor="cost_blind", prompt_tokens=1000)
    assert (moved.decision.primary, moved.model) == ("x/big", "x/keep")   # without the policy
    provider, monitor = FakeProvider(script), Monitor()
    ledger = BudgetLedger([Budget("move", limit, "downgrade")])
    result = make(router(), provider, monitor, ledger=ledger).call(
        "t", MESSAGES, flavor="cost_blind", prompt_tokens=1000, policy=TENANT)
    assert (result.decision.primary, result.decision.fallbacks) == ("x/big", ("x/mid", "x/small"))
    assert result.model == "x/mid" and models_called(provider) == ["x/mid"]
    [record] = [rec for rec in monitor.records if "budget_event" not in rec]
    assert record["budget_moves"] == [{"entry": "x/big", "model": "x/big", "budget": "move"}]


def test_downgrade_with_no_allowed_entry_that_fits_raises_the_last_refusal():
    limit = Registry(MODELS).get("x/keep").cost(1000, 200)   # only ruled-out models fit
    provider = FakeProvider(everyone())
    ledger = BudgetLedger([Budget("move", limit, "downgrade")])
    with pytest.raises(BudgetExceeded) as caught:
        make(router(), provider, ledger=ledger).call("t", MESSAGES, flavor="cost_blind", prompt_tokens=1000,
                                                     policy=TENANT)
    assert (caught.value.model, caught.value.attempts, provider.calls) == ("x/small", (), [])
    assert caught.value.decision.primary == "x/big"


# --- a shadow call the policy rules out is not sent ------------------------------------------

def test_a_shadow_route_the_policy_rules_out_is_not_sent_with_no_draw_id_or_pair_keys():
    route = router(shadow_rate=1.0, shadow_route="x/keep")
    provider, monitor, ids = FakeProvider(everyone()), Monitor(), Ids()
    result = make(route, provider, monitor, random=never, ids=ids).call("t", MESSAGES, policy=TENANT)
    assert result.model == "x/small" and models_called(provider) == ["x/small"]
    assert ids.taken == ["call-0"]
    [record] = monitor.records
    assert not {"pair_id", "shadow", "checked"} & set(record)
    # without the policy the same call is shadowed on x/keep
    plain, shadowed = FakeProvider(everyone()), Monitor()
    make(route, plain, shadowed, random=lambda: 0.0).call("t", MESSAGES)
    assert models_called(plain) == ["x/nowhere", "x/keep"]
    assert [rec["shadow"] for rec in shadowed.records] == [False, True]


def test_a_shadow_runner_gets_no_job_when_the_policy_rules_the_shadow_out():
    route = router(shadow_rate=1.0, shadow_route="y/cheap")
    jobs = []
    ticks = itertools.count()
    ex = Executor(route, FakeProvider(everyone()), clock=lambda: float(next(ticks)), now=lambda: TS,
                  id_factory=Ids(), random=never, shadow_runner=jobs.append)
    assert ex.call("t", MESSAGES, policy=TENANT).model == "x/small" and jobs == []


def test_the_default_shadow_route_is_the_best_model_the_policy_allows():
    counts = dict(COUNTS, **{"x/keep": 100, "x/big": 99})   # x/keep has the highest bound
    route = router(counts, shadow_rate=1.0)
    plain = FakeProvider(everyone())
    make(route, plain, random=lambda: 0.0).call("t", MESSAGES)
    assert models_called(plain) == ["x/nowhere", "x/keep"]
    provider, monitor = FakeProvider(everyone()), Monitor()
    make(route, provider, monitor, random=lambda: 0.0).call("t", MESSAGES, policy=TENANT)
    assert models_called(provider) == ["x/small", "x/big"]
    assert [(rec["model"], rec["shadow"]) for rec in monitor.records] == [("x/small", False), ("x/big", True)]


# --- records: from v1.642 a policy's label, else no key ---------------------------------------

@pytest.mark.parametrize("kwargs", [{}, {"flavor": "cost_blind"}, {"validate": lambda text: False}])
def test_a_policy_that_keeps_the_route_writes_the_records_of_no_policy_plus_its_label(kwargs):
    everyone_allowed = Policy(allowed_families=("x", "y"), region=None, require_zdr=False)
    out = []
    for extra in ({}, {"policy": everyone_allowed}):
        monitor = Monitor()
        try:
            make(router(), FakeProvider(everyone()), monitor).call("t", MESSAGES, **kwargs, **extra)
        except AllModelsFailed:
            pass
        out.append(monitor.records)
    # v1.642 (row POL2a): each record gains the policy's label right after basis, and only that
    assert out[0] and len(out[0]) == len(out[1]) and not any("policy" in rec for rec in out[0])
    assert [after_basis(rec) for rec in out[1]] == ["policy"] * len(out[0])
    assert {rec["policy"] for rec in out[1]} == {everyone_allowed.label}
    bare = [{k: v for k, v in rec.items() if k != "policy"} for rec in out[1]]
    assert bare == out[0] and [list(rec) for rec in bare] == [list(rec) for rec in out[0]]


def after_basis(record):
    keys = list(record)
    return keys[keys.index("basis") + 1]


# --- defaults: no policy, or Policy(), keeps every record and result on the shipped data -------

# decision_sha256 of the 192 outcomes and their 330 records below, computed on a `git archive edcd01c`
# copy of the package (v1.622), where Executor.call takes no policy
V1_622_DIGEST = "9bb065c8b70d37333ea76aa6546e765011e9410ecdba880bbfc3f0b409d29b33"


def _shape_fn(value, call):
    return ProcedureResult("shaped " + call(value), tool_calls=1, tool_cost_usd=0.0001)


def _outcomes(extra):
    """Every example task, both flavors, six call shapes, half of the calls shadowed."""
    registry = Registry.load(DATA_DIR / "models.json")
    ids = [m.id for m in registry.models]
    cascade = Cascade(ids[2], ids[1], "sig")
    proc = Procedure("shape", "1", _shape_fn, max_model_calls=1, max_tool_calls=1, model=ids[1])
    tasks = {name: dataclasses.replace(t, cascades=(cascade,), shadow_rate=0.5)
             for name, t in load_tasks(DATA_DIR / "example_tasks.json").items()}
    stats = Stats()
    for name in tasks:
        for i, model_id in enumerate(ids):
            stats.add(name, model_id, 90 + i % 10, 100)
        stats.add(name, cascade.id, 100, 100, escalated=30)
        stats.add(name, proc.id, 97, 100, cost_usd=0.001)
    failing = set(ids[::3])

    def script(model_id):
        def complete(messages):
            if model_id in failing:
                raise ProviderError("outage")
            return Completion(f"{model_id} says ok", 40, 10)
        return complete

    draws = itertools.cycle([0.25, 0.75])
    monitor, ids_taken = Monitor(), Ids()
    ledger = BudgetLedger([Budget("move", 0.002, "downgrade"), Budget("note", 0.001, "warn")])
    ticks = itertools.count()
    plain = Executor(Router(registry, tasks, stats), FakeProvider({m: script(m) for m in ids}), monitor=monitor,
                     clock=lambda: float(next(ticks)), now=lambda: TS, id_factory=ids_taken,
                     random=lambda: next(draws))
    budgeted = Executor(Router(registry, tasks, stats), FakeProvider({m: script(m) for m in ids}),
                        monitor=monitor, clock=lambda: float(next(ticks)), now=lambda: TS, id_factory=ids_taken,
                        ledger=ledger, random=lambda: next(draws))
    shapes = (
        (plain, {}),
        (plain, {"prompt_tokens": 600_000}),
        (plain, {"exclude_models": (ids[4],), "validate": lambda text: "o" in text.split()[0]}),
        (plain, {"signals": {"sig": lambda text: len(text) % 2 == 0}}),
        (plain, {"procedures": (proc,)}),
        (budgeted, {"tags": {"team": "a"}}),
    )
    out = []
    for name in tasks:
        for flavor in ("cost_effective", "cost_blind"):
            for ex, case in shapes:
                for _ in range(2):
                    try:
                        result = ex.call(name, MESSAGES, flavor, **case, **extra)
                        got = {"model": result.model, "text": result.text, "call_id": result.call_id,
                               "attempts": [dataclasses.asdict(a) for a in result.attempts],
                               "decision": result.decision.to_dict()}
                    except (AllModelsFailed, BudgetExceeded) as error:
                        got = {"error": type(error).__name__, "message": str(error),
                               "attempts": [dataclasses.asdict(a) for a in error.attempts],
                               "decision": error.decision.to_dict()}
                    except NoModelClearsBar as error:
                        got = {"error": "NoModelClearsBar", "message": str(error),
                               "candidates": [candidate_fields(c) for c in error.candidates]}
                    out.append(got)
    return out, monitor.records


@pytest.mark.parametrize("extra", [{}, {"policy": None}, {"policy": Policy()}],
                         ids=["no keyword", "None", "Policy()"])
def test_no_policy_and_an_empty_policy_keep_every_v1_622_record_on_the_shipped_data(extra):
    out, records = _outcomes(extra)
    assert (len(out), len(records)) == (192, 330)
    assert any(rec.get("shadow") is True for rec in records) and any("budget_moves" in rec for rec in records)
    assert decision_sha256({"outcomes": out, "records": records}) == V1_622_DIGEST
