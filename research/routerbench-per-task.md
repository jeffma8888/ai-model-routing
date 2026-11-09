# Each RouterBench eval's own best model

[where-routing-pays.md](where-routing-pays.md) finds that on RouterBench `cost_blind` routing ends just below the best single model, and that the committed results hold no per-task single-model rows, so it cannot say on how many evals another model is truly the best. That is the ceiling of per-task routing, how much success choosing a model per eval could add. This note reads the pinned RouterBench file itself to name each eval's best model. Its numbers are the output of [routerbench_per_task.py](routerbench_per_task.py), which reads the file through the converter's checked reader ([DESIGN.md](../DESIGN.md) 12.6 and 12.8).

## Facts

- Data: the pinned RouterBench file, converted with the defaults of 12.6, the matrix behind [the committed results](../evidence/routerbench/RESULTS.md): 65 evals, 11 models, 28,281 items, 50 seeds of the 12.2 split at a calibration_fraction of 0.5
- `openai/gpt-4-1106-preview` is the best model on all items of every eval but 3: `abstract2title`, where 4 models answer every item (1.000) and the cheapest is taken; `mmlu-business-ethics`, where `zero-one-ai/Yi-34B-Chat` leads by 0.020 at a shortfall of 0.134; and `mmlu-public-relations`, where `openai/gpt-3.5-turbo-1106` leads by 0.027 at a shortfall of 0.130. No eval has another model ahead by more than its shortfall (0)
- The ceiling is small: each eval's own best model on all items, chosen in hindsight, reaches a held-out success of 0.8213 against 0.8211 for the best single model, 1.9 more correct held-out items per seed; the best model on each seed's held-out half, chosen on the items it is scored on, reaches 0.8216, 6.6 more
- Routing per eval loses more than that: at bar 0.6 in `cost_blind` the router reaches 0.8194, 23.8 fewer items per seed, since on 274 of 3,250 eval and seed cells, on 22 evals, the calibration half ranks another model first; `best_on_calibration` does the same on 289 cells of 23 evals
- The room is between prompts: the per-prompt oracle of 12.3 reaches 0.9587

## Method

- The script loads `evidence/routerbench/convert.py` from its path, checks the cached file's size and sha256 (`verify`), unpickles it with the restricted unpickler (`load_frame`) and converts it with the defaults; it never downloads
- It runs `evaluate` (12.3) on that matrix with the committed config's seeds, `calibration_fraction`, `min_samples` and `confidence` at its first bar, 0.6, on `cost_blind`, and stops unless every model row, the routed row, `best_on_calibration` and the oracle equal the committed file's
- Per eval, the best model on all its items has the most correct items, then the lower total cost, then the lower ID (the 12.7 rule on one eval), and `tied` counts the models with that count. The margin is its success minus the best single model's on all items. The shortfall is its success minus the Wilson lower bound of that success at the eval's calibration half, the median over seeds of the real 12.2 halves, as in where-routing-pays.md: a model's calibration success must sit about that far above the bar for its bound to clear it, and two models closer than that can trade places from seed to seed. `seeds` counts the seeds on which that model is also the best on the held-out half (the highest held-out success, then the lower held-out cost, then the ID), and `models` the models that are that best on some seed
- A row over evals is 12.3's summary: per seed, the correct held-out items over the held-out items of the group's evals, and the summed cost, each averaged over the 50 seeds; `vs single` is the mean over seeds of the correct held-out items minus the best single model's. The per-eval best on all items is one model per eval, chosen in hindsight on all its items, half of which each seed then scores. The per-eval best on each held-out half is chosen on the items it is scored on, so no rule that picks one model per eval and seed can beat it. The oracle of 12.3 picks per prompt, in hindsight too
- Groups: all evals, the 57 whose name starts with `mmlu`, and the 8 others
- What another dataset needs: the calibration half is `items_needed` (4.3) at a success of 0.8 and a bar of 0.8 minus the margin, the half from which the shortfall is within the margin; the share of items is the gain over the margin, since one model per task gains its margin on the items of the tasks where it is the better choice and nothing elsewhere

## Results

```text
$ python research/routerbench_per_task.py
RouterBench (routerbench_0shot.pkl at revision 784021482c3f320c6619ed4b3bb3b41a21424fcb): 65 evals, 11 models, 28,281 items, 50 seeds, calibration_fraction 0.5, confidence 0.95
best single model (12.7): openai/gpt-4-1106-preview, held-out success 0.8211 at 26.2358 USD
per eval: its items and calibration half (median over seeds), its best model on all its items, the models tied on that count, that model's success and the best single model's on all items, the margin, the Wilson shortfall of that success at the half, the seeds on which it is also the best on the held-out half, and the models that are that best on some seed
  eval                                      items  half  best on all items                  tied  success  single  margin  shortfall  seeds  models
  Chinese_character_riddles                   100    51  openai/gpt-4-1106-preview             1  0.130    0.130   +0.000  0.062         28       4
  abstract2title                              254   127  zero-one-ai/Yi-34B-Chat               4  1.000    1.000   +0.000  0.029          5       5
  arc-challenge                              1470   732  openai/gpt-4-1106-preview             1  0.962    0.962   +0.000  0.017         50       1
  bias_detection                              285   142  openai/gpt-4-1106-preview             1  0.375    0.375   +0.000  0.077         47       3
  chinese_zodiac                              394   197  openai/gpt-4-1106-preview             1  0.708    0.708   +0.000  0.064         50       1
  hellaswag                                 10042  5023  openai/gpt-4-1106-preview             1  0.840    0.840   +0.000  0.010         50       1
  mbpp                                        427   217  openai/gpt-4-1106-preview             1  0.686    0.686   +0.000  0.064         48       3
  mmlu-abstract-algebra                       100    50  openai/gpt-4-1106-preview             1  0.550    0.550   +0.000  0.127         50       1
  mmlu-anatomy                                135    66  openai/gpt-4-1106-preview             1  0.807    0.807   +0.000  0.116         50       1
  mmlu-astronomy                              152    75  openai/gpt-4-1106-preview             1  0.928    0.928   +0.000  0.074         50       1
  mmlu-business-ethics                        100    49  zero-one-ai/Yi-34B-Chat               1  0.820    0.800   +0.020  0.134         30       5
  mmlu-clinical-knowledge                     265   132  openai/gpt-4-1106-preview             1  0.868    0.868   +0.000  0.065         50       1
  mmlu-college-biology                        144    72  openai/gpt-4-1106-preview             1  0.944    0.944   +0.000  0.079         50       1
  mmlu-college-chemistry                      100    51  openai/gpt-4-1106-preview             1  0.580    0.580   +0.000  0.128         44       3
  mmlu-college-computer-science               100    50  openai/gpt-4-1106-preview             1  0.770    0.770   +0.000  0.144         50       1
  mmlu-college-mathematics                    100    49  openai/gpt-4-1106-preview             1  0.450    0.450   +0.000  0.131         27       3
  mmlu-college-medicine                       173    86  openai/gpt-4-1106-preview             1  0.792    0.792   +0.000  0.099         50       1
  mmlu-college-physics                        102    51  openai/gpt-4-1106-preview             1  0.559    0.559   +0.000  0.145         48       3
  mmlu-computer-security                      100    51  openai/gpt-4-1106-preview             1  0.860    0.860   +0.000  0.117         50       1
  mmlu-conceptual-physics                     235   119  openai/gpt-4-1106-preview             1  0.821    0.821   +0.000  0.076         50       1
  mmlu-econometrics                           114    56  openai/gpt-4-1106-preview             1  0.667    0.667   +0.000  0.137         48       3
  mmlu-electrical-engineering                 145    73  openai/gpt-4-1106-preview             1  0.745    0.745   +0.000  0.116         50       1
  mmlu-elementary-mathematics                 378   189  openai/gpt-4-1106-preview             1  0.706    0.706   +0.000  0.066         50       1
  mmlu-formal-logic                           126    63  openai/gpt-4-1106-preview             1  0.619    0.619   +0.000  0.123         50       1
  mmlu-global-facts                           100    51  openai/gpt-4-1106-preview             1  0.530    0.530   +0.000  0.135         40       6
  mmlu-high-school-biology                    310   156  openai/gpt-4-1106-preview             1  0.939    0.939   +0.000  0.053         50       1
  mmlu-high-school-chemistry                  203   101  openai/gpt-4-1106-preview             1  0.729    0.729   +0.000  0.090         50       1
  mmlu-high-school-computer-science           100    49  openai/gpt-4-1106-preview             1  0.910    0.910   +0.000  0.102         50       1
  mmlu-high-school-european-history           165    83  openai/gpt-4-1106-preview             1  0.867    0.867   +0.000  0.089         49       2
  mmlu-high-school-geography                  198   100  openai/gpt-4-1106-preview             1  0.934    0.934   +0.000  0.072         50       1
  mmlu-high-school-government-and-politics    193    97  openai/gpt-4-1106-preview             1  0.974    0.974   +0.000  0.061         50       1
  mmlu-high-school-macroeconomics             390   197  openai/gpt-4-1106-preview             1  0.867    0.867   +0.000  0.053         50       1
  mmlu-high-school-mathematics                270   135  openai/gpt-4-1106-preview             1  0.470    0.470   +0.000  0.079         50       1
  mmlu-high-school-microeconomics             238   118  openai/gpt-4-1106-preview             1  0.966    0.966   +0.000  0.050         50       1
  mmlu-high-school-physics                    151    73  openai/gpt-4-1106-preview             1  0.636    0.636   +0.000  0.120         50       1
  mmlu-high-school-psychology                 545   271  openai/gpt-4-1106-preview             1  0.954    0.954   +0.000  0.030         50       1
  mmlu-high-school-statistics                 216   109  openai/gpt-4-1106-preview             1  0.792    0.792   +0.000  0.088         50       1
  mmlu-high-school-us-history                 204   103  openai/gpt-4-1106-preview             1  0.956    0.956   +0.000  0.065         50       1
  mmlu-high-school-world-history              237   117  openai/gpt-4-1106-preview             1  0.924    0.924   +0.000  0.064         46       2
  mmlu-human-aging                            223   112  openai/gpt-4-1106-preview             1  0.830    0.830   +0.000  0.079         50       1
  mmlu-human-sexuality                        131    66  openai/gpt-4-1106-preview             1  0.885    0.885   +0.000  0.107         50       1
  mmlu-international-law                      121    58  openai/gpt-4-1106-preview             1  0.901    0.901   +0.000  0.109         49       2
  mmlu-jurisprudence                          108    53  openai/gpt-4-1106-preview             1  0.870    0.870   +0.000  0.119         49       2
  mmlu-logical-fallacies                      163    80  openai/gpt-4-1106-preview             1  0.877    0.877   +0.000  0.092         49       2
  mmlu-machine-learning                       112    55  openai/gpt-4-1106-preview             1  0.759    0.759   +0.000  0.122         50       1
  mmlu-management                             103    51  openai/gpt-4-1106-preview             1  0.874    0.874   +0.000  0.108         21       5
  mmlu-marketing                              234   117  openai/gpt-4-1106-preview             1  0.936    0.936   +0.000  0.054         42       3
  mmlu-medical-genetics                       100    51  openai/gpt-4-1106-preview             1  0.950    0.950   +0.000  0.109         50       1
  mmlu-miscellaneous                          783   392  openai/gpt-4-1106-preview             1  0.951    0.951   +0.000  0.026         50       1
  mmlu-moral-disputes                         346   175  openai/gpt-4-1106-preview             1  0.818    0.818   +0.000  0.065         50       1
  mmlu-moral-scenarios                        895   447  openai/gpt-4-1106-preview             1  0.754    0.754   +0.000  0.042         50       1
  mmlu-nutrition                              306   153  openai/gpt-4-1106-preview             1  0.873    0.873   +0.000  0.058         50       1
  mmlu-philosophy                             311   157  openai/gpt-4-1106-preview             1  0.833    0.833   +0.000  0.064         50       1
  mmlu-prehistory                             324   162  openai/gpt-4-1106-preview             1  0.907    0.907   +0.000  0.055         50       1
  mmlu-professional-accounting                282   141  openai/gpt-4-1106-preview             1  0.745    0.745   +0.000  0.078         50       1
  mmlu-professional-law                      1534   769  openai/gpt-4-1106-preview             1  0.675    0.675   +0.000  0.034         50       1
  mmlu-professional-medicine                  272   137  openai/gpt-4-1106-preview             1  0.930    0.930   +0.000  0.059         50       1
  mmlu-professional-psychology                612   304  openai/gpt-4-1106-preview             1  0.858    0.858   +0.000  0.043         50       1
  mmlu-public-relations                       110    56  openai/gpt-3.5-turbo-1106             1  0.773    0.745   +0.027  0.130         37       3
  mmlu-security-studies                       245   124  openai/gpt-4-1106-preview             1  0.767    0.767   +0.000  0.083         42       3
  mmlu-sociology                              201   101  openai/gpt-4-1106-preview             1  0.905    0.905   +0.000  0.078         50       1
  mmlu-us-foreign-policy                      100    49  openai/gpt-4-1106-preview             1  0.920    0.920   +0.000  0.112         47       3
  mmlu-virology                               166    82  openai/gpt-4-1106-preview             1  0.566    0.566   +0.000  0.113         45       3
  mmlu-world-religions                        171    85  openai/gpt-4-1106-preview             1  0.889    0.889   +0.000  0.078         35       4
  winogrande                                 1267   637  openai/gpt-4-1106-preview             1  0.819    0.819   +0.000  0.032         50       1
evals whose best model on all items is not openai/gpt-4-1106-preview: 3 (abstract2title, mmlu-business-ethics, mmlu-public-relations); with a higher success than it: 2; higher by more than the shortfall: 0
largest margin: +0.027 on mmlu-public-relations (openai/gpt-3.5-turbo-1106), shortfall 0.130
routed (cost_blind, bar 0.6) takes another model on 274 of 3,250 eval and seed cells, on 22 evals; best_on_calibration on 289, on 23 evals
held-out success and cost over 50 seeds, as 12.3's summary computes them; vs single: the mean correct held-out items per seed minus the best single model's
  group   evals  strategy                             success  cost (USD)  vs single
  all        65  best single model                    0.8211   26.2358          +0.0
  all        65  routed (cost_blind, bar 0.6)         0.8194   25.2675         -23.8
  all        65  best_on_calibration                  0.8194   25.0029         -23.9
  all        65  per-eval best on all items           0.8213   25.7045          +1.9
  all        65  per-eval best on each held-out half  0.8216   25.2630          +6.6
  all        65  oracle (per prompt)                  0.9587   1.9634        +1944.1
  mmlu       57  best single model                    0.8118   10.0612          +0.0
  mmlu       57  routed (cost_blind, bar 0.6)         0.8094   9.8060          -16.7
  mmlu       57  best_on_calibration                  0.8094   9.7774          -16.8
  mmlu       57  per-eval best on all items           0.8121   9.9628           +1.9
  mmlu       57  per-eval best on each held-out half  0.8126   9.8200           +5.9
  mmlu       57  oracle (per prompt)                  0.9547   0.8425        +1002.7
  other       8  best single model                    0.8303   16.1746          +0.0
  other       8  routed (cost_blind, bar 0.6)         0.8293   15.4615          -7.1
  other       8  best_on_calibration                  0.8293   15.2255          -7.1
  other       8  per-eval best on all items           0.8303   15.7417          +0.0
  other       8  per-eval best on each held-out half  0.8304   15.4430          +0.8
  other       8  oracle (per prompt)                  0.9627   1.1209         +941.4
what another dataset needs, at a success of 0.8: the calibration half from which the Wilson shortfall is within the margin (items_needed, 4.3), and the share of items that evals with that margin over the best single model must hold for a gain of 0.01 in success
  margin 0.02: half 1,727; share of items 0.50
  margin 0.05: half 317; share of items 0.20
  margin 0.1: half 97; share of items 0.10
```

## Reading it

- On RouterBench one model is the best, or tied for the best, on every eval. Where another model leads, the lead is a tie at 1.000 broken by cost on `abstract2title`, or 0.020 and 0.027 on two evals of 100 and 110 items whose halves of 49 and 56 leave shortfalls of 0.134 and 0.130. No calibration half on this file can show another model to be better
- So per-task routing has almost nothing to gain here in success: even in hindsight, each eval's own best model adds 1.9 correct held-out items per seed (0.8213 against 0.8211), and picking on each held-out half itself, which no rule can do, adds 6.6 (0.8216). By group it is 0.8121 and 0.8126 against 0.8118 on the 57 `mmlu` evals, and 0.8303 and 0.8304 against 0.8303 on the 8 others
- What routing per eval does instead is follow noise. The router at bar 0.6 in `cost_blind` takes another model on 274 of 3,250 cells, on 22 evals, and ends 23.8 correct items per seed below the best single model (0.8194), as `best_on_calibration` does (289 cells, 23 evals, 23.9 fewer). These are the 22 evals with two or more picks that where-routing-pays.md counts: halves from 49 to 5023 items rank a model that is not better first often enough to lose more than a perfect choice per eval could gain. Its cost falls, 25.2675 USD against 26.2358, because the models it moves to are cheaper
- The room for more success is between prompts inside an eval: the per-prompt oracle reaches 0.9587 at 1.9634 USD, 1944.1 more correct items per seed. A router that wants more success on this data has to choose per prompt, for example a cascade, not per eval; the oracle is chosen in hindsight per prompt, so it only bounds that from above

## What another dataset needs

- Tasks whose best model differs from the overall best by more than the shortfall at their calibration half. At a success of 0.8, a margin of 0.02 needs a half of 1,727 items, 0.05 needs 317 and 0.1 needs 97
- Enough of its items in such tasks: one model per task gains its margin only on those items, so a gain of 0.01 in success needs 0.50 of the items in tasks with a margin of 0.02, 0.20 at 0.05 and 0.10 at 0.1. RouterBench has 2 evals where another model has a higher success, 100 and 110 of its 28,281 items
- So a candidate dataset for per-task routing evidence needs, at a margin of 0.05, about a fifth (0.20) of its items in tasks where another model leads by that much, each task with a half of 317 items or more

## Limits

- One dataset and its 11 models, all older than the current ones; a newer model set may differ more from task to task
- The tasks are RouterBench's evals. A finer split inside an eval (by prompt kind or length) may differ in its best model where the evals do not; this note does not test one
- The shortfall is a yardstick, not a test of the difference between two models: it is how far one model's bound sits below its success, while two models' calibration counts on the same items are paired, so the noise of their difference can be smaller or larger
- The per-eval best on all items is scored on held-out halves of the items it was chosen on, so it is optimistic, and the per-eval best on each half more so; both are ceilings, not rules
- What another dataset needs is taken at one success, 0.8; a success nearer the middle needs larger halves for the same margin
- Costs are those the file records per prompt

## Regenerate

```bash
python -m pip install -e ".[evidence]"
python evidence/routerbench/convert.py --out routerbench-matrix.jsonl
python research/routerbench_per_task.py
```

The converter downloads the pinned file into its cache folder and checks it; the script reads it from there and never downloads, and its matrix output is not read. `tests/test_research_routerbench_per_task.py` compares the Results block with a fresh run when the file and pandas are present.
