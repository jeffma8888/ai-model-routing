# AutoBench Router Benchmark 2026 evidence

The Autobench Router Benchmark 2026 asked 20 current models each of 252 long, open-ended questions, had a committee of judge models score every answer, and stored the billed cost of every call. That is enough to test routing offline with no API key, on 2026 models: `convert.py` turns it into the outcome matrix that `model-routing evaluate` reads (DESIGN 12.1 and 12.9).

## Source and licence

- Dataset: https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10
- Pinned revision: [`43755180be7d8097068982d7a3f37fc04cd15379`](https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10/tree/43755180be7d8097068982d7a3f37fc04cd15379)
- Licence: CC-BY-4.0 (https://creativecommons.org/licenses/by/4.0/) on the questions, scores, costs and tables, as the dataset card states. Attribution: Autobench, Autobench Router Benchmark 2026. The card links the paper as [Do LLM Routers Pay for Themselves?](https://autobench.org/reports/do-llm-routers-pay-for-themselves) and asks users to cite it as: Autobench. Do LLM Routers Route? A Pre-Registered, Cost-Aware Audit of Commercial LLM Routers. 2026.
- This repo commits no part of the dataset: the converter downloads it into `~/.cache/ai-model-routing-evidence/autobench-2026/`, outside the repo

The converter reads four files and checks a fifth. Each is pinned in `convert.py` by size and sha256 and checked before it is read; a cached file that fails is an error, never silently replaced. The dataset's own `SHA256SUMS` must also agree with the pins, as a second check.

| File | Bytes | sha256 |
| --- | --- | --- |
| `matrix.csv` | 1,899,644 | `56d7a5c0a586364c8a0c0d5d737d0a4fde2a311a806b93beee38300e668ba28c` |
| `questions.csv` | 298,329 | `c09fff8818218333bb5773e5f96754b41a312c8aa733972cb68f6be024afccb2` |
| `pool.json` | 6,582 | `86c83dcbab072a912a1f61f79c76f32d394fad4e2ecccdbc0c80c2a5b40f67a8` |
| `frozen_params.json` | 2,042 | `53b27f66d85f820637e9bb6215a80d9364b14707c3ff52b1632c1fe4221d76b7` |
| `SHA256SUMS` | 1,198 | `2bb56265da42a3743a493f6b27e2e100597a78ec1724ae4a288fe585ec56b08a` |

## What counts as a success

The scores are judge ratings on a 1 to 5 scale, not right or wrong, so the converter uses the dataset's own **Delta-Hit**: a model's answer is a success when its score is at least the mean of the three best pool scores on that question minus a width. The default width is the dataset's `delta_signal`, 0.2007 (two thirds of the median judge spread); `--width 0.3011090610836323` uses its official width, `delta_official`. Both come from `frozen_params.json`. This rule gives the dataset's own `delta_hit_signal` label on all 6,291 router decisions in its `decisions.csv` that carry one (checked when the converter was written; the opt-in test `test_real_delta_hit_reproduces_the_dataset_labels` repeats the check when that file is in the cache).

A Delta-Hit is relative, not an absolute acceptance check. It means "rated about as well as the best three answers in this pool", by judges that are themselves models from the same pool, so whether an answer counts depends on which other models were asked, and the ratings are model judgments rather than gold labels.

## Regenerate the matrix

```bash
python -m pip install -e .
python evidence/autobench-2026/convert.py --out autobench-matrix.jsonl --task-by all
model-routing evaluate --outcomes autobench-matrix.jsonl --bar 0.8
```

`--task-by all` makes one task of every kept question, so the evaluator's default `min_samples = 30` can be met; with the default, one task per domain, no domain can meet it (see Reading it), so the routed model never clears the bar. Results committed for this dataset use `--task-by all`, with the per-domain matrix only as a stated sensitivity at a lower `--min-samples`.

No extra is needed: the converter is standard library only. It prints a JSON report of what it kept and dropped. With the default options on the pinned files it keeps 203 of 252 questions over 20 models and writes 4,060 rows. The mean success over those rows is 0.667 at the default width and 0.762 at the official width.

## What is dropped, and why

- Unscored cells: 107 pool cells have no score (no judge rated them, and 100 of them have a billed cost of 0). A question is kept only when all 20 pool models have a score on it, so the matrix is complete as the evaluator requires; the 49 questions with an unscored cell are dropped and counted, never scored as misses
- Rows outside the pool: `matrix.csv` also holds 388 later `fill_7_4` rows for 13 models outside the 20-model pool, which the dataset uses to grade routers that picked those models. They are dropped and counted
- Repeated cells: a (question, model) pair in two rows is refused rather than resolved by picking one; the pinned file has none

## Reading it

- A task is the question's `ddc_domain`, as written (Dewey Decimal style classes such as `9 History`, plus `A Agentic tool use`): 10 tasks of 12 to 33 kept questions. A calibration half then holds fewer than 30 items, so the evaluator's default `min_samples = 30` cannot be met per domain; `--task-by all` pools every question into one task of 203 items
- The costs are the billed USD per call in the matrix frozen on 2026-08-29 (the card dates the `fill_7_4` rows 2026-09-05, and every one of them is dropped); vendor prices and products have moved since
- Model IDs are written as `vendor/model` from the pool's `openrouter_id`, with hyphens removed from the vendor (`x-ai/grok-4.6` becomes `xai/grok-4.6`, `z-ai/glm-5.3` becomes `zai/glm-5.3`)
