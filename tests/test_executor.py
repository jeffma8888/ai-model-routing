"""Attempt fallback, cost attribution, injected dependencies, and JSON validation."""

from dataclasses import FrozenInstanceError

import pytest
from model_routing import (
    AllModelsFailed, Completion, Executor, FakeProvider, Monitor, NoModelClearsBar,
    ProviderError, Router, Stats, json_validator,
)


RECORD_TYPES = {
    "ts": str, "call_id": str, "task": str, "flavor": str, "model": str,
    "family": str, "attempt": int, "final": bool, "outcome": str,
    "latency_ms": float, "input_tokens": int, "output_tokens": int,
    "cost_usd": float, "routing_cost_usd": float, "below_bar": bool,
    "basis": str, "tags": dict,
}


def fail(message="outage"):
    def script(messages):
        raise ProviderError(message)
    return script


@pytest.fixture
def injected_executor():
    def make(router, provider, monitor=None, times=(1.0, 1.125, 2.0, 2.25, 3.0, 3.5)):
        ticks = iter(times)
        return Executor(router, provider, monitor=monitor, clock=lambda: next(ticks),
                        now=lambda: "2026-01-02T03:04:05Z", id_factory=lambda: "fixed-call")
    return make


def assert_record_schema(record):
    assert set(record) == set(RECORD_TYPES) | {"error"}
    for key, expected_type in RECORD_TYPES.items():
        assert type(record[key]) is expected_type, (key, record[key])
    assert record["error"] is None or isinstance(record["error"], str)
    assert all(type(k) is str and type(v) is str for k, v in record["tags"].items())


def test_executor_falls_back_on_providererror_and_records_exact_attempt_schema(router, injected_executor):
    monitor = Monitor()
    messages = [{"role": "user", "content": "judge"}]
    def second(received):
        assert received == messages
        assert len(monitor.records) == 1
        assert monitor.records[0]["outcome"] == "error"
        return Completion("accepted", 31, 7)
    provider = FakeProvider({"fiction/cheap": fail(), "fiction/mid": second})
    executor = injected_executor(router, provider, monitor)
    result = executor.call("judge", messages, tags={"suite": "tiny"})
    assert result.call_id == "fixed-call"
    assert result.text == "accepted" and result.model == "fiction/mid"
    assert isinstance(result.attempts, tuple) and len(result.attempts) == 2
    assert result.decision.primary == "fiction/cheap"
    first, last = result.attempts
    assert (first.model, first.outcome, first.input_tokens, first.output_tokens, first.cost_usd) == (
        "fiction/cheap", "error", 0, 0, 0.0)
    assert "ProviderError" in first.error and "outage" in first.error
    assert first.latency_ms == pytest.approx(125.0)
    assert last.latency_ms == pytest.approx(250.0)
    assert (last.model, last.outcome, last.error, last.input_tokens, last.output_tokens) == (
        "fiction/mid", "ok", None, 31, 7)
    assert last.cost_usd == pytest.approx(router.registry.get("fiction/mid").cost(31, 7))
    assert provider.calls == [("fiction/cheap", messages), ("fiction/mid", messages)]
    assert len(monitor.records) == 2
    for index, (record, attempt) in enumerate(zip(monitor.records, result.attempts)):
        assert_record_schema(record)
        assert record == {
            "ts": "2026-01-02T03:04:05Z", "call_id": "fixed-call", "task": "judge",
            "flavor": "cost_effective", "model": attempt.model,
            "family": router.registry.get(attempt.model).family,
            "attempt": index, "final": index == 1, "outcome": attempt.outcome,
            "error": attempt.error, "latency_ms": attempt.latency_ms,
            "input_tokens": attempt.input_tokens, "output_tokens": attempt.output_tokens,
            "cost_usd": attempt.cost_usd, "routing_cost_usd": attempt.cost_usd,
            "below_bar": False, "basis": "measured", "tags": {"suite": "tiny"},
        }


def test_executor_invalid_output_falls_back_and_bills_actual_tokens(router, injected_executor):
    provider = FakeProvider({"fiction/cheap": lambda _: Completion("bad", 70, 11),
                             "fiction/mid": lambda _: Completion('{"ok":true}', 90, 12)})
    monitor = Monitor()
    result = injected_executor(router, provider, monitor).call("judge", [], validate=json_validator("ok"))
    invalid, ok = result.attempts
    assert invalid.outcome == "invalid" and invalid.error == "validation failed"
    assert (invalid.input_tokens, invalid.output_tokens) == (70, 11)
    assert invalid.cost_usd == pytest.approx(router.registry.get("fiction/cheap").cost(70, 11))
    assert ok.outcome == "ok"
    assert [r["final"] for r in monitor.records] == [False, True]
    assert [r["outcome"] for r in monitor.records] == ["invalid", "ok"]
    for record in monitor.records:
        assert_record_schema(record)
        assert record["tags"] == {}


def test_executor_any_falsy_validator_result_triggers_fallback(router, injected_executor):
    seen = []
    def validate(text):
        seen.append(text)
        return [] if text == "first" else {"valid": True}
    provider = FakeProvider({"fiction/cheap": lambda _: Completion("first", 1, 1),
                             "fiction/mid": lambda _: Completion("second", 2, 2)})
    result = injected_executor(router, provider).call("judge", [], validate=validate)
    assert seen == ["first", "second"]
    assert [a.outcome for a in result.attempts] == ["invalid", "ok"]


def test_executor_non_providererror_propagates_without_trying_fallback(router, injected_executor):
    error = RuntimeError("programming bug")
    def script(messages):
        raise error
    provider = FakeProvider({"fiction/cheap": script,
                             "fiction/mid": lambda _: Completion("should not run", 1, 1)})
    with pytest.raises(RuntimeError) as caught:
        injected_executor(router, provider).call("judge", [])
    assert caught.value is error
    assert provider.calls == [("fiction/cheap", [])]


def test_executor_all_models_failed_exposes_attempts_decision_and_final_flag(router, injected_executor):
    provider = FakeProvider({"fiction/cheap": fail("first"),
                             "fiction/mid": lambda _: Completion("invalid", 10, 5),
                             "fiction/best": fail("last")})
    monitor = Monitor()
    with pytest.raises(AllModelsFailed) as caught:
        injected_executor(router, provider, monitor).call("judge", [], validate=lambda _: False)
    error = caught.value
    assert isinstance(error.attempts, tuple)
    assert [a.outcome for a in error.attempts] == ["error", "invalid", "error"]
    assert [a.model for a in error.attempts] == ["fiction/cheap", "fiction/mid", "fiction/best"]
    assert error.decision.primary == "fiction/cheap"
    assert [r["final"] for r in monitor.records] == [False, False, True]
    assert [r["attempt"] for r in monitor.records] == [0, 1, 2]
    assert [a.latency_ms for a in error.attempts] == [125.0, 250.0, 500.0]
    for record in monitor.records:
        assert_record_schema(record)


def test_executor_stops_after_success_and_marks_only_attempt_final(router, injected_executor):
    provider = FakeProvider({"fiction/cheap": lambda _: Completion("ok", 1, 2)})
    monitor = Monitor()
    result = injected_executor(router, provider, monitor).call("judge", [])
    assert len(result.attempts) == len(provider.calls) == len(monitor.records) == 1
    assert monitor.records[0]["final"] is True


def test_executor_zero_fallbacks_exhausts_after_primary_failure(registry, task_factory, measured_stats, injected_executor):
    router = Router(registry, {"judge": task_factory(max_fallbacks=0)}, measured_stats)
    provider = FakeProvider({"fiction/cheap": fail()})
    monitor = Monitor()
    with pytest.raises(AllModelsFailed) as caught:
        injected_executor(router, provider, monitor).call("judge", [])
    assert len(caught.value.attempts) == 1
    assert monitor.records[0]["final"] is True


def test_executor_cost_blind_records_list_price_but_zero_routing_cost(router, injected_executor):
    provider = FakeProvider({"fiction/best": lambda _: Completion("bad", 17, 9),
                             "fiction/mid": lambda _: Completion("ok", 13, 4)})
    monitor = Monitor()
    result = injected_executor(router, provider, monitor).call(
        "judge", [], flavor="cost_blind", validate=lambda text: text == "ok")
    assert [a.model for a in result.attempts] == ["fiction/best", "fiction/mid"]
    for attempt, record in zip(result.attempts, monitor.records):
        assert_record_schema(record)
        assert record["flavor"] == "cost_blind"
        assert record["routing_cost_usd"] == 0.0
        expected = router.registry.get(attempt.model).cost(attempt.input_tokens, attempt.output_tokens)
        assert record["cost_usd"] == pytest.approx(expected)
        assert record["cost_usd"] > 0


def test_executor_passes_timeout_messages_and_select_options(registry, task_factory, measured_stats, injected_executor):
    task = task_factory(timeout_s=4.25)
    router = Router(registry, {"judge": task}, measured_stats)
    received = []
    class Provider:
        def complete(self, model_id, messages, timeout_s):
            received.append((model_id, messages, timeout_s))
            return Completion("ok", 1, 1)
    messages = [{"role": "user", "content": "hello"}]
    result = injected_executor(router, Provider()).call(
        "judge", messages, generator_model="fiction/cheap", exclude_models=("fiction/mid",))
    assert result.model == "fiction/best"
    assert received == [("fiction/best", messages, 4.25)]
    assert [c.reason for c in result.decision.candidates] == ["generator", "excluded_model", "passes"]


def test_executor_route_errors_propagate_without_provider_calls(registry, task_factory, injected_executor):
    router = Router(registry, {"judge": task_factory()}, Stats())
    provider = FakeProvider({})
    executor = injected_executor(router, provider)
    with pytest.raises(NoModelClearsBar):
        executor.call("judge", [])
    with pytest.raises(KeyError):
        executor.call("missing", [])
    with pytest.raises(ValueError):
        executor.call("judge", [], flavor="bad")
    assert provider.calls == []


@pytest.mark.parametrize("measured,basis", [(True, "measured"), (False, "prior")])
def test_executor_records_below_bar_and_selected_basis(registry, task_factory, priors, injected_executor, measured, basis):
    stats = Stats()
    if measured:
        stats.add("judge", "fiction/cheap", 1, 1)
    task = task_factory(on_no_model="best_available", prior_category="judging")
    router = Router(registry, {"judge": task}, stats, priors)
    provider = FakeProvider({m.id: lambda _: Completion("ok", 1, 1) for m in registry.models})
    monitor = Monitor()
    injected_executor(router, provider, monitor).call("judge", [])
    assert monitor.records[0]["below_bar"] is True
    assert monitor.records[0]["basis"] == basis


def test_attempt_and_call_result_are_frozen(router, injected_executor):
    provider = FakeProvider({"fiction/cheap": lambda _: Completion("ok", 1, 1)})
    result = injected_executor(router, provider).call("judge", [])
    with pytest.raises(FrozenInstanceError):
        result.model = "changed"
    with pytest.raises(FrozenInstanceError):
        result.attempts[0].outcome = "changed"


@pytest.mark.parametrize("text,required,expected", [
    ('{"answer":null,"reason":"yes"}', ("answer", "reason"), True),
    ('{"answer":false}', ("answer",), True),
    ('{"answer":1}', ("answer", "reason"), False),
    ('{}', (), True), ('[]', (), False), ('null', (), False),
    ('42', (), False), ('"string"', (), False), ('true', (), False),
    ('broken', (), False), ('{"answer":1} trailing', ("answer",), False),
])
def test_json_validator_requires_an_object_and_all_requested_keys(text, required, expected):
    assert json_validator(*required)(text) is expected


def test_executor_default_clock_now_and_id_produce_utc_timestamp_and_hex_id(router):
    from datetime import datetime, timedelta
    from uuid import UUID

    provider = FakeProvider({"fiction/cheap": lambda _: Completion("ok", 1, 1)})
    monitor = Monitor()
    result = Executor(router, provider, monitor=monitor).call("judge", [])
    assert UUID(hex=result.call_id).hex == result.call_id
    assert len(result.call_id) == 32
    timestamp = datetime.fromisoformat(monitor.records[0]["ts"].replace("Z", "+00:00"))
    assert timestamp.utcoffset() == timedelta(0)
    assert result.attempts[0].latency_ms >= 0.0
    assert_record_schema(monitor.records[0])
