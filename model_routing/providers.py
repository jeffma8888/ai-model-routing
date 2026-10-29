"""Model providers: a scripted fake for tests and an OpenAI-compatible HTTP client."""

from __future__ import annotations

import json
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional, Protocol, Tuple


@dataclass(frozen=True)
class Completion:
    """A model response with its billed token counts."""

    text: str
    input_tokens: int
    output_tokens: int


class ProviderError(Exception):
    """A failure that a fallback should handle: timeout, rate limit, 5xx, bad response.

    ``status`` is the HTTP status code when the failure was an HTTP error,
    else ``None``.
    """

    def __init__(self, message: str = "", status: Optional[int] = None):
        super().__init__(message)
        self.status = status


class Provider(Protocol):
    """Anything that can complete a chat for a model ID."""

    def complete(self, model_id: str, messages: List[dict], timeout_s: float) -> Completion:
        """Return a completion or raise :class:`ProviderError`."""
        ...


class FakeProvider:
    """A provider driven by a script of per-model callables.

    Exceptions raised by a script callable propagate unchanged; a model ID
    missing from the script raises :class:`ProviderError`. ``calls`` records
    ``(model_id, messages)`` in call order.
    """

    def __init__(self, script: Dict[str, Callable[[List[dict]], Completion]]):
        self.script = script
        self.calls: List[Tuple[str, List[dict]]] = []

    def complete(self, model_id: str, messages: List[dict], timeout_s: float) -> Completion:
        """Record the call and return ``script[model_id](messages)``."""
        self.calls.append((model_id, messages))
        if model_id not in self.script:
            raise ProviderError(f"no scripted response for model {model_id!r}")
        return self.script[model_id](messages)


class OpenAICompatibleProvider:
    """A client for any endpoint that implements ``POST /chat/completions``.

    ``model_map`` maps registry IDs to the endpoint's model IDs (unmapped IDs
    are sent as is). The API key is read from ``api_key_env`` at call time;
    when that variable is unset no Authorization header is sent, which suits
    local servers. ``opener`` defaults to ``urllib.request.urlopen`` and
    exists so tests never touch the network.

    ``base_url`` must be an http or https URL with a host, else the
    constructor raises ``ValueError`` (the message never echoes the URL).
    Error messages show every URL as ``scheme://host[:port]/path`` and replace
    the API key, the base URL password and every base URL query parameter
    value of at least 8 characters with ``[redacted]``.
    """

    def __init__(self, base_url: str, api_key_env: str = "OPENAI_API_KEY",
                 model_map: Optional[Dict[str, str]] = None,
                 opener: Optional[Callable] = None):
        _validate_base_url(base_url)
        self.base_url = base_url
        self.api_key_env = api_key_env
        self.model_map = dict(model_map or {})
        self.opener = opener

    @property
    def url(self) -> str:
        """The full chat completions URL."""
        return self.base_url.rstrip("/") + "/chat/completions"

    @property
    def display_url(self) -> str:
        """The chat completions URL without userinfo, query string or fragment."""
        return _strip_url(self.base_url).rstrip("/") + "/chat/completions"

    def _secrets(self, key: str) -> List[str]:
        parts = urllib.parse.urlsplit(self.base_url)
        secrets = [key, parts.password or ""]
        secrets += [value for _, value in
                    urllib.parse.parse_qsl(parts.query, keep_blank_values=True)
                    if len(value) >= MIN_QUERY_SECRET_CHARS]
        return [x for x in secrets if x]

    def _clean(self, text: str, key: str) -> str:
        return _redact_values(_strip_urls(text), self._secrets(key))

    def complete(self, model_id: str, messages: List[dict], timeout_s: float) -> Completion:
        """POST the messages and parse the first choice and the token usage.

        Every :class:`ProviderError` raised here has the API key value
        replaced with ``[redacted]``, shows URLs without userinfo, query string
        or fragment, and carries no exception chain.
        ``timeout_s`` bounds each blocking socket operation, not the total call.
        """
        body = json.dumps({"model": self.model_map.get(model_id, model_id),
                           "messages": messages}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(self.api_key_env) or ""
        if key:
            headers["Authorization"] = f"Bearer {key}"
        request = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        opener = self.opener if self.opener is not None else urllib.request.urlopen
        failure: Optional[ProviderError] = None
        try:
            response = opener(request, timeout=timeout_s)
            try:
                payload = response.read()
            finally:
                close = getattr(response, "close", None)
                if close is not None:
                    close()
        except urllib.error.HTTPError as exc:
            snippet = _redacted_prefix(_read_body(exc), self._secrets(key), BODY_SNIPPET_CHARS)
            failure = ProviderError(
                self._clean(f"request to {self.display_url} failed: HTTPError {exc.code}: "
                            f"{exc.reason}" + (f": {snippet}" if snippet else ""), key),
                status=exc.code)
        except ProviderError as exc:
            failure = ProviderError(self._clean(str(exc), key), status=getattr(exc, "status", None))
        except Exception as exc:
            failure = ProviderError(self._clean(f"request to {self.display_url} failed: "
                                                f"{type(exc).__name__}: {exc}", key))
        if failure is not None:
            raise failure from None
        try:
            data = json.loads(payload)
            text = data["choices"][0]["message"]["content"]
            usage = data["usage"]
            input_tokens = usage["prompt_tokens"]
            output_tokens = usage["completion_tokens"]
            shape_ok = isinstance(text, str) and _is_count(input_tokens) \
                and _is_count(output_tokens)
        except Exception as exc:
            failure = ProviderError(self._clean(f"unparseable response from {self.display_url}: "
                                                f"{type(exc).__name__}: {exc}", key))
        else:
            if not shape_ok:
                failure = ProviderError(f"unexpected response shape from {self.display_url}")
        if failure is not None:
            raise failure from None
        return Completion(text, input_tokens, output_tokens)


BODY_SNIPPET_CHARS = 200
REDACTED = "[redacted]"
# Shorter base_url query values (v=1, beta=true) cannot carry a credential.
MIN_QUERY_SECRET_CHARS = 8


def _read_body(error: "urllib.error.HTTPError") -> str:
    try:
        raw = error.read()
    except Exception:
        return ""
    if not raw:
        return ""
    if isinstance(raw, bytes):
        return raw.decode("utf-8", errors="replace")
    return str(raw)


def _redacted_prefix(text: str, secrets: List[str], limit: int) -> str:
    """Return the first ``limit`` characters of ``text`` with every secret occurrence
    that starts inside them replaced whole, so no partial secret survives the cut."""
    ordered = sorted(set(x for x in secrets if x), key=len, reverse=True)
    out = []
    i = 0
    while i < min(limit, len(text)):
        for secret in ordered:
            if text.startswith(secret, i):
                out.append(REDACTED)
                i += len(secret)
                break
        else:
            out.append(text[i])
            i += 1
    return "".join(out)


_URL_TOKEN = re.compile(r"[A-Za-z][A-Za-z0-9+.\-]*://[^\s'\"<>`]+")
_TRAILING = ".,;:!?)]}"


def _validate_base_url(base_url: object) -> None:
    ok = False
    if isinstance(base_url, str):
        try:
            parts = urllib.parse.urlsplit(base_url)
            parts.port
            ok = parts.scheme in ("http", "https") and bool(parts.hostname)
        except ValueError:
            ok = False
    if not ok:
        raise ValueError("base_url must be an http or https URL with a host") from None


def _strip_url(url: str) -> str:
    """Return ``url`` as ``scheme://host[:port]/path``."""
    scheme = url.split("://", 1)[0]
    try:
        parts = urllib.parse.urlsplit(url)
        host = parts.hostname or ""
        port = parts.port
    except ValueError:
        return f"{scheme}://{REDACTED}"
    if ":" in host:
        host = f"[{host}]"
    netloc = host + (f":{port}" if port is not None else "")
    return f"{parts.scheme}://{netloc}{parts.path}"


def _strip_urls(text: str) -> str:
    def rewrite(match: "re.Match[str]") -> str:
        token = match.group(0)
        stripped = token.rstrip(_TRAILING)
        return _strip_url(stripped) + token[len(stripped):]
    return _URL_TOKEN.sub(rewrite, text)


def _redact_values(text: str, secrets: List[str]) -> str:
    ordered = sorted(set(x for x in secrets if x), key=len, reverse=True)
    if not ordered:
        return text
    return re.sub("|".join(re.escape(x) for x in ordered), REDACTED, text)


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
