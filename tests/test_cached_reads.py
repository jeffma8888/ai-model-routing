"""v1.41 cached context reads in the delegation cost (DESIGN 13.1, 13.2, 13.7), written
before the code.

``cached_read_ratio`` (rho) and ``--cached-read-ratio`` price the parent's reads of its
context C in the inline work calls (K * C with a call of its own, (K - 1) * C folded) at
rho times its list input price, as the float first argument
``K * C * rho + w_in * S_in + w_out * S_out`` of ``Model.cost``. Every other read and all
output stay at list price, and the delegate, its cost, the context checks and the bounds
are the same for every rho. The new behaviour is committed under strict xfail markers,
each naming what the v1.40 code raises: ``TypeError`` where a test passes
``cached_read_ratio`` to ``decide_delegation``, ``AssertionError`` where a CLI test passes
``--cached-read-ratio`` (v1.40 exits 2 on an unknown option). The implementing commit
removes the markers (DESIGN 13.8). The tests that are not marked pin that the v1.41
expressions with rho = 1.0 and rho = 1 give the v1.40 costs bit for bit; they pass before
the code and after it.
"""

import dataclasses
import json
import re
from fractions import Fraction

import pytest

from model_routing import Model, Registry, Router, Stats, Task, main

RED = pytest.mark.xfail(strict=True, raises=TypeError,
                        reason="v1.41 cached_read_ratio is not implemented yet (DESIGN 13.1)")
RED_CLI = pytest.mark.xfail(strict=True, raises=AssertionError,
                            reason="v1.41 --cached-read-ratio is not implemented yet (DESIGN 13.7)")

TASK = "review"
S_IN, S_OUT = 2000, 500
C, B, R = 20_000, 300, 200
WORK = {"context_tokens": C, "brief_tokens": B, "result_tokens": R}
COUNTS = {"fiction/cheap": (70, 100), "fiction/mid": (95, 100), "fiction/best": (99, 100)}
TOKENS = {"fiction/cheap": (70, 100, 150_000, 40_000), "fiction/mid": (95, 100, 260_000, 30_000),
          "fiction/best": (99, 100, 310_000, 81_000)}
# totals that 100 trials do not divide, next to a model with counts only
ODD = {"fiction/cheap": (70, 100), "fiction/mid": (95, 100, 260_001, 30_001),
       "fiction/best": (99, 100, 310_000, 81_000)}
BELOW = {"fiction/cheap": (70, 100), "fiction/mid": (75, 100), "fiction/best": (78, 100)}
TEXT_KEYS = ["mode", "model", "reason", "below_bar", "inline_cost_usd", "delegate_cost_usd",
             "parent_quality_lb", "delegate_quality_lb"]
FIELDS = ["task", "flavor", "parent", "mode", "model", "reason", "below_bar", "inline_allowed",
          "inline_cost_usd", "delegate_cost_usd", "parent_quality_lb", "delegate_quality_lb",
          "route"]
PARENTS = ("fiction/cheap", "fiction/mid", "fiction/best")


def models(windows=None):
    """cheap 1/2, mid 3/6, best 10/20 USD per 1M tokens; 100,000-token windows unless set."""
    w = windows or {}
    return [Model("fiction/cheap", "small", 1.0, 2.0, w.get("fiction/cheap", 100_000)),
            Model("fiction/mid", "medium", 3.0, 6.0, w.get("fiction/mid", 100_000)),
            Model("fiction/best", "large", 10.0, 20.0, w.get("fiction/best", 100_000))]


def build_stats(rows):
    """``rows`` maps a model to (successes, trials) or (successes, trials, input, output)."""
    stats = Stats()
    for model_id, (successes, trials, *tokens) in rows.items():
        if tokens:
            stats.add(TASK, model_id, successes, trials, input_tokens=tokens[0],
                      output_tokens=tokens[1])
        else:
            stats.add(TASK, model_id, successes, trials)
    return stats


def make_router(rows=COUNTS, registry_models=None, **task_fields):
    fields = {"name": TASK, "bar": 0.8, "min_samples": 30,
              "expected_input_tokens": S_IN, "expected_output_tokens": S_OUT}
    fields.update(task_fields)
    registry = Registry(models() if registry_models is None else registry_models)
    return Router(registry, {TASK: Task(**fields)}, build_stats(rows))


def decide(router, parent, flavor="cost_effective", **kwargs):
    work = dict(WORK)
    work.update(kwargs)
    return router.decide_delegation(TASK, parent, flavor, **work)


def sizes(router, model_id):
    """The 5.2 sizes: the rounded-up measured mean, else the task's expected tokens."""
    mean = router.stats.mean_tokens(TASK, model_id)
    return (S_IN, S_OUT) if mean is None else mean


def inline_v141(router, parent, k=1, carry=0, separate=True, ratio=1.0, context=C):
    """13.2 v1.41: the parent's reads of C in its work calls at ``ratio`` of its input price,
    evaluated left to right as the spec writes it."""
    p = router.registry.get(parent)
    s_in, s_out = sizes(router, parent)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    if separate:
        return (p.cost(k * context * ratio + w_in * s_in + w_out * s_out, k * s_out)
                + (1 + carry) * p.cost(k * (s_in + s_out), 0))
    return (p.cost((k - 1) * context * ratio + w_in * s_in + w_out * s_out, k * s_out)
            + carry * p.cost(k * (s_in + s_out), 0))


def delegate_v138(router, parent, delegate, k=1, carry=0, brief=B, result=R):
    p, d = router.registry.get(parent), router.registry.get(delegate)
    d_in, d_out = sizes(router, delegate)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    return (p.cost(0, brief) + d.cost(k * brief + w_in * d_in + w_out * d_out, k * d_out)
            + (1 + carry) * p.cost(brief + result, 0))


GRID = [(rows, parent, flavor, separate, carry)
        for rows in (COUNTS, TOKENS, ODD)
        for parent in PARENTS
        for flavor in ("cost_effective", "cost_blind")
        for separate in (True, False)
        for carry in (0, 2)]


# plain: the v1.41 expressions with rho = 1.0 or 1 are the v1.40 costs (13.2)

@pytest.mark.parametrize("ratio", [1.0, 1])
@pytest.mark.parametrize("k", [1, 3])
@pytest.mark.parametrize("rows,parent,flavor,separate,carry", GRID)
def test_ratio_one_expressions_give_the_v140_costs_bit_for_bit(rows, parent, flavor, separate,
                                                               carry, k, ratio):
    router = make_router(rows)
    decision = decide(router, parent, flavor, carry_turns=carry, inline_separate_call=separate,
                      work_calls=k)
    assert decision.inline_cost_usd == inline_v141(router, parent, k, carry, separate, ratio)
    assert decision.delegate_cost_usd == delegate_v138(router, parent, decision.route.primary, k,
                                                       carry)


@pytest.mark.parametrize("context", [0, 1, 123_457, 10**9 + 7])
@pytest.mark.parametrize("separate", [True, False])
def test_ratio_one_is_bit_for_bit_at_any_context(context, separate):
    # a context past every window blocks inline, but its cost is still reported (13.6)
    router = make_router(ODD)
    for parent in PARENTS:
        decision = decide(router, parent, context_tokens=context, inline_separate_call=separate,
                          work_calls=2)
        assert decision.inline_cost_usd == inline_v141(router, parent, 2, 0, separate, 1.0,
                                                       context)


def test_a_float_argument_equal_to_the_integer_total_prices_the_same():
    # Model.cost converts an int to the same float before it multiplies (13.2 v1.41)
    for model in models() + [Model("fiction/odd", "odd", 0.15, 0.6, 1), Model("fiction/int", "i", 3, 7, 1)]:
        for tokens in (0, 1, 2_500, 46_501, 10**9 + 7):
            assert model.cost(tokens * 1.0, 500) == model.cost(tokens, 500)
            assert model.cost(tokens * 1.0 + 3, 0) == model.cost(tokens + 3, 0)


# 13.1 the input

@RED
@pytest.mark.parametrize("ratio", [1.0, 1])
@pytest.mark.parametrize("rows,parent,flavor,separate,carry", GRID)
def test_ratio_one_is_the_v140_decision(rows, parent, flavor, separate, carry, ratio):
    router = make_router(rows)
    for k in (1, 2):
        assert (decide(router, parent, flavor, carry_turns=carry, inline_separate_call=separate,
                       work_calls=k, cached_read_ratio=ratio)
                == decide(router, parent, flavor, carry_turns=carry,
                          inline_separate_call=separate, work_calls=k))


@RED
@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_ratio_one_is_the_v140_decision_below_the_bar(flavor):
    router = make_router(BELOW, on_no_model="best_available")
    for parent in PARENTS:
        assert (decide(router, parent, flavor, cached_read_ratio=1.0)
                == decide(router, parent, flavor))


@RED
@pytest.mark.parametrize("value", [-0.1, -1, 1.0000001, 2, float("nan"), float("inf"),
                                   float("-inf"), True, False, "0.5", None, Fraction(1, 2)])
def test_cached_read_ratio_must_be_an_int_or_float_in_0_1_and_not_a_bool(value):
    with pytest.raises(ValueError, match="cached_read_ratio"):
        decide(make_router(), "fiction/best", cached_read_ratio=value)


@RED
@pytest.mark.parametrize("value", [0, 1, 0.0, 0.5, 1.0, 5e-324])
def test_cached_read_ratio_accepts_ints_and_floats_from_0_to_1(value):
    decision = decide(make_router(), "fiction/best", cached_read_ratio=value)
    assert decision.inline_cost_usd == inline_v141(make_router(), "fiction/best", ratio=value)


@RED
@pytest.mark.parametrize("bad,name", [({"work_calls": 0, "cached_read_ratio": -1}, "work_calls"),
                                      ({"inline_separate_call": "yes",
                                        "cached_read_ratio": 2.0}, "inline_separate_call")])
def test_cached_read_ratio_is_checked_after_inline_separate_call(bad, name):
    with pytest.raises(ValueError, match=name):
        decide(make_router(), "fiction/best", **bad)


@RED
def test_the_router_is_not_modified_and_the_fields_are_unchanged():
    router = make_router(TOKENS)
    task, stats = router.tasks[TASK], dict(router.stats.items())
    decision = decide(router, "fiction/best", cached_read_ratio=0.1, work_calls=2)
    assert router.tasks == {TASK: task} and dict(router.stats.items()) == stats
    assert [f.name for f in dataclasses.fields(decision)] == FIELDS
    assert list(decision.to_dict()) == FIELDS


# 13.2 cost of each path

@RED
@pytest.mark.parametrize("ratio", [0.0, 0.1, 0.5])
@pytest.mark.parametrize("k", [1, 3])
@pytest.mark.parametrize("rows,parent,flavor,separate,carry", GRID)
def test_the_ratio_prices_the_parents_reads_of_c_and_nothing_else(rows, parent, flavor, separate,
                                                                  carry, k, ratio):
    router = make_router(rows)
    work = {"carry_turns": carry, "inline_separate_call": separate, "work_calls": k}
    decision = decide(router, parent, flavor, cached_read_ratio=ratio, **work)
    listed = decide(router, parent, flavor, **work)
    assert decision.inline_cost_usd == inline_v141(router, parent, k, carry, separate, ratio)
    assert decision.delegate_cost_usd == listed.delegate_cost_usd
    assert decision.route == listed.route
    assert (decision.inline_allowed, decision.parent_quality_lb, decision.delegate_quality_lb) == (
        listed.inline_allowed, listed.parent_quality_lb, listed.delegate_quality_lb)


@RED
@pytest.mark.parametrize("k,separate,carry,ratio,inline", [
    # best is 10/20 USD per 1M tokens; C 20,000, S_in 2,000, S_out 500
    (1, True, 0, 0.1, 0.075),     # (2,000 + 2,000) * 10 + 500 * 20, then 2,500 * 10
    (1, True, 0, 0.0, 0.055),     # (0 + 2,000) * 10 + 500 * 20, then 2,500 * 10
    (2, True, 1, 0.25, 0.285),    # (10,000 + 6,000 + 500) * 10 + 1,000 * 20, then 2 * 5,000 * 10
    (2, False, 0, 0.5, 0.185),    # (10,000 + 6,000 + 500) * 10 + 1,000 * 20
    (1, False, 2, 0.0, 0.08),     # 2,000 * 10 + 500 * 20, then 2 * 2,500 * 10; no C term
])
def test_hand_computed_inline_costs(k, separate, carry, ratio, inline):
    decision = decide(make_router(), "fiction/best", work_calls=k, inline_separate_call=separate,
                      carry_turns=carry, cached_read_ratio=ratio)
    assert decision.inline_cost_usd == pytest.approx(inline, rel=1e-12)
    assert decision.route.primary == "fiction/mid"


@RED
@pytest.mark.parametrize("k,context,ratio", [(3, 123_457, 0.1), (3, 123_457, 0.3), (3, 77_777, 0.9),
                                             (7, 77_777, 0.1), (7, 77_777, 0.7),
                                             (4, 123_457, 0.1), (4, 77_777, 0.9)])
@pytest.mark.parametrize("separate", [True, False])
def test_the_cached_reads_are_the_integer_product_times_the_ratio(k, context, ratio, separate):
    # (K * C) * rho, not K * (C * rho): the two round apart at these values, separate at
    # K = 3 and 7 and folded (K - 1 = 3) at K = 4 (13.2 v1.41);
    # a context past every window blocks inline, but its cost is still reported
    router = make_router(TOKENS)
    for parent in PARENTS:
        decision = decide(router, parent, context_tokens=context, work_calls=k,
                          inline_separate_call=separate, cached_read_ratio=ratio)
        assert decision.inline_cost_usd == inline_v141(router, parent, k, 0, separate, ratio,
                                                       context)


@RED
@pytest.mark.parametrize("ratio", [0, 0.3, 1.0])
@pytest.mark.parametrize("rows,parent,flavor,carry",
                         [(rows, parent, flavor, carry)
                          for rows, parent, flavor, separate, carry in GRID if not separate])
def test_folded_work_of_one_call_costs_the_same_for_every_ratio(rows, parent, flavor, carry, ratio):
    router = make_router(rows)
    work = {"carry_turns": carry, "inline_separate_call": False}
    assert decide(router, parent, flavor, cached_read_ratio=ratio, **work) == decide(
        router, parent, flavor, **work)


@RED
def test_a_lower_ratio_can_keep_the_work_inline():
    # mid as the parent and its own delegate: with B = R = 2,000, delegating costs
    # 0.012 + 0.015 + 0.012 = 0.039 USD; inline costs 0.06 * rho + 0.0165, so it is the
    # cheaper path below rho = 0.375 (13.5 row 3)
    router = make_router()
    work = {"brief_tokens": 2000, "result_tokens": 2000}
    listed = decide(router, "fiction/mid", cached_read_ratio=1.0, **work)
    cached = decide(router, "fiction/mid", cached_read_ratio=0.25, **work)
    assert (listed.mode, listed.reason, listed.model) == ("delegate", "delegate_cheaper",
                                                          "fiction/mid")
    assert (cached.mode, cached.reason, cached.model) == ("inline", "inline_cheaper",
                                                          "fiction/mid")
    assert listed.delegate_cost_usd == cached.delegate_cost_usd == pytest.approx(0.039, rel=1e-12)
    assert listed.inline_cost_usd == pytest.approx(0.0765, rel=1e-12)
    assert cached.inline_cost_usd == pytest.approx(0.0315, rel=1e-12)


@RED
def test_cost_blind_never_compares_cost_so_the_ratio_cannot_move_it():
    router = make_router()
    work = {"brief_tokens": 2000, "result_tokens": 2000}
    for parent in PARENTS:
        listed = decide(router, parent, "cost_blind", **work)
        for ratio in (0.0, 0.25):
            cached = decide(router, parent, "cost_blind", cached_read_ratio=ratio, **work)
            assert (cached.mode, cached.model, cached.reason) == (listed.mode, listed.model,
                                                                  listed.reason)


# 13.4 the context check reads tokens, not prices

@RED
@pytest.mark.parametrize("k,window", [(1, 22_499), (2, 24_999)])
def test_the_context_check_is_the_same_at_every_ratio(k, window):
    # C + K * (S_in + S_out) is 22,500 at K = 1 and 25,000 at K = 2
    router = make_router(registry_models=models({"fiction/best": window}))
    decision = decide(router, "fiction/best", work_calls=k, cached_read_ratio=0.0)
    assert (decision.mode, decision.reason, decision.inline_allowed) == (
        "delegate", "parent_context_full", False)
    roomy = make_router(registry_models=models({"fiction/best": window + 1}))
    assert decide(roomy, "fiction/best", work_calls=k, cached_read_ratio=0.0).inline_allowed


# 13.7 CLI

@pytest.fixture
def delegate_files(tmp_path):
    router = make_router()
    rows = [dict(dataclasses.asdict(m), source="https://example.org/prices")
            for m in router.registry.models]
    paths = {"registry": tmp_path / "models.json", "tasks": tmp_path / "tasks.json",
             "stats": tmp_path / "stats.json", "priors": tmp_path / "no-priors.json"}
    paths["registry"].write_text(json.dumps({"version": "1", "as_of": "2026-01-01",
                                             "currency": "USD", "models": rows}),
                                 encoding="utf-8")
    task = dataclasses.asdict(router.tasks[TASK])
    paths["tasks"].write_text(json.dumps({"tasks": [task]}), encoding="utf-8")
    router.stats.save(paths["stats"])
    return paths


def delegate_args(files, parent="fiction/best", *extra):
    args = ["delegate", TASK, "--parent", parent]
    for key, value in WORK.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    for flag, path in files.items():
        args += ["--" + flag, str(path)]
    return args + list(extra)


@RED_CLI
@pytest.mark.parametrize("extra,kwargs", [((), {}),
                                          (("--fold-inline", "--work-calls", "2",
                                            "--carry-turns", "1"),
                                           {"inline_separate_call": False, "work_calls": 2,
                                            "carry_turns": 1})])
def test_cli_cached_read_ratio_reaches_the_api(delegate_files, capsys, extra, kwargs):
    code = main(delegate_args(delegate_files, "fiction/best", "--json",
                              "--cached-read-ratio", "0.25", *extra))
    out = capsys.readouterr().out
    assert code == 0
    expected = decide(make_router(), "fiction/best", cached_read_ratio=0.25, **kwargs).to_dict()
    assert json.loads(out) == expected


@RED_CLI
@pytest.mark.parametrize("value", ["1", "1.0"])
def test_cli_ratio_one_prints_what_no_flag_prints(delegate_files, capsys, value):
    assert main(delegate_args(delegate_files, "fiction/best", "--cached-read-ratio", value)) == 0
    flagged = capsys.readouterr().out
    assert main(delegate_args(delegate_files, "fiction/best")) == 0
    assert flagged == capsys.readouterr().out


@RED_CLI
def test_cli_text_keeps_its_eight_lines_with_a_cached_read_ratio(delegate_files, capsys):
    code = main(delegate_args(delegate_files, "fiction/best", "--cached-read-ratio", "0.1"))
    text = capsys.readouterr().out
    assert code == 0
    assert [line.split(":", 1)[0] for line in text.splitlines()] == TEXT_KEYS
    assert re.search(r"^inline_cost_usd:\s+0\.075000$", text, re.MULTILINE)
    assert re.search(r"^delegate_cost_usd:\s+0\.020900$", text, re.MULTILINE)


@RED_CLI
@pytest.mark.parametrize("value", ["-0.5", "1.5", "nan", "inf", "half"])
def test_cli_bad_cached_read_ratio_exits_two_with_one_error_line(delegate_files, capsys, value):
    assert main(delegate_args(delegate_files, "fiction/best", "--cached-read-ratio", "0.5")) == 0
    capsys.readouterr()
    assert main(delegate_args(delegate_files, "fiction/best", "--cached-read-ratio", value)) == 2
    lines = capsys.readouterr().err.splitlines()
    assert lines[-1].startswith("error: ")
    assert sum(line.startswith("error: ") for line in lines) == 1
