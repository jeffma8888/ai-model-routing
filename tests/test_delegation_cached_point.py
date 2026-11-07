"""v1.57 cached context reads in the delegation evidence (DESIGN 13.9, 13.10), written before
the code.

A point of ``evaluate_delegation`` may carry ``cached_read_ratio`` rho, an int or a float
that is not a bool, from 0 to 1. It reaches ``decide_delegation``, and the held-out inline
cost of each item prices the parent's reads of C in its work calls at rho times its list
input price; the delegated cost, the delegate and every success count are those of the same
point without the key. A point without it means rho = 1.0 and serialises as before. The
13.10 variant grid gains variant point 1, base point 2 with rho = 0.1, and ``table`` gains a
``cached`` column when a config point carries the ratio.

The new behaviour is committed under strict xfail markers, each naming what the v1.56 code
raises: ``ValueError`` where a test runs a point with ``cached_read_ratio`` (``_points``
accepts the five ``POINT_KEYS`` and ``work_calls`` only), and ``AssertionError`` where a test
expects a v1.57 error message that the v1.56 key check raises first with other words, or
the two variant points or the ``cached`` column. The implementing commit (v1.58) removes the
markers. The tests that are never marked pin that points without the key give the v1.56
result bit for bit; they pass before the code and after it.

The harness fixture is the one of tests/test_delegation_eval_work_calls.py: two seeds that
each hold 3 items for calibration and 5 out, every call reads 1,000 tokens and writes 200,
prices per 1M tokens big 10/40, small 1/4 and weak 0.1/0.4, big and small right on every
item and weak on none, so at bar 0.4 big and small clear and weak does not.
"""

import hashlib
import importlib
import importlib.util
import json
import math
import statistics
from math import fsum
from pathlib import Path

import pytest

from model_routing import Model, Registry, Router, Stats, Task, evaluate_delegation
from model_routing.evaluate import split_items

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "delegation" / "results.py"
RESULTS = ROOT / "evidence" / "delegation" / "results.json"
VARIANTS_FILE = ROOT / "evidence" / "delegation" / "variants.json"
ITEMS = [f"q{i}" for i in range(1, 9)]
SEEDS = [0, 1]
HELD = {0: ("q1", "q2", "q3", "q7", "q8"), 1: ("q1", "q4", "q5", "q6", "q8")}
MODELS = ["fiction/big", "fiction/small", "fiction/weak"]
RIGHT = {"fiction/big": True, "fiction/small": True, "fiction/weak": False}
S_IN, S_OUT = 1000, 200
KEYS = ["context_tokens", "brief_tokens", "result_tokens", "carry_turns",
        "inline_separate_call"]
STRATEGIES = ["decision", "inline", "delegate"]

RED_RUN = pytest.mark.xfail(strict=True, raises=ValueError,
                            reason="v1.56 _points rejects cached_read_ratio as an extra key")
RED_MESSAGE = pytest.mark.xfail(strict=True, raises=AssertionError,
                                reason="v1.56 raises its key-check message first")
RED_SCRIPT = pytest.mark.xfail(strict=True, raises=AssertionError,
                               reason="v1.56 has one variant point and no cached column")


def point(c, b, r, t, separate, **extra):
    return dict({"context_tokens": c, "brief_tokens": b, "result_tokens": r, "carry_turns": t,
                 "inline_separate_call": separate}, **extra)


# the points of tests/test_delegation_eval_work_calls.py
POINTS = [point(100_000, 500, 300, 0, True), point(0, 500, 300, 0, False),
          point(0, 500, 300, 2, True)]
KPOINTS = [point(100_000, 500, 300, 0, True, work_calls=2),
           point(100_000, 500, 300, 0, False, work_calls=2),
           point(0, 500, 300, 2, False, work_calls=3)]
# cached points: a call of its own over a large context at rho 0.1, then 0 (the int), the
# same context with the last of two calls folded at rho 0.25, and a separate K = 3 point
RPOINTS = [point(100_000, 500, 300, 0, True, cached_read_ratio=0.1),
           point(100_000, 500, 300, 0, True, cached_read_ratio=0),
           point(100_000, 500, 300, 0, False, work_calls=2, cached_read_ratio=0.25),
           point(20_000, 400, 900, 1, True, work_calls=3, cached_read_ratio=0.37)]


def load():
    return importlib.import_module("model_routing.delegation_eval")


def registry(window=1_000_000):
    return Registry([Model("fiction/big", "large", 10.0, 40.0, window),
                     Model("fiction/small", "small", 1.0, 4.0, window),
                     Model("fiction/weak", "tiny", 0.1, 0.4, window)])


def varied_registry():
    return Registry([Model("fiction/big", "large", 2.7, 13.1, 1_000_000),
                     Model("fiction/small", "small", 0.33, 1.9, 1_000_000),
                     Model("fiction/weak", "tiny", 0.07, 0.29, 1_000_000)])


def matrix(task="work", items=ITEMS, tokens=None):
    rows = []
    for item in items:
        for m in MODELS:
            tin, tout = (S_IN, S_OUT) if tokens is None else tokens(item, m)
            rows.append({"task": task, "item": item, "model": m, "correct": RIGHT[m],
                         "input_tokens": tin, "output_tokens": tout})
    return rows


def run(rows=None, reg=None, **kwargs):
    args = {"bars": [0.4], "points": POINTS, "seeds": SEEDS, "min_samples": 3}
    args.update(kwargs)
    return load().evaluate_delegation(matrix() if rows is None else rows,
                                      registry() if reg is None else reg, **args)


def varied_tokens(item, m):
    k = int(item[1:])
    return 900 + 37 * k + 5 * MODELS.index(m), 150 + 11 * k + MODELS.index(m)


def stats_for(rows, cal):
    stats = Stats()
    for m in MODELS:
        own = [r for r in rows if r["model"] == m and r["item"] in cal]
        stats.add("work", m, sum(r["correct"] for r in own), len(own),
                  input_tokens=sum(r["input_tokens"] for r in own),
                  output_tokens=sum(r["output_tokens"] for r in own))
    return stats


def held_out_costs(pt, p, d, tokens_p, tokens_d):
    """One item's inline and delegated cost by the 13.9 v1.57 expressions, left to right."""
    c, b, r, t = (pt[key] for key in KEYS[:4])
    k = pt.get("work_calls", 1)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    (tin, tout), (din, dout) = tokens_p, tokens_d
    reads = k * c if pt["inline_separate_call"] else (k - 1) * c
    if "cached_read_ratio" in pt:
        reads = reads * pt["cached_read_ratio"]
    if pt["inline_separate_call"]:
        inline = (p.cost(reads + w_in * tin + w_out * tout, k * tout)
                  + (1 + t) * p.cost(k * (tin + tout), 0))
    else:
        inline = (p.cost(reads + w_in * tin + w_out * tout, k * tout)
                  + t * p.cost(k * (tin + tout), 0))
    delegate = (p.cost(0, b) + d.cost(k * b + w_in * din + w_out * dout, k * dout)
                + (1 + t) * p.cost(b + r, 0))
    return inline, delegate


def without_ratio(pt):
    return {k: v for k, v in pt.items() if k != "cached_read_ratio"}


# --- v1.57 harness behaviour, red until the v1.58 harness takes cached_read_ratio ---------

@RED_RUN
def test_a_cached_point_serialises_the_ratio_last():
    given = [point(100_000, 500, 300, 0, True, cached_read_ratio=0.1),
             {"cached_read_ratio": 0.5, "work_calls": 2, "inline_separate_call": False,
              "carry_turns": 1, "result_tokens": 3, "brief_tokens": 2, "context_tokens": 9}]
    result = run(points=POINTS + given)
    assert result["config"]["points"] == POINTS + given
    keys = [list(p) for p in result["config"]["points"]]
    assert keys == [KEYS] * 3 + [KEYS + ["cached_read_ratio"],
                                 KEYS + ["work_calls", "cached_read_ratio"]]


@RED_RUN
def test_points_without_the_ratio_keep_their_cells_beside_cached_points():
    alone, mixed = run(points=POINTS + KPOINTS), run(points=POINTS + KPOINTS + RPOINTS)
    assert [c for c in mixed["cells"] if c["point"] < 6] == alone["cells"]
    assert [r for r in mixed["summary"] if r["point"] < 6] == alone["summary"]


@RED_RUN
def test_the_decision_is_decide_delegation_with_the_points_ratio():
    # seed 2 calibrates on 4 items, so the lower and the upper median differ
    rows = matrix(tokens=varied_tokens)
    result = run(rows=rows, seeds=[0, 1, 2], points=RPOINTS)
    moved = 0
    for c in result["cells"]:
        cal, _ = split_items(ITEMS, c["seed"])
        cal_rows = [r for r in rows if r["item"] in cal]
        task = Task(name="work", bar=0.4, min_samples=3, confidence=0.95,
                    independent_of_generator=False,
                    expected_input_tokens=statistics.median_low(
                        [r["input_tokens"] for r in cal_rows]),
                    expected_output_tokens=statistics.median_low(
                        [r["output_tokens"] for r in cal_rows]),
                    on_no_model="best_available", max_fallbacks=0)
        router = Router(registry(), {"work": task}, stats_for(rows, cal))
        pt = RPOINTS[c["point"]]
        d = router.decide_delegation("work", c["parent"], c["flavor"], **pt)
        assert (c["mode"], c["model"], c["reason"], c["below_bar"], c["inline_allowed"],
                c["delegate"]) == (d.mode, d.model, d.reason, d.below_bar,
                                   d.inline_allowed, d.route.primary)
        full = router.decide_delegation("work", c["parent"], c["flavor"], **without_ratio(pt))
        moved += (full.mode, full.reason) != (d.mode, d.reason)
    # rho reached the decision: some cached cells decide otherwise than list-price reads would
    assert moved > 0


@RED_RUN
def test_held_out_cost_prices_the_parents_reads_of_c_at_rho():
    def tokens(item, m):
        k = int(item[1:])
        return 1013 + 977 * k + 131 * MODELS.index(m), 89 + 233 * k + 41 * MODELS.index(m)

    rows = matrix(tokens=tokens)
    reg = varied_registry()
    points = RPOINTS + [point(7_777, 400, 900, 2, False, cached_read_ratio=0.9)]
    result = run(rows=rows, reg=reg, points=points)
    for c in result["cells"]:
        p, d = reg.get(c["parent"]), reg.get(c["delegate"])
        costs = [held_out_costs(points[c["point"]], p, d, tokens(i, p.id), tokens(i, d.id))
                 for i in HELD[c["seed"]]]
        assert c["cost_usd"]["inline"] == fsum(x for x, _ in costs)
        assert c["cost_usd"]["delegate"] == fsum(y for _, y in costs)
        chosen = "inline" if c["mode"] == "inline" else "delegate"
        assert c["cost_usd"]["decision"] == c["cost_usd"][chosen]


@RED_RUN
def test_rho_moves_only_the_inline_cost_and_through_it_the_decision():
    # one run per point: RPOINTS 0 and 1 are the same point without the ratio
    for pt in RPOINTS:
        cached, full = run(points=[pt]), run(points=[without_ratio(pt)])
        assert len(cached["cells"]) == len(full["cells"])
        for a, b in zip(cached["cells"], full["cells"]):
            for key in ("bar", "flavor", "point", "parent", "seed", "task", "calibration_items",
                        "held_out_items", "expected_input_tokens", "expected_output_tokens",
                        "inline_allowed", "delegate"):
                assert a[key] == b[key], key
            assert a["correct"]["inline"] == b["correct"]["inline"]
            assert a["correct"]["delegate"] == b["correct"]["delegate"]
            assert a["cost_usd"]["delegate"] == b["cost_usd"]["delegate"]
            # every cached point here reads C > 0 in at least one work call at rho < 1
            assert a["cost_usd"]["inline"] < b["cost_usd"]["inline"]


@RED_RUN
def test_folded_work_of_one_call_costs_the_same_for_every_rho():
    # (K - 1) * C = 0, so the ratio has nothing to price (DESIGN 13.2 v1.41)
    folded = point(100_000, 500, 300, 2, False)
    base = run(points=[folded])
    for rho in (0, 0.1, 0.5, 1.0):
        cached = run(points=[dict(folded, cached_read_ratio=rho)])
        assert cached["cells"] == base["cells"], rho
        assert cached["summary"] == base["summary"], rho


@RED_RUN
@pytest.mark.parametrize("rho", [1.0, 1])
def test_ratio_1_gives_the_cells_of_the_same_point_without_it(rho):
    reg = varied_registry()
    rows = matrix(tokens=varied_tokens)
    plain = POINTS + KPOINTS
    explicit = [dict(p, cached_read_ratio=rho) for p in plain]
    alone = run(rows=rows, reg=reg, points=plain)
    ones = run(rows=rows, reg=reg, points=explicit)
    assert ones["cells"] == alone["cells"]
    assert ones["summary"] == alone["summary"]
    # the key stays on the points that were given it
    assert ones["config"]["points"] == explicit


@RED_MESSAGE
@pytest.mark.parametrize("value", [-0.1, 1.000001, 2, -1, True, False, "0.1", None,
                                   math.nan, math.inf, -math.inf])
def test_an_invalid_ratio_is_a_value_error_naming_it(value):
    with pytest.raises(ValueError, match=r"^'cached_read_ratio' must be a number from 0 to 1"):
        run(points=[dict(POINTS[0], cached_read_ratio=value)])


@RED_MESSAGE
def test_the_ratio_is_checked_after_work_calls():
    with pytest.raises(ValueError, match=r"^'work_calls' must be an integer >= 1"):
        run(points=[dict(POINTS[0], work_calls=0, cached_read_ratio=2)])


@RED_MESSAGE
@pytest.mark.parametrize("points", [
    [POINTS[0], dict(POINTS[0], cached_read_ratio=1.0)],
    [dict(POINTS[1], cached_read_ratio=1), POINTS[1]],
    [dict(KPOINTS[0], cached_read_ratio=0.1), dict(KPOINTS[0], cached_read_ratio=0.1)],
    [dict(POINTS[0], work_calls=1, cached_read_ratio=1.0), POINTS[0]],
], ids=["missing-then-1.0", "int-1-then-missing", "same-rho", "k-and-rho-defaults"])
def test_a_repeated_point_is_a_value_error_with_a_missing_ratio_read_as_1(points):
    with pytest.raises(ValueError, match=r"^points must be distinct"):
        run(points=points)


@RED_MESSAGE
@pytest.mark.parametrize("pt", [dict(POINTS[0], extra=1),
                                dict(POINTS[0], cached_read_ratio=0.1, extra=1),
                                {k: v for k, v in POINTS[0].items() if k != "carry_turns"}])
def test_the_key_message_names_both_optional_keys(pt):
    with pytest.raises(ValueError, match=r"^a point needs exactly the keys \[.*\], and "
                                         r"optionally 'work_calls' and 'cached_read_ratio': "):
        run(points=[pt])


# --- v1.57 results script, red until v1.58 -------------------------------------------------

@pytest.fixture
def dr():
    spec = importlib.util.spec_from_file_location("delegation_results_cached", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


VARIANTS = [
    {"context_tokens": 64000, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
     "inline_separate_call": False, "work_calls": 2},
    {"context_tokens": 200000, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
     "inline_separate_call": True, "cached_read_ratio": 0.1},
]


def tiny():
    """The 80-item, two-model matrix of tests/test_delegation_variants.py."""
    reg = Registry([
        Model(id="v/strong", family="S", price_in=3.0, price_out=12.0, context_window=1_000_000),
        Model(id="v/cheap", family="C", price_in=0.1, price_out=0.4, context_window=100_000)])
    rows = []
    for i in range(80):
        rows.append({"task": "all", "item": f"q{i}", "model": "v/strong", "correct": i % 10 != 0,
                     "input_tokens": 200 + i, "output_tokens": 900 + 3 * i})
        rows.append({"task": "all", "item": f"q{i}", "model": "v/cheap", "correct": i % 3 != 0,
                     "input_tokens": 180 + i, "output_tokens": 700 + 2 * i})
    return rows, reg


@RED_SCRIPT
def test_variant_points_append_base_point_2_with_a_cached_ratio(dr):
    got = dr.variant_points()
    assert got == VARIANTS
    assert [list(p) for p in got] == [KEYS + ["work_calls"], KEYS + ["cached_read_ratio"]]
    assert without_ratio(got[1]) == dr.points()[2]
    assert got[1]["cached_read_ratio"] == 0.1


@RED_SCRIPT
def test_run_on_the_variants_grid_has_both_points_and_keeps_variant_point_0(dr):
    rows, reg = tiny()
    got = dr.run(rows, reg, grid="variants")
    assert got["config"]["points"] == VARIANTS
    full = evaluate_delegation(rows, reg, bars=[0.7, 0.8], points=VARIANTS, seeds=range(50))
    assert got == {key: full[key] for key in ("config", "tasks", "summary")}
    first = evaluate_delegation(rows, reg, bars=[0.7, 0.8], points=VARIANTS[:1], seeds=range(50))
    assert [r for r in got["summary"] if r["point"] == 0] == first["summary"]


@RED_SCRIPT
def test_variant_point_1_costs_less_inline_than_base_point_2_and_the_same_delegated(dr):
    rows, reg = tiny()
    base, variants = dr.run(rows, reg), dr.run(rows, reg, grid="variants")
    assert len(variants["config"]["points"]) == 2

    def index(results, at):
        return {(r["bar"], r["flavor"], r["parent"], r["strategy"]): r
                for r in results["summary"] if r["point"] == at}

    b, v = index(base, 2), index(variants, 1)
    assert set(b) == set(v)
    for (bar, flavor, parent, strategy), row in v.items():
        other = b[bar, flavor, parent, strategy]
        if strategy == "inline":
            assert row["cost_usd"] < other["cost_usd"]
            assert row["success"] == other["success"]
        if strategy == "delegate":
            assert (row["cost_usd"], row["success"]) == (other["cost_usd"], other["success"])


VALUES = {("a/x", "decision"): (0.5, 1.0, 1.0), ("a/x", "inline"): (0.25, 0.5, None),
          ("a/x", "delegate"): (0.5, 1.0, None), ("b/y", "decision"): (0.7, 3.0, 0.0),
          ("b/y", "inline"): (0.75, 1.5, None), ("b/y", "delegate"): (0.9, 2.5, None)}


def handmade(points):
    """Results with the same summary values on every point, as in the 13.10 table tests."""
    summary = [{"bar": 0.5, "flavor": "cost_effective", "point": index, "parent": parent,
                "strategy": strategy, "success": success, "cost_usd": cost,
                "below_bar_rate": 0.0, "delegate_rate": rate}
               for index in range(len(points))
               for (parent, strategy), (success, cost, rate) in VALUES.items()]
    return {"config": {"bars": [0.5], "seeds": [0], "flavors": ["cost_effective"],
                       "points": points, "parents": ["a/x", "b/y"]},
            "tasks": {"t": {"items": 4, "models": ["a/x", "b/y"]}}, "summary": summary}


def tpoint(context, separate, **extra):
    return dict({"context_tokens": context, "brief_tokens": 1, "result_tokens": 2,
                 "carry_turns": 0, "inline_separate_call": separate}, **extra)


TAIL = "0.600        2.0000    0.500        1.0000    0.700        1.7500    0.500"
CACHED_HEADER = ("bar  flavor          context  separate  cached  dec_success  dec_cost  inl_success"
                 "  inl_cost  del_success  del_cost  delegated")
CACHED_DASHES = ("---  --------------  -------  --------  ------  -----------  --------  -----------"
                 "  --------  -----------  --------  ---------")
BOTH_HEADER = ("bar  flavor          context  separate  calls  cached  dec_success  dec_cost"
               "  inl_success  inl_cost  del_success  del_cost  delegated")
BOTH_DASHES = ("---  --------------  -------  --------  -----  ------  -----------  --------"
               "  -----------  --------  -----------  --------  ---------")
NO_CACHED_HEADER = ("bar  flavor          context  separate  dec_success  dec_cost  inl_success"
                    "  inl_cost  del_success  del_cost  delegated")


@RED_SCRIPT
def test_table_has_a_cached_column_after_separate_when_a_point_carries_the_ratio(dr):
    got = dr.table(handmade([tpoint(10, True, cached_read_ratio=0.1), tpoint(20, True)]))
    assert got == "\n".join([CACHED_HEADER, CACHED_DASHES,
                             "0.5  cost_effective  10       True      0.1     " + TAIL,
                             "0.5  cost_effective  20       True      1.0     " + TAIL])


@RED_SCRIPT
def test_table_puts_cached_after_calls_and_prints_each_default(dr):
    got = dr.table(handmade([tpoint(10, True, work_calls=3),
                             tpoint(20, False, cached_read_ratio=0.25),
                             tpoint(30, True, cached_read_ratio=0)]))
    assert got == "\n".join([BOTH_HEADER, BOTH_DASHES,
                             "0.5  cost_effective  10       True      3      1.0     " + TAIL,
                             "0.5  cost_effective  20       False     1      0.25    " + TAIL,
                             "0.5  cost_effective  30       True      1      0       " + TAIL])


# --- what stays as it is: plain tests that pass before the code and after it ------------

# SHA-256 of json.dumps(result, sort_keys=True), taken on the v1.56 harness
V156_SHA256 = {
    "k-points": "c77d072bd18f3adcb7869574ed9f875da08d9eda6ec7e8ad372c2e9973e12f65",
    "varied": "8b4a31f69c5c2414298f7066e0eebaec543ade41f33710af6f897696935cb0c4",
}


def digest(result):
    return hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()


def test_points_without_the_ratio_give_the_v156_result_bit_for_bit():
    assert digest(run(points=POINTS + KPOINTS)) == V156_SHA256["k-points"]
    varied = run(rows=matrix(tokens=varied_tokens), reg=varied_registry(), seeds=[0, 1, 2],
                 points=POINTS + KPOINTS)
    assert digest(varied) == V156_SHA256["varied"]


def test_the_hand_expressions_without_the_ratio_are_the_v156_held_out_costs():
    reg = varied_registry()
    rows = matrix(tokens=varied_tokens)
    points = POINTS + KPOINTS
    result = run(rows=rows, reg=reg, points=points)
    for c in result["cells"]:
        p, d = reg.get(c["parent"]), reg.get(c["delegate"])
        costs = [held_out_costs(points[c["point"]], p, d, varied_tokens(i, p.id),
                                varied_tokens(i, d.id)) for i in HELD[c["seed"]]]
        assert c["cost_usd"]["inline"] == fsum(x for x, _ in costs)
        assert c["cost_usd"]["delegate"] == fsum(y for _, y in costs)


def test_the_committed_base_points_and_variant_point_0_carry_no_ratio(dr):
    base = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert all("cached_read_ratio" not in p for p in base["config"]["points"])
    variants = json.loads(VARIANTS_FILE.read_text(encoding="utf-8"))
    assert "cached_read_ratio" not in variants["config"]["points"][0]
    assert dr.table(base).split("\n", 1)[0] == NO_CACHED_HEADER
