"""DESIGN 5.2 v1.604 (row PROD1a): the production options in a README section of their own.

From v1.604 README `## Running it in production`, after `## Monitoring and cost attribution` and
before `## Evidence: held-out results on public data`, opens with one sentence that links
`## How a model is chosen` and then holds the seven paragraphs that section held at 16a8fd6 after
its context-window ones (variants, procedures, self-hosted rows, `scope_tasks`, the prompt cache and
the two on budgets), word for word and in their order (from v1.605 a paragraph on `promote` and its
transcripts follow them, tests/test_promote_docs.py): no link target in them changes, since each
names a section or file that stays. `## How a model is chosen` keeps one sentence in their place
and is at most CHOSEN_CAP bytes by the 12.8 measure (v1.335): its size at v1.604 plus MARGIN, which
is under the shortest of the seven, so a later production option goes in the new section. Every
README link to a heading, in the README or in another Markdown file of the repo, resolves. A docs
slice: no package module changes, so these tests passed when they were written.

DESIGN 5.2 v1.629 (row PROD1f): `## Running it in production` is at most PRODUCTION_CAP bytes by the
same measure: its size at v1.629 plus PRODUCTION_MARGIN, room for two paragraphs the size of its
longest (LONGEST, the one on `promote`) but not three. A later version whose text does not fit trims
an older paragraph or moves its detail to DESIGN; only a version that states its reason raises the
cap. A docs slice too: no README text changes, so these tests passed when they were written.

DESIGN 5.2 v1.648 (row PROD1gb): two of the seven moved paragraphs, the one on self-hosted rows and the
one on the prompt cache, are trimmed (tests/test_readme_trim.py), so the move test checks those two by
their openings, their order and a length under the one they moved with, and the other five by their
v1.604 bytes and sha256 as before.
"""

import hashlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CHOSEN = "## How a model is chosen"
PRODUCTION = "## Running it in production"
CHOSEN_SIZE, MARGIN = 6_216, 1_000  # v1.604: the section after the move, and room for one short paragraph
CHOSEN_CAP = CHOSEN_SIZE + MARGIN
# v1.629 (row PROD1f): the production section at v1.629, its margin, and its longest paragraph then
# (the one on `promote`, v1.605); 12,318 bytes at v1.604 (`git show bba6e7c:README.md`)
PRODUCTION_SIZE, PRODUCTION_MARGIN, LONGEST, PRODUCTION_AT_V1_604 = 23_294, 6_706, 2_847, 12_318
PRODUCTION_CAP = PRODUCTION_SIZE + PRODUCTION_MARGIN
# The seven paragraphs of `## How a model is chosen` at 16a8fd6 after the context-window ones, in
# order: their opening words, UTF-8 bytes and sha256 (`git show 16a8fd6:README.md`).
MOVED = [
    ("One model run two ways can be two routes. ", 1825,
     "b0f49c1eda533f51493c68f525dd6eca65f7183da0619e91c86563147b8e1e9f"),
    ("Recurring tool work can be a route of its own. ", 1735,
     "9a7f7a04a509b556be0b795df674172e8db126c599adc4dd80e866a6beefda4c"),
    ("A model you train or serve yourself is a row priced from its hour. ", 2002,
     "f4d957778a71262785868356b2e392087a68442d9b76aeb43c363293db82a1db"),
    ("A model built for some tasks can be kept to them. ", 1176,
     "f20162a30b1ae2f24a08f5881642ec4ff4c8c2802711663367b2a8ca35648023"),
    ("A prompt cache changes what a call costs, ", 2133,
     "07d412ae4456ae31e2a7d32c962470eccd10c3d3d04a33d63234b5d43c7b8223"),
    ("A budget tracks what the executor spends and can warn, refuse or move a call. ", 1566,
     "aefb0f28e9467c1fba3ef5f3b11acc481aca402df68a66c6d2062d61b1243c54"),
    ("The estimate is no bound: ", 1659,
     "85318b6f8f8b400e7c17e56e2737cce7923df888d09068f4323836e781e6e7bb"),
]
# v1.648 (row PROD1gb): the MOVED paragraphs a later version trimmed, by opening (tests/test_readme_trim.py)
TRIMMED = ("A model you train or serve yourself is a row priced from its hour. ",
           "A prompt cache changes what a call costs, ")
LEAD = ("These options sit on top of the selection rule of [How a model is chosen](#how-a-model-is-chosen): "
        "each changes which routes a task has, what they cost or what a call may spend.")
POINTER = ("Variants of one model, procedures, self-hosted rows, task scopes, prompt-cache prices and budgets "
           "change which routes a task has, what they cost or what a call may spend; each is explained in "
           "[Running it in production](#running-it-in-production).")
LINK = re.compile(r"\]\(([^)\s]*)#([^)\s]+)\)")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def section_lines(text, heading):
    """The 12.8 measure's lines (v1.335): the heading line through the line before the next `## `."""
    lines = text.splitlines(keepends=True)
    starts = [i for i, line in enumerate(lines) if line.rstrip("\r\n") == heading]
    if len(starts) != 1:
        raise ValueError(f"README has {len(starts)} `{heading}` lines, not one")
    start = starts[0]
    end = next((i for i in range(start + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    return lines[start:end]


def size(text, heading):
    return sum(len(line.encode("utf-8")) for line in section_lines(text, heading))


def paragraphs(text, heading):
    body = "".join(section_lines(text, heading)[1:])
    return body.split("\n### ", 1)[0].strip().split("\n\n")


def cap_problems(text, cap=CHOSEN_CAP, heading=CHOSEN):
    found = size(text, heading)
    return [] if found <= cap else [f"`{heading}` is {found:,} bytes, over its {cap:,}-byte cap"]


def padded(text, heading, n):
    """`text` with n `x` bytes before the first line after `heading` and its blank line, so the section
    grows by exactly n whatever section follows it, and padding again finds the same place (review
    iter-482 should-fix 1 and 2: at the cap a pad of 0 then 1 is the one-byte-over case)."""
    head = "\n" + heading + "\n\n"
    assert text.count(head) == 1, heading
    return text.replace(head, head + "x" * n, 1)


def slug(heading):
    """GitHub's anchor for a heading: lower case, drop what is not a letter, digit, space, `-` or `_`."""
    return re.sub(r"[^\w\- ]", "", heading.strip().lower()).replace(" ", "-")


def anchors(text):
    found, seen, fence = set(), {}, False
    for line in text.splitlines():
        if line.startswith("```"):
            fence = not fence
            continue
        heading = re.match(r"#{1,6} (.+)$", line)
        if heading and not fence:
            base = slug(heading.group(1))
            count = seen.get(base, 0)
            seen[base] = count + 1
            found.add(base if count == 0 else f"{base}-{count}")
    return found


def link_problems(text, root=ROOT):
    """Each link to a heading (`(#a)` or `(path.md#a)`, never a URL) whose anchor is not a heading of its file."""
    problems = []
    for path, anchor in LINK.findall(text):
        if "://" in path:
            continue
        if path == "":
            target = text
        else:
            file = root / path
            if not file.is_file():
                problems.append(f"{path}#{anchor}: no such file")
                continue
            target = file.read_text(encoding="utf-8")
        if anchor not in anchors(target):
            problems.append(f"{path}#{anchor}: no such heading")
    return problems


# --- the cap --------------------------------------------------------------------------------

def test_how_a_model_is_chosen_is_under_its_cap():
    text = read("README.md")
    assert size(text, CHOSEN) <= CHOSEN_CAP
    assert cap_problems(text) == []
    # the margin is under the shortest moved paragraph, so none of them fits back in
    assert MARGIN < min(n for _, n, _ in MOVED) == 1176


def test_the_cap_fails_one_byte_over():
    text = read("README.md")
    room = CHOSEN_CAP - size(text, CHOSEN)
    at = padded(text, CHOSEN, room)
    assert size(at, CHOSEN) == CHOSEN_CAP and cap_problems(at) == []
    over = padded(at, CHOSEN, 1)
    assert size(over, CHOSEN) == CHOSEN_CAP + 1
    assert cap_problems(over) == [f"`{CHOSEN}` is {CHOSEN_CAP + 1:,} bytes, over its {CHOSEN_CAP:,}-byte cap"]


def test_running_it_in_production_is_under_its_cap():
    text = read("README.md")
    assert size(text, PRODUCTION) <= PRODUCTION_CAP == 30_000
    assert cap_problems(text, PRODUCTION_CAP, PRODUCTION) == []
    # the margin holds two paragraphs the size of the longest at v1.629, not three
    assert 2 * LONGEST <= PRODUCTION_MARGIN < 3 * LONGEST
    assert PRODUCTION_SIZE - PRODUCTION_AT_V1_604 == 10_976


def test_the_production_cap_fails_one_byte_over():
    text = read("README.md")
    room = PRODUCTION_CAP - size(text, PRODUCTION)
    at = padded(text, PRODUCTION, room)
    assert size(at, PRODUCTION) == PRODUCTION_CAP and cap_problems(at, PRODUCTION_CAP, PRODUCTION) == []
    over = padded(at, PRODUCTION, 1)
    assert size(over, PRODUCTION) == PRODUCTION_CAP + 1
    assert cap_problems(over, PRODUCTION_CAP, PRODUCTION) == [
        f"`{PRODUCTION}` is {PRODUCTION_CAP + 1:,} bytes, over its {PRODUCTION_CAP:,}-byte cap"]
    # the padding lands in the production section only
    assert size(over, CHOSEN) == size(text, CHOSEN)
    evidence = "## Evidence: held-out results on public data"
    assert size(over, evidence) == size(text, evidence)


def test_a_pad_adds_exactly_its_bytes_to_its_section_only():
    text = "intro\n## A\n\nab\n\n## B\n\ncd\n"
    assert padded(text, "## A", 0) == text
    for n in (0, 1, 5):
        once = padded(text, "## A", n)
        assert size(once, "## A") == size(text, "## A") + n and size(once, "## B") == size(text, "## B")
        assert size(padded(once, "## A", 1), "## A") == size(text, "## A") + n + 1


def test_the_measure_reads_the_heading_through_the_line_before_the_next_section():
    text = "intro\n## A\nab\n### B\ncd\n## C\nef\n"
    assert size(text, "## A") == len("## A\nab\n### B\ncd\n") == 17
    assert size(text, "## C") == len("## C\nef\n")
    assert paragraphs("## A\n\nx\n\ny\n\n### B\nz\n", "## A") == ["x", "y"]


# --- the move -------------------------------------------------------------------------------

def test_the_new_section_follows_monitoring_and_precedes_evidence():
    heads = [line for line in read("README.md").splitlines() if line.startswith("## ")]
    at = heads.index(PRODUCTION)
    assert heads[at - 1:at + 2] == ["## Monitoring and cost attribution", PRODUCTION,
                                    "## Evidence: held-out results on public data"]
    assert heads.count(PRODUCTION) == 1


def test_the_new_section_is_the_lead_and_the_seven_paragraphs_word_for_word():
    found = paragraphs(read("README.md"), PRODUCTION)
    assert found[0] == LEAD
    # v1.605 (row GATE1d): the paragraph on `promote` and its transcripts follow the seven
    # (tests/test_promote_docs.py)
    moved = found[1:8]
    assert len(moved) == len(MOVED) == 7
    assert found[8].startswith("Judge a challenger route against the current one only on the items ")
    assert [opening for opening, _, _ in MOVED if opening in TRIMMED] == list(TRIMMED)
    for paragraph, (opening, length, digest) in zip(moved, MOVED):
        assert paragraph.startswith(opening), opening
        if opening in TRIMMED:
            assert len(paragraph.encode("utf-8")) < length, opening
            continue
        assert len(paragraph.encode("utf-8")) == length, opening
        assert hashlib.sha256(paragraph.encode("utf-8")).hexdigest() == digest, opening
    assert "\n### " not in "".join(section_lines(read("README.md"), PRODUCTION))


def test_how_a_model_is_chosen_keeps_the_rule_and_one_pointer():
    text = read("README.md")
    found = paragraphs(text, CHOSEN)
    assert found[-1] == POINTER and found[-2].startswith("The window limits one request. ")
    body = "".join(section_lines(text, CHOSEN))
    assert body.count(POINTER) == 1 and body.count("```mermaid") == 1
    assert body.count("\n### The quality bar is a confidence bound, not an average\n") == 1
    assert body.count("\n### Rules that protect quality\n") == 1
    for opening, _, _ in MOVED:
        assert opening not in body, opening
        assert text.count(opening) == 1, opening


def test_the_links_to_the_moved_paragraphs_target_the_new_section():
    text = read("README.md")
    # review iter-453 nit 2: `link_problems` cannot see a stale link to a moved paragraph, since the old
    # heading stays, so the old anchor is counted: the lead is its one link; a new link to the selection
    # rule raises this count
    assert text.count("](#how-a-model-is-chosen)") == 1 and LEAD in text
    assert text.count("Under a [budget](#running-it-in-production) the executor logs ") == 1
    limits = "".join(section_lines(text, "## Limitations and non-goals (v1)"))
    assert limits.count("needs a gateway or the provider's own ([Running it in production]"
                        "(#running-it-in-production)). ") == 1
    assert slug("Running it in production") == "running-it-in-production"


# --- every link to a heading ------------------------------------------------------------------

def test_every_readme_link_to_a_heading_resolves():
    text = read("README.md")
    assert len(LINK.findall(text)) >= 60
    assert link_problems(text) == []


def test_link_problems_names_a_missing_heading_or_file(tmp_path):
    (tmp_path / "note.md").write_text("# Note\n\n## A part, of it\n\n```\n## not a heading\n```\n",
                                      encoding="utf-8")
    text = ("## Here\n\n## Here\n\n[a](#here) [b](#here-1) [c](note.md#a-part-of-it) "
            "[d](https://example.com/x#y) [e](#gone) [f](note.md#not-a-heading) [g](missing.md#x)\n")
    assert link_problems(text, root=tmp_path) == [
        "#gone: no such heading", "note.md#not-a-heading: no such heading", "missing.md#x: no such file"]
    assert slug("Evidence: held-out results on public data") == "evidence-held-out-results-on-public-data"
    assert slug("Start cheap, escalate on a signal") == "start-cheap-escalate-on-a-signal"


# --- DESIGN and the changelog -----------------------------------------------------------------

def test_design_states_the_section_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = design[design.index("### 5.2 "):design.index("### 5.3 ")]
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.604 README (row PROD1a): ")]
    for kept in ("`## Running it in production`, after `## Monitoring and cost attribution` and before "
                 "`## Evidence: held-out results on public data`",
                 "the seven paragraphs that section held at 16a8fd6 after its context-window ones, word for word "
                 "and in their order",
                 f"is at most {CHOSEN_CAP:,} bytes by the 12.8 measure (v1.335): its {CHOSEN_SIZE:,} at v1.604 "
                 f"plus a margin of {MARGIN:,}, under the shortest of the seven (1,176 bytes)",
                 "target `#running-it-in-production`",
                 "No package module, evidence file or README transcript changes"):
        assert mine.count(kept) == 1, kept
    pointer = " (`## Running it in production` from v1.604, row PROD1a) gains "
    assert design.count("README `## How a model is chosen`" + pointer) == 3
    for owner in ("- v1.600 README and note (row B1d): ",
                  "  - README and note: README `## How a model is chosen`" + pointer + "a paragraph, after the "
                  "one on `scope_tasks`",
                  "  - README and note: README `## How a model is chosen`" + pointer + "a paragraph, after the "
                  "one on procedures"):
        assert sum(line.startswith(owner) and pointer in line for line in design.splitlines()) == 1, owner
    # the Status line keeps five versions (tests/test_design_status.py), so the version is pinned by its
    # changelog line, which stays (review iter-453 nit 1)
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.604 (")]
    assert line.startswith("- v1.604 (2026-11-23): docs and tests (4.6, 5.2, 6, 11, row PROD1a). ")
    assert len(line.encode("utf-8")) <= 600


def test_design_and_the_changelog_name_the_production_cap():
    design = read("DESIGN.md")
    five2 = design[design.index("### 5.2 "):design.index("### 5.3 ")]
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.629 README cap (row PROD1f): ")]
    for kept in (f"`## Running it in production` is at most {PRODUCTION_CAP:,} bytes by the 12.8 measure (v1.335): "
                 f"its {PRODUCTION_SIZE:,} at v1.629 plus a margin of {PRODUCTION_MARGIN:,}",
                 f"room for two paragraphs the size of its longest (the {LONGEST:,}-byte one on `promote`, v1.605) "
                 "but not three",
                 f"the section held {PRODUCTION_AT_V1_604:,} bytes at v1.604 and grew by 10,976 from v1.605 to v1.625",
                 "trims an older paragraph of the section, or moves its detail to this file and links the clause",
                 "only a version that states its reason raises the cap",
                 "No package module, evidence file, README text or README transcript changes"):
        assert mine.count(kept) == 1, kept
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.629 (")]
    assert line.startswith("- v1.629 (2026-11-24): docs and tests (5.2, row PROD1f). ")
    assert line.count(f"at most {PRODUCTION_CAP:,} bytes by the 12.8 measure, its {PRODUCTION_SIZE:,} at v1.629 "
                      f"plus a margin of {PRODUCTION_MARGIN:,}") == 1
    assert len(line.encode("utf-8")) <= 600
