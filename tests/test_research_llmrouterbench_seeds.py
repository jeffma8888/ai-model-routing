"""research/llmrouterbench-seeds.md and research/llmrouterbench_seeds.py (DESIGN 12.8 v1.177).

The note's numbers are the script's lines on the LLMRouterBench matrix, compared byte for byte when
the pinned file is cached (the session fixture `llmrouterbench_pinned` of tests/conftest.py, which
CI never fills). The script's lines, its check against the committed results file and its exits
are tested on a small matrix.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import math
import re
import statistics
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "llmrouterbench_seeds.py"
NOTE = ROOT / "research" / "llmrouterbench-seeds.md"
INDEX = ROOT / "research" / "README.md"
PAYS = ROOT / "research" / "where-routing-pays.md"
RESULTS = "evidence/llmrouterbench/results.json"
COMMAND = "$ python research/llmrouterbench_seeds.py --matrix llmrouterbench-matrix.jsonl"
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl",
    COMMAND[2:],
]
# DESIGN section numbers: the only numbers of the note's prose not in the script's lines
ALLOWED = {"12.2", "12.3", "12.7", "12.8", "12.18", "12.19"}
NUMBER = re.compile(r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
CONFIG = {"bars": [0.5, 0.65], "seeds": list(range(6)), "flavors": ["cost_effective", "cost_blind"],
          "calibration_fraction": 0.5, "min_samples": 10, "confidence": 0.95}
# per task: (items, {model: (percent correct, cost per call)})
TINY = {"a": (120, {"v/x": (72, 0.03), "v/y": (55, 0.02), "v/z": (45, 0.001)}),
        "b": (100, {"v/x": (50, 0.03), "v/y": (66, 0.02), "v/z": (40, 0.001)})}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lrs():
    return _load("research_llmrouterbench_seeds", SCRIPT)


def tiny_rows():
    """Two tasks with different best models; correctness from a hash, so the halves vary by seed."""
    rows = []
    for task, (n, models) in TINY.items():
        for i in range(n):
            for model, (pct, cost) in models.items():
                h = int(hashlib.sha256(f"{task}|{i}|{model}".encode()).hexdigest(), 16)
                rows.append({"task": task, "item": f"{task}{i}", "model": model, "correct": h % 100 < pct,
                             "cost_usd": cost * (1 + i % 3)})
    return rows


def run_evaluate(rows):
    return evaluate(outcomes_from_rows(rows), bars=CONFIG["bars"], seeds=CONFIG["seeds"],
                    flavors=CONFIG["flavors"], calibration_fraction=CONFIG["calibration_fraction"],
                    min_samples=CONFIG["min_samples"], confidence=CONFIG["confidence"])


def committed(rows):
    result = run_evaluate(rows)
    return {"config": result["config"], "summary": result["summary"]}


def seed_rows(cells, strategy):
    """Per seed, in seed order: (correct held-out items, held-out items, cost) pooled over tasks."""
    out = []
    for seed in CONFIG["seeds"]:
        cs = [c for c in cells if c["seed"] == seed]
        out.append((sum(round(c["success"][strategy] * c["held_out_items"]) for c in cs),
                    sum(c["held_out_items"] for c in cs), math.fsum(c["cost_usd"][strategy] for c in cs)))
    return out


def expected_line(label, mine, base):
    diffs = [m[0] - b[0] for m, b in zip(mine, base)]
    gaps = sorted((m[0] - b[0]) / m[1] for m, b in zip(mine, base))
    ratios = [m[2] / b[2] for m, b in zip(mine, base)]
    k = len(gaps) // 2
    median = gaps[k] if len(gaps) % 2 else (gaps[k - 1] + gaps[k]) / 2
    return (f"{label}: above on {sum(d > 0 for d in diffs)}, equal on {sum(d == 0 for d in diffs)}, "
            f"below on {sum(d < 0 for d in diffs)} of {len(diffs)} seeds; gap lowest {gaps[0]:+.4f}, "
            f"median {median:+.4f}, highest {gaps[-1]:+.4f}, mean {math.fsum(gaps) / len(gaps):+.4f}; "
            f"cost over the best single model's {min(ratios):.3f} to {max(ratios):.3f}")


def test_gap_line_by_hand(lrs):
    mine = [(55, 100, 2.0), (50, 100, 1.0), (47, 100, 3.0), (60, 100, 1.5)]
    base = [(50, 100, 4.0), (50, 100, 4.0), (50, 100, 4.0), (50, 100, 3.0)]
    assert lrs.gap_line("x", mine, base) == (
        "x: above on 2, equal on 1, below on 1 of 4 seeds; gap lowest -0.0300, median +0.0250, "
        "highest +0.1000, mean +0.0300; cost over the best single model's 0.250 to 0.750")
    free = [(m[0], m[1], 0.0) if k == 2 else m for k, m in enumerate(base)]
    assert lrs.gap_line("x", mine, free).endswith("; cost over the best single model's -")


def test_best_single_model_is_the_12_7_rule(lrs):
    def row(strategy, success, cost, flavor="cost_blind"):
        return {"bar": 0.5, "flavor": flavor, "strategy": strategy, "success": success, "cost_usd": cost}
    rows = [row("routed", 0.9, 1.0), row("model:v/b", 0.6, 2.0), row("model:v/a", 0.6, 2.0), row("model:v/c", 0.6, 3.0)]
    assert lrs.best_single_model(rows) == "v/a"
    assert lrs.best_single_model(rows + [row("model:v/d", 0.6, 1.5)]) == "v/d"
    assert lrs.best_single_model(rows + [row("model:v/e", 0.61, 9.0)]) == "v/e"
    with pytest.raises(ValueError, match="differs"):
        lrs.best_single_model(rows + [row("model:v/d", 0.6, 1.5, "cost_effective")])


def test_report_lines_on_a_small_matrix(lrs):
    rows = tiny_rows()
    result = run_evaluate(rows)
    lines = lrs.report(outcomes_from_rows(rows), committed(rows), rel="evidence/tiny/results.json")
    summary = [r for r in result["summary"] if (r["bar"], r["flavor"]) == (0.5, "cost_effective")]
    best = min((r for r in summary if r["strategy"].startswith("model:")),
               key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))["strategy"][len("model:"):]
    at = {(b, f): [c for c in result["cells"] if (c["bar"], c["flavor"]) == (b, f)]
          for b in CONFIG["bars"] for f in CONFIG["flavors"]}
    base = seed_rows(at[(0.5, "cost_effective")], f"model:{best}")
    held = [n for _, n, _ in base]
    want = [f"LLMRouterBench (evidence/tiny/results.json): 2 tasks, 3 models, 220 items, bars 0.5, 0.65, "
            f"6 seeds, held-out items per seed {min(held):,} to {max(held):,}",
            f"best single model (12.7): {best}; a gap is a row's pooled held-out success on a seed minus "
            f"{best}'s on the same halves",
            expected_line("best_on_calibration (every bar and flavor)",
                          seed_rows(at[(0.5, "cost_effective")], "best_on_calibration"), base)]
    for flavor in CONFIG["flavors"]:
        want.append(f"{flavor} routed:")
        signs, picks = [set() for _ in CONFIG["seeds"]], {}
        for bar in CONFIG["bars"]:
            mine = seed_rows(at[(bar, flavor)], "routed")
            for k, (m, b) in enumerate(zip(mine, base)):
                signs[k].add((m[0] > b[0]) - (m[0] < b[0]))
            for c in at[(bar, flavor)]:
                picks.setdefault((c["task"], c["seed"]), set()).add(c["models"]["routed"])
            want.append(expected_line(f"  bar {bar}", mine, base))
        want.append(f"  seeds whose gap has one sign at every bar: {sum(len(s) == 1 for s in signs)} of 6; "
                    f"(task, seed) cells routed to one model at every bar: "
                    f"{sum(len(p) == 1 for p in picks.values())} of 12")
    assert lines == want
    # the matrix exercises the counts: some row is above on some seed and below on another
    assert any(re.search(r"above on [1-5], equal on \d, below on [1-5]", x) for x in lines)


@pytest.mark.parametrize("key", ["success", "cost_usd"])
@pytest.mark.parametrize("strategy", ["routed", "best_on_calibration", "model:"])
def test_report_stops_when_a_row_is_not_the_committed_one(lrs, strategy, key):
    rows = tiny_rows()
    record = committed(rows)
    best = lrs.best_single_model(record["summary"])
    name = f"model:{best}" if strategy == "model:" else strategy
    hit = [r for r in record["summary"] if (r["bar"], r["flavor"], r["strategy"]) == (0.65, "cost_blind", name)]
    assert len(hit) == 1
    hit[0][key] *= 1 + 1e-9
    with pytest.raises(ValueError, match="committed"):
        lrs.report(outcomes_from_rows(rows), record)


# Two seed sets for the one-sign count, as (base correct, routed correct at bar 0.5, at bar 0.6)
# per seed out of 1,000 held-out items: level then below beside below twice keeps one sign on 1 seed
# of 2; above twice on both seeds, once by 3 items (a gap of +0.003), keeps one sign on 2 of 2.
SIGN_SEEDS = [([(500, 500, 480), (500, 490, 480)], "1 of 2"), ([(500, 503, 520), (500, 530, 520)], "2 of 2")]


@pytest.mark.parametrize("seeds, count", SIGN_SEEDS)
def test_one_sign_count_compares_correct_counts(lrs, monkeypatch, seeds, count):
    bars, held = [0.5, 0.6], 1000
    cells = []
    for k, bar in enumerate(bars):
        for seed, (base, *routed) in enumerate(seeds):
            cells.append({"bar": bar, "flavor": "cost_blind", "seed": seed, "task": "t", "calibration_items": held,
                          "held_out_items": held, "cleared": True,
                          "models": {"routed": "v/a", "best_on_calibration": "v/a", "cheapest": "v/b"},
                          "success": {"routed": routed[k] / held, "best_on_calibration": base / held,
                                      "model:v/a": base / held, "model:v/b": 0.4},
                          "cost_usd": {"routed": 1.5, "best_on_calibration": 2.0, "model:v/a": 2.0, "model:v/b": 1.0}})
    summary = []
    for bar in bars:
        for strategy in ("routed", "best_on_calibration", "model:v/a", "model:v/b"):
            mine = [c for c in cells if c["bar"] == bar]
            summary.append({"bar": bar, "flavor": "cost_blind", "strategy": strategy,
                            "success": math.fsum(c["success"][strategy] for c in mine) / len(mine),
                            "cost_usd": math.fsum(c["cost_usd"][strategy] for c in mine) / len(mine)})
    config = {"bars": bars, "seeds": [0, 1], "flavors": ["cost_blind"], "calibration_fraction": 0.5,
              "min_samples": 1, "confidence": 0.95}
    result = {"config": config, "tasks": {"t": {"items": 2 * held, "models": ["v/a", "v/b"]}}, "cells": cells}
    monkeypatch.setattr(lrs, "evaluate", lambda outcomes, **kwargs: result)
    lines = lrs.report(None, {"config": config, "summary": summary})
    assert lines[-1] == (f"  seeds whose gap has one sign at every bar: {count}; "
                         "(task, seed) cells routed to one model at every bar: 2 of 2")


def _tree(tmp_path, rows):
    path = tmp_path / RESULTS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(committed(rows)), encoding="utf-8")
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return ["--root", str(tmp_path), "--matrix", str(matrix)]


def _main(lrs, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = lrs.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_main_prints_the_report(lrs, tmp_path):
    rows = tiny_rows()
    code, out, err = _main(lrs, _tree(tmp_path, rows))
    assert (code, err) == (0, "")
    assert out == "\n".join(lrs.report(outcomes_from_rows(rows), committed(rows))) + "\n"
    assert out.startswith(f"LLMRouterBench ({RESULTS}): 2 tasks, ")


@pytest.mark.parametrize("break_it", ["matrix", "results", "key", "row"])
def test_main_exits_2_with_one_error_line(lrs, tmp_path, break_it):
    rows = tiny_rows()
    argv = _tree(tmp_path, rows)
    if break_it == "matrix":
        argv[argv.index("--matrix") + 1] = str(tmp_path / "missing.jsonl")
    elif break_it == "results":
        (tmp_path / RESULTS).write_text("not json", encoding="utf-8")
    elif break_it == "key":
        (tmp_path / RESULTS).write_text(json.dumps({"summary": []}), encoding="utf-8")
    else:
        (tmp_path / "m.jsonl").write_text(json.dumps({"task": "t", "item": "i", "model": "m"}) + "\n",
                                          encoding="utf-8")
    code, out, err = _main(lrs, argv)
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1


def test_script_is_standard_library_and_model_routing():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^(?:from|import) ([\w.]+)", text, flags=re.M)}
    assert imports <= {"argparse", "json", "math", "statistics", "sys", "pathlib", "model_routing"}
    assert text.isascii()


def _blocks(text, lang):
    return re.findall(rf"^```{lang}\n(.*?)^```$", text, flags=re.M | re.S)


def _prose(note):
    prose = re.sub(r"^```\w*\n.*?^```$", "", note, flags=re.M | re.S)
    return re.sub(r"\]\([^)]*\)|`[^`]*`", "", prose)


def test_note_quotes_its_commands_and_links():
    note = NOTE.read_text(encoding="utf-8")
    assert note.startswith("# The LLMRouterBench gain, seed by seed\n\n")
    assert not note.split("\n", 2)[2].startswith("#")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == [
        "Facts", "Method", "Results", "Reading it", "Limits", "Regenerate"]
    assert _blocks(note, "bash") == ["\n".join(REGENERATE) + "\n"]
    [text] = _blocks(note, "text")
    assert text.startswith(COMMAND + "\n")
    assert note.isascii()
    for link in ("../DESIGN.md", "../evidence/llmrouterbench/RESULTS.md", "llmrouterbench_seeds.py",
                 "where-routing-pays.md"):
        assert f"]({link})" in note, link


def test_facts_states_the_finding_before_any_number():
    note = NOTE.read_text(encoding="utf-8")
    facts = note.split("\n## Facts\n", 1)[1].split("\n## ", 1)[0]
    first = [x for x in facts.split("\n") if x.startswith("- ")][0]
    assert NUMBER.findall(_prose(first)) == [], first


def test_every_number_of_the_prose_is_in_the_output_or_allowed():
    note = NOTE.read_text(encoding="utf-8")
    [text] = _blocks(note, "text")
    printed = set(NUMBER.findall(text))
    assert sorted({n for n in NUMBER.findall(_prose(note)) if n not in printed and n not in ALLOWED}) == []


def test_where_routing_pays_limits_and_the_research_index_link_the_note():
    pays = PAYS.read_text(encoding="utf-8")
    limits = pays[pays.index("\n## Limits\n"):pays.index("\n## Regenerate\n")]
    assert sum("](llmrouterbench-seeds.md)" in x for x in limits.split("\n")) == 1
    index = INDEX.read_text(encoding="utf-8").split("\n")
    rows = [x for x in index if x.startswith("| [llmrouterbench-seeds.md](llmrouterbench-seeds.md) | ")]
    assert len(rows) == 1 and "[llmrouterbench_seeds.py](llmrouterbench_seeds.py)" in rows[0]
    assert sum(x.startswith("- `research/llmrouterbench-seeds.md` ") for x in index) == 1


# --- the pinned file, only when already cached (one session read, tests/conftest.py) ----------

@pytest.fixture(scope="module")
def output(lrs, llmrouterbench_pinned):
    """The script's lines on the matrix the session fixture wrote from the cached pinned file."""
    code, report, rows = llmrouterbench_pinned
    assert code == 0 and report["rows"] == 156858
    status, out, err = _main(lrs, ["--matrix", str(rows)])
    assert (status, err) == (0, "")
    return out


def test_note_results_block_is_the_script_output(output):
    [text] = _blocks(NOTE.read_text(encoding="utf-8"), "text")
    assert text == COMMAND + "\n" + output


def test_cost_blind_and_best_on_calibration_are_above_on_every_seed(output):
    lines = output.split("\n")
    assert lines[1].startswith("best single model (12.7): google/gemini-2.5-pro; ")
    seeds = re.search(r", (\d+) seeds, ", lines[0])[1]
    above = f": above on {seeds}, equal on 0, below on 0 of {seeds} seeds; "
    assert lines[2].startswith("best_on_calibration (every bar and flavor)" + above)
    blind = lines[lines.index("cost_blind routed:") + 1:]
    bars = [x for x in blind if x.startswith("  bar ")]
    assert len(bars) == 8 and all(above in x for x in bars)
