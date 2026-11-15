"""v1.408 the output re-read share in the CLI, the 13.9 evaluator and README Limitations
(DESIGN 13.1, 13.7; row D11c), written before the code.

``model-routing delegate --output-reread-share X`` (default 1.0) passes ``output_reread_share``
(sigma, 13.1 v1.404) to ``decide_delegation`` as a float, and exits 2 with one ``error:`` line,
the last on stderr, on a value that is not a number in [0, 1], ``nan`` and ``inf`` included, as
``--cached-read-ratio`` does (v1.41). The 13.9 evaluator keeps 1.0: a point has no key for the
share, so a point that carries one fails. README Limitations names the 13.2 over-statement for a
model whose history drops its reasoning, with the measured over predicted medians of
research/ledger-cost-model.md, which the README test builds from the note's Results block.

The fixture is that of tests/test_output_reread_share.py: cheap 1/2, mid 3/6 and best 10/20 USD
per 1M tokens, S_in = 2,000, S_out = 500, C = 20,000, B = 300, R = 200, and in ``cost_effective``
the delegate is mid.
"""

import dataclasses
import json
import re
from pathlib import Path

import pytest

from model_routing import main
from model_routing.delegation_eval import _points
from test_output_reread_share import TASK, decide, plain_router

ROOT = Path(__file__).resolve().parents[1]
WORK = {"context_tokens": 20_000, "brief_tokens": 300, "result_tokens": 200}
TEXT_KEYS = ["mode", "model", "reason", "below_bar", "inline_cost_usd", "delegate_cost_usd",
             "parent_quality_lb", "delegate_quality_lb"]


@pytest.fixture
def delegate_files(tmp_path):
    router = plain_router()
    rows = [dict(dataclasses.asdict(m), source="https://example.org/prices")
            for m in router.registry.models]
    paths = {"registry": tmp_path / "models.json", "tasks": tmp_path / "tasks.json",
             "stats": tmp_path / "stats.json", "priors": tmp_path / "no-priors.json"}
    paths["registry"].write_text(json.dumps({"version": "1", "as_of": "2026-01-01",
                                             "currency": "USD", "models": rows}),
                                 encoding="utf-8")
    task = dataclasses.asdict(router.tasks[TASK])
    paths["tasks"].write_text(json.dumps({"tasks": [task]}), encoding="utf-8")
    router.stats.save(paths["stats"])
    return paths


def delegate_args(files, *extra, parent="fiction/best"):
    args = ["delegate", TASK, "--parent", parent]
    for key, value in WORK.items():
        args += ["--" + key.replace("_", "-"), str(value)]
    for flag, path in files.items():
        args += ["--" + flag, str(path)]
    return args + list(extra)


# 13.7: the flag reaches decide_delegation

@pytest.mark.parametrize("extra,kwargs", [
    ((), {}),
    (("--fold-inline", "--work-calls", "3", "--carry-turns", "1"),
     {"inline_separate_call": False, "work_calls": 3, "carry_turns": 1}),
    (("--work-calls", "2", "--cached-read-ratio", "0.1"),
     {"work_calls": 2, "cached_read_ratio": 0.1}),
])
def test_cli_output_reread_share_reaches_the_api(delegate_files, capsys, extra, kwargs):
    code = main(delegate_args(delegate_files, "--json", "--output-reread-share", "0.25", *extra))
    out = capsys.readouterr().out
    assert code == 0
    expected = decide(plain_router(), "fiction/best", output_reread_share=0.25, **kwargs).to_dict()
    assert json.loads(out) == expected
    # the share moves the cost, so a flag the CLI dropped would fail the equality above
    assert expected != decide(plain_router(), "fiction/best", **kwargs).to_dict()


@pytest.mark.parametrize("value", ["1", "1.0"])
def test_cli_share_one_prints_what_no_flag_prints(delegate_files, capsys, value):
    assert main(delegate_args(delegate_files, "--output-reread-share", value)) == 0
    flagged = capsys.readouterr().out
    assert main(delegate_args(delegate_files)) == 0
    assert flagged == capsys.readouterr().out


def test_cli_text_keeps_its_eight_lines_with_a_share(delegate_files, capsys):
    # One work call in a call of its own, T = 0, on best (10/20): the work call reads C + S_in =
    # 22,000 and writes 500; the next call re-reads S_in + sigma * S_out = 2,000 + 125. Inline is
    # 24,125 * 10 / 1M + 500 * 20 / 1M = 0.24125 + 0.01 = 0.25125 (0.255 at sigma 1). Delegating:
    # the brief 300 * 20 / 1M = 0.006, mid reads B + S_in = 2,300 * 3 / 1M = 0.0069 and writes
    # 500 * 6 / 1M = 0.003 (one call re-reads no output), the next call reads B + R = 500 * 10 / 1M
    # = 0.005, so 0.0209 at every sigma.
    code = main(delegate_args(delegate_files, "--output-reread-share", "0.25"))
    text = capsys.readouterr().out
    assert code == 0
    assert [line.split(":", 1)[0] for line in text.splitlines()] == TEXT_KEYS
    assert re.search(r"^inline_cost_usd:\s+0\.251250$", text, re.MULTILINE)
    assert re.search(r"^delegate_cost_usd:\s+0\.020900$", text, re.MULTILINE)
    assert main(delegate_args(delegate_files)) == 0
    assert re.search(r"^inline_cost_usd:\s+0\.255000$", capsys.readouterr().out, re.MULTILINE)


@pytest.mark.parametrize("value", ["-0.5", "1.5", "nan", "inf", "-inf", "half"])
def test_cli_bad_output_reread_share_exits_two_with_one_error_line(delegate_files, capsys, value):
    assert main(delegate_args(delegate_files, "--output-reread-share", "0.5")) == 0
    capsys.readouterr()
    assert main(delegate_args(delegate_files, "--output-reread-share", value)) == 2
    captured = capsys.readouterr()
    lines = captured.err.splitlines()
    assert captured.out == ""
    assert lines[-1].startswith("error: ")
    assert sum(line.startswith("error: ") for line in lines) == 1
    assert "output-reread-share" in lines[-1].replace("_", "-")


def test_cli_the_ratio_is_checked_before_the_share(delegate_files, capsys):
    assert main(delegate_args(delegate_files, "--cached-read-ratio", "2",
                              "--output-reread-share", "2")) == 2
    last = capsys.readouterr().err.splitlines()[-1]
    assert "cached_read_ratio" in last and "output_reread_share" not in last


# 13.1: the 13.9 evaluator keeps 1.0

POINT = {"context_tokens": 20_000, "brief_tokens": 300, "result_tokens": 200, "carry_turns": 0,
         "inline_separate_call": True}


def test_the_evaluator_points_take_no_share():
    assert _points([POINT]) == [POINT]
    for share in (0.5, 1.0):
        with pytest.raises(ValueError, match="optionally 'work_calls' and 'cached_read_ratio'"):
            _points([dict(POINT, output_reread_share=share)])


def section(text, start, end):
    return text[text.index(start):text.index(end)]


def test_design_states_the_flag_in_13_7_and_the_evaluator_in_13_1():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    s13_1 = section(design, "### 13.1 Inputs", "### 13.2 ")
    s13_7 = section(design, "### 13.7 CLI", "### 13.8 ")
    assert "do not pass it yet" not in s13_1
    for term in ("The CLI passes it from v1.408 (`--output-reread-share`, 13.7, row D11c)",
                 "the 13.9 evaluator keeps 1.0, since a point has no key for it",
                 "so every committed delegation result re-reads each S_out whole"):
        assert term in s13_1, term
    for term in ("[--cached-read-ratio X] [--output-reread-share X] [--",  # v1.409 adds a flag
                 "`--output-reread-share` (v1.408, default 1.0) passes `output_reread_share` (13.1) "
                 "as a float",
                 "`>= 1`, from v1.41, a `--cached-read-ratio` and, from v1.408, an "
                 "`--output-reread-share` that is not a number in [0, 1], `nan` and "
                 "`inf` included"):
        assert term in s13_7, term


# README Limitations: the over-statement, from the note's Results block

NOTE = ROOT / "research" / "ledger-cost-model.md"
RATIO = re.compile(r"  (single|chain): measured [\d,]+\.\d, 13\.2 rule [\d,]+\.\d, ratio (\d\.\d{3}) ")


def medians():
    """The depths and, per path, the 13.2 rule's median measured over predicted ratios, in depth
    order, from the note's Results block."""
    text = NOTE.read_text(encoding="utf-8")
    block = text.split("\n## Results\n", 1)[1].split("```text\n", 1)[1].split("\n```", 1)[0]
    depths, ratios = [], {"single": [], "chain": []}
    for line in block.splitlines():
        found = re.fullmatch(r"depth (\d+), 100 items", line)
        if found:
            depths.append(found[1])
        found = RATIO.match(line)
        if found:
            ratios[found[1]].append(found[2])
    assert depths == ["20", "50", "100"]
    assert [len(ratios["single"]), len(ratios["chain"])] == [3, 3]
    return depths, ratios


def limitations_bullet():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    limits = readme.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in limits.split("\n")
               if line.startswith("- The inline-or-delegate cost is a list-price approximation.")]
    assert len(bullets) == 1
    return bullets[0]


def test_readme_limitations_name_the_over_statement_and_the_share():
    (d20, d50, d100), ratios = medians()
    s, c = ratios["single"], ratios["chain"]
    # the whole-history ratio falls with depth, as the sentence's "increasingly" says
    assert float(s[0]) > float(s[1]) > float(s[2])
    sentence = (
        "For a model whose history keeps each reply and drops its reasoning, that over-states the "
        "re-reads, increasingly as more calls come before each one: on the ledger runs "
        "([research/ledger-cost-model.md](research/ledger-cost-model.md)) measured prompt tokens "
        f"over those the rule predicts are a median {s[0]}, {s[1]} and {s[2]} on the whole-history "
        f"path at depths {d20}, {d50} and {d100} and {c[0]}, {c[1]} and {c[2]} on the chain. "
        "`output_reread_share` (`--output-reread-share`, default 1.0, each output re-read whole) "
        "sets the share of each output that later calls re-read.")
    bullet = limitations_bullet()
    assert bullet.count(sentence) == 1
    before = "with nothing summarised between calls. "
    assert bullet.index(before) + len(before) == bullet.index(sentence)
