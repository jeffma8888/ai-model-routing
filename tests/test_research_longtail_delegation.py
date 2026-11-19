"""Longtail-SWE as delegation evidence (DESIGN 13.16 v1.495, row R50): research/longtail-delegation.md and its
script research/longtail_delegation.py. CI has neither `pyarrow` nor the four pinned files, so the test that runs
the script on them skips there; the others use hand-made rows, the note, DESIGN.md and research/README.md."""
import importlib.util
import json
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "research" / "longtail-delegation.md"
SCRIPT = ROOT / "research" / "longtail_delegation.py"
DESIGN = ROOT / "DESIGN.md"
RESEARCH_README = ROOT / "research" / "README.md"
BULLET = "- Longtail-SWE as delegation evidence, on nebius/Longtail-SWE-trajectories (v1.495, row R50): "
NUMBER = re.compile(r"(?<![\w.])\d+(?:[.,]\d+)*")
SECTIONS = ("Facts", "Method", "Results", "Reading it", "Recommendation")
SOL61 = "openai/gpt-6.1-sol"


def load():
    if not SCRIPT.is_file():
        raise FileNotFoundError(f"no script at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("longtail_delegation_for_tests", SCRIPT)
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


def trajectory(prompts, calls=3, tin=100, tout=20, events=()):
    return json.dumps({"prompts": prompts, "events": list(events),
                       "usage": {"model_calls": calls, "tokens": {"input": tin, "cached_input": 0, "cache_creation": None,
                                                                  "output": tout, "total": tin + tout}}})


SYSTEM, USER = {"role": "system", "content": "s" * 99}, {"role": "user", "content": "u" * 10}


def test_design_13_16_specifies_the_note():
    design = DESIGN.read_text(encoding="utf-8")
    lines = [line for line in design.split("\n") if line.startswith(BULLET)]
    assert len(lines) == 1
    assert design.index("\n### 13.16 ") < design.index(lines[0]) < design.index("\n### 13.17 ")
    for phrase in ("`research/longtail-delegation.md` and its script `research/longtail_delegation.py`",
                   "Columns read: the converter's `COLUMNS` and `model_patch`",
                   "a size in tokens is its characters over 4, rounded up",
                   "no statement, message, patch or other dataset text is printed, kept or committed",
                   "it exits 2 if the harness scores those rows", "(row R50b)"):
        assert phrase in lines[0], phrase
    assert "\u2013" not in lines[0] and "\u2014" not in lines[0]


def test_research_readme_lists_the_note():
    note()  # FileNotFoundError until the note exists
    text = RESEARCH_README.read_text(encoding="utf-8")
    assert text.count("| [longtail-delegation.md](longtail-delegation.md) | ") == 1
    assert text.count("[longtail_delegation.py](longtail_delegation.py)") == 1
    assert text.count("\n- `research/longtail-delegation.md` ") == 1


def test_size_rule_on_hand_cases():
    m = load()
    assert m.CHARS == 4
    assert [m.size(s) for s in ("", "a", "abcd", "abcde", "x" * 4000, "\u00e9" * 5)] == [0, 1, 1, 2, 1000, 2]
    for bad in (None, 3, b"abcd"):
        with pytest.raises(ValueError, match="not a string"):
            m.size(bad)


def test_counts_keep_sizes_and_counts_only():
    m = load()
    events = [{"seq": 0, "messages": [{"role": "assistant", "content": "x"}]},
              {"seq": 1, "usage": {}, "messages": [{"tokens": 3}, {"role": "tool"}]}, {"seq": 2}]
    got = m.counts({"trajectory": trajectory([SYSTEM, USER], events=events), "model_patch": "p" * 9})
    assert got == {"brief": 3, "result": 3, "input": 100, "output": 20, "calls": 3, "usage_events": 2}
    assert all(type(v) is int for v in got.values())
    assert m.counts({"trajectory": trajectory([USER]), "model_patch": ""})["result"] == 0


@pytest.mark.parametrize("row, case", [
    ({"trajectory": "{", "model_patch": ""}, "trajectory is not JSON"),
    ({"trajectory": trajectory([SYSTEM, USER, USER]), "model_patch": ""}, "2 user prompts, not one"),
    ({"trajectory": trajectory([SYSTEM]), "model_patch": ""}, "0 user prompts, not one"),
    ({"trajectory": trajectory([SYSTEM, USER], calls=0), "model_patch": ""}, "model_calls 0 is not an int >= 1"),
    ({"trajectory": trajectory([SYSTEM, USER], calls=True), "model_patch": ""}, "model_calls True is not an int >= 1"),
    ({"trajectory": trajectory([SYSTEM, USER]), "model_patch": None}, "not a string"),
    ({"trajectory": trajectory([SYSTEM, {"role": "user", "content": None}]), "model_patch": ""}, "not a string"),
    ({"trajectory": trajectory([SYSTEM, USER], tin=5, tout=1).replace('"total": 6', '"total": 7'), "model_patch": ""},
     "token total 7 is not input + output"),
])
def test_counts_refuse_a_bad_run(row, case):
    with pytest.raises(ValueError, match=re.escape(case)):
        load().counts(row)


def hand_rows(tokens):
    return [{"task": "t", "item": f"i{n}", "model": SOL61, "correct": n % 2 == 0, "input_tokens": tokens,
             "output_tokens": 10} for n in range(8)]


CONFIG = {"seeds": [0], "flavors": ["cost_effective"], "calibration_fraction": 0.5, "min_samples": 1, "confidence": 0.95}


def test_refusal_gives_the_harness_message_and_refuses_scored_rows():
    from model_routing import Registry
    m = load()
    registry = Registry.load(ROOT / "model_routing" / "data" / "models.json")
    window = registry.get(SOL61).context_window
    points = m.points(100, 100)
    assert [(p["context_tokens"], p["inline_separate_call"], p["carry_turns"]) for p in points] == [
        (8000, True, 1), (64000, True, 1), (200000, True, 1), (8000, False, 1)]
    message = m.refusal(hand_rows(window + 1), registry, CONFIG, points)
    assert message.startswith("no model fits the delegated work: task 't', parent 'openai/gpt-6.1-sol', point 0")
    with pytest.raises(ValueError, match="the 13.9 harness scored the one-call rows"):
        m.refusal(hand_rows(1000), registry, CONFIG, points)


def test_note_has_its_sections_and_no_dataset_text():
    text = note()
    heads = [line[3:] for line in text.split("\n") if line.startswith("## ")]
    assert heads == list(SECTIONS)
    assert "\u2013" not in text and "\u2014" not in text
    for phrase in ("dfd6075c56b7841b9c254cc70a57e39c1df0076c", "CC BY 4.0", "[longtail_delegation.py](longtail_delegation.py)",
                   "characters over 4, rounded up"):
        assert phrase in text, phrase
    for marker in ("diff --git", "@@ ", "```diff", "\n+++ ", "\n--- a/"):
        assert marker not in text, marker


def test_prose_numbers_are_in_the_block():
    text = note()
    block = set(NUMBER.findall(results_block(text)))
    prose = section(text, "Reading it") + section(text, "Recommendation") + next(
        line for line in text.split("\n") if line.startswith("- Short answer: "))
    allowed = {"4", "13.2", "13.3", "13.4", "13.5", "13.9", "12.25", "12.26", "4.1"}
    missing = sorted(set(NUMBER.findall(prose)) - block - allowed)
    assert not missing, missing


SPREAD = r"median ([\d,]+), 10th to 90th percentile ([\d,]+) to ([\d,]+)"
MODEL_ROW = re.compile(r"^(\S+/\S+) +([\d,]+) +(\d+) of (\d+) +([\d,]+) +(\d+) +([\d,]+)$", re.M)


def keyed(block):
    """The block's statistics keyed by what they describe (review iter-352 should-fix 1)."""
    def spread(label):
        found = re.findall(re.escape(label) + ": " + SPREAD, block)
        assert len(found) == 1, label
        return found[0]
    rows = {m: dict(zip(("window", "over", "rows", "input", "calls", "per_call"), rest))
            for m, *rest in MODEL_ROW.findall(block)}
    empty = re.findall(r"model_patch: " + SPREAD + r"; (\d+) empty", block)
    assert len(rows) == 4 and len(empty) == 1
    return {"brief": spread("brief, the run's user prompt"), "result": spread("result, the run's model_patch"),
            "input": spread("run input tokens"), "output": spread("run output tokens"),
            "calls": spread("model calls a run"), "empty": empty[0][3], "models": rows,
            "events": re.findall(r"all ([\d,]+) runs of the four files: (\d+)", block)[0]}


def test_reading_numbers_describe_their_rows():
    text = note()
    k = keyed(results_block(text))
    short = next(line for line in text.split("\n") if line.startswith("- Short answer: "))
    reading = section(text, "Reading it")
    overs = sorted(int(r["over"]) for r in k["models"].values())
    rows = {r["rows"] for r in k["models"].values()}
    assert len(rows) == 1
    per_call = sorted((int(r["per_call"].replace(",", "")) for r in k["models"].values()))
    for phrase in (f"model calls (median {k['calls'][0]})", f"on {overs[0]} to {overs[-1]} of each model's {rows.pop()} rows",
                   f"({k['events'][1]} usage or tokens keys on its events)",
                   f"a median {k['brief'][0]} and {k['result'][0]} tokens"):
        assert phrase in short, phrase
    for phrase in (f"the user prompt is a median {k['brief'][0]} tokens (10th to 90th percentile {k['brief'][1]} to "
                   f"{k['brief'][2]})", f"the patch a median {k['result'][0]} ({k['result'][1]} to {k['result'][2]}), with "
                   f"{k['empty']} empty patch", f"a median {k['calls'][0]} model calls ({k['calls'][1]} to {k['calls'][2]})",
                   f"input total a median {k['input'][0]} tokens ({k['input'][1]} to {k['input'][2]})",
                   f"against a median {k['output'][0]} output tokens", f"like the {k['input'][0]} above",
                   f"a median of {per_call[0]:,} to {per_call[-1]:,} tokens by model",
                   f"{k['events'][1]} of the events, or of their messages, carry a usage or tokens key, over all "
                   f"{k['events'][0]} runs"):
        assert phrase in reading, phrase
    for model, r in k["models"].items():
        assert f"{r['over']} (`{model}`)" in reading, model
    windows = sorted({r["window"] for r in k["models"].values()})
    assert f"context window, {' or '.join(windows)} tokens" in reading


def test_keyed_reading_fails_on_swapped_counts():
    text = note()
    swapped = text.replace("154 (`anthropic/claude-opus-5.5`)", "@@").replace("111 (`openai/gpt-6.1-sol`)", "154 (`openai/gpt-6.1-sol`)").replace("@@", "111 (`anthropic/claude-opus-5.5`)")
    assert swapped != text
    k = keyed(results_block(swapped))
    reading = section(swapped, "Reading it")
    assert any(f"{r['over']} (`{m}`)" not in reading for m, r in k["models"].items())


def test_bad_option_exits_2_with_one_error_line(capsys):
    assert load().main(["--bogus"]) == 2
    err = capsys.readouterr().err.strip().split("\n")
    assert len(err) == 1 and err[0].startswith("error: ")


def test_note_results_block_is_a_fresh_run(capsys):
    pytest.importorskip("pyarrow")
    m = load()
    cache = m.CONVERT.default_cache_dir()
    if not all((cache / name).is_file() for name in m.CONVERT.FILES):
        pytest.skip("the four pinned Longtail-SWE files are not cached")
    assert m.main([]) == 0
    assert capsys.readouterr().out == results_block(note())
