"""Longtail-SWE's other configs at their vendors' list prices (DESIGN 12.22 v1.497, row R53): research/longtail-pool.md
and its script research/longtail_pool.py. CI has neither `pyarrow` nor the eleven files, so the test that runs the
script on them skips there; the others read the note, DESIGN.md, research/README.md, the script's constants and
synthetic rows."""
import importlib.util
import io
import json
import re
from contextlib import redirect_stdout
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "research" / "longtail-pool.md"
SCRIPT = ROOT / "research" / "longtail_pool.py"
CONVERTER = ROOT / "evidence" / "longtail-swe" / "convert.py"
DESIGN = ROOT / "DESIGN.md"
RESEARCH_README = ROOT / "research" / "README.md"
BULLET = "- Longtail-SWE's other configs at their vendors' list prices (v1.497, row R53): "
# each vendor prefix and the start of the one page its prices may come from
PAGES = {"deepseek": "https://api-docs.deepseek.com/", "moonshotai": "https://platform.moonshot.ai/",
         "qwen": "https://www.alibabacloud.com/help/en/model-studio/", "z-ai": "https://docs.z.ai/"}


def load_path(name, path):
    if not path.is_file():
        raise FileNotFoundError(f"no script at {path.name}")
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def load():
    return load_path("longtail_pool_for_tests", SCRIPT)


def note():
    return NOTE.read_text(encoding="utf-8")


def results_block(text):
    found = re.findall(r"\n## Results\n\n```text\n(.*?)```\n", text, re.S)
    assert len(found) == 1
    return found[0]


def section(text, heading):
    start = text.index(f"\n## {heading}\n") + 1
    end = text.find("\n## ", start + 1)
    return text[start:] if end < 0 else text[start:end + 1]


def reading_of(text):
    body = section(text, "Reading it")
    return body[len("## Reading it\n\n"):].rstrip("\n") + "\n"


def test_design_12_22_specifies_the_note():
    design = DESIGN.read_text(encoding="utf-8")
    lines = [line for line in design.split("\n") if line.startswith(BULLET)]
    assert len(lines) == 1
    assert design.index("\n### 12.22 ") < design.index(lines[0]) < design.index("\n### 12.23 ")
    for phrase in ("`research/longtail-pool.md` and its script `research/longtail_pool.py`", "601,005,089 bytes",
                   "read on 2026-11-19", "`UNPRICED` leaves out `deepseek/deepseek-v4-flash`", "(the 49 with no token counts)",
                   "a `LIST_PRICES` ID already in `models.json` exits 2", "a bad option exits 2 with one `error:` line",
                   "`research/README.md` lists the note", "No results file, package, README or workflow change"):
        assert phrase in lines[0], phrase
    assert "\u2013" not in lines[0] and "\u2014" not in lines[0] and len(lines[0].encode()) < 6000


def test_research_readme_lists_the_note():
    note()  # FileNotFoundError until the note exists
    text = RESEARCH_README.read_text(encoding="utf-8")
    assert text.count("| [longtail-pool.md](longtail-pool.md) | ") == 1
    assert text.count("[longtail_pool.py](longtail_pool.py)") == 1
    assert text.count("\n- `research/longtail-pool.md` ") == 1


def test_each_price_names_its_vendor_page_and_read_date():
    lp, text = load(), note()
    block = results_block(text)
    assert lp.READ == "2026-11-19" and f"(pages read {lp.READ})\n" in block
    assert len(lp.LIST_PRICES) == 6 and len(lp.UNPRICED) == 1 and not set(lp.LIST_PRICES) & set(lp.UNPRICED)
    for mid, (p_in, p_out, page) in lp.LIST_PRICES.items():
        assert page.startswith(PAGES[mid.split("/")[0]]), mid
        for price in (p_in, p_out):
            assert isinstance(price, float) and 0 < price < 100, (mid, price)
        assert block.count(f"{mid:<30} {p_in:>5g} {p_out:>7g}  {page}\n") == 1, mid
        assert page in section(text, "Facts"), page
    for mid, page in lp.UNPRICED.items():
        assert page.startswith(PAGES[mid.split("/")[0]])
        assert len([line for line in block.split("\n") if line.startswith(f"left out: {mid} (") and line.endswith(page)]) == 1
    assert "2026-11-19" in section(text, "Facts")


def test_no_vendor_price_replaces_a_registry_row(monkeypatch, capsys):
    lp = load()
    reg = lp.registry()
    ids = [m["id"] for m in reg["models"]]
    assert len(ids) == len(set(ids))
    for mid, (p_in, p_out, _) in lp.LIST_PRICES.items():
        assert {"id": mid, "price_in": p_in, "price_out": p_out} in reg["models"]
    monkeypatch.setitem(lp.LIST_PRICES, "openai/gpt-6.1-sol", (1.0, 2.0, "https://example.com/"))
    with pytest.raises(ValueError, match=r"^already in the registry: openai/gpt-6\.1-sol$"):
        lp.registry()
    # review iter-354 should-fix 4: the clash exits 2 through `main` with one `error:` line
    stub(monkeypatch, lp, {"data/b.parquet": rows_of("kimi-k3", 2)})
    assert lp.main([]) == 2
    assert capsys.readouterr().err == "error: already in the registry: openai/gpt-6.1-sol\n"


@pytest.mark.parametrize("name, expected", [
    ("claude-opus-5.5", "anthropic/claude-opus-5.5"), ("gpt-6.1-sol", "openai/gpt-6.1-sol"),
    ("deepseek-v4.1-flash", "deepseek/deepseek-v4.1-flash"), ("kimi-k3.1-pro", "moonshotai/kimi-k3.1-pro"),
    ("kimi-k3", "moonshotai/kimi-k3"), ("qwen3.8-27b", "qwen/qwen3.8-27b"), ("qwen3.6-27b", "qwen/qwen3.6-27b"),
    ("glm-5.3-flash", "z-ai/glm-5.3-flash"),
    ("qwen3.8-27b\n", None), ("Qwen/Qwen3.8-27B", None), ("qwen", None), ("qwen-3", None), ("kimi-", None),
    ("llama-4", None), ("deepseek-ai/DeepSeek-V4.1-Flash-1017", None), (None, None), (7, None),
])
def test_model_ids_by_regex_over_the_canonical_name(name, expected):
    lp = load()
    if expected is None:
        with pytest.raises(ValueError, match="^model name "):
            lp.model_id(name)
    else:
        assert lp.model_id(name) == expected


def test_the_converter_file_is_not_widened():
    lp = load()
    fresh = load_path("longtail_swe_convert_unwidened", CONVERTER)
    assert list(fresh.FILES) == list(lp.FOUR) and len(fresh.FILES) == 4 and len(fresh.VENDORS) == 2
    with pytest.raises(ValueError):
        fresh.model_id("kimi-k3")
    assert list(lp.CONVERT.FILES) == sorted({**lp.FOUR, **lp.EXTRA}) and len(lp.CONVERT.FILES) == 11
    assert len(lp.EXTRA) == 7 and not set(lp.EXTRA) & set(lp.FOUR)
    assert sum(size for size, _ in lp.EXTRA.values()) == 601_005_089
    block = results_block(note())
    for name, (size, sha) in lp.EXTRA.items():
        assert re.fullmatch(r"data/swelike__[a-z0-9.-]+\.parquet", name) and re.fullmatch(r"[0-9a-f]{64}", sha)
        assert block.count(f"{name} {size} {sha}\n") == 1, name


def trajectory(tin, tout):
    tokens = {"input": tin, "cached_input": None, "cache_creation": None, "output": tout,
              "total": (tin or 0) + (tout or 0)}
    return json.dumps({"usage": {"tokens": tokens}})


def rows_of(canonical, n, bad=()):
    return [{"instance_id": f"repo__issue-{i}", "programming_language": "OCaml", "canonical_model": canonical,
             "run_index": 0, "resolved": i % 2, "initial_statement_matches_release": True,
             "trajectory": trajectory(None, None) if i in bad else trajectory(1000, 100)} for i in range(n)]


def stub(monkeypatch, lp, files):
    monkeypatch.setattr(lp.CONVERT, "FILES", {name: (1, "0" * 64) for name in files})
    monkeypatch.setattr(lp.CONVERT, "fetch", lambda cache=None: {name: name for name in files})
    monkeypatch.setattr(lp.CONVERT, "read_rows", lambda path: files[path])


def test_a_left_out_model_is_counted_and_never_priced(monkeypatch):
    lp = load()
    stub(monkeypatch, lp, {"data/a.parquet": rows_of("deepseek-v4-flash", 3, bad=(1,)),
                           "data/b.parquet": rows_of("kimi-k3", 2)})
    recs, left, cached = lp.records()
    assert left == {"deepseek/deepseek-v4-flash": (3, 1)}
    assert cached == {(f"repo__issue-{i}", "moonshotai/kimi-k3"): (0, 1000, 100) for i in range(2)}
    assert [r["model"] for r in recs] == ["moonshotai/kimi-k3"] * 2
    p_in, p_out, _ = lp.LIST_PRICES["moonshotai/kimi-k3"]
    assert [r["cost_usd"] for r in recs] == [(1000 * p_in + 100 * p_out) / 1_000_000] * 2
    assert lp.refused(rows_of("glm-5.3-flash", 4, bad=(0, 3))) == 2


def test_a_priced_run_with_no_token_counts_and_a_mixed_file_stop_the_script(monkeypatch, capsys):
    lp = load()
    stub(monkeypatch, lp, {"data/b.parquet": rows_of("kimi-k3", 2, bad=(1,))})
    with pytest.raises(ValueError, match=r"^data/b\.parquet: row 1: token count input None "):
        lp.records()
    assert lp.main([]) == 2
    err = capsys.readouterr().err
    assert err.startswith("error: data/b.parquet: row 1: token count input") and err.count("\n") == 1
    stub(monkeypatch, lp, {"data/c.parquet": rows_of("deepseek-v4-flash", 1) + rows_of("kimi-k3", 1)})
    with pytest.raises(ValueError, match=r"^data/c\.parquet: a left-out model shares its file with another$"):
        lp.records()
    assert lp.main(["--bogus"]) == 2
    assert capsys.readouterr().err.count("\n") == 1


def test_reading_it_is_built_from_the_block():
    lp, text = load(), note()
    facts = lp.facts_from_block(results_block(text))
    assert len(facts["prices"]) == 10 and len(facts["alone"]) == 10 and len(facts["base"]) == 3
    assert facts["equal"] == (8, 8, 8, 8) and len(facts["picks"]) == 8 and len(facts["left"]) == 1
    assert set(facts["cache"]) == set(facts["prices"])
    assert {m for m, v in facts["cache"].items() if v[1] != "-"} == set(lp.CACHE_HIT) <= set(lp.LIST_PRICES)
    assert reading_of(text) == lp.reading(facts)


def test_reading_follows_a_changed_block():
    lp = load()
    block = results_block(note())
    luna = [line for line in block.split("\n") if line.startswith("openai/gpt-5.6-luna ") and "(" in line]
    assert len(luna) == 1
    moved = block.replace(luna[0], luna[0][:-len("252.57")] + "999.99").replace(": 8 of 8; ", ": 7 of 8; ")
    assert luna[0].endswith(" 252.57") and moved != block
    text = lp.reading(lp.facts_from_block(moved))
    assert "on 7 of 8 (bar, flavor) rows" in text and "`openai/gpt-5.6-luna` (0.726 for" not in text
    assert "`openai/gpt-6.1-sol` (0.804 for 357.50) has at least the held-out success of every added model" in text


def test_the_note_holds_its_sections_and_the_public_content_rules():
    text = note()
    heads = re.findall(r"^## (.+)$", text, re.M)
    assert heads == ["Facts", "Method", "Results", "Reading it", "Recommendation", "Limits"]
    assert text.isascii() and "/Users/" not in text and "/home/" not in text
    assert "Nothing for the README or a results file now" in section(text, "Recommendation")
    assert "no routed row" in section(text, "Facts") and "at list prices" in section(text, "Facts")
    assert "billed at the Flash price" in section(text, "Facts")


@pytest.fixture(scope="module")
def fresh_block():
    pytest.importorskip("pyarrow")
    lp = load()
    cache = lp.CONVERT.default_cache_dir()
    if not all((cache / name).is_file() for name in lp.CONVERT.FILES):
        pytest.skip("the eleven Longtail-SWE files are not in the default cache")
    out = io.StringIO()
    with redirect_stdout(out):
        assert lp.main([]) == 0
    return out.getvalue()


def test_note_results_block_is_a_fresh_run(fresh_block):
    assert results_block(note()) == fresh_block
