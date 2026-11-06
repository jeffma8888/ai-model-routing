"""v1.43 multi-call work in the delegation evidence harness (DESIGN 13.9), written before
the code.

A point of ``evaluate_delegation`` may carry ``work_calls`` K, an integer >= 1 that is not
a bool. It reaches ``decide_delegation``, and the held-out cost of each item on each path
follows the 13.2 K-call expressions with that item's recorded tokens as the sizes of each
work call; the item's success is still its one recorded answer. A point without the key
means K = 1 and serialises as before. The new behaviour is committed under strict xfail
markers, each naming what the v1.42 harness raises: ``ValueError`` where a test runs a
point with ``work_calls`` (``_points`` accepts exactly the five ``POINT_KEYS``), and
``AssertionError`` where a test expects a v1.43 error message that the v1.42 key check
raises first with other words. The tests that are not marked pin that points without the
key give the v1.42 result bit for bit; they pass before the code and after it.

The fixture is the one of tests/test_delegation_eval.py: two seeds that each hold 3 items
for calibration and 5 out (seed 0 holds out q1 q2 q3 q7 q8), every call reads 1,000 tokens
and writes 200, prices per 1M tokens are big 10/40, small 1/4 and weak 0.1/0.4, and big
and small are right on every item and weak on none, so at bar 0.4 big and small clear
(3 of 3 has a 95% Wilson lower bound of 0.438) and weak does not.
"""

import hashlib
import importlib
import json
import statistics
from math import fsum
from pathlib import Path

import pytest

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
ROOT = Path(__file__).resolve().parents[1]

RUNS = pytest.mark.xfail(strict=True, raises=ValueError,
                         reason="v1.42 _points accepts exactly the five POINT_KEYS")
MESSAGE = pytest.mark.xfail(strict=True, raises=AssertionError,
                            reason="v1.42 raises a ValueError in other words: its key "
                                   "check runs first")


def point(c, b, r, t, separate):
    return {"context_tokens": c, "brief_tokens": b, "result_tokens": r, "carry_turns": t,
            "inline_separate_call": separate}


def kpoint(c, b, r, t, separate, k):
    return dict(point(c, b, r, t, separate), work_calls=k)


# the points of tests/test_delegation_eval.py, none with work_calls
POINTS = [point(100_000, 500, 300, 0, True), point(0, 500, 300, 0, False),
          point(0, 500, 300, 2, True)]
# K0: two calls of their own over a large context; K1: the same context with the last of
# two calls folded into the next one; K2: three calls, no context, the last folded, and
# two later calls that re-read what the work left
KPOINTS = [kpoint(100_000, 500, 300, 0, True, 2), kpoint(100_000, 500, 300, 0, False, 2),
           kpoint(0, 500, 300, 2, False, 3)]


def load():
    return importlib.import_module("model_routing.delegation_eval")


def registry(window=1_000_000):
    """big 10/40, small 1/4, weak 0.1/0.4 USD per 1M tokens."""
    return Registry([Model("fiction/big", "large", 10.0, 40.0, window),
                     Model("fiction/small", "small", 1.0, 4.0, window),
                     Model("fiction/weak", "tiny", 0.1, 0.4, window)])


def matrix(task="work", items=ITEMS, tokens=None, right=None):
    rows = []
    for item in items:
        for m in MODELS:
            tin, tout = (S_IN, S_OUT) if tokens is None else tokens(item, m)
            ok = RIGHT[m] if right is None else right(item, m)
            rows.append({"task": task, "item": item, "model": m, "correct": ok,
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


def stats_for(rows, cal):
    stats = Stats()
    for m in MODELS:
        own = [r for r in rows if r["model"] == m and r["item"] in cal]
        stats.add("work", m, sum(r["correct"] for r in own), len(own),
                  input_tokens=sum(r["input_tokens"] for r in own),
                  output_tokens=sum(r["output_tokens"] for r in own))
    return stats


def held_out_costs(pt, p, d, tokens_p, tokens_d):
    """One item's inline and delegated cost by the 13.9 v1.43 expressions, left to right."""
    c, b, r, t = (pt[key] for key in KEYS[:4])
    k = pt.get("work_calls", 1)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    (tin, tout), (din, dout) = tokens_p, tokens_d
    if pt["inline_separate_call"]:
        inline = (p.cost(k * c + w_in * tin + w_out * tout, k * tout)
                  + (1 + t) * p.cost(k * (tin + tout), 0))
    else:
        inline = (p.cost((k - 1) * c + w_in * tin + w_out * tout, k * tout)
                  + t * p.cost(k * (tin + tout), 0))
    delegate = (p.cost(0, b) + d.cost(k * b + w_in * din + w_out * dout, k * dout)
                + (1 + t) * p.cost(b + r, 0))
    return inline, delegate


# --- v1.43 behaviour, red until the harness takes work_calls ----------------------------

# (flavor, parent, point) -> mode, model, reason, delegate, inline and delegate cost per
# item. K0 inline reads 2 * 100,000 + 3 * 1,000 + 1 * 200 = 203,200 and writes 400, then
# the next call re-reads 2,400; K1 charges C once, 103,200 and 400 and no re-read (T = 0);
# K2 (K = 3) reads 6 * 1,000 + 3 * 200 = 6,600 and writes 600, then 2 later calls re-read
# 3,600. Delegated, K0 and K1 brief 500, the delegate reads 2 * 500 + 3,200 = 4,200 and
# writes 400, the next call re-reads 800; K2 reads 3 * 500 + 6,600 = 8,100 and writes 600,
# and 3 calls re-read 800. Priced at their K calls on the brief, small (0.0058 for K = 2)
# is cheaper than big (0.058), so cost_effective delegates to small; cost_blind ranks on
# the bounds alone, and big and small tie, as at K = 1
KNOWN = [
    ("cost_effective", "fiction/big", 0, "delegate", "fiction/small", "delegate_cheaper",
     "fiction/small", 2.072, 0.0338),
    ("cost_effective", "fiction/small", 0, "delegate", "fiction/small", "delegate_cheaper",
     "fiction/small", 0.2072, 0.0086),
    ("cost_effective", "fiction/weak", 0, "delegate", "fiction/small", "parent_below_bar",
     "fiction/small", 0.02072, 0.00608),
    ("cost_effective", "fiction/big", 1, "delegate", "fiction/small", "delegate_cheaper",
     "fiction/small", 1.048, 0.0338),
    ("cost_effective", "fiction/small", 1, "delegate", "fiction/small", "delegate_cheaper",
     "fiction/small", 0.1048, 0.0086),
    ("cost_effective", "fiction/weak", 1, "delegate", "fiction/small", "parent_below_bar",
     "fiction/small", 0.01048, 0.00608),
    ("cost_effective", "fiction/big", 2, "delegate", "fiction/small", "delegate_cheaper",
     "fiction/small", 0.162, 0.0545),
    # three calls make delegating to its own model cheaper than folding (0.0149 < 0.0162),
    # though one call of this point stays inline (0.0042 against 0.0067)
    ("cost_effective", "fiction/small", 2, "delegate", "fiction/small", "delegate_cheaper",
     "fiction/small", 0.0162, 0.0149),
    ("cost_effective", "fiction/weak", 2, "delegate", "fiction/small", "parent_below_bar",
     "fiction/small", 0.00162, 0.01094),
    ("cost_blind", "fiction/big", 0, "inline", "fiction/big", "inline_as_good",
     "fiction/big", 2.072, 0.086),
    ("cost_blind", "fiction/small", 0, "inline", "fiction/small", "inline_as_good",
     "fiction/big", 0.2072, 0.0608),
    ("cost_blind", "fiction/weak", 0, "delegate", "fiction/big", "parent_below_bar",
     "fiction/big", 0.02072, 0.05828),
    ("cost_blind", "fiction/big", 1, "inline", "fiction/big", "inline_as_good",
     "fiction/big", 1.048, 0.086),
    ("cost_blind", "fiction/weak", 1, "delegate", "fiction/big", "parent_below_bar",
     "fiction/big", 0.01048, 0.05828),
    ("cost_blind", "fiction/small", 2, "inline", "fiction/small", "inline_as_good",
     "fiction/big", 0.0162, 0.1094),
    ("cost_blind", "fiction/weak", 2, "delegate", "fiction/big", "parent_below_bar",
     "fiction/big", 0.00162, 0.10544),
]


@RUNS
@pytest.mark.parametrize("flavor,parent,p,mode,model,reason,delegate,inline_each,"
                         "delegate_each", KNOWN)
def test_known_answers_with_work_calls(flavor, parent, p, mode, model, reason, delegate,
                                       inline_each, delegate_each):
    result = run(points=KPOINTS)
    for seed in SEEDS:
        c = cell(result, flavor, parent, p, seed)
        assert (c["mode"], c["model"], c["reason"], c["delegate"]) == (mode, model, reason,
                                                                       delegate)
        assert c["below_bar"] is False and c["inline_allowed"] is True
        assert c["cost_usd"]["inline"] == pytest.approx(5 * inline_each, rel=1e-12)
        assert c["cost_usd"]["delegate"] == pytest.approx(5 * delegate_each, rel=1e-12)
        chosen = "inline" if mode == "inline" else "delegate"
        assert c["cost_usd"]["decision"] == c["cost_usd"][chosen]
        # the success is each item's one recorded answer, whatever K
        assert c["correct"] == {"decision": 5 * RIGHT[model], "inline": 5 * RIGHT[parent],
                                "delegate": 5 * RIGHT[delegate]}
        assert c["success"] == {s: c["correct"][s] / 5 for s in STRATEGIES}


@RUNS
def test_one_k2_cell_by_hand_for_each_inline_separate_call():
    big, small = registry().get("fiction/big"), registry().get("fiction/small")
    result = run(points=KPOINTS[:2], flavors=["cost_effective"], parents=["fiction/big"],
                 seeds=[0])
    # K = 2, w_in = 3, w_out = 1, C = 100,000, B = 500, R = 300, T = 0, each held-out item
    # 1,000 in and 200 out for every model; the delegate is small (see KNOWN)
    separate = big.cost(2 * 100_000 + 3 * 1000 + 1 * 200, 2 * 200) + 1 * big.cost(2 * 1200, 0)
    folded = big.cost(1 * 100_000 + 3 * 1000 + 1 * 200, 2 * 200) + 0 * big.cost(2 * 1200, 0)
    delegated = (big.cost(0, 500) + small.cost(2 * 500 + 3 * 1000 + 1 * 200, 2 * 200)
                 + 1 * big.cost(500 + 300, 0))
    assert separate == pytest.approx(2.032 + 0.016 + 0.024, rel=1e-12)
    assert folded == pytest.approx(1.032 + 0.016, rel=1e-12)
    assert delegated == pytest.approx(0.02 + 0.0042 + 0.0016 + 0.008, rel=1e-12)
    for p, inline in ((0, separate), (1, folded)):
        c = cell(result, "cost_effective", "fiction/big", p, 0)
        assert (c["mode"], c["reason"], c["delegate"]) == ("delegate", "delegate_cheaper",
                                                           "fiction/small")
        assert c["cost_usd"] == {"decision": fsum([delegated] * 5),
                                 "inline": fsum([inline] * 5),
                                 "delegate": fsum([delegated] * 5)}


def varied_tokens(item, m):
    k = int(item[1:])
    return 900 + 37 * k + 5 * MODELS.index(m), 150 + 11 * k + MODELS.index(m)


@RUNS
def test_the_decision_is_decide_delegation_with_the_points_work_calls():
    # seed 2 calibrates on 4 items, so the lower and the upper median differ
    rows = matrix(tokens=varied_tokens)
    result = run(rows=rows, seeds=[0, 1, 2], points=POINTS + KPOINTS)
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
        pt = (POINTS + KPOINTS)[c["point"]]
        d = router.decide_delegation("work", c["parent"], c["flavor"], **pt)
        assert (c["mode"], c["model"], c["reason"], c["below_bar"], c["inline_allowed"],
                c["delegate"]) == (d.mode, d.model, d.reason, d.below_bar,
                                   d.inline_allowed, d.route.primary)
        one = router.decide_delegation("work", c["parent"], c["flavor"],
                                       **{key: pt[key] for key in KEYS})
        moved += (one.mode, one.reason) != (d.mode, d.reason)
    # K reached the decision: some K-call cells decide otherwise than one call would
    assert moved > 0


@RUNS
def test_held_out_cost_follows_the_k_call_expressions_with_each_items_own_tokens():
    def tokens(item, m):
        k = int(item[1:])
        return 1013 + 977 * k + 131 * MODELS.index(m), 89 + 233 * k + 41 * MODELS.index(m)

    rows = matrix(tokens=tokens)
    reg = Registry([Model("fiction/big", "large", 2.7, 13.1, 1_000_000),
                    Model("fiction/small", "small", 0.33, 1.9, 1_000_000),
                    Model("fiction/weak", "tiny", 0.07, 0.29, 1_000_000)])
    points = KPOINTS + [kpoint(20_000, 400, 900, 1, True, 5)]
    result = run(rows=rows, reg=reg, points=points)
    for c in result["cells"]:
        p, d = reg.get(c["parent"]), reg.get(c["delegate"])
        inline, delegate = [], []
        for item in HELD[c["seed"]]:
            i, dl = held_out_costs(points[c["point"]], p, d, tokens(item, p.id),
                                   tokens(item, d.id))
            inline.append(i)
            delegate.append(dl)
        assert c["cost_usd"]["inline"] == fsum(inline)
        assert c["cost_usd"]["delegate"] == fsum(delegate)
        chosen = "inline" if c["mode"] == "inline" else "delegate"
        assert c["cost_usd"]["decision"] == c["cost_usd"][chosen]


@RUNS
def test_points_without_work_calls_keep_their_cells_beside_k_call_points():
    alone, mixed = run(), run(points=POINTS + KPOINTS)
    assert [c for c in mixed["cells"] if c["point"] < 3] == alone["cells"]
    assert [r for r in mixed["summary"] if r["point"] < 3] == alone["summary"]
    assert mixed["config"]["points"] == POINTS + KPOINTS
    for p in mixed["config"]["points"][:3]:
        assert list(p) == KEYS
    for p in mixed["config"]["points"][3:]:
        assert list(p) == KEYS + ["work_calls"]


@RUNS
def test_work_calls_1_gives_the_cells_of_the_same_point_without_it():
    explicit = [dict(p, work_calls=1) for p in POINTS]
    alone, ones = run(), run(points=explicit)
    assert ones["cells"] == alone["cells"]
    assert ones["summary"] == alone["summary"]
    # the key stays on the points that were given it
    assert ones["config"]["points"] == explicit
    for p in ones["config"]["points"]:
        assert list(p) == KEYS + ["work_calls"]


@RUNS
def test_success_is_each_items_one_recorded_answer_whatever_k():
    # small is wrong on q2, q5 and q8, weak right on q3 and q6, so counts are not 0 or 5
    def right(item, m):
        k = int(item[1:])
        return {"fiction/big": True, "fiction/small": k % 3 != 2,
                "fiction/weak": k % 3 == 0}[m]

    rows = matrix(right=right)
    result = run(rows=rows, points=[POINTS[0], dict(POINTS[0], work_calls=4)])
    for c in result["cells"]:
        if c["point"] != 1:
            continue
        held = HELD[c["seed"]]
        assert c["correct"]["inline"] == sum(right(i, c["parent"]) for i in held)
        assert c["correct"]["delegate"] == sum(right(i, c["delegate"]) for i in held)
        assert c["correct"]["decision"] == sum(right(i, c["model"]) for i in held)
        assert c["success"] == {s: c["correct"][s] / 5 for s in STRATEGIES}


@MESSAGE
@pytest.mark.parametrize("value", [0, -1, True, False, 1.5, 2.0, "2", None])
def test_an_invalid_work_calls_is_a_value_error_naming_it(value):
    with pytest.raises(ValueError, match=r"^'work_calls' must be an integer >= 1"):
        run(points=[dict(POINTS[0], work_calls=value)])


@MESSAGE
def test_work_calls_is_checked_after_inline_separate_call():
    with pytest.raises(ValueError, match=r"^'inline_separate_call' must be true or false"):
        run(points=[dict(POINTS[0], inline_separate_call=1, work_calls=0)])


@MESSAGE
@pytest.mark.parametrize("points", [
    [POINTS[0], dict(POINTS[0], work_calls=1)],
    [dict(POINTS[1], work_calls=1), POINTS[1]],
    [KPOINTS[0], dict(KPOINTS[0])],
], ids=["missing-then-1", "1-then-missing", "same-k"])
def test_a_repeated_point_is_a_value_error_with_a_missing_work_calls_read_as_1(points):
    with pytest.raises(ValueError, match=r"^points must be distinct"):
        run(points=points)


@MESSAGE
def test_a_k_call_point_with_no_delegate_is_a_value_error_naming_it():
    # in a 2,000-token window one call fits inline (1,200) and delegated (1,300), but two
    # calls fit neither: inline 2 * 1,200 = 2,400, the delegate's last call
    # 100 + 2 * 1,200 = 2,500
    one = point(0, 100, 300, 0, True)
    with pytest.raises(ValueError) as caught:
        run(reg=registry(window=2000), points=[one, dict(one, work_calls=2)],
            parents=["fiction/small"])
    message = str(caught.value)
    assert "no model fits" in message and "'fiction/small'" in message
    assert "point 1" in message


# --- what stays as it is: plain tests that pass before the code and after it ------------

def varied_registry():
    return Registry([Model("fiction/big", "large", 2.7, 13.1, 1_000_000),
                     Model("fiction/small", "small", 0.33, 1.9, 1_000_000),
                     Model("fiction/weak", "tiny", 0.07, 0.29, 1_000_000)])


def varied_rows():
    # three tasks, a different token count on every call and mixed answers, as in the
    # v1.19 determinism fixture of tests/test_delegation_eval.py
    rows = []
    for t, task in enumerate(["a", "b", "c"]):
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


VARIED_POINTS = [point(100_000, 500, 300, 0, True), point(0, 700, 450, 3, False),
                 point(20_000, 400, 900, 2, True)]

# SHA-256 of json.dumps(result, sort_keys=True), taken on the v1.42 harness
V142_SHA256 = {
    "main": "f3e40163ca964e77b8751c386d89481c2ef4dc07f99b83b1367d25f3c4bbdd15",
    "varied": "979ba32bf4376086e3d16b53faed3f8fee0e369cd675d9c8cc3fff1ed8f21b9a",
}


def digest(result):
    return hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()


def test_points_without_work_calls_give_the_v142_result_bit_for_bit():
    assert digest(run()) == V142_SHA256["main"]
    varied = run(rows=varied_rows(), reg=varied_registry(), seeds=list(range(6)),
                 points=VARIED_POINTS)
    assert digest(varied) == V142_SHA256["varied"]


def test_the_k_call_expressions_with_k_1_are_the_v142_held_out_costs():
    # the reference above, given no work_calls, reproduces every v1.42 cell exactly
    reg = varied_registry()
    rows = varied_rows()
    tokens = {(r["task"], r["item"], r["model"]): (r["input_tokens"], r["output_tokens"])
              for r in rows}
    result = run(rows=rows, reg=reg, seeds=list(range(6)), points=VARIED_POINTS)
    for c in result["cells"]:
        _, held = split_items(ITEMS, c["seed"])
        p, d = reg.get(c["parent"]), reg.get(c["delegate"])
        costs = [held_out_costs(VARIED_POINTS[c["point"]], p, d,
                                tokens[c["task"], i, p.id], tokens[c["task"], i, d.id])
                 for i in held]
        assert c["cost_usd"]["inline"] == fsum(x for x, _ in costs)
        assert c["cost_usd"]["delegate"] == fsum(y for _, y in costs)


@pytest.mark.parametrize("separate", [True, False])
def test_k_1_arguments_are_the_v142_integers(separate):
    # with K = 1 every token total of the 13.9 v1.43 expressions is the integer of the
    # v1.42 one, so the floats agree bit for bit on any prices
    reg = varied_registry()
    for c, b, r, t, tin, tout in [(0, 0, 0, 0, 0, 0), (100_000, 500, 300, 2, 1234, 567),
                                  (199_999, 7, 11, 9, 98_765, 4321)]:
        pt = point(c, b, r, t, separate)
        for p in map(reg.get, MODELS):
            for d in map(reg.get, MODELS):
                if separate:
                    inline = p.cost(c + tin, tout) + (1 + t) * p.cost(tin + tout, 0)
                else:
                    inline = p.cost(tin, tout) + t * p.cost(tin + tout, 0)
                delegate = (p.cost(0, b) + d.cost(b + tin, tout)
                            + (1 + t) * p.cost(b + r, 0))
                assert held_out_costs(pt, p, d, (tin, tout), (tin, tout)) == (inline,
                                                                              delegate)


def test_an_extra_key_beside_work_calls_is_still_a_value_error():
    with pytest.raises(ValueError):
        run(points=[dict(POINTS[0], work_calls=2, extra=1)])


def test_the_committed_delegation_config_has_no_work_calls():
    results = json.loads((ROOT / "evidence" / "delegation" / "results.json").read_text())
    for p in results["config"]["points"]:
        assert list(p) == KEYS
