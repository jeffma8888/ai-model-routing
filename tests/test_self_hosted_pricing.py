"""Self-hosted pricing: a registry row priced from an hour of your own serving (DESIGN 4.1 and 9 v1.581, row SELF1a)."""

import dataclasses
import json
import math
from pathlib import Path

import pytest

import model_routing
from model_routing import (BELOW_BAR, DATA_DIR, PASSES, Model, PriceTier, Registry, Router, Stats, Task,
                           Variant)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "model_routing"
HOUR = {"usd_per_hour": 10, "tokens_per_hour_in": 36_000_000, "tokens_per_hour_out": 2_000_000,
        "utilization": 0.5, "input_cost_share": 0.5}
KEYS = tuple(HOUR)


def prices(**overrides):
    return model_routing.self_hosted_prices(**dict(HOUR, **overrides))


def hosted_row(model_id="acme/ft-7b", **extra):
    row = dict({"id": model_id, "family": "acme", "context_window": 32_000,
                "pricing_basis": "self_hosted"}, **HOUR)
    row.update(extra)
    return row


def list_row(model_id="v/m", **extra):
    return dict({"id": model_id, "family": "v", "price_in": 1.0, "price_out": 2.0,
                 "context_window": 100_000}, **extra)


def load(tmp_path, rows):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": rows}), encoding="utf-8")
    return Registry.load(path)


def test_the_function_is_exported_right_after_variant():
    from model_routing.registry import self_hosted_prices as inner
    names = list(model_routing.__all__)
    assert names[names.index("Variant") + 1] == "self_hosted_prices"
    assert model_routing.self_hosted_prices is inner


def test_the_row_example_gives_the_two_prices():
    price_in, price_out = prices()
    assert round(price_in, 4) == 0.2778
    assert price_in == pytest.approx(10 * 0.5 / (36_000_000 * 0.5) * 1_000_000, rel=1e-12)
    assert price_out == pytest.approx(5.0, rel=1e-12)
    assert isinstance(price_in, float) and isinstance(price_out, float)


def test_the_hour_is_charged_once():
    price_in, price_out = prices()
    model = Model("acme/ft-7b", "acme", price_in, price_out, 32_000, pricing_basis="self_hosted")
    used_in, used_out = 36_000_000 * 0.5, 2_000_000 * 0.5
    assert (used_in * price_in + used_out * price_out) / 1_000_000 == pytest.approx(10.0, rel=1e-12)
    assert model.cost(18_000_000, 0) == pytest.approx(5.0, rel=1e-12)
    assert model.cost(0, 1_000_000) == pytest.approx(5.0, rel=1e-12)


@pytest.mark.parametrize("share, expected", [(0, (0.0, 5.0)), (1, (10 / 36, 0.0))])
def test_a_share_at_either_end_charges_the_hour_to_one_side(share, expected):
    got = prices(input_cost_share=share, utilization=1)
    assert got == pytest.approx(expected, rel=1e-12, abs=0.0)
    assert got[share] == 0.0


def test_a_free_hour_is_free_and_full_use_is_allowed():
    assert prices(usd_per_hour=0) == (0.0, 0.0)
    full = prices(utilization=1)
    assert full == pytest.approx((10 * 0.5 / 36, 10 * 0.5 / 2), rel=1e-12)


@pytest.mark.parametrize("name, value", [
    ("usd_per_hour", -0.01), ("usd_per_hour", math.inf), ("usd_per_hour", math.nan), ("usd_per_hour", True),
    ("usd_per_hour", "10"), ("usd_per_hour", None),
    ("tokens_per_hour_in", 0), ("tokens_per_hour_in", -1), ("tokens_per_hour_in", math.inf),
    ("tokens_per_hour_out", 0), ("tokens_per_hour_out", False),
    ("utilization", 0), ("utilization", 1.0001), ("utilization", -0.5), ("utilization", math.nan),
    ("input_cost_share", -0.0001), ("input_cost_share", 1.0001), ("input_cost_share", True),
])
def test_each_argument_is_checked_and_named(name, value):
    with pytest.raises(ValueError, match=name):
        prices(**{name: value})


@pytest.mark.parametrize("name", KEYS)
@pytest.mark.parametrize("value", [True, False, math.nan, math.inf, -math.inf, "1", None, 10 ** 400])
def test_every_argument_refuses_every_non_number(name, value):
    # review iter-428 should-fix 2: each argument crossed with each kind; 10 ** 400 is an int too
    # large for a float
    with pytest.raises(ValueError, match=name):
        prices(**{name: value})


@pytest.mark.parametrize("overrides, price", [
    ({"usd_per_hour": 1e308, "tokens_per_hour_in": 1, "tokens_per_hour_out": 1, "utilization": 1},
     "price_in"),
    ({"tokens_per_hour_in": 5e-324}, "price_in"),
    ({"tokens_per_hour_out": 1e-320, "utilization": 1}, "price_out"),
])
def test_a_derived_price_that_is_not_finite_is_refused(tmp_path, overrides, price):
    # review iter-428 must-fix 2: each input is in its range, but the price could never rank
    with pytest.raises(ValueError, match=f"derived {price} is not a finite number"):
        prices(**overrides)
    with pytest.raises(ValueError, match=f"models.json.*derived {price}"):
        load(tmp_path, [hosted_row(**overrides)])


@pytest.mark.parametrize("row", [None, 3, "bad", [], ["v/m"]])
def test_a_row_that_is_not_an_object_names_the_file(tmp_path, row):
    # review iter-428 must-fix 1: as before v1.581, never an AttributeError
    with pytest.raises(ValueError, match="models.json.*invalid model row"):
        load(tmp_path, [list_row(), row])


def test_a_model_is_list_priced_by_default_and_the_field_follows_variant():
    model = Model("v/m", "v", 1.0, 2.0, 100_000)
    assert model.pricing_basis == "list"
    # the last field until v1.582 adds `deployment` and `base_model` after it (DESIGN 4.1)
    assert [f.name for f in dataclasses.fields(Model)][-4:] == ["variant", "pricing_basis", "deployment",
                                                                "base_model"]
    assert list(dataclasses.asdict(model))[-3] == "pricing_basis"
    assert dataclasses.asdict(model)["pricing_basis"] == "list"


@pytest.mark.parametrize("basis", ["", "self-hosted", "api", "LIST", None, 1])
def test_a_basis_is_list_or_self_hosted(basis):
    with pytest.raises(ValueError, match="pricing_basis"):
        Model("v/m", "v", 1.0, 2.0, 100_000, pricing_basis=basis)


def test_a_self_hosted_model_holds_no_price_tiers():
    tier = PriceTier(50_000, 2.0, 4.0)
    Model("v/m", "v", 1.0, 2.0, 100_000, price_tiers=(tier,))
    with pytest.raises(ValueError, match="tier"):
        Model("v/m", "v", 1.0, 2.0, 100_000, price_tiers=(tier,), pricing_basis="self_hosted")


def test_a_self_hosted_row_gets_the_derived_prices(tmp_path):
    registry = load(tmp_path, [list_row(), hosted_row(price_valid_until="2027-06-30")])
    hosted = registry.get("acme/ft-7b")
    assert (hosted.price_in, hosted.price_out) == prices()
    assert hosted.pricing_basis == "self_hosted"
    assert (hosted.family, hosted.context_window, hosted.price_valid_until) == ("acme", 32_000, "2027-06-30")
    assert hosted.price_tiers == ()
    assert registry.get("v/m").pricing_basis == "list"


@pytest.mark.parametrize("basis", [None, "list"])
def test_an_absent_null_or_list_basis_is_a_list_row(tmp_path, basis):
    row = list_row() if basis is None else list_row(pricing_basis=basis)
    plain = load(tmp_path, [list_row()]).get("v/m")
    assert load(tmp_path, [row]).get("v/m") == plain
    assert load(tmp_path, [list_row(pricing_basis=None)]).get("v/m") == plain


@pytest.mark.parametrize("key", KEYS)
def test_a_self_hosted_row_missing_a_key_is_refused(tmp_path, key):
    row = hosted_row()
    del row[key]
    with pytest.raises(ValueError, match=f"models.json.*{key}"):
        load(tmp_path, [row])
    with pytest.raises(ValueError, match=f"models.json.*{key}"):
        load(tmp_path, [hosted_row(**{key: None})])


@pytest.mark.parametrize("extra", [{"price_in": 1.0}, {"price_out": 2.0}, {"price_tiers": []},
                                   {"price_in": 1.0, "price_out": 2.0}, {"price_in": None},
                                   {"price_out": None}, {"price_tiers": None}])  # None: should-fix 1
def test_a_self_hosted_row_states_no_list_price(tmp_path, extra):
    with pytest.raises(ValueError, match="models.json.*takes no price_in, price_out or price_tiers"):
        load(tmp_path, [hosted_row(**extra)])


@pytest.mark.parametrize("key", KEYS)
def test_a_list_row_naming_an_hourly_key_is_refused(tmp_path, key):
    for value in (None, 0):  # review iter-428 should-fix 1: the key's presence, whatever its value
        with pytest.raises(ValueError, match=f"models.json.*{key}.*pricing_basis"):
            load(tmp_path, [list_row(**{key: value})])
    with pytest.raises(ValueError, match=f"models.json.*{key}.*pricing_basis"):
        load(tmp_path, [list_row(**{key: HOUR[key]})])
    with pytest.raises(ValueError, match=f"models.json.*{key}.*pricing_basis"):
        load(tmp_path, [list_row(pricing_basis="list", **{key: HOUR[key]})])


@pytest.mark.parametrize("basis", ["gpu", "", 3, "Self_Hosted"])
def test_an_unknown_basis_on_a_row_is_refused(tmp_path, basis):
    with pytest.raises(ValueError, match="models.json.*pricing_basis"):
        load(tmp_path, [list_row(pricing_basis=basis)])


@pytest.mark.parametrize("name, value", [("utilization", 0), ("utilization", 2), ("input_cost_share", 1.5),
                                         ("tokens_per_hour_in", 0), ("usd_per_hour", -1),
                                         ("usd_per_hour", True), ("usd_per_hour", "10")])
def test_a_refused_hour_value_on_a_row_names_the_file(tmp_path, name, value):
    with pytest.raises(ValueError, match=f"models.json.*{name}"):
        load(tmp_path, [hosted_row(**{name: value})])


def test_the_variants_of_a_self_hosted_row_keep_its_basis_and_prices(tmp_path):
    registry = load(tmp_path, [hosted_row(variants={"batch8": {"items_per_call": 8}})])
    base, variant = registry.models
    assert variant.id == "acme/ft-7b@batch8"
    assert (variant.pricing_basis, variant.price_in, variant.price_out) == (
        "self_hosted", base.price_in, base.price_out)


def test_a_list_model_round_trips_and_a_self_hosted_one_is_refused(tmp_path):
    registry = load(tmp_path, [list_row(price_tiers=[{"above_input_tokens": 50_000, "price_in": 2.0,
                                                      "price_out": 4.0}]), hosted_row()])
    listed, hosted = registry.models
    back = load(tmp_path, [dataclasses.asdict(listed)])
    assert back.models == (listed,)
    with pytest.raises(ValueError, match="models.json.*takes no price_in, price_out or price_tiers"):
        load(tmp_path, [dataclasses.asdict(hosted)])


def test_a_self_hosted_model_is_routed_by_its_measured_success_at_its_derived_price(tmp_path):
    registry = load(tmp_path, [list_row("v/m"), hosted_row()])
    task = Task(name="review", bar=0.8, min_samples=30, expected_input_tokens=1000,
                expected_output_tokens=200)
    stats = Stats()
    stats.add("review", "v/m", 95, 100)
    stats.add("review", "acme/ft-7b", 95, 100)
    picked = Router(registry, {"review": task}, stats).select("review", "cost_effective")
    assert (picked.primary, picked.fallbacks) == ("acme/ft-7b", ("v/m",))
    price_in, price_out = prices()
    costs = {c.model_id: c.list_cost for c in picked.candidates}
    assert costs["acme/ft-7b"] == pytest.approx((1000 * price_in + 200 * price_out) / 1_000_000, rel=1e-12)
    weak = Stats()
    weak.add("review", "v/m", 95, 100)
    weak.add("review", "acme/ft-7b", 60, 100)
    below = Router(registry, {"review": task}, weak).select("review", "cost_effective")
    assert below.primary == "v/m"
    assert {c.model_id: c.reason for c in below.candidates} == {"v/m": PASSES, "acme/ft-7b": BELOW_BAR}


def test_every_packaged_row_is_list_priced():
    registry = Registry.load(DATA_DIR / "models.json")
    assert {m.pricing_basis for m in registry.models} == {"list"}
    raw = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))
    assert not any(key in row for row in raw["models"] for key in KEYS + ("pricing_basis",))


def test_only_the_registry_reads_the_basis_yet():
    # v1.581 (row SELF1a): selection, execution, records and reports read price_in and price_out
    # as for any model; v1.584 (row SELF1c): the router, executor, report and CLI also name the
    # basis in candidates, records, report groups and the select table, and no other module does
    naming = {path.name for path in PACKAGE.glob("*.py")
              if any(word in path.read_text(encoding="utf-8")
                     for word in ("pricing_basis", "self_hosted"))}
    assert naming == {"registry.py", "__init__.py", "router.py", "executor.py", "monitor.py",
                      "cli.py"}


def test_the_production_note_says_the_hourly_row_ships():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert "a model is a registry row priced from a vendor's list price" not in text
    assert "planned in the Harvey lesson on your own trained model, is the form such a price would take" not in text
    assert "so a hosted 7B model has no price of its own" not in text
    assert ("for a model you host, `pricing_basis` `self_hosted` derives its prices from your own hourly cost, "
            "throughput and utilization") in text
    assert "The change still planned: a task scope, so a model built for some tasks is never a candidate on others" in text
    assert "a hosted 7B model can be a registry row priced from your own hourly cost and throughput" in text
    assert "capacity you pay for by the hour can enter as a row priced from that hourly cost" in text


def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four = design[design.index("### 4.1 "):design.index("### 4.2 ")]
    assert four.count("- v1.581 self-hosted pricing (row SELF1a): `Model` gains a last field, `pricing_basis") == 1
    assert four.count("- v1.581 `Registry.load` reads the optional `pricing_basis` key of a row") == 1
    assert "0.2778 and 5.0 to four places" in four
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.581 (")]
    assert len(mine) == 1 and "(4.1, 9, row SELF1a)" in mine[0]
