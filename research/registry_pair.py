"""The registry's own model pair on public data: superlinked/train-a-router-reasoning (DESIGN 12.22 v1.430, row R40).

Reads the release's `pair.json` and its two graded splits, `recordings/grades-calibration.json` and
`recordings/grades-final.json`, at the pinned revision, each checked against its pinned size and
sha256 and downloaded into `--cache` when absent. Checks that the pair's two models and their input
and output list prices are the registry's own (model_routing/data/models.json), then calibrates on
the calibration split and scores on the final split, the release's own held-out protocol, with the
evaluator's own cell (`_split_sums`, `_cell`, `_strategies` and `_summary` of
model_routing/evaluate.py, private names this script may use as research/response_bank_split.py
does), one task per (dataset, task) pair, at the bars, `min_samples` and confidence of the committed
evidence/routerbench/results.json, both flavors. Standard library and `model_routing` only. Exit 0,
or 2 with one `error: ...` line, a carriage return or newline escaped.

  python research/registry_pair.py [--cache DIR] [--root PATH]
"""

import argparse
import hashlib
import json
import math
import sys
import urllib.request
from pathlib import Path

from model_routing import Outcome, Registry
from model_routing.evaluate import _cell, _split_sums, _strategies, _summary
from model_routing.stats import wilson_lower_bound

ROOT = Path(__file__).resolve().parents[1]
REPO = "superlinked/train-a-router-reasoning"
REVISION = "63336f25fc54597a8e161a7245613f91bd60177e"
FILES = {
    "pair.json": (2473, "4b4cc5f936fe8a8018b6845bfa9bd29b7d18ec428489d15ebab62554c4cd11b4"),
    "recordings/grades-calibration.json": (3777170, "2f47b9df61b131879f30b4ea36693a8ce8bc43e46afd17d7fbd5d7a93922e8ac"),
    "recordings/grades-final.json": (3742778, "8d66442ad94b5e846a856084adfaba7a2915bab6253008e93ed44348dc264a5f"),
}
SPLITS = ("calibration", "final")
ARMS = ("cheap", "strong")
VENDOR = "openai/"
CONFIG = "evidence/routerbench/results.json"
SEED = "release"
TIMEOUT = 60


def url(name):
    return f"https://huggingface.co/datasets/{REPO}/resolve/{REVISION}/{name}"


def default_cache_dir():
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "registry-pair"


def verify(path, size, sha256, name=None):
    path = Path(path)
    name = path.name if name is None else name
    if path.stat().st_size != size:
        raise ValueError(f"{name}: size {path.stat().st_size}, expected {size}")
    digest = hashlib.sha256(path.read_bytes()).hexdigest()
    if digest != sha256:
        raise ValueError(f"{name}: sha256 {digest}, expected {sha256}")


def fetch(cache, opener=urllib.request.urlopen):
    """Each pinned file's path, in FILES order, once it is in `cache` and verified; an absent file
    is downloaded at the pinned revision to a `.part` file, verified, then renamed."""
    out = {}
    for name, (size, sha256) in FILES.items():
        dest = Path(cache) / name
        if not dest.exists():
            dest.parent.mkdir(parents=True, exist_ok=True)
            part = dest.with_name(dest.name + ".part")
            with opener(url(name), timeout=TIMEOUT) as resp:
                part.write_bytes(resp.read())
            try:
                verify(part, size, sha256, name)
            except ValueError:
                part.unlink()
                raise
            part.replace(dest)
        verify(dest, size, sha256, name)
        out[name] = dest
    return out


def check_pair(pair, registry):
    """Each arm's registry ID, after the pair's model and its input and output prices are checked
    against the registry's."""
    if pair.get("format") != "routerbench-openai-pair-v1":
        raise ValueError(f"pair.json: format {pair.get('format')!r}, expected 'routerbench-openai-pair-v1'")
    ids = {}
    for arm in ARMS:
        model = pair["arms"][arm]["model"]
        if VENDOR + model not in registry:
            raise ValueError(f"pair.json: the {arm} model {model!r} is not in the registry as {VENDOR + model!r}")
        listed, prices = registry.get(VENDOR + model), pair["prices_usd_per_million"][model]
        found = (float(prices["input"]), float(prices["output"]))
        if found != (listed.price_in, listed.price_out):
            raise ValueError(f"pair.json: {model} prices {found} are not the registry's "
                             f"{(listed.price_in, listed.price_out)}")
        ids[arm] = listed.id
    return ids


def outcomes(grades, split, ids):
    """One Outcome per arm and row of a graded split, its task `<dataset>/<task>` with each space of
    the task made an underscore."""
    if grades.get("format") != "routerbench-paired-grades-v1" or grades.get("split") != split:
        raise ValueError(f"{split}: format {grades.get('format')!r} split {grades.get('split')!r}, expected "
                         f"'routerbench-paired-grades-v1' {split!r}")
    seen, found = set(), []
    for row in grades["rows"]:
        if row.get("role") != split or row["id"] in seen:
            raise ValueError(f"{split}: row {row.get('id')!r} has role {row.get('role')!r} or is repeated")
        seen.add(row["id"])
        task = f"{row['dataset']}/{row['task'].replace(' ', '_')}"
        for arm in ARMS:
            correct, cost = row[f"{arm}_correct"], row[f"{arm}_cost_usd"]
            if type(correct) is not int or correct not in (0, 1) or isinstance(cost, bool) \
                    or not isinstance(cost, (int, float)) or not math.isfinite(cost) or cost < 0:
                raise ValueError(f"{split}: row {row['id']!r}: {arm} correct {correct!r} cost {cost!r}")
            found.append(Outcome(task, row["id"], ids[arm], correct == 1, float(cost)))
    return found


def release_split(calibration, final, config):
    """Each task's (calibration, final) items and the evaluator's cells and summary on that split."""
    both = {o.item for o in calibration} & {o.item for o in final}
    if both:
        raise ValueError(f"{len(both)} items are in both splits, such as {min(both)!r}")
    table, items = {}, {}
    for part, rows in (("calibration", calibration), ("final", final)):
        for o in rows:
            by_model = table.setdefault((o.task, o.item), {})
            if o.model in by_model:
                raise ValueError(f"repeated outcome for task {o.task!r}, item {o.item!r}, model {o.model!r}")
            by_model[o.model] = o
            items.setdefault(o.task, {"calibration": set(), "final": set()})[part].add(o.item)
    models = sorted({o.model for o in calibration} | {o.model for o in final})
    for (task, item), by_model in sorted(table.items()):
        if len(by_model) != len(models):
            raise ValueError(f"incomplete matrix: task {task!r}, item {item!r}")
    tasks = sorted(items)
    splits, sums = {}, {}
    for task in tasks:
        cal, held = tuple(sorted(items[task]["calibration"])), tuple(sorted(items[task]["final"]))
        if not cal or not held:
            raise ValueError(f"task {task!r}: the calibration or final split is empty")
        splits[task] = (cal, held)
        sums[task, SEED] = _split_sums(table, models, task, cal, held)
    strategies = _strategies(models)
    cells = [_cell(sums[task, SEED], models, strategies, task, bar, flavor, SEED,
                   config["min_samples"], config["confidence"])
             for bar in config["bars"] for flavor in config["flavors"] for task in tasks]
    summary = _summary(cells, sums, config["bars"], config["flavors"], [SEED], tasks, strategies)
    return models, tasks, splits, sums, cells, summary


def _row(summary, bar, flavor, strategy):
    rows = [r for r in summary if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    if len(rows) != 1:
        raise ValueError(f"{len(rows)} summary rows for {(bar, flavor, strategy)}")
    return rows[0]


def families(grades):
    """The split's question count and its set of `family` values."""
    return len(grades["rows"]), {row["family"] for row in grades["rows"]}


def report(pair, ids, grades_calibration, grades_final, config):
    calibration = outcomes(grades_calibration, "calibration", ids)
    final = outcomes(grades_final, "final", ids)
    models, tasks, splits, sums, cells, summary = release_split(calibration, final, config)
    cheap, strong = ids["cheap"], ids["strong"]
    floor, confidence = config["min_samples"], config["confidence"]
    lines = [f"{REPO} at {REVISION[:7]} (grades-calibration.json calibrates, grades-final.json scores): "
             f"{len(tasks)} tasks, {len(models)} models, bars " + " ".join(str(b) for b in config["bars"])
             + f", min_samples {floor}, confidence {confidence} ({CONFIG} config)"]
    for arm in ARMS:
        model = pair["arms"][arm]["model"]
        p = pair["prices_usd_per_million"][model]
        lines.append(f"  {arm}: {ids[arm]} at {p['input']} and {p['output']} USD per million input and output "
                     f"tokens, the registry's prices, reasoning {pair['arms'][arm]['settings']['reasoning']['effort']}")
    (n_cal, fam_cal), (n_final, fam_final) = families(grades_calibration), families(grades_final)
    lines.append(f"  families: calibration {n_cal:,} questions in {len(fam_cal):,}, final {n_final:,} in "
                 f"{len(fam_final):,}, {len(fam_cal & fam_final)} in both splits")
    lines.append(f"  {'task':<44} cal  final  below min_samples  cheap right  strong right  cheap bound  strong bound")
    for task in tasks:
        cal, held = splits[task]
        succ = sums[task, SEED]["succ"]
        b = [wilson_lower_bound(succ[m], len(cal), confidence) for m in (cheap, strong)]
        lines.append(f"  {task:<44}{len(cal):>4}{len(held):>7}  {'yes' if len(cal) < floor else 'no':<17}"
                     f"  {succ[cheap]:>11}  {succ[strong]:>12}  {b[0]:>11.3f}  {b[1]:>12.3f}")
    lines.append(f"  {'all':<44}{sum(len(c) for c, _ in splits.values()):>6,}"
                 f"{sum(len(h) for _, h in splits.values()):>6,}")
    first = (config["bars"][0], config["flavors"][0])
    lines.append("  single models on the final split, held-out success and cost (USD):")
    for m in models:
        r = _row(summary, *first, f"model:{m}")
        lines.append(f"    {m:<20} {r['success']:.3f}  {r['cost_usd']:.6f}")
    strong_row = _row(summary, *first, f"model:{strong}")
    for s in ("oracle", "best_on_calibration", "cheapest"):
        r = _row(summary, *first, s)
        lines.append(f"  {s}: {r['success']:.3f} at {r['cost_usd'] / strong_row['cost_usd']:.3f} of {strong}'s cost")
    lines.append("  bar  flavor          routed  cost (USD)  cost / strong  cleared   tasks on cheap  "
                 "cleared below the bar on final")
    for flavor in config["flavors"]:
        for bar in config["bars"]:
            r = _row(summary, bar, flavor, "routed")
            group = [x for x in cells if (x["bar"], x["flavor"]) == (bar, flavor)]
            cleared = sum(x["cleared"] for x in group)
            on_cheap = sum(x["models"]["routed"] == cheap for x in group)
            under = sum(x["cleared"] and x["success"]["routed"] < bar for x in group)
            lines.append(f"  {bar:<4} {flavor:<15} {r['success']:.3f}   {r['cost_usd']:<11.6f} "
                         f"{r['cost_usd'] / strong_row['cost_usd']:<14.3f} {cleared:>2} of {len(tasks)}  {on_cheap:>14}  "
                         f"{under:>2}")
    lines.append(f"  tasks routed to {cheap} (* cleared, else the best available fallback):")
    for flavor in config["flavors"]:
        for bar in config["bars"]:
            picks = [f"{x['task']}{'*' if x['cleared'] else ''}" for x in cells
                     if (x["bar"], x["flavor"]) == (bar, flavor) and x["models"]["routed"] == cheap]
            lines.append(f"    {bar} {flavor}: " + (", ".join(picks) if picks else "none"))
    return lines


def main(argv=None):
    parser = argparse.ArgumentParser(prog="registry_pair.py", description=__doc__.splitlines()[0])
    parser.add_argument("--cache", type=Path, help="folder for the pinned files (default: the evidence cache)")
    parser.add_argument("--root", type=Path, default=ROOT, help="repository root (default: this checkout)")
    args = parser.parse_args(argv)
    try:
        paths = fetch(args.cache if args.cache is not None else default_cache_dir())
        read = {name: json.loads(path.read_text(encoding="utf-8")) for name, path in paths.items()}
        with open(args.root / CONFIG, encoding="utf-8") as fh:
            config = json.load(fh)["config"]
        registry = Registry.load(args.root / "model_routing" / "data" / "models.json")
        pair = read["pair.json"]
        ids = check_pair(pair, registry)
        lines = report(pair, ids, read["recordings/grades-calibration.json"],
                       read["recordings/grades-final.json"], config)
    except (OSError, ValueError, KeyError, TypeError, AttributeError, ZeroDivisionError) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    print("\n".join(lines))
    return 0


if __name__ == "__main__":
    sys.exit(main())
