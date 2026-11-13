"""Delegation results on the LLM Routing Response Bank (DESIGN 13.14; specified in v1.310, row E21b).

The 13.9 harness on the response-bank converter's default rows (12.20), all five models as the
pool, with the 4 `mmlu_pro` items that hold the six `missing` cells dropped by 13.13's
``select_rows``, a committed registry that prices each model at the pair its bills give on its
responses with no cache read, the 13.10 base points and the 12.21 bars. v1.310 holds every test
that loads ``evidence/response-bank-delegation/results.py`` or reads one of its committed files
(``registry.json``, ``results.json``) under a strict xfail marker naming ``FileNotFoundError``;
row E21c commits them and removes the markers. The other tests pass before and after: the
research note states each price, cache-read price, window and source the registry takes from it,
and, when the four pinned files are cached, 13.13's ``select_rows`` on the converter's rows gives
the dropped items, kept counts, success span and list-cost-to-bill ratios that 13.14 states.

v1.311 (review iter-207 must-fix 1 and should-fix 1) adds four strict-xfail cases of the v1.269 check of
an ``--out`` that names an input, adapted from 13.13's, and more ``notes`` phrases in the registry test.

v1.312 (row E21c) commits the script, ``registry.json`` and ``results.json`` and removes the markers.

v1.313 (row E21e) adds the tests of ``RESULTS.md``, 13.13's five adapted to the sentences 13.14 states and a
cached-file one on its Method sentences, each under a strict xfail marker naming ``FileNotFoundError``
until the file lands. They import 13.13's ``dearer_than_inline``, ``section``, ``fenced`` and ``join``,
and the cached-file tests share one module-scoped run of the pinned rows.

v1.314 (row E21e) commits ``RESULTS.md`` and removes the markers.
"""

import importlib.util
import json
import math
import re
from collections import Counter, defaultdict
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation
from test_evidence_llmrouterbench_delegation import dearer_than_inline, fenced, join, section

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "response-bank-delegation"
SCRIPT = FOLDER / "results.py"
REGISTRY = FOLDER / "registry.json"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
DELEGATION_SCRIPT = ROOT / "evidence" / "delegation" / "results.py"
LRB_SCRIPT = ROOT / "evidence" / "llmrouterbench-delegation" / "results.py"
RESEARCH = ROOT / "research" / "delegation-datasets.md"

REVISION = "547beb31ecd8f12b116b87eb4f56feee73edda6c"
DATASET_TREE = f"https://huggingface.co/datasets/Lurume/llm-routing-response-bank/tree/{REVISION}"
DEEPSEEK_PAGE = "https://api-docs.deepseek.com/quick_start/pricing"
KIMI_PAGE = "https://platform.moonshot.ai/docs/pricing/chat"
KIMI_NOW = "https://platform.kimi.ai/docs/pricing/chat"
ZAI_PAGE = "https://docs.z.ai/guides/overview/pricing"
FLASH = "deepseek/deepseek-v4-flash"
PRO = "deepseek/deepseek-v4-pro"
KIMI = "moonshotai/kimi-k2.7-code"
GLM = "z-ai/glm-5.3"
GLM_FLASH = "z-ai/glm-5.3-flash"
POOL = (FLASH, PRO, KIMI, GLM, GLM_FLASH)
PAGE_PRICED = (KIMI, GLM, GLM_FLASH)
CACHE_PRICE = {FLASH: 0.0028, PRO: 0.003625, KIMI: 0.19, GLM: 0.26, GLM_FLASH: 0.03}
BARS = (0.8, 0.9)
SEEDS = 50
KEYS = ("config", "tasks", "summary")
FLAVORS = ["cost_effective", "cost_blind"]
DROPPED = ["mmlu_pro:10969", "mmlu_pro:10990", "mmlu_pro:11007", "mmlu_pro:7872"]
KEPT_ITEMS = {"aime": 30, "gpqa_diamond": 198, "livecodebench": 1055, "mmlu_pro": 12028}
LIST_TO_BILL = {FLASH: 0.9999, PRO: 0.9995, KIMI: 0.9901, GLM: 0.9855, GLM_FLASH: 0.9824}
REGISTRY_MODEL_KEYS = ["id", "family", "price_in", "price_out", "context_window", "source", "notes"]
STATED_MODELS = [
    {"id": FLASH, "family": "deepseek", "price_in": 0.14, "price_out": 0.28, "context_window": 1_000_000,
     "source": DATASET_TREE},
    {"id": PRO, "family": "deepseek", "price_in": 0.435, "price_out": 0.87, "context_window": 1_000_000,
     "source": DATASET_TREE},
    {"id": KIMI, "family": "moonshotai", "price_in": 0.95, "price_out": 4, "context_window": 262_144,
     "source": KIMI_PAGE},
    {"id": GLM, "family": "z-ai", "price_in": 1.4, "price_out": 4.4, "context_window": 1_000_000,
     "source": ZAI_PAGE},
    {"id": GLM_FLASH, "family": "z-ai", "price_in": 0.15, "price_out": 0.5, "context_window": 1_000_000,
     "source": ZAI_PAGE},
]
WINDOW_PAGE = {FLASH: DEEPSEEK_PAGE, PRO: DEEPSEEK_PAGE, KIMI: KIMI_NOW,
               GLM: "https://docs.z.ai/guides/llm/glm-5.3", GLM_FLASH: "https://docs.z.ai/guides/llm/glm-5.3-flash"}
CELLS = 16_000
REASONS = {
    "cost_effective": {"none_clear": 5040, "delegate_cheaper": 2062, "parent_below_bar": 848, "inline_cheaper": 50},
    "cost_blind": {"none_clear": 5040, "delegate_better": 1492, "parent_below_bar": 848, "inline_as_good": 620},
}
POINT0 = {0.8: (20.7429, 101.6277, 0.847, 0.861), 0.9: (75.1256, 101.6277, 0.874, 0.861)}
TABLE_CMD = "$ python evidence/delegation/results.py --table evidence/response-bank-delegation/results.json"
PARENT_CMD = TABLE_CMD + " --bar 0.8 --point 0"
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/response-bank/convert.py --out response-bank-matrix.jsonl",
    "python evidence/response-bank-delegation/results.py --matrix response-bank-matrix.jsonl --registry "
    "evidence/response-bank-delegation/registry.json --out evidence/response-bank-delegation/results.json",
    TABLE_CMD[2:],
    PARENT_CMD[2:],
]
POOL_SENTENCE = ("The pool is all five models of [the response-bank routing results](../response-bank/RESULTS.md), "
                 "each priced at the input and output pair its bills give on its responses with no cache read, so "
                 "no model of those results is left out.")
NONE_CLEAR = "`none_clear` is 13.5 row 7: no model clears the bar, so the calibration bounds decide, not cost."
ASSUMED_PHRASES = ("lossless", "list price", "never a bill", "0.9999", "0.9995", "0.9901", "0.9855", "0.9824",
                   "0.0028", "0.003625", "0.19", "0.26", "0.03", "1e-09", "which the registry does not hold",
                   "other prices", "usage.input", "25,478", "60,154", "980", "1,281", "10, 3, 1 and 16",
                   "10, 3, 1 and 14", "1M", "1,000,000", "262,144", "The 4 dropped items", "retired",
                   "DeepSeek-V4.1-Flash-1017", "new users", "October 31, 2026", "end of December 2026",
                   "a reader may no longer be able to call", "13.8")

def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def ld():
    return _load("response_bank_delegation_results", SCRIPT)


@pytest.fixture(scope="module")
def dr():
    return _load("delegation_results_for_response_bank", DELEGATION_SCRIPT)


@pytest.fixture(scope="module")
def lrb():
    return _load("llmrouterbench_delegation_for_response_bank", LRB_SCRIPT)


@pytest.fixture(scope="module")
def pinned_rows(response_bank_pinned):
    code, _, err, path = response_bank_pinned
    assert code == 0, err
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


@pytest.fixture(scope="module")
def pinned_full(pinned_rows):
    """The 13.14 run on the pinned rows, once per module: (kept rows, dropped items, full run with its cells).

    The script is loaded here, not through the function-scoped ``ld``, so the run is shared; a test must
    not modify it."""
    script = _load("response_bank_delegation_results_pinned", SCRIPT)
    kept, dropped = script.select_rows(pinned_rows, list(POOL))
    registry = Registry.load(REGISTRY)
    full = evaluate_delegation(kept, registry, bars=list(script.BARS), points=script.points(),
                               seeds=range(script.SEEDS))
    return kept, dropped, full


def g(x):
    return format(x, "g")


def mean(values):
    values = list(values)
    return math.fsum(values) / len(values)


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
    return text[text.index("## LLM Routing Response Bank (2026-11-12)"):]


def row(task, item, model, correct, i, o):
    return {"task": task, "item": item, "model": model, "correct": correct, "cost_usd": 0.001,
            "input_tokens": i, "output_tokens": o}


def synthetic(items=40):
    rows = []
    for n in range(items):
        for model, every in (("vendor/a", 3), ("vendor/b", 2)):
            rows.append(row("t", f"t:{n}", model, n % every != 0, 300 + 7 * n, 40 + n))
    registry = Registry([Model(id="vendor/a", family="vendor", price_in=3.0, price_out=15.0, context_window=1_000_000),
                         Model(id="vendor/b", family="vendor", price_in=0.4, price_out=1.6, context_window=1_000_000)])
    return rows, registry


def registry_json(registry):
    return {"models": [{"id": m.id, "family": m.family, "price_in": m.price_in, "price_out": m.price_out,
                        "context_window": m.context_window, "source": "fake"} for m in registry.models]}


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows) + "\n", encoding="utf-8")


def stated_registry():
    return Registry([Model(id=s["id"], family=s["family"], price_in=float(s["price_in"]),
                           price_out=float(s["price_out"]), context_window=s["context_window"])
                     for s in STATED_MODELS])


# ---- plain tests: pass before and after row E21c ----

def test_research_note_states_each_registry_value():
    text = note_section()
    prices = {r[0].strip("`"): r for r in table_rows(text, "### List prices")}
    windows = {r[0].strip("`"): r for r in table_rows(text, "### Context windows (2026-11-12)")}
    assert sorted(prices) == sorted(windows) == sorted(POOL)
    cache = ", ".join(g(CACHE_PRICE[m]) for m in POOL[:-1]) + " and " + g(CACHE_PRICE[POOL[-1]])
    assert f"({cache}, in the same order)" in text
    for stated in STATED_MODELS:
        mid = stated["id"]
        assert f"`{mid}` ({g(stated['price_in'])} and {g(stated['price_out'])}" in text, mid
        if mid in PAGE_PRICED:
            assert prices[mid][1] == stated["source"], mid
            assert prices[mid][3] == f"{g(stated['price_in'])}, {g(CACHE_PRICE[mid])}, {g(stated['price_out'])}", mid
        else:
            assert prices[mid][1] == DEEPSEEK_PAGE, mid
        assert windows[mid][3] == f"{stated['context_window']:,}", mid
        assert windows[mid][4].startswith("vendor page"), mid
        assert WINDOW_PAGE[mid] in windows[mid][1], mid
    assert prices[FLASH][3].startswith("none for this model; `deepseek-flash` 0.15, 0.003, 0.6 off-peak and 0.3, 0.006, 1.2 at peak")
    assert prices[PRO][3] == "0.66, 0.022, 1.98 off-peak and 1.32, 0.044, 3.96 at peak, neither the recorded 0.435, 0.003625, 0.87"
    assert "Each 1M is read here as 1,000,000" in text


def test_pinned_rows_drop_the_missing_items_and_keep_the_span(pinned_rows, lrb):
    kept, dropped = lrb.select_rows(pinned_rows, POOL)
    assert dropped == DROPPED
    assert len(pinned_rows) - len(kept) == 20 and len(kept) == 66_555
    items = defaultdict(set)
    for r in kept:
        items[r["task"]].add(r["item"])
    assert {t: len(v) for t, v in sorted(items.items())} == KEPT_ITEMS
    assert sum(KEPT_ITEMS.values()) == 13_311
    tally = defaultdict(lambda: [0, 0])
    for r in kept:
        t = tally[r["task"], r["model"]]
        t[0] += bool(r["correct"])
        t[1] += 1
    rates = sorted((a / n, a, n, key) for key, (a, n) in tally.items())
    assert rates[0][1:] == (23, 30, ("aime", GLM))
    assert rates[-1][1:] == (29, 30, ("aime", PRO))
    assert round(rates[0][0], 4) == 0.7667 and round(rates[-1][0], 4) == 0.9667
    assert tuple(k / 10 for k in range(1, 10) if rates[0][0] < k / 10 < rates[-1][0]) == BARS


def test_pinned_list_cost_is_just_under_the_bill(pinned_rows, lrb):
    kept, _ = lrb.select_rows(pinned_rows, POOL)
    registry = stated_registry()
    listed, billed = defaultdict(list), defaultdict(list)
    for r in kept:
        listed[r["model"]].append(registry.get(r["model"]).base_cost(r["input_tokens"], r["output_tokens"]))
        billed[r["model"]].append(r["cost_usd"])
    ratios = {m: round(math.fsum(listed[m]) / math.fsum(billed[m]), 4) for m in POOL}
    assert ratios == LIST_TO_BILL
    for stated in STATED_MODELS:
        assert CACHE_PRICE[stated["id"]] < stated["price_in"] / 2, stated["id"]


# ---- the script and its files (row E21c) ----

def test_constants(ld):
    assert ld.POOL == POOL
    assert ld.BARS == BARS
    assert ld.SEEDS == SEEDS
    assert ld.KEYS == KEYS


def test_points_are_the_13_10_base_points(ld, dr):
    assert ld.points() == dr.points()


def test_select_rows_is_the_13_13_function(ld, lrb):
    assert Path(ld.select_rows.__code__.co_filename).resolve() == LRB_SCRIPT.resolve()
    rows = [row("t", "t:1", "vendor/a", True, 10, 5), row("t", "t:1", "vendor/b", False, None, None),
            row("t", "t:2", "vendor/b", False, 14, 8), row("t", "t:2", "vendor/a", True, 15, 9)]
    assert ld.select_rows(rows, ["vendor/a", "vendor/b"]) == lrb.select_rows(rows, ["vendor/a", "vendor/b"])
    assert ld.select_rows(rows, ["vendor/a", "vendor/b"]) == ([rows[2], rows[3]], ["t:1"])


def test_run_is_evaluate_delegation_keeping_keys(ld):
    rows, registry = synthetic()
    result = ld.run(rows, registry)
    full = evaluate_delegation(rows, registry, bars=list(BARS), points=ld.points(), seeds=range(SEEDS))
    assert list(result) == list(KEYS)
    assert result == {key: full[key] for key in KEYS}


def test_cli_writes_the_run_on_the_rows_left(ld, tmp_path):
    rows, registry = synthetic()
    rows.append(row("t", "t:0", "vendor/a", False, None, None))
    rows = [r for r in rows if not (r["item"] == "t:0" and r["model"] == "vendor/a" and r["input_tokens"] is not None)]
    matrix = tmp_path / "m.jsonl"
    write_jsonl(matrix, rows)
    reg = tmp_path / "registry.json"
    reg.write_text(json.dumps(registry_json(registry)), encoding="utf-8")
    out = tmp_path / "results.json"
    assert ld.main(["--matrix", str(matrix), "--registry", str(reg), "--out", str(out)]) == 0
    kept, dropped = ld.select_rows(rows, ["vendor/a", "vendor/b"])
    assert dropped == ["t:0"]
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
    for out in (tmp_path.anchor, "."):
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
    assert content["as_of"] == "2026-11-12"
    assert "research/delegation-datasets.md" in content["note"]
    models = content["models"]
    assert [m["id"] for m in models] == list(POOL)
    for got, stated in zip(models, STATED_MODELS):
        assert list(got) == REGISTRY_MODEL_KEYS
        assert {k: got[k] for k in REGISTRY_MODEL_KEYS[:-1]} == stated
        assert got["family"] == got["id"].split("/")[0]
        notes = got["notes"]
        for phrase in (g(CACHE_PRICE[got["id"]]), "not in the registry", WINDOW_PAGE[got["id"]],
                       f"{stated['context_window']:,}"):
            assert phrase in notes, (got["id"], phrase)
        if got["id"] != KIMI:
            assert "1M" in notes and "1,000,000" in notes, got["id"]
        if got["id"] in (FLASH, PRO):
            for phrase in ("responses with cache_read 0", DEEPSEEK_PAGE, "opened 2026-11-12", "off-peak", "at peak",
                           "max_position_embeddings", "1048576"):
                assert phrase in notes, (got["id"], phrase)
        if got["id"] in PAGE_PRICED:
            assert "states this pair" in notes, got["id"]
    by_id = {m["id"]: m["notes"] for m in models}
    for phrase in ("retired", "DeepSeek-V4.1-Flash-1017", "deepseek-flash", "0.15 and 0.6", "0.3 and 1.2"):
        assert phrase in by_id[FLASH], phrase
    for phrase in ("0.66 and 1.98", "1.32 and 3.96"):
        assert phrase in by_id[PRO], phrase
    for phrase in ("redirects", "new users", "October 31, 2026", "retire", "end of December 2026"):
        assert phrase in by_id[KIMI], phrase
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
    keys = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]) for r in results["summary"]}
    assert len(keys) == len(results["summary"]) == len(BARS) * 2 * 4 * len(POOL) * 3 == 240


def test_pinned_run_rebuilds_the_committed_file_and_the_prototype_numbers(ld, pinned_full):
    kept, dropped, full = pinned_full
    assert dropped == DROPPED
    registry = Registry.load(REGISTRY)
    built = {key: full[key] for key in KEYS}
    assert json.dumps(built, indent=2) + "\n" == RESULTS.read_text(encoding="utf-8")
    assert built == ld.run(kept, registry)
    cells = full["cells"]
    assert len(cells) == CELLS
    assert all(c["inline_allowed"] for c in cells)
    for flavor, want in REASONS.items():
        assert Counter(c["reason"] for c in cells if c["flavor"] == flavor) == Counter(want), flavor
    index = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r for r in built["summary"]}
    for bar, (dec_cost, inl_cost, dec_success, inl_success) in POINT0.items():
        dec = [index[bar, "cost_effective", 0, p, "decision"] for p in POOL]
        inl = [index[bar, "cost_effective", 0, p, "inline"] for p in POOL]
        assert round(mean(r["cost_usd"] for r in dec), 4) == dec_cost, bar
        assert round(mean(r["cost_usd"] for r in inl), 4) == inl_cost, bar
        assert round(mean(r["success"] for r in dec), 3) == dec_success, bar
        assert round(mean(r["success"] for r in inl), 3) == inl_success, bar


# ---- v1.311 an --out that names an input (review iter-207 must-fix 1; 13.13 v1.269) ----

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


# ---- v1.313 RESULTS.md (row E21e): committed red as strict xfail; v1.314 lands the file ----

def summary_index(results):
    return {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r for r in results["summary"]}


def reading_bullets(results):
    """13.13's five Reading it bullets, in its order, built from a results file."""
    index = summary_index(results)
    parents, bars, points = results["config"]["parents"], results["config"]["bars"], results["config"]["points"]
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
    return [first, second, third, dearer_than_inline(results), f"`results.json` is {len(RESULTS.read_bytes()):,} bytes."]


def test_reading_bullets_on_the_committed_numbers():
    """Plain: the builder gives the numbers 13.14 v1.313 states for the committed file."""
    bullets = reading_bullets(json.loads(RESULTS.read_text(encoding="utf-8")))
    assert "all 30 of their decision rows" in bullets[0] and "0.950 and 0.954 at bars 0.8 and 0.9." in bullets[0]
    assert bullets[1] == ("At bar 0.8 and point 0 (8,000 context tokens), averaged over the 5 parents, the "
                          "`cost_effective` decision costs 20.7429 USD on a held-out half against 101.6277 for always "
                          "inline (4.90 times as much), with held-out success 0.847 against 0.861.")
    assert bullets[2] == ("At bar 0.9 and point 0 it costs 75.1256 USD against 101.6277 for always inline, with "
                          "held-out success 0.874 against 0.861.")
    assert bullets[3] == "At bar 0.8 and point 0 the `cost_effective` decision costs more than always inline for no parent."
    assert bullets[4] == "`results.json` is 69,970 bytes."


def test_results_md_structure():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert text.split("\n")[0] == ("# Delegation on the LLM Routing Response Bank: inline or sub-agent on held-out "
                                   "single calls")
    text.encode("ascii")
    assert "\u2013" not in text and "\u2014" not in text
    for needle in ("https://huggingface.co/datasets/Lurume/llm-routing-response-bank", REVISION, "2026-09-17",
                   "ODC-BY-4.0", "planned", "To be added.", "(registry.json)", "(results.json)",
                   "(../response-bank/README.md)", "(../response-bank/RESULTS.md)",
                   "(../../research/delegation-datasets.md)"):
        assert needle in text, needle
    headings = [line for line in text.split("\n") if line.startswith("## ")]
    assert headings == ["## Method", "## Assumed", "## Results", "## Reading it", "## Regenerate"]
    method = section(text, "## Method")
    assert POOL_SENTENCE in method
    assert NONE_CLEAR in method
    for model in POOL:
        assert f"`{model}`" in method, model
    rows = len(POOL) * sum(KEPT_ITEMS.values())
    assert f"That leaves {rows:,} rows: " + join(f"`{t}` {n:,}" for t, n in KEPT_ITEMS.items()) + " items" in method
    assumed = section(text, "## Assumed")
    for phrase in ASSUMED_PHRASES:
        assert phrase in assumed, phrase


def test_results_md_tables_are_the_committed_file(dr):
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    blocks = fenced(section(RESULTS_MD.read_text(encoding="utf-8"), "## Results"), "text")
    assert len(blocks) == 2
    assert blocks[0] == TABLE_CMD + "\n" + dr.table(results).rstrip("\n")
    assert blocks[1] == PARENT_CMD + "\n" + dr.parent_table(results, 0.8, 0).rstrip("\n")


def test_results_md_reading_it_is_built_from_the_committed_file():
    want = reading_bullets(json.loads(RESULTS.read_text(encoding="utf-8")))
    reading = section(RESULTS_MD.read_text(encoding="utf-8"), "## Reading it")
    bullets = [line[2:] for line in reading.split("\n") if line.startswith("- ")]
    assert bullets == want


def test_results_md_regenerate_block():
    regenerate = section(RESULTS_MD.read_text(encoding="utf-8"), "## Regenerate")
    blocks = fenced(regenerate, "bash")
    assert len(blocks) == 1 and blocks[0].split("\n") == REGENERATE
    before = regenerate[:regenerate.index("```bash")]
    for needle in ("1,018,191,580", "`~/.cache/ai-model-routing-evidence/response-bank/`", "sha256", "not committed"):
        assert needle in before, needle


def method_sentences(full, registry):
    """The Method sentences 13.14 v1.313 builds from the cells of the pinned run, in its order."""
    _kept, dropped, run = full
    cells = run["cells"]
    seeds, bars = len(run["config"]["seeds"]), run["config"]["bars"]
    per_task = Counter(item.split(":")[0] for item in dropped)
    left = sum(run["tasks"][t]["items"] for t in run["tasks"])
    drop = (f"{len(dropped)} items are dropped for a null token count ("
            + join(f"{n} in `{t}`" for t, n in sorted(per_task.items())) + f"), so {left:,} items remain.")
    sizes = [c["expected_input_tokens"] + c["expected_output_tokens"] for c in cells]
    size = f"which sum to {min(sizes):,} to {max(sizes):,} tokens over the cells"
    aime = [c for c in cells if c["task"] == "aime"]
    cal = sorted({c["calibration_items"] for c in aime})
    assert cal[-1] < 30
    per_flavor = Counter(c["flavor"] for c in aime)
    assert len(set(per_flavor.values())) == 1 and all(c["reason"] == "none_clear" for c in aime)
    aime_line = (f"`aime` has {run['tasks']['aime']['items']} items, so its calibration half holds {cal[0]} to {cal[-1]} "
                 f"over the seeds, under the default `min_samples` of 30 on all {seeds}: no model clears a bar there, "
                 f"and all {per_flavor['cost_effective']:,} `aime` cells of each flavor are 13.5 row 7 (`none_clear`).")
    outside = [c for c in cells if c["task"] != "aime"]
    counts = {}
    for flavor in FLAVORS:
        for bar in bars:
            here = [c for c in outside if c["flavor"] == flavor and c["bar"] == bar]
            counts[flavor, bar] = (sum(c["reason"] == "none_clear" for c in here), len(here))
    assert counts["cost_effective", bars[0]] == counts["cost_blind", bars[0]]
    assert counts["cost_effective", bars[-1]] == counts["cost_blind", bars[-1]]
    (a, m), (b, m2) = counts["cost_effective", bars[0]], counts["cost_effective", bars[-1]]
    assert m == m2
    high = [c for c in outside if c["bar"] == bars[-1]]
    never = sorted({c["task"] for c in high} - {c["task"] for c in high if c["reason"] != "none_clear"})
    cleared = sorted({c["task"] for c in high if c["reason"] != "none_clear"})
    assert len(cleared) == 1
    cleared_seeds = {c["seed"] for c in high if c["task"] == cleared[0] and c["reason"] != "none_clear"}
    outside_line = (f"Outside `aime`, {a:,} of each flavor's {m:,} cells at bar {bars[0]} and {b:,} of its {m:,} at bar "
                    f"{bars[-1]} are `none_clear`: at bar {bars[-1]} no model clears "
                    + " or ".join(f"`{t}`" for t in never)
                    + f" on any seed, and a model clears `{cleared[0]}` on {len(cleared_seeds)} of the {seeds} seeds.")
    assert all(c["inline_allowed"] for c in cells)
    windows = {m.id: m.context_window for m in registry.models}
    smallest = min(windows, key=windows.get)
    others = {w for model, w in windows.items() if model != smallest}
    assert len(others) == 1 and windows[smallest] < min(others)
    c2 = run["config"]["points"][2]["context_tokens"]
    assert c2 < windows[smallest]
    blocked = (f"Inline is blocked on no cell: at point 2, C = {c2:,} is under every parent's window, "
               f"{windows[smallest]:,} for `{smallest}` and {min(others):,} for the other four.")
    reasons = Counter(c["reason"] for c in cells if c["flavor"] == "cost_effective")
    ordered = sorted(reasons.items(), key=lambda kv: (-kv[1], kv[0]))
    reason_line = (f"Of the {sum(reasons.values()):,} `cost_effective` cells, " + join(f"{n:,} `{r}`" for r, n in ordered)
                   + ". " + NONE_CLEAR)
    return [drop, size, aime_line, outside_line, blocked, reason_line]


def test_pinned_method_sentences(pinned_full):
    sentences = method_sentences(pinned_full, Registry.load(REGISTRY))
    assert sentences[0] == "4 items are dropped for a null token count (4 in `mmlu_pro`), so 13,311 items remain."
    assert sentences[1] == "which sum to 1,265 to 11,045 tokens over the cells"
    assert "holds 10 to 21 over the seeds" in sentences[2] and "all 2,000 `aime` cells" in sentences[2]
    assert sentences[3] == ("Outside `aime`, 60 of each flavor's 3,000 cells at bar 0.8 and 2,980 of its 3,000 at bar "
                            "0.9 are `none_clear`: at bar 0.9 no model clears `livecodebench` or `mmlu_pro` on any "
                            "seed, and a model clears `gpqa_diamond` on 1 of the 50 seeds.")
    assert "262,144 for `moonshotai/kimi-k2.7-code` and 1,000,000 for the other four." in sentences[4]
    method = section(RESULTS_MD.read_text(encoding="utf-8"), "## Method")
    for sentence in sentences:
        assert sentence in method, sentence


# ---- the README subsection (DESIGN 12.8 v1.316, row E21d) ----

README = ROOT / "README.md"
README_HEADING = "Delegation on the LLM Routing Response Bank"
EVIDENCE_HEADINGS = ["RouterBench", "AutoBench", "AutoBench judges", "tau2-bench", "LiveCodeBench",
                     "LLMRouterBench", "LLM Routing Response Bank", "Delegation on AutoBench", "Delegation on tau2-bench",
                     "Delegation on LLMRouterBench", README_HEADING]
README_LINKS = (
    "[LLM Routing Response Bank](https://huggingface.co/datasets/Lurume/llm-routing-response-bank)",
    f"[`{REVISION[:7]}`]({DATASET_TREE})",
    "ODC-BY-4.0",
    "planned licence",
    '"with attribution to this dataset repository"',
    "from the dataset repository https://huggingface.co/datasets/Lurume/llm-routing-response-bank",
    "[RESULTS.md](evidence/response-bank-delegation/RESULTS.md)",
    "[results.json](evidence/response-bank-delegation/results.json)",
    "[registry.json](evidence/response-bank-delegation/registry.json)",
    "[evidence/response-bank/README.md](evidence/response-bank/README.md)",
    "[research/delegation-datasets.md](research/delegation-datasets.md)",
    "[inline or sub-agent](#inline-or-sub-agent)",
    "[LLM Routing Response Bank](#llm-routing-response-bank)",
    "[Delegation on AutoBench](#delegation-on-autobench)",
    f"without the {len(DROPPED)} `mmlu_pro` items",
    "8,000, 64,000 and 200,000",
    "list-price estimate",
)
# Each is the start of one RESULTS.md bullet that the README repeats verbatim (12.8 v1.316).
README_METHOD = ("`aime` has 30 items", "Outside `aime`, ", "Inline is blocked on no cell", "Of the ")
README_ASSUMED = ("The lossless brief", "Every cost is a list price", "A row's input tokens are `usage.input`",
                  "The windows are the vendor pages'", "The vendor pages, opened 2026-11-12",
                  "The limits of `DESIGN.md` 13.8")
README_RED = pytest.mark.xfail(strict=True, raises=AssertionError,
                               reason="the README subsection lands with row E21d (DESIGN 12.8 v1.316)")


def readme_subsection():
    text = README.read_text(encoding="utf-8")
    heading = "\n## Evidence: held-out results on public data\n"
    assert text.count(heading) == 1
    evidence = text.split(heading, 1)[1].split("\n## ", 1)[0]
    assert re.findall(r"^### (.*)$", evidence, re.M) == EVIDENCE_HEADINGS
    return evidence.split(f"\n### {README_HEADING}\n", 1)[1].split("\n### ", 1)[0]


def readme_counts_sentence(results):
    config, tasks = results["config"], results["tasks"]
    families = join([f"`{name}` {task['items']:,}" for name, task in tasks.items()])
    parents = join([f"`{p}`" for p in config["parents"]])
    total = sum(task["items"] for task in tasks.values())
    return (f"Each item is one benchmark question, which each model answered in one recorded call, one task per "
            f"benchmark family ({families} items, {total:,} in all), with each of the {len(config['parents'])} "
            f"models ({parents}) as the parent, over {len(config['seeds'])} seeds.")


def results_md_line(start, heading):
    found = [line for line in section(RESULTS_MD.read_text(encoding="utf-8"), heading).split("\n")
             if line.startswith(f"- {start}")]
    assert len(found) == 1, start
    return found[0]


def root_pool_line():
    line = results_md_line("The pool is all five", "## Method")
    assert line.startswith("- " + POOL_SENTENCE)
    assert line.count("](../response-bank/RESULTS.md)") == 1 and line.count("](") == 1
    return line.replace("](../response-bank/RESULTS.md)", "](evidence/response-bank/RESULTS.md)")


@README_RED
def test_readme_subsection_links_the_sources_and_licence():
    sub = readme_subsection()
    for needle in README_LINKS:
        assert needle in sub, needle
    assert sub.isascii() and "\u2013" not in sub and "\u2014" not in sub
    assert "](../" not in sub


@README_RED
def test_readme_subsection_shows_the_counts_tables_and_reading_it(dr):
    sub = readme_subsection()
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert readme_counts_sentence(results) in sub
    assert sum(task["items"] for task in results["tasks"].values()) == 13_311
    bar = results["config"]["bars"][0]
    assert PARENT_CMD == f"{TABLE_CMD} --bar {bar} --point 0"
    assert f"```text\n{TABLE_CMD}\n{dr.table(results)}\n```" in sub
    assert f"```text\n{PARENT_CMD}\n{dr.parent_table(results, bar, 0)}\n```" in sub
    # the first three Reading it bullets, which the RESULTS.md test builds from the committed file; the
    # v1.239 bullet on the parents dearer than inline and the size bullet, the last, stay in RESULTS.md
    reading = [line for line in section(RESULTS_MD.read_text(encoding="utf-8"), "## Reading it").split("\n")
               if line.startswith("- ")]
    assert len(reading) == 5 and reading[-1].startswith("- `results.json` is ")
    for line in reading[:3]:
        assert f"\n{line}\n" in sub, line
    for line in reading[3:]:
        assert line[2:] not in sub, line
    assert "`results.json` is " not in sub


@README_RED
def test_readme_subsection_repeats_the_results_md_lines():
    sub = readme_subsection()
    for start in README_METHOD:
        assert f"\n{results_md_line(start, '## Method')}\n" in sub, start
    for start in README_ASSUMED:
        assert f"\n{results_md_line(start, '## Assumed')}\n" in sub, start
    # the one repeated line with a link targets the routing RESULTS.md from the repo root
    pool = root_pool_line()
    assert f"\n{pool}\n" in sub
    limits = sub.index("\nLimits, as RESULTS.md states them:\n")
    assert sub.index(pool) < limits
    assert sub.index(results_md_line(README_METHOD[-1], "## Method")) < limits
    assert limits < sub.index(results_md_line(README_ASSUMED[0], "## Assumed"))


@README_RED
def test_readme_subsection_regenerate_block_is_the_results_md_one():
    sub = readme_subsection()
    assert re.findall(r"```bash\n.*?```\n", sub, re.S) == ["```bash\n" + "\n".join(REGENERATE) + "\n```\n"]
    blocks = fenced(section(RESULTS_MD.read_text(encoding="utf-8"), "## Regenerate"), "bash")
    assert blocks and blocks[0].split("\n") == REGENERATE


@README_RED
def test_readme_layout_names_the_results_md():
    text = README.read_text(encoding="utf-8")
    layout = text.split("\n## Layout\n", 1)[1].split("\n## ", 1)[0]
    lrbd = "(delegation on LLMRouterBench: evidence/llmrouterbench-delegation/RESULTS.md)\n"
    assert lrbd + ("                (delegation on the LLM Routing Response Bank: "
                   "evidence/response-bank-delegation/RESULTS.md)\n") in layout


@README_RED
def test_readme_limitations_name_the_fourth_dataset():
    text = README.read_text(encoding="utf-8")
    limits = text.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in limits.splitlines() if line.startswith("- The delegation evidence reads")]
    assert len(bullets) == 1
    assert bullets[0].startswith("- The delegation evidence reads four datasets: the AutoBench 2026 matrix, "
                                 "LLMRouterBench on the ")
    assert (", which leaves out its best single model, `google/gemini-2.5-pro`, the LLM Routing Response Bank on "
            f"all {len(POOL)} of its models ([evidence/response-bank-delegation/RESULTS.md]"
            "(evidence/response-bank-delegation/RESULTS.md)), and tau2-bench ") in bullets[0]
    pays = [line for line in limits.splitlines() if line.startswith("- On the four delegation results files of ")]
    assert len(pays) == 1
    assert pays[0].startswith("- On the four delegation results files of AutoBench 2026, tau2-bench and "
                              "LLMRouterBench the per-task decision is close to a fixed policy.")
