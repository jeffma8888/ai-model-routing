"""tau2-bench converter contract (DESIGN 12.14, v1.50 and v1.51), written before the converter and kept as its tests.

The converter is a standard-library script outside the package (``evidence/tau2-bench/convert.py``),
so it is loaded from its path by an autouse fixture. Every test uses small synthetic run dicts
shaped like a run file (top keys timestamp, info, tasks, simulations), except the last, which
reads the pinned files only when all 12 are already in the default cache and skips otherwise
(CI never downloads them).
"""

import ast
import copy
import hashlib
import importlib.util
import io
import json
import math
import random
import urllib.request
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows, split_items

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "tau2-bench" / "convert.py"
EVIDENCE_README = ROOT / "evidence" / "tau2-bench" / "README.md"
REVISION = "033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f"
BASE_URL = f"https://raw.githubusercontent.com/sierra-research/tau2-bench/{REVISION}/data/tau2/results/final/"
TAIL = "_gpt-4.1-2025-04-14_4trials.json"
PINNED = [
    ("claude-3-7-sonnet-20250219_airline_default", 10551448, "40a2c6a246eab27db5cdefda895fbe7f44be78a23d300817248534aa606d66de"),
    ("claude-3-7-sonnet-20250219_retail_default", 24908843, "ed41dbd18c080154156484e3a0122c095e324a11367a640d88e15956daed7b9d"),
    ("claude-3-7-sonnet-20250219_telecom_default", 41190190, "f49e540896fe91ab8631647f02eb777ef6fed5a6ebec545f43e71d0504e227b2"),
    ("gpt-4.1-2025-04-14_airline_default", 8790399, "31d19e79b8ddc5934a60701f913ff5fefb41dee5e68f7b813c26254ab2e2d5c8"),
    ("gpt-4.1-2025-04-14_retail_default", 22044059, "5fc5b96ada0fe46a463eaed98d1bfed9947fe073bac052290162dae18d71394e"),
    ("gpt-4.1-2025-04-14_telecom_default", 37463627, "8e1793f57a9e216514dbce1f93b44b0592d5904f1c5b97ab711906782107a1f2"),
    ("gpt-4.1-mini-2025-04-14_airline_base", 9781836, "41788956547a100fb8e34baf159f36dd1f07f0765798a5fdaf917576c5dba9d0"),
    ("gpt-4.1-mini-2025-04-14_retail_base", 23697012, "6d6badb43b716adca31591b0b40e15fd493b49adddaa8e2c47035bb557549257"),
    ("gpt-4.1-mini-2025-04-14_telecom_base", 51038687, "04fad1a6fb3ff8804be31c54cf5a993b64868e37683c226e014e7adbf60841d9"),
    ("o4-mini-2025-04-16_airline_default", 7599444, "6a3a354c9bce42b52905af096e9cea6f555548acbb17b567fd403c356df7b4ec"),
    ("o4-mini-2025-04-16_retail_default", 22066527, "7135f38bbbbd46d6babe830574c8623bb276d8fd6da316580b905cf513853f98"),
    ("o4-mini-2025-04-16_telecom_default", 36801670, "1f46a6f296694bdb3ae203e6b379cdada0b8f17b648a4cf90d6343de1f1fb070"),
]
EXTRACT_KEYS = ["domain", "agent", "user", "trial", "tokens", "cells", "missing_trial"]
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd"]
TOKEN_ROW_KEYS = ROW_KEYS + ["input_tokens", "output_tokens"]
REPORT_KEYS = ["models", "user_models", "trial", "task_by", "kept", "dropped_incomplete", "rows"]
STDLIB = {"argparse", "hashlib", "json", "math", "re", "sys", "urllib", "pathlib"}


def load_cv():
    if not SCRIPT.is_file():
        raise ModuleNotFoundError(f"no converter at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("tau2_convert", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def cv():
    return load_cv()


def message(role, usage=None, cost=0.0):
    return {"role": role, "content": "x", "tool_calls": None, "turn_idx": 0, "timestamp": "t",
            "cost": cost, "usage": usage, "raw_data": None}


def usage(prompt, completion):
    return {"prompt_tokens": prompt, "completion_tokens": completion}


def sim(task_id, trial, reward=1.0, cost=0.01, turns=((100, 10),)):
    messages = [message("assistant")]
    for prompt, completion in turns:
        messages.append(message("user", usage=usage(9999, 9999), cost=0.5))
        messages.append(message("assistant", usage=usage(prompt, completion), cost=0.001))
        messages.append(message("tool"))
    return {"id": f"{task_id}-{trial}", "task_id": task_id, "timestamp": "t", "start_time": "t",
            "end_time": "t", "duration": 1.0, "termination_reason": "user_stop", "agent_cost": cost,
            "user_cost": 0.002, "reward_info": {"reward": reward, "reward_basis": ["DB"]},
            "messages": messages, "trial": trial, "seed": 1000 + trial}


def default_outcome(agent, task_id, trial):
    code = sum(map(ord, agent + task_id)) + trial
    return (1.0 if code % 2 == 0 else 0.0), round(0.001 * (1 + code % 5) * len(agent), 6)


def run(domain="airline", agent="gpt-alpha-1", user="gpt-user-1", tasks=("0", "1", "2"), trials=(0, 1),
        sims=None):
    if sims is None:
        sims = []
        for trial in trials:
            for task_id in tasks:
                reward, cost = default_outcome(agent, task_id, trial)
                sims.append(sim(task_id, trial, reward, cost))
    return {"timestamp": "2025-06-01T00:00:00",
            "info": {"git_commit": "abc", "num_trials": len(trials), "max_steps": 200, "max_errors": 10,
                     "user_info": {"implementation": "user_simulator", "llm": user, "llm_args": {}},
                     "agent_info": {"implementation": "llm_agent", "llm": agent, "llm_args": {}},
                     "environment_info": {"domain_name": domain, "policy": "p", "tool_defs": None},
                     "seed": 300},
            "tasks": [{"id": task_id, "description": None} for task_id in tasks],
            "simulations": sims}


AGENTS = ("gpt-alpha-1", "claude-beta-2")
MODELS = ["anthropic/claude-beta-2", "openai/gpt-alpha-1"]
DOMAINS = {"airline": ("0", "1"), "retail": ("0", "1", "2")}


def runs(**kwargs):
    return [run(domain=domain, agent=agent, tasks=tasks, **kwargs)
            for domain, tasks in DOMAINS.items() for agent in AGENTS]


def expected_rows(trial=0, task_by="domain"):
    rows = []
    for domain, tasks in DOMAINS.items():
        for task_id in tasks:
            for agent, model in (("claude-beta-2", MODELS[0]), ("gpt-alpha-1", MODELS[1])):
                reward, cost = default_outcome(agent, task_id, trial)
                rows.append({"task": domain if task_by == "domain" else "all", "item": f"{domain}|{task_id}",
                             "model": model, "correct": reward == 1.0, "cost_usd": cost})
    return sorted(rows, key=lambda r: (r["task"], r["item"], r["model"]))


def error(cv, fn, *args, **kwargs):
    with pytest.raises(ValueError) as caught:
        fn(*args, **kwargs)
    return str(caught.value)


# pins and layout

def test_pinned_source(cv):
    assert cv.REVISION == REVISION
    assert cv.LICENCE == "MIT"
    assert cv.BASE_URL == BASE_URL
    assert list(cv.FILES.items()) == [(name + TAIL, (size, sha)) for name, size, sha in PINNED]
    assert list(cv.FILES) == sorted(cv.FILES)
    assert sum(size for _, size, _ in PINNED) == 295933742
    assert min(size for _, size, _ in PINNED) == 7599444 and max(size for _, size, _ in PINNED) == 51038687


def test_standard_library_only():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.update(alias.name.split(".")[0] for alias in node.names)
        elif isinstance(node, ast.ImportFrom):
            names.add((node.module or "").split(".")[0])
    assert names <= STDLIB, names - STDLIB


def test_default_cache_dir_is_outside_the_repo(cv):
    folder = cv.default_cache_dir()
    assert folder == Path.home() / ".cache" / "ai-model-routing-evidence" / "tau2-bench"
    assert ROOT not in folder.parents


def test_verify(cv, tmp_path):
    path = tmp_path / "f.json"
    path.write_bytes(b"abc")
    sha = hashlib.sha256(b"abc").hexdigest()
    cv.verify(path, 3, sha)
    message = error(cv, cv.verify, path, 4, sha)
    assert "4" in message and "3" in message
    message = error(cv, cv.verify, path, 3, "0" * 64)
    assert "0" * 64 in message and sha in message


# fetch

def pin_files(cv, monkeypatch, contents):
    files = {name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in sorted(contents.items())}
    monkeypatch.setattr(cv, "FILES", files)
    return files


def fake_urlopen(served, calls):
    def urlopen(url, *args, **kwargs):
        calls.append(url)
        return io.BytesIO(served[url[len(BASE_URL):]])
    return urlopen


def test_fetch_downloads_missing_files_through_part(cv, monkeypatch, tmp_path):
    contents = {"a.json": b'{"a": 1}', "b.json": b'{"b": 2}'}
    pin_files(cv, monkeypatch, contents)
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen(contents, calls))
    folder = tmp_path / "new" / "cache"
    assert cv.fetch(folder) == folder
    assert calls == [BASE_URL + "a.json", BASE_URL + "b.json"]
    assert sorted(p.name for p in folder.iterdir()) == ["a.json", "b.json"]
    assert (folder / "b.json").read_bytes() == contents["b.json"]


def test_fetch_keeps_a_verified_file(cv, monkeypatch, tmp_path):
    contents = {"a.json": b'{"a": 1}', "b.json": b'{"b": 2}'}
    pin_files(cv, monkeypatch, contents)
    (tmp_path / "a.json").write_bytes(contents["a.json"])
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen(contents, calls))
    cv.fetch(tmp_path)
    assert calls == [BASE_URL + "b.json"]


def test_fetch_leaves_a_bad_present_file_in_place(cv, monkeypatch, tmp_path):
    contents = {"a.json": b'{"a": 1}'}
    pin_files(cv, monkeypatch, contents)
    (tmp_path / "a.json").write_bytes(b'{"a": 2}')
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen(contents, calls))
    assert "a.json" in error(cv, cv.fetch, tmp_path)
    assert (tmp_path / "a.json").read_bytes() == b'{"a": 2}'
    assert calls == []


def test_fetch_removes_the_part_file_when_the_download_fails_its_check(cv, monkeypatch, tmp_path):
    pin_files(cv, monkeypatch, {"a.json": b'{"a": 1}'})
    calls = []
    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen({"a.json": b'{"a": 9}'}, calls))
    error(cv, cv.fetch, tmp_path)
    assert list(tmp_path.iterdir()) == []


class ProtocolBreak(Exception):
    """Stands in for an HTTP protocol error such as an incomplete chunked read, which is not an OSError."""


class BrokenDownload:
    def __init__(self, failure=None):
        self.reads = 0
        self.failure = failure if failure is not None else OSError("connection reset")

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
        self.reads += 1
        if self.reads == 1:
            return b'{"a"'
        raise self.failure


def test_fetch_removes_the_part_file_when_the_download_breaks(cv, monkeypatch, tmp_path):
    pin_files(cv, monkeypatch, {"a.json": b'{"a": 1}'})
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: BrokenDownload())
    with pytest.raises(OSError):
        cv.fetch(tmp_path)
    assert list(tmp_path.iterdir()) == []


@pytest.mark.parametrize("failure", [OSError("connection reset"), ProtocolBreak("incomplete read")])
def test_fetch_raises_a_broken_download_as_an_os_error_naming_the_file(cv, monkeypatch, tmp_path, failure):
    pin_files(cv, monkeypatch, {"a.json": b'{"a": 1}'})
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: BrokenDownload(failure))
    with pytest.raises(OSError) as caught:
        cv.fetch(tmp_path)
    assert "a.json" in str(caught.value) and str(failure) in str(caught.value)
    assert caught.value is failure or caught.value.__cause__ is failure
    assert list(tmp_path.iterdir()) == []


def test_fetch_downloads_with_a_timeout(cv, monkeypatch, tmp_path):
    contents = {"a.json": b'{"a": 1}'}
    pin_files(cv, monkeypatch, contents)
    seen = []

    def urlopen(url, *args, **kwargs):
        seen.append((url, args, kwargs))
        return io.BytesIO(contents["a.json"])

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    cv.fetch(tmp_path)
    assert seen == [(BASE_URL + "a.json", (), {"timeout": 60})]


# model ids

@pytest.mark.parametrize("name, expected", [
    ("claude-3-7-sonnet-20250219", "anthropic/claude-3-7-sonnet-20250219"),
    ("gpt-4.1-2025-04-14", "openai/gpt-4.1-2025-04-14"),
    ("gpt-4.1-mini-2025-04-14", "openai/gpt-4.1-mini-2025-04-14"),
    ("o4-mini-2025-04-16", "openai/o4-mini-2025-04-16"),
    ("o3", "openai/o3"),
])
def test_model_id(cv, name, expected):
    assert cv.model_id(name) == expected


@pytest.mark.parametrize("name", ["", None, 3, "claude-", "gpt-", "openai/gpt-4.1", "vendor/claude-x",
                                  "gemini-2.5-pro", "o-mini", "omni-1", "Claude-3", "o"])
def test_model_id_refuses_a_guess(cv, name):
    error(cv, cv.model_id, name)


# extract

def test_extract_keeps_the_chosen_trial(cv):
    data = run(trials=(0, 1, 2, 3))
    result = cv.extract(data, trial=2)
    assert list(result) == EXTRACT_KEYS
    assert result["domain"] == "airline"
    assert result["agent"] == "openai/gpt-alpha-1" and result["user"] == "openai/gpt-user-1"
    assert result["trial"] == 2 and result["tokens"] is False
    assert list(result["cells"]) == ["0", "1", "2"]
    for task_id, cell in result["cells"].items():
        reward, cost = default_outcome("gpt-alpha-1", task_id, 2)
        assert list(cell) == ["correct", "cost_usd"]
        assert cell["correct"] is (reward == 1.0)
        assert type(cell["cost_usd"]) is float and cell["cost_usd"] == cost
    assert result["missing_trial"] == []


def test_extract_default_is_trial_0_without_tokens(cv):
    data = run()
    assert cv.extract(data) == cv.extract(data, trial=0, tokens=False)
    assert cv.extract(data)["trial"] == 0


def test_extract_writes_costs_as_floats_and_negative_zero_as_zero(cv):
    data = run(tasks=("a", "b"), sims=[sim("a", 0, 1, 0), sim("b", 0, 0, -0.0)])
    cells = cv.extract(data)["cells"]
    assert type(cells["a"]["cost_usd"]) is float and cells["a"]["cost_usd"] == 0.0
    assert math.copysign(1.0, cells["b"]["cost_usd"]) == 1.0
    assert cells["a"]["correct"] is True and cells["b"]["correct"] is False


def test_extract_tokens_sum_the_agent_messages_only(cv):
    data = run(tasks=("a",), sims=[sim("a", 0, turns=((100, 10), (250, 30)))])
    cell = cv.extract(data, tokens=True)["cells"]["a"]
    assert list(cell) == ["correct", "cost_usd", "input_tokens", "output_tokens"]
    assert (cell["input_tokens"], cell["output_tokens"]) == (350, 40)
    assert cv.extract(data, tokens=True)["tokens"] is True


def test_extract_without_tokens_reads_no_message(cv):
    bad = sim("a", 0)
    bad["messages"] = "not a list"
    data = run(tasks=("a",), sims=[bad])
    assert "input_tokens" not in cv.extract(data)["cells"]["a"]
    error(cv, cv.extract, data, tokens=True)


def test_extract_lists_tasks_without_the_trial(cv):
    data = run(tasks=("0", "1", "2"), sims=[sim("0", 0), sim("1", 0), sim("2", 1)])
    result = cv.extract(data)
    assert list(result["cells"]) == ["0", "1"]
    assert result["missing_trial"] == ["2"]
    assert list(cv.extract(data, trial=1)["cells"]) == ["2"]
    assert cv.extract(data, trial=1)["missing_trial"] == ["0", "1"]


def test_extract_checks_reward_and_cost_on_the_chosen_trial_only(cv):
    data = run(tasks=("a",), sims=[sim("a", 0), sim("a", 1, reward=0.5, cost=-1.0)])
    assert list(cv.extract(data)["cells"]) == ["a"]
    error(cv, cv.extract, data, trial=1)


def test_extract_refuses_a_trial_no_simulation_has(cv):
    error(cv, cv.extract, run(trials=(0, 1)), trial=5)


def test_extract_message_names_the_domain_agent_and_task(cv):
    data = run(tasks=("t-17",), sims=[sim("t-17", 0, reward=0.5)])
    message = error(cv, cv.extract, data)
    assert "airline" in message and "openai/gpt-alpha-1" in message and "t-17" in message


def drop(path):
    def mutate(data):
        *head, last = path
        target = data
        for key in head:
            target = target[key]
        del target[last]
    return mutate


def put(path, value):
    def mutate(data):
        *head, last = path
        target = data
        for key in head:
            target = target[key]
        target[last] = value
    return mutate


def on_sim(key, value):
    return put(("simulations", 0, key), value)


def on_reward(value):
    return put(("simulations", 0, "reward_info", "reward"), value)


def append_sim(entry):
    def mutate(data):
        data["simulations"].append(entry)
    return mutate


def agent_usage(value):
    return put(("simulations", 0, "messages", 2, "usage"), value)


BAD_RUNS = {
    "no info": drop(("info",)),
    "no tasks": drop(("tasks",)),
    "no simulations": drop(("simulations",)),
    "info not a dict": put(("info",), []),
    "no environment_info": drop(("info", "environment_info")),
    "domain empty": put(("info", "environment_info", "domain_name"), ""),
    "domain not a string": put(("info", "environment_info", "domain_name"), 3),
    "domain with a bar": put(("info", "environment_info", "domain_name"), "air|line"),
    "agent llm missing": drop(("info", "agent_info", "llm")),
    "agent llm empty": put(("info", "agent_info", "llm"), ""),
    "agent not mapped": put(("info", "agent_info", "llm"), "gemini-x"),
    "user llm missing": drop(("info", "user_info", "llm")),
    "user with a slash": put(("info", "user_info", "llm"), "vendor/gpt-user-1"),
    "tasks not a list": put(("tasks",), {}),
    "task not a dict": put(("tasks", 0), "0"),
    "task id not a string": put(("tasks", 0, "id"), 0),
    "task id empty": put(("tasks", 0, "id"), ""),
    "task id repeats": put(("tasks", 1, "id"), "0"),
    "simulations not a list": put(("simulations",), {}),
    "simulation not a dict": put(("simulations", 0), []),
    "unknown task": on_sim("task_id", "9"),
    "task_id missing": drop(("simulations", 0, "task_id")),
    "trial a bool": on_sim("trial", True),
    "trial a string": on_sim("trial", "0"),
    "trial a float": on_sim("trial", 0.0),
    "trial negative": on_sim("trial", -1),
    "trial repeats": append_sim(sim("0", 0)),
    "reward partial": on_reward(0.5),
    "reward a bool": on_reward(True),
    "reward none": on_reward(None),
    "reward a string": on_reward("1"),
    "reward nan": on_reward(float("nan")),
    "reward 2": on_reward(2),
    "no reward_info": drop(("simulations", 0, "reward_info")),
    "cost negative": on_sim("agent_cost", -0.01),
    "cost nan": on_sim("agent_cost", float("nan")),
    "cost inf": on_sim("agent_cost", float("inf")),
    "cost a bool": on_sim("agent_cost", False),
    "cost a string": on_sim("agent_cost", "0.1"),
    "cost none": on_sim("agent_cost", None),
    "cost too large for a float": on_sim("agent_cost", 10 ** 400),
    "messages not a list": on_sim("messages", "x"),
    "message not a dict": put(("simulations", 0, "messages", 1), []),
    "usage not a dict": agent_usage([1, 2]),
    "usage key missing": drop(("simulations", 0, "messages", 2, "usage")),
    "prompt tokens negative": agent_usage(usage(-1, 10)),
    "prompt tokens a float": agent_usage(usage(1.0, 10)),
    "completion tokens a bool": agent_usage(usage(1, True)),
    "completion tokens missing": agent_usage({"prompt_tokens": 1}),
}


@pytest.mark.parametrize("case", sorted(BAD_RUNS))
def test_extract_refuses_invalid_runs(cv, case):
    data = run()
    BAD_RUNS[case](data)
    error(cv, cv.extract, data, tokens=True)


@pytest.mark.parametrize("data", [[], "run", None, 3])
def test_extract_refuses_a_run_that_is_not_an_object(cv, data):
    error(cv, cv.extract, data)


@pytest.mark.parametrize("kwargs", [{"trial": True}, {"trial": -1}, {"trial": "0"}, {"trial": 1.0},
                                    {"tokens": "yes"}, {"tokens": 1}, {"tokens": None}])
def test_extract_refuses_bad_arguments(cv, kwargs):
    error(cv, cv.extract, run(), **kwargs)


def test_extract_checks_simulations_in_file_order(cv):
    bad_reward = sim("0", 0, reward=0.5)
    unknown = sim("9", 0)
    first = run(tasks=("0",), sims=[bad_reward, unknown])
    assert "reward" in error(cv, cv.extract, first)
    second = run(tasks=("0",), sims=[copy.deepcopy(unknown), copy.deepcopy(bad_reward)])
    message = error(cv, cv.extract, second)
    assert "'9'" in message and "reward" not in message
    third = run(tasks=("0",), sims=[sim("0", 0, cost=-1.0)])
    assert "agent_cost" in error(cv, cv.extract, third)


def test_extract_checks_the_names_before_the_bar_and_the_vendor_rule(cv):
    data = run(domain="air|line", agent="gemini-x")
    del data["info"]["user_info"]["llm"]
    assert "info.user_info.llm" in error(cv, cv.extract, data)
    message = error(cv, cv.extract, run(domain="air|line", agent="gemini-x"))
    assert "air|line" in message and "gemini-x" not in message
    message = error(cv, cv.extract, run(agent="gemini-x", user="vendor/gpt-user-1"))
    assert "gemini-x" in message and "vendor/gpt-user-1" not in message


def test_extract_refuses_a_cost_too_large_for_a_float(cv):
    data = run(tasks=("a",), sims=[sim("a", 0, cost=10 ** 400)])
    assert "agent_cost" in error(cv, cv.extract, data)


def test_extract_checks_arguments_before_the_run(cv):
    assert "trial" in error(cv, cv.extract, [], trial=-1)


# convert

def extracts(cv, trial=0, tokens=False, data=None):
    return [cv.extract(item, trial=trial, tokens=tokens) for item in (data if data is not None else runs())]


def test_convert_rows_and_report(cv):
    rows, report = cv.convert(extracts(cv))
    assert all(list(row) == ROW_KEYS for row in rows)
    assert rows == expected_rows()
    assert list(report) == REPORT_KEYS
    assert report == {"models": MODELS, "user_models": ["openai/gpt-user-1"], "trial": 0, "task_by": "domain",
                      "kept": {"airline": 2, "retail": 3}, "dropped_incomplete": {"airline": 0, "retail": 0},
                      "rows": 10}
    assert list(report["kept"]) == ["airline", "retail"]


def test_convert_pools_the_same_items_with_task_by_all(cv):
    rows, report = cv.convert(extracts(cv, trial=1), task_by="all")
    assert rows == expected_rows(trial=1, task_by="all")
    assert {row["item"] for row in rows} == {row["item"] for row in expected_rows()}
    assert report["kept"] == {"all": 5} and report["dropped_incomplete"] == {"all": 0}
    assert report["task_by"] == "all" and report["trial"] == 1


def test_convert_drops_items_some_agent_lacks(cv):
    full = run(domain="airline", agent="gpt-alpha-1", tasks=("0", "1", "2"))
    partial = run(domain="airline", agent="claude-beta-2", tasks=("0", "1", "7"),
                  sims=[sim("0", 0), sim("1", 1), sim("7", 0)])
    rows, report = cv.convert([cv.extract(full), cv.extract(partial)])
    assert sorted({row["item"] for row in rows}) == ["airline|0"]
    assert report["kept"] == {"airline": 1}
    assert report["dropped_incomplete"] == {"airline": 3}
    assert report["rows"] == 2 == len(rows)


def test_convert_token_rows(cv):
    rows, _ = cv.convert(extracts(cv, tokens=True))
    assert all(list(row) == TOKEN_ROW_KEYS for row in rows)
    assert all((row["input_tokens"], row["output_tokens"]) == (100, 10) for row in rows)


def test_convert_does_not_depend_on_order(cv):
    expected = cv.convert(extracts(cv))
    rng = random.Random(7)
    for _ in range(5):
        data = runs()
        for item in data:
            rng.shuffle(item["simulations"])
            rng.shuffle(item["tasks"])
        rng.shuffle(data)
        assert cv.convert(extracts(cv, data=data)) == expected


def test_convert_leaves_its_input_unchanged(cv):
    given = extracts(cv)
    before = copy.deepcopy(given)
    cv.convert(given)
    assert given == before


def test_convert_rows_are_a_complete_outcome_matrix(cv):
    tasks = tuple(str(i) for i in range(40))
    data = [run(domain=domain, agent=agent, tasks=tasks) for domain in ("airline", "retail") for agent in AGENTS]
    rows, _ = cv.convert(extracts(cv, data=data))
    outcomes = outcomes_from_rows(rows)
    assert len(outcomes) == 160
    result = evaluate(outcomes, bars=[0.5], seeds=[0], min_samples=1)
    assert sorted(result["tasks"]) == ["airline", "retail"]


def mixed(cv, **changes):
    first = cv.extract(run(domain="airline", agent="gpt-alpha-1"))
    second = cv.extract(run(domain="airline", agent="claude-beta-2", **changes))
    return [first, second]


def test_convert_refuses_mixed_runs(cv):
    error(cv, cv.convert, mixed(cv, user="gpt-user-2"))
    first = cv.extract(run(agent="gpt-alpha-1"))
    error(cv, cv.convert, [first, cv.extract(run(agent="claude-beta-2"), trial=1)])
    error(cv, cv.convert, [first, cv.extract(run(agent="claude-beta-2"), tokens=True)])
    error(cv, cv.convert, [first, cv.extract(run(agent="gpt-alpha-1"))])
    error(cv, cv.convert, [first, cv.extract(run(agent="claude-beta-2")),
                           cv.extract(run(domain="retail", agent="gpt-alpha-1"))])


@pytest.mark.parametrize("given", [[], (), None, "runs"])
def test_convert_refuses_no_runs(cv, given):
    error(cv, cv.convert, given)


@pytest.mark.parametrize("task_by", ["domains", "", None, "task"])
def test_convert_refuses_an_unknown_task_by(cv, task_by):
    error(cv, cv.convert, extracts(cv), task_by=task_by)


# files

def test_read_run(cv, tmp_path):
    path = tmp_path / "run.json"
    path.write_text(json.dumps(run()), encoding="utf-8")
    assert cv.read_run(path) == run()
    path.write_text("{not json", encoding="utf-8")
    assert "run.json" in error(cv, cv.read_run, path)


@pytest.mark.parametrize("blob", [b"\xff\xfe{}", b"[" * 200000, b'{"a": 1} trailing'])
def test_read_run_refuses_an_unreadable_file(cv, tmp_path, blob):
    path = tmp_path / "run.json"
    path.write_bytes(blob)
    assert "run.json" in error(cv, cv.read_run, path)


def test_write_jsonl(cv, tmp_path):
    rows = expected_rows()
    path = tmp_path / "m.jsonl"
    cv.write_jsonl(rows, path)
    assert path.read_text(encoding="utf-8") == "".join(json.dumps(row) + "\n" for row in rows)


# CLI

def install(cv, monkeypatch, folder, data):
    contents = {}
    for item in data:
        info = item["info"]
        name = f"{info['agent_info']['llm']}_{info['environment_info']['domain_name']}.json"
        contents[name] = json.dumps(item).encode("utf-8")
    folder.mkdir(parents=True, exist_ok=True)
    for name, blob in contents.items():
        (folder / name).write_bytes(blob)
    pin_files(cv, monkeypatch, contents)
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: pytest.fail("no download expected"))


def test_main_writes_the_matrix_and_prints_the_report(cv, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, runs())
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--cache", str(cache)]) == 0
    captured = capsys.readouterr()
    rows, report = cv.convert(extracts(cv))
    assert captured.out == json.dumps(report, indent=2) + "\n"
    assert captured.err == ""
    assert out.read_text(encoding="utf-8") == "".join(json.dumps(row) + "\n" for row in rows)
    assert not (tmp_path / "m.jsonl.part").exists()


def test_main_options(cv, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, runs())
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--cache", str(cache), "--trial", "1", "--task-by", "all", "--tokens"]) == 0
    rows, report = cv.convert(extracts(cv, trial=1, tokens=True), task_by="all")
    assert json.loads(capsys.readouterr().out) == report
    assert [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()] == rows


@pytest.mark.parametrize("argv", [
    [],
    ["--trial", "0"],
    ["--out", "OUT", "--trial", "-1"],
    ["--out", "OUT", "--trial", "x"],
    ["--out", "OUT", "--trial", "1.0"],
    ["--out", "OUT", "--trial", ""],
    ["--out", "OUT", "--task-by", "domains"],
    ["--out", "OUT", "--bogus"],
    ["--out", ""],
    ["--out", "."],
    ["--out", "/"],
])
def test_main_refuses_bad_options_before_any_download(cv, monkeypatch, tmp_path, capsys, argv):
    monkeypatch.setattr(cv, "fetch", lambda *a, **k: pytest.fail("fetch called for a bad option"))
    out = tmp_path / "m.jsonl"
    assert cv.main([str(out) if arg == "OUT" else arg for arg in argv]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.count("\n") == 1 and captured.err.startswith("error: ")
    assert not out.exists()


def test_main_invalid_data_writes_nothing(cv, monkeypatch, tmp_path, capsys):
    data = runs()
    data[1]["simulations"][0]["reward_info"]["reward"] = 0.5
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, data)
    out = tmp_path / "m.jsonl"
    out.write_text("old\n", encoding="utf-8")
    assert cv.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.count("\n") == 1 and captured.err.startswith("error: ")
    assert out.read_text(encoding="utf-8") == "old\n"
    assert not (tmp_path / "m.jsonl.part").exists()


def test_main_hash_mismatch(cv, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, runs())
    name = sorted(cv.FILES)[0]
    blob = (cache / name).read_bytes()
    (cache / name).write_bytes(blob[:-1] + (b" " if blob[-1:] != b" " else b"\t"))
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--cache", str(cache)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ") and name in err and err.count("\n") == 1
    assert not out.exists()


def test_main_broken_download_writes_nothing(cv, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, runs())
    name = sorted(cv.FILES)[-1]
    (cache / name).unlink()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: BrokenDownload())
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.count("\n") == 1 and captured.err.startswith("error: ")
    assert not out.exists() and not (cache / (name + ".part")).exists()


def test_main_reports_a_protocol_error_on_one_line(cv, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, runs())
    name = sorted(cv.FILES)[0]
    (cache / name).unlink()
    monkeypatch.setattr(urllib.request, "urlopen", lambda *a, **k: BrokenDownload(ProtocolBreak("incomplete read")))
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.count("\n") == 1 and captured.err.startswith("error: ")
    assert name in captured.err and "incomplete read" in captured.err
    assert not out.exists() and not (cache / (name + ".part")).exists()


def test_main_output_folder_missing(cv, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, runs())
    out = tmp_path / "missing" / "m.jsonl"
    assert cv.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.count("\n") == 1 and captured.err.startswith("error: ")
    assert not (tmp_path / "missing").exists()


def test_main_output_that_is_a_folder_is_left_as_it_was(cv, monkeypatch, tmp_path, capsys):
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, runs())
    out = tmp_path / "out"
    out.mkdir()
    (out / "keep.txt").write_text("keep\n", encoding="utf-8")
    assert cv.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.count("\n") == 1 and captured.err.startswith("error: ")
    assert sorted(p.name for p in out.iterdir()) == ["keep.txt"]
    assert not (tmp_path / "out.part").exists()


def test_main_keeps_the_error_on_one_line(cv, monkeypatch, tmp_path, capsys):
    data = [run(domain="air\nline", agent=agent) for agent in AGENTS]
    data[0]["simulations"][0]["reward_info"]["reward"] = 0.5
    cache = tmp_path / "cache"
    install(cv, monkeypatch, cache, data)
    assert cv.main(["--out", str(tmp_path / "m.jsonl"), "--cache", str(cache)]) == 2
    err = capsys.readouterr().err
    assert err.count("\n") == 1 and "air\\nline" in err


# the evidence README (DESIGN 12.14, v1.51)

# The README's default counts as written; test_pinned_files_when_cached builds the same phrases
# from the converter report and rows on the pinned files
README_COUNTS = [
    "keeps 50 airline, 114 retail and 114 telecom tasks, drops none and writes 1,112 rows",
    "0.5 to 0.58 in airline, 0.684 to 0.798 in retail and 0.368 to 0.439 in telecom",
    "`cost_usd` runs from 0.00136 to 6.446604 USD",
    "6,629 to 2,096,093 input tokens and 123 to 26,531 output tokens",
]


def test_evidence_readme():
    text = EVIDENCE_README.read_text(encoding="utf-8")
    for needle in ["https://github.com/sierra-research/tau2-bench", REVISION, "`data/tau2/results/final`",
                   "MIT", "Copyright (c) 2025 Sierra Research", "~/.cache/ai-model-routing-evidence/tau2-bench/",
                   "`reward_info.reward`", "`agent_cost`", "`user_cost`", "airline: 29 tasks differ, retail: 114",
                   "openai/gpt-4.1-2025-04-14", "python evidence/tau2-bench/convert.py --out", "--trial",
                   "--task-by all", "--tokens", "(RESULTS.md)", "DESIGN 12.14", *README_COUNTS]:
        assert needle in text, needle
    for name, size, sha in PINNED:
        assert f"| `{name + TAIL}` | {size:,} | `{sha}` |" in text, name
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text


# the pinned files, only when cached

def test_pinned_files_when_cached(cv, tmp_path, capsys):
    folder = cv.default_cache_dir()
    if not all((folder / (name + TAIL)).is_file() for name, _, _ in PINNED):
        pytest.skip("the 12 pinned tau2-bench run files are not in the default cache")
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--tokens"]) == 0
    report = json.loads(capsys.readouterr().out)
    assert report == {
        "models": ["anthropic/claude-3-7-sonnet-20250219", "openai/gpt-4.1-2025-04-14",
                   "openai/gpt-4.1-mini-2025-04-14", "openai/o4-mini-2025-04-16"],
        "user_models": ["openai/gpt-4.1-2025-04-14"], "trial": 0, "task_by": "domain",
        "kept": {"airline": 50, "retail": 114, "telecom": 114},
        "dropped_incomplete": {"airline": 0, "retail": 0, "telecom": 0}, "rows": 1112}
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    success = {}
    for row in rows:
        success.setdefault(row["task"], {}).setdefault(row["model"], []).append(row["correct"])
    ranges = {task: (round(min(sum(v) / len(v) for v in by.values()), 3), round(max(sum(v) / len(v) for v in by.values()), 3))
              for task, by in success.items()}
    assert ranges == {"airline": (0.5, 0.58), "retail": (0.684, 0.798), "telecom": (0.368, 0.439)}
    assert (min(r["cost_usd"] for r in rows), max(r["cost_usd"] for r in rows)) == (0.0013599999999999999, 6.446604)
    assert (min(r["input_tokens"] for r in rows), max(r["input_tokens"] for r in rows)) == (6629, 2096093)
    assert (min(r["output_tokens"] for r in rows), max(r["output_tokens"] for r in rows)) == (123, 26531)
    kept, spans = report["kept"], {task: f"{low:g} to {high:g} in {task}" for task, (low, high) in ranges.items()}
    built = [f"keeps {kept['airline']} airline, {kept['retail']} retail and {kept['telecom']} telecom tasks, drops "
             f"{'none' if not any(report['dropped_incomplete'].values()) else 'some'} and writes {report['rows']:,} rows",
             f"{spans['airline']}, {spans['retail']} and {spans['telecom']}",
             f"`cost_usd` runs from {round(min(r['cost_usd'] for r in rows), 6)!r} to "
             f"{round(max(r['cost_usd'] for r in rows), 6)!r} USD",
             f"{min(r['input_tokens'] for r in rows):,} to {max(r['input_tokens'] for r in rows):,} input tokens and "
             f"{min(r['output_tokens'] for r in rows):,} to {max(r['output_tokens'] for r in rows):,} output tokens"]
    assert built == README_COUNTS
    halves = {}
    for task in ("airline", "retail", "telecom"):
        items = {row["item"] for row in rows if row["task"] == task}
        sizes = [len(split_items(items, seed)[0]) for seed in range(50)]
        halves[task] = (min(sizes), max(sizes), sum(1 for size in sizes if size < 30))
    assert halves == {"airline": (16, 35, 40), "retail": (45, 65, 0), "telecom": (44, 68, 0)}
    assert sum(1 for seed in range(10) if len(split_items({row["item"] for row in rows if row["task"] == "airline"}, seed)[0]) < 30) == 7
    pooled = [len(split_items({row["item"] for row in rows}, seed)[0]) for seed in range(50)]
    assert (min(pooled), max(pooled)) == (114, 158)
    seeds, stops, totals = set(), {}, {}
    for name, _, _ in PINNED:
        data = cv.read_run(folder / (name + TAIL))
        for entry in data["simulations"]:
            seeds.add((entry["trial"], entry["seed"]))
            stops[entry["termination_reason"]] = stops.get(entry["termination_reason"], 0) + 1
        for trial in range(4):
            result = cv.extract(data, trial=trial)
            assert result["missing_trial"] == []
            totals.setdefault(result["agent"], []).extend(c["cost_usd"] for c in result["cells"].values())
    assert seeds == {(0, 626729), (1, 373753), (2, 361454), (3, 1567)}
    assert stops == {"user_stop": 4412, "max_steps": 36}
    assert round(math.fsum(totals["anthropic/claude-3-7-sonnet-20250219"]), 6) == 487.623954
    assert round(math.fsum(totals["openai/gpt-4.1-mini-2025-04-14"]), 6) == 29.755562
