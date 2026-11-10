"""Per-attempt JSONL logging and cost and reliability reports."""

from __future__ import annotations

import json
from math import ceil
from pathlib import Path
from typing import Dict, Iterable, List, Optional, Union

PathLike = Union[str, Path]

_GROUP_KEYS = ("model", "task", "flavor", "family")
NO_TAG = "(none)"


class Monitor:
    """Collects attempt records in memory and optionally appends them to a JSONL file."""

    def __init__(self, path: Optional[PathLike] = None):
        self.path = Path(path) if path is not None else None
        self.records: List[dict] = []

    def record(self, rec: dict) -> None:
        """Store one attempt record and append it to the log file when set."""
        self.records.append(rec)
        if self.path is not None:
            with self.path.open("a", encoding="utf-8") as handle:
                handle.write(json.dumps(rec) + "\n")


def load_records(path: PathLike) -> List[dict]:
    """Read a JSONL file of objects, skipping blank lines.

    A line that is not valid JSON, or not a JSON object, raises ``ValueError``
    naming ``<path>:<line number>``.
    """
    records = []
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
            records.append(value)
    return records


def _grouper(by: str):
    if by in _GROUP_KEYS:
        return lambda rec: str(rec.get(by))
    if by.startswith("tag:") and len(by) > 4:
        key = by[4:]
        return lambda rec: (rec.get("tags") or {}).get(key, NO_TAG)
    raise ValueError(f"unknown report key {by!r}; use model, task, flavor, family or tag:<key>")


def _nearest_rank(sorted_values: List[float], q: float) -> Optional[float]:
    if not sorted_values:
        return None
    index = max(0, ceil(q * len(sorted_values)) - 1)
    return sorted_values[index]


def report(records: Iterable[dict], by: str = "model") -> List[dict]:
    """Aggregate attempt records by ``by``.

    Attempt-level sums use each attempt; call-level counts (``calls``,
    ``failed_calls``, ``fallback_calls``) use the group of the call's final
    attempt. ``below_bar_calls`` (the last key) counts the calls whose final
    attempt is ``ok`` on a model under the bar: its record's ``below_bar`` or
    ``below_bar_fallback`` is true (DESIGN 8.1, 8.3, v1.203). Rows are sorted
    by descending ``cost_usd``, then ``group``.
    """
    group_of = _grouper(by)
    groups: Dict[str, dict] = {}
    latencies: Dict[str, List[float]] = {}
    under: Dict[str, int] = {}
    for rec in records:
        group = group_of(rec)
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
            if int(rec.get("attempt", 0)) > 0:
                row["fallback_calls"] += 1
            if outcome == "ok" and (rec.get("below_bar") is True
                                    or rec.get("below_bar_fallback") is True):
                under[group] += 1
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
    rows.sort(key=lambda r: (-r["cost_usd"], r["group"]))
    return rows
