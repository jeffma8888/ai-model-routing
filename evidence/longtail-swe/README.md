# Longtail-SWE evidence

nebius/Longtail-SWE-trajectories, published by Nebius, holds coding-agent runs on issues of open-source repositories in 13 languages, three runs per issue and model under one scaffold, each with the saved `resolved` label of the task's own tests and the run's token counts. Four of its models are the registry's, so routing per task between them can be tested offline with no API key: `convert.py` turns their four parquet files into the outcome matrix that `model-routing evaluate` reads (DESIGN 12.1 and 12.25).

This folder holds the converter, `convert.py`; the committed results of `model-routing evaluate` on its default matrix at bars 0.6 to 0.9 over 50 seeds in both flavors, [results.json](results.json); and what they say, with the commands that regenerate them, [RESULTS.md](RESULTS.md).

## Source

- Dataset: https://huggingface.co/datasets/nebius/Longtail-SWE-trajectories, four files read:
  - `data/swelike__claude-opus-5.5-high.parquet`, 36,213,846 bytes, sha256 `45b9323ae1b33c7301e60a266594202e6f6684de4386c9d50356783b113bea91`
  - `data/swelike__gpt-5.6-luna-xhigh.parquet`, 94,695,456 bytes, sha256 `144ac5b635135d0df37eae6edf2d40148e58f8832d8d59b492a865a98dd99093`
  - `data/swelike__gpt-5.6-sol-high.parquet`, 56,147,793 bytes, sha256 `af2e3bcaf8625d131d467cb4a55164fd63f561d7ee6125db6217cfe603511b57`
  - `data/swelike__gpt-6.1-sol-high.parquet`, 49,548,306 bytes, sha256 `52441cc627aa6688150be052044549b0fe6b2e1215f676a254602919f4bc2fff`
- Pinned revision: `dfd6075c56b7841b9c254cc70a57e39c1df0076c` (last modified 2026-11-16)
- Licence: the dataset card has `license: cc-by-4.0` (CC BY 4.0); its LEGAL.md applies that licence to the compilation and the publisher's own material and leaves source-repository material and third-party model outputs under their own terms, both quoted in [RESULTS.md](RESULTS.md)
- This repo commits no part of the dataset: the converter downloads it into `~/.cache/ai-model-routing-evidence/longtail-swe/`, outside the repo

## The models

The four registry models, each at the one reasoning setting of its file, with their prices in USD per million input and output tokens from `model_routing/data/models.json` and the issues each resolves at run 0, of the 194 kept:

| model | input | output | resolved |
| --- | ---: | ---: | ---: |
| `anthropic/claude-opus-5.5` | 4 | 20 | 162 |
| `openai/gpt-5.6-luna` | 0.2 | 1.2 | 140 |
| `openai/gpt-5.6-sol` | 4 | 20 | 152 |
| `openai/gpt-6.1-sol` | 2 | 10 | 155 |

## Items

One routing task, `issue_resolution`: an item is an issue (`instance_id`) at run 0, so the library's seeded halves split by issue, and one task per language would leave too few issues in each calibration half for `min_samples` 30 (DESIGN 12.25). The kept issues per language, from the converter's report:

| language | items |
| --- | ---: |
| Clojure | 12 |
| Dart | 13 |
| Elixir | 22 |
| Erlang | 12 |
| F# | 16 |
| Haskell | 13 |
| Julia | 26 |
| Kotlin | 11 |
| Lua | 13 |
| OCaml | 12 |
| R | 14 |
| Scala | 17 |
| Swift | 13 |

194 items in all, 776 rows (4 per item).

The converter drops the 8 issues whose initial statement differs from the release's on some model's run (`initial_statement_matches_release` false), for all four models, so every model is scored on one statement per issue; its report lists them under `dropped_statement`. The 1 run with no saved result, `openai/gpt-6.1-sol` on `babashka__cli-162`, counts as a miss with its charge (DESIGN 12.25).

## What a row keeps

Each row has `task`, `item` (the run's `instance_id`), `model`, `correct` (`resolved` is 1) and `cost_usd` (the run's tokens at the model's registry prices, every input token at the input price, with no cache discount). Of each trajectory the converter reads only its `usage.tokens` record; it keeps no prompt, message, tool call, patch or token count.

## Regenerate the matrix

```bash
python -m pip install -e ".[evidence]"
python evidence/longtail-swe/convert.py --out longtail-swe-matrix.jsonl
```

The converter needs `pyarrow`, which the `evidence` extra installs, and prints a JSON report of what it kept: the models, the run, the items per task and per language, the dropped and unscored issues and the rows.
