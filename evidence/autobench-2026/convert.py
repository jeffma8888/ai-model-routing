"""Convert the public AutoBench Router Benchmark 2026 into the evaluator's outcome matrix (DESIGN 12.9).

Usage: python evidence/autobench-2026/convert.py --out PATH [--cache DIR] [--width W] [--task-by {domain,all}]
                                                 [--tokens] [--registry PATH]

Standard library only. Every file is pinned by size and sha256 and checked before it is
read; the dataset's own SHA256SUMS must agree with the pins. Success is the dataset's
Delta-Hit: a score within ``width`` of the mean of the best ``top_k`` pool scores on the
same question, which is relative to this pool and not an absolute acceptance check.
``--tokens`` adds each call's token counts to the rows and ``--registry`` writes a models.json
registry from the pool's list prices: the inputs of the delegation evidence (DESIGN 13.9).
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import math
import os
import re
import sys
import urllib.request
from pathlib import Path

DATASET = "AutoBench/router-benchmark-2026-10"
REVISION = "43755180be7d8097068982d7a3f37fc04cd15379"
BASE_URL = f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/"
SUMS = "SHA256SUMS"
# name -> (bytes, sha256); these pins are the trust root, SHA256SUMS is a second check.
FILES = {
    "matrix.csv": (1899644, "56d7a5c0a586364c8a0c0d5d737d0a4fde2a311a806b93beee38300e668ba28c"),
    "questions.csv": (298329, "c09fff8818218333bb5773e5f96754b41a312c8aa733972cb68f6be024afccb2"),
    "pool.json": (6582, "86c83dcbab072a912a1f61f79c76f32d394fad4e2ecccdbc0c80c2a5b40f67a8"),
    "frozen_params.json": (2042, "53b27f66d85f820637e9bb6215a80d9364b14707c3ff52b1632c1fe4221d76b7"),
    SUMS: (1198, "2bb56265da42a3743a493f6b27e2e100597a78ec1724ae4a288fe585ec56b08a"),
}
TASK_BY = ("domain", "all")
SUMS_LINE = re.compile(r"([0-9a-f]{64})  (\S.*)")


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "autobench-2026"


def sha256_of(path: Path) -> str:
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


def check_sums(text: str) -> None:
    listed = {}
    for i, line in enumerate(text.splitlines(), 1):
        if not line.strip():
            continue
        match = SUMS_LINE.fullmatch(line)
        if not match:
            raise ValueError(f"{SUMS} line {i} is not '<sha256>  <name>': {line!r}")
        listed[match.group(2)] = match.group(1)
    for name, (_, sha) in FILES.items():
        if name == SUMS:
            continue
        if name not in listed:
            raise ValueError(f"{SUMS} has no entry for {name}")
        if listed[name] != sha:
            raise ValueError(f"{SUMS} lists sha256 {listed[name]} for {name}, pinned {sha}")


def fetch(cache_dir=None) -> Path:
    cache = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    for name, (size, sha) in FILES.items():
        target = cache / name
        if target.exists():
            verify(target, size, sha)
            continue
        cache.mkdir(parents=True, exist_ok=True)
        part = cache / (name + ".part")
        try:
            with urllib.request.urlopen(BASE_URL + name, timeout=60) as response, part.open("wb") as out:
                for chunk in iter(lambda: response.read(1 << 20), b""):
                    out.write(chunk)
            verify(part, size, sha)
        except BaseException:
            part.unlink(missing_ok=True)
            raise
        part.replace(target)
    check_sums((cache / SUMS).read_text(encoding="utf-8"))
    return cache


def model_id(openrouter_id: str) -> str:
    if not isinstance(openrouter_id, str) or openrouter_id.count("/") != 1:
        raise ValueError(f"model ID {openrouter_id!r} is not of the form vendor/model")
    vendor, model = openrouter_id.split("/")
    if not vendor or not model:
        raise ValueError(f"model ID {openrouter_id!r} is not of the form vendor/model")
    vendor = re.sub("-", "", vendor)
    if not vendor:
        raise ValueError(f"model ID {openrouter_id!r} has an empty vendor once hyphens are removed")
    return f"{vendor}/{model}"


def _text(value) -> bool:
    return isinstance(value, str) and bool(value)


def pool_models(pool) -> dict[str, str]:
    members = pool.get("members") if isinstance(pool, dict) else None
    if not isinstance(members, list) or not members:
        raise ValueError("pool has no non-empty members list")
    names, owner = {}, {}
    for entry in members:
        if not isinstance(entry, dict):
            raise ValueError(f"pool member {entry!r} is not an object")
        display, ident = entry.get("display_id"), entry.get("openrouter_id")
        if not _text(display) or not _text(ident):
            raise ValueError(f"pool member {entry!r} needs a display_id and an openrouter_id")
        if display in names:
            raise ValueError(f"pool display ID {display!r} is repeated")
        mid = model_id(ident)
        if mid in owner:
            raise ValueError(f"pool members {owner[mid]!r} and {display!r} both map to {mid!r}")
        names[display], owner[mid] = mid, display
    return names


def _price(entry, key: str, display: str) -> float:
    value = entry.get(key)
    try:
        number = float(value) if _is_number(value) else math.nan
    except OverflowError:
        number = math.nan
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"pool member {display!r}: {key} must be a finite number >= 0, got {value!r}")
    return number


def pool_registry(pool) -> dict:
    names = pool_models(pool)
    models = []
    for entry in pool["members"]:
        display = entry["display_id"]
        family = entry.get("family")
        if not _text(family):
            raise ValueError(f"pool member {display!r}: family must be a non-empty string, got {family!r}")
        price_in = _price(entry, "input_cost_per_mtok", display)
        price_out = _price(entry, "output_cost_per_mtok", display)
        window = entry.get("context_window")
        if isinstance(window, bool) or not isinstance(window, int) or window < 1:
            raise ValueError(f"pool member {display!r}: context_window must be an int >= 1, got {window!r}")
        models.append({"id": names[display], "family": family, "price_in": price_in, "price_out": price_out,
                       "context_window": window})
    models.sort(key=lambda m: m["id"])
    return {"source": {"dataset": DATASET, "revision": REVISION, "file": "pool.json"}, "models": models}


def delta_hit(score, pool_scores, width, top_k) -> bool:
    top = sorted(pool_scores, reverse=True)[:top_k]
    reference = math.fsum(top) / top_k
    return bool(score >= reference - width)


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _check_options(width, top_k, task_by, pool_size) -> None:
    if not _is_number(width) or not math.isfinite(width) or width <= 0:
        raise ValueError(f"width must be a finite number > 0, got {width!r}")
    if isinstance(top_k, bool) or not isinstance(top_k, int) or not 1 <= top_k <= pool_size:
        raise ValueError(f"top_k must be an int from 1 to {pool_size}, got {top_k!r}")
    if task_by not in TASK_BY:
        raise ValueError(f"task_by must be one of {', '.join(TASK_BY)}, got {task_by!r}")


def _finite(text, what: str, pid: str, model: str) -> float:
    try:
        value = float(text) if isinstance(text, str) else math.nan
    except ValueError:
        value = math.nan
    if not math.isfinite(value):
        raise ValueError(f"{pid}, {model}: {what} {text!r} is not a finite number")
    return value


def _count(text, what: str, pid: str, model: str) -> int:
    value = _finite(text, what, pid, model)
    if value < 0 or not value.is_integer():
        raise ValueError(f"{pid}, {model}: {what} {text!r} is not a whole number >= 0")
    return int(value)


def convert(matrix, questions, pool, width, top_k: int = 3, task_by: str = "domain", tokens: bool = False):
    names = pool_models(pool)
    _check_options(width, top_k, task_by, len(names))
    if not isinstance(tokens, bool):
        raise ValueError(f"tokens must be a bool, got {tokens!r}")
    task_of = {}
    for q in questions:
        pid = q.get("prompt_id") if isinstance(q, dict) else None
        if not _text(pid):
            raise ValueError(f"question {q!r} has no prompt_id")
        if pid in task_of:
            raise ValueError(f"question {pid!r} is repeated")
        if task_by == "domain":
            domain = q.get("ddc_domain")
            if not _text(domain):
                raise ValueError(f"question {pid!r} has no ddc_domain")
            task_of[pid] = domain
        else:
            task_of[pid] = "all"
    seen, scores, out_of_pool = set(), {pid: {} for pid in task_of}, {}
    for r in matrix:
        pid, model = (r.get("prompt_id"), r.get("model")) if isinstance(r, dict) else (None, None)
        if not _text(pid) or not _text(model):
            raise ValueError(f"matrix row {r!r} needs a prompt_id and a model")
        if pid not in task_of:
            raise ValueError(f"matrix row for {pid!r}, {model!r} names no question")
        if (pid, model) in seen:
            raise ValueError(f"matrix cell {pid!r}, {model!r} is repeated")
        seen.add((pid, model))
        if model not in names:
            out_of_pool[model] = out_of_pool.get(model, 0) + 1
            continue
        score = r.get("score")
        if score is None or score == "":
            continue
        value = _finite(score, "score", pid, model)
        cost = _finite(r.get("cost"), "cost", pid, model)
        if cost < 0:
            raise ValueError(f"{pid}, {model}: cost {r.get('cost')!r} is below 0")
        counts = (_count(r.get("input_tokens"), "input_tokens", pid, model),
                  _count(r.get("output_tokens"), "output_tokens", pid, model)) if tokens else None
        scores[pid][model] = (value, 0.0 if cost == 0 else cost, counts)
    rows, kept, dropped, unscored = [], {}, {}, 0
    for pid in sorted(task_of):
        task, cells = task_of[pid], scores[pid]
        if len(cells) < len(names):
            dropped[task] = dropped.get(task, 0) + 1
            unscored += len(names) - len(cells)
            continue
        kept[task] = kept.get(task, 0) + 1
        pool_scores = [cells[d][0] for d in names]
        for display, mid in names.items():
            value, cost, counts = cells[display]
            out = {"task": task, "item": pid, "model": mid,
                   "correct": delta_hit(value, pool_scores, width, top_k), "cost_usd": cost}
            if counts is not None:
                out["input_tokens"], out["output_tokens"] = counts
            rows.append(out)
    rows.sort(key=lambda x: (x["task"], x["item"], x["model"]))
    report = {"models": sorted(names.values()), "width": width, "top_k": top_k, "task_by": task_by,
              "kept": dict(sorted(kept.items())), "dropped_unscored": dict(sorted(dropped.items())),
              "unscored_cells": unscored, "dropped_out_of_pool": dict(sorted(out_of_pool.items())),
              "rows": len(rows)}
    return rows, report


def read_csv(path) -> list[dict]:
    with Path(path).open(encoding="utf-8", newline="") as f:
        return list(csv.DictReader(f))


def write_jsonl(rows, path) -> None:
    with Path(path).open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def _width(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value <= 0:
        raise argparse.ArgumentTypeError(f"{text!r} is not a finite number > 0")
    return value


def print_report(text: str) -> None:
    """Print `text` to stdout and flush it. After a BrokenPipeError, point the stdout file descriptor at
    os.devnull and re-raise: the failed flush leaves the bytes in the stdout buffer, and the interpreter's
    own flush at exit would try them again and fail with two more stderr lines and exit status 120
    (DESIGN 13.11 v1.150; the Python `signal` module docs' note on SIGPIPE)."""
    try:
        print(text, flush=True)
    except BrokenPipeError:
        _stdout_to_devnull()
        raise


def _stdout_to_devnull() -> None:
    """Point the stdout file descriptor at os.devnull; a stdout with none (a stand-in object), or one the
    redirect fails on, is left as it is."""
    try:
        fd = sys.stdout.fileno()
        devnull = os.open(os.devnull, os.O_WRONLY)
    except (AttributeError, OSError, ValueError):  # io.UnsupportedOperation is both of the last two
        return
    try:
        os.dup2(devnull, fd)
    except OSError:
        pass
    finally:
        os.close(devnull)


def main(argv=None) -> int:
    parser = _Parser(prog="convert.py", description="AutoBench Router Benchmark 2026 to an outcome matrix")
    parser.add_argument("--out", required=True, help="output JSONL path")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {default_cache_dir()})")
    parser.add_argument("--width", type=_width, default=None,
                        help="Delta-Hit width (default: delta_signal from frozen_params.json; "
                             "0.3011090610836323 is the dataset's official width)")
    parser.add_argument("--task-by", choices=TASK_BY, default="domain",
                        help="task = the question's domain, or one task for all (default: %(default)s)")
    parser.add_argument("--tokens", action="store_true",
                        help="also write each row's input_tokens and output_tokens")
    parser.add_argument("--registry", default=None,
                        help="also write a models.json registry built from the pool's list prices")
    try:
        args = parser.parse_args(argv)
        if args.registry is not None:
            paths = [p.resolve() for name in (args.out, args.registry)
                     for p in (Path(name), Path(name + ".part"))]
            if len(set(paths)) < len(paths):
                raise _UsageError("--registry and --out (or their .part files) name the same file")
        folder = fetch(args.cache)
        params = json.loads((folder / "frozen_params.json").read_text(encoding="utf-8"))
        if not isinstance(params, dict):
            raise ValueError("frozen_params.json is not an object")
        for key in ("top_k",) + (("delta_signal",) if args.width is None else ()):
            if key not in params:
                raise ValueError(f"frozen_params.json has no {key}")
        width = args.width if args.width is not None else params["delta_signal"]
        pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
        rows, report = convert(read_csv(folder / "matrix.csv"), read_csv(folder / "questions.csv"), pool,
                               width, params["top_k"], args.task_by, args.tokens)
        registry = pool_registry(pool) if args.registry is not None else None
        targets = [Path(args.out)] + ([Path(args.registry)] if registry is not None else [])
        parts = [t.with_name(t.name + ".part") for t in targets]
        try:
            write_jsonl(rows, parts[0])
            if registry is not None:
                parts[1].write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
            # print before the renames, so a write to stdout that fails leaves --out and --registry as they were (v1.94)
            print_report(json.dumps(report, indent=2))
            for part, target in zip(parts, targets):
                part.replace(target)
        finally:
            for part in parts:
                part.unlink(missing_ok=True)
    except (_UsageError, ValueError, OSError, csv.Error) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
