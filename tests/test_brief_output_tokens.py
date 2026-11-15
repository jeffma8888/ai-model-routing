"""v1.405 the brief's output charge at its own size (DESIGN 13.1, 13.2; row D11b), written before
the code.

``brief_output_tokens`` (W, default None, meaning B) is what the decision turn writes to produce
the brief, the completion of the call that writes it. W replaces B in the brief's output charge
alone, ``P.cost(0, B)`` in 13.2 and ``B * out(C)`` on a tiered parent; the delegate's read of the
brief, the parent's re-reads of B + R and the delegate's ``select`` keep B, so W moves
``delegate_cost_usd`` only, and W = B gives the None costs bit for bit.

Every hand-computed case below is worked in the comment above it. The untiered models are cheap
1/2, mid 3/6 and best 10/20 USD per 1M tokens, with S_in = 2,000 and S_out = 500 (no token counts),
and in ``cost_effective`` the delegate is mid. The tiered ones are those of
tests/test_delegation_tiers.py: a parent ``t/long`` at 1 in and 4 out, 3 and 9 over 50,000 input
tokens, and the delegate ``s/small`` at 0.1 and 0.4.
"""

import inspect
import math
from pathlib import Path

import pytest

from model_routing import Model, PriceTier, Registry, Router, Stats, Task
from model_routing import delegation

ROOT = Path(__file__).resolve().parents[1]
TASK = "review"
S_IN, S_OUT = 2000, 500
COUNTS = {"fiction/cheap": (70, 100), "fiction/mid": (95, 100), "fiction/best": (99, 100)}
FLAVORS = ("cost_effective", "cost_blind")


def plain_router():
    stats = Stats()
    for model_id, (successes, trials) in COUNTS.items():
        stats.add(TASK, model_id, successes, trials)
    task = Task(name=TASK, bar=0.8, min_samples=30, expected_input_tokens=S_IN,
                expected_output_tokens=S_OUT)
    reg = Registry([Model("fiction/cheap", "small", 1.0, 2.0, 100_000),
                    Model("fiction/mid", "medium", 3.0, 6.0, 100_000),
                    Model("fiction/best", "large", 10.0, 20.0, 100_000)])
    return Router(reg, {TASK: task}, stats)


def tiered_router():
    parent = Model("t/long", "t", 1.0, 4.0, 1_000_000, price_tiers=(PriceTier(50_000, 3.0, 9.0),))
    reg = Registry([parent, Model("s/small", "s", 0.1, 0.4, 1_000_000)])
    task = Task(name=TASK, bar=0.7, min_samples=20, independent_of_generator=False,
                expected_input_tokens=S_IN, expected_output_tokens=S_OUT)
    stats = Stats()
    for model in reg.models:
        stats.add(TASK, model.id, 95, 100)
    return Router(reg, {TASK: task}, stats)


def decide(router, parent, flavor="cost_effective", **work):
    sizes = {"context_tokens": 20_000, "brief_tokens": 300, "result_tokens": 200}
    sizes.update(work)
    return router.decide_delegation(TASK, parent, flavor, **sizes)


def usd(tokens_in, tokens_out, price_in, price_out):
    """A hand-computed token total at one model's prices."""
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def approx(value):
    return pytest.approx(value, rel=1e-12, abs=0)


def test_the_signature_takes_w_after_the_share():
    for function in (delegation.decide_delegation, Router.decide_delegation):
        params = list(inspect.signature(function).parameters)
        assert params.index("brief_output_tokens") == params.index("output_reread_share") + 1
        param = inspect.signature(function).parameters["brief_output_tokens"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY
        assert param.default is None


def test_design_states_w_in_13_1_and_13_2():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    s13_1 = design[design.index("### 13.1 Inputs"):design.index("### 13.2 ")]
    s13_2 = design[design.index("### 13.2 "):design.index("### 13.3 ")]
    assert ("output_reread_share=1.0, brief_output_tokens=None, generator_model=None"
            in s13_1)
    assert "- `brief_output_tokens` (W, v1.405, default None, meaning B):" in s13_1
    for term in ("W replaces B in the brief's output charge alone, `P.cost(0, B)` in 13.2 and "
                 "`B * out(C)` on a tiered parent",
                 "so of the two costs W moves `delegate_cost_usd` alone, and through it the 13.5 "
                 "rows that compare them, never `inline_cost_usd`",
                 "checked after `output_reread_share`",
                 "W = B gives the None costs bit for bit"):
        assert term in s13_1, term
    assert "so B (W from v1.405, 13.1) is charged once as parent output" in s13_2


def prices(model, tokens):
    """A model's prices for a call that reads ``tokens``: the fixtures' one tier is t/long's."""
    if model.price_tiers and tokens > 50_000:
        return 3.0, 9.0
    return model.price_in, model.price_out


def delegate_path(router, decision, k, t, rho, c, w, b=300, r=200):
    """``delegate_cost_usd`` with the brief written at W, written from DESIGN 13.1 v1.405 and 13.2
    v1.38, v1.41 and v1.219 apart from the code, evaluated left to right as the spec writes it."""
    p = router.registry.get(decision.parent)
    d = router.registry.get(decision.route.primary)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2

    def shared(added_in, added_out=0):
        if not p.price_tiers:
            return p.base_cost(added_in, added_out)
        price_in, price_out = prices(p, c + added_in)
        return (added_in * price_in + c * rho * (price_in - prices(p, c)[0])
                + added_out * price_out) / 1_000_000

    if d.price_tiers:
        calls = []
        for j in range(1, k + 1):
            added = j * S_IN + (j - 1) * S_OUT
            price_in, price_out = prices(d, b + added)
            calls.append(((b + added) * price_in + S_OUT * price_out) / 1_000_000)
        work = math.fsum(calls)
    else:
        work = d.base_cost(k * b + w_in * S_IN + w_out * S_OUT, k * S_OUT)
    return shared(0, w) + work + (1 + t) * shared(b + r)


# both registries, both flavors, one call and several, a separate and a folded inline call,
# carried turns, a cached read ratio, a context under and over t/long's threshold, and four W
GRID = [(tiered, flavor, k, fold, t, rho, c, w)
        for tiered in (False, True) for flavor in FLAVORS for k in (1, 3)
        for fold in (True, False) for t in (0, 2) for rho in (1.0, 0.25)
        for c in (20_000, 60_000) for w in (0, 300, 800, 5_000)]


@pytest.mark.parametrize("tiered,flavor,k,fold,t,rho,c,w", GRID)
def test_w_moves_only_the_brief_charge(tiered, flavor, k, fold, t, rho, c, w):
    router, parent = (tiered_router(), "t/long") if tiered else (plain_router(), "fiction/mid")
    work = {"context_tokens": c, "work_calls": k, "inline_separate_call": not fold,
            "carry_turns": t, "cached_read_ratio": rho}
    default = decide(router, parent, flavor, **work)
    written = decide(router, parent, flavor, brief_output_tokens=w, **work)
    assert written.delegate_cost_usd == delegate_path(router, default, k, t, rho, c, w)
    assert written.inline_cost_usd == default.inline_cost_usd
    assert written.route.to_dict() == default.route.to_dict()
    assert (written.inline_allowed, written.parent_quality_lb, written.delegate_quality_lb) \
        == (default.inline_allowed, default.parent_quality_lb, default.delegate_quality_lb)


@pytest.mark.parametrize("tiered", [False, True])
@pytest.mark.parametrize("flavor", FLAVORS)
@pytest.mark.parametrize("sigma", [1.0, 0.5])
def test_none_and_b_give_the_default_bit_for_bit(tiered, flavor, sigma):
    router, parent = (tiered_router(), "t/long") if tiered else (plain_router(), "fiction/mid")
    for work in ({}, {"work_calls": 3, "carry_turns": 2}, {"inline_separate_call": False},
                 {"context_tokens": 60_000, "cached_read_ratio": 0.25}):
        work = {"output_reread_share": sigma, **work}
        default = decide(router, parent, flavor, **work)
        for w in (None, 300):
            assert decide(router, parent, flavor, brief_output_tokens=w, **work).to_dict() \
                == default.to_dict()


# (work, delegate_cost_usd) with parent fiction/mid and delegate fiction/mid (3 in, 6 out),
# C = 20,000, B = 300, R = 200, W = 800 unless set
PLAIN = [
    # K = 1, T = 0: the brief 800 out at 6, the delegate reads 2,300 and writes 500, the next call
    # re-reads B + R = 500
    ({}, usd(0, 800, 3, 6) + usd(2_300, 500, 3, 6) + usd(500, 0, 3, 6)),
    # K = 3, T = 1, sigma = 0.5: the delegate reads 900 + 12,000 + 750 = 13,650 and writes 1,500,
    # and 2 later calls re-read 500; W is still the one brief, 800 out
    ({"work_calls": 3, "carry_turns": 1, "output_reread_share": 0.5},
     usd(0, 800, 3, 6) + usd(13_650, 1_500, 3, 6) + 2 * usd(500, 0, 3, 6)),
    # W = 0: no brief charge at all, the reads of B unchanged
    ({"brief_output_tokens": 0}, usd(2_300, 500, 3, 6) + usd(500, 0, 3, 6)),
]


@pytest.mark.parametrize("work,delegate", PLAIN)
def test_w_gives_the_hand_computed_delegate_cost(work, delegate):
    work = {"brief_output_tokens": 800, **work}
    decision = decide(plain_router(), "fiction/mid", **work)
    assert decision.route.primary == "fiction/mid"
    assert decision.delegate_cost_usd == approx(delegate)
    unset = {key: value for key, value in work.items() if key != "brief_output_tokens"}
    assert decision.inline_cost_usd \
        == decide(plain_router(), "fiction/mid", **unset).inline_cost_usd


# (C, delegate_cost_usd) with parent t/long and delegate s/small, K = 1, T = 0, B = 300, R = 200,
# W = 800: the decision turn reads C on both paths, so the brief is W at out(C)
TIERED = [
    # C = 45,600, under 50,000: the brief 800 * 4; s/small reads 2,300 and writes 500,
    # 230 + 200; the next call adds 500 and reads 46,100, under: 500 * 1
    (45_600, 0.0032 + 0.00043 + 0.0005),
    # C = 60,000, over: the brief 800 * 9; the next call adds 500 at 3, and C's tier is the
    # call's, so no dearer re-read of C
    (60_000, 0.0072 + 0.00043 + 0.0015),
    # C = 49,400, under, though C + W = 50,200 is over: the decision turn reads C alone, so
    # the brief is 800 * 4, not 800 * 9 plus a dearer re-read of C; the next call adds 500 and
    # reads 49,900, under: 500 * 1 (review iter-265 should-fix 1)
    (49_400, 0.0032 + 0.00043 + 0.0005),
]


@pytest.mark.parametrize("c,delegate", TIERED)
def test_a_tiered_parent_writes_w_at_the_tier_of_c(c, delegate):
    decision = decide(tiered_router(), "t/long", context_tokens=c, brief_output_tokens=800)
    assert decision.route.primary == "s/small"
    assert decision.delegate_cost_usd == approx(delegate)
    assert decision.inline_cost_usd \
        == decide(tiered_router(), "t/long", context_tokens=c).inline_cost_usd


def test_w_can_turn_a_delegate_cheaper_decision_inline():
    # K = 1, C = 2,500, B = R = 1,000, T = 1: inline is 4,500 read and 500 written, then
    # 2 * 2,500 re-read, 0.0315; delegated at W = B is 0.006 + 0.012 + 2 * 0.006 = 0.030, and at
    # W = 1,300 the brief is 0.0078, so 0.0318
    work = {"context_tokens": 2_500, "brief_tokens": 1_000, "result_tokens": 1_000,
            "carry_turns": 1}
    brief = decide(plain_router(), "fiction/mid", **work)
    longer = decide(plain_router(), "fiction/mid", brief_output_tokens=1_300, **work)
    assert (brief.mode, brief.reason) == ("delegate", delegation.DELEGATE_CHEAPER)
    assert (longer.mode, longer.reason) == ("inline", delegation.INLINE_CHEAPER)
    assert brief.delegate_cost_usd == approx(0.030)
    assert longer.delegate_cost_usd == approx(0.0318)
    assert brief.inline_cost_usd == longer.inline_cost_usd == approx(0.0315)


@pytest.mark.parametrize("value", [True, False, -1, 300.0, 1.5, math.nan, math.inf, "300"])
def test_a_w_that_is_not_none_or_a_count_raises(value):
    with pytest.raises(ValueError, match="brief_output_tokens"):
        decide(plain_router(), "fiction/mid", brief_output_tokens=value)


def test_w_is_checked_after_the_share():
    with pytest.raises(ValueError, match="output_reread_share"):
        decide(plain_router(), "fiction/mid", output_reread_share=2.0, brief_output_tokens=-1)


@pytest.mark.parametrize("value", [None, 0, 1, 299, 300_000])
def test_w_is_not_checked_against_b(value):
    decide(plain_router(), "fiction/mid", brief_output_tokens=value)
