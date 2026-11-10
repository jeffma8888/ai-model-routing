"""DESIGN 7, 8.1, 8.3 and 10 v1.203 (row S2b): a record says that its model was under the bar.

An attempt on a model of `RouteDecision.below_bar_fallbacks` (a task with `fallback_below_bar`,
5.3) carries `below_bar_fallback: true` right after `below_bar`, and no other record has the key.
`report` counts in `below_bar_calls` the calls whose final attempt is `ok` on a model under the
bar, and the `report` text table shows that column only when some row counts one."""

import hashlib
import json
from pathlib import Path

import pytest

from model_routing import (AllModelsFailed, Completion, Executor, FakeProvider, Model, Monitor,
                           ProviderError, Registry, Router, Stats, Task, load_records, report)
from model_routing.cli import _table, main
from model_routing.demo import run_demo

ROOT = Path(__file__).resolve().parents[1]

V1_202_KEYS = ["ts", "call_id", "task", "flavor", "model", "family", "attempt", "final",
               "outcome", "error", "latency_ms", "input_tokens", "output_tokens", "cost_usd",
               "routing_cost_usd", "below_bar", "basis", "tags"]
WITH_KEY = V1_202_KEYS[:16] + ["below_bar_fallback"] + V1_202_KEYS[16:]
V1_202_COLUMNS = ["calls", "attempts", "errors", "invalid", "fallback_calls", "fallback_rate",
                  "cost_usd", "routing_cost_usd", "p50_ms", "p95_ms"]
V1_203_COLUMNS = V1_202_COLUMNS[:6] + ["below_bar_calls"] + V1_202_COLUMNS[6:]
# sha256 of the whole calls.jsonl of `run_demo` (seed 7) at v1.202, all 456 records; the
# v1.12 pin of tests/test_demo_delegation.py covers the first 455
V1_202_CALLS_SHA256 = "e3f4eca7bc4c6e8ca0eb41da21c786cbd897c9fa1792e713a518664c3b02219a"

# (id, family, price_in, successes, trials); bar 0.7, min_samples 20
MODELS = [
    ("p/cheap", "p1", 1.0, 95, 100),   # passes, cheapest: the primary in both flavors
    ("p/dear", "p2", 5.0, 93, 100),    # passes: the first fallback
    ("b/close", "b1", 2.0, 70, 100),   # below_bar, bound about 0.604
    ("b/far", "b2", 0.5, 50, 100),     # below_bar, bound about 0.404
]


def build(on=True, max_fallbacks=2):
    registry = Registry([Model(m, fam, price, 2.0, 100_000) for m, fam, price, _, _ in MODELS])
    stats = Stats()
    for m, _, _, succ, trials in MODELS:
        stats.add("t", m, succ, trials)
    task = Task(name="t", bar=0.7, min_samples=20, independent_of_generator=False,
                max_fallbacks=max_fallbacks, fallback_below_bar=on)
    return Router(registry, {"t": task}, stats)


def fail(messages):
    raise ProviderError("outage")


def ok(messages):
    return Completion("fine", 10, 2)


def bad(messages):
    return Completion("not fine", 10, 2)


def executor(router, script, monitor):
    ticks = iter(float(i) for i in range(100))
    return Executor(router, FakeProvider(script), monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: "2026-01-02T03:04:05Z", id_factory=lambda: "fixed-call")


def keys(records):
    return [list(rec) for rec in records]


# ---- 8.1 the key on an attempt record --------------------------------------------------------

@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_an_attempt_on_a_below_bar_fallback_carries_the_key_after_below_bar(flavor):
    router = build()
    monitor = Monitor()
    run = executor(router, {"p/cheap": fail, "p/dear": bad, "b/close": ok}, monitor)
    result = run.call("t", [{"role": "user", "content": "x"}], flavor=flavor,
                      validate=lambda text: text == "fine")
    assert (result.decision.primary, result.decision.fallbacks) == ("p/cheap", ("p/dear", "b/close"))
    assert result.decision.below_bar_fallbacks == ("b/close",)
    assert [rec["model"] for rec in monitor.records] == ["p/cheap", "p/dear", "b/close"]
    assert keys(monitor.records) == [V1_202_KEYS, V1_202_KEYS, WITH_KEY]
    assert monitor.records[2]["below_bar_fallback"] is True
    assert [rec["below_bar"] for rec in monitor.records] == [False, False, False]


def test_every_below_bar_fallback_attempt_has_the_key_when_all_fail():
    router = build(max_fallbacks=3)
    monitor = Monitor()
    run = executor(router, {}, monitor)
    with pytest.raises(AllModelsFailed):
        run.call("t", [{"role": "user", "content": "x"}])
    assert [rec["model"] for rec in monitor.records] == ["p/cheap", "p/dear", "b/close", "b/far"]
    assert keys(monitor.records) == [V1_202_KEYS, V1_202_KEYS, WITH_KEY, WITH_KEY]


def test_no_record_has_the_key_without_a_below_bar_fallback_attempt():
    """Option off: the route stops at the passing models. Option on, primary answers: one record."""
    for on, script, models in [(False, {}, ["p/cheap", "p/dear"]),
                               (True, {"p/cheap": ok}, ["p/cheap"]),
                               (True, {"p/dear": ok}, ["p/cheap", "p/dear"])]:
        monitor = Monitor()
        run = executor(build(on=on), script, monitor)
        if script:
            assert run.call("t", [{"role": "user", "content": "x"}]).model == models[-1]
        else:
            with pytest.raises(AllModelsFailed):
                run.call("t", [{"role": "user", "content": "x"}])
        assert [rec["model"] for rec in monitor.records] == models
        assert keys(monitor.records) == [V1_202_KEYS] * len(models)


def test_a_best_available_route_keeps_v1_202_keys_with_below_bar_true():
    registry = Registry([Model(m, fam, price, 2.0, 100_000) for m, fam, price, _, _ in MODELS[2:]])
    stats = Stats()
    for m, _, _, succ, trials in MODELS[2:]:
        stats.add("t", m, succ, trials)
    task = Task(name="t", bar=0.7, min_samples=20, independent_of_generator=False,
                on_no_model="best_available", fallback_below_bar=True)
    monitor = Monitor()
    run = executor(Router(registry, {"t": task}, stats), {"b/far": ok}, monitor)
    run.call("t", [{"role": "user", "content": "x"}])
    assert [rec["model"] for rec in monitor.records] == ["b/close", "b/far"]
    assert keys(monitor.records) == [V1_202_KEYS, V1_202_KEYS]
    assert [rec["below_bar"] for rec in monitor.records] == [True, True]


def test_call_delegated_takes_the_key_from_the_route():
    router = build()
    decision = router.decide_delegation("t", "b/far", "cost_effective", context_tokens=1000,
                                        brief_tokens=100, result_tokens=20)
    assert (decision.mode, decision.reason) == ("delegate", "parent_below_bar")
    assert decision.route.below_bar_fallbacks == ("b/close",)
    monitor = Monitor()
    run = executor(router, {"p/cheap": fail, "p/dear": fail, "b/close": ok}, monitor)
    run.call_delegated(decision, [{"role": "user", "content": "brief"}], tags={"team": "x"})
    assert keys(monitor.records) == [V1_202_KEYS, V1_202_KEYS, WITH_KEY]
    assert monitor.records[2]["below_bar_fallback"] is True
    assert monitor.records[2]["tags"] == {"team": "x", "delegated": "true", "parent": "b/far"}


def test_the_demo_records_keep_v1_202_keys(tmp_path):
    run_demo(tmp_path / "demo")
    records = load_records(tmp_path / "demo" / "calls.jsonl")
    assert len(records) == 456
    assert keys(records) == [V1_202_KEYS] * len(records)
    data = (tmp_path / "demo" / "calls.jsonl").read_bytes()
    assert hashlib.sha256(data).hexdigest() == V1_202_CALLS_SHA256


# ---- 8.3 below_bar_calls -----------------------------------------------------------------------

def logged(record_factory):
    """Six calls, by hand: A, B and E count; C failed; D cleared; F is an old writer's record."""
    r = record_factory
    old = r(call_id="F", model="p/cheap")
    del old["below_bar"]
    return [
        r(call_id="A", model="p/cheap", final=False, outcome="error", error="ProviderError: x"),
        r(call_id="A", model="b/close", attempt=1, below_bar_fallback=True),
        r(call_id="B", model="b/far", below_bar=True, basis="measured"),
        r(call_id="C", model="p/cheap", final=False, outcome="error", error="ProviderError: x"),
        r(call_id="C", model="b/close", attempt=1, outcome="error", error="ProviderError: x",
          below_bar_fallback=True),
        r(call_id="D", model="p/cheap"),
        r(call_id="E", model="p/cheap", final=False, outcome="error", error="ProviderError: x"),
        r(call_id="E", model="b/close", attempt=1, final=False, outcome="invalid",
          error="validation failed", below_bar_fallback=True),
        r(call_id="E", model="b/far", attempt=2, below_bar_fallback=True),
        old,
    ]


def test_report_counts_the_ok_calls_answered_under_the_bar(record_factory):
    rows = {row["group"]: row for row in report(logged(record_factory))}
    assert {group: row["below_bar_calls"] for group, row in rows.items()} == {
        "p/cheap": 0, "b/close": 1, "b/far": 2}
    assert {group: row["calls"] for group, row in rows.items()} == {
        "p/cheap": 2, "b/close": 2, "b/far": 2}
    assert rows["b/close"]["failed_calls"] == 1


@pytest.mark.parametrize("flag", ["below_bar", "below_bar_fallback"])
@pytest.mark.parametrize("value,counted", [(True, 1), (1, 0), ("true", 0), (False, 0), (None, 0),
                                           ("missing", 0)])
def test_only_a_json_true_counts_in_either_flag(record_factory, flag, value, counted):
    rec = record_factory(model="b/far")
    del rec["below_bar"]
    if value != "missing":
        rec[flag] = value
    assert [row["below_bar_calls"] for row in report([rec])] == [counted]


@pytest.mark.parametrize("by", ["model", "task", "flavor", "family", "tag:none"])
def test_every_row_has_the_count_as_its_last_key(record_factory, by):
    rows = report(logged(record_factory), by=by)
    assert all(list(row)[-1] == "below_bar_calls" for row in rows)
    assert sum(row["below_bar_calls"] for row in rows) == 3


def test_a_log_without_any_call_under_the_bar_counts_zero(record_factory):
    rows = report([record_factory(), record_factory(call_id="2", model="fiction/b")])
    assert [row["below_bar_calls"] for row in rows] == [0, 0]


# ---- 10 the report text table -----------------------------------------------------------------

def write(path, records):
    path.write_text("".join(json.dumps(rec) + "\n" for rec in records), encoding="utf-8")


def header(text):
    return text.splitlines()[0].split()


def test_report_text_shows_the_column_when_some_call_was_under_the_bar(tmp_path, record_factory, capsys):
    path = tmp_path / "calls.jsonl"
    write(path, logged(record_factory))
    assert main(["report", "--log", str(path)]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert header(lines[0]) == ["model"] + V1_203_COLUMNS
    column = V1_203_COLUMNS.index("below_bar_calls") + 1
    assert {line.split()[0]: line.split()[column] for line in lines[2:]} == {
        "p/cheap": "0", "b/close": "1", "b/far": "2"}
    assert main(["report", "--log", str(path), "--json"]) == 0
    assert {row["group"]: row["below_bar_calls"] for row in json.loads(capsys.readouterr().out)} == {
        "p/cheap": 0, "b/close": 1, "b/far": 2}


def test_report_text_without_a_call_under_the_bar_is_the_v1_202_table(tmp_path, record_factory, capsys):
    path = tmp_path / "calls.jsonl"
    records = [r for r in logged(record_factory) if r["call_id"] in ("C", "D", "F")]
    records = [{k: v for k, v in r.items() if k != "below_bar_fallback"} for r in records]
    write(path, records)
    assert main(["report", "--log", str(path), "--by", "flavor"]) == 0
    text = capsys.readouterr().out
    rows = report(records, by="flavor")

    def fmt(value):
        return "-" if value is None else f"{value:.1f}"
    table = [[r["group"], r["calls"], r["attempts"], r["errors"], r["invalid"],
              r["fallback_calls"], f"{r['fallback_rate']:.3f}", f"{r['cost_usd']:.6f}",
              f"{r['routing_cost_usd']:.6f}", fmt(r["p50_latency_ms"]),
              fmt(r["p95_latency_ms"])] for r in rows]
    assert text == _table(["flavor"] + V1_202_COLUMNS, table) + "\n"
    assert text == (
        "flavor          calls  attempts  errors  invalid  fallback_calls  fallback_rate"
        "  cost_usd  routing_cost_usd  p50_ms  p95_ms\n"
        "--------------  -----  --------  ------  -------  --------------  -------------"
        "  --------  ----------------  ------  ------\n"
        "cost_effective  3      4         2       0        1               0.333"
        "          0.000480  0.000480          10.0    10.0\n")


# ---- README ------------------------------------------------------------------------------------

def test_readme_monitoring_names_the_key_and_the_count():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Monitoring and cost attribution\n", 1)[1].split("\n## ", 1)[0]
    assert "also carries `below_bar_fallback: true`" in section
    assert "has `below_bar: true`" in section
    assert "`below_bar_calls`" in section
    assert "`fallback_below_bar`" in section
