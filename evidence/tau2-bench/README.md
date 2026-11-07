# tau2-bench evidence

The tau2-bench paper results record, for 4 agent models in 3 customer-service domains (airline, retail and telecom), every conversation an agent had with a simulated user, whether the run's program checks passed at its end, and what the agent's model calls cost. That is enough to test routing offline with no API key, on an agentic task with a label from a program rather than a judge: `convert.py` turns the results into the outcome matrix that `model-routing evaluate` reads (DESIGN 12.1), one routing task per domain. The converter's full contract is DESIGN 12.14.

The routing results on this matrix are in [RESULTS.md](RESULTS.md), with the file behind them, [results.json](results.json) (DESIGN 12.15).

## Source and licence

- Repo: https://github.com/sierra-research/tau2-bench
- Pinned revision: [`033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f`](https://github.com/sierra-research/tau2-bench/tree/033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f), folder `data/tau2/results/final`
- Licence: MIT, as the repo's LICENSE file states, with the line "Copyright (c) 2025 Sierra Research"
- This repo commits no part of the run files: the converter downloads them into `~/.cache/ai-model-routing-evidence/tau2-bench/`, outside the repo

The converter reads the 12 default run files, 4 agents by 3 domains, 295,933,742 bytes in all. The folder has no checksum file, so the pins in `convert.py` are the only trust root: each file is checked by size and sha256 before it is read, and a cached file that fails is an error, never silently replaced. The folder's other 14 run files (telecom ablations and the `telecom-workflow` domain, for two of the agents) are not read.

| File | Bytes | sha256 |
| --- | --- | --- |
| `claude-3-7-sonnet-20250219_airline_default_gpt-4.1-2025-04-14_4trials.json` | 10,551,448 | `40a2c6a246eab27db5cdefda895fbe7f44be78a23d300817248534aa606d66de` |
| `claude-3-7-sonnet-20250219_retail_default_gpt-4.1-2025-04-14_4trials.json` | 24,908,843 | `ed41dbd18c080154156484e3a0122c095e324a11367a640d88e15956daed7b9d` |
| `claude-3-7-sonnet-20250219_telecom_default_gpt-4.1-2025-04-14_4trials.json` | 41,190,190 | `f49e540896fe91ab8631647f02eb777ef6fed5a6ebec545f43e71d0504e227b2` |
| `gpt-4.1-2025-04-14_airline_default_gpt-4.1-2025-04-14_4trials.json` | 8,790,399 | `31d19e79b8ddc5934a60701f913ff5fefb41dee5e68f7b813c26254ab2e2d5c8` |
| `gpt-4.1-2025-04-14_retail_default_gpt-4.1-2025-04-14_4trials.json` | 22,044,059 | `5fc5b96ada0fe46a463eaed98d1bfed9947fe073bac052290162dae18d71394e` |
| `gpt-4.1-2025-04-14_telecom_default_gpt-4.1-2025-04-14_4trials.json` | 37,463,627 | `8e1793f57a9e216514dbce1f93b44b0592d5904f1c5b97ab711906782107a1f2` |
| `gpt-4.1-mini-2025-04-14_airline_base_gpt-4.1-2025-04-14_4trials.json` | 9,781,836 | `41788956547a100fb8e34baf159f36dd1f07f0765798a5fdaf917576c5dba9d0` |
| `gpt-4.1-mini-2025-04-14_retail_base_gpt-4.1-2025-04-14_4trials.json` | 23,697,012 | `6d6badb43b716adca31591b0b40e15fd493b49adddaa8e2c47035bb557549257` |
| `gpt-4.1-mini-2025-04-14_telecom_base_gpt-4.1-2025-04-14_4trials.json` | 51,038,687 | `04fad1a6fb3ff8804be31c54cf5a993b64868e37683c226e014e7adbf60841d9` |
| `o4-mini-2025-04-16_airline_default_gpt-4.1-2025-04-14_4trials.json` | 7,599,444 | `6a3a354c9bce42b52905af096e9cea6f555548acbb17b567fd403c356df7b4ec` |
| `o4-mini-2025-04-16_retail_default_gpt-4.1-2025-04-14_4trials.json` | 22,066,527 | `7135f38bbbbd46d6babe830574c8623bb276d8fd6da316580b905cf513853f98` |
| `o4-mini-2025-04-16_telecom_default_gpt-4.1-2025-04-14_4trials.json` | 36,801,670 | `1f46a6f296694bdb3ae203e6b379cdada0b8f17b648a4cf90d6343de1f1fb070` |

## What counts as a success, and as the cost

- A conversation is a success when its `reward_info.reward` is 1 and a failure when it is 0, the result of the run's program checks (in airline and retail the final database state and the values the agent had to tell the user; in telecom assertions on the environment, plus the agent's actions in some conversations). A partial reward is refused, never rounded
- A row's cost is the run's recorded `agent_cost` in USD, the agent model's calls in that conversation. `user_cost`, the simulated user's calls, is never counted: it is the benchmark's cost, not the routed call's. The files do not say which price table produced `agent_cost`
- One trial per task: each run file holds 4 trials of every task, and keeping each trial as its own item would let the split into calibration and held-out halves put trials of one task in both. So trial 0 is kept by default, and `--trial 1` to `--trial 3` are a sensitivity check. Trial t ran with the same seed for every agent
- Model IDs come from a rule over the run's model name: `claude-` becomes `anthropic/`, and `gpt-` or `o` followed by a digit becomes `openai/`. A name that contains `/` or that no rule covers is an error, not a guess
- A task that some agent lacks at the kept trial is dropped and counted, never scored as a failure

## Regenerate the matrix

```bash
python -m pip install -e .
python evidence/tau2-bench/convert.py --out tau2-matrix.jsonl
model-routing evaluate --outcomes tau2-matrix.jsonl --bar 0.6
```

`--task-by all` makes one task of all 278 items, `--tokens` adds each row's `input_tokens` and `output_tokens` (summed over the agent's messages; user and tool messages are not counted), and `--cache DIR` downloads somewhere other than the default folder. No extra is needed: the converter is standard library only. It prints a JSON report of what it kept and dropped.

With the default options on the pinned files the converter reports 4 agent models and the user model `openai/gpt-4.1-2025-04-14`, keeps 50 airline, 114 retail and 114 telecom tasks, drops none and writes 1,112 rows, with the same counts at every trial from 0 to 3. At trial 0 the agents' success rates per domain run from 0.5 to 0.58 in airline, 0.684 to 0.798 in retail and 0.368 to 0.439 in telecom, and `cost_usd` runs from 0.00136 to 6.446604 USD. With `--tokens`, one conversation's agent calls used 6,629 to 2,096,093 input tokens and 123 to 26,531 output tokens.

With `--calls`, which implies `--tokens`, each row also lists its conversation's agent calls in order, every call's new input (`call_input_tokens`: the first prompt, then each prompt less the previous prompt and completion) and output (`call_output_tokens`), the per-call rows of DESIGN 13.9; at trial 0 it leaves out `openai/o4-mini-2025-04-16`, whose new input is negative on 2,962 of its calls, and keeps 3 agents and 834 rows of 2 to 100 calls each (median 14).

Airline has only 50 tasks, and the evaluator draws each item's half from a hash of its ID, so the airline calibration half holds 16 to 35 items over the seeds 0 to 49, fewer than the default `min_samples` of 30 on 40 of them, and on those seeds no model can clear a bar in airline at that default. `--task-by all` pools the three domains into one task whose calibration half holds 114 to 158 items over those seeds.

## Reading it

- The 4 agents date from 2025, and the costs are those the runs recorded at the prices of their time
- The airline and retail tasks are the June 2025 task sets, which the folder's README says differ from the current base tasks ("airline: 29 tasks differ, retail: 114"); telecom is unchanged
- A model, `openai/gpt-4.1-2025-04-14`, plays the user in every conversation, so a reward is the agent's success with that simulated user, and a failed conversation can be the simulator's fault
- 36 of the 4,448 conversations in the 12 files ended at the step limit rather than when the user stopped, and their reward is used as recorded
