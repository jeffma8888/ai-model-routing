"""research/check-fallback.md and research/check_fallback.py (DESIGN 12.8 v1.181; README Limitations v1.185).

The note's numbers are the script's lines on the LLMRouterBench matrix, compared byte for byte when
the pinned file is cached (the session fixture `llmrouterbench_pinned` of tests/conftest.py, which
CI never fills). The routes, the replay and the recovered share are checked by hand on a matrix of
four models and eight items, and the script's checks and exits on a small hashed matrix.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import math
import re
from pathlib import Path

import pytest

from model_routing import Outcome, evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "check_fallback.py"
NOTE = ROOT / "research" / "check-fallback.md"
INDEX = ROOT / "research" / "README.md"
README = ROOT / "README.md"
RESULTS = "evidence/llmrouterbench/results.json"
COMMAND = "$ python research/check_fallback.py --matrix llmrouterbench-matrix.jsonl"
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl",
    COMMAND[2:],
]
# the 12.18 tasks, ascending, and the pinned commit of the dataset's code repository
TASKS = ["aime", "arc-agi", "arenahard", "gpqa", "hle", "livecodebench", "livemathbench", "mmlupro", "simpleqa"]
CODE = "https://github.com/ynulihao/LLMRouterBench/blob/811df08b1b37646064eeb8cb6acfd498bf99885a/evaluation/"
# DESIGN section numbers: the only numbers of the note's prose not in the script's lines
ALLOWED = {"5.3", "12.3", "12.8", "12.18", "12.19"}
NUMBER = re.compile(r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
CONFIG = {"bars": [0.3, 0.4, 0.5], "seeds": list(range(5)), "flavors": ["cost_effective", "cost_blind"],
          "calibration_fraction": 0.5, "min_samples": 10, "confidence": 0.95}
# per task: (items, {model: (percent correct, cost per call)})
TINY = {"a": (120, {"v/w": (60, 0.01), "v/x": (72, 0.03), "v/y": (55, 0.02), "v/z": (45, 0.001)}),
        "b": (100, {"v/w": (58, 0.01), "v/x": (50, 0.03), "v/y": (66, 0.02), "v/z": (40, 0.001)})}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def cf():
    return _load("research_check_fallback", SCRIPT)


# --- by hand: one task, four models, four calibration and four held-out items, one seed ------------
# Calibration (min_samples 1, confidence 0.95): v/a 4 of 4 at 3 a call, v/b 3 of 4 at 2, v/c 2 of 4
# at 1, v/d 4 of 4 at 4, so Wilson bounds 0.510, 0.301, 0.150 and 0.510. At bar 0.1 all four pass:
# cost_effective sorts them c, b, a, d, cost_blind a, d, b, c. At bar 0.4 only a and d pass, a first.
# Held out (each model's cost as on calibration): h0 every model scores 1, h1 only v/b, h2 only v/d,
# h3 none. Oracle: 3 of 4 at 1 + 2 + 4 + 1 = 8.
HAND_CAL = {"v/a": "1111", "v/b": "1110", "v/c": "1100", "v/d": "1111"}
HAND_HELD = {"v/a": "1000", "v/b": "1100", "v/c": "1000", "v/d": "1010"}
HAND_COST = {"v/a": 3.0, "v/b": 2.0, "v/c": 1.0, "v/d": 4.0}
HAND_ROUTED = {("cost_effective", 0.1): "v/c", ("cost_effective", 0.4): "v/a",
               ("cost_blind", 0.1): "v/a", ("cost_blind", 0.4): "v/a"}
HAND_LINES = [
    "LLMRouterBench (evidence/hand/results.json): 1 tasks, 4 models, 8 items, 1 seeds, bars 0.1 and 0.4, "
    "the lowest and highest of 2",
    "a route is the router's primary then its next max_fallbacks models (5.3); each held-out item is tried "
    "down its route until a record scores 1, and every attempt's cost is spent",
    "oracle: success 0.7500, cost 8.0000",
    "cost_effective bar 0.1:",
    # c: only h0; c, b, a: h0 at 1, h1 at 1 + 2, h2 and h3 at 1 + 2 + 3; then d scores h2
    "  max_fallbacks 0: success 0.2500, cost 4.0000, 1.000 times no fallback's, attempts per item 1.000, "
    "routes of 1 to 1 models, gap to the oracle recovered 0.000",
    "  max_fallbacks 2: success 0.5000, cost 16.0000, 4.000 times no fallback's, attempts per item 2.250, "
    "routes of 3 to 3 models, gap to the oracle recovered 0.500",
    "  max_fallbacks 3: success 0.7500, cost 24.0000, 6.000 times no fallback's, attempts per item 2.750, "
    "routes of 4 to 4 models, gap to the oracle recovered 1.000",
    "cost_effective bar 0.4:",
    # a: only h0 at 3 an item; a, d: h0 at 3, h1 to h3 at 3 + 4, d scoring h2
    "  max_fallbacks 0: success 0.2500, cost 12.0000, 1.000 times no fallback's, attempts per item 1.000, "
    "routes of 1 to 1 models, gap to the oracle recovered 0.000",
    "  max_fallbacks 2: success 0.5000, cost 24.0000, 2.000 times no fallback's, attempts per item 1.750, "
    "routes of 2 to 2 models, gap to the oracle recovered 0.500",
    "  max_fallbacks 3: success 0.5000, cost 24.0000, 2.000 times no fallback's, attempts per item 1.750, "
    "routes of 2 to 2 models, gap to the oracle recovered 0.500",
    "cost_blind bar 0.1:",
    # a, d, b: h0 at 3, h1 at 3 + 4 + 2, h2 at 3 + 4, h3 at 9; then c adds 1 on h3
    "  max_fallbacks 0: success 0.2500, cost 12.0000, 1.000 times no fallback's, attempts per item 1.000, "
    "routes of 1 to 1 models, gap to the oracle recovered 0.000",
    "  max_fallbacks 2: success 0.7500, cost 28.0000, 2.333 times no fallback's, attempts per item 2.250, "
    "routes of 3 to 3 models, gap to the oracle recovered 1.000",
    "  max_fallbacks 3: success 0.7500, cost 29.0000, 2.417 times no fallback's, attempts per item 2.500, "
    "routes of 4 to 4 models, gap to the oracle recovered 1.000",
    "cost_blind bar 0.4:",
    "  max_fallbacks 0: success 0.2500, cost 12.0000, 1.000 times no fallback's, attempts per item 1.000, "
    "routes of 1 to 1 models, gap to the oracle recovered 0.000",
    "  max_fallbacks 2: success 0.5000, cost 24.0000, 2.000 times no fallback's, attempts per item 1.750, "
    "routes of 2 to 2 models, gap to the oracle recovered 0.500",
    "  max_fallbacks 3: success 0.5000, cost 24.0000, 2.000 times no fallback's, attempts per item 1.750, "
    "routes of 2 to 2 models, gap to the oracle recovered 0.500",
    "per task at bar 0.4, held-out success with max_fallbacks 0 and 3, and the oracle's:",
    "  t (8 items): cost_effective from 0.2500 to 0.5000, cost_blind from 0.2500 to 0.5000, routes of 2 to 2 models; "
    "oracle 0.7500",
]


def hand_outcomes():
    out = []
    for m in HAND_CAL:
        for k in range(4):
            out.append(Outcome("t", f"c{k}", m, HAND_CAL[m][k] == "1", HAND_COST[m]))
            out.append(Outcome("t", f"h{k}", m, HAND_HELD[m][k] == "1", HAND_COST[m]))
    return tuple(out)


def hand_committed(oracle=(0.75, 8.0)):
    config = {"bars": [0.1, 0.4], "seeds": [0], "flavors": ["cost_effective", "cost_blind"],
              "calibration_fraction": 0.5, "min_samples": 1, "confidence": 0.95}
    summary, per_task = [], []
    for (flavor, bar), m in HAND_ROUTED.items():
        success = HAND_HELD[m].count("1") / 4
        row = {"bar": bar, "flavor": flavor, "strategy": "routed", "success": success, "cost_usd": 4 * HAND_COST[m]}
        summary.append(row)
        per_task.append(dict(row, task="t"))
        summary.append({"bar": bar, "flavor": flavor, "strategy": "oracle", "success": oracle[0],
                        "cost_usd": oracle[1]})
    return {"config": config, "summary": summary, "per_task": per_task}


def hand_result():
    cells = [{"bar": bar, "flavor": flavor, "seed": 0, "task": "t", "calibration_items": 4, "held_out_items": 4,
              "cleared": True, "models": {"routed": m, "best_on_calibration": "v/a", "cheapest": "v/c"}}
             for (flavor, bar), m in sorted(HAND_ROUTED.items(), key=lambda kv: (kv[0][1], kv[0][0] == "cost_blind"))]
    return {"tasks": {"t": {"items": 8, "models": sorted(HAND_CAL)}}, "cells": cells}


@pytest.fixture
def hand(cf, monkeypatch):
    monkeypatch.setattr(cf, "evaluate", lambda outcomes, **kwargs: hand_result())
    monkeypatch.setattr(cf, "split_items", lambda items, seed, fraction=0.5: (
        tuple(f"c{k}" for k in range(4)), tuple(f"h{k}" for k in range(4))))


def test_report_by_hand(cf, hand):
    assert cf.report(hand_outcomes(), hand_committed(), rel="evidence/hand/results.json") == HAND_LINES


def test_routes_by_hand(cf):
    rows = {}
    for o in hand_outcomes():
        rows.setdefault(o.item, {})[o.model] = o
    cal = tuple(f"c{k}" for k in range(4))
    succ, mean_cost = cf.calibration(rows, cal, sorted(HAND_CAL))
    assert succ == {"v/a": 4, "v/b": 3, "v/c": 2, "v/d": 4} and mean_cost == HAND_COST
    def path(flavor, bar, limit):
        return cf.route(succ, mean_cost, 4, "t", flavor, bar, 1, 0.95, limit)
    assert path("cost_effective", 0.1, 3) == ("v/c", "v/b", "v/a", "v/d")
    assert path("cost_effective", 0.1, 2) == ("v/c", "v/b", "v/a")
    assert path("cost_blind", 0.1, 3) == ("v/a", "v/d", "v/b", "v/c")
    assert path("cost_blind", 0.4, 3) == path("cost_effective", 0.4, 3) == ("v/a", "v/d")
    assert path("cost_effective", 0.4, 0) == ("v/a",)


def test_attempts_and_share_by_hand(cf):
    rows = {}
    for o in hand_outcomes():
        rows.setdefault(o.item, {})[o.model] = o
    assert cf.attempts(rows["h1"], ("v/c", "v/b", "v/a")) == (True, 2, [1.0, 2.0])
    assert cf.attempts(rows["h3"], ("v/a", "v/d")) == (False, 2, [3.0, 4.0])
    assert cf.replay(rows, tuple(f"h{k}" for k in range(4)), ("v/a", "v/d", "v/b")) == (
        3, 9, [3.0, 3.0, 4.0, 2.0, 3.0, 4.0, 3.0, 4.0, 2.0])
    assert cf.share(0.5, 0.25, 0.75) == 0.5
    assert cf.share(0.25, 0.25, 0.25) is None


@pytest.mark.parametrize("key", ["success", "cost_usd"])
@pytest.mark.parametrize("which", ["routed", "per_task", "oracle"])
def test_report_stops_when_a_row_is_not_the_committed_one(cf, hand, which, key):
    record = hand_committed()
    rows = record["per_task"] if which == "per_task" else record["summary"]
    hit = [r for r in rows if (r["bar"], r["flavor"], r["strategy"]) ==
           (0.4, "cost_blind", "oracle" if which == "oracle" else "routed")]
    assert len(hit) == 1
    hit[0][key] *= 1 + 1e-9
    with pytest.raises(ValueError, match="committed"):
        cf.report(hand_outcomes(), record)


def test_report_stops_when_a_route_does_not_start_with_the_routed_model(cf, hand, monkeypatch):
    real = cf.route
    monkeypatch.setattr(cf, "route", lambda *a: ("v/b",) + real(*a)[1:] if a[5] == 0.4 else real(*a))
    with pytest.raises(ValueError, match="routed model"):
        cf.report(hand_outcomes(), hand_committed())


# --- a small hashed matrix: the script's own checks pass on the real evaluate ----------------------

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


def committed(rows):
    result = evaluate(outcomes_from_rows(rows), **CONFIG)
    return {"config": result["config"], "summary": result["summary"], "per_task": result["per_task"]}


def test_routes_rebuilt_as_12_3_on_every_cell(cf):
    outcomes = outcomes_from_rows(tiny_rows())
    result = evaluate(outcomes, **CONFIG)
    table = {}
    for o in outcomes:
        table.setdefault(o.task, {}).setdefault(o.item, {})[o.model] = o
    models = sorted({o.model for o in outcomes})
    for c in result["cells"]:
        cal, _ = cf.split_items(table[c["task"]], c["seed"], CONFIG["calibration_fraction"])
        succ, mean_cost = cf.calibration(table[c["task"]], cal, models)
        def path(limit):
            return cf.route(succ, mean_cost, len(cal), c["task"], c["flavor"], c["bar"],
                            CONFIG["min_samples"], CONFIG["confidence"], limit)
        whole = path(len(models) - 1)
        assert path(0) == (c["models"]["routed"],)
        assert path(2) == whole[:3]
        assert len(set(whole)) == len(whole) and (c["cleared"] or len(whole) == len(models))


def test_report_on_a_small_matrix(cf):
    rows = tiny_rows()
    record = committed(rows)
    lines = cf.report(outcomes_from_rows(rows), record, rel="evidence/tiny/results.json")
    assert lines[0] == ("LLMRouterBench (evidence/tiny/results.json): 2 tasks, 4 models, 220 items, 5 seeds, "
                        "bars 0.3 and 0.5, the lowest and highest of 3")
    for flavor in CONFIG["flavors"]:
        for bar in (0.3, 0.5):
            k = lines.index(f"{flavor} bar {bar}:")
            got = [re.match(r"  max_fallbacks (\d+): success (\S+), cost (\S+), ", x).groups() for x in lines[k + 1:k + 4]]
            assert [g[0] for g in got] == ["0", "2", "3"]
            row = [r for r in record["summary"] if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, "routed")][0]
            assert got[0][1:] == (f"{row['success']:.4f}", f"{row['cost_usd']:.4f}")
            assert [float(g[1]) for g in got] == sorted(float(g[1]) for g in got)
    # each pooled line rebuilt per seed from the script's route and replay: the means over seeds
    outcomes = outcomes_from_rows(rows)
    table = {}
    for o in outcomes:
        table.setdefault(o.task, {}).setdefault(o.item, {})[o.model] = o
    models = sorted({o.model for o in outcomes})
    for flavor in CONFIG["flavors"]:
        for bar in (0.3, 0.5):
            k = lines.index(f"{flavor} bar {bar}:")
            for j, limit in enumerate((0, 2, 3)):
                per_seed = []
                for seed in CONFIG["seeds"]:
                    correct = held_n = tries = 0
                    spent = []
                    for task in sorted(table):
                        cal, held = cf.split_items(table[task], seed, CONFIG["calibration_fraction"])
                        succ, mean_cost = cf.calibration(table[task], cal, models)
                        path = cf.route(succ, mean_cost, len(cal), task, flavor, bar, CONFIG["min_samples"],
                                        CONFIG["confidence"], limit)
                        c, n, s = cf.replay(table[task], held, path)
                        correct, held_n, tries = correct + c, held_n + len(held), tries + n
                        spent.extend(s)
                    per_seed.append((correct / held_n, math.fsum(spent), tries / held_n))
                means = [math.fsum(x[i] for x in per_seed) / len(per_seed) for i in range(3)]
                assert lines[k + 1 + j].startswith(f"  max_fallbacks {limit}: success {means[0]:.4f}, "
                                                   f"cost {means[1]:.4f}, ")
                assert f", attempts per item {means[2]:.3f}, " in lines[k + 1 + j]
    assert lines[-3] == "per task at bar 0.5, held-out success with max_fallbacks 0 and 3, and the oracle's:"
    assert [x.split(" (")[0] for x in lines[-2:]] == ["  a", "  b"]
    # the matrix exercises the fallback: some route recovers part of the gap, short of all of it
    assert any(re.search(r"recovered 0\.[1-9]", x) for x in lines)


def _tree(tmp_path, rows):
    path = tmp_path / RESULTS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(committed(rows)), encoding="utf-8")
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return ["--root", str(tmp_path), "--matrix", str(matrix)]


def _main(cf, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = cf.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_main_prints_the_report(cf, tmp_path):
    rows = tiny_rows()
    code, out, err = _main(cf, _tree(tmp_path, rows))
    assert (code, err) == (0, "")
    assert out == "\n".join(cf.report(outcomes_from_rows(rows), committed(rows))) + "\n"
    assert out.startswith(f"LLMRouterBench ({RESULTS}): 2 tasks, ")


@pytest.mark.parametrize("break_it", ["matrix", "results", "key", "row"])
def test_main_exits_2_with_one_error_line(cf, tmp_path, break_it):
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
    code, out, err = _main(cf, argv)
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1


def test_script_is_standard_library_and_model_routing():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^(?:from|import) ([\w.]+)", text, flags=re.M)}
    assert imports <= {"argparse", "json", "math", "sys", "pathlib", "model_routing"}
    assert text.isascii()


# --- the note ---------------------------------------------------------------------------------------

def _blocks(text, lang):
    return re.findall(rf"^```{lang}\n(.*?)^```$", text, flags=re.M | re.S)


def _prose(note):
    prose = re.sub(r"^```\w*\n.*?^```$", "", note, flags=re.M | re.S)
    return re.sub(r"\]\([^)]*\)|`[^`]*`", "", prose)


def _section(note, name):
    return note.split(f"\n## {name}\n", 1)[1].split("\n## ", 1)[0]


def test_note_quotes_its_commands_and_links():
    note = NOTE.read_text(encoding="utf-8")
    assert note.startswith("# What a fallback on a failed check buys on LLMRouterBench\n\n")
    assert not note.split("\n", 2)[2].startswith("#")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == [
        "Facts", "Checks per task", "Method", "Results", "Reading it", "Limits", "Regenerate"]
    assert _blocks(note, "bash") == ["\n".join(REGENERATE) + "\n"]
    [text] = _blocks(note, "text")
    assert text.startswith(COMMAND + "\n")
    assert note.isascii()
    for link in ("../DESIGN.md", "../evidence/llmrouterbench/RESULTS.md", "check_fallback.py"):
        assert f"]({link})" in note, link


def test_facts_says_first_that_the_numbers_are_an_upper_bound():
    facts = _section(NOTE.read_text(encoding="utf-8"), "Facts")
    first = [x for x in facts.split("\n") if x.startswith("- ")][0]
    assert "upper bound" in first and "check" in first, first


def test_checks_per_task_has_one_linked_row_per_task():
    table = [x for x in _section(NOTE.read_text(encoding="utf-8"), "Checks per task").split("\n")
             if x.startswith("|")]
    assert table[0] == "| task | how the record's score is made | a check at call time without the answer key |"
    assert set(table[1]) <= set("|-: ")
    rows = [[c.strip() for c in x.strip("|").split("|")] for x in table[2:]]
    assert [r[0] for r in rows] == [f"`{t}`" for t in TASKS]
    for r in rows:
        assert len(r) == 3 and f"]({CODE}" in r[1] and r[2], r


def test_every_number_of_the_prose_is_in_the_output_or_allowed():
    note = NOTE.read_text(encoding="utf-8")
    [text] = _blocks(note, "text")
    printed = set(NUMBER.findall(text))
    assert sorted({n for n in NUMBER.findall(_prose(note)) if n not in printed and n not in ALLOWED}) == []


def test_the_research_index_lists_the_note():
    index = INDEX.read_text(encoding="utf-8").split("\n")
    rows = [x for x in index if x.startswith("| [check-fallback.md](check-fallback.md) | ")]
    assert len(rows) == 1 and "[check_fallback.py](check_fallback.py)" in rows[0]
    assert sum(x.startswith("- `research/check-fallback.md` ") for x in index) == 1



def limitations_first_bullet():
    """README Limitations bullet 1 (v1.185), its ranges built from the note's Results block."""
    [text] = _blocks(NOTE.read_text(encoding="utf-8"), "text")
    lines = text.split("\n")
    models = int(re.search(r", (\d+) models, ", lines[1]).group(1))
    got = {}
    for x in lines:
        m = re.fullmatch(r"  max_fallbacks (\d+): success \S+, cost \S+, (\S+) times no fallback's, .*, "
                         r"gap to the oracle recovered (\S+)", x)
        if m:
            got.setdefault(int(m.group(1)), []).append((m.group(2), m.group(3)))
    assert sorted(got) == [0, 2, models - 1] and all(len(v) == 4 for v in got.values()), got

    def span(k, i):
        values = sorted((v[i] for v in got[k]), key=float)
        return f"{values[0]} to {values[-1]}"

    return ("- Routes per task, not per prompt: the router picks each task's first model, with no difficulty "
            "prediction or confidence-based cascade. What reacts per call is the executor's fallback, which moves "
            "to the next model of the route when the caller's `validate` check fails (`DESIGN.md` 7). Replayed on "
            "LLMRouterBench with a check as good as the record's own score, so as upper bounds, two fallbacks "
            f"recover {span(2, 1)} of the gap between routed and per-item oracle success, at {span(2, 0)} times "
            "the cost, and the router's whole sorted list, which at a high bar holds only the models that clear "
            f"it, {span(models - 1, 1)}, at {span(models - 1, 0)} times. "
            "A check at call time can only do worse, and on every task but `arenahard` "
            "the score is made against an answer key a caller does not hold, in part on `livecodebench`, whose "
            "public test cases a caller may hold ([research/check-fallback.md](research/check-fallback.md))")


def test_readme_limitations_first_bullet_names_the_fallback_on_a_failed_check():
    readme = README.read_text(encoding="utf-8")
    limits = readme.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in limits.splitlines() if line.startswith("- ")]
    assert bullets[0] == limitations_first_bullet()
    assert sum("(research/check-fallback.md)" in b for b in bullets) == 1
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    section = design.split("\n## 7. Execution with fallback (`executor.py`)\n", 1)[1].split("\n## ", 1)[0]
    assert "- `validate` given and `validate(text)` is falsy: outcome `invalid`" in section
    reading = [x for x in _section(NOTE.read_text(encoding="utf-8"), "Reading it").split("\n") if x.startswith("- ")]
    assert "](../README.md#limitations-and-non-goals-v1)' first bullet" in reading[-1], reading[-1]
    assert "backlog row" not in reading[-1] and "now also says" in reading[-1], reading[-1]


# --- the pinned file, only when already cached (one session read, tests/conftest.py) ----------

@pytest.fixture(scope="module")
def output(cf, llmrouterbench_pinned):
    """The script's lines on the matrix the session fixture wrote from the cached pinned file."""
    code, report, rows = llmrouterbench_pinned
    assert code == 0 and report["rows"] == 156858
    status, out, err = _main(cf, ["--matrix", str(rows)])
    assert (status, err) == (0, "")
    return out


def test_note_results_block_is_the_script_output(output):
    [text] = _blocks(NOTE.read_text(encoding="utf-8"), "text")
    assert text == COMMAND + "\n" + output


def test_more_fallbacks_never_lower_success_or_cost(output):
    lines = output.split("\n")
    heads = [k for k, x in enumerate(lines) if re.fullmatch(r"cost_\w+ bar [\d.]+:", x)]
    assert len(heads) == 4
    for k in heads:
        got = [re.match(r"  max_fallbacks (\d+): success (\S+), cost (\S+), ", x).groups() for x in lines[k + 1:k + 4]]
        assert [g[0] for g in got] == ["0", "2", "12"]
        for i in (1, 2):
            assert float(got[i][1]) >= float(got[0][1]) and float(got[i][2]) >= float(got[0][2])
        assert lines[k + 1].endswith("gap to the oracle recovered 0.000")
