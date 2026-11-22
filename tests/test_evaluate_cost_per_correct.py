"""DESIGN 12.3, 12.4 and 12.5 v1.570 (row CPS1c): the offline evaluator's cost per correct item.

`evaluate(..., cost_per_correct=True)` and `model-routing evaluate --cost-per-correct` add
`cost_per_correct_usd` to each `summary` and `per_task` row: one `math.fsum` of the row's cells'
held-out `cost_usd` over the sum of their held-out correct counts, None at 0 correct. Row CPS1c
wrote these tests under strict xfail; the guards pin what v1.569 keeps without the option.

The planted matrix, 12 items `i00` to `i11` on each of two tasks, every cost a whole number of
dollars so each sum is exact, seeds 0 and 1 (by `split_items`, seed 0 holds out i01, i03, i04,
i08, i10 and i11, seed 1 i01, i04, i06 and i11):
- task `t`: fiction/cheap costs 3 and is right on the odd items; fiction/strong costs 4 and is
  right on every item. At bar 0.1 with `min_samples` 1 both clear, so `cost_effective` routes to
  fiction/cheap: 0.75 of fiction/strong's cost per call, but 6.0 per correct item against 4.0
- task `u`: the same two models, fiction/cheap wrong on every item, so only fiction/strong clears
Held out over both seeds, fiction/cheap costs 3 * 10 on each task and is right on 3 + 2 items
of `t`; fiction/strong costs 4 * 10 on each task and is right on all 10; the oracle pays 3 on an
odd item of `t` and 4 on every other item, 35 on `t` and 40 on `u`.
"""

import json

import pytest

from model_routing import Outcome, evaluate, split_items
from model_routing.cli import main

CHEAP, STRONG = "fiction/cheap", "fiction/strong"
CASCADE = f"{CHEAP}>{STRONG}@sig"
ITEMS = [f"i{n:02d}" for n in range(12)]
SEEDS = [0, 1]
ROW_KEYS = ["bar", "flavor", "strategy", "success", "cost_usd", "below_bar_rate", "cleared_rate",
            "bar_violation_rate"]
STRATEGIES = ["routed", "oracle", "best_on_calibration", "cheapest", f"model:{CHEAP}",
              f"model:{STRONG}"]
HEADER = ("strategy              success  cost_usd  below_bar_rate  cleared_rate  "
          "bar_violation_rate")


def odd(item):
    return int(item[1:]) % 2 == 1


def outcomes():
    rows = []
    for task in ("t", "u"):
        for item in ITEMS:
            rows.append(Outcome(task, item, CHEAP, odd(item) if task == "t" else False, 3.0))
            rows.append(Outcome(task, item, STRONG, True, 4.0))
    return rows


def run(**kw):
    return evaluate(outcomes(), bars=[0.1], seeds=SEEDS, min_samples=1, **kw)


def by_strategy(rows, flavor, task=None):
    return {r["strategy"]: r for r in rows
            if r["flavor"] == flavor and (task is None or r["task"] == task)}


def write_matrix(tmp_path, rows):
    path = tmp_path / "m.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return str(path)


def matrix_rows():
    return [{"task": o.task, "item": o.item, "model": o.model, "correct": o.correct,
             "cost_usd": o.cost_usd} for o in outcomes()]


def cli(capsys, tmp_path, *extra):
    path = write_matrix(tmp_path, matrix_rows())
    code = main(["evaluate", "--outcomes", path, "--bar", "0.1", "--seeds", "2",
                 "--min-samples", "1", *extra])
    out = capsys.readouterr()
    return code, out.out, out.err


# guards: they pass before and after v1.570


def test_the_split_is_the_one_the_docstring_reads():
    assert split_items(ITEMS, 0)[1] == ("i01", "i03", "i04", "i08", "i10", "i11")
    assert split_items(ITEMS, 1)[1] == ("i01", "i04", "i06", "i11")


def test_without_the_option_rows_keep_the_v1_569_keys():
    result = run()
    assert [list(r) for r in result["summary"]] == [ROW_KEYS] * 12
    assert [list(r) for r in result["per_task"]] == [
        ROW_KEYS[:2] + ["task"] + ROW_KEYS[2:] + ["routed_models"]] * 24


def test_the_planted_routes_and_costs_per_call():
    eff = by_strategy(run()["summary"], "cost_effective")
    assert eff["routed"]["cost_usd"] == 35.0 and eff["routed"]["success"] == 0.75
    assert eff[f"model:{CHEAP}"]["cost_usd"] == 30.0 and eff[f"model:{STRONG}"]["cost_usd"] == 40.0
    tasks = {(r["flavor"], r["task"]): r["routed_models"] for r in run()["per_task"]
             if r["strategy"] == "routed"}
    assert tasks == {("cost_effective", "t"): {CHEAP: 2}, ("cost_effective", "u"): {STRONG: 2},
                     ("cost_blind", "t"): {STRONG: 2}, ("cost_blind", "u"): {STRONG: 2}}


def test_cli_text_without_the_option_has_no_new_column(capsys, tmp_path):
    code, out, err = cli(capsys, tmp_path)
    assert code == 0 and err == ""
    assert "cost_per_correct_usd" not in out
    assert out.splitlines()[1] == HEADER


def test_cli_json_without_the_option_has_no_new_key(capsys, tmp_path):
    code, out, _ = cli(capsys, tmp_path, "--json")
    assert code == 0
    result = json.loads(out)
    assert all("cost_per_correct_usd" not in r for r in result["summary"] + result["per_task"])


# the v1.570 contract


def test_false_is_the_default_bit_for_bit():
    assert json.dumps(run(cost_per_correct=False), sort_keys=True) == json.dumps(run(),
                                                                                 sort_keys=True)


def test_true_adds_one_last_key_and_changes_nothing_else():
    plain, priced = run(), run(cost_per_correct=True)
    for key in ("summary", "per_task"):
        assert [list(r)[-1] for r in priced[key]] == ["cost_per_correct_usd"] * len(priced[key])
        assert [{k: v for k, v in r.items() if k != "cost_per_correct_usd"}
                for r in priced[key]] == plain[key]
    assert priced["cells"] == plain["cells"] and priced["config"] == plain["config"]


def test_summary_cost_per_correct_is_held_out_cost_over_held_out_correct():
    eff = by_strategy(run(cost_per_correct=True)["summary"], "cost_effective")
    got = {s: eff[s]["cost_per_correct_usd"] for s in STRATEGIES}
    # routed: t on fiction/cheap (30 over 5 right) and u on fiction/strong (40 over 10)
    assert got == {"routed": 70 / 15, "oracle": 75 / 20, "best_on_calibration": 4.0,
                   "cheapest": 12.0, f"model:{CHEAP}": 12.0, f"model:{STRONG}": 4.0}
    blind = by_strategy(run(cost_per_correct=True)["summary"], "cost_blind")
    assert blind["routed"]["cost_per_correct_usd"] == 4.0


def test_per_task_cost_per_correct_and_none_at_zero_correct():
    rows = run(cost_per_correct=True)["per_task"]
    t, u = by_strategy(rows, "cost_effective", "t"), by_strategy(rows, "cost_effective", "u")
    assert {s: t[s]["cost_per_correct_usd"] for s in STRATEGIES} == {
        "routed": 6.0, "oracle": 3.5, "best_on_calibration": 4.0, "cheapest": 6.0,
        f"model:{CHEAP}": 6.0, f"model:{STRONG}": 4.0}
    assert {s: u[s]["cost_per_correct_usd"] for s in STRATEGIES} == {
        "routed": 4.0, "oracle": 4.0, "best_on_calibration": 4.0, "cheapest": None,
        f"model:{CHEAP}": None, f"model:{STRONG}": 4.0}
    # the CPS1 case: on t the routed model is 0.75 of fiction/strong's cost per call
    assert t["routed"]["cost_usd"] / t[f"model:{STRONG}"]["cost_usd"] == 0.75


def test_a_free_correct_strategy_costs_zero_not_none():
    rows = [Outcome("t", i, m, True, 0.0) for i in ITEMS for m in (CHEAP, STRONG)]
    result = evaluate(rows, bars=[0.5], seeds=SEEDS, min_samples=1, cost_per_correct=True)
    assert {r["cost_per_correct_usd"] for r in result["summary"]} == {0.0}


@pytest.mark.parametrize("value", [1, 0, "yes", None, 1.0])
def test_a_value_that_is_not_a_bool_is_refused(value):
    with pytest.raises(ValueError, match="cost_per_correct must be True or False"):
        run(cost_per_correct=value)


def test_the_bool_is_checked_before_any_work():
    with pytest.raises(ValueError, match="cost_per_correct must be True or False"):
        evaluate([Outcome("t", "i00", CHEAP, True, 1.0)], bars=[0.5], seeds=[0],
                 cost_per_correct="yes")


def test_cascade_rows_put_it_after_escalation_share():
    rows = []
    for item in ITEMS:
        rows.append(Outcome("t", item, CHEAP, odd(item), 3.0))
        rows.append(Outcome("t", item, STRONG, True, 4.0))
        rows.append(Outcome("t", item, CASCADE, True, 3.0 if odd(item) else 7.0,
                            escalated=not odd(item)))
    result = evaluate(rows, bars=[0.1], seeds=SEEDS, min_samples=1, cost_per_correct=True)
    assert [list(r)[-2:] for r in result["summary"]] == [
        ["escalation_share", "cost_per_correct_usd"]] * len(result["summary"])
    eff = by_strategy(result["summary"], "cost_effective")
    # held out: 9 + 21 on seed 0 and 6 + 14 on seed 1, right on all 10 items
    assert eff[f"model:{CASCADE}"]["cost_per_correct_usd"] == 5.0


def test_slices_never_gain_the_key():
    rows = [Outcome(o.task, o.item, o.model, o.correct, o.cost_usd,
                    "odd" if odd(o.item) else "even") for o in outcomes()]
    result = evaluate(rows, bars=[0.1], seeds=SEEDS, min_samples=1, cost_per_correct=True)
    assert all("cost_per_correct_usd" not in r
               for r in result["per_slice"] + result["slice_summary"])
    assert [list(r)[-1] for r in result["per_task"]] == (
        ["cost_per_correct_usd"] * len(result["per_task"]))


def test_cli_text_gains_a_last_column_to_six_decimals(capsys, tmp_path):
    code, out, err = cli(capsys, tmp_path, "--cost-per-correct")
    assert code == 0 and err == ""
    lines = out.splitlines()
    assert lines[0] == "bar 0.1, cost_effective"
    assert lines[1].split() == HEADER.split() + ["cost_per_correct_usd"]
    rows = {line.split()[0]: line.split() for line in lines[3:9]}
    assert rows["routed"][-1] == "4.666667"
    assert rows["oracle"][-1] == "3.750000"
    assert rows[f"model:{CHEAP}"][-1] == "12.000000"
    blind = out.split("\n\n")[1].splitlines()
    assert blind[0] == "bar 0.1, cost_blind" and blind[3].split()[:1] == ["routed"]
    assert blind[3].split()[-1] == "4.000000"


def test_cli_text_prints_a_dash_for_none(capsys, tmp_path):
    rows = [r for r in matrix_rows() if r["task"] == "u"]
    path = write_matrix(tmp_path, rows)
    code = main(["evaluate", "--outcomes", path, "--bar", "0.1", "--seeds", "2",
                 "--min-samples", "1", "--flavor", "cost_effective", "--cost-per-correct"])
    out = capsys.readouterr().out
    assert code == 0
    table = {line.split()[0]: line.split() for line in out.splitlines()[3:]}
    assert table["cheapest"][-1] == "-" and table[f"model:{CHEAP}"][-1] == "-"
    assert table["routed"][-1] == "4.000000"


def test_cli_json_keeps_the_key_in_summary_and_per_task(capsys, tmp_path):
    code, out, _ = cli(capsys, tmp_path, "--cost-per-correct", "--json")
    assert code == 0
    result = json.loads(out)
    assert "cells" not in result
    eff = by_strategy(result["summary"], "cost_effective")
    assert eff["routed"]["cost_per_correct_usd"] == 70 / 15
    assert [list(r)[-1] for r in result["per_task"]] == (
        ["cost_per_correct_usd"] * len(result["per_task"]))
