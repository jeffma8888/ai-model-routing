"""Delegation results on LLMRouterBench (DESIGN 13.13; specified in v1.196, row E17b).

The 13.9 harness on the LLMRouterBench converter's default rows (12.18), filtered by the
script's ``select_rows`` to the 8 pool models the research note prices, with the 10 items that
have a null token count dropped, a committed registry of those 8 models, the 13.10 base points
and 4 of the 12.19 bars. v1.196 held every test that loads
``evidence/llmrouterbench-delegation/results.py`` or reads one of its three committed files
(``registry.json``, ``results.json``, ``RESULTS.md``) under a strict xfail marker naming
``FileNotFoundError``; row E17c (v1.197) commits them and removes the markers. The other tests
passed before and after: the 13.10 base points carry no ``work_calls``, the research note states each
price, window and window kind the registry takes from it, and, when the pinned file is cached,
the converter's rows filtered to the 8 models give the dropped items, kept counts and success
span that 13.13 states.

v1.239 (row E17f) adds a Reading it bullet that names, at the lowest bar and point 0, each parent
whose `cost_effective` decision costs more than always inline, with both costs and both held-out
successes; its test was committed ahead of the bullet as a strict xfail, and v1.240 lands the bullet
and removes the marker.
"""

import importlib.util
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "llmrouterbench-delegation"
SCRIPT = FOLDER / "results.py"
REGISTRY = FOLDER / "registry.json"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
DELEGATION_SCRIPT = ROOT / "evidence" / "delegation" / "results.py"
RESEARCH = ROOT / "research" / "delegation-datasets.md"

REVISION = "b95870f9e60c589e82f7972c91ffa8de9ca89f85"
DATASET_TREE = f"https://huggingface.co/datasets/NPULH/LLMRouterBench/tree/{REVISION}"
CLAUDE = "anthropic/claude-sonnet-4"
R1 = "deepseek/deepseek-r1-0528"
V3 = "deepseek/deepseek-v3-0324"
TERMINUS = "deepseek/deepseek-v3.1-terminus"
INTERN = "internlm/intern-s1"
GPT5 = "openai/gpt-5"
CHAT = "openai/gpt-5-chat"
GLM = "z-ai/glm-4.6"
POOL = (CLAUDE, R1, V3, TERMINUS, INTERN, GPT5, CHAT, GLM)
PAGE_PRICED = (CLAUDE, GPT5, CHAT, GLM)
OPEN_WEIGHTS = (R1, V3, TERMINUS, INTERN)
BARS = (0.1, 0.3, 0.5, 0.8)
SEEDS = 50
KEYS = ("config", "tasks", "summary")
STRATEGIES = ("decision", "inline", "delegate")
FLAVORS = ["cost_effective", "cost_blind"]
DROPPED = ["hle|1144", "hle|1265", "hle|2000", "hle|2072", "hle|554",
           "simpleqa|1137", "simpleqa|2574", "simpleqa|2683", "simpleqa|3592", "simpleqa|4113"]
KEPT_ITEMS = {"aime": 60, "arc-agi": 400, "arenahard": 749, "gpqa": 198, "hle": 2152,
              "livecodebench": 1055, "livemathbench": 121, "mmlupro": 3000, "simpleqa": 4321}
REGISTRY_MODEL_KEYS = ["id", "family", "price_in", "price_out", "context_window", "source", "notes"]
STATED_MODELS = [
    {"id": CLAUDE, "family": "anthropic", "price_in": 3, "price_out": 15, "context_window": 200000,
     "source": "https://platform.claude.com/docs/en/about-claude/pricing"},
    {"id": R1, "family": "deepseek", "price_in": 0.5, "price_out": 2.15, "context_window": 163840,
     "source": DATASET_TREE},
    {"id": V3, "family": "deepseek", "price_in": 0.25, "price_out": 0.88, "context_window": 163840,
     "source": DATASET_TREE},
    {"id": TERMINUS, "family": "deepseek", "price_in": 0.27, "price_out": 1, "context_window": 163840,
     "source": DATASET_TREE},
    {"id": INTERN, "family": "internlm", "price_in": 0.18, "price_out": 0.54, "context_window": 65536,
     "source": DATASET_TREE},
    {"id": GPT5, "family": "openai", "price_in": 1.25, "price_out": 10, "context_window": 400000,
     "source": "https://platform.openai.com/docs/models/gpt-5"},
    {"id": CHAT, "family": "openai", "price_in": 1.25, "price_out": 10, "context_window": 128000,
     "source": "https://platform.openai.com/docs/models/gpt-5-chat-latest"},
    {"id": GLM, "family": "z-ai", "price_in": 0.6, "price_out": 2.2, "context_window": 200000,
     "source": "https://docs.z.ai/guides/overview/pricing"},
]
TABLE_CMD = "$ python evidence/delegation/results.py --table evidence/llmrouterbench-delegation/results.json"
PARENT_CMD = TABLE_CMD + " --bar 0.1 --point 0"
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl",
    "python evidence/llmrouterbench-delegation/results.py --matrix llmrouterbench-matrix.jsonl --registry "
    "evidence/llmrouterbench-delegation/registry.json --out evidence/llmrouterbench-delegation/results.json",
    TABLE_CMD[2:],
    PARENT_CMD[2:],
]
GEMINI = ("The pool leaves out `google/gemini-2.5-pro`, the best single model of [the LLMRouterBench routing "
          "results](../llmrouterbench/RESULTS.md), since no vendor page prices it and its recorded costs give "
          "no exact price pair.")
NONE_CLEAR = "`none_clear` is 13.5 row 7: no model clears the bar, so the calibration bounds decide, not cost."


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ld():
    return _load("llmrouterbench_delegation_results", SCRIPT)


@pytest.fixture(scope="module")
def dr():
    return _load("delegation_results_for_llmrouterbench", DELEGATION_SCRIPT)


def g(x):
    return format(x, "g")


def join(parts):
    parts = list(parts)
    return parts[0] if len(parts) == 1 else ", ".join(parts[:-1]) + " and " + parts[-1]


def mean(values):
    values = list(values)
    return math.fsum(values) / len(values)


def section(text, heading):
    start = text.index(heading + "\n") + len(heading) + 1
    nxt = text.find("\n## ", start)
    return text[start:] if nxt == -1 else text[start:nxt]


def fenced(text, kind):
    return re.findall(r"```" + kind + r"\n(.*?)\n```", text, flags=re.S)


def table_rows(text, heading):
    """The `| ... |` rows of the first Markdown table after `heading`, cells stripped, header and rule skipped."""
    body = text[text.index(heading):]
    rows = []
    for line in body.split("\n")[1:]:
        if line.startswith("|"):
            rows.append([cell.strip() for cell in line.strip().strip("|").split("|")])
        elif rows:
            break
    return rows[2:]


def note_section():
    text = RESEARCH.read_text(encoding="utf-8")
    return text[text.index("## LLMRouterBench (2026-11-09)"):]


def window_rows():
    rows = table_rows(note_section(), "### Context windows (2026-11-10)")
    return {row[0].strip("`"): row for row in rows}


def committed_results():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def summary_index(results):
    return {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r for r in results["summary"]}


def row(task, item, model, correct, i, o):
    return {"task": task, "item": item, "model": model, "correct": correct, "cost_usd": 0.001,
            "input_tokens": i, "output_tokens": o}


def synthetic(items=40):
    rows = []
    for n in range(items):
        for model, every in (("vendor/a", 3), ("vendor/b", 2), ("other/c", 5)):
            rows.append(row("t", f"t|{n}", model, n % every != 0, 300 + 7 * n, 40 + n))
    registry = Registry([Model(id="vendor/a", family="vendor", price_in=3.0, price_out=15.0, context_window=1_000_000),
                         Model(id="vendor/b", family="vendor", price_in=0.4, price_out=1.6, context_window=1_000_000)])
    return rows, registry


def registry_json(registry):
    return {"models": [{"id": m.id, "family": m.family, "price_in": m.price_in, "price_out": m.price_out,
                        "context_window": m.context_window, "source": "fake"} for m in registry.models]}


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + "\n", encoding="utf-8")


# ---- plain tests: pass before and after row E17c ----

def test_base_points_carry_no_work_calls(dr):
    points = dr.points()
    assert len(points) == 4
    assert all("work_calls" not in p and "cached_read_ratio" not in p for p in points)


def test_research_note_states_each_registry_value():
    section_text = note_section()
    prices = {r[0].strip("`"): r for r in table_rows(section_text, "### List prices")}
    lines = {}
    for line in fenced(section_text, "text")[0].split("\n"):
        m = re.match(r"  ([a-z0-9./-]+): recorded ", line)
        if m:
            lines[m.group(1)] = line
    windows = window_rows()
    assert sorted(windows) == sorted(POOL)
    for stated in STATED_MODELS:
        mid = stated["id"]
        pair = f"{g(stated['price_in'])}, {g(stated['price_out'])}"
        if mid in PAGE_PRICED:
            assert prices[mid][1] == stated["source"], mid
            assert prices[mid][3] == pair, mid
        else:
            assert prices[mid][3] == "none found", mid
            assert f"exact pair {g(stated['price_in'])} in, {g(stated['price_out'])} out" in lines[mid], mid
        assert windows[mid][3] == f"{stated['context_window']:,}", mid
        kind = "weights' position limit" if mid in OPEN_WEIGHTS else "vendor page"
        assert windows[mid][4] == kind, mid
        if mid in OPEN_WEIGHTS:
            assert windows[mid][1].startswith("https://huggingface.co/") and "/config.json" in windows[mid][1], mid
    assert "exact pair 3 in, 15 out" in lines[CLAUDE]
    assert "summary: list price 4 of 13, exact pair 5 of 13, either 8 of 13" in section_text


# ---- the script and its files (row E17c) ----

def test_constants(ld):
    assert ld.POOL == POOL
    assert ld.BARS == BARS
    assert ld.SEEDS == SEEDS
    assert ld.KEYS == KEYS


def test_points_are_the_13_10_base_points(ld, dr):
    assert ld.points() == dr.points()


def test_select_rows_keeps_the_models_and_drops_null_count_items(ld):
    rows = [row("t", "t|1", "vendor/a", True, 10, 5), row("t", "t|1", "vendor/b", False, 11, 6),
            row("t", "t|1", "other/c", True, None, None),
            row("t", "t|10", "vendor/a", True, 12, None), row("t", "t|10", "vendor/b", True, 13, 7),
            row("t", "t|2", "vendor/b", False, 14, 8), row("t", "t|2", "vendor/a", True, 15, 9),
            row("u", "u|0", "vendor/a", False, None, 3), row("u", "u|0", "vendor/b", True, 16, 2)]
    before = json.dumps(rows)
    kept, dropped = ld.select_rows(rows, ["vendor/a", "vendor/b"])
    assert json.dumps(rows) == before
    assert dropped == ["t|10", "u|0"]
    assert kept == [rows[0], rows[1], rows[5], rows[6]]
    assert ld.select_rows(rows, ("vendor/b",)) == ([rows[1], rows[4], rows[5], rows[8]], [])


def test_select_rows_errors(ld):
    good = [row("t", "t|1", "vendor/a", True, 10, 5)]
    for models in ([], (), "vendor/a", ["vendor/a", "vendor/a"], [""], [3], None):
        with pytest.raises(ValueError):
            ld.select_rows(good, models)
    for rows in (None, "rows", {"a": 1}):
        with pytest.raises(ValueError):
            ld.select_rows(rows, ["vendor/a"])
    for key in ("item", "model", "input_tokens", "output_tokens"):
        bad = dict(good[0])
        del bad[key]
        with pytest.raises(ValueError):
            ld.select_rows([bad], ["vendor/a"])
    with pytest.raises(ValueError):
        ld.select_rows(["not a dict"], ["vendor/a"])
    with pytest.raises(ValueError):
        ld.select_rows(good, ["vendor/a", "vendor/zz"])
    with pytest.raises(ValueError):
        ld.select_rows([row("t", "t|1", "vendor/a", True, None, 5)], ["vendor/a"])


def test_run_is_evaluate_delegation_keeping_keys(ld):
    rows, registry = synthetic()
    kept, dropped = ld.select_rows(rows, ["vendor/a", "vendor/b"])
    assert dropped == []
    result = ld.run(kept, registry)
    full = evaluate_delegation(kept, registry, bars=list(BARS), points=ld.points(), seeds=range(SEEDS))
    assert list(result) == list(KEYS)
    assert result == {key: full[key] for key in KEYS}


def test_cli_writes_the_run_on_the_rows_left(ld, tmp_path):
    rows, registry = synthetic()
    rows.append(row("t", "t|0", "other/c", True, None, None))
    matrix = tmp_path / "m.jsonl"
    write_jsonl(matrix, rows)
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(registry_json(registry)), encoding="utf-8")
    out = tmp_path / "results.json"
    assert ld.main(["--matrix", str(matrix), "--registry", str(reg), "--out", str(out)]) == 0
    kept, _ = ld.select_rows(rows, ["vendor/a", "vendor/b"])
    assert out.read_text(encoding="utf-8") == json.dumps(ld.run(kept, registry), indent=2) + "\n"
    assert not (tmp_path / "results.json.part").exists()


def test_cli_errors(ld, tmp_path, capsys):
    rows, registry = synthetic()
    matrix = tmp_path / "m.jsonl"
    write_jsonl(matrix, rows)
    reg = tmp_path / "registry.json"
    payload = registry_json(registry)
    payload["models"].append({"id": "vendor/zz", "family": "vendor", "price_in": 1.0, "price_out": 1.0,
                              "context_window": 1000, "source": "fake"})
    reg.write_text(json.dumps(payload), encoding="utf-8")
    out = tmp_path / "results.json"
    out.write_text("keep\n", encoding="utf-8")
    for argv in (["--matrix", str(tmp_path / "absent.jsonl"), "--registry", str(reg), "--out", str(out)],
                 ["--matrix", str(matrix), "--registry", str(reg), "--out", str(out)]):
        assert ld.main(argv) == 1
        err = capsys.readouterr().err
        assert err.startswith("error: ") and err.count("\n") == 1
        assert out.read_text(encoding="utf-8") == "keep\n"
        assert not (tmp_path / "results.json.part").exists()
    with pytest.raises(SystemExit) as exc:
        ld.main(["--matrix", str(matrix), "--out", str(out)])
    assert exc.value.code == 2


def test_cli_out_with_an_empty_name_is_one_error_line(ld, tmp_path, capsys):
    rows, registry = synthetic()
    matrix = tmp_path / "m.jsonl"
    write_jsonl(matrix, rows)
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(registry_json(registry)), encoding="utf-8")
    for out in ("/", "."):
        assert ld.main(["--matrix", str(matrix), "--registry", str(reg), "--out", out]) == 1, out
        err = capsys.readouterr().err
        assert err.startswith("error: ") and err.count("\n") == 1, out


def test_cli_failure_removes_a_part_left_by_an_earlier_run(ld, tmp_path, capsys):
    rows, registry = synthetic()
    matrix = tmp_path / "m.jsonl"
    write_jsonl(matrix, rows)
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(registry_json(registry)), encoding="utf-8")
    out = tmp_path / "results.json"
    part = tmp_path / "results.json.part"
    for argv in (["--matrix", str(tmp_path / "absent.jsonl"), "--registry", str(reg), "--out", str(out)],
                 ["--matrix", str(matrix), "--registry", str(tmp_path / "absent.json"), "--out", str(out)]):
        out.write_text("keep\n", encoding="utf-8")
        part.write_text("stale\n", encoding="utf-8")
        assert ld.main(argv) == 1
        assert capsys.readouterr().err.startswith("error: ")
        assert out.read_text(encoding="utf-8") == "keep\n"
        assert not part.exists()


def test_registry_file():
    text = REGISTRY.read_text(encoding="utf-8")
    content = json.loads(text)
    assert text == json.dumps(content, indent=2) + "\n"
    assert list(content) == ["as_of", "note", "models"]
    assert content["as_of"] == "2026-11-10"
    assert "research/delegation-datasets.md" in content["note"]
    models = content["models"]
    assert [m["id"] for m in models] == list(POOL)
    windows = window_rows()
    for got, stated in zip(models, STATED_MODELS):
        assert list(got) == REGISTRY_MODEL_KEYS
        assert {k: got[k] for k in REGISTRY_MODEL_KEYS[:-1]} == stated
        assert got["family"] == got["id"].split("/")[0]
        notes = got["notes"]
        if got["id"] in OPEN_WEIGHTS:
            url = windows[got["id"]][1].split(" ")[0]
            for phrase in ("position limit", "not a served window", "max_position_embeddings", url, "12,056",
                           "1e-9 USD"):
                assert phrase in notes, (got["id"], phrase)
    by_id = {m["id"]: m["notes"] for m in models}
    for phrase in ("inferred", "https://platform.claude.com/docs/en/build-with-claude/context-windows", "June 15, 2026"):
        assert phrase in by_id[CLAUDE], phrase
    assert "Deprecated" in by_id[GPT5] and "0.906" in by_id[GPT5]
    assert "Shut down" in by_id[CHAT] and "0.967" in by_id[CHAT]
    for phrase in ("200K", "https://docs.z.ai/guides/llm/glm-4.6", "200,000", "0.996"):
        assert phrase in by_id[GLM], phrase
    Registry.load(REGISTRY)


def test_results_file_shape(dr):
    text = RESULTS.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 300_000
    results = json.loads(text)
    assert text == json.dumps(results, indent=2) + "\n"
    assert list(results) == list(KEYS)
    config = results["config"]
    assert config["bars"] == list(BARS)
    assert config["seeds"] == list(range(SEEDS))
    assert config["flavors"] == FLAVORS
    assert config["points"] == dr.points()
    assert config["parents"] == list(POOL)
    assert results["tasks"] == {task: {"items": n, "models": list(POOL)} for task, n in KEPT_ITEMS.items()}
    keys = list(summary_index(results))
    assert len(keys) == len(results["summary"]) == len(BARS) * 2 * 4 * len(POOL) * 3 == 768


def test_results_md_structure():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert text.split("\n")[0] == "# Delegation on LLMRouterBench: inline or sub-agent on held-out single calls"
    text.encode("ascii")
    assert "\u2013" not in text and "\u2014" not in text
    for needle in ("https://huggingface.co/datasets/NPULH/LLMRouterBench", REVISION, "MIT", "(registry.json)",
                   "(results.json)", "(../llmrouterbench/README.md)", "(../../research/delegation-datasets.md)"):
        assert needle in text, needle
    headings = [line for line in text.split("\n") if line.startswith("## ")]
    assert headings == ["## Method", "## Assumed", "## Results", "## Reading it", "## Regenerate"]
    method = section(text, "## Method")
    assert GEMINI in method
    assert NONE_CLEAR in method
    for needle in [f"`{m}`" for m in POOL] + ["`swe-bench`"]:
        assert needle in method, needle
    assumed = section(text, "## Assumed")
    for phrase in ("lossless", "list price", "0.906", "1.000", "position limit", "inferred", "200K", "200,000",
                   "10", "2025", "0.5", "13.8"):
        assert phrase in assumed, phrase


def test_results_md_tables_are_the_committed_file(dr):
    results = committed_results()
    blocks = fenced(section(RESULTS_MD.read_text(encoding="utf-8"), "## Results"), "text")
    assert len(blocks) == 2
    assert blocks[0] == TABLE_CMD + "\n" + dr.table(results).rstrip("\n")
    assert blocks[1] == PARENT_CMD + "\n" + dr.parent_table(results, 0.1, 0).rstrip("\n")


def test_results_md_reading_it_is_built_from_the_committed_file():
    results = committed_results()
    index = summary_index(results)
    parents = results["config"]["parents"]
    bars = results["config"]["bars"]
    points = results["config"]["points"]
    rates = [index[(b, "cost_effective", p, q, "decision")]["delegate_rate"]
             for b in bars for p in (0, 1, 2) for q in parents]
    assert all(rate == 1.0 for rate in rates)
    folded = [f"{mean(index[(b, 'cost_effective', 3, q, 'decision')]['delegate_rate'] for q in parents):.3f}"
              for b in bars]
    first = ("In `cost_effective` the decision delegates on every seed for every parent at points 0 to 2 at every "
             f"bar (`delegate_rate` 1.0 on all {len(rates)} of their decision rows); at point 3, the work folded into "
             f"the parent's next call, its rate averaged over the {len(parents)} parents is {join(folded)} at bars "
             f"{join(str(b) for b in bars)}.")

    def means(bar, strategy):
        rows = [index[(bar, "cost_effective", 0, q, strategy)] for q in parents]
        return mean(r["success"] for r in rows), mean(r["cost_usd"] for r in rows)

    low, high = bars[0], bars[-1]
    dec_s, dec_c = means(low, "decision")
    inl_s, inl_c = means(low, "inline")
    second = (f"At bar {low} and point 0 ({points[0]['context_tokens']:,} context tokens), averaged over the "
              f"{len(parents)} parents, the `cost_effective` decision costs {dec_c:.4f} USD on a held-out half "
              f"against {inl_c:.4f} for always inline ({inl_c / dec_c:.2f} times as much), with held-out success "
              f"{dec_s:.3f} against {inl_s:.3f}.")
    hdec_s, hdec_c = means(high, "decision")
    hinl_s, hinl_c = means(high, "inline")
    third = (f"At bar {high} and point 0 it costs {hdec_c:.4f} USD against {hinl_c:.4f} for always inline, with "
             f"held-out success {hdec_s:.3f} against {hinl_s:.3f}.")
    size = f"`results.json` is {len(RESULTS.read_bytes()):,} bytes."
    reading = section(RESULTS_MD.read_text(encoding="utf-8"), "## Reading it")
    bullets = [line[2:] for line in reading.split("\n") if line.startswith("- ")]
    for bullet in (first, second, third, size):
        assert bullet in bullets, bullet


def dearer_than_inline(results):
    """The 13.13 v1.239 bullet: at the lowest bar and point 0, each parent whose `cost_effective` decision
    `cost_usd` exceeds its always-inline one, compared unrounded, in the config's parent order."""
    index = summary_index(results)
    bar, parents = results["config"]["bars"][0], results["config"]["parents"]
    dearer = []
    for parent in parents:
        dec = index[(bar, "cost_effective", 0, parent, "decision")]
        inl = index[(bar, "cost_effective", 0, parent, "inline")]
        if dec["cost_usd"] > inl["cost_usd"]:
            dearer.append(f"`{parent}` ({dec['cost_usd']:.4f} against {inl['cost_usd']:.4f} USD, held-out success "
                          f"{dec['success']:.3f} against {inl['success']:.3f})")
    start = f"At bar {bar} and point 0 the `cost_effective` decision costs more than always inline for "
    if not dearer:
        return start + "no parent."
    return start + f"{len(dearer)} of the {len(parents)} parents: {join(dearer)}."


def test_dearer_than_inline_bullet_cases():
    """The builder on hand-made summaries: no parent, one, and two in config order; a tie is not dearer."""
    def results(costs):
        summary = []
        for parent, (dec, inl) in costs.items():
            summary.append({"bar": 0.1, "flavor": "cost_effective", "point": 0, "parent": parent,
                            "strategy": "decision", "cost_usd": dec, "success": 0.5})
            summary.append({"bar": 0.1, "flavor": "cost_effective", "point": 0, "parent": parent,
                            "strategy": "inline", "cost_usd": inl, "success": 0.25})
        return {"config": {"bars": [0.1, 0.8], "parents": list(costs)}, "summary": summary}

    start = "At bar 0.1 and point 0 the `cost_effective` decision costs more than always inline for "
    assert dearer_than_inline(results({"a/x": (1.0, 2.0), "b/y": (3.0, 3.0)})) == start + "no parent."
    assert dearer_than_inline(results({"a/x": (2.0, 1.0), "b/y": (1.0, 2.0)})) == (
        start + "1 of the 2 parents: `a/x` (2.0000 against 1.0000 USD, held-out success 0.500 against 0.250).")
    assert dearer_than_inline(results({"b/y": (5.0, 1.0), "a/x": (2.0, 1.0), "c/z": (0.5, 1.0)})) == (
        start + "2 of the 3 parents: `b/y` (5.0000 against 1.0000 USD, held-out success 0.500 against 0.250) and "
        "`a/x` (2.0000 against 1.0000 USD, held-out success 0.500 against 0.250).")


def test_results_md_reading_it_names_the_parents_dearer_than_inline():
    results = committed_results()
    bullet = dearer_than_inline(results)
    reading = section(RESULTS_MD.read_text(encoding="utf-8"), "## Reading it")
    bullets = [line[2:] for line in reading.split("\n") if line.startswith("- ")]
    assert bullets.count(bullet) == 1, bullet
    at = bullets.index(bullet)
    high = results["config"]["bars"][-1]
    assert bullets[at - 1].startswith(f"At bar {high} and point 0 it costs "), bullets[at - 1]
    assert bullets[at + 1] == f"`results.json` is {len(RESULTS.read_bytes()):,} bytes.", bullets[at + 1]


def test_results_md_regenerate_block():
    blocks = fenced(section(RESULTS_MD.read_text(encoding="utf-8"), "## Regenerate"), "bash")
    assert blocks and blocks[0].split("\n") == REGENERATE


# ---- the README subsection (DESIGN 12.8 v1.200) ----

README = ROOT / "README.md"
EVIDENCE_HEADINGS = ["RouterBench", "AutoBench", "AutoBench judges", "tau2-bench", "LiveCodeBench",
                     "LLMRouterBench", "Delegation on AutoBench", "Delegation on tau2-bench",
                     "Delegation on LLMRouterBench"]
README_LINKS = (
    "[LLMRouterBench](https://huggingface.co/datasets/NPULH/LLMRouterBench)",
    f"[`{REVISION[:7]}`]({DATASET_TREE})",
    '(licence MIT, "Copyright (c) 2025-2026 LLMRouterBench contributors")',
    "[RESULTS.md](evidence/llmrouterbench-delegation/RESULTS.md)",
    "[results.json](evidence/llmrouterbench-delegation/results.json)",
    "[registry.json](evidence/llmrouterbench-delegation/registry.json)",
    "[evidence/llmrouterbench/README.md](evidence/llmrouterbench/README.md)",
    "[research/delegation-datasets.md](research/delegation-datasets.md)",
    "[inline or sub-agent](#inline-or-sub-agent)",
    "[LLMRouterBench](#llmrouterbench)",
    "8,000, 64,000 and 200,000",
    "list-price estimate",
)
# Each is the start of one RESULTS.md bullet that the README repeats verbatim (12.8 v1.200).
METHOD_LINES = ("`aime` has 60 items", "At point 2, C = 200,000", "Of the ")
ASSUMED_LINES = ("The lossless brief", "Every cost is a list price", "The windows of the three DeepSeek models",
                 "The 8 models are 2025 snapshots", "An `arenahard` score of 0.5", "The limits of `DESIGN.md` 13.8")
ROOT_GEMINI = GEMINI.replace("](../llmrouterbench/RESULTS.md)", "](evidence/llmrouterbench/RESULTS.md)")


def readme_subsection():
    text = README.read_text(encoding="utf-8")
    heading = "\n## Evidence: held-out results on public data\n"
    assert text.count(heading) == 1
    evidence = text.split(heading, 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.*)$", evidence, re.M) == EVIDENCE_HEADINGS
    return evidence.split("\n### Delegation on LLMRouterBench\n", 1)[1].split("\n### ", 1)[0]


def counts_sentence(results):
    config, tasks = results["config"], results["tasks"]
    benchmarks = join([f"`{name}` {task['items']:,}" for name, task in tasks.items()])
    parents = join([f"`{p}`" for p in config["parents"]])
    total = sum(task["items"] for task in tasks.values())
    return (f"Each item is one benchmark question, which each model answered in one recorded call, one task per "
            f"benchmark ({benchmarks} items, {total:,} in all), with each of the {len(config['parents'])} priced "
            f"models ({parents}) as the parent, over {len(config['seeds'])} seeds.")


def results_md_line(start, heading):
    found = [line for line in section(RESULTS_MD.read_text(encoding="utf-8"), heading).split("\n")
             if line.startswith(f"- {start}")]
    assert len(found) == 1, start
    return found[0]


def test_readme_subsection_links_the_sources_and_licence():
    sub = readme_subsection()
    for needle in README_LINKS:
        assert needle in sub, needle
    assert sub.isascii() and "\u2013" not in sub and "\u2014" not in sub
    assert "](../" not in sub


def test_readme_subsection_shows_the_counts_tables_and_reading_it(dr):
    sub = readme_subsection()
    results = committed_results()
    assert counts_sentence(results) in sub
    assert sum(task["items"] for task in results["tasks"].values()) == 12_056
    assert f"```text\n{TABLE_CMD}\n{dr.table(results)}\n```" in sub
    assert f"```text\n{PARENT_CMD}\n{dr.parent_table(results, results['config']['bars'][0], 0)}\n```" in sub
    # the first three Reading it bullets, which the RESULTS.md test builds from the committed file; the
    # v1.239 bullet on the parents dearer than inline and the size bullet, the last, stay in RESULTS.md
    reading = [line for line in section(RESULTS_MD.read_text(encoding="utf-8"), "## Reading it").split("\n")
               if line.startswith("- ")]
    assert reading[-1].startswith("- `results.json` is ")
    for line in reading[:3]:
        assert f"\n{line}\n" in sub, line
    for line in reading[3:]:
        assert line[2:] not in sub, line
    assert "`results.json` is " not in sub


def test_readme_subsection_repeats_the_results_md_lines():
    sub = readme_subsection()
    for start in METHOD_LINES:
        assert f"\n{results_md_line(start, '## Method')}\n" in sub, start
    for start in ASSUMED_LINES:
        assert f"\n{results_md_line(start, '## Assumed')}\n" in sub, start
    # The one repeated line with a link targets the routing RESULTS.md from the repo root.
    assert results_md_line("The pool leaves out", "## Method") == "- " + GEMINI
    assert f"\n- {ROOT_GEMINI}\n" in sub
    limits = sub.index("\nLimits, as RESULTS.md states them:\n")
    assert sub.index(results_md_line(METHOD_LINES[-1], "## Method")) < limits
    assert limits < sub.index(results_md_line(ASSUMED_LINES[0], "## Assumed"))


def test_readme_subsection_regenerate_block_is_the_results_md_one():
    sub = readme_subsection()
    assert re.findall(r"```bash\n.*?```\n", sub, re.S) == ["```bash\n" + "\n".join(REGENERATE) + "\n```\n"]


def test_readme_layout_names_the_results_md():
    text = README.read_text(encoding="utf-8")
    layout = text.split("\n## Layout\n", 1)[1].split("\n## ", 1)[0]
    tau2 = "(delegation on tau2-bench: evidence/tau2-bench-delegation/RESULTS.md)\n"
    assert tau2 + "                (delegation on LLMRouterBench: evidence/llmrouterbench-delegation/RESULTS.md)\n" in layout


def test_readme_limitations_name_the_third_dataset():
    text = README.read_text(encoding="utf-8")
    limits = text.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in limits.splitlines() if line.startswith("- The delegation evidence reads")]
    assert len(bullets) == 1
    assert bullets[0].startswith(
        "- The delegation evidence reads three datasets: the AutoBench 2026 matrix, LLMRouterBench on the "
        f"{len(POOL)} of its 13 pool models that a list price or the exact price pair of their recorded costs prices "
        "([evidence/llmrouterbench-delegation/RESULTS.md](evidence/llmrouterbench-delegation/RESULTS.md)), which "
        "leaves out its best single model, `google/gemini-2.5-pro`, and tau2-bench ")
    # the left-out model is the one RESULTS.md names
    assert GEMINI.startswith("The pool leaves out `google/gemini-2.5-pro`, the best single model")


# ---- cached-file tests: run only when the pinned LLMRouterBench file is in the default cache ----

@pytest.fixture(scope="module")
def pinned_rows(llmrouterbench_pinned):
    code, _report, path = llmrouterbench_pinned
    assert code == 0
    with open(path, encoding="utf-8") as fh:
        return [json.loads(line) for line in fh if line.strip()]


def test_pinned_rows_filtered_to_the_pool(pinned_rows):
    pool = [r for r in pinned_rows if r["model"] in POOL]
    null = sorted({r["item"] for r in pool if r["input_tokens"] is None or r["output_tokens"] is None})
    assert null == DROPPED
    kept = [r for r in pool if r["item"] not in set(null)]
    assert len(pool) - len(kept) == 80
    assert len(kept) == 96_448
    counts = Counter(r["task"] for r in kept if r["model"] == CLAUDE)
    assert dict(counts) == KEPT_ITEMS and sum(counts.values()) == 12_056
    tally = defaultdict(lambda: [0, 0])
    for r in kept:
        cell = tally[(r["task"], r["model"])]
        cell[0] += r["correct"]
        cell[1] += 1
    rates = sorted((a / n, key, a, n) for key, (a, n) in tally.items())
    assert len(rates) == 9 * 8
    assert rates[0][1:] == (("hle", V3), 78, 2152)
    assert rates[-1][1:] == (("aime", GPT5), 53, 60)
    assert all(rates[0][0] < bar < rates[-1][0] for bar in BARS)
    assert max(r["input_tokens"] for r in kept) == 16_563


@pytest.fixture(scope="module")
def pinned_full(llmrouterbench_delegation_full):
    # the session run of tests/conftest.py (DESIGN 13.8 v1.227): select_rows, then 13.9 at the
    # script's BARS, points() and SEEDS on the committed registry, as this fixture ran it before
    return llmrouterbench_delegation_full


def test_pinned_results_are_the_committed_bytes(pinned_full):
    kept, dropped, full = pinned_full
    assert dropped == DROPPED and len(kept) == 96_448
    text = json.dumps({key: full[key] for key in KEYS}, indent=2) + "\n"
    assert text == RESULTS.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) == 230_012


def test_pinned_prototype_numbers(pinned_full):
    _kept, _dropped, full = pinned_full
    cells = full["cells"]
    assert len(cells) == 115_200 and len(full["summary"]) == 768
    sizes = [c["expected_input_tokens"] + c["expected_output_tokens"] for c in cells]
    assert (min(sizes), max(sizes)) == (377, 6803)
    blocked = Counter((c["parent"], c["point"]) for c in cells if not c["inline_allowed"])
    expected = {(p, 2): 3600 for p in POOL if p != GPT5}
    expected[(INTERN, 1)] = 2184
    assert dict(blocked) == expected
    reasons = {f: Counter(c["reason"] for c in cells if c["flavor"] == f) for f in FLAVORS}
    assert reasons["cost_effective"] == {"delegate_cheaper": 19921, "none_clear": 14840, "parent_context_full": 13692,
                                         "parent_below_bar": 6555, "inline_cheaper": 2592}
    assert reasons["cost_blind"] == {"delegate_better": 17674, "none_clear": 14840, "parent_context_full": 13692,
                                     "parent_below_bar": 6555, "inline_as_good": 4839}
    aime = sorted({c["calibration_items"] for c in cells if c["task"] == "aime"})
    assert (aime[0], aime[-1]) == (22, 42)
    under = {c["seed"] for c in cells if c["task"] == "aime" and c["calibration_items"] < 30}
    assert len(under) == 25
    index = summary_index(full)
    for bar, dec, inl in ((0.1, (0.450, 69.5970), (0.445, 133.3194)), (0.8, (0.582, 221.6676), (0.445, 133.3194))):
        for strategy, (s, c) in (("decision", dec), ("inline", inl)):
            rows = [index[(bar, "cost_effective", 0, q, strategy)] for q in POOL]
            assert f"{mean(r['success'] for r in rows):.3f}" == f"{s:.3f}"
            assert f"{mean(r['cost_usd'] for r in rows):.4f}" == f"{c:.4f}"


def test_pinned_method_sentences(pinned_full):
    _kept, dropped, full = pinned_full
    per_task = Counter(item.split("|")[0] for item in dropped)
    left = sum(KEPT_ITEMS.values())
    drop = (f"{len(dropped)} items are dropped for a null token count ("
            + join(f"{n} in `{t}`" for t, n in sorted(per_task.items())) + f"), so {left:,} items remain.")
    counts = Counter(c["reason"] for c in full["cells"] if c["flavor"] == "cost_effective")
    total = sum(counts.values())
    ordered = sorted(counts.items(), key=lambda kv: (-kv[1], kv[0]))
    reasons = f"Of the {total:,} `cost_effective` cells, " + join(f"{n:,} `{r}`" for r, n in ordered) + "."
    method = section(RESULTS_MD.read_text(encoding="utf-8"), "## Method")
    assert drop in method
    assert reasons + " " + NONE_CLEAR in method


# --- v1.269 an --out that names an input (row D4h, DESIGN 13.13) ---------------------------------
# Committed as strict xfail ahead of the code; the implementing commit, v1.270, removed the marker.

class _Unread:
    """A stand-in for both reads: a call means a file was read before the --out check."""

    @staticmethod
    def load(path):
        raise AssertionError(f"{path} read before the --out check")


@pytest.mark.parametrize("case, option", [
    ("out is the matrix", "--matrix"), ("out is the registry", "--registry"),
    ("part is the matrix", "--matrix"), ("part is the registry", "--registry")])
def test_cli_out_naming_an_input_is_exit_2_before_any_read(ld, tmp_path, capsys, monkeypatch, case, option):
    matrix, reg, out = tmp_path / "m.jsonl", tmp_path / "registry.json", tmp_path / "results.json"
    if case == "out is the matrix":
        out = matrix
    elif case == "out is the registry":
        out = reg
    elif case == "part is the matrix":
        matrix = tmp_path / "results.json.part"
    else:
        reg = tmp_path / "results.json.part"
    matrix.write_text("matrix bytes\n", encoding="utf-8")
    reg.write_text("registry bytes\n", encoding="utf-8")
    before = {p.name: p.read_bytes() for p in sorted(tmp_path.iterdir())}
    monkeypatch.setattr(ld, "_read_rows", _Unread.load)
    monkeypatch.setattr(ld, "Registry", _Unread)
    assert ld.main(["--matrix", str(matrix), "--registry", str(reg), "--out", str(out)]) == 2, case
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err == f"error: --out (or its .part file) names the same file as {option}\n"
    assert {p.name: p.read_bytes() for p in sorted(tmp_path.iterdir())} == before
