# Longtail-SWE results

What `model-routing evaluate` measures on nebius/Longtail-SWE-trajectories, a public release of coding-agent runs on issues of open-source repositories: `anthropic/claude-opus-5.5`, `openai/gpt-5.6-luna`, `openai/gpt-5.6-sol` and `openai/gpt-6.1-sol`, each run by the release's `swelike` scaffold on the same 194 issues in 13 languages, as one routing task, `issue_resolution`. A success is a run whose saved evaluation marks the issue `resolved` by the task's own tests, at run 0 of the release's three runs per issue and model, and the cost of a run is its input and output tokens at the registry's list prices with no cache discount, an estimate and not a bill (DESIGN 12.25). See [README.md](README.md) for what the converter reads and keeps, and DESIGN 12.26 for this file's contract. For each of 50 seeds the 194 issues are split in half by a seeded hash; the router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best model on the calibration half, the cheapest model and each single model (DESIGN 12.3). The file behind every number here is [results.json](results.json): the summary rows and the routed per-task rows, including how many of the 50 seeds routed to each model. It is made by the RouterBench results script, `evidence/routerbench/results.py`, which does not depend on the dataset.

The bars are 0.6, 0.7, 0.8 and 0.9, the bars of the RouterBench results. On the pool of 194 issues the models resolve from 140 (`openai/gpt-5.6-luna`, 0.722) to 162 (`anthropic/claude-opus-5.5`, 0.835), so every tenth strictly inside that span would give only 0.8 (DESIGN 12.26), too few bars to show a trade of success for cost as the bar moves. The others are kept, 0.6 and 0.7 under every model's rate on the pool and 0.9 above it, and since a model clears on its calibration bound, not its rate, they give different rows.

## Source and licence

- Dataset: https://huggingface.co/datasets/nebius/Longtail-SWE-trajectories, published by Nebius, pinned revision [`dfd6075c56b7841b9c254cc70a57e39c1df0076c`](https://huggingface.co/datasets/nebius/Longtail-SWE-trajectories/tree/dfd6075c56b7841b9c254cc70a57e39c1df0076c) (last modified 2026-11-16), of which the converter reads four files, one per registry model:
  - `data/swelike__claude-opus-5.5-high.parquet`, 36,213,846 bytes, sha256 `45b9323ae1b33c7301e60a266594202e6f6684de4386c9d50356783b113bea91`
  - `data/swelike__gpt-5.6-luna-xhigh.parquet`, 94,695,456 bytes, sha256 `144ac5b635135d0df37eae6edf2d40148e58f8832d8d59b492a865a98dd99093`
  - `data/swelike__gpt-5.6-sol-high.parquet`, 56,147,793 bytes, sha256 `af2e3bcaf8625d131d467cb4a55164fd63f561d7ee6125db6217cfe603511b57`
  - `data/swelike__gpt-6.1-sol-high.parquet`, 49,548,306 bytes, sha256 `52441cc627aa6688150be052044549b0fe6b2e1215f676a254602919f4bc2fff`
- Licence: the dataset card at the pinned revision (5,537 bytes, sha256 `5c6bc2f63f280f468c8551c712b4193ea1cb85e7b3f09df34499c37b72454c2d`, read on 2026-11-18) has `license: cc-by-4.0`, and its License section says: "The dataset compilation is licensed under CC BY 4.0. Source repositories retain their own licenses, and model and tool outputs may be subject to provider terms." It points to [LEGAL.md](https://huggingface.co/datasets/nebius/Longtail-SWE-trajectories/blob/dfd6075c56b7841b9c254cc70a57e39c1df0076c/LEGAL.md) (3,853 bytes, sha256 `818eae55bd8d9ec60e743b870bad10437ee9f56484d03f6e0896f868ee9240a3`, read on 2026-11-18), a notice that says it is not legal advice; the second paragraph of each of its sections 1, 2 and 3, on the licence's scope, source-repository material and third-party model outputs, each joined onto one line, says:
  - "This license applies to the dataset compilation and to original material authored by Nebius. It does **not** override or extend to the rights in third-party material referenced or included within the dataset, which remain governed by their own respective terms (see Sections 2 and 3)."
  - "Material originating from a source repository (including code, issue text, diffs, and patches that appear within trajectories) continues to be governed by that repository's license. Users who reuse, modify, or redistribute such material are responsible for identifying and complying with the applicable upstream license for each instance."
  - "These generated outputs may be subject to the **usage terms, license agreements, acceptable-use policies, and output-ownership or redistribution provisions** of the respective model providers. Such terms vary between providers and may change over time. Nebius makes **no representation or warranty** as to the licensing status, ownership, or permitted uses of any third-party model output contained in this dataset."
- LEGAL.md's section 3 also asks (paraphrased, not quoted) that anyone using the dataset, above all to train, fine-tune, evaluate or redistribute, first check and follow the terms of each model or tool whose output the dataset may hold
- Attribution, as CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) asks: these results derive from Longtail-SWE Trajectories by Nebius, nebius/Longtail-SWE-trajectories at revision `dfd6075c56b7841b9c254cc70a57e39c1df0076c`, licensed under CC BY 4.0. Changes made: the converter reads, per run of the four registry models at run 0, only the issue ID, its language, the `resolved` label and the token counts, drops the issues whose initial statement changed and writes one row per issue and model with the label and the tokens priced at the registry's list prices (DESIGN 12.25), and `model-routing evaluate` turns that matrix into the numbers below. The card asks to cite the paper [Longtail-SWE: High-Quality SWE Tasks for Underrepresented Languages](https://arxiv.org/abs/2611.10304)
- This repo commits no part of the dataset: [results.json](results.json) holds only pooled numbers and per-seed model counts, and the converter keeps no prompt, message, tool call, patch or trajectory text of the release (see [README.md](README.md)), so none of the source-repository material or third-party model output that LEGAL.md names is redistributed here

## Results

Routed rows: `success` is the share of held-out issues whose run is `resolved`, `cost_usd` is the estimated cost of those runs (both averaged over the 50 seeds), `vs_best_model` is that cost divided by the cost of the best single model (`anthropic/claude-opus-5.5`), `cleared_rate` is the share of the 50 (task, seed) cells where some model cleared the bar on the calibration half, and `bar_violation_rate` is the share of cleared cells whose held-out success fell below the bar, `-` where no cell cleared. Baseline rows do not depend on the bar or the flavor.

```text
$ python evidence/routerbench/results.py --table evidence/longtail-swe/results.json
bar  flavor          success  cost_usd   vs_best_model  cleared_rate  bar_violation_rate
---  --------------  -------  ---------  -------------  ------------  ------------------
0.6  cost_effective  0.740    278.7232   0.160          1.000         0.000
0.6  cost_blind      0.832    1705.8157  0.977          1.000         0.000
0.7  cost_effective  0.805    1005.6813  0.576          0.940         0.021
0.7  cost_blind      0.832    1705.8157  0.977          0.940         0.000
0.8  cost_effective  0.823    1541.0533  0.883          0.080         1.000
0.8  cost_blind      0.832    1705.8157  0.977          0.080         1.000
0.9  cost_effective  0.823    1541.0533  0.883          0.000         -
0.9  cost_blind      0.832    1705.8157  0.977          0.000         -

strategy                         success  cost_usd
-------------------------------  -------  ---------
oracle                           0.953    379.5033
best_on_calibration              0.823    1541.0533
cheapest                         0.726    252.5743
model:anthropic/claude-opus-5.5  0.837    1745.3069
model:openai/gpt-5.6-luna        0.726    252.5743
model:openai/gpt-5.6-sol         0.787    1143.6247
model:openai/gpt-6.1-sol         0.804    357.4990
```

Routed rows beat these single models on both counts: `openai/gpt-5.6-sol` (by bar 0.7 `cost_effective`).

## Reading it

- `cost_effective`: at bar 0.6 a model clears on 50 of the 50 seeds, and the router spends 0.160 of the cost of the best single model, `anthropic/claude-opus-5.5`, for a held-out success of 0.740, against 0.837 for that model. Always calling the cheapest model, `openai/gpt-5.6-luna`, reaches 0.726 at 252.5743 USD, so at bar 0.6 the router pays 1.104 of that cost for more held-out success, routing 38 seeds to `openai/gpt-5.6-luna` and 12 seeds to `openai/gpt-6.1-sol`
- At the higher bars `cost_effective` reaches 0.805 at 0.576 of the best single model's cost at bar 0.7, 47 seeds cleared; 0.823 at 0.883 of the best single model's cost at bar 0.8, 4 seeds cleared; 0.823 at 0.883 of the best single model's cost at bar 0.9, 0 seeds cleared; a seed on which no model clears falls back to the model with the highest Wilson lower bound on its calibration half (`on_no_model="best_available"`, DESIGN 5.3)
- `cost_blind` reaches 0.832 at 0.977 of the best single model's cost at every bar, 0.0044 below that model's held-out success, routing 48 seeds to `anthropic/claude-opus-5.5`, 1 seed to `openai/gpt-5.6-sol` and 1 seed to `openai/gpt-6.1-sol` at every bar, 0.0089 above `best_on_calibration`'s 0.823: on seeds where two models tie on the calibration count, `best_on_calibration` takes the cheaper one and `cost_blind` the lower model ID (DESIGN 12.26)
- Bar violations: 0.021 at bar 0.7 (`cost_effective`) is 1 of 47 cleared cells; 1.000 at bar 0.8 (`cost_effective`) is 4 of 4 cleared cells; 1.000 at bar 0.8 (`cost_blind`) is 4 of 4 cleared cells, against a nominal one-sided 0.025 for the 0.95 Wilson bound (DESIGN 12.3)
- Complementary halves: with one task, each seed's two halves split one pool of 194 issues, so a model's held-out count is its count on the pool less its calibration count. At bar 0.8 every cleared cell is under the bar in both flavors, 4 of 4 cells, though `anthropic/claude-opus-5.5` resolves 162 of the 194 issues (0.835) on the pool: a calibration half lucky enough to clear leaves an unlucky held-out half, the re-split correlation that DESIGN 12.3 names, and DESIGN 12.26 gives the seeds and their counts
- `openai/gpt-6.1-sol` alone reaches 0.804 at 0.205 of the best single model's cost, while the first routed `cost_effective` row at or above that success, at bar 0.7, reaches 0.805 at 0.576: 0.0014 more held-out success for 2.813 times that model's cost
- The per-item oracle reaches 0.953 at 0.217 of the best single model's cost, while the highest routed success of either flavor at any bar is 0.832: with one task, each seed's router sends every held-out issue to one model, so it cannot pick per issue
- Each cost is a run's input tokens, cached ones included, at the model's input price and its output tokens, reasoning included, at its output price, with no cache discount (DESIGN 12.25): an estimate at list prices and not a bill, since the vendors' cache rates, which the registry does not hold, would lower it wherever cache reads outweigh a cache-write premium. The prices are `anthropic/claude-opus-5.5` 4 and 20, `openai/gpt-5.6-luna` 0.2 and 1.2, `openai/gpt-5.6-sol` 4 and 20 and `openai/gpt-6.1-sol` 2 and 10 USD per million input and output tokens in `models.json`
- One task of 194 issues in 13 languages at run 0 alone, of the release's three runs per issue and model (DESIGN 12.26 leaves runs 1 and 2 out of this file); the 8 issues whose initial statement differs from the release's are dropped for every model, and the 1 run with no saved result (`openai/gpt-6.1-sol` on `babashka__cli-162`) counts as a miss with its charge (DESIGN 12.25)
- Size: the committed file, 21,500 bytes, holds only the summary and the routed per-task rows (DESIGN 12.7)

## Regenerate

```bash
python -m pip install -e ".[evidence]"
python evidence/longtail-swe/convert.py --out longtail-swe-matrix.jsonl
model-routing evaluate --outcomes longtail-swe-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json > longtail-swe-evaluate.json
python evidence/routerbench/results.py --evaluate longtail-swe-evaluate.json --out evidence/longtail-swe/results.json
python evidence/routerbench/results.py --table evidence/longtail-swe/results.json
```

The converter downloads the four pinned files (236,605,401 bytes) into `~/.cache/ai-model-routing-evidence/longtail-swe/` on its first run and checks each against its pinned size and sha256; the `evidence` extra installs `pyarrow`, the parquet reader it needs, and converting the cached files takes about 4 seconds. The `evidence` workflow reruns these commands on GitHub and fails if `results.json` changes by a byte (`DESIGN.md` 12.13, v1.489), while the test suite rebuilds `results.json` only where `pyarrow` is installed and the four files are cached.
