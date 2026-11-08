# What a cost read from LiveCodeBench output length would see

Question: the LiveCodeBench evidence is `cost_blind` only, because the submissions record no cost, no token counts and no list price (`DESIGN.md` 12.16). Yet each pinned file holds every problem's text and every sample's output text, so a cost could be estimated from text length at list price. What would that estimate see, and what would it miss? Short answer: it sees the visible output only, and on the OpenAI reasoning runs the visible length stays the same at every reasoning setting while their reasoning tokens are billed and not shown, so the estimate would price those settings alike. Which of the 67 models publish their reasoning, beyond what the one OpenAI page quoted says of its reasoning models, and each vendor's list price, are not read here, so this note makes no recommendation yet and the evidence stays `cost_blind`.

## Facts

- Over the 713 problems every one of the 67 files has, the median first-sample output runs from 312 characters (`deepseek/dscoder-1.3b-ins`) to 37,220 (`agentica/deepcoder-14b-preview`), 119.3 times; at 4 characters per token that is 78 to 9,305 output tokens
- 4 of the 67 models hold a `</think>` marker in at least half their first samples: `agentica/deepcoder-14b-preview`, `qwen/qwen3-235b-a22b`, `qwen/qwq-32b_temp` and `qwen/qwq-max-preview`
- The OpenAI runs at three reasoning settings have about the same visible length at each: `openai/o1-2024-12-17` from 1,091 characters (high) to 1,130 (low), 1.04 times; `openai/o3-mini-2025-01-31` 1.05 times; `openai/o4-mini` 1.18 times, with high the shortest, 955 against 1,127 at low
- The OpenAI help page on tokens says reasoning tokens "are not visible as answer text, but they count toward output usage and are billed as output tokens" (read 2026-11-08), so on those runs the visible length cannot show what each setting was billed for
- The two Anthropic models run with and without thinking go the other way: `anthropic/claude-opus-4-thinking` 8,635 characters against 1,598 (5.40 times) and `anthropic/claude-sonnet-4-thinking` 13,393 against 1,960 (6.83 times), so some of what thinking adds reaches the published output; whether it is the reasoning, a summary of it or a longer answer, length alone does not show
- Recommendation: none yet. A text-length cost under-counts the runs whose reasoning is billed and unseen; which of the 67 those are, and each vendor's list price on a date read, need the vendors' own pages, which this note does not read yet beyond the one OpenAI page quoted

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
first samples recorded as an empty string, counted as 0 characters: 3 (in 1 files)
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

## Limits

- Lengths only: the note reads no price and does not say which models publish their reasoning; both need each vendor's own pages, dated
- One sample per problem, the first, as the evidence labels it; the later samples are not read
- The input is under-counted for every model alike: the harness's instructions are not in the files
- The marker finds only reasoning that keeps its tag; reasoning written without it is counted as answer
- The ratio of 4 characters per token is for English text; code tokenizes differently, and differently per vendor

## Regenerate

The script downloads the 67 pinned files into the converter's cache when they are not there, checks each by size and sha256, and takes a few seconds once they are cached.

```bash
python research/livecodebench_cost.py
```
