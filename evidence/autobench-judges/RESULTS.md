# AutoBench judge results

What `model-routing evaluate` measures when the router chooses a judge model on public data. The outcome matrix is the one `evidence/autobench-2026/judges.py` builds, at its default options, from the per-judge grades the AutoBench Router Benchmark 2026 publishes (DESIGN 12.11, and the [judge section of the evidence README](../autobench-2026/README.md#judge-evidence-one-item-per-graded-answer)). An item is one graded answer, 756 of them, and a model is one of the 5 candidate judges; a judge's grade is a success when it is within 0.5 of the mean of the other judges' grades on that answer. For each of 50 seeds the answers are split in half by a seeded hash; the router calibrates on one half at a bar and is scored on the other half, next to the oracle, the best judge on the calibration half, the cheapest judge and every single judge (DESIGN 12.3). The answers are pooled into one task, `all`. The file behind every number here is [results.json](results.json): the summary rows and the routed per-task rows, including how many of the 50 seeds routed to each judge. It is made by the RouterBench results script, `evidence/routerbench/results.py`, which does not depend on the dataset.

## Results

Routed rows: `success` is the share of held-out answers on which the judge agrees with the committee, `cost_usd` is the list-price estimate of judging them (both averaged over the 50 seeds), `vs_best_model` is that cost divided by the cost of the best single judge (`tencent/hy3`), `cleared_rate` is the share of seeds where some judge cleared the bar on the calibration half, and `bar_violation_rate` is the share of cleared seeds whose held-out success fell below the bar. Baseline rows do not depend on the bar or the flavor.

```text
$ python evidence/routerbench/results.py --table evidence/autobench-judges/results.json
bar  flavor          success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate
---  --------------  -------  --------  -------------  ------------  ------------------
0.6  cost_effective  0.816    0.0617    0.518          1.000         0.000
0.6  cost_blind      0.831    0.1146    0.962          1.000         0.000
0.7  cost_effective  0.816    0.0617    0.518          1.000         0.000
0.7  cost_blind      0.831    0.1146    0.962          1.000         0.000
0.8  cost_effective  0.831    0.1135    0.953          0.560         0.071
0.8  cost_blind      0.831    0.1146    0.962          0.560         0.036
0.9  cost_effective  0.831    0.1146    0.962          0.000         -
0.9  cost_blind      0.831    0.1146    0.962          0.000         -

strategy                               success  cost_usd
-------------------------------------  -------  --------
oracle                                 0.957    0.0832
best_on_calibration                    0.831    0.1146
cheapest                               0.816    0.0617
model:deepseek/deepseek-v4-flash-0731  0.816    0.0617
model:google/gemma-4-31b-it            0.771    0.1144
model:meta/muse-glimmer-30b            0.599    0.3234
model:openai/gpt-5.6-luna              0.642    0.2105
model:tencent/hy3                      0.835    0.1192
```

## Reading it

- At bars 0.6 and 0.7 every seed clears and `cost_effective` routes all 50 seeds to `deepseek/deepseek-v4-flash-0731`, the cheapest candidate: held-out success 0.816 at 0.518 of the cost of the best single judge, `tencent/hy3` (0.835 at 0.1192 USD)
- At bar 0.8 a judge clears on 28 of the 50 seeds, and `cost_effective` routes 45 to `tencent/hy3` and 5 to `deepseek/deepseek-v4-flash-0731`: held-out success 0.831 at 0.953 of the best single judge's cost. At bar 0.9 no seed clears (the best single judge's held-out success is 0.835), so the router falls back on every seed to the judge with the highest lower bound
- `cost_blind` routes to the judge with the highest lower bound: held-out success 0.831 at 0.962 of the best single judge's cost at every bar, routing 46 to `tencent/hy3` and 4 to `deepseek/deepseek-v4-flash-0731`, level with `best_on_calibration` at full precision
- There is one task, so each rate counts seeds: `cost_effective` at bar 0.8, 0.071, is 2 of the 28 seeds that cleared; `cost_blind` at bar 0.8, 0.036, is 1 of the 28 seeds that cleared. Read them next to a nominal one-sided 0.025 for a 95% Wilson bound on one judge, as a resampling estimate for this matrix and never as a guarantee (DESIGN 12.3)
- The oracle, 0.957 at 0.0832 USD, takes on each held-out answer the cheapest candidate that agrees with the committee, or, where none agrees (0.043 of the held-out answers), the cheapest candidate on that answer, counted wrong: a hindsight bound, next to 0.835 for the best single judge
- The two costliest candidates agree with the committee least: `meta/muse-glimmer-30b` (0.599 at 0.3234 USD) and `openai/gpt-5.6-luna` (0.642 at 0.2105 USD), so a higher price did not buy more agreement. `openai/gpt-5.6-luna` is the answer model of the dataset card's headline, which no commercial router beat on quality and cost together ([AutoBench results](../autobench-2026/RESULTS.md))

## Sensitivity

Tolerance. With `--tolerance 1.0` a grade within one point of the committee's mean counts as agreement, so more of the judges' grades count as successes. At bar 0.8 with 50 seeds:

- `tencent/hy3` alone: held-out success 0.935 at 0.1192 USD
- bar 0.8, `cost_effective`: routed success 0.920 at 0.0617 USD, cleared_rate 1.000, bar_violation_rate 0.000
- bar 0.8, `cost_blind`: routed success 0.931 at 0.1226 USD, cleared_rate 1.000, bar_violation_rate 0.000

Reasoning tokens. With `--answer-tokens output` the judge is charged for reading the answer model's reasoning too, an upper bound on cost. Every grade keeps its label, and in the three lines below held-out success, cleared and bar-violation rates are those of the default run and only the costs rise. At bar 0.8 with 50 seeds:

- `tencent/hy3` alone: held-out success 0.835 at 0.2357 USD
- bar 0.8, `cost_effective`: routed success 0.831 at 0.2255 USD, cleared_rate 0.560, bar_violation_rate 0.071
- bar 0.8, `cost_blind`: routed success 0.831 at 0.2276 USD, cleared_rate 0.560, bar_violation_rate 0.036

## Caveats

- The label is a committee label, not a human gold label: a judge succeeds when it agrees with the other judges, which are models, on the same answer. A judge that always grades as the committee does scores 1.0 whether or not the committee is right, and a judge that is right where the committee is wrong scores lower
- The cost is a list-price estimate at the pool's list prices, never a billed cost: a judge call is assumed to read the question, the visible answer and a 400-token rubric, and to write a 200-token grade (DESIGN 12.11)
- The 5 candidates are the pool judges whose set keeps the most answers, not the best or the cheapest judges; a judge outside them is not compared here. 756 of the 4,933 scored answers are kept: the converter drops the 1,252 answered by a candidate, since no model grades its own answer, and the 2,925 that some candidate did not grade, so every candidate grades every item
- Answers to the same question are separate items, so a seed's split can put answers to one question in both halves
- Data: CC-BY-4.0, Autobench, Autobench Router Benchmark 2026, https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10 at revision 43755180be7d8097068982d7a3f37fc04cd15379. Pinned files, sha256 values, the citation the card asks for and what the converter drops are in the [evidence README](../autobench-2026/README.md)

## Regenerate

```bash
python -m pip install -e .
python evidence/autobench-2026/judges.py --out autobench-judges.jsonl --registry autobench-models.json
model-routing evaluate --outcomes autobench-judges.jsonl --registry autobench-models.json --bar 0.6 0.7 0.8 0.9 --seeds 50 --json > autobench-judges-evaluate.json
python evidence/routerbench/results.py --evaluate autobench-judges-evaluate.json --out evidence/autobench-judges/results.json
python evidence/routerbench/results.py --table evidence/autobench-judges/results.json
```

The judge rows carry token counts and no cost, so `evaluate` needs `--registry`: the file `judges.py --registry` writes, priced at the pool's list prices. The full evaluate output keeps every per-task strategy; the committed file, 23,225 bytes, keeps only the summary and the routed per-task rows. Two runs give byte-identical files. The sensitivity numbers come from:

```bash
python evidence/autobench-2026/judges.py --out autobench-judges-tolerance-1.jsonl --tolerance 1.0
model-routing evaluate --outcomes autobench-judges-tolerance-1.jsonl --registry autobench-models.json --bar 0.8 --seeds 50
python evidence/autobench-2026/judges.py --out autobench-judges-output.jsonl --answer-tokens output
model-routing evaluate --outcomes autobench-judges-output.jsonl --registry autobench-models.json --bar 0.8 --seeds 50
```
