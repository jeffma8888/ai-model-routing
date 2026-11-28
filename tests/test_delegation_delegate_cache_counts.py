"""DESIGN 13.2, 13.3 and 13.6 v1.707 (row CACHE4b): the delegate's measured cache counts.

On a delegate without ``price_tiers`` whose own key on the task holds measured cache counts, each
of its K work calls holds its rounded-down mean cached reads and writes (5.2 v1.588), fitted inside
its mean input without the brief, which is new input, so its work term is ``D.cost(Y, K * S_out,
cached_input_tokens=K * M_r, cache_write_tokens=K * M_w)``, Y the v1.38 first argument, in
``delegate_cost_usd`` and in the delegate's ``select`` alike, and
``DelegationDecision.delegate_cache_counts`` states the counts used. A pair's sides read none (row
DEL1k), and with no count on a delegate's own key, or a tiered delegate, every decision is v1.706's.
Committed ahead of the code (v1.707 red commit): the tests of the new costs and field fail on v1.706,
and the guards of what stays pass before and after it.
"""

import dataclasses

import pytest

from model_routing import DelegationDecision, Model, PriceTier, Registry, Router, Stats, Task
from model_routing.delegation import DELEGATE_CHEAPER

PARENT, CHEAP, CACHED, TIERED = "fiction/parent", "fiction/cheap", "fiction/cached", "fiction/tiered"
ROOT, LEAF = "fiction/root", "fiction/leaf"
# CACHED has the 4.1 v1.587 worked prices: 3.0 in, 0.3 cached, 3.75 written, 15.0 out; CHEAP is
# cheaper per token and states no cache price
PRICES = {PARENT: (3.0, 15.0), CHEAP: (2.0, 10.0), CACHED: (3.0, 15.0), TIERED: (3.0, 15.0)}
CACHE_PRICES = dict(price_cached_in=0.3, price_cache_write=3.75)
REGISTRY = Registry([
    Model(PARENT, "fam-a", 3.0, 15.0, 200_000),
    Model(CHEAP, "fam-b", 2.0, 10.0, 200_000),
    Model(CACHED, "fam-c", 3.0, 15.0, 200_000, **CACHE_PRICES),
    Model(TIERED, "fam-d", 3.0, 15.0, 400_000, price_tiers=(PriceTier(100_000, 6.0, 22.5),)),
    Model(ROOT, "fam-e", 3.0, 15.0, 200_000, **CACHE_PRICES),
    Model(LEAF, "fam-f", 3.0, 15.0, 200_000, **CACHE_PRICES),
])
TASK = Task("t", bar=0.7, min_samples=10, independent_of_generator=False,
            expected_input_tokens=10_000, expected_output_tokens=500)
OTHER = Task("u", bar=0.7, min_samples=10, independent_of_generator=False,
             expected_input_tokens=10_000, expected_output_tokens=500)
C, B, R = 50_000, 400, 60
N = 20  # trials per key
READS_90 = {"cached_input_tokens": 9_000 * N, "cached_trials": N}
WRITES_90 = {"cache_write_tokens": 9_000 * N, "cache_write_trials": N}


def _stats(cache=None, other=None, model=CACHED, parent_cache=None):
    """Every model at N of N on the task with 10,000 and 500 mean tokens; ``cache`` on ``model``'s key."""
    stats = Stats()
    for model_id in (PARENT, CHEAP, CACHED, TIERED):
        extra = cache if model_id == model else parent_cache if model_id == PARENT else None
        stats.add("t", model_id, N, N, input_tokens=10_000 * N, output_tokens=500 * N, **(extra or {}))
    if other is not None:
        stats.add("u", model, N, N, input_tokens=10_000 * N, output_tokens=500 * N, **other)
    return stats


def _decide(stats, exclude=(PARENT, TIERED), **kw):
    router = Router(REGISTRY, {"t": TASK, "u": OTHER}, stats)
    return router.decide_delegation("t", PARENT, context_tokens=C, brief_tokens=B, result_tokens=R,
                                    exclude_models=exclude, **kw)


def _cost(model_id, inp, out, cached=0.0, write=0.0):
    """A call by hand: CACHED's cache prices, every other model's input price on its counts."""
    price_in, price_out = PRICES[model_id]
    read, written = (0.3, 3.75) if model_id == CACHED else (price_in, price_in)
    return ((inp - cached - write) * price_in + cached * read + write * written + out * price_out) / 1_000_000


PARENT_TERMS = _cost(PARENT, 0, B) + _cost(PARENT, B + R, 0)  # the brief written, then B + R re-read


def _candidate(decision, model_id):
    return next(c for c in decision.route.candidates if c.model_id == model_id)


# --- the new costs (fail on v1.706) ----------------------------------------------------------

def test_a_delegate_that_writes_its_cache_on_one_shot_work_pays_the_premium():
    alone = (PARENT, CHEAP, TIERED)
    plain, written = _decide(_stats(), exclude=alone), _decide(_stats(WRITES_90), exclude=alone)
    assert plain.model == written.model == CACHED
    assert plain.delegate_cost_usd == pytest.approx(PARENT_TERMS + _cost(CACHED, B + 10_000, 500), rel=1e-12)
    assert written.delegate_cost_usd == pytest.approx(
        PARENT_TERMS + _cost(CACHED, B + 10_000, 500, write=9_000), rel=1e-12)
    assert written.delegate_cost_usd - plain.delegate_cost_usd == pytest.approx(9_000 * 0.75 / 1e6, rel=1e-9)
    assert written.delegate_cache_counts == (0, 9_000)
    assert _candidate(written, CACHED).list_cost == pytest.approx(_cost(CACHED, B + 10_000, 500, write=9_000),
                                                                 rel=1e-12)


def test_a_delegate_whose_reads_are_cached_outranks_a_cheaper_uncached_one():
    plain, cached = _decide(_stats()), _decide(_stats(READS_90))
    assert (plain.mode, plain.model, plain.reason) == ("delegate", CHEAP, DELEGATE_CHEAPER)
    assert (cached.mode, cached.model, cached.reason) == ("delegate", CACHED, DELEGATE_CHEAPER)
    assert plain.delegate_cost_usd == pytest.approx(PARENT_TERMS + _cost(CHEAP, B + 10_000, 500), rel=1e-12)
    assert cached.delegate_cost_usd == pytest.approx(
        PARENT_TERMS + _cost(CACHED, B + 10_000, 500, cached=9_000), rel=1e-12)
    assert cached.delegate_cost_usd < plain.delegate_cost_usd
    assert getattr(plain, "delegate_cache_counts", None) is None
    assert cached.delegate_cache_counts == (9_000, 0)
    assert _candidate(cached, CACHED).list_cost < _candidate(cached, CHEAP).list_cost < _candidate(plain, CACHED).list_cost


@pytest.mark.parametrize("separate", [True, False])
def test_k_3_holds_the_counts_in_each_of_the_delegates_three_work_calls(separate):
    plain = _decide(_stats(), work_calls=3, inline_separate_call=separate)
    cached = _decide(_stats(READS_90), work_calls=3, inline_separate_call=separate)
    w_in, w_out = 6, 3
    total_in = 3 * B + w_in * 10_000 + w_out * 500
    assert plain.model == CHEAP and cached.model == CACHED
    assert plain.delegate_cost_usd == pytest.approx(PARENT_TERMS + _cost(CHEAP, total_in, 1_500), rel=1e-12)
    assert cached.delegate_cost_usd == pytest.approx(
        PARENT_TERMS + _cost(CACHED, total_in, 1_500, cached=3 * 9_000), rel=1e-12)
    assert cached.delegate_cache_counts == (9_000, 0)


@pytest.mark.parametrize("work_calls", [1, 3])
def test_each_candidates_list_cost_is_the_delegates_work_term_bit_for_bit(work_calls):
    d = _decide(_stats(READS_90), work_calls=work_calls)
    parent = REGISTRY.get(PARENT)
    term = _candidate(d, CACHED).list_cost
    assert d.delegate_cost_usd == parent.base_cost(0, B) + term + 1 * parent.base_cost(B + R, 0)
    k = work_calls
    total_in = k * B + k * (k + 1) // 2 * 10_000 + k * (k - 1) // 2 * 500
    assert term == pytest.approx(_cost(CACHED, total_in, k * 500, cached=k * 9_000), rel=1e-12)


def test_both_flavors_report_the_counted_delegate_cost():
    # cost_blind ranks by bound, then ID, so CACHED leads with and without counts, and the parent's
    # equal bound keeps the work inline: the delegate's cost is reported all the same
    plain, cached = _decide(_stats(), flavor="cost_blind"), _decide(_stats(READS_90), flavor="cost_blind")
    assert plain.route.primary == cached.route.primary == CACHED
    assert cached.delegate_cost_usd == pytest.approx(
        PARENT_TERMS + _cost(CACHED, B + 10_000, 500, cached=9_000), rel=1e-12)
    assert cached.delegate_cost_usd < plain.delegate_cost_usd
    assert cached.delegate_cache_counts == (9_000, 0)


def test_the_counts_are_fitted_inside_the_mean_input_without_the_brief():
    # reads reported on half the trials: a mean of 10,300 per reporting call, over the 10,000 mean
    # input but under it plus B, so it is fitted to 10,000 and B stays new input
    over = {"cached_input_tokens": 10_300 * (N // 2), "cached_trials": N // 2}
    d = _decide(_stats(over))
    assert d.delegate_cache_counts == (10_000, 0)
    assert _candidate(d, CACHED).list_cost == pytest.approx(_cost(CACHED, B + 10_000, 500, cached=10_000),
                                                           rel=1e-12)


def test_the_field_is_last_defaults_to_none_and_its_key_is_last_only_when_set():
    last = dataclasses.fields(DelegationDecision)[-1]
    assert (last.name, last.default) == ("delegate_cache_counts", None)
    d = _decide(_stats(READS_90, parent_cache=READS_90), depth=1)
    data = d.to_dict()
    assert list(data)[-3:] == ["depth", "inline_cache_counts", "delegate_cache_counts"]
    assert data["delegate_cache_counts"] == [9_000, 0]
    assert d.delegate_cache_counts == (9_000, 0)


# --- what stays (pass before and after v1.707) -----------------------------------------------

def _same(a, b):
    assert a.to_dict() == b.to_dict()
    assert getattr(a, "delegate_cache_counts", None) is None and getattr(b, "delegate_cache_counts", None) is None


def test_no_count_keeps_the_decision_and_adds_no_key():
    d = _decide(_stats())
    assert "delegate_cache_counts" not in d.to_dict()
    assert getattr(d, "delegate_cache_counts", None) is None


@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
@pytest.mark.parametrize("work_calls", [1, 3])
def test_a_count_on_another_task_never_leaks(flavor, work_calls):
    _same(_decide(_stats(), flavor=flavor, work_calls=work_calls),
          _decide(_stats(other=READS_90), flavor=flavor, work_calls=work_calls))


@pytest.mark.parametrize("work_calls", [1, 3])
def test_a_tiered_delegate_reads_no_count(work_calls):
    alone = (PARENT, CHEAP, CACHED)
    plain = _decide(_stats(), exclude=alone, work_calls=work_calls)
    counted = _decide(_stats(READS_90, model=TIERED), exclude=alone, work_calls=work_calls)
    assert plain.model == TIERED
    _same(plain, counted)


def _pair_stats(cache=None):
    stats = Stats()
    stats.add("t", PARENT, N, N, input_tokens=10_000 * N, output_tokens=500 * N)
    stats.add("t", f"{ROOT}+{LEAF}", N, N)
    for model_id in (ROOT, LEAF):
        stats.add("t", model_id, N, N, input_tokens=10_000 * N, output_tokens=500 * N, **(cache or {}))
    return stats


@pytest.mark.parametrize("work_calls", [1, 3])
def test_a_pairs_sides_read_no_count(work_calls):
    def decide(stats):
        router = Router(REGISTRY, {"t": TASK}, stats)
        return router.decide_delegation("t", PARENT, context_tokens=C, brief_tokens=B, result_tokens=R,
                                        work_calls=work_calls, delegate_roots=[ROOT], delegate_leaves=[LEAF])
    plain, counted = decide(_pair_stats()), decide(_pair_stats(READS_90))
    assert plain.model == f"{ROOT}+{LEAF}"
    _same(plain, counted)


def test_the_router_stats_are_left_as_they_were():
    stats = _stats(READS_90)
    before = (stats.tokens("t", CACHED), stats.cache_tokens("t", CACHED), stats.get("t", CACHED))
    for k in (1, 2):
        _decide(stats, work_calls=k)
    assert (stats.tokens("t", CACHED), stats.cache_tokens("t", CACHED), stats.get("t", CACHED)) == before
