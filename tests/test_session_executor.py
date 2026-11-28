"""DESIGN 4.1, 7 and 8.1 v1.697 (row CACHE3b, the second part of row CACHE3): the executor observes a session.

`Model.cache_ttl_s` states how long a provider keeps a prompt cache alive after a call reads it. Given a
`session_id`, `Executor.call` keeps the session's last attempt (its model, one `clock()` read right after its
check, and whether it reported cached reads) and passes `select` that model as `session_route`, with
`session_warm` True only when the attempt read cached tokens and the gap is at least 0 and below the model's
cache life. Without a `session_id` every decision and record keeps its bytes: `V1_696_DIGEST` was computed on
the package at 8235c66, before v1.697.

v1.698 (row T35, review iter-557 should-fix 1, 2, 4 and 5, nit 2): a pinned call of a session, an exception that is
no `ProviderError`, `.end_session` during a call, an entry kept past its life, and a digest that holds a shadow, a
failure of every route, an `invalid` record, a slice, a policy label and budget records.
"""

import dataclasses
import hashlib
import json
import math

import pytest

from model_routing import (
    AllModelsFailed, Budget, BudgetExceeded, BudgetLedger, Completion, Executor, FakeProvider, Model, Monitor,
    Policy, Procedure, ProcedureResult, ProviderError, Registry, Router, Stats, Task,
)

WARM, CHEAP = "fiction/warm", "fiction/cheap"
TTL = 300.0
NEW, OUT, TRIALS, CONTEXT = 1_000, 500, 100, 50_000
MESSAGES = [{"role": "user", "content": "go on"}]
TS = "2026-11-27T00:00:00Z"


def _registry(ttl=TTL):
    # W at 3.0 in, 0.3 cached, 15.0 out; C at 1.0 in, 0.1 cached, 5.0 out, as tests/test_session_cache.py
    return Registry([
        Model(WARM, "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3, cache_ttl_s=ttl),
        Model(CHEAP, "fam-b", 1.0, 5.0, 200_000, price_cached_in=0.1, cache_ttl_s=TTL),
    ])


def _router(registry=None, **task_extra):
    """Both models read CONTEXT tokens a call, all but NEW of them cached: past the 11,000-token break-even."""
    fields = dict(bar=0.7, min_samples=10, independent_of_generator=False, expected_input_tokens=CONTEXT,
                  expected_output_tokens=OUT)
    fields.update(task_extra)
    stats = Stats()
    for model_id in (WARM, CHEAP):
        stats.add("t", model_id, 95, TRIALS, input_tokens=CONTEXT * TRIALS, output_tokens=OUT * TRIALS,
                  cached_input_tokens=(CONTEXT - NEW) * TRIALS)
    return Router(registry if registry is not None else _registry(), {"t": Task("t", **fields)}, stats)


def hit(messages):
    return Completion("ok", CONTEXT, OUT, cached_input_tokens=CONTEXT - NEW)


def miss(messages):
    return Completion("ok", CONTEXT, OUT, cached_input_tokens=0)


def unsaid(messages):
    return Completion("ok", CONTEXT, OUT)


def outage(messages):
    raise ProviderError("outage")


class Clock:
    """An injected clock: ``reads`` counts its calls, ``t`` is moved by the test."""

    def __init__(self):
        self.t, self.reads = 0.0, 0

    def __call__(self):
        self.reads += 1
        return self.t


class Run:
    def __init__(self, router=None, script=None, **kwargs):
        ids = iter(range(10_000))
        self.clock = Clock()
        self.router = router if router is not None else _router()
        self.monitor = Monitor()
        self.provider = FakeProvider(script if script is not None else {WARM: hit, CHEAP: hit})
        self.ex = Executor(self.router, self.provider, monitor=self.monitor, clock=self.clock, now=lambda: TS,
                           id_factory=lambda: f"call-{next(ids)}", **kwargs)
        self.selects = []
        select = self.router.select

        def spy(*args, **kw):
            self.selects.append({k: kw[k] for k in ("session_route", "session_warm") if k in kw})
            return select(*args, **kw)

        self.router.select = spy

    def warm_up(self, session="s"):
        """A first call of the session that runs on WARM (CHEAP excluded), at clock 0."""
        return self.ex.call("t", MESSAGES, exclude_models=(CHEAP,), session_id=session)


# --- the cache life on a model --------------------------------------------------------------------------------

def test_cache_ttl_s_is_the_last_field_and_defaults_to_unknown():
    names = [f.name for f in dataclasses.fields(Model)]
    assert names[-3:] == ["regions", "zero_data_retention", "cache_ttl_s"]
    plain = Model("v/m", "v", 1.0, 2.0, 100_000)
    assert plain.cache_ttl_s is None
    assert list(dataclasses.asdict(plain))[-1] == "cache_ttl_s"


@pytest.mark.parametrize("value,stored", [(300, 300.0), (0.5, 0.5), (3600.0, 3600.0)])
def test_a_cache_life_is_stored_as_a_float(value, stored):
    model = Model("v/m", "v", 1.0, 2.0, 100_000, cache_ttl_s=value)
    assert model.cache_ttl_s == stored and type(model.cache_ttl_s) is float


@pytest.mark.parametrize("value", [0, 0.0, -1, True, False, "300", math.inf, math.nan, 10 ** 400, [300]])
def test_a_cache_life_that_is_no_finite_number_above_0_is_refused(value):
    with pytest.raises(ValueError, match="cache_ttl_s"):
        Model("v/m", "v", 1.0, 2.0, 100_000, cache_ttl_s=value)


def _load(tmp_path, rows):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": rows}), encoding="utf-8")
    return Registry.load(path), path


def test_registry_load_reads_the_cache_life_and_its_variants_keep_it(tmp_path):
    row = {"id": "v/m", "family": "v", "price_in": 1.0, "price_out": 2.0, "context_window": 100_000,
           "cache_ttl_s": 300, "variants": {"lean": {"harness": "h 1"}}}
    registry, _ = _load(tmp_path, [row, dict(row, id="v/n", cache_ttl_s=None, variants=None)])
    assert [(m.id, m.cache_ttl_s) for m in registry.models] == [("v/m", 300.0), ("v/m@lean", 300.0), ("v/n", None)]
    absent = {k: v for k, v in row.items() if k not in ("cache_ttl_s", "variants")}
    assert _load(tmp_path, [absent])[0].get("v/m").cache_ttl_s is None


@pytest.mark.parametrize("value", ["300", True, 0, -5])
def test_registry_load_refuses_a_bad_cache_life_naming_the_file(tmp_path, value):
    row = {"id": "v/m", "family": "v", "price_in": 1.0, "price_out": 2.0, "context_window": 100_000,
           "cache_ttl_s": value}
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": [row]}), encoding="utf-8")
    with pytest.raises(ValueError, match="models.json") as info:
        Registry.load(path)
    assert "cache_ttl_s" in str(info.value)


def test_a_fine_tune_row_takes_no_cache_life_from_its_base_and_a_model_round_trips(tmp_path):
    base = {"id": "v/base", "family": "v", "price_in": 1.0, "price_out": 2.0, "context_window": 100_000,
            "cache_ttl_s": 300}
    tune = {"id": "v/tune", "base_model": "v/base", "price_in": 1.0, "price_out": 2.0, "context_window": 100_000}
    registry, _ = _load(tmp_path, [base, tune])
    assert (registry.get("v/base").cache_ttl_s, registry.get("v/tune").cache_ttl_s) == (300.0, None)
    model = Model("v/m", "v", 1.0, 2.0, 100_000, cache_ttl_s=90)
    again, _ = _load(tmp_path, [dataclasses.asdict(model)])
    assert again.get("v/m") == model


# --- the warm, the expired and the never-cached cases ---------------------------------------------------------

def test_a_cached_read_inside_the_cache_life_is_warm_and_keeps_the_session_route():
    run = Run()
    first = run.warm_up()
    assert first.model == WARM and first.decision.session_pricing is None
    run.clock.t = 10.0
    result = run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": True}
    assert result.decision.session_pricing == "warm"
    assert (result.model, result.decision.pick_reason) == (WARM, "stay_warm")


def test_a_gap_past_the_cache_life_is_conservative_and_switches():
    run = Run()
    run.warm_up()
    run.clock.t = 301.0
    result = run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": False}
    assert result.decision.session_pricing == "conservative"
    assert result.model == CHEAP and result.decision.pick_reason != "stay_warm"


@pytest.mark.parametrize("gap,warm", [(0.0, True), (299.5, True), (TTL, False), (TTL + 0.5, False)])
def test_the_gap_must_be_below_the_cache_life(gap, warm):
    run = Run()
    run.warm_up()
    run.clock.t = gap
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": warm}


def test_a_clock_that_went_back_is_never_warm():
    run = Run()
    run.clock.t = 100.0
    run.warm_up()
    run.clock.t = 99.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": False}


@pytest.mark.parametrize("reply", [miss, unsaid])
def test_a_last_attempt_with_no_cached_read_is_never_warm(reply):
    run = Run(script={WARM: reply, CHEAP: hit})
    run.warm_up()
    run.clock.t = 1.0
    result = run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": False}
    assert result.decision.session_pricing == "conservative"


def test_an_unknown_cache_life_is_never_warm():
    run = Run(router=_router(_registry(ttl=None)))
    run.warm_up()
    run.clock.t = 1.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": False}


def test_a_session_route_outside_the_registry_is_never_warm():
    run = Run()
    run.warm_up()
    run.router.registry = Registry([run.router.registry.get(CHEAP)])
    run.clock.t = 1.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": False}


# --- what the state holds -----------------------------------------------------------------------------------

def test_a_session_s_first_call_routes_as_a_call_without_one():
    run, plain = Run(), Run()
    first = run.ex.call("t", MESSAGES, session_id="s")
    other = plain.ex.call("t", MESSAGES)
    assert run.selects == [{}]
    assert first.decision == other.decision and first.decision.session_pricing is None


def test_after_a_fallback_the_state_is_the_fallback_s():
    run = Run(script={CHEAP: outage, WARM: hit})
    run.ex.call("t", MESSAGES, session_id="s")  # CHEAP is first without a session
    assert [m for m, _ in run.provider.calls] == [CHEAP, WARM]
    run.clock.t = 1.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": True}


def test_after_every_route_failed_the_state_is_the_last_error_and_never_warm():
    run = Run()
    run.warm_up()
    run.provider.script[WARM] = outage
    with pytest.raises(AllModelsFailed):
        run.ex.call("t", MESSAGES, session_id="s", exclude_models=(CHEAP,))
    run.provider.script[WARM] = hit
    run.clock.t = 1.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": False}


def test_an_invalid_answer_is_the_session_s_last_attempt():
    run = Run()
    run.warm_up()
    run.clock.t = 1.0
    with pytest.raises(AllModelsFailed):
        run.ex.call("t", MESSAGES, session_id="s", exclude_models=(WARM,), validate=lambda text: False)
    assert [m for m, _ in run.provider.calls] == [WARM, CHEAP]
    run.clock.t = 2.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": CHEAP, "session_warm": True}


def test_a_budget_refusal_before_any_attempt_leaves_the_state():
    # the warm-up settles 0.0252 on WARM; WARM's next hold (about 0.0075) passes 0.03, so it is refused
    run = Run(ledger=BudgetLedger([Budget("cap", 0.03, "refuse")]))
    run.warm_up()
    run.clock.t = 200.0
    with pytest.raises(BudgetExceeded):
        run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": True}
    assert len(run.provider.calls) == 1
    run.clock.t = TTL + 1.0  # under 300 s after the refused call, not after the last attempt
    run.ex.call("t", MESSAGES, session_id="s")  # conservative: CHEAP first, its hold fits
    assert run.selects[-1] == {"session_route": WARM, "session_warm": False}


def test_a_shadow_never_changes_the_state_and_its_records_carry_no_session_id():
    run = Run(router=_router(shadow_rate=1.0, shadow_route=WARM), random=lambda: 0.0)
    first = run.ex.call("t", MESSAGES, session_id="s")
    assert first.model == CHEAP and [m for m, _ in run.provider.calls] == [CHEAP, WARM]
    run.clock.t = 1.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": CHEAP, "session_warm": True}
    shadows = [r for r in run.monitor.records if r.get("shadow") is True]
    routed = [r for r in run.monitor.records if r.get("shadow") is False]
    assert shadows and all("session_id" not in r for r in shadows)
    assert routed and all(r["session_id"] == "s" for r in routed)


def test_two_sessions_keep_their_own_state():
    run = Run()
    run.warm_up("a")
    run.clock.t = 1.0
    run.ex.call("t", MESSAGES, session_id="b")
    assert run.selects[-1] == {}
    run.ex.call("t", MESSAGES, session_id="a")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": True}


def test_end_session_drops_the_state():
    run = Run()
    run.warm_up()
    assert run.ex.end_session("s") is True
    assert run.ex.end_session("s") is False
    assert run.ex.end_session("never") is False
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {}


@pytest.mark.parametrize("value", ["", 3, None, b"s"])
def test_end_session_refuses_what_is_no_non_empty_str(value):
    with pytest.raises(ValueError, match="session_id"):
        Run().ex.end_session(value)


# --- the checks, the records and the clock --------------------------------------------------------------------

@pytest.mark.parametrize("value", ["", 3, b"s", ("s",)])
def test_a_session_id_must_be_a_non_empty_str_before_any_call(value):
    run = Run()
    with pytest.raises(ValueError, match="session_id"):
        run.ex.call("t", MESSAGES, session_id=value)
    assert (run.selects, run.provider.calls, run.clock.reads, run.monitor.records) == ([], [], 0, [])


def test_a_session_with_signals_or_procedures_is_refused_before_any_call():
    run = Run()
    with pytest.raises(ValueError, match="signals"):
        run.ex.call("t", MESSAGES, session_id="s", signals={"sig": lambda text: True})
    proc = Procedure("shape", "1", lambda value, call: ProcedureResult(call(value)), max_model_calls=1,
                     max_tool_calls=0, model=WARM)
    with pytest.raises(ValueError, match="procedures"):
        run.ex.call("t", MESSAGES, session_id="s", procedures=(proc,))
    assert (run.selects, run.provider.calls, run.clock.reads) == ([], [], 0)


def test_each_attempt_record_of_a_session_call_carries_session_id_right_after_slice():
    run = Run(script={CHEAP: outage, WARM: hit})
    run.ex.call("t", MESSAGES, session_id="s-1")
    assert len(run.monitor.records) == 2
    for record in run.monitor.records:
        keys = list(record)
        assert record["session_id"] == "s-1"
        assert keys[keys.index("slice") + 1] == "session_id"
    plain = Run()
    plain.ex.call("t", MESSAGES)
    assert all("session_id" not in r for r in plain.monitor.records)


def test_a_session_call_reads_the_clock_once_more_per_attempt_and_once_before_select():
    run = Run()
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.clock.reads == 3  # the attempt's two, then one after its check
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.clock.reads == 3 + 4  # one before select, then 3
    plain = Run()
    plain.ex.call("t", MESSAGES)
    plain.ex.call("t", MESSAGES)
    assert plain.clock.reads == 4


# --- review iter-557 (v1.698) --------------------------------------------------------------------------------

def test_a_pinned_call_of_a_session_gets_no_stay_warm_and_its_model_is_the_next_session_route():
    # should-fix 5: a pin is passed the session's keywords as any call is, and its attempt is the session's last
    run = Run()
    run.warm_up()
    run.clock.t = 1.0
    kept = run.ex.call("t", MESSAGES, session_id="s", pin_route=WARM, pinned_by="ops")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": True}
    assert (kept.model, kept.decision.basis, kept.decision.session_pricing) == (WARM, "pinned", "warm")
    assert kept.decision.pick_reason is None
    run.clock.t = 2.0
    moved = run.ex.call("t", MESSAGES, session_id="s", pin_route=CHEAP, pinned_by="ops")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": True}
    assert (moved.model, moved.decision.pick_reason) == (CHEAP, None)
    run.clock.t = 3.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": CHEAP, "session_warm": True}


def test_the_executor_drops_no_entry_itself():
    # should-fix 4: no expiry once the gap passes the life and no cap; only .end_session drops an entry
    run = Run()
    for session in ("a", "b", "c"):
        run.warm_up(session)
    run.clock.t = 1_000 * TTL
    for session in ("a", "b", "c"):
        run.ex.call("t", MESSAGES, session_id=session)
        assert run.selects[-1] == {"session_route": WARM, "session_warm": False}


def test_end_session_during_a_call_of_the_session_is_undone_by_its_attempt():
    # should-fix 4: the attempt stores an entry again once the provider returns
    run = Run()
    run.warm_up()
    ended = []

    def ending(messages):
        ended.append(run.ex.end_session("s"))
        return hit(messages)

    run.provider.script[CHEAP] = ending
    run.clock.t = 1.0
    run.ex.call("t", MESSAGES, session_id="s", exclude_models=(WARM,))
    assert ended == [True]
    run.clock.t = 2.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": CHEAP, "session_warm": True}


@pytest.mark.parametrize("where", ["provider", "validate"])
def test_an_exception_that_is_no_provider_error_leaves_the_state(where):
    # nit 2: it leaves .call before the attempt is logged, though the provider was called
    def bug(value):
        raise RuntimeError("a bug")

    run = Run()
    run.warm_up()
    if where == "provider":
        run.provider.script[CHEAP] = bug
    run.clock.t = 1.0
    with pytest.raises(RuntimeError, match="a bug"):
        run.ex.call("t", MESSAGES, session_id="s", exclude_models=(WARM,),
                    validate=bug if where == "validate" else None)
    assert [m for m, _ in run.provider.calls] == [WARM, CHEAP]
    run.clock.t = 2.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": WARM, "session_warm": True}


# --- unchanged without a session ------------------------------------------------------------------------------

def _guard():
    """Decisions and records of calls without a session, as JSON text, on fixtures that build at 8235c66.

    Review iter-557 should-fix 1 and 2 (v1.698): a shadow on its own route, a failure of every route, two
    `invalid` attempts, a sliced call, a policy label and a warn budget's records are in it.
    """
    out = []
    plain_registry = Registry([
        Model(WARM, "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3),
        Model(CHEAP, "fam-b", 1.0, 5.0, 200_000, price_cached_in=0.1),
    ])

    def once(run, **kwargs):
        try:
            out.append(run.ex.call("t", MESSAGES, **kwargs).decision.to_dict())
        except AllModelsFailed as exc:
            out.append([type(exc).__name__, str(exc)])
        out.extend(run.monitor.records)

    scripts = ({WARM: hit, CHEAP: hit}, {WARM: outage, CHEAP: miss}, {WARM: unsaid, CHEAP: outage},
               {WARM: outage, CHEAP: outage})
    for flavor in ("cost_effective", "cost_blind"):
        for script in scripts:
            once(Run(router=_router(plain_registry), script=script), flavor=flavor)
    once(Run(router=_router(plain_registry)), validate=lambda text: False)
    sliced = _router(plain_registry)
    for model_id, successes in ((WARM, 99), (CHEAP, 60)):
        sliced.stats.add("t@s", model_id, successes, TRIALS, input_tokens=CONTEXT * TRIALS,
                         output_tokens=OUT * TRIALS, cached_input_tokens=(CONTEXT - NEW) * TRIALS)
    once(Run(router=sliced), slice="s")
    once(Run(router=_router(plain_registry)), policy=Policy(allowed_families=("fam-a", "fam-b"), name="tenant-a"))
    run = Run(router=_router(plain_registry), ledger=BudgetLedger([Budget("watch", 0.01, "warn")]))
    for _ in range(2):
        out.append(run.ex.call("t", MESSAGES).decision.to_dict())
    out.extend(run.monitor.records)
    run = Run(router=_router(plain_registry, shadow_rate=1.0, shadow_route=WARM), random=lambda: 0.0)
    out.append(run.ex.call("t", MESSAGES, tags={"team": "a"}).decision.to_dict())
    run.ex.call("t", MESSAGES, pin_route=CHEAP, pinned_by="ops")
    out.extend(run.monitor.records)
    out.append(run.clock.reads)
    return json.dumps(out, sort_keys=False, separators=(",", ":"))


# sha256 of _guard() on the package at 8235c66 (v1.696), recomputed for the v1.698 guard
V1_696_DIGEST = "7aaf0bbc9f3bad17878c1a29b40d3bcf992f398d0db6f2bc11d755667654a91d"


def test_calls_without_a_session_keep_their_v1_696_bytes():
    assert hashlib.sha256(_guard().encode()).hexdigest() == V1_696_DIGEST


def test_the_guard_holds_a_shadow_a_failure_an_invalid_answer_a_slice_a_policy_and_budget_records():
    # review iter-557 should-fix 1 and 2: so the digest pins each of them
    items = json.loads(_guard())
    records = [item for item in items if isinstance(item, dict) and "outcome" in item]
    assert {r["shadow"] for r in records if "pair_id" in r} == {False, True}
    assert items.count(["AllModelsFailed", "all 2 routed models failed for task 't'"]) == 3
    assert sum(r["outcome"] == "invalid" for r in records) == 2
    assert any(r.get("slice") == "s" for r in records)
    assert any(r.get("policy") == "tenant-a" for r in records)
    assert any("budget_event" in item for item in items if isinstance(item, dict))
