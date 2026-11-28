"""DESIGN 5.1 and 5.2 v1.695 (row CACHE3a, the first part of row CACHE3): a session's warm cache.

A prompt cache holds the prefix one model was sent, so a call moved to another model mid-session
reads its whole context at that model's input price. `.select(..., session_route=R,
session_warm=W)` prices every registry candidate with measured cache counts cold, its mean cached
reads at the input price, except R itself when W is True, labels the decision's
`session_pricing` `warm` or `conservative`, and gives the decision `pick_reason` `stay_warm` when
the warm route is first only because a switch would cost more. Without a `session_route` every
decision keeps its bytes: `V1_694_DIGEST` was computed on the package at 2caa7ee, before v1.695.
"""

import hashlib
import json
import math

import pytest

from model_routing import (
    Model, NoModelClearsBar, Procedure, ProcedureResult, Registry, Router, Stats, Task,
)

WARM, CHEAP, PLAIN = "fiction/warm", "fiction/cheap", "fiction/plain"
# W at 3.0 in, 0.3 cached, 15.0 out; C at 1.0 in, 0.1 cached, 5.0 out (DESIGN 5.2 v1.695)
W_IN, W_CACHED, W_OUT = 3.0, 0.3, 15.0
C_IN, C_CACHED, C_OUT = 1.0, 0.1, 5.0
REGISTRY = Registry([
    Model(WARM, "fam-a", W_IN, W_OUT, 200_000, price_cached_in=W_CACHED),
    Model(CHEAP, "fam-b", C_IN, C_OUT, 200_000, price_cached_in=C_CACHED),
])
NEW, OUT, TRIALS = 1_000, 500, 100
TASK = Task("t", bar=0.7, min_samples=10, independent_of_generator=False,
            expected_input_tokens=10_000, expected_output_tokens=OUT)
# the break-even context length, from the 5.2 v1.695 formula
BREAK_EVEN = (NEW * (W_IN - W_CACHED) + OUT * (W_OUT - C_OUT)) / (C_IN - W_CACHED)


def _stats(context, models=(WARM, CHEAP), successes=95):
    """Each model read ``context`` tokens a call, all but ``NEW`` of them cached, and wrote OUT."""
    stats = Stats()
    for model_id in models:
        stats.add("t", model_id, successes, TRIALS, input_tokens=context * TRIALS,
                  output_tokens=OUT * TRIALS, cached_input_tokens=(context - NEW) * TRIALS)
    return stats


def _router(stats, registry=REGISTRY, task=TASK):
    return Router(registry, {task.name: task}, stats)


def _by_id(decision):
    return {c.model_id: c for c in decision.candidates}


def _cost(price_in, price_cached, price_out, context, cached):
    return ((context - cached) * price_in + cached * price_cached + OUT * price_out) / 1_000_000


# --- the break-even context length --------------------------------------------------------

def test_the_break_even_length_is_eleven_thousand_tokens():
    assert BREAK_EVEN == pytest.approx(11_000, rel=1e-12)
    warm = REGISTRY.get(WARM).cost(11_000, OUT, cached_input_tokens=11_000 - NEW)
    cold = REGISTRY.get(CHEAP).cost(11_000, OUT)
    assert warm == pytest.approx(cold, rel=1e-12)


def test_past_the_break_even_length_the_warm_route_is_kept_with_stay_warm():
    from model_routing.router import STAY_WARM
    assert STAY_WARM == "stay_warm"
    decision = _router(_stats(11_001)).select("t", session_route=WARM, session_warm=True)
    assert decision.primary == WARM
    assert decision.fallbacks == (CHEAP,)
    assert decision.pick_reason == "stay_warm"
    assert decision.session_pricing == "warm"
    by_id = _by_id(decision)
    assert by_id[WARM].list_cost == pytest.approx(_cost(W_IN, W_CACHED, W_OUT, 11_001, 10_001))
    assert by_id[CHEAP].list_cost == pytest.approx(_cost(C_IN, C_CACHED, C_OUT, 11_001, 0))
    assert by_id[WARM].list_cost < by_id[CHEAP].list_cost
    assert by_id[WARM].reason == "passes" and by_id[CHEAP].reason == "passes"


def test_short_of_the_break_even_length_the_cheap_route_wins_the_switch():
    decision = _router(_stats(10_999)).select("t", session_route=WARM, session_warm=True)
    assert decision.primary == CHEAP
    assert decision.pick_reason is None
    assert decision.session_pricing == "warm"
    by_id = _by_id(decision)
    assert by_id[CHEAP].list_cost < by_id[WARM].list_cost


@pytest.mark.parametrize("context", [2_000, 10_999, 11_001, 50_000, 150_000])
def test_without_a_session_the_cheap_route_is_first_at_any_length(context):
    decision = _router(_stats(context)).select("t")
    assert decision.primary == CHEAP
    assert decision.pick_reason is None
    assert decision.session_pricing is None
    assert _by_id(decision)[CHEAP].list_cost == pytest.approx(
        _cost(C_IN, C_CACHED, C_OUT, context, context - NEW))


@pytest.mark.parametrize("context", [11_001, 50_000, 150_000])
def test_every_length_past_the_break_even_keeps_the_warm_route(context):
    decision = _router(_stats(context)).select("t", session_route=WARM, session_warm=True)
    assert (decision.primary, decision.pick_reason) == (WARM, "stay_warm")


# --- the price of a cold route ----------------------------------------------------------

def test_a_cold_route_moves_its_cached_reads_to_the_input_price():
    decision = _router(_stats(20_000)).select("t", session_route=WARM, session_warm=True)
    cheap = _by_id(decision)[CHEAP]
    uncached, read, write, output = cheap.cost_breakdown
    assert read == 0.0 and write == 0.0
    assert uncached == pytest.approx(20_000 * C_IN / 1_000_000)
    assert output == pytest.approx(OUT * C_OUT / 1_000_000)
    assert math.fsum(cheap.cost_breakdown) == pytest.approx(cheap.list_cost, rel=1e-12)
    assert cheap.routing_cost == cheap.list_cost
    warm = _by_id(decision)[WARM]
    assert warm.cost_breakdown[1] == pytest.approx(19_000 * W_CACHED / 1_000_000)


def test_without_session_warm_every_route_is_cold_and_the_estimate_conservative():
    decision = _router(_stats(11_001)).select("t", session_route=WARM)
    assert decision.session_pricing == "conservative"
    assert decision.primary == CHEAP
    assert decision.pick_reason is None
    by_id = _by_id(decision)
    assert by_id[WARM].list_cost == pytest.approx(_cost(W_IN, W_CACHED, W_OUT, 11_001, 0))
    assert by_id[WARM].cost_breakdown[1] == 0.0
    assert by_id[CHEAP].cost_breakdown[1] == 0.0


def test_the_session_route_on_a_warm_call_keeps_its_v1_588_candidate():
    stats = _stats(30_000)
    blind = _by_id(_router(stats).select("t"))
    warm = _by_id(_router(stats).select("t", session_route=WARM, session_warm=True))
    assert warm[WARM] == blind[WARM]
    assert warm[CHEAP] != blind[CHEAP]


def test_a_session_route_that_is_no_candidate_makes_every_route_a_switch():
    decision = _router(_stats(30_000)).select("t", session_route="fiction/gone",
                                                session_warm=True)
    assert decision.session_pricing == "warm"
    assert all(c.cost_breakdown[1] == 0.0 for c in decision.candidates)
    assert decision.primary == CHEAP
    assert decision.pick_reason is None


def test_a_candidate_without_measured_cache_counts_keeps_its_price():
    registry = Registry(list(REGISTRY.models) + [Model(PLAIN, "fam-c", 0.5, 2.0, 200_000)])
    stats = _stats(30_000)
    stats.add("t", PLAIN, 95, TRIALS, input_tokens=30_000 * TRIALS, output_tokens=OUT * TRIALS)
    blind = _by_id(_router(stats, registry).select("t"))
    session = _by_id(_router(stats, registry).select("t", session_route=WARM,
                                                       session_warm=True))
    assert session[PLAIN] == blind[PLAIN]
    assert session[PLAIN].cost_breakdown is None


def test_a_cold_route_without_a_cached_price_names_no_unknown_cache_price():
    registry = Registry([REGISTRY.get(WARM), Model(PLAIN, "fam-c", 1.0, 5.0, 200_000)])
    stats = _stats(30_000, models=(WARM, PLAIN))
    blind = _by_id(_router(stats, registry).select("t"))
    assert blind[PLAIN].cache_price_unknown == ("price_cached_in",)
    session = _by_id(_router(stats, registry).select("t", session_route=WARM,
                                                       session_warm=True))
    assert session[PLAIN].cache_price_unknown == ()
    assert session[PLAIN].list_cost == pytest.approx(blind[PLAIN].list_cost)


def test_a_cold_route_keeps_its_measured_cache_writes():
    registry = Registry([REGISTRY.get(WARM),
                         Model(PLAIN, "fam-c", 1.0, 5.0, 200_000, price_cached_in=0.1,
                               price_cache_write=1.25)])
    stats = _stats(30_000, models=(WARM,))
    stats.add("t", PLAIN, 95, TRIALS, input_tokens=30_000 * TRIALS, output_tokens=OUT * TRIALS,
              cached_input_tokens=20_000 * TRIALS, cache_write_tokens=4_000 * TRIALS)
    session = _by_id(_router(stats, registry).select("t", session_route=WARM,
                                                       session_warm=True))
    uncached, read, write, _ = session[PLAIN].cost_breakdown
    assert read == 0.0
    assert write == pytest.approx(4_000 * 1.25 / 1_000_000)
    assert uncached == pytest.approx(26_000 * 1.0 / 1_000_000)
    assert session[PLAIN].list_cost == registry.get(PLAIN).cost(
        30_000, OUT, cached_input_tokens=0, cache_write_tokens=4_000)


def test_cost_blind_never_stays_warm_and_still_prices_the_switch():
    decision = _router(_stats(50_000)).select("t", "cost_blind", session_route=WARM,
                                                session_warm=True)
    assert decision.pick_reason is None
    assert decision.session_pricing == "warm"
    assert all(c.routing_cost == 0.0 for c in decision.candidates)
    assert _by_id(decision)[CHEAP].cost_breakdown[1] == 0.0
    assert decision.primary == min((WARM, CHEAP))


def test_stay_warm_replaces_cheaper_per_success_under_retry_same():
    task = Task("t", bar=0.7, min_samples=10, independent_of_generator=False,
                expected_input_tokens=10_000, expected_output_tokens=OUT,
                failure_policy="retry_same")
    decision = _router(_stats(50_000), task=task).select("t", session_route=WARM,
                                                         session_warm=True)
    assert decision.primary == WARM
    assert decision.pick_reason == "stay_warm"


def test_a_warm_route_first_at_its_own_price_is_no_stay_warm():
    # at v1.588 prices the cheap model is first, so with the cheap one as the session route
    # nothing is kept that a session-blind decision would not pick
    decision = _router(_stats(50_000)).select("t", session_route=CHEAP, session_warm=True)
    assert decision.primary == CHEAP
    assert decision.pick_reason is None


def test_a_pinned_call_holds_the_candidates_priced_for_the_session():
    decision = _router(_stats(50_000)).select("t", pin_route=CHEAP, session_route=WARM,
                                                session_warm=True)
    assert decision.basis == "pinned" and decision.primary == CHEAP
    assert decision.session_pricing == "warm"
    assert decision.pick_reason is None
    assert _by_id(decision)[CHEAP].cost_breakdown[1] == 0.0


def test_a_refusal_holds_the_candidates_priced_for_the_session():
    task = Task("t", bar=0.99, min_samples=10, independent_of_generator=False,
                expected_input_tokens=10_000, expected_output_tokens=OUT, on_no_model="refuse")
    with pytest.raises(NoModelClearsBar) as caught:
        _router(_stats(50_000), task=task).select("t", session_route=WARM, session_warm=True)
    by_id = {c.model_id: c for c in caught.value.candidates}
    assert by_id[CHEAP].cost_breakdown[1] == 0.0
    assert by_id[WARM].cost_breakdown[1] > 0.0


# --- checks ------------------------------------------------------------------------------

@pytest.mark.parametrize("route", ["", 3, b"fiction/warm", ("fiction/warm",)])
def test_a_session_route_must_be_a_non_empty_str(route):
    with pytest.raises(ValueError, match="session_route"):
        _router(_stats(30_000)).select("t", session_route=route)


@pytest.mark.parametrize("warm", [1, 0, "yes", None])
def test_session_warm_must_be_a_bool(warm):
    with pytest.raises(ValueError, match="session_warm"):
        _router(_stats(30_000)).select("t", session_route=WARM, session_warm=warm)


def test_session_warm_needs_a_session_route():
    with pytest.raises(ValueError, match="session_warm"):
        _router(_stats(30_000)).select("t", session_warm=True)


def test_a_session_with_cascades_or_procedures_is_refused():
    def fn(item, handle):
        return ProcedureResult("done", tool_calls=0)
    proc = Procedure("p", "1", fn, max_model_calls=0, max_tool_calls=0)
    with pytest.raises(ValueError, match="cascades"):
        _router(_stats(30_000)).select("t", cascades=True, session_route=WARM)
    with pytest.raises(ValueError, match="procedures"):
        _router(_stats(30_000)).select("t", procedures=[proc], session_route=WARM)


def test_the_checks_come_before_the_task_lookup():
    with pytest.raises(ValueError, match="session_route"):
        _router(_stats(30_000)).select("no-such-task", session_route="")


# --- to_dict -----------------------------------------------------------------------------

def test_to_dict_writes_pick_reason_after_basis_and_session_pricing_before_candidates():
    data = _router(_stats(50_000)).select("t", session_route=WARM, session_warm=True).to_dict()
    assert list(data) == ["task", "flavor", "primary", "fallbacks", "below_bar", "basis",
                          "pick_reason", "session_pricing", "candidates"]
    assert data["pick_reason"] == "stay_warm" and data["session_pricing"] == "warm"


def test_to_dict_of_a_conservative_decision_has_no_pick_reason():
    data = _router(_stats(50_000)).select("t", session_route=WARM).to_dict()
    assert list(data) == ["task", "flavor", "primary", "fallbacks", "below_bar", "basis",
                          "session_pricing", "candidates"]
    assert data["session_pricing"] == "conservative"


def test_to_dict_under_retry_same_keeps_pick_reason_in_its_v1_567_place():
    task = Task("t", bar=0.7, min_samples=10, independent_of_generator=False,
                expected_input_tokens=10_000, expected_output_tokens=OUT,
                failure_policy="retry_same", max_p95_ms=1_000.0)
    data = _router(_stats(50_000), task=task).select("t", session_route=WARM,
                                                     session_warm=True).to_dict()
    assert list(data)[:11] == ["task", "flavor", "primary", "fallbacks", "below_bar", "basis",
                               "failure_policy", "expected_cost_per_success_usd", "pick_reason",
                               "max_p95_ms", "session_pricing"]


# --- unchanged without a session -----------------------------------------------------------

def _guard_decisions():
    """Decisions without a session, as JSON text, over the fixtures of this module."""
    out = []
    retry = Task("t", bar=0.7, min_samples=10, independent_of_generator=False,
                 expected_input_tokens=10_000, expected_output_tokens=OUT,
                 failure_policy="retry_same")
    writer = Registry([REGISTRY.get(WARM),
                       Model(PLAIN, "fam-c", 1.0, 5.0, 200_000, price_cache_write=1.25)])
    for context in (2_000, 10_999, 11_000, 11_001, 50_000):
        stats = _stats(context)
        for flavor in ("cost_effective", "cost_blind"):
            out.append(_router(stats).select("t", flavor).to_dict())
            out.append(_router(stats, task=retry).select("t", flavor).to_dict())
        wstats = _stats(context, models=(WARM,))
        wstats.add("t", PLAIN, 90, TRIALS, input_tokens=context * TRIALS,
                   output_tokens=OUT * TRIALS, cache_write_tokens=(context // 2) * TRIALS)
        out.append(_router(wstats, writer).select("t").to_dict())
        out.append(_router(stats).select("t", pin_route=WARM).to_dict())
    return json.dumps(out, sort_keys=False, separators=(",", ":"))


# sha256 of _guard_decisions() on the package at 2caa7ee (v1.694)
V1_694_DIGEST = "487eb2c1bbff707f6700f33ad1f6ab9cc4cc136bb0261be9e6ccf0601cd5d996"


def test_decisions_without_a_session_keep_their_v1_694_bytes():
    assert hashlib.sha256(_guard_decisions().encode()).hexdigest() == V1_694_DIGEST


def test_the_default_keywords_give_the_decision_without_them():
    stats = _stats(50_000)
    plain = _router(stats).select("t")
    stated = _router(stats).select("t", session_route=None, session_warm=False)
    assert stated == plain
    assert json.dumps(stated.to_dict()) == json.dumps(plain.to_dict())
    assert "session_pricing" not in plain.to_dict()
    assert plain.session_pricing is None
