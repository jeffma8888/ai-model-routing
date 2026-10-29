"""JSONL sinks and attempt-level versus call-level aggregation."""

import json

import pytest
from model_routing import Monitor, load_records, report


REPORT_KEYS = {
    "group", "attempts", "ok", "errors", "invalid", "input_tokens", "output_tokens",
    "cost_usd", "routing_cost_usd", "calls", "failed_calls", "fallback_calls",
    "fallback_rate", "p50_latency_ms", "p95_latency_ms",
}


def test_monitor_memory_sink_appends_in_order(record_factory):
    monitor = Monitor()
    assert monitor.records == []
    records = [record_factory(call_id="a"), record_factory(call_id="b")]
    for record in records:
        monitor.record(record)
    assert monitor.records == records


def test_monitor_file_sink_appends_json_lines_and_memory_records(tmp_path, record_factory):
    path = tmp_path / "calls.jsonl"
    existing = record_factory(call_id="existing")
    path.write_text(json.dumps(existing) + "\n", encoding="utf-8")
    monitor = Monitor(path)
    first, second = record_factory(call_id="first"), record_factory(call_id="second")
    monitor.record(first)
    assert [json.loads(line) for line in path.read_text().splitlines()] == [existing, first]
    monitor.record(second)
    assert monitor.records == [first, second]
    assert [json.loads(line) for line in path.read_text().splitlines()] == [existing, first, second]


def test_monitor_creates_new_log_file(tmp_path, record_factory):
    path = tmp_path / "new.jsonl"
    record = record_factory()
    Monitor(path).record(record)
    assert load_records(path) == [record]


def test_load_records_skips_empty_and_whitespace_lines(tmp_path, record_factory):
    records = [record_factory(call_id="a"), record_factory(call_id="b")]
    path = tmp_path / "calls.jsonl"
    path.write_text("\n  \n" + json.dumps(records[0]) + "\n\t\n" + json.dumps(records[1]) + "\n\n")
    assert load_records(path) == records


@pytest.fixture
def mixed_records(record_factory):
    return [
        record_factory(call_id="fallback-ok", model="fiction/a", family="a", attempt=0,
                       final=False, outcome="error", error="ProviderError: outage",
                       latency_ms=900.0, input_tokens=0, output_tokens=0,
                       cost_usd=0.0, routing_cost_usd=0.0, tags={"suite": "red"}),
        record_factory(call_id="fallback-ok", model="fiction/b", family="b", attempt=1,
                       latency_ms=20.0, input_tokens=20, output_tokens=2,
                       cost_usd=0.2, routing_cost_usd=0.2, tags={"suite": "red"}),
        record_factory(call_id="failed", model="fiction/a", family="a", attempt=0,
                       final=False, outcome="invalid", error="validation failed",
                       latency_ms=800.0, input_tokens=10, output_tokens=1,
                       cost_usd=0.1, routing_cost_usd=0.1, tags={"suite": "blue"}),
        record_factory(call_id="failed", model="fiction/b", family="b", attempt=1,
                       outcome="error", error="ProviderError: outage", latency_ms=700.0,
                       input_tokens=0, output_tokens=0, cost_usd=0.0,
                       routing_cost_usd=0.0, tags={"suite": "blue"}),
        record_factory(call_id="single-ok", model="fiction/a", family="a", task="other",
                       flavor="cost_blind", latency_ms=10.0, input_tokens=30, output_tokens=3,
                       cost_usd=0.3, routing_cost_usd=0.0),
    ]


def test_report_uses_each_attempt_for_sums_and_final_attempt_for_call_metrics(mixed_records):
    rows = report(mixed_records)
    assert all(set(row) == REPORT_KEYS for row in rows)
    assert rows == [
        {"group": "fiction/a", "attempts": 3, "ok": 1, "errors": 1, "invalid": 1,
         "input_tokens": 40, "output_tokens": 4, "cost_usd": 0.4,
         "routing_cost_usd": 0.1, "calls": 1, "failed_calls": 0,
         "fallback_calls": 0, "fallback_rate": 0.0,
         "p50_latency_ms": 10.0, "p95_latency_ms": 10.0},
        {"group": "fiction/b", "attempts": 2, "ok": 1, "errors": 1, "invalid": 0,
         "input_tokens": 20, "output_tokens": 2, "cost_usd": 0.2,
         "routing_cost_usd": 0.2, "calls": 2, "failed_calls": 1,
         "fallback_calls": 2, "fallback_rate": 1.0,
         "p50_latency_ms": 20.0, "p95_latency_ms": 20.0},
    ]


@pytest.mark.parametrize("by,groups", [
    ("model", {"fiction/a": (3, 1), "fiction/b": (2, 2)}),
    ("family", {"a": (3, 1), "b": (2, 2)}),
    ("task", {"judge": (4, 2), "other": (1, 1)}),
    ("flavor", {"cost_effective": (4, 2), "cost_blind": (1, 1)}),
    ("tag:suite", {"red": (2, 1), "blue": (2, 1), "(none)": (1, 1)}),
    ("tag:missing", {"(none)": (5, 3)}),
])
def test_report_supports_each_group_key_and_missing_tags(mixed_records, by, groups):
    rows = report(mixed_records, by=by)
    assert {r["group"]: (r["attempts"], r["calls"]) for r in rows} == groups
    assert sum(r["cost_usd"] for r in rows) == pytest.approx(0.6)
    assert sum(r["routing_cost_usd"] for r in rows) == pytest.approx(0.3)
    assert sum(r["failed_calls"] for r in rows) == 1
    assert sum(r["fallback_calls"] for r in rows) == 2


def test_report_missing_tag_and_empty_tag_value_are_distinct(record_factory):
    missing = record_factory(call_id="missing")
    empty = record_factory(call_id="empty", tags={"suite": ""})
    rows = report([missing, empty], by="tag:suite")
    assert {row["group"] for row in rows} == {"(none)", ""}


def test_report_nonfinal_only_group_has_zero_calls_and_zero_fallback_rate(record_factory):
    records = [record_factory(model="fiction/first", final=False, outcome="error",
                              error="ProviderError: outage", attempt=0),
               record_factory(model="fiction/last", attempt=1)]
    rows = {row["group"]: row for row in report(records)}
    first = rows["fiction/first"]
    assert first["attempts"] == 1
    assert first["calls"] == first["failed_calls"] == first["fallback_calls"] == 0
    assert first["fallback_rate"] == 0.0
    assert first["p50_latency_ms"] is None and first["p95_latency_ms"] is None
    assert rows["fiction/last"]["fallback_calls"] == 1


def test_report_final_invalid_counts_as_failed_call_without_fallback(record_factory):
    row = report([record_factory(outcome="invalid", error="validation failed")])[0]
    assert row["calls"] == row["failed_calls"] == row["invalid"] == 1
    assert row["fallback_calls"] == 0
    assert row["p50_latency_ms"] is None and row["p95_latency_ms"] is None


def test_report_nearest_rank_percentiles_use_ok_attempts_only_hand_computed(record_factory):
    # Sorted successful latencies are 1..20: ceil(.5*20)=10, ceil(.95*20)=19.
    # Interpolation would give 10.5 and 19.05, which are deliberately not accepted.
    records = [record_factory(call_id=str(i), latency_ms=float(i)) for i in range(20, 0, -1)]
    records += [record_factory(call_id="error", outcome="error", latency_ms=10000.0),
                record_factory(call_id="invalid", outcome="invalid", latency_ms=0.0)]
    row = report(records)[0]
    assert row["p50_latency_ms"] == 10.0
    assert row["p95_latency_ms"] == 19.0
    assert row["ok"] == 20


def test_report_sorts_descending_cost_then_ascending_group_and_rounds_sums(record_factory):
    records = [
        record_factory(model="fiction/z", call_id="z", cost_usd=0.1, routing_cost_usd=0.1),
        record_factory(model="fiction/a", call_id="a", cost_usd=0.1, routing_cost_usd=0.1),
        record_factory(model="fiction/top", call_id="t", cost_usd=1.1234567, routing_cost_usd=0.1234567),
        record_factory(model="fiction/tiny", call_id="s1", cost_usd=0.0000004, routing_cost_usd=0.0000004),
        record_factory(model="fiction/tiny", call_id="s2", cost_usd=0.0000004, routing_cost_usd=0.0000004),
    ]
    rows = report(records)
    assert [row["group"] for row in rows] == ["fiction/top", "fiction/a", "fiction/z", "fiction/tiny"]
    assert rows[0]["cost_usd"] == 1.123457
    assert rows[0]["routing_cost_usd"] == 0.123457
    assert rows[-1]["cost_usd"] == rows[-1]["routing_cost_usd"] == 0.000001


@pytest.mark.parametrize("by", ["model", "task", "flavor", "family", "tag:suite"])
def test_report_empty_records_returns_empty_list(by):
    assert report([], by=by) == []


@pytest.mark.parametrize("by", ["unknown", "cost_usd", "tags", "tag", ""])
def test_report_unknown_group_key_raises_valueerror_even_with_empty_input(by):
    with pytest.raises(ValueError):
        report([], by=by)


@pytest.mark.parametrize("lines,number", [
    ('{}\n\n[]\n', 3), ('{}\n{"truncated":\n', 2),
])
def test_load_records_rejects_malformed_or_nonobject_line_with_path_and_number(tmp_path, lines, number):
    path = tmp_path / "fiction-calls.jsonl"
    path.write_text(lines, encoding="utf-8")
    with pytest.raises(ValueError) as caught:
        load_records(path)
    assert f"{path.name}:{number}" in str(caught.value)
