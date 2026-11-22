"""DESIGN 4.2, 5.1, 5.3, 8.1 and 10 v1.567 (row CPS1a): a task's failure policy and cost per success.

With `failure_policy` `retry_same` the routes that clear the bar are ranked by routing cost over
the Wilson lower bound, an estimate of the cost per success that assumes independent retries;
with the default `none` every decision, dict, record and CLI output is v1.566's.
"""

import dataclasses
import json
import re
from datetime import date
from pathlib import Path

import pytest

import model_routing
from model_routing import (Cascade, Executor, FakeProvider, Model, Monitor, Registry, Router,
                           Stats, Task, load_tasks, wilson_lower_bound)
from model_routing.cli import main
from model_routing.demo import _tasks_json
from model_routing.providers import Completion

RED = pytest.mark.xfail(strict=True, reason="v1.567 lands in the implementing commit (row CPS1a)")

A, B = "fiction/a", "fiction/b"
CASCADE = f"{A}>{B}@sig"
NOTE = Path(__file__).resolve().parent.parent / "research" / "production-lessons.md"
V1_566_KEYS = ["task", "flavor", "primary", "fallbacks", "below_bar", "basis", "candidates"]


def _registry():
    return Registry([
        Model(id=A, family="small", price_in=0.6, price_out=1.2, context_window=8000),
        Model(id=B, family="large", price_in=1.0, price_out=2.0, context_window=8000),
    ])


def _stats(a=(60, 100), b=(99, 100), task="t"):
    stats = Stats()
    stats.add(task, A, *a)
    stats.add(task, B, *b)
    return stats


def _task(policy=None, **overrides):
    fields = {"name": "t", "bar": 0.5, "min_samples": 10}
    fields.update(overrides)
    if policy is not None:
        fields["failure_policy"] = policy
    return Task(**fields)


def _router(policy=None, *, a=(60, 100), b=(99, 100), stats=None, **overrides):
    task = _task(policy, **overrides)
    return Router(_registry(), {"t": task}, _stats(a, b) if stats is None else stats)


def _by_id(decision):
    return {c.model_id: c for c in decision.candidates}


# ---- 4.2 the field ------------------------------------------------------------------------

@RED
def test_the_field_is_last_and_none_by_default():
    assert [f.name for f in dataclasses.fields(Task)][-2:] == ["cascades", "failure_policy"]
    assert Task("t", 0.5).failure_policy == "none"
    assert Task("t", 0.5, failure_policy="retry_same").failure_policy == "retry_same"


@RED
@pytest.mark.parametrize("value", ["retry", "", "RETRY_SAME", "None", None, 1, True])
def test_any_other_value_raises_valueerror_naming_the_task(value):
    with pytest.raises(ValueError, match=r"task 't'.*failure_policy"):
        Task("t", 0.5, failure_policy=value)


@RED
def test_load_tasks_reads_the_field_and_a_row_without_it_gets_none(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"tasks": [
        {"name": "r", "bar": 0.5, "failure_policy": "retry_same"}, {"name": "n", "bar": 0.5}]}))
    tasks = load_tasks(path)
    assert (tasks["r"].failure_policy, tasks["n"].failure_policy) == ("retry_same", "none")
    path.write_text(json.dumps({"tasks": [{"name": "x", "bar": 0.5, "failure_policy": "always"}]}))
    with pytest.raises(ValueError, match="failure_policy"):
        load_tasks(path)


def test_the_demo_tasks_file_has_no_key_for_the_default():
    assert "failure_policy" not in json.loads(_tasks_json(Task("t", 0.5)))["tasks"][0]


@RED
def test_the_demo_tasks_file_holds_the_key_when_it_is_not_the_default():
    row = json.loads(_tasks_json(Task("t", 0.5, failure_policy="retry_same")))["tasks"][0]
    assert row["failure_policy"] == "retry_same"


# ---- 5.3 the order, on the row's example -----------------------------------------------------

@RED
def test_the_row_example_none_picks_a_and_retry_same_picks_b():
    none = _router().select("t")
    assert (none.primary, none.fallbacks) == (A, (B,))
    assert (none.failure_policy, none.expected_cost_per_success_usd, none.pick_reason) == (
        "none", None, None)
    retry = _router("retry_same").select("t")
    assert (retry.primary, retry.fallbacks) == (B, (A,))
    assert retry.pick_reason == "cheaper_per_success" == model_routing.CHEAPER_PER_SUCCESS
    cands = _by_id(retry)
    # A costs 0.6 of B per call (1,000 in and 200 out at 0.6 and 1.2 against 1.0 and 2.0 per million)
    assert cands[A].list_cost == pytest.approx(0.00084) and cands[B].list_cost == pytest.approx(0.0014)
    assert cands[A].list_cost == pytest.approx(0.6 * cands[B].list_cost)
    # Wilson lower bounds at 0.95: 60 of 100 is 0.502003, just over the bar of 0.5; 99 of 100 is 0.945514
    assert cands[A].quality_lb == pytest.approx(0.502003, abs=1e-6)
    assert cands[B].quality_lb == pytest.approx(0.945514, abs=1e-6)
    # per success: A 0.00084 / 0.502003 = 0.00167330, B 0.0014 / 0.945514 = 0.00148068
    assert cands[A].list_cost / cands[A].quality_lb == pytest.approx(0.00167330, abs=1e-8)
    assert retry.expected_cost_per_success_usd == pytest.approx(0.00148068, abs=1e-8)
    assert retry.expected_cost_per_success_usd == cands[B].list_cost / cands[B].quality_lb


@RED
def test_the_same_first_pick_gives_no_reason_and_the_primarys_cost_per_success():
    decision = _router("retry_same", a=(99, 100), b=(60, 100)).select("t")
    assert (decision.primary, decision.fallbacks, decision.pick_reason) == (A, (B,), None)
    cand = _by_id(decision)[A]
    assert decision.expected_cost_per_success_usd == cand.list_cost / cand.quality_lb


@RED
def test_cost_blind_keeps_the_per_call_order_and_states_the_list_price_estimate():
    for policy in (None, "retry_same"):
        decision = _router(policy).select("t", flavor="cost_blind")
        assert (decision.primary, decision.fallbacks, decision.pick_reason) == (B, (A,), None)
    cand = _by_id(decision)[B]
    assert cand.routing_cost == 0.0
    assert decision.expected_cost_per_success_usd == cand.list_cost / cand.quality_lb


@RED
def test_a_zero_lower_bound_is_infinite_per_success_and_states_no_number():
    # bar 0: A passes on 0 of 10 with a bound of 0, the cheaper one per call
    none = _router(a=(0, 10), bar=0.0).select("t")
    assert none.primary == A
    retry = _router("retry_same", a=(0, 10), bar=0.0)
    decision = retry.select("t")
    assert (decision.primary, decision.fallbacks, decision.pick_reason) == (
        B, (A,), "cheaper_per_success")
    alone = retry.select("t", exclude_models=(B,))
    assert (alone.primary, alone.expected_cost_per_success_usd) == (A, None)
    assert alone.to_dict()["expected_cost_per_success_usd"] is None


@RED
def test_best_available_below_the_bar_keeps_its_order_and_states_the_estimate():
    for policy in (None, "retry_same"):
        decision = _router(policy, bar=0.99, on_no_model="best_available").select("t")
        assert (decision.primary, decision.fallbacks, decision.below_bar) == (B, (A,), True)
        assert decision.pick_reason is None
    cand = _by_id(decision)[B]
    assert decision.expected_cost_per_success_usd == cand.list_cost / cand.quality_lb


@RED
def test_a_cascade_is_priced_by_its_own_bound_and_cost():
    stats = _stats()
    stats.add("t", CASCADE, 98, 100, escalated=20)
    cascades = (Cascade(A, B, "sig"),)
    none = _router(stats=stats, cascades=cascades).select("t", cascades=True)
    assert none.primary == A
    decision = _router("retry_same", stats=stats, cascades=cascades).select("t", cascades=True)
    assert (decision.primary, decision.fallbacks) == (CASCADE, (B, A))
    cand = _by_id(decision)[CASCADE]
    # 0.00084 for A's call, plus 20 in 100 hand-ups of B reading 1,200 and writing 200: 0.2 * 0.0016
    assert cand.list_cost == pytest.approx(0.00116)
    assert cand.quality_lb == wilson_lower_bound(98, 100, 0.95)
    assert decision.expected_cost_per_success_usd == pytest.approx(0.00116 / 0.929988, rel=1e-6)


@RED
def test_a_slice_takes_the_tasks_policy():
    stats = _stats(task="t@deep")
    decision = _router("retry_same", stats=stats, slices={"deep": {"bar": 0.5}}).select(
        "t", slice="deep")
    assert (decision.primary, decision.pick_reason, decision.failure_policy) == (
        B, "cheaper_per_success", "retry_same")


@RED
def test_the_delegate_follows_the_policy_through_select():
    kwargs = dict(context_tokens=100, brief_tokens=50, result_tokens=50)
    assert _router().decide_delegation("t", B, **kwargs).route.primary == A
    assert _router("retry_same").decide_delegation("t", B, **kwargs).route.primary == B


# ---- 5.1 the dict -----------------------------------------------------------------------------

def test_the_default_dict_has_the_v1_566_keys():
    assert list(_router().select("t").to_dict()) == V1_566_KEYS


@RED
def test_the_dict_gains_the_keys_after_basis_only_off_the_default():
    data = _router("retry_same").select("t").to_dict()
    assert list(data) == [*V1_566_KEYS[:-1], "failure_policy", "expected_cost_per_success_usd",
                          "pick_reason", "candidates"]
    assert (data["failure_policy"], data["pick_reason"]) == ("retry_same", "cheaper_per_success")
    same = _router("retry_same", a=(99, 100), b=(60, 100)).select("t").to_dict()
    assert list(same) == [*V1_566_KEYS[:-1], "failure_policy", "expected_cost_per_success_usd",
                          "candidates"]


@RED
def test_the_reason_code_is_exported_after_cascade_unknown_model():
    names = model_routing.__all__
    assert names[names.index("CASCADE_UNKNOWN_MODEL") + 1] == "CHEAPER_PER_SUCCESS"
    assert model_routing.CHEAPER_PER_SUCCESS == "cheaper_per_success"


# ---- 8.1 the records --------------------------------------------------------------------------

def _records(policy):
    monitor = Monitor()
    provider = FakeProvider({m: (lambda messages: Completion("ok", 1000, 200)) for m in (A, B)})
    Executor(_router(policy), provider, monitor).call("t", [{"role": "user", "content": "x"}])
    return monitor.records


def test_records_of_the_default_have_no_new_key():
    assert all("expected_cost_per_success_usd" not in r for r in _records(None))


@RED
def test_records_end_with_the_decisions_cost_per_success_off_the_default():
    (record,) = _records("retry_same")
    assert record["model"] == B
    assert list(record)[-1] == "expected_cost_per_success_usd"
    assert record["expected_cost_per_success_usd"] == pytest.approx(0.0014 / 0.945514, rel=1e-6)


# ---- 10 the CLI -------------------------------------------------------------------------------

def _cli_files(tmp_path, policy):
    models = [dict(dataclasses.asdict(m), source="https://example.org/prices")
              for m in _registry().models]
    (tmp_path / "models.json").write_text(json.dumps(
        {"version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models}))
    row = {"name": "t", "bar": 0.5, "min_samples": 10}
    if policy is not None:
        row["failure_policy"] = policy
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [row]}))
    _stats().save(tmp_path / "stats.json")
    return ["--registry", str(tmp_path / "models.json"), "--tasks", str(tmp_path / "tasks.json"),
            "--stats", str(tmp_path / "stats.json"), "--priors", str(tmp_path / "none.json")]


def test_select_output_of_the_default_has_no_policy_line(tmp_path, capsys):
    assert main(["select", "t", *_cli_files(tmp_path, None)], today=date(2026, 1, 2)) == 0
    out = capsys.readouterr().out
    assert "policy:" not in out and "pick:" not in out


@RED
def test_select_prints_the_policy_line_and_the_pick_reason(tmp_path, capsys):
    files = _cli_files(tmp_path, "retry_same")
    assert main(["select", "t", *files], today=date(2026, 1, 2)) == 0
    lines = capsys.readouterr().out.splitlines()
    at = lines.index("below_bar: false")
    assert lines[at + 1] == ("policy:    retry_same, expected cost per success $0.001481 "
                             "(an estimate assuming independent retries)")
    assert lines[at + 2] == "pick:      cheaper_per_success"
    assert main(["select", "t", "--json", *files], today=date(2026, 1, 2)) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["pick_reason"] == "cheaper_per_success"
    assert data["expected_cost_per_success_usd"] == pytest.approx(0.00148068, abs=1e-8)


# ---- the note ---------------------------------------------------------------------------------

@RED
def test_the_harvey_line_names_the_shipped_policy_and_keeps_the_report_column_planned():
    text = NOTE.read_text(encoding="utf-8")
    harvey = text[text.index("## Harvey"):text.index("## Uber")]
    lines = [line for line in harvey.splitlines() if line.startswith("- In this library: ")]
    line = next(line for line in lines if "per success" in line)
    assert "It does not price a failure" not in line
    for phrase in ("`failure_policy`", "`retry_same`", "Wilson lower bound",
                   "assumes independent retries", "`cheaper_per_success`",
                   "The change still to come: cost per success as a column of the reports."):
        assert phrase in line, phrase
    assert re.search(r"cost per successful outcome as the `cost_effective` objective", text) is None
