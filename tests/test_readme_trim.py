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
section to pay for them, each pinned in DROPPED_V1_653 to the line of 4.1, 4.2, 4.3, 7, 8.2 or 11 that states it,
so the section is 23,995 bytes, at most 24,000. The v1.647 and v1.652 lists lose the entries v1.653 brings back.
These tests failed on v1.652's README and pass on v1.653's.
"""

from pathlib import Path

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
ENDS = {"### 4.7 ": "\n## 5. ", "### 8.3 ": "\n## 9. ", "## 10. ": "\n## 11. ", "### 4.1 ": "\n### 4.2 ",
        "### 5.2 ": "\n### 5.3 ", "## 6. ": "\n## 7. ", "## 7. ": "\n## 8. ", "## 11. ": "\n## 12. ",
        "### 4.3 ": "\n### 4.4 ", "### 4.5 ": "\n### 4.6 ", "### 4.6 ": "\n### 4.7 ",
        "### 8.1 ": "\n### 8.2 ", "### 4.2 ": "\n### 4.3 ", "### 8.2 ": "\n### 8.3 "}


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def paragraph(lead):
    [found] = [p for p in paragraphs(read("README.md"), PRODUCTION) if p.startswith(lead)]
    return found


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
    assert "It requires the bar to admit the challenger first and exits 3 when it does not. " in paragraph(PROMOTE_LEAD)
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
    for lead in OLD_BYTES_V1_648:
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
    for lead in OLD_BYTES_V1_650:
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
    assert "its policy, for which it gives no saving, not a measurement of this library" in paragraph(EST_LEAD)
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
    assert found == NEW_BYTES_V1_651
    assert sum(OLD_BYTES_V1_651.values()) - sum(found.values()) == 399
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
    # v1.653 (row PROD1h) changes three of the nine again, which NEW_BYTES_V1_653 holds; the six it left keep their
    # v1.652 bytes
    assert {k: v for k, v in found.items() if k not in NEW_BYTES_V1_653} == {
        k: v for k, v in NEW_BYTES_V1_652.items() if k not in NEW_BYTES_V1_653}
    assert all(found[k] == NEW_BYTES_V1_653[k] for k in found if k in NEW_BYTES_V1_653)
    assert sum(OLD_BYTES_V1_652.values()) - sum(NEW_BYTES_V1_652.values()) == 1_166
    assert size(read("README.md"), PRODUCTION) <= TARGET < PRODUCTION_CAP == 30_000


def test_the_v1_652_nine_keep_their_quotes_and_links_and_no_dash():
    for lead in OLD_BYTES_V1_652:
        text = paragraph(lead)
        assert text.startswith(lead), lead
        assert text.count("](") == {PROMOTE_LEAD: 2, EST_LEAD: 2, SHADOW_LEAD: 0, LAT_LEAD: 0}.get(lead, 1), lead
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
    assert "Only reported counts are priced as hits, never a repeated prompt. " in paragraph(CACHE_LEAD)
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
# the six paragraphs v1.653 changes, as v1.652 (f6d28c2) left them and as v1.653 leaves them
OLD_BYTES_V1_653 = {VAR_LEAD: 1_468, SELF_LEAD: 1_382, PROMOTE_LEAD: 1_693, SHADOW_LEAD: 1_641, THREADS_LEAD: 632,
                    LAT_LEAD: 1_389}
NEW_BYTES_V1_653 = {VAR_LEAD: 1_486, SELF_LEAD: 1_450, PROMOTE_LEAD: 1_708, SHADOW_LEAD: 1_595, THREADS_LEAD: 549,
                    LAT_LEAD: 1_420}
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
]
# what leaves to pay for it, as v1.652 (f6d28c2) wrote it, each pinned the same way
DROPPED_V1_653 = [
    (SELF_LEAD, "In place of list prices, ", "### 4.1 ",
     "prices derived from what an hour of the caller's own serving costs"),
    (SELF_LEAD, "unmeasured it is not routed, ", "## 11. ",
     "they give reasons `insufficient_samples`, `passes`, `passes` and `generator_family`"),
    (SHADOW_LEAD, ", from 0, the default, to 1,", "### 4.2 ",
     "`shadow_rate: float = 0.0`, the share of the task's `.call`s also sent to a shadow route"),
    (SHADOW_LEAD, ", with no fallback,", "## 7. ",
     "the executor makes one provider call of the shadow route on the same `messages`, by step 2 with no fallback"),
    (LAT_LEAD, ", in milliseconds,", "### 4.2 ", "the highest 95th-percentile time in milliseconds a route may take"),
    (LAT_LEAD, ", so below 20 trials it is the slowest of them", "### 4.3 ", "the slowest of them while `n` is below 20"),
    (THREADS_LEAD, "(a rotated log's files oldest first)", "### 8.2 ", "give such files in the order they were written"),
    (THREADS_LEAD, ", since a log given twice would count it twice", "### 8.2 ",
     "which would count its calls and its spend twice"),
]
NAMES_V1_653 = {THREADS_LEAD: ["Executor", "Monitor", "BudgetLedger", "id_factory", "random", "now", "clock",
                               "report", "pairs", "--log PATH"]}


def test_the_v1_653_six_and_the_section_at_most_24000_bytes():
    found = {lead: len(paragraph(lead).encode("utf-8")) for lead in OLD_BYTES_V1_653}
    assert found == NEW_BYTES_V1_653
    assert sum(NEW_BYTES_V1_653.values()) - sum(OLD_BYTES_V1_653.values()) == 3
    assert size(read("README.md"), PRODUCTION) == 23_995 <= TARGET < PRODUCTION_CAP == 30_000


def test_the_v1_653_caveats_and_qualifiers_are_back_where_design_states_them():
    design = read("DESIGN.md")
    assert len(BACK_V1_653) == 5
    for lead, text, heading, phrase in BACK_V1_653:
        assert paragraph(lead).count(text) == 1, text
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


def test_the_v1_653_six_keep_their_names_quotes_and_links_and_no_dash():
    for lead in OLD_BYTES_V1_653:
        text = paragraph(lead)
        assert text.startswith(lead), lead
        assert "\u2014" not in text and "\u2013" not in text
    names = paragraph(THREADS_LEAD).split("`")[1::2]
    assert [n for n in NAMES_V1_653[THREADS_LEAD] if n not in names] == []
    assert paragraph(SELF_LEAD).count("](") == 1 and paragraph(PROMOTE_LEAD).count("](") == 2
    assert paragraph(VAR_LEAD).count("](") == 1 and paragraph(THREADS_LEAD).count("](") == 0


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
                 "each stated on a line of 4.1, 4.2, 4.3, 7, 8.2 or 11, so no subsection gains one",
                 "so the section is 23,995 bytes by the 12.8 measure, at most row PROD1g's 24,000 and under v1.629's "
                 "30,000-byte cap, which stays",
                 "No package module, evidence file or README transcript changes."):
        assert mine.count(kept) == 1, kept
    assert five2.index("\n- v1.652 README trim (") < five2.index("\n" + mine)
    assert len(mine.encode("utf-8")) <= 6_000
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.653 (")]
    assert line.startswith("- v1.653 (2026-11-25): docs and tests (5.2, row PROD1h). ")
    assert len(line.encode("utf-8")) <= 600
