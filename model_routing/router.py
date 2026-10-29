"""Per-task routing: pick the cheapest (or best) model that clears the bar."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from typing import Dict, Iterable, List, Optional, Sequence, Tuple

from .priors import Priors
from .registry import Registry
from .stats import Stats, wilson_lower_bound
from .tasks import Task

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

    def to_dict(self) -> dict:
        """Return the decision as plain JSON-able types."""
        return {
            "task": self.task,
            "flavor": self.flavor,
            "primary": self.primary,
            "fallbacks": list(self.fallbacks),
            "below_bar": self.below_bar,
            "basis": self.basis,
            "candidates": [asdict(c) for c in self.candidates],
        }


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
               exclude_models: Iterable[str] = ()) -> RouteDecision:
        """Route ``task_name`` and return a :class:`RouteDecision`.

        Raises ``KeyError`` for an unknown task or generator, ``ValueError``
        for an unknown flavor, and :class:`NoModelClearsBar` when nothing can
        be chosen under the task's ``on_no_model`` policy.
        """
        if flavor not in FLAVORS:
            raise ValueError(f"unknown flavor {flavor!r}; expected one of {FLAVORS}")
        if task_name not in self.tasks:
            raise KeyError(f"unknown task: {task_name!r}")
        task = self.tasks[task_name]
        excluded = set(exclude_models)
        generator_family = None
        if generator_model is not None:
            generator_family = self.registry.get(generator_model).family

        candidates = tuple(self._candidate(task, model, flavor, excluded,
                                           generator_model, generator_family)
                           for model in self.registry.models)

        passing = [c for c in candidates if c.passes]
        if passing:
            passing.sort(key=lambda c: (c.routing_cost, -c.quality_lb, c.model_id))
            return self._decision(task, flavor, passing, False, "measured", candidates)

        if task.on_no_model == "refuse":
            raise NoModelClearsBar(
                f"no model clears the bar {task.bar} for task {task.name!r}", candidates)

        eligible = [c for c in candidates if c.eligible]
        measured = sorted((c for c in eligible if c.trials > 0),
                          key=lambda c: (-c.quality_lb, c.routing_cost, c.model_id))
        if measured:
            return self._decision(task, flavor, measured, True, "measured", candidates)

        if self.priors is not None and task.prior_category is not None:
            scored = []
            for c in eligible:
                score = self.priors.score(task.prior_category, c.model_id)
                if score is not None:
                    scored.append((score, c))
            scored.sort(key=lambda pair: (-pair[0], pair[1].routing_cost, pair[1].model_id))
            if scored:
                return self._decision(task, flavor, [c for _, c in scored], True, "prior",
                                      candidates)

        raise NoModelClearsBar(
            f"no eligible measured or prior-scored model for task {task.name!r}", candidates)

    def _candidate(self, task: Task, model, flavor: str, excluded: set,
                   generator_model: Optional[str],
                   generator_family: Optional[str]) -> Candidate:
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
        elif model.context_window < task.expected_input_tokens + task.expected_output_tokens:
            reason = CONTEXT_TOO_SMALL
        elif trials < task.min_samples:
            reason = INSUFFICIENT_SAMPLES
        elif wilson_lower_bound(successes, trials, task.confidence) < task.bar:
            reason = BELOW_BAR
        else:
            reason = PASSES
        list_cost = model.cost(task.expected_input_tokens, task.expected_output_tokens)
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

    @staticmethod
    def _decision(task: Task, flavor: str, ordered: Sequence[Candidate], below_bar: bool,
                  basis: str, candidates: Tuple[Candidate, ...]) -> RouteDecision:
        chosen: List[Candidate] = list(ordered)
        return RouteDecision(
            task=task.name,
            flavor=flavor,
            primary=chosen[0].model_id,
            fallbacks=tuple(c.model_id for c in chosen[1:1 + task.max_fallbacks]),
            below_bar=below_bar,
            basis=basis,
            candidates=candidates,
        )
