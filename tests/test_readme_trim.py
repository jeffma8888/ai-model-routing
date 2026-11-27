"""DESIGN 5.2 v1.647 (row PROD1g, first part): room in README `## Running it in production`.

From v1.647 the section's paragraph on `promote` (v1.605) and the one on `drift` (v1.635), its two
longest at 2,847 and 3,046 bytes, are cut, so later versions have room under v1.629's 30,000-byte cap
(tests/test_readme_production.py), which stays. Each keeps its lead claim, every API, command and
option name it gave, its quote and its links. Each clause it dropped is stated in DESIGN 4.7, 8.3 or
10: DROPPED pins it to the subsection and a phrase found there, the two that no subsection stated
(a chain of promotions losing up to k times the margin, and the pairs a margin needs) being added to
4.7 as v1.647. DROPPED was made from a word diff of v1.646's two paragraphs (8c53538) against v1.647's:
every run of words the diff shows as removed is in an entry, as v1.646 wrote it, and what the diff
keeps is the lead sentences, the names in NAMES, the quotes and links in LINKS and the clauses
tests/test_promote_docs.py and tests/test_drift_docs.py pin (review iter-502 must-fix 1, should-fix 2).
The README pins of the docs modules that read the two paragraphs are restated to the new text, and
each fails on v1.646's README. A docs slice: no package module, evidence file or README transcript
changes; these tests failed on v1.646's README and pass on v1.647's.

DESIGN 5.2 v1.648 (row PROD1gb, second part): the paragraph on self-hosted rows, the one on the prompt
cache and the first on shadows are cut the same way, from 2,002, 2,133 and 2,040 bytes to 1,568, 1,798
and 1,728. DROPPED_V1_648 was made from a word diff of v1.647's three paragraphs (aff2625) against
v1.648's: every run of words it shows as removed is in an entry, as v1.647 wrote it, pinned to 4.1,
5.2, 6, 7 or 11, each a behavioural subsection, so no subsection gains a clause. The three keep every
name in backticks they gave (NAMES_V1_648), their quotes and links. These tests failed on v1.647's
README and pass on v1.648's.

DESIGN 5.2 v1.649 (row PROD1gbb, third part): the paragraph on variants, the one on procedures and the
second on shadows, on their records and pairs, are cut the same way, from 1,825, 1,735 and 1,750 bytes
to 1,506, 1,429 and 1,607. DROPPED_V1_649 was made from a word diff of v1.648's three paragraphs
(139c8b6) against v1.649's: every run of words it shows as removed is in an entry, pinned to 4.1, 4.3,
4.5, 5.2, 6, 7, 8.3 or 11, each a behavioural subsection, so no subsection gains a clause. The three
keep every name in backticks they gave (NAMES_V1_649), their quotes and links. The pinned-call
paragraph is left whole, as tests/test_pin_docs.py reads every hard check's words in it (review
iter-495 must-fix 1). These tests failed on v1.648's README and pass on v1.649's.

DESIGN 5.2 v1.650 (row PROD1gbbb, fourth part): the paragraph on the latency bar and the two on budgets
are cut the same way, from 1,709, 1,566 and 1,659 bytes to 1,473, 1,268 and 1,562, each by deleting
clauses, the latency one also writing "a parent whose" for "the delegate keeps the bar, and so does a
parent: one whose". DROPPED_V1_650 holds each deleted clause as v1.649 (4551ee2) wrote it, pinned to
4.3, 4.6, 5.2, 7 or 8.3, each a behavioural subsection, so no subsection gains a clause. The three keep
every name in backticks they gave (NAMES_V1_650), their quotes and links. These tests failed on
v1.649's README and pass on v1.650's.

DESIGN 5.2 v1.651 (row PROD1gbbbb, fifth part): the paragraph on task scopes, the one on a tenant's policy and
the one on pinned calls are cut the same way, from 1,176, 1,316 and 1,779 bytes to 909, 1,212 and 1,751, each
by deleting clauses, the task-scope one also writing "On a task none of them matches," for "On any other task"
(review iter-506 should-fix 3); the policy one keeps the shadow call and the parent it rules out (should-fix 1
and 2). DROPPED_V1_651 holds each deleted clause as v1.650 (a7d6530) wrote it, pinned to 5.2 or 7, each a
behavioural subsection, so no subsection gains a clause. The three keep every name in backticks
they gave (NAMES_V1_651), their quotes and links, and the pinned-call one every hard check's words, which
tests/test_pin_docs.py reads (review iter-495 must-fix 1). These tests failed on v1.650's README and pass on
v1.651's.

DESIGN 5.2 v1.652 (row PROD1gbbbbb, sixth part): nine paragraphs that v1.647 to v1.650 trimmed are cut again, from
15,176 bytes to 14,010, so the section is 23,992 bytes, at most row PROD1g's 24,000. DROPPED_V1_652 holds each
deleted clause as v1.651 (2c8b0c7) wrote it, pinned to 4.1, 4.3, 4.6, 4.7, 5.2, 7, 8.1, 8.3 or 11, each a
behavioural subsection, so no subsection gains a clause. The v1.647 to v1.650 tests hold each paragraph they
trimmed and v1.652 cut again to at most the bytes they left it, and the two v1.652 left alone (procedures, the
first on budgets) to those bytes exactly (review iter-507 should-fix 2); their names and links tests still run on
all nine. These tests failed on v1.651's
README and pass on v1.652's.

DESIGN 5.2 v1.653 (row PROD1h): two caveats v1.652 dropped come back in short form where each claim is made, the
latency one (a trial's time runs from your call to the route's answer, a monitor record's is one attempt's) and
the self-hosted one (the throughputs describe one workload, the hour's split is an approximation), with two
qualifiers review nits asked for (`promote`'s list prices, the variants' token counts). Eight clauses leave the
section to pay for them, each pinned in DROPPED_V1_653 to the line of 4.1, 4.2, 4.3, 4.7, 7, 8.2 or 11 that states
it, so the section is 23,976 bytes, at most 24,000; a rotated log's order and the shadow rate's default stay
(review iter-508 must-fix 1 and should-fix 1). The v1.647 and v1.652 lists lose the entries v1.653 brings back.
These tests failed on v1.652's README and pass on v1.653's.

DESIGN 5.2 v1.654 (row OPP1c): the sentence on `report --opportunities` ends the section, in the room row PROD1g
made under v1.629's cap (tests/test_opportunities_docs.py), so the v1.652 and v1.653 tests hold the section less
that sentence's paragraph and its blank line to the bytes they set, at most 24,000 and 23,976.

DESIGN 5.2 v1.655 (row T30): the v1.652 and v1.653 tests take out one list, LATER, of the paragraphs added
after v1.653, each with its own bytes and its blank line, so a slice that adds a paragraph appends one entry;
one test alone names the section's last paragraph, and the docs modules place a paragraph by the one next to
it, never by a count from the section's end. LATER's entries since: v1.656's sentence on `keep_records`
(row PROD1b), v1.657's on calls from a coroutine (DESIGN 7, row PROD1e) and v1.658's on the record format
(DESIGN 8.1, row LOG1), the section's last; v1.659's two paragraphs of the walk-through (row PROD1), its
sentence and its list of steps, the section's first after its lead.

DESIGN 5.2 v1.664 (row PROD1ia, the first part of row PROD1i): the walk-through's sentence and its ten steps are cut
from 143 and 3,364 bytes to 115 and 3,088, each step keeping the names tests/test_readme_walkthrough.py `TOPICS`
pins, its commands and its lesson's anchor (ANCHORS_V1_659), so LATER's two v1.659 entries are restated and
DROPPED_V1_664 pins each dropped clause to the phrase of DESIGN 5.2 that states it. These tests failed on v1.663's
README and pass on v1.664's.

DESIGN 5.2 v1.665 (row PROD1iba, the first part of row PROD1ib): the paragraph on `drift` and the first on shadows are
cut again, from 1,921 and 1,610 bytes to 1,741 and 1,527, so the section is 29,385 bytes. Each keeps its lead, every
name in backticks (NAMES, NAMES_V1_648), its quote and links and every clause an earlier test keeps on purpose;
DROPPED_V1_665 holds each clause it drops or rewords, as v1.664 (76aa0e3) wrote it, pinned to the line of 7, 8.3 or 10
that states it, a pronoun or a moved phrase aside. The v1.652 and v1.653 tests hold the two at v1.665's bytes. These
tests failed on v1.664's README and pass on v1.665's.

DESIGN 5.2 v1.666 (row PROD1ibba, the first part of row PROD1ibb): the paragraph on `promote` and the one on pinned
calls are cut again, from 1,708 and 1,751 bytes to 1,628 and 1,724, so the section is 29,278 bytes. Each keeps its
lead, every name in backticks (NAMES, NAMES_V1_651), its quote and links and every clause an earlier test keeps;
DROPPED_V1_666 holds each clause it drops or rewords, as v1.665 (48a41e9) wrote it, pinned to the line of 4.7, 5.2,
7 or 10 that states it. These tests failed on v1.665's README and pass on v1.666's.

DESIGN 5.2 v1.673 (row PROD1ibbba, the first part of row PROD1ibbb): the second paragraph on budgets and the one on
the prompt cache become pointer paragraphs by row PROD1ibbb's rule, from 1,455 and 1,586 bytes to 397 and 394, so the
section is 27,028 bytes. Each keeps its lead sentence, its option's names in backticks and its one `DESIGN.md`
pointer (POINTERS_V1_673), at most 400 bytes; DROPPED_V1_673 pins each clause and name it drops, as v1.666 (def0b69)
wrote it, to the line of 3, 4.1, 4.3, 4.6, 5.1, 5.2, 6, 7, 8.3 or 10 that states it, and QUOTES_V1_673 each quote to
the note's lesson that keeps it. The v1.648 and v1.650 names tests leave the two to these tests. These tests failed
on v1.666's README and pass on v1.673's.

DESIGN 5.2 v1.674 (row PROD1ibbbb, the second part of row PROD1ibbb): the paragraph on self-hosted rows becomes a
pointer paragraph by the same rule, from 1,450 bytes to 368, so the section is 25,946 bytes, at most row PROD1i's
26,000. It keeps its lead and the sentence after it, which names the option, a fine-tune's `"base_model"` and
`"deployment"` and its one `DESIGN.md` pointer (POINTERS_V1_674); DROPPED_V1_674 pins each clause and name it drops,
as v1.673 (23b02ba) wrote it, to the line of 4.1, 5.1, 5.2, 8.1, 8.3, 10 or 11 that states it, the lesson's link and
the Harvey sentence's qualifier to the Why that 4.1's v1.581 line gains (review iter-532 must-fix 1 and 2), and
QUOTES_V1_674 Harvey's quote to its lesson. The v1.648 names test leaves it to these tests. These tests failed on v1.673's README and pass on v1.674's.
"""

from pathlib import Path

import pytest
from test_readme_production import PRODUCTION, PRODUCTION_CAP, paragraphs, size

ROOT = Path(__file__).resolve().parents[1]
PROMOTE_LEAD = "Judge a challenger route against the current one only on the items both were graded on. "
DRIFT_LEAD = ("A route's success can drift while its all-time counts still admit it, since a provider can change "
              "the model behind an ID. ")
# v1.646 (8c53538): each paragraph's UTF-8 bytes and its names in backticks, in their first order
OLD_BYTES = {PROMOTE_LEAD: 2_847, DRIFT_LEAD: 3_046}
NAMES = {
    PROMOTE_LEAD: ["calibrate --outcomes FILE",
                   "model-routing promote --task T --challenger ROUTE --margin M --outcomes FILE", "select",
                   "promote", "--alpha", "-M", "hold", "insufficient_overlap", "min_samples", "DESIGN.md",
                   "pair_outcomes", "current", "paired_promotion", "cost_effective", "cost_blind", "retry_same"],
    DRIFT_LEAD: ["model-routing drift --log PATH --audits PATH [--window 30d]", "report --audits", "--stats FILE",
                 "ok", "min_samples", "fell_below", "rose_above", "--json",
                 "select --window 30d --log PATH --audits PATH", "--stats", "DESIGN.md", "max_p95_ms",
                 "select --window", "drift", "latency_flag", "went_over", "came_under"],
}
LINKS = {
    PROMOTE_LEAD: ["(https://doi.org/10.3102/1076998611411915)",
                   "(research/production-lessons.md#switch-models-only-on-locked-data-and-a-significant-result)",
                   "Harvey compares models on fixed sets: \"once a collection of evaluation samples is \u201cpublished,\u201d"],
    DRIFT_LEAD: ["(research/production-lessons.md#test-a-model-before-the-switch-and-re-run-the-tests-on-the-models-in-"
                 "production-every-day)",
                 "GitHub runs its tests on the models it serves: \"We also run these tests against our production "
                 "models every day."],
}
# Each clause v1.647 dropped, as v1.646's paragraph wrote it, the DESIGN subsection that states it, and
# a phrase of that subsection that says it.
DROPPED = [
    (PROMOTE_LEAD, "and two routes measured on different labeled items cannot be told apart by their bounds", "### 4.7 ",
     "two success rates measured on different labeled items cannot be told apart by their bounds"),
    (PROMOTE_LEAD, "to FILE, apart from the stats, and", "## 10. ",
     "Then it writes the stats file as it does without the option and appends each record to FILE"),
    (PROMOTE_LEAD, "so two routes pair only when one results file graded both", "### 4.7 ",
     "so two routes pair only when that one file graded both"),
    # v1.653 (row PROD1h) brings back "cheaper per item at list prices" (review iter-502 nit 3), so it leaves this list
    (PROMOTE_LEAD, "(the adjusted Wald interval of [Bonett and Price, 2012]", "### 4.7 ",
     "the adjusted Wald interval of Bonett and Price (2012)"),
    (PROMOTE_LEAD, "each promotion against the route before it can lose up to M by the interval's reading", "### 4.7 ",
     "can lose up to `margin` at each step by the interval's reading, so k of them up to k times `margin` against "
     "the first route"),
    (PROMOTE_LEAD, "`promote` always pairs with `select`'s primary", "### 4.7 ",
     "since `promote` (10 v1.603) pairs with `select`'s primary"),
    (PROMOTE_LEAD, "at 30 pairs it is -0.0866 with no discordant pair and -0.1500 with two each way", "### 4.7 ",
     "it is -0.0866 at 30 pairs with no discordant pair and -0.1500 with two each way"),
    (PROMOTE_LEAD, "a cheaper challenger needs 91 pairs to clear a margin of 0.03 with no discordant pair and 442 with "
     "5% of the pairs going each way, and never fewer than the task's `min_samples`", "### 4.7 ",
     "gives `promote` from 91 pairs with no discordant pair and from 442 with 5% of the pairs going each way"),
    (PROMOTE_LEAD, "whose primary is the cheapest per success", "## 10. ",
     "whose primary is the cheapest per success (5.3 v1.567)"),
    (PROMOTE_LEAD, "Calibrate each labeled file once, since a second run doubles the trials the admission reads while "
     "the pairs count each item once", "## 10. ",
     "A results file calibrated twice counts its trials twice in the stats (v1.602 above) while `pair_outcomes` "
     "counts each repeated item once"),
    (PROMOTE_LEAD, "at a false-promotion rate of at most about 0.05", "## 10. ",
     "at a family-wise rate of at most about A passes `--alpha` A / k (Bonferroni)"),
    (DRIFT_LEAD, "the last N UTC days, today included,", "## 10. ", "the N UTC days that end with the command's date"),
    # review iter-502 must-fix 1: the next three are pinned to the `audited_results` bullets `drift` reads
    (DRIFT_LEAD, "so a route whose rejected answers a fallback then made good still pays for them", "### 8.3 ",
     "So a route whose answers the check rejects, and a fallback then answers, counts those trials too"),
    (DRIFT_LEAD, "so a window under `min_samples` trials flags nothing", "### 8.3 ",
     "So a window under `min_samples` trials flags nothing"),
    (DRIFT_LEAD, "so a route measured at 0.92 all-time whose audited calls in the window succeed at 0.70 loses "
     "admission there", "## 10. ",
     "so a route measured at 0.92 all-time whose audited calls in the window succeed at 0.70 loses admission there"),
    (DRIFT_LEAD, "the window's calls are among its calls, so the all-time bound moves toward the window's as the "
     "window grows", "### 8.3 ", "so the all-time bound moves toward the window's as the window grows"),
    (DRIFT_LEAD, "audits picked by a rule other than chance bias every route's rate", "### 8.3 ",
     "an audit file that picks calls by a rule other than chance biases every route's rate"),
    (DRIFT_LEAD, "counts once for the cascade, with whether it handed up", "### 8.3 ",
     "`item`, `correct`, `escalated` the record's"),
    (DRIFT_LEAD, "at its model calls' and tools' cost", "### 8.3 ",
     "for a procedure, the records of its model calls and its closing record, which holds its tool cost"),
    (DRIFT_LEAD, "Each audited call's row also carries its route's time", "### 8.3 ",
     "Each row now carries `latency_ms`, which `calibrate_from_results` reads as its one trial's time"),
    (DRIFT_LEAD, "(a cascade's legs summed,", "### 8.3 ",
     "a cascade's row the `math.fsum`, in log order, of the `latency_ms` of the entry's records that v1.636 checks"),
    (DRIFT_LEAD, " a procedure's whole run)", "### 8.3 ",
     "a procedure's row its closing record's alone, which times the whole run"),
    (DRIFT_LEAD, "`latency_flag`, kept apart from the success flag: `went_over` when the window's p95, over at least "
     "`min_samples` timed calls, is over the bar while the all-time side keeps the route in", "### 8.3 ",
     "`latency_flag` is `went_over` when the all-time side is on time and the window's p95, not None, is over the bar"),
    (DRIFT_LEAD, "`came_under` the other way", "### 8.3 ",
     "`came_under` when the all-time side is not on time (its p95 over the bar, or none under `\"deny\"`)"),
    (DRIFT_LEAD, ", kept apart from the success flag:", "## 10. ",
     "the table gains, after `flag`, the columns `all_time_p95_ms`, `window_p95_ms`"),
    (DRIFT_LEAD, "when the all-time side comes from the same log, as it does without `--stats`,", "### 8.3 ",
     "when both `Stats` come from one log, the window's calls are among the all-time ones"),
    (DRIFT_LEAD, "and each bound is at the task's confidence", "### 8.3 ",
     "each row's bounds are each at the task's confidence, so over many keys some flags come by chance"),
    (PROMOTE_LEAD, "once a challenger is promoted on non-inferiority, check the next one against the first route, not "
     "the promoted one", "### 4.7 ", "a caller checks each later challenger against the first route"),
    (PROMOTE_LEAD, "The bound is wide on few pairs:", "### 4.7 ", "The bound is wide on few pairs: at the default `alpha`"),
]
# v1.648 (row PROD1gb, second part): three more paragraphs, as v1.647 (aff2625) wrote them
SELF_LEAD = "A model you train or serve yourself is a row priced from its hour. "
CACHE_LEAD = "A prompt cache changes what a call costs, so a route is priced at the cache hits it measured. "
SHADOW_LEAD = ("A share of routed calls can also go to a reference route, so a quality loss nobody labelled "
               "shows up in pairs to label. ")
OLD_BYTES_V1_648 = {SELF_LEAD: 2_002, CACHE_LEAD: 2_133, SHADOW_LEAD: 2_040}
NEW_BYTES_V1_648 = {SELF_LEAD: 1_568, CACHE_LEAD: 1_798, SHADOW_LEAD: 1_728}
NAMES_V1_648 = {
    SELF_LEAD: ["models.json", '"pricing_basis": "self_hosted"', "usd_per_hour", "tokens_per_hour_in",
                "tokens_per_hour_out", "utilization", "input_cost_share", '"base_model"', '"deployment"', "api",
                "self_hosted", "select", "pricing_basis", "report --by pricing_basis", "DESIGN.md",
                "model_routing.demo.run_self_hosted_demo()"],
    CACHE_LEAD: ["models.json", "price_cached_in", "price_cache_write", "price_tiers", "cache_price_unknown",
                 "cached_input_tokens", "cache_write_tokens", "input_tokens", "output_tokens", "cost_breakdown",
                 "--cached-read-ratio", "OpenAICompatibleProvider", "usage.prompt_tokens_details.cached_tokens",
                 "report --cache", "cache_hit_rate", "usage.input_tokens", "cache_read_input_tokens",
                 "cache_creation_input_tokens", "DESIGN.md"],
    SHADOW_LEAD: ["shadow_rate", "shadow_route", "Executor(..., random=...)", "model", 'shadow: "true"',
                  'tags={"shadow": "true"}', "report", "report --shadow", "shadow_calls", "shadow_failed_calls",
                  "shadow_cost_usd", "shadow_runner", ".call", "Executor(..., shadow_runner=pool.submit)", "pool",
                  "ThreadPoolExecutor", "pool.shutdown(wait=True)", "DESIGN.md"],
}
LINKS_V1_648 = {
    SELF_LEAD: ["(research/production-lessons.md#your-own-trained-model-is-a-candidate-kept-to-the-tasks-it-was-"
                "measured-on)",
                "\"completes tasks competitively with leading frontier models while reducing cost per query by 90%.\""],
    CACHE_LEAD: ["(research/production-lessons.md#the-cache-hit-rate-is-a-cost-number)",
                 "Manus: \"If I had to choose just one metric, I'd argue that the KV-cache hit rate is the single most "
                 "important metric for a production-stage AI agent.\""],
    SHADOW_LEAD: [],
}
DROPPED_V1_648 = [
    (SELF_LEAD, "what an hour of one serving unit costs you", "### 4.1 ",
     "prices derived from what an hour of the caller's own serving costs"),
    (SELF_LEAD, "what that unit reads and writes in an hour of full use on this work", "### 4.1 ",
     "the tokens one serving unit reads, or writes, in an hour of full use on this work"),
    (SELF_LEAD, "the share of the hour it spends on this work", "### 4.1 ",
     "`utilization` (the share of the hour the unit spends on this work)"),
    (SELF_LEAD, "and `input_cost_share`, the share of the hour charged to input", "### 4.1 ",
     "`input_cost_share` (the share of the hour charged to input)"),
    (SELF_LEAD, "admitted on its own measured success against the task's bar, then ranked at what its hour costs you",
     "### 4.1 ", "so an hour fully used at those throughputs is charged once, its input share on input tokens and "
     "the rest on output tokens, and the routing math of 5.2 is unchanged"),
    (SELF_LEAD, "since a unit that reads and writes in the same hour has no one price per token of each", "### 4.1 ",
     "is an approximation the caller chooses: a unit that reads and writes in the same hour has no one price per "
     "token of each"),
    (SELF_LEAD, "and it is never a judge of its base's output", "## 11. ", "and it never judges its base's output"),
    (CACHE_LEAD, "uncached input, cached reads, cache writes and output each at its own price", "### 4.1 ",
     "cached_input_tokens * r + cache_write_tokens * w + output_tokens * p_out"),
    (CACHE_LEAD, "and a write premium can make caching the dearer choice on a prompt read once", "### 4.1 ",
     "A write premium can make caching lose"),
    (CACHE_LEAD, "A cascade's legs are priced at their own models' counts", "### 5.2 ",
     "A cascade (7 v1.536) prices each leg at its own model's counts"),
    (CACHE_LEAD, "and so is the model of a procedure without a measured mean cost", "### 5.2 ",
     "A procedure (v1.577) without a mean cost prices its model's one call at the task's or slice's expected sizes "
     "at that model's counts"),
    (CACHE_LEAD, "with the last two as the cached and written counts", "## 6. ",
     "`cache_read_input_tokens` as `cached_input_tokens` and `cache_creation_input_tokens` as `cache_write_tokens`"),
    (SHADOW_LEAD, "must pass the task's hard rules but", "## 7. ", "its candidate is `eligible` (5.1: the hard rules"),
    (SHADOW_LEAD, "and a call whose primary is the shadow route is not shadowed", "## 7. ",
     "a shadow route exists, it is not the decision's primary"),
    (SHADOW_LEAD, "by a fallback or a cascade's hand-up onto it", "## 7. ",
     "a fallback onto it included (a below-bar fallback too, 5.3), or a cascade leg of it, a hand-up onto a "
     "cascade's `strong` included"),
    (SHADOW_LEAD, "since its pair would compare that model with itself", "## 7. ",
     "its pair would compare that model with itself"),
    (SHADOW_LEAD, "and spares the call the shadow's wait and its errors", "## 7. ",
     "the caller waits for the hand-off and not for the shadow's provider call"),
    (SHADOW_LEAD, "while a runner that runs the job at once waits as None does", "## 7. ",
     "makes `.call` wait for the shadow as None does"),
]
# v1.649 (row PROD1gbb, third part): three more paragraphs, as v1.648 (139c8b6) wrote them
VAR_LEAD = "One model run two ways can be two routes. "
PROC_LEAD = "Recurring tool work can be a route of its own. "
RECORDS_LEAD = "Every record of a shadowed call carries `pair_id`, the routed call's ID, `shadow`, and `checked`, "
OLD_BYTES_V1_649 = {VAR_LEAD: 1_825, PROC_LEAD: 1_735, RECORDS_LEAD: 1_750}
NEW_BYTES_V1_649 = {VAR_LEAD: 1_506, PROC_LEAD: 1_429, RECORDS_LEAD: 1_607}
NAMES_V1_649 = {
    VAR_LEAD: ["models.json", '"variants": {"lean": {"harness": "lean-agent 2.0", "reasoning_effort": "low"}}',
               "vendor/model@lean", '"items_per_call": 4', "select", "items", "OpenAICompatibleProvider(model_map=...)",
               "DESIGN.md", "provider_options", '{"reasoning_effort": "high"}', "OpenAICompatibleProvider", "model",
               "messages", "anthropic/claude-sonnet-4", "openai/o3-mini-2025-01-31", "@medium", "@high"],
    PROC_LEAD: ["Procedure(name, version, fn, max_model_calls=..., max_tool_calls=..., model=...)",
                "proc:<name>@<version>+<model>", "select(..., procedures=[...])", "Executor.call(..., procedures=[...])",
                "validate", "procedure", "procedure_version", "model_calls", "tool_calls", "tool_cost_usd", "DESIGN.md",
                "model_routing.demo.run_procedure_demo()"],
    RECORDS_LEAD: ["pair_id", "shadow", "checked", ".call", "model-routing pairs --log PATH --out FILE", "--checked",
                   "--audits PATH", "--results RESULTS", "cost_usd", "calibrate --outcomes", "promote", "--challenger",
                   "--dataset-sha256", "--routes ROUTED SHADOW", "evaluate --outcomes", "escalated", "calibrate",
                   "evaluate", "DESIGN.md"],
}
LINKS_V1_649 = {
    VAR_LEAD: ["[LiveCodeBench's runs](evidence/livecodebench-variants/RESULTS.md)"],
    PROC_LEAD: ["(research/production-lessons.md#keep-tool-schemas-and-polling-out-of-the-models-context)",
                '"the loop runs in a subprocess, and only the summary comes back."'],
    RECORDS_LEAD: ["(research/production-lessons.md#test-a-model-before-the-switch-and-re-run-the-tests-on-the-models-"
                   "in-production-every-day)",
                   '"We also conduct live internal evaluations, similar to canary testing, where we switch a number of '
                   'Hubbers to use a new model."'],
}
DROPPED_V1_649 = [
    (VAR_LEAD, "listed right after its base", "### 4.1 ", "placed right after its base in the object's order"),
    (VAR_LEAD, "Excluding a model,", "### 5.2 ", "so excluding a base excludes its variants"),
    (VAR_LEAD, "or naming it as the generator, covers its variants", "### 5.2 ",
     "so a variant of the generator's model, and its base, have reason `generator`"),
    (VAR_LEAD, "each item is one trial carrying its whole call's token counts", "### 4.3 ",
     "carrying the token counts of the whole call that handled it"),
    (VAR_LEAD, "its mean call over 4", "### 5.2 ", "the mean of one call (4.3 v1.573), it is `model.cost` of them over k"),
    (VAR_LEAD, "unmeasured, it is priced as one call at the task's sizes", "### 5.2 ",
     "At the task's expected sizes it is that call's cost, undivided"),
    (VAR_LEAD, "the executor passes them to the provider", "## 7. ",
     "options=registry.get(model).provider_options)` when that model's `provider_options` (4.1) is not empty"),
    (VAR_LEAD, "which an option may not replace", "## 6. ", "An option never replaces a key the adapter sets"),
    # review iter-504 should-fix 1: 4.5 lists batch, not fetch, so the fetch has its own entry
    (PROC_LEAD, "such as submit, poll, fetch", "## 11. ",
     "each submit, poll and fetch one tool call at 0.00001 USD (`PROCEDURE_TOOL_COST_USD`)"),
    (PROC_LEAD, "and shape the result", "### 4.5 ", "a recurring job's fixed steps (submit, poll, batch, shape a result)"),
    (PROC_LEAD, "never on its model's", "### 5.2 ", "then rules 6 to 8 on its own counts under its own `.id`"),
    (PROC_LEAD, "its model calls at list price plus the tool cost it reports", "### 4.3 ",
     "per trial its model calls at list price plus its `tool_cost_usd`"),
    (PROC_LEAD, "and a new version starts with no runs", "### 5.2 ", "so a new version or another model starts at 0 trials"),
    (PROC_LEAD, "an agent route that polls by model turns with the raw rows in its context", "## 11. ",
     "each turn's input the context so far"),
    (PROC_LEAD, "a procedure that polls in code and sends its one model call only what it counted", "## 11. ",
     "Each then counts the rows and sums the amounts in code and makes one model call"),
    (RECORDS_LEAD, "which refuses a log whose shadowed calls ran none", "### 8.3 ",
     "saying its call ran no acceptance check (`validate`)"),
    (RECORDS_LEAD, "so label such a log", "### 8.3 ", "and pointing to `audits` or no label instead"),
    (RECORDS_LEAD, "An error side is never labelled", "### 8.3 ", "An `error` side gave no answer, so it is None under both"),
    # review iter-504 must-fix 1: the pair rows' item (8.3 v1.613), not `calls_results`' own call ID
    (RECORDS_LEAD, "and the routed call's ID as its item", "### 8.3 ",
     "The item is the `pair_id`, the routed call's ID, so the two rows of a pair are one item graded on both routes"),
]
# v1.650 (row PROD1gbbb, fourth part): three more paragraphs, as v1.649 (4551ee2) wrote them
LAT_LEAD = "A task can also hold its routes to a time. "
BUDGET_LEAD = "A budget tracks what the executor spends and can warn, refuse or move a call. "
EST_LEAD = "The estimate is no bound: "
OLD_BYTES_V1_650 = {LAT_LEAD: 1_709, BUDGET_LEAD: 1_566, EST_LEAD: 1_659}
NEW_BYTES_V1_650 = {LAT_LEAD: 1_473, BUDGET_LEAD: 1_268, EST_LEAD: 1_562}
NAMES_V1_650 = {
    LAT_LEAD: ["tasks.json", '"max_p95_ms"', "too_slow", "min_samples", '"latency_unknown": "deny"', "latency_unknown",
               "ceil(0.95 * n) - 1", "n", "latency_ms", "model-routing calibrate", "Stats.add(..., latencies_ms=[...])",
               "report(records, shadow=True)", "model-routing report --shadow", "shadow", "true", "report",
               "select --json", "delegate --json", "max_p95_ms", "p95_latency_ms", "null", "deny", "delegate",
               "parent_too_slow", "parent_latency_unknown"],
    BUDGET_LEAD: ['Budget(name, limit_usd, mode, window="total", task=None, tags={})', "task", "tags", "window",
                  "total", "day", "month", "load_budgets(path)", "Executor(..., ledger=BudgetLedger(budgets))",
                  "prompt_tokens", "expected_output_tokens", "warn", "refuse", "BudgetExceeded", "downgrade"],
    EST_LEAD: ["refuse", "strict=True", "billing_bound", "max_tokens", "max_completion_tokens", "max_output_tokens",
               "provider_options", "report", "budget_report(records, budgets)", "budget_used_pct",
               "model-routing demo --budgets FILE", "DESIGN.md"],
}
LINKS_V1_650 = {
    LAT_LEAD: [],
    BUDGET_LEAD: [],
    EST_LEAD: ["[Monitoring and cost attribution](#monitoring-and-cost-attribution)",
               "(research/production-lessons.md#spend-tiers-and-nudges-not-strict-caps)",
               '"To avoid imposing strict caps, we implemented real-time spend tracking and automated nudges"',
               '"Alerts at 50/80/100% of expected spend so engineers have time to plan."'],
}
DROPPED_V1_650 = [
    (LAT_LEAD, "after the task's and the policy's rules and", "### 5.2 ",
     "Why after 5d: a route the task, the call or the policy already rules out keeps its v1.627 reason"),
    (LAT_LEAD, "not its models'", "### 5.2 ", "are judged on their own key's times, never their models'"),
    (LAT_LEAD, "(on a sliced call, the slice's trials and `min_samples`)", "### 5.2 ",
     "at least `min_samples` times, the task's or on a sliced call the slice's"),
    (LAT_LEAD, "it is a time a trial took", "### 4.3 ", "so it is a time one of the trials took"),
    (LAT_LEAD, "and a call that falls back makes several", "### 4.3 ",
     "is one attempt's, and a call that falls back makes several"),
    (LAT_LEAD, "the delegate keeps the bar", "### 5.2 ", "`decide_delegation`'s delegate keeps the bar (13.3 v1.628)"),
    (BUDGET_LEAD, "so one budget can pool a team's tools on a shared tag while another caps one tool", "### 4.6 ",
     'one on `{"tool": "a"}` only the calls tagged so'),
    (BUDGET_LEAD, "each window's spend kept apart", "### 4.6 ", "a hold of one window never counts against another"),
    (BUDGET_LEAD, "a fallback's, a cascade leg's, a procedure's model call and a hand-off's included", "## 7. ",
     "a cascade's cheap or strong leg or a procedure's model call, from `.call` or `.call_delegated`"),
    (BUDGET_LEAD, "so tokens a provider bills for a failed call are in no budget", "## 7. ",
     "so tokens a provider bills for a failed call are in no budget"),
    (BUDGET_LEAD, "and no later route entry is tried", "## 7. ", "No later route entry is tried"),
    (EST_LEAD, "or pays a cache-write price", "## 7. ", "or pays a cache-write price costs more than its hold"),
    (EST_LEAD, "a procedure's included", "## 7. ",
     "Before a procedure entry's run, a strict budget that applies refuses the entry"),
    (EST_LEAD, "whose cost is then unknown", "### 4.6 ", "releases the hold of a call whose cost is not known"),
    (EST_LEAD, "`budget_used_pct` in each window", "### 8.3 ",
     "gives each budget's spend in each window as a percent of its limit"),
]
# v1.651 (row PROD1gbbbb, fifth part): three more paragraphs, as v1.650 (a7d6530) wrote them
SCOPE_LEAD = 'A model built for some tasks can be kept to them. '
POLICY_LEAD = "A tenant's rules hold whatever a route costs. "
PIN_LEAD = 'A call can also pin its route. '
OLD_BYTES_V1_651 = {SCOPE_LEAD: 1_176, POLICY_LEAD: 1_316, PIN_LEAD: 1_779}
NEW_BYTES_V1_651 = {SCOPE_LEAD: 909, POLICY_LEAD: 1_212, PIN_LEAD: 1_751}
NAMES_V1_651 = {
    SCOPE_LEAD: [
        'models.json', '"scope_tasks"', '["review_*"]', '@', '<task>@<slice>', 'out_of_scope', 'DESIGN.md'],
    POLICY_LEAD: [
        'Policy(allowed_routes=None, allowed_families=None, region=None, require_zdr=False, name=None)', 'policy=',
        'select', 'Executor.call', 'decide_delegation', 'select --policy FILE', 'delegate --policy FILE',
        'models.json', 'region', 'regions', 'require_zdr', '"zero_data_retention": true', 'policy_excluded',
        'region_unavailable', 'zdr_required', 'zero_data_retention', 'Executor', 'policy', 'name',
        'report --by policy', 'call_delegated'],
    PIN_LEAD: [
        'Executor.call(..., pin_route=ROUTE, pinned_by=TAG)', 'signals', 'procedures',
        'select(..., pin_route=ROUTE)', 'basis', 'pinned', 'DESIGN.md', 'NoModelClearsBar', 'allow_below_bar',
        'region', 'require_zdr', 'deny', 'allow_below_bar=True', 'below_bar', 'true', 'AllModelsFailed', 'downgrade',
        '.call', 'pinned_by', 'report --by basis', 'measured', 'prior', 'report --by pinned_by', '(none)'],
}
LINKS_V1_651 = {
    SCOPE_LEAD: ["(research/production-lessons.md#your-own-trained-model-is-a-candidate-kept-to-the-tasks-it-was-"
                 "measured-on)",
                 '"These capabilities are each trained separately and can be deployed as tools and sub-agents that '
                 'our model can route to in order to tackle specific tasks."'],
    POLICY_LEAD: [],
    PIN_LEAD: ["[Limitations](#limitations-and-non-goals-v1)"],
}
DROPPED_V1_651 = [
    (SCOPE_LEAD, "and any other against the task", "### 5.2 ",
     "a pattern without `@` is matched against the task's name and a pattern with `@` against the `<task>@<slice>` key"),
    (SCOPE_LEAD, "so a pattern with `@` keeps the model to one slice", "### 5.2 ",
     "a pattern such as `support@deep` or `*@deep` to that slice alone"),
    (SCOPE_LEAD, "not at cold start, as a fallback or as the best available model, whatever its counts", "### 5.2 ",
     "it is never the primary, a fallback, a below-bar fallback or a `best_available` measured or prior pick, so it "
     "gets no cold-start call on a task outside its scope, whatever its counts or prior"),  # review iter-506 nit 1
    (SCOPE_LEAD, "and on a slice by that slice's counts", "### 5.2 ", "and on a sliced call by that slice's counts alone"),
    (SCOPE_LEAD, "so a model whose gains differ by part of a task is checked on each part", "### 5.2 ",
     "a model scoped to a task clears the bar on each slice it serves"),
    (POLICY_LEAD, "a cascade's legs, a procedure's model", "## 7. ",
     "with a cascade's cheap and strong models and a procedure's named model, each of which met rules 5b to 5d"),
    (POLICY_LEAD, "a budget's downgrade", "## 7. ",
     "a move goes along that route only, so it never lands on a model the policy ruled out"),
    (POLICY_LEAD, "and a value a row leaves out fails closed", "### 5.2 ",
     "So a value the registry does not state fails closed"),
    (PIN_LEAD, "without ranking the routes", "### 5.2 ",
     "the ranking of 5.3 is skipped: the pin is the decision's only entry"),
]
# v1.652 (row PROD1gbbbbb, sixth part): nine paragraphs an earlier part trimmed, as v1.651 (2c8b0c7) wrote them
OLD_BYTES_V1_652 = {PROMOTE_LEAD: 1_902, DRIFT_LEAD: 2_032, SELF_LEAD: 1_568, CACHE_LEAD: 1_798, SHADOW_LEAD: 1_728,
                    RECORDS_LEAD: 1_607, VAR_LEAD: 1_506, LAT_LEAD: 1_473, EST_LEAD: 1_562}
NEW_BYTES_V1_652 = {PROMOTE_LEAD: 1_693, DRIFT_LEAD: 1_921, SELF_LEAD: 1_382, CACHE_LEAD: 1_586, SHADOW_LEAD: 1_641,
                    RECORDS_LEAD: 1_475, VAR_LEAD: 1_468, LAT_LEAD: 1_389, EST_LEAD: 1_455}
TARGET = 24_000  # row PROD1g: the section at most 24,000 bytes, 6,000 under PRODUCTION_CAP, which stays
DROPPED_V1_652 = [
    (PROMOTE_LEAD, "The Wilson bar admits each route on its own counts, so a challenger that clears it can still do worse",
     "### 4.7 ", "a route the Wilson bound admits may still do worse than the route it would replace on the same items"),
    (PROMOTE_LEAD, "so the check complements the bar and never replaces it", "### 4.7 ",
     "It complements the bar and never replaces it"),
    (DRIFT_LEAD, "and a cascade's or a procedure's audited call counts once for its route", "### 8.3 ",
     "So an audited call that a cascade or a procedure answered counts once for that route"),
    (DRIFT_LEAD, "and which calls to audit stays yours", "### 8.3 ", "so which calls to audit stays the caller's"),
    # v1.653 (row PROD1h) brings back the one workload and the hour's split (review iter-507 should-fix 3)
    (SELF_LEAD, "and the same hour used 2% of the time makes it the dearer route", "## 11. ",
     "the same hour used a fiftieth of the time makes it the dearer route"),
    (CACHE_LEAD, "so a model that is cheaper per token but never hits the cache can cost more than a pricier one", "### 5.2 ",
     "a model that is cheaper per token but never hits the cache can cost more per call"),
    (CACHE_LEAD, "each attempt is priced at the counts its provider returned", "## 7. ",
     "each attempt is priced at the counts its provider returns"),
    # review iter-507 must-fix 1: that the record carries them is 8.1's record-key rule, not 7's price line
    (CACHE_LEAD, "and its record carries them", "### 8.1 ",
     "the cached reads and cache writes its provider returned for the call, inside the record's `input_tokens`"),
    (SHADOW_LEAD, "so a challenger can be shadowed before it is admitted", "## 7. ",
     "need not clear the bar, so a challenger can be shadowed before it is admitted"),
    (SHADOW_LEAD, "so the caller waits for it too", "## 7. ",
     "a shadowed call sends its shadow on the caller's thread before `.call` returns"),
    (RECORDS_LEAD, "Nothing reads a pair into the stats, so an unlabelled pair never changes a route", "### 8.3 ",
     "so an unlabelled pair never updates quality stats"),
    (RECORDS_LEAD, "as it needs rows of the cascade's two models too", "### 8.3 ",
     "needs a cascade's cheap and strong models in the matrix to route it by their rows"),
    (VAR_LEAD, "and an unmeasured variant starts cold", "### 4.3 ",
     "so a variant with no trials of its own is unmeasured (cold start, 5.3)"),
    # v1.653 (row PROD1h) brings back, in short form, that a trial runs from your call to the answer and a record's time is
    # one attempt's (review iter-507 should-fix 1)
    (EST_LEAD, "The ledger is one process's: a limit shared by many processes still needs a gateway", "### 4.6 ",
     "a limit shared by many processes still needs a gateway or the provider's own"),
]
ENDS = {"### 5.1 ": "\n### 5.2 ", "## 3. ": "\n## 4. ", "### 4.7 ": "\n## 5. ", "### 8.3 ": "\n## 9. ", "## 10. ": "\n## 11. ", "### 4.1 ": "\n### 4.2 ",
        "### 5.2 ": "\n### 5.3 ", "## 6. ": "\n## 7. ", "## 7. ": "\n## 8. ", "## 11. ": "\n## 12. ",
        "### 4.3 ": "\n### 4.4 ", "### 4.5 ": "\n### 4.6 ", "### 4.6 ": "\n### 4.7 ",
        "### 8.1 ": "\n### 8.2 ", "### 4.2 ": "\n### 4.3 ", "### 8.2 ": "\n### 8.3 "}


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def paragraph(lead):
    [found] = [p for p in paragraphs(read("README.md"), PRODUCTION) if p.startswith(lead)]
    return found


SAVINGS_LEAD = "A log also shows where a cheaper route, such as a procedure or a model of your own, would save most: "
# DESIGN 5.2 v1.655 (row T30): each paragraph added to the section after v1.653, in the order added, as its lead
# and its own bytes with its blank line; a slice that adds a paragraph appends its entry here
MONITOR_LEAD = "A monitor that runs for a service's life need not hold every record in memory: "
COROUTINE_LEAD = "A service built on an asyncio event loop calls the executor from a coroutine with "
FORMAT_LEAD = "A store that loads the log (a warehouse table or a dashboard) builds its schema from the record format: "
WALK_LEAD = "From a first call to steady state, each step with one lesson from "
STEPS_LEAD = "1. Define each task in `tasks.json` with its `bar` and `min_samples`, "
CONSENSUS_LEAD = "A team with no human labels can make them from its reference judges' recorded grades: "
CONSISTENCY_LEAD = "A judge can also be held to grading alike on reruns. "
PAIR_LEAD = "A delegating harness's root and sub-agent models can be routed as a pair: "
LATER = [
    (SAVINGS_LEAD, 714),  # v1.654, row OPP1c: 712 bytes and the blank line
    (MONITOR_LEAD, 370),  # v1.656, row PROD1b: 368 bytes and the blank line
    (COROUTINE_LEAD, 445),  # v1.657, row PROD1e: 443 bytes and the blank line
    (FORMAT_LEAD, 340),  # v1.658, row LOG1: 338 bytes and the blank line
    (WALK_LEAD, 117),  # v1.659, row PROD1: the walk-through's sentence, after the lead; 115 bytes from v1.664
    (STEPS_LEAD, 3090),  # v1.659, row PROD1: its ten steps, before the seven of v1.604; 3,088 bytes from v1.664
    (CONSENSUS_LEAD, 596),  # v1.663, row JUDGE1bbb: 594 bytes and the blank line
    (CONSISTENCY_LEAD, 829),  # v1.675, row JUDGE2c: 827 bytes and the blank line
    (PAIR_LEAD, 589),  # v1.680, row PROD1j: 587 bytes and the blank line, the section's last
]


def without_later(text):
    """`text` less each LATER paragraph and its blank line, wherever in the section it sits (row T30)."""
    for lead, size_with_blank in LATER:
        [later] = [p for p in paragraphs(text, PRODUCTION) if p.startswith(lead)]
        assert len(later.encode("utf-8")) + 2 == size_with_blank, lead
        assert text.count("\n\n" + later + "\n\n") == 1, lead
        text = text.replace("\n\n" + later + "\n\n", "\n\n", 1)
    return text


def subsection(design, heading):
    start = design.index("\n" + heading)
    return design[start:design.index(ENDS[heading], start)]


def test_the_two_paragraphs_are_shorter_and_the_section_under_its_cap():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES}
    # v1.652 (row PROD1gbbbbb) cuts both again, so each is at most the bytes v1.647 left it
    assert all(found[lead] <= left for lead, left in {PROMOTE_LEAD: 1_902, DRIFT_LEAD: 2_032}.items())
    assert sum(OLD_BYTES.values()) - sum(found.values()) >= 1_959
    assert size(read("README.md"), PRODUCTION) <= PRODUCTION_CAP == 30_000


def test_each_keeps_its_lead_its_names_its_quote_and_its_links():
    for lead in OLD_BYTES:
        text = paragraph(lead)
        names = []
        for name in text.split("`")[1::2]:
            if name not in names:
                names.append(name)
        assert [n for n in NAMES[lead] if n not in names] == [], lead
        for link in LINKS[lead]:
            assert text.count(link) == 1, link
        assert "\u2014" not in text and "\u2013" not in text


def test_each_dropped_clause_is_gone_and_its_design_subsection_states_it():
    design = read("DESIGN.md")
    assert len(DROPPED) == 29  # v1.653 takes one back
    for lead, clause, heading, phrase in DROPPED:
        assert clause not in paragraph(lead), clause
        assert phrase in subsection(design, heading), (heading, phrase)


def test_the_check_fails_on_a_clause_still_there_or_a_phrase_design_lacks():
    design = read("DESIGN.md")
    # v1.652 drops "so the check complements the bar and never replaces it" (DROPPED_V1_652); the exit stays
    # v1.666 (row PROD1ibba) says the exit in a shorter form (DROPPED_V1_666)
    assert "The bar must admit the challenger first, or it exits 3. " in paragraph(PROMOTE_LEAD)
    assert "k times M against the first route" not in subsection(design, "## 10. ")
    assert "-0.0866" not in subsection(design, "## 10. ") and "-0.0866" in subsection(design, "### 4.7 ")


def test_design_states_the_trim_the_two_new_clauses_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = design[design.index("\n### 5.2 "):design.index("\n### 5.3 ")]
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.647 README trim (row PROD1g, first part; ")]
    for kept in ("is cut from 2,847 to 1,902 bytes and the one on `drift` (v1.635) from 3,046 to 2,032",
                 "under v1.629's 30,000-byte cap, which stays",
                 "each clause it drops is stated in 4.7, 8.3 or 10",
                 "tests/test_readme_trim.py pins each dropped clause to its subsection and a phrase found there",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    four7 = subsection(design, "### 4.7 ")
    [new] = [line for line in four7.splitlines() if line.startswith("- v1.647 (row PROD1g, 5.2 v1.647: ")]
    # before v1.601's Not-in-this-version line, which tests/test_promote_docs.py pins as 4.7's last
    assert four7.index(new) < four7.index("\n- Not in this version: the labeled file's hash")
    assert len(new.encode("utf-8")) <= 6_000 and len(mine.encode("utf-8")) <= 6_000
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.647 (")]
    assert line.startswith("- v1.647 (2026-11-25): docs and tests (4.7, 5.2, row PROD1g). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.648 (row PROD1gb, second part) ------------------------------------------------------------

def test_the_three_paragraphs_are_shorter_and_the_section_under_its_cap():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_648}
    # v1.652 (row PROD1gbbbbb) cuts some of them again, so each is at most the bytes v1.648 left it
    # review iter-507 should-fix 2: one v1.652 left alone keeps its v1.648 bytes exactly
    assert all(found[lead] <= NEW_BYTES_V1_648[lead] if lead in NEW_BYTES_V1_652
               else found[lead] == NEW_BYTES_V1_648[lead] for lead in found)
    assert sum(OLD_BYTES_V1_648.values()) - sum(found.values()) >= 1_081
    assert size(read("README.md"), PRODUCTION) <= PRODUCTION_CAP == 30_000


def test_the_three_keep_their_leads_their_names_their_quotes_and_their_links():
    # v1.673 (row PROD1ibbba): the cache one is a pointer paragraph, which the v1.673 tests hold, and v1.674 (row
    # PROD1ibbbb) the self-hosted one, which the v1.674 tests hold
    for lead in [lead for lead in OLD_BYTES_V1_648 if lead not in {**POINTERS_V1_673, **POINTERS_V1_674}]:
        text = paragraph(lead)
        names = []
        for name in text.split("`")[1::2]:
            if name not in names:
                names.append(name)
        assert [n for n in NAMES_V1_648[lead] if n not in names] == [], lead
        for link in LINKS_V1_648[lead]:
            assert text.count(link) == 1, link
        assert "\u2014" not in text and "\u2013" not in text


def test_each_clause_the_three_dropped_is_gone_and_its_design_subsection_states_it():
    design = read("DESIGN.md")
    assert len(DROPPED_V1_648) == 18
    for lead, clause, heading, phrase in DROPPED_V1_648:
        assert clause not in paragraph(lead), clause
        assert phrase in subsection(design, heading), (heading, phrase)
        # a behavioural subsection, never a 5.2 history bullet of the README
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)


def test_the_v1_648_check_fails_on_a_clause_still_there_or_a_phrase_elsewhere():
    design = read("DESIGN.md")
    # kept on purpose: no behavioural subsection states it as the paragraph does
    assert "has no shadow record and gives no pair" in paragraph(SHADOW_LEAD)
    assert "so at a `shadow_rate` of 0.05 about one call in twenty is paid twice" in paragraph(SHADOW_LEAD)
    assert "has no one price per token of each" not in subsection(design, "## 7. ")
    assert "A write premium can make caching lose" not in subsection(design, "### 5.2 ")


def test_design_states_the_v1_648_trim_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.648 README trim (row PROD1gb, second part): ")]
    for kept in ("paragraph on self-hosted rows is cut from 2,002 to 1,568 bytes, the one on the prompt cache "
                 "from 2,133 to 1,798 and the first on shadows from 2,040 to 1,728",
                 "under v1.629's 30,000-byte cap, which stays",
                 "each clause it drops is stated in 4.1, 5.2, 6, 7 or 11, so no subsection gains one",
                 "tests/test_readme_production.py checks the two of the v1.604 move it trims",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    assert five2.index("\n- v1.647 README trim (") < five2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.648 (")]
    assert line.startswith("- v1.648 (2026-11-25): docs and tests (5.2, row PROD1g, second part). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.649 (row PROD1gbb, third part) ------------------------------------------------------------

def test_the_v1_649_three_are_shorter_and_the_section_under_its_cap():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_649}
    # v1.652 (row PROD1gbbbbb) cuts some of them again, so each is at most the bytes v1.649 left it
    # review iter-507 should-fix 2: one v1.652 left alone keeps its v1.649 bytes exactly
    assert all(found[lead] <= NEW_BYTES_V1_649[lead] if lead in NEW_BYTES_V1_652
               else found[lead] == NEW_BYTES_V1_649[lead] for lead in found)
    assert sum(OLD_BYTES_V1_649.values()) - sum(found.values()) >= 768
    assert size(read("README.md"), PRODUCTION) <= PRODUCTION_CAP == 30_000


def test_the_v1_649_three_keep_their_leads_their_names_their_quotes_and_their_links():
    for lead in OLD_BYTES_V1_649:
        text = paragraph(lead)
        names = []
        for name in text.split("`")[1::2]:
            if name not in names:
                names.append(name)
        assert [n for n in NAMES_V1_649[lead] if n not in names] == [], lead
        for link in LINKS_V1_649[lead]:
            assert text.count(link) == 1, link
        assert "\u2014" not in text and "\u2013" not in text


def test_each_clause_the_v1_649_three_dropped_is_gone_and_its_design_subsection_states_it():
    design = read("DESIGN.md")
    assert len(DROPPED_V1_649) == 19
    for lead, clause, heading, phrase in DROPPED_V1_649:
        assert clause not in paragraph(lead), clause
        # a behavioural subsection, never a 5.2 history bullet of the README
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)


def test_the_v1_649_check_fails_on_a_clause_still_there_or_a_phrase_elsewhere():
    design = read("DESIGN.md")
    # kept on purpose: no behavioural subsection states them as the paragraph does
    assert "once the outcomes file holds the two routes' outcomes from another file too" in paragraph(RECORDS_LEAD)
    # v1.652 drops "as it needs rows of the cascade's two models too", which 8.3's Use line states (DROPPED_V1_652)
    assert "which `calibrate` reads, while `evaluate` refuses them (`DESIGN.md` 8.3 and 10)." in paragraph(RECORDS_LEAD)
    assert "the post gives no count of what its checks caught" in paragraph(RECORDS_LEAD)
    assert "An option never replaces a key the adapter sets" not in subsection(design, "## 7. ")
    assert "each turn's input the context so far" not in subsection(design, "### 4.5 ")
    # review iter-504 must-fix 1: the `calls_results` Keys line names a call's own ID, never the pair's item
    [calls] = [line for line in subsection(design, "### 8.3 ").splitlines()
               if "`item`, the call ID, so `item_outcomes` (4.3 v1.602) reads the rows" in line]
    assert calls.startswith("  - Keys, in order: ") and "The item is the `pair_id`" not in calls


def test_design_states_the_v1_649_trim_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.649 README trim (row PROD1gbb, third part): ")]
    for kept in ("paragraph on variants is cut from 1,825 to 1,506 bytes, the one on procedures from 1,735 to 1,429 "
                 "and the second on shadows, on their records and pairs, from 1,750 to 1,607",
                 "so the section is 26,188 bytes by the 12.8 measure, under v1.629's 30,000-byte cap, which stays",
                 "each clause it drops is stated in 4.1, 4.3, 4.5, 5.2, 6, 7, 8.3 or 11, so no subsection gains one",
                 "tests/test_readme_production.py checks the two more of the v1.604 move it trims",
                 "tests/test_pin_docs.py reads each hard check's words in it (review iter-495 must-fix 1)",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    assert five2.index("\n- v1.648 README trim (") < five2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.649 (")]
    assert line.startswith("- v1.649 (2026-11-25): docs and tests (5.2, row PROD1g, third part). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.650 (row PROD1gbbb, fourth part) ----------------------------------------------------------

def test_the_v1_650_three_are_shorter_and_the_section_under_its_cap():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_650}
    # v1.652 (row PROD1gbbbbb) cuts some of them again, so each is at most the bytes v1.650 left it
    # review iter-507 should-fix 2: one v1.652 left alone keeps its v1.650 bytes exactly
    assert all(found[lead] <= NEW_BYTES_V1_650[lead] if lead in NEW_BYTES_V1_652
               else found[lead] == NEW_BYTES_V1_650[lead] for lead in found)
    assert sum(OLD_BYTES_V1_650.values()) - sum(found.values()) >= 631
    assert size(read("README.md"), PRODUCTION) <= PRODUCTION_CAP == 30_000


def test_the_v1_650_three_keep_their_leads_their_names_their_quotes_and_their_links():
    # v1.673 (row PROD1ibbba): the second on budgets is a pointer paragraph, which the v1.673 tests hold
    for lead in [lead for lead in OLD_BYTES_V1_650 if lead not in POINTERS_V1_673]:
        text = paragraph(lead)
        names = []
        for name in text.split("`")[1::2]:
            if name not in names:
                names.append(name)
        assert [n for n in NAMES_V1_650[lead] if n not in names] == [], lead
        for link in LINKS_V1_650[lead]:
            assert text.count(link) == 1, link
        assert "\u2014" not in text and "\u2013" not in text


def test_each_clause_the_v1_650_three_dropped_is_gone_and_its_design_subsection_states_it():
    design = read("DESIGN.md")
    assert len(DROPPED_V1_650) == 15
    for lead, clause, heading, phrase in DROPPED_V1_650:
        assert clause not in paragraph(lead), clause
        # a behavioural subsection, never a 5.2 history bullet of the README
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)


def test_the_v1_650_check_fails_on_a_clause_still_there_or_a_phrase_elsewhere():
    design = read("DESIGN.md")
    # kept on purpose: the only place the paragraph names `report`, the slice's output size (review
    # iter-448 must-fix 3), what a strict budget promises, and what the Uber quote is not
    assert "by default `report` puts a shadow attempt's time in its group's percentiles" in paragraph(LAT_LEAD)
    assert "its output the slice's or the task's `expected_output_tokens`" in paragraph(BUDGET_LEAD)
    assert "so its spend stays under its limit while providers bill within the bound" in paragraph(EST_LEAD)
    # v1.673 (row PROD1ibbba): the Uber quotes leave with their caveat, which the note's lesson states
    assert "its policy, for which it gives no saving" not in paragraph(EST_LEAD)
    assert "neither source gives a saving for its policy" in read("research/production-lessons.md")
    assert "a parent whose own time on the task is above the bar, or unknown under `deny`" in paragraph(LAT_LEAD)
    assert "so tokens a provider bills for a failed call are in no budget" not in subsection(design, "### 4.6 ")
    assert "Why after 5d" not in subsection(design, "## 7. ")
    assert "releases the hold of a call whose cost is not known" not in subsection(design, "## 7. ")


def test_design_states_the_v1_650_trim_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines()
              if line.startswith("- v1.650 README trim (row PROD1gbbb, fourth part): ")]
    for kept in ("paragraph on the latency bar is cut from 1,709 to 1,473 bytes, the first on budgets from 1,566 to "
                 "1,268 and the second, on the estimate and strict budgets, from 1,659 to 1,562",
                 "so the section is 25,557 bytes by the 12.8 measure, under v1.629's 30,000-byte cap, which stays",
                 "each clause it drops is stated in 4.3, 4.6, 5.2, 7 or 8.3, so no subsection gains one",
                 "so only the one on task scopes keeps its v1.604 bytes and sha256",
                 "tests/test_pin_docs.py reads each hard check's words in it (review iter-495 must-fix 1)",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    assert five2.index("\n- v1.649 README trim (") < five2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.650 (")]
    assert line.startswith("- v1.650 (2026-11-25): docs and tests (5.2, row PROD1g, fourth part). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.651 (row PROD1gbbbb, fifth part) ----------------------------------------------------------

def test_the_v1_651_three_are_shorter_and_the_section_under_its_cap():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_651}
    # v1.666 (row PROD1ibba) cuts the pinned-call one again, which NEW_BYTES_V1_666 holds, and v1.675 (row JUDGE2c)
    # adds its clause on 5.2 rules 5g and 5h, which GROWN_V1_675 holds
    assert found == {k: NEW_BYTES_V1_666.get(k, v) + GROWN_V1_675.get(k, 0) for k, v in NEW_BYTES_V1_651.items()}
    assert sum(OLD_BYTES_V1_651.values()) - sum(NEW_BYTES_V1_651.values()) == 399
    assert size(read("README.md"), PRODUCTION) <= PRODUCTION_CAP == 30_000


def test_the_v1_651_three_keep_their_leads_their_names_their_quotes_and_their_links():
    for lead in OLD_BYTES_V1_651:
        text = paragraph(lead)
        names = []
        for name in text.split("`")[1::2]:
            if name not in names:
                names.append(name)
        assert [n for n in NAMES_V1_651[lead] if n not in names] == [], lead
        for link in LINKS_V1_651[lead]:
            assert text.count(link) == 1, link
        assert "\u2014" not in text and "\u2013" not in text


def test_each_clause_the_v1_651_three_dropped_is_gone_and_its_design_subsection_states_it():
    design = read("DESIGN.md")
    assert len(DROPPED_V1_651) == 9
    for lead, clause, heading, phrase in DROPPED_V1_651:
        assert clause not in paragraph(lead), clause
        # a behavioural subsection, never a 5.2 history bullet of the README
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)


def test_the_v1_651_check_fails_on_a_clause_still_there_or_a_phrase_elsewhere():
    design = read("DESIGN.md")
    # kept on purpose: what a scope does, the tenant's set and what a row's values are not, and where a pin sits
    assert "makes the model a candidate only on a task one of them matches" in paragraph(SCOPE_LEAD)
    assert ("On a task none of them matches, its candidate is `out_of_scope` and not eligible, so it gets no calls "
            "there. ") in paragraph(SCOPE_LEAD)  # review iter-506 should-fix 3
    assert ("so the primary, each fallback, a shadow call and a delegate stay inside the allowed set, and a parent "
            "the policy rules out does not work inline. ") in paragraph(POLICY_LEAD)  # should-fix 1 and 2
    assert "On any other task" not in paragraph(SCOPE_LEAD)
    assert "not a certification: the library checks only that the row states them. " in paragraph(POLICY_LEAD)
    assert "a pin is a choice the caller makes for one call before it runs" in paragraph(PIN_LEAD)
    assert "the ranking of 5.3 is skipped" not in subsection(design, "## 7. ")
    assert "a move goes along that route only" not in subsection(design, "### 5.2 ")
    assert "with a cascade's cheap and strong models and a procedure's named model" not in subsection(design, "### 5.2 ")


def test_design_states_the_v1_651_trim_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines()
              if line.startswith("- v1.651 README trim (row PROD1gbbbb, fifth part): ")]
    for kept in ("paragraph on task scopes is cut from 1,176 to 909 bytes, the one on a tenant's policy from 1,316 to "
                 "1,212 and the one on pinned calls from 1,779 to 1,751",
                 "so the section is 25,158 bytes by the 12.8 measure, under v1.629's 30,000-byte cap, which stays",
                 "each clause it drops is stated in 5.2 or 7, so no subsection gains one",
                 "(review iter-506 should-fix 1 to 3)",
                 "so none of the seven paragraphs of the v1.604 move keeps its v1.604 bytes",
                 "which tests/test_pin_docs.py reads (review iter-495 must-fix 1)",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    assert five2.index("\n- v1.650 README trim (") < five2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.651 (")]
    assert line.startswith("- v1.651 (2026-11-25): docs and tests (5.2, row PROD1g, fifth part). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.652 (row PROD1gbbbbb, sixth part) ---------------------------------------------------------

def test_the_v1_652_nine_are_shorter_and_the_section_at_most_24000_bytes():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_652}
    # v1.653 (row PROD1h) changes five of the nine again, which NEW_BYTES_V1_653 holds; the four it left keep their
    # v1.652 bytes (review iter-508 nit 1); v1.665 (row PROD1iba) cuts two again, which NEW_BYTES_V1_665 holds,
    # and v1.666 (row PROD1ibba) the `promote` one, which NEW_BYTES_V1_666 holds; v1.673 (row PROD1ibbba) makes the
    # second on budgets and the cache one pointer paragraphs, which NEW_BYTES_V1_673 holds, and v1.674 (row PROD1ibbbb)
    # the self-hosted one, which NEW_BYTES_V1_674 holds
    later = {**NEW_BYTES_V1_653, **NEW_BYTES_V1_665, **NEW_BYTES_V1_666, **NEW_BYTES_V1_673, **NEW_BYTES_V1_674}
    assert {k: v for k, v in found.items() if k not in later} == {
        k: v for k, v in NEW_BYTES_V1_652.items() if k not in later}
    assert all(found[k] == later[k] for k in found if k in later)
    assert sum(OLD_BYTES_V1_652.values()) - sum(NEW_BYTES_V1_652.values()) == 1_166
    # v1.654 (row OPP1c) adds a sentence in the room under the cap; the section less LATER (v1.655, row T30)
    # stays at most TARGET
    assert size(without_later(read("README.md")), PRODUCTION) <= TARGET < PRODUCTION_CAP == 30_000


def test_the_v1_652_nine_keep_their_quotes_and_links_and_no_dash():
    for lead in OLD_BYTES_V1_652:
        text = paragraph(lead)
        assert text.startswith(lead), lead
        # v1.673 (row PROD1ibbba): the second on budgets keeps no link, and the cache one its lesson's; v1.674 (row
        # PROD1ibbbb): the self-hosted one keeps none, since step 5 and the scope paragraph link its lesson
        assert text.count("](") == {PROMOTE_LEAD: 2, EST_LEAD: 0, SHADOW_LEAD: 0, LAT_LEAD: 0,
                                    SELF_LEAD: 0}.get(lead, 1), lead
        assert "\u2014" not in text and "\u2013" not in text


def test_each_clause_the_v1_652_nine_dropped_is_gone_and_its_design_subsection_states_it():
    design = read("DESIGN.md")
    assert len(DROPPED_V1_652) == 14  # v1.653 takes three back
    for lead, clause, heading, phrase in DROPPED_V1_652:
        assert clause not in paragraph(lead), clause
        # a behavioural subsection, never a 5.2 history bullet of the README
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)


def test_the_v1_652_check_fails_on_a_clause_still_there_or_a_phrase_elsewhere():
    design = read("DESIGN.md")
    readme = read("README.md")
    # kept on purpose: what each paragraph's claim rests on stays in it
    assert "a named one need not clear the bar. Once the routed call has returned" in paragraph(SHADOW_LEAD)
    assert "With no `shadow_runner` the shadow runs before `.call` returns. " in paragraph(SHADOW_LEAD)
    # v1.673 (row PROD1ibbba): the cache one is a pointer paragraph, and DESIGN 4.1 states it (DROPPED_V1_673)
    assert "Only reported counts are priced as hits" not in paragraph(CACHE_LEAD)
    assert "a repeated prompt is never assumed to hit" in subsection(design, "### 4.1 ")
    assert "so a flag is a reason to audit more calls, not proof of a change (" in paragraph(DRIFT_LEAD)
    # the one-process ledger leaves the section but not the README: Limitations still says it
    limits = readme[readme.index("\n## Limitations and non-goals (v1)\n"):readme.index("\n## Layout\n")]
    assert limits.count("a limit shared by many processes needs a gateway or the provider's own") == 1
    assert "never hits the cache can cost more per call" not in subsection(design, "## 7. ")
    assert "so which calls to audit stays the caller's" not in subsection(design, "## 10. ")


def test_design_states_the_v1_652_trim_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines()
              if line.startswith("- v1.652 README trim (row PROD1gbbbbb, sixth part): ")]
    for kept in ("the one on `promote` from 1,902 to 1,693 bytes, the one on `drift` from 2,032 to 1,921",
                 "so the section is 23,992 bytes by the 12.8 measure, at most the 24,000 that row PROD1g set and "
                 "under v1.629's 30,000-byte cap, which stays",
                 "each clause it drops is stated in 4.1, 4.3, 4.6, 4.7, 5.2, 7, 8.1, 8.3 or 11, so no subsection gains one",
                 "the tests of v1.647 to v1.650 hold each paragraph they trimmed to at most the bytes they left it and "
                 "the two they did not touch again to those bytes",
                 "README `## Limitations and non-goals (v1)` still says a limit shared by many processes needs a "
                 "gateway or the provider's own",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    assert five2.index("\n- v1.651 README trim (") < five2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.652 (")]
    assert line.startswith("- v1.652 (2026-11-25): docs and tests (5.2, row PROD1g, sixth part). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.653 (row PROD1h): two caveats back, eight clauses traded out --------------------------------------

THREADS_LEAD = "One `Executor`, with its `Monitor` and `BudgetLedger`, can serve every request thread of a process: "
EXAMPLE_LEAD = "`demo/atlas-max` clears the bar and measures 0.953 against 0.913 on the same 300 items, "
# the seven paragraphs v1.653 changes, as v1.652 (f6d28c2) left them and as v1.653 leaves them
OLD_BYTES_V1_653 = {VAR_LEAD: 1_468, SELF_LEAD: 1_382, PROMOTE_LEAD: 1_693, EXAMPLE_LEAD: 490, SHADOW_LEAD: 1_641,
                    THREADS_LEAD: 632, LAT_LEAD: 1_389}
NEW_BYTES_V1_653 = {VAR_LEAD: 1_486, SELF_LEAD: 1_450, PROMOTE_LEAD: 1_708, EXAMPLE_LEAD: 427, SHADOW_LEAD: 1_610,
                    THREADS_LEAD: 578, LAT_LEAD: 1_420}
# what comes back, each with the behavioural DESIGN subsection and the phrase of the line that states it
BACK_V1_653 = [
    (LAT_LEAD, "A trial's time, from your call to the route's answer, is a results row's `latency_ms`", "### 4.3 ",
     "so a route's time is what the caller measured from its call to its answer"),  # review iter-507 should-fix 1
    (LAT_LEAD, "while a monitor record's `latency_ms` is one attempt's. To read a bar off a log", "### 4.3 ",
     "an attempt record's `latency_ms` (8.1) is one attempt's"),
    (SELF_LEAD, "Its throughputs describe one workload, and its split of the hour between input and output is an "
     "approximation you choose. ", "### 4.1 ",
     "The throughputs describe one workload, and the split of an hour between input and output is an approximation "
     "the caller chooses"),  # review iter-507 should-fix 3
    (PROMOTE_LEAD, "for a challenger cheaper per item at list prices, on a paired lower bound", "## 10. ",
     "so at list prices in either flavor and per item"),  # review iter-502 nit 3
    (VAR_LEAD, "so once measured with token counts the route is priced per item", "### 5.2 ",
     "for a route whose `items_per_call` k is above 1 (4.1), `list_cost`"),  # review iter-507 nit 1
    # review iter-508 must-fix 1: `report` reads a call's first record before its last, so the order stays
    (THREADS_LEAD, "once per log (rotated files oldest first), refusing", "### 8.2 ",
     "give such files in the order they were written"),
    (SHADOW_LEAD, "A task's `shadow_rate`, 0 by default, is the share", "### 4.2 ",  # review iter-508 should-fix 1
     "`shadow_rate: float = 0.0`, the share of the task's `.call`s also sent to a shadow route"),
]
# what leaves to pay for it, as v1.652 (f6d28c2) wrote it, each pinned the same way
DROPPED_V1_653 = [
    (SELF_LEAD, "In place of list prices, ", "### 4.1 ",
     "prices derived from what an hour of the caller's own serving costs"),
    (SELF_LEAD, "unmeasured it is not routed, ", "## 11. ",
     "they give reasons `insufficient_samples`, `passes`, `passes` and `generator_family`"),
    (SHADOW_LEAD, ", from 0, the default, to 1,", "### 4.2 ", "a finite `int` or `float` in [0, 1] that is not a `bool`"),
    (SHADOW_LEAD, ", with no fallback,", "## 7. ",
     "the executor makes one provider call of the shadow route on the same `messages`, by step 2 with no fallback"),
    (LAT_LEAD, ", in milliseconds,", "### 4.2 ", "the highest 95th-percentile time in milliseconds a route may take"),
    (LAT_LEAD, ", so below 20 trials it is the slowest of them", "### 4.3 ", "the slowest of them while `n` is below 20"),
    # the transcript above it prints `cheaper: false` and `basis: n/a`, and 4.7 states when the margin is read
    (EXAMPLE_LEAD, " The margin is not read, since `demo/atlas-max` is not cheaper.", "### 4.7 ",
     "`cheaper` and `lower_bound > -margin` gives `promote` with basis `non_inferior`"),
    (THREADS_LEAD, ", since a log given twice would count it twice", "### 8.2 ",
     "which would count its calls and its spend twice"),
]
NAMES_V1_653 = {THREADS_LEAD: ["Executor", "Monitor", "BudgetLedger", "id_factory", "random", "now", "clock",
                               "report", "pairs", "--log PATH"]}


def test_the_v1_653_seven_and_the_section_at_most_24000_bytes():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_653}
    # v1.665 (row PROD1iba) cuts the first on shadows again, which NEW_BYTES_V1_665 holds, and v1.666 (row
    # PROD1ibba) the `promote` one, which NEW_BYTES_V1_666 holds, and v1.674 (row PROD1ibbbb) the self-hosted one,
    # which NEW_BYTES_V1_674 holds
    later = {**NEW_BYTES_V1_665, **NEW_BYTES_V1_666, **NEW_BYTES_V1_674}
    assert found == {k: later.get(k, v) for k, v in NEW_BYTES_V1_653.items()}
    assert sum(OLD_BYTES_V1_653.values()) - sum(NEW_BYTES_V1_653.values()) == 16
    # v1.654 (row OPP1c) adds a sentence in the room under the cap; the section less LATER (v1.655, row T30)
    # keeps v1.653's bytes, less what v1.665 (row PROD1iba), v1.666 (row PROD1ibba), v1.673 (row PROD1ibbba) and
    # v1.674 (row PROD1ibbbb) cut, and more the clause v1.675 (row JUDGE2c) adds to the pin paragraph, and LATER's
    # entries are the rest
    text = read("README.md")
    assert (size(without_later(text), PRODUCTION)
            == 23_976 - CUT_V1_665 - CUT_V1_666 - CUT_V1_673 - CUT_V1_674 + sum(GROWN_V1_675.values())
            == 20_343 <= TARGET < PRODUCTION_CAP == 30_000)
    assert size(text, PRODUCTION) - size(without_later(text), PRODUCTION) == sum(b for _, b in LATER)
    assert LATER[0] == (SAVINGS_LEAD, 714)  # v1.654's paragraph, its own 712 bytes and the blank line


def test_the_v1_653_caveats_and_qualifiers_are_back_where_design_states_them():
    design = read("DESIGN.md")
    assert len(BACK_V1_653) == 7
    for lead, text, heading, phrase in BACK_V1_653:
        # v1.674 (row PROD1ibbbb): the self-hosted one is a pointer paragraph, so its one-workload caveat is 4.1's
        # alone (DROPPED_V1_674)
        assert paragraph(lead).count(text) == (0 if lead in POINTERS_V1_674 else 1), text
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)


def test_each_clause_v1_653_traded_out_is_gone_and_its_design_subsection_states_it():
    design = read("DESIGN.md")
    assert len(DROPPED_V1_653) == 8
    for lead, clause, heading, phrase in DROPPED_V1_653:
        assert clause not in paragraph(lead), clause
        # a behavioural subsection, never a 5.2 history bullet of the README
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)


def test_the_v1_653_seven_keep_their_names_quotes_and_links_and_no_dash():
    for lead in OLD_BYTES_V1_653:
        text = paragraph(lead)
        assert text.startswith(lead), lead
        assert "\u2014" not in text and "\u2013" not in text
    names = paragraph(THREADS_LEAD).split("`")[1::2]
    assert [n for n in NAMES_V1_653[THREADS_LEAD] if n not in names] == []
    # v1.674 (row PROD1ibbbb): the self-hosted one is a pointer paragraph with no link
    assert paragraph(SELF_LEAD).count("](") == 0 and paragraph(PROMOTE_LEAD).count("](") == 2
    assert paragraph(VAR_LEAD).count("](") == 1 and paragraph(THREADS_LEAD).count("](") == 0
    assert paragraph(EXAMPLE_LEAD).count("`demo/atlas-max`") == 2 and paragraph(EXAMPLE_LEAD).count("](") == 0


def test_the_v1_653_check_fails_on_a_clause_still_there_or_a_phrase_elsewhere():
    design = read("DESIGN.md")
    # a mutant: the paragraph with a traded clause put back fails the check
    lat = paragraph(LAT_LEAD)
    mutant = lat.replace("of the `n` sorted times. ", "of the `n` sorted times, so below 20 trials it is the slowest "
                         "of them. ")
    assert mutant != lat
    assert [c for lead, c, _, _ in DROPPED_V1_653 if lead == LAT_LEAD and c in mutant] == [
        ", so below 20 trials it is the slowest of them"]
    # kept on purpose: a task with no bar routes as before, a named shadow route need not clear the bar, and a
    # record found in two logs is refused
    assert "A task with no bar routes as before." in lat
    assert "a named one need not clear the bar. Once the routed call has returned" in paragraph(SHADOW_LEAD)
    assert "refusing a record found in two of them." in paragraph(THREADS_LEAD)
    # each owner is the behavioural line, not a line of another subsection
    assert "give such files in the order they were written" not in subsection(design, "### 8.3 ")
    assert "`cheaper: false`" not in paragraph(EXAMPLE_LEAD)
    assert "cheaper:              false\nalpha:" in read("README.md")  # the transcript still shows it
    assert "the slowest of them while `n` is below 20" not in subsection(design, "### 4.2 ")
    assert "by step 2 with no fallback" not in subsection(design, "### 4.2 ")
    assert "so at list prices in either flavor and per item" not in subsection(design, "### 4.7 ")


def test_design_states_the_v1_653_change_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines()
              if line.startswith("- v1.653 README caveats (row PROD1h, review iter-507 should-fix 1 and 3): ")]
    for kept in ("gets back, in short form where each claim is made, two caveats v1.652 dropped",
                 "a trial's time runs from your call to the route's answer while a monitor record's `latency_ms` is "
                 "one attempt's (4.3 v1.626)",
                 "its throughputs describe one workload and its split of the hour between input and output is an "
                 "approximation you choose (4.1 v1.581)",
                 "each stated on a line of 4.1, 4.2, 4.3, 4.7, 7, 8.2 or 11, so no subsection gains one",
                 "so the section is 23,976 bytes by the 12.8 measure, at most row PROD1g's 24,000 and under v1.629's "
                 "30,000-byte cap, which stays",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    assert five2.index("\n- v1.652 README trim (") < five2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.653 (")]
    assert line.startswith("- v1.653 (2026-11-25): docs and tests (5.2, row PROD1h). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.655 (row T30) -----------------------------------------------------------------------------

def test_the_section_ends_with_the_record_format_sentence():
    # the one test that names the section's last paragraph; a slice that adds one after it restates this alone
    # (v1.656, row PROD1b: the sentence on `keep_records` follows the savings sentence, v1.654's last;
    # v1.657, row PROD1e: the sentence on calls from a coroutine follows it; v1.658, row LOG1: the sentence on the
    # record format follows that; v1.663, row JUDGE1bbb: the paragraph on consensus labels follows that; v1.675,
    # row JUDGE2c: the paragraph on the self-consistency minimum follows that; v1.680, row PROD1j: the paragraph
    # on the pair route follows that)
    found = paragraphs(read("README.md"), PRODUCTION)
    assert found[-1].startswith(PAIR_LEAD)
    assert found[found.index(paragraph(PAIR_LEAD)) - 1].startswith(CONSISTENCY_LEAD)
    assert found[found.index(paragraph(CONSISTENCY_LEAD)) - 1].startswith(CONSENSUS_LEAD)
    assert found[found.index(paragraph(CONSENSUS_LEAD)) - 1].startswith(FORMAT_LEAD)
    assert found[found.index(paragraph(FORMAT_LEAD)) - 1].startswith(COROUTINE_LEAD)
    assert found[found.index(paragraph(COROUTINE_LEAD)) - 1].startswith(MONITOR_LEAD)
    assert found[found.index(paragraph(MONITOR_LEAD)) - 1].startswith(SAVINGS_LEAD)


def test_later_takes_out_a_paragraph_wherever_it_sits_and_only_its_bytes():
    text = read("README.md")
    found = paragraphs(text, PRODUCTION)
    # appended to, never rewritten: v1.654's entry stays first whatever a later slice adds
    assert LATER[0] == (SAVINGS_LEAD, 714) and sum(p.startswith(SAVINGS_LEAD) for p in found) == 1
    # a hand case: one more paragraph after the savings sentence leaves the section less LATER that paragraph more
    extra = "A hand case puts this paragraph directly after the savings sentence."
    savings = paragraph(SAVINGS_LEAD)
    grown = text.replace("\n\n" + savings + "\n\n", "\n\n" + savings + "\n\n" + extra + "\n\n", 1)
    after = paragraphs(grown, PRODUCTION)
    assert grown.count(extra) == 1 and after[after.index(savings) + 1] == extra
    assert size(without_later(grown), PRODUCTION) == size(without_later(text), PRODUCTION) + len(extra) + 2
    # a mutant: an entry whose bytes are not its paragraph's own and its blank line's fails the check
    LATER[0] = (SAVINGS_LEAD, 712)
    try:
        with pytest.raises(AssertionError, match="A log also shows"):
            without_later(text)
    finally:
        LATER[0] = (SAVINGS_LEAD, 714)
    assert LATER[0] == (SAVINGS_LEAD, 714)


def test_design_states_v1_655_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.655 README paragraph places (row T30): ")]
    for kept in ("a test places a paragraph of `## Running it in production` by the paragraph directly before or "
                 "after it, never by a count from the section's end",
                 "in place of v1.654's third last, second last and last",
                 "One test alone, in tests/test_readme_trim.py, names the section's last paragraph",
                 "take out one list, `LATER`, of the paragraphs added after v1.653",
                 "a slice that adds a paragraph appends its entry",
                 "No package module, evidence file, README text or transcript changes."):
        assert mine.count(kept) == 1, kept
    assert five2.index("\n- v1.654 README savings report (") < five2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.655 (")]
    assert line.startswith("- v1.655 (2026-11-25): tests (5.2, row T30). ")
    assert line.endswith(" README.md and every transcript keep their bytes.")
    assert len(line.encode("utf-8")) <= 600


# --- v1.664 (row PROD1ia, the first part of row PROD1i) ---------------------------------------------

STEPS_V1_659, STEPS_V1_664, INTRO_V1_659, INTRO_V1_664 = 3_364, 3_088, 143, 115
SECTION_V1_663, SECTION_V1_664 = 29_952, 29_648
# each step's lesson anchor in research/production-lessons.md, as v1.659 linked it
ANCHORS_V1_659 = [
    "benchmark-the-real-work-then-take-the-cheapest-setup-that-holds-quality",
    "a-catalogue-of-models-does-not-pick-one-and-a-stand-in-model-must-clear-the-same-bar",
    "effort-harness-and-batch-size-are-part-of-the-measured-setup",
    "keep-tool-schemas-and-polling-out-of-the-models-context",
    "your-own-trained-model-is-a-candidate-kept-to-the-tasks-it-was-measured-on",
    "keep-the-prompt-prefix-the-same-byte-for-byte",
    "spend-tiers-and-nudges-not-strict-caps",
    "switch-models-only-on-locked-data-and-a-significant-result",
    "the-price-of-a-given-score-falls-fast-and-unevenly-date-the-prices-and-re-run-the-choice",
    "price-cache-writes-and-set-the-caches-life-by-how-the-work-pauses",
]
# (where: 0 the sentence, else the step's number; the clause as v1.663 wrote it; a phrase of DESIGN 5.2 that states it)
DROPPED_V1_664 = [
    (0, "in order, ", "a numbered list of ten steps in this order"),
    (0, "in the paragraphs below", "The paragraphs after the list are the steps' detail"),
    (1, "so a wrong answer is an `invalid` attempt and the call moves to its fallback",
     "whose rejection is an `invalid` attempt that falls back (7)"),
    (2, "must clear the same bar](", "admitted only once its own bound clears the bar (rule 7"),
    (3, "a route, a `variants` entry per effort or harness, and", "a route for each setup by `variants` (4.1)"),
    (5, "at its real price", "a self-hosted row priced from its hour"),
    (5, "kept to the tasks it was measured on](", "kept to its tasks by `scope_tasks` (4.1)"),
    (8, "with a task's `shadow_rate`", "a share of calls shadowed by `shadow_rate`"),
    (8, "switches models only on locked data", "a switch made only on `promote`'s decision"),
    (9, "once a row's `price_valid_until` has passed", "`select` warns past a row's `price_valid_until`, v1.411"),
    (10, "[sets the cache's life by how the work pauses](", "a cache life set by how the traffic pauses"),
]


def walk_parts(text):
    found = paragraphs(text, PRODUCTION)
    [at] = [k for k, p in enumerate(found) if p.startswith(WALK_LEAD)]
    return found[at], found[at + 1].split("\n")


def test_the_v1_664_walkthrough_is_shorter_and_the_section_under_its_cap():
    intro, steps = walk_parts(read("README.md"))
    assert len(intro.encode("utf-8")) == INTRO_V1_664 and len("\n".join(steps).encode("utf-8")) == STEPS_V1_664
    assert (INTRO_V1_659 + STEPS_V1_659) - (INTRO_V1_664 + STEPS_V1_664) == SECTION_V1_663 - SECTION_V1_664 == 304
    assert size(read("README.md"), PRODUCTION) <= SECTION_V1_664 < PRODUCTION_CAP == 30_000


def test_the_v1_664_steps_keep_their_lesson_anchors_in_order():
    _, steps = walk_parts(read("README.md"))
    found = [step.split("](research/production-lessons.md#", 1)[1].split(")", 1)[0] for step in steps]
    assert found == ANCHORS_V1_659


def clauses_still_there(readme):
    """Each DROPPED_V1_664 clause still in the sentence or the step it was dropped from."""
    intro, steps = walk_parts(readme)
    return [clause for where, clause, _ in DROPPED_V1_664 if clause in (intro if where == 0 else steps[where - 1])]


def test_each_clause_v1_664_dropped_is_gone_and_design_5_2_states_it():
    five2 = subsection(read("DESIGN.md"), "### 5.2 ")
    assert len(DROPPED_V1_664) == 11
    assert clauses_still_there(read("README.md")) == []
    for _, clause, phrase in DROPPED_V1_664:
        assert five2.count(phrase) >= 1, (clause, phrase)


def test_the_v1_664_check_names_a_clause_put_back():
    # review iter-521 should-fix 1: put v1.663's words back into a step, the walk-through's sentence intact
    readme = read("README.md")
    _, steps = walk_parts(readme)
    # the reworded clauses keep their content in the step itself
    assert "whose rejection is an `invalid` attempt" in steps[0]
    assert "a cache life set by how the traffic pauses" in steps[9]
    fallback = "so a wrong answer is an `invalid` attempt and the call moves to its fallback"
    one = steps[0].replace(" a check whose rejection is an `invalid` attempt:", " a check, " + fallback + ":")
    two = steps[1].replace("like [a stand-in model](", "as [a stand-in model must clear the same bar](")
    assert one != steps[0] and two != steps[1]
    worse = readme.replace(steps[0], one, 1).replace(steps[1], two, 1)
    assert clauses_still_there(worse) == [fallback, "must clear the same bar]("]


def test_design_states_v1_664_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines()
              if line.startswith("- v1.664 README walk-through trim (row PROD1ia, the first part of row PROD1i): ")]
    for kept in ("its ten steps are cut from 3,364 to 3,088 bytes",
                 "Each step keeps every name v1.659 gives it (tests/test_readme_walkthrough.py `TOPICS`)",
                 "its one link to a lesson of research/production-lessons.md by the same anchor",
                 "So the section is 29,648 bytes by the 12.8 measure, 352 under v1.629's 30,000-byte cap, which stays.",
                 "row PROD1ib cuts the paragraphs after the list to reach 26,000",
                 "restates the two v1.659 entries to 117 and 3,090 bytes with their blank lines",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    assert five2.index("\n- v1.659 README walk-through (row PROD1): ") < five2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.664 (")]
    assert line.startswith("- v1.664 (2026-11-26): docs and tests (5.2, row PROD1i, first part). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.665 (row PROD1iba, the first part of row PROD1ib) -------------------------------------------

# the paragraph on `drift` and the first on shadows, as v1.664 (76aa0e3) left them and as v1.665 leaves them
OLD_BYTES_V1_665 = {DRIFT_LEAD: 1_921, SHADOW_LEAD: 1_610}
NEW_BYTES_V1_665 = {DRIFT_LEAD: 1_741, SHADOW_LEAD: 1_527}
CUT_V1_665, SECTION_V1_665 = 263, 29_385
# each clause v1.665 drops or rewords, as v1.664 wrote it, the behavioural DESIGN subsection that states it, and a
# phrase of the line there that says it
DROPPED_V1_665 = [
    (DRIFT_LEAD, "twice: on the audited calls of the last N UTC days", "### 8.3 ",
     "`window_trials`, `window_lb`, each bound `wilson_lower_bound` (4.3) of its counts"),
    (DRIFT_LEAD, "the stats file you route on when you pass it as", "## 10. ",
     "`all_time` is `Stats.load(PATH)` with `--stats`, the stats a route is admitted on"),
    (DRIFT_LEAD, "each answer the task's check rejected as a failure", "### 8.3 ",
     "since the task's check rejected that answer whatever the audit says"),
    (DRIFT_LEAD, "Wilson bounds, the bar, `min_samples` and a flag", "### 8.3 ",
     "then `bar`, `min_samples`, `confidence` and `flag`"),
    (DRIFT_LEAD, "when the window clears it and the all-time side does not", "### 8.3 ",
     "`rose_above` when the all-time side does not clear"),
    (DRIFT_LEAD, "and alerts on a flag", "## 10. ", "so a scheduled job reads `--json` and alerts on a flag"),
    (DRIFT_LEAD, "to route on the window alone,", "## 10. ", "reads the window's stats instead of `--stats`"),
    (SHADOW_LEAD, "a shadowed call sends the same messages to the shadow route once", "## 7. ",
     "the executor makes one provider call of the shadow route on the same `messages`"),
    (SHADOW_LEAD, "A call answered by the shadow route's own model sends no shadow", "## 7. ",
     "its pair would compare that model with itself"),
    (SHADOW_LEAD, "is the shadow route is still shadowed", "## 7. ",
     "so a procedure whose `model` is the shadow route is still shadowed on the call's `messages`"),
    (SHADOW_LEAD, "it is held and settled under the call's tags", "## 7. ",
     "it holds and settles that call as v1.595 does, under the call's task and its tags plus `shadow: \"true\"`"),
    (SHADOW_LEAD, "The default `report` counts a shadow", "### 8.3 ", "so a shadow call counts as a call of its own"),
]
# what each rewording keeps, in the paragraph itself
KEPT_V1_665 = {DRIFT_LEAD: ["each `invalid` answer as a failure", "`rose_above` when only the window clears it",
                            "or on the stats you route on (`--stats FILE`)",
                            "`select --window 30d --log PATH --audits PATH` routes on the window's stats"],
               SHADOW_LEAD: ["the same messages go to the shadow route once",
                             "a procedure whose `model` is that route still does",
                             "its tags are the call's plus `shadow: \"true\"`",
                             "`report` counts a shadow as a call of its own, while `report --shadow`"]}


def v1_665_still_there(readme):
    """Each DROPPED_V1_665 clause still in the paragraph it was dropped from."""
    found = paragraphs(readme, PRODUCTION)
    return [clause for lead, clause, _, _ in DROPPED_V1_665
            if any(p.startswith(lead) and clause in p for p in found)]


def test_the_v1_665_two_are_shorter_and_the_section_under_its_cap():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_665}
    assert found == NEW_BYTES_V1_665
    assert sum(OLD_BYTES_V1_665.values()) - sum(found.values()) == CUT_V1_665 == SECTION_V1_664 - SECTION_V1_665
    assert size(read("README.md"), PRODUCTION) <= SECTION_V1_665 < PRODUCTION_CAP == 30_000


def test_the_v1_665_two_keep_their_leads_names_quote_and_links():
    for lead, names in ((DRIFT_LEAD, NAMES[DRIFT_LEAD]), (SHADOW_LEAD, NAMES_V1_648[SHADOW_LEAD])):
        text = paragraph(lead)
        assert text.startswith(lead) and [n for n in names if n not in text.split("`")[1::2]] == [], lead
        assert all(text.count(kept) == 1 for kept in KEPT_V1_665[lead]), lead
        assert "\u2014" not in text and "\u2013" not in text
    assert all(paragraph(DRIFT_LEAD).count(link) == 1 for link in LINKS[DRIFT_LEAD])
    assert paragraph(DRIFT_LEAD).count("](") == 1 and paragraph(SHADOW_LEAD).count("](") == 0


def test_each_clause_v1_665_dropped_is_gone_and_its_design_subsection_states_it():
    design = read("DESIGN.md")
    assert len(DROPPED_V1_665) == 12
    assert v1_665_still_there(read("README.md")) == []
    for lead, clause, heading, phrase in DROPPED_V1_665:
        # a behavioural subsection, never a 5.2 history bullet of the README
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)


def test_the_v1_665_check_names_a_clause_put_back():
    readme = read("README.md")
    drift, shadow = paragraph(DRIFT_LEAD), paragraph(SHADOW_LEAD)
    one = drift.replace("so a scheduled job reads its `--json`;", "so a scheduled job reads its `--json` and alerts on a flag;")
    two = shadow.replace("its tags are the call's plus", "it is held and settled under the call's tags plus")
    assert one != drift and two != shadow
    worse = readme.replace(drift, one, 1).replace(shadow, two, 1)
    assert v1_665_still_there(worse) == ["and alerts on a flag", "it is held and settled under the call's tags"]
    # a clause in another paragraph is not the dropped one's (review iter-522 should-fix 1: the hand case holds it)
    other = "It reads its `--json` and alerts on a flag."
    elsewhere = readme.replace("\n\n" + drift + "\n\n", "\n\n" + drift + "\n\n" + other + "\n\n", 1)
    assert elsewhere.count(other) == 1 and "and alerts on a flag" in other
    assert v1_665_still_there(elsewhere) == []


def test_design_states_v1_665_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines()
              if line.startswith("- v1.665 README trim (row PROD1iba, the first part of row PROD1ib): ")]
    for kept in ("the paragraph on `drift` (v1.635) is cut from 1,921 to 1,741 bytes and the first on shadows (v1.619) "
                 "from 1,610 to 1,527",
                 "Each clause it drops or rewords is stated in 7, 8.3 or 10, so no subsection gains one",
                 "So the section is 29,385 bytes by the 12.8 measure, 615 under v1.629's 30,000-byte cap, which stays.",
                 "row PROD1ibb cuts the rest to reach 26,000",
                 # review iter-522 should-fix 2: the number the v1.653 test now holds
                 "and the section less `LATER` at 23,713, v1.653's 23,976 less 263",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    # review iter-522 nit 4: right after v1.664's bullet
    lines = five2.splitlines()
    assert lines[lines.index(mine) - 1].startswith("- v1.664 README walk-through trim (")
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.665 (")]
    assert line.startswith("- v1.665 (2026-11-26): docs and tests (5.2, row PROD1i, second part). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.666 (row PROD1ibba, the first part of row PROD1ibb) -----------------------------------------

# the paragraph on `promote` and the one on pinned calls, as v1.665 (48a41e9) left them and as v1.666 leaves them
OLD_BYTES_V1_666 = {PROMOTE_LEAD: 1_708, PIN_LEAD: 1_751}
NEW_BYTES_V1_666 = {PROMOTE_LEAD: 1_628, PIN_LEAD: 1_724}
CUT_V1_666, SECTION_V1_666 = 107, 29_278
# each clause v1.666 drops or rewords, as v1.665 wrote it, the behavioural DESIGN subsection that states it, and a
# phrase of the line there that says it
DROPPED_V1_666 = [
    (PROMOTE_LEAD, "with the sha256 of the results file, to FILE", "## 10. ",
     "the command computes the sha256 of the results file's bytes"),
    (PROMOTE_LEAD, "It requires the bar to admit the challenger first and exits 3 when it does not", "## 10. ",
     "the command exits 3 with one line, `error: challenger ROUTE is not admitted on task T: REASON`"),
    (PROMOTE_LEAD, "4.7, with the pairs a margin needs, and 10", "### 4.7 ",
     "gives `promote` from 91 pairs with no discordant pair"),
    (PROMOTE_LEAD, "to check k challengers on one file pass `--alpha` 0.05 divided by k", "## 10. ",
     "passes `--alpha` A / k (Bonferroni)"),
    (PIN_LEAD, "a tag that names who or what pinned the call, a contract or a ticket for example", "## 7. ",
     "`pinned_by=None`, the tag that names who or what pinned the call"),
    (PIN_LEAD, "and it gives up the fallback that bullet names", "### 5.2 ",
     "the ranking of 5.3 is skipped: the pin is the decision's only entry"),
]
# what each rewording keeps, in the paragraph itself
KEPT_V1_666 = {PROMOTE_LEAD: ["appends to FILE each labeled row's outcome with the results file's sha256, and ",
                              "The bar must admit the challenger first, or it exits 3. Then it prints ",
                              "It is advisory and changes no route or file (`DESIGN.md` 4.7 and 10). ",
                              "for k challengers on one file pass `--alpha` 0.05/k. "],
               PIN_LEAD: ["a tag naming who or what pinned the call (a contract or a ticket), which each attempt",
                          "; it gives up that bullet's fallback, while a cascade pin keeps its hand-up."]}


def v1_666_still_there(readme):
    """Each DROPPED_V1_666 clause still in the paragraph it was dropped from."""
    found = paragraphs(readme, PRODUCTION)
    return [clause for lead, clause, _, _ in DROPPED_V1_666
            if any(p.startswith(lead) and clause in p for p in found)]


def test_the_v1_666_two_are_shorter_and_the_section_under_its_cap():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_666}
    # v1.675 (row JUDGE2c) adds its clause on 5.2 rules 5g and 5h to the pin paragraph, which GROWN_V1_675 holds
    found = {lead: n - GROWN_V1_675.get(lead, 0) for lead, n in found.items()}
    assert found == NEW_BYTES_V1_666
    assert sum(OLD_BYTES_V1_666.values()) - sum(found.values()) == CUT_V1_666 == SECTION_V1_665 - SECTION_V1_666
    assert size(read("README.md"), PRODUCTION) <= SECTION_V1_666 < PRODUCTION_CAP == 30_000


def test_the_v1_666_two_keep_their_leads_names_quote_and_links():
    for lead, names in ((PROMOTE_LEAD, NAMES[PROMOTE_LEAD]), (PIN_LEAD, NAMES_V1_651[PIN_LEAD])):
        text = paragraph(lead)
        assert text.startswith(lead) and [n for n in names if n not in text.split("`")[1::2]] == [], lead
        assert all(text.count(kept) == 1 for kept in KEPT_V1_666[lead]), lead
        assert "\u2014" not in text and "\u2013" not in text
    assert all(paragraph(PROMOTE_LEAD).count(link) == 1 for link in LINKS[PROMOTE_LEAD])
    assert all(paragraph(PIN_LEAD).count(link) == 1 for link in LINKS_V1_651[PIN_LEAD])
    assert paragraph(PROMOTE_LEAD).count("](") == 2 and paragraph(PIN_LEAD).count("](") == 1


def test_each_clause_v1_666_dropped_is_gone_and_its_design_subsection_states_it():
    design = read("DESIGN.md")
    assert len(DROPPED_V1_666) == 6
    assert v1_666_still_there(read("README.md")) == []
    for lead, clause, heading, phrase in DROPPED_V1_666:
        # a behavioural subsection, never a 5.2 history bullet of the README
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)


def test_the_v1_666_check_names_a_clause_put_back():
    readme = read("README.md")
    promote, pin = paragraph(PROMOTE_LEAD), paragraph(PIN_LEAD)
    one = promote.replace("(`DESIGN.md` 4.7 and 10)", "(`DESIGN.md` 4.7, with the pairs a margin needs, and 10)")
    two = pin.replace("; it gives up that bullet's fallback,", ", and it gives up the fallback that bullet names,")
    assert one != promote and two != pin
    worse = readme.replace(promote, one, 1).replace(pin, two, 1)
    assert v1_666_still_there(worse) == ["4.7, with the pairs a margin needs, and 10",
                                         "and it gives up the fallback that bullet names"]
    # a clause in another paragraph is not the dropped one's
    other = "So a pin is the caller's, and it gives up the fallback that bullet names."
    elsewhere = readme.replace("\n\n" + pin + "\n\n", "\n\n" + pin + "\n\n" + other + "\n\n", 1)
    assert elsewhere.count(other) == 1 and "and it gives up the fallback that bullet names" in other
    assert v1_666_still_there(elsewhere) == []


def test_design_states_v1_666_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines()
              if line.startswith("- v1.666 README trim (row PROD1ibba, the first part of row PROD1ibb): ")]
    for kept in ("the paragraph on `promote` (v1.605) is cut from 1,708 to 1,628 bytes and the one on pinned calls "
                 "(v1.641) from 1,751 to 1,724",
                 "Each clause it drops or rewords is stated in 4.7, 5.2, 7 or 10, so no subsection gains one",
                 "So the section is 29,278 bytes by the 12.8 measure, 722 under v1.629's 30,000-byte cap, which stays.",
                 "and the section less `LATER` at 23,606, v1.665's 23,713 less 107",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    lines = five2.splitlines()
    assert lines[lines.index(mine) - 1].startswith("- v1.665 README trim (")
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.666 (")]
    assert line.startswith("- v1.666 (2026-11-26): docs and tests (5.2, row PROD1i, third part). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.673 (row PROD1ibbba, the first part of row PROD1ibbb): two pointer paragraphs ---------------

# the second on budgets and the one on the prompt cache, as v1.666 (def0b69) left them and as v1.673 leaves them
OLD_BYTES_V1_673 = {EST_LEAD: 1_455, CACHE_LEAD: 1_586}
NEW_BYTES_V1_673 = {EST_LEAD: 397, CACHE_LEAD: 394}
CUT_V1_673, SECTION_V1_673, POINTER_CAP = 2_250, 27_028, 400
# row PROD1ibbb's rule (SCOUT iter 530): a pointer paragraph keeps its lead sentence, the names in backticks of the
# option it introduces and its one pointer to DESIGN, and is at most POINTER_CAP bytes; review iter-531 should-fix 2:
# the cache one's lead is its first two sentences, the second naming the option, and nit 1: the names are the
# option's alone, the pointer holding `DESIGN.md` and the lead `refuse`
CACHE_SECOND = ("A `models.json` row may give `price_cached_in` and `price_cache_write`, and a results line its "
                "`cached_input_tokens` and `cache_write_tokens` ")
POINTERS_V1_673 = {
    EST_LEAD: ("The estimate is no bound: a call that reads or writes more than its estimate costs more than its hold, "
               "so a `refuse` budget can end past its limit by the overrun of the calls in flight. ",
               ["strict=True", "billing_bound"],
               "(`DESIGN.md` 4.6, 7, 8.1, 8.3, 10 and 11)."),
    CACHE_LEAD: (CACHE_LEAD + CACHE_SECOND, ["models.json", "price_cached_in", "price_cache_write",
                                            "cached_input_tokens", "cache_write_tokens"],
                 "(`DESIGN.md` 4.1, 4.3, 5.1, 5.2, 6, 7, 8.3 and 10). "),
}
# what each keeps besides: a strict budget's promise, and the cache lesson's link by its heading
# review iter-531 should-fix 1: "an unbounded call", where "one" could be read as the bound
KEPT_V1_673 = {EST_LEAD: ["A `strict=True` budget holds each call's `billing_bound` instead and refuses an unbounded "
                          "call, so its spend stays under its limit while providers bill within the bound "],
               CACHE_LEAD: ["[The cache hit rate is a cost number](research/production-lessons.md#the-cache-hit-rate-is-a-"
                            "cost-number)."]}
# each clause and name v1.673 drops, as v1.666 wrote it, the behavioural DESIGN subsection that states it, and a phrase
# of the line there that says it
DROPPED_V1_673 = [
    (EST_LEAD, "the most it can cost given a `max_tokens`, `max_completion_tokens` or `max_output_tokens` in its route's "
     "`provider_options` and its model's context window", "### 4.6 ",
     "its `provider_options` hold at least one of `max_tokens`, `max_completion_tokens` and `max_output_tokens`"),
    # review iter-531 must-fix 1: the charge is 4.6's `.settle_unpriced`, and the calls it is charged for are 7's
    (EST_LEAD, "it charges that bound", "### 4.6 ", "a strict budget adds the bound it held"),
    (EST_LEAD, "for a call that raised anything but a provider error", "## 7. ",
     "releases with `.settle_unpriced`, not `.settle` at 0.0, a hold whose provider call raised"),
    (EST_LEAD, "With a monitor the executor writes each warn crossing and each refusal to the log as a budget record",
     "## 7. ", "with a ledger and a monitor, the executor writes a budget record (8.1 v1.598)"),
    (EST_LEAD, "which `report` skips", "### 8.3 ",
     "`report` drops every record with a `budget_event` key (8.1 v1.598) before it reads any"),
    (EST_LEAD, "`budget_report(records, budgets)` gives each budget's `budget_used_pct`", "### 8.3 ",
     "gives each budget's spend in each window as a percent of its limit, the row's `budget_used_pct`"),
    (EST_LEAD, "as the example at the end of [Monitoring and cost attribution](#monitoring-and-cost-attribution) shows",
     "## 3. ", "a fourth block, at the end of `## Monitoring and cost attribution`"),
    (EST_LEAD, "`model-routing demo --budgets FILE` runs the demo under a file of budgets and exits 4 when a call is "
     "refused", "## 10. ", "the demo ends at that call and the command exits 4 with one line on stderr"),
    (CACHE_LEAD, "USD per 1M input tokens its provider reads from and writes to the prompt cache", "### 4.1 ",
     "USD per 1M input tokens that the provider serves from its prompt cache (a cached read) and that it writes to the "
     "cache (a cache write)"),
    (CACHE_LEAD, "except a row with `price_tiers` or a self-hosted one, which may hold neither", "### 4.1 ",
     "A model with `price_tiers` holding either raises `ValueError`"),
    (CACHE_LEAD, "an absent one is the input price", "### 4.1 ",
     "the `price_cached_in` and `price_cache_write`, each `p_in` when `None`"),
    (CACHE_LEAD, "names the absent field in `cache_price_unknown`", "### 5.1 ",
     "that are `None` on the model while its own measured count is above 0, so those tokens were priced at the call's "
     "input price"),
    (CACHE_LEAD, "beside its `input_tokens` and `output_tokens`", "### 4.3 ",
     "`calibrate_from_results`: a row may carry `cached_input_tokens` and `cache_write_tokens`, either or both, only "
     "beside its `input_tokens` and `output_tokens`"),
    (CACHE_LEAD, "counted inside its `input_tokens`", "### 4.3 ",
     "since a call's cached reads and cache writes are input tokens of it (4.1 v1.587)"),
    (CACHE_LEAD, "and once a model has them on a task it is priced there at their means", "### 5.2 ",
     "`cached` and `write` are `stats.mean_cache_tokens` (4.3 v1.588)"),
    (CACHE_LEAD, "the four parts in its candidate's `cost_breakdown`", "### 5.1 ",
     "the USD parts of its `list_cost` (uncached input, cached reads, cache writes, output)"),
    (CACHE_LEAD, "Only reported counts are priced as hits, never a repeated prompt.", "### 4.1 ",
     "a repeated prompt is never assumed to hit"),
    (CACHE_LEAD, "The inline-or-sub-agent decision reads only `--cached-read-ratio`.", "## 6. ",
     "the delegation costs of 13.2 read no measured cache count"),
    (CACHE_LEAD, "`OpenAICompatibleProvider` maps `usage.prompt_tokens_details.cached_tokens`", "## 6. ",
     "`OpenAICompatibleProvider.complete` reads `usage.prompt_tokens_details.cached_tokens`"),
    (CACHE_LEAD, "`report --cache` gives each group's `cache_hit_rate`", "### 8.3 ",
     "and `cache_hit_rate`, the first over the second"),
    (CACHE_LEAD, "An adapter for another API keeps `input_tokens` inclusive", "## 6. ",
     "an adapter of another API fills `Completion` by 4.1 v1.587's inclusive rule"),
    (CACHE_LEAD, "Anthropic's Messages API counts cache reads and writes outside its `usage.input_tokens`", "## 6. ",
     "Anthropic's Messages API gives `usage.input_tokens` as the"),
    (CACHE_LEAD, "so its adapter returns the sum of `input_tokens`, `cache_read_input_tokens` and "
     "`cache_creation_input_tokens` as the input", "## 6. ", "so its adapter returns the sum of the three as `input_tokens`"),
]
# each quote v1.673 drops, as v1.666 wrote it, and the lesson of research/production-lessons.md that keeps it word for
# word; the 5.2 bullet names the lesson (no behavioural subsection quotes a source)
UBER_CAPS = '"To avoid imposing strict caps, we implemented real-time spend tracking and automated nudges"'
UBER_ALERTS = '"Alerts at 50/80/100% of expected spend so engineers have time to plan."'
MANUS_V1_673 = ("\"If I had to choose just one metric, I'd argue that the KV-cache hit rate is the single most "
                "important metric for a production-stage AI agent.\"")
QUOTES_V1_673 = [(EST_LEAD, UBER_CAPS, "Spend tiers and nudges, not strict caps"),
                 (EST_LEAD, UBER_ALERTS, "Spend tiers and nudges, not strict caps"),
                 (CACHE_LEAD, MANUS_V1_673, "The cache hit rate is a cost number")]


def v1_673_still_there(readme):
    """Each DROPPED_V1_673 clause and QUOTES_V1_673 quote still in the paragraph it was dropped from."""
    found = paragraphs(readme, PRODUCTION)
    return [clause for lead, clause, *_ in DROPPED_V1_673 + QUOTES_V1_673
            if any(p.startswith(lead) and clause in p for p in found)]


def pointer_problems(text, first, names, pointer, cap=POINTER_CAP):
    """What a pointer paragraph lacks by row PROD1ibbb's rule, in a fixed order; [] when it has all."""
    problems = []
    if len(text.encode("utf-8")) > cap:
        problems.append(f"{len(text.encode('utf-8'))} bytes, over {cap}")
    if not text.startswith(first):
        problems.append("no lead sentence")
    problems += [f"no `{n}`" for n in names if n not in text.split("`")[1::2]]
    if text.count(pointer) != 1:
        problems.append("no pointer")
    if "\u2014" in text or "\u2013" in text:
        problems.append("a dash")
    return problems


def test_the_v1_673_two_are_pointer_paragraphs_and_the_section_under_its_cap():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_673}
    assert found == NEW_BYTES_V1_673 and all(n <= POINTER_CAP for n in found.values())
    assert sum(OLD_BYTES_V1_673.values()) - sum(found.values()) == CUT_V1_673 == SECTION_V1_666 - SECTION_V1_673
    # v1.680 (row PROD1j) adds its paragraph in the room v1.673 and v1.674 made, so the section less it is at most
    # v1.673's bytes
    assert size(read("README.md"), PRODUCTION) - ADDED_V1_680 <= SECTION_V1_673 < PRODUCTION_CAP == 30_000
    for lead, (first, names, pointer) in POINTERS_V1_673.items():
        assert pointer_problems(paragraph(lead), first, names, pointer) == [], lead
        assert all(paragraph(lead).count(kept) == 1 for kept in KEPT_V1_673[lead]), lead
    # the budget one keeps no link and the cache one only its lesson's
    assert paragraph(EST_LEAD).count("](") == 0 and paragraph(CACHE_LEAD).count("](") == 1


def test_the_pointer_check_names_what_a_paragraph_lacks():
    first, names, pointer = POINTERS_V1_673[CACHE_LEAD]
    text = paragraph(CACHE_LEAD)
    assert pointer_problems(text, first, names, pointer) == []
    assert pointer_problems(text, first, names, pointer, cap=len(text.encode("utf-8")) - 1) == [
        f"{len(text.encode('utf-8'))} bytes, over {len(text.encode('utf-8')) - 1}"]
    # the cache one's names sit in its lead, so a bare one breaks both (review iter-531 should-fix 2)
    assert pointer_problems(text.replace("`price_cache_write`", "price_cache_write"), first, names, pointer) == [
        "no lead sentence", "no `price_cache_write`"]
    assert pointer_problems(text.replace(pointer, "(`DESIGN.md` 4.1). "), first, names, pointer) == ["no pointer"]
    assert pointer_problems(text.replace("A prompt cache", "The prompt cache", 1), first, names, pointer) == [
        "no lead sentence"]
    # the second sentence is the cache one's lead too, and a bare name is no name (review iter-531 should-fix 2, nit 1)
    assert pointer_problems(text.replace("and a results line its", "and a results row its"), first, names,
                            pointer) == ["no lead sentence"]
    est_first, est_names, est_pointer = POINTERS_V1_673[EST_LEAD]
    assert pointer_problems(paragraph(EST_LEAD).replace("`billing_bound`", "billing_bound"), est_first, est_names,
                            est_pointer) == ["no `billing_bound`"]
    assert pointer_problems(text.replace(" (`DESIGN.md`", " \u2014 (`DESIGN.md`"), first, names, pointer) == [
        "a dash"]


def test_each_clause_and_quote_v1_673_dropped_is_gone_and_stated_where_it_lives():
    design = read("DESIGN.md")
    assert len(DROPPED_V1_673) == 23 and len(QUOTES_V1_673) == 3
    assert v1_673_still_there(read("README.md")) == []
    for lead, clause, heading, phrase in DROPPED_V1_673:
        # a behavioural subsection, never a 5.2 history bullet of the README
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)
    note = read("research/production-lessons.md")
    for lead, quote, lesson in QUOTES_V1_673:
        body = note.split(f"\n### {lesson}\n", 1)[1].split("\n### ", 1)[0]
        assert body.count(quote) == 1, quote
    # the section still links both lessons: step 7 the spend tiers, the cache pointer its own
    section = "\n\n".join(paragraphs(read("README.md"), PRODUCTION))
    assert section.count("(research/production-lessons.md#spend-tiers-and-nudges-not-strict-caps)") == 1
    assert section.count("(research/production-lessons.md#the-cache-hit-rate-is-a-cost-number)") == 1
    assert "neither source gives a saving for its policy" in note


def test_the_v1_673_check_names_a_clause_put_back():
    readme = read("README.md")
    est, cache = paragraph(EST_LEAD), paragraph(CACHE_LEAD)
    one = est.replace(" (`DESIGN.md` 4.6,", "; `budget_report(records, budgets)` gives each budget's `budget_used_pct` "
                      "(`DESIGN.md` 4.6,")
    two = cache.replace("[The cache hit rate", "Manus: " + MANUS_V1_673 + " [The cache hit rate")
    assert one != est and two != cache
    worse = readme.replace(est, one, 1).replace(cache, two, 1)
    assert v1_673_still_there(worse) == ["`budget_report(records, budgets)` gives each budget's `budget_used_pct`",
                                         MANUS_V1_673]
    # a clause in another paragraph is not the dropped one's
    other = "So `budget_report(records, budgets)` gives each budget's `budget_used_pct` from the log."
    elsewhere = readme.replace("\n\n" + est + "\n\n", "\n\n" + est + "\n\n" + other + "\n\n", 1)
    assert elsewhere.count(other) == 1 and v1_673_still_there(elsewhere) == []


def test_design_states_v1_673_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines()
              if line.startswith("- v1.673 README pointer paragraphs (row PROD1ibbba, the first part of row PROD1ibbb): ")]
    for kept in ("the second paragraph on budgets, on the estimate and strict budgets (v1.600), is cut from 1,455 to 397 "
                 "bytes and the one on the prompt cache (v1.594) from 1,586 to 394",
                 "each a pointer paragraph of at most 400 bytes by row PROD1ibbb's rule",
                 "is stated in 3, 4.1, 4.3, 4.6, 5.1, 5.2, 6, 7, 8.3 or 10, so no subsection gains one",
                 "Uber's two under `Spend tiers and nudges, not strict caps`, which step 7 of the walk-through still links",
                 "Manus's under `The cache hit rate is a cost number`, which the cache one links by that heading",
                 "So the section is 27,028 bytes by the 12.8 measure, 2,972 under v1.629's 30,000-byte cap, which stays",
                 # review iter-531 must-fix 1: the bound is 4.6's charge, for the raised calls 7 names
                 "the bound a strict budget charges a call whose cost is not known (4.6), which 7 limits to a provider "
                 "call that raised by a bug or with cache counts `Model.cost` refuses",
                 "it keeps its lead sentence (the cache one its first two, the second naming the option)",
                 "row PROD1ibbbb makes the paragraph on self-hosted rows (1,450 bytes) a pointer paragraph",
                 "and the section less `LATER` at 21,356, v1.666's 23,606 less 2,250",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    lines = five2.splitlines()
    assert lines[lines.index(mine) - 1].startswith("- v1.666 README trim (")
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.673 (")]
    assert line.startswith("- v1.673 (2026-11-26): docs and tests (5.2, row PROD1i, fourth part). ")
    assert len(line.encode("utf-8")) <= 600


# --- v1.674 (row PROD1ibbbb, the second part of row PROD1ibbb): the self-hosted one a pointer paragraph ---------

# as v1.673 (23b02ba) left it and as v1.674 leaves it; the section by the 12.8 measure and row PROD1i's target
OLD_BYTES_V1_674 = {SELF_LEAD: 1_450}
NEW_BYTES_V1_674 = {SELF_LEAD: 368}
CUT_V1_674, SECTION_V1_674, TARGET_V1_674 = 1_082, 25_946, 26_000
# its lead is its first two sentences, the second naming the option and its five keys, as the cache one's (v1.673)
SELF_SECOND = ('A `models.json` row with `"pricing_basis": "self_hosted"` gives `usd_per_hour`, `tokens_per_hour_in`, '
               '`tokens_per_hour_out`, `utilization` and `input_cost_share`. ')
POINTERS_V1_674 = {
    SELF_LEAD: (SELF_LEAD + SELF_SECOND,
                ["models.json", '"pricing_basis": "self_hosted"', "usd_per_hour", "tokens_per_hour_in",
                 "tokens_per_hour_out", "utilization", "input_cost_share", '"base_model"', '"deployment"'],
                "(`DESIGN.md` 4.1, 5.1, 8.1, 8.3, 10 and 11)."),
}
# what it keeps besides: the fine-tune's two keys, which no other README paragraph names
KEPT_V1_674 = {SELF_LEAD: ['A fine-tune names its base with `"base_model"`, and `"deployment"` records where a model '
                           'runs ']}
# each clause and name v1.674 drops, as v1.673 wrote it, the behavioural DESIGN subsection that states it, and a phrase
# of the line there that says it
DROPPED_V1_674 = [
    (SELF_LEAD, "The loader derives its prices per million tokens from them", "### 4.1 ",
     "since its prices are derived: they are `self_hosted_prices` of the five"),
    (SELF_LEAD, "so it is routed like any model", "### 4.1 ",
     "so a self-hosted model is routed by its measured success at its derived price"),
    # v1.653's caveat (review iter-507 should-fix 3), now 4.1's alone
    (SELF_LEAD, "Its throughputs describe one workload, and its split of the hour between input and output is an "
     "approximation you choose.", "### 4.1 ",
     "The throughputs describe one workload, and the split of an hour between input and output is an approximation "
     "the caller chooses"),
    (SELF_LEAD, "and has its base's family", "### 4.1 ", "So a fine-tune is its base's family"),
    (SELF_LEAD, "so with generator isolation on it never judges its base's output", "### 5.2 ",
     "So with `independent_of_generator` a fine-tune has reason `generator_family` when the generator is its base"),
    (SELF_LEAD, "`api` or `self_hosted`", "### 4.1 ",
     "`deployment` says where the model runs: `\"api\"`, a vendor's endpoint, or `\"self_hosted\"`, weights the caller "
     "serves"),
    (SELF_LEAD, "Decisions, attempt records and the `select` table name a self-hosted model's `pricing_basis`",
     "### 5.1 ", "a registry model's candidate holds that model's `pricing_basis`"),
    (SELF_LEAD, "attempt records", "### 8.1 ",
     "only on an attempt whose `model` is a registry model with `pricing_basis` `\"self_hosted\"`"),
    (SELF_LEAD, "the `select` table", "## 10. ", "gains a `pricing_basis` column right before `list_cost`"),
    (SELF_LEAD, "`report --by pricing_basis` splits a log's spend into that part and the rest", "### 8.3 ",
     "so a log's spend splits into what self-hosted models cost by their hour and the rest"),
    (SELF_LEAD, "`model_routing.demo.run_self_hosted_demo()` routes a fictional fine-tune", "## 11. ",
     "`run_self_hosted_demo() -> dict`, in `demo.py` and not in `__all__`"),
    # review iter-532 should-fix 1: the hour and the list-priced rival each by the line that states it
    (SELF_LEAD, "served at 2 USD an hour", "## 11. ", "`usd_per_hour` 2.0"),
    (SELF_LEAD, "against a list-priced model", "## 11. ", "against a list-priced model by measured success"),
    (SELF_LEAD, "once its own runs clear the bar it is the primary at a twelfth of the list model's cost a call",
     "## 11. ", "one whose own runs clear the bar is the primary at a twelfth of the list model's cost a call"),
    # review iter-532 must-fix 1 and 2: the link and the qualifier, which no DESIGN line stated, are the Why of 4.1's
    # v1.581 line from v1.674
    (SELF_LEAD, "([production lessons](research/production-lessons.md#your-own-trained-model-is-a-candidate-kept-to-the-"
     "tasks-it-was-measured-on))", "### 4.1 ",
     "which is the lesson on your own trained model of `research/production-lessons.md`"),
    (SELF_LEAD, "its own number, with no hourly cost given, not a measurement of this library", "### 4.1 ",
     "for its Firm Knowledge model: its own number, with no hourly cost given, not a measurement of this library"),
]
# the quote v1.674 drops, as v1.673 wrote it, and the lesson of research/production-lessons.md that keeps it
SELF_LESSON = "Your own trained model is a candidate, kept to the tasks it was measured on"
HARVEY_V1_674 = '"completes tasks competitively with leading frontier models while reducing cost per query by 90%."'
QUOTES_V1_674 = [(SELF_LEAD, HARVEY_V1_674, SELF_LESSON)]
SELF_LINK = "(research/production-lessons.md#your-own-trained-model-is-a-candidate-kept-to-the-tasks-it-was-measured-on)"


def v1_674_still_there(readme):
    """Each DROPPED_V1_674 clause and QUOTES_V1_674 quote still in the paragraph it left."""
    found = paragraphs(readme, PRODUCTION)
    return [clause for lead, clause, *_ in DROPPED_V1_674 + QUOTES_V1_674
            if any(p.startswith(lead) and clause in p for p in found)]


def test_the_v1_674_one_is_a_pointer_paragraph_and_the_section_at_most_26000_bytes():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_674}
    assert found == NEW_BYTES_V1_674 and all(n <= POINTER_CAP for n in found.values())
    assert sum(OLD_BYTES_V1_674.values()) - sum(found.values()) == CUT_V1_674 == SECTION_V1_673 - SECTION_V1_674
    # review iter-531 nit 2: the section is pinned to its bytes, so a later change to it restates this test;
    # v1.675 (row JUDGE2c) spends some of the room v1.674 made, by its paragraph and the pin paragraph's clause,
    # and v1.680 (row PROD1j) more, by its paragraph
    assert SECTION_V1_674 <= TARGET_V1_674 < PRODUCTION_CAP == 30_000 and PRODUCTION_CAP - SECTION_V1_674 == 4_054
    assert SECTION_V1_674 + ADDED_V1_675 == SECTION_V1_675
    assert size(read("README.md"), PRODUCTION) == SECTION_V1_675 + ADDED_V1_680 == SECTION_V1_680


def test_the_v1_674_one_keeps_its_lead_its_names_and_its_pointer():
    readme = read("README.md")
    for lead, (first, names, pointer) in POINTERS_V1_674.items():
        text = paragraph(lead)
        assert pointer_problems(text, first, names, pointer) == [], lead
        assert all(text.count(kept) == 1 for kept in KEPT_V1_674[lead]), lead
        assert text.endswith(KEPT_V1_674[lead][0] + pointer), lead
        assert text.count("](") == 0, lead
    # the fine-tune's two keys are named nowhere else in README.md, so the pointer keeps them
    assert readme.count('`"base_model"`') == 1 and readme.count('`"deployment"`') == 1


def test_the_v1_674_pointer_check_names_what_it_lacks():
    first, names, pointer = POINTERS_V1_674[SELF_LEAD]
    text = paragraph(SELF_LEAD)
    assert pointer_problems(text, first, names, pointer, cap=len(text.encode("utf-8")) - 1) == [
        f"{len(text.encode('utf-8'))} bytes, over {len(text.encode('utf-8')) - 1}"]
    # a key of the second sentence is the lead's too, while the fine-tune's are names alone
    assert pointer_problems(text.replace("`utilization`", "utilization"), first, names, pointer) == [
        "no lead sentence", "no `utilization`"]
    assert pointer_problems(text.replace('`"base_model"`', '"base_model"'), first, names, pointer) == [
        'no `"base_model"`']
    assert pointer_problems(text.replace(" 10 and 11).", " 10).", 1), first, names, pointer) == ["no pointer"]
    assert pointer_problems(text.replace("is a row priced from its hour", "is priced from its hour"), first, names,
                            pointer) == ["no lead sentence"]


def test_each_clause_and_quote_v1_674_dropped_is_gone_and_stated_where_it_lives():
    design = read("DESIGN.md")
    assert len(DROPPED_V1_674) == 16 and len(QUOTES_V1_674) == 1
    assert v1_674_still_there(read("README.md")) == []
    for lead, clause, heading, phrase in DROPPED_V1_674:
        # a behavioural subsection, never a 5.2 history bullet of the README
        [owner] = [line for line in subsection(design, heading).splitlines() if phrase in line]
        assert "README" not in owner.split(":", 1)[0], (heading, phrase)
    note = read("research/production-lessons.md")
    lesson = note.split(f"\n### {SELF_LESSON}\n", 1)[1].split("\n### ", 1)[0]
    for lead, quote, _ in QUOTES_V1_674:
        assert lesson.count(quote) == 1, quote
    # the quote is the Firm Knowledge model's, as 4.1's Why says
    [result] = [line for line in lesson.splitlines() if line.startswith("- Result: ")]
    assert result.startswith("- Result: its Firm Knowledge model " + HARVEY_V1_674)
    # review iter-532 must-fix 1 and 2: the Why that states the link and the qualifier closes 4.1's v1.581 line
    [owner] = [line for line in subsection(design, "### 4.1 ").splitlines()
               if "which is the lesson on your own trained model of" in line]
    assert owner.startswith("- v1.581 self-hosted pricing (row SELF1a): ")
    assert owner.endswith(". Why (v1.674, row PROD1ibbbb): a model a team trains or serves itself is a route like any "
                          "other, which is the lesson on your own trained model of `research/production-lessons.md`, "
                          "where Harvey reports a 90% cut in cost per query for its Firm Knowledge model: its own number, "
                          "with no hourly cost given, not a measurement of this library.")
    # the section still links the lesson twice: step 5 of the walk-through and the paragraph on task scope
    section = "\n\n".join(paragraphs(read("README.md"), PRODUCTION))
    assert section.count(SELF_LINK) == 2
    assert SELF_LINK in walk_parts(read("README.md"))[1][4] and SELF_LINK in paragraph(SCOPE_LEAD)


def test_the_v1_674_check_names_a_clause_put_back():
    readme = read("README.md")
    text = paragraph(SELF_LEAD)
    back = text.replace(" (`DESIGN.md` 4.1,", "; `report --by pricing_basis` splits a log's spend into that part and the "
                        "rest (`DESIGN.md` 4.1,")
    assert back != text
    assert v1_674_still_there(readme.replace(text, back, 1)) == [
        "`report --by pricing_basis` splits a log's spend into that part and the rest"]
    # a clause in another paragraph is not the dropped one's
    other = "So `report --by pricing_basis` splits a log's spend into that part and the rest."
    elsewhere = readme.replace("\n\n" + text + "\n\n", "\n\n" + text + "\n\n" + other + "\n\n", 1)
    assert elsewhere.count(other) == 1 and v1_674_still_there(elsewhere) == []


def test_design_states_v1_674_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines()
              if line.startswith("- v1.674 README pointer paragraph (row PROD1ibbbb, the second part of row PROD1ibbb): ")]
    for kept in ("the paragraph on self-hosted rows (v1.585) is cut from 1,450 to 368 bytes, a pointer paragraph by row "
                 "PROD1ibbb's rule (SCOUT iter 530)",
                 "it keeps its lead sentence and the one after it, which names the option",
                 "a fine-tune's `\"base_model\"` and `\"deployment\"`, which no other README paragraph names",
                 "and its one pointer to this file (4.1, 5.1, 8.1, 8.3, 10 and 11)",
                 "is stated in 4.1, 5.1, 5.2, 8.1, 8.3, 10 or 11, and `DROPPED_V1_674` pins it",
                 # review iter-532 must-fix 1 and 2
                 "the link and the qualifier of the Harvey sentence, which no line stated, are 4.1's from this version, "
                 "a Why on its v1.581 line",
                 "the caveat v1.653 brought back that its throughputs describe one workload",
                 "which step 5 of the walk-through and the paragraph on task scope still link",
                 "under `Your own trained model is a candidate, kept to the tasks it was measured on` (`QUOTES_V1_674`)",
                 "So the section is 25,946 bytes by the 12.8 measure, at most row PROD1i's 26,000 and 4,054 under "
                 "v1.629's 30,000-byte cap, which stays",
                 "the section less `LATER` is 20,274, v1.673's 21,356 less 1,082",
                 "with this part rows PROD1ibbb, PROD1ibb, PROD1ib and PROD1i close",
                 "tests/test_self_hosted_demo.py restates its pins of it",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    lines = five2.splitlines()
    assert lines[lines.index(mine) - 1].startswith("- v1.673 README pointer paragraphs (")
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.674 (")]
    assert line.startswith("- v1.674 (2026-11-26): docs and tests (5.2, row PROD1i, fifth part). ")
    assert line.count("4.1 gaining a Why with the link's lesson and the Harvey number's qualifier") == 1
    assert len(line.encode("utf-8")) <= 600


# --- v1.675 (row JUDGE2c, the third part of row JUDGE2): the self-consistency minimum -----------------------------

# the new paragraph's own bytes, LATER's eighth entry less its blank line, and the pin paragraph's clause on 5.2
# rules 5g and 5h (v1.668), which tests/test_pin_docs.py's HARD reads; tests/test_self_consistency_docs.py checks
# the paragraph's claims
CONSISTENCY_BYTES_V1_675 = 827
PIN_CLAUSE_V1_675 = ", inconsistent or of unknown consistency under `min_self_consistency`"
GROWN_V1_675 = {PIN_LEAD: 69}
ADDED_V1_675 = CONSISTENCY_BYTES_V1_675 + 2 + sum(GROWN_V1_675.values())
SECTION_V1_675 = 26_844


def test_the_v1_675_paragraph_and_clause_and_the_section_at_its_bytes():
    text = read("README.md")
    assert LATER[7] == (CONSISTENCY_LEAD, CONSISTENCY_BYTES_V1_675 + 2)  # the eighth entry; v1.680's follows it
    assert len(paragraph(CONSISTENCY_LEAD).encode("utf-8")) == CONSISTENCY_BYTES_V1_675
    pin = paragraph(PIN_LEAD)
    assert pin.count(PIN_CLAUSE_V1_675) == 1 and len(PIN_CLAUSE_V1_675.encode("utf-8")) == GROWN_V1_675[PIN_LEAD]
    assert len(pin.encode("utf-8")) == NEW_BYTES_V1_666[PIN_LEAD] + GROWN_V1_675[PIN_LEAD] == 1_793
    assert pin.count("rules 1 to 5h of `DESIGN.md` 5.2") == 1 and "5f" not in pin
    # the section is pinned to its bytes, so a later change to it restates this test (review iter-531 nit 2):
    # v1.680 (row PROD1j) adds its paragraph after this one
    assert SECTION_V1_675 == SECTION_V1_674 + ADDED_V1_675 < PRODUCTION_CAP == 30_000
    assert PRODUCTION_CAP - SECTION_V1_675 == 3_156
    assert size(text, PRODUCTION) == SECTION_V1_675 + ADDED_V1_680 == SECTION_V1_680
    assert size(without_later(text), PRODUCTION) == 20_343


def test_design_states_v1_675_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines()
              if line.startswith("- v1.675 README self-consistency minimum (row JUDGE2c, the third part of JUDGE2; ")]
    for kept in ("The new paragraph is 827 bytes, the eighth entry of tests/test_readme_trim.py's `LATER`",
                 "the pin paragraph grows from 1,724 to 1,793 bytes",
                 "so the section is 26,844 bytes by the 12.8 measure, 3,156 under v1.629's 30,000-byte cap, which stays",
                 "the section less `LATER` is 20,343, v1.674's 20,274 and the clause's 69 bytes",
                 "says the hard checks a pin keeps are rules 1 to 5h, where it said 1 to 5f",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    lines = five2.splitlines()
    assert lines[lines.index(mine) - 1].startswith("- v1.674 README pointer paragraph (")
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.675 (")]
    assert line.startswith("- v1.675 (2026-11-26): docs and tests (5.2, row JUDGE2, third part). ")
    assert line.count("so the section is 26,844 bytes, 3,156 under the 30,000-byte cap") == 1
    assert len(line.encode("utf-8")) <= 600


# --- v1.680 (row PROD1j): the pair route ----------------------------------------------------------------------------

# the new paragraph's own bytes, LATER's ninth entry less its blank line; tests/test_pair_route_docs.py checks its
# claims, its names and its link
PAIR_BYTES_V1_680, PAIR_CAP_V1_680 = 587, 600
ADDED_V1_680 = PAIR_BYTES_V1_680 + 2
SECTION_V1_680 = 27_433


def test_the_v1_680_paragraph_and_the_section_at_its_bytes():
    text = read("README.md")
    assert LATER[8] == LATER[-1] == (PAIR_LEAD, ADDED_V1_680) and len(LATER) == 9
    assert len(paragraph(PAIR_LEAD).encode("utf-8")) == PAIR_BYTES_V1_680 <= PAIR_CAP_V1_680
    # the section is pinned to its bytes, so a later change to it restates this test (review iter-531 nit 2)
    assert size(text, PRODUCTION) == SECTION_V1_680 == SECTION_V1_675 + ADDED_V1_680 < PRODUCTION_CAP == 30_000
    assert PRODUCTION_CAP - SECTION_V1_680 == 2_567
    # the paragraph is in LATER, so the section less LATER keeps v1.675's bytes
    assert size(without_later(text), PRODUCTION) == 20_343


def test_design_states_v1_680_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = subsection(design, "### 5.2 ")
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.680 README pair route (row PROD1j; ")]
    for kept in ("ends with one paragraph of at most 600 bytes on routing a delegating harness's root and sub-agent "
                 "models as a pair, right after the one on the self-consistency minimum (v1.675)",
                 "The new paragraph is 587 bytes, the ninth entry of tests/test_readme_trim.py's `LATER`",
                 "so the section is 27,433 bytes by the 12.8 measure, 2,567 under v1.629's 30,000-byte cap, which stays",
                 "the section less `LATER` stays 20,343",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    lines = five2.splitlines()
    assert lines[lines.index(mine) - 1].startswith("- v1.675 README self-consistency minimum (")
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.680 (")]
    assert line.startswith("- v1.680 (2026-11-27): docs and tests (5.2, row PROD1j). ")
    assert line.count(", so the section is 27,433 bytes, 2,567 under the 30,000-byte cap. ") == 1
    assert line.endswith(" README.md transcripts and every evidence file keep their bytes.")
    assert len(line.encode("utf-8")) <= 600
