"""Model providers: a scripted fake for tests and an OpenAI-compatible HTTP client."""

from __future__ import annotations

import json
import os
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
    """A failure that a fallback should handle: timeout, rate limit, 5xx, bad response."""


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
    """

    def __init__(self, base_url: str, api_key_env: str = "OPENAI_API_KEY",
                 model_map: Optional[Dict[str, str]] = None,
                 opener: Optional[Callable] = None):
        self.base_url = base_url
        self.api_key_env = api_key_env
        self.model_map = dict(model_map or {})
        self.opener = opener

    @property
    def url(self) -> str:
        """The full chat completions URL."""
        return self.base_url.rstrip("/") + "/chat/completions"

    def complete(self, model_id: str, messages: List[dict], timeout_s: float) -> Completion:
        """POST the messages and parse the first choice and the token usage."""
        body = json.dumps({"model": self.model_map.get(model_id, model_id),
                           "messages": messages}).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        key = os.environ.get(self.api_key_env)
        if key:
            headers["Authorization"] = f"Bearer {key}"
        request = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        opener = self.opener if self.opener is not None else urllib.request.urlopen
        try:
            response = opener(request, timeout=timeout_s)
            try:
                payload = response.read()
            finally:
                close = getattr(response, "close", None)
                if close is not None:
                    close()
        except ProviderError:
            raise
        except Exception as exc:
            raise ProviderError(f"request to {self.url} failed: "
                                f"{type(exc).__name__}: {exc}") from exc
        try:
            data = json.loads(payload)
            text = data["choices"][0]["message"]["content"]
            usage = data["usage"]
            input_tokens = usage["prompt_tokens"]
            output_tokens = usage["completion_tokens"]
        except Exception as exc:
            raise ProviderError(f"unparseable response from {self.url}: "
                                f"{type(exc).__name__}: {exc}") from exc
        if not isinstance(text, str) or not _is_count(input_tokens) \
                or not _is_count(output_tokens):
            raise ProviderError(f"unexpected response shape from {self.url}")
        return Completion(text, input_tokens, output_tokens)


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0
