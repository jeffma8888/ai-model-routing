"""Executor.call_delegated: run a delegate decision on its route (DESIGN 7, v1.11)."""

import pytest
from model_routing import (
    AllModelsFailed, Completion, Executor, FakeProvider, Monitor, ProviderError, Router,
    json_validator,
)

BRIEF = [{"role": "user", "content": "Brief: judge whether this one answer is faithful."}]


def fail(message="outage"):
    def script(messages):
        raise ProviderError(message)
    return script


class RecordingProvider:
    def __init__(self):
        self.timeouts = []

    def complete(self, model_id, messages, timeout_s):
        self.timeouts.append((model_id, timeout_s))
        return Completion("ok", 5, 1)


@pytest.fixture
def make_executor():
    def make(router, provider, monitor=None):
        ticks = iter(float(i) for i in range(100))
        return Executor(router, provider, monitor=monitor, clock=lambda: next(ticks),
                        now=lambda: "2026-01-02T03:04:05Z", id_factory=lambda: "fixed-call")
    return make


def delegate_decision(router, flavor="cost_effective"):
    if flavor == "cost_effective":
        decision = router.decide_delegation("judge", "fiction/best", flavor, context_tokens=5000,
                                            brief_tokens=100, result_tokens=20)
        assert (decision.reason, decision.model) == ("delegate_cheaper", "fiction/cheap")
    else:
        decision = router.decide_delegation("judge", "fiction/cheap", flavor, context_tokens=0,
                                            brief_tokens=100, result_tokens=20)
        assert (decision.reason, decision.model) == ("delegate_better", "fiction/best")
    assert decision.mode == "delegate"
    return decision


def order_of(decision):
    order = (decision.route.primary, *decision.route.fallbacks)
    assert len(order) >= 2
    return order


def test_call_delegated_runs_the_route_with_fallback_and_tags_every_record(router, make_executor):
    decision = delegate_decision(router)
    route = decision.route
    order = order_of(decision)
    monitor = Monitor()
    provider = FakeProvider({order[0]: fail(), order[1]: lambda m: Completion("done", 1100, 200)})
    tags = {"suite": "tiny"}
    result = make_executor(router, provider, monitor).call_delegated(decision, BRIEF, tags=tags)
    assert (result.call_id, result.text, result.model) == ("fixed-call", "done", order[1])
    assert result.decision is route
    assert [a.outcome for a in result.attempts] == ["error", "ok"]
    assert result.attempts[1].cost_usd == router.registry.get(order[1]).cost(1100, 200)
    assert provider.calls == [(order[0], BRIEF), (order[1], BRIEF)]
    assert tags == {"suite": "tiny"}
    assert len(monitor.records) == 2
    for index, record in enumerate(monitor.records):
        assert record["tags"] == {"suite": "tiny", "delegated": "true", "parent": "fiction/best"}
        assert (record["task"], record["flavor"], record["model"]) == (
            "judge", "cost_effective", order[index])
        assert (record["attempt"], record["final"]) == (index, index == 1)
        assert record["below_bar"] is route.below_bar is False
        assert record["basis"] == route.basis
        assert record["routing_cost_usd"] == record["cost_usd"]
        assert record["call_id"] == "fixed-call"


def test_call_delegated_uses_the_decided_route_without_selecting_again(router, make_executor,
                                                                       monkeypatch):
    decision = delegate_decision(router)

    def select(*args, **kwargs):
        raise AssertionError("select called again")
    monkeypatch.setattr(router, "select", select)
    router.stats.add("judge", "fiction/cheap", 0, 1000)
    provider = FakeProvider({"fiction/cheap": lambda m: Completion("ok", 10, 2)})
    result = make_executor(router, provider).call_delegated(decision, BRIEF)
    assert result.model == decision.route.primary == "fiction/cheap"


def test_call_delegated_passes_the_timeout_of_the_routers_task(registry, task_factory,
                                                               measured_stats, make_executor):
    task = task_factory(timeout_s=12.5)
    router = Router(registry, {task.name: task}, measured_stats)
    decision = delegate_decision(router)
    provider = RecordingProvider()
    make_executor(router, provider).call_delegated(decision, BRIEF)
    assert provider.timeouts == [(decision.route.primary, 12.5)]


def test_call_delegated_validates_and_falls_back_like_call(router, make_executor):
    decision = delegate_decision(router)
    order = order_of(decision)
    provider = FakeProvider({order[0]: lambda m: Completion("not json", 30, 4),
                             order[1]: lambda m: Completion('{"verdict": "ok"}', 30, 4)})
    monitor = Monitor()
    result = make_executor(router, provider, monitor).call_delegated(
        decision, BRIEF, validate=json_validator("verdict"))
    assert [a.outcome for a in result.attempts] == ["invalid", "ok"]
    assert result.attempts[0].cost_usd == router.registry.get(order[0]).cost(30, 4)
    assert [r["tags"] for r in monitor.records] == [
        {"delegated": "true", "parent": "fiction/best"}] * 2


def test_call_delegated_all_failed_carries_the_route_and_tags(router, make_executor):
    decision = delegate_decision(router)
    order = order_of(decision)
    provider = FakeProvider({model_id: fail() for model_id in order})
    monitor = Monitor()
    with pytest.raises(AllModelsFailed) as info:
        make_executor(router, provider, monitor).call_delegated(decision, BRIEF)
    assert info.value.decision is decision.route
    assert [a.model for a in info.value.attempts] == list(order)
    assert [r["final"] for r in monitor.records] == [False] * (len(order) - 1) + [True]
    assert all(r["tags"] == {"delegated": "true", "parent": "fiction/best"}
               for r in monitor.records)


def test_call_delegated_cost_blind_logs_list_price_and_zero_routing_cost(router, make_executor):
    decision = delegate_decision(router, "cost_blind")
    provider = FakeProvider({"fiction/best": lambda m: Completion("ok", 1100, 200)})
    monitor = Monitor()
    make_executor(router, provider, monitor).call_delegated(decision, BRIEF)
    (record,) = monitor.records
    assert (record["flavor"], record["model"]) == ("cost_blind", "fiction/best")
    assert record["cost_usd"] == router.registry.get("fiction/best").cost(1100, 200) > 0
    assert record["routing_cost_usd"] == 0.0
    assert record["tags"] == {"delegated": "true", "parent": "fiction/cheap"}


def test_call_delegated_refuses_an_inline_decision_before_any_call(router, make_executor):
    decision = router.decide_delegation("judge", "fiction/cheap", context_tokens=0,
                                        brief_tokens=100, result_tokens=20,
                                        inline_separate_call=False)
    assert (decision.mode, decision.reason) == ("inline", "inline_cheaper")
    provider = FakeProvider({})
    monitor = Monitor()
    with pytest.raises(ValueError, match="inline"):
        make_executor(router, provider, monitor).call_delegated(decision, BRIEF)
    assert provider.calls == [] and monitor.records == []


@pytest.mark.parametrize("tags", [{"delegated": "false"}, {"delegated": "true"},
                                  {"suite": "tiny", "parent": "someone"}])
def test_call_delegated_rejects_caller_tags_it_sets_itself(router, make_executor, tags):
    decision = delegate_decision(router)
    provider = FakeProvider({})
    monitor = Monitor()
    with pytest.raises(ValueError, match="delegated|parent"):
        make_executor(router, provider, monitor).call_delegated(decision, BRIEF, tags=tags)
    assert provider.calls == [] and monitor.records == []


def test_call_delegated_unknown_task_in_this_router_raises_keyerror(registry, task_factory,
                                                                    measured_stats, router,
                                                                    make_executor):
    decision = delegate_decision(router)
    other = Router(registry, {"other": task_factory(name="other")}, measured_stats)
    provider = FakeProvider({})
    with pytest.raises(KeyError):
        make_executor(other, provider).call_delegated(decision, BRIEF)
    assert provider.calls == []
