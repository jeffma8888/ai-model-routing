# LiveCodeBench variant results

What `model-routing evaluate` measures when the LiveCodeBench runs of one model at two or more reasoning settings are routed as variants of that model, `vendor/model@variant` (`DESIGN.md` 4.1), each a route with its own stats: the runs of 5 models in the public LiveCodeBench submissions, 13 routes on the same 713 dated contest problems as one routing task, `code_generation`, with the success label of [the LiveCodeBench results](../livecodebench/RESULTS.md) (`graded_list[0]`, the first sample passing the problem's test cases). `anthropic/claude-opus-4` and `anthropic/claude-sonnet-4` are each a base route and `@thinking`; `openai/o1-2024-12-17`, `openai/o3-mini-2025-01-31` and `openai/o4-mini` are each at `@low`, `@medium` and `@high`. A router keyed by model name would pool each model's runs into one success rate; here each setting is measured and admitted on its own. For each of 50 seeds the 713 problems are split in half by a seeded hash; the router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best route on the calibration half, the `cheapest` baseline and each route alone (`DESIGN.md` 12.3 and 12.32). The committed numbers are in [results.json](results.json), made by the RouterBench results script, `evidence/routerbench/results.py`, from the rows that [variants.py](variants.py) keeps of the converter's matrix.

This is `cost_blind` evidence only, as in [the LiveCodeBench results](../livecodebench/RESULTS.md): the submissions record no cost, no token counts and no list price, so every `cost_usd` is 0.0, which is what `cost_blind` assumes of every model's token cost. `cost_effective` is not run, since with every cost 0 its rows would repeat these.

## Source and licence

- Repo: https://github.com/LiveCodeBench/submissions (archived), pinned revision [`6ca212e9c2039373f6e5069d37ffa9db66e23736`](https://github.com/LiveCodeBench/submissions/tree/6ca212e9c2039373f6e5069d37ffa9db66e23736), the 13 runs' files among the 67 kept files listed in [the converter's README](../livecodebench/README.md)
- Licence: MIT, as the repo's LICENSE file states, with the line "Copyright (c) 2025 LiveCodeBench"

## Results

`success` is the share of held-out problems the routed route's first sample solved, averaged over the 50 seeds; `cleared_rate` is the share of seeds on which some route cleared the bar on the calibration half, and `bar_violation_rate` the share of cleared seeds whose held-out success fell below the bar. Every `cost_usd` is 0.0000 and every `vs_best_model` is `-`, because no cost is recorded. Baseline rows do not depend on the bar.

```text
$ python evidence/routerbench/results.py --table evidence/livecodebench-variants/results.json
bar  flavor      success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate
---  ----------  -------  --------  -------------  ------------  ------------------
0.1  cost_blind  0.909    0.0000    -              1.000         0.000
0.2  cost_blind  0.909    0.0000    -              1.000         0.000
0.3  cost_blind  0.909    0.0000    -              1.000         0.000
0.4  cost_blind  0.909    0.0000    -              1.000         0.000
0.5  cost_blind  0.909    0.0000    -              1.000         0.000
0.6  cost_blind  0.909    0.0000    -              1.000         0.000
0.7  cost_blind  0.909    0.0000    -              1.000         0.000
0.8  cost_blind  0.909    0.0000    -              1.000         0.000
0.9  cost_blind  0.909    0.0000    -              0.180         1.000

strategy                                  success  cost_usd
----------------------------------------  -------  --------
oracle                                    0.947    0.0000
best_on_calibration                       0.909    0.0000
cheapest                                  0.701    0.0000
model:anthropic/claude-opus-4             0.701    0.0000
model:anthropic/claude-opus-4@thinking    0.765    0.0000
model:anthropic/claude-sonnet-4           0.654    0.0000
model:anthropic/claude-sonnet-4@thinking  0.742    0.0000
model:openai/o1-2024-12-17@high           0.857    0.0000
model:openai/o1-2024-12-17@low            0.798    0.0000
model:openai/o1-2024-12-17@medium         0.819    0.0000
model:openai/o3-mini-2025-01-31@high      0.819    0.0000
model:openai/o3-mini-2025-01-31@low       0.776    0.0000
model:openai/o3-mini-2025-01-31@medium    0.822    0.0000
model:openai/o4-mini@high                 0.909    0.0000
model:openai/o4-mini@low                  0.833    0.0000
model:openai/o4-mini@medium               0.893    0.0000```

## Reading it

- Each model's routes, from the lowest held-out success to the highest, the same at every bar: `anthropic/claude-opus-4` base 0.701, `@thinking` 0.765, a gap of 0.064; `anthropic/claude-sonnet-4` base 0.654, `@thinking` 0.742, a gap of 0.088; `openai/o1-2024-12-17` `@low` 0.798, `@medium` 0.819, `@high` 0.857, a gap of 0.059; `openai/o3-mini-2025-01-31` `@low` 0.776, `@high` 0.819, `@medium` 0.822, a gap of 0.046; `openai/o4-mini` `@low` 0.833, `@medium` 0.893, `@high` 0.909, a gap of 0.076. The widest gap is `anthropic/claude-sonnet-4`'s.
- The highest setting is not the best route of `openai/o3-mini-2025-01-31`: `@medium` 0.822 against `@high` 0.819.
- Routed, held-out success is 0.909 at every bar, with all 50 seeds routed to `openai/o4-mini@high` at each bar, against 0.902 for the routed row of the 67 runs in [results.json](../livecodebench/results.json); at bar 0.9 the `cleared_rate` is 0.180 here and 0.180 there.
- One success rate keyed by the model's name, with its calls spread evenly over its settings, would read the mean of its routes: `anthropic/claude-opus-4` 0.733, 0.032 over its lowest route and 0.032 under its highest; `anthropic/claude-sonnet-4` 0.698, 0.044 over its lowest route and 0.044 under its highest; `openai/o1-2024-12-17` 0.825, 0.027 over its lowest route and 0.032 under its highest; `openai/o3-mini-2025-01-31` 0.806, 0.030 over its lowest route and 0.016 under its highest; `openai/o4-mini` 0.878, 0.045 over its lowest route and 0.031 under its highest.

## Limits

- No cost or token count is recorded, so this file makes no cost claim and cannot show a lower setting as the cheaper route.
- Each setting is one run, under its submission folder's label, so a gap between two settings is one run's, not a mean over reruns.
- The routes are 13 of the 67 runs of the LiveCodeBench results, so the `routed`, `oracle`, `best_on_calibration` and `cheapest` rows are not those of their results.json; each `model:` row is, under its route ID.

## Regenerate

The commands below rebuild [results.json](results.json) byte for byte from the pinned files, which the converter downloads into its cache and checks by size and sha256.

```bash
python -m pip install -e .
python evidence/livecodebench/convert.py --out livecodebench-matrix.jsonl
python evidence/livecodebench-variants/variants.py --matrix livecodebench-matrix.jsonl --out livecodebench-variants.jsonl
model-routing evaluate --outcomes livecodebench-variants.jsonl --bar 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9 --seeds 50 --flavor cost_blind --json > livecodebench-variants-evaluate.json
python evidence/routerbench/results.py --evaluate livecodebench-variants-evaluate.json --out evidence/livecodebench-variants/results.json
python evidence/routerbench/results.py --table evidence/livecodebench-variants/results.json
```
