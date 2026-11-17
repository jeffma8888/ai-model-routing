"""superlinked/train-a-router-reasoning to an outcome matrix (DESIGN 12.23, v1.431).

Standard library only; the package never imports this script. It reads the release's pair.json and its two
graded splits at one pinned revision, checks that the pair's two models and their input and output list prices
are the registry's own (model_routing/data/models.json, read as JSON), and writes one 12.1 row per (task, item,
model), both splits joined, so that 12.2 draws its halves by seed. The release is a collection of MIT and
Apache-2.0 components (its card's `license_name` at REVISION); no question or answer text is read or written.
"""

import argparse
import hashlib
import json
import math
import os
import sys
import urllib.request
from pathlib import Path

DATASET = "superlinked/train-a-router-reasoning"
REVISION = "63336f25fc54597a8e161a7245613f91bd60177e"
LICENCE = "mixed-mit-and-apache-2.0"
FILES = {
    "pair.json": (2473, "4b4cc5f936fe8a8018b6845bfa9bd29b7d18ec428489d15ebab62554c4cd11b4"),
    "recordings/grades-calibration.json": (3777170, "2f47b9df61b131879f30b4ea36693a8ce8bc43e46afd17d7fbd5d7a93922e8ac"),
    "recordings/grades-final.json": (3742778, "8d66442ad94b5e846a856084adfaba7a2915bab6253008e93ed44348dc264a5f"),
}
SPLITS = ("calibration", "final")
ARMS = ("cheap", "strong")
VENDOR = "openai/"
PAIR_FORMAT = "routerbench-openai-pair-v1"
GRADES_FORMAT = "routerbench-paired-grades-v1"
REGISTRY = Path(__file__).resolve().parents[2] / "model_routing" / "data" / "models.json"
TIMEOUT = 60
ATTEMPTS = 3  # tries per missing file, at once (DESIGN.md 12.13 v1.406)


def url(name) -> str:
    """The download URL of one pinned file at REVISION; a ValueError for any other name."""
    if name not in FILES:
        raise ValueError(f"not a pinned file: {name!r}")
    return f"https://huggingface.co/datasets/{DATASET}/resolve/{REVISION}/{name}"


def _text(value, what):
    if not isinstance(value, str) or not value:
        raise ValueError(f"{what} must be a non-empty string, got {value!r}")
    return value


def _price(value, what):
    """A list price per million tokens, a number or a decimal string, finite and >= 0 (never a bool)."""
    if isinstance(value, bool) or not isinstance(value, (int, float, str)):
        raise ValueError(f"pair price: {what} {value!r} is not a price")
    try:
        found = float(value)
    except (ValueError, OverflowError):
        raise ValueError(f"pair price: {what} {value!r} is not a price") from None
    if not math.isfinite(found) or found < 0:
        raise ValueError(f"pair price: {what} {value!r} is not a price")
    return found


def check_pair(pair, registry) -> dict:
    """`{arm: registry ID}` for the two arms of `pair` (parsed pair.json), after each arm's model is checked to be
    in `registry` (parsed models.json) as `openai/<model>` at the pair's input and output prices."""
    if not isinstance(pair, dict) or pair.get("format") != PAIR_FORMAT:
        found = pair.get("format") if isinstance(pair, dict) else pair
        raise ValueError(f"pair format {found!r}, expected {PAIR_FORMAT!r}")
    models = registry.get("models") if isinstance(registry, dict) else None
    if not isinstance(models, list) or not all(isinstance(m, dict) for m in models):
        raise ValueError("registry: not a models.json registry")
    listed = {m.get("id"): m for m in models}
    ids = {}
    for arm in ARMS:
        try:
            model = pair["arms"][arm]["model"]
        except (KeyError, TypeError, IndexError):
            raise ValueError(f"pair: no {arm} model") from None
        if not isinstance(model, str) or not model:
            raise ValueError(f"pair: the {arm} model {model!r} is not a non-empty string")
        try:
            prices = pair["prices_usd_per_million"][model]
            pin, pout = prices["input"], prices["output"]
        except (KeyError, TypeError, IndexError):
            raise ValueError(f"pair: no input and output price for {model!r}") from None
        rid = VENDOR + model
        if rid not in listed:
            raise ValueError(f"model not in the registry: the {arm} model {model!r} as {rid!r}")
        found = (_price(pin, f"{model} input"), _price(pout, f"{model} output"))
        row = listed[rid]
        expected = (row.get("price_in"), row.get("price_out"))
        if found != expected:
            raise ValueError(f"price differs: {model} {found} in pair.json, {expected} in the registry")
        ids[arm] = rid
    if ids["cheap"] == ids["strong"]:
        raise ValueError(f"same model in both arms: {ids['cheap']!r}")
    return ids


def grade_rows(grades, split, ids) -> list:
    """One record per row of a graded split and arm, in file order: `task`, `item`, `family`, `split`, `model`,
    `correct`, `cost_usd` and `valid`, in that order."""
    if not isinstance(grades, dict) or grades.get("format") != GRADES_FORMAT or grades.get("split") != split:
        found = (grades.get("format"), grades.get("split")) if isinstance(grades, dict) else grades
        raise ValueError(f"grades format: {found!r}, expected {(GRADES_FORMAT, split)!r}")
    rows = grades.get("rows")
    if not isinstance(rows, list) or not rows:
        raise ValueError(f"no rows in the {split} split")
    out = []
    for n, row in enumerate(rows):
        if not isinstance(row, dict):
            raise ValueError(f"{split} row {n}: not an object")
        item = _text(row.get("id"), f"{split} row {n} id")
        where = f"{split} row {item!r}"
        if row.get("role") != split:
            raise ValueError(f"row role: {where} has role {row.get('role')!r}")
        dataset = _text(row.get("dataset"), f"{where} dataset")
        if "/" in dataset:
            raise ValueError(f"{where} dataset {dataset!r} holds '/'")
        task = f"{dataset}/{_text(row.get('task'), f'{where} task').replace(' ', '_')}"
        family = _text(row.get("family"), f"{where} family")
        for arm in ARMS:
            correct, cost, valid = row.get(f"{arm}_correct"), row.get(f"{arm}_cost_usd"), row.get(f"{arm}_valid")
            if type(correct) is not int or correct not in (0, 1):
                raise ValueError(f"{where}: {arm}_correct {correct!r} is not 0 or 1")
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                raise ValueError(f"{where}: {arm}_cost_usd {cost!r} is not a finite number >= 0")
            if not isinstance(valid, bool):
                raise ValueError(f"{where}: {arm}_valid {valid!r} is not a bool")
            if not valid and correct == 1:
                raise ValueError(f"invalid cell scored 1: {where}, {arm}")
            out.append({"task": task, "item": item, "family": family, "split": split, "model": ids[arm],
                        "correct": correct == 1, "cost_usd": float(cost) + 0.0, "valid": valid})
    return out


def _records(value, name):
    if not isinstance(value, (list, tuple)) or not value:
        raise ValueError(f"{name} must be a non-empty list or tuple")
    return value


def convert(calibration, final) -> tuple:
    """`(rows, report)` over the `grade_rows` records of the two splits, joined."""
    cells = {}
    for name, records in (("calibration", calibration), ("final", final)):
        for r in _records(records, name):
            by_model = cells.setdefault(r["item"], {})
            first = next(iter(by_model.values()), None)
            if first is not None and first["split"] != r["split"]:
                raise ValueError(f"item in both splits: {r['item']!r}")
            if r["model"] in by_model:
                raise ValueError(f"repeated cell: item {r['item']!r}, model {r['model']!r}")
            if first is not None and (first["task"], first["family"]) != (r["task"], r["family"]):
                raise ValueError(f"item task differs: item {r['item']!r}")
            by_model[r["model"]] = r
    models = sorted({m for by_model in cells.values() for m in by_model})
    for item, by_model in sorted(cells.items()):
        if len(by_model) != len(models):
            raise ValueError(f"incomplete item: {item!r} has no row for "
                             f"{sorted(set(models) - set(by_model))[0]!r}")
    rows, tasks, family_items = [], {}, {}
    for item, by_model in sorted(cells.items(), key=lambda kv: (next(iter(kv[1].values()))["task"], kv[0])):
        first = next(iter(by_model.values()))
        t = tasks.setdefault(first["task"], {"items": 0, "calibration": 0, "final": 0, "invalid_cells": 0})
        t["items"] += 1
        t[first["split"]] += 1
        family_items.setdefault(first["family"], []).append(first)
        for model in models:
            r = by_model[model]
            t["invalid_cells"] += not r["valid"]
            rows.append({"task": r["task"], "item": item, "model": model, "correct": r["correct"],
                         "cost_usd": r["cost_usd"]})
    shared = {f: rs for f, rs in family_items.items() if len(rs) > 1}
    report = {
        "models": models,
        "tasks": {task: tasks[task] for task in sorted(tasks)},
        "families": {
            "families": len(family_items),
            "shared_families": len(shared),
            "shared_items": sum(len(rs) for rs in shared.values()),
            "in_both_splits": sum(len({r["split"] for r in rs}) > 1 for rs in family_items.values()),
            "across_tasks": sum(len({r["task"] for r in rs}) > 1 for rs in family_items.values()),
        },
        "rows": len(rows),
    }
    return rows, report


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "registry-pair"


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


def read_json(path, name=None):
    """One JSON file, parsed; invalid UTF-8 or JSON, or nesting past the recursion limit, is a ValueError naming
    the file."""
    name = Path(path).name if name is None else name
    try:
        return json.loads(Path(path).read_bytes().decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"{name}: invalid JSON: {exc}") from None


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


def _read_all(paths) -> tuple:
    """The two splits' `grade_rows` records, calibration first, after the pair is checked against REGISTRY."""
    ids = check_pair(read_json(paths["pair.json"], "pair.json"), read_json(REGISTRY, "models.json"))
    return tuple(grade_rows(read_json(paths[f"recordings/grades-{s}.json"], f"grades-{s}.json"), s, ids)
                 for s in SPLITS)


def main(argv=None) -> int:
    parser = _Parser(prog="convert.py", description="superlinked/train-a-router-reasoning to an outcome matrix")
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
