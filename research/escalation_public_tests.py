"""Can a failed LiveCodeBench sample's failing test be matched against its problem's public test cases?

Usage: python research/escalation_public_tests.py [--cache DIR]

Reads SAMPLE, release files of the problems (livecodebench/code_generation_lite at RELEASE_REVISION,
pinned by bytes and sha256 in RELEASE_FILES), downloaded into DIR/release, and the runner's two files at
RUNNER_REVISION (RUNNER_FILES), downloaded into DIR/runner, DIR being the 12.16 converter's cache folder
unless --cache names another; then the 67 kept submission files the converter downloads, each file
checked by size and sha256 before it is read. From a release line it reads only question_id,
contest_date, metadata and public_test_cases; the private cases, a base64 zlib pickle, are never
decoded. The runner lists a problem's public cases before its private ones and records the first
failing case through truncatefn: as raw text for a standard-input problem, and for a call-based one (its
metadata names a func_name) as str() of the JSON-parsed input lines and output. So a failed first sample
whose recorded inputs and expected equal one public case's recorded form failed that public case, and
one that matches none passed every public case and failed a private one. Prints, per kept file, the sample problems, the failed first samples and how each was
matched. Standard library only. Read by research/escalation.md (DESIGN 7 v1.534, row ESC1c).
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import statistics
import sys
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
CONVERT = _ROOT / "evidence" / "livecodebench" / "convert.py"
RELEASE_REPO = "livecodebench/code_generation_lite"
RELEASE_REVISION = "0fe84c3912ea0c4d4a78037083943e8f0c4dd505"
# file: (bytes, sha256) at RELEASE_REVISION, the Hugging Face tree API's LFS size and oid, read 2026-11-20
RELEASE_FILES = {
    "test.jsonl": (1252609773, "2bd02b38beb48e8c46b5b9987095d999ff38cd8efc255ea5d58974317c48f63f"),
    "test2.jsonl": (713377060, "095df7c5daf15f882c51a9deb84085cff1e073495a5dbcf95015a564d485f3a3"),
    "test3.jsonl": (623360766, "28ed26cc83363ce3f1fe2d5fad9f8393077beb1907b167a31bd3b32f80801b79"),
    "test4.jsonl": (1204644685, "d711138ddaebfcf5f8ec6a4283ee677298c0f5c5d374a235af92aaf0584510da"),
    "test5.jsonl": (557699297, "7f77571c2a6df0c2a72a3277650309f67e01e0008e18117e624633df53f81214"),
    "test6.jsonl": (134303240, "bb4c364f71921c4495a6ad15abe1a927350b720009f4933e2e71f8af0f6fd1f5"),
}
SAMPLE = ("test3.jsonl",)
RUNNER_REPO = "LiveCodeBench/LiveCodeBench"
RUNNER_REVISION = "28fef95ea8c9f7a547c8329f2cd3d32b92c1fa24"
# path: (bytes, sha256) at RUNNER_REVISION, read 2026-11-20
RUNNER_FILES = {
    "lcb_runner/benchmarks/code_generation.py": (4688, "0bc93f5a650b55d6a1b54d3db852d80ae64891ece4ff085b2e6b469eb89f8846"),
    "lcb_runner/evaluation/testing_util.py": (18276, "b7cb6a8a69807bb868150a61742e25d7bb5328bbe01d514471b6ec43c9fa9ed2"),
}
ORDER_LINE = "for t in self.public_test_cases + self.private_test_cases"
FN_NAME_LINE = '"fn_name": self.metadata.get("func_name", None)'
TRUNCATE_LINE = "def truncatefn(s, length=300):"
# grade_call_based parses each case before it runs it, and records the parsed values (review iter-379 must-fix 1)
PARSE_LINES = ('[json.loads(line) for line in inputs.split("\\n")] for inputs in all_inputs',
               "all_outputs = [json.loads(output) for output in all_outputs]")
LENGTH = 300
TIMEOUT = 60
KINDS = ("public", "other", "input_only", "no_test", "unread")
COLUMNS = ("problems", "failed") + KINDS
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})(T.*)?")


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def truncate(s, length: int = LENGTH) -> str:
    """The runner's truncatefn: str(s) when it is no longer than `length`, else its first length // 2
    characters, "...(truncated) ..." and its slice from -length // 2 on."""
    s = s if isinstance(s, str) else str(s)
    if len(s) <= length:
        return s
    return s[: length // 2] + "...(truncated) ..." + s[-length // 2:]


def _download(url: str, target: Path, size: int, sha256: str, convert) -> Path:
    if target.exists():
        convert.verify(target, size, sha256)
        return target
    target.parent.mkdir(parents=True, exist_ok=True)
    part = target.with_name(target.name + ".part")
    try:
        try:
            with urllib.request.urlopen(url, timeout=TIMEOUT) as response, open(part, "wb") as out:
                for block in iter(lambda: response.read(1 << 20), b""):
                    out.write(block)
        except Exception as exc:
            raise OSError(f"{target.name}: download failed: {exc}") from exc
        convert.verify(part, size, sha256)  # a mismatch is the converter's ValueError, not a download failure
        part.replace(target)
    finally:
        part.unlink(missing_ok=True)
    return target


def fetch_release(folder, names, convert) -> dict:
    """{name: path} for each named RELEASE_FILES file, under `folder`/release, verified; the release half
    of fetch, which the LiveCodeBench cascade replay calls for its four files (DESIGN 7 v1.551)."""
    folder = Path(folder)
    paths = {}
    for name in names:
        size, sha256 = RELEASE_FILES[name]
        url = f"https://huggingface.co/datasets/{RELEASE_REPO}/resolve/{RELEASE_REVISION}/{name}"
        paths[name] = _download(url, folder / "release" / name, size, sha256, convert)
    return paths


def fetch(folder, convert) -> dict:
    """{name: path} for each SAMPLE release file and each RUNNER_FILES file, under `folder`, verified."""
    folder = Path(folder)
    paths = fetch_release(folder, SAMPLE, convert)
    for name, (size, sha256) in RUNNER_FILES.items():
        url = f"https://raw.githubusercontent.com/{RUNNER_REPO}/{RUNNER_REVISION}/{name}"
        paths[name] = _download(url, folder / "runner" / name.rsplit("/", 1)[1], size, sha256, convert)
    return paths


def check_runner(sources: dict) -> None:
    """A ValueError unless code_generation.py lists the public cases first in both lists of
    get_evaluation_sample and takes fn_name from the problem's func_name, and testing_util.py truncates
    at 300 characters and parses a call-based case's input lines and output as JSON."""
    generation = sources["lcb_runner/benchmarks/code_generation.py"]
    if generation.count(ORDER_LINE) != 2:
        raise ValueError(f"code_generation.py: {ORDER_LINE!r} is not there twice")
    if generation.count(FN_NAME_LINE) != 1:
        raise ValueError(f"code_generation.py: {FN_NAME_LINE!r} is not there once")
    testing = sources["lcb_runner/evaluation/testing_util.py"]
    for line in (TRUNCATE_LINE,) + PARSE_LINES:
        if testing.count(line) != 1:
            raise ValueError(f"testing_util.py: {line!r} is not there once")


def _is_case(value) -> bool:
    return isinstance(value, dict) and isinstance(value.get("input"), str) and isinstance(value.get("output"), str)


def recorded(case: dict, call_based: bool, at: str) -> tuple:
    """(inputs, expected) as the runner records one public case: truncate of the raw text for a
    standard-input problem; for a call-based one truncate of str() of the list of its JSON-parsed input
    lines and of its JSON-parsed output, as grade_call_based parses them."""
    if not call_based:
        return truncate(case["input"]), truncate(case["output"])
    try:
        args = [json.loads(line) for line in case["input"].split("\n")]
        want = json.loads(case["output"])
    except ValueError as exc:
        raise ValueError(f"{at}: a call-based public case is not JSON ({exc})") from exc
    return truncate(str(args)), truncate(str(want))


def read_release(lines, label: str) -> dict:
    """{question_id: {"date": "YYYY-MM-DD", "call_based": bool, "cases": [(inputs, expected), ...]}},
    sorted, the cases in their recorded form, from the lines of one release file; only question_id,
    contest_date, metadata and public_test_cases are read. A problem is call-based when its metadata
    names a func_name; its cases' testtype must then be functional, and stdin otherwise. An empty
    public_test_cases list is a problem with no public case, read with cases [] (DESIGN 7 v1.552)."""
    problems = {}
    for k, line in enumerate(lines, 1):
        at = f"{label} line {k}"
        try:
            record = json.loads(line)
        except ValueError as exc:
            raise ValueError(f"{at}: not valid JSON ({exc})") from exc
        if not isinstance(record, dict):
            raise ValueError(f"{at}: not an object")
        qid = record.get("question_id")
        if not isinstance(qid, str) or not qid:
            raise ValueError(f"{at}: no question_id string")
        if qid in problems:
            raise ValueError(f"{at}: question_id {qid} repeats")
        date = record.get("contest_date")
        found = DATE.fullmatch(date) if isinstance(date, str) else None
        if found is None:
            raise ValueError(f"{at}: question_id {qid}: contest_date {date!r} is not a date")
        try:
            cases = json.loads(record.get("public_test_cases"))
        except (TypeError, ValueError):
            cases = None
        if not isinstance(cases, list) or not all(_is_case(c) for c in cases):  # [] is no public case (v1.552)
            raise ValueError(f"{at}: question_id {qid}: public_test_cases is not a JSON list of input and "
                             "output strings")
        try:
            meta = json.loads(record.get("metadata"))
        except (TypeError, ValueError):
            meta = None
        if not isinstance(meta, dict):
            raise ValueError(f"{at}: question_id {qid}: metadata is not a JSON object string")
        name = meta.get("func_name")
        if name is not None and (not isinstance(name, str) or not name):
            raise ValueError(f"{at}: question_id {qid}: func_name {name!r} is not a non-empty string")
        call_based = name is not None
        kind = "functional" if call_based else "stdin"
        if any(c.get("testtype") != kind for c in cases):
            raise ValueError(f"{at}: question_id {qid}: a public case's testtype is not {kind!r}")
        problems[qid] = {"date": found.group(1), "call_based": call_based,
                         "cases": [recorded(c, call_based, f"{at}: question_id {qid}") for c in cases]}
    if not problems:
        raise ValueError(f"{label}: no problem")
    return dict(sorted(problems.items()))


def first_metadata(record: dict, at: str):
    """The first sample's metadata entry as an object, or None when the record's metadata is absent or not
    a non-empty list."""
    listed = record.get("metadata")
    if not isinstance(listed, list) or not listed:
        return None
    entry = listed[0]
    if isinstance(entry, str):
        try:
            entry = json.loads(entry)
        except ValueError as exc:
            raise ValueError(f"{at}: metadata entry 0 is not valid JSON") from exc
    if not isinstance(entry, dict):
        raise ValueError(f"{at}: metadata entry 0 is not an object")
    return entry


def classify(meta, cases: list, at: str) -> tuple:
    """(kind, the 0-based index of the matched public case or None) for one failed first sample."""
    if meta is None:
        return "unread", None
    if "inputs" not in meta:
        return "no_test", None
    given, wanted = meta["inputs"], meta.get("expected")
    if not isinstance(given, str) or not isinstance(wanted, str):
        raise ValueError(f"{at}: the failing test's inputs and expected are not both strings")
    for k, (inp, out) in enumerate(cases):
        if given == inp and wanted == out:
            return "public", k
    if any(given == inp for inp, _ in cases):
        return "input_only", None
    return "other", None


def reduce_file(records, folder: str, release: dict, convert) -> dict:
    """One parsed kept file: its model, its question ids, and over the release problems it holds the
    counts of COLUMNS and the public matches by case index. The labels are convert.extract's."""
    extract = convert.extract(records, folder)
    counts = dict.fromkeys(COLUMNS, 0)
    index = {}
    for record in records:
        qid = record["question_id"]
        if qid not in release:
            continue
        counts["problems"] += 1
        if extract["cells"][qid]["correct"]:
            continue
        counts["failed"] += 1
        at = f"{folder}: question_id {qid}"
        kind, k = classify(first_metadata(record, at), release[qid]["cases"], at)
        counts[kind] += 1
        if k is not None:
            index[k] = index.get(k, 0) + 1
    return {"model": extract["model"], "items": set(extract["cells"]), "counts": counts,
            "index": dict(sorted(index.items()))}


def _share(part: int, whole: int) -> str:
    return f"{part / whole:.3f}" if whole else "n/a"


def report(rows: list, release: dict, revisions: tuple, sample=SAMPLE) -> list:
    """Lines for the reduce_file dicts of every kept file and the read_release dict of the sample;
    `revisions` is (release, runner, submissions)."""
    rows = sorted(rows, key=lambda r: r["model"])
    common = set.intersection(*(r["items"] for r in rows))
    cases = [len(p["cases"]) for p in release.values()]
    dates = sorted(p["date"] for p in release.values())
    called = sum(p["call_based"] for p in release.values())
    width = max([len("model"), len("all")] + [len(r["model"]) for r in rows])
    heads = COLUMNS + ("public_share", "public_of_tested")
    lines = [
        f"problem release {RELEASE_REPO} at {revisions[0]}, read: {', '.join(sample)}",
        f"runner {RUNNER_REPO} at {revisions[1]}: public cases before private ones (get_evaluation_sample), "
        f"the failing case recorded by truncatefn at {LENGTH} characters",
        f"submissions at {revisions[2]}: {len(rows)} kept files, {len(common)} problems in every one "
        "(the 12.16 kept problems)",
        f"sample problems: {len(release)}, contest dates {dates[0]} to {dates[-1]}, public cases per problem "
        f"{min(cases)} to {max(cases)} (median {statistics.median(cases):g}), among the 12.16 kept problems: "
        f"{len(common & set(release))}",
        f"call-based (a func_name, cases recorded parsed): {called}, standard input (recorded as text): "
        f"{len(release) - called}",
        "",
        f"{'model':<{width}}" + "".join(f"  {h}" for h in heads),
        f"{'-' * width}" + "".join(f"  {'-' * len(h)}" for h in heads),
    ]
    total = dict.fromkeys(COLUMNS, 0)
    index = {}
    for name, counts in [(r["model"], r["counts"]) for r in rows] + [("all", total)]:
        if name != "all":
            for key in COLUMNS:
                total[key] += counts[key]
        tested = counts["public"] + counts["other"] + counts["input_only"]
        cells = [f"{counts[key]:,}" for key in COLUMNS]
        cells += [_share(counts["public"], counts["failed"]), _share(counts["public"], tested)]
        lines.append(f"{name:<{width}}" + "".join(f"  {c:>{len(h)}}" for c, h in zip(cells, heads)))
    for r in rows:
        for k, n in r["index"].items():
            index[k] = index.get(k, 0) + n
    matched = ", ".join(f"{k}: {n:,}" for k, n in sorted(index.items())) or "none"
    lines += ["", f"public matches by the 0-based index of the matched case: {matched}"]
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", default=None, help="download folder (default: the converter's)")
    args = parser.parse_args(argv)
    try:
        convert = _load(CONVERT, "livecodebench_convert")
        folder = convert.fetch(args.cache)
        paths = fetch(folder, convert)
        check_runner({name: paths[name].read_text(encoding="utf-8") for name in RUNNER_FILES})
        release = {}
        for name in SAMPLE:
            with open(paths[name], "rb") as f:
                part = read_release(f, name)
            if set(part) & set(release):
                raise ValueError(f"{name}: a question_id is in two sample files")
            release.update(part)
        release = dict(sorted(release.items()))
        rows = [reduce_file(convert.read_file(folder / name), name.split("/")[0], release, convert)
                for name in convert.FILES]
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(report(rows, release, (RELEASE_REVISION, RUNNER_REVISION, convert.REVISION))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
