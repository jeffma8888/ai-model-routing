"""research/production-lessons.md (v1.562, row PL1a): what public production write-ups found about
cutting model cost at equal or better quality, and what this library does with each lesson.

Run offline. The note's quotes were checked word for word against their pages when it was written;
this file checks what a reader can check without fetching them: every URL in the note is in its
`## Sources` list and every listed URL is cited above it, the list states the date the pages were
fetched, each quote is under 40 words and names its URL, and the note names no local path. It also
checks that README.md and research/README.md link the note once, that DESIGN 14 says a change the
note names is a plan, and that the changelog line names its section and the row.

v1.563 (row PL1b) adds `## Uber` after `## Harvey`, with its items on what the sources do not say,
and one rule: a Sources item that says its page is paywalled says it is quoted only from the part
its fetch returned, so a reader knows which part of the page the quotes were checked against.

v1.564 (row PL1c) adds `## Other teams` after `## Uber`, four write-ups on prompt caching, with
their items on what the sources do not say, and says in the frame that a number the note computes
from a source's own numbers says it is computed here.

v1.565 (row PL1d) adds three lessons to `## Other teams` (LMSYS RouteLLM, OpenRouter Fusion and
Replit code repair), with their items on what the sources do not say, and says in the frame that
a result measured on a benchmark rather than on production traffic says so, and that a model name
in the text, as in a quote, is its author's product name."""

import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
NOTE = ROOT / "research" / "production-lessons.md"
README = ROOT / "README.md"
RESEARCH_README = ROOT / "research" / "README.md"
CHANGELOG = ROOT / "CHANGELOG.md"
DESIGN = ROOT / "DESIGN.md"

URL = re.compile(r"https?://[^\s)\]>\"'`]+")
QUOTE = re.compile(r'"([^"]+)"( \(\[[^\]]+\]\((https://[^)]+)\)\))?')
LOCAL_PATH = re.compile(r"(?:^|[\s(\[`'\"])(?:~[/\\]|/(?!/)|[A-Za-z]:[\\/])|file:|\\Users\\|\$HOME\b|%USERPROFILE%")  # review iter-407 nit 1: $HOME
FETCHED = re.compile(r"^Each page was fetched on \d{4}-\d{2}-\d{2}\.$", re.M)
PAYWALLED = re.compile(r"paywall", re.I)
QUOTED_FROM = re.compile(r"\bquoted only from (?:the |its )?(?!(?:the|its)\b)[A-Za-z]{3,}", re.I)  # review iter-408 should-fix 1
SOURCES = "\n## Sources\n"


def problems(text):
    """Every way the note breaks its rules, one line each; [] when none."""
    found = []
    if text.count(SOURCES) != 1:
        return [f"the note has {text.count(SOURCES)} `## Sources` headings, not one"]
    body, sources = text.split(SOURCES)
    if "\n## " in sources:
        found.append("`## Sources` is not the last section")
    listed = [m.group(0) for line in sources.splitlines() if line.startswith("- ")
              for m in [URL.match(line[2:])] if m]
    items = [line for line in sources.splitlines() if line.startswith("- ")]
    if len(listed) != len(items):
        found.append("a Sources item does not start with its URL")
    if len(set(listed)) != len(listed):
        found.append("a URL is listed twice in Sources")
    if not FETCHED.search(sources):
        found.append("Sources does not say the date the pages were fetched")
    for line in items:
        if PAYWALLED.search(line) and not QUOTED_FROM.search(line):
            found.append(f"the paywalled item {line[2:42]!r} does not say which part it is quoted from")
    cited = URL.findall(body)
    for url in sorted(set(cited) - set(listed)):
        found.append(f"{url} is cited but not in Sources")
    for url in sorted(set(listed) - set(cited)):
        found.append(f"{url} is in Sources but cited nowhere")
    for quote, link, url in QUOTE.findall(body):
        if not link:
            found.append(f"the quote {quote[:40]!r} names no URL")
        if len(quote.split()) >= 40:
            found.append(f"the quote {quote[:40]!r} has {len(quote.split())} words, not under 40")
    for number, line in enumerate(text.splitlines(), 1):
        if LOCAL_PATH.search(line):
            found.append(f"line {number} names a local path")
    return found


def test_the_note_keeps_its_rules():
    assert problems(NOTE.read_text(encoding="utf-8")) == []


def test_the_note_quotes_and_cites_its_sources():
    text = NOTE.read_text(encoding="utf-8")
    body = text.split(SOURCES)[0]
    assert len(QUOTE.findall(body)) >= 130  # v1.565 (row PL1d): 138
    assert len(set(URL.findall(body))) >= 18
    assert "## What the sources do not say" in body
    assert "first sent everything to frontier models" in body
    # v1.563 (row PL1b): the Uber section sits after Harvey's, and its do-not-say items before both
    assert body.count("\n## Uber\n") == 1 and body.index("\n## Harvey\n") < body.index("\n## Uber\n")
    unsaid = body[body.index("## What the sources do not say"):body.index("\n## Harvey\n")]
    assert "$1,500 a month" in unsaid and "These are two policies at two dates" in unsaid
    assert "The two have different baselines, so no saving per request is derived from them" in unsaid
    # v1.564 (row PL1c): `## Other teams` after Uber's, its do-not-say items, and the computed-number rule
    assert body.count("\n## Other teams\n") == 1 and body.index("\n## Uber\n") < body.index("\n## Other teams\n")
    assert "so none of them is a saving from routing" in unsaid and "the cut computed here is about 8.7x on input" in unsaid
    assert "not a company write-up, and it gives no cache hit rate" in unsaid
    frame = body[:body.index("## What the sources do not say")]
    assert "A number this note computes from a source's own numbers says it is computed here." in frame
    # v1.565 (row PL1d): three lessons on routing, panels and a distilled model, each said to be a benchmark result
    assert "A result measured on a benchmark rather than on production traffic says so, and says who ran it." in frame
    assert "A model name, in a quote or in the text, is its author's product name" in frame
    assert "Model names inside quotes" not in frame
    assert "RouteLLM's numbers are a research lab's results on three public benchmarks" in unsaid
    assert "Fusion's numbers are a vendor's benchmark of its own product" in unsaid
    assert "Replit's per-model scores are in chart images only" in unsaid
    other = body[body.index("\n## Other teams\n"):]
    for url in ("https://lmsys.org/blog/2024-07-01-routellm/", "https://openrouter.ai/blog/announcements/fusion-beats-frontier/",
                "https://blog.replit.com/code-repair"):
        assert url in other
    assert "All three give results on benchmarks, not on production traffic" in other


SMALL = """# Note

## Lesson

- Result: "a short quote" ([page](https://example.com/a))

## Sources

Each page was fetched on 2026-11-21.

- https://example.com/a (what it is)
"""


@pytest.mark.parametrize("old, new, message", [
    ("https://example.com/a))", "https://example.com/b))", "https://example.com/b is cited but not in Sources"),
    ("- https://example.com/a (what it is)\n", "- https://example.com/a (what it is)\n- https://example.com/c (more)\n",
     "https://example.com/c is in Sources but cited nowhere"),
    ("Each page was fetched on 2026-11-21.\n", "", "Sources does not say the date the pages were fetched"),
    ('"a short quote"', '"' + " ".join(["word"] * 40) + '"', "has 40 words, not under 40"),
    (' ([page](https://example.com/a))', ' (https://example.com/a)', "names no URL"),
    ("## Lesson\n", "## Lesson\n\nCopied from /opt/notes/lessons.md.\n", "line 5 names a local path"),
    ("## Lesson\n", "## Lesson\n\nSee ~/notes for more.\n", "line 5 names a local path"),
    ("## Lesson\n", "## Lesson\n\nSee C:\\notes for more.\n", "line 5 names a local path"),
    ("## Lesson\n", "## Lesson\n\nSee file:notes.md.\n", "line 5 names a local path"),
    ("## Lesson\n", "## Lesson\n\nSee $HOME/notes for more.\n", "line 5 names a local path"),
    ("## Lesson\n", "## Lesson\n\nSee %USERPROFILE%\\notes for more.\n", "line 5 names a local path"),
    ("## Sources\n", "## Sources\n\n## More\n", "`## Sources` is not the last section"),
    ("- https://example.com/a (what it is)\n", "- https://example.com/a (what it is)\n- https://example.com/a (again)\n",
     "a URL is listed twice in Sources"),
    ("- https://example.com/a (what it is)\n", "- https://example.com/a (what it is)\n- see above\n",
     "a Sources item does not start with its URL"),
    ("\n## Sources\n", "\n## Sources\n\n## Sources\n", "2 `## Sources` headings"),
    ("- https://example.com/a (what it is)\n", "- https://example.com/a (a news report, paywalled past its opening)\n",
     "does not say which part it is quoted from"),
    ("- https://example.com/a (what it is)\n", "- https://example.com/a (Paywalled past its opening)\n",
     "does not say which part it is quoted from"),
    ("- https://example.com/a (what it is)\n", "- https://example.com/a (paywalled; quoted only from)\n",
     "does not say which part it is quoted from"),
    ("- https://example.com/a (what it is)\n", "- https://example.com/a (behind a paywall, quoted only from the)\n",
     "does not say which part it is quoted from"),
])
def test_a_broken_note_is_named(old, new, message):
    assert problems(SMALL) == []
    assert SMALL.count(old) == 1
    found = problems(SMALL.replace(old, new))
    assert any(message in line for line in found), found


def test_a_paywalled_item_that_says_what_it_is_quoted_from_passes():
    text = SMALL.replace("- https://example.com/a (what it is)\n",
                         "- https://example.com/a (a report, paywalled past its opening and quoted only from the opening)\n")
    assert problems(text) == []


def test_the_readmes_link_the_note_once():
    readme = README.read_text(encoding="utf-8")
    assert readme.count("(research/production-lessons.md)") == 1
    mine = [line for line in readme.splitlines() if "(research/production-lessons.md)" in line]
    assert ("Harvey's, Uber's, four other teams' on prompt caching and three on routing, panels and a distilled model "
            "so far") in mine[0]  # v1.565, row PL1d
    prior = readme.index("Full survey with sources and dates: [research/prior-art.md](research/prior-art.md).")
    assert prior < readme.index("(research/production-lessons.md)") < readme.index("## Limitations and non-goals")
    text = RESEARCH_README.read_text(encoding="utf-8")
    assert text.count("| [production-lessons.md](production-lessons.md) |") == 1
    assert (text.index("| [production-lessons.md](production-lessons.md) |")
            < text.index("| [prior-art.md](prior-art.md) |"))
    assert "The production-lessons note was gathered on 2026-11-21." in text
    row = [line for line in text.splitlines() if line.startswith("| [production-lessons.md](production-lessons.md) |")]
    assert ("(Short answer, from Harvey's and Uber's engineering blogs, four other teams' write-ups on prompt "
            "caching and three on routing, panels and a distilled model so far:") in row[0]


def test_the_changelog_line_names_the_row():
    mine = [line for line in CHANGELOG.read_text(encoding="utf-8").splitlines() if line.startswith("- v1.562 (")]
    assert len(mine) == 1
    assert ": docs and tests (14, row PL1a). `research/production-lessons.md` reads" in mine[0]
    uber = [line for line in CHANGELOG.read_text(encoding="utf-8").splitlines() if line.startswith("- v1.563 (")]
    assert len(uber) == 1
    assert ": docs and tests (14, row PL1b). `research/production-lessons.md` gains `## Uber`" in uber[0]
    other = [line for line in CHANGELOG.read_text(encoding="utf-8").splitlines() if line.startswith("- v1.564 (")]
    assert len(other) == 1
    assert ": docs and tests (14, row PL1c). `research/production-lessons.md` gains `## Other teams`" in other[0]
    more = [line for line in CHANGELOG.read_text(encoding="utf-8").splitlines() if line.startswith("- v1.565 (")]
    assert len(more) == 1
    assert ": docs and tests (14, row PL1d). `research/production-lessons.md` gains three lessons in `## Other teams`" in more[0]


def test_design_14_says_a_named_change_is_a_plan():
    text = DESIGN.read_text(encoding="utf-8")
    fourteen = text[text.index("## 14. "):text.index("## 15. ")]
    mine = [line for line in fourteen.splitlines() if line.startswith("- Production lessons (v1.562, row PL1a): ")]
    assert len(mine) == 1
    assert "`research/production-lessons.md`" in mine[0]
    assert "A change it names is a plan, not part of v1: it is specified in its own section" in mine[0]
    assert mine[0].count("From v1.563 (row PL1b), a page paywalled past its opening is quoted only from the "
                         "opening its fetch returned and its Sources item says so") == 1
    assert mine[0].count("From v1.564 (row PL1c), a number the note computes from a source's own numbers says "
                         "it is computed here") == 1
    assert mine[0].count("From v1.565 (row PL1d), a result measured on a benchmark rather than on production traffic "
                         "says so") == 1
