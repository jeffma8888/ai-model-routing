"""The drift comparison: `drift_check` (DESIGN 8.3 v1.633, row M1b, the second part of row M1's
drift check).

Each (task, route) key of the all-time and a recent window's `Stats` is judged against its task's
bar: `fell_below` when the all-time counts clear it and the window's, with at least `min_samples`
trials, do not; `rose_above` when the all-time counts do not and the window's do; None otherwise,
so a window under `min_samples` trials flags nothing and a key is flagged at most once."""

import copy
from pathlib import Path

import pytest

import model_routing
from model_routing import Model, NoModelClearsBar, Registry, Router, Stats, Task, wilson_lower_bound
from model_routing.stats import calibrate_from_results

ROOT = Path(__file__).resolve().parents[1]
CHEAP, MID = "fiction/cheap", "fiction/mid"
OLD, NEW = "2026-10-01T00:00:00.000+00:00", "2026-11-20T00:00:00.000+00:00"
JUDGE = Task("judge", bar=0.8, min_samples=30)
TASKS = {"judge": JUDGE}
KEYS = ["task", "route", "all_time_successes", "all_time_trials", "all_time_lb",
        "window_successes", "window_trials", "window_lb", "bar", "min_samples", "confidence", "flag"]


def drift(*args, **kwargs):
    return model_routing.drift_check(*args, **kwargs)


def stats(*entries):
    out = Stats()
    for task, model, successes, trials in entries:
        out.add(task, model, successes, trials)
    return out


def one(all_time, window, tasks=TASKS):
    [row] = drift(all_time, window, tasks)
    return row


def rec(call_id, model, ts):
    return {"ts": ts, "call_id": call_id, "task": "judge", "flavor": "cost_effective",
            "model": model, "family": model.split("/")[0], "attempt": 0, "final": True,
            "outcome": "ok", "error": None, "latency_ms": 5.0, "input_tokens": 1000,
            "output_tokens": 200, "cost_usd": 0.001, "routing_cost_usd": 0.001,
            "below_bar": False, "basis": "measured", "tags": {}, "slice": None}


def router(on_stats):
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000)])
    return Router(registry, TASKS, on_stats)


# --- the row ----------------------------------------------------------------------------

def test_a_row_has_both_counts_both_bounds_the_bar_and_a_flag_in_order():
    row = one(stats(("judge", CHEAP, 460, 500)), stats(("judge", CHEAP, 28, 40)))
    assert list(row) == KEYS
    assert row == {"task": "judge", "route": CHEAP,
                   "all_time_successes": 460, "all_time_trials": 500,
                   "all_time_lb": wilson_lower_bound(460, 500, 0.95),
                   "window_successes": 28, "window_trials": 40,
                   "window_lb": wilson_lower_bound(28, 40, 0.95),
                   "bar": 0.8, "min_samples": 30, "confidence": 0.95, "flag": "fell_below"}
    assert round(row["all_time_lb"], 4) == 0.8929 and round(row["window_lb"], 4) == 0.5457


def test_the_bounds_are_at_the_tasks_confidence():
    task = Task("judge", bar=0.8, min_samples=30, confidence=0.8)
    row = one(stats(("judge", CHEAP, 460, 500)), stats(("judge", CHEAP, 28, 40)), {"judge": task})
    assert row["confidence"] == 0.8
    assert row["all_time_lb"] == wilson_lower_bound(460, 500, 0.8)
    assert row["window_lb"] == wilson_lower_bound(28, 40, 0.8)
    assert row["window_lb"] > wilson_lower_bound(28, 40, 0.95)


# --- the flag ---------------------------------------------------------------------------

def test_a_route_at_0_92_all_time_and_0_70_in_the_window_is_flagged_fell_below():
    log, audits = [], {}
    for i in range(500):   # 460 of 500 right all-time, 28 of the last 40 in November
        recent = i >= 460
        call_id = f"cheap-{i}"
        log.append(rec(call_id, CHEAP, NEW if recent else OLD))
        audits[call_id] = (i - 460 < 28) if recent else (i < 432)
    all_time = calibrate_from_results(model_routing.audited_results(log, audits))
    window = calibrate_from_results(
        model_routing.audited_results(log, audits, since="2026-11-01T00:00:00Z"))
    assert all_time.get("judge", CHEAP) == (460, 500) and window.get("judge", CHEAP) == (28, 40)
    row = one(all_time, window)
    assert (row["route"], row["flag"]) == (CHEAP, "fell_below")
    assert router(all_time).select("judge").primary == CHEAP   # select admits it all-time
    with pytest.raises(NoModelClearsBar) as caught:              # and not on the window
        router(window).select("judge")
    [cheap] = [c for c in caught.value.candidates if c.model_id == CHEAP]
    assert cheap.reason == "below_bar"


def test_a_rise_is_flagged_once():
    all_time = stats(("judge", CHEAP, 460, 500), ("judge", MID, 20, 40))
    window = stats(("judge", CHEAP, 40, 40), ("judge", MID, 40, 40))
    rows = drift(all_time, window, TASKS)
    assert [(r["route"], r["flag"]) for r in rows] == [(CHEAP, None), (MID, "rose_above")]
    assert sum(r["flag"] == "rose_above" for r in rows) == 1
    assert round(rows[1]["window_lb"], 4) == 0.9124 and rows[1]["all_time_lb"] < 0.8


def test_a_route_under_min_samples_all_time_that_clears_in_the_window_rose_above():
    row = one(stats(("judge", MID, 10, 10)), stats(("judge", MID, 40, 40)))
    assert row["flag"] == "rose_above"


def test_a_window_under_min_samples_flags_nothing():
    assert one(stats(("judge", CHEAP, 460, 500)), stats(("judge", CHEAP, 0, 29)))["flag"] is None
    assert one(stats(("judge", MID, 20, 40)), stats(("judge", MID, 29, 29)))["flag"] is None
    assert wilson_lower_bound(29, 29) > 0.8   # it would clear the bar with one more trial
    assert one(stats(("judge", MID, 20, 40)), stats(("judge", MID, 30, 30)))["flag"] == "rose_above"


@pytest.mark.parametrize("all_time, window", [
    ((460, 500), (40, 40)),   # both clear
    ((20, 40), (28, 40)),     # both below
    ((10, 10), (28, 40)),     # under min_samples all-time, below in the window
    ((0, 0), (0, 0)),         # nothing on either side
])
def test_no_change_flags_nothing(all_time, window):
    assert one(stats(("judge", CHEAP, *all_time)), stats(("judge", CHEAP, *window)))["flag"] is None


def test_a_bound_at_the_bar_clears_it():
    bar = wilson_lower_bound(36, 40)
    task = Task("judge", bar=bar, min_samples=30)
    row = one(stats(("judge", CHEAP, 36, 40)), stats(("judge", CHEAP, 35, 40)), {"judge": task})
    assert row["all_time_lb"] == bar and row["flag"] == "fell_below"
    row = one(stats(("judge", CHEAP, 35, 40)), stats(("judge", CHEAP, 36, 40)), {"judge": task})
    assert row["flag"] == "rose_above"


def test_the_flag_agrees_with_select_on_both_sides():
    cases = [((460, 500), (28, 40)), ((20, 40), (40, 40)), ((10, 10), (40, 40)), ((460, 500), (0, 29))]
    for all_time, window in cases:
        a, w = stats(("judge", CHEAP, *all_time)), stats(("judge", CHEAP, *window))
        row = one(a, w)
        clears = []
        for side in (a, w):
            try:
                clears.append(router(side).select("judge").primary == CHEAP)
            except NoModelClearsBar:
                clears.append(False)
        want = {(True, False): "fell_below", (False, True): "rose_above"}.get(tuple(clears))
        if row["window_trials"] < 30:
            want = None
        assert row["flag"] == want, (all_time, window)


# --- which keys -------------------------------------------------------------------------

def test_one_row_per_key_of_either_stats_in_sorted_order():
    all_time = stats(("judge", MID, 460, 500), ("judge", CHEAP, 460, 500))
    window = stats(("judge", "fiction/new", 40, 40), ("judge", CHEAP, 28, 40))
    rows = drift(all_time, window, TASKS)
    assert [(r["task"], r["route"]) for r in rows] == [
        ("judge", CHEAP), ("judge", MID), ("judge", "fiction/new")]
    mid, new = rows[1], rows[2]
    assert (mid["window_successes"], mid["window_trials"], mid["window_lb"], mid["flag"]) == (0, 0, 0.0, None)
    assert (new["all_time_successes"], new["all_time_trials"], new["all_time_lb"]) == (0, 0, 0.0)
    assert new["flag"] == "rose_above"


def test_a_slice_key_is_judged_on_the_slices_bar_and_min_samples():
    task = Task("judge", bar=0.8, min_samples=30, slices={"long": {"bar": 0.5, "min_samples": 10}})
    rows = drift(stats(("judge", CHEAP, 20, 40), ("judge@long", CHEAP, 20, 40)),
                 stats(("judge", CHEAP, 10, 10), ("judge@long", CHEAP, 10, 10)), {"judge": task})
    assert [(r["task"], r["bar"], r["min_samples"], r["flag"]) for r in rows] == [
        ("judge", 0.8, 30, None), ("judge@long", 0.5, 10, "rose_above")]


def test_a_slice_the_task_does_not_declare_takes_the_tasks_bar():
    rows = drift(stats(("judge@short", CHEAP, 460, 500)), stats(("judge@short", CHEAP, 28, 40)), TASKS)
    assert [(r["task"], r["bar"], r["min_samples"], r["flag"]) for r in rows] == [
        ("judge@short", 0.8, 30, "fell_below")]


def test_a_key_that_names_a_task_is_judged_on_that_task():
    tasks = {"judge": JUDGE, "judge@long": Task("judge@long", bar=0.5, min_samples=10)}
    row = one(stats(("judge@long", CHEAP, 20, 40)), stats(("judge@long", CHEAP, 10, 10)), tasks)
    assert (row["bar"], row["min_samples"], row["flag"]) == (0.5, 10, "rose_above")


def test_a_key_of_a_task_not_given_gives_no_row():
    all_time = stats(("other", CHEAP, 460, 500), ("other@long", CHEAP, 460, 500),
                     ("judge@a@b", CHEAP, 460, 500), ("judge", CHEAP, 460, 500))
    window = stats(("other", CHEAP, 28, 40), ("judge", CHEAP, 28, 40))
    assert [(r["task"], r["flag"]) for r in drift(all_time, window, TASKS)] == [("judge", "fell_below")]


def test_no_stats_give_no_rows():
    assert drift(Stats(), Stats(), TASKS) == []
    assert drift(stats(("judge", CHEAP, 1, 1)), Stats(), {}) == []


def test_a_cascade_or_procedure_key_is_judged_like_any_other():
    cascade = f"{CHEAP}>{MID}@low-confidence"
    PROC = f"proc:extract@v1+{CHEAP}"
    a, w = Stats(), Stats()
    a.add("judge", cascade, 460, 500, escalated=50)
    w.add("judge", cascade, 28, 40, escalated=4)
    a.add("judge", PROC, 20, 40, cost_usd=0.4)
    w.add("judge", PROC, 40, 40, cost_usd=0.4)
    rows = drift(a, w, TASKS)
    assert [(r["route"], r["flag"]) for r in rows] == [
        (cascade, "fell_below"), (PROC, "rose_above")]


def test_neither_stats_nor_tasks_is_changed():
    all_time, window = stats(("judge", CHEAP, 460, 500)), stats(("judge", CHEAP, 28, 40))
    tasks = {"judge": JUDGE}
    before = (list(all_time.items()), list(window.items()), copy.copy(tasks))
    drift(all_time, window, tasks)
    assert (list(all_time.items()), list(window.items()), tasks) == before


# --- checks -----------------------------------------------------------------------------

@pytest.mark.parametrize("args, message", [
    (({"stats": []}, Stats(), TASKS), "all_time must be a Stats"),
    ((Stats(), None, TASKS), "window must be a Stats"),
    ((Stats(), Stats(), [JUDGE]), "tasks must be a mapping"),
    ((Stats(), Stats(), {"judge": {"bar": 0.8}}), "must be a Task"),
    ((Stats(), Stats(), {"other": JUDGE}), "is not its task's name"),
])
def test_a_bad_input_raises(args, message):
    with pytest.raises(ValueError, match=message):
        drift(*args)


def test_a_check_comes_before_any_row():
    with pytest.raises(ValueError, match="is not its task's name"):
        drift(stats(("judge", CHEAP, 460, 500)), stats(("judge", CHEAP, 28, 40)),
              {"judge": JUDGE, "x": Task("y", bar=0.5)})


# --- the API and the spec ---------------------------------------------------------------

def test_drift_check_is_exported_after_audited_results():
    names = model_routing.__all__
    assert names[names.index("audited_results") + 1] == "drift_check"
    assert model_routing.drift_check is model_routing.monitor.drift_check


def test_design_and_changelog_state_v1_633():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    section = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert section.count("- v1.633 `drift_check(all_time, window, tasks) -> list[dict]` (row M1b)") == 1
    assert "is row M1b, which v1.633 adds as `drift_check`, and the `drift` command" in section
    assert "audited_results (v1.632), drift_check (v1.633)\n" in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.633 (2026-11-24): spec, code and tests (3, 8.3, row M1b).") == 1
