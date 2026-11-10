"""research/delegation-datasets.md `## LLMRouterBench (2026-11-09)` and research/llmrouterbench_prices.py
(DESIGN 13.9 v1.187).

The section's numbers are the script's lines on the LLMRouterBench matrix, compared byte for byte when
the pinned file is cached (the session fixture `llmrouterbench_pinned` of tests/conftest.py, which CI
never fills). The script's lines, its price fit and its exits are tested on a small matrix.
"""

import contextlib
import importlib.util
import io
import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "llmrouterbench_prices.py"
NOTE = ROOT / "research" / "delegation-datasets.md"
CONVERTER = ROOT / "evidence" / "llmrouterbench" / "convert.py"
DESIGN = ROOT / "DESIGN.md"
HEADING = "## LLMRouterBench (2026-11-09)"
COMMAND = "$ python research/llmrouterbench_prices.py --matrix llmrouterbench-matrix.jsonl"
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl",
    COMMAND[2:],
]
# the vendor pages read on 2026-11-09, as the section's table gives them (USD per 1M tokens)
VENDOR = {"anthropic/claude-sonnet-4": (3, 15), "openai/gpt-5": (1.25, 10), "openai/gpt-5-chat": (1.25, 10),
          "z-ai/glm-4.6": (0.6, 2.2)}
# the subsection of 2026-11-10 (DESIGN 13.9 v1.194, row E17a): per priced model, its window in tokens,
# its kind and, for a weights' position limit, the Hugging Face repo and pinned revision of its config.json
WINDOW_HEADING = "### Context windows (2026-11-10)"
VENDOR_PAGE, POSITION_LIMIT = "vendor page", "weights' position limit"
WINDOWS = {
    "anthropic/claude-sonnet-4": (200000, VENDOR_PAGE, None),
    "deepseek/deepseek-r1-0528": (163840, POSITION_LIMIT,
                                  ("deepseek-ai/DeepSeek-R1-0528", "4236a6af538feda4548eca9ab308586007567f52")),
    "deepseek/deepseek-v3-0324": (163840, POSITION_LIMIT,
                                  ("deepseek-ai/DeepSeek-V3-0324", "e9b33add76883f293d6bf61f6bd89b497e80e335")),
    "deepseek/deepseek-v3.1-terminus": (163840, POSITION_LIMIT,
                                        ("deepseek-ai/DeepSeek-V3.1-Terminus",
                                         "19510d6dc61f79dbd925bd51ee8a9081c509a4b6")),
    "internlm/intern-s1": (65536, POSITION_LIMIT, ("internlm/Intern-S1", "4ecad381e28293c4825793f113327cc016cdcbda")),
    "openai/gpt-5": (400000, VENDOR_PAGE, None),
    "openai/gpt-5-chat": (128000, VENDOR_PAGE, None),
    "z-ai/glm-4.6": (200000, VENDOR_PAGE, None),
}
DELEGATION_RESULTS = ROOT / "evidence" / "delegation" / "results.py"
# the vendor-page rows: the page URL that opens the row and a verbatim quote the row gives (review iter-146)
WINDOW_PAGES = {
    "anthropic/claude-sonnet-4": ("https://platform.claude.com/docs/en/build-with-claude/context-windows",
                                  "\"Other Claude models, including Claude Sonnet 4.5 (deprecated), have a 200k-token context window\""),
    "openai/gpt-5": ("https://platform.openai.com/docs/models/gpt-5", "a 400,000 context window"),
    "openai/gpt-5-chat": ("https://platform.openai.com/docs/models/gpt-5-chat-latest", "a 128,000 context window"),
    "z-ai/glm-4.6": ("https://docs.z.ai/guides/llm/glm-4.6",
                     "\"The context window has been expanded from 128K to 200K tokens\""),
}
R1_CARD_QUOTE = "\"the maximum generation length is set to 64K tokens\""


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lrp():
    return _load("research_llmrouterbench_prices", SCRIPT)


def pool_ids():
    conv = _load("lrb_convert_for_prices", CONVERTER)
    return [conv.model_id(folder) for folder in conv.POOL]


# per model: (input price, output price, extra cost on the item `a|2`), USD per 1M tokens and USD
TINY = {"v/x": (2, 10, 0.0), "v/y": (1, 4, 0.001), "v/z": (0.5, 1.5, 0.0)}
ITEMS = ["a|0", "a|1", "a|2", "b|0", "b|1"]


def tiny_rows(null_on=("b|1", "v/z")):
    rows = []
    for j, (model, (p_in, p_out, extra)) in enumerate(sorted(TINY.items())):
        for k, item in enumerate(ITEMS):
            n_in, n_out = 1000 + 100 * k + 7 * j, 50 + 30 * k * k
            cost = (n_in * p_in + n_out * p_out) / 1e6 + (extra if item == "a|2" else 0.0)
            rows.append({"task": item.split("|")[0], "item": item, "model": model, "correct": k % 2 == 0,
                         "cost_usd": cost, "input_tokens": n_in,
                         "output_tokens": None if (item, model) == null_on else n_out})
    return rows


def _write(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def _main(lrp, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = lrp.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_fit_recovers_an_exact_pair(lrp):
    points = [(1000 + 13 * k, 40 + 9 * k * k, (1000 + 13 * k) * 0.27e-6 + (40 + 9 * k * k) * 1.0e-6)
              for k in range(6)]
    a, b, worst, unrounded = lrp.fit(points)
    assert (a, b) == (0.27, 1.0) and worst <= lrp.TOLERANCE and unrounded <= lrp.TOLERANCE


def test_fit_reports_how_far_a_cost_off_the_pair_is(lrp):
    points = [(1000 + 13 * k, 40 + 9 * k * k, (1000 + 13 * k) * 0.27e-6 + (40 + 9 * k * k) * 1.0e-6)
              for k in range(6)]
    points[2] = (points[2][0], points[2][1], points[2][2] + 0.002)
    a, b, worst, unrounded = lrp.fit(points)
    assert worst > lrp.TOLERANCE and worst < 0.002
    assert unrounded > math.sqrt(len(points)) * lrp.TOLERANCE


# review iter-144 must-fix 2: an exact pair with more than 4 decimals fails only after rounding
FINER = [(n_in, n_out, (n_in * 1.23456 + n_out * 2.34567) / 1e6) for n_in, n_out in ((1000, 100), (100, 1000), (500, 700))]


def test_fit_tells_a_finer_pair_from_no_pair(lrp):
    a, b, worst, unrounded = lrp.fit(FINER)
    assert (a, b) == (1.2346, 2.3457)
    assert worst > lrp.TOLERANCE and unrounded <= lrp.TOLERANCE


def test_fit_with_counts_that_fix_no_pair_is_none(lrp):
    assert lrp.fit([(10, 20, 1e-5), (20, 40, 2e-5)]) is None
    assert lrp.fit([]) is None


def test_report_lines_on_a_small_matrix(lrp):
    lines = lrp.report(tiny_rows(), {"v/x": (2, 10), "v/y": (2, 2)})
    kept = ITEMS[:4]
    rows = {(r["item"], r["model"]): r for r in tiny_rows()}

    def recorded(model):
        return math.fsum(rows[(i, model)]["cost_usd"] for i in kept)

    def at(model, p_in, p_out):
        return math.fsum((rows[(i, model)]["input_tokens"] * p_in + rows[(i, model)]["output_tokens"] * p_out) / 1e6
                         for i in kept)

    assert lines[0] == "5 items over 2 tasks and 3 models; largest input_tokens 1414"
    assert lines[1] == "null token count: 1 items (b 1), 3 rows; kept 4 items, 12 rows"
    assert lines[2] == ("per model on the kept items: recorded cost, cost at the list price, their ratio, and "
                        "one price pair for every recorded cost (USD per 1M tokens, exact within 1e-09 USD)")
    x = recorded("v/x")
    assert lines[3] == (f"  v/x: recorded {x:.6f}; list 2 in, 10 out: {at('v/x', 2, 10):.6f}, ratio "
                        f"{x / at('v/x', 2, 10):.3f}; exact pair 2 in, 10 out")
    y = recorded("v/y")
    assert lines[4].startswith(f"  v/y: recorded {y:.6f}; list 2 in, 2 out: {at('v/y', 2, 2):.6f}, ratio "
                               f"{y / at('v/y', 2, 2):.3f}; no pair within 1e-09 USD (least squares ")
    assert re.fullmatch(r".* in, .* out to 4 decimals; unrounded off by up to \d+\.\d{6} USD\)", lines[4])
    assert lines[5] == f"  v/z: recorded {recorded('v/z'):.6f}; list none; exact pair 0.5 in, 1.5 out"
    assert lines[6] == "summary: list price 2 of 3, exact pair 2 of 3, either 3 of 3"
    assert len(lines) == 7


def test_report_drops_every_row_of_an_item_with_a_null_count(lrp):
    both = tiny_rows(null_on=("a|0", "v/x"))
    lines = lrp.report(both, {})
    assert lines[1] == "null token count: 1 items (a 1), 3 rows; kept 4 items, 12 rows"


def finer_rows():
    return [{"task": "t", "item": f"t|{k}", "model": "v/f", "cost_usd": cost, "input_tokens": n_in,
             "output_tokens": n_out} for k, (n_in, n_out, cost) in enumerate(FINER)]


def test_report_says_no_4_decimal_pair_when_a_finer_pair_is_not_ruled_out(lrp):
    lines = lrp.report(finer_rows(), {})
    assert lines[1] == "null token count: 0 items, 0 rows; kept 3 items, 3 rows"
    assert re.fullmatch(r"  v/f: recorded \d+\.\d{6}; list none; no 4-decimal pair \(least squares 1\.2346 in, "
                        r"2\.3457 out, off by up to \d+\.\d{6} USD; a finer pair is not ruled out\)", lines[3]), lines[3]


# review iter-144 must-fix 1: a zero list cost and a matrix with no count left report, not crash
def test_report_with_a_zero_list_cost_prints_ratio_none(lrp):
    rows = [{"task": "t", "item": f"t|{k}", "model": "v/z", "cost_usd": 0.0, "input_tokens": 0, "output_tokens": 0}
            for k in range(2)]
    lines = lrp.report(rows, {"v/z": (1, 2)})
    assert lines[0] == "2 items over 1 tasks and 1 models; largest input_tokens 0"
    assert lines[3] == "  v/z: recorded 0.000000; list 1 in, 2 out: 0.000000, ratio none; no exact pair (the counts fix no pair)"
    assert lines[4] == "summary: list price 1 of 1, exact pair 0 of 1, either 1 of 1"


def test_report_when_every_item_is_dropped_and_no_row_has_an_input_count(lrp):
    rows = [{"task": "t", "item": f"t|{k}", "model": "v/n", "cost_usd": 0.5, "input_tokens": None, "output_tokens": 3}
            for k in range(2)]
    lines = lrp.report(rows, {"v/n": (1, 2)})
    assert lines[0] == "2 items over 1 tasks and 1 models; largest input_tokens none"
    assert lines[1] == "null token count: 2 items (t 2), 2 rows; kept 0 items, 0 rows"
    assert lines[3] == "  v/n: recorded 0.000000; list 1 in, 2 out: 0.000000, ratio none; no exact pair (the counts fix no pair)"


def test_main_prints_the_report(lrp, tmp_path):
    code, out, err = _main(lrp, ["--matrix", str(_write(tmp_path / "m.jsonl", tiny_rows()))])
    assert (code, err) == (0, "")
    assert out == "\n".join(lrp.report(tiny_rows())) + "\n"


@pytest.mark.parametrize("break_it", ["missing", "not_json", "not_object", "no_key", "negative_tokens",
                                      "bool_tokens", "bad_cost", "repeated", "incomplete"])
def test_main_exits_2_with_one_error_line(lrp, tmp_path, break_it):
    path = tmp_path / "m.jsonl"
    rows = tiny_rows()
    if break_it == "missing":
        pass
    elif break_it == "not_json":
        path.write_text("{\n", encoding="utf-8")
    elif break_it == "not_object":
        path.write_text("[1]\n", encoding="utf-8")
    else:
        if break_it == "no_key":
            del rows[0]["cost_usd"]
        elif break_it == "negative_tokens":
            rows[0]["input_tokens"] = -1
        elif break_it == "bool_tokens":
            rows[0]["output_tokens"] = True
        elif break_it == "bad_cost":
            rows[0]["cost_usd"] = float("inf")
        elif break_it == "repeated":
            rows.append(dict(rows[0]))
        elif break_it == "incomplete":
            rows.pop()
        _write(path, rows)
    code, out, err = _main(lrp, ["--matrix", str(path)])
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1


def test_script_is_standard_library():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^(?:from|import) ([\w.]+)", text, flags=re.M)}
    assert imports <= {"argparse", "json", "math", "sys", "pathlib"}
    assert text.isascii()


def _section():
    note = NOTE.read_text(encoding="utf-8")
    assert note.count("\n" + HEADING + "\n") == 1
    section = note.split("\n" + HEADING + "\n", 1)[1]
    assert "\n## " not in section, "the LLMRouterBench section is the last one"
    return section


def _blocks(text, lang):
    return re.findall(rf"^```{lang}\n(.*?)^```$", text, flags=re.M | re.S)


def test_section_shape_commands_and_ascii():
    section = _section()
    assert re.findall(r"^### (.+)$", section, flags=re.M) == [
        "List prices", "Recorded costs", "Recommendation", WINDOW_HEADING[4:]]
    assert _blocks(section, "bash") == ["\n".join(REGENERATE) + "\n"]
    [text] = _blocks(section, "text")
    assert text.startswith(COMMAND + "\n")
    assert section.isascii() and "\u2013" not in section and "\u2014" not in section
    first = [x for x in section.split("\n") if x.startswith("- ")][0]
    assert not re.search(r"\d", re.sub(r"`[^`]*`", "", first)), "the finding comes before any number"


def test_price_table_names_the_pool_and_the_script_prices(lrp):
    section = _section()
    table = section.split("\n### List prices\n", 1)[1].split("\n### ", 1)[0]
    rows = [x for x in table.split("\n") if x.startswith("| `")]
    models = [re.match(r"\| `([^`]+)` \|", x)[1] for x in rows]
    assert models == pool_ids()
    assert lrp.LIST_PRICES == VENDOR
    for model, row in zip(models, rows):
        cells = [c.strip() for c in row.strip("|").split("|")]
        assert len(cells) == 5, row
        assert cells[1].startswith("https://"), row
        if model in VENDOR:
            p_in, p_out = VENDOR[model]
            assert cells[3] == f"{p_in:g}, {p_out:g}", row
        else:
            assert cells[3] == "none found", row


def _table_rows(text):
    return [[c.strip() for c in x.strip("|").split("|")] for x in text.split("\n") if x.startswith("| `")]


def _windows_part():
    section = _section()
    assert section.count("\n" + WINDOW_HEADING + "\n") == 1
    return section.split("\n" + WINDOW_HEADING + "\n", 1)[1]


def test_window_table_gives_each_priced_model_a_window():
    """Every model priced by a page or an exact pair has one window row, in ID order (v1.194)."""
    section = _section()
    [text] = _blocks(section, "text")
    exact = sorted(re.findall(r"^  (\S+): .*; exact pair ", text, flags=re.M))
    assert sorted(set(VENDOR) | set(exact)) == sorted(WINDOWS)
    rows = _table_rows(_windows_part())
    assert [re.fullmatch(r"`([^`]+)`", r[0])[1] for r in rows] == sorted(WINDOWS)
    for row in rows:
        model = row[0].strip("`")
        window, kind, pinned = WINDOWS[model]
        assert len(row) == 5, row
        assert row[3] == f"{window:,}" and row[4] == kind, row
        assert row[1].startswith("https://") and re.search(r" \(2026-11-(09|10)[;)]", row[1]), row
        if kind == POSITION_LIMIT:
            repo, rev = pinned
            assert row[1].startswith(f"https://huggingface.co/{repo}/raw/{rev}/config.json (2026-11-10; "), row
            assert f"max_position_embeddings` {window}" in row[2], row
        else:
            assert pinned is None and "huggingface.co" not in row[1], row
            page, quote = WINDOW_PAGES[model]
            assert row[1].startswith(page + " (2026-11-"), row
            assert quote in row[2], row
    assert sorted(WINDOW_PAGES) == sorted(m for m, (_, kind, _) in WINDOWS.items() if kind == VENDOR_PAGE)
    [r1] = [r for r in rows if r[0] == "`deepseek/deepseek-r1-0528`"]
    assert R1_CARD_QUOTE in r1[2]
    [claude] = [r for r in rows if r[0] == "`anthropic/claude-sonnet-4`"]
    assert "so the window is inferred, as the page does not name Claude Sonnet 4" in claude[2]


def test_openai_windows_are_the_list_price_table_ones():
    section = _section()
    prices = section.split("\n### List prices\n", 1)[1].split("\n### ", 1)[0]
    listed = {r[0].strip("`"): r[4] for r in _table_rows(prices)}
    windows = {r[0].strip("`"): r for r in _table_rows(_windows_part())}
    for model in ("openai/gpt-5", "openai/gpt-5-chat"):
        assert listed[model] == f"{WINDOWS[model][0]:,}"
        assert listed[model] in windows[model][2]


def test_window_bullets_are_the_rule_3_arithmetic_at_the_13_10_points():
    """The room C leaves for the work under 13.4 rule 3, at the committed 13.10 context sizes."""
    dr = _load("delegation_results_for_windows", DELEGATION_RESULTS)
    small, mid, large = sorted(set(dr.CONTEXT_TOKENS))
    part = _windows_part()
    bullets = [x for x in part.split("\n") if x.startswith("- ")]
    assert len(bullets) == 5
    vendor = sorted(m for m, (_, kind, _) in WINDOWS.items() if kind == VENDOR_PAGE)
    assert bullets[0].startswith(f"- A vendor page gives a window for {len(vendor)} of the {len(WINDOWS)}: ")
    assert bullets[0].endswith("its window is inferred from the page's sentence on every Claude model outside its 1M-token list")
    open_ = [m for m in WINDOWS if m not in vendor]
    limits = sorted({WINDOWS[m][0] for m in open_}, reverse=True)
    assert all(f"{w:,}" in bullets[1] for w in limits)
    roomy = [m for m in WINDOWS if WINDOWS[m][0] > large]
    assert roomy == ["openai/gpt-5"]
    assert f"`openai/gpt-5`'s {WINDOWS['openai/gpt-5'][0]:,} is at most {large:,}" in bullets[2]
    assert f"for the other {len(WINDOWS) - len(roomy)} parents on any work" in bullets[2]
    assert f"read as 204,800, the two 200K windows leave {204800 - large:,} tokens" in bullets[2]
    room = {m: WINDOWS[m][0] - mid for m in WINDOWS}
    assert (f"At C = {mid:,} (point 1) the room the window leaves past C, for the K * (S_in + S_out) of the work, is "
            f"{room['internlm/intern-s1']:,} tokens for "
            f"`internlm/intern-s1`, {room['openai/gpt-5-chat']:,} for `openai/gpt-5-chat` and "
            f"{room['deepseek/deepseek-r1-0528']:,} for the DeepSeek models") in bullets[2]
    tight = min(WINDOWS, key=lambda m: WINDOWS[m][0])
    assert f"at C = {small:,} (points 0 and 3) the smallest is `{tight}`'s {WINDOWS[tight][0] - small:,}" in bullets[2]
    assert sorted(set(dr.CONTEXT_TOKENS)) == [small, mid, large] and len(dr.CONTEXT_TOKENS) == 3
    # the recommendation, pinned by its opening phrases (review iter-146 should-fix 3)
    assert bullets[3].startswith(f"- Keep all {len(WINDOWS)} models, each window with its kind in `notes`, ")
    assert "the window is the weights' position limit, not a served window" in bullets[3]
    assert bullets[4].startswith("- Read 200K as 200,000 for the two pages that write it and say so in `notes`")


def test_design_13_9_names_the_windows_subsection():
    design = DESIGN.read_text(encoding="utf-8")
    [bullet] = [x for x in design.split("\n") if x.startswith("  - (v1.187) LLMRouterBench as a third dataset: ")]
    assert f"(v1.194, row E17a) The section ends with `{WINDOW_HEADING}`" in bullet
    assert f"`{VENDOR_PAGE}` or `{POSITION_LIMIT}`" in bullet


def test_design_13_9_names_the_section_and_the_script():
    design = DESIGN.read_text(encoding="utf-8")
    assert "(v1.187) LLMRouterBench as a third dataset: [`research/delegation-datasets.md`]" in design
    assert "`research/llmrouterbench_prices.py`" in design
    bullet = [x for x in design.split("\n") if x.startswith("  - (v1.187) LLMRouterBench as a third dataset: ")]
    assert len(bullet) == 1
    for phrase in ("must be non-empty strings", "a file with no rows is an error", "dropped items included, and `none`",
                   "prints `ratio none`", "`no pair within 1e-09 USD`", "sqrt(n) times `TOLERANCE`", "`no 4-decimal pair`"):
        assert phrase in bullet[0], phrase


# --- the pinned file, only when already cached (one session read, tests/conftest.py) ----------

@pytest.fixture(scope="module")
def output(lrp, llmrouterbench_pinned):
    """The script's lines on the matrix the session fixture wrote from the cached pinned file."""
    code, report, rows = llmrouterbench_pinned
    assert code == 0 and report["rows"] == 156858
    status, out, err = _main(lrp, ["--matrix", str(rows)])
    assert (status, err) == (0, "")
    return out


def test_section_results_block_is_the_script_output(output):
    [text] = _blocks(_section(), "text")
    assert text == COMMAND + "\n" + output


def test_null_counts_are_the_12_18_ones(output):
    lines = output.split("\n")
    assert lines[0] == "12066 items over 9 tasks and 13 models; largest input_tokens 16563"
    assert lines[1] == "null token count: 10 items (hle 5, simpleqa 5), 130 rows; kept 12056 items, 156728 rows"
