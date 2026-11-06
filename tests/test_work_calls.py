"""v1.38 multi-call work in the delegation cost (DESIGN 13.1 to 13.4, 13.7), written
before the code.

The work may be K successive calls of the task (``work_calls``, ``--work-calls``): call j
reads its path's base context (C inline, B delegated) plus the j inputs and j - 1
outputs so far and writes S_out, and each path prices its K calls as one ``Model.cost``
of their integer token totals. The new behaviour is committed under strict xfail
markers, each naming what the v1.37 code raises: ``TypeError`` where a test passes
``work_calls`` to ``decide_delegation``, ``AssertionError`` where a CLI test passes
``--work-calls`` (v1.37 exits 2 on an unknown option). The implementing commit removes
the markers (DESIGN 13.8). The tests that are not marked pin that the v1.38 expressions
with K = 1 give the v1.37 costs bit for bit; they pass before and after the code.
"""

import dataclasses
import json
import re

import pytest

from model_routing import Model, Registry, Router, Stats, Task, main
from model_routing.router import CONTEXT_TOO_SMALL, PASSES

TASK = "review"
S_IN, S_OUT = 2000, 500
C, B, R = 20_000, 300, 200
WORK = {"context_tokens": C, "brief_tokens": B, "result_tokens": R}
COUNTS = {"fiction/cheap": (70, 100), "fiction/mid": (95, 100), "fiction/best": (99, 100)}
TOKENS = {"fiction/cheap": (70, 100, 150_000, 40_000), "fiction/mid": (95, 100, 260_000, 30_000),
          "fiction/best": (99, 100, 310_000, 81_000)}
BELOW = {"fiction/cheap": (70, 100), "fiction/mid": (75, 100), "fiction/best": (78, 100)}
TEXT_KEYS = ["mode", "model", "reason", "below_bar", "inline_cost_usd", "delegate_cost_usd",
             "parent_quality_lb", "delegate_quality_lb"]
FIELDS = ["task", "flavor", "parent", "mode", "model", "reason", "below_bar", "inline_allowed",
          "inline_cost_usd", "delegate_cost_usd", "parent_quality_lb", "delegate_quality_lb",
          "route"]

RED = pytest.mark.xfail(strict=True, raises=TypeError,
                        reason="v1.37 decide_delegation has no work_calls keyword (13.8)")
RED_CLI = pytest.mark.xfail(strict=True, raises=AssertionError,
                            reason="v1.37 delegate exits 2 on --work-calls (13.8)")


def models(windows=None, extra=()):
    """cheap 1/2, mid 3/6, best 10/20 USD per 1M tokens; 100,000-token windows unless set."""
    w = windows or {}
    return [Model("fiction/cheap", "small", 1.0, 2.0, w.get("fiction/cheap", 100_000)),
            Model("fiction/mid", "medium", 3.0, 6.0, w.get("fiction/mid", 100_000)),
            Model("fiction/best", "large", 10.0, 20.0, w.get("fiction/best", 100_000)),
            *extra]


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


def work_tokens(k, base_reads, base, s_in, s_out):
    """Input and output token totals of K calls (13.2 v1.38), w_in = K(K + 1) / 2 and
    w_out = K(K - 1) / 2."""
    return base_reads * base + k * (k + 1) // 2 * s_in + k * (k - 1) // 2 * s_out, k * s_out


def inline_v138(router, parent, k, carry=0, separate=True, context=C):
    p = router.registry.get(parent)
    s_in, s_out = sizes(router, parent)
    if separate:
        return (p.cost(*work_tokens(k, k, context, s_in, s_out))
                + (1 + carry) * p.cost(k * (s_in + s_out), 0))
    return (p.cost(*work_tokens(k, k - 1, context, s_in, s_out))
            + carry * p.cost(k * (s_in + s_out), 0))


def delegate_work_v138(router, delegate, k, brief=B):
    d_in, d_out = sizes(router, delegate)
    return router.registry.get(delegate).cost(*work_tokens(k, k, brief, d_in, d_out))


def delegate_v138(router, parent, delegate, k, carry=0, brief=B, result=R):
    p = router.registry.get(parent)
    return (p.cost(0, brief) + delegate_work_v138(router, delegate, k, brief)
            + (1 + carry) * p.cost(brief + result, 0))


def by_id(route):
    return {c.model_id: c for c in route.candidates}


GRID = [(rows, parent, flavor, separate, carry)
        for rows in (COUNTS, TOKENS)
        for parent in ("fiction/cheap", "fiction/mid", "fiction/best")
        for flavor in ("cost_effective", "cost_blind")
        for separate in (True, False)
        for carry in (0, 2)]


# plain: the v1.38 expressions with K = 1 are the v1.37 ones (13.2)

@pytest.mark.parametrize("rows,parent,flavor,separate,carry", GRID)
def test_k1_expressions_give_the_v137_costs_bit_for_bit(rows, parent, flavor, separate, carry):
    router = make_router(rows)
    decision = decide(router, parent, flavor, carry_turns=carry, inline_separate_call=separate)
    assert decision.inline_cost_usd == inline_v138(router, parent, 1, carry, separate)
    assert decision.delegate_cost_usd == delegate_v138(router, parent, decision.route.primary, 1,
                                                       carry)


@pytest.mark.parametrize("k", range(1, 7))
@pytest.mark.parametrize("folded", [False, True])
def test_k_call_totals_are_the_sum_of_the_calls(k, folded):
    # call j reads base + j * s_in + (j - 1) * s_out and writes s_out; folding drops the
    # base from the last call only, the parent's next call (13.2 v1.38)
    base, s_in, s_out = 12_345, 678, 91
    calls = [(0 if folded and j == k else base) + j * s_in + (j - 1) * s_out
             for j in range(1, k + 1)]
    assert work_tokens(k, k - folded, base, s_in, s_out) == (sum(calls), k * s_out)


# 13.1 the input

@RED
@pytest.mark.parametrize("rows,parent,flavor,separate,carry", GRID)
def test_work_calls_one_is_the_v137_decision(rows, parent, flavor, separate, carry):
    router = make_router(rows)
    assert (decide(router, parent, flavor, carry_turns=carry, inline_separate_call=separate,
                   work_calls=1)
            == decide(router, parent, flavor, carry_turns=carry, inline_separate_call=separate))


@RED
@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_work_calls_one_is_the_v137_decision_below_the_bar(flavor):
    router = make_router(BELOW, on_no_model="best_available")
    for parent in ("fiction/cheap", "fiction/mid", "fiction/best"):
        assert (decide(router, parent, flavor, work_calls=1)
                == decide(router, parent, flavor))


@RED
@pytest.mark.parametrize("value", [0, -1, True, False, 1.0, 2.5, "2", None])
def test_work_calls_must_be_an_integer_of_at_least_one_and_not_a_bool(value):
    with pytest.raises(ValueError, match="work_calls"):
        decide(make_router(), "fiction/best", work_calls=value)


@RED
def test_the_router_is_not_modified_and_the_bounds_stay_per_call():
    router = make_router(TOKENS)
    task, stats = router.tasks[TASK], dict(router.stats.items())
    one = decide(router, "fiction/best", "cost_blind", work_calls=1)
    many = decide(router, "fiction/best", "cost_blind", work_calls=5)
    assert router.tasks == {TASK: task} and dict(router.stats.items()) == stats
    assert many.route.primary == one.route.primary
    assert (many.parent_quality_lb, many.delegate_quality_lb) == (one.parent_quality_lb,
                                                                  one.delegate_quality_lb)
    assert [f.name for f in dataclasses.fields(many)] == FIELDS


# 13.2 cost of each path

@RED
@pytest.mark.parametrize("k", [2, 3, 7])
@pytest.mark.parametrize("rows,parent,flavor,separate,carry", GRID)
def test_k_call_costs_are_the_v138_expressions(k, rows, parent, flavor, separate, carry):
    router = make_router(rows)
    decision = decide(router, parent, flavor, carry_turns=carry, inline_separate_call=separate,
                      work_calls=k)
    assert decision.inline_cost_usd == inline_v138(router, parent, k, carry, separate)
    assert decision.delegate_cost_usd == delegate_v138(router, parent, decision.route.primary, k,
                                                       carry)


@RED
def test_k_call_costs_by_hand():
    router = make_router()
    # separate, K = 3, T = 0: best reads 3 * 20,000 + 6 * 2,000 + 3 * 500 = 73,500 and
    # writes 1,500, then the next call re-reads 3 * 2,500; mid reads 3 * 300 + 6 * 2,000
    # + 3 * 500 = 14,400 and writes 1,500
    three = decide(router, "fiction/best", work_calls=3)
    assert three.inline_cost_usd == pytest.approx(0.735 + 0.03 + 0.075, rel=1e-12)
    assert three.model == "fiction/mid"
    assert three.delegate_cost_usd == pytest.approx(0.006 + 0.0432 + 0.009 + 0.005, rel=1e-12)
    # folded, K = 2, T = 0: mid's last call is its next call, so C is read once, in the
    # first call: 1 * 20,000 + 3 * 2,000 + 1 * 500 = 26,500 in, 1,000 out
    two = decide(router, "fiction/mid", inline_separate_call=False, work_calls=2)
    assert two.inline_cost_usd == pytest.approx(0.0795 + 0.006, rel=1e-12)
    assert two.delegate_cost_usd == pytest.approx(0.0018 + 0.0213 + 0.006 + 0.0015, rel=1e-12)


@RED
def test_from_two_calls_a_folded_parent_delegates_to_its_own_model_with_no_carry():
    # 13.2 v1.38: folded, inline minus delegating to its own model gains (K - 1) * C
    router = make_router(registry_models=models()[1:2], rows={"fiction/mid": (95, 100)})
    one = decide(router, "fiction/mid", inline_separate_call=False, work_calls=1)
    two = decide(router, "fiction/mid", inline_separate_call=False, work_calls=2)
    assert (one.mode, one.reason) == ("inline", "inline_cheaper")
    assert (two.mode, two.model, two.reason) == ("delegate", "fiction/mid", "delegate_cheaper")


# 13.4 the inline context check

@RED
@pytest.mark.parametrize("window,k,allowed", [(25_000, 2, True), (24_999, 2, False),
                                              (24_999, 1, True), (22_500, 1, True),
                                              (32_500, 5, True), (32_499, 5, False)])
def test_inline_context_check_holds_the_last_call(window, k, allowed):
    # C + K * (S_in + S_out), with the task's expected sizes whatever the parent measured
    rows = dict(COUNTS, **{"fiction/mid": (95, 100, 900_000, 900_000)})
    router = make_router(rows, models({"fiction/mid": window}))
    decision = decide(router, "fiction/mid", work_calls=k)
    assert decision.inline_allowed is allowed
    if not allowed:
        assert (decision.mode, decision.reason) == ("delegate", "parent_context_full")


@RED
@pytest.mark.parametrize("separate", [True, False])
def test_inline_context_check_is_the_same_folded(separate):
    router = make_router(registry_models=models({"fiction/mid": 24_999}))
    decision = decide(router, "fiction/mid", inline_separate_call=separate, work_calls=2)
    assert decision.reason == "parent_context_full"


# 13.3 the delegate's select

@RED
@pytest.mark.parametrize("window,reason", [(7_800, PASSES), (7_799, CONTEXT_TOO_SMALL)])
def test_delegate_window_holds_its_last_call_not_the_k_call_total(window, reason):
    # B + K * (S_in + S_out) = 300 + 3 * 2,500 = 7,800, under the K-call total of 15,900
    router = make_router(registry_models=models({"fiction/mid": window}))
    decision = decide(router, "fiction/best", work_calls=3)
    assert by_id(decision.route)["fiction/mid"].reason == reason


@RED
@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
@pytest.mark.parametrize("rows", [COUNTS, TOKENS])
@pytest.mark.parametrize("k", [1, 2, 4])
def test_each_candidate_is_priced_at_its_k_calls(flavor, rows, k):
    router = make_router(rows)
    decision = decide(router, "fiction/best", flavor, work_calls=k)
    for model_id, candidate in by_id(decision.route).items():
        assert candidate.list_cost == delegate_work_v138(router, model_id, k)
        assert candidate.routing_cost == (candidate.list_cost if flavor == "cost_effective"
                                          else 0.0)


@RED
@pytest.mark.parametrize("rows", [COUNTS, TOKENS])
@pytest.mark.parametrize("carry", [0, 3])
def test_the_delegate_cost_holds_its_route_candidate_list_cost(rows, carry):
    router = make_router(rows)
    decision = decide(router, "fiction/best", carry_turns=carry, work_calls=4)
    parent = router.registry.get("fiction/best")
    work = by_id(decision.route)[decision.route.primary].list_cost
    assert decision.delegate_cost_usd == (parent.cost(0, B) + work
                                          + (1 + carry) * parent.cost(B + R, 0))


def two_price_shapes(out_price):
    """``fiction/in-cheap`` has cheap input, ``fiction/out-cheap`` cheap output."""
    extra = (Model("fiction/in-cheap", "x", 1.0, out_price, 100_000),
             Model("fiction/out-cheap", "y", 4.0, 1.0, 100_000))
    rows = {"fiction/best": (99, 100), "fiction/in-cheap": (95, 100),
            "fiction/out-cheap": (95, 100)}
    return make_router(rows, models()[2:] + list(extra))


@RED
def test_the_delegate_is_the_cheapest_over_its_k_calls_not_its_largest_call():
    # K = 3: in-cheap costs 14,400 + 45,000 over its three calls against out-cheap's
    # 57,600 + 1,500, but its last call alone 7,300 + 15,000 against 29,200 + 500
    router = two_price_shapes(30.0)
    assert decide(router, "fiction/best", work_calls=3).route.primary == "fiction/out-cheap"


@RED
def test_more_calls_can_move_the_delegate_to_cheaper_input():
    # out-cheap wins one call (9,700 against 12,300), in-cheap three (44,400 against 59,100)
    router = two_price_shapes(20.0)
    assert decide(router, "fiction/best", work_calls=1).route.primary == "fiction/out-cheap"
    assert decide(router, "fiction/best", work_calls=3).route.primary == "fiction/in-cheap"


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
@pytest.mark.parametrize("extra,kwargs", [((), {}), (("--fold-inline", "--carry-turns", "2"),
                                                     {"inline_separate_call": False,
                                                      "carry_turns": 2})])
def test_cli_work_calls_reaches_the_api(delegate_files, capsys, extra, kwargs):
    code = main(delegate_args(delegate_files, "fiction/best", "--json", "--work-calls", "3",
                              *extra))
    out = capsys.readouterr().out
    assert code == 0
    expected = decide(make_router(), "fiction/best", work_calls=3, **kwargs).to_dict()
    assert json.loads(out) == expected


@RED_CLI
def test_cli_text_keeps_its_eight_lines_with_work_calls(delegate_files, capsys):
    code = main(delegate_args(delegate_files, "fiction/best", "--work-calls", "3"))
    text = capsys.readouterr().out
    assert code == 0
    assert [line.split(":", 1)[0] for line in text.splitlines()] == TEXT_KEYS
    assert re.search(r"^inline_cost_usd:\s+0\.840000$", text, re.MULTILINE)
    assert re.search(r"^delegate_cost_usd:\s+0\.063200$", text, re.MULTILINE)


@RED_CLI
@pytest.mark.parametrize("value", ["0", "-1", "1.5", "many"])
def test_cli_bad_work_calls_exits_two_with_one_error_line(delegate_files, capsys, value):
    assert main(delegate_args(delegate_files, "fiction/best", "--work-calls", "2")) == 0
    capsys.readouterr()
    assert main(delegate_args(delegate_files, "fiction/best", "--work-calls", value)) == 2
    lines = capsys.readouterr().err.splitlines()
    assert lines[-1].startswith("error: ")
    assert sum(line.startswith("error: ") for line in lines) == 1
