"""research/delegation-datasets.md `### Context windows (2026-11-12)` (DESIGN 15 v1.308, row E21a).

The subsection gives each of the LLM Routing Response Bank's five models a context window from a vendor
page, with the open weights' position limit beside it, and a quoted command on the four pinned files.
These tests read the note alone and download nothing: the table, the command's windows and its 13.10
points, and that each number of the bullets is in the command's output or the table.
"""

import ast
import importlib.util
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "research" / "delegation-datasets.md"
README = ROOT / "research" / "README.md"
SECTION = "## LLM Routing Response Bank (2026-11-12)"
HEADING = "### Context windows (2026-11-12)"
COMMAND = "$ python - < response-bank-windows.py"
DEEPSEEK = "https://api-docs.deepseek.com/quick_start/pricing"
# per model: the window, its kind, the vendor page, the Hugging Face repos whose config.json the row pins,
# and the weights' max_position_embeddings
WINDOWS = {
    "deepseek/deepseek-v4-flash": (1000000, "vendor page, for the model that now serves the name", DEEPSEEK,
                                   ["deepseek-ai/DeepSeek-V4-Flash", "deepseek-ai/DeepSeek-V4.1-Flash-1017"], 1048576),
    "deepseek/deepseek-v4-pro": (1000000, "vendor page", DEEPSEEK,
                                 ["deepseek-ai/DeepSeek-V4-Pro", "deepseek-ai/DeepSeek-V4-Pro-0813"], 1048576),
    "moonshotai/kimi-k2.7-code": (262144, "vendor page", "https://platform.moonshot.ai/docs/pricing/chat",
                                  ["moonshotai/Kimi-K2.7-Code"], 262144),
    "z-ai/glm-5.3": (1000000, "vendor page", "https://docs.z.ai/guides/llm/glm-5.3", ["zai-org/GLM-5.3"], 1048576),
    "z-ai/glm-5.3-flash": (1000000, "vendor page", "https://docs.z.ai/guides/llm/glm-5.3-flash",
                           ["zai-org/GLM-5.3-Flash"], 1048576),
}
QUOTES = {
    "moonshotai/kimi-k2.7-code": "\"All K2 series models support a 262,144-token context window.\"",
    "z-ai/glm-5.3": "\"GLM-5.3 currently supports text-only inputs, with a 1M-token context window and a maximum "
                    "output length of 128K tokens.\"",
    "z-ai/glm-5.3-flash": "\"Text parameters are consistent with GLM-5.3, with support for a 1M-token context window.\"",
}


def _subsection():
    note = NOTE.read_text(encoding="utf-8")
    assert note.count("\n" + SECTION + "\n") == 1
    section = note.split("\n" + SECTION + "\n", 1)[1].split("\n## ", 1)[0]
    assert section.count("\n" + HEADING + "\n") == 1
    return section, section.split("\n" + HEADING + "\n", 1)[1]


def _blocks(text, lang):
    return re.findall(rf"^```{lang}\n(.*?)^```$", text, flags=re.M | re.S)


def _table_rows(text):
    return [[c.strip() for c in x.strip("|").split("|")] for x in text.split("\n") if x.startswith("| `")]


def _points():
    spec = importlib.util.spec_from_file_location("delegation_results", ROOT / "evidence" / "delegation" / "results.py")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.points()


def test_subsection_ends_the_response_bank_section():
    section, sub = _subsection()
    assert re.findall(r"^### (.+)$", section, flags=re.M) == [
        "List prices", "Recorded costs", "Recommendation", HEADING[4:]]
    assert sub.isascii() and "\u2013" not in sub and "\u2014" not in sub
    assert sub.rstrip("\n").split("\n")[-1].startswith("- "), "the subsection ends with its recommendation bullets"


def test_table_gives_each_model_a_window_with_its_page_and_weights():
    _, sub = _subsection()
    rows = _table_rows(sub)
    assert [re.fullmatch(r"`([^`]+)`", r[0])[1] for r in rows] == sorted(WINDOWS)
    for row in rows:
        model = row[0].strip("`")
        window, kind, page, repos, limit = WINDOWS[model]
        assert len(row) == 5, row
        assert row[3] == f"{window:,}" and row[4] == kind, row
        assert row[1].startswith(page) and "(2026-11-12" in row[1], row
        for repo in repos:
            assert re.search(rf"https://huggingface\.co/{re.escape(repo)}/raw/[0-9a-f]{{40}}/config\.json", row[1]), (repo, row)
        assert f"max_position_embeddings` {limit}" in row[2], row
        if model in QUOTES:
            assert QUOTES[model] in row[2], row
    assert "redirects (HTTP 301) to https://platform.kimi.ai/docs/pricing/chat" in rows[2][1]


def test_command_reads_the_table_windows_and_the_13_10_points():
    _, sub = _subsection()
    [py] = _blocks(sub, "python")
    [text] = _blocks(sub, "text")
    assert py.isascii()
    [value] = [n.value for n in ast.walk(ast.parse(py)) if isinstance(n, ast.Assign)
               and any(isinstance(t, ast.Name) and t.id == "window" for t in n.targets)]
    assert ast.literal_eval(value) == {m: w[0] for m, w in WINDOWS.items()}
    assert text.startswith(COMMAND + "\n")
    for model in WINDOWS:
        [line] = [x for x in text.split("\n") if x.startswith(f"  {model}: ")]
        assert "; over its window 0;" in line, line
    smallest = min(w[0] for w in WINDOWS.values())
    points = _points()
    lines = [x for x in text.split("\n") if x.startswith("  point ")]
    assert len(lines) == len(points)
    for k, (line, pt) in enumerate(zip(lines, points)):
        C, B = pt["context_tokens"], pt["brief_tokens"]
        m = re.fullmatch(rf"  point {k} \(C {C}, B {B}\): room 262144 -> {262144 - C}, 1000000 -> {1000000 - C}; "
                         r"rule 3 need (\d+), under it 0, margin to the smallest window (\d+) \((\d+\.\d) times the largest "
                         r"S_in \+ S_out\); rule 5 need (\d+), under it 0", line)
        assert m, line
        assert int(m[1]) + int(m[2]) == smallest and int(m[1]) > C and int(m[4]) > B
        work = int(re.search(r"^  largest S_in \+ S_out \(S_in the whole prompt\): (\d+) ", text, flags=re.M)[1])
        assert m[3] == f"{int(m[2]) / work:.1f}" and int(m[1]) == C + work and int(m[4]) == work + B


def _numbers(text):
    return {x.replace(",", "") for x in re.findall(r"\d[\d,]*\d|\d", text)}


def _findings():
    _, sub = _subsection()
    bullets = [x for x in sub.split("\n| Model |", 1)[0].split("\n") if x.startswith("- ")]
    assert len(bullets) == 5
    [text] = _blocks(sub, "text")
    return bullets, text, sub


def test_each_bullet_number_is_in_the_output_or_the_table():
    """Every number of the five bullets, of any length, is in the output or the table (URLs left out)."""
    bullets, text, sub = _findings()
    table = re.sub(r"https://\S+", "", "\n".join("|".join(r) for r in _table_rows(sub)))
    known = _numbers(text) | _numbers(table)
    missing = sorted(n for b in bullets for n in _numbers(b) if n not in known)
    assert not missing, missing


def test_per_model_numbers_are_that_models_output_line():
    """The largest whole call and output a bullet gives a model are the ones on that model's line."""
    bullets, text, _ = _findings()
    line = {m: next(x for x in text.split("\n") if x.startswith(f"  {m}: ")) for m in WINDOWS}
    whole = re.findall(r"(\d+)(?: tokens)? for `([^`]+)` \((?:on )?`(\w+)`\)", bullets[2])
    assert sorted(m for _, m, _ in whole) == sorted(WINDOWS)
    for n, model, family in whole:
        assert f"; largest whole call {n} ({family}); " in line[model], (model, n)
    capped = re.findall(r"The largest `([^`]+)` output is (\d+)(?: tokens)?, on (\d+) responses", bullets[3])
    assert sorted(m for m, _, _ in capped) == ["moonshotai/kimi-k2.7-code", "z-ai/glm-5.3", "z-ai/glm-5.3-flash"]
    for model, n, count in capped:
        assert re.search(rf"; largest output {n} \(\w+\) on {count}; ", line[model]), (model, n, count)
    flash = line["z-ai/glm-5.3-flash"]
    assert "with 72 above 128000 and none above 131072" in bullets[3] and "output over 128,000 72, 131,072 0," in flash
    v4 = re.search(r"; largest output (\d+) \(\w+\) on (\d+); .*, 384,000 (\d+), 393,216 (\d+)$",
                   line["deepseek/deepseek-v4-flash"])
    assert v4[3] == v4[4]
    assert (f"wrote more than 384,000 tokens on {v4[3]} responses (up to {v4[1]}, on {v4[2]})") in bullets[3]
    margins = re.findall(r"margin to the smallest window (\d+) \((\d+\.\d) times", text)
    smallest = min(margins, key=lambda x: int(x[0]))
    assert re.search(rf"the smallest margin, {smallest[0]} tokens under .* at point 2, is {re.escape(smallest[1])} times the largest "
                     r"whole-set S_in \+ S_out, (\d+) on `aime`", bullets[4])


def test_research_readme_names_the_subsection():
    text = README.read_text(encoding="utf-8")
    assert "the LLM Routing Response Bank section of delegation-datasets.md and its context windows on 2026-11-12." in text
    [row] = [x for x in text.split("\n") if x.startswith("| [delegation-datasets.md](delegation-datasets.md) |")]
    assert ("its context-windows subsection of the same day gives each of the five a window from a vendor page "
            "(1M for four, 262,144 for the fifth); no recorded response exceeds its model's window") in row
