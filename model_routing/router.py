"""Per-task routing: pick the cheapest (or best) model that clears the bar."""

from __future__ import annotations

import math
from fnmatch import fnmatchcase
from dataclasses import asdict, dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .priors import Priors
from .procedures import Procedure
from .registry import Registry, _tier_prices
from .stats import Stats, wilson_lower_bound
from .tasks import Cascade, Task, is_slice_name

EXCLUDED_MODEL = "excluded_model"
EXCLUDED_FAMILY = "excluded_family"
GENERATOR = "generator"
GENERATOR_FAMILY = "generator_family"
CONTEXT_TOO_SMALL = "context_too_small"
INSUFFICIENT_SAMPLES = "insufficient_samples"
BELOW_BAR = "below_bar"
PASSES = "passes"
CASCADE_UNKNOWN_MODEL = "cascade_unknown_model"
CHEAPER_PER_SUCCESS = "cheaper_per_success"  # a decision's reason, never a candidate's
PROCEDURE_UNKNOWN_MODEL = "procedure_unknown_model"
OUT_OF_SCOPE = "out_of_scope"
POLICY_EXCLUDED = "policy_excluded"  # DESIGN 5.1 v1.622, rules 5b to 5d
REGION_UNAVAILABLE = "region_unavailable"
ZDR_REQUIRED = "zdr_required"
TOO_SLOW = "too_slow"  # DESIGN 5.1 v1.628, rules 5e and 5f
LATENCY_UNKNOWN = "latency_unknown"

FLAVORS = ("cost_effective", "cost_blind")
_BREAKDOWN_KEYS = ("uncached_input_usd", "cached_read_usd", "cache_write_usd", "output_usd")

_ELIGIBLE_REASONS = (INSUFFICIENT_SAMPLES, BELOW_BAR, PASSES)


def _check_prompt_tokens(prompt_tokens) -> None:
    """A call's own size (DESIGN 5.2 v1.507): None, or an int of at least 0 that is not a bool."""
    if prompt_tokens is None:
        return
    if isinstance(prompt_tokens, bool) or not isinstance(prompt_tokens, int) or prompt_tokens < 0:
        raise ValueError(f"prompt_tokens must be an integer >= 0, got {prompt_tokens!r}")


def _check_pin(pin_route, allow_below_bar) -> None:
    """A call's pin keywords (DESIGN 5.2 v1.639), checked right after ``policy``."""
    if pin_route is not None and (not isinstance(pin_route, str) or not pin_route):
        raise ValueError(f"pin_route must be None or a non-empty string, got {pin_route!r}")
    if not isinstance(allow_below_bar, bool):
        raise ValueError(f"allow_below_bar must be a bool, got {allow_below_bar!r}")
    if allow_below_bar and pin_route is None:
        raise ValueError("allow_below_bar needs a pin_route")


def _in_scope(patterns: Tuple[str, ...], name: str, key: Optional[str]) -> bool:
    """Rule 5a (DESIGN 5.2 v1.586): on a sliced call a pattern with '@' reads the key, any other the name."""
    return any(fnmatchcase(key if key is not None and "@" in pattern else name, pattern)
               for pattern in patterns)


def _names(value, field_name: str) -> Optional[Tuple[str, ...]]:
    """A policy list (DESIGN 5.1 v1.622): None, or a list or tuple of non-empty strings, as a tuple."""
    if value is None:
        return None
    if not isinstance(value, (list, tuple)) or not all(isinstance(v, str) and v for v in value):
        raise ValueError(f"{field_name} must be None or a list or tuple of non-empty strings, got {value!r}")
    return tuple(value)


@dataclass(frozen=True)
class Policy:
    """The rules a tenant's calls keep whatever they cost (DESIGN 5.1 and 5.2 v1.622).

    ``allowed_routes`` and ``allowed_families`` are None (no limit) or the route IDs and families a
    call may reach; ``region`` is the region its calls must be served in, and ``require_zdr`` asks for
    zero data retention. A value the registry does not state fails closed. ``Policy()`` limits nothing.
    """

    allowed_routes: Optional[Tuple[str, ...]] = None
    allowed_families: Optional[Tuple[str, ...]] = None
    region: Optional[str] = None
    require_zdr: bool = False

    def __post_init__(self) -> None:
        object.__setattr__(self, "allowed_routes", _names(self.allowed_routes, "allowed_routes"))
        object.__setattr__(self, "allowed_families", _names(self.allowed_families, "allowed_families"))
        if self.region is not None and (not isinstance(self.region, str) or not self.region):
            raise ValueError(f"region must be None or a non-empty string, got {self.region!r}")
        if not isinstance(self.require_zdr, bool):
            raise ValueError(f"require_zdr must be a bool, got {self.require_zdr!r}")


def _policy_rule(policy: Optional[Policy], model) -> Optional[str]:
    """Rules 5b to 5d (DESIGN 5.2 v1.622) on a registry model, or None."""
    if policy is None:
        return None
    if policy.allowed_routes is not None and model.id not in policy.allowed_routes \
            and model.base_id not in policy.allowed_routes:
        return POLICY_EXCLUDED
    if policy.allowed_families is not None and model.family not in policy.allowed_families:
        return POLICY_EXCLUDED
    if policy.region is not None and policy.region not in model.regions:
        return REGION_UNAVAILABLE
    if policy.require_zdr and model.zero_data_retention is not True:
        return ZDR_REQUIRED
    return None


def _route_id_rule(policy: Optional[Policy], route_id: str) -> Optional[str]:
    """A cascade's or a procedure's own ID under ``allowed_routes`` (DESIGN 5.2 v1.622), or None."""
    if policy is not None and policy.allowed_routes is not None and route_id not in policy.allowed_routes:
        return POLICY_EXCLUDED
    return None


def _per_success(candidate: "Candidate") -> float:
    """Routing cost over the Wilson lower bound, infinite when it is 0 (DESIGN 5.3 v1.567)."""
    if candidate.quality_lb <= 0:
        return math.inf
    return candidate.routing_cost / candidate.quality_lb


def _sizes(stats: Stats, task: Task, model_id: str) -> Tuple[int, int]:
    """The input and output tokens a model is priced at on the task (DESIGN 5.2).

    Its rounded-up mean tokens per call when the stats hold token counts for it,
    else the task's expected tokens.
    """
    mean = stats.mean_tokens(task.name, model_id)
    if mean is None:
        return task.expected_input_tokens, task.expected_output_tokens
    return mean


def _breakdown(model, size_in: int, size_out: int, cached: int, write: int,
               per_item: bool = True) -> Tuple[float, float, float, float]:
    """The USD parts of a candidate's list cost, per item (DESIGN 5.1 v1.588).

    Uncached input, cached reads, cache writes and output, each at the call's tier prices with
    an unknown cache price read as the input price, so the parts' ``math.fsum`` is the
    ``list_cost`` that 5.3 orders by within a relative 1e-12. ``per_item`` False gives a whole
    call's parts, as a cascade's legs and a procedure's model call are priced (5.2 v1.591).
    """
    price_in, price_out = _tier_prices(model, size_in)
    read = price_in if model.price_cached_in is None else model.price_cached_in
    written = price_in if model.price_cache_write is None else model.price_cache_write
    per = 1_000_000 * (model.items_per_call if per_item else 1)
    return ((size_in - cached - write) * price_in / per, cached * read / per,
            write * written / per, size_out * price_out / per)


def _fit(counts: Tuple[int, int], room: int) -> Tuple[int, int]:
    """Cached reads and cache writes fitted inside a read of ``room`` tokens, the write first
    (DESIGN 5.2 v1.588), as a hand-up read or a procedure's expected input takes them (v1.591)."""
    cached, write = counts
    write = min(write, room)
    return min(cached, room - write), write


def _call_cost(model, size_in: int, size_out: int, counts: Optional[Tuple[int, int]]) -> float:
    """``model.cost`` given the counts only when there are any (DESIGN 5.2 v1.591), so a leg or a
    model without them is priced as before, the evaluator's calibration-priced models (12.3) too."""
    if counts is None:
        return model.cost(size_in, size_out)
    return model.cost(size_in, size_out, cached_input_tokens=counts[0],
                      cache_write_tokens=counts[1])


def _unknown_cache_prices(model, cached: int, write: int) -> Tuple[str, ...]:
    """The registry cache prices a route's own counts needed and the model leaves unknown (5.1)."""
    names = []
    if cached and model.price_cached_in is None:
        names.append("price_cached_in")
    if write and model.price_cache_write is None:
        names.append("price_cache_write")
    return tuple(names)


@dataclass(frozen=True)
class Candidate:
    """One registry model, cascade (DESIGN 7 v1.536) or procedure (5.2 v1.577) for a task.

    ``reason`` names the rule that decided it. ``pricing_basis`` is a registry model's own
    (``"list"`` or ``"self_hosted"``) and None for a cascade or a procedure (5.1 v1.584).
    ``cost_breakdown`` holds the four USD parts of ``list_cost`` when the route has measured
    cache counts, and ``cache_price_unknown`` the cache prices those counts needed and the model
    leaves unknown, so they were read at the call's input price (5.1 v1.588); a cascade's or a
    procedure's when a leg's model or the procedure's priced model has them (5.2 v1.591).
    ``p95_latency_ms`` is, under the task's ``max_p95_ms``, the route's time that rule 5e reads, None
    when it is unknown or the task sets no bar (5.1 and 5.2 v1.628).
    """

    model_id: str
    family: str
    successes: int
    trials: int
    quality_lb: float
    routing_cost: float
    list_cost: float
    eligible: bool
    passes: bool
    reason: str
    pricing_basis: Optional[str] = None
    cost_breakdown: Optional[Tuple[float, float, float, float]] = None
    cache_price_unknown: Tuple[str, ...] = ()
    p95_latency_ms: Optional[float] = None


@dataclass(frozen=True)
class RouteDecision:
    """The chosen primary model, ordered fallbacks, and every candidate considered.

    ``candidates`` holds one per registry model, in registry order, then, for a decision made
    with ``cascades=True``, one per cascade of the task, in task order (DESIGN 5.1 v1.536), and
    then one per procedure the call names, in its order (5.1 v1.577).
    """

    task: str
    flavor: str
    primary: str
    fallbacks: Tuple[str, ...]
    below_bar: bool
    basis: str
    candidates: Tuple[Candidate, ...]
    below_bar_fallbacks: Tuple[str, ...] = ()
    slice: Optional[str] = None
    failure_policy: str = "none"
    expected_cost_per_success_usd: Optional[float] = None
    pick_reason: Optional[str] = None
    max_p95_ms: Optional[float] = None

    def to_dict(self) -> dict:
        """Return the decision as plain JSON-able types.

        ``below_bar_fallbacks`` is a key only when it is not empty (DESIGN 5.1); the cost per
        success keys only when ``failure_policy`` is not ``"none"`` (v1.567); a candidate's
        ``pricing_basis`` only when it is ``"self_hosted"`` (v1.584), its ``cost_breakdown``
        only with measured cache counts and its ``cache_price_unknown`` only when that list is
        not empty (v1.588); ``max_p95_ms`` and each candidate's ``p95_latency_ms`` only when the
        task sets a latency bar (v1.628).
        """
        data = {"task": self.task}
        if self.slice is not None:
            data["slice"] = self.slice
        data.update({
            "flavor": self.flavor,
            "primary": self.primary,
            "fallbacks": list(self.fallbacks),
        })
        if self.below_bar_fallbacks:
            data["below_bar_fallbacks"] = list(self.below_bar_fallbacks)
        data.update(below_bar=self.below_bar, basis=self.basis)
        if self.failure_policy != "none":
            data["failure_policy"] = self.failure_policy
            data["expected_cost_per_success_usd"] = self.expected_cost_per_success_usd
            if self.pick_reason is not None:
                data["pick_reason"] = self.pick_reason
        timed = self.max_p95_ms is not None  # DESIGN 5.1 v1.628
        if timed:
            data["max_p95_ms"] = self.max_p95_ms
        data["candidates"] = [_candidate_dict(c, timed) for c in self.candidates]
        return data


def _candidate_dict(candidate: Candidate, timed: bool = False) -> dict:
    """A candidate's dict, its ``pricing_basis`` key only for a self-hosted model (5.1 v1.584).

    Its last two fields, the cache ones of v1.588, are keys only when they hold something: the
    breakdown as an object of the four USD parts, then the unknown cache prices as a list. Its time
    is its last key only under a latency bar (``timed``), a number or null (v1.628).
    """
    data = asdict(candidate)
    p95 = data.pop("p95_latency_ms")
    if data["pricing_basis"] != "self_hosted":
        del data["pricing_basis"]
    parts = data.pop("cost_breakdown")
    unknown = data.pop("cache_price_unknown")
    if parts is not None:
        data["cost_breakdown"] = dict(zip(_BREAKDOWN_KEYS, parts))
        if unknown:
            data["cache_price_unknown"] = list(unknown)
    if timed:
        data["p95_latency_ms"] = p95
    return data


class NoModelClearsBar(Exception):
    """No model can be routed to; ``.candidates`` explains why for each model."""

    def __init__(self, message: str, candidates: Tuple[Candidate, ...]):
        super().__init__(message)
        self.candidates = candidates


class Router:
    """Selects models for tasks from measured stats, with optional cold-start priors."""

    def __init__(self, registry: Registry, tasks: Dict[str, Task], stats: Stats,
                 priors: Optional[Priors] = None):
        self.registry = registry
        self.tasks = tasks
        self.stats = stats
        self.priors = priors

    def select(self, task_name: str, flavor: str = "cost_effective",
               generator_model: Optional[str] = None,
               exclude_models: Iterable[str] = (), *,
               prompt_tokens: Optional[int] = None,
               slice: Optional[str] = None, cascades: bool = False,
               procedures: Sequence[Procedure] = (),
               policy: Optional[Policy] = None,
               pin_route: Optional[str] = None,
               allow_below_bar: bool = False) -> RouteDecision:
        """Route ``task_name`` and return a :class:`RouteDecision`.

        ``prompt_tokens`` is the size of the one request being routed: when given, the
        context-window check reads it in place of the task's ``expected_input_tokens``,
        so the primary and every fallback can hold that request, while prices stay at the
        task's sizes (DESIGN 5.2 v1.507). ``slice`` names a slice of the task: the bar is
        then judged on the counts under the stats key ``<task>@<slice>`` alone, with the
        slice's ``bar``, ``min_samples`` and sizes (DESIGN 5.2 v1.511). With ``cascades``
        True each cascade of the task is a candidate too, after the registry models, judged
        on its own trials and priced at its cheap model's call plus its share of hand-ups to
        its strong model, never on a prior (DESIGN 7 v1.532 and v1.536). Each of
        ``procedures`` is a candidate after those, judged by rules 1 to 5 on its named model
        and by its own trials under its ``proc:`` ID, at its measured mean cost per trial,
        never on a prior (DESIGN 5.2 v1.577). A ``policy`` rules out, after rule 5a, each route
        that reaches a model outside its allowed routes or families, its region or its retention
        rule, and a cascade or procedure whose own ID ``allowed_routes`` leaves out (DESIGN 5.2
        v1.622). Under the task's ``max_p95_ms`` a route whose p95 on the call's key is above it is
        ``too_slow``, and with ``latency_unknown`` ``"deny"`` one whose time is unknown is
        ``latency_unknown`` (5.2 v1.628). A ``pin_route`` skips the ranking: every candidate is judged
        as without it and the pin is the only entry, ``basis`` ``"pinned"``; a pin that is not
        ``eligible`` raises :class:`NoModelClearsBar`, as does one that does not pass unless
        ``allow_below_bar`` is True, and a pin that is no candidate ``ValueError`` (5.2 v1.639).
        Raises ``KeyError``
        for an unknown task or generator, ``ValueError`` for an unknown flavor, a
        ``prompt_tokens`` that is not an integer >= 0, a ``slice`` that is not a non-empty
        string without '@', a sliced task whose name holds '@' or whose slice key is
        another task, a ``cascades`` that is not a bool, or, with ``cascades`` True, a
        registry ID equal to a cascade's ``id``, ``procedures`` that is not a list or tuple of
        ``Procedure``, two of them with one ``id`` or a registry ID equal to one's ``id``,
        a ``policy`` that is not None or a ``Policy``, and :class:`NoModelClearsBar` when nothing
        can be chosen under the task's ``on_no_model`` policy.
        """
        if flavor not in FLAVORS:
            raise ValueError(f"unknown flavor {flavor!r}; expected one of {FLAVORS}")
        _check_prompt_tokens(prompt_tokens)
        if slice is not None and not is_slice_name(slice):
            raise ValueError(f"slice must be a non-empty string without '@', got {slice!r}")
        if not isinstance(cascades, bool):
            raise ValueError(f"cascades must be a bool, got {cascades!r}")
        if not isinstance(procedures, (list, tuple)) \
                or not all(isinstance(proc, Procedure) for proc in procedures):
            raise ValueError("procedures must be a list or tuple of Procedure, "
                             f"got {type(procedures).__name__}")
        if policy is not None and not isinstance(policy, Policy):  # DESIGN 5.2 v1.622
            raise ValueError(f"policy must be None or a Policy, got {type(policy).__name__}")
        _check_pin(pin_route, allow_below_bar)  # DESIGN 5.2 v1.639
        if task_name not in self.tasks:
            raise KeyError(f"unknown task: {task_name!r}")
        base = self.tasks[task_name]
        task = base
        if slice is not None:
            key = f"{base.name}@{slice}"
            if "@" in base.name:
                raise ValueError(f"task {base.name!r} holds '@', so it cannot be sliced")
            if key in self.tasks:
                raise ValueError(f"slice key {key!r} is also a task of this router")
            task = replace(base, name=key, slices={}, **base.slices.get(slice, {}))
        routed = task.cascades if cascades else ()
        for cascade in routed:
            if cascade.id in self.registry:
                raise ValueError(f"registry model {cascade.id!r} has the id of a cascade "
                                 f"of task {base.name!r}")
        seen = set()
        for proc in procedures:  # DESIGN 5.2 v1.577: one stats key per route
            if proc.id in seen:
                raise ValueError(f"two procedures have the id {proc.id!r}")
            seen.add(proc.id)
            if proc.id in self.registry:
                raise ValueError(f"registry model {proc.id!r} has the id of a procedure")
        excluded = set(exclude_models)
        generator_base = generator_family = None
        if generator_model is not None:
            generator = self.registry.get(generator_model)
            generator_base, generator_family = generator.base_id, generator.family

        fit_input = task.expected_input_tokens if prompt_tokens is None else prompt_tokens
        names = (base.name, None if slice is None else task.name)  # DESIGN 5.2 v1.586
        candidates = tuple(self._candidate(task, model, flavor, excluded,
                                           generator_base, generator_family, fit_input, names,
                                           policy)
                           for model in self.registry.models)
        candidates += tuple(self._cascade_candidate(task, cascade, flavor, excluded,
                                                    generator_base, generator_family, fit_input,
                                                    names, policy)
                            for cascade in routed)
        candidates += tuple(self._procedure_candidate(task, proc, flavor, excluded,
                                                      generator_base, generator_family, fit_input,
                                                      names, policy)
                            for proc in procedures)

        if pin_route is not None:  # DESIGN 5.2 v1.639: no ranking, the hard checks kept
            return self._pinned(task, flavor, candidates, pin_route, allow_below_bar, base.name, slice)

        passing = [c for c in candidates if c.passes]
        if passing:
            passing.sort(key=lambda c: (c.routing_cost, -c.quality_lb, c.model_id))
            pick_reason = None
            if task.failure_policy == "retry_same":  # DESIGN 5.3 v1.567
                per_call_first = passing[0].model_id
                passing.sort(key=lambda c: (_per_success(c), -c.quality_lb, c.model_id))
                if passing[0].model_id != per_call_first:
                    pick_reason = CHEAPER_PER_SUCCESS
            under = []
            if task.fallback_below_bar:
                under = sorted((c for c in candidates
                                if c.eligible and not c.passes and c.trials > 0),
                               key=lambda c: (-c.quality_lb, c.routing_cost, c.model_id))
            return self._decision(task, flavor, passing + under, False, "measured", candidates,
                                  under=frozenset(c.model_id for c in under),
                                  name=base.name, slice_name=slice, pick_reason=pick_reason)

        where = f"task {base.name!r}" + ("" if slice is None else f" slice {slice!r}")
        if task.on_no_model == "refuse":
            raise NoModelClearsBar(
                f"no model clears the bar {task.bar} for {where}", candidates)

        eligible = [c for c in candidates if c.eligible]
        measured = sorted((c for c in eligible if c.trials > 0),
                          key=lambda c: (-c.quality_lb, c.routing_cost, c.model_id))
        if measured:
            return self._decision(task, flavor, measured, True, "measured", candidates,
                                  name=base.name, slice_name=slice)

        if self.priors is not None and task.prior_category is not None:
            scored = []
            no_prior = {cascade.id for cascade in routed} | seen
            for c in eligible:
                if c.model_id in no_prior:  # no cascade or procedure has one (7 v1.532, 5.2 v1.577)
                    continue
                score = self.priors.score(task.prior_category, c.model_id)
                if score is not None:
                    scored.append((score, c))
            scored.sort(key=lambda pair: (-pair[0], pair[1].routing_cost, pair[1].model_id))
            if scored:
                return self._decision(task, flavor, [c for _, c in scored], True, "prior",
                                      candidates, name=base.name, slice_name=slice)

        raise NoModelClearsBar(
            f"no eligible measured or prior-scored model for {where}", candidates)

    def decide_delegation(self, task_name: str, parent_model: str,
                          flavor: str = "cost_effective", *, context_tokens: int,
                          brief_tokens: int, result_tokens: int, carry_turns: int = 0,
                          work_calls: int = 1, inline_separate_call: bool = True,
                          cached_read_ratio: float = 1.0,
                          output_reread_share: float = 1.0,
                          brief_output_tokens: Optional[int] = None,
                          generator_model: Optional[str] = None,
                          exclude_models: Iterable[str] = (),
                          policy: Optional[Policy] = None):
        """Decide whether ``parent_model`` does the work inline or delegates it.

        The work is ``work_calls`` successive calls of the task, one by default.
        Returns a :class:`~model_routing.delegation.DelegationDecision`; the delegate
        is this router's ``select`` with the brief added to the task's input, and for
        ``work_calls`` > 1 its window checked against its last call and its cost taken
        over its K calls (DESIGN 13.3). ``cached_read_ratio`` prices the parent's
        reads of its context in the inline work calls at that fraction of its list
        input price, for a parent whose provider caches the prompt prefix; every other
        read and all output stay at list price (DESIGN 13.2). ``output_reread_share`` is
        the share of each work call's output that later calls re-read, for a model whose
        history drops its reasoning; it scales those re-reads on both paths and never a
        written output or a context check (DESIGN 13.1, 13.2). ``brief_output_tokens`` is
        what the call that writes the brief outputs, by default ``brief_tokens``; it prices
        that output alone, while every read of the brief keeps ``brief_tokens`` (DESIGN
        13.1). A ``policy`` runs the delegate's ``select`` under it and keeps a parent it
        rules out from working inline (DESIGN 13.3 and 13.4 v1.624). Raises
        ``KeyError`` for an unknown task, parent or generator, ``ValueError`` for an
        unknown flavor, an invalid token count (``brief_output_tokens`` included, unless
        None), ``work_calls`` below 1 or a
        ``cached_read_ratio`` or ``output_reread_share`` that is not a number from 0
        to 1, or a ``policy`` that is not None or a ``Policy``, and
        :class:`NoModelClearsBar` when neither path is allowed (DESIGN section 13).
        """
        from .delegation import decide_delegation
        return decide_delegation(self, task_name, parent_model, flavor,
                                 context_tokens=context_tokens, brief_tokens=brief_tokens,
                                 result_tokens=result_tokens, carry_turns=carry_turns,
                                 work_calls=work_calls,
                                 inline_separate_call=inline_separate_call,
                                 cached_read_ratio=cached_read_ratio,
                                 output_reread_share=output_reread_share,
                                 brief_output_tokens=brief_output_tokens,
                                 generator_model=generator_model,
                                 exclude_models=exclude_models, policy=policy)

    def _pinned(self, task: Task, flavor: str, candidates: Tuple[Candidate, ...], pin_route: str,
                allow_below_bar: bool, name: str, slice_name: Optional[str]) -> RouteDecision:
        """The decision of a pinned call (DESIGN 5.2 v1.639): the pin alone, or a refusal."""
        by_id = {c.model_id: c for c in candidates}
        if pin_route not in by_id:
            raise ValueError(f"pin_route {pin_route!r} is no route of this call: a registry model, "
                             f"a cascade of the task with cascades=True or one of procedures")
        pinned = by_id[pin_route]
        where = f"task {name!r}" + ("" if slice_name is None else f" slice {slice_name!r}")
        if not pinned.eligible:
            raise NoModelClearsBar(f"pinned route {pin_route!r} is {pinned.reason} for {where}; "
                                   f"a pin keeps rules 1 to 5f", candidates)
        if not pinned.passes and not allow_below_bar:
            raise NoModelClearsBar(f"pinned route {pin_route!r} is {pinned.reason} for {where}; "
                                   f"pass allow_below_bar=True to run it under the bar", candidates)
        return self._decision(task, flavor, [pinned], not pinned.passes, "pinned", candidates,
                              name=name, slice_name=slice_name)

    @staticmethod
    def _model_rule(task: Task, model, excluded: set, generator_base: Optional[str],
                    generator_family: Optional[str], fit_input: int,
                    names: Tuple[str, Optional[str]],
                    policy: Optional[Policy] = None) -> Optional[str]:
        """The first of rules 1 to 5d (DESIGN 5.2) that applies to ``model``, or None.

        Rules 1 and 3 read ``base_id`` too, so they cover a model's variants (v1.572). Rule 5a
        (v1.586) matches ``scope_tasks`` against ``names``, the task's name and a sliced call's key.
        Rules 5b to 5d are the ``policy``'s (v1.622).
        """
        if model.id in excluded or model.base_id in excluded:  # DESIGN 5.2 v1.572
            return EXCLUDED_MODEL
        if model.family in task.exclude_families:
            return EXCLUDED_FAMILY
        if task.independent_of_generator and generator_base is not None \
                and model.base_id == generator_base:
            return GENERATOR
        if task.independent_of_generator and generator_family is not None \
                and model.family == generator_family:
            return GENERATOR_FAMILY
        if model.context_window < fit_input + task.expected_output_tokens:
            return CONTEXT_TOO_SMALL
        if model.scope_tasks and not _in_scope(model.scope_tasks, *names):
            return OUT_OF_SCOPE
        return _policy_rule(policy, model)

    def _latency_rule(self, task: Task, route_id: str) -> Tuple[Optional[str], Optional[float]]:
        """Rules 5e and 5f (DESIGN 5.2 v1.628) on a route's own key: its reason or None, and its time.

        The time is the key's p95 once it holds at least ``min_samples`` times, else unknown (None),
        which ``latency_unknown`` ``"deny"`` rules out. Without a bar, (None, None).
        """
        if task.max_p95_ms is None:
            return None, None
        p95 = None
        if len(self.stats.latencies(task.name, route_id)) >= task.min_samples:
            p95 = self.stats.p95_latency_ms(task.name, route_id)
        if p95 is None:
            return (LATENCY_UNKNOWN if task.latency_unknown == "deny" else None), None
        return (TOO_SLOW if p95 > task.max_p95_ms else None), p95

    @staticmethod
    def _measured_rule(task: Task, successes: int, trials: int) -> str:
        """Rules 6 to 8 (DESIGN 5.2) on these counts."""
        if trials < task.min_samples:
            return INSUFFICIENT_SAMPLES
        if wilson_lower_bound(successes, trials, task.confidence) < task.bar:
            return BELOW_BAR
        return PASSES

    def _candidate(self, task: Task, model, flavor: str, excluded: set,
                   generator_base: Optional[str],
                   generator_family: Optional[str], fit_input: int,
                   names: Tuple[str, Optional[str]], policy: Optional[Policy] = None) -> Candidate:
        successes, trials = self.stats.get(task.name, model.id)
        slow, p95 = self._latency_rule(task, model.id)  # DESIGN 5.2 v1.628: after 5d, before 6
        reason = (self._model_rule(task, model, excluded, generator_base, generator_family,
                                   fit_input, names, policy)
                  or slow or self._measured_rule(task, successes, trials))
        list_cost = self._list_cost(task, model)
        counts = self._cache_counts(task, model)
        mean = self.stats.mean_tokens(task.name, model.id)
        return Candidate(
            model_id=model.id,
            family=model.family,
            successes=successes,
            trials=trials,
            quality_lb=wilson_lower_bound(successes, trials, task.confidence),
            routing_cost=list_cost if flavor == "cost_effective" else 0.0,
            list_cost=list_cost,
            eligible=reason in _ELIGIBLE_REASONS,
            passes=reason == PASSES,
            reason=reason,
            pricing_basis=model.pricing_basis,
            cost_breakdown=None if counts is None else _breakdown(model, *mean, *counts),
            cache_price_unknown=() if counts is None else _unknown_cache_prices(model, *counts),
            p95_latency_ms=p95,
        )

    def _cascade_candidate(self, task: Task, cascade: Cascade, flavor: str, excluded: set,
                           generator_base: Optional[str],
                           generator_family: Optional[str], fit_input: int,
                           names: Tuple[str, Optional[str]],
                           policy: Optional[Policy] = None) -> Candidate:
        """A cascade as one candidate (DESIGN 7 v1.532 and v1.536).

        ``cascade_unknown_model`` when the registry lacks either model; else rule 1 on its
        own ``id``, then rules 1 to 5 on the cheap model and then the strong one, then rules 6
        to 8 on its own counts. Its cost is the cheap model's call at its sizes plus ``p``,
        the share of its trials that escalated, times the strong model reading the input and
        the cheap model's output and writing that output again. Each leg is priced at its own
        model's measured cache counts, the strong model's fitted inside the hand-up read, never
        the cheap model's share, with the breakdown and unknown prices of both (5.2 v1.591).
        """
        successes, trials = self.stats.get(task.name, cascade.id)
        quality_lb = wilson_lower_bound(successes, trials, task.confidence)
        slow, p95 = self._latency_rule(task, cascade.id)  # its own key's times (5.2 v1.628)
        if cascade.cheap not in self.registry or cascade.strong not in self.registry:
            return Candidate(model_id=cascade.id, family="", successes=successes,
                             trials=trials, quality_lb=quality_lb, routing_cost=0.0,
                             list_cost=0.0, eligible=False, passes=False,
                             reason=CASCADE_UNKNOWN_MODEL, p95_latency_ms=p95)
        cheap = self.registry.get(cascade.cheap)
        strong = self.registry.get(cascade.strong)
        reason = EXCLUDED_MODEL if cascade.id in excluded else _route_id_rule(policy, cascade.id)
        for model in (cheap, strong):
            if reason is None:
                reason = self._model_rule(task, model, excluded, generator_base,
                                          generator_family, fit_input, names, policy)
        if reason is None:
            reason = slow or self._measured_rule(task, successes, trials)
        size_in, size_out = _sizes(self.stats, task, cheap.id)
        p = self.stats.escalations(task.name, cascade.id) / trials if trials else 0.0
        read = size_in + size_out
        low = self._cache_counts(task, cheap)  # inside size_in, its own mean, already
        high = self._cache_counts(task, strong)
        high = None if high is None else _fit(high, read)
        list_cost = (_call_cost(cheap, size_in, size_out, low)
                     + p * _call_cost(strong, read, size_out, high))
        breakdown, unknown = None, ()
        if low is not None or high is not None:  # DESIGN 5.2 v1.591
            low_counts = (0, 0) if low is None else low
            high_counts = (0, 0) if high is None else high
            parts = zip(_breakdown(cheap, size_in, size_out, *low_counts, per_item=False),
                        _breakdown(strong, read, size_out, *high_counts, per_item=False))
            breakdown = tuple(mine + p * theirs for mine, theirs in parts)
            needed = (set(_unknown_cache_prices(cheap, *low_counts))
                      | set(_unknown_cache_prices(strong, *high_counts)))
            unknown = tuple(n for n in ("price_cached_in", "price_cache_write") if n in needed)
        return Candidate(
            model_id=cascade.id,
            family=strong.family,
            successes=successes,
            trials=trials,
            quality_lb=quality_lb,
            routing_cost=list_cost if flavor == "cost_effective" else 0.0,
            list_cost=list_cost,
            eligible=reason in _ELIGIBLE_REASONS,
            passes=reason == PASSES,
            reason=reason,
            cost_breakdown=breakdown,
            cache_price_unknown=unknown,
            p95_latency_ms=p95,
        )

    def _procedure_candidate(self, task: Task, proc: Procedure, flavor: str, excluded: set,
                             generator_base: Optional[str],
                             generator_family: Optional[str], fit_input: int,
                             names: Tuple[str, Optional[str]],
                             policy: Optional[Policy] = None) -> Candidate:
        """A procedure as one candidate (DESIGN 5.2 v1.577).

        ``procedure_unknown_model`` when the registry lacks its named model; else rule 1 on its
        own ``id``, then rules 1 to 5 on its named model, if any, then rules 6 to 8 on its own
        counts. Its cost is its mean cost per trial once measured, before that one call of its
        model at the task's sizes, or 0.0 without a model. That one call is priced at its model's
        measured cache counts fitted inside the task's input, undivided, with their breakdown and
        unknown prices (5.2 v1.591).
        """
        successes, trials = self.stats.get(task.name, proc.id)
        quality_lb = wilson_lower_bound(successes, trials, task.confidence)
        slow, p95 = self._latency_rule(task, proc.id)  # its own key's times (5.2 v1.628)
        model = None
        if proc.model is not None:
            if proc.model not in self.registry:
                return Candidate(model_id=proc.id, family="", successes=successes,
                                 trials=trials, quality_lb=quality_lb, routing_cost=0.0,
                                 list_cost=0.0, eligible=False, passes=False,
                                 reason=PROCEDURE_UNKNOWN_MODEL, p95_latency_ms=p95)
            model = self.registry.get(proc.model)
        reason = EXCLUDED_MODEL if proc.id in excluded else _route_id_rule(policy, proc.id)
        if reason is None and model is not None:
            reason = self._model_rule(task, model, excluded, generator_base, generator_family,
                                      fit_input, names, policy)
        if reason is None:
            reason = slow or self._measured_rule(task, successes, trials)
        list_cost = self.stats.mean_cost(task.name, proc.id)
        breakdown, unknown = None, ()
        if list_cost is None and model is None:
            list_cost = 0.0
        elif list_cost is None:
            size_in, size_out = task.expected_input_tokens, task.expected_output_tokens
            counts = self._cache_counts(task, model)
            counts = None if counts is None else _fit(counts, size_in)  # DESIGN 5.2 v1.591
            list_cost = _call_cost(model, size_in, size_out, counts)
            if counts is not None:
                breakdown = _breakdown(model, size_in, size_out, *counts, per_item=False)
                unknown = _unknown_cache_prices(model, *counts)
        return Candidate(
            model_id=proc.id,
            family="" if model is None else model.family,
            successes=successes,
            trials=trials,
            quality_lb=quality_lb,
            routing_cost=list_cost if flavor == "cost_effective" else 0.0,
            list_cost=list_cost,
            eligible=reason in _ELIGIBLE_REASONS,
            passes=reason == PASSES,
            reason=reason,
            cost_breakdown=breakdown,
            cache_price_unknown=unknown,
            p95_latency_ms=p95,
        )

    def _cache_counts(self, task: Task, model) -> Optional[Tuple[int, int]]:
        """The measured cached reads and cache writes a route is priced at (DESIGN 5.2 v1.588).

        Each the rounded-down mean over the calls that reported it, 0 when none did, fitted
        inside the route's mean input with the write first, since a capped write would move its
        tokens to the input price and under-state a write premium. ``None`` when the stats hold
        no token totals, so no cache count either, or no cache count for the route: its price is
        then v1.587's. The delegation routers of 13.3 return ``None``. A cascade's legs and a
        procedure's model read them too (v1.591).
        """
        mean = self.stats.mean_tokens(task.name, model.id)
        if mean is None:
            return None
        cached, write = self.stats.mean_cache_tokens(task.name, model.id)
        if cached is None and write is None:
            return None
        write = min(0 if write is None else write, mean[0])
        return min(0 if cached is None else cached, mean[0] - write), write

    def _list_cost(self, task: Task, model) -> float:
        """A candidate's list-price cost at its 5.2 sizes, per item (DESIGN 5.2 v1.573).

        At its measured mean, one call, the cost is over the route's ``items_per_call``; at the
        task's expected sizes, one call of one item, it is that call's cost, undivided. A route
        with measured cache counts is priced at them through ``Model.cost`` (v1.588).
        """
        mean = self.stats.mean_tokens(task.name, model.id)
        if mean is None:
            return model.cost(task.expected_input_tokens, task.expected_output_tokens)
        counts = self._cache_counts(task, model)
        if counts is None:
            return model.cost(*mean) / model.items_per_call
        return model.cost(*mean, cached_input_tokens=counts[0],
                          cache_write_tokens=counts[1]) / model.items_per_call

    @staticmethod
    def _decision(task: Task, flavor: str, ordered: Sequence[Candidate], below_bar: bool,
                  basis: str, candidates: Tuple[Candidate, ...],
                  under: frozenset = frozenset(), name: Optional[str] = None,
                  slice_name: Optional[str] = None,
                  pick_reason: Optional[str] = None) -> RouteDecision:
        chosen: List[Candidate] = list(ordered)
        per_success = None  # DESIGN 5.1 v1.567: at list price, in either flavor
        if task.failure_policy != "none" and chosen[0].quality_lb > 0:
            per_success = chosen[0].list_cost / chosen[0].quality_lb
        fallbacks = tuple(c.model_id for c in chosen[1:1 + task.max_fallbacks])
        return RouteDecision(
            task=task.name if name is None else name,
            flavor=flavor,
            primary=chosen[0].model_id,
            fallbacks=fallbacks,
            below_bar=below_bar,
            basis=basis,
            candidates=candidates,
            below_bar_fallbacks=tuple(m for m in fallbacks if m in under),
            slice=slice_name,
            failure_policy=task.failure_policy,
            expected_cost_per_success_usd=per_success,
            pick_reason=pick_reason,
            max_p95_ms=task.max_p95_ms,
        )
