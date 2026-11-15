"""research/ledger-cost-model.md and research/ledger_cost_model.py (DESIGN 12.22 v1.402, row R37).

The note's `text` block is the script's output on the pinned ledger files, compared byte for byte
when they are already in the converter's default cache (CI never downloads them), and so are the
measured medians against the committed results file. Every number of the note's prose must be in
that block, so the other tests need no download; the rules are checked on synthetic records.
"""

import importlib.util
import json
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "ledger_cost_model.py"
NOTE = ROOT / "research" / "ledger-cost-model.md"
INDEX = ROOT / "research" / "README.md"
DESIGN = ROOT / "DESIGN.md"
RESULTS = ROOT / "evidence" / "ledger-handoff" / "results.json"
COMMAND = "$ python research/ledger_cost_model.py"
SECTIONS = ["## Facts", "## The rule", "## Method", "## Results", "## Reading it", "## Recommendation",
            "## Limits", "## Regenerate"]
PROSE = ("## Reading it", "## Recommendation")
# DESIGN section numbers the prose may name, which are no figures of the block
REFERENCES = {"12.22", "13.1", "13.2", "13.15"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?")  # thousands commas, never a trailing one
BULLET = "- The 13.2 re-read rule against measured tokens (v1.402, row R37): "


def load():
    spec = importlib.util.spec_from_file_location("ledger_cost_model", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def step(prompt, completion, reasoning, t):
    return {"t": t, "prompt_tokens": prompt, "completion_tokens": completion, "reasoning_tokens": reasoning}


def section(text, heading):
    start = text.index(heading + "\n")
    rest = text[start + len(heading) + 1:]
    end = rest.find("\n## ")
    return rest if end < 0 else rest[:end]


def block(text):
    body = section(text, "## Results")
    found = re.findall(r"```text\n(.*?)\n```", body, re.S)
    assert len(found) == 1, "## Results holds one ```text block"
    return found[0]


def cached(mod):
    conv = mod._load(mod.CONVERTER, "ledger_handoff_results_for_test")
    root = conv.default_cache_dir()
    if not all((root / Path(path).name).exists() for path in conv.FILES):
        pytest.skip("the pinned ledger files are not in the default cache")
    return conv, root


def test_single_prediction_by_hand():
    mod = load()
    record = {"L": 3, "item": 0, "steps": [step(100, 5, 1, 1), step(999, 6, 2, 2), step(999, 7, 3, 3)]}
    # 100, then 100 + 10 + 5, then 100 + 20 + 5 + 6; the reply rule drops each earlier call's reasoning
    assert mod.predict(record, False, 10, reply=False) == 100 + 115 + 131
    assert mod.predict(record, False, 10, reply=True) == 100 + 114 + 128
    assert mod.measured(record, False) == 100 + 999 + 999


def test_chain_prediction_by_hand():
    mod = load()
    record = {"L": 4, "item": 1,
              "steps": [step(100, 5, 1, 1), step(999, 6, 1, 2), step(120, 7, 1, 3), step(999, 8, 1, 4)],
              "notes": [{"after_t": 2, "prompt_tokens": 50, "completion_tokens": 9, "note_tokens": 4}]}
    assert [len(steps) for steps, _ in mod.contexts(record, True)] == [2, 2]
    # context 1: 100 and 100 + 10 + 5; its note's call 100 + 10 + 5 + 6; context 2: 120 and 120 + 10 + 7
    assert mod.predict(record, True, 10, reply=False) == 100 + 115 + 121 + 120 + 137
    assert mod.predict(record, True, 10, reply=True) == 100 + 114 + 119 + 120 + 136
    assert mod.measured(record, True) == 100 + 999 + 120 + 999 + 50
    # on `single` the notes are never read
    assert mod.predict(record, False, 10, reply=False) == 100 + 115 + 131 + 148


@pytest.mark.parametrize("after_t, message", [(9, "no later step"), (4, "no step after the last note")])
def test_a_note_that_splits_no_context_is_refused(after_t, message):
    mod = load()
    record = {"L": 4, "item": 2, "steps": [step(100, 5, 1, t) for t in (1, 2, 3, 4)],
              "notes": [{"after_t": after_t, "prompt_tokens": 50, "completion_tokens": 9, "note_tokens": 4}]}
    with pytest.raises(ValueError, match=message):
        mod.predict(record, True, 10, reply=False)


def test_a_bad_cached_file_exits_2_before_any_download(tmp_path):
    mod = load()
    conv = mod._load(mod.CONVERTER, "ledger_handoff_results_for_test")
    first = Path(next(iter(conv.FILES))).name  # fetch checks the files in this order, a present one first
    (tmp_path / first).write_bytes(b"{}")
    done = subprocess.run([sys.executable, str(SCRIPT), "--cache", str(tmp_path)], capture_output=True, text=True)
    assert done.returncode == 2
    assert done.stdout == ""
    assert done.stderr.startswith("error: ") and done.stderr.count("\n") == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == [first]


def test_note_sections_in_order_with_the_rule_before_the_numbers():
    text = NOTE.read_text(encoding="utf-8")
    found = [line for line in text.splitlines() if line.startswith("## ")]
    assert found == SECTIONS
    assert text.index("## The rule") < text.index("## Results")
    assert block(text).startswith(COMMAND + "\n")


def test_every_prose_number_is_in_the_results_block():
    text = NOTE.read_text(encoding="utf-8")
    numbers = set(NUMBER.findall(block(text)))
    for heading in PROSE:
        for number in NUMBER.findall(section(text, heading)):
            assert number in numbers or number in REFERENCES, f"{heading}: {number} is not in the Results block"


def test_the_recommendation_names_the_follow_on_row():
    text = NOTE.read_text(encoding="utf-8")
    assert "row D11" in section(text, "## Recommendation")


def test_the_index_lists_the_note():
    text = INDEX.read_text(encoding="utf-8")
    assert "| [ledger-cost-model.md](ledger-cost-model.md) |" in text


def test_the_design_bullet_is_in_12_22_and_under_1900_bytes():
    text = DESIGN.read_text(encoding="utf-8")
    start, end = text.index("### 12.22 "), text.index("\n## 13. ")
    lines = [line for line in text[start:end].splitlines() if line.startswith(BULLET)]
    assert len(lines) == 1
    assert len(lines[0].encode("utf-8")) < 1900


def test_the_results_block_is_the_script_output():
    mod = load()
    cached(mod)
    done = subprocess.run([sys.executable, str(SCRIPT)], capture_output=True, text=True, check=True)
    text = NOTE.read_text(encoding="utf-8")
    assert block(text) == COMMAND + "\n" + done.stdout.rstrip("\n")


def test_the_measured_medians_equal_the_committed_results():
    mod = load()
    conv, root = cached(mod)
    single = conv.ledger(conv.read_lines(root / "single.jsonl"), "single.jsonl", notes=False)
    chain = conv.ledger(conv.read_lines(root / "decomposed.jsonl"), "decomposed.jsonl", notes=True)
    committed = json.loads(RESULTS.read_text(encoding="utf-8"))["depths"]
    import statistics
    for row in committed:
        keys = sorted(key for key in single if key[0] == row["depth"])
        got = {"single": float(statistics.median(mod.measured(single[k], False) for k in keys)),
               "chain": float(statistics.median(mod.measured(chain[k], True) for k in keys))}
        assert got == row["median_prompt_tokens"]
