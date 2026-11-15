"""Measured hand-off paths: the ledger runs of the Attention Tax, Handoff Tax release (DESIGN 13.15).

Usage: python evidence/ledger-handoff/results.py --out PATH [--cache DIR]

Standard library only. Six files of the public GitHub repository at a pinned commit, the three ledger
run files and their three run settings, are downloaded into a cache outside the repo, each checked by
size and by the sha256 the repository's SHA256SUMS lists for it before it is read. One model makes
every call. ``single`` runs each item in one context; ``decomposed``, the chain here, runs every five
steps in a fresh context that starts from a note the previous context wrote, so a successor takes
over and no parent reads a result back. That is a surrogate for the DESIGN 13 hand-off, so the paths
are reported as measured, never priced and never set beside a delegation decision (13.15).
"""

import argparse
import hashlib
import json
import os
import statistics
import sys
import urllib.request
from pathlib import Path

REVISION = "d891b4eb92abf039431be850646830b486f9e5af"
REPO_URL = "https://github.com/akshitanchan/attention-handoff-tax"
BASE_URL = f"https://raw.githubusercontent.com/akshitanchan/attention-handoff-tax/{REVISION}/"
LICENCE = "CC BY 4.0 (data and config), MIT (code)"
MODEL = "openai/gpt-oss-20b"
TIMEOUT = 60
MAX_COUNT = 2**63 - 1  # the largest signed 64-bit integer
# repository path: (bytes, sha256), each sha256 the one SHA256SUMS lists at REVISION, in path order
FILES = {
    "config/ledger/config_decomposed.json": (427, "910f1b73f19c5027d70f5d2082c222ee2b625b2a6bfdbf8dd322de4f58219dca"),
    "config/ledger/config_handoff.json": (424, "bb57bd79b2488e938719b917db888c5bdac5bf6d8597d5e0a084e17b266a4d90"),
    "config/ledger/config_single.json": (423, "7829ba29b1f8396d328d61d8d1ec44abcd74832d67048e439c79cd41af644418"),
    "data/ledger/decomposed.jsonl": (6227860, "3f88ba82edea7da4a78e06b7859ee49e8da8d2f2ff1a99e2ac2a09332819f39a"),
    "data/ledger/handoff.jsonl": (1005220, "b146c4adc0a21b1ca4658a6a6b65d1d5840357a5db0b224570389203bb1f9cc9"),
    "data/ledger/single.jsonl": (4187684, "f7554b7be15e8706b923852202552369d633f02ab536a7644c473ffb5e2c7d4b"),
}
# each run file's config by its `command` value
CONFIGS = {"single": "config_single.json", "decomposed": "config_decomposed.json", "handoff": "config_handoff.json"}
ARMS = ("history", "note_100", "note_300", "note_900")
NOTE_BUDGETS = {"note_100": 100, "note_300": 300, "note_900": 900}
FLAGS = ("inc_ok", "abs_ok")


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "ledger-handoff"


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
    """Return the cache folder once every file in FILES is in it, under its base name, and verified."""
    root = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    for path, (size, sha256) in FILES.items():
        dest = root / Path(path).name
        if dest.exists():
            verify(dest, size, sha256)  # a present file that fails is kept and refused
            continue
        part = dest.with_name(dest.name + ".part")
        try:
            try:
                with urllib.request.urlopen(BASE_URL + path, timeout=TIMEOUT) as resp, open(part, "wb") as out:
                    for block in iter(lambda: resp.read(1 << 20), b""):
                        out.write(block)
            except Exception as exc:  # a ValueError from urlopen included: every download error names its path
                raise OSError(f"{path}: download failed: {exc}") from exc
            verify(part, size, sha256)
            part.replace(dest)
        finally:
            if part.exists():
                part.unlink()
    return root


def _kind(value) -> str:
    """A short description of a refused value that never converts a long int to a string."""
    if isinstance(value, str):
        return repr(value) if len(value) <= 40 else f"a string of {len(value)} characters"
    return type(value).__name__


def _int(obj: dict, key: str, where: str, low=None) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool):
        raise ValueError(f"{where}: {key} is not an int ({_kind(value)})")
    if low is not None and not low <= value <= MAX_COUNT:
        raise ValueError(f"{where}: {key} is outside {low} to 2**63 - 1")
    return value


def _flag(obj: dict, key: str, where: str) -> int:
    value = obj.get(key)
    if not isinstance(value, int) or isinstance(value, bool) or value not in (0, 1):
        raise ValueError(f"{where}: {key} is not 0 or 1 ({_kind(value)})")
    return value


def _calls(obj: dict, key: str, where: str, flags=(), empty=False) -> list:
    """The list obj[key] of call records, each with prompt and completion counts and the named flags."""
    calls = obj.get(key)
    if not isinstance(calls, list) or (not calls and not empty):
        raise ValueError(f"{where}: {key} is not a {'' if empty else 'non-empty '}list")
    for i, call in enumerate(calls):
        at = f"{where}: {key}[{i}]"
        if not isinstance(call, dict):
            raise ValueError(f"{at} is not a JSON object")
        _int(call, "prompt_tokens", at, 0)
        _int(call, "completion_tokens", at, 0)
        for flag in flags:
            _flag(call, flag, at)
    return calls


def read_json(path) -> dict:
    """One UTF-8 JSON object; anything else is a ValueError naming the file."""
    name = Path(path).name
    try:
        with open(path, "rb") as f:
            obj = json.loads(f.read().decode("utf-8"))
    except (ValueError, RecursionError) as exc:
        raise ValueError(f"{name}: not valid UTF-8 JSON ({type(exc).__name__}: {exc})") from exc
    if not isinstance(obj, dict):
        raise ValueError(f"{name}: not a JSON object")
    return obj


def read_lines(path) -> list:
    """(line number, JSON object) for each non-blank line of a UTF-8 JSON Lines file, read line by line."""
    name = Path(path).name
    rows = []
    with open(path, "rb") as f:
        for number, raw in enumerate(f, 1):
            try:
                text = raw.decode("utf-8")
                if not text.strip():
                    continue
                obj = json.loads(text)
            except (ValueError, RecursionError) as exc:
                raise ValueError(f"{name}:{number}: not valid UTF-8 JSON ({type(exc).__name__}: {exc})") from exc
            if not isinstance(obj, dict):
                raise ValueError(f"{name}:{number}: not a JSON object")
            rows.append((number, obj))
    if not rows:
        raise ValueError(f"{name}: no record")
    return rows


def check_config(obj: dict, name: str, command: str) -> None:
    """A run settings file names its run by `command` and the one model by `model`."""
    if obj.get("command") != command:
        raise ValueError(f"{name}: command is {_kind(obj.get('command'))}, expected {command!r}")
    if obj.get("model") != MODEL:
        raise ValueError(f"{name}: model is {_kind(obj.get('model'))}, expected {MODEL!r}")


def ledger(rows: list, name: str, notes: bool) -> dict:
    """Map each (depth, item) key of single.jsonl, or of decomposed.jsonl with notes, to its checked record."""
    found = {}
    for number, obj in rows:
        where = f"{name}:{number}"
        key = (_int(obj, "L", where, 1), _int(obj, "item", where, 0))
        _flag(obj, "final_ok", where)
        _calls(obj, "steps", where)
        if notes:
            for i, note in enumerate(_calls(obj, "notes", where, empty=True)):
                _int(note, "note_tokens", f"{where}: notes[{i}]", 0)
        if key in found:
            raise ValueError(f"{where}: (L, item) {key} repeats")
        found[key] = obj
    return found


def _median(values) -> float:
    return float(statistics.median(list(values)))


def _sum(calls, key: str) -> int:
    return sum(call[key] for call in calls)


def depths(single: dict, chain: dict) -> list:
    """Per depth, ascending: items, final_ok per path, the chain's paired losses and gains, median tokens."""
    if set(single) != set(chain):
        first = min(set(single) ^ set(chain))
        raise ValueError(f"single.jsonl and decomposed.jsonl hold different (L, item) keys, the first {first}")
    found = []
    for depth in sorted({key[0] for key in single}):
        keys = sorted(key for key in single if key[0] == depth)
        one, two = [single[k] for k in keys], [chain[k] for k in keys]
        chain_calls = [r["steps"] + r["notes"] for r in two]  # the note calls count on the chain path
        notes = [note for r in two for note in r["notes"]]
        found.append({
            "depth": depth,
            "items": len(keys),
            "final_ok": {"single": sum(r["final_ok"] for r in one), "chain": sum(r["final_ok"] for r in two)},
            "chain_lost": sum(a["final_ok"] > b["final_ok"] for a, b in zip(one, two)),
            "chain_gained": sum(a["final_ok"] < b["final_ok"] for a, b in zip(one, two)),
            "median_prompt_tokens": {"single": _median(_sum(r["steps"], "prompt_tokens") for r in one),
                                     "chain": _median(_sum(c, "prompt_tokens") for c in chain_calls)},
            "median_completion_tokens": {"single": _median(_sum(r["steps"], "completion_tokens") for r in one),
                                         "chain": _median(_sum(c, "completion_tokens") for c in chain_calls)},
            "median_notes": _median(len(r["notes"]) for r in two),
            "median_note_tokens": _median(n["note_tokens"] for n in notes) if notes else None,
        })
    return found


def probe(rows: list, name: str) -> dict:
    """The hand-off probe: per arm, the items whose continued steps all hold each flag, and paired counts."""
    items, seen, pre_steps, steps = [], set(), set(), set()
    for number, obj in rows:
        where = f"{name}:{number}"
        item = _int(obj, "item", where, 0)
        if item in seen:
            raise ValueError(f"{where}: item {item} repeats")
        seen.add(item)
        pre = _calls(obj, "pre", where)
        _int(pre[-1], "balance", f"{where}: pre[{len(pre) - 1}]")
        pre_steps.add(len(pre))
        arms = obj.get("conditions")
        if not isinstance(arms, dict) or set(arms) != set(ARMS):
            raise ValueError(f"{where}: conditions is not a JSON object with exactly the arms {', '.join(ARMS)}")
        for arm in ARMS:
            at = f"{where}: {arm}"
            if not isinstance(arms[arm], dict):
                raise ValueError(f"{at} is not a JSON object")
            steps.add(len(_calls(arms[arm], "steps", at, FLAGS)))
            if arm in NOTE_BUDGETS:
                if _int(arms[arm], "s", at) != NOTE_BUDGETS[arm]:
                    raise ValueError(f"{at}: s is not {NOTE_BUDGETS[arm]}")
                _int(arms[arm], "note_tokens", at, 0)
                _int(arms[arm], "note_prompt_tokens", at, 0)
                _int(arms[arm], "note_balance", at)
        items.append(obj)
    for label, counts in (("pre", pre_steps), ("continued steps", steps)):
        if len(counts) != 1:
            raise ValueError(f"{name}: the items hold {label} lists of different lengths {sorted(counts)}")

    def kept(arm_obj, flag):
        return all(step[flag] for step in arm_obj["steps"])

    history = [obj["conditions"]["history"] for obj in items]
    arms = []
    for arm in ARMS:
        run = [obj["conditions"][arm] for obj in items]
        row = {"arm": arm}
        if arm in NOTE_BUDGETS:
            row["note_budget"] = NOTE_BUDGETS[arm]
        for flag in FLAGS:
            row[f"all_{flag}"] = sum(kept(y, flag) for y in run)
        if arm in NOTE_BUDGETS:
            for flag in FLAGS:
                row[f"{flag}_lost"] = sum(kept(h, flag) and not kept(y, flag) for h, y in zip(history, run))
                row[f"{flag}_gained"] = sum(not kept(h, flag) and kept(y, flag) for h, y in zip(history, run))
            row["note_balance_kept"] = sum(o["conditions"][arm]["note_balance"] == o["pre"][-1]["balance"] for o in items)
        row["median_prompt_tokens"] = _median(_sum(y["steps"], "prompt_tokens") for y in run)
        if arm in NOTE_BUDGETS:
            row["median_note_tokens"] = _median(y["note_tokens"] for y in run)
            row["median_note_prompt_tokens"] = _median(y["note_prompt_tokens"] for y in run)
        arms.append(row)
    return {"items": len(items), "pre_steps": pre_steps.pop(), "steps": steps.pop(), "arms": arms}


def build(root) -> dict:
    """The results file from the six files in folder `root`, which `fetch` has verified."""
    root = Path(root)
    for command, name in CONFIGS.items():
        check_config(read_json(root / name), name, command)
    single = ledger(read_lines(root / "single.jsonl"), "single.jsonl", notes=False)
    chain = ledger(read_lines(root / "decomposed.jsonl"), "decomposed.jsonl", notes=True)
    return {
        "source": {"repo": REPO_URL, "revision": REVISION, "licence": LICENCE,
                   "files": {path: {"bytes": size, "sha256": sha256} for path, (size, sha256) in FILES.items()}},
        "model": MODEL,
        "depths": depths(single, chain),
        "probe": probe(read_lines(root / "handoff.jsonl"), "handoff.jsonl"),
    }


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def print_report(text: str) -> None:
    """Print `text` to stdout and flush it; after a BrokenPipeError, point stdout at os.devnull and
    re-raise, as the TRAIL summary does (DESIGN 13.11 v1.150)."""
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
    """The path an output option names, or a ValueError for a bad one, checked before any download."""
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
    parser = _Parser(prog="results.py", description="The ledger hand-off runs to a small results file")
    parser.add_argument("--out", required=True, help="output JSON path")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {default_cache_dir()})")
    try:
        args = parser.parse_args(argv)
        out = _check_out(args.out)
        part = out.with_name(out.name + ".part")
        try:  # on any failure from here on, <out>.part goes, a stale one from an earlier run included
            text = json.dumps(build(fetch(args.cache)), indent=2) + "\n"
            with open(part, "w", encoding="utf-8") as f:
                f.write(text)
            print_report(text.rstrip("\n"))  # before the rename, so a failed write to stdout leaves --out as it was
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
