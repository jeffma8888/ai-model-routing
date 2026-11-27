"""DESIGN 13.1, 13.2 and 13.3 v1.684, 7 v1.684 (row DEL1h): a pair in the delegation decision.

`decide_delegation(..., delegate_roots=..., delegate_leaves=...)` hands the work to a delegating
harness: the delegate is `select_pair` on the briefed task, and the delegate path is priced at the
pair's `list_cost` there, each side at its 5.2 sizes on the briefed task (so each reads B), or at its
mean side tokens with B on the root alone. K > 1 work calls on a pair, which raised `ValueError`
until v1.686, are tests/test_delegation_pair_calls.py's (row DEL1m). The fixture is DEL1a's
(tests/test_select_pair.py).
"""

import inspect
import json
from pathlib import Path

import pytest

from model_routing import FakeProvider, Model, Monitor, Policy, Router, delegation
from model_routing.registry import Variant
from model_routing.stats import wilson_lower_bound
from decision_hash import decision_sha256
from test_select_pair import LEAVES, ROOTS, cost, registry, router

ROOT = Path(__file__).resolve().parents[1]
SIZES = dict(context_tokens=5000, brief_tokens=300, result_tokens=150, carry_turns=2)
PAIR = dict(delegate_roots=ROOTS, delegate_leaves=LEAVES)
# taken on an export of v1.683 (6b5ee61) by the grid below, before the keywords existed, through
# decision_sha256 so a bound's last bit cannot move it by platform (tests/test_decision_hash_pins.py)
NO_PAIR_SHA256 = "82d8d7fc59ddbb0160a92b2d87863213c8368d15d81d0c7a4150c3e68e952542"
SIDES = {("r/strong", "l/cheap"): dict(root_input_tokens=48000, root_output_tokens=9000,
                                       leaf_input_tokens=30000, leaf_output_tokens=7000)}


def decide(rt, parent, flavor="cost_effective", **kwargs):
    return rt.decide_delegation("t", parent, flavor, **{**SIZES, **kwargs})


def parent_terms(parent, b=300, r=150, t=2):
    """13.2: the brief written once, then B + R re-read by the next call and the T after it."""
    return cost(parent, 0, b), (1 + t) * cost(parent, b + r, 0)


# --- 13.1 v1.684: the keywords and their checks ------------------------------------------------

def test_the_signature_ends_with_the_two_keywords_defaulting_to_none():
    for function in (delegation.decide_delegation, Router.decide_delegation):
        params = inspect.signature(function).parameters
        # v1.691 (row DEL3): `depth` follows them, tests/test_delegation_depth.py
        assert list(params)[-4:-1] == ["policy", "delegate_roots", "delegate_leaves"]
        for name in ("delegate_roots", "delegate_leaves"):
            assert params[name].kind is inspect.Parameter.KEYWORD_ONLY
            assert params[name].default is None


@pytest.mark.parametrize("given", [dict(delegate_roots=ROOTS), dict(delegate_leaves=LEAVES)])
def test_one_without_the_other_raises_after_policy_and_before_the_parent(given):
    rt = router()
    with pytest.raises(ValueError, match="delegate_roots and delegate_leaves"):
        decide(rt, "r/weak", **given)
    with pytest.raises(ValueError, match="delegate_roots and delegate_leaves"):
        decide(rt, "no/such-parent", **given)
    with pytest.raises(ValueError, match="policy"):
        decide(rt, "r/weak", policy="not a policy", **given)


def test_select_pair_checks_the_lists_after_the_parent():
    rt = router()
    with pytest.raises(ValueError, match="roots must be a non-empty"):
        decide(rt, "r/weak", delegate_roots=[], delegate_leaves=LEAVES)
    with pytest.raises(ValueError, match="leaves names a model twice"):
        decide(rt, "r/weak", delegate_roots=ROOTS, delegate_leaves=["l/cheap", "l/cheap"])
    with pytest.raises(KeyError):
        decide(rt, "r/weak", delegate_roots=["r/none"], delegate_leaves=LEAVES)
    with pytest.raises(KeyError):
        decide(rt, "no/such-parent", delegate_roots=[], delegate_leaves=LEAVES)


# --- 13.2 and 13.3 v1.684: the pair as the delegate ----------------------------------------------

def test_a_parent_that_does_not_clear_delegates_to_the_cheapest_admitted_pair():
    rt = router(solo=False)
    d = decide(rt, "r/weak", **PAIR)
    assert (d.mode, d.reason, d.below_bar, d.model) == ("delegate", "parent_below_bar", False,
                                                         "r/strong+l/cheap")
    assert d.route.primary == "r/strong+l/cheap"
    assert [c.model_id for c in d.route.candidates] == [f"{r}+{l}" for r in ROOTS for l in LEAVES]
    assert d.delegate_quality_lb == wilson_lower_bound(39, 40, 0.95)
    brief, reads = parent_terms("r/weak")
    # each side at its 5.2 sizes on the briefed task: 1000 + B in, 200 out
    assert d.delegate_cost_usd == brief + (cost("r/strong", 1300) + cost("l/cheap", 1300)) + reads
    # 13.2: the parent unmeasured, at the task's sizes, in a call of its own over C
    assert d.inline_cost_usd == cost("r/weak", 6000) + 3 * cost("r/weak", 1200, 0)


def test_a_parent_that_costs_more_delegates_to_the_pair_as_delegate_cheaper():
    rt = router()
    d = decide(rt, "r/strong", context_tokens=50_000, **PAIR)
    brief, reads = parent_terms("r/strong")
    assert (d.mode, d.reason, d.model) == ("delegate", "delegate_cheaper", "r/strong+l/cheap")
    assert d.delegate_cost_usd == brief + (cost("r/strong", 1300) + cost("l/cheap", 1300)) + reads
    assert d.inline_cost_usd == cost("r/strong", 51_000) + 3 * cost("r/strong", 1200, 0)
    assert d.delegate_cost_usd < d.inline_cost_usd


def test_a_cheap_parent_that_clears_works_inline_in_both_flavors():
    rt = router()
    d = decide(rt, "r/weak", context_tokens=2000, **PAIR)
    brief, reads = parent_terms("r/weak")
    assert (d.mode, d.reason, d.model) == ("inline", "inline_cheaper", "r/weak")
    assert d.route.primary == "r/strong+l/cheap"
    assert d.delegate_cost_usd == brief + (cost("r/strong", 1300) + cost("l/cheap", 1300)) + reads
    blind = decide(rt, "r/weak", "cost_blind", context_tokens=2000, **PAIR)
    # cost_blind: the best bound, 40 of 40, first by ID among its ties
    assert (blind.mode, blind.reason, blind.route.primary) == ("inline", "inline_as_good",
                                                               "r/strong+l/dear")
    assert blind.delegate_quality_lb == blind.parent_quality_lb == wilson_lower_bound(40, 40, 0.95)
    assert blind.delegate_cost_usd == brief + (cost("r/strong", 1300) + cost("l/dear", 1300)) + reads


def test_side_tokens_price_each_side_at_its_mean_with_the_brief_on_the_root_alone():
    rt = router(pair_extra={("r/strong", "l/cheap"): dict(
        root_input_tokens=36_000, root_output_tokens=6_000, leaf_input_tokens=30_000,
        leaf_output_tokens=7_001)})
    before = rt.stats.side_tokens("t", "r/strong+l/cheap")
    d = decide(rt, "r/strong", context_tokens=50_000, **PAIR)
    brief, reads = parent_terms("r/strong")
    # means rounded up over 40 side trials: root 900 + B in and 150 out, leaf 750 in and 176 out
    pair = cost("r/strong", 1200, 150) + cost("l/cheap", 750, 176)
    assert d.route.primary == "r/strong+l/cheap"
    assert next(c.list_cost for c in d.route.candidates if c.model_id == d.model) == pair
    assert d.delegate_cost_usd == brief + pair + reads
    assert rt.stats.side_tokens("t", "r/strong+l/cheap") == before == (36_000, 6_000, 30_000, 7_001, 40)


def test_a_side_is_priced_per_call_whatever_its_items_per_call():
    batch = Model("r/strong@batch", "strong", 10.0, 30.0, 100_000, variant=Variant("batch", items_per_call=2))
    rt = router(pairs={("r/strong@batch", "l/cheap"): 40}, reg=registry(extra=(batch,)), solo=False,
                pair_extra={("r/strong@batch", "l/cheap"): SIDES[("r/strong", "l/cheap")]})
    d = rt.decide_delegation("t", "r/weak", **SIZES, delegate_roots=["r/strong@batch"],
                             delegate_leaves=["l/cheap"])
    brief, reads = parent_terms("r/weak")
    assert d.model == "r/strong@batch+l/cheap"
    assert d.delegate_cost_usd == brief + (cost("r/strong", 1500, 225) + cost("l/cheap", 750, 175)) + reads
    # select_pair itself divides each side by its items_per_call (5.2 v1.671)
    own = rt.select_pair("t", ["r/strong@batch"], ["l/cheap"]).candidates[0].list_cost
    assert own == cost("r/strong", 1200, 225) / 2 + cost("l/cheap", 750, 175)


def test_a_policy_and_an_exclusion_reach_the_pair_and_the_router_is_left_as_it_was(tmp_path):
    rt = router()
    tasks = dict(rt.tasks)
    rt.stats.save(tmp_path / "before.json")
    d = decide(rt, "r/strong", context_tokens=50_000, exclude_models=["l/cheap"], **PAIR)
    assert d.model == "r/strong+l/mid"
    allow = Policy(allowed_routes=("r/good", "l/dear"))
    ruled = decide(rt, "r/weak", context_tokens=2000, policy=allow, **PAIR)
    assert ruled.reason == "parent_policy_excluded" and ruled.model == "r/good+l/dear"
    rt.stats.save(tmp_path / "after.json")
    assert rt.tasks == tasks
    assert (tmp_path / "after.json").read_bytes() == (tmp_path / "before.json").read_bytes()


# --- 7 v1.684: .call_delegated refuses a pair decision -------------------------------------------

def test_call_delegated_refuses_a_pair_decision_before_any_id_call_or_record():
    from model_routing import Executor
    rt = router(solo=False)
    d = decide(rt, "r/weak", **PAIR)
    ids, monitor = [], Monitor()
    provider = FakeProvider({})
    ex = Executor(rt, provider, monitor=monitor, id_factory=lambda: ids.append(1) or "call-0")
    with pytest.raises(ValueError, match="call_pair"):
        ex.call_delegated(d, [{"role": "user", "content": "brief"}])
    with pytest.raises(ValueError, match="call_pair"):
        ex.call_delegated(d, [{"role": "user", "content": "brief"}], tags={"parent": "x"})
    assert ids == [] and monitor.records == []


# --- unchanged: every decision without a pair ----------------------------------------------------

def no_pair_grid():
    out = []
    for solo in (True, False):
        for extra in (None, SIDES):
            rt = router(solo=solo, pair_extra=extra)
            for parent in ROOTS + LEAVES:
                for flavor in ("cost_effective", "cost_blind"):
                    for k in (1, 3):
                        for folded in (True, False):
                            try:
                                out.append(rt.decide_delegation(
                                    "t", parent, flavor, context_tokens=5000, brief_tokens=300,
                                    result_tokens=150, carry_turns=2, work_calls=k,
                                    inline_separate_call=folded).to_dict())
                            except Exception as exc:
                                out.append([type(exc).__name__, str(exc)])
    return out


def test_every_no_pair_decision_on_the_fixture_keeps_its_v1_683_bytes():
    grid = no_pair_grid()
    assert len(grid) == 224
    assert decision_sha256(grid) == NO_PAIR_SHA256


# --- the spec ------------------------------------------------------------------------------------

def test_design_states_the_pair_in_13_1_13_2_13_3_and_7():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    s7 = design[design.index("## 7. "):design.index("## 8. ")]
    s13_1 = design[design.index("### 13.1 Inputs"):design.index("### 13.2 ")]
    s13_2 = design[design.index("### 13.2 "):design.index("### 13.3 ")]
    s13_3 = design[design.index("### 13.3 "):design.index("### 13.4 ")]
    # v1.691 (row DEL3): `depth=None` follows them, tests/test_delegation_depth.py
    assert "policy=None, delegate_roots=None, delegate_leaves=None, depth=None) -> DelegationDecision`" in s13_1
    assert "- `delegate_roots` and `delegate_leaves` (v1.684, row DEL1h, default None):" in s13_1
    assert "- v1.684 a pair delegate (row DEL1h, 13.3 v1.684):" in s13_2
    assert "with B added to the root's input alone" in s13_2
    assert "- v1.684 a pair (row DEL1h, 13.1 v1.684):" in s13_3
    assert "  - Tests (tests/test_delegation_pair.py):" in s13_3
    assert "- v1.684 a pair decision in `.call_delegated` (row DEL1h, 13.3 v1.684):" in s7
