"""Per-attempt JSONL logging and cost and reliability reports."""

from __future__ import annotations

import json
import threading
from math import ceil, fsum, isfinite
from pathlib import Path
from typing import Dict, Iterable, List, Mapping, Optional, Sequence, Tuple, Union

from .budget import Budget, _instant
from .stats import Stats, wilson_lower_bound
from .tasks import Task

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


def load_logs(paths: Sequence[PathLike]) -> List[dict]:
    """Read many monitor logs as one record stream, in the order given (DESIGN 8.2 v1.620).

    ``paths`` is a non-empty list or tuple of paths, each read with ``load_records``' rules; a
    ``call_id`` in two files is one call's records (a log rotated between two of its attempts),
    so give a rotated log's files in the order they were written. A record equal to a record of an earlier file,
    compared as ``json.dumps(record, sort_keys=True)``, raises ``ValueError`` naming both
    ``<path>:<line number>``s: one attempt in two files is a log given twice or a copy of one.
    No record is compared with another of its own file, so ``load_logs([path])`` is
    ``load_records(path)``.
    """
    if not isinstance(paths, (list, tuple)) or not paths \
            or not all(isinstance(path, (str, Path)) for path in paths):
        raise ValueError(f"paths must be a non-empty list or tuple of paths, got {paths!r}")
    records: List[dict] = []
    earlier: Dict[str, str] = {}
    compare = len(paths) > 1
    for path in paths:
        here: Dict[str, str] = {}
        for number, value in _numbered_objects(path):
            if compare:
                key = json.dumps(value, sort_keys=True)
                if key in earlier:
                    raise ValueError(f"{path}:{number}: the same record as {earlier[key]}: a log "
                                     f"given twice, or a copy of one, would count it twice")
                here.setdefault(key, f"{path}:{number}")
            records.append(value)
        for key, where in here.items():
            earlier.setdefault(key, where)
    return records


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
    ``checked`` key that is not a real bool is refused whatever the labels. Budget records
    are dropped first, so a shadow that was not sent or whose hold was refused has no pair.
    A bad argument, or a log the executor cannot write, raises ``ValueError`` before any pair
    is returned.
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
                                 f"false: its call ran no acceptance check (validate), so "
                                 f"checked=True (--checked) cannot label it; label it by "
                                 f"audits or leave it unlabelled")

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

    v1.621: with ``records``, a routed side that is a cascade or a procedure gives its row too, at
    the summed cost of its route entry's records, a cascade's row with ``escalated`` after
    ``cost_usd``; a cascade or procedure ``shadow_route`` is still refused (DESIGN 8.3 v1.621).
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
            if _entry_kind(item[key]) is None:
                continue
            if records is None:
                raise ValueError(f"{where}: {key} {item[key]!r} is a cascade's or a procedure's, "
                                 "whose row needs escalated or cost_usd, which a pair does not hold")
            if key == "shadow_route":  # DESIGN 8.3 v1.621: 4.2 v1.607 shadows on a registry model
                raise ValueError(f"{where}: {key} {item[key]!r} is a cascade's or a procedure's, "
                                 "which the executor never shadows on, since it shadows on a "
                                 "registry model only, so the pair is not of a monitor log")
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
                if side == "routed" and (position, "escalated") in costs:  # DESIGN 8.3 v1.621
                    out["escalated"] = costs[position, "escalated"]
            if item.get("slice") is not None:
                out["slice"] = item["slice"]
            rows.append(out)
    return rows


def audited_results(records: Iterable[dict], audits: Mapping[str, bool], *,
                    since: Optional[str] = None, until: Optional[str] = None) -> List[dict]:
    """The labeled results rows of a monitor log's audited calls (DESIGN 8.3 v1.632, row M1a).

    Budget records are dropped first. Each record of an audited call that holds an answer gives
    ``{"task", "model", "item", "correct"}``, the item its call ID, then the record's
    ``input_tokens`` and ``output_tokens`` when both are counts, and ``slice`` last when not None:
    the final ``ok`` record labelled by its audit, and each ``invalid`` record ``false``, since
    the task's check rejected it; an ``error`` record gives no row. With ``since`` or ``until``,
    ISO 8601 timestamps (no offset reads as UTC), only the calls whose final record's ``ts`` is in
    ``[since, until)`` give rows, so ``calibrate_from_results`` keeps a recent window's stats apart
    from the all-time file. Every audited call is checked before any row is returned, and a bad
    input raises ``ValueError``.

    v1.636 (row M1d): a cascade's or a procedure's route entry gives one row, its answer's: a
    cascade's ``model`` its ``cascade`` with ``escalated`` and no token counts, a procedure's its
    closing record's ``model`` with ``cost_usd``, the ``math.fsum`` of the entry's records; a
    handed-up cheap leg and a procedure's model calls give none (DESIGN 8.3 v1.636).

    v1.637 (row LAT2): each row carries ``latency_ms`` before ``slice``, its route entry's time to
    its answer: a plain record's, a cascade's legs' ``math.fsum``, a procedure's closing record's
    alone, which times its run; none when a value is not a finite number >= 0 (DESIGN 8.3 v1.637).
    """
    records = list(records)
    for position, rec in enumerate(records, start=1):
        if not isinstance(rec, Mapping):
            raise ValueError(f"record {position} must be a mapping, got {rec!r}")
    if not isinstance(audits, Mapping) or not all(
            isinstance(call_id, str) and call_id and type(correct) is bool
            for call_id, correct in audits.items()):
        raise ValueError("audits must be a mapping of call ID to true or false, "
                         f"got {audits!r}")
    bounds = []
    for name, value in (("since", since), ("until", until)):
        try:
            bounds.append(None if value is None else _instant(value))
        except ValueError:
            raise ValueError(f"{name} must be None or an ISO 8601 timestamp str, "
                             f"got {value!r}") from None
    start, end = bounds
    if start is not None and end is not None and not start < end:
        raise ValueError(f"since must be before until, got since={since!r} and until={until!r}")
    calls: Dict[str, List[Mapping]] = {}
    for rec in records:
        call_id = rec.get("call_id")
        if "budget_event" not in rec and isinstance(call_id, str) and call_id in audits:
            calls.setdefault(call_id, []).append(rec)
    rows: List[dict] = []
    for call_id, recs in calls.items():
        finals = [rec for rec in recs if rec.get("final") is True]
        if len(finals) != 1:
            raise ValueError(f"call_id {call_id!r} has {'no' if not finals else 'more than one'} "
                             "final record, so its audit cannot be joined")
        final = finals[0]
        kept = True
        if start is not None or end is not None:
            try:
                stamp = _instant(final.get("ts"))
            except ValueError:
                raise ValueError(f"call_id {call_id!r}: ts {final.get('ts')!r} is no ISO 8601 "
                                 "timestamp, so the window cannot read it") from None
            kept = (start is None or start <= stamp) and (end is None or stamp < end)
        for rec in recs:
            if "procedure" in rec and "model_calls" not in rec:
                continue                  # DESIGN 8.3 v1.636: a model call of a procedure's run
            if rec.get("outcome") == "invalid":
                correct = False
            elif rec.get("final") is True and rec.get("outcome") == "ok":   # the one final record
                correct = audits[call_id]
            else:
                continue                  # an error, or no answer of this call
            out = _audited_row(call_id, rec, correct, recs)
            if kept:
                rows.append(out)
    return rows


def _audited_row(call_id: str, rec: Mapping, correct: bool, recs: List[Mapping]) -> dict:
    """One row of ``audited_results``, its record's fields checked (DESIGN 8.3 v1.632); a
    cascade's or a procedure's entry checked as ``pair_results`` checks one (v1.636)."""
    kind = "cascade" if "cascade" in rec else "procedure" if "procedure" in rec else None
    for key in ("task", "cascade" if kind == "cascade" else "model"):
        value = rec.get(key)
        if not isinstance(value, str) or not value:
            raise ValueError(f"call_id {call_id!r}: {key} must be a non-empty string, got {value!r}")
    name = rec.get("slice")
    if name is not None and (not isinstance(name, str) or not name or "@" in name):
        raise ValueError(f"call_id {call_id!r}: slice must be null or a non-empty string "
                         f"without '@', got {name!r}")
    if name is not None and "@" in rec["task"]:   # DESIGN 4.3 v1.511
        raise ValueError(f"call_id {call_id!r}: a sliced call's task must hold no '@', "
                         f"got {rec['task']!r}")
    model = rec["cascade"] if kind == "cascade" else rec["model"]
    out = {"task": rec["task"], "model": model, "item": call_id, "correct": correct}
    times = [rec.get("latency_ms")]       # DESIGN 8.3 v1.637: a procedure's times its whole run
    if kind == "cascade":
        out["escalated"] = _audited_cascade(call_id, rec, model, recs)
        times = [other.get("latency_ms") for other in recs if _entry(other) == model]  # its legs
    elif kind == "procedure":
        out["cost_usd"] = _audited_procedure(call_id, rec, model, recs)
    else:
        sizes = (rec.get("input_tokens"), rec.get("output_tokens"))
        if all(isinstance(n, int) and not isinstance(n, bool) and n >= 0 for n in sizes):
            out["input_tokens"], out["output_tokens"] = sizes
    if all(_finite_cost(value) for value in times):
        try:
            total = fsum(times)
        except OverflowError:
            total = float("inf")
        if isfinite(total):
            out["latency_ms"] = total
    if name is not None:
        out["slice"] = name
    return out


def _audited_cascade(call_id: str, rec: Mapping, model: str, recs: List[Mapping]) -> bool:
    """A cascade row's ``escalated``, its entry checked as v1.621 checks one (DESIGN 8.3 v1.636)."""
    if ">" not in model or model.startswith("proc:"):
        raise ValueError(f"call_id {call_id!r}: cascade must be a cascade's route ID, holding '>' "
                         f"and not starting with 'proc:', got {model!r}")
    escalated = rec.get("escalated")
    if type(escalated) is not bool:
        raise ValueError(f"call_id {call_id!r}: its cascade record's escalated must be true or "
                         f"false, got {escalated!r}")
    legs = [other for other in recs if _entry(other) == model]
    if not escalated and len(legs) != 1:
        raise ValueError(f"call_id {call_id!r}: its cascade {model!r} kept its cheap answer, so its "
                         "route entry needs that record alone, and the call holds "
                         f"{len(legs)} records of it")
    if escalated and (len(legs) != 2 or legs[1] is not rec or legs[0].get("escalated") is not True
                      or legs[0].get("final") is True):
        raise ValueError(f"call_id {call_id!r}: its cascade {model!r} handed up, so its route entry "
                         "needs its cheap leg's record (escalated true, final not true) before this "
                         f"one, and the call holds {len(legs)} record{'' if len(legs) == 1 else 's'} "
                         "of it")
    return escalated


def _audited_procedure(call_id: str, rec: Mapping, model: str, recs: List[Mapping]) -> float:
    """A procedure row's ``cost_usd``, the ``math.fsum`` of its entry's records, checked as v1.621
    checks them (DESIGN 8.3 v1.636)."""
    if not model.startswith("proc:"):
        raise ValueError(f"call_id {call_id!r}: a procedure's closing record's model must be its "
                         f"route ID, starting with 'proc:', got {model!r}")
    count = rec.get("model_calls")
    if type(count) is not int or count < 0:
        raise ValueError(f"call_id {call_id!r}: its procedure's closing record's model_calls must be "
                         f"an integer >= 0, got {count!r}")
    legs = [other for other in recs if _entry(other) == model]
    earlier = [other for other in legs if other is not rec]
    if len(earlier) != count:
        raise ValueError(f"call_id {call_id!r}: its procedure {model!r} made {count} model "
                         f"call{'' if count == 1 else 's'}, and the call holds {len(earlier)} "
                         f"record{'' if len(earlier) == 1 else 's'} of them")
    if not _finite_cost(rec.get("cost_usd")):
        raise ValueError(f"call_id {call_id!r}: its procedure's closing record's cost_usd must be a "
                         f"finite number >= 0, got {rec.get('cost_usd')!r}")
    for other in earlier:
        if not _finite_cost(other.get("cost_usd")):
            raise ValueError(f"call_id {call_id!r}: a record of its procedure {model!r} before its "
                             f"closing one has cost_usd {other.get('cost_usd')!r}, not a finite "
                             "number >= 0")
    try:
        total = fsum(other["cost_usd"] for other in legs)
    except OverflowError:
        total = float("inf")
    if not isfinite(total):
        raise ValueError(f"call_id {call_id!r}: the costs of its procedure {model!r} sum past the "
                         "largest float")
    return total


def _finite_cost(value: object) -> bool:
    """A finite number >= 0, never a bool, as 12.1 reads a cost (DESIGN 8.3 v1.614)."""
    return not isinstance(value, bool) and isinstance(value, (int, float)) and isfinite(value) \
        and value >= 0


FELL_BELOW, ROSE_ABOVE = "fell_below", "rose_above"   # DESIGN 8.3 v1.633


def drift_check(all_time: Stats, window: Stats, tasks: Mapping[str, Task]) -> List[dict]:
    """Judge each (task, route) key of two ``Stats`` against its task's bar (DESIGN 8.3 v1.633, row M1b).

    ``all_time`` is the stats a route is admitted on and ``window`` a recent window's, as
    ``calibrate_from_results(audited_results(..., since=...))`` gives them; ``tasks`` maps a task
    name to its ``Task``. One row per key of either, sorted, a key held by one alone read as 0 of 0
    in the other: ``task``, ``route``, both sides' successes, trials and Wilson lower bound at the
    task's confidence, then ``bar``, ``min_samples``, ``confidence`` and ``flag``. A side clears the
    bar when it holds at least ``min_samples`` trials and its bound is at or above ``bar``, as
    ``select`` admits a measured route; ``flag`` is ``"fell_below"`` when the all-time side clears
    and the window, with at least ``min_samples`` trials, does not, ``"rose_above"`` when the
    all-time side does not and the window does, else None. A ``<task>@<slice>`` key takes the
    slice's ``bar`` and ``min_samples`` where the task gives them, and a key of no task given has no
    row. A bad input raises ``ValueError`` before any row is returned.
    """
    for name, value in (("all_time", all_time), ("window", window)):
        if not isinstance(value, Stats):
            raise ValueError(f"{name} must be a Stats, got {type(value).__name__}")
    if not isinstance(tasks, Mapping):
        raise ValueError(f"tasks must be a mapping of task name to Task, got {type(tasks).__name__}")
    for key, task in tasks.items():
        if not isinstance(task, Task):
            raise ValueError(f"tasks[{key!r}] must be a Task, got {type(task).__name__}")
        if key != task.name:
            raise ValueError(f"tasks key {key!r} is not its task's name {task.name!r}")
    keys = sorted({key for key, _ in all_time.items()} | {key for key, _ in window.items()})
    rows: List[dict] = []
    for task_key, route in keys:
        judged = _drift_bar(task_key, tasks)
        if judged is None:
            continue                      # a key of no task given
        bar, min_samples, confidence = judged
        sides = []
        for stats in (all_time, window):
            successes, trials = stats.get(task_key, route)
            bound = wilson_lower_bound(successes, trials, confidence)
            sides.append((successes, trials, bound, trials >= min_samples and bound >= bar))
        (s_all, t_all, lb_all, clears_all), (s_win, t_win, lb_win, clears_win) = sides
        flag = None
        if t_win >= min_samples and clears_all != clears_win:
            flag = FELL_BELOW if clears_all else ROSE_ABOVE
        rows.append({"task": task_key, "route": route,
                     "all_time_successes": s_all, "all_time_trials": t_all, "all_time_lb": lb_all,
                     "window_successes": s_win, "window_trials": t_win, "window_lb": lb_win,
                     "bar": bar, "min_samples": min_samples, "confidence": confidence, "flag": flag})
    return rows


def _drift_bar(task_key: str, tasks: Mapping[str, Task]) -> Optional[Tuple[float, int, float]]:
    """``(bar, min_samples, confidence)`` of a stats key's task, a slice's own where its task gives
    them (DESIGN 5.2 v1.511, 8.3 v1.633), or None for a key of no task given."""
    if task_key in tasks:
        task = tasks[task_key]
        return task.bar, task.min_samples, task.confidence
    if task_key.count("@") != 1:
        return None
    base, name = task_key.split("@")
    if base not in tasks or not name:
        return None
    task = tasks[base]
    own = task.slices.get(name, {})
    return own.get("bar", task.bar), own.get("min_samples", task.min_samples), task.confidence


def _entry_kind(route: str) -> Optional[str]:
    """``"procedure"`` for a ``proc:`` route, ``"cascade"`` for any other holding ``>``, else None,
    as stats keys are read (DESIGN 4.3 v1.577, 8.3 v1.621)."""
    if route.startswith("proc:"):
        return "procedure"
    return "cascade" if ">" in route else None


def _pair_costs(kept: List[tuple], records: List[Mapping]) -> Dict[tuple, object]:
    """Each kept pair's side costs, ``{(position, side): cost_usd}``, read from the final record of
    its routed call and of its shadow call in the log (DESIGN 8.3 v1.614); a cascade's or a
    procedure's routed side sums its route entry's records, and a cascade's adds
    ``(position, "escalated")`` (v1.621)."""
    records = [rec for rec in records if "budget_event" not in rec]
    routed: Dict[str, List[Mapping]] = {}
    shadow: Dict[tuple, List[Mapping]] = {}
    calls: Dict[str, List[Mapping]] = {}  # v1.621: every record of each routed call, in log order
    for rec in records:
        call_id, pair_id = rec.get("call_id"), rec.get("pair_id")
        if not isinstance(call_id, str) or not isinstance(pair_id, str):
            continue
        if rec.get("shadow") is not True and call_id == pair_id:
            calls.setdefault(pair_id, []).append(rec)
        if rec.get("final") is not True:
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
        route = item["routed_route"]
        kind = _entry_kind(route)
        legs = [rec for rec in calls.get(pair_id, []) if _entry(rec) == route]
        earlier = [rec for rec in legs if rec is not routed_rec]
        if kind == "cascade":  # DESIGN 8.3 v1.621: the cheap leg, then the strong one if handed up
            escalated = routed_rec.get("escalated")
            if type(escalated) is not bool:
                raise ValueError(f"{where}: its routed cascade's final record's escalated must "
                                 f"be true or false, got {escalated!r}")
            if escalated and (len(earlier) != 1 or earlier[0].get("escalated") is not True
                              or earlier[0].get("final") is True):
                raise ValueError(f"{where}: its routed cascade {route!r} handed up, so its route "
                                 "entry needs its cheap leg's record (escalated true, final not "
                                 "true) and its final record, and the log holds "
                                 f"{len(legs)} record{'' if len(legs) == 1 else 's'} of it")
            if not escalated and earlier:
                raise ValueError(f"{where}: its routed cascade {route!r} kept its cheap answer, so "
                                 "its route entry needs its final record alone, and the log holds "
                                 f"{len(legs)} records of it")
            costs[position, "escalated"] = escalated
        elif kind == "procedure":  # its model calls, then the closing record
            count = routed_rec.get("model_calls")
            if type(count) is not int or count < 0:
                raise ValueError(f"{where}: its routed procedure's closing record's model_calls "
                                 f"must be an integer >= 0, got {count!r}")
            if len(earlier) != count:
                raise ValueError(f"{where}: its routed procedure {route!r} made {count} model "
                                 f"call{'' if count == 1 else 's'}, and the log holds "
                                 f"{len(earlier)} record{'' if len(earlier) == 1 else 's'} of them")
        for side, rec in (("routed", routed_rec), ("shadow", shadow_rec)):
            cost = rec.get("cost_usd")
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) \
                    or not isfinite(cost) or cost < 0:
                raise ValueError(f"{where}: the {side} final record's cost_usd must be a finite "
                                 f"number >= 0, got {cost!r}")
            costs[position, side] = cost
        if kind is not None:
            for rec in earlier:
                cost = rec.get("cost_usd")
                if isinstance(cost, bool) or not isinstance(cost, (int, float)) \
                        or not isfinite(cost) or cost < 0:
                    raise ValueError(f"{where}: a record of its routed entry {route!r} before its "
                                     f"final one has cost_usd {cost!r}, not a finite number >= 0")
            try:
                total = fsum(rec["cost_usd"] for rec in legs)
            except OverflowError:
                total = float("inf")
            if not isfinite(total):
                raise ValueError(f"{where}: the costs of its routed entry {route!r} sum past the "
                                 "largest float")
            costs[position, "routed"] = total
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
