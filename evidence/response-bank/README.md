# Response-bank evidence

The LLM Routing Response Bank recorded, for 13,315 tasks of four benchmark families, the response of each of five models with a binary quality score, its token usage and its billed cost. Every model has a scored cell on every task, each call with a bill, so routing per family can be tested offline with no API key: `convert.py` turns the records into the outcome matrix that `model-routing evaluate` reads (DESIGN 12.1 and 12.20).

This folder holds the converter, `convert.py`; the committed results of `model-routing evaluate` on its default matrix at bars 0.8 and 0.9 over 50 seeds in both flavors, [results.json](results.json); and what they say, with the commands that regenerate them, [RESULTS.md](RESULTS.md).

## Source

- Dataset: https://huggingface.co/datasets/Lurume/llm-routing-response-bank, four files read:
  - `responses_cal.jsonl`, 62,806,440 bytes, sha256 `31262ff3c39cf66c17332bdc3f104bdf25c4abedd8dc75767297fa67c2a08de5`
  - `responses_eval.jsonl`, 942,083,749 bytes, sha256 `c0b9df2c194730cd24757001878a1e24648b4990747d60157261b60818e42305`
  - `scores_cal.jsonl`, 349,266 bytes, sha256 `58826526608edd7ffaa16540fb0393ef631ee428cb708da92dae32d690a995cd`
  - `scores_eval.jsonl`, 12,952,125 bytes, sha256 `09b7376e7964a85aee77644af64188b8b14156fab6201e6f3e80852ea6e42b4b`
- Pinned revision: `547beb31ecd8f12b116b87eb4f56feee73edda6c` (2026-09-17)
- Licence: the dataset's LICENSE file says: "Planned license: Open Data Commons Attribution License v4.0 (ODC-BY-4.0, https://opendatacommons.org/licenses/by/4-0/). Final licensing wording will be attached at the formal publication of the associated study; until then, you may use, redistribute, and build on this data under ODC-BY-4.0 terms with attribution to this dataset repository." Its per-family terms and closing paragraph are quoted in [RESULTS.md](RESULTS.md)
- Attribution: these results derive from the LLM Routing Response Bank, https://huggingface.co/datasets/Lurume/llm-routing-response-bank; the card's Citation section reads "To be added." at this revision
- This repo commits no part of the dataset: the converter downloads it into `~/.cache/ai-model-routing-evidence/response-bank/`, outside the repo

## The models

The five models of the release, each written as a provider-neutral `vendor/model` ID by a rule over the raw ID (DESIGN 12.20):

| raw ID | model |
| --- | --- |
| `deepseek-v4-flash` | `deepseek/deepseek-v4-flash` |
| `deepseek-v4-pro` | `deepseek/deepseek-v4-pro` |
| `glm-5-3-flash` | `z-ai/glm-5.3-flash` |
| `glm-5.3` | `z-ai/glm-5.3` |
| `kimi-k2.7-code` | `moonshotai/kimi-k2.7-code` |

## Tasks

One routing task per family. The release splits each family into calibration and evaluation tasks for its own study; no `task_id` is in both, so the converter joins the two and the library draws its own halves by seed (DESIGN 12.20):

| task | calibration | evaluation | items |
| --- | ---: | ---: | ---: |
| `aime` | 8 | 22 | 30 |
| `gpqa_diamond` | 32 | 166 | 198 |
| `livecodebench` | 88 | 967 | 1,055 |
| `mmlu_pro` | 128 | 11,904 | 12,032 |

13,315 items in all, 66,575 rows (5 per item).

## Finishes and missing cells

The converter's report counts these over the kept cells, per family. A `missing` cell has a score of 0 and no response, so it is a miss at a cost of 0.0 with null token counts; a response that stopped at its length limit keeps its score; an other finish is a `finish_reason` that is neither `stop` nor `length` (null, `content_filter` or `engine_overloaded`), each scored 0:

| task | missing | length | length scored 1 | other finish |
| --- | ---: | ---: | ---: | ---: |
| `aime` | 0 | 5 | 0 | 0 |
| `gpqa_diamond` | 0 | 71 | 0 | 6 |
| `livecodebench` | 0 | 246 | 16 | 3 |
| `mmlu_pro` | 6 | 128 | 1 | 12 |

No item is dropped: every item has a score from all five models, a response or a `missing` reason in every cell, and one prompt digest across its responses.

## What a row keeps

Each row has `task` (the family), `item` (the `task_id`), `model`, `correct` (a `quality` of 1), `cost_usd` (the response's `official_usd`), `input_tokens` and `output_tokens` (the response's `usage.input` and `usage.output`, null for a `missing` cell). The converter reads each file one line at a time and keeps from each response only its key, finish reason, bill and token counts, comparing prompts across models only by their `prompt_sha256`; it keeps no prompt, reference answer, response text or reasoning text.

## Regenerate the matrix

```bash
python -m pip install -e .
python evidence/response-bank/convert.py --out response-bank-matrix.jsonl
```

The converter prints a JSON report of what it kept and dropped, reading each of the four files once, line by line.
