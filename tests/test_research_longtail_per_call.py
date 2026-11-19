"""Longtail-SWE per call, under a stated split of each run's totals (DESIGN 13.16 v1.496, row R50b):
research/longtail-per-call.md and its script research/longtail_per_call.py. CI has neither `pyarrow` nor the four pinned
files, so the test that runs the script on them skips there; the others use hand cases, the note, DESIGN.md and
research/README.md."""
import importlib.util
import re
from pathlib import Path

import pytest

from model_routing.delegation_eval import _calls

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "research" / "longtail-per-call.md"
SCRIPT = ROOT / "research" / "longtail_per_call.py"
DESIGN = ROOT / "DESIGN.md"
RESEARCH_README = ROOT / "research" / "README.md"
BULLET = "- Longtail-SWE per call, under a stated split of each run's totals (v1.496, row R50b): "
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")
SECTIONS = ("Facts", "Method", "Results", "Reading it", "Recommendation")
SOL61 = "openai/gpt-6.1-sol"


def load():
    if not SCRIPT.is_file():
        raise FileNotFoundError(f"no script at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("longtail_per_call_for_tests", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


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


def test_design_13_16_specifies_the_note():
    design = DESIGN.read_text(encoding="utf-8")
    lines = [line for line in design.split("\n") if line.startswith(BULLET)]
    assert len(lines) == 1
    r50 = design.index("\n- Longtail-SWE as delegation evidence, on nebius/Longtail-SWE-trajectories (v1.495, row R50): ")
    assert design.index("\n### 13.16 ") < r50 < design.index(lines[0]) < design.index("\n### 13.17 ")
    for phrase in ("`research/longtail-per-call.md` and its script `research/longtail_per_call.py`",
                   "an assumption the release cannot check", "call 1 also O % K",
                   "the remainder r = L % T going r // K to call 1 and r % K to call K",
                   "A run with L below 0 is refused and its item dropped for all four models, both counted",
                   "It exits 2 if the harness refuses the split rows",
                   "No results file, package, README or workflow change"):
        assert phrase in lines[0], phrase
    assert "\u2013" not in lines[0] and "\u2014" not in lines[0]


def test_research_readme_lists_the_note():
    note()  # FileNotFoundError until the note exists
    text = RESEARCH_README.read_text(encoding="utf-8")
    assert text.count("| [longtail-per-call.md](longtail-per-call.md) | ") == 1
    assert text.count("[longtail_per_call.py](longtail_per_call.py)") == 1
    assert text.count("\n- `research/longtail-per-call.md` ") == 1


@pytest.mark.parametrize("tin, tout, calls, ins, outs", [
    (100, 10, 3, [15, 14, 16], [4, 3, 3]),   # L = 100 - (2 * 4 + 3) = 89, T = 6, a = 14, r = 5: 1 to call 1, 2 to call 3
    (50, 7, 1, [50], [7]),                    # one call reads the whole input
    (11, 10, 3, [0, 0, 0], [4, 3, 3]),        # L = 0: every read is a re-read of an earlier output
    (30, 0, 4, [3, 3, 3, 3], [0, 0, 0, 0]),   # T = 10, a = 3, r = 0
    (39, 4, 4, [3, 3, 3, 6], [1, 1, 1, 1]),   # L = 39 - 6 = 33, T = 10, a = 3, r = 3: 0 to call 1, 3 to call 4
    (47, 4, 4, [4, 4, 4, 5], [1, 1, 1, 1]),   # L = 41, T = 10, a = 4, r = 1: 0 to call 1, 1 to call 4
])
def test_split_on_hand_cases(tin, tout, calls, ins, outs):
    m = load()
    got = m.split(tin, tout, calls)
    assert got == (ins, outs)
    k, rd, a, o, a_calls, b_calls = _calls({"input_tokens": tin, "output_tokens": tout,
                                             "call_input_tokens": got[0], "call_output_tokens": got[1]})
    assert (k, rd, o, list(a_calls), list(b_calls)) == (calls, tin, tout, got[0], got[1])
    assert all(type(x) is int and x >= 0 for x in got[0] + got[1])


def test_split_reads_the_totals_by_brute_force():
    m = load()
    for calls in (1, 2, 3, 5, 8, 13, 38):
        for tout in (0, 1, calls - 1, calls, 7 * calls + 3, 1001):
            least = sum((calls - 1 - j) * b for j, b in enumerate(m.split(10 ** 9, tout, calls)[1]))
            for tin in (least, least + 1, least + calls * (calls + 1) // 2 - 1, least + 12345, 2568100 + least):
                ins, outs = m.split(tin, tout, calls)
                reads = sum(sum(ins[:j + 1]) + sum(outs[:j]) for j in range(calls))
                assert (reads, sum(outs), len(ins)) == (tin, tout, calls)
                assert max(outs) - min(outs) <= tout % calls and outs[1:] == [tout // calls] * (calls - 1)
            if least:
                assert m.split(least - 1, tout, calls) is None


@pytest.mark.parametrize("bad", [(10, 5, 0), (10, 5, True), (-1, 5, 2), (10, -5, 2), (10.0, 5, 2)])
def test_split_refuses_a_bad_count(bad):
    with pytest.raises(ValueError, match="must be"):
        load().split(*bad)


def kept_row(item, model, tin, tout, calls, correct=True):
    row = {"task": "t", "item": item, "model": model, "correct": correct, "input_tokens": tin, "output_tokens": tout}
    return row, {"brief": 1, "result": 1, "input": tin, "output": tout, "calls": calls, "usage_events": 0}


def test_per_call_rows_drop_a_refused_item_for_every_model():
    m = load()
    kept = [kept_row("i0", "a/x", 100, 10, 3), kept_row("i0", "b/y", 100, 10, 3),
            kept_row("i1", "a/x", 5, 10, 3), kept_row("i1", "b/y", 100, 10, 3), kept_row("i2", "a/x", 50, 7, 1),
            kept_row("i2", "b/y", 11, 10, 3)]
    rows, refused, dropped = m.per_call(kept)
    assert (refused, dropped) == (1, ["i1"])
    assert [(r["item"], r["model"]) for r in rows] == [("i0", "a/x"), ("i0", "b/y"), ("i2", "a/x"), ("i2", "b/y")]
    assert rows[0]["call_input_tokens"] == [15, 14, 16] and rows[0]["call_output_tokens"] == [4, 3, 3]
    assert rows[3]["call_input_tokens"] == [0, 0, 0]
    assert all(_calls(r) is not None for r in rows)


def test_note_has_its_sections_and_no_dataset_text():
    text = note()
    heads = [line[3:] for line in text.split("\n") if line.startswith("## ")]
    assert heads == list(SECTIONS)
    assert "\u2013" not in text and "\u2014" not in text
    for phrase in ("dfd6075c56b7841b9c254cc70a57e39c1df0076c", "CC BY 4.0", "[longtail_per_call.py](longtail_per_call.py)",
                   "[longtail-delegation.md](longtail-delegation.md)", "an assumption"):
        assert phrase in text, phrase
    for marker in ("diff --git", "@@ ", "```diff", "\n+++ ", "\n--- a/"):
        assert marker not in text, marker


def test_prose_numbers_are_in_the_block():
    text = note()
    block = set(NUMBER.findall(results_block(text)))
    prose = section(text, "Reading it") + section(text, "Recommendation") + next(
        line for line in text.split("\n") if line.startswith("- Short answer: "))
    allowed = {"4", "13.2", "13.3", "13.4", "13.5", "13.9", "12.25", "12.26", "4.1", "1.74"}
    missing = sorted(set(NUMBER.findall(prose)) - block - allowed)
    assert not missing, missing


def test_bad_option_exits_2_with_one_error_line(capsys):
    assert load().main(["--bogus"]) == 2
    err = capsys.readouterr().err.strip().split("\n")
    assert len(err) == 1 and err[0].startswith("error: ")


def test_note_results_block_is_a_fresh_run(capsys):
    pytest.importorskip("pyarrow")
    m = load()
    cache = m.LD.CONVERT.default_cache_dir()
    if not all((cache / name).is_file() for name in m.LD.CONVERT.FILES):
        pytest.skip("the four pinned Longtail-SWE files are not cached")
    assert m.main([]) == 0
    assert capsys.readouterr().out == results_block(note())
