"""Every README transcript matches a fresh run line for line (DESIGN 12.5, v1.5)."""

import re
from pathlib import Path

import pytest

from model_routing import main

README = Path(__file__).resolve().parent.parent / "README.md"
BLOCK = re.compile(r"```text\n(\$ model-routing [^\n]*\n.*?)```", re.S)


def transcripts():
    if not README.exists():
        pytest.skip("README.md is not next to the tests")
    return BLOCK.findall(README.read_text(encoding="utf-8"))


def test_readme_shows_the_demo_report_and_evaluate_transcripts():
    commands = [block.split("\n", 1)[0].split()[2] for block in transcripts()]
    assert {"demo", "report", "evaluate"} <= set(commands)
    assert commands.index("demo") < commands.index("report")
    assert commands.index("demo") < commands.index("evaluate")


def test_readme_transcripts_match_a_fresh_run(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    for block in transcripts():
        lines = block.rstrip("\n").split("\n")
        code = main(lines[0].split()[2:])
        out = capsys.readouterr().out
        assert code == 0, lines[0]
        assert out.rstrip("\n").split("\n") == lines[1:], lines[0]
