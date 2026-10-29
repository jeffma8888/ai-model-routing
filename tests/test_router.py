"""Selection rules, precedence, costs, quality, and fallback ordering."""

import json
from dataclasses import FrozenInstanceError

import pytest
from model_routing import (
    Registry, Router, Stats, Priors, NoModelClearsBar, wilson_lower_bound,
)
from model_routing import router as router_module


@pytest.fixture
def rule_selection(model_factory, task_factory):
    """Inspect the target even if every model is refused."""
    def select(*, task_overrides=None, trials=100, successes=100,
               context_window=8000, generator=None, exclude=()):
        models = [model_factory("fiction/target", "target-family", context_window=context_window),
                  model_factory("fiction/sibling", "target-family"),
                  model_factory("fiction/other", "other-family")]
        registry = Registry(models)
        task = task_factory(**(task_overrides or {}))
        stats = Stats()
        stats.add("judge", "fiction/target", successes, trials)
        router = Router(registry, {"judge": task}, stats)
        try:
            candidates = router.select("judge", generator_model=generator,
                                       exclude_models=exclude).candidates
        except NoModelClearsBar as exc:
            candidates = exc.candidates
        return next(c for c in candidates if c.model_id == "fiction/target")
    return select


@pytest.mark.parametrize("name,value", [
    ("EXCLUDED_MODEL", "excluded_model"), ("EXCLUDED_FAMILY", "excluded_family"),
    ("GENERATOR", "generator"), ("GENERATOR_FAMILY", "generator_family"),
    ("CONTEXT_TOO_SMALL", "context_too_small"),
    ("INSUFFICIENT_SAMPLES", "insufficient_samples"),
    ("BELOW_BAR", "below_bar"), ("PASSES", "passes"),
])
def test_reason_constants_have_exact_pinned_values(name, value):
    assert getattr(router_module, name) == value


def test_excluded_model_is_first_even_with_family_generator_context_and_sample_failures(rule_selection):
    candidate = rule_selection(
        task_overrides={"exclude_families": ("target-family",)},
        trials=0, successes=0, context_window=1,
        generator="fiction/target", exclude=("fiction/target",))
    assert (candidate.reason, candidate.eligible, candidate.passes) == ("excluded_model", False, False)


def test_excluded_family_is_first_before_generator_context_and_samples(rule_selection):
    candidate = rule_selection(task_overrides={"exclude_families": ("target-family",)},
                               generator="fiction/target", context_window=1,
                               trials=0, successes=0)
    assert (candidate.reason, candidate.eligible, candidate.passes) == ("excluded_family", False, False)


def test_generator_id_is_first_before_generator_family_context_and_samples(rule_selection):
    candidate = rule_selection(generator="fiction/target", context_window=1,
                               trials=0, successes=0)
    assert (candidate.reason, candidate.eligible, candidate.passes) == ("generator", False, False)


def test_generator_family_is_first_before_context_and_samples(rule_selection):
    candidate = rule_selection(generator="fiction/sibling", context_window=1,
                               trials=0, successes=0)
    assert (candidate.reason, candidate.eligible, candidate.passes) == ("generator_family", False, False)


def test_context_too_small_is_first_before_insufficient_samples(rule_selection):
    candidate = rule_selection(context_window=1199, trials=0, successes=0)
    assert (candidate.reason, candidate.eligible, candidate.passes) == ("context_too_small", False, False)


def test_insufficient_samples_is_first_even_when_quality_is_below_bar(rule_selection):
    candidate = rule_selection(trials=9, successes=0)
    assert (candidate.reason, candidate.eligible, candidate.passes) == ("insufficient_samples", True, False)


def test_below_bar_is_first_when_eligible_and_sufficiently_measured(rule_selection):
    candidate = rule_selection(trials=100, successes=50)
    assert (candidate.reason, candidate.eligible, candidate.passes) == ("below_bar", True, False)


def test_passes_when_all_prior_rules_do_not_apply(rule_selection):
    candidate = rule_selection()
    assert (candidate.reason, candidate.eligible, candidate.passes) == ("passes", True, True)


def test_context_and_sample_and_quality_boundaries_are_inclusive(rule_selection):
    candidate = rule_selection(context_window=1200, trials=10, successes=10,
                               task_overrides={"bar": wilson_lower_bound(10, 10)})
    assert candidate.reason == "passes"


def test_independence_false_allows_generator_and_its_family(rule_selection):
    for generator in ("fiction/target", "fiction/sibling"):
        candidate = rule_selection(generator=generator,
                                   task_overrides={"independent_of_generator": False})
        assert candidate.reason == "passes"


def test_min_samples_blocks_high_quality_even_with_zero_bar(rule_selection):
    candidate = rule_selection(trials=0, successes=0, task_overrides={"bar": 0.0})
    assert candidate.reason == "insufficient_samples"


def test_router_stores_constructor_arguments(registry, task_factory, measured_stats, priors):
    tasks = {"judge": task_factory()}
    router = Router(registry, tasks, measured_stats, priors)
    assert router.registry is registry
    assert router.tasks is tasks
    assert router.stats is measured_stats
    assert router.priors is priors


@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_candidates_preserve_registry_order_costs_counts_and_lower_bounds(router, flavor):
    decision = router.select("judge", flavor=flavor, exclude_models=("fiction/cheap",))
    assert isinstance(decision.candidates, tuple)
    assert [c.model_id for c in decision.candidates] == [m.id for m in router.registry.models]
    for candidate in decision.candidates:
        model = router.registry.get(candidate.model_id)
        counts = router.stats.get("judge", model.id)
        assert candidate.family == model.family
        assert (candidate.successes, candidate.trials) == counts
        assert candidate.quality_lb == pytest.approx(wilson_lower_bound(*counts))
        assert candidate.list_cost == pytest.approx(model.cost(1000, 200))
        assert candidate.routing_cost == (candidate.list_cost if flavor == "cost_effective" else 0.0)
    assert decision.candidates[0].quality_lb > 0


def test_candidate_lower_bound_uses_task_confidence_even_when_excluded(registry, task_factory, measured_stats):
    task = task_factory(confidence=0.8)
    router = Router(registry, {"judge": task}, measured_stats)
    decision = router.select("judge", exclude_models=("fiction/cheap",))
    assert decision.candidates[0].quality_lb == pytest.approx(wilson_lower_bound(90, 100, 0.8))


def test_cost_effective_picks_cheapest_passing_not_highest_quality(router):
    decision = router.select("judge")
    assert decision.primary == "fiction/cheap"
    assert decision.fallbacks == ("fiction/mid", "fiction/best")
    assert decision.basis == "measured"
    assert decision.below_bar is False
    assert decision.task == "judge" and decision.flavor == "cost_effective"


def test_cost_effective_skips_cheaper_model_that_does_not_pass(registry, task_factory):
    stats = Stats()
    stats.add("judge", "fiction/cheap", 0, 100)
    stats.add("judge", "fiction/mid", 95, 100)
    stats.add("judge", "fiction/best", 100, 100)
    decision = Router(registry, {"judge": task_factory()}, stats).select("judge")
    assert decision.primary == "fiction/mid"
    assert decision.fallbacks == ("fiction/best",)


def test_cost_effective_price_ties_use_quality_then_ascending_id(model_factory, task_factory):
    registry = Registry([model_factory("fiction/z"), model_factory("fiction/b"),
                         model_factory("fiction/a")])
    stats = Stats()
    for model, successes in [("fiction/z", 90), ("fiction/b", 100), ("fiction/a", 100)]:
        stats.add("judge", model, successes, 100)
    decision = Router(registry, {"judge": task_factory()}, stats).select("judge")
    assert (decision.primary, *decision.fallbacks) == ("fiction/a", "fiction/b", "fiction/z")


def test_cost_effective_ranks_expected_full_call_cost_not_input_price(model_factory, task_factory):
    registry = Registry([model_factory("fiction/input-cheap", price_in=1, price_out=100),
                         model_factory("fiction/call-cheap", price_in=2, price_out=1)])
    stats = Stats()
    for model in registry.models:
        stats.add("judge", model.id, 100, 100)
    router = Router(registry, {"judge": task_factory()}, stats)
    assert router.select("judge").primary == "fiction/call-cheap"


def test_cost_blind_picks_highest_lower_bound_despite_price(router):
    decision = router.select("judge", flavor="cost_blind")
    assert decision.primary == "fiction/best"
    assert decision.fallbacks == ("fiction/mid", "fiction/cheap")
    assert decision.basis == "measured" and not decision.below_bar


def test_cost_blind_uses_confidence_bound_not_raw_accuracy(model_factory, task_factory):
    registry = Registry([model_factory("fiction/perfect"), model_factory("fiction/evidence")])
    stats = Stats()
    stats.add("judge", "fiction/perfect", 10, 10)
    stats.add("judge", "fiction/evidence", 95, 100)
    decision = Router(registry, {"judge": task_factory()}, stats).select("judge", "cost_blind")
    assert decision.primary == "fiction/evidence"


def test_cost_blind_equal_quality_uses_id_not_price(model_factory, task_factory):
    registry = Registry([model_factory("fiction/z", price_in=1),
                         model_factory("fiction/a", price_in=99)])
    stats = Stats()
    for model in registry.models:
        stats.add("judge", model.id, 100, 100)
    decision = Router(registry, {"judge": task_factory()}, stats).select("judge", "cost_blind")
    assert decision.primary == "fiction/a"


@pytest.mark.parametrize("limit,expected", [(0, ()), (1, ("fiction/mid",)),
                                           (2, ("fiction/mid", "fiction/best")),
                                           (10, ("fiction/mid", "fiction/best"))])
def test_max_fallbacks_limits_only_fallbacks(registry, task_factory, measured_stats, limit, expected):
    router = Router(registry, {"judge": task_factory(max_fallbacks=limit)}, measured_stats)
    decision = router.select("judge")
    assert decision.primary == "fiction/cheap"
    assert decision.fallbacks == expected


def test_refuse_raises_with_all_candidates_in_registry_order(registry, task_factory, priors):
    router = Router(registry, {"judge": task_factory(prior_category="judging")}, Stats(), priors)
    with pytest.raises(NoModelClearsBar) as caught:
        router.select("judge", exclude_models=("fiction/cheap",))
    candidates = caught.value.candidates
    assert isinstance(candidates, tuple)
    assert [c.model_id for c in candidates] == [m.id for m in registry.models]
    assert [c.reason for c in candidates] == ["excluded_model", "insufficient_samples",
                                             "insufficient_samples"]
    assert all(c.quality_lb == 0.0 and not c.passes for c in candidates)


def test_best_available_prefers_measured_quality_over_cost_and_prior(registry, task_factory, priors):
    stats = Stats()
    stats.add("judge", "fiction/cheap", 1, 1)
    stats.add("judge", "fiction/mid", 4, 4)
    task = task_factory(bar=1.0, on_no_model="best_available", prior_category="judging")
    decision = Router(registry, {"judge": task}, stats, priors).select("judge")
    assert decision.primary == "fiction/mid"
    assert decision.fallbacks == ("fiction/cheap",)
    assert decision.below_bar is True and decision.basis == "measured"
    assert all(c.reason == "insufficient_samples" for c in decision.candidates)


@pytest.mark.parametrize("flavor,expected", [
    ("cost_effective", ("fiction/z", "fiction/a", "fiction/b")),
    ("cost_blind", ("fiction/a", "fiction/b", "fiction/z")),
])
def test_best_available_measured_ties_use_routing_cost_then_id(model_factory, task_factory, flavor, expected):
    registry = Registry([model_factory("fiction/z", price_in=1),
                         model_factory("fiction/b", price_in=3),
                         model_factory("fiction/a", price_in=3)])
    stats = Stats()
    for model in registry.models:
        stats.add("judge", model.id, 1, 1)
    task = task_factory(bar=1, on_no_model="best_available")
    decision = Router(registry, {"judge": task}, stats).select("judge", flavor)
    assert (decision.primary, *decision.fallbacks) == expected
    assert decision.basis == "measured" and decision.below_bar


def test_best_available_uses_priors_only_when_eligible_measured_list_is_empty(registry, task_factory, priors):
    stats = Stats()
    stats.add("judge", "fiction/cheap", 100, 100)
    task = task_factory(on_no_model="best_available", prior_category="judging")
    decision = Router(registry, {"judge": task}, stats, priors).select(
        "judge", exclude_models=("fiction/cheap",))
    assert decision.primary == "fiction/mid"
    assert decision.fallbacks == ("fiction/best",)
    assert decision.basis == "prior" and decision.below_bar
    assert not any(c.passes for c in decision.candidates)


@pytest.mark.parametrize("flavor,expected", [
    ("cost_effective", ("fiction/z", "fiction/a", "fiction/b")),
    ("cost_blind", ("fiction/a", "fiction/b", "fiction/z")),
])
def test_best_available_prior_ties_use_routing_cost_then_id(model_factory, task_factory, flavor, expected):
    registry = Registry([model_factory("fiction/z", price_in=1),
                         model_factory("fiction/b", price_in=3),
                         model_factory("fiction/a", price_in=3),
                         model_factory("fiction/unscored", price_in=0)])
    priors = Priors({"judging": {"metric": "score", "source": "https://example.org",
                                "as_of": "2026-01-01", "scores": {
                                    "fiction/a": 5, "fiction/b": 5, "fiction/z": 5}}})
    task = task_factory(on_no_model="best_available", prior_category="judging", max_fallbacks=10)
    decision = Router(registry, {"judge": task}, Stats(), priors).select("judge", flavor)
    assert (decision.primary, *decision.fallbacks) == expected
    assert decision.basis == "prior" and decision.below_bar


def test_best_available_prior_scores_outrank_cost(registry, task_factory, priors):
    task = task_factory(on_no_model="best_available", prior_category="judging", max_fallbacks=0)
    decision = Router(registry, {"judge": task}, Stats(), priors).select("judge")
    assert decision.primary == "fiction/mid"
    assert decision.fallbacks == ()


@pytest.mark.parametrize("category,with_priors,exclude", [
    (None, False, ()), (None, True, ()), ("missing", True, ()),
    ("judging", False, ()),
    ("judging", True, ("fiction/cheap", "fiction/mid", "fiction/best")),
])
def test_best_available_refuses_when_neither_eligible_measurements_nor_priors_exist(
        registry, task_factory, priors, category, with_priors, exclude):
    task = task_factory(on_no_model="best_available", prior_category=category)
    router = Router(registry, {"judge": task}, Stats(), priors if with_priors else None)
    with pytest.raises(NoModelClearsBar):
        router.select("judge", exclude_models=exclude)


def test_passing_measurements_take_precedence_over_best_available_priors(registry, task_factory, measured_stats, priors):
    task = task_factory(on_no_model="best_available", prior_category="judging")
    decision = Router(registry, {"judge": task}, measured_stats, priors).select("judge")
    assert decision.primary == "fiction/cheap"
    assert not decision.below_bar and decision.basis == "measured"


def test_unknown_flavor_raises_valueerror(router):
    with pytest.raises(ValueError):
        router.select("judge", flavor="unknown")


def test_unknown_task_raises_keyerror(router):
    with pytest.raises(KeyError):
        router.select("unknown")


def test_unknown_generator_raises_keyerror(router):
    with pytest.raises(KeyError):
        router.select("judge", generator_model="fiction/missing")


def test_route_decision_to_dict_is_plain_json_with_lists_and_candidate_dicts(router):
    decision = router.select("judge")
    data = decision.to_dict()
    assert set(data) == {"task", "flavor", "primary", "fallbacks", "below_bar", "basis", "candidates"}
    assert data["fallbacks"] == list(decision.fallbacks)
    assert isinstance(data["candidates"], list)
    assert data["candidates"][0] == {
        "model_id": "fiction/cheap", "family": "small", "successes": 90, "trials": 100,
        "quality_lb": decision.candidates[0].quality_lb,
        "routing_cost": 0.0014, "list_cost": 0.0014,
        "eligible": True, "passes": True, "reason": "passes",
    }
    assert json.loads(json.dumps(data)) == data


def test_candidates_and_decisions_are_frozen(router):
    decision = router.select("judge")
    with pytest.raises(FrozenInstanceError):
        decision.primary = "fiction/other"
    with pytest.raises(FrozenInstanceError):
        decision.candidates[0].reason = "other"


def test_best_available_measured_path_applies_max_fallbacks(registry, task_factory, measured_stats):
    task = task_factory(bar=1.0, on_no_model="best_available", max_fallbacks=1)
    decision = Router(registry, {"judge": task}, measured_stats).select("judge")
    assert decision.primary == "fiction/best"
    assert decision.fallbacks == ("fiction/mid",)
    assert decision.basis == "measured" and decision.below_bar


def test_zero_prior_score_is_present_and_can_support_cold_start(registry, task_factory):
    priors = Priors({"judging": {"metric": "score", "source": "https://example.org",
                                "as_of": "2026-01-01", "scores": {"fiction/cheap": 0}}})
    task = task_factory(on_no_model="best_available", prior_category="judging")
    decision = Router(registry, {"judge": task}, Stats(), priors).select("judge")
    assert decision.primary == "fiction/cheap" and decision.fallbacks == ()
    assert decision.basis == "prior" and decision.below_bar


@pytest.mark.parametrize("policy", ["refuse", "best_available"])
def test_empty_registry_raises_no_model_with_empty_candidates(task_factory, policy):
    from model_routing import Registry
    task = task_factory(on_no_model=policy, prior_category="judging")
    router = Router(Registry([]), {"judge": task}, Stats())
    with pytest.raises(NoModelClearsBar) as caught:
        router.select("judge")
    assert caught.value.candidates == ()
