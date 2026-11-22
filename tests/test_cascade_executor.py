"""DESIGN 7 and 8.1 v1.532 and v1.537 (row ESC2c): cascades, part 3, the executor and records.

`Executor.call(..., signals=...)` routes with `cascades=True`, checks before any call that every
cascade entry of the route has a callable signal, runs a cascade entry's cheap model, hands the
call up to a fresh strong call when the signal is truthy or the cheap model raises
`ProviderError`, applies `validate` to the entry's result, and records `cascade` and `escalated`
right after `slice` on the cascade's attempts. Without `signals` every route and record is
v1.536's. The contract tests were written under strict xfail and the implementing commit removed
the marks; the unmarked guards pin what v1.537 keeps and pass before and after it.
"""

import hashlib
import inspect
import re

import pytest

from model_routing import (
    AllModelsFailed, Attempt, Cascade, Completion, Executor, FakeProvider, Model, Monitor,
    ProviderError, Registry, Router, Stats, Task, run_demo,
)


CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
REGISTRY = Registry([
    Model(CHEAP, "fam-a", 1.0, 2.0, 10_000),
    Model(MID, "fam-b", 3.0, 6.0, 10_000),
    Model(BEST, "fam-c", 10.0, 30.0, 100_000),
])
C = Cascade(CHEAP, BEST, "sig")
CID = "fiction/cheap>fiction/best@sig"
MESSAGES = [{"role": "user", "content": "hi"}]  # 2 characters, estimated at 1 token
TS = "2026-11-20T00:00:00Z"

# the demo's calls.jsonl at 6dae5ba (v1.536), computed in iter 383 before any v1.537 code
V1_536_DEMO_CALLS_SHA256 = "4f111326781939140bebe04e0841a66306cac48492bc6c95f4bc2211fa92b351"

V1_536_KEYS = ["ts", "call_id", "task", "flavor", "model", "family", "attempt", "final",
               "outcome", "error", "latency_ms", "input_tokens", "output_tokens", "cost_usd",
               "routing_cost_usd", "below_bar", "basis", "tags", "slice", "prompt_tokens",
               "prompt_tokens_estimated"]
CASCADE_KEYS = V1_536_KEYS[:19] + ["cascade", "escalated"] + V1_536_KEYS[19:]


def with_bbf(keys):
    at = keys.index("below_bar") + 1
    return keys[:at] + ["below_bar_fallback"] + keys[at:]


def planted_stats(cascade=(95, 100, 20), key="t"):
    """cheap 60/100 at 1200 in and 300 out per call, best 98/100, the cascade's own counts.

    With the task's bar 0.8 the cascade (0.0066) and best (0.016) pass and the cheap model is
    below the bar, so `cost_effective` routes (cascade, best) and `cost_blind`, by bound,
    (best, cascade), as tests/test_cascade_candidates.py computes by hand.
    """
    stats = Stats()
    stats.add(key, CHEAP, 60, 100, input_tokens=120_000, output_tokens=30_000)
    stats.add(key, BEST, 98, 100)
    s, n, e = cascade
    stats.add(key, CID, s, n, escalated=e)
    return stats


def ok(text, input_tokens, output_tokens):
    return lambda messages: Completion(text, input_tokens, output_tokens)


def fail(message="outage"):
    def script(messages):
        raise ProviderError(message)
    return script


class Harness:
    """An executor on a planted task with a scripted provider, a monitor and fixed time."""

    def __init__(self, script, task=None, stats=None):
        self.task = Task("t", bar=0.8, min_samples=10, cascades=(C,)) if task is None else task
        router = Router(REGISTRY, {self.task.name: self.task},
                        planted_stats() if stats is None else stats)
        self.provider = FakeProvider(script)
        self.monitor = Monitor()
        self.ids = []
        ticks = iter(0.5 * i for i in range(1000))  # every attempt takes 500 ms
        self.executor = Executor(router, self.provider, monitor=self.monitor,
                                 clock=lambda: next(ticks), now=lambda: TS,
                                 id_factory=self._id)

    def _id(self):
        self.ids.append("call-1")
        return "call-1"

    def call(self, **kw):
        return self.executor.call("t", MESSAGES, **kw)


def cost(model, input_tokens, output_tokens):
    return REGISTRY.get(model).cost(input_tokens, output_tokens)


def record(model, attempt, final, outcome, tokens=(0, 0), error=None, flavor="cost_effective",
           **extra):
    value = cost(model, *tokens) if outcome != "error" else 0.0
    rec = {
        "ts": TS, "call_id": "call-1", "task": "t", "flavor": flavor, "model": model,
        "family": REGISTRY.get(model).family, "attempt": attempt, "final": final,
        "outcome": outcome, "error": error, "latency_ms": 500.0,
        "input_tokens": tokens[0], "output_tokens": tokens[1], "cost_usd": value,
        "routing_cost_usd": value if flavor == "cost_effective" else 0.0,
        "below_bar": False, "basis": "measured", "tags": {}, "slice": None,
        "prompt_tokens": 1, "prompt_tokens_estimated": True,
    }
    rec.update(extra)
    return rec


def route(decision):
    return (decision.primary, *decision.fallbacks)


# --- guards: without signals every route and record is v1.536's ---------------------------

def test_guard_the_demo_log_keeps_its_v1_536_bytes(tmp_path):
    run_demo(tmp_path / "demo")
    data = (tmp_path / "demo" / "calls.jsonl").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V1_536_DEMO_CALLS_SHA256


def test_guard_without_signals_a_planted_cascade_is_never_run():
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: ok("strong answer", 55, 12)})
    result = h.executor.call("t", MESSAGES)
    assert (result.model, result.text) == (BEST, "strong answer")
    assert route(result.decision) == (BEST,)
    assert [c.model_id for c in result.decision.candidates] == [CHEAP, MID, BEST]
    assert h.provider.calls == [(BEST, MESSAGES)]
    assert h.monitor.records == [record(BEST, 0, True, "ok", (55, 12))]
    assert list(h.monitor.records[0]) == V1_536_KEYS


def test_guard_call_delegated_takes_no_signals():
    assert "signals" not in inspect.signature(Executor.call_delegated).parameters


# --- the signals keyword and its checks ---------------------------------------------------

@pytest.mark.parametrize("value", [[], "sig", 1, ("sig",), {"sig"}])
def test_signals_that_is_no_mapping_is_a_value_error_before_select(value):
    h = Harness({})
    with pytest.raises(ValueError, match="^signals must be None or a mapping, got "):
        h.executor.call("no-such-task", MESSAGES, signals=value)
    assert (h.provider.calls, h.monitor.records, h.ids) == ([], [], [])


def test_signals_is_a_keyword_after_slice():
    # v1.578 (row PROC1c): `procedures` follows it, so the three are read by name
    params = list(inspect.signature(Executor.call).parameters.values())
    at = [p.name for p in params].index("signals")
    assert [p.name for p in params[at - 2:at + 1]] == ["prompt_tokens", "slice", "signals"]
    assert params[at].kind is inspect.Parameter.KEYWORD_ONLY and params[at].default is None


def test_with_signals_the_route_holds_the_cascade():
    h = Harness({CHEAP: ok("cheap answer", 40, 9)})
    result = h.call(signals={"sig": lambda text: False})
    assert [c.model_id for c in result.decision.candidates] == [CHEAP, MID, BEST, CID]
    assert route(result.decision) == (CID, BEST)


@pytest.mark.parametrize("signals", [{}, {"other": lambda text: False}, {"sig": "no"},
                                     {"sig": None}])
def test_a_missing_or_uncallable_signal_is_a_value_error_before_any_call_and_record(signals):
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: ok("strong answer", 55, 12)})
    with pytest.raises(ValueError, match=re.escape(CID)) as caught:
        h.call(signals=signals)
    assert "sig" in str(caught.value)
    assert (h.provider.calls, h.monitor.records, h.ids) == ([], [], [])


def test_a_cascade_fallback_entry_needs_its_signal_too():
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: ok("strong answer", 55, 12)})
    with pytest.raises(ValueError, match=re.escape(CID)):
        h.call(flavor="cost_blind", signals={})
    assert (h.provider.calls, h.monitor.records, h.ids) == ([], [], [])


def test_a_mapping_with_no_routed_cascade_runs_as_without_signals():
    plain = Task("t", bar=0.8, min_samples=10)
    stats = Stats()
    stats.add("t", BEST, 98, 100)
    h = Harness({BEST: ok("strong answer", 55, 12)}, task=plain, stats=stats)
    result = h.call(signals={})
    assert (result.model, route(result.decision)) == (BEST, (BEST,))
    assert h.monitor.records == [record(BEST, 0, True, "ok", (55, 12))]
    assert list(h.monitor.records[0]) == V1_536_KEYS


# --- running a cascade entry ----------------------------------------------------------------

def test_the_cheap_text_is_kept_when_the_signal_is_falsy():
    seen = []
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: ok("strong answer", 55, 12)})
    result = h.call(signals={"sig": lambda text: seen.append(text) or 0})
    assert seen == ["cheap answer"]
    assert (result.call_id, result.text, result.model) == ("call-1", "cheap answer", CHEAP)
    assert result.attempts == (Attempt(CHEAP, "ok", None, 500.0, 40, 9, cost(CHEAP, 40, 9)),)
    assert h.provider.calls == [(CHEAP, MESSAGES)]
    # (40 * 1 + 9 * 2) / 1e6
    assert h.monitor.records[0]["cost_usd"] == pytest.approx(58e-6, rel=1e-12)
    assert h.monitor.records == [
        record(CHEAP, 0, True, "ok", (40, 9), cascade=CID, escalated=False)]
    assert list(h.monitor.records[0]) == CASCADE_KEYS


def test_a_truthy_signal_hands_up_to_a_fresh_strong_call():
    validated = []
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: ok("strong answer", 55, 12)})
    result = h.call(signals={"sig": lambda text: "cheap" in text},
                    validate=lambda text: validated.append(text) or True)
    assert (result.text, result.model) == ("strong answer", BEST)
    # the strong model starts fresh on the caller's messages, never the cheap model's output
    assert h.provider.calls == [(CHEAP, MESSAGES), (BEST, MESSAGES)]
    assert h.provider.calls[1][1] is MESSAGES
    # validate sees the entry's result only, not the handed-up cheap text
    assert validated == ["strong answer"]
    assert result.attempts == (
        Attempt(CHEAP, "ok", None, 500.0, 40, 9, cost(CHEAP, 40, 9)),
        Attempt(BEST, "ok", None, 500.0, 55, 12, cost(BEST, 55, 12)))
    assert h.monitor.records == [
        record(CHEAP, 0, False, "ok", (40, 9), cascade=CID, escalated=True),
        record(BEST, 1, True, "ok", (55, 12), cascade=CID, escalated=True)]
    # the strong attempt is charged to the strong model: (55 * 10 + 12 * 30) / 1e6
    assert h.monitor.records[1]["family"] == "fam-c"
    assert h.monitor.records[1]["cost_usd"] == pytest.approx(910e-6, rel=1e-12)
    assert [list(r) for r in h.monitor.records] == [CASCADE_KEYS, CASCADE_KEYS]


def test_a_cheap_provider_error_hands_up_without_calling_the_signal():
    def signal(text):
        raise AssertionError("the signal must not run on a provider error")
    h = Harness({CHEAP: fail(), BEST: ok("strong answer", 55, 12)})
    result = h.call(signals={"sig": signal})
    assert (result.text, result.model) == ("strong answer", BEST)
    assert h.monitor.records == [
        record(CHEAP, 0, False, "error", error="ProviderError: outage",
               cascade=CID, escalated=True),
        record(BEST, 1, True, "ok", (55, 12), cascade=CID, escalated=True)]


def test_validate_rejecting_the_kept_cheap_text_moves_on_without_escalating():
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: ok("strong answer", 55, 12)})
    result = h.call(signals={"sig": lambda text: False},
                    validate=lambda text: text == "strong answer")
    assert (result.text, result.model) == ("strong answer", BEST)
    # the second attempt is best as the route's next entry, so it has no cascade keys
    assert h.monitor.records == [
        record(CHEAP, 0, False, "invalid", (40, 9), error="validation failed",
               cascade=CID, escalated=False),
        record(BEST, 1, True, "ok", (55, 12))]
    assert [list(r) for r in h.monitor.records] == [CASCADE_KEYS, V1_536_KEYS]


def test_validate_applies_to_the_strong_result():
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: ok("strong answer", 55, 12)})
    with pytest.raises(AllModelsFailed) as caught:
        h.call(signals={"sig": lambda text: True}, validate=lambda text: False)
    assert [(a.model, a.outcome) for a in caught.value.attempts] == [
        (CHEAP, "ok"), (BEST, "invalid"), (BEST, "invalid")]
    assert route(caught.value.decision) == (CID, BEST)
    assert h.monitor.records == [
        record(CHEAP, 0, False, "ok", (40, 9), cascade=CID, escalated=True),
        record(BEST, 1, False, "invalid", (55, 12), error="validation failed",
               cascade=CID, escalated=True),
        record(BEST, 2, True, "invalid", (55, 12), error="validation failed")]


def test_a_cascade_as_the_last_entry_ends_the_call_on_its_strong_attempt():
    h = Harness({CHEAP: fail(), BEST: fail("down")})
    with pytest.raises(AllModelsFailed) as caught:
        h.call(flavor="cost_blind", signals={"sig": lambda text: False})
    assert route(caught.value.decision) == (BEST, CID)
    assert [a.model for a in caught.value.attempts] == [BEST, CHEAP, BEST]
    blind = dict(flavor="cost_blind")
    assert h.monitor.records == [
        record(BEST, 0, False, "error", error="ProviderError: down", **blind),
        record(CHEAP, 1, False, "error", error="ProviderError: outage",
               cascade=CID, escalated=True, **blind),
        record(BEST, 2, True, "error", error="ProviderError: down",
               cascade=CID, escalated=True, **blind)]


def test_a_signal_exception_propagates_with_no_record_of_its_attempt():
    def signal(text):
        raise RuntimeError("boom")
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: fail("down")})
    with pytest.raises(RuntimeError, match="boom"):
        h.call(flavor="cost_blind", signals={"sig": signal})
    assert h.provider.calls == [(BEST, MESSAGES), (CHEAP, MESSAGES)]
    assert h.monitor.records == [
        record(BEST, 0, False, "error", error="ProviderError: down", flavor="cost_blind")]


def test_a_signal_exception_on_the_first_entry_leaves_no_record():
    # review iter-383 nit 2: nothing was recorded before the cheap attempt, so nothing is
    def signal(text):
        raise RuntimeError("boom")
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: ok("strong answer", 55, 12)})
    with pytest.raises(RuntimeError, match="boom"):
        h.call(signals={"sig": signal})
    assert h.provider.calls == [(CHEAP, MESSAGES)]
    assert h.monitor.records == []


def test_a_kept_cheap_text_that_fails_validate_on_the_last_entry_ends_the_call():
    # review iter-383 nit 3: the cascade is the route's last entry, so its invalid kept
    # cheap attempt is final and the call fails without a hand-up
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: fail("down")})
    with pytest.raises(AllModelsFailed) as caught:
        h.call(flavor="cost_blind", signals={"sig": lambda text: False},
               validate=lambda text: False)
    assert route(caught.value.decision) == (BEST, CID)
    assert h.provider.calls == [(BEST, MESSAGES), (CHEAP, MESSAGES)]
    assert h.monitor.records == [
        record(BEST, 0, False, "error", error="ProviderError: down", flavor="cost_blind"),
        record(CHEAP, 1, True, "invalid", (40, 9), error="validation failed",
               flavor="cost_blind", cascade=CID, escalated=False)]


# --- records: below_bar_fallback follows the route entry, slices ----------------------------

def test_below_bar_fallback_follows_the_route_entry_not_the_model_called():
    calls = []
    def best(messages):
        calls.append(1)
        if len(calls) == 1:
            raise ProviderError("down")
        return Completion("strong answer", 55, 12)
    t = Task("t", bar=0.8, min_samples=10, cascades=(C,), fallback_below_bar=True)
    # the cascade at 50/100 is under the bar, below the cheap model's 60/100 by bound
    h = Harness({CHEAP: fail(), BEST: best}, task=t, stats=planted_stats(cascade=(50, 100, 10)))
    result = h.call(signals={"sig": lambda text: True})
    assert route(result.decision) == (BEST, CHEAP, CID)
    assert result.decision.below_bar_fallbacks == (CHEAP, CID)
    assert (result.text, result.model) == ("strong answer", BEST)
    assert h.monitor.records == [
        record(BEST, 0, False, "error", error="ProviderError: down"),
        record(CHEAP, 1, False, "error", error="ProviderError: outage",
               below_bar_fallback=True),
        record(CHEAP, 2, False, "error", error="ProviderError: outage",
               below_bar_fallback=True, cascade=CID, escalated=True),
        # best is the primary entry too, but this attempt is the cascade entry's
        record(BEST, 3, True, "ok", (55, 12), below_bar_fallback=True,
               cascade=CID, escalated=True)]
    assert [list(r) for r in h.monitor.records] == [
        V1_536_KEYS, with_bbf(V1_536_KEYS), with_bbf(CASCADE_KEYS), with_bbf(CASCADE_KEYS)]


def test_a_sliced_call_runs_the_tasks_cascades_on_the_slice_key():
    t = Task("t", bar=0.8, min_samples=10, cascades=(C,), slices={"s": {}})
    h = Harness({CHEAP: ok("cheap answer", 40, 9)}, task=t, stats=planted_stats(key="t@s"))
    result = h.call(slice="s", signals={"sig": lambda text: False})
    assert (result.decision.slice, route(result.decision)) == ("s", (CID, BEST))
    assert h.monitor.records == [
        record(CHEAP, 0, True, "ok", (40, 9), slice="s", cascade=CID, escalated=False)]
    assert list(h.monitor.records[0]) == CASCADE_KEYS
