"""DESIGN 8.3 and 10 v1.646 (row OPP1b): the savings report names the admitted route.

Given a `Router`, `opportunities(records, *, audits=None, target_cost_per_call=None, router=None)` adds to
each task's row the route `router.select(task, "cost_effective")` admits (its primary when the decision is
not below the bar, else None) and that route's `list_cost`, and with a target the labelled items a route at
the target needs before `select` admits it, at the task's audited success rate in the log:
`max(items_needed(rate, bar, confidence), min_samples)`. `report --opportunities --stats PATH
[--registry PATH] [--tasks PATH]` prints it; without `--stats` every v1.645 output keeps its bytes.
"""

import contextlib
import io
import json
from datetime import date
from pathlib import Path

import pytest

import model_routing
from model_routing import Model, Registry, Router, Stats, Task, items_needed, wilson_lower_bound
from model_routing.priors import Priors
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
CHEAP, MID = "fiction/cheap", "fiction/mid"
V1_645 = ["task", "calls", "days", "calls_per_day", "cost_usd", "spend_share", "cost_per_call_usd",
          "cost_per_day_usd"]
ROUTE = ["route", "route_list_cost_usd"]
TARGET = ["target_cost_per_call_usd", "saving_per_day_usd"]

# Prices per 1M tokens: cheap 1.0 in and 2.0 out, mid 3.0 and 6.0.
MODELS = [{"id": CHEAP, "family": "small", "price_in": 1.0, "price_out": 2.0, "context_window": 8000},
          {"id": MID, "family": "medium", "price_in": 3.0, "price_out": 6.0, "context_window": 8000}]
# extract: bar 0.8, min_samples 10, default sizes 1000 in and 200 out: cheap 40/40 and mid 40/40 both
#   pass (40 / (40 + z*z) = 0.912), so cost_effective takes cheap at (1000 * 1.0 + 200 * 2.0) / 1e6 = 0.0014.
# classify: bar 0.9, min_samples 50, 2000 in and 50 out: cheap 30/40 is under the bar (0.75 observed),
#   mid 100/100 passes (100 / (100 + z*z) = 0.963), at (2000 * 3.0 + 50 * 6.0) / 1e6 = 0.0063.
# summarize: bar 0.8, on_no_model refuse, nothing measured: NoModelClearsBar, no route.
# draft: bar 0.8, on_no_model best_available, cheap 10/40 under the bar: a below-bar decision, no route.
TASKS = [{"name": "extract", "bar": 0.8, "min_samples": 10},
         {"name": "classify", "bar": 0.9, "min_samples": 50, "expected_input_tokens": 2000,
          "expected_output_tokens": 50},
         {"name": "summarize", "bar": 0.8},
         {"name": "draft", "bar": 0.8, "on_no_model": "best_available"}]
COUNTS = [("extract", CHEAP, 40, 40), ("extract", MID, 40, 40), ("classify", CHEAP, 30, 40),
          ("classify", MID, 100, 100), ("draft", CHEAP, 10, 40)]


def rec(call_id, task, model, cost, ts):
    return {"call_id": call_id, "task": task, "flavor": "cost_effective", "model": model, "family": "x",
            "attempt": 0, "final": True, "outcome": "ok", "latency_ms": 10.0, "input_tokens": 100,
            "output_tokens": 20, "cost_usd": cost, "routing_cost_usd": 0.0, "ts": ts}


# extract: 2 calls of 0.002 over 2 days; classify: 4 of 0.01 on one day; summarize: 1 of 0.006;
# draft: 3 of 0.001 on one day. Spend per day: classify 0.04, summarize 0.006, draft 0.003, extract 0.002.
LOG = ([rec("e1", "extract", CHEAP, 0.002, "2026-11-01T09:00:00Z"),
        rec("e2", "extract", CHEAP, 0.002, "2026-11-02T09:00:00Z")]
       + [rec(f"c{n}", "classify", MID, 0.01, f"2026-11-05T0{n}:00:00Z") for n in range(1, 5)]
       + [rec("s1", "summarize", MID, 0.006, "2026-11-03T00:00:00Z")]
       + [rec(f"d{n}", "draft", CHEAP, 0.001, f"2026-11-04T0{n}:00:00Z") for n in range(1, 4)])
# extract 2 of 2 right (rate 1.0), classify 4 of 4 (1.0), summarize 1 of 1 (1.0), draft 2 of 3 (2/3).
AUDITS = {"e1": True, "e2": True, "c1": True, "c2": True, "c3": True, "c4": True, "s1": True,
          "d1": True, "d2": True, "d3": False}


def build(models=MODELS):
    registry = Registry([Model(m["id"], m["family"], m["price_in"], m["price_out"], m["context_window"])
                         for m in models])
    tasks = {t["name"]: Task(**t) for t in TASKS}
    stats = Stats()
    for task, model, successes, trials in COUNTS:
        stats.add(task, model, successes, trials)
    return Router(registry, tasks, stats)


def opportunities(*args, **kwargs):
    return model_routing.opportunities(*args, **kwargs)


def by_task(rows):
    return {r["task"]: r for r in rows}


# --- the function ------------------------------------------------------------------------------

def test_a_router_adds_the_admitted_route_and_its_list_cost():
    rows = opportunities(LOG, router=build())
    assert [r["task"] for r in rows] == ["classify", "summarize", "draft", "extract"]   # v1.645's sort
    assert [(r["route"], r["route_list_cost_usd"]) for r in rows] == [
        (MID, 0.0063), (None, None), (None, None), (CHEAP, 0.0014)]
    assert [list(r) for r in rows] == [V1_645 + ROUTE] * 4


def test_the_route_is_selects_primary_when_it_clears_the_bar():
    router = build()
    rows = by_task(opportunities(LOG, router=router))
    for name in ("extract", "classify"):
        decision = router.select(name, "cost_effective")
        assert not decision.below_bar and rows[name]["route"] == decision.primary
    decision = router.select("draft", "cost_effective")   # best_available: a measured route under the bar
    assert decision.below_bar and decision.primary == CHEAP and rows["draft"]["route"] is None
    with pytest.raises(model_routing.NoModelClearsBar):
        router.select("summarize", "cost_effective")


def test_items_to_admit_by_hand():
    rows = opportunities(LOG, router=build(), audits=AUDITS, target_cost_per_call=0.001)
    # rate 1.0: n / (n + z*z) >= bar, so 16 at 0.8 (4 * z*z = 15.37) and 35 at 0.9 (9 * z*z = 34.57, 4.3)
    assert items_needed(1.0, 0.8) == 16 and items_needed(1.0, 0.9) == 35
    items = {r["task"]: r["items_to_admit"] for r in rows}
    assert items == {"extract": 16,      # 16 over min_samples 10
                     "classify": 50,     # 35 raised to min_samples 50
                     "summarize": 30,    # 16 raised to the default min_samples 30, though no route clears now
                     "draft": None}      # 2/3 is under the bar 0.8, so no count clears
    assert [list(r) for r in rows] == [V1_645 + ["cost_per_success_usd"] + ROUTE + TARGET + ["items_to_admit"]] * 4


def test_the_target_sort_and_saving_stay_v1_645s():
    rows = opportunities(LOG, router=build(), target_cost_per_call=0.001)
    # classify 4 * 0.009 = 0.036, summarize 1 * 0.005, extract 1 * 0.001, draft 3 * 0 = 0
    assert [(r["task"], r["saving_per_day_usd"]) for r in rows] == [
        ("classify", 0.036), ("summarize", 0.005), ("extract", 0.001), ("draft", 0.0)]
    plain = opportunities(LOG, target_cost_per_call=0.001)
    assert [{k: r[k] for k in V1_645 + TARGET} for r in rows] == plain


def test_items_are_none_without_audits_or_an_audited_call():
    rows = opportunities(LOG, router=build(), target_cost_per_call=0.0)
    assert [r["items_to_admit"] for r in rows] == [None] * 4
    rows = by_task(opportunities(LOG, router=build(), audits={"e1": True}, target_cost_per_call=0.0))
    assert rows["extract"]["items_to_admit"] == 16 and rows["classify"]["items_to_admit"] is None


def test_a_retry_same_route_is_selects_primary_though_dearer_per_call():
    # review iter-501 should-fix 1. bar 0.2, min_samples 10: cheap 14/40 passes (Wilson lb 0.2213) and mid
    # 40/40 (0.9124); per call cheap 0.0014 < mid 0.0042, but per success (5.3 v1.567) cheap 0.0014 / 0.2213
    # = 0.006325 > mid 0.0042 / 0.9124 = 0.004603, so select's primary is mid and the row names it
    registry = build().registry
    stats = Stats()
    stats.add("retry", CHEAP, 14, 40)
    stats.add("retry", MID, 40, 40)
    router = Router(registry, {"retry": Task("retry", bar=0.2, min_samples=10, failure_policy="retry_same")}, stats)
    assert round(wilson_lower_bound(14, 40), 4) == 0.2213 and round(wilson_lower_bound(40, 40), 4) == 0.9124
    assert router.select("retry", "cost_effective").primary == MID
    (row,) = opportunities([rec("r1", "retry", CHEAP, 0.002, "2026-11-04T00:00:00Z")], router=router)
    assert (row["route"], row["route_list_cost_usd"]) == (MID, 0.0042)


def test_a_decision_on_a_prior_is_not_admitted():
    # review iter-501 nit 1: nothing measured, best_available and a prior: select gives cheap on its prior
    registry = build().registry
    task = Task("guess", bar=0.8, on_no_model="best_available", prior_category="code")
    router = Router(registry, {"guess": task}, Stats(), Priors({"code": {"scores": {CHEAP: 0.9}}}))
    decision = router.select("guess", "cost_effective")
    assert (decision.primary, decision.basis, decision.below_bar) == (CHEAP, "prior", True)
    (row,) = opportunities([rec("g1", "guess", CHEAP, 0.002, "2026-11-04T00:00:00Z")], router=router)
    assert (row["route"], row["route_list_cost_usd"]) == (None, None)


def test_a_bar_of_0_needs_min_samples_items():
    # review iter-501 nit 1: at bar 0 every count clears, so items_needed is 1 (4.3), raised to min_samples 10
    registry = build().registry
    router = Router(registry, {"zero": Task("zero", bar=0.0, min_samples=10)}, Stats())
    log = [rec("z1", "zero", CHEAP, 0.001, "2026-11-04T00:00:00Z"),
           rec("z2", "zero", CHEAP, 0.001, "2026-11-04T01:00:00Z")]
    (row,) = opportunities(log, router=router, audits={"z1": True, "z2": False}, target_cost_per_call=0.0)
    assert items_needed(0.5, 0.0) == 1 and row["items_to_admit"] == 10


def test_a_router_without_a_target_has_no_items_key():
    rows = opportunities(LOG, router=build(), audits=AUDITS)
    assert [list(r) for r in rows] == [V1_645 + ["cost_per_success_usd"] + ROUTE] * 4


def test_no_router_keeps_v1_645s_rows():
    assert opportunities(LOG, router=None) == opportunities(LOG)
    assert [list(r) for r in opportunities(LOG, router=None)] == [V1_645] * 4


def test_a_task_the_router_does_not_hold_is_a_value_error_naming_it():
    log = LOG + [rec("o1", "other", CHEAP, 0.001, "2026-11-04T00:00:00Z"),
                 rec("a1", "another", CHEAP, 0.001, "2026-11-04T00:00:00Z")]
    with pytest.raises(ValueError, match=r"\['another', 'other'\]"):
        opportunities(log, router=build())


@pytest.mark.parametrize("router", ["router", {}, 0, True])
def test_a_bad_router_is_a_value_error_before_any_record_is_read(router):
    with pytest.raises(ValueError, match="router must be None or a Router"):
        opportunities([{"task": "t", "ts": "never", "final": True}], router=router)


def test_an_empty_log_with_a_router_gives_no_rows():
    assert opportunities([], router=build(), target_cost_per_call=0.1) == []


# --- the CLI -----------------------------------------------------------------------------------

def run(argv, today=date(2026, 11, 25)):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, today=today)
    return code, out.getvalue(), err.getvalue()


def files(tmp_path, models=MODELS, log=LOG):
    paths = {name: tmp_path / f"{name}.json" for name in ("registry", "tasks", "stats")}
    paths["registry"].write_text(json.dumps({"models": models}), encoding="utf-8")
    paths["tasks"].write_text(json.dumps({"tasks": TASKS}), encoding="utf-8")
    build().stats.save(paths["stats"])
    paths["log"] = tmp_path / "calls.jsonl"
    paths["log"].write_text("".join(json.dumps(r) + "\n" for r in log), encoding="utf-8")
    paths["audits"] = tmp_path / "audits.jsonl"
    paths["audits"].write_text("".join(json.dumps({"call_id": c, "correct": v}) + "\n"
                                       for c, v in AUDITS.items()), encoding="utf-8")
    return {k: str(v) for k, v in paths.items()}


def argv(p, *extra):
    return ["report", "--log", p["log"], "--opportunities", "--stats", p["stats"], "--registry", p["registry"],
            "--tasks", p["tasks"], *extra]


def body(out):
    lines = out.rstrip("\n").split("\n")
    return lines[0].split(), [line.split() for line in lines[2:]]


def test_cli_stats_adds_the_route_columns(tmp_path):
    p = files(tmp_path)
    code, out, err = run(argv(p))
    assert (code, err) == (0, "")
    header, rows = body(out)
    assert header == V1_645 + ROUTE
    assert [(r[0], r[-2], r[-1]) for r in rows] == [
        ("classify", MID, "0.006300"), ("summarize", "n/a", "n/a"), ("draft", "n/a", "n/a"),
        ("extract", CHEAP, "0.001400")]
    code, out, err = run(argv(p, "--json"))
    assert (code, err) == (0, "") and json.loads(out) == opportunities(LOG, router=build())


def test_cli_audits_and_target_add_the_items(tmp_path):
    p = files(tmp_path)
    code, out, err = run(argv(p, "--audits", p["audits"], "--target-cost-per-call", "0.001"))
    assert (code, err) == (0, "")
    header, rows = body(out)
    assert header == V1_645 + ["cost_per_success_usd"] + ROUTE + TARGET + ["items_to_admit"]
    assert [(r[0], r[-1]) for r in rows] == [("classify", "50"), ("summarize", "30"), ("extract", "16"),
                                             ("draft", "n/a")]
    code, out, _ = run(argv(p, "--audits", p["audits"], "--target-cost-per-call", "0.001", "--json"))
    assert json.loads(out) == opportunities(LOG, router=build(), audits=AUDITS, target_cost_per_call=0.001)


def test_cli_defaults_to_the_packaged_registry_and_tasks(tmp_path):
    p = files(tmp_path, log=[rec("j1", "faithfulness_judge", CHEAP, 0.001, "2026-11-04T00:00:00Z")])
    Stats().save(p["stats"])
    code, out, err = run(["report", "--log", p["log"], "--opportunities", "--stats", p["stats"]])
    assert code == 0   # a packaged price whose stated end date has passed warns, as select warns on it
    assert err == "" or all(line.startswith("warning: list price of ") for line in err.splitlines())   # nit 2
    header, rows = body(out)
    assert header == V1_645 + ROUTE and rows[0][0] == "faithfulness_judge" and rows[0][-2:] == ["n/a", "n/a"]


def test_cli_warns_on_an_expired_price_of_an_eligible_model(tmp_path):
    models = [dict(MODELS[0], price_valid_until="2026-11-01"), MODELS[1]]
    p = files(tmp_path, models=models)
    code, out, err = run(argv(p))
    assert code == 0 and out
    assert err == (f"warning: list price of {CHEAP} was stated valid through 2026-11-01; check the vendor "
                   "page and update the registry\n")
    assert run(argv(p), today=date(2026, 11, 1))[2] == ""
    # without --stats no registry is read, so nothing warns
    assert run(["report", "--log", p["log"], "--opportunities"])[2] == ""


@pytest.mark.parametrize("extra, word", [
    (["--stats", "s.json"], "--stats"),
    (["--registry", "r.json"], "--registry"),
    (["--tasks", "t.json"], "--tasks"),
    (["--opportunities", "--registry", "r.json"], "--registry"),
    (["--opportunities", "--tasks", "t.json"], "--tasks"),
])
def test_cli_flag_conflicts_exit_2_before_any_path_is_read(tmp_path, extra, word):
    code, out, err = run(["report", "--log", str(tmp_path / "missing.jsonl")] + extra)
    assert code == 2 and out == ""
    assert err.count("\n") == 1 and err.startswith("error: ") and word in err
    assert "missing.jsonl" not in err


def test_cli_a_missing_stats_file_exits_2(tmp_path):
    p = files(tmp_path)
    code, out, err = run(argv(p)[:5] + [str(tmp_path / "none.json")] + argv(p)[6:])
    assert code == 2 and out == "" and "none.json" in err and err.count("\n") == 1


def test_cli_a_log_task_no_task_file_holds_exits_2(tmp_path):
    p = files(tmp_path, log=LOG + [rec("o1", "other", CHEAP, 0.001, "2026-11-04T00:00:00Z")])
    code, out, err = run(argv(p))
    assert code == 2 and out == "" and "'other'" in err and err.count("\n") == 1


def test_cli_without_stats_keeps_v1_645s_output(tmp_path):
    p = files(tmp_path)
    code, out, err = run(["report", "--log", p["log"], "--opportunities", "--json"])
    assert (code, err) == (0, "") and json.loads(out) == opportunities(LOG)
    code, out, _ = run(["report", "--log", p["log"], "--opportunities"])
    assert body(out)[0] == V1_645


def test_cli_no_routed_record_prints_the_header_alone(tmp_path):
    p = files(tmp_path, log=[])
    code, out, err = run(argv(p, "--target-cost-per-call", "0"))
    assert (code, err) == (0, "")
    assert body(out) == (V1_645 + ROUTE + TARGET + ["items_to_admit"], [])


# --- the spec and the note ---------------------------------------------------------------------

def test_design_and_changelog_state_v1_646():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    head = "- v1.646 `opportunities(records, *, audits=None, target_cost_per_call=None, router=None)` (row OPP1b)"
    assert eight3.count(head) == 1
    assert eight3.index("- v1.645 `opportunities(") < eight3.index(head)
    # v1.654 (row OPP1c) names itself in place of the row
    assert "admitted, which v1.646 adds (row OPP1b), and the README sentence, which v1.654 adds (5.2)." in eight3
    assert "`max(items_needed(rate, task.bar, task.confidence), task.min_samples)`" in eight3
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    assert ten.index("  - v1.645 `report --log PATH --opportunities") < ten.index(
        "  - v1.646 `report --log PATH --opportunities --stats PATH [--registry PATH] [--tasks PATH]")
    lines = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").rstrip("\n").split("\n")
    [line] = [x for x in lines if x.startswith("- v1.646 (")]
    assert line.startswith("- v1.646 (2026-11-25): spec, code and tests (8.3, 10, row OPP1b).")
    assert len(line.encode()) <= 600


def test_the_note_no_longer_calls_the_route_or_the_items_planned():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert "It does not yet name the cheapest route that clears the bar." not in note
    assert "would need to be admitted is planned" not in note
