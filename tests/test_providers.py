"""Provider contracts with injected HTTP doubles and no live network."""

import io
import json
import traceback
from dataclasses import FrozenInstanceError
from urllib.error import HTTPError, URLError

import pytest
from model_routing import (
    AllModelsFailed, Completion, Executor, FakeProvider, Monitor, OpenAICompatibleProvider,
    ProviderError, Registry, Router, Stats,
)


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
    calls = []
    def opener(request, timeout):
        calls.append((request, timeout))
        raise error
    provider = OpenAICompatibleProvider("https://example.org", opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", messages, 1)
    assert len(calls) == 1
    assert type(error).__name__ in str(caught.value)
    if isinstance(error, HTTPError):
        assert str(error.code) in str(caught.value)
    else:
        assert str(error) in str(caught.value)


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
    calls = []
    def opener(request, timeout):
        calls.append((request, timeout))
        return io.BytesIO(payload)
    provider = OpenAICompatibleProvider("https://example.org", opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", messages, 1)
    assert len(calls) == 1
    assert "response" in str(caught.value).lower()


def test_openai_provider_wraps_response_read_failure(monkeypatch, messages):
    monkeypatch.setenv("OPENAI_API_KEY", "key")
    class BrokenResponse(io.BytesIO):
        def read(self, *args, **kwargs):
            raise OSError("truncated response")
    calls = []
    def opener(request, timeout):
        calls.append((request, timeout))
        return BrokenResponse()
    provider = OpenAICompatibleProvider("https://example.org", opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", messages, 1)
    assert len(calls) == 1
    assert "truncated response" in str(caught.value)


def test_openai_provider_redacts_opener_secret_and_suppresses_cause(monkeypatch, messages):
    fake_key = "fiction-secret-do-not-log-7391"
    monkeypatch.setenv("FICTION_API_KEY", fake_key)
    calls = []
    def opener(request, timeout):
        calls.append((request, timeout))
        raise OSError("rejected " + request.get_header("Authorization"))
    provider = OpenAICompatibleProvider("https://example.org", api_key_env="FICTION_API_KEY",
                                        opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/amber", messages, 2.5)
    assert len(calls) == 1
    error = caught.value
    assert "rejected" in str(error) and "[redacted]" in str(error)
    assert fake_key not in str(error) and fake_key not in repr(error)
    assert error.__cause__ is None
    assert error.__suppress_context__ is True
    assert error.status is None


def test_openai_provider_secret_never_reaches_executor_attempt_or_jsonl(
        monkeypatch, tmp_path, model_factory, task_factory, messages):
    fake_key = "fiction-secret-do-not-log-8282"
    monkeypatch.setenv("FICTION_API_KEY", fake_key)
    calls = []
    def opener(request, timeout):
        calls.append((request, timeout))
        raise OSError("rejected " + request.get_header("Authorization"))
    provider = OpenAICompatibleProvider("https://example.org", api_key_env="FICTION_API_KEY",
                                        opener=opener)
    registry = Registry([model_factory("fiction/amber")])
    stats = Stats()
    stats.add("judge", "fiction/amber", 100, 100)
    router = Router(registry, {"judge": task_factory(max_fallbacks=0)}, stats)
    path = tmp_path / "calls.jsonl"
    monitor = Monitor(path)
    with pytest.raises(AllModelsFailed) as caught:
        Executor(router, provider, monitor=monitor).call("judge", messages)
    assert len(calls) == 1
    assert len(caught.value.attempts) == 1
    assert "rejected" in caught.value.attempts[0].error
    assert fake_key not in caught.value.attempts[0].error
    lines = path.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 1
    assert all(fake_key not in line and "rejected" in json.loads(line)["error"] for line in lines)


def test_openai_provider_http_status_redacted_body_and_200_character_cap(monkeypatch, messages):
    fake_key = "fiction-secret-do-not-log-9191"
    monkeypatch.setenv("FICTION_API_KEY", fake_key)
    prefix = "begin " + fake_key + " "
    body = prefix + "x" * (200 - len(prefix)) + "BEYOND_200"
    calls = []
    def opener(request, timeout):
        calls.append((request, timeout))
        raise HTTPError(request.full_url, 429, "rate limited", {}, io.BytesIO(body.encode()))
    provider = OpenAICompatibleProvider("https://example.org", api_key_env="FICTION_API_KEY",
                                        opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/amber", messages, 4)
    assert len(calls) == 1
    error = caught.value
    assert error.status == 429
    assert "429" in str(error)
    assert "begin [redacted]" in str(error)
    assert fake_key not in str(error) and fake_key not in repr(error)
    assert "x" * 100 in str(error)
    assert "BEYOND_200" not in str(error)
    assert error.__cause__ is None and error.__suppress_context__ is True


def test_openai_provider_strips_url_credentials_from_errors():
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        raise OSError("connection refused")

    provider = OpenAICompatibleProvider(
        "https://alice:" + "fiction-pass-5521" + "@" + "gateway.example.org:8443/v1?token=fiction-q-7712#frag",
        api_key_env="FICTION_UNSET_KEY_ENV",
        opener=opener,
    )
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", [{"role": "user", "content": "hi"}], 5.0)
    assert len(calls) == 1
    message = str(caught.value) + repr(caught.value)
    assert "fiction-pass-5521" not in message
    assert "alice" not in message
    assert "fiction-q-7712" not in message
    assert "frag" not in message
    assert "https://gateway.example.org:8443/v1/chat/completions" in message


QUERY_VALUE = "fiction-qv-" + "6402"
OTHER_PASS = "fiction-op-" + "7713"
OTHER_TOKEN = "fiction-ot-" + "8824"
OTHER_URL = ("https://other:" + OTHER_PASS + "@" + "other.example/v2?access_token="
             + OTHER_TOKEN + "#fiction-frag")


def _base_with_query():
    return "https://gateway.example.org/v1?token=" + QUERY_VALUE + "&mode=standard"


def _assert_clean(text):
    for value in (QUERY_VALUE, OTHER_PASS, OTHER_TOKEN, "fiction-frag", "other:"):
        assert value not in text, value


def test_openai_provider_redacts_standalone_query_values(messages):
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        raise OSError("token " + QUERY_VALUE + " was rejected")

    provider = OpenAICompatibleProvider(_base_with_query(), api_key_env="FICTION_UNSET_KEY_ENV",
                                        opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", messages, 5.0)
    assert len(calls) == 1
    error = caught.value
    _assert_clean(str(error) + repr(error))
    assert "token [redacted] was rejected" in str(error)
    assert error.__cause__ is None and error.__suppress_context__ is True


def test_openai_provider_strips_credentials_from_any_url_in_opener_errors(messages):
    calls = []

    def opener(request, timeout):
        calls.append(request.full_url)
        raise OSError("redirect failed " + OTHER_URL)

    provider = OpenAICompatibleProvider("https://example.org/v1", opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", messages, 5.0)
    assert len(calls) == 1
    message = str(caught.value) + repr(caught.value)
    _assert_clean(message)
    assert "https://other.example/v2" in message


def test_openai_provider_strips_credentials_from_urls_in_http_body_and_reason(messages):
    calls = []
    body = "moved to " + OTHER_URL + " and token " + QUERY_VALUE

    def opener(request, timeout):
        calls.append(request.full_url)
        raise HTTPError(request.full_url, 401, "see " + OTHER_URL, {}, io.BytesIO(body.encode()))

    provider = OpenAICompatibleProvider(_base_with_query(), api_key_env="FICTION_UNSET_KEY_ENV",
                                        opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", messages, 5.0)
    assert len(calls) == 1
    error = caught.value
    assert error.status == 401
    _assert_clean(str(error) + repr(error))
    assert "https://other.example/v2" in str(error)


def test_url_and_query_credentials_never_reach_attempt_or_jsonl(
        tmp_path, model_factory, task_factory, messages):
    def opener(request, timeout):
        raise OSError("redirect failed " + OTHER_URL + " token " + QUERY_VALUE)

    provider = OpenAICompatibleProvider(_base_with_query(), api_key_env="FICTION_UNSET_KEY_ENV",
                                        opener=opener)
    registry = Registry([model_factory("fiction/amber")])
    stats = Stats()
    stats.add("judge", "fiction/amber", 100, 100)
    router = Router(registry, {"judge": task_factory(max_fallbacks=0)}, stats)
    path = tmp_path / "calls.jsonl"
    with pytest.raises(AllModelsFailed) as caught:
        Executor(router, provider, monitor=Monitor(path)).call("judge", messages)
    _assert_clean(caught.value.attempts[0].error)
    _assert_clean(path.read_text(encoding="utf-8"))


@pytest.mark.parametrize("base_url", [
    "not-a-url?token=" + QUERY_VALUE,
    "ftp://files.example.org/v1?token=" + QUERY_VALUE,
    "https:///v1?token=" + QUERY_VALUE,
])
def test_openai_provider_rejects_malformed_base_url_without_echoing_it(base_url):
    with pytest.raises(ValueError) as caught:
        OpenAICompatibleProvider(base_url)
    assert QUERY_VALUE not in str(caught.value)
    assert "token=" not in str(caught.value)


@pytest.mark.parametrize("base_url", ["https://example.org", "https://example.org/v1/"])
def test_openai_provider_error_shows_endpoint_url_exactly_once(base_url, messages):
    def opener(request, timeout):
        raise OSError("connection refused")

    provider = OpenAICompatibleProvider(base_url, opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", messages, 5.0)
    message = str(caught.value)
    expected = base_url.rstrip("/") + "/chat/completions"
    assert message.count("/chat/completions") == 1, message
    assert expected + " failed" in message, message


def test_short_query_values_do_not_mangle_messages(messages):
    long_value = "fiction-lv-" + "93017"

    def opener(request, timeout):
        raise OSError("refused by 192.0.2.1 after 1 try, token " + long_value)

    provider = OpenAICompatibleProvider(
        "https://gateway.example.org:8443/v1?v=1&beta=true&token=" + long_value,
        api_key_env="FICTION_UNSET_KEY_ENV", opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", messages, 5.0)
    message = str(caught.value)
    assert "https://gateway.example.org:8443/v1/chat/completions failed" in message, message
    assert "refused by 192.0.2.1 after 1 try" in message, message
    assert long_value not in message
    assert "token [redacted]" in message


def test_raw_and_decoded_query_values_are_redacted(messages):
    raw_a, raw_b = "fiction%2Fqv" + "4410", "fiction+qv" + "5521"
    forms = (raw_a, "fiction/qv4410", raw_b, "fiction qv5521")
    body = " | ".join(forms)

    def opener(request, timeout):
        raise HTTPError(request.full_url, 400, "bad request", {}, io.BytesIO(body.encode()))

    provider = OpenAICompatibleProvider(
        "https://gateway.example.org/v1?api_key=" + raw_a + "&other=" + raw_b,
        api_key_env="FICTION_UNSET_KEY_ENV", opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", messages, 5.0)
    message = str(caught.value) + repr(caught.value)
    for form in forms:
        assert form not in message, form
    assert caught.value.status == 400


def test_unprintable_opener_exception_still_becomes_clean_provider_error(monkeypatch, messages):
    fake_key = "fiction-unprintable-" + "6630"
    monkeypatch.setenv("FICTION_API_KEY", fake_key)

    class Unprintable(OSError):
        def __str__(self):
            raise RuntimeError("cannot format " + fake_key)

    def opener(request, timeout):
        raise Unprintable(fake_key)

    provider = OpenAICompatibleProvider("https://example.org/v1", api_key_env="FICTION_API_KEY",
                                        opener=opener)
    with pytest.raises(ProviderError) as caught:
        provider.complete("fiction/a", messages, 5.0)
    error = caught.value
    text = str(error) + repr(error) + "".join(
        traceback.format_exception(type(error), error, error.__traceback__))
    assert fake_key not in text
    assert "Unprintable" in str(error)
    assert error.__cause__ is None and error.__suppress_context__ is True


def test_base_url_query_is_kept_after_the_endpoint_path(messages):
    captured = []
    payload = json.dumps({"choices": [{"message": {"content": "ok"}}],
                          "usage": {"prompt_tokens": 1, "completion_tokens": 1}}).encode()

    def opener(request, timeout):
        captured.append(request.full_url)
        return io.BytesIO(payload)

    provider = OpenAICompatibleProvider("https://gateway.example.org/openai/?api-version=2026-10-01",
                                        api_key_env="FICTION_UNSET_KEY_ENV", opener=opener)
    provider.complete("fiction/a", messages, 5.0)
    assert captured == ["https://gateway.example.org/openai/chat/completions?api-version=2026-10-01"]

