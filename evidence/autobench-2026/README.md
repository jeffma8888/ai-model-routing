# AutoBench Router Benchmark 2026 evidence

The Autobench Router Benchmark 2026 asked 20 current models each of 252 long, open-ended questions, had a committee of judge models score every answer, and stored the billed cost of every call. That is enough to test routing offline with no API key, on 2026 models: `convert.py` turns it into the outcome matrix that `model-routing evaluate` reads (DESIGN 12.1 and 12.9), and `judges.py` turns the per-judge grades into a judge outcome matrix (DESIGN 12.11, [Judge evidence](#judge-evidence-one-item-per-graded-answer)).

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

`--task-by all` makes one task of every kept question, so the evaluator's default `min_samples = 30` can be met; with the default, one task per domain, no domain can meet it (see Reading it), so the routed model never clears the bar. The committed results, [RESULTS.md](RESULTS.md) and [results.json](results.json), use `--task-by all`, with the per-domain matrix only as a stated sensitivity at a lower `--min-samples`.

No extra is needed: the converter is standard library only. It prints a JSON report of what it kept and dropped. With the default options on the pinned files it keeps 203 of 252 questions over 20 models and writes 4,060 rows. The mean success over those rows is 0.667 at the default width and 0.762 at the official width.

## Token counts and a price registry (for the delegation evidence)

```bash
python evidence/autobench-2026/convert.py --out autobench-matrix.jsonl --task-by all --tokens --registry autobench-models.json
```

`--tokens` adds `input_tokens` and `output_tokens` to every row, the cell's own `matrix.csv` columns as integers. `output_tokens` already counts the reasoning tokens, so `reasoning_tokens` is not read. Without `--tokens` the rows are exactly as before. `--registry` writes a `models.json`-format file (DESIGN 4.1) built from `pool.json`: each model's ID, `family`, `context_window` and its list prices per 1M tokens, `input_cost_per_mtok` and `output_cost_per_mtok`. `evaluate_delegation` (DESIGN 13.9) needs both, because a hand-off charges one item's tokens to two models, and a billed per-call total cannot be split that way. A cost from this registry is a list-price estimate: on the default rows, list price times tokens has a median ratio of 1.000 to the billed cost (2 rows are billed 0 and left out).

## What is dropped, and why

- Unscored cells: 107 pool cells have no score (no judge rated them, and 100 of them have a billed cost of 0). A question is kept only when all 20 pool models have a score on it, so the matrix is complete as the evaluator requires; the 49 questions with an unscored cell are dropped and counted, never scored as misses
- Rows outside the pool: `matrix.csv` also holds 388 later `fill_7_4` rows for 13 models outside the 20-model pool, which the dataset uses to grade routers that picked those models. They are dropped and counted
- Repeated cells: a (question, model) pair in two rows is refused rather than resolved by picking one; the pinned file has none

## Reading it

- A task is the question's `ddc_domain`, as written (Dewey Decimal style classes such as `9 History`, plus `A Agentic tool use`): 10 tasks of 12 to 33 kept questions. A calibration half then holds fewer than 30 items, so the evaluator's default `min_samples = 30` cannot be met per domain; `--task-by all` pools every question into one task of 203 items
- The costs are the billed USD per call in the matrix frozen on 2026-08-29 (the card dates the `fill_7_4` rows 2026-09-05, and every one of them is dropped); vendor prices and products have moved since
- Model IDs are written as `vendor/model` from the pool's `openrouter_id`, with hyphens removed from the vendor (`x-ai/grok-4.6` becomes `xai/grok-4.6`, `z-ai/glm-5.3` becomes `zai/glm-5.3`)

## Judge evidence: one item per graded answer

AutoBench publishes every judge's grade of every answer (`judges_json` in `matrix.csv`), so the same pinned files give public evidence for choosing a judge model. `judges.py` turns those grades into a judge outcome matrix in the format `model-routing evaluate` reads (DESIGN 12.11): an item is one graded answer (a question and the pool model that answered it), a model is a candidate judge, and a judge's grade is a success when it is within 0.5 of the mean of the other judges' grades on that answer. It loads `convert.py` from this folder for the pinned files, their checks and the download, and like it is standard library only, so no extra is needed.

```bash
python -m pip install -e .
python evidence/autobench-2026/judges.py --out autobench-judges.jsonl --registry autobench-models.json
model-routing evaluate --outcomes autobench-judges.jsonl --registry autobench-models.json --bar 0.8
```

The rows carry token counts and no cost, so `evaluate` needs `--registry`: the file it writes is the one `convert.py --registry` writes, priced at the pool's list prices. The script prints a JSON report of what it kept and dropped.

Every assumption, each with the option that changes it:

- The label is a committee label, not a human gold label: a judge is scored on agreement with the other judges on the same answer (leave one out). A judge that always grades as the committee does scores 1.0 whether or not the committee is right, and a judge that is right where the committee is wrong scores lower. The answer model's grade of its own answer never enters a committee
- Tolerance 0.5 on the 1 to 5 scale (`--tolerance`), compared as written with no epsilon, against the `math.fsum` mean of the committee's grades. The grades are read from `judges_json`; the dataset's `score` only tells scored answers from unscored ones
- Every committee has at least 3 judges (`--min-committee`)
- The cost of a judge call is an estimate at the pool's list prices, never a billed cost: the judge reads the answer's prompt (that cell's `input_tokens`), the visible answer and an assumed 400-token rubric (`--rubric-tokens`), and writes an assumed 200-token grade (`--grade-tokens`). The visible answer is the cell's `output_tokens` less its `reasoning_tokens`, floored at 0 (`--answer-tokens visible`, the default): `output_tokens` is the billed count with the reasoning in it, and a judge never reads the reasoning. `--answer-tokens output` counts the reasoning too, an upper bound. 707 of the 756 kept answers report some, and their `reasoning_tokens` sum to 0.738 of their `output_tokens` (on 14 of them `reasoning_tokens` is above `output_tokens`, by at most 10%, so the two counts are not exact); the floor gives those 14 an answer of 0 tokens. By default the judges read 1,218,584 input tokens per candidate over the kept answers, 0.406 of the 3,001,074 that `--answer-tokens output` counts
- Candidates: by default the 5 pool judges (`--size`) whose set keeps the most answers, ties to the set whose sorted display IDs come first; `--candidates` names them instead. On the pinned files the five are `deepseek/deepseek-v4-flash-0731`, `google/gemma-4-31b-it`, `meta/muse-glimmer-30b`, `openai/gpt-5.6-luna` and `tencent/hy3`. Each candidate more cuts the kept answers by about a third (1,191 at 4, 756 at 5, 460 at 6), so 5 trades the number of judges compared against the number of items. Judges outside the pool may sit on committees but are never candidates, since they have no price
- Answers to one question are separate items, so the evaluator's random split can put answers to one question in both halves
- One pooled task, `all`; `--task-by domain` makes one task per question domain, as a sensitivity

What is dropped, with the default options on the pinned files:

- Answers by a candidate: 1,252. Generator isolation never lets a model grade its own answer, and dropping the whole answer keeps every candidate on every item. In all, 2,478 answers carry a grade from their own answer model, the answers a self-grading check would measure
- Answers some candidate did not grade (not among that answer's judges, or a null grade): 2,925, so the matrix is complete as the evaluator requires
- Answers with too small a committee: 0
- The 107 unscored cells and the 388 rows outside the pool, as `convert.py` drops them

Kept: 756 of the 4,933 scored answers, 3,780 rows (one per candidate), mean success 0.735 over the rows.
