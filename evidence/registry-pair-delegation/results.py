"""Delegation results on the registry pair, superlinked/train-a-router-reasoning (DESIGN 13.17).

Usage:
  python evidence/registry-pair-delegation/results.py --matrix MATRIX.jsonl --out results.json

Runs ``evaluate_delegation`` (DESIGN 13.9) on the registry-pair converter's default matrix (12.23:
one task per (dataset, task) pair, each row one of the registry's own two models on one question,
with the release's cost estimate and no token counts). ``matrix`` gives each row tokens at the
``low`` end of 13.16 v1.466: both models list output at RATIO times input, so a row's cost fixes
E = cost_usd * 10^6 / price_in = in + RATIO * out, rounded here to the nearest whole token (a half
to the even one), and the row takes in = E % RATIO and out = E // RATIO, the fewest tokens that
cost E, which under-states the inline path's re-read. It runs at the bars and seeds named below
and the four base grid points of evidence/delegation/results.py (read by file path, with its
``clashing_input``), on this checkout's registry, and keeps the config, tasks and summary (no
cells, so the file stays small). Print its tables with
``python evidence/delegation/results.py --table results.json``. Standard library and the
model_routing package.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import math
import sys
from fractions import Fraction
from pathlib import Path

from model_routing import Registry, evaluate_delegation

RATIO = 5
BARS = (0.8, 0.9)
SEEDS = 50
KEYS = ("config", "tasks", "summary")
_EVIDENCE = Path(__file__).resolve().parents[1]
REGISTRY = _EVIDENCE.parent / "model_routing" / "data" / "models.json"
_DELEGATION_SCRIPT = _EVIDENCE / "delegation" / "results.py"


def _delegation():
    """evidence/delegation/results.py, loaded by file path."""
    spec = importlib.util.spec_from_file_location("_delegation_results_for_registry_pair", _DELEGATION_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tokens(cost_usd, price_in) -> tuple:
    """(input_tokens, output_tokens) at the low end: E rounded to a whole token, a half to the even one."""
    if type(cost_usd) not in (int, float) or not math.isfinite(cost_usd) or cost_usd < 0:
        raise ValueError(f"cost_usd {cost_usd!r} is not a finite number >= 0")
    e = round(Fraction(repr(cost_usd)) * 10 ** 6 / Fraction(str(price_in)))
    return e % RATIO, e // RATIO


def _check_ratio(model) -> None:
    if model.price_tiers or Fraction(str(model.price_out)) != RATIO * Fraction(str(model.price_in)):
        raise ValueError(f"output price of {model.id}: {model.price_out} is not {RATIO} times its input price "
                         f"{model.price_in}, or the model has price tiers")


def matrix(rows, registry) -> list:
    """The 13.9 rows: each row's task, item, model and correct, then its low-end tokens in place of its cost."""
    checked = set()
    out = []
    for r in rows:
        model = r["model"]
        if model not in registry:
            raise ValueError(f"model not in the registry: {model}")
        m = registry.get(model)
        if model not in checked:
            _check_ratio(m)
            checked.add(model)
        tin, tout = tokens(r["cost_usd"], m.price_in)
        out.append({"task": r["task"], "item": r["item"], "model": model, "correct": r["correct"],
                    "input_tokens": tin, "output_tokens": tout})
    return out


def run(rows, registry) -> dict:
    """The 13.9 evidence at BARS, the base points and SEEDS seeds, keeping only KEYS."""
    result = evaluate_delegation(rows, registry, bars=list(BARS), points=_delegation().points(), seeds=range(SEEDS))
    return {key: result[key] for key in KEYS}


def _read_rows(path: str) -> list:
    rows = []
    with open(path, encoding="utf-8") as fh:
        for number, line in enumerate(fh, 1):
            if not line.strip():
                continue
            try:
                rows.append(json.loads(line))
            except ValueError as exc:
                raise ValueError(f"{path}:{number}: invalid JSON: {exc}") from None
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="results.py", description="delegation results on the registry pair")
    parser.add_argument("--matrix", required=True, help="registry-pair converter output")
    parser.add_argument("--out", required=True, help="results file to write")
    args = parser.parse_args(argv)
    part = None
    try:
        out = Path(args.out)
        candidate = out.with_name(out.name + ".part")
        clash = _delegation().clashing_input(out, [("--matrix", args.matrix), ("the registry", str(REGISTRY))])
        if clash is not None:  # a usage error, before any file is read, written or removed (13.10 v1.269)
            print(f"error: --out (or its .part file) names the same file as {clash}", file=sys.stderr)
            return 2
        part = candidate
        registry = Registry.load(REGISTRY)
        rows = matrix(_read_rows(args.matrix), registry)
        text = json.dumps(run(rows, registry), indent=2) + "\n"
        part.write_text(text, encoding="utf-8")
        part.replace(out)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 1
    finally:
        if part is not None:
            try:
                part.unlink(missing_ok=True)
            except OSError:
                pass
    return 0


if __name__ == "__main__":
    sys.exit(main())
