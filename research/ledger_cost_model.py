"""Does the DESIGN 13.2 re-read rule predict the prompt tokens of the ledger runs?

Usage: python research/ledger_cost_model.py [--cache DIR]

Reads the pinned `single.jsonl` and `decomposed.jsonl` of the ledger runs and their run settings
through evidence/ledger-handoff/results.py (`fetch`, which checks each file by size and sha256,
then `read_json`, `read_lines` and `ledger`), and prints, per depth and path, the measured prompt
tokens per item against the ones the 13.2 work-call rule predicts. That rule has call j of a
context read X + j * S_in + (j - 1) * S_out, every earlier call's input and whole output re-read.
Here a context's first prompt is X + S_in, S_in is the run settings' `k` (the tokens each
transaction is padded to) and S_out of an earlier call is its `completion_tokens`, so call j reads
the first prompt + (j - 1) * k + the completions of the calls before it in its context. On the
chain each fresh context starts again from its own first prompt (the system message, the note and
the first transaction), and a note's call reads its context's history as one more call would,
without a transaction (13.2 gives the request no size). The `reply` rule is the same with each
earlier completion less its `reasoning_tokens`, the reply the history keeps. Standard library
only. Read by research/ledger-cost-model.md (DESIGN 12.22).
"""

from __future__ import annotations

import argparse
import importlib.util
import statistics
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
CONVERTER = _ROOT / "evidence" / "ledger-handoff" / "results.py"
PATHS = ("single", "chain")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def contexts(record: dict, chain: bool) -> list:
    """The record's contexts in order, each (steps, note or None): one context on `single`; on the
    chain one per note plus the last, split at each note's `after_t`."""
    steps, notes = record["steps"], (record.get("notes", []) if chain else [])
    found, start = [], 0
    for note in notes:
        end = next((i + 1 for i, s in enumerate(steps) if s.get("t") == note.get("after_t")), None)
        if end is None or end <= start:
            raise ValueError(f"L={record['L']} item={record['item']}: a note's after_t is no later step")
        found.append((steps[start:end], note))
        start = end
    if start >= len(steps):
        raise ValueError(f"L={record['L']} item={record['item']}: no step after the last note")
    found.append((steps[start:], None))
    return found


def predict(record: dict, chain: bool, k: int, reply: bool) -> int:
    """The prompt tokens the 13.2 rule predicts for the record, summed over its calls."""
    total = 0
    for steps, note in contexts(record, chain):
        first, read = steps[0]["prompt_tokens"], 0
        for j, step in enumerate(steps):
            total += first + j * k + read
            read += step["completion_tokens"] - (step["reasoning_tokens"] if reply else 0)
        if note is not None:  # the note's call: the history of the context, no transaction
            total += first + (len(steps) - 1) * k + read
    return total


def measured(record: dict, chain: bool) -> int:
    calls = record["steps"] + (record["notes"] if chain else [])
    return sum(call["prompt_tokens"] for call in calls)


def _ratio(values) -> str:
    q = statistics.quantiles(values, n=10, method="inclusive")
    return f"{statistics.median(values):.3f} ({q[0]:.3f} to {q[8]:.3f}, highest {max(values):.3f})"


def report(single: dict, chain: dict, k: int) -> list:
    lines = [f"k = {k} tokens per transaction; ratios are measured over predicted, median (10th to 90th percentile, highest)"]
    for depth in sorted({key[0] for key in single}):
        keys = sorted(key for key in single if key[0] == depth)
        lines.append("")
        lines.append(f"depth {depth}, {len(keys)} items")
        medians = {}
        for path, records in (("single", single), ("chain", chain)):
            rows = [records[key] for key in keys]
            is_chain = path == "chain"
            meas = [measured(r, is_chain) for r in rows]
            full = [predict(r, is_chain, k, reply=False) for r in rows]
            kept = [predict(r, is_chain, k, reply=True) for r in rows]
            medians[path] = [statistics.median(v) for v in (meas, full, kept)]
            lines.append(
                f"  {path}: measured {medians[path][0]:,.1f}, 13.2 rule {medians[path][1]:,.1f}, "
                f"ratio {_ratio([m / p for m, p in zip(meas, full)])}; "
                f"reply rule {medians[path][2]:,.1f}, ratio {_ratio([m / p for m, p in zip(meas, kept)])}")
        over = [a / b for a, b in zip(medians["single"], medians["chain"])]
        lines.append(f"  single over chain, medians: measured {over[0]:.2f}, 13.2 rule {over[1]:.2f}, reply rule {over[2]:.2f}")
        rows = [chain[key] for key in keys]
        share = statistics.median(sum(n["prompt_tokens"] for n in r["notes"]) / measured(r, True) for r in rows)
        notes = [n for r in rows for n in r["notes"]]
        lines.append(
            f"  chain notes: {share:.1%} of an item's measured prompt tokens (median); a note's call wrote a median of "
            f"{statistics.median(n['completion_tokens'] for n in notes):,} completion tokens for a note of "
            f"{statistics.median(n['note_tokens'] for n in notes):,}")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", default=None, help="the converter's cache folder (default its own)")
    args = parser.parse_args(argv)
    try:
        conv = _load(CONVERTER, "ledger_handoff_results")
        root = conv.fetch(args.cache)
        settings = {}
        for command in ("single", "decomposed"):
            name = conv.CONFIGS[command]
            settings[command] = conv.read_json(root / name)
            conv.check_config(settings[command], name, command)
        ks = {s.get("k") for s in settings.values()}
        if len(ks) != 1 or not isinstance(next(iter(ks)), int) or isinstance(next(iter(ks)), bool) or next(iter(ks)) < 1:
            raise ValueError("the two run settings files must give one int k of at least 1")
        k = ks.pop()
        single = conv.ledger(conv.read_lines(root / "single.jsonl"), "single.jsonl", notes=False)
        chain = conv.ledger(conv.read_lines(root / "decomposed.jsonl"), "decomposed.jsonl", notes=True)
        if set(single) != set(chain):
            raise ValueError("single.jsonl and decomposed.jsonl hold different (L, item) keys")
        for records in (single, chain):
            for record in records.values():
                for call in record["steps"]:
                    conv._int(call, "reasoning_tokens", f"L={record['L']} item={record['item']}", 0)
        print("\n".join(report(single, chain, k)))
    except (ValueError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
