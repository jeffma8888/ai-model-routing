"""DESIGN 5.1, 7, 8.1, 8.3 and 10 v1.584 (row SELF1c): records and reports name a self-hosted basis.

A registry model's `Candidate` holds its model's `pricing_basis`, a cascade's or procedure's None;
`RouteDecision.to_dict()` writes the key, last in a candidate, only for `"self_hosted"`. An attempt on
a self-hosted model writes `pricing_basis` right after `routing_cost_usd`; a procedure's closing
record never does. `report(by="pricing_basis")` groups a record without the key under `"list"`. The
`select` candidate table gains a `pricing_basis` column before `list_cost` only when a candidate is
self-hosted. Without one every decision, record and table keeps v1.583's bytes. The contract tests
were written under strict xfail and the implementing commit removed the marks; the unmarked guards
pin what v1.584 keeps and passed before and after it.
"""

import dataclasses
import hashlib
import io
import json
from contextlib import redirect_stderr, redirect_stdout
from pathlib import Path

import pytest

from model_routing import (Cascade, DATA_DIR, Candidate, Completion, Executor, FakeProvider, Model,
                           Monitor, Procedure, ProcedureResult, Registry, Router, Stats, Task,
                           Variant, report, run_demo, self_hosted_prices)
from model_routing.cli import PER_ITEM_LINE, _candidate_table, main

ROOT = Path(__file__).resolve().parents[1]
TS = "2026-11-22T00:00:00Z"
TEN = ["model_id", "family", "successes", "trials", "quality_lb", "routing_cost", "list_cost",
       "eligible", "passes", "reason"]
V1_583_KEYS = ["ts", "call_id", "task", "flavor", "model", "family", "attempt", "final", "outcome",
               "error", "latency_ms", "input_tokens", "output_tokens", "cost_usd",
               "routing_cost_usd", "below_bar", "basis", "tags", "slice", "prompt_tokens",
               "prompt_tokens_estimated"]
# the demo's calls.jsonl, unchanged since v1.536 (tests/test_procedure_executor.py)
DEMO_CALLS_SHA256 = "4f111326781939140bebe04e0841a66306cac48492bc6c95f4bc2211fa92b351"
HOSTED, LISTED = "acme/ft-7b", "v/m"
PRICE_IN, PRICE_OUT = self_hosted_prices(10, 36_000_000, 2_000_000, 0.5, 0.5)


def hosted():
    return Model(HOSTED, "acme", PRICE_IN, PRICE_OUT, 32_000, pricing_basis="self_hosted")


def registry():
    return Registry([Model(LISTED, "v", 1.0, 2.0, 100_000), hosted()])


def stats(hosted_counts=(95, 100), listed_counts=(99, 100)):
    planted = Stats()
    planted.add("t", HOSTED, *hosted_counts)
    planted.add("t", LISTED, *listed_counts)
    return planted


def task():
    return Task("t", bar=0.8, min_samples=10)


def decide(reg=None, planted=None, **kw):
    return Router(registry() if reg is None else reg, {"t": task()},
                  stats() if planted is None else planted).select("t", "cost_effective", **kw)


def executor(script, reg=None, planted=None):
    monitor = Monitor()
    ticks = iter(0.5 * i for i in range(1000))
    router = Router(registry() if reg is None else reg, {"t": task()},
                    stats() if planted is None else planted)
    return Executor(router, FakeProvider(script), monitor=monitor, clock=lambda: next(ticks),
                    now=lambda: TS, id_factory=lambda: "call-1"), monitor


def answer(text="ok"):
    return lambda messages: Completion(text, 400, 100)


MSGS = [{"role": "user", "content": "hi"}]


def test_the_candidate_field_is_after_the_ten_and_none_by_default():
    fields = {f.name: f for f in dataclasses.fields(Candidate)}
    # v1.588 (row CACHE1b) added the two cache fields after it, so it is the eleventh of thirteen
    assert list(fields)[:11] == TEN + ["pricing_basis"]
    assert fields["pricing_basis"].default is None


def test_a_model_candidate_holds_its_models_basis():
    decision = decide()
    assert decision.primary == HOSTED
    assert {c.model_id: c.pricing_basis for c in decision.candidates} == {
        LISTED: "list", HOSTED: "self_hosted"}


def test_to_dict_names_the_basis_last_and_only_for_a_self_hosted_candidate():
    data = decide().to_dict()
    listed, hosted_dict = data["candidates"]
    assert list(listed) == TEN
    assert list(hosted_dict) == TEN + ["pricing_basis"] and hosted_dict["pricing_basis"] == "self_hosted"
    assert json.loads(json.dumps(data)) == data


def test_a_procedure_candidate_holds_none_and_writes_no_key():
    proc = Procedure("poll", "v1", lambda value, call: ProcedureResult(call(value)), max_model_calls=1,
                     max_tool_calls=0, model=HOSTED)
    planted = stats()
    planted.add("t", proc.id, 99, 100, cost_usd=0.0001)
    decision = decide(planted=planted, procedures=[proc])
    by_id = {c.model_id: c for c in decision.candidates}
    assert by_id[proc.id].pricing_basis is None and by_id[HOSTED].pricing_basis == "self_hosted"
    assert "pricing_basis" not in decision.to_dict()["candidates"][-1]


def test_a_list_priced_decision_keeps_ten_keys_a_candidate():
    reg = Registry.load(DATA_DIR / "models.json")
    planted = Stats()
    for model in reg.models:
        planted.add("t", model.id, 99, 100)
    data = Router(reg, {"t": task()}, planted).select("t", "cost_effective").to_dict()
    assert data["candidates"] and all(list(c) == TEN for c in data["candidates"])


def test_a_self_hosted_attempt_names_its_basis_right_after_routing_cost():
    run, monitor = executor({HOSTED: answer()})
    run.call("t", MSGS)
    [rec] = monitor.records
    keys = V1_583_KEYS[:15] + ["pricing_basis"] + V1_583_KEYS[15:]
    assert list(rec) == keys and rec["pricing_basis"] == "self_hosted" and rec["model"] == HOSTED


def test_a_fallback_from_a_self_hosted_model_names_the_basis_on_its_attempt_only():
    def down(messages):
        from model_routing import ProviderError
        raise ProviderError("outage")
    run, monitor = executor({HOSTED: down, LISTED: answer()})
    run.call("t", MSGS)
    first, second = monitor.records
    assert first["model"] == HOSTED and first["pricing_basis"] == "self_hosted"
    assert second["model"] == LISTED and list(second) == V1_583_KEYS


def test_a_procedures_model_call_names_the_basis_and_its_closing_record_does_not():
    proc = Procedure("poll", "v1", lambda value, call: ProcedureResult("shaped " + call(value)),
                     max_model_calls=1, max_tool_calls=0, model=HOSTED)
    planted = stats(hosted_counts=(0, 100), listed_counts=(0, 100))
    planted.add("t", proc.id, 99, 100, cost_usd=0.0001)
    run, monitor = executor({HOSTED: answer()}, planted=planted)
    result = run.call("t", MSGS, procedures=[proc])
    assert result.model == proc.id
    model_call, closing = monitor.records
    assert model_call["model"] == HOSTED and model_call["pricing_basis"] == "self_hosted"
    assert closing["model"] == proc.id and "pricing_basis" not in closing


def cascade_task(cheap, strong):
    return Task("t", bar=0.8, min_samples=10, cascades=(Cascade(cheap, strong, "sig"),))


@pytest.mark.parametrize("cheap, strong, expected", [
    (HOSTED, LISTED, ["self_hosted", None]),     # the cheap attempt holds the key, the strong one not
    (LISTED, HOSTED, [None, "self_hosted"]),     # and the other way round
])
def test_each_attempt_of_a_cascade_names_the_basis_of_its_own_model(cheap, strong, expected):
    # review iter-432 should-fix 1: both branches of a mixed-basis cascade, not the shared path alone
    task_with = cascade_task(cheap, strong)
    planted = stats(hosted_counts=(0, 100), listed_counts=(0, 100))
    planted.add("t", task_with.cascades[0].id, 99, 100, escalated=10)
    monitor = Monitor()
    ticks = iter(0.5 * i for i in range(1000))
    router = Router(registry(), {"t": task_with}, planted)
    run = Executor(router, FakeProvider({cheap: answer("cheap"), strong: answer("strong")}),
                   monitor=monitor, clock=lambda: next(ticks), now=lambda: TS,
                   id_factory=lambda: "call-1")
    result = run.call("t", MSGS, signals={"sig": lambda text: text == "cheap"})
    assert result.model == strong
    assert [rec["model"] for rec in monitor.records] == [cheap, strong]
    assert [rec.get("pricing_basis") for rec in monitor.records] == expected


def test_a_delegated_hand_off_to_a_self_hosted_model_names_the_basis():
    # review iter-432 should-fix 1: .call_delegated writes the key too
    router = Router(registry(), {"t": task()}, stats())
    decision = router.decide_delegation("t", LISTED, "cost_effective", context_tokens=5000,
                                        brief_tokens=100, result_tokens=20)
    assert (decision.mode, decision.model) == ("delegate", HOSTED)
    monitor = Monitor()
    ticks = iter(0.5 * i for i in range(1000))
    run = Executor(router, FakeProvider({HOSTED: answer()}), monitor=monitor,
                   clock=lambda: next(ticks), now=lambda: TS, id_factory=lambda: "call-1")
    run.call_delegated(decision, MSGS)
    [rec] = monitor.records
    assert rec["model"] == HOSTED and rec["pricing_basis"] == "self_hosted"
    assert list(rec).index("pricing_basis") == list(rec).index("routing_cost_usd") + 1


def test_a_list_priced_attempt_keeps_v1_583_keys():
    run, monitor = executor({LISTED: answer()}, planted=stats(hosted_counts=(0, 100)))
    run.call("t", MSGS)
    [rec] = monitor.records
    assert list(rec) == V1_583_KEYS and rec["model"] == LISTED


def test_the_demo_log_keeps_its_bytes(tmp_path):
    run_demo(tmp_path)
    digest = hashlib.sha256((tmp_path / "calls.jsonl").read_bytes()).hexdigest()
    assert digest == DEMO_CALLS_SHA256


def test_report_by_pricing_basis_splits_the_spend():
    records = [
        {"call_id": "a", "attempt": 0, "final": True, "outcome": "ok", "model": HOSTED,
         "cost_usd": 0.25, "routing_cost_usd": 0.25, "pricing_basis": "self_hosted"},
        {"call_id": "b", "attempt": 0, "final": True, "outcome": "ok", "model": LISTED,
         "cost_usd": 1.0, "routing_cost_usd": 1.0},
        {"call_id": "c", "attempt": 0, "final": True, "outcome": "ok", "model": LISTED,
         "cost_usd": 0.5, "routing_cost_usd": 0.5},
    ]
    rows = report(records, by="pricing_basis")
    assert [(r["group"], r["calls"], r["cost_usd"]) for r in rows] == [
        ("list", 2, 1.5), ("self_hosted", 1, 0.25)]


def test_an_unknown_report_key_names_pricing_basis():
    # v1.640 (row PIN1b): basis and pinned_by follow it; tests/test_report_pinned.py pins the message
    with pytest.raises(ValueError, match=r"use model, task, flavor, family, pricing_basis, "):
        report([], by="nope")


def test_every_other_report_key_ignores_the_basis():
    records = [{"call_id": "a", "attempt": 0, "final": True, "outcome": "ok", "model": HOSTED,
                "family": "acme", "cost_usd": 0.25, "pricing_basis": "self_hosted"}]
    without = [{k: v for k, v in records[0].items() if k != "pricing_basis"}]
    for by in ("model", "task", "flavor", "family", "tag:team"):
        assert report(records, by=by) == report(without, by=by)


def write_files(tmp_path, reg_rows):
    (tmp_path / "models.json").write_text(json.dumps({"models": reg_rows}), encoding="utf-8")
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [
        {"name": "t", "bar": 0.8, "min_samples": 10}]}), encoding="utf-8")
    counts = [{"task": "t", "model": row["id"], "successes": 95, "trials": 100} for row in reg_rows]
    (tmp_path / "stats.json").write_text(json.dumps({"stats": counts}), encoding="utf-8")
    return ["--registry", str(tmp_path / "models.json"), "--tasks", str(tmp_path / "tasks.json"),
            "--stats", str(tmp_path / "stats.json"), "--priors", str(tmp_path / "none.json")]


def run_cli(argv):
    out, err = io.StringIO(), io.StringIO()
    with redirect_stdout(out), redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


HOSTED_ROW = {"id": HOSTED, "family": "acme", "context_window": 32_000, "pricing_basis": "self_hosted",
              "usd_per_hour": 10, "tokens_per_hour_in": 36_000_000, "tokens_per_hour_out": 2_000_000,
              "utilization": 0.5, "input_cost_share": 0.5}
LISTED_ROW = {"id": LISTED, "family": "v", "price_in": 1.0, "price_out": 2.0, "context_window": 100_000}


def test_select_shows_a_pricing_basis_column_before_list_cost(tmp_path):
    code, out, _ = run_cli(["select", "t"] + write_files(tmp_path, [LISTED_ROW, HOSTED_ROW]))
    assert code == 0
    table = out.split("\n\n", 1)[1].splitlines()
    header = table[0].split()
    assert header == ["model", "family", "measured", "quality_lb", "pricing_basis", "list_cost",
                      "routing_cost", "reason"]
    rows = {line.split()[0]: line.split()[4] for line in table[2:] if line.strip()}
    assert rows == {LISTED: "list", HOSTED: "self_hosted"}


def test_select_without_a_self_hosted_candidate_has_no_column(tmp_path):
    code, out, _ = run_cli(["select", "t"] + write_files(tmp_path, [LISTED_ROW]))
    assert code == 0 and "pricing_basis" not in out
    assert out.split("\n\n", 1)[1].splitlines()[0].split() == [
        "model", "family", "measured", "quality_lb", "list_cost", "routing_cost", "reason"]


def test_select_json_names_the_basis_only_on_the_self_hosted_candidate(tmp_path):
    code, out, _ = run_cli(["select", "t", "--json"] + write_files(tmp_path, [LISTED_ROW, HOSTED_ROW]))
    assert code == 0
    listed, hosted_dict = json.loads(out)["candidates"]
    assert "pricing_basis" not in listed and hosted_dict["pricing_basis"] == "self_hosted"


def test_the_basis_column_follows_items_and_a_cascade_cell_is_a_dash():
    # review iter-432 should-fix 2: the two optional columns together, in DESIGN 10 v1.584's order
    cascade = Cascade(HOSTED, LISTED, "sig")
    task_with = Task("t", bar=0.8, min_samples=10, cascades=(cascade,))
    planted = stats()
    planted.add("t", cascade.id, 99, 100, escalated=10)
    reg = Registry([Model(LISTED, "v", 1.0, 2.0, 100_000),
                    hosted(),
                    Model("v/m@batch4", "v", 1.0, 2.0, 100_000,
                          variant=Variant("batch4", items_per_call=4))])
    planted.add("t", "v/m@batch4", 95, 100)
    decision = Router(reg, {"t": task_with}, planted).select("t", "cost_effective", cascades=True)
    table = _candidate_table(decision.candidates, reg).splitlines()
    assert table[0].split() == ["model", "family", "measured", "quality_lb", "items",
                                "pricing_basis", "list_cost", "routing_cost", "reason"]
    cells = {line.split()[0]: line.split()[4:6] for line in table[2:] if line.startswith(("v/", "acme/"))}
    assert cells[LISTED] == ["1", "list"] and cells[HOSTED] == ["1", "self_hosted"]
    assert cells[cascade.id] == ["1", "-"]
    assert table[-1] == PER_ITEM_LINE


def test_the_exit_3_table_on_stderr_shows_the_column(tmp_path):
    # review iter-432 should-fix 2: the NoModelClearsBar table takes the same column
    files = write_files(tmp_path, [LISTED_ROW, HOSTED_ROW])
    (tmp_path / "stats.json").write_text(json.dumps({"stats": [
        {"task": "t", "model": LISTED, "successes": 1, "trials": 100},
        {"task": "t", "model": HOSTED, "successes": 1, "trials": 100}]}), encoding="utf-8")
    code, out, err = run_cli(["select", "t"] + files)
    assert code == 3 and out == ""
    header = err.splitlines()[1].split()
    assert header == ["model", "family", "measured", "quality_lb", "pricing_basis", "list_cost",
                      "routing_cost", "reason"]


def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for start, end, opening in [
            ("### 5.1 ", "### 5.2 ", "- v1.584 pricing basis (row SELF1c): `Candidate` gains a last field"),
            ("## 7. ", "## 8. ", "- v1.584 pricing basis (row SELF1c): an attempt on a self-hosted model"),
            ("### 8.1 ", "### 8.2 ", "- v1.584 `pricing_basis` (str, `\"self_hosted\"` wherever it is present)"),
            ("### 8.3 ", "## 9. ", "- v1.584 `by=\"pricing_basis\"` (row SELF1c)"),
            ("## 10. ", "## 11. ", "- v1.584 `select` (row SELF1c)")]:
        part = design[design.index(start):design.index(end)]
        assert part.count(opening) == 1, start
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.584 (")]
    assert len(mine) == 1 and "(5.1, 7, 8.1, 8.3, 10, row SELF1c)" in mine[0]
