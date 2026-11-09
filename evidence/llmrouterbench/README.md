# LLMRouterBench evidence

LLMRouterBench recorded, for the items of many benchmarks, each model's score and the cost and token counts of its call. Its 13-model performance-cost pool is scored on the same items of 9 benchmarks, each call with a recorded cost, so routing per benchmark can be tested offline with no API key: `convert.py` turns the records into the outcome matrix that `model-routing evaluate` reads (DESIGN 12.1 and 12.18).

This folder holds the converter, `convert.py`; the committed results of `model-routing evaluate` on its default matrix at bars 0.1 to 0.8 over 50 seeds in both flavors, [results.json](results.json); and what they say, with the commands that regenerate them, [RESULTS.md](RESULTS.md).

## Source

- Dataset: https://huggingface.co/datasets/NPULH/LLMRouterBench, one file `bench-release.tar.gz`
- Pinned revision: `b95870f9e60c589e82f7972c91ffa8de9ca89f85`, 1,283,503,080 bytes, sha256 `b79f8cde1a6f029c2efa663a3a3b6f7748defb22341fe59f328cebef6648c8f1`
- Licence: MIT, as the dataset's LICENSE file states, with the line "Copyright (c) 2025-2026 LLMRouterBench contributors" and this scope paragraph: "This license applies to the original code and benchmark data contributions of LLMRouterBench, to the extent of the contributors' rights. Third-party datasets, code, and other incorporated materials retain their original licenses." This repo commits no part of the dataset: the converter downloads it into `~/.cache/ai-model-routing-evidence/llmrouterbench/`, outside the repo

## The pool

The 13 model folders of the dataset's performance-cost setting, each written as a provider-neutral `vendor/model` ID by a rule over the folder name (DESIGN 12.18):

| folder | model |
| --- | --- |
| `claude-sonnet-4` | `anthropic/claude-sonnet-4` |
| `deepseek-r1-0528` | `deepseek/deepseek-r1-0528` |
| `deepseek-v3-0324` | `deepseek/deepseek-v3-0324` |
| `deepseek-v3.1-terminus` | `deepseek/deepseek-v3.1-terminus` |
| `gemini-2.5-flash` | `google/gemini-2.5-flash` |
| `gemini-2.5-pro` | `google/gemini-2.5-pro` |
| `glm-4.6` | `z-ai/glm-4.6` |
| `gpt-5` | `openai/gpt-5` |
| `gpt-5-chat` | `openai/gpt-5-chat` |
| `intern-s1` | `internlm/intern-s1` |
| `kimi-k2-0905` | `moonshotai/kimi-k2-0905` |
| `qwen3-235b-a22b-2507` | `qwen/qwen3-235b-a22b-2507` |
| `qwen3-235b-a22b-thinking-2507` | `qwen/qwen3-235b-a22b-thinking-2507` |

## Tasks

One routing task per benchmark, in the one split that every pool model has (`arenahard` has no split folder):

| task | split | items |
| --- | --- | ---: |
| `aime` | `hybrid` | 60 |
| `arc-agi` | `v1` | 400 |
| `arenahard` | (none) | 749 |
| `gpqa` | `test` | 198 |
| `hle` | `test` | 2,157 |
| `livecodebench` | `test` | 1,055 |
| `livemathbench` | `test` | 121 |
| `mmlupro` | `test_3000` | 3,000 |
| `simpleqa` | `test` | 4,326 |

12,066 items in all, 156,858 rows (13 per item). An item is kept only when every pool model has a scored record for it and every model's record holds the same question; 2 items fail that question check, one in `arenahard` and one in `hle`.

## What is dropped, and why

- `arenahard_coding`: subset of arenahard
- `arenahard_creative_writing`: subset of arenahard
- `arenahard_math`: subset of arenahard
- `humaneval`: no split holds every pool model
- `swe-bench`: no split holds every pool model
- `tau2`: no split holds every pool model

The three `arenahard` subsets hold 253, 250 and 247 questions, the 750 of `arenahard`, so keeping them too would count each question twice; `humaneval` has a file only for `openai/gpt-5-chat`, `swe-bench` lacks `qwen/qwen3-235b-a22b-thinking-2507` and `tau2` lacks `openai/gpt-5-chat`. A benchmark is never routed over fewer models, so every task routes over the same pool.

## What a row keeps

Each row has `task`, `item` (`<benchmark>|<index>`), `model`, `correct` (a score of 1; a 0.5, given only by the `arenahard` judge, is a miss), `cost_usd` (the record's `cost`), `input_tokens` and `output_tokens` (a negative count, 10 of `openai/gpt-5`'s, written as null). The converter compares each record's question across models through a sha256 digest and keeps no question, prompt, prediction, ground truth or output text.

## Regenerate the matrix

```bash
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
```

The converter prints a JSON report of what it kept and dropped, reading the 1.28 GB file once as a stream with nothing extracted to disk.
