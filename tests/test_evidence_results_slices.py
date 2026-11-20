"""DESIGN 12.7 v1.521 (row STRAT3e): the results script keeps a sliced run's slice keys.

When ``model-routing evaluate --slice-by FIELD --json`` (DESIGN 12.3 v1.514) gives a result with
``per_slice`` and ``slice_summary``, ``reduce`` copies both, unchanged and in that order, after
``per_task``, and ``table`` prints a third table after the baselines: the CLI's slices table
(12.4 v1.514) with the bar and the flavor in front, one row per (bar, flavor, strategy) in
config order. A result with neither key reduces and prints exactly as before, so every committed
file the script wrote stays byte for byte. The tests marked ``RED`` fail until v1.522 implements
v1.521 (strict, so one that passes early fails the suite); the unmarked ones guard what v1.521
keeps and pass before and after it. Every test uses in-memory results except the last, which
reads the committed results files and their RESULTS.md.
"""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "routerbench" / "results.py"
RED = pytest.mark.xfail(strict=True, reason="row STRAT3e implements DESIGN v1.521 in v1.522")
# The committed results files this script writes (the README regenerate commands and the
# evidence workflow pass each to `results.py --evaluate`).
COMMITTED = ("routerbench", "autobench-2026", "autobench-judges", "tau2-bench", "livecodebench",
             "llmrouterbench", "response-bank", "registry-pair", "longtail-swe")
SLICE_HEADER = ["bar", "flavor", "strategy", "success", "cost_usd", "below_bar_rate",
                "cleared_rate", "bar_violation_rate", "slice_miss_rate"]


@pytest.fixture
def rs():
    spec = importlib.util.spec_from_file_location("routerbench_results_slices", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def summary_rows(bar, flavor):
    rate = {"below_bar_rate": 0.5, "cleared_rate": 0.5, "bar_violation_rate": 0.0}
    return [{"bar": bar, "flavor": flavor, "strategy": "routed", "success": 0.75,
             "cost_usd": 0.002, **rate},
            {"bar": bar, "flavor": flavor, "strategy": "model:acme/cheap", "success": 0.7,
             "cost_usd": 0.001, **rate},
            {"bar": bar, "flavor": flavor, "strategy": "model:acme/strong", "success": 0.9,
             "cost_usd": 0.004, **rate}]


def slice_row(bar, flavor, strategy, success, cost, below, cleared, violation, miss):
    return {"bar": bar, "flavor": flavor, "strategy": strategy, "success": success,
            "cost_usd": cost, "below_bar_rate": below, "cleared_rate": cleared,
            "bar_violation_rate": violation, "slice_miss_rate": miss}


def hand(bars=(0.8,), flavors=("cost_blind",)):
    """A sliced evaluate result in the --json shape, with an extra per-task strategy row."""
    bars, flavors = list(bars), list(flavors)
    summary, per_task, per_slice, slices = [], [], [], []
    for bar in bars:
        for flavor in flavors:
            summary += summary_rows(bar, flavor)
            for st in ("routed", "oracle"):
                per_task.append({"bar": bar, "flavor": flavor, "task": "all", "strategy": st,
                                 "success": 0.75, "routed_models": {"acme/cheap": 2}})
            for name in ("1-easy", "2-hard"):
                for st in ("pooled", "sliced"):
                    per_slice.append({"bar": bar, "flavor": flavor, "task": "all", "slice": name,
                                      "strategy": st, "success": 0.5, "cost_usd": 0.001,
                                      "below_bar_rate": 0.5, "cleared_rate": 1.0,
                                      "bar_violation_rate": 0.5,
                                      "routed_models": {"acme/cheap": 2}})
            slices += [slice_row(bar, flavor, "pooled", 0.75, 0.002, 0.25, 0.5, 0.5, 1.0),
                       slice_row(bar, flavor, "sliced", 0.875, 0.003, 0.125, 0.75, None, None)]
    return {"config": {"bars": bars, "seeds": [0, 1], "flavors": flavors,
                       "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95},
            "tasks": {"all": {"items": 8, "models": ["acme/cheap", "acme/strong"],
                              "slices": {"1-easy": 4, "2-hard": 4}}},
            "cells": [{"task": "all"}],
            "summary": summary, "per_task": per_task, "per_slice": per_slice,
            "slice_summary": slices}


def unsliced(result):
    out = copy.deepcopy(result)
    for key in ("per_slice", "slice_summary"):
        out.pop(key)
    out["tasks"]["all"].pop("slices")
    return out


# The slices table of hand(): widths 3, 10, 8, 7, 8, 14, 12, 18 and 15, two spaces between
# columns, trailing spaces stripped; 0.875 and 0.0030 print without rounding.
HAND_SLICES = "\n".join([
    "bar  flavor      strategy  success  cost_usd  below_bar_rate  cleared_rate  "
    "bar_violation_rate  slice_miss_rate",
    "---  ----------  --------  -------  --------  --------------  ------------  "
    "------------------  ---------------",
    "0.8  cost_blind  pooled    0.750    0.0020    0.250" + " " * 11 + "0.500" + " " * 9
    + "0.500" + " " * 15 + "1.000",
    "0.8  cost_blind  sliced    0.875    0.0030    0.125" + " " * 11 + "0.750" + " " * 9
    + "-" + " " * 19 + "-",
])


@RED
def test_reduce_keeps_the_slice_keys_after_per_task(rs):
    result = hand()
    before = copy.deepcopy(result)
    out = rs.reduce(result)
    assert list(out) == ["config", "tasks", "summary", "per_task", "per_slice", "slice_summary"]
    assert out["per_slice"] == result["per_slice"]
    assert {r["strategy"] for r in out["per_slice"]} == {"pooled", "sliced"}
    assert out["slice_summary"] == result["slice_summary"]
    assert out["tasks"]["all"]["slices"] == {"1-easy": 4, "2-hard": 4}
    assert [r["strategy"] for r in out["per_task"]] == ["routed"]
    assert result == before
    assert rs.reduce(out) == out


@RED
@pytest.mark.parametrize("present, missing", [("per_slice", "slice_summary"),
                                              ("slice_summary", "per_slice")])
def test_reduce_names_the_missing_slice_key(rs, present, missing):
    result = hand()
    result.pop(missing)
    with pytest.raises(ValueError, match=missing):
        rs.reduce(result)
    assert present in result


def test_reduce_of_an_unsliced_result_keeps_four_keys(rs):
    out = rs.reduce(unsliced(hand()))
    assert list(out) == ["config", "tasks", "summary", "per_task"]


@RED
def test_table_adds_the_slices_table_known_answer(rs):
    result = hand()
    assert rs.table(result) == rs.table(unsliced(result)) + "\n\n" + HAND_SLICES


@RED
def test_table_lists_the_slice_rows_in_config_order(rs):
    result = hand(bars=(0.8, 0.9), flavors=("cost_effective", "cost_blind"))
    result["slice_summary"].reverse()
    third = rs.table(result).split("\n\n")[2].splitlines()
    assert third[0].split() == SLICE_HEADER
    keys = [tuple(line.split()[:3]) for line in third[2:]]
    assert keys == [(bar, flavor, st) for bar in ("0.8", "0.9")
                    for flavor in ("cost_effective", "cost_blind")
                    for st in ("sliced", "pooled")]


@RED
def test_table_refuses_a_block_without_slice_rows(rs):
    result = hand(bars=(0.8, 0.9))
    result["slice_summary"] = [r for r in result["slice_summary"] if r["bar"] != 0.9]
    with pytest.raises(ValueError, match="slice_summary"):
        rs.table(result)


def test_table_of_an_unsliced_result_is_two_tables(rs):
    text = rs.table(unsliced(hand()))
    assert text.count("\n\n") == 1
    assert "slice_miss_rate" not in text


def planted_rows():
    """40 items in two slices: the cheap model answers every easy item and half the hard ones."""
    rows = []
    for i in range(40):
        name = "1-easy" if i < 20 else "2-hard"
        rows.append({"task": "all", "item": f"q{i:02d}", "model": "acme/cheap",
                     "correct": i < 20 or i % 2 == 0, "cost_usd": 0.001, "difficulty": name})
        rows.append({"task": "all", "item": f"q{i:02d}", "model": "acme/strong",
                     "correct": True, "cost_usd": 0.01, "difficulty": name})
    return rows


@RED
def test_a_real_sliced_run_reduces_and_prints_its_slice_summary(rs):
    result = evaluate(outcomes_from_rows(planted_rows(), slice_by="difficulty"),
                      bars=[0.6, 0.9], seeds=range(3), min_samples=5)
    result.pop("cells")
    out = rs.reduce(json.loads(json.dumps(result)))
    assert out["per_slice"] == result["per_slice"]
    assert out["slice_summary"] == result["slice_summary"]
    blocks = rs.table(out).split("\n\n")
    assert len(blocks) == 3
    lines = blocks[2].splitlines()
    assert lines[0].split() == SLICE_HEADER
    assert len(lines) == 2 + len(result["slice_summary"]) == 2 + 2 * 2 * 2

    def fmt(value):
        return "-" if value is None else f"{value:.3f}"
    for line, r in zip(lines[2:], result["slice_summary"]):
        assert line.split() == [str(r["bar"]), r["flavor"], r["strategy"], fmt(r["success"]),
                                f"{r['cost_usd']:.4f}", fmt(r["below_bar_rate"]),
                                fmt(r["cleared_rate"]), fmt(r["bar_violation_rate"]),
                                fmt(r["slice_miss_rate"])]


@RED
def test_cli_writes_a_sliced_file_and_prints_three_tables(rs, tmp_path, capsys):
    result = hand()
    full, out = tmp_path / "full.json", tmp_path / "results.json"
    full.write_text(json.dumps(result), encoding="utf-8")
    assert rs.main(["--evaluate", str(full), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == json.dumps(rs.reduce(result), indent=2) + "\n"
    assert "slice_summary" in json.loads(out.read_text(encoding="utf-8"))
    capsys.readouterr()
    assert rs.main(["--table", str(out)]) == 0
    assert capsys.readouterr().out == rs.table(result) + "\n"
    assert rs.table(result).endswith(HAND_SLICES)


@pytest.mark.parametrize("folder", COMMITTED)
def test_each_committed_file_reduces_and_prints_as_before(rs, folder):
    path = ROOT / "evidence" / folder / "results.json"
    text = path.read_text(encoding="utf-8")
    results = json.loads(text)
    assert "per_slice" not in results and "slice_summary" not in results
    assert json.dumps(rs.reduce(results), indent=2) + "\n" == text
    table = rs.table(results)
    assert table.count("\n\n") == 1
    assert table in (ROOT / "evidence" / folder / "RESULTS.md").read_text(encoding="utf-8")
