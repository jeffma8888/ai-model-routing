"""DESIGN 5.2 v1.605 (row GATE1d): the README paragraph on promotion checks, its transcripts, the
note's GitHub line and the defaults.

README `## Running it in production` gains, after the two paragraphs on budgets, one on `promote`:
it complements the Wilson bar and never replaces it, the margin's reference route stays fixed, and
the bound is wide on few pairs. Two transcripts that gates.py and tests/test_readme.py run on a
fresh demo output calibrate the demo's `outcomes.jsonl` with `--outcomes` and hold `demo/atlas-max`
against `demo/atlas-mid`. With no outcomes file nothing GATE1 added runs: no evidence or research
script names it, and the ten transcripts before the two keep their v1.601 bytes. A docs slice: no
package module changes, so these tests passed when they were written.

DESIGN 5.2 v1.606 (row GATE1e): the paragraph's paired lower bound cites its source, the adjusted
Wald interval of Bonett and Price (2012), by its DOI (tests/test_paired_bound_source.py).
"""

import hashlib
import math
import re
from pathlib import Path

from model_routing import paired_promotion
from model_routing.demo import OUTPUTS

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r"```text\n(\$ model-routing [^\n]*\n.*?)```", re.S)  # gates.py's and tests/test_readme.py's
OPENING = "Judge a challenger route against the current one only on the items both were graded on. "
DEMO = "The demo's `outcomes.jsonl` has one line per judge and item with `task`, `model`, `item` and `correct`, "
AFTER = "`demo/atlas-max` clears the bar and measures 0.953 against 0.913 on the same 300 items, "
LAST_BUDGET = "The estimate is no bound: "
CALIBRATE = ("$ model-routing calibrate --results demo-run/outcomes.jsonl --stats demo-run/paired-stats.json "
             "--outcomes demo-run/paired.jsonl")
PROMOTE = ("$ model-routing promote --task demo_faithfulness_judge --challenger demo/atlas-max --margin 0.02 "
           "--outcomes demo-run/paired.jsonl --registry demo-run/models.json --tasks demo-run/tasks.json "
           "--stats demo-run/paired-stats.json")
# The README's ten transcripts at 16a8fd6 (v1.601, before row GATE1b), in order: the first words after
# `$ model-routing `, UTF-8 bytes and sha256 of each block as BLOCK finds it (`git show 16a8fd6:README.md`).
V1_601 = [
    ("demo --out ./demo-run", 831, "f69bc5dfcde9ceaf73ed8bb3860890dbb19d048c3ac4a335d335cbd0ef473386"),
    ("report --log demo-run/calls.jsonl --by flavor", 558,
     "334cb0a03a936478a0760f4c53652a5110573489bdffe051a01eb54a12c709df"),
    ("report --log demo-run/calls.jsonl --by tag:delegated", 561,
     "80bd11068d7f3540f4cd7e143e58064fa7769d6524f9f61259538a79bd24d317"),
    ("evaluate --outcomes demo-run/outcomes.jsonl", 1674,
     "b8fccf3c0bfd789b81298be36d738ce4c13663064e6ffb5bcc611998d9b3703a"),
    ("delegate demo_faithfulness_judge --parent demo/atlas-max ", 497,
     "af84b703b60f980a9c07a199f9bd6254f5506bb2aa8fd0fa42bbc92d6b5ab752"),
    ("delegate demo_faithfulness_judge --parent demo/atlas-mid ", 507,
     "dd5266e190e138fb43026b2fbce8c8a5d38ccedbd9d4e9e367f791c0f2bd9b21"),
    ("delegate demo_faithfulness_judge --parent demo/atlas-mid ", 526,
     "73cab9fca1ba1095fe49dfc3fa108034a88428e08232f698c3bd0a4aca0fd1a3"),
    ("delegate demo_faithfulness_judge --parent demo/atlas-mid ", 517,
     "dc4089f103cbf4cf7dd9dda5b6155e17b5b012708fc2151eec8efea995db3d07"),
    ("plan --success 0.9 --bar 0.8", 151, "eb9d65cfbe81762ef35843efb7586bf654a434ded8a0ead650d2d3b978ee8c40"),
    ("plan --success 1.0 --bar 0.8", 151, "430d2477b67822e29f3fe46c5cece7b4cfce6d661e05b41d757f5cba89116e39"),
]
GATE1_NAMES = ("item_outcomes", "pair_outcomes", "paired_promotion", "PromotionCheck")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def production():
    """README `## Running it in production`, its heading line through the line before the next `## `."""
    text = read("README.md")
    return text.split("\n## Running it in production\n", 1)[1].split("\n## ", 1)[0]


def part(opening):
    """The paragraph of the production section that starts with ``opening``, up to its blank line."""
    body = production()
    assert body.count("\n\n" + opening) == 1, opening
    return opening + body.split("\n\n" + opening, 1)[1].split("\n\n", 1)[0]


def values(block):
    """A `promote` transcript's `key: value` lines as a dict of strings."""
    return dict(re.match(r"(\w+):\s+(.*)$", line).groups() for line in block.rstrip("\n").split("\n")[1:])


def bound(n, b, c, margin=0.03):
    """`paired_promotion` on n pairs, b of them right only for the current route and c only for the challenger."""
    current = {f"i{k}": k >= b + c or k < b for k in range(n)}
    challenger = {f"i{k}": k >= b for k in range(n)}
    return paired_promotion(current, challenger, margin=margin, cheaper=True, min_pairs=1)


# --- the paragraphs ---------------------------------------------------------------------------

def test_the_paragraph_follows_the_two_on_budgets_and_precedes_the_one_on_threads():
    body = production()
    at = body.index("\n\n" + OPENING)
    assert body.index("\n\n" + LAST_BUDGET) < at
    assert body[:at].rstrip().endswith("not a measurement of this library.")
    assert body.index(DEMO) > at and body.index(CALIBRATE) > body.index(DEMO)
    assert body.index(PROMOTE) > body.index(CALIBRATE) and body.index(AFTER) > body.index(PROMOTE)
    # review iter-454 should-fix 3: the last sentence says the hold is the point and nothing was switched;
    # v1.616 (row PROD1c): the one-sentence paragraph on threads follows it (tests/test_threads.py)
    last = body.rstrip().rsplit("\n\n", 1)
    assert last[1].startswith("One `Executor`, with its `Monitor` and `BudgetLedger`, can serve ")
    assert last[0].endswith("This hold is the point of the example: a gap of 0.040 on 300 items, at five "
                            "times the list cost per item, is not yet evidence that `demo/atlas-max` is "
                            "better, and `promote` changed no route or file.")
    assert "\n### " not in body


def test_the_paragraph_says_the_check_complements_the_bar_and_how_to_use_it():
    text = part(OPENING)
    for clause in ("so a challenger that clears it can still do worse than the route it would replace on the same items",
                   "so two routes pair only when one results file graded both",
                   "It requires the bar to admit the challenger first and exits 3 when it does not, so the check "
                   "complements the bar and never replaces it.",
                   "Then it prints `promote` on an exact McNemar result in the challenger's favor at `--alpha` "
                   "(default 0.05) or, for a challenger "
                   "cheaper per item at list prices, on a paired lower bound above `-M` (the adjusted Wald interval "
                   "of [Bonett and Price, 2012](https://doi.org/10.3102/1076998611411915)); `hold` otherwise; and "
                   "`insufficient_overlap` under the task's `min_samples` pairs.",
                   "It is advisory and changes no route or file (`DESIGN.md` 4.7 and 10).",
                   # review iter-454 should-fix 1: `promote` pairs with `select`'s primary, so the paragraph says
                   # how to check a later challenger against the first route
                   "Declare M before the run, and once a challenger is promoted on non-inferiority, check the next "
                   "one against the first route, not the promoted one: each promotion against the route before it "
                   "can lose up to M by the interval's reading, so a chain of k of them can lose up to k times M "
                   "against the first route.",
                   "`promote` always pairs with `select`'s primary, so for that check call `pair_outcomes` with the "
                   "first route as `current` and pass its two maps to `paired_promotion`.",
                   "so a cheaper challenger arises under `cost_blind`, or on a `retry_same` task, whose primary is the "
                   "cheapest per success.",
                   "Calibrate each labeled file once, since a second run doubles the trials the admission reads while "
                   "the pairs count each item once",
                   "pass `--alpha` 0.05 divided by k.",
                   "([production lessons](research/production-lessons.md#switch-models-only-on-locked-data-and-a-significant-result))"):
        assert text.count(clause) == 1, clause
    assert "\u2014" not in text and "\u2013" not in text


def test_the_quote_is_the_notes_word_for_word():
    quote = re.search(r'Harvey compares models on fixed sets: "(.+?)" \(\[production lessons\]', part(OPENING)).group(1)
    note = read("research/production-lessons.md")
    locked = note[note.index("### Switch models only on locked data and a significant result"):]
    assert locked.split("\n### ", 1)[0].count('"' + quote + '"') == 1
    assert quote.startswith("once a collection of evaluation samples is \u201cpublished,\u201d it becomes locked")


def test_the_bound_numbers_are_the_checks():
    text = part(OPENING)
    assert f"at 30 pairs it is {bound(30, 0, 0).lower_bound:.4f} with no discordant pair and " \
           f"{bound(30, 2, 2).lower_bound:.4f} with two each way" in text
    assert (round(bound(30, 0, 0).lower_bound, 4), round(bound(30, 2, 2).lower_bound, 4)) == (-0.0866, -0.15)
    # the smallest pair counts at which a cheaper challenger tied with the current route clears a 0.03 margin
    none = next(n for n in range(1, 1000) if bound(n, 0, 0).decision == "promote")
    each = next(n for n in range(1, 1000) if bound(n, round(0.05 * n), round(0.05 * n)).decision == "promote")
    assert (none, each) == (91, 442)
    assert bound(90, 0, 0).decision == "hold" and bound(441, 22, 22).decision == "hold"
    assert (f"so at the default `--alpha` a cheaper challenger needs {none} pairs to clear a margin of 0.03 with no "
            f"discordant pair and {each} with 5% of the pairs going each way, and never fewer than the task's "
            f"`min_samples`.") in text


def test_bound_counts_its_pairs_as_said():
    check = bound(10, 2, 3)
    assert (check.pairs, check.current_only, check.challenger_only, check.unpaired) == (10, 2, 3, 0)


# --- the transcripts --------------------------------------------------------------------------

def test_the_two_transcripts_come_last_and_the_ten_before_keep_their_v1_601_bytes():
    blocks = BLOCK.findall(read("README.md"))
    assert len(blocks) == len(V1_601) + 2 == 12
    for block, (words, size, digest) in zip(blocks, V1_601):
        assert block.startswith("$ model-routing " + words), words
        assert len(block.encode("utf-8")) == size, words
        assert hashlib.sha256(block.encode("utf-8")).hexdigest() == digest, words
    assert blocks[-2].split("\n", 1)[0] == CALIBRATE and blocks[-1].split("\n", 1)[0] == PROMOTE
    # the ten name nothing GATE1 added, so with no outcomes file they run as at v1.601
    for block in blocks[:-2]:
        command = block.split("\n", 1)[0]
        assert " promote " not in command and not (" calibrate " in command and "--outcomes" in command)


def test_the_two_write_only_files_the_demo_does_not_and_no_earlier_transcript_names():
    # review iter-454 should-fix 4: what this shows is that the demo writes neither file and no README text
    # before the calibrate block names one; that no earlier block prints otherwise is the fresh runs' check
    # (tests/test_readme.py and gates.py) on the ten pinned blocks above
    before = read("README.md").split(CALIBRATE, 1)[0]
    for name in ("paired-stats.json", "paired.jsonl"):
        assert name not in OUTPUTS
        assert "demo-run/" + name not in before, name


def test_the_text_states_the_transcripts_numbers():
    blocks = BLOCK.findall(read("README.md"))
    got = values(blocks[-1])
    assert (got["current"], got["challenger"], got["decision"], got["basis"]) == (
        "demo/atlas-mid", "demo/atlas-max", "hold", "n/a")
    assert (got["pairs"], got["challenger_only"], got["current_only"], got["cheaper"]) == ("300", "24", "12", "false")
    text = part(AFTER)
    rates = (float(got["challenger_rate"]), float(got["current_rate"]))
    assert f"measures {rates[0]:.3f} against {rates[1]:.3f} on the same {got['pairs']} items" in text
    assert f"right on {got['challenger_only']} items where `demo/atlas-mid` is wrong and wrong on " \
           f"{got['current_only']} where it is right" in text
    # review iter-454 should-fix 3: the gap and the cost ratio the last sentence names
    assert got["difference"] == "0.040000" and "a gap of 0.040 on 300 items" in text
    ratio = float(got["challenger_list_cost"]) / float(got["current_list_cost"])
    assert math.isclose(ratio, 5.0) and "at five times the list cost per item" in text
    p = float(got["p_value"])
    assert p > float(got["alpha"]) and f"p {p:.3f} is over {got['alpha']}" in text
    # the exact McNemar p of 24 against 12, two-sided
    assert math.isclose(min(1.0, 2 * sum(math.comb(36, k) for k in range(13)) / 2 ** 36), p, abs_tol=5e-7)
    calibrated = blocks[-2].rstrip("\n").split("\n")
    digest = calibrated[-1].rsplit(" ", 1)[1]
    assert calibrated[-1] == f"appended 1200 outcomes to demo-run/paired.jsonl, dataset_sha256 {digest}"
    assert got["dataset_sha256"] == digest
    rows = {line.split()[1]: line.split()[2:4] for line in calibrated[2:6]}
    assert rows["demo/atlas-max"] == ["286", "300"] and rows["demo/atlas-mid"] == ["274", "300"]
    assert int(got["min_pairs"]) == 50 and "min_samples" in part(OPENING)


# --- no outcomes file, no change --------------------------------------------------------------

def test_no_evidence_or_research_script_names_what_gate1_added():
    paths = [*sorted((ROOT / "evidence").rglob("*.py")), *sorted((ROOT / "research").rglob("*.py"))]
    assert len(paths) > 2
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for name in GATE1_NAMES:
            assert name not in source, (path, name)
    workflow = read(".github/workflows/evidence.yml")
    assert workflow.count("run: git diff --exit-code -- evidence/") == 1


# --- the note -------------------------------------------------------------------------------

def test_the_notes_github_line_names_the_paired_check_as_shipped():
    note = read("research/production-lessons.md")
    [line] = [x for x in note.splitlines()
              if x.startswith("- In this library: the caller calls a task, not a model, ")]
    assert ("The paired check of the Harvey lesson on locked data can run before a route changes: from v1.603 "
            "`model-routing promote` compares a challenger with the current route on the items that one labeled "
            "file graded for both, by `paired_promotion` (v1.601), after the bar admits the challenger, so "
            "re-running a fixed labeled set after a model or price change says whether to promote. ") in line
    changes = line.split(" The changes: ", 1)[1].split(" Which measure counts ", 1)[0]
    assert "paired" not in changes and "promote" not in changes
    assert changes.endswith("and a set share of routed calls also sent to a reference route, so a quality loss "
                            "nobody labeled shows up in pairs to label.")


# --- DESIGN and the changelog -----------------------------------------------------------------

def test_design_states_the_paragraph_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = design[design.index("### 5.2 "):design.index("### 5.3 ")]
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.605 README and note (row GATE1d): ")]
    for kept in ("gains, after the two paragraphs on budgets, one on promotion checks (4.7, 10)",
                 "so the check complements the bar and never replaces it",
                 "and a chain of k of them up to k times M (review iter-449 should-fix 3(b))",
                 "(review iter-454 should-fix 1)", "(review iter-454 should-fix 3)",
                 "at 30 pairs -0.0866 with no discordant pair and -0.1500 with two each way (review iter-449 nit 5)",
                 "a cheaper challenger needs 91 pairs to clear a margin of 0.03 with none and 442 with 5% of the "
                 "pairs going each way",
                 "(10 v1.603, review iter-452 should-fix 1, review iter-454 nit 5)", "(review iter-452 should-fix 2)",
                 "(review iter-449 should-fix 3(a))",
                 "`calibrate --results demo-run/outcomes.jsonl --stats demo-run/paired-stats.json --outcomes "
                 "demo-run/paired.jsonl`",
                 "the README's ten transcripts before the two keep their v1.601 bytes, each pinned by sha256 "
                 "(tests/test_promote_docs.py)",
                 "No package module or evidence file changes"):
        assert mine.count(kept) == 1, kept
    assert "(from v1.605 a paragraph on `promote` and its transcripts follow them, row GATE1d)" in five2
    seven = design[design.index("### 4.7 "):design.index("## 5. ")]
    assert seven.rstrip("\n").endswith("the README paragraph (row GATE1d), which v1.605 adds (5.2).")
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.605 (")]
    assert line.startswith("- v1.605 (2026-11-23): docs and tests (4.7, 5.2, row GATE1d). ")
    assert len(line.encode("utf-8")) <= 600
