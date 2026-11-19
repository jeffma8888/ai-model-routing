"""Convert nebius/Longtail-SWE-trajectories into the evaluator's outcome matrix (DESIGN 12.25).

Usage: python evidence/longtail-swe/convert.py --out PATH [--cache DIR] [--run N]

Standard library only but for the parquet reader `pyarrow` (the `evidence` extra), which only
`read_rows` imports, when called. The four pinned parquet files of the release's registry models are
downloaded into a cache outside the repo and checked by size and sha256. Of each run only its task,
language, model, run index, `resolved`, statement flag and the `usage.tokens` record of its trajectory
are kept, and each run is priced from its tokens at the registry's list prices, an estimate and not a
bill: no prompt, message, tool call or patch is kept. One routing task, `issue_resolution`; an item is
a task at one run index (run 0 by default), and a task whose statement changed for any model is
dropped for every model.
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

DATASET = "nebius/Longtail-SWE-trajectories"
REVISION = "dfd6075c56b7841b9c254cc70a57e39c1df0076c"
LICENCE = "cc-by-4.0"
FILES = {
    "data/swelike__claude-opus-5.5-high.parquet": (36213846, "45b9323ae1b33c7301e60a266594202e6f6684de4386c9d50356783b113bea91"),
    "data/swelike__gpt-5.6-luna-xhigh.parquet": (94695456, "144ac5b635135d0df37eae6edf2d40148e58f8832d8d59b492a865a98dd99093"),
    "data/swelike__gpt-5.6-sol-high.parquet": (56147793, "af2e3bcaf8625d131d467cb4a55164fd63f561d7ee6125db6217cfe603511b57"),
    "data/swelike__gpt-6.1-sol-high.parquet": (49548306, "52441cc627aa6688150be052044549b0fe6b2e1215f676a254602919f4bc2fff"),
}
COLUMNS = ("instance_id", "programming_language", "canonical_model", "run_index", "resolved",
           "initial_statement_matches_release", "trajectory")
TASK = "issue_resolution"
VENDORS = (("anthropic", re.compile(r"claude-[a-z0-9.-]+")), ("openai", re.compile(r"gpt-[a-z0-9.-]+")))
REGISTRY = Path(__file__).resolve().parents[2] / "model_routing" / "data" / "models.json"
TIMEOUT = 60
ATTEMPTS = 3  # tries per missing file, at once (DESIGN.md 12.13 v1.406)


def url(name) -> str:
    """The download URL of a pinned file at REVISION; a ValueError for a name not in FILES."""
    if name not in FILES:
        raise ValueError(f"not a pinned file: {name!r}")
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{name}"


def model_id(canonical) -> str:
    """The provider-neutral ID of a canonical model name, by a regex over the name, never a vendor list."""
    if isinstance(canonical, str):
        for vendor, rx in VENDORS:
            if rx.fullmatch(canonical):
                return f"{vendor}/{canonical}"
    raise ValueError(f"model name {canonical!r} is not a claude- or gpt- name")


def _count(value):
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def tokens(trajectory) -> tuple:
    """`(input, output)` of the `usage.tokens` record of one run's trajectory, a JSON string; nothing else
    of the trajectory is kept. A ValueError opens with its case (12.25)."""
    if not isinstance(trajectory, str):
        raise ValueError("trajectory is not a string")
    try:
        data = json.loads(trajectory)
    except (json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"trajectory is not JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError("trajectory is not an object")
    usage = data.get("usage")
    tok = usage.get("tokens") if isinstance(usage, dict) else None
    if not isinstance(tok, dict):
        raise ValueError("no tokens in the trajectory's usage")
    for key in ("input", "output", "total"):
        if not _count(tok.get(key)):
            raise ValueError(f"token count {key} {tok.get(key)!r} is not an int >= 0")
    if tok["total"] != tok["input"] + tok["output"]:
        raise ValueError(f"token total {tok['total']} is not input + output")
    cached = 0
    for key in ("cached_input", "cache_creation"):
        value = tok.get(key)
        if value is not None and not _count(value):
            raise ValueError(f"cached tokens {key} {value!r} is neither null nor an int >= 0")
        cached += value or 0
    if cached > tok["input"]:
        raise ValueError(f"cached tokens {cached} above input {tok['input']}")
    return (tok["input"], tok["output"])


def _price(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value) and value >= 0


def run_records(rows, registry) -> list:
    """One record per row of one file, in row order, priced at the model's registry row; a ValueError
    opens `row <n>` (0-based, within the file) and then its case (12.25)."""
    models = registry.get("models") if isinstance(registry, dict) else None
    by_id = {m.get("id"): m for m in models if isinstance(m, dict)} if isinstance(models, list) else {}
    out = []
    for n, row in enumerate(rows):
        try:
            if not isinstance(row, dict):
                raise ValueError("not an object")
            for key in ("instance_id", "programming_language"):
                if not isinstance(row.get(key), str) or not row.get(key):
                    raise ValueError(f"{key} must be a non-empty string")
            if not _count(row.get("run_index")):
                raise ValueError(f"run_index {row.get('run_index')!r} is not an int >= 0")
            res = row.get("resolved")
            if res is not None and (type(res) is not int or res not in (0, 1)):
                raise ValueError(f"resolved {res!r} is not 0, 1 or null")
            if not isinstance(row.get("initial_statement_matches_release"), bool):
                raise ValueError("initial_statement_matches_release is not a bool")
            mid = model_id(row.get("canonical_model"))
            if mid not in by_id:
                raise ValueError(f"model not in the registry: {mid}")
            entry = by_id[mid]
            if "price_tiers" in entry:
                raise ValueError(f"price tiers on {mid}")
            if not (_price(entry.get("price_in")) and _price(entry.get("price_out"))):
                raise ValueError(f"registry price of {mid} is not a finite number >= 0")
            tin, tout = tokens(row.get("trajectory"))
        except ValueError as exc:
            raise ValueError(f"row {n}: {exc}") from None
        out.append({"task": TASK, "item": row["instance_id"], "language": row["programming_language"],
                    "run": row["run_index"], "model": mid, "correct": res == 1, "scored": res is not None,
                    "statement_matches": row["initial_statement_matches_release"],
                    "cost_usd": (tin * entry["price_in"] + tout * entry["price_out"]) / 1_000_000})
    return out


def convert(records, run=0) -> tuple:
    """The rows (one per kept item and model, sorted) and the report, from the records of all files at
    `run`; an item whose statement changed for any model is dropped for every model, and an unscored run
    is a miss that keeps its charge (12.25)."""
    if not isinstance(records, (list, tuple)) or not records:
        raise ValueError("records must be a non-empty list or tuple")
    if type(run) is not int or run < 0:
        raise ValueError("run must be an int >= 0")
    seen, lang = set(), {}
    for r in records:
        key = (r["item"], r["model"], r["run"])
        if key in seen:
            raise ValueError(f"repeated run: {key}")
        seen.add(key)
        if lang.setdefault(r["item"], r["language"]) != r["language"]:
            raise ValueError(f"item language differs: {r['item']}")
    models = sorted({r["model"] for r in records})
    at = {(r["item"], r["model"]): r for r in records if r["run"] == run}
    items = sorted({r["item"] for r in records})
    for item in items:
        for m in models:
            if (item, m) not in at:
                raise ValueError(f"incomplete item {item}: no record of {m} at run {run}")
    dropped = sorted({item for (item, _), r in at.items() if not r["statement_matches"]})
    kept = [i for i in items if i not in set(dropped)]
    if not kept:
        raise ValueError("no items: every item dropped for a changed statement")
    rows = [{"task": TASK, "item": i, "model": m, "correct": at[(i, m)]["correct"], "cost_usd": at[(i, m)]["cost_usd"]}
            for i in kept for m in models]
    languages = {}
    for i in kept:
        languages[lang[i]] = languages.get(lang[i], 0) + 1
    report = {"models": models, "run": run, "tasks": {TASK: {"items": len(kept)}},
              "languages": dict(sorted(languages.items())), "dropped_statement": dropped,
              "resolved": {m: sum(at[(i, m)]["correct"] for i in kept) for m in models},
              "unscored": {m: [i for i in kept if not at[(i, m)]["scored"]] for m in models}, "rows": len(rows)}
    return rows, report


def read_rows(path) -> list:
    """The COLUMNS of every row of one parquet file, as dicts; pyarrow is imported here alone."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        raise ValueError("reading parquet needs pyarrow: pip install -e '.[evidence]'") from None
    name = Path(path).name
    try:
        pf = pq.ParquetFile(path)
        names = pf.schema_arrow.names
    except Exception as exc:
        raise ValueError(f"{name}: cannot read: {exc}") from None
    missing = [c for c in COLUMNS if c not in names]
    if missing:
        raise ValueError(f"{name}: lacks the columns {missing}")
    out = []
    try:
        for batch in pf.iter_batches(columns=list(COLUMNS)):
            out += batch.to_pylist()
    except Exception as exc:
        raise ValueError(f"{name}: cannot read: {exc}") from None
    return out


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "longtail-swe"


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
    out = {}
    for name in sorted(FILES):
        size, sha256 = FILES[name]
        dest = root / name
        if dest.exists():
            verify(dest, size, sha256)
            out[name] = dest
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        try:
            for attempt in range(1, ATTEMPTS + 1):
                try:
                    with urllib.request.urlopen(url(name), timeout=TIMEOUT) as resp, open(part, "wb") as f:
                        for block in iter(lambda: resp.read(1 << 20), b""):
                            f.write(block)
                    break
                except ValueError:
                    raise
                except Exception as exc:
                    if attempt == ATTEMPTS:
                        raise OSError(f"{name}: download failed: {exc}") from exc
            verify(part, size, sha256)
            part.replace(dest)
        finally:
            if part.exists():
                part.unlink()
        out[name] = dest
    return out


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
    parser = _Parser(prog="convert.py", description="nebius/Longtail-SWE-trajectories to an outcome matrix")
    parser.add_argument("--out", required=True, help="output JSONL path")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {default_cache_dir()})")
    parser.add_argument("--run", default="0", help="the run_index read (default 0)")
    try:
        args = parser.parse_args(argv)
        out = _check_out(args.out)
        if not re.fullmatch(r"[0-9]+", args.run):
            raise ValueError(f"--run must be decimal digits only, got {args.run!r}")
        run = int(args.run)
        part = out.with_name(out.name + ".part")
        try:
            paths = fetch(args.cache)
            registry = json.loads(REGISTRY.read_text(encoding="utf-8"))
            recs = []
            for name in FILES:
                file_rows = read_rows(paths[name])
                try:
                    recs += run_records(file_rows, registry)
                except ValueError as exc:  # the file, then the row within it (v1.479)
                    raise ValueError(f"{name}: {exc}") from None
            rows, report = convert(recs, run)
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
