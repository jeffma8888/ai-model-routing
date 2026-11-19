"""Longtail-SWE as delegation evidence: can the 13.5 decision be scored on agent runs on repository issues?
(DESIGN 13.16 v1.495, row R50)

Reads the four pinned files of the converter `evidence/longtail-swe/convert.py` (12.25), loaded by path,
through its `fetch` (size and sha256 checked, an absent file downloaded), `run_records` (the 12.25 checks
and cost), `tokens` (the `usage.tokens` record) and `convert` (the 12.26 matrix, run 0). Columns read: the
converter's `COLUMNS` and `model_patch`. Of each run it keeps counts only: the characters of the one `user`
prompt of its trajectory (the brief, the statement the run starts from), the characters of its
`model_patch` (the result), `usage.model_calls`, the token totals, and how many of its events, or of their
messages, carry a `usage` or `tokens` key. A size in tokens is its characters over CHARS, rounded up; the
points' brief and result are the `statistics.median_low` of those sizes over the matrix's rows. It prints
the sizes, each model's context window against its runs' totals, and what `evaluate_delegation` gives on
the matrix with each row one call of its run's totals; it exits 2 if the harness scores those rows. Needs
`pyarrow` as the converter does. Exit 0, or 2 with one `error: ...` line, a carriage return or newline
escaped.

  python research/longtail_delegation.py [--cache DIR]
"""
import argparse
import importlib.util
import json
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model_routing import Registry, evaluate_delegation  # noqa: E402

BARS = [0.7, 0.8]
CONTEXTS = ((8000, True), (64000, True), (200000, True), (8000, False))
CARRY = 1
CHARS = 4  # characters a token, rounded up (the ratio of research/livecodebench-cost.md)
EXTRA = ("model_patch",)
KEYS = ("usage", "tokens")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONVERT = load("longtail_swe_convert_for_delegation", ROOT / "evidence" / "longtail-swe" / "convert.py")
CONFIG = ROOT / "evidence" / "longtail-swe" / "results.json"


def size(text) -> int:
    """Tokens of a string by the stated rule: its characters over CHARS, rounded up."""
    if not isinstance(text, str):
        raise ValueError(f"not a string: {type(text).__name__}")
    return -(-len(text) // CHARS)


def _marked(value) -> int:
    return int(isinstance(value, dict) and any(k in value for k in KEYS))


def counts(row) -> dict:
    """The brief and result sizes, the token totals, the model calls and the events with a usage record of
    one run; nothing else of the run is kept."""
    try:
        data = json.loads(row["trajectory"])
    except (TypeError, json.JSONDecodeError, RecursionError) as exc:
        raise ValueError(f"trajectory is not JSON: {exc}") from None
    if not isinstance(data, dict):
        raise ValueError("trajectory is not an object")
    prompts = data.get("prompts")
    users = [p for p in prompts if isinstance(p, dict) and p.get("role") == "user"] if isinstance(prompts, list) else []
    if len(users) != 1:
        raise ValueError(f"{len(users)} user prompts, not one")
    usage = data.get("usage")
    calls = usage.get("model_calls") if isinstance(usage, dict) else None
    if type(calls) is not int or calls < 1:
        raise ValueError(f"model_calls {calls!r} is not an int >= 1")
    tin, tout = CONVERT.tokens(row["trajectory"])
    events = data.get("events") if isinstance(data.get("events"), list) else []
    marked = sum(_marked(e) + sum(_marked(m) for m in (e.get("messages") or [] if isinstance(e, dict) else []))
                 for e in events)
    return {"brief": size(users[0].get("content")), "result": size(row.get("model_patch")),
            "input": tin, "output": tout, "calls": calls, "usage_events": marked}


def read(paths, registry) -> list:
    """(record, counts) per row of the four files, in FILES order; a ValueError names the file, then the row."""
    try:
        import pyarrow.parquet as pq
    except ImportError:
        raise ValueError("reading parquet needs pyarrow: pip install -e '.[evidence]'") from None
    out = []
    for name in CONVERT.FILES:
        try:
            rows = []
            for batch in pq.ParquetFile(paths[name]).iter_batches(columns=list(CONVERT.COLUMNS) + list(EXTRA)):
                rows += batch.to_pylist()
        except Exception as exc:
            raise ValueError(f"{name}: cannot read: {exc}") from None
        try:
            recs = CONVERT.run_records([{k: r[k] for k in CONVERT.COLUMNS} for r in rows], registry)
            for n, (rec, row) in enumerate(zip(recs, rows)):
                try:
                    out.append((rec, counts(row)))
                except ValueError as exc:
                    raise ValueError(f"row {n}: {exc}") from None
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from None
    return out


def matrix(pairs, run=0):
    """The 12.26 matrix as one-call rows of each run's token totals, the convert report, and (row, counts)."""
    rows, report = CONVERT.convert([rec for rec, _ in pairs], run)
    at = {(rec["item"], rec["model"]): c for rec, c in pairs if rec["run"] == run}
    kept = [(r, at[(r["item"], r["model"])]) for r in rows]
    out = [{"task": r["task"], "item": r["item"], "model": r["model"], "correct": r["correct"],
            "input_tokens": c["input"], "output_tokens": c["output"]} for r, c in kept]
    return out, report, kept


def points(brief, result) -> list:
    return [{"context_tokens": c, "brief_tokens": brief, "result_tokens": result, "carry_turns": CARRY,
             "inline_separate_call": separate} for c, separate in CONTEXTS]


def refusal(rows, registry, config, pts) -> str:
    """The harness's refusal of the one-call rows; a ValueError if it scores them."""
    try:
        evaluate_delegation(rows, registry, bars=BARS, points=pts, seeds=config["seeds"], flavors=config["flavors"],
                            calibration_fraction=config["calibration_fraction"], min_samples=config["min_samples"],
                            confidence=config["confidence"])
    except ValueError as exc:
        return str(exc)
    raise ValueError("the 13.9 harness scored the one-call rows, so the note's reading no longer holds")


def spread(values) -> str:
    q = statistics.quantiles(values, n=10, method="inclusive")
    return f"median {statistics.median_low(values):,}, 10th to 90th percentile {q[0]:,.0f} to {q[-1]:,.0f}"


def block(pairs, registry, config) -> str:
    rows, report, kept = matrix(pairs)
    models = report["models"]
    brief = statistics.median_low([c["brief"] for _, c in kept])
    result = statistics.median_low([c["result"] for _, c in kept])
    pts = points(brief, result)
    events = sum(c["usage_events"] for rec, c in pairs)
    out = [f"{CONVERT.DATASET} at {CONVERT.REVISION[:7]}: the 12.26 matrix (run 0, "
           f"{report['tasks'][CONVERT.TASK]['items']} items, {len(models)} models, {len(kept)} rows) as delegation evidence",
           f"Sizes over the {len(kept)} rows, tokens = characters / {CHARS}, rounded up",
           f"  brief, the run's user prompt: {spread([c['brief'] for _, c in kept])}",
           f"  result, the run's model_patch: {spread([c['result'] for _, c in kept])}; "
           f"{sum(c['result'] == 0 for _, c in kept)} empty",
           f"  run input tokens: {spread([c['input'] for _, c in kept])}",
           f"  run output tokens: {spread([c['output'] for _, c in kept])}",
           f"  model calls a run: {spread([c['calls'] for _, c in kept])}",
           f"  usage or tokens keys on events or their messages, all {len(pairs):,} runs of the four files: {events}",
           "Context window against each run's input plus output",
           "model                      window      over  median input  median calls  median input a call"]
    for m in models:
        mine = [c for r, c in kept if r["model"] == m]
        window = registry.get(m).context_window
        out.append(f"{m:<26} {window:>9,}  {sum(c['input'] + c['output'] > window for c in mine):>3} of {len(mine)}"
                   f"  {statistics.median_low([c['input'] for c in mine]):>12,}  "
                   f"{statistics.median_low([c['calls'] for c in mine]):>12}  "
                   f"{statistics.median_low([-(-c['input'] // c['calls']) for c in mine]):>19,}")
    out.append(f"13.9 harness, each row one call of its run's totals, bars {' '.join(map(str, BARS))}, "
               f"{len(config['seeds'])} seeds, points (carry turns {CARRY}, brief {brief:,}, result {result:,}): "
               + "; ".join(f"{i} context {p['context_tokens']:,} " + ("separate" if p["inline_separate_call"] else "folded")
                           for i, p in enumerate(pts)))
    out.append(f"  refused: {refusal(rows, registry, config, pts)}")
    return "\n".join(out) + "\n"


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None) -> int:
    parser = _Parser(prog="longtail_delegation.py", description="Longtail-SWE as delegation evidence")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {CONVERT.default_cache_dir()})")
    try:
        args = parser.parse_args(argv)
        config = json.loads(CONFIG.read_text(encoding="utf-8"))["config"]
        registry = Registry.load(CONVERT.REGISTRY)
        raw = json.loads(CONVERT.REGISTRY.read_text(encoding="utf-8"))
        text = block(read(CONVERT.fetch(args.cache), raw), registry, config)
    except (ValueError, OSError, KeyError, TypeError) as exc:
        msg = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {msg}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
