"""v1.22 delegation results on AutoBench (DESIGN 13.10), written before the script.

``evidence/delegation/results.py`` runs ``evaluate_delegation`` (DESIGN 13.9) on the
AutoBench 2026 matrix with token counts and the pool registry, and prints the tables that
its RESULTS.md and the README show. The first tests check the script on small inputs with
known answers, the next ones the committed file against RESULTS.md and the README. The
last one reads the pinned AutoBench files only when they are already in the default cache
and skips otherwise (CI never downloads them). v1.37 adds the break-even table
(``breakeven_table`` and ``--breakeven``), which puts a number on how much held-out success
a lossy hand-off may lose before delegating does no better than working inline. v1.40 adds a
fourth grid point with the work folded into the parent's next call, on which the
``cost_effective`` decision keeps some work inline, and a ``separate`` column to ``table``.
"""

import importlib.util
import json
import math
import os
import re
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "delegation"
SCRIPT = FOLDER / "results.py"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
README = ROOT / "README.md"
TABLE_COMMAND = "$ python evidence/delegation/results.py --table evidence/delegation/results.json"
PARENT_COMMAND = TABLE_COMMAND + " --bar 0.8 --point 1"
REGENERATE = (
    "```bash\n"
    "python -m pip install -e .\n"
    "python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all"
    " --tokens --registry autobench-pool.json\n"
    "python evidence/delegation/results.py --matrix autobench-tokens.jsonl"
    " --registry autobench-pool.json --out evidence/delegation/results.json\n"
    "python evidence/delegation/results.py --table evidence/delegation/results.json\n"
    "python evidence/delegation/results.py --table evidence/delegation/results.json"
    " --bar 0.8 --point 1\n"
    "```\n")
# v1.48: the README block is the RESULTS.md one followed by the two Variant points lines
README_REGENERATE = REGENERATE[:-len("```\n")] + (
    "python evidence/delegation/results.py --matrix autobench-tokens.jsonl"
    " --registry autobench-pool.json --grid variants --out evidence/delegation/variants.json\n"
    "python evidence/delegation/results.py --table evidence/delegation/variants.json\n"
    "```\n")
MODELS = [
    "anthropic/claude-sonnet-5", "deepseek/deepseek-v4-flash-0731", "google/gemini-3.7-flash",
    "google/gemma-4-31b-it", "meta/muse-glimmer-30b", "meta/muse-spark-1.2",
    "minimax/minimax-m3", "moonshotai/kimi-k2.6", "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3.5-lightning", "openai/gpt-5.6-luna", "openai/gpt-5.6-sol",
    "openai/gpt-oss-120b", "qwen/qwen3.5-9b", "qwen/qwen3.8-max", "tencent/hy3",
    "xai/grok-4.3", "xai/grok-4.6", "zai/glm-5.2", "zai/glm-5.3"]
POINTS = [{"context_tokens": c, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
           "inline_separate_call": True} for c in (8000, 64000, 200000)] + [
    {"context_tokens": 8000, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
     "inline_separate_call": False}]
CONFIG = {"bars": [0.7, 0.8], "seeds": list(range(50)),
          "flavors": ["cost_effective", "cost_blind"], "points": POINTS, "parents": MODELS,
          "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95}
STRATEGIES = ("decision", "inline", "delegate")


def load(name, path):
    if not path.is_file():
        raise ModuleNotFoundError(f"no script at {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def dr():
    return load("delegation_results", SCRIPT)


# --- the script on small inputs ---------------------------------------------------------------

def test_constants_name_the_stated_run(dr):
    assert dr.BARS == (0.7, 0.8) and dr.SEEDS == 50
    assert dr.points() == POINTS
    assert [list(p) for p in dr.points()] == [list(POINTS[0])] * 4
    assert dr.points() is not dr.points()


def tiny():
    registry = Registry([
        Model(id="v/strong", family="S", price_in=3.0, price_out=12.0, context_window=1_000_000),
        Model(id="v/cheap", family="C", price_in=0.1, price_out=0.4, context_window=100_000)])
    rows = []
    for i in range(80):
        rows.append({"task": "all", "item": f"q{i}", "model": "v/strong", "correct": i % 10 != 0,
                     "input_tokens": 200 + i, "output_tokens": 900 + 3 * i})
        rows.append({"task": "all", "item": f"q{i}", "model": "v/cheap", "correct": i % 3 != 0,
                     "input_tokens": 180 + i, "output_tokens": 700 + 2 * i, "cost_usd": 1.0})
    return rows, registry


def test_run_is_evaluate_delegation_without_cells(dr):
    rows, registry = tiny()
    got = dr.run(rows, registry)
    full = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=POINTS, seeds=range(50))
    assert list(got) == ["config", "tasks", "summary"]
    assert got == {key: full[key] for key in ("config", "tasks", "summary")}
    assert got["config"]["parents"] == ["v/cheap", "v/strong"]
    blocked = [c for c in full["cells"] if c["parent"] == "v/cheap" and c["point"] == 2]
    assert blocked and all(c["reason"] == "parent_context_full" for c in blocked)


def test_a_folded_point_does_not_depend_on_c_while_every_window_has_room():
    # v1.40 (DESIGN 13.10): at K = 1 no folded cost reads C, and C enters the decision only
    # through the 13.4 rule 3 check, so one folded point stands for every C with room
    rows, registry = tiny()

    def without_point(result, index):
        return [{k: v for k, v in r.items() if k != "point"} for r in result["summary"]
                if r["point"] == index]

    folded = evaluate_delegation(rows, registry, bars=[0.7, 0.8], seeds=range(20),
                                 points=[dict(POINTS[3], context_tokens=c) for c in (8000, 64000)])
    assert without_point(folded, 0) == without_point(folded, 1)
    separate = evaluate_delegation(rows, registry, bars=[0.7, 0.8], seeds=range(20),
                                   points=[dict(POINTS[0], context_tokens=c) for c in (8000, 64000)])
    assert without_point(separate, 0) != without_point(separate, 1)


def handmade():
    point = {"context_tokens": 10, "brief_tokens": 1, "result_tokens": 2, "carry_turns": 0,
             "inline_separate_call": True}
    values = {("a/x", "decision"): (0.5, 1.0, 1.0), ("a/x", "inline"): (0.25, 0.5, None),
              ("a/x", "delegate"): (0.5, 1.0, None), ("b/y", "decision"): (0.7, 3.0, 0.0),
              ("b/y", "inline"): (0.75, 1.5, None), ("b/y", "delegate"): (0.9, 2.5, None)}
    summary = [{"bar": 0.5, "flavor": "cost_effective", "point": 0, "parent": parent,
                "strategy": strategy, "success": success, "cost_usd": cost,
                "below_bar_rate": 0.0, "delegate_rate": rate}
               for (parent, strategy), (success, cost, rate) in values.items()]
    return {"config": {"bars": [0.5], "seeds": [0], "flavors": ["cost_effective"],
                       "points": [point], "parents": ["a/x", "b/y"]},
            "tasks": {"t": {"items": 4, "models": ["a/x", "b/y"]}}, "summary": summary}


MEANS = "\n".join([
    "bar  flavor          context  separate  dec_success  dec_cost  inl_success  inl_cost"
    "  del_success  del_cost  delegated",
    "---  --------------  -------  --------  -----------  --------  -----------  --------"
    "  -----------  --------  ---------",
    "0.5  cost_effective  10       True      0.600        2.0000    0.500        1.0000"
    "    0.700        1.7500    0.500"])
PARENTS = "\n".join([
    "flavor          parent  delegated  dec_success  dec_cost  inl_success  inl_cost"
    "  del_success  del_cost",
    "--------------  ------  ---------  -----------  --------  -----------  --------"
    "  -----------  --------",
    "cost_effective  a/x     1.000      0.500        1.0000    0.250        0.5000"
    "    0.500        1.0000",
    "cost_effective  b/y     0.000      0.700        3.0000    0.750        1.5000"
    "    0.900        2.5000"])


def test_table_is_the_mean_over_parents(dr):
    assert dr.table(handmade()) == MEANS


def test_table_names_whether_inline_work_takes_its_own_call(dr):
    # v1.40: points 0 and 3 of the committed grid share C, so the `separate` column tells them apart
    results = handmade()
    results["config"]["points"][0]["inline_separate_call"] = False
    assert dr.table(results) == MEANS.replace("True ", "False")


def test_parent_table_is_one_row_per_flavor_and_parent(dr):
    assert dr.parent_table(handmade(), 0.5, 0) == PARENTS


@pytest.mark.parametrize("change, match", [
    (lambda r: r.pop("config"), "config"),
    (lambda r: r.pop("summary"), "summary"),
    (lambda r: r["summary"].pop(3), "b/y"),
    (lambda r: r["summary"].append(dict(r["summary"][0])), "repeated"),
])
def test_tables_refuse_bad_results(dr, change, match):
    for render in (dr.table, lambda r: dr.parent_table(r, 0.5, 0)):
        results = handmade()
        change(results)
        with pytest.raises(ValueError, match=match):
            render(results)


@pytest.mark.parametrize("bar, point, match", [(0.6, 0, "bar 0.6"), (0.5, 1, "point 1"),
                                               (0.5, -1, "point -1")])
def test_parent_table_refuses_a_bar_or_point_not_in_the_config(dr, bar, point, match):
    with pytest.raises(ValueError, match=match):
        dr.parent_table(handmade(), bar, point)


@pytest.mark.parametrize("argv", [
    [], ["--matrix", "m"], ["--matrix", "m", "--registry", "r"], ["--matrix", "m", "--out", "o"],
    ["--matrix", "m", "--registry", "r", "--out", "o", "--bar", "0.8", "--point", "1"],
    ["--table", "t", "--out", "o"], ["--table", "t", "--registry", "r"],
    ["--table", "t", "--bar", "0.8"], ["--table", "t", "--point", "1"],
    ["--table", "t", "--matrix", "m"],
])
def test_cli_usage_errors_are_one_line_and_exit_2(dr, argv, capsys):
    assert dr.main(argv) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ") and err.count("\n") == 1


def test_cli_writes_run_and_prints_both_tables(dr, tmp_path, capsys):
    rows, registry = tiny()
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps({"models": [
        {"id": "v/strong", "family": "S", "price_in": 3.0, "price_out": 12.0,
         "context_window": 1_000_000},
        {"id": "v/cheap", "family": "C", "price_in": 0.1, "price_out": 0.4,
         "context_window": 100_000}]}), encoding="utf-8")
    out = tmp_path / "results.json"
    assert dr.main(["--matrix", str(matrix), "--registry", str(pool), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == json.dumps(dr.run(rows, registry), indent=2) + "\n"
    assert not (tmp_path / "results.json.part").exists()
    capsys.readouterr()
    assert dr.main(["--table", str(out)]) == 0
    assert capsys.readouterr().out == dr.table(json.loads(out.read_text())) + "\n"
    assert dr.main(["--table", str(out), "--bar", "0.8", "--point", "1"]) == 0
    assert capsys.readouterr().out == dr.parent_table(json.loads(out.read_text()), 0.8, 1) + "\n"
    assert dr.main(["--table", str(out), "--bar", "0.9", "--point", "1"]) == 2
    assert capsys.readouterr().err.startswith("error: bar 0.9")


# --- v1.249 the --matrix output path and a stale part (row H5, DESIGN 13.10) -------------------
# Committed as strict xfail ahead of the code; the implementing commit removed the markers.

class _Unread:
    """A stand-in for both reads: a call means a file was read before the --out check."""

    @staticmethod
    def load(path):
        raise AssertionError(f"{path} read before the --out check")


def matrix_inputs(tmp_path):
    rows, registry = tiny()
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps({"models": [
        {"id": m.id, "family": m.family, "price_in": m.price_in, "price_out": m.price_out,
         "context_window": m.context_window} for m in registry.models]}), encoding="utf-8")
    return rows, registry, matrix, pool


def test_cli_out_with_an_empty_name_is_one_error_line_before_any_read(dr, tmp_path, capsys, monkeypatch):
    _, _, matrix, pool = matrix_inputs(tmp_path)
    monkeypatch.setattr(dr, "_read_rows", _Unread.load)
    monkeypatch.setattr(dr, "Registry", _Unread)
    for out in ("/", "."):
        assert dr.main(["--matrix", str(matrix), "--registry", str(pool), "--out", out]) == 2, out
        err = capsys.readouterr().err
        assert err.startswith("error: ") and err.count("\n") == 1, out


def test_cli_failure_removes_a_part_left_by_an_earlier_run(dr, tmp_path, capsys):
    _, _, matrix, pool = matrix_inputs(tmp_path)
    out, part = tmp_path / "results.json", tmp_path / "results.json.part"
    for argv in (["--matrix", str(tmp_path / "absent.jsonl"), "--registry", str(pool), "--out", str(out)],
                 ["--matrix", str(matrix), "--registry", str(tmp_path / "absent.json"), "--out", str(out)]):
        out.write_text("keep", encoding="utf-8")
        part.write_text("stale\n", encoding="utf-8")
        assert dr.main(argv) == 2
        err = capsys.readouterr().err
        assert err.startswith("error: ") and err.count("\n") == 1
        assert out.read_text(encoding="utf-8") == "keep"
        assert not part.exists()


def test_cli_ignores_an_oserror_from_removing_the_part(dr, tmp_path, capsys, monkeypatch):
    rows, registry, matrix, pool = matrix_inputs(tmp_path)
    want = json.dumps(dr.run(rows, registry), indent=2) + "\n"

    def refuse(self, missing_ok=False):
        raise PermissionError(13, "refused", str(self))

    monkeypatch.setattr(Path, "unlink", refuse)
    out = tmp_path / "results.json"
    assert dr.main(["--matrix", str(matrix), "--registry", str(pool), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == want
    assert capsys.readouterr().err == ""
    assert dr.main(["--matrix", str(tmp_path / "absent.jsonl"), "--registry", str(pool),
                    "--out", str(out)]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ") and "absent.jsonl" in err and "refused" not in err
    assert out.read_text(encoding="utf-8") == want


# --- v1.37 the break-even table on small inputs (DESIGN 13.10) -----------------------------------
# Committed as strict xfail ahead of breakeven_table; the implementing commit removed the markers.

def breakeven_handmade():
    """handmade() plus a parent below inline, one whose margins round to zero from below and
    one with a partial rate whose decision success is not the delegate's."""
    results = handmade()
    values = {("c/z", "decision"): (0.6, 1.0, 0.5), ("c/z", "inline"): (0.7, 1.0, None),
              ("c/z", "delegate"): (0.65, 1.0, None), ("d/w", "decision"): (0.3, 1.0, 0.25),
              ("d/w", "inline"): (0.3001, 1.0, None), ("d/w", "delegate"): (0.3, 1.0, None),
              ("e/v", "decision"): (0.62, 1.0, 0.4), ("e/v", "inline"): (0.6, 1.0, None),
              ("e/v", "delegate"): (0.6002, 1.0, None)}
    results["summary"] += [{"bar": 0.5, "flavor": "cost_effective", "point": 0, "parent": parent,
                            "strategy": strategy, "success": success, "cost_usd": cost,
                            "below_bar_rate": 0.0, "delegate_rate": rate}
                           for (parent, strategy), (success, cost, rate) in values.items()]
    results["config"]["parents"] += ["c/z", "d/w", "e/v"]
    return results


BREAKEVEN = "\n".join([
    "flavor          parent  delegated  dec_success  inl_success  del_success  del_margin"
    "  dec_breakeven",
    "--------------  ------  ---------  -----------  -----------  -----------  ----------"
    "  -------------",
    "cost_effective  a/x     1.000      0.500        0.250        0.500        0.250       0.250",
    "cost_effective  b/y     0.000      0.700        0.750        0.900        0.150       -",
    "cost_effective  c/z     0.500      0.600        0.700        0.650        -0.050      -0.200",
    "cost_effective  d/w     0.250      0.300        0.300        0.300        0.000       0.000",
    "cost_effective  e/v     0.400      0.620        0.600        0.600        0.000       0.050"])


def test_breakeven_table_is_the_margin_over_inline_per_parent(dr):
    # a/x delegates on every seed, so its break-even equals its margin; b/y never delegates
    # ("-"); c/z is below inline and delegates on half the seeds, so its break-even is twice
    # its decision's margin; d/w's margins are -0.0001 and -0.0004 and print 0.000; e/v's
    # always-delegate margin is +0.0002 (0.000) while its decision's, 0.02 over a rate of 0.4,
    # is 0.050, so neither column can be read off the other
    assert dr.breakeven_table(breakeven_handmade(), 0.5, 0) == BREAKEVEN


@pytest.mark.parametrize("change, match", [
    (lambda r: r.pop("config"), "config"),
    (lambda r: r.pop("summary"), "summary"),
    (lambda r: r["summary"].pop(3), "b/y"),
    (lambda r: r["summary"].append(dict(r["summary"][0])), "repeated"),
])
def test_breakeven_table_refuses_bad_results(dr, change, match):
    results = handmade()
    change(results)
    with pytest.raises(ValueError, match=match):
        dr.breakeven_table(results, 0.5, 0)


@pytest.mark.parametrize("bar, point, match", [(0.6, 0, "bar 0.6"), (0.5, 1, "point 1"),
                                               (0.5, -1, "point -1")])
def test_breakeven_table_refuses_a_bar_or_point_not_in_the_config(dr, bar, point, match):
    with pytest.raises(ValueError, match=match):
        dr.breakeven_table(handmade(), bar, point)


def near():
    """tiny() with two models of close success rates, so cost_blind delegates on part of the
    seeds for both parents."""
    rows, registry = tiny()
    for row in rows:
        number = int(row["item"][1:])
        row["correct"] = number % (7 if row["model"] == "v/strong" else 8) != 0
    return rows, registry


def test_dec_breakeven_is_exact_on_one_task():
    # DESIGN 13.10 v1.37: with one task a summary success is the seed mean of one cell's
    # held-out rate, every seed weighted equally whatever its held-out size, and delegate_rate
    # the share of seeds delegated, so lowering the decision's rate by L on every delegated
    # seed lowers its mean by L * delegate_rate
    rows, registry = near()
    full = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=POINTS, seeds=range(50))
    summary = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
               for r in full["summary"]}
    groups = {}
    for cell in full["cells"]:
        groups.setdefault((cell["bar"], cell["flavor"], cell["point"], cell["parent"]),
                          []).append(cell)
    shares = set()
    for key, cells in groups.items():
        assert {c["task"] for c in cells} == {"all"} and len(cells) == 50
        dec, inl = summary[key + ("decision",)], summary[key + ("inline",)]
        assert dec["success"] == math.fsum(c["success"]["decision"] for c in cells) / 50
        share = sum(c["mode"] == "delegate" for c in cells) / 50
        assert dec["delegate_rate"] == share
        shares.add(share)
        if share == 0:
            continue
        loss = (dec["success"] - inl["success"]) / share
        lowered = math.fsum(c["success"]["decision"] - (loss if c["mode"] == "delegate" else 0.0)
                            for c in cells) / 50
        assert lowered == pytest.approx(inl["success"], abs=1e-12), key
    assert len(shares - {0.0, 1.0}) >= 2, shares


@pytest.mark.parametrize("argv, match", [
    (["--breakeven", "t"], "--breakeven needs --bar and --point"),
    (["--breakeven", "t", "--bar", "0.8"], "--breakeven needs --bar and --point"),
    (["--breakeven", "t", "--point", "1"], "--breakeven needs --bar and --point"),
    (["--breakeven", "t", "--bar", "0.8", "--point", "1", "--out", "o"], "--registry and --out"),
    (["--breakeven", "t", "--bar", "0.8", "--point", "1", "--registry", "r"],
     "--registry and --out"),
    (["--breakeven", "t", "--table", "t", "--bar", "0.8", "--point", "1"], "not allowed with"),
    (["--breakeven", "t", "--matrix", "m", "--bar", "0.8", "--point", "1"], "not allowed with"),
])
def test_cli_breakeven_usage_errors_are_one_line_and_exit_2(dr, argv, match, capsys):
    assert dr.main(argv) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: ") and err.count("\n") == 1 and match in err, err


def test_cli_prints_the_breakeven_table(dr, tmp_path, capsys):
    path = tmp_path / "results.json"
    path.write_text(json.dumps(breakeven_handmade()), encoding="utf-8")
    assert dr.main(["--breakeven", str(path), "--bar", "0.5", "--point", "0"]) == 0
    assert capsys.readouterr().out == BREAKEVEN + "\n"
    assert dr.main(["--breakeven", str(path), "--bar", "0.6", "--point", "0"]) == 2
    assert capsys.readouterr().err.startswith("error: bar 0.6")


# --- the committed file, RESULTS.md and the README ---------------------------------------------

def committed():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def test_committed_file_is_the_stated_run(dr):
    text = RESULTS.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 300_000
    results = json.loads(text)
    assert text == json.dumps(results, indent=2) + "\n"
    assert list(results) == ["config", "tasks", "summary"]
    assert results["config"] == CONFIG
    assert results["tasks"] == {"all": {"items": 203, "models": MODELS}}
    keys = [(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"])
            for r in results["summary"]]
    assert keys == [(b, f, p, m, s) for b in CONFIG["bars"] for f in CONFIG["flavors"]
                    for p in range(len(POINTS)) for m in MODELS for s in STRATEGIES]


def block(command, text):
    return f"```text\n{command}\n{text}\n```\n"


def test_results_md_shows_both_tables_and_the_regenerate_commands(dr):
    md = RESULTS_MD.read_text(encoding="utf-8")
    results = committed()
    assert block(TABLE_COMMAND, dr.table(results)) in md
    assert block(PARENT_COMMAND, dr.parent_table(results, 0.8, 1)) in md
    assert REGENERATE in md
    for phrase in ("https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10",
                   "CC-BY-4.0", "list-price estimate", "never a billed cost",
                   "as if a brief of B tokens carried everything the item needs",
                   "as if C more tokens of context did not change it", "no prompt caching",
                   "[results.json](results.json)", "`DESIGN.md` 13.9", "`DESIGN.md` 13.10"):
        assert phrase in md, phrase


def reading_it(results):
    """The "Reading it" sentences, built from a results file (DESIGN 13.10)."""
    rows = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
            for r in results["summary"]}
    parents = results["config"]["parents"]
    points = results["config"]["points"]
    # v1.40: the every-seed and across-sizes sentences hold on the separate-call points only
    separate = [i for i, p in enumerate(points) if p["inline_separate_call"]]
    assert separate == [0, 1, 2], separate
    sizes = [f"{points[i]['context_tokens']:,}" for i in separate]
    n = len(parents)
    where = "at the three points where inline work takes a parent call of its own"

    def mean(bar, flavor, point, strategy, key):
        return math.fsum(rows[(bar, flavor, point, p, strategy)][key] for p in parents) / n

    def same(bar, flavor, strategy, key, fmt):
        values = {format(mean(bar, flavor, i, strategy, key), fmt) for i in separate}
        assert len(values) == 1, (bar, flavor, strategy, key, values)
        return values.pop()

    for i in range(len(points)):
        for p in parents:
            assert len({(r["success"], r["cost_usd"]) for (b, f, j, q, s), r in rows.items()
                        if (j, q, s) == (i, p, "inline")}) == 1, (i, p)
    out = []
    assert {rows[(0.7, "cost_effective", i, p, "decision")]["delegate_rate"]
            for i in separate for p in parents} == {1.0}
    out.append(f"At bar 0.7, {where}, `cost_effective` delegates on every seed for every parent "
               f"and holds a mean held-out success of "
               f"{same(0.7, 'cost_effective', 'decision', 'success', '.3f')} at "
               f"{same(0.7, 'cost_effective', 'decision', 'cost_usd', '.4f')} USD at each of them")
    for i in separate:
        for p in parents:
            dec, dlg = (rows[(0.8, "cost_effective", i, p, s)] for s in ("decision", "delegate"))
            assert dec["delegate_rate"] == 1.0, (i, p)
            assert (dec["success"], dec["cost_usd"]) == (dlg["success"], dlg["cost_usd"]), (i, p)
    out.append(f"At bar 0.8, {where}, `cost_effective` delegates on every seed for every parent, "
               f"so it scores and costs the same as always delegating: a mean held-out success "
               f"over the {n} parents of {same(0.8, 'cost_effective', 'decision', 'success', '.3f')}"
               f" at each of them, against {same(0.8, 'cost_effective', 'inline', 'success', '.3f')}"
               f" for always inline")
    first = [mean(0.8, "cost_effective", separate[0], s, "cost_usd") for s in ("decision", "inline")]
    last = [mean(0.8, "cost_effective", separate[-1], s, "cost_usd")
            for s in ("decision", "inline")]
    assert first[0] > first[1] and last[0] < last[1]
    out.append(f"At bar 0.8, with inline work in a parent call of its own, the `cost_effective` "
               f"decision costs more than always inline at {sizes[0]} context tokens "
               f"({first[0]:.4f} against {first[1]:.4f} USD) and far less at {sizes[-1]} "
               f"({last[0]:.4f} against {last[1]:.4f}), where that call re-reads the whole context")
    sol = {s: rows[(0.8, "cost_effective", 1, "openai/gpt-5.6-sol", s)] for s in STRATEGIES}
    assert sol["decision"]["success"] < sol["inline"]["success"]
    assert sol["decision"]["cost_usd"] < sol["inline"]["cost_usd"]
    out.append(f"With `openai/gpt-5.6-sol` as the parent at bar 0.8 and {sizes[1]} context "
               f"tokens, always inline scores {sol['inline']['success']:.3f} at "
               f"{sol['inline']['cost_usd']:.4f} USD; `cost_effective` delegates on "
               f"{100 * sol['decision']['delegate_rate']:.1f}% of seeds and scores "
               f"{sol['decision']['success']:.3f} at {sol['decision']['cost_usd']:.4f} USD, "
               f"{100 * sol['decision']['cost_usd'] / sol['inline']['cost_usd']:.0f}% of the "
               f"inline cost")
    luna = {s: rows[(0.8, "cost_blind", 1, "openai/gpt-5.6-luna", s)] for s in STRATEGIES}
    assert luna["decision"]["success"] < luna["inline"]["success"]
    assert luna["decision"]["cost_usd"] > luna["inline"]["cost_usd"]
    out.append(f"With `openai/gpt-5.6-luna` as the parent at bar 0.8 and {sizes[1]} context "
               f"tokens, `cost_blind` delegates on {100 * luna['decision']['delegate_rate']:.1f}% "
               f"of seeds and scores {luna['decision']['success']:.3f} against "
               f"{luna['inline']['success']:.3f} inline, at {luna['decision']['cost_usd']:.4f} "
               f"against {luna['inline']['cost_usd']:.4f} USD")
    out.append(folded_reading(results))
    return out


def folded_reading(results):
    """v1.40: the RESULTS.md and README bullet on the folded point (DESIGN 13.10)."""
    rows = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
            for r in results["summary"]}
    parents = results["config"]["parents"]
    points = results["config"]["points"]
    folded = [i for i, p in enumerate(points) if not p["inline_separate_call"]]
    assert len(folded) == 1, folded
    f = folded[0]
    n = len(parents)

    def mean(bar, strategy, key):
        return math.fsum(rows[(bar, "cost_effective", f, p, strategy)][key] for p in parents) / n

    def share(bar):
        rates = {p: rows[(bar, "cost_effective", f, p, "decision")]["delegate_rate"]
                 for p in parents}
        mixed = sum(0 < r < 1 for r in rates.values())
        never = [f"`{p}`" for p in parents if rates[p] == 0]
        assert mixed > 0, bar
        text = f"{mean(bar, 'decision', 'delegate_rate'):.3f} at bar {bar}, where {mixed} mix "
        text += "inline and delegated seeds"
        if never:
            text += f" and {', '.join(never)} never {'delegates' if len(never) == 1 else 'delegate'}"
        return text

    cost = {bar: [mean(bar, s, "cost_usd") for s in ("decision", "delegate")] for bar in (0.7, 0.8)}
    success = {bar: [mean(bar, s, "success") for s in ("decision", "delegate")]
               for bar in (0.7, 0.8)}
    assert all(c[0] < c[1] for c in cost.values()), cost
    return (f"With the work folded into the parent's next call (`inline_separate_call` False) at "
            f"{points[f]['context_tokens']:,} context tokens, `cost_effective` keeps some work "
            f"inline: its mean delegated share over the {n} parents is {share(0.7)}, and "
            f"{share(0.8)}. It costs less than always delegating at both bars: "
            f"{cost[0.7][0]:.4f} against {cost[0.7][1]:.4f} USD at bar 0.7 (held-out success "
            f"{success[0.7][0]:.3f} against {success[0.7][1]:.3f}) and {cost[0.8][0]:.4f} against "
            f"{cost[0.8][1]:.4f} at bar 0.8 ({success[0.8][0]:.3f} against "
            f"{success[0.8][1]:.3f}), while always inline costs {mean(0.8, 'inline', 'cost_usd'):.4f}"
            f" USD at {mean(0.8, 'inline', 'success'):.3f}")

def test_results_md_method_states_the_per_model_sizes(dr):
    # v1.35 (DESIGN 13.9): each model is priced at its own mean calibration sizes, and the
    # pooled medians are only the task's expected sizes for the context checks
    method = RESULTS_MD.read_text(encoding="utf-8").split("\n## Method\n", 1)[1].split("\n## ", 1)[0]
    for phrase in ("each model's accepted count there and its own mean input and output "
                   "tokens per answer there, which price it",
                   "the median input and output tokens of all the half's answers as the "
                   "task's expected sizes for the context-window checks"):
        assert phrase in method, phrase
    assert "and the median input and output tokens of the half's answers)" not in method


def test_results_md_reading_it_is_the_committed_results(dr):
    md = RESULTS_MD.read_text(encoding="utf-8")
    for sentence in reading_it(committed()):
        assert sentence in md, sentence
    assert f"{RESULTS.stat().st_size:,} bytes" in md


def readme_subsection():
    readme = README.read_text(encoding="utf-8")
    heading = "\n## Evidence: held-out results on public data\n"
    assert readme.count(heading) == 1
    section = readme.split(heading, 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.*)$", section, re.M) == ["RouterBench", "AutoBench",
                                                        "AutoBench judges", "tau2-bench",
                                                        "LiveCodeBench", "LLMRouterBench",
                                                        "Delegation on AutoBench", "Delegation on tau2-bench",
            "Delegation on LLMRouterBench"]
    return section.split("\n### Delegation on AutoBench\n", 1)[1].split("\n### ", 1)[0]


def test_readme_subsection_shows_the_table_and_links(dr):
    sub = readme_subsection()
    assert block(TABLE_COMMAND, dr.table(committed())) in sub
    for sentence in reading_it(committed())[1:3]:
        assert sentence in sub, sentence
    assert f"- {folded_reading(committed())}\n" in sub
    assert re.findall(r"```bash\n.*?```\n", sub, re.S) == [README_REGENERATE]
    for phrase in ("[RESULTS.md](evidence/delegation/RESULTS.md)",
                   "[results.json](evidence/delegation/results.json)",
                   "8,000, 64,000 and 200,000", "brief of 500 tokens", "500-token result",
                   "(`inline_separate_call` True)", "(`inline_separate_call` False)",
                   "`separate` whether inline work takes a parent call of its own (`True`) or "
                   "folds into the next call (`False`)", "(licence CC-BY-4.0)",
                   "The decision prices each model at its own mean input and output tokens "
                   "per answer on the calibration half; the median sizes of all the half's "
                   "answers are used only for the context-window checks.",
                   "](https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10/tree/43755180be7d8097068982d7a3f37fc04cd15379)",
                   "list-price estimate"):
        assert phrase in sub, phrase
    readme = README.read_text(encoding="utf-8")
    inline = readme.split("\n### Inline or sub-agent\n", 1)[1].split("\n## ", 1)[0]
    assert "[Delegation on AutoBench](#delegation-on-autobench)" in inline


BREAKEVEN_COMMAND = ("$ python evidence/delegation/results.py --breakeven"
                     " evidence/delegation/results.json --bar 0.8 --point 1")


def breakeven_reading(results):
    """v1.37: the RESULTS.md "Reading it" bullet and the README bullet on the bar 0.8, point 1
    break-even table, built from a results file (DESIGN 13.10)."""
    rows = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
            for r in results["summary"]}
    parents = results["config"]["parents"]
    n = len(parents)
    size = f"{results['config']['points'][1]['context_tokens']:,}"
    values = {}
    for p in parents:
        dec, inl, dlg = (rows[(0.8, "cost_effective", 1, p, s)] for s in STRATEGIES)
        assert dec["delegate_rate"] == 1.0 and dec["success"] == dlg["success"], p
        values[p] = (dec["success"] - inl["success"]) / dec["delegate_rate"]
    mean = math.fsum(values.values()) / n
    low = min(parents, key=values.get)
    below = sum(v < 0 for v in values.values())
    assert values[low] < 0 < mean
    md = (f"At bar 0.8 and {size} context tokens, `cost_effective` delegates on every seed for "
          f"every parent, so `dec_breakeven` equals `del_margin`: a lossy brief may lower the "
          f"delegated held-out success by a mean of {mean:.3f} over the {n} parents before the "
          f"decision does no better than always inline. The minimum is {values[low]:.3f}, with "
          f"`{low}` as the parent, and {below} of the {n} parents are below zero: they already "
          f"score higher inline than the delegate does with a lossless brief")
    readme = (f"A lossy brief is not measured, but the break-even table in "
              f"[RESULTS.md](evidence/delegation/RESULTS.md) puts a number on it: at bar 0.8 and "
              f"{size} context tokens, it may lower the delegated held-out success by a mean of "
              f"{mean:.3f} over the {n} parents before the `cost_effective` decision does no "
              f"better than always inline, and the minimum is {values[low]:.3f}, with `{low}` as "
              f"the parent, one of the {below} that already score higher inline than the "
              f"delegate does with a lossless brief")
    return md, readme


def test_results_md_shows_the_breakeven_block_and_its_reading(dr):
    md = RESULTS_MD.read_text(encoding="utf-8")
    results = committed()
    assert block(BREAKEVEN_COMMAND, dr.breakeven_table(results, 0.8, 1)) in md
    reading = md.split("\n## Reading it\n", 1)[1].split("\n## ", 1)[0]
    assert f"- {breakeven_reading(results)[0]}\n" in reading
    for phrase in ("`del_margin` is always delegating's held-out success minus always inline's",
                   "`dec_breakeven` is the decision's held-out success minus always inline's, "
                   "divided by its `delegated` share",
                   "exact here for the stored success, the mean over seeds of each seed's "
                   "held-out rate with every seed weighted equally, since all 203 questions "
                   "are one task",
                   "A value below zero means that always delegating, or the decision, already "
                   "scores below always inline with a lossless brief.",
                   "`-` where the decision never delegates"):
        assert phrase in md, phrase


def test_readme_subsection_states_the_breakeven_numbers(dr):
    assert f"- {breakeven_reading(committed())[1]}\n" in readme_subsection()


# --- v1.112: where a fixed policy beats the decision on both counts ---------------------------

def dominated(results):
    """v1.112 (DESIGN 13.10): the (bar, flavor, point, parent, strategy) keys, in config order,
    whose `inline` or `delegate` row has success at least the decision's and cost at most its,
    at least one of the two strictly, on the stored floats with no tolerance."""
    rows = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
            for r in results["summary"]}
    config = results["config"]
    out = []
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            for point in range(len(config["points"])):
                for parent in config["parents"]:
                    dec = rows[(bar, flavor, point, parent, "decision")]
                    for strategy in ("inline", "delegate"):
                        row = rows[(bar, flavor, point, parent, strategy)]
                        if (row["success"] >= dec["success"] and row["cost_usd"] <= dec["cost_usd"]
                                and (row["success"] > dec["success"]
                                     or row["cost_usd"] < dec["cost_usd"])):
                            out.append((bar, flavor, point, parent, strategy))
    return out


def test_dominated_needs_both_counts_and_one_strictly():
    results = handmade()
    # a/x: inline scores lower, delegate ties on both counts; b/y: both fixed policies dominate
    assert dominated(results) == [(0.5, "cost_effective", 0, "b/y", "inline"),
                                  (0.5, "cost_effective", 0, "b/y", "delegate")]
    for row in results["summary"]:
        if (row["parent"], row["strategy"]) == ("a/x", "delegate"):
            row["cost_usd"] = 0.999          # same success, strictly cheaper
        if (row["parent"], row["strategy"]) == ("b/y", "inline"):
            row["success"] = 0.7             # same success, strictly cheaper
        if (row["parent"], row["strategy"]) == ("b/y", "delegate"):
            row["cost_usd"] = 3.0            # strictly better success, same cost
    assert dominated(results) == [(0.5, "cost_effective", 0, "a/x", "delegate"),
                                  (0.5, "cost_effective", 0, "b/y", "inline"),
                                  (0.5, "cost_effective", 0, "b/y", "delegate")]
    for row in results["summary"]:
        if (row["parent"], row["strategy"]) == ("b/y", "delegate"):
            row["cost_usd"] = 3.0000001      # better success, but dearer
    assert (0.5, "cost_effective", 0, "b/y", "delegate") not in dominated(results)


def words(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def dominated_reading(results):
    """v1.112: the last RESULTS.md "Reading it" bullet, built from a results file
    (DESIGN 13.10)."""
    rows = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
            for r in results["summary"]}
    config = results["config"]
    points = config["points"]
    found = dominated(results)
    groups = [key[:4] for key in found]
    assert len(set(groups)) == len(groups), "a group dominated by both strategies"
    total = (len(config["bars"]) * len(config["flavors"]) * len(points)
             * len(config["parents"]))
    blind = [key for key in found if key[1] == "cost_blind"]
    effective = [key for key in found if key[1] == "cost_effective"]
    by_delegate = [key for key in blind if key[4] == "delegate"]
    by_inline = [key for key in blind if key[4] == "inline"]
    for key in by_delegate:
        assert rows[key]["success"] == rows[key[:4] + ("decision",)]["success"], key
    inline_parents = {key[3] for key in by_inline}
    assert len(inline_parents) == 1, inline_parents
    assert by_delegate and effective

    def where(idx):
        separate = [f"{points[i]['context_tokens']:,}" for i in idx
                    if points[i]["inline_separate_call"]]
        folded = [f"{points[i]['context_tokens']:,}" for i in idx
                  if not points[i]["inline_separate_call"]]
        parts = []
        if separate:
            parts.append(f"{words(separate)} context tokens with inline work in a call of its own")
        if folded:
            unit = "" if separate else " context tokens"
            parts.append(f"{words(folded)}{unit} with the work folded")
        return " and at ".join(parts)

    def values(keys, strategy, key, fmt):
        texts = [format(rows[k[:4] + (strategy,)][key], fmt) for k in keys]
        if key == "success" and len(set(texts)) == 1:
            return texts[0]
        return words(texts)

    order = []
    for key in effective:
        if (key[4], key[3], key[0]) not in order:
            order.append((key[4], key[3], key[0]))
    clauses = []
    for strategy, parent, bar in order:
        keys = [k for k in effective if (k[4], k[3], k[0]) == (strategy, parent, bar)]
        keys.sort(key=lambda k: (not points[k[2]]["inline_separate_call"], k[2]))
        policy = "inline" if strategy == "inline" else "delegating"
        clauses.append(
            f"always {policy} with `{parent}` as the parent at bar {bar}, at "
            f"{where([k[2] for k in keys])} ({values(keys, strategy, 'success', '.3f')} at "
            f"{values(keys, strategy, 'cost_usd', '.4f')} USD against the decision's "
            f"{values(keys, 'decision', 'success', '.3f')} at "
            f"{values(keys, 'decision', 'cost_usd', '.4f')})")
    listed = clauses[0] if len(clauses) == 1 else ", ".join(clauses[:-1]) + ", and " + clauses[-1]
    return (f"In {len(found)} of the {total} (bar, flavor, point, parent) groups a fixed policy "
            f"does at least as well as the decision on both counts, a held-out success at least "
            f"the decision's at a cost at most its and one of the two strictly: {len(blind)} in "
            f"`cost_blind` and {len(effective)} in `cost_effective`. In `cost_blind` always "
            f"delegating does so in {len(by_delegate)} of them, each at exactly the decision's "
            f"held-out success, and always inline in {len(by_inline)}, all with "
            f"`{inline_parents.pop()}` as the parent. In `cost_effective` they are {listed}. The "
            f"decision reads only the calibration half, where the bar is held on lower bounds and "
            f"each path is priced at that half's mean sizes, so a path chosen there can score "
            f"lower or cost more on the held-out half; a delegate that clears is taken whatever "
            f"its cost when the parent does not clear, the paths are ordered by bound before cost "
            f"when neither clears, and `cost_blind` keeps a tie of equal bounds inline whatever "
            f"delegating would save, as when the delegate is the parent's own model "
            f"(`DESIGN.md` 13.5 rows 2, 4 and 7)")


def test_results_md_names_where_a_fixed_policy_beats_the_decision(dr):
    results = committed()
    found = dominated(results)
    assert len(found) == 30
    assert [k for k in found if k[1] == "cost_effective"] == [
        (0.7, "cost_effective", 3, "google/gemini-3.7-flash", "delegate"),
        (0.8, "cost_effective", 0, "openai/gpt-5.6-luna", "inline"),
        (0.8, "cost_effective", 1, "openai/gpt-5.6-luna", "inline"),
        (0.8, "cost_effective", 3, "openai/gpt-5.6-luna", "inline")]
    reading = RESULTS_MD.read_text(encoding="utf-8").split("\n## Reading it\n", 1)[1]
    reading = reading.split("\n## ", 1)[0]
    bullet = f"- {dominated_reading(results)}"
    assert reading.count(bullet + "\n") == 1
    assert reading.rstrip("\n").endswith(bullet)


def test_readme_subsection_leaves_the_dominated_groups_to_results_md():
    assert "a fixed policy does at least as well" not in readme_subsection()


# --- v1.59: the delegation evidence reads one dataset (research/delegation-datasets.md) --------

DATASETS_NOTE = ROOT / "research" / "delegation-datasets.md"
DATASETS_LINK = "[research/delegation-datasets.md](research/delegation-datasets.md)"
TAU2_RESULTS_LINK = "[evidence/tau2-bench-delegation/RESULTS.md](evidence/tau2-bench-delegation/RESULTS.md)"


def test_readme_and_design_say_the_delegation_evidence_reads_one_dataset():
    note = DATASETS_NOTE.read_text(encoding="utf-8")
    for figure in ("each item is a conversation of 2 to 100 agent model calls",
                   "2 to 100 model calls per conversation",
                   "every one of the 4 agents on each of the 278 items",
                   "about three quarters of their prompt tokens",
                   "mis-prices both paths in directions that grow with K",
                   "a point's `work_calls` would not help: it sets one K for every item",
                   "before any tau2-bench delegation converter"):
        assert figure in note, figure
    sub = readme_subsection()
    # v1.75: the harness prices a conversation on its own calls from per-call rows (13.9);
    # v1.77: the tau2-bench converter writes them with --calls (12.14);
    # v1.79: the delegation results on them are committed (13.12)
    sentence = ("tau2-bench, which the "
                "routing evidence above also reads, records each item as a conversation of 2 to "
                "100 model calls, which the harness prices on the item's own calls only from "
                "rows that list each call's tokens; its converter's `--calls` writes such rows, "
                f"and the delegation results on them are in {TAU2_RESULTS_LINK} ({DATASETS_LINK}).")
    assert sub.count(sentence) == 1
    assert sub.index(sentence) < sub.index("[research/hand-off-data.md]") < sub.index("```text\n")
    readme = README.read_text(encoding="utf-8")
    limits = readme.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    bullets = [b for b in limits.split("\n") if b.startswith("- The delegation evidence reads")]
    assert bullets == [
        # v1.200: LLMRouterBench is the third (13.13, 12.8)
        "- The delegation evidence reads three datasets: the AutoBench 2026 matrix, LLMRouterBench on the 8 of "
        "its 13 pool models that a list price or the exact price pair of their recorded costs prices "
        "([evidence/llmrouterbench-delegation/RESULTS.md](evidence/llmrouterbench-delegation/RESULTS.md)), which "
        "leaves out its best single model, `google/gemini-2.5-pro`, and tau2-bench "
        f"({TAU2_RESULTS_LINK}), whose items are conversations of 2 to 100 model calls. The "
        "`DESIGN.md` 13.9 harness prices such an item "
        "on its own calls only from rows that list each call's input and output tokens "
        "(`call_input_tokens`, `call_output_tokens`), which the tau2-bench converter writes with "
        "`--calls`; fed a conversation's "
        "summed counts instead, it would mis-price both "
        "paths, by amounts that grow with the number of calls. Its list prices also leave out the "
        "prompt-cache discount that the recorded costs of the three OpenAI agents imply on about "
        f"three quarters of their prompt tokens ({DATASETS_LINK}). "
        # v1.92: the 13.12 cached point on these rows (12.8)
        "The cached point of the bullet above, applied to these rows with the ratio at 0.1, 0.25 "
        "or 0, moves no decision: each keeps the mode, model and reason it has at list price "
        "([RESULTS.md](evidence/tau2-bench-delegation/RESULTS.md#reading-it), `DESIGN.md` 13.12)"]
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    section = design.split("\n### 13.9 ", 1)[1].split("\n### ", 1)[0]
    measured = section.split("\n- What is measured and what is assumed:\n", 1)[1].split("\n- ", 1)[0]
    one = [b for b in measured.split("\n") if b.startswith("  - (v1.59) one dataset:")]
    assert len(one) == 1
    for phrase in ("read only the AutoBench matrix (12.9)",
                   "[`research/delegation-datasets.md`](research/delegation-datasets.md)",
                   "each item is a conversation of 2 to 100 model calls",
                   "a point's `work_calls` sets one K for every item",
                   "about three quarters of their prompt tokens"):
        assert phrase in one[0], phrase


# --- the pinned files, only when already cached ------------------------------------------------

def test_real_results_regenerate_byte_identical(dr, tmp_path):
    cv = load("autobench_convert", ROOT / "evidence" / "autobench-2026" / "convert.py")
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
    assert report["models"] == MODELS and report["kept"] == {"all": 203}
    path = tmp_path / "pool-registry.json"
    path.write_text(json.dumps(cv.pool_registry(pool)), encoding="utf-8")
    result = dr.run(rows, Registry.load(path))
    assert json.dumps(result, indent=2) + "\n" == RESULTS.read_text(encoding="utf-8")
    small = {m["id"]: m["context_window"] for m in cv.pool_registry(pool)["models"]
             if m["context_window"] < POINTS[2]["context_tokens"]}
    assert small == {"meta/muse-glimmer-30b": 131_072, "openai/gpt-oss-120b": 131_000}
    md = RESULTS_MD.read_text(encoding="utf-8")
    assert ("At 200,000 tokens `meta/muse-glimmer-30b` and `openai/gpt-oss-120b` (context windows "
            "of 131,072 and 131,000 tokens) have no room") in md
    for r in result["summary"]:
        if r["parent"] in small and r["point"] == 2 and r["strategy"] == "decision":
            assert r["delegate_rate"] == 1.0, r


# --- v1.269 an empty config, a bad --table file, an --out that names an input (row D4h) ----------
# Committed ahead of the code; each test the v1.268 script fails carried a strict xfail naming
# what it raised, and the implementing commit, v1.270, removed the markers.

@pytest.mark.parametrize("key", ["bars", "flavors", "points"])
def test_table_refuses_a_config_with_no_bar_flavor_or_point(dr, key):
    results = handmade()
    results["config"][key] = []
    with pytest.raises(ValueError, match=re.escape("config has no (bar, flavor, point)")):
        dr.table(results)


def test_table_refuses_a_config_with_no_parents_first(dr):
    results = handmade()
    results["config"]["parents"] = []
    with pytest.raises(ValueError, match="config has no parents"):
        dr.table(results)
    results["config"]["bars"] = []
    with pytest.raises(ValueError, match="config has no parents"):
        dr.table(results)


def test_parent_and_breakeven_tables_of_no_parents_are_the_header_alone(dr):
    for key in ("parents", "flavors"):
        results = handmade()
        results["config"][key] = []
        for got, headers in ((dr.parent_table(results, 0.5, 0), ["flavor", "parent", "delegated"] + dr.HEADERS),
                             (dr.breakeven_table(results, 0.5, 0), dr.BREAKEVEN_HEADERS)):
            assert got == "  ".join(headers) + "\n" + "  ".join("-" * len(h) for h in headers), key


@pytest.mark.parametrize("mode", ["--table", "--breakeven"])
@pytest.mark.parametrize("content, match", [
    (None, "No such file"), ("{not json", "invalid JSON"),
    ("[1, 2]", "expected a JSON object, got list")])
def test_cli_refuses_a_results_file_that_is_missing_not_json_or_not_an_object(
        dr, tmp_path, capsys, mode, content, match):
    path = tmp_path / "results.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    argv = [mode, str(path)] + (["--bar", "0.5", "--point", "0"] if mode == "--breakeven" else [])
    assert dr.main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.startswith("error: ") and captured.err.count("\n") == 1
    assert str(path) in captured.err and match in captured.err


def test_clashing_input_names_the_first_input_that_is_out_or_its_part(dr, tmp_path, monkeypatch):
    matrix, pool = tmp_path / "m.jsonl", tmp_path / "pool.json"
    matrix.write_text("matrix\n", encoding="utf-8")
    pool.write_text("registry\n", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    inputs = [("--matrix", str(matrix)), ("--registry", str(pool))]
    clash = dr.clashing_input
    assert clash(tmp_path / "results.json", inputs) is None
    assert clash(tmp_path / "m.json", inputs) is None
    assert clash(matrix, inputs) == "--matrix"
    assert clash(pool, inputs) == "--registry"
    assert clash(tmp_path / "sub" / ".." / "m.jsonl", inputs) == "--matrix"
    assert clash(tmp_path / "m", [("--matrix", str(tmp_path / "m.part"))]) == "--matrix"
    both = [("--registry", str(matrix) + ".part"), ("--matrix", str(matrix))]
    assert clash(matrix, both) == "--registry"
    assert clash(matrix, both[::-1]) == "--matrix"
    link = tmp_path / "link.json"
    link.symlink_to(matrix)
    assert clash(link, inputs) == "--matrix"
    assert clash(tmp_path / "pool.json", [("--registry", str(tmp_path / "sub" / ".." / "link.json"))]) is None
    assert clash(matrix, [("--registry", str(link))]) == "--registry"
    hard, hard_part = tmp_path / "hard.json", tmp_path / "other.json.part"
    os.link(matrix, hard)
    os.link(pool, hard_part)
    assert clash(hard, inputs) == "--matrix"
    assert clash(tmp_path / "other.json", inputs) == "--registry"

    def refuse(a, b):
        raise PermissionError(13, "refused", str(a))

    monkeypatch.setattr(os.path, "samefile", refuse)
    assert clash(hard, inputs) is None
    assert clash(matrix, inputs) == "--matrix"


def _named_files(tmp_path, case):
    """Matrix, registry and --out paths for one way an --out can name an input."""
    matrix, pool, out = tmp_path / "m.jsonl", tmp_path / "pool.json", tmp_path / "results.json"
    if case == "out is the matrix":
        out = matrix
    elif case == "out is the registry":
        out = pool
    elif case == "part is the matrix":
        matrix = tmp_path / "results.json.part"
    elif case == "part is the registry":
        pool = tmp_path / "results.json.part"
    matrix.write_text("matrix bytes\n", encoding="utf-8")
    pool.write_text("registry bytes\n", encoding="utf-8")
    return matrix, pool, out


CLASH_CASES = [("out is the matrix", "--matrix"), ("out is the registry", "--registry"),
               ("part is the matrix", "--matrix"), ("part is the registry", "--registry")]


def snapshot(folder):
    return {p.name: p.read_bytes() for p in sorted(folder.iterdir())}


@pytest.mark.parametrize("case, option", CLASH_CASES)
def test_cli_out_naming_an_input_is_a_usage_error_before_any_read(dr, tmp_path, capsys, monkeypatch,
                                                                  case, option):
    matrix, pool, out = _named_files(tmp_path, case)
    before = snapshot(tmp_path)
    monkeypatch.setattr(dr, "_read_rows", _Unread.load)
    monkeypatch.setattr(dr, "Registry", _Unread)
    for grid in ([], ["--grid", "variants"]):
        argv = ["--matrix", str(matrix), "--registry", str(pool), "--out", str(out)] + grid
        assert dr.main(argv) == 2, case
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == f"error: --out (or its .part file) names the same file as {option}\n"
        assert snapshot(tmp_path) == before
