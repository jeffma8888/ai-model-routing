"""Labeled results rows from a pair file: `pair_results` (DESIGN 8.3 v1.613, row CANARY1d; the pair
file is 8.3 v1.610 and the `pairs` command 10 v1.612)."""

import hashlib
import json
from pathlib import Path

import pytest

import model_routing
from model_routing import (
    Completion, Executor, FakeProvider, Model, Monitor, ProviderError, Registry, Router, Stats,
    Task, load_records, shadow_pairs,
)
from model_routing.promotion import pair_outcomes, paired_promotion
from model_routing.stats import calibrate_from_results, item_outcomes

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
ROW_KEYS = ["task", "model", "item", "correct"]


def results(*args, **kwargs):
    return model_routing.pair_results(*args, **kwargs)


def pair(pair_id, routed_correct, shadow_correct, routed=CHEAP, shadow=BEST, slice=None,
         task="judge"):
    return {"pair_id": pair_id, "task": task, "slice": slice, "routed_route": routed,
            "shadow_route": shadow, "shadow_call_id": pair_id + "-s", "shadow_outcome": "ok",
            "routed_correct": routed_correct, "shadow_correct": shadow_correct}


def row(model, item, correct, slice=None):
    out = {"task": "judge", "model": model, "item": item, "correct": correct}
    return out if slice is None else {**out, "slice": slice}


HAND = [pair("c0", True, True), pair("c2", False, True, slice="long"),
        pair("c4", True, None, routed=MID), pair("c6", None, None), pair("c8", True, False)]
EXPECTED = [row(CHEAP, "c0", True), row(BEST, "c0", True),
            row(CHEAP, "c2", False, "long"), row(BEST, "c2", True, "long"),
            row(CHEAP, "c8", True), row(BEST, "c8", False)]


def pair_file(tmp_path, pairs):
    path = tmp_path / "pairs.jsonl"
    path.write_text("".join(json.dumps(p) + "\n" for p in pairs), encoding="utf-8")
    return path


# --- a hand-built pair file -------------------------------------------------------------

def test_two_rows_per_pair_with_both_sides_labelled_routed_side_first(tmp_path):
    assert results(load_records(pair_file(tmp_path, HAND))) == EXPECTED


def test_a_row_has_its_keys_in_order_and_slice_last_only_on_a_sliced_pair():
    rows = results(HAND)
    assert [list(r) for r in rows] == [ROW_KEYS, ROW_KEYS, ROW_KEYS + ["slice"],
                                       ROW_KEYS + ["slice"], ROW_KEYS, ROW_KEYS]


def test_a_pair_with_a_none_side_is_left_out_so_rows_are_two_per_pair_m_counts():
    m = sum(p["routed_correct"] is not None and p["shadow_correct"] is not None for p in HAND)
    assert m == 3 and len(results(HAND)) == 2 * m
    assert results([pair("c4", True, None), pair("c5", None, False), pair("c6", None, None)]) == []


def test_no_pairs_give_no_rows_and_a_generator_is_read():
    assert results([]) == []
    assert results(p for p in HAND) == EXPECTED


def test_pairs_are_left_unchanged():
    before = [dict(p) for p in HAND]
    results(HAND)
    assert HAND == before


# --- what reads the rows ----------------------------------------------------------------

def test_calibrate_reads_the_rows_as_one_trial_per_labelled_side():
    stats = calibrate_from_results(results(HAND))
    assert isinstance(stats, Stats)
    assert stats.get("judge", CHEAP) == (2, 3)
    assert stats.get("judge", BEST) == (2, 3)
    assert stats.get("judge", MID) == (0, 0)  # c4's shadow side is None, so no row at all
    assert stats.get("judge@long", CHEAP) == (0, 1)


def test_item_outcomes_and_pair_outcomes_pair_the_routed_route_with_the_shadow_route(tmp_path):
    path = pair_file(tmp_path, HAND)
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    records = item_outcomes(results(load_records(path)), dataset_sha256=digest)
    current, challenger, got = pair_outcomes(records, task="judge", current=CHEAP,
                                             challenger=BEST)
    assert current == {"c0": True, "c2": False, "c8": True}
    assert challenger == {"c0": True, "c2": True, "c8": False}
    assert got == digest
    check = paired_promotion(current, challenger, margin=0.05, min_pairs=3)
    assert (check.pairs, check.unpaired, check.current_only, check.challenger_only) == (3, 0, 1, 1)
    assert check.decision == "hold"


# --- a real shadowed run ----------------------------------------------------------------

def answers(*texts):
    queue = list(texts)

    def complete(messages):
        if not queue:
            raise ProviderError("outage")
        return Completion(queue.pop(0), 1000, 200)
    return complete


def run(script, calls, validate=None):
    task = Task("judge", bar=0.7, min_samples=10, shadow_rate=1.0)
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (MID, (95, 100)),
                                          (BEST, (100, 100))):
        stats.add(task.name, model_id, successes, trials)
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000),
                         Model(BEST, "large", 10.0, 20.0, 8000)])
    monitor = Monitor()
    ids = iter(f"call-{i}" for i in range(1000))
    ticks = iter(float(i) for i in range(10_000))
    executor = Executor(Router(registry, {task.name: task}, stats), FakeProvider(script),
                        monitor=monitor, clock=lambda: next(ticks),
                        now=lambda: "2026-11-23T00:00:00Z", id_factory=lambda: next(ids),
                        random=lambda: 0.0)
    for _ in range(calls):
        executor.call("judge", MESSAGES, validate=validate)
    return monitor.records


def test_a_checked_run_gives_rows_for_its_ok_and_invalid_shadows_and_none_for_an_error():
    script = {CHEAP: answers("cheap", "cheap", "cheap"), BEST: answers("best", "bad")}
    records = run(script, 3, validate=lambda text: text != "bad")
    assert results(shadow_pairs(records, checked=True)) == [
        row(CHEAP, "call-0", True), row(BEST, "call-0", True),
        row(CHEAP, "call-2", True), row(BEST, "call-2", False)]  # call-4's shadow erred
    assert results(shadow_pairs(records)) == []  # unlabelled: no row, so no trial


# --- checks -----------------------------------------------------------------------------

@pytest.mark.parametrize("bad, message", [
    ("not a pair", "pair 2 must be a mapping"),
    ({**HAND[0], "pair_id": ""}, "pair 2: pair_id must be a non-empty string"),
    ({k: v for k, v in HAND[0].items() if k != "task"}, "pair 2: task must be a non-empty string"),
    ({**HAND[0], "routed_route": 3}, "pair 2: routed_route must be a non-empty string"),
    ({**HAND[0], "shadow_route": None}, "pair 2: shadow_route must be a non-empty string"),
    ({**HAND[0], "pair_id": "c9", "slice": "a@b"}, "pair 2: slice must be null or a non-empty string without '@'"),
    ({**HAND[0], "pair_id": "c9", "slice": ""}, "pair 2: slice must be null or a non-empty string without '@'"),
    ({**HAND[0], "pair_id": "c9", "task": "a@b", "slice": "long"},
     "pair 2: a sliced pair's task must hold no '@', got 'a@b'"),  # review iter-464 must-fix 1
    ({**HAND[0], "pair_id": "c9", "routed_correct": 1}, "pair 2: routed_correct must be true, false or null"),
    ({**HAND[0], "pair_id": "c9", "shadow_correct": "yes"}, "pair 2: shadow_correct must be true, false or null"),
    ({**HAND[0], "pair_id": "c9", "shadow_route": CHEAP}, "pair 2: routed_route and shadow_route are both"),
    ({**HAND[0], "pair_id": "c9", "routed_route": "cascade:fiction/cheap>fiction/mid"},
     "pair 2: routed_route 'cascade:fiction/cheap>fiction/mid' is a cascade's or a procedure's"),
    ({**HAND[0], "pair_id": "c9", "routed_route": "proc:triage@1"},
     "pair 2: routed_route 'proc:triage@1' is a cascade's or a procedure's"),
    ({**HAND[0], "pair_id": "c9", "shadow_route": "a/x>b/y"},
     "pair 2: shadow_route 'a/x>b/y' is a cascade's or a procedure's"),
    (HAND[0], "pair 2: pair_id 'c0' is also pair 1's"),
])
def test_a_bad_pair_raises_naming_its_position(bad, message):
    with pytest.raises(ValueError) as exc:
        results([HAND[0], bad])
    assert message in str(exc.value)


def test_a_variant_route_is_read_as_any_model_is():  # review iter-464 nit 1
    rows = results([pair("c0", True, False, routed=CHEAP + "@terse")])
    assert rows == [row(CHEAP + "@terse", "c0", True), row(BEST, "c0", False)]
    assert calibrate_from_results(rows).get("judge", CHEAP + "@terse") == (1, 1)


def test_a_pair_with_a_none_side_is_checked_too():
    with pytest.raises(ValueError, match="pair 1: routed_route and shadow_route are both"):
        results([pair("c0", None, None, routed=BEST)])
    with pytest.raises(ValueError, match="pair 2: pair_id 'c0' is also pair 1's"):
        results([pair("c0", None, None), pair("c0", None, None)])


def test_every_pair_is_checked_before_any_row():
    with pytest.raises(ValueError, match="pair 6: "):
        results(HAND + [{**HAND[0], "pair_id": "c9", "routed_correct": 0}])


# --- the API and the spec ---------------------------------------------------------------

def test_pair_results_is_exported_after_shadow_pairs():
    names = model_routing.__all__
    assert names[names.index("shadow_pairs") + 1] == "pair_results"
    assert model_routing.pair_results is model_routing.monitor.pair_results


def test_design_and_changelog_state_v1_613():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    section = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert section.count("- v1.613 `pair_results(pairs) -> list[dict]` (row CANARY1d, v1.610)") == 1
    assert "shadow_pairs (v1.610), pair_results (v1.613), audited_results (v1.632)\n" in design  # M1a
    assert "`pair_results` reads a labelled one as labeled results rows (v1.613, row CANARY1d)" \
        in section
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.613 (2026-11-23): spec, code and tests (8.3, row CANARY1d).") == 1
