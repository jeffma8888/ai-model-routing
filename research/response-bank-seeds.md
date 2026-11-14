# The response-bank gain, seed by seed

[where-routing-pays.md](where-routing-pays.md) finds two routing datasets where a routed row passes the best single model's held-out success, LLMRouterBench and the LLM Routing Response Bank, and the README's response-bank bullet in Results at a glance and its Limitations bullet on where routing pays rest on that finding. On the response bank the gain is small, and every committed number is a mean over the seeds of the 12.2 split, since 12.3's `summary` averages each seed's pooled held-out success ([DESIGN.md](../DESIGN.md)), so a mean gain could come from seeds that gain beside others that lose. [llmrouterbench-seeds.md](llmrouterbench-seeds.md) reads LLMRouterBench seed by seed; this note reads the response bank the same way. Its numbers are the output of [llmrouterbench_seeds.py](llmrouterbench_seeds.py) with `--dataset response-bank`, which runs `evaluate` on the matrix behind [the committed results](../evidence/response-bank/RESULTS.md) and stops unless each mean it rebuilds is the committed one.

## Facts

- The committed gain is a mean, not a gain on every seed: `best_on_calibration`, `cost_blind` routing at both bars and `cost_effective` routing at the higher bar pass the best single model on most seeds' own halves but fall below it on the rest, while on LLMRouterBench the same rows pass it on every seed ([llmrouterbench-seeds.md](llmrouterbench-seeds.md))
- Data: the 12.20 matrix, 4 tasks, 5 models and 13,315 items, run with the committed config, bars 0.8 and 0.9 and 50 seeds, each seed holding 6,535 to 6,772 held-out items; the best single model is `deepseek/deepseek-v4-pro` (12.7)
- `cost_blind`: above on 42 of the 50 seeds and below on 8, with a gap of -0.0032 on the lowest seed, +0.0026 at the median and +0.0059 on the highest, against the committed mean of +0.0022, at 0.958 to 2.327 of that model's cost on the same halves; all 200 (task, seed) cells keep one routed model at both bars, so its line is the same at both
- `best_on_calibration`, and `cost_effective` routing at bar 0.9, give that same line
- `cost_effective` at bar 0.8: below on all 50 seeds, from -0.0310 to -0.0203, at 0.174 to 0.241 of that model's cost; 8 of the 50 seeds keep one sign at both bars, those below at bar 0.9 too, and 95 of the 200 cells keep one routed model

## Method

- The script is [llmrouterbench_seeds.py](llmrouterbench_seeds.py) with `--dataset response-bank`: it reads the config of `evidence/response-bank/results.json` (its bars, seeds, both flavors, `calibration_fraction`, `min_samples` and `confidence`) and runs `evaluate` (12.3) with it on the matrix the 12.20 converter writes, the matrix the committed file was made from (12.21)
- On a seed, a row's pooled held-out success is its correct held-out items over the held-out items, both summed over the seed's task halves, the value 12.3's `summary` averages over the seeds; the script stops unless, at every bar and flavor, that average for the routed row, `best_on_calibration` and the best single model is the committed one, and the same for the cost
- A seed's gap is a row's pooled held-out success minus the best single model's on the same halves, so both are scored on the same items and the comparison is paired; a seed counts as above, equal or below by the two correct counts, and the median of an even count of gaps is the mean of the middle two
- The cost ratio is a row's cost on a seed over the best single model's on the same halves, each the sum of the responses' billed cost; a line gives its lowest and highest over the seeds
- The best single model is 12.7's, the `model:` row with the highest held-out success in the committed summary, so it is chosen in hindsight on the halves it is then scored on, while the routed rows and `best_on_calibration` choose on the calibration halves alone

## Results

```text
$ python research/llmrouterbench_seeds.py --dataset response-bank --matrix response-bank-matrix.jsonl
LLM Routing Response Bank (evidence/response-bank/results.json): 4 tasks, 5 models, 13,315 items, bars 0.8, 0.9, 50 seeds, held-out items per seed 6,535 to 6,772
best single model (12.7): deepseek/deepseek-v4-pro; a gap is a row's pooled held-out success on a seed minus deepseek/deepseek-v4-pro's on the same halves
best_on_calibration (every bar and flavor): above on 42, equal on 0, below on 8 of 50 seeds; gap lowest -0.0032, median +0.0026, highest +0.0059, mean +0.0022; cost over the best single model's 0.958 to 2.327
cost_effective routed:
  bar 0.8: above on 0, equal on 0, below on 50 of 50 seeds; gap lowest -0.0310, median -0.0247, highest -0.0203, mean -0.0252; cost over the best single model's 0.174 to 0.241
  bar 0.9: above on 42, equal on 0, below on 8 of 50 seeds; gap lowest -0.0032, median +0.0026, highest +0.0059, mean +0.0022; cost over the best single model's 0.958 to 2.327
  seeds whose gap has one sign at every bar: 8 of 50; (task, seed) cells routed to one model at every bar: 95 of 200
cost_blind routed:
  bar 0.8: above on 42, equal on 0, below on 8 of 50 seeds; gap lowest -0.0032, median +0.0026, highest +0.0059, mean +0.0022; cost over the best single model's 0.958 to 2.327
  bar 0.9: above on 42, equal on 0, below on 8 of 50 seeds; gap lowest -0.0032, median +0.0026, highest +0.0059, mean +0.0022; cost over the best single model's 0.958 to 2.327
  seeds whose gap has one sign at every bar: 50 of 50; (task, seed) cells routed to one model at every bar: 200 of 200
```

## Reading it

- The mean hides seeds that lose: in `cost_blind` the median seed gains +0.0026, but 8 of the 50 seeds fall below the best single model, the lowest to a gap of -0.0032, so on a new split of these items routing would likely pass that model, but not surely, and by a few thousandths either way
- The cost moves more than the success: from seed to seed `cost_blind` costs 0.958 to 2.327 times what the best single model costs on the same halves, so on some seed it costs less than that model and on others more than twice as much
- `cost_effective` at bar 0.8 buys its saving with success on every seed, below the best single model on all 50 at 0.174 to 0.241 of its cost; at bar 0.9 it falls back on nearly every cell to the model `best_on_calibration` takes, which is why it gives `cost_blind`'s line there ([the committed results](../evidence/response-bank/RESULTS.md) say why)
- On LLMRouterBench the lowest seed's gain is more than half the mean, a gain on every split; here the lowest seed is below the best single model, a gain on most splits

## Recommendation

- README.md's response-bank bullet in Results at a glance says `cost_blind` routing passes the best single model's held-out success at every bar; that holds for the committed mean, a gap of +0.0022, and on 42 of the 50 seeds, not on every one. Keep `passes`, but say it is a mean and on how many seeds it holds, for example `passes the best single model's held-out success in the mean over 50 seeds, on 42 of them`; its `more than twice its cost` is the ratio of the mean costs, while seed by seed the cost runs from 0.958 to 2.327 of that model's, so say it is a mean too
- The README Limitations bullet on where routing pays and [where-routing-pays.md](where-routing-pays.md) count the response bank as one of the two routing datasets with a routed row above the best single model; keep it there, since its mean is above, and add that its gain holds on most seeds while LLMRouterBench's holds on every one
- Make these wording changes in a change of their own; this note changes no README line

## Limits

- The seeds re-split the same items, so they show how the gain moves from one split of this dataset to another, not how it would move on new items or new tasks; the seeds are not independent samples, and the note gives no interval
- The release's own split, read in [response-bank-split.md](response-bank-split.md), is one more split of the same items, with a far smaller calibration side; there `cost_blind` routing is below the best single model, as on the seeds here that lose
- The best single model is chosen in hindsight on the held-out halves (12.7); against a model chosen in advance the gap would be at least as large on the mean
- A success is a response scored `quality == 1` and a cost each response's billed `official_usd`, as in the committed results (12.20)

## Regenerate

```bash
python -m pip install -e .
python evidence/response-bank/convert.py --out response-bank-matrix.jsonl
python research/llmrouterbench_seeds.py --dataset response-bank --matrix response-bank-matrix.jsonl
```

The converter downloads the four pinned files into its cache folder on its first run and checks them; the script reads only the matrix and the committed results file. `tests/test_research_response_bank_seeds.py` compares the Results block with a fresh run when the pinned files are cached.
