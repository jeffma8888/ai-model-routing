"""Lurume/llm-routing-response-bank to an outcome matrix (DESIGN 12.20, v1.288 and v1.289).

Standard library only; the package never imports this script. It reads the two scores files and the two
responses files of one pinned revision, keeps only each response's key, finish reason, billed cost and
token counts (never its text or reasoning), and writes one 12.1 row per (task, item, model). The data's
terms are ODC-BY-4.0 with attribution to the dataset repository, as its LICENSE grants them at REVISION.
"""

import argparse
import hashlib
import json
import math
import os
import re
import sys
import urllib.request
from pathlib import Path

DATASET = "Lurume/llm-routing-response-bank"
REVISION = "547beb31ecd8f12b116b87eb4f56feee73edda6c"
LICENCE = "ODC-BY-4.0"
FILES = {
    "responses_cal.jsonl": (62806440, "31262ff3c39cf66c17332bdc3f104bdf25c4abedd8dc75767297fa67c2a08de5"),
    "responses_eval.jsonl": (942083749, "c0b9df2c194730cd24757001878a1e24648b4990747d60157261b60818e42305"),
    "scores_cal.jsonl": (349266, "58826526608edd7ffaa16540fb0393ef631ee428cb708da92dae32d690a995cd"),
    "scores_eval.jsonl": (12952125, "09b7376e7964a85aee77644af64188b8b14156fab6201e6f3e80852ea6e42b4b"),
}
MODELS = ("deepseek-v4-flash", "deepseek-v4-pro", "glm-5-3-flash", "glm-5.3", "kimi-k2.7-code")
VENDORS = (("deepseek-", "deepseek"), ("glm-", "z-ai"), ("kimi-", "moonshotai"))
TIMEOUT = 60
_ID = re.compile(r"[a-z0-9][a-z0-9._-]*")
_GLM_VERSION = re.compile(r"^glm-(\d+)-(\d+)(?=-|$)")
_SHA256 = re.compile(r"[0-9a-f]{64}")


def url(name) -> str:
    """The download URL of one pinned file at REVISION; a ValueError for any other name."""
    if name not in FILES:
        raise ValueError(f"not a pinned file: {name!r}")
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{name}"


def model_id(raw) -> str:
    """The provider-neutral ID of a raw model ID, by the VENDORS prefix rule; a ValueError, never a guess."""
    if not isinstance(raw, str) or not raw.isascii() or not _ID.fullmatch(raw):
        raise ValueError(f"not a model ID: {raw!r}")
    for prefix, vendor in VENDORS:
        if raw.startswith(prefix):
            return vendor + "/" + _GLM_VERSION.sub(r"glm-\1.\2", raw)
    raise ValueError(f"no vendor for model ID {raw!r}")


def _key(obj):
    if not isinstance(obj, dict):
        raise ValueError(f"not an object: {type(obj).__name__}")
    task_id, family = obj.get("task_id"), obj.get("dataset")
    if not isinstance(family, str) or not family or ":" in family or "|" in family:
        raise ValueError(f"bad dataset {family!r}")
    if not isinstance(task_id, str) or not task_id.startswith(family + ":") or task_id == family + ":":
        raise ValueError(f"task_id {task_id!r} is not in dataset {family!r}")
    return task_id, family, model_id(obj.get("model_id"))


def _count(value, name):
    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
        raise ValueError(f"bad {name} {value!r}")
    return value


def score_record(obj) -> dict:
    task_id, family, model = _key(obj)
    quality = obj.get("quality")
    if isinstance(quality, bool) or not isinstance(quality, (int, float)) or quality not in (0, 1):
        raise ValueError(f"{task_id} {model}: quality {quality!r} is not 0 or 1")
    evaluator = obj.get("evaluator")
    if not isinstance(evaluator, dict):
        raise ValueError(f"{task_id} {model}: evaluator is not an object")
    missing = None
    if "missing" in evaluator:  # present: a non-empty string, never null (v1.289)
        missing = evaluator["missing"]
        if not isinstance(missing, str) or not missing:
            raise ValueError(f"{task_id} {model}: bad missing {missing!r}")
        if quality == 1:
            raise ValueError(f"{task_id} {model}: a missing cell scored 1")
    return {"task_id": task_id, "family": family, "model": model, "correct": quality == 1, "missing": missing}


def response_record(obj) -> dict:
    task_id, family, model = _key(obj)
    sample = _count(obj.get("sample_index"), "sample_index")
    digest = obj.get("prompt_sha256")
    if not isinstance(digest, str) or not _SHA256.fullmatch(digest):
        raise ValueError(f"{task_id} {model}: bad prompt_sha256")
    finish = obj.get("finish_reason")
    if finish is not None and not isinstance(finish, str):
        raise ValueError(f"{task_id} {model}: bad finish_reason {finish!r}")
    usd = obj.get("official_usd")
    if isinstance(usd, bool) or not isinstance(usd, (int, float)):
        raise ValueError(f"{task_id} {model}: bad official_usd {usd!r}")
    try:
        usd = float(usd)
    except OverflowError:  # an int too large for a float (v1.289)
        raise ValueError(f"{task_id} {model}: official_usd too large for a float") from None
    if not math.isfinite(usd) or usd < 0:
        raise ValueError(f"{task_id} {model}: bad official_usd {usd!r}")
    usage = obj.get("usage")
    if not isinstance(usage, dict):
        raise ValueError(f"{task_id} {model}: usage is not an object")
    return {
        "task_id": task_id,
        "family": family,
        "model": model,
        "sample_index": sample,
        "prompt_sha256": digest,
        "finish_reason": finish,
        "cost_usd": usd + 0.0,  # a negative zero written 0.0
        "input_tokens": _count(usage.get("input"), "usage input"),
        "output_tokens": _count(usage.get("output"), "usage output"),
    }


def read_jsonl(path, parse) -> list:
    """`parse` of each non-blank line of a JSONL file, read in binary one line at a time; a ValueError names
    `<file name>:<line>` (1-based)."""
    path = Path(path)
    out = []
    with open(path, "rb") as f:
        for number, raw in enumerate(f, 1):
            try:
                line = raw.decode("utf-8")
                if not line.strip():
                    continue
                out.append(parse(json.loads(line)))
            except (ValueError, RecursionError) as exc:
                raise ValueError(f"{path.name}:{number}: {exc}") from exc
    return out


def _records(value, name):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{name} must be a non-empty list or tuple")
    return value


def convert(scores, responses) -> tuple:
    """The 12.1 rows and the report for parsed scores and responses (12.20); the input is not modified."""
    scores = _records(scores, "scores")
    responses = _records(responses, "responses")
    cells, families = {}, {}
    for s in scores:
        key = (s["task_id"], s["model"])
        if key in cells:
            raise ValueError(f"repeated score for {key[0]} {key[1]}")
        cells[key] = s
        families[s["task_id"]] = s["family"]
    models = sorted({s["model"] for s in scores})
    bills, ignored, seen = {}, 0, set()
    for r in responses:
        key = (r["task_id"], r["model"], r["sample_index"])
        if key in seen:
            raise ValueError(f"repeated response for {key[0]} {key[1]} sample {key[2]}")
        seen.add(key)
        if (r["task_id"], r["model"]) not in cells:
            raise ValueError(f"response without a score: {r['task_id']} {r['model']}")
        if r["sample_index"] != 0:
            ignored += 1
            continue
        bills[(r["task_id"], r["model"])] = r
    tasks = {}
    rows = []
    for task_id in sorted(families):
        family = families[task_id]
        t = tasks.setdefault(family, {"items": 0, "dropped_incomplete": 0, "dropped_unbilled": 0,
                                      "dropped_prompt_differs": 0, "missing_cells": 0, "length_finishes": 0,
                                      "length_successes": 0, "other_finishes": 0})
        if any((task_id, m) not in cells for m in models):
            t["dropped_incomplete"] += 1
            continue
        if any((task_id, m) not in bills and cells[(task_id, m)]["missing"] is None for m in models):
            t["dropped_unbilled"] += 1
            continue
        if len({bills[(task_id, m)]["prompt_sha256"] for m in models if (task_id, m) in bills}) > 1:
            t["dropped_prompt_differs"] += 1
            continue
        t["items"] += 1
        for m in models:
            s, b = cells[(task_id, m)], bills.get((task_id, m))
            if s["missing"] is not None:
                t["missing_cells"] += 1
            if b is not None:
                if b["finish_reason"] == "length":
                    t["length_finishes"] += 1
                    t["length_successes"] += s["correct"]
                elif b["finish_reason"] != "stop":
                    t["other_finishes"] += 1
            rows.append({
                "task": family,
                "item": task_id,
                "model": m,
                "correct": s["correct"],
                "cost_usd": b["cost_usd"] if b else 0.0,
                "input_tokens": b["input_tokens"] if b else None,
                "output_tokens": b["output_tokens"] if b else None,
            })
    if not rows:
        raise ValueError("no row kept")
    rows.sort(key=lambda r: (r["task"], r["item"], r["model"]))
    report = {"models": models, "tasks": {f: tasks[f] for f in sorted(tasks)}, "ignored_samples": ignored,
              "rows": len(rows)}
    return rows, report


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "response-bank"


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


def fetch(cache_dir=None) -> dict:
    """Each pinned file's path, in FILES order, once it is in the cache and verified."""
    root = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    out = {}
    for name in sorted(FILES):
        size, sha256 = FILES[name]
        dest = root / name
        if dest.exists():
            verify(dest, size, sha256)
            out[name] = dest
            continue
        part = dest.with_name(name + ".part")
        try:
            try:
                with urllib.request.urlopen(url(name), timeout=TIMEOUT) as resp, open(part, "wb") as f:
                    for block in iter(lambda: resp.read(1 << 20), b""):
                        f.write(block)
            except ValueError:
                raise
            except Exception as exc:
                raise OSError(f"{name}: download failed: {exc}") from exc
            verify(part, size, sha256)
            part.replace(dest)
        finally:
            if part.exists():
                part.unlink()
        out[name] = dest
    return out


def _read_all(paths) -> tuple:
    """The scores, then the responses, calibration before evaluation, each file read by `read_jsonl`."""
    scores = read_jsonl(paths["scores_cal.jsonl"], score_record) + read_jsonl(paths["scores_eval.jsonl"], score_record)
    responses = read_jsonl(paths["responses_cal.jsonl"], response_record) + read_jsonl(
        paths["responses_eval.jsonl"], response_record)
    return scores, responses


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
        if path.is_dir():
            raise ValueError(f"{option} {value!r}: {str(path)!r} is a folder")
    if not out.parent.is_dir():
        raise ValueError(f"{option} {value!r}: folder {str(out.parent)!r} does not exist")
    return out


def main(argv=None) -> int:
    parser = _Parser(prog="convert.py", description="LLM Routing Response Bank to an outcome matrix")
    parser.add_argument("--out", required=True, help="output JSONL path")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {default_cache_dir()})")
    try:
        args = parser.parse_args(argv)
        out = _check_out(args.out)
        part = out.with_name(out.name + ".part")
        try:
            rows, report = convert(*_read_all(fetch(args.cache)))
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
