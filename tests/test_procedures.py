"""DESIGN 4.5 v1.576 (row PROC1a): a procedure, its route ID and its bounded run, standalone."""

import dataclasses
import importlib
import math
from pathlib import Path

import pytest

PACKAGE = Path(__file__).resolve().parent.parent / "model_routing"
NAMES = ("Procedure", "ProcedureResult", "ProcedureRun", "ProcedureLimitError")


def mod():
    return importlib.import_module("model_routing.procedures")


def done(text="out", tool_calls=0, tool_cost_usd=0.0):
    def fn(value, handle):
        return mod().ProcedureResult(text, tool_calls, tool_cost_usd)
    return fn


def make(fn=None, *, name="poll-job", version="1", max_model_calls=0, max_tool_calls=5,
         model=None):
    return mod().Procedure(name, version, fn or done(), max_model_calls=max_model_calls,
                           max_tool_calls=max_tool_calls, model=model)


def test_id_without_a_model():
    assert make().id == "proc:poll-job@1"


def test_id_with_a_model_route():
    proc = make(model="acme/small@low", max_model_calls=2)
    assert proc.id == "proc:poll-job@1+acme/small@low"


def test_a_new_version_or_model_is_another_id():
    ids = {make().id, make(version="2").id,
           make(model="acme/small", max_model_calls=1).id,
           make(model="acme/large", max_model_calls=1).id}
    assert len(ids) == 4


@pytest.mark.parametrize("field", ["name", "version"])
@pytest.mark.parametrize("bad", ["", "a b", "a@b", "a+b", "a/b", "a:b", "-a", ".a", 1, None])
def test_name_and_version_follow_the_variant_pattern(field, bad):
    with pytest.raises(ValueError):
        make(**{field: bad})


@pytest.mark.parametrize("good", ["a", "A1", "v1.2_x-y", "0"])
def test_name_and_version_accept_the_pattern(good):
    assert make(name=good, version=good).id == f"proc:{good}@{good}"


def test_fn_must_be_callable():
    with pytest.raises(ValueError):
        mod().Procedure("a", "1", "not callable", max_model_calls=0, max_tool_calls=0)


@pytest.mark.parametrize("field", ["max_model_calls", "max_tool_calls"])
@pytest.mark.parametrize("bad", [-1, True, False, 1.0, "1", None])
def test_limits_are_ints_of_at_least_zero(field, bad):
    kwargs = {"max_model_calls": 1, "model": "acme/small"}
    kwargs[field] = bad
    with pytest.raises(ValueError):
        make(**kwargs)


@pytest.mark.parametrize("bad", ["", "a b", "a\tb", "a+b", 3, b"acme/small", "proc:poll-job@1"])
def test_model_is_none_or_a_route_id_without_plus_or_space(bad):
    with pytest.raises(ValueError):
        make(model=bad, max_model_calls=1)


def test_the_id_is_name_version_and_model_whatever_fn_and_bounds():
    first = make(done("a"), model="acme/small", max_model_calls=1, max_tool_calls=0)
    second = make(done("b"), model="acme/small", max_model_calls=9, max_tool_calls=4)
    assert first.id == second.id == "proc:poll-job@1+acme/small"


def test_model_calls_need_a_named_model():
    with pytest.raises(ValueError):
        make(max_model_calls=1)


def test_a_named_model_needs_model_calls():
    with pytest.raises(ValueError):
        make(model="acme/small", max_model_calls=0)


def test_limits_and_model_are_keyword_only():
    with pytest.raises(TypeError):
        mod().Procedure("a", "1", done(), 0, 0)


def test_procedure_is_frozen():
    proc = make()
    with pytest.raises(dataclasses.FrozenInstanceError):
        proc.name = "other"


@pytest.mark.parametrize("bad", [None, 1, b"x"])
def test_result_output_is_a_str(bad):
    with pytest.raises(ValueError):
        mod().ProcedureResult(bad)


@pytest.mark.parametrize("bad", [-1, True, 1.0, "1", None])
def test_result_tool_calls_is_an_int_of_at_least_zero(bad):
    with pytest.raises(ValueError):
        mod().ProcedureResult("x", tool_calls=bad)


@pytest.mark.parametrize("bad", [-0.01, math.nan, math.inf, True, "1", None])
def test_result_tool_cost_is_a_finite_number_of_at_least_zero(bad):
    with pytest.raises(ValueError):
        mod().ProcedureResult("x", tool_cost_usd=bad)


def test_result_defaults_and_an_int_cost_stored_as_float():
    result = mod().ProcedureResult("x")
    assert (result.tool_calls, result.tool_cost_usd) == (0, 0.0)
    cost = mod().ProcedureResult("x", tool_cost_usd=2).tool_cost_usd
    assert type(cost) is float and cost == 2.0


def test_run_returns_the_route_output_and_counts():
    def fn(value, handle):
        first = handle([{"role": "user", "content": "submit " + value}])
        second = handle([{"role": "user", "content": "fetch " + first}])
        return mod().ProcedureResult(second, tool_calls=3, tool_cost_usd=0.25)

    replies = iter(["job-7", "done"])
    proc = make(fn, model="acme/small", max_model_calls=2, max_tool_calls=3)
    run = proc.run("x", lambda messages: next(replies))
    assert run == mod().ProcedureRun("proc:poll-job@1+acme/small", "done", 2, 3, 0.25)
    assert type(run.tool_cost_usd) is float


def test_handle_passes_messages_and_text_unchanged():
    sent, text = [{"role": "user", "content": "q"}], "reply"
    seen = []

    def call(messages):
        seen.append(messages)
        return text

    def fn(value, handle):
        assert handle(sent) is text
        return mod().ProcedureResult("ok")

    make(fn, model="acme/small", max_model_calls=1).run(None, call)
    assert seen[0] is sent


def test_input_is_passed_as_given():
    marker = object()
    got = []

    def fn(value, handle):
        got.append(value)
        return mod().ProcedureResult("ok")

    make(fn).run(marker, lambda m: "")
    assert got[0] is marker


def test_a_call_over_the_bound_is_refused_before_it_reaches_call():
    calls = []

    def fn(value, handle):
        for _ in range(3):
            handle([])
        return mod().ProcedureResult("never")

    proc = make(fn, model="acme/small", max_model_calls=2)
    with pytest.raises(mod().ProcedureLimitError, match="proc:poll-job@1"):
        proc.run(None, lambda m: calls.append(m) or "t")
    assert len(calls) == 2


def test_a_procedure_without_a_model_can_make_no_call():
    calls = []

    def fn(value, handle):
        handle([])
        return mod().ProcedureResult("never")

    with pytest.raises(mod().ProcedureLimitError):
        make(fn).run(None, lambda m: calls.append(m) or "t")
    assert calls == []


def test_a_call_that_raises_still_counts():
    def call(messages):
        raise RuntimeError("provider down")

    def fn(value, handle):
        try:
            handle([])
        except RuntimeError:
            pass
        handle([])
        return mod().ProcedureResult("never")

    with pytest.raises(mod().ProcedureLimitError):
        make(fn, model="acme/small", max_model_calls=1).run(None, call)


@pytest.mark.parametrize("raises", [False, True])
def test_a_kept_handle_is_dead_once_the_run_ends(raises):
    kept, calls = [], []

    def fn(value, handle):
        kept.append(handle)
        if raises:
            raise KeyError("boom")
        return mod().ProcedureResult("ok")

    proc = make(fn, model="acme/small", max_model_calls=5)
    if raises:
        with pytest.raises(KeyError):
            proc.run(None, lambda m: calls.append(m) or "t")
    else:
        proc.run(None, lambda m: calls.append(m) or "t")
    with pytest.raises(mod().ProcedureLimitError):
        kept[0]([])
    assert calls == []


def test_a_kept_handle_reports_the_ended_run_before_the_bound():
    kept = []

    def fn(value, handle):
        handle([])
        kept.append(handle)
        return mod().ProcedureResult("ok")

    make(fn, model="acme/small", max_model_calls=1).run(None, lambda m: "t")
    with pytest.raises(mod().ProcedureLimitError, match="after its run ended"):
        kept[0]([])


def test_exceptions_of_fn_and_call_propagate_unchanged():
    error = ValueError("from fn")

    def fn(value, handle):
        raise error

    with pytest.raises(ValueError) as caught:
        make(fn).run(None, lambda m: "")
    assert caught.value is error

    call_error = OSError("from call")

    def call(messages):
        raise call_error

    def fn2(value, handle):
        return mod().ProcedureResult(handle([]))

    with pytest.raises(OSError) as caught2:
        make(fn2, model="acme/small", max_model_calls=1).run(None, call)
    assert caught2.value is call_error


@pytest.mark.parametrize("bad", ["text", None, {"output": "x"}, "run"])
def test_a_return_that_is_no_result_is_a_value_error_naming_the_id(bad):
    if bad == "run":  # has tool_calls over the bound, so the type is checked first
        bad = mod().ProcedureRun("r", "x", 0, 99, 0.0)
    with pytest.raises(ValueError, match="proc:poll-job@1"):
        make(lambda value, handle: bad).run(None, lambda m: "")


def test_tool_calls_over_the_bound_are_refused():
    proc = make(done(tool_calls=6), max_tool_calls=5)
    with pytest.raises(mod().ProcedureLimitError, match="proc:poll-job@1"):
        proc.run(None, lambda m: "")
    assert make(done(tool_calls=5), max_tool_calls=5).run(None, lambda m: "").tool_calls == 5


def test_each_run_has_its_own_count():
    def fn(value, handle):
        for _ in range(value):
            handle([])
        return mod().ProcedureResult("ok")

    proc = make(fn, model="acme/small", max_model_calls=2)
    assert [proc.run(n, lambda m: "").model_calls for n in (2, 1, 2)] == [2, 1, 2]


def test_limit_error_is_an_exception():
    assert issubclass(mod().ProcedureLimitError, Exception)


def test_all_exports_the_four_names_after_evaluate_delegation():
    procedures = mod()
    import model_routing
    names = list(model_routing.__all__)
    at = names.index("evaluate_delegation")
    assert names[at + 1:at + 5] == list(NAMES)
    for name in NAMES:
        assert getattr(model_routing, name) is getattr(procedures, name)


def test_execution_records_reports_and_delegation_do_not_read_procedures_yet():
    # v1.577 (row PROC1b): router.py and stats.py route and count procedures; the executor's
    # run of one is row PROC1c, and decide_delegation passes none (5.2 v1.577)
    assert mod().__file__ == str(PACKAGE / "procedures.py")
    for module in ("executor.py", "monitor.py", "cli.py", "demo.py", "delegation.py"):
        text = (PACKAGE / module).read_text(encoding="utf-8")
        assert "procedure" not in text.lower(), module
