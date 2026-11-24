"""The pair file: `shadow_pairs` reads a monitor log into one pair record per shadow that ran
(DESIGN 8.3 v1.610, row CANARY1b; the shadow calls are 7 and 8.1 v1.607 and v1.609)."""

from pathlib import Path

import pytest

import model_routing
from model_routing import (
    Completion, Executor, FakeProvider, Model, Monitor, ProviderError, Registry, Router, Stats,
    Task,
)

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
KEYS = ["pair_id", "task", "slice", "routed_route", "shadow_route", "shadow_call_id",
        "shadow_outcome", "routed_correct", "shadow_correct"]


def pairs(*args, **kwargs):
    return model_routing.shadow_pairs(*args, **kwargs)


def router():
    """cost_effective routes cheap first, then mid and best; the default shadow route is best."""
    task = Task("judge", bar=0.7, min_samples=10, shadow_rate=1.0)
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (MID, (95, 100)),
                                          (BEST, (100, 100))):
        stats.add(task.name, model_id, successes, trials)
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000),
                         Model(BEST, "large", 10.0, 20.0, 8000)])
    return Router(registry, {task.name: task}, stats)


def answers(*texts):
    """A script callable that answers each text in turn, then raises ProviderError."""
    queue = list(texts)

    def complete(messages):
        if not queue:
            raise ProviderError("outage")
        return Completion(queue.pop(0), 1000, 200)
    return complete


def run(script, calls, validate=None):
    monitor = Monitor()
    ids = iter(f"call-{i}" for i in range(1000))
    ticks = iter(float(i) for i in range(10_000))
    executor = Executor(router(), FakeProvider(script), monitor=monitor,
                        clock=lambda: next(ticks), now=lambda: "2026-11-23T00:00:00Z",
                        id_factory=lambda: next(ids), random=lambda: 0.0)
    for _ in range(calls):
        executor.call("judge", MESSAGES, validate=validate)
    return monitor.records


def three_shadows():
    """Shadows that answer ok, answer invalid, then err (calls call-0/1, call-2/3, call-4/5)."""
    script = {CHEAP: answers("cheap", "cheap", "cheap"), BEST: answers("best", "bad")}
    return run(script, 3, validate=lambda text: text != "bad")


def pair(pair_id, shadow_call_id, outcome, routed=None, shadow=None, route=CHEAP, slice=None):
    return {"pair_id": pair_id, "task": "judge", "slice": slice, "routed_route": route,
            "shadow_route": BEST, "shadow_call_id": shadow_call_id, "shadow_outcome": outcome,
            "routed_correct": routed, "shadow_correct": shadow}


def rec(call_id, pair_id, shadow, final=True, model=CHEAP, outcome="ok", **extra):
    """A hand-built attempt record with the v1.607 pair keys."""
    return {"call_id": call_id, "task": "judge", "model": model, "attempt": 0, "final": final,
            "outcome": outcome, "slice": None, "pair_id": pair_id, "shadow": shadow, **extra}


# --- the pairs of a real log -------------------------------------------------------------

def test_one_unlabelled_pair_per_shadow_that_ran_in_shadow_record_order():
    result = pairs(three_shadows())
    assert result == [pair("call-0", "call-1", "ok"), pair("call-2", "call-3", "invalid"),
                      pair("call-4", "call-5", "error")]
    assert all(list(p) == KEYS for p in result)


def test_checked_labels_an_ok_side_true_an_invalid_one_false_and_an_error_none():
    result = pairs(three_shadows(), checked=True)
    assert [(p["routed_correct"], p["shadow_correct"]) for p in result] == [
        (True, True), (True, False), (True, None)]


def test_audits_label_the_audited_sides_and_never_an_error_side():
    audits = {"call-0": False, "call-1": True, "call-3": True, "call-5": True}
    result = pairs(three_shadows(), audits=audits)
    assert [(p["routed_correct"], p["shadow_correct"]) for p in result] == [
        (False, True), (None, False), (None, None)]  # call-3 is invalid (should-fix 2)


def test_an_invalid_side_is_false_under_audits_audited_or_not():
    for audits in ({"call-3": True}, {}):
        assert pairs(three_shadows(), audits=audits)[1]["shadow_correct"] is False


def test_a_fallback_s_answer_names_the_fallback_as_the_routed_route():
    records = run({MID: answers("mid"), BEST: answers("best")}, 1)  # cheap errs, mid answers
    assert pairs(records) == [pair("call-0", "call-1", "ok", route=MID)]


def test_a_shadow_that_was_not_sent_has_no_pair():
    records = run({BEST: answers("best")}, 1)  # cheap and mid err, so best answers: no shadow
    assert any(r.get("pair_id") == "call-0" for r in records)
    assert pairs(records) == []


def test_records_are_left_unchanged():
    records = three_shadows()
    before = [dict(r) for r in records]
    pairs(records, checked=True)
    assert records == before


# --- hand-built logs --------------------------------------------------------------------

def test_a_refused_shadow_has_no_pair_and_budget_records_are_dropped():
    refused = {"ts": "t", "call_id": "s1", "task": "judge", "tags": {"shadow": "true"},
               "pair_id": "r1", "shadow": True, "budget_event": "refused"}
    assert pairs([rec("r1", "r1", False), refused]) == []


def test_the_routed_side_is_the_final_record_and_its_route_entry():
    records = [rec("r1", "r1", False, final=False, outcome="error"),
               rec("r1", "r1", False, model=MID, slice="deep"),
               rec("s1", "r1", True, model=BEST),
               rec("r2", "r2", False, cascade="judge/cascade"),
               rec("s2", "r2", True, model=BEST, outcome="invalid"),
               rec("r3", "r3", False, model="proc:p@1", procedure="p", model_calls=1),
               rec("s3", "r3", True, model=BEST),
               rec("x", None, None)]
    result = pairs(records)
    assert [p["routed_route"] for p in result] == [MID, "judge/cascade", "proc:p@1"]
    assert result[0]["slice"] == "deep" and result[1]["shadow_outcome"] == "invalid"


@pytest.mark.parametrize("kwargs", [
    {"checked": 1}, {"checked": None}, {"audits": [("r1", True)]}, {"audits": {"r1": 1}},
    {"audits": {"": True}}, {"audits": {3: True}}, {"checked": True, "audits": {}},
])
def test_bad_label_arguments_are_value_errors(kwargs):
    with pytest.raises(ValueError):
        pairs([rec("r1", "r1", False), rec("s1", "r1", True, model=BEST)], **kwargs)


@pytest.mark.parametrize("records, name", [
    ([rec("r1", "r1", False), rec("s1", "", True)], "''"),
    ([rec("r1", "r1", False), rec("s1", 7, True)], "7"),
    ([rec("r1", "r1", False), rec("s1", "r1", True), rec("s2", "r1", True)], "'r1'"),
    ([rec("s1", "r1", True)], "'r1'"),
    ([rec("r1", "r1", False, final=False), rec("s1", "r1", True)], "'r1'"),
    ([rec("r1", "r1", False), rec("r1", "r1", False), rec("s1", "r1", True)], "'r1'"),
])
def test_a_log_the_executor_cannot_write_is_a_value_error_naming_the_pair(records, name):
    with pytest.raises(ValueError, match=name):
        pairs(records)


@pytest.mark.parametrize("call_id", ["", None, [1], 7])
def test_a_shadow_record_s_bad_call_id_is_a_value_error_naming_the_pair(call_id):
    records = [rec("r1", "r1", False), rec(call_id, "r1", True, model=BEST)]
    for kwargs in ({}, {"audits": {"r1": True}}):  # review iter-461 should-fix 3
        with pytest.raises(ValueError, match="'r1'"):
            pairs(records, **kwargs)


def test_pairs_follow_the_shadow_records_not_the_routed_ones():
    records = [rec("r2", "r2", False), rec("r1", "r1", False),
               rec("s1", "r1", True, model=BEST), rec("s2", "r2", True, model=BEST)]
    assert [p["pair_id"] for p in pairs(records)] == ["r1", "r2"]  # should-fix 4


def test_a_routed_record_without_the_pair_keys_is_no_routed_side():
    plain = {k: v for k, v in rec("r1", "r1", False).items() if k not in ("pair_id", "shadow")}
    with pytest.raises(ValueError, match="'r1'"):  # should-fix 1
        pairs([plain, rec("s1", "r1", True, model=BEST)])


def test_an_empty_log_or_one_without_shadows_has_no_pairs():
    assert pairs([]) == []
    assert pairs([rec("r1", None, None)]) == []


# --- exports and spec -------------------------------------------------------------------

def test_shadow_pairs_is_exported_after_budget_report():
    names = model_routing.__all__
    assert names[names.index("budget_report") + 1] == "shadow_pairs"
    assert model_routing.shadow_pairs is model_routing.monitor.shadow_pairs


def test_design_names_the_function_in_its_layout_line_and_in_8_3():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert "report, budget_report (v1.598), shadow_pairs (v1.610)" in design
    section = design[design.index("### 8.3 "):design.index("## 9. Data files")]
    assert "- v1.610 `shadow_pairs(records, *, checked=False, audits=None) -> list[dict]`" in section
