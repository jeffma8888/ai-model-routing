"""DESIGN 8.3 v1.579 (row RPT2, review iter-425 should-fix 2): `report` counts route entries.

A call counts in `fallback_calls` when its final record belongs to another route entry than its
first record, each record's entry read from the record alone: a record with a `cascade` key is
that cascade's; one with a `procedure` key is `proc:<procedure>@<procedure_version>+<model>` on
a model call's record (one without `model_calls`) and its `model` on the closing record; any
other record is its `model`'s. A call's first record is the latest record with its `call_id` and
`attempt` 0 at or before its final record. So a cascade that handed up, or a procedure that made
model calls, is no fallback call when it was the call's first entry, and a call that moved on
from either, or to either, is one. Every log without `cascade` and `procedure` keys gives
v1.577's rows key for key. The contract tests were written under strict xfail and the
implementing commit removed the marks; the unmarked guards pin what v1.579 keeps and pass before
and after it.
"""
import hashlib
import json

import pytest

from model_routing import (
    Cascade, Completion, Executor, FakeProvider, Model, Monitor, Procedure, ProcedureResult,
    ProviderError, Registry, Router, Stats, Task, load_records, report, run_demo,
)

contract = pytest.mark.xfail(strict=True, reason="DESIGN v1.579 is not implemented yet (RPT2)")

CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
REGISTRY = Registry([
    Model(CHEAP, "fam-a", 1.0, 2.0, 10_000),
    Model(MID, "fam-b", 3.0, 6.0, 10_000),
    Model(BEST, "fam-c", 10.0, 30.0, 100_000),
])
C = Cascade(CHEAP, BEST, "sig")
CID = "fiction/cheap>fiction/best@sig"
TS = "2026-11-22T00:00:00Z"
BY = ("model", "task", "flavor", "family", "tag:team")

# report(...) rows of the demo's calls.jsonl, json.dumps of the list, at fa2551c (v1.578),
# computed in iter 426 before any v1.579 code; the log has no cascade or procedure key
DEMO_CALLS_SHA256 = "4f111326781939140bebe04e0841a66306cac48492bc6c95f4bc2211fa92b351"
DEMO_ROWS_SHA256 = {
    "model": "08cac9ebeae776b44ef2559903f107eaa7a3a99befc43e1f4105fd68b26fe2de",
    "task": "f362c61863f8a84fe7f986e6fd7953cf696d98dcf2848a9cd571a357f8622260",
    "flavor": "97b2e1c32ae25ad7fc19d4b2e1f55a9d81113469db24d87a9f2726de23dca27a",
    "family": "490ebf8a6d849f555b9440301b3895d88f7d59581efbf3411ed30b776a60d84b",
    "tag:delegated": "1e11b068d2f8ce1a4adf277b83f6aab16615725d9a1277ff77303199ca22e5c3",
}


def poll_fn(value, call):
    """Polls in code, then one model call that shapes the result."""
    text = call([{"role": "user", "content": "summarize: " + value[-1]["content"]}])
    return ProcedureResult("shaped " + text, tool_calls=3, tool_cost_usd=0.0005)


def poll_twice(value, call):
    call(value)
    text = call(value)
    return ProcedureResult("shaped " + text, tool_calls=3, tool_cost_usd=0.0005)


def boom(value, call):
    raise RuntimeError("boom")


def proc(fn=poll_fn):
    return Procedure("poll", "v1", fn, max_model_calls=2, max_tool_calls=5, model=CHEAP)


PID = "proc:poll@v1+fiction/cheap"


def cascade_stats():
    """cheap below the 0.8 bar, the cascade and best above it, as tests/test_cascade_executor.py
    plants them: `cost_effective` routes (cascade, best) and `cost_blind` (best, cascade)."""
    stats = Stats()
    stats.add("t", CHEAP, 60, 100, input_tokens=120_000, output_tokens=30_000)
    stats.add("t", BEST, 98, 100)
    stats.add("t", CID, 95, 100, escalated=20)
    return stats


def procedure_stats():
    """best at 98 of 100 and the procedure at 95 of 100, a mean 0.0002 a trial, so it is first."""
    stats = Stats()
    stats.add("t", BEST, 98, 100)
    stats.add("t", PID, 95, 100, cost_usd=0.02)
    return stats


def ok(text, input_tokens, output_tokens):
    return lambda messages: Completion(text, input_tokens, output_tokens)


def fail(message="outage"):
    def script(messages):
        raise ProviderError(message)
    return script


def fail_then(text, input_tokens, output_tokens):
    """A ProviderError on the first call, then a completion on every later one."""
    seen = []

    def script(messages):
        seen.append(messages)
        if len(seen) == 1:
            raise ProviderError("outage")
        return Completion(text, input_tokens, output_tokens)
    return script


class Harness:
    """An executor on task `t` with a scripted provider, a monitor and fixed time."""

    def __init__(self, script, stats):
        task = Task("t", bar=0.8, min_samples=10, cascades=(C,))
        router = Router(REGISTRY, {"t": task}, stats)
        self.monitor = Monitor()
        ticks = iter(0.5 * i for i in range(1000))
        self.executor = Executor(router, FakeProvider(script), monitor=self.monitor,
                                 clock=lambda: next(ticks), now=lambda: TS,
                                 id_factory=lambda: "call-1")

    def call(self, **kw):
        return self.executor.call("t", [{"role": "user", "content": "hi"}],
                                  tags={"team": "a"}, **kw)


def rec(model, attempt, final, outcome="ok", call_id="call-1", **extra):
    """A minimal attempt record: report reads these keys and the extra ones."""
    record = {"call_id": call_id, "task": "t", "flavor": "cost_effective", "model": model,
              "family": "fam", "attempt": attempt, "final": final, "outcome": outcome,
              "latency_ms": 500.0, "input_tokens": 10, "output_tokens": 2, "cost_usd": 0.001,
              "routing_cost_usd": 0.001, "tags": {}}
    record.update(extra)
    return record


def model_call(attempt, model=CHEAP, version="v1", **kw):
    return rec(model, attempt, False, procedure="poll", procedure_version=version, **kw)


def closing(attempt, final, outcome="ok", model=PID, version="v1", name="poll", model_calls=1,
            **kw):
    return rec(model, attempt, final, outcome, procedure=name, procedure_version=version,
               model_calls=model_calls, tool_calls=3, tool_cost_usd=0.0005, **kw)


def strong(attempt, final=True, outcome="ok", **kw):
    return rec(BEST, attempt, final, outcome, cascade=CID, escalated=True, **kw)


def fallbacks(records, by="model"):
    return {row["group"]: (row["calls"], row["fallback_calls"], row["fallback_rate"])
            for row in report(records, by=by)}


def v1_577_fallbacks(records, by="model"):
    """v1.577's count by hand: a final record whose attempt index is above 0."""
    rows = report(records, by=by)
    finals = [r for r in records if r.get("final")]
    count = {row["group"]: 0 for row in rows}
    for r in finals:
        group = {"model": r["model"], "task": r["task"]}[by]
        count[group] += int(r.get("attempt", 0)) > 0
    return count


# --- guards: without cascade and procedure keys every row is v1.577's ------------------------

@pytest.fixture(scope="module")
def demo_records(tmp_path_factory):
    out = tmp_path_factory.mktemp("rpt2") / "demo"
    run_demo(out)
    assert hashlib.sha256((out / "calls.jsonl").read_bytes()).hexdigest() == DEMO_CALLS_SHA256
    return load_records(out / "calls.jsonl")


@pytest.mark.parametrize("by", sorted(DEMO_ROWS_SHA256))
def test_guard_the_demo_log_gives_v1_578_rows_key_for_key(demo_records, by):
    rows = report(demo_records, by=by)
    assert hashlib.sha256(json.dumps(rows).encode()).hexdigest() == DEMO_ROWS_SHA256[by]
    assert sum(row["fallback_calls"] for row in rows) == 55


def test_guard_a_plain_final_above_attempt_0_is_a_fallback_whatever_its_first_record():
    # a plain entry writes one record, so its final record above attempt 0 follows another
    # entry's record, even one naming the same model, or none in the log at all
    records = [rec(MID, 0, False, "error"), rec(MID, 1, True),
               rec(BEST, 2, True, call_id="call-2"),
               rec(CHEAP, 0, True, call_id="call-3"),
               rec(BEST, 1, True, call_id=None)]
    assert fallbacks(records) == {MID: (1, 1, 1.0), BEST: (2, 2, 1.0), CHEAP: (1, 0, 0.0)}
    assert {g: f for g, (_, f, _) in fallbacks(records).items()} == v1_577_fallbacks(records)


def test_guard_a_cascade_or_procedure_final_with_no_first_record_before_it_counts_as_v1_577():
    records = [strong(1, call_id="call-1"),
               closing(1, True, call_id="call-2"),
               model_call(0, call_id="call-2")]   # after its final record, so not its first
    assert fallbacks(records) == {BEST: (1, 1, 1.0), PID: (1, 1, 1.0), CHEAP: (0, 0, 0.0)}


def test_guard_a_first_entry_at_attempt_0_is_no_fallback_as_before():
    records = [rec(CHEAP, 0, True, cascade=CID, escalated=False),
               closing(0, True, model="proc:shape@v2", version="v2", name="shape",
                       model_calls=0, call_id="call-2")]
    assert fallbacks(records) == {CHEAP: (1, 0, 0.0), "proc:shape@v2": (1, 0, 0.0)}


# --- end to end: the executor's records (7 v1.537, 8.1 v1.578) --------------------------------

@contract
@pytest.mark.parametrize("cheap", [ok("cheap answer", 40, 9), fail()], ids=["signal", "error"])
def test_a_cascade_that_hands_up_as_the_first_entry_is_no_fallback_call(cheap):
    h = Harness({CHEAP: cheap, BEST: ok("strong answer", 55, 12)}, cascade_stats())
    result = h.call(signals={"sig": lambda text: True})
    assert result.model == BEST
    assert [(r["model"], r["attempt"], r["final"], r["cascade"]) for r in h.monitor.records] == [
        (CHEAP, 0, False, CID), (BEST, 1, True, CID)]
    for by in BY:
        rows = report(h.monitor.records, by=by)
        assert sum(row["calls"] for row in rows) == 1, by
        assert [(row["fallback_calls"], row["fallback_rate"]) for row in rows
                if row["calls"]] == [(0, 0.0)], by


@contract
def test_a_procedure_primary_that_made_model_calls_is_no_fallback_call():
    h = Harness({CHEAP: ok("cheap answer", 4000, 1000)}, procedure_stats())
    result = h.call(procedures=[proc(poll_twice)])
    assert result.model == PID
    assert [(r["model"], r["attempt"], r["final"]) for r in h.monitor.records] == [
        (CHEAP, 0, False), (CHEAP, 1, False), (PID, 2, True)]
    assert fallbacks(h.monitor.records) == {PID: (1, 0, 0.0), CHEAP: (0, 0, 0.0)}
    for by in BY:
        rows = report(h.monitor.records, by=by)
        assert [(row["fallback_calls"], row["fallback_rate"]) for row in rows
                if row["calls"]] == [(0, 0.0)], by


def test_a_fallback_onto_a_cascade_that_hands_up_is_a_fallback_call():
    # cost_blind routes (best, cascade): best fails, the cascade's cheap model hands up
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: fail_then("strong answer", 55, 12)},
                cascade_stats())
    result = h.call(flavor="cost_blind", signals={"sig": lambda text: True})
    assert (result.decision.primary, result.model) == (BEST, BEST)
    assert [(r["model"], r["attempt"], r.get("cascade")) for r in h.monitor.records] == [
        (BEST, 0, None), (CHEAP, 1, CID), (BEST, 2, CID)]
    assert fallbacks(h.monitor.records) == {BEST: (1, 1, 1.0), CHEAP: (0, 0, 0.0)}


def test_a_fallback_after_a_cascade_or_a_procedure_is_a_fallback_call():
    h = Harness({CHEAP: ok("cheap answer", 40, 9), BEST: ok("strong answer", 55, 12)},
                cascade_stats())
    h.call(signals={"sig": lambda text: False}, validate=lambda text: text == "strong answer")
    assert [(r["model"], r["attempt"], r.get("cascade")) for r in h.monitor.records] == [
        (CHEAP, 0, CID), (BEST, 1, None)]
    assert fallbacks(h.monitor.records) == {BEST: (1, 1, 1.0), CHEAP: (0, 0, 0.0)}
    h = Harness({CHEAP: ok("cheap answer", 4000, 1000), BEST: ok("strong answer", 55, 12)},
                procedure_stats())
    h.call(procedures=[proc(boom)])
    assert [(r["model"], r["attempt"]) for r in h.monitor.records] == [(PID, 0), (BEST, 1)]
    assert fallbacks(h.monitor.records) == {BEST: (1, 1, 1.0), PID: (0, 0, 0.0)}
    h = Harness({CHEAP: ok("cheap answer", 4000, 1000), BEST: ok("strong answer", 55, 12)},
                procedure_stats())
    h.call(procedures=[proc()], validate=lambda text: text == "strong answer")
    assert [(r["model"], r["attempt"]) for r in h.monitor.records] == [
        (CHEAP, 0), (PID, 1), (BEST, 2)]
    assert fallbacks(h.monitor.records) == {BEST: (1, 1, 1.0), PID: (0, 0, 0.0),
                                            CHEAP: (0, 0, 0.0)}


# --- the entry of each record, read from the record alone (8.3 v1.579) ------------------------

@contract
def test_a_model_call_record_belongs_to_proc_name_at_version_plus_its_model():
    # the closing record's model is the procedure's .id; any other closing model is another entry
    assert fallbacks([model_call(0), closing(1, True)]) == {CHEAP: (0, 0, 0.0), PID: (1, 0, 0.0)}
    other = "proc:poll@v1"
    assert fallbacks([model_call(0), closing(1, True, model=other)]) == {
        CHEAP: (0, 0, 0.0), other: (1, 1, 1.0)}
    # another version, or another model, of the same procedure name is another entry
    assert fallbacks([model_call(0, version="v2"), closing(1, True)])[PID] == (1, 1, 1.0)
    assert fallbacks([model_call(0, model=MID), closing(1, True)])[PID] == (1, 1, 1.0)


@contract
def test_a_procedure_after_a_failed_procedure_is_a_fallback_and_its_own_calls_are_not():
    v2 = "proc:poll@v2+fiction/cheap"
    records = [model_call(0), closing(1, False, "invalid"),
               model_call(2, version="v2"), closing(3, True, model=v2, version="v2"),
               model_call(0, call_id="call-2"), model_call(1, call_id="call-2"),
               closing(2, True, call_id="call-2")]
    assert fallbacks(records) == {PID: (1, 0, 0.0), v2: (1, 1, 1.0), CHEAP: (0, 0, 0.0)}


@contract
def test_a_cascade_record_belongs_to_its_cascade_key_whatever_its_model():
    other = "fiction/mid>fiction/best@sig"
    records = [rec(CHEAP, 0, False, cascade=CID, escalated=True), strong(1),
               rec(MID, 0, False, cascade=other, escalated=True, call_id="call-2"),
               strong(1, call_id="call-2")]
    assert fallbacks(records) == {BEST: (2, 1, 0.5), CHEAP: (0, 0, 0.0), MID: (0, 0, 0.0)}


# --- a call's first record: the latest at attempt 0 with its call_id before its final -------

@contract
def test_interleaved_calls_are_matched_by_call_id():
    records = [rec(CHEAP, 0, False, cascade=CID, escalated=True),
               rec(MID, 0, False, "error", call_id="call-2"),
               rec(BEST, 1, True, call_id="call-2"),
               strong(1)]
    assert fallbacks(records) == {BEST: (2, 1, 0.5), CHEAP: (0, 0, 0.0), MID: (0, 0, 0.0)}


@contract
def test_logs_appended_one_after_another_keep_a_reused_call_id_apart():
    first_log = [rec(MID, 0, True)]
    second_log = [rec(CHEAP, 0, False, cascade=CID, escalated=True), strong(1)]
    assert fallbacks(first_log + second_log) == {
        MID: (1, 0, 0.0), CHEAP: (0, 0, 0.0), BEST: (1, 0, 0.0)}
    # the other way round: the cascade's first record is still its own, the plain call's too
    assert fallbacks(second_log + first_log) == {
        MID: (1, 0, 0.0), CHEAP: (0, 0, 0.0), BEST: (1, 0, 0.0)}


@contract
def test_the_rule_holds_under_every_report_key_and_with_audits():
    records = [rec(CHEAP, 0, False, cascade=CID, escalated=True, tags={"team": "a"}),
               strong(1, tags={"team": "a"})]
    for by in BY:
        (row,) = [r for r in report(records, by=by) if r["calls"]]
        assert (row["fallback_calls"], row["fallback_rate"]) == (0, 0.0), by
    (row,) = [r for r in report(records, audits={"call-1": True}) if r["calls"]]
    assert (row["fallback_calls"], row["correct_calls"], row["cost_per_success_usd"]) == (
        0, 1, 0.002)
