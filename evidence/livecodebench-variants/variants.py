"""Route LiveCodeBench's runs of one model at two or more reasoning settings as variants of that model
(DESIGN 12.32 v1.575).

Standard library only. The submissions hold some models at several reasoning settings, each in a folder
named ``<base> (<setting>)``, and the 12.16 converter gives each run a model ID of its own, so a
router keyed by those IDs already keeps their stats apart, but as unrelated models. This script names
them as the library names a measured setup (DESIGN 4.1 v1.572): a route of the model,
``vendor/model@variant``, where the variant is ``low``, ``medium`` (``Med`` or ``Medium``), ``high`` or
``thinking``, and a folder named the base alone is the base route. It reads the converter's JSONL
matrix and writes the rows of those runs only, each renamed to its route, every other key and value
kept; a model with one run is left out. It loads the 12.16 converter and
research/livecodebench_cost.py by path, for ``model_id``, ``FILES`` and ``SETTING``.

    python evidence/livecodebench/convert.py --out livecodebench-matrix.jsonl
    python evidence/livecodebench-variants/variants.py --matrix livecodebench-matrix.jsonl \\
        --out livecodebench-variants.jsonl
"""

import argparse
import importlib.util
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parents[1]


def _load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


convert = _load(_ROOT / "evidence" / "livecodebench" / "convert.py", "livecodebench_convert_for_variants")
cost_research = _load(_ROOT / "research" / "livecodebench_cost.py", "livecodebench_cost_for_variants")

# a submission folder's setting and the variant name of its route (DESIGN 12.32)
VARIANT = {"Low": "low", "Med": "medium", "Medium": "medium", "High": "high", "Thinking": "thinking"}


def routes(folders) -> dict:
    """Each run's 12.16 model ID and its route ID, for every base with two or more runs, sorted by run ID."""
    folders = list(folders)
    seen = set()
    for folder in folders:
        if folder in seen:
            raise ValueError(f"folder {folder!r} is repeated")
        seen.add(folder)
    groups = {}
    for folder in folders:
        found = cost_research.SETTING.fullmatch(folder)
        if found:
            groups.setdefault(found.group("base"), []).append((VARIANT[found.group("setting")], folder))
    out = {}
    for base in sorted(groups):
        runs = list(groups[base])
        if base in seen:
            runs.append((None, base))
        if len(runs) < 2:
            continue
        named = {}
        for variant, folder in runs:
            if variant in named:
                raise ValueError(f"{base}: {named[variant]!r} and {folder!r} are both {variant}")
            named[variant] = folder
        model = convert.model_id(base)
        for variant, folder in runs:
            out[convert.model_id(folder)] = model if variant is None else f"{model}@{variant}"
    if len(set(out.values())) != len(out):
        raise ValueError("two runs map to one route")
    return dict(sorted(out.items()))


def variant_rows(rows, table) -> list:
    """The rows whose ``model`` is a run of ``table``, in input order, each a new dict naming its route."""
    return [dict(row, model=table[row["model"]]) for row in rows
            if isinstance(row.get("model"), str) and row["model"] in table]


def read_matrix(path) -> list:
    rows = []
    with open(path, encoding="utf-8") as f:
        for number, line in enumerate(f, 1):
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                raise ValueError(f"{path} line {number} is not JSON") from None
            if not isinstance(row, dict):
                raise ValueError(f"{path} line {number} is not a JSON object")
            rows.append(row)
    return rows


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(prog="variants.py", description="LiveCodeBench runs at reasoning settings as "
                                     "variant routes of their models (DESIGN 12.32)")
    parser.add_argument("--matrix", required=True, help="the 12.16 converter's JSONL matrix")
    parser.add_argument("--out", required=True, help="output JSONL path")
    args = parser.parse_args(argv)
    try:
        table = routes(name.split("/")[0] for name in convert.FILES)
        out_rows = variant_rows(read_matrix(args.matrix), table)
        if not out_rows:
            raise ValueError(f"{args.matrix} holds no run of the {len(table)} routes")
        Path(args.out).write_text("".join(json.dumps(row) + "\n" for row in out_rows), encoding="utf-8")
    except (ValueError, OSError) as exc:
        msg = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {msg}", file=sys.stderr)
        return 2
    models = {route.split("@")[0] for route in table.values()}
    print(f"{len(out_rows)} rows, {len(table)} routes of {len(models)} models")
    return 0


if __name__ == "__main__":
    sys.exit(main())
