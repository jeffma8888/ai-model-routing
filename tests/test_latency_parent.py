"""DESIGN 13.4 to 13.7 v1.631 (row LAT1d): the inline parent under the task's latency bar.

13.4 rule 5 reads the parent's time on the task as 5.2 rules 5e and 5f read a route's: once the key
holds `min_samples` times, a p95 above `max_p95_ms` blocks inline as `parent_too_slow`, and with
`latency_unknown="deny"` an unknown time blocks it as `parent_latency_unknown`. It comes after rules 1
to 4, the delegate is never the parent's own model, the costs and bounds are those without the rule,
and with no bar no decision changes. `model-routing delegate` prints the code on its `reason:` line.
"""

import json
from pathlib import Path

import pytest
from test_latency_docs import make, run

import model_routing
from model_routing import Model, NoModelClearsBar, Policy, Registry, Router, Stats, Task
from model_routing import delegation

ROOT = Path(__file__).resolve().parents[1]
N, BAR = 30, 500.0
CHEAP, MID, PRICEY = "a/cheap", "b/mid", "c/pricey"
FAST, SLOW = [100.0] * N, [900.0] * N
TOKENS = {"input_tokens": 1000 * N, "output_tokens": 200 * N, "token_trials": N}
WORK = {"context_tokens": 20_000, "brief_tokens": 400, "result_tokens": 300}
SHAPES = [{}, {"work_calls": 3}, {"inline_separate_call": False}, {"brief_tokens": 0}]
SHAPE_IDS = ["one call", "K = 3", "folded", "no brief"]
TOO_SLOW, UNKNOWN = "parent_too_slow", "parent_latency_unknown"


def registry(cheap_window=100_000):
    return Registry([Model(CHEAP, "a", 0.1, 0.2, cheap_window), Model(MID, "b", 0.5, 1.0, 100_000),
                     Model(PRICEY, "c", 1.0, 2.0, 100_000)])


def router(times, reg=None, **fields):
    """Every route at 30 of 30 with token counts; ``times`` maps a model to its latencies, none if absent."""
    stats = Stats()
    for model_id in (CHEAP, MID, PRICEY):
        extra = {"latencies_ms": times[model_id]} if model_id in times else {}
        stats.add("t", model_id, N, N, **TOKENS, **extra)
    task = Task("t", **{"bar": 0.8, "min_samples": N, "max_p95_ms": BAR, **fields})
    return Router(reg or registry(), {"t": task}, stats)


def by_id(route):
    return {c.model_id: c for c in route.candidates}


def decide(r, parent=CHEAP, flavor="cost_effective", **extra):
    return r.decide_delegation("t", parent, flavor, **{**WORK, **extra})


# --- 13.6 v1.631: the two codes ----------------------------------------------------------------

def test_the_two_codes_have_their_pinned_values_and_stay_in_the_module():
    for name in ("PARENT_TOO_SLOW", "PARENT_LATENCY_UNKNOWN"):
        assert getattr(delegation, name) == name.lower()
        assert name not in model_routing.__all__


# --- 13.4 rule 5 and 13.5 row 1 -----------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_a_parent_measured_slow_cannot_work_inline_and_a_fast_route_takes_the_work(flavor, shape):
    d = decide(router({CHEAP: SLOW, MID: FAST, PRICEY: FAST}), CHEAP, flavor, **shape)
    assert (d.mode, d.reason, d.inline_allowed, d.below_bar) == ("delegate", TOO_SLOW, False, False)
    assert d.model == d.route.primary and d.model in (MID, PRICEY)
    assert CHEAP not in d.route.fallbacks  # the delegate is never the parent's own model
    assert (by_id(d.route)[CHEAP].reason, by_id(d.route)[CHEAP].p95_latency_ms) == ("too_slow", 900.0)


@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
def test_the_costs_bounds_and_delegate_are_those_without_the_rule(shape):
    """The rule moves `inline_allowed` and the row alone: the decision with no bar and the parent's model
    excluded from the delegate has the same delegate, costs and bounds."""
    d = decide(router({CHEAP: SLOW, MID: FAST, PRICEY: FAST}), **shape)
    ref = decide(router({CHEAP: SLOW, MID: FAST, PRICEY: FAST}, max_p95_ms=None), exclude_models=(CHEAP,), **shape)
    assert ref.inline_allowed is True and ref.reason != TOO_SLOW
    assert d.model == d.route.primary == ref.route.primary  # ref may work inline: folded work is cheaper there
    assert (d.inline_cost_usd, d.delegate_cost_usd) == (ref.inline_cost_usd, ref.delegate_cost_usd)
    assert (d.parent_quality_lb, d.delegate_quality_lb) == (ref.parent_quality_lb, ref.delegate_quality_lb)


@pytest.mark.parametrize("times, blocked", [([100.0] * 29 + [900.0], False), ([100.0] * 28 + [900.0] * 2, True),
                                            ([BAR] * N, False), ([BAR + 0.5] * N, True)],
                         ids=["1 slow of 30", "2 slow of 30", "at the bar", "just above"])
def test_the_parent_s_p95_is_by_nearest_rank_and_must_be_above_the_bar(times, blocked):
    d = decide(router({CHEAP: times, MID: FAST, PRICEY: FAST}))
    assert d.inline_allowed is (not blocked)
    assert (d.reason == TOO_SLOW) is blocked
    if not blocked:
        assert not d.reason.startswith("parent_")


@pytest.mark.parametrize("times", [None, [900.0] * (N - 1)], ids=["untimed", "29 slow times"])
def test_a_parent_with_fewer_than_min_samples_times_follows_latency_unknown(times):
    timed = {MID: FAST, PRICEY: FAST}
    if times is not None:
        timed[CHEAP] = times
    allow = decide(router(timed))
    assert allow.inline_allowed is True and not allow.reason.startswith("parent_")
    deny = decide(router(timed, latency_unknown="deny"))
    assert (deny.mode, deny.reason, deny.inline_allowed) == ("delegate", UNKNOWN, False)
    assert deny.model != CHEAP and by_id(deny.route)[CHEAP].reason == "latency_unknown"


@pytest.mark.parametrize("fields, reg, extra, reason", [
    ({"exclude_families": ("a",)}, None, {}, "parent_excluded_family"),
    ({"independent_of_generator": True}, None, {"generator_model": CHEAP}, "parent_not_independent"),
    ({}, "small", {}, "parent_context_full"),
    ({}, None, {"policy": Policy(allowed_families=("b", "c"))}, "parent_policy_excluded"),
], ids=["rule 1", "rule 2", "rule 3", "rule 4"])
@pytest.mark.parametrize("deny", [False, True], ids=["slow", "untimed under deny"])
def test_rules_1_to_4_come_before_rule_5(fields, reg, extra, reason, deny):
    times = {MID: FAST, PRICEY: FAST} if deny else {CHEAP: SLOW, MID: FAST, PRICEY: FAST}
    if deny:
        fields = {**fields, "latency_unknown": "deny"}
    r = router(times, registry(10_000) if reg else None, **fields)
    assert decide(r, **extra).reason == reason


@pytest.mark.parametrize("on_no_model", ["refuse", "best_available"])
def test_a_slow_parent_with_no_route_inside_the_bar_raises_with_the_delegate_s_candidates(on_no_model):
    """Up to v1.630 this parent, clearing the success bar, worked inline as `only_parent_clears`."""
    r = router({CHEAP: SLOW, MID: SLOW, PRICEY: SLOW}, on_no_model=on_no_model)
    with pytest.raises(NoModelClearsBar) as error:
        decide(r)
    assert {(c.model_id, c.reason) for c in error.value.candidates} == {
        (CHEAP, "too_slow"), (MID, "too_slow"), (PRICEY, "too_slow")}


def test_the_router_is_left_as_it_was():
    r = router({CHEAP: SLOW, MID: FAST, PRICEY: FAST})
    before = (dict(r.tasks), r.stats.latencies("t", CHEAP), r.stats.get("t", CHEAP))
    for shape in SHAPES:
        decide(r, **shape)
    assert (dict(r.tasks), r.stats.latencies("t", CHEAP), r.stats.get("t", CHEAP)) == before


# --- with no bar nothing changes; a fast parent decides as before ------------------------------------

@pytest.mark.parametrize("fields", [{"max_p95_ms": None}, {"max_p95_ms": None, "latency_unknown": "deny"}],
                         ids=["no bar", "deny without a bar"])
def test_with_no_bar_a_slow_parent_decides_as_on_untimed_stats(fields):
    timed, plain = router({CHEAP: SLOW, MID: SLOW}, **fields), router({}, **fields)
    for parent in (CHEAP, MID, PRICEY):
        for flavor in ("cost_effective", "cost_blind"):
            for shape in SHAPES:
                assert (decide(timed, parent, flavor, **shape).to_dict()
                        == decide(plain, parent, flavor, **shape).to_dict())


@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_a_parent_inside_the_bar_decides_as_with_no_bar(flavor, shape):
    keys = ("mode", "model", "reason", "below_bar", "inline_allowed", "inline_cost_usd", "delegate_cost_usd",
            "parent_quality_lb", "delegate_quality_lb")
    times = {CHEAP: FAST, MID: FAST, PRICEY: FAST}
    for parent in (CHEAP, MID, PRICEY):
        barred = decide(router(times), parent, flavor, **shape).to_dict()
        free = decide(router(times, max_p95_ms=None), parent, flavor, **shape).to_dict()
        assert {k: barred[k] for k in keys} == {k: free[k] for k in keys}


# --- 13.7 v1.631: the command line -----------------------------------------------------------------

def argv(parent):
    return ["--parent", parent, "--context-tokens", "2000", "--brief-tokens", "1000", "--result-tokens", "1000"]


def test_delegate_prints_parent_too_slow_on_its_reason_line_and_in_json(tmp_path):
    base = make(tmp_path, max_p95_ms=BAR)  # the cheap route has two of its 30 times at 900 ms
    code, out, err = run(["delegate", "t", *argv(CHEAP), *base])
    assert (code, err) == (0, "")
    fields = dict(line.split(":", 1) for line in out.splitlines())
    assert (fields["mode"].strip(), fields["model"].strip(), fields["reason"].strip()) == ("delegate", MID, TOO_SLOW)
    code, out, err = run(["delegate", "t", *argv(CHEAP), "--json", *base])
    assert (code, err) == (0, "")
    data = json.loads(out)
    assert (data["reason"], data["inline_allowed"], data["model"]) == (TOO_SLOW, False, MID)
    found = {c["model_id"]: c for c in data["route"]["candidates"]}
    assert (found[CHEAP]["reason"], found[CHEAP]["p95_latency_ms"]) == ("too_slow", 900.0)


def test_delegate_prints_parent_latency_unknown_for_an_untimed_parent_under_deny(tmp_path):
    base = make(tmp_path, max_p95_ms=BAR, latency_unknown="deny")  # the pricey route is untimed
    code, out, err = run(["delegate", "t", *argv(PRICEY), "--json", *base])
    assert (code, err) == (0, "")
    data = json.loads(out)
    assert (data["mode"], data["model"], data["reason"]) == ("delegate", MID, UNKNOWN)


def test_delegate_exits_3_when_the_bar_leaves_a_slow_parent_no_route(tmp_path):
    base = make(tmp_path, max_p95_ms=50, latency_unknown="deny")  # every timed route is above 50 ms
    code, out, err = run(["delegate", "t", *argv(CHEAP), *base])
    assert code == 3 and out == ""
    assert "too_slow" in err and "latency_unknown" in err


# --- the spec and the docs ------------------------------------------------------------------------------

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_design_and_the_changelog_state_v1_631():
    design = read("DESIGN.md")
    four = design.split("\n### 13.4 ", 1)[1].split("\n### 13.5 ", 1)[0]
    assert four.count("\n5. v1.631 (row LAT1d): the task sets `max_p95_ms` (4.2 v1.628) and the parent's time") == 1
    assert four.count("\n- v1.631 (row LAT1d), why the parent's time on the task bounds its inline work: ") == 1
    assert "no rule reads the parent's time" not in four
    five = design.split("\n### 13.5 ", 1)[1].split("\n### 13.6 ", 1)[0]
    assert five.count("\n- v1.631 (row LAT1d): row 1 takes a parent that 13.4 rule 5 blocks, ") == 1
    six = design.split("\n### 13.6 ", 1)[1].split("\n### 13.7 ", 1)[0]
    assert six.count("`PARENT_TOO_SLOW`, `PARENT_LATENCY_UNKNOWN` (the two from v1.631)") == 1
    seven = design.split("\n### 13.7 ", 1)[1].split("\n### 13.8 ", 1)[0]
    assert seven.count("\n- v1.631 (row LAT1d): a parent the latency bar rules out prints ") == 1
    five2 = design.split("\n### 5.2 ", 1)[1].split("\n### 5.3 ", 1)[0]
    assert five2.count("\n- v1.631 README and note (row LAT1d): ") == 1
    assert "and its inline parent reads no time (13.4 v1.628)" not in five2
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.631 (")]
    assert line.startswith("- v1.631 (2026-11-24): spec, code and tests (5.2, 13.4, 13.5, 13.6, 13.7, row LAT1d). ")


def test_the_readme_and_the_note_no_longer_hold_the_parent_to_no_time():
    assert "while a parent working inline is held to no time" not in read("README.md")
    assert "The change: the same bar on a parent's inline work" not in read("research/production-lessons.md")
