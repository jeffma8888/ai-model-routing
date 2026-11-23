"""DESIGN 4.6 and 3 v1.600 (row B1d): the docs on budgets.

README `## How a model is chosen` gains two paragraphs, after the one on the prompt cache, on
`Budget` and `load_budgets`, the scopes, windows and modes, `BudgetLedger` and the executor's hold
and settle, that the estimate is no bound, a strict budget's `billing_bound`, the budget records,
`budget_report` and `demo --budgets FILE`, and that a limit shared across processes still needs a
gateway or the provider's own, quoting Uber's spend tiers only through
research/production-lessons.md. `## Monitoring and cost attribution` ends with the ```python block
that tests/test_readme_code.py runs, the Limitations no longer say there are no budgets, and the
note's spend-tiers line gains v1.597's strict budget. A docs slice: no package module changes, so
these tests passed when they were written.
"""

import dataclasses
import inspect
import re
from pathlib import Path

import pytest

import model_routing
from model_routing import (Budget, BudgetExceeded, BudgetLedger, Executor, Model, Variant,
                           billing_bound, budget_report, load_budgets)
from model_routing import cli

ROOT = Path(__file__).resolve().parents[1]
CAPS = "\"To avoid imposing strict caps, we implemented real-time spend tracking and automated nudges\""
ALERTS = "\"Alerts at 50/80/100% of expected spend so engineers have time to plan.\""
LESSON = "Spend tiers and nudges, not strict caps"
OPENER = "A budget tracks what the executor spends and can warn, refuse or move a call. "
SECOND = "The estimate is no bound: "  # review iter-448 should-fix 2: two paragraphs


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def section(text, heading):
    return text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def production_paragraphs():
    # v1.604 (row PROD1a): the paragraphs moved to `## Running it in production`, word for word
    part = section(read("README.md"), "Running it in production").split("\n### ", 1)[0]
    return part.strip().split("\n\n")


def both():
    paragraphs = production_paragraphs()
    found = [i for i, p in enumerate(paragraphs) if p.startswith(OPENER)]
    assert len(found) == 1
    first, second = paragraphs[found[0]:found[0] + 2]
    assert second.startswith(SECOND)
    return first, second


def paragraph():
    return "\n\n".join(both())


def slug(heading):
    return re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")


# --- README: the paragraph ---------------------------------------------------------------------

def test_the_paragraphs_follow_the_cache_paragraph_and_end_the_part():
    paragraphs = production_paragraphs()
    first, second = both()
    at = paragraphs.index(first)
    assert at == len(paragraphs) - 2 and paragraphs[at + 1] == second
    assert paragraphs[at - 1].startswith("A prompt cache changes what a call costs")
    # review iter-448 must-fix 2: a `warn` budget caps nothing, so the opener says what each mode does
    assert "A budget caps" not in first


def test_the_paragraph_names_each_part_once():
    text = paragraph()
    for kept in ("`Budget(name, limit_usd, mode, window=\"total\", task=None, tags={})`",
                 "the calls whose tags hold every pair of its `tags`",
                 "or every call when it names neither",
                 "the calls of one run share a budget when you tag each with the run's ID",
                 "(`total`), a UTC `day` or a UTC `month`, each window's spend kept apart",
                 "`load_budgets(path)` reads a list of them from a JSON file",
                 "`Executor(..., ledger=BudgetLedger(budgets))`",
                 "a fallback's, a cascade leg's, a procedure's model call and a hand-off's included",
                 "holds the call's list-price estimate on every budget that applies",
                 # review iter-448 must-fix 3: the estimate reads a slice's output size first
                 "its output the slice's or the task's `expected_output_tokens`",
                 "after the call it settles the measured cost, 0.0 for a call that failed with a provider error",
                 "so tokens a provider bills for a failed call are in no budget",
                 "A `warn` budget notes the first time its spend reaches 50, 80 and 100 percent of its limit in a window",
                 "a `refuse` budget raises `BudgetExceeded` before the call whose hold would pass its limit, and no "
                 "later route entry is tried",
                 "a `downgrade` budget moves that call on along its route to the next entry that clears the bar "
                 "and fits, and refuses when none does, so no call goes below the bar to fit a budget",
                 "The estimate is no bound",
                 "A `strict=True` budget holds each call's `billing_bound` instead",
                 "`max_tokens`, `max_completion_tokens` or `max_output_tokens` in its route's `provider_options`",
                 "refuses a call it cannot bound, a procedure's included",
                 # review iter-448 should-fix 1: a strict hold of a call that raised settles at its bound
                 "it charges that bound for a call that raised anything but a provider error, whose cost "
                 "is then unknown",
                 "so its spend stays under its limit while providers bill within the bound",
                 "as a budget record, which `report` skips",
                 "`budget_report(records, budgets)` gives each budget's `budget_used_pct` in each window",
                 "[Monitoring and cost attribution](#monitoring-and-cost-attribution)",
                 "`model-routing demo --budgets FILE` runs the demo under a file of budgets and exits 4",
                 "The ledger is one process's: a limit shared by many processes still needs a gateway or the "
                 "provider's own",
                 "(`DESIGN.md` 4.6, 7, 8.1, 8.3, 10 and 11)"):
        assert text.count(kept) == 1, kept


def test_the_names_it_gives_are_the_librarys(capsys):
    fields = {f.name: f for f in dataclasses.fields(Budget)}
    assert list(fields) == ["name", "limit_usd", "mode", "window", "task", "tags", "strict"]
    assert (fields["window"].default, fields["task"].default) == ("total", None)
    for mode in ("warn", "refuse", "downgrade"):
        for window in ("total", "day", "month"):
            Budget("b", 1.0, mode, window=window, task="t", tags={"team": "a"})
    with pytest.raises(ValueError):
        Budget("b", 1.0, "warn", strict=True)  # strict takes only `refuse` or `downgrade`
    assert "ledger" in inspect.signature(Executor).parameters
    assert list(inspect.signature(budget_report).parameters) == ["records", "budgets"]
    assert list(inspect.signature(load_budgets).parameters) == ["path"]
    assert issubclass(BudgetExceeded, Exception) and callable(BudgetLedger)
    for name in ("Budget", "BudgetLedger", "BudgetExceeded", "load_budgets", "billing_bound",
                 "budget_report", "report", "Executor"):
        assert name in model_routing.__all__, name
    with pytest.raises(SystemExit):
        cli.main(["demo", "--help"])
    assert "--budgets" in capsys.readouterr().out.split()
    assert cli.EXIT_BUDGET == 4


@pytest.mark.parametrize("key", ["max_tokens", "max_completion_tokens", "max_output_tokens"])
def test_each_output_key_the_paragraph_names_bounds_a_call(key):
    bare = Model("fiction/m", "fam", 1.0, 2.0, 10_000)
    assert billing_bound(bare) is None
    # a route's provider_options are its variant's (DESIGN 4.1 v1.574)
    capped = Model("fiction/m@capped", "fam", 1.0, 2.0, 10_000,
                   variant=Variant("capped", provider_options={key: 500}))
    # 9,500 input tokens at 1.0 and 500 output at 2.0 per 1M
    assert billing_bound(capped) == pytest.approx((9_500 * 1.0 + 500 * 2.0) / 1_000_000)


def test_the_uber_quotes_are_the_notes_word_for_word_and_the_link_resolves():
    text = paragraph()
    assert text.endswith("Uber describes one spend tier across its interactive tools: " + CAPS + ", with "
                         + ALERTS + " ([production lessons](research/production-lessons.md#"
                         "spend-tiers-and-nudges-not-strict-caps)): its policy, for which it gives no saving, "
                         "not a measurement of this library.")
    note = read("research/production-lessons.md")
    lesson = note.split(f"\n### {LESSON}\n", 1)[1].split("\n### ", 1)[0]
    for quote in (CAPS, ALERTS):
        assert lesson.count(quote + " ([software factory](https://www.uber.com/us/en/blog/"
                            "efficient-software-factory/))") == 1, quote
    assert "one shared spend tier across its interactive tools" in note
    assert "neither source gives a saving for its policy" in lesson
    assert slug(LESSON) == "spend-tiers-and-nudges-not-strict-caps"
    assert "uber.com" not in text  # quoted through the note, never the blog


# --- README: the code block, the limitations and the layout ------------------------------------

def test_monitoring_ends_with_the_budget_block_and_its_bullets():
    monitoring = section(read("README.md"), "Monitoring and cost attribution")
    lead = ("Under a [budget](#running-it-in-production) the executor logs each warn crossing and each refusal "
            "as well, and `budget_report` reads each budget's spend back from the log:\n\n```python\n"
            "from model_routing import Budget, BudgetExceeded, BudgetLedger, budget_report\n")
    assert monitoring.count(lead) == 1
    tail = monitoring[monitoring.index(lead):]
    assert tail.count("```python") == 1 and tail.count("\n```\n") == 1
    bullets = tail.split("\n```\n", 1)[1].strip().split("\n")
    assert len(bullets) == 2 and all(b.startswith("- ") for b in bullets)
    # review iter-448 must-fix 1: the sum, and that it is over the limit
    assert bullets[0].endswith("0.00062 spent and 0.000375 held come to 0.000995, over the judge's 0.0009")
    assert "`report` reads the same log as before, since it skips budget records" in bullets[1]


def test_the_limitations_no_longer_say_there_are_no_budgets():
    limits = section(read("README.md"), "Limitations and non-goals (v1)")
    assert "No budgets" not in limits
    assert limits.count("- Budgets hold inside one process, and a `warn` budget writes a log record, not an "
                        "alert: a limit shared by many processes needs a gateway or the provider's own "
                        "([Running it in production](#running-it-in-production)). No async execution or "
                        "streaming. ") == 1  # v1.604, row PROD1a


def test_the_layout_names_the_three_modes():
    assert read("README.md").count(
        "\n  budget.py     in-process spend limits per task or tag: warn, refuse or downgrade\n") == 1


# --- DESIGN, the changelog and the note --------------------------------------------------------

def test_design_states_the_docs_and_the_changelog_the_version():
    design = read("DESIGN.md")
    four6 = design[design.index("### 4.6 Budgets"):design.index("## 5. ")]
    [mine] = [line for line in four6.splitlines() if line.startswith("- v1.600 README and note (row B1d): ")]
    for kept in ("gains two paragraphs, after the one on the prompt cache",
                 "a strict hold of a call that raised anything else settling at its bound",
                 "a strict budget's `billing_bound` and the three output keys it reads",
                 "quoting Uber's spend tiers only through `research/production-lessons.md`",
                 "ends with a ```python block that runs three judge calls under a ledger (3 v1.600)",
                 "No note line planned a shipped budget change",
                 "No package module changes in v1.600"):
        assert mine.count(kept) == 1, kept
    assert four6.count("- Not in this version: request and token limits per route (row BUDGET2) and a limit "
                       "shared across processes (14); the README paragraph and its code block are v1.600's "
                       "(row B1d); ") == 1
    assert "the README paragraph (row B1d)" not in four6
    three = design[design.index("## 3. "):design.index("## 4. ")]
    assert three.count("  - v1.600 (row B1d): a fourth block, at the end of `## Monitoring and cost "
                       "attribution`") == 1
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.600 (")]
    assert line.startswith("- v1.600 (2026-11-23): docs and tests (3, 4.6, row B1d). ")
    assert len(line.encode("utf-8")) <= 600


def in_this_library():
    return [x for x in read("research/production-lessons.md").splitlines() if x.startswith("- In this library: ")]


def test_the_spend_line_gains_the_strict_budget_before_its_records_sentence():
    [spend] = [x for x in in_this_library() if "`BudgetExceeded`" in x]
    strict = ("From v1.597 a strict budget holds each call's billing bound, the most it can cost at its route's "
              "output maximum and its model's context window, in place of the estimate, and refuses a call it "
              "cannot bound, so its spend stays under its limit while providers bill within the bound. ")
    assert spend.count(strict) == 1
    assert spend.index("From v1.596 ") < spend.index(strict) < spend.index("From v1.598 ")


def test_no_note_line_plans_a_shipped_budget_change():
    shipped = ("downgrade", "strict", "budget_used_pct", "budget_report", "--budgets", "BudgetExceeded",
               "day and month", "a budget that", "an in-process budget")
    with_budget = []
    for line in in_this_library():
        for marker in ("The change: ", "The changes: ", "The change still planned"):
            if marker in line:
                planned = line.split(marker, 1)[1]
                assert not [w for w in shipped if w in planned], planned
                if "budget" in planned.lower():
                    with_budget.append(planned)
        for sentence in re.findall(r"[^.]*\bplanned\b[^.]*\.", line):
            assert "budget" not in sentence.lower(), sentence
    # the one planned change that names a budget is the rate limits' (row BUDGET2), and only to
    # say that both hold inside one process
    [grab] = with_budget
    assert grab.startswith("request and token limits per route in the registry")
    assert grab.lower().count("budget") == 1 and "The budget and those limits hold inside one process" in grab
