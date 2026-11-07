"""v1.74 per-call sizes in the delegation evidence harness (DESIGN 13.9), written before
the code.

A row of ``evaluate_delegation`` may carry ``call_input_tokens`` and
``call_output_tokens``, two lists of the same length K: the first call's whole read and
each later call's new input, and each call's output. A held-out item is then priced on
its own K calls by position (call j reads a_1 to a_j and b_1 to b_{j-1}), each path at
the calls of the model doing the work, and the row's ``input_tokens`` and
``output_tokens`` must be what those calls read and write. The decision on such a task
reads the calibration half's median call count and rounded-up per-call means, a stated
forecast. The new behaviour is committed under strict xfail markers naming what the
v1.73 harness raises: ``AssertionError`` everywhere, since v1.73 ignores the two keys as
extra keys (DESIGN 13.9 rows), so a test sees the one-call cost of ``input_tokens`` and
``output_tokens``, no ``expected_work_calls`` and no error. The implementing commit
removes the markers. The tests that are never marked pin that rows without the keys give
the v1.73 result bit for bit, that the closed form of the reads is the sum of the calls'
reads, and that a point with ``work_calls`` 1 is the point without it; they pass before
the code and after it.

The fixture is the one of tests/test_delegation_eval_work_calls.py: two seeds that each
hold 3 items for calibration and 5 out (seed 0 holds out q1 q2 q3 q7 q8), prices per 1M
tokens are big 10/40, small 1/4 and weak 0.1/0.4, and big and small are right on every
item and weak on none, so at bar 0.4 big and small clear and weak does not.
"""

import hashlib
import importlib
import json
from math import ceil, fsum

import pytest

from model_routing import Model, Registry

ITEMS = [f"q{i}" for i in range(1, 9)]
SEEDS = [0, 1]
HELD = {0: ("q1", "q2", "q3", "q7", "q8"), 1: ("q1", "q4", "q5", "q6", "q8")}
MODELS = ["fiction/big", "fiction/small", "fiction/weak"]
RIGHT = {"fiction/big": True, "fiction/small": True, "fiction/weak": False}
S_IN, S_OUT = 1000, 200
RED = pytest.mark.xfail(strict=True, raises=AssertionError,
                        reason="v1.73 ignores the per-call keys as extra keys (DESIGN 13.9 v1.74)")


def point(c, b, r, t, separate, **extra):
    return dict({"context_tokens": c, "brief_tokens": b, "result_tokens": r,
                 "carry_turns": t, "inline_separate_call": separate}, **extra)


POINTS = [point(100_000, 500, 300, 0, True), point(0, 500, 300, 0, False),
          point(0, 500, 300, 2, True)]
# a separate call over a large context, a folded call with two later re-reads, and the
# first at a cached ratio of 0.5
UNEQUAL_POINTS = [point(100_000, 500, 300, 0, True), point(100_000, 500, 300, 2, False),
                  point(100_000, 500, 300, 0, True, cached_read_ratio=0.5)]


def load():
    return importlib.import_module("model_routing.delegation_eval")


def registry(window=1_000_000):
    """big 10/40, small 1/4, weak 0.1/0.4 USD per 1M tokens."""
    return Registry([Model("fiction/big", "large", 10.0, 40.0, window),
                     Model("fiction/small", "small", 1.0, 4.0, window),
                     Model("fiction/weak", "tiny", 0.1, 0.4, window)])


def reads(a, b):
    """Rd of DESIGN 13.9 v1.74: sum over j of (K - j + 1) * a_j + (K - j) * b_j."""
    k = len(a)
    return (sum((k - j) * x for j, x in enumerate(a))
            + sum((k - j - 1) * y for j, y in enumerate(b)))


def by_call(a, b):
    """The same total read call by call: call j reads a_1 to a_j and b_1 to b_{j-1}."""
    return sum(sum(a[:j + 1]) + sum(b[:j]) for j in range(len(a)))


def call_row(task, item, model, a, b, correct=None):
    return {"task": task, "item": item, "model": model,
            "correct": RIGHT[model] if correct is None else correct,
            "input_tokens": reads(a, b), "output_tokens": sum(b),
            "call_input_tokens": list(a), "call_output_tokens": list(b)}


def plain_matrix(task="work"):
    return [{"task": task, "item": i, "model": m, "correct": RIGHT[m],
             "input_tokens": S_IN, "output_tokens": S_OUT} for i in ITEMS for m in MODELS]


def call_matrix(calls, task="work"):
    """calls: model -> (call_input_tokens, call_output_tokens), the same on every item."""
    return [call_row(task, i, m, *calls[m]) for i in ITEMS for m in MODELS]


def run(rows, points, bars=(0.4,), reg=None):
    return load().evaluate_delegation(rows, reg or registry(), list(bars), points, seeds=SEEDS,
                                      min_samples=3)


def raises_value_error(start, fn):
    """AssertionError, never pytest's Failed, when fn does not raise the stated ValueError."""
    try:
        fn()
    except ValueError as e:
        assert str(e).startswith(start), str(e)
        return
    raise AssertionError(f"no ValueError starting {start!r}")


def expected_costs(cell, pt, calls, reg):
    """The v1.74 held-out inline and delegated costs of one cell, from DESIGN 13.9."""
    p, d = reg.get(cell["parent"]), reg.get(cell["delegate"])
    c, b, r, t = (pt[k] for k in ("context_tokens", "brief_tokens", "result_tokens",
                                  "carry_turns"))
    pa, pb = calls[p.id]
    da, db = calls[d.id]
    kp = len(pa)
    base = kp * c if pt["inline_separate_call"] else (kp - 1) * c
    if "cached_read_ratio" in pt:
        base = base * pt["cached_read_ratio"]
    if pt["inline_separate_call"]:
        inline = (p.cost(base + reads(pa, pb), sum(pb))
                  + (1 + t) * p.cost(sum(pa) + sum(pb), 0))
    else:
        inline = p.cost(base + reads(pa, pb), sum(pb)) + t * p.cost(sum(pa) + sum(pb), 0)
    delegated = (p.cost(0, b) + d.cost(len(da) * b + reads(da, db), sum(db))
                 + (1 + t) * p.cost(b + r, 0))
    n = len(HELD[cell["seed"]])
    return fsum([inline] * n), fsum([delegated] * n)


# ---- plain tests: true before the code and after it ----

def test_the_closed_form_of_the_reads_is_the_sum_of_the_calls_reads():
    cases = [([1], [2]), ([1, 9], [2, 2]), ([3_252, 55, 4_337, 7], [120, 0, 31, 900]),
             ([1_000] * 15, [200] * 15)]
    for a, b in cases:
        assert reads(a, b) == by_call(a, b)
    # review iter-072 must-fix 1: the two reads are 1 and 12, while means give 17
    assert reads([1, 9], [2, 2]) == 13
    assert 3 * 5 + 1 * 2 == 17
    for k in (1, 2, 15):
        assert reads([S_IN] * k, [S_OUT] * k) == (k * (k + 1) // 2 * S_IN
                                                  + k * (k - 1) // 2 * S_OUT)


# SHA-256 of json.dumps(result, sort_keys=True), taken on the v1.73 harness
V173_SHA = "09209f4b10570f28950aafde14f80ce49d501506c28aac1bf968200038ee9b3e"


def test_rows_without_call_keys_give_the_v1_73_result_bit_for_bit():
    tokens = {"fiction/big": (1_200, 900), "fiction/small": (800, 150),
              "fiction/weak": (5_000, 40)}
    rows = [{"task": task, "item": i, "model": m, "correct": RIGHT[m] or i in ("q2", "q5"),
             "input_tokens": tokens[m][0] + 7 * int(i[1:]), "output_tokens": tokens[m][1]}
            for task in ("alpha", "beta") for i in ITEMS for m in MODELS]
    pts = POINTS + [point(100_000, 500, 300, 0, True, work_calls=2),
                    point(64_000, 500, 500, 1, False, work_calls=15),
                    point(100_000, 500, 300, 0, True, work_calls=2, cached_read_ratio=0.25)]
    result = run(rows, pts, bars=(0.4, 0.8))
    digest = hashlib.sha256(json.dumps(result, sort_keys=True).encode()).hexdigest()
    assert digest == V173_SHA
    assert all("expected_work_calls" not in c for c in result["cells"])


def test_a_point_with_work_calls_1_is_the_point_without_it_on_per_call_rows():
    rows = call_matrix({m: ([S_IN, 300], [S_OUT, 100]) for m in MODELS})
    without = run(rows, [point(100_000, 500, 300, 0, True)])
    with_one = run(rows, [point(100_000, 500, 300, 0, True, work_calls=1)])
    assert with_one["cells"] == without["cells"]
    assert with_one["summary"] == without["summary"]


# ---- red tests: v1.74 behaviour ----

@RED
@pytest.mark.parametrize("k", [2, 3])
def test_k_equal_calls_price_as_the_plain_row_at_a_point_with_work_calls_k(k):
    rows = call_matrix({m: ([S_IN] * k, [S_OUT] * k) for m in MODELS})
    per_call = run(rows, POINTS, bars=(0.4, 0.8))
    plain = run(plain_matrix(), [dict(p, work_calls=k) for p in POINTS], bars=(0.4, 0.8))
    assert [c.get("expected_work_calls") for c in per_call["cells"]] == [k] * len(plain["cells"])
    stripped = [{key: v for key, v in c.items() if key != "expected_work_calls"}
                for c in per_call["cells"]]
    assert stripped == plain["cells"]
    assert per_call["summary"] == plain["summary"]


@RED
def test_unequal_calls_are_priced_by_position_on_each_path():
    calls = {m: ([1_000, 9_000], [200, 200]) for m in MODELS}
    assert reads(*calls["fiction/big"]) == 11_200
    reg = registry()
    result = run(call_matrix(calls), UNEQUAL_POINTS, bars=(0.4, 0.8), reg=reg)
    for cell in result["cells"]:
        inline, delegated = expected_costs(cell, UNEQUAL_POINTS[cell["point"]], calls, reg)
        assert cell["cost_usd"]["inline"] == inline
        assert cell["cost_usd"]["delegate"] == delegated
        assert cell.get("expected_work_calls") == 2
        assert (cell["expected_input_tokens"], cell["expected_output_tokens"]) == (5_000, 200)


@RED
def test_each_path_uses_the_calls_of_the_model_doing_the_work():
    calls = {"fiction/big": ([S_IN] * 3, [S_OUT] * 3), "fiction/small": ([S_IN], [S_OUT]),
             "fiction/weak": ([S_IN] * 2, [S_OUT] * 2)}
    reg = registry()
    result = run(call_matrix(calls), UNEQUAL_POINTS, reg=reg)
    for cell in result["cells"]:
        inline, delegated = expected_costs(cell, UNEQUAL_POINTS[cell["point"]], calls, reg)
        assert cell["cost_usd"]["inline"] == inline
        assert cell["cost_usd"]["delegate"] == delegated
        # median_low of the call counts 3, 1 and 2 over the three calibration items
        assert cell.get("expected_work_calls") == 2
        assert (cell["expected_input_tokens"], cell["expected_output_tokens"]) == (S_IN, S_OUT)


def _bad(change):
    rows = call_matrix({m: ([S_IN, 300], [S_OUT, 100]) for m in MODELS})
    change(rows[4])
    return rows


@RED
@pytest.mark.parametrize("change, start", [
    (lambda r: r.pop("call_output_tokens"),
     "'call_input_tokens' and 'call_output_tokens' go together"),
    (lambda r: r.pop("call_input_tokens"),
     "'call_input_tokens' and 'call_output_tokens' go together"),
    (lambda r: r.update(call_input_tokens=[]),
     "'call_input_tokens' must be a non-empty list of integers >= 0"),
    (lambda r: r.update(call_input_tokens=1_300),
     "'call_input_tokens' must be a non-empty list of integers >= 0"),
    (lambda r: r.update(call_input_tokens=[S_IN, -1]),
     "'call_input_tokens' must be a non-empty list of integers >= 0"),
    (lambda r: r.update(call_output_tokens=[S_OUT, True]),
     "'call_output_tokens' must be a non-empty list of integers >= 0"),
    (lambda r: r.update(call_output_tokens=[S_OUT, 100.0]),
     "'call_output_tokens' must be a non-empty list of integers >= 0"),
    (lambda r: r.update(call_output_tokens=[S_OUT, 100, 0]),
     "'call_input_tokens' and 'call_output_tokens' must have the same length"),
    (lambda r: r.update(input_tokens=r["input_tokens"] + 1),
     "'input_tokens' must be what the row's calls read"),
    (lambda r: r.update(output_tokens=r["output_tokens"] - 1),
     "'input_tokens' must be what the row's calls read"),
])
def test_an_invalid_per_call_row_is_refused(change, start):
    raises_value_error(start, lambda: run(_bad(change), POINTS))


@RED
def test_a_task_mixes_no_per_call_rows_with_plain_rows():
    rows = call_matrix({m: ([S_IN, 300], [S_OUT, 100]) for m in MODELS})
    plain = plain_matrix()
    rows[0] = plain[0]
    raises_value_error("task 'work': either every row or no row carries per-call sizes",
                       lambda: run(rows, POINTS))


@RED
def test_per_call_and_plain_tasks_run_together():
    rows = (call_matrix({m: ([S_IN, 300], [S_OUT, 100]) for m in MODELS}, task="calls")
            + plain_matrix(task="plain"))
    result = run(rows, POINTS)
    assert {c["task"]: c.get("expected_work_calls") for c in result["cells"]} == {
        "calls": 2, "plain": None}
    assert all("expected_work_calls" not in c for c in result["cells"] if c["task"] == "plain")


@RED
def test_a_point_with_work_calls_above_1_is_refused_on_a_per_call_task():
    rows = call_matrix({m: ([S_IN, 300], [S_OUT, 100]) for m in MODELS})
    pts = [POINTS[0], dict(POINTS[1], work_calls=2)]
    raises_value_error("point 1 sets 'work_calls' above 1 and task 'work' has per-call sizes",
                       lambda: run(rows, pts))


@RED
def test_the_decision_reads_rounded_up_per_call_means_and_the_median_call_count():
    # every model: K = 3, new inputs 1,000 + 10 + 1 and outputs 200 + 1 + 0, so the
    # rounded-up per-call means are ceil(1011 / 3) = 337 and ceil(201 / 3) = 67
    calls = {m: ([1_000, 10, 1], [200, 1, 0]) for m in MODELS}
    result = run(call_matrix(calls), POINTS)
    assert (ceil(1_011 / 3), ceil(201 / 3)) == (337, 67)
    for cell in result["cells"]:
        assert cell.get("expected_work_calls") == 3
        assert (cell["expected_input_tokens"], cell["expected_output_tokens"]) == (337, 67)
