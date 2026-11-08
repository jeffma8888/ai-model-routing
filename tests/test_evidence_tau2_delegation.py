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
v1.82 adds the pooled run, the same script on the three domains as one task, written to
``pooled.json``; its tests came before the file and the RESULTS.md parts and failed until v1.83.
"""

import importlib.util
import json
import re
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
def calls_extracts(cv):
    """The --calls extracts of the 12 pinned files at trial 0, each file verified and read once."""
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("the 12 pinned tau2-bench run files are not in the default cache")
    extracts = []
    for n, (size, sha) in cv.FILES.items():
        cv.verify(folder / n, size, sha)
        extracts.append(cv.extract(cv.read_run(folder / n), trial=0, tokens=True, calls=True))
    return extracts


@pytest.fixture(scope="module")
def calls_matrix(cv, calls_extracts):
    """Rows and report of the converter's --calls matrix at trial 0, one task per domain."""
    return cv.convert(calls_extracts)


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


def reading_it(results):
    """The 13.12 Reading it bullets, built from the committed file, the file size last."""
    index = summary_index(results)
    config = results["config"]
    decision = [r for r in results["summary"] if r["flavor"] == "cost_effective" and r["strategy"] == "decision"]
    assert decision and all(r["delegate_rate"] == 1.0 for r in decision)
    bar, parents = config["bars"][0], config["parents"]
    row = {s: [index[(bar, "cost_effective", 0, p, s)] for p in parents] for s in STRATEGIES}
    dec_cost, inl_cost = mean(r["cost_usd"] for r in row["decision"]), mean(r["cost_usd"] for r in row["inline"])
    dec_s, inl_s = mean(r["success"] for r in row["decision"]), mean(r["success"] for r in row["inline"])
    dearer = [f"`{p}` ({d['cost_usd']:.4f} against {i['cost_usd']:.4f})"
              for p, d, i in zip(parents, row["decision"], row["inline"]) if d["cost_usd"] > i["cost_usd"]]
    tail = ", ".join(dearer) if dearer else "no parent"
    return [
        f"In `cost_effective` the decision delegates on every seed for every parent at every bar and point "
        f"(`delegate_rate` 1.0 on all {len(decision)} decision rows).",
        f"At bar {bar} and point 0 ({config['points'][0]['context_tokens']:,} context tokens), averaged over the "
        f"{len(parents)} parents, the `cost_effective` decision costs {dec_cost:.4f} USD on a held-out half "
        f"against {inl_cost:.4f} for always inline ({inl_cost / dec_cost:.2f} times as much), with held-out "
        f"success {dec_s:.3f} against {inl_s:.3f}.",
        f"At that bar and point the `cost_effective` decision costs more than always inline for {tail}.",
        f"`results.json` is {len(RESULTS.read_bytes()):,} bytes.",
    ]


def test_results_md_reading_it_is_built_from_the_file(dr):
    text = section(RESULTS_MD.read_text(encoding="utf-8"), "## Reading it")
    for sentence in reading_it(committed_results()):
        assert sentence in text, sentence


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


# --- the README subsection (DESIGN 12.8 v1.80) -------------------------------------------------

README = ROOT / "README.md"
EVIDENCE_HEADINGS = ["RouterBench", "AutoBench", "AutoBench judges", "tau2-bench", "LiveCodeBench",
                     "Delegation on AutoBench", "Delegation on tau2-bench"]
README_LINKS = (
    "[tau2-bench](https://github.com/sierra-research/tau2-bench)",
    f"[{REVISION[:7]}](https://github.com/sierra-research/tau2-bench/tree/{REVISION})",
    '(licence MIT, "Copyright (c) 2025 Sierra Research")',
    "[RESULTS.md](evidence/tau2-bench-delegation/RESULTS.md)",
    "[results.json](evidence/tau2-bench-delegation/results.json)",
    "[registry.json](evidence/tau2-bench-delegation/registry.json)",
    "](evidence/tau2-bench/README.md)",
    "](research/delegation-datasets.md)",
    "[inline or sub-agent](#inline-or-sub-agent)",
    "8,000, 64,000 and 200,000",
    "list-price estimate",
)
# Each is the start of one RESULTS.md bullet that the README repeats verbatim (12.8 v1.80):
# three from Method, the rest from Assumed.
RESULTS_MD_LINES = (
    "Of the ",
    "Airline has 50 conversations",
    "At point 2, C = 200,000",
    "The lossless brief",
    "List price over-states",
    "Each conversation is read at trial 0 only",
    "The agents are 2025 snapshots",
    "The limits of `DESIGN.md` 13.8",
)


def words(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def counts_sentence(results):
    config, tasks = results["config"], results["tasks"]
    domains = words([f"{name} {task['items']}" for name, task in tasks.items()])
    agents = words([f"`{p}`" for p in config["parents"]])
    return (f"Each item is one agent conversation at trial 0, one task per domain ({domains} "
            f"conversations), with each of the {len(config['parents'])} agents ({agents}) as the "
            f"parent, over {len(config['seeds'])} seeds.")


def readme_subsection():
    text = README.read_text(encoding="utf-8")
    heading = "\n## Evidence: held-out results on public data\n"
    assert text.count(heading) == 1
    evidence = text.split(heading, 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.*)$", evidence, re.M) == EVIDENCE_HEADINGS
    return evidence.split("\n### Delegation on tau2-bench\n", 1)[1].split("\n### ", 1)[0]


def test_readme_subsection_links_the_sources_and_licence():
    sub = readme_subsection()
    for needle in README_LINKS:
        assert needle in sub, needle
    assert sub.isascii() and "\u2013" not in sub and "\u2014" not in sub


def test_readme_subsection_shows_the_counts_tables_and_reading_it(dr):
    sub = readme_subsection()
    results = committed_results()
    assert counts_sentence(results) in sub
    assert f"```text\n{TABLE_CMD}\n{dr.table(results)}\n```" in sub
    assert f"```text\n{PARENT_CMD}\n{dr.parent_table(results, results['config']['bars'][0], 0)}\n```" in sub
    for sentence in reading_it(results)[:3]:
        assert f"- {sentence}\n" in sub, sentence
    assert "`results.json` is " not in sub


def test_readme_subsection_repeats_the_results_md_lines():
    sub = readme_subsection()
    lines = RESULTS_MD.read_text(encoding="utf-8").splitlines()
    for start in RESULTS_MD_LINES:
        found = [line for line in lines if line.startswith(f"- {start}")]
        assert len(found) == 1, start
        assert f"\n{found[0]}\n" in sub, start


def test_readme_subsection_regenerate_block_is_the_results_md_one():
    sub = readme_subsection()
    assert re.findall(r"```bash\n.*?```\n", sub, re.S) == ["```bash\n" + "\n".join(REGENERATE) + "\n```\n"]


def test_readme_layout_names_the_results_md():
    text = README.read_text(encoding="utf-8")
    layout = text.split("\n## Layout\n", 1)[1].split("\n## ", 1)[0]
    assert "(delegation on tau2-bench: evidence/tau2-bench-delegation/RESULTS.md)" in layout


# --- the pooled run (DESIGN 13.12 v1.82) -------------------------------------------------------

POOLED = FOLDER / "pooled.json"
POOLED_CMD = "$ python evidence/delegation/results.py --table evidence/tau2-bench-delegation/pooled.json"
REGENERATE_POOLED = [
    "python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all",
    "python evidence/tau2-bench-delegation/results.py --matrix tau2-calls-all.jsonl --registry "
    "evidence/tau2-bench-delegation/registry.json --out evidence/tau2-bench-delegation/pooled.json",
    POOLED_CMD[2:],
]
RUNS = ("per domain", "pooled")
# The 13.5 row 3 reasons; in cost_effective the last two come only from its exact cost tie.
COST_COMPARED = ("delegate_cheaper", "inline_cheaper", "delegate_better", "inline_as_good")


def committed_pooled():
    return json.loads(POOLED.read_text(encoding="utf-8"))


def test_committed_pooled_file_has_the_stated_shape():
    text = POOLED.read_text(encoding="utf-8")
    pooled = json.loads(text)
    assert len(text.encode("utf-8")) < 300_000
    assert text == json.dumps(pooled, indent=2) + "\n"
    assert list(pooled) == list(KEYS)
    assert pooled["config"] == committed_results()["config"]
    assert pooled["tasks"] == {"all": {"items": sum(DOMAINS.values()), "models": KEPT}}
    assert pooled["tasks"]["all"]["items"] == 278
    keys = [(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]) for r in pooled["summary"]]
    assert len(keys) == len(set(keys)) == 6 * 2 * 4 * 3 * 3


def test_pooled_inline_rows_have_the_per_domain_success_and_cost():
    per_domain, pooled = summary_index(committed_results()), summary_index(committed_pooled())
    assert set(per_domain) == set(pooled)
    inline = [key for key in per_domain if key[4] == "inline"]
    assert len(inline) == 6 * 2 * 4 * 3
    for key in inline:
        assert pooled[key]["success"] == per_domain[key]["success"], key
        assert pooled[key]["cost_usd"] == per_domain[key]["cost_usd"], key


def test_results_md_shows_the_pooled_method_table_and_regenerate_block(dr):
    text = RESULTS_MD.read_text(encoding="utf-8")
    method = [line for line in section(text, "## Method").splitlines()
              if line.startswith("- A second run pools the three domains")]
    assert len(method) == 1
    for needle in ("`--task-by all`", "278 conversations", "(pooled.json)",
                   "a sensitivity of this reading, not its main result"):
        assert needle in method[0], needle
    results = section(text, "## Results")
    block = f"```text\n{POOLED_CMD}\n{dr.table(committed_pooled())}\n```"
    assert block in results
    assert results.index(block) > results.index(PARENT_CMD)
    regenerate = section(text, "## Regenerate")
    blocks = re.findall(r"```bash\n(.*?)```", regenerate, re.S)
    assert blocks == ["\n".join(REGENERATE) + "\n", "\n".join(REGENERATE_POOLED) + "\n"]
    assert "```\n\nThe pooled run:\n\n```bash\n" in regenerate
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text


def pooled_reading(results, pooled):
    """The 13.12 v1.82 Reading it bullets built from the two committed files."""
    decision = [r for r in pooled["summary"] if r["flavor"] == "cost_effective" and r["strategy"] == "decision"]
    assert decision and all(r["delegate_rate"] == 1.0 for r in decision)
    config = pooled["config"]
    bar, parents = config["bars"][0], config["parents"]

    def means(res):
        index = summary_index(res)
        rows = [index[(bar, "cost_effective", 0, p, "decision")] for p in parents]
        return mean(r["cost_usd"] for r in rows), mean(r["success"] for r in rows)

    (p_cost, p_success), (d_cost, d_success) = means(pooled), means(results)
    return [
        f"Pooled, the `cost_effective` decision again delegates on every seed for every parent at every bar and "
        f"point; at bar {bar} and point 0, averaged over the {len(parents)} parents, it costs {p_cost:.4f} USD on a "
        f"held-out half against {d_cost:.4f} per domain, with held-out success {p_success:.3f} against "
        f"{d_success:.3f}. Always inline has the same held-out success and cost in both runs, since the split "
        f"reads only the seed and the item ID (`DESIGN.md` 12.2).",
        f"`pooled.json` is {len(POOLED.read_bytes()):,} bytes.",
    ]


def test_results_md_reading_it_states_the_pooled_run():
    text = section(RESULTS_MD.read_text(encoding="utf-8"), "## Reading it")
    for sentence in pooled_reading(committed_results(), committed_pooled()):
        assert f"- {sentence}\n" in text, sentence


def reason_table(runs):
    """The v1.82 Markdown table of each run's cost_effective reason counts per bar, then over all bars."""
    totals = Counter(c["reason"] for label in RUNS for c in runs[label])
    reasons = sorted(totals, key=lambda reason: (-totals[reason], reason))
    lines = ["| bar | run | cells | " + " | ".join(f"`{r}`" for r in reasons) + " |",
             "| --- | --- | ---: | " + " | ".join("---:" for _ in reasons) + " |"]
    for bar in [*BARS, "all"]:
        for label in RUNS:
            counts = Counter(c["reason"] for c in runs[label] if bar == "all" or c["bar"] == bar)
            lines.append(f"| {bar} | {label} | {sum(counts.values()):,} | "
                         + " | ".join(f"{counts[r]:,}" for r in reasons) + " |")
    return "\n".join(lines)


def cost_comparison_sentence(runs):
    """The v1.82 Reading it bullet on the cells that reach the 13.5 row 3 cost comparison."""
    assert not [c for label in RUNS for c in runs[label] if c["reason"] == "inline_cheaper"]
    (a, n), (b, m) = [(sum(c["reason"] in COST_COMPARED for c in runs[label]), len(runs[label])) for label in RUNS]
    return (f"The cost comparison (`DESIGN.md` 13.5 row 3: both paths clear the bar, so their costs are compared) "
            f"is reached on {a:,} of the {n:,} `cost_effective` cells per domain ({a / n:.1%}) and on {b:,} of the "
            f"{m:,} pooled ({b / m:.1%}); no cell of either run is `inline_cheaper`.")


@pytest.fixture(scope="module")
def pooled_matrix(cv, calls_extracts):
    """Rows and report of the converter's --calls matrix at trial 0, the domains as one task."""
    return cv.convert(calls_extracts, "all")


@pytest.fixture(scope="module")
def run_cells(dr, calls_matrix, pooled_matrix):
    """The cells of both runs with the committed registry, from in-process runs that keep them."""
    registry = Registry.load(REGISTRY)
    return {label: evaluate_delegation(matrix[0], registry, bars=list(BARS), points=dr.points(),
                                       seeds=range(50))["cells"]
            for label, matrix in zip(RUNS, (calls_matrix, pooled_matrix))}


def test_pinned_pooled_matrix_is_the_per_domain_rows_as_one_task(calls_matrix, pooled_matrix):
    rows, report = pooled_matrix
    assert report["task_by"] == "all" and report["kept"] == {"all": 278}
    assert report["models"] == KEPT and report["left_out"] == {O4: 2962} and report["rows"] == 834 == len(rows)
    assert {r["task"] for r in rows} == {"all"}

    def without_task(matrix_rows):
        return sorted(json.dumps({k: v for k, v in r.items() if k != "task"}, sort_keys=True) for r in matrix_rows)

    assert without_task(rows) == without_task(calls_matrix[0])


def test_pinned_files_regenerate_pooled_byte_identical(td, pooled_matrix):
    rows, _ = pooled_matrix
    text = json.dumps(td.run(rows, Registry.load(REGISTRY)), indent=2) + "\n"
    assert text == POOLED.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) == 126_695


def test_pinned_files_give_the_stated_pooled_numbers(dr, run_cells):
    cells = run_cells["pooled"]
    assert len(cells) == 7_200 and {c["task"] for c in cells} == {"all"}
    ks = [c["expected_work_calls"] for c in cells]
    ss = [c["expected_input_tokens"] + c["expected_output_tokens"] for c in cells]
    assert (min(ks), max(ks)) == (13, 15) and (min(ss), max(ss)) == (603, 636)
    points = dr.points()
    work = max(c["expected_work_calls"] * (c["expected_input_tokens"] + c["expected_output_tokens"]) for c in cells)
    rule5 = max(points[c["point"]]["brief_tokens"] + c["expected_work_calls"]
                * (c["expected_input_tokens"] + c["expected_output_tokens"]) for c in cells)
    rule3 = max(points[c["point"]]["context_tokens"] + c["expected_work_calls"]
                * (c["expected_input_tokens"] + c["expected_output_tokens"])
                for c in cells if points[c["point"]]["context_tokens"] == 64_000)
    assert (work, rule5, rule3) == (9_240, 9_740, 73_240)
    blocked = [c for c in cells if not c["inline_allowed"]]
    assert len(blocked) == 600 and all(c["point"] == 2 and c["parent"] == CLAUDE for c in blocked)
    assert {c["reason"] for c in blocked} == {"parent_context_full"}
    halves = [c["calibration_items"] for c in cells]
    assert (min(halves), max(halves)) == (114, 158)
    reasons = {f: Counter(c["reason"] for c in cells if c["flavor"] == f) for f in FLAVORS}
    assert reasons["cost_effective"] == {"none_clear": 1826, "delegate_cheaper": 1232,
                                        "parent_context_full": 300, "parent_below_bar": 242}
    assert reasons["cost_blind"] == {"none_clear": 1826, "delegate_better": 787, "inline_as_good": 445,
                                    "parent_context_full": 300, "parent_below_bar": 242}
    compared = {label: [sum(c["reason"] in COST_COMPARED for c in run_cells[label]
                            if c["flavor"] == "cost_effective" and c["bar"] == bar) for bar in BARS]
                for label in RUNS}
    assert compared == {"per domain": [892, 584, 514, 271, 40, 0], "pooled": [550, 550, 132, 0, 0, 0]}
    allowed = [sum(c["inline_allowed"] for c in cells if c["flavor"] == "cost_effective" and c["bar"] == bar)
               for bar in BARS]
    assert allowed == [550] * 6
    method = section(RESULTS_MD.read_text(encoding="utf-8"), "## Method")
    assert f"{min(halves)} to {max(halves)} conversations" in method


def test_results_md_reason_table_and_cost_comparison_are_built_from_the_runs(run_cells):
    text = RESULTS_MD.read_text(encoding="utf-8")
    runs = {label: [c for c in run_cells[label] if c["flavor"] == "cost_effective"] for label in RUNS}
    assert [len(runs[label]) for label in RUNS] == [10_800, 3_600]
    assert f"\n{reason_table(runs)}\n" in section(text, "## Results")
    assert f"- {cost_comparison_sentence(runs)}\n" in section(text, "## Reading it")
