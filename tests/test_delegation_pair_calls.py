"""DESIGN 13.1, 13.2 and 13.3 v1.686 (row DEL1m): a pair delegate for K > 1 work calls.

From v1.686 `decide_delegation` with `delegate_roots`, `delegate_leaves` and `work_calls` above 1
prices the pair's K work calls as 13.2 prices one delegate's K calls (v1.38, v1.219, v1.404), each
side a history of its own: call j of a side reads its base context, its j inputs and sigma times
each of its j - 1 outputs, and writes its output. With no side tokens each side is at its 5.2 sizes
on the task and its base context is B; with side tokens each is at its mean side tokens and B is
the root's base context alone. 5.2 rule 5 checks each side's window at the delegate's last call.
The fixture is DEL1a's (tests/test_select_pair.py); every hand computation is at K = 3, B = 300,
S_in = 1000 and S_out = 200, so w_in = 6 and w_out = 3 (13.2 v1.38).
"""

from math import fsum
from pathlib import Path

import pytest

from model_routing import Model
from model_routing.registry import PriceTier
from model_routing.stats import wilson_lower_bound
from decision_hash import decision_sha256
from test_delegation_pair import PAIR, SIDES, SIZES, decide, parent_terms
from test_select_pair import LEAVES, ROOTS, cost, registry, router

ROOT = Path(__file__).resolve().parents[1]
# taken on an export of v1.685 (8c82eb6) by the grid below, while a pair took one work call only,
# through decision_sha256 so a bound's last bit cannot move it by platform
PAIR_K1_SHA256 = "14e614ac02fec8aed7488663f5ebf4b23e2deeec6517df34d89a0297c306f700"
# DEL1h's side tokens over 40 side trials: root 900 in and 150 out, leaf 750 in and 176 out
LIGHT = dict(root_input_tokens=36_000, root_output_tokens=6_000, leaf_input_tokens=30_000,
             leaf_output_tokens=7_001)


def candidate(decision, model_id):
    return next(c for c in decision.route.candidates if c.model_id == model_id)


# --- 13.1 v1.686: K calls of a pair are taken, and K is still checked --------------------------

def test_a_pair_takes_k_work_calls_and_work_calls_is_still_checked_before_the_parent():
    rt = router(solo=False)
    for k in (2, 3, 7):
        assert decide(rt, "r/weak", work_calls=k, **PAIR).model == "r/strong+l/cheap"
    for bad in (0, -1, True, 1.5):
        for parent in ("r/weak", "no/such-parent"):
            with pytest.raises(ValueError, match="work_calls"):
                decide(rt, parent, work_calls=bad, **PAIR)


# --- 13.2 v1.686: each side's K calls ------------------------------------------------------------

def test_without_side_tokens_each_side_reads_the_brief_in_each_of_its_k_calls():
    rt = router(solo=False)
    d = decide(rt, "r/weak", work_calls=3, **PAIR)
    assert (d.mode, d.reason, d.below_bar, d.model) == ("delegate", "parent_below_bar", False,
                                                         "r/strong+l/cheap")
    # each side: 3 * 300 + 6 * 1000 + 3 * 200 = 7500 in, 3 * 200 = 600 out
    for c in d.route.candidates:
        root, leaf = c.model_id.split("+")
        assert c.list_cost == c.routing_cost == cost(root, 7500, 600) + cost(leaf, 7500, 600)
    brief, reads = parent_terms("r/weak")
    pair = cost("r/strong", 7500, 600) + cost("l/cheap", 7500, 600)
    assert d.delegate_cost_usd == brief + pair + reads
    assert d.delegate_quality_lb == wilson_lower_bound(39, 40, 0.95)
    # inline is as without a pair: 3 * 5000 + 6 * 1000 + 3 * 200 = 21600 in, then 3 * 1200 re-read
    assert d.inline_cost_usd == cost("r/weak", 21600, 600) + 3 * cost("r/weak", 3600, 0)
    assert d.inline_cost_usd == decide(router(), "r/weak", work_calls=3).inline_cost_usd


def test_side_tokens_put_the_brief_on_the_root_alone_in_each_of_its_k_calls():
    rt = router(pair_extra={("r/strong", "l/cheap"): LIGHT})
    d = decide(rt, "r/strong", context_tokens=50_000, work_calls=3, **PAIR)
    assert (d.mode, d.reason, d.model) == ("delegate", "delegate_cheaper", "r/strong+l/cheap")
    # root: 3 * 300 + 6 * 900 + 3 * 150 = 6750 in, 450 out; leaf: 6 * 750 + 3 * 176 = 5028 in, 528 out
    pair = cost("r/strong", 6750, 450) + cost("l/cheap", 5028, 528)
    assert candidate(d, d.model).list_cost == pair
    brief, reads = parent_terms("r/strong")
    assert d.delegate_cost_usd == brief + pair + reads
    # a pair with no side tokens on the same router still reads B on both sides
    assert candidate(d, "r/strong+l/mid").list_cost == cost("r/strong", 7500, 600) + cost("l/mid", 7500, 600)


def test_sigma_scales_each_sides_rereads_of_its_own_outputs_and_nothing_else():
    rt = router(solo=False, pair_extra={("r/strong", "l/mid"): LIGHT})
    d = decide(rt, "r/weak", work_calls=3, output_reread_share=0.5, **PAIR)
    # each side: 3 * 300 + 6 * 1000 + 3 * 0.5 * 200 = 7200 in, 600 out
    assert candidate(d, "r/strong+l/cheap").list_cost == cost("r/strong", 7200, 600) + cost("l/cheap", 7200, 600)
    # side tokens: root 900 + 5400 + 3 * 0.5 * 150 = 6525 in, leaf 4500 + 3 * 0.5 * 176 = 4764 in
    assert candidate(d, "r/strong+l/mid").list_cost == cost("r/strong", 6525, 450) + cost("l/mid", 4764, 528)
    brief, reads = parent_terms("r/weak")
    assert d.delegate_cost_usd == brief + candidate(d, d.model).list_cost + reads


def test_a_tiered_root_pays_each_of_its_k_calls_at_the_tier_of_its_own_read():
    tier = Model("r/tier", "tier", 10.0, 30.0, 100_000, price_tiers=(PriceTier(2400, 20.0, 60.0),))
    rt = router(pairs={("r/tier", "l/cheap"): 40}, reg=registry(extra=(tier,)), solo=False)
    d = rt.decide_delegation("t", "r/weak", **SIZES, work_calls=3, delegate_roots=["r/tier"],
                             delegate_leaves=["l/cheap"])
    # the root's calls read 1300, 2500 and 3700 (B + j * 1000 + (j - 1) * 200), so calls 2 and 3
    # are over 2400; without B call 2 would read 2200, under it
    root = fsum([(1300 * 10.0 + 200 * 30.0) / 1_000_000, (2500 * 20.0 + 200 * 60.0) / 1_000_000,
                 (3700 * 20.0 + 200 * 60.0) / 1_000_000])
    pair = root + cost("l/cheap", 7500, 600)
    assert d.model == "r/tier+l/cheap" and candidate(d, d.model).list_cost == pair
    brief, reads = parent_terms("r/weak")
    assert d.delegate_cost_usd == brief + pair + reads


def test_a_tiered_leaf_with_side_tokens_reads_no_brief_in_its_k_calls():
    tier = Model("l/tier", "tier", 0.1, 0.3, 100_000, price_tiers=(PriceTier(1800, 0.2, 0.6),))
    rt = router(pairs={("r/strong", "l/tier"): 40}, reg=registry(extra=(tier,)), solo=False,
                pair_extra={("r/strong", "l/tier"): LIGHT})
    d = rt.decide_delegation("t", "r/weak", **SIZES, work_calls=3, delegate_roots=["r/strong"],
                             delegate_leaves=["l/tier"])
    # the leaf's calls read 750, 1676 and 2602 (j * 750 + (j - 1) * 176), so call 3 alone is over
    # 1800; with B call 2 would read 1976, over it
    leaf = fsum([(750 * 0.1 + 176 * 0.3) / 1_000_000, (1676 * 0.1 + 176 * 0.3) / 1_000_000,
                 (2602 * 0.2 + 176 * 0.6) / 1_000_000])
    pair = cost("r/strong", 6750, 450) + leaf
    assert d.model == "r/strong+l/tier" and candidate(d, d.model).list_cost == pair
    brief, reads = parent_terms("r/weak")
    assert d.delegate_cost_usd == brief + pair + reads


def test_a_side_is_priced_per_call_at_k_calls_whatever_its_items_per_call():
    from model_routing.registry import Variant
    batch = Model("r/strong@batch", "strong", 10.0, 30.0, 100_000, variant=Variant("batch", items_per_call=2))
    rt = router(pairs={("r/strong@batch", "l/cheap"): 40}, reg=registry(extra=(batch,)), solo=False,
                pair_extra={("r/strong@batch", "l/cheap"): SIDES[("r/strong", "l/cheap")]})
    d = rt.decide_delegation("t", "r/weak", **SIZES, work_calls=3, delegate_roots=["r/strong@batch"],
                             delegate_leaves=["l/cheap"])
    # root 1200 in and 225 out per side trial: 900 + 7200 + 675 = 8775 in, 675 out, undivided;
    # leaf 750 and 175: 4500 + 525 = 5025 in, 525 out
    assert candidate(d, d.model).list_cost == cost("r/strong", 8775, 675) + cost("l/cheap", 5025, 525)


# --- 13.3 v1.686: the delegate's select_pair at K calls ----------------------------------------

@pytest.mark.parametrize("side", ["r/strong", "l/cheap"])
def test_rule_5_checks_each_sides_window_at_the_last_call_with_each_output_whole(side):
    # the last call: B + 3 * 1000 + 2 * 200 = 3700 in and 200 out, so a 3900-token window fits it
    # and a 3899 one does not, whatever sigma, and side tokens (a root at 900 and 150 would need
    # 3450) are read by no window check
    for extra in (None, {("r/strong", "l/cheap"): LIGHT}):
        for sigma in (1.0, 0.0):
            for window in (3899, 3900):
                rt = router(reg=registry(windows={side: window}), pair_extra=extra)
                d = decide(rt, "r/weak", context_tokens=2000, work_calls=3,
                           output_reread_share=sigma, **PAIR)
                mine = {c.reason for c in d.route.candidates if side in c.model_id.split("+")}
                others = {c.reason for c in d.route.candidates if side not in c.model_id.split("+")}
                assert "context_too_small" not in others
                if window == 3899:
                    assert mine == {"context_too_small"}
                else:
                    assert "context_too_small" not in mine
    # at one work call each side is checked at the briefed call, 1000 + 300 + 200 = 1500 (v1.684)
    for window, refused in ((1499, True), (1500, False)):
        rt = router(reg=registry(windows={side: window}))
        reasons = {c.reason for c in decide(rt, "r/weak", context_tokens=2000, **PAIR).route.candidates
                   if side in c.model_id.split("+")}
        assert (reasons == {"context_too_small"}) is refused


def test_cost_blind_takes_the_best_bound_at_k_calls_and_charges_its_k_calls():
    rt = router()
    d = decide(rt, "r/weak", "cost_blind", context_tokens=2000, work_calls=3, **PAIR)
    assert (d.mode, d.reason, d.route.primary) == ("inline", "inline_as_good", "r/strong+l/dear")
    assert all(c.routing_cost == 0.0 for c in d.route.candidates)
    brief, reads = parent_terms("r/weak")
    assert d.delegate_cost_usd == brief + (cost("r/strong", 7500, 600) + cost("l/dear", 7500, 600)) + reads


def test_k_calls_of_a_pair_leave_the_router_as_it_was(tmp_path):
    rt = router(pair_extra={("r/strong", "l/cheap"): LIGHT})
    tasks = dict(rt.tasks)
    rt.stats.save(tmp_path / "before.json")
    for k in (2, 3):
        decide(rt, "r/strong", context_tokens=50_000, work_calls=k, **PAIR)
    rt.stats.save(tmp_path / "after.json")
    assert rt.tasks == tasks
    assert (tmp_path / "after.json").read_bytes() == (tmp_path / "before.json").read_bytes()


# --- unchanged: every pair decision at one work call ---------------------------------------------

def pair_grid():
    out = []
    for solo in (True, False):
        for extra in (None, SIDES):
            rt = router(solo=solo, pair_extra=extra)
            for parent in ROOTS + LEAVES:
                for flavor in ("cost_effective", "cost_blind"):
                    for folded in (True, False):
                        for sigma in (1.0, 0.5):
                            try:
                                out.append(rt.decide_delegation(
                                    "t", parent, flavor, context_tokens=5000, brief_tokens=300,
                                    result_tokens=150, carry_turns=2, inline_separate_call=folded,
                                    output_reread_share=sigma, **PAIR).to_dict())
                            except Exception as exc:
                                out.append([type(exc).__name__, str(exc)])
    return out


def test_every_pair_decision_at_one_work_call_keeps_its_v1_685_bytes():
    grid = pair_grid()
    assert len(grid) == 224
    assert decision_sha256(grid) == PAIR_K1_SHA256


# --- the spec ------------------------------------------------------------------------------------

def test_design_states_k_calls_of_a_pair_in_13_1_13_2_13_3_and_7():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    s7 = design[design.index("## 7. "):design.index("## 8. ")]
    s13_1 = design[design.index("### 13.1 Inputs"):design.index("### 13.2 ")]
    s13_2 = design[design.index("### 13.2 "):design.index("### 13.3 ")]
    s13_3 = design[design.index("### 13.3 "):design.index("### 13.4 ")]
    assert "raised `ValueError` naming `work_calls` until v1.686 (row DEL1m)" in s13_1
    assert "not priced in this version" not in s13_1
    assert "- v1.686 K calls of a pair delegate (row DEL1m, 13.3 v1.686):" in s13_2
    assert "- v1.686 K calls of a pair (row DEL1m, 13.1 and 13.2 v1.686):" in s13_3
    assert "  - Tests (tests/test_delegation_pair_calls.py):" in s13_3
    assert "K > 1 work calls on a pair (row DEL1m)" not in s13_3
    assert "a pair delegate for K > 1 work calls (row DEL1m)" not in s7
    assert "a pair decision of K > 1 work calls (13.3 v1.686, row DEL1m)" in s7
