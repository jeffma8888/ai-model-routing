"""research/no-path-clears.md and research/no_path_clears.py (DESIGN 13.8 v1.86).

The note's numbers are the script's output on the three committed delegation runs, compared byte
for byte when the pinned AutoBench and tau2-bench files are already in the default cache (CI never
downloads them). The script's tables and its rebuild of a 13.5 row 7 decision are checked on small
matrices, one with per-call rows (13.9 v1.74) and one without.

DESIGN 13.8 v1.338 (row R30): the script also reruns the LLMRouterBench (13.13) and response-bank
(13.14) delegation runs, each checked against its committed results.json, and prints one line per
bar in each flavor's block; the note gains a dated section on the two runs, and the cached-file
tests also need their pinned files.
"""

import contextlib
import importlib.util
import io
import json
import re
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "no_path_clears.py"
NOTE = ROOT / "research" / "no-path-clears.md"
INDEX = ROOT / "research" / "README.md"
README = ROOT / "README.md"
COMMAND = ("$ python research/no_path_clears.py --autobench autobench-tokens.jsonl "
           "--autobench-registry autobench-pool.json --tau2 tau2-calls.jsonl --tau2-pooled tau2-calls-all.jsonl "
           "--llmrouterbench llmrouterbench-matrix.jsonl --response-bank response-bank-matrix.jsonl")
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens "
    "--registry autobench-pool.json",
    "python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls",
    "python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all",
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl",
    "python evidence/response-bank/convert.py --out response-bank-matrix.jsonl",
    COMMAND[2:],
]
LIMITATION = (
    "- When neither path clears the bar, a task whose `on_no_model` is `best_available` still decides "
    "(`DESIGN.md` 13.5 row 7, reason `none_clear`, `below_bar` true), by the calibration bounds and not by "
    "cost, while the default, `refuse`, raises `NoModelClearsBar`. On the committed tau2-bench delegation "
    "runs row 7 decides most `cost_effective` cells, and the path it takes has a held-out success below the "
    "bar on most of them; [research/no-path-clears.md](research/no-path-clears.md) measures it on the five "
    "committed delegation runs of four datasets, AutoBench, tau2-bench, LLMRouterBench and the LLM Routing "
    "Response Bank, and recommends keeping the rule")
LABELS = ("AutoBench (13.10 results.json)", "tau2-bench per domain (13.12 results.json)",
          "tau2-bench pooled (13.12 pooled.json)", "LLMRouterBench (13.13 results.json)",
          "LLM Routing Response Bank (13.14 results.json)")
SECTION = "LLMRouterBench and the response bank (2026-11-13)"
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
# v1.338: the response bank's registry, for a small matrix its script's select_rows keeps
BANK_REGISTRY = ROOT / "evidence" / "response-bank-delegation" / "registry.json"
RED = pytest.mark.xfail(strict=True, reason="v1.338 (row R30): implemented by v1.339")
# Section and row numbers of DESIGN.md, and the runs' 50 seeds: the only numbers of the note's
# prose that are not in the script's output
ALLOWED = {"13.5", "13.9", "13.10", "13.12", "13.13", "13.14", "3", "4", "6", "7", "50"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?%?")
POINT = {"context_tokens": 8000, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
         "inline_separate_call": True}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def npc():
    return _load("research_no_path_clears", SCRIPT)


def registry():
    return Registry([
        Model(id="v/strong", family="S", price_in=3.0, price_out=12.0, context_window=1_000_000),
        Model(id="v/cheap", family="C", price_in=0.1, price_out=0.4, context_window=1_000_000)])


def tiny(per_call=False):
    """80 items on which neither model clears a bar of 0.8 (64 and 53 correct), so every cell is row 7."""
    rows = []
    for i in range(80):
        for model, correct, scale in (("v/strong", i % 5 != 0, 3), ("v/cheap", i % 3 != 0, 2)):
            row = {"task": "all", "item": f"q{i}", "model": model, "correct": correct}
            if per_call:
                a = [300 + i] + [20 + scale * (i % 7)] * (1 + (i + scale) % 3)
                b = [40 + scale * (i % 5)] * len(a)
                k = len(a)
                row["input_tokens"] = sum((k - j) * a[j] + (k - j - 1) * b[j] for j in range(k))
                row["output_tokens"] = sum(b)
                row["call_input_tokens"], row["call_output_tokens"] = a, b
            else:
                row["input_tokens"], row["output_tokens"] = 200 + i, 700 + scale * i
            rows.append(row)
    return rows


def bar_line(cells, bar, total):
    """The v1.338 per-bar line of one flavor's cells."""
    hit = [c for c in cells if c["bar"] == bar and c["reason"] == "none_clear"]
    line = f"    bar {bar}: none_clear on {len(hit):,} of {total:,} cells"
    if hit:
        met = sum(c["success"]["decision"] >= bar for c in hit)
        line += f", the decision's held-out success at the bar or above on {met:,} ({met / len(hit):.1%})"
    return line


@RED
@pytest.mark.parametrize("per_call", [False, True])
def test_report_scores_each_path_on_the_row_7_cells(npc, per_call):
    rows, reg = tiny(per_call), registry()
    result = evaluate_delegation(rows, reg, bars=[0.8], points=[POINT], seeds=range(4))
    cells = result["cells"]
    assert cells and {c["reason"] for c in cells} == {"none_clear"}
    lines = npc.report("tiny", rows, reg, result)
    assert lines[0] == "tiny: 16 cells, bars 0.8"
    assert lines[1] == "  cost_effective: none_clear on 8 of 8 cells (100.0%)"
    blind = lines.index("  cost_blind: none_clear on 8 of 8 cells (100.0%)")
    effective, rest = lines[2:blind], lines[blind + 1:]
    held = sum(c["held_out_items"] for c in cells if c["flavor"] == "cost_blind")
    for flavor, block in (("cost_effective", effective), ("cost_blind", rest)):
        mine = [c for c in cells if c["flavor"] == flavor]
        delegated = sum(c["mode"] == "delegate" for c in mine)
        assert block[0] == bar_line(mine, 0.8, 8)
        assert block[1] == (f"    decision delegates on {delegated:,} and works inline on {8 - delegated:,}; "
                            f"{held:,} held-out items")
        for strategy in ("decision", "inline", "delegate"):
            line = next(x for x in block if x.startswith(f"    {strategy:<8}  success "))
            success = sum(c["correct"][strategy] for c in mine) / held
            assert line.startswith(f"    {strategy:<8}  success {success:.3f}  cost per item ")
    assert any(x.startswith("    cheaper   success ") for x in effective)
    assert any(x.startswith("    cheaper against decision: success ") for x in effective)
    assert not any("cheaper" in x for x in rest)
    assert effective[-1].startswith("    decision's held-out success at least the better path's on ")


@RED
def test_report_gives_one_line_per_bar_after_the_share(npc):
    rows, reg = tiny(), registry()
    result = evaluate_delegation(rows, reg, bars=[0.5, 0.8], points=[POINT], seeds=range(4))
    lines = npc.report("t", rows, reg, result)
    for flavor in ("cost_effective", "cost_blind"):
        mine = [c for c in result["cells"] if c["flavor"] == flavor]
        row7 = [c for c in mine if c["reason"] == "none_clear"]
        assert 0 < len(row7) < len(mine)
        k = lines.index(f"  {flavor}: none_clear on {len(row7):,} of {len(mine):,} cells "
                        f"({len(row7) / len(mine):.1%})")
        per_bar = [bar_line(mine, bar, sum(c["bar"] == bar for c in mine)) for bar in (0.5, 0.8)]
        assert lines[k + 1:k + 3] == per_bar
        assert per_bar[0] == f"    bar 0.5: none_clear on 0 of {len(mine) // 2:,} cells"
        assert lines[k + 3].startswith("    decision delegates on ")


def test_report_prints_only_the_share_when_no_cell_is_row_7(npc):
    rows, reg = tiny(), registry()
    result = evaluate_delegation(rows, reg, bars=[0.5], points=[POINT], seeds=range(2))
    assert "none_clear" not in {c["reason"] for c in result["cells"]}
    assert npc.report("t", rows, reg, result) == [
        "t: 8 cells, bars 0.5", "  cost_effective: none_clear on 0 of 4 cells (0.0%)",
        "  cost_blind: none_clear on 0 of 4 cells (0.0%)"]


@pytest.mark.parametrize("per_call", [False, True])
def test_rebuild_is_the_cells_decision_and_refuses_a_changed_cell(npc, per_call):
    rows, reg = tiny(per_call), registry()
    result = evaluate_delegation(rows, reg, bars=[0.8], points=[POINT], seeds=range(4))
    cache = {}
    for cell in result["cells"]:
        decision = npc.rebuild(rows, reg, result, cell, cache)
        assert (decision.mode, decision.model, decision.reason) == (cell["mode"], cell["model"], cell["reason"])
        assert decision.below_bar
    cell = dict(result["cells"][0], mode="inline" if result["cells"][0]["mode"] == "delegate" else "delegate")
    with pytest.raises(AssertionError):
        npc.rebuild(rows, reg, result, cell, cache)


def bank_rows(items=40):
    """A small single-call matrix of the five registry models of 13.14, one task."""
    rows = []
    for k, model in enumerate(m.id for m in Registry.load(BANK_REGISTRY).models):
        for i in range(items):
            rows.append({"task": "gpqa_diamond", "item": f"q{i}", "model": model, "correct": (i + k) % 4 != 0,
                         "input_tokens": 300 + i, "output_tokens": 900 + 7 * k})
    return rows


@RED
def test_rerun_selected_refuses_a_run_that_is_not_the_committed_file(npc, tmp_path):
    path = tmp_path / "bank.jsonl"
    path.write_text("".join(json.dumps(r) + "\n" for r in bank_rows()), encoding="utf-8")
    with pytest.raises(ValueError, match=r"^the rerun is not evidence/response-bank-delegation/results\.json$"):
        npc.rerun_selected(str(path), "response-bank-delegation", "r30_bank_small")


@RED
def test_main_prints_nothing_to_stdout_when_a_rerun_is_refused(npc, monkeypatch, capsys):
    monkeypatch.setattr(npc, "read_rows", lambda path: [])
    monkeypatch.setattr(npc.Registry, "load", staticmethod(lambda path: None))
    monkeypatch.setattr(npc, "evaluate_delegation", lambda *a, **k: {})
    monkeypatch.setattr(npc, "report", lambda label, *a: [label])
    seen = []

    def refuse(path, folder, name):
        seen.append(folder)
        if folder == "response-bank-delegation":
            raise ValueError(f"the rerun is not evidence/{folder}/results.json")
        return [], None, {}

    monkeypatch.setattr(npc, "rerun_selected", refuse)
    code = npc.main(["--autobench", "a", "--autobench-registry", "b", "--tau2", "c", "--tau2-pooled", "d",
                     "--llmrouterbench", "e", "--response-bank", "f"])
    out, err = capsys.readouterr()
    assert code == 1 and out == ""
    assert err == "error: the rerun is not evidence/response-bank-delegation/results.json\n"
    assert seen == ["llmrouterbench-delegation", "response-bank-delegation"]


def test_script_is_standard_library_and_model_routing(npc):
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^(?:from|import) ([\w.]+)", text, flags=re.M)}
    assert imports <= {"__future__", "argparse", "importlib", "json", "math", "statistics", "sys",
                       "collections", "pathlib", "model_routing"}
    assert text.isascii()


def _sections(text):
    return re.findall(r"^## (.+)$", text, flags=re.M)


def _blocks(text, lang):
    return re.findall(rf"^```{lang}\n(.*?)^```$", text, flags=re.M | re.S)


@RED
def test_note_quotes_its_commands():
    note = NOTE.read_text(encoding="utf-8")
    assert note.startswith("# When neither path clears the bar\n")
    assert _sections(note) == ["Facts", "Method", "Results", "Reading it", SECTION, "Recommendation", "Limits",
                               "Regenerate"]
    assert _blocks(note, "bash") == ["\n".join(REGENERATE) + "\n"]
    [text] = _blocks(note, "text")
    assert text.startswith(COMMAND + "\n")
    assert note.isascii() and "\u2013" not in note and "\u2014" not in note
    for link in ("../DESIGN.md", "../evidence/delegation/RESULTS.md",
                 "../evidence/tau2-bench-delegation/RESULTS.md", "../evidence/llmrouterbench-delegation/RESULTS.md",
                 "../evidence/response-bank-delegation/RESULTS.md", "no_path_clears.py"):
        assert f"]({link})" in note


def test_every_number_of_the_prose_is_in_the_output_or_allowed():
    note = NOTE.read_text(encoding="utf-8")
    [text] = _blocks(note, "text")
    prose = DATE.sub("", re.sub(r"^```\w*\n.*?^```$", "", note, flags=re.M | re.S))
    printed = set(NUMBER.findall(text))
    missing = sorted({n for n in NUMBER.findall(prose) if n not in printed and n not in ALLOWED})
    assert missing == []


@RED
def test_readme_limitations_and_research_index_link_the_note():
    readme = README.read_text(encoding="utf-8")
    limits = readme[readme.index("## Limitations and non-goals (v1)\n"):readme.index("\n## Layout\n")]
    assert "\n" + LIMITATION + "\n" in limits
    two = limits.index("\n- The delegation evidence reads four datasets")
    assert two < limits.index("\n" + LIMITATION + "\n")
    index = INDEX.read_text(encoding="utf-8")
    assert "| [no-path-clears.md](no-path-clears.md) | " in index


# --- the pinned files, only when already cached ------------------------------------------------

@pytest.fixture(scope="module")
def output(tmp_path_factory, llmrouterbench_pinned, response_bank_pinned):
    """The script's stdout on the five runs' matrices, rebuilt in process from the cached files (the
    LLMRouterBench and response-bank matrices are the session fixtures' converter output, v1.338)."""
    ab = _load("r5_autobench_convert", ROOT / "evidence" / "autobench-2026" / "convert.py")
    t2 = _load("r5_tau2_convert", ROOT / "evidence" / "tau2-bench" / "convert.py")
    a_dir, t_dir = ab.default_cache_dir(), t2.default_cache_dir()
    if not all((a_dir / n).is_file() for n in ab.FILES) or not all((t_dir / n).is_file() for n in t2.FILES):
        pytest.skip("the pinned AutoBench and tau2-bench files are not in the default cache")
    for name, (size, sha) in ab.FILES.items():
        ab.verify(a_dir / name, size, sha)
    params = json.loads((a_dir / "frozen_params.json").read_text(encoding="utf-8"))
    pool = json.loads((a_dir / "pool.json").read_text(encoding="utf-8"))
    ab_rows, _ = ab.convert(ab.read_csv(a_dir / "matrix.csv"), ab.read_csv(a_dir / "questions.csv"), pool,
                            params["delta_signal"], params["top_k"], task_by="all", tokens=True)
    extracts = []
    for name, (size, sha) in t2.FILES.items():
        t2.verify(t_dir / name, size, sha)
        extracts.append(t2.extract(t2.read_run(t_dir / name), trial=0, tokens=True, calls=True))
    out = tmp_path_factory.mktemp("r5")
    files = {"autobench": ab_rows, "tau2": t2.convert(extracts)[0], "tau2-pooled": t2.convert(extracts, "all")[0]}
    for key, rows in files.items():
        (out / f"{key}.jsonl").write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    (out / "pool.json").write_text(json.dumps(ab.pool_registry(pool)), encoding="utf-8")
    lrb_code, _report, lrb_path = llmrouterbench_pinned
    bank_code, _out, bank_err, bank_path = response_bank_pinned
    assert lrb_code == 0 and bank_code == 0, bank_err
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = _load("r5_script", SCRIPT).main([
            "--autobench", str(out / "autobench.jsonl"), "--autobench-registry", str(out / "pool.json"),
            "--tau2", str(out / "tau2.jsonl"), "--tau2-pooled", str(out / "tau2-pooled.jsonl"),
            "--llmrouterbench", str(lrb_path), "--response-bank", str(bank_path)])
    assert code == 0
    return buf.getvalue()


def runs(output):
    """The output split into its five runs, by label (v1.338)."""
    starts = [output.index(label + ": ") for label in LABELS]
    assert starts == sorted(starts) and starts[0] == 0
    return {label: output[a:b] for label, a, b in zip(LABELS, starts, starts[1:] + [len(output)])}


@RED
def test_note_results_block_is_the_script_output(output):
    [text] = _blocks(NOTE.read_text(encoding="utf-8"), "text")
    assert text == COMMAND + "\n" + output


@RED
def test_output_backs_the_readme_bullet(output):
    by_label = runs(output)
    assert by_label[LABELS[0]].startswith("AutoBench (13.10 results.json): 16,000 cells")
    for run in (by_label[LABELS[1]], by_label[LABELS[2]]):
        effective = run[run.index("  cost_effective: "):run.index("  cost_blind: ")]
        share = float(re.search(r"cells \((\d+\.\d)%\)", effective).group(1))
        met = float(re.search(r"    decision  success .* on [\d,]+ \((\d+\.\d)%\)", effective).group(1))
        assert share > 50 and met < 50


@RED
@pytest.mark.parametrize("label, folder", [(LABELS[3], "llmrouterbench-delegation"),
                                           (LABELS[4], "response-bank-delegation")])
def test_new_runs_row_7_counts_are_the_results_md_ones(output, label, folder):
    run = runs(output)[label]
    effective = run[run.index("  cost_effective: "):run.index("  cost_blind: ")]
    got = re.search(r"none_clear on ([\d,]+) of ([\d,]+) cells", effective).groups()
    results = (ROOT / "evidence" / folder / "RESULTS.md").read_text(encoding="utf-8")
    total = re.search(r"^- Of the ([\d,]+) `cost_effective` cells, (.*)$", results, flags=re.M)
    assert total.group(1) == got[1]
    assert re.search(rf"\b{got[0]} `none_clear`", total.group(2))
    bars = re.findall(r"^    bar [\d.]+: none_clear on ([\d,]+) of ([\d,]+) cells", effective, flags=re.M)
    assert sum(int(n.replace(",", "")) for n, _ in bars) == int(got[0].replace(",", ""))
    assert sum(int(m.replace(",", "")) for _, m in bars) == int(got[1].replace(",", ""))
