"""DESIGN 8.3 and 10 v1.590 (row CACHE1f): the report's cache hit rate.

`report(records, by, audits, cache=True)` and `model-routing report --cache` add three last keys
to each row, `cached_input_tokens`, `cache_counted_input_tokens` and `cache_hit_rate`, from the
records that carry a `cached_input_tokens` count (8.1 v1.589) alone, so a record without the count
is unknown and never read as a miss, and a group where no record says has the rate `None` (`n/a`),
never 0. The write count enters no part of the rate. Without the keyword every row and every byte
of the CLI output is v1.589's. The contract tests were written under strict xfail and the
implementing commit removed the marks; the unmarked guards pin what v1.590 keeps and passed before
and after it.
"""

import contextlib
import io
import json
from pathlib import Path

import pytest

from model_routing import (Executor, Model, Monitor, OpenAICompatibleProvider, Registry, Router,
                           Stats, Task, report)
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
A, B = "fiction/a", "fiction/b"
V1_589_KEYS = ["group", "attempts", "ok", "errors", "invalid", "input_tokens", "output_tokens",
               "cost_usd", "routing_cost_usd", "calls", "failed_calls", "fallback_calls",
               "fallback_rate", "p50_latency_ms", "p95_latency_ms", "below_bar_calls"]
AUDIT_KEYS = ["audited_calls", "correct_calls", "cost_per_success_usd", "successes_per_100k_tokens"]
CACHE_KEYS = ["cached_input_tokens", "cache_counted_input_tokens", "cache_hit_rate"]
MSGS = [{"role": "user", "content": "hi"}]


def _rec(call_id, model, attempt, final, outcome, cost, tokens_in, tokens_out, **counts):
    """A v1.589 record: the counts, when given, right after output_tokens (8.1 v1.589)."""
    record = {"ts": "2026-01-01T00:00:00Z", "call_id": call_id, "task": "judge",
              "flavor": "cost_effective", "model": model, "family": model.split("/")[1],
              "attempt": attempt, "final": final, "outcome": outcome, "error": None,
              "latency_ms": 10.0, "input_tokens": tokens_in, "output_tokens": tokens_out}
    record.update(counts)
    record.update({"cost_usd": cost, "routing_cost_usd": cost, "below_bar": False,
                   "basis": "measured", "tags": {}})
    return record


def _tail(row):
    return tuple(row[key] for key in CACHE_KEYS)


def _by_group(rows):
    return {row["group"]: _tail(row) for row in rows}


def _adapter_records(usages):
    """The records of one OpenAI-compatible adapter call per usage object, through the executor."""
    bodies = iter(json.dumps({"choices": [{"message": {"content": "v"}}], "usage": u}).encode()
                  for u in usages)
    provider = OpenAICompatibleProvider("https://example.org/v1",
                                        opener=lambda request, timeout: io.BytesIO(next(bodies)))
    registry = Registry([Model(A, "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3)])
    planted = Stats()
    planted.add("t", A, 99, 100)
    router = Router(registry, {"t": Task("t", bar=0.7, min_samples=10)}, planted)
    monitor = Monitor()
    ticks = iter(0.5 * i for i in range(1000))
    ids = iter(f"call-{i}" for i in range(1000))
    run = Executor(router, provider, monitor=monitor, clock=lambda: next(ticks),
                   now=lambda: "2026-11-22T00:00:00Z", id_factory=lambda: next(ids))
    for _ in usages:
        run.call("t", MSGS)
    return monitor.records


# ---- 8.3 report(records, by, audits, cache) ---------------------------------------------------

def test_an_adapter_group_at_9000_of_10000_cached_gives_0_9():
    records = _adapter_records([
        {"prompt_tokens": 6_000, "completion_tokens": 50,
         "prompt_tokens_details": {"cached_tokens": 5_400}},
        {"prompt_tokens": 4_000, "completion_tokens": 50,
         "prompt_tokens_details": {"cached_tokens": 3_600}}])
    assert [rec["cached_input_tokens"] for rec in records] == [5_400, 3_600]
    (row,) = report(records, cache=True)
    assert list(row) == V1_589_KEYS + CACHE_KEYS
    assert _tail(row) == (9_000, 10_000, 0.9)
    assert {k: row[k] for k in V1_589_KEYS} == report(records)[0]


def test_cache_false_is_the_default():
    records = [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=900)]
    assert report(records, cache=False) == report(records)
    assert [list(row) for row in report(records, cache=False)] == [V1_589_KEYS]


def test_the_rate_is_rounded_to_6_decimals():
    records = [_rec("c1", A, 0, True, "ok", 0.1, 3_000, 10, cached_input_tokens=1_000)]
    assert _by_group(report(records, cache=True)) == {A: (1_000, 3_000, 0.333333)}


def test_a_mixed_group_counts_only_the_records_that_carry_the_count():
    records = [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=900),
               _rec("c2", A, 0, True, "ok", 0.1, 9_000, 10)]
    (row,) = report(records, cache=True)
    assert _tail(row) == (900, 1_000, 0.9)   # c2 says nothing, so it is no miss
    assert row["input_tokens"] == 10_000      # the attempt sum still counts every input token


def test_a_group_where_no_record_says_gives_none_never_zero():
    records = [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10),
               _rec("c2", B, 0, True, "ok", 0.3, 2_000, 20, cached_input_tokens=0)]
    assert _by_group(report(records, cache=True)) == {A: (0, 0, None), B: (0, 2_000, 0.0)}


def test_a_whole_input_cached_gives_1_0():
    # review iter-438 should-fix 2: a count equal to its input is a count, the top of the range
    records = [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=1_000)]
    assert _by_group(report(records, cache=True)) == {A: (1_000, 1_000, 1.0)}


def test_a_zero_input_sum_gives_none():
    records = [_rec("c1", A, 0, True, "ok", 0.0, 0, 0, cached_input_tokens=0)]
    assert _by_group(report(records, cache=True)) == {A: (0, 0, None)}


def test_the_write_count_enters_no_part_of_the_rate():
    both = [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=900,
                 cache_write_tokens=100)]
    reads = [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=900)]
    assert report(both, cache=True) == report(reads, cache=True)
    writes = [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10, cache_write_tokens=1_000)]
    assert _by_group(report(writes, cache=True)) == {A: (0, 0, None)}


def test_the_sums_are_attempt_level_like_input_tokens():
    # c1 is invalid on A (a billed call, so its record carries the count), then ends ok on B
    records = [_rec("c1", A, 0, False, "invalid", 0.1, 1_000, 10, cached_input_tokens=500),
               _rec("c1", B, 1, True, "ok", 0.3, 1_000, 10, cached_input_tokens=0),
               _rec("c2", B, 0, False, "error", 0.0, 0, 0)]
    assert _by_group(report(records, cache=True)) == {A: (500, 1_000, 0.5), B: (0, 1_000, 0.0)}
    (row,) = report(records, by="task", cache=True)
    assert _tail(row) == (500, 2_000, 0.25)


def test_with_audits_the_three_keys_come_last():
    records = [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=900)]
    (row,) = report(records, audits={"c1": True}, cache=True)
    assert list(row) == V1_589_KEYS + AUDIT_KEYS + CACHE_KEYS
    assert (_tail(row), row["cost_per_success_usd"]) == ((900, 1_000, 0.9), 0.1)


@pytest.mark.parametrize("write", [None, -1, True, 1.5, "x", 10_000])
def test_a_bad_write_count_is_never_read(write):
    # review iter-438 should-fix 1: the write count is read by nothing, so no value of it raises
    records = [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=900,
                    cache_write_tokens=write)]
    assert _by_group(report(records, cache=True)) == {A: (900, 1_000, 0.9)}


@pytest.mark.parametrize("value", [-1, True, False, None, 1.5, 900.0, "9", 1_001])
def test_a_bad_carried_count_raises_naming_the_call_id(value):
    records = [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=900),
               _rec("c9", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=value)]
    with pytest.raises(ValueError, match="c9"):
        report(records, cache=True)


def test_a_carried_count_beside_a_missing_input_count_is_above_it():
    record = _rec("c9", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=5)
    record.pop("input_tokens")
    with pytest.raises(ValueError, match="c9"):
        report([record], cache=True)
    zero = dict(record, cached_input_tokens=0)
    assert _by_group(report([zero], cache=True)) == {A: (0, 0, None)}


@pytest.mark.parametrize("value", [-1, True, None, 1.5, "9", 1_001])
def test_without_the_keyword_no_count_is_read(value):
    # unmarked guard: v1.589's report reads neither count, and v1.590's default reads none
    counted = [_rec("c9", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=value,
                    cache_write_tokens=value)]
    plain = [_rec("c9", A, 0, True, "ok", 0.1, 1_000, 10)]
    for by in ("model", "task", "family"):
        assert report(counted, by=by) == report(plain, by=by)


# ---- 10 the CLI ---------------------------------------------------------------------------------

def _run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def _cli_records():
    return [_rec("c1", A, 0, True, "ok", 0.1, 1_000, 10, cached_input_tokens=900),
            _rec("c2", B, 0, True, "ok", 0.3, 2_000, 20)]


def _log(tmp_path, records, name="calls.jsonl"):
    path = tmp_path / name
    path.write_text("".join(json.dumps(r) + "\n" for r in records), encoding="utf-8")
    return path


def _strip(records):
    return [{k: v for k, v in rec.items() if k not in ("cached_input_tokens", "cache_write_tokens")}
            for rec in records]


@pytest.mark.parametrize("extra", [[], ["--json"], ["--by", "task"]])
def test_the_cli_without_cache_prints_v1_589_bytes(tmp_path, extra):
    # unmarked guard: a log whose records carry counts reports as the same log without them
    counted = _run(["report", "--log", str(_log(tmp_path, _cli_records()))] + extra)
    plain = _run(["report", "--log", str(_log(tmp_path, _strip(_cli_records()), "plain.jsonl"))] + extra)
    assert counted == plain and counted[0] == 0


def test_the_cli_table_gains_three_columns_after_p95_with_n_a(tmp_path):
    code, out, err = _run(["report", "--log", str(_log(tmp_path, _cli_records())), "--cache"])
    assert (code, err) == (0, "")
    assert out == (
        "model      calls  attempts  errors  invalid  fallback_calls  fallback_rate  cost_usd  "
        "routing_cost_usd  p50_ms  p95_ms  cached_input_tokens  cache_counted_input_tokens  "
        "cache_hit_rate\n"
        "---------  -----  --------  ------  -------  --------------  -------------  --------  "
        "----------------  ------  ------  -------------------  --------------------------  "
        "--------------\n"
        "fiction/b  1      1         0       0        0               0.000          0.300000  "
        "0.300000          10.0    10.0    0                    0                           n/a\n"
        "fiction/a  1      1         0       0        0               0.000          0.100000  "
        "0.100000          10.0    10.0    900                  1000                        0.900\n")


def test_the_cache_columns_follow_p95_when_below_bar_calls_shows(tmp_path):
    # review iter-438 should-fix 3: v1.203's column after fallback_rate leaves the three after p95_ms
    records = _cli_records()
    records[0]["below_bar"] = True             # c1 ends ok on A under the bar
    code, out, err = _run(["report", "--log", str(_log(tmp_path, records)), "--cache"])
    assert (code, err) == (0, "")
    header, _, row_b, row_a = out.splitlines()
    assert header.split() == ["model", "calls", "attempts", "errors", "invalid", "fallback_calls",
                              "fallback_rate", "below_bar_calls", "cost_usd", "routing_cost_usd",
                              "p50_ms", "p95_ms"] + CACHE_KEYS
    assert row_a.split()[7:] == ["1", "0.100000", "0.100000", "10.0", "10.0", "900", "1000", "0.900"]
    assert row_b.split()[7:] == ["0", "0.300000", "0.300000", "10.0", "10.0", "0", "0", "n/a"]


def test_the_cli_json_has_the_three_keys_with_null(tmp_path):
    code, out, err = _run(["report", "--log", str(_log(tmp_path, _cli_records())), "--cache", "--json"])
    assert (code, err) == (0, "")
    rows = json.loads(out)
    assert [list(row) for row in rows] == [V1_589_KEYS + CACHE_KEYS] * 2
    assert _by_group(rows) == {B: (0, 0, None), A: (900, 1_000, 0.9)}


def test_the_cli_with_audits_and_cache_puts_the_cache_columns_last(tmp_path):
    audits = tmp_path / "audits.jsonl"
    audits.write_text('{"call_id": "c1", "correct": true}\n{"call_id": "c2", "correct": false}\n',
                      encoding="utf-8")
    code, out, err = _run(["report", "--log", str(_log(tmp_path, _cli_records())),
                           "--audits", str(audits), "--cache"])
    assert (code, err) == (0, "")
    header = out.splitlines()[0].split()
    assert header[-7:] == AUDIT_KEYS + CACHE_KEYS


def test_a_refused_count_exits_2_with_one_error_line(tmp_path):
    records = _cli_records() + [_rec("c9", A, 0, True, "ok", 0.1, 10, 1, cached_input_tokens=11)]
    code, out, err = _run(["report", "--log", str(_log(tmp_path, records)), "--cache"])
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1 and "c9" in err


# ---- the spec -----------------------------------------------------------------------------------

def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for start, end, opening in [
            ("### 8.3 ", "## 9. ", '- v1.590 `report(records, by="model", audits=None, cache=False)` '
                                   "(row CACHE1f)"),
            ("## 10. ", "## 11. ", "  - v1.590 `--cache` (row CACHE1f)")]:
        part = design[design.index(start):design.index(end)]
        assert part.count(opening) == 1, start
    # v1.611 (row CANARY1c) adds `[--shadow]` after `[--cache]`, v1.693 (row CACHE2b) `[--anomalies]` after it
    assert "- `report --log PATH [--by KEY] [--json] [--audits PATH] [--cache] [--shadow] [--anomalies]`" in design
    assert "its hit rate is row CACHE1f (done in v1.590, 8.3 and 10" in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.590 (")]
    assert len(mine) == 1 and "(8.1, 8.3, 10, row CACHE1f)" in mine[0]
