# Where task-level routing pays on the committed evidence

README Results at a glance shows routing costing less than the best single model on some datasets and never reaching that model's held-out success on any. This note reads the five committed routing results files to say why, and what a user's own data needs for routing to pay. Its numbers are the output of [where_routing_pays.py](where_routing_pays.py), which reads only those files (`DESIGN.md` 12.8).

## Facts

- Files read, nothing downloaded: `evidence/routerbench/results.json`, `evidence/autobench-2026/results.json`, `evidence/autobench-judges/results.json`, `evidence/tau2-bench/results.json` and `evidence/livecodebench/results.json`
- Tasks routed: 65 on RouterBench, 3 on tau2-bench, 1 each on AutoBench, AutoBench judges and LiveCodeBench
- On all five, no routed row at any bar or flavor reaches the best single model's held-out success, and neither does `best_on_calibration`, each task's best model on its calibration half with no bar: 0.819 against 0.821 on RouterBench, 0.858 against 0.882 on AutoBench, 0.831 against 0.835 on AutoBench judges, 0.578 against 0.612 on tau2-bench and 0.902 against 0.909 on LiveCodeBench
- The best single model is the one with the highest held-out success (12.7), so it is chosen on the very items it is scored on; it is a reference no rule that sees only a calibration half can be sure to pick
- Where routing pays on these files is cost: at a bar below the best single model's success, `cost_effective` routing takes cheaper models that clear it, for example 0.735 at 0.341 of the best single model's cost at bar 0.6 on RouterBench and 0.854 at 0.056 at bar 0.7 on AutoBench
- A gain in success would need tasks that differ in their best model and calibration halves large enough to tell the candidates apart; three of the five files route one pooled task, and on RouterBench's 65 tasks the top pick takes 0.916 of the `cost_blind` picks

## Method

- For each file the script prints the tasks, models, seeds and run settings; the items per task and the expected calibration half, `int(items * calibration_fraction)` (the 12.2 split hashes each item with the seed, so the real count varies by seed, and the files do not record it); and the number of tasks whose half is below `min_samples`
- The best single model is chosen among the `model:` summary rows as in 12.7, highest held-out success, then lower cost, then ID; the script requires it to be the same at every bar and flavor. `best_on_calibration` is the 12.3 baseline at the first bar and flavor
- The Wilson shortfall is the best single model's held-out success minus the Wilson lower bound of that success observed on n items at the run's confidence (`model_routing.stats.wilson_lower_bound`, the bound the router uses), at the smallest half and, when it differs, the median half. A model's calibration success must sit about that far above the bar for its bound to clear it (5.3), and two models closer than that can trade places from seed to seed
- Per flavor and bar: the routed held-out success, cost, cost over the best single model's (`-` when that is 0, as on LiveCodeBench), cleared rate, and, from each task's `routed_models` (the model picked on each seed), the number of distinct models picked, the number of tasks whose pick changes between seeds, and the most-picked model's share of all task and seed picks

## Results

```text
$ python research/where_routing_pays.py
RouterBench (evidence/routerbench/results.json): 65 tasks, 11 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: 100 to 10042, median 201; expected calibration half: 50 to 5021, median 100; tasks whose half is below min_samples: 0
  best single model: openai/gpt-4-1106-preview, held-out success 0.821 at 26.2358 USD; Wilson shortfall of that success: 0.129 at a half of 50, 0.088 at 100
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.819 at 25.0029 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share
  0.6  cost_effective  0.735   8.9478      0.341        0.804    9              41             0.446
  0.7  cost_effective  0.761   11.7482     0.448        0.616    8              39             0.615
  0.8  cost_effective  0.808   23.2560     0.886        0.371    8              31             0.819
  0.9  cost_effective  0.819   24.9963     0.953        0.111    8              22             0.911
  0.6  cost_blind      0.819   25.2675     0.963        0.804    8              22             0.916
  0.7  cost_blind      0.819   25.2675     0.963        0.616    8              22             0.916
  0.8  cost_blind      0.819   25.2675     0.963        0.371    8              22             0.916
  0.9  cost_blind      0.819   25.2675     0.963        0.111    8              22             0.916

AutoBench (evidence/autobench-2026/results.json): 1 task, 20 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: all 203; expected calibration half: 101; tasks whose half is below min_samples: 0
  best single model: openai/gpt-5.6-sol, held-out success 0.882 at 5.5616 USD; Wilson shortfall of that success: 0.079 at a half of 101
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.858 at 3.6535 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share
  0.6  cost_effective  0.720   0.1976      0.036        1.000    5              1              0.400
  0.7  cost_effective  0.854   0.3110      0.056        1.000    3              1              0.900
  0.8  cost_effective  0.855   2.9694      0.534        0.660    5              1              0.460
  0.9  cost_effective  0.858   3.6535      0.657        0.000    5              1              0.600
  0.6  cost_blind      0.857   3.6917      0.664        1.000    5              1              0.600
  0.7  cost_blind      0.857   3.6917      0.664        1.000    5              1              0.600
  0.8  cost_blind      0.857   3.6917      0.664        0.660    5              1              0.600
  0.9  cost_blind      0.857   3.6917      0.664        0.000    5              1              0.600

AutoBench judges (evidence/autobench-judges/results.json): 1 task, 5 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: all 756; expected calibration half: 378; tasks whose half is below min_samples: 0
  best single model: tencent/hy3, held-out success 0.835 at 0.1192 USD; Wilson shortfall of that success: 0.040 at a half of 378
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.831 at 0.1146 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share
  0.6  cost_effective  0.816   0.0617      0.518        1.000    1              0              1.000
  0.7  cost_effective  0.816   0.0617      0.518        1.000    1              0              1.000
  0.8  cost_effective  0.831   0.1135      0.953        0.560    2              1              0.900
  0.9  cost_effective  0.831   0.1146      0.962        0.000    2              1              0.920
  0.6  cost_blind      0.831   0.1146      0.962        1.000    2              1              0.920
  0.7  cost_blind      0.831   0.1146      0.962        1.000    2              1              0.920
  0.8  cost_blind      0.831   0.1146      0.962        0.560    2              1              0.920
  0.9  cost_blind      0.831   0.1146      0.962        0.000    2              1              0.920

tau2-bench (evidence/tau2-bench/results.json): 3 tasks, 4 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: airline 50, retail 114, telecom 114; expected calibration half: 25, 57, 57; tasks whose half is below min_samples: 1
  best single model: anthropic/claude-3-7-sonnet-20250219, held-out success 0.612 at 63.2133 USD; Wilson shortfall of that success: 0.205 at a half of 25, 0.128 at 57
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.578 at 31.0962 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share
  0.3  cost_effective  0.547   9.1340      0.144        0.667    4              2              0.680
  0.4  cost_effective  0.544   15.6738     0.248        0.400    4              2              0.527
  0.5  cost_effective  0.545   16.4831     0.261        0.333    4              3              0.473
  0.6  cost_effective  0.559   24.2031     0.383        0.327    4              3              0.320
  0.7  cost_effective  0.578   30.7979     0.487        0.080    4              3              0.413
  0.8  cost_effective  0.578   31.0962     0.492        0.000    4              3              0.420
  0.3  cost_blind      0.589   40.3751     0.639        0.667    4              3              0.580
  0.4  cost_blind      0.589   40.3751     0.639        0.400    4              3              0.580
  0.5  cost_blind      0.589   40.3751     0.639        0.333    4              3              0.580
  0.6  cost_blind      0.589   40.3751     0.639        0.327    4              3              0.580
  0.7  cost_blind      0.589   40.3751     0.639        0.080    4              3              0.580
  0.8  cost_blind      0.589   40.3751     0.639        0.000    4              3              0.580

LiveCodeBench (evidence/livecodebench/results.json): 1 task, 67 models, 50 seeds, calibration_fraction 0.5, min_samples 30, confidence 0.95
  items per task: code_generation 713; expected calibration half: 356; tasks whose half is below min_samples: 0
  best single model: openai/o4-mini-high, held-out success 0.909 at 0.0000 USD; Wilson shortfall of that success: 0.033 at a half of 356
  best_on_calibration (each task's best model on its half, no bar): held-out success 0.902 at 0.0000 USD
  not in the file: each task's single-model rows (per_task holds the routed rows only) and each seed's calibration size (the seeded hash split of 12.2 varies it)
  bar  flavor          routed  cost (USD)  cost / best  cleared  models picked  tasks with 2+  top pick share
  0.1  cost_blind      0.902   0.0000      -            1.000    2              1              0.580
  0.2  cost_blind      0.902   0.0000      -            1.000    2              1              0.580
  0.3  cost_blind      0.902   0.0000      -            1.000    2              1              0.580
  0.4  cost_blind      0.902   0.0000      -            1.000    2              1              0.580
  0.5  cost_blind      0.902   0.0000      -            1.000    2              1              0.580
  0.6  cost_blind      0.902   0.0000      -            1.000    2              1              0.580
  0.7  cost_blind      0.902   0.0000      -            1.000    2              1              0.580
  0.8  cost_blind      0.902   0.0000      -            1.000    2              1              0.580
  0.9  cost_blind      0.902   0.0000      -            0.180    2              1              0.580
```

## Reading it

- One pooled task reduces routing to one model chosen per seed on half the items. On AutoBench, AutoBench judges and LiveCodeBench a seed that picks the best single model matches it and a seed that picks another loses, so routing can at best tie it: in `cost_blind`, where the passing sort reduces to the highest bound (5.3), the picks spread over 5, 2 and 2 models, the top pick's share is 0.600, 0.920 and 0.580, and routing reaches 0.857, 0.831 and 0.902 against 0.882, 0.835 and 0.909
- The bar is a floor, not a target: in `cost_effective` the router takes the cheapest model whose bound clears the bar (5.3), so a low bar buys cost with success. On RouterBench routing moves from 0.735 at 0.341 of the best single model's cost at bar 0.6 to 0.819 at 0.953 at bar 0.9; on AutoBench from 0.720 at 0.036 at bar 0.6 to 0.854 at 0.056 at bar 0.7; on AutoBench judges it reaches 0.816 at 0.518 at bars 0.6 and 0.7; on tau2-bench 0.547 at 0.144 at bar 0.3. README's AutoBench bullet adds that always calling one cheaper model, `openai/gpt-5.6-luna`, does as well on both counts; this script compares with the best single model only
- Per-task routing can gain in success only where tasks differ in their best model. RouterBench is the one file with many tasks: in `cost_blind` its picks spread over 8 models and 22 of the 65 tasks pick two or more across seeds, yet the top pick takes 0.916 of the picks and routing reaches 0.819 at 0.963 of the best single model's cost against its 0.821, as does `best_on_calibration`. So on these tasks one model is the best or near it almost everywhere, and the per-task differences that exist do not make up for choosing on a half. The file holds no per-task single-model rows, so this note cannot say on how many tasks another model is truly the best
- The halves decide how finely the bound can tell candidates apart: the shortfall is 0.129 at a half of 50 and 0.088 at 100 on RouterBench, 0.205 at 25 and 0.128 at 57 on tau2-bench, against 0.040 at 378 on AutoBench judges and 0.033 at 356 on LiveCodeBench
- On tau2-bench the airline task's expected half, 25, is below `min_samples` 30, so a model can clear there only on a seed whose split gives it 30 or more calibration items, and otherwise the router falls back to the highest bound (5.3, `best_available`); the cleared rate falls from 0.667 at bar 0.3 to 0.000 at bar 0.8, and `cost_blind` routing reaches 0.589 against 0.612

## What your own data needs

- A bar you mean, with cheaper models that clear it: `cost_effective` routing then saves the price gap and gives up success down toward the bar, which is the trade every saving above shows
- Calibration halves large enough that the shortfall at your success level is smaller than the gap between your bar and the models you hope will clear it; on these files it runs from 0.033 at a half of 356 to 0.205 at 25
- More than one task, split where the best model is likely to differ (by input kind, language or length), each with enough items for its own half; one pooled task can do no better than the best single model
- A baseline you could have chosen in advance, such as the model you call today, rather than the best single model of 12.7, which is chosen on the scored items

## Limits

- The script reads the committed results files only. They hold no per-task single-model rows and no per-seed calibration sizes, so the note cannot name each task's best model, and its halves are the expected `int(items * calibration_fraction)`
- The shortfall is taken at the best single model's success; a success nearer 0.5 has a larger one at the same half
- Costs are those each results file holds (recorded per call or priced at list, as each README subsection says); LiveCodeBench records none, so its cost columns are 0
- The bars, seeds and settings are those each results file was run with; a different bar grid or `min_samples` would move the cleared rates and the picks

## Regenerate

```text
python -m pip install -e .
python research/where_routing_pays.py
```

It reads the committed files, so a fresh checkout prints the Results block byte for byte; `tests/test_research_where_routing_pays.py` checks it on every run of the suite.
