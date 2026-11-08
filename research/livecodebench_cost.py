"""How long are the LiveCodeBench outputs, and what would a cost read from their length miss?

Usage: python research/livecodebench_cost.py [--cache DIR]

Reads the 67 pinned LiveCodeBench files that evidence/livecodebench/convert.py downloads, each
checked by size and sha256 before it is read, one at a time, and prints over the question ids
every file has: the length of the problem text; per model, the median characters of the first
sample's output (the sample the label reads), the share of first samples that hold a `</think>`
marker and the output tokens a text-length method gives at CHARS_PER_TOKEN characters per token;
and, for each model run at more than one reasoning setting, those medians side by side.
Standard library only. Read by research/livecodebench-cost.md.
"""

from __future__ import annotations

import argparse
import importlib.util
import re
import statistics
import sys
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
CONVERT = _ROOT / "evidence" / "livecodebench" / "convert.py"
# "1 token is approximately 4 characters", a rough estimate for English text, read 2026-11-08 at
# https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them
CHARS_PER_TOKEN = 4
MARKER = "</think>"
# a folder name ending in a parenthesised reasoning setting, as "O4-Mini (High)" or "Claude-Opus-4 (Thinking)"
SETTING = re.compile(r"(?P<base>.+?) \((?P<setting>Thinking|High|Med|Medium|Low)\)")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def reduce_file(records, folder: str) -> dict:
    """Per question id: the problem text's length, the first sample's output length and whether it holds MARKER.

    An output_list that is the empty string "" is a record with no output text, whatever its label: 47
    records over all ids hold one, in three files, and 3 of them are on the ids every file has, all in
    one file. It counts as 0 characters, flagged so that report() can count them. Any other output_list
    that is not a list starting with a string is a ValueError."""
    if not isinstance(records, list) or not records:
        raise ValueError(f"{folder}: the file must hold a non-empty list of problems")
    cells = {}
    for i, rec in enumerate(records):
        qid = rec.get("question_id") if isinstance(rec, dict) else None
        if not isinstance(qid, str) or not qid or qid in cells:
            raise ValueError(f"{folder}: entry {i} has no question_id string, or it repeats")
        text, outputs = rec.get("question_content"), rec.get("output_list")
        if not isinstance(text, str):
            raise ValueError(f"{folder}: question_id {qid}: question_content is not a string")
        if outputs == "":
            cells[qid] = (len(text), 0, False, True)
        elif not isinstance(outputs, list) or not outputs or not isinstance(outputs[0], str):
            raise ValueError(f"{folder}: question_id {qid}: output_list has no first sample string")
        else:
            cells[qid] = (len(text), len(outputs[0]), MARKER in outputs[0], False)
    return cells


def _median(values) -> int:
    return round(statistics.median(values))


def report(reduced: dict, model_of) -> list:
    """Lines for {folder: reduce_file(...)}; model_of maps a folder to its `vendor/model` id."""
    folders = sorted(reduced)
    common = sorted(set.intersection(*(set(reduced[f]) for f in folders)))
    empty = {f: sum(reduced[f][q][3] for q in common) for f in folders}
    first = reduced[folders[0]]
    prompt = [first[q][0] for q in common]
    differ = sum(any(reduced[f][q][0] != first[q][0] for q in common) for f in folders)
    lines = [
        f"{len(folders)} files, {len(common):,} question ids in every file",
        f"problem text: median {_median(prompt):,} characters, from {min(prompt):,} to {max(prompt):,}; "
        f"files whose text differs from {folders[0]}'s on some id: {differ}",
        f"first samples recorded as an empty string, counted as 0 characters: {sum(empty.values())} "
        f"(in {sum(n > 0 for n in empty.values())} files)",
        f"output tokens estimated at {CHARS_PER_TOKEN} characters per token",
        "",
        f"{'model':<45}  {'median_output_chars':>19}  {'think_marker':>12}  {'est_output_tokens':>17}",
        f"{'-' * 45}  {'-' * 19}  {'-' * 12}  {'-' * 17}",
    ]
    medians = {}
    for f in sorted(folders, key=model_of):
        out = [reduced[f][q][1] for q in common]
        marked = sum(reduced[f][q][2] for q in common) / len(common)
        medians[f] = _median(out)
        lines.append(f"{model_of(f):<45}  {medians[f]:>19,}  {marked:>12.3f}  "
                     f"{round(statistics.median(out) / CHARS_PER_TOKEN):>17,}")
    marked_half = sum(sum(reduced[f][q][2] for q in common) * 2 >= len(common) for f in folders)
    lo, hi = min(medians.values()), max(medians.values())
    lines += ["", f"models with the marker in at least half their first samples: {marked_half} of {len(folders)}",
              f"median output characters per model: from {lo:,} to {hi:,} ({hi / lo:.1f} times)", "",
              "runs of one model at more than one reasoning setting (median output characters):"]
    groups = {}
    for f in folders:
        m = SETTING.fullmatch(f)
        if m:
            groups.setdefault(m.group("base"), {})[m.group("setting")] = f
    for base in sorted(groups):
        runs = dict(groups[base])
        if base in reduced:
            runs["none"] = base
        if len(runs) < 2:
            continue
        cells = sorted(runs.items(), key=lambda kv: medians[kv[1]])
        shown = "  ".join(f"{setting} {medians[f]:,}" for setting, f in cells)
        ratio = medians[cells[-1][1]] / medians[cells[0][1]]
        lines.append(f"  {base}: {shown} (longest over shortest {ratio:.2f})")
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", default=None, help="download folder (default: the converter's)")
    args = parser.parse_args(argv)
    convert = _load(CONVERT, "livecodebench_convert")
    try:
        root = convert.fetch(args.cache)
        reduced = {}
        for name in convert.FILES:
            folder = name.split("/")[0]
            reduced[folder] = reduce_file(convert.read_file(root / name), folder)
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(report(reduced, convert.model_id)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
