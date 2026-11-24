"""DESIGN 7, 8.1 and 8.3 v1.578 (row PROC1c): the executor runs a procedure route.

`Executor.call(..., procedures=[...])` passes the procedures to `select`, runs a routed procedure
entry by `Procedure.run` on a deep copy of the call's messages, sends each model call of its handle
to its named model as a timed, priced attempt (a `ProviderError` raised into `fn`), and closes the
entry with one attempt under the procedure's ID: `error` when the run raises, else `validate` on its
output, `invalid` or `ok`, at its tool cost. An `error` or `invalid` entry falls back. Its records
gain `procedure` and `procedure_version` right after `slice`, the closing one also `model_calls`,
`tool_calls` and `tool_cost_usd`. Without procedures every route and record is v1.577's. The
contract tests were written under strict xfail and the implementing commit removed the marks; the
unmarked guards pin what v1.578 keeps and passed before and after it.
"""

import hashlib
import inspect

import pytest

from model_routing import (
    AllModelsFailed, Attempt, Completion, Executor, FakeProvider, Model, Monitor, Procedure,
    ProcedureResult, ProviderError, Registry, Router, Stats, Task, Variant, report, run_demo,
)

MODEL, CHEAP, BEST = "fiction/model", "fiction/cheap", "fiction/best"
REGISTRY = Registry([
    Model(MODEL, "fam-a", 1.0, 2.0, 10_000),
    Model(CHEAP, "fam-b", 0.1, 0.2, 10_000),
    Model(BEST, "fam-c", 10.0, 30.0, 100_000),   # 0.016 a call at the task's 1,000 and 200
])
TS = "2026-11-22T00:00:00Z"

# the demo's calls.jsonl, unchanged since v1.536 (tests/test_cascade_executor.py)
DEMO_CALLS_SHA256 = "4f111326781939140bebe04e0841a66306cac48492bc6c95f4bc2211fa92b351"

V1_577_KEYS = ["ts", "call_id", "task", "flavor", "model", "family", "attempt", "final",
               "outcome", "error", "latency_ms", "input_tokens", "output_tokens", "cost_usd",
               "routing_cost_usd", "below_bar", "basis", "tags", "slice", "prompt_tokens",
               "prompt_tokens_estimated"]
CALL_KEYS = V1_577_KEYS[:19] + ["procedure", "procedure_version"] + V1_577_KEYS[19:]
CLOSING_KEYS = (V1_577_KEYS[:19] + ["procedure", "procedure_version", "model_calls",
                                    "tool_calls", "tool_cost_usd"] + V1_577_KEYS[19:])


def msgs():
    return [{"role": "user", "content": "hi"}]  # 2 characters, estimated at 1 token


def poll_fn(value, call):
    """Three polls in code, then one model call that shapes the result."""
    text = call([{"role": "user", "content": "summarize: " + value[-1]["content"]}])
    return ProcedureResult("shaped " + text, tool_calls=3, tool_cost_usd=0.0005)


def boom(value, call):
    raise RuntimeError("boom")


def proc(fn=poll_fn, model=CHEAP, max_model_calls=2, max_tool_calls=5):
    return Procedure("poll", "v1", fn, max_model_calls=max_model_calls,
                     max_tool_calls=max_tool_calls, model=model)


POLL = proc()
PID = "proc:poll@v1+fiction/cheap"


def code_fn(value, call):
    return ProcedureResult("shaped in code", tool_calls=2)


CODE = Procedure("shape", "v2", code_fn, max_model_calls=0, max_tool_calls=2)   # proc:shape@v2


def planted(counts=(95, 100, 0.02), key=PID, best=(98, 100)):
    """best at 98 of 100; the procedure at a mean 0.0002 a trial passes the 0.8 bar first."""
    stats = Stats()
    stats.add("t", BEST, *best)
    s, n, c = counts
    stats.add("t", key, s, n, cost_usd=c)
    return stats


def ok(text, input_tokens, output_tokens):
    return lambda messages: Completion(text, input_tokens, output_tokens)


def fail(message="outage"):
    def script(messages):
        raise ProviderError(message)
    return script


SCRIPT = {CHEAP: ok("cheap answer", 4000, 1000), BEST: ok("strong answer", 55, 12)}


class Harness:
    """An executor on a planted task with a scripted provider, a monitor and fixed time."""

    def __init__(self, script=None, task=None, stats=None, registry=REGISTRY):
        self.task = Task("t", bar=0.8, min_samples=10) if task is None else task
        router = Router(registry, {self.task.name: self.task},
                        planted() if stats is None else stats)
        self.provider = FakeProvider(dict(SCRIPT) if script is None else script)
        self.monitor = Monitor()
        self.ids = []
        ticks = iter(0.5 * i for i in range(1000))  # each clock read is 500 ms after the last
        self.executor = Executor(router, self.provider, monitor=self.monitor,
                                 clock=lambda: next(ticks), now=lambda: TS,
                                 id_factory=self._id)

    def _id(self):
        self.ids.append("call-1")
        return "call-1"

    def call(self, messages=None, **kw):
        return self.executor.call("t", msgs() if messages is None else messages, **kw)


def cost(model, input_tokens, output_tokens):
    return REGISTRY.get(model).cost(input_tokens, output_tokens)


def record(model, attempt, final, outcome, tokens=(0, 0), error=None, latency=500.0,
           value=None, family=None, flavor="cost_effective", **extra):
    if value is None:
        value = cost(model, *tokens) if outcome != "error" else 0.0
    rec = {
        "ts": TS, "call_id": "call-1", "task": "t", "flavor": flavor, "model": model,
        "family": REGISTRY.get(model).family if family is None else family,
        "attempt": attempt, "final": final, "outcome": outcome, "error": error,
        "latency_ms": latency, "input_tokens": tokens[0], "output_tokens": tokens[1],
        "cost_usd": value, "routing_cost_usd": value if flavor == "cost_effective" else 0.0,
        "below_bar": False, "basis": "measured", "tags": {}, "slice": None,
        "prompt_tokens": 1, "prompt_tokens_estimated": True,
    }
    rec.update(extra)
    return rec


def model_call(attempt, outcome="ok", tokens=(4000, 1000), error=None, model=CHEAP, **kw):
    return record(model, attempt, False, outcome, tokens, error, procedure="poll",
                  procedure_version="v1", **kw)


def closing(attempt, final, outcome, error=None, latency=1500.0, model_calls=1, tool_calls=3,
            tool_cost=0.0005, model=PID, family="fam-b", name="poll", version="v1", **kw):
    value = 0.0 if tool_cost is None else tool_cost
    return record(model, attempt, final, outcome, (0, 0), error, latency, value, family,
                  procedure=name, procedure_version=version, model_calls=model_calls,
                  tool_calls=tool_calls, tool_cost_usd=tool_cost, **kw)


def route(decision):
    return (decision.primary, *decision.fallbacks)


# --- guards: without procedures every route and record is v1.577's ------------------------

def test_guard_the_demo_log_keeps_its_bytes(tmp_path):
    run_demo(tmp_path / "demo")
    data = (tmp_path / "demo" / "calls.jsonl").read_bytes()
    assert hashlib.sha256(data).hexdigest() == DEMO_CALLS_SHA256


def test_guard_without_procedures_a_planted_procedure_is_never_run():
    h = Harness()
    result = h.call()
    assert (result.model, result.text) == (BEST, "strong answer")
    assert route(result.decision) == (BEST,)
    assert [c.model_id for c in result.decision.candidates] == [MODEL, CHEAP, BEST]
    assert h.provider.calls == [(BEST, msgs())]
    assert h.monitor.records == [record(BEST, 0, True, "ok", (55, 12))]
    assert list(h.monitor.records[0]) == V1_577_KEYS


def test_guard_call_delegated_takes_no_procedures():
    assert "procedures" not in inspect.signature(Executor.call_delegated).parameters


# --- the keyword and its check (7 v1.578) ---------------------------------------------------

def test_procedures_is_a_keyword_after_signals_defaulting_to_empty():
    # v1.623 (row POL1b): `policy` follows it, so the two are read by name
    params = list(inspect.signature(Executor.call).parameters.values())
    at = [p.name for p in params].index("procedures")
    assert [p.name for p in params[at - 1:at + 1]] == ["signals", "procedures"]
    assert params[at].kind is inspect.Parameter.KEYWORD_ONLY and params[at].default == ()


@pytest.mark.parametrize("value", ["poll", {PID: POLL}, [POLL, "x"], None])
def test_bad_procedures_raise_before_any_call_or_record(value):
    h = Harness()
    with pytest.raises(ValueError, match="^procedures must be a list or tuple of Procedure"):
        h.call(procedures=value)
    assert (h.provider.calls, h.monitor.records, h.ids) == ([], [], [])


def test_an_empty_list_routes_and_records_as_without_procedures():
    h = Harness()
    result = h.call(procedures=[])
    assert route(result.decision) == (BEST,)
    assert h.monitor.records == [record(BEST, 0, True, "ok", (55, 12))]


# --- a procedure route to success -------------------------------------------------------------

def test_a_procedure_primary_runs_its_model_call_and_closes_ok():
    h = Harness()
    result = h.call(procedures=[POLL])
    assert route(result.decision) == (PID, BEST)
    assert (result.model, result.text) == (PID, "shaped cheap answer")
    assert h.provider.calls == [(CHEAP, [{"role": "user", "content": "summarize: hi"}])]
    assert result.attempts == (
        Attempt(CHEAP, "ok", None, 500.0, 4000, 1000, cost(CHEAP, 4000, 1000)),
        Attempt(PID, "ok", None, 1500.0, 0, 0, 0.0005),
    )
    assert h.monitor.records == [model_call(0), closing(1, True, "ok")]


def test_the_procedure_keys_follow_slice_in_this_order():
    h = Harness()
    h.call(procedures=[POLL])
    first, last = h.monitor.records
    assert list(first) == CALL_KEYS
    assert list(last) == CLOSING_KEYS


def test_a_procedure_without_a_model_makes_no_provider_call():
    h = Harness(stats=planted((95, 100, 0.01), CODE.id))
    result = h.call(procedures=[CODE])
    assert (result.model, result.text) == ("proc:shape@v2", "shaped in code")
    assert h.provider.calls == []
    assert h.monitor.records == [
        closing(0, True, "ok", latency=500.0, model_calls=0, tool_calls=2, tool_cost=0.0,
                model="proc:shape@v2", family="", name="shape", version="v2")]


def test_cost_blind_records_the_tool_cost_with_no_routing_cost():
    h = Harness()
    result = h.call(procedures=[POLL], flavor="cost_blind", exclude_models=[BEST])
    assert route(result.decision) == (PID,)
    assert h.monitor.records == [model_call(0, flavor="cost_blind"),
                                 closing(1, True, "ok", flavor="cost_blind")]
    assert h.monitor.records[1]["cost_usd"] == 0.0005
    assert h.monitor.records[1]["routing_cost_usd"] == 0.0


def test_a_variant_model_of_a_procedure_gets_its_provider_options():
    high = CHEAP + "@high"
    registry = Registry([
        Model(CHEAP, "fam-b", 0.1, 0.2, 10_000),
        Model(high, "fam-b", 0.1, 0.2, 10_000,
              variant=Variant("high", provider_options={"reasoning_effort": "high"})),
        Model(BEST, "fam-c", 10.0, 30.0, 100_000),
    ])
    p = proc(model=high)
    h = Harness({high: ok("cheap answer", 4000, 1000), BEST: ok("strong answer", 55, 12)},
                stats=planted(key=p.id), registry=registry)
    result = h.call(procedures=[p])
    assert result.model == "proc:poll@v1+fiction/cheap@high"
    assert [model for model, _ in h.provider.calls] == [high]
    assert h.provider.call_options == [{"reasoning_effort": "high"}]


# --- failed runs fall back ----------------------------------------------------------------------

def test_a_procedure_that_raises_is_an_error_attempt_and_falls_back():
    h = Harness()
    result = h.call(procedures=[proc(boom)])
    assert (result.model, result.text) == (BEST, "strong answer")
    assert h.provider.calls == [(BEST, msgs())]
    assert h.monitor.records == [
        closing(0, False, "error", "RuntimeError: boom", latency=500.0, model_calls=0,
                tool_calls=None, tool_cost=None),
        record(BEST, 1, True, "ok", (55, 12)),
    ]


def test_a_call_over_max_model_calls_is_an_error_after_the_calls_it_made():
    def greedy(value, call):
        for _ in range(3):
            call(value)
        return ProcedureResult("never")

    h = Harness()
    result = h.call(procedures=[proc(greedy)])
    assert result.model == BEST
    assert [model for model, _ in h.provider.calls] == [CHEAP, CHEAP, BEST]
    assert h.monitor.records == [
        model_call(0), model_call(1),
        closing(2, False, "error", f"ProcedureLimitError: {PID}: model call 3 is over "
                "max_model_calls 2", latency=2500.0, model_calls=2, tool_calls=None,
                tool_cost=None),
        record(BEST, 3, True, "ok", (55, 12)),
    ]


def test_tool_calls_over_the_bound_or_a_wrong_return_value_is_an_error():
    over = proc(lambda value, call: ProcedureResult("x", tool_calls=6, tool_cost_usd=0.1))
    wrong = proc(lambda value, call: "x")
    for p, error in ((over, f"ProcedureLimitError: {PID}: 6 tool calls are over max_tool_calls 5"),
                     (wrong, f"ValueError: {PID}: fn must return a ProcedureResult, got str")):
        h = Harness()
        assert h.call(procedures=[p]).model == BEST
        assert h.monitor.records[0] == closing(0, False, "error", error, latency=500.0,
                                               model_calls=0, tool_calls=None, tool_cost=None)


def test_a_provider_error_is_raised_into_fn_which_may_call_again():
    outage = ProviderError("outage")
    seen, caught = [], []

    def flaky(messages):
        seen.append(messages)
        if len(seen) == 1:
            raise outage
        return Completion("cheap answer", 4000, 1000)

    def retry(value, call):
        try:
            return ProcedureResult(call(value))
        except ProviderError as exc:
            caught.append(exc)
            return ProcedureResult(call(value), tool_calls=1, tool_cost_usd=0.0001)

    h = Harness({CHEAP: flaky, BEST: ok("strong answer", 55, 12)})
    result = h.call(procedures=[proc(retry)])
    assert caught == [outage] and caught[0] is outage
    assert (result.model, result.text) == (PID, "cheap answer")
    assert h.monitor.records == [
        model_call(0, "error", (0, 0), "ProviderError: outage"), model_call(1),
        closing(2, True, "ok", latency=2500.0, model_calls=2, tool_calls=1, tool_cost=0.0001),
    ]


def test_a_provider_error_fn_lets_through_fails_the_entry():
    h = Harness({CHEAP: fail(), BEST: ok("strong answer", 55, 12)})
    result = h.call(procedures=[proc(lambda value, call: ProcedureResult(call(value)))])
    assert result.model == BEST
    assert h.monitor.records == [
        model_call(0, "error", (0, 0), "ProviderError: outage"),
        closing(1, False, "error", "ProviderError: outage", model_calls=1, tool_calls=None,
                tool_cost=None),
        record(BEST, 2, True, "ok", (55, 12)),
    ]


def test_validate_applies_to_the_output_and_an_invalid_one_falls_back_at_its_tool_cost():
    checked = []

    def validate(text):
        checked.append(text)
        return text.startswith("strong")

    h = Harness()
    result = h.call(procedures=[POLL], validate=validate)
    assert checked == ["shaped cheap answer", "strong answer"]
    assert result.model == BEST
    assert h.monitor.records == [
        model_call(0),
        closing(1, False, "invalid", "validation failed"),
        record(BEST, 2, True, "ok", (55, 12)),
    ]
    # as the last entry an invalid run is final, at its tool cost (review iter-425 nit 3)
    h = Harness()
    with pytest.raises(AllModelsFailed) as info:
        h.call(procedures=[POLL], validate=validate, exclude_models=[BEST])
    assert info.value.attempts[-1] == Attempt(PID, "invalid", "validation failed", 1500.0, 0, 0,
                                              0.0005)
    assert h.monitor.records == [model_call(0), closing(1, True, "invalid", "validation failed")]


def test_a_procedure_as_the_last_entry_ends_in_all_models_failed():
    h = Harness()
    with pytest.raises(AllModelsFailed, match="^all 1 routed models failed for task 't'$") as info:
        h.call(procedures=[proc(boom)], exclude_models=[BEST])
    assert route(info.value.decision) == (PID,)
    assert info.value.attempts == (Attempt(PID, "error", "RuntimeError: boom", 500.0, 0, 0, 0.0),)
    assert h.monitor.records == [
        closing(0, True, "error", "RuntimeError: boom", latency=500.0, model_calls=0,
                tool_calls=None, tool_cost=None)]


def test_the_procedure_gets_a_copy_so_its_edits_never_reach_a_later_entry():
    received = []

    def editing(value, call):
        received.append(value)
        value[0]["content"] = "raw payload"
        value.append({"role": "assistant", "content": "raw payload"})
        raise RuntimeError("after the edit")

    messages = msgs()
    h = Harness()
    h.call(messages, procedures=[proc(editing)])
    assert received[0] is not messages
    assert messages == msgs()
    assert h.provider.calls == [(BEST, msgs())]


# --- what propagates --------------------------------------------------------------------------

def test_a_provider_bug_propagates_even_when_fn_catches_it():
    bug = KeyError("bug")

    def broken(messages):
        raise bug

    def swallow(value, call):
        for _ in range(2):  # the second call raises the bug again without reaching the provider
            try:
                call(value)
            except KeyError as exc:
                assert exc is bug
        return ProcedureResult("swallowed")

    h = Harness({CHEAP: broken, BEST: ok("strong answer", 55, 12)})
    with pytest.raises(KeyError) as info:
        h.call(procedures=[proc(swallow)])
    assert info.value is bug
    assert [model for model, _ in h.provider.calls] == [CHEAP]
    assert h.monitor.records == []


def test_an_exception_from_validate_and_a_keyboard_interrupt_propagate():
    def bad_check(text):
        raise ZeroDivisionError("check")

    h = Harness()
    with pytest.raises(ZeroDivisionError):
        h.call(procedures=[POLL], validate=bad_check)
    assert h.monitor.records == [model_call(0)]

    def interrupted(value, call):
        raise KeyboardInterrupt

    h = Harness()
    with pytest.raises(KeyboardInterrupt):
        h.call(procedures=[proc(interrupted)])
    assert h.monitor.records == []


def test_messages_that_cannot_be_copied_raise_before_the_run_with_no_record():
    ran = []
    h = Harness()
    messages = [{"role": "user", "content": "hi", "extra": (x for x in "ab")}]
    with pytest.raises(TypeError):
        h.call(messages, procedures=[proc(lambda value, call: ran.append(value))])
    assert (ran, h.provider.calls, h.monitor.records) == ([], [], [])


def test_on_a_retry_same_task_the_procedure_keys_come_before_the_per_success_estimate():
    # review iter-425 should-fix 1: the 8.1 v1.567 key stays last, on both records
    h = Harness(task=Task("t", bar=0.8, min_samples=10, failure_policy="retry_same"))
    result = h.call(procedures=[POLL])
    assert result.model == PID
    lb = next(c.quality_lb for c in result.decision.candidates if c.model_id == PID)
    estimate = result.decision.expected_cost_per_success_usd
    assert estimate == (0.02 / 100) / lb
    first, last = h.monitor.records
    assert list(first) == CALL_KEYS + ["expected_cost_per_success_usd"]
    assert list(last) == CLOSING_KEYS + ["expected_cost_per_success_usd"]
    assert first["expected_cost_per_success_usd"] == last["expected_cost_per_success_usd"] == estimate


# --- below-bar fallback and the report (8.1 and 8.3 v1.578) -----------------------------------

def test_a_procedure_below_bar_fallback_marks_both_its_records():
    task = Task("t", bar=0.8, min_samples=10, fallback_below_bar=True)
    h = Harness({CHEAP: ok("cheap answer", 4000, 1000), BEST: fail()}, task=task,
                stats=planted((70, 100, 0.02)))
    result = h.call(procedures=[POLL])
    assert route(result.decision) == (BEST, PID)
    assert result.decision.below_bar_fallbacks == (PID,)
    assert result.model == PID
    first, call_rec, last = h.monitor.records
    assert "below_bar_fallback" not in first
    assert call_rec["below_bar_fallback"] is True and last["below_bar_fallback"] is True
    at = CALL_KEYS.index("below_bar") + 1
    assert list(call_rec) == CALL_KEYS[:at] + ["below_bar_fallback"] + CALL_KEYS[at:]
    assert list(last) == CLOSING_KEYS[:at] + ["below_bar_fallback"] + CLOSING_KEYS[at:]


def test_report_charges_the_tool_cost_to_the_procedure_and_the_model_call_to_its_model():
    h = Harness()
    h.call(procedures=[POLL])
    rows = {row["group"]: row for row in report(h.monitor.records, by="model")}
    assert set(rows) == {PID, CHEAP}
    assert rows[PID]["cost_usd"] == 0.0005 and rows[PID]["attempts"] == 1
    assert rows[CHEAP]["cost_usd"] == round(cost(CHEAP, 4000, 1000), 6)
    assert rows[CHEAP]["calls"] == 0 and rows[PID]["calls"] == 1
    # 8.3 v1.579 (row RPT2) lifts v1.578's limit: the closing record is attempt 1 but belongs to
    # the call's first entry, so the call is no fallback call
    assert rows[PID]["fallback_calls"] == 0 and rows[PID]["fallback_rate"] == 0.0
    (task_row,) = report(h.monitor.records, by="task")
    assert task_row["cost_usd"] == round(cost(CHEAP, 4000, 1000) + 0.0005, 6)
