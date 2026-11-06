"""Inline or sub-agent: should a running agent do one call of a task itself or hand it off?

The parent is a model already running with its own context. Doing the work inline
costs a parent call over that context; delegating costs a brief, a call on the model
``Router.select`` picks, and reading the result back. Both paths are held to the
task's bar, and both flavors apply (DESIGN section 13).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from typing import Iterable, Optional

from .router import FLAVORS, NoModelClearsBar, RouteDecision, Router, _sizes
from .stats import Stats, wilson_lower_bound

INLINE = "inline"
DELEGATE = "delegate"

PARENT_EXCLUDED_FAMILY = "parent_excluded_family"
PARENT_NOT_INDEPENDENT = "parent_not_independent"
PARENT_CONTEXT_FULL = "parent_context_full"
PARENT_BELOW_BAR = "parent_below_bar"
DELEGATE_CHEAPER = "delegate_cheaper"
INLINE_CHEAPER = "inline_cheaper"
DELEGATE_BETTER = "delegate_better"
INLINE_AS_GOOD = "inline_as_good"
ONLY_PARENT_CLEARS = "only_parent_clears"
NONE_CLEAR = "none_clear"


@dataclass(frozen=True)
class DelegationDecision:
    """Inline or delegate for one piece of work, with the cost and quality of each path."""

    task: str
    flavor: str
    parent: str
    mode: str
    model: str
    reason: str
    below_bar: bool
    inline_allowed: bool
    inline_cost_usd: float
    delegate_cost_usd: Optional[float]
    parent_quality_lb: float
    delegate_quality_lb: Optional[float]
    route: Optional[RouteDecision]

    def to_dict(self) -> dict:
        """Return the decision as plain JSON-able types, keys in field order."""
        return {
            "task": self.task,
            "flavor": self.flavor,
            "parent": self.parent,
            "mode": self.mode,
            "model": self.model,
            "reason": self.reason,
            "below_bar": self.below_bar,
            "inline_allowed": self.inline_allowed,
            "inline_cost_usd": self.inline_cost_usd,
            "delegate_cost_usd": self.delegate_cost_usd,
            "parent_quality_lb": self.parent_quality_lb,
            "delegate_quality_lb": self.delegate_quality_lb,
            "route": None if self.route is None else self.route.to_dict(),
        }


def _count(name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be an integer >= 0, got {value!r}")
    return value


def _briefed_stats(stats: Stats, task_name: str, brief_tokens: int) -> Stats:
    """A copy of the task's stats with the brief added to every recorded call's input.

    Rounding up ``(I + B * n) / n`` gives the rounded-up ``I / n`` plus B exactly, so
    the delegate's ``select`` prices a measured model at its mean input plus B (13.3).
    """
    copy = Stats()
    for (name, model_id), (successes, trials) in stats.items():
        if name != task_name:
            continue
        i, o, n = stats.tokens(name, model_id)
        tokens = {}
        if n:
            tokens = {"input_tokens": i + brief_tokens * n, "output_tokens": o,
                      "token_trials": n}
        copy.add(name, model_id, successes, trials, **tokens)
    return copy


def decide_delegation(router: Router, task_name: str, parent_model: str,
                      flavor: str = "cost_effective", *, context_tokens: int,
                      brief_tokens: int, result_tokens: int, carry_turns: int = 0,
                      inline_separate_call: bool = True,
                      generator_model: Optional[str] = None,
                      exclude_models: Iterable[str] = ()) -> DelegationDecision:
    """The logic of :meth:`Router.decide_delegation` (DESIGN 13.1 to 13.5)."""
    if flavor not in FLAVORS:
        raise ValueError(f"unknown flavor {flavor!r}; expected one of {FLAVORS}")
    if task_name not in router.tasks:
        raise KeyError(f"unknown task: {task_name!r}")
    task = router.tasks[task_name]
    c = _count("context_tokens", context_tokens)
    b = _count("brief_tokens", brief_tokens)
    r = _count("result_tokens", result_tokens)
    t = _count("carry_turns", carry_turns)
    if not isinstance(inline_separate_call, bool):
        raise ValueError(f"inline_separate_call must be a bool, got {inline_separate_call!r}")
    parent = router.registry.get(parent_model)
    generator_family = None
    if generator_model is not None:
        generator_family = router.registry.get(generator_model).family
    excluded = tuple(exclude_models)
    s_in, s_out = task.expected_input_tokens, task.expected_output_tokens
    p_in, p_out = _sizes(router.stats, task, parent.id)

    # 13.2: both paths are charged for the same parent calls, each for what it adds,
    # with the work at the sizes of the model doing it (v1.33)
    if inline_separate_call:
        inline_cost = parent.cost(c + p_in, p_out) + (1 + t) * parent.cost(p_in + p_out, 0)
    else:
        inline_cost = parent.cost(p_in, p_out) + t * parent.cost(p_in + p_out, 0)

    # 13.4: the first rule that applies blocks inline
    block = None
    if parent.family in task.exclude_families:
        block = PARENT_EXCLUDED_FAMILY
    elif task.independent_of_generator and generator_model is not None and (
            parent.id == generator_model or parent.family == generator_family):
        block = PARENT_NOT_INDEPENDENT
    elif parent.context_window < c + s_in + s_out:
        block = PARENT_CONTEXT_FULL

    # 13.3: the delegate reads the brief as well as the work's input
    briefed = replace(task, expected_input_tokens=s_in + b)
    sub = Router(router.registry, {task.name: briefed},
                 _briefed_stats(router.stats, task.name, b), router.priors)
    route: Optional[RouteDecision] = None
    failed: Optional[NoModelClearsBar] = None
    try:
        route = sub.select(task.name, flavor=flavor, generator_model=generator_model,
                           exclude_models=excluded)
    except NoModelClearsBar as exc:
        failed = exc

    delegate_cost = delegate_lb = None
    if route is not None:
        delegate = router.registry.get(route.primary)
        d_in, d_out = _sizes(router.stats, task, delegate.id)
        delegate_cost = (parent.cost(0, b) + delegate.cost(b + d_in, d_out)
                         + (1 + t) * parent.cost(b + r, 0))
        delegate_lb = next(x.quality_lb for x in route.candidates
                           if x.model_id == route.primary)
    successes, trials = router.stats.get(task.name, parent.id)
    parent_lb = wilson_lower_bound(successes, trials, task.confidence)
    parent_clears = trials >= task.min_samples and parent_lb >= task.bar
    delegate_clears = route is not None and not route.below_bar

    def decision(mode: str, reason: str, below_bar: bool) -> DelegationDecision:
        return DelegationDecision(
            task=task.name, flavor=flavor, parent=parent.id, mode=mode,
            model=parent.id if mode == INLINE else route.primary, reason=reason,
            below_bar=below_bar, inline_allowed=block is None, inline_cost_usd=inline_cost,
            delegate_cost_usd=delegate_cost, parent_quality_lb=parent_lb,
            delegate_quality_lb=delegate_lb, route=route)

    def refuse() -> NoModelClearsBar:
        # only reached when the delegate's select raised, so ``failed`` is set (13.5)
        return NoModelClearsBar(f"no way to do task {task.name!r} inline or delegated",
                                failed.candidates)

    # 13.5: the first row that applies wins; floats are compared exactly
    if block is not None:
        if route is None:
            raise refuse()
        return decision(DELEGATE, block, route.below_bar)
    if delegate_clears and not parent_clears:
        return decision(DELEGATE, PARENT_BELOW_BAR, False)
    if delegate_clears and parent_clears:
        if flavor == "cost_effective":
            if delegate_cost < inline_cost:
                return decision(DELEGATE, DELEGATE_CHEAPER, False)
            if delegate_cost > inline_cost:
                return decision(INLINE, INLINE_CHEAPER, False)
        if delegate_lb > parent_lb:
            return decision(DELEGATE, DELEGATE_BETTER, False)
        return decision(INLINE, INLINE_AS_GOOD, False)
    if parent_clears:
        return decision(INLINE, ONLY_PARENT_CLEARS, False)
    if task.on_no_model == "refuse":
        raise refuse()
    if route is not None and route.basis == "measured" and (trials == 0 or delegate_lb > parent_lb):
        return decision(DELEGATE, NONE_CLEAR, True)
    if (flavor == "cost_effective" and route is not None and route.basis == "measured"
            and trials > 0 and delegate_lb == parent_lb and delegate_cost < inline_cost):
        return decision(DELEGATE, NONE_CLEAR, True)
    if trials > 0:
        return decision(INLINE, NONE_CLEAR, True)
    if route is not None:
        return decision(DELEGATE, NONE_CLEAR, True)
    raise refuse()
