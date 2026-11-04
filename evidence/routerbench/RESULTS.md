# RouterBench results

What `model-routing evaluate` measures on the public RouterBench outcome matrix: 11 models, 65 evals (one task each), 28,281 prompts, each with every model's recorded correctness and cost. For each eval and each of 50 seeds the prompts are split in half by a seeded hash; the router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best model on the calibration half, the cheapest model and every single model (DESIGN 12.3). The file behind every number here is [results.json](results.json): the summary rows and the routed per-task rows, including, for each task, how many of the 50 seeds routed it to each model.

## Results

Routed rows: `success` is the share of correct answers over all held-out prompts of all 65 evals, `cost_usd` is the recorded cost of answering them (both averaged over the 50 seeds), `vs_best_model` is that cost divided by the cost of the best single model (`openai/gpt-4-1106-preview`), `cleared_rate` is the share of (eval, seed) cells where some model cleared the bar on calibration, and `bar_violation_rate` is the share of cleared cells whose held-out success fell below the bar. Baseline rows do not depend on the bar or the flavor.

```text
$ python evidence/routerbench/results.py --table evidence/routerbench/results.json
bar  flavor          success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate
---  --------------  -------  --------  -------------  ------------  ------------------
0.6  cost_effective  0.735    8.9478    0.341          0.804         0.013
0.6  cost_blind      0.819    25.2675   0.963          0.804         0.004
0.7  cost_effective  0.761    11.7482   0.448          0.616         0.032
0.7  cost_blind      0.819    25.2675   0.963          0.616         0.010
0.8  cost_effective  0.808    23.2560   0.886          0.371         0.031
0.8  cost_blind      0.819    25.2675   0.963          0.371         0.016
0.9  cost_effective  0.819    24.9963   0.953          0.111         0.022
0.9  cost_blind      0.819    25.2675   0.963          0.111         0.022

strategy                                 success  cost_usd
---------------------------------------  -------  --------
oracle                                   0.959    1.9634
best_on_calibration                      0.819    25.0029
cheapest                                 0.276    0.4662
model:WizardLM/WizardLM-13B-V1.2         0.414    0.7042
model:anthropic/claude-instant-v1        0.595    1.9550
model:anthropic/claude-v1                0.630    19.5599
model:anthropic/claude-v2                0.633    20.2267
model:meta/code-llama-instruct-34b-chat  0.130    1.8060
model:meta/llama-2-70b-chat              0.276    2.1409
model:mistralai/mistral-7b-chat          0.276    0.4662
model:mistralai/mixtral-8x7b-chat        0.557    1.4065
model:openai/gpt-3.5-turbo-1106          0.627    2.3654
model:openai/gpt-4-1106-preview          0.821    26.2358
model:zero-one-ai/Yi-34B-Chat            0.680    1.8655
```

## Reading it

- `cost_effective` buys the cheapest model that clears the bar on each eval, not the best answer. At bar 0.6 it cleared 80.4% of cells and spent 0.341 of the best single model's cost for an overall success of 0.735 against that model's 0.821; at 0.9 only 11.1% of cells clear, the router falls back to the best available model elsewhere, and the cost ratio rises to 0.953
- `cost_blind` routes each eval to the model with the highest lower bound: success 0.819 at 0.963 of the best single model's cost at every bar, level with `best_on_calibration`
- `bar_violation_rate` for `cost_effective` runs from 0.013 to 0.032 across the four bars, next to a nominal one-sided 0.025 for a 95% Wilson bound on one model. It is a resampling estimate for this matrix (the routed model is picked among several that passed, held-out halves are about 50 prompts for the smallest evals, and the 50 seeds re-split one pool), not a guarantee (DESIGN 12.3, "Reading the numbers")
- The per-prompt oracle reaches 0.959 at 1.9634 USD. Routing per eval gets nowhere near it; whether per-prompt routing can is an open question this file does not answer

## Sensitivity: graded evals

By default the converter drops the six evals whose scores are not just 0 or 1 (see [README.md](README.md)). With `--pass-score 0.75` a call counts as correct when its score is at least 0.75, which brings back `grade-school-math` (7,450 prompts) and `consensus_summary` (362); the other four graded evals stay out as smaller than 100 prompts. That matrix has 67 evals, 36,093 prompts and 397,023 rows. At bar 0.8 with 50 seeds, `cost_effective` routed success is 0.796 at 0.780 of the cost of the best single model (`openai/gpt-4-1106-preview`, 0.790), cleared_rate 0.364 and bar_violation_rate 0.033; `cost_blind` reaches 0.805 at 0.815 with bar_violation_rate 0.018. The 0.75 threshold is a choice, not something the dataset defines.

## Caveats

- The models date from 2023 and the costs are the ones the dataset recorded, at that time's prices
- A task is one eval (`eval_name`), so this is routing per task, not per prompt
- The dataset card states no licence for the data; the RouterBench code is MIT licensed. Source, pinned revision and sha256 are in [README.md](README.md)

## Regenerate

```bash
python -m pip install -e ".[evidence]"
python evidence/routerbench/convert.py --out routerbench-matrix.jsonl
model-routing evaluate --outcomes routerbench-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json > routerbench-evaluate.json
python evidence/routerbench/results.py --evaluate routerbench-evaluate.json --out evidence/routerbench/results.json
python evidence/routerbench/results.py --table evidence/routerbench/results.json
```

The evaluate step takes about 70 seconds on one laptop core and its output is about 2.7 MB, which is why only the summary and the routed per-task rows are committed. Two runs give byte-identical files. The sensitivity numbers come from:

```bash
python evidence/routerbench/convert.py --out routerbench-matrix-p075.jsonl --pass-score 0.75
model-routing evaluate --outcomes routerbench-matrix-p075.jsonl --bar 0.8 --seeds 50
```
