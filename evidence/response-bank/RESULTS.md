# Response-bank results

What `model-routing evaluate` measures on the public LLM Routing Response Bank: 5 models, each scored on the same tasks of 4 benchmark families, each family one routing task (`aime` 30 items, `gpqa_diamond` 198, `livecodebench` 1,055 and `mmlu_pro` 12,032, 13,315 in all), a success when the response's `quality` is 1 (the label of an exact-answer parser, or of LiveCodeBench's tests for code) and the response's billed `official_usd` as the cost of the call. See [README.md](README.md) for what the converter reads, keeps and drops, and DESIGN 12.21 for this file's contract. For each of 50 seeds the items of each task are split in half by a seeded hash; the router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best model on the calibration half, the cheapest model and every single model (DESIGN 12.3). The file behind every number here is [results.json](results.json): the summary rows and the routed per-task rows, including how many of the 50 seeds routed to each model. It is made by the RouterBench results script, `evidence/routerbench/results.py`, which does not depend on the dataset.

The bars are 0.8 and 0.9, every tenth strictly inside the span of the per-task, per-model success rates on all items, which runs from 0.767 (`z-ai/glm-5.3` on `aime`, 23 of 30) to 0.967 (`deepseek/deepseek-v4-pro` on `aime`, 29 of 30). Each of the five models scores from 0.767 to 0.967 on every family, so only two tenths fall inside. At 0.9 only `gpqa_diamond` clears, on 1 seed of 50, and the held-out half of that seed falls below the bar.

## Source and licence

- Dataset: https://huggingface.co/datasets/Lurume/llm-routing-response-bank, the LLM Routing Response Bank, pinned revision [`547beb31ecd8f12b116b87eb4f56feee73edda6c`](https://huggingface.co/datasets/Lurume/llm-routing-response-bank/tree/547beb31ecd8f12b116b87eb4f56feee73edda6c) (2026-09-17), of which the converter reads four files:
  - `responses_cal.jsonl`, 62,806,440 bytes, sha256 `31262ff3c39cf66c17332bdc3f104bdf25c4abedd8dc75767297fa67c2a08de5`
  - `responses_eval.jsonl`, 942,083,749 bytes, sha256 `c0b9df2c194730cd24757001878a1e24648b4990747d60157261b60818e42305`
  - `scores_cal.jsonl`, 349,266 bytes, sha256 `58826526608edd7ffaa16540fb0393ef631ee428cb708da92dae32d690a995cd`
  - `scores_eval.jsonl`, 12,952,125 bytes, sha256 `09b7376e7964a85aee77644af64188b8b14156fab6201e6f3e80852ea6e42b4b`
- Licence: the dataset card names no standard licence (`license: other`) and points to the dataset's LICENSE file, which at the pinned revision (1,480 bytes, sha256 `ebff7b5d9a32da5f04702a29a8b6ce45bbc7b805963cfe45aeb85cd00e0ef6cd`, read on 2026-11-12) says, apart from its title and with each paragraph or list item joined onto one line:
  - "Planned license: Open Data Commons Attribution License v4.0 (ODC-BY-4.0, https://opendatacommons.org/licenses/by/4-0/). Final licensing wording will be attached at the formal publication of the associated study; until then, you may use, redistribute, and build on this data under ODC-BY-4.0 terms with attribution to this dataset repository."
  - Per-family terms:
    - `mmlu_pro` subset: "derived from TIGER-Lab/MMLU-Pro (MIT). Retain the upstream notice when redistributing."
    - `livecodebench` subset: "problems originate from LeetCode, AtCoder, and Codeforces and are republished as gathered by the LiveCodeBench benchmark; problem statements remain the copyright of their original platforms."
    - `aime` subset: "AIME 2025 problems are copyright MAA / Art of Problem Solving, reproduced here without modification for research use."
    - `gpqa_diamond` subset: "only non-recoverable metadata (task ids, prompt hashes, lengths, outcomes, usage, cost) is included. Users must obtain the questions from the gated official source under its own terms; the terms of that source (including the prohibition on publishing examples in plain text and requests not to train on them) bind downstream use."
  - "Model responses are outputs of third-party language models, collected and released by the dataset compilers. The compilers make no warranty as to accuracy or fitness for any purpose."
- Attribution, as those terms ask: the data behind these results is the LLM Routing Response Bank, from the dataset repository https://huggingface.co/datasets/Lurume/llm-routing-response-bank. The card's Citation section reads "To be added." at this revision, so the repository is named instead
- This repo commits no part of the dataset: [results.json](results.json) holds only per-task and pooled numbers, and the converter keeps no question, prompt, reference answer or response text (see [README.md](README.md)), so none of the families' materials named above is redistributed here

## Results

Routed rows: `success` is the share of held-out items whose response scored 1, pooled over the four tasks, `cost_usd` is the billed cost of those calls (both averaged over the 50 seeds), `vs_best_model` is that cost divided by the cost of the best single model (`deepseek/deepseek-v4-pro`), `cleared_rate` is the share of the 200 (task, seed) cells where some model cleared the bar on the calibration half, and `bar_violation_rate` is the share of cleared cells whose held-out success fell below the bar. Baseline rows do not depend on the bar or the flavor.

```text
$ python evidence/routerbench/results.py --table evidence/response-bank/results.json
bar  flavor          success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate
---  --------------  -------  --------  -------------  ------------  ------------------
0.8  cost_effective  0.847    5.4902    0.201          0.735         0.000
0.8  cost_blind      0.874    57.4404   2.104          0.735         0.000
0.9  cost_effective  0.874    57.4387   2.104          0.005         1.000
0.9  cost_blind      0.874    57.4404   2.104          0.005         1.000

strategy                          success  cost_usd
--------------------------------  -------  --------
oracle                            0.938    8.0211
best_on_calibration               0.874    57.4387
cheapest                          0.847    5.4364
model:deepseek/deepseek-v4-flash  0.861    23.2204
model:deepseek/deepseek-v4-pro    0.872    27.2956
model:moonshotai/kimi-k2.7-code   0.871    71.0675
model:z-ai/glm-5.3                0.855    69.0601
model:z-ai/glm-5.3-flash          0.845    6.2289
```

Routed rows beat these single models on both counts: `moonshotai/kimi-k2.7-code` (by bar 0.8 `cost_blind`, bar 0.9 `cost_effective`, bar 0.9 `cost_blind`); `z-ai/glm-5.3` (by bar 0.8 `cost_blind`, bar 0.9 `cost_effective`, bar 0.9 `cost_blind`); `z-ai/glm-5.3-flash` (by bar 0.8 `cost_effective`).

## Reading it

- `cost_effective`: At bar 0.8 a model clears on 147 of the 200 (task, seed) cells; of their 50 seeds each, it clears on 0 of `aime`, 47 of `gpqa_diamond`, 50 of `livecodebench` and 50 of `mmlu_pro`. The `aime` calibration half holds 10 to 21 of its 30 items over the 50 seeds and is under `min_samples` 30 on 50 of them, so on every seed no model can clear it (DESIGN 12.3) and the router takes the best model available on the calibration half. At bar 0.8 the router spends 0.201 of the best single model's cost for a held-out success of 0.847, against 0.872 for that model (`deepseek/deepseek-v4-pro`), and it routes every seed of `livecodebench` and `mmlu_pro` to `z-ai/glm-5.3-flash`. Always calling the cheapest model, `z-ai/glm-5.3-flash`, reaches 0.845 at 6.2289 USD, so at bar 0.8 the router pays 0.881 of that cost for more held-out success; the `cheapest` baseline, which takes the model of lowest mean calibration cost on each task, reaches 0.847 at 5.4364 USD
- At bar 0.9 a model clears on 1 of the 200 cells, 1 seed of `gpqa_diamond`. Where no model clears, the router takes the best model available on the calibration half (DESIGN 12.3), so `cost_effective` there reaches 0.874 at 2.104 of the best single model's cost, the held-out success and cost of `best_on_calibration`
- `cost_blind` reaches 0.874 at 2.104 of the best single model's cost at every bar, 0.0022 above that model's held-out success, while the 5 single models' held-out successes run from 0.845 to 0.872: at bar 0.8 it routes 45 of the 50 `mmlu_pro` seeds to `moonshotai/kimi-k2.7-code`, the single model with the highest cost, 71.0675 USD. Where the models are this close, leaving cost out buys little held-out success at a much higher cost
- Bar violations: 1.000 at bar 0.9 (`cost_effective`) is 1 of 1 cleared cell and 1.000 at bar 0.9 (`cost_blind`) is 1 of 1 cleared cell, against a nominal one-sided 0.025 for the 0.95 Wilson bound. One cleared cell gives no rate worth reading; the 0.8 rows, where most cells clear, show none (DESIGN 12.3)
- The per-item oracle reaches 0.938 at 8.0211 USD, while the highest routed success of either flavor at any bar is 0.874: on some items some model succeeds where the one routed to that task fails, and routing per family, not per prompt, cannot pick per item
- Each cost is the response's billed `official_usd`, which the dataset card describes as provider billing in USD including cache discounts: a recorded bill, never tokens times a list price, and never a price from `models.json`, which has none of the five models (DESIGN 12.20)
- `mmlu_pro` holds 12,032 of the 13,315 items, so the pooled rows mostly measure it; each family is routed apart, on its own halves
- Misses with no bill: the 6 `missing` cells (all on `mmlu_pro`, three each of `z-ai/glm-5.3` and `z-ai/glm-5.3-flash`: provider content filters and one refusal) score 0 at a cost of 0.0, so a router that picks either model there meets those failures (DESIGN 12.20)
- Length finishes keep their label: 450 kept cells stopped at their length limit and 17 of them score 1, since the label is what an acceptance check reads from the returned text (DESIGN 12.20)
- Both splits: the release's 256 calibration and 13,059 evaluation tasks are joined, and the halves here are the library's own, drawn by seed as on every other dataset (DESIGN 12.20). Nothing is dropped: every item has a score from all five models, a response or a `missing` reason in every cell, and one prompt digest across its responses
- Size: the committed file, 17,451 bytes, holds only the summary and the routed per-task rows (DESIGN 12.7)

## Regenerate

```bash
python -m pip install -e .
python evidence/response-bank/convert.py --out response-bank-matrix.jsonl
model-routing evaluate --outcomes response-bank-matrix.jsonl --bar 0.8 0.9 --seeds 50 --json > response-bank-evaluate.json
python evidence/routerbench/results.py --evaluate response-bank-evaluate.json --out evidence/response-bank/results.json
python evidence/routerbench/results.py --table evidence/response-bank/results.json
```

The converter downloads the four pinned files (1,018,191,580 bytes) into `~/.cache/ai-model-routing-evidence/response-bank/` on its first run and checks each against its pinned size and sha256; verifying, reading and converting them takes about 3 seconds once they are cached.
