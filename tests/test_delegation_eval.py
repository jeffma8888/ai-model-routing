"""v1.19 offline delegation evidence contract (DESIGN 13.9), written before the module exists.

They were held under a module-level strict xfail until ``delegation_eval.py``
landed; the implementing commit removed that marker (DESIGN 13.9).

The main matrix is built so every answer can be checked by hand: two seeds that
each hold 3 items for calibration and 5 out (seed 0 holds out q1 q2 q3 q7 q8,
seed 1 holds out q1 q4 q5 q6 q8), every call reads 1,000 tokens and writes 200,
`fiction/big` and `fiction/small` are right on every item and `fiction/weak` on
none. At bar 0.4, 3 of 3 has a 95% Wilson lower bound of 0.438, so the first two
clear and the third does not.
"""

import importlib
import json
import random
import statistics
from math import fsum

import pytest

import model_routing
from model_routing import Model, Registry, Router, Stats, Task
from model_routing.evaluate import split_items

ITEMS = [f"q{i}" for i in range(1, 9)]
SEEDS = [0, 1]
HELD = {0: ("q1", "q2", "q3", "q7", "q8"), 1: ("q1", "q4", "q5", "q6", "q8")}
MODELS = ["fiction/big", "fiction/small", "fiction/weak"]
RIGHT = {"fiction/big": True, "fiction/small": True, "fiction/weak": False}
S_IN, S_OUT = 1000, 200
KEYS = ["context_tokens", "brief_tokens", "result_tokens", "carry_turns",
        "inline_separate_call"]
STRATEGIES = ["decision", "inline", "delegate"]
CELL_KEYS = ["bar", "flavor", "point", "parent", "seed", "task", "calibration_items",
             "held_out_items", "expected_input_tokens", "expected_output_tokens", "mode",
             "model", "reason", "below_bar", "inline_allowed", "delegate", "correct",
             "success", "cost_usd"]
SUMMARY_KEYS = ["bar", "flavor", "point", "parent", "strategy", "success", "cost_usd",
                "below_bar_rate", "delegate_rate"]


def point(c, b, r, t, separate):
    return {"context_tokens": c, "brief_tokens": b, "result_tokens": r, "carry_turns": t,
            "inline_separate_call": separate}


# P0: a large parent context; P1: no context, the work folded into the next call;
# P2: no context, a separate call, and two later calls that re-read what it left
POINTS = [point(100_000, 500, 300, 0, True), point(0, 500, 300, 0, False),
          point(0, 500, 300, 2, True)]


def load():
    return importlib.import_module("model_routing.delegation_eval")


def registry(window=1_000_000, big_window=None, windows=None, reverse=False):
    """big 10/40, small 1/4, weak 0.1/0.4 USD per 1M tokens."""
    size = {"fiction/big": window if big_window is None else big_window,
            "fiction/small": window, "fiction/weak": window}
    size.update(windows or {})
    models = [Model("fiction/big", "large", 10.0, 40.0, size["fiction/big"]),
              Model("fiction/small", "small", 1.0, 4.0, size["fiction/small"]),
              Model("fiction/weak", "tiny", 0.1, 0.4, size["fiction/weak"])]
    return Registry(models[::-1] if reverse else models)


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


def cell(result, flavor, parent, p, seed):
    found = [c for c in result["cells"] if c["flavor"] == flavor and c["parent"] == parent
             and c["point"] == p and c["seed"] == seed]
    assert len(found) == 1
    return found[0]


# (flavor, parent, point) -> mode, model, reason, delegate, inline and delegate cost per item
KNOWN = [
    ("cost_effective", "fiction/big", 0, "delegate", "fiction/small", "delegate_cheaper",
     "fiction/small", 1.03, 0.0303),
    ("cost_effective", "fiction/big", 1, "inline", "fiction/big", "inline_cheaper",
     "fiction/small", 0.018, 0.0303),
    ("cost_effective", "fiction/big", 2, "delegate", "fiction/small", "delegate_cheaper",
     "fiction/small", 0.054, 0.0463),
    ("cost_effective", "fiction/small", 0, "delegate", "fiction/small", "delegate_cheaper",
     "fiction/small", 0.103, 0.0051),
    ("cost_effective", "fiction/small", 1, "inline", "fiction/small", "inline_cheaper",
     "fiction/small", 0.0018, 0.0051),
    ("cost_effective", "fiction/small", 2, "inline", "fiction/small", "inline_cheaper",
     "fiction/small", 0.0054, 0.0067),
    ("cost_effective", "fiction/weak", 0, "delegate", "fiction/small", "parent_below_bar",
     "fiction/small", 0.0103, 0.00258),
    ("cost_effective", "fiction/weak", 1, "delegate", "fiction/small", "parent_below_bar",
     "fiction/small", 0.00018, 0.00258),
    ("cost_effective", "fiction/weak", 2, "delegate", "fiction/small", "parent_below_bar",
     "fiction/small", 0.00054, 0.00274),
    ("cost_blind", "fiction/big", 0, "inline", "fiction/big", "inline_as_good",
     "fiction/big", 1.03, 0.051),
    ("cost_blind", "fiction/big", 2, "inline", "fiction/big", "inline_as_good",
     "fiction/big", 0.054, 0.067),
    ("cost_blind", "fiction/small", 0, "inline", "fiction/small", "inline_as_good",
     "fiction/big", 0.103, 0.0258),
    ("cost_blind", "fiction/small", 2, "inline", "fiction/small", "inline_as_good",
     "fiction/big", 0.0054, 0.0274),
    ("cost_blind", "fiction/weak", 0, "delegate", "fiction/big", "parent_below_bar",
     "fiction/big", 0.0103, 0.02328),
    ("cost_blind", "fiction/weak", 2, "delegate", "fiction/big", "parent_below_bar",
     "fiction/big", 0.00054, 0.02344),
]


@pytest.mark.parametrize("flavor,parent,p,mode,model,reason,delegate,inline_each,"
                         "delegate_each", KNOWN)
def test_known_answers_for_the_decision_and_both_baselines(flavor, parent, p, mode, model,
                                                           reason, delegate, inline_each,
                                                           delegate_each):
    result = run()
    for seed in SEEDS:
        c = cell(result, flavor, parent, p, seed)
        assert (c["mode"], c["model"], c["reason"], c["delegate"]) == (mode, model, reason,
                                                                       delegate)
        assert c["below_bar"] is False and c["inline_allowed"] is True
        assert c["calibration_items"] == 3 and c["held_out_items"] == 5
        assert (c["expected_input_tokens"], c["expected_output_tokens"]) == (S_IN, S_OUT)
        assert c["cost_usd"]["inline"] == pytest.approx(5 * inline_each, rel=1e-12)
        assert c["cost_usd"]["delegate"] == pytest.approx(5 * delegate_each, rel=1e-12)
        chosen = "inline" if mode == "inline" else "delegate"
        assert c["cost_usd"]["decision"] == c["cost_usd"][chosen]
        assert c["correct"] == {"decision": 5 * RIGHT[model], "inline": 5 * RIGHT[parent],
                                "delegate": 5 * RIGHT[delegate]}
        assert c["success"] == {s: c["correct"][s] / 5 for s in STRATEGIES}


def test_decision_is_router_decide_delegation_on_the_calibration_half():
    # seed 2 calibrates on 4 items, so 12 calibration rows, where the lower and the
    # upper median differ
    rows = matrix(tokens=lambda item, m: (900 + 37 * int(item[1:]) + 5 * MODELS.index(m),
                                          150 + 11 * int(item[1:]) + MODELS.index(m)))
    result = run(rows=rows, seeds=[0, 1, 2])
    split_sizes = set()
    for c in result["cells"]:
        cal, _ = split_items(ITEMS, c["seed"])
        split_sizes.add(len(cal))
        cal_rows = [r for r in rows if r["item"] in cal]
        s_in = statistics.median_low([r["input_tokens"] for r in cal_rows])
        s_out = statistics.median_low([r["output_tokens"] for r in cal_rows])
        assert (c["expected_input_tokens"], c["expected_output_tokens"]) == (s_in, s_out)
        stats = Stats()
        for m in MODELS:
            stats.add("work", m, len(cal) * RIGHT[m], len(cal))
        task = Task(name="work", bar=0.4, min_samples=3, confidence=0.95,
                    independent_of_generator=False, expected_input_tokens=s_in,
                    expected_output_tokens=s_out, on_no_model="best_available",
                    max_fallbacks=0)
        d = Router(registry(), {"work": task}, stats).decide_delegation(
            "work", c["parent"], c["flavor"], **POINTS[c["point"]])
        assert (c["mode"], c["model"], c["reason"], c["below_bar"], c["inline_allowed"],
                c["delegate"]) == (d.mode, d.model, d.reason, d.below_bar, d.inline_allowed,
                                   d.route.primary)
    assert split_sizes == {3, 4}


def test_held_out_cost_uses_each_items_own_tokens_for_the_model_that_did_the_work():
    def tokens(item, m):
        k = int(item[1:])
        return 1000 * k + MODELS.index(m), 100 * k + 7 * MODELS.index(m)

    rows = matrix(tokens=tokens)
    reg = registry()
    result = run(rows=rows, reg=reg, flavors=["cost_effective"], parents=["fiction/big"])
    for c in result["cells"]:
        pt = POINTS[c["point"]]
        big, sub = reg.get("fiction/big"), reg.get(c["delegate"])
        C, B, R, T = (pt[k] for k in KEYS[:4])
        inline, delegate = 0.0, 0.0
        for item in HELD[c["seed"]]:
            tin, tout = tokens(item, "fiction/big")
            if pt["inline_separate_call"]:
                inline += big.cost(C + tin, tout) + (1 + T) * big.cost(tin + tout, 0)
            else:
                inline += big.cost(tin, tout) + T * big.cost(tin + tout, 0)
            din, dout = tokens(item, c["delegate"])
            delegate += big.cost(0, B) + sub.cost(B + din, dout) + (1 + T) * big.cost(B + R, 0)
        assert c["cost_usd"]["inline"] == pytest.approx(inline, rel=1e-12)
        assert c["cost_usd"]["delegate"] == pytest.approx(delegate, rel=1e-12)


def test_parent_context_full_delegates_and_the_inline_baseline_is_still_scored():
    result = run(reg=registry(big_window=50_000), flavors=["cost_effective"],
                 parents=["fiction/big"])
    for seed in SEEDS:
        full = cell(result, "cost_effective", "fiction/big", 0, seed)
        assert (full["mode"], full["model"], full["reason"]) == (
            "delegate", "fiction/small", "parent_context_full")
        assert full["inline_allowed"] is False and full["below_bar"] is False
        assert full["cost_usd"]["inline"] == pytest.approx(5 * 1.03, rel=1e-12)
        assert full["cost_usd"]["decision"] == full["cost_usd"]["delegate"]
        fits = cell(result, "cost_effective", "fiction/big", 1, seed)
        assert fits["inline_allowed"] is True and fits["mode"] == "inline"


@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_the_delegate_baseline_is_the_route_even_when_the_decision_stays_inline(flavor):
    # big fits 1,200 tokens inline but not 1,700 delegated, small fits neither, so the
    # route falls back to weak (below the bar) and only the parent clears
    reg = registry(windows={"fiction/big": 1500, "fiction/small": 1500})
    result = run(reg=reg, flavors=[flavor], parents=["fiction/big"],
                 points=[point(0, 500, 300, 0, True)])
    for seed in SEEDS:
        c = cell(result, flavor, "fiction/big", 0, seed)
        assert (c["mode"], c["model"], c["reason"], c["delegate"]) == (
            "inline", "fiction/big", "only_parent_clears", "fiction/weak")
        assert c["below_bar"] is False and c["inline_allowed"] is True
        assert c["correct"] == {"decision": 5, "inline": 5, "delegate": 0}
        assert c["success"] == {"decision": 1.0, "inline": 1.0, "delegate": 0.0}
        assert c["cost_usd"]["inline"] == pytest.approx(5 * 0.03, rel=1e-12)
        assert c["cost_usd"]["delegate"] == pytest.approx(5 * 0.02823, rel=1e-12)
        assert c["cost_usd"]["decision"] == c["cost_usd"]["inline"]


@pytest.mark.parametrize("window,points,parent,failing", [
    # nothing fits: inline blocked, no route
    (1000, [point(0, 500, 300, 0, True)], "fiction/big", 0),
    # point 0 fits a delegate (1,300 tokens), point 1 (1,700) fits only inline
    (1500, [point(0, 100, 300, 0, True), point(0, 500, 300, 0, True)], "fiction/small", 1),
])
def test_a_cell_with_no_delegate_is_a_value_error(window, points, parent, failing):
    with pytest.raises(ValueError) as caught:
        run(reg=registry(window=window), points=points, parents=[parent])
    message = str(caught.value)
    assert "work" in message and parent in message and f"point {failing}" in message


def test_summary_rows_order_and_values():
    result = run()
    rows = result["summary"]
    expect_order = [(0.4, f, p, parent, s) for f in ["cost_effective", "cost_blind"]
                    for p in range(3) for parent in MODELS for s in STRATEGIES]
    assert [(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"])
            for r in rows] == expect_order
    for r in rows:
        assert list(r) == SUMMARY_KEYS
        group = [c for c in result["cells"] if c["flavor"] == r["flavor"]
                 and c["point"] == r["point"] and c["parent"] == r["parent"]]
        s = r["strategy"]
        assert r["success"] == sum(c["success"][s] for c in group) / 2
        assert r["cost_usd"] == pytest.approx(sum(c["cost_usd"][s] for c in group) / 2,
                                              rel=1e-12)
        assert r["below_bar_rate"] == sum(c["success"][s] < 0.4 for c in group) / 2
        if s == "decision":
            assert r["delegate_rate"] == sum(c["mode"] == "delegate" for c in group) / 2
        else:
            assert r["delegate_rate"] is None
    weak = {r["strategy"]: r for r in rows
            if (r["flavor"], r["point"], r["parent"]) == ("cost_effective", 1, "fiction/weak")}
    assert [weak[s]["success"] for s in STRATEGIES] == [1.0, 0.0, 1.0]
    assert [weak[s]["below_bar_rate"] for s in STRATEGIES] == [0.0, 1.0, 0.0]
    assert weak["decision"]["delegate_rate"] == 1.0
    assert weak["inline"]["cost_usd"] == pytest.approx(5 * 0.00018, rel=1e-12)


def test_each_bar_decides_on_its_own_bar():
    # 3 of 3 has a 95% lower bound of 0.438: at bar 0.4 big and small clear, at 0.5 none does
    result = run(bars=[0.4, 0.5])
    assert [c["bar"] for c in result["cells"]] == [0.4] * 36 + [0.5] * 36
    changed = 0
    for c in result["cells"]:
        stats = Stats()
        for m in MODELS:
            stats.add("work", m, 3 * RIGHT[m], 3)
        task = Task(name="work", bar=c["bar"], min_samples=3, confidence=0.95,
                    independent_of_generator=False, expected_input_tokens=S_IN,
                    expected_output_tokens=S_OUT, on_no_model="best_available",
                    max_fallbacks=0)
        d = Router(registry(), {"work": task}, stats).decide_delegation(
            "work", c["parent"], c["flavor"], **POINTS[c["point"]])
        assert (c["mode"], c["model"], c["reason"], c["below_bar"], c["delegate"]) == (
            d.mode, d.model, d.reason, d.below_bar, d.route.primary)
        changed += c["bar"] == 0.5 and d.below_bar
    assert changed > 0


def test_a_success_equal_to_the_bar_is_not_below_it():
    # at bar 0 a held-out success of 0 is not below the bar; at bar 1 a success of 1 is not
    rows = {(r["bar"], r["parent"], r["strategy"]): r
            for r in run(bars=[0.0, 1.0], flavors=["cost_effective"])["summary"]}
    assert rows[0.0, "fiction/weak", "inline"]["success"] == 0.0
    assert rows[0.0, "fiction/weak", "inline"]["below_bar_rate"] == 0.0
    assert rows[1.0, "fiction/big", "inline"]["success"] == 1.0
    assert rows[1.0, "fiction/big", "inline"]["below_bar_rate"] == 0.0
    assert rows[1.0, "fiction/weak", "inline"]["below_bar_rate"] == 1.0


def test_summary_success_weights_items_across_tasks_within_a_seed():
    # task b: fiction/small is right only on q1, so its held-out success differs by seed
    rows = matrix(task="a") + [dict(r, task="b", correct=(r["model"] != "fiction/weak"
                                                          and (r["model"] == "fiction/big"
                                                               or r["item"] == "q1")))
                               for r in matrix(items=ITEMS[:6])]
    result = run(rows=rows, flavors=["cost_effective"], parents=["fiction/small"],
                 points=[POINTS[1]])
    sizes = set()
    for r in result["summary"]:
        s = r["strategy"]
        per_seed, per_seed_cost = [], []
        for seed in SEEDS:
            cs = [c for c in result["cells"] if c["seed"] == seed]
            assert sorted(c["task"] for c in cs) == ["a", "b"]
            sizes.update(c["held_out_items"] for c in cs)
            per_seed.append(sum(c["correct"][s] for c in cs)
                            / sum(c["held_out_items"] for c in cs))
            per_seed_cost.append(sum(c["cost_usd"][s] for c in cs))
        assert r["success"] == pytest.approx(sum(per_seed) / 2, rel=1e-15)
        # a seed's cost is its total over both tasks, never a mean per task
        assert r["cost_usd"] == pytest.approx(sum(per_seed_cost) / 2, rel=1e-12)
    assert len(sizes) > 1


def test_cells_nest_in_the_stated_order_with_the_stated_keys():
    rows = matrix(task="b") + matrix(task="a")
    result = run(rows=rows, bars=[0.5, 0.4], flavors=["cost_blind", "cost_effective"],
                 parents=["fiction/weak", "fiction/big"], seeds=[1, 0])
    order = [(c["bar"], c["flavor"], c["point"], c["parent"], c["seed"], c["task"])
             for c in result["cells"]]
    assert order == [(b, f, p, parent, seed, t) for b in [0.5, 0.4]
                     for f in ["cost_blind", "cost_effective"] for p in range(3)
                     for parent in ["fiction/weak", "fiction/big"] for seed in [1, 0]
                     for t in ["a", "b"]]
    for c in result["cells"]:
        assert list(c) == CELL_KEYS
        for key in ("correct", "success", "cost_usd"):
            assert list(c[key]) == STRATEGIES


def test_config_and_tasks():
    result = run()
    assert list(result) == ["config", "tasks", "cells", "summary"]
    assert result["config"] == {"bars": [0.4], "seeds": SEEDS,
                                "flavors": ["cost_effective", "cost_blind"],
                                "points": POINTS, "parents": MODELS,
                                "calibration_fraction": 0.5, "min_samples": 3,
                                "confidence": 0.95}
    for p in result["config"]["points"]:
        assert list(p) == KEYS
    assert result["tasks"] == {"work": {"items": 8, "models": MODELS}}


def test_parents_default_to_every_model_ascending_and_keep_the_given_order():
    assert run()["config"]["parents"] == MODELS
    reversed_registry = run(reg=registry(reverse=True))
    assert reversed_registry["config"]["parents"] == MODELS
    assert reversed_registry["tasks"]["work"]["models"] == MODELS
    picked = run(parents=["fiction/weak", "fiction/big"])
    assert picked["config"]["parents"] == ["fiction/weak", "fiction/big"]
    assert {c["parent"] for c in picked["cells"]} == {"fiction/weak", "fiction/big"}


def test_cost_usd_in_a_row_is_ignored_for_the_list_price():
    priced = [dict(r, cost_usd=99.0) for r in matrix()]
    assert run(rows=priced) == run()


def test_same_result_for_any_row_order_and_byte_identical_json():
    rows = matrix()
    shuffled = list(rows)
    random.Random(7).shuffle(shuffled)
    a, b = run(rows=rows), run(rows=shuffled)
    assert a == b
    assert json.dumps(a, sort_keys=True) == json.dumps(b, sort_keys=True)


# A fixture on which float addition order changes the last digits: three tasks, six
# seeds, prices that are not binary fractions and a different token count on every
# call; fiction/small is wrong on q1 and q6 of task b and q3 and q8 of task c (none of
# task a), and fiction/weak is right on q3 and q6 of task a, q2, q5 and q8 of task b
# and q1, q4 and q7 of task c. On it plain left-to-right addition, or a cost
# expression written another way, gives a total or a mean that differs from the spec's
VARIED_TASKS = ["a", "b", "c"]
VARIED_SEEDS = list(range(6))
VARIED_POINTS = [point(100_000, 500, 300, 0, True), point(0, 700, 450, 3, False),
                 point(20_000, 400, 900, 2, True)]


def varied_registry():
    return Registry([Model("fiction/big", "large", 2.7, 13.1, 1_000_000),
                     Model("fiction/small", "small", 0.33, 1.9, 1_000_000),
                     Model("fiction/weak", "tiny", 0.07, 0.29, 1_000_000)])


def varied_rows():
    rows = []
    for t, task in enumerate(VARIED_TASKS):
        for item in ITEMS:
            k = int(item[1:])
            for i, m in enumerate(MODELS):
                wrong = m == "fiction/small" and k * t % 5 == 1
                rows.append({"task": task, "item": item, "model": m,
                             "correct": (RIGHT[m] and not wrong)
                             or (m == "fiction/weak" and (k + t) % 3 == 0),
                             "input_tokens": 1013 + 977 * k + 131 * i + 17 * t,
                             "output_tokens": 89 + 233 * k + 41 * i + 7 * t})
    return rows


def run_varied(rows):
    return run(rows=rows, reg=varied_registry(), seeds=VARIED_SEEDS, points=VARIED_POINTS)


def naive_sum(values):
    # plain left-to-right float addition; builtin `sum` did this before Python 3.12,
    # but from 3.12 it compensates (Neumaier) and often equals `fsum`, so it cannot
    # stand in for a naive total on every Python the suite runs on
    acc = 0.0
    for v in values:
        acc += v
    return acc


def test_costs_are_exact_fsum_totals_of_items_costed_left_to_right():
    rows, reg = varied_rows(), varied_registry()
    result = run_varied(rows)
    tokens = {(r["task"], r["item"], r["model"]): (r["input_tokens"], r["output_tokens"])
              for r in rows}
    sensitive = set()

    def total(values, level):
        values = list(values)
        if naive_sum(values) != fsum(values):
            sensitive.add(level)
        return fsum(values)

    def mean(values, level):
        values = list(values)
        if naive_sum(values) / len(values) != fsum(values) / len(values):
            sensitive.add(level)
        return fsum(values) / len(values)

    for c in result["cells"]:
        pt = VARIED_POINTS[c["point"]]
        C, B, R, T = (pt[k] for k in KEYS[:4])
        P = reg.get(c["parent"])
        _, held = split_items(ITEMS, c["seed"])

        def inline(item):
            tin, tout = tokens[c["task"], item, P.id]
            if pt["inline_separate_call"]:
                return P.cost(C + tin, tout) + (1 + T) * P.cost(tin + tout, 0)
            return P.cost(tin, tout) + T * P.cost(tin + tout, 0)

        def delegated(item, D):
            tin, tout = tokens[c["task"], item, D.id]
            return P.cost(0, B) + D.cost(B + tin, tout) + (1 + T) * P.cost(B + R, 0)

        # the same costs written another way, for the guard below
        def rescaled_inline(item):
            tin, tout = tokens[c["task"], item, P.id]
            if pt["inline_separate_call"]:
                return P.cost(C + tin, tout) + P.cost((1 + T) * (tin + tout), 0)
            return P.cost(tin, tout) + P.cost(T * (tin + tout), 0)

        def regrouped_delegated(item, D):
            tin, tout = tokens[c["task"], item, D.id]
            return P.cost(0, B) + (D.cost(B + tin, tout) + (1 + T) * P.cost(B + R, 0))

        D = reg.get(c["delegate"])
        inline_total = total((inline(i) for i in held), "items")
        delegate_total = total((delegated(i, D) for i in held), "items")
        if inline_total != fsum(rescaled_inline(i) for i in held):
            sensitive.add("separate inline rescaled" if pt["inline_separate_call"]
                          else "folded inline rescaled")
        if delegate_total != fsum(regrouped_delegated(i, D) for i in held):
            sensitive.add("delegate regrouped")
        if c["mode"] == "inline":
            decision = total((inline(i) for i in held), "items")
        else:
            decision = total((delegated(i, reg.get(c["model"])) for i in held), "items")
        assert c["cost_usd"] == {"decision": decision, "inline": inline_total,
                                "delegate": delegate_total}
    for r in result["summary"]:
        s = r["strategy"]
        group = [c for c in result["cells"] if (c["bar"], c["flavor"], c["point"], c["parent"])
                 == (r["bar"], r["flavor"], r["point"], r["parent"])]
        by_seed = [[c for c in group if c["seed"] == seed] for seed in VARIED_SEEDS]
        seed_cost = [total((c["cost_usd"][s] for c in cs), "tasks") for cs in by_seed]
        assert r["cost_usd"] == mean(seed_cost, "cost mean")
        # per-cell `correct` counts are checked against the rows by the tests above
        seed_success = [sum(c["correct"][s] for c in cs) / sum(c["held_out_items"] for c in cs)
                        for cs in by_seed]
        assert r["success"] == mean(seed_success, "success mean")
    # the fixture is sensitive at every level, each checked on the value the test
    # compares, so naive left-to-right addition (builtin `sum` before Python 3.12) or
    # a cost written another way fails an equality above; on 3.12 and later a module
    # that sums with builtin `sum` gives the same values here, so only the 3.10 and
    # 3.11 jobs catch that
    assert sensitive == {"items", "tasks", "cost mean", "success mean",
                         "separate inline rescaled", "folded inline rescaled",
                         "delegate regrouped"}
    assert {c["mode"] for c in result["cells"]} == {"inline", "delegate"}


def test_same_result_for_any_row_order_on_varied_tokens_and_tasks():
    rows = varied_rows()
    expect = run_varied(rows)
    text = json.dumps(expect, sort_keys=True)
    orders = [rows[::-1]]
    for seed in range(3):
        shuffled = list(rows)
        random.Random(seed).shuffle(shuffled)
        orders.append(shuffled)
    for order in orders:
        got = run_varied(order)
        assert got == expect
        assert json.dumps(got, sort_keys=True) == text


def test_registry_and_rows_are_not_modified():
    load()
    reg = registry()
    before = reg.models
    rows = matrix()
    copy = [dict(r) for r in rows]
    run(rows=rows, reg=reg)
    assert reg.models == before
    assert rows == copy


def test_min_samples_and_confidence_reach_the_decision():
    # 3 of 3 clears bar 0.4 at min_samples 3 and confidence 0.95 (bound 0.438), but
    # not with 4 samples required or at confidence 0.99 (bound 0.311)
    for kwargs in ({"min_samples": 4}, {"confidence": 0.99}):
        result = run(**kwargs)
        assert {c["reason"] for c in result["cells"]} == {"none_clear"}
        assert all(c["below_bar"] for c in result["cells"])
        for key, value in kwargs.items():
            assert result["config"][key] == value
    assert "none_clear" not in {c["reason"] for c in run()["cells"]}


def test_calibration_fraction_reaches_the_split():
    result = run(calibration_fraction=0.75)
    assert result["config"]["calibration_fraction"] == 0.75
    for c in result["cells"]:
        cal, held = split_items(ITEMS, c["seed"], 0.75)
        assert (c["calibration_items"], c["held_out_items"]) == (len(cal), len(held))
    assert {(c["seed"], c["calibration_items"]) for c in result["cells"]} == {(0, 5), (1, 3)}


def test_split_matches_evaluate():
    result = run()
    for c in result["cells"]:
        cal, held = split_items(ITEMS, c["seed"], 0.5)
        assert (c["calibration_items"], c["held_out_items"]) == (len(cal), len(held))
        assert held == HELD[c["seed"]]


def bad_rows(edit):
    rows = matrix()
    edit(rows)
    return rows


@pytest.mark.parametrize("rows", [
    [],
    bad_rows(lambda rs: rs.__setitem__(0, "not a dict")),
    bad_rows(lambda rs: rs[0].pop("task")),
    bad_rows(lambda rs: rs[0].__setitem__("item", "")),
    bad_rows(lambda rs: rs[0].__setitem__("model", 3)),
    bad_rows(lambda rs: rs[0].__setitem__("correct", 1)),
    bad_rows(lambda rs: rs[0].pop("input_tokens")),
    bad_rows(lambda rs: rs[0].pop("output_tokens")),
    bad_rows(lambda rs: rs[0].__setitem__("input_tokens", True)),
    bad_rows(lambda rs: rs[0].__setitem__("output_tokens", -1)),
    bad_rows(lambda rs: rs[0].__setitem__("input_tokens", 1000.0)),
    bad_rows(lambda rs: rs.append(dict(rs[0]))),
    bad_rows(lambda rs: rs.pop()),
    bad_rows(lambda rs: rs.append(dict(rs[0], model="fiction/unknown"))),
], ids=["empty", "not-dict", "no-task", "empty-item", "model-not-str", "correct-int",
        "no-input-tokens", "no-output-tokens", "bool-tokens", "negative-tokens",
        "float-tokens", "repeated", "incomplete", "not-in-registry"])
def test_bad_rows_are_value_errors(rows):
    with pytest.raises(ValueError):
        run(rows=rows)


def test_token_counts_are_required_even_with_cost_usd():
    rows = matrix()
    rows[0] = {k: v for k, v in rows[0].items() if k != "output_tokens"}
    rows[0]["cost_usd"] = 0.01
    with pytest.raises(ValueError):
        run(rows=rows)


@pytest.mark.parametrize("kwargs", [
    {"points": []},
    {"points": ["not a dict"]},
    {"points": [{k: v for k, v in POINTS[0].items() if k != "carry_turns"}]},
    {"points": [dict(POINTS[0], extra=1)]},
    {"points": [dict(POINTS[0], context_tokens=-1)]},
    {"points": [dict(POINTS[0], context_tokens=True)]},
    {"points": [dict(POINTS[0], brief_tokens=True)]},
    {"points": [dict(POINTS[0], result_tokens=True)]},
    {"points": [dict(POINTS[0], carry_turns=True)]},
    {"points": [dict(POINTS[0], result_tokens=1.5)]},
    {"points": [dict(POINTS[0], inline_separate_call=1)]},
    {"points": [POINTS[0], dict(POINTS[0])]},
    {"parents": []},
    {"parents": ["fiction/unknown"]},
    {"parents": ["fiction/big", "fiction/big"]},
    {"bars": []},
    {"bars": [True]},
    {"bars": [float("nan")]},
    {"bars": [1.5]},
    {"bars": [0.4, 0.4]},
    {"seeds": []},
    {"seeds": [True]},
    {"seeds": [0, 0]},
    {"flavors": []},
    {"flavors": ["cheapest"]},
    {"flavors": ["cost_blind", "cost_blind"]},
    {"min_samples": 0},
    {"confidence": 1.0},
    {"calibration_fraction": 0.0},
], ids=lambda kw: json.dumps(kw, default=str)[:60])
def test_bad_options_are_value_errors(kwargs):
    with pytest.raises(ValueError):
        run(**kwargs)


def test_an_empty_split_is_a_value_error():
    # seed 5 holds out only q6 and q8, so a task of q1 to q5 has an empty held-out half
    with pytest.raises(ValueError):
        run(rows=matrix(items=ITEMS[:5]), seeds=[5])


def test_exported_from_the_package():
    module = load()
    assert "evaluate_delegation" in model_routing.__all__
    assert model_routing.evaluate_delegation is module.evaluate_delegation
