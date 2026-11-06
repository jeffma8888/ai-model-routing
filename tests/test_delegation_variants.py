"""v1.45 variant points of the delegation results (DESIGN 13.10), written before the code.

A grid point that changes a 13.2 knob the base grid holds fixed goes in a second results
file, ``evidence/delegation/variants.json``, so the committed ``results.json`` keeps its bytes
and each file stays under about 300 KB. ``variant_points()`` holds the variant points, ``run``
takes ``grid="base"`` or ``grid="variants"``, the CLI takes ``--grid`` with ``--matrix`` only,
and ``table`` gains a ``calls`` column when a config point carries ``work_calls``.

These tests were committed in v1.45 ahead of the script, each under a strict xfail naming what
the v1.44 script raised (``AttributeError`` for ``variant_points``, ``TypeError`` for
``run(..., grid=...)``, ``AssertionError`` for the ``calls`` column and the ``--grid``
outcomes); v1.46 implements the script and removes the markers. v1.47 commits
``variants.json`` with a ``Variant points`` part in the delegation RESULTS.md, and the last tests
check the file, that part and its bullet against both committed files; the cached-file one
reads the pinned AutoBench files only when they are already in the default cache.
"""

import importlib.util
import json
import math
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "delegation" / "results.py"
RESULTS = ROOT / "evidence" / "delegation" / "results.json"
VARIANTS_FILE = ROOT / "evidence" / "delegation" / "variants.json"
RESULTS_MD = ROOT / "evidence" / "delegation" / "RESULTS.md"
VARIANTS_COMMAND = "$ python evidence/delegation/results.py --table evidence/delegation/variants.json"
VARIANTS_REGENERATE = (
    "```bash\n"
    "python evidence/delegation/results.py --matrix autobench-tokens.jsonl"
    " --registry autobench-pool.json --grid variants --out evidence/delegation/variants.json\n"
    "python evidence/delegation/results.py --table evidence/delegation/variants.json\n"
    "```\n")
STRATEGIES = ("decision", "inline", "delegate")
KEYS = ["config", "tasks", "summary"]
POINT_KEYS = ["context_tokens", "brief_tokens", "result_tokens", "carry_turns",
              "inline_separate_call", "work_calls"]
VARIANTS = [{"context_tokens": 64000, "brief_tokens": 500, "result_tokens": 500,
             "carry_turns": 1, "inline_separate_call": False, "work_calls": 2}]


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


# --- variant_points and run(grid=...) ------------------------------------------------------------

def test_variant_points_are_the_stated_variant_grid(dr):
    assert dr.variant_points() == VARIANTS
    assert [list(p) for p in dr.variant_points()] == [POINT_KEYS]
    assert dr.variant_points() is not dr.variant_points()


def test_run_on_the_variants_grid_is_evaluate_delegation_on_the_variant_points(dr):
    rows, registry = tiny()
    got = dr.run(rows, registry, grid="variants")
    full = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=VARIANTS, seeds=range(50))
    assert list(got) == KEYS
    assert got == {key: full[key] for key in KEYS}


def test_run_on_the_base_grid_is_the_default_run(dr):
    rows, registry = tiny()
    assert dr.run(rows, registry, grid="base") == dr.run(rows, registry)


@pytest.mark.parametrize("grid", ["", "Base", "variant", "all", None, 1])
def test_run_refuses_any_other_grid_before_evaluating(dr, grid):
    # no rows and no registry: evaluate_delegation would raise with another message
    with pytest.raises(ValueError, match=r"^grid must be 'base' or 'variants'"):
        dr.run([], None, grid=grid)


# --- the calls column ------------------------------------------------------------------------------

def test_table_has_a_calls_column_when_a_point_carries_work_calls(dr):
    got = dr.table(handmade([point(10, True, work_calls=2)]))
    assert got == "\n".join([CALLS_HEADER, CALLS_DASHES,
                             "0.5  cost_effective  10       True      2      " + CALLS_TAIL])


def test_table_prints_1_for_a_point_without_work_calls_beside_one_with_it(dr):
    got = dr.table(handmade([point(10, True, work_calls=3), point(20, False)]))
    assert got == "\n".join([CALLS_HEADER, CALLS_DASHES,
                             "0.5  cost_effective  10       True      3      " + CALLS_TAIL,
                             "0.5  cost_effective  20       False     1      " + CALLS_TAIL])


# --- the CLI ---------------------------------------------------------------------------------------

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


def test_cli_grid_base_writes_the_same_bytes_as_no_grid(dr, tmp_path):
    matrix, pool = write_inputs(tmp_path)
    assert dr.main(["--matrix", matrix, "--registry", pool, "--grid", "base",
                    "--out", str(tmp_path / "a.json")]) == 0
    assert dr.main(["--matrix", matrix, "--registry", pool, "--out", str(tmp_path / "b.json")]) == 0
    assert (tmp_path / "a.json").read_bytes() == (tmp_path / "b.json").read_bytes()


ONLY_MATRIX = "error: --grid is only used with --matrix\n"


@pytest.mark.parametrize("argv, err", [
    (["--table", "t", "--grid", "variants"], ONLY_MATRIX),
    (["--table", "t", "--bar", "0.8", "--point", "0", "--grid", "base"], ONLY_MATRIX),
    (["--breakeven", "t", "--bar", "0.8", "--point", "0", "--grid", "variants"], ONLY_MATRIX),
    # the --grid check comes before the --bar and --point checks (DESIGN 13.10, v1.46)
    (["--table", "t", "--bar", "0.8", "--grid", "variants"], ONLY_MATRIX),
    (["--breakeven", "t", "--grid", "variants"], ONLY_MATRIX),
    (["--table", "t", "--out", "o", "--grid", "variants"],
     "error: --registry and --out are only used with --matrix\n"),
])
def test_cli_grid_is_only_used_with_matrix(dr, argv, err, capsys):
    assert dr.main(argv) == 2
    assert capsys.readouterr().err == err


def test_cli_refuses_an_unknown_grid_in_one_line(dr, capsys):
    assert dr.main(["--matrix", "m", "--registry", "r", "--out", "o", "--grid", "x"]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: argument --grid: invalid choice") and err.count("\n") == 1


# --- v1.47: the committed variants.json and its RESULTS.md part --------------------------------

def committed(path):
    return json.loads(path.read_text(encoding="utf-8"))


def test_committed_variants_file_is_the_stated_variant_run():
    text = VARIANTS_FILE.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 300_000
    variants = json.loads(text)
    assert text == json.dumps(variants, indent=2) + "\n"
    assert list(variants) == KEYS
    base = committed(RESULTS)
    assert list(variants["config"]) == list(base["config"])
    assert variants["config"] == {**base["config"], "points": VARIANTS}
    assert variants["tasks"] == base["tasks"]
    config = variants["config"]
    keys = [(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"])
            for r in variants["summary"]]
    assert keys == [(b, f, p, m, s) for b in config["bars"] for f in config["flavors"]
                    for p in range(len(VARIANTS)) for m in config["parents"] for s in STRATEGIES]


def variant_reading(base, variants):
    """The Variant points bullet: variant point 0 against base point 3 (DESIGN 13.10, v1.47)."""
    def index(results):
        rows = {}
        for r in results["summary"]:
            rows[(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"])] = r
        return rows

    rows = {"base": index(base), "variants": index(variants)}
    folded = [i for i, p in enumerate(base["config"]["points"])
              if not p["inline_separate_call"] and "work_calls" not in p]
    assert folded == [3], folded
    point = variants["config"]["points"][0]
    assert {k: point[k] for k in ("inline_separate_call", "work_calls")} == {
        "inline_separate_call": False, "work_calls": 2}
    at = {"base": folded[0], "variants": 0}
    parents = variants["config"]["parents"]
    assert parents == base["config"]["parents"]
    n = len(parents)

    def values(grid, bar, strategy, key):
        return [rows[grid][(bar, "cost_effective", at[grid], p, strategy)][key] for p in parents]

    def mean(grid, bar, strategy, key):
        return math.fsum(values(grid, bar, strategy, key)) / n

    bars = variants["config"]["bars"]
    assert bars == [0.7, 0.8]
    for bar in bars:
        assert all(r == 1.0 for r in values("variants", bar, "decision", "delegate_rate")), bar
    rate = {bar: mean("base", bar, "decision", "delegate_rate") for bar in bars}

    def costs(bar):
        pairs = [(label, mean("variants", bar, s, "cost_usd"), mean("base", bar, s, "cost_usd"))
                 for label, s in (("the decision", "decision"), ("always inline", "inline"),
                                  ("always delegating", "delegate"))]
        return ", ".join(f"{label} {v:.4f} against {b:.4f}" for label, v, b in pairs)

    return (f"With the work in two folded calls at {point['context_tokens']:,} context tokens "
            f"(variant point 0) instead of one (point 3, which stands for every context size with "
            f"room in every parent's window), `cost_effective` delegates on every seed for every "
            f"parent at both bars: its mean delegated share over the {n} parents is 1.000 at bar "
            f"0.7 and at bar 0.8, against {rate[0.7]:.3f} and {rate[0.8]:.3f} at point 3. Mean "
            f"costs in USD, variant point 0 against point 3: at bar 0.7 {costs(0.7)}; at bar 0.8 "
            f"{costs(0.8)}. On the inline path the second call re-reads the "
            f"{point['context_tokens']:,}-token context; on the delegate path each call reads only "
            f"the brief")


def variant_part():
    md = RESULTS_MD.read_text(encoding="utf-8")
    assert md.count("\n## Variant points\n") == 1
    headings = [line for line in md.split("\n") if line.startswith("## ")]
    assert headings == ["## Method", "## What is measured and what is assumed", "## Results",
                        "## Reading it", "## Variant points", "## Regenerate"], headings
    return md.split("\n## Variant points\n", 1)[1].split("\n## ", 1)[0]


def test_results_md_variant_part_shows_the_table_bullet_and_regenerate_lines(dr):
    part = variant_part()
    variants = committed(VARIANTS_FILE)
    assert f"```text\n{VARIANTS_COMMAND}\n{dr.table(variants)}\n```\n" in part
    assert f"- {variant_reading(committed(RESULTS), variants)}\n" in part
    assert VARIANTS_REGENERATE in part
    assert f"[variants.json](variants.json) ({VARIANTS_FILE.stat().st_size:,} bytes)" in part
    for phrase in ("`work_calls` 2", "the `calls` column", "`DESIGN.md` 13.10", "`DESIGN.md` 13.2",
                   "whether the two calls succeed together is not measured"):
        assert phrase in part, phrase
    md = RESULTS_MD.read_text(encoding="utf-8")
    assert "apart from the [Variant points](#variant-points) part" in md
    assert ("- One work call per path at points 0 to 3, two at variant point 0, and no prompt "
            "caching (`DESIGN.md` 13.8)\n") in md


def test_variant_reading_refuses_a_file_where_the_decision_keeps_work_inline():
    base, variants = committed(RESULTS), committed(VARIANTS_FILE)
    for row in variants["summary"]:
        if (row["bar"], row["flavor"], row["strategy"]) == (0.8, "cost_effective", "decision"):
            row["delegate_rate"] = 0.98
            break
    with pytest.raises(AssertionError):
        variant_reading(base, variants)


# --- the pinned files, only when already cached ------------------------------------------------

def test_real_variants_regenerate_byte_identical(dr, tmp_path):
    path = ROOT / "evidence" / "autobench-2026" / "convert.py"
    spec = importlib.util.spec_from_file_location("autobench_convert_variants", path)
    cv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cv)
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("pinned AutoBench files are not in the default cache")
    for name, (size, sha) in cv.FILES.items():
        cv.verify(folder / name, size, sha)
    params = json.loads((folder / "frozen_params.json").read_text(encoding="utf-8"))
    pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
    rows, report = cv.convert(cv.read_csv(folder / "matrix.csv"),
                              cv.read_csv(folder / "questions.csv"), pool, params["delta_signal"],
                              params["top_k"], task_by="all", tokens=True)
    assert report["kept"] == {"all": 203}
    registry = tmp_path / "pool-registry.json"
    registry.write_text(json.dumps(cv.pool_registry(pool)), encoding="utf-8")
    result = dr.run(rows, Registry.load(registry), grid="variants")
    assert json.dumps(result, indent=2) + "\n" == VARIANTS_FILE.read_text(encoding="utf-8")
