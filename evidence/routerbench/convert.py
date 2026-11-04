"""Convert the public RouterBench 0-shot frame into the evaluator's outcome matrix (DESIGN 12.6).

Usage: python evidence/routerbench/convert.py --out PATH [--cache DIR] [--pass-score T] [--min-items N]

Standard library only, except that reading the frame needs pandas (the ``evidence``
extra). The download is pinned by size and sha256 and checked before anything is
unpickled, and unpickling resolves only the 11 globals the pinned file references.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import pickle
import sys
import urllib.request
from pathlib import Path

REVISION = "784021482c3f320c6619ed4b3bb3b41a21424fcb"
FILENAME = "routerbench_0shot.pkl"
SIZE = 99567659
SHA256 = "ba4f77f19517610a707c374e99322d7750c30fc4ae7ff5527888595a1e65d36d"
URL = f"https://huggingface.co/datasets/withmartian/routerbench/resolve/{REVISION}/{FILENAME}"

# Exactly the globals the pinned file references (static pickletools scan, no code run).
ALLOWED_GLOBALS = frozenset({
    ("builtins", "slice"),
    ("numpy", "dtype"),
    ("numpy", "ndarray"),
    ("numpy.core.multiarray", "_reconstruct"),
    ("numpy.core.numeric", "_frombuffer"),
    ("pandas._libs.internals", "_unpickle_block"),
    ("pandas.core.frame", "DataFrame"),
    ("pandas.core.indexes.base", "Index"),
    ("pandas.core.indexes.base", "_new_Index"),
    ("pandas.core.indexes.range", "RangeIndex"),
    ("pandas.core.internals.managers", "BlockManager"),
})
META_COLUMNS = ("sample_id", "prompt", "eval_name", "oracle_model_to_route_to")
VENDOR_PREFIXES = (("claude-", "anthropic"), ("gpt-", "openai"))
COST_SUFFIX = "|total_cost"


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "routerbench"


def sha256_of(path: Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            digest.update(chunk)
    return digest.hexdigest()


def verify(path, size: int = SIZE, sha256: str = SHA256) -> None:
    path = Path(path)
    got_size = path.stat().st_size
    if got_size != size:
        raise ValueError(f"{path.name}: expected {size} bytes, got {got_size}")
    got = sha256_of(path)
    if got != sha256:
        raise ValueError(f"{path.name}: expected sha256 {sha256}, got {got}")


def fetch(cache_dir=None) -> Path:
    cache = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    target = cache / FILENAME
    if target.exists():
        verify(target, SIZE, SHA256)
        return target
    cache.mkdir(parents=True, exist_ok=True)
    part = cache / (FILENAME + ".part")
    try:
        with urllib.request.urlopen(URL, timeout=60) as response, part.open("wb") as out:
            for chunk in iter(lambda: response.read(1 << 20), b""):
                out.write(chunk)
        verify(part, SIZE, SHA256)
    except BaseException:
        part.unlink(missing_ok=True)
        raise
    part.replace(target)
    return target


class RestrictedUnpickler(pickle.Unpickler):
    """Resolves only the exact (module, name) pairs in ALLOWED_GLOBALS."""

    def find_class(self, module, name):
        if (module, name) not in ALLOWED_GLOBALS:
            raise pickle.UnpicklingError(f"refused global {module}.{name}")
        return super().find_class(module, name)

    def persistent_load(self, pid):
        raise pickle.UnpicklingError("refused persistent id")


def restricted_load(fileobj):
    return RestrictedUnpickler(fileobj, fix_imports=False).load()


def model_id(column: str) -> str:
    if not isinstance(column, str) or not column:
        raise ValueError(f"model column {column!r} is not a non-empty string")
    if "/" in column:
        return column
    for prefix, vendor in VENDOR_PREFIXES:
        if column.startswith(prefix):
            return f"{vendor}/{column}"
    raise ValueError(f"model column {column!r} has no known vendor; add it to VENDOR_PREFIXES")


def _model_columns(names) -> list[str]:
    return [c for c in names if isinstance(c, str) and "|" not in c and c not in META_COLUMNS]


def frame_columns(frame) -> dict[str, list]:
    names = list(frame.columns)
    for key in ("sample_id", "eval_name"):
        if key not in names:
            raise ValueError(f"frame has no {key} column")
    models = _model_columns(names)
    if not models:
        raise ValueError("frame has no model column")
    out = {"sample_id": frame["sample_id"].tolist(), "eval_name": frame["eval_name"].tolist()}
    for m in models:
        if m + COST_SUFFIX not in names:
            raise ValueError(f"model column {m!r} has no {m + COST_SUFFIX!r} column")
        out[m] = frame[m].tolist()
        out[m + COST_SUFFIX] = frame[m + COST_SUFFIX].tolist()
    return out


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_options(pass_score, min_items) -> None:
    if pass_score is not None and not (_is_number(pass_score) and 0 < pass_score <= 1):
        raise ValueError(f"pass_score must be None or a number in (0, 1], got {pass_score!r}")
    if isinstance(min_items, bool) or not isinstance(min_items, int) or min_items < 1:
        raise ValueError(f"min_items must be an int >= 1, got {min_items!r}")


def convert(columns: dict, pass_score=None, min_items: int = 100) -> tuple[list[dict], dict]:
    _check_options(pass_score, min_items)
    for key in ("sample_id", "eval_name"):
        if key not in columns:
            raise ValueError(f"no {key} column")
    ids, tasks = columns["sample_id"], columns["eval_name"]
    models = _model_columns(columns)
    if not models:
        raise ValueError("no model column")
    names, seen_ids = {}, {}
    for m in models:
        if m + COST_SUFFIX not in columns:
            raise ValueError(f"model column {m!r} has no {m + COST_SUFFIX!r} column")
        mid = model_id(m)
        if mid in seen_ids:
            raise ValueError(f"columns {seen_ids[mid]!r} and {m!r} both map to model {mid!r}")
        seen_ids[mid], names[m] = m, mid
    n = len(ids)
    for key in ["eval_name"] + [c for m in models for c in (m, m + COST_SUFFIX)]:
        if len(columns[key]) != n:
            raise ValueError(f"column {key!r} has length {len(columns[key])}, sample_id has {n}")
    seen = set()
    for i in range(n):
        if not isinstance(ids[i], str) or not ids[i]:
            raise ValueError(f"row {i}: sample_id {ids[i]!r} is not a non-empty string")
        if ids[i] in seen:
            raise ValueError(f"sample_id {ids[i]!r} is repeated")
        seen.add(ids[i])
        if not isinstance(tasks[i], str) or not tasks[i]:
            raise ValueError(f"{ids[i]}: eval_name {tasks[i]!r} is not a non-empty string")
        for m in models:
            score, cost = columns[m][i], columns[m + COST_SUFFIX][i]
            if not _is_number(score) or not 0 <= score <= 1:
                raise ValueError(f"{ids[i]}: score {score!r} in column {m!r} is not a number in [0, 1]")
            if not _is_number(cost) or not math.isfinite(cost) or cost < 0:
                raise ValueError(f"{ids[i]}: cost {cost!r} in column {m + COST_SUFFIX!r} is not a "
                                 "finite number >= 0")
    by_task: dict[str, list[int]] = {}
    for i in range(n):
        by_task.setdefault(tasks[i], []).append(i)
    rows, kept, dropped_graded, dropped_small = [], {}, {}, {}
    for task in sorted(by_task):
        index = by_task[task]
        graded = any(columns[m][i] not in (0, 1) for i in index for m in models)
        if graded and pass_score is None:
            dropped_graded[task] = len(index)
            continue
        if len(index) < min_items:
            dropped_small[task] = len(index)
            continue
        kept[task] = len(index)
        for i in sorted(index, key=lambda j: ids[j]):
            for m in sorted(models, key=lambda c: names[c]):
                score = columns[m][i]
                correct = score >= pass_score if pass_score is not None else score == 1
                rows.append({"task": task, "item": ids[i], "model": names[m],
                             "correct": bool(correct),
                             "cost_usd": float(columns[m + COST_SUFFIX][i])})
    report = {"models": sorted(names.values()), "kept": kept, "dropped_graded": dropped_graded,
              "dropped_small": dropped_small, "rows": len(rows)}
    return rows, report


def write_jsonl(rows, path) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def _pass_score(text: str) -> float:
    value = float(text)
    _check_options(value, 1)
    return value


def _min_items(text: str) -> int:
    value = int(text)
    _check_options(None, value)
    return value


def main(argv=None) -> int:
    parser = _Parser(prog="convert.py", description="RouterBench 0-shot to an outcome matrix")
    parser.add_argument("--out", required=True, help="output JSONL path")
    parser.add_argument("--cache", default=None, help="download folder (default: %(default)s)")
    parser.add_argument("--pass-score", type=_pass_score, default=None,
                        help="keep graded tasks, correct when score >= this (0, 1]")
    parser.add_argument("--min-items", type=_min_items, default=100,
                        help="drop tasks with fewer items (default: %(default)s)")
    try:
        args = parser.parse_args(argv)
        path = fetch(args.cache)
        with path.open("rb") as f:
            frame = restricted_load(f)
        rows, report = convert(frame_columns(frame), args.pass_score, args.min_items)
        out = Path(args.out)
        part = out.with_name(out.name + ".part")
        write_jsonl(rows, part)
        part.replace(out)
    except (_UsageError, ValueError, OSError, pickle.UnpicklingError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
