"""Delegation results on tau2-bench (DESIGN 13.12; specified in v1.78, committed in v1.79).

The 13.9 harness on the tau2-bench converter's ``--calls`` rows (12.14), one task per domain,
with a committed registry of the three agents the converter keeps, the 13.10 base points and the
12.15 bars. v1.78 held every test that loads ``evidence/tau2-bench-delegation/results.py`` or
reads one of its three committed files (``registry.json``, ``results.json``, ``RESULTS.md``)
under a strict xfail marker naming ``FileNotFoundError``; v1.79 commits them and removes the
markers. The other tests passed before and after: the 13.10 base points carry no
``work_calls``, the harness refuses the variant points with ``work_calls`` above 1 on per-call
rows, the research note states each price, window and status the registry takes from it, and,
when the 12 pinned files are cached, the ``--calls`` matrix keeps exactly the registry's agents.
"""

import importlib.util
import json
import math
import random
from collections import Counter
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "tau2-bench-delegation"
SCRIPT = FOLDER / "results.py"
REGISTRY = FOLDER / "registry.json"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
DELEGATION_SCRIPT = ROOT / "evidence" / "delegation" / "results.py"
CONVERTER = ROOT / "evidence" / "tau2-bench" / "convert.py"
RESEARCH = ROOT / "research" / "delegation-datasets.md"

BARS = (0.3, 0.4, 0.5, 0.6, 0.7, 0.8)
KEYS = ("config", "tasks", "summary")
STRATEGIES = ("decision", "inline", "delegate")
FLAVORS = ["cost_effective", "cost_blind"]
CLAUDE = "anthropic/claude-3-7-sonnet-20250219"
GPT41 = "openai/gpt-4.1-2025-04-14"
MINI = "openai/gpt-4.1-mini-2025-04-14"
O4 = "openai/o4-mini-2025-04-16"
KEPT = [CLAUDE, GPT41, MINI]
DOMAINS = {"airline": 50, "retail": 114, "telecom": 114}
REVISION = "033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f"
REGISTRY_MODEL_KEYS = ["id", "family", "price_in", "price_out", "context_window", "source", "notes"]
STATED_MODELS = [
    {"id": CLAUDE, "family": "anthropic", "price_in": 3, "price_out": 15, "context_window": 200000,
     "source": f"https://github.com/sierra-research/tau2-bench/tree/{REVISION}/data/tau2/results/final"},
    {"id": GPT41, "family": "openai", "price_in": 2.0, "price_out": 8.0, "context_window": 1047576,
     "source": "https://platform.openai.com/docs/models/gpt-4.1"},
    {"id": MINI, "family": "openai", "price_in": 0.4, "price_out": 1.6, "context_window": 1047576,
     "source": "https://platform.openai.com/docs/models/gpt-4.1-mini"},
]
TABLE_CMD = "$ python evidence/delegation/results.py --table evidence/tau2-bench-delegation/results.json"
PARENT_CMD = TABLE_CMD + " --bar 0.3 --point 0"
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls",
    "python evidence/tau2-bench-delegation/results.py --matrix tau2-calls.jsonl --registry "
    "evidence/tau2-bench-delegation/registry.json --out evidence/tau2-bench-delegation/results.json",
    TABLE_CMD[2:],
    PARENT_CMD[2:],
]

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def td():
    return _load("tau2_delegation_results", SCRIPT)


@pytest.fixture(scope="module")
def dr():
    return _load("delegation_results_for_tau2", DELEGATION_SCRIPT)


@pytest.fixture(scope="module")
def cv():
    return _load("tau2_convert_for_delegation", CONVERTER)


def call_row(task, item, model, correct, a, b):
    """A 13.9 v1.74 per-call row whose counts are what its calls read (Rd) and write (O)."""
    k = len(a)
    rd = sum((k - j) * a[j] + (k - j - 1) * b[j] for j in range(k))
    return {"task": task, "item": item, "model": model, "correct": correct,
            "input_tokens": rd, "output_tokens": sum(b),
            "call_input_tokens": list(a), "call_output_tokens": list(b)}


def synthetic(items=40, seed=7):
    rng = random.Random(seed)
    rows = []
    for i in range(items):
        for model, p in (("vendor/a", 0.7), ("vendor/b", 0.5)):
            k = rng.randint(1, 4)
            a = [rng.randint(200, 900)] + [rng.randint(5, 120) for _ in range(k - 1)]
            b = [rng.randint(10, 300) for _ in range(k)]
            rows.append(call_row("t", f"i{i}", model, rng.random() < p, a, b))
    registry = Registry([Model(id="vendor/a", family="vendor", price_in=3.0, price_out=15.0, context_window=1_000_000),
                         Model(id="vendor/b", family="other", price_in=0.4, price_out=1.6, context_window=1_000_000)])
    return rows, registry


def registry_json(registry):
    return {"models": [{"id": m.id, "family": m.family, "price_in": m.price_in, "price_out": m.price_out,
                        "context_window": m.context_window} for m in registry.models]}


def committed_results():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def summary_index(results):
    return {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r for r in results["summary"]}


def mean(values):
    values = list(values)
    return math.fsum(values) / len(values)


def section(text, heading):
    start = text.index(f"\n{heading}\n")
    rest = text[start + len(heading) + 2:]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


# --- plain from the start ----------------------------------------------------------------------

def test_base_points_carry_no_work_calls(dr):
    assert all("work_calls" not in p for p in dr.points())
    assert len(dr.points()) == 4


def test_variant_points_with_work_calls_are_refused_on_per_call_rows(dr):
    rows, registry = synthetic()
    refused = [p for p in dr.variant_points() if p.get("work_calls", 1) > 1]
    assert len(refused) == 2
    for point in refused:
        with pytest.raises(ValueError) as exc:
            evaluate_delegation(rows, registry, bars=[0.5], points=[point], seeds=range(1))
        assert "point 0 sets 'work_calls' above 1 and task 't' has per-call sizes" in str(exc.value)
    cached = [p for p in dr.variant_points() if p.get("work_calls", 1) == 1]
    assert len(cached) == 1
    result = evaluate_delegation(rows, registry, bars=[0.5], points=cached, seeds=range(1))
    assert len(result["cells"]) == 2 * 2


def test_research_note_states_the_registry_prices_windows_and_status():
    text = RESEARCH.read_text(encoding="utf-8")
    assert ("| `openai/gpt-4.1-2025-04-14` | https://platform.openai.com/docs/models/gpt-4.1 | Deprecated "
            "| 2.00, 0.50, 8.00 | 1,047,576 |") in text
    assert ("| `openai/gpt-4.1-mini-2025-04-14` | https://platform.openai.com/docs/models/gpt-4.1-mini "
            "| Deprecated | 0.40, 0.10, 1.60 | 1,047,576 |") in text
    assert "| `openai/o4-mini-2025-04-16` | https://platform.openai.com/docs/models/o4-mini | Shut down |" in text
    assert "retired on the Claude API on February 19, 2026" in text
    assert "not stated on a current page; the recorded costs give 3 and 15 (below) | not found on a current page |" in text
    assert "all 4,371 calls cost exactly 3 USD per 1M prompt tokens plus 15 per 1M completion tokens" in text
    assert "(opened 2026-11-06)" in text
    assert "51.722764 against 22.986508 USD (2.25 times), 16.954327 against 7.217661 (2.35)" in text
    assert "airline | 50 | 16 to 35 | 15 to 34 | 40 (7 of seeds 0 to 9) |" in text


# --- the pinned files, only when already cached ------------------------------------------------

@pytest.fixture(scope="module")
def calls_matrix(cv):
    """Rows and report of the converter's --calls matrix at trial 0, each pinned file read once."""
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("the 12 pinned tau2-bench run files are not in the default cache")
    extracts = []
    for n, (size, sha) in cv.FILES.items():
        cv.verify(folder / n, size, sha)
        extracts.append(cv.extract(cv.read_run(folder / n), trial=0, tokens=True, calls=True))
    return cv.convert(extracts)


def test_pinned_calls_matrix_keeps_the_registry_agents(calls_matrix):
    rows, report = calls_matrix
    assert report["models"] == KEPT == [m["id"] for m in STATED_MODELS]
    assert report["left_out"] == {O4: 2962}
    assert report["kept"] == DOMAINS and report["rows"] == 834 == len(rows)


# --- the script (v1.79) ------------------------------------------------------------------------

def test_constants_and_points_are_the_stated_ones(td, dr):
    assert td.BARS == BARS
    assert td.SEEDS == 50
    assert td.KEYS == KEYS
    assert td.points() == dr.points()


def test_run_is_evaluate_delegation_on_the_stated_config(td, dr):
    rows, registry = synthetic()
    got = td.run(rows, registry)
    want = evaluate_delegation(rows, registry, bars=list(BARS), points=dr.points(), seeds=range(50))
    assert list(got) == list(KEYS)
    assert got == {key: want[key] for key in KEYS}


def test_main_writes_the_run_and_returns_0(td, tmp_path):
    rows, registry = synthetic()
    matrix, reg, out = tmp_path / "m.jsonl", tmp_path / "r.json", tmp_path / "out.json"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    reg.write_text(json.dumps(registry_json(registry)), encoding="utf-8")
    assert td.main(["--matrix", str(matrix), "--registry", str(reg), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == json.dumps(td.run(rows, Registry.load(reg)), indent=2) + "\n"
    assert not (tmp_path / "out.json.part").exists()


def test_main_reports_a_harness_error_and_leaves_out_untouched(td, tmp_path, capsys):
    rows, registry = synthetic()
    rows[3] = dict(rows[3], input_tokens=rows[3]["input_tokens"] + 1)
    matrix, reg, out = tmp_path / "m.jsonl", tmp_path / "r.json", tmp_path / "out.json"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    reg.write_text(json.dumps(registry_json(registry)), encoding="utf-8")
    out.write_text("keep", encoding="utf-8")
    assert td.main(["--matrix", str(matrix), "--registry", str(reg), "--out", str(out)]) == 1
    err = capsys.readouterr().err
    assert err.startswith("error: ") and err.count("\n") == 1
    assert out.read_text(encoding="utf-8") == "keep"
    assert not (tmp_path / "out.json.part").exists()


def test_main_requires_every_option(td, tmp_path):
    with pytest.raises(SystemExit) as exc:
        td.main(["--matrix", str(tmp_path / "m.jsonl"), "--out", str(tmp_path / "o.json")])
    assert exc.value.code == 2


# --- the committed files (v1.79) ---------------------------------------------------------------

def test_committed_registry_is_the_stated_one():
    text = REGISTRY.read_text(encoding="utf-8")
    data = json.loads(text)
    assert text == json.dumps(data, indent=2) + "\n"
    assert list(data) == ["as_of", "note", "models"]
    assert data["as_of"] == "2026-11-06"
    assert "research/delegation-datasets.md" in data["note"]
    assert [list(m) for m in data["models"]] == [REGISTRY_MODEL_KEYS] * 3
    for got, want in zip(data["models"], STATED_MODELS):
        assert {k: got[k] for k in want} == want
        assert isinstance(got["notes"], str) and got["notes"]
    assert "assumed" in data["models"][0]["notes"] and "February 19, 2026" in data["models"][0]["notes"]
    assert all("Deprecated" in m["notes"] for m in data["models"][1:])
    loaded = Registry.load(REGISTRY)
    assert [m.id for m in loaded.models] == KEPT
    assert all(m.price_valid_until is None for m in loaded.models)


def test_committed_results_file_has_the_stated_shape(dr):
    text = RESULTS.read_text(encoding="utf-8")
    results = json.loads(text)
    assert len(text.encode("utf-8")) < 300_000
    assert text == json.dumps(results, indent=2) + "\n"
    assert list(results) == list(KEYS)
    config = results["config"]
    assert config["bars"] == list(BARS) and config["seeds"] == list(range(50))
    assert config["flavors"] == FLAVORS and config["points"] == dr.points()
    assert config["parents"] == KEPT
    assert results["tasks"] == {d: {"items": n, "models": KEPT} for d, n in DOMAINS.items()}
    keys = [(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]) for r in results["summary"]]
    assert len(keys) == len(set(keys)) == 6 * 2 * 4 * 3 * 3


def test_results_md_holds_the_sources_sections_tables_and_regenerate_block(dr):
    text = RESULTS_MD.read_text(encoding="utf-8")
    results = committed_results()
    assert text.splitlines()[0] == "# Delegation on tau2-bench: inline or sub-agent on held-out conversations"
    for needle in ("https://github.com/sierra-research/tau2-bench", REVISION, "MIT", "(registry.json)",
                   "(results.json)", "(../tau2-bench/README.md)", "(../../research/delegation-datasets.md)"):
        assert needle in text
    heads = [line for line in text.splitlines() if line.startswith("## ")]
    assert heads == ["## Method", "## Assumed", "## Results", "## Reading it", "## Regenerate"]
    assert f"```text\n{TABLE_CMD}\n{dr.table(results)}\n```" in section(text, "## Results")
    assert f"```text\n{PARENT_CMD}\n{dr.parent_table(results, 0.3, 0)}\n```" in section(text, "## Results")
    assert "```bash\n" + "\n".join(REGENERATE) + "\n```" in section(text, "## Regenerate")
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text


def test_results_md_reading_it_is_built_from_the_file(dr):
    text = section(RESULTS_MD.read_text(encoding="utf-8"), "## Reading it")
    results = committed_results()
    index = summary_index(results)
    config = results["config"]
    decision = [r for r in results["summary"] if r["flavor"] == "cost_effective" and r["strategy"] == "decision"]
    assert decision and all(r["delegate_rate"] == 1.0 for r in decision)
    assert (f"In `cost_effective` the decision delegates on every seed for every parent at every bar and point "
            f"(`delegate_rate` 1.0 on all {len(decision)} decision rows).") in text
    bar, parents = config["bars"][0], config["parents"]
    row = {s: [index[(bar, "cost_effective", 0, p, s)] for p in parents] for s in STRATEGIES}
    dec_cost, inl_cost = mean(r["cost_usd"] for r in row["decision"]), mean(r["cost_usd"] for r in row["inline"])
    dec_s, inl_s = mean(r["success"] for r in row["decision"]), mean(r["success"] for r in row["inline"])
    assert (f"At bar {bar} and point 0 ({config['points'][0]['context_tokens']:,} context tokens), averaged over the "
            f"{len(parents)} parents, the `cost_effective` decision costs {dec_cost:.4f} USD on a held-out half "
            f"against {inl_cost:.4f} for always inline ({inl_cost / dec_cost:.2f} times as much), with held-out "
            f"success {dec_s:.3f} against {inl_s:.3f}.") in text
    dearer = [f"`{p}` ({d['cost_usd']:.4f} against {i['cost_usd']:.4f})"
              for p, d, i in zip(parents, row["decision"], row["inline"]) if d["cost_usd"] > i["cost_usd"]]
    tail = ", ".join(dearer) if dearer else "no parent"
    assert f"At that bar and point the `cost_effective` decision costs more than always inline for {tail}." in text
    assert f"`results.json` is {len(RESULTS.read_bytes()):,} bytes." in text


def test_results_md_states_the_assumptions():
    text = section(RESULTS_MD.read_text(encoding="utf-8"), "## Assumed")
    for needle in ("lossless", "whole conversation", "tool schemas", "2.25 times", "2.35 times", "1.0 times",
                   "list-price estimate", f"`{O4}`", "2,962", "200,000", "assumed", "trial 0",
                   "Deprecated", "Shut down", "February 19, 2026", "40 of the 50 seeds", "per call"):
        assert needle in text, needle


# --- the pinned files with the committed registry (v1.79), only when cached --------------------

def test_pinned_files_regenerate_results_byte_identical(td, calls_matrix):
    rows, _ = calls_matrix
    text = json.dumps(td.run(rows, Registry.load(REGISTRY)), indent=2) + "\n"
    assert text == RESULTS.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) == 132_475


def test_pinned_files_give_the_stated_work_calls_and_window_checks(dr, calls_matrix):
    rows, _ = calls_matrix
    registry = Registry.load(REGISTRY)
    full = evaluate_delegation(rows, registry, bars=list(BARS), points=dr.points(), seeds=range(50))
    cells = full["cells"]
    assert len(cells) == 21_600
    spans = {"airline": ((10, 12), (604, 718)), "retail": ((11, 12), (643, 675)), "telecom": ((17, 19), (512, 574))}
    for task, (k_span, s_span) in spans.items():
        mine = [c for c in cells if c["task"] == task]
        ks = [c["expected_work_calls"] for c in mine]
        ss = [c["expected_input_tokens"] + c["expected_output_tokens"] for c in mine]
        assert (min(ks), max(ks)) == k_span and (min(ss), max(ss)) == s_span, task
    work = max(c["expected_work_calls"] * (c["expected_input_tokens"] + c["expected_output_tokens"]) for c in cells)
    assert work == 10_242
    points = dr.points()
    rule5 = max(points[c["point"]]["brief_tokens"] + c["expected_work_calls"]
                * (c["expected_input_tokens"] + c["expected_output_tokens"]) for c in cells)
    rule3 = max(points[c["point"]]["context_tokens"] + c["expected_work_calls"]
                * (c["expected_input_tokens"] + c["expected_output_tokens"])
                for c in cells if points[c["point"]]["context_tokens"] == 64_000)
    assert rule5 == 10_742 and rule3 == 74_242
    blocked = [c for c in cells if not c["inline_allowed"]]
    assert all(c["point"] == 2 and c["parent"] == CLAUDE for c in blocked) and len(blocked) == 1_800
    assert all(c["reason"] == "parent_context_full" for c in blocked)
    assert not [c for c in cells if c["reason"] == "parent_context_full" and c["inline_allowed"]]
    rates = {r["delegate_rate"] for r in full["summary"] if r["flavor"] == "cost_effective" and r["strategy"] == "decision"}
    assert rates == {1.0}
    reasons = {f: Counter(c["reason"] for c in cells if c["flavor"] == f) for f in FLAVORS}
    assert reasons["cost_effective"] == {"none_clear": 6941, "delegate_cheaper": 2301,
                                        "parent_context_full": 900, "parent_below_bar": 658}
    assert reasons["cost_blind"] == {"none_clear": 6941, "delegate_better": 1375, "inline_as_good": 926,
                                    "parent_context_full": 900, "parent_below_bar": 658}
    ranked = sorted(reasons["cost_effective"].items(), key=lambda kv: (-kv[1], kv[0]))
    parts = [f"{n:,} `{reason}`" for reason, n in ranked]
    listed = ", ".join(parts[:-1]) + " and " + parts[-1]
    method = section(RESULTS_MD.read_text(encoding="utf-8"), "## Method")
    total = sum(reasons["cost_effective"].values())
    assert f"Of the {total:,} `cost_effective` cells, {listed}." in method
    assert "`none_clear` is 13.5 row 7: no agent clears the bar, so the calibration bounds decide, not cost." in method
