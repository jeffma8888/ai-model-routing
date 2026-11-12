"""Delegation results on the tau2-bench per-call matrix (DESIGN 13.12).

Usage:
  python evidence/tau2-bench-delegation/results.py --matrix MATRIX.jsonl --registry registry.json --out results.json

Runs ``evaluate_delegation`` (DESIGN 13.9) on the tau2-bench converter's ``--calls`` matrix
(one task per domain, each row a conversation priced on its own calls) with the committed
registry of the three agents that matrix keeps, at the bars and seeds named below and the four
base grid points of evidence/delegation/results.py, and keeps the config, tasks and summary (no
cells, so the file stays small). Print its tables with that script:
``python evidence/delegation/results.py --table results.json``, and with ``--bar X --point I``
one row per parent. Standard library and the model_routing package.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from pathlib import Path

from model_routing import Registry, evaluate_delegation

BARS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
SEEDS = 50
KEYS = ("config", "tasks", "summary")
_DELEGATION_SCRIPT = Path(__file__).resolve().parents[1] / "delegation" / "results.py"


def _delegation():
    """evidence/delegation/results.py, loaded by file path."""
    spec = importlib.util.spec_from_file_location("_delegation_results_points", _DELEGATION_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def points() -> list:
    """The four base points of DESIGN 13.10, read from evidence/delegation/results.py by file path."""
    return _delegation().points()


def run(rows, registry) -> dict:
    """The 13.9 evidence at BARS, the base points and SEEDS seeds, keeping only KEYS."""
    result = evaluate_delegation(rows, registry, bars=list(BARS), points=points(), seeds=range(SEEDS))
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
    parser = argparse.ArgumentParser(prog="results.py",
                                     description="delegation results on the tau2-bench per-call matrix")
    parser.add_argument("--matrix", required=True, help="tau2-bench converter output with --calls")
    parser.add_argument("--registry", required=True, help="registry of the matrix's agents")
    parser.add_argument("--out", required=True, help="results file to write")
    args = parser.parse_args(argv)
    part = None
    try:
        out = Path(args.out)
        candidate = out.with_name(out.name + ".part")
        clash = _delegation().clashing_input(out, [("--matrix", args.matrix), ("--registry", args.registry)])
        if clash is not None:  # a usage error, before any file is read, written or removed (v1.269)
            print(f"error: --out (or its .part file) names the same file as {clash}", file=sys.stderr)
            return 2
        part = candidate
        text = json.dumps(run(_read_rows(args.matrix), Registry.load(args.registry)), indent=2) + "\n"
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
