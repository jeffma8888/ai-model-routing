"""DESIGN 12.1, 12.3 and 12.4 v1.514 (row STRAT2): the offline evaluator scores slices.

A pooled success rate averages over the mix of a task's items, so a route can meet the bar on
the task while it misses it on a slice. With `slice_by`, an outcome row names its slice; each
cell of a sliced task then scores two routes on each slice's held-out items: `pooled`, the cell's
`routed` model, and `sliced`, the primary of `Router.select(..., slice=S)` on that slice's own
calibration counts. `per_slice` and `slice_summary` report their success, cost and bar rates, and
`slice_miss_rate` counts how often a route that meets the bar on the task misses it on a slice.
The tests marked `RED` fail until row STRAT2b implements v1.514 (strict, so one that passes early
fails the suite); the unmarked ones guard what v1.514 keeps and pass before and after it.

The planted matrix: on `support`, 400 quick items and 100 deep ones. fiction/cheap costs 1.0 a
call and answers every quick item and no deep one; fiction/best costs 8.0 and answers every
item. Pooled, cheap clears 0.6 on every seed (about 0.8 on about 250 calibration items), so the
`cost_effective` route is cheap: 1.0 on the quick held-out items and 0.0 on the deep ones. Sliced,
quick routes to cheap and deep to best, 1.0 on both. Every count below is read from `split_items`,
and every cost is a whole number of dollars, so each sum is exact.
"""

import json
from math import fsum

import pytest

from model_routing import (
    Outcome, evaluate, load_outcomes, outcomes_from_rows, split_items, wilson_lower_bound,
)
from model_routing.cli import main

RED = pytest.mark.xfail(strict=True, reason="row STRAT2b implements DESIGN v1.514")

V1_513_KEYS = ["config", "tasks", "cells", "summary", "per_task"]
CELL_KEYS = ["bar", "flavor", "seed", "task", "calibration_items", "held_out_items", "cleared",
             "models", "success", "cost_usd"]
ENTRY_KEYS = ["calibration_items", "held_out_items", "cleared", "models", "success", "cost_usd"]
PER_SLICE_KEYS = ["bar", "flavor", "task", "slice", "strategy", "success", "cost_usd",
                  "below_bar_rate", "cleared_rate", "bar_violation_rate", "routed_models"]
SLICE_SUMMARY_KEYS = ["bar", "flavor", "strategy", "success", "cost_usd", "below_bar_rate",
                      "cleared_rate", "bar_violation_rate", "slice_miss_rate"]
CHEAP, BEST = "fiction/cheap", "fiction/best"
QUICK = [f"q{i:03d}" for i in range(400)]
DEEP = [f"d{i:03d}" for i in range(100)]
COMMON = [f"c{i:03d}" for i in range(200)]
RARE = [f"r{i:02d}" for i in range(12)]
SEEDS = [0, 1, 2]
BAR = 0.6


def cal(items, seed):
    return split_items(items, seed)[0]


def held(items, seed):
    return split_items(items, seed)[1]


def sliced_rows(task, slices, key="slice"):
    """``slices``: (slice name, items, is fiction/cheap right on them); fiction/best is right on
    every item."""
    rows = []
    for name, items, cheap_right in slices:
        for item in items:
            rows.append({"task": task, "item": item, "model": CHEAP, "correct": cheap_right,
                         "cost_usd": 1.0, key: name})
            rows.append({"task": task, "item": item, "model": BEST, "correct": True,
                         "cost_usd": 8.0, key: name})
    return rows


def planted_rows(key="slice"):
    return sliced_rows("support", [("quick", QUICK, True), ("deep", DEEP, False)], key)


def run(rows, slice_by="slice", **kw):
    kw.setdefault("bars", [BAR])
    kw.setdefault("seeds", SEEDS)
    kw.setdefault("flavors", ("cost_effective",))
    return evaluate(outcomes_from_rows(rows, slice_by=slice_by), **kw)


def strip(rows):
    return [{k: v for k, v in r.items() if k != "slice"} for r in rows]


# --- guards: what v1.514 keeps (pass before and after) ---

def test_the_planted_split_is_what_the_expectations_assume():
    for seed in SEEDS:
        c = len(cal(QUICK, seed)) + len(cal(DEEP, seed))
        assert wilson_lower_bound(len(cal(QUICK, seed)), c) > BAR
        assert wilson_lower_bound(len(cal(DEEP, seed)), len(cal(DEEP, seed))) > BAR
        assert min(len(cal(DEEP, seed)), len(cal(QUICK, seed))) >= 30
        assert held(DEEP, seed) and held(QUICK, seed)
        assert 2 <= len(cal(RARE, seed)) < 30 and held(RARE, seed)
        assert wilson_lower_bound(len(cal(RARE, seed)), len(cal(RARE, seed))) > 0.3
        n = len(cal(COMMON, seed)) + len(cal(RARE, seed))
        assert wilson_lower_bound(len(cal(COMMON, seed)), n) > BAR


def test_a_slice_key_without_slice_by_is_an_extra_key():
    assert outcomes_from_rows(planted_rows()) == outcomes_from_rows(strip(planted_rows()))


def test_an_unsliced_run_keeps_the_v1_513_keys():
    result = evaluate(outcomes_from_rows(planted_rows()), bars=[BAR], seeds=SEEDS)
    assert list(result) == V1_513_KEYS
    assert all(list(cell) == CELL_KEYS for cell in result["cells"])
    assert all(list(v) == ["items", "models"] for v in result["tasks"].values())


def test_the_cli_without_slice_by_ignores_a_slice_key(tmp_path, capsys):
    out = []
    for name, rows in (("a", planted_rows()), ("b", strip(planted_rows()))):
        path = tmp_path / f"{name}.jsonl"
        path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
        assert main(["evaluate", "--outcomes", str(path), "--bar", "0.6", "--seeds", "3"]) == 0
        out.append(capsys.readouterr().out)
    assert out[0] == out[1]


# --- 12.1: reading a slice ---

@RED
def test_outcome_gains_a_last_slice_field_defaulting_to_none():
    o = Outcome("support", "q000", CHEAP, True, 1.0)
    assert o.slice is None
    assert Outcome("support", "q000", CHEAP, True, 1.0, "quick").slice == "quick"


@RED
def test_slice_by_reads_each_rows_slice():
    outcomes = outcomes_from_rows(planted_rows(key="difficulty"), slice_by="difficulty")
    assert {(o.item[0], o.slice) for o in outcomes} == {("q", "quick"), ("d", "deep")}


@RED
def test_load_outcomes_takes_slice_by(tmp_path):
    path = tmp_path / "m.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in planted_rows()), encoding="utf-8")
    assert load_outcomes(path, slice_by="slice") == outcomes_from_rows(planted_rows(),
                                                                       slice_by="slice")


@RED
def test_an_absent_or_null_value_is_no_slice():
    rows = strip(planted_rows())
    rows[0]["slice"] = None
    assert all(o.slice is None for o in outcomes_from_rows(rows, slice_by="slice"))


@RED
@pytest.mark.parametrize("slice_by", ["", 3, True])
def test_a_bad_slice_by_is_refused(slice_by):
    with pytest.raises(ValueError):
        outcomes_from_rows(planted_rows(), slice_by=slice_by)


@RED
@pytest.mark.parametrize("value", ["", "a@b", 3, True, ["deep"]])
def test_a_bad_slice_value_is_refused(value):
    rows = planted_rows()
    rows[5]["slice"] = value
    with pytest.raises(ValueError):
        outcomes_from_rows(rows, slice_by="slice")


@RED
def test_a_sliced_row_on_a_task_with_an_at_sign_is_refused():
    rows = planted_rows()
    rows[0]["task"] = "sup@port"
    with pytest.raises(ValueError):
        outcomes_from_rows(rows, slice_by="slice")


# --- 12.3: the checks ---

@RED
def test_two_slices_for_one_item_are_refused():
    rows = planted_rows()
    rows[1]["slice"] = "deep"  # q000 on fiction/best; fiction/cheap's q000 row says quick
    with pytest.raises(ValueError) as exc:
        run(rows)
    assert "'support'" in str(exc.value) and "'q000'" in str(exc.value)


@RED
def test_a_task_with_sliced_and_unsliced_items_is_refused():
    rows = planted_rows()
    for row in rows[-2:]:
        del row["slice"]  # d099 on both models
    with pytest.raises(ValueError) as exc:
        run(rows)
    assert "'support'" in str(exc.value) and "'d099'" in str(exc.value)


@RED
def test_a_slice_with_an_empty_side_is_refused():
    rows = planted_rows() + sliced_rows("support", [("lone", ["z000"], True)])
    with pytest.raises(ValueError) as exc:
        run(rows)
    assert str(exc.value) == ("task 'support' slice 'lone', seed 0: the calibration or held-out "
                              "split is empty")


@RED
def test_null_slices_everywhere_give_the_unsliced_result():
    rows = strip(planted_rows())
    for row in rows:
        row["slice"] = None
    assert run(rows) == run(strip(planted_rows()), slice_by=None)


# --- 12.3: the sliced result ---

@RED
def test_the_pooled_numbers_are_the_unsliced_runs():
    flavors = ("cost_effective", "cost_blind")
    sliced = run(planted_rows(), flavors=flavors)
    plain = run(strip(planted_rows()), slice_by=None, flavors=flavors)
    assert list(sliced) == V1_513_KEYS + ["per_slice", "slice_summary"]
    for key in ("config", "summary", "per_task"):
        assert sliced[key] == plain[key]
    assert [{k: v for k, v in c.items() if k != "slices"} for c in sliced["cells"]] == plain["cells"]


@RED
def test_tasks_names_each_slices_item_count():
    assert run(planted_rows())["tasks"] == {
        "support": {"items": 500, "models": [BEST, CHEAP], "slices": {"deep": 100, "quick": 400}}}


@RED
def test_each_cell_scores_both_routes_on_each_slice():
    cells = run(planted_rows())["cells"]
    assert [c["seed"] for c in cells] == SEEDS
    for cell in cells:
        seed = cell["seed"]
        hq, hd = len(held(QUICK, seed)), len(held(DEEP, seed))
        assert list(cell) == CELL_KEYS + ["slices"]
        assert cell["models"]["routed"] == CHEAP and cell["cleared"]
        assert list(cell["slices"]) == ["deep", "quick"]
        assert all(list(e) == ENTRY_KEYS for e in cell["slices"].values())
        assert cell["slices"]["deep"] == {
            "calibration_items": len(cal(DEEP, seed)), "held_out_items": hd, "cleared": True,
            "models": {"pooled": CHEAP, "sliced": BEST},
            "success": {"pooled": 0.0, "sliced": 1.0},
            "cost_usd": {"pooled": float(hd), "sliced": 8.0 * hd}}
        assert cell["slices"]["quick"] == {
            "calibration_items": len(cal(QUICK, seed)), "held_out_items": hq, "cleared": True,
            "models": {"pooled": CHEAP, "sliced": CHEAP},
            "success": {"pooled": 1.0, "sliced": 1.0},
            "cost_usd": {"pooled": float(hq), "sliced": float(hq)}}


@RED
def test_per_slice_rows_on_the_planted_hard_slice():
    rows = run(planted_rows())["per_slice"]
    assert [(r["slice"], r["strategy"]) for r in rows] == [
        ("deep", "pooled"), ("deep", "sliced"), ("quick", "pooled"), ("quick", "sliced")]
    assert all(list(r) == PER_SLICE_KEYS for r in rows)
    hd = [len(held(DEEP, s)) for s in SEEDS]
    hq = [len(held(QUICK, s)) for s in SEEDS]
    base = {"bar": BAR, "flavor": "cost_effective", "task": "support"}
    assert rows[0] == {**base, "slice": "deep", "strategy": "pooled", "success": 0.0,
                       "cost_usd": fsum(hd) / 3, "below_bar_rate": 1.0, "cleared_rate": 1.0,
                       "bar_violation_rate": 1.0, "routed_models": {CHEAP: 3}}
    assert rows[1] == {**base, "slice": "deep", "strategy": "sliced", "success": 1.0,
                       "cost_usd": fsum(8.0 * h for h in hd) / 3, "below_bar_rate": 0.0,
                       "cleared_rate": 1.0, "bar_violation_rate": 0.0, "routed_models": {BEST: 3}}
    for row in rows[2:]:
        assert row == {**base, "slice": "quick", "strategy": row["strategy"], "success": 1.0,
                       "cost_usd": fsum(hq) / 3, "below_bar_rate": 0.0, "cleared_rate": 1.0,
                       "bar_violation_rate": 0.0, "routed_models": {CHEAP: 3}}


@RED
def test_slice_summary_gives_the_headline():
    rows = run(planted_rows())["slice_summary"]
    assert [r["strategy"] for r in rows] == ["pooled", "sliced"]
    assert all(list(r) == SLICE_SUMMARY_KEYS for r in rows)
    hq = [len(held(QUICK, s)) for s in SEEDS]
    hd = [len(held(DEEP, s)) for s in SEEDS]
    base = {"bar": BAR, "flavor": "cost_effective"}
    assert rows[0] == {**base, "strategy": "pooled",
                       "success": fsum(q / (q + d) for q, d in zip(hq, hd)) / 3,
                       "cost_usd": fsum(q + d for q, d in zip(hq, hd)) / 3,
                       "below_bar_rate": 0.5, "cleared_rate": 1.0, "bar_violation_rate": 0.5,
                       "slice_miss_rate": 1.0}
    assert rows[1] == {**base, "strategy": "sliced", "success": 1.0,
                       "cost_usd": fsum(q + 8.0 * d for q, d in zip(hq, hd)) / 3,
                       "below_bar_rate": 0.0, "cleared_rate": 1.0, "bar_violation_rate": 0.0,
                       "slice_miss_rate": 0.0}


@RED
def test_cost_blind_routes_best_everywhere_and_misses_no_slice():
    result = run(planted_rows(), flavors=("cost_blind",))
    for cell in result["cells"]:
        assert cell["models"]["routed"] == BEST
        assert {e["models"]["sliced"] for e in cell["slices"].values()} == {BEST}
    assert [r["slice_miss_rate"] for r in result["slice_summary"]] == [0.0, 0.0]


@RED
def test_a_small_slice_clears_nothing_until_it_has_min_samples():
    rows = sliced_rows("triage", [("common", COMMON, True), ("rare", RARE, False)])
    result = run(rows)
    for cell in result["cells"]:
        assert cell["models"]["routed"] == CHEAP and cell["cleared"]
        rare = cell["slices"]["rare"]
        assert rare["calibration_items"] < 30
        assert rare["cleared"] is False
        assert rare["models"] == {"pooled": CHEAP, "sliced": BEST}
        assert rare["success"] == {"pooled": 0.0, "sliced": 1.0}
    sliced_rare = [r for r in result["per_slice"]
                   if r["slice"] == "rare" and r["strategy"] == "sliced"]
    assert len(sliced_rare) == 1
    assert sliced_rare[0]["cleared_rate"] == 0.0
    assert sliced_rare[0]["bar_violation_rate"] is None
    pooled_rare = [(r["cleared_rate"], r["bar_violation_rate"]) for r in result["per_slice"]
                   if r["slice"] == "rare" and r["strategy"] == "pooled"]
    assert pooled_rare == [(1.0, 1.0)]
    summary = {r["strategy"]: r for r in result["slice_summary"]}
    assert summary["pooled"]["cleared_rate"] == 1.0
    assert summary["sliced"]["cleared_rate"] == 0.5
    assert summary["pooled"]["slice_miss_rate"] == 1.0
    assert summary["sliced"]["slice_miss_rate"] is None
    loose = run(rows, bars=[0.3], min_samples=1)
    assert all(c["slices"]["rare"]["cleared"] for c in loose["cells"])


@RED
def test_an_unsliced_task_beside_a_sliced_one_gets_no_slice_rows():
    plain = [{**r, "task": "other"} for r in strip(planted_rows())]
    result = run(planted_rows() + plain)
    assert "slices" not in result["tasks"]["other"]
    assert all("slices" not in c for c in result["cells"] if c["task"] == "other")
    assert {r["task"] for r in result["per_slice"]} == {"support"}
    assert result["slice_summary"] == run(planted_rows())["slice_summary"]


@RED
def test_a_sliced_run_is_deterministic():
    rows = planted_rows()
    a = json.dumps(run(rows), sort_keys=True)
    assert a == json.dumps(run(list(reversed(rows))), sort_keys=True)


# --- 12.4: the CLI ---

def _matrix(tmp_path, rows):
    path = tmp_path / "m.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return str(path)


ARGS = ["--bar", "0.6", "--seeds", "3", "--flavor", "cost_effective"]


@RED
def test_cli_json_keeps_per_slice_and_slice_summary(tmp_path, capsys):
    path = _matrix(tmp_path, planted_rows(key="difficulty"))
    argv = ["evaluate", "--outcomes", path, *ARGS, "--slice-by", "difficulty", "--json"]
    assert main(argv) == 0
    printed = json.loads(capsys.readouterr().out)
    expected = run(planted_rows(key="difficulty"), slice_by="difficulty")
    expected.pop("cells")
    assert printed == json.loads(json.dumps(expected))
    assert list(printed) == ["config", "tasks", "summary", "per_task", "per_slice", "slice_summary"]


@RED
def test_cli_text_adds_a_slices_table_after_each_table(tmp_path, capsys):
    path = _matrix(tmp_path, planted_rows())
    assert main(["evaluate", "--outcomes", path, *ARGS]) == 0
    plain = capsys.readouterr().out
    assert main(["evaluate", "--outcomes", path, *ARGS, "--slice-by", "slice"]) == 0
    out = capsys.readouterr().out
    assert out.startswith(plain.rstrip("\n") + "\n\nbar 0.6, cost_effective, slices\n")
    block = out[len(plain.rstrip("\n")) + 2:].splitlines()
    assert block[1].split() == ["strategy", "success", "cost_usd", "below_bar_rate",
                                "cleared_rate", "bar_violation_rate", "slice_miss_rate"]
    assert [line.split()[0] for line in block[3:]] == ["pooled", "sliced"]
    assert block[3].split()[-1] == "1.000" and block[4].split()[-1] == "0.000"
    assert block[3].split()[3:6] == ["0.500", "1.000", "0.500"]


@RED
def test_cli_a_bad_slice_value_is_exit_2(tmp_path, capsys):
    rows = planted_rows()
    rows[0]["slice"] = 3
    path = _matrix(tmp_path, rows)
    assert main(["evaluate", "--outcomes", path, *ARGS, "--slice-by", "slice"]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("error: ")
