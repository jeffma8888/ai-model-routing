"""Turn the per-judge grades of AutoBench Router Benchmark 2026 into a judge outcome matrix (DESIGN 12.11).

Usage: python evidence/autobench-2026/judges.py --out PATH [--cache DIR] [--registry PATH]
                                                [--tolerance T] [--candidates A,B,...] [--size K]
                                                [--min-committee N] [--rubric-tokens N] [--grade-tokens N]
                                                [--task-by {domain,all}] [--answer-tokens {visible,output}]

Standard library only. The pinned files, their checks and the download are those of
convert.py in this folder, loaded from its path, never copied. An item is one graded answer
(a question and the model that answered it), a model is a candidate judge, and a judge is
correct when its grade is within ``tolerance`` of the mean of the other judges' grades on that
answer: a leave-one-out committee label, not a human gold label. Rows carry estimated token
counts and no cost, so ``model-routing evaluate --registry`` prices them at the pool's list prices.
By default the judge reads the visible answer, the cell's output tokens less its reasoning tokens.
"""

from __future__ import annotations

import argparse
import csv
import importlib.util
import itertools
import json
import math
import sys
from pathlib import Path


def _load_convert():
    path = Path(__file__).resolve().with_name("convert.py")
    spec = importlib.util.spec_from_file_location("autobench_convert", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


convert = _load_convert()

DEFAULT_TOLERANCE = 0.5
DEFAULT_SIZE = 5
DEFAULT_MIN_COMMITTEE = 3
DEFAULT_RUBRIC_TOKENS = 400
DEFAULT_GRADE_TOKENS = 200
ANSWER_TOKENS = ("visible", "output")
DEFAULT_ANSWER_TOKENS = "visible"


def _is_number(value) -> bool:
    return isinstance(value, (int, float)) and not isinstance(value, bool)


def _whole(value, what: str, low: int) -> None:
    if isinstance(value, bool) or not isinstance(value, int) or value < low:
        raise ValueError(f"{what} must be an int >= {low}, got {value!r}")


def parse_grades(text, pid: str, model: str) -> dict:
    try:
        grades = json.loads(text) if isinstance(text, str) else None
    except ValueError:
        grades = None
    if not isinstance(grades, dict):
        raise ValueError(f"{pid}, {model}: judges_json {text!r} is not a JSON object")
    out = {}
    for judge, grade in grades.items():
        if not judge:
            raise ValueError(f"{pid}, {model}: judges_json has an empty judge name")
        if grade is None:
            continue
        if not _is_number(grade) or not math.isfinite(grade):
            raise ValueError(f"{pid}, {model}: judge {judge!r} grade {grade!r} is not a finite number or null")
        out[judge] = grade
    return out


def _fate(answer, graders, chosen, min_committee) -> str:
    if answer in chosen:
        return "self_graded"
    if not all(c in graders for c in chosen):
        return "missing_candidate"
    if sum(1 for j in graders if j != answer) - 1 < min_committee:
        return "small_committee"
    return "kept"


def judge_matrix(matrix, pool, tolerance=DEFAULT_TOLERANCE, candidates=None, size=DEFAULT_SIZE,
                 min_committee=DEFAULT_MIN_COMMITTEE, rubric_tokens=DEFAULT_RUBRIC_TOKENS,
                 grade_tokens=DEFAULT_GRADE_TOKENS, task_by="all", questions=None,
                 answer_tokens=DEFAULT_ANSWER_TOKENS):
    names = convert.pool_models(pool)
    if not _is_number(tolerance) or not math.isfinite(tolerance) or tolerance < 0:
        raise ValueError(f"tolerance must be a finite number >= 0, got {tolerance!r}")
    if candidates is not None:
        if not isinstance(candidates, (list, tuple)) or not candidates:
            raise ValueError(f"candidates must be a non-empty list of pool display IDs, got {candidates!r}")
        for c in candidates:
            if not isinstance(c, str) or c not in names:
                raise ValueError(f"candidate {c!r} is not a pool display ID")
        if len(set(candidates)) != len(candidates):
            raise ValueError(f"candidates repeat a display ID: {candidates!r}")
    _whole(size, "size", 1)
    _whole(min_committee, "min_committee", 1)
    _whole(rubric_tokens, "rubric_tokens", 0)
    _whole(grade_tokens, "grade_tokens", 0)
    if not isinstance(answer_tokens, str) or answer_tokens not in ANSWER_TOKENS:
        raise ValueError(f"answer_tokens must be one of {', '.join(ANSWER_TOKENS)}, got {answer_tokens!r}")
    if task_by not in convert.TASK_BY:
        raise ValueError(f"task_by must be one of {', '.join(convert.TASK_BY)}, got {task_by!r}")
    task_of = None
    if task_by == "domain":
        if not isinstance(questions, list):
            raise ValueError("task_by 'domain' needs the questions table")
        task_of = {}
        for q in questions:
            pid = q.get("prompt_id") if isinstance(q, dict) else None
            if not isinstance(pid, str) or not pid:
                raise ValueError(f"question {q!r} has no prompt_id")
            if pid in task_of:
                raise ValueError(f"question {pid!r} is repeated")
            domain = q.get("ddc_domain")
            if not isinstance(domain, str) or not domain:
                raise ValueError(f"question {pid!r} has no ddc_domain")
            task_of[pid] = domain
    seen, cells, out_of_pool, unscored = set(), [], {}, 0
    for r in matrix:
        pid, model = (r.get("prompt_id"), r.get("model")) if isinstance(r, dict) else (None, None)
        if not isinstance(pid, str) or not pid or not isinstance(model, str) or not model:
            raise ValueError(f"matrix row {r!r} needs a prompt_id and a model")
        if task_of is not None and pid not in task_of:
            raise ValueError(f"matrix row for {pid!r}, {model!r} names no question")
        if (pid, model) in seen:
            raise ValueError(f"matrix cell {pid!r}, {model!r} is repeated")
        seen.add((pid, model))
        if model not in names:
            out_of_pool[model] = out_of_pool.get(model, 0) + 1
            continue
        score = r.get("score")
        if score is None or score == "":
            unscored += 1
            continue
        graders = parse_grades(r.get("judges_json"), pid, model)
        prompt = convert._count(r.get("input_tokens"), "input_tokens", pid, model)
        read = convert._count(r.get("output_tokens"), "output_tokens", pid, model)
        if answer_tokens == "visible":
            read = max(read - convert._count(r.get("reasoning_tokens"), "reasoning_tokens", pid, model), 0)
        tokens = prompt + read
        cells.append((pid, model, graders, tokens))
    if candidates is None:
        judges = sorted({j for _, _, graders, _ in cells for j in graders if j in names})
        if size > len(judges):
            raise ValueError(f"size {size} is more than the {len(judges)} pool judges that grade a scored cell")
        best, chosen = -1, None
        for combo in itertools.combinations(judges, size):
            n = sum(1 for _, answer, graders, _ in cells if _fate(answer, graders, combo, min_committee) == "kept")
            if n > best:
                best, chosen = n, combo
        chosen, by = tuple(chosen), "most_cells"
    else:
        chosen, by = tuple(candidates), "given"
    rows, kept = [], {}
    dropped = {"self_graded": 0, "missing_candidate": 0, "small_committee": 0}
    self_graded_cells = 0
    for pid, answer, graders, tokens in cells:
        if answer in graders:
            self_graded_cells += 1
        fate = _fate(answer, graders, chosen, min_committee)
        if fate != "kept":
            dropped[fate] += 1
            continue
        task = task_of[pid] if task_of is not None else "all"
        kept[task] = kept.get(task, 0) + 1
        for judge in chosen:
            committee = [g for j, g in graders.items() if j != judge and j != answer]
            mean = math.fsum(committee) / len(committee)
            rows.append({"task": task, "item": f"{pid}|{names[answer]}", "model": names[judge],
                         "correct": abs(graders[judge] - mean) <= tolerance,
                         "input_tokens": tokens + rubric_tokens, "output_tokens": grade_tokens})
    rows.sort(key=lambda x: (x["task"], x["item"], x["model"]))
    report = {"candidates": sorted(names[c] for c in chosen), "candidates_by": by, "tolerance": tolerance,
              "min_committee": min_committee, "rubric_tokens": rubric_tokens, "grade_tokens": grade_tokens,
              "answer_tokens": answer_tokens, "task_by": task_by, "scored_cells": len(cells),
              "kept": dict(sorted(kept.items())),
              "dropped_self_graded": dropped["self_graded"],
              "dropped_missing_candidate": dropped["missing_candidate"],
              "dropped_small_committee": dropped["small_committee"], "self_graded_cells": self_graded_cells,
              "unscored_cells": unscored, "dropped_out_of_pool": dict(sorted(out_of_pool.items())),
              "rows": len(rows)}
    return rows, report


class _UsageError(Exception):
    pass


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise _UsageError(message)


def _tolerance(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        value = math.nan
    if not math.isfinite(value) or value < 0:
        raise argparse.ArgumentTypeError(f"{text!r} is not a finite number >= 0")
    return value


def _int_at_least(low: int):
    def parse(text: str) -> int:
        try:
            value = int(text)
        except ValueError:
            raise argparse.ArgumentTypeError(f"{text!r} is not an integer") from None
        if value < low:
            raise argparse.ArgumentTypeError(f"{text!r} is below {low}")
        return value
    return parse


def main(argv=None) -> int:
    parser = _Parser(prog="judges.py", description="AutoBench 2026 judge grades to a judge outcome matrix")
    parser.add_argument("--out", required=True, help="output JSONL path")
    parser.add_argument("--cache", default=None, help="download folder (default: that of convert.py)")
    parser.add_argument("--registry", default=None,
                        help="also write the models.json registry convert.py --registry writes")
    parser.add_argument("--tolerance", type=_tolerance, default=DEFAULT_TOLERANCE,
                        help="largest distance from the other judges' mean grade that counts as correct "
                             "(default: %(default)s)")
    parser.add_argument("--candidates", default=None,
                        help="comma-separated judge display IDs (default: the --size judges that keep the most cells)")
    parser.add_argument("--size", type=_int_at_least(1), default=DEFAULT_SIZE,
                        help="number of candidate judges when --candidates is not given (default: %(default)s)")
    parser.add_argument("--min-committee", type=_int_at_least(1), default=DEFAULT_MIN_COMMITTEE,
                        help="fewest other judges a kept answer needs (default: %(default)s)")
    parser.add_argument("--rubric-tokens", type=_int_at_least(0), default=DEFAULT_RUBRIC_TOKENS,
                        help="assumed judge prompt tokens beyond the question and answer (default: %(default)s)")
    parser.add_argument("--grade-tokens", type=_int_at_least(0), default=DEFAULT_GRADE_TOKENS,
                        help="assumed judge output tokens (default: %(default)s)")
    parser.add_argument("--task-by", choices=convert.TASK_BY, default="all",
                        help="task = one pooled judge task, or the question's domain (default: %(default)s)")
    parser.add_argument("--answer-tokens", choices=ANSWER_TOKENS, default=DEFAULT_ANSWER_TOKENS,
                        help="answer length a judge reads: output tokens less reasoning tokens, floored at 0, "
                             "or all output tokens (default: %(default)s)")
    try:
        args = parser.parse_args(argv)
        if args.registry is not None:
            paths = [p.resolve() for name in (args.out, args.registry)
                     for p in (Path(name), Path(name + ".part"))]
            if len(set(paths)) < len(paths):
                raise _UsageError("--registry and --out (or their .part files) name the same file")
        candidates = None
        if args.candidates is not None:
            candidates = args.candidates.split(",")
            if any(not c for c in candidates):
                raise _UsageError(f"--candidates {args.candidates!r} has an empty name")
        folder = convert.fetch(args.cache)
        pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
        questions = convert.read_csv(folder / "questions.csv") if args.task_by == "domain" else None
        rows, report = judge_matrix(convert.read_csv(folder / "matrix.csv"), pool, args.tolerance, candidates,
                                    args.size, args.min_committee, args.rubric_tokens, args.grade_tokens,
                                    args.task_by, questions, args.answer_tokens)
        registry = convert.pool_registry(pool) if args.registry is not None else None
        targets = [Path(args.out)] + ([Path(args.registry)] if registry is not None else [])
        parts = [t.with_name(t.name + ".part") for t in targets]
        try:
            convert.write_jsonl(rows, parts[0])
            if registry is not None:
                parts[1].write_text(json.dumps(registry, indent=2) + "\n", encoding="utf-8")
            # print before the renames, so a write to stdout that fails leaves --out and --registry as they were (v1.94)
            print(json.dumps(report, indent=2), flush=True)
            for part, target in zip(parts, targets):
                part.replace(target)
        finally:
            for part in parts:
                part.unlink(missing_ok=True)
    except (_UsageError, ValueError, OSError, csv.Error) as exc:
        message = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {message}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
