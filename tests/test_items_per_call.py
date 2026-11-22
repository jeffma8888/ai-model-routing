"""Items per call: a judge's cost per item (DESIGN 4.1, 4.3, 5.2, 10, 12.1 and 13.3 v1.573, row VAR1c)."""

import dataclasses
import json
from datetime import date
from pathlib import Path

import pytest

from model_routing import (BELOW_BAR, DATA_DIR, PASSES, Completion, Executor, FakeProvider, Model,
                           Monitor, Registry, Router, Stats, Task, Variant, outcomes_from_rows)
from model_routing.delegation_eval import evaluate_delegation
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
JUDGE, BATCH4, BATCH16 = "v/judge", "v/judge@batch4", "v/judge@batch16"
PER_ITEM = "list_cost and routing_cost are per item; items is how many items one call of the route handles"


def judge_row(variants, model_id=JUDGE, family="v", price_in=1.0, price_out=4.0):
    return {"id": model_id, "family": family, "price_in": price_in, "price_out": price_out,
            "context_window": 100_000, "source": "https://example.org/prices", "variants": variants}


def write_registry(tmp_path, rows):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"version": "1", "as_of": "2026-01-01", "currency": "USD",
                                "models": rows}), encoding="utf-8")
    return path


def load(tmp_path, rows):
    return Registry.load(write_registry(tmp_path, rows))


def three_judges(tmp_path, k4=4, k16=16):
    variants = {"batch4": {} if k4 is None else {"items_per_call": k4},
                "batch16": {} if k16 is None else {"items_per_call": k16}}
    return load(tmp_path, [judge_row(variants)])


def grade_task(**overrides):
    fields = dict(name="grade", bar=0.85, min_samples=30, expected_input_tokens=2000,
                  expected_output_tokens=200)
    fields.update(overrides)
    return Task(**fields)


def measured_stats(tokens=True):
    """One call grades 1, 4 or 16 answers; every item carries its whole call's tokens (4.3 v1.573)."""
    stats = Stats()
    for model_id, (successes, trials), (call_in, call_out) in (
            (JUDGE, (95, 100), (2000, 200)),
            (BATCH4, (94, 100), (5000, 800)),
            (BATCH16, (78, 112), (17000, 3200))):
        extra = dict(input_tokens=call_in * trials, output_tokens=call_out * trials) if tokens else {}
        stats.add("grade", model_id, successes, trials, **extra)
    return stats


# 4.1: the field, the property and the registry key


def test_items_per_call_is_the_last_field_of_a_variant_and_defaults_to_1():
    assert [f.name for f in dataclasses.fields(Variant)][-2:] == ["context_policy", "items_per_call"]
    assert Variant("lean").items_per_call == 1
    assert Variant("batch4", items_per_call=4).items_per_call == 4
    assert Variant("b", "high", "agent 1", {}, 16).items_per_call == 16


@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, 4.0, "4", None, [4]])
def test_items_per_call_is_an_int_of_at_least_1_that_is_not_a_bool(value):
    with pytest.raises(ValueError):
        Variant("batch", items_per_call=value)


def test_a_model_s_items_per_call_is_its_variant_s_and_1_without_one():
    assert Model(JUDGE, "v", 1.0, 4.0, 8000).items_per_call == 1
    assert Model(BATCH4, "v", 1.0, 4.0, 8000, variant=Variant("batch4", items_per_call=4)
                 ).items_per_call == 4
    assert Model("v/judge@lean", "v", 1.0, 4.0, 8000).items_per_call == 1  # an id holding '@' alone


def test_registry_load_reads_items_per_call_and_a_null_is_absent(tmp_path):
    registry = load(tmp_path, [judge_row({"batch4": {"items_per_call": 4, "harness": "grader 1"},
                                          "plain": {"items_per_call": None}})])
    assert [m.items_per_call for m in registry.models] == [1, 4, 1]
    assert registry.get(BATCH4).variant == Variant("batch4", harness="grader 1", items_per_call=4)
    as_dict = dataclasses.asdict(registry.get(BATCH4))["variant"]
    assert list(as_dict)[-1] == "items_per_call" and as_dict["items_per_call"] == 4
    assert dataclasses.asdict(registry.get("v/judge@plain"))["variant"]["items_per_call"] == 1


@pytest.mark.parametrize("settings", [{"items_per_call": 0}, {"items_per_call": 2.5},
                                      {"items_per_call": 4.0}, {"items_per_call": True},
                                      {"items_per_call": "4"},
                                      {"provider_options": {"effort": "low"}}])
def test_a_bad_items_per_call_or_provider_options_names_the_file(tmp_path, settings):
    with pytest.raises(ValueError, match="models.json"):
        load(tmp_path, [judge_row({"batch": settings})])


def test_every_packaged_model_handles_one_item_per_call():
    registry = Registry.load(DATA_DIR / "models.json")
    assert {m.items_per_call for m in registry.models} == {1}


# 5.2: the cost per item, the row's test


def test_one_judge_at_1_4_and_16_items_a_call_picks_4(tmp_path):
    registry = three_judges(tmp_path)
    decision = Router(registry, {"grade": grade_task()}, measured_stats()).select("grade")
    by_id = {c.model_id: c for c in decision.candidates}
    assert [c.model_id for c in decision.candidates] == [JUDGE, BATCH4, BATCH16]
    assert {m: c.reason for m, c in by_id.items()} == {JUDGE: PASSES, BATCH4: PASSES,
                                                       BATCH16: BELOW_BAR}
    # hand computation at 1.0 and 4.0 USD per 1M tokens: one call of 1, 4 and 16 answers
    assert registry.get(JUDGE).cost(2000, 200) == pytest.approx(0.0028, rel=1e-12)
    assert registry.get(BATCH4).cost(5000, 800) == pytest.approx(0.0082, rel=1e-12)
    assert registry.get(BATCH16).cost(17000, 3200) == pytest.approx(0.0298, rel=1e-12)
    assert by_id[JUDGE].list_cost == registry.get(JUDGE).cost(2000, 200)
    assert by_id[BATCH4].list_cost == registry.get(BATCH4).cost(5000, 800) / 4
    assert by_id[BATCH16].list_cost == registry.get(BATCH16).cost(17000, 3200) / 16
    assert by_id[BATCH4].list_cost == pytest.approx(0.00205, rel=1e-12)
    assert by_id[BATCH16].list_cost == pytest.approx(0.0018625, rel=1e-12)
    assert by_id[BATCH4].routing_cost == by_id[BATCH4].list_cost
    # the cheapest per item is under the bar, so the pick is 4 a call, then the single-item judge
    assert by_id[BATCH16].quality_lb < 0.85 <= by_id[BATCH4].quality_lb < by_id[JUDGE].quality_lb
    assert (decision.primary, decision.fallbacks, decision.below_bar) == (BATCH4, (JUDGE,), False)
    # undivided, a call of 4 would cost more than the single-item call, so the division decides
    assert registry.get(BATCH4).cost(5000, 800) > registry.get(JUDGE).cost(2000, 200)


def test_cost_blind_reads_no_cost_and_picks_the_best_bound(tmp_path):
    registry = three_judges(tmp_path)
    decision = Router(registry, {"grade": grade_task()}, measured_stats()).select(
        "grade", flavor="cost_blind")
    assert decision.primary == JUDGE
    assert {c.routing_cost for c in decision.candidates} == {0.0}
    assert {c.model_id: c.list_cost for c in decision.candidates}[BATCH4] == pytest.approx(0.00205)


def test_at_the_task_s_sizes_a_call_of_k_items_is_priced_whole(tmp_path):
    registry = three_judges(tmp_path)
    decision = Router(registry, {"grade": grade_task()}, measured_stats(tokens=False)).select("grade")
    one_call = registry.get(JUDGE).cost(2000, 200)
    assert [c.list_cost for c in decision.candidates] == [one_call, one_call, one_call]
    assert decision.primary == JUDGE  # equal costs, the higher bound first (5.3)


def test_a_variant_without_items_per_call_is_priced_as_v1_572(tmp_path):
    stats = measured_stats()
    new = Router(three_judges(tmp_path, k4=1, k16=None), {"grade": grade_task()}, stats)
    (tmp_path / "old").mkdir()
    old = Router(three_judges(tmp_path / "old", k4=None, k16=None), {"grade": grade_task()}, stats)
    assert new.select("grade").to_dict() == old.select("grade").to_dict()
    by_id = {c.model_id: c.list_cost for c in old.select("grade").candidates}
    assert by_id[BATCH4] == old.registry.get(BATCH4).cost(5000, 800)  # one call, undivided


def test_the_cost_per_success_is_per_item(tmp_path):
    registry = three_judges(tmp_path)
    task = grade_task(failure_policy="retry_same")
    decision = Router(registry, {"grade": task}, measured_stats()).select("grade")
    primary = {c.model_id: c for c in decision.candidates}[decision.primary]
    assert decision.primary == BATCH4
    assert decision.expected_cost_per_success_usd == primary.list_cost / primary.quality_lb


# 12.1, 13.3 and 8.1: the costs that stay a call's, and the evaluator's per-item row


def test_a_token_form_outcome_of_a_route_of_k_items_costs_its_call_over_k(tmp_path):
    registry = three_judges(tmp_path)
    rows = [{"task": "grade", "item": "a", "model": BATCH4, "correct": True,
             "input_tokens": 5000, "output_tokens": 800},
            {"task": "grade", "item": "a", "model": JUDGE, "correct": True,
             "input_tokens": 2000, "output_tokens": 200},
            {"task": "grade", "item": "b", "model": BATCH4, "correct": False, "cost_usd": 0.5,
             "input_tokens": 5000, "output_tokens": 800}]
    got = [o.cost_usd for o in outcomes_from_rows(rows, registry)]
    assert got == [registry.get(BATCH4).cost(5000, 800) / 4, registry.get(JUDGE).cost(2000, 200), 0.5]


@pytest.mark.parametrize("work_calls", [1, 3])
def test_every_delegation_cost_prices_a_call_whole(tmp_path, work_calls):
    stats = measured_stats()
    stats.add("grade", "p/parent", 95, 100, input_tokens=300_000, output_tokens=30_000)
    decisions = []
    for name, k4 in (("per_item", 4), ("as_today", None)):
        (tmp_path / name).mkdir()
        registry = load(tmp_path / name, [
            judge_row({}, model_id="p/parent", family="p", price_in=3.0, price_out=15.0),
            judge_row({"batch4": {} if k4 is None else {"items_per_call": k4}})])
        router = Router(registry, {"grade": grade_task()}, stats)
        decisions.append(router.decide_delegation(
            "grade", "p/parent", context_tokens=4000, brief_tokens=300, result_tokens=100,
            work_calls=work_calls))
    assert decisions[0] == decisions[1]
    assert decisions[0].route is not None and decisions[0].route.primary == JUDGE


def test_the_held_out_delegation_costs_price_a_call_whole():
    """13.9 (review iter-419 should-fix 1): a delegate of 4 items a call changes no result."""
    rows = []
    for j in range(80):
        rows.append({"task": "t", "item": f"i{j:02d}", "model": "v/p", "correct": j % 4 != 0,
                     "input_tokens": 10, "output_tokens": j % 40})
        rows.append({"task": "t", "item": f"i{j:02d}", "model": "v/d@batch4", "correct": j % 5 != 0,
                     "input_tokens": 10, "output_tokens": 20})
    point = {"context_tokens": 0, "brief_tokens": 10, "result_tokens": 10, "carry_turns": 0,
             "inline_separate_call": False}
    results = []
    for k in (4, 1):
        registry = Registry([Model("v/p", "p", 3.0, 15.0, 100_000),
                             Model("v/d@batch4", "v", 1.0, 4.0, 100_000,
                                   variant=Variant("batch4", items_per_call=k))])
        results.append(evaluate_delegation(rows, registry, bars=[0.5], points=[point],
                                           seeds=range(3), min_samples=10, parents=["v/p"]))
    assert results[0] == results[1]
    assert results[0]["summary"]  # costs were compared, not an empty result


def test_the_delegate_exit_3_table_shows_no_items(tmp_path, capsys):
    """13.3 and 10 (review iter-419 should-fix 1): the delegate's costs are a call's, so no column."""
    files = cli_files(tmp_path, {"batch4": {"items_per_call": 4}, "batch16": {"items_per_call": 16}},
                      {"bar": 0.99})
    assert main(["delegate", "grade", "--parent", JUDGE, "--context-tokens", "4000",
                 "--brief-tokens", "300", "--result-tokens", "100", *files],
                today=date(2026, 1, 2)) == 3
    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert lines[0].startswith("error: ")
    header, rows, after = table_rows(lines)
    assert "items" not in header and [r["model"] for r in rows] == [JUDGE, BATCH4, BATCH16]
    assert PER_ITEM not in captured.err


def test_the_log_record_prices_the_whole_call(tmp_path):
    registry = three_judges(tmp_path)
    router = Router(registry, {"grade": grade_task()}, measured_stats())
    provider = FakeProvider({BATCH4: lambda messages: Completion("ok", 5000, 800)})
    monitor = Monitor()
    result = Executor(router, provider, monitor=monitor).call(
        "grade", [{"role": "user", "content": "four answers"}])
    record = monitor.records[0]
    assert (result.model, record["model"]) == (BATCH4, BATCH4)
    assert record["cost_usd"] == record["routing_cost_usd"] == registry.get(BATCH4).cost(5000, 800)


# 10: select prints the per-item cost


def cli_files(tmp_path, variants, task_extra=None):
    write_registry(tmp_path, [judge_row(variants)])
    task = {"name": "grade", "bar": 0.85, "min_samples": 30, "expected_input_tokens": 2000,
            "expected_output_tokens": 200}
    task.update(task_extra or {})
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [task]}), encoding="utf-8")
    measured_stats().save(tmp_path / "stats.json")
    return ["--registry", str(tmp_path / "models.json"), "--tasks", str(tmp_path / "tasks.json"),
            "--stats", str(tmp_path / "stats.json"), "--priors", str(tmp_path / "none.json")]


def table_rows(lines):
    at = next(i for i, line in enumerate(lines) if line.startswith("model "))
    header = lines[at].split()
    rows = []
    for line in lines[at + 2:]:
        if not line.strip():
            break
        cells = line.split()
        if cells[0] not in (JUDGE, BATCH4, BATCH16):
            break
        rows.append(dict(zip(header, cells)))
    return header, rows, at + 2 + len(rows)


def test_select_prints_the_items_column_and_the_per_item_cost(tmp_path, capsys):
    files = cli_files(tmp_path, {"batch4": {"items_per_call": 4}, "batch16": {"items_per_call": 16}})
    assert main(["select", "grade", *files], today=date(2026, 1, 2)) == 0
    lines = capsys.readouterr().out.splitlines()
    assert lines[2] == f"primary:   {BATCH4}"
    header, rows, after = table_rows(lines)
    assert header == ["model", "family", "measured", "quality_lb", "items", "list_cost",
                      "routing_cost", "reason"]
    registry = Registry.load(tmp_path / "models.json")
    assert [(r["model"], r["items"], r["list_cost"]) for r in rows] == [
        (JUDGE, "1", f"{registry.get(JUDGE).cost(2000, 200):.6f}"),
        (BATCH4, "4", f"{registry.get(BATCH4).cost(5000, 800) / 4:.6f}"),
        (BATCH16, "16", f"{registry.get(BATCH16).cost(17000, 3200) / 16:.6f}")]
    assert rows[1]["list_cost"] == "0.002050"
    assert lines[after:] == [PER_ITEM]


def test_select_without_a_route_of_several_items_prints_v1_572_s_table(tmp_path, capsys):
    files = cli_files(tmp_path, {"batch4": {"items_per_call": 1}, "batch16": {}})
    assert main(["select", "grade", *files], today=date(2026, 1, 2)) == 0
    out = capsys.readouterr().out
    header, rows, after = table_rows(out.splitlines())
    assert header == ["model", "family", "measured", "quality_lb", "list_cost", "routing_cost",
                      "reason"]
    assert PER_ITEM not in out and out.splitlines()[after:] == []


def test_select_s_exit_3_table_shows_the_items_too(tmp_path, capsys):
    files = cli_files(tmp_path, {"batch4": {"items_per_call": 4}, "batch16": {"items_per_call": 16}})
    assert main(["select", "grade", "--exclude", JUDGE, *files], today=date(2026, 1, 2)) == 3
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert lines[0].startswith("error: no model clears the bar 0.85")
    header, rows, after = table_rows(lines)
    assert "items" in header and [r["items"] for r in rows] == ["1", "4", "16"]
    assert lines[after] == PER_ITEM


def test_select_json_keeps_its_keys(tmp_path, capsys):
    files = cli_files(tmp_path, {"batch4": {"items_per_call": 4}, "batch16": {"items_per_call": 16}})
    assert main(["select", "grade", "--json", *files], today=date(2026, 1, 2)) == 0
    data = json.loads(capsys.readouterr().out)
    assert list(data["candidates"][0]) == ["model_id", "family", "successes", "trials", "quality_lb",
                                           "routing_cost", "list_cost", "eligible", "passes",
                                           "reason"]
    assert data["primary"] == BATCH4
    assert data["candidates"][1]["list_cost"] == pytest.approx(0.00205, rel=1e-12)


# the README and the production note


def test_the_readme_names_items_per_call():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    part = text.split("## How a model is chosen", 1)[1].split("\n## ", 1)[0]
    assert ('A variant whose calls each handle several items, a judge grading four answers in one call '
            'for example, sets `"items_per_call": 4`') in part
    assert "priced per item, its mean call over 4, and `select` shows an `items` column" in part


def test_the_production_note_states_items_per_call_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert "the number of criteria per call as a setting of a variant, priced per item, and" not in text
    assert "and the number of criteria per call measured as a setting of the judge" not in text
    assert ("A variant can also set how many items one call grades, `items_per_call`, and is then "
            "priced per item, its measured call cost over that number, so grading many criteria per "
            "call is measured as a setup of its own. The change still planned: the provider options a "
            "variant passes on each call.") in text
    assert ("The number of criteria per call is measured today as a setting of the judge, a variant "
            "with its own stats priced per item, as in the lesson on measured setups below. The "
            "changes: labels built from the items where every run of the chosen strong judges agrees, "
            "for a team with no human labels; and a self-consistency minimum, so a judge whose reruns "
            "disagree is excluded whatever its bound.") in text
