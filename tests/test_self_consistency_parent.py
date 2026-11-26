"""DESIGN 13.4 to 13.7 v1.669 (row JUDGE2d): the inline parent under the task's self-consistency minimum.

13.4 rule 6 reads the parent's share on the task as 5.2 rules 5g and 5h read a route's: once the key
holds `min_samples` rerun items, a share under `min_self_consistency` blocks inline as
`parent_inconsistent`, and with fewer rerun items the share is unknown and blocks it as
`parent_consistency_unknown`, with no `allow`. It comes after rules 1 to 5, the delegate is never the
parent's own model, the costs and bounds are those without the rule, and with no minimum no decision
changes. `model-routing delegate` prints the code.
"""

import json
from pathlib import Path

import pytest
from test_latency_docs import ROWS, run

import model_routing
from model_routing import Model, NoModelClearsBar, Policy, Registry, Router, Stats, Task
from model_routing import delegation

ROOT = Path(__file__).resolve().parents[1]
N, LEAST = 30, 0.9
CHEAP, MID, PRICEY = "a/cheap", "b/mid", "c/pricey"
TOKENS = {"input_tokens": 1000 * N, "output_tokens": 200 * N, "token_trials": N}
WORK = {"context_tokens": 20_000, "brief_tokens": 400, "result_tokens": 300}
SHAPES = [{}, {"work_calls": 3}, {"inline_separate_call": False}, {"brief_tokens": 0}]
SHAPE_IDS = ["one call", "K = 3", "folded", "no brief"]
INCONSISTENT, UNKNOWN = "parent_inconsistent", "parent_consistency_unknown"
ALIKE, SHAKY = (N, N), (N, 24)  # 30 of 30 alike; 24 of 30 is 0.8, under 0.9
STEADY = {CHEAP: SHAKY, MID: ALIKE, PRICEY: ALIKE}


def registry(cheap_window=100_000):
    return Registry([Model(CHEAP, "a", 0.1, 0.2, cheap_window), Model(MID, "b", 0.5, 1.0, 100_000),
                     Model(PRICEY, "c", 1.0, 2.0, 100_000)])


def router(shares, reg=None, times=None, **fields):
    """Every route at 30 of 30 with token counts; ``shares`` maps a model to (rerun items, alike), none if absent."""
    stats = Stats()
    for model_id in (CHEAP, MID, PRICEY):
        extra = {}
        if model_id in shares:
            extra.update(rerun_items=shares[model_id][0], consistent_items=shares[model_id][1])
        if times and model_id in times:
            extra["latencies_ms"] = times[model_id]
        stats.add("t", model_id, N, N, **TOKENS, **extra)
    task = Task("t", **{"bar": 0.8, "min_samples": N, "min_self_consistency": LEAST, **fields})
    return Router(reg or registry(), {"t": task}, stats)


def by_id(route):
    return {c.model_id: c for c in route.candidates}


def decide(r, parent=CHEAP, flavor="cost_effective", **extra):
    return r.decide_delegation("t", parent, flavor, **{**WORK, **extra})


# --- 13.6 v1.669: the two codes ----------------------------------------------------------------

def test_the_two_codes_have_their_pinned_values_and_stay_in_the_module():
    for name in ("PARENT_INCONSISTENT", "PARENT_CONSISTENCY_UNKNOWN"):
        assert getattr(delegation, name) == name.lower()
        assert name not in model_routing.__all__


# --- 13.4 rule 6 and 13.5 row 1 -----------------------------------------------------------------

@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_an_inconsistent_parent_cannot_work_inline_and_a_consistent_route_takes_the_work(flavor, shape):
    d = decide(router(STEADY), CHEAP, flavor, **shape)
    assert (d.mode, d.reason, d.inline_allowed, d.below_bar) == ("delegate", INCONSISTENT, False, False)
    assert d.model == d.route.primary and d.model in (MID, PRICEY)
    assert CHEAP not in d.route.fallbacks  # the delegate is never the parent's own model
    assert by_id(d.route)[CHEAP].reason == "inconsistent"


@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
def test_the_costs_bounds_and_delegate_are_those_without_the_rule(shape):
    """The rule moves `inline_allowed` and the row alone: the decision with no minimum and the parent's model
    excluded from the delegate has the same delegate, costs and bounds."""
    d = decide(router(STEADY), **shape)
    ref = decide(router(STEADY, min_self_consistency=None), exclude_models=(CHEAP,), **shape)
    assert ref.inline_allowed is True and ref.reason != INCONSISTENT
    assert d.model == d.route.primary == ref.route.primary
    assert (d.inline_cost_usd, d.delegate_cost_usd) == (ref.inline_cost_usd, ref.delegate_cost_usd)
    assert (d.parent_quality_lb, d.delegate_quality_lb) == (ref.parent_quality_lb, ref.delegate_quality_lb)


@pytest.mark.parametrize("share, least, blocked", [((N, 27), LEAST, False), ((N, 26), LEAST, True),
                                                   ((N, N), 1.0, False), ((N, N - 1), 1.0, True),
                                                   ((N, 0), 0.0, False)],
                         ids=["27 of 30 at 0.9", "26 of 30 at 0.9", "all at 1", "29 of 30 at 1", "none at 0"])
def test_the_parent_s_share_is_compared_as_it_is_and_must_be_under_the_minimum(share, least, blocked):
    d = decide(router({CHEAP: share, MID: ALIKE, PRICEY: ALIKE}, min_self_consistency=least))
    assert d.inline_allowed is (not blocked)
    assert (d.reason == INCONSISTENT) is blocked
    if not blocked:
        assert not d.reason.startswith("parent_")


@pytest.mark.parametrize("share", [None, (N - 1, N - 1), (0, 0)], ids=["no rerun data", "29 items", "0 items"])
def test_a_parent_with_fewer_than_min_samples_rerun_items_is_consistency_unknown_with_no_allow(share):
    shares = {MID: ALIKE, PRICEY: ALIKE}
    if share is not None:
        shares[CHEAP] = share
    for unknown in ("allow", "deny"):  # latency_unknown is the latency bar's, and there is no bar here
        d = decide(router(shares, latency_unknown=unknown))
        assert (d.mode, d.reason, d.inline_allowed) == ("delegate", UNKNOWN, False)
        assert d.model != CHEAP and by_id(d.route)[CHEAP].reason == "consistency_unknown"


@pytest.mark.parametrize("fields, reg, extra, reason", [
    ({"exclude_families": ("a",)}, None, {}, "parent_excluded_family"),
    ({"independent_of_generator": True}, None, {"generator_model": CHEAP}, "parent_not_independent"),
    ({}, "small", {}, "parent_context_full"),
    ({}, None, {"policy": Policy(allowed_families=("b", "c"))}, "parent_policy_excluded"),
    ({"max_p95_ms": 500.0}, None, {}, "parent_too_slow"),
    ({"max_p95_ms": 500.0, "latency_unknown": "deny"}, "untimed", {}, "parent_latency_unknown"),
], ids=["rule 1", "rule 2", "rule 3", "rule 4", "rule 5 slow", "rule 5 unknown"])
@pytest.mark.parametrize("share", [SHAKY, None], ids=["inconsistent", "unknown share"])
def test_rules_1_to_5_come_before_rule_6(fields, reg, extra, reason, share):
    shares = {MID: ALIKE, PRICEY: ALIKE, **({CHEAP: share} if share else {})}
    times = {MID: [100.0] * N, PRICEY: [100.0] * N}
    if reg != "untimed":
        times[CHEAP] = [900.0] * N
    r = router(shares, registry(10_000) if reg == "small" else None, times, **fields)
    assert decide(r, **extra).reason == reason


@pytest.mark.parametrize("on_no_model", ["refuse", "best_available"])
def test_an_inconsistent_parent_with_no_route_inside_the_minimum_raises_with_the_delegate_s_candidates(on_no_model):
    """Up to v1.668 this parent, clearing the success bar, worked inline as `only_parent_clears`."""
    r = router({CHEAP: SHAKY, MID: SHAKY, PRICEY: SHAKY}, on_no_model=on_no_model)
    with pytest.raises(NoModelClearsBar) as error:
        decide(r)
    assert {(c.model_id, c.reason) for c in error.value.candidates} == {
        (CHEAP, "inconsistent"), (MID, "inconsistent"), (PRICEY, "inconsistent")}


def test_the_router_is_left_as_it_was():
    r = router(STEADY)
    before = (dict(r.tasks), r.stats.consistency("t", CHEAP), r.stats.get("t", CHEAP))
    for shape in SHAPES:
        decide(r, **shape)
    assert (dict(r.tasks), r.stats.consistency("t", CHEAP), r.stats.get("t", CHEAP)) == before


# --- with no minimum nothing changes; a consistent parent decides as before ---------------------------

def test_with_no_minimum_an_inconsistent_parent_decides_as_on_stats_without_rerun_counts():
    counted, plain = router(STEADY, min_self_consistency=None), router({}, min_self_consistency=None)
    for parent in (CHEAP, MID, PRICEY):
        for flavor in ("cost_effective", "cost_blind"):
            for shape in SHAPES:
                assert (decide(counted, parent, flavor, **shape).to_dict()
                        == decide(plain, parent, flavor, **shape).to_dict())


@pytest.mark.parametrize("shape", SHAPES, ids=SHAPE_IDS)
@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_a_parent_inside_the_minimum_decides_as_with_no_minimum(flavor, shape):
    shares = {CHEAP: ALIKE, MID: ALIKE, PRICEY: ALIKE}
    for parent in (CHEAP, MID, PRICEY):
        held = decide(router(shares), parent, flavor, **shape).to_dict()
        free = decide(router(shares, min_self_consistency=None), parent, flavor, **shape).to_dict()
        assert held == free


# --- 13.7 v1.669: the command line -----------------------------------------------------------------

def make(d, shares, **task):
    d.mkdir(exist_ok=True)
    (d / "models.json").write_text(json.dumps({"models": ROWS}), encoding="utf-8")
    row = {"name": "t", "bar": 0.8, "min_samples": N, "expected_input_tokens": 1000, "expected_output_tokens": 200,
           "min_self_consistency": LEAST, **task}
    (d / "tasks.json").write_text(json.dumps({"tasks": [row]}), encoding="utf-8")
    stats = Stats()
    for model_id in (CHEAP, MID, PRICEY):
        extra = {}
        if model_id in shares:
            extra.update(rerun_items=shares[model_id][0], consistent_items=shares[model_id][1])
        stats.add("t", model_id, N, N, **extra)
    stats.save(d / "stats.json")
    return ["--registry", str(d / "models.json"), "--tasks", str(d / "tasks.json"), "--stats", str(d / "stats.json")]


def argv(parent):
    return ["--parent", parent, "--context-tokens", "2000", "--brief-tokens", "1000", "--result-tokens", "1000"]


def test_delegate_prints_parent_inconsistent_on_its_reason_line_and_in_json(tmp_path):
    base = make(tmp_path, STEADY)
    code, out, err = run(["delegate", "t", *argv(CHEAP), *base])
    assert (code, err) == (0, "")
    fields = dict(line.split(":", 1) for line in out.splitlines())
    assert (fields["mode"].strip(), fields["model"].strip(), fields["reason"].strip()) == ("delegate", MID, INCONSISTENT)
    code, out, err = run(["delegate", "t", *argv(CHEAP), "--json", *base])
    assert (code, err) == (0, "")
    data = json.loads(out)
    assert (data["reason"], data["inline_allowed"], data["model"]) == (INCONSISTENT, False, MID)
    assert {c["model_id"]: c["reason"] for c in data["route"]["candidates"]}[CHEAP] == "inconsistent"


def test_delegate_prints_parent_consistency_unknown_for_a_parent_with_no_rerun_data(tmp_path):
    base = make(tmp_path, {MID: ALIKE, PRICEY: ALIKE})
    code, out, err = run(["delegate", "t", *argv(CHEAP), "--json", *base])
    assert (code, err) == (0, "")
    data = json.loads(out)
    assert (data["mode"], data["model"], data["reason"]) == ("delegate", MID, UNKNOWN)


def test_delegate_exits_3_when_the_minimum_leaves_an_inconsistent_parent_no_route(tmp_path):
    base = make(tmp_path, {CHEAP: SHAKY, MID: SHAKY})  # the pricey route has no rerun data
    code, out, err = run(["delegate", "t", *argv(CHEAP), *base])
    assert code == 3 and out == ""
    assert "inconsistent" in err and "consistency_unknown" in err


def test_with_no_minimum_delegate_prints_what_it_prints_on_stats_without_rerun_counts(tmp_path):
    counted = make(tmp_path / "counted", STEADY, min_self_consistency=None)
    plain = make(tmp_path / "plain", {}, min_self_consistency=None)
    for parent in (CHEAP, MID, PRICEY):
        for extra in ([], ["--json"]):
            assert run(["delegate", "t", *argv(parent), *extra, *counted]) == \
                run(["delegate", "t", *argv(parent), *extra, *plain])


# --- the spec ---------------------------------------------------------------------------------------

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def part(text, start, end):
    return text.split(f"\n### {start} ", 1)[1].split(f"\n### {end} ", 1)[0]


def test_design_and_the_changelog_state_v1_669():
    design = read("DESIGN.md")
    four = part(design, "13.4", "13.5")
    assert four.count("\n6. v1.669 (row JUDGE2d): the task sets `min_self_consistency` (4.2 v1.668) and the parent's "
                      "share on the task, read as 5.2 rules 5g and 5h read a route's") == 1
    assert four.index("\n5. v1.631 (row LAT1d): ") < four.index("\n6. v1.669 (row JUDGE2d): ")
    assert four.count("is under the minimum: `parent_inconsistent` (5g); or that share is unknown: "
                      "`parent_consistency_unknown` (5h), with no `allow`, as 5h has none") == 1
    assert four.count("\n- v1.669 (row JUDGE2d), why the parent's share on the task stands for its inline work: ") == 1
    assert four.count("that makes the share a proxy, not a bound") == 1
    assert four.count("From v1.669 rule 6 reads the parent's share (row JUDGE2d, the bullet below)") == 1
    assert "no rule reads the parent's self-consistency" not in four
    assert part(design, "13.5", "13.6").count("\n- v1.669 (row JUDGE2d): row 1 takes a parent that 13.4 rule 6 "
                                              "blocks, ") == 1
    six = part(design, "13.6", "13.7")
    assert six.count("`PARENT_INCONSISTENT`, `PARENT_CONSISTENCY_UNKNOWN` (the two from v1.669)") == 1
    assert six.count("\n- v1.669: the fields and `to_dict()` are unchanged, the parent's share being in no field") == 1
    seven = part(design, "13.7", "13.8")
    assert seven.count("\n- v1.669 (row JUDGE2d): a parent the self-consistency minimum rules out (13.4 rule 6) "
                       "prints ") == 1
    five2 = part(design, "5.2", "5.3")
    assert five2.count("and from v1.669 so does its inline parent (13.4 rule 6, row JUDGE2d)") == 1
    assert "while its inline parent reads no share" not in five2
    # the Status line keeps five versions (tests/test_design_status.py), so the version is pinned by its
    # changelog line, which stays
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.669 (")]
    assert line.startswith("- v1.669 (2026-11-26): spec, code and tests (5.2, 13.4, 13.5, 13.6, 13.7, row JUDGE2d). ")
    assert len(line.encode("utf-8")) <= 600
