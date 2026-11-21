"""Replay a cascade of two tau2-bench agents on a signal from the cheap run's own calls (DESIGN 7 v1.539, v1.540).

Usage: python evidence/tau2-bench/cascades.py --out PATH [--cache DIR]

Standard library and ``model_routing``. A cascade starts an item on the cheap agent and hands it up to
the strong one when its signal fires: ``calls-over-N`` (more than N agent calls), ``calls-over-N-no-write``
(more than N agent calls and no write call among the first N) or ``transfer`` (a call of
``transfer_to_human_agents``). A row replays it from the two agents' recorded runs of the item: kept, the
cheap run's label and cost; handed up at call h, the strong run's label, and as cost the cheap run's first
h calls, call h's prompt and completion read by the strong model as uncached input at its input list price,
and the strong run. The strong run in the data starts fresh, with its own simulated user, so a row replays
a hand-up that restarts the conversation, and ``calls-over-N`` and ``transfer`` may hand up a run that has
written, which assumes the cheap agent's writes undone (research/escalation.md). The CLI (v1.540) reads
the 12 pinned run files through convert.py in this folder and each domain's write tools through
research/escalation_signals.py, both loaded from their paths, never copied, and writes the 12.14 matrix at
trial 0, one task per domain, with one row per cascade and item for each pair of the four agents, its
cheap agent the one at the lower input list price of prices.json, and each signal of SIGNALS; it prints a
report of the counts. No result is computed here (rows ESC3c to ESC3f).
"""

import argparse
import datetime
import importlib.util
import itertools
import json
import math
import re
import sys
from pathlib import Path

from model_routing import Cascade

_HERE = Path(__file__).resolve().parent
PRICES = _HERE / "prices.json"
TRIAL = 0


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


convert = _load(_HERE / "convert.py", "tau2_bench_convert_for_cascades")
signals = _load(_HERE.parents[1] / "research" / "escalation_signals.py", "escalation_signals_for_cascades")

TRANSFER = "transfer_to_human_agents"
SIGNALS = ("calls-over-10", "calls-over-10-no-write", "calls-over-15", "calls-over-15-no-write",
           "calls-over-20", "calls-over-20-no-write", "transfer")
_CALLS_OVER = re.compile(r"calls-over-([1-9][0-9]*)(-no-write)?")
CALL_KEYS = ("cost_usd", "prompt_tokens", "completion_tokens", "write", "transfer")
ROW_KEYS = ("task", "item", "model", "correct", "cost_usd", "escalated")


def parse_signal(signal) -> tuple:
    """``("calls-over", N)``, ``("calls-over-no-write", N)`` or ``("transfer", None)``; else a ValueError."""
    if isinstance(signal, str):
        if signal == "transfer":
            return ("transfer", None)
        found = _CALLS_OVER.fullmatch(signal)  # [0-9] matches ASCII digits only
        if found is not None and len(found.group(1)) <= 4000:  # int() refuses longer digit strings
            return ("calls-over-no-write" if found.group(2) else "calls-over", int(found.group(1)))
    raise ValueError(f"unknown signal {signal!r}: a signal is calls-over-<N>, calls-over-<N>-no-write or transfer")


def _price(value) -> bool:
    if not isinstance(value, (int, float)) or isinstance(value, bool):
        return False
    try:
        return math.isfinite(float(value)) and value >= 0
    except OverflowError:  # an int too large for a float is not finite
        return False


def _count(value) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _tool_names(value, at) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{at}: tool_calls is not a list")
    names = []
    for entry in value:
        name = entry.get("name") if isinstance(entry, dict) else None
        if not isinstance(name, str) or not name:
            raise ValueError(f"{at}: a tool call is not an object with a non-empty name")
        names.append(name)
    return names


def agent_calls(messages, writes, at="") -> list:
    """One dict per agent call (an agent message with a usage), in message order, keys CALL_KEYS."""
    if not isinstance(messages, list):
        raise ValueError(f"{at}: messages is not a list")
    if isinstance(writes, (str, bytes)):
        raise ValueError(f"{at}: writes is a {type(writes).__name__}, not a collection of tool names")
    writes = set(writes)
    calls = []
    for message in messages:
        if not isinstance(message, dict):
            raise ValueError(f"{at}: a message is a {type(message).__name__}, not an object")
        if message.get("role") != "assistant":
            continue
        if "usage" not in message:
            raise ValueError(f"{at}: an agent message has no usage key")
        cost = message.get("cost")
        if not _price(cost):
            raise ValueError(f"{at}: an agent message's cost {cost!r} is not a finite number >= 0")
        names = _tool_names(message.get("tool_calls"), at)
        usage = message["usage"]
        if usage is None:
            if names:
                raise ValueError(f"{at}: an agent message without a usage calls a tool")
            if cost != 0:
                raise ValueError(f"{at}: an agent message without a usage has the cost {cost!r}, not 0")
            continue
        if not (isinstance(usage, dict) and _count(usage.get("prompt_tokens"))
                and _count(usage.get("completion_tokens"))):
            raise ValueError(f"{at}: a usage is not an object with int prompt_tokens and completion_tokens >= 0")
        calls.append({"cost_usd": float(cost) + 0.0, "prompt_tokens": usage["prompt_tokens"],
                      "completion_tokens": usage["completion_tokens"], "write": bool(writes.intersection(names)),
                      "transfer": TRANSFER in names})
    return calls


def hand_up(calls, signal):
    """The 1-based call after which the cascade hands up, or None when it keeps the cheap run."""
    kind, n = parse_signal(signal)
    if kind == "transfer":
        return next((k for k, entry in enumerate(calls, 1) if entry["transfer"]), None)
    if len(calls) <= n:
        return None
    if kind == "calls-over-no-write" and any(entry["write"] for entry in calls[:n]):
        return None
    return n


def cascade_cell(calls, cheap, strong, signal, price_in) -> dict:
    """``{"correct", "cost_usd", "escalated"}`` of one item run through the cascade (DESIGN 7 v1.539)."""
    if not _price(price_in):
        raise ValueError(f"price_in {price_in!r} is not a finite number >= 0")
    h = hand_up(calls, signal)
    if h is None:
        return {"correct": cheap["correct"], "cost_usd": cheap["cost_usd"], "escalated": False}
    last = calls[h - 1]
    reread = (last["prompt_tokens"] + last["completion_tokens"]) * price_in / 1_000_000
    cost = math.fsum([entry["cost_usd"] for entry in calls[:h]] + [reread, strong["cost_usd"]])
    return {"correct": strong["correct"], "cost_usd": cost, "escalated": True}


def _key(row) -> tuple:
    return (str(row["task"]), str(row["item"]), str(row["model"]))


def cascade_rows(rows, calls, cascades, prices) -> list:
    """A copy of every row plus one cascade row per cascade and (task, item) of its cheap model, sorted."""
    rows = list(rows)  # read once, so a one-shot iterable of rows keeps every row
    cascades = list(cascades)
    cells = {}
    for row in rows:
        key = (row["task"], row["item"], row["model"])
        if key in cells:
            raise ValueError(f"row {key!r} is repeated")
        cells[key] = row
    items = {}
    for task, item, model in cells:
        items.setdefault(model, set()).add((task, item))
    seen = set()
    for cascade in cascades:
        if not isinstance(cascade, Cascade):
            raise ValueError(f"cascade {cascade!r} is not a Cascade")
        if cascade.id in seen:
            raise ValueError(f"cascade {cascade.id} is repeated")
        seen.add(cascade.id)
    for cascade in cascades:
        cid = cascade.id
        try:
            parse_signal(cascade.signal)
        except ValueError as exc:
            raise ValueError(f"cascade {cid}: {exc}") from None
        if cid in items:  # v1.549, review iter-394: a row of its own output passed in again
            raise ValueError(f"cascade {cid}: the rows already hold a row of its id, which the call would repeat")
        for role, model in (("cheap", cascade.cheap), ("strong", cascade.strong)):
            if model not in items:
                raise ValueError(f"cascade {cid}: its {role} model {model} has no row")
        if items[cascade.cheap] != items[cascade.strong]:
            odd = sorted(items[cascade.cheap] ^ items[cascade.strong], key=str)[0]
            raise ValueError(f"cascade {cid}: {odd!r} has a row of only one of its two models")
        if cascade.strong not in prices:
            raise ValueError(f"cascade {cid}: its strong model {cascade.strong} has no price")
        if not _price(prices[cascade.strong]):
            raise ValueError(f"cascade {cid}: its strong model's price {prices[cascade.strong]!r} is not a finite"
                             " number >= 0")
        for task, item in sorted(items[cascade.cheap], key=str):
            if (cascade.cheap, item) not in calls:
                raise ValueError(f"cascade {cid}: no calls for ({cascade.cheap!r}, {item!r})")
    out = [dict(row) for row in rows]
    for cascade in cascades:
        price = prices[cascade.strong]
        for task, item in items[cascade.cheap]:
            cell = cascade_cell(calls[(cascade.cheap, item)], cells[(task, item, cascade.cheap)],
                                cells[(task, item, cascade.strong)], cascade.signal, price)
            out.append({"task": task, "item": item, "model": cascade.id, **cell})
    return sorted(out, key=_key)


_PRICE_KEYS = ("as_of", "note", "models")
_ENTRY_KEYS = ("id", "price_in", "source", "notes")
_DATE = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _real_date(value) -> bool:
    if not isinstance(value, str) or _DATE.fullmatch(value) is None:
        return False
    try:
        datetime.date.fromisoformat(value)
    except ValueError:
        return False
    return True


def load_prices(path) -> tuple:
    """``(as_of, {id: price_in})`` of a dated price file (DESIGN 7 v1.540); a ValueError naming it."""
    path = Path(path)
    name = path.name
    try:
        doc = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, RecursionError) as exc:  # JSONDecodeError and UnicodeDecodeError are ValueErrors
        raise ValueError(f"{name}: not a valid UTF-8 JSON file ({type(exc).__name__}: {exc})") from None
    if not isinstance(doc, dict) or set(doc) != set(_PRICE_KEYS):
        raise ValueError(f"{name}: not an object with exactly the keys {', '.join(_PRICE_KEYS)}")
    if not _real_date(doc["as_of"]):
        raise ValueError(f"{name}: as_of {doc['as_of']!r} is not a real YYYY-MM-DD date")
    if not isinstance(doc["note"], str):
        raise ValueError(f"{name}: note is a {type(doc['note']).__name__}, not a str")
    models = doc["models"]
    if not isinstance(models, list) or not models:
        raise ValueError(f"{name}: models is not a non-empty list")
    prices = {}
    for k, entry in enumerate(models):
        if not isinstance(entry, dict) or set(entry) != set(_ENTRY_KEYS):
            raise ValueError(f"{name}: models[{k}] is not an object with exactly the keys {', '.join(_ENTRY_KEYS)}")
        model = entry["id"]
        if not isinstance(model, str) or not model:
            raise ValueError(f"{name}: models[{k}] id {model!r} is not a non-empty str")
        if model in prices:
            raise ValueError(f"{name}: model {model} is repeated")
        if not _price(entry["price_in"]):
            raise ValueError(f"{name}: {model} price_in {entry['price_in']!r} is not a finite number >= 0")
        source = entry["source"]
        if not isinstance(source, str) or not source.startswith("https://"):
            raise ValueError(f"{name}: {model} source {source!r} is not an https:// URL")
        if not isinstance(entry["notes"], str):
            raise ValueError(f"{name}: {model} notes is a {type(entry['notes']).__name__}, not a str")
        prices[model] = entry["price_in"]
    return doc["as_of"], prices


def pair_cascades(models, prices) -> list:
    """One Cascade per pair of ``models`` and signal of SIGNALS, the cheap model at the lower price_in."""
    models = sorted(set(models))
    missing = [model for model in models if model not in prices]
    if missing:
        raise ValueError(f"no price for {', '.join(missing)}")
    unused = sorted(set(prices) - set(models))
    if unused:
        raise ValueError(f"a price for a model with no run: {', '.join(unused)}")
    found = []
    for a, b in itertools.combinations(models, 2):
        if prices[a] == prices[b]:
            raise ValueError(f"{a} and {b} have one price_in {prices[a]!r}, so neither is the cheap model")
        cheap, strong = (a, b) if prices[a] < prices[b] else (b, a)
        found += [Cascade(cheap, strong, signal) for signal in SIGNALS]
    return sorted(found, key=lambda cascade: cascade.id)


def run_calls(run, tools, trial=TRIAL) -> tuple:
    """``(extract, {(agent, item): agent_calls}, greetings)`` of one parsed run file at ``trial``."""
    e = convert.extract(run, trial)
    domain, agent = e["domain"], e["agent"]
    if domain not in tools:
        raise ValueError(f"{domain}: no tools file is pinned for this domain")
    writes = {name for name, kind in tools[domain].items() if kind == "WRITE"}
    calls, greetings = {}, 0
    for entry in run["simulations"]:
        if entry["trial"] != trial or entry["task_id"] not in e["cells"]:
            continue
        at = f"{domain} {agent} task {entry['task_id']!r} trial {trial}"
        messages = entry.get("messages")
        found = agent_calls(messages, writes, at)
        calls[(agent, f"{domain}|{entry['task_id']}")] = found
        greetings += sum(1 for message in messages if message.get("role") == "assistant") - len(found)
    return e, calls, greetings


def report(as_of, matrix, cascades, rows, out_rows, calls, greetings) -> dict:
    """The CLI's report; ``escalated`` lists every cascade for every task of ``kept`` (DESIGN 7 v1.540)."""
    counts = {task: {cascade.id: 0 for cascade in cascades} for task in matrix["kept"]}
    for row in out_rows:
        if row["model"] in counts.get(row["task"], {}):
            counts[row["task"]][row["model"]] += int(row["escalated"])
    return {"revision": convert.REVISION, "prices_as_of": as_of, "models": sorted(matrix["models"]),
            "trial": matrix["trial"], "kept": matrix["kept"], "agent_calls": sum(len(v) for v in calls.values()),
            "greetings": greetings, "model_rows": len(rows), "cascades": len(cascades),
            "cascade_rows": len(out_rows) - len(rows), "rows": len(out_rows),
            "escalated": {task: {cid: counts[task][cid] for cid in sorted(counts[task])} for task in sorted(counts)}}


def main(argv=None) -> int:
    parser = convert._Parser(prog="cascades.py", description="tau2-bench cascade replay rows")
    parser.add_argument("--out", required=True, help="output JSONL path")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {convert.default_cache_dir()})")
    try:
        args = parser.parse_args(argv)
        out = convert._check_out(args.out)
    except (convert._UsageError, ValueError) as exc:
        print(f"error: {convert._one_line(exc)}", file=sys.stderr)
        return 2
    part = out.with_name(out.name + ".part")
    try:
        as_of, prices = load_prices(PRICES)
        folder = Path(convert.fetch(args.cache))
        sources = signals.fetch_tools(folder / "tools", convert)
        tools = {domain: signals.tool_types(text, f"{domain}-tools.py") for domain, text in sources.items()}
        extracts, calls, greetings = [], {}, 0
        for name in convert.FILES:  # one run file in memory at a time
            e, found, seen = run_calls(convert.read_run(folder / name), tools)
            extracts.append(e)
            calls.update(found)
            greetings += seen
        rows, matrix = convert.convert(extracts, "domain")
        cascades = pair_cascades(matrix["models"], prices)
        out_rows = cascade_rows(rows, calls, cascades, prices)
        summary = report(as_of, matrix, cascades, rows, out_rows, calls, greetings)
        try:
            convert.write_jsonl(out_rows, part)
            # print before the rename, so a write to stdout that fails leaves --out as it was (12.14 v1.94)
            convert.print_report(json.dumps(summary, indent=2))
            part.replace(out)
        finally:
            part.unlink(missing_ok=True)
    except (ValueError, OSError) as exc:
        print(f"error: {convert._one_line(exc)}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
