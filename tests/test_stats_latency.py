"""DESIGN 4.3 v1.626 (row LAT1a): measured latency in `Stats`.

Beside its counts, `Stats` keeps the time in milliseconds of each timed trial per
`(task, model_id)`: `.add(..., latencies_ms=[...])`, a calibration row's `latency_ms`, and a
stats file's `latencies_ms` array, the row's last key, written only for a key that holds a
time. `.latencies` returns them sorted and `.p95_latency_ms` gives their 95th percentile by
`report`'s nearest-rank rule (8.3), `None` when none is recorded. No rule reads the times yet
(rows LAT1b and LAT1c), so a stats or results file without them keeps its v1.625 bytes.
"""

import json
from pathlib import Path

import pytest

from model_routing import Stats, calibrate_from_results
from model_routing.cli import main
from model_routing.monitor import report
from model_routing.stats import item_outcomes

ROOT = Path(__file__).resolve().parents[1]
CASCADE = "fiction/cheap>fiction/strong"
PROC = "proc:triage@1"


def _report_p95(values):
    records = [{"call_id": f"c{i}", "task": "t", "model": "m", "attempt": 0, "final": True,
                "outcome": "ok", "latency_ms": v, "input_tokens": 0, "output_tokens": 0,
                "cost_usd": 0.0} for i, v in enumerate(values)]
    return report(records)[0]["p95_latency_ms"]


def test_nothing_is_recorded_until_a_time_is_given():
    stats = Stats()
    assert stats.latencies("t", "m") == ()
    assert stats.p95_latency_ms("t", "m") is None
    stats.add("t", "m", 3, 4)
    assert stats.latencies("t", "m") == ()
    assert stats.p95_latency_ms("t", "m") is None


def test_times_accumulate_sorted_as_floats():
    stats = Stats()
    stats.add("t", "m", 2, 3, latencies_ms=[300, 120.5])
    stats.add("t", "m", 1, 1, latencies_ms=(80,))
    assert stats.latencies("t", "m") == (80.0, 120.5, 300.0)
    assert all(type(v) is float for v in stats.latencies("t", "m"))
    assert stats.get("t", "m") == (3, 4)
    assert stats.latencies("t", "other") == ()


@pytest.mark.parametrize("n, expected", [
    (1, 7.0), (2, 2.0), (10, 10.0), (19, 19.0), (20, 19.0), (21, 20.0), (40, 38.0),
    (100, 95.0), (101, 96.0),
])
def test_the_p95_is_reports_nearest_rank(n, expected):
    values = [7.0] if n == 1 else [float(v) for v in range(n, 0, -1)]
    stats = Stats()
    stats.add("t", "m", n, n, latencies_ms=values)
    assert stats.p95_latency_ms("t", "m") == expected
    assert stats.p95_latency_ms("t", "m") == _report_p95(values)


def test_below_twenty_trials_the_p95_is_the_slowest():
    stats = Stats()
    stats.add("t", "m", 19, 19, latencies_ms=[100.0] * 18 + [9000.0])
    assert stats.p95_latency_ms("t", "m") == 9000.0
    stats.add("t", "m", 1, 1, latencies_ms=[100.0])
    assert stats.p95_latency_ms("t", "m") == 100.0  # 20 times: the second slowest


@pytest.mark.parametrize("bad", [
    [], [-1], [float("nan")], [float("inf")], [True], ["5"], [None], "12", 12, {"a": 1},
    [10 ** 400], [1.0, 2.0, 3.0],
])
def test_a_bad_time_raises_and_adds_nothing(bad):
    stats = Stats()
    with pytest.raises(ValueError, match="latencies_ms"):
        stats.add("t", "m", 1, 2, latencies_ms=bad)
    assert stats.get("t", "m") == (0, 0)
    assert stats.latencies("t", "m") == ()


def test_a_time_needs_a_trial():
    stats = Stats()
    with pytest.raises(ValueError, match="latencies_ms"):
        stats.add("t", "m", 0, 0, latencies_ms=[5.0])
    assert stats.get("t", "m") == (0, 0)


def test_a_bad_time_beside_good_tokens_adds_nothing():
    stats = Stats()
    with pytest.raises(ValueError, match="latencies_ms"):
        stats.add("t", "m", 1, 1, input_tokens=10, output_tokens=5, latencies_ms=[-2])
    assert stats.get("t", "m") == (0, 0)
    assert stats.tokens("t", "m") == (0, 0, 0)


def test_a_cascade_and_a_procedure_key_hold_times():
    stats = Stats()
    stats.add("t", CASCADE, 1, 2, escalated=1, latencies_ms=[400.0, 1500.0])
    stats.add("t", PROC, 1, 1, cost_usd=0.002, latencies_ms=[900.0])
    assert stats.latencies("t", CASCADE) == (400.0, 1500.0)
    assert stats.p95_latency_ms("t", CASCADE) == 1500.0
    assert stats.latencies("t", PROC) == (900.0,)


def test_merge_joins_both_sides_and_changes_neither():
    a, b = Stats(), Stats()
    a.add("t", "m", 1, 2, latencies_ms=[50.0, 10.0])
    b.add("t", "m", 1, 1, latencies_ms=[30.0])
    b.add("t", "n", 1, 1, latencies_ms=[5.0])
    merged = a.merge(b)
    assert merged.latencies("t", "m") == (10.0, 30.0, 50.0)
    assert merged.latencies("t", "n") == (5.0,)
    assert merged.get("t", "m") == (2, 3)
    assert a.latencies("t", "m") == (10.0, 50.0)
    assert b.latencies("t", "m") == (30.0,)


def test_save_writes_the_times_last_and_sorted_and_loads_back(tmp_path):
    stats = Stats()
    stats.add("t", "m", 2, 3, input_tokens=30, output_tokens=6, cached_input_tokens=9,
              latencies_ms=[300.0, 120])
    stats.add("t", CASCADE, 1, 1, escalated=0, latencies_ms=[700])
    stats.add("t", "untimed", 1, 1)
    path = tmp_path / "stats.json"
    stats.save(path)
    rows = {row["model"]: row for row in json.loads(path.read_text(encoding="utf-8"))["stats"]}
    assert list(rows["m"]) == ["task", "model", "successes", "trials", "input_tokens",
                               "output_tokens", "token_trials", "cached_input_tokens",
                               "cached_trials", "latencies_ms"]
    assert rows["m"]["latencies_ms"] == [120.0, 300.0]
    assert list(rows[CASCADE])[-1] == "latencies_ms"
    assert "latencies_ms" not in rows["untimed"]
    loaded = Stats.load(path)
    assert loaded.latencies("t", "m") == (120.0, 300.0)
    assert loaded.latencies("t", CASCADE) == (700.0,)
    again = tmp_path / "again.json"
    loaded.save(again)
    assert again.read_bytes() == path.read_bytes()


def test_a_stats_file_without_times_keeps_its_bytes(tmp_path):
    stats = Stats()
    stats.add("t", "m", 2, 3, input_tokens=30, output_tokens=6)
    stats.add("t", PROC, 1, 1, cost_usd=0.5)
    path = tmp_path / "stats.json"
    stats.save(path)
    expected = {"stats": [
        {"task": "t", "model": "m", "successes": 2, "trials": 3, "input_tokens": 30,
         "output_tokens": 6, "token_trials": 3},
        {"task": "t", "model": PROC, "successes": 1, "trials": 1, "cost_usd": 0.5},
    ]}
    assert path.read_text(encoding="utf-8") == json.dumps(expected, indent=2) + "\n"


@pytest.mark.parametrize("bad", [None, 5, "120", [], [True], [-1], ["a"], [1, 2, 3]])
def test_a_bad_file_row_raises_naming_the_file(tmp_path, bad):
    path = tmp_path / "stats.json"
    row = {"task": "t", "model": "m", "successes": 1, "trials": 2, "latencies_ms": bad}
    path.write_text(json.dumps({"stats": [row]}), encoding="utf-8")
    with pytest.raises(ValueError, match="stats.json"):
        Stats.load(path)


def test_calibration_reads_one_time_per_row_under_both_slice_keys():
    rows = [
        {"task": "t", "model": "m", "correct": True, "latency_ms": 200},
        {"task": "t", "model": "m", "correct": False, "latency_ms": 900.5, "slice": "deep"},
        {"task": "t", "model": "m", "correct": True},
        {"task": "t", "model": CASCADE, "correct": True, "escalated": True, "latency_ms": 1200},
        {"task": "t", "model": PROC, "correct": True, "cost_usd": 0.0, "latency_ms": 40},
    ]
    stats = calibrate_from_results(rows)
    assert stats.get("t", "m") == (2, 3)
    assert stats.latencies("t", "m") == (200.0, 900.5)
    assert stats.latencies("t@deep", "m") == (900.5,)
    assert stats.latencies("t", CASCADE) == (1200.0,)
    assert stats.latencies("t", PROC) == (40.0,)


@pytest.mark.parametrize("bad", [None, True, "200", -1, float("nan"), [200]])
def test_a_bad_row_time_raises(bad):
    rows = [{"task": "t", "model": "m", "correct": True, "latency_ms": 10},
            {"task": "t", "model": "m", "correct": True, "latency_ms": bad}]
    with pytest.raises(ValueError, match="latency_ms"):
        calibrate_from_results(rows)
    with pytest.raises(ValueError, match="latency_ms"):
        item_outcomes([dict(row, item=f"i{n}") for n, row in enumerate(rows)],
                      dataset_sha256="0" * 64)


def test_item_outcomes_records_gain_no_key():
    rows = [{"task": "t", "model": "m", "item": "i1", "correct": True, "latency_ms": 10}]
    record = item_outcomes(rows, dataset_sha256="0" * 64)[0]
    assert list(record) == ["task", "slice", "route", "item", "correct", "dataset_sha256"]


def test_results_without_times_give_the_same_stats():
    rows = [{"task": "t", "model": "m", "correct": n % 3 != 0, "input_tokens": 10 + n,
             "output_tokens": 2} for n in range(9)]
    timed = [dict(row, latency_ms=float(n)) for n, row in enumerate(rows)]
    plain, with_times = calibrate_from_results(rows), calibrate_from_results(timed)
    assert plain.items() == with_times.items()
    assert plain.tokens("t", "m") == with_times.tokens("t", "m")
    assert plain.latencies("t", "m") == ()
    assert with_times.latencies("t", "m") == tuple(float(n) for n in range(9))


def test_calibrate_writes_the_times_and_prints_the_same_table(tmp_path, capsys):
    rows = [{"task": "t", "model": "m", "correct": True, "latency_ms": 150},
            {"task": "t", "model": "m", "correct": False}]
    timed, plain = tmp_path / "timed.jsonl", tmp_path / "plain.jsonl"
    timed.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    plain.write_text("".join(json.dumps({k: v for k, v in r.items() if k != "latency_ms"}) + "\n"
                             for r in rows), encoding="utf-8")
    outputs = []
    for name, results in (("a", timed), ("b", plain)):
        stats_path = tmp_path / f"{name}.json"
        assert main(["calibrate", "--results", str(results), "--stats", str(stats_path)]) == 0
        outputs.append(capsys.readouterr().out.replace(str(stats_path), "STATS"))
    assert outputs[0] == outputs[1]
    assert Stats.load(tmp_path / "a.json").latencies("t", "m") == (150.0,)
    assert "latencies_ms" not in (tmp_path / "b.json").read_text(encoding="utf-8")


def test_design_and_changelog_state_v1_626():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert "- v1.626 measured latency (row LAT1a):" in design
    assert "`.p95_latency_ms(task, model_id) -> float | None`" in design
    assert "- v1.626 files and calibration:" in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert changelog[-1].startswith("- v1.626 (2026-11-24): spec, code and tests (4.3, row LAT1a).")
