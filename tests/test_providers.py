"""Provider contracts with injected HTTP doubles and no live network."""

import io
import json
from dataclasses import FrozenInstanceError
from urllib.error import HTTPError, URLError

import pytest
from model_routing import Completion, FakeProvider, OpenAICompatibleProvider, ProviderError


@pytest.fixture(autouse=True)
def prevent_live_network(monkeypatch):
    def forbidden(*args, **kwargs):
        raise AssertionError("Tests must inject an opener, never access the network")
    monkeypatch.setattr("urllib.request.urlopen", forbidden)


@pytest.fixture
def messages():
    return [{"role": "user", "content": "Judge this fictional answer."}]


def test_completion_has_pinned_fields_and_is_frozen():
    completion = Completion("answer", 11, 7)
    assert (completion.text, completion.input_tokens, completion.output_tokens) == ("answer", 11, 7)
    with pytest.raises(FrozenInstanceError):
        completion.text = "changed"


def test_fake_provider_calls_script_with_messages_and_records_call_order(messages):
    received = []
    def script(value):
        received.append(value)
        return Completion("ok", 2, 3)
    provider = FakeProvider({"fiction/a": script, "fiction/b": script})
    assert provider.complete("fiction/b", messages, 1) == Completion("ok", 2, 3)
    assert provider.complete("fiction/a", [], 2) == Completion("ok", 2, 3)
    assert received == [messages, []]
    assert provider.calls == [("fiction/b", messages), ("fiction/a", [])]


@pytest.mark.parametrize("error", [ProviderError("outage"), RuntimeError("script bug")])
def test_fake_provider_propagates_exact_script_exception_and_records_call(messages, error):
    def fail(value):
        raise error
    provider = FakeProvider({"fiction/a": fail})
    with pytest.raises(type(error)) as caught:
        provider.complete("fiction/a", messages, 3)
    assert caught.value is error
    assert provider.calls == [("fiction/a", messages)]


def test_fake_provider_unknown_model_raises_providererror_and_records_call(messages):
    provider = FakeProvider({})
    with pytest.raises(ProviderError):
        provider.complete("fiction/unknown", messages, 3)
    assert provider.calls == [("fiction/unknown", messages)]


@pytest.mark.parametrize("base_url", ["https://example.org/v1", "https://example.org/v1///"])
def test_openai_provider_posts_mapped_model_messages_auth_and_timeout(monkeypatch, messages, base_url):
    monkeypatch.setenv("FICTION_API_KEY", "test-secret")
    calls = []
    def opener(request, timeout):
        calls.append((request, timeout))
        return io.BytesIO(json.dumps({"choices": [{"message": {"content": "verdict"}}],
                                     "usage": {"prompt_tokens": 13, "completion_tokens": 5}}).encode())
    provider = OpenAICompatibleProvider(base_url, api_key_env="FICTION_API_KEY",
                                        model_map={"fiction/a": "wire-a"}, opener=opener)
    assert provider.complete("fiction/a", messages, 7.5) == Completion("verdict", 13, 5)
    assert len(calls) == 1
    request, timeout = calls[0]
    assert request.full_url == "https://example.org/v1/chat/completions"
    assert request.get_method() == "POST"
    assert json.loads(request.data) == {"model": "wire-a", "messages": messages}
    headers = {key.lower(): value for key, value in request.header_items()}
    assert headers["authorization"] == "Bearer test-secret"
    assert timeout == 7.5


def test_openai_provider_unmapped_model_and_default_api_key_env(monkeypatch, messages):
    monkeypatch.setenv("OPENAI_API_KEY", "default-secret")
    captured = []
    def opener(request, timeout):
        captured.append(request)
        return io.BytesIO(b'{"choices":[{"message":{"content":""}}],"usage":{"prompt_tokens":0,"completion_tokens":0}}')
    provider = OpenAICompatibleProvider("https://example.org", opener=opener)
    assert provider.complete("fiction/raw", messages, 1) == Completion("", 0, 0)
    assert json.loads(captured[0].data)["model"] == "fiction/raw"
    assert dict((k.lower(), v) for k, v in captured[0].header_items())["authorization"] == "Bearer default-secret"


@pytest.mark.parametrize("error", [
    TimeoutError("timeout"), URLError("offline"), OSError("connection closed"),
    HTTPError("https://example.org", 429, "rate limited", {}, None),
    HTTPError("https://example.org", 503, "unavailable", {}, None),
])
def test_openai_provider_wraps_every_network_and_http_failure(monkeypatch, messages, error):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    def opener(request, timeout):
        raise error
    provider = OpenAICompatibleProvider("https://example.org", opener=opener)
    with pytest.raises(ProviderError):
        provider.complete("fiction/a", messages, 1)


@pytest.mark.parametrize("payload", [
    b"not-json", b"\xff", b"null", b"[]", b"{}",
    b'{"choices":[],"usage":{"prompt_tokens":1,"completion_tokens":2}}',
    b'{"choices":[{}],"usage":{"prompt_tokens":1,"completion_tokens":2}}',
    b'{"choices":[{"message":{}}],"usage":{"prompt_tokens":1,"completion_tokens":2}}',
    b'{"choices":[{"message":{"content":"ok"}}]}',
    b'{"choices":[{"message":{"content":"ok"}}],"usage":{"completion_tokens":2}}',
    b'{"choices":[{"message":{"content":"ok"}}],"usage":{"prompt_tokens":1}}',
])
def test_openai_provider_wraps_json_and_required_field_parse_failures(monkeypatch, messages, payload):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    provider = OpenAICompatibleProvider("https://example.org",
                                        opener=lambda request, timeout: io.BytesIO(payload))
    with pytest.raises(ProviderError):
        provider.complete("fiction/a", messages, 1)


def test_openai_provider_wraps_response_read_failure(monkeypatch, messages):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    class BrokenResponse(io.BytesIO):
        def read(self, *args, **kwargs):
            raise OSError("truncated response")
    provider = OpenAICompatibleProvider("https://example.org",
                                        opener=lambda request, timeout: BrokenResponse())
    with pytest.raises(ProviderError):
        provider.complete("fiction/a", messages, 1)
