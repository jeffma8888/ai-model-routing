# When no model clears the bar

Question: on a cell where no model clears the task's bar, a task whose `on_no_model` is `best_available` makes the router take the measured model with the highest calibration bound (`DESIGN.md` 5.3), in `cost_effective` as in `cost_blind`, whatever its price. Should a `cost_effective` router take the cheapest model there instead? Short answer: keep 5.3. On the six routing datasets that record a cost its fallback is the `best_on_calibration` model on every such cell, and the cheapest model loses most of the held-out success where the models are far apart (the whole RouterBench row at bar 0.9 falls from 0.819 to 0.351, the AutoBench one from 0.858 to 0.453). It saves cost for about the same success only where the models are close, as on tau2-bench at bars 0.3 to 0.6 and on the AutoBench judges. On LLMRouterBench and the LLM Routing Response Bank it raises the whole row's success at no bar, and its large savings cost 0.041 to 0.055 of it on LLMRouterBench at bars 0.3 to 0.8 and 0.027 on the response bank at bar 0.9.

## Facts

- In `cost_effective` no model clears on 19.6% to 88.9% of the RouterBench cells at bars 0.6 to 0.9, on none of the AutoBench or AutoBench judges cells at bars 0.6 and 0.7 and on 34.0% and 44.0% of them at 0.8, on 33.3% to 100.0% of the tau2-bench cells at bars 0.3 to 0.8, on 5.6% to 74.4% of the LLMRouterBench cells at bars 0.1 to 0.8 and on 26.5% and 99.5% of the response-bank cells at bars 0.8 and 0.9
- On every one of those cells the router's fallback is the `best_on_calibration` model, so the two rows are equal on every dataset and bar
- The cheapest model scores 0.165 to 0.257 of held-out success on those RouterBench cells against the fallback's 0.511 to 0.798, and reaches the bar on none of them; on AutoBench it scores 0.454 and 0.453 against 0.861 and 0.857
- On the AutoBench judges cells it scores 0.822 and 0.816 against 0.840 and 0.831, at 0.000164 USD per item against 0.000297 and 0.000306
- On tau2-bench at bars 0.4 to 0.6 the cheapest agent scores 0.448, 0.447 and 0.452 on those cells against the fallback's 0.440, 0.439 and 0.444, at 0.035493, 0.035056 and 0.034771 USD per item against 0.184082, 0.184417 and 0.182711; at bars 0.7 and 0.8 it loses 0.022 and 0.030 of the whole row's success for 74.5% and 88.4% less cost
- On LLMRouterBench the cheapest model scores 0.046 to 0.706 on those cells against the fallback's 0.269 to 0.844; with it as the fallback the whole row loses 0.041 to 0.055 of success at bars 0.3 to 0.8 for 70.3% to 96.5% less cost
- On the response bank it scores 0.929 and 0.847 against 0.932 and 0.874 at bars 0.8 and 0.9; the whole row keeps its 0.847 at bar 0.8 for 0.6% less cost and loses 0.027 at bar 0.9 for 90.5% less
- Recommendation: keep 5.3 in both flavors and add no `on_no_model` value; README Limitations says what the fallback costs on tau2-bench. LLMRouterBench and the response bank, read since 2026-11-13, leave it as it was

## Method

- Datasets: the six routing evidence datasets whose outcomes carry a cost, [RouterBench](../evidence/routerbench/RESULTS.md) (`DESIGN.md` 12.7), [AutoBench](../evidence/autobench-2026/RESULTS.md) (12.10), [AutoBench judges](../evidence/autobench-judges/RESULTS.md) (12.12), [tau2-bench](../evidence/tau2-bench/RESULTS.md) (12.15), [LLMRouterBench](../evidence/llmrouterbench/RESULTS.md) (12.19) and the [LLM Routing Response Bank](../evidence/response-bank/RESULTS.md) (12.21). LiveCodeBench records no cost, so a cheapest model is not defined there
- Each matrix is the one its RESULTS.md Regenerate block writes. [no_model_clears.py](no_model_clears.py) runs `evaluate` ([DESIGN.md](../DESIGN.md) 12.3) on it with the bars, seeds and options of the committed results file, on the `cost_effective` flavor alone, and stops unless the routed row it gets at each bar is the committed one
- A cell is one (bar, seed, task). No model clears it when its `cleared` is false: no candidate passes on the calibration half, so the router, which `evaluate` builds with `on_no_model="best_available"`, takes the 5.3 fallback, the measured model with the highest Wilson lower bound, then the lower cost
- Three choices are scored on the held-out halves of those cells: `fallback` (the routed model), `cheapest` (the model with the lowest mean calibration cost, the `cheapest` baseline of 12.3, which a fallback by price would take) and `best_on_calibration` (the highest calibration success, then the lower cost). Success is the held-out items a choice answered correctly over the held-out items, pooled over the cells; cost per item is the held-out cost over the same items; "at the bar or above" counts the cells whose held-out success reaches the bar
- The whole row is the bar's `cost_effective` routed row as 12.3's `summary` computes it, the mean over seeds of each seed's pooled success and of its summed cost: once as routed, and once with `cheapest` in place of the fallback on the cells where no model clears, the trade a fallback by price would make in the committed tables

## Results

```text
$ python research/no_model_clears.py --routerbench routerbench-matrix.jsonl --autobench autobench-matrix.jsonl --judges autobench-judges.jsonl --judges-registry autobench-models.json --tau2 tau2-matrix.jsonl --llmrouterbench llmrouterbench-matrix.jsonl --response-bank response-bank-matrix.jsonl
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

LLMRouterBench (evidence/llmrouterbench/results.json): 9 tasks, 13 models, bars 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 50 seeds
  bar 0.1: no model clears on 25 of 450 cost_effective cells (5.6%), 832 held-out items; tasks with such a cell: 1 of 9
    the routed model is best_on_calibration's on 25 and the cheapest model's on 0
    fallback             success 0.844  cost per item 0.059655 USD  at the bar or above on 25 (100.0%)
    cheapest             success 0.706  cost per item 0.001325 USD  at the bar or above on 25 (100.0%)
    best_on_calibration  success 0.844  cost per item 0.059655 USD  at the bar or above on 25 (100.0%)
    whole row: routed success 0.553 at 39.4802 USD; with the cheapest model as the fallback 0.552 at 38.5096 USD (success -0.000, cost -2.5%)
  bar 0.2: no model clears on 25 of 450 cost_effective cells (5.6%), 832 held-out items; tasks with such a cell: 1 of 9
    the routed model is best_on_calibration's on 25 and the cheapest model's on 0
    fallback             success 0.844  cost per item 0.059655 USD  at the bar or above on 25 (100.0%)
    cheapest             success 0.706  cost per item 0.001325 USD  at the bar or above on 25 (100.0%)
    best_on_calibration  success 0.844  cost per item 0.059655 USD  at the bar or above on 25 (100.0%)
    whole row: routed success 0.576 at 86.9437 USD; with the cheapest model as the fallback 0.576 at 85.9731 USD (success -0.000, cost -1.1%)
  bar 0.3: no model clears on 75 of 450 cost_effective cells (16.7%), 54,773 held-out items; tasks with such a cell: 2 of 9
    the routed model is best_on_calibration's on 75 and the cheapest model's on 0
    fallback             success 0.269  cost per item 0.063719 USD  at the bar or above on 25 (33.3%)
    cheapest             success 0.046  cost per item 0.000905 USD  at the bar or above on 25 (33.3%)
    best_on_calibration  success 0.269  cost per item 0.063719 USD  at the bar or above on 25 (33.3%)
    whole row: routed success 0.580 at 97.9296 USD; with the cheapest model as the fallback 0.539 at 29.1192 USD (success -0.041, cost -70.3%)
  bar 0.4: no model clears on 76 of 450 cost_effective cells (16.9%), 54,980 held-out items; tasks with such a cell: 3 of 9
    the routed model is best_on_calibration's on 76 and the cheapest model's on 0
    fallback             success 0.270  cost per item 0.063950 USD  at the bar or above on 26 (34.2%)
    cheapest             success 0.046  cost per item 0.000909 USD  at the bar or above on 25 (32.9%)
    best_on_calibration  success 0.270  cost per item 0.063950 USD  at the bar or above on 26 (34.2%)
    whole row: routed success 0.580 at 97.9296 USD; with the cheapest model as the fallback 0.539 at 28.6096 USD (success -0.041, cost -70.8%)
  bar 0.5: no model clears on 125 of 450 cost_effective cells (27.8%), 64,770 held-out items; tasks with such a cell: 3 of 9
    the routed model is best_on_calibration's on 125 and the cheapest model's on 0
    fallback             success 0.308  cost per item 0.074077 USD  at the bar or above on 69 (55.2%)
    cheapest             success 0.078  cost per item 0.001097 USD  at the bar or above on 25 (20.0%)
    best_on_calibration  success 0.308  cost per item 0.074077 USD  at the bar or above on 69 (55.2%)
    whole row: routed success 0.581 at 97.9935 USD; with the cheapest model as the fallback 0.532 at 3.4549 USD (success -0.049, cost -96.5%)
  bar 0.6: no model clears on 181 of 450 cost_effective cells (40.2%), 174,307 held-out items; tasks with such a cell: 6 of 9
    the routed model is best_on_calibration's on 181 and the cheapest model's on 28
    fallback             success 0.452  cost per item 0.030297 USD  at the bar or above on 31 (17.1%)
    cheapest             success 0.368  cost per item 0.000444 USD  at the bar or above on 30 (16.6%)
    best_on_calibration  success 0.452  cost per item 0.030297 USD  at the bar or above on 31 (17.1%)
    whole row: routed success 0.586 at 113.9149 USD; with the cheapest model as the fallback 0.537 at 9.8437 USD (success -0.049, cost -91.4%)
  bar 0.7: no model clears on 255 of 450 cost_effective cells (56.7%), 193,622 held-out items; tasks with such a cell: 6 of 9
    the routed model is best_on_calibration's on 255 and the cheapest model's on 30
    fallback             success 0.473  cost per item 0.030646 USD  at the bar or above on 52 (20.4%)
    cheapest             success 0.393  cost per item 0.000502 USD  at the bar or above on 20 (7.8%)
    best_on_calibration  success 0.473  cost per item 0.030646 USD  at the bar or above on 52 (20.4%)
    whole row: routed success 0.598 at 129.3241 USD; with the cheapest model as the fallback 0.547 at 12.5916 USD (success -0.051, cost -90.3%)
  bar 0.8: no model clears on 335 of 450 cost_effective cells (74.4%), 199,394 held-out items; tasks with such a cell: 7 of 9
    the routed model is best_on_calibration's on 335 and the cheapest model's on 30
    fallback             success 0.483  cost per item 0.031296 USD  at the bar or above on 89 (26.6%)
    cheapest             success 0.399  cost per item 0.000506 USD  at the bar or above on 3 (0.9%)
    best_on_calibration  success 0.483  cost per item 0.031296 USD  at the bar or above on 89 (26.6%)
    whole row: routed success 0.606 at 154.0269 USD; with the cheapest model as the fallback 0.551 at 31.2414 USD (success -0.055, cost -79.7%)

LLM Routing Response Bank (evidence/response-bank/results.json): 4 tasks, 5 models, bars 0.8, 0.9, 50 seeds
  bar 0.8: no model clears on 53 of 200 cost_effective cells (26.5%), 1,063 held-out items; by task: aime 50, gpqa_diamond 3, livecodebench 0, mmlu_pro 0
    the routed model is best_on_calibration's on 53 and the cheapest model's on 27
    fallback             success 0.932  cost per item 0.006832 USD  at the bar or above on 52 (98.1%)
    cheapest             success 0.929  cost per item 0.005311 USD  at the bar or above on 51 (96.2%)
    best_on_calibration  success 0.932  cost per item 0.006832 USD  at the bar or above on 52 (98.1%)
    whole row: routed success 0.847 at 5.4902 USD; with the cheapest model as the fallback 0.847 at 5.4579 USD (success -0.000, cost -0.6%)
  bar 0.9: no model clears on 199 of 200 cost_effective cells (99.5%), 332,531 held-out items; by task: aime 50, gpqa_diamond 49, livecodebench 50, mmlu_pro 50
    the routed model is best_on_calibration's on 199 and the cheapest model's on 67
    fallback             success 0.874  cost per item 0.008636 USD  at the bar or above on 85 (42.7%)
    cheapest             success 0.847  cost per item 0.000816 USD  at the bar or above on 65 (32.7%)
    best_on_calibration  success 0.874  cost per item 0.008636 USD  at the bar or above on 85 (42.7%)
    whole row: routed success 0.874 at 57.4387 USD; with the cheapest model as the fallback 0.847 at 5.4364 USD (success -0.027, cost -90.5%)
```

## Reading it

- The fallback is the `best_on_calibration` model on every cell where no model clears. Every model of a matrix is measured on the same calibration items, so the highest Wilson bound goes with the highest calibration success, and both break a tie by the lower cost. The question is therefore the best model on the calibration half or the cheapest one
- What decides it is how far the cheapest model sits below the best. On RouterBench the cheapest model reaches the bar on 0 of the cells at every bar, and with it as the fallback the whole row's success falls by 0.023 at bar 0.6 and by 0.469 at bar 0.9, where no model clears on 88.9% of the cells; on AutoBench it falls by 0.139 and 0.404 at bars 0.8 and 0.9
- On tau2-bench the four agents are close on these cells. At bars 0.3 to 0.6 the whole row moves by -0.002, +0.004, +0.005 and +0.005 with the cheapest agent as the fallback, for 33.0%, 71.7%, 73.2% and 50.1% less cost. At bar 0.3 the cells where no model clears are airline 40 and telecom 10: the airline ones are the seeds whose calibration half is under `min_samples` (the tau2-bench RESULTS.md gives the split sizes), where no agent can clear at any bar
- On the AutoBench judges the cheapest judge reaches the bar on all 22 cells at bar 0.8, as the fallback does, and the whole row loses 0.008 of success for 19.3% less cost; at 0.9 it loses 0.016 for 46.2% less
- The delegation decision has the same question when neither path clears, and [no-path-clears.md](no-path-clears.md) kept its rule (13.5 row 7) for the same reason: the choice by bound scores highest on the held-out halves

## LLMRouterBench and the response bank (2026-11-13)

- On LLMRouterBench (9 tasks, 13 models) no model clears on 25 of the 450 `cost_effective` cells at bars 0.1 and 0.2 (5.6%), all on 1 task: they are the `aime` seeds whose calibration half is under `min_samples` (its RESULTS.md says so). The share rises with the bar, to 125 (27.8%) on 3 tasks at bar 0.5 and 335 (74.4%) on 7 at bar 0.8, and on every one of these cells the fallback is the `best_on_calibration` model, as on the four datasets before
- There the cheapest model sits far below the best: on those cells it scores 0.046 against the fallback's 0.269 at bar 0.3 and 0.399 against 0.483 at bar 0.8, and from bar 0.4 up it reaches the bar on fewer of them (25 against 26 at 0.4, 3 against 89 at 0.8). With it as the fallback the whole row loses 0.041 to 0.055 of success at bars 0.3 to 0.8 for 70.3% to 96.5% less cost, and at bars 0.1 and 0.2, where those cells hold 832 held-out items, it changes by -0.000 for 2.5% and 1.1% less
- The fallback cells carry most of the row's cost: at bar 0.5 they are 27.8% of the cells, yet the cheapest model there cuts the whole row's cost by 96.5%, from 97.9935 to 3.4549 USD, since the fallback costs 0.074077 USD per item on them against 0.001097
- On the response bank (4 tasks, 5 models) no model clears on 53 of the 200 cells at bar 0.8 (26.5%): all 50 `aime` cells, whose calibration halves are under `min_samples` on every seed (its RESULTS.md says so), and 3 `gpqa_diamond` ones; at bar 0.9 on 199 of the 200 (99.5%)
- Its five models are close on these cells: the cheapest scores 0.929 against 0.932 at bar 0.8 and 0.847 against 0.874 at 0.9, and reaches the bar on 51 against 52 and 65 against 85 of them. The whole row keeps its 0.847 at bar 0.8 for 0.6% less cost, and at 0.9 loses 0.027 for 90.5% less, near the trade tau2-bench shows at bar 0.7 (0.022 for 74.5%)
- So the two datasets leave the recommendation as it was: at every bar of both the fallback keeps at least as much of the whole row's success as the cheapest model, which changes it by -0.000 to -0.055. They do show where a rule between the two (Recommendation, third bullet) would pay most: on LLMRouterBench at bars 0.5 to 0.7 a fallback by price cuts the row's cost by 90.3% to 96.5%

## Recommendation

- Keep 5.3 as it is in both flavors, and keep `refuse` as the default of `on_no_model`. A fallback by price would cut the whole row's cost by 0.6% to 99.5% on these six datasets, but where the models are far apart it gives up most of the success the fallback keeps: 0.469 on RouterBench and 0.404 on AutoBench at bar 0.9. Where it saves on tau2-bench, its success gain on the whole row is at most 0.005, and on LLMRouterBench and the response bank it gains none
- Add no `on_no_model` value now. A user who wants the cheaper model where nothing clears can set a bar it clears, or `refuse` and handle `NoModelClearsBar`
- A rule between the two, the cheapest model whose calibration success cannot be told apart from the best's, might keep the tau2-bench saving without the RouterBench loss. The cells keep no calibration counts, so it is not measured here; it would be a new research row before any spec change

## Limits

- Calibration and held-out halves are each dataset's own seeded splits, so this compares the choices on held-out halves of the same data, not on new data
- Two of the six datasets route one pooled task (AutoBench and the AutoBench judges), so their cells are seeds of one task; RouterBench's are 65 tasks, tau2-bench's 3, LLMRouterBench's 9 and the response bank's 4. With more than five tasks the script counts the tasks that hold such a cell instead of naming them, so of the LLMRouterBench tasks with such a cell this note names only `aime`, the one its RESULTS.md names
- `cheapest` is the model with the lowest mean calibration cost, whatever its success; no choice that weighs cost against the bound is measured here
- Costs are each results file's own (12.7, 12.10, 12.12, 12.15, 12.19 and 12.21 say how each is priced)

## Regenerate

```bash
python -m pip install -e ".[evidence]"
python evidence/routerbench/convert.py --out routerbench-matrix.jsonl
python evidence/autobench-2026/convert.py --out autobench-matrix.jsonl --task-by all
python evidence/autobench-2026/judges.py --out autobench-judges.jsonl --registry autobench-models.json
python evidence/tau2-bench/convert.py --out tau2-matrix.jsonl
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python evidence/response-bank/convert.py --out response-bank-matrix.jsonl
python research/no_model_clears.py --routerbench routerbench-matrix.jsonl --autobench autobench-matrix.jsonl --judges autobench-judges.jsonl --judges-registry autobench-models.json --tau2 tau2-matrix.jsonl --llmrouterbench llmrouterbench-matrix.jsonl --response-bank response-bank-matrix.jsonl
```
