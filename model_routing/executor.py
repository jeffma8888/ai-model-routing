"""Run a routed call with fallback, timing, validation and per-attempt logging."""

from __future__ import annotations

import copy
import json
import math
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .delegation import DELEGATE
from .procedures import Procedure
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
             slice: Optional[str] = None,
             signals: Optional[Mapping] = None,
             procedures: Sequence[Procedure] = ()) -> CallResult:
        """Route and execute one call; raise :class:`AllModelsFailed` if none succeeds.

        ``prompt_tokens`` is the request's size in tokens; when None it is estimated with
        :func:`estimate_prompt_tokens`. Either way the route holds only models whose window
        fits it plus the task's expected output, and every record carries it as
        ``prompt_tokens`` with ``prompt_tokens_estimated`` (DESIGN 7 and 8.1 v1.507). A
        ``prompt_tokens`` that is not an integer >= 0 raises ``ValueError`` before any call.
        ``slice`` names a slice of the task, routed on that slice's own counts, and every
        record carries it (DESIGN 7 and 8.1 v1.511); ``select`` checks it before any call.
        ``signals`` maps signal names to callables and routes the task's cascades too: a
        cascade entry runs its cheap model and hands the call up to a fresh call of its strong
        model when ``signals[signal](text)`` is truthy or the cheap model raises
        ``ProviderError``, and its records carry ``cascade`` and ``escalated`` (DESIGN 7 and
        8.1 v1.537). A ``signals`` that is not a mapping, or a routed cascade whose signal is
        no callable in it, raises ``ValueError`` before any call.
        ``procedures`` (a list or tuple of :class:`Procedure`, ``()`` by default; ``None`` is
        refused) is passed to ``select``, which checks it before any call: a routed procedure
        entry runs by ``Procedure.run`` on a deep copy of ``messages``, each model call of its
        handle an attempt of its named model, then one closing attempt under its ID, ``error``
        when the run raises, else ``validate`` on its output; an ``error`` or ``invalid`` entry
        falls back, and its records carry the procedure keys (DESIGN 7 and 8.1 v1.578).
        """
        _check_prompt_tokens(prompt_tokens)
        if signals is not None and not isinstance(signals, Mapping):
            raise ValueError(f"signals must be None or a mapping, "
                             f"got {type(signals).__name__}")
        estimated = prompt_tokens is None
        size = estimate_prompt_tokens(messages) if estimated else prompt_tokens
        decision = self.router.select(task_name, flavor=flavor,
                                      generator_model=generator_model,
                                      exclude_models=exclude_models, prompt_tokens=size,
                                      slice=slice, cascades=signals is not None,
                                      procedures=procedures)
        cascades = {}
        if signals is not None:
            by_id = {cascade.id: cascade for cascade in self.router.tasks[task_name].cascades}
            for entry in (decision.primary, *decision.fallbacks):
                cascade = by_id.get(entry)
                if cascade is None:
                    continue
                if cascade.signal not in signals or not callable(signals[cascade.signal]):
                    raise ValueError(f"routed cascade {entry!r} needs a callable for its "
                                     f"signal {cascade.signal!r} in signals")
                cascades[entry] = cascade
        routed = {proc.id: proc for proc in procedures}  # select checked them (5.2 v1.577)
        return self._execute(task_name, decision, messages, dict(tags or {}), validate,
                             (size, estimated), cascades, signals, routed)

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
                 size: Optional[Tuple[int, bool]] = None,
                 cascades: Optional[Dict[str, object]] = None,
                 signals: Optional[Mapping] = None,
                 procedures: Optional[Dict[str, Procedure]] = None) -> CallResult:
        task = self.router.tasks[task_name]
        registry = self.router.registry
        call_id = self.id_factory()
        order = (decision.primary, *decision.fallbacks)
        attempts: List[Attempt] = []

        def log(attempt: Attempt, final: bool, entry: str, cascade=None, escalated=None,
                keys: Optional[dict] = None, family: Optional[str] = None):
            attempts.append(attempt)
            if self.monitor is not None:
                self.monitor.record(self._record(call_id, decision, registry, len(attempts) - 1,
                                                 final, attempt, call_tags, size, entry,
                                                 cascade, escalated, keys, family))

        for position, entry in enumerate(order):
            last = position == len(order) - 1
            proc = (procedures or {}).get(entry)
            if proc is not None:
                text = self._procedure(proc, messages, task, registry, validate, log, last)
                if text is not None:
                    return CallResult(call_id, text, entry, tuple(attempts), decision)
                continue
            cascade = (cascades or {}).get(entry)
            if cascade is None:
                attempt, text = self._checked(*self._run(entry, messages, task, registry),
                                              validate)
                log(attempt, text is not None or last, entry)
                if text is not None:
                    return CallResult(call_id, text, entry, tuple(attempts), decision)
                continue
            # DESIGN 7 v1.537: the cheap model first; a ProviderError or a truthy signal
            # hands the call up to a fresh call of the strong model on the same messages
            attempt, completion = self._run(cascade.cheap, messages, task, registry)
            if completion is not None and not signals[cascade.signal](completion.text):
                attempt, text = self._checked(attempt, completion, validate)
                log(attempt, text is not None or last, entry, cascade, False)
                if text is not None:
                    return CallResult(call_id, text, cascade.cheap, tuple(attempts), decision)
                continue
            log(attempt, False, entry, cascade, True)
            attempt, text = self._checked(*self._run(cascade.strong, messages, task, registry),
                                          validate)
            log(attempt, text is not None or last, entry, cascade, True)
            if text is not None:
                return CallResult(call_id, text, cascade.strong, tuple(attempts), decision)
        raise AllModelsFailed(
            f"all {len(attempts)} routed models failed for task {task_name!r}",
            tuple(attempts), decision)

    def _procedure(self, proc: Procedure, messages: List[dict], task, registry, validate, log,
                   last: bool) -> Optional[str]:
        """Run one procedure entry (DESIGN 7 v1.578): its accepted output, or None to move on.

        Each model call of the handle is an attempt of the procedure's model, a ``ProviderError``
        raised into ``fn`` after its record; then one closing attempt under the procedure's ID.
        A provider exception other than ``ProviderError`` propagates once the run has ended, and a
        later call of the handle within its bound raises it again without reaching the provider.
        """
        names = {"procedure": proc.name, "procedure_version": proc.version}
        state = {"calls": 0, "bug": None}

        def call(call_messages: List[dict]) -> str:
            if state["bug"] is not None:
                raise state["bug"]
            try:
                attempt, completion, exc = self._attempt(proc.model, call_messages, task,
                                                         registry)
            except Exception as bug:  # a bug, not an outage: it leaves .call (7 step 2)
                state["bug"] = bug
                raise
            state["calls"] += 1  # a call that reached the provider and has a record
            log(attempt, False, proc.id, keys=dict(names))
            if completion is None:
                raise exc
            return completion.text

        value = copy.deepcopy(messages)  # an error of the copy is the caller's: it propagates
        start = self.clock()
        run, error = None, None
        try:
            run = proc.run(value, call)
        except Exception as exc:
            error = f"{type(exc).__name__}: {exc}"
        if state["bug"] is not None:
            raise state["bug"]
        latency_ms = float((self.clock() - start) * 1000.0)
        text = None
        if run is None:
            attempt = Attempt(proc.id, "error", error, latency_ms, 0, 0, 0.0)
        elif validate is not None and not validate(run.output):
            attempt = Attempt(proc.id, "invalid", "validation failed", latency_ms, 0, 0,
                              run.tool_cost_usd)
        else:
            attempt = Attempt(proc.id, "ok", None, latency_ms, 0, 0, run.tool_cost_usd)
            text = run.output
        keys = dict(names, model_calls=state["calls"],
                    tool_calls=None if run is None else run.tool_calls,
                    tool_cost_usd=None if run is None else run.tool_cost_usd)
        family = "" if proc.model is None else registry.get(proc.model).family
        log(attempt, text is not None or last, proc.id, keys=keys, family=family)
        return text

    def _run(self, model_id: str, messages: List[dict], task, registry):
        """One timed provider call: its attempt, ``ok`` or ``error``, and the completion or None.

        A route with provider options passes a new copy of them as ``options``; any other route
        calls the provider as before v1.574 (DESIGN 7 v1.574).
        """
        attempt, completion, _ = self._attempt(model_id, messages, task, registry)
        return attempt, completion

    def _attempt(self, model_id: str, messages: List[dict], task, registry):
        """``_run``'s attempt and completion, and the ``ProviderError`` caught or None."""
        options = registry.get(model_id).provider_options if model_id in registry else {}
        start = self.clock()
        try:
            if options:
                completion = self.provider.complete(model_id, messages, task.timeout_s,
                                                    options=options)
            else:
                completion = self.provider.complete(model_id, messages, task.timeout_s)
        except ProviderError as exc:
            latency_ms = float((self.clock() - start) * 1000.0)
            return Attempt(model_id, "error", f"{type(exc).__name__}: {exc}",
                           latency_ms, 0, 0, 0.0), None, exc
        latency_ms = float((self.clock() - start) * 1000.0)
        cost = float(registry.get(model_id).cost(completion.input_tokens,
                                                  completion.output_tokens))
        return Attempt(model_id, "ok", None, latency_ms, completion.input_tokens,
                       completion.output_tokens, cost), completion, None

    @staticmethod
    def _checked(attempt: Attempt, completion, validate):
        """The attempt as ``validate`` leaves it, and the accepted text or None."""
        if completion is None:
            return attempt, None
        if validate is not None and not validate(completion.text):
            return replace(attempt, outcome="invalid", error="validation failed"), None
        return attempt, completion.text

    def _record(self, call_id: str, decision: RouteDecision, registry, index: int,
                final: bool, attempt: Attempt, tags: Dict[str, str],
                size: Optional[Tuple[int, bool]] = None, entry: Optional[str] = None,
                cascade=None, escalated: Optional[bool] = None, keys: Optional[dict] = None,
                family: Optional[str] = None) -> dict:
        model = registry.get(attempt.model) if family is None else None  # None: a closing record
        record = {
            "ts": self.now(),
            "call_id": call_id,
            "task": decision.task,
            "flavor": decision.flavor,
            "model": attempt.model,
            "family": model.family if model is not None else family,
            "attempt": index,
            "final": final,
            "outcome": attempt.outcome,
            "error": attempt.error,
            "latency_ms": attempt.latency_ms,
            "input_tokens": attempt.input_tokens,
            "output_tokens": attempt.output_tokens,
            "cost_usd": attempt.cost_usd,
            "routing_cost_usd": attempt.cost_usd if decision.flavor == "cost_effective" else 0.0,
        }
        if model is not None and model.pricing_basis == "self_hosted":  # DESIGN 8.1 v1.584
            record["pricing_basis"] = "self_hosted"
        record["below_bar"] = decision.below_bar
        # v1.537: by the route entry, so both attempts of a cascade entry share it
        if (attempt.model if entry is None else entry) in decision.below_bar_fallbacks:
            record["below_bar_fallback"] = True
        record["basis"] = decision.basis
        record["tags"] = dict(tags)
        record["slice"] = decision.slice
        if cascade is not None:
            record["cascade"] = cascade.id
            record["escalated"] = escalated
        if keys is not None:  # DESIGN 8.1 v1.578: a procedure entry's records
            record.update(keys)
        if size is not None:
            record["prompt_tokens"], record["prompt_tokens_estimated"] = size
        if decision.failure_policy != "none":  # DESIGN 8.1 v1.567: the last key
            record["expected_cost_per_success_usd"] = decision.expected_cost_per_success_usd
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
