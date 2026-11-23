"""DESIGN 6, 7 and 8.1 v1.589 (row CACHE1c): the cache counts a provider returns, in the records.

`Completion` and `Attempt` gain `cached_input_tokens` and `cache_write_tokens`, `None` when the
provider did not say. The OpenAI-compatible adapter reads `usage.prompt_tokens_details.cached_tokens`
(the chat completions usage object has no write count), the executor prices each attempt at the
counts through `Model.cost`, and a record gains each count right after `output_tokens` only when
its provider returned it, so every record without them keeps v1.588's keys and the demo log its
bytes. `report` reads neither key (row CACHE1f). The contract tests were written under strict xfail
and the implementing commit removed the marks; the unmarked guards pin what v1.589 keeps and passed
before and after it.
"""

import dataclasses
import hashlib
import io
import json
from pathlib import Path

import pytest

from model_routing import (Attempt, Cascade, Completion, Executor, FakeProvider, Model, Monitor,
                           OpenAICompatibleProvider, Procedure, ProcedureResult, ProviderError,
                           Registry, Router, Stats, Task, report, run_demo)

ROOT = Path(__file__).resolve().parents[1]
TS = "2026-11-22T00:00:00Z"
PRICEY, CHEAP = "fiction/pricey", "fiction/cheap"
# the 4.1 v1.587 worked example: 3.0 in, 0.3 cached, 3.75 written, 15.0 out, against 2.0 in
REGISTRY = Registry([
    Model(PRICEY, "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3, price_cache_write=3.75),
    Model(CHEAP, "fam-b", 2.0, 15.0, 200_000),
])
V1_588_KEYS = ["ts", "call_id", "task", "flavor", "model", "family", "attempt", "final", "outcome",
               "error", "latency_ms", "input_tokens", "output_tokens", "cost_usd",
               "routing_cost_usd", "below_bar", "basis", "tags", "slice", "prompt_tokens",
               "prompt_tokens_estimated"]
AFTER = V1_588_KEYS.index("output_tokens") + 1
WITH_CACHED = V1_588_KEYS[:AFTER] + ["cached_input_tokens"] + V1_588_KEYS[AFTER:]
WITH_WRITE = V1_588_KEYS[:AFTER] + ["cache_write_tokens"] + V1_588_KEYS[AFTER:]
WITH_BOTH = V1_588_KEYS[:AFTER] + ["cached_input_tokens", "cache_write_tokens"] + V1_588_KEYS[AFTER:]
# the demo's calls.jsonl, unchanged since v1.536 (tests/test_pricing_basis_records.py)
DEMO_CALLS_SHA256 = "4f111326781939140bebe04e0841a66306cac48492bc6c95f4bc2211fa92b351"
MSGS = [{"role": "user", "content": "hi"}]


def stats(pricey=(99, 100), cheap=(99, 100)):
    planted = Stats()
    planted.add("t", PRICEY, *pricey)
    planted.add("t", CHEAP, *cheap)
    return planted


def executor(script, planted=None, task=None):
    monitor = Monitor()
    ticks = iter(0.5 * i for i in range(1000))
    task = Task("t", bar=0.7, min_samples=10) if task is None else task
    router = Router(REGISTRY, {"t": task}, stats() if planted is None else planted)
    return Executor(router, FakeProvider(script), monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: TS, id_factory=lambda: "call-1"), monitor


def answer(text="ok", tin=10_000, tout=500, **counts):
    return lambda messages: Completion(text, tin, tout, **counts)


def adapter(usage):
    body = json.dumps({"choices": [{"message": {"content": "v"}}], "usage": usage}).encode()
    return OpenAICompatibleProvider("https://example.org/v1",
                                    opener=lambda request, timeout: io.BytesIO(body))


def cost(model_id, *args, **counts):
    return REGISTRY.get(model_id).cost(*args, **counts)


# --- 6: the completion and the adapter -------------------------------------------------------

def test_completion_gains_the_two_counts_last_both_unknown_by_default():
    assert [f.name for f in dataclasses.fields(Completion)] == [
        "text", "input_tokens", "output_tokens", "cached_input_tokens", "cache_write_tokens"]
    plain = Completion("a", 10, 2)
    assert (plain.cached_input_tokens, plain.cache_write_tokens) == (None, None)
    assert plain == Completion("a", 10, 2, None, None) != Completion("a", 10, 2, 0, None)


def test_the_adapter_reads_cached_tokens_counted_inside_prompt_tokens():
    usage = {"prompt_tokens": 10_000, "completion_tokens": 500,
             "prompt_tokens_details": {"cached_tokens": 9_000, "audio_tokens": 0}}
    assert adapter(usage).complete("fiction/a", MSGS, 5) == Completion("v", 10_000, 500, 9_000, None)


@pytest.mark.parametrize("cached", [0, 13])
def test_a_zero_or_whole_prompt_count_is_a_count(cached):
    usage = {"prompt_tokens": 13, "completion_tokens": 5,
             "prompt_tokens_details": {"cached_tokens": cached}}
    got = adapter(usage).complete("fiction/a", MSGS, 5)
    assert got.cached_input_tokens == cached and got.cached_input_tokens is not None


def test_the_adapter_never_reports_a_cache_write():
    usage = {"prompt_tokens": 13, "completion_tokens": 5,
             "prompt_tokens_details": {"cached_tokens": 3, "cache_write_tokens": 4}}
    got = adapter(usage).complete("fiction/a", MSGS, 5)
    assert (got.cached_input_tokens, got.cache_write_tokens) == (3, None)


@pytest.mark.parametrize("details", [
    "absent", None, {}, {"cached_tokens": None}, {"audio_tokens": 3}])
def test_an_absent_or_null_count_is_unknown(details):
    usage = {"prompt_tokens": 13, "completion_tokens": 5}
    if details != "absent":
        usage["prompt_tokens_details"] = details
    got = adapter(usage).complete("fiction/a", MSGS, 5)
    assert got == Completion("v", 13, 5)
    assert getattr(got, "cached_input_tokens", None) is None
    assert getattr(got, "cache_write_tokens", None) is None


@pytest.mark.parametrize("details", [
    "x", [9], 5, False, {"cached_tokens": -1}, {"cached_tokens": True}, {"cached_tokens": 1.5},
    {"cached_tokens": "9"}, {"cached_tokens": 14}])
def test_a_malformed_count_or_details_is_a_bad_response(details):
    usage = {"prompt_tokens": 13, "completion_tokens": 5, "prompt_tokens_details": details}
    with pytest.raises(ProviderError, match="unexpected response shape") as caught:
        adapter(usage).complete("fiction/a", MSGS, 5)
    assert caught.value.status is None


# --- 7 and 8.1: the attempt, its cost and its record -----------------------------------------

def test_attempt_gains_the_two_counts_last_both_unknown_by_default():
    names = [f.name for f in dataclasses.fields(Attempt)]
    assert names[-2:] == ["cached_input_tokens", "cache_write_tokens"] and len(names) == 9
    plain = Attempt("m", "ok", None, 1.0, 10, 2, 0.1)
    assert (plain.cached_input_tokens, plain.cache_write_tokens) == (None, None)


def test_a_call_with_cached_reads_is_priced_at_the_cached_price():
    run, monitor = executor({PRICEY: answer(cached_input_tokens=9_000)})
    result = run.call("t", MSGS, exclude_models=[CHEAP])
    [attempt] = result.attempts
    assert (attempt.cached_input_tokens, attempt.cache_write_tokens) == (9_000, None)
    # 1,000 uncached at 3.0, 9,000 cached at 0.3 and 500 out at 15.0, against 0.0375 unmeasured
    assert attempt.cost_usd == cost(PRICEY, 10_000, 500, cached_input_tokens=9_000)
    assert attempt.cost_usd == pytest.approx(0.0132)
    [rec] = monitor.records
    assert list(rec) == WITH_CACHED
    assert (rec["input_tokens"], rec["cached_input_tokens"]) == (10_000, 9_000)
    assert rec["cost_usd"] == rec["routing_cost_usd"] == attempt.cost_usd


def test_a_write_is_priced_at_its_premium_and_both_keys_keep_their_order():
    run, monitor = executor({PRICEY: answer(cached_input_tokens=0, cache_write_tokens=9_000)})
    [attempt] = run.call("t", MSGS, exclude_models=[CHEAP]).attempts
    assert attempt.cost_usd == cost(PRICEY, 10_000, 500, cache_write_tokens=9_000)
    assert attempt.cost_usd == pytest.approx(0.04425)
    [rec] = monitor.records
    assert list(rec) == WITH_BOTH
    assert (rec["cached_input_tokens"], rec["cache_write_tokens"]) == (0, 9_000)


def test_a_write_alone_writes_its_key_alone():
    run, monitor = executor({PRICEY: answer(cache_write_tokens=9_000)})
    [attempt] = run.call("t", MSGS, exclude_models=[CHEAP]).attempts
    assert (attempt.cached_input_tokens, attempt.cache_write_tokens) == (None, 9_000)
    assert attempt.cost_usd == pytest.approx(0.04425)
    [rec] = monitor.records
    assert list(rec) == WITH_WRITE


def test_an_unknown_cache_price_is_the_input_price_in_the_record():
    run, monitor = executor({CHEAP: answer(cached_input_tokens=9_000)})
    [attempt] = run.call("t", MSGS, exclude_models=[PRICEY]).attempts
    assert attempt.cost_usd == cost(CHEAP, 10_000, 500) == pytest.approx(0.0275)
    [rec] = monitor.records
    assert list(rec) == WITH_CACHED and rec["cached_input_tokens"] == 9_000


def test_an_invalid_attempt_keeps_its_counts_and_the_fallback_has_its_own():
    run, monitor = executor({CHEAP: answer("bad", cached_input_tokens=100),
                             PRICEY: answer("good", cached_input_tokens=9_000)})
    result = run.call("t", MSGS, validate=lambda text: text == "good")
    invalid, ok = result.attempts
    assert (invalid.model, invalid.outcome, invalid.cached_input_tokens) == (CHEAP, "invalid", 100)
    assert invalid.cost_usd == cost(CHEAP, 10_000, 500, cached_input_tokens=100)
    assert (ok.model, ok.outcome, ok.cached_input_tokens) == (PRICEY, "ok", 9_000)
    assert [(r["model"], r["cached_input_tokens"]) for r in monitor.records] == [
        (CHEAP, 100), (PRICEY, 9_000)]
    assert all(list(r) == WITH_CACHED for r in monitor.records)


def test_an_error_attempt_has_no_counts():
    def down(messages):
        raise ProviderError("down")
    run, monitor = executor({CHEAP: down, PRICEY: answer(cached_input_tokens=9_000)})
    error, ok = run.call("t", MSGS).attempts
    assert (error.outcome, error.cached_input_tokens, error.cache_write_tokens) == ("error", None, None)
    assert ok.cached_input_tokens == 9_000
    first, second = monitor.records
    assert list(first) == V1_588_KEYS and list(second) == WITH_CACHED


@pytest.mark.parametrize("counts, named", [
    ({"cached_input_tokens": 10_001}, "is over input_tokens"),
    ({"cached_input_tokens": 6_000, "cache_write_tokens": 5_000}, "is over input_tokens"),
    ({"cached_input_tokens": True}, "cached_input_tokens must be an int"),
    ({"cached_input_tokens": -1}, "cached_input_tokens must be an int"),
    ({"cached_input_tokens": 5.0}, "cached_input_tokens must be an int"),
    ({"cache_write_tokens": "9"}, "cache_write_tokens must be an int"),
])
def test_counts_the_cost_refuses_raise_before_any_record(counts, named):
    run, monitor = executor({PRICEY: answer(**counts)})
    with pytest.raises(ValueError, match=named):
        run.call("t", MSGS, exclude_models=[CHEAP])
    assert monitor.records == []


def test_each_leg_of_a_cascade_carries_its_own_counts():
    task = Task("t", bar=0.7, min_samples=10, cascades=(Cascade(CHEAP, PRICEY, "sig"),))
    planted = stats(pricey=(0, 100), cheap=(0, 100))
    planted.add("t", task.cascades[0].id, 99, 100, escalated=10)
    run, monitor = executor({CHEAP: answer("cheap", cached_input_tokens=100),
                             PRICEY: answer("strong", cached_input_tokens=9_000)}, planted, task)
    result = run.call("t", MSGS, signals={"sig": lambda text: text == "cheap"})
    assert result.model == PRICEY
    cheap, strong = monitor.records
    assert (cheap["model"], cheap["cached_input_tokens"]) == (CHEAP, 100)
    assert (strong["model"], strong["cached_input_tokens"]) == (PRICEY, 9_000)
    assert strong["cost_usd"] == cost(PRICEY, 10_000, 500, cached_input_tokens=9_000)
    for rec in (cheap, strong):
        keys = list(rec)
        assert keys.index("cached_input_tokens") == keys.index("output_tokens") + 1


def test_a_procedures_model_call_carries_the_counts_and_its_closing_record_does_not():
    proc = Procedure("poll", "v1", lambda value, call: ProcedureResult("shaped " + call(value)),
                     max_model_calls=1, max_tool_calls=0, model=PRICEY)
    planted = stats(pricey=(0, 100), cheap=(0, 100))
    planted.add("t", proc.id, 99, 100, cost_usd=0.0001)
    run, monitor = executor({PRICEY: answer(cached_input_tokens=9_000)}, planted)
    result = run.call("t", MSGS, procedures=[proc])
    assert result.model == proc.id
    model_call, closing = monitor.records
    assert model_call["cached_input_tokens"] == 9_000
    assert model_call["cost_usd"] == cost(PRICEY, 10_000, 500, cached_input_tokens=9_000)
    assert "cached_input_tokens" not in closing and "cache_write_tokens" not in closing
    assert (result.attempts[-1].cached_input_tokens, result.attempts[-1].cache_write_tokens) == (None, None)


def test_a_delegated_hand_off_carries_the_counts():
    router = Router(REGISTRY, {"t": Task("t", bar=0.7, min_samples=10)}, stats())
    decision = router.decide_delegation("t", PRICEY, "cost_effective", context_tokens=50_000,
                                        brief_tokens=100, result_tokens=20)
    assert decision.mode == "delegate"
    monitor = Monitor()
    ticks = iter(0.5 * i for i in range(1000))
    run = Executor(router, FakeProvider({m: answer(cached_input_tokens=9_000) for m in (PRICEY, CHEAP)}),
                   monitor=monitor, clock=lambda: next(ticks), now=lambda: TS,
                   id_factory=lambda: "call-1")
    run.call_delegated(decision, MSGS)
    rec = monitor.records[0]
    assert rec["cached_input_tokens"] == 9_000 and rec["tags"]["delegated"] == "true"
    keys = list(rec)
    assert keys.index("cached_input_tokens") == keys.index("output_tokens") + 1


# --- what v1.589 keeps -----------------------------------------------------------------------

def test_a_completion_without_counts_keeps_v1_588_records_and_costs():
    run, monitor = executor({PRICEY: answer()})
    [attempt] = run.call("t", MSGS, exclude_models=[CHEAP]).attempts
    assert attempt.cost_usd == cost(PRICEY, 10_000, 500) == pytest.approx(0.0375)
    assert getattr(attempt, "cached_input_tokens", None) is None
    assert getattr(attempt, "cache_write_tokens", None) is None
    [rec] = monitor.records
    assert list(rec) == V1_588_KEYS


def test_a_providers_own_completion_type_with_three_fields_still_works():
    @dataclasses.dataclass(frozen=True)
    class Legacy:
        text: str
        input_tokens: int
        output_tokens: int

    run, monitor = executor({PRICEY: lambda messages: Legacy("ok", 10_000, 500)})
    [attempt] = run.call("t", MSGS, exclude_models=[CHEAP]).attempts
    assert attempt.cost_usd == cost(PRICEY, 10_000, 500)
    assert getattr(attempt, "cached_input_tokens", None) is None
    [rec] = monitor.records
    assert list(rec) == V1_588_KEYS


def test_the_demo_log_keeps_its_bytes(tmp_path):
    run_demo(tmp_path)
    digest = hashlib.sha256((tmp_path / "calls.jsonl").read_bytes()).hexdigest()
    assert digest == DEMO_CALLS_SHA256


def test_report_reads_neither_count():
    run, monitor = executor({PRICEY: answer()})
    run.call("t", MSGS, exclude_models=[CHEAP])
    [plain] = monitor.records
    keys = list(plain)
    counted = dict(zip(keys[:AFTER], [plain[k] for k in keys[:AFTER]]))
    counted.update(cached_input_tokens=9_000, cache_write_tokens=500)
    counted.update((k, plain[k]) for k in keys[AFTER:])
    for by in ("model", "task", "flavor", "family", "pricing_basis"):
        assert report([counted], by=by) == report([plain], by=by)
    assert report([counted])[0]["input_tokens"] == 10_000


def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for start, end, opening in [
            ("## 6. ", "## 7. ", "- v1.589 cache counts (row CACHE1c): `Completion` gains two last fields"),
            ("## 7. ", "## 8. ", "- v1.589 cache counts (row CACHE1c): `Attempt` gains two last fields"),
            ("### 8.1 ", "### 8.2 ", "- v1.589 `cached_input_tokens` (int) and `cache_write_tokens` (int)")]:
        part = design[design.index(start):design.index(end)]
        assert part.count(opening) == 1, start
    assert "the records' counts are row CACHE1c (done in v1.589, 7 and 8.1)" in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.589 (")]
    assert len(mine) == 1 and "(6, 7, 8.1, row CACHE1c)" in mine[0]


def test_the_production_note_says_the_records_carry_the_counts():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    for gone in ("the delegation decision and the attempt records pass none yet",
                 "and its cost, with no cached or written tokens",
                 "no record prices a cache write yet",
                 "The change: cached and written tokens in the attempt records"):
        assert gone not in note, gone
    for kept in ("The attempt records carry the cached and written tokens a provider returns, each "
                 "attempt priced at them. A cascade's legs, a procedure's model and the delegation "
                 "decision pass none yet",
                 "a record prices the cache writes its provider returns, as a route prices its "
                 "measured ones",
                 "the monitor records each attempt's input and output tokens, the cached and "
                 "written tokens its provider returns"):
        assert note.count(kept) == 1, kept
