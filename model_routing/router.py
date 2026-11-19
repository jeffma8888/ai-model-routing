"""Per-task routing: pick the cheapest (or best) model that clears the bar."""

from __future__ import annotations

from dataclasses import asdict, dataclass, replace
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .priors import Priors
from .registry import Registry
from .stats import Stats, wilson_lower_bound
from .tasks import Task, is_slice_name

EXCLUDED_MODEL = "excluded_model"
EXCLUDED_FAMILY = "excluded_family"
GENERATOR = "generator"
GENERATOR_FAMILY = "generator_family"
CONTEXT_TOO_SMALL = "context_too_small"
INSUFFICIENT_SAMPLES = "insufficient_samples"
BELOW_BAR = "below_bar"
PASSES = "passes"

FLAVORS = ("cost_effective", "cost_blind")

_ELIGIBLE_REASONS = (INSUFFICIENT_SAMPLES, BELOW_BAR, PASSES)


def _check_prompt_tokens(prompt_tokens) -> None:
    """A call's own size (DESIGN 5.2 v1.507): None, or an int of at least 0 that is not a bool."""
    if prompt_tokens is None:
        return
    if isinstance(prompt_tokens, bool) or not isinstance(prompt_tokens, int) or prompt_tokens < 0:
        raise ValueError(f"prompt_tokens must be an integer >= 0, got {prompt_tokens!r}")


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
    """One registry model as evaluated for a task, with the rule that decided it."""

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


@dataclass(frozen=True)
class RouteDecision:
    """The chosen primary model, ordered fallbacks, and every candidate considered."""

    task: str
    flavor: str
    primary: str
    fallbacks: Tuple[str, ...]
    below_bar: bool
    basis: str
    candidates: Tuple[Candidate, ...]
    below_bar_fallbacks: Tuple[str, ...] = ()
    slice: Optional[str] = None

    def to_dict(self) -> dict:
        """Return the decision as plain JSON-able types.

        ``below_bar_fallbacks`` is a key only when it is not empty (DESIGN 5.1).
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
        data.update(below_bar=self.below_bar, basis=self.basis,
                    candidates=[asdict(c) for c in self.candidates])
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
               slice: Optional[str] = None) -> RouteDecision:
        """Route ``task_name`` and return a :class:`RouteDecision`.

        ``prompt_tokens`` is the size of the one request being routed: when given, the
        context-window check reads it in place of the task's ``expected_input_tokens``,
        so the primary and every fallback can hold that request, while prices stay at the
        task's sizes (DESIGN 5.2 v1.507). ``slice`` names a slice of the task: the bar is
        then judged on the counts under the stats key ``<task>@<slice>`` alone, with the
        slice's ``bar``, ``min_samples`` and sizes (DESIGN 5.2 v1.511). Raises ``KeyError``
        for an unknown task or generator, ``ValueError`` for an unknown flavor, a
        ``prompt_tokens`` that is not an integer >= 0, a ``slice`` that is not a non-empty
        string without '@', or a sliced task whose name holds '@' or whose slice key is
        another task, and :class:`NoModelClearsBar` when nothing can be chosen under the
        task's ``on_no_model`` policy.
        """
        if flavor not in FLAVORS:
            raise ValueError(f"unknown flavor {flavor!r}; expected one of {FLAVORS}")
        _check_prompt_tokens(prompt_tokens)
        if slice is not None and not is_slice_name(slice):
            raise ValueError(f"slice must be a non-empty string without '@', got {slice!r}")
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
        excluded = set(exclude_models)
        generator_family = None
        if generator_model is not None:
            generator_family = self.registry.get(generator_model).family

        fit_input = task.expected_input_tokens if prompt_tokens is None else prompt_tokens
        candidates = tuple(self._candidate(task, model, flavor, excluded,
                                           generator_model, generator_family, fit_input)
                           for model in self.registry.models)

        passing = [c for c in candidates if c.passes]
        if passing:
            passing.sort(key=lambda c: (c.routing_cost, -c.quality_lb, c.model_id))
            under = []
            if task.fallback_below_bar:
                under = sorted((c for c in candidates
                                if c.eligible and not c.passes and c.trials > 0),
                               key=lambda c: (-c.quality_lb, c.routing_cost, c.model_id))
            return self._decision(task, flavor, passing + under, False, "measured", candidates,
                                  under=frozenset(c.model_id for c in under),
                                  name=base.name, slice_name=slice)

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
            for c in eligible:
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

    def _candidate(self, task: Task, model, flavor: str, excluded: set,
                   generator_model: Optional[str],
                   generator_family: Optional[str], fit_input: int) -> Candidate:
        successes, trials = self.stats.get(task.name, model.id)
        if model.id in excluded:
            reason = EXCLUDED_MODEL
        elif model.family in task.exclude_families:
            reason = EXCLUDED_FAMILY
        elif task.independent_of_generator and generator_model is not None \
                and model.id == generator_model:
            reason = GENERATOR
        elif task.independent_of_generator and generator_family is not None \
                and model.family == generator_family:
            reason = GENERATOR_FAMILY
        elif model.context_window < fit_input + task.expected_output_tokens:
            reason = CONTEXT_TOO_SMALL
        elif trials < task.min_samples:
            reason = INSUFFICIENT_SAMPLES
        elif wilson_lower_bound(successes, trials, task.confidence) < task.bar:
            reason = BELOW_BAR
        else:
            reason = PASSES
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
        )

    def _list_cost(self, task: Task, model) -> float:
        """A candidate's list-price cost of one call of the task at its 5.2 sizes."""
        return model.cost(*_sizes(self.stats, task, model.id))

    @staticmethod
    def _decision(task: Task, flavor: str, ordered: Sequence[Candidate], below_bar: bool,
                  basis: str, candidates: Tuple[Candidate, ...],
                  under: frozenset = frozenset(), name: Optional[str] = None,
                  slice_name: Optional[str] = None) -> RouteDecision:
        chosen: List[Candidate] = list(ordered)
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
        )
