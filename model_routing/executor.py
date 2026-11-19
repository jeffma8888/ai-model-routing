"""Run a routed call with fallback, timing, validation and per-attempt logging."""

from __future__ import annotations

import json
import math
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from .delegation import DELEGATE
from .providers import Provider, ProviderError
from .router import RouteDecision, Router, _check_prompt_tokens


@dataclass(frozen=True)
class Attempt:
    """One provider call within a routed call."""

    model: str
    outcome: str
    error: Optional[str]
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float


@dataclass(frozen=True)
class CallResult:
    """The accepted response of a routed call and every attempt that led to it."""

    call_id: str
    text: str
    model: str
    attempts: Tuple[Attempt, ...]
    decision: RouteDecision


class AllModelsFailed(Exception):
    """Every routed model errored or failed validation; see ``.attempts``."""

    def __init__(self, message: str, attempts: Tuple[Attempt, ...], decision: RouteDecision):
        super().__init__(message)
        self.attempts = attempts
        self.decision = decision


def estimate_prompt_tokens(messages: Iterable[object], chars_per_token: float = 4.0) -> int:
    """Estimate the tokens of a request's messages as characters / ``chars_per_token``, rounded up.

    Counts every message's string ``content`` and the ``text`` of each ``{"type": "text"}``
    part of a list ``content``; any other part, message or content adds 0 (DESIGN 7 v1.507).
    A rough heuristic for English text that under-counts code and non-Latin scripts: a caller
    with a tokenizer should pass the real count as ``prompt_tokens``. Raises ``ValueError``
    unless ``chars_per_token`` is a finite number above 0 that is not a bool.
    """
    if isinstance(chars_per_token, bool) or not isinstance(chars_per_token, (int, float)) \
            or (isinstance(chars_per_token, float) and not math.isfinite(chars_per_token)) \
            or chars_per_token <= 0:
        raise ValueError(f"chars_per_token must be a finite number above 0, "
                         f"got {chars_per_token!r}")
    chars = 0
    for message in messages:
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if isinstance(content, str):
            chars += len(content)
        elif isinstance(content, list):
            for part in content:
                if isinstance(part, dict) and part.get("type") == "text" \
                        and isinstance(part.get("text"), str):
                    chars += len(part["text"])
    return math.ceil(chars / chars_per_token)


def _utc_now() -> str:
    stamp = datetime.now(timezone.utc).isoformat(timespec="milliseconds")
    return stamp.replace("+00:00", "Z")


def _new_id() -> str:
    return uuid.uuid4().hex


class Executor:
    """Executes calls against the primary model, falling back on provider errors.

    ``clock`` returns seconds for latency timing, ``now`` returns an ISO 8601
    UTC timestamp and ``id_factory`` returns a call ID; all are injectable.
    """

    def __init__(self, router: Router, provider: Provider, monitor=None,
                 clock: Callable[[], float] = time.monotonic,
                 now: Optional[Callable[[], str]] = None,
                 id_factory: Optional[Callable[[], str]] = None):
        self.router = router
        self.provider = provider
        self.monitor = monitor
        self.clock = clock
        self.now = now if now is not None else _utc_now
        self.id_factory = id_factory if id_factory is not None else _new_id

    def call(self, task_name: str, messages: List[dict], flavor: str = "cost_effective",
             generator_model: Optional[str] = None, exclude_models: Iterable[str] = (),
             tags: Optional[Dict[str, str]] = None,
             validate: Optional[Callable[[str], object]] = None, *,
             prompt_tokens: Optional[int] = None,
             slice: Optional[str] = None) -> CallResult:
        """Route and execute one call; raise :class:`AllModelsFailed` if none succeeds.

        ``prompt_tokens`` is the request's size in tokens; when None it is estimated with
        :func:`estimate_prompt_tokens`. Either way the route holds only models whose window
        fits it plus the task's expected output, and every record carries it as
        ``prompt_tokens`` with ``prompt_tokens_estimated`` (DESIGN 7 and 8.1 v1.507). A
        ``prompt_tokens`` that is not an integer >= 0 raises ``ValueError`` before any call.
        ``slice`` names a slice of the task, routed on that slice's own counts, and every
        record carries it (DESIGN 7 and 8.1 v1.511); ``select`` checks it before any call.
        """
        _check_prompt_tokens(prompt_tokens)
        estimated = prompt_tokens is None
        size = estimate_prompt_tokens(messages) if estimated else prompt_tokens
        decision = self.router.select(task_name, flavor=flavor,
                                      generator_model=generator_model,
                                      exclude_models=exclude_models, prompt_tokens=size,
                                      slice=slice)
        return self._execute(task_name, decision, messages, dict(tags or {}), validate,
                             (size, estimated))

    def call_delegated(self, decision, messages: List[dict],
                       tags: Optional[Dict[str, str]] = None,
                       validate: Optional[Callable[[str], object]] = None) -> CallResult:
        """Run the hand-off of a ``delegate`` :class:`DelegationDecision` on its route.

        ``messages`` is the brief. The route is used as decided, with fallback and
        validation as in :meth:`call`; every record is tagged ``delegated`` and
        ``parent``. An inline decision, or a caller tag with either name, raises
        ``ValueError`` before any call (DESIGN 7, v1.11).
        """
        if decision.mode != DELEGATE:
            raise ValueError(f"decision mode is {decision.mode!r}: inline work happens in the "
                             f"parent's own call, so there is no hand-off to run")
        if decision.route is None:
            raise ValueError("delegate decision has no route to run")
        call_tags = dict(tags or {})
        reserved = sorted(key for key in ("delegated", "parent") if key in call_tags)
        if reserved:
            raise ValueError(f"tag names {', '.join(reserved)} are set by call_delegated; "
                             f"pass other names")
        call_tags["delegated"] = "true"
        call_tags["parent"] = decision.parent
        return self._execute(decision.task, decision.route, messages, call_tags, validate)

    def _execute(self, task_name: str, decision: RouteDecision, messages: List[dict],
                 call_tags: Dict[str, str],
                 validate: Optional[Callable[[str], object]],
                 size: Optional[Tuple[int, bool]] = None) -> CallResult:
        task = self.router.tasks[task_name]
        registry = self.router.registry
        call_id = self.id_factory()
        order = (decision.primary, *decision.fallbacks)
        attempts: List[Attempt] = []
        for index, model_id in enumerate(order):
            start = self.clock()
            text = None
            try:
                completion = self.provider.complete(model_id, messages, task.timeout_s)
            except ProviderError as exc:
                latency_ms = float((self.clock() - start) * 1000.0)
                attempt = Attempt(model_id, "error", f"{type(exc).__name__}: {exc}",
                                  latency_ms, 0, 0, 0.0)
            else:
                latency_ms = float((self.clock() - start) * 1000.0)
                cost = float(registry.get(model_id).cost(completion.input_tokens,
                                                          completion.output_tokens))
                if validate is not None and not validate(completion.text):
                    attempt = Attempt(model_id, "invalid", "validation failed", latency_ms,
                                      completion.input_tokens, completion.output_tokens, cost)
                else:
                    attempt = Attempt(model_id, "ok", None, latency_ms,
                                      completion.input_tokens, completion.output_tokens, cost)
                    text = completion.text
            attempts.append(attempt)
            final = attempt.outcome == "ok" or index == len(order) - 1
            if self.monitor is not None:
                self.monitor.record(self._record(call_id, decision, registry, index, final,
                                                 attempt, call_tags, size))
            if text is not None:
                return CallResult(call_id, text, model_id, tuple(attempts), decision)
        raise AllModelsFailed(
            f"all {len(attempts)} routed models failed for task {task_name!r}",
            tuple(attempts), decision)

    def _record(self, call_id: str, decision: RouteDecision, registry, index: int,
                final: bool, attempt: Attempt, tags: Dict[str, str],
                size: Optional[Tuple[int, bool]] = None) -> dict:
        record = {
            "ts": self.now(),
            "call_id": call_id,
            "task": decision.task,
            "flavor": decision.flavor,
            "model": attempt.model,
            "family": registry.get(attempt.model).family,
            "attempt": index,
            "final": final,
            "outcome": attempt.outcome,
            "error": attempt.error,
            "latency_ms": attempt.latency_ms,
            "input_tokens": attempt.input_tokens,
            "output_tokens": attempt.output_tokens,
            "cost_usd": attempt.cost_usd,
            "routing_cost_usd": attempt.cost_usd if decision.flavor == "cost_effective" else 0.0,
            "below_bar": decision.below_bar,
        }
        if attempt.model in decision.below_bar_fallbacks:
            record["below_bar_fallback"] = True
        record["basis"] = decision.basis
        record["tags"] = dict(tags)
        record["slice"] = decision.slice
        if size is not None:
            record["prompt_tokens"], record["prompt_tokens_estimated"] = size
        return record


def json_validator(*required_keys: str) -> Callable[[str], bool]:
    """Return a validator that accepts a JSON object containing every required key."""
    def validate(text: str) -> bool:
        try:
            value = json.loads(text)
        except (TypeError, ValueError):
            return False
        return isinstance(value, dict) and all(key in value for key in required_keys)
    return validate
