"""DESIGN 12.7 v1.571 (row CPS1d): the results tables' cost per correct column.

`evidence/routerbench/results.py` keeps a row's `cost_per_correct_usd` (12.3 v1.570) in `reduce`,
and when some `summary` row has that key `table` gives the routed and the baselines tables a last
column, `cost_per_correct_usd`, to 6 decimals and `-` for None; a row the two tables read that
lacks it is a `ValueError` naming its bar, flavor and strategy; the slices table never gains it.
Without the key the tables are v1.570's (a guard that passes before and after). Row CPS1d wrote
the tests that need the column under strict xfail.

The planted file has one bar, 0.5, in both flavors. Its best model is `model:v/b` (success 0.8,
cost 8.0), so `vs_best_model` is 3 / 8 = 0.375 for the `cost_effective` routed row and 8 / 8 for
the `cost_blind` one. Its cost per correct values are 0.25 and 0.5 routed, and for the baselines
of the first block 1 / 9 (printed 0.111111), None, 0.1, 0.1 and 0.5.
"""

import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
KEY = "cost_per_correct_usd"
RED = pytest.mark.xfail(strict=True, reason="v1.571: table gains the column in the implementing commit")


def load():
    path = ROOT / "evidence" / "routerbench" / "results.py"
    spec = importlib.util.spec_from_file_location("routerbench_results_cpc", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture()
def rs():
    return load()


# (strategy, success, cost_usd, cost_per_correct_usd) of each block's non-routed rows
BASELINES = [("oracle", 0.9, 2.0, 1 / 9), ("best_on_calibration", 0.8, 8.0, None),
             ("cheapest", 0.5, 1.0, 0.1), ("model:v/a", 0.5, 1.0, 0.1), ("model:v/b", 0.8, 8.0, 0.5)]
ROUTED = {"cost_effective": (0.6, 3.0, 0.25), "cost_blind": (0.8, 8.0, 0.5)}


def planted(with_key=True):
    summary = []
    for flavor, (success, cost, per_correct) in ROUTED.items():
        rows = [{"bar": 0.5, "flavor": flavor, "strategy": "routed", "success": success,
                 "cost_usd": cost, "below_bar_rate": 0.0, "cleared_rate": 1.0,
                 "bar_violation_rate": 0.0, KEY: per_correct}]
        rows += [{"bar": 0.5, "flavor": flavor, "strategy": s, "success": p, "cost_usd": c,
                  "below_bar_rate": 0.0, "cleared_rate": None, "bar_violation_rate": None,
                  KEY: k} for s, p, c, k in BASELINES]
        summary += rows
    if not with_key:
        for row in summary:
            del row[KEY]
    return {"config": {"bars": [0.5], "seeds": [0, 1], "flavors": list(ROUTED),
                       "calibration_fraction": 0.5, "min_samples": 1, "confidence": 0.95},
            "tasks": {"t": {"items": 4, "models": ["v/a", "v/b"]}},
            "summary": summary,
            "per_task": [{"bar": 0.5, "flavor": f, "task": "t", "strategy": "routed",
                          "success": ROUTED[f][0], "cost_usd": ROUTED[f][1],
                          "routed_models": {"v/a": 2}, **({KEY: ROUTED[f][2]} if with_key else {})}
                         for f in ROUTED]}


V1570 = "\n".join([
    "bar  flavor          success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate",
    "---  --------------  -------  --------  -------------  ------------  ------------------",
    "0.5  cost_effective  0.600    3.0000    0.375          1.000         0.000",
    "0.5  cost_blind      0.800    8.0000    1.000          1.000         0.000",
    "",
    "strategy             success  cost_usd",
    "-------------------  -------  --------",
    "oracle               0.900    2.0000",
    "best_on_calibration  0.800    8.0000",
    "cheapest             0.500    1.0000",
    "model:v/a            0.500    1.0000",
    "model:v/b            0.800    8.0000"])

V1571 = "\n".join([
    "bar  flavor          success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate  cost_per_correct_usd",
    "---  --------------  -------  --------  -------------  ------------  ------------------  --------------------",
    "0.5  cost_effective  0.600    3.0000    0.375          1.000         0.000               0.250000",
    "0.5  cost_blind      0.800    8.0000    1.000          1.000         0.000               0.500000",
    "",
    "strategy             success  cost_usd  cost_per_correct_usd",
    "-------------------  -------  --------  --------------------",
    "oracle               0.900    2.0000    0.111111",
    "best_on_calibration  0.800    8.0000    -",
    "cheapest             0.500    1.0000    0.100000",
    "model:v/a            0.500    1.0000    0.100000",
    "model:v/b            0.800    8.0000    0.500000"])


def row(results, flavor, strategy):
    rows = [r for r in results["summary"] if (r["flavor"], r["strategy"]) == (flavor, strategy)]
    assert len(rows) == 1
    return rows[0]


def test_without_the_key_the_tables_are_v1570s(rs):
    assert rs.table(planted(with_key=False)) == V1570


@RED
def test_with_the_key_both_tables_end_in_the_column(rs):
    assert rs.table(planted()) == V1571


@RED
@pytest.mark.parametrize("flavor, strategy", [("cost_blind", "routed"), ("cost_effective", "routed"),
                                              ("cost_effective", "oracle"),
                                              ("cost_effective", "model:v/b")])
def test_a_row_the_tables_read_without_the_key_is_a_value_error(rs, flavor, strategy):
    results = planted()
    del row(results, flavor, strategy)[KEY]
    with pytest.raises(ValueError) as info:
        rs.table(results)
    assert str(info.value) == f"summary row bar 0.5, {flavor}, {strategy} has no {KEY!r} key"


@RED
def test_a_row_the_tables_do_not_read_may_lack_the_key(rs):
    # the cost_blind block's baselines are not printed: the baselines come from the first block
    results = planted()
    for strategy, *_ in BASELINES:
        del row(results, "cost_blind", strategy)[KEY]
    assert rs.table(results) == V1571


def test_reduce_keeps_the_key_last_and_unchanged(rs):
    result = planted()
    result["per_task"].append({**result["per_task"][0], "strategy": "oracle"})
    out = rs.reduce(result)
    assert out["summary"] == planted()["summary"]
    assert [list(r)[-1] for r in out["summary"] + out["per_task"]] == [KEY] * (12 + 2)
    assert [r[KEY] for r in out["per_task"]] == [0.25, 0.5]


def test_the_slices_table_never_gains_the_column(rs):
    results = planted()
    results["per_slice"] = []
    results["slice_summary"] = [
        {"bar": 0.5, "flavor": f, "strategy": s, "success": 0.5, "cost_usd": 1.0, "below_bar_rate": 0.0,
         "cleared_rate": 1.0, "bar_violation_rate": 0.0, "slice_miss_rate": None}
        for f in ROUTED for s in ("pooled", "sliced")]
    third = rs.table(results).split("\n\n")[2].split("\n")
    assert third[0].split() == ["bar", "flavor", "strategy", "success", "cost_usd", "below_bar_rate",
                                "cleared_rate", "bar_violation_rate", "slice_miss_rate"]
    assert len(third) == 2 + 4 and all(len(line.split()) == 9 for line in third[2:])


@RED
def test_the_cli_prints_the_column_and_refuses_a_row_without_it(rs, tmp_path, capsys):
    path = tmp_path / "results.json"
    path.write_text(json.dumps(planted()), encoding="utf-8")
    assert rs.main(["--table", str(path)]) == 0
    assert capsys.readouterr().out == V1571 + "\n"
    results = planted()
    del row(results, "cost_effective", "cheapest")[KEY]
    path.write_text(json.dumps(results), encoding="utf-8")
    assert rs.main(["--table", str(path)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: summary row bar 0.5, cost_effective, cheapest has no {KEY!r} key\n"


@RED
def test_tau2_bench_is_the_one_committed_results_file_with_the_key():
    carrying, checked = [], 0
    for path in sorted((ROOT / "evidence").glob("*/*.json")):
        data = json.loads(path.read_text(encoding="utf-8"))
        if not (isinstance(data, dict) and isinstance(data.get("summary"), list)
                and data["summary"] and isinstance(data["summary"][0], dict)
                and "strategy" in data["summary"][0]):
            continue
        checked += 1
        if any(KEY in r for r in data["summary"] + data.get("per_task", [])):
            carrying.append(path.relative_to(ROOT).as_posix())
    assert checked >= 10
    assert carrying == ["evidence/tau2-bench/results.json"]
