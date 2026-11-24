"""Per-attempt JSONL logging and cost and reliability reports."""

from __future__ import annotations

import json
import threading
from math import ceil, fsum, isfinite
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Union

from .budget import Budget, _instant

PathLike = Union[str, Path]

_GROUP_KEYS = ("model", "task", "flavor", "family")
NO_TAG = "(none)"


class Monitor:
    """Collects attempt records in memory and optionally appends them to a JSONL file.

    One monitor may be shared by the threads of a process (DESIGN 8.2 v1.616): ``record`` holds a
    lock from its append to ``records`` through the close of the file, so each record is one whole
    line and ``records`` and the file hold the records in one order. Two monitors on one path, or
    two processes, are not guarded by it.
    """

    def __init__(self, path: Optional[PathLike] = None):
        self.path = Path(path) if path is not None else None
        self.records: List[dict] = []
        self._lock = threading.Lock()

    def record(self, rec: dict) -> None:
        """Store one attempt record and append it to the log file when set, under the lock."""
        with self._lock:
            self.records.append(rec)
            if self.path is not None:
                with self.path.open("a", encoding="utf-8") as handle:
                    handle.write(json.dumps(rec) + "\n")


def load_records(path: PathLike) -> List[dict]:
    """Read a JSONL file of objects, skipping blank lines.

    A line that is not valid JSON, or not a JSON object, raises ``ValueError``
    naming ``<path>:<line number>``.
    """
    return [value for _, value in _numbered_objects(path)]


def _numbered_objects(path: PathLike):
    """Yield ``(line number, object)`` for each non-blank line of a JSONL file of objects."""
    with Path(path).open(encoding="utf-8") as handle:
        for number, line in enumerate(handle, start=1):
            if not line.strip():
                continue
            try:
                value = json.loads(line)
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON: {exc}") from None
            if not isinstance(value, dict):
                raise ValueError(f"{path}:{number}: expected a JSON object, "
                                 f"got {type(value).__name__}")
            yield number, value


def load_audits(path: PathLike) -> Dict[str, bool]:
    """Read a JSONL file of audits into ``{call_id: correct}``, in file order (DESIGN 8.2, v1.569).

    Each non-blank line is an object with ``call_id`` (a non-empty string) and ``correct`` (a JSON
    boolean); other keys are ignored. A bad line, or a ``call_id`` an earlier line gave, raises
    ``ValueError`` naming ``<path>:<line number>``.
    """
    audits: Dict[str, bool] = {}
    for number, value in _numbered_objects(path):
        call_id, correct = value.get("call_id"), value.get("correct")
        if not isinstance(call_id, str) or not call_id:
            raise ValueError(f"{path}:{number}: call_id must be a non-empty string, got {call_id!r}")
        if not isinstance(correct, bool):
            raise ValueError(f"{path}:{number}: correct must be true or false, got {correct!r}")
        if call_id in audits:
            raise ValueError(f"{path}:{number}: call_id {call_id!r} is audited twice")
        audits[call_id] = correct
    return audits


def _grouper(by: str):
    if by in _GROUP_KEYS:
        return lambda rec: str(rec.get(by))
    if by == "pricing_basis":  # DESIGN 8.3 v1.584: only a self-hosted model's records hold it
        return lambda rec: str(rec.get(by, "list"))
    if by.startswith("tag:") and len(by) > 4:
        key = by[4:]
        return lambda rec: (rec.get("tags") or {}).get(key, NO_TAG)
    raise ValueError(f"unknown report key {by!r}; use model, task, flavor, family, pricing_basis or tag:<key>")


def _entry(rec: dict) -> object:
    """The route entry a record belongs to, read from the record alone (DESIGN 8.3 v1.579)."""
    if "cascade" in rec:
        return rec.get("cascade")
    if "procedure" in rec and "model_calls" not in rec:   # a model call of the procedure
        return f"proc:{rec.get('procedure')}@{rec.get('procedure_version')}+{rec.get('model')}"
    return rec.get("model")               # a closing record's model is the procedure's .id


def _key(rec: dict) -> object:
    """The record's ``call_id`` in a tuple, or ``None`` when it cannot be a dict key (a JSON
    array or object), so that record matches no other (DESIGN 8.3 v1.579)."""
    call_id = rec.get("call_id")
    try:
        hash(call_id)
    except TypeError:
        return None
    return (call_id,)


def _is_fallback(rec: dict, first: Dict[object, object]) -> bool:
    """Whether a final record ends its call on another route entry than its first record."""
    if int(rec.get("attempt", 0)) <= 0:
        return False
    if "cascade" not in rec and "procedure" not in rec:
        return True                       # a plain entry writes one record (v1.577's count)
    key = _key(rec)
    return key is None or key not in first or first[key] != _entry(rec)


def _nearest_rank(sorted_values: List[float], q: float) -> Optional[float]:
    if not sorted_values:
        return None
    index = max(0, ceil(q * len(sorted_values)) - 1)
    return sorted_values[index]


def report(records: Iterable[dict], by: str = "model",
           audits: Optional[Mapping[str, bool]] = None, cache: bool = False,
           shadow: bool = False) -> List[dict]:
    """Aggregate attempt records by ``by``.

    Attempt-level sums use each attempt; call-level counts (``calls``,
    ``failed_calls``, ``fallback_calls``) use the group of the call's final
    attempt. ``below_bar_calls`` (the last key) counts the calls whose final
    attempt is ``ok`` on a model under the bar: its record's ``below_bar`` or
    ``below_bar_fallback`` is true (DESIGN 8.1, 8.3, v1.203). Rows are sorted
    by descending ``cost_usd``, then ``group``.

    A call counts in ``fallback_calls`` when its final record belongs to another
    route entry than its first record, the latest record with its ``call_id`` and
    ``attempt`` 0 at or before it, so a cascade that handed up or a procedure that
    made model calls is no fallback as the first entry (DESIGN 8.3 v1.579).

    With ``audits`` (``{call_id: correct}``, ``load_audits``) each row also gains
    ``audited_calls``, ``correct_calls``, ``cost_per_success_usd`` and
    ``successes_per_100k_tokens`` (DESIGN 8.3, v1.569): every attempt of the group's calls over
    the calls whose final attempt is ``ok`` and audited ``True``, ``None`` until every call of the
    group is audited.

    With ``cache=True`` each row also gains, last, ``cached_input_tokens``,
    ``cache_counted_input_tokens`` and ``cache_hit_rate`` (DESIGN 8.3, v1.590): the group's
    attempts that carry a ``cached_input_tokens`` count, their cached and their input tokens, and
    the first over the second, ``None`` when no attempt of the group carries the count or their
    input sums to 0. An attempt without the count is unknown, never a miss, and
    ``cache_write_tokens`` enters no part of the rate.

    With ``shadow=True`` (DESIGN 8.3, v1.611) a shadow record, one whose ``shadow`` is JSON
    ``true`` (7 v1.607), enters none of the keys above, so they read the routed records alone, and
    each row gains, last, ``shadow_calls``, ``shadow_failed_calls`` and ``shadow_cost_usd``, read from
    the group's shadow records alone; a group that only shadow records reach has a row of routed
    zeros. A ``shadow`` that is not a ``bool`` raises ``ValueError`` before any record is read.
    """
    if not isinstance(shadow, bool):
        raise ValueError(f"shadow must be True or False, got {shadow!r}")
    group_of = _grouper(by)
    records = [rec for rec in records if "budget_event" not in rec]  # DESIGN 8.3 v1.598
    shadows: List[dict] = []
    if shadow:  # DESIGN 8.3 v1.611: only a JSON true marks a shadow record
        shadows = [rec for rec in records if rec.get("shadow") is True]
        records = [rec for rec in records if rec.get("shadow") is not True]
    groups: Dict[str, dict] = {}
    latencies: Dict[str, List[float]] = {}
    under: Dict[str, int] = {}
    first: Dict[object, object] = {}

    def row_of(group: str) -> dict:
        row = groups.get(group)
        if row is None:
            row = groups[group] = {
                "group": group, "attempts": 0, "ok": 0, "errors": 0, "invalid": 0,
                "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0,
                "routing_cost_usd": 0.0, "calls": 0, "failed_calls": 0,
                "fallback_calls": 0,
            }
            latencies[group] = []
            under[group] = 0
        return row

    for rec in records:
        if rec.get("attempt", 0) == 0 and _key(rec) is not None:
            first[_key(rec)] = _entry(rec)
        group = group_of(rec)
        row = row_of(group)
        outcome = rec.get("outcome")
        row["attempts"] += 1
        if outcome == "ok":
            row["ok"] += 1
            latencies[group].append(float(rec.get("latency_ms", 0.0)))
        elif outcome == "error":
            row["errors"] += 1
        elif outcome == "invalid":
            row["invalid"] += 1
        row["input_tokens"] += int(rec.get("input_tokens", 0))
        row["output_tokens"] += int(rec.get("output_tokens", 0))
        row["cost_usd"] += float(rec.get("cost_usd", 0.0))
        row["routing_cost_usd"] += float(rec.get("routing_cost_usd", 0.0))
        if rec.get("final"):
            row["calls"] += 1
            if outcome != "ok":
                row["failed_calls"] += 1
            if _is_fallback(rec, first):
                row["fallback_calls"] += 1
            if outcome == "ok" and (rec.get("below_bar") is True
                                    or rec.get("below_bar_fallback") is True):
                under[group] += 1
    for rec in shadows:  # a group that only shadow records reach still has a row
        row_of(group_of(rec))
    rows = []
    for group, row in groups.items():
        row["cost_usd"] = round(row["cost_usd"], 6)
        row["routing_cost_usd"] = round(row["routing_cost_usd"], 6)
        row["fallback_rate"] = row["fallback_calls"] / row["calls"] if row["calls"] else 0.0
        values = sorted(latencies[group])
        row["p50_latency_ms"] = _nearest_rank(values, 0.50)
        row["p95_latency_ms"] = _nearest_rank(values, 0.95)
        row["below_bar_calls"] = under[group]
        rows.append(row)
    if audits is not None:
        _add_audit_keys(records, groups, group_of, audits)
    if cache:
        _add_cache_keys(records, groups, group_of)
    if shadow:
        _add_shadow_keys(shadows, groups, group_of)
    rows.sort(key=lambda r: (-r["cost_usd"], r["group"]))
    return rows


def _add_audit_keys(records: List[dict], groups: Dict[str, dict], group_of,
                    audits: Mapping[str, bool]) -> None:
    """Add the four v1.569 keys to each row of ``groups`` (DESIGN 8.3)."""
    attempts: Dict[object, List[dict]] = {}
    finals: Dict[object, dict] = {}
    for rec in records:
        call_id = rec.get("call_id")
        attempts.setdefault(call_id, []).append(rec)
        if rec.get("final"):
            if call_id in finals:
                raise ValueError(f"call_id {call_id!r} has more than one final record, "
                                 "so its audit cannot be joined")
            finals[call_id] = rec
    calls: Dict[str, List[object]] = {group: [] for group in groups}
    for call_id, rec in finals.items():
        calls[group_of(rec)].append(call_id)
    for group, row in groups.items():
        audited = [c for c in calls[group] if isinstance(c, str) and c in audits]
        correct = sum(1 for c in audited
                      if finals[c].get("outcome") == "ok" and audits[c] is True)
        charged = [rec for c in calls[group] for rec in attempts[c]]
        complete = len(audited) == row["calls"]
        cost = fsum(float(rec.get("cost_usd", 0.0)) for rec in charged)
        counted = all("input_tokens" in rec and "output_tokens" in rec for rec in charged)
        tokens = sum(int(rec["input_tokens"]) + int(rec["output_tokens"])
                     for rec in charged) if counted else 0
        row["audited_calls"] = len(audited)
        row["correct_calls"] = correct
        row["cost_per_success_usd"] = (round(cost / correct, 6)
                                       if complete and correct else None)
        row["successes_per_100k_tokens"] = (round(correct * 100000 / tokens, 6)
                                            if complete and counted and tokens else None)


def _add_cache_keys(records: List[dict], groups: Dict[str, dict], group_of) -> None:
    """Add the three v1.590 keys to each row of ``groups`` (DESIGN 8.3)."""
    cached = {group: 0 for group in groups}
    counted = {group: 0 for group in groups}
    for rec in records:
        if "cached_input_tokens" not in rec:
            continue                      # unknown, so neither a hit nor a miss
        value, size = rec["cached_input_tokens"], int(rec.get("input_tokens", 0))
        if isinstance(value, bool) or not isinstance(value, int) or not 0 <= value <= size:
            raise ValueError(f"call_id {rec.get('call_id')!r}: cached_input_tokens must be an "
                             f"integer from 0 to its input_tokens ({size}), got {value!r}")
        group = group_of(rec)
        cached[group] += value
        counted[group] += size
    for group, row in groups.items():
        row["cached_input_tokens"] = cached[group]
        row["cache_counted_input_tokens"] = counted[group]
        row["cache_hit_rate"] = (round(cached[group] / counted[group], 6)
                                 if counted[group] else None)


def _add_shadow_keys(shadows: List[dict], groups: Dict[str, dict], group_of) -> None:
    """Add the three v1.611 keys to each row of ``groups``, from the shadow records (DESIGN 8.3)."""
    for row in groups.values():
        row.update(shadow_calls=0, shadow_failed_calls=0, shadow_cost_usd=0.0)
    for rec in shadows:
        row = groups[group_of(rec)]
        row["shadow_cost_usd"] += float(rec.get("cost_usd", 0.0))
        if rec.get("final") is True:  # a JSON true, as shadow_pairs reads it; calls reads truthiness
            row["shadow_calls"] += 1
            if rec.get("outcome") != "ok":
                row["shadow_failed_calls"] += 1
    for row in groups.values():
        row["shadow_cost_usd"] = round(row["shadow_cost_usd"], 6)


def budget_report(records: Iterable[dict], budgets: Sequence[Budget]) -> List[dict]:
    """Each budget's spend in each window as a percent of its limit (DESIGN 8.3 v1.598).

    The spend is the ``math.fsum`` of ``cost_usd`` over the attempt records the budget applies
    to, a ``day`` or ``month`` budget's window read from each record's ``ts``; the counts are of
    the budget records (8.1 v1.598) with the budget's name, the row's window and that event.
    """
    if not isinstance(budgets, (list, tuple)) or not all(isinstance(b, Budget) for b in budgets):
        raise ValueError(f"budgets must be a list or tuple of Budget, got {budgets!r}")
    names = [budget.name for budget in budgets]
    if len(set(names)) != len(names):
        raise ValueError(f"budget names must be unique, got {names}")
    records = list(records)
    rows = []
    for budget in budgets:
        spend: Dict[Optional[str], List[float]] = {None: []} if budget.window == "total" else {}
        counts: Dict[Optional[str], Dict[str, int]] = {}
        for rec in records:
            if "budget_event" in rec:
                label = rec.get("window")
                if rec.get("budget") != budget.name or (
                        label is not None if budget.window == "total" else not isinstance(label, str)):
                    continue
                if rec["budget_event"] in ("warn", "refused"):  # review iter-446 nit 5
                    counts.setdefault(label, {"warn": 0, "refused": 0})[rec["budget_event"]] += 1
                continue
            if not budget.applies(rec.get("task"), rec.get("tags") or {}):
                continue
            spend.setdefault(_window(budget, rec), []).append(float(rec.get("cost_usd", 0.0)))
        labels = [None] if budget.window == "total" else sorted(set(spend) | set(counts))
        for label in labels:
            total = fsum(spend.get(label, ()))
            tally = counts.get(label, {"warn": 0, "refused": 0})
            rows.append({"budget": budget.name, "window": label, "mode": budget.mode,
                         "limit_usd": budget.limit_usd, "spent_usd": round(total, 6),
                         "budget_used_pct": round(100 * total / budget.limit_usd, 6),
                         "warn_records": tally["warn"], "refused_records": tally["refused"]})
    return rows


def shadow_pairs(records: Iterable[dict], *, checked: bool = False,
                 audits: Optional[Mapping[str, bool]] = None) -> List[dict]:
    """One pair record per shadow that ran, in the order of its shadow records (DESIGN 8.3 v1.610).

    A shadow record is an attempt record whose ``shadow`` is true; its routed side is the
    ``final`` record whose ``call_id`` and ``pair_id`` are both its ``pair_id``. Each side's ``correct``
    comes from ``checked=True`` (``ok`` true, ``invalid`` false) or from ``audits`` by call ID
    (an ``invalid`` side false whatever its audit), never both, and is None on an ``error`` side
    or with neither. ``checked=True`` is the caller's word that every call ran with a
    ``validate``, checked against the records from v1.618: a pair whose routed final record or
    shadow record says ``checked: false`` is refused, while a record without the key, from an
    older log, is taken on that word (DESIGN 8.3 v1.618, review iter-461 should-fix 5); a
    ``checked`` key that is not a real bool is refused whatever the labels. Budget records are dropped
    first, so a shadow that was not sent or whose hold was refused has no pair. A bad argument,
    or a log the executor cannot write, raises ``ValueError`` before any pair is returned.
    """
    if type(checked) is not bool:
        raise ValueError(f"checked must be true or false, got {checked!r}")
    if audits is not None:
        if not isinstance(audits, Mapping):
            raise ValueError(f"audits must be None or a mapping of call ID to true or false, "
                             f"got {type(audits).__name__}")
        for call_id, correct in audits.items():
            if not isinstance(call_id, str) or not call_id:
                raise ValueError(f"audits: a call ID must be a non-empty string, got {call_id!r}")
            if type(correct) is not bool:
                raise ValueError(f"audits: the audit of {call_id!r} must be true or false, "
                                 f"got {correct!r}")
        if checked:
            raise ValueError("pass checked=True or audits, not both: their labels could disagree")
    records = [rec for rec in records if "budget_event" not in rec]
    shadows: List[dict] = []
    seen = set()
    for rec in records:
        if rec.get("shadow") is not True:
            continue
        pair_id = rec.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id:
            raise ValueError(f"a shadow record's pair_id must be a non-empty string, got {pair_id!r}")
        call_id = rec.get("call_id")
        if not isinstance(call_id, str) or not call_id:  # review iter-461 should-fix 3
            raise ValueError(f"pair_id {pair_id!r}: its shadow record's call_id must be a "
                             f"non-empty string, got {call_id!r}")
        if pair_id in seen:
            raise ValueError(f"pair_id {pair_id!r} has more than one shadow record")
        seen.add(pair_id)
        shadows.append(rec)
    finals: Dict[str, List[dict]] = {}
    for rec in records:
        pair_id = rec.get("pair_id")
        if rec.get("shadow") is not True and isinstance(pair_id, str) and pair_id in seen \
                and rec.get("call_id") == pair_id and rec.get("final") is True:
            finals.setdefault(pair_id, []).append(rec)
    for rec in shadows:
        count = len(finals.get(rec["pair_id"], ()))
        if count != 1:
            raise ValueError(f"pair_id {rec['pair_id']!r}: its routed call has "
                             f"{'no' if count == 0 else count} final records, so it is no pair")
    for rec in shadows:  # DESIGN 8.3 v1.618: what the records say about the check
        for side, record in (("routed", finals[rec["pair_id"]][0]), ("shadow", rec)):
            if "checked" not in record:
                continue  # a record from before v1.618: the caller's word, as in v1.610
            value = record["checked"]
            if type(value) is not bool:
                raise ValueError(f"pair_id {rec['pair_id']!r}: its {side} record's checked must "
                                 f"be true or false, got {value!r}")
            if checked and not value:
                raise ValueError(f"pair_id {rec['pair_id']!r}: its {side} record says checked "
                                 f"false, so its call ran no validate and the check cannot "
                                 f"label it")

    def correct(side: dict) -> Optional[bool]:
        outcome = side.get("outcome")
        if outcome == "error":
            return None                   # no answer, so never a wrong one
        if checked:
            return {"ok": True, "invalid": False}.get(outcome)
        if audits is not None:  # review iter-461 should-fix 2: the check rejected it
            return False if outcome == "invalid" else audits.get(side.get("call_id"))
        return None

    result = []
    for rec in shadows:
        routed = finals[rec["pair_id"]][0]
        result.append({"pair_id": rec["pair_id"], "task": routed.get("task"),
                       "slice": routed.get("slice"), "routed_route": _entry(routed),
                       "shadow_route": rec.get("model"), "shadow_call_id": rec.get("call_id"),
                       "shadow_outcome": rec.get("outcome"), "routed_correct": correct(routed),
                       "shadow_correct": correct(rec)})
    return result


def pair_results(pairs: Iterable[dict], *, records: Optional[Iterable[dict]] = None,
                 routes: Optional[Sequence[str]] = None) -> List[dict]:
    """The labeled results rows of a pair file, two per pair with both sides labelled (DESIGN 8.3 v1.613).

    Each such pair gives ``{"task", "model", "item", "correct"}`` for its routed route, then for its
    shadow route, the item its ``pair_id``, with ``slice`` last when the pair's is not None, so
    ``calibrate_from_results`` and ``item_outcomes`` read them; a pair with a None side adds no
    row. Every pair is checked before any row is returned, and a bad one raises ``ValueError``
    naming its 1-based position; a cascade or procedure route is refused, since its row would
    need ``escalated`` or ``cost_usd``, which a pair does not hold.

    v1.614: with ``records``, the monitor log the pairs came from, each row gains ``cost_usd``
    right after ``correct``, its side's final record's alone (a fallback's row is not charged for
    the failed attempt before it); with ``routes``, ``(routed, shadow)``, only that route pair's
    pairs give rows, so ``evaluate`` (DESIGN 12.3) reads them as a complete outcome matrix.
    """
    if routes is not None and (not isinstance(routes, (list, tuple)) or len(routes) != 2
                               or not all(isinstance(r, str) and r for r in routes)
                               or routes[0] == routes[1]):
        raise ValueError(f"routes must be None or a list or tuple of two different non-empty "
                         f"strings, got {routes!r}")
    if records is not None:
        records = list(records)
        for position, rec in enumerate(records, start=1):
            if not isinstance(rec, Mapping):
                raise ValueError(f"record {position} must be a mapping, got {rec!r}")
    pairs = list(pairs)
    seen: Dict[str, int] = {}
    for position, item in enumerate(pairs, start=1):
        where = f"pair {position}"
        if not isinstance(item, Mapping):
            raise ValueError(f"{where} must be a mapping, got {item!r}")
        for key in ("pair_id", "task", "routed_route", "shadow_route"):
            value = item.get(key)
            if not isinstance(value, str) or not value:
                raise ValueError(f"{where}: {key} must be a non-empty string, got {value!r}")
        name = item.get("slice")
        if name is not None and (not isinstance(name, str) or not name or "@" in name):
            raise ValueError(f"{where}: slice must be null or a non-empty string without '@', "
                             f"got {name!r}")
        if name is not None and "@" in item["task"]:  # review iter-464 must-fix 1 (4.3 v1.511)
            raise ValueError(f"{where}: a sliced pair's task must hold no '@', got {item['task']!r}")
        for key in ("routed_correct", "shadow_correct"):
            if item.get(key) is not None and type(item.get(key)) is not bool:
                raise ValueError(f"{where}: {key} must be true, false or null, got {item.get(key)!r}")
        if item["routed_route"] == item["shadow_route"]:
            raise ValueError(f"{where}: routed_route and shadow_route are both "
                             f"{item['routed_route']!r}, so it compares no two routes")
        for key in ("routed_route", "shadow_route"):
            if ">" in item[key] or item[key].startswith("proc:"):
                raise ValueError(f"{where}: {key} {item[key]!r} is a cascade's or a procedure's, "
                                 "whose row needs escalated or cost_usd, which a pair does not hold")
        if item["pair_id"] in seen:
            raise ValueError(f"{where}: pair_id {item['pair_id']!r} is also pair "
                             f"{seen[item['pair_id']]}'s")
        seen[item["pair_id"]] = position
    kept = [(position, item) for position, item in enumerate(pairs, start=1)
            if item.get("routed_correct") is not None and item.get("shadow_correct") is not None
            and (routes is None or (item["routed_route"], item["shadow_route"]) == tuple(routes))]
    costs = None if records is None else _pair_costs(kept, records)
    rows = []
    for position, item in kept:
        for side, route, correct in (("routed", "routed_route", "routed_correct"),
                                     ("shadow", "shadow_route", "shadow_correct")):
            out = {"task": item["task"], "model": item[route], "item": item["pair_id"],
                   "correct": item[correct]}
            if costs is not None:
                out["cost_usd"] = costs[position, side]
            if item.get("slice") is not None:
                out["slice"] = item["slice"]
            rows.append(out)
    return rows


def _pair_costs(kept: List[tuple], records: List[Mapping]) -> Dict[tuple, object]:
    """Each kept pair's side costs, ``{(position, side): cost_usd}``, read from the final record of
    its routed call and of its shadow call in the log (DESIGN 8.3 v1.614)."""
    records = [rec for rec in records if "budget_event" not in rec]
    routed: Dict[str, List[Mapping]] = {}
    shadow: Dict[tuple, List[Mapping]] = {}
    for rec in records:
        if rec.get("final") is not True:
            continue
        call_id, pair_id = rec.get("call_id"), rec.get("pair_id")
        if not isinstance(call_id, str) or not isinstance(pair_id, str):
            continue
        if rec.get("shadow") is True:
            shadow.setdefault((pair_id, call_id), []).append(rec)
        elif call_id == pair_id:
            routed.setdefault(pair_id, []).append(rec)
    costs: Dict[tuple, object] = {}
    for position, item in kept:
        where, pair_id = f"pair {position}", item["pair_id"]
        found = routed.get(pair_id, [])
        if len(found) != 1:
            raise ValueError(f"{where}: its routed call {pair_id!r} has "
                             f"{'no' if not found else len(found)} final record"
                             f"{'s' if len(found) > 1 else ''} in the log")
        routed_rec = found[0]
        call_id = item.get("shadow_call_id")
        if not isinstance(call_id, str) or not call_id:
            raise ValueError(f"{where}: shadow_call_id must be a non-empty string, got {call_id!r}")
        found = shadow.get((pair_id, call_id), [])
        if len(found) != 1:
            raise ValueError(f"{where}: its shadow call {call_id!r} has "
                             f"{'no' if not found else len(found)} final record"
                             f"{'s' if len(found) > 1 else ''} in the log")
        shadow_rec = found[0]
        if _entry(routed_rec) != item["routed_route"]:  # the pair is not of this log
            raise ValueError(f"{where}: the log's routed call {pair_id!r} ends on "
                             f"{_entry(routed_rec)!r}, not on its routed_route "
                             f"{item['routed_route']!r}")
        if shadow_rec.get("model") != item["shadow_route"]:
            raise ValueError(f"{where}: the log's shadow call {call_id!r} ran "
                             f"{shadow_rec.get('model')!r}, not its shadow_route "
                             f"{item['shadow_route']!r}")
        for side, rec in (("routed", routed_rec), ("shadow", shadow_rec)):
            cost = rec.get("cost_usd")
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) \
                    or not isfinite(cost) or cost < 0:
                raise ValueError(f"{where}: the {side} final record's cost_usd must be a finite "
                                 f"number >= 0, got {cost!r}")
            costs[position, side] = cost
    return costs


def _window(budget: Budget, rec: dict) -> Optional[str]:
    """The label of ``budget``'s window that holds the record's ``ts``, None for ``total``."""
    if budget.window == "total":
        return None
    try:
        instant = _instant(rec.get("ts"))
    except ValueError:
        raise ValueError(f"call_id {rec.get('call_id')!r}: ts {rec.get('ts')!r} is no ISO 8601 "
                         f"timestamp, so budget {budget.name!r} cannot read its window") from None
    label = f"{instant.year:04d}-{instant.month:02d}"
    return label + f"-{instant.day:02d}" if budget.window == "day" else label
