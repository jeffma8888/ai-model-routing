"""DESIGN 5.2 v1.700 (row CACHE3c): a session with cascades and procedures.

To v1.699 `select` refused a `session_route` with `cascades=True` or any `procedures`. From v1.700
a cascade's legs and an unmeasured procedure's one call of its model are priced cold under a
session as a registry candidate is (5.2 v1.695): each leg's measured cached reads, after the
v1.591 fit, at its model's input price and its writes kept, except a leg whose model is the warm
session route. A cascade whose cheap leg is the warm route stays warm for `stay_warm`; one whose
strong leg alone is warm is a switch, and a procedure never gets it. A measured procedure keeps
its mean cost per trial. Without a `session_route` every decision with cascades and procedures
keeps its bytes: `V1_699_DIGEST` was computed on the package at 3682050, before v1.700.
"""

import json

import pytest

from decision_hash import decision_sha256
from model_routing import (Cascade, Model, NoModelClearsBar, Procedure, ProcedureResult,
                           Registry, Router, Stats, Task)

CHEAP, STRONG, OTHER = "fiction/cheap", "fiction/strong", "fiction/other"
# the 5.2 v1.700 example: cheap at 1.0 in, 0.1 cached, 1.25 written and 4.0 out, strong at 3.0
# in, 0.3 cached, 3.75 written and 15.0 out; other at 1.5 in, 0.15 cached and 2.0 out
REGISTRY = Registry([
    Model(CHEAP, "fam-b", 1.0, 4.0, 200_000, price_cached_in=0.1, price_cache_write=1.25),
    Model(STRONG, "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3, price_cache_write=3.75),
])
WITH_OTHER = Registry(list(REGISTRY.models)
                      + [Model(OTHER, "fam-c", 1.5, 2.0, 200_000, price_cached_in=0.15)])
CASCADE = Cascade(CHEAP, STRONG, "sig")
CID = CASCADE.id
CACHED = {"cached_input_tokens": 900_000}  # 9,000 of each call's 10,000 input tokens


def _one_call(value, call):
    return ProcedureResult(call([{"role": "user", "content": str(value)}]))


def _noop(value, call):
    return ProcedureResult("done", tool_calls=1)


ON_CHEAP = Procedure("poll", "v1", _one_call, max_model_calls=1, max_tool_calls=5, model=CHEAP)
MEASURED = Procedure("poll", "v2", _one_call, max_model_calls=1, max_tool_calls=5, model=CHEAP)
BARE = Procedure("tool", "v1", _noop, max_model_calls=0, max_tool_calls=5)


def _task(**fields):
    values = dict(bar=0.7, min_samples=10, independent_of_generator=False,
                  expected_input_tokens=10_000, expected_output_tokens=500, cascades=(CASCADE,))
    values.update(fields)
    return Task("t", **values)


def _stats(cheap=CACHED, strong=CACHED, other=None, cheap_successes=95, escalated=20):
    """Each model at 10,000 in and 500 out a call over 100 trials with the cache kwargs given,
    the cascade at 90 of 100 with ``escalated`` hand-ups."""
    stats = Stats()
    for model_id, cache, successes in ((CHEAP, cheap, cheap_successes), (STRONG, strong, 95),
                                       (OTHER, other, 95)):
        if model_id == OTHER and other is None:
            continue
        stats.add("t", model_id, successes, 100, input_tokens=1_000_000, output_tokens=50_000,
                  **(cache or {}))
    stats.add("t", CID, 90, 100, escalated=escalated)
    return stats


def _select(stats, registry=REGISTRY, task=None, **kw):
    task = _task() if task is None else task
    return Router(registry, {task.name: task}, stats).select(task.name, **kw)


def _by_id(decision):
    return {c.model_id: c for c in decision.candidates}


# --- the old refusal is gone ----------------------------------------------------------------

def test_a_session_with_cascades_is_priced_not_refused():
    decision = _select(_stats(), cascades=True, session_route=CHEAP, session_warm=True)
    assert decision.session_pricing == "warm" and CID in _by_id(decision)


def test_a_session_with_procedures_is_priced_not_refused():
    decision = _select(_stats(), procedures=[ON_CHEAP, BARE], session_route=CHEAP)
    assert decision.session_pricing == "conservative" and ON_CHEAP.id in _by_id(decision)


# --- a cascade's legs, by hand ----------------------------------------------------------------

@pytest.mark.parametrize("session, expected", [
    # v1.591: 0.0039 + 0.2 * 0.0147 (the hand-up read of 10,500, 9,000 of it cached)
    ({}, 0.00684),
    # warm on cheap: the cheap leg keeps 0.0039, the strong leg reads 10,500 uncached, 0.039
    ({"session_route": CHEAP, "session_warm": True}, 0.0117),
    # warm on strong: the cheap leg reads 10,000 uncached, 0.012, the strong leg keeps 0.0147
    ({"session_route": STRONG, "session_warm": True}, 0.01494),
    # conservative, and a warm route that is neither leg: both legs cold, 0.012 + 0.2 * 0.039
    ({"session_route": CHEAP}, 0.0198),
    ({"session_route": STRONG}, 0.0198),
    ({"session_route": "fiction/elsewhere", "session_warm": True}, 0.0198),
])
def test_a_cascades_price_under_a_session_is_the_hand_computed_one(session, expected):
    candidate = _by_id(_select(_stats(), cascades=True, **session))[CID]
    assert candidate.list_cost == pytest.approx(expected, abs=1e-12)
    assert candidate.routing_cost == candidate.list_cost


def test_cost_blind_prices_the_cold_legs_at_a_routing_cost_of_zero():
    candidate = _by_id(_select(_stats(), "cost_blind", cascades=True,
                               session_route=CHEAP, session_warm=True))[CID]
    assert candidate.list_cost == pytest.approx(0.0117, abs=1e-12)
    assert candidate.routing_cost == 0.0


def test_the_cold_strong_legs_breakdown_has_no_cached_part():
    candidate = _by_id(_select(_stats(), cascades=True, session_route=CHEAP,
                               session_warm=True))[CID]
    # uncached 1,000 * 1.0 + 0.2 * 10,500 * 3.0; cached 9,000 * 0.1; no write; output
    # 500 * 4.0 + 0.2 * 500 * 15.0, each per million
    assert candidate.cost_breakdown == pytest.approx((0.0073, 0.0009, 0.0, 0.0035), abs=1e-15)
    assert candidate.cache_price_unknown == ()


def test_a_cold_leg_keeps_its_measured_cache_writes():
    # cheap reads 8,000 cached and writes 1,000 a call; cold, it pays 9,000 at 1.0 and the write
    # at 1.25: (9,000 + 1,250 + 2,000) / 1e6 = 0.01225, plus 0.2 * 0.039 for the strong leg
    stats = _stats(cheap={"cached_input_tokens": 800_000, "cache_write_tokens": 100_000},
                   strong=None)
    candidate = _by_id(_select(stats, cascades=True, session_route=STRONG))[CID]
    assert candidate.list_cost == pytest.approx(0.02005, abs=1e-12)
    assert candidate.cost_breakdown == pytest.approx(
        (0.009 + 0.2 * 0.0315, 0.0, 0.00125, 0.002 + 0.2 * 0.0075), abs=1e-15)


def test_a_cold_leg_without_cache_prices_names_the_write_price_alone():
    bare = Registry([Model(CHEAP, "fam-b", 1.0, 4.0, 200_000), REGISTRY.get(STRONG)])
    stats = _stats(cheap={"cached_input_tokens": 800_000, "cache_write_tokens": 100_000},
                   strong=None)
    warm = _by_id(_select(stats, bare, cascades=True))[CID]
    cold = _by_id(_select(stats, bare, cascades=True, session_route=STRONG))[CID]
    assert warm.cache_price_unknown == ("price_cached_in", "price_cache_write")
    assert cold.cache_price_unknown == ("price_cache_write",)


def test_a_leg_without_measured_cache_counts_keeps_its_price():
    plain = _by_id(_select(_stats(cheap=None, strong=None), cascades=True))[CID]
    cold = _by_id(_select(_stats(cheap=None, strong=None), cascades=True,
                          session_route=CHEAP))[CID]
    assert plain.list_cost == cold.list_cost == pytest.approx(0.0198, abs=1e-12)
    assert plain.cost_breakdown is None and cold.cost_breakdown is None


# --- a procedure's model ------------------------------------------------------------------------

@pytest.mark.parametrize("session, expected", [
    ({}, 0.0039),  # one call of cheap at the task's 10,000 in and 500 out, 9,000 cached
    ({"session_route": CHEAP, "session_warm": True}, 0.0039),
    ({"session_route": CHEAP}, 0.012),
    ({"session_route": STRONG, "session_warm": True}, 0.012),
])
def test_an_unmeasured_procedures_call_is_priced_cold_unless_its_model_is_warm(session, expected):
    candidate = _by_id(_select(_stats(), procedures=[ON_CHEAP], **session))[ON_CHEAP.id]
    assert candidate.list_cost == pytest.approx(expected, abs=1e-12)


def test_a_cold_procedure_call_has_the_cold_breakdown():
    candidate = _by_id(_select(_stats(), procedures=[ON_CHEAP], session_route=STRONG))[ON_CHEAP.id]
    assert candidate.cost_breakdown == pytest.approx((0.01, 0.0, 0.0, 0.002), abs=1e-15)


@pytest.mark.parametrize("session", [{}, {"session_route": CHEAP},
                                     {"session_route": STRONG, "session_warm": True}])
def test_a_measured_procedure_and_one_without_a_model_keep_their_cost(session):
    stats = _stats()
    stats.add("t", MEASURED.id, 95, 100, cost_usd=0.5)
    by_id = _by_id(_select(stats, procedures=[MEASURED, BARE], **session))
    assert by_id[MEASURED.id].list_cost == 0.005 and by_id[MEASURED.id].cost_breakdown is None
    assert by_id[BARE.id].list_cost == 0.0


# --- stay_warm ----------------------------------------------------------------------------------

def _stay_stats():
    """Cheap fails the bar alone (60 of 100), so the cascade, other and strong are the passing
    routes; other is first at v1.591 prices, 0.00385 against the cascade's 0.00684, and cold it
    costs (10,000 * 1.5 + 500 * 2.0) / 1e6 = 0.016."""
    return _stats(other=CACHED, cheap_successes=60)


def test_a_cascade_whose_cheap_leg_is_warm_stays_warm():
    blind = _select(_stay_stats(), WITH_OTHER, cascades=True)
    assert blind.primary == OTHER and _by_id(blind)[OTHER].list_cost == pytest.approx(0.00385)
    decision = _select(_stay_stats(), WITH_OTHER, cascades=True, session_route=CHEAP,
                       session_warm=True)
    by_id = _by_id(decision)
    assert by_id[CID].list_cost == pytest.approx(0.0117, abs=1e-12)
    assert by_id[OTHER].list_cost == pytest.approx(0.016, abs=1e-12)
    assert decision.primary == CID and decision.pick_reason == "stay_warm"


def test_a_cascade_whose_strong_leg_alone_is_warm_is_a_switch():
    decision = _select(_stay_stats(), WITH_OTHER, cascades=True, session_route=STRONG,
                       session_warm=True)
    assert _by_id(decision)[CID].list_cost == pytest.approx(0.01494, abs=1e-12)
    assert decision.primary == CID and decision.pick_reason is None


def test_a_conservative_session_on_the_cheap_leg_moves_off_the_cascade():
    decision = _select(_stay_stats(), WITH_OTHER, cascades=True, session_route=CHEAP)
    assert decision.primary == OTHER and decision.pick_reason is None


def test_a_procedure_on_the_warm_model_never_stays_warm():
    # measured at 95 of 100 with no cost, it is priced at one warm call of cheap, 0.0039: second
    # to other's 0.00385 at v1.591 prices and first under the session, with no stay_warm
    stats = _stay_stats()
    stats.add("t", ON_CHEAP.id, 95, 100)
    blind = _select(stats, WITH_OTHER, procedures=[ON_CHEAP])
    assert blind.primary == OTHER
    decision = _select(stats, WITH_OTHER, procedures=[ON_CHEAP], session_route=CHEAP,
                       session_warm=True)
    assert _by_id(decision)[ON_CHEAP.id].list_cost == pytest.approx(0.0039, abs=1e-12)
    assert decision.primary == ON_CHEAP.id and decision.pick_reason is None


def test_a_pin_on_the_cascade_holds_its_session_price_and_no_stay_warm():
    decision = _select(_stay_stats(), WITH_OTHER, cascades=True, pin_route=CID,
                       session_route=CHEAP, session_warm=True)
    assert decision.primary == CID and decision.basis == "pinned"
    assert _by_id(decision)[CID].list_cost == pytest.approx(0.0117, abs=1e-12)
    assert decision.pick_reason is None and decision.session_pricing == "warm"


def test_a_refusal_holds_the_cascade_priced_for_the_session():
    task = _task(bar=0.99, on_no_model="refuse")
    with pytest.raises(NoModelClearsBar) as caught:
        _select(_stats(), task=task, cascades=True, session_route=CHEAP)
    cascade = {c.model_id: c for c in caught.value.candidates}[CID]
    assert cascade.list_cost == pytest.approx(0.0198, abs=1e-12)
    assert cascade.cost_breakdown[1] == 0.0


# --- a session route that names a cascade or a procedure ------------------------------------------

def test_a_session_route_that_is_a_routed_cascades_id_is_refused():
    with pytest.raises(ValueError, match="session_route .* is the id of a cascade or procedure"):
        _select(_stats(), cascades=True, session_route=CID)


def test_a_session_route_that_is_a_procedures_id_is_refused():
    with pytest.raises(ValueError, match="session_route .* is the id of a cascade or procedure"):
        _select(_stats(), procedures=[ON_CHEAP], session_route=ON_CHEAP.id)


def test_a_cascades_id_is_a_plain_switch_when_the_cascade_is_not_routed():
    decision = _select(_stats(), session_route=CID, session_warm=True)
    assert decision.session_pricing == "warm" and CID not in _by_id(decision)


# --- unchanged without a session --------------------------------------------------------------------

def _guard_decisions():
    """Decisions with cascades and procedures and without a session, over this module's fixtures."""
    out = []
    bare = Registry([Model(CHEAP, "fam-b", 1.0, 4.0, 200_000), REGISTRY.get(STRONG)])
    writes = {"cached_input_tokens": 800_000, "cache_write_tokens": 100_000}
    for cheap, strong, other in ((CACHED, CACHED, None), (None, None, None), (writes, None, None),
                                 (None, CACHED, None), (CACHED, CACHED, CACHED)):
        for successes in (95, 60):
            stats = _stats(cheap, strong, other, cheap_successes=successes)
            stats.add("t", MEASURED.id, 95, 100, cost_usd=0.5)
            registry = REGISTRY if other is None else WITH_OTHER
            for flavor in ("cost_effective", "cost_blind"):
                out.append(_select(stats, registry, flavor=flavor, cascades=True,
                                   procedures=[ON_CHEAP, MEASURED, BARE]).to_dict())
                out.append(_select(stats, bare, flavor=flavor, cascades=True).to_dict())
            out.append(_select(stats, registry, cascades=True, pin_route=CID).to_dict())
            out.append(_select(stats, registry, procedures=[ON_CHEAP], pin_route=ON_CHEAP.id,
                               allow_below_bar=True).to_dict())
    return out


# decision_sha256 of _guard_decisions(), keys in order, on the package at 3682050 (v1.699)
V1_699_DIGEST = "2ed81ef227c4701e1bfe94c607052449312be77d8b7701e7ff399d66e191fb00"


def test_decisions_with_cascades_and_procedures_and_no_session_keep_their_v1_699_bytes():
    assert decision_sha256(_guard_decisions(), sort_keys=False) == V1_699_DIGEST


def test_the_guard_holds_cascades_procedures_and_pins():
    data = _guard_decisions()
    assert len(data) == 60
    ids = {c["model_id"] for d in data for c in d["candidates"]}
    assert {CID, ON_CHEAP.id, MEASURED.id, BARE.id, OTHER} <= ids
    assert {d["basis"] for d in data} == {"measured", "pinned"}
    assert "session_pricing" not in json.dumps(data)
