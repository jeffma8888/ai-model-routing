"""DESIGN 8.3 and 10 v1.611 (row CANARY1c): `report` keeps shadow calls apart.

`report(records, by, audits, cache, shadow=True)` and `model-routing report --shadow` keep every
record whose `shadow` is JSON `true` (a shadow call, 7 and 8.1 v1.607) out of v1.610's keys, so the
calls, failures, fallback rate, latency percentiles, below-bar count and the audit and cache keys
read the routed records alone, and add three last keys read from the shadow records alone:
`shadow_calls`, `shadow_failed_calls` and `shadow_cost_usd`. Without the keyword every row and
every byte of the CLI output is v1.610's, where a shadow call counts as a call of its own.
"""

import contextlib
import copy
import io
import json
import inspect
from pathlib import Path

import pytest

from model_routing import (
    Completion, Executor, FakeProvider, Model, Monitor, ProviderError, Registry, Router, Stats,
    Task, report,
)
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
V1_610_KEYS = ["group", "attempts", "ok", "errors", "invalid", "input_tokens", "output_tokens",
               "cost_usd", "routing_cost_usd", "calls", "failed_calls", "fallback_calls",
               "fallback_rate", "p50_latency_ms", "p95_latency_ms", "below_bar_calls"]
AUDIT_KEYS = ["audited_calls", "correct_calls", "cost_per_success_usd", "successes_per_100k_tokens"]
CACHE_KEYS = ["cached_input_tokens", "cache_counted_input_tokens", "cache_hit_rate"]
SHADOW_KEYS = ["shadow_calls", "shadow_failed_calls", "shadow_cost_usd"]


def router():
    """cost_effective routes cheap first, then mid and best; the default shadow route is best."""
    task = Task("judge", bar=0.7, min_samples=10, shadow_rate=1.0)
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (MID, (95, 100)),
                                          (BEST, (100, 100))):
        stats.add(task.name, model_id, successes, trials)
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000),
                         Model(BEST, "large", 10.0, 20.0, 8000)])
    return Router(registry, {task.name: task}, stats)


def answers(*texts):
    """A script callable that answers each text in turn, then raises ProviderError."""
    queue = list(texts)

    def complete(messages):
        if not queue:
            raise ProviderError("outage")
        return Completion(queue.pop(0), 1000, 200)
    return complete


def run(script, calls, validate=None):
    monitor = Monitor()
    ids = iter(f"call-{i}" for i in range(1000))
    ticks = iter(float(i) for i in range(10_000))
    executor = Executor(router(), FakeProvider(script), monitor=monitor,
                        clock=lambda: next(ticks), now=lambda: "2026-11-23T00:00:00Z",
                        id_factory=lambda: next(ids), random=lambda: 0.0)
    for _ in range(calls):
        executor.call("judge", MESSAGES, validate=validate)
    return monitor.records


def three_shadows():
    """Routed on cheap three times (0.0014 each); shadows on best answer ok (0.014), invalid
    (0.014), then err (0.0), as calls call-1, call-3 and call-5."""
    script = {CHEAP: answers("cheap", "cheap", "cheap"), BEST: answers("best", "bad")}
    return run(script, 3, validate=lambda text: text != "bad")


def rec(call_id, shadow, model=CHEAP, outcome="ok", latency=10.0, cost=0.1, **extra):
    """A hand-built final attempt record of task judge."""
    return {"call_id": call_id, "task": "judge", "flavor": "cost_effective", "model": model,
            "family": model.split("/")[1], "attempt": 0, "final": True, "outcome": outcome,
            "latency_ms": latency, "input_tokens": 1000, "output_tokens": 200, "cost_usd": cost,
            "routing_cost_usd": cost, "below_bar": False, "tags": {}, "pair_id": "p",
            "shadow": shadow, **extra}


def routed_only(records):
    return [r for r in records if r.get("shadow") is not True]


def strip(row):
    return {k: v for k, v in row.items() if k not in SHADOW_KEYS}


def tails(rows):
    return {row["group"]: tuple(row[k] for k in SHADOW_KEYS) for row in rows}


def zero_row(group):
    return {"group": group, "attempts": 0, "ok": 0, "errors": 0, "invalid": 0, "input_tokens": 0,
            "output_tokens": 0, "cost_usd": 0.0, "routing_cost_usd": 0.0, "calls": 0,
            "failed_calls": 0, "fallback_calls": 0, "fallback_rate": 0.0, "p50_latency_ms": None,
            "p95_latency_ms": None, "below_bar_calls": 0}


def by_group(rows, key):
    return {row["group"]: row[key] for row in rows}


# ---- 8.3 the default is v1.610's ----------------------------------------------------------------

def test_the_keyword_defaults_to_false():
    assert inspect.signature(report).parameters["shadow"].default is False


def test_without_the_keyword_a_shadow_is_a_call_of_its_own():
    # unmarked guard: v1.607 to v1.610 count a shadow call among the calls of its group
    rows = report(three_shadows(), by="task")
    assert [list(row) for row in rows] == [V1_610_KEYS]
    assert (rows[0]["calls"], rows[0]["failed_calls"], rows[0]["errors"], rows[0]["invalid"]) == (6, 2, 1, 1)
    assert report(three_shadows(), by="task", shadow=False) == rows


# ---- 8.3 shadow=True: the routed keys ------------------------------------------------------------

@pytest.mark.parametrize("by", ["model", "task", "flavor", "family", "pricing_basis", "tag:shadow"])
def test_the_routed_keys_are_the_rows_of_the_log_without_its_shadow_records(by):
    records = three_shadows()
    kept = {row["group"]: strip(row) for row in report(records, by=by, shadow=True)}
    plain = {row["group"]: row for row in report(routed_only(records), by=by)}
    assert {group: kept[group] for group in plain} == plain
    for group in set(kept) - set(plain):   # a group only shadow records reach
        assert kept[group] == zero_row(group)


def test_a_shadow_s_failures_leave_the_routed_errors_and_failed_calls():
    row, = report(three_shadows(), by="task", shadow=True)
    assert (row["calls"], row["failed_calls"], row["errors"], row["invalid"]) == (3, 0, 0, 0)
    assert (row["attempts"], row["ok"], row["cost_usd"]) == (3, 3, 0.0042)


def test_the_fallback_rate_is_over_the_routed_calls_alone():
    records = run({MID: answers("mid"), BEST: answers("best")}, 1)  # cheap errs, mid answers
    before, = report(records, by="task")
    after, = report(records, by="task", shadow=True)
    assert (before["calls"], before["fallback_calls"], before["fallback_rate"]) == (2, 1, 0.5)
    assert (after["calls"], after["fallback_calls"], after["fallback_rate"]) == (1, 1, 1.0)
    assert tails([after]) == {"judge": (1, 0, 0.014)}


def test_a_shadow_s_latency_enters_neither_percentile():
    records = [rec("r", False, latency=10.0), rec("s", True, model=BEST, latency=500.0)]
    before, = report(records, by="task")
    after, = report(records, by="task", shadow=True)
    assert (before["p50_latency_ms"], before["p95_latency_ms"]) == (10.0, 500.0)
    assert (after["p50_latency_ms"], after["p95_latency_ms"]) == (10.0, 10.0)


def test_below_bar_calls_counts_routed_calls_alone():
    records = [rec("r", False, below_bar_fallback=True), rec("s", True, model=BEST, below_bar=True)]
    assert by_group(report(records, by="task"), "below_bar_calls") == {"judge": 2}
    assert by_group(report(records, by="task", shadow=True), "below_bar_calls") == {"judge": 1}


def test_an_audit_of_a_shadow_is_ignored_and_success_costs_the_routed_attempts():
    audits = {"call-0": True, "call-2": True, "call-4": True, "call-1": True, "call-3": True}
    before, = report(three_shadows(), by="task", audits=audits)
    after, = report(three_shadows(), by="task", audits=audits, shadow=True)
    assert (before["audited_calls"], before["cost_per_success_usd"]) == (5, None)  # 5 of 6
    assert [after[k] for k in AUDIT_KEYS] == [3, 3, 0.0014, 83.333333]  # 3 * 1e5 / 3,600


def test_the_cache_keys_read_the_routed_records_alone():
    records = [rec("r", False, cached_input_tokens=100), rec("s", True, cached_input_tokens=900)]
    before, = report(records, by="task", cache=True)
    after, = report(records, by="task", cache=True, shadow=True)
    assert [before[k] for k in CACHE_KEYS] == [1000, 2000, 0.5]
    assert [after[k] for k in CACHE_KEYS] == [100, 1000, 0.1]


@pytest.mark.parametrize("value", [1, "true", None, False])
def test_only_a_json_true_marks_a_shadow_record(value):
    records = [rec("r", False), rec("s", value, model=BEST)]
    assert report(records, shadow=True) == [
        dict(row, shadow_calls=0, shadow_failed_calls=0, shadow_cost_usd=0.0)
        for row in report(records)]


def test_a_record_without_the_key_is_routed():
    records = [{k: v for k, v in rec("r", False).items() if k not in ("pair_id", "shadow")}]
    assert tails(report(records, shadow=True)) == {CHEAP: (0, 0, 0.0)}
    assert strip(report(records, shadow=True)[0]) == report(records)[0]


# ---- 8.3 shadow=True: the shadow keys --------------------------------------------------------------

def test_the_shadow_keys_come_last_in_order():
    assert [list(row) for row in report(three_shadows(), shadow=True)] == [V1_610_KEYS + SHADOW_KEYS] * 2
    rows = report(three_shadows(), audits={}, cache=True, shadow=True)
    assert [list(row) for row in rows] == [V1_610_KEYS + AUDIT_KEYS + CACHE_KEYS + SHADOW_KEYS] * 2


@pytest.mark.parametrize("by, want", [
    ("model", {CHEAP: (0, 0, 0.0), BEST: (3, 2, 0.028)}),
    ("family", {"small": (0, 0, 0.0), "large": (3, 2, 0.028)}),
    ("task", {"judge": (3, 2, 0.028)}),
    ("tag:shadow", {"(none)": (0, 0, 0.0), "true": (3, 2, 0.028)}),
])
def test_each_shadow_record_counts_in_its_own_group(by, want):
    assert tails(report(three_shadows(), by=by, shadow=True)) == want


def test_rows_sort_by_the_routed_spend():
    assert [r["group"] for r in report(three_shadows())] == [BEST, CHEAP]   # 0.028 over 0.0042
    assert [r["group"] for r in report(three_shadows(), shadow=True)] == [CHEAP, BEST]


@pytest.mark.parametrize("by", ["model", "task", "family", "tag:shadow"])
def test_the_spend_is_split_and_none_is_lost(by):
    total = sum(r["cost_usd"] for r in report(three_shadows(), by=by))
    split = sum(r["cost_usd"] + r["shadow_cost_usd"] for r in report(three_shadows(), by=by, shadow=True))
    assert split == pytest.approx(total, abs=1e-9) and total == pytest.approx(0.0322, abs=1e-9)


def test_a_shadow_s_routing_cost_enters_no_key():
    rows = report(three_shadows(), shadow=True)
    assert by_group(rows, "routing_cost_usd") == {CHEAP: 0.0042, BEST: 0.0}


def test_a_refused_shadow_hold_is_in_no_key():
    budget = {"budget_event": "refused", "call_id": "call-9", "task": "judge", "model": BEST,
              "pair_id": "call-0", "shadow": True, "final": True, "outcome": "error", "cost_usd": 0.5}
    records = three_shadows()
    assert report(records + [budget], shadow=True) == report(records, shadow=True)


def test_a_log_with_no_shadow_record_gains_three_zero_keys():
    records = run({BEST: answers("best")}, 1)  # the routed answer is best's: no shadow is sent
    assert any(r.get("pair_id") == "call-0" for r in records)
    for by in ("model", "task"):
        assert report(records, by=by, shadow=True) == [
            dict(row, shadow_calls=0, shadow_failed_calls=0, shadow_cost_usd=0.0)
            for row in report(records, by=by)]


@pytest.mark.parametrize("value", [1, 0, "yes", None, 1.0])
def test_a_shadow_that_is_not_a_bool_raises_before_any_record_is_read(value):
    def untouched():
        raise AssertionError("a record was read")
        yield
    with pytest.raises(ValueError, match="shadow"):
        report(untouched(), shadow=value)


def test_records_are_left_unchanged():
    records = three_shadows()
    before = copy.deepcopy(records)
    report(records, audits={"call-0": True}, cache=True, shadow=True)
    assert records == before


# ---- 10 the CLI -----------------------------------------------------------------------------------

def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def _log(tmp_path, records, name="calls.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def test_the_cli_table_gains_three_columns_after_p95(tmp_path):
    code, out, err = _run(["report", "--log", str(_log(tmp_path, three_shadows())), "--shadow"])
    assert (code, err) == (0, "")
    header, rule, cheap, best = out.splitlines()
    assert header.split() == ["model", "calls", "attempts", "errors", "invalid", "fallback_calls",
                              "fallback_rate", "cost_usd", "routing_cost_usd", "p50_ms", "p95_ms",
                              ] + SHADOW_KEYS
    assert len(rule.split()) == len(header.split()) and set(rule.replace(" ", "")) == {"-"}
    assert cheap.split() == [CHEAP, "3", "3", "0", "0", "0", "0.000", "0.004200", "0.004200",
                             "1000.0", "1000.0", "0", "0", "0.000000"]
    assert best.split() == [BEST, "0", "0", "0", "0", "0", "0.000", "0.000000", "0.000000",
                            "-", "-", "3", "2", "0.028000"]


def test_the_cli_puts_the_shadow_columns_after_audits_and_cache(tmp_path):
    audits = tmp_path / "audits.jsonl"
    audits.write_text('{"call_id": "call-0", "correct": true}\n', encoding="utf-8")
    code, out, err = _run(["report", "--log", str(_log(tmp_path, three_shadows())),
                           "--audits", str(audits), "--cache", "--shadow"])
    assert (code, err) == (0, "")
    assert out.splitlines()[0].split()[-10:] == AUDIT_KEYS + CACHE_KEYS + SHADOW_KEYS


def test_the_cli_json_has_the_three_keys(tmp_path):
    code, out, err = _run(["report", "--log", str(_log(tmp_path, three_shadows())), "--shadow",
                           "--json"])
    assert (code, err) == (0, "")
    rows = json.loads(out)
    assert [list(row) for row in rows] == [V1_610_KEYS + SHADOW_KEYS] * 2
    assert tails(rows) == {CHEAP: (0, 0, 0.0), BEST: (3, 2, 0.028)}


def test_the_cli_without_the_option_prints_v1_610_rows(tmp_path):
    # unmarked guard: no shadow column or key, and the rows count a shadow as a call of its own
    path = _log(tmp_path, three_shadows())
    code, out, err = _run(["report", "--log", str(path), "--json"])
    assert (code, err) == (0, "") and json.loads(out) == report(three_shadows())
    code, out, err = _run(["report", "--log", str(path)])
    assert (code, err) == (0, "") and "shadow" not in out


def test_the_below_bar_column_follows_the_routed_count(tmp_path):
    path = _log(tmp_path, [rec("r", False), rec("s", True, model=BEST, below_bar=True)])
    plain = _run(["report", "--log", str(path)])[1].splitlines()[0].split()
    kept = _run(["report", "--log", str(path), "--shadow"])[1].splitlines()[0].split()
    assert "below_bar_calls" in plain and "below_bar_calls" not in kept


# ---- the spec -------------------------------------------------------------------------------------

def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for start, end, opening in [
            ("### 8.3 ", "## 9. ", '- v1.611 `report(records, by="model", audits=None, cache=False, '
                                   'shadow=False)` (row CANARY1c'),
            ("## 10. ", "## 11. ", "  - v1.611 `--shadow` (row CANARY1c)")]:
        part = design[design.index(start):design.index(end)]
        assert part.count(opening) == 1, start
    assert "- `report --log PATH [--by KEY] [--json] [--audits PATH] [--cache] [--shadow]`" in design
    assert "(row CANARY1c, which v1.611 adds as `shadow=True`, 8.3;" in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.611 (")]
    assert len(mine) == 1 and "(7, 8.1, 8.3, 10, row CANARY1c)" in mine[0]
