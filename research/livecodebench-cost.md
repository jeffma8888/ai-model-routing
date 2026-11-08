# What a cost read from LiveCodeBench output length would see

Question: the LiveCodeBench evidence is `cost_blind` only, because the submissions record no cost, no token counts and no list price (`DESIGN.md` 12.16). Yet each pinned file holds every problem's text and every sample's output text, so a cost could be estimated from text length at list price. What would that estimate see, and what would it miss? Short answer: it sees the visible output only, and on the OpenAI reasoning runs the visible length stays the same at every reasoning setting while their reasoning tokens are billed and not shown, so the estimate would price those settings alike. Five vendors' current pages on reasoning are read in `## Vendor pages`. The four that speak of billing say reasoning is billed as output, and none of them describes returning the raw reasoning by default. But of the 67 models the five pages name only `o4-mini`, so they cannot say which of the older runs hid their reasoning. The pricing pages of those five vendors and of `mistralai`, `moonshotai` and `qwen`, read in `## Prices`, list by their own name only the two Claude 4 models, each with and without thinking, and `o3`; the pricing pages of the other five families and the reasoning pages of eight are not read yet, so this note makes no recommendation yet and the evidence stays `cost_blind`.

## Facts

- Over the 713 problems every one of the 67 files has, the median first-sample output runs from 312 characters (`deepseek/dscoder-1.3b-ins`) to 37,220 (`agentica/deepcoder-14b-preview`), 119.3 times; at 4 characters per token that is 78 to 9,305 output tokens
- 4 of the 67 models hold a `</think>` marker in at least half their first samples: `agentica/deepcoder-14b-preview`, `qwen/qwen3-235b-a22b`, `qwen/qwq-32b_temp` and `qwen/qwq-max-preview`
- The OpenAI runs at three reasoning settings have about the same visible length at each: `openai/o1-2024-12-17` from 1,091 characters (high) to 1,130 (low), 1.04 times; `openai/o3-mini-2025-01-31` 1.05 times; `openai/o4-mini` 1.18 times, with high the shortest, 955 against 1,127 at low
- The OpenAI help page on tokens says reasoning tokens "are not visible as answer text, but they count toward output usage and are billed as output tokens" (read 2026-11-08), so on those runs the visible length cannot show what each setting was billed for
- The two Anthropic models run with and without thinking go the other way: `anthropic/claude-opus-4-thinking` 8,635 characters against 1,598 (5.40 times) and `anthropic/claude-sonnet-4-thinking` 13,393 against 1,960 (6.83 times), so some of what thinking adds reaches the published output; whether it is the reasoning, a summary of it or a longer answer, length alone does not show
- The current pages on reasoning of openai, anthropic, google, xai and deepseek (read 2026-11-08, `## Vendor pages`) name only `o4-mini` of the 67; the four that speak of billing (openai, anthropic, google on its pricing page, xai) say reasoning is billed as output, and none of those four describes returning the raw reasoning by default
- The pricing pages of the same five vendors (read 2026-11-08, `## Prices`) list by their own name only `anthropic/claude-opus-4` and `anthropic/claude-sonnet-4`, each also run with thinking, and `openai/o3-high`; every other run of the five vendors is not listed, the dated OpenAI and Gemini runs because the page lists their names undated or as a later stable model
- The pricing pages of `mistralai`, `moonshotai` and `qwen` (read 2026-11-08, `## Prices`) list none of their 14 runs: the two Mistral runs are named by aliases, a name the vendor gives to whichever version is current, and the Kimi and Qwen pages list no model of the runs' names
- Recommendation: none yet. A text-length cost under-counts the runs whose reasoning is billed and unseen; which of the 67 those were, the vendors' current pages do not say, and the pricing pages of five vendor families and the reasoning pages of eight are not read yet

## Method

- Files: the 67 pinned files of the LiveCodeBench converter (`DESIGN.md` 12.16), downloaded into its cache and checked by size and sha256 before each is read, over the 713 question ids every file has, as in the committed results (12.17)
- Input: `question_content`, the problem text. The prompt each model was sent also held the harness's instructions, which the files do not record, so the problem text is less than the input
- Output: the first sample of `output_list`, the sample whose `graded_list[0]` label the evidence reads (12.16). An `output_list` that is the empty string, a record with no output text, counts as 0 characters; the script prints how many first samples are one
- Marker: `</think>` in the first sample, the tag with which open-weight reasoning models close their reasoning. Its absence does not show that a sample holds no reasoning, since a run may strip the tag or never write it
- Tokens: characters over 4, the rough estimate for English text on the OpenAI help page on tokens (https://help.openai.com/en/articles/4936856-what-are-tokens-and-how-to-count-them, read 2026-11-08: "1 token is approximately 4 characters"); the Gemini API page on tokens gives the same ratio (https://ai.google.dev/gemini-api/docs/tokens, read 2026-11-08: "a token is equivalent to about 4 characters"). Code is not English text and each vendor has its own tokenizer, so the ratio gives a size, not a count
- Settings: a folder name ending in a parenthesised `Thinking`, `High`, `Med`, `Medium` or `Low` is one run of the bare name at that setting; the bare folder, when there is one, is the run at `none`

## Results

```text
$ python research/livecodebench_cost.py
67 files, 713 question ids in every file
problem text: median 1,283 characters, from 449 to 3,950; files whose text differs from Claude-3-Haiku's on some id: 0
first samples recorded as an empty string, counted as 0 characters: 3 (in 1 file)
output tokens estimated at 4 characters per token

model                                          median_output_chars  think_marker  est_output_tokens
---------------------------------------------  -------------------  ------------  -----------------
agentica/deepcoder-14b-preview                              37,220         0.980              9,305
anthropic/claude-3-haiku                                       532         0.000                133
anthropic/claude-3.5-sonnet-20240620                           538         0.000                134
anthropic/claude-3.5-sonnet-20241022                           689         0.000                172
anthropic/claude-3.7-sonnet                                 24,472         0.000              6,118
anthropic/claude-opus-4                                      1,598         0.000                400
anthropic/claude-opus-4-thinking                             8,635         0.000              2,159
anthropic/claude-sonnet-4                                    1,960         0.000                490
anthropic/claude-sonnet-4-thinking                          13,393         0.000              3,348
deepseek/deepseek-r1-0528                                    3,439         0.000                860
deepseek/deepseek-r1-lite-preview                            2,533         0.000                633
deepseek/deepseek-r1-preview                                 2,614         0.000                654
deepseek/deepseek-v3                                           791         0.000                198
deepseek/dscoder-1.3b-ins                                      312         0.000                 78
deepseek/dscoder-33b-ins                                       404         0.000                101
deepseek/dscoder-6.7b-ins                                      478         0.000                120
google/gemini-2.5-flash-04-17                                2,800         0.000                700
google/gemini-2.5-flash-05-20                                9,114         0.000              2,278
google/gemini-2.5-pro-03-25                                  4,102         0.000              1,026
google/gemini-2.5-pro-05-06                                  9,286         0.000              2,322
google/gemini-2.5-pro-06-05                                  7,553         0.000              1,888
google/gemini-exp-1206                                         489         0.000                122
google/gemini-flash-1.5-002                                    476         0.000                119
google/gemini-flash-2.0-exp                                    510         0.000                128
google/gemini-flash-2.0-thinking                               603         0.000                151
google/gemini-flash-2.0-thinking-01-21                      13,240         0.000              3,310
google/gemini-flash-2.0-thinking-12-19                      13,644         0.000              3,411
google/gemini-pro-1.5-002                                      481         0.000                120
lgai/exaone-4.0-32b                                          3,556         0.000                889
meta-llama/llama3.3-70b-ins                                    786         0.000                196
metastone/metastone-l1-7b                                    2,658         0.000                664
mistralai/codestral-latest                                     627         0.000                157
mistralai/mistral-large                                        865         0.000                216
moonshotai/kimi-k1.6-ioi                                     1,141         0.000                285
moonshotai/kimi-k1.6-ioi-high                                1,135         0.000                284
nvidia/llama-3_1-nemotron-nano-8b-v1                           941         0.000                235
nvidia/llama-3_1-nemotron-ultra-253b-v1                        652         0.000                163
nvidia/openreasoning-nemotron-32b                              516         0.000                129
openai/gpt-4-0613                                              396         0.000                 99
openai/gpt-4-turbo-1106                                        671         0.000                168
openai/gpt-4-turbo-2024-04-09                                  860         0.000                215
openai/gpt-4o-2024-05-13                                       608         0.000                152
openai/gpt-4o-2024-08-06                                     1,077         0.000                269
openai/gpt-4o-mini-2024-07-18                                  719         0.000                180
openai/o1-2024-12-17-high                                    1,091         0.000                273
openai/o1-2024-12-17-low                                     1,130         0.000                282
openai/o1-2024-12-17-med                                     1,112         0.000                278
openai/o1-mini-2024-09-12                                      638         0.000                160
openai/o1-preview-2024-09-12                                   628         0.000                157
openai/o3-high                                               1,028         0.000                257
openai/o3-mini-2025-01-31-high                               1,374         0.000                344
openai/o3-mini-2025-01-31-low                                1,318         0.000                330
openai/o3-mini-2025-01-31-med                                1,388         0.000                347
openai/o4-mini-high                                            955         0.000                239
openai/o4-mini-low                                           1,127         0.000                282
openai/o4-mini-medium                                        1,119         0.000                280
qwen/qwen2-ins-72b                                             467         0.000                117
qwen/qwen2.5-coder-ins-32b                                     640         0.000                160
qwen/qwen2.5-coder-ins-7b                                      463         0.000                116
qwen/qwen2.5-ins-32b                                           552         0.000                138
qwen/qwen2.5-ins-72b                                           575         0.000                144
qwen/qwen2.5-ins-7b                                            438         0.000                110
qwen/qwen3-235b-a22b                                        28,537         1.000              7,134
qwen/qwq-32b-preview                                        19,622         0.000              4,906
qwen/qwq-32b_temp                                           19,922         0.952              4,980
qwen/qwq-max-preview                                        19,114         0.997              4,778
xai/grok-3-mini-high                                           748         0.000                187

models with the marker in at least half their first samples: 4 of 67
median output characters per model: from 312 to 37,220 (119.3 times)

runs of one model at more than one reasoning setting (median output characters):
  Claude-Opus-4: none 1,598  Thinking 8,635 (longest over shortest 5.40)
  Claude-Sonnet-4: none 1,960  Thinking 13,393 (longest over shortest 6.83)
  O1-2024-12-17: High 1,091  Med 1,112  Low 1,130 (longest over shortest 1.04)
  O3-Mini-2025-01-31: Low 1,318  High 1,374  Med 1,388 (longest over shortest 1.05)
  O4-Mini: High 955  Medium 1,119  Low 1,127 (longest over shortest 1.18)
```

## Reading it

- The estimate would span two orders of magnitude, 312 to 37,220 characters per median first sample, and the long end is reasoning written into the output: the 4 models with the marker in at least half their first samples have medians of 19,114 to 37,220, and `qwen/qwq-32b-preview` (19,622) and `anthropic/claude-3.7-sonnet` (24,472) are as long with no marker
- The reasoning setting does not show on the OpenAI o-series: 1.04, 1.05 and 1.18 times from the shortest to the longest setting, and `openai/o4-mini` is shortest at high. A text-length cost would give each setting about the same price, whatever each was billed for. `moonshotai/kimi-k1.6-ioi` (1,141) and `moonshotai/kimi-k1.6-ioi-high` (1,135), which the script's setting rule does not pair, look the same
- Thinking shows on the Claude 4 runs, 5.40 and 6.83 times the run without it, so for those a text-length cost would rise with thinking; how much of the billed thinking it misses, length cannot tell
- On input the estimate separates no model: the problem text is the same in all 67 files (0 differ, median 1,283 characters, 449 to 3,950), so every model gets the same input token count and only the list price differs

## Vendor pages

Each vendor's current page on how its models return and bill reasoning, for five of the thirteen vendor families among the 67. A page describes the vendor's models on the date read, not the runs in the files, so the table draws no conclusion on a model the page does not name. Quotes are verbatim but for straight apostrophes. The other eight families (`agentica`, `lgai`, `meta-llama`, `metastone`, `mistralai`, `moonshotai`, `nvidia`, `qwen`) are not read here.

| vendor | page, read | what it says of reasoning and its billing | models among the 67 it names |
|---|---|---|---|
| openai | https://platform.openai.com/docs/guides/reasoning, read 2026-11-08 | "reasoning tokens are not visible via the API" and "are billed as output tokens"; "we don't expose the raw reasoning tokens emitted by the model", and a summary of the reasoning "will not be included unless you explicitly opt in" | `openai/o4-mini-high`, `openai/o4-mini-low`, `openai/o4-mini-medium`: the page names `o4-mini` once, as a model that "supports detailed" reasoning summaries; the other OpenAI models it names are later ones |
| anthropic | https://docs.anthropic.com/en/docs/build-with-claude/thinking and https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking, both read 2026-11-08 | "the tokens Claude spends reasoning are billed as output tokens, even when the thinking text isn't returned to you"; what a thinking block shows "is never the raw chain of thought", but a summary, or an empty field when `display` is `"omitted"`, of which it says "Omitting reduces latency, not cost"; the second page's `thinking_tokens` usage field "reports how many of the billed output tokens were internal reasoning" | none; the first page says the summary is the default display on two later models it names "and earlier models", a group it does not list, and the second page speaks of "earlier Claude 4 models" the same way; read as every earlier model, the group would take in the two Claude 4 models among the 67 on the date read, which says nothing of how they ran when the files were made |
| google | https://ai.google.dev/gemini-api/docs/thinking and https://ai.google.dev/gemini-api/docs/pricing, both read 2026-11-08 | "By default, only the final output is returned", with thought summaries an opt-in; the pricing page heads each output price "Output price (including thinking tokens)" | none; the thinking page names a later Gemini model only, and the pricing page is read here only for that heading |
| xai | https://docs.x.ai/docs/guides/reasoning, read 2026-11-08 | "the reasoning tokens are billed as part of your total consumption"; "Usage metrics expose reasoning_tokens", and the reasoning content "is encrypted by us and can be returned" when the request asks for it, while for one later model it names the page says it comes back, encrypted, on every Responses API response, with summaries of the reasoning exposed | none; the models it names are later Grok models |
| deepseek | https://api-docs.deepseek.com/guides/reasoning_model, read 2026-11-08 | the address now serves the page titled "Your First API Call", which names `deepseek-flash` and `deepseek-v4-pro` and says nothing of how reasoning is returned or billed | none; so no first-party page on the deepseek models among the 67 is read here |

- Every page above that speaks of billing says reasoning is billed as output, and none of them describes returning the raw reasoning by default: openai and xai describe it as encrypted or not returned, with a summary on request for some models, google returns only the final output unless summaries are asked for, and anthropic a summary or an empty block. A cost read from the visible text would under-count any run billed that way
- The pages describe today's models: of the 67 they name only `o4-mini`. Whether each older run returned its reasoning, a summary of it or nothing, today's pages do not say, and the files cannot settle it, since the marker and the lengths are data, not documentation

## Prices

Each model's row says whether its vendor's pricing page lists it on the date read, under which name, and at what standard price per million input and output tokens, in USD, for the shortest prompts where the page tiers by prompt length. A run counts as listed when the page lists a model of the run's name, the folder name less any reasoning setting, up to case, spaces and hyphens, and a dated run only when the page lists that date. Word order is compared as written, and a run named by an alias, a name its vendor gives to whichever version is current (a name ending in `latest`, or a bare name whose earlier versions the vendor's own models page lists under versioned IDs), counts as not listed, since the page prices the version the alias names on the date read, which may not be the run's. A price is the page's on the date read, not the price when the run was made. The pricing pages of `mistralai`, `moonshotai` and `qwen` are read as well, each on its maker's domain; those of the other five families (`agentica`, `lgai`, `meta-llama`, `metastone`, `nvidia`) are not read yet.

| model | pricing page, read | listed as | input | output |
|---|---|---|---|---|
| `agentica/deepcoder-14b-preview` | not read yet | not read | - | - |
| `anthropic/claude-3-haiku` | https://docs.anthropic.com/en/docs/about-claude/pricing, read 2026-11-08 | not listed | - | - |
| `anthropic/claude-3.5-sonnet-20240620` | https://docs.anthropic.com/en/docs/about-claude/pricing, read 2026-11-08 | not listed | - | - |
| `anthropic/claude-3.5-sonnet-20241022` | https://docs.anthropic.com/en/docs/about-claude/pricing, read 2026-11-08 | not listed | - | - |
| `anthropic/claude-3.7-sonnet` | https://docs.anthropic.com/en/docs/about-claude/pricing, read 2026-11-08 | not listed | - | - |
| `anthropic/claude-opus-4` | https://docs.anthropic.com/en/docs/about-claude/pricing, read 2026-11-08 | "Claude Opus 4" | $15.00 | $75.00 |
| `anthropic/claude-opus-4-thinking` | https://docs.anthropic.com/en/docs/about-claude/pricing, read 2026-11-08 | "Claude Opus 4" | $15.00 | $75.00 |
| `anthropic/claude-sonnet-4` | https://docs.anthropic.com/en/docs/about-claude/pricing, read 2026-11-08 | "Claude Sonnet 4" | $3.00 | $15.00 |
| `anthropic/claude-sonnet-4-thinking` | https://docs.anthropic.com/en/docs/about-claude/pricing, read 2026-11-08 | "Claude Sonnet 4" | $3.00 | $15.00 |
| `deepseek/deepseek-r1-0528` | https://api-docs.deepseek.com/quick_start/pricing, read 2026-11-08 | not listed | - | - |
| `deepseek/deepseek-r1-lite-preview` | https://api-docs.deepseek.com/quick_start/pricing, read 2026-11-08 | not listed | - | - |
| `deepseek/deepseek-r1-preview` | https://api-docs.deepseek.com/quick_start/pricing, read 2026-11-08 | not listed | - | - |
| `deepseek/deepseek-v3` | https://api-docs.deepseek.com/quick_start/pricing, read 2026-11-08 | not listed | - | - |
| `deepseek/dscoder-1.3b-ins` | https://api-docs.deepseek.com/quick_start/pricing, read 2026-11-08 | not listed | - | - |
| `deepseek/dscoder-33b-ins` | https://api-docs.deepseek.com/quick_start/pricing, read 2026-11-08 | not listed | - | - |
| `deepseek/dscoder-6.7b-ins` | https://api-docs.deepseek.com/quick_start/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-2.5-flash-04-17` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-2.5-flash-05-20` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-2.5-pro-03-25` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-2.5-pro-05-06` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-2.5-pro-06-05` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-exp-1206` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-flash-1.5-002` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-flash-2.0-exp` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-flash-2.0-thinking` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-flash-2.0-thinking-01-21` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-flash-2.0-thinking-12-19` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `google/gemini-pro-1.5-002` | https://ai.google.dev/gemini-api/docs/pricing, read 2026-11-08 | not listed | - | - |
| `lgai/exaone-4.0-32b` | not read yet | not read | - | - |
| `meta-llama/llama3.3-70b-ins` | not read yet | not read | - | - |
| `metastone/metastone-l1-7b` | not read yet | not read | - | - |
| `mistralai/codestral-latest` | https://mistral.ai/pricing, read 2026-11-08 | not listed | - | - |
| `mistralai/mistral-large` | https://mistral.ai/pricing, read 2026-11-08 | not listed | - | - |
| `moonshotai/kimi-k1.6-ioi` | https://platform.moonshot.ai/docs/pricing/chat, read 2026-11-08 | not listed | - | - |
| `moonshotai/kimi-k1.6-ioi-high` | https://platform.moonshot.ai/docs/pricing/chat, read 2026-11-08 | not listed | - | - |
| `nvidia/llama-3_1-nemotron-nano-8b-v1` | not read yet | not read | - | - |
| `nvidia/llama-3_1-nemotron-ultra-253b-v1` | not read yet | not read | - | - |
| `nvidia/openreasoning-nemotron-32b` | not read yet | not read | - | - |
| `openai/gpt-4-0613` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/gpt-4-turbo-1106` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/gpt-4-turbo-2024-04-09` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/gpt-4o-2024-05-13` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/gpt-4o-2024-08-06` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/gpt-4o-mini-2024-07-18` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o1-2024-12-17-high` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o1-2024-12-17-low` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o1-2024-12-17-med` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o1-mini-2024-09-12` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o1-preview-2024-09-12` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o3-high` | https://platform.openai.com/docs/pricing, read 2026-11-08 | "o3" | $2.00 | $8.00 |
| `openai/o3-mini-2025-01-31-high` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o3-mini-2025-01-31-low` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o3-mini-2025-01-31-med` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o4-mini-high` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o4-mini-low` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `openai/o4-mini-medium` | https://platform.openai.com/docs/pricing, read 2026-11-08 | not listed | - | - |
| `qwen/qwen2-ins-72b` | https://www.alibabacloud.com/help/en/model-studio/model-pricing, read 2026-11-08 | not listed | - | - |
| `qwen/qwen2.5-coder-ins-32b` | https://www.alibabacloud.com/help/en/model-studio/model-pricing, read 2026-11-08 | not listed | - | - |
| `qwen/qwen2.5-coder-ins-7b` | https://www.alibabacloud.com/help/en/model-studio/model-pricing, read 2026-11-08 | not listed | - | - |
| `qwen/qwen2.5-ins-32b` | https://www.alibabacloud.com/help/en/model-studio/model-pricing, read 2026-11-08 | not listed | - | - |
| `qwen/qwen2.5-ins-72b` | https://www.alibabacloud.com/help/en/model-studio/model-pricing, read 2026-11-08 | not listed | - | - |
| `qwen/qwen2.5-ins-7b` | https://www.alibabacloud.com/help/en/model-studio/model-pricing, read 2026-11-08 | not listed | - | - |
| `qwen/qwen3-235b-a22b` | https://www.alibabacloud.com/help/en/model-studio/model-pricing, read 2026-11-08 | not listed | - | - |
| `qwen/qwq-32b-preview` | https://www.alibabacloud.com/help/en/model-studio/model-pricing, read 2026-11-08 | not listed | - | - |
| `qwen/qwq-32b_temp` | https://www.alibabacloud.com/help/en/model-studio/model-pricing, read 2026-11-08 | not listed | - | - |
| `qwen/qwq-max-preview` | https://www.alibabacloud.com/help/en/model-studio/model-pricing, read 2026-11-08 | not listed | - | - |
| `xai/grok-3-mini-high` | https://docs.x.ai/docs/models, read 2026-11-08 | not listed | - | - |

- The eight pricing pages list, by their own name, only the two Claude 4 models, each run with and without thinking at one price per model, and `o3`, the model of `openai/o3-high`. Thinking is billed as output on the anthropic page of `## Vendor pages`, so a text-length cost of the two thinking runs would price only the part of their thinking that reaches the published output
- openai: in the page's source (its text as rendered without scripts shows only the newest models), the standard table of text-token prices lists `gpt-4o` at $2.50 input and $10.00 output and `gpt-4o-mini` at $0.15 and $0.60, by undated names it does not tie to a date, so the dated runs `openai/gpt-4o-2024-05-13`, `openai/gpt-4o-2024-08-06` and `openai/gpt-4o-mini-2024-07-18` are not listed; its fine-tuning table there names `gpt-4o-2024-08-06` and `gpt-4o-mini-2024-07-18` as models to fine-tune, at the price of a model fine-tuned from them, which is not the base model's price. It lists none of the other OpenAI runs: no `gpt-4`, `gpt-4-turbo`, `o1` or `o3-mini` model and no `o4-mini`
- anthropic: no Claude 3 model is on the page, so `anthropic/claude-3-haiku`, the two `anthropic/claude-3.5-sonnet` runs and `anthropic/claude-3.7-sonnet` are not listed
- google: the page lists `gemini-2.5-pro` at $1.25 input and $10.00 output for the shortest prompts and `gemini-2.5-flash` at $0.30 and $2.50, both marked deprecated, with requests to each routed to a later model and billed at that model's rates from 2026-12-01. The five `google/gemini-2.5` runs are dated versions of those two models and the page lists none of their dates, so they are not listed; no Gemini 1.5 or 2.0 model and no `gemini-exp-1206` is on the page
- xai: the page lists one later Grok model only, so `xai/grok-3-mini-high` is not listed
- deepseek: the pricing address, like the reasoning-guide address of `## Vendor pages`, now serves the page titled "Your First API Call", which names `deepseek-flash` and `deepseek-v4-pro` and gives no price figure; it says two retired legacy names are still accepted and "billed at the Flash price", names of no run here, so none of the deepseek runs is listed
- mistralai: the page's source names no Codestral model, and its only per-token prices are in its answer on how API use is priced (its rendered text shows the subscription plans), which gives Mistral Large as the example, at $0.50 per million input tokens and $1.50 output. Both runs are named by aliases: `mistralai/codestral-latest` by its suffix, and `mistralai/mistral-large` because the vendor's models page, https://docs.mistral.ai/getting-started/models/models_overview/ (read 2026-11-08), lists two earlier Mistral Large versions under versioned IDs among its deprecated and retired models, retired on 2025-03-30 and 2026-05-31, and features Mistral Large 4 today. So neither run is listed
- moonshotai: the page lists the K3 and K2 series of Kimi models only, and no k1.6 model, so neither `moonshotai/kimi-k1.6-ioi` run is listed
- qwen: the page, the model price list of Alibaba Cloud Model Studio, the maker's own model service, names `qwen-max` and later Qwen models and none of the ten qwen runs' names, and says "Models in the Qwen2.5 series and other models marked as deprecated in this document are no longer available for calling, and their pricing information can no longer be queried", so none of the qwen runs is listed

## Limits

- Prices of the date read: the pricing pages give today's names and prices, not those of the day each run was made, and the pricing pages of five vendor families and the reasoning pages of eight are not read yet. The reasoning pages read name only `o4-mini` of the 67
- One sample per problem, the first, as the evidence labels it; the later samples are not read
- The input is under-counted for every model alike: the harness's instructions are not in the files
- The marker finds only reasoning that keeps its tag; reasoning written without it is counted as answer
- The ratio of 4 characters per token is for English text; code tokenizes differently, and differently per vendor

## Regenerate

The script downloads the 67 pinned files into the converter's cache when they are not there, checks each by size and sha256, and takes a few seconds once they are cached.

```bash
python research/livecodebench_cost.py
```
