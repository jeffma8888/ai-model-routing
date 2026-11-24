"""A pair file's rows as an outcome matrix: `pair_results(pairs, records=..., routes=...)` (DESIGN 8.3
v1.614, row CANARY1m; the rows are 8.3 v1.613, the pair file 8.3 v1.610 and the matrix 12.1 and 12.3)."""

import inspect
import json
from math import fsum
from pathlib import Path

import pytest

import model_routing
from model_routing import (
    Completion, Executor, FakeProvider, Model, Monitor, ProviderError, Registry, Router, Stats,
    Task, load_records, shadow_pairs,
)
from model_routing.evaluate import evaluate, outcomes_from_rows, split_items
from model_routing.stats import calibrate_from_results, item_outcomes

ROOT = Path(__file__).resolve().parents[1]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
ITEMS = [f"p{i}" for i in range(8)]
# hand-set costs and labels of the eight pairs routed on CHEAP and shadowed on BEST
COST_CHEAP = {"p0": 0.001, "p1": 0.002, "p2": 0.003, "p3": 0.004, "p4": 0.005, "p5": 0.006,
              "p6": 0.007, "p7": 0.008}
COST_BEST = {"p0": 0.01, "p1": 0.02, "p2": 0.03, "p3": 0.04, "p4": 0.05, "p5": 0.06,
             "p6": 0.07, "p7": 0.08}
OK_CHEAP = {"p0": True, "p1": True, "p2": True, "p3": False, "p4": True, "p5": True,
            "p6": False, "p7": True}
OK_BEST = {i: i != "p5" for i in ITEMS}


def results(*args, **kwargs):
    return model_routing.pair_results(*args, **kwargs)


def rec(call_id, model, cost, *, pair_id, shadow=False, attempt=0, final=True, outcome="ok",
        slice=None):
    return {"ts": "2026-11-23T00:00:00Z", "call_id": call_id, "task": "judge",
            "flavor": "cost_effective", "model": model, "attempt": attempt, "final": final,
            "outcome": outcome, "cost_usd": cost, "tags": {"shadow": "true"} if shadow else {},
            "slice": slice, "pair_id": pair_id, "shadow": shadow}


def hand_log():
    log = []
    for i in ITEMS:
        log.append(rec(i, CHEAP, COST_CHEAP[i], pair_id=i))
        log.append(rec(i + "-s", BEST, COST_BEST[i], pair_id=i, shadow=True))
    # p8: the routed call's CHEAP attempt was invalid, so MID, a fallback, answered it
    log.append(rec("p8", CHEAP, 0.0035, pair_id="p8", final=False, outcome="invalid"))
    log.append(rec("p8", MID, 0.0045, pair_id="p8", attempt=1))
    log.append(rec("p8-s", BEST, 0.045, pair_id="p8", shadow=True))
    # p9: the shadow erred, so its pair has a None side and gives no row
    log.append(rec("p9", CHEAP, 0.0011, pair_id="p9"))
    log.append(rec("p9-s", BEST, 0.0, pair_id="p9", shadow=True, outcome="error"))
    # a budget record of p0's call (8.1 v1.598), which is no attempt record
    log.insert(1, {"ts": "2026-11-23T00:00:00Z", "call_id": "p0", "task": "judge", "tags": {},
                   "pair_id": "p0", "shadow": False, "budget_event": "warn", "budget": "daily",
                   "mode": "warn", "window": None, "share": 0.5, "spent_usd": 1.0,
                   "limit_usd": 2.0})
    return log


AUDITS = {**{i: OK_CHEAP[i] for i in ITEMS}, **{i + "-s": OK_BEST[i] for i in ITEMS},
          "p8": True, "p8-s": False, "p9": True}


def write_jsonl(path, values):
    path.write_text("".join(json.dumps(v) + "\n" for v in values), encoding="utf-8")
    return path


@pytest.fixture
def files(tmp_path):
    log = write_jsonl(tmp_path / "calls.jsonl", hand_log())
    pairs = write_jsonl(tmp_path / "pairs.jsonl", shadow_pairs(load_records(log), audits=AUDITS))
    return load_records(pairs), load_records(log)


def row(model, item, correct, cost, slice=None):
    out = {"task": "judge", "model": model, "item": item, "correct": correct, "cost_usd": cost}
    return out if slice is None else {**out, "slice": slice}


# --- the rows with their costs ------------------------------------------------------------

def test_each_row_gains_its_sides_cost_after_correct(files):
    pairs, log = files
    rows = results(pairs, records=log)
    expected = []
    for i in ITEMS:
        expected += [row(CHEAP, i, OK_CHEAP[i], COST_CHEAP[i]), row(BEST, i, OK_BEST[i], COST_BEST[i])]
    expected += [row(MID, "p8", True, 0.0045), row(BEST, "p8", False, 0.045)]
    assert rows == expected  # p9's shadow erred, so its pair gives no row
    assert [list(r) for r in rows] == [["task", "model", "item", "correct", "cost_usd"]] * 18


def test_a_fallback_row_costs_its_final_record_alone_not_the_failed_attempt_before_it(files):
    pairs, log = files
    rows = results(pairs, records=log, routes=(MID, BEST))
    assert rows == [row(MID, "p8", True, 0.0045), row(BEST, "p8", False, 0.045)]
    assert rows[0]["cost_usd"] != 0.0035 + 0.0045


def test_a_sliced_pair_keeps_slice_last_after_cost_usd():
    log = [rec("c2", CHEAP, 0.25, pair_id="c2", slice="long"),
           rec("c2-s", BEST, 0.5, pair_id="c2", shadow=True, slice="long")]
    pairs = shadow_pairs(log, checked=True)
    rows = results(pairs, records=log)
    assert rows == [row(CHEAP, "c2", True, 0.25, "long"), row(BEST, "c2", True, 0.5, "long")]
    assert list(rows[0]) == ["task", "model", "item", "correct", "cost_usd", "slice"]


def test_the_routes_filter_keeps_one_route_pair_and_its_order(files):
    pairs, log = files
    rows = results(pairs, records=log, routes=(CHEAP, BEST))
    assert [r["item"] for r in rows] == [i for i in ITEMS for _ in (0, 1)]
    assert {r["model"] for r in rows} == {CHEAP, BEST}
    assert results(pairs, records=log, routes=[CHEAP, BEST]) == rows  # a list serves too
    assert results(pairs, records=log, routes=(BEST, CHEAP)) == []    # the order is the pair's
    assert results(pairs, routes=(CHEAP, BEST)) == [
        {k: v for k, v in r.items() if k != "cost_usd"} for r in rows]  # without records


# --- evaluate reads them ------------------------------------------------------------------

def test_evaluate_runs_on_the_rows_with_each_sides_cost_checked_by_hand(files):
    pairs, log = files
    outcomes = outcomes_from_rows(results(pairs, records=log, routes=(CHEAP, BEST)))
    result = evaluate(outcomes, bars=[0.8], seeds=[0, 1, 2], min_samples=1)
    assert result["tasks"] == {"judge": {"items": 8, "models": [BEST, CHEAP]}}
    # held-out items by split_items (12.2): seed 0 p0 p1 p3 p6, seed 1 p0 p5, seed 2 p0 p2 p3 p5 p7
    assert [split_items(ITEMS, seed)[1] for seed in (0, 1, 2)] == [
        ("p0", "p1", "p3", "p6"), ("p0", "p5"), ("p0", "p2", "p3", "p5", "p7")]
    hand = {0: (0.014, 0.14, 0.5, 1.0), 1: (0.007, 0.07, 1.0, 0.5), 2: (0.022, 0.22, 0.8, 0.8)}
    cells = [c for c in result["cells"] if c["flavor"] == "cost_effective"]
    assert [c["seed"] for c in cells] == [0, 1, 2]
    for cell in cells:
        cheap_cost, best_cost, cheap_ok, best_ok = hand[cell["seed"]]
        assert cell["cost_usd"]["model:" + CHEAP] == pytest.approx(cheap_cost, rel=1e-12)
        assert cell["cost_usd"]["model:" + BEST] == pytest.approx(best_cost, rel=1e-12)
        assert cell["success"]["model:" + CHEAP] == cheap_ok
        assert cell["success"]["model:" + BEST] == best_ok
        held = split_items(ITEMS, cell["seed"])[1]
        assert cell["cost_usd"]["model:" + CHEAP] == fsum(COST_CHEAP[i] for i in held)


def test_without_routes_a_fallbacks_pair_leaves_the_matrix_incomplete(files):
    pairs, log = files
    outcomes = outcomes_from_rows(results(pairs, records=log))
    with pytest.raises(ValueError, match="incomplete matrix: no row for task 'judge', item 'p0', "
                                         "model 'fiction/mid'"):
        evaluate(outcomes, bars=[0.8], seeds=[0], min_samples=1)


def test_without_records_the_rows_hold_no_cost_so_no_outcome_matrix(files):
    pairs, _ = files
    with pytest.raises(ValueError, match="needs 'cost_usd' or both token counts"):
        outcomes_from_rows(results(pairs, routes=(CHEAP, BEST)))


def test_calibrate_and_item_outcomes_read_the_rows_as_they_read_v1_613s(files):
    pairs, log = files
    costed, plain = results(pairs, records=log), results(pairs)
    a, b = calibrate_from_results(costed), calibrate_from_results(plain)
    for model_id in (CHEAP, MID, BEST):
        assert a.get("judge", model_id) == b.get("judge", model_id)
    assert a.get("judge", CHEAP) == (6, 8) and a.get("judge", BEST) == (7, 9)
    digest = "0" * 64
    assert item_outcomes(costed, dataset_sha256=digest) == item_outcomes(plain,
                                                                         dataset_sha256=digest)


def test_under_checked_labels_every_routed_row_is_true():  # review iter-465 should-fix 1
    log = []
    for i, outcome in enumerate(("ok", "invalid", "ok")):
        log += [rec(f"q{i}", CHEAP, 0.001, pair_id=f"q{i}"),
                rec(f"q{i}-s", BEST, 0.01, pair_id=f"q{i}", shadow=True, outcome=outcome)]
    rows = results(shadow_pairs(log, checked=True), records=log, routes=(CHEAP, BEST))
    assert [r["correct"] for r in rows if r["model"] == CHEAP] == [True, True, True]
    assert [r["correct"] for r in rows if r["model"] == BEST] == [True, False, True]


def test_a_real_shadowed_run_gives_each_side_its_list_price():
    task = Task("judge", bar=0.7, min_samples=10, shadow_rate=1.0)
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (BEST, (100, 100))):
        stats.add(task.name, model_id, successes, trials)
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000),
                         Model(BEST, "large", 10.0, 20.0, 8000)])
    queue = {CHEAP: ["cheap", "cheap"], BEST: ["best", "bad"]}

    def answer(model_id):
        def complete(messages):
            if not queue[model_id]:
                raise ProviderError("outage")
            return Completion(queue[model_id].pop(0), 1000, 200)
        return complete
    monitor = Monitor()
    ids = iter(f"call-{i}" for i in range(100))
    ticks = iter(float(i) for i in range(1000))
    executor = Executor(Router(registry, {task.name: task}, stats),
                        FakeProvider({CHEAP: answer(CHEAP), BEST: answer(BEST)}), monitor=monitor,
                        clock=lambda: next(ticks), now=lambda: "2026-11-23T00:00:00Z",
                        id_factory=lambda: next(ids), random=lambda: 0.0)
    for _ in range(2):
        executor.call("judge", [{"role": "user", "content": "judge"}],
                      validate=lambda text: text != "bad")
    rows = results(shadow_pairs(monitor.records, checked=True), records=monitor.records)
    # 1000 input and 200 output tokens: CHEAP 1000 * 1.0 / 1e6 + 200 * 2.0 / 1e6 = 0.0014 and
    # BEST 1000 * 10.0 / 1e6 + 200 * 20.0 / 1e6 = 0.014, the invalid answer's tokens paid too
    assert [(r["model"], r["item"], r["correct"]) for r in rows] == [
        (CHEAP, "call-0", True), (BEST, "call-0", True), (CHEAP, "call-2", True),
        (BEST, "call-2", False)]
    assert [r["cost_usd"] for r in rows] == pytest.approx([0.0014, 0.014, 0.0014, 0.014],
                                                          rel=1e-12)


# --- v1.613 without the keywords ----------------------------------------------------------

def test_without_the_keywords_every_row_is_v1_613s_byte_for_byte(files):
    pairs, _ = files
    plain = results(pairs)
    assert results(pairs, records=None, routes=None) == plain
    assert json.dumps(plain[:2]) == (
        '[{"task": "judge", "model": "fiction/cheap", "item": "p0", "correct": true}, '
        '{"task": "judge", "model": "fiction/best", "item": "p0", "correct": true}]')
    assert len(plain) == 18 and all("cost_usd" not in r for r in plain)


def test_the_signature_adds_two_keyword_only_arguments():
    params = inspect.signature(model_routing.pair_results).parameters
    assert [(n, p.kind.name, p.default) for n, p in params.items()][1:] == [
        ("records", "KEYWORD_ONLY", None), ("routes", "KEYWORD_ONLY", None)]


# --- what is looked up and what is not ----------------------------------------------------

def test_a_pair_that_gives_no_row_is_not_looked_up(files):
    pairs, log = files
    p9 = [p for p in pairs if p["pair_id"] == "p9"]
    assert results(p9, records=[]) == []                                       # a None side
    assert results(pairs[:1], records=[], routes=(MID, BEST)) == []             # another pair


def test_records_and_pairs_may_be_generators_and_are_left_unchanged(files):
    pairs, log = files
    before_pairs, before_log = json.dumps(pairs), json.dumps(log)
    rows = results((p for p in pairs), records=(r for r in log), routes=(CHEAP, BEST))
    assert len(rows) == 16
    assert json.dumps(pairs) == before_pairs and json.dumps(log) == before_log


def test_a_v1_613_check_runs_before_any_record_lookup(files):
    pairs, _ = files
    with pytest.raises(ValueError, match="pair 2: routed_route and shadow_route are both"):
        results([pairs[0], {**pairs[1], "shadow_route": CHEAP}], records=[])


# --- checks -------------------------------------------------------------------------------

ROUTES_MESSAGE = "routes must be None or a list or tuple of two different non-empty strings"


@pytest.mark.parametrize("routes", [
    CHEAP + BEST, "ab", (CHEAP,), (CHEAP, BEST, MID), (CHEAP, CHEAP), (CHEAP, ""), (CHEAP, 3),
    {CHEAP, BEST}, {CHEAP: BEST}, (None, BEST),
])
def test_a_bad_routes_raises(files, routes):
    pairs, log = files
    with pytest.raises(ValueError) as exc:
        results(pairs, records=log, routes=routes)
    assert ROUTES_MESSAGE in str(exc.value)


def test_a_record_that_is_not_a_mapping_raises_naming_its_position(files):
    pairs, log = files
    with pytest.raises(ValueError, match="record 3 must be a mapping, got 'x'"):
        results(pairs, records=log[:2] + ["x"] + log[2:])
    with pytest.raises(ValueError, match="record 1 must be a mapping, got 'call_id'"):
        results(pairs, records={"call_id": "p0"})   # one record passed alone


def without(log, call_id, model):
    return [r for r in log if not (r.get("call_id") == call_id and r.get("model") == model
                                   and "budget_event" not in r)]


@pytest.mark.parametrize("edit, message", [
    (lambda log: without(log, "p1", CHEAP),
     "pair 2: its routed call 'p1' has no final record in the log"),
    (lambda log: log + [rec("p1", CHEAP, 0.002, pair_id="p1")],
     "pair 2: its routed call 'p1' has 2 final records in the log"),
    (lambda log: without(log, "p1-s", BEST),
     "pair 2: its shadow call 'p1-s' has no final record in the log"),
    (lambda log: log + [rec("p1-s", BEST, 0.02, pair_id="p1", shadow=True)],
     "pair 2: its shadow call 'p1-s' has 2 final records in the log"),
    (lambda log: [{**r, "model": MID} if r.get("call_id") == "p1" else r for r in log],
     "pair 2: the log's routed call 'p1' ends on 'fiction/mid', not on its routed_route "
     "'fiction/cheap'"),
    (lambda log: [{**r, "model": MID} if r.get("call_id") == "p1-s" else r for r in log],
     "pair 2: the log's shadow call 'p1-s' ran 'fiction/mid', not its shadow_route "
     "'fiction/best'"),
    (lambda log: [{**r, "pair_id": "p0"} if r.get("call_id") == "p1-s" else r for r in log],
     "pair 2: its shadow call 'p1-s' has no final record in the log"),
    (lambda log: [{**r, "final": False} if r.get("call_id") == "p1" else r for r in log],
     "pair 2: its routed call 'p1' has no final record in the log"),
])
def test_a_missing_doubled_or_mismatched_record_raises_naming_the_pair(files, edit, message):
    pairs, log = files
    with pytest.raises(ValueError) as exc:
        results(pairs, records=edit(log))
    assert message in str(exc.value)


def test_a_shadow_call_id_naming_no_record_raises():  # review iter-465 nit 5
    log = [rec("p1", CHEAP, 0.002, pair_id="p1"), rec("p1-s", BEST, 0.02, pair_id="p1", shadow=True)]
    pairs = [{**shadow_pairs(log, checked=True)[0], "shadow_call_id": "p1-x"}]
    with pytest.raises(ValueError, match="pair 1: its shadow call 'p1-x' has no final record in the log"):
        results(pairs, records=log)


def test_a_budget_record_is_dropped_before_any_lookup():  # review iter-465 nit 1
    log = [rec("p1", CHEAP, 0.002, pair_id="p1"), rec("p1-s", BEST, 0.02, pair_id="p1", shadow=True)]
    pairs = shadow_pairs(log, checked=True)
    # a hand-edited budget record that carries the routed call's keys and final true (8.1 v1.598
    # writes neither), so only the drop keeps it from being a second final record
    budget = {**log[0], "budget_event": "refused", "cost_usd": 9.0}
    assert results(pairs, records=[budget] + log) == [row(CHEAP, "p1", True, 0.002),
                                                      row(BEST, "p1", True, 0.02)]


@pytest.mark.parametrize("cost", [None, True, -0.001, float("inf"), float("nan"), "0.002"])
@pytest.mark.parametrize("side, call_id, name", [("routed", "p1", "routed"),
                                                 ("shadow", "p1-s", "shadow")])
def test_a_bad_cost_raises_naming_the_pair_and_side(files, cost, side, call_id, name):
    pairs, log = files
    edited = [{**r, "cost_usd": cost} if r.get("call_id") == call_id else r for r in log]
    with pytest.raises(ValueError) as exc:
        results(pairs, records=edited)
    assert f"pair 2: the {name} final record's cost_usd must be a finite number >= 0, got " \
        in str(exc.value)


def test_a_missing_cost_raises_too(files):
    pairs, log = files
    edited = [{k: v for k, v in r.items() if k != "cost_usd"} if r.get("call_id") == "p1" else r
              for r in log]
    with pytest.raises(ValueError, match="pair 2: the routed final record's cost_usd must be a "
                                         "finite number >= 0, got None"):
        results(pairs, records=edited)


def test_an_integer_cost_is_kept_as_recorded(files):
    pairs, log = files
    edited = [{**r, "cost_usd": 0} if r.get("call_id") == "p0" else r for r in log]
    rows = results(pairs, records=edited, routes=(CHEAP, BEST))
    assert rows[0]["cost_usd"] == 0 and type(rows[0]["cost_usd"]) is int


def test_a_bad_shadow_call_id_raises_with_records_only(files):
    pairs, log = files
    bad = [pairs[0], {**pairs[1], "shadow_call_id": None}]
    with pytest.raises(ValueError, match="pair 2: shadow_call_id must be a non-empty string, "
                                         "got None"):
        results(bad, records=log)
    assert len(results(bad)) == 4  # v1.613 reads no shadow_call_id


def test_every_pairs_records_are_checked_before_any_row(files):
    pairs, log = files
    with pytest.raises(ValueError, match="pair 9: "):
        results(pairs, records=without(log, "p8-s", BEST))


# --- the spec -----------------------------------------------------------------------------

def test_design_and_changelog_state_v1_614():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    section = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert section.count("- v1.614 `pair_results(pairs, *, records=None, routes=None) -> "
                         "list[dict]` (row CANARY1m, v1.613)") == 1
    assert "cannot read the rows (row CANARY1m, which v1.614 adds as the `records` and `routes` " \
        "keywords)" in section
    assert "as an outcome matrix for `evaluate` (v1.614, row CANARY1m)" in section
    assert "So under `checked=True` every routed row is `true`" in section  # iter-465 should-fix 1
    assert "the routed side's checked before the shadow's (review iter-465 nit 3)." in section
    seven = design[design.index("## 7. "):design.index("## 8. ")]
    assert "which v1.614 adds as `pair_results`' `records` and `routes`, 8.3);" in seven
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.614 (2026-11-23): spec, code and tests (8.3, row CANARY1m).") == 1
