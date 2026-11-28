"""DESIGN 7 v1.704 (row SESS1, the 7 v1.698 stated limit): a bound on the executor's session table.

`Executor(..., max_sessions=None)`: None keeps v1.698's table, one entry per session until `.end_session`;
an `int` of at least 1 keeps at most that many entries. Storing a session's attempt makes its entry the
newest, and when storing a new session's attempt would pass the bound, the entry stored least recently is
dropped first, under the same lock, so that session's next call passes `select` no session keyword, as a first
call does. Without the argument, or with one no smaller than the sessions an executor sees, every session
call keeps its v1.703 bytes: `V1_703_SESSION_DIGEST` was computed on the package at 9c392d2, before v1.704.
"""

import hashlib
import inspect
import json

import pytest

from model_routing import AllModelsFailed, Executor, FakeProvider
from test_session_executor import CHEAP, MESSAGES, WARM, Run, _router, hit, outage, wrote

WARM_KEYS = {"session_route": WARM, "session_warm": True}


def _again(run, session, **kwargs):
    """One more call of ``session``; the keywords its ``select`` was passed."""
    run.ex.call("t", MESSAGES, session_id=session, **kwargs)
    return run.selects[-1]


# --- the parameter and its checks -----------------------------------------------------------------------------

def test_max_sessions_is_the_last_parameter_keyword_only_and_defaults_to_none():
    params = list(inspect.signature(Executor).parameters.values())
    assert [p.name for p in params[-2:]] == ["shadow_runner", "max_sessions"]
    assert params[-1].kind is inspect.Parameter.KEYWORD_ONLY and params[-1].default is None


@pytest.mark.parametrize("value", [0, -1, 1.5, 2.0, True, False, "2", [2]])
def test_a_max_sessions_that_is_no_int_of_at_least_1_is_refused_when_the_executor_is_built(value):
    with pytest.raises(ValueError, match="max_sessions"):
        Executor(_router(), FakeProvider({WARM: hit, CHEAP: hit}), max_sessions=value)


def test_the_max_sessions_check_comes_after_the_shadow_runner_check():
    with pytest.raises(ValueError, match="shadow_runner"):
        Executor(_router(), FakeProvider({WARM: hit}), shadow_runner=0.5, max_sessions=0)


@pytest.mark.parametrize("value", [None, 1, 2, 1_024])
def test_none_and_an_int_of_at_least_1_are_taken(value):
    Executor(_router(), FakeProvider({WARM: hit}), max_sessions=value)


# --- the bound --------------------------------------------------------------------------------------------------

def test_with_max_sessions_2_a_third_session_drops_the_oldest_and_leaves_the_other_two():
    run = Run(max_sessions=2)
    for session in ("a", "b", "c"):
        run.warm_up(session)
    run.clock.t = 10.0
    for session in ("b", "c"):
        result = run.ex.call("t", MESSAGES, session_id=session)
        assert run.selects[-1] == WARM_KEYS
        assert (result.model, result.decision.session_pricing, result.decision.pick_reason) == (
            WARM, "warm", "stay_warm")
    first = run.ex.call("t", MESSAGES, session_id="a")
    assert run.selects[-1] == {}
    assert first.decision.session_pricing is None and first.model == CHEAP  # routed as a first call


def test_a_session_called_again_is_not_the_one_dropped():
    run = Run(max_sessions=2)
    run.warm_up("a")
    run.warm_up("b")
    run.clock.t = 1.0
    assert _again(run, "a") == WARM_KEYS  # a is now the newest
    run.warm_up("c")  # drops b, stored least recently
    run.clock.t = 2.0
    assert _again(run, "a") == WARM_KEYS
    assert _again(run, "c") == WARM_KEYS
    assert _again(run, "b") == {}


def test_the_drop_follows_the_stores_not_a_clock_that_went_back():
    # review iter-565 should-fix 2: a, stored first, holds the later clock read and is still the one dropped
    run = Run(max_sessions=2)
    run.clock.t = 5.0
    run.warm_up("a")
    run.clock.t = 0.0
    run.warm_up("b")
    run.warm_up("c")
    run.clock.t = 6.0
    assert _again(run, "b") == WARM_KEYS
    assert _again(run, "a") == {}


def test_max_sessions_1_keeps_only_the_last_session_stored():
    run = Run(max_sessions=1)
    run.warm_up("a")
    run.clock.t = 1.0
    assert _again(run, "a") == WARM_KEYS
    assert _again(run, "a") == WARM_KEYS  # a session's own attempts drop none
    run.warm_up("b")
    assert _again(run, "a") == {}  # dropped by b, and a is stored again, dropping b
    assert _again(run, "b") == {}


def test_a_call_s_fallback_keeps_one_entry_for_its_session():
    run = Run(script={CHEAP: outage, WARM: hit}, max_sessions=2)
    for session in ("a", "b"):
        run.ex.call("t", MESSAGES, session_id=session)  # two attempts each: the cheap error, then WARM
    assert len(run.monitor.records) == 4
    run.clock.t = 1.0
    assert _again(run, "a") == WARM_KEYS
    assert _again(run, "b") == WARM_KEYS


def test_a_dropped_session_s_end_session_is_false():
    run = Run(max_sessions=1)
    run.warm_up("a")
    run.warm_up("b")
    assert run.ex.end_session("a") is False
    assert run.ex.end_session("b") is True


def test_a_call_with_no_attempt_stores_no_entry_and_drops_none():
    run = Run(max_sessions=1)
    run.warm_up("a")
    with pytest.raises(ValueError):
        run.ex.call("t", MESSAGES, session_id="b", slice="")  # refused by select before any attempt
    assert len(run.monitor.records) == 1  # the warm-up's alone
    run.clock.t = 1.0
    assert _again(run, "a") == WARM_KEYS


def test_max_sessions_none_keeps_1_100_sessions():
    # review iter-558 nit 1: three sessions would pass a cap of 1,024
    run = Run()
    names = [f"s-{i}" for i in range(1_100)]
    for session in names:
        run.warm_up(session)
    run.clock.t = 10.0
    for session in names:
        assert _again(run, session) == WARM_KEYS


def test_max_sessions_1_100_keeps_1_100_sessions_and_drops_the_oldest_at_the_next():
    run = Run(max_sessions=1_100)
    names = [f"s-{i}" for i in range(1_101)]
    for session in names:
        run.warm_up(session)
    run.clock.t = 10.0
    assert _again(run, "s-1") == WARM_KEYS
    assert _again(run, "s-1100") == WARM_KEYS
    assert _again(run, "s-0") == {}  # stored again, dropping s-2
    assert sum(run.ex.end_session(session) for session in names) == 1_100  # review iter-565 nit 6


# --- unchanged without the argument -------------------------------------------------------------------------

def _session_guard(**kwargs):
    """Decisions, records, ``select`` keywords and clock reads of session calls, as JSON text.

    Warm, expired, pinned, `cost_blind`, write-only, fallback and all-failed calls of at most three sessions,
    and `.end_session`, on fixtures that build at 9c392d2 (v1.703).
    """
    out = []

    def calls(run, steps):
        for session, t, extra in steps:
            run.clock.t = t
            try:
                out.append(run.ex.call("t", MESSAGES, session_id=session, **extra).decision.to_dict())
            except AllModelsFailed as exc:
                out.append([type(exc).__name__, str(exc)])

    def close(run):
        out.extend(run.monitor.records)
        out.append(run.selects)
        out.append(run.clock.reads)

    run = Run(**kwargs)
    calls(run, [("a", 0.0, {"exclude_models": (CHEAP,)}), ("b", 1.0, {}), ("a", 10.0, {}),
                ("c", 20.0, {"exclude_models": (CHEAP,)}), ("a", 21.0, {"flavor": "cost_blind"}),
                ("b", 400.0, {}), ("c", 410.0, {"pin_route": CHEAP, "pinned_by": "ops"}), ("c", 411.0, {})])
    out.append([run.ex.end_session("b"), run.ex.end_session("b")])
    calls(run, [("b", 412.0, {}), ("a", 413.0, {})])
    close(run)
    run = Run(script={CHEAP: outage, WARM: hit}, **kwargs)
    calls(run, [("x", 0.0, {}), ("x", 5.0, {}), ("y", 6.0, {})])
    close(run)
    run = Run(script={WARM: wrote, CHEAP: wrote}, **kwargs)
    calls(run, [("w", 0.0, {"exclude_models": (CHEAP,)}), ("w", 10.0, {}), ("w", 400.0, {})])
    close(run)
    run = Run(script={WARM: outage, CHEAP: outage}, **kwargs)
    calls(run, [("z", 0.0, {}), ("z", 1.0, {})])
    close(run)
    return json.dumps(out, sort_keys=False, separators=(",", ":"))


# sha256 of _session_guard() on the package at 9c392d2 (v1.703)
V1_703_SESSION_DIGEST = "be50e1f49a9dcadfb6d475becb60739a0c01bdbebd87dd07c98ca818fe3c0b1f"


def test_session_calls_without_max_sessions_keep_their_v1_703_bytes():
    assert hashlib.sha256(_session_guard().encode()).hexdigest() == V1_703_SESSION_DIGEST


@pytest.mark.parametrize("value", [None, 3, 1_024])
def test_a_bound_no_smaller_than_the_sessions_seen_changes_no_byte(value):
    assert hashlib.sha256(_session_guard(max_sessions=value).encode()).hexdigest() == V1_703_SESSION_DIGEST


def test_the_session_guard_holds_each_case():
    items = json.loads(_session_guard())
    decisions = [item for item in items if isinstance(item, dict) and "primary" in item and "outcome" not in item]
    assert {d.get("session_pricing") for d in decisions} == {None, "warm", "conservative"}
    assert any(d.get("pick_reason") == "stay_warm" for d in decisions)
    assert [True, False] in items
    assert items.count(["AllModelsFailed", "all 2 routed models failed for task 't'"]) == 2
    records = [item for item in items if isinstance(item, dict) and "outcome" in item]
    assert {r["outcome"] for r in records} == {"ok", "error"}
    assert any(r.get("pinned_by") == "ops" for r in records)
    assert {r["flavor"] for r in records} == {"cost_effective", "cost_blind"}
