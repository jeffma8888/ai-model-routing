"""Delegation results on the LLMRouterBench matrix (DESIGN 13.13).

Usage:
  python evidence/llmrouterbench-delegation/results.py --matrix MATRIX.jsonl --registry registry.json --out results.json

Runs ``evaluate_delegation`` (DESIGN 13.9) on the LLMRouterBench converter's default matrix
(one task per benchmark, each row one model's single call on one item), filtered by
``select_rows`` to the models of the committed registry, the 8 pool models with a price, with
the items that have a null token count dropped, at the bars and seeds named below and the four
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

POOL = (
    "anthropic/claude-sonnet-4",
    "deepseek/deepseek-r1-0528",
    "deepseek/deepseek-v3-0324",
    "deepseek/deepseek-v3.1-terminus",
    "internlm/intern-s1",
    "openai/gpt-5",
    "openai/gpt-5-chat",
    "z-ai/glm-4.6",
)
BARS = (0.1, 0.3, 0.5, 0.8)
SEEDS = 50
KEYS = ("config", "tasks", "summary")
ROW_KEYS = ("item", "model", "input_tokens", "output_tokens")
_DELEGATION_SCRIPT = Path(__file__).resolve().parents[1] / "delegation" / "results.py"


def points() -> list:
    """The four base points of DESIGN 13.10, read from evidence/delegation/results.py by file path."""
    spec = importlib.util.spec_from_file_location("_delegation_results_points", _DELEGATION_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.points()


def select_rows(rows, models) -> tuple:
    """The rows of ``models``, less every item on which one of them has a null token count.

    Returns ``(rows left, dropped item IDs ascending)``; rows keep their input order and the
    input is not modified. A row of another model is ignored whatever its counts.
    """
    if not isinstance(models, (list, tuple)) or not models:
        raise ValueError("models must be a non-empty list or tuple of model IDs")
    if not all(isinstance(m, str) and m for m in models):
        raise ValueError("every model must be a non-empty string")
    if len(set(models)) != len(models):
        raise ValueError("models must be distinct")
    if not isinstance(rows, (list, tuple)):
        raise ValueError("rows must be a list or tuple")
    wanted = set(models)
    kept = []
    for number, r in enumerate(rows):
        if not isinstance(r, dict):
            raise ValueError(f"row {number} is not an object")
        absent = [key for key in ROW_KEYS if key not in r]
        if absent:
            raise ValueError(f"row {number} lacks {', '.join(absent)}")
        if r["model"] in wanted:
            kept.append(r)
    seen = {r["model"] for r in kept}
    unseen = [m for m in models if m not in seen]
    if unseen:
        raise ValueError(f"no row has the model {unseen[0]}")
    dropped = {r["item"] for r in kept if r["input_tokens"] is None or r["output_tokens"] is None}
    left = [r for r in kept if r["item"] not in dropped]
    if not left:
        raise ValueError("no row left after dropping the items with a null token count")
    return left, sorted(dropped, key=str)


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
                                     description="delegation results on the LLMRouterBench matrix")
    parser.add_argument("--matrix", required=True, help="LLMRouterBench converter output")
    parser.add_argument("--registry", required=True, help="registry of the priced pool models")
    parser.add_argument("--out", required=True, help="results file to write")
    args = parser.parse_args(argv)
    out = Path(args.out)
    part = out.with_name(out.name + ".part")
    try:
        registry = Registry.load(args.registry)
        rows, _dropped = select_rows(_read_rows(args.matrix), [m.id for m in registry.models])
        text = json.dumps(run(rows, registry), indent=2) + "\n"
        try:
            part.write_text(text, encoding="utf-8")
            part.replace(out)
        finally:
            part.unlink(missing_ok=True)
    except (ValueError, KeyError, TypeError, OSError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
