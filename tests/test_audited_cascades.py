"""A cascade's and a procedure's audited calls give their rows: `audited_results` (DESIGN 8.3
v1.636, row M1d, the last code part of row M1's drift check).

At v1.632 a call with a cascade's or a procedure's record gave no row. Now the entry's answer
gives one row of the entry's route, as `pair_results` (v1.621) gives a routed side: a cascade's
with `escalated` and no token counts, a procedure's with `cost_usd`, the `math.fsum` of its
entry's records. A handed-up cheap leg and a procedure's model calls give no row, and a call of
plain routes keeps its v1.632 rows. From v1.637 (row LAT2) each row carries its entry's
`latency_ms` before `slice`, tests/test_audited_latency.py: these records take 5.0 ms each, and the
executor's clock stands still, so its attempts take 0.0."""

import copy
import math
from pathlib import Path

import pytest

import model_routing
from model_routing import (
    Cascade, Completion, Executor, FakeProvider, Model, Monitor, Procedure, ProcedureResult,
    ProviderError, Registry, Router, Stats, Task, drift_check,
)
from model_routing.stats import calibrate_from_results, item_outcomes

ROOT = Path(__file__).resolve().parents[1]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
REGISTRY = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000),
                     Model(BEST, "large", 10.0, 20.0, 8000)])
CASCADE = Cascade(CHEAP, MID, "sig")            # fiction/cheap>fiction/mid@sig
C = CASCADE.id
OLD, NEW = "2026-10-01T00:00:00.000+00:00", "2026-11-20T00:00:00.000+00:00"
MESSAGES = [{"role": "user", "content": "q"}]


def polling(value, call):
    text = call([{"role": "user", "content": "summarize"}])
    return ProcedureResult("shaped " + text, tool_calls=3, tool_cost_usd=0.0005)


POLLING = Procedure("poll", "v1", polling, max_model_calls=2, max_tool_calls=5, model=CHEAP)
P = POLLING.id                                  # proc:poll@v1+fiction/cheap


def audited(*args, **kwargs):
    return model_routing.audited_results(*args, **kwargs)


def answers(*texts):
    queue = list(texts)

    def complete(messages):
        if not queue:
            raise ProviderError("outage")
        return Completion(queue.pop(0), 1000, 200)
    return complete


def executor(entry_id, script, **counts):
    """The entry at 100/100 is the primary, mid then best its fallbacks; cheap's 50/100 is under
    the 0.7 bar, so cheap is no route of its own."""
    stats = Stats()
    for model_id, successes in ((CHEAP, 50), (MID, 95), (BEST, 98)):
        stats.add("judge", model_id, successes, 100)
    stats.add("judge", entry_id, 100, 100, **counts)
    task = Task("judge", bar=0.7, min_samples=10, cascades=(CASCADE,))
    monitor = Monitor()
    ids = iter(f"call-{i}" for i in range(100))
    run = Executor(Router(REGISTRY, {"judge": task}, stats), FakeProvider(script), monitor=monitor,
                   now=lambda: NEW, id_factory=lambda: next(ids), clock=lambda: 0.0)
    return run, monitor


def cascade_log():
    """call-0 keeps the cheap answer; call-1 hands up; call-2's cheap answer is rejected and mid
    answers as the fallback; call-3 hands up, the strong answer is rejected and mid answers as
    the fallback; call-4's cheap leg fails, so it hands up."""
    run, monitor = executor(C, {CHEAP: answers("c0", "hand1", "bad", "hand3"),
                                MID: answers("m1", "m2", "bad", "m3", "m4"), BEST: answers()},
                            escalated=20)
    for _ in range(5):
        run.call("judge", MESSAGES, signals={"sig": lambda text: text.startswith("hand")},
                 validate=lambda text: text != "bad")
    return monitor.records


def procedure_log():
    """call-0's run is accepted; call-1's output is rejected and mid answers as the fallback;
    call-2's model call fails, so its run fails and mid answers."""
    run, monitor = executor(P, {CHEAP: answers("ok0", "bad"), MID: answers("m1", "m2"),
                                BEST: answers()}, cost_usd=0.02)
    for _ in range(3):
        run.call("judge", MESSAGES, procedures=[POLLING], validate=lambda text: "bad" not in text)
    return monitor.records


def entry(model, item, correct, latency=0.0, slice=None, **extra):
    out = {"task": "judge", "model": model, "item": item, "correct": correct, **extra,
           "latency_ms": latency}                 # DESIGN 8.3 v1.637
    return out if slice is None else {**out, "slice": slice}


def plain(model, item, correct, latency=0.0):
    return entry(model, item, correct, latency, input_tokens=1000, output_tokens=200)


def rec(call_id, model, outcome, final=True, attempt=0, ts=NEW, **extra):
    out = {"ts": ts, "call_id": call_id, "task": "judge", "flavor": "cost_effective",
           "model": model, "family": "fiction", "attempt": attempt, "final": final,
           "outcome": outcome, "error": None, "latency_ms": 5.0, "input_tokens": 1000,
           "output_tokens": 200, "cost_usd": 0.001, "routing_cost_usd": 0.001,
           "below_bar": False, "basis": "measured", "tags": {}, "slice": None}
    out.update(extra)
    return out


def leg(call_id, model, outcome, escalated, **kwargs):
    return rec(call_id, model, outcome, cascade=C, escalated=escalated, **kwargs)


def call_of(call_id, model, outcome, final=False, **kwargs):   # a model call of POLLING's run
    return rec(call_id, model, outcome, final=final, procedure="poll", procedure_version="v1",
               **kwargs)


def closing(call_id, outcome, final=True, attempt=1, model_calls=1, model=P, **kwargs):
    fields = dict(procedure="poll", procedure_version="v1", model_calls=model_calls,
                  tool_calls=3, tool_cost_usd=0.0005, input_tokens=0, output_tokens=0,
                  cost_usd=0.0005)
    fields.update(kwargs)
    return rec(call_id, model, outcome, final=final, attempt=attempt, **fields)


# --- a cascade's rows --------------------------------------------------------------------------

def test_a_cascade_entry_gives_one_row_with_escalated_and_no_tokens():
    records = cascade_log()
    assert [(r["call_id"], r["model"], r["outcome"], r.get("escalated"), r["final"])
            for r in records] == [
        ("call-0", CHEAP, "ok", False, True),
        ("call-1", CHEAP, "ok", True, False), ("call-1", MID, "ok", True, True),
        ("call-2", CHEAP, "invalid", False, False), ("call-2", MID, "ok", None, True),
        ("call-3", CHEAP, "ok", True, False), ("call-3", MID, "invalid", True, False),
        ("call-3", MID, "ok", None, True),
        ("call-4", CHEAP, "error", True, False), ("call-4", MID, "ok", True, True)]
    audits = {f"call-{i}": i != 1 for i in range(5)}
    rows = audited(records, audits)
    assert rows == [
        entry(C, "call-0", True, escalated=False),
        entry(C, "call-1", False, escalated=True),
        entry(C, "call-2", False, escalated=False), plain(MID, "call-2", True),
        entry(C, "call-3", False, escalated=True), plain(MID, "call-3", True),
        entry(C, "call-4", True, escalated=True)]
    assert list(rows[0]) == ["task", "model", "item", "correct", "escalated", "latency_ms"]


def test_calibrate_reads_a_cascade_row_as_one_trial_with_its_escalation():
    rows = audited(cascade_log(), {f"call-{i}": i != 1 for i in range(5)})
    stats = calibrate_from_results(rows)
    assert stats.get("judge", C) == (2, 5) and stats.escalations("judge", C) == 3
    assert stats.get("judge", MID) == (2, 2) and stats.get("judge", CHEAP) == (0, 0)
    assert [o["route"] for o in item_outcomes(rows, dataset_sha256="0" * 64)][:3] == [C, C, C]


def test_a_sliced_cascade_row_keeps_slice_last():
    log = [leg("a", CHEAP, "ok", False, slice="long")]
    [row] = audited(log, {"a": True})
    assert row == entry(C, "a", True, 5.0, escalated=False, slice="long")
    assert list(row)[-1] == "slice"
    assert calibrate_from_results([row]).get("judge@long", C) == (1, 1)


def test_a_handed_up_leg_that_failed_gives_no_row_and_is_not_checked():
    log = [leg("a", CHEAP, "ok", True, final=False),
           {**leg("a", MID, "error", None, final=False, attempt=1), "task": None},
           rec("a", BEST, "ok", attempt=2)]
    assert audited(log, {"a": True}) == [plain(BEST, "a", True, 5.0)]


# --- a procedure's rows ------------------------------------------------------------------------

def test_a_procedure_entry_gives_one_row_at_its_model_calls_plus_its_tool_cost():
    records = procedure_log()
    assert [(r["call_id"], r["model"], r["outcome"], r.get("model_calls"), r["final"])
            for r in records] == [
        ("call-0", CHEAP, "ok", None, False), ("call-0", P, "ok", 1, True),
        ("call-1", CHEAP, "ok", None, False), ("call-1", P, "invalid", 1, False),
        ("call-1", MID, "ok", None, True),
        ("call-2", CHEAP, "error", None, False), ("call-2", P, "error", 1, False),
        ("call-2", MID, "ok", None, True)]
    rows = audited(records, {"call-0": True, "call-1": True, "call-2": False})
    whole = math.fsum([0.0014, 0.0005])         # 1000 in and 200 out at 1 and 2 a 1M, its tools
    assert [r["cost_usd"] for r in records[:2]] == [0.0014, 0.0005]
    assert rows == [entry(P, "call-0", True, cost_usd=whole),
                    entry(P, "call-1", False, cost_usd=whole), plain(MID, "call-1", True),
                    plain(MID, "call-2", False)]
    assert list(rows[0]) == ["task", "model", "item", "correct", "cost_usd", "latency_ms"]
    stats = calibrate_from_results(rows)
    assert stats.get("judge", P) == (1, 2) and stats.cost("judge", P) == 2 * whole   # summed
    assert stats.get("judge", CHEAP) == (0, 0)


def test_a_model_call_of_a_procedure_gives_no_row_whatever_its_outcome():
    log = [call_of("a", CHEAP, "invalid"), closing("a", "ok")]
    assert audited(log, {"a": False}) == [
        entry(P, "a", False, 5.0, cost_usd=math.fsum([0.001, 0.0005]))]


def test_a_procedure_with_no_model_sums_its_closing_record_alone():
    log = [closing("a", "ok", attempt=0, model_calls=0, model="proc:tidy@2")]
    log[0]["procedure"], log[0]["procedure_version"] = "tidy", "2"
    assert audited(log, {"a": True}) == [entry("proc:tidy@2", "a", True, 5.0, cost_usd=0.0005)]


# --- plain calls, the window and drift ---------------------------------------------------------

def test_a_log_of_plain_calls_keeps_its_v1_632_rows():
    log = [rec("a", CHEAP, "invalid", final=False), rec("a", MID, "ok", attempt=1),
           rec("b", CHEAP, "ok")]
    assert audited(log, {"a": True, "b": False}) == [
        plain(CHEAP, "a", False, 5.0), plain(MID, "a", True, 5.0), plain(CHEAP, "b", False, 5.0)]


def test_a_cascade_call_is_kept_by_its_final_records_time_and_checked_outside_it():
    log = [leg("a", CHEAP, "ok", True, final=False, ts=OLD), leg("a", MID, "ok", True, ts=NEW),
           leg("b", CHEAP, "ok", False, ts=OLD)]
    assert audited(log, {"a": True, "b": True}, since=NEW) == [
        entry(C, "a", True, 10.0, escalated=True)]       # its two legs' 5.0 each
    bad = [leg("b", CHEAP, "ok", None, ts=OLD)] + log[:2]
    with pytest.raises(ValueError, match="call_id 'b': its cascade record's escalated"):
        audited(bad, {"a": True, "b": True}, since=NEW)


def test_drift_check_flags_a_cascade_that_fell_below_the_bar_in_the_window():
    log, audits = [], {}
    for i in range(500):   # 460 of 500 right all-time, 28 of the last 40 in November
        recent = i >= 460
        log.append(leg(f"k{i}", CHEAP, "ok", False, ts=NEW if recent else OLD))
        audits[f"k{i}"] = (i - 460 < 28) if recent else (i < 432)
    all_time = calibrate_from_results(audited(log, audits))
    window = calibrate_from_results(audited(log, audits, since="2026-11-01T00:00:00Z"))
    assert all_time.get("judge", C) == (460, 500) and window.get("judge", C) == (28, 40)
    [row] = drift_check(all_time, window, {"judge": Task("judge", bar=0.8, min_samples=10)})
    assert (row["route"], row["flag"]) == (C, "fell_below")


def test_records_and_audits_are_left_unchanged():
    for log in (cascade_log(), procedure_log()):   # the two logs share call IDs, so each alone
        audits = {"call-1": True, "call-2": False}
        before = copy.deepcopy(log)
        assert len(audited(log, audits)) >= 2
        assert log == before and audits == {"call-1": True, "call-2": False}


# --- checks ------------------------------------------------------------------------------------

@pytest.mark.parametrize("log, message", [
    ([rec("a", CHEAP, "ok", cascade=7, escalated=False)],
     "call_id 'a': cascade must be a non-empty string, got 7"),
    ([rec("a", CHEAP, "ok", cascade="", escalated=False)],
     "call_id 'a': cascade must be a non-empty string, got ''"),
    ([rec("a", CHEAP, "ok", cascade="cascade:x", escalated=False)],
     "call_id 'a': cascade must be a cascade's route ID, holding '>' and not starting with "
     "'proc:', got 'cascade:x'"),
    ([rec("a", CHEAP, "ok", cascade="proc:x>y", escalated=False)],
     "call_id 'a': cascade must be a cascade's route ID"),
    ([call_of("a", CHEAP, "ok"), closing("a", "ok", model="fiction/x")],
     "call_id 'a': a procedure's closing record's model must be its route ID, starting with "
     "'proc:', got 'fiction/x'"),
    ([call_of("a", CHEAP, "ok"), closing("a", "ok", model=None)],
     "call_id 'a': model must be a non-empty string, got None"),
    ([leg("a", CHEAP, "ok", None)],
     "call_id 'a': its cascade record's escalated must be true or false, got None"),
    ([leg("a", CHEAP, "ok", 1)],
     "call_id 'a': its cascade record's escalated must be true or false, got 1"),
    ([leg("a", CHEAP, "ok", True, final=False), leg("a", CHEAP, "ok", False, attempt=1)],
     f"call_id 'a': its cascade {C!r} kept its cheap answer, so its route entry needs that "
     "record alone, and the call holds 2 records of it"),
    ([leg("a", MID, "ok", True)],
     f"call_id 'a': its cascade {C!r} handed up, so its route entry needs its cheap leg's record "
     "(escalated true, final not true) before this one, and the call holds 1 record of it"),
    ([leg("a", CHEAP, "ok", False, final=False), leg("a", MID, "ok", True, attempt=1)],
     f"call_id 'a': its cascade {C!r} handed up"),
    ([leg("a", MID, "invalid", True, final=False), leg("a", CHEAP, "error", True, final=False,
                                                         attempt=1), rec("a", BEST, "ok", attempt=2)],
     f"call_id 'a': its cascade {C!r} handed up, so its route entry needs its cheap leg's record "
     "(escalated true, final not true) before this one, and the call holds 2 records of it"),
    ([leg("a", CHEAP, "ok", True, final=False), leg("a", MID, "ok", True, attempt=1),
      leg("a", CHEAP, "error", True, final=False, attempt=2)],
     "the call holds 3 records of it"),
    ([call_of("a", CHEAP, "ok"), closing("a", "ok", model_calls=True)],
     "call_id 'a': its procedure's closing record's model_calls must be an integer >= 0, got True"),
    ([call_of("a", CHEAP, "ok"), closing("a", "ok", model_calls=-1)],
     "call_id 'a': its procedure's closing record's model_calls must be an integer >= 0, got -1"),
    ([call_of("a", CHEAP, "ok"), closing("a", "ok", model_calls=2)],
     f"call_id 'a': its procedure {P!r} made 2 model calls, and the call holds 1 record of them"),
    ([closing("a", "ok", attempt=0)],
     f"call_id 'a': its procedure {P!r} made 1 model call, and the call holds 0 records of them"),
    ([call_of("a", CHEAP, "ok"), closing("a", "ok", cost_usd=None)],
     "call_id 'a': its procedure's closing record's cost_usd must be a finite number >= 0, got None"),
    ([call_of("a", CHEAP, "ok"), closing("a", "ok", cost_usd=True)],
     "call_id 'a': its procedure's closing record's cost_usd must be a finite number >= 0, got True"),
    ([call_of("a", CHEAP, "ok", cost_usd=-1), closing("a", "ok")],
     f"call_id 'a': a record of its procedure {P!r} before its closing one has cost_usd -1, "
     "not a finite number >= 0"),
    ([call_of("a", CHEAP, "ok", cost_usd=float("nan")), closing("a", "ok")],
     "before its closing one has cost_usd nan"),
    ([call_of("a", CHEAP, "ok", cost_usd=1e308), closing("a", "ok", cost_usd=1e308)],
     f"call_id 'a': the costs of its procedure {P!r} sum past the largest float"),
])
def test_a_bad_cascade_or_procedure_record_raises(log, message):
    with pytest.raises(ValueError) as exc:
        audited(log, {"a": True})
    assert message in str(exc.value)


def test_the_task_and_slice_checks_come_before_the_entry_checks():
    with pytest.raises(ValueError, match="call_id 'a': task must be a non-empty string"):
        audited([leg("a", CHEAP, "ok", None, task="")], {"a": True})
    with pytest.raises(ValueError, match="call_id 'a': slice must be null"):
        audited([call_of("a", CHEAP, "ok"), closing("a", "ok", model_calls=-1, slice="")],
                {"a": True})


# --- the spec and the docs ---------------------------------------------------------------------

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_design_and_the_changelog_state_v1_636():
    design = read("DESIGN.md")
    eight3 = design[design.index("\n### 8.3 "):design.index("\n## 9. ")]
    assert eight3.count("\n- v1.636 `audited_results` gives a cascade's and a procedure's audited "
                        "calls their rows (row M1d, v1.632, 7 v1.537 and v1.578): ") == 1
    assert eight3.index("\n- v1.633 `drift_check(") < eight3.index("\n- v1.636 `audited_results`")
    assert eight3.count("as `pair_results` v1.621 reads them (row M1d, which v1.636 adds)") == 1
    assert eight3.count("gave such a call no row before v1.636 (row M1d)") == 1
    ten = design[design.index("\n## 10. "):design.index("\n## 11. ")]
    assert ten.count("which `audited_results` gives no row (row M1d, which v1.636 adds, 8.3)") == 1
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.636 (")]
    assert line.startswith("- v1.636 (2026-11-24): spec, code and tests (8.3, row M1d). ")
    assert len(line.encode("utf-8")) <= 600


def test_no_doc_says_a_cascade_or_procedure_route_gets_no_rows_yet():
    for name in ("README.md", "research/production-lessons.md"):
        assert "route gets no rows from the log yet" not in read(name), name
    readme = read("README.md")
    # v1.647 (row PROD1g): the README says it in a shorter form; how such a row is read stays in DESIGN 8.3
    assert readme.count("and a cascade's or a procedure's audited call counts once for its route.") == 1
    assert read("research/production-lessons.md").count(
        "and from v1.636 a call that a cascade or a procedure answered counts for that route too. ") == 1


def test_only_monitor_py_reads_the_new_rows():
    # no evidence or research script calls audited_results, so every evidence file keeps its bytes
    scripts = [p for folder in ("evidence", "research") for p in (ROOT / folder).rglob("*.py")]
    assert len(scripts) >= 20
    assert [str(p) for p in scripts if "audited_results" in p.read_text(encoding="utf-8")] == []
