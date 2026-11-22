"""Per-task routing: pick the cheapest (or best) model that clears the bar."""

from __future__ import annotations

import math
from dataclasses import asdict, dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .priors import Priors
from .procedures import Procedure
from .registry import Registry
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

FLAVORS = ("cost_effective", "cost_blind")

_ELIGIBLE_REASONS = (INSUFFICIENT_SAMPLES, BELOW_BAR, PASSES)


def _check_prompt_tokens(prompt_tokens) -> None:
    """A call's own size (DESIGN 5.2 v1.507): None, or an int of at least 0 that is not a bool."""
    if prompt_tokens is None:
        return
    if isinstance(prompt_tokens, bool) or not isinstance(prompt_tokens, int) or prompt_tokens < 0:
        raise ValueError(f"prompt_tokens must be an integer >= 0, got {prompt_tokens!r}")


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


@dataclass(frozen=True)
class Candidate:
    """One registry model, cascade (DESIGN 7 v1.536) or procedure (5.2 v1.577) for a task.

    ``reason`` names the rule that decided it. ``pricing_basis`` is a registry model's own
    (``"list"`` or ``"self_hosted"``) and None for a cascade or a procedure (5.1 v1.584).
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

    def to_dict(self) -> dict:
        """Return the decision as plain JSON-able types.

        ``below_bar_fallbacks`` is a key only when it is not empty (DESIGN 5.1); the cost per
        success keys only when ``failure_policy`` is not ``"none"`` (v1.567); a candidate's
        ``pricing_basis`` only when it is ``"self_hosted"`` (v1.584).
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
        data["candidates"] = [_candidate_dict(c) for c in self.candidates]
        return data


def _candidate_dict(candidate: Candidate) -> dict:
    """A candidate's dict, its ``pricing_basis`` key only for a self-hosted model (5.1 v1.584)."""
    data = asdict(candidate)
    if data["pricing_basis"] != "self_hosted":
        del data["pricing_basis"]
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
               procedures: Sequence[Procedure] = ()) -> RouteDecision:
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
        never on a prior (DESIGN 5.2 v1.577). Raises ``KeyError``
        for an unknown task or generator, ``ValueError`` for an unknown flavor, a
        ``prompt_tokens`` that is not an integer >= 0, a ``slice`` that is not a non-empty
        string without '@', a sliced task whose name holds '@' or whose slice key is
        another task, a ``cascades`` that is not a bool, or, with ``cascades`` True, a
        registry ID equal to a cascade's ``id``, ``procedures`` that is not a list or tuple of
        ``Procedure``, two of them with one ``id`` or a registry ID equal to one's ``id``,
        and :class:`NoModelClearsBar` when nothing
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
        candidates = tuple(self._candidate(task, model, flavor, excluded,
                                           generator_base, generator_family, fit_input)
                           for model in self.registry.models)
        candidates += tuple(self._cascade_candidate(task, cascade, flavor, excluded,
                                                    generator_base, generator_family, fit_input)
                            for cascade in routed)
        candidates += tuple(self._procedure_candidate(task, proc, flavor, excluded,
                                                      generator_base, generator_family, fit_input)
                            for proc in procedures)

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
                          exclude_models: Iterable[str] = ()):
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
        13.1). Raises
        ``KeyError`` for an unknown task, parent or generator, ``ValueError`` for an
        unknown flavor, an invalid token count (``brief_output_tokens`` included, unless
        None), ``work_calls`` below 1 or a
        ``cached_read_ratio`` or ``output_reread_share`` that is not a number from 0
        to 1, and
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
                                 exclude_models=exclude_models)

    @staticmethod
    def _model_rule(task: Task, model, excluded: set, generator_base: Optional[str],
                    generator_family: Optional[str], fit_input: int) -> Optional[str]:
        """The first of rules 1 to 5 (DESIGN 5.2) that applies to ``model``, or None.

        Rules 1 and 3 read ``base_id`` too, so they cover a model's variants (v1.572).
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
        return None

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
                   generator_family: Optional[str], fit_input: int) -> Candidate:
        successes, trials = self.stats.get(task.name, model.id)
        reason = self._model_rule(task, model, excluded, generator_base, generator_family,
                                  fit_input) or self._measured_rule(task, successes, trials)
        list_cost = self._list_cost(task, model)
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
        )

    def _cascade_candidate(self, task: Task, cascade: Cascade, flavor: str, excluded: set,
                           generator_base: Optional[str],
                           generator_family: Optional[str], fit_input: int) -> Candidate:
        """A cascade as one candidate (DESIGN 7 v1.532 and v1.536).

        ``cascade_unknown_model`` when the registry lacks either model; else rule 1 on its
        own ``id``, then rules 1 to 5 on the cheap model and then the strong one, then rules 6
        to 8 on its own counts. Its cost is the cheap model's call at its sizes plus ``p``,
        the share of its trials that escalated, times the strong model reading the input and
        the cheap model's output and writing that output again.
        """
        successes, trials = self.stats.get(task.name, cascade.id)
        quality_lb = wilson_lower_bound(successes, trials, task.confidence)
        if cascade.cheap not in self.registry or cascade.strong not in self.registry:
            return Candidate(model_id=cascade.id, family="", successes=successes,
                             trials=trials, quality_lb=quality_lb, routing_cost=0.0,
                             list_cost=0.0, eligible=False, passes=False,
                             reason=CASCADE_UNKNOWN_MODEL)
        cheap = self.registry.get(cascade.cheap)
        strong = self.registry.get(cascade.strong)
        reason = EXCLUDED_MODEL if cascade.id in excluded else None
        for model in (cheap, strong):
            if reason is None:
                reason = self._model_rule(task, model, excluded, generator_base,
                                          generator_family, fit_input)
        if reason is None:
            reason = self._measured_rule(task, successes, trials)
        size_in, size_out = _sizes(self.stats, task, cheap.id)
        p = self.stats.escalations(task.name, cascade.id) / trials if trials else 0.0
        list_cost = cheap.cost(size_in, size_out) + p * strong.cost(size_in + size_out, size_out)
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
        )

    def _procedure_candidate(self, task: Task, proc: Procedure, flavor: str, excluded: set,
                             generator_base: Optional[str],
                             generator_family: Optional[str], fit_input: int) -> Candidate:
        """A procedure as one candidate (DESIGN 5.2 v1.577).

        ``procedure_unknown_model`` when the registry lacks its named model; else rule 1 on its
        own ``id``, then rules 1 to 5 on its named model, if any, then rules 6 to 8 on its own
        counts. Its cost is its mean cost per trial once measured, before that one call of its
        model at the task's sizes, or 0.0 without a model.
        """
        successes, trials = self.stats.get(task.name, proc.id)
        quality_lb = wilson_lower_bound(successes, trials, task.confidence)
        model = None
        if proc.model is not None:
            if proc.model not in self.registry:
                return Candidate(model_id=proc.id, family="", successes=successes,
                                 trials=trials, quality_lb=quality_lb, routing_cost=0.0,
                                 list_cost=0.0, eligible=False, passes=False,
                                 reason=PROCEDURE_UNKNOWN_MODEL)
            model = self.registry.get(proc.model)
        reason = EXCLUDED_MODEL if proc.id in excluded else None
        if reason is None and model is not None:
            reason = self._model_rule(task, model, excluded, generator_base, generator_family,
                                      fit_input)
        if reason is None:
            reason = self._measured_rule(task, successes, trials)
        list_cost = self.stats.mean_cost(task.name, proc.id)
        if list_cost is None:
            list_cost = 0.0 if model is None else model.cost(task.expected_input_tokens,
                                                             task.expected_output_tokens)
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
        )

    def _list_cost(self, task: Task, model) -> float:
        """A candidate's list-price cost at its 5.2 sizes, per item (DESIGN 5.2 v1.573).

        At its measured mean, one call, the cost is over the route's ``items_per_call``; at the
        task's expected sizes, one call of one item, it is that call's cost, undivided.
        """
        mean = self.stats.mean_tokens(task.name, model.id)
        if mean is None:
            return model.cost(task.expected_input_tokens, task.expected_output_tokens)
        return model.cost(*mean) / model.items_per_call

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
        )
