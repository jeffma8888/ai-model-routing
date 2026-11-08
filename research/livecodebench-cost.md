# What a cost read from LiveCodeBench output length would see

Question: the LiveCodeBench evidence is `cost_blind` only, because the submissions record no cost, no token counts and no list price (`DESIGN.md` 12.16). Yet each pinned file holds every problem's text and every sample's output text, so a cost could be estimated from text length at list price. What would that estimate see, and what would it miss? Short answer: it sees the visible output only, and on the OpenAI reasoning runs the visible length stays the same at every reasoning setting while their reasoning tokens are billed and not shown, so the estimate would price those settings alike. Five vendors' current pages on reasoning are read in `## Vendor pages`. The four that speak of billing say reasoning is billed as output, and none of them describes returning the raw reasoning by default. But of the 67 models the five pages name only `o4-mini`, so they cannot say which of the older runs hid their reasoning. The pricing pages of those five vendors and of `mistralai`, `moonshotai`, `qwen` and `meta-llama`, read in `## Prices`, list by their own name only the two Claude 4 models, each with and without thinking, and `o3`, and the other four families publish their weights and give no per-token price on their own sites. The other eight families' pages, read in `## Vendor pages` as well, are three makers' API pages, which return the reasoning apart from the answer and name none of the runs, and model cards, which say how the published weights write their reasoning: five runs' cards describe a `<think>` block, and only one of those five runs holds the marker in its first samples. This note recommends keeping the evidence `cost_blind` (`## Recommendation`): of the 67 runs only five carry a list price under their own name, and three of those five were made with reasoning whose billed size the files do not show.

## Facts

- Over the 713 problems every one of the 67 files has, the median first-sample output runs from 312 characters (`deepseek/dscoder-1.3b-ins`) to 37,220 (`agentica/deepcoder-14b-preview`), 119.3 times; at 4 characters per token that is 78 to 9,305 output tokens
- 4 of the 67 models hold a `</think>` marker in at least half their first samples: `agentica/deepcoder-14b-preview`, `qwen/qwen3-235b-a22b`, `qwen/qwq-32b_temp` and `qwen/qwq-max-preview`
- The OpenAI runs at three reasoning settings have about the same visible length at each: `openai/o1-2024-12-17` from 1,091 characters (high) to 1,130 (low), 1.04 times; `openai/o3-mini-2025-01-31` 1.05 times; `openai/o4-mini` 1.18 times, with high the shortest, 955 against 1,127 at low
- The OpenAI help page on tokens says reasoning tokens "are not visible as answer text, but they count toward output usage and are billed as output tokens" (read 2026-11-08), so on those runs the visible length cannot show what each setting was billed for
- The two Anthropic models run with and without thinking go the other way: `anthropic/claude-opus-4-thinking` 8,635 characters against 1,598 (5.40 times) and `anthropic/claude-sonnet-4-thinking` 13,393 against 1,960 (6.83 times), so some of what thinking adds reaches the published output; whether it is the reasoning, a summary of it or a longer answer, length alone does not show
- The current pages on reasoning of openai, anthropic, google, xai and deepseek (read 2026-11-08, `## Vendor pages`) name only `o4-mini` of the 67; the four that speak of billing (openai, anthropic, google on its pricing page, xai) say reasoning is billed as output, and none of those four describes returning the raw reasoning by default
- The pages of the other eight families (read 2026-11-08, `## Vendor pages`): the API pages of `mistralai`, `moonshotai` and `qwen` return the reasoning apart from the answer and name none of their runs; the model cards of `lgai/exaone-4.0-32b`, `metastone/metastone-l1-7b` and the two Llama Nemotron runs describe a `<think>` block, yet none of those four runs holds the marker in any first sample (0.000), while `qwen/qwen3-235b-a22b`, whose card describes the same block, holds it in 1.000
- The pricing pages of the same five vendors (read 2026-11-08, `## Prices`) list by their own name only `anthropic/claude-opus-4` and `anthropic/claude-sonnet-4`, each also run with thinking, and `openai/o3-high`; every other run of the five vendors is not listed, the dated OpenAI and Gemini runs because the page lists their names undated or as a later stable model
- The pricing pages of `mistralai`, `moonshotai` and `qwen` (read 2026-11-08, `## Prices`) list none of their 14 runs: the two Mistral runs are named by aliases, names the vendor has given to more than one version, so the name does not say which version the page prices, and the Kimi and Qwen pages list no model of the runs' names
- Of the last five families (read 2026-11-08, `## Prices`), Meta's pricing page names no Llama model, so `meta-llama/llama3.3-70b-ins` is not listed, and `agentica`, `lgai`, `metastone` and `nvidia` give no per-token price on the pages of their own sites read, while each run's model card publishes the weights, so those runs have no first-party price. On every family's pages, only the two Claude 4 models and `o3` carry a first-party price under their own name
- Recommendation: keep the evidence `cost_blind` (`## Recommendation`). A `cost_effective` run at list price could price only the five runs listed under their own name, and three of those, the two Claude 4 thinking runs and `openai/o3-high`, were made with reasoning that their vendors' pages say is billed as output, while length alone does not show how much of it reached the output, so a text-length cost would under-count exactly those three

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

Each vendor family's current page on how its models return and bill reasoning, for every one of the thirteen vendor families among the 67: first the five vendors' reasoning pages, then the other eight families, each on a page of its own domain or on its runs' model cards under its own account on huggingface.co, the cards of `## Prices` for the four families read there. A page describes the vendor's models on the date read, not the runs in the files, so the table draws no conclusion on a model the page does not name, and a model card describes how the published weights generate text, not what the LiveCodeBench harness kept of it. Quotes are verbatim but for straight apostrophes and code shown in backticks.

| vendor | page, read | what it says of reasoning and its billing | models among the 67 it names |
|---|---|---|---|
| openai | https://platform.openai.com/docs/guides/reasoning, read 2026-11-08 | "reasoning tokens are not visible via the API" and "are billed as output tokens"; "we don't expose the raw reasoning tokens emitted by the model", and a summary of the reasoning "will not be included unless you explicitly opt in" | `openai/o4-mini-high`, `openai/o4-mini-low`, `openai/o4-mini-medium`: the page names `o4-mini` once, as a model that "supports detailed" reasoning summaries; the other OpenAI models it names are later ones |
| anthropic | https://docs.anthropic.com/en/docs/build-with-claude/thinking and https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking, both read 2026-11-08 | "the tokens Claude spends reasoning are billed as output tokens, even when the thinking text isn't returned to you"; what a thinking block shows "is never the raw chain of thought", but a summary, or an empty field when `display` is `"omitted"`, of which it says "Omitting reduces latency, not cost"; the second page's `thinking_tokens` usage field "reports how many of the billed output tokens were internal reasoning" | none; the first page says the summary is the default display on two later models it names "and earlier models", a group it does not list, and the second page speaks of "earlier Claude 4 models" the same way; read as every earlier model, the group would take in the two Claude 4 models among the 67 on the date read, which says nothing of how they ran when the files were made |
| google | https://ai.google.dev/gemini-api/docs/thinking and https://ai.google.dev/gemini-api/docs/pricing, both read 2026-11-08 | "By default, only the final output is returned", with thought summaries an opt-in; the pricing page heads each output price "Output price (including thinking tokens)" | none; the thinking page names a later Gemini model only, and the pricing page is read here only for that heading |
| xai | https://docs.x.ai/docs/guides/reasoning, read 2026-11-08 | "the reasoning tokens are billed as part of your total consumption"; "Usage metrics expose reasoning_tokens", and the reasoning content "is encrypted by us and can be returned" when the request asks for it, while for one later model it names the page says it comes back, encrypted, on every Responses API response, with summaries of the reasoning exposed | none; the models it names are later Grok models |
| deepseek | https://api-docs.deepseek.com/guides/reasoning_model, read 2026-11-08 | the address now serves the page titled "Your First API Call", which names `deepseek-flash` and `deepseek-v4-pro` and says nothing of how reasoning is returned or billed | none; so no first-party page on the deepseek models among the 67 is read here |
| agentica | https://huggingface.co/agentica-org/DeepCoder-14B-Preview, read 2026-11-08 | the run's model card calls it "a code reasoning LLM" and asks: "Avoid adding a system prompt; all instructions should be contained within the user prompt"; its text does not say how the reasoning is marked in what the model writes, though the chat template in the page's data ends the generation prompt with `<think>`, so a reply goes on inside a think block; with no first-party API (`## Prices`), nothing on billing | `agentica/deepcoder-14b-preview`, the card's own model |
| lgai | https://huggingface.co/LGAI-EXAONE/EXAONE-4.0-32B, read 2026-11-08 | "You can activate reasoning mode by using the enable_thinking=True argument with the tokenizer, which opens a reasoning block that starts with `<think>` tag without closing it", so in reasoning mode the model writes its reasoning into the text it generates; with no first-party API (`## Prices`), nothing on billing | `lgai/exaone-4.0-32b`, the card's own model; the card does not say which mode the run used |
| meta-llama | https://dev.meta.ai/llama/docs/model-cards-and-prompt-formats/llama3_3, read 2026-11-08 | Meta's model card for the run's model calls it "a text-only 70B instruction-tuned model" and says nothing of reasoning: its text holds neither `think` nor `reasoning` | `meta-llama/llama3.3-70b-ins`, the card's own model |
| metastone | https://huggingface.co/MetaStoneTec/MetaStone-L1-7B, read 2026-11-08 | "MetaStone-L1 is the lite reasoning model of the MetaStone series", and the card's usage notes say "Make sure the model starts with `<think>\n` to prevent generating empty think content", so the model writes its reasoning into the text it generates; with no first-party API (`## Prices`), nothing on billing | `metastone/metastone-l1-7b`, the card's own model |
| mistralai | https://docs.mistral.ai/inference/conversations/reasoning, read 2026-11-08, the page the address https://docs.mistral.ai/capabilities/reasoning/ leads to | "The output of reasoning models includes a reasoning chunk with the model's thinking traces, followed by the final answer"; on two of the models it names, at the lowest setting "the thinking chunk is omitted from the response", and on billing it says only that a full thinking chunk comes "at the cost of increased token usage" | none; the models it names are later ones, Mistral Large 4 among them, and it says "Earlier Magistral models with native reasoning have been deprecated" |
| moonshotai | https://platform.moonshot.ai/docs/guide/use-kimi-k2-thinking-model, which redirects to https://platform.kimi.ai/docs/guide/use-thinking-models, read 2026-11-08 | "The reasoning process is returned in the response's reasoning_content field", apart from the answer's `content` field, and "reasoning_content counts toward token consumption" | none; the models it names are later Kimi models, and no k1.6 model |
| nvidia | https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1, https://huggingface.co/nvidia/Llama-3_1-Nemotron-Ultra-253B-v1 and https://huggingface.co/nvidia/OpenReasoning-Nemotron-32B, read 2026-11-08 | the two Llama Nemotron cards say "Reasoning mode (ON/OFF) is controlled via the system prompt" and "The model will include `<think></think>` if no reasoning was necessary in Reasoning ON model, this is expected behaviour", so with reasoning on the model writes its reasoning into a `<think>` block of the text it generates; the third card calls its model "a reasoning model that is post-trained for reasoning about math, code and science solution generation" and does not say how the reasoning is marked; with no first-party API (`## Prices`), nothing on billing | `nvidia/llama-3_1-nemotron-nano-8b-v1`, `nvidia/llama-3_1-nemotron-ultra-253b-v1`, `nvidia/openreasoning-nemotron-32b`, each card's own model; the two Llama Nemotron cards do not say which mode a run used |
| qwen | https://www.alibabacloud.com/help/en/model-studio/deep-thinking and https://huggingface.co/Qwen/Qwen3-235B-A22B, both read 2026-11-08 | Model Studio's deep thinking page: "The thinking content is returned through the `reasoning_content` field, and the reply content is returned through the `content` field", "Some hybrid thinking models have different prices in thinking and non-thinking modes", and "If the model does not Output Thinking Process in thinking mode, it is billed at the non-thinking mode price"; the run's own model card: "In this mode, the model will generate think content wrapped in a `<think>...</think>` block, followed by the final response" | `qwen/qwen3-235b-a22b`, the card's own model; the deep thinking page names none of the ten runs, and speaks of the Qwen3 open-source models only as a group, as "hybrid thinking" models whose thinking a prompt can switch on and off |

- Every page above that speaks of billing says reasoning is billed as output, and none of them describes returning the raw reasoning by default: openai and xai describe it as encrypted or not returned, with a summary on request for some models, google returns only the final output unless summaries are asked for, and anthropic a summary or an empty block. A cost read from the visible text would under-count any run billed that way
- The five vendors' pages describe today's models: of the 67 they name only `o4-mini`. Whether each older run returned its reasoning, a summary of it or nothing, today's pages do not say, and the files cannot settle it, since the marker and the lengths are data, not documentation
- Of the other eight families, the three whose API pages are read return the reasoning apart from the answer, as a reasoning chunk (`mistralai`) or a `reasoning_content` field (`moonshotai`, `qwen`), and name none of their runs; the `moonshotai` page counts the reasoning toward the tokens consumed, the `qwen` page bills a thinking mode that writes no thinking at the non-thinking price, and the `mistralai` page says only that reasoning costs token usage. The Moonshot address answers with a redirect to `platform.kimi.ai`, the domain of the Kimi platform on the date read
- The model cards say what the published weights write, and the files show what the harness kept, here each run's share of first samples holding the marker in brackets. The cards of `lgai/exaone-4.0-32b` (0.000), `metastone/metastone-l1-7b` (0.000), `nvidia/llama-3_1-nemotron-nano-8b-v1` (0.000) and `nvidia/llama-3_1-nemotron-ultra-253b-v1` (0.000) describe a `<think>` block, yet none of those runs holds the marker, while `qwen/qwen3-235b-a22b` (1.000), whose card describes the same block, does. `agentica/deepcoder-14b-preview` (0.980), whose card's text does not say how the reasoning is marked, holds it too, and `nvidia/openreasoning-nemotron-32b` (0.000), whose card does not say either, does not. So a card cannot show whether a run had reasoning on or kept its tag, and `meta-llama/llama3.3-70b-ins` (0.000), whose card says nothing of reasoning, holds no marker either

## Prices

Each model's row says whether its vendor's pricing page lists it on the date read, under which name, and at what standard price per million input and output tokens, in USD, for the shortest prompts where the page tiers by prompt length. A run counts as listed when the page lists a model of the run's name, the folder name less any reasoning setting, up to case, spaces and hyphens, and a dated run only when the page lists that date. Word order is compared as written, and a run named by an alias, a name its vendor has given to more than one version (a name ending in `latest`, or a bare name whose earlier versions the vendor's own models page lists under versioned IDs), counts as not listed, since the name does not say which version the run was and the page prices the version current on the date read. A price is the page's on the date read, not the price when the run was made. The pricing pages of `mistralai`, `moonshotai`, `qwen` and `meta-llama` are read as well, each on its maker's domain, and the four families whose own domain gives no per-token price (`agentica`, `lgai`, `metastone`, `nvidia`) on each run's own model card under the family's account on huggingface.co, where the weights are published: their rows say `no first-party price`. A host's price, for running an open model on another company's service, is not a first-party price and is not given.

| model | pricing page, read | listed as | input | output |
|---|---|---|---|---|
| `agentica/deepcoder-14b-preview` | https://huggingface.co/agentica-org/DeepCoder-14B-Preview, read 2026-11-08 | no first-party price | - | - |
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
| `lgai/exaone-4.0-32b` | https://huggingface.co/LGAI-EXAONE/EXAONE-4.0-32B, read 2026-11-08 | no first-party price | - | - |
| `meta-llama/llama3.3-70b-ins` | https://dev.meta.ai/docs/pricing-rate-limits, read 2026-11-08 | not listed | - | - |
| `metastone/metastone-l1-7b` | https://huggingface.co/MetaStoneTec/MetaStone-L1-7B, read 2026-11-08 | no first-party price | - | - |
| `mistralai/codestral-latest` | https://mistral.ai/pricing, read 2026-11-08 | not listed | - | - |
| `mistralai/mistral-large` | https://mistral.ai/pricing, read 2026-11-08 | not listed | - | - |
| `moonshotai/kimi-k1.6-ioi` | https://platform.moonshot.ai/docs/pricing/chat, read 2026-11-08 | not listed | - | - |
| `moonshotai/kimi-k1.6-ioi-high` | https://platform.moonshot.ai/docs/pricing/chat, read 2026-11-08 | not listed | - | - |
| `nvidia/llama-3_1-nemotron-nano-8b-v1` | https://huggingface.co/nvidia/Llama-3.1-Nemotron-Nano-8B-v1, read 2026-11-08 | no first-party price | - | - |
| `nvidia/llama-3_1-nemotron-ultra-253b-v1` | https://huggingface.co/nvidia/Llama-3_1-Nemotron-Ultra-253B-v1, read 2026-11-08 | no first-party price | - | - |
| `nvidia/openreasoning-nemotron-32b` | https://huggingface.co/nvidia/OpenReasoning-Nemotron-32B, read 2026-11-08 | no first-party price | - | - |
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

- The nine pricing pages list, by their own name, only the two Claude 4 models, each run with and without thinking at one price per model, and `o3`, the model of `openai/o3-high`. Thinking is billed as output on the anthropic page of `## Vendor pages`, so a text-length cost of the two thinking runs would price only the part of their thinking that reaches the published output
- openai: in the page's source (its text as rendered without scripts shows only the newest models), the standard table of text-token prices lists `gpt-4o` at $2.50 input and $10.00 output and `gpt-4o-mini` at $0.15 and $0.60, by undated names it does not tie to a date, so the dated runs `openai/gpt-4o-2024-05-13`, `openai/gpt-4o-2024-08-06` and `openai/gpt-4o-mini-2024-07-18` are not listed; its fine-tuning table there names `gpt-4o-2024-08-06` and `gpt-4o-mini-2024-07-18` as models to fine-tune, at the price of a model fine-tuned from them, which is not the base model's price. It lists none of the other OpenAI runs: no `gpt-4`, `gpt-4-turbo`, `o1` or `o3-mini` model and no `o4-mini`
- anthropic: no Claude 3 model is on the page, so `anthropic/claude-3-haiku`, the two `anthropic/claude-3.5-sonnet` runs and `anthropic/claude-3.7-sonnet` are not listed
- google: the page lists `gemini-2.5-pro` at $1.25 input and $10.00 output for the shortest prompts and `gemini-2.5-flash` at $0.30 and $2.50, both marked deprecated, with requests to each routed to a later model and billed at that model's rates from 2026-12-01. The five `google/gemini-2.5` runs are dated versions of those two models and the page lists none of their dates, so they are not listed; no Gemini 1.5 or 2.0 model and no `gemini-exp-1206` is on the page
- xai: the page lists one later Grok model only, so `xai/grok-3-mini-high` is not listed
- deepseek: the pricing address, like the reasoning-guide address of `## Vendor pages`, now serves the page titled "Your First API Call", which names `deepseek-flash` and `deepseek-v4-pro` and gives no price figure; it says two retired legacy names are still accepted and "billed at the Flash price", names of no run here, so none of the deepseek runs is listed
- mistralai: the page's source names no Codestral model, and its only per-token prices are in its answer on how API use is priced (its rendered text shows the subscription plans), which gives Mistral Large as the example, at $0.50 per million input tokens and $1.50 output. Both runs are named by aliases: `mistralai/codestral-latest` by its suffix, and `mistralai/mistral-large` because the vendor's models page, https://docs.mistral.ai/getting-started/models/models_overview/ (read 2026-11-08), lists earlier Mistral Large versions, two of them under versioned IDs among its deprecated and retired models, retired on 2025-03-30 and 2026-05-31, and features Mistral Large 4 today, so the bare name does not say which version the run was. So neither run is listed
- moonshotai: the page lists the K3 and K2 series of Kimi models only, and no k1.6 model, so neither `moonshotai/kimi-k1.6-ioi` run is listed
- qwen: the page, the model price list of Alibaba Cloud Model Studio, the maker's own model service, names `qwen-max` and later Qwen models and none of the ten qwen runs' names, and says "Models in the Qwen2.5 series and other models marked as deprecated in this document are no longer available for calling, and their pricing information can no longer be queried", so none of the qwen runs is listed
- meta-llama: the address of the Llama API, https://www.llama.com/products/llama-api/, now leads to Meta's developer site, whose models menu lists its Muse models and Segment Anything, and whose pricing page bills per token only "the reasoning models (Muse Wonder and Muse Spark)" and names no Llama model, so `meta-llama/llama3.3-70b-ins` is not listed. The site's Llama model card page, https://dev.meta.ai/llama/docs/model-cards-and-prompt-formats/llama3_3 (read 2026-11-08), offers the weights for download and names cloud partners, hosts whose prices are not given here
- agentica: the family's own site, https://agentica-project.com/ (read 2026-11-08), describes the project as an open-source initiative spawned from the Berkeley Sky Computing Lab, with blog posts on its models, and offers no API and no price; the run's model card says the project "is released under the MIT License", so `agentica/deepcoder-14b-preview` has published weights and no first-party price
- lgai: LG AI Research's EXAONE page, https://www.lgresearch.ai/exaone (read 2026-11-08), mostly in Korean, presents a later EXAONE model and the company's industry solutions, with a link to try that model, and gives no price; the run's model card publishes the weights under the EXAONE AI Model License Agreement and links a host to try it on, whose price is not given here, so `lgai/exaone-4.0-32b` has no first-party price
- metastone: the run's model card publishes the weights and names no API of its own, no price and no licence, and the card links no site of the family's own, so no other first-party page is read and `metastone/metastone-l1-7b` has no first-party price
- nvidia: the pages of NVIDIA's own model catalog for the two Llama Nemotron runs, https://build.nvidia.com/nvidia/llama-3_1-nemotron-nano-8b-v1 and https://build.nvidia.com/nvidia/llama-3_1-nemotron-ultra-253b-v1 (both read 2026-11-08), give no per-token price: each says to "download and run the NVIDIA NIM inference microservice for this model on your infrastructure of choice" and offers an evaluation of NVIDIA AI Enterprise for production, and the catalog address of the third, https://build.nvidia.com/nvidia/openreasoning-nemotron-32b, serves only the catalog's menus and title, no model page. The three runs' model cards publish the weights under licences that govern their use, the NVIDIA Open Model License for the two Llama Nemotron runs, which also name Meta's Llama licence, and CC-BY-4.0 for `nvidia/openreasoning-nemotron-32b`, so the three runs have no first-party price

## Recommendation

- Keep the evidence `cost_blind`, as `evidence/livecodebench/RESULTS.md` says, and read no cost from the length of the output text
- Too few runs carry a price. By their own name the pricing pages list only `anthropic/claude-opus-4`, `anthropic/claude-opus-4-thinking`, `anthropic/claude-sonnet-4`, `anthropic/claude-sonnet-4-thinking` and `openai/o3-high` (`## Prices`); every other run has no first-party price under its own name on the date read, and the note gives no host's price. A `cost_effective` run at list price could price those five only, so it would route among them, not among the 67 the evidence routes
- Three of those five were billed for what the files may not hold: `anthropic/claude-opus-4-thinking`, `anthropic/claude-sonnet-4-thinking` and `openai/o3-high`, made with thinking or at a high reasoning setting by their names. Their vendors' reasoning pages say reasoning is billed as output (`## Vendor pages`), but they describe current models, so they do not say how these runs returned it, and length alone does not show how much of the billed reasoning reached a run's output: on the OpenAI o-series the visible length barely moves with the setting, and on the Claude 4 runs thinking adds length of unknown make (`## Reading it`). A text-length cost can only under-count such a run, and the `cost_effective` passing sort puts the cheapest model that clears first (`DESIGN.md` 5.3), so the error can only move its choice toward these three
- What is left, the two Claude 4 runs without thinking, would be a routing result over two models of one vendor, priced on an input that misses the harness's instructions (`## Method`)

## Limits

- Prices of the date read: the pricing pages give today's names and prices, not those of the day each run was made. Four families publish weights and sell no tokens on the pages read, so their runs have no first-party price, and what a host charges is another price, not given here. The five vendors' reasoning pages name only `o4-mini` of the 67, and the model cards, which name their runs, describe the published weights, not how the harness ran them
- One sample per problem, the first, as the evidence labels it; the later samples are not read
- The input is under-counted for every model alike: the harness's instructions are not in the files
- The marker finds only reasoning that keeps its tag; reasoning written without it is counted as answer
- The ratio of 4 characters per token is for English text; code tokenizes differently, and differently per vendor
- The recommendation holds for these files and the pages of the date read: a run of the same problems that records each call's billed tokens, input and output with any reasoning, as the usage fields of the vendors' pages report them (`## Vendor pages`), would give each model a cost from its usage, not from text length

## Regenerate

The script downloads the 67 pinned files into the converter's cache when they are not there, checks each by size and sha256, and takes a few seconds once they are cached.

```bash
python research/livecodebench_cost.py
```
