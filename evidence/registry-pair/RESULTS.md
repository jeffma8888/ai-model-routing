# Registry-pair results

What `model-routing evaluate` measures on superlinked/train-a-router-reasoning, the public release whose two models and their prices are the registry's own: `openai/gpt-6-luna` and `openai/gpt-6.1-sol`, each graded on the same 6,099 questions of MMLU-Pro, BIG-Bench Hard and KOR-Bench, as 31 routing tasks, one per (dataset, task) pair (14 `bbh`, 3 `korbench` and 14 `mmlupro` tasks), a success when the release's strict declared-label equality marks the answer right, and the release's estimated cost of the call, from its token counts at the registry's list prices, as its cost. See [README.md](README.md) for what the converter reads and keeps, and DESIGN 12.24 for this file's contract. For each of 50 seeds the items of each task are split in half by a seeded hash; the router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best model on the calibration half, the cheapest model and each single model (DESIGN 12.3). The file behind every number here is [results.json](results.json): the summary rows and the routed per-task rows, including how many of the 50 seeds routed to each model. It is made by the RouterBench results script, `evidence/routerbench/results.py`, which does not depend on the dataset.

The bars are 0.6, 0.7, 0.8 and 0.9, the bars of the RouterBench results. Every tenth strictly inside the span of the per-task, per-model success rates, which runs from 0.710 (`openai/gpt-6-luna` on `mmlupro/law`, 304 of 428) to 1.000 (18 (task, model) pairs on 12 `bbh` tasks), would give only 0.8 and 0.9 (DESIGN 12.24). The two lower bars are kept so that each row has a counterpart in the family-held check below, and since a task clears on its calibration bound, not its rate, they still give different rows.

## Source and licence

- Dataset: https://huggingface.co/datasets/superlinked/train-a-router-reasoning, pinned revision [`63336f25fc54597a8e161a7245613f91bd60177e`](https://huggingface.co/datasets/superlinked/train-a-router-reasoning/tree/63336f25fc54597a8e161a7245613f91bd60177e) (last modified 2026-10-21), of which the converter reads three files:
  - `pair.json`, 2,473 bytes, sha256 `4b4cc5f936fe8a8018b6845bfa9bd29b7d18ec428489d15ebab62554c4cd11b4`
  - `recordings/grades-calibration.json`, 3,777,170 bytes, sha256 `2f47b9df61b131879f30b4ea36693a8ce8bc43e46afd17d7fbd5d7a93922e8ac`
  - `recordings/grades-final.json`, 3,742,778 bytes, sha256 `8d66442ad94b5e846a856084adfaba7a2915bab6253008e93ed44348dc264a5f`
- Licence: the dataset card at the pinned revision (4,824 bytes, sha256 `8d707ef4ee5bf8b272335e4561294628fc0072c2122bf3ded4c3cb349ecad0eb`, read on 2026-11-16) names no single licence: its metadata reads `license: other` and `license_name: mixed-mit-and-apache-2.0`, and its Licenses section, with each paragraph joined onto one line, says:
  - "This is a collection with multiple upstream licenses, not a relicensing of its components. Preserve the included notices when redistributing them."
  - its table of components, each row as component: upstream and license:
    - MMLU-Pro questions: [TIGER-Lab/MMLU-Pro](https://huggingface.co/datasets/TIGER-Lab/MMLU-Pro), MIT
    - BIG-Bench Hard questions: [suzgunmirac/BIG-Bench-Hard](https://github.com/suzgunmirac/BIG-Bench-Hard), MIT
    - KOR-Bench questions: [KOR-Bench/KOR-Bench](https://github.com/KOR-Bench/KOR-Bench), Apache-2.0
    - Laya original and adapted weights: [convaiinnovations/laya](https://huggingface.co/convaiinnovations/laya), Apache-2.0
    - Example code and study-specific metadata: [superlinked/sie](https://github.com/superlinked/sie), Apache-2.0
  - "Exact source notices and revisions are included under `source/notices/` and `source/source-plan.json`. Please cite the upstream benchmarks and Laya when using these artifacts in research, and identify the immutable artifact revision used for a reported reproduction."
- Attribution, as the card asks: these results derive from superlinked/train-a-router-reasoning at revision `63336f25fc54597a8e161a7245613f91bd60177e`; its questions come from the upstream benchmarks MMLU-Pro (TIGER-Lab/MMLU-Pro), BIG-Bench Hard (suzgunmirac/BIG-Bench-Hard) and KOR-Bench (KOR-Bench/KOR-Bench), and the card also asks to cite Laya (convaiinnovations/laya)
- This repo commits no part of the dataset: [results.json](results.json) holds only per-task and pooled numbers, and the converter keeps no question, answer or row of the release (see [README.md](README.md)), so none of the components named above is redistributed here

## Results

Routed rows: `success` is the share of held-out items whose answer the release marks right, pooled over the 31 tasks, `cost_usd` is the estimated cost of those calls (both averaged over the 50 seeds), `vs_best_model` is that cost divided by the cost of the best single model (`openai/gpt-6.1-sol`), `cleared_rate` is the share of the 1,550 (task, seed) cells where some model cleared the bar on the calibration half, and `bar_violation_rate` is the share of cleared cells whose held-out success fell below the bar. Baseline rows do not depend on the bar or the flavor.

```text
$ python evidence/routerbench/results.py --table evidence/registry-pair/results.json
bar  flavor          success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate
---  --------------  -------  --------  -------------  ------------  ------------------
0.6  cost_effective  0.885    0.4882    0.114          0.967         0.000
0.6  cost_blind      0.918    3.8351    0.897          0.967         0.000
0.7  cost_effective  0.892    0.9864    0.231          0.957         0.001
0.7  cost_blind      0.918    3.8351    0.897          0.957         0.000
0.8  cost_effective  0.906    2.2621    0.529          0.840         0.014
0.8  cost_blind      0.918    3.8351    0.897          0.840         0.002
0.9  cost_effective  0.917    3.5815    0.838          0.493         0.007
0.9  cost_blind      0.918    3.8351    0.897          0.493         0.004

strategy                  success  cost_usd
------------------------  -------  --------
oracle                    0.933    0.8420
best_on_calibration       0.918    3.8351
cheapest                  0.884    0.4632
model:openai/gpt-6-luna   0.884    0.4632
model:openai/gpt-6.1-sol  0.921    4.2761
```

No routed row beats any of the 2 single models on both counts: against each of them, every routed row in the table has lower held-out success or a higher cost.

## Reading it

- `cost_effective`: at bar 0.6 a model clears on 1,499 of the 1,550 (task, seed) cells, and the router spends 0.114 of the cost of the best single model, `openai/gpt-6.1-sol`, for a held-out success of 0.885, against 0.921 for that model. Always calling the cheapest model, `openai/gpt-6-luna`, reaches 0.884 at 0.4632 USD, so at bar 0.6 the router pays 1.054 of that cost for more held-out success
- At the higher bars `cost_effective` reaches 0.892 at 0.231 of the best single model's cost at bar 0.7, 1,483 cells cleared; 0.906 at 0.529 of the best single model's cost at bar 0.8, 1,302 cells cleared; 0.917 at 0.838 of the best single model's cost at bar 0.9, 764 cells cleared
- `cost_blind` reaches 0.918 at 0.897 of the best single model's cost at every bar, the held-out success and cost of `best_on_calibration`, 0.0027 below that model's held-out success; at bar 0.6 it routes every seed of 6 of the 31 tasks to `openai/gpt-6-luna`
- Bar violations: 0.001 at bar 0.7 (`cost_effective`) is 2 of 1,483 cleared cells; 0.014 at bar 0.8 (`cost_effective`) is 18 of 1,302 cleared cells; 0.007 at bar 0.9 (`cost_effective`) is 5 of 764 cleared cells; 0.002 at bar 0.8 (`cost_blind`) is 2 of 1,302 cleared cells; 0.004 at bar 0.9 (`cost_blind`) is 3 of 764 cleared cells, against a nominal one-sided 0.025 for the 0.95 Wilson bound (DESIGN 12.3)
- The per-item oracle reaches 0.933 at 0.197 of the best single model's cost, while the highest routed success of either flavor at any bar is 0.918: routing per task, not per question, cannot pick per item
- `korbench/logic` (20 items) never clears: its calibration half is under `min_samples` 30 on every seed (DESIGN 12.24), so the router falls back to the model with the higher Wilson lower bound on that half (`on_no_model="best_available"`, DESIGN 5.3), `openai/gpt-6-luna` on 31 seeds and `openai/gpt-6.1-sol` on 19, the same counts at every bar in both flavors
- Each cost is the release's estimate from the call's token counts at the list prices its `pair.json` names, which the converter checks are the registry's (DESIGN 12.23): `openai/gpt-6-luna` 0.1 and 0.5, `openai/gpt-6.1-sol` 2 and 10 USD per million input and output tokens in `models.json`
- Two models from one vendor, so each task has one choice, the cheaper or the stronger; `mmlupro` holds 4,629 of the 6,099 items in 14 tasks, so the pooled rows mostly measure it
- Size: the committed file, 109,164 bytes, holds only the summary and the routed per-task rows (DESIGN 12.7)

## Family-held check

The release keeps each family of related questions in one split, and the seeded halves of [results.json](results.json) do not: 808 of the 6,099 items are in the 276 families of two or more, so a question can be scored while a relative of it calibrates (DESIGN 12.23). [research/registry-pair.md](../../research/registry-pair.md) runs the same bars, `min_samples` 30 and confidence 0.95 on the release's own split, its 3,056 calibration questions calibrating and its 3,043 final ones scoring, one split in place of 50 seeded halves. Its costs are sums over the final split, so only shares of `openai/gpt-6.1-sol`'s cost compare, and a committed `cleared_rate` is a share of 1,550 (task, seed) cells, not of 31 tasks:

- alone: `openai/gpt-6-luna` 0.886 on the final split, 0.884 in the committed means; `openai/gpt-6.1-sol` 0.926 on the final split, 0.921 in the committed means
- bar 0.6, `cost_effective`: release split 0.886 at 0.112 of `openai/gpt-6.1-sol`'s cost, 30 of 31 tasks cleared, 0 of them below the bar on the final split; committed means 0.885 at 0.114, cleared_rate 0.967, bar_violation_rate 0.000
- bar 0.7, `cost_effective`: release split 0.898 at 0.240 of `openai/gpt-6.1-sol`'s cost, 28 of 31 tasks cleared, 0 of them below the bar on the final split; committed means 0.892 at 0.231, cleared_rate 0.957, bar_violation_rate 0.001
- bar 0.8, `cost_effective`: release split 0.912 at 0.487 of `openai/gpt-6.1-sol`'s cost, 25 of 31 tasks cleared, 0 of them below the bar on the final split; committed means 0.906 at 0.529, cleared_rate 0.840, bar_violation_rate 0.014
- bar 0.9, `cost_effective`: release split 0.920 at 0.798 of `openai/gpt-6.1-sol`'s cost, 15 of 31 tasks cleared, 0 of them below the bar on the final split; committed means 0.917 at 0.838, cleared_rate 0.493, bar_violation_rate 0.007
- bar 0.6, `cost_blind`: release split 0.922 at 0.864 of `openai/gpt-6.1-sol`'s cost, 30 of 31 tasks cleared, 0 of them below the bar on the final split; committed means 0.918 at 0.897, cleared_rate 0.967, bar_violation_rate 0.000
- bar 0.7, `cost_blind`: release split 0.922 at 0.864 of `openai/gpt-6.1-sol`'s cost, 28 of 31 tasks cleared, 0 of them below the bar on the final split; committed means 0.918 at 0.897, cleared_rate 0.957, bar_violation_rate 0.000
- bar 0.8, `cost_blind`: release split 0.922 at 0.864 of `openai/gpt-6.1-sol`'s cost, 25 of 31 tasks cleared, 0 of them below the bar on the final split; committed means 0.918 at 0.897, cleared_rate 0.840, bar_violation_rate 0.002
- bar 0.9, `cost_blind`: release split 0.922 at 0.864 of `openai/gpt-6.1-sol`'s cost, 15 of 31 tasks cleared, 0 of them below the bar on the final split; committed means 0.918 at 0.897, cleared_rate 0.493, bar_violation_rate 0.004

On all 8 rows the committed routed success is below the release split's, by 0.001 to 0.006, and so is each model's alone. The two readings score different questions, so each gap mixes how hard the final split is with what the halves do: this check cannot isolate an effect of related questions in both seeded halves, and shows only that no committed row is above its release-split counterpart. No cleared task fell below its bar on the final split, and the committed bar-violation rates are at most 0.014, under the nominal one-sided 0.025.

## Regenerate

```bash
python -m pip install -e .
python evidence/registry-pair/convert.py --out registry-pair-matrix.jsonl
model-routing evaluate --outcomes registry-pair-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json > registry-pair-evaluate.json
python evidence/routerbench/results.py --evaluate registry-pair-evaluate.json --out evidence/registry-pair/results.json
python evidence/routerbench/results.py --table evidence/registry-pair/results.json
```

The converter downloads the three pinned files (7,522,421 bytes) into `~/.cache/ai-model-routing-evidence/registry-pair/` on its first run, the folder `research/registry_pair.py` also reads, and checks each against its pinned size and sha256; converting them takes under a second once they are cached. The `evidence` workflow reruns these commands on GitHub and fails if `results.json` changes by a byte (DESIGN.md 12.13, v1.443).
