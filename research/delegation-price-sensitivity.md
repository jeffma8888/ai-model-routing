# How far a wrong list price moves a committed delegation decision

[price-sensitivity.md](price-sensitivity.md) measures a price error on `cost_effective` routing, and [reread-sensitivity.md](reread-sensitivity.md) re-decides every committed delegation cell under the two inputs other than price, but no note said how far a wrong list price moves an inline-or-delegate decision, though 13.2 prices both paths from the registry's input and output prices and the parent and the delegate can come from different vendors' pages. This note reruns both grids of [the AutoBench delegation results](../evidence/delegation/RESULTS.md), the one grid each of [the LLMRouterBench delegation results](../evidence/llmrouterbench-delegation/RESULTS.md) and [the LLM Routing Response Bank delegation results](../evidence/response-bank-delegation/RESULTS.md), and the per-domain and pooled runs of [the tau2-bench delegation results](../evidence/tau2-bench-delegation/RESULTS.md) with one model's input and output prices halved or doubled at a time, re-decides every cell and scores the committed pick and the new one at the committed prices. Its numbers are the output of [delegation_price_sensitivity.py](delegation_price_sensitivity.py), which stops unless each run and each cell at the committed prices is the committed one ([DESIGN.md](../DESIGN.md) 12.22).

## Facts

- A wrong list price for one model moves far more committed delegation decisions than the re-read share or the brief's output do on AutoBench and on LLMRouterBench, fewer than a zero re-read share does on the LLM Routing Response Bank, and some on tau2-bench, where neither of those inputs moves any: on the first two, in `cost_effective` one model's prices halved or doubled can move about half of a bar's cells, nearly all of them to a delegated pick rather than inline, and in the run that moves the most at each bar the moved picks cost more at the list price, right more often at some bars and less often at others; on the Response Bank a run moves at most a few cells of one task, none of them inline; on tau2-bench two of its three models move cells, up to about a fifth of a bar's cells per domain, none of them inline, and in the run that moves the most at each bar the moved picks cost more than twice as much at the list price; no `cost_blind` cell moves
- AutoBench data: the AutoBench 2026 matrix and pool that evidence/delegation/results.py runs, its base grid (16,000 cells: 2 bars, 2 flavors, 4 points, 20 parents, 50 seeds) and its variant grid (12,000 cells, 3 points), with the 20 models of the pool, each model's input and output prices times 0.5 and times 2.0 in turn, so 40 runs per grid; every cell's decision and held-out sum is reproduced at the committed prices before any price is scaled
- AutoBench base grid, `cost_effective`: at bar 0.7 8 of the 40 runs move a cell, and the most, doubling `openai/gpt-5.6-luna`'s prices, moves 2,147 of 4,000 cells (53.7%), 22 of them to inline, for a held-out success gap of -0.1413 at 1.236 times their cost and 1.127 times the cost over all the bar's cells; at bar 0.8 5 of the 40 runs move a cell, and the most, halving `openai/gpt-5.6-sol`'s prices, moves 317 of 4,000 cells (7.9%), 1 of them to inline, for a held-out success gap of +0.0496 at 1.292 times their cost and 1.027 times the cost over all the bar's cells
- AutoBench variant grid, `cost_effective`: at bar 0.7 6 of the 40 runs move a cell, and the most, doubling `openai/gpt-5.6-luna`'s prices, moves 1,580 of 3,000 cells (52.7%), none to inline, for a held-out success gap of -0.1385 at 1.587 times their cost and 1.299 times the cost over all the bar's cells; at bar 0.8 5 of the 40 runs move a cell, and the most, halving `openai/gpt-5.6-sol`'s prices, moves 240 of 3,000 cells (8.0%), none to inline, for a held-out success gap of +0.0496 at 1.246 times their cost and 1.025 times the cost over all the bar's cells
- AutoBench by model: 8 of the 20 models move a base-grid cell at one factor or the other and 12 move none at either; on the variant grid 7 move a cell. Over every flavor and bar of the base grid the runs that move the most are doubling `openai/gpt-5.6-luna`'s prices (2,147 cells) and halving `google/gemini-3.7-flash`'s (1,834)
- On AutoBench, of the 5,901 cells the base grid's runs change, 51 go inline; of the variant grid's 4,240, 0; the rest go to a delegated pick
- LLMRouterBench data: the rows and registry that evidence/llmrouterbench-delegation/results.py runs, its one grid (115,200 cells: 9 tasks, 4 bars, 2 flavors, 4 points, 8 parents, 50 seeds), with the 8 models of its registry, each model's input and output prices times 0.5 and times 2.0 in turn, so 16 runs; every cell's decision and held-out sum is reproduced at the committed prices before any price is scaled
- LLMRouterBench, `cost_effective`: at bar 0.1 11 of the 16 runs move a cell, and the most, halving `deepseek/deepseek-v3.1-terminus`'s prices, moves 6,610 of 14,400 cells (45.9%), 8 of them to inline, for a held-out success gap of -0.0049 at 1.031 times their cost and 1.005 times the cost over all the bar's cells; at bar 0.3 12 of the 16 runs move a cell, and the most, halving `deepseek/deepseek-v3.1-terminus`'s prices, moves 4,693 of 14,400 cells (32.6%), 1 of them to inline, for a held-out success gap of +0.0915 at 1.063 times their cost and 1.001 times the cost over all the bar's cells; at bar 0.5 15 of the 16 runs move a cell, and the most, doubling `deepseek/deepseek-v3.1-terminus`'s prices, moves 3,238 of 14,400 cells (22.5%), 30 of them to inline, for a held-out success gap of -0.0468 at 1.024 times their cost and 1.001 times the cost over all the bar's cells; at bar 0.8 3 of the 16 runs move a cell, and the most, doubling `deepseek/deepseek-r1-0528`'s prices, moves 512 of 14,400 cells (3.6%), 14 of them to inline, for a held-out success gap of +0.0297 at 1.555 times their cost and 1.001 times the cost over all the bar's cells
- LLMRouterBench by model and task: every one of the 8 models moves a cell at one factor or the other; over every flavor and bar the runs that move the most are halving `deepseek/deepseek-v3.1-terminus`'s prices (12,711 cells) and doubling `deepseek/deepseek-v3-0324`'s (12,600); of the 53,306 cells its runs change, 192 go inline; every task has changed cells, livecodebench the most (9,150) and arc-agi the fewest (1,536)
- Response Bank data: the rows and registry that evidence/response-bank-delegation/results.py runs, its one grid (16,000 cells: 4 tasks, 2 bars, 2 flavors, 4 points, 5 parents, 50 seeds), with the 5 models of its registry, each model's input and output prices times 0.5 and times 2.0 in turn, so 10 runs; every cell's decision and held-out sum is reproduced at the committed prices before any price is scaled
- Response Bank, `cost_effective`: at bar 0.8 4 of the 10 runs move a cell, and the most, doubling `deepseek/deepseek-v4-flash`'s prices, moves 20 of 4,000 cells (0.5%), none to inline, for a held-out success gap of -0.1875 at 1.128 times their cost and 1.000 times the cost over all the bar's cells; at bar 0.9 4 of the 10 runs move a cell, and the most, doubling `deepseek/deepseek-v4-flash`'s prices, moves 20 of 4,000 cells (0.5%), none to inline, for a held-out success gap of -0.1875 at 1.128 times their cost and 1.000 times the cost over all the bar's cells
- Response Bank by model and task: 3 of the 5 models move a cell at one factor or the other and 2 move none at either; 4 of the 10 runs move a cell, each 40 cells over every flavor and bar, so 160 in all, none of them inline; only aime has changed cells, and gpqa_diamond, livecodebench and mmlu_pro have none
- tau2-bench data: the rows and registry that evidence/tau2-bench-delegation/results.py runs, its grid per domain (21,600 cells: 3 tasks, 6 bars, 2 flavors, 4 points, 3 parents, 50 seeds) and pooled (7,200 cells, one task), with the 3 models of its registry, each model's input and output prices times 0.5 and times 2.0 in turn, so 6 runs per grid; each held-out item is priced call by call from its per-call sizes, and every cell's decision and held-out sum is reproduced at the committed prices before any price is scaled
- tau2-bench per domain, `cost_effective`: at bar 0.3 2 of the 6 runs move a cell, and the most, halving `anthropic/claude-3-7-sonnet-20250219`'s prices, moves 108 of 1,800 cells (6.0%), none to inline, for a held-out success gap of -0.0732 at 3.427 times their cost and 1.076 times the cost over all the bar's cells; at bar 0.4 2 of the 6 runs move a cell, and the most, halving `anthropic/claude-3-7-sonnet-20250219`'s prices, moves 120 of 1,800 cells (6.7%), none to inline, for a held-out success gap of -0.0758 at 3.399 times their cost and 1.059 times the cost over all the bar's cells; at bar 0.5 2 of the 6 runs move a cell, and the most, halving `anthropic/claude-3-7-sonnet-20250219`'s prices, moves 204 of 1,800 cells (11.3%), none to inline, for a held-out success gap of +0.0029 at 2.889 times their cost and 1.121 times the cost over all the bar's cells; at bar 0.6 2 of the 6 runs move a cell, and the most, halving `anthropic/claude-3-7-sonnet-20250219`'s prices, moves 348 of 1,800 cells (19.3%), none to inline, for a held-out success gap of +0.0612 at 2.770 times their cost and 1.171 times the cost over all the bar's cells; at bar 0.7 2 of the 6 runs move a cell, and the most, halving `anthropic/claude-3-7-sonnet-20250219`'s prices, moves 180 of 1,800 cells (10.0%), none to inline, for a held-out success gap of +0.0220 at 3.003 times their cost and 1.066 times the cost over all the bar's cells; at bar 0.8 2 of the 6 runs move a cell, and the most, halving `anthropic/claude-3-7-sonnet-20250219`'s prices, moves 168 of 1,800 cells (9.3%), none to inline, for a held-out success gap of +0.0163 at 3.039 times their cost and 1.060 times the cost over all the bar's cells
- tau2-bench pooled, `cost_effective`: at bars 0.3 and 0.4 no run moves a cell; at bar 0.5 2 of the 6 runs move a cell, and the most, halving `anthropic/claude-3-7-sonnet-20250219`'s prices, moves 60 of 600 cells (10.0%), none to inline, for a held-out success gap of +0.0917 at 2.385 times their cost and 1.068 times the cost over all the bar's cells; at bar 0.6 2 of the 6 runs move a cell, and the most, halving `anthropic/claude-3-7-sonnet-20250219`'s prices, moves 12 of 600 cells (2.0%), none to inline, for a held-out success gap of +0.0942 at 2.490 times their cost and 1.013 times the cost over all the bar's cells; at bar 0.7 2 of the 6 runs move a cell, and the most, halving `anthropic/claude-3-7-sonnet-20250219`'s prices, moves 12 of 600 cells (2.0%), none to inline, for a held-out success gap of +0.0942 at 2.490 times their cost and 1.013 times the cost over all the bar's cells; at bar 0.8 2 of the 6 runs move a cell, and the most, halving `anthropic/claude-3-7-sonnet-20250219`'s prices, moves 12 of 600 cells (2.0%), none to inline, for a held-out success gap of +0.0942 at 2.490 times their cost and 1.013 times the cost over all the bar's cells
- tau2-bench by model and task: per domain and pooled 2 of the 3 models move a cell, halving `anthropic/claude-3-7-sonnet-20250219`'s prices or doubling `openai/gpt-4.1-2025-04-14`'s, each run the same number of cells (1,128 per domain, 96 pooled), and `openai/gpt-4.1-mini-2025-04-14` moves none at either factor; none of the changed cells go inline; per domain airline has the most changed cells (1,416), retail 840 and telecom none
- No run moves a `cost_blind` cell, on any grid or bar of the four datasets

## Method

- On AutoBench the matrix, pool, bars, seeds and points are the ones evidence/delegation/results.py runs (13.10). On LLMRouterBench they are the 13.13 grid of evidence/llmrouterbench-delegation/results.py, on the rows its `select_rows` keeps for that folder's committed registry.json, read and checked as research/reread_sensitivity.py's `--dataset llmrouterbench` reads and checks them; on the Response Bank they are the 13.14 grid of evidence/response-bank-delegation/results.py, read and checked in the same way, as `--dataset response-bank` reads and checks them; on tau2-bench they are the 13.12 grid of evidence/tau2-bench-delegation/results.py, per domain (results.json) and pooled (pooled.json), on every row of the tau2-bench converter's `--calls` matrix (`--calls --task-by all` pooled), read and checked as `--dataset tau2-bench` and `tau2-bench-pooled` read and check them; a run is then one of that registry's models and one factor. The script reads them through research/reread_sensitivity.py's `inputs` and runs each grid through its `checked`: `evaluate_delegation` (13.9) runs the grid, its config, tasks and summary must be the committed file's, and each cell re-decided at the committed prices must keep its mode and model and its held-out sums for the decision, always inline and always delegating, or the script exits 2
- A run is one model of the pool and one factor, 0.5 or 2.0: a registry whose one change is that model's `price_in` and `price_out` times the factor, which stands for any error in the list price the decision uses, a stale snapshot, a vendor change not yet copied or a wrong row. It scales every cost of that model, as a parent on either path or as a candidate delegate. Every `cost_effective` cell's router is rebuilt with the 13.9 `_router` on the cell's own calibration half and that registry, and the cell is re-decided; the calibration counts and sizes do not depend on a price, so the price is the one input that differs, while a `cost_blind` cell keeps its committed pick (v1.429): its candidates' routing cost is zero and 13.5 compares no costs in that flavor, so no price can move it, and the script's test checks on hand matrices that this prints what re-deciding every cell prints; up to v1.428 the script re-decided those cells too, and the blocks below, the same bytes, show that none moved
- A cell changes when its mode or its model changes. Both picks are scored on the cell's held-out half at the committed prices' 13.2 costs: the error is in the price the decision believes, and the bill is at the list price, as [price-sensitivity.md](price-sensitivity.md) scores routing
- The tau2-bench rows carry per-call sizes (13.9 v1.74): each held-out item is priced call by call by the re-read script's `call_cost` at the committed prices, and the decision forecasts the work from the calibration half's per-call means with its median call count as `work_calls`, as the committed run does
- Columns: `runs moving` counts the runs that change any of the flavor and bar's cells. The other columns are those of the run that changes the most, the first in model ID, then factor, order on a tie, named in `by`: `most changed / cells` and `share` count its changed cells, `to inline` those whose new mode is inline, `success gap` is its new picks' held-out correct count minus the committed picks' over the changed cells' held-out items, `cost ratio` its new picks' held-out cost over the committed picks' on the changed cells, and `all cost ratio` the same over every cell of the flavor and bar. Each grid's last lines give the changed cells of all its runs by point, on LLMRouterBench, the Response Bank and tau2-bench per domain by task too, in the run's task order, and each model's changed cells over every flavor and bar at each factor with how many go inline

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

```text
$ python research/delegation_price_sensitivity.py --dataset llmrouterbench --matrix llmrouterbench-matrix.jsonl
One model's list price halved or doubled on the LLMRouterBench delegation results: each cell re-decided with that model's input and output prices times 0.5 or 2.0, both picks scored at the committed prices
LLMRouterBench, base grid (`evidence/llmrouterbench-delegation/results.json`): 115,200 cells, 9 tasks, 4 bars, 2 flavors, 4 points, 8 parents, 50 seeds, 8 models, so 16 runs; every cell's decision and held-out sum reproduced at the committed prices
  flavor          bar  runs moving  most changed / cells  share  to inline  success gap  cost ratio  all cost ratio  by
  cost_effective  0.1      11 / 16          6,610 / 14,400  45.9%          8      -0.0049       1.031           1.005  deepseek/deepseek-v3.1-terminus times 0.5
  cost_effective  0.3      12 / 16          4,693 / 14,400  32.6%          1      +0.0915       1.063           1.001  deepseek/deepseek-v3.1-terminus times 0.5
  cost_effective  0.5      15 / 16          3,238 / 14,400  22.5%         30      -0.0468       1.024           1.001  deepseek/deepseek-v3.1-terminus times 2.0
  cost_effective  0.8       3 / 16            512 / 14,400   3.6%         14      +0.0297       1.555           1.001  deepseek/deepseek-r1-0528 times 2.0
  cost_blind      0.1       0 / 16              0 / 14,400   0.0%          0            -           -           1.000  -
  cost_blind      0.3       0 / 16              0 / 14,400   0.0%          0            -           -           1.000  -
  cost_blind      0.5       0 / 16              0 / 14,400   0.0%          0            -           -           1.000  -
  cost_blind      0.8       0 / 16              0 / 14,400   0.0%          0            -           -           1.000  -
  changed cells by point, all 16 runs: 0: 14,024, 1: 14,024, 2: 14,024, 3: 11,234
  changed cells by task, all 16 runs: aime 5,146, arc-agi 1,536, arenahard 6,938, gpqa 7,770, hle 3,200, livecodebench 9,150, livemathbench 8,466, mmlupro 8,400, simpleqa 2,700
  anthropic/claude-sonnet-4: times 0.5 changes 3 cells (3 to inline), times 2.0 changes 567 (0 to inline)
  deepseek/deepseek-r1-0528: times 0.5 changes 1,214 cells (0 to inline), times 2.0 changes 2,560 (20 to inline)
  deepseek/deepseek-v3-0324: times 0.5 changes 9,624 cells (0 to inline), times 2.0 changes 12,600 (12 to inline)
  deepseek/deepseek-v3.1-terminus: times 0.5 changes 12,711 cells (9 to inline), times 2.0 changes 9,693 (58 to inline)
  internlm/intern-s1: times 0.5 changes 187 cells (0 to inline), times 2.0 changes 96 (3 to inline)
  openai/gpt-5: times 0.5 changes 640 cells (20 to inline), times 2.0 changes 0 (0 to inline)
  openai/gpt-5-chat: times 0.5 changes 8 cells (8 to inline), times 2.0 changes 677 (0 to inline)
  z-ai/glm-4.6: times 0.5 changes 2,617 cells (59 to inline), times 2.0 changes 109 (0 to inline)
```

```text
$ python research/delegation_price_sensitivity.py --dataset response-bank --matrix response-bank-matrix.jsonl
One model's list price halved or doubled on the LLM Routing Response Bank delegation results: each cell re-decided with that model's input and output prices times 0.5 or 2.0, both picks scored at the committed prices
LLM Routing Response Bank, base grid (`evidence/response-bank-delegation/results.json`): 16,000 cells, 4 tasks, 2 bars, 2 flavors, 4 points, 5 parents, 50 seeds, 5 models, so 10 runs; every cell's decision and held-out sum reproduced at the committed prices
  flavor          bar  runs moving  most changed / cells  share  to inline  success gap  cost ratio  all cost ratio  by
  cost_effective  0.8       4 / 10             20 / 4,000   0.5%          0      -0.1875       1.128           1.000  deepseek/deepseek-v4-flash times 2.0
  cost_effective  0.9       4 / 10             20 / 4,000   0.5%          0      -0.1875       1.128           1.000  deepseek/deepseek-v4-flash times 2.0
  cost_blind      0.8       0 / 10              0 / 4,000   0.0%          0            -           -           1.000  -
  cost_blind      0.9       0 / 10              0 / 4,000   0.0%          0            -           -           1.000  -
  changed cells by point, all 10 runs: 0: 40, 1: 40, 2: 40, 3: 40
  changed cells by task, all 10 runs: aime 160, gpqa_diamond 0, livecodebench 0, mmlu_pro 0
  deepseek/deepseek-v4-flash: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 40 (0 to inline)
  deepseek/deepseek-v4-pro: times 0.5 changes 40 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  moonshotai/kimi-k2.7-code: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  z-ai/glm-5.3: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  z-ai/glm-5.3-flash: times 0.5 changes 40 cells (0 to inline), times 2.0 changes 40 (0 to inline)
```

```text
$ python research/delegation_price_sensitivity.py --dataset tau2-bench --matrix tau2-calls.jsonl
One model's list price halved or doubled on the tau2-bench per domain delegation results: each cell re-decided with that model's input and output prices times 0.5 or 2.0, both picks scored at the committed prices
tau2-bench per domain, base grid (`evidence/tau2-bench-delegation/results.json`): 21,600 cells, 3 tasks, 6 bars, 2 flavors, 4 points, 3 parents, 50 seeds, 3 models, so 6 runs; every cell's decision and held-out sum reproduced at the committed prices
  flavor          bar  runs moving  most changed / cells  share  to inline  success gap  cost ratio  all cost ratio  by
  cost_effective  0.3       2 / 6             108 / 1,800   6.0%          0      -0.0732       3.427           1.076  anthropic/claude-3-7-sonnet-20250219 times 0.5
  cost_effective  0.4       2 / 6             120 / 1,800   6.7%          0      -0.0758       3.399           1.059  anthropic/claude-3-7-sonnet-20250219 times 0.5
  cost_effective  0.5       2 / 6             204 / 1,800  11.3%          0      +0.0029       2.889           1.121  anthropic/claude-3-7-sonnet-20250219 times 0.5
  cost_effective  0.6       2 / 6             348 / 1,800  19.3%          0      +0.0612       2.770           1.171  anthropic/claude-3-7-sonnet-20250219 times 0.5
  cost_effective  0.7       2 / 6             180 / 1,800  10.0%          0      +0.0220       3.003           1.066  anthropic/claude-3-7-sonnet-20250219 times 0.5
  cost_effective  0.8       2 / 6             168 / 1,800   9.3%          0      +0.0163       3.039           1.060  anthropic/claude-3-7-sonnet-20250219 times 0.5
  cost_blind      0.3       0 / 6               0 / 1,800   0.0%          0            -           -           1.000  -
  cost_blind      0.4       0 / 6               0 / 1,800   0.0%          0            -           -           1.000  -
  cost_blind      0.5       0 / 6               0 / 1,800   0.0%          0            -           -           1.000  -
  cost_blind      0.6       0 / 6               0 / 1,800   0.0%          0            -           -           1.000  -
  cost_blind      0.7       0 / 6               0 / 1,800   0.0%          0            -           -           1.000  -
  cost_blind      0.8       0 / 6               0 / 1,800   0.0%          0            -           -           1.000  -
  changed cells by point, all 6 runs: 0: 564, 1: 564, 2: 564, 3: 564
  changed cells by task, all 6 runs: airline 1,416, retail 840, telecom 0
  anthropic/claude-3-7-sonnet-20250219: times 0.5 changes 1,128 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  openai/gpt-4.1-2025-04-14: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 1,128 (0 to inline)
  openai/gpt-4.1-mini-2025-04-14: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
```

```text
$ python research/delegation_price_sensitivity.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl
One model's list price halved or doubled on the tau2-bench pooled delegation results: each cell re-decided with that model's input and output prices times 0.5 or 2.0, both picks scored at the committed prices
tau2-bench pooled, base grid (`evidence/tau2-bench-delegation/pooled.json`): 7,200 cells, 6 bars, 2 flavors, 4 points, 3 parents, 50 seeds, 3 models, so 6 runs; every cell's decision and held-out sum reproduced at the committed prices
  flavor          bar  runs moving  most changed / cells  share  to inline  success gap  cost ratio  all cost ratio  by
  cost_effective  0.3       0 / 6               0 / 600     0.0%          0            -           -           1.000  -
  cost_effective  0.4       0 / 6               0 / 600     0.0%          0            -           -           1.000  -
  cost_effective  0.5       2 / 6              60 / 600    10.0%          0      +0.0917       2.385           1.068  anthropic/claude-3-7-sonnet-20250219 times 0.5
  cost_effective  0.6       2 / 6              12 / 600     2.0%          0      +0.0942       2.490           1.013  anthropic/claude-3-7-sonnet-20250219 times 0.5
  cost_effective  0.7       2 / 6              12 / 600     2.0%          0      +0.0942       2.490           1.013  anthropic/claude-3-7-sonnet-20250219 times 0.5
  cost_effective  0.8       2 / 6              12 / 600     2.0%          0      +0.0942       2.490           1.013  anthropic/claude-3-7-sonnet-20250219 times 0.5
  cost_blind      0.3       0 / 6               0 / 600     0.0%          0            -           -           1.000  -
  cost_blind      0.4       0 / 6               0 / 600     0.0%          0            -           -           1.000  -
  cost_blind      0.5       0 / 6               0 / 600     0.0%          0            -           -           1.000  -
  cost_blind      0.6       0 / 6               0 / 600     0.0%          0            -           -           1.000  -
  cost_blind      0.7       0 / 6               0 / 600     0.0%          0            -           -           1.000  -
  cost_blind      0.8       0 / 6               0 / 600     0.0%          0            -           -           1.000  -
  changed cells by point, all 6 runs: 0: 48, 1: 48, 2: 48, 3: 48
  anthropic/claude-3-7-sonnet-20250219: times 0.5 changes 96 cells (0 to inline), times 2.0 changes 0 (0 to inline)
  openai/gpt-4.1-2025-04-14: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 96 (0 to inline)
  openai/gpt-4.1-mini-2025-04-14: times 0.5 changes 0 cells (0 to inline), times 2.0 changes 0 (0 to inline)
```

## Reading it

- The moved decisions go to a delegated pick and rarely inline. The delegate a decision weighs is the router's `cost_effective` pick, the cheapest of the models whose calibration bound clears the bar, so a wrong price can change that pick on any cell where it is close in cost to the next; the parent's own path wins only on the few cells where the two paths cost about the same, as on the re-read note's folded point
- So a price error moves cells at every point (the `changed cells by point` lines), unlike the re-read share and the brief's output, which move the cost of one path against the other and change cells only where the paths are close
- On AutoBench most models move no cell at either factor (the per-model lines); on LLMRouterBench every model moves some; on the Response Bank and on tau2-bench some models move none
- On AutoBench, at bar 0.7 doubling `openai/gpt-5.6-luna`'s prices, the run that moves the most, sends the work to picks that cost more at the list price and, on the cells it moves, are right less often on the held-out half. At bar 0.8 halving `openai/gpt-5.6-sol`'s prices, the run that moves the most, makes it look cheaper than the delegate the decision picked, so the moved picks cost more and, on those cells, are right more often
- On LLMRouterBench the share the run that moves the most changes falls as the bar rises, the moved picks cost more at every bar, and whether they are right more or less often on the held-out half varies by bar
- On the Response Bank a price error moves far fewer cells than on the other two datasets, and at each bar fewer than a zero re-read share moves in [reread-sensitivity.md](reread-sensitivity.md): the runs that move a cell each change the same number, all of one task and at every point, none of them inline, and at each bar the run that moves the most sends the work to picks that cost more at the list price and, on the cells it moves, are right less often on the held-out half
- On tau2-bench, where [reread-sensitivity.md](reread-sensitivity.md) changes no cell at any setting, a price error moves cells at every `cost_effective` bar per domain and at all but the two lowest pooled, in two runs only, halving one model's prices or doubling another's, each of which makes the first look cheaper against the second, and none of the moved cells go inline. In the run that moves the most at each bar where one moves, the moved picks cost more than twice as much at the list price; per domain they are right more often at some bars and less often at others, pooled more often at every such bar
- For each `cost_effective` bar's run that moves the most, on AutoBench and LLMRouterBench, the cost over all the bar's cells rises at the list price, on LLMRouterBench by a few thousandths at most, far less than on AutoBench; on the Response Bank it is unchanged at the block's three decimals; on tau2-bench it rises at every bar where a run moves a cell, by more than on LLMRouterBench at any bar
- `cost_blind` compares no costs (13.5), and no run moves one of its cells

## Recommendation

- Keep a registry's prices current for delegation as for routing: on AutoBench and LLMRouterBench one wrong price moves up to about half of a bar's `cost_effective` delegation decisions, far more than either input [reread-sensitivity.md](reread-sensitivity.md) varies, and raises the bill, on AutoBench by far more than those inputs move it and on LLMRouterBench by about as little, so refresh a model's row when its vendor changes a price, as [price-sensitivity.md](price-sensitivity.md) recommends for routing; on the Response Bank it moves a few decisions of one task and leaves the bill over each bar's cells unchanged at three decimals, and on tau2-bench, where neither input the re-read note varies moves a cell, it moves up to about a fifth of a bar's cells per domain and raises the bill, so how far a wrong price reaches depends on the dataset, and a small effect on one is no bound on another
- Every committed delegation results file is now measured, and no one bound holds across the four delegation datasets: README Limitations' prices bullet links this note and gives the range, from a few cells of one task to about half of a bar's cells, rather than one figure, right after its routing sentence on a stale price, which stays as it is

## Limits

- Four datasets, AutoBench 2026, LLMRouterBench, the LLM Routing Response Bank and tau2-bench, per domain and pooled, every committed delegation results file; the ledger hand-off runs carry no price, so a price error does not apply to them
- Two factors, one model at a time, both of its prices together; no run scales two models, or one of a model's two prices alone
- The held-out cost is 13.2's list-price approximation at the committed prices, not a measured bill
- The script re-decides with the 13.9 helper `_router`, which the package does not export; the check at the committed prices is what keeps the two in step

## Regenerate

```bash
python -m pip install -e .
python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens --registry autobench-pool.json
python research/delegation_price_sensitivity.py --matrix autobench-tokens.jsonl --registry autobench-pool.json
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python research/delegation_price_sensitivity.py --dataset llmrouterbench --matrix llmrouterbench-matrix.jsonl
python evidence/response-bank/convert.py --out response-bank-matrix.jsonl
python research/delegation_price_sensitivity.py --dataset response-bank --matrix response-bank-matrix.jsonl
python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls
python research/delegation_price_sensitivity.py --dataset tau2-bench --matrix tau2-calls.jsonl
python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all
python research/delegation_price_sensitivity.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl
```
