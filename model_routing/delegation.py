"""Inline or sub-agent: should a running agent do a piece of work itself or hand it off?

The work is one or more successive calls of a task. The parent is a model already
running with its own context. Doing the work inline costs parent calls over that
context; delegating costs a brief, calls on the model ``Router.select`` picks over the
brief alone, and reading the result back. Both paths are held to the task's bar, and
both flavors apply (DESIGN section 13).
"""

from __future__ import annotations

from dataclasses import dataclass, replace
from math import fsum
from typing import Iterable, List, Optional, Sequence, Tuple

from .registry import _tier_prices
from .router import FLAVORS, NoModelClearsBar, Policy, RouteDecision, Router, _call_cost, _policy_rule, _sizes
from .router import (CONSISTENCY_UNKNOWN, INCONSISTENT, LATENCY_UNKNOWN, POLICY_EXCLUDED, REGION_UNAVAILABLE,
                     TOO_SLOW, ZDR_REQUIRED)
from .stats import Stats, _is_cascade_key, _is_procedure_key, wilson_lower_bound
from .tasks import Task

INLINE = "inline"
DELEGATE = "delegate"

PARENT_EXCLUDED_FAMILY = "parent_excluded_family"
PARENT_NOT_INDEPENDENT = "parent_not_independent"
PARENT_CONTEXT_FULL = "parent_context_full"
PARENT_POLICY_EXCLUDED = "parent_policy_excluded"  # DESIGN 13.4 rule 4 (v1.624)
PARENT_REGION_UNAVAILABLE = "parent_region_unavailable"
PARENT_ZDR_REQUIRED = "parent_zdr_required"
PARENT_TOO_SLOW = "parent_too_slow"  # DESIGN 13.4 rule 5 (v1.631)
PARENT_LATENCY_UNKNOWN = "parent_latency_unknown"
PARENT_INCONSISTENT = "parent_inconsistent"  # DESIGN 13.4 rule 6 (v1.669)
PARENT_CONSISTENCY_UNKNOWN = "parent_consistency_unknown"
PARENT_BELOW_BAR = "parent_below_bar"
DELEGATE_CHEAPER = "delegate_cheaper"
INLINE_CHEAPER = "inline_cheaper"
DELEGATE_BETTER = "delegate_better"
INLINE_AS_GOOD = "inline_as_good"
ONLY_PARENT_CLEARS = "only_parent_clears"
NONE_CLEAR = "none_clear"
DEPTH_CAP = "depth_cap"  # DESIGN 13.5 v1.691

# 5.2 rules 5b to 5d on the parent, as its 13.4 rule 4 codes
_PARENT_POLICY_CODES = {POLICY_EXCLUDED: PARENT_POLICY_EXCLUDED, REGION_UNAVAILABLE: PARENT_REGION_UNAVAILABLE,
                        ZDR_REQUIRED: PARENT_ZDR_REQUIRED}
# 5.2 rules 5e and 5f on the parent's own key, as its 13.4 rule 5 codes
_PARENT_LATENCY_CODES = {TOO_SLOW: PARENT_TOO_SLOW, LATENCY_UNKNOWN: PARENT_LATENCY_UNKNOWN}
# 5.2 rules 5g and 5h on the parent's own key, as its 13.4 rule 6 codes
_PARENT_CONSISTENCY_CODES = {INCONSISTENT: PARENT_INCONSISTENT, CONSISTENCY_UNKNOWN: PARENT_CONSISTENCY_UNKNOWN}


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
    depth: Optional[int] = None  # DESIGN 13.6 v1.691
    inline_cache_counts: Optional[Tuple[int, int]] = None  # DESIGN 13.6 v1.706
    delegate_cache_counts: Optional[Tuple[int, int]] = None  # DESIGN 13.6 v1.707

    def to_dict(self) -> dict:
        """Return the decision as plain JSON-able types, keys in field order, ``depth``,
        ``inline_cache_counts`` and ``delegate_cache_counts`` only when set (DESIGN 13.6 v1.691,
        v1.706, v1.707)."""
        data = {
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
        if self.depth is not None:  # DESIGN 13.6 v1.691
            data["depth"] = self.depth
        if self.inline_cache_counts is not None:  # DESIGN 13.6 v1.706
            data["inline_cache_counts"] = list(self.inline_cache_counts)
        if self.delegate_cache_counts is not None:  # DESIGN 13.6 v1.707
            data["delegate_cache_counts"] = list(self.delegate_cache_counts)
        return data


def _count(name: str, value) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{name} must be an integer >= 0, got {value!r}")
    return value


def _call_costs(model, calls: int, context: int, charged: float, s_in: int,
                s_out: int, share: float = 1) -> List[float]:
    """Each of ``calls`` work calls priced at its own tier (13.2 v1.219).

    Call j reads ``context + j * s_in + (j - 1) * share * s_out``, which sets its tier, and pays
    that tier's prices on ``charged + j * s_in + (j - 1) * share * s_out`` input and ``s_out``
    output tokens; ``share`` is the re-read share sigma (v1.404).
    """
    return _listed_call_costs(model, context, charged, [s_in] * calls, [s_out] * calls, share)


def _listed_call_costs(model, context: int, charged: float, ins: Sequence[int],
                       outs: Sequence[int], share: float = 1) -> List[float]:
    """Work calls of their own sizes, each priced at its own tier (13.2 v1.219, 13.9 v1.222).

    Call j reads ``context`` plus ``ins[:j + 1]`` and ``share`` times each of ``outs[:j]``,
    which sets its tier, and pays that tier's prices on ``charged`` plus those tokens and on
    ``outs[j]`` output tokens. The tokens added so far are a running sum, of integers with the
    int share 1 that 13.9 passes, so with equal sizes it is the integer
    ``j * s_in + (j - 1) * s_out`` of ``_call_costs`` and each cost the same float; a float
    share (v1.404) adds ``share * s_out``, the same value at 1.0.
    """
    costs = []
    added = 0
    for s_in, s_out in zip(ins, outs):
        added += s_in
        price_in, price_out = _tier_prices(model, context + added)
        costs.append(((charged + added) * price_in + s_out * price_out) / 1_000_000)
        added += share * s_out
    return costs


def _work_cost(model, k: int, base_reads: float, s_in: int, s_out: int, context: int,
               charged: float, share: float = 1) -> float:
    """List cost of K work calls (13.2).

    Call j reads the path's base context, the j inputs and ``share`` times each of the
    j - 1 outputs so far (v1.404), and writes ``s_out``. On a model without tiers the K
    calls are one ``Model.base_cost`` of their totals, ``base_reads + w_in * s_in +
    w_out * share * s_out`` read and ``K * s_out`` written, with w_in = K(K + 1) / 2 and
    w_out = K(K - 1) / 2 (v1.38); ``base_reads`` is the base context times the calls charged
    for it. On a model with tiers they are the ``math.fsum`` of the calls, each at its own
    tier, over base ``context`` of which ``charged`` is paid (v1.219).
    """
    if model.price_tiers:
        return fsum(_call_costs(model, k, context, charged, s_in, s_out, share))
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    return model.base_cost(base_reads + w_in * s_in + w_out * share * s_out, k * s_out)


def _counted_work_cost(model, k: int, base_reads: float, s_in: int, s_out: int, share: float,
                       counts: Tuple[int, int]) -> float:
    """K inline work calls on a parent without tiers at its measured cache counts (13.2 v1.706).

    ``_work_cost``'s totals, with each call's ``counts`` (its cached reads and writes per call,
    fitted inside ``s_in``) held in its input: one ``Model.cost`` with K times each count.
    """
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    return model.cost(base_reads + w_in * s_in + w_out * share * s_out, k * s_out,
                      cached_input_tokens=k * counts[0], cache_write_tokens=k * counts[1])


def _own_counts(router: Router, task: Task, model) -> Optional[Tuple[int, int]]:
    """A model's measured cache counts on the task, as ``router.stats`` holds them (13.2 v1.706 and
    v1.707): ``Router._cache_counts``, fitted inside its mean input, or None on a model with tiers."""
    return None if model.price_tiers else router._cache_counts(task, model)


def _delegate_work_cost(model, k: int, b: int, d_in: int, d_out: int, share: float,
                        counts: Optional[Tuple[int, int]]) -> float:
    """The delegate's K work calls over the brief (13.2 v1.38), at its measured counts when it has
    any (v1.707), the brief new input: the work term of ``delegate_cost_usd`` and its ``select``."""
    if counts is None:
        return _work_cost(model, k, k * b, d_in, d_out, b, b, share)
    return _counted_work_cost(model, k, k * b, d_in, d_out, share, counts)


def _shared(parent, c: int, rho: float, added_in: int, added_out: int = 0) -> float:
    """What a parent call over C is charged for the tokens a path adds to it (13.2).

    Without tiers ``Model.base_cost`` of the additions (v1.212); with tiers the additions at
    the tier of the call's whole read, C plus ``added_in``, and the dearer re-read of C, at
    rho, when they take the call over a threshold that C alone is not over (v1.219).
    """
    if not parent.price_tiers:
        return parent.base_cost(added_in, added_out)
    price_in, price_out = _tier_prices(parent, c + added_in)
    c_price_in, _ = _tier_prices(parent, c)
    return (added_in * price_in + c * rho * (price_in - c_price_in)
            + added_out * price_out) / 1_000_000


class _PerCallRouter(Router):
    """The delegate's ``select`` for one work call: each candidate priced per call at its 5.2
    sizes, whatever its ``items_per_call`` (13.3 v1.573), as ``delegate_cost_usd`` prices it, at
    its measured counts on ``router``'s stats when it has any (13.3 v1.707)."""

    def __init__(self, router: Router, task: Task, briefed: Task, stats: Stats):
        super().__init__(router.registry, {task.name: briefed}, stats, router.priors)
        self._router = router
        self._task = task

    def _list_cost(self, task: Task, model) -> float:
        return _call_cost(model, *_sizes(self.stats, task, model.id),
                          _own_counts(self._router, self._task, model))

    def _pair_cost(self, task: Task, root, leaf, sides) -> float:
        """A pair's sides read no measured cache count (13.3 v1.707, row DEL1k)."""
        if sides is None:
            return (root.cost(*_sizes(self.stats, task, root.id))
                    + leaf.cost(*_sizes(self.stats, task, leaf.id)))
        return super()._pair_cost(task, root, leaf, sides)

    @staticmethod
    def _side_cost(model, tokens) -> float:
        """A pair's side per call too, whatever its ``items_per_call`` (13.2 v1.684)."""
        return model.cost(*tokens)

    def _cache_counts(self, task: Task, model) -> None:
        """No measured cache count: 13.2's costs are v1.587's (5.2 v1.588)."""
        return None


class _WorkCallsRouter(Router):
    """The delegate's ``select`` for K > 1 work calls on the brief (13.3, v1.38).

    Its one task is a copy whose expected input is the delegate's last call,
    ``B + K * S_in + (K - 1) * S_out``, so 5.2 rule 5 checks that call; each candidate
    is priced at its K calls at its own 5.2 sizes on the original task.
    """

    def __init__(self, router: Router, task: Task, brief_tokens: int, work_calls: int,
                 share: float = 1):
        # rule 5 checks the last call with every earlier output whole, whatever the share
        last_call = replace(task, expected_input_tokens=brief_tokens
                            + work_calls * task.expected_input_tokens
                            + (work_calls - 1) * task.expected_output_tokens)
        super().__init__(router.registry, {task.name: last_call}, router.stats, router.priors)
        self._router = router
        self._task = task
        self._brief_tokens = brief_tokens
        self._work_calls = work_calls
        self._share = share

    def _list_cost(self, task: Task, model) -> float:
        # ``task`` is the last-call copy, whose expected input is only for rule 5; a model
        # without token counts is priced at the original task's expected sizes, and one with
        # measured cache counts on it at them (13.3 v1.707)
        return self._calls_cost(model, _own_counts(self._router, self._task, model))

    def _calls_cost(self, model, counts: Optional[Tuple[int, int]]) -> float:
        d_in, d_out = _sizes(self.stats, self._task, model.id)
        return _delegate_work_cost(model, self._work_calls, self._brief_tokens, d_in, d_out,
                                   self._share, counts)

    def _pair_cost(self, task: Task, root, leaf, sides) -> float:
        """A pair's K calls, the root's plus the leaf's, each side a history of its own (13.2 v1.686).

        With no side tokens each side's K calls are ``_list_cost``'s, at its 5.2 sizes over the
        brief; with them each side is at its mean side tokens on ``router.stats``, the brief the
        root's base context alone. Each side per call, whatever its ``items_per_call``.
        """
        if sides is None:  # ``task`` is the last-call copy; a side reads no cache count (13.3 v1.707)
            return self._calls_cost(root, None) + self._calls_cost(leaf, None)
        k, b, share = self._work_calls, self._brief_tokens, self._share
        (root_in, root_out), (leaf_in, leaf_out) = sides
        return (_work_cost(root, k, k * b, root_in, root_out, b, b, share)
                + _work_cost(leaf, k, 0, leaf_in, leaf_out, 0, 0, share))

    def _cache_counts(self, task: Task, model) -> None:
        """No measured cache count: 13.2's costs are v1.587's (5.2 v1.588)."""
        return None


def _briefed_stats(stats: Stats, task_name: str, brief_tokens: int) -> Stats:
    """A copy of the task's stats with the brief added to every recorded call's input.

    Rounding up ``(I + B * n) / n`` gives the rounded-up ``I / n`` plus B exactly, so
    the delegate's ``select`` prices a measured model at its mean input plus B (13.3).
    With no brief or no token totals on the task, ``stats`` itself is returned, as v1.32
    passed it. A cascade key keeps its escalation count and holds no token totals (DESIGN 7
    v1.536); a procedure key keeps its summed cost and holds none either (13.3 v1.627). Every key
    keeps its times, so a latency bar reads in the delegate what it reads in the router (v1.628),
    its label sources (v1.663, review iter-518 nit 3) and its rerun counts, so a self-consistency
    minimum reads in the delegate what it reads in the router (v1.668). A pair key keeps its side
    tokens with B added to the root's input over its side trials, the side that reads the brief, and
    a side token on the task builds the copy even with no token totals (v1.684).
    """
    rows = [(key, counts) for key, counts in stats.items() if key[0] == task_name]
    if brief_tokens == 0 or not any(stats.tokens(*key)[2] or stats.side_tokens(*key)[4]
                                    for key, _ in rows):
        return stats
    copy = Stats()
    for (name, model_id), (successes, trials) in rows:
        i, o, n = stats.tokens(name, model_id)
        tokens = {}
        if n:
            tokens = {"input_tokens": i + brief_tokens * n, "output_tokens": o,
                      "token_trials": n}
        if _is_cascade_key(model_id):
            tokens["escalated"] = stats.escalations(name, model_id)
        elif _is_procedure_key(model_id):  # 13.3 v1.627, review iter-478 should-fix 3
            tokens["cost_usd"] = stats.cost(name, model_id)
        times = stats.latencies(name, model_id)  # 13.3 v1.628, review iter-478 should-fix 3
        if times:
            tokens["latencies_ms"] = list(times)
        sources = stats.label_sources(name, model_id)  # 13.3 v1.663, review iter-518 nit 3
        if sources:
            tokens["label_sources"] = sources
        items, alike = stats.consistency(name, model_id)  # 13.3 v1.668
        if items:
            tokens.update(rerun_items=items, consistent_items=alike)
        ri, ro, li, lo, sides = stats.side_tokens(name, model_id)  # 13.3 v1.684
        if sides:
            tokens.update(root_input_tokens=ri + brief_tokens * sides, root_output_tokens=ro,
                          leaf_input_tokens=li, leaf_output_tokens=lo, side_trials=sides)
        copy.add(name, model_id, successes, trials, **tokens)
    return copy


def decide_delegation(router: Router, task_name: str, parent_model: str,
                      flavor: str = "cost_effective", *, context_tokens: int,
                      brief_tokens: int, result_tokens: int, carry_turns: int = 0,
                      work_calls: int = 1, inline_separate_call: bool = True,
                      cached_read_ratio: float = 1.0,
                      output_reread_share: float = 1.0,
                      brief_output_tokens: Optional[int] = None,
                      generator_model: Optional[str] = None,
                      exclude_models: Iterable[str] = (),
                      policy: Optional[Policy] = None,
                      delegate_roots: Optional[Sequence[str]] = None,
                      delegate_leaves: Optional[Sequence[str]] = None,
                      depth: Optional[int] = None) -> DelegationDecision:
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
    if isinstance(work_calls, bool) or not isinstance(work_calls, int) or work_calls < 1:
        raise ValueError(f"work_calls must be an integer >= 1, got {work_calls!r}")
    k = work_calls
    if not isinstance(inline_separate_call, bool):
        raise ValueError(f"inline_separate_call must be a bool, got {inline_separate_call!r}")
    rho = cached_read_ratio
    if isinstance(rho, bool) or not isinstance(rho, (int, float)) or not 0 <= rho <= 1:
        raise ValueError(f"cached_read_ratio must be a number from 0 to 1, got {rho!r}")
    sigma = output_reread_share
    if isinstance(sigma, bool) or not isinstance(sigma, (int, float)) or not 0 <= sigma <= 1:
        raise ValueError(f"output_reread_share must be a number from 0 to 1, got {sigma!r}")
    # 13.1 v1.405: what the decision turn writes for the brief, B unless stated
    w = b if brief_output_tokens is None else _count("brief_output_tokens", brief_output_tokens)
    if policy is not None and not isinstance(policy, Policy):  # DESIGN 13.1 v1.624
        raise ValueError(f"policy must be None or a Policy, got {type(policy).__name__}")
    pair = delegate_roots is not None
    if pair != (delegate_leaves is not None):  # DESIGN 13.1 v1.684
        raise ValueError("delegate_roots and delegate_leaves go together: give both or neither")
    if depth is not None:  # DESIGN 13.1 v1.691
        _count("depth", depth)
    parent = router.registry.get(parent_model)
    generator_family = None
    if generator_model is not None:
        generator_family = router.registry.get(generator_model).family
    excluded = tuple(exclude_models)
    s_in, s_out = task.expected_input_tokens, task.expected_output_tokens
    p_in, p_out = _sizes(router.stats, task, parent.id)

    # 13.2: both paths are charged for the same parent calls, each for what it adds,
    # with the work at the sizes of the model doing it (v1.33) and K calls long (v1.38);
    # folded work takes only the last call into the next one, which re-reads C anyway;
    # the work calls' reads of C are priced at rho times the list input price (v1.41);
    # a tiered model pays each call at its own tier (v1.219); every re-read of an
    # output is sigma of it, never the output written or a context check (v1.404)
    # v1.706: on a parent without tiers, its measured cache counts on the task sit in each work
    # call's own input; rho still prices C alone
    counts = _own_counts(router, task, parent)
    if counts is not None and inline_separate_call:
        inline_cost = (_counted_work_cost(parent, k, k * c * rho, p_in, p_out, sigma, counts)
                       + (1 + t) * _shared(parent, c, rho, k * (p_in + sigma * p_out)))
    elif counts is not None:
        inline_cost = (_counted_work_cost(parent, k, (k - 1) * c * rho, p_in, p_out, sigma, counts)
                       + t * parent.base_cost(k * (p_in + sigma * p_out), 0))
    elif inline_separate_call:
        inline_cost = (_work_cost(parent, k, k * c * rho, p_in, p_out, c, c * rho, sigma)
                       + (1 + t) * _shared(parent, c, rho, k * (p_in + sigma * p_out)))
    elif parent.price_tiers:
        # the K-th work call is the parent's next call, a shared call (v1.219)
        inline_cost = (fsum(_call_costs(parent, k - 1, c, c * rho, p_in, p_out, sigma)
                            + [_shared(parent, c, rho, k * p_in + (k - 1) * sigma * p_out,
                                       p_out)])
                       + t * _shared(parent, c, rho, k * (p_in + sigma * p_out)))
    else:
        inline_cost = (_work_cost(parent, k, (k - 1) * c * rho, p_in, p_out, c, c * rho, sigma)
                       + t * parent.base_cost(k * (p_in + sigma * p_out), 0))

    # 13.4: the first rule that applies blocks inline; rule 4 is 5.2 rules 5b to 5d on the parent (v1.624),
    # rule 5 is 5e and 5f on the parent's time on the task, read as a route's (v1.631), and rule 6 is 5g and
    # 5h on the parent's share of rerun items graded alike on the task, read as a route's (v1.669)
    parent_rule = _policy_rule(policy, parent)
    block = None
    if parent.family in task.exclude_families:
        block = PARENT_EXCLUDED_FAMILY
    elif task.independent_of_generator and generator_model is not None and (
            parent.id == generator_model or parent.family == generator_family):
        block = PARENT_NOT_INDEPENDENT
    elif parent.context_window < c + k * (s_in + s_out):
        block = PARENT_CONTEXT_FULL
    elif parent_rule is not None:
        block = _PARENT_POLICY_CODES[parent_rule]
    elif (latency_rule := router._latency_rule(task, parent.id)[0]) is not None:
        block = _PARENT_LATENCY_CODES[latency_rule]
    elif (consistency_rule := router._consistency_rule(task, parent.id)) is not None:
        block = _PARENT_CONSISTENCY_CODES[consistency_rule]

    # 13.3: the delegate reads the brief as well as the work's input; with K = 1 this
    # is the v1.34 select, and K > 1 checks the last call and prices the K calls, a pair's
    # side by side (v1.686)
    if k == 1:
        briefed = replace(task, expected_input_tokens=s_in + b)
        sub = _PerCallRouter(router, task, briefed, _briefed_stats(router.stats, task.name, b))
    else:
        sub = _WorkCallsRouter(router, task, b, k, sigma)
    route: Optional[RouteDecision] = None
    failed: Optional[NoModelClearsBar] = None
    try:
        if pair:  # 13.3 v1.684: a delegating harness's pair on the briefed task
            route = sub.select_pair(task.name, delegate_roots, delegate_leaves, flavor,
                                    generator_model=generator_model, exclude_models=excluded,
                                    policy=policy)
        else:
            route = sub.select(task.name, flavor=flavor, generator_model=generator_model,
                               exclude_models=excluded, policy=policy)
    except NoModelClearsBar as exc:
        failed = exc

    delegate_cost = delegate_lb = delegate_counts = None
    if route is not None and pair:  # 13.2 v1.684, v1.686: the pair's list cost stands for D's calls
        pair_cost = next(x.list_cost for x in route.candidates if x.model_id == route.primary)
        delegate_cost = (_shared(parent, c, rho, 0, w) + pair_cost
                         + (1 + t) * _shared(parent, c, rho, b + r))
        delegate_lb = next(x.quality_lb for x in route.candidates
                           if x.model_id == route.primary)
    elif route is not None:
        delegate = router.registry.get(route.primary)
        d_in, d_out = _sizes(router.stats, task, delegate.id)
        delegate_counts = _own_counts(router, task, delegate)  # 13.2 v1.707
        delegate_cost = (_shared(parent, c, rho, 0, w)
                         + _delegate_work_cost(delegate, k, b, d_in, d_out, sigma, delegate_counts)
                         + (1 + t) * _shared(parent, c, rho, b + r))
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
            delegate_quality_lb=delegate_lb, route=route, depth=depth, inline_cache_counts=counts,
            delegate_cache_counts=delegate_counts)

    def refuse() -> NoModelClearsBar:
        # only reached when the delegate's select raised, so ``failed`` is set (13.5)
        return NoModelClearsBar(f"no way to do task {task.name!r} inline or delegated",
                                failed.candidates)

    # 13.5 v1.691: at or past an enabled cap no hand-off is advised; inline when the parent may and clears
    cap = task.max_delegation_depth
    if cap is not None and (depth or 0) >= cap:
        if block is None and parent_clears:
            return decision(INLINE, DEPTH_CAP, False)
        raise NoModelClearsBar(f"no way to do task {task.name!r} ({DEPTH_CAP}): depth {depth or 0} is at or past "
                               f"the task's max_delegation_depth {cap}, and the parent may not do it inline "
                               f"at the bar", route.candidates if route is not None else failed.candidates)

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
