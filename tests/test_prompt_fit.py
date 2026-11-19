"""DESIGN 5.2, 7, 8.1 and 10 v1.507 (row FIT1): the per-call context fit.

`Router.select(prompt_tokens=...)` checks rule 5 against the call's own size in place of the
task's declared input, `Executor.call` passes the caller's count or `estimate_prompt_tokens`
of its messages, every `.call` record ends with `prompt_tokens` and `prompt_tokens_estimated`,
and `select --prompt-tokens N` passes the size from the command line. The tests marked `RED`
fail until row FIT1b implements v1.507 (strict, so one that passes early fails the suite); the
unmarked ones guard what v1.507 keeps and pass before and after it.
"""

import json
from dataclasses import asdict
from pathlib import Path

import pytest

import model_routing
from model_routing import (
    Completion, Executor, FakeProvider, Monitor, NoModelClearsBar, ProviderError, Registry,
    Router,
)
from model_routing.cli import main

RED = pytest.mark.xfail(strict=True, reason="row FIT1b implements DESIGN v1.507")

README = Path(__file__).resolve().parents[1] / "README.md"

V1_506_KEYS = ["ts", "call_id", "task", "flavor", "model", "family", "attempt", "final",
               "outcome", "error", "latency_ms", "input_tokens", "output_tokens", "cost_usd",
               "routing_cost_usd", "below_bar", "basis", "tags"]

# fiction/cheap holds the task's declared 1,000 + 200 tokens but not 1,900 + 200.
WINDOWS = {"fiction/cheap": 2000, "fiction/mid": 8000, "fiction/best": 8000}
LONG = [{"role": "user", "content": "x" * 7600}]  # 7,600 characters: 1,900 estimated tokens


@pytest.fixture
def fit_registry(model_factory):
    return Registry([
        model_factory("fiction/cheap", "small", 1.0, 2.0, WINDOWS["fiction/cheap"]),
        model_factory("fiction/mid", "medium", 3.0, 6.0, WINDOWS["fiction/mid"]),
        model_factory("fiction/best", "large", 10.0, 20.0, WINDOWS["fiction/best"]),
    ])


@pytest.fixture
def fit_router(fit_registry, task_factory, measured_stats):
    def make(**task_overrides):
        task = task_factory(**task_overrides)
        return Router(fit_registry, {task.name: task}, measured_stats)
    return make


def reasons(decision_or_candidates):
    candidates = getattr(decision_or_candidates, "candidates", decision_or_candidates)
    return {c.model_id: c.reason for c in candidates}


def executor_for(router, script, monitor):
    ticks = iter(float(t) for t in range(100))
    return Executor(router, FakeProvider(script), monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: "2026-01-02T03:04:05Z", id_factory=lambda: "fixed-call")


def ok(text="done", tokens=(1900, 10)):
    return lambda messages: Completion(text, *tokens)


def outage(messages):
    raise ProviderError("outage")


# --- guards: what v1.507 keeps ------------------------------------------------------------

def test_without_prompt_tokens_rule_5_reads_the_declared_size(fit_router):
    decision = fit_router().select("judge")
    assert decision.primary == "fiction/cheap"
    assert decision.fallbacks == ("fiction/mid", "fiction/best")
    assert set(reasons(decision).values()) == {"passes"}


# --- Router.select(prompt_tokens=...) -----------------------------------------------------

@RED
@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_a_model_that_holds_the_declared_size_but_not_the_call_is_ruled_out(fit_router, flavor):
    decision = fit_router().select("judge", flavor=flavor, prompt_tokens=1900)
    cheap = next(c for c in decision.candidates if c.model_id == "fiction/cheap")
    assert (cheap.reason, cheap.eligible, cheap.passes) == ("context_too_small", False, False)
    assert "fiction/cheap" not in (decision.primary, *decision.fallbacks)
    assert reasons(decision)["fiction/mid"] == reasons(decision)["fiction/best"] == "passes"


@RED
def test_a_call_exactly_at_the_window_fits(fit_router):
    decision = fit_router().select("judge", prompt_tokens=1800)
    assert decision.primary == "fiction/cheap"
    assert reasons(decision)["fiction/cheap"] == "passes"


@RED
def test_prompt_tokens_changes_no_price(fit_router, fit_registry):
    plain = fit_router().select("judge")
    sized = fit_router().select("judge", prompt_tokens=5000)
    for before, after in zip(plain.candidates, sized.candidates):
        assert (after.list_cost, after.routing_cost) == (before.list_cost, before.routing_cost)
    mid = next(c for c in sized.candidates if c.model_id == "fiction/mid")
    assert mid.list_cost == fit_registry.get("fiction/mid").cost(1000, 200)


@RED
@pytest.mark.parametrize("policy", ["refuse", "best_available"])
def test_no_model_holds_the_call(fit_router, policy):
    with pytest.raises(NoModelClearsBar) as caught:
        fit_router(on_no_model=policy).select("judge", prompt_tokens=10_000)
    assert set(reasons(caught.value.candidates).values()) == {"context_too_small"}


@RED
@pytest.mark.parametrize("bad", [-1, True, False, 1.5, "100", [1]])
def test_select_rejects_a_prompt_tokens_that_is_no_count(fit_router, bad):
    with pytest.raises(ValueError):
        fit_router().select("judge", prompt_tokens=bad)


# --- estimate_prompt_tokens ----------------------------------------------------------------

@RED
def test_estimate_is_exported():
    assert "estimate_prompt_tokens" in model_routing.__all__
    assert callable(model_routing.estimate_prompt_tokens)


@RED
@pytest.mark.parametrize("messages, chars_per_token, expected", [
    ([], 4.0, 0),
    ([{"role": "user", "content": "abcd"}], 4.0, 1),
    ([{"role": "user", "content": "abcde"}], 4.0, 2),
    ([{"role": "user", "content": "abcde"}], 2.0, 3),
    ([{"role": "user", "content": "ab"}, {"role": "assistant", "content": "ab"}], 4.0, 1),
    ([{"role": "user", "content": [{"type": "text", "text": "abc"},
                                   {"type": "image_url", "image_url": {"url": "x" * 40}},
                                   {"type": "text", "text": "defgh"}]}], 4.0, 2),
    ([{"role": "user", "content": None}, {"role": "tool"}], 4.0, 0),
    ([{"role": "user", "content": [{"type": "text", "text": 7}, "loose"]}], 4.0, 0),
    (LONG, 4.0, 1900),
])
def test_estimate_arithmetic(messages, chars_per_token, expected):
    from model_routing import estimate_prompt_tokens
    assert estimate_prompt_tokens(messages, chars_per_token=chars_per_token) == expected
    if chars_per_token == 4.0:
        assert estimate_prompt_tokens(messages) == expected


@RED
@pytest.mark.parametrize("bad", [0, 0.0, -1.0, True, float("nan"), float("inf"), "4"])
def test_estimate_rejects_a_bad_ratio(bad):
    from model_routing import estimate_prompt_tokens
    with pytest.raises(ValueError):
        estimate_prompt_tokens(LONG, chars_per_token=bad)


# --- Executor.call ------------------------------------------------------------------------

@RED
def test_the_executor_never_sends_a_call_to_a_model_too_small_for_it(fit_router):
    monitor = Monitor()
    executor = executor_for(fit_router(), {"fiction/cheap": ok(), "fiction/mid": outage,
                                           "fiction/best": ok()}, monitor)
    result = executor.call("judge", LONG)
    assert [model for model, _ in executor.provider.calls] == ["fiction/mid", "fiction/best"]
    assert result.model == "fiction/best"
    for record in monitor.records:
        assert list(record) == V1_506_KEYS + ["prompt_tokens", "prompt_tokens_estimated"]
        assert type(record["prompt_tokens"]) is int and record["prompt_tokens"] == 1900
        assert record["prompt_tokens_estimated"] is True


@RED
def test_an_explicit_count_overrides_the_estimate_both_ways(fit_router):
    monitor = Monitor()
    executor = executor_for(fit_router(), {"fiction/cheap": ok(), "fiction/mid": ok(),
                                           "fiction/best": ok()}, monitor)
    executor.call("judge", [{"role": "user", "content": "hi"}], prompt_tokens=1900)
    executor.call("judge", LONG, prompt_tokens=100)
    assert [model for model, _ in executor.provider.calls] == ["fiction/mid", "fiction/cheap"]
    assert [(r["prompt_tokens"], r["prompt_tokens_estimated"]) for r in monitor.records] == [
        (1900, False), (100, False)]


@RED
@pytest.mark.parametrize("bad", [-1, True, 2.5, "5"])
def test_a_bad_count_fails_before_any_provider_call_or_record(fit_router, bad):
    monitor = Monitor()
    executor = executor_for(fit_router(), {"fiction/cheap": ok()}, monitor)
    with pytest.raises(ValueError):
        executor.call("judge", LONG, prompt_tokens=bad)
    assert executor.provider.calls == [] and monitor.records == []


# --- CLI select --prompt-tokens -------------------------------------------------------------

@pytest.fixture
def fit_files(cli_files, write_json, fit_registry):
    models = [dict(asdict(model), source="https://example.org/prices")
              for model in fit_registry.models]
    files = dict(cli_files)
    files["registry"] = write_json("fit-models.json", {
        "version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models})
    return files


def select_args(files, *extra):
    args = ["select", "judge"]
    for flag, path in files.items():
        args.extend(["--" + flag, str(path)])
    return args + list(extra)


@RED
def test_cli_select_passes_the_size(fit_files, capsys):
    assert main(select_args(fit_files, "--prompt-tokens", "1900", "--json")) == 0
    decision = json.loads(capsys.readouterr().out)
    assert decision["primary"] == "fiction/mid"
    assert decision["fallbacks"] == ["fiction/best"]
    assert {c["model_id"]: c["reason"] for c in decision["candidates"]}["fiction/cheap"] == (
        "context_too_small")


@RED
@pytest.mark.parametrize("text", ["-1", "1.5", "abc"])
def test_cli_select_rejects_a_bad_size(fit_files, capsys, text):
    assert main(select_args(fit_files, "--prompt-tokens", text)) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.splitlines()[-1] == (
        f"error: argument --prompt-tokens: must be an integer >= 0, got {text!r}")


# --- README ---------------------------------------------------------------------------------

@RED
def test_readme_says_which_sizes_are_declared_measured_and_per_call():
    text = README.read_text(encoding="utf-8")
    section = text.split("\n## How a model is chosen\n", 1)[1].split("\n## ", 1)[0]
    for phrase in ("prompt_tokens", "estimate_prompt_tokens", "--prompt-tokens",
                   "largest single request", "compact", "expected_input_tokens"):
        assert phrase in section, phrase
