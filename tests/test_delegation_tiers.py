"""DESIGN 13.2 v1.219 (row P1b): per-call price tiers in the inline-or-delegate cost.

On a model with `price_tiers` each term of 13.2 that the model's calls pay is priced call by
call: work call j reads its base context plus j inputs and j - 1 outputs and pays its own tier;
a shared parent call (the decision turn, the next call and the T after it) is charged its added
tokens A at the tier of C + A, plus the dearer re-read of C, at rho, when A takes it over a
threshold. A model without tiers keeps every v1.218 cost bit for bit.

Every hand-built case uses a parent `t/long` (1 in, 4 out; over 50,000 input tokens 3 in, 9 out)
and a delegate `s/small` (0.1 in, 0.4 out), with no token counts, so S_in = 2,000 and
S_out = 500, the task's expected sizes."""

import json
from pathlib import Path

import pytest

from model_routing import Model, PriceTier, Registry, Router, Stats, Task

ROOT = Path(__file__).resolve().parents[1]
TASK = "t"
FLAVORS = ["cost_effective", "cost_blind"]

def registry(parent_tiers=True, small=(), extra=()):
    parent = Model("t/long", "t", 1.0, 4.0, 1_000_000,
                   price_tiers=(PriceTier(50_000, 3.0, 9.0),) if parent_tiers else ())
    return Registry([parent, Model("s/small", "s", 0.1, 0.4, 1_000_000, price_tiers=small),
                     *extra])


def router(reg):
    task = Task(name=TASK, bar=0.7, min_samples=20, independent_of_generator=False,
                expected_input_tokens=2_000, expected_output_tokens=500)
    stats = Stats()
    for model in reg.models:
        stats.add(TASK, model.id, 95, 100)
    return Router(reg, {TASK: task}, stats)


def decide(reg, flavor="cost_effective", **work):
    sizes = {"brief_tokens": 300, "result_tokens": 200}
    sizes.update(work)
    return router(reg).decide_delegation(TASK, "t/long", flavor, **sizes)


def approx(value):
    return pytest.approx(value, rel=1e-12, abs=0)


# (work, inline_cost_usd, delegate_cost_usd), each worked in the comment above it
CASES = [
    # separate, K = 2, C = 47,000: call 1 reads 49,000 at base, (49,000 + 2,000) = 0.051;
    # call 2 reads 51,500 at the tier, (154,500 + 4,500) = 0.159; the next call adds
    # A = 5,000 to C, 52,000 is over: 5,000 * 3 + 47,000 * (3 - 1) = 0.109. Delegated: the
    # brief 300 * out(47,000) = 0.0012, s/small's two calls (710 + 400) = 0.00111, the next
    # call A = 500, 47,500 is under: 0.0005
    ({"context_tokens": 47_000, "work_calls": 2}, 0.319, 0.00281),
    # separate, K = 1, C = 49,800: the work call reads 51,800, (155,400 + 4,500) = 0.1599;
    # A = 2,500: 7,500 + 99,600 = 0.1071. Delegated: 0.0012 + (230 + 200) = 0.00043, and
    # A = 500 takes the next call to 50,300: 1,500 + 99,600 = 0.1011
    ({"context_tokens": 49_800}, 0.267, 0.10273),
    # rho = 0.1, as the first case: call 1 charges 4,700 + 2,000 at base with 2,000 out,
    # 0.0087; call 2 charges 4,700 + 4,500 at the tier, 27,600 + 4,500 = 0.0321; the next
    # call 15,000 + 0.1 * 47,000 * 2 = 0.0244. The delegate path takes no re-read term
    ({"context_tokens": 47_000, "work_calls": 2, "cached_read_ratio": 0.1}, 0.0652, 0.00281),
    # rho = 0.5, as the second case: the delegated next call 1,500 + 0.5 * 49,800 * 2 = 0.0513
    # and inline: the call charges 24,900 + 2,000 at the tier, 80,700 + 4,500 = 0.0852, the
    # next call 7,500 + 49,800 = 0.0573
    ({"context_tokens": 49_800, "cached_read_ratio": 0.5}, 0.1425, 0.05293),
    # folded, K = 2, T = 1, C = 47,000: call 1 reads 49,000 at base, 0.051; the next call is
    # the second work call, A = 4,500 to 51,500: 13,500 + 94,000 + 500 * 9 = 0.112; the T call
    # A = 5,000: 0.109. Delegated: 0.0012 + 0.00111 + 2 * 0.0005
    ({"context_tokens": 47_000, "work_calls": 2, "carry_turns": 1,
      "inline_separate_call": False}, 0.272, 0.00331),
    # C = 60,000 is over on its own: the brief is 300 * 9 = 0.0027, the delegated next call
    # 500 * 3 = 0.0015 with no re-read term; inline (186,000 + 4,500) + 7,500 = 0.198
    ({"context_tokens": 60_000}, 0.198, 0.00463),
]


@pytest.mark.parametrize("flavor", FLAVORS)
@pytest.mark.parametrize("work, inline, delegate", CASES)
def test_a_tiered_parent_pays_each_call_at_its_own_tier(flavor, work, inline, delegate):
    decision = decide(registry(), flavor, **work)
    assert decision.route.primary == "s/small"
    assert (decision.inline_cost_usd, decision.delegate_cost_usd) == (approx(inline),
                                                                      approx(delegate))


def test_only_the_second_work_call_crosses_the_threshold():
    """The first case with no tier on the parent costs 0.1095 inline; the tier moves only
    call 2, (51,500 + 2,000) = 0.0535 at base, and the next call, by (0.159 - 0.0535)
    + (0.109 - 0.005)."""
    without = decide(registry(parent_tiers=False), context_tokens=47_000, work_calls=2)
    tiered = decide(registry(), context_tokens=47_000, work_calls=2)
    assert without.inline_cost_usd == approx(0.1095)
    assert tiered.inline_cost_usd - without.inline_cost_usd == approx(0.1055 + 0.104)


def agreeing(decision, parent):
    primary = next(c for c in decision.route.candidates if c.model_id == decision.route.primary)
    return primary.list_cost, (parent.base_cost(0, 49_000) + primary.list_cost
                               + 1 * parent.base_cost(49_000 + 200, 0))


@pytest.mark.parametrize("flavor", FLAVORS)
def test_k1_delegate_is_charged_what_its_select_ranks_it_at(flavor):
    """s/small over 50,000 at 0.3 / 0.9 reads B + S_in = 51,000: (15,300 + 450) = 0.01575,
    below z/mid's (25,500 + 1,000) = 0.0265, so it is the primary in both flavors."""
    reg = registry(parent_tiers=False, small=(PriceTier(50_000, 0.3, 0.9),),
                   extra=[Model("z/mid", "z", 0.5, 2.0, 1_000_000)])
    decision = decide(reg, flavor, context_tokens=1_000, brief_tokens=49_000)
    assert decision.route.primary == "s/small"
    list_cost, charged = agreeing(decision, reg.get("t/long"))
    assert list_cost == approx(0.01575)
    assert decision.delegate_cost_usd == charged


@pytest.mark.parametrize("flavor", FLAVORS)
def test_k2_select_prices_a_tiered_candidate_per_call(flavor):
    """B = 47,000, K = 2: s/small's call 1 reads 49,000 at base, (4,900 + 200) = 0.0051, call 2
    reads 51,500 at the tier, (15,450 + 450) = 0.0159; z/mid's total at base, 100,500 * 0.5
    + 1,000 * 2 = 0.05225. The v1.218 total at base is (10,050 + 400) = 0.01045."""
    reg = registry(parent_tiers=False, small=(PriceTier(50_000, 0.3, 0.9),),
                   extra=[Model("z/mid", "z", 0.5, 2.0, 1_000_000)])
    decision = decide(reg, flavor, context_tokens=1_000, brief_tokens=47_000, work_calls=2,
                      result_tokens=2_200)
    assert decision.route.primary == "s/small"
    primary = next(c for c in decision.route.candidates if c.model_id == "s/small")
    mid = next(c for c in decision.route.candidates if c.model_id == "z/mid")
    assert (primary.list_cost, mid.list_cost) == (approx(0.021), approx(0.05225))
    parent = reg.get("t/long")
    assert decision.delegate_cost_usd == (parent.base_cost(0, 47_000) + primary.list_cost
                                          + 1 * parent.base_cost(47_000 + 2_200, 0))


@pytest.mark.parametrize("flavor", FLAVORS)
def test_a_tiered_parent_and_delegate_at_three_calls_with_two_tiers_each(flavor):
    """t/long over 50,000 at 3 / 9 and over 52,200 at 5 / 15; s/small over 1,000 at 0.2 / 0.8 and
    over 4,000 at 0.3 / 1.2; C = 45,000, K = 3. Inline: the calls read 47,000, 49,500 and
    52,000, (47,000 + 2,000) + (49,500 + 2,000) + (156,000 + 4,500) = 0.261; the next call adds
    7,500 to 52,500, past the second tier: 37,500 + 45,000 * (5 - 1) = 0.2175. Delegated:
    300 * 4 = 0.0012; s/small reads 2,300, 4,800 and 7,300, (460 + 400) + (1,440 + 600)
    + (2,190 + 600) = 0.00569; the next call 500 at base. t/long as a delegate would cost
    (4,300 + 6,800 + 9,300) = 0.0204, so s/small is the primary in both flavors."""
    reg = Registry([
        Model("t/long", "t", 1.0, 4.0, 1_000_000,
              price_tiers=(PriceTier(50_000, 3.0, 9.0), PriceTier(52_200, 5.0, 15.0))),
        Model("s/small", "s", 0.1, 0.4, 1_000_000,
              price_tiers=(PriceTier(1_000, 0.2, 0.8), PriceTier(4_000, 0.3, 1.2)))])
    decision = decide(reg, flavor, context_tokens=45_000, work_calls=3)
    assert decision.route.primary == "s/small"
    costs = {c.model_id: c.list_cost for c in decision.route.candidates}
    assert costs == {"s/small": approx(0.00569), "t/long": approx(0.0204)}
    assert (decision.inline_cost_usd, decision.delegate_cost_usd) == (approx(0.4785),
                                                                      approx(0.00739))


def test_a_tier_cheaper_than_the_base_makes_the_re_read_term_negative():
    """t/odd at 1 / 4, over 50,000 at 0.5 / 2; C = 49,800, K = 1. The work call reads 51,800,
    (25,900 + 1,000) = 0.0269; the next call adds 2,500 to 52,300: 1,250 + 49,800 * (0.5 - 1)
    = -0.02365, since the path lowers the price of the whole call."""
    reg = Registry([Model("t/odd", "t", 1.0, 4.0, 1_000_000,
                          price_tiers=(PriceTier(50_000, 0.5, 2.0),)),
                    Model("s/small", "s", 0.1, 0.4, 1_000_000)])
    decision = router(reg).decide_delegation(TASK, "t/odd", context_tokens=49_800,
                                             brief_tokens=300, result_tokens=200)
    assert decision.inline_cost_usd == approx(0.0269 - 0.02365)


SHAPES = [
    {"context_tokens": 47_000, "work_calls": 2},
    {"context_tokens": 49_800, "carry_turns": 3},
    {"context_tokens": 47_000, "work_calls": 3, "cached_read_ratio": 0.1},
    {"context_tokens": 60_000, "work_calls": 2, "inline_separate_call": False, "carry_turns": 1},
    {"context_tokens": 120_000, "brief_tokens": 60_000, "inline_separate_call": False},
]


@pytest.mark.parametrize("flavor", FLAVORS)
@pytest.mark.parametrize("work", SHAPES)
def test_without_tiers_every_cost_is_the_v1_218_one(flavor, work):
    """The v1.212 expressions, written out with `Model.base_cost` and compared exactly."""
    reg = registry(parent_tiers=False)
    decision = decide(reg, flavor, **work)
    p, d = reg.get("t/long"), reg.get(decision.route.primary)
    c, b, r = work["context_tokens"], work.get("brief_tokens", 300), 200
    t, k = work.get("carry_turns", 0), work.get("work_calls", 1)
    rho = work.get("cached_read_ratio", 1.0)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    s_in, s_out = 2_000, 500
    if work.get("inline_separate_call", True):
        inline = (p.base_cost(k * c * rho + w_in * s_in + w_out * s_out, k * s_out)
                  + (1 + t) * p.base_cost(k * (s_in + s_out), 0))
    else:
        inline = (p.base_cost((k - 1) * c * rho + w_in * s_in + w_out * s_out, k * s_out)
                  + t * p.base_cost(k * (s_in + s_out), 0))
    delegate = (p.base_cost(0, b) + d.base_cost(k * b + w_in * s_in + w_out * s_out, k * s_out)
                + (1 + t) * p.base_cost(b + r, 0))
    assert (decision.inline_cost_usd, decision.delegate_cost_usd) == (inline, delegate)


def test_no_committed_delegation_registry_has_a_tier():
    """So v1.219 moves no committed delegation result: the byte tests of the four committed
    delegation results files (tests/test_evidence_*delegation*.py) pass unchanged."""
    for name in ("tau2-bench-delegation", "llmrouterbench-delegation"):
        path = ROOT / "evidence" / name / "registry.json"
        assert all(m.price_tiers == () for m in Registry.load(path).models)
        assert "price_tiers" not in path.read_text(encoding="utf-8")
    # the AutoBench pool is written by its converter, which writes no tier
    assert "price_tiers" not in (ROOT / "evidence" / "autobench-2026" / "convert.py").read_text(
        encoding="utf-8")


def test_design_specifies_per_call_tiers():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for fragment in [
        "- v1.219 per-call tiers (row P1b): on a model with `price_tiers` (4.1)",
        "`A * in(C + A) + rho * C * (in(C + A) - in(C))`",
        "So with K = 1 the delegate's work term is `D.cost(B + S_in, S_out)` exactly",
        "the folded work term is the `math.fsum` of the K - 1 work calls before it",
        "- v1.219 (2026-11-10): spec and tests (row P1b).",
    ]:
        assert text.count(fragment) == 1, fragment

