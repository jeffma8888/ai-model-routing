"""DESIGN 8.1 v1.658 (row LOG1): one list of every record key, which the executor's records are checked against.

Two tables in DESIGN 8.1 are the record format: every key an attempt record or a budget record may hold, in
the order a record holds them, with its JSON type. model_routing/monitor.py holds the same two lists once, as
`RECORD_KEYS` and `BUDGET_RECORD_KEYS`. A record holds some of its list's keys, in the list's order, each value
of a listed type, and no other key; a record with a `budget_event` key is a budget record.
"""

import dataclasses
import itertools
import re
from pathlib import Path

import pytest

from model_routing import (Budget, BudgetExceeded, BudgetLedger, Cascade, Completion, Executor, FakeProvider, Model,
                           Monitor, Policy, Procedure, ProcedureResult, ProviderError, Registry, Router, Stats, Task,
                           load_records)
from model_routing.demo import run_demo
from model_routing.monitor import BUDGET_RECORD_KEYS, RECORD_KEYS

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "judge"}]
TS = "2026-11-25T00:00:00Z"
REGION = "eu-west"
JSON_TYPES = {
    "string": lambda v: isinstance(v, str),
    "integer": lambda v: isinstance(v, int) and not isinstance(v, bool),
    "number": lambda v: isinstance(v, (int, float)) and not isinstance(v, bool),
    "boolean": lambda v: isinstance(v, bool),
    "null": lambda v: v is None,
    "object": lambda v: isinstance(v, dict),
    "array": lambda v: isinstance(v, list),
}


def problems(record):
    """What breaks the format in one record, [] when nothing does (DESIGN 8.1 v1.658)."""
    listed = BUDGET_RECORD_KEYS if "budget_event" in record else RECORD_KEYS
    order = [key for key, _ in listed]
    types = dict(listed)
    found = [f"{key} is not in the list" for key in record if key not in types]
    known = [key for key in record if key in types]
    if known != sorted(known, key=order.index):
        found.append(f"keys out of order: {known}")
    for key in known:
        if not any(JSON_TYPES[name](record[key]) for name in types[key]):
            found.append(f"{key}: {record[key]!r} is not {' or '.join(types[key])}")
    return found


# --- the scenarios -------------------------------------------------------------------------------

def model(model_id, price, family="x", **extra):
    return Model(model_id, family, price, 2 * price, 100_000, regions=(REGION,), zero_data_retention=True, **extra)


MODELS = [model("x/small", 0.5), model("x/mid", 1.0), model("x/big", 2.0)]
COUNTS = {"x/small": 95, "x/mid": 98, "x/big": 100}


def router(models=MODELS, counts=COUNTS, extra_stats=(), **task_extra):
    fields = dict(bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200)
    fields.update(task_extra)
    stats = Stats()
    for model_id, successes in counts.items():
        stats.add("t", model_id, successes, 100)
    for args, kwargs in extra_stats:
        stats.add("t", *args, **kwargs)
    return Router(Registry(models), {"t": Task(name="t", **fields)}, stats)


def ok(messages):
    return Completion("ok", 1000, 200)


def cached(messages):
    return Completion("ok", 1000, 200, cached_input_tokens=800, cache_write_tokens=100)


def outage(messages):
    raise ProviderError("outage")


class Run:
    """One executor whose monitor writes to its own log file; ``.records`` reads that file back."""

    def __init__(self, path, route, script=None, ledger=None, **kwargs):
        ticks, ids = itertools.count(), itertools.count()
        self.path = path
        provider = FakeProvider(script if script is not None else {m.id: ok for m in MODELS})
        self.ex = Executor(route, provider, monitor=Monitor(path), clock=lambda: float(next(ticks)),
                           now=lambda: TS, id_factory=lambda: f"call-{next(ids)}", ledger=ledger, **kwargs)

    @property
    def records(self):
        return load_records(self.path)


def scenarios(tmp):
    """Each scenario's records, read back from its log file, by name."""
    out = {}
    count = itertools.count()

    def run(*args, **kwargs):
        return Run(tmp / f"log-{next(count)}.jsonl", *args, **kwargs)

    r = run(router())
    r.ex.call("t", MESSAGES)
    r.ex.call("t", MESSAGES, flavor="cost_blind")
    out["plain"] = r.records

    r = run(router(), {"x/small": outage, "x/mid": ok, "x/big": ok})
    r.ex.call("t", MESSAGES)
    out["fallback"] = r.records

    weak = [model("x/small", 0.5), model("x/weak", 0.2)]
    r = run(router(models=weak, counts={"x/small": 95, "x/weak": 60}, fallback_below_bar=True),
            {"x/small": outage, "x/weak": ok})
    r.ex.call("t", MESSAGES)
    out["below-bar fallback"] = r.records

    cascade = Cascade("x/small", "x/big", "sig")
    r = run(router(counts={"x/small": 50, "x/big": 100}, cascades=(cascade,),
                   extra_stats=[((cascade.id, 99, 100), {"escalated": 50})]))
    r.ex.call("t", MESSAGES, signals={"sig": lambda text: True})
    out["cascade"] = r.records

    proc = Procedure("shape", "1", lambda value, call: ProcedureResult("shaped " + call(value), tool_calls=1,
                                                                       tool_cost_usd=0.0001),
                     max_model_calls=1, max_tool_calls=1, model="x/small")
    r = run(router(counts={"x/small": 50, "x/big": 100}, extra_stats=[((proc.id, 100, 100), {"cost_usd": 0.0001})]))
    r.ex.call("t", MESSAGES, procedures=(proc,))
    out["procedure"] = r.records

    def broken(value, call):
        call(value)
        raise RuntimeError("the tool is down")

    bad = Procedure("shape", "2", broken, max_model_calls=1, max_tool_calls=1, model="x/small")
    r = run(router(counts={"x/small": 50, "x/big": 100}, extra_stats=[((bad.id, 100, 100), {"cost_usd": 0.0001})]))
    r.ex.call("t", MESSAGES, procedures=(bad,))
    out["procedure that raised"] = r.records

    r = run(router())
    r.ex.call("t", MESSAGES, pin_route="x/mid", pinned_by="ops")
    out["pinned"] = r.records

    r = run(router())
    r.ex.call("t", MESSAGES, policy=Policy(region=REGION, name="acme"), pin_route="x/mid", pinned_by="ops")
    r.ex.call("t", MESSAGES, policy=Policy(region=REGION, name="acme"))
    out["named policy"] = r.records

    r = run(router(shadow_rate=1.0), random=lambda: 0.0)
    r.ex.call("t", MESSAGES)
    r.ex.call("t", MESSAGES, validate=lambda text: True)
    out["shadowed"] = r.records

    r = run(router(), ledger=BudgetLedger([Budget("note", 0.0000001, "warn", window="day")]))
    r.ex.call("t", MESSAGES, policy=Policy(region=REGION, name="acme"))
    out["warn budget"] = r.records

    r = run(router(), ledger=BudgetLedger([Budget("cap", 0.0000001, "refuse")]))
    with pytest.raises(BudgetExceeded):
        r.ex.call("t", MESSAGES)
    out["refused budget"] = r.records

    # cost_blind routes x/big first; its hold at 1,000 prompt tokens (0.0028) passes 0.002 and x/mid's (0.0014) fits
    r = run(router(), ledger=BudgetLedger([Budget("d", 0.002, "downgrade")]))
    r.ex.call("t", MESSAGES, flavor="cost_blind", prompt_tokens=1000)
    out["downgrade budget"] = r.records

    r = run(router(shadow_rate=1.0), ledger=BudgetLedger([Budget("cap", 0.001, "refuse")]), random=lambda: 0.0)
    r.ex.call("t", MESSAGES, policy=Policy(region=REGION, name="acme"))
    out["shadow's refused budget"] = r.records

    other = MODELS + [model("y/cheap", 0.1, family="y")]
    # the parent under the bar, so the work is handed off to the route (reason `parent_below_bar`)
    route = router(models=other, counts=dict(COUNTS, **{"y/cheap": 60}))
    decision = route.decide_delegation("t", "y/cheap", context_tokens=2000, brief_tokens=1000, result_tokens=1000,
                                       inline_separate_call=False)
    assert (decision.mode, decision.reason) == ("delegate", "parent_below_bar")
    r = run(route, {m.id: ok for m in other})
    r.ex.call_delegated(decision, MESSAGES, tags={"team": "a"})
    out["delegated"] = r.records

    hosted = [model("x/own", 0.05, pricing_basis="self_hosted"), model("x/big", 2.0)]
    r = run(router(models=hosted, counts={"x/own": 95, "x/big": 100}), {"x/own": ok, "x/big": ok})
    r.ex.call("t", MESSAGES)
    out["self-hosted"] = r.records

    warm = [model("x/small", 0.5, price_cached_in=0.05, price_cache_write=0.625), model("x/big", 2.0)]
    r = run(router(models=warm, counts={"x/small": 95, "x/big": 100}), {"x/small": cached, "x/big": ok})
    r.ex.call("t", MESSAGES)
    out["cached"] = r.records

    r = run(router(failure_policy="retry_same"))
    r.ex.call("t", MESSAGES)
    out["retry_same"] = r.records
    return out


@pytest.fixture(scope="module")
def logs(tmp_path_factory):
    return scenarios(tmp_path_factory.mktemp("record-keys"))


@pytest.fixture(scope="module")
def demo_records(tmp_path_factory):
    out = tmp_path_factory.mktemp("record-keys-demo") / "demo"
    run_demo(out)
    return load_records(out / "calls.jsonl")


# --- the records ---------------------------------------------------------------------------------

def test_each_scenario_writes_records(logs):
    assert all(logs[name] for name in logs), [name for name in logs if not logs[name]]


@pytest.mark.parametrize("name", [
    "plain", "fallback", "below-bar fallback", "cascade", "procedure", "procedure that raised", "pinned",
    "named policy", "shadowed", "warn budget", "refused budget", "downgrade budget", "shadow's refused budget",
    "delegated", "self-hosted", "cached", "retry_same"])
def test_every_record_of_the_scenario_holds_listed_keys_in_order_with_listed_types(logs, name):
    for record in logs[name]:
        assert problems(record) == [], (name, record)


def test_the_scenarios_carry_the_keys_they_exist_for(logs):
    def keys(name):
        return set().union(*(record.keys() for record in logs[name]))
    assert "error" in keys("fallback") and logs["fallback"][0]["error"] == "ProviderError: outage"
    assert logs["below-bar fallback"][-1]["below_bar_fallback"] is True
    assert {"cascade", "escalated"} <= keys("cascade")
    assert {"procedure", "procedure_version", "model_calls", "tool_calls", "tool_cost_usd"} <= keys("procedure")
    [closing] = [r for r in logs["procedure that raised"] if "model_calls" in r]
    assert (closing["outcome"], closing["tool_calls"], closing["tool_cost_usd"]) == ("error", None, None)
    assert {"pinned_by"} <= keys("pinned") and {"policy"} <= keys("named policy")
    assert [r["checked"] for r in logs["shadowed"]] == [False, False, True, True]
    assert {r["budget_event"] for r in logs["warn budget"] if "budget_event" in r} == {"warn"}
    assert [r["budget_event"] for r in logs["refused budget"]] == ["refused"]
    assert any("budget_moves" in r for r in logs["downgrade budget"])
    assert any(r.get("budget_event") == "refused" and r["shadow"] for r in logs["shadow's refused budget"])
    assert all(r["tags"]["delegated"] == "true" and "prompt_tokens" not in r for r in logs["delegated"])
    assert logs["self-hosted"][0]["pricing_basis"] == "self_hosted"
    assert (logs["cached"][0]["cached_input_tokens"], logs["cached"][0]["cache_write_tokens"]) == (800, 100)
    assert "expected_cost_per_success_usd" in keys("retry_same")


def test_the_scenarios_together_carry_every_key_of_both_lists(logs):
    records = [record for name in logs for record in logs[name]]
    attempts = [r for r in records if "budget_event" not in r]
    budgets = [r for r in records if "budget_event" in r]
    assert set().union(*(r.keys() for r in attempts)) == {key for key, _ in RECORD_KEYS}
    assert set().union(*(r.keys() for r in budgets)) == {key for key, _ in BUDGET_RECORD_KEYS}


def test_every_record_of_the_demo_log_holds_listed_keys_in_order_with_listed_types(demo_records):
    assert demo_records
    assert [(i, problems(r)) for i, r in enumerate(demo_records) if problems(r)] == []


# --- the check fails a record that breaks the format (mutants) -----------------------------------

def test_a_key_the_list_lacks_fails_the_check(logs):
    record = dict(logs["plain"][0], region="eu-west")
    assert problems(record) == ["region is not in the list"]
    budget = dict(logs["refused budget"][0], flavor="cost_effective")
    assert problems(budget) == ["flavor is not in the list"]


def test_two_keys_swapped_fail_the_check(logs):
    record = logs["plain"][0]
    keys = list(record)
    keys[1], keys[2] = keys[2], keys[1]
    assert problems({key: record[key] for key in keys})[0].startswith("keys out of order: ")


@pytest.mark.parametrize("key,value", [("attempt", "0"), ("attempt", True), ("final", 1), ("cost_usd", None),
                                       ("tags", []), ("slice", 3), ("error", 0)])
def test_a_value_of_another_type_fails_the_check(logs, key, value):
    record = dict(logs["plain"][0])
    record[key] = value
    assert len(problems(record)) == 1 and problems(record)[0].startswith(f"{key}: ")


def test_a_budget_record_is_checked_against_its_own_list(logs):
    (refused,) = logs["refused budget"]
    keys = [key for key in refused]
    assert keys.index("model") > keys.index("budget_event")
    assert problems(refused) == []
    assert problems({k: v for k, v in refused.items() if k != "budget_event"}) != []


# --- the code's lists and the DESIGN tables ------------------------------------------------------

def eight1():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    return design[design.index("### 8.1 "):design.index("### 8.2 ")]


def table(title):
    text = eight1()
    rows = text[text.index(f"\n{title}\n\n| Key | JSON type | Carried by | Since |\n|---|---|---|---|\n"):]
    rows = rows.split("|---|---|---|---|\n", 1)[1].split("\n\n", 1)[0].splitlines()
    out = []
    for row in rows:
        match = re.fullmatch(r"\| `([a-z_]+)` \| ([a-z ]+?) \| (.+?) \| (base|v1\.\d+) \|", row)
        assert match, row
        out.append((match[1], tuple(match[2].split(" or ")), match[4]))
    return out


def test_the_lists_are_tuples_of_key_and_json_types():
    for listed in (RECORD_KEYS, BUDGET_RECORD_KEYS):
        assert isinstance(listed, tuple)
        assert all(isinstance(key, str) and isinstance(types, tuple) and types and set(types) <= set(JSON_TYPES)
                   for key, types in listed)
        assert len({key for key, _ in listed}) == len(listed)


@pytest.mark.parametrize("title,listed", [("Attempt records:", RECORD_KEYS), ("Budget records:", BUDGET_RECORD_KEYS)])
def test_each_design_table_equals_the_code_list_key_and_types_for_key(title, listed):
    assert [(key, types) for key, types, _ in table(title)] == list(listed)


@pytest.mark.parametrize("title", ["Attempt records:", "Budget records:"])
def test_each_since_names_the_dated_bullet_that_adds_the_key_or_the_base_line(title):
    text = eight1()
    lines = text.splitlines()
    base = lines[1]
    for key, _, since in table(title):
        if since == "base":
            assert f"`{key}` (" in base, key
        else:
            [bullet] = [line for line in lines if line.startswith(f"- {since} ")]
            assert f"`{key}`" in bullet, (key, since)


def test_the_lists_are_not_exported():
    import model_routing
    assert "RECORD_KEYS" not in model_routing.__all__ and "BUDGET_RECORD_KEYS" not in model_routing.__all__


def test_design_states_v1_658_and_the_changelog_the_version():
    text = eight1()
    assert text.count("\n- v1.658 the record format (row LOG1): the two tables below are the record format. ") == 1
    assert text.count("\nAttempt records:\n\n| Key |") == 1 and text.count("\nBudget records:\n\n| Key |") == 1
    assert text.count("so no one order fits both") == 1
    [line] = [x for x in (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines() if x.startswith("- v1.658 (")]
    assert line.startswith("- v1.658 (2026-11-25): spec, code, docs and tests (8.1, row LOG1). ")
    assert len(line.encode("utf-8")) <= 600
