"""research/below-bar-fallback.md and research/below_bar_fallback.py (DESIGN 12.8 v1.191).

The note's numbers are the script's lines on the LLMRouterBench matrix, compared byte for byte when
the pinned file is cached (the session fixture `llmrouterbench_pinned` of tests/conftest.py, which
CI never fills). Both routes, the added success and the cost ratio are checked by hand on the four
models and eight items of tests/test_research_check_fallback.py, and the script's checks and exits
on a small hashed matrix.
"""

import contextlib
import dataclasses
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path

import pytest

from model_routing import Outcome, evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "below_bar_fallback.py"
SIBLING = ROOT / "research" / "check_fallback.py"
NOTE = ROOT / "research" / "below-bar-fallback.md"
CHECK_NOTE = ROOT / "research" / "check-fallback.md"
INDEX = ROOT / "research" / "README.md"
RESULTS = "evidence/llmrouterbench/results.json"
COMMAND = "$ python research/below_bar_fallback.py --matrix llmrouterbench-matrix.jsonl"
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl",
    COMMAND[2:],
]
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
def bb():
    return _load("research_below_bar_fallback", SCRIPT)


# --- by hand: the matrix of tests/test_research_check_fallback.py --------------------------------
# Calibration (min_samples 1, confidence 0.95): v/a 4 of 4 at 3 a call, v/b 3 of 4 at 2, v/c 2 of 4
# at 1, v/d 4 of 4 at 4, so Wilson bounds 0.510, 0.301, 0.150 and 0.510. At bar 0.1 all four pass,
# so the below-bar route is the 5.3 route. At bar 0.4 only a and d pass, a first in both flavors,
# and the rest in the best_available order is b (0.301) then c (0.150).
# Held out (each model's cost as on calibration): h0 every model scores 1, h1 only v/b, h2 only v/d,
# h3 none. Oracle: 3 of 4 at 8.
HAND_CAL = {"v/a": "1111", "v/b": "1110", "v/c": "1100", "v/d": "1111"}
HAND_HELD = {"v/a": "1000", "v/b": "1100", "v/c": "1000", "v/d": "1010"}
HAND_COST = {"v/a": 3.0, "v/b": 2.0, "v/c": 1.0, "v/d": 4.0}
HAND_ROUTED = {("cost_effective", 0.1): "v/c", ("cost_effective", 0.4): "v/a",
               ("cost_blind", 0.1): "v/a", ("cost_blind", 0.4): "v/a"}
_HEAD = ("the 5.3 route is the router's primary then its next max_fallbacks models, from the clearing models "
         "alone when one clears; the below-bar route goes on after those to every other eligible measured model "
         "in the best_available order, up to max_fallbacks fallbacks; each held-out item is tried down a route "
         "until a record scores 1, and every attempt's cost is spent")
# at bar 0.4 in both flavors: a, d is the 5.3 route; a, d, b scores h0 at 3, h1 at 3 + 4 + 2, h2 at
# 3 + 4 and fails h3 at 9, so 3 of 4 at 28 against a, d's 2 of 4 at 24; then c adds 1 on h3, 29
_BAR_04 = [
    "  max_fallbacks 2: 5.3 route success 0.5000, cost 24.0000, routes of 2 to 2 models; below-bar route "
    "success 0.7500, cost 28.0000, routes of 3 to 3 models, attempts per item 2.250; it differs in 1 of 1 "
    "cells, adds success 0.2500 at 1.167 times the cost and recovers 1.000 of the 5.3 route's gap to the oracle",
    "  max_fallbacks 3: 5.3 route success 0.5000, cost 24.0000, routes of 2 to 2 models; below-bar route "
    "success 0.7500, cost 29.0000, routes of 4 to 4 models, attempts per item 2.500; it differs in 1 of 1 "
    "cells, adds success 0.2500 at 1.208 times the cost and recovers 1.000 of the 5.3 route's gap to the oracle",
]
HAND_LINES = [
    "LLMRouterBench (evidence/hand/results.json): 1 tasks, 4 models, 8 items, 1 seeds, bars 0.1 and 0.4, "
    "the lowest and highest of 2",
    _HEAD,
    "oracle: success 0.7500, cost 8.0000",
    "cost_effective bar 0.1: no fallback success 0.2500, cost 4.0000; a model clears the bar in 1 of 1 cells",
    # c, b, a: h0 at 1, h1 at 1 + 2, h2 and h3 at 1 + 2 + 3; the whole list adds d, scoring h2
    "  max_fallbacks 2: 5.3 route success 0.5000, cost 16.0000, routes of 3 to 3 models; below-bar route "
    "success 0.5000, cost 16.0000, routes of 3 to 3 models, attempts per item 2.250; it differs in 0 of 1 "
    "cells, adds success 0.0000 at 1.000 times the cost and recovers 0.000 of the 5.3 route's gap to the oracle",
    "  max_fallbacks 3: 5.3 route success 0.7500, cost 24.0000, routes of 4 to 4 models; below-bar route "
    "success 0.7500, cost 24.0000, routes of 4 to 4 models, attempts per item 2.750; it differs in 0 of 1 "
    "cells, adds success 0.0000 at 1.000 times the cost and recovers - of the 5.3 route's gap to the oracle",
    "cost_effective bar 0.4: no fallback success 0.2500, cost 12.0000; a model clears the bar in 1 of 1 cells",
    *_BAR_04,
    "cost_blind bar 0.1: no fallback success 0.2500, cost 12.0000; a model clears the bar in 1 of 1 cells",
    # a, d, b: h0 at 3, h1 at 3 + 4 + 2, h2 at 3 + 4, h3 at 9; the whole list adds c on h3
    "  max_fallbacks 2: 5.3 route success 0.7500, cost 28.0000, routes of 3 to 3 models; below-bar route "
    "success 0.7500, cost 28.0000, routes of 3 to 3 models, attempts per item 2.250; it differs in 0 of 1 "
    "cells, adds success 0.0000 at 1.000 times the cost and recovers - of the 5.3 route's gap to the oracle",
    "  max_fallbacks 3: 5.3 route success 0.7500, cost 29.0000, routes of 4 to 4 models; below-bar route "
    "success 0.7500, cost 29.0000, routes of 4 to 4 models, attempts per item 2.500; it differs in 0 of 1 "
    "cells, adds success 0.0000 at 1.000 times the cost and recovers - of the 5.3 route's gap to the oracle",
    "cost_blind bar 0.4: no fallback success 0.2500, cost 12.0000; a model clears the bar in 1 of 1 cells",
    *_BAR_04,
    "per task with max_fallbacks 3, held-out success with the 5.3 route and the below-bar route, the cost of "
    "the second over the first's, and the oracle's:",
    "bar 0.1:",
    "  t (8 items): cost_effective from 0.7500 to 0.7500 at 1.000 times, cost_blind from 0.7500 to 0.7500 at "
    "1.000 times, the routes differ in 0 of 2 cells; oracle 0.7500",
    "bar 0.4:",
    "  t (8 items): cost_effective from 0.5000 to 0.7500 at 1.208 times, cost_blind from 0.5000 to 0.7500 at "
    "1.208 times, the routes differ in 2 of 2 cells; oracle 0.7500",
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
def hand(bb, monkeypatch):
    monkeypatch.setattr(bb, "evaluate", lambda outcomes, **kwargs: hand_result())
    monkeypatch.setattr(bb, "split_items", lambda items, seed, fraction=0.5: (
        tuple(f"c{k}" for k in range(4)), tuple(f"h{k}" for k in range(4))))


def test_report_by_hand(bb, hand):
    assert bb.report(hand_outcomes(), hand_committed(), rel="evidence/hand/results.json") == HAND_LINES


def test_routes_by_hand(bb):
    rows = {}
    for o in hand_outcomes():
        rows.setdefault(o.item, {})[o.model] = o
    succ, mean_cost = bb.CF.calibration(rows, tuple(f"c{k}" for k in range(4)), sorted(HAND_CAL))

    def decision(flavor, bar):
        return bb.decide(succ, mean_cost, 4, "t", flavor, bar, 1, 0.95)

    for flavor in ("cost_effective", "cost_blind"):
        high = decision(flavor, 0.4)
        assert bb.routes(high, 3) == (("v/a", "v/d"), ("v/a", "v/d", "v/b", "v/c"))
        assert bb.routes(high, 2) == (("v/a", "v/d"), ("v/a", "v/d", "v/b"))
        assert bb.routes(high, 0) == (("v/a",), ("v/a",))
        # the tail is the router's own best_available order: its whole list where no model clears
        none_clear = bb.CF.route(succ, mean_cost, 4, "t", flavor, 1.0, 1, 0.95, 3)
        assert [m for m in none_clear if m not in ("v/a", "v/d")] == ["v/b", "v/c"]
        assert bb.routes(decision(flavor, 1.0), 3) == (none_clear, none_clear)
        low = decision(flavor, 0.1)
        for limit in (0, 2, 3):
            whole = bb.CF.route(succ, mean_cost, 4, "t", flavor, 0.1, 1, 0.95, limit)
            assert bb.routes(low, limit) == (whole, whole)


def test_the_below_bar_tail_leaves_out_ineligible_and_unmeasured_models(bb):
    rows = {}
    for o in hand_outcomes():
        rows.setdefault(o.item, {})[o.model] = o
    succ, mean_cost = bb.CF.calibration(rows, tuple(f"c{k}" for k in range(4)), sorted(HAND_CAL))
    decision = bb.decide(succ, mean_cost, 4, "t", "cost_effective", 0.4, 1, 0.95)
    model = decision.candidates[0]
    # both would sort first in the tail on their bound, so only the filter keeps them out
    unmeasured = dataclasses.replace(model, model_id="v/e", successes=0, trials=0, quality_lb=0.9,
                                     eligible=True, passes=False, reason="insufficient_samples")
    ineligible = dataclasses.replace(model, model_id="v/f", quality_lb=0.9, eligible=False, passes=False,
                                     reason="excluded_model")
    wider = dataclasses.replace(decision, candidates=decision.candidates + (unmeasured, ineligible))
    assert bb.routes(wider, 5) == (("v/a", "v/d"), ("v/a", "v/d", "v/b", "v/c"))
    assert (bb._ratio(29.0, 24.0), bb._ratio(1.0, 0.0), bb._ratio(0.0, 0.0)) == ("1.208", "-", "-")


@pytest.mark.parametrize("key", ["success", "cost_usd"])
@pytest.mark.parametrize("which", ["routed", "per_task", "oracle"])
def test_report_stops_when_a_row_is_not_the_committed_one(bb, hand, which, key):
    record = hand_committed()
    rows = record["per_task"] if which == "per_task" else record["summary"]
    hit = [r for r in rows if (r["bar"], r["flavor"], r["strategy"]) ==
           (0.4, "cost_blind", "oracle" if which == "oracle" else "routed")]
    assert len(hit) == 1
    hit[0][key] *= 1 + 1e-9
    with pytest.raises(ValueError, match="committed"):
        bb.report(hand_outcomes(), record)


def test_report_stops_when_a_route_does_not_start_with_the_routed_model(bb, hand, monkeypatch):
    real = bb.decide
    monkeypatch.setattr(bb, "decide", lambda *a: dataclasses.replace(real(*a), primary="v/b")
                        if a[5] == 0.4 else real(*a))
    with pytest.raises(ValueError, match="routed model"):
        bb.report(hand_outcomes(), hand_committed())


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


def test_the_5_3_route_is_the_first_part_of_the_below_bar_route_on_every_cell(bb):
    outcomes = outcomes_from_rows(tiny_rows())
    result = evaluate(outcomes, **CONFIG)
    table = {}
    for o in outcomes:
        table.setdefault(o.task, {}).setdefault(o.item, {})[o.model] = o
    models = sorted({o.model for o in outcomes})
    differ = 0
    for c in result["cells"]:
        cal, _ = bb.split_items(table[c["task"]], c["seed"], CONFIG["calibration_fraction"])
        succ, mean_cost = bb.CF.calibration(table[c["task"]], cal, models)
        args = (succ, mean_cost, len(cal), c["task"], c["flavor"], c["bar"], CONFIG["min_samples"],
                CONFIG["confidence"])
        decision = bb.decide(*args)
        assert decision.primary == c["models"]["routed"]
        for limit in (0, 2, 3):
            mine, below = bb.routes(decision, limit)
            assert mine == bb.CF.route(*args, limit)
            assert below[:len(mine)] == mine and len(set(below)) == len(below) == min(limit + 1, len(models))
            assert c["cleared"] or mine == below
            differ += mine != below
    assert differ > 0


def test_report_on_a_small_matrix(bb):
    rows = tiny_rows()
    record = committed(rows)
    lines = bb.report(outcomes_from_rows(rows), record, rel="evidence/tiny/results.json")
    assert lines[:2] == ["LLMRouterBench (evidence/tiny/results.json): 2 tasks, 4 models, 220 items, 5 seeds, "
                         "bars 0.3 and 0.5, the lowest and highest of 3", _HEAD]
    pattern = re.compile(r"  max_fallbacks (\d+): 5\.3 route success (\S+), cost (\S+), routes of \d+ to \d+ "
                         r"models; below-bar route success (\S+), cost (\S+), routes of \d+ to \d+ models, "
                         r"attempts per item \S+; it differs in (\d+) of 10 cells, adds success (\S+) at (\S+) "
                         r"times the cost and recovers (\S+) of the 5\.3 route's gap to the oracle")
    top = float(re.fullmatch(r"oracle: success (\S+), cost \S+", lines[2]).group(1))
    for flavor in CONFIG["flavors"]:
        for bar in (0.3, 0.5):
            k = [j for j, x in enumerate(lines) if x.startswith(f"{flavor} bar {bar}: no fallback success ")]
            assert len(k) == 1
            row = [r for r in record["summary"] if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, "routed")][0]
            assert lines[k[0]].startswith(f"{flavor} bar {bar}: no fallback success {row['success']:.4f}, "
                                          f"cost {row['cost_usd']:.4f}; a model clears the bar in ")
            got = [pattern.fullmatch(x).groups() for x in lines[k[0] + 1:k[0] + 3]]
            assert [g[0] for g in got] == ["2", "3"]
            for g in got:
                s1, c1, s2, c2 = (float(v) for v in g[1:5])
                # each printed value is rounded to 4 decimals, so their difference is within 1e-4
                assert s2 >= s1 and c2 >= c1 and abs(float(g[6]) - (s2 - s1)) <= 1e-4 + 1e-12
                assert g[7] == f"{c2 / c1:.3f}" or abs(float(g[7]) - c2 / c1) <= 1e-3
            # with every model the below-bar route tries the whole pool, so its check reaches the oracle
            assert float(got[1][3]) == top
    assert lines[-7] == ("per task with max_fallbacks 3, held-out success with the 5.3 route and the below-bar "
                         "route, the cost of the second over the first's, and the oracle's:")
    assert [x.split(" (")[0] for x in lines[-6:]] == ["bar 0.3:", "  a", "  b", "bar 0.5:", "  a", "  b"]
    assert any(re.search(r"it differs in [1-9]\d* of 10 cells", x) for x in lines)


def _tree(tmp_path, rows):
    path = tmp_path / RESULTS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(committed(rows)), encoding="utf-8")
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return ["--root", str(tmp_path), "--matrix", str(matrix)]


def _main(bb, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = bb.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_main_prints_the_report(bb, tmp_path):
    rows = tiny_rows()
    code, out, err = _main(bb, _tree(tmp_path, rows))
    assert (code, err) == (0, "")
    assert out == "\n".join(bb.report(outcomes_from_rows(rows), committed(rows))) + "\n"
    assert out.startswith(f"LLMRouterBench ({RESULTS}): 2 tasks, ")


@pytest.mark.parametrize("break_it", ["matrix", "results", "key", "row"])
def test_main_exits_2_with_one_error_line(bb, tmp_path, break_it):
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
    code, out, err = _main(bb, argv)
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1


def test_script_is_standard_library_model_routing_and_its_sibling():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^(?:from|import) ([\w.]+)", text, flags=re.M)}
    assert imports <= {"argparse", "importlib", "json", "math", "sys", "pathlib", "model_routing"}
    assert 'with_name("check_fallback.py")' in text and SIBLING.is_file()
    assert text.isascii()


# --- the note ---------------------------------------------------------------------------------------

def _blocks(text, lang):
    return re.findall(rf"^```{lang}\n(.*?)^```$", text, flags=re.M | re.S)


def _prose(note):
    prose = re.sub(r"^```\w*\n.*?^```$", "", note, flags=re.M | re.S)
    return re.sub(r"\]\([^)]*\)|`[^`]*`", "", prose)


def _section(note, name):
    return note.split(f"\n## {name}\n", 1)[1].split("\n## ", 1)[0]


def _bullets(text):
    return [x for x in text.split("\n") if x.startswith("- ")]


def test_note_quotes_its_commands_and_links():
    note = NOTE.read_text(encoding="utf-8")
    assert note.startswith("# Should a route go on below the bar after its clearing models fail?\n\n")
    assert not note.split("\n", 2)[2].startswith("#")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == [
        "Facts", "Method", "Results", "Reading it", "Recommendation", "Limits", "Regenerate"]
    assert _blocks(note, "bash") == ["\n".join(REGENERATE) + "\n"]
    [text] = _blocks(note, "text")
    assert text.startswith(COMMAND + "\n")
    assert note.isascii() and "\u2013" not in note and "\u2014" not in note
    for link in ("../DESIGN.md", "check-fallback.md", "below_bar_fallback.py"):
        assert f"]({link})" in note, link


def test_facts_says_first_that_the_numbers_are_an_upper_bound():
    first = _bullets(_section(NOTE.read_text(encoding="utf-8"), "Facts"))[0]
    assert "upper bound" in first and "check" in first, first


def test_recommendation_names_an_option_on_task_with_the_default_unchanged():
    text = _section(NOTE.read_text(encoding="utf-8"), "Recommendation")
    assert "`Task`" in text and "default" in text and "because" in text, text
    assert not re.search(r"\b[A-Z]+\d+[a-z]?\b", text), "the note names no backlog row"


def test_every_number_of_the_prose_is_in_the_output_or_allowed():
    note = NOTE.read_text(encoding="utf-8")
    [text] = _blocks(note, "text")
    printed = set(NUMBER.findall(text))
    assert sorted({n for n in NUMBER.findall(_prose(note)) if n not in printed and n not in ALLOWED}) == []


def test_the_research_index_and_the_check_fallback_note_link_the_note():
    index = INDEX.read_text(encoding="utf-8").split("\n")
    rows = [x for x in index if x.startswith("| [below-bar-fallback.md](below-bar-fallback.md) | ")]
    assert len(rows) == 1 and "[below_bar_fallback.py](below_bar_fallback.py)" in rows[0]
    assert sum(x.startswith("- `research/below-bar-fallback.md` ") for x in index) == 1
    reading = _bullets(_section(CHECK_NOTE.read_text(encoding="utf-8"), "Reading it"))
    hits = [x for x in reading if "](below-bar-fallback.md)" in x]
    assert len(hits) == 1 and "backlog row" not in hits[0], hits


def test_design_specifies_the_note():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    section = design.split("\n### 12.8 ", 1)[1].split("\n### ", 1)[0]
    bullets = [x for x in section.split("\n") if x.startswith("- Below-bar fallback, on LLMRouterBench (v1.191): ")]
    assert len(bullets) == 1
    for words in ("`research/below-bar-fallback.md`", "`research/below_bar_fallback.py`",
                  "`(-quality_lb, routing_cost, model_id)`", "`## Recommendation`",
                  "`tests/test_research_below_bar_fallback.py`", "No change under `model_routing/`"):
        assert words in bullets[0], words
    assert re.search(r"^- v1\.191 \(\d{4}-\d{2}-\d{2}\): spec and tests \(row R16\)\. ", design, flags=re.M)


# --- the pinned file, only when already cached (one session read, tests/conftest.py) ----------

@pytest.fixture(scope="module")
def output(bb, llmrouterbench_pinned):
    """The script's lines on the matrix the session fixture wrote from the cached pinned file."""
    code, report, rows = llmrouterbench_pinned
    assert code == 0 and report["rows"] == 156858
    status, out, err = _main(bb, ["--matrix", str(rows)])
    assert (status, err) == (0, "")
    return out


def test_note_results_block_is_the_script_output(output):
    [text] = _blocks(NOTE.read_text(encoding="utf-8"), "text")
    assert text == COMMAND + "\n" + output


def test_the_whole_below_bar_route_reaches_the_oracle(output):
    lines = output.split("\n")
    top = re.fullmatch(r"oracle: success (\S+), cost \S+", lines[2]).group(1)
    whole = [x for x in lines if x.startswith("  max_fallbacks 12: ")]
    assert len(whole) == 4
    for x in whole:
        assert f"; below-bar route success {top}, " in x and x.endswith(" recovers 1.000 of the 5.3 route's gap "
                                                                       "to the oracle"), x


# v1.263 (row E1d): the script rebuilds a cell's router over 12.3's registry, so of two means one ulp
# apart, which the old price of mean * 1e6 per million input tokens merged into one cost, the
# `cost_effective` route starts at the lower one, not at the lower model ID
def test_route_starts_at_the_lower_of_two_means_one_ulp_apart(bb):
    low, high = float.fromhex("0x1.47ae147ae1488p-7"), float.fromhex("0x1.47ae147ae1489p-7")
    succ, mean_cost = {"v/a": 32, "v/z": 32}, {"v/a": high, "v/z": low}
    decision = bb.decide(succ, mean_cost, 32, "t", "cost_effective", 0.8, 30, 0.95)
    assert (decision.primary, decision.fallbacks) == ("v/z", ("v/a",))
