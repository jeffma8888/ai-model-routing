# When no model clears the bar

Question: on a cell where no model clears the task's bar, a task whose `on_no_model` is `best_available` makes the router take the measured model with the highest calibration bound (`DESIGN.md` 5.3), in `cost_effective` as in `cost_blind`, whatever its price. Should a `cost_effective` router take the cheapest model there instead? Short answer: keep 5.3. On the four routing datasets that record a cost its fallback is the `best_on_calibration` model on every such cell, and the cheapest model loses most of the held-out success where the models are far apart (the whole RouterBench row at bar 0.9 falls from 0.819 to 0.351, the AutoBench one from 0.858 to 0.453). It saves cost for about the same success only where the models are close, as on tau2-bench at bars 0.3 to 0.6 and on the AutoBench judges.

## Facts

- In `cost_effective` no model clears on 19.6% to 88.9% of the RouterBench cells at bars 0.6 to 0.9, on none of the AutoBench or AutoBench judges cells at bars 0.6 and 0.7 and on 34.0% and 44.0% of them at 0.8, and on 33.3% to 100.0% of the tau2-bench cells at bars 0.3 to 0.8
- On every one of those cells the router's fallback is the `best_on_calibration` model, so the two rows are equal on every dataset and bar
- The cheapest model scores 0.165 to 0.257 of held-out success on those RouterBench cells against the fallback's 0.511 to 0.798, and reaches the bar on none of them; on AutoBench it scores 0.454 and 0.453 against 0.861 and 0.857
- On the AutoBench judges cells it scores 0.822 and 0.816 against 0.840 and 0.831, at 0.000164 USD per item against 0.000297 and 0.000306
- On tau2-bench at bars 0.4 to 0.6 the cheapest agent scores 0.448, 0.447 and 0.452 on those cells against the fallback's 0.440, 0.439 and 0.444, at 0.035493, 0.035056 and 0.034771 USD per item against 0.184082, 0.184417 and 0.182711; at bars 0.7 and 0.8 it loses 0.022 and 0.030 of the whole row's success for 74.5% and 88.4% less cost
- Recommendation: keep 5.3 in both flavors and add no `on_no_model` value; README Limitations says what the fallback costs on tau2-bench

## Method

- Datasets: the four routing evidence datasets whose outcomes carry a cost, [RouterBench](../evidence/routerbench/RESULTS.md) (`DESIGN.md` 12.7), [AutoBench](../evidence/autobench-2026/RESULTS.md) (12.10), [AutoBench judges](../evidence/autobench-judges/RESULTS.md) (12.12) and [tau2-bench](../evidence/tau2-bench/RESULTS.md) (12.15). LiveCodeBench records no cost, so a cheapest model is not defined there
- Each matrix is the one its RESULTS.md Regenerate block writes. [no_model_clears.py](no_model_clears.py) runs `evaluate` ([DESIGN.md](../DESIGN.md) 12.3) on it with the bars, seeds and options of the committed results file, on the `cost_effective` flavor alone, and stops unless the routed row it gets at each bar is the committed one
- A cell is one (bar, seed, task). No model clears it when its `cleared` is false: no candidate passes on the calibration half, so the router, which `evaluate` builds with `on_no_model="best_available"`, takes the 5.3 fallback, the measured model with the highest Wilson lower bound, then the lower cost
- Three choices are scored on the held-out halves of those cells: `fallback` (the routed model), `cheapest` (the model with the lowest mean calibration cost, the `cheapest` baseline of 12.3, which a fallback by price would take) and `best_on_calibration` (the highest calibration success, then the lower cost). Success is the held-out items a choice answered correctly over the held-out items, pooled over the cells; cost per item is the held-out cost over the same items; "at the bar or above" counts the cells whose held-out success reaches the bar
- The whole row is the bar's `cost_effective` routed row as 12.3's `summary` computes it, the mean over seeds of each seed's pooled success and of its summed cost: once as routed, and once with `cheapest` in place of the fallback on the cells where no model clears, the trade a fallback by price would make in the committed tables

## Results

```text
$ python research/no_model_clears.py --routerbench routerbench-matrix.jsonl --autobench autobench-matrix.jsonl --judges autobench-judges.jsonl --judges-registry autobench-models.json --tau2 tau2-matrix.jsonl
RouterBench (evidence/routerbench/results.json): 65 tasks, 11 models, bars 0.6, 0.7, 0.8, 0.9, 50 seeds
  bar 0.6: no model clears on 637 of 3,250 cost_effective cells (19.6%), 47,141 held-out items; tasks with such a cell: 21 of 65
    the routed model is best_on_calibration's on 637 and the cheapest model's on 0
    fallback             success 0.511  cost per item 0.002452 USD  at the bar or above on 188 (29.5%)
    cheapest             success 0.165  cost per item 0.000031 USD  at the bar or above on 0 (0.0%)
    best_on_calibration  success 0.511  cost per item 0.002452 USD  at the bar or above on 188 (29.5%)
    whole row: routed success 0.735 at 8.9478 USD; with the cheapest model as the fallback 0.712 at 6.6651 USD (success -0.023, cost -25.5%)
  bar 0.7: no model clears on 1,249 of 3,250 cost_effective cells (38.4%), 151,930 held-out items; tasks with such a cell: 34 of 65
    the routed model is best_on_calibration's on 1,249 and the cheapest model's on 0
    fallback             success 0.652  cost per item 0.002466 USD  at the bar or above on 522 (41.8%)
    cheapest             success 0.206  cost per item 0.000036 USD  at the bar or above on 0 (0.0%)
    best_on_calibration  success 0.652  cost per item 0.002466 USD  at the bar or above on 522 (41.8%)
    whole row: routed success 0.761 at 11.7482 USD; with the cheapest model as the fallback 0.665 at 4.3657 USD (success -0.096, cost -62.8%)
  bar 0.8: no model clears on 2,045 of 3,250 cost_effective cells (62.9%), 264,430 held-out items; tasks with such a cell: 50 of 65
    the routed model is best_on_calibration's on 2,045 and the cheapest model's on 0
    fallback             success 0.725  cost per item 0.001868 USD  at the bar or above on 752 (36.8%)
    cheapest             success 0.238  cost per item 0.000030 USD  at the bar or above on 0 (0.0%)
    best_on_calibration  success 0.725  cost per item 0.001868 USD  at the bar or above on 752 (36.8%)
    whole row: routed success 0.808 at 23.2560 USD; with the cheapest model as the fallback 0.625 at 13.5374 USD (success -0.183, cost -41.8%)
  bar 0.9: no model clears on 2,888 of 3,250 cost_effective cells (88.9%), 612,318 held-out items; tasks with such a cell: 61 of 65
    the routed model is best_on_calibration's on 2,888 and the cheapest model's on 0
    fallback             success 0.798  cost per item 0.001890 USD  at the bar or above on 626 (21.7%)
    cheapest             success 0.257  cost per item 0.000034 USD  at the bar or above on 0 (0.0%)
    best_on_calibration  success 0.798  cost per item 0.001890 USD  at the bar or above on 626 (21.7%)
    whole row: routed success 0.819 at 24.9963 USD; with the cheapest model as the fallback 0.351 at 2.2679 USD (success -0.469, cost -90.9%)

AutoBench (evidence/autobench-2026/results.json): 1 task, 20 models, bars 0.6, 0.7, 0.8, 0.9, 50 seeds
  bar 0.6: no model clears on 0 of 50 cost_effective cells (0.0%)
  bar 0.7: no model clears on 0 of 50 cost_effective cells (0.0%)
  bar 0.8: no model clears on 17 of 50 cost_effective cells (34.0%), 1,746 held-out items; by task: all 17
    the routed model is best_on_calibration's on 17 and the cheapest model's on 0
    fallback             success 0.861  cost per item 0.033002 USD  at the bar or above on 16 (94.1%)
    cheapest             success 0.454  cost per item 0.000185 USD  at the bar or above on 0 (0.0%)
    best_on_calibration  success 0.861  cost per item 0.033002 USD  at the bar or above on 16 (94.1%)
    whole row: routed success 0.855 at 2.9694 USD; with the cheapest model as the fallback 0.716 at 1.8234 USD (success -0.139, cost -38.6%)
  bar 0.9: no model clears on 50 of 50 cost_effective cells (100.0%), 5,072 held-out items; by task: all 50
    the routed model is best_on_calibration's on 50 and the cheapest model's on 0
    fallback             success 0.857  cost per item 0.036016 USD  at the bar or above on 2 (4.0%)
    cheapest             success 0.453  cost per item 0.000188 USD  at the bar or above on 0 (0.0%)
    best_on_calibration  success 0.857  cost per item 0.036016 USD  at the bar or above on 2 (4.0%)
    whole row: routed success 0.858 at 3.6535 USD; with the cheapest model as the fallback 0.453 at 0.0191 USD (success -0.404, cost -99.5%)

AutoBench judges (evidence/autobench-judges/results.json): 1 task, 5 models, bars 0.6, 0.7, 0.8, 0.9, 50 seeds
  bar 0.6: no model clears on 0 of 50 cost_effective cells (0.0%)
  bar 0.7: no model clears on 0 of 50 cost_effective cells (0.0%)
  bar 0.8: no model clears on 22 of 50 cost_effective cells (44.0%), 8,256 held-out items; by task: all 22
    the routed model is best_on_calibration's on 22 and the cheapest model's on 3
    fallback             success 0.840  cost per item 0.000297 USD  at the bar or above on 22 (100.0%)
    cheapest             success 0.822  cost per item 0.000164 USD  at the bar or above on 22 (100.0%)
    best_on_calibration  success 0.840  cost per item 0.000297 USD  at the bar or above on 22 (100.0%)
    whole row: routed success 0.831 at 0.1135 USD; with the cheapest model as the fallback 0.823 at 0.0916 USD (success -0.008, cost -19.3%)
  bar 0.9: no model clears on 50 of 50 cost_effective cells (100.0%), 18,757 held-out items; by task: all 50
    the routed model is best_on_calibration's on 50 and the cheapest model's on 4
    fallback             success 0.831  cost per item 0.000306 USD  at the bar or above on 0 (0.0%)
    cheapest             success 0.816  cost per item 0.000164 USD  at the bar or above on 0 (0.0%)
    best_on_calibration  success 0.831  cost per item 0.000306 USD  at the bar or above on 0 (0.0%)
    whole row: routed success 0.831 at 0.1146 USD; with the cheapest model as the fallback 0.816 at 0.0617 USD (success -0.016, cost -46.2%)

tau2-bench (evidence/tau2-bench/results.json): 3 tasks, 4 models, bars 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 50 seeds
  bar 0.3: no model clears on 50 of 150 cost_effective cells (33.3%), 1,626 held-out items; by task: airline 40, retail 0, telecom 10
    the routed model is best_on_calibration's on 50 and the cheapest model's on 11
    fallback             success 0.498  cost per item 0.115595 USD  at the bar or above on 49 (98.0%)
    cheapest             success 0.491  cost per item 0.023014 USD  at the bar or above on 50 (100.0%)
    best_on_calibration  success 0.498  cost per item 0.115595 USD  at the bar or above on 49 (98.0%)
    whole row: routed success 0.547 at 9.1340 USD; with the cheapest model as the fallback 0.546 at 6.1233 USD (success -0.002, cost -33.0%)
  bar 0.4: no model clears on 90 of 150 cost_effective cells (60.0%), 3,784 held-out items; by task: airline 42, retail 0, telecom 48
    the routed model is best_on_calibration's on 90 and the cheapest model's on 28
    fallback             success 0.440  cost per item 0.184082 USD  at the bar or above on 66 (73.3%)
    cheapest             success 0.448  cost per item 0.035493 USD  at the bar or above on 73 (81.1%)
    best_on_calibration  success 0.440  cost per item 0.184082 USD  at the bar or above on 66 (73.3%)
    whole row: routed success 0.544 at 15.6738 USD; with the cheapest model as the fallback 0.548 at 4.4285 USD (success +0.004, cost -71.7%)
  bar 0.5: no model clears on 100 of 150 cost_effective cells (66.7%), 4,041 held-out items; by task: airline 50, retail 0, telecom 50
    the routed model is best_on_calibration's on 100 and the cheapest model's on 29
    fallback             success 0.439  cost per item 0.184417 USD  at the bar or above on 35 (35.0%)
    cheapest             success 0.447  cost per item 0.035056 USD  at the bar or above on 31 (31.0%)
    best_on_calibration  success 0.439  cost per item 0.184417 USD  at the bar or above on 35 (35.0%)
    whole row: routed success 0.545 at 16.4831 USD; with the cheapest model as the fallback 0.550 at 4.4118 USD (success +0.005, cost -73.2%)
  bar 0.6: no model clears on 101 of 150 cost_effective cells (67.3%), 4,096 held-out items; by task: airline 50, retail 1, telecom 50
    the routed model is best_on_calibration's on 101 and the cheapest model's on 29
    fallback             success 0.444  cost per item 0.182711 USD  at the bar or above on 7 (6.9%)
    cheapest             success 0.452  cost per item 0.034771 USD  at the bar or above on 3 (3.0%)
    best_on_calibration  success 0.444  cost per item 0.182711 USD  at the bar or above on 7 (6.9%)
    whole row: routed success 0.559 at 24.2031 USD; with the cheapest model as the fallback 0.563 at 12.0839 USD (success +0.005, cost -50.1%)
  bar 0.7: no model clears on 138 of 150 cost_effective cells (92.0%), 6,202 held-out items; by task: airline 50, retail 38, telecom 50
    the routed model is best_on_calibration's on 138 and the cheapest model's on 29
    fallback             success 0.558  cost per item 0.212550 USD  at the bar or above on 33 (23.9%)
    cheapest             success 0.534  cost per item 0.027515 USD  at the bar or above on 18 (13.0%)
    best_on_calibration  success 0.558  cost per item 0.212550 USD  at the bar or above on 33 (23.9%)
    whole row: routed success 0.578 at 30.7979 USD; with the cheapest model as the fallback 0.556 at 7.8462 USD (success -0.022, cost -74.5%)
  bar 0.8: no model clears on 150 of 150 cost_effective cells (100.0%), 6,909 held-out items; by task: airline 50, retail 50, telecom 50
    the routed model is best_on_calibration's on 150 and the cheapest model's on 29
    fallback             success 0.578  cost per item 0.225041 USD  at the bar or above on 19 (12.7%)
    cheapest             success 0.549  cost per item 0.026085 USD  at the bar or above on 0 (0.0%)
    best_on_calibration  success 0.578  cost per item 0.225041 USD  at the bar or above on 19 (12.7%)
    whole row: routed success 0.578 at 31.0962 USD; with the cheapest model as the fallback 0.548 at 3.6044 USD (success -0.030, cost -88.4%)
```

## Reading it

- The fallback is the `best_on_calibration` model on every cell where no model clears. Every model of a matrix is measured on the same calibration items, so the highest Wilson bound goes with the highest calibration success, and both break a tie by the lower cost. The question is therefore the best model on the calibration half or the cheapest one
- What decides it is how far the cheapest model sits below the best. On RouterBench the cheapest model reaches the bar on 0 of the cells at every bar, and with it as the fallback the whole row's success falls by 0.023 at bar 0.6 and by 0.469 at bar 0.9, where no model clears on 88.9% of the cells; on AutoBench it falls by 0.139 and 0.404 at bars 0.8 and 0.9
- On tau2-bench the four agents are close on these cells. At bars 0.3 to 0.6 the whole row moves by -0.002, +0.004, +0.005 and +0.005 with the cheapest agent as the fallback, for 33.0%, 71.7%, 73.2% and 50.1% less cost. At bar 0.3 the cells where no model clears are airline 40 and telecom 10: the airline ones are the seeds whose calibration half is under `min_samples` (the tau2-bench RESULTS.md gives the split sizes), where no agent can clear at any bar
- On the AutoBench judges the cheapest judge reaches the bar on all 22 cells at bar 0.8, as the fallback does, and the whole row loses 0.008 of success for 19.3% less cost; at 0.9 it loses 0.016 for 46.2% less
- The delegation decision has the same question when neither path clears, and [no-path-clears.md](no-path-clears.md) kept its rule (13.5 row 7) for the same reason: the choice by bound scores highest on the held-out halves

## Recommendation

- Keep 5.3 as it is in both flavors, and keep `refuse` as the default of `on_no_model`. A fallback by price would cut the whole row's cost by 19.3% to 99.5% on these datasets, but where the models are far apart it gives up most of the success the fallback keeps: 0.469 on RouterBench and 0.404 on AutoBench at bar 0.9. Where it saves on tau2-bench, its success gain on the whole row is at most 0.005
- Add no `on_no_model` value now. A user who wants the cheaper model where nothing clears can set a bar it clears, or `refuse` and handle `NoModelClearsBar`
- A rule between the two, the cheapest model whose calibration success cannot be told apart from the best's, might keep the tau2-bench saving without the RouterBench loss. The cells keep no calibration counts, so it is not measured here; it would be a new research row before any spec change

## Limits

- Calibration and held-out halves are each dataset's own seeded splits, so this compares the choices on held-out halves of the same data, not on new data
- Two of the four datasets route one pooled task (AutoBench and the AutoBench judges), so their cells are seeds of one task; RouterBench's are 65 tasks, tau2-bench's 3
- `cheapest` is the model with the lowest mean calibration cost, whatever its success; no choice that weighs cost against the bound is measured here
- Costs are each results file's own (12.7, 12.10, 12.12 and 12.15 say how each is priced)

## Regenerate

```bash
python -m pip install -e ".[evidence]"
python evidence/routerbench/convert.py --out routerbench-matrix.jsonl
python evidence/autobench-2026/convert.py --out autobench-matrix.jsonl --task-by all
python evidence/autobench-2026/judges.py --out autobench-judges.jsonl --registry autobench-models.json
python evidence/tau2-bench/convert.py --out tau2-matrix.jsonl
python research/no_model_clears.py --routerbench routerbench-matrix.jsonl --autobench autobench-matrix.jsonl --judges autobench-judges.jsonl --judges-registry autobench-models.json --tau2 tau2-matrix.jsonl
```
