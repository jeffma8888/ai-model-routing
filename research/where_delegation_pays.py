"""Where the per-task delegation decision pays on the committed evidence (DESIGN 13.8 v1.206, v1.323).

Reads only the five committed delegation results files under evidence/ and compares, in each
summary row (bar, flavor, point, parent), the `decision` strategy with the two fixed policies,
always `inline` and always `delegate`, on held-out success and list-price cost. Prints, per file,
flavor and bar, how many rows the decision equals a fixed policy in both, is better than both,
is beaten by one on success or on cost alone, or trades one for the other, then per flavor the
rows where the decision changed something by point, how many of them cost less than always
delegate and at no less success, and the largest success gain over the better fixed policy, and
the counts over all five files. Standard library only. Exit 0, or 2 with one
`error: ...` line when a file is missing, is not JSON, lacks a key the report reads, a row lacks
a strategy or has one twice, a success or a cost is not a number, or a row's decision equals a
fixed policy while its `delegate_rate` says the decision did not take that path on every cell (or
the reverse). That last check is a consistency check on the committed files, not a property of
DESIGN 13.9: a file whose two fixed policies share one pair, or whose mixed decision ties a policy
exactly, would fail it.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DATASETS = (
    ("AutoBench", "evidence/delegation/results.json"),
    ("tau2-bench", "evidence/tau2-bench-delegation/results.json"),
    ("tau2-bench pooled", "evidence/tau2-bench-delegation/pooled.json"),
    ("LLMRouterBench", "evidence/llmrouterbench-delegation/results.json"),
    ("LLM Routing Response Bank", "evidence/response-bank-delegation/results.json"),
)
STRATEGIES = ("decision", "inline", "delegate")
# The outcome classes, in column order; each row gets exactly one (see `classify`)
CLASSES = ("= delegate", "= inline", "better", "beaten on success", "beaten on cost", "trade-off")
HEADER = ("  flavor          bar   rows  = delegate  = inline  better  beaten on success  "
          "beaten on cost  trade-off  top success")


def pair(row):
    return row["success"], row["cost_usd"]


def classify(decision, inline, delegate):
    """One of CLASSES for a row: the decision's (success, cost) against the two fixed policies'.

    `= delegate` and `= inline` when it equals that policy in both (compared exactly, as floats);
    else `better` when its success is at least both and its cost at most both; else `beaten on
    success` when a fixed policy has a higher success at no more cost, `beaten on cost` when one
    has the same success at a lower cost; else `trade-off`."""
    d, i, g = pair(decision), pair(inline), pair(delegate)
    if d == g:
        return "= delegate"
    if d == i:
        return "= inline"
    if d[0] >= max(i[0], g[0]) and d[1] <= min(i[1], g[1]):
        return "better"
    if any(p[0] > d[0] and p[1] <= d[1] for p in (i, g)):
        return "beaten on success"
    if any(p[0] == d[0] and p[1] < d[1] for p in (i, g)):
        return "beaten on cost"
    return "trade-off"


def load(root, rel):
    path = Path(root) / rel
    try:
        results = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ValueError(f"{rel}: no such file") from None
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"{rel}: not a JSON file ({exc})") from None
    if not isinstance(results, dict):
        raise ValueError(f"{rel}: not a JSON object")
    return results


def rows_of(results, rel):
    """The summary as {(bar, flavor, point, parent): {strategy: row}} in file order."""
    groups = {}
    for row in results["summary"]:
        key = (row["bar"], row["flavor"], row["point"], row["parent"])
        group = groups.setdefault(key, {})
        if row["strategy"] in group:
            raise ValueError(f"{rel}: two {row['strategy']!r} rows for {key}")
        group[row["strategy"]] = row
    for key, group in groups.items():
        if sorted(group) != sorted(STRATEGIES):
            raise ValueError(f"{rel}: the row {key} has the strategies {sorted(group)}")
        for strategy in STRATEGIES:
            for value in pair(group[strategy]):
                if isinstance(value, bool) or not isinstance(value, (int, float)):
                    raise ValueError(f"{rel}: the {strategy!r} row {key} has a success or cost {value!r}")
        rate = group["decision"]["delegate_rate"]
        same = classify(group["decision"], group["inline"], group["delegate"])
        if (same == "= delegate") != (rate == 1.0) or (same == "= inline") != (rate == 0.0):
            raise ValueError(f"{rel}: the row {key} is {same!r} with delegate_rate {rate!r}")
    return groups


def plural(n, word):
    return f"{n} {word}{'' if n == 1 else 's'}"


def table_line(flavor, bar, counts, top):
    cells = [counts[c] for c in CLASSES]
    return (f"  {flavor:<14}  {bar:<4}  {sum(cells):>4}  {cells[0]:>10}  {cells[1]:>8}  {cells[2]:>6}  "
            f"{cells[3]:>17}  {cells[4]:>14}  {cells[5]:>9}  {top:>11}")


def gain(group):
    """The decision's success minus the better fixed policy's."""
    return group["decision"]["success"] - max(group["inline"]["success"], group["delegate"]["success"])


def report(root):
    lines = ["Where the per-task delegation decision pays: each summary row (bar, flavor, point, parent) of "
             "the five committed delegation files, the decision against always inline and always delegate"]
    totals = {}
    for name, rel in DATASETS:
        results = load(root, rel)
        try:
            config, groups = results["config"], rows_of(results, rel)
            flavors, bars, points = config["flavors"], config["bars"], config["points"]
            head = (f"{name} (`{rel}`): {plural(len(groups), 'row')}, {plural(len(results['tasks']), 'task')}, "
                    f"bars {' '.join(str(b) for b in bars)}, {plural(len(points), 'point')}, "
                    f"{plural(len(config['parents']), 'parent')}")
        except (KeyError, TypeError) as exc:
            raise ValueError(f"{rel}: lacks a key the report reads ({exc!r})") from None
        lines += [head, HEADER]
        for flavor in flavors:
            for bar in bars:
                sel = [g for k, g in groups.items() if k[:2] == (bar, flavor)]
                counts = Counter(classify(g["decision"], g["inline"], g["delegate"]) for g in sel)
                top = sum(1 for g in sel if gain(g) > 0)
                lines.append(table_line(flavor, bar, counts, top))
                total = totals.setdefault(flavor, [Counter(), 0])
                total[0].update(counts)
                total[1] += top
        for flavor in flavors:
            changed = [(k, g) for k, g in groups.items() if k[1] == flavor
                       and classify(g["decision"], g["inline"], g["delegate"]) not in CLASSES[:2]]
            by_point = Counter(k[2] for k, _ in changed)
            lines.append(f"  changed rows by point, {flavor}: "
                         + ", ".join(f"{p}: {by_point[p]}" for p in range(len(points))))
            if not changed:
                lines.append(f"  against always delegate, {flavor}: no changed row")
                lines.append(f"  largest gain, {flavor}: no changed row")
                continue
            cheaper = [g for _, g in changed if g["decision"]["cost_usd"] < g["delegate"]["cost_usd"]]
            kept = sum(1 for g in cheaper if g["decision"]["success"] >= g["delegate"]["success"])
            lines.append(f"  against always delegate, {flavor}: {plural(len(changed), 'changed row')}, {len(cheaper)} cheaper "
                         f"({kept} of them at no less success), {len(changed) - len(cheaper)} not cheaper")
            key, g = max(changed, key=lambda kg: gain(kg[1]))
            d, i, e = (pair(g[s]) for s in STRATEGIES)
            lines.append(f"  largest gain, {flavor}: bar {key[0]}, point {key[2]}, parent {key[3]}: decision "
                         f"{d[0]:.4f} at {d[1]:.4f} USD, inline {i[0]:.4f} at {i[1]:.4f}, delegate {e[0]:.4f} "
                         f"at {e[1]:.4f}, gain {gain(g):+.4f}")
    lines += ["All five files", HEADER]
    for flavor, (counts, top) in totals.items():
        lines.append(table_line(flavor, "all", counts, top))
    return "\n".join(lines) + "\n"


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.split("\n\n", 1)[0])
    parser.add_argument("--root", default=str(ROOT), help="the repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        text = report(args.root)
    except ValueError as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
