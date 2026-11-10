"""Can LLMRouterBench feed the delegation evidence? Recorded costs against list prices (DESIGN 13.9 v1.187)

Usage:
  python research/llmrouterbench_prices.py --matrix llmrouterbench-matrix.jsonl

Reads the rows the LLMRouterBench converter writes (DESIGN 12.18), drops every row of an item on
which any row has a null token count, as a delegation run must, and prints per model, on the kept
items, the recorded cost, the cost at the vendor list price of `LIST_PRICES` and their ratio, and
whether one input and output price reproduces every recorded cost. Standard library only. Read by
research/delegation-datasets.md. Exit 0, or 2 with one `error: ...` line on a missing or unreadable
file or a row it refuses.
"""

import argparse
import json
import math
import sys

# USD per 1M tokens (input, output), from the vendor pages research/delegation-datasets.md lists,
# opened 2026-11-09, for the pool models whose page states a price
LIST_PRICES = {
    "anthropic/claude-sonnet-4": (3, 15),
    "openai/gpt-5": (1.25, 10),
    "openai/gpt-5-chat": (1.25, 10),
    "z-ai/glm-4.6": (0.6, 2.2),
}
TOLERANCE = 1e-9  # USD: a price pair is exact when every kept row's cost is this close to it
KEYS = ("task", "item", "model", "cost_usd", "input_tokens", "output_tokens")


def _count(value):
    return value is None or (isinstance(value, int) and not isinstance(value, bool) and value >= 0)


def load_rows(path):
    """The converter's rows, checked; a ValueError or OSError names the problem."""
    rows, seen = [], set()
    with open(path, encoding="utf-8") as handle:
        for number, line in enumerate(handle, 1):
            if not line.strip():
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"{path}:{number}: not JSON ({exc.msg})") from None
            if not isinstance(row, dict):
                raise ValueError(f"{path}:{number}: not a JSON object")
            for key in KEYS:
                if key not in row:
                    raise ValueError(f"{path}:{number}: no {key!r}")
            for key in ("task", "item", "model"):
                if not isinstance(row[key], str) or not row[key]:
                    raise ValueError(f"{path}:{number}: {key!r} must be a non-empty string")
            cost = row["cost_usd"]
            if isinstance(cost, bool) or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                raise ValueError(f"{path}:{number}: 'cost_usd' must be a finite number >= 0")
            for key in ("input_tokens", "output_tokens"):
                if not _count(row[key]):
                    raise ValueError(f"{path}:{number}: {key!r} must be an integer >= 0 or null")
            if (row["item"], row["model"]) in seen:
                raise ValueError(f"{path}:{number}: repeated item {row['item']!r} for {row['model']!r}")
            seen.add((row["item"], row["model"]))
            rows.append(row)
    if not rows:
        raise ValueError(f"{path}: no rows")
    models = {r["model"] for r in rows}
    items = {r["item"] for r in rows}
    if len(seen) != len(models) * len(items):
        lacking = sorted(i for i in items if sum((i, m) in seen for m in models) != len(models))
        raise ValueError(f"{path}: item {lacking[0]!r} lacks a model of the rows")
    return rows


def fit(points):
    """Least-squares (input, output) prices, USD per 1M tokens, each rounded to 4 decimals, over
    (input_tokens, output_tokens, cost) points, with the largest difference they leave and the
    largest difference the unrounded least-squares pair leaves; None when the counts fix no pair."""
    sxx = math.fsum(x * x for x, _, _ in points)
    syy = math.fsum(y * y for _, y, _ in points)
    sxy = math.fsum(x * y for x, y, _ in points)
    sxz = math.fsum(x * z for x, _, z in points)
    syz = math.fsum(y * z for _, y, z in points)
    det = sxx * syy - sxy * sxy
    if not points or det <= 0:
        return None
    a0 = (sxz * syy - syz * sxy) / det * 1e6
    b0 = (syz * sxx - sxz * sxy) / det * 1e6
    unrounded = max(abs(z - (x * a0 + y * b0) / 1e6) for x, y, z in points)
    a, b = round(a0, 4), round(b0, 4)
    worst = max(abs(z - (x * a + y * b) / 1e6) for x, y, z in points)
    return a, b, worst, unrounded


def _price(value):
    return f"{value:g}"


def report(rows, list_prices=LIST_PRICES):
    """The printed lines, without a trailing newline."""
    models = sorted({r["model"] for r in rows})
    tasks = sorted({r["task"] for r in rows})
    items = {r["item"]: r["task"] for r in rows}
    counts = [r["input_tokens"] for r in rows if r["input_tokens"] is not None]
    largest = max(counts) if counts else "none"
    dropped = sorted({r["item"] for r in rows if r["input_tokens"] is None or r["output_tokens"] is None})
    per_task = {}
    for item in dropped:
        per_task[items[item]] = per_task.get(items[item], 0) + 1
    kept = [r for r in rows if r["item"] not in set(dropped)]
    lines = [
        f"{len(items)} items over {len(tasks)} tasks and {len(models)} models; largest input_tokens {largest}",
        f"null token count: {len(dropped)} items"
        + (" (" + ", ".join(f"{t} {n}" for t, n in sorted(per_task.items())) + ")" if dropped else "")
        + f", {len(dropped) * len(models)} rows; kept {len(items) - len(dropped)} items, {len(kept)} rows",
        "per model on the kept items: recorded cost, cost at the list price, their ratio, and one price pair "
        f"for every recorded cost (USD per 1M tokens, exact within {TOLERANCE:g} USD)",
    ]
    listed = exact = either = 0
    for model in models:
        mine = [r for r in kept if r["model"] == model]
        recorded = math.fsum(r["cost_usd"] for r in mine)
        line = f"  {model}: recorded {recorded:.6f}; "
        if model in list_prices:
            p_in, p_out = list_prices[model]
            at = math.fsum((r["input_tokens"] * p_in + r["output_tokens"] * p_out) / 1e6 for r in mine)
            ratio = f"{recorded / at:.3f}" if at > 0 else "none"
            line += f"list {_price(p_in)} in, {_price(p_out)} out: {at:.6f}, ratio {ratio}; "
            listed += 1
        else:
            line += "list none; "
        pair = fit([(r["input_tokens"], r["output_tokens"], r["cost_usd"]) for r in mine])
        if pair is None:
            line += "no exact pair (the counts fix no pair)"
        elif pair[2] <= TOLERANCE:
            line += f"exact pair {_price(pair[0])} in, {_price(pair[1])} out"
            exact += 1
        elif pair[3] > math.sqrt(len(mine)) * TOLERANCE:
            # a pair within TOLERANCE of every cost leaves a sum of squares of at most n * TOLERANCE**2,
            # which the least-squares pair cannot exceed, so none of its differences could pass this
            line += (f"no pair within {TOLERANCE:g} USD (least squares {_price(pair[0])} in, {_price(pair[1])} out "
                     f"to 4 decimals; unrounded off by up to {pair[3]:.6f} USD)")
        else:
            line += (f"no 4-decimal pair (least squares {_price(pair[0])} in, {_price(pair[1])} out, "
                     f"off by up to {pair[2]:.6f} USD; a finer pair is not ruled out)")
        either += model in list_prices or (pair is not None and pair[2] <= TOLERANCE)
        lines.append(line)
    lines.append(f"summary: list price {listed} of {len(models)}, exact pair {exact} of {len(models)}, "
                 f"either {either} of {len(models)}")
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n", 1)[0])
    parser.add_argument("--matrix", required=True, help="the LLMRouterBench converter's rows (JSONL)")
    args = parser.parse_args(argv)
    try:
        lines = report(load_rows(args.matrix))
    except (OSError, ValueError) as exc:
        message = str(exc).replace("\n", "\\n").replace("\r", "\\r")
        print(f"error: {message}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
