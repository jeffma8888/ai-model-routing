"""A variant's provider options, sent on each call of its route (DESIGN 4.1, 6 and 7 v1.574, row VAR1d)."""

import dataclasses
import io
import json
import math
from pathlib import Path

import pytest

from model_routing import (Completion, Executor, FakeProvider, Model, Monitor,
                           OpenAICompatibleProvider, ProviderError, Registry, Router, Stats, Task,
                           Variant)
from model_routing.delegation import DELEGATE, DelegationDecision

ROOT = Path(__file__).resolve().parents[1]
HIGH = {"reasoning_effort": "high"}
LOW = {"reasoning_effort": "low", "extra": {"tags": ["a", 1, 2.5, True, None]}}
MESSAGES = [{"role": "user", "content": "x"}]


def row(model_id="v/m", family="v", **extra):
    return dict({"id": model_id, "family": family, "price_in": 1.0, "price_out": 2.0,
                 "context_window": 100_000}, **extra)


def load(tmp_path, rows):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": rows}), encoding="utf-8")
    return Registry.load(path)


def review_task():
    return Task(name="review", bar=0.8, min_samples=30, expected_input_tokens=1000,
                expected_output_tokens=200)


def two_variants(tmp_path):
    return load(tmp_path, [row("v/m", variants={"high": {"provider_options": HIGH},
                                                "low": {"provider_options": LOW}})])


def measured_router(registry):
    stats = Stats()
    for model in registry.models:
        stats.add("review", model.id, 30, 30)
    return Router(registry, {"review": review_task()}, stats)


def fixed_executor(router, provider, monitor=None):
    ticks = iter(float(i) for i in range(100))
    return Executor(router, provider, monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: "2026-01-02T03:04:05Z", id_factory=lambda: "fixed-call")


def fail(messages):
    raise ProviderError("outage")


def ok(messages):
    return Completion("ok", 10, 2)


# 4.1: the field and its checks


def test_provider_options_is_the_last_variant_field_and_defaults_to_empty():
    assert [f.name for f in dataclasses.fields(Variant)][-2:] == ["items_per_call", "provider_options"]
    assert Variant("lean").provider_options == {}
    positional = Variant("lean", "low", "agent 1", {"a": 1}, 2, {"effort": "low"})
    assert (positional.items_per_call, positional.provider_options) == (2, {"effort": "low"})


def test_provider_options_are_stored_as_a_new_plain_copy():
    nested = {"tags": ("a", 1), "inner": {"k": [1, {"deep": 2.5}]}}
    options = {"reasoning_effort": "high", "extra": nested, "flag": False, "none": None}
    variant = Variant("high", provider_options=options)
    options["reasoning_effort"] = "low"
    nested["inner"]["k"].append(3)
    assert variant.provider_options == {"reasoning_effort": "high", "flag": False, "none": None,
                                        "extra": {"tags": ["a", 1], "inner": {"k": [1, {"deep": 2.5}]}}}
    assert type(variant.provider_options["extra"]["tags"]) is list
    assert list(variant.provider_options) == ["reasoning_effort", "extra", "flag", "none"]


@pytest.mark.parametrize("options", [
    None, [("a", 1)], "a", {"": 1}, {1: 1}, {"a": float("nan")}, {"a": float("inf")},
    {"a": [float("-inf")]}, {"a": {"b": float("nan")}}, {"a": {1: "x"}}, {"a": {1, 2}},
    {"a": b"x"}, {"a": object()}, {"a": [object()]}, {"a": 1j},
])
def test_provider_options_must_be_a_mapping_of_json_values(options):
    with pytest.raises(ValueError):
        Variant("lean", provider_options=options)


def test_a_nested_mapping_may_have_any_string_key():
    assert Variant("x", provider_options={"a": {"": 1}}).provider_options == {"a": {"": 1}}


def test_model_provider_options_is_a_new_copy_on_each_read():
    model = Model("v/m@high", "v", 1.0, 2.0, 8000,
                  variant=Variant("high", provider_options={"a": {"b": [1]}}))
    first = model.provider_options
    first["a"]["b"].append(2)
    first["c"] = 3
    assert model.provider_options == {"a": {"b": [1]}}
    assert model.provider_options is not model.provider_options
    assert model.variant.provider_options == {"a": {"b": [1]}}
    assert Model("v/m", "v", 1.0, 2.0, 8000).provider_options == {}
    assert Model("v/m@lean", "v", 1.0, 2.0, 8000, variant=Variant("lean")).provider_options == {}


def test_registry_load_reads_provider_options_and_asdict_ends_with_them(tmp_path):
    registry = load(tmp_path, [row("v/m", variants={"high": {"provider_options": HIGH},
                                                "plain": {"provider_options": None},
                                                "both": {"items_per_call": 2,
                                                         "provider_options": LOW}})])
    assert [m.id for m in registry.models] == ["v/m", "v/m@high", "v/m@plain", "v/m@both"]
    assert [m.provider_options for m in registry.models] == [{}, HIGH, {}, LOW]
    as_dict = dataclasses.asdict(registry.get("v/m@both"))["variant"]
    assert list(as_dict)[-2:] == ["items_per_call", "provider_options"]
    assert as_dict["provider_options"] == LOW


@pytest.mark.parametrize("options", [[1], "high", {"": 1}, {"a": [{"b": None}, 1e400]}])
def test_bad_provider_options_in_a_file_name_the_file(tmp_path, options):
    with pytest.raises(ValueError, match="models.json"):
        load(tmp_path, [row("v/m", variants={"high": {"provider_options": options}})])


def test_a_variant_object_still_refuses_an_unknown_key(tmp_path):
    with pytest.raises(ValueError, match="models.json"):
        load(tmp_path, [row("v/m", variants={"high": {"provider_option": HIGH}})])


def test_the_packaged_registry_sends_no_options():
    registry = Registry.load(ROOT / "model_routing" / "data" / "models.json")
    assert all(m.provider_options == {} for m in registry.models)


# 6: FakeProvider


def test_fake_provider_records_the_options_of_each_call():
    provider = FakeProvider({"a": lambda messages: Completion(str(len(messages)), 1, 1)})
    options = {"effort": {"level": "high"}}
    assert provider.complete("a", MESSAGES, 5.0).text == "1"
    assert provider.complete("a", MESSAGES, 5.0, options=None).text == "1"
    provider.complete("a", MESSAGES, 5.0, options=options)
    options["effort"]["level"] = "low"
    assert provider.calls == [("a", MESSAGES)] * 3
    assert provider.call_options == [None, None, {"effort": {"level": "high"}}]


def test_fake_provider_records_the_options_of_an_unscripted_call():
    provider = FakeProvider({})
    with pytest.raises(ProviderError):
        provider.complete("missing", MESSAGES, 1.0, options={"a": 1})
    assert (provider.calls, provider.call_options) == ([("missing", MESSAGES)], [{"a": 1}])


# 6: OpenAICompatibleProvider


class Opener:
    def __init__(self):
        self.requests = []

    def __call__(self, request, timeout):
        self.requests.append(request)
        body = {"choices": [{"message": {"content": "ok"}}],
                "usage": {"prompt_tokens": 3, "completion_tokens": 1}}
        return io.BytesIO(json.dumps(body).encode("utf-8"))


def openai(opener):
    return OpenAICompatibleProvider("https://example.test/v1", api_key_env="NO_SUCH_KEY_ENV",
                                    model_map={"v/m@high": "m-1"}, opener=opener)


V1_573_BODY = json.dumps({"model": "m-1", "messages": MESSAGES}).encode("utf-8")


@pytest.mark.parametrize("kwargs", [{}, {"options": None}, {"options": {}}])
def test_without_options_the_body_is_v1_573s_byte_for_byte(kwargs):
    opener = Opener()
    assert openai(opener).complete("v/m@high", MESSAGES, 5.0, **kwargs).text == "ok"
    assert opener.requests[0].data == V1_573_BODY


def test_options_follow_model_and_messages_in_their_order():
    opener = Opener()
    openai(opener).complete("v/m@high", MESSAGES, 5.0,
                            options={"reasoning_effort": "high", "extra": {"a": [1, None]}})
    body = json.loads(opener.requests[0].data)
    assert list(body) == ["model", "messages", "reasoning_effort", "extra"]
    assert body == {"model": "m-1", "messages": MESSAGES, "reasoning_effort": "high",
                    "extra": {"a": [1, None]}}


@pytest.mark.parametrize("key", ["model", "messages", "stream"])
def test_an_option_never_replaces_a_key_the_adapter_sets(key):
    opener = Opener()
    with pytest.raises(ValueError) as caught:
        openai(opener).complete("v/m@high", MESSAGES, 5.0,
                                options={"reasoning_effort": "high", key: "value-not-shown"})
    assert opener.requests == []
    assert repr(key) in str(caught.value) and "value-not-shown" not in str(caught.value)


@pytest.mark.parametrize("options", [["reasoning_effort"], "high", 3])
def test_options_that_are_not_a_mapping_are_refused_before_any_request(options):
    opener = Opener()
    with pytest.raises(ValueError):
        openai(opener).complete("v/m@high", MESSAGES, 5.0, options=options)
    assert opener.requests == []


# 7: the executor


def test_each_attempt_sends_the_options_of_the_route_it_calls(tmp_path):
    router = measured_router(two_variants(tmp_path))
    decision = router.select("review")
    assert (decision.primary, decision.fallbacks) == ("v/m", ("v/m@high", "v/m@low"))
    provider = FakeProvider({"v/m": fail, "v/m@high": fail, "v/m@low": ok})
    result = fixed_executor(router, provider).call("review", MESSAGES)
    assert result.model == "v/m@low"
    assert [model for model, _ in provider.calls] == ["v/m", "v/m@high", "v/m@low"]
    assert provider.call_options == [None, HIGH, LOW]


def test_a_variant_primary_sends_its_options_and_a_base_fallback_sends_none(tmp_path):
    registry = two_variants(tmp_path)
    stats = Stats()
    stats.add("review", "v/m@high", 30, 30)
    stats.add("review", "v/m", 30, 30, input_tokens=60_000, output_tokens=12_000, token_trials=30)
    router = Router(registry, {"review": review_task()}, stats)
    assert (router.select("review").primary, router.select("review").fallbacks) == ("v/m@high", ("v/m",))
    provider = FakeProvider({"v/m@high": fail, "v/m": ok})
    assert fixed_executor(router, provider).call("review", MESSAGES).model == "v/m"
    assert provider.call_options == [HIGH, None]


class ThreeArgProvider:
    """A provider written to the v1.573 `Provider` signature, with no `options` keyword."""

    def __init__(self):
        self.seen = []

    def complete(self, model_id, messages, timeout_s):
        self.seen.append(model_id)
        return Completion("ok", 10, 2)


def test_a_provider_without_the_keyword_still_serves_a_route_without_options(tmp_path):
    registry = load(tmp_path, [row("v/m", variants={"lean": {"harness": "lean-agent 2.0"}})])
    router = measured_router(registry)
    provider = ThreeArgProvider()
    assert fixed_executor(router, provider).call("review", MESSAGES).model == "v/m"
    stats = Stats()
    stats.add("review", "v/m@lean", 30, 30)
    lean = Router(registry, {"review": review_task()}, stats)
    assert fixed_executor(lean, provider).call("review", MESSAGES).model == "v/m@lean"
    assert provider.seen == ["v/m", "v/m@lean"]


def test_a_provider_without_the_keyword_raises_type_error_on_a_route_with_options(tmp_path):
    registry = two_variants(tmp_path)
    stats = Stats()
    stats.add("review", "v/m@high", 30, 30)
    router = Router(registry, {"review": review_task()}, stats)
    monitor = Monitor()
    with pytest.raises(TypeError):
        fixed_executor(router, ThreeArgProvider(), monitor).call("review", MESSAGES)
    assert monitor.records == []


class MutatingProvider:
    def __init__(self):
        self.received = []

    def complete(self, model_id, messages, timeout_s, *, options=None):
        self.received.append(json.loads(json.dumps(options)))
        if options is not None:
            options["reasoning_effort"] = "changed"
            options.clear()
        return Completion("ok", 10, 2)


def test_a_provider_that_changes_its_options_changes_no_later_call(tmp_path):
    registry = two_variants(tmp_path)
    stats = Stats()
    stats.add("review", "v/m@high", 30, 30)
    router = Router(registry, {"review": review_task()}, stats)
    provider = MutatingProvider()
    executor = fixed_executor(router, provider)
    executor.call("review", MESSAGES)
    executor.call("review", MESSAGES)
    assert provider.received == [HIGH, HIGH]
    assert registry.get("v/m@high").provider_options == HIGH


def test_records_keep_their_bytes_with_options(tmp_path):
    def records_for(variants):
        registry = load(tmp_path, [row("v/m", variants=variants)])
        stats = Stats()
        stats.add("review", "v/m@high", 30, 30)
        stats.add("review", "v/m", 30, 30, input_tokens=60_000, output_tokens=12_000,
                  token_trials=30)
        router = Router(registry, {"review": review_task()}, stats)
        assert router.select("review").fallbacks == ("v/m",)
        monitor = Monitor()
        result = fixed_executor(router, FakeProvider({"v/m@high": fail, "v/m": ok}),
                                monitor).call("review", MESSAGES)
        return [json.dumps(r) for r in monitor.records], result.attempts

    with_options = records_for({"high": {"provider_options": HIGH}})
    without = records_for({"high": {}})
    assert with_options == without
    assert all("reasoning_effort" not in line for line in with_options[0])


def test_call_delegated_sends_the_routes_options(tmp_path):
    registry = load(tmp_path, [row("v/m", variants={"high": {"provider_options": HIGH}}),
                               row("w/p", family="w")])
    stats = Stats()
    stats.add("review", "v/m@high", 30, 30)
    router = Router(registry, {"review": review_task()}, stats)
    route = router.select("review")
    assert (route.primary, route.fallbacks) == ("v/m@high", ())
    decision = DelegationDecision("review", "cost_effective", "w/p", DELEGATE, "v/m@high",
                                  "delegate_cheaper", False, True, 0.002, 0.001, 0.0, 0.8, route)
    provider = FakeProvider({"v/m@high": ok})
    result = fixed_executor(router, provider).call_delegated(decision, MESSAGES)
    assert (result.model, provider.call_options) == ("v/m@high", [HIGH])


def test_a_refused_key_propagates_after_the_attempts_before_it(tmp_path):
    registry = load(tmp_path, [row("v/m", variants={"bad": {"provider_options": {"stream": True}}})])
    router = measured_router(registry)
    monitor = Monitor()
    opened = []

    def opener(request, timeout):
        opened.append(request)
        raise OSError("down")

    provider = OpenAICompatibleProvider("https://example.test/v1", api_key_env="NO_SUCH_KEY_ENV",
                                        opener=opener)
    with pytest.raises(ValueError, match="stream"):
        fixed_executor(router, provider, monitor).call("review", MESSAGES)
    assert len(opened) == 1
    assert [(r["model"], r["outcome"]) for r in monitor.records] == [("v/m", "error")]


def test_a_hand_built_route_of_an_unknown_model_calls_the_provider_before_the_cost_lookup(tmp_path):
    # review iter-421 nit 1: as in v1.573, the provider is called, then registry.get raises
    registry = two_variants(tmp_path)
    router = measured_router(registry)
    route = dataclasses.replace(router.select("review"), primary="x/unknown", fallbacks=())
    decision = DelegationDecision("review", "cost_effective", "v/m", DELEGATE, "x/unknown",
                                  "delegate_cheaper", False, True, 0.002, 0.001, 0.0, 0.8, route)
    provider = FakeProvider({"x/unknown": ok})
    with pytest.raises(KeyError):
        fixed_executor(router, provider).call_delegated(decision, MESSAGES)
    assert (provider.calls, provider.call_options) == ([("x/unknown", MESSAGES)], [None])


# Docs


def test_the_readme_says_provider_options_are_sent():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    part = text.split("## How a model is chosen", 1)[1].split("\n## ", 1)[0]
    assert ("A variant's `provider_options`, for example `{\"reasoning_effort\": \"high\"}`, are "
            "sent: the executor passes them to the provider on each call of that route, and "
            "`OpenAICompatibleProvider` adds them to the request body after `model` and `messages`, "
            "which an option may not replace (`DESIGN.md` 6 and 7).") in part


def test_the_production_note_states_provider_options_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert "The change still planned: the provider options a variant passes on each call." not in text
    assert ("A variant can also carry provider options, such as an effort parameter, which the "
            "executor sends to the provider on each call of its route.") in text
