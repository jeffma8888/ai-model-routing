"""v1.404 output re-reads in the delegation cost (DESIGN 13.1, 13.2, 13.3; row D11a), written
before the code.

``output_reread_share`` (sigma, default 1.0) is the share of each work call's output S_out that
later calls re-read: each read ``w_out * S_out`` of the v1.38 and v1.41 expressions becomes
``w_out * sigma * S_out`` and each read ``K * (S_in + S_out)`` becomes
``K * (S_in + sigma * S_out)``, on both paths and in the delegate's K-call ``select``; a tiered
call's read and tier count its S_out re-reads at sigma. The written outputs, the brief, the result,
every read of C and the context checks keep their sizes, and sigma = 1.0 (or the int 1) gives every
v1.403 cost bit for bit.

Every hand-computed case below is worked in the comment above it. The untiered models are cheap
1/2, mid 3/6 and best 10/20 USD per 1M tokens, with S_in = 2,000 and S_out = 500 (no token counts),
and in ``cost_effective`` the delegate is mid, the cheapest model that clears the 0.8 bar. The
tiered ones are those of tests/test_delegation_tiers.py: a parent ``t/long`` at 1 in and 4 out, 3
and 9 over 50,000 input tokens, and the delegate ``s/small`` at 0.1 and 0.4.
"""

import inspect
import math
from pathlib import Path

import pytest

from model_routing import Model, PriceTier, Registry, Router, Stats, Task
from model_routing import delegation
from model_routing.router import CONTEXT_TOO_SMALL

ROOT = Path(__file__).resolve().parents[1]
TASK = "review"
S_IN, S_OUT = 2000, 500
COUNTS = {"fiction/cheap": (70, 100), "fiction/mid": (95, 100), "fiction/best": (99, 100)}
FLAVORS = ("cost_effective", "cost_blind")


def models(windows=None):
    w = windows or {}
    return [Model("fiction/cheap", "small", 1.0, 2.0, w.get("fiction/cheap", 100_000)),
            Model("fiction/mid", "medium", 3.0, 6.0, w.get("fiction/mid", 100_000)),
            Model("fiction/best", "large", 10.0, 20.0, w.get("fiction/best", 100_000))]


def plain_router(windows=None):
    stats = Stats()
    for model_id, (successes, trials) in COUNTS.items():
        stats.add(TASK, model_id, successes, trials)
    task = Task(name=TASK, bar=0.8, min_samples=30, expected_input_tokens=S_IN,
                expected_output_tokens=S_OUT)
    return Router(Registry(models(windows)), {TASK: task}, stats)


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


def test_the_signature_takes_the_share_after_cached_read_ratio():
    for function in (delegation.decide_delegation, Router.decide_delegation):
        params = list(inspect.signature(function).parameters)
        assert params.index("output_reread_share") == params.index("cached_read_ratio") + 1
        param = inspect.signature(function).parameters["output_reread_share"]
        assert param.kind is inspect.Parameter.KEYWORD_ONLY
        assert param.default == 1.0 and type(param.default) is float


def test_design_states_the_share_in_13_1_and_13_2():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    s13_1 = design[design.index("### 13.1 Inputs"):design.index("### 13.2 ")]
    s13_2 = design[design.index("### 13.2 "):design.index("### 13.3 ")]
    assert "cached_read_ratio=1.0, output_reread_share=1.0, generator_model=None" in s13_1
    assert "- `output_reread_share` (sigma, v1.404, default 1.0):" in s13_1
    assert "checked after `cached_read_ratio`" in s13_1
    assert "- v1.404, output re-reads (13.1, row D11a):" in s13_2
    for term in ("`w_out * sigma * S_out`", "`K * (S_in + sigma * S_out)`",
                 "A = K * S_in + (K - 1) * sigma * S_out",
                 "B, R and every read of C keep their sizes",
                 "sigma = 1.0 gives every v1.403 cost bit for bit"):
        assert term in s13_2, term


# every combination the v1.403 code prices differently: both registries, both flavors, one call
# and several, a separate and a folded inline call, carried turns and a cached read ratio
GRID = [(tiered, flavor, k, fold, t, rho, c)
        for tiered in (False, True) for flavor in FLAVORS for k in (1, 2, 3)
        for fold in (True, False) for t in (0, 2) for rho in (1.0, 0.25)
        for c in (20_000, 45_600)]


@pytest.mark.parametrize("tiered,flavor,k,fold,t,rho,c", GRID)
def test_one_gives_the_default_bit_for_bit(tiered, flavor, k, fold, t, rho, c):
    router, parent = (tiered_router(), "t/long") if tiered else (plain_router(), "fiction/mid")
    work = {"context_tokens": c, "work_calls": k, "inline_separate_call": not fold,
            "carry_turns": t, "cached_read_ratio": rho}
    default = decide(router, parent, flavor, **work).to_dict()
    assert decide(router, parent, flavor, output_reread_share=1.0, **work).to_dict() == default
    assert decide(router, parent, flavor, output_reread_share=1, **work).to_dict() == default


# (work, inline_cost_usd, delegate_cost_usd) with parent fiction/mid and delegate fiction/mid
# (3 in, 6 out), C = 20,000, B = 300, R = 200, sigma = 0.5 unless set; w_in = 6, w_out = 3 at K = 3
PLAIN = [
    # separate, K = 3, T = 1: the work reads 3 * 20,000 + 6 * 2,000 + 3 * 0.5 * 500 = 72,750
    # and writes 1,500; each of the 1 + T = 2 later calls re-reads 3 * (2,000 + 250) = 6,750.
    # Delegated: the brief 300 out, the delegate reads 900 + 12,000 + 750 = 13,650 and writes
    # 1,500, and 2 later calls re-read B + R = 500
    ({"work_calls": 3, "carry_turns": 1},
     usd(72_750, 1_500, 3, 6) + 2 * usd(6_750, 0, 3, 6),
     usd(0, 300, 3, 6) + usd(13_650, 1_500, 3, 6) + 2 * usd(500, 0, 3, 6)),
    # folded, K = 3, T = 1: the work reads 2 * 20,000 + 12,000 + 750 = 52,750, writes 1,500, and
    # the T = 1 call after the next re-reads 6,750; the delegate path is the case above
    ({"work_calls": 3, "carry_turns": 1, "inline_separate_call": False},
     usd(52_750, 1_500, 3, 6) + usd(6_750, 0, 3, 6),
     usd(0, 300, 3, 6) + usd(13_650, 1_500, 3, 6) + 2 * usd(500, 0, 3, 6)),
    # separate, K = 1, T = 2: no work call re-reads an output, but the 3 later calls re-read
    # 2,000 + 250 = 2,250 each; the delegate's one call reads 2,300 and writes 500, as at 1.0
    ({"carry_turns": 2},
     usd(22_000, 500, 3, 6) + 3 * usd(2_250, 0, 3, 6),
     usd(0, 300, 3, 6) + usd(2_300, 500, 3, 6) + 3 * usd(500, 0, 3, 6)),
    # folded, K = 2, T = 0, sigma = 0: the work reads 20,000 + 3 * 2,000 = 26,000 and writes
    # 1,000, no call after the next; the delegate reads 600 + 6,000 = 6,600 and writes 1,000
    ({"work_calls": 2, "inline_separate_call": False, "output_reread_share": 0.0},
     usd(26_000, 1_000, 3, 6),
     usd(0, 300, 3, 6) + usd(6_600, 1_000, 3, 6) + usd(500, 0, 3, 6)),
    # separate, K = 3, T = 0, rho = 0.25, sigma = 0.25: the work reads 0.25 * 60,000 + 12,000 +
    # 3 * 125 = 27,375 and writes 1,500; the next call re-reads 3 * 2,125 = 6,375. Delegated:
    # 900 + 12,000 + 375 = 13,275 read
    ({"work_calls": 3, "cached_read_ratio": 0.25, "output_reread_share": 0.25},
     usd(27_375, 1_500, 3, 6) + usd(6_375, 0, 3, 6),
     usd(0, 300, 3, 6) + usd(13_275, 1_500, 3, 6) + usd(500, 0, 3, 6)),
]


@pytest.mark.parametrize("work,inline,delegate", PLAIN)
def test_the_share_gives_the_hand_computed_costs(work, inline, delegate):
    work = {"output_reread_share": 0.5, **work}
    decision = decide(plain_router(), "fiction/mid", **work)
    assert decision.route is not None and decision.route.primary == "fiction/mid"
    assert decision.inline_cost_usd == approx(inline)
    assert decision.delegate_cost_usd == approx(delegate)
    # the inline path is the same in both flavors
    assert decide(plain_router(), "fiction/mid", "cost_blind", **work).inline_cost_usd \
        == decision.inline_cost_usd


# (work, inline_cost_usd, delegate_cost_usd) with parent t/long and delegate s/small, C = 45,600,
# B = 300, R = 200, K = 2, sigma = 0.5
TIERED = [
    # separate, T = 0: call 1 reads 47,600 at the base prices, 49,600 = 0.0496; call 2 reads
    # 45,600 + 4,000 + 250 = 49,850, under 50,000 (at sigma = 1.0 it would read 50,100, over):
    # 49,850 + 2,000 = 0.05185; the next call adds A = 2 * 2,250 = 4,500 and reads 50,100, over:
    # 4,500 * 3 + 45,600 * (3 - 1) = 104,700. Delegated: the brief 300 * 4 = 0.0012; s/small
    # reads 2,300 then 300 + 4,000 + 250 = 4,550, (230 + 200) + (455 + 200); the next call
    # adds 500, under the threshold
    ({}, 0.0496 + 0.05185 + 0.1047, 0.0012 + 0.00043 + 0.000655 + 0.0005),
    # folded, T = 1: call 1 as above, 0.0496; the next call adds A = 4,000 + 250 = 4,250 and
    # writes 500, reading 49,850, under: 4,250 + 2,000 = 0.00625; the T = 1 call after it adds
    # 4,500, over: 0.1047. Delegated: as above with 2 later calls of 0.0005
    ({"inline_separate_call": False, "carry_turns": 1},
     0.0496 + 0.00625 + 0.1047, 0.0012 + 0.00043 + 0.000655 + 2 * 0.0005),
]


@pytest.mark.parametrize("work,inline,delegate", TIERED)
def test_a_tiered_call_takes_its_tier_at_the_scaled_read(work, inline, delegate):
    work = {"context_tokens": 45_600, "work_calls": 2, "output_reread_share": 0.5, **work}
    decision = decide(tiered_router(), "t/long", **work)
    assert decision.route.primary == "s/small"
    assert decision.inline_cost_usd == approx(inline)
    assert decision.delegate_cost_usd == approx(delegate)


def test_the_delegates_k_call_select_prices_the_share():
    # K = 3, sigma = 0.5: each candidate reads 13,650 and writes 1,500 in all
    decision = decide(plain_router(), "fiction/mid", work_calls=3, output_reread_share=0.5)
    costs = {x.model_id: x.list_cost for x in decision.route.candidates}
    assert costs["fiction/mid"] == approx(usd(13_650, 1_500, 3, 6))
    assert costs["fiction/best"] == approx(usd(13_650, 1_500, 10, 20))
    assert costs["fiction/cheap"] == approx(usd(13_650, 1_500, 1, 2))


def test_the_share_can_turn_a_delegate_cheaper_decision_inline():
    # K = 1, C = 2,500, B = R = 1,000, T = 1. At 1.0 inline is 4,500 read and 500 written, then
    # 2 * 2,500 re-read, 0.0315, against 0.006 + 0.012 + 2 * 0.006 = 0.030 delegated; at 0 the
    # re-reads are 2 * 2,000 and inline is 0.0285
    work = {"context_tokens": 2_500, "brief_tokens": 1_000, "result_tokens": 1_000,
            "carry_turns": 1}
    whole = decide(plain_router(), "fiction/mid", **work)
    none = decide(plain_router(), "fiction/mid", output_reread_share=0.0, **work)
    assert (whole.mode, whole.reason) == ("delegate", delegation.DELEGATE_CHEAPER)
    assert (none.mode, none.reason) == ("inline", delegation.INLINE_CHEAPER)
    assert whole.inline_cost_usd == approx(0.0315) and none.inline_cost_usd == approx(0.0285)
    assert whole.delegate_cost_usd == approx(0.030) == none.delegate_cost_usd


def test_the_context_checks_keep_each_output_whole():
    # K = 3, C = 20,000: inline needs 20,000 + 3 * 2,500 = 27,500, more than a 27,400 window even
    # though 20,000 + 6,000 + 0 + 500 would fit at sigma = 0
    router = plain_router({"fiction/mid": 27_400, "fiction/best": 7_500})
    decision = decide(router, "fiction/mid", work_calls=3, output_reread_share=0.0)
    assert decision.reason == delegation.PARENT_CONTEXT_FULL
    # the delegate's last call reads 300 + 6,000 + 1,000 and writes 500, 7,800 in a 7,500 window,
    # though 300 + 6,000 + 0 + 500 would fit
    reasons = {x.model_id: x.reason for x in decision.route.candidates}
    assert reasons["fiction/best"] == CONTEXT_TOO_SMALL


@pytest.mark.parametrize("value", [True, False, -0.1, 1.5, 2, -1, math.nan, math.inf, -math.inf,
                                   "0.5", None])
def test_a_share_that_is_not_a_number_from_0_to_1_raises(value):
    with pytest.raises(ValueError, match="output_reread_share"):
        decide(plain_router(), "fiction/mid", output_reread_share=value)


def test_the_share_is_checked_after_cached_read_ratio():
    with pytest.raises(ValueError, match="cached_read_ratio"):
        decide(plain_router(), "fiction/mid", cached_read_ratio=2.0, output_reread_share=2.0)


@pytest.mark.parametrize("value", [0, 0.0, 1, 1.0])
def test_the_ends_are_allowed(value):
    decide(plain_router(), "fiction/mid", output_reread_share=value)
