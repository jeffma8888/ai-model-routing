# Where task-level routing pays on the committed evidence

README Results at a glance shows routing costing less than the best single model on some datasets, never reaching that model's held-out success on five of them and passing it on LLMRouterBench and the LLM Routing Response Bank. This note reads the seven committed routing results files to say why, and what a user's own data needs for routing to pay. Its numbers are the output of [where_routing_pays.py](where_routing_pays.py), which reads only those files (`DESIGN.md` 12.8).

## Facts

- Files read, nothing downloaded: `evidence/routerbench/results.json`, `evidence/autobench-2026/results.json`, `evidence/autobench-judges/results.json`, `evidence/tau2-bench/results.json`, `evidence/livecodebench/results.json`, `evidence/llmrouterbench/results.json` and `evidence/response-bank/results.json`
- Tasks routed: 65 on RouterBench, 9 on LLMRouterBench, 4 on the LLM Routing Response Bank, 3 on tau2-bench, 1 each on AutoBench, AutoBench judges and LiveCodeBench
- On the first five, no routed row at any bar or flavor reaches the best single model's held-out success, and neither does `best_on_calibration`, each task's best model on its calibration half with no bar: 0.819 against 0.821 on RouterBench, 0.858 against 0.882 on AutoBench, 0.831 against 0.835 on AutoBench judges, 0.578 against 0.612 on tau2-bench and 0.902 against 0.909 on LiveCodeBench
- On LLMRouterBench both pass it: `best_on_calibration` reaches 0.615 against the 0.592 of `google/gemini-2.5-pro`, `cost_blind` routing 0.615 at every bar for 0.473 of that model's cost, and `cost_effective` routing 0.598 at 0.353 at bar 0.7 and 0.606 at 0.420 at bar 0.8. The `cost_blind` gain, +0.0223, is 0.89 of the in-sample per-task gain, 0.0250, that research/datasets.md measured on all items (section below)
- On the LLM Routing Response Bank both pass it too, by less and at a higher cost: `best_on_calibration` reaches 0.874 against the 0.872 of `deepseek/deepseek-v4-pro`, and `cost_blind` routing 0.874 at both bars, a gain of +0.0022, but at 2.104 times that model's cost, as does `cost_effective` routing at bar 0.9 (second section below)
- The best single model is the one with the highest held-out success (12.7), so it is chosen in hindsight, by its success on the held-out halves it is then scored on, while routing and `best_on_calibration` choose on the calibration half alone; it is a reference no rule that sees only a calibration half can be sure to pick
- Where routing pays on the first five files is cost: at a bar below the best single model's success, `cost_effective` routing takes cheaper models that clear it, for example 0.735 at 0.341 of the best single model's cost at bar 0.6 on RouterBench and 0.854 at 0.056 at bar 0.7 on AutoBench
- A gain in success needs tasks that differ in their best model and calibration halves large enough to tell the candidates apart. Three of the first five files route one pooled task, and on RouterBench's 65 tasks the top pick takes 0.916 of the `cost_blind` picks; LLMRouterBench's 9 tasks are of the other kind: in `cost_blind` 5 of them never pick the best single model, and the median expected half is 374 items

## Method

- For each file the script prints the tasks, models, seeds and run settings; the items per task and the expected calibration half, `int(items * calibration_fraction)` (the 12.2 split hashes each item with the seed, so the real count varies by seed, and the files do not record it); and the number of tasks whose half is below `min_samples`
- The best single model is chosen among the `model:` summary rows as in 12.7, highest held-out success, then lower cost, then ID; the script requires it to be the same at every bar and flavor. `best_on_calibration` is the 12.3 baseline at the first bar and flavor
- The Wilson shortfall is the best single model's held-out success minus the Wilson lower bound of that success observed on n items at the run's confidence (`model_routing.stats.wilson_lower_bound`, the bound the router uses), at the smallest half and, when it differs, the median half. A model's calibration success must sit about that far above the bar for its bound to clear it (5.3), and two models closer than that can trade places from seed to seed
- Per flavor and bar: the routed held-out success, cost, cost over the best single model's (`-` when that is 0, as on LiveCodeBench), cleared rate, and, from each task's `routed_models` (the model picked on each seed), the number of distinct models picked, the number of tasks whose pick changes between seeds, and the most-picked model's share of all task and seed picks
- Each row also gives (`DESIGN.md` 12.8, v1.166), from the same `routed_models`, the tasks that pick a model other than the best single model on some seed (`off best`) and on every seed (`never best`), and the routed held-out success minus the best single model's (`gain`). For a file whose in-sample per-task gain a note measured on all items, LLMRouterBench's in research/datasets.md, one line gives that gain and the share of it each held-out gain keeps: `best_on_calibration`'s, and per flavor the routed rows', as one value or the lowest to the highest over the bars. The script holds the in-sample figure as a constant, and the test suite checks it against that note

## Results

```text
$ python research/where_routing_pays.py
RouterBench (evidence/routerbench/results.json): 65 tasks, 11 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: 100 to 10042, median 201; expected calibration half: 50 to 5021, median 100; tasks whose half is below min_samples: 0
  best single model: openai/gpt-4-1106-preview, held-out success 0.821 at 26.2358 USD; Wilson shortfall of that success: 0.129 at a half of 50, 0.088 at 100
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.819 at 25.0029 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share  off best  never best  gain
  0.6  cost_effective  0.735   8.9478      0.341        0.804    9              41             0.446           54        30          -0.0865
  0.7  cost_effective  0.761   11.7482     0.448        0.616    8              39             0.615           48        13          -0.0597
  0.8  cost_effective  0.808   23.2560     0.886        0.371    8              31             0.819           32        4           -0.0134
  0.9  cost_effective  0.819   24.9963     0.953        0.111    8              22             0.911           23        1           -0.0016
  0.6  cost_blind      0.819   25.2675     0.963        0.804    8              22             0.916           22        1           -0.0017
  0.7  cost_blind      0.819   25.2675     0.963        0.616    8              22             0.916           22        1           -0.0017
  0.8  cost_blind      0.819   25.2675     0.963        0.371    8              22             0.916           22        1           -0.0017
  0.9  cost_blind      0.819   25.2675     0.963        0.111    8              22             0.916           22        1           -0.0017

AutoBench (evidence/autobench-2026/results.json): 1 task, 20 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: all 203; expected calibration half: 101; tasks whose half is below min_samples: 0
  best single model: openai/gpt-5.6-sol, held-out success 0.882 at 5.5616 USD; Wilson shortfall of that success: 0.079 at a half of 101
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.858 at 3.6535 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share  off best  never best  gain
  0.6  cost_effective  0.720   0.1976      0.036        1.000    5              1              0.400           1         1           -0.1624
  0.7  cost_effective  0.854   0.3110      0.056        1.000    3              1              0.900           1         1           -0.0280
  0.8  cost_effective  0.855   2.9694      0.534        0.660    5              1              0.460           1         0           -0.0276
  0.9  cost_effective  0.858   3.6535      0.657        0.000    5              1              0.600           1         0           -0.0247
  0.6  cost_blind      0.857   3.6917      0.664        1.000    5              1              0.600           1         0           -0.0251
  0.7  cost_blind      0.857   3.6917      0.664        1.000    5              1              0.600           1         0           -0.0251
  0.8  cost_blind      0.857   3.6917      0.664        0.660    5              1              0.600           1         0           -0.0251
  0.9  cost_blind      0.857   3.6917      0.664        0.000    5              1              0.600           1         0           -0.0251

AutoBench judges (evidence/autobench-judges/results.json): 1 task, 5 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: all 756; expected calibration half: 378; tasks whose half is below min_samples: 0
  best single model: tencent/hy3, held-out success 0.835 at 0.1192 USD; Wilson shortfall of that success: 0.040 at a half of 378
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.831 at 0.1146 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share  off best  never best  gain
  0.6  cost_effective  0.816   0.0617      0.518        1.000    1              0              1.000           1         1           -0.0190
  0.7  cost_effective  0.816   0.0617      0.518        1.000    1              0              1.000           1         1           -0.0190
  0.8  cost_effective  0.831   0.1135      0.953        0.560    2              1              0.900           1         0           -0.0042
  0.9  cost_effective  0.831   0.1146      0.962        0.000    2              1              0.920           1         0           -0.0034
  0.6  cost_blind      0.831   0.1146      0.962        1.000    2              1              0.920           1         0           -0.0034
  0.7  cost_blind      0.831   0.1146      0.962        1.000    2              1              0.920           1         0           -0.0034
  0.8  cost_blind      0.831   0.1146      0.962        0.560    2              1              0.920           1         0           -0.0034
  0.9  cost_blind      0.831   0.1146      0.962        0.000    2              1              0.920           1         0           -0.0034

tau2-bench (evidence/tau2-bench/results.json): 3 tasks, 4 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: airline 50, retail 114, telecom 114; expected calibration half: 25, 57, 57; tasks whose half is below min_samples: 1
  best single model: anthropic/claude-3-7-sonnet-20250219, held-out success 0.612 at 63.2133 USD; Wilson shortfall of that success: 0.205 at a half of 25, 0.128 at 57
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.578 at 31.0962 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share  off best  never best  gain
  0.3  cost_effective  0.547   9.1340      0.144        0.667    4              2              0.680           3         1           -0.0649
  0.4  cost_effective  0.544   15.6738     0.248        0.400    4              2              0.527           3         1           -0.0681
  0.5  cost_effective  0.545   16.4831     0.261        0.333    4              3              0.473           3         0           -0.0669
  0.6  cost_effective  0.559   24.2031     0.383        0.327    4              3              0.320           3         0           -0.0534
  0.7  cost_effective  0.578   30.7979     0.487        0.080    4              3              0.413           3         0           -0.0346
  0.8  cost_effective  0.578   31.0962     0.492        0.000    4              3              0.420           3         0           -0.0340
  0.3  cost_blind      0.589   40.3751     0.639        0.667    4              3              0.580           3         0           -0.0231
  0.4  cost_blind      0.589   40.3751     0.639        0.400    4              3              0.580           3         0           -0.0231
  0.5  cost_blind      0.589   40.3751     0.639        0.333    4              3              0.580           3         0           -0.0231
  0.6  cost_blind      0.589   40.3751     0.639        0.327    4              3              0.580           3         0           -0.0231
  0.7  cost_blind      0.589   40.3751     0.639        0.080    4              3              0.580           3         0           -0.0231
  0.8  cost_blind      0.589   40.3751     0.639        0.000    4              3              0.580           3         0           -0.0231

LiveCodeBench (evidence/livecodebench/results.json): 1 task, 67 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: code_generation 713; expected calibration half: 356; tasks whose half is below min_samples: 0
  best single model: openai/o4-mini-high, held-out success 0.909 at 0.0000 USD; Wilson shortfall of that success: 0.033 at a half of 356
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.902 at 0.0000 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share  off best  never best  gain
  0.1  cost_blind      0.902   0.0000      -            1.000    2              1              0.580           1         0           -0.0066
  0.2  cost_blind      0.902   0.0000      -            1.000    2              1              0.580           1         0           -0.0066
  0.3  cost_blind      0.902   0.0000      -            1.000    2              1              0.580           1         0           -0.0066
  0.4  cost_blind      0.902   0.0000      -            1.000    2              1              0.580           1         0           -0.0066
  0.5  cost_blind      0.902   0.0000      -            1.000    2              1              0.580           1         0           -0.0066
  0.6  cost_blind      0.902   0.0000      -            1.000    2              1              0.580           1         0           -0.0066
  0.7  cost_blind      0.902   0.0000      -            1.000    2              1              0.580           1         0           -0.0066
  0.8  cost_blind      0.902   0.0000      -            1.000    2              1              0.580           1         0           -0.0066
  0.9  cost_blind      0.902   0.0000      -            0.180    2              1              0.580           1         0           -0.0066

LLMRouterBench (evidence/llmrouterbench/results.json): 9 tasks, 13 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: 60 to 4326, median 749; expected calibration half: 30 to 2163, median 374; tasks whose half is below min_samples: 0
  best single model: google/gemini-2.5-pro, held-out success 0.592 at 366.3999 USD; Wilson shortfall of that success: 0.169 at a half of 30, 0.049 at 374
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.615 at 171.3368 USD
  in-sample per-task gain over google/gemini-2.5-pro on all items (research/datasets.md): 0.0250; share of it kept on the held-out halves: best_on_calibration 0.89, routed cost_effective -1.58 to 0.55, routed cost_blind 0.89
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share  off best  never best  gain
  0.1  cost_effective  0.553   39.4802     0.108        0.944    9              2              0.558           9         8           -0.0395
  0.2  cost_effective  0.576   86.9437     0.237        0.944    9              3              0.491           9         8           -0.0164
  0.3  cost_effective  0.580   97.9296     0.267        0.833    9              2              0.447           9         8           -0.0125
  0.4  cost_effective  0.580   97.9296     0.267        0.831    9              2              0.447           9         8           -0.0125
  0.5  cost_effective  0.581   97.9935     0.267        0.722    9              3              0.387           9         8           -0.0112
  0.6  cost_effective  0.586   113.9149    0.311        0.598    10             5              0.347           9         6           -0.0066
  0.7  cost_effective  0.598   129.3241    0.353        0.433    9              5              0.329           9         6           +0.0058
  0.8  cost_effective  0.606   154.0269    0.420        0.256    7              5              0.491           9         5           +0.0137
  0.1  cost_blind      0.615   173.4190    0.473        0.944    8              5              0.602           9         5           +0.0223
  0.2  cost_blind      0.615   173.4190    0.473        0.944    8              5              0.602           9         5           +0.0223
  0.3  cost_blind      0.615   173.4190    0.473        0.833    8              5              0.602           9         5           +0.0223
  0.4  cost_blind      0.615   173.4190    0.473        0.831    8              5              0.602           9         5           +0.0223
  0.5  cost_blind      0.615   173.4190    0.473        0.722    8              5              0.602           9         5           +0.0223
  0.6  cost_blind      0.615   173.4190    0.473        0.598    8              5              0.602           9         5           +0.0223
  0.7  cost_blind      0.615   173.4190    0.473        0.433    8              5              0.602           9         5           +0.0223
  0.8  cost_blind      0.615   173.4190    0.473        0.256    8              5              0.602           9         5           +0.0223

LLM Routing Response Bank (evidence/response-bank/results.json): 4 tasks, 5 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: aime 30, gpqa_diamond 198, livecodebench 1055, mmlu_pro 12032; expected calibration half: 15, 99, 527, 6016; tasks whose half is below min_samples: 1
  best single model: deepseek/deepseek-v4-pro, held-out success 0.872 at 27.2956 USD; Wilson shortfall of that success: 0.251 at a half of 15, 0.041 at 313
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.874 at 57.4387 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share  off best  never best  gain
  0.8  cost_effective  0.847   5.4902      0.201        0.735    3              2              0.505           4         2           -0.0252
  0.9  cost_effective  0.874   57.4387     2.104        0.005    4              3              0.410           3         0           +0.0022
  0.8  cost_blind      0.874   57.4404     2.104        0.735    3              3              0.415           3         0           +0.0022
  0.9  cost_blind      0.874   57.4404     2.104        0.005    3              3              0.415           3         0           +0.0022
```

## Reading it

- One pooled task reduces routing to one model chosen per seed on half the items. On AutoBench, AutoBench judges and LiveCodeBench a seed that picks the best single model matches it and a seed that picks another loses, so routing can at best tie it: in `cost_blind`, where the passing sort reduces to the highest bound (5.3), the picks spread over 5, 2 and 2 models, the top pick's share is 0.600, 0.920 and 0.580, and routing reaches 0.857, 0.831 and 0.902 against 0.882, 0.835 and 0.909
- The bar is a floor, not a target: in `cost_effective` the router takes the cheapest model whose bound clears the bar (5.3), so a low bar buys cost with success. On RouterBench routing moves from 0.735 at 0.341 of the best single model's cost at bar 0.6 to 0.819 at 0.953 at bar 0.9; on AutoBench from 0.720 at 0.036 at bar 0.6 to 0.854 at 0.056 at bar 0.7; on AutoBench judges it reaches 0.816 at 0.518 at bars 0.6 and 0.7; on tau2-bench 0.547 at 0.144 at bar 0.3. README's AutoBench bullet adds that always calling one cheaper model, `openai/gpt-5.6-luna`, does as well on both counts; this script compares with the best single model only
- Per-task routing can gain in success only where tasks differ in their best model. Of the first five, RouterBench is the one file with many tasks: in `cost_blind` its picks spread over 8 models and 22 of the 65 tasks pick two or more across seeds, the same 22 that pick a model other than the best single one on some seed, of which 1 never picks it, yet the top pick takes 0.916 of the picks and routing reaches 0.819 at 0.963 of the best single model's cost against its 0.821, as does `best_on_calibration`. So on these tasks one model is the best or near it almost everywhere, and routing per task ends just below that one model. The file holds no per-task single-model rows, so this note cannot say on how many tasks another model is truly the best; LLMRouterBench, where it can be said, is the next section
- The halves decide how finely the bound can tell candidates apart: the shortfall is 0.129 at a half of 50 and 0.088 at 100 on RouterBench, 0.205 at 25 and 0.128 at 57 on tau2-bench, against 0.040 at 378 on AutoBench judges and 0.033 at 356 on LiveCodeBench
- On tau2-bench the airline task's expected half, 25, is below `min_samples` 30, and a seed's split varies around it; the per-seed airline, retail and telecom halves and the seeds where a model clears are in `evidence/tau2-bench/RESULTS.md` (its Reading it bullet on where routing per domain works), not in this file. Where no model clears, the router falls back to the highest bound (5.3, `best_available`). Over the 3 tasks and 50 seeds the cleared rate falls from 0.667 at bar 0.3 to 0.000 at bar 0.8, a bar above the best single model's 0.612, and `cost_blind` routing reaches 0.589

## Many-task data: LLMRouterBench (2026-11-09)

The finding of the first five files does not hold on LLMRouterBench: routing passes the best single model's held-out success there, in `cost_blind` at every bar and in `cost_effective` at the highest bars, each at less than half that model's cost, and it keeps most of the per-task gain that research/datasets.md measured on all items.

- Why it differs: its tasks differ in their best model, and its halves are large enough to tell. In `cost_blind` all 9 tasks pick a model other than `google/gemini-2.5-pro` on some seed and 5 on every seed, and at the median expected half, 374 items, the Wilson shortfall is 0.049, against 0.088 at RouterBench's median half of 100. [evidence/llmrouterbench/RESULTS.md](../evidence/llmrouterbench/RESULTS.md) names the 4 tasks routed to `openai/gpt-5` on every seed, a model about as good over all items at about half the cost
- `cost_blind`: 0.615 at every bar for 173.4190 USD, 0.473 of the best single model's 366.3999, a gain of +0.0223, level with `best_on_calibration`'s 0.615 at 171.3368. The bar moves only the cleared rate, from 0.944 at bar 0.1 to 0.256 at bar 0.8: the passing sort reduces to the highest bound (5.3), and a cell where no model clears falls back to that same model
- `cost_effective`: the gain runs from -0.0395 at bar 0.1, for 0.108 of the best single model's cost, to +0.0058 at bar 0.7 (0.598 at 0.353) and +0.0137 at bar 0.8 (0.606 at 0.420). So every routed row from bar 0.7 up costs less than the best single model and passes its held-out success, while below bar 0.7 `cost_effective` routing trades success for cost as on the first five files
- The in-sample gain kept: of the 0.0250, `best_on_calibration` and `cost_blind` routing keep 0.89, and `cost_effective` routing from -1.58 at the lowest bar to 0.55 at the highest. The in-sample gain picks each task's model in hindsight on all items and the held-out gains pick it on the calibration half and score it on the other, so read 0.89 as most of the gain surviving the split, not as an exact share
- The `aime` task's expected half, 30, equals `min_samples`, so the script counts no task below it, but its real half varies by seed and falls under it on some, where no model can clear; RESULTS.md counts those seeds

## Seventh file: LLM Routing Response Bank (2026-11-12)

On the LLM Routing Response Bank routing passes the best single model's held-out success too, in `cost_blind` at both bars and in `cost_effective` at the higher one, but by about a tenth of LLMRouterBench's gain and, unlike there, at more than twice that model's cost.

- `cost_blind`: 0.874 at both bars for 57.4404 USD, 2.104 times the 27.2956 of the best single model, `deepseek/deepseek-v4-pro`, a gain of +0.0022, level with `best_on_calibration`'s 0.874 at 57.4387. On LLMRouterBench the same row gains +0.0223 at 0.473 of its best single model's cost
- Where the cost comes from: in `cost_blind` every task picks `deepseek/deepseek-v4-pro` on some seed (`never best` 0, against 5 of LLMRouterBench's 9 tasks that never pick its best single model), but `mmlu_pro`, the largest task with 12032 items, picks `moonshotai/kimi-k2.7-code` on most seeds, a model that costs more than twice as much as the best single model to call on every item. The passing sort of `cost_blind` reduces to the highest bound (5.3) and does not look at price, so the model with the higher bound on the calibration half wins whatever it costs
- `cost_effective`: at bar 0.8, 0.847 at 0.201 of the best single model's cost, a gain of -0.0252, trading success for cost as on the first five files; at bar 0.9, where 0.005 of the cells clear, the router falls back to the highest bound (5.3, `best_available`) on nearly every cell and lands where `cost_blind` does, 0.874 at 2.104
- The halves are large but for one task: at the median expected half, 313, the Wilson shortfall is 0.041, near LLMRouterBench's 0.049 at 374, while `aime`'s expected half, 15, is below `min_samples` 30, the one task of the file whose half is

## What your own data needs

- A bar you mean, with cheaper models that clear it: `cost_effective` routing then saves the price gap and gives up success down toward the bar, which is the trade every saving above shows
- Calibration halves large enough that the shortfall at your success level is smaller than the gap between your bar and the models you hope will clear it; on these files it runs from 0.033 at a half of 356 to 0.251 at 15
- More than one task, split where the best model is likely to differ (by input kind, language or length), each with enough items for its own half; one pooled task can do no better than the best single model, while LLMRouterBench's benchmarks, routed one task each, pass it
- A baseline you could have chosen in advance, such as the model you call today, rather than the best single model of 12.7, which is chosen in hindsight on the held-out halves
- A look at what a gain in success costs: `cost_blind` ignores price by design, and on the LLM Routing Response Bank its gain of +0.0022 comes at 2.104 times the best single model's cost

## Limits

- The script reads the committed results files only. They hold no per-task single-model rows and no per-seed calibration sizes, so the note cannot name each task's best model, and its halves are the expected `int(items * calibration_fraction)`; [routerbench-per-task.md](routerbench-per-task.md) reads the pinned RouterBench file and names each eval's best model there
- The LLMRouterBench shares compare gains on different items, the in-sample one on all items with each task's model chosen in hindsight and the held-out ones on the halves, and the best single model they are measured from is itself chosen in hindsight on the held-out halves (12.7)
- Every held-out number here is a mean over the seeds of a results file; [llmrouterbench-seeds.md](llmrouterbench-seeds.md) reruns the LLMRouterBench evaluation and gives its gain over the best single model seed by seed
- The shortfall is taken at the best single model's success; a success nearer 0.5 has a larger one at the same half
- Costs are those each results file holds (recorded per call or priced at list, as each README subsection says); LiveCodeBench records none, so its cost columns are 0
- The bars, seeds and settings are those each results file was run with; a different bar grid or `min_samples` would move the cleared rates and the picks

## Regenerate

```text
python -m pip install -e .
python research/where_routing_pays.py
```

It reads the committed files, so a fresh checkout prints the Results block byte for byte; `tests/test_research_where_routing_pays.py` checks it on every run of the suite.
