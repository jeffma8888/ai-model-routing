# Can the delegation evidence run on a second dataset? (as of 2026-11-06)

Question: the delegation results (`DESIGN.md` 13.9 and 13.10) read one dataset, the AutoBench 2026 token matrix, while the routing evidence reads three (RouterBench, AutoBench with its judges, tau2-bench). Can the 13.9 harness run on tau2-bench, the one other committed dataset with a per-item cost, and would a `cost_blind`-only run on a dataset with no cost, such as LiveCodeBench, mean anything?

Method: the 12 tau2-bench run files pinned in `evidence/tau2-bench/convert.py` (revision 033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f, MIT), each checked against its pinned sha256 by the converter's `fetch` and read from the evidence cache outside the repo with the standard-library `json` module, trial 0 only (the converter's default, `DESIGN.md` 12.14). A model call is an agent message (role `assistant`) whose `usage` is not `null`; every conversation's first agent message is a fixed greeting with `usage` `null` and a cost of 0, so it is not counted. Split sizes are from `model_routing.split_items` over the converter's item IDs (`<domain>|<task id>`) at the default `calibration_fraction` 0.5 and seeds 0 to 49. Prices and context windows are as the vendors' pages stated them when opened on 2026-11-06. Nothing from the files is committed.

The 13.1 inputs named below are those of `Router.decide_delegation`: the parent's context C, the brief B, the result R, the work's input and output per call S_in and S_out, the number of work calls K, the later parent calls T, and whether inline work takes a parent call of its own (`inline_separate_call`).

## Summary

- Not as the harness stands. tau2-bench has what the routing evidence uses (a success from program checks and a recorded cost for every one of the 4 agents on each of the 278 items) and per-call token counts, but each item is a conversation of 2 to 100 agent model calls, and the 13.9 harness prices an item as one call, or as K calls with one K for every item of a point
- Fed the converter's `--tokens` counts (each the sum over a conversation's calls), the K = 1 costs would charge the parent's context once where a parent doing the conversation inline re-reads it on every call, and would have later parent calls re-read the summed prompts, which are 7.32 to 19.13 times (median per agent and domain) the last call's prompt plus completion
- The recorded costs of the three OpenAI agents fit, call by call, list price with about three quarters of their prompt tokens at the cached-input price: an automatic prompt-cache discount inferred from the costs, since no field records cached counts or names a price table. At list price, as 13.9 prices every row, the same tokens cost 1.79 to 2.35 times what those runs recorded. The one Anthropic agent's costs are exactly list price
- For o4-mini (run at reasoning effort `high`) most next prompts are shorter than the previous prompt plus its completion, so neither its new input per call nor the output a later call re-reads can be read from the usage
- Per domain, retail and telecom calibration halves always reach the default `min_samples` of 30; airline's do not on 40 of the 50 seeds
- A `cost_blind`-only delegation run on LiveCodeBench would be the `cost_blind` routing choice with the parent kept on ties, beside costs made from invented token counts, so it would not test delegation
- Recommendation: a documented limitation now, and a harness change (per-item work calls and sizes) before any tau2-bench delegation converter

## What tau2-bench records for each 13.1 input

| Input | Recorded? | What the files hold (trial 0) |
|---|---|---|
| success | yes | `reward_info.reward`, 0 or 1 per (task, agent), from program checks (12.14) |
| K | yes, per conversation | 2 to 100 model calls per conversation; the medians per agent and domain are 10 to 23 |
| S_in, S_out | only as usage | each call's `prompt_tokens` counts everything that call read: the agent's system prompt with the domain policy and the tool schemas, then the conversation so far. The new input of a call can be split off for three agents (below), not for o4-mini |
| the work's own base context | only as usage | the first model call reads 3,252 to 8,245 prompt tokens (the system prompt, the greeting and the user's first message): 3,252 to 3,670 for the three OpenAI agents in airline and retail and 6,273 to 6,321 in telecom; 5,177 to 5,378 and 8,201 to 8,245 for `anthropic/claude-3-7-sonnet-20250219` |
| C | no | there is no parent: the agent is the top-level model, and the only other model in a conversation is the user simulator |
| B | no | nothing is handed off. The nearest number is the first call's read above: a delegate needs the policy and the tool schemas, in its brief or its own system prompt, so the 500-token brief of the AutoBench grid would under-state it |
| R | no | a conversation ends when the user simulator stops it (1,104 of the 1,112 trial-0 conversations) or at the step limit (8), and nothing is handed back to a parent |
| T, `inline_separate_call` | no | no parent call follows the work |
| cached reads | no | `usage` has only `prompt_tokens` and `completion_tokens`; the cached share is inferred from the cost below |

Splitting the new input off. For a call j after the first, write new(j) = prompt(j) - prompt(j - 1) - completion(j - 1), the tokens added since the previous call if every prompt re-sends the whole history:

- `anthropic/claude-3-7-sonnet-20250219`, `openai/gpt-4.1-2025-04-14` and `openai/gpt-4.1-mini-2025-04-14`: new(j) is at least 0 on all 12,399 such steps (4,093, 3,475 and 4,831), with medians of 55 to 227 tokens per agent and domain. So for these three the per-call new input and the output are readable, and the summed counts are the closed form of 13.2 v1.38 only if the calls are of equal size, which they are not (new(j) runs from 7 to 4,337)
- `openai/o4-mini-2025-04-16`: new(j) is negative on 2,962 of its 3,849 steps (368 of 487 in airline, 871 of 1,389 in retail, 1,723 of 1,973 in telecom; as low as -2,248), which fits completion counts that include reasoning tokens a later call does not re-read. 13.2 charges each work call's output as re-read by the calls after it, so for this agent the usage gives neither S_out as re-read nor S_in
- Summed over a conversation, the prompts are 1.91 to 65.71 times (medians 7.32 to 19.13 per agent and domain) the last call's prompt plus completion. The largest last-call prompt is 33,765 tokens (`anthropic/claude-3-7-sonnet-20250219`, telecom), while the summed counts reach 2,096,093 (the converter's `--tokens` range, 12.14)

## What the 13.9 harness would do with the converter's `--tokens` matrix

The converter's `--tokens` rows carry, per (item, agent), the summed `prompt_tokens` and `completion_tokens` of that conversation's calls. 13.9 would read them as one call's in(i, m) and out(i, m):

- delegated, `P.cost(0, B) + D.cost(B + in(i, D), out(i, D)) + (1 + T) * P.cost(B + R, 0)`: the delegate's term is close to its conversation at list price, except that it reads B once where each of its calls would re-read it
- inline with a call of its own, `P.cost(C + in(i, P), out(i, P)) + (1 + T) * P.cost(in(i, P) + out(i, P), 0)`: C is charged once, where a parent doing the conversation inline re-reads C on each of its calls (13.2 v1.38 charges K * C), so inline is under-charged by about (K - 1) * C; and the 1 + T later calls re-read the summed prompts, 7.32 to 19.13 times (median) the last call's prompt plus completion, so inline is over-charged there. Both errors grow with K, which varies by conversation, so no grid point corrects them
- a point's `work_calls` would not help: it sets one K for every item, and each of its K calls is priced at the item's recorded sizes, which on tau2-bench are already a whole conversation
- the 13.4 inline check reads S_in and S_out as the `median_low` of the calibration rows. Over all trial-0 rows of a domain those medians are 54,910 and 1,344 (airline), 64,821 and 1,220 (retail) and 152,156 and 1,922 (telecom). On the calibration rows of each of the 50 seeds, at C = 64,000, a grid point of 13.10, the telecom check is 210,536 to 230,765 tokens, over the 200,000-token window of `openai/o4-mini-2025-04-16` on every seed, so inline would be blocked (`parent_context_full`) for that parent though no telecom conversation's last call read more than 33,765 tokens (airline 112,482 to 126,853, retail 124,386 to 133,006)

## Prices and context windows

13.9 prices every row from the registry (it ignores `cost_usd`, because a delegated item charges one item's tokens to two models), so all four agents would need dated list prices and context windows in a registry. None is in `model_routing/data/models.json`.

| Agent | Page (opened 2026-11-06) | Status on that page | Input, cached input, output (USD per 1M tokens) | Context window |
|---|---|---|---|---|
| `openai/gpt-4.1-2025-04-14` | https://platform.openai.com/docs/models/gpt-4.1 | Deprecated | 2.00, 0.50, 8.00 | 1,047,576 |
| `openai/gpt-4.1-mini-2025-04-14` | https://platform.openai.com/docs/models/gpt-4.1-mini | Deprecated | 0.40, 0.10, 1.60 | 1,047,576 |
| `openai/o4-mini-2025-04-16` | https://platform.openai.com/docs/models/o4-mini | Shut down | 1.10, 0.275, 4.40 | 200,000 |
| `anthropic/claude-3-7-sonnet-20250219` | https://docs.anthropic.com/en/docs/about-claude/pricing and https://docs.anthropic.com/en/docs/about-claude/model-deprecations | retired on the Claude API on February 19, 2026 (deprecations page); the pricing page has no row for it | not stated on a current page; the recorded costs give 3 and 15 (below) | not found on a current page |

The OpenAI pricing page (https://platform.openai.com/docs/pricing), opened the same day, names the two GPT-4.1 snapshots only in a table with a training price (fine-tuned models) and does not name o4-mini.

What the recorded costs imply, per model call at trial 0:

- `anthropic/claude-3-7-sonnet-20250219`: all 4,371 calls cost exactly 3 USD per 1M prompt tokens plus 15 per 1M completion tokens (largest difference 1.4e-17 USD), and its 278 conversations sum to 128.132292 USD at list price and as recorded
- the three OpenAI agents: on every one of their 12,989 calls (3,753, 5,109 and 4,127) the recorded cost equals the model page's price with k prompt tokens at the cached-input price, for a whole number k that is 0 on 391 calls and a multiple of 128 of at least 1,024 on the other 12,598. That fits OpenAI's automatic prompt caching, whose guide (https://platform.openai.com/docs/guides/prompt-caching, opened 2026-11-06) says reported cached tokens are rounded "down to the nearest multiple of 128". The inferred cached tokens are 77.42% of `openai/gpt-4.1-2025-04-14`'s prompt tokens, 78.94% of `openai/gpt-4.1-mini-2025-04-14`'s and 74.75% of `openai/o4-mini-2025-04-16`'s
- so list price over-states what these runs recorded: 51.722764 against 22.986508 USD (2.25 times), 16.954327 against 7.217661 (2.35) and 37.003552 against 20.66512 (1.79) over each agent's 278 conversations, while the Anthropic agent's ratio is 1.0. 13.2 v1.41 prices a cached read only on the parent's reads of C, never on re-reads of the work's own history and never for the delegate, so on these files a list-price comparison would move every cost between the Anthropic agent and the three OpenAI agents by about a factor of two
- this answers what 12.14 leaves open ("the files do not name the price table behind it") only as an inference from the costs: no field names the prices or the cached counts

## Calibration halves (12.2)

| Task | Items | Calibration half over seeds 0 to 49 | Held-out half | Seeds with a calibration half under 30 |
|---|---|---|---|---|
| airline | 50 | 16 to 35 | 15 to 34 | 40 (7 of seeds 0 to 9) |
| retail | 114 | 45 to 65 | 49 to 69 | 0 |
| telecom | 114 | 44 to 68 | 46 to 70 | 0 |
| all (pooled) | 278 | 114 to 158 | 120 to 164 | 0 |

- Per domain, retail and telecom reach the default `min_samples` on every seed, so a parent and its delegates can clear a bar there
- On airline's 40 short seeds no model has enough trials to clear (5.2 rule 6), so the parent does not clear and the delegate's `select` has no passing candidate: unless 13.4 blocks inline (row 1), every decision there is 13.5 row 7 (`none_clear`), settled by the two calibration bounds, and in `cost_effective` by cost only when the bounds are equal. A per-domain run would have to state that, or pool the domains
- With 4 agents, each parent has 4 possible delegates (the other 3 and its own model)

## A `cost_blind`-only run on a dataset with no cost (LiveCodeBench)

- 13.9 needs `input_tokens` and `output_tokens` on every row and prices both paths with them. LiveCodeBench records neither (`research/datasets.md`), so the rows would carry sizes chosen by hand
- In `cost_blind` no cost is compared: 13.5 rows 4 and 7 compare bounds, and the delegate's `select` ranks passing models by `(routing_cost, -quality_lb, model_id)` with `routing_cost` 0.0 for every model (5.2, 5.3). The sizes reach only the two window checks, 13.4 rule 3 and 5.2 rule 5
- So, with sizes that fit every window, the `cost_blind` decision for a parent picks whichever of the parent and the highest-bound model has the higher calibration bound (row 2 when only the delegate clears, row 4 when both do, row 5 when only the parent does, row 7 when neither does), the parent on a tie. Scored on the held-out half, that is the `cost_blind` routing choice with the parent kept on ties, which the routing evidence planned for LiveCodeBench (backlog row E11) will show; the inline and delegated costs printed beside it would follow from the chosen sizes, not from the data
- What delegation trades, the parent's context against the brief, the result and the delegate's price, never enters such a run. It would not be delegation evidence

## Recommendation

- A documented limitation, not a converter now: the delegation evidence stays on the AutoBench matrix. tau2-bench has the labels, per-call usage and a recorded cost for all four agents, but each item is a whole multi-call conversation, which the 13.9 harness cannot price: one call on summed counts mis-prices both paths in directions that grow with K, a grid K applies one K to conversations of 2 to 100 calls, and list price ignores the cache discount that the OpenAI agents' recorded costs imply on about three quarters of their prompt tokens. The README Limitations section and `DESIGN.md` 13.9 should say the delegation evidence reads one dataset and link this file (superseded by `DESIGN.md` 13.12 v1.79: once 13.9 v1.74 priced each conversation on its own calls and 12.14 v1.77 wrote such rows, the tau2-bench delegation results were committed in [evidence/tau2-bench-delegation/RESULTS.md](../evidence/tau2-bench-delegation/RESULTS.md), and the README says the delegation evidence reads two datasets)
- What would have to come first, as a library change specified in `DESIGN.md` 13.9 before any converter: a row that carries its own work calls and per-call sizes, so that each item is priced on its own conversation: the first call's read as the work's base context, which the brief has to carry, and then either the sequence of each call's new input and output, or the exact totals 13.2's K-call reads need, which are K, the input weighted by the number of calls that read it (call i's new input is read by calls i to K, so K - i + 1 times, and its output by calls i + 1 to K) and the plain sums of input and output that the later parent calls re-read. Means per call are not enough: they drop each call's position, so they price unequal calls wrongly (with K = 2, no base context, new inputs 1 and 9 and outputs 2 and 2, the two prompts read 1 and 12 tokens, 13 in all, while means of 5 and 2 give 3 * 5 + 1 * 2 = 17), and a mean-based row could only be a stated approximation; a stated rule for agents whose completion counts include reasoning that later calls do not re-read (o4-mini here); and either cached re-reads of the work's history at a stated ratio, or a statement that list price over-states agents that cached
- Then a tau2-bench delegation converter, with these assumptions stated: the brief carries the domain policy and the tool schemas, so it is at least the first call's read (3,252 to 8,245 tokens) (superseded by `DESIGN.md` 13.9 v1.74: the first call's read is the work's own input on both paths, and B is the hand-off alone); the delegate is credited with its own whole conversation, the lossless-brief assumption of the AutoBench results; per-domain tasks with airline's short halves stated, or the pooled task; the Anthropic agent priced from its recorded costs, since no current page states its price; and four 2025 agents, of which the vendors list two as deprecated, one as shut down and one as retired
- LiveCodeBench stays `cost_blind` routing evidence only (row E11), with no delegation run

## LLMRouterBench (2026-11-09)

Question: can the LLMRouterBench matrix (`DESIGN.md` 12.18), whose items are single calls, each with a success, a recorded cost and both token counts apart from 10 null output counts, feed the 13.9 harness, which prices every row from a registry at list price and needs both counts on every row of a complete matrix? Prices are from the vendor pages below, opened 2026-11-09; every other number is a line of [llmrouterbench_prices.py](llmrouterbench_prices.py) on the converter's default matrix.

- Not with the whole pool: none of the vendor pages fetched prices most of its models, and the recorded costs give an exact price table for only some of the rest
- A vendor page states a price for 4 of the 13 pool models: `anthropic/claude-sonnet-4` (3 and 15 USD per 1M input and output tokens), `openai/gpt-5` and `openai/gpt-5-chat` (1.25 and 10; the first is deprecated and the second shut down) and `z-ai/glm-4.6` (0.6 and 2.2). None was found in the pages fetched for the other 9: both Gemini 2.5 models are deprecated and off Google's pricing page, DeepSeek's page names only its V4 models, and the Moonshot, Qwen and InternLM pages served no readable price table
- The recorded costs of 5 models are one input and one output price on every kept item, within 1e-09 USD: `anthropic/claude-sonnet-4` at 3 and 15, its list price; `deepseek/deepseek-r1-0528` at 0.5 and 2.15, `deepseek/deepseek-v3-0324` at 0.25 and 0.88 and `deepseek/deepseek-v3.1-terminus` at 0.27 and 1; and `internlm/intern-s1` at 0.18 and 0.54. For the other 8 no pair can be within 1e-09 USD of every recorded cost: even the unrounded least-squares pair is off by 0.004045 to 0.297965 USD at its worst item, where a pair within 1e-09 USD of every cost would leave it at most the square root of the item count times 1e-09 USD
- Recorded over list price on the same token counts is 1.000 for `anthropic/claude-sonnet-4`, 0.996 for `z-ai/glm-4.6`, 0.967 for `openai/gpt-5-chat` and 0.906 for `openai/gpt-5`, inside the 0.853 to 1.502 that 12.18 gives against the dataset README's own price list
- A delegation run loses 10 of the 12066 items to a null token count, 5 in `hle` and 5 in `simpleqa`, the 10 negative `openai/gpt-5` completion counts that 12.18 writes as null, so 130 rows, and keeps 12056 items
- No prompt reaches more than 16563 input tokens, so no price tier by prompt length applies to any of these calls

### List prices

| Model | Page (opened 2026-11-09) | Status on that page | Input, output (USD per 1M tokens) | Context window on that page |
|---|---|---|---|---|
| `anthropic/claude-sonnet-4` | https://platform.claude.com/docs/en/about-claude/pricing | listed in the model pricing table | 3, 15 | not on that page |
| `deepseek/deepseek-r1-0528` | https://api-docs.deepseek.com/quick_start/pricing | not named: the page names only `deepseek-flash` (served by DeepSeek-V4.1-Flash-1017) and `deepseek-v4-pro` | none found | not on that page |
| `deepseek/deepseek-v3-0324` | https://api-docs.deepseek.com/quick_start/pricing | not named: the page names only `deepseek-flash` (served by DeepSeek-V4.1-Flash-1017) and `deepseek-v4-pro` | none found | not on that page |
| `deepseek/deepseek-v3.1-terminus` | https://api-docs.deepseek.com/quick_start/pricing | not named: the page names only `deepseek-flash` (served by DeepSeek-V4.1-Flash-1017) and `deepseek-v4-pro` | none found | not on that page |
| `google/gemini-2.5-flash` | https://ai.google.dev/gemini-api/docs/pricing and https://ai.google.dev/gemini-api/docs/deprecations | the pricing page names no Gemini 2.5 model; the deprecations page says `gemini-2.5-flash` is deprecated and no longer available to select in Google AI Studio | none found | not on that page |
| `google/gemini-2.5-pro` | https://ai.google.dev/gemini-api/docs/pricing and https://ai.google.dev/gemini-api/docs/deprecations | the pricing page names no Gemini 2.5 model; the deprecations page says `gemini-2.5-pro` is deprecated and that from December 1, 2026 API requests to it route to `gemini-3.8-flash` | none found | not on that page |
| `z-ai/glm-4.6` | https://docs.z.ai/guides/overview/pricing | listed among the text models | 0.6, 2.2 | not on that page |
| `openai/gpt-5` | https://platform.openai.com/docs/models/gpt-5 | Deprecated | 1.25, 10 | 400,000 |
| `openai/gpt-5-chat` | https://platform.openai.com/docs/models/gpt-5-chat-latest | Shut down | 1.25, 10 | 128,000 |
| `internlm/intern-s1` | https://internlm.intern-ai.org.cn/api/document | the page served no readable model or price text to a plain HTTP fetch | none found | not on that page |
| `moonshotai/kimi-k2-0905` | https://platform.moonshot.ai/docs/pricing/chat | not named in the page's text, which names the K3 and K2 series and links guides for Kimi K3.1 Pro, K3, K2.7 Code and K2.6; its price tables did not come through as text | none found | 262,144 for every K2 series model (the page does not name this one) |
| `qwen/qwen3-235b-a22b-2507` | https://www.alibabacloud.com/help/en/model-studio/models | not named in the text the page served to a plain HTTP fetch, which held no model table | none found | not on that page |
| `qwen/qwen3-235b-a22b-thinking-2507` | https://www.alibabacloud.com/help/en/model-studio/models | not named in the text the page served to a plain HTTP fetch, which held no model table | none found | not on that page |

### Recorded costs

Each line is one pool model on the kept items: the sum of its recorded costs, the same token counts at its list price and the ratio of the two when a page above gives one, and the least-squares input and output price over its items, rounded to 4 decimals: `exact pair` when that rounded pair reproduces every recorded cost within 1e-09 USD; `no pair within 1e-09 USD` when even the unrounded pair is off by more than the square root of the item count times 1e-09 USD, a bound that any pair within 1e-09 USD of every cost would keep it under; and `no 4-decimal pair` when only the rounding fails it, which no model here does.

```text
$ python research/llmrouterbench_prices.py --matrix llmrouterbench-matrix.jsonl
12066 items over 9 tasks and 13 models; largest input_tokens 16563
null token count: 10 items (hle 5, simpleqa 5), 130 rows; kept 12056 items, 156728 rows
per model on the kept items: recorded cost, cost at the list price, their ratio, and one price pair for every recorded cost (USD per 1M tokens, exact within 1e-09 USD)
  anthropic/claude-sonnet-4: recorded 102.219153; list 3 in, 15 out: 102.219153, ratio 1.000; exact pair 3 in, 15 out
  deepseek/deepseek-r1-0528: recorded 164.659235; list none; exact pair 0.5 in, 2.15 out
  deepseek/deepseek-v3-0324: recorded 8.217254; list none; exact pair 0.25 in, 0.88 out
  deepseek/deepseek-v3.1-terminus: recorded 10.928473; list none; exact pair 0.27 in, 1 out
  google/gemini-2.5-flash: recorded 102.374935; list none; no pair within 1e-09 USD (least squares 0.198 in, 2.4803 out to 4 decimals; unrounded off by up to 0.049652 USD)
  google/gemini-2.5-pro: recorded 732.489198; list none; no pair within 1e-09 USD (least squares 1.16 in, 10.0021 out to 4 decimals; unrounded off by up to 0.010600 USD)
  internlm/intern-s1: recorded 34.803192; list none; exact pair 0.18 in, 0.54 out
  moonshotai/kimi-k2-0905: recorded 15.761589; list none; no pair within 1e-09 USD (least squares 0.4989 in, 2.0029 out to 4 decimals; unrounded off by up to 0.004661 USD)
  openai/gpt-5: recorded 382.877608; list 1.25 in, 10 out: 422.603241, ratio 0.906; no pair within 1e-09 USD (least squares 4.2373 in, 8.6936 out to 4 decimals; unrounded off by up to 0.297965 USD)
  openai/gpt-5-chat: recorded 52.919864; list 1.25 in, 10 out: 54.726774, ratio 0.967; no pair within 1e-09 USD (least squares 1.4882 in, 9.0396 out to 4 decimals; unrounded off by up to 0.071824 USD)
  qwen/qwen3-235b-a22b-2507: recorded 9.767046; list none; no pair within 1e-09 USD (least squares 0.0375 in, 0.6464 out to 4 decimals; unrounded off by up to 0.036806 USD)
  qwen/qwen3-235b-a22b-thinking-2507: recorded 84.637969; list none; no pair within 1e-09 USD (least squares 1.6766 in, 1.7042 out to 4 decimals; unrounded off by up to 0.026696 USD)
  z-ai/glm-4.6: recorded 201.726410; list 0.6 in, 2.2 out: 202.505216, ratio 0.996; no pair within 1e-09 USD (least squares 0.5535 in, 2.2004 out to 4 decimals; unrounded off by up to 0.004045 USD)
summary: list price 4 of 13, exact pair 5 of 13, either 8 of 13
```

```bash
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python research/llmrouterbench_prices.py --matrix llmrouterbench-matrix.jsonl
```

The converter downloads the pinned 1.28 GB file once into `~/.cache/ai-model-routing-evidence/llmrouterbench/` (`DESIGN.md` 12.18).

### Recommendation

- Not a 13-model delegation run. 13.9 needs every model of the rows in the registry, and with a registry rule of a vendor page price, else the exact pair the recorded costs give (as `DESIGN.md` 13.12 prices `anthropic/claude-3-7-sonnet-20250219` from its recorded costs), 8 models are priced: the 4 with a page price, the three DeepSeek models and `internlm/intern-s1`. The two Gemini 2.5 models, `moonshotai/kimi-k2-0905` and the two Qwen3 models have neither, and a least-squares pair that misses some item's recorded cost would be an assumed price, given neither by the data nor by a page
- Take it as a later version on that 8-model pool, specified in `DESIGN.md` first: a third delegation dataset, of single-call items as the AutoBench matrix holds, over the benchmarks that hold every model of the pool (9 kinds of job with the whole pool). That version has to state four things. The pool: `convert` takes a `pool` (12.18) but the CLI does not, and a smaller pool can change which benchmarks hold every pool model, so it names its benchmarks. The 10 dropped items. The list prices, which put `openai/gpt-5` about a tenth above its recorded cost (0.906). And a context window per model, which the pages above give for only 2 of the 8 (13.4 reads the parent's window)
- What it cannot show: how delegation would fare with `google/gemini-2.5-pro`, the best single model of the LLMRouterBench routing results, which this pool leaves out; and every one of the 8 models dates from 2025
