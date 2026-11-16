# Whether the re-read share and the brief's output move a committed delegation decision

v1.404 and v1.405 give `decide_delegation` the two inputs that [the ledger runs' note](ledger-cost-model.md) found missing: `output_reread_share` (sigma), the share of each work call's output that later calls re-read, and `brief_output_tokens` (W), what the call that writes the brief writes. Every committed delegation result keeps sigma at 1.0 and W at the brief's size B (13.1), so no note said whether either input changes a decision that [the AutoBench delegation results](../evidence/delegation/RESULTS.md), [the LLMRouterBench delegation results](../evidence/llmrouterbench-delegation/RESULTS.md), [the LLM Routing Response Bank delegation results](../evidence/response-bank-delegation/RESULTS.md) or [the tau2-bench delegation results](../evidence/tau2-bench-delegation/RESULTS.md) report. This note reruns both AutoBench grids, the LLMRouterBench grid, the Response Bank grid and the tau2-bench grid per domain and pooled, re-decides every cell at sigma 0, sigma 0.5 and W = 2 B, and scores the committed pick and the new one at that setting's costs.

## Facts

- Neither input moves more than a small share of the committed delegation decisions on AutoBench, LLMRouterBench or the LLM Routing Response Bank, and neither moves any on tau2-bench: each changes only `cost_effective` cells, no `cost_blind` decision, and leaves the cost over all the cells of a file, flavor and bar within a few thousandths of the committed picks' cost at the same setting
- Data: the AutoBench 2026 matrix and pool that evidence/delegation/results.py runs, its base grid (16,000 cells: 2 bars, 2 flavors, 4 points, 20 parents, 50 seeds) and its variant grid (12,000 cells, 3 points); and the LLMRouterBench rows and registry that evidence/llmrouterbench-delegation/results.py runs, its one grid (115,200 cells: 9 tasks, 4 bars, 2 flavors, 4 points, 8 parents, 50 seeds); and the Response Bank rows and registry that evidence/response-bank-delegation/results.py runs, its one grid (16,000 cells: 4 tasks, 2 bars, 2 flavors, 4 points, 5 parents, 50 seeds); and the tau2-bench `--calls` rows and registry that evidence/tau2-bench-delegation/results.py runs, its grid per domain (21,600 cells: 3 tasks, 6 bars, 2 flavors, 4 points, 3 parents, 50 seeds) and pooled (7,200 cells, one task); every cell's decision and held-out sum is reproduced at sigma 1.0 and W = B before either input is varied
- Base grid, `cost_effective`, bar 0.7: sigma 0 changes 19 of 4,000 cells (0.5%), sigma 0.5 changes 5 (0.1%) and W = 2 B changes 18 (0.5%), every one to inline; the new picks score -0.1348, -0.1132 and -0.1269 in held-out success against the committed picks, at 1.049, 1.188 and 1.089 times their cost. At bar 0.8 each setting changes 1 cell, to inline, at +0.0000 in success and 0.829 to 0.943 times the cost. Every changed base-grid cell is at point 3, where inline work is folded into the parent's next call
- Variant grid: only at bar 0.8 in `cost_effective`, where sigma 0 and sigma 0.5 each change 20 of 3,000 cells (0.7%), all at variant point 2, the longest run, and none to inline: the work goes to another delegate, for +0.0500 in held-out success at 1.092 and 1.128 times the cost; W = 2 B changes none
- LLMRouterBench, `cost_effective`: at a bar's 14,400 cells sigma 0 changes 142 to 180 (1.0% to 1.2%), sigma 0.5 47 to 103 (0.3% to 0.7%) and W = 2 B 94 to 380 (0.7% to 2.6%, the most at bars 0.1 and 0.3), every one to inline. On the changed cells the new picks cost 0.834 to 0.975 times the committed picks, for a held-out success gap of -0.0282 to +0.0734, and of -0.0047 to +0.0001 at sigma 0
- LLMRouterBench by point and task: every sigma change is at point 3, and W = 2 B also changes 104 cells at point 0. At sigma 0 and 0.5 no mmlupro or simpleqa cell changes, and at sigma 0 hle and arc-agi change the most (200 and 192); at W = 2 B every task changes some, gpqa the most (229)
- Response Bank, `cost_effective`: sigma 0 changes 154 of a bar's 4,000 cells at both bars (3.9%), sigma 0.5 changes 0 and 4 (0.0% and 0.1%) and W = 2 B 41 and 4 (1.0% and 0.1%), every one to inline and at point 3. On the changed cells of each flavor, bar and setting the new picks score +0.0000 to +0.0104 in held-out success against the committed picks, never less, at 0.877 to 1.028 times their cost, the one ratio over 1 at sigma 0 and bar 0.8
- Response Bank by task: at sigma 0 aime, gpqa_diamond and livecodebench change 100 cells each and mmlu_pro 8; at sigma 0.5 and W = 2 B only mmlu_pro changes (4 and 45)
- tau2-bench: no cell changes at any setting, per domain (21,600 cells) or pooled (7,200), in either flavor, at any bar or point
- Over all the cells of a file, flavor and bar the cost ratio is 1.000 to 1.003 on AutoBench, 0.997 to 1.000 on LLMRouterBench, 0.996 to 1.000 on the Response Bank and 1.000 on tau2-bench, where no pick changes

## Method

- The matrix, registry, bars, seeds and points are the ones evidence/delegation/results.py runs (13.10). With `--dataset llmrouterbench` they are the ones evidence/llmrouterbench-delegation/results.py runs (13.13): the converter's default matrix, the rows its `select_rows` keeps for the committed registry, its bars and seeds and the four base points; with `--dataset response-bank` they are the ones evidence/response-bank-delegation/results.py runs (13.14): the response-bank converter's default matrix, the rows the same `select_rows` keeps for its committed registry, its bars and seeds and the same four points; with `--dataset tau2-bench` (`tau2-bench-pooled`) they are the ones evidence/tau2-bench-delegation/results.py runs (13.12): the tau2-bench converter's `--calls` (`--calls --task-by all`) matrix, every row of it, the committed registry, its bars and seeds and the same four points, checked against results.json (pooled.json). `evaluate_delegation` (13.9) runs each grid, and its config, tasks and summary must be the committed file's, or the script exits 2
- Each cell (bar, flavor, point, parent, seed) is re-decided by `decide_delegation` with the run's own calibration half and router, the 13.9 ones, so sigma and W are the only inputs that differ. At sigma 1.0 and W = B the re-decided mode and model must be the cell's, and the held-out correct count and cost the script computes for them, for always inline and for always delegating must be the cell's, or the script exits 2
- What sigma scales, from 13.2 (v1.404): each re-read of a work call's output S_out and nothing else. Each read `w_out * S_out` is `w_out * sigma * S_out` and each read `K * (S_in + S_out)` is `K * (S_in + sigma * S_out)`; the written outputs, the brief B, the result R and every read of the context C keep their sizes. W is the decision turn's output on the delegated path, `P.cost(0, W)` in 13.2 (v1.410), and every read of the brief stays B
- On tau2-bench each row carries its calls' sizes (13.9 v1.74): a conversation's work is its own K calls, call j reading the new input a_1 to a_j and the outputs b_1 to b_(j-1), each output re-read at sigma, so the K calls read `sum (K - j + 1) a_j + sigma * sum (K - j) b_j` and each later read of the work, of its new input A and output O, is `A + sigma * O`; at sigma 1.0 each is the 13.9 cost. The decision forecasts the work as the calibration half's median call count (`work_calls`) at each model's rounded-up mean sizes per call, as 13.9 does. A row without per-call sizes on tau2-bench, or one with them on another dataset, exits 2
- So at one work call, the AutoBench base grid and every LLMRouterBench and Response Bank point, w_out is 0 and sigma lowers only the inline path's cost, through the parent's calls after the work, which re-read its output; the delegated path's cost and the delegate's pick do not move. At more work calls, variant points 0 and 2, sigma also lowers each candidate delegate's cost in the delegate's own pick, so it can move the model the work goes to. W raises only the delegated path's cost. On tau2-bench the decision's `work_calls` is above one on every domain ([the tau2-bench delegation results](../evidence/tau2-bench-delegation/RESULTS.md)), so there too sigma lowers each candidate delegate's cost
- A cell changes when its mode or its model changes. Both picks of a changed cell are scored on the cell's held-out half at that setting's 13.2 list-price costs, the bill a caller would see whose model really re-reads that share or writes that much: the committed pick against the one the decision makes once told
- Columns: `changed / cells` and `share` count the changed cells, `to inline` those whose new mode is inline; `success gap` is the new picks' held-out correct count minus the committed picks', over the changed cells' held-out items; `cost ratio` is the new picks' held-out cost over the committed picks' on the changed cells, and `all cost ratio` the same over every cell. The `changed cells by reason` lines give the committed decision's 13.5 reason for the changed cells, with how many seeds and parents they fall on and the parent most of them have; on a run of more than one task the header names the task count and the `changed cells by task` lines give each task's changed cells

## Results

```text
$ python research/reread_sensitivity.py --matrix autobench-tokens.jsonl --registry autobench-pool.json
The re-read share and the brief's output on the AutoBench 2026 delegation results: each cell re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs
AutoBench 2026, base grid (`evidence/delegation/results.json`): 16,000 cells, 2 bars, 2 flavors, 4 points, 20 parents, 50 seeds; every cell's decision and held-out sum reproduced at sigma 1.0 and W = B
  flavor          bar  setting    changed / cells  share  to inline  success gap  cost ratio  all cost ratio
  cost_effective  0.7  sigma 0         19 / 4,000   0.5%         19      -0.1348       1.049           1.000
  cost_effective  0.7  sigma 0.5        5 / 4,000   0.1%          5      -0.1132       1.188           1.000
  cost_effective  0.7  W = 2 B         18 / 4,000   0.5%         18      -0.1269       1.089           1.000
  cost_effective  0.8  sigma 0          1 / 4,000   0.0%          1      +0.0000       0.829           1.000
  cost_effective  0.8  sigma 0.5        1 / 4,000   0.0%          1      +0.0000       0.925           1.000
  cost_effective  0.8  W = 2 B          1 / 4,000   0.0%          1      +0.0000       0.943           1.000
  cost_blind      0.7  sigma 0          0 / 4,000   0.0%          0            -           -           1.000
  cost_blind      0.7  sigma 0.5        0 / 4,000   0.0%          0            -           -           1.000
  cost_blind      0.7  W = 2 B          0 / 4,000   0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0          0 / 4,000   0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0.5        0 / 4,000   0.0%          0            -           -           1.000
  cost_blind      0.8  W = 2 B          0 / 4,000   0.0%          0            -           -           1.000
  changed cells by point, sigma 0: 0: 0, 1: 0, 2: 0, 3: 20
  changed cells by point, sigma 0.5: 0: 0, 1: 0, 2: 0, 3: 6
  changed cells by point, W = 2 B: 0: 0, 1: 0, 2: 0, 3: 19
  changed cells by reason, sigma 0: delegate_cheaper 19, none_clear 1; 18 seeds, 3 parents, the most 16 of google/gemini-3.7-flash
  changed cells by reason, sigma 0.5: delegate_cheaper 5, none_clear 1; 6 seeds, 2 parents, the most 5 of google/gemini-3.7-flash
  changed cells by reason, W = 2 B: delegate_cheaper 18, none_clear 1; 16 seeds, 4 parents, the most 15 of google/gemini-3.7-flash
AutoBench 2026, variants grid (`evidence/delegation/variants.json`): 12,000 cells, 2 bars, 2 flavors, 3 points, 20 parents, 50 seeds; every cell's decision and held-out sum reproduced at sigma 1.0 and W = B
  flavor          bar  setting    changed / cells  share  to inline  success gap  cost ratio  all cost ratio
  cost_effective  0.7  sigma 0          0 / 3,000   0.0%          0            -           -           1.000
  cost_effective  0.7  sigma 0.5        0 / 3,000   0.0%          0            -           -           1.000
  cost_effective  0.7  W = 2 B          0 / 3,000   0.0%          0            -           -           1.000
  cost_effective  0.8  sigma 0         20 / 3,000   0.7%          0      +0.0500       1.092           1.002
  cost_effective  0.8  sigma 0.5       20 / 3,000   0.7%          0      +0.0500       1.128           1.003
  cost_effective  0.8  W = 2 B          0 / 3,000   0.0%          0            -           -           1.000
  cost_blind      0.7  sigma 0          0 / 3,000   0.0%          0            -           -           1.000
  cost_blind      0.7  sigma 0.5        0 / 3,000   0.0%          0            -           -           1.000
  cost_blind      0.7  W = 2 B          0 / 3,000   0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0          0 / 3,000   0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0.5        0 / 3,000   0.0%          0            -           -           1.000
  cost_blind      0.8  W = 2 B          0 / 3,000   0.0%          0            -           -           1.000
  changed cells by point, sigma 0: 0: 0, 1: 0, 2: 20
  changed cells by point, sigma 0.5: 0: 0, 1: 0, 2: 20
  changed cells by point, W = 2 B: 0: 0, 1: 0, 2: 0
  changed cells by reason, sigma 0: none_clear 20; 1 seed, 20 parents, the most 1 of anthropic/claude-sonnet-5
  changed cells by reason, sigma 0.5: none_clear 20; 1 seed, 20 parents, the most 1 of anthropic/claude-sonnet-5
  changed cells by reason, W = 2 B: none
```

```text
$ python research/reread_sensitivity.py --dataset llmrouterbench --matrix llmrouterbench-matrix.jsonl
The re-read share and the brief's output on the LLMRouterBench delegation results: each cell re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs
LLMRouterBench, base grid (`evidence/llmrouterbench-delegation/results.json`): 115,200 cells, 9 tasks, 4 bars, 2 flavors, 4 points, 8 parents, 50 seeds; every cell's decision and held-out sum reproduced at sigma 1.0 and W = B
  flavor          bar  setting    changed / cells  share  to inline  success gap  cost ratio  all cost ratio
  cost_effective  0.1  sigma 0        142 / 14,400   1.0%        142      -0.0047       0.937           0.999
  cost_effective  0.1  sigma 0.5       47 / 14,400   0.3%         47      -0.0282       0.937           1.000
  cost_effective  0.1  W = 2 B        377 / 14,400   2.6%        377      +0.0734       0.834           0.997
  cost_effective  0.3  sigma 0        144 / 14,400   1.0%        144      -0.0046       0.927           0.998
  cost_effective  0.3  sigma 0.5       85 / 14,400   0.6%         85      -0.0046       0.971           0.999
  cost_effective  0.3  W = 2 B        380 / 14,400   2.6%        380      -0.0012       0.914           0.997
  cost_effective  0.5  sigma 0        169 / 14,400   1.2%        169      -0.0036       0.926           0.998
  cost_effective  0.5  sigma 0.5      103 / 14,400   0.7%        103      -0.0039       0.970           0.999
  cost_effective  0.5  W = 2 B        272 / 14,400   1.9%        272      -0.0187       0.949           0.999
  cost_effective  0.8  sigma 0        180 / 14,400   1.2%        180      +0.0001       0.927           0.999
  cost_effective  0.8  sigma 0.5       91 / 14,400   0.6%         91      +0.0000       0.971           1.000
  cost_effective  0.8  W = 2 B         94 / 14,400   0.7%         94      +0.0017       0.975           1.000
  cost_blind      0.1  sigma 0          0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.1  sigma 0.5        0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.1  W = 2 B          0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.3  sigma 0          0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.3  sigma 0.5        0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.3  W = 2 B          0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.5  sigma 0          0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.5  sigma 0.5        0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.5  W = 2 B          0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0          0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0.5        0 / 14,400   0.0%          0            -           -           1.000
  cost_blind      0.8  W = 2 B          0 / 14,400   0.0%          0            -           -           1.000
  changed cells by point, sigma 0: 0: 0, 1: 0, 2: 0, 3: 635
  changed cells by point, sigma 0.5: 0: 0, 1: 0, 2: 0, 3: 326
  changed cells by point, W = 2 B: 0: 104, 1: 0, 2: 0, 3: 1019
  changed cells by reason, sigma 0: none_clear 403, delegate_cheaper 232; 50 seeds, 8 parents, the most 392 of openai/gpt-5
  changed cells by reason, sigma 0.5: none_clear 248, delegate_cheaper 78; 50 seeds, 6 parents, the most 240 of openai/gpt-5
  changed cells by reason, W = 2 B: delegate_cheaper 874, none_clear 249; 50 seeds, 8 parents, the most 406 of openai/gpt-5-chat
  changed cells by task, sigma 0: aime 138, arc-agi 192, arenahard 28, gpqa 4, hle 200, livecodebench 45, livemathbench 28, mmlupro 0, simpleqa 0
  changed cells by task, sigma 0.5: aime 99, arc-agi 5, arenahard 25, gpqa 4, hle 150, livecodebench 42, livemathbench 1, mmlupro 0, simpleqa 0
  changed cells by task, W = 2 B: aime 101, arc-agi 38, arenahard 145, gpqa 229, hle 150, livecodebench 191, livemathbench 161, mmlupro 8, simpleqa 100
```

```text
$ python research/reread_sensitivity.py --dataset response-bank --matrix response-bank-matrix.jsonl
The re-read share and the brief's output on the LLM Routing Response Bank delegation results: each cell re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs
LLM Routing Response Bank, base grid (`evidence/response-bank-delegation/results.json`): 16,000 cells, 4 tasks, 2 bars, 2 flavors, 4 points, 5 parents, 50 seeds; every cell's decision and held-out sum reproduced at sigma 1.0 and W = B
  flavor          bar  setting    changed / cells  share  to inline  success gap  cost ratio  all cost ratio
  cost_effective  0.8  sigma 0        154 / 4,000   3.9%        154      +0.0041       1.028           1.000
  cost_effective  0.8  sigma 0.5        0 / 4,000   0.0%          0            -           -           1.000
  cost_effective  0.8  W = 2 B         41 / 4,000   1.0%         41      +0.0104       0.944           0.996
  cost_effective  0.9  sigma 0        154 / 4,000   3.9%        154      +0.0000       0.889           0.999
  cost_effective  0.9  sigma 0.5        4 / 4,000   0.1%          4      +0.0000       0.877           1.000
  cost_effective  0.9  W = 2 B          4 / 4,000   0.1%          4      +0.0000       0.931           1.000
  cost_blind      0.8  sigma 0          0 / 4,000   0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0.5        0 / 4,000   0.0%          0            -           -           1.000
  cost_blind      0.8  W = 2 B          0 / 4,000   0.0%          0            -           -           1.000
  cost_blind      0.9  sigma 0          0 / 4,000   0.0%          0            -           -           1.000
  cost_blind      0.9  sigma 0.5        0 / 4,000   0.0%          0            -           -           1.000
  cost_blind      0.9  W = 2 B          0 / 4,000   0.0%          0            -           -           1.000
  changed cells by point, sigma 0: 0: 0, 1: 0, 2: 0, 3: 308
  changed cells by point, sigma 0.5: 0: 0, 1: 0, 2: 0, 3: 4
  changed cells by point, W = 2 B: 0: 0, 1: 0, 2: 0, 3: 45
  changed cells by reason, sigma 0: none_clear 206, delegate_cheaper 102; 50 seeds, 4 parents, the most 149 of deepseek/deepseek-v4-flash
  changed cells by reason, sigma 0.5: none_clear 4; 4 seeds, 1 parent, the most 4 of deepseek/deepseek-v4-pro
  changed cells by reason, W = 2 B: delegate_cheaper 41, none_clear 4; 43 seeds, 2 parents, the most 41 of z-ai/glm-5.3
  changed cells by task, sigma 0: aime 100, gpqa_diamond 100, livecodebench 100, mmlu_pro 8
  changed cells by task, sigma 0.5: aime 0, gpqa_diamond 0, livecodebench 0, mmlu_pro 4
  changed cells by task, W = 2 B: aime 0, gpqa_diamond 0, livecodebench 0, mmlu_pro 45
```

```text
$ python research/reread_sensitivity.py --dataset tau2-bench --matrix tau2-calls.jsonl
The re-read share and the brief's output on the tau2-bench per domain delegation results: each cell re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs
tau2-bench per domain, base grid (`evidence/tau2-bench-delegation/results.json`): 21,600 cells, 3 tasks, 6 bars, 2 flavors, 4 points, 3 parents, 50 seeds; every cell's decision and held-out sum reproduced at sigma 1.0 and W = B
  flavor          bar  setting    changed / cells  share  to inline  success gap  cost ratio  all cost ratio
  cost_effective  0.3  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.3  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.3  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.4  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.4  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.4  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.5  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.5  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.5  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.6  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.6  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.6  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.7  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.7  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.7  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.8  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.8  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_effective  0.8  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.3  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.3  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.3  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.4  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.4  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.4  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.5  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.5  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.5  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.6  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.6  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.6  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.7  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.7  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.7  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0          0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0.5        0 / 1,800   0.0%          0            -           -           1.000
  cost_blind      0.8  W = 2 B          0 / 1,800   0.0%          0            -           -           1.000
  changed cells by point, sigma 0: 0: 0, 1: 0, 2: 0, 3: 0
  changed cells by point, sigma 0.5: 0: 0, 1: 0, 2: 0, 3: 0
  changed cells by point, W = 2 B: 0: 0, 1: 0, 2: 0, 3: 0
  changed cells by reason, sigma 0: none
  changed cells by reason, sigma 0.5: none
  changed cells by reason, W = 2 B: none
  changed cells by task, sigma 0: airline 0, retail 0, telecom 0
  changed cells by task, sigma 0.5: airline 0, retail 0, telecom 0
  changed cells by task, W = 2 B: airline 0, retail 0, telecom 0
```

```text
$ python research/reread_sensitivity.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl
The re-read share and the brief's output on the tau2-bench pooled delegation results: each cell re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs
tau2-bench pooled, base grid (`evidence/tau2-bench-delegation/pooled.json`): 7,200 cells, 6 bars, 2 flavors, 4 points, 3 parents, 50 seeds; every cell's decision and held-out sum reproduced at sigma 1.0 and W = B
  flavor          bar  setting    changed / cells  share  to inline  success gap  cost ratio  all cost ratio
  cost_effective  0.3  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.3  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.3  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.4  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.4  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.4  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.5  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.5  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.5  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.6  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.6  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.6  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.7  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.7  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.7  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.8  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.8  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_effective  0.8  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.3  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.3  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.3  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.4  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.4  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.4  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.5  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.5  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.5  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.6  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.6  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.6  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.7  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.7  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.7  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0          0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.8  sigma 0.5        0 / 600     0.0%          0            -           -           1.000
  cost_blind      0.8  W = 2 B          0 / 600     0.0%          0            -           -           1.000
  changed cells by point, sigma 0: 0: 0, 1: 0, 2: 0, 3: 0
  changed cells by point, sigma 0.5: 0: 0, 1: 0, 2: 0, 3: 0
  changed cells by point, W = 2 B: 0: 0, 1: 0, 2: 0, 3: 0
  changed cells by reason, sigma 0: none
  changed cells by reason, sigma 0.5: none
  changed cells by reason, W = 2 B: none
```


## Reading it

- The changes sit where the two paths cost about the same. At point 3 the folded inline work adds no read of the context, so the 13.5 cost comparison is close and a lower inline cost (sigma) or a higher delegated one (W) tips a few cells to inline; where inline work is a call of its own, points 0 to 2, its read of the context makes inline far dearer and nothing moves. All but one of each setting's changed base-grid cells are ones the decision delegated as the cheaper path (`delegate_cheaper`), and most of them are one parent's
- The new base-grid picks are not better on the held-out half. At bar 0.7 the parent, which every new pick takes, is right less often on those cells than the delegate it replaces, which `cost_effective` allows for a path that clears the bar; and at bar 0.7 the new picks also cost more: the decision prices each path at the calibration half's mean sizes (13.9), so next to a tie the held-out items can put the cheaper path on the other side
- The variant cells are one seed's 20 parents at variant point 2 and bar 0.8, every one a `none_clear` cell (13.5), where no path clears the bar and the work goes to the delegate's fallback pick. At many work calls sigma lowers each candidate's cost in that pick (13.2), and here it moves the pick to a delegate that is right more often, at a higher cost
- `cost_blind` never compares the paths' costs (13.5), and no `cost_blind` cell moves on any grid
- The AutoBench bound does not carry over as a number: LLMRouterBench changes up to 2.6% of a flavor and bar's cells and the Response Bank 3.9%, against 0.7%. It carries over in direction: every LLMRouterBench and Response Bank point is one work call, where sigma lowers only the inline path's cost and W raises only the delegated path's, so a change can only be to inline, and every one is
- On LLMRouterBench, unlike AutoBench's base grid at bar 0.7, the new picks cost less on the changed cells (0.834 to 0.975 times), so a caller whose model re-reads less or writes more than the brief would pay a little less by passing the two inputs; over all the cells the cost ratio is at least 0.997. Most of its sigma changes are cells where no path clears the bar (`none_clear` 403 of 635 at sigma 0, 248 of 326 at sigma 0.5), and most of its W = 2 B changes are ones the decision delegated as the cheaper path (`delegate_cheaper` 874)
- On the Response Bank sigma 0 moves the largest share of any dataset and setting, 154 cells at each bar (3.9%), most of them `none_clear` (206 of 308) and the most of them deepseek/deepseek-v4-flash's (149), while sigma 0.5 and W = 2 B move only mmlu_pro cells. In no flavor, bar and setting are the new picks worse on the held-out half, and they cost less on the changed cells except at sigma 0 and bar 0.8: there, as at AutoBench's bar 0.7, the decision prices each path at the calibration half's mean sizes, so next to a tie the held-out items can put the cheaper path on the other side
- On tau2-bench nothing moves, per domain or pooled. Every cell where the decision compares the two paths' costs delegated as the cheaper path (the tau2-bench delegation results find no `inline_cheaper` cell), and by 13.2 a conversation's many work calls put sigma on both paths, so a lower sigma cheapens the delegated work too, while a doubled W adds B tokens of the parent's output to a path that pays for every call of a conversation; in `cost_effective` neither moves a cell back to inline or to another delegate, and `cost_blind` compares no costs

## Recommendation

- Keep every committed delegation result at sigma 1.0 and W = B: neither input changes more than 0.7% of the cells of an AutoBench file, flavor and bar, 2.6% of LLMRouterBench's, 3.9% of the Response Bank's or none of tau2-bench's, per domain or pooled, and the cost over all of them moves by a factor of 0.996 to 1.003
- README Limitations' inline-or-delegate cost bullet gives these bounds, after its sentences on the two inputs, and links this note

## Limits

- Four datasets, AutoBench 2026, LLMRouterBench, the LLM Routing Response Bank and tau2-bench, whose grids fix the brief's size and the work-call counts (one work call on every LLMRouterBench and Response Bank point, each conversation's own calls on tau2-bench), so the note measures the two inputs only at those points
- Three settings, each varying one input with the other at its default; no run lowers sigma and raises W together, as a model that drops its reasoning from its history and reasons before it writes the brief would. A model's own sigma and W are its caller's to measure; the ledger runs give one pair
- The held-out cost is 13.2's list-price approximation at each setting, not a measured bill
- The script re-decides with the 13.9 helpers `_calibrate` and `_router`, which the package does not export; the check at sigma 1.0 and W = B is what keeps the two in step

## Regenerate

```bash
python -m pip install -e .
python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens --registry autobench-pool.json
python research/reread_sensitivity.py --matrix autobench-tokens.jsonl --registry autobench-pool.json
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python research/reread_sensitivity.py --dataset llmrouterbench --matrix llmrouterbench-matrix.jsonl
python evidence/response-bank/convert.py --out response-bank-matrix.jsonl
python research/reread_sensitivity.py --dataset response-bank --matrix response-bank-matrix.jsonl
python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls
python research/reread_sensitivity.py --dataset tau2-bench --matrix tau2-calls.jsonl
python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all
python research/reread_sensitivity.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl
```
