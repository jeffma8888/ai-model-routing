"""DESIGN 12.1, 12.3 and 12.4 v1.538 (row ESC4): the offline evaluator scores cascades.

DESIGN 7 v1.532 gives a cascade an outcome-matrix row of its own: `model` its `id`, a bool
`escalated`, no token counts and `cost_usd` the whole cascade's spend. v1.538 reads that row,
routes each cell with the matrix's cascades as 5.2 candidates (`select(..., cascades=True)`),
keeps `cheapest`, `best_on_calibration` and `oracle` to the single models, and reports how often
the cheap model escalated on held-out items as `escalation_share`. Row ESC4 wrote these tests
under strict xfail; the guards pin what v1.538 keeps and pass before and after it.

The planted matrix, 60 items `q000` to `q059` on each task, every cost a whole number of dollars
so each sum is exact:
- task `t`: fiction/cheap costs 1 and is wrong on every item whose index is a multiple of 3 (a
  third of them); fiction/strong is right on every item and costs 20 on an item whose index is a
  multiple of 3 or of 5 and 10 elsewhere; the cascade escalates on exactly those items (every
  failure of the cheap model and some false alarms), so it is right on every item and costs 1, or
  21 when it escalated
- task `u`: the same three rows, but fiction/cheap is right on every item, fiction/strong costs 10
  everywhere and the cascade escalates on the multiples of 7, costing 11 there and 1 elsewhere
At bar 0.8 with `min_samples` 5, on `t` fiction/cheap fails the bar and fiction/strong and the
cascade clear it, and the cascade's 5.2 price, 1 plus its escalated share of C times
fiction/strong's mean calibration cost, is the lower, so `t` routes to the cascade; on `u`
fiction/cheap clears and costs least, so `u` routes to it. Every count is read from `split_items`.
"""

import hashlib
import json

import pytest

from model_routing import Outcome, evaluate, outcomes_from_rows, split_items, wilson_lower_bound
from model_routing import evaluate as evaluate_module
from model_routing.cli import main

RED = pytest.mark.xfail(strict=True, reason="row ESC4: DESIGN 12 v1.538 is not code yet")

CHEAP, STRONG = "fiction/cheap", "fiction/strong"
CASCADE = f"{CHEAP}>{STRONG}@sig"
ITEMS = [f"q{i:03d}" for i in range(60)]
SEEDS = [0, 1, 2]
BAR = 0.8
STRATEGIES = ["routed", "oracle", "best_on_calibration", "cheapest", f"model:{CHEAP}",
              f"model:{CASCADE}", f"model:{STRONG}"]
CELL_KEYS = ["bar", "flavor", "seed", "task", "calibration_items", "held_out_items", "cleared",
             "models", "success", "cost_usd"]
ROW_KEYS = ["bar", "flavor", "strategy", "success", "cost_usd", "below_bar_rate", "cleared_rate",
            "bar_violation_rate"]


def index(item):
    return int(item[1:])


def escalates(task, i):
    return (i % 3 == 0 or i % 5 == 0) if task == "t" else i % 7 == 0


def strong_cost(task, i):
    return 20.0 if task == "t" and escalates(task, i) else 10.0


def cascade_cost(task, i):
    return 1.0 + (strong_cost(task, i) if escalates(task, i) else 0.0)


def single_rows(task):
    rows = []
    for item in ITEMS:
        i = index(item)
        rows.append({"task": task, "item": item, "model": CHEAP,
                     "correct": task == "u" or i % 3 != 0, "cost_usd": 1.0})
        rows.append({"task": task, "item": item, "model": STRONG, "correct": True,
                     "cost_usd": strong_cost(task, i)})
    return rows


def cascade_rows(task):
    return [{"task": task, "item": item, "model": CASCADE, "correct": True,
             "cost_usd": cascade_cost(task, index(item)),
             "escalated": escalates(task, index(item))} for item in ITEMS]


def planted_rows(tasks=("t", "u")):
    return [r for task in tasks for r in single_rows(task) + cascade_rows(task)]


def run(rows, **kw):
    kw.setdefault("bars", [BAR])
    kw.setdefault("seeds", SEEDS)
    kw.setdefault("flavors", ("cost_effective",))
    kw.setdefault("min_samples", 5)
    return evaluate(outcomes_from_rows(rows, slice_by=kw.pop("slice_by", None)), **kw)


def cal(seed):
    return [index(item) for item in split_items(ITEMS, seed)[0]]


def held(seed):
    return [index(item) for item in split_items(ITEMS, seed)[1]]


def cell_of(result, task, seed, bar=BAR):
    [cell] = [c for c in result["cells"]
              if c["task"] == task and c["seed"] == seed and c["bar"] == bar]
    return cell


def digest(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode("utf-8")).hexdigest()


def write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return str(path)


# --- guards: what v1.538 keeps (pass before and after) ---

def test_the_planted_split_is_what_the_expectations_assume():
    for seed in SEEDS:
        c = cal(seed)
        assert wilson_lower_bound(sum(i % 3 != 0 for i in c), len(c)) < BAR
        assert wilson_lower_bound(len(c), len(c)) > BAR
        assert len(c) >= 5 and held(seed)
    assert (len(cal(0)), len(held(0))) == (25, 35)
    assert sum(escalates("t", i) for i in cal(0)) == 10
    assert sum(escalates("t", i) for i in held(0)) == 18
    assert sum(cascade_cost("t", i) for i in held(0)) == 395.0


def test_a_run_without_a_cascade_row_keeps_the_v1_537_result():
    rows = single_rows("t") + single_rows("u")
    result = run(rows, flavors=("cost_effective", "cost_blind"))
    assert all(list(cell) == CELL_KEYS for cell in result["cells"])
    assert all(list(r) == ROW_KEYS for r in result["summary"])
    assert all(list(r) == ROW_KEYS[:2] + ["task"] + ROW_KEYS[2:] + ["routed_models"]
               for r in result["per_task"])
    assert digest(result) == V1_537_DIGEST


def test_the_cli_without_a_cascade_row_prints_no_escalation_column(tmp_path, capsys):
    path = write(tmp_path / "o.jsonl", single_rows("t") + single_rows("u"))
    assert main(["evaluate", "--outcomes", path, "--bar", "0.8", "--seeds", "3",
                 "--min-samples", "5"]) == 0
    out = capsys.readouterr().out
    assert "escalation_share" not in out
    assert hashlib.sha256(out.encode("utf-8")).hexdigest() == V1_537_CLI_DIGEST


V1_537_DIGEST = "25dc19a3fd666ef170a8aa5ea524c30a59cb4c02488ef6687bf6f531de6adc6a"
V1_537_CLI_DIGEST = "38f1791242bfebdde8d1d112d258c272ac3c8e3832f6238dc3b433ca013b1a40"


# --- 12.1: reading a cascade row ---

@RED
def test_outcome_gains_a_last_escalated_field_defaulting_to_none():
    o = Outcome("t", "q000", CHEAP, True, 1.0)
    assert o.escalated is None
    assert Outcome("t", "q000", CASCADE, True, 1.0, None, True).escalated is True


@RED
def test_a_cascade_rows_escalated_is_read_and_a_model_rows_is_none():
    outcomes = outcomes_from_rows(single_rows("t")[:2] + cascade_rows("t")[:2])
    assert [o.escalated for o in outcomes] == [None, None, True, False]


@RED
@pytest.mark.parametrize("value", [None, 1, 0, "true"])
def test_a_cascade_row_needs_a_bool_escalated(value):
    row = dict(cascade_rows("t")[0], escalated=value)
    with pytest.raises(ValueError, match="escalated"):
        outcomes_from_rows([row])
    del row["escalated"]
    with pytest.raises(ValueError, match="escalated"):
        outcomes_from_rows([row])


@RED
def test_a_cascade_row_carries_no_token_counts():
    row = dict(cascade_rows("t")[0], input_tokens=10, output_tokens=5)
    with pytest.raises(ValueError, match="token"):
        outcomes_from_rows([row])


@RED
@pytest.mark.parametrize("model", ["fiction/a>fiction/b", f"{CHEAP}>{CHEAP}@sig",
                                   "fiction/a>fiction/b@Bad", "a>b>c@sig"])
def test_a_model_holding_a_gt_sign_must_be_a_cascade_id(model):
    row = dict(cascade_rows("t")[0], model=model)
    with pytest.raises(ValueError, match="cascade id"):
        outcomes_from_rows([row])


@RED
@pytest.mark.parametrize("value", [True, False, None])
def test_only_a_cascade_row_carries_escalated(value):
    row = dict(single_rows("t")[0], escalated=value)
    with pytest.raises(ValueError, match="only a cascade row"):
        outcomes_from_rows([row])


# --- 12.3: the checks ---

@RED
@pytest.mark.parametrize("missing", [CHEAP, STRONG])
def test_a_cascade_needs_both_its_models_in_the_matrix(missing):
    rows = [r for r in planted_rows() if r["model"] != missing]
    with pytest.raises(ValueError, match=f"cascade '{CASCADE}'.*{missing}.*not a model"):
        run(rows)


@RED
def test_an_outcome_built_in_code_is_checked_as_a_row_is():
    outcomes = list(outcomes_from_rows(planted_rows()))
    k = next(n for n, o in enumerate(outcomes) if o.model == CASCADE)
    o = outcomes[k]
    outcomes[k] = Outcome(o.task, o.item, o.model, o.correct, o.cost_usd)
    with pytest.raises(ValueError, match="a cascade outcome needs escalated"):
        evaluate(outcomes, bars=[BAR], seeds=SEEDS, min_samples=5)
    outcomes[k] = o
    m = next(n for n, x in enumerate(outcomes) if x.model == CHEAP)
    x = outcomes[m]
    outcomes[m] = Outcome(x.task, x.item, x.model, x.correct, x.cost_usd, None, False)
    with pytest.raises(ValueError, match="only a cascade outcome"):
        evaluate(outcomes, bars=[BAR], seeds=SEEDS, min_samples=5)


# --- 12.3: routing and scoring ---

@RED
def test_each_cell_routes_t_to_the_cascade_and_u_to_the_cheap_model():
    result = run(planted_rows())
    for seed in SEEDS:
        t, u = cell_of(result, "t", seed), cell_of(result, "u", seed)
        assert t["models"]["routed"] == CASCADE and t["cleared"]
        assert u["models"]["routed"] == CHEAP and u["cleared"]
        h = held(seed)
        assert t["success"]["routed"] == 1.0
        assert t["cost_usd"]["routed"] == sum(cascade_cost("t", i) for i in h)
        assert u["cost_usd"]["routed"] == float(len(h))
    assert cell_of(result, "t", 0)["cost_usd"]["routed"] == 395.0


@RED
def test_the_baselines_range_over_the_single_models():
    result = run(planted_rows())
    for cell in result["cells"]:
        # the cascade ties fiction/strong on calibration successes at a lower mean cost
        assert cell["models"]["best_on_calibration"] == STRONG
        assert cell["models"]["cheapest"] == CHEAP
    rows = [dict(r, cost_usd=0.5) if r["model"] == CASCADE else r for r in planted_rows()]
    for cell in run(rows)["cells"]:
        h = held(cell["seed"])
        assert cell["models"]["cheapest"] == CHEAP
        # fiction/cheap's cost 1 where it is right, else fiction/strong's, never the 0.5
        assert cell["cost_usd"]["oracle"] == sum(
            1.0 if cell["task"] == "u" or i % 3 else strong_cost(cell["task"], i) for i in h)


@RED
def test_the_cascade_is_priced_by_5_2_over_a_registry_of_the_single_models(monkeypatch):
    seen = []

    class Recording(evaluate_module.Router):
        def select(self, *args, **kw):
            decision = super().select(*args, **kw)
            seen.append((sorted(m.id for m in self.registry.models()), kw, decision))
            return decision

    monkeypatch.setattr(evaluate_module, "Router", Recording)
    run(planted_rows(("t",)), seeds=[0])
    [(ids, kw, decision)] = seen
    assert ids == [CHEAP, STRONG] and kw == {"cascades": True}
    [cand] = [c for c in decision.candidates if c.model_id == CASCADE]
    c = cal(0)
    p = sum(escalates("t", i) for i in c) / len(c)
    mean_strong = sum(strong_cost("t", i) for i in c) / len(c)
    assert (cand.successes, cand.trials) == (25, 25)
    assert cand.list_cost == pytest.approx(1.0 + p * mean_strong) == pytest.approx(6.6)
    # not the cascade rows' own mean calibration cost
    assert sum(cascade_cost("t", i) for i in c) / len(c) == 9.0


@RED
def test_each_cell_holds_an_escalation_share_per_strategy():
    result = run(planted_rows())
    for seed in SEEDS:
        h = held(seed)
        t, u = cell_of(result, "t", seed), cell_of(result, "u", seed)
        assert list(t) == CELL_KEYS + ["escalation_share"]
        share_t = sum(escalates("t", i) for i in h) / len(h)
        share_u = sum(escalates("u", i) for i in h) / len(h)
        assert t["escalation_share"] == {s: (share_t if s in ("routed", f"model:{CASCADE}")
                                            else None) for s in STRATEGIES}
        assert u["escalation_share"] == {s: (share_u if s == f"model:{CASCADE}" else None)
                                         for s in STRATEGIES}
        assert list(t["escalation_share"]) == STRATEGIES
    assert cell_of(result, "t", 0)["escalation_share"]["routed"] == 18 / 35


@RED
def test_summary_and_per_task_rows_end_with_an_escalation_share():
    result = run(planted_rows())
    esc_t = sum(sum(escalates("t", i) for i in held(s)) for s in SEEDS)
    esc_u = sum(sum(escalates("u", i) for i in held(s)) for s in SEEDS)
    n = sum(len(held(s)) for s in SEEDS)
    summary = {r["strategy"]: r for r in result["summary"]}
    assert all(list(r) == ROW_KEYS + ["escalation_share"] for r in result["summary"])
    # routed counts only the cells routed to a cascade, here the three of task t
    assert summary["routed"]["escalation_share"] == esc_t / n
    assert summary[f"model:{CASCADE}"]["escalation_share"] == (esc_t + esc_u) / (2 * n)
    for s in ("oracle", "best_on_calibration", "cheapest", f"model:{CHEAP}", f"model:{STRONG}"):
        assert summary[s]["escalation_share"] is None
    per_task = {(r["task"], r["strategy"]): r for r in result["per_task"]}
    assert all(list(r) == ROW_KEYS[:2] + ["task"] + ROW_KEYS[2:]
               + ["routed_models", "escalation_share"] for r in result["per_task"])
    assert per_task["t", "routed"]["escalation_share"] == esc_t / n
    assert per_task["u", "routed"]["escalation_share"] is None
    assert per_task["u", f"model:{CASCADE}"]["escalation_share"] == esc_u / n
    assert per_task["t", "routed"]["routed_models"] == {CASCADE: 3}


@RED
def test_a_sliced_cell_routes_its_slices_with_the_cascades():
    rows = [dict(r, part="even" if index(r["item"]) % 2 == 0 else "odd")
            for r in planted_rows(("t",))]
    result = run(rows, slice_by="part", bars=[0.7])
    for seed in SEEDS:
        entries = cell_of(result, "t", seed, 0.7)["slices"]
        for name, parity in (("even", 0), ("odd", 1)):
            h = [i for i in held(seed) if i % 2 == parity]
            assert entries[name]["models"]["sliced"] == CASCADE
            assert entries[name]["cost_usd"]["sliced"] == sum(cascade_cost("t", i) for i in h)
            assert entries[name]["success"]["sliced"] == 1.0


# --- 12.4: the CLI ---

@RED
def test_the_cli_table_gains_an_escalation_share_column(tmp_path, capsys):
    path = write(tmp_path / "o.jsonl", planted_rows())
    assert main(["evaluate", "--outcomes", path, "--bar", "0.8", "--seeds", "3",
                 "--min-samples", "5", "--flavor", "cost_effective"]) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[0] == "bar 0.8, cost_effective"
    assert lines[1].split() == ["strategy", "success", "cost_usd", "below_bar_rate",
                                "cleared_rate", "bar_violation_rate", "escalation_share"]
    esc_t = sum(sum(escalates("t", i) for i in held(s)) for s in SEEDS)
    n = sum(len(held(s)) for s in SEEDS)
    routed = next(line.split() for line in lines if line.startswith("routed"))
    assert routed[-1] == f"{esc_t / n:.3f}"
    oracle = next(line.split() for line in lines if line.startswith("oracle"))
    assert oracle[-1] == "-"


@RED
def test_the_cli_json_keeps_the_escalation_share(tmp_path, capsys):
    path = write(tmp_path / "o.jsonl", planted_rows())
    assert main(["evaluate", "--outcomes", path, "--bar", "0.8", "--seeds", "3",
                 "--min-samples", "5", "--json"]) == 0
    result = json.loads(capsys.readouterr().out)
    assert "cells" not in result
    assert all("escalation_share" in r for r in result["summary"] + result["per_task"])
