# LiveCodeBench results

What `model-routing evaluate` measures on the public LiveCodeBench submissions: 67 models from 2023 to 2025 on 713 dated contest problems (2023-05-07 to 2024-10-05), one routing task, `code_generation`, with a success label from each problem's own test cases (`graded_list[0]`, the model's first sample passing them) and no cost. See [README.md](README.md) for what the converter reads and keeps, and DESIGN 12.17 for this file's contract. For each of 50 seeds the 713 problems are split in half by a seeded hash; the router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best model on the calibration half, the `cheapest` baseline and each of the 67 models alone. The committed numbers are in [results.json](results.json).

This is `cost_blind` evidence only. The submissions record no cost, no token counts and no list price, so every row of the matrix has `cost_usd` 0.0, which is what `cost_blind` assumes of every model's token cost (DESIGN 12.16). `cost_effective` is not run: with every cost 0 its routing sorts reduce to `cost_blind`'s (DESIGN 5.3), so its rows would only repeat the `cost_blind` rows.

A cost read from the length of the output text was weighed and is not used: [research/livecodebench-cost.md](../../research/livecodebench-cost.md) finds that the vendors' pricing pages list by their own name only five of the 67 runs, and that three of those five, the two Claude 4 thinking runs and `openai/o3-high`, were run with reasoning that their vendors' pages say is billed as output, while the files do not show how much of it each run's output holds, so it recommends keeping this evidence `cost_blind`.

The bars run from 0.1 to 0.9, every tenth strictly inside the per-model first-sample success span on the 713 problems: the models' rates run from 0.093 to 0.913. At bar 0 every model with enough calibration problems clears and at bar 1 none can, so neither is run.

## Source and licence

- Repo: https://github.com/LiveCodeBench/submissions (archived), pinned revision [`6ca212e9c2039373f6e5069d37ffa9db66e23736`](https://github.com/LiveCodeBench/submissions/tree/6ca212e9c2039373f6e5069d37ffa9db66e23736), the 67 kept files listed in [README.md](README.md)
- Licence: MIT, as the repo's LICENSE file states, with the line "Copyright (c) 2025 LiveCodeBench"

## Results

Routed rows: `success` is the share of held-out problems the routed model's first sample solved, averaged over the 50 seeds, `cleared_rate` is the share of the 50 seeds on which some model cleared the bar on the calibration half, and `bar_violation_rate` is the share of cleared seeds whose held-out success fell below the bar. Every `cost_usd` is 0.0000 and every `vs_best_model` is `-`, because no cost is recorded (DESIGN 12.7 prints `-` when the best model's cost is 0). Baseline rows do not depend on the bar.

```text
$ python evidence/routerbench/results.py --table evidence/livecodebench/results.json
bar  flavor      success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate
---  ----------  -------  --------  -------------  ------------  ------------------
0.1  cost_blind  0.902    0.0000    -              1.000         0.000
0.2  cost_blind  0.902    0.0000    -              1.000         0.000
0.3  cost_blind  0.902    0.0000    -              1.000         0.000
0.4  cost_blind  0.902    0.0000    -              1.000         0.000
0.5  cost_blind  0.902    0.0000    -              1.000         0.000
0.6  cost_blind  0.902    0.0000    -              1.000         0.000
0.7  cost_blind  0.902    0.0000    -              1.000         0.000
0.8  cost_blind  0.902    0.0000    -              1.000         0.000
0.9  cost_blind  0.902    0.0000    -              0.180         1.000

strategy                                       success  cost_usd
---------------------------------------------  -------  --------
oracle                                         0.972    0.0000
best_on_calibration                            0.902    0.0000
cheapest                                       0.766    0.0000
model:agentica/deepcoder-14b-preview           0.766    0.0000
model:anthropic/claude-3-haiku                 0.223    0.0000
model:anthropic/claude-3.5-sonnet-20240620     0.518    0.0000
model:anthropic/claude-3.5-sonnet-20241022     0.543    0.0000
model:anthropic/claude-3.7-sonnet              0.691    0.0000
model:anthropic/claude-opus-4                  0.701    0.0000
model:anthropic/claude-opus-4-thinking         0.765    0.0000
model:anthropic/claude-sonnet-4                0.654    0.0000
model:anthropic/claude-sonnet-4-thinking       0.742    0.0000
model:deepseek/deepseek-r1-0528                0.904    0.0000
model:deepseek/deepseek-r1-lite-preview        0.669    0.0000
model:deepseek/deepseek-r1-preview             0.820    0.0000
model:deepseek/deepseek-v3                     0.616    0.0000
model:deepseek/dscoder-1.3b-ins                0.090    0.0000
model:deepseek/dscoder-33b-ins                 0.273    0.0000
model:deepseek/dscoder-6.7b-ins                0.194    0.0000
model:google/gemini-2.5-flash-04-17            0.819    0.0000
model:google/gemini-2.5-flash-05-20            0.832    0.0000
model:google/gemini-2.5-pro-03-25              0.880    0.0000
model:google/gemini-2.5-pro-05-06              0.874    0.0000
model:google/gemini-2.5-pro-06-05              0.891    0.0000
model:google/gemini-exp-1206                   0.534    0.0000
model:google/gemini-flash-1.5-002              0.370    0.0000
model:google/gemini-flash-2.0-exp              0.462    0.0000
model:google/gemini-flash-2.0-thinking         0.524    0.0000
model:google/gemini-flash-2.0-thinking-01-21   0.572    0.0000
model:google/gemini-flash-2.0-thinking-12-19   0.588    0.0000
model:google/gemini-pro-1.5-002                0.431    0.0000
model:lgai/exaone-4.0-32b                      0.859    0.0000
model:meta-llama/llama3.3-70b-ins              0.358    0.0000
model:metastone/metastone-l1-7b                0.590    0.0000
model:mistralai/codestral-latest               0.391    0.0000
model:mistralai/mistral-large                  0.395    0.0000
model:moonshotai/kimi-k1.6-ioi                 0.850    0.0000
model:moonshotai/kimi-k1.6-ioi-high            0.882    0.0000
model:nvidia/llama-3_1-nemotron-nano-8b-v1     0.673    0.0000
model:nvidia/llama-3_1-nemotron-ultra-253b-v1  0.806    0.0000
model:nvidia/openreasoning-nemotron-32b        0.855    0.0000
model:openai/gpt-4-0613                        0.336    0.0000
model:openai/gpt-4-turbo-1106                  0.372    0.0000
model:openai/gpt-4-turbo-2024-04-09            0.423    0.0000
model:openai/gpt-4o-2024-05-13                 0.461    0.0000
model:openai/gpt-4o-2024-08-06                 0.419    0.0000
model:openai/gpt-4o-mini-2024-07-18            0.379    0.0000
model:openai/o1-2024-12-17-high                0.857    0.0000
model:openai/o1-2024-12-17-low                 0.798    0.0000
model:openai/o1-2024-12-17-med                 0.819    0.0000
model:openai/o1-mini-2024-09-12                0.730    0.0000
model:openai/o1-preview-2024-09-12             0.586    0.0000
model:openai/o3-high                           0.891    0.0000
model:openai/o3-mini-2025-01-31-high           0.819    0.0000
model:openai/o3-mini-2025-01-31-low            0.776    0.0000
model:openai/o3-mini-2025-01-31-med            0.822    0.0000
model:openai/o4-mini-high                      0.909    0.0000
model:openai/o4-mini-low                       0.833    0.0000
model:openai/o4-mini-medium                    0.893    0.0000
model:qwen/qwen2-ins-72b                       0.298    0.0000
model:qwen/qwen2.5-coder-ins-32b               0.471    0.0000
model:qwen/qwen2.5-coder-ins-7b                0.332    0.0000
model:qwen/qwen2.5-ins-32b                     0.470    0.0000
model:qwen/qwen2.5-ins-72b                     0.490    0.0000
model:qwen/qwen2.5-ins-7b                      0.295    0.0000
model:qwen/qwen3-235b-a22b                     0.879    0.0000
model:qwen/qwq-32b-preview                     0.641    0.0000
model:qwen/qwq-32b_temp                        0.824    0.0000
model:qwen/qwq-max-preview                     0.836    0.0000
model:xai/grok-3-mini-high                     0.833    0.0000
```

With every cost 0, the `cheapest` baseline is the model with the lowest ID, `agentica/deepcoder-14b-preview` (DESIGN 12.3 breaks a cost tie by model ID), so it is no cost baseline: its 0.766 is that model's success.

## Reading it

- `cost_blind` reaches a held-out success of 0.902 at every bar, the same as `best_on_calibration`: with no cost the router takes the model with the highest Wilson lower bound on the calibration half, and with the same number of calibration problems for every model that is the model with the highest calibration success, so the two pick the same model on every seed. It routes 29 of the 50 seeds to `openai/o4-mini-high` and 21 to `deepseek/deepseek-r1-0528`, at every bar
- Against single models: always calling `openai/o4-mini-high` reaches 0.909 and always calling `deepseek/deepseek-r1-0528` 0.904; the other 65 of the 67 single models reach less than the routed 0.902. Choosing on half of the problems gives up a little held-out success to the best model in hindsight, which no router knows in advance
- The bar holds where the best models clear it with room: at bars 0.1 to 0.8 a model clears on every one of the 50 seeds and no cleared seed falls below the bar on held-out
- Bar violations: 1.000 at bar 0.9 is 9 of the 9 seeds that cleared, against 13 of the 41 seeds that did not clear, and a nominal one-sided 0.025 for the 0.95 Wilson bound. The split cuts one pool of 713 problems in two, so a model's rate on all of them is the mean of its two halves weighted by size, and a calibration half that comes out above it leaves the held-out half below it. On the 9 seeds that cleared bar 0.9 the router took `openai/o4-mini-high`, whose rate on all 713 problems is 0.913: its calibration-half rate was 0.932 to 0.946 and its held-out rate 0.878 to 0.895. A model whose rate sits just above a bar clears it only on a lucky calibration half, and on this pool that luck is paid back on the held-out half. Read the rates as resampling estimates for this pool, never as a guarantee (DESIGN 12.3)
- Calibration halves hold 331 to 376 problems over the 50 seeds, never under `min_samples` 30
- The per-item oracle reaches 0.972, against the routed 0.902: on many problems some model passes where the routed one fails, and routing per task cannot pick per problem
- The models date from 2023 to 2025 and the 713 problems from 2023-05-07 to 2024-10-05, so many problems predate a model's training data: the contamination LiveCodeBench dates its problems to expose. A later model's rate on old problems can overstate what it does on new ones
- A label is the test cases passing for the first sample at the run's own sampling settings, and the runs do not share them: they drew 1, 4 or 10 samples per problem
- The problems come from LeetCode, AtCoder and Codeforces, so nothing of them is kept but the question id and the contest date
- With no cost, this matrix says which model clears a bar, never what it costs
- Size: the committed file, 175,413 bytes, holds only the summary and the routed per-task rows (DESIGN 12.7)

## Regenerate

```bash
python -m pip install -e .
python evidence/livecodebench/convert.py --out livecodebench-matrix.jsonl
model-routing evaluate --outcomes livecodebench-matrix.jsonl --bar 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 --seeds 50 --flavor cost_blind --json > livecodebench-evaluate.json
python evidence/routerbench/results.py --evaluate livecodebench-evaluate.json --out evidence/livecodebench/results.json
python evidence/routerbench/results.py --table evidence/livecodebench/results.json
```

The converter downloads the 67 pinned files (about 1.23 GB) into `~/.cache/ai-model-routing-evidence/livecodebench/` on its first run and checks each against its pinned size and sha256. The evaluate step took about 5.5 seconds on one laptop when the committed file was made; the time is not checked.
