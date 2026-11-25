"""The labeled results rows of a monitor log's audited calls: `audited_results` (DESIGN 8.3
v1.632, row M1a, the first part of row M1's drift check).

An audited call's final `ok` answer is labelled by its audit and each `invalid` answer `false`,
an `error` gives no row, and `since` and `until` keep the calls whose final record's `ts` is in
`[since, until)`, so `calibrate_from_results` keeps a recent window's stats apart from the
all-time file. A call of a cascade or a procedure gives no row at v1.632 (row M1d)."""

import copy
from pathlib import Path

import pytest

import model_routing
from model_routing import (
    AllModelsFailed, Completion, Executor, FakeProvider, Model, Monitor, ProviderError, Registry,
    Router, Stats, Task, report,
)
from model_routing.stats import calibrate_from_results, item_outcomes

ROOT = Path(__file__).resolve().parents[1]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
OLD, NEW = "2026-10-01T00:00:00.000+00:00", "2026-11-20T00:00:00.000+00:00"


def audited(*args, **kwargs):
    return model_routing.audited_results(*args, **kwargs)


def rec(call_id, model, outcome, final=True, attempt=0, ts=NEW, task="judge", slice=None,
        **extra):
    out = {"ts": ts, "call_id": call_id, "task": task, "flavor": "cost_effective",
           "model": model, "family": model.split("/")[0], "attempt": attempt, "final": final,
           "outcome": outcome, "error": None, "latency_ms": 5.0, "input_tokens": 1000,
           "output_tokens": 200, "cost_usd": 0.001, "routing_cost_usd": 0.001,
           "below_bar": False, "basis": "measured", "tags": {}, "slice": slice}
    out.update(extra)
    return out


def row(model, item, correct, slice=None, tokens=(1000, 200)):
    out = {"task": "judge", "model": model, "item": item, "correct": correct}
    if tokens is not None:
        out.update(input_tokens=tokens[0], output_tokens=tokens[1])
    return out if slice is None else {**out, "slice": slice}


LOG = [
    rec("c0", CHEAP, "invalid", final=False),                 # rejected, then a fallback answers
    rec("c0", MID, "ok", attempt=1),
    rec("c1", CHEAP, "ok"),
    rec("c2", CHEAP, "error", final=False, input_tokens=0, output_tokens=0),
    rec("c2", MID, "ok", attempt=1),
    rec("c3", CHEAP, "error", final=False, input_tokens=0, output_tokens=0),
    rec("c3", MID, "error", attempt=1, input_tokens=0, output_tokens=0),
    rec("c4", CHEAP, "ok"),                                   # not audited
    rec("c5", CHEAP, "ok", slice="long"),
    rec("c6", CHEAP, "invalid"),                              # the check beats the audit
    rec("c0-s", BEST, "ok", shadow=True, pair_id="c0"),       # a shadow call: one of its own
    {"ts": NEW, "call_id": "c7", "task": "judge", "tags": {}, "budget_event": "refused",
     "budget": "daily", "mode": "refuse", "window": "2026-11-20"},  # its hold refused: no attempt
]
AUDITS = {"c0": True, "c1": False, "c2": True, "c3": False, "c5": True, "c6": True,
          "c0-s": False, "c7": True, "elsewhere": True}
EXPECTED = [row(CHEAP, "c0", False), row(MID, "c0", True), row(CHEAP, "c1", False),
            row(MID, "c2", True), row(CHEAP, "c5", True, "long"), row(CHEAP, "c6", False),
            row(BEST, "c0-s", False)]


# --- rows -------------------------------------------------------------------------------

def test_each_answer_of_an_audited_call_gives_one_row_in_log_order():
    assert audited(LOG, AUDITS) == EXPECTED


def test_a_row_has_its_keys_in_order_and_slice_last_only_on_a_sliced_call():
    keys = ["task", "model", "item", "correct", "input_tokens", "output_tokens"]
    assert [list(r) for r in audited(LOG, AUDITS)] == [keys] * 4 + [keys + ["slice"]] + [keys] * 2


def test_an_error_gives_no_row_and_a_call_with_no_answer_gives_none():
    rows = audited(LOG, AUDITS)
    assert [r for r in rows if r["item"] == "c2"] == [row(MID, "c2", True)]
    assert [r for r in rows if r["item"] in ("c3", "c4", "c7", "elsewhere")] == []


def test_rows_come_in_the_order_of_each_calls_first_record():
    log = [rec("a", CHEAP, "invalid", final=False), rec("b", CHEAP, "ok"),
           rec("a", MID, "ok", attempt=1)]
    assert audited(log, {"a": True, "b": True}) == [row(CHEAP, "a", False), row(MID, "a", True),
                                                   row(CHEAP, "b", True)]


def test_token_counts_are_copied_only_when_both_are_counts():
    log = [rec("a", CHEAP, "ok"), rec("b", CHEAP, "ok", input_tokens=True),
           {k: v for k, v in rec("c", CHEAP, "ok").items() if k != "output_tokens"},
           rec("d", CHEAP, "ok", input_tokens=-1), rec("e", CHEAP, "ok", output_tokens=2.0),
           rec("f", CHEAP, "ok", input_tokens=0, output_tokens=0)]
    rows = audited(log, dict.fromkeys("abcdef", True))
    assert rows == [row(CHEAP, "a", True)] + [row(CHEAP, x, True, tokens=None) for x in "bcde"] \
        + [row(CHEAP, "f", True, tokens=(0, 0))]


def test_nothing_else_of_a_record_is_copied():
    log = [rec("a", CHEAP, "ok", cached_input_tokens=800, cascade_note="x", latency_ms=99.0)]
    assert audited(log, {"a": True}) == [row(CHEAP, "a", True)]


def test_no_records_or_no_audits_give_no_rows_and_a_generator_is_read():
    assert audited([], AUDITS) == []
    assert audited(LOG, {}) == []
    assert audited((r for r in LOG), AUDITS) == EXPECTED


def test_records_and_audits_are_left_unchanged():
    log, audits = copy.deepcopy(LOG), dict(AUDITS)
    audited(log, audits, since=OLD)
    assert log == LOG and audits == AUDITS


def test_a_cascade_or_procedure_call_gives_no_row_yet():
    cascade = [rec("k", CHEAP, "ok", final=False, cascade="cascade:x", escalated=True),
               rec("k", MID, "ok", attempt=1, cascade="cascade:x", escalated=True)]
    procedure = [rec("p", CHEAP, "ok", final=False, procedure="triage", procedure_version="1"),
                 rec("p", "proc:triage@1", "ok", attempt=1, procedure="triage",
                     procedure_version="1", model_calls=1, tool_calls=0)]
    assert audited(cascade + procedure + LOG, {**AUDITS, "k": True, "p": True}) == EXPECTED


# --- what reads the rows ----------------------------------------------------------------

def test_calibrate_reads_one_trial_per_row_with_its_tokens():
    stats = calibrate_from_results(audited(LOG, AUDITS))
    assert stats.get("judge", CHEAP) == (1, 4)
    assert stats.get("judge", MID) == (2, 2)
    assert stats.get("judge", BEST) == (0, 1)
    assert stats.get("judge@long", CHEAP) == (1, 1)
    assert stats.tokens("judge", CHEAP) == (4000, 800, 4)


def test_item_outcomes_read_the_rows_with_the_call_id_as_the_item():
    records = item_outcomes(audited(LOG, AUDITS), dataset_sha256="0" * 64)
    assert [(r["route"], r["item"], r["correct"]) for r in records][:2] == [
        (CHEAP, "c0", False), (MID, "c0", True)]


def test_a_true_final_row_is_a_call_reports_correct_calls_count():
    rows = audited(LOG, AUDITS)
    for group in report(LOG, by="model", audits=AUDITS):
        assert group["correct_calls"] == sum(r["correct"] for r in rows if r["model"] == group["group"])


# --- the window -------------------------------------------------------------------------

WINDOWED = [rec("o", CHEAP, "ok", ts=OLD), rec("n", CHEAP, "invalid", final=False, ts=OLD),
            rec("n", MID, "ok", attempt=1, ts=NEW), rec("z", CHEAP, "ok", ts="2026-11-20T08:00:00Z"),
            rec("naive", CHEAP, "ok", ts="2026-11-21T00:00:00")]
W_AUDITS = dict.fromkeys(["o", "n", "z", "naive"], True)


def items(rows):
    return [(r["model"], r["item"]) for r in rows]


def test_a_call_is_kept_by_its_final_records_time():
    assert items(audited(WINDOWED, W_AUDITS, since="2026-11-01T00:00:00Z")) == [
        (CHEAP, "n"), (MID, "n"), (CHEAP, "z"), (CHEAP, "naive")]
    assert items(audited(WINDOWED, W_AUDITS, until="2026-11-01T00:00:00Z")) == [(CHEAP, "o")]


def test_since_is_inclusive_and_until_exclusive_so_two_windows_share_no_call():
    first = audited(WINDOWED, W_AUDITS, since=OLD, until=NEW)
    second = audited(WINDOWED, W_AUDITS, since=NEW, until="2026-12-01T00:00:00Z")
    assert items(first) == [(CHEAP, "o")]
    assert items(second) == [(CHEAP, "n"), (MID, "n"), (CHEAP, "z"), (CHEAP, "naive")]


def test_offsets_are_read_as_instants_and_no_offset_reads_as_utc():
    assert items(audited(WINDOWED, W_AUDITS, since="2026-11-20T00:00:01-08:00")) == [(CHEAP, "naive")]
    assert items(audited(WINDOWED, W_AUDITS, since="2026-11-20T08:00:00",
                         until="2026-11-20T08:00:00.001+00:00")) == [(CHEAP, "z")]


def test_with_no_bound_no_ts_is_read():
    log = [rec("a", CHEAP, "ok", ts=None), rec("b", CHEAP, "ok", ts="yesterday")]
    assert items(audited(log, {"a": True, "b": True})) == [(CHEAP, "a"), (CHEAP, "b")]


def admitting_router(stats):
    task = Task("judge", bar=0.8, min_samples=30)
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000)])
    return Router(registry, {"judge": task}, stats)


def test_a_route_at_0_92_all_time_and_0_70_in_the_window_loses_admission_in_the_window():
    log, audits = [], {}
    for i in range(500):   # 460 of 500 right all-time, 28 of the last 40 in November
        recent = i >= 460
        call_id = f"cheap-{i}"
        log.append(rec(call_id, CHEAP, "ok", ts=NEW if recent else OLD))
        audits[call_id] = (i - 460 < 28) if recent else (i < 432)
    for i in range(40):
        log.append(rec(f"mid-{i}", MID, "ok", ts=NEW))
        audits[f"mid-{i}"] = True
    all_time = calibrate_from_results(audited(log, audits))
    window = calibrate_from_results(audited(log, audits, since="2026-11-01T00:00:00Z"))
    assert all_time.get("judge", CHEAP) == (460, 500) and window.get("judge", CHEAP) == (28, 40)
    assert window.get("judge", MID) == (40, 40)
    assert admitting_router(all_time).select("judge").primary == CHEAP
    decision = admitting_router(window).select("judge")
    assert decision.primary == MID
    [cheap] = [c for c in decision.candidates if c.model_id == CHEAP]
    assert cheap.reason == "below_bar" and cheap.quality_lb < 0.8


# --- a real executor log ----------------------------------------------------------------

def answers(*texts):
    queue = list(texts)

    def complete(messages):
        if not queue:
            raise ProviderError("outage")
        return Completion(queue.pop(0), 1000, 200)
    return complete


def test_the_rows_of_a_real_executor_log():
    task = Task("judge", bar=0.7, min_samples=10)
    stats = Stats()
    for model_id in (CHEAP, MID, BEST):
        stats.add("judge", model_id, 100, 100)
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000),
                         Model(BEST, "large", 10.0, 20.0, 8000)])
    monitor = Monitor()
    ids = iter(f"call-{i}" for i in range(100))
    stamps = iter([OLD] * 2 + [NEW] * 100)
    script = {CHEAP: answers("bad", "fine"), MID: answers("good")}
    executor = Executor(Router(registry, {"judge": task}, stats), FakeProvider(script),
                        monitor=monitor, now=lambda: next(stamps), id_factory=lambda: next(ids))
    for _ in range(3):
        try:
            executor.call("judge", [{"role": "user", "content": "q"}],
                          validate=lambda text: text != "bad")
        except AllModelsFailed:
            pass
    records = monitor.records
    assert [(r["call_id"], r["model"], r["outcome"]) for r in records] == [
        ("call-0", CHEAP, "invalid"), ("call-0", MID, "ok"), ("call-1", CHEAP, "ok"),
        ("call-2", CHEAP, "error"), ("call-2", MID, "error"), ("call-2", BEST, "error")]
    audits = {"call-0": True, "call-1": True, "call-2": False}
    assert audited(records, audits) == [row(CHEAP, "call-0", False), row(MID, "call-0", True),
                                        row(CHEAP, "call-1", True)]
    assert audited(records, audits, since=NEW) == [row(CHEAP, "call-1", True)]


# --- checks -----------------------------------------------------------------------------

@pytest.mark.parametrize("log, audits, kwargs, message", [
    (LOG + ["not a record"], AUDITS, {}, f"record {len(LOG) + 1} must be a mapping"),
    (LOG, [("c0", True)], {}, "audits must be a mapping of call ID to true or false"),
    (LOG, {"c0": 1}, {}, "audits must be a mapping of call ID to true or false"),
    (LOG, {"": True}, {}, "audits must be a mapping of call ID to true or false"),
    (LOG, {3: True}, {}, "audits must be a mapping of call ID to true or false"),
    (LOG, AUDITS, {"since": "last week"}, "since must be None or an ISO 8601 timestamp"),
    (LOG, AUDITS, {"until": 20261120}, "until must be None or an ISO 8601 timestamp"),
    (LOG, AUDITS, {"since": NEW, "until": NEW}, "since must be before until"),
    (LOG, AUDITS, {"since": NEW, "until": OLD}, "since must be before until"),
    ([rec("a", CHEAP, "ok", final=False)], {"a": True}, {}, "call_id 'a' has no final record"),
    ([rec("a", CHEAP, "ok", final=1)], {"a": True}, {}, "call_id 'a' has no final record"),
    ([rec("a", CHEAP, "ok"), rec("a", MID, "ok")], {"a": True}, {},
     "call_id 'a' has more than one final record"),
    ([rec("a", CHEAP, "ok", ts="soon")], {"a": True}, {"since": OLD},
     "call_id 'a': ts 'soon' is no ISO 8601 timestamp"),
    ([rec("a", CHEAP, "ok", ts=None)], {"a": True}, {"until": NEW},
     "call_id 'a': ts None is no ISO 8601 timestamp"),
    ([rec("a", CHEAP, "ok", task="")], {"a": True}, {}, "call_id 'a': task must be a non-empty string"),
    ([rec("a", CHEAP, "invalid", final=False, task=None), rec("a", MID, "ok", attempt=1)],
     {"a": True}, {}, "call_id 'a': task must be a non-empty string"),
    ([{**rec("a", CHEAP, "ok"), "model": 7}], {"a": True}, {},
     "call_id 'a': model must be a non-empty string"),
    ([rec("a", CHEAP, "ok", slice="a@b")], {"a": True}, {},
     "call_id 'a': slice must be null or a non-empty string without '@'"),
    ([rec("a", CHEAP, "ok", slice="")], {"a": True}, {},
     "call_id 'a': slice must be null or a non-empty string without '@'"),
    ([rec("a", CHEAP, "ok", task="t@s", slice="long")], {"a": True}, {},
     "call_id 'a': a sliced call's task must hold no '@', got 't@s'"),
])
def test_a_bad_input_raises(log, audits, kwargs, message):
    with pytest.raises(ValueError) as exc:
        audited(log, audits, **kwargs)
    assert message in str(exc.value)


def test_every_audited_call_is_checked_whatever_the_window():
    log = [rec("a", CHEAP, "ok", ts=OLD, task=""), rec("b", CHEAP, "ok", ts=NEW)]
    with pytest.raises(ValueError, match="call_id 'a': task must be a non-empty string"):
        audited(log, {"a": True, "b": True}, since=NEW)


def test_a_record_that_gives_no_row_is_not_checked_for_its_fields():
    log = [{**rec("a", CHEAP, "error", final=False), "task": None, "model": None},
           rec("a", MID, "ok", attempt=1)]
    assert audited(log, {"a": True}) == [row(MID, "a", True)]


def test_an_unaudited_call_is_never_checked():
    log = [rec("a", CHEAP, "ok", final=False), rec("b", CHEAP, "ok", task="")] + LOG
    assert audited(log, AUDITS) == EXPECTED


# --- the API and the spec ---------------------------------------------------------------

def test_audited_results_is_exported_after_pair_results():
    names = model_routing.__all__
    assert names[names.index("pair_results") + 1] == "audited_results"
    assert model_routing.audited_results is model_routing.monitor.audited_results


def test_design_and_changelog_state_v1_632():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    section = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert section.count("- v1.632 `audited_results(records, audits, *, since=None, until=None) "
                         "-> list[dict]` (row M1a)") == 1
    assert "pair_results (v1.613), audited_results (v1.632)\n" in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.632 (2026-11-24): spec, code and tests (3, 8.3, row M1a).") == 1
