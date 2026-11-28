"""DESIGN 4.1, 7 and 8.1 v1.697 (row CACHE3b, the second part of row CACHE3): the executor observes a session.

`Model.cache_ttl_s` states how long a provider keeps a prompt cache alive after a call reads it. Given a
`session_id`, `Executor.call` keeps the session's last attempt (its model, one `clock()` read right after its
check, and whether it reported cached reads) and passes `select` that model as `session_route`, with
`session_warm` True only when the attempt read cached tokens and the gap is at least 0 and below the model's
cache life. Without a `session_id` every decision and record keeps its bytes: `V1_696_DIGEST` was computed on
the package at 8235c66, before v1.697.
"""

import dataclasses
import hashlib
import json
import math

import pytest

from model_routing import (
    AllModelsFailed, Budget, BudgetExceeded, BudgetLedger, Completion, Executor, FakeProvider, Model, Monitor,
    Procedure, ProcedureResult, ProviderError, Registry, Router, Stats, Task,
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
    path.write_text(json.dumps(rows), encoding="utf-8")
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
    path.write_text(json.dumps([row]), encoding="utf-8")
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
    run = Run(script={WARM: outage, CHEAP: hit})
    run.ex.call("t", MESSAGES, session_id="s", flavor="cost_blind")  # cost_blind: both at 0, WARM is first
    assert [m for m, _ in run.provider.calls] == [WARM, CHEAP]
    run.clock.t = 1.0
    run.ex.call("t", MESSAGES, session_id="s")
    assert run.selects[-1] == {"session_route": CHEAP, "session_warm": True}


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
    with pytest.raises(BudgetExceeded):
        run.ex.call("t", MESSAGES, session_id="s", flavor="cost_blind")
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
                     model=WARM)
    with pytest.raises(ValueError, match="procedures"):
        run.ex.call("t", MESSAGES, session_id="s", procedures=(proc,))
    assert (run.selects, run.provider.calls, run.clock.reads) == ([], [], 0)


def test_each_attempt_record_of_a_session_call_carries_session_id_right_after_slice():
    run = Run(script={WARM: outage, CHEAP: hit})
    run.ex.call("t", MESSAGES, session_id="s-1", flavor="cost_blind")
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


# --- unchanged without a session ------------------------------------------------------------------------------

def _guard():
    """Decisions and records of calls without a session, as JSON text, on fixtures that build at 8235c66."""
    out = []
    plain_registry = Registry([
        Model(WARM, "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3),
        Model(CHEAP, "fam-b", 1.0, 5.0, 200_000, price_cached_in=0.1),
    ])
    for flavor in ("cost_effective", "cost_blind"):
        for script in ({WARM: hit, CHEAP: hit}, {WARM: outage, CHEAP: miss}, {WARM: unsaid, CHEAP: outage}):
            run = Run(router=_router(plain_registry), script=script)
            try:
                result = run.ex.call("t", MESSAGES, flavor=flavor)
                out.append(result.decision.to_dict())
            except Exception as exc:  # AllModelsFailed
                out.append(type(exc).__name__)
            out.extend(run.monitor.records)
    run = Run(router=_router(plain_registry, shadow_rate=1.0), random=lambda: 0.0)
    out.append(run.ex.call("t", MESSAGES, tags={"team": "a"}).decision.to_dict())
    run.ex.call("t", MESSAGES, pin_route=CHEAP, pinned_by="ops")
    out.extend(run.monitor.records)
    out.append(run.clock.reads)
    return json.dumps(out, sort_keys=False, separators=(",", ":"))


# sha256 of _guard() on the package at 8235c66 (v1.696)
V1_696_DIGEST = "26dfc14a910d67ca882bfaee0e44285abae1b42d6acf9f614447d66b589a16a5"


def test_calls_without_a_session_keep_their_v1_696_bytes():
    assert hashlib.sha256(_guard().encode()).hexdigest() == V1_696_DIGEST
