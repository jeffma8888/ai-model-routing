"""v1.22 delegation results on AutoBench (DESIGN 13.10), written before the script.

``evidence/delegation/results.py`` runs ``evaluate_delegation`` (DESIGN 13.9) on the
AutoBench 2026 matrix with token counts and the pool registry, and prints the tables that
its RESULTS.md and the README show. The first tests check the script on small inputs with
known answers, the next ones the committed file against RESULTS.md and the README. The
last one reads the pinned AutoBench files only when they are already in the default cache
and skips otherwise (CI never downloads them).
"""

import importlib.util
import json
import math
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
MODELS = [
    "anthropic/claude-sonnet-5", "deepseek/deepseek-v4-flash-0731", "google/gemini-3.7-flash",
    "google/gemma-4-31b-it", "meta/muse-glimmer-30b", "meta/muse-spark-1.2",
    "minimax/minimax-m3", "moonshotai/kimi-k2.6", "nvidia/nemotron-3-ultra-550b-a55b",
    "nvidia/nemotron-3.5-lightning", "openai/gpt-5.6-luna", "openai/gpt-5.6-sol",
    "openai/gpt-oss-120b", "qwen/qwen3.5-9b", "qwen/qwen3.8-max", "tencent/hy3",
    "xai/grok-4.3", "xai/grok-4.6", "zai/glm-5.2", "zai/glm-5.3"]
POINTS = [{"context_tokens": c, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
           "inline_separate_call": True} for c in (8000, 64000, 200000)]
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
    assert [list(p) for p in dr.points()] == [list(POINTS[0])] * 3
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
    "bar  flavor          context  dec_success  dec_cost  inl_success  inl_cost  del_success"
    "  del_cost  delegated",
    "---  --------------  -------  -----------  --------  -----------  --------  -----------"
    "  --------  ---------",
    "0.5  cost_effective  10       0.600        2.0000    0.500        1.0000    0.700"
    "        1.7500    0.500"])
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
                    for p in range(3) for m in MODELS for s in STRATEGIES]


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
    sizes = [f"{p['context_tokens']:,}" for p in results["config"]["points"]]
    n = len(parents)

    def mean(bar, flavor, point, strategy, key):
        return math.fsum(rows[(bar, flavor, point, p, strategy)][key] for p in parents) / n

    def same(bar, flavor, strategy, key, fmt):
        values = {format(mean(bar, flavor, i, strategy, key), fmt) for i in range(len(sizes))}
        assert len(values) == 1, (bar, flavor, strategy, key, values)
        return values.pop()

    for i in range(len(sizes)):
        for p in parents:
            assert len({(r["success"], r["cost_usd"]) for (b, f, j, q, s), r in rows.items()
                        if (j, q, s) == (i, p, "inline")}) == 1, (i, p)
    out = []
    assert {rows[(0.7, "cost_effective", i, p, "decision")]["delegate_rate"]
            for i in range(len(sizes)) for p in parents} == {1.0}
    out.append(f"At bar 0.7, `cost_effective` delegates on every seed for every parent and holds "
               f"a mean held-out success of {same(0.7, 'cost_effective', 'decision', 'success', '.3f')}"
               f" at {same(0.7, 'cost_effective', 'decision', 'cost_usd', '.4f')} USD at every point")
    always = {sum(1 for p in parents
                  if rows[(0.8, "cost_effective", i, p, "decision")]["delegate_rate"] == 1.0)
              for i in range(len(sizes))}
    assert len(always) == 1
    out.append(f"At bar 0.8, the `cost_effective` decision's mean held-out success over the {n} "
               f"parents is {same(0.8, 'cost_effective', 'decision', 'success', '.3f')} at every "
               f"point, against {same(0.8, 'cost_effective', 'inline', 'success', '.3f')} for "
               f"always inline and {same(0.8, 'cost_effective', 'delegate', 'success', '.3f')} for "
               f"always delegating; {always.pop()} of the {n} parents delegate on every seed")
    first = [mean(0.8, "cost_effective", 0, s, "cost_usd") for s in ("decision", "inline")]
    last = [mean(0.8, "cost_effective", len(sizes) - 1, s, "cost_usd")
            for s in ("decision", "inline")]
    assert first[0] > first[1] and last[0] < last[1]
    out.append(f"At bar 0.8 the `cost_effective` decision costs more than always inline at "
               f"{sizes[0]} context tokens ({first[0]:.4f} against {first[1]:.4f} USD) and far "
               f"less at {sizes[-1]} ({last[0]:.4f} against {last[1]:.4f}), where the parent's "
               f"own call for the work re-reads the whole context")
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
    return out


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
                                                        "AutoBench judges",
                                                        "Delegation on AutoBench"]
    return section.split("\n### Delegation on AutoBench\n", 1)[1]


def test_readme_subsection_shows_the_table_and_links(dr):
    sub = readme_subsection()
    assert block(TABLE_COMMAND, dr.table(committed())) in sub
    for sentence in reading_it(committed())[1:3]:
        assert sentence in sub, sentence
    assert REGENERATE in sub
    for phrase in ("[RESULTS.md](evidence/delegation/RESULTS.md)",
                   "[results.json](evidence/delegation/results.json)",
                   "8,000, 64,000 and 200,000", "brief of 500 tokens", "500-token result",
                   "(`inline_separate_call` True)", "(licence CC-BY-4.0)",
                   "](https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10/tree/43755180be7d8097068982d7a3f37fc04cd15379)",
                   "list-price estimate"):
        assert phrase in sub, phrase
    readme = README.read_text(encoding="utf-8")
    inline = readme.split("\n### Inline or sub-agent\n", 1)[1].split("\n## ", 1)[0]
    assert "[Delegation on AutoBench](#delegation-on-autobench)" in inline


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
