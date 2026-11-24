"""A cascade's or a procedure's routed side gives results rows from the log (DESIGN 8.3 and 10
v1.621, row CANARY2): its cost the route entry's records, a cascade's row with `escalated`."""

import json
import math
from pathlib import Path

import pytest

from model_routing import (
    Cascade, Completion, Executor, FakeProvider, Model, Monitor, Procedure, ProcedureResult,
    Registry, Router, Stats, Task, calibrate_from_results, evaluate, item_outcomes, load_records,
    outcomes_from_rows, pair_results, shadow_pairs,
)
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
REGISTRY = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000),
                     Model(BEST, "large", 10.0, 20.0, 8000)])
CASCADE = Cascade(CHEAP, MID, "sig")  # fiction/cheap>fiction/mid@sig
SHA = "0" * 64


def polling(value, call):
    text = call([{"role": "user", "content": "summarize"}])
    return ProcedureResult("shaped " + text, tool_calls=3, tool_cost_usd=0.0005)


POLLING = Procedure("poll", "v1", polling, max_model_calls=2, max_tool_calls=5, model=CHEAP)


def entry_router(entry_id, **counts):
    """cheap 50/100 is under the 0.7 bar, so the entry at 100/100 is the primary; best's 98/100
    is the highest registry bound, so best is the default shadow route."""
    stats = Stats()
    for model_id, successes in ((CHEAP, 50), (MID, 95), (BEST, 98)):
        stats.add("judge", model_id, successes, 100)
    stats.add("judge", entry_id, 100, 100, **counts)
    tasks = {"judge": Task("judge", bar=0.7, min_samples=10, cascades=(CASCADE,), shadow_rate=1.0)}
    return Router(REGISTRY, tasks, stats)


def executor(route, monitor):
    ids = iter(f"call-{i}" for i in range(100))
    ticks = iter(float(i) for i in range(1000))
    prov = FakeProvider({m: (lambda name: lambda messages: Completion(name, 1000, 200))(m)
                         for m in (CHEAP, MID, BEST)})
    return Executor(route, prov, monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: "2026-11-24T00:00:00Z", id_factory=lambda: next(ids),
                    random=lambda: 0.0)


def cascade_log():
    """call-0 keeps the cheap answer, call-2 hands up; each shadowed on best (call-1, call-3)."""
    monitor = Monitor()
    run = executor(entry_router(CASCADE.id, escalated=20), monitor)
    run.call("judge", MESSAGES, signals={"sig": lambda text: False}, validate=lambda text: True)
    run.call("judge", MESSAGES, signals={"sig": lambda text: True}, validate=lambda text: True)
    return monitor.records


def procedure_log():
    monitor = Monitor()
    executor(entry_router(POLLING.id, cost_usd=0.02), monitor).call(
        "judge", MESSAGES, procedures=[POLLING], validate=lambda text: True)
    return monitor.records


def cost(records, call_id, model):
    found = [r for r in records if r["call_id"] == call_id and r["model"] == model]
    assert len(found) == 1
    return found[0]["cost_usd"]


# --- the rows -------------------------------------------------------------------------------

def test_a_cascade_pair_gives_its_row_with_escalated_and_the_whole_cascade_s_cost():
    records = cascade_log()
    assert [(r["call_id"], r["model"], r.get("escalated")) for r in records] == [
        ("call-0", CHEAP, False), ("call-1", BEST, None),
        ("call-2", CHEAP, True), ("call-2", MID, True), ("call-3", BEST, None)]
    rows = pair_results(shadow_pairs(records, checked=True), records=records)
    handed_up = math.fsum([cost(records, "call-2", CHEAP), cost(records, "call-2", MID)])
    assert abs(handed_up - (0.0014 + 0.0042)) < 1e-12  # 1000 in and 200 out at 1/2 and 3/6 a 1M
    assert rows == [
        {"task": "judge", "model": CASCADE.id, "item": "call-0", "correct": True,
         "cost_usd": cost(records, "call-0", CHEAP), "escalated": False},
        {"task": "judge", "model": BEST, "item": "call-0", "correct": True,
         "cost_usd": cost(records, "call-1", BEST)},
        {"task": "judge", "model": CASCADE.id, "item": "call-2", "correct": True,
         "cost_usd": handed_up, "escalated": True},
        {"task": "judge", "model": BEST, "item": "call-2", "correct": True,
         "cost_usd": cost(records, "call-3", BEST)}]
    assert list(rows[0]) == ["task", "model", "item", "correct", "cost_usd", "escalated"]
    stats = calibrate_from_results(rows)
    assert stats.get("judge", CASCADE.id) == (2, 2)
    assert stats.escalations("judge", CASCADE.id) == 1
    assert [o["route"] for o in item_outcomes(rows, dataset_sha256=SHA)] == [CASCADE.id, BEST] * 2


def test_a_procedure_pair_gives_its_row_at_its_model_calls_plus_its_tool_cost():
    records = procedure_log()
    assert [(r["call_id"], r["model"]) for r in records] == [
        ("call-0", CHEAP), ("call-0", POLLING.id), ("call-1", BEST)]
    rows = pair_results(shadow_pairs(records, checked=True), records=records)
    whole = math.fsum([cost(records, "call-0", CHEAP), 0.0005])
    assert rows == [
        {"task": "judge", "model": POLLING.id, "item": "call-0", "correct": True, "cost_usd": whole},
        {"task": "judge", "model": BEST, "item": "call-0", "correct": True,
         "cost_usd": cost(records, "call-1", BEST)}]
    assert calibrate_from_results(rows).cost("judge", POLLING.id) == whole


def test_a_sliced_cascade_row_keeps_slice_last():
    records = cascade_log()
    for rec in records:
        rec["slice"] = "long"
    rows = pair_results(shadow_pairs(records, checked=True), records=records)
    assert list(rows[2]) == ["task", "model", "item", "correct", "cost_usd", "escalated", "slice"]


def test_routes_keeps_the_cascade_route_pair_which_evaluate_refuses():
    records = cascade_log()
    rows = pair_results(shadow_pairs(records, checked=True), records=records,
                        routes=(CASCADE.id, BEST))
    assert [row["model"] for row in rows] == [CASCADE.id, BEST] * 2
    with pytest.raises(ValueError, match=f"cascade {CASCADE.id!r}: its cheap model {CHEAP!r} is "
                                         "not a model of the matrix"):
        evaluate(outcomes_from_rows(rows), bars=[0.5], seeds=[0], min_samples=1)


def test_an_earlier_entry_that_failed_before_a_fallback_onto_the_cascade_is_not_charged():
    records = [rec(CHEAP + "x", 0.5, final=False, outcome="invalid", cascade=False),
               rec(CHEAP, 0.001, attempt=1, escalated=False), shadow_rec()]
    rows = pair_results(shadow_pairs(records, checked=True), records=records)
    assert rows[0]["cost_usd"] == 0.001 and rows[0]["escalated"] is False


# --- checks ---------------------------------------------------------------------------------

def rec(model, cost_usd, *, attempt=0, final=True, outcome="ok", escalated=None, cascade=True,
        **extra):
    out = {"call_id": "c0", "task": "judge", "model": model, "attempt": attempt, "final": final,
           "outcome": outcome, "cost_usd": cost_usd, "slice": None, "pair_id": "c0", "shadow": False}
    if cascade:
        out.update(cascade=CASCADE.id, escalated=escalated)
    out.update(extra)
    return out


def shadow_rec(cost_usd=0.02):
    return {"call_id": "c0-s", "task": "judge", "model": BEST, "attempt": 0, "final": True,
            "outcome": "ok", "cost_usd": cost_usd, "slice": None, "pair_id": "c0", "shadow": True}


def proc_rec(cost_usd, **extra):
    return rec(POLLING.id, cost_usd, cascade=False, procedure="poll", procedure_version="v1",
               **extra)


def proc_call(cost_usd=0.0014):
    return rec(CHEAP, cost_usd, final=False, cascade=False, procedure="poll",
               procedure_version="v1")


CHECKS = {
    "escalated missing": ([rec(CHEAP, 0.001, escalated=None), shadow_rec()],
                          "pair 1: its routed cascade's final record's escalated must be true or false, "
                          "got None"),
    "escalated not a bool": ([rec(CHEAP, 0.001, escalated=1), shadow_rec()],
                             "pair 1: its routed cascade's final record's escalated must be true or "
                             "false, got 1"),
    "a handed-up call without its cheap leg": (
        [rec(MID, 0.004, attempt=1, escalated=True), shadow_rec()],
        f"pair 1: its routed cascade {CASCADE.id!r} handed up, so its route entry needs its cheap "
        "leg's record (escalated true, final not true) and its final record, and the log holds 1 "
        "record of it"),
    "a kept answer with a second record": (
        [rec(CHEAP, 0.001, final=False, escalated=True), rec(CHEAP, 0.001, attempt=1, escalated=False),
         shadow_rec()],
        f"pair 1: its routed cascade {CASCADE.id!r} kept its cheap answer, so its route entry needs "
        "its final record alone, and the log holds 2 records of it"),
    "a leg that says final": (
        [rec(CHEAP, 0.001, escalated=True), rec(MID, 0.004, attempt=1, escalated=True), shadow_rec()],
        "pair 1: its routed call 'c0' has 2 final records in the log"),
    "model_calls negative": ([proc_call(), proc_rec(0.0005, attempt=1, model_calls=-1), shadow_rec()],
                             "pair 1: its routed procedure's closing record's model_calls must be an "
                             "integer >= 0, got -1"),
    "model_calls missing reads as a model call": (  # v1.579's entry check comes first (v1.614)
        [proc_call(), proc_rec(0.0005, attempt=1), shadow_rec()],
        f"pair 1: the log's routed call 'c0' ends on 'proc:poll@v1+{POLLING.id}', not on its "
        f"routed_route {POLLING.id!r}"),
    "model_calls a bool": ([proc_rec(0.0005, model_calls=True), shadow_rec()],
                           "pair 1: its routed procedure's closing record's model_calls must be an "
                           "integer >= 0, got True"),
    "a model call missing": (
        [proc_rec(0.0005, attempt=1, model_calls=2), proc_call(), shadow_rec()],
        f"pair 1: its routed procedure {POLLING.id!r} made 2 model calls, and the log holds 1 record "
        "of them"),
    "an earlier record's cost": (
        [proc_call(cost_usd=-1.0), proc_rec(0.0005, attempt=1, model_calls=1), shadow_rec()],
        f"pair 1: a record of its routed entry {POLLING.id!r} before its final one has cost_usd -1.0, "
        "not a finite number >= 0"),
    "a sum past the largest float": (
        [proc_call(cost_usd=1.7e308), proc_rec(1.7e308, attempt=1, model_calls=1), shadow_rec()],
        f"pair 1: the costs of its routed entry {POLLING.id!r} sum past the largest float"),
}


@pytest.mark.parametrize("case", sorted(CHECKS))
def test_a_routed_entry_whose_records_are_not_whole_is_refused(case):
    records, message = CHECKS[case]
    pairs = [{"pair_id": "c0", "task": "judge", "slice": None,
              "routed_route": records[0].get("cascade") or POLLING.id, "shadow_route": BEST,
              "shadow_call_id": "c0-s", "shadow_outcome": "ok", "routed_correct": True,
              "shadow_correct": True}]
    with pytest.raises(ValueError) as exc:
        pair_results(pairs, records=records)
    assert str(exc.value) == message


@pytest.mark.parametrize("route", [CASCADE.id, POLLING.id])
def test_without_records_the_v1_613_refusal_stands(route):
    pair = {"pair_id": "c0", "task": "judge", "routed_route": route, "shadow_route": BEST,
            "routed_correct": True, "shadow_correct": True}
    with pytest.raises(ValueError) as exc:
        pair_results([pair])
    assert str(exc.value) == (f"pair 1: routed_route {route!r} is a cascade's or a procedure's, whose "
                              "row needs escalated or cost_usd, which a pair does not hold")


@pytest.mark.parametrize("route", [CASCADE.id, POLLING.id])
def test_a_cascade_or_procedure_shadow_route_is_refused_with_records_too(route):
    pair = {"pair_id": "c0", "task": "judge", "routed_route": BEST, "shadow_route": route,
            "routed_correct": None, "shadow_correct": None}
    with pytest.raises(ValueError) as exc:
        pair_results([pair], records=[])
    assert str(exc.value) == (f"pair 1: shadow_route {route!r} is a cascade's or a procedure's, "
                              "which the executor never shadows on, since it shadows on a registry "
                              "model only, so the pair is not of a monitor log")


def test_a_plain_pair_s_rows_keep_their_keys_and_costs_as_recorded():
    records = [rec(CHEAP, 0, cascade=False), shadow_rec(cost_usd=0)]
    rows = pair_results(shadow_pairs(records, checked=True), records=records)
    assert rows == [{"task": "judge", "model": CHEAP, "item": "c0", "correct": True, "cost_usd": 0},
                    {"task": "judge", "model": BEST, "item": "c0", "correct": True, "cost_usd": 0}]
    assert type(rows[0]["cost_usd"]) is int  # as recorded, not summed (v1.614)


# --- the command ----------------------------------------------------------------------------

def test_pairs_results_writes_a_cascade_pair_s_rows_and_routes_keeps_them(tmp_path, capsys):
    log = tmp_path / "calls.jsonl"
    log.write_text("".join(json.dumps(r) + "\n" for r in cascade_log()), encoding="utf-8")
    out, results = tmp_path / "pairs.jsonl", tmp_path / "rows.jsonl"
    code = main(["pairs", "--log", str(log), "--out", str(out), "--checked", "--results",
                 str(results), "--routes", CASCADE.id, BEST])
    captured = capsys.readouterr()
    assert (code, captured.err) == (0, "")
    records = load_records(log)
    rows = pair_results(shadow_pairs(records, checked=True), records=records)
    assert results.read_text(encoding="utf-8") == "".join(json.dumps(r) + "\n" for r in rows)
    assert captured.out == (f"wrote 2 pairs to {out}: 2 with both sides labelled\n"
                            f"wrote 4 results rows to {results}: routed {CASCADE.id}, shadow {BEST}\n"
                            "labelled pairs of other route pairs left out: 0\n")


def test_the_spec_and_changelog_name_the_rule():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert "- v1.621 `pair_results(..., records=...)` reads a cascade's or a procedure's routed side (row CANARY2" in design
    assert "- v1.621 `pairs --results` on a cascade's or a procedure's pair (row CANARY2, 8.3 v1.621)" in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert [line for line in changelog.splitlines()  # any line, so a later version keeps it
            if line.startswith("- v1.621 (2026-11-24): spec, code, docs and tests (8.3, 10, row CANARY2).")] != []
