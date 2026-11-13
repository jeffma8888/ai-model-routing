"""Delegation results on the LLM Routing Response Bank matrix (DESIGN 13.14).

Usage:
  python evidence/response-bank-delegation/results.py --matrix MATRIX.jsonl --registry registry.json --out results.json

Runs ``evaluate_delegation`` (DESIGN 13.9) on the response-bank converter's default matrix
(12.20: one task per benchmark, each row one model's single call on one item), filtered by
``select_rows`` to the models of the committed registry, all five models of the release, each
priced at the input and output pair its bills give on its responses with no cache read, with the
items that have a null token count dropped, at the bars and seeds named below and the four base
grid points of evidence/delegation/results.py, and keeps the config, tasks and summary (no
cells, so the file stays small). ``select_rows`` and ``points()`` are read by file path from
evidence/llmrouterbench-delegation/results.py and evidence/delegation/results.py, so neither
rule can drift between the runs. Print its tables with the delegation script:
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

POOL = (
    "deepseek/deepseek-v4-flash",
    "deepseek/deepseek-v4-pro",
    "moonshotai/kimi-k2.7-code",
    "z-ai/glm-5.3",
    "z-ai/glm-5.3-flash",
)
BARS = (0.8, 0.9)
SEEDS = 50
KEYS = ("config", "tasks", "summary")
_EVIDENCE = Path(__file__).resolve().parents[1]
_DELEGATION_SCRIPT = _EVIDENCE / "delegation" / "results.py"
_LLMROUTERBENCH_SCRIPT = _EVIDENCE / "llmrouterbench-delegation" / "results.py"


def _load(name: str, path: Path):
    """The module at ``path``, loaded by file path."""
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _delegation():
    """evidence/delegation/results.py, loaded by file path."""
    return _load("_delegation_results_points", _DELEGATION_SCRIPT)


def points() -> list:
    """The four base points of DESIGN 13.10, read from evidence/delegation/results.py by file path."""
    return _delegation().points()


select_rows = _load("_llmrouterbench_delegation_select_rows", _LLMROUTERBENCH_SCRIPT).select_rows


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
                                     description="delegation results on the LLM Routing Response Bank matrix")
    parser.add_argument("--matrix", required=True, help="response-bank converter output")
    parser.add_argument("--registry", required=True, help="registry of the five priced models")
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
        registry = Registry.load(args.registry)
        rows, _dropped = select_rows(_read_rows(args.matrix), [m.id for m in registry.models])
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
