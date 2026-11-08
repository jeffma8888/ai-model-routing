"""Convert the tau2-bench paper results into the evaluator's outcome matrix (DESIGN 12.14).

Usage: python evidence/tau2-bench/convert.py --out PATH [--cache DIR] [--trial N] [--task-by {domain,all}] [--tokens] [--calls]

Standard library only. The 12 default run files of the pinned commit are downloaded into a
cache outside the repo, each checked by size and sha256 before it is read, and read one at a
time. One trial of every task is kept (trial 0 by default), its program-checked reward of 0 or 1
is the label and its recorded ``agent_cost`` is the cost; the user simulator's cost is never
counted. One routing task per domain, or one task ``all`` over every domain. ``--calls`` adds
each conversation's agent calls, every call's new input and output (DESIGN 12.14 v1.76), and
leaves out an agent with a negative new input.
"""

import argparse
import hashlib
import json
import math
import re
import sys
import urllib.request
from pathlib import Path

REPO = "sierra-research/tau2-bench"
REVISION = "033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f"
FOLDER = "data/tau2/results/final"
LICENCE = "MIT"
BASE_URL = f"https://raw.githubusercontent.com/{REPO}/{REVISION}/{FOLDER}/"
TIMEOUT = 60
_TAIL = "_gpt-4.1-2025-04-14_4trials.json"
# name: (bytes, sha256), in ascending name order
FILES = {
    "claude-3-7-sonnet-20250219_airline_default" + _TAIL: (10551448, "40a2c6a246eab27db5cdefda895fbe7f44be78a23d300817248534aa606d66de"),
    "claude-3-7-sonnet-20250219_retail_default" + _TAIL: (24908843, "ed41dbd18c080154156484e3a0122c095e324a11367a640d88e15956daed7b9d"),
    "claude-3-7-sonnet-20250219_telecom_default" + _TAIL: (41190190, "f49e540896fe91ab8631647f02eb777ef6fed5a6ebec545f43e71d0504e227b2"),
    "gpt-4.1-2025-04-14_airline_default" + _TAIL: (8790399, "31d19e79b8ddc5934a60701f913ff5fefb41dee5e68f7b813c26254ab2e2d5c8"),
    "gpt-4.1-2025-04-14_retail_default" + _TAIL: (22044059, "5fc5b96ada0fe46a463eaed98d1bfed9947fe073bac052290162dae18d71394e"),
    "gpt-4.1-2025-04-14_telecom_default" + _TAIL: (37463627, "8e1793f57a9e216514dbce1f93b44b0592d5904f1c5b97ab711906782107a1f2"),
    "gpt-4.1-mini-2025-04-14_airline_base" + _TAIL: (9781836, "41788956547a100fb8e34baf159f36dd1f07f0765798a5fdaf917576c5dba9d0"),
    "gpt-4.1-mini-2025-04-14_retail_base" + _TAIL: (23697012, "6d6badb43b716adca31591b0b40e15fd493b49adddaa8e2c47035bb557549257"),
    "gpt-4.1-mini-2025-04-14_telecom_base" + _TAIL: (51038687, "04fad1a6fb3ff8804be31c54cf5a993b64868e37683c226e014e7adbf60841d9"),
    "o4-mini-2025-04-16_airline_default" + _TAIL: (7599444, "6a3a354c9bce42b52905af096e9cea6f555548acbb17b567fd403c356df7b4ec"),
    "o4-mini-2025-04-16_retail_default" + _TAIL: (22066527, "7135f38bbbbd46d6babe830574c8623bb276d8fd6da316580b905cf513853f98"),
    "o4-mini-2025-04-16_telecom_default" + _TAIL: (36801670, "1f46a6f296694bdb3ae203e6b379cdada0b8f17b648a4cf90d6343de1f1fb070"),
}
TASK_BY = ("domain", "all")


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "tau2-bench"


def sha256_of(path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path, size: int, sha256: str) -> None:
    path = Path(path)
    got_size = path.stat().st_size
    if got_size != size:
        raise ValueError(f"{path.name}: expected {size} bytes, got {got_size}")
    got = sha256_of(path)
    if got != sha256:
        raise ValueError(f"{path.name}: expected sha256 {sha256}, got {got}")


def fetch(cache_dir=None) -> Path:
    """Return the cache folder once every file in FILES is in it and verified."""
    folder = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    folder.mkdir(parents=True, exist_ok=True)
    for name, (size, sha256) in FILES.items():
        target = folder / name
        if target.exists():
            verify(target, size, sha256)
            continue
        part = folder / (name + ".part")
        try:
            with urllib.request.urlopen(BASE_URL + name, timeout=TIMEOUT) as response, part.open("wb") as out:
                for chunk in iter(lambda: response.read(1 << 20), b""):
                    out.write(chunk)
            verify(part, size, sha256)
        except ValueError:
            part.unlink(missing_ok=True)
            raise
        except Exception as exc:
            part.unlink(missing_ok=True)
            raise OSError(f"{name}: download failed: {exc}") from exc
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        part.replace(target)
    return folder


def model_id(llm) -> str:
    """Map a run's model name to a provider-neutral ID by rule; refuse what no rule covers."""
    if not isinstance(llm, str) or not llm:
        raise ValueError(f"model name {llm!r} is not a non-empty string")
    if "/" in llm:
        raise ValueError(f"model name {llm!r} contains '/'; a prefix is never guessed away")
    if llm.startswith("claude-") and len(llm) > len("claude-"):
        return "anthropic/" + llm
    if (llm.startswith("gpt-") and len(llm) > len("gpt-")) or re.match(r"o[0-9]", llm):
        return "openai/" + llm
    raise ValueError(f"model name {llm!r} matches no vendor rule")


def _number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _finite(value) -> bool:
    try:
        return math.isfinite(value)
    except OverflowError:  # an int too large for a float
        return False


def _count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _check_trial(value, label) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"{label} {value!r} is not an int >= 0")


def extract(run, trial=0, tokens=False, calls=False) -> dict:
    """Reduce one parsed run file to the cells of one trial (DESIGN 12.14)."""
    _check_trial(trial, "trial")
    if not isinstance(tokens, bool):
        raise ValueError(f"tokens {tokens!r} is not a bool")
    if not isinstance(calls, bool):
        raise ValueError(f"calls {calls!r} is not a bool")
    if calls and not tokens:
        raise ValueError("calls needs tokens: a per-call row carries the summed counts too")
    if not isinstance(run, dict):
        raise ValueError(f"a run is a {type(run).__name__}, not an object")
    for key in ("info", "tasks", "simulations"):
        if key not in run:
            raise ValueError(f"the run has no {key!r}")
    info = run["info"]
    if not isinstance(info, dict):
        raise ValueError(f"info is a {type(info).__name__}, not an object")

    def name(section, key):
        part = info.get(section)
        value = part.get(key) if isinstance(part, dict) else None
        if not isinstance(value, str) or not value:
            raise ValueError(f"info.{section}.{key} {value!r} is not a non-empty string")
        return value

    domain = name("environment_info", "domain_name")
    agent_llm = name("agent_info", "llm")
    user_llm = name("user_info", "llm")
    if "|" in domain:
        raise ValueError(f"domain {domain!r} contains '|', which separates domain and task in an item")
    agent = model_id(agent_llm)
    user = model_id(user_llm)
    where = f"{domain} {agent}"

    tasks = run["tasks"]
    if not isinstance(tasks, list):
        raise ValueError(f"{where}: tasks is not a list")
    ids = []
    known = set()
    for task in tasks:
        task_id = task.get("id") if isinstance(task, dict) else None
        if not isinstance(task_id, str) or not task_id:
            raise ValueError(f"{where}: task id {task_id!r} is not a non-empty string")
        if task_id in known:
            raise ValueError(f"{where}: task {task_id!r} repeats")
        ids.append(task_id)
        known.add(task_id)

    simulations = run["simulations"]
    if not isinstance(simulations, list):
        raise ValueError(f"{where}: simulations is not a list")
    seen = set()
    cells = {}
    for entry in simulations:
        if not isinstance(entry, dict):
            raise ValueError(f"{where}: a simulation is a {type(entry).__name__}, not an object")
        task_id = entry.get("task_id")
        if not isinstance(task_id, str) or task_id not in known:
            raise ValueError(f"{where}: simulation task {task_id!r} is not a task of the run")
        number = entry.get("trial")
        _check_trial(number, f"{where} task {task_id!r}: trial")
        if (task_id, number) in seen:
            raise ValueError(f"{where} task {task_id!r}: trial {number} repeats")
        seen.add((task_id, number))
        if number != trial:
            continue
        at = f"{where} task {task_id!r} trial {number}"
        reward_info = entry.get("reward_info")
        reward = reward_info.get("reward") if isinstance(reward_info, dict) else None
        if not _number(reward) or reward not in (0, 1):
            raise ValueError(f"{at}: reward {reward!r} is not 0 or 1")
        cost = entry.get("agent_cost")
        if not _number(cost) or not _finite(cost) or cost < 0:
            raise ValueError(f"{at}: agent_cost {cost!r} is not a finite number >= 0")
        cell = {"correct": reward == 1, "cost_usd": float(cost) + 0.0}  # + 0.0 turns -0.0 into 0.0
        if tokens:
            cell["input_tokens"], cell["output_tokens"], new_in, outs = _agent_tokens(entry.get("messages"), at)
            if calls:
                if not outs:
                    raise ValueError(f"{at}: no agent message has a usage, so the conversation has no model call")
                cell["call_input_tokens"], cell["call_output_tokens"] = new_in, outs
        cells[task_id] = cell
    if not cells:
        raise ValueError(f"{where}: no simulation has trial {trial}")
    return {"domain": domain, "agent": agent, "user": user, "trial": trial, "tokens": tokens, "calls": calls,
            "cells": {task_id: cells[task_id] for task_id in sorted(cells)},
            "missing_trial": sorted(task_id for task_id in ids if task_id not in cells)}


def _agent_tokens(messages, at) -> tuple:
    """Sum prompt and completion tokens over the agent's messages, and list each call's new input and output.

    User and tool messages are skipped. The j-th new input is the first prompt for j = 1, then the
    prompt less the previous prompt and completion, so it may be negative (DESIGN 12.14 v1.76).
    """
    if not isinstance(messages, list):
        raise ValueError(f"{at}: messages is not a list")
    total_in = total_out = 0
    new_in, outs = [], []
    previous = None
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError(f"{at}: a message is a {type(message).__name__}, not an object")
        if message.get("role") != "assistant":
            continue
        if "usage" not in message:
            raise ValueError(f"{at}: an agent message has no usage")
        usage = message["usage"]
        if usage is None:
            continue
        if not isinstance(usage, dict):
            raise ValueError(f"{at}: an agent message's usage is a {type(usage).__name__}, not an object")
        for key in ("prompt_tokens", "completion_tokens"):
            if not _count(usage.get(key)):
                raise ValueError(f"{at}: usage {key} {usage.get(key)!r} is not an int >= 0")
        prompt, completion = usage["prompt_tokens"], usage["completion_tokens"]
        total_in += prompt
        total_out += completion
        new_in.append(prompt if previous is None else prompt - previous)
        outs.append(completion)
        previous = prompt + completion
    return total_in, total_out, new_in, outs


def convert(extracts, task_by="domain") -> tuple:
    """Rows of the 12.1 outcome matrix and a report, from the extracts of every run."""
    if task_by not in TASK_BY:
        raise ValueError(f"task_by {task_by!r} is not one of {', '.join(TASK_BY)}")
    if not isinstance(extracts, (list, tuple)) or not extracts:
        raise ValueError("no runs to convert")
    for key, label in (("user", "user model"), ("trial", "trial"), ("tokens", "tokens setting"),
                       ("calls", "calls setting")):
        values = sorted({repr(e[key]) for e in extracts})
        if len(values) > 1:
            raise ValueError(f"the runs differ in their {label}: {', '.join(values)}")
    domains = {}
    for e in extracts:
        by_agent = domains.setdefault(e["domain"], {})
        if e["agent"] in by_agent:
            raise ValueError(f"{e['domain']}: two runs for {e['agent']}")
        by_agent[e["agent"]] = e
    models = sorted({e["agent"] for e in extracts})
    for domain in sorted(domains):
        missing = [model for model in models if model not in domains[domain]]
        if missing:
            raise ValueError(f"{domain}: no run for {', '.join(missing)}")
    calls = extracts[0]["calls"]
    left_out = {}
    if calls:
        for model in models:
            negative = sum(1 for e in extracts if e["agent"] == model for cell in e["cells"].values()
                           for value in cell["call_input_tokens"] if value < 0)
            if negative:
                left_out[model] = negative
        if len(left_out) == len(models):
            raise ValueError("every agent has a call whose new input is negative: "
                             + ", ".join(f"{m} ({n})" for m, n in left_out.items()))
        models = [model for model in models if model not in left_out]

    rows, kept, dropped = [], {}, {}
    for domain in sorted(domains):
        by_agent = domains[domain]
        task = domain if task_by == "domain" else "all"
        task_ids = set()
        for model in models:
            task_ids.update(by_agent[model]["cells"])
            task_ids.update(by_agent[model]["missing_trial"])
        complete = sorted(t for t in task_ids if all(t in by_agent[m]["cells"] for m in models))
        kept[task] = kept.get(task, 0) + len(complete)
        dropped[task] = dropped.get(task, 0) + len(task_ids) - len(complete)
        for task_id in complete:
            for model in models:
                cell = by_agent[model]["cells"][task_id]
                row = {"task": task, "item": f"{domain}|{task_id}", "model": model,
                       "correct": cell["correct"], "cost_usd": cell["cost_usd"]}
                if "input_tokens" in cell:
                    row["input_tokens"] = cell["input_tokens"]
                    row["output_tokens"] = cell["output_tokens"]
                if calls:
                    row["call_input_tokens"] = list(cell["call_input_tokens"])
                    row["call_output_tokens"] = list(cell["call_output_tokens"])
                rows.append(row)
    rows.sort(key=lambda r: (r["task"], r["item"], r["model"]))
    report = {"models": models, "user_models": [extracts[0]["user"]], "trial": extracts[0]["trial"],
              "task_by": task_by, "kept": {t: kept[t] for t in sorted(kept)},
              "dropped_incomplete": {t: dropped[t] for t in sorted(dropped)}, "rows": len(rows)}
    if calls:
        report["left_out"] = left_out
    return rows, report


def read_run(path):
    path = Path(path)
    try:
        with path.open(encoding="utf-8") as f:
            return json.load(f)
    except (ValueError, RecursionError) as exc:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        raise ValueError(f"{path.name}: not a valid UTF-8 JSON file ({type(exc).__name__}: {exc})") from exc


def write_jsonl(rows, path) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


def _one_line(exc) -> str:
    return str(exc).replace("\r", "\\r").replace("\n", "\\n")


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def main(argv=None) -> int:
    parser = _Parser(prog="convert.py", description="tau2-bench paper results to an outcome matrix")
    parser.add_argument("--out", required=True, help="output JSONL path")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {default_cache_dir()})")
    parser.add_argument("--trial", default="0", help="the trial kept of every task (default: %(default)s)")
    parser.add_argument("--task-by", default="domain", help="domain (one task per domain, the default) or all")
    parser.add_argument("--tokens", action="store_true", help="add the agent's summed input and output tokens")
    parser.add_argument("--calls", action="store_true",
                        help="add each call's new input and output (implies --tokens; leaves out agents it cannot split)")
    try:
        args = parser.parse_args(argv)
        if not re.fullmatch(r"[0-9]+", args.trial):
            raise _UsageError(f"--trial {args.trial!r} is not an int >= 0")
        trial = int(args.trial)
        if args.task_by not in TASK_BY:
            raise _UsageError(f"--task-by {args.task_by!r} is not one of {', '.join(TASK_BY)}")
        out = Path(args.out)
        if not out.name:
            raise _UsageError(f"--out {args.out!r} does not end in a file name")
    except (_UsageError, ValueError) as exc:  # int() refuses a digit string past the interpreter's limit
        print(f"error: {_one_line(exc)}", file=sys.stderr)
        return 2
    part = out.with_name(out.name + ".part")
    try:
        folder = fetch(args.cache)
        extracts = [extract(read_run(folder / name), trial, args.tokens or args.calls, args.calls) for name in FILES]
        rows, report = convert(extracts, args.task_by)
        try:
            write_jsonl(rows, part)
            # print before the rename, so a write to stdout that fails leaves --out as it was (v1.94)
            print(json.dumps(report, indent=2), flush=True)
            part.replace(out)
        finally:
            part.unlink(missing_ok=True)
    except (ValueError, OSError) as exc:
        print(f"error: {_one_line(exc)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
