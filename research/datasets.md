# Public datasets with per-item outcomes on coding or agentic tasks (as of 2026-11-06)

Question: is there a public dataset, with a stated licence, that holds every model's or agent's outcome per item on a coding or agentic task checked by a program (unit tests, a database state check), ideally with a per-item cost or token counts? The committed evidence uses two datasets, RouterBench (mostly multiple-choice MMLU subjects) and AutoBench 2026 (graded by a committee of model judges), so no committed result comes from such a task yet.

Method: every revision below is the commit or dataset SHA that the GitHub or Hugging Face API returned on 2026-11-06. Licences are as the repo's LICENSE file, the API's licence field or the dataset card states them ("none stated" if absent). Sizes are the API's file sizes. Sample files were downloaded outside the repo and read with the standard-library `json` module; nothing from them is committed.

Model ids below use the provider-neutral form `provider/name`.

## Summary

- Recommended: the tau2-bench paper results. They are the one candidate found with a stated licence (MIT), a per-item outcome from a program check, and a per-item cost
- Their limits: 4 agent models from 2 providers, all released in 2025, and a model plays the user in every conversation
- LiveCodeBench submissions (MIT, 72 model folders, labels from test cases) have the widest coding pool but no cost or token counts, so they could feed `cost_blind` only
- SWE-bench experiments has the most agents (182 folders for SWE-bench Verified) but no stated licence, so it stays out by the same rule as the two routing datasets at the end

## Candidates

### 1. tau2-bench paper results (recommended)

- URL: https://github.com/sierra-research/tau2-bench, folder `data/tau2/results/final`
- Revision: 033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f (commit date 2026-11-04)
- Licence: MIT (the repo's LICENSE file and the API's licence field)
- Files: 26 run JSON files, 603,837,972 bytes in all; the 12 default runs (4 agent models by 3 domains) are 295,933,742 bytes, from 7,599,444 to 51,038,687 bytes each (also the smallest and largest of the 26)
- Agents: anthropic/claude-3-7-sonnet-20250219, openai/gpt-4.1-2025-04-14, openai/gpt-4.1-mini-2025-04-14 and openai/o4-mini-2025-04-16, all released in 2025. The user simulator is openai/gpt-4.1-2025-04-14 at temperature 0 in every run
- Items: 50 airline tasks, 114 retail and 114 telecom (counted in the o4-mini runs; the claude-3-7-sonnet airline run also has 50), 4 trials per task, so 200, 456 and 456 simulations per run file
- Label: `reward_info.reward`, 0.0 or 1.0 per simulation, from program checks. In airline and retail the reward basis is `DB` and `COMMUNICATE` (the final database state against the expected one, and the values the agent had to tell the user); in telecom it is `ENV_ASSERTION`, plus `ACTION` in 80 of the 456 simulations. No model judge is in the reward basis of the 4 files read
- Cost and tokens: every simulation has `agent_cost` and `user_cost` in USD (200 of 200, 456 of 456 and 456 of 456 in the three o4-mini runs, 200 of 200 in the claude-3-7-sonnet airline run), and the agent's messages carry `usage` with `prompt_tokens` and `completion_tokens`. The files do not say which price table produced `agent_cost`
- Caveat from the folder's README: these are the June 2025 paper results, produced "before the task fixes that shipped in v1.0.0". It goes on: "The airline and retail tasks recorded here therefore differ from the current base tasks, and `tau2 submit` task verification rejects them (airline: 29 tasks differ, retail: 114). Telecom is unchanged and verifies." The runs read have 114 retail tasks, so the README's retail count is the whole retail set. They "are not leaderboard submissions". The leaderboard folder `web/leaderboard/public/submissions` has 88 submission folders (71 with a 2026 date in the name, 12 with 2025, 5 with 2024) beside 7 files at the folder's top level. 77 hold a `submission.json` with pass rates per domain only. The other 11, all dated 2026-10, hold a `benchmark-submission.json` with one reward per (language, domain, task, trial); the one read, ava-zero, is a voice run (mode `voice`; 900 trials, 6 languages by 3 domains, 1 trial each) with no cost or token counts, so these may be a per-item source for 2026 models, but for a voice benchmark and without cost
- Converter: standard-library `json`, so no new dependency under the `evidence` extra. Load one run file at a time (up to 51 MB), keep only (domain, task id, trial, reward, `agent_cost`, summed tokens) and pin each file's sha256. DESIGN 12.1 takes one row per (task, item, model), so either each trial becomes its own item or the converter keeps one trial, and the choice is stated. One routing task per domain gives 4 models by 278 items if one trial is kept, or by 1,112 if each trial is its own item; the converter sizes its committed results file against the about 300 KB cap. None of the four models is in `model_routing/data/models.json`, so the cost is either `agent_cost` as each row's `cost_usd`, or the token counts priced from a dated public price list with `agent_cost` as a cross-check

### 2. LiveCodeBench submissions

- URL: https://github.com/LiveCodeBench/submissions
- Revision: 6ca212e9c2039373f6e5069d37ffa9db66e23736 (commit date 2025-08-01; the repo is archived)
- Licence: MIT (the repo's LICENSE file and the API's licence field). The problems come from LeetCode, AtCoder and Codeforces, so a converter keeps only question ids, dates and labels, never question text or generated code
- Files: 73 JSON files in 72 model folders, 1,353,069,054 bytes in all, from 3,636,170 to 55,720,447 bytes each. Some folders are variants of one model (reasoning effort levels, a 10-sample run, a duplicate folder)
- Models: from openai/gpt-4-0613 (2023) to anthropic/claude-opus-4 and deepseek/deepseek-r1-0528 (2025)
- Items: each file lists its own problems. The o1-mini file has 880 (contest dates 2023-05-07 to 2025-01-04), the claude-opus-4 file 1,055 (2023-05-07 to 2025-04-06; 602 AtCoder, 444 LeetCode, 9 Codeforces), so a converter must intersect question ids or fix a date window
- Label: `graded_list`, one boolean per sample from the problem's test cases, and `pass@1`; file names with `_1_` hold 1 sample per problem, `_10_` hold 10
- Cost and tokens: none. `metadata` holds an execution time per sample, and `output_list` holds the raw output, so only a character count of the output is available
- Converter: standard-library `json`; the full download is 1.35 GB, so read file by file and keep (model, question id, contest date, passes, samples). It could feed `cost_blind` only, unless a dated price list and a token estimate are added and stated as assumptions

### 3. SWE-bench experiments (not taken: no stated licence)

- URL: https://github.com/SWE-bench/experiments
- Revision: 40f164d5b8f1d249bf95a6df8b74b577fd8e519d (commit date 2026-09-03)
- Licence: none stated. The tree has no LICENSE file, the API's licence field is null, and the README has no licence wording
- Files: `evaluation/verified` has 182 submission folders, named with dates from 2023-10-10 to 2026-09-01; 135 have `results/results.json` (1,645,358 bytes in all) and 41 have `per_instance_details.json`
- Agents: one per folder, an agent scaffold with a model, 2023 to 2026
- Label: per instance, the `resolved` list of `results.json` (SWE-bench's test-based check), beside `no_generation` and `no_logs` lists. In the folder dated 2026-09-01 (mini-SWE-agent) 359 instances are resolved and 59 have no generation
- Cost and tokens: that folder's `per_instance_details.json` (441 instances) has `api_calls` and `resolved` only, and its `metadata.yaml` has a mean `instance_calls` of 39.03; neither has a cost or token counts. Trajectories sit in a separate repo per submission and were not checked
- Converter: standard-library `json` on small files. It stays out unless the repo states a licence

## Checked, but no per-item outcomes

- nebius/SWE-rebench-leaderboard (https://huggingface.co/datasets/nebius/SWE-rebench-leaderboard), revision 34d5a58864acf91613740a09ec5d205228dcfa39 (last modified 2026-07-28), licence CC-BY-4.0 in the card: 16 parquet files, 10,296,402 bytes. The card describes the tasks of the SWE-rebench leaderboard, each with a Docker image; no model's outcome is in the dataset
- bigcode/bigcodebench-results (https://huggingface.co/datasets/bigcode/bigcodebench-results), revision 08ceb6b15ecd9c0f7c82932e4e248208ffeeb9b4 (last modified 2025-04-17), licence none stated in the card: one 12,503-byte parquet file of 202 rows, one per model, with aggregate `complete` and `instruct` scores. The per-item material is in the GitHub releases of https://github.com/bigcode-project/bigcodebench (Apache-2.0, archived): release v0.2.5 of 2025-04-11 has 2 zip assets, 167,031,371 bytes: `sanitized_calibrated_samples.zip` (165,188,552) and `deepcoder.zip` (1,842,819). By its name, the first it holds generated samples rather than graded outcomes (not opened), so a converter would have to run each task's tests in a sandbox

## Routing datasets checked earlier, still not taken

- CARROT-LLM-Routing/SPROUT (https://huggingface.co/datasets/CARROT-LLM-Routing/SPROUT), revision d54e3cda2189ca1ed13a877a44ed34736c4b6920 (last modified 2025-02-04): licence none stated in the card data or tags, re-read 2026-11-06
- RouteWorks/RouterArena (https://huggingface.co/datasets/RouteWorks/RouterArena), revision a4a062ce3313b56bb09c042e1bc37b61d34e3bd8 (last modified 2025-12-03): licence none stated in the card data or tags, re-read 2026-11-06
- This repo commits no results derived from a dataset without a stated licence

## Recommendation

- Take the tau2-bench paper results as the third dataset, with a converter under `evidence/tau2-bench/` that pins the revision and each file's sha256, reads the 12 default runs, and commits a results file and a RESULTS.md with the source URL, licence and regenerate command, as the two existing datasets do
- Why it over LiveCodeBench: it is the only candidate with a per-item cost, so it can show `cost_effective` on an agentic task, and its 4 trials per task give 4 samples per (task, model) when each trial becomes its own item (the choice the converter states, above)
- What it does not fix: the four agents are 2025 models, not the current models in `model_routing/data/models.json`; four agents from two providers is a small pool; the user is a model, so a failed conversation can be the simulator's fault; and the airline and retail results describe the June 2025 task sets, not the current ones
- If a coding result checked by tests is wanted next, LiveCodeBench submissions is the candidate, as `cost_blind` evidence only
