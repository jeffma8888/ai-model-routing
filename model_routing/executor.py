"""Run a routed call with fallback, timing, validation and per-attempt logging."""

from __future__ import annotations

import json
import time
import uuid
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Tuple

from .providers import Provider, ProviderError
from .router import RouteDecision, Router


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
             validate: Optional[Callable[[str], object]] = None) -> CallResult:
        """Route and execute one call; raise :class:`AllModelsFailed` if none succeeds."""
        decision = self.router.select(task_name, flavor=flavor,
                                      generator_model=generator_model,
                                      exclude_models=exclude_models)
        task = self.router.tasks[task_name]
        registry = self.router.registry
        call_id = self.id_factory()
        call_tags = dict(tags or {})
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
                                                 attempt, call_tags))
            if text is not None:
                return CallResult(call_id, text, model_id, tuple(attempts), decision)
        raise AllModelsFailed(
            f"all {len(attempts)} routed models failed for task {task_name!r}",
            tuple(attempts), decision)

    def _record(self, call_id: str, decision: RouteDecision, registry, index: int,
                final: bool, attempt: Attempt, tags: Dict[str, str]) -> dict:
        return {
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
            "basis": decision.basis,
            "tags": dict(tags),
        }


def json_validator(*required_keys: str) -> Callable[[str], bool]:
    """Return a validator that accepts a JSON object containing every required key."""
    def validate(text: str) -> bool:
        try:
            value = json.loads(text)
        except (TypeError, ValueError):
            return False
        return isinstance(value, dict) and all(key in value for key in required_keys)
    return validate
