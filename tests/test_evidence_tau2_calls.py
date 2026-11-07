"""tau2-bench converter, per-call mode (DESIGN 12.14 v1.76), written before the code.

With ``calls``, ``extract`` writes each conversation's agent calls as two lists, the first
prompt and then each prompt less the previous prompt and completion (``call_input_tokens``),
and each completion (``call_output_tokens``), the per-call rows of DESIGN 13.9 v1.74; the
summed counts of ``--tokens`` are then the lists' Rd and O. ``convert`` leaves out, and reports
as ``left_out``, every agent with a negative new input in any cell. The new behaviour is held
under strict xfail markers naming what the v1.75 converter raises: ``TypeError`` where a test
calls ``extract`` with ``calls`` (an unexpected keyword), ``AssertionError`` where it runs
``main`` with ``--calls`` (refused, so ``main`` returns 2) or converts hand-made extracts that
carry ``calls`` (no lists, no ``left_out``, and no error where ``refused`` expects one). The
unmarked tests pass before and after the code: the closed form of the reads, ``convert``
without ``calls``, and, when the 12 pinned files are cached, the bytes v1.75 writes without
``--calls``. The implementing commit, v1.77, removes the markers.
"""

import hashlib
import importlib.util
import json
import random
import statistics
import urllib.request
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "tau2-bench" / "convert.py"
TAIL = "_gpt-4.1-2025-04-14_4trials.json"
EXTRACT_KEYS = ["domain", "agent", "user", "trial", "tokens", "calls", "cells", "missing_trial"]
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd", "input_tokens", "output_tokens"]
CALL_ROW_KEYS = ROW_KEYS + ["call_input_tokens", "call_output_tokens"]
REPORT_KEYS = ["models", "user_models", "trial", "task_by", "kept", "dropped_incomplete", "rows"]
O4 = "openai/o4-mini-2025-04-16"
MINI = "openai/gpt-4.1-mini-2025-04-14"
KEPT = ["anthropic/claude-3-7-sonnet-20250219", "openai/gpt-4.1-2025-04-14", MINI]

NEEDS_CALLS = pytest.mark.xfail(strict=True, raises=TypeError,
                                reason="v1.76 spec: extract(calls=...) lands in v1.77")
NEEDS_MODE = pytest.mark.xfail(strict=True, raises=AssertionError,
                               reason="v1.76 spec: the per-call mode lands in v1.77")


@pytest.fixture
def cv():
    spec = importlib.util.spec_from_file_location("tau2_convert_calls", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def refused(fn, *args, **kwargs):
    """The ValueError message of a call that must be refused; AssertionError if none comes."""
    try:
        fn(*args, **kwargs)
    except ValueError as exc:
        return str(exc)
    raise AssertionError("no ValueError")


def message(role, usage=None):
    return {"role": role, "content": "x", "tool_calls": None, "turn_idx": 0, "timestamp": "t",
            "cost": 0.0, "usage": usage, "raw_data": None}


def sim(task_id, turns, trial=0, reward=1.0, cost=0.01):
    """A conversation: the agent's greeting (usage null), then per turn a user message, an agent call, a tool message."""
    messages = [message("assistant")]
    for prompt, completion in turns:
        messages.append(message("user", {"prompt_tokens": 9999, "completion_tokens": 9999}))
        messages.append(message("assistant", {"prompt_tokens": prompt, "completion_tokens": completion}))
        messages.append(message("tool"))
    return {"id": f"{task_id}-{trial}", "task_id": task_id, "timestamp": "t", "start_time": "t", "end_time": "t",
            "duration": 1.0, "termination_reason": "user_stop", "agent_cost": cost, "user_cost": 0.002,
            "reward_info": {"reward": reward, "reward_basis": ["DB"]}, "messages": messages, "trial": trial,
            "seed": 1000 + trial}


def run(sims, domain="airline", agent="gpt-alpha-1"):
    tasks = sorted({entry["task_id"] for entry in sims})
    return {"timestamp": "2025-06-01T00:00:00",
            "info": {"git_commit": "abc", "num_trials": 1, "max_steps": 200, "max_errors": 10,
                     "user_info": {"implementation": "user_simulator", "llm": "gpt-user-1", "llm_args": {}},
                     "agent_info": {"implementation": "llm_agent", "llm": agent, "llm_args": {}},
                     "environment_info": {"domain_name": domain, "policy": "p", "tool_defs": None},
                     "seed": 300},
            "tasks": [{"id": task_id, "description": None} for task_id in tasks],
            "simulations": sims}


def reads(a, b):
    """13.9 Rd: call j reads a_1..a_j and b_1..b_{j-1}."""
    k = len(a)
    return sum((k - j) * a[j] + (k - j - 1) * b[j] for j in range(k))


def hand_cell(a, b, correct=True, cost=0.01):
    return {"correct": correct, "cost_usd": cost, "input_tokens": reads(a, b), "output_tokens": sum(b),
            "call_input_tokens": list(a), "call_output_tokens": list(b)}


def hand_extract(domain, agent, cells, calls=True, missing=()):
    """An extract as v1.76 specifies it, made by hand so that v1.75's convert can read it."""
    if not calls:
        cells = {t: {k: v for k, v in c.items() if not k.startswith("call_")} for t, c in cells.items()}
    return {"domain": domain, "agent": agent, "user": "openai/gpt-user-1", "trial": 0, "tokens": True,
            "calls": calls, "cells": {t: cells[t] for t in sorted(cells)}, "missing_trial": sorted(missing)}


def three_agents(calls=True):
    good = {"0": hand_cell([100, 40], [10, 20]), "1": hand_cell([120], [30], correct=False)}
    bad = {"0": hand_cell([100, -5], [50, 5]), "1": hand_cell([110, 7], [12, 3])}
    other = {"0": hand_cell([90, 1, 2], [3, 4, 5], correct=False), "1": hand_cell([95], [6])}
    return [hand_extract(domain, agent, cells, calls)
            for domain in ("airline", "retail")
            for agent, cells in (("openai/gpt-a", good), ("openai/gpt-b", bad if domain == "retail" else good),
                                 ("anthropic/claude-c", other))]


# ---- extract ----

@NEEDS_CALLS
def test_extract_writes_each_call_by_position(cv):
    data = run([sim("a", ((100, 10), (150, 20), (400, 5)))])
    result = cv.extract(data, tokens=True, calls=True)
    assert list(result) == EXTRACT_KEYS and result["calls"] is True and result["tokens"] is True
    cell = result["cells"]["a"]
    assert list(cell) == ["correct", "cost_usd", "input_tokens", "output_tokens", "call_input_tokens",
                          "call_output_tokens"]
    # 100, then 150 - 100 - 10 and 400 - 150 - 20; the greeting (usage null) and the user's usage are skipped
    assert cell["call_input_tokens"] == [100, 40, 230] and cell["call_output_tokens"] == [10, 20, 5]
    assert (cell["input_tokens"], cell["output_tokens"]) == (650, 35)
    assert cell["input_tokens"] == reads(cell["call_input_tokens"], cell["call_output_tokens"])


@NEEDS_CALLS
def test_extract_records_a_negative_new_input(cv):
    cell = cv.extract(run([sim("a", ((100, 50), (120, 5)))]), tokens=True, calls=True)["cells"]["a"]
    assert cell["call_input_tokens"] == [100, -30] and cell["call_output_tokens"] == [50, 5]
    assert cell["input_tokens"] == 220 == reads([100, -30], [50, 5])


@NEEDS_CALLS
def test_extract_without_calls_carries_the_key_and_no_lists(cv):
    data = run([sim("a", ((100, 10), (150, 20)))])
    for tokens in (False, True):
        result = cv.extract(data, tokens=tokens, calls=False)
        assert list(result) == EXTRACT_KEYS and result["calls"] is False
        assert "call_input_tokens" not in result["cells"]["a"]
    assert cv.extract(data) == cv.extract(data, calls=False)


@NEEDS_CALLS
def test_extract_calls_needs_tokens(cv):
    assert refused(cv.extract, run([sim("a", ((100, 10),))]), calls=True).startswith("calls needs tokens")


@NEEDS_CALLS
@pytest.mark.parametrize("calls", [1, 0, "yes", None, 1.0])
def test_extract_calls_must_be_a_bool(cv, calls):
    text = refused(cv.extract, run([sim("a", ((100, 10),))]), tokens=True, calls=calls)
    assert text.startswith("calls ") and "is not a bool" in text


@NEEDS_CALLS
def test_extract_checks_tokens_before_calls(cv):
    assert refused(cv.extract, run([sim("a", ((100, 10),))]), tokens="x", calls="y").startswith("tokens ")


@NEEDS_CALLS
def test_extract_refuses_a_conversation_with_no_model_call(cv):
    data = run([sim("a", ((100, 10),)), sim("b", ())])
    text = refused(cv.extract, data, tokens=True, calls=True)
    assert "has no model call" in text and "'b'" in text
    assert cv.extract(data, tokens=True)["cells"]["b"]["input_tokens"] == 0  # without calls, as v1.50


# ---- convert ----

@NEEDS_MODE
def test_convert_leaves_out_an_agent_with_a_negative_new_input(cv):
    rows, report = cv.convert(three_agents())
    assert list(report) == REPORT_KEYS + ["left_out"]
    assert report["models"] == ["anthropic/claude-c", "openai/gpt-a"]
    assert report["left_out"] == {"openai/gpt-b": 1}
    assert report["kept"] == {"airline": 2, "retail": 2} and report["rows"] == 8 == len(rows)
    assert all(list(row) == CALL_ROW_KEYS for row in rows)
    first = rows[0]
    assert (first["item"], first["model"]) == ("airline|0", "anthropic/claude-c")
    assert first["call_input_tokens"] == [90, 1, 2] and first["call_output_tokens"] == [3, 4, 5]
    assert first["input_tokens"] == reads([90, 1, 2], [3, 4, 5])


@NEEDS_MODE
def test_convert_reports_an_empty_left_out(cv):
    extracts = [e for e in three_agents() if e["agent"] != "openai/gpt-b"]
    _, report = cv.convert(extracts)
    assert report.get("left_out") == {} and report["models"] == ["anthropic/claude-c", "openai/gpt-a"]


@NEEDS_MODE
def test_convert_rows_hold_new_lists(cv):
    extracts = three_agents()
    rows, _ = cv.convert(extracts)
    row = next(r for r in rows if r["model"] == "openai/gpt-a" and r["item"] == "airline|0")
    assert "call_input_tokens" in row
    cell = next(e for e in extracts if e["agent"] == "openai/gpt-a" and e["domain"] == "airline")["cells"]["0"]
    assert row["call_input_tokens"] == cell["call_input_tokens"]
    assert row["call_input_tokens"] is not cell["call_input_tokens"]
    assert row["call_output_tokens"] is not cell["call_output_tokens"]


@NEEDS_MODE
def test_convert_counts_kept_items_over_the_kept_agents(cv):
    extracts = three_agents()
    for e in extracts:
        if e["agent"] == "openai/gpt-b" and e["domain"] == "airline":
            del e["cells"]["1"]
            e["missing_trial"] = ["1"]
    rows, report = cv.convert(extracts)
    assert report.get("left_out") == {"openai/gpt-b": 1}
    assert report["kept"] == {"airline": 2, "retail": 2}
    assert report["dropped_incomplete"] == {"airline": 0, "retail": 0}


@NEEDS_MODE
def test_convert_refuses_when_every_agent_is_left_out(cv):
    extracts = [e for e in three_agents() if e["agent"] == "openai/gpt-b"]
    assert refused(cv.convert, extracts).startswith("every agent has a call whose new input is negative")


@NEEDS_MODE
def test_convert_refuses_mixed_calls_settings(cv):
    on, off = three_agents(calls=True), three_agents(calls=False)
    assert "calls setting" in refused(cv.convert, on[:3] + off[3:])


def test_convert_without_calls_is_v150(cv):
    rows, report = cv.convert(three_agents(calls=False))
    assert list(report) == REPORT_KEYS
    assert report["models"] == ["anthropic/claude-c", "openai/gpt-a", "openai/gpt-b"] and report["rows"] == 12
    assert all(list(row) == ROW_KEYS for row in rows)


# ---- the closed form ----

def test_summed_prompts_are_the_reads_of_the_difference_lists():
    rng = random.Random(76)
    for _ in range(2000):
        k = rng.randint(1, 30)
        prompts, completions = [], []
        for j in range(k):
            completions.append(rng.randint(0, 900))
            if j == 0:
                prompts.append(rng.randint(0, 9000))
            else:  # any later prompt, so a difference may be negative
                prompts.append(max(0, prompts[-1] + completions[-2] + rng.randint(-1500, 4000)))
        a = [prompts[0]] + [prompts[j] - prompts[j - 1] - completions[j - 1] for j in range(1, k)]
        assert reads(a, completions) == sum(prompts)


# ---- main ----

def install(cv, monkeypatch, folder, data):
    contents = {f"{d['info']['agent_info']['llm']}_{d['info']['environment_info']['domain_name']}.json":
                json.dumps(d).encode("utf-8") for d in data}
    folder.mkdir(parents=True, exist_ok=True)
    for name, blob in contents.items():
        (folder / name).write_bytes(blob)
    files = {name: (len(blob), hashlib.sha256(blob).hexdigest()) for name, blob in sorted(contents.items())}
    monkeypatch.setattr(cv, "FILES", files)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("no download expected"))


def synthetic_runs():
    turns = {"gpt-alpha-1": ((100, 10), (150, 20)), "claude-beta-2": ((200, 5), (210, 9), (300, 1)),
             "o4-gamma-3": ((100, 50), (120, 5))}  # gamma's second new input is 120 - 100 - 50 = -30
    return [run([sim(t, turns[agent]) for t in ("0", "1")], domain=domain, agent=agent)
            for domain in ("airline", "retail") for agent in turns]


@NEEDS_MODE
def test_main_calls_writes_per_call_rows(cv, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, synthetic_runs())
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--cache", str(cache), "--calls"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report["left_out"] == {"openai/o4-gamma-3": 4}  # one negative entry in each of its 4 cells
    assert report["models"] == ["anthropic/claude-beta-2", "openai/gpt-alpha-1"] and report["rows"] == 8
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert all(list(row) == CALL_ROW_KEYS for row in rows)
    alpha = next(r for r in rows if r["model"] == "openai/gpt-alpha-1")
    assert alpha["call_input_tokens"] == [100, 40] and alpha["call_output_tokens"] == [10, 20]
    assert (alpha["input_tokens"], alpha["output_tokens"]) == (250, 30)


@NEEDS_MODE
def test_main_calls_implies_tokens(cv, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, synthetic_runs())
    one, both = tmp_path / "one.jsonl", tmp_path / "both.jsonl"
    assert cv.main(["--out", str(one), "--cache", str(cache), "--calls"]) == 0
    assert cv.main(["--out", str(both), "--cache", str(cache), "--calls", "--tokens"]) == 0
    assert one.read_bytes() == both.read_bytes()
    printed = capsys.readouterr().out
    assert printed.count('"left_out"') == 2


# ---- the delegation harness reads the rows ----

@NEEDS_CALLS
def test_per_call_rows_feed_the_delegation_harness(cv):
    agents = {"gpt-alpha-1": ((100, 10), (150, 20)), "claude-beta-2": ((200, 5), (210, 9), (300, 1))}
    runs = [run([sim(str(t), turns, reward=float(t % 2)) for t in range(12)], agent=agent)
            for agent, turns in agents.items()]
    rows, report = cv.convert([cv.extract(r, tokens=True, calls=True) for r in runs])
    registry = Registry([Model("openai/gpt-alpha-1", "alpha", 1.0, 4.0, 1_000_000),
                         Model("anthropic/claude-beta-2", "beta", 3.0, 15.0, 1_000_000)])
    point = {"context_tokens": 5000, "brief_tokens": 300, "result_tokens": 200, "carry_turns": 1,
             "inline_separate_call": True}
    result = evaluate_delegation(rows, registry, bars=[0.4], points=[point], seeds=[0], min_samples=1)
    assert result["cells"] and all(cell["expected_work_calls"] in (2, 3) for cell in result["cells"])


# ---- the pinned files, when cached ----

def cached(cv):
    folder = cv.default_cache_dir()
    if not all((folder / name).is_file() for name in cv.FILES):
        pytest.skip("the 12 pinned tau2-bench run files are not in the default cache")
    return folder


def test_pinned_matrices_without_calls_are_the_v175_bytes_when_cached(cv, tmp_path, capsys):
    cached(cv)
    pins = {(): "b2fccfd79c9afa172c4069dfa25a2026c58c50ade0ba5ad9873088a4dd7794b9",
            ("--tokens",): "48da15decc04cf209311199a07f72c4fbef41247779c8961a911cd425d0fb324"}
    for flags, digest in pins.items():
        out = tmp_path / "m.jsonl"
        assert cv.main(["--out", str(out), *flags]) == 0
        assert hashlib.sha256(out.read_bytes()).hexdigest() == digest
    assert '"left_out"' not in capsys.readouterr().out


@NEEDS_MODE
def test_pinned_files_calls_at_trial_0_when_cached(cv, tmp_path, capsys):
    cached(cv)
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--calls"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {"models": KEPT, "user_models": ["openai/gpt-4.1-2025-04-14"], "trial": 0, "task_by": "domain",
                      "kept": {"airline": 50, "retail": 114, "telecom": 114},
                      "dropped_incomplete": {"airline": 0, "retail": 0, "telecom": 0}, "rows": 834,
                      "left_out": {O4: 2962}}
    blob = out.read_bytes()
    assert len(blob) == 341633
    assert hashlib.sha256(blob).hexdigest() == "16dfc0084311273c7321d0c8e8873dbe85ce7c79d5d9e0cc8bde188ee2bb0cd4"
    rows = [json.loads(line) for line in blob.decode("utf-8").splitlines()]
    plain = "".join(json.dumps({k: row[k] for k in ROW_KEYS}) + "\n" for row in rows).encode("utf-8")
    # the --tokens matrix less o4-mini's rows: the summed counts are unchanged by --calls
    assert hashlib.sha256(plain).hexdigest() == "db5ef48f498c5924c13d14718e74f525ef9fa292114eb008d9a51b4b9623c53f"
    calls = {m: [len(r["call_input_tokens"]) for r in rows if r["model"] == m] for m in KEPT}
    spans = {m: (min(k), statistics.median(k), max(k)) for m, k in calls.items()}
    assert spans == {KEPT[0]: (5, 15, 100), KEPT[1]: (2, 12, 99), KEPT[2]: (3, 14, 100)}
    every = [k for ks in calls.values() for k in ks]
    assert (min(every), statistics.median(every), max(every)) == (2, 14, 100)
    first = [r["call_input_tokens"][0] for r in rows]
    assert (min(first), max(first)) == (3252, 8245)
    last = [sum(r["call_input_tokens"]) + sum(r["call_output_tokens"][:-1]) for r in rows]
    assert max(last) == 33765


@NEEDS_CALLS
def test_pinned_files_calls_at_every_trial_when_cached(cv):
    folder = cached(cv)
    data = [cv.read_run(folder / name) for name in cv.FILES]
    seen = {}
    for trial in range(4):
        extracts = [cv.extract(d, trial=trial, tokens=True, calls=True) for d in data]
        _, report = cv.convert(extracts)
        seen[trial] = (report["models"], report["rows"], report["left_out"])
    assert seen == {0: (KEPT, 834, {O4: 2962}), 1: (KEPT[:2], 556, {MINI: 2, O4: 2765}),
                    2: (KEPT[:2], 556, {MINI: 1, O4: 2784}), 3: (KEPT, 834, {O4: 2880})}
