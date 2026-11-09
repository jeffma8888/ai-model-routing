# LLMRouterBench results

What `model-routing evaluate` measures on the public LLMRouterBench records: 13 API models from 2025, each scored on the same items of 9 benchmarks, each benchmark one routing task (`aime` 60 items, `arc-agi` 400, `arenahard` 749, `gpqa` 198, `hle` 2,157, `livecodebench` 1,055, `livemathbench` 121, `mmlupro` 3,000 and `simpleqa` 4,326, 12,066 in all), a success when the record's score is 1 and the record's own `cost` as the cost of the call. See [README.md](README.md) for what the converter reads, keeps and drops, and DESIGN 12.19 for this file's contract. For each of 50 seeds the items of each task are split in half by a seeded hash; the router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best model on the calibration half, the cheapest model and every single model (DESIGN 12.3). The file behind every number here is [results.json](results.json): the summary rows and the routed per-task rows, including how many of the 50 seeds routed to each model. It is made by the RouterBench results script, `evidence/routerbench/results.py`, which does not depend on the dataset.

The bars run from 0.1 to 0.8, every tenth strictly inside the span of the per-task, per-model success rates on all items, which runs from 0.036 (`deepseek/deepseek-v3-0324` on `hle`, 78 of 2,157) to 0.883 (`openai/gpt-5` on `aime`, 53 of 60). With nine tasks the span is taken over every (task, model) pair, so at each bar some model of some task is on each side of it.

## Source and licence

- Dataset: https://huggingface.co/datasets/NPULH/LLMRouterBench, pinned revision [`b95870f9e60c589e82f7972c91ffa8de9ca89f85`](https://huggingface.co/datasets/NPULH/LLMRouterBench/tree/b95870f9e60c589e82f7972c91ffa8de9ca89f85), one file `bench-release.tar.gz`, 1,283,503,080 bytes, sha256 `b79f8cde1a6f029c2efa663a3a3b6f7748defb22341fe59f328cebef6648c8f1`
- Licence: MIT, as the dataset's LICENSE file states, with the line "Copyright (c) 2025-2026 LLMRouterBench contributors" and this scope paragraph: "This license applies to the original code and benchmark data contributions of LLMRouterBench, to the extent of the contributors' rights. Third-party datasets, code, and other incorporated materials retain their original licenses." The benchmarks' own questions are such third-party material, and this repo keeps none of them (see [README.md](README.md))

## Results

Routed rows: `success` is the share of held-out items whose record scored 1, pooled over the nine tasks, `cost_usd` is the recorded cost of those calls (both averaged over the 50 seeds), `vs_best_model` is that cost divided by the cost of the best single model (`google/gemini-2.5-pro`), `cleared_rate` is the share of the 450 (task, seed) cells where some model cleared the bar on the calibration half, and `bar_violation_rate` is the share of cleared cells whose held-out success fell below the bar. Baseline rows do not depend on the bar or the flavor.

```text
$ python evidence/routerbench/results.py --table evidence/llmrouterbench/results.json
bar  flavor          success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate
---  --------------  -------  --------  -------------  ------------  ------------------
0.1  cost_effective  0.553    39.4802   0.108          0.944         0.000
0.1  cost_blind      0.615    173.4190  0.473          0.944         0.000
0.2  cost_effective  0.576    86.9437   0.237          0.944         0.000
0.2  cost_blind      0.615    173.4190  0.473          0.944         0.000
0.3  cost_effective  0.580    97.9296   0.267          0.833         0.000
0.3  cost_blind      0.615    173.4190  0.473          0.833         0.000
0.4  cost_effective  0.580    97.9296   0.267          0.831         0.000
0.4  cost_blind      0.615    173.4190  0.473          0.831         0.000
0.5  cost_effective  0.581    97.9935   0.267          0.722         0.000
0.5  cost_blind      0.615    173.4190  0.473          0.722         0.000
0.6  cost_effective  0.586    113.9149  0.311          0.598         0.026
0.6  cost_blind      0.615    173.4190  0.473          0.598         0.000
0.7  cost_effective  0.598    129.3241  0.353          0.433         0.067
0.7  cost_blind      0.615    173.4190  0.473          0.433         0.021
0.8  cost_effective  0.606    154.0269  0.420          0.256         0.078
0.8  cost_blind      0.615    173.4190  0.473          0.256         0.078

strategy                                  success  cost_usd
----------------------------------------  -------  --------
oracle                                    0.821    33.6900
best_on_calibration                       0.615    171.3368
cheapest                                  0.530    3.3909
model:anthropic/claude-sonnet-4           0.374    51.2358
model:deepseek/deepseek-r1-0528           0.473    82.4778
model:deepseek/deepseek-v3-0324           0.409    4.1138
model:deepseek/deepseek-v3.1-terminus     0.432    5.4773
model:google/gemini-2.5-flash             0.426    51.2620
model:google/gemini-2.5-pro               0.592    366.3999
model:internlm/intern-s1                  0.370    17.4013
model:moonshotai/kimi-k2-0905             0.437    7.9007
model:openai/gpt-5                        0.591    191.4699
model:openai/gpt-5-chat                   0.471    26.5507
model:qwen/qwen3-235b-a22b-2507           0.539    4.8886
model:qwen/qwen3-235b-a22b-thinking-2507  0.522    42.3711
model:z-ai/glm-4.6                        0.438    101.1528
```

Routed rows beat these single models on both counts: `anthropic/claude-sonnet-4` (by bar 0.1 `cost_effective`); `deepseek/deepseek-r1-0528` (by bar 0.1 `cost_effective`); `google/gemini-2.5-flash` (by bar 0.1 `cost_effective`); `google/gemini-2.5-pro` (by bar 0.1 `cost_blind`, bar 0.2 `cost_blind`, bar 0.3 `cost_blind`, bar 0.4 `cost_blind`, bar 0.5 `cost_blind`, bar 0.6 `cost_blind`, bar 0.7 `cost_effective`, bar 0.7 `cost_blind`, bar 0.8 `cost_effective`, bar 0.8 `cost_blind`); `openai/gpt-5` (by bar 0.1 `cost_blind`, bar 0.2 `cost_blind`, bar 0.3 `cost_blind`, bar 0.4 `cost_blind`, bar 0.5 `cost_blind`, bar 0.6 `cost_blind`, bar 0.7 `cost_effective`, bar 0.7 `cost_blind`, bar 0.8 `cost_effective`, bar 0.8 `cost_blind`); `qwen/qwen3-235b-a22b-thinking-2507` (by bar 0.1 `cost_effective`); `z-ai/glm-4.6` (by bar 0.1 `cost_effective`, bar 0.2 `cost_effective`, bar 0.3 `cost_effective`, bar 0.4 `cost_effective`, bar 0.5 `cost_effective`).

## Reading it

- `cost_effective`: At bar 0.1 a model clears on 425 of the 450 (task, seed) cells: on all 50 seeds of every task but `aime`, and on 25 of `aime`'s. The `aime` calibration half holds 22 to 42 of its 60 items over the 50 seeds and is under `min_samples` 30 on 25 of them, where no model can clear (DESIGN 12.3), so its uncleared cells are those seeds; there the router takes the best model available on the calibration half. At bar 0.1 the router spends 0.108 of the best single model's cost for a held-out success of 0.553, against 0.592 for that model (`google/gemini-2.5-pro`). Always calling the cheapest model, `deepseek/deepseek-v3-0324`, reaches 0.409 at 4.1138 USD, so at bar 0.1 the router pays 9.6 times as much for more held-out success. As the bar rises fewer cells clear and the cost rises: at bar 0.8 it reaches 0.606 at 0.420 of the best single model's cost
- `cost_blind` reaches 0.615 at 0.473 of the best single model's cost at every bar, 0.0223 above that model's held-out success, against `best_on_calibration`'s 0.615 at 0.468. Routing per task is what pays here: at bar 0.1 it routes every seed of `arc-agi`, `hle`, `livecodebench` and `mmlupro` to `openai/gpt-5`, which is about as good as `google/gemini-2.5-pro` over all items and costs about half as much, while the other 5 tasks split their seeds among two or more models
- Against the in-sample gain: research/datasets.md finds, on all 12,066 items, that each task's own best model reaches 0.0250 more success than `google/gemini-2.5-pro`. The 0.0223 is 0.89 of the in-sample gain of 0.0250, though the two are measured on different items (the held-out halves here, all items there), so read it as most of the gain surviving the split, not as an exact share
- Bar violations: 0.026 at bar 0.6 (`cost_effective`) is 7 of the 269 cells that cleared, 0.067 at bar 0.7 (`cost_effective`) is 13 of the 195 cells that cleared, 0.078 at bar 0.8 (`cost_effective`) is 9 of the 115 cells that cleared, 0.021 at bar 0.7 (`cost_blind`) is 4 of the 195 cells that cleared and 0.078 at bar 0.8 (`cost_blind`) is 9 of the 115 cells that cleared, against a nominal one-sided 0.025 for the 0.95 Wilson bound. Read them as resampling estimates on held-out halves, not as a guarantee (DESIGN 12.3)
- The per-item oracle reaches 0.821 at 33.6900 USD, while the highest routed success of either flavor at any bar is 0.615: on many items some model succeeds where the one routed to that task fails, and routing per benchmark, not per prompt, cannot pick per item
- Half scores: the four `arenahard` folders are scored by a model judge, and 2,144 kept `arenahard` cells score 0.5. A 0.5 is not a full success, so each counts as a miss (DESIGN 12.18); a run that counts it as a success is not made yet
- The 13 models date from 2025. Each cost is the record's own: summed per model it is 0.853 to 1.502 times the dataset README's price list applied to the same token counts (DESIGN 12.18), so it is a recorded cost from a price table the files do not name, never a list price from `models.json`, which has none of these models
- Dropped by the converter, so not in these numbers: `arenahard_coding`, `arenahard_creative_writing` and `arenahard_math` (their questions are those of `arenahard`), and `humaneval`, `swe-bench` and `tau2`, each lacking a pool model (see [README.md](README.md))
- Size: the committed file, 139,115 bytes, holds only the summary and the routed per-task rows (DESIGN 12.7)

## Regenerate

```bash
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
model-routing evaluate --outcomes llmrouterbench-matrix.jsonl --bar 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 --seeds 50 --json > llmrouterbench-evaluate.json
python evidence/routerbench/results.py --evaluate llmrouterbench-evaluate.json --out evidence/llmrouterbench/results.json
python evidence/routerbench/results.py --table evidence/llmrouterbench/results.json
```

The converter downloads the pinned file (about 1.28 GB) into `~/.cache/ai-model-routing-evidence/llmrouterbench/` on its first run and checks it against its pinned size and sha256; verifying, reading and converting it takes about 13 seconds once it is cached.
