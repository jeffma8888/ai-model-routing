"""v1.409 the brief's output size in the CLI, the 13.9 evaluator and the ledger evidence
(DESIGN 13.1, 13.7, 13.15; row D12), written before the code.

``model-routing delegate --brief-output-tokens N`` (default unset, meaning B) passes
``brief_output_tokens`` (W, 13.1 v1.405) to ``decide_delegation`` as an integer, and exits 2 with
one ``error:`` line, the last on stderr, on a value that is not an integer >= 0, as the other
token options do; unset, the CLI prints what v1.408 printed, byte for byte. The 13.9 evaluator
keeps W = B, since a point has no key for it, and 13.15 says the ledger runs set no W from their
note calls' measured completions, which the test builds from research/ledger-cost-model.md.

v1.412 (row DOC31, review iter-269 should-fix 1): README Limitations' inline-or-delegate cost
bullet names the flag in the sentence after the re-read share's, with the note calls' medians and
depths, which the test builds from the same Results block, and 13.1 says so.

The fixture is that of tests/test_output_reread_share_cli.py: cheap 1/2, mid 3/6 and best 10/20
USD per 1M tokens, S_in = 2,000, S_out = 500, C = 20,000, B = 300, R = 200, and in
``cost_effective`` the delegate is mid.
"""

import json
import re
from pathlib import Path

import pytest

from model_routing import main
from model_routing.delegation_eval import _points
from test_output_reread_share import decide, plain_router
from test_output_reread_share_cli import (TEXT_KEYS, delegate_args, delegate_files,  # noqa: F401
                                        limitations_bullet)

ROOT = Path(__file__).resolve().parents[1]


# 13.7: the flag reaches decide_delegation

@pytest.mark.parametrize("extra,kwargs", [
    ((), {}),
    (("--fold-inline", "--carry-turns", "1"), {"inline_separate_call": False, "carry_turns": 1}),
    (("--work-calls", "2", "--output-reread-share", "0.5", "--cached-read-ratio", "0.1"),
     {"work_calls": 2, "output_reread_share": 0.5, "cached_read_ratio": 0.1}),
])
def test_cli_brief_output_tokens_reaches_the_api(delegate_files, capsys, extra, kwargs):
    code = main(delegate_args(delegate_files, "--json", "--brief-output-tokens", "900", *extra))
    out = capsys.readouterr().out
    assert code == 0
    expected = decide(plain_router(), "fiction/best", brief_output_tokens=900, **kwargs).to_dict()
    assert json.loads(out) == expected
    # W moves the delegate's cost, so a flag the CLI dropped would fail the equality above
    assert expected != decide(plain_router(), "fiction/best", **kwargs).to_dict()


@pytest.mark.parametrize("json_flag", [(), ("--json",)])
def test_cli_unset_or_b_prints_the_v1_408_output(delegate_files, capsys, json_flag):
    assert main(delegate_args(delegate_files, *json_flag)) == 0
    unset = capsys.readouterr().out
    assert main(delegate_args(delegate_files, *json_flag, "--brief-output-tokens", "300")) == 0
    assert capsys.readouterr().out == unset  # W = B, the --brief-tokens value
    if json_flag:
        assert json.loads(unset) == decide(plain_router(), "fiction/best").to_dict()


def test_cli_text_keeps_its_eight_lines_with_w(delegate_files, capsys):
    # On best (10/20), delegating at W = B = 300: the brief 300 * 20 / 1M = 0.006, mid reads
    # B + S_in = 2,300 * 3 / 1M = 0.0069 and writes 500 * 6 / 1M = 0.003, the next call reads
    # B + R = 500 * 10 / 1M = 0.005, so 0.0209. W = 900 charges the brief 900 * 20 / 1M = 0.018
    # and keeps every read of B, so 0.0209 - 0.006 + 0.018 = 0.0329; inline stays 0.255.
    code = main(delegate_args(delegate_files, "--brief-output-tokens", "900"))
    text = capsys.readouterr().out
    assert code == 0
    assert [line.split(":", 1)[0] for line in text.splitlines()] == TEXT_KEYS
    assert re.search(r"^delegate_cost_usd:\s+0\.032900$", text, re.MULTILINE)
    assert re.search(r"^inline_cost_usd:\s+0\.255000$", text, re.MULTILINE)
    assert main(delegate_args(delegate_files)) == 0
    assert re.search(r"^delegate_cost_usd:\s+0\.020900$", capsys.readouterr().out, re.MULTILINE)


def test_cli_w_zero_is_allowed(delegate_files, capsys):
    # W = 0 charges no brief output: 0.0209 - 0.006 = 0.0149
    assert main(delegate_args(delegate_files, "--brief-output-tokens", "0")) == 0
    assert re.search(r"^delegate_cost_usd:\s+0\.014900$", capsys.readouterr().out, re.MULTILINE)


@pytest.mark.parametrize("value", ["-1", "1.5", "nan", "half", ""])
def test_cli_bad_brief_output_tokens_exits_two_with_one_error_line(delegate_files, capsys, value):
    assert main(delegate_args(delegate_files, "--brief-output-tokens", "900")) == 0
    capsys.readouterr()
    assert main(delegate_args(delegate_files, "--brief-output-tokens", value)) == 2
    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert captured.out == ""
    assert lines[-1].startswith("error: ")
    assert sum(line.startswith("error: ") for line in lines) == 1
    assert "brief-output-tokens" in lines[-1].replace("_", "-")


def test_cli_the_share_is_checked_before_w(delegate_files, capsys):
    assert main(delegate_args(delegate_files, "--output-reread-share", "2",
                              "--brief-output-tokens", "-1")) == 2
    last = capsys.readouterr().err.splitlines()[-1]
    assert "output_reread_share" in last and "brief_output_tokens" not in last


def test_cli_help_names_the_flag(capsys):
    with pytest.raises(SystemExit) as raised:
        main(["delegate", "--help"])
    assert raised.value.code == 0
    assert "--brief-output-tokens" in capsys.readouterr().out


# 13.1: the 13.9 evaluator keeps W = B

POINT = {"context_tokens": 20_000, "brief_tokens": 300, "result_tokens": 200, "carry_turns": 0,
         "inline_separate_call": True}


def test_the_evaluator_points_take_no_w():
    assert _points([POINT]) == [POINT]
    for w in (0, 300, 900):
        with pytest.raises(ValueError, match="optionally 'work_calls' and 'cached_read_ratio'"):
            _points([dict(POINT, brief_output_tokens=w)])


def section(text, start, end):
    return text[text.index(start):text.index(end)]


def test_design_states_the_flag_in_13_7_and_the_evaluator_in_13_1():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    s13_1 = section(design, "### 13.1 Inputs", "### 13.2 ")
    s13_7 = section(design, "### 13.7 CLI", "### 13.8 ")
    assert "and the CLI (13.7) and the 13.9 evaluator do not pass it" not in s13_1
    for term in ("The CLI passes it from v1.409 (`--brief-output-tokens`, 13.7, row D12)",
                 "the 13.9 evaluator keeps W = B, since a point has no key for it",
                 "and so does every committed delegation result, the ledger runs of 13.15 "
                 "included (its decision (2))",
                 "README `### Inline or sub-agent`'s condition (13.8 v1.256) names the flag among "
                 "its preconditions (no `--brief-output-tokens`), since at W above B its "
                 "`B * p_out / p_in` is `W * p_out / p_in`"):
        assert term in s13_1, term
    # the README paragraph itself is built and checked by tests/test_research_delegation_reasons.py
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert readme.count("the brief's output charged at its size (no `--brief-output-tokens`)") == 1
    for term in ("[--output-reread-share X] [--brief-output-tokens N] [--flavor",
                 "`--brief-output-tokens` (v1.409, default unset, meaning B) passes "
                 "`brief_output_tokens` (13.1) as an integer, and with it unset the CLI prints "
                 "what v1.408 printed, byte for byte",
                 "a token option (from v1.409 `--brief-output-tokens` included) that is not an "
                 "integer `>= 0`"):
        assert term in s13_7, term


# 13.15: the ledger runs set no W, with the note calls' medians from the note's Results block

NOTE = ROOT / "research" / "ledger-cost-model.md"
NOTE_CALL = re.compile(r"a note's call wrote a median of (\d+\.\d) completion tokens for a note "
                       r"of (\d+\.\d)$")


def note_call_medians():
    """The depths and, per depth, the median completion tokens of a note's call and the median
    note size, from the note's Results block (review iter-269 nit 4: the depths too)."""
    text = NOTE.read_text(encoding="utf-8")
    block = text.split("\n## Results\n", 1)[1].split("```text\n", 1)[1].split("\n```", 1)[0]
    depths = [int(m[1]) for m in (re.fullmatch(r"depth (\d+), \d+ items", line)
                                  for line in block.splitlines()) if m]
    found = [NOTE_CALL.search(line) for line in block.splitlines()]
    pairs = [(float(m[1]), float(m[2])) for m in found if m]
    assert len(depths) == len(pairs) >= 2  # one note-call line per depth
    return depths, pairs


def test_design_13_15_says_the_ledger_runs_keep_w_at_b():
    depths, pairs = note_call_medians()
    written = sorted(p[0] for p in pairs)
    notes = sorted(p[1] for p in pairs)
    # every note's call writes more than its note, so W = B under-charges it here
    assert all(w > b for w, b in pairs)
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    s13_15 = section(design, "### 13.15 ", "## 14. ")
    sentence = (
        "So no result here sets 13.1's W from the note calls' measured completion tokens (a "
        f"median {written[0]:.1f} to {written[-1]:.1f} for notes of {notes[0]:.1f} to "
        f"{notes[-1]:.1f} at depths {min(depths)} to {max(depths)}, `research/ledger-cost-model.md`): "
        "every committed "
        "delegation result keeps W = B (13.1, v1.409, row D12)")
    assert s13_15.count(sentence) == 1
    assert "never as a decision's outcome. " + sentence in s13_15


# README Limitations: the flag beside the re-read share, from the note's Results block (v1.412)

def brief_output_sentence():
    """The README Limitations sentence on the flag, with the note calls' medians and depths."""
    depths, pairs = note_call_medians()
    written = sorted(p[0] for p in pairs)
    notes = sorted(p[1] for p in pairs)
    # every note's call writes more than its note, so the brief's size under-states it here
    assert all(w > b for w, b in pairs)
    return (
        "`brief_output_tokens` (`--brief-output-tokens`, default the brief's size) sets the "
        "output tokens of the call that writes the brief, which the brief's size under-states "
        "when that call reasons before it writes: on the ledger runs the call that wrote a note "
        f"produced a median {written[0]:.1f} to {written[-1]:.1f} completion tokens for notes of "
        f"{notes[0]:.1f} to {notes[-1]:.1f}, at depths {min(depths)} to {max(depths)}.")


def test_readme_limitations_name_the_flag_after_the_reread_share():
    sentence = brief_output_sentence()
    bullet = limitations_bullet()
    assert bullet.count(sentence) == 1
    before = "sets the share of each output that later calls re-read. "
    assert bullet.index(before) + len(before) == bullet.index(sentence)
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    limits = readme.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    # Limitations names the flag in this sentence alone
    assert limits.count("--brief-output-tokens") == 1


def test_design_13_1_states_the_limitations_sentence():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    s13_1 = section(design, "### 13.1 Inputs", "### 13.2 ")
    clause = (
        "From v1.412 (row DOC31) README Limitations' inline-or-delegate cost bullet names the flag "
        "in the sentence after the `output_reread_share` one: it sets the output tokens of the "
        "call that writes the brief, which the brief's size under-states when that call reasons "
        "before it writes, with the note calls' medians above and their depths, 20 to 100, which "
        "its test reads from the note's Results block")
    assert s13_1.count(clause) == 1
    depths, _ = note_call_medians()
    assert (min(depths), max(depths)) == (20, 100)
