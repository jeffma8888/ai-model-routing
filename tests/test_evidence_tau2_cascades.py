"""DESIGN 7 v1.539 (row ESC3a): the tau2-bench cascade replay, evidence/tau2-bench/cascades.py.

The script turns tau2-bench run messages and 12.14 matrix rows into cascade rows in the 12.1 v1.538
format. These tests were committed before it under a module-level strict xfail whose error is the one
loading a missing file by path raises, FileNotFoundError, and the implementing commit removed the mark.
Every test uses synthetic messages and rows; none reads the pinned files."""

import copy
import importlib.util
import math
from pathlib import Path

import pytest

from model_routing import Cascade, evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "tau2-bench" / "cascades.py"
TRANSFER = "transfer_to_human_agents"
AT = "airline openai/x task '7' trial 0"

_loaded = []


def m():
    if not _loaded:
        spec = importlib.util.spec_from_file_location("tau2_cascades", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _loaded.append(module)
    return _loaded[0]


def agent(prompt, completion, cost, *tools):
    return {"role": "assistant", "content": "ok", "cost": cost,
            "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
            "tool_calls": [{"id": f"c{i}", "name": t, "arguments": {}} for i, t in enumerate(tools)] or None}


GREETING = {"role": "assistant", "content": "Hi! How can I help you today?", "cost": 0.0, "usage": None,
            "tool_calls": None}
USER = {"role": "user", "content": "I need help", "cost": 0.0001, "usage": {"prompt_tokens": 9}}
TOOL = {"role": "tool", "content": "{}", "cost": "not read"}


def call(cost=0.01, prompt=1000, completion=50, write=False, transfer=False):
    return {"cost_usd": cost, "prompt_tokens": prompt, "completion_tokens": completion, "write": write,
            "transfer": transfer}


# --- SIGNALS and parse_signal

def test_signals_are_the_esc1b_grid_and_transfer():
    assert m().SIGNALS == ("calls-over-10", "calls-over-10-no-write", "calls-over-15", "calls-over-15-no-write",
                           "calls-over-20", "calls-over-20-no-write", "transfer")
    assert m().TRANSFER == TRANSFER


@pytest.mark.parametrize("signal,parsed", [
    ("calls-over-10", ("calls-over", 10)), ("calls-over-1", ("calls-over", 1)),
    ("calls-over-15-no-write", ("calls-over-no-write", 15)), ("calls-over-120", ("calls-over", 120)),
    ("transfer", ("transfer", None)),
])
def test_parse_signal_reads_each_form(signal, parsed):
    got = m().parse_signal(signal)
    assert got == parsed and type(got) is tuple and type(got[1]) is type(parsed[1])


@pytest.mark.parametrize("signal", ["calls-over-0", "calls-over-010", "calls-over-", "calls-over-10-no-writes",
                                    "calls-over-10 ", "calls-over--1", "Transfer", "transfer-", "", "calls-over-1.5",
                                    "calls-over-\u0661\u0660", "calls-over-" + "1" * 5000, 10, None, b"transfer"])
def test_parse_signal_refuses_every_other_value(signal):
    with pytest.raises(ValueError, match="unknown signal") as info:
        m().parse_signal(signal)
    assert repr(signal) in str(info.value)


# --- agent_calls

def test_agent_calls_reads_each_agent_call_in_order():
    writes = {"book_reservation"}
    messages = [GREETING, USER, agent(100, 10, 0.5, "get_user_details"), TOOL,
                agent(150, 20, 1, "book_reservation", "get_user_details"), USER, agent(200, 5, -0.0, TRANSFER)]
    got = m().agent_calls(messages, writes, AT)
    assert got == [call(0.5, 100, 10), call(1.0, 150, 20, write=True), call(0.0, 200, 5, transfer=True)]
    assert all(list(c) == ["cost_usd", "prompt_tokens", "completion_tokens", "write", "transfer"] for c in got)
    assert type(got[1]["cost_usd"]) is float and math.copysign(1.0, got[2]["cost_usd"]) == 1.0
    assert m().agent_calls([], writes) == [] and m().agent_calls([GREETING, USER], frozenset()) == []


def test_agent_calls_takes_writes_as_any_collection_and_leaves_messages_unmodified():
    messages = [agent(10, 1, 0.1, "cancel_pending_order"), agent(20, 2, 0.2)]
    before = copy.deepcopy(messages)
    for writes in ({"cancel_pending_order"}, ["cancel_pending_order"], ("cancel_pending_order",),
                   frozenset({"cancel_pending_order"})):
        assert [c["write"] for c in m().agent_calls(messages, writes)] == [True, False]
    assert messages == before


def _with(**changes):
    message = agent(100, 10, 0.5, "get_user_details")
    for key, value in changes.items():
        if value is KeyError:
            del message[key]
        else:
            message[key] = value
    return message


BAD = {
    "messages not a list": "nope",
    "a message not a dict": [GREETING, 1],
    "no usage key": [_with(usage=KeyError)],
    "cost a bool": [_with(cost=True)],
    "cost a str": [_with(cost="0.1")],
    "cost missing": [_with(cost=KeyError)],
    "cost nan": [_with(cost=float("nan"))],
    "cost inf": [_with(cost=float("inf"))],
    "cost negative": [_with(cost=-0.5)],
    "cost an int too large for a float": [_with(cost=10 ** 400)],
    "tool_calls not a list": [_with(tool_calls="get_user_details")],
    "a tool call not a dict": [_with(tool_calls=["get_user_details"])],
    "a tool call with no name": [_with(tool_calls=[{"arguments": {}}])],
    "a tool call with an empty name": [_with(tool_calls=[{"name": ""}])],
    "a tool call with a non-str name": [_with(tool_calls=[{"name": 3}])],
    "null usage with a tool call": [dict(GREETING, tool_calls=[{"name": "get_user_details"}])],
    "null usage with a cost": [dict(GREETING, cost=0.001)],
    "usage not a dict": [_with(usage=[100, 10])],
    "prompt_tokens a bool": [_with(usage={"prompt_tokens": True, "completion_tokens": 10})],
    "prompt_tokens a float": [_with(usage={"prompt_tokens": 100.0, "completion_tokens": 10})],
    "prompt_tokens negative": [_with(usage={"prompt_tokens": -1, "completion_tokens": 10})],
    "completion_tokens missing": [_with(usage={"prompt_tokens": 100})],
    "completion_tokens a str": [_with(usage={"prompt_tokens": 100, "completion_tokens": "10"})],
}


@pytest.mark.parametrize("case", sorted(BAD))
def test_agent_calls_refuses_a_bad_message_naming_where(case):
    with pytest.raises(ValueError) as info:
        m().agent_calls(BAD[case], {"book_reservation"}, AT)
    assert str(info.value).startswith(AT)


@pytest.mark.parametrize("writes", ["book_reservation", b"book_reservation"])
def test_agent_calls_refuses_a_str_of_writes(writes):
    with pytest.raises(ValueError, match="not a collection of tool names") as info:
        m().agent_calls([agent(1, 1, 0.1, "b")], writes, AT)
    assert str(info.value).startswith(AT)


def test_a_greeting_with_a_zero_int_cost_is_no_call():
    assert m().agent_calls([dict(GREETING, cost=0), agent(5, 1, 0.1)], set()) == [call(0.1, 5, 1)]


# --- hand_up

def twelve(write_at=None, transfer_at=()):
    return [call(write=(k == write_at), transfer=(k in transfer_at)) for k in range(1, 13)]


def test_hand_up_on_the_call_count_signals():
    h = m().hand_up
    assert h(twelve(), "calls-over-10") == 10 and h(twelve(), "calls-over-11") == 11
    assert h(twelve(), "calls-over-12") is None and h(twelve(), "calls-over-15") is None
    assert h(twelve(write_at=11), "calls-over-10-no-write") == 10
    assert h(twelve(write_at=10), "calls-over-10-no-write") is None
    assert h(twelve(write_at=1), "calls-over-10-no-write") is None
    assert h(twelve(write_at=10), "calls-over-10") == 10
    assert h(twelve()[:10], "calls-over-10") is None and h(twelve()[:10], "calls-over-10-no-write") is None
    assert h([], "calls-over-1") is None


def test_hand_up_on_transfer_takes_the_first_transfer():
    h = m().hand_up
    assert h(twelve(transfer_at=(4, 7)), "transfer") == 4
    assert h(twelve(transfer_at=(12,)), "transfer") == 12
    assert h(twelve(), "transfer") is None and h([], "transfer") is None


def test_hand_up_refuses_an_unknown_signal():
    with pytest.raises(ValueError, match="unknown signal"):
        m().hand_up(twelve(), "calls-over-0")


# --- cascade_cell

CHEAP = {"correct": False, "cost_usd": 0.12, "input_tokens": 9}
STRONG = {"correct": True, "cost_usd": 0.4}


def test_cascade_cell_keeps_the_cheap_run_when_the_signal_does_not_fire():
    got = m().cascade_cell(twelve()[:3], CHEAP, STRONG, "calls-over-10", 2.0)
    assert got == {"correct": False, "cost_usd": 0.12, "escalated": False}
    assert list(got) == ["correct", "cost_usd", "escalated"]


def test_cascade_cell_prices_a_hand_up_by_hand():
    calls = twelve()
    calls[9] = call(prompt=3000, completion=200)
    got = m().cascade_cell(calls, CHEAP, STRONG, "calls-over-10", 2.0)
    assert got["escalated"] is True and got["correct"] is True and list(got) == ["correct", "cost_usd", "escalated"]
    assert got["cost_usd"] == math.fsum([0.01] * 10 + [3200 * 2.0 / 1_000_000, 0.4])
    assert got["cost_usd"] == pytest.approx(0.1 + 0.0064 + 0.4, abs=1e-15)


def test_cascade_cell_on_transfer_reads_the_calls_up_to_the_transfer():
    calls = [call(0.03, 500, 40), call(0.05, 900, 60, transfer=True), call(0.07, 1500, 10)]
    strong = {"correct": False, "cost_usd": 0.25}
    got = m().cascade_cell(calls, {"correct": True, "cost_usd": 0.15}, strong, "transfer", 3)
    assert got == {"correct": False, "cost_usd": math.fsum([0.03, 0.05, 960 * 3 / 1_000_000, 0.25]),
                   "escalated": True}


@pytest.mark.parametrize("price", [True, "2", float("nan"), float("inf"), -1, -0.01, None, 10 ** 400])
def test_cascade_cell_refuses_a_bad_price(price):
    with pytest.raises(ValueError):
        m().cascade_cell(twelve(), CHEAP, STRONG, "calls-over-10", price)


def test_a_zero_price_adds_no_reread():
    got = m().cascade_cell(twelve(), CHEAP, STRONG, "calls-over-10", 0)
    assert got["cost_usd"] == math.fsum([0.01] * 10 + [0.4])


# --- cascade_rows

C = "x/cheap"
S = "y/strong"
CID = f"{C}>{S}@calls-over-10"


def matrix():
    return [
        {"task": "t", "item": "t|a", "model": C, "correct": True, "cost_usd": 0.02},
        {"task": "t", "item": "t|a", "model": S, "correct": True, "cost_usd": 0.3},
        {"task": "t", "item": "t|b", "model": C, "correct": False, "cost_usd": 0.12},
        {"task": "t", "item": "t|b", "model": S, "correct": True, "cost_usd": 0.4},
    ]


def matrix_calls():
    b = twelve()
    b[9] = call(prompt=3000, completion=200)
    return {(C, "t|a"): [call(0.01), call(0.01)], (C, "t|b"): b}


def test_cascade_rows_add_one_row_per_cascade_and_item_sorted():
    rows, calls = matrix(), matrix_calls()
    before = (copy.deepcopy(rows), copy.deepcopy(calls))
    got = m().cascade_rows(rows, calls, [Cascade(C, S, "calls-over-10")], {S: 2.0})
    assert got == [
        rows[0], {"task": "t", "item": "t|a", "model": CID, "correct": True, "cost_usd": 0.02, "escalated": False},
        rows[1], rows[2],
        {"task": "t", "item": "t|b", "model": CID, "correct": True,
         "cost_usd": math.fsum([0.01] * 10 + [3200 * 2.0 / 1_000_000, 0.4]), "escalated": True},
        rows[3],
    ]
    assert all(list(r) == ["task", "item", "model", "correct", "cost_usd", "escalated"] for r in got if ">" in r["model"])
    assert (rows, calls) == before and not any(r is s for r in got for s in rows)


def test_cascade_rows_keep_every_key_of_a_row_and_sort_whatever_the_input_order():
    rows = [dict(r, input_tokens=10, output_tokens=2) for r in reversed(matrix())]
    got = m().cascade_rows(rows, matrix_calls(), [Cascade(C, S, "calls-over-1"), Cascade(C, S, "transfer")], {S: 1})
    keys = [(r["task"], r["item"], r["model"]) for r in got]
    assert keys == sorted(keys) and len(got) == 8
    assert all("input_tokens" not in r for r in got if ">" in r["model"])
    assert [r for r in got if ">" not in r["model"]] == sorted(rows, key=lambda r: (r["task"], r["item"], r["model"]))
    assert m().cascade_rows(matrix(), {}, [], {}) == matrix()


def test_cascade_rows_read_one_shot_iterables_once():
    listed = m().cascade_rows(matrix(), matrix_calls(), [Cascade(C, S, "calls-over-10")], {S: 2.0})
    got = m().cascade_rows(iter(matrix()), matrix_calls(), iter([Cascade(C, S, "calls-over-10")]), {S: 2.0})
    assert got == listed and len(got) == 6


def _bad(kind):
    rows, calls, cascades, prices = matrix(), matrix_calls(), [Cascade(C, S, "calls-over-10")], {S: 2.0}
    if kind == "repeated row":
        rows.append(dict(rows[0]))
    elif kind == "not a Cascade":
        cascades = [(C, S, "calls-over-10")]
    elif kind == "repeated cascade":
        cascades = cascades * 2
    elif kind == "unknown signal":
        cascades = [Cascade(C, S, "calls-over-0")]
    elif kind == "cheap with no row":
        cascades = [Cascade("z/none", S, "calls-over-10")]
    elif kind == "strong with no row":
        cascades = [Cascade(C, "z/none", "calls-over-10")]
    elif kind == "item only the cheap has":
        rows = [r for r in rows if (r["model"], r["item"]) != (S, "t|b")]
    elif kind == "item only the strong has":
        rows = [r for r in rows if (r["model"], r["item"]) != (C, "t|b")]
    elif kind == "no price":
        prices = {C: 0.4}
    elif kind == "bad price":
        prices = {S: "2"}
    elif kind == "no calls":
        del calls[(C, "t|b")]
    return rows, calls, cascades, prices


@pytest.mark.parametrize("kind", ["repeated row", "not a Cascade", "repeated cascade", "unknown signal",
                                  "cheap with no row", "strong with no row", "item only the cheap has",
                                  "item only the strong has", "no price", "bad price", "no calls"])
def test_cascade_rows_refuse_before_any_output(kind):
    rows, calls, cascades, prices = _bad(kind)
    with pytest.raises(ValueError) as info:
        m().cascade_rows(rows, calls, cascades, prices)
    if kind not in ("repeated row", "not a Cascade"):
        assert cascades[0].id in str(info.value)


def test_the_rows_run_through_the_offline_evaluator():
    rows, calls = [], {}
    for k in range(60):
        item = f"t|{k:02d}"
        hard = k % 3 == 0
        rows.append({"task": "t", "item": item, "model": C, "correct": not hard, "cost_usd": 0.02})
        rows.append({"task": "t", "item": item, "model": S, "correct": True, "cost_usd": 0.3})
        calls[(C, item)] = [call(0.002) for _ in range(12 if hard else 4)]
    got = m().cascade_rows(rows, calls, [Cascade(C, S, "calls-over-10")], {S: 2.0})
    outcomes = outcomes_from_rows(got)
    assert sum(o.escalated is True for o in outcomes) == 20 and sum(o.escalated is False for o in outcomes) == 40
    assert all(o.correct for o in outcomes if o.model == CID)
    result = evaluate(outcomes, bars=[0.9], seeds=range(3), min_samples=10)
    shares = [r["escalation_share"] for r in result["summary"]]
    assert any(s is not None and 0 < s < 1 for s in shares)
