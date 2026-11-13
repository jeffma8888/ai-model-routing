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

### Context windows (2026-11-10)

`DESIGN.md` 13.4 rule 3 blocks inline when the parent's `context_window` is under C + K * (S_in + S_out), and 5.2 rule 5 checks the delegate's last call against its own window, so a delegation registry needs a window for each of the 8 priced models. The table above gives one for 2 of them. Pages opened 2026-11-10 unless a row says otherwise.

- A vendor page gives a window for 4 of the 8: `anthropic/claude-sonnet-4` and `z-ai/glm-4.6` (200K, read here as 200,000), `openai/gpt-5` (400,000) and `openai/gpt-5-chat` (128,000). The Claude page does not name Claude Sonnet 4: its window is inferred from the page's sentence on every Claude model outside its 1M-token list
- For the three DeepSeek models and `internlm/intern-s1` no page fetched states a window. The one number is the open weights' position limit, `max_position_embeddings` in each model's config.json at its Hugging Face revision: 163,840 for the three DeepSeek models (`rope_scaling` type `yarn`, factor 40 over `original_max_position_embeddings` 4,096) and 65,536 for `internlm/intern-s1` (in its `text_config`, `rope_scaling` null). That is how far the weights attend, not the window of the service that recorded the costs, which the dataset does not name
- At C = 200,000 (13.10 point 2) each window but `openai/gpt-5`'s 400,000 is at most 200,000 with 200K read as 200,000, so rule 3 blocks inline for the other 7 parents on any work; read as 204,800, the two 200K windows leave 4,800 tokens for the work. At C = 64,000 (point 1) the room the window leaves past C, for the K * (S_in + S_out) of the work, is 1,536 tokens for `internlm/intern-s1`, 64,000 for `openai/gpt-5-chat` and 99,840 for the DeepSeek models; at C = 8,000 (points 0 and 3) the smallest is `internlm/intern-s1`'s 57,536

| Model | Page (opened) | What it states | Window (tokens) | Kind |
|---|---|---|---|---|
| `anthropic/claude-sonnet-4` | https://platform.claude.com/docs/en/build-with-claude/context-windows (2026-11-10) | it lists the models with a 1M-token window, Claude Sonnet 4 not among them, then "Other Claude models, including Claude Sonnet 4.5 (deprecated), have a 200k-token context window"; https://platform.claude.com/docs/en/about-claude/model-deprecations (2026-11-10) gives `claude-sonnet-4-20250514` the retirement date June 15, 2026; so the window is inferred, as the page does not name Claude Sonnet 4 | 200,000 | vendor page |
| `deepseek/deepseek-r1-0528` | https://huggingface.co/deepseek-ai/DeepSeek-R1-0528/raw/4236a6af538feda4548eca9ab308586007567f52/config.json (2026-11-10; a revision of 2025-05-29) | `max_position_embeddings` 163840, `rope_scaling` type `yarn`, factor 40, `original_max_position_embeddings` 4096; its release page https://api-docs.deepseek.com/news/news250528 names no window, and its model card says "the maximum generation length is set to 64K tokens" for the card's benchmark runs | 163,840 | weights' position limit |
| `deepseek/deepseek-v3-0324` | https://huggingface.co/deepseek-ai/DeepSeek-V3-0324/raw/e9b33add76883f293d6bf61f6bd89b497e80e335/config.json (2026-11-10; a revision of 2025-03-27) | `max_position_embeddings` 163840, with the `rope_scaling` of `deepseek/deepseek-r1-0528`; its release page https://api-docs.deepseek.com/news/news250325 served only its title and a site banner to a plain HTTP fetch | 163,840 | weights' position limit |
| `deepseek/deepseek-v3.1-terminus` | https://huggingface.co/deepseek-ai/DeepSeek-V3.1-Terminus/raw/19510d6dc61f79dbd925bd51ee8a9081c509a4b6/config.json (2026-11-10; a revision of 2025-09-29) | `max_position_embeddings` 163840, with the `rope_scaling` of `deepseek/deepseek-r1-0528`; its release page https://api-docs.deepseek.com/news/news250922 names no window | 163,840 | weights' position limit |
| `internlm/intern-s1` | https://huggingface.co/internlm/Intern-S1/raw/4ecad381e28293c4825793f113327cc016cdcbda/config.json (2026-11-10; a revision of 2026-03-29) | `text_config.max_position_embeddings` 65536, `rope_scaling` null; its model card https://huggingface.co/internlm/Intern-S1 names no window | 65,536 | weights' position limit |
| `openai/gpt-5` | https://platform.openai.com/docs/models/gpt-5 (2026-11-09) | a 400,000 context window, as in the List prices table | 400,000 | vendor page |
| `openai/gpt-5-chat` | https://platform.openai.com/docs/models/gpt-5-chat-latest (2026-11-09) | a 128,000 context window, as in the List prices table | 128,000 | vendor page |
| `z-ai/glm-4.6` | https://docs.z.ai/guides/llm/glm-4.6 (2026-11-10) | "The context window has been expanded from 128K to 200K tokens" | 200,000 | vendor page |

Recommendation for the registry of a later version (`DESIGN.md` 13.13, row E17b):

- Keep all 8 models, each window with its kind in `notes`, as 13.12 keeps an assumed window for `anthropic/claude-3-7-sonnet-20250219` and says so: for the four open-weight models `notes` says the window is the weights' position limit, not a served window, and for `anthropic/claude-sonnet-4` that it is inferred from the sentence on every other Claude model. Dropping them would leave 4 models, two of them OpenAI's, and the window enters only the rule 3 and 5.2 rule 5 checks, whose `parent_context_full` cells RESULTS.md can count per parent
- Read 200K as 200,000 for the two pages that write it and say so in `notes`, since at point 2 the other reading leaves 4,800 tokens of room

## LLM Routing Response Bank (2026-11-12)

Question: can the LLM Routing Response Bank (`DESIGN.md` 12.20, Lurume/llm-routing-response-bank at 547beb31ecd8f12b116b87eb4f56feee73edda6c, ODC-BY-4.0 terms with attribution), whose items are single calls with a success, a billed `official_usd` and the `usage` token counts, be a fourth delegation dataset beside AutoBench 2026, LLMRouterBench and tau2-bench? The 13.9 harness prices both paths at list price from a registry and needs a complete matrix, so the question is whether one price pair per model reproduces the bills, whether a vendor page states it, how large the work is per family, and whether the cheaper path, inline or delegated, changes with the family at the 13.10 `points()`. Prices are from the vendor pages below, opened 2026-11-12; every other number is a line of the command below, run on the four pinned files.

- Yes, as a later version with its own registry rule: one input and output price pair per model, with a third price for cache reads, reproduces every bill within 1e-09 USD, vendor pages state those same prices for three of the five models, and at the 13.10 points the cheaper path changes with the family for many (parent, delegate) pairs
- The pair each model's bills give on its responses with `usage.cache_read` 0 misses every response with a cache read and no other: 1572 of its 13315 responses for `deepseek/deepseek-v4-flash` (0.14 and 0.28 USD per 1M input and output tokens), 6527 of 13315 for `deepseek/deepseek-v4-pro` (0.435 and 0.87), 5872 of 13315 for `moonshotai/kimi-k2.7-code` (0.95 and 4), 5906 of 13312 for `z-ai/glm-5.3` (1.4 and 4.4) and 5602 of 13312 for `z-ai/glm-5.3-flash` (0.15 and 0.5), by at most 0.000005734 to 0.000615680 USD. No pair is within 1e-09 USD of every bill: the least-squares pair over all of a model's responses is off by 0.000005725 to 0.000606944 USD at its worst one, where a pair within 1e-09 USD of each would leave it under 1.2e-07. With a cache-read price as a third price (0.0028, 0.003625, 0.19, 0.26 and 0.03, in the same order) every bill is reproduced within 1e-09 USD
- `usage.input` counts only the prompt tokens not read from the cache: `total_tokens` is `input + output + cache_read` on all 66569 responses. So the converter's `input_tokens` (12.20) is the uncached part of the prompt, and a list-price harness that charges the whole prompt at the input price would put the cached responses above their bills, while one that charges `usage.input` alone would put them below their bills by the cache-read charge
- The vendor pages state the recorded three prices for `z-ai/glm-5.3`, `z-ai/glm-5.3-flash` and `moonshotai/kimi-k2.7-code`. DeepSeek's page states other prices today: `deepseek-v4-pro` at 0.66 and 1.98 off-peak and 1.32 and 3.96 at peak (cache hit 0.022 and 0.044), and the legacy name `deepseek-v4-flash` is still accepted but retired, its requests served by DeepSeek-V4.1-Flash-1017 at the `deepseek-flash` price (0.15 and 0.6 off-peak, 0.3 and 1.2 at peak). The Kimi page says the K2 series, `kimi-k2.7-code` among it, closes to new users from October 31, 2026 and retires by the end of December 2026
- The families differ in size mostly in output: over all five models the median output is 4999.5 tokens on `aime`, 2414 on `gpqa_diamond`, 1808 on `livecodebench` and 302 on `mmlu_pro` (90th percentiles 31480, 40574, 131182 and 2771), while the median input is 183 to 980 (90th percentiles 346 to 1366), and all but one of the 25479 responses with a cache read are on `mmlu_pro` (25478 of its 60154, a 90th percentile of 1536 cache-read tokens), the other on `livecodebench`
- At the 13.10 points, with each model at its own `median_low` sizes per family and priced at the pair above, the cheaper path differs between families for 10 of the 25 (parent, delegate) pairs at point 0 (C 8000, inline work a call of its own), 3 at point 1 (C 64000), 1 at point 2 (C 200000) and 16 at point 3 (C 8000, inline work folded into the parent's call). Every model is the parent of such a pair at point 0. Read with the whole prompt, `input + cache_read`, as the work's input, the counts are the same at points 0 to 2 and 14 at point 3
- The matrix is complete on 13311 of the 13315 items: four `mmlu_pro` items lack one or two models' responses, the six `missing` cells of 12.20

### List prices

| Model | Page (opened 2026-11-12) | Status on that page | Input, cached input, output (USD per 1M tokens) | Context window on that page |
|---|---|---|---|---|
| `deepseek/deepseek-v4-flash` | https://api-docs.deepseek.com/quick_start/pricing | the legacy name `deepseek-v4-flash` is accepted, but its model is retired and its requests are served by DeepSeek-V4.1-Flash-1017 and billed at the `deepseek-flash` price | none for this model; `deepseek-flash` 0.15, 0.003, 0.6 off-peak and 0.3, 0.006, 1.2 at peak | 1M for `deepseek-flash` |
| `deepseek/deepseek-v4-pro` | https://api-docs.deepseek.com/quick_start/pricing | listed, model version DeepSeek-V4-Pro-0813 | 0.66, 0.022, 1.98 off-peak and 1.32, 0.044, 3.96 at peak, neither the recorded 0.435, 0.003625, 0.87 | 1M |
| `moonshotai/kimi-k2.7-code` | https://platform.moonshot.ai/docs/pricing/chat | listed in the K2 series table of the page's HTML (its text view shows no table); the page's note closes the K2 series to new users from October 31, 2026 and plans to retire it by the end of December 2026 | 0.95, 0.19, 4 | 262,144 for every K2 series model |
| `z-ai/glm-5.3` | https://docs.z.ai/guides/overview/pricing | listed among the latest models | 1.4, 0.26, 4.4 | not on that page |
| `z-ai/glm-5.3-flash` | https://docs.z.ai/guides/overview/pricing | listed among the latest models as GLM-5.3-Flash | 0.15, 0.03, 0.5 | not on that page |

### Recorded costs

Each model line gives its responses and billed total; the input and output pair fit, by least squares rounded to 4 decimals, on its responses with `cache_read` 0; how many responses that pair misses by more than 1e-09 USD, how many of those have a `cache_read` above 0, and the largest miss; how far the unrounded least-squares pair over all its responses is off at its worst one, beside the square root of the response count times 1e-09 USD that a pair within 1e-09 USD of every bill would keep it under; and the misses left when each cache-read token is priced at the median, over the cached responses, of the bill left after the pair divided by `cache_read`, rounded to 6 decimals. The family lines pool all five models; the last part names each pair whose cheaper path differs between families, as `parent>delegate` and the families where inline costs less, with the 13.9 inline and delegated cost expressions at K = 1.

```text
$ python - < response-bank-delegation.py
66569 responses, sample_index [0] | total_tokens == input + output + cache_read on 66569
per model: one price pair for every billed official_usd (USD per 1M tokens, exact within 1e-09 USD)
  deepseek/deepseek-v4-flash: 13315 responses, billed 46.883518; pair 0.14 in, 0.28 out fit on the 11743 with cache_read 0; misses 1572, 1572 of them cache_read > 0, largest 0.000005734; least squares on all off by up to 0.000005725 (bound 1.2e-07); with 0.0028 per cache_read token misses 0
  deepseek/deepseek-v4-pro: 13315 responses, billed 54.603459; pair 0.435 in, 0.87 out fit on the 6788 with cache_read 0; misses 6527, 6527 of them cache_read > 0, largest 0.000008352; least squares on all off by up to 0.000008026 (bound 1.2e-07); with 0.003625 per cache_read token misses 0
  moonshotai/kimi-k2.7-code: 13315 responses, billed 141.864469; pair 0.95 in, 4 out fit on the 7443 with cache_read 0; misses 5872, 5872 of them cache_read > 0, largest 0.000437760; least squares on all off by up to 0.000426408 (bound 1.2e-07); with 0.19 per cache_read token misses 0
  z-ai/glm-5.3: 13312 responses, billed 138.970994; pair 1.4 in, 4.4 out fit on the 7406 with cache_read 0; misses 5906, 5906 of them cache_read > 0, largest 0.000615680; least squares on all off by up to 0.000606944 (bound 1.2e-07); with 0.26 per cache_read token misses 0
  z-ai/glm-5.3-flash: 13312 responses, billed 12.534056; pair 0.15 in, 0.5 out fit on the 7710 with cache_read 0; misses 5602, 5602 of them cache_read > 0, largest 0.000055680; least squares on all off by up to 0.000055359 (bound 1.2e-07); with 0.03 per cache_read token misses 0
items held by all five models: 13311 of 13315 | short: [('mmlu_pro', 'mmlu_pro:10969', 3), ('mmlu_pro', 'mmlu_pro:10990', 4), ('mmlu_pro', 'mmlu_pro:11007', 3), ('mmlu_pro', 'mmlu_pro:7872', 4)]
per family over all five models: median and 90th percentile (nearest rank) tokens
  aime: 150 responses, 0 with cache_read > 0; input 183, 346; cache 0, 0; output 4999.5, 31480
  gpqa_diamond: 990 responses, 0 with cache_read > 0; input 238, 395; cache 0, 0; output 2414, 40574
  livecodebench: 5275 responses, 1 with cache_read > 0; input 492, 779; cache 0, 0; output 1808, 131182
  mmlu_pro: 60154 responses, 25478 with cache_read > 0; input 980, 1366; cache 0, 1536; output 302, 2771
cheaper path at each 13.10 point, every (parent, delegate) pair, each model at its median_low sizes per family, priced at the pair above
  input, point 0 (C 8000, separate call True): 10 of 25 pairs differ
    deepseek-v4-flash>deepseek-v4-pro inline on aime,gpqa_diamond
    deepseek-v4-flash>kimi-k2.7-code inline on aime,gpqa_diamond,mmlu_pro
    deepseek-v4-flash>glm-5.3 inline on aime,gpqa_diamond,mmlu_pro
    deepseek-v4-pro>deepseek-v4-flash inline on livecodebench
    deepseek-v4-pro>kimi-k2.7-code inline on aime,gpqa_diamond
    kimi-k2.7-code>deepseek-v4-flash inline on livecodebench
    glm-5.3>deepseek-v4-flash inline on livecodebench
    glm-5.3>kimi-k2.7-code inline on aime,gpqa_diamond,livecodebench
    glm-5.3-flash>deepseek-v4-flash inline on aime,livecodebench
    glm-5.3-flash>deepseek-v4-pro inline on aime,gpqa_diamond,livecodebench
  input, point 1 (C 64000, separate call True): 3 of 25 pairs differ
    deepseek-v4-flash>kimi-k2.7-code inline on aime,gpqa_diamond
    glm-5.3-flash>deepseek-v4-flash inline on livecodebench
    glm-5.3-flash>kimi-k2.7-code inline on aime,gpqa_diamond,livecodebench
  input, point 2 (C 200000, separate call True): 1 of 25 pairs differ
    glm-5.3-flash>deepseek-v4-flash inline on livecodebench
  input, point 3 (C 8000, separate call False): 16 of 25 pairs differ
    deepseek-v4-flash>deepseek-v4-flash inline on gpqa_diamond,mmlu_pro
    deepseek-v4-flash>deepseek-v4-pro inline on aime,gpqa_diamond,mmlu_pro
    deepseek-v4-flash>kimi-k2.7-code inline on aime,gpqa_diamond,mmlu_pro
    deepseek-v4-flash>glm-5.3 inline on aime,gpqa_diamond,mmlu_pro
    deepseek-v4-flash>glm-5.3-flash inline on gpqa_diamond,mmlu_pro
    deepseek-v4-pro>deepseek-v4-flash inline on livecodebench,mmlu_pro
    deepseek-v4-pro>deepseek-v4-pro inline on mmlu_pro
    deepseek-v4-pro>glm-5.3 inline on mmlu_pro
    deepseek-v4-pro>glm-5.3-flash inline on mmlu_pro
    kimi-k2.7-code>deepseek-v4-flash inline on livecodebench,mmlu_pro
    kimi-k2.7-code>deepseek-v4-pro inline on mmlu_pro
    kimi-k2.7-code>kimi-k2.7-code inline on gpqa_diamond,livecodebench,mmlu_pro
    kimi-k2.7-code>glm-5.3 inline on mmlu_pro
    kimi-k2.7-code>glm-5.3-flash inline on mmlu_pro
    glm-5.3>deepseek-v4-flash inline on gpqa_diamond,livecodebench,mmlu_pro
    glm-5.3>glm-5.3-flash inline on gpqa_diamond,livecodebench,mmlu_pro
  input + cache_read, point 0 (C 8000, separate call True): 10 of 25 pairs differ
    deepseek-v4-flash>deepseek-v4-pro inline on aime,gpqa_diamond
    deepseek-v4-flash>kimi-k2.7-code inline on aime,gpqa_diamond,mmlu_pro
    deepseek-v4-flash>glm-5.3 inline on aime,gpqa_diamond,mmlu_pro
    deepseek-v4-pro>deepseek-v4-flash inline on livecodebench
    deepseek-v4-pro>kimi-k2.7-code inline on aime,gpqa_diamond
    kimi-k2.7-code>deepseek-v4-flash inline on livecodebench
    glm-5.3>deepseek-v4-flash inline on livecodebench
    glm-5.3>kimi-k2.7-code inline on aime,gpqa_diamond,livecodebench
    glm-5.3-flash>deepseek-v4-flash inline on aime,livecodebench
    glm-5.3-flash>deepseek-v4-pro inline on aime,gpqa_diamond,livecodebench
  input + cache_read, point 1 (C 64000, separate call True): 3 of 25 pairs differ
    deepseek-v4-flash>kimi-k2.7-code inline on aime,gpqa_diamond
    glm-5.3-flash>deepseek-v4-flash inline on livecodebench
    glm-5.3-flash>kimi-k2.7-code inline on aime,gpqa_diamond,livecodebench
  input + cache_read, point 2 (C 200000, separate call True): 1 of 25 pairs differ
    glm-5.3-flash>deepseek-v4-flash inline on livecodebench
  input + cache_read, point 3 (C 8000, separate call False): 14 of 25 pairs differ
    deepseek-v4-flash>deepseek-v4-flash inline on gpqa_diamond,mmlu_pro
    deepseek-v4-flash>deepseek-v4-pro inline on aime,gpqa_diamond,mmlu_pro
    deepseek-v4-flash>kimi-k2.7-code inline on aime,gpqa_diamond,mmlu_pro
    deepseek-v4-flash>glm-5.3 inline on aime,gpqa_diamond,mmlu_pro
    deepseek-v4-flash>glm-5.3-flash inline on gpqa_diamond,mmlu_pro
    deepseek-v4-pro>deepseek-v4-flash inline on livecodebench
    deepseek-v4-pro>deepseek-v4-pro inline on mmlu_pro
    deepseek-v4-pro>glm-5.3 inline on mmlu_pro
    kimi-k2.7-code>deepseek-v4-flash inline on livecodebench
    kimi-k2.7-code>deepseek-v4-pro inline on mmlu_pro
    kimi-k2.7-code>kimi-k2.7-code inline on gpqa_diamond,livecodebench,mmlu_pro
    kimi-k2.7-code>glm-5.3 inline on mmlu_pro
    glm-5.3>deepseek-v4-flash inline on gpqa_diamond,livecodebench,mmlu_pro
    glm-5.3>glm-5.3-flash inline on gpqa_diamond,livecodebench,mmlu_pro
```

The command is the block below, saved as `response-bank-delegation.py` and run from the repository root with Python 3.10 or later: the standard library, `evidence/response-bank/convert.py`, whose `fetch` downloads the four pinned files (about 1 GB) once into `~/.cache/ai-model-routing-evidence/response-bank/` and checks each size and sha256, and `evidence/delegation/results.py` for `points()`, which imports `model_routing` from the checkout. Nothing from the files is committed.

```python
import importlib.util, json, math, statistics as st
from collections import defaultdict

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

cv = load("convert", "evidence/response-bank/convert.py")
points = load("results", "evidence/delegation/results.py").points()
paths = cv.fetch()  # downloads once into the cache and checks each file's size and sha256
rows = []
for name in ("responses_cal.jsonl", "responses_eval.jsonl"):
    with open(paths[name], "rb") as f:
        for raw in f:
            if raw.strip():
                obj = json.loads(raw)
                r = cv.response_record(obj)
                r["cache"] = obj["usage"]["cache_read"]
                r["total"] = obj["usage"]["total_tokens"]
                rows.append(r)
by_model, by_family = defaultdict(list), defaultdict(list)
for r in rows:
    by_model[r["model"]].append(r); by_family[r["family"]].append(r)
print(len(rows), "responses, sample_index", sorted({r["sample_index"] for r in rows}),
      "| total_tokens == input + output + cache_read on", sum(r["total"] == r["input_tokens"] + r["output_tokens"] + r["cache"] for r in rows))

def pair(rs):  # least squares (USD per 1M tokens) of cost on input and output, no intercept
    a = math.fsum(r["input_tokens"] ** 2 for r in rs); b = math.fsum(r["input_tokens"] * r["output_tokens"] for r in rs)
    c = math.fsum(r["output_tokens"] ** 2 for r in rs); d = math.fsum(r["input_tokens"] * r["cost_usd"] for r in rs)
    e = math.fsum(r["output_tokens"] * r["cost_usd"] for r in rs)
    return (d * c - b * e) / (a * c - b * b) * 1e6, (a * e - b * d) / (a * c - b * b) * 1e6

def cost(r, p_in, p_out, p_cache=0.0):
    return (r["input_tokens"] * p_in + r["output_tokens"] * p_out + r["cache"] * p_cache) / 1e6

prices = {}
print("per model: one price pair for every billed official_usd (USD per 1M tokens, exact within 1e-09 USD)")
for m, rs in sorted(by_model.items()):
    fresh = [r for r in rs if r["cache"] == 0]
    p = tuple(round(x, 4) for x in pair(fresh))
    off = [abs(cost(r, *p) - r["cost_usd"]) for r in rs]
    miss = [r for r, x in zip(rs, off) if x > 1e-9]
    ls = pair(rs)
    worst = max(abs(cost(r, *ls) - r["cost_usd"]) for r in rs)
    hit = [r for r in rs if r["cache"] > 0]
    q = round(st.median((r["cost_usd"] - cost(r, *p)) / r["cache"] * 1e6 for r in hit), 6)
    three = sum(abs(cost(r, *p, q) - r["cost_usd"]) > 1e-9 for r in rs)
    prices[m] = p
    print(f"  {m}: {len(rs)} responses, billed {math.fsum(r['cost_usd'] for r in rs):.6f}; pair {p[0]:g} in, {p[1]:g} out fit on the "
          f"{len(fresh)} with cache_read 0; misses {len(miss)}, {sum(r['cache'] > 0 for r in miss)} of them cache_read > 0, largest {max(off):.9f}; "
          f"least squares on all off by up to {worst:.9f} (bound {math.sqrt(len(rs)) * 1e-9:.1e}); with {q:g} per cache_read token misses {three}")
def nearest(xs, q):
    xs = sorted(xs); return xs[math.ceil(q * len(xs)) - 1]
held = defaultdict(set)
for r in rows:
    held[r["family"], r["task_id"]].add(r["model"])
print("items held by all five models:", sum(len(v) == 5 for v in held.values()), "of", len(held),
      "| short:", sorted((f, t, len(v)) for (f, t), v in held.items() if len(v) < 5))
print("per family over all five models: median and 90th percentile (nearest rank) tokens")
for fam, rs in sorted(by_family.items()):
    cells = []
    for key in ("input_tokens", "cache", "output_tokens"):
        xs = [r[key] for r in rs]; cells.append(f"{key.replace('_tokens', '')} {st.median(xs):g}, {nearest(xs, 0.9)}")
    print(f"  {fam}: {len(rs)} responses, {sum(r['cache'] > 0 for r in rs)} with cache_read > 0; " + "; ".join(cells))
print("cheaper path at each 13.10 point, every (parent, delegate) pair, each model at its median_low sizes per family, priced at the pair above")
for prompt in ("input", "input + cache_read"):
    size = {}
    for (m, fam) in {(r["model"], r["family"]) for r in rows}:
        rs = [r for r in by_model[m] if r["family"] == fam]
        size[m, fam] = (st.median_low([r["input_tokens"] + (r["cache"] if prompt != "input" else 0) for r in rs]),
                        st.median_low([r["output_tokens"] for r in rs]))
    for k, pt in enumerate(points):
        C, B, R, T, sep = (pt[x] for x in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns", "inline_separate_call"))
        split = []
        c = lambda m, i, o: (i * prices[m][0] + o * prices[m][1]) / 1e6
        for P in sorted(by_model):
            for D in sorted(by_model):
                path = {}
                for fam in sorted(by_family):
                    (pi, po), (di, do) = size[P, fam], size[D, fam]
                    inline = c(P, C + pi, po) + (1 + T) * c(P, pi + po, 0) if sep else c(P, pi, po) + T * c(P, pi + po, 0)
                    deleg = c(P, 0, B) + c(D, B + di, do) + (1 + T) * c(P, B + R, 0)
                    path[fam] = "inline" if inline < deleg else "delegate" if deleg < inline else "tie"
                if len(set(path.values())) > 1:
                    split.append(f"{P.split('/')[1]}>{D.split('/')[1]} inline on " + ",".join(f for f, v in path.items() if v == "inline"))
        print(f"  {prompt}, point {k} (C {C}, separate call {sep}): {len(split)} of 25 pairs differ" + ("".join(f"\n    {s}" for s in split)))
```

### Recommendation

- Take it as a fourth delegation dataset, in a later version specified in `DESIGN.md` first as a 13.x results section, as 13.13 took LLMRouterBench: its items are single calls, every model's bills reproduce within 1e-09 USD from three prices, and at the 13.10 points the cheaper path depends on the family for many pairs, which a per-task decision can act on
- Registry rule for that version: every model at the input and output pair its bills give on the responses with `cache_read` 0, the vendor page price for three of the five, with `notes` saying for the two DeepSeek models that the page now states other prices and, for `deepseek/deepseek-v4-flash`, that the name is served by another model; a vendor page price that differs from the recorded bill would price the work at a price it was not billed at
- That version states four things. The input size: `usage.input` as the converter writes it, the uncached part, or `input + cache_read`, the whole prompt; the family split holds either way, while only the whole prompt makes the list cost of a cached response its size at the input price, above its bill, and `usage.input` alone puts that cost below the bill by the cache-read charge. The four `mmlu_pro` items that lack a model, which a complete matrix drops. A context window per model for 13.4 rule 3 and the 5.2 rule 5 check: the DeepSeek page gives 1M for its current models and the Kimi page 262,144 for the K2 series, while the Z.ai pricing page gives none, so the windows are read first, as the 2026-11-10 subsection did for LLMRouterBench. And the dates: `deepseek-v4-flash` is retired and the K2 series retires by the end of December 2026, so the results describe models a reader may no longer be able to call
- What it cannot show, as on the other three datasets: a real hand-off with a brief and a result, which the 13.9 grid assumes; the split above is the stated grid's prices at each family's median sizes, not a held-out result

### Context windows (2026-11-12)

`DESIGN.md` 13.4 rule 3 blocks inline when the parent's `context_window` is under C + K * (S_in + S_out), and 5.2 rule 5 checks the delegate's last call, S_in + B + S_out, against its own window, so the registry of the later version the Recommendation above names (row E21) needs a window for each of the five models. The List prices table gives one for three of them. Pages opened 2026-11-12 (Pacific time); every number in the bullets and the table that is not on a page is a line of the command after the table, run on the four pinned files.

- A vendor page gives a window for all five: 1M for `deepseek/deepseek-v4-pro` and for `deepseek-flash`, the model that now serves the retired `deepseek-v4-flash` name (the DeepSeek pricing page), 1M for `z-ai/glm-5.3` and `z-ai/glm-5.3-flash` (their Z.ai model pages), and 262,144 for `moonshotai/kimi-k2.7-code` (the Kimi pricing page, for every K2 series model). Each 1M is read here as 1,000,000
- The open weights are consistent with the pages: `max_position_embeddings` in each model's config.json at its Hugging Face revision is 1048576, 1M read as 1,048,576, for the DeepSeek-V4-Flash and DeepSeek-V4-Pro weights (and for DeepSeek-V4.1-Flash-1017, the model now serving the `deepseek-v4-flash` name, and DeepSeek-V4-Pro-0813, the version the pricing page names; the release does not say which version recorded its calls) and for both GLM-5.3 weights, and 262144 for Kimi-K2.7-Code, its page's window. That is how far the weights attend, not the window of the service that recorded the bills
- No response is longer than its model's window: the largest whole call, `input + cache_read + output`, is 516654 tokens for `deepseek/deepseek-v4-flash` (on `mmlu_pro`), 222286 for `deepseek/deepseek-v4-pro` (`livecodebench`), 35520 for `moonshotai/kimi-k2.7-code` (`gpqa_diamond`), 130806 for `z-ai/glm-5.3` (`gpqa_diamond`) and 132871 for `z-ai/glm-5.3-flash` (`mmlu_pro`)
- The largest outputs sit at round values, each reached by many responses, that look like caps, though the pages do not state them all. The largest `z-ai/glm-5.3` output is 128000 tokens, on 107 responses, its page's "maximum output length of 128K tokens" read as 128,000. The largest `z-ai/glm-5.3-flash` output is 131072, on 70 responses, with 72 above 128000 and none above 131072, while its page states no maximum output, only that its text parameters are those of GLM-5.3. The largest `moonshotai/kimi-k2.7-code` output is 32768, on 165 responses, a limit no page fetched states. `deepseek/deepseek-v4-flash` wrote more than 384,000 tokens on 111 responses (up to 515083, on 12), above the 384K maximum output the DeepSeek page gives `deepseek-flash`, so that page's maximum output is not the limit the recorded calls ran under
- At the 13.10 points (K = 1) no window blocks inline or a delegate: with each family's `median_low` sizes over all five models (S_in the whole prompt, `input + cache_read`), the largest rule 3 need, C + S_in + S_out, is 13168 tokens at points 0 and 3, 69168 at point 1 and 205168 at point 2, and the largest rule 5 need, S_in + B + S_out, is 5668, against the smallest window, 262,144, which leaves 254144, 198144 and 62144 tokens past C. 13.9 reads the sizes on each calibration half, not on the whole set, but the smallest margin, 56976 tokens under `moonshotai/kimi-k2.7-code`'s window at point 2, is 11.0 times the largest whole-set S_in + S_out, 5168 on `aime`. So reading 1M as 1,048,576 instead would change no check at these points

| Model | Page (opened) | What it states | Window (tokens) | Kind |
|---|---|---|---|---|
| `deepseek/deepseek-v4-flash` | https://api-docs.deepseek.com/quick_start/pricing (2026-11-12); https://huggingface.co/deepseek-ai/DeepSeek-V4-Flash/raw/60d8d70770c6776ff598c94bb586a859a38244f1/config.json and https://huggingface.co/deepseek-ai/DeepSeek-V4.1-Flash-1017/raw/08c8657f02291e11b6f6b63e0e16014f8e748518/config.json (2026-11-12; revisions last modified 2026-06-22 and 2026-11-10) | context length 1M and maximum output 384K for `deepseek-flash`, model version DeepSeek-V4.1-Flash-1017, which serves the legacy name `deepseek-v4-flash`, whose own model is retired; the retired model's weights' `max_position_embeddings` 1048576, `rope_scaling` type `yarn`, factor 16, `original_max_position_embeddings` 65536, and the serving model's `text_config.max_position_embeddings` 1048576 with the same `rope_scaling` | 1,000,000 | vendor page, for the model that now serves the name |
| `deepseek/deepseek-v4-pro` | https://api-docs.deepseek.com/quick_start/pricing (2026-11-12); https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro/raw/b5968e9190ef611bbf34a7229255be88a0e937c1/config.json and https://huggingface.co/deepseek-ai/DeepSeek-V4-Pro-0813/raw/72e1d3230f6c080a530b0a1d46f8eb4602340597/config.json (2026-11-12; revisions last modified 2026-06-22 and 2026-08-13) | context length 1M and maximum output 384K for `deepseek-v4-pro`, model version DeepSeek-V4-Pro-0813; both weights' `max_position_embeddings` 1048576, with the `rope_scaling` of `deepseek/deepseek-v4-flash` | 1,000,000 | vendor page |
| `moonshotai/kimi-k2.7-code` | https://platform.moonshot.ai/docs/pricing/chat, which now redirects (HTTP 301) to https://platform.kimi.ai/docs/pricing/chat (2026-11-12); https://huggingface.co/moonshotai/Kimi-K2.7-Code/raw/74797c9c62378b951a1f6fcf5c4631024e9b8bef/config.json (2026-11-12; a revision last modified 2026-06-15) | "All K2 series models support a 262,144-token context window."; the weights' `text_config.max_position_embeddings` 262144, `rope_scaling` type `yarn`, factor 64, `original_max_position_embeddings` 4096 | 262,144 | vendor page |
| `z-ai/glm-5.3` | https://docs.z.ai/guides/llm/glm-5.3 (2026-11-12); https://huggingface.co/zai-org/GLM-5.3/raw/ba32f8c19c8738e2c57c71798c601d477a7bf844/config.json (2026-11-12; a revision last modified 2026-10-14) | "GLM-5.3 currently supports text-only inputs, with a 1M-token context window and a maximum output length of 128K tokens."; the weights' `max_position_embeddings` 1048576 | 1,000,000 | vendor page |
| `z-ai/glm-5.3-flash` | https://docs.z.ai/guides/llm/glm-5.3-flash (2026-11-12); https://huggingface.co/zai-org/GLM-5.3-Flash/raw/46a050bec13002ad29ee795c16e61cf4fa3c4a9c/config.json (2026-11-12; a revision last modified 2026-10-15) | "Text parameters are consistent with GLM-5.3, with support for a 1M-token context window."; the weights' `text_config.max_position_embeddings` 1048576 | 1,000,000 | vendor page |

```text
$ python - < response-bank-windows.py
66569 responses; windows (1M read as 1,000,000): deepseek-v4-flash 1000000, deepseek-v4-pro 1000000, kimi-k2.7-code 262144, glm-5.3 1000000, glm-5.3-flash 1000000
per model: the largest input + cache_read + output and the largest output of one response, each with its family
  deepseek/deepseek-v4-flash: 13315 responses; largest whole call 516654 (mmlu_pro); largest output 515083 (mmlu_pro) on 12; over its window 0; output over 128,000 688, 131,072 688, 384,000 111, 393,216 111
  deepseek/deepseek-v4-pro: 13315 responses; largest whole call 222286 (livecodebench); largest output 221145 (livecodebench) on 1; over its window 0; output over 128,000 8, 131,072 7, 384,000 0, 393,216 0
  moonshotai/kimi-k2.7-code: 13315 responses; largest whole call 35520 (gpqa_diamond); largest output 32768 (mmlu_pro) on 165; over its window 0; output over 128,000 0, 131,072 0, 384,000 0, 393,216 0
  z-ai/glm-5.3: 13312 responses; largest whole call 130806 (gpqa_diamond); largest output 128000 (mmlu_pro) on 107; over its window 0; output over 128,000 0, 131,072 0, 384,000 0, 393,216 0
  z-ai/glm-5.3-flash: 13312 responses; largest whole call 132871 (mmlu_pro); largest output 131072 (mmlu_pro) on 70; over its window 0; output over 128,000 72, 131,072 0, 384,000 0, 393,216 0
per family over all five models: median_low input, input + cache_read and output, the sizes 13.9 reads on the whole set (it reads them on each calibration half)
  aime: 150 responses; S_in 182, S_in with cache_read 182, S_out 4986
  gpqa_diamond: 990 responses; S_in 238, S_in with cache_read 238, S_out 2414
  livecodebench: 5275 responses; S_in 492, S_in with cache_read 492, S_out 1808
  mmlu_pro: 60154 responses; S_in 980, S_in with cache_read 1281, S_out 302
  largest S_in + S_out (S_in the whole prompt): 5168 (aime)
at each 13.10 point (K = 1): the room past C each window leaves, the largest 13.4 rule 3 need C + S_in + S_out and 5.2 rule 5 need S_in + B + S_out of any family (S_in the whole prompt), and the models whose window is under each
  point 0 (C 8000, B 500): room 262144 -> 254144, 1000000 -> 992000; rule 3 need 13168, under it 0, margin to the smallest window 248976 (48.2 times the largest S_in + S_out); rule 5 need 5668, under it 0
  point 1 (C 64000, B 500): room 262144 -> 198144, 1000000 -> 936000; rule 3 need 69168, under it 0, margin to the smallest window 192976 (37.3 times the largest S_in + S_out); rule 5 need 5668, under it 0
  point 2 (C 200000, B 500): room 262144 -> 62144, 1000000 -> 800000; rule 3 need 205168, under it 0, margin to the smallest window 56976 (11.0 times the largest S_in + S_out); rule 5 need 5668, under it 0
  point 3 (C 8000, B 500): room 262144 -> 254144, 1000000 -> 992000; rule 3 need 13168, under it 0, margin to the smallest window 248976 (48.2 times the largest S_in + S_out); rule 5 need 5668, under it 0
```

The command is the block below, saved as `response-bank-windows.py` and run from the repository root as the one in Recorded costs is, with the same files and imports; the windows in it are the table's. Nothing from the files is committed.

```python
import importlib.util, json, statistics as st
from collections import defaultdict

def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    mod = importlib.util.module_from_spec(spec); spec.loader.exec_module(mod)
    return mod

cv = load("convert", "evidence/response-bank/convert.py")
points = load("results", "evidence/delegation/results.py").points()
paths = cv.fetch()  # downloads once into the cache and checks each file's size and sha256
rows = []
for name in ("responses_cal.jsonl", "responses_eval.jsonl"):
    with open(paths[name], "rb") as f:
        for raw in f:
            if raw.strip():
                obj = json.loads(raw)
                r = cv.response_record(obj)
                r["cache"] = obj["usage"]["cache_read"]
                rows.append(r)
window = {"deepseek/deepseek-v4-flash": 1_000_000, "deepseek/deepseek-v4-pro": 1_000_000,
          "moonshotai/kimi-k2.7-code": 262_144, "z-ai/glm-5.3": 1_000_000, "z-ai/glm-5.3-flash": 1_000_000}
print(len(rows), "responses; windows (1M read as 1,000,000):", ", ".join(f"{m.split('/')[1]} {w}" for m, w in window.items()))
print("per model: the largest input + cache_read + output and the largest output of one response, each with its family")
for m in sorted(window):
    rs = [r for r in rows if r["model"] == m]
    big = max(rs, key=lambda r: (r["input_tokens"] + r["cache"] + r["output_tokens"], r["family"]))
    out = max(rs, key=lambda r: (r["output_tokens"], r["family"]))
    over = sum(r["input_tokens"] + r["cache"] + r["output_tokens"] > window[m] for r in rs)
    print(f"  {m}: {len(rs)} responses; largest whole call {big['input_tokens'] + big['cache'] + big['output_tokens']} ({big['family']}); "
          f"largest output {out['output_tokens']} ({out['family']}) on {sum(r['output_tokens'] == out['output_tokens'] for r in rs)}; over its window {over}; output over "
          + ", ".join(f"{x:,} {sum(r['output_tokens'] > x for r in rs)}" for x in (128_000, 131_072, 384_000, 393_216)))
print("per family over all five models: median_low input, input + cache_read and output, the sizes 13.9 reads on the whole set (it reads them on each calibration half)")
size = {}
for fam in sorted({r["family"] for r in rows}):
    rs = [r for r in rows if r["family"] == fam]
    size[fam] = (st.median_low([r["input_tokens"] for r in rs]), st.median_low([r["input_tokens"] + r["cache"] for r in rs]),
                 st.median_low([r["output_tokens"] for r in rs]))
    print(f"  {fam}: {len(rs)} responses; S_in {size[fam][0]}, S_in with cache_read {size[fam][1]}, S_out {size[fam][2]}")
work = max(sorted(size), key=lambda fam: size[fam][1] + size[fam][2])
print(f"  largest S_in + S_out (S_in the whole prompt): {size[work][1] + size[work][2]} ({work})")
print("at each 13.10 point (K = 1): the room past C each window leaves, the largest 13.4 rule 3 need C + S_in + S_out and 5.2 rule 5 need S_in + B + S_out"
      " of any family (S_in the whole prompt), and the models whose window is under each")
for k, pt in enumerate(points):
    C, B = pt["context_tokens"], pt["brief_tokens"]
    need = max(C + s[1] + s[2] for s in size.values())
    brief = max(s[1] + B + s[2] for s in size.values())
    print(f"  point {k} (C {C}, B {B}): room " + ", ".join(f"{w} -> {w - C}" for w in sorted(set(window.values())))
          + f"; rule 3 need {need}, under it {sum(w < need for w in window.values())}, margin to the smallest window {min(window.values()) - need}"
          + f" ({(min(window.values()) - need) / (size[work][1] + size[work][2]):.1f} times the largest S_in + S_out)"
          + f"; rule 5 need {brief}, under it {sum(w < brief for w in window.values())}")
```

Recommendation for the registry of the later version (row E21b):

- Give the four 1M models `context_window` 1,000,000, the pages' 1M read as decimal, with `notes` giving the weights' 1048576 and, for `deepseek/deepseek-v4-flash`, that the page's window is that of DeepSeek-V4.1-Flash-1017, the model now serving the name; give `moonshotai/kimi-k2.7-code` 262,144, where the page and the weights agree. Either reading of 1M leaves every rule 3 and rule 5 check above as it is, so the results do not depend on the choice
- The window enters only those two checks, so the results section can state its `parent_context_full` cells per parent, which the margins above put at 0 at every 13.10 point unless a calibration half's sizes move by tens of thousands of tokens
