"""Convert the LLMRouterBench results into the evaluator's outcome matrix (DESIGN 12.18).

Usage: python evidence/llmrouterbench/convert.py --out PATH [--cache DIR]

Standard library only. The one pinned file, a gzip tarball of 700 JSON result files, is downloaded
into a cache outside the repo, checked by size and sha256, and read member by member as a stream;
nothing is extracted to disk. Only the 13 models of the performance-cost pool are read. One routing
task per benchmark folder; an item is kept only where every pool model has a scored record and the
digest of its question agrees across them. Nothing is kept but benchmark, index, model, score, cost
and token counts: no question, prompt, prediction, ground truth or raw output text.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import tarfile
import urllib.request
from pathlib import Path

REVISION = "b95870f9e60c589e82f7972c91ffa8de9ca89f85"
LICENCE = "MIT"
FILE = "bench-release.tar.gz"
SIZE = 1283503080
SHA256 = "b79f8cde1a6f029c2efa663a3a3b6f7748defb22341fe59f328cebef6648c8f1"
URL = f"https://huggingface.co/datasets/NPULH/LLMRouterBench/resolve/{REVISION}/{FILE}"
ROOT = "bench-release"
TIMEOUT = 60
# the model folders of the performance-cost pool (the GitHub README's second setting), ascending
POOL = (
    "claude-sonnet-4",
    "deepseek-r1-0528",
    "deepseek-v3-0324",
    "deepseek-v3.1-terminus",
    "gemini-2.5-flash",
    "gemini-2.5-pro",
    "glm-4.6",
    "gpt-5",
    "gpt-5-chat",
    "intern-s1",
    "kimi-k2-0905",
    "qwen3-235b-a22b-2507",
    "qwen3-235b-a22b-thinking-2507",
)
VENDORS = (
    (r"claude-", "anthropic"),
    (r"deepseek-", "deepseek"),
    (r"gemini-", "google"),
    (r"glm-", "z-ai"),
    (r"gpt-", "openai"),
    (r"intern-", "internlm"),
    (r"kimi-", "moonshotai"),
    (r"qwen", "qwen"),
)
SLUG = re.compile(r"[a-z0-9][a-z0-9._-]*")
SCORES = (0, 0.5, 1)


def model_id(folder) -> str:
    """`vendor/model` from a model folder name by the first VENDORS pattern that matches its start."""
    if not isinstance(folder, str) or not folder:
        raise ValueError(f"folder name must be a non-empty string, got {folder!r}")
    if "/" in folder:
        raise ValueError(f"folder name {folder!r} contains '/'")
    if not folder.isascii():
        raise ValueError(f"folder name {folder!r} is not ASCII")
    if not SLUG.fullmatch(folder):
        raise ValueError(f"folder name {folder!r} gives no valid model name")
    for pattern, vendor in VENDORS:
        if re.match(pattern, folder):
            return f"{vendor}/{folder}"
    raise ValueError(f"no vendor rule matches folder {folder!r}")


def member_path(name):
    """(benchmark, split, model folder) of a result file's member name, or None for any other member.
    `bench-release/<benchmark>/<folder>/<file>.json` has split "", and
    `bench-release/<benchmark>/<split>/<folder>/<file>.json` names its split."""
    if not isinstance(name, str):
        return None
    parts = name.split("/")
    if len(parts) not in (4, 5) or parts[0] != ROOT or not parts[-1].endswith(".json"):
        return None
    if any(p in ("", ".", "..") for p in parts) or parts[-1] == ".json":
        return None
    if len(parts) == 4:
        return parts[1], "", parts[2]
    return parts[1], parts[2], parts[3]


def _number(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def query_digest(query) -> str:
    """sha256 of a record's `origin_query` as canonical JSON, so the question itself is never kept."""
    return hashlib.sha256(json.dumps(query, ensure_ascii=False, sort_keys=True).encode("utf-8")).hexdigest()


def extract(doc, benchmark, split, folder) -> dict:
    """One parsed result file reduced to, per record index, its score, cost, token counts and question digest."""
    for label, value in (("benchmark", benchmark), ("split", split)):
        if not isinstance(value, str) or "|" in value or (label == "benchmark" and not value):
            raise ValueError(f"{label} must be a string without '|' (benchmark non-empty), got {value!r}")
    model = model_id(folder)
    where = f"{benchmark}/{split}/{folder}" if split else f"{benchmark}/{folder}"
    if not isinstance(doc, dict) or not isinstance(doc.get("records"), list) or not doc["records"]:
        raise ValueError(f"{where}: the file must be an object with a non-empty records list")
    cells = {}
    for i, rec in enumerate(doc["records"]):
        if not isinstance(rec, dict):
            raise ValueError(f"{where}: record {i} is not an object")
        index = rec.get("index")
        if not _count(index):
            raise ValueError(f"{where}: record {i}: index {index!r} is not an integer >= 0")
        if index in cells:
            raise ValueError(f"{where}: index {index} repeats")
        score = rec.get("score")
        if score is not None and not (_number(score) and score in SCORES):
            raise ValueError(f"{where}: index {index}: score {score!r} is not 0, 0.5, 1 or null")
        cost = rec.get("cost")
        if not (_number(cost) and math.isfinite(cost) and cost >= 0):
            raise ValueError(f"{where}: index {index}: cost {cost!r} is not a finite number >= 0")
        tokens = {}
        for key in ("prompt_tokens", "completion_tokens"):
            value = rec.get(key)
            if not (isinstance(value, int) and not isinstance(value, bool)):
                raise ValueError(f"{where}: index {index}: {key} {value!r} is not an integer")
            tokens[key] = value if value >= 0 else None  # a negative count is written as null (v1.154)
        if "origin_query" not in rec:
            raise ValueError(f"{where}: index {index} has no origin_query")
        cells[index] = {
            "score": None if score is None else float(score),
            "cost_usd": float(cost) + 0.0,
            "input_tokens": tokens["prompt_tokens"],
            "output_tokens": tokens["completion_tokens"],
            "query": query_digest(rec["origin_query"]),
        }
    return {"benchmark": benchmark, "split": split, "model": model, "cells": dict(sorted(cells.items()))}


def convert(extracts, pool=None) -> tuple:
    """Rows, one routing task per benchmark over the pool, sorted by (task, item, model), and a report."""
    pool = [model_id(f) for f in POOL] if pool is None else pool
    if not isinstance(pool, (list, tuple)) or not pool or not all(isinstance(m, str) and m for m in pool) \
            or len(set(pool)) != len(pool):
        raise ValueError("pool must be a non-empty list or tuple of distinct model IDs")
    if not isinstance(extracts, (list, tuple)) or not extracts:
        raise ValueError("extracts must be a non-empty list or tuple")
    models = sorted(pool)
    grid = {}
    for ex in extracts:
        key = (ex["benchmark"], ex["split"], ex["model"])
        if key in grid:
            raise ValueError(f"two files for benchmark {key[0]!r} split {key[1]!r} model {key[2]}")
        grid[key] = ex
    benchmarks = sorted({b for b, _, m in grid if m in pool})
    dropped, lacking, tasks, rows = {}, {}, {}, []
    for bench in benchmarks:
        parent = next((a for a in benchmarks if a != bench and bench.startswith(a + "_")), None)
        if parent is not None:
            dropped[bench] = f"subset of {parent}"
            continue
        splits = sorted({s for b, s, m in grid if b == bench and m in pool})
        full = [s for s in splits if all((bench, s, m) in grid for m in models)]
        if not full:
            dropped[bench] = "no split holds every pool model"
            lacking[bench] = {s: [m for m in models if (bench, s, m) not in grid] for s in splits}
            continue
        if len(full) > 1:
            raise ValueError(f"benchmark {bench!r} has {len(full)} splits that hold every pool model: {full}")
        split = full[0]
        cells = {m: grid[(bench, split, m)]["cells"] for m in models}
        indices = sorted(set().union(*cells.values()))
        counts = {"split": split, "items": 0, "dropped_incomplete": 0, "dropped_unscored": 0,
                  "dropped_question_differs": 0, "half_scores": 0, "null_tokens": 0}
        for index in indices:
            if any(index not in cells[m] for m in models):
                counts["dropped_incomplete"] += 1
            elif any(cells[m][index]["score"] is None for m in models):
                counts["dropped_unscored"] += 1
            elif len({cells[m][index]["query"] for m in models}) > 1:
                counts["dropped_question_differs"] += 1
            else:
                counts["items"] += 1
                for m in models:
                    c = cells[m][index]
                    counts["half_scores"] += c["score"] == 0.5
                    counts["null_tokens"] += c["input_tokens"] is None or c["output_tokens"] is None
                    rows.append({"task": bench, "item": f"{bench}|{index}", "model": m, "correct": c["score"] == 1.0,
                                 "cost_usd": c["cost_usd"], "input_tokens": c["input_tokens"],
                                 "output_tokens": c["output_tokens"]})
        tasks[bench] = counts
    if not rows:
        raise ValueError("no benchmark keeps an item for every pool model")
    rows.sort(key=lambda r: (r["task"], r["item"], r["model"]))
    report = {"models": models, "tasks": tasks, "dropped_benchmarks": dropped, "lacking": lacking, "rows": len(rows)}
    return rows, report


def read_archive(path, folders=POOL) -> list:
    """Extracts of the archive's result files whose model folder is in `folders`, in member order; the
    stream is read once and nothing is written to disk. Other members are never parsed."""
    path = Path(path)
    out = []
    try:
        with tarfile.open(path, mode="r|gz") as tar:
            for member in tar:
                key = member_path(member.name) if member.isfile() else None
                if key is None or key[2] not in folders:
                    continue
                raw = tar.extractfile(member).read()
                try:
                    doc = json.loads(raw.decode("utf-8"))
                except (ValueError, RecursionError) as exc:
                    raise ValueError(f"{member.name}: not valid UTF-8 JSON ({type(exc).__name__}: {exc})") from exc
                out.append(extract(doc, *key))
    except (tarfile.TarError, EOFError, OSError) as exc:
        raise ValueError(f"{path.name}: not a readable gzip tarball ({type(exc).__name__}: {exc})") from exc
    return out


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "llmrouterbench"


def verify(path, size: int, sha256: str) -> None:
    path = Path(path)
    if path.stat().st_size != size:
        raise ValueError(f"{path.name}: size {path.stat().st_size}, expected {size}")
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != sha256:
        raise ValueError(f"{path.name}: sha256 {digest.hexdigest()}, expected {sha256}")


def fetch(cache_dir=None) -> Path:
    """Return the path of the pinned file once it is in the cache and verified."""
    root = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    dest = root / FILE
    if dest.exists():
        verify(dest, SIZE, SHA256)
        return dest
    part = dest.with_name(dest.name + ".part")
    try:
        try:
            with urllib.request.urlopen(URL, timeout=TIMEOUT) as resp, open(part, "wb") as out:
                for block in iter(lambda: resp.read(1 << 20), b""):
                    out.write(block)
        except ValueError:
            raise
        except Exception as exc:
            raise OSError(f"{FILE}: download failed: {exc}") from exc
        verify(part, SIZE, SHA256)
        part.replace(dest)
    finally:
        if part.exists():
            part.unlink()
    return dest


def write_jsonl(rows, path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def print_report(text: str) -> None:
    """Print `text` to stdout and flush it; after a BrokenPipeError, point the stdout file descriptor at
    os.devnull and re-raise, as the other evidence CLIs do (DESIGN 13.11 v1.150)."""
    try:
        print(text, flush=True)
    except BrokenPipeError:
        _stdout_to_devnull()
        raise


def _stdout_to_devnull() -> None:
    try:
        fd = sys.stdout.fileno()
        devnull = os.open(os.devnull, os.O_WRONLY)
    except (AttributeError, OSError, ValueError):
        return
    try:
        os.dup2(devnull, fd)
    except OSError:
        pass
    finally:
        os.close(devnull)


def _check_out(value, option="--out"):
    """The path an output option names, or a ValueError for a bad one, checked before any download (12.14 v1.174)."""
    if value.rsplit("/", 1)[-1] in ("", ".", ".."):
        raise ValueError(f"{option} must end in a file name, got {value!r}")
    out = Path(value)
    for path in (out, out.with_name(out.name + ".part")):
        if path.is_dir():  # a link to a folder included
            raise ValueError(f"{option} {value!r}: {str(path)!r} is a folder")
    if not out.parent.is_dir():
        raise ValueError(f"{option} {value!r}: folder {str(out.parent)!r} does not exist")
    return out


def main(argv=None) -> int:
    parser = _Parser(prog="convert.py", description="LLMRouterBench results to an outcome matrix")
    parser.add_argument("--out", required=True, help="output JSONL path")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {default_cache_dir()})")
    try:
        args = parser.parse_args(argv)
        out = _check_out(args.out)
        part = out.with_name(out.name + ".part")
        try:
            rows, report = convert(read_archive(fetch(args.cache)))
            write_jsonl(rows, part)
            print_report(json.dumps(report, indent=2))
            part.replace(out)
        finally:
            part.unlink(missing_ok=True)
    except (ValueError, OSError) as exc:
        msg = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {msg}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
