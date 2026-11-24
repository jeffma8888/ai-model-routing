"""Whether a shadowed call ran its check (DESIGN 7, 8.1, 8.3 and 10 v1.618, row CANARY1l).

From v1.618 every record of a shadowed call, the routed call's and the shadow's, budget records
included, carries `checked` right after `shadow`: `true` when `.call` was given a `validate` and
`false` when it was given None. So `shadow_pairs(..., checked=True)` and `pairs --checked` refuse a
pair whose records say no check ran, where v1.610 had only the caller's word for it, while a
record with no `checked` key, as a log from before v1.618 holds, is still taken on that word. A
call that is not shadowed writes no new key.
"""

import pytest
from model_routing import (
    Budget, BudgetLedger, Cascade, Completion, Executor, FakeProvider, Model, Monitor, Procedure,
    ProcedureResult, ProviderError, Registry, Router, Stats, Task, load_records, shadow_pairs,
)
from model_routing.cli import main

MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
REGISTRY = Registry([
    Model(CHEAP, "small", 1.0, 2.0, 8000),
    Model(MID, "medium", 3.0, 6.0, 8000),
    Model(BEST, "large", 10.0, 20.0, 8000),
])
PAIR_KEYS = ["pair_id", "shadow", "checked"]


def router(**fields):
    """cost_effective routes cheap first; the default shadow route is best (bound highest)."""
    task = Task("judge", bar=0.7, min_samples=10, **fields)
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (MID, (95, 100)),
                                          (BEST, (100, 100))):
        stats.add(task.name, model_id, successes, trials)
    return Router(REGISTRY, {task.name: task}, stats)


def answer(text):
    return lambda messages: Completion(text, 1000, 200)


def provider(**overrides):
    script = {CHEAP: answer("cheap"), MID: answer("mid"), BEST: answer("best")}
    script.update(overrides)
    return FakeProvider(script)


def outage(messages):
    raise ProviderError("outage")


def make(route, monitor, *, random=lambda: 0.0, prov=None, **kwargs):
    ticks = iter(float(i) for i in range(10_000))
    ids = iter(f"call-{i}" for i in range(10_000))
    return Executor(route, prov or provider(), monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: "2026-11-24T00:00:00Z", id_factory=lambda: next(ids),
                    random=random, **kwargs)


def never():
    raise AssertionError("random was called")


def accept(text):
    return True


CHECKS = pytest.mark.parametrize("validate, value", [(accept, True), (None, False)],
                                 ids=["validate", "none"])


def after_slice(rec, count):
    keys = list(rec)
    at = keys.index("slice") + 1
    return keys[at:at + count]


# --- 7 and 8.1 v1.618: the records ---------------------------------------------------------------

@CHECKS
def test_both_calls_records_carry_checked_right_after_shadow(validate, value):
    base, monitor = Monitor(), Monitor()
    make(router(), base, random=never).call("judge", MESSAGES, validate=validate)
    make(router(shadow_rate=1.0), monitor).call("judge", MESSAGES, validate=validate)
    routed, shadow = monitor.records
    assert (routed["shadow"], shadow["shadow"]) == (False, True)
    keys = list(base.records[0])
    at = keys.index("slice") + 1
    for rec in (routed, shadow):
        assert list(rec) == keys[:at] + PAIR_KEYS + keys[at:]
        assert rec["checked"] is value


@CHECKS
def test_budget_records_of_both_calls_carry_it_right_after_shadow(validate, value):
    warned, refused = Monitor(), Monitor()
    cheap = REGISTRY.get(CHEAP).cost(1000, 200)
    make(router(shadow_rate=1.0), warned, ledger=BudgetLedger([Budget("w", cheap, "warn")])).call(
        "judge", MESSAGES, validate=validate)
    make(router(shadow_rate=1.0), refused, ledger=BudgetLedger(
        [Budget("shadows", 0.001, "refuse", tags={"shadow": "true"})])).call(
        "judge", MESSAGES, validate=validate)
    budget = [rec for rec in warned.records + refused.records if "budget_event" in rec]
    assert {(rec["budget_event"], rec["shadow"]) for rec in budget} == {("warn", False),
                                                                         ("refused", True)}
    for rec in budget:
        assert list(rec)[:7] == ["ts", "call_id", "task", "tags"] + PAIR_KEYS
    assert all(rec["checked"] is value for rec in warned.records + refused.records)


def test_an_invalid_shadow_says_checked_and_its_pair_labels_it_false():
    monitor = Monitor()
    make(router(shadow_rate=1.0), monitor).call("judge", MESSAGES,
                                                validate=lambda text: text != "best")
    routed, shadow = monitor.records
    assert (routed["outcome"], shadow["outcome"]) == ("ok", "invalid")
    assert (routed["checked"], shadow["checked"]) == (True, True)
    pairs = shadow_pairs(monitor.records, checked=True)
    assert [(p["routed_correct"], p["shadow_correct"]) for p in pairs] == [(True, False)]


@pytest.mark.parametrize("first, second", [(accept, None), (None, accept)])
def test_a_runner_s_job_writes_the_value_of_the_call_that_handed_it_over(first, second):
    jobs, monitor = [], Monitor()
    executor = make(router(shadow_rate=1.0), monitor, shadow_runner=jobs.append)
    executor.call("judge", MESSAGES, validate=first)
    executor.call("judge", MESSAGES, validate=second)
    assert [rec["shadow"] for rec in monitor.records] == [False, False]
    for job in jobs:
        job()
    values = {"call-0": first is not None, "call-2": second is not None}
    assert [(rec["call_id"], rec["pair_id"], rec["shadow"]) for rec in monitor.records] == [
        ("call-0", "call-0", False), ("call-2", "call-2", False),
        ("call-1", "call-0", True), ("call-3", "call-2", True)]
    for rec in monitor.records:
        assert after_slice(rec, 3) == PAIR_KEYS
        assert rec["checked"] is values[rec["pair_id"]]


@CHECKS
def test_a_skipped_shadow_s_routed_record_carries_it(validate, value):
    monitor = Monitor()
    result = make(router(shadow_rate=1.0, shadow_route=MID), monitor,
                  prov=provider(**{CHEAP: outage})).call("judge", MESSAGES, validate=validate)
    assert result.model == MID  # a fallback onto the shadow route answered (7 v1.609)
    assert [(r["model"], r["outcome"], r["pair_id"], r["shadow"]) for r in monitor.records] == [
        (CHEAP, "error", "call-0", False), (MID, "ok", "call-0", False)]
    for rec in monitor.records:
        assert after_slice(rec, 3) == PAIR_KEYS and rec["checked"] is value


CASCADE = Cascade(CHEAP, MID, "sig")


def entry_stats(entry_id, **counts):
    """cheap is under the bar, so the entry leads the route and best is the default shadow."""
    stats = Stats()
    for model_id, successes in ((CHEAP, 50), (MID, 95), (BEST, 98)):
        stats.add("judge", model_id, successes, 100)
    stats.add("judge", entry_id, 100, 100, **counts)
    return stats


def polling(value, call):
    return ProcedureResult("shaped " + call([{"role": "user", "content": "summarize"}]),
                           tool_calls=1)


POLLING = Procedure("poll", "v1", polling, max_model_calls=1, max_tool_calls=1, model=CHEAP)


@CHECKS
def test_a_cascade_primary_s_legs_carry_it_the_escalated_cheap_leg_included(validate, value):
    task = Task("judge", bar=0.7, min_samples=10, cascades=(CASCADE,), shadow_rate=1.0)
    monitor = Monitor()
    result = make(Router(REGISTRY, {"judge": task}, entry_stats(CASCADE.id, escalated=20)),
                  monitor).call("judge", MESSAGES, validate=validate,
                                signals={"sig": lambda output: True})
    assert result.model == MID
    cheap, strong, shadow = monitor.records
    assert [(r["model"], r["final"], r["shadow"]) for r in monitor.records] == [
        (CHEAP, False, False), (MID, True, False), (BEST, True, True)]
    for rec in (cheap, strong):
        assert after_slice(rec, 5) == PAIR_KEYS + ["cascade", "escalated"]
    assert after_slice(shadow, 3) == PAIR_KEYS
    assert all(rec["checked"] is value for rec in monitor.records)


@CHECKS
def test_a_procedure_primary_s_records_carry_it_its_model_call_included(validate, value):
    task = Task("judge", bar=0.7, min_samples=10, shadow_rate=1.0)
    monitor = Monitor()
    result = make(Router(REGISTRY, {"judge": task}, entry_stats(POLLING.id, cost_usd=0.02)),
                  monitor).call("judge", MESSAGES, validate=validate, procedures=[POLLING])
    assert result.model == POLLING.id
    call, closing, shadow = monitor.records
    assert [(r["model"], r["final"], r["shadow"]) for r in monitor.records] == [
        (CHEAP, False, False), (POLLING.id, True, False), (BEST, True, True)]
    for rec in (call, closing):
        assert after_slice(rec, 5) == PAIR_KEYS + ["procedure", "procedure_version"]
    assert all(rec["checked"] is value for rec in monitor.records)


PLAIN_KEYS = ["ts", "call_id", "task", "flavor", "model", "family", "attempt", "final", "outcome",
              "error", "latency_ms", "input_tokens", "output_tokens", "cost_usd",
              "routing_cost_usd", "below_bar", "basis", "tags", "slice", "prompt_tokens",
              "prompt_tokens_estimated"]


@pytest.mark.parametrize("fields, random", [({}, never), ({"shadow_rate": 0.5}, lambda: 0.5)],
                         ids=["rate 0", "a draw at the rate"])
def test_a_call_that_is_not_shadowed_writes_the_same_records_with_and_without_a_validate(
        fields, random):
    checked, unchecked = Monitor(), Monitor()
    make(router(**fields), checked, random=random).call("judge", MESSAGES, validate=accept)
    make(router(**fields), unchecked, random=random).call("judge", MESSAGES)
    assert checked.records == unchecked.records and len(checked.records) == 1
    assert list(checked.records[0]) == PLAIN_KEYS  # none of the three pair keys


# --- 8.3 v1.618: shadow_pairs reads what the records say -----------------------------------------

def rec(call_id, model, pair_id, shadow=False, **extra):
    return {"call_id": call_id, "task": "judge", "model": model, "attempt": 0, "final": True,
            "outcome": "ok", "slice": None, "pair_id": pair_id, "shadow": shadow, **extra}


def log_of(*pairs):
    """One routed and one shadow record per pair ID; extras by (pair ID, side)."""
    records = []
    for pair_id, routed, shadow in pairs:
        records += [rec(pair_id, CHEAP, pair_id, **routed),
                    rec(pair_id + "-s", BEST, pair_id, shadow=True, **shadow)]
    return records


YES, NO = {"checked": True}, {"checked": False}


@pytest.mark.parametrize("side", ["routed", "shadow"])
def test_checked_true_refuses_a_pair_whose_record_says_no_check_ran(side):
    bad = (NO, YES) if side == "routed" else (YES, NO)
    log = log_of(("p1", YES, YES), ("p2", *bad), ("p3", YES, YES))
    with pytest.raises(ValueError) as exc:
        shadow_pairs(log, checked=True)
    assert str(exc.value) == (f"pair_id 'p2': its {side} record says checked false: its call ran "
                              f"no acceptance check (validate), so checked=True (--checked) "
                              f"cannot label it; label it by audits or leave it unlabelled")


def test_pairs_are_checked_in_shadow_record_order_the_routed_side_first():  # iter-469 nit 2
    log = log_of(("p1", YES, NO), ("p2", NO, YES))
    with pytest.raises(ValueError, match="^pair_id 'p1': its shadow record says checked false"):
        shadow_pairs(log, checked=True)
    log = log_of(("p1", NO, NO))
    with pytest.raises(ValueError, match="^pair_id 'p1': its routed record says checked false"):
        shadow_pairs(log, checked=True)


def test_v1_610_s_checks_come_first():
    log = log_of(("p1", NO, NO)) + [rec("p2-s", BEST, "p2", shadow=True, checked=True)]
    with pytest.raises(ValueError, match="^pair_id 'p2': its routed call has no final records"):
        shadow_pairs(log, checked=True)


@pytest.mark.parametrize("labels", [{}, {"audits": {"p1": True, "p1-s": False}}],
                         ids=["neither", "audits"])
def test_without_checked_true_a_checked_false_refuses_nothing(labels):
    log = log_of(("p1", NO, NO))
    expected = (True, False) if labels else (None, None)
    pairs = shadow_pairs(log, **labels)
    assert [(p["routed_correct"], p["shadow_correct"]) for p in pairs] == [expected]


def test_a_record_with_no_checked_key_is_taken_on_the_caller_s_word():
    log = log_of(("p1", {}, {}), ("p2", YES, {}), ("p3", {}, YES))
    pairs = shadow_pairs(log, checked=True)
    assert [(p["routed_correct"], p["shadow_correct"]) for p in pairs] == [(True, True)] * 3
    assert [list(p) for p in pairs] == [list(shadow_pairs(log_of(("p1", {}, {})))[0])] * 3


@pytest.mark.parametrize("labels", [{"checked": True}, {}, {"audits": {}}],
                         ids=["checked", "neither", "audits"])
@pytest.mark.parametrize("side", ["routed", "shadow"])
@pytest.mark.parametrize("value", [1, 0, "false", None])
def test_a_checked_that_is_not_a_real_bool_is_refused_whatever_the_labels(value, side, labels):
    bad = ({"checked": value}, YES) if side == "routed" else (YES, {"checked": value})
    with pytest.raises(ValueError) as exc:
        shadow_pairs(log_of(("p1", *bad)), **labels)
    assert str(exc.value) == (f"pair_id 'p1': its {side} record's checked must be true or "
                              f"false, got {value!r}")


def test_a_real_log_of_unchecked_calls_is_refused_by_checked_true_and_audited_as_before():
    monitor = Monitor()
    make(router(shadow_rate=1.0), monitor).call("judge", MESSAGES)
    with pytest.raises(ValueError, match="^pair_id 'call-0': its routed record says checked"):
        shadow_pairs(monitor.records, checked=True)
    assert [(p["routed_correct"], p["shadow_correct"])
            for p in shadow_pairs(monitor.records)] == [(None, None)]
    audited = shadow_pairs(monitor.records, audits={"call-0": True, "call-1": False})
    assert [(p["routed_correct"], p["shadow_correct"]) for p in audited] == [(True, False)]


# --- 10 v1.618: pairs --checked ------------------------------------------------------------------

@pytest.mark.parametrize("existing", [False, True])
def test_pairs_checked_on_a_log_of_unchecked_calls_exits_two_and_writes_nothing(
        tmp_path, capsys, existing):
    log, out = tmp_path / "calls.jsonl", tmp_path / "pairs.jsonl"
    make(router(shadow_rate=1.0), Monitor(log)).call("judge", MESSAGES)
    if existing:
        out.write_text("an older pair file\n", encoding="utf-8")
    code = main(["pairs", "--log", str(log), "--out", str(out), "--checked"])
    captured = capsys.readouterr()
    assert (code, captured.out) == (2, "")
    assert captured.err == ("error: pair_id 'call-0': its routed record says checked false: its "
                            "call ran no acceptance check (validate), so checked=True (--checked) "
                            "cannot label it; label it by audits or leave it unlabelled\n")
    if existing:
        assert out.read_text(encoding="utf-8") == "an older pair file\n"
    else:
        assert not out.exists()
    assert main(["pairs", "--log", str(log), "--out", str(out)]) == 0  # unlabelled, as before
    assert capsys.readouterr().out == f"wrote 1 pairs to {out}: 0 with both sides labelled\n"
    assert len(load_records(out)) == 1
