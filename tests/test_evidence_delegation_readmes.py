"""DESIGN 13.10 v1.271 (row D4j): each of the three delegation evidence folders has a README.md
that names every file the folder holds, links the converter whose output its script reads with
the options its RESULTS.md `## Regenerate` block passes, links that dataset's evidence README,
and points to the `## Regenerate` block instead of repeating its commands."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
EVIDENCE = ROOT / "evidence"

FOLDERS = {
    "delegation": {
        "title": "# Delegation evidence on AutoBench 2026",
        "section": "13.10",
        "converter": "../autobench-2026/convert.py",
        "options": ("--task-by all --tokens --registry",),
        "dataset_readme": "../autobench-2026/README.md",
        "files": ("results.py", "results.json", "variants.json", "RESULTS.md"),
    },
    "tau2-bench-delegation": {
        "title": "# Delegation evidence on tau2-bench",
        "section": "13.12",
        "converter": "../tau2-bench/convert.py",
        "options": ("--calls",),
        "dataset_readme": "../tau2-bench/README.md",
        "files": ("results.py", "registry.json", "results.json", "pooled.json", "RESULTS.md"),
    },
    "llmrouterbench-delegation": {
        "title": "# Delegation evidence on LLMRouterBench",
        "section": "13.13",
        "converter": "../llmrouterbench/convert.py",
        "options": (),
        "dataset_readme": "../llmrouterbench/README.md",
        "files": ("results.py", "registry.json", "results.json", "RESULTS.md"),
    },
}
LINK = re.compile(r"\]\(([^)\s]+)\)")
NAMES = sorted(FOLDERS)


def readme(name):
    return (EVIDENCE / name / "README.md").read_text(encoding="utf-8")


def slug(heading):
    """The anchor GitHub gives a Markdown heading: lower case, spaces to hyphens, other
    punctuation but hyphens and underscores dropped."""
    text = heading.strip().lower()
    return re.sub(r"[^a-z0-9 _-]", "", text).replace(" ", "-")


def headings(text):
    return {slug(line.lstrip("#")) for line in text.split("\n") if re.match(r"#{1,6} ", line)}


def section(text, heading):
    """The lines of one `## ` section, up to the next `## ` heading or the end."""
    lines = text.split("\n")
    start = lines.index(heading)
    end = next((k for k in range(start + 1, len(lines)) if lines[k].startswith("## ")), len(lines))
    return lines[start + 1:end]


def regenerate_commands(name):
    """The lines inside the fenced `bash` blocks of a RESULTS.md `## Regenerate` section."""
    md = (EVIDENCE / name / "RESULTS.md").read_text(encoding="utf-8")
    commands, inside = [], False
    for line in section(md, "## Regenerate"):
        if line.startswith("```"):
            inside = line == "```bash"
            continue
        if inside:
            commands.append(line)
    return commands


def relative_links(text):
    return [t for t in LINK.findall(text) if not re.match(r"[a-z]+:", t)]


@pytest.mark.parametrize("name", NAMES)
def test_title_and_design_section(name):
    text = readme(name)
    spec = FOLDERS[name]
    assert text.split("\n")[0] == spec["title"]
    assert f"`DESIGN.md` {spec['section']})" in text


@pytest.mark.parametrize("name", NAMES)
def test_names_every_file_the_folder_holds(name):
    folder = EVIDENCE / name
    held = {p.name for p in folder.iterdir()
            if p.is_file() and p.suffix in (".py", ".json", ".md") and p.name != "README.md"}
    spec = FOLDERS[name]
    assert held == set(spec["files"])
    holds = [line for line in readme(name).split("\n") if line.startswith("This folder holds")]
    assert len(holds) == 1
    for file in spec["files"]:
        if file.endswith(".py"):
            assert f"`{file}`" in holds[0], file
        else:
            assert f"]({file})" in holds[0], file


@pytest.mark.parametrize("name", NAMES)
def test_links_the_converter_its_regenerate_block_runs(name):
    spec = FOLDERS[name]
    inputs = "\n".join(section(readme(name), "## Inputs"))
    assert f"[`{spec['converter']}`]({spec['converter']})" in inputs
    assert f"]({spec['dataset_readme']})" in inputs
    assert "not committed" in inputs
    converter = (EVIDENCE / name / spec["converter"]).resolve().relative_to(ROOT).as_posix()
    runs = [c for c in regenerate_commands(name) if c.startswith(f"python {converter} ")]
    assert runs, converter
    for option in spec["options"]:
        assert f"`{option}`" in inputs or f"`{option} " in inputs, option
        assert option in runs[0], option


@pytest.mark.parametrize("name", NAMES)
def test_points_to_the_regenerate_block_without_commands(name):
    text = readme(name)
    assert section(text, "## Regenerate")
    assert "](RESULTS.md#regenerate)" in "\n".join(section(text, "## Regenerate"))
    assert "```" not in text


@pytest.mark.parametrize("name", NAMES)
def test_every_relative_link_resolves(name):
    folder = EVIDENCE / name
    links = relative_links(readme(name))
    assert links
    for link in links:
        path, _, fragment = link.partition("#")
        target = (folder / path).resolve()
        assert target.is_file(), link
        assert ROOT in target.parents, link
        if fragment:
            assert fragment in headings(target.read_text(encoding="utf-8")), link


@pytest.mark.parametrize("name", NAMES)
def test_ascii_with_no_dash(name):
    text = readme(name)
    assert text.isascii()
    assert text.endswith("\n") and not text.endswith("\n\n")


def test_variant_points_link_names_the_variants_part():
    text = readme("delegation")
    assert "](RESULTS.md#variant-points)" in text
    md = (EVIDENCE / "delegation" / "RESULTS.md").read_text(encoding="utf-8")
    variants = [c for c in section(md, "## Variant points") if c.startswith("python ")]
    assert any("--grid variants" in c for c in variants)


def test_slug_matches_the_github_anchor_rule():
    assert slug(" Variant points") == "variant-points"
    assert slug("Regenerate") == "regenerate"
    assert slug("What a row keeps, and why") == "what-a-row-keeps-and-why"
