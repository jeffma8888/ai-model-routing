"""v1.45 variant points of the delegation results (DESIGN 13.10), written before the code.

A grid point that changes a 13.2 knob the base grid holds fixed goes in a second results
file, ``evidence/delegation/variants.json``, so the committed ``results.json`` keeps its bytes
and each file stays under about 300 KB. ``variant_points()`` holds the variant points, ``run``
takes ``grid="base"`` or ``grid="variants"``, the CLI takes ``--grid`` with ``--matrix`` only,
and ``table`` gains a ``calls`` column when a config point carries ``work_calls``.

Every test that needs the v1.45 script is held as strict xfail naming what the v1.44 script
raises: ``AttributeError`` for ``variant_points``, ``TypeError`` for ``run(..., grid=...)``, and
``AssertionError`` for the ``calls`` column and the ``--grid`` outcomes, since v1.44 prints no
such column and rejects ``--grid`` as an unrecognized argument. The plain tests pass before and
after. The tests of the committed ``variants.json`` come with that file.
"""

import importlib.util
import json
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "delegation" / "results.py"
RESULTS = ROOT / "evidence" / "delegation" / "results.json"
KEYS = ["config", "tasks", "summary"]
POINT_KEYS = ["context_tokens", "brief_tokens", "result_tokens", "carry_turns",
              "inline_separate_call", "work_calls"]
VARIANTS = [{"context_tokens": 64000, "brief_tokens": 500, "result_tokens": 500,
             "carry_turns": 1, "inline_separate_call": False, "work_calls": 2}]

no_variant_points = pytest.mark.xfail(
    strict=True, raises=AttributeError,
    reason="v1.44 results.py has no variant_points (DESIGN 13.10, v1.45)")
no_grid = pytest.mark.xfail(
    strict=True, raises=TypeError, reason="v1.44 run takes no grid (DESIGN 13.10, v1.45)")
no_calls_column = pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="v1.44 table prints no calls column (DESIGN 13.10, v1.45)")
no_grid_option = pytest.mark.xfail(
    strict=True, raises=AssertionError,
    reason="v1.44 results.py rejects --grid as an unrecognized argument (DESIGN 13.10, v1.45)")


@pytest.fixture
def dr():
    spec = importlib.util.spec_from_file_location("delegation_results_variants", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tiny():
    registry = Registry([
        Model(id="v/strong", family="S", price_in=3.0, price_out=12.0, context_window=1_000_000),
        Model(id="v/cheap", family="C", price_in=0.1, price_out=0.4, context_window=100_000)])
    rows = []
    for i in range(80):
        rows.append({"task": "all", "item": f"q{i}", "model": "v/strong", "correct": i % 10 != 0,
                     "input_tokens": 200 + i, "output_tokens": 900 + 3 * i})
        rows.append({"task": "all", "item": f"q{i}", "model": "v/cheap", "correct": i % 3 != 0,
                     "input_tokens": 180 + i, "output_tokens": 700 + 2 * i})
    return rows, registry


POOL = {"models": [
    {"id": "v/strong", "family": "S", "price_in": 3.0, "price_out": 12.0,
     "context_window": 1_000_000},
    {"id": "v/cheap", "family": "C", "price_in": 0.1, "price_out": 0.4,
     "context_window": 100_000}]}


def write_inputs(tmp_path):
    rows, _ = tiny()
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps(POOL), encoding="utf-8")
    return str(matrix), str(pool)


VALUES = {("a/x", "decision"): (0.5, 1.0, 1.0), ("a/x", "inline"): (0.25, 0.5, None),
          ("a/x", "delegate"): (0.5, 1.0, None), ("b/y", "decision"): (0.7, 3.0, 0.0),
          ("b/y", "inline"): (0.75, 1.5, None), ("b/y", "delegate"): (0.9, 2.5, None)}


def handmade(points):
    """Results with the same summary values on every point, as in the 13.10 table tests."""
    summary = [{"bar": 0.5, "flavor": "cost_effective", "point": index, "parent": parent,
                "strategy": strategy, "success": success, "cost_usd": cost,
                "below_bar_rate": 0.0, "delegate_rate": rate}
               for index in range(len(points))
               for (parent, strategy), (success, cost, rate) in VALUES.items()]
    return {"config": {"bars": [0.5], "seeds": [0], "flavors": ["cost_effective"],
                       "points": points, "parents": ["a/x", "b/y"]},
            "tasks": {"t": {"items": 4, "models": ["a/x", "b/y"]}}, "summary": summary}


def point(context, separate, **extra):
    return dict({"context_tokens": context, "brief_tokens": 1, "result_tokens": 2,
                 "carry_turns": 0, "inline_separate_call": separate}, **extra)


HEADER = ("bar  flavor          context  separate  dec_success  dec_cost  inl_success  inl_cost"
          "  del_success  del_cost  delegated")
DASHES = ("---  --------------  -------  --------  -----------  --------  -----------  --------"
          "  -----------  --------  ---------")
ROW = ("0.5  cost_effective  10       True      0.600        2.0000    0.500        1.0000"
       "    0.700        1.7500    0.500")
CALLS_HEADER = ("bar  flavor          context  separate  calls  dec_success  dec_cost  inl_success"
                "  inl_cost  del_success  del_cost  delegated")
CALLS_DASHES = ("---  --------------  -------  --------  -----  -----------  --------  -----------"
                "  --------  -----------  --------  ---------")
CALLS_TAIL = ("0.600        2.0000    0.500        1.0000    0.700        1.7500    0.500")


# --- the variant point, plain (true before and after v1.45) -------------------------------------

def test_the_variant_point_is_a_13_9_point_that_serialises_work_calls_last():
    rows, registry = tiny()
    result = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=VARIANTS, seeds=range(5))
    assert result["config"]["points"] == VARIANTS
    assert [list(p) for p in result["config"]["points"]] == [POINT_KEYS]


def test_the_variant_point_costs_more_inline_than_the_same_folded_point_at_k_1():
    # the second work call re-reads C on the inline path, (K - 1) * C (DESIGN 13.2)
    rows, registry = tiny()
    k1 = {k: v for k, v in VARIANTS[0].items() if k != "work_calls"}
    result = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=[VARIANTS[0], k1],
                                 seeds=range(10))
    inline = {(r["bar"], r["flavor"], r["parent"], r["point"]): r["cost_usd"]
              for r in result["summary"] if r["strategy"] == "inline"}
    groups = {key[:3] for key in inline}
    assert len(groups) == 2 * 2 * 2
    for group in groups:
        assert inline[group + (0,)] > inline[group + (1,)], group


def test_a_table_without_work_calls_has_no_calls_column(dr):
    assert dr.table(handmade([point(10, True)])) == "\n".join([HEADER, DASHES, ROW])
    committed = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert dr.table(committed).split("\n", 1)[0] == HEADER


# --- variant_points and run(grid=...) (red until v1.45) ------------------------------------------

@no_variant_points
def test_variant_points_are_the_stated_variant_grid(dr):
    assert dr.variant_points() == VARIANTS
    assert [list(p) for p in dr.variant_points()] == [POINT_KEYS]
    assert dr.variant_points() is not dr.variant_points()


@no_grid
def test_run_on_the_variants_grid_is_evaluate_delegation_on_the_variant_points(dr):
    rows, registry = tiny()
    got = dr.run(rows, registry, grid="variants")
    full = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=VARIANTS, seeds=range(50))
    assert list(got) == KEYS
    assert got == {key: full[key] for key in KEYS}


@no_grid
def test_run_on_the_base_grid_is_the_default_run(dr):
    rows, registry = tiny()
    assert dr.run(rows, registry, grid="base") == dr.run(rows, registry)


@no_grid
@pytest.mark.parametrize("grid", ["", "Base", "variant", "all", None, 1])
def test_run_refuses_any_other_grid_before_evaluating(dr, grid):
    # no rows and no registry: evaluate_delegation would raise with another message
    with pytest.raises(ValueError, match=r"^grid must be 'base' or 'variants'"):
        dr.run([], None, grid=grid)


# --- the calls column (red until v1.45) ------------------------------------------------------------

@no_calls_column
def test_table_has_a_calls_column_when_a_point_carries_work_calls(dr):
    got = dr.table(handmade([point(10, True, work_calls=2)]))
    assert got == "\n".join([CALLS_HEADER, CALLS_DASHES,
                             "0.5  cost_effective  10       True      2      " + CALLS_TAIL])


@no_calls_column
def test_table_prints_1_for_a_point_without_work_calls_beside_one_with_it(dr):
    got = dr.table(handmade([point(10, True, work_calls=3), point(20, False)]))
    assert got == "\n".join([CALLS_HEADER, CALLS_DASHES,
                             "0.5  cost_effective  10       True      3      " + CALLS_TAIL,
                             "0.5  cost_effective  20       False     1      " + CALLS_TAIL])


# --- the CLI (red until v1.45) ---------------------------------------------------------------------

@no_grid_option
def test_cli_grid_variants_writes_the_variant_run_and_its_table(dr, tmp_path, capsys):
    matrix, pool = write_inputs(tmp_path)
    out = tmp_path / "variants.json"
    assert dr.main(["--matrix", matrix, "--registry", pool, "--grid", "variants",
                    "--out", str(out)]) == 0
    rows, registry = tiny()
    assert out.read_text(encoding="utf-8") == json.dumps(
        dr.run(rows, registry, grid="variants"), indent=2) + "\n"
    assert not (tmp_path / "variants.json.part").exists()
    capsys.readouterr()
    assert dr.main(["--table", str(out)]) == 0
    printed = capsys.readouterr().out
    assert printed == dr.table(json.loads(out.read_text(encoding="utf-8"))) + "\n"
    assert printed.split("\n", 1)[0] == CALLS_HEADER


@no_grid_option
def test_cli_grid_base_writes_the_same_bytes_as_no_grid(dr, tmp_path):
    matrix, pool = write_inputs(tmp_path)
    assert dr.main(["--matrix", matrix, "--registry", pool, "--grid", "base",
                    "--out", str(tmp_path / "a.json")]) == 0
    assert dr.main(["--matrix", matrix, "--registry", pool, "--out", str(tmp_path / "b.json")]) == 0
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()


ONLY_MATRIX = "error: --grid is only used with --matrix\n"


@no_grid_option
@pytest.mark.parametrize("argv, err", [
    (["--table", "t", "--grid", "variants"], ONLY_MATRIX),
    (["--table", "t", "--bar", "0.8", "--point", "0", "--grid", "base"], ONLY_MATRIX),
    (["--breakeven", "t", "--bar", "0.8", "--point", "0", "--grid", "variants"], ONLY_MATRIX),
    (["--table", "t", "--out", "o", "--grid", "variants"],
     "error: --registry and --out are only used with --matrix\n"),
])
def test_cli_grid_is_only_used_with_matrix(dr, argv, err, capsys):
    assert dr.main(argv) == 2
    assert capsys.readouterr().err == err


@no_grid_option
def test_cli_refuses_an_unknown_grid_in_one_line(dr, capsys):
    assert dr.main(["--matrix", "m", "--registry", "r", "--out", "o", "--grid", "x"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: argument --grid: invalid choice") and err.count("\n") == 1
