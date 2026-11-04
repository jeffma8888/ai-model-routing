"""The README matches the repo: every transcript matches a fresh run line for line
(DESIGN 12.5, v1.5), and its claims about the package hold (DESIGN 3, v1.13)."""

import argparse
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


# DESIGN 3, v1.13: the README's claims about the package match the repo.

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "model_routing"
SIZE = re.compile(r"about ([0-9][0-9,]*) lines")
LAYOUT = re.compile(r"^## Layout\n\s*```[\w-]*\n(.*?)^```", re.S | re.M)


def package_lines(package):
    """Total line count of package/*.py as wc -l counts it: newline characters."""
    return sum(p.read_bytes().count(b"\n") for p in package.glob("*.py"))


def package_entries(block):
    """(name, description) for each line indented two spaces under model_routing/."""
    entries, inside = [], False
    for line in block.split("\n"):
        if line == "model_routing/":
            inside = True
        elif inside and re.match(r"  \S", line):
            name, _, rest = line[2:].partition(" ")
            entries.append((name, rest.strip()))
        elif inside and line.startswith("   "):
            continue
        elif inside:
            break
    return entries


def parser_subcommands():
    from model_routing.cli import _build_parser

    for action in _build_parser()._actions:
        if isinstance(action, argparse._SubParsersAction):
            return list(action.choices)
    raise AssertionError("cli.py defines no subcommands")


def claim_problems(text, line_count, modules, data_files, commands):
    """Every way the README's claims about the package disagree with the repo."""
    problems = []
    sizes = SIZE.findall(text)
    if len(sizes) != 1:
        problems.append(f"expected one 'about N lines' claim, found {len(sizes)}")
    else:
        stated = int(sizes[0].replace(",", ""))
        if abs(stated - line_count) > 0.10 * line_count:
            problems.append(f"README says about {stated} lines, model_routing/*.py has {line_count}")
    blocks = LAYOUT.findall(text)
    if len(blocks) != 1:
        problems.append(f"expected one Layout block, found {len(blocks)}")
        return problems
    entries = package_entries(blocks[0])
    named = [name for name, _ in entries if name.endswith(".py")]
    problems += [f"module {n} missing from the Layout block" for n in sorted(set(modules) - set(named))]
    problems += [f"Layout block names {n}, not a model_routing/*.py file"
                 for n in sorted(set(named) - set(modules))]
    problems += [f"Layout block names {n} more than once"
                 for n in sorted({n for n in named if named.count(n) > 1})]
    data_entries = [rest for name, rest in entries if name == "data/"]
    if len(data_entries) != 1:
        problems.append(f"expected one data/ entry in the Layout block, found {len(data_entries)}")
    else:
        listed = [n.strip() for n in data_entries[0].split(",") if n.strip()]
        problems += [f"data file {n} missing from the data/ entry"
                     for n in sorted(set(data_files) - set(listed))]
        problems += [f"data/ entry names {n}, not a file in model_routing/data/"
                     for n in sorted(set(listed) - set(data_files))]
        problems += [f"data/ entry names {n} more than once"
                     for n in sorted({n for n in listed if listed.count(n) > 1})]
    described = dict(entries)
    head, sep, tail = described.get("cli.py", "").partition("model-routing ")
    if not sep:
        problems.append("the cli.py entry does not list the subcommands after 'model-routing'")
        return problems
    shown = [word.strip() for word in tail.split("|")]
    problems += [f"subcommand {c} missing from the cli.py entry" for c in commands if c not in shown]
    problems += [f"cli.py entry names {c}, not a subcommand" for c in shown if c not in commands]
    problems += [f"cli.py entry names {c} more than once"
                 for c in sorted({c for c in shown if shown.count(c) > 1})]
    return problems


def test_readme_claims_about_the_package_match_the_repo():
    if not README.exists() or not PACKAGE.is_dir():
        pytest.skip("README.md and model_routing/ are not next to the tests")
    modules = sorted(p.name for p in PACKAGE.glob("*.py"))
    data_files = sorted(p.name for p in (PACKAGE / "data").iterdir()
                        if p.is_file() and not p.name.startswith("."))
    assert {"__init__.py", "cli.py", "delegation.py"} <= set(modules)
    assert {"models.json", "example_tasks.json"} <= set(data_files)
    problems = claim_problems(README.read_text(encoding="utf-8"), package_lines(PACKAGE),
                              modules, data_files, parser_subcommands())
    assert problems == []


def test_parser_subcommands_are_the_shipped_six():
    assert parser_subcommands() == ["select", "calibrate", "report", "demo", "evaluate", "delegate"]


def test_package_lines_counts_newlines_as_wc_does(tmp_path):
    (tmp_path / "a.py").write_text("x = 1\ny = 2\n", encoding="utf-8")
    (tmp_path / "b.py").write_text("z = 3\nlast line, no newline", encoding="utf-8")
    (tmp_path / "notes.txt").write_text("not counted\n" * 50, encoding="utf-8")
    assert package_lines(tmp_path) == 3


SAMPLE = """# pkg

- standard library only, about 2,000 lines you can read in an afternoon

## Layout

```
model_routing/
  __init__.py   public names
  cli.py        model-routing select | demo
  data/         models.json, tasks.json
tests/          the suite
```
"""
SAMPLE_ARGS = (2000, ["__init__.py", "cli.py"], ["models.json", "tasks.json"], ["select", "demo"])


def test_claim_problems_passes_a_matching_readme():
    assert claim_problems(SAMPLE, *SAMPLE_ARGS) == []


@pytest.mark.parametrize("stated, ok", [
    ("1,800", True), ("1,799", False), ("2,200", True), ("2,201", False), ("1,000", False),
])
def test_claim_problems_allows_ten_percent_on_the_line_count(stated, ok):
    text = SAMPLE.replace("about 2,000 lines", f"about {stated} lines")
    problems = claim_problems(text, *SAMPLE_ARGS)
    assert problems == ([] if ok else [f"README says about {int(stated.replace(',', ''))} lines, "
                                       "model_routing/*.py has 2000"])


def test_claim_problems_needs_exactly_one_line_count_claim():
    twice = SAMPLE.replace("## Layout", "Still about 2,000 lines.\n\n## Layout")
    assert claim_problems(twice, *SAMPLE_ARGS) == ["expected one 'about N lines' claim, found 2"]
    none = SAMPLE.replace("about 2,000 lines", "short")
    assert claim_problems(none, *SAMPLE_ARGS) == ["expected one 'about N lines' claim, found 0"]


def test_claim_problems_catches_missing_stale_and_repeated_modules():
    line_count, modules, data_files, commands = SAMPLE_ARGS
    assert claim_problems(SAMPLE, line_count, modules + ["router.py"], data_files, commands) == [
        "module router.py missing from the Layout block"]
    stale = SAMPLE.replace("  cli.py", "  old.py        gone\n  cli.py")
    assert claim_problems(stale, *SAMPLE_ARGS) == [
        "Layout block names old.py, not a model_routing/*.py file"]
    twice = SAMPLE.replace("  cli.py", "  __init__.py   again\n  cli.py")
    assert claim_problems(twice, *SAMPLE_ARGS) == ["Layout block names __init__.py more than once"]


def test_claim_problems_reads_only_the_model_routing_entries():
    elsewhere = SAMPLE.replace("tests/          the suite", "tests/          the suite\n  router.py     not here")
    line_count, modules, data_files, commands = SAMPLE_ARGS
    assert claim_problems(elsewhere, line_count, modules + ["router.py"], data_files, commands) == [
        "module router.py missing from the Layout block"]
    continued = SAMPLE.replace("  cli.py", "                more about __init__\n  cli.py")
    assert claim_problems(continued, *SAMPLE_ARGS) == []


def test_claim_problems_catches_missing_and_stale_data_files():
    line_count, modules, data_files, commands = SAMPLE_ARGS
    assert claim_problems(SAMPLE, line_count, modules, data_files + ["priors.json"], commands) == [
        "data file priors.json missing from the data/ entry"]
    assert claim_problems(SAMPLE, line_count, modules, ["models.json"], commands) == [
        "data/ entry names tasks.json, not a file in model_routing/data/"]


def test_claim_problems_reads_data_names_without_a_dot():
    line_count, modules, data_files, commands = SAMPLE_ARGS
    stale = SAMPLE.replace("models.json, tasks.json", "models.json, tasks.json, LICENSE")
    assert claim_problems(stale, *SAMPLE_ARGS) == [
        "data/ entry names LICENSE, not a file in model_routing/data/"]
    assert claim_problems(stale, line_count, modules, data_files + ["LICENSE"], commands) == []


def test_claim_problems_catches_a_repeated_data_name_and_extra_data_entries():
    twice = SAMPLE.replace("models.json, tasks.json", "models.json, tasks.json, models.json")
    assert claim_problems(twice, *SAMPLE_ARGS) == ["data/ entry names models.json more than once"]
    extra = SAMPLE.replace("  data/ ", "  data/         old.json\n  data/ ")
    assert claim_problems(extra, *SAMPLE_ARGS) == [
        "expected one data/ entry in the Layout block, found 2"]
    gone = SAMPLE.replace("  data/         models.json, tasks.json\n", "")
    assert claim_problems(gone, *SAMPLE_ARGS) == [
        "expected one data/ entry in the Layout block, found 0"]


def test_claim_problems_allows_a_fence_tag_and_blank_lines_before_the_layout_block():
    tagged = SAMPLE.replace("## Layout\n\n```\n", "## Layout\n\n```text\n")
    assert claim_problems(tagged, *SAMPLE_ARGS) == []
    spaced = SAMPLE.replace("## Layout\n\n```\n", "## Layout\n\n\n```\n")
    assert claim_problems(spaced, *SAMPLE_ARGS) == []


def test_claim_problems_catches_missing_stale_and_repeated_subcommands():
    line_count, modules, data_files, commands = SAMPLE_ARGS
    assert claim_problems(SAMPLE, line_count, modules, data_files, commands + ["delegate"]) == [
        "subcommand delegate missing from the cli.py entry"]
    assert claim_problems(SAMPLE, line_count, modules, data_files, ["select"]) == [
        "cli.py entry names demo, not a subcommand"]
    twice = SAMPLE.replace("select | demo", "select | demo | select")
    assert claim_problems(twice, *SAMPLE_ARGS) == ["cli.py entry names select more than once"]
    bare = SAMPLE.replace("model-routing select | demo", "the command line")
    assert claim_problems(bare, *SAMPLE_ARGS) == [
        "the cli.py entry does not list the subcommands after 'model-routing'"]


def test_claim_problems_needs_one_layout_block():
    assert claim_problems(SAMPLE.replace("## Layout", "## Files"), *SAMPLE_ARGS) == [
        "expected one Layout block, found 0"]
