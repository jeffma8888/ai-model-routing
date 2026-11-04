"""v1.4 delegation contract (DESIGN section 13), written before the module exists.

Every test imports ``model_routing.delegation`` first, so until it exists each one
fails with ModuleNotFoundError and the strict xfail below keeps the suite green.
The implementing commit removes ``pytestmark`` (DESIGN 13.8).
"""

import dataclasses
import importlib
import json
import re

import pytest

import model_routing
from model_routing import Model, NoModelClearsBar, Priors, Registry, Router, Stats, Task, main
from model_routing.stats import wilson_lower_bound

pytestmark = pytest.mark.xfail(
    strict=True, raises=ModuleNotFoundError,
    reason="D2: model_routing.delegation is specified (DESIGN 13) but not implemented yet")

S_IN, S_OUT = 2000, 500
WORK = {"context_tokens": 20_000, "brief_tokens": 300, "result_tokens": 200}
MEASURED = {"fiction/cheap": (70, 100), "fiction/mid": (95, 100), "fiction/best": (99, 100)}
ALL_BELOW = {"fiction/cheap": (70, 100), "fiction/mid": (75, 100), "fiction/best": (78, 100)}
FIELDS = ["task", "flavor", "parent", "mode", "model", "reason", "below_bar", "inline_allowed",
          "inline_cost_usd", "delegate_cost_usd", "parent_quality_lb", "delegate_quality_lb",
          "route"]
REASONS = ["PARENT_EXCLUDED_FAMILY", "PARENT_NOT_INDEPENDENT", "PARENT_CONTEXT_FULL",
           "PARENT_BELOW_BAR", "DELEGATE_CHEAPER", "INLINE_CHEAPER", "DELEGATE_BETTER",
           "INLINE_AS_GOOD", "ONLY_PARENT_CLEARS", "NONE_CLEAR"]


def load_dl():
    return importlib.import_module("model_routing.delegation")


def models(window=100_000, free=False, extra=()):
    """cheap 1/2, mid 3/6, best 10/20 USD per 1M tokens (all 0 when ``free``)."""
    def price(value):
        return 0.0 if free else value
    return [Model("fiction/cheap", "small", price(1.0), price(2.0), window),
            Model("fiction/mid", "medium", price(3.0), price(6.0), window),
            Model("fiction/best", "large", price(10.0), price(20.0), window), *extra]


def make_router(stats=MEASURED, registry_models=None, priors=None, **task_fields):
    fields = {"name": "review", "bar": 0.8, "min_samples": 30,
              "expected_input_tokens": S_IN, "expected_output_tokens": S_OUT}
    fields.update(task_fields)
    task = Task(**fields)
    measured = Stats()
    for model_id, (successes, trials) in stats.items():
        measured.add("review", model_id, successes, trials)
    registry = Registry(models() if registry_models is None else registry_models)
    return Router(registry, {"review": task}, measured, priors)


def decide(router, parent, flavor="cost_effective", **kwargs):
    load_dl()
    work = dict(WORK)
    work.update(kwargs)
    return router.decide_delegation("review", parent, flavor, **work)


def cost(router, model_id, input_tokens, output_tokens):
    return router.registry.get(model_id).cost(input_tokens, output_tokens)


def inline_cost(router, parent, context=20_000, carry=0):
    return cost(router, parent, context + S_IN, S_OUT) + carry * cost(router, parent, S_IN + S_OUT, 0)


def delegate_cost(router, parent, delegate, brief=300, result=200, carry=0):
    return (cost(router, parent, result, brief) + cost(router, delegate, brief + S_IN, S_OUT)
            + carry * cost(router, parent, brief + result, 0))


def lb(stats, model_id):
    return wilson_lower_bound(*stats[model_id], 0.95)


# 13.6 types, constants and exports

def test_modes_and_reason_codes_have_the_pinned_values():
    dl = load_dl()
    assert (dl.INLINE, dl.DELEGATE) == ("inline", "delegate")
    for name in REASONS:
        assert getattr(dl, name) == name.lower()


def test_decision_is_a_frozen_dataclass_with_the_pinned_fields_and_is_exported():
    dl = load_dl()
    assert [f.name for f in dataclasses.fields(dl.DelegationDecision)] == FIELDS
    assert "DelegationDecision" in model_routing.__all__
    assert model_routing.DelegationDecision is dl.DelegationDecision
    decision = decide(make_router(), "fiction/best")
    with pytest.raises(dataclasses.FrozenInstanceError):
        decision.mode = "inline"


def test_to_dict_is_plain_json_with_the_route_as_its_own_dict():
    router = make_router()
    decision = decide(router, "fiction/best")
    data = decision.to_dict()
    assert list(data) == FIELDS
    assert data["route"] == decision.route.to_dict()
    assert json.loads(json.dumps(data)) == data
    alone = decide(router, "fiction/best", exclude_models=("fiction/cheap", "fiction/mid",
                                                            "fiction/best"))
    assert alone.route is None and alone.to_dict()["route"] is None


# 13.2 cost of each path

def test_costs_follow_the_pinned_formulas():
    router = make_router()
    decision = decide(router, "fiction/best")
    assert decision.inline_cost_usd == pytest.approx(0.23, rel=1e-12)
    assert decision.inline_cost_usd == pytest.approx(inline_cost(router, "fiction/best"), rel=1e-12)
    assert decision.delegate_cost_usd == pytest.approx(0.0179, rel=1e-12)
    assert decision.delegate_cost_usd == pytest.approx(
        delegate_cost(router, "fiction/best", "fiction/mid"), rel=1e-12)


def test_carry_turns_charge_each_path_for_what_it_leaves_in_the_parent_context():
    router = make_router()
    decision = decide(router, "fiction/best", carry_turns=3)
    assert decision.inline_cost_usd == pytest.approx(0.23 + 3 * 0.025, rel=1e-12)
    assert decision.delegate_cost_usd == pytest.approx(0.0179 + 3 * 0.005, rel=1e-12)


def test_carry_turns_can_turn_an_inline_decision_into_a_delegation():
    router = make_router()
    stay = decide(router, "fiction/mid", context_tokens=1000)
    assert (stay.mode, stay.reason) == ("inline", "inline_cheaper")
    assert stay.inline_cost_usd == pytest.approx(0.012, rel=1e-12)
    assert stay.delegate_cost_usd == pytest.approx(0.0123, rel=1e-12)
    go = decide(router, "fiction/mid", context_tokens=1000, carry_turns=1)
    assert (go.mode, go.reason, go.model) == ("delegate", "delegate_cheaper", "fiction/mid")
    assert go.inline_cost_usd == pytest.approx(0.0195, rel=1e-12)
    assert go.delegate_cost_usd == pytest.approx(0.0138, rel=1e-12)


def test_costs_are_list_price_in_cost_blind_too():
    router = make_router()
    blind = decide(router, "fiction/mid", "cost_blind")
    assert blind.route.primary == "fiction/best"
    assert blind.inline_cost_usd == pytest.approx(inline_cost(router, "fiction/mid"), rel=1e-12)
    assert blind.delegate_cost_usd == pytest.approx(
        delegate_cost(router, "fiction/mid", "fiction/best"), rel=1e-12)


def test_a_large_context_can_make_delegating_to_the_parents_own_model_cheaper():
    router = make_router()
    decision = decide(router, "fiction/mid")
    assert (decision.mode, decision.reason) == ("delegate", "delegate_cheaper")
    assert decision.model == decision.parent == "fiction/mid"
    assert decision.inline_cost_usd == pytest.approx(0.069, rel=1e-12)
    assert decision.delegate_cost_usd == pytest.approx(0.0123, rel=1e-12)


# 13.3 the delegate

def test_the_delegate_is_routed_on_a_task_copy_with_the_brief_added_to_its_input():
    router = make_router()
    decision = decide(router, "fiction/best", "cost_effective", generator_model="fiction/cheap",
                      exclude_models=("fiction/best",))
    copy = dataclasses.replace(router.tasks["review"], expected_input_tokens=S_IN + 300)
    expected = Router(router.registry, {"review": copy}, router.stats, router.priors).select(
        "review", "cost_effective", generator_model="fiction/cheap",
        exclude_models=("fiction/best",))
    assert decision.route == expected
    mid = [c for c in decision.route.candidates if c.model_id == "fiction/mid"][0]
    assert mid.list_cost == pytest.approx(cost(router, "fiction/mid", S_IN + 300, S_OUT), rel=1e-12)
    assert router.tasks["review"].expected_input_tokens == S_IN


def test_the_delegate_context_rule_counts_the_brief():
    tight = [Model("fiction/cheap", "small", 1.0, 2.0, S_IN + S_OUT + 299),
             Model("fiction/mid", "medium", 3.0, 6.0, 100_000),
             Model("fiction/best", "large", 10.0, 20.0, 100_000)]
    router = make_router(stats={"fiction/cheap": (99, 100), "fiction/mid": (95, 100),
                                "fiction/best": (99, 100)}, registry_models=tight)
    assert router.select("review").primary == "fiction/cheap"
    decision = decide(router, "fiction/best")
    reasons = {c.model_id: c.reason for c in decision.route.candidates}
    assert reasons["fiction/cheap"] == "context_too_small"
    assert decision.route.primary == decision.model == "fiction/mid"


def test_delegate_quality_is_the_route_primary_lower_bound():
    decision = decide(make_router(), "fiction/mid", "cost_blind")
    primary = [c for c in decision.route.candidates if c.model_id == decision.route.primary][0]
    assert decision.delegate_quality_lb == primary.quality_lb
    assert decision.delegate_quality_lb == pytest.approx(lb(MEASURED, "fiction/best"), abs=1e-12)
    assert decision.parent_quality_lb == pytest.approx(lb(MEASURED, "fiction/mid"), abs=1e-12)


def test_the_cost_effective_delegate_minimises_delegate_cost_among_passing_models():
    router = make_router(stats={"fiction/cheap": (95, 100), "fiction/mid": (95, 100),
                                "fiction/best": (99, 100)})
    decision = decide(router, "fiction/best")
    assert decision.model == "fiction/cheap"
    for c in decision.route.candidates:
        if c.passes:
            assert decision.delegate_cost_usd <= delegate_cost(
                router, "fiction/best", c.model_id) + 1e-15


# 13.4 and 13.5 row 1: inline blocked, the parent must delegate

def test_a_parent_that_generated_the_output_must_delegate_even_when_inline_is_cheaper():
    router = make_router()
    decision = decide(router, "fiction/mid", generator_model="fiction/mid", context_tokens=1000)
    assert decision.inline_cost_usd < decision.delegate_cost_usd
    assert (decision.mode, decision.reason, decision.model) == (
        "delegate", "parent_not_independent", "fiction/best")
    assert decision.inline_allowed is False and decision.below_bar is False
    reasons = {c.model_id: c.reason for c in decision.route.candidates}
    assert reasons["fiction/mid"] == "generator"


def test_a_parent_in_the_generator_family_must_delegate():
    sibling = Model("fiction/mid-2", "medium", 2.0, 4.0, 100_000)
    router = make_router(stats=dict(MEASURED, **{"fiction/mid-2": (95, 100)}),
                         registry_models=models(extra=(sibling,)))
    decision = decide(router, "fiction/mid", generator_model="fiction/mid-2",
                      context_tokens=1000)
    assert (decision.mode, decision.reason, decision.model) == (
        "delegate", "parent_not_independent", "fiction/best")
    reasons = {c.model_id: c.reason for c in decision.route.candidates}
    assert reasons["fiction/mid"] == "generator_family"


def test_without_independence_the_generator_may_work_inline():
    router = make_router(independent_of_generator=False)
    decision = decide(router, "fiction/mid", generator_model="fiction/mid", context_tokens=1000)
    assert decision.inline_allowed is True
    assert (decision.mode, decision.reason, decision.model) == (
        "inline", "inline_cheaper", "fiction/mid")


def test_a_parent_whose_family_the_task_excludes_must_delegate():
    router = make_router(exclude_families=("medium",))
    decision = decide(router, "fiction/mid", context_tokens=1000)
    assert (decision.mode, decision.reason, decision.model) == (
        "delegate", "parent_excluded_family", "fiction/best")
    assert decision.inline_allowed is False


def test_a_full_parent_context_forces_delegation_and_an_exact_fit_does_not():
    router = make_router()
    full = decide(router, "fiction/mid", context_tokens=100_000 - S_IN - S_OUT + 1)
    assert (full.mode, full.reason, full.inline_allowed) == ("delegate", "parent_context_full", False)
    fits = decide(router, "fiction/mid", context_tokens=100_000 - S_IN - S_OUT)
    assert fits.inline_allowed is True and fits.reason != "parent_context_full"


@pytest.mark.parametrize("task_fields, extra, reason", [
    ({"exclude_families": ("medium",)}, {"generator_model": "fiction/mid"}, "parent_excluded_family"),
    ({}, {"generator_model": "fiction/mid"}, "parent_not_independent"),
])
def test_blocking_rules_apply_in_the_pinned_order(task_fields, extra, reason):
    router = make_router(**task_fields)
    decision = decide(router, "fiction/mid", context_tokens=200_000, **extra)
    assert decision.reason == reason


def test_a_blocked_parent_with_no_route_raises_no_model_clears_bar():
    router = make_router(stats=ALL_BELOW)
    load_dl()
    with pytest.raises(NoModelClearsBar) as info:
        decide(router, "fiction/mid", generator_model="fiction/mid")
    assert [c.model_id for c in info.value.candidates] == [
        "fiction/cheap", "fiction/mid", "fiction/best"]


def test_a_blocked_parent_delegates_below_the_bar_only_under_best_available():
    router = make_router(stats=ALL_BELOW, on_no_model="best_available")
    decision = decide(router, "fiction/mid", generator_model="fiction/mid")
    assert (decision.mode, decision.reason, decision.model) == (
        "delegate", "parent_not_independent", "fiction/best")
    assert decision.below_bar is True and decision.route.below_bar is True


# 13.5 rows 2 to 5: inline allowed

def test_cost_effective_delegates_to_a_cheaper_passing_model():
    decision = decide(make_router(), "fiction/best")
    assert (decision.mode, decision.reason, decision.model) == (
        "delegate", "delegate_cheaper", "fiction/mid")
    assert decision.below_bar is False and decision.inline_allowed is True


def test_cost_effective_stays_inline_when_inline_is_cheaper():
    decision = decide(make_router(), "fiction/mid", context_tokens=1000)
    assert (decision.mode, decision.reason, decision.model) == (
        "inline", "inline_cheaper", "fiction/mid")
    assert decision.route is not None and decision.below_bar is False


def test_a_parent_below_the_bar_delegates_even_when_that_costs_more():
    decision = decide(make_router(), "fiction/cheap", context_tokens=1000)
    assert decision.delegate_cost_usd > decision.inline_cost_usd
    assert (decision.mode, decision.reason, decision.model) == (
        "delegate", "parent_below_bar", "fiction/mid")


def test_a_parent_needs_min_samples_trials_to_clear_the_bar():
    short = make_router(stats=dict(MEASURED, **{"fiction/cheap": (29, 29)}))
    decision = decide(short, "fiction/cheap", context_tokens=1000)
    assert decision.parent_quality_lb >= 0.8
    assert (decision.mode, decision.reason) == ("delegate", "parent_below_bar")
    enough = make_router(stats=dict(MEASURED, **{"fiction/cheap": (30, 30)}))
    decision = decide(enough, "fiction/cheap", context_tokens=1000)
    assert (decision.mode, decision.reason, decision.model) == (
        "inline", "inline_cheaper", "fiction/cheap")


def test_cost_blind_delegates_only_to_a_higher_lower_bound():
    router = make_router()
    up = decide(router, "fiction/mid", "cost_blind", context_tokens=1000)
    assert (up.mode, up.reason, up.model) == ("delegate", "delegate_better", "fiction/best")
    assert up.delegate_cost_usd > up.inline_cost_usd
    same = decide(router, "fiction/best", "cost_blind")
    assert (same.mode, same.reason, same.model) == ("inline", "inline_as_good", "fiction/best")
    assert same.delegate_quality_lb == same.parent_quality_lb


def test_a_cost_effective_tie_goes_to_quality_then_inline():
    router = make_router(registry_models=models(free=True))
    better = decide(router, "fiction/mid")
    assert better.inline_cost_usd == better.delegate_cost_usd == 0.0
    assert (better.mode, better.reason, better.model) == (
        "delegate", "delegate_better", "fiction/best")
    same = decide(router, "fiction/best")
    assert (same.mode, same.reason, same.model) == ("inline", "inline_as_good", "fiction/best")


def test_exclude_models_limits_the_delegate_and_never_the_parent():
    router = make_router()
    away = decide(router, "fiction/mid", exclude_models=("fiction/mid",))
    assert (away.mode, away.reason, away.model) == ("delegate", "delegate_cheaper", "fiction/best")
    home = decide(router, "fiction/mid", exclude_models=("fiction/mid",), context_tokens=1000)
    assert (home.mode, home.reason, home.model) == ("inline", "inline_cheaper", "fiction/mid")
    assert home.inline_allowed is True


def test_only_the_parent_clears_with_no_route():
    every = ("fiction/cheap", "fiction/mid", "fiction/best")
    decision = decide(make_router(), "fiction/best", exclude_models=every)
    assert (decision.mode, decision.reason, decision.model) == (
        "inline", "only_parent_clears", "fiction/best")
    assert decision.route is None
    assert decision.delegate_cost_usd is None and decision.delegate_quality_lb is None
    assert decision.below_bar is False


def test_only_the_parent_clears_with_a_below_bar_route():
    stats = {"fiction/cheap": (70, 100), "fiction/mid": (95, 100), "fiction/best": (75, 100)}
    router = make_router(stats=stats, on_no_model="best_available")
    decision = decide(router, "fiction/mid", exclude_models=("fiction/mid",))
    assert decision.route.below_bar is True and decision.route.primary == "fiction/best"
    assert (decision.mode, decision.reason, decision.model) == (
        "inline", "only_parent_clears", "fiction/mid")
    assert decision.below_bar is False


# 13.5 rows 6 and 7: neither clears

def test_neither_clears_under_refuse_raises():
    router = make_router(stats=ALL_BELOW)
    load_dl()
    with pytest.raises(NoModelClearsBar) as info:
        decide(router, "fiction/mid")
    assert len(info.value.candidates) == 3
    assert all(c.reason == "below_bar" for c in info.value.candidates)


def test_neither_clears_under_best_available_takes_the_higher_measured_bound_ties_inline():
    router = make_router(stats=ALL_BELOW, on_no_model="best_available")
    up = decide(router, "fiction/mid", context_tokens=1000)
    assert (up.mode, up.reason, up.model, up.below_bar) == (
        "delegate", "none_clear", "fiction/best", True)
    same = decide(router, "fiction/best")
    assert (same.mode, same.reason, same.model, same.below_bar) == (
        "inline", "none_clear", "fiction/best", True)


def test_neither_clears_an_unmeasured_parent_takes_a_measured_route():
    stats = {"fiction/mid": (75, 100), "fiction/best": (78, 100)}
    router = make_router(stats=stats, on_no_model="best_available")
    decision = decide(router, "fiction/cheap", context_tokens=1000)
    assert decision.parent_quality_lb == 0.0
    assert (decision.mode, decision.reason, decision.model, decision.below_bar) == (
        "delegate", "none_clear", "fiction/best", True)


def prior_router(stats):
    priors = Priors({"review": {"metric": "fictional", "source": "https://example.org/scores",
                                "as_of": "2026-01-01",
                                "scores": {"fiction/cheap": 50, "fiction/best": 90}}})
    return make_router(stats=stats, priors=priors, on_no_model="best_available",
                       prior_category="review")


def test_neither_clears_a_measured_parent_beats_a_prior_route():
    router = prior_router({"fiction/mid": (75, 100)})
    decision = decide(router, "fiction/mid", exclude_models=("fiction/mid",))
    assert decision.route.basis == "prior" and decision.route.primary == "fiction/best"
    assert (decision.mode, decision.reason, decision.model, decision.below_bar) == (
        "inline", "none_clear", "fiction/mid", True)


def test_neither_clears_an_unmeasured_parent_takes_a_prior_route():
    router = prior_router({})
    decision = decide(router, "fiction/mid", exclude_models=("fiction/mid",))
    assert decision.route.basis == "prior"
    assert (decision.mode, decision.reason, decision.model, decision.below_bar) == (
        "delegate", "none_clear", "fiction/best", True)


def test_neither_clears_with_nothing_measured_or_prior_raises():
    router = make_router(stats={}, on_no_model="best_available")
    load_dl()
    with pytest.raises(NoModelClearsBar):
        decide(router, "fiction/mid")


# 13.1 validation

@pytest.mark.parametrize("name", ["context_tokens", "brief_tokens", "result_tokens",
                                  "carry_turns"])
@pytest.mark.parametrize("value", [-1, 1.5, True, "10", None])
def test_token_counts_must_be_non_negative_integers(name, value):
    router = make_router()
    load_dl()
    with pytest.raises(ValueError):
        decide(router, "fiction/best", **{name: value})


def test_zero_token_counts_are_allowed():
    decision = decide(make_router(), "fiction/best", context_tokens=0, brief_tokens=0,
                      result_tokens=0, carry_turns=0)
    assert decision.mode in ("inline", "delegate")


def test_unknown_task_parent_or_generator_raise_key_error_and_unknown_flavor_value_error():
    router = make_router()
    load_dl()
    with pytest.raises(KeyError):
        router.decide_delegation("nope", "fiction/best", **WORK)
    with pytest.raises(KeyError):
        decide(router, "fiction/nope")
    with pytest.raises(KeyError):
        decide(router, "fiction/best", generator_model="fiction/nope")
    with pytest.raises(ValueError):
        decide(router, "fiction/best", "cheapest")


def test_the_decision_is_deterministic():
    router = make_router()
    assert decide(router, "fiction/best") == decide(router, "fiction/best")


# 13.7 CLI

@pytest.fixture
def delegate_files(tmp_path):
    registry = make_router().registry
    rows = [dict(dataclasses.asdict(m), source="https://example.org/prices")
            for m in registry.models]
    paths = {"registry": tmp_path / "models.json", "tasks": tmp_path / "tasks.json",
             "stats": tmp_path / "stats.json", "priors": tmp_path / "no-priors.json"}
    paths["registry"].write_text(json.dumps({"version": "1", "as_of": "2026-01-01",
                                             "currency": "USD", "models": rows}),
                                 encoding="utf-8")
    task = dataclasses.asdict(make_router().tasks["review"])
    paths["tasks"].write_text(json.dumps({"tasks": [task]}), encoding="utf-8")
    make_router().stats.save(paths["stats"])
    return paths


def delegate_args(files, parent="fiction/best", *extra, **work):
    tokens = dict(WORK)
    tokens.update(work)
    args = ["delegate", "review", "--parent", parent]
    for key, value in tokens.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    for flag, path in files.items():
        args += ["--" + flag, str(path)]
    return args + list(extra)


def test_cli_json_matches_the_api(delegate_files, capsys):
    load_dl()
    assert main(delegate_args(delegate_files, "fiction/best", "--json")) == 0
    data = json.loads(capsys.readouterr().out)
    assert data == decide(make_router(), "fiction/best").to_dict()


def test_cli_options_reach_the_api(delegate_files, capsys):
    load_dl()
    args = delegate_args(delegate_files, "fiction/mid", "--json", "--flavor", "cost_blind",
                         "--generator", "fiction/cheap", "--exclude", "fiction/best",
                         carry_turns=2)
    assert main(args) == 0
    data = json.loads(capsys.readouterr().out)
    expected = decide(make_router(), "fiction/mid", "cost_blind", carry_turns=2,
                      generator_model="fiction/cheap", exclude_models=("fiction/best",))
    assert data == expected.to_dict()


def test_cli_text_prints_one_line_per_key(delegate_files, capsys):
    load_dl()
    assert main(delegate_args(delegate_files, "fiction/best")) == 0
    text = capsys.readouterr().out
    for key, value in [("mode", "delegate"), ("model", "fiction/mid"),
                       ("reason", "delegate_cheaper"), ("below_bar", "false"),
                       ("inline_cost_usd", "0.230000"), ("delegate_cost_usd", "0.017900"),
                       ("parent_quality_lb", "0.946"), ("delegate_quality_lb", "0.888")]:
        assert re.search(rf"^{key}:\s+{re.escape(value)}$", text, re.MULTILINE), key


def test_cli_text_prints_a_dash_for_none(delegate_files, capsys):
    load_dl()
    args = delegate_args(delegate_files, "fiction/best", "--exclude", "fiction/cheap",
                         "fiction/mid", "fiction/best")
    assert main(args) == 0
    text = capsys.readouterr().out
    assert re.search(r"^reason:\s+only_parent_clears$", text, re.MULTILINE)
    assert re.search(r"^delegate_cost_usd:\s+-$", text, re.MULTILINE)
    assert re.search(r"^delegate_quality_lb:\s+-$", text, re.MULTILINE)


@pytest.mark.parametrize("change", [
    ("--parent", "fiction/nope"), ("--generator", "fiction/nope"), ("--exclude", "fiction/nope"),
    ("--context-tokens", "-1"), ("--brief-tokens", "1.5"), ("--result-tokens", "many"),
    ("--carry-turns", "-2"), ("--flavor", "cheapest"), ("task", "nope"), ("drop", "--brief-tokens"),
])
def test_cli_bad_input_exits_two_with_one_error_line(delegate_files, capsys, change):
    load_dl()
    args = delegate_args(delegate_files, "fiction/best")
    flag, value = change
    if flag == "task":
        args[1] = value
    elif flag == "drop":
        at = args.index(value)
        del args[at:at + 2]
    elif flag in args:
        args[args.index(flag) + 1] = value
    else:
        args += [flag, value]
    assert main(args) == 2
    err = capsys.readouterr().err
    assert re.search(r"^error: ", err, re.MULTILINE)


def test_cli_no_model_clears_bar_exits_three_with_candidates_on_stderr(tmp_path, delegate_files,
                                                                       capsys):
    load_dl()
    below = Stats()
    for model_id, (successes, trials) in ALL_BELOW.items():
        below.add("review", model_id, successes, trials)
    below.save(delegate_files["stats"])
    assert main(delegate_args(delegate_files, "fiction/mid")) == 3
    err = capsys.readouterr().err
    assert err.startswith("error: ")
    for model_id in ALL_BELOW:
        assert model_id in err
