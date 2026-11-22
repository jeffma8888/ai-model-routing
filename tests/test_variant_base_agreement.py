"""A variant agrees with its base model (DESIGN 4.1 and 5.2 v1.583, row VAR2, review iter-429 should-fix 4)."""

import dataclasses
import json
import re
from pathlib import Path

import pytest

from model_routing import (CONTEXT_TOO_SMALL, DATA_DIR, GENERATOR_FAMILY, PASSES, Model, PriceTier, Registry,
                           Router, Stats, Task, Variant)

ROOT = Path(__file__).resolve().parents[1]
TASK = "grade"
TAIL = "; a variant has its base's family, pricing_basis, deployment and base_model"


def base():
    return Model("v/base", "v", 1.0, 2.0, 100_000)


def tune():
    return Model("acme/ft", "v", 0.1, 0.2, 100_000, base_model="v/base")


def other_family():
    return Model("w/judge", "w", 3.0, 6.0, 100_000)


def variant_of(model, name="high", **change):
    """A variant built directly from its base model, with the changed fields alone differing."""
    change.setdefault("aliases", dict(model.aliases))
    return dataclasses.replace(model, id=f"{model.id}@{name}", variant=Variant(name), **change)


def router(models, **task_extra):
    task = Task(name=TASK, bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200,
                independent_of_generator=True, **task_extra)
    stats = Stats()
    for model in models:
        stats.add(TASK, model.id, 95, 100)
    return Router(Registry(models), {TASK: task}, stats)


def load(tmp_path, rows):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": rows}), encoding="utf-8")
    return Registry.load(path)


@pytest.mark.parametrize("models, differs", [
    (lambda: [base(), variant_of(base(), family="w")], "family 'w' (its base's 'v')"),
    (lambda: [base(), variant_of(base(), pricing_basis="self_hosted")],
     "pricing_basis 'self_hosted' (its base's 'list')"),
    (lambda: [base(), variant_of(base(), deployment="self_hosted")], "deployment 'self_hosted' (its base's 'api')"),
    # review iter-431 nit 2: two fields at once, pricing_basis named before deployment
    (lambda: [base(), variant_of(base(), pricing_basis="self_hosted", deployment="self_hosted")],
     "pricing_basis 'self_hosted' (its base's 'list'), deployment 'self_hosted' (its base's 'api')"),
    (lambda: [base(), tune(), variant_of(tune(), base_model=None)], "base_model None (its base's 'v/base')"),
    (lambda: [base(), Model("v/other", "v", 2.0, 4.0, 100_000),
              variant_of(Model("v/other", "v", 2.0, 4.0, 100_000), base_model="v/base")],
     "base_model 'v/base' (its base's None)"),
], ids=["family", "pricing_basis", "deployment", "basis-and-deployment", "base_model-dropped", "base_model-added"])
def test_a_variant_that_differs_from_its_base_in_one_checked_field_is_refused(models, differs):
    built = models()  # built inside the test, so the red run collects
    variant = built[-1]
    message = f"variant {variant.id!r} differs from its base model {variant.base_id!r} in {differs}{TAIL}"
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        Registry(built)


def test_the_reviewer_probe_is_refused_naming_each_field_in_order():
    # review iter-429 should-fix 4: this registry routed acme/ft@high as the primary judge of v/base
    probe = Model("acme/ft@high", "acme", 0.1, 0.2, 100_000, variant=Variant("high"))
    with pytest.raises(ValueError) as caught:
        Registry([base(), tune(), probe, other_family()])
    assert str(caught.value) == ("variant 'acme/ft@high' differs from its base model 'acme/ft' in family 'acme' "
                                 "(its base's 'v'), base_model None (its base's 'v/base')" + TAIL)


def test_the_first_differing_variant_in_registry_order_is_named():
    x_model = Model("x/m", "x", 1.0, 2.0, 100_000)
    built = [x_model, base(), variant_of(base(), family="w"), variant_of(x_model, family="w")]
    with pytest.raises(ValueError, match="^variant 'v/base@high' differs"):
        Registry(built)
    with pytest.raises(ValueError, match="^variant 'x/m@high' differs"):
        Registry([built[0], built[1], built[3], built[2]])
    # review iter-431 nit 1: a base later in the order than its variant is still its base
    with pytest.raises(ValueError, match="^variant 'v/base@high' differs from its base model 'v/base' in family"):
        Registry([variant_of(base(), family="w"), base()])


@pytest.mark.parametrize("models, message", [
    (lambda: [base(), variant_of(base(), family="w"), variant_of(base(), family="w")],
     "duplicate model id: 'v/base@high'"),
    (lambda: [base(), variant_of(base(), family="w", base_model="v/nope")],
     "base_model 'v/nope' of 'v/base@high' is not a model of this registry"),
    (lambda: [base(), tune(), variant_of(tune(), family="acme", base_model="acme/ft")],
     "model 'acme/ft@high' names itself as its base_model"),
], ids=["duplicate-first", "missing-base-model-next", "itself-next"])
def test_the_duplicate_and_base_checks_come_first(models, message):
    built = models()
    with pytest.raises(ValueError, match=f"^{re.escape(message)}$"):
        Registry(built)


def test_a_variant_whose_base_is_not_in_the_registry_is_not_checked():
    # v1.572 lets a caller route a variant alone, as tests/test_items_per_call.py does with v/d@batch4
    alone = Model("v/d@batch4", "anything", 1.0, 4.0, 100_000, variant=Variant("batch4", items_per_call=4),
                  pricing_basis="self_hosted")
    registry = Registry([base(), alone])
    assert registry.get("v/d@batch4").family == "anything"


def test_a_directly_built_variants_prices_window_and_aliases_stay_free():
    long = variant_of(base(), name="long", price_in=2.0, price_out=4.0, context_window=1_000_000,
                      price_tiers=(PriceTier(200_000, 3.0, 6.0),), price_valid_until="2026-12-31",
                      aliases={"p": "v-base-long"})
    registry = Registry([base(), long])
    assert registry.get("v/base@long") == long
    # 5.2 rule 5 reads the variant's own window: a 150,000-token prompt fits it, not its base
    picked = router([base(), long]).select(TASK, "cost_effective", prompt_tokens=150_000)
    reasons = {c.model_id: c.reason for c in picked.candidates}
    assert reasons == {"v/base": CONTEXT_TOO_SMALL, "v/base@long": PASSES}


def test_a_variant_with_its_bases_fields_judges_as_its_base_family():
    # the probe with the base's family and base_model, as Registry.load writes it
    agreeing = variant_of(tune())
    picked = router([base(), tune(), agreeing, other_family()]).select(TASK, "cost_effective",
                                                                       generator_model="v/base")
    reasons = {c.model_id: c.reason for c in picked.candidates}
    assert reasons["acme/ft@high"] == GENERATOR_FAMILY
    assert (picked.primary, picked.fallbacks) == ("w/judge", ())
    without = router([base(), tune(), other_family()]).select(TASK, "cost_effective", generator_model="v/base")
    assert [c for c in picked.candidates if c.model_id != "acme/ft@high"] == list(without.candidates)


def test_every_loaded_variant_passes(tmp_path):
    hour = {"usd_per_hour": 10.0, "tokens_per_hour_in": 36_000_000, "tokens_per_hour_out": 2_000_000,
            "utilization": 0.5, "input_cost_share": 0.5}
    rows = [
        {"id": "v/base", "family": "v", "price_in": 1.0, "price_out": 2.0, "context_window": 100_000,
         "price_tiers": [{"above_input_tokens": 50_000, "price_in": 2.0, "price_out": 4.0}],
         "aliases": {"p": "base"}, "variants": {"high": {"reasoning_effort": "high"}, "batch": {"items_per_call": 4}}},
        dict({"id": "own/m", "family": "own", "pricing_basis": "self_hosted", "context_window": 32_000,
              "variants": {"lean": {"harness": "agent 1"}}}, **hour),
        {"id": "acme/ft", "base_model": "v/base", "deployment": "self_hosted", "price_in": 0.1, "price_out": 0.2,
         "context_window": 100_000, "variants": {"high": {"provider_options": {"reasoning_effort": "high"}}}},
    ]
    registry = load(tmp_path, rows)
    assert [m.id for m in registry.models] == ["v/base", "v/base@high", "v/base@batch", "own/m", "own/m@lean",
                                               "acme/ft", "acme/ft@high"]
    assert Registry(registry.models).models == registry.models


@pytest.mark.parametrize("path", ["model_routing/data/models.json", "evidence/llmrouterbench-delegation/registry.json",
                                  "evidence/tau2-bench-delegation/registry.json",
                                  "evidence/response-bank-delegation/registry.json"])
def test_every_committed_registry_file_still_loads(path):
    registry = Registry.load(ROOT / path)
    assert Registry(registry.models).models == registry.models


def test_the_in_repo_directly_built_variants_still_pass():
    # tests/test_procedure_executor.py, tests/test_procedure_routing.py and tests/test_items_per_call.py
    cheap = Model("fiction/cheap", "fam-b", 0.1, 0.2, 10_000)
    Registry([cheap, Model("fiction/cheap@high", "fam-b", 0.1, 0.2, 10_000,
                           variant=Variant("high", provider_options={"reasoning_effort": "high"})),
              Model("fiction/best", "fam-c", 10.0, 30.0, 100_000)])
    Registry([Model("fiction/model", "fam-a", 1.0, 2.0, 10_000), cheap,
              Model("fiction/twin", "fam-b", 0.5, 1.0, 10_000), Model("fiction/narrow", "fam-c", 0.1, 0.2, 1_000),
              Model("fiction/cheap@high", "fam-b", 0.1, 0.2, 10_000, variant=Variant("high"))])
    for k in (4, 1):
        Registry([Model("v/p", "p", 3.0, 15.0, 100_000),
                  Model("v/d@batch4", "v", 1.0, 4.0, 100_000, variant=Variant("batch4", items_per_call=k))])


def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four = design[design.index("### 4.1 "):design.index("### 4.2 ")]
    assert four.count("- v1.583 a variant agrees with its base (row VAR2, review iter-429 should-fix 4)") == 1
    assert "does not yet check a directly built variant" not in four
    five = design[design.index("### 5.2 "):design.index("### 5.3 ")]
    assert five.count("from v1.583 `Registry` holds a variant to its base's family") == 1
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").rstrip("\n").split("\n")
    mine = [line for line in changelog if line.startswith("- v1.583 (")]
    assert len(mine) == 1
    assert mine[0].startswith("- v1.583 (2026-11-22): spec, code and tests (4.1, 5.2, row VAR2).")
