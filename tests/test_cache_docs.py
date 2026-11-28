"""DESIGN 6 v1.594 (row CACHE1d): the docs on prompt-cache pricing.

README `## How a model is chosen` gains a paragraph, after the one on `scope_tasks`, on the
registry's cache prices, the counts a results line may carry and their cost breakdown, the attempt
records and `report --cache`, and how an adapter of another API maps its usage fields, quoting
Manus only through research/production-lessons.md. DESIGN 6 states the mapping: `input_tokens`
counts every input token of a call, its cached reads and cache writes included, so an API whose
input count leaves the cache out (Anthropic's Messages API) is summed first. The note's six cache
lessons already state every measured count as shipped, so the only changes their `In this library`
lines plan are the monitor check (row CACHE2), the cold-cache switch (row CACHE3) and the budget
(row B1), and the delegation decision passes only the parent's measured count, to its inline work
(v1.706, row CACHE4a; the delegate's is row CACHE4b). A docs slice:
no package module changes, so these tests passed when they were written.
"""

import dataclasses
import inspect
import re
from pathlib import Path

import pytest

from model_routing import (Candidate, Completion, Executor, FakeProvider, Model, Monitor, Registry,
                           Router, Stats, Task, report)
from model_routing import cli

ROOT = Path(__file__).resolve().parents[1]
MANUS = ("\"If I had to choose just one metric, I'd argue that the KV-cache hit rate is the single "
         "most important metric for a production-stage AI agent.\"")
ANTHROPIC = ("\"Number of input tokens that were not read from or used to create a cache (that is, "
             "tokens after the last cache breakpoint)\"")
CACHE_LESSONS = (
    "Price cache writes, and set the cache's life by how the work pauses",
    "The cache hit rate is a cost number",
    "Keep the prompt prefix the same, byte for byte",
    "Shrink the prompt first, then cache what is read often",
    "Set the cache's life by the traffic rate",
    "Caching that every layer seems to support can still miss, and an alert does not stop spend",
)


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def production_paragraphs():
    # v1.604 (row PROD1a): the paragraphs moved to `## Running it in production`, word for word
    section = read("README.md").split("\n## Running it in production\n", 1)[1].split("\n## ", 1)[0]
    return section.split("\n### ", 1)[0].strip().split("\n\n")


def paragraph():
    found = [p for p in production_paragraphs() if p.startswith("A prompt cache changes what a call costs")]
    assert len(found) == 1
    return found[0]


def slug(heading):
    return re.sub(r"[^a-z0-9 -]", "", heading.lower()).replace(" ", "-")


# --- README ---------------------------------------------------------------------------------

def test_the_paragraph_follows_the_scope_paragraph_and_ends_the_part():
    paragraphs = production_paragraphs()
    at = paragraphs.index(paragraph())
    # v1.600 (row B1d): the two budget paragraphs follow it; from v1.605 (row GATE1d) the part on `promote`
    # follows them (tests/test_promote_docs.py); from v1.694 (row CACHE2c) the paragraph on the cache-miss check
    # comes between it and them (tests/test_cache_miss_docs.py), and from v1.703 (row CACHE3d) the one on a
    # session's switch right after that (tests/test_session_cli.py)
    assert paragraphs[at + 5].startswith("Judge a challenger route against the current one only on the items ")
    assert paragraphs[at + 3].startswith("A budget tracks what the executor spends ")
    assert paragraphs[at + 2].startswith("A switch mid-session starts cold: ")
    assert paragraphs[at + 1].startswith("A `Monitor(path, tasks=..., on_anomaly=...)` writes a `cache_miss` anomaly record ")
    assert paragraphs[at - 1].startswith("A model built for some tasks can be kept to them. ")


def test_the_paragraph_names_each_field_option_and_section():
    text = paragraph()
    # v1.673 (row PROD1ibbba): a pointer paragraph, so it keeps the two prices, the two counts and its pointer; each
    # clause it drops is DESIGN 4.1's, 4.3's, 5.1's, 5.2's, 6's or 8.3's (tests/test_readme_trim.py DROPPED_V1_673)
    for kept in ("A `models.json` row may give `price_cached_in` and `price_cache_write`, and a results line its "
                 "`cached_input_tokens` and `cache_write_tokens` (`DESIGN.md` 4.1, 4.3, 5.1, 5.2, 6, 7, 8.3 and 10). ",):
        assert text.count(kept) == 1, kept
    assert len(text.encode("utf-8")) <= 400


def test_the_v1_594_clauses_left_the_paragraph():
    text = paragraph()
    for gone in ("`price_cached_in` and `price_cache_write`, USD per 1M input tokens",
                 # review iter-442 should-fix 3 and 2
                 "except a row with `price_tiers` or a self-hosted one, which may hold neither",
                 "an absent one is the input price, and a candidate that priced a measured count "
                 "that way names the absent field in `cache_price_unknown`",
                 "A results line may carry `cached_input_tokens` and `cache_write_tokens`",
                 "counted inside its `input_tokens`", "`cost_breakdown`",
                 "Only reported counts are priced as hits, never a repeated prompt",
                 # v1.648 (row PROD1gb): the four parts' prices, the write premium, a cascade's legs and a
                 # procedure's model are DESIGN 4.1's and 5.2's (tests/test_readme_trim.py)
                 "it is priced there at their means, the four parts in its candidate's `cost_breakdown`.",
                 # v1.652 (row PROD1gbbbbb): the model that never hits the cache and what an attempt's price
                 # reads are DESIGN 5.2's and 7's (tests/test_readme_trim.py DROPPED_V1_652)
                 "never a repeated prompt. The inline-or-sub-agent decision reads only `--cached-read-ratio`.",
                 "maps `usage.prompt_tokens_details.cached_tokens` and `report --cache` gives",
                 "`usage.prompt_tokens_details.cached_tokens`",
                 "`report --cache` gives each group's `cache_hit_rate`",
                 "An adapter for another API keeps `input_tokens` inclusive",
                 "returns the sum of `input_tokens`, `cache_read_input_tokens` and "
                 "`cache_creation_input_tokens` as the input (`DESIGN.md` 4.1, 4.3, 5.1, 5.2, 6, 7, 8.3 and 10)"):
        assert gone not in text, gone


def test_the_names_it_gives_are_the_librarys(capsys):
    assert {"price_cached_in", "price_cache_write"} <= {f.name for f in dataclasses.fields(Model)}
    assert {"cost_breakdown", "cache_price_unknown"} <= {f.name for f in dataclasses.fields(Candidate)}
    assert {"cached_input_tokens", "cache_write_tokens"} <= {f.name for f in dataclasses.fields(Completion)}
    assert "cache" in inspect.signature(report).parameters
    assert "cached_read_ratio" in inspect.signature(Router.decide_delegation).parameters
    # review iter-442 nit 3: each option on its own command
    for command, option in (("report", "--cache"), ("delegate", "--cached-read-ratio")):
        with pytest.raises(SystemExit):
            cli.main([command, "--help"])
        assert option in capsys.readouterr().out.split()
    with pytest.raises(SystemExit):
        cli.main(["delegate", "--help"])
    assert "--cache" not in capsys.readouterr().out.split()


def test_the_manus_line_is_the_notes_word_for_word_and_its_link_resolves():
    note = read("research/production-lessons.md")
    text = paragraph()
    # v1.673 (row PROD1ibbba): the quote stays in the note's lesson, which the pointer paragraph links by its heading
    assert MANUS not in text and "Manus" not in text
    assert text.endswith(" [The cache hit rate is a cost number]"
                         "(research/production-lessons.md#the-cache-hit-rate-is-a-cost-number).")
    lesson = note.split("\n### The cache hit rate is a cost number\n", 1)[1].split("\n### ", 1)[0]
    assert lesson.count("Manus: " + MANUS + " ([Manus](https://manus.im/blog/") == 1
    assert slug("The cache hit rate is a cost number") == "the-cache-hit-rate-is-a-cost-number"
    assert "manus.im" not in text  # quoted through the note, never the blog


def test_the_cheaper_model_that_misses_costs_more_than_the_pricier_one_that_hits():
    pricey = Model("fiction/pricey", "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3,
                   price_cache_write=3.75)
    cheap = Model("fiction/cheap", "fam-b", 2.0, 15.0, 200_000)
    hits = pricey.cost(10_000, 500, cached_input_tokens=9_000)
    misses = cheap.cost(10_000, 500, cached_input_tokens=0)
    assert hits == pytest.approx(0.0132) and misses == pytest.approx(0.0275) and hits < misses
    once = pricey.cost(10_000, 500, cache_write_tokens=9_000)
    assert once == pytest.approx(0.04425) and once > pricey.cost(10_000, 500)


# --- DESIGN 6: another API's usage ------------------------------------------------------------

REGISTRY = Registry([Model("fiction/pricey", "fam-a", 3.0, 15.0, 200_000, price_cached_in=0.3,
                           price_cache_write=3.75)])
MSGS = [{"role": "user", "content": "hi"}]


def messages_api_completion(usage, text="ok"):
    """DESIGN 6 v1.594's mapping of a Messages API usage object into a `Completion`: a cache
    count the response lacks or gives as null adds 0 and is passed as None."""
    read, write = usage.get("cache_read_input_tokens"), usage.get("cache_creation_input_tokens")
    return Completion(text, usage["input_tokens"] + (read or 0) + (write or 0), usage["output_tokens"],
                      cached_input_tokens=read, cache_write_tokens=write)


def run(completion):
    planted = Stats()
    planted.add("t", "fiction/pricey", 99, 100)
    router = Router(REGISTRY, {"t": Task("t", bar=0.7, min_samples=10)}, planted)
    monitor = Monitor()
    ticks = iter(0.5 * i for i in range(100))
    executor = Executor(router, FakeProvider({"fiction/pricey": lambda messages: completion}),
                        monitor=monitor, clock=lambda: next(ticks), now=lambda: "2026-11-22T00:00:00Z",
                        id_factory=lambda: "call-1")
    return executor, monitor


USAGE = {"input_tokens": 1_000, "cache_read_input_tokens": 8_000, "cache_creation_input_tokens": 1_000,
         "output_tokens": 500}


def test_the_summed_mapping_prices_the_call_at_its_three_parts():
    executor, monitor = run(messages_api_completion(USAGE))
    [attempt] = executor.call("t", MSGS).attempts
    model = REGISTRY.get("fiction/pricey")
    assert attempt.cost_usd == model.cost(10_000, 500, cached_input_tokens=8_000, cache_write_tokens=1_000)
    # 1,000 uncached at 3.0, 8,000 cached at 0.3, 1,000 written at 3.75 and 500 out at 15.0
    assert attempt.cost_usd == pytest.approx((3_000 + 2_400 + 3_750 + 7_500) / 1_000_000)
    [rec] = monitor.records
    assert (rec["input_tokens"], rec["cached_input_tokens"], rec["cache_write_tokens"]) == (10_000, 8_000, 1_000)
    [row] = report(monitor.records, by="model", cache=True)
    assert row["cache_hit_rate"] == pytest.approx(0.8)


def test_a_count_the_response_lacks_or_nulls_adds_nothing_and_stays_unknown():
    executor, monitor = run(messages_api_completion({"input_tokens": 2_000, "cache_read_input_tokens": 8_000,
                                                     "cache_creation_input_tokens": None,
                                                     "output_tokens": 500}))
    [attempt] = executor.call("t", MSGS).attempts
    assert (attempt.cached_input_tokens, attempt.cache_write_tokens) == (8_000, None)
    assert attempt.cost_usd == REGISTRY.get("fiction/pricey").cost(10_000, 500, cached_input_tokens=8_000)
    [rec] = monitor.records
    assert rec["input_tokens"] == 10_000 and "cache_write_tokens" not in rec
    executor, monitor = run(messages_api_completion({"input_tokens": 3_000, "output_tokens": 500}))
    [attempt] = executor.call("t", MSGS).attempts
    assert (attempt.cached_input_tokens, attempt.cache_write_tokens) == (None, None)
    assert attempt.cost_usd == REGISTRY.get("fiction/pricey").cost(3_000, 500)


def test_the_uncached_count_alone_is_refused_once_the_counts_sum_above_it():
    naive = Completion("ok", 1_000, 500, cached_input_tokens=8_000, cache_write_tokens=1_000)
    executor, monitor = run(naive)
    with pytest.raises(ValueError, match="is over input_tokens"):
        executor.call("t", MSGS)
    assert monitor.records == []


def test_the_uncached_count_alone_under_states_the_cost_when_it_is_not_refused():
    usage = {"input_tokens": 6_000, "cache_read_input_tokens": 4_000, "cache_creation_input_tokens": 0,
             "output_tokens": 500}
    right, _ = run(messages_api_completion(usage))
    naive, _ = run(Completion("ok", 6_000, 500, cached_input_tokens=4_000, cache_write_tokens=0))
    [good] = right.call("t", MSGS).attempts
    [bad] = naive.call("t", MSGS).attempts
    assert bad.cost_usd < good.cost_usd


def test_design_6_states_the_mapping_and_the_changelog_the_version():
    design = read("DESIGN.md")
    six = design[design.index("## 6. Providers"):design.index("## 7. ")]
    mine = [line for line in six.splitlines() if line.startswith("- v1.594 another API's usage (row CACHE1d): ")]
    assert len(mine) == 1
    for kept in ("`input_tokens` is every input token of the call, its cached reads and cache writes included",
                 "each `None` when the API does not say, never 0",
                 "Anthropic's Messages API gives `usage.input_tokens` as the " + ANTHROPIC,
                 "(`https://platform.claude.com/docs/en/build-with-claude/prompt-caching`, fetched 2026-11-22)",
                 "returns the sum of the three as `input_tokens`, `cache_read_input_tokens` as "
                 "`cached_input_tokens` and `cache_creation_input_tokens` as `cache_write_tokens`",
                 "A cache count the response lacks or gives as `null` adds 0 to the sum and is "
                 "passed as `None`, never 0",
                 "is priced at the model's one `price_cache_write`",
                 "the executor raises `Model.cost`'s `ValueError` from `.call` before the attempt is recorded",
                 "The package ships no such adapter"):
        assert mine[0].count(kept) == 1, kept
    assert six.count("  - Not in this version: the delegation costs of 13.2 read no measured cache count.") == 1
    assert "is row CACHE4" in six
    changelog = [line for line in read("CHANGELOG.md").splitlines() if line.startswith("- v1.594 (")]
    assert len(changelog) == 1 and "(6, row CACHE1d)" in changelog[0]
    assert len(changelog[0].encode("utf-8")) <= 600


# --- the note -------------------------------------------------------------------------------

def lesson_lines():
    note = read("research/production-lessons.md")
    lines = {}
    for heading in CACHE_LESSONS:
        body = note.split(f"\n### {heading}\n", 1)[1].split("\n### ", 1)[0].split("\n## ", 1)[0]
        [line] = [x for x in body.splitlines() if x.startswith("- In this library: ")]
        lines[heading] = line
    return lines


# review iter-552 nit 1: named for what is left planned; v1.693 (row CACHE2b): the check's count in `report`
# ships too, so only the switch was; v1.695 (row CACHE3a): the switch ships in `select`, so none is
def test_the_cache_lessons_plan_no_change():
    lines = lesson_lines()
    planned = {h: line.count("planned") for h, line in lines.items() if "planned" in line}
    # v1.692 (row CACHE2a): the monitor check ships, tests/test_cache_miss.py; v1.695 (row CACHE3a): the
    # switch's price, tests/test_session_cache.py
    assert planned == {}
    prefix = lines["Keep the prompt prefix the same, byte for byte"]
    assert ("and from v1.692 a `Monitor` given the tasks flags a task and model whose hit rate over its latest "
            "calls falls under a floor the task sets, `min_cache_hit_rate`.") in prefix
    assert ("Since a cache holds the prefix one model was sent, from v1.695 `select(..., session_route=..., "
            "session_warm=...)` prices the cached reads of a call moved to another model mid-session at that "
            "model's input price, and keeps a pricier model, with `pick_reason` `stay_warm`, when the switch "
            "would cost more.") in prefix
    # review iter-555 nit 1 (v1.696, row T34): a cold route keeps its measured writes, so only the reads move
    assert "uncached input price" not in prefix
    changes = {h: line.split("The change: ", 1)[1] for h, line in lines.items() if "The change" in line}
    # v1.596 (row B1b): the budget that refuses or moves a call is shipped; v1.692 (row CACHE2a): so is the
    # check; v1.693 (row CACHE2b): so is its count in `report`, so no cache lesson names a change left
    assert changes == {}
    for line in lines.values():
        assert "The changes" not in line and "measured cached and written tokens per task and model" not in line


def test_the_bill_lesson_says_report_cache_gives_the_hit_rate():
    # review iter-442 nit 5: the hit rate is measured and shown today; v1.692 (row CACHE2a): the check on a
    # floor ships, tests/test_cache_miss.py
    assert ("so a cache that mostly misses shows in the log, and `report --cache` gives each group's "
            "hit rate, and an in-process budget refuses a call (v1.595) or moves it only to a route that "
            "still clears the bar (v1.596), as in the Uber lesson on spend tiers. From v1.692 a `Monitor` "
            "given the tasks writes an anomaly record, and calls an optional callback, when a task and model's "
            "hit rate over its last `cache_miss_calls` attempts with a count falls under the task's "
            "`min_cache_hit_rate`, and from v1.693 `report --anomalies` gives each model's or task's count of "
            "those records.") in lesson_lines()[CACHE_LESSONS[5]]


def test_the_delegation_decision_passes_only_the_parents_measured_count():
    # v1.706 (row CACHE4a): the parent's counts price its inline work; the delegate's are row CACHE4b
    lines = lesson_lines()
    assert ("the delegation decision prices the parent's inline work at the parent's own measured counts on "
            "the task but passes none to the delegate's model choice yet") in lines[CACHE_LESSONS[0]]
    assert ("while the delegation decision passes only the parent's counts, to its inline work, beside its "
            "cached-read ratio.") in lines[CACHE_LESSONS[1]]
    for line in (lines[CACHE_LESSONS[0]], lines[CACHE_LESSONS[1]]):
        assert "passes none to model choice yet" not in line and "passes no count yet" not in line
