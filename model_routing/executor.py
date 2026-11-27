"""Run a routed call with fallback, timing, validation and per-attempt logging."""

from __future__ import annotations

import copy
import json
import math
import random as _random
import threading
import time
import uuid
from collections.abc import Mapping
from dataclasses import dataclass, replace
from datetime import datetime, timezone
from typing import Callable, Dict, Iterable, List, Optional, Sequence, Tuple

from .budget import BudgetExceeded, BudgetLedger, billing_bound
from .delegation import DELEGATE, INLINE, DelegationDecision
from .procedures import Procedure
from .providers import Provider, ProviderError
from .router import Policy, RouteDecision, Router, _check_pin, _check_prompt_tokens
from .stats import _SIDE_TOTALS


@dataclass(frozen=True)
class Attempt:
    """One provider call within a routed call.

    ``cached_input_tokens`` and ``cache_write_tokens`` are its completion's counts, ``None`` when
    the provider gave none and on an error or a procedure's closing attempt (DESIGN 7 v1.589).
    """

    model: str
    outcome: str
    error: Optional[str]
    latency_ms: float
    input_tokens: int
    output_tokens: int
    cost_usd: float
    cached_input_tokens: Optional[int] = None
    cache_write_tokens: Optional[int] = None


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
    UTC timestamp and ``id_factory`` returns a call ID; all are injectable. ``ledger``, None
    or a :class:`BudgetLedger`, holds each provider call's estimate before it and settles its
    measured cost after (DESIGN 7 v1.595); a ``downgrade`` budget moves a call to the next route
    entry that clears the bar, and a ``day`` or ``month`` budget reads its window from ``now``
    (DESIGN 7 v1.596). ``random``, None for ``random.random``, draws whether a call of a task
    with a ``shadow_rate`` is shadowed (DESIGN 7 v1.607). ``shadow_runner``, None or a callable,
    takes each shadow as one job with no argument: one that runs the job on another thread, such as
    a ``concurrent.futures.ThreadPoolExecutor``'s ``submit``, lets ``.call`` return without waiting
    for the shadow's provider call or its errors, while one that runs it at once, and None, make
    ``.call`` wait for the shadow on the caller's thread (DESIGN 7 v1.617, review iter-468
    should-fix 1).

    One executor, with its router, a :class:`Monitor` and a :class:`BudgetLedger`, may serve many
    threads at once: a call keeps its state in its own locals and sets no attribute of the executor
    or its router. The provider, an injected ``clock``, ``now``, ``id_factory`` or ``random``, a
    ``monitor`` that is no :class:`Monitor`, ``validate``, the ``signals`` callables and a
    procedure's ``fn``, and a change to the router's registry, tasks, stats or priors while calls
    run are the caller's to guard (DESIGN 7 v1.616, review iter-467 nit 1).
    """

    def __init__(self, router: Router, provider: Provider, monitor=None,
                 clock: Callable[[], float] = time.monotonic,
                 now: Optional[Callable[[], str]] = None,
                 id_factory: Optional[Callable[[], str]] = None,
                 ledger: Optional[BudgetLedger] = None,
                 random: Optional[Callable[[], float]] = None,
                 shadow_runner: Optional[Callable[[Callable[[], None]], object]] = None):
        if ledger is not None and not isinstance(ledger, BudgetLedger):
            raise ValueError(f"ledger must be None or a BudgetLedger, got {type(ledger).__name__}")
        if random is not None and not callable(random):
            raise ValueError(f"random must be None or a callable, got {type(random).__name__}")
        if shadow_runner is not None and not callable(shadow_runner):  # DESIGN 7 v1.617
            raise ValueError(f"shadow_runner must be None or a callable, "
                             f"got {type(shadow_runner).__name__}")
        self.router = router
        self.provider = provider
        self.monitor = monitor
        self.clock = clock
        self.now = now if now is not None else _utc_now
        self.id_factory = id_factory if id_factory is not None else _new_id
        self.ledger = ledger
        self.random = random if random is not None else _random.random  # DESIGN 7 v1.607
        self.shadow_runner = shadow_runner  # DESIGN 7 v1.617
        # DESIGN 7 v1.597: a strict budget reads each call's billing bound
        self._strict = ledger is not None and any(budget.strict for budget in ledger.budgets)

    def call(self, task_name: str, messages: List[dict], flavor: str = "cost_effective",
             generator_model: Optional[str] = None, exclude_models: Iterable[str] = (),
             tags: Optional[Dict[str, str]] = None,
             validate: Optional[Callable[[str], object]] = None, *,
             prompt_tokens: Optional[int] = None,
             slice: Optional[str] = None,
             signals: Optional[Mapping] = None,
             procedures: Sequence[Procedure] = (),
             policy: Optional[Policy] = None,
             pin_route: Optional[str] = None,
             pinned_by: Optional[str] = None,
             allow_below_bar: bool = False) -> CallResult:
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
        A task with a ``shadow_rate`` above 0 may shadow the call: once the routed call has
        returned, one call of the shadow route on the same messages, whose failure never fails
        the routed call, both calls' records paired by ``pair_id`` (DESIGN 7 and 8.1 v1.607),
        each saying by ``checked`` whether ``validate`` was given (7 and 8.1 v1.618);
        none when the routed answer came from the shadow route's model (7 and 8.1 v1.609).
        With a ``shadow_runner`` the shadow is handed to it as one job, on a deep copy of
        ``messages``, and ``.call`` returns once the runner has taken it (7 v1.617).
        ``policy``, None or a :class:`Policy`, is passed to ``select``, which checks it before any
        call: every entry the call can reach, its fallbacks, a cascade's two models, a procedure's
        model and a downgrade move's landing included, is one the policy allows, and a shadow
        route it rules out is not sent, with no draw and no pair keys. Under a policy whose ``label`` is
        not None every record the call writes, its shadow's and budget records included, carries it
        as ``policy`` (DESIGN 7 and 8.1 v1.642).
        ``pin_route`` and ``allow_below_bar`` are passed to ``select`` (5.2 v1.639), and a pin needs
        ``pinned_by``, a non-empty tag, checked before any call: the call runs the pin alone, with no
        fallback and no shadow, and each attempt record carries ``pinned_by`` (DESIGN 7 v1.639).
        """
        _check_pin(pin_route, allow_below_bar)  # DESIGN 7 v1.639: before select, any ID or call
        if pinned_by is not None and (not isinstance(pinned_by, str) or not pinned_by):
            raise ValueError(f"pinned_by must be None or a non-empty string, got {pinned_by!r}")
        if pin_route is not None and pinned_by is None:
            raise ValueError("a pinned call needs a pinned_by tag")
        if pinned_by is not None and pin_route is None:
            raise ValueError("pinned_by needs a pin_route")
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
                                      procedures=procedures, policy=policy,
                                      pin_route=pin_route, allow_below_bar=allow_below_bar)
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
        # DESIGN 7 v1.639: a pinned call is never shadowed, so no draw
        shadow = None if pin_route is not None else self._shadow_route(task_name, decision, tags)
        label = None if policy is None else policy.label  # DESIGN 7 v1.642: select checked it
        return self._execute(task_name, decision, messages, dict(tags or {}), validate,
                             (size, estimated), cascades, signals, routed, shadow, pinned_by, label)

    def call_pair(self, task_name: str, roots: Sequence[str], leaves: Sequence[str],
                  messages: List[dict], harness: Callable[[str, str, List[dict]], Mapping],
                  flavor: str = "cost_effective", *, generator_model: Optional[str] = None,
                  exclude_models: Iterable[str] = (), policy: Optional[Policy] = None,
                  tags: Optional[Dict[str, str]] = None,
                  validate: Optional[Callable[[str], object]] = None) -> CallResult:
        """Route a root and leaf pair with ``select_pair`` and run ``harness(root, leaf, messages)``
        on each pair of the route in turn, as ``.call`` runs a model, with one record per attempt
        holding the four side token counts the harness returned (DESIGN 7 and 8.1 v1.678).

        With a ``ledger`` each pair holds its list-price estimate before its harness call and
        settles its side cost after, so warn, refuse, downgrade and strict budgets meet it as they
        meet ``.call``, with budget records and ``budget_moves`` (DESIGN 7 v1.681). Raises
        ``ValueError`` for a ``harness`` that is not callable, before ``select_pair``; for two pairs
        with one ID; and for a return value that is not a mapping of a ``str`` ``text`` and the four
        counts, each an int >= 0 that is not a bool.
        """
        if not callable(harness):
            raise ValueError(f"harness must be a callable, got {type(harness).__name__}")
        decision = self.router.select_pair(task_name, roots, leaves, flavor,
                                           generator_model=generator_model,
                                           exclude_models=exclude_models, policy=policy)
        sides = {f"{root}+{leaf}": (root, leaf) for root in roots for leaf in leaves}
        if len(sides) != len(roots) * len(leaves):  # an ID may hold "+", so never split one
            raise ValueError("two pairs have one ID, so a pair's root and leaf cannot be told apart")
        label = None if policy is None else policy.label  # select_pair checked it
        return self._run_pair(task_name, decision, sides, messages, harness, tags, validate, label)

    def _run_pair(self, task_name: str, decision: RouteDecision, sides: Dict[str, Tuple[str, str]],
                  messages: List[dict], harness: Callable[[str, str, List[dict]], Mapping],
                  tags: Optional[Dict[str, str]], validate: Optional[Callable[[str], object]],
                  label: Optional[str]) -> CallResult:
        """The attempt loop of ``.call_pair`` over a pair route, from its call ID on (DESIGN 7 v1.678
        and v1.681); ``.call_delegated`` runs a pair decision on it too (7 v1.685)."""
        task = self.router.tasks[task_name]
        registry, call_id, call_tags = self.router.registry, self.id_factory(), dict(tags or {})
        order, attempts, moves = (decision.primary, *decision.fallbacks), [], []

        def note(fields: dict) -> None:  # DESIGN 7 v1.681: a budget record, as 8.1 v1.598
            if self.monitor is not None:
                self.monitor.record({"ts": self.now(), "call_id": call_id, "task": decision.task,
                                     **_policy_key(label), "tags": dict(call_tags), **fields})

        moving = None  # DESIGN 7 v1.681: the last downgrade refusal while the call is moving
        for position, entry in enumerate(order):
            if moving is not None:
                if decision.below_bar or entry in decision.below_bar_fallbacks:
                    break  # a move never lands under the bar (7 v1.596)
                moving = None
            root, leaf = sides[entry]
            hold = None
            if self.ledger is not None:
                try:
                    hold = self._pair_hold(task, entry, registry.get(root), registry.get(leaf),
                                           call_tags)
                except BudgetExceeded as exc:  # only this call's own reservation is caught here
                    note(_refused(exc))
                    if exc.budget.mode != "downgrade":
                        exc.attempts, exc.decision = tuple(attempts), decision
                        raise
                    moving = exc
                    moves.append({"entry": entry, "model": entry, "budget": exc.budget.name})
                    continue
            cost = None if self._strict else 0.0  # 7 v1.597: a raised run's cost is not known
            try:
                start = self.clock()
                try:
                    run, error = harness(root, leaf, messages), None
                except ProviderError as exc:
                    run, error = None, f"{type(exc).__name__}: {exc}"
                latency_ms = float((self.clock() - start) * 1000.0)
                counts, text = (0, 0, 0, 0), None
                if error is not None:
                    attempt = Attempt(entry, "error", error, latency_ms, 0, 0, 0.0)
                else:
                    counts, text = _pair_run(run), run["text"]
                    side = float(registry.get(root).cost(*counts[:2]) + registry.get(leaf).cost(*counts[2:]))
                    attempt = Attempt(entry, "ok", None, latency_ms, counts[0] + counts[2],
                                      counts[1] + counts[3], side)
                cost = attempt.cost_usd
            finally:
                if hold is not None:  # DESIGN 7 v1.681: settled before the attempt's record
                    events = (self.ledger.settle_unpriced(hold) if cost is None
                              else self.ledger.settle(hold, cost))
                    for event in events:
                        note(_warned(event))
            if text is not None and validate is not None and not validate(text):
                attempt, text = replace(attempt, outcome="invalid", error="validation failed"), None
            attempts.append(attempt)
            # DESIGN 8.1 v1.678: the four after slice; `attempt` counts the attempts made, which a
            # refused pair adds none to (7 v1.681), and `final` is read from the route position
            if self.monitor is not None:
                self.monitor.record(self._record(
                    call_id, decision, registry, len(attempts) - 1,
                    text is not None or position == len(order) - 1, attempt, call_tags, entry=entry,
                    keys=dict(zip(_SIDE_TOTALS, counts)), family=registry.get(root).family,
                    moves=moves, policy_label=label))
            if text is not None:
                return CallResult(call_id, text, entry, tuple(attempts), decision)
        if moving is not None:
            moving.attempts, moving.decision = tuple(attempts), decision
            raise moving
        raise AllModelsFailed(f"all {len(attempts)} routed pairs failed for task {task_name!r}",
                              tuple(attempts), decision)

    def _pair_hold(self, task, entry: str, root, leaf, tags: Dict[str, str]):
        """Hold a pair's list-price estimate, one whole run (DESIGN 7 v1.681): each side at its mean
        tokens inside the pair when the pair's key holds them (4.3 v1.671), else at the task's
        expected sizes, with no cache count; a strict budget meets no billing bound (v1.597)."""
        side_tokens = self.router.stats.mean_side_tokens(task.name, entry)
        if side_tokens is None:
            side_tokens = ((task.expected_input_tokens, task.expected_output_tokens),) * 2
        estimate = float(root.cost(*side_tokens[0]) + leaf.cost(*side_tokens[1]))
        extra = self._at()
        if self._strict:  # a harness may call either side any number of times
            extra["bound_usd"] = None
        return self.ledger.reserve(task.name, tags, estimate, entry, **extra)

    def _shadow_route(self, task_name: str, decision: RouteDecision,
                      tags: Optional[Dict[str, str]]) -> Optional[str]:
        """The route a call is shadowed on, or None when it is not (DESIGN 7 v1.607)."""
        task = self.router.tasks[task_name]
        if task.shadow_rate <= 0:
            return None
        registry = self.router.registry
        if task.shadow_route is not None and task.shadow_route not in registry:
            raise ValueError(f"task {task_name!r}: shadow_route {task.shadow_route!r} is not "
                             f"a registry model")
        if tags and "shadow" in tags:
            raise ValueError("tag name shadow is set on a shadowed call's shadow; "
                             "pass another name")
        models = {c.model_id: c for c in decision.candidates if c.model_id in registry}
        target = task.shadow_route
        if target is None:
            passing = sorted((c for c in models.values() if c.passes),
                             key=lambda c: (-c.quality_lb, c.model_id))
            if not passing:
                return None
            target = passing[0].model_id
        if target == decision.primary or not models[target].eligible:
            return None
        value = self.random()
        if isinstance(value, bool) or not isinstance(value, (int, float)) \
                or not 0.0 <= value < 1.0:  # review iter-456 must-fix 2
            raise ValueError(f"random() must return a real number in [0, 1), got {value!r}")
        return target if value < task.shadow_rate else None

    def call_delegated(self, decision, messages: List[dict],
                       tags: Optional[Dict[str, str]] = None,
                       validate: Optional[Callable[[str], object]] = None, *,
                       harness: Optional[Callable[[str, str, List[dict]], Mapping]] = None) -> CallResult:
        """Run the hand-off of a ``delegate`` :class:`DelegationDecision` on its route.

        ``messages`` is the brief. The route is used as decided, with fallback and
        validation as in :meth:`call`; every record is tagged ``delegated`` and
        ``parent``. An inline decision, or a caller tag with either name, raises
        ``ValueError`` before any call (DESIGN 7, v1.11). A pair decision from
        ``decide_delegation`` with ``delegate_roots`` and ``delegate_leaves`` runs through
        ``harness(root, leaf, messages)`` as :meth:`call_pair` runs its route (7 v1.685); a pair
        decision with no ``harness``, a ``harness`` on any other, and a route entry that does not
        split one way into a registry root and leaf raise ``ValueError`` before any ID.
        """
        if decision.mode != DELEGATE:
            raise ValueError(f"decision mode is {decision.mode!r}: inline work happens in the "
                             f"parent's own call, so there is no hand-off to run")
        if decision.route is None:
            raise ValueError("delegate decision has no route to run")
        if harness is not None and not callable(harness):  # DESIGN 7 v1.685
            raise ValueError(f"harness must be None or a callable, got {type(harness).__name__}")
        route, registry = decision.route, self.router.registry
        if harness is None and _pair_splits(registry, route.primary):  # DESIGN 7 v1.684
            raise ValueError(f"delegate route {route.primary!r} is a pair: a pair from delegate_roots and "
                             f"delegate_leaves runs through a harness, so pass it as harness or run it "
                             f"with call_pair")
        sides: Dict[str, Tuple[str, str]] = {}
        if harness is not None:  # DESIGN 7 v1.685: the decision holds the pair IDs alone
            if not _pair_splits(registry, route.primary):
                raise ValueError(f"harness runs a pair decision, and delegate route {route.primary!r} "
                                 f"is no pair of a registry root and leaf")
            for entry in (route.primary, *route.fallbacks):
                splits = _pair_splits(registry, entry)
                if len(splits) != 1:
                    raise ValueError(f"route entry {entry!r} does not split one way into a registry root "
                                     f"and leaf joined by '+', so its root and leaf cannot be told apart")
                sides[entry] = splits[0]
        call_tags = dict(tags or {})
        reserved = sorted(key for key in ("delegated", "parent") if key in call_tags)
        if reserved:
            raise ValueError(f"tag names {', '.join(reserved)} are set by call_delegated; "
                             f"pass other names")
        call_tags["delegated"] = "true"
        call_tags["parent"] = decision.parent
        if harness is not None:  # DESIGN 7 v1.685: no policy, as .call_delegated takes none
            return self._run_pair(decision.task, route, sides, messages, harness, call_tags, validate,
                                  None)
        return self._execute(decision.task, decision.route, messages, call_tags, validate)

    def record_mode(self, decision, actual_mode: str, input_tokens: int,
                    tags: Optional[Mapping[str, str]] = None) -> dict:
        """Log the mode the agent took beside the mode ``decision`` advised (DESIGN 7 v1.687).

        ``decision`` is a :class:`DelegationDecision`, ``actual_mode`` ``"inline"`` or
        ``"delegate"`` and ``input_tokens`` the work's input size, an ``int`` >= 0. The mode record
        (8.1 v1.687) holds ``ts``, ``call_id``, the decision's ``task``, ``flavor`` and ``parent``,
        its ``mode`` as ``advised_mode``, ``actual_mode``, its ``reason``, ``input_tokens`` as
        ``work_input_tokens`` and ``tags``; it goes to the monitor when there is one, and a copy is returned. No router,
        provider or ledger call is made. A bad argument raises ``ValueError`` before any ID or record.
        """
        if not isinstance(decision, DelegationDecision):
            raise ValueError(f"decision must be a DelegationDecision, got {type(decision).__name__}")
        if not (isinstance(decision.mode, str) and decision.mode in (INLINE, DELEGATE)):
            raise ValueError(f"decision mode must be 'inline' or 'delegate', got {decision.mode!r}")
        if not (isinstance(actual_mode, str) and actual_mode in (INLINE, DELEGATE)):
            raise ValueError(f"actual_mode must be 'inline' or 'delegate', got {actual_mode!r}")
        if not isinstance(input_tokens, int) or isinstance(input_tokens, bool) or input_tokens < 0:
            raise ValueError(f"input_tokens must be an int >= 0, got {input_tokens!r}")
        if tags is not None and not (isinstance(tags, Mapping) and all(
                isinstance(key, str) and isinstance(value, str) for key, value in tags.items())):
            raise ValueError(f"tags must be None or a mapping of str to str, got {tags!r}")
        rec = {"ts": self.now(), "call_id": self.id_factory(), "task": decision.task,
               "flavor": decision.flavor, "parent": decision.parent, "advised_mode": decision.mode,
               "actual_mode": actual_mode, "reason": decision.reason, "work_input_tokens": input_tokens,
               "tags": dict(tags or {})}
        if self.monitor is not None:
            self.monitor.record(rec)
        return dict(rec, tags=dict(rec["tags"]))

    def _execute(self, task_name: str, decision: RouteDecision, messages: List[dict],
                 call_tags: Dict[str, str],
                 validate: Optional[Callable[[str], object]],
                 size: Optional[Tuple[int, bool]] = None,
                 cascades: Optional[Dict[str, object]] = None,
                 signals: Optional[Mapping] = None,
                 procedures: Optional[Dict[str, Procedure]] = None,
                 shadow: Optional[str] = None,
                 pinned_by: Optional[str] = None,
                 policy_label: Optional[str] = None) -> CallResult:
        task = self.router.tasks[task_name]
        registry = self.router.registry
        call_id = self.id_factory()
        pair = shadow_id = None
        if shadow is not None:  # DESIGN 7 and 8.1 v1.607: both IDs before any provider call
            shadow_id = self.id_factory()
            if shadow_id == call_id:  # review iter-456 must-fix 1
                raise ValueError(f"id_factory returned {call_id!r} again for the call's shadow")
            # 8.1 v1.618: and whether the call was given a check, on both calls' records
            pair = {"pair_id": call_id, "shadow": False, "checked": validate is not None}
        order = (decision.primary, *decision.fallbacks)
        attempts: List[Attempt] = []
        moves: List[dict] = []  # DESIGN 7 v1.596: each downgrade move so far, in order
        scope = None
        if self.ledger is not None:  # DESIGN 7 v1.595: the hold's task, tags and sizes
            out = dict(task.slices.get(decision.slice) or {}).get(
                "expected_output_tokens", task.expected_output_tokens)

            def note(fields: dict) -> None:  # DESIGN 7 and 8.1 v1.598: a budget record
                if self.monitor is not None:
                    self.monitor.record({"ts": self.now(), "call_id": call_id,
                                         "task": decision.task, **_policy_key(policy_label),
                                         "tags": dict(call_tags), **(pair or {}), **fields})

            # the fifth item collects this call's own downgrade refusals (7 v1.596)
            scope = (task_name, call_tags, None if size is None else size[0], out, [], note)

        def log(attempt: Attempt, final: bool, entry: str, cascade=None, escalated=None,
                keys: Optional[dict] = None, family: Optional[str] = None):
            attempts.append(attempt)
            if self.monitor is not None:
                self.monitor.record(self._record(call_id, decision, registry, len(attempts) - 1,
                                                 final, attempt, call_tags, size, entry,
                                                 cascade, escalated, keys, family, moves, pair,
                                                 pinned_by, policy_label))

        try:
            result = self._entries(task_name, decision, messages, validate, cascades, signals,
                                   procedures, task, registry, call_id, order, attempts, log,
                                   scope, moves)
        except BudgetExceeded as exc:
            exc.attempts, exc.decision = tuple(attempts), decision
            raise
        # DESIGN 7 v1.607: only once the routed call has returned; v1.609: and never on an
        # answer of the shadow route's own model, a fallback or a cascade leg onto it
        if shadow is not None and result.model != shadow:
            if self.shadow_runner is None:
                self._shadow(shadow, task_name, task, decision, messages, call_tags, validate,
                             size, call_id, shadow_id, policy_label)
            else:  # DESIGN 7 v1.617: off the caller's path, on its own copy of the messages
                self.shadow_runner(self._job(shadow, task_name, task, decision,
                                             copy.deepcopy(messages), call_tags, validate, size,
                                             call_id, shadow_id, policy_label))
        return result

    def _job(self, *args) -> Callable[[], None]:
        """The shadow as one job with no argument, which runs it once (DESIGN 7 v1.617).

        A second call raises ``RuntimeError`` and writes nothing, so a runner that retries a job
        cannot give one pair two shadow records.
        """
        once = threading.Lock()

        def job() -> None:
            if not once.acquire(blocking=False):
                raise RuntimeError("this shadow job has already run; a job runs its shadow once")
            self._shadow(*args)

        return job

    def _shadow(self, model_id: str, task_name: str, task, decision: RouteDecision,
                messages: List[dict],
                call_tags: Dict[str, str], validate, size, pair_id: str, call_id: str,
                policy_label: Optional[str] = None) -> None:
        """One provider call of the shadow route, logged under its own call ID (7 v1.607).

        A ``ProviderError``, an invalid output or a refusal of its own reservation never
        reaches the caller; any other exception propagates, as in step 2.
        """
        registry = self.router.registry
        tags = dict(call_tags, shadow="true")
        pair = {"pair_id": pair_id, "shadow": True, "checked": validate is not None}  # 8.1 v1.618
        scope, refused = None, []
        if self.ledger is not None:
            out = dict(task.slices.get(decision.slice) or {}).get(
                "expected_output_tokens", task.expected_output_tokens)

            def note(fields: dict) -> None:
                if self.monitor is not None:
                    self.monitor.record({"ts": self.now(), "call_id": call_id,
                                         "task": decision.task, **_policy_key(policy_label),
                                         "tags": dict(tags), **pair, **fields})
                # marked only once recorded: _attempt raises its own refusal right after this
                # returns, so a monitor's own exception is never taken for it (iter-456 should-fix 1)
                if fields.get("budget_event") == "refused":
                    refused.append(fields)

            scope = (task_name, tags, None if size is None else size[0], out, None, note)
        try:
            attempt, completion, _ = self._attempt(model_id, messages, task, registry, scope)
        except BudgetExceeded:
            if refused:
                return
            raise
        attempt, _ = self._checked(attempt, completion, validate)
        if self.monitor is not None:
            self.monitor.record(self._record(call_id, decision, registry, 0, True, attempt, tags,
                                             size, model_id, pair=pair, policy_label=policy_label))

    def _entries(self, task_name, decision, messages, validate, cascades, signals, procedures,
                 task, registry, call_id, order, attempts, log, scope, moves) -> CallResult:
        moving = None  # DESIGN 7 v1.596: the last downgrade refusal while the call is moving
        for position, entry in enumerate(order):
            last = position == len(order) - 1
            if moving is not None:
                if decision.below_bar or entry in decision.below_bar_fallbacks:
                    raise moving  # a move never lands under the bar
                moving = None
            proc = (procedures or {}).get(entry)
            if proc is not None and scope is not None and self._strict:
                refusal = self._strict_refusal(scope, proc.id)  # DESIGN 7 v1.597
                if refusal is not None:
                    scope[5](_refused(refusal))  # DESIGN 7 v1.598
                    if refusal.budget.mode != "downgrade":
                        raise refusal
                    moving = refusal
                    moves.append({"entry": entry, "model": proc.id,
                                  "budget": refusal.budget.name})
                    continue
            if proc is not None:  # a downgrade refusal inside the run ends the call (7 v1.596)
                text = self._procedure(proc, messages, task, registry, validate, log, last,
                                       scope)
                if text is not None:
                    return CallResult(call_id, text, entry, tuple(attempts), decision)
                continue
            try:
                result = self._entry(entry, cascades, signals, messages, task, registry, scope,
                                     validate, log, last, call_id, attempts, decision)
            except BudgetExceeded as exc:
                if scope is None or not any(own is exc for own in scope[4]):
                    raise  # not this call's own downgrade refusal (review iter-444 must-fix 1)
                moving = exc  # DESIGN 7 v1.596: no call was made; move on along the route
                moves.append({"entry": entry, "model": exc.model, "budget": exc.budget.name})
                continue
            if result is not None:
                return result
        if moving is not None:
            raise moving
        raise AllModelsFailed(
            f"all {len(attempts)} routed models failed for task {task_name!r}",
            tuple(attempts), decision)

    def _entry(self, entry, cascades, signals, messages, task, registry, scope, validate, log,
               last, call_id, attempts, decision) -> Optional[CallResult]:
        """Run one plain or cascade route entry: its result, or None to move on."""
        cascade = (cascades or {}).get(entry)
        if cascade is None:
            attempt, text = self._checked(*self._run(entry, messages, task, registry,
                                                     scope), validate)
            log(attempt, text is not None or last, entry)
            if text is not None:
                return CallResult(call_id, text, entry, tuple(attempts), decision)
            return None
        # DESIGN 7 v1.537: the cheap model first; a ProviderError or a truthy signal
        # hands the call up to a fresh call of the strong model on the same messages
        attempt, completion = self._run(cascade.cheap, messages, task, registry, scope)
        if completion is not None and not signals[cascade.signal](completion.text):
            attempt, text = self._checked(attempt, completion, validate)
            log(attempt, text is not None or last, entry, cascade, False)
            if text is not None:
                return CallResult(call_id, text, cascade.cheap, tuple(attempts), decision)
            return None
        log(attempt, False, entry, cascade, True)
        attempt, text = self._checked(*self._run(cascade.strong, messages, task, registry,
                                                 scope), validate)
        log(attempt, text is not None or last, entry, cascade, True)
        if text is not None:
            return CallResult(call_id, text, cascade.strong, tuple(attempts), decision)
        return None

    def _strict_refusal(self, scope, model: str) -> Optional[BudgetExceeded]:
        """The refusal of a procedure entry by a strict budget that applies, whose tool cost has
        no bound: the first strict ``refuse`` budget, else ``downgrade``; no other budget is read
        (DESIGN 7 v1.597, review iter-445 should-fix 1)."""
        applying = [budget for budget in self.ledger.budgets
                    if budget.strict and budget.applies(scope[0], scope[1])]
        for mode in ("refuse", "downgrade"):
            for budget in applying:
                if budget.mode == mode:
                    at = self._at().get("at")
                    [(_, label)] = BudgetLedger._slots([budget], at)  # v1.598: its window
                    return BudgetExceeded(budget, self.ledger.spent_usd(budget.name, at),
                                          self.ledger.held_usd(budget.name, at), 0.0, model,
                                          unbounded=True, window=label)
        return None

    def _at(self) -> dict:
        """``{"at": now()}`` for a ledger with a day or month budget, else ``{}`` (7 v1.596)."""
        if any(budget.window != "total" for budget in self.ledger.budgets):
            return {"at": self.now()}
        return {}

    def _procedure(self, proc: Procedure, messages: List[dict], task, registry, validate, log,
                   last: bool, scope=None) -> Optional[str]:
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
                attempt, completion, exc = self._attempt(
                    proc.model, call_messages, task, registry,
                    None if scope is None else (scope[0], scope[1], None, scope[3], None,
                                                scope[5]))
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
        if scope is not None:  # DESIGN 7 v1.595: the tool cost, spent with no hold
            for event in self.ledger.charge(scope[0], scope[1], attempt.cost_usd, **self._at()):
                scope[5](_warned(event))  # DESIGN 7 v1.598
        log(attempt, text is not None or last, proc.id, keys=keys, family=family)
        return text

    def _run(self, model_id: str, messages: List[dict], task, registry, scope=None):
        """One timed provider call: its attempt, ``ok`` or ``error``, and the completion or None.

        A route with provider options passes a new copy of them as ``options``; any other route
        calls the provider as before v1.574 (DESIGN 7 v1.574).
        """
        attempt, completion, _ = self._attempt(model_id, messages, task, registry, scope)
        return attempt, completion

    def _attempt(self, model_id: str, messages: List[dict], task, registry, scope=None):
        """``_run``'s attempt and completion, and the ``ProviderError`` caught or None.

        With a ``scope`` (task, tags, prompt tokens or None, output tokens, and the list of the
        call's own downgrade refusals or None) the ledger holds the call's list-price estimate
        before it and settles the attempt's cost after (7 v1.595 and v1.596).
        """
        if scope is None:
            return self._provider_call(model_id, messages, task, registry)
        name, tags, prompt, out, refused, note = scope
        size_in = estimate_prompt_tokens(messages) if prompt is None else prompt
        estimate = float(registry.get(model_id).cost(size_in, out)) if model_id in registry else 0.0
        extra = self._at()
        if self._strict:  # DESIGN 7 v1.597: None for a model outside the registry
            extra["bound_usd"] = (billing_bound(registry.get(model_id))
                                  if model_id in registry else None)
        try:
            hold = self.ledger.reserve(name, tags, estimate, model_id, **extra)
        except BudgetExceeded as exc:
            note(_refused(exc))  # DESIGN 7 v1.598: a refusal of this call's own reservation
            if refused is not None and exc.budget.mode == "downgrade":
                refused.append(exc)  # a refusal of this call's own reservation may move it
            raise
        cost = None if self._strict else 0.0  # 7 v1.597: a raised call's cost is not known
        try:
            result = self._provider_call(model_id, messages, task, registry)
            cost = result[0].cost_usd
            return result
        finally:
            if cost is None:  # DESIGN 7 v1.597: a strict budget adds the bound it held
                events = self.ledger.settle_unpriced(hold)
            else:
                events = self.ledger.settle(hold, cost)
            for event in events:  # DESIGN 7 v1.598: each crossing right after its settle; a
                # monitor error here propagates in place of the call's own (review iter-446 nit 4)
                note(_warned(event))

    def _provider_call(self, model_id: str, messages: List[dict], task, registry):
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
        # DESIGN 7 v1.589: a provider's own completion type may hold only the three v1.588 fields
        cached = getattr(completion, "cached_input_tokens", None)
        write = getattr(completion, "cache_write_tokens", None)
        cost = float(registry.get(model_id).cost(
            completion.input_tokens, completion.output_tokens,
            cached_input_tokens=0 if cached is None else cached,
            cache_write_tokens=0 if write is None else write))  # a refused count is a bug: raise
        return Attempt(model_id, "ok", None, latency_ms, completion.input_tokens,
                       completion.output_tokens, cost, cached, write), completion, None

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
                family: Optional[str] = None, moves: Optional[List[dict]] = None,
                pair: Optional[dict] = None, pinned_by: Optional[str] = None,
                policy_label: Optional[str] = None) -> dict:
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
        }
        for name in ("cached_input_tokens", "cache_write_tokens"):  # DESIGN 8.1 v1.589
            if getattr(attempt, name) is not None:
                record[name] = getattr(attempt, name)
        record.update({
            "cost_usd": attempt.cost_usd,
            "routing_cost_usd": attempt.cost_usd if decision.flavor == "cost_effective" else 0.0,
        })
        if model is not None and model.pricing_basis == "self_hosted":  # DESIGN 8.1 v1.584
            record["pricing_basis"] = "self_hosted"
        record["below_bar"] = decision.below_bar
        # v1.537: by the route entry, so both attempts of a cascade entry share it
        if (attempt.model if entry is None else entry) in decision.below_bar_fallbacks:
            record["below_bar_fallback"] = True
        record["basis"] = decision.basis
        if pinned_by is not None:  # DESIGN 8.1 v1.639: a pinned call's tag
            record["pinned_by"] = pinned_by
        record.update(_policy_key(policy_label))  # DESIGN 8.1 v1.642: after any pinned_by
        record["tags"] = dict(tags)
        record["slice"] = decision.slice
        if pair is not None:  # DESIGN 8.1 v1.607: a shadowed call's records
            record.update(pair)
        if cascade is not None:
            record["cascade"] = cascade.id
            record["escalated"] = escalated
        if keys is not None:  # DESIGN 8.1 v1.578: a procedure entry's records
            record.update(keys)
        if moves:  # DESIGN 8.1 v1.596: the downgrade moves before this record
            record["budget_moves"] = [dict(move) for move in moves]
        if size is not None:
            record["prompt_tokens"], record["prompt_tokens_estimated"] = size
        if decision.failure_policy != "none":  # DESIGN 8.1 v1.567: the last key
            record["expected_cost_per_success_usd"] = decision.expected_cost_per_success_usd
        return record


def _pair_splits(registry, entry: str) -> List[Tuple[str, str]]:
    """Each way ``entry``, no registry ID itself, splits into a registry root and a registry leaf
    joined by ``+``, as ``select_pair`` names a pair (DESIGN 7 v1.684 and v1.685)."""
    if entry in registry:
        return []
    return [(entry[:i], entry[i + 1:]) for i, char in enumerate(entry)
            if char == "+" and entry[:i] in registry and entry[i + 1:] in registry]


def _pair_run(run) -> Tuple[int, int, int, int]:
    """A harness's four side counts, its return value checked (DESIGN 7 v1.678)."""
    if not isinstance(run, Mapping) or not isinstance(run.get("text"), str) or not all(
            isinstance(run.get(key), int) and not isinstance(run[key], bool) and run[key] >= 0
            for key in _SIDE_TOTALS):
        raise ValueError(f"harness must return a mapping of a str text and {', '.join(_SIDE_TOTALS)}, "
                         f"each an int >= 0, got {run!r}")
    return tuple(run[key] for key in _SIDE_TOTALS)


def _policy_key(label: Optional[str]) -> dict:
    """A record's ``policy`` key, or none when the call's policy has no label (DESIGN 8.1 v1.642)."""
    return {} if label is None else {"policy": label}


def _refused(exc: BudgetExceeded) -> dict:
    """A refused budget record's fields after ``tags`` (DESIGN 8.1 v1.598)."""
    return {"budget_event": "refused", "budget": exc.budget.name, "mode": exc.budget.mode,
            "window": exc.window, "model": exc.model, "spent_usd": exc.spent_usd,
            "held_usd": exc.held_usd, "estimate_usd": exc.estimate_usd,
            "limit_usd": exc.budget.limit_usd, "unbounded": exc.unbounded}


def _warned(event: dict) -> dict:
    """A warn budget record's fields after ``tags`` (DESIGN 8.1 v1.598)."""
    return {"budget_event": "warn", "budget": event["budget"], "mode": "warn",
            "window": event.get("window"), "share": event["share"],
            "spent_usd": event["spent_usd"], "limit_usd": event["limit_usd"]}


def json_validator(*required_keys: str) -> Callable[[str], bool]:
    """Return a validator that accepts a JSON object containing every required key."""
    def validate(text: str) -> bool:
        try:
            value = json.loads(text)
        except (TypeError, ValueError):
            return False
        return isinstance(value, dict) and all(key in value for key in required_keys)
    return validate
