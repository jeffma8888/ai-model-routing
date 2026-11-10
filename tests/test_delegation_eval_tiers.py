"""DESIGN 13.9 v1.222 (row P1c): per-call price tiers in the held-out delegation costs.

On a model with `price_tiers` each held-out cost is priced call by call as 13.2 v1.219 prices
the decision: work call j at the tier of its own read, a shared parent call charged its added
tokens at the tier of C plus them and the dearer re-read of C at rho, a folded next call as the
work's last call, and a row with per-call sizes (v1.74) on its own calls. A model without tiers
keeps every v1.221 held-out cost bit for bit.

The hand-built models are those of tests/test_delegation_tiers.py: a parent `t/long` (1 in,
4 out; over 50,000 input tokens 3 in, 9 out) and a delegate `s/small` (0.1 in, 0.4 out, here
sometimes with a tier of its own). Every row is correct, so `s/small` is the delegate in both
flavors: the cheaper in `cost_effective`, the first ID of a tie in `cost_blind`."""

from math import fsum
from pathlib import Path

import pytest

from model_routing import Model, PriceTier, Registry, Router, Stats, Task, evaluate_delegation
from model_routing.evaluate import split_items

ROOT = Path(__file__).resolve().parents[1]
TASK = "t"
ITEMS = [f"q{i}" for i in range(1, 9)]
SEEDS = [0, 1]
BAR = 0.4
FLAVORS = ["cost_effective", "cost_blind"]
RED = pytest.mark.xfail(strict=True, raises=AssertionError,
                        reason="v1.221 prices every held-out cost at the base prices (13.9 v1.222)")


def registry(parent_tiers=True, small=()):
    parent = Model("t/long", "t", 1.0, 4.0, 1_000_000,
                   price_tiers=(PriceTier(50_000, 3.0, 9.0),) if parent_tiers else ())
    return Registry([parent, Model("s/small", "s", 0.1, 0.4, 1_000_000, price_tiers=small)])


def point(**work):
    p = {"context_tokens": 0, "brief_tokens": 300, "result_tokens": 200, "carry_turns": 0,
         "inline_separate_call": True}
    p.update(work)
    return p


def run(rows, reg, points):
    return evaluate_delegation(rows, reg, bars=[BAR], points=points, seeds=SEEDS,
                               parents=["t/long"], min_samples=3)


def rows_of(sizes):
    """``sizes(index, model)`` gives the size keys of model's row for item q<index>."""
    return [dict({"task": TASK, "item": f"q{i}", "model": m, "correct": True}, **sizes(i, m))
            for i in range(1, 9) for m in ("t/long", "s/small")]


def constant(i, m):
    return {"input_tokens": 2_000, "output_tokens": 500}


def held(seed):
    return split_items(ITEMS, seed)[1]


def approx(value):
    return pytest.approx(value, rel=1e-12, abs=0)


# The six hand-worked cases of tests/test_delegation_tiers.py CASES, at S_in = 2,000 and
# S_out = 500 for both models: (work, inline cost of one call path, delegate cost), worked there
CASES = [
    ({"context_tokens": 47_000, "work_calls": 2}, 0.319, 0.00281),
    ({"context_tokens": 49_800}, 0.267, 0.10273),
    ({"context_tokens": 47_000, "work_calls": 2, "cached_read_ratio": 0.1}, 0.0652, 0.00281),
    ({"context_tokens": 49_800, "cached_read_ratio": 0.5}, 0.1425, 0.05293),
    ({"context_tokens": 47_000, "work_calls": 2, "carry_turns": 1,
      "inline_separate_call": False}, 0.272, 0.00331),
    ({"context_tokens": 60_000}, 0.198, 0.00463),
]


@RED
def test_constant_rows_cost_the_hand_worked_decision_cases_per_item():
    """Each held-out item has the sizes the decision prices, so it costs what the case does."""
    result = run(rows_of(constant), registry(), [point(**w) for w, _, _ in CASES])
    for cell in result["cells"]:
        _, inline, delegate = CASES[cell["point"]]
        n = cell["held_out_items"]
        assert cell["delegate"] == "s/small"
        assert (cell["cost_usd"]["inline"], cell["cost_usd"]["delegate"]) == (
            approx(n * inline), approx(n * delegate))


# C = 45,000, one separate call, T = 0, B = 300, R = 200. q<i>: t/long reads 1,000 * i and writes
# 200, s/small (over 5,000 at 0.3 / 0.9) reads 1,000 * i and writes 100. Costs in USD * 1e6.
# Inline: the work call reads 45,000 + 1,000 * i, at base up to 50,000 (q5 reads exactly 50,000,
# not over), then the next call adds A = 1,000 * i + 200: q1 46,800 + 1,200; q5 50,800 + (5,200 * 3
# + 45,000 * 2); q6 (153,000 + 1,800) + (18,600 + 90,000); q8 (159,000 + 1,800) + (24,600 + 90,000)
INLINE = {1: 48_000, 2: 50_000, 3: 52_000, 4: 54_000, 5: 156_400, 6: 263_400, 7: 269_400,
          8: 275_400}
# Delegated: the brief 300 * 4 = 1,200, s/small's call reads 300 + 1,000 * i, over 5,000 from q5
# (q4 430 + 40, q5 1,590 + 90), the next call A = 500 at base, 500
DELEGATE = {1: 1_870, 2: 1_970, 3: 2_070, 4: 2_170, 5: 3_380, 6: 3_680, 7: 3_980, 8: 4_280}


def growing(i, m):
    return {"input_tokens": 1_000 * i, "output_tokens": 200 if m == "t/long" else 100}


@RED
@pytest.mark.parametrize("flavor", FLAVORS)
def test_each_held_out_item_pays_the_tier_of_its_own_calls(flavor):
    reg = registry(small=(PriceTier(5_000, 0.3, 0.9),))
    result = run(rows_of(growing), reg, [point(context_tokens=45_000)])
    cells = [c for c in result["cells"] if c["flavor"] == flavor]
    assert len(cells) == len(SEEDS)
    for cell in cells:
        items = [int(i[1:]) for i in held(cell["seed"])]
        assert cell["delegate"] == "s/small"
        assert cell["cost_usd"]["inline"] == approx(fsum(INLINE[i] for i in items) / 1e6)
        assert cell["cost_usd"]["delegate"] == approx(fsum(DELEGATE[i] for i in items) / 1e6)


def per_call(i, m):
    """Two calls: reads 1,000, then 1,000 + 500 + 2,000; Rd = 2 * 1,000 + 2,000 + 500."""
    return {"input_tokens": 4_500, "output_tokens": 1_000, "call_input_tokens": [1_000, 2_000],
            "call_output_tokens": [500, 500]}


# C = 47,000. Separate: call 1 reads 48,000 at base, 48,000 + 2,000; call 2 reads 50,500 at the
# tier, 151,500 + 4,500; the next call adds A + O = 4,000 to 51,000: 12,000 + 47,000 * 2. Folded,
# T = 1: call 1 as before; the next call is call 2, A = 3,500 to 50,500, 10,500 + 94,000 + 500 * 9;
# the T call 106,000. Delegated (s/small over 2,000 at 0.3 / 0.9): the brief 1,200; call 1 reads
# 1,300, 130 + 200; call 2 reads 3,800 at the tier, 1,140 + 450; each call after it 500 at base.
# A mean per call (1,500 in) would put call 1 at 48,500 and cost 50,500 there, not 50,000
PER_CALL = [(point(context_tokens=47_000), 0.312, 0.00362),
            (point(context_tokens=47_000, carry_turns=1, inline_separate_call=False), 0.265,
             0.00412)]


@RED
def test_a_row_with_per_call_sizes_pays_each_of_its_calls_at_its_tier():
    reg = registry(small=(PriceTier(2_000, 0.3, 0.9),))
    result = run(rows_of(per_call), reg, [p for p, _, _ in PER_CALL])
    for cell in result["cells"]:
        _, inline, delegate = PER_CALL[cell["point"]]
        n = cell["held_out_items"]
        assert (cell["expected_work_calls"], cell["delegate"]) == (2, "s/small")
        assert (cell["cost_usd"]["inline"], cell["cost_usd"]["delegate"]) == (
            approx(n * inline), approx(n * delegate))


def equal_calls(i, m):
    return {"input_tokens": 3 * 2_000 + 500, "output_tokens": 1_000,
            "call_input_tokens": [2_000, 2_000], "call_output_tokens": [500, 500]}


@pytest.mark.parametrize("case", [0, 2, 4])
def test_equal_calls_price_as_the_row_without_the_keys_at_k_calls(case):
    """13.9 v1.222: on a tiered model bit for bit at any rho (case 2 has rho = 0.1)."""
    work = dict(CASES[case][0])
    reg = registry(small=(PriceTier(2_000, 0.3, 0.9),))
    single = run(rows_of(constant), reg, [point(**work)])
    del work["work_calls"]
    calls = run(rows_of(equal_calls), reg, [point(**work)])
    assert len(single["cells"]) == len(calls["cells"]) == 2 * len(SEEDS)
    for a, b in zip(single["cells"], calls["cells"]):
        assert (a["seed"], a["flavor"], a["delegate"]) == (b["seed"], b["flavor"], b["delegate"])
        assert a["cost_usd"] == b["cost_usd"]


def harness_decision(reg, flavor, seed, work):
    """The decision 13.9 makes on constant rows, rebuilt from the calibration half."""
    cal = split_items(ITEMS, seed)[0]
    stats = Stats()
    for m in reg.models:
        stats.add(TASK, m.id, len(cal), len(cal), input_tokens=2_000 * len(cal),
                  output_tokens=500 * len(cal))
    task = Task(name=TASK, bar=BAR, min_samples=3, confidence=0.95,
                independent_of_generator=False, expected_input_tokens=2_000,
                expected_output_tokens=500, on_no_model="best_available", max_fallbacks=0)
    return Router(reg, {TASK: task}, stats).decide_delegation(TASK, "t/long", flavor,
                                                              **point(**work))


TIERS = {"none": (False, ()), "parent": (True, ()), "delegate": (False, (PriceTier(2_000, 0.3, 0.9),)),
         "both": (True, (PriceTier(2_000, 0.3, 0.9),))}
SHAPES = [w for w, _, _ in CASES] + [{"context_tokens": 45_000, "work_calls": 3, "carry_turns": 2}]


@pytest.mark.parametrize("tiers", [pytest.param("none"), pytest.param("parent", marks=RED),
                                   pytest.param("delegate", marks=RED),
                                   pytest.param("both", marks=RED)])
def test_the_decision_and_its_scoring_price_the_same_calls_the_same_way(tiers):
    """On constant rows each held-out item costs the decision's own costs, bit for bit."""
    parent_tiers, small = TIERS[tiers]
    reg = registry(parent_tiers, small)
    result = run(rows_of(constant), reg, [point(**w) for w in SHAPES])
    assert len(result["cells"]) == 2 * len(SHAPES) * len(SEEDS)
    for cell in result["cells"]:
        decision = harness_decision(reg, cell["flavor"], cell["seed"], SHAPES[cell["point"]])
        n = cell["held_out_items"]
        assert (cell["mode"], cell["delegate"]) == (decision.mode, decision.route.primary)
        assert cell["cost_usd"]["inline"] == fsum([decision.inline_cost_usd] * n)
        assert cell["cost_usd"]["delegate"] == fsum([decision.delegate_cost_usd] * n)


def base_inline(p, pt, tin, tout):
    """The v1.221 held-out inline cost of a row without per-call sizes."""
    c, t, k = pt["context_tokens"], pt["carry_turns"], pt.get("work_calls", 1)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    reads = k * c if pt["inline_separate_call"] else (k - 1) * c
    if "cached_read_ratio" in pt:
        reads = reads * pt["cached_read_ratio"]
    after = (1 + t) if pt["inline_separate_call"] else t
    return (p.base_cost(reads + w_in * tin + w_out * tout, k * tout)
            + after * p.base_cost(k * (tin + tout), 0))


def base_delegate(p, d, pt, tin, tout):
    b, r, t, k = pt["brief_tokens"], pt["result_tokens"], pt["carry_turns"], pt.get("work_calls", 1)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    return (p.base_cost(0, b) + d.base_cost(k * b + w_in * tin + w_out * tout, k * tout)
            + (1 + t) * p.base_cost(b + r, 0))


BASE_SHAPES = [{"context_tokens": 45_000},
               {"context_tokens": 47_000, "work_calls": 2, "cached_read_ratio": 0.1},
               {"context_tokens": 47_000, "work_calls": 3, "carry_turns": 1,
                "inline_separate_call": False}]


def test_without_tiers_every_held_out_cost_is_the_v1_221_one():
    reg = registry(parent_tiers=False)
    p, d = reg.get("t/long"), reg.get("s/small")
    result = run(rows_of(growing), reg, [point(**w) for w in BASE_SHAPES])
    for cell in result["cells"]:
        pt = point(**BASE_SHAPES[cell["point"]])
        sizes = {i: growing(int(i[1:]), "t/long") for i in held(cell["seed"])}
        small = {i: growing(int(i[1:]), "s/small") for i in held(cell["seed"])}
        assert cell["delegate"] == "s/small"
        assert cell["cost_usd"]["inline"] == fsum(
            base_inline(p, pt, s["input_tokens"], s["output_tokens"]) for s in sizes.values())
        assert cell["cost_usd"]["delegate"] == fsum(
            base_delegate(p, d, pt, s["input_tokens"], s["output_tokens"]) for s in small.values())


def test_without_tiers_a_per_call_row_keeps_its_v1_221_cost():
    """13.9 v1.74 with K = 2, Rd = 4,500, A = 3,000 and O = 1,000 for both models."""
    reg = registry(parent_tiers=False)
    p, d = reg.get("t/long"), reg.get("s/small")
    result = run(rows_of(per_call), reg, [pt for pt, _, _ in PER_CALL])
    for cell in result["cells"]:
        c, t = 47_000, PER_CALL[cell["point"]][0]["carry_turns"]
        if PER_CALL[cell["point"]][0]["inline_separate_call"]:
            inline = p.base_cost(2 * c + 4_500, 1_000) + (1 + t) * p.base_cost(4_000, 0)
        else:
            inline = p.base_cost(c + 4_500, 1_000) + t * p.base_cost(4_000, 0)
        delegate = p.base_cost(0, 300) + d.base_cost(2 * 300 + 4_500, 1_000) + (1 + t) * p.base_cost(500, 0)
        n = cell["held_out_items"]
        assert cell["cost_usd"]["inline"] == fsum([inline] * n)
        assert cell["cost_usd"]["delegate"] == fsum([delegate] * n)


def test_design_specifies_held_out_tiers():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for fragment in [
        "- v1.222 per-call tiers in the held-out costs (row P1c): on a model with `price_tiers` (4.1)",
        "call j reading X + a_1 + ... + a_j + b_1 + ... + b_{j-1} and writing b_j",
        "A = A(i, P) + O(i, P) - b_K that writes b_K, the row's last call",
        "so the decision and its scoring price the same calls the same way",
        "- v1.222 (2026-11-10): spec and tests (row P1c).",
    ]:
        assert text.count(fragment) == 1, fragment


README_LIMITATION = (
    "- A long-prompt tier is costed per call where `models.json` gives its rates (`price_tiers`, "
    "`DESIGN.md` 4.1): a call whose input is over the tier's threshold pays the tier's prices on "
    "all of its input and output tokens, as the claude-haiku-5.5 and gpt-6-astra pages state, "
    "and the inline-or-delegate cost and the held-out costs of the delegation evidence price each "
    "work call and each later parent call at its own tier (`DESIGN.md` 13.2, 13.9). Two costs "
    "stay at the base prices, so a long-context call there is under-costed: grok-4.7 over 200K "
    "input tokens, whose page says the rates are higher without stating them, and the parent's "
    "own output in a later call that a path's additions take over a threshold. A task whose line "
    "is a whole conversation, such as `tool_calling_support_agent`, is costed as one call of the "
    "conversation's summed sizes, so a tiered model can be costed at its higher price although "
    "each of its calls is shorter")


@RED
def test_readme_limitation_names_the_two_costs_still_at_the_base_prices():
    lines = (ROOT / "README.md").read_text(encoding="utf-8").split("\n")
    assert lines.count(README_LIMITATION) == 1
    assert not any("whose registries have no tiers" in line for line in lines)
