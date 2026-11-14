# The LLMRouterBench gain, seed by seed

[where-routing-pays.md](where-routing-pays.md) finds two routing datasets where a routed row passes the best single model's held-out success, LLMRouterBench and the LLM Routing Response Bank, and the README's LLMRouterBench bullet and its Limitations bullet on where routing pays rest on that finding. Every committed number is a mean over the seeds of the 12.2 split, since 12.3's `summary` averages each seed's pooled held-out success ([DESIGN.md](../DESIGN.md)), and no committed file holds a seed's value, so a mean gain could come from a few seeds with large gains beside others that lose. This note runs the evaluation again and reads it seed by seed. Its numbers are the output of [llmrouterbench_seeds.py](llmrouterbench_seeds.py), which runs `evaluate` on the matrix behind [the committed results](../evidence/llmrouterbench/RESULTS.md) and stops unless each mean it rebuilds is the committed one. [response-bank-seeds.md](response-bank-seeds.md) reads the LLM Routing Response Bank the same way.

## Facts

- The gain is on every seed: `best_on_calibration` and `cost_blind` routing at every bar pass the best single model on each seed's own halves, not only in the mean, while `cost_effective` routing passes it on every seed only at the highest bar and is below it on every seed at the low bars
- Data: the 12.18 matrix, 9 tasks, 13 models and 12,066 items, run with the committed config, bars 0.1 to 0.8 and 50 seeds, each seed holding 5,936 to 6,171 held-out items; the best single model is `google/gemini-2.5-pro` (12.7)
- `cost_blind`: above on all 50 seeds at every bar, with a gap of +0.0155 on the lowest seed, +0.0233 at the median and +0.0287 on the highest, against the committed mean of +0.0223, at 0.404 to 0.531 of that model's cost on the same halves; all 450 (task, seed) cells keep one routed model at every bar, so its lines are the same at every bar
- `best_on_calibration`: above on all 50 seeds, from +0.0153 to +0.0289 with a median of +0.0233, at 0.404 to 0.531 of the cost
- `cost_effective`: below on all 50 seeds at bars 0.1 to 0.5, its highest gap there -0.0015 at bar 0.5; at bar 0.6 above on 4, equal on 1 and below on 45; at bar 0.7 above on 44, equal on 1 and below on 5, its lowest gap -0.0022, so the mean of +0.0058 there is not a gain on every seed; at bar 0.8 above on all 50, from +0.0061 to +0.0209, at 0.356 to 0.481 of the cost. No seed's `cost_effective` gap keeps one sign at every bar (0 of 50), and 105 of the 450 cells keep one routed model

## Method

- The script reads the config of `evidence/llmrouterbench/results.json` (its bars, seeds, both flavors, `calibration_fraction`, `min_samples` and `confidence`) and runs `evaluate` (12.3) with it on the matrix the 12.18 converter writes, the matrix the committed file was made from (12.19)
- On a seed, a row's pooled held-out success is its correct held-out items over the held-out items, both summed over the seed's 9 task halves, the value 12.3's `summary` averages over the seeds; the script stops unless, at every bar and flavor, that average for the routed row, `best_on_calibration` and the best single model is the committed one
- A seed's gap is a row's pooled held-out success minus the best single model's on the same halves, so both are scored on the same items and the comparison is paired; a seed counts as above, equal or below by the two correct counts, and the median of the 50 gaps is the mean of the middle two
- The cost ratio is a row's cost on a seed over the best single model's on the same halves, each the sum of the records' own `cost`; a line gives its lowest and highest over the seeds
- The best single model is 12.7's, the `model:` row with the highest held-out success in the committed summary, so it is chosen in hindsight on the halves it is then scored on, while the routed rows and `best_on_calibration` choose on the calibration halves alone

## Results

```text
$ python research/llmrouterbench_seeds.py --matrix llmrouterbench-matrix.jsonl
LLMRouterBench (evidence/llmrouterbench/results.json): 9 tasks, 13 models, 12,066 items, bars 0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 50 seeds, held-out items per seed 5,936 to 6,171
best single model (12.7): google/gemini-2.5-pro; a gap is a row's pooled held-out success on a seed minus google/gemini-2.5-pro's on the same halves
best_on_calibration (every bar and flavor): above on 50, equal on 0, below on 0 of 50 seeds; gap lowest +0.0153, median +0.0233, highest +0.0289, mean +0.0223; cost over the best single model's 0.404 to 0.531
cost_effective routed:
  bar 0.1: above on 0, equal on 0, below on 50 of 50 seeds; gap lowest -0.0468, median -0.0406, highest -0.0289, mean -0.0395; cost over the best single model's 0.102 to 0.121
  bar 0.2: above on 0, equal on 0, below on 50 of 50 seeds; gap lowest -0.0310, median -0.0158, highest -0.0028, mean -0.0164; cost over the best single model's 0.187 to 0.280
  bar 0.3: above on 0, equal on 0, below on 50 of 50 seeds; gap lowest -0.0217, median -0.0135, highest -0.0023, mean -0.0125; cost over the best single model's 0.250 to 0.280
  bar 0.4: above on 0, equal on 0, below on 50 of 50 seeds; gap lowest -0.0217, median -0.0135, highest -0.0023, mean -0.0125; cost over the best single model's 0.250 to 0.280
  bar 0.5: above on 0, equal on 0, below on 50 of 50 seeds; gap lowest -0.0191, median -0.0120, highest -0.0015, mean -0.0112; cost over the best single model's 0.251 to 0.281
  bar 0.6: above on 4, equal on 1, below on 45 of 50 seeds; gap lowest -0.0164, median -0.0075, highest +0.0030, mean -0.0066; cost over the best single model's 0.265 to 0.384
  bar 0.7: above on 44, equal on 1, below on 5 of 50 seeds; gap lowest -0.0022, median +0.0054, highest +0.0125, mean +0.0058; cost over the best single model's 0.296 to 0.410
  bar 0.8: above on 50, equal on 0, below on 0 of 50 seeds; gap lowest +0.0061, median +0.0134, highest +0.0209, mean +0.0137; cost over the best single model's 0.356 to 0.481
  seeds whose gap has one sign at every bar: 0 of 50; (task, seed) cells routed to one model at every bar: 105 of 450
cost_blind routed:
  bar 0.1: above on 50, equal on 0, below on 0 of 50 seeds; gap lowest +0.0155, median +0.0233, highest +0.0287, mean +0.0223; cost over the best single model's 0.404 to 0.531
  bar 0.2: above on 50, equal on 0, below on 0 of 50 seeds; gap lowest +0.0155, median +0.0233, highest +0.0287, mean +0.0223; cost over the best single model's 0.404 to 0.531
  bar 0.3: above on 50, equal on 0, below on 0 of 50 seeds; gap lowest +0.0155, median +0.0233, highest +0.0287, mean +0.0223; cost over the best single model's 0.404 to 0.531
  bar 0.4: above on 50, equal on 0, below on 0 of 50 seeds; gap lowest +0.0155, median +0.0233, highest +0.0287, mean +0.0223; cost over the best single model's 0.404 to 0.531
  bar 0.5: above on 50, equal on 0, below on 0 of 50 seeds; gap lowest +0.0155, median +0.0233, highest +0.0287, mean +0.0223; cost over the best single model's 0.404 to 0.531
  bar 0.6: above on 50, equal on 0, below on 0 of 50 seeds; gap lowest +0.0155, median +0.0233, highest +0.0287, mean +0.0223; cost over the best single model's 0.404 to 0.531
  bar 0.7: above on 50, equal on 0, below on 0 of 50 seeds; gap lowest +0.0155, median +0.0233, highest +0.0287, mean +0.0223; cost over the best single model's 0.404 to 0.531
  bar 0.8: above on 50, equal on 0, below on 0 of 50 seeds; gap lowest +0.0155, median +0.0233, highest +0.0287, mean +0.0223; cost over the best single model's 0.404 to 0.531
  seeds whose gap has one sign at every bar: 50 of 50; (task, seed) cells routed to one model at every bar: 450 of 450
```

## Reading it

- The mean does not hide seeds that lose: in `cost_blind` the lowest seed's gap, +0.0155, is more than half the committed mean, +0.0223, and no seed is below or level with the best single model, so the README's statement that `cost_blind` routing passes that model holds on every split of these items, not only on average
- `cost_blind` gives the same line at every bar because the bar never changes its pick: it takes each task's model with the highest calibration bound whether or not that bound clears the bar, so the bar moves only whether a cell counts as cleared, and all 450 cells keep one model. `best_on_calibration`, which takes each task's model with the highest calibration success, gives nearly the same line
- `cost_effective` buys cost with success. At bars 0.1 to 0.5 it is below the best single model on every seed, at 0.102 to 0.281 of its cost, as the README says for bar 0.1; at bar 0.7 its mean gain, +0.0058, comes with 5 seeds below and 1 level, so a gain there is likely on a new split of these items but not certain; at bar 0.8 it is above on every seed at under half the cost, 0.356 to 0.481
- So the README's LLMRouterBench lines need no new wording: what they say of the mean holds on each seed

## Limits

- The 50 seeds re-split the same 12,066 items, so they show how the gain moves from one split of this dataset to another, not how it would move on new items or new tasks; the seeds are not independent samples, and the note gives no interval
- The best single model is chosen in hindsight on the held-out halves (12.7); every other single model has a lower mean held-out success, so against a model chosen in advance the mean gap would be at least as large
- A success is a record scored 1, so an `arenahard` half score counts as a miss (12.18), and a cost is the record's own `cost`, as in the committed results
- One dataset: of the other routing results files only the LLM Routing Response Bank's has a routed row above the best single model ([where-routing-pays.md](where-routing-pays.md)), and [response-bank-seeds.md](response-bank-seeds.md) reads it the same way, where the gain holds on most seeds but not on every one

## Regenerate

```bash
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python research/llmrouterbench_seeds.py --matrix llmrouterbench-matrix.jsonl
```

The converter downloads the pinned file into its cache folder on its first run and checks it; the script reads only the matrix and the committed results file. `tests/test_research_llmrouterbench_seeds.py` compares the Results block with a fresh run when the pinned file is cached.
