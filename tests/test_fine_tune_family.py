"""A fine-tune is its base's family: `deployment` and `base_model` (DESIGN 4.1, 5.2, 9 and 13.4 v1.582, row SELF1b)."""

import dataclasses
import json
from pathlib import Path

import pytest

from model_routing import (DATA_DIR, EXCLUDED_FAMILY, GENERATOR, GENERATOR_FAMILY, PASSES, Model, Registry,
                           Router, Stats, Task, Variant)
from model_routing.delegation import PARENT_EXCLUDED_FAMILY, PARENT_NOT_INDEPENDENT

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "model_routing"
TASK = "grade"


def base():
    return Model("v/base", "v", 1.0, 2.0, 100_000)


def tune(**extra):
    return Model("acme/ft", extra.pop("family", "v"), 0.1, 0.2, 100_000, **dict({"base_model": "v/base"}, **extra))


def other_family():
    return Model("w/judge", "w", 3.0, 6.0, 100_000)


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


def row(model_id, family="v", **extra):
    out = {"id": model_id, "price_in": 1.0, "price_out": 2.0, "context_window": 100_000}
    if family is not None:
        out["family"] = family
    out.update(extra)
    return out


def test_the_two_fields_follow_pricing_basis():
    names = [f.name for f in dataclasses.fields(Model)]
    assert names[-3:] == ["pricing_basis", "deployment", "base_model"]
    assert list(dataclasses.asdict(base()))[-2:] == ["deployment", "base_model"]


def test_a_list_model_runs_at_an_api_and_a_self_hosted_one_where_its_owner_serves_it():
    plain = base()
    assert (plain.deployment, plain.base_model) == ("api", None)
    hosted = Model("acme/ft", "v", 0.1, 0.2, 100_000, pricing_basis="self_hosted")
    assert hosted.deployment == "self_hosted"
    assert dataclasses.asdict(hosted)["deployment"] == "self_hosted"
    assert Model("v/base", "v", 1.0, 2.0, 100_000, deployment="self_hosted").deployment == "self_hosted"
    assert Model("v/base", "v", 1.0, 2.0, 100_000, pricing_basis="self_hosted",
                 deployment="api").deployment == "api"
    assert base() == Model("v/base", "v", 1.0, 2.0, 100_000, deployment="api", base_model=None)


@pytest.mark.parametrize("value", ["cloud", "", "API", 1, True, ["api"]])
def test_a_deployment_is_api_or_self_hosted(value):
    with pytest.raises(ValueError, match="deployment"):
        Model("v/base", "v", 1.0, 2.0, 100_000, deployment=value)


@pytest.mark.parametrize("value", ["", 1, True, ["v/base"]])
def test_a_base_model_is_none_or_a_non_empty_string(value):
    with pytest.raises(ValueError, match="base_model"):
        Model("acme/ft", "v", 0.1, 0.2, 100_000, base_model=value)


def test_a_fine_tune_of_a_registry_model_is_accepted_before_or_after_its_base():
    for models in ([base(), tune()], [tune(), base()]):
        registry = Registry(models)
        assert registry.get("acme/ft").base_model == "v/base"


@pytest.mark.parametrize("models, message", [
    (lambda: [tune()], "is not a model of this registry"),
    (lambda: [Model("v/base", "v", 1.0, 2.0, 100_000, base_model="v/base")], "names itself"),
    (lambda: [base(), Model("v/base@high", "v", 1.0, 2.0, 100_000, variant=Variant("high")),
              tune(base_model="v/base@high")], "is a variant"),
    (lambda: [base(), Model("acme/mid", "v", 0.5, 1.0, 100_000, base_model="v/base"),
              tune(base_model="acme/mid")], "names a base_model itself"),
    (lambda: [base(), tune(family="acme")], "its base's family"),
], ids=["missing", "itself", "variant", "chained", "other-family"])
def test_a_missing_own_variant_chained_or_other_family_base_is_refused(models, message):
    built = models()  # built inside the test, so the red run collects
    with pytest.raises(ValueError, match=message):
        Registry(built)


def test_a_variant_of_its_own_fine_tune_is_not_its_own_base():
    variant = Model("acme/ft@high", "v", 0.1, 0.2, 100_000, variant=Variant("high"), base_model="acme/ft")
    with pytest.raises(ValueError, match="names itself"):
        Registry([base(), tune(), variant])


def test_a_fine_tune_cannot_judge_its_base_familys_output():
    models = [base(), tune(), other_family()]
    picked = router(models).select(TASK, "cost_effective", generator_model="v/base")
    reasons = {c.model_id: c.reason for c in picked.candidates}
    assert reasons == {"v/base": GENERATOR, "acme/ft": GENERATOR_FAMILY, "w/judge": PASSES}
    assert (picked.primary, picked.fallbacks) == ("w/judge", ())
    # the same fine-tune under a family of its owner's naming and no base would be picked
    loose = router([base(), Model("acme/ft", "acme", 0.1, 0.2, 100_000), other_family()])
    assert loose.select(TASK, "cost_effective", generator_model="v/base").primary == "acme/ft"


def test_a_base_cannot_judge_its_fine_tunes_output_nor_a_fine_tune_its_familys():
    models = [base(), tune(), Model("v/other", "v", 2.0, 4.0, 100_000), other_family()]
    on_tune = router(models).select(TASK, "cost_effective", generator_model="acme/ft")
    assert {c.model_id: c.reason for c in on_tune.candidates} == {
        "v/base": GENERATOR_FAMILY, "acme/ft": GENERATOR, "v/other": GENERATOR_FAMILY, "w/judge": PASSES}
    on_other = router(models).select(TASK, "cost_effective", generator_model="v/other")
    assert {c.model_id: c.reason for c in on_other.candidates}["acme/ft"] == GENERATOR_FAMILY
    assert on_other.primary == "w/judge"


def test_excluding_the_base_family_excludes_the_fine_tune():
    picked = router([base(), tune(), other_family()], exclude_families=("v",)).select(TASK, "cost_effective")
    assert {c.model_id: c.reason for c in picked.candidates} == {
        "v/base": EXCLUDED_FAMILY, "acme/ft": EXCLUDED_FAMILY, "w/judge": PASSES}


def _delegate(models, parent, generator, **task_extra):
    return router(models, **task_extra).decide_delegation(
        TASK, parent, "cost_effective", context_tokens=2000, brief_tokens=300, result_tokens=200,
        generator_model=generator)


def test_the_delegation_parent_check_reads_a_fine_tune_as_its_base_family():
    models = [base(), tune(), other_family()]
    on_base = _delegate(models, "acme/ft", "v/base")
    assert (on_base.mode, on_base.reason, on_base.inline_allowed) == ("delegate", PARENT_NOT_INDEPENDENT, False)
    assert on_base.model == "w/judge"
    on_tune = _delegate(models, "v/base", "acme/ft")
    assert (on_tune.mode, on_tune.reason) == ("delegate", PARENT_NOT_INDEPENDENT)
    excluded = _delegate(models, "acme/ft", None, exclude_families=("v",))
    assert (excluded.mode, excluded.reason) == ("delegate", PARENT_EXCLUDED_FAMILY)


def test_a_fine_tune_row_may_leave_out_its_family_and_gets_its_bases(tmp_path):
    for family in (None, "absent"):
        tuned = row("acme/ft", family=None, base_model="v/base", deployment="self_hosted")
        if family is None:
            tuned["family"] = None
        registry = load(tmp_path, [tuned, row("v/base")])
        model = registry.get("acme/ft")
        assert (model.family, model.base_model, model.deployment) == ("v", "v/base", "self_hosted")
        assert registry.get("v/base").deployment == "api"


@pytest.mark.parametrize("rows, message", [
    ([row("acme/ft", family=None, base_model="v/nope")], "models.json.*is not a row of this file"),
    ([row("acme/mid", family=None, base_model="acme/ft"), row("acme/ft", family=None, base_model="acme/mid")],
     "models.json.*states no family"),
    ([row("v/base"), row("acme/ft", family="acme", base_model="v/base")], "models.json.*its base's family"),
    ([row("acme/ft", base_model="v/nope")], "models.json.*is not a model of this registry"),
    ([row("v/base"), row("v/base")], "models.json.*duplicate model id"),
    ([row("v/base", deployment="cloud")], "models.json.*deployment"),
])
def test_a_refused_row_or_registry_names_the_file(tmp_path, rows, message):
    with pytest.raises(ValueError, match=message):
        load(tmp_path, rows)


def test_the_variants_of_a_fine_tune_row_keep_its_base_and_deployment(tmp_path):
    registry = load(tmp_path, [row("v/base"), row("acme/ft", family=None, base_model="v/base",
                                                  deployment="self_hosted", variants={"high": {}})])
    variant = registry.get("acme/ft@high")
    assert (variant.family, variant.base_model, variant.deployment) == ("v", "v/base", "self_hosted")


def test_a_list_priced_fine_tune_round_trips_through_asdict(tmp_path):
    registry = load(tmp_path, [row("v/base"), row("acme/ft", family=None, base_model="v/base",
                                                  deployment="self_hosted")])
    back = load(tmp_path, [dataclasses.asdict(m) for m in registry.models])
    assert back.models == registry.models


def test_the_packaged_registry_is_api_with_no_base():
    registry = Registry.load(DATA_DIR / "models.json")
    assert {(m.deployment, m.base_model) for m in registry.models} == {("api", None)}


def test_no_packaged_row_names_the_keys():
    raw = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))
    assert not any(key in r for r in raw["models"] for key in ("deployment", "base_model"))


def test_explicit_defaults_load_as_the_packaged_models(tmp_path):
    raw = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))
    explicit = [dict(r, deployment="api", base_model=None) for r in raw["models"]]
    assert load(tmp_path, explicit).models == Registry.load(DATA_DIR / "models.json").models


def test_only_the_registry_reads_the_keys_yet():
    # v1.582 (row SELF1b): routing, delegation, execution, records and reports read `family`
    # as before, so without the keys every decision is v1.581's; SELF1c and SELF1d may name them
    for path in sorted(PACKAGE.glob("*.py")):
        if path.name == "registry.py":
            continue
        text = path.read_text(encoding="utf-8")
        assert "base_model" not in text and "deployment" not in text, path.name


def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four = design[design.index("### 4.1 "):design.index("### 4.2 ")]
    assert four.count("- v1.582 deployment and base (row SELF1b): `Model` gains two last fields") == 1
    assert four.count("- v1.582 `Registry.load` reads the optional `deployment` and `base_model` keys") == 1
    five = design[design.index("### 5.2 "):design.index("### 5.3 ")]
    assert five.count("- v1.582 fine-tunes (row SELF1b): rules 2 and 4 read a fine-tune's `family`") == 1
    thirteen = design[design.index("### 13.4 "):design.index("### 13.5 ")]
    assert thirteen.count("- v1.582 fine-tunes (row SELF1b): rules 1 and 2 read the parent's") == 1
    nine = design[design.index("## 9. "):design.index("## 10. ")]
    assert nine.count("- v1.582 `deployment` and `base_model` (format in 4.1, row SELF1b) are optional") == 1
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.582 (")]
    assert len(mine) == 1 and "(4.1, 5.2, 9, 13.4, row SELF1b)" in mine[0]
