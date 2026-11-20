"""Replay a cascade of two tau2-bench agents on a signal from the cheap run's own calls (DESIGN 7 v1.539).

Standard library and ``model_routing``. A cascade starts an item on the cheap agent and hands it up to
the strong one when its signal fires: ``calls-over-N`` (more than N agent calls), ``calls-over-N-no-write``
(more than N agent calls and no write call among the first N) or ``transfer`` (a call of
``transfer_to_human_agents``). A row replays it from the two agents' recorded runs of the item: kept, the
cheap run's label and cost; handed up at call h, the strong run's label, and as cost the cheap run's first
h calls, call h's prompt and completion read by the strong model as uncached input at its input list price,
and the strong run. The strong run in the data starts fresh, with its own simulated user, so a row replays
a hand-up that restarts the conversation, and ``calls-over-N`` and ``transfer`` may hand up a run that has
written, which assumes the cheap agent's writes undone (research/escalation.md). This version holds the
reduction and the replay rule on messages and rows a caller passes in; it downloads, prices and writes
nothing (rows ESC3b to ESC3f).
"""

import math
import re

from model_routing import Cascade

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
        found = _CALLS_OVER.fullmatch(signal) if signal.isascii() else None
        if found is not None:
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
        for role, model in (("cheap", cascade.cheap), ("strong", cascade.strong)):
            if model not in items:
                raise ValueError(f"cascade {cid}: its {role} model {model} has no row")
        if items[cascade.cheap] != items[cascade.strong]:
            odd = sorted(items[cascade.cheap] ^ items[cascade.strong], key=str)[0]
            raise ValueError(f"cascade {cid}: {odd!r} has a row of only one of its two models")
        if cascade.strong not in prices:
            raise ValueError(f"cascade {cid}: its strong model {cascade.strong} has no price")
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
