"""DESIGN 4.1 and 9 v1.587 (row CACHE1a): cache prices in the registry and in `Model.cost`.

`Model.price_cached_in` and `Model.price_cache_write` are USD per 1M input tokens read from and
written to the provider's prompt cache, `None` meaning the price is unknown and the call's input
price applies. `Model.cost` takes a call's cached reads and cache writes as two keyword-only counts
within `input_tokens`, so a write premium can make caching lose on one-shot work, and with both
counts 0 it is v1.586's cost bit for bit. No package module but the registry names them yet, so
every route, record, report, evidence file and README transcript keeps its bytes. The contract
tests were written under strict xfail and the implementing commit removed the marks; the unmarked
guards pin what v1.587 keeps and passed before and after it.
"""

import dataclasses
import json
import math
from pathlib import Path

import pytest

from model_routing import DATA_DIR, Model, PriceTier, Registry, Variant

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "model_routing"
NAMES = ("price_cached_in", "price_cache_write", "cached_input_tokens", "cache_write_tokens")


def cached(**extra):
    return Model("v/c", "v", 3.0, 15.0, 200_000, **dict({"price_cached_in": 0.3, "price_cache_write": 3.75},
                                                        **extra))


def _load(tmp_path, rows):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": rows}), encoding="utf-8")
    return Registry.load(path)


def _row(model_id, **extra):
    return dict({"id": model_id, "family": "v", "price_in": 3.0, "price_out": 15.0, "context_window": 200_000},
                **extra)


def _hour():
    return {"pricing_basis": "self_hosted", "usd_per_hour": 10, "tokens_per_hour_in": 36_000_000,
            "tokens_per_hour_out": 2_000_000, "utilization": 0.5, "input_cost_share": 0.5}


def test_the_two_prices_are_the_last_fields_and_default_to_unknown():
    names = [f.name for f in dataclasses.fields(Model)]
    assert names[-3:] == ["scope_tasks", "price_cached_in", "price_cache_write"]
    plain = Model("v/m", "v", 1.0, 2.0, 100_000)
    assert (plain.price_cached_in, plain.price_cache_write) == (None, None)
    assert list(dataclasses.asdict(plain))[-2:] == ["price_cached_in", "price_cache_write"]


def test_a_cache_price_is_stored_as_a_float():
    model = cached(price_cached_in=0, price_cache_write=4)
    assert (model.price_cached_in, model.price_cache_write) == (0.0, 4.0)
    assert type(model.price_cached_in) is float and type(model.price_cache_write) is float


@pytest.mark.parametrize("name", ["price_cached_in", "price_cache_write"])
@pytest.mark.parametrize("value", [True, False, "0.3", -0.1, math.nan, math.inf, [0.3], 10 ** 400])
def test_a_cache_price_is_none_or_a_finite_number_at_least_zero(name, value):
    with pytest.raises(ValueError, match=name):
        cached(**{name: value})


@pytest.mark.parametrize("name", ["price_cached_in", "price_cache_write"])
def test_a_tiered_or_self_hosted_model_refuses_a_cache_price(name):
    with pytest.raises(ValueError, match=name):
        Model("v/t", "v", 3.0, 15.0, 1_000_000, price_tiers=(PriceTier(200_000, 6.0, 22.5),), **{name: 0.3})
    with pytest.raises(ValueError, match=name):
        Model("v/h", "v", 0.2, 5.0, 100_000, pricing_basis="self_hosted", **{name: 0.3})
    # without a cache price both still build, as in v1.586
    Model("v/t", "v", 3.0, 15.0, 1_000_000, price_tiers=(PriceTier(200_000, 6.0, 22.5),))
    Model("v/h", "v", 0.2, 5.0, 100_000, pricing_basis="self_hosted")


def test_the_worked_example_a_hit_a_one_shot_write_and_a_cheaper_model_that_misses():
    model = cached()
    uncached = model.cost(10_000, 500)
    hit = model.cost(10_000, 500, cached_input_tokens=9_000)
    write = model.cost(10_000, 500, cache_write_tokens=9_000)
    assert uncached == pytest.approx(0.0375, rel=1e-12)
    assert hit == pytest.approx(0.0132, rel=1e-12)  # (1000*3 + 9000*0.3 + 500*15) / 1e6
    assert write == pytest.approx(0.04425, rel=1e-12)  # (1000*3 + 9000*3.75 + 500*15) / 1e6
    assert write > uncached  # a write premium makes caching lose on a one-shot prompt
    cheaper = Model("v/d", "v", 2.0, 15.0, 200_000)
    assert cheaper.cost(10_000, 500) == pytest.approx(0.0275, rel=1e-12)
    assert cheaper.cost(10_000, 500, cached_input_tokens=0) > hit  # cheaper per token, but it misses


def test_reads_and_writes_together_are_each_at_their_own_price():
    got = cached().cost(10_000, 500, cached_input_tokens=6_000, cache_write_tokens=3_000)
    assert got == pytest.approx((1_000 * 3.0 + 6_000 * 0.3 + 3_000 * 3.75 + 500 * 15.0) / 1e6, rel=1e-12)
    assert cached().cost(9_000, 0, cached_input_tokens=9_000) == pytest.approx(9_000 * 0.3 / 1e6, rel=1e-12)


def test_an_unknown_cache_price_is_the_input_price():
    reads_unknown = cached(price_cached_in=None)
    assert reads_unknown.cost(10_000, 500, cached_input_tokens=9_000) == reads_unknown.cost(10_000, 500)
    assert reads_unknown.cost(10_000, 500, cache_write_tokens=9_000) == pytest.approx(0.04425, rel=1e-12)
    writes_unknown = cached(price_cache_write=None)
    assert writes_unknown.cost(10_000, 500, cache_write_tokens=9_000) == writes_unknown.cost(10_000, 500)
    plain = Model("v/m", "v", 3.0, 15.0, 200_000)
    assert plain.cost(10_000, 500, cached_input_tokens=4_000, cache_write_tokens=5_000) == plain.cost(10_000, 500)


def test_a_tiered_model_prices_reads_and_writes_at_its_call_tier_input_price():
    tiered = Model("v/t", "v", 3.0, 15.0, 1_000_000, price_tiers=(PriceTier(200_000, 6.0, 22.5),))
    long_call = tiered.cost(300_000, 1_000, cached_input_tokens=200_000, cache_write_tokens=50_000)
    assert long_call == tiered.cost(300_000, 1_000)
    assert long_call == pytest.approx((300_000 * 6.0 + 1_000 * 22.5) / 1e6, rel=1e-12)
    assert tiered.cost(100_000, 1_000, cached_input_tokens=90_000) == tiered.cost(100_000, 1_000)


@pytest.mark.parametrize("kwargs, named", [
    ({"cached_input_tokens": -1}, "cached_input_tokens"),
    ({"cached_input_tokens": True}, "cached_input_tokens"),
    ({"cached_input_tokens": 1.0}, "cached_input_tokens"),
    ({"cached_input_tokens": "1"}, "cached_input_tokens"),
    ({"cached_input_tokens": None}, "cached_input_tokens"),
    ({"cache_write_tokens": -1}, "cache_write_tokens"),
    ({"cache_write_tokens": False}, "cache_write_tokens"),
    ({"cache_write_tokens": 2.5}, "cache_write_tokens"),
    ({"cached_input_tokens": 1_001}, "cached_input_tokens"),
    ({"cache_write_tokens": 1_001}, "cache_write_tokens"),
    ({"cached_input_tokens": 600, "cache_write_tokens": 401}, "cached_input_tokens.*cache_write_tokens"),
])
def test_the_counts_are_ints_at_least_zero_within_the_input(kwargs, named):
    with pytest.raises(ValueError, match=named):
        cached().cost(1_000, 100, **kwargs)


def test_the_counts_are_keyword_only_and_may_fill_the_input():
    with pytest.raises(TypeError):
        cached().cost(1_000, 100, 10)
    assert cached().cost(1_000, 100, cached_input_tokens=600, cache_write_tokens=400) == pytest.approx(
        (600 * 0.3 + 400 * 3.75 + 100 * 15.0) / 1e6, rel=1e-12)


def test_with_both_counts_zero_the_cost_is_v1586s_bit_for_bit():
    registry = Registry.load(DATA_DIR / "models.json")
    for model in registry.models + (cached(),):
        for size_in, size_out in ((0, 0), (1, 1), (1_234, 567), (99_999, 3_001), (150_000, 8_000)):
            if size_in >= model.context_window:
                continue
            assert model.cost(size_in, size_out, cached_input_tokens=0, cache_write_tokens=0) == \
                model.cost(size_in, size_out)


def test_without_cache_counts_the_packaged_costs_are_the_tier_formula():
    # the guard v1.587 keeps: Model.cost(i, o) is v1.586's expression on every packaged model
    for model in Registry.load(DATA_DIR / "models.json").models:
        for size_in, size_out in ((0, 0), (1_234, 567), (150_000, 8_000)):
            price_in, price_out = model.price_in, model.price_out
            for tier in model.price_tiers:
                if size_in > tier.above_input_tokens:
                    price_in, price_out = tier.price_in, tier.price_out
            assert model.cost(size_in, size_out) == (size_in * price_in + size_out * price_out) / 1_000_000


def test_a_row_reads_both_prices_and_its_variants_keep_them(tmp_path):
    registry = _load(tmp_path, [_row("v/a", price_cached_in=0.3, price_cache_write=3.75, variants={"hi": {}}),
                                _row("v/b"), _row("v/c", price_cached_in=None, price_cache_write=None),
                                _row("v/d", price_cached_in=0)])
    for model_id in ("v/a", "v/a@hi"):
        model = registry.get(model_id)
        assert (model.price_cached_in, model.price_cache_write) == (0.3, 3.75)
    assert {(registry.get(m).price_cached_in, registry.get(m).price_cache_write) for m in ("v/b", "v/c")} == \
        {(None, None)}
    assert registry.get("v/d").price_cached_in == 0.0 and registry.get("v/d").price_cache_write is None


@pytest.mark.parametrize("name", ["price_cached_in", "price_cache_write"])
@pytest.mark.parametrize("value", ["0.3", True, -1, [0.3], {"usd": 0.3}])
def test_a_refused_row_price_names_the_file(tmp_path, name, value):
    with pytest.raises(ValueError, match=f"models.json.*{name}"):
        _load(tmp_path, [_row("v/a", **{name: value})])


@pytest.mark.parametrize("name", ["price_cached_in", "price_cache_write"])
def test_a_self_hosted_or_tiered_row_refuses_a_cache_price(tmp_path, name):
    with pytest.raises(ValueError, match="models.json"):
        _load(tmp_path, [dict({"id": "v/h", "family": "v", "context_window": 100_000, name: 0.3}, **_hour())])
    tiers = [{"above_input_tokens": 100_000, "price_in": 6.0, "price_out": 22.5}]
    with pytest.raises(ValueError, match=f"models.json.*{name}"):
        _load(tmp_path, [_row("v/t", price_tiers=tiers, **{name: 0.3})])


def test_models_with_and_without_cache_prices_round_trip_through_asdict(tmp_path):
    registry = _load(tmp_path, [_row("v/a", price_cached_in=0.3, price_cache_write=3.75), _row("v/b")])
    back = _load(tmp_path, [dataclasses.asdict(m) for m in registry.models])
    assert back.models == registry.models
    as_json = json.loads(json.dumps(dataclasses.asdict(registry.get("v/b"))))
    assert (as_json["price_cached_in"], as_json["price_cache_write"]) == (None, None)
    variant = Model("v/a@hi", "v", 1.0, 2.0, 100_000, variant=Variant("hi"), price_cached_in=0.1)
    with pytest.raises(ValueError, match="models.json"):
        _load(tmp_path, [dataclasses.asdict(variant)])  # its base row holds it, as before v1.587


def test_no_packaged_row_or_evidence_file_names_a_cache_price():
    raw = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))
    assert not any(key in r for r in raw["models"] for key in NAMES[:2])
    named = [path for path in (ROOT / "evidence").rglob("*") if path.is_file()
             and path.suffix in (".json", ".py", ".md")
             and any(key in path.read_text(encoding="utf-8") for key in NAMES)]
    assert named == []


def test_only_the_registry_names_the_prices_and_the_counts():
    # so no route, record, report, delegation decision, evidence file or README transcript changes yet
    naming = {path.name for path in PACKAGE.glob("*.py")
              if any(key in path.read_text(encoding="utf-8") for key in NAMES)}
    assert naming == {"registry.py"}


def test_the_production_note_states_registry_cache_prices_as_shipped():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    for gone in ("registry prices for cached reads", "planned cache prices", "no cache write is priced",
                 "the one cache price it reads", "as planned for cache prices"):
        assert gone not in note, gone
    uber = note.split("\n### Price cache writes, and set the cache's life by how the work pauses\n", 1)[1]
    line = [x for x in uber.split("\n### ", 1)[0].splitlines() if x.startswith("- In this library: ")]
    assert len(line) == 1
    assert line[0].startswith("- In this library: a registry row may state `price_cached_in` and "
                              "`price_cache_write`, and `Model.cost` prices a call's cached reads and cache writes")
    assert "The change: measured cached and written tokens per task and model" in line[0]
    rate = note.split("\n### The cache hit rate is a cost number\n", 1)[1]
    rate_line = [x for x in rate.split("\n### ", 1)[0].splitlines() if x.startswith("- In this library: ")]
    assert len(rate_line) == 1
    assert "a registry row may state a cached-read and a cache-write price" in rate_line[0]
    assert "but model choice passes none yet" in rate_line[0]


def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four = design[design.index("### 4.1 "):design.index("### 4.2 ")]
    assert four.count("- v1.587 cache prices (row CACHE1a): `Model` gains two last fields after `scope_tasks`") == 1
    assert four.count("- v1.587 `Model.cost(input_tokens, output_tokens, *, cached_input_tokens=0, "
                      "cache_write_tokens=0)`") == 1
    assert four.count("- v1.587 `Registry.load` reads the optional `price_cached_in` and `price_cache_write`") == 1
    assert "costs 0.0375 uncached, 0.0132 with 9,000 cached reads, and 0.04425 with 9,000 cache writes" in four
    nine = design[design.index("## 9. "):design.index("## 10. ")]
    assert nine.count("- v1.587 `price_cached_in` and `price_cache_write` (format in 4.1, row CACHE1a)") == 1
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.587 (")]
    assert len(mine) == 1 and changelog[-1] == mine[0]
    assert len(mine[0].encode("utf-8")) <= 600
