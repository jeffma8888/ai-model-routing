# TRAIL sub-agent sizes

What the public TRAIL traces record about real hand-offs: how many model calls a sub-agent run makes and how many tokens those calls read and write, set beside the sizes the delegation grid assumes (DESIGN 13.11). In 47 of the 117 GAIA traces the top agent (`CodeAgent.run`) hands work to a sub-agent (`ToolCallingAgent.run`), 60 sub-agent runs in all. 38 traces hold one run, 5 two and 4 three. Each run's model calls are the spans of its subtree whose name ends in `.__call__`, and its token counts are the sums of those calls' `llm.token_count.prompt` and `llm.token_count.completion`. The per-run numbers and their min, median and max are in [summary.json](summary.json) (14,483 bytes), written by [summary.py](summary.py).

These are observed usage, not the inputs of DESIGN 13.1. Each call's prompt count is everything that call read (the sub-agent's instructions, the brief and the run's history so far), while 13.1 and 13.2 take the new input each call adds and grow the context from it, so `prompt_tokens` counts each re-read again and must never be read as K times the work's input per call. `model_calls` is the one number comparable with 13.1's K, though it counts every model call of the run, whatever the call's role. The committed delegation points do one work call (`evidence/delegation/results.json`) or two (variant point 0 of `evidence/delegation/variants.json`); every run here makes more.

## Source and licence

- Repo: https://github.com/patronus-ai/trail-benchmark, pinned revision [`0ffbed9db859b4a66250dc783fa4dccf86869595`](https://github.com/patronus-ai/trail-benchmark/tree/0ffbed9db859b4a66250dc783fa4dccf86869595) (commit date 2025-05-14), folder `benchmarking/data/GAIA`, the 117 trace files pinned by size and sha256 in [summary.py](summary.py). The gated Hugging Face copy is never read: its card asks users not to reshare it outside a gated or private repository
- Licence: MIT, as the repo's LICENSE file states, with the line "Copyright (c) 2025 patronus-ai"

## Results

The min, median and max over the 60 runs:

| count | min | median | max |
|---|---|---|---|
| `model_calls` | 3 | 15 | 31 |
| `prompt_tokens` | 5,508 | 94,868.5 | 357,993 |
| `completion_tokens` | 1,990 | 8,343.5 | 21,188 |
| `first_call_prompt_tokens` | 549 | 594.5 | 765 |

`first_call_prompt_tokens` is the prompt count of each run's first model call in walk order, which on every pinned run is also its earliest by `timestamp`; the files do not mark which part of that prompt is the brief.

## What TRAIL lacks

- No success label: the files hold each run's final answer but not the GAIA reference answers, so no run is scored
- No run of a task without its sub-agent, so the same work is never done inline and a brief's loss is not measured
- The sub-agent is its parent's model: every counted call names `o3-mini`, so a cheaper delegate is never tried and no price is compared

So its numbers feed no decision and no results file: they show how large real delegated work is, beside the grid's stated sizes.

## Regenerate

```bash
python evidence/trail/summary.py --out evidence/trail/summary.json
```

The script uses the standard library only. It downloads the 117 pinned files (111,205,744 bytes) into a cache folder outside the repo (`--cache DIR` to choose it), checks each file's size and sha256, and writes the same bytes as the committed file. The `evidence` workflow does not rerun it: its numbers feed no decision, and the test suite compares the committed bytes wherever the 117 files are cached.
