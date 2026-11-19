"""Delegation results on Longtail-SWE, nebius/Longtail-SWE-trajectories, per call under a stated split (DESIGN 13.18).

Usage:
  python evidence/longtail-swe-delegation/results.py --out results.json [--cache DIR]

Loads research/longtail_per_call.py by file path (``PC``) and with it research/longtail_delegation.py
(``LD``), whose ``read`` takes the counts of each run of the four pinned files of the converter
evidence/longtail-swe/convert.py (12.25), fetched and checked by its ``fetch`` (no statement, message or
patch is kept), and whose ``matrix`` gives the 12.26 matrix at run 0. The release records each run's token
totals only, so ``PC.per_call`` splits each run into its model calls by the rule of 13.16 v1.496, an
assumption the release cannot check. ``evaluate_delegation`` (13.9, per-call mode) runs once on the split
rows at BARS, the four points of research/longtail-delegation.md and the seeds, flavors, calibration
fraction, ``min_samples`` and confidence of evidence/longtail-swe/results.json, on this checkout's registry;
the file keeps the config, tasks and summary (no cells) and the split's counts. Print its tables with
``python evidence/delegation/results.py --table results.json``. Needs ``pyarrow``, the ``evidence`` extra.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from model_routing import Registry, evaluate_delegation  # noqa: E402

BARS = (0.7, 0.8)
KEYS = ("config", "tasks", "summary")
REGISTRY = ROOT / "model_routing" / "data" / "models.json"
_PER_CALL_SCRIPT = ROOT / "research" / "longtail_per_call.py"
_DELEGATION_SCRIPT = ROOT / "evidence" / "delegation" / "results.py"


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


PC = _load("longtail_per_call_for_delegation_results", _PER_CALL_SCRIPT)
LD = PC.LD
CONVERT = LD.CONVERT
CONFIG = LD.CONFIG


def _delegation():
    """evidence/delegation/results.py, loaded by file path."""
    return _load("_delegation_results_for_longtail_swe", _DELEGATION_SCRIPT)


def inputs(pairs) -> tuple:
    """The split rows, the four points and the split's counts, from the (record, counts) pairs of ``LD.read``."""
    one, _, kept = LD.matrix(pairs)
    brief = statistics.median_low([c["brief"] for _, c in kept])
    result = statistics.median_low([c["result"] for _, c in kept])
    rows, refused, dropped = PC.per_call([(r, c) for r, (_, c) in zip(one, kept)])
    return rows, LD.points(brief, result), {"runs_refused": refused, "items_dropped": dropped, "rows": len(rows)}


def run(rows, points, split, registry, config) -> dict:
    """The 13.9 evidence at BARS on the split rows, keeping KEYS and the split's counts."""
    result = evaluate_delegation(rows, registry, bars=list(BARS), points=points, seeds=config["seeds"],
                                 flavors=config["flavors"], calibration_fraction=config["calibration_fraction"],
                                 min_samples=config["min_samples"], confidence=config["confidence"])
    out = {key: result[key] for key in KEYS}
    out["split"] = dict(split)
    return out


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="results.py", description="delegation results on Longtail-SWE, per call")
    parser.add_argument("--out", required=True, help="results file to write")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {CONVERT.default_cache_dir()})")
    args = parser.parse_args(argv)
    part = None
    try:
        out = Path(args.out)
        root = Path(args.cache) if args.cache is not None else CONVERT.default_cache_dir()
        named = [("the config", str(CONFIG)), ("the registry", str(REGISTRY))]
        named += [(f"the pinned file {name}", str(root / name)) for name in sorted(CONVERT.FILES)]
        clash = _delegation().clashing_input(out, named)
        if clash is not None:  # a usage error, before any file is read, written or removed (13.10 v1.269)
            print(f"error: --out (or its .part file) names the same file as {clash}", file=sys.stderr)
            return 2
        part = out.with_name(out.name + ".part")
        config = json.loads(CONFIG.read_text(encoding="utf-8"))["config"]
        registry = Registry.load(REGISTRY)
        raw = json.loads(REGISTRY.read_text(encoding="utf-8"))
        rows, points, split = inputs(LD.read(CONVERT.fetch(args.cache), raw))
        text = json.dumps(run(rows, points, split, registry, config), indent=2) + "\n"
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
