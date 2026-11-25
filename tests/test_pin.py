"""DESIGN 5.2, 7 and 8.1 v1.639 (row PIN1a): a pinned call skips the ranking, keeps the hard checks.

`select(..., pin_route=ROUTE, allow_below_bar=False)` judges every candidate as without a pin and
makes the pin the decision's only entry, `basis` `"pinned"`; a pin that is not `eligible` (rules 1 to
5f) is refused whatever `allow_below_bar` says, and one that is eligible but does not pass is refused
unless `allow_below_bar=True`. `Executor.call(..., pin_route=ROUTE, pinned_by=TAG)` runs the pin
alone, never shadowed, and each attempt record carries `pinned_by` right after `basis`.
"""

import inspect
import itertools
from pathlib import Path

import pytest

from model_routing import (AllModelsFailed, Cascade, Completion, Executor, FakeProvider, Model, Monitor,
                           NoModelClearsBar, Policy, Procedure, ProcedureResult, Registry, Router, Stats,
                           Task)
from model_routing.router import (BELOW_BAR, CONTEXT_TOO_SMALL, EXCLUDED_MODEL, GENERATOR,
                                  INSUFFICIENT_SAMPLES, POLICY_EXCLUDED, TOO_SLOW)

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "judge"}]
TS = "2026-11-25T00:00:00Z"
TAG = "ticket-42"


def model(model_id, family, price, window=100_000):
    return Model(model_id, family, price, 2 * price, window)


MODELS = [model("x/tiny", "x", 0.05, window=500), model("x/cheap", "x", 0.1), model("x/low", "x", 0.2),
          model("x/new", "x", 0.3), model("y/other", "y", 0.5), model("x/mid", "x", 1.0)]
# successes of 100 against a 0.8 bar: x/low is below it, x/new has no trials, x/tiny cannot hold the call
COUNTS = {"x/tiny": 99, "x/cheap": 97, "x/low": 60, "y/other": 99, "x/mid": 98}


def router(counts=COUNTS, latencies=None, cascades=(), **extra):
    fields = dict(bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200)
    fields.update(extra)
    stats = Stats()
    for model_id, successes in counts.items():
        times = (latencies or {}).get(model_id)
        stats.add("t", model_id, successes, 100, **({} if times is None else {"latencies_ms": times}))
    return Router(Registry(MODELS), {"t": Task(name="t", cascades=cascades, **fields)}, stats)


def answer(text="ok"):
    return lambda messages: Completion(text, 1000, 200)


def everyone():
    return {m.id: answer(m.id) for m in MODELS}


class Ids:
    def __init__(self):
        self.taken = []

    def __call__(self):
        self.taken.append(f"call-{len(self.taken)}")
        return self.taken[-1]


def make(route, provider, monitor=None, random=None, ids=None):
    ticks = itertools.count()
    kwargs = {} if random is None else {"random": random}
    return Executor(route, provider, monitor=monitor, clock=lambda: float(next(ticks)), now=lambda: TS,
                    id_factory=ids if ids is not None else Ids(), **kwargs)


def called(provider):
    return [model_id for model_id, _ in provider.calls]


def reasons(candidates):
    return {c.model_id: c.reason for c in candidates}


# --- the keywords ------------------------------------------------------------------------------

def test_select_takes_pin_route_and_allow_below_bar_after_policy():
    params = list(inspect.signature(Router.select).parameters.values())
    assert [p.name for p in params[-3:]] == ["policy", "pin_route", "allow_below_bar"]
    assert (params[-2].default, params[-1].default) == (None, False)
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params[-2:])


def test_call_takes_pin_route_pinned_by_and_allow_below_bar_after_policy():
    params = list(inspect.signature(Executor.call).parameters.values())
    assert [p.name for p in params[-4:]] == ["policy", "pin_route", "pinned_by", "allow_below_bar"]
    assert [p.default for p in params[-3:]] == [None, None, False]
    assert all(p.kind is inspect.Parameter.KEYWORD_ONLY for p in params[-3:])
    assert "pin_route" not in inspect.signature(Executor.call_delegated).parameters


@pytest.mark.parametrize("kwargs, message", [
    ({"pin_route": ""}, "^pin_route must be None or a non-empty string, got ''$"),
    ({"pin_route": 3}, "^pin_route must be None or a non-empty string, got 3$"),
    ({"pin_route": "x/cheap", "allow_below_bar": 1}, "^allow_below_bar must be a bool, got 1$"),
    ({"allow_below_bar": True}, "^allow_below_bar needs a pin_route$"),
])
def test_select_checks_the_pin_keywords(kwargs, message):
    with pytest.raises(ValueError, match=message):
        router().select("t", **kwargs)


@pytest.mark.parametrize("kwargs, message", [
    ({"pin_route": "x/cheap"}, "^a pinned call needs a pinned_by tag$"),
    ({"pinned_by": TAG}, "^pinned_by needs a pin_route$"),
    ({"pin_route": "x/cheap", "pinned_by": ""}, "^pinned_by must be None or a non-empty string, got ''$"),
    ({"pin_route": "x/cheap", "pinned_by": 7}, "^pinned_by must be None or a non-empty string, got 7$"),
    ({"pin_route": "", "pinned_by": TAG}, "^pin_route must be None or a non-empty string"),
    ({"allow_below_bar": True}, "^allow_below_bar needs a pin_route$"),
])
def test_call_checks_the_pin_keywords_before_any_id_provider_call_or_record(kwargs, message):
    provider, monitor, ids = FakeProvider(everyone()), Monitor(), Ids()
    with pytest.raises(ValueError, match=message):
        make(router(), provider, monitor, ids=ids).call("t", MESSAGES, **kwargs)
    assert (provider.calls, monitor.records, ids.taken) == ([], [], [])


# --- a pin that clears the bar ------------------------------------------------------------------

def test_a_passing_pin_that_is_not_the_cheapest_is_the_only_entry_with_basis_pinned():
    route = router()
    assert route.select("t").primary == "x/cheap"
    decision = route.select("t", pin_route="x/mid")
    assert (decision.primary, decision.fallbacks, decision.below_bar_fallbacks) == ("x/mid", (), ())
    assert (decision.below_bar, decision.basis, decision.pick_reason) == (False, "pinned", None)
    assert decision.candidates == route.select("t").candidates
    data = decision.to_dict()
    assert (data["primary"], data["fallbacks"], data["below_bar"], data["basis"]) == ("x/mid", [], False, "pinned")


def test_a_pinned_call_runs_the_pin_alone_and_logs_its_tag_after_basis():
    provider, monitor = FakeProvider(everyone()), Monitor()
    result = make(router(), provider, monitor).call("t", MESSAGES, pin_route="x/mid", pinned_by=TAG)
    assert (result.model, result.text, called(provider)) == ("x/mid", "x/mid", ["x/mid"])
    [record] = monitor.records
    keys = list(record)
    assert keys[keys.index("basis"):keys.index("basis") + 3] == ["basis", "pinned_by", "tags"]
    assert (record["basis"], record["pinned_by"], record["below_bar"]) == ("pinned", TAG, False)
    assert "below_bar_fallback" not in record


def test_a_failed_pin_ends_the_call_with_no_fallback():
    provider, monitor = FakeProvider({}), Monitor()   # every model raises ProviderError
    with pytest.raises(AllModelsFailed) as caught:
        make(router(), provider, monitor).call("t", MESSAGES, pin_route="x/mid", pinned_by=TAG)
    assert called(provider) == ["x/mid"] and [a.model for a in caught.value.attempts] == ["x/mid"]
    assert [(r["model"], r["final"], r["pinned_by"]) for r in monitor.records] == [("x/mid", True, TAG)]
    invalid = FakeProvider(everyone())
    with pytest.raises(AllModelsFailed):
        make(router(), invalid).call("t", MESSAGES, pin_route="x/mid", pinned_by=TAG, validate=lambda t: False)
    assert called(invalid) == ["x/mid"]


def test_a_pinned_call_is_never_shadowed():
    def never():
        raise AssertionError("random was called")
    route = router(shadow_rate=1.0)
    provider, monitor, ids = FakeProvider(everyone()), Monitor(), Ids()
    make(route, provider, monitor, random=never, ids=ids).call("t", MESSAGES, pin_route="x/cheap", pinned_by=TAG)
    assert called(provider) == ["x/cheap"] and ids.taken == ["call-0"]
    assert all("pair_id" not in r and "shadow" not in r for r in monitor.records)


# --- a pin under the bar: refused unless allowed ------------------------------------------------

@pytest.mark.parametrize("pin, reason", [("x/low", BELOW_BAR), ("x/new", INSUFFICIENT_SAMPLES)])
def test_a_pin_that_does_not_pass_is_refused_by_default(pin, reason):
    with pytest.raises(NoModelClearsBar, match=f"^pinned route '{pin}' is {reason} for task 't'; ") as caught:
        router().select("t", pin_route=pin)
    assert reasons(caught.value.candidates)[pin] == reason
    provider, monitor, ids = FakeProvider(everyone()), Monitor(), Ids()
    with pytest.raises(NoModelClearsBar):
        make(router(), provider, monitor, ids=ids).call("t", MESSAGES, pin_route=pin, pinned_by=TAG)
    assert (provider.calls, monitor.records, ids.taken) == ([], [], [])


@pytest.mark.parametrize("pin", ["x/low", "x/new"])
def test_an_allowed_pin_under_the_bar_runs_and_is_logged_with_both_flags(pin):
    decision = router().select("t", pin_route=pin, allow_below_bar=True)
    assert (decision.primary, decision.fallbacks, decision.below_bar, decision.basis) == (pin, (), True, "pinned")
    provider, monitor = FakeProvider(everyone()), Monitor()
    result = make(router(), provider, monitor).call("t", MESSAGES, pin_route=pin, pinned_by=TAG,
                                                    allow_below_bar=True)
    assert (result.model, called(provider)) == (pin, [pin])
    [record] = monitor.records
    assert (record["below_bar"], record["basis"], record["pinned_by"]) == (True, "pinned", TAG)


def test_on_no_model_is_not_read_for_a_pin():
    counts = {"x/low": 60}
    route = router(counts=counts, on_no_model="refuse")
    with pytest.raises(NoModelClearsBar, match="^no model clears the bar"):
        route.select("t")
    assert route.select("t", pin_route="x/low", allow_below_bar=True).primary == "x/low"


# --- the hard checks: refused whatever allow_below_bar says --------------------------------------

@pytest.mark.parametrize("allow", [False, True])
def test_a_pin_whose_window_is_too_small_is_refused(allow):
    with pytest.raises(NoModelClearsBar, match=f"^pinned route 'x/tiny' is {CONTEXT_TOO_SMALL} for task 't'; "):
        router().select("t", pin_route="x/tiny", allow_below_bar=allow)
    provider, monitor = FakeProvider(everyone()), Monitor()
    with pytest.raises(NoModelClearsBar):   # the call's own size: x/cheap's 100,000 cannot hold it
        make(router(), provider, monitor).call("t", MESSAGES, pin_route="x/cheap", pinned_by=TAG,
                                               allow_below_bar=allow, prompt_tokens=99_900)
    assert (provider.calls, monitor.records) == ([], [])


@pytest.mark.parametrize("allow", [False, True])
def test_an_excluded_generator_or_ruled_out_pin_is_refused(allow):
    route = Router(Registry(MODELS), {"t": Task(name="t", bar=0.8, min_samples=30, expected_input_tokens=1000,
                                                 expected_output_tokens=200, independent_of_generator=True)},
                   router().stats)
    cases = [(dict(exclude_models=["x/mid"]), "x/mid", EXCLUDED_MODEL),
             (dict(generator_model="y/other"), "y/other", GENERATOR),
             (dict(policy=Policy(allowed_families=("x",))), "y/other", POLICY_EXCLUDED)]
    for kwargs, pin, reason in cases:
        with pytest.raises(NoModelClearsBar, match=f"^pinned route '{pin}' is {reason} for task 't'; ") as caught:
            route.select("t", pin_route=pin, allow_below_bar=allow, **kwargs)
        assert reasons(caught.value.candidates)[pin] == reason
        provider = FakeProvider(everyone())
        with pytest.raises(NoModelClearsBar):
            make(route, provider).call("t", MESSAGES, pin_route=pin, pinned_by=TAG, allow_below_bar=allow, **kwargs)
        assert provider.calls == []


@pytest.mark.parametrize("allow", [False, True])
def test_a_pin_over_the_latency_bar_is_refused(allow):
    route = router(latencies={"x/mid": [2000.0] * 30, "x/cheap": [100.0] * 30}, max_p95_ms=1000.0)
    with pytest.raises(NoModelClearsBar, match=f"^pinned route 'x/mid' is {TOO_SLOW} for task 't'; "):
        route.select("t", pin_route="x/mid", allow_below_bar=allow)


def test_an_unknown_pin_raises_value_error():
    with pytest.raises(ValueError, match="^pin_route 'z/none' is no route of this call"):
        router().select("t", pin_route="z/none")
    cascade = Cascade("x/cheap", "x/mid", "sig")
    with pytest.raises(ValueError, match="^pin_route 'x/cheap>x/mid@sig' is no route of this call"):
        router(cascades=(cascade,)).select("t", pin_route=cascade.id)   # cascades=False: no such candidate


def test_a_cascade_pin_and_a_procedure_pin_run_as_their_entries():
    cascade = Cascade("x/cheap", "x/mid", "sig")
    route = router(cascades=(cascade,))
    route.stats.add("t", cascade.id, 99, 100, escalated=50)
    provider, monitor = FakeProvider(everyone()), Monitor()
    result = make(route, provider, monitor).call("t", MESSAGES, signals={"sig": lambda text: True},
                                                 pin_route=cascade.id, pinned_by=TAG)
    assert (result.model, called(provider)) == ("x/mid", ["x/cheap", "x/mid"])
    assert [(r["cascade"], r["basis"], r["pinned_by"]) for r in monitor.records] == [(cascade.id, "pinned", TAG)] * 2

    def fn(value, call):
        return ProcedureResult(call(value), tool_calls=0)
    proc = Procedure("shape", "v1", fn, max_model_calls=1, max_tool_calls=0, model="x/mid")
    route = router()
    route.stats.add("t", proc.id, 99, 100, cost_usd=10.0)
    provider, monitor = FakeProvider(everyone()), Monitor()
    result = make(route, provider, monitor).call("t", MESSAGES, procedures=(proc,), pin_route=proc.id, pinned_by=TAG)
    assert (result.model, called(provider)) == (proc.id, ["x/mid"])
    assert {(r["model"], r["pinned_by"]) for r in monitor.records} == {("x/mid", TAG), (proc.id, TAG)}


# --- defaults unchanged -------------------------------------------------------------------------

def test_with_no_pin_records_and_decisions_keep_their_keys():
    plain, explicit = Monitor(), Monitor()
    a = make(router(), FakeProvider(everyone()), plain).call("t", MESSAGES)
    b = make(router(), FakeProvider(everyone()), explicit).call("t", MESSAGES, pin_route=None, pinned_by=None,
                                                               allow_below_bar=False)
    assert plain.records == explicit.records and a.decision == b.decision
    assert a.decision.basis == "measured" and all("pinned_by" not in r for r in plain.records)
    assert router().select("t") == router().select("t", pin_route=None, allow_below_bar=False)


# --- the docs -----------------------------------------------------------------------------------

def test_design_states_v1_639_in_5_2_7_and_8_1():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert design.count("- v1.639 a pinned route (row PIN1a): `.select` gains two keywords after `policy`") == 1
    assert design.count("- v1.639 a pinned call (row PIN1a): `.call` gains three keywords after `policy`") == 1
    assert design.count("- v1.639 `pinned_by` (str), right after `basis` and before `tags` (row PIN1a") == 1
    assert design.index("a pinned route (row PIN1a)") < design.index("### 5.3 Choosing") \
        < design.index("a pinned call (row PIN1a)") < design.index("## 8. Monitoring") \
        < design.index("`pinned_by` (str), right after") < design.index("### 8.2 ")


def test_the_note_no_longer_calls_the_pinned_call_planned():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert "The change: a pinned call" not in note and "the pinned call planned" not in note
    assert note.count("From v1.639 a call can pin its route: `Executor.call` with `pin_route` and a "
                      "`pinned_by` tag skips the ranking but keeps the hard checks") == 1
    assert note.count("A manual override is a pinned call, from v1.639, as in the Harvey lesson on "
                      "tenant policy.") == 1
