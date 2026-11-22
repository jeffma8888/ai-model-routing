"""Variants of one model as routes of their own (DESIGN 4.1, 4.3, 5.2 and 9 v1.572, row VAR1a)."""

import dataclasses
import json
from pathlib import Path

import pytest

import model_routing
from model_routing import (BELOW_BAR, CONTEXT_TOO_SMALL, DATA_DIR, EXCLUDED_FAMILY, EXCLUDED_MODEL,
                           GENERATOR, GENERATOR_FAMILY, INSUFFICIENT_SAMPLES, PASSES, Cascade,
                           Completion, Executor, FakeProvider, Model, Monitor, Registry, Router,
                           Stats, Task, Variant, calibrate_from_results)

ROOT = Path(__file__).resolve().parents[1]


def row(model_id="v/m", family="v", **extra):
    return dict({"id": model_id, "family": family, "price_in": 1.0, "price_out": 2.0,
                 "context_window": 100_000}, **extra)


def load(tmp_path, rows):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": rows}), encoding="utf-8")
    return Registry.load(path)


def reasons(decision_or_exc):
    return {c.model_id: c.reason for c in decision_or_exc.candidates}


def test_variant_is_exported_from_the_package():
    assert "Variant" in model_routing.__all__
    from model_routing.registry import Variant as inner
    assert inner is Variant


def test_variant_defaults_and_a_copied_policy():
    plain = Variant("lean")
    assert (plain.reasoning_effort, plain.harness, plain.context_policy) == (None, None, {})
    policy = {"compact_at_tokens": 400_000}
    long = Variant("long", reasoning_effort="medium", harness="agent 1.2", context_policy=policy)
    policy["compact_at_tokens"] = 1
    assert long.context_policy == {"compact_at_tokens": 400_000}
    ok = Variant("a.B_9-x", context_policy={"a": None, "b": True, "c": 3, "d": 2.5, "e": "x"})
    assert ok.name == "a.B_9-x"


@pytest.mark.parametrize("name", ["", "a@b", "a b", "a/b", "-a", ".a", 3, None])
def test_a_variant_name_is_a_plain_token(name):
    with pytest.raises(ValueError):
        Variant(name)


@pytest.mark.parametrize("field", ["reasoning_effort", "harness"])
@pytest.mark.parametrize("value", ["", 3, b"low", True])
def test_effort_and_harness_are_none_or_a_non_empty_string(field, value):
    with pytest.raises(ValueError):
        Variant("lean", **{field: value})


@pytest.mark.parametrize("policy", [None, [("a", 1)], "a", {"": 1}, {1: 1}, {"a": [1]},
                                    {"a": {"b": 1}}, {"a": float("nan")}, {"a": float("inf")}])
def test_a_context_policy_is_a_mapping_of_scalars(policy):
    with pytest.raises(ValueError):
        Variant("lean", context_policy=policy)


def test_model_variant_is_the_last_field_and_names_the_route():
    assert [f.name for f in dataclasses.fields(Model)][-2:] == ["price_tiers", "variant"]
    lean = Model("v/m@lean", "v", 1.0, 2.0, 8000, variant=Variant("lean", harness="agent 2"))
    assert (lean.id, lean.base_id) == ("v/m@lean", "v/m")
    plain = Model("v/m", "v", 1.0, 2.0, 8000)
    assert (plain.variant, plain.base_id) == (None, "v/m")
    assert list(dataclasses.asdict(plain))[-1] == "variant"
    assert dataclasses.asdict(plain)["variant"] is None
    assert dataclasses.asdict(lean)["variant"] == {
        "name": "lean", "reasoning_effort": None, "harness": "agent 2", "context_policy": {},
        "items_per_call": 1}  # v1.573


@pytest.mark.parametrize("model_id, variant", [
    ("v/m@deep", Variant("lean")), ("@lean", Variant("lean")), ("a@b@lean", Variant("lean")),
    ("v/m", Variant("lean")), ("lean", Variant("lean")), (3, Variant("lean")),
    ("v/m@lean", "lean"), ("v/m", {"name": "x"}),
])
def test_a_route_id_and_its_variant_must_agree(model_id, variant):
    with pytest.raises(ValueError):
        Model(model_id, "v", 1.0, 2.0, 8000, variant=variant)


def test_a_model_without_a_variant_keeps_a_v1_571_id():
    cascade_like = Model("fiction/cheap>fiction/best@sig", "x", 1.0, 1.0, 100_000)
    assert cascade_like.base_id == cascade_like.id and cascade_like.variant is None


def test_null_settings_are_absent_and_aliases_are_copied(tmp_path):
    registry = load(tmp_path, [row("v/m", aliases={"gateway": "m-1"}, variants={
        "lean": {"harness": None, "reasoning_effort": None, "context_policy": None}})])
    lean = registry.get("v/m@lean")
    assert lean.variant == Variant("lean")
    assert lean.aliases == registry.get("v/m").aliases
    assert lean.aliases is not registry.get("v/m").aliases


def test_load_puts_each_variant_right_after_its_base(tmp_path):
    base = row("v/m", aliases={"gateway": "m-1"}, price_valid_until="2027-01-31",
               price_tiers=[{"above_input_tokens": 4000, "price_in": 2, "price_out": 4}],
               variants={"lean": {"harness": "lean-agent 2.0", "reasoning_effort": "low"},
                         "long": {"context_policy": {"compact_at_tokens": 400_000}}})
    registry = load(tmp_path, [base, row("w/n", "w"), row("x/k", "x", variants=None)])
    assert [m.id for m in registry.models] == ["v/m", "v/m@lean", "v/m@long", "w/n", "x/k"]
    first = registry.get("v/m")
    assert first.variant is None
    for name in ("lean", "long"):
        model = registry.get(f"v/m@{name}")
        assert model.base_id == "v/m" and model.variant.name == name
        for key in ("family", "price_in", "price_out", "context_window", "aliases",
                    "price_valid_until", "price_tiers"):
            assert getattr(model, key) == getattr(first, key)
    assert registry.get("v/m@lean").variant == Variant("lean", "low", "lean-agent 2.0")
    assert registry.get("v/m@long").variant.context_policy == {"compact_at_tokens": 400_000}
    assert registry.get("v/m").cost(5000, 100) == registry.get("v/m@lean").cost(5000, 100)


@pytest.mark.parametrize("variants", [
    [], "lean", {"lean": "x"}, {"lean": None}, {"lean": {"items_per_call": 0}},
    {"lean": {"provider_options": {"effort": "low"}}}, {"lean": {"harnes": "x"}},
    {"a@b": {}}, {"": {}}, {"lean": {"harness": ""}}, {"lean": {"context_policy": [1]}},
])
def test_an_invalid_variants_value_names_the_file(tmp_path, variants):
    with pytest.raises(ValueError, match="models.json"):
        load(tmp_path, [row("v/m", variants=variants)])


@pytest.mark.parametrize("extra", [{}, {"variants": {"lean": {}}}])
def test_a_row_id_holding_an_at_sign_is_refused(tmp_path, extra):
    with pytest.raises(ValueError, match="models.json"):
        load(tmp_path, [row("v/m@lean", **extra)])


def test_a_variant_written_back_as_a_row_is_refused(tmp_path):
    registry = load(tmp_path, [row("v/m", variants={"lean": {}})])
    rows = [dataclasses.asdict(m) for m in registry.models]
    with pytest.raises(ValueError, match="models.json"):
        load(tmp_path, rows)
    assert [m.id for m in load(tmp_path, rows[:1]).models] == ["v/m"]


def test_the_packaged_registry_has_no_variant():
    raw = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))
    assert all("variants" not in r and "@" not in r["id"] for r in raw["models"])
    registry = Registry.load(DATA_DIR / "models.json")
    assert [m.id for m in registry.models] == [r["id"] for r in raw["models"]]
    assert all(m.variant is None and m.base_id == m.id for m in registry.models)


def _review_task(**overrides):
    fields = dict(name="review", bar=0.8, min_samples=30, expected_input_tokens=1000,
                  expected_output_tokens=200)
    fields.update(overrides)
    return Task(**fields)


def test_two_harnesses_of_one_model_the_cheaper_admitted_only_by_its_own_rows(tmp_path):
    registry = load(tmp_path, [row("v/m", variants={"lean": {"harness": "lean-agent 2.0"}})])
    task = _review_task()
    stats = Stats()
    stats.add("review", "v/m", 95, 100, input_tokens=400_000, output_tokens=40_000)
    router = Router(registry, {"review": task}, stats)
    cold = router.select("review")
    assert (cold.primary, cold.fallbacks) == ("v/m", ())
    assert reasons(cold) == {"v/m": PASSES, "v/m@lean": INSUFFICIENT_SAMPLES}
    lean_cold = next(c for c in cold.candidates if c.model_id == "v/m@lean")
    assert (lean_cold.trials, lean_cold.list_cost) == (0, pytest.approx(0.0014, abs=1e-15))
    assert stats.get("review", "v/m@lean") == (0, 0)

    lean_rows = [{"task": "review", "model": "v/m@lean", "correct": i >= 6,
                  "input_tokens": 1500, "output_tokens": 300} for i in range(100)]
    measured = stats.merge(calibrate_from_results(lean_rows))
    assert measured.get("review", "v/m") == (95, 100)
    assert measured.tokens("review", "v/m") == (400_000, 40_000, 100)
    assert measured.get("review", "v/m@lean") == (94, 100)
    router = Router(registry, {"review": task}, measured)
    cheap = router.select("review", "cost_effective")
    assert (cheap.primary, cheap.fallbacks) == ("v/m@lean", ("v/m",))
    costs = {c.model_id: c.list_cost for c in cheap.candidates}
    assert costs == {"v/m": pytest.approx(0.0048, abs=1e-15),
                     "v/m@lean": pytest.approx(0.0021, abs=1e-15)}
    blind = router.select("review", "cost_blind")
    assert (blind.primary, blind.fallbacks) == ("v/m", ("v/m@lean",))

    weak_rows = [dict(r, correct=i >= 30) for i, r in enumerate(lean_rows)]
    weak = Router(registry, {"review": task}, stats.merge(calibrate_from_results(weak_rows)))
    assert reasons(weak.select("review")) == {"v/m": PASSES, "v/m@lean": BELOW_BAR}


@pytest.fixture
def family_router(tmp_path):
    registry = load(tmp_path, [row("v/m", variants={"lean": {}, "deep": {}}), row("v/k"),
                               row("w/n", "w")])
    stats = Stats()
    for model in registry.models:
        stats.add("review", model.id, 30, 30)

    def make(**task_fields):
        task = _review_task(min_samples=30, **task_fields)
        return Router(registry, {"review": task}, stats)
    return make


V_ROUTES = ("v/m", "v/m@lean", "v/m@deep")


def test_excluding_a_base_excludes_its_variants_and_a_variant_only_itself(family_router):
    router = family_router()
    got = reasons(router.select("review", exclude_models=("v/m",)))
    assert got == {**{m: EXCLUDED_MODEL for m in V_ROUTES}, "v/k": PASSES, "w/n": PASSES}
    got = reasons(router.select("review", exclude_models=("v/m@lean",)))
    assert got == {"v/m": PASSES, "v/m@lean": EXCLUDED_MODEL, "v/m@deep": PASSES,
                   "v/k": PASSES, "w/n": PASSES}


@pytest.mark.parametrize("generator", V_ROUTES)
def test_the_generator_is_its_base_and_every_variant_of_it(family_router, generator):
    got = reasons(family_router().select("review", generator_model=generator))
    assert got == {**{m: GENERATOR for m in V_ROUTES}, "v/k": GENERATOR_FAMILY, "w/n": PASSES}
    off = family_router(independent_of_generator=False)
    assert set(reasons(off.select("review", generator_model=generator)).values()) == {PASSES}


def test_a_sibling_generator_reaches_the_variants_by_family(family_router):
    got = reasons(family_router().select("review", generator_model="v/k"))
    assert got == {**{m: GENERATOR_FAMILY for m in V_ROUTES}, "v/k": GENERATOR, "w/n": PASSES}


def test_family_exclusion_and_the_window_apply_to_variants(family_router, tmp_path):
    got = reasons(family_router(exclude_families=("v",)).select("review"))
    assert got == {**{m: EXCLUDED_FAMILY for m in V_ROUTES}, "v/k": EXCLUDED_FAMILY,
                   "w/n": PASSES}
    small = load(tmp_path, [row("v/m", context_window=1100, variants={"lean": {}}),
                            row("w/n", "w")])
    stats = Stats()
    for model in small.models:
        stats.add("review", model.id, 30, 30)
    got = reasons(Router(small, {"review": _review_task()}, stats).select("review"))
    assert got == {"v/m": CONTEXT_TOO_SMALL, "v/m@lean": CONTEXT_TOO_SMALL, "w/n": PASSES}


def test_a_cascade_member_is_judged_by_the_base_rules_and_is_never_a_variant(tmp_path):
    with pytest.raises(ValueError):
        Cascade("v/m@lean", "w/n", "sig")
    registry = load(tmp_path, [row("v/m", variants={"lean": {}}), row("w/n", "w")])
    stats = Stats()
    for model in registry.models:
        stats.add("review", model.id, 30, 30)
    task = _review_task(cascades=(Cascade("v/m", "w/n", "sig"),))
    router = Router(registry, {"review": task}, stats)
    got = reasons(router.select("review", generator_model="v/m@lean", cascades=True))
    assert got == {"v/m": GENERATOR, "v/m@lean": GENERATOR, "w/n": PASSES,
                   "v/m>w/n@sig": GENERATOR}
    got = reasons(router.select("review", exclude_models=("v/m",), cascades=True))
    assert got == {"v/m": EXCLUDED_MODEL, "v/m@lean": EXCLUDED_MODEL, "w/n": PASSES,
                   "v/m>w/n@sig": EXCLUDED_MODEL}


@pytest.mark.parametrize("parent, generator", [("v/m@lean", "v/m"), ("v/m", "v/m@lean")])
def test_the_inline_check_refuses_a_parent_that_is_the_generator_s_setup(family_router, parent,
                                                                         generator):
    decision = family_router().decide_delegation(
        "review", parent, generator_model=generator, context_tokens=1000, brief_tokens=100,
        result_tokens=50)
    assert (decision.inline_allowed, decision.mode, decision.model) == (False, "delegate", "w/n")


def test_the_executor_calls_and_logs_the_route_id(tmp_path):
    registry = load(tmp_path, [row("v/m", variants={"lean": {"harness": "lean-agent 2.0"}})])
    stats = Stats()
    stats.add("review", "v/m@lean", 30, 30)
    router = Router(registry, {"review": _review_task()}, stats)
    seen = []
    provider = FakeProvider(
        {"v/m@lean": lambda messages: seen.append(1) or Completion("ok", 10, 2)})
    monitor = Monitor()
    result = Executor(router, provider, monitor=monitor).call(
        "review", [{"role": "user", "content": "x"}])
    assert (result.model, seen, [r["model"] for r in monitor.records]) == (
        "v/m@lean", [1], ["v/m@lean"])


def test_the_readme_names_the_variants_key():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    part = text.split("## How a model is chosen", 1)[1].split("\n## ", 1)[0]
    assert '"variants": {"lean": {"harness": "lean-agent 2.0", "reasoning_effort": "low"}}' in part
    assert "`vendor/model@lean`" in part and "`DESIGN.md` 4.1 and 5.2" in part
    assert "map each route in `OpenAICompatibleProvider(model_map=...)`" in part


def test_the_production_note_states_the_shipped_part_of_measured_setups():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert "pool into one success rate and one mean cost. The change: route a measured" not in text
    assert "once the measured-setup change lands" not in text
    assert ("- In this library: a registry row can name variants of its model, such as an effort "
            "or a harness, and each is a route of its own, `vendor/model@variant`, with its own "
            "stats, so today the runs of one model at two efforts or in two harnesses no longer "
            "pool into one success rate and one mean cost.") in text
    assert ("The change still planned: the provider options a variant passes on each call."
            ) in text  # v1.573: items per call shipped (tests/test_items_per_call.py)
