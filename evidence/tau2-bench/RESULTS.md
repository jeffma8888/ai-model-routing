# tau2-bench results

What `model-routing evaluate` measures on the public tau2-bench paper results: 4 agent models from 2025, each in 3 customer-service domains (airline 50 tasks, retail 114, telecom 114), one conversation per task and agent with a simulated user, a success label from the run's own program checks (`reward_info.reward` of 1) and the agent's recorded cost of that conversation (`agent_cost`; the simulated user's `user_cost` is never counted). See [README.md](README.md) for what the converter reads and keeps, and DESIGN 12.15 for this file's contract. Each domain is one routing task, the converter's default, because a task in this library is one kind of job and the three domains are three kinds. For each of 50 seeds the tasks of each domain are split in half by a seeded hash; the router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best agent on the calibration half, the cheapest agent and every single agent (DESIGN 12.3). The file behind every number here is [results.json](results.json): the summary rows and the routed per-domain rows, including how many of the 50 seeds routed to each agent. It is made by the RouterBench results script, `evidence/routerbench/results.py`, which does not depend on the dataset.

The bars run from 0.3 to 0.8, every tenth from the one below the lowest per-domain agent success rate to the one above the highest: the agents' per-domain success rates at trial 0 run from 0.368 to 0.798. The 0.6 to 0.9 of the other datasets would leave two bars at which no cell clears and say nothing below 0.6.

## Source and licence

- Repo: https://github.com/sierra-research/tau2-bench, pinned revision [`033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f`](https://github.com/sierra-research/tau2-bench/tree/033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f), folder `data/tau2/results/final`, the 12 default run files listed in [README.md](README.md)
- Licence: MIT, as the repo's LICENSE file states, with the line "Copyright (c) 2025 Sierra Research"

## Results

Routed rows: `success` is the share of held-out tasks whose conversation passed the program checks, pooled over the three domains, `cost_usd` is the recorded agent cost of those conversations (both averaged over the 50 seeds), `vs_best_model` is that cost divided by the cost of the best single agent (`anthropic/claude-3-7-sonnet-20250219`), `cleared_rate` is the share of the 150 (domain, seed) cells where some agent cleared the bar on the calibration half, and `bar_violation_rate` is the share of cleared cells whose held-out success fell below the bar. Baseline rows do not depend on the bar or the flavor.

```text
$ python evidence/routerbench/results.py --table evidence/tau2-bench/results.json
bar  flavor          success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate
---  --------------  -------  --------  -------------  ------------  ------------------
0.3  cost_effective  0.547    9.1340    0.144          0.667         0.000
0.3  cost_blind      0.589    40.3751   0.639          0.667         0.000
0.4  cost_effective  0.544    15.6738   0.248          0.400         0.033
0.4  cost_blind      0.589    40.3751   0.639          0.400         0.033
0.5  cost_effective  0.545    16.4831   0.261          0.333         0.000
0.5  cost_blind      0.589    40.3751   0.639          0.333         0.000
0.6  cost_effective  0.559    24.2031   0.383          0.327         0.061
0.6  cost_blind      0.589    40.3751   0.639          0.327         0.000
0.7  cost_effective  0.578    30.7979   0.487          0.080         0.083
0.7  cost_blind      0.589    40.3751   0.639          0.080         0.000
0.8  cost_effective  0.578    31.0962   0.492          0.000         -
0.8  cost_blind      0.589    40.3751   0.639          0.000         -

strategy                                    success  cost_usd
------------------------------------------  -------  --------
oracle                                      0.801    7.6369
best_on_calibration                         0.578    31.0962
cheapest                                    0.548    3.6044
model:anthropic/claude-3-7-sonnet-20250219  0.612    63.2133
model:openai/gpt-4.1-2025-04-14             0.562    11.3983
model:openai/gpt-4.1-mini-2025-04-14        0.548    3.6044
model:openai/o4-mini-2025-04-16             0.571    10.2499
```

No routed row beats any of the 4 single agents on both counts: against each of them, every routed row in the table has lower held-out success or a higher cost.

## Reading it

- `cost_effective`: At bar 0.3 a model clears on 100 of the 150 (domain, seed) cells, and the router spends 0.144 of the best single agent's cost for a held-out success of 0.547, against 0.612 for that agent (`anthropic/claude-3-7-sonnet-20250219`). Always calling the cheapest agent, `openai/gpt-4.1-mini-2025-04-14`, reaches 0.548 at 3.6044 USD, so at bar 0.3 the router pays 2.5 times as much for no more held-out success. As the bar rises fewer cells clear, the router falls back to the best agent available on more of them, and its cost rises toward that of `best_on_calibration`
- Where routing per domain works: On retail at bars 0.3 and 0.4 `cost_effective` routes all 50 seeds to `openai/gpt-4.1-mini-2025-04-14`, for a held-out success of 0.692 at 0.7711 USD, against `cost_blind`'s 0.795 at 18.1069 USD there. The cost at the lowest bars comes from the other two domains: on airline a model clears on 10 of the 50 seeds at bar 0.3 and on none from bar 0.5, because the airline calibration half holds 16 to 35 tasks over the 50 seeds, under `min_samples` 30 on 40 of them; retail holds 45 to 65 and telecom 44 to 68. On a cell where no agent clears, the router takes the best agent available on the calibration half (DESIGN 12.3), which is rarely the cheapest
- `cost_blind` reaches 0.589 at 0.639 of the best single agent's cost at every bar, against `best_on_calibration`'s 0.578 at 0.492.
- Bar violations: 0.033 at bar 0.4 is 2 of the 60 cells that cleared, 0.061 at bar 0.6 is 3 of the 49 cells that cleared, and 0.083 at bar 0.7 is 1 of the 12 cells that cleared, against a nominal one-sided 0.025 for the 0.95 Wilson bound. Read them as resampling estimates on held-out halves of 15 to 70 tasks, not as a guarantee (DESIGN 12.3)
- The per-item oracle reaches 0.801 at 7.6369 USD, while the highest routed success of either flavor at any bar is 0.589: on many tasks some agent succeeds where the one routed to that domain fails, and routing per domain cannot pick per task
- The 4 agents date from 2025, and the costs are those the runs recorded at the prices of their time
- The airline and retail tasks are the June 2025 task sets, which the folder's README says differ from the current base tasks ("airline: 29 tasks differ, retail: 114"); telecom is unchanged
- A model, `openai/gpt-4.1-2025-04-14`, plays the user in every conversation, so a reward is the agent's success with that simulated user, and a failed conversation can be the simulator's fault
- Size: the committed file, 44,822 bytes, holds only the summary and the routed per-domain rows (DESIGN 12.7)

## Sensitivity

Not committed as files; each comes from the commands below with the same bars and seeds.

Pooled matrix (`--task-by all`, one task of all 278 tasks, whose calibration half is never under `min_samples`):

- pooled, bar 0.3, `cost_effective`: routed success 0.548 at 3.6044 USD, cleared_rate 1.000, bar_violation_rate 0.000
- pooled, bar 0.4, `cost_effective`: routed success 0.548 at 3.6044 USD, cleared_rate 1.000, bar_violation_rate 0.000
- pooled, bar 0.5, `cost_effective`: routed success 0.577 at 41.7068 USD, cleared_rate 0.720, bar_violation_rate 0.028
- pooled, bar 0.6, `cost_effective`: routed success 0.586 at 49.9335 USD, cleared_rate 0.000, bar_violation_rate -
- pooled, bar 0.7, `cost_effective`: routed success 0.586 at 49.9335 USD, cleared_rate 0.000, bar_violation_rate -
- pooled, bar 0.8, `cost_effective`: routed success 0.586 at 49.9335 USD, cleared_rate 0.000, bar_violation_rate -

Trials 1, 2 and 3 (`--trial N`, the per-domain matrix of that trial), at the lowest bar:

- trial 1, bar 0.3, `cost_effective`: routed success 0.556 at 11.7471 USD, cleared_rate 0.733, bar_violation_rate 0.000
- trial 1, bar 0.3, `cost_blind`: routed success 0.629 at 50.1429 USD, cleared_rate 0.733, bar_violation_rate 0.000
- trial 1: best single agent `anthropic/claude-3-7-sonnet-20250219` 0.630 at 58.6432 USD, cheapest agent `openai/gpt-4.1-mini-2025-04-14` 0.546 at 3.7188 USD
- trial 1, single agents: No routed row beats any of the 4 single agents on both counts: against each of them, every routed row in the table has lower held-out success or a higher cost.
- trial 2, bar 0.3, `cost_effective`: routed success 0.561 at 6.9489 USD, cleared_rate 0.720, bar_violation_rate 0.000
- trial 2, bar 0.3, `cost_blind`: routed success 0.629 at 44.4082 USD, cleared_rate 0.720, bar_violation_rate 0.000
- trial 2: best single agent `anthropic/claude-3-7-sonnet-20250219` 0.627 at 58.9575 USD, cheapest agent `openai/gpt-4.1-mini-2025-04-14` 0.542 at 3.8008 USD
- trial 2, single agents: Routed rows beat these single agents on both counts: `anthropic/claude-3-7-sonnet-20250219` (by bar 0.3 `cost_blind`, bar 0.4 `cost_blind`, bar 0.5 `cost_blind`, bar 0.6 `cost_blind`, bar 0.7 `cost_blind`, bar 0.8 `cost_blind`).
- trial 3, bar 0.3, `cost_effective`: routed success 0.545 at 16.3502 USD, cleared_rate 0.713, bar_violation_rate 0.000
- trial 3, bar 0.3, `cost_blind`: routed success 0.604 at 49.5182 USD, cleared_rate 0.713, bar_violation_rate 0.000
- trial 3: best single agent `anthropic/claude-3-7-sonnet-20250219` 0.617 at 60.4148 USD, cheapest agent `openai/gpt-4.1-mini-2025-04-14` 0.549 at 3.6943 USD
- trial 3, single agents: No routed row beats any of the 4 single agents on both counts: against each of them, every routed row in the table has lower held-out success or a higher cost.

So the trial 0 sentence under the table, that no routed row beats a single agent on both counts, holds on trials 1 and 3 but not on trial 2, where `cost_blind` beats always calling `anthropic/claude-3-7-sonnet-20250219` at every bar (0.629 at 44.4082 USD against 0.627 at 58.9575). On trial 1 `cost_blind` reaches 0.629 against that agent's 0.630. On trials 1 to 3 the `cost_effective` row at the lowest bar costs 1.8 to 4.4 times as much as the cheapest agent, for a held-out success of 0.545 to 0.561 against that agent's 0.542 to 0.549.

```bash
python evidence/tau2-bench/convert.py --out tau2-all.jsonl --task-by all
model-routing evaluate --outcomes tau2-all.jsonl --bar 0.3 0.4 0.5 0.6 0.7 0.8 --seeds 50
python evidence/tau2-bench/convert.py --out tau2-trial-1.jsonl --trial 1
model-routing evaluate --outcomes tau2-trial-1.jsonl --bar 0.3 0.4 0.5 0.6 0.7 0.8 --seeds 50
```

Repeat the last two lines with `--trial 2` and `--trial 3`.

## Regenerate

```bash
python -m pip install -e .
python evidence/tau2-bench/convert.py --out tau2-matrix.jsonl
model-routing evaluate --outcomes tau2-matrix.jsonl --bar 0.3 0.4 0.5 0.6 0.7 0.8 --seeds 50 --json > tau2-evaluate.json
python evidence/routerbench/results.py --evaluate tau2-evaluate.json --out evidence/tau2-bench/results.json
python evidence/routerbench/results.py --table evidence/tau2-bench/results.json
```

The converter downloads the 12 pinned files (about 296 MB) into `~/.cache/ai-model-routing-evidence/tau2-bench/` on its first run and checks each against its pinned size and sha256. The evaluate step takes well under a second.
