# AutoBench Router Benchmark 2026 results

What `model-routing evaluate` measures on the public AutoBench Router Benchmark 2026 matrix: 20 models from 2026, 203 open-ended questions on which every one of them was scored, the billed cost of every call, and a success label from the dataset's own Delta-Hit rule at the converter's default width, the dataset's `delta_signal` of 0.2007 (see [README.md](README.md)). The questions are pooled into one task, `all` (`--task-by all`), so the evaluator's default `min_samples = 30` can be met. For each of 50 seeds the questions are split in half by a seeded hash; the router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best model on the calibration half, the cheapest model and every single model (DESIGN 12.3). The file behind every number here but those of `## Slices` is [results.json](results.json): the summary rows and the routed per-task rows, including how many of the 50 seeds routed to each model. It is made by the RouterBench results script, `evidence/routerbench/results.py`, which does not depend on the dataset.

## Results

Routed rows: `success` is the share of held-out questions with a Delta-Hit, `cost_usd` is the billed cost of answering them (both averaged over the 50 seeds), `vs_best_model` is that cost divided by the cost of the best single model (`openai/gpt-5.6-sol`), `cleared_rate` is the share of seeds where some model cleared the bar on the calibration half, and `bar_violation_rate` is the share of cleared seeds whose held-out success fell below the bar. Baseline rows do not depend on the bar or the flavor.

```text
$ python evidence/routerbench/results.py --table evidence/autobench-2026/results.json
bar  flavor          success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate
---  --------------  -------  --------  -------------  ------------  ------------------
0.6  cost_effective  0.720    0.1976    0.036          1.000         0.000
0.6  cost_blind      0.857    3.6917    0.664          1.000         0.000
0.7  cost_effective  0.854    0.3110    0.056          1.000         0.020
0.7  cost_blind      0.857    3.6917    0.664          1.000         0.000
0.8  cost_effective  0.855    2.9694    0.534          0.660         0.030
0.8  cost_blind      0.857    3.6917    0.664          0.660         0.000
0.9  cost_effective  0.858    3.6535    0.657          0.000         -
0.9  cost_blind      0.857    3.6917    0.664          0.000         -

strategy                                 success  cost_usd
---------------------------------------  -------  --------
oracle                                   1.000    0.0836
best_on_calibration                      0.858    3.6535
cheapest                                 0.453    0.0191
model:anthropic/claude-sonnet-5          0.859    2.5573
model:deepseek/deepseek-v4-flash-0731    0.681    0.0344
model:google/gemini-3.7-flash            0.774    0.7354
model:google/gemma-4-31b-it              0.489    0.0193
model:meta/muse-glimmer-30b              0.554    0.0875
model:meta/muse-spark-1.2                0.705    0.8598
model:minimax/minimax-m3                 0.769    0.3250
model:moonshotai/kimi-k2.6               0.776    1.1534
model:nvidia/nemotron-3-ultra-550b-a55b  0.603    0.3980
model:nvidia/nemotron-3.5-lightning      0.415    0.0907
model:openai/gpt-5.6-luna                0.872    0.3092
model:openai/gpt-5.6-sol                 0.882    5.5616
model:openai/gpt-oss-120b                0.442    0.0184
model:qwen/qwen3.5-9b                    0.276    0.0977
model:qwen/qwen3.8-max                   0.853    1.1341
model:tencent/hy3                        0.683    0.0706
model:xai/grok-4.3                       0.558    0.3676
model:xai/grok-4.6                       0.689    1.2245
model:zai/glm-5.2                        0.756    0.2971
model:zai/glm-5.3                        0.755    0.4042
```

## Next to the dataset's headline

The dataset card, at the pinned revision, states: "Headline finding: no commercial pass beats always calling GPT-5.6 Luna on quality and cost together." On how it graded routers, the card says: "Seven routers were then graded by lookup: a router only names a model; we read that cell", and it describes `scoreboard.json` as "The published board", with "28 passes". This router was not one of them, and it routes one pooled task rather than each prompt.

On the same matrix no routed row beats it on both counts: always calling `openai/gpt-5.6-luna` reaches held-out success 0.872 at 0.3092 USD, and every routed row in the table has lower held-out success or a higher cost.

The closest row is `cost_effective` at bar 0.7: it routes 45 of the 50 seeds to `openai/gpt-5.6-luna`, and the other seeds to weaker models that cleared the bar on their calibration half, so it ends a little below that model on success and a little above it on cost. On this matrix, calibrating on half the questions and routing at a bar finds that model, but does not beat calling it every time.

## Reading it

- `cost_effective` buys the cheapest model that clears the bar, not the best answer. At bar 0.6 every seed clears and it spends 0.036 of the best single model's cost for a held-out success of 0.720 against that model's 0.882. At 0.8 a model clears on 33 of the 50 seeds; on the rest the router falls back to the model with the highest lower bound, and the cost rises to 0.534 of the best single model. At 0.9 no model's lower bound on a calibration half of 77 to 120 questions reaches the bar (the best single model's held-out success is 0.882), so no seed clears and the router falls back on every one
- `cost_blind` routes to the model with the highest lower bound: success 0.857 at 0.664 of the best single model's cost at every bar, close to `best_on_calibration` (0.858 at 0.657) but not the same choice on every seed
- There is one task, so each rate counts seeds: the `cost_effective` bar-violation rate of 0.020 at bar 0.7 is 1 of the 50 seeds that cleared, and 0.030 at bar 0.8 is 1 of the 33 seeds that cleared. Read it next to a nominal one-sided 0.025 for a 95% Wilson bound on one model, as a resampling estimate for this matrix and never as a guarantee (DESIGN 12.3, "Reading the numbers")
- The oracle's 1.000 holds by construction: on every question the top-scoring model is within the width of the mean of the best three, so some model always has a Delta-Hit. Its cost, the cheapest model with a hit on each question, is a hindsight bound that routing one pooled task cannot approach

## Sensitivity

Official width. With `--width 0.3011090610836323`, the dataset's `delta_official`, more answers count as hits. At bar 0.8 with 50 seeds:

- `openai/gpt-5.6-luna` alone: held-out success 0.897 at 0.3092 USD
- bar 0.8, `cost_effective`: routed success 0.866 at 0.5440 USD, cleared_rate 1.000, bar_violation_rate 0.080
- bar 0.8, `cost_blind`: routed success 0.933 at 4.8254 USD, cleared_rate 1.000, bar_violation_rate 0.000

Per domain. The default `--task-by domain` gives 10 tasks of 12 to 33 questions, so a calibration half holds from 1 to 25 questions over the 500 (domain, seed) splits, and at the default `min_samples = 30` no seed clears. At `--min-samples 5`, with 50 seeds:

- `openai/gpt-5.6-luna` alone: held-out success 0.872 at 0.3092 USD
- bar 0.6, `cost_effective`: routed success 0.849 at 0.4132 USD, cleared_rate 0.796, bar_violation_rate 0.075
- bar 0.6, `cost_blind`: routed success 0.876 at 1.6706 USD, cleared_rate 0.796, bar_violation_rate 0.080
- bar 0.8, `cost_effective`: routed success 0.859 at 0.5864 USD, cleared_rate 0.050, bar_violation_rate 0.120
- bar 0.8, `cost_blind`: routed success 0.876 at 1.6706 USD, cleared_rate 0.050, bar_violation_rate 0.080

At bar 0.8 almost nothing clears: at 95% confidence a perfect score needs at least 16 calibration questions for a Wilson lower bound of 0.8 or more, and 447 of the 500 halves hold fewer. The bar-violation rates run far above the nominal 0.025, because a small calibration half lets a model in on a lucky draw. Neither run beats `openai/gpt-5.6-luna` alone on both counts.

## Slices

The questions file labels each question with one of five difficulty levels and one of five skills, and `convert.py --labels` writes both on every row (see [README.md](README.md#question-labels-for-the-slice-evidence)). `model-routing evaluate --slice-by` then scores each value as a slice of the one task (DESIGN 12.3). In the slices tables, `pooled` is the task's own route, the routed rows above, scored on each slice's held-out questions, and `sliced` is a route calibrated on each slice's own calibration questions alone and scored on its held-out ones. The four files behind every number in this section are [slices-difficulty.json](slices-difficulty.json) and [slices-skill.json](slices-skill.json), at the default `min_samples = 30`, and [slices-difficulty-min10.json](slices-difficulty-min10.json) and [slices-skill-min10.json](slices-skill-min10.json), at `--min-samples 10`. In each of them the summary and the routed per-task rows are those of results.json, because the pooled task's calibration half holds at least 77 questions on every seed.

Questions per slice, of the 203: by difficulty 48 `1-very-simple`, 50 `2-simple`, 42 `3-unmarked`, 33 `4-difficult` and 30 `5-very-difficult`; by skill 15 `coding`, 23 `creative_synthesis`, 43 `math_reasoning`, 31 `planning_agentic` and 91 `world_knowledge`.

A rate in the slices tables counts (slice, seed) pairs: `below_bar_rate` is the share whose held-out success fell below the bar, `cleared_rate` the share that cleared the bar on the calibration half, and `bar_violation_rate` the share of cleared ones whose held-out success fell below it. `slice_miss_rate` counts seeds: of those on which the route cleared (for `sliced`, on every slice) and met the bar on all the held-out questions, the share on which some slice fell below it.

From `python evidence/routerbench/results.py --table evidence/autobench-2026/slices-difficulty.json`, its third table:

```text
bar  flavor          strategy  success  cost_usd  below_bar_rate  cleared_rate  bar_violation_rate  slice_miss_rate
---  --------------  --------  -------  --------  --------------  ------------  ------------------  ---------------
0.6  cost_effective  pooled    0.720    0.1976    0.196           1.000         0.196               0.540
0.6  cost_effective  sliced    0.838    1.4070    0.032           0.032         0.000               -
0.6  cost_blind      pooled    0.857    3.6917    0.004           1.000         0.004               0.020
0.6  cost_blind      sliced    0.840    1.9324    0.032           0.032         0.000               -
0.7  cost_effective  pooled    0.854    0.3110    0.052           1.000         0.052               0.102
0.7  cost_effective  sliced    0.839    1.4099    0.124           0.028         0.000               -
0.7  cost_blind      pooled    0.857    3.6917    0.056           1.000         0.056               0.240
0.7  cost_blind      sliced    0.840    1.9324    0.116           0.028         0.000               -
0.8  cost_effective  pooled    0.855    2.9694    0.264           0.660         0.267               0.844
0.8  cost_effective  sliced    0.841    1.4181    0.324           0.020         0.000               -
0.8  cost_blind      pooled    0.857    3.6917    0.260           0.660         0.261               0.879
0.8  cost_blind      sliced    0.840    1.9324    0.336           0.020         0.000               -
0.9  cost_effective  pooled    0.858    3.6535    0.652           0.000         -                   -
0.9  cost_effective  sliced    0.840    1.4224    0.656           0.000         -                   -
0.9  cost_blind      pooled    0.857    3.6917    0.652           0.000         -                   -
0.9  cost_blind      sliced    0.840    1.9324    0.660           0.000         -                   -
```

From `python evidence/routerbench/results.py --table evidence/autobench-2026/slices-skill.json`, its third table:

```text
bar  flavor          strategy  success  cost_usd  below_bar_rate  cleared_rate  bar_violation_rate  slice_miss_rate
---  --------------  --------  -------  --------  --------------  ------------  ------------------  ---------------
0.6  cost_effective  pooled    0.720    0.1976    0.196           1.000         0.196               0.640
0.6  cost_effective  sliced    0.868    0.7530    0.076           0.200         0.000               -
0.6  cost_blind      pooled    0.857    3.6917    0.076           1.000         0.076               0.360
0.6  cost_blind      sliced    0.868    1.5810    0.052           0.200         0.000               -
0.7  cost_effective  pooled    0.854    0.3110    0.228           1.000         0.228               0.980
0.7  cost_effective  sliced    0.881    0.7581    0.112           0.200         0.000               -
0.7  cost_blind      pooled    0.857    3.6917    0.128           1.000         0.128               0.560
0.7  cost_blind      sliced    0.868    1.5810    0.120           0.200         0.040               -
0.8  cost_effective  pooled    0.855    2.9694    0.268           0.660         0.261               0.969
0.8  cost_effective  sliced    0.866    1.1856    0.188           0.144         0.000               -
0.8  cost_blind      pooled    0.857    3.6917    0.264           0.660         0.255               0.939
0.8  cost_blind      sliced    0.868    1.5810    0.184           0.144         0.000               -
0.9  cost_effective  pooled    0.858    3.6535    0.604           0.000         -                   -
0.9  cost_effective  sliced    0.866    1.1856    0.592           0.000         -                   -
0.9  cost_blind      pooled    0.857    3.6917    0.608           0.000         -                   -
0.9  cost_blind      sliced    0.868    1.5810    0.608           0.000         -                   -
```

Reading it:

- A route that meets the bar on the whole task can still miss it on a slice. Of the seeds where the pooled `cost_effective` route cleared and met the bar on all the held-out questions, some slice fell below it on 0.540 of them at bar 0.6 by difficulty and 0.640 by skill, and on 0.102 and 0.980 at bar 0.7. The task's success rate is an average over its mix of questions, and the average hides the slices below the bar
- At the default `min_samples = 30` the sliced route rarely clears: at bar 0.6 its `cleared_rate` is 0.032 by difficulty and 0.200 by skill, where only `world_knowledge`, with 91 questions, clears, on every seed. On the other slices it falls back to the model with the highest lower bound on the slice's few questions, so the sliced `cost_effective` route at bar 0.6 reaches held-out success 0.838 at 1.4070 USD by difficulty and 0.868 at 0.7530 USD by skill, against the pooled route's 0.720 at 0.1976 USD: more success, at several times the cost
- At `--min-samples 10` more slices clear: at bar 0.6 the sliced `cleared_rate` is 0.956 by difficulty and 0.744 by skill, and the sliced `cost_effective` route reaches 0.793 at 0.5202 USD by difficulty and 0.857 at 0.4211 USD by skill, with a `slice_miss_rate` of 0.220 and 0.000 against the pooled route's 0.540 and 0.640. The price is a looser check: at bar 0.8 the sliced `cost_effective` `bar_violation_rate` is 0.127 by difficulty and 0.025 by skill, against 0.000 and 0.000 at 30. At 95% confidence a perfect score needs at least 6, 9, 16 and 35 calibration questions for a Wilson lower bound of 0.6, 0.7, 0.8 and 0.9, so a small slice can clear a low bar on a lucky half, and no slice clears at 0.9 in any file
- No sliced row in the four files beats `openai/gpt-5.6-luna` alone (held-out success 0.872 at 0.3092 USD) on both counts. On this matrix slicing shows where the pooled route misses a slice, but it finds no cheaper way to that model's quality
- A slice's held-out half holds a few to a few dozen questions, so one question moves a slice's held-out rate far more than the task's, and a slice miss is partly sampling noise, not only a weaker route

The four files come from these commands, after `python -m pip install -e .`; two runs give byte-identical files:

```bash
python evidence/autobench-2026/convert.py --out autobench-labels.jsonl --task-by all --labels
model-routing evaluate --outcomes autobench-labels.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --slice-by difficulty --json > autobench-slices-difficulty.json
python evidence/routerbench/results.py --evaluate autobench-slices-difficulty.json --out evidence/autobench-2026/slices-difficulty.json
model-routing evaluate --outcomes autobench-labels.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --slice-by skill --json > autobench-slices-skill.json
python evidence/routerbench/results.py --evaluate autobench-slices-skill.json --out evidence/autobench-2026/slices-skill.json
model-routing evaluate --outcomes autobench-labels.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --slice-by difficulty --min-samples 10 --json > autobench-slices-difficulty-min10.json
python evidence/routerbench/results.py --evaluate autobench-slices-difficulty-min10.json --out evidence/autobench-2026/slices-difficulty-min10.json
model-routing evaluate --outcomes autobench-labels.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --slice-by skill --min-samples 10 --json > autobench-slices-skill-min10.json
python evidence/routerbench/results.py --evaluate autobench-slices-skill-min10.json --out evidence/autobench-2026/slices-skill-min10.json
```

## Caveats

- The models are 2026 models, and the costs are the billed USD per call in the matrix frozen on 2026-08-29; vendor prices have moved since
- A Delta-Hit is relative, not an absolute acceptance check: it means "rated about as well as the best three answers in this pool on this question" by judges that are themselves models from the same pool, so these are model judgments, not gold labels
- The sample is small: 203 questions, with 77 to 120 in the calibration half over the 50 seeds, so the Wilson bound admits few models at high bars, and the per-domain split is too small for the default `min_samples`
- The converter drops the 49 questions with an unscored pool cell (107 cells) rather than scoring them as misses, and the 388 rows for 13 models outside the 20-model pool
- Data: CC-BY-4.0, Autobench, Autobench Router Benchmark 2026, https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10 at revision 43755180be7d8097068982d7a3f37fc04cd15379. Pinned files, sha256 values, the citation the card asks for and what the converter drops are in [README.md](README.md)

## Regenerate

```bash
python -m pip install -e .
python evidence/autobench-2026/convert.py --out autobench-matrix.jsonl --task-by all
model-routing evaluate --outcomes autobench-matrix.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50 --json > autobench-evaluate.json
python evidence/routerbench/results.py --evaluate autobench-evaluate.json --out evidence/autobench-2026/results.json
python evidence/routerbench/results.py --table evidence/autobench-2026/results.json
```

The evaluate step takes under a second and its full output is about 116 KB; the committed file, 56,887 bytes, keeps only the summary and the routed per-task rows. Two runs give byte-identical files. The sensitivity numbers come from:

```bash
python evidence/autobench-2026/convert.py --out autobench-matrix-official.jsonl --task-by all --width 0.3011090610836323
model-routing evaluate --outcomes autobench-matrix-official.jsonl --bar 0.8 --seeds 50
python evidence/autobench-2026/convert.py --out autobench-matrix-domain.jsonl
model-routing evaluate --outcomes autobench-matrix-domain.jsonl --bar 0.6 0.8 --seeds 50 --min-samples 5
```
