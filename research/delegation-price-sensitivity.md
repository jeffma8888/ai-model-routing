# How far a wrong list price moves a committed delegation decision

[price-sensitivity.md](price-sensitivity.md) measures a price error on `cost_effective` routing, and [reread-sensitivity.md](reread-sensitivity.md) re-decides every committed delegation cell under the two inputs other than price, but no note said how far a wrong list price moves an inline-or-delegate decision, though 13.2 prices both paths from the registry's input and output prices and the parent and the delegate can come from different vendors' pages. This note reruns both grids of [the AutoBench delegation results](../evidence/delegation/RESULTS.md) with one model's input and output prices halved or doubled at a time, re-decides every cell and scores the committed pick and the new one at the committed prices. Its numbers are the output of [delegation_price_sensitivity.py](delegation_price_sensitivity.py), which stops unless each run and each cell at the committed prices is the committed one ([DESIGN.md](../DESIGN.md) 12.22).

## Facts

- A wrong list price for one model moves far more committed delegation decisions than the re-read share or the brief's output do: in `cost_effective` one model's prices halved or doubled can move about half of a bar's cells, nearly all of them to a delegated pick rather than inline, and in the run that moves the most at each bar the moved picks cost more at the list price, right less often at the lower bar and more often at the higher one; no `cost_blind` cell moves
- Data: the AutoBench 2026 matrix and pool that evidence/delegation/results.py runs, its base grid (16,000 cells: 2 bars, 2 flavors, 4 points, 20 parents, 50 seeds) and its variant grid (12,000 cells, 3 points), with the 20 models of the pool, each model's input and output prices times 0.5 and times 2.0 in turn, so 40 runs per grid; every cell's decision and held-out sum is reproduced at the committed prices before any price is scaled
- Base grid, `cost_effective`: at bar 0.7 8 of the 40 runs move a cell, and the most, doubling `openai/gpt-5.6-luna`'s prices, moves 2,147 of 4,000 cells (53.7%), 22 of them to inline, for a held-out success gap of -0.1413 at 1.236 times their cost and 1.127 times the cost over all the bar's cells; at bar 0.8 5 of the 40 runs move a cell, and the most, halving `openai/gpt-5.6-sol`'s prices, moves 317 of 4,000 cells (7.9%), 1 of them to inline, for a held-out success gap of +0.0496 at 1.292 times their cost and 1.027 times the cost over all the bar's cells
- Variant grid, `cost_effective`: at bar 0.7 6 of the 40 runs move a cell, and the most, doubling `openai/gpt-5.6-luna`'s prices, moves 1,580 of 3,000 cells (52.7%), none to inline, for a held-out success gap of -0.1385 at 1.587 times their cost and 1.299 times the cost over all the bar's cells; at bar 0.8 5 of the 40 runs move a cell, and the most, halving `openai/gpt-5.6-sol`'s prices, moves 240 of 3,000 cells (8.0%), none to inline, for a held-out success gap of +0.0496 at 1.246 times their cost and 1.025 times the cost over all the bar's cells
- By model: 8 of the 20 models move a base-grid cell at one factor or the other and 12 move none at either; on the variant grid 7 move a cell. Over every flavor and bar of the base grid the runs that move the most are doubling `openai/gpt-5.6-luna`'s prices (2,147 cells) and halving `google/gemini-3.7-flash`'s (1,834)
- Of the 5,901 cells the base grid's runs change, 51 go inline; of the variant grid's 4,240, 0; the rest go to a delegated pick
- No run moves a `cost_blind` cell, on either grid or bar

## Method

- The matrix, pool, bars, seeds and points are the ones evidence/delegation/results.py runs (13.10). The script reads them through research/reread_sensitivity.py's `inputs` and runs each grid through its `checked`: `evaluate_delegation` (13.9) runs the grid, its config, tasks and summary must be the committed file's, and each cell re-decided at the committed prices must keep its mode and model and its held-out sums for the decision, always inline and always delegating, or the script exits 2
- A run is one model of the pool and one factor, 0.5 or 2.0: a registry whose one change is that model's `price_in` and `price_out` times the factor, which stands for any error in the list price the decision uses, a stale snapshot, a vendor change not yet copied or a wrong row. It scales every cost of that model, as a parent on either path or as a candidate delegate. Every cell's router is rebuilt with the 13.9 `_router` on the cell's own calibration half and that registry, and the cell is re-decided; the calibration counts and sizes do not depend on a price, so the price is the one input that differs
- A cell changes when its mode or its model changes. Both picks are scored on the cell's held-out half at the committed prices' 13.2 costs: the error is in the price the decision believes, and the bill is at the list price, as [price-sensitivity.md](price-sensitivity.md) scores routing
- Columns: `runs moving` counts the runs that change any of the flavor and bar's cells. The other columns are those of the run that changes the most, the first in model and factor order on a tie, named in `by`: `most changed / cells` and `share` count its changed cells, `to inline` those whose new mode is inline, `success gap` is its new picks' held-out correct count minus the committed picks' over the changed cells' held-out items, `cost ratio` its new picks' held-out cost over the committed picks' on the changed cells, and `all cost ratio` the same over every cell of the flavor and bar. Each grid's last lines give the changed cells of all its runs by point, and each model's changed cells over every flavor and bar at each factor with how many go inline

## Results

```text
$ python research/delegation_price_sensitivity.py --matrix autobench-tokens.jsonl --registry autobench-pool.json
One model's list price halved or doubled on the AutoBench 2026 delegation results: each cell re-decided with that model's input and output prices times 0.5 or 2.0, both picks scored at the committed prices
AutoBench 2026, base grid (`evidence/delegation/results.json`): 16,000 cells, 2 bars, 2 flavors, 4 points, 20 parents, 50 seeds, 20 models, so 40 runs; every cell's decision and held-out sum reproduced at the committed prices
  flavor          bar  runs moving  most changed / cells  share  to inline  success gap  cost ratio  all cost ratio  by
  cost_effective  0.7       8 / 40          2,147 / 4,000  53.7%         22      -0.1413       1.236           1.127  openai/gpt-5.6-luna times 2.0
  cost_effective  0.8       5 / 40            317 / 4,000   7.9%          1      +0.0496       1.292           1.027  openai/gpt-5.6-sol times 0.5
  cost_blind      0.7       0 / 40              0 / 4,000   0.0%          0            -           -           1.000  -
  cost_blind      0.8       0 / 40              0 / 4,000   0.0%          0            -           -           1.000  -
  changed cells by point, all 40 runs: 0: 1,480, 1: 1,480, 2: 1,480, 3: 1,461
  anthropic/claude-sonnet-5: times 0.5 changes 82 cells (0 to inline), times 2.0 changes 238 (0 to inline)
  deepseek/deepseek-v4-flash-0731: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  google/gemini-3.7-flash: times 0.5 changes 1,834 cells (22 to inline), times 2.0 changes 1 (0 to inline)
  google/gemma-4-31b-it: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  meta/muse-glimmer-30b: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  meta/muse-spark-1.2: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  minimax/minimax-m3: times 0.5 changes 395 cells (0 to inline), times 2.0 changes 84 (0 to inline)
  moonshotai/kimi-k2.6: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  nvidia/nemotron-3-ultra-550b-a55b: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  nvidia/nemotron-3.5-lightning: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  openai/gpt-5.6-luna: times 0.5 changes 85 cells (0 to inline), times 2.0 changes 2,147 (22 to inline)
  openai/gpt-5.6-sol: times 0.5 changes 317 cells (1 to inline), times 2.0 changes 82 (0 to inline)
  openai/gpt-oss-120b: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  qwen/qwen3.5-9b: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  qwen/qwen3.8-max: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 79 (1 to inline)
  tencent/hy3: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  xai/grok-4.3: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  xai/grok-4.6: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  zai/glm-5.2: times 0.5 changes 5 cells (5 to inline), times 2.0 changes 0 (0 to inline)
  zai/glm-5.3: times 0.5 changes 552 cells (0 to inline), times 2.0 changes 0 (0 to inline)
AutoBench 2026, variants grid (`evidence/delegation/variants.json`): 12,000 cells, 2 bars, 2 flavors, 3 points, 20 parents, 50 seeds, 20 models, so 40 runs; every cell's decision and held-out sum reproduced at the committed prices
  flavor          bar  runs moving  most changed / cells  share  to inline  success gap  cost ratio  all cost ratio  by
  cost_effective  0.7       6 / 40          1,580 / 3,000  52.7%          0      -0.1385       1.587           1.299  openai/gpt-5.6-luna times 2.0
  cost_effective  0.8       5 / 40            240 / 3,000   8.0%          0      +0.0496       1.246           1.025  openai/gpt-5.6-sol times 0.5
  cost_blind      0.7       0 / 40              0 / 3,000   0.0%          0            -           -           1.000  -
  cost_blind      0.8       0 / 40              0 / 3,000   0.0%          0            -           -           1.000  -
  changed cells by point, all 40 runs: 0: 1,480, 1: 1,480, 2: 1,280
  anthropic/claude-sonnet-5: times 0.5 changes 60 cells (0 to inline), times 2.0 changes 180 (0 to inline)
  deepseek/deepseek-v4-flash-0731: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  google/gemini-3.7-flash: times 0.5 changes 1,380 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  google/gemma-4-31b-it: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  meta/muse-glimmer-30b: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  meta/muse-spark-1.2: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  minimax/minimax-m3: times 0.5 changes 320 cells (0 to inline), times 2.0 changes 40 (0 to inline)
  moonshotai/kimi-k2.6: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  nvidia/nemotron-3-ultra-550b-a55b: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  nvidia/nemotron-3.5-lightning: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  openai/gpt-5.6-luna: times 0.5 changes 40 cells (0 to inline), times 2.0 changes 1,580 (0 to inline)
  openai/gpt-5.6-sol: times 0.5 changes 240 cells (0 to inline), times 2.0 changes 60 (0 to inline)
  openai/gpt-oss-120b: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  qwen/qwen3.5-9b: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  qwen/qwen3.8-max: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 60 (0 to inline)
  tencent/hy3: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  xai/grok-4.3: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  xai/grok-4.6: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  zai/glm-5.2: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  zai/glm-5.3: times 0.5 changes 280 cells (0 to inline), times 2.0 changes 0 (0 to inline)
```

## Reading it

- The moved decisions go to a delegated pick and rarely inline. The delegate a decision weighs is the router's `cost_effective` pick, the cheapest of the models whose calibration bound clears the bar, so a wrong price can change that pick on any cell where it is close in cost to the next; the parent's own path wins only on the few cells where the two paths cost about the same, as on the re-read note's folded point
- So a price error moves cells at every point (the `changed cells by point` lines), unlike the re-read share and the brief's output, which move the cost of one path against the other and change cells only where the paths are close
- Most models move no cell at either factor (the per-model lines)
- At bar 0.7 doubling `openai/gpt-5.6-luna`'s prices, the run that moves the most, sends the work to picks that cost more at the list price and, on the cells it moves, are right less often on the held-out half. At bar 0.8 halving `openai/gpt-5.6-sol`'s prices, the run that moves the most, makes it look cheaper than the delegate the decision picked, so the moved picks cost more and, on those cells, are right more often
- For each `cost_effective` bar's run that moves the most, the cost over all the bar's cells rises at the list price
- `cost_blind` compares no costs (13.5), and no run moves one of its cells

## Recommendation

- Keep a registry's prices current for delegation as for routing: on AutoBench one wrong price moves up to about half of a bar's `cost_effective` delegation decisions and raises the bill, far more than either input [reread-sensitivity.md](reread-sensitivity.md) varies, so refresh a model's row when its vendor changes a price, as [price-sensitivity.md](price-sensitivity.md) recommends for routing
- Measure the LLMRouterBench, Response Bank and tau2-bench delegation results the same way before README Limitations states a bound across the delegation datasets; until then the README's routing sentence on a stale price stays as it is

## Limits

- One dataset, AutoBench 2026; the other three delegation datasets are not measured yet
- Two factors, one model at a time, both of its prices together; no run scales two models, or one of a model's two prices alone
- The held-out cost is 13.2's list-price approximation at the committed prices, not a measured bill
- The script re-decides with the 13.9 helper `_router`, which the package does not export; the check at the committed prices is what keeps the two in step

## Regenerate

```bash
python -m pip install -e .
python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens --registry autobench-pool.json
python research/delegation_price_sensitivity.py --matrix autobench-tokens.jsonl --registry autobench-pool.json
```
