"""DESIGN 4.3 and 5.2 v1.671 (row DEL1ba, the first part of row DEL1b): a pair's side tokens.

A pair key `<root>+<leaf>` may hold the summed input and output tokens of its root and of its leaf
over `side_trials` of its trials. `select_pair` then prices each side at its mean tokens inside the
pair, at its own prices, with no cache count, over its `items_per_call`; a pair key without them is
priced as in v1.670, each side at its own key's 5.2 sizes. The fixture is tests/test_select_pair.py's
4 x 3 one, whose task expects 1,000 input and 200 output tokens.
"""

import json

import pytest

from model_routing import Model, Registry, Router, Stats, Task, Variant
from test_select_pair import LEAVES, N, PAIRS, ROOTS, by_id, cost, registry, router

SIDES = ("root_input_tokens", "root_output_tokens", "leaf_input_tokens", "leaf_output_tokens")


def sides(root_in, root_out, leaf_in, leaf_out, trials=N):
    """Per-trial side tokens as `.add` totals over ``trials`` side trials."""
    return dict(zip(SIDES, (root_in * trials, root_out * trials, leaf_in * trials, leaf_out * trials)),
                side_trials=trials)


# --- 4.3 v1.671: .add, .side_tokens, .mean_side_tokens, .merge -------------------------------

def test_add_keeps_the_five_and_the_means_round_up():
    stats = Stats()
    stats.add("t", "a+b", 2, 3, root_input_tokens=100, root_output_tokens=101, leaf_input_tokens=7,
              leaf_output_tokens=0)
    assert stats.side_tokens("t", "a+b") == (100, 101, 7, 0, 3)
    assert stats.mean_side_tokens("t", "a+b") == ((34, 34), (3, 0))
    stats.add("t", "a+b", 1, 2, **dict(zip(SIDES, (2, 0, 0, 0))), side_trials=1)
    assert stats.side_tokens("t", "a+b") == (102, 101, 7, 0, 4)
    assert stats.mean_side_tokens("t", "a+b") == ((26, 26), (2, 0))
    assert stats.get("t", "a+b") == (3, 5)
    assert stats.tokens("t", "a+b") == (0, 0, 0)  # apart from the token keys


def test_a_key_without_side_tokens_has_zeros_and_no_mean():
    stats = Stats()
    stats.add("t", "a+b", 1, 1, input_tokens=10, output_tokens=5)
    assert stats.side_tokens("t", "a+b") == (0, 0, 0, 0, 0)
    assert stats.mean_side_tokens("t", "a+b") is None
    assert stats.mean_side_tokens("t", "never") is None


@pytest.mark.parametrize("kwargs", [
    {"root_input_tokens": 1},
    {"root_input_tokens": 1, "root_output_tokens": 1, "leaf_input_tokens": 1},
    {"side_trials": 1},
    {**dict(zip(SIDES, (1, 1, 1, -1)))},
    {**dict(zip(SIDES, (1, 1, True, 1)))},
    {**dict(zip(SIDES, (1, 1.0, 1, 1)))},
    {**dict(zip(SIDES, (1, 1, 1, "1")))},
    {**dict(zip(SIDES, (1, 1, 1, 1))), "side_trials": 0},
    {**dict(zip(SIDES, (1, 1, 1, 1))), "side_trials": 4},
    {**dict(zip(SIDES, (1, 1, 1, 1))), "side_trials": True},
    {**dict(zip(SIDES, (1, 1, 1, 1))), "side_trials": 2.0},
], ids=["one total", "three totals", "side_trials alone", "negative", "a bool", "a float", "a str",
        "zero side trials", "over trials", "a bool side_trials", "a float side_trials"])
def test_add_refuses_a_bad_set_and_adds_nothing(kwargs):
    stats = Stats()
    with pytest.raises(ValueError, match="side_trials|_tokens"):
        stats.add("t", "a+b", 1, 3, **kwargs)
    assert stats.get("t", "a+b") == (0, 0)
    assert stats.side_tokens("t", "a+b") == (0, 0, 0, 0, 0)


@pytest.mark.parametrize("model_id, extra", [("x/a>x/b@low", {"escalated": 0}), ("proc:p@1", {"cost_usd": 0.5})],
                         ids=["cascade", "procedure"])
def test_a_cascade_or_procedure_key_holds_no_side_tokens(model_id, extra):
    stats = Stats()
    with pytest.raises(ValueError, match="side"):
        stats.add("t", model_id, 1, 1, **extra, **dict(zip(SIDES, (1, 1, 1, 1))))
    assert stats.get("t", model_id) == (0, 0)


def test_merge_sums_the_five():
    one, two = Stats(), Stats()
    one.add("t", "a+b", 1, 2, **dict(zip(SIDES, (10, 20, 30, 40))))
    two.add("t", "a+b", 1, 3, **dict(zip(SIDES, (1, 2, 3, 4))), side_trials=1)
    two.add("t", "c+d", 1, 1)
    merged = one.merge(two)
    assert merged.side_tokens("t", "a+b") == (11, 22, 33, 44, 3)
    assert merged.side_tokens("t", "c+d") == (0, 0, 0, 0, 0)
    assert merged.get("t", "a+b") == (2, 5)


# --- 4.3 v1.671: files ----------------------------------------------------------------------

def test_save_writes_the_five_after_the_cache_keys_and_before_the_sources(tmp_path):
    stats = Stats()
    stats.add("t", "a+b", 2, 2, input_tokens=9, output_tokens=8, cached_input_tokens=4,
              label_sources={"human": 2}, latencies_ms=[5.0], **dict(zip(SIDES, (5, 6, 7, 8))), side_trials=1)
    path = tmp_path / "s.json"
    stats.save(path)
    row = json.loads(path.read_text(encoding="utf-8"))["stats"][0]
    assert list(row) == ["task", "model", "successes", "trials", "input_tokens", "output_tokens",
                         "token_trials", "cached_input_tokens", "cached_trials", *SIDES, "side_trials",
                         "label_sources", "latencies_ms"]
    assert [row[k] for k in (*SIDES, "side_trials")] == [5, 6, 7, 8, 1]
    again = Stats.load(path)
    assert again.side_tokens("t", "a+b") == (5, 6, 7, 8, 1)
    again.save(tmp_path / "t.json")
    assert (tmp_path / "t.json").read_bytes() == path.read_bytes()


V1_670_FILE = {"stats": [
    {"task": "t", "model": "a+b", "successes": 3, "trials": 4, "input_tokens": 40, "output_tokens": 8,
     "token_trials": 4, "cached_input_tokens": 12, "cached_trials": 2, "cache_write_tokens": 3,
     "cache_write_trials": 1, "label_sources": {"consensus": 1, "human": 3}, "rerun_items": 2,
     "consistent_items": 1, "latencies_ms": [1.5, 2.0]},
    {"task": "t", "model": "proc:p@1", "successes": 2, "trials": 2, "cost_usd": 0.25},
    {"task": "t", "model": "x/a>x/b@low", "successes": 1, "trials": 2, "escalated": 1},
    {"task": "t@deep", "model": "x/y", "successes": 0, "trials": 1},
]}


def test_a_file_without_side_tokens_keeps_its_bytes(tmp_path):
    path = tmp_path / "old.json"
    path.write_text(json.dumps(V1_670_FILE, indent=2) + "\n", encoding="utf-8")
    Stats.load(path).save(tmp_path / "new.json")
    assert (tmp_path / "new.json").read_bytes() == path.read_bytes()


@pytest.mark.parametrize("change", [
    {"side_trials": None},
    {"leaf_output_tokens": None},
    {"root_input_tokens": True},
    {"root_output_tokens": "6"},
    {"leaf_input_tokens": -1},
    {"side_trials": 3},
    {"model": "x/a>x/b@low", "escalated": 0},
    {"model": "proc:p@1", "cost_usd": 0.5},
], ids=["null side_trials", "null total", "a bool", "a str", "negative", "over trials", "cascade",
        "procedure"])
def test_load_refuses_a_bad_row_naming_the_file(tmp_path, change):
    row = {"task": "t", "model": "a+b", "successes": 1, "trials": 2,
           **dict(zip(SIDES, (5, 6, 7, 8))), "side_trials": 2}
    row.update(change)
    path = tmp_path / "bad.json"
    path.write_text(json.dumps({"stats": [row]}), encoding="utf-8")
    with pytest.raises(ValueError, match="bad.json"):
        Stats.load(path)


@pytest.mark.parametrize("drop", [*SIDES, "side_trials"])
def test_load_refuses_a_partial_set(tmp_path, drop):
    row = {"task": "t", "model": "a+b", "successes": 1, "trials": 2,
           **dict(zip(SIDES, (5, 6, 7, 8))), "side_trials": 2}
    del row[drop]
    path = tmp_path / "part.json"
    path.write_text(json.dumps({"stats": [row]}), encoding="utf-8")
    with pytest.raises(ValueError, match="part.json"):
        Stats.load(path)


# --- 5.2 v1.671: each side priced at its tokens inside the pair -------------------------------

def test_a_root_that_reads_little_is_priced_below_the_same_pair_at_the_sides_own_sizes():
    # root 50 in, 200 out per trial at 10 and 30 per million: (500 + 6000) / 1e6 = 0.0065
    # leaf 4,000 in, 100 out at 0.1 and 0.3 per million: (400 + 30) / 1e6 = 0.00043
    extra = {("r/strong", "l/cheap"): sides(50, 200, 4000, 100)}
    priced = by_id(router(pair_extra=extra).select_pair("t", ROOTS, LEAVES))["r/strong+l/cheap"]
    assert priced.list_cost == pytest.approx(0.0065 + 0.00043, rel=1e-12)
    assert priced.routing_cost == priced.list_cost
    at_own_sizes = cost("r/strong") + cost("l/cheap")  # v1.670: 0.016 + 0.00016
    assert at_own_sizes == pytest.approx(0.01616, rel=1e-12)
    assert priced.list_cost < at_own_sizes
    assert priced.cost_breakdown is None and priced.cache_price_unknown == ()


def test_a_cheap_leaf_that_reads_far_more_is_not_the_cheaper_pair():
    # strong+cheap: 0.0065 + (90,000 * 0.1 + 100 * 0.3) / 1e6 = 0.0065 + 0.00903 = 0.01553
    # strong+mid: 0.0065 + (2,000 * 1 + 100 * 3) / 1e6 = 0.0065 + 0.0023 = 0.0088
    # good+dear at v1.670's sizes: 0.0048 + 0.016 = 0.0208; strong+dear 0.032
    extra = {("r/strong", "l/cheap"): sides(50, 200, 90_000, 100),
             ("r/strong", "l/mid"): sides(50, 200, 2000, 100)}
    decision = router(pair_extra=extra).select_pair("t", ROOTS, LEAVES)
    assert decision.primary == "r/strong+l/mid"
    assert decision.fallbacks == ("r/strong+l/cheap", "r/good+l/dear")
    priced = by_id(decision)
    assert priced["r/strong+l/cheap"].list_cost == pytest.approx(0.01553, rel=1e-12)
    assert priced["r/strong+l/mid"].list_cost == pytest.approx(0.0088, rel=1e-12)
    assert priced["r/good+l/dear"].list_cost == pytest.approx(0.0208, rel=1e-12)
    assert router().select_pair("t", ROOTS, LEAVES).primary == "r/strong+l/cheap"  # v1.670


def test_cost_blind_choice_is_unchanged_by_side_tokens():
    extra = {pair: sides(1, 1, 1, 1) for pair in PAIRS}
    assert router(pair_extra=extra).select_pair("t", ROOTS, LEAVES, "cost_blind").to_dict()["primary"] == \
        router().select_pair("t", ROOTS, LEAVES, "cost_blind").to_dict()["primary"] == "r/strong+l/dear"
    blind = router(pair_extra=extra).select_pair("t", ROOTS, LEAVES, "cost_blind")
    assert all(c.routing_cost == 0.0 for c in blind.candidates)
    # list_cost still reads them: (1 * 10 + 1 * 30) / 1e6 for each side of strong+dear
    assert by_id(blind)["r/strong+l/dear"].list_cost == pytest.approx(0.00008, rel=1e-12)


def test_a_leaf_with_no_tokens_in_the_pair_costs_nothing():
    extra = {("r/strong", "l/dear"): sides(1000, 200, 0, 0)}
    priced = by_id(router(pair_extra=extra).select_pair("t", ROOTS, LEAVES))["r/strong+l/dear"]
    assert priced.list_cost == pytest.approx(cost("r/strong"), rel=1e-12)


def test_the_means_round_up_per_side_trial():
    # 3 side trials of 10 trials: root (101, 10) -> (34, 4), leaf (3001, 0) -> (1001, 0)
    pair_extra = {("r/strong", "l/cheap"): {**dict(zip(SIDES, (101, 10, 3001, 0))), "side_trials": 3}}
    priced = by_id(router(pair_extra=pair_extra).select_pair("t", ROOTS, LEAVES))["r/strong+l/cheap"]
    assert priced.list_cost == pytest.approx((34 * 10 + 4 * 30 + 1001 * 0.1) / 1_000_000, rel=1e-12)


def test_a_side_s_items_per_call_divides_its_side_cost():
    batch = Model("l/batch@four", "batch", 1.0, 3.0, 100_000, variant=Variant("four", items_per_call=4))
    reg = registry(extra=[batch])
    stats = Stats()
    stats.add("t", "r/strong+l/batch@four", N, N, **sides(50, 200, 8000, 400))
    r = Router(reg, {"t": Task("t", bar=0.8, min_samples=30)}, stats)
    priced = r.select_pair("t", ["r/strong"], ["l/batch@four"]).candidates[0]
    # root 0.0065; leaf (8,000 * 1 + 400 * 3) / 1e6 / 4 = 0.0092 / 4 = 0.0023
    assert priced.list_cost == pytest.approx(0.0065 + 0.0023, rel=1e-12)
    stats_plain = Stats()
    stats_plain.add("t", "r/strong+l/batch@four", N, N)
    plain = Router(reg, {"t": Task("t", bar=0.8, min_samples=30)}, stats_plain)
    # v1.670: at the task's sizes one call of one item, undivided: (1,000 * 1 + 200 * 3) / 1e6
    assert plain.select_pair("t", ["r/strong"], ["l/batch@four"]).candidates[0].list_cost == \
        pytest.approx(cost("r/strong") + 0.0016, rel=1e-12)


def test_a_side_at_its_side_tokens_has_no_cache_count_while_one_at_its_own_sizes_keeps_it():
    strong = Model("r/strong", "strong", 10.0, 30.0, 100_000, price_cached_in=1.0)
    reg = Registry([strong] + [m for m in registry().models if m.id != "r/strong"])
    cached = {"r/strong": {"input_tokens": 500 * N, "output_tokens": 100 * N, "cached_input_tokens": 400 * N}}
    # v1.670: the root at its own key's mean 500 / 100 with 400 cached reads:
    # (100 * 10 + 400 * 1 + 100 * 30) / 1e6 = 0.0044, plus the cheap leaf at the task's sizes 0.00016
    at_own = by_id(router(reg=reg, solo_extra=cached).select_pair("t", ROOTS, LEAVES))["r/strong+l/cheap"]
    assert at_own.list_cost == pytest.approx(0.0044 + 0.00016, rel=1e-12)
    # v1.671: the same tokens as side tokens carry no cache count: (500 * 10 + 100 * 30) / 1e6 = 0.008
    extra = {("r/strong", "l/cheap"): sides(500, 100, 1000, 200)}
    at_side = by_id(router(reg=reg, solo_extra=cached, pair_extra=extra)
                    .select_pair("t", ROOTS, LEAVES))["r/strong+l/cheap"]
    assert at_side.list_cost == pytest.approx(0.008 + 0.00016, rel=1e-12)
    assert at_side.cost_breakdown is None and at_side.cache_price_unknown == ()


def test_a_pair_key_s_own_token_keys_are_not_read():
    extra = {("r/strong", "l/cheap"): {"input_tokens": 10 * N, "output_tokens": 10 * N}}
    priced = by_id(router(pair_extra=extra).select_pair("t", ROOTS, LEAVES))["r/strong+l/cheap"]
    assert priced.list_cost == pytest.approx(cost("r/strong") + cost("l/cheap"), rel=1e-12)


# --- unchanged: select and every pair without side tokens -------------------------------------

def test_select_reads_no_side_tokens():
    on_models = {m: sides(1, 1, 1, 1) for m in ROOTS + LEAVES}
    on_pairs = {pair: sides(1, 1, 1, 1) for pair in PAIRS}
    plain = router()
    for r in (router(solo_extra=on_models), router(pair_extra=on_pairs)):
        assert r.select("t").to_dict() == plain.select("t").to_dict()
        assert r.select("t", "cost_blind").to_dict() == plain.select("t", "cost_blind").to_dict()


def test_pairs_without_side_tokens_keep_v1_670_s_decision():
    extra = {("r/strong", "l/mid"): sides(50, 200, 2000, 100)}
    with_one, without = by_id(router(pair_extra=extra).select_pair("t", ROOTS, LEAVES)), \
        by_id(router().select_pair("t", ROOTS, LEAVES))
    for pair_id, candidate in without.items():
        if pair_id != "r/strong+l/mid":
            assert with_one[pair_id] == candidate
