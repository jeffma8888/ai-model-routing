"""The drift check judges a route's time too: `drift_check` and `drift` (DESIGN 8.3 v1.638 and 10,
row LAT3).

From v1.637 a window's stats hold each audited call's time, but `drift_check` judged successes
alone, so `drift` never said that a route's recent calls went over its task's `max_p95_ms`. A row of
a task that sets the bar now gives both sides' p95, as `select`'s rule 5e reads it (None until the key
holds `min_samples` times), and `latency_flag`: `went_over` when the all-time side is on time (its p95
at or under the bar, or none under `latency_unknown` "allow") and the window's p95 is over the bar,
`came_under` when the all-time side is not on time and the window's p95 is at or under the bar, kept
apart from `flag`. A row of a task with no bar keeps v1.633's keys, and `drift`'s table gains its
columns only when a row carries the bar, so with no bar every output keeps its bytes."""

import contextlib
import io
import json
from datetime import date
from math import ceil
from pathlib import Path

import pytest

import model_routing
from model_routing import Model, NoModelClearsBar, Registry, Router, Stats, Task
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
CHEAP, MID = "fiction/cheap", "fiction/mid"
V1_633_KEYS = ["task", "route", "all_time_successes", "all_time_trials", "all_time_lb",
               "window_successes", "window_trials", "window_lb", "bar", "min_samples", "confidence", "flag"]
LATENCY_KEYS = ["all_time_p95_ms", "window_p95_ms", "max_p95_ms", "latency_unknown", "latency_flag"]
BAR = 1000.0
TIMED = Task("judge", bar=0.8, min_samples=30, max_p95_ms=BAR)
DENY = Task("judge", bar=0.8, min_samples=30, max_p95_ms=BAR, latency_unknown="deny")


def drift(*args, **kwargs):
    return model_routing.drift_check(*args, **kwargs)


def timed(*entries):
    """Stats of `(task, model, successes, trials, times)`, `times` None for none."""
    out = Stats()
    for task, model, successes, trials, times in entries:
        out.add(task, model, successes, trials, latencies_ms=times)
    return out


def one(all_time, window, task=TIMED):
    [row] = drift(all_time, window, {task.name: task})
    return row


def side(ms, n=40, successes=None, model=CHEAP, task="judge"):
    """One key at `n` trials, all right unless `successes` says, each timed at `ms` (None: no times)."""
    return timed((task, model, n if successes is None else successes, n, None if ms is None else [ms] * n))


# --- the row ----------------------------------------------------------------------------

def test_a_row_of_a_task_with_a_bar_gains_both_p95s_the_bar_and_a_latency_flag_after_flag():
    row = one(side(800.0, 500), side(1500.0))
    assert list(row) == V1_633_KEYS + LATENCY_KEYS
    assert {k: row[k] for k in LATENCY_KEYS} == {
        "all_time_p95_ms": 800.0, "window_p95_ms": 1500.0, "max_p95_ms": BAR,
        "latency_unknown": "allow", "latency_flag": "went_over"}
    assert row["flag"] is None   # both sides' successes clear the bar


def test_a_row_of_a_task_with_no_bar_keeps_the_v1_633_keys_whatever_its_times():
    task = Task("judge", bar=0.8, min_samples=30)
    row = one(side(800.0, 500), side(1500.0), task)
    assert list(row) == V1_633_KEYS
    assert row == one(side(None, 500), side(None), task)


def test_the_bar_is_the_tasks_as_given():
    task = Task("judge", bar=0.8, min_samples=30, max_p95_ms=1000)
    row = one(side(800.0, 500), side(1500.0), task)
    assert row["max_p95_ms"] == 1000 and type(row["max_p95_ms"]) is int


# --- the flag ---------------------------------------------------------------------------

def test_800_ms_all_time_and_1500_ms_in_the_window_against_a_1000_ms_bar_went_over():
    assert one(side(800.0, 500), side(1500.0))["latency_flag"] == "went_over"


@pytest.mark.parametrize("all_time, window", [
    (800.0, 900.0),     # under the bar on both sides
    (1500.0, 1200.0),   # over it on both sides
    (1000.0, 1000.0),   # at it on both sides: a p95 at the bar is on time
])
def test_no_change_flags_nothing(all_time, window):
    assert one(side(all_time, 500), side(window))["latency_flag"] is None


def test_a_route_over_the_bar_all_time_and_under_it_in_the_window_came_under():
    assert one(side(1500.0, 500), side(800.0))["latency_flag"] == "came_under"
    assert one(side(1500.0, 500), side(BAR))["latency_flag"] == "came_under"   # at the bar is on time
    assert one(side(BAR, 500), side(BAR + 0.5))["latency_flag"] == "went_over"


def test_a_window_with_fewer_than_min_samples_times_has_no_p95_and_flags_nothing():
    window = timed(("judge", CHEAP, 40, 40, [1500.0] * 29))   # 40 trials, 29 of them timed
    row = one(side(800.0, 500), window)
    assert (row["window_p95_ms"], row["latency_flag"]) == (None, None)
    window = timed(("judge", CHEAP, 40, 40, [1500.0] * 30))
    row = one(side(800.0, 500), window)
    assert (row["window_p95_ms"], row["latency_flag"]) == (1500.0, "went_over")


def test_an_all_time_side_with_fewer_than_min_samples_times_has_no_p95():
    all_time = timed(("judge", CHEAP, 460, 500, [800.0] * 29))
    row = one(all_time, side(1500.0))
    assert (row["all_time_p95_ms"], row["latency_flag"]) == (None, "went_over")   # none is on time under allow


def test_under_allow_no_all_time_time_is_on_time():
    assert one(side(None, 500), side(1500.0))["latency_flag"] == "went_over"
    assert one(side(None, 500), side(800.0))["latency_flag"] is None


def test_under_deny_no_all_time_time_is_not_on_time():
    row = one(side(None, 500), side(800.0), DENY)
    assert (row["all_time_p95_ms"], row["window_p95_ms"], row["latency_unknown"], row["latency_flag"]) == (
        None, 800.0, "deny", "came_under")
    row = one(side(None, 500), side(1500.0), DENY)   # ruled out on both sides, its p95s say why
    assert (row["all_time_p95_ms"], row["window_p95_ms"], row["latency_flag"]) == (None, 1500.0, None)
    assert one(side(800.0, 500), side(1500.0), DENY)["latency_flag"] == "went_over"


def test_a_window_with_no_times_flags_nothing_under_either_choice():
    for task in (TIMED, DENY):
        for all_time in (800.0, 1500.0, None):
            row = one(side(all_time, 500), side(None), task)
            assert (row["window_p95_ms"], row["latency_flag"]) == (None, None), (task, all_time)


def test_the_p95_is_the_nearest_rank_one_stats_gives():
    times = [float(ms) for ms in range(1, 41)]
    row = one(side(800.0, 500), timed(("judge", CHEAP, 40, 40, list(reversed(times)))))
    assert row["window_p95_ms"] == times[ceil(0.95 * 40) - 1] == 38.0
    assert row["window_p95_ms"] == timed(("judge", CHEAP, 40, 40, times)).p95_latency_ms("judge", CHEAP)


def test_a_row_can_carry_both_flags():
    row = one(side(800.0, 500, successes=460), side(1500.0, 40, successes=28))
    assert (row["flag"], row["latency_flag"]) == ("fell_below", "went_over")
    row = one(side(1500.0, 500, successes=200), side(800.0, 40))
    assert (row["flag"], row["latency_flag"]) == ("rose_above", "came_under")


def test_the_success_flag_reads_no_time():
    for all_time, window in [(800.0, 1500.0), (1500.0, 800.0), (None, None)]:
        row = one(side(all_time, 500, successes=460), side(window, 40, successes=28))
        assert row["flag"] == "fell_below"


def reason(on_stats, task):
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000)])
    try:
        candidates = Router(registry, {"judge": task}, on_stats).select("judge").candidates
    except NoModelClearsBar as caught:
        candidates = caught.candidates
    [cheap] = [c for c in candidates if c.model_id == CHEAP]
    return cheap.reason


@pytest.mark.parametrize("task", [TIMED, DENY])
def test_the_latency_flag_agrees_with_select_on_both_sides(task):
    cases = [(800.0, 1500.0), (1500.0, 800.0), (800.0, 900.0), (1500.0, 1200.0), (None, 1500.0),
             (None, 800.0), (800.0, None), (BAR, BAR), (1500.0, BAR)]
    for all_time, window in cases:
        a, w = side(all_time, 500), side(window, 40)
        row = one(a, w, task)
        on_time = [reason(s, task) not in ("too_slow", "latency_unknown") for s in (a, w)]
        want = {(True, False): "went_over", (False, True): "came_under"}.get(tuple(on_time))
        if row["window_p95_ms"] is None:
            want = None
        assert row["latency_flag"] == want, (task.latency_unknown, all_time, window)


# --- which keys -------------------------------------------------------------------------

def test_a_slice_key_takes_the_tasks_bar_and_the_slices_min_samples():
    task = Task("judge", bar=0.8, min_samples=30, max_p95_ms=BAR, slices={"long": {"min_samples": 10}})
    all_time = timed(("judge", CHEAP, 460, 500, [800.0] * 500), ("judge@long", CHEAP, 460, 500, [800.0] * 500))
    window = timed(("judge", CHEAP, 10, 10, [1500.0] * 10), ("judge@long", CHEAP, 10, 10, [1500.0] * 10))
    rows = drift(all_time, window, {"judge": task})
    assert [(r["task"], r["min_samples"], r["window_p95_ms"], r["max_p95_ms"], r["latency_flag"]) for r in rows] == [
        ("judge", 30, None, BAR, None), ("judge@long", 10, 1500.0, BAR, "went_over")]


def test_rows_of_a_task_with_a_bar_and_one_without_each_keep_their_own_keys():
    plain = Task("plain", bar=0.8, min_samples=30)
    all_time = timed(("judge", CHEAP, 460, 500, [800.0] * 500), ("plain", CHEAP, 460, 500, [800.0] * 500))
    window = timed(("judge", CHEAP, 40, 40, [1500.0] * 40), ("plain", CHEAP, 40, 40, [1500.0] * 40))
    rows = drift(all_time, window, {"judge": TIMED, "plain": plain})
    assert [r["task"] for r in rows] == ["judge", "plain"]
    assert list(rows[0]) == V1_633_KEYS + LATENCY_KEYS and list(rows[1]) == V1_633_KEYS


def test_a_cascade_key_is_judged_on_its_own_times():
    cascade = f"{CHEAP}>{MID}@low-confidence"
    a, w = Stats(), Stats()
    a.add("judge", cascade, 460, 500, escalated=50, latencies_ms=[800.0] * 500)
    w.add("judge", cascade, 40, 40, escalated=4, latencies_ms=[1500.0] * 40)
    [row] = drift(a, w, {"judge": TIMED})
    assert (row["route"], row["latency_flag"]) == (cascade, "went_over")


# --- the command ------------------------------------------------------------------------

TODAY = date(2026, 11, 24)
SINCE, UNTIL = "2026-10-26T00:00:00+00:00", "2026-11-25T00:00:00+00:00"
OLD, NEW = "2026-10-01T12:00:00.000+00:00", "2026-11-20T12:00:00.000+00:00"


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, today=TODAY)
    return code, out.getvalue(), err.getvalue()


def rec(call_id, model, ts, latency, task="judge"):
    return {"ts": ts, "call_id": call_id, "task": task, "flavor": "cost_effective", "model": model,
            "family": model.split("/")[0], "attempt": 0, "final": True, "outcome": "ok", "error": None,
            "latency_ms": latency, "input_tokens": 1000, "output_tokens": 200, "cost_usd": 0.001,
            "routing_cost_usd": 0.001, "below_bar": False, "basis": "measured", "tags": {}, "slice": None}


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")


def write_tasks(path, *tasks):
    path.write_text(json.dumps({"tasks": [{"bar": 0.8, "min_samples": 30, "expected_input_tokens": 1000,
                                           "expected_output_tokens": 200, **t} for t in tasks]}), encoding="utf-8")


@pytest.fixture
def files(tmp_path):
    """In the window the cheap route's 40 calls take 1.5 s and the mid route's 40 take 0.8 s, all right;
    stats.json has the cheap route at 460/500 timed at 0.8 s and the mid one at 470/500 timed at 1.5 s."""
    stats = Stats()
    stats.add("judge", CHEAP, 460, 500, latencies_ms=[800.0] * 500)
    stats.add("judge", MID, 470, 500, latencies_ms=[1500.0] * 500)
    stats.save(tmp_path / "stats.json")
    records = ([rec(f"c{k}", CHEAP, NEW, 1500.0) for k in range(40)]
               + [rec(f"m{k}", MID, NEW, 800.0) for k in range(40)] + [rec("p0", CHEAP, NEW, 5.0, task="plain")])
    write_jsonl(tmp_path / "calls.jsonl", records)
    write_jsonl(tmp_path / "untimed.jsonl", [{k: v for k, v in r.items() if k != "latency_ms"} for r in records])
    write_jsonl(tmp_path / "audits.jsonl", [{"call_id": r["call_id"], "correct": True} for r in records])
    write_tasks(tmp_path / "bar.json", {"name": "judge", "max_p95_ms": 1000})
    write_tasks(tmp_path / "both.json", {"name": "judge", "max_p95_ms": 1000}, {"name": "plain"})
    write_tasks(tmp_path / "none.json", {"name": "judge"}, {"name": "plain"})
    return tmp_path


def drift_argv(d, tasks, *extra, log="calls.jsonl", stats=True):
    return (["drift", "--log", str(d / log), "--audits", str(d / "audits.jsonl"), "--tasks", str(d / tasks)]
            + (["--stats", str(d / "stats.json")] if stats else []) + list(extra))


def test_drift_json_with_a_bar_is_drift_check_on_the_stats_file_and_the_windows_stats(files):
    code, out, err = run(drift_argv(files, "bar.json", "--json"))
    assert (code, err) == (0, "")
    rows = json.loads(out)["rows"]
    assert [(r["route"], r["all_time_p95_ms"], r["window_p95_ms"], r["max_p95_ms"], r["latency_flag"])
            for r in rows] == [(CHEAP, 800.0, 1500.0, 1000, "went_over"), (MID, 1500.0, 800.0, 1000, "came_under")]
    assert all(list(r) == V1_633_KEYS + LATENCY_KEYS for r in rows)


def test_the_text_output_with_a_bar_byte_for_byte(files):
    code, out, err = run(drift_argv(files, "both.json"))
    assert (code, err) == (0, "")
    head, table = out.split("\n\n")
    assert head == f"since:    {SINCE}\nuntil:    {UNTIL}\nall_time: {files / 'stats.json'}"
    assert table.splitlines() == [
        "task   route          all_time  all_time_lb  window  window_lb  bar  min_samples  flag  all_time_p95_ms  "
        "window_p95_ms  max_p95_ms  latency_flag",
        "-----  -------------  --------  -----------  ------  ---------  ---  -----------  ----  ---------------  "
        "-------------  ----------  ------------",
        "judge  fiction/cheap  460/500   0.893        40/40   0.912      0.8  30           -     800.0            "
        "1500.0         1000        went_over",
        "judge  fiction/mid    470/500   0.916        40/40   0.912      0.8  30           -     1500.0           "
        "800.0          1000        came_under",
        "plain  fiction/cheap  0/0       0.000        1/1     0.207      0.8  30           -     -                "
        "-              -           -",
    ]
    assert out.endswith("-\n")


@pytest.mark.parametrize("extra, stats", [((), True), (("--json",), True), ((), False), (("--json",), False)])
def test_with_no_bar_drift_prints_what_it_prints_on_the_log_with_no_times(files, extra, stats):
    timed_out = run(drift_argv(files, "none.json", *extra, stats=stats))
    untimed_out = run(drift_argv(files, "none.json", *extra, log="untimed.jsonl", stats=stats))
    assert timed_out[0] == 0 and timed_out[1]
    assert timed_out == untimed_out   # with no bar no time is read, so the logs' times change nothing
    assert "p95" not in timed_out[1] and "latency_flag" not in timed_out[1]


def test_with_no_bar_the_table_keeps_the_v1_634_columns(files):
    code, out, err = run(drift_argv(files, "none.json"))
    assert (code, err) == (0, "")
    assert out.split("\n\n")[1].splitlines() == [
        "task   route          all_time  all_time_lb  window  window_lb  bar  min_samples  flag",
        "-----  -------------  --------  -----------  ------  ---------  ---  -----------  ----",
        "judge  fiction/cheap  460/500   0.893        40/40   0.912      0.8  30           -",
        "judge  fiction/mid    470/500   0.916        40/40   0.912      0.8  30           -",
        "plain  fiction/cheap  0/0       0.000        1/1     0.207      0.8  30           -",
    ]


def test_drift_writes_no_file_with_a_bar(files):
    before = sorted(p.name for p in files.iterdir())
    assert run(drift_argv(files, "bar.json"))[0] == 0
    assert sorted(p.name for p in files.iterdir()) == before


# --- the spec and the docs --------------------------------------------------------------

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_design_and_the_changelog_state_v1_638():
    design = read("DESIGN.md")
    eight3 = design[design.index("\n### 8.3 "):design.index("\n## 9. ")]
    assert eight3.count("\n- v1.638 `drift_check` judges each row's time against its task's latency bar (row LAT3, "
                        "v1.633, v1.637, 4.2 v1.628, 5.2 v1.628, 10 v1.634): ") == 1
    assert eight3.index("\n- v1.637 `audited_results`") < eight3.index("\n- v1.638 `drift_check`")
    assert eight3.count("From v1.638 (row LAT3) a row of a task with a latency bar also gives `latency_flag`, "
                        "which reads rules 5e and 5f alone.") == 1
    assert eight3.count("a latency flag in `drift_check` and `drift` (row LAT3, which v1.638 adds)") == 1
    for key in LATENCY_KEYS:
        assert f"`{key}`" in eight3[eight3.index("\n- v1.638 `drift_check`"):]
    ten = design[design.index("\n## 10. "):design.index("\n## 11. ")]
    assert ten.count("From 8.3 v1.638 (row LAT3), when any row carries `max_p95_ms`, the table gains, after `flag`, "
                     "the columns `all_time_p95_ms`, `window_p95_ms` and `max_p95_ms`") == 1
    assert ten.count("when no row carries it, the table keeps v1.634's nine columns and its bytes") == 1
    assert "otherwise it keeps these columns" not in ten   # review iter-492 must-fix 1
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.638 (")]
    assert line.startswith("- v1.638 (2026-11-25): spec, code and tests (8.3, 10, row LAT3). ")
    assert len(line.encode("utf-8")) <= 600
    assert design.splitlines()[2].startswith("Status: v1.638, 2026-11-25 (v1.638, spec, code and tests: ")


def test_the_readme_drift_paragraph_names_the_latency_flag_after_the_window_times_sentence():
    text = read("README.md")
    sentence = (" On such a task each `drift` row also gives both sides' p95 and a `latency_flag`, kept apart from "
                "the success flag: `went_over` when the window's p95, over at least `min_samples` timed calls, is "
                "over the bar while the all-time side keeps the route in, `came_under` the other way.")
    assert text.count(sentence) == 1
    assert text.count("holds each route to the bar on the window's times." + sentence + " GitHub runs its tests") == 1
