# Do held-out items' cheaper delegation paths differ from the per-task decision?

## Facts

- Question: on the LLMRouterBench (`DESIGN.md` 13.13), AutoBench 2026 (`DESIGN.md` 13.10) and tau2-bench (`DESIGN.md` 13.12, per domain and pooled) delegation evidence, how often is a held-out item's cheaper path, inline or delegated, by list price at that item's own sizes, not the path the per-task `DESIGN.md` 13.5 decision took, and what would taking it give?
- Rule, stated before any number: an item's cheaper path is the one whose `DESIGN.md` 13.9 list-price cost at its recorded sizes is lower, the decision's mode on an exact tie; `pick` takes it on every cell, `size rule` only on the cells where the decision compared the two paths' costs (see Method).
- Reads the converter's matrix of the pinned LLMRouterBench file, the committed `evidence/llmrouterbench-delegation/registry.json`, and its `results.json`, whose summary the rerun must equal; with `--dataset autobench`, the AutoBench 2026 converter's `--task-by all --tokens` matrix and `--registry` pool (`DESIGN.md` 12.9) and the committed `evidence/delegation/results.json`, whose summary that rerun must equal; with `--dataset tau2-bench` or `tau2-bench-pooled`, the tau2-bench converter's `--calls` or `--calls --task-by all` matrix (`DESIGN.md` 12.14), the committed `evidence/tau2-bench-delegation/registry.json`, and its `results.json` or `pooled.json`, whose summary that rerun must equal. No library code, harness or results file changes.
- Short answer: often, but where a rule could fairly take it, it saves little. On LLMRouterBench, in `cost_effective` an item's cheaper path is not the decision's mode on 11% to 40% of the held-out items (bars 0.1 to 0.8), and `pick` cuts the summed cost by 20% to 43% at a mean success 0.7 to 7.8 points lower. On the cells where the decision compared costs, 6.1% to 6.8% of items switch, and `size rule` cuts the summed cost of a bar's 32 rows by at most 1.4% (8.1% on its best single row), at no lower mean success.
- AutoBench 2026 agrees: in `cost_effective` an item's cheaper path is not the decision's mode on 21% to 40% of the held-out items (bars 0.7 and 0.8), `pick` cuts the summed cost by 10% to 42% at a mean success about 7 to 11 points lower, and `size rule` cuts the summed cost of a bar's 80 rows by at most 1.1% (19.8% on its best single row), at no lower mean success.
- tau2-bench, where each conversation is priced on its own calls, switches fewer items and saves almost nothing where a rule could fairly take it: in `cost_effective` an item's cheaper path is not the decision's mode on 6% to 21% of the held-out items per domain and 0.1% to 27% pooled (bars 0.3 to 0.8), and `pick` cuts the summed cost by 11% to 16% per domain and 0.05% to 18% pooled, at a mean success from 0.2 points higher to 1.4 points lower; but `size rule` switches 16 of 46,540 items per domain (bar 0.3, none at the higher bars) and 118 of 75,999 pooled (bars 0.3 and 0.4), and cuts a bar's summed cost by at most 0.004% per domain and 0.05% pooled (0.04% and 0.51% on the best rows).
- Recommendation: no spec row for a per-item size rule; a README Limitations line with the numbers of the three datasets (a later backlog row).

## Method

- A cell is one (bar, flavor, point, parent, seed, task) of the 13.9 run that `evidence/llmrouterbench-delegation/results.py` makes: its 4 bars, 50 seeds, the 4 base points of `DESIGN.md` 13.10, both flavors and every parent of the 8 priced pool models. The script reruns it and stops unless its summary is the committed one. With `--dataset autobench` it is the base-grid run of `evidence/delegation/results.py` on the AutoBench 2026 matrix: bars 0.7 and 0.8, the same 50 seeds and 4 points, both flavors, one task `all` of 203 items, and every one of the 20 pool models as a parent; the script reruns it on every row and stops unless its summary is the committed `evidence/delegation/results.json` one. With `--dataset tau2-bench` it is the run of `evidence/tau2-bench-delegation/results.py` on the tau2-bench `--calls` matrix: bars 0.3 to 0.8, the same 50 seeds and 4 points, both flavors, one task per domain over 278 conversations, and each of the 3 agents of the committed registry as a parent, checked against the committed `results.json`; `--dataset tau2-bench-pooled` is the same run on the `--calls --task-by all` matrix, one task `all` of the same 278 conversations, checked against the committed `pooled.json`.
- For each held-out item of a cell the script rebuilds the cost 13.9 charges always inline (the parent at its own input and output tokens on that item, with the point's context, carry turns and calls) and always delegating (brief and result on the parent, the work at the cell's delegate's own tokens on that item). It stops unless the exact sum of each over the held-out half is the cell's cost of that path, and the parent's and the delegate's correct counts are the cell's. On tau2-bench each item is a conversation priced on its own calls (`DESIGN.md` 13.9 v1.74): each path at the calls of the model doing the work on it, the parent's inline and the delegate's delegated, which may differ in number.
- An item's cheaper path is the path with the lower rebuilt cost; on an exact tie it is the cell's mode. An item is switched when its cheaper path is not the cell's mode.
- `pick` takes every switched item's cheaper path on every cell. `size rule` does so only on the cells whose decision came from 13.5 row 3 by cost, reason `delegate_cheaper` or `inline_cheaper`: there both paths clear the bar on the calibration half, so a rule that also sees each item's sizes could choose either. On every other cell the mode comes from 13.4 or from the bounds, so `size rule` keeps it; in `cost_blind` that is every cell.
- An item's success is the record of the path it takes: the parent's on inline, the delegate's on delegate. A strategy's row (bar, flavor, point, parent) averages its cells over seeds as the 13.9 summary does. Since each item takes its cheaper path, `pick` costs no more than either fixed policy, a floor for any rule that chooses between the two paths item by item; its success has no such bound.
- Columns: `cells` the cells a strategy may change; `switched / items` the switched items over the held-out items of those cells, then their `share`; `cost / decision` the strategy's summed row cost over the decision's, over the rows of the flavor and bar (32 on LLMRouterBench, 4 points by 8 parents; 80 on AutoBench, 4 by 20; 12 on tau2-bench, 4 by 3); `success - decision` the mean over those rows of the strategy's success minus the decision's; `better` the rows whose success is at least the decision's at a lower cost.

## Results

### LLMRouterBench (`DESIGN.md` 13.13)

```text
$ python research/per_item_delegation.py --matrix llmrouterbench-matrix.jsonl
Per-item delegation paths on LLMRouterBench: each held-out item's cheaper path by list price at its own sizes, against the per-task decision
matrix: 96,448 rows, 12,056 items, 9 tasks, 8 models; 115,200 cells, 33,696 path pairs rebuilt, each equal to its cell's inline and delegate costs and correct counts
  flavor          bar  strategy    cells  switched / items     share  cost / decision  success - decision  better
  cost_effective  0.1  pick        14400  1,103,037 / 9,647,200  0.1143           0.8043             -0.0069       8
  cost_effective  0.1  size rule    9238   401,335 / 6,592,005  0.0609           0.9864             +0.0005       8
  cost_effective  0.3  pick        14400  2,173,371 / 9,647,200  0.2253           0.5896             -0.0392       2
  cost_effective  0.3  size rule    7150   259,159 / 3,991,675  0.0649           0.9975             +0.0005       9
  cost_effective  0.5  pick        14400  3,108,931 / 9,647,200  0.3223           0.5881             -0.0619       2
  cost_effective  0.5  size rule    5160   192,458 / 2,820,049  0.0682           0.9986             +0.0002      10
  cost_effective  0.8  pick        14400  3,879,686 / 9,647,200  0.4022           0.5710             -0.0780       3
  cost_effective  0.8  size rule     965    72,682 / 1,184,986  0.0613           0.9993             +0.0001       7
  cost_blind      0.1  pick        14400  5,407,434 / 9,647,200  0.5605           0.4542             -0.0827       1
  cost_blind      0.1  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.3  pick        14400  5,407,434 / 9,647,200  0.5605           0.4542             -0.0827       1
  cost_blind      0.3  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.5  pick        14400  5,407,434 / 9,647,200  0.5605           0.4542             -0.0827       1
  cost_blind      0.5  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.8  pick        14400  5,407,434 / 9,647,200  0.5605           0.4542             -0.0827       1
  cost_blind      0.8  size rule       0         0 / 0               -           1.0000             +0.0000       0
  pick, switched share by point, cost_effective: 0: 0.3306, 1: 0.1316, 2: 0.0523, 3: 0.5495
  pick, switched share by point, cost_blind: 0: 0.8165, 1: 0.3575, 2: 0.2043, 3: 0.8638
  largest cost cut at no less success, pick, cost_effective: bar 0.3, point 3, parent openai/gpt-5: decision 0.5254 at 167.0604 USD, pick 0.5393 at 159.4061
  largest cost cut at no less success, size rule, cost_effective: bar 0.1, point 3, parent openai/gpt-5: decision 0.4496 at 88.0736 USD, size rule 0.4846 at 80.9463
  largest cost cut at no less success, pick, cost_blind: bar 0.1, point 3, parent openai/gpt-5: decision 0.5909 at 238.4023 USD, pick 0.5910 at 227.9575
  largest cost cut at no less success, size rule, cost_blind: no row
```

### AutoBench 2026 (`DESIGN.md` 13.10)

```text
$ python research/per_item_delegation.py --dataset autobench --matrix autobench-tokens.jsonl --registry autobench-pool.json
Per-item delegation paths on AutoBench 2026: each held-out item's cheaper path by list price at its own sizes, against the per-task decision
matrix: 4,060 rows, 203 items, 1 task, 20 models; 16,000 cells, 7,280 path pairs rebuilt, each equal to its cell's inline and delegate costs and correct counts
  flavor          bar  strategy    cells  switched / items     share  cost / decision  success - decision  better
  cost_effective  0.7  pick         4000    86,679 / 405,760    0.2136           0.8982             -0.0651      11
  cost_effective  0.7  size rule    1024     9,053 / 104,060    0.0870           0.9886             +0.0014       8
  cost_effective  0.8  pick         4000   160,808 / 405,760    0.3963           0.5777             -0.1055      11
  cost_effective  0.8  size rule     204     1,362 / 20,496     0.0665           0.9989             +0.0002       5
  cost_blind      0.7  pick         4000   191,621 / 405,760    0.4723           0.4448             -0.1145      12
  cost_blind      0.7  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.8  pick         4000   191,621 / 405,760    0.4723           0.4448             -0.1145      12
  cost_blind      0.8  size rule       0         0 / 0               -           1.0000             +0.0000       0
  pick, switched share by point, cost_effective: 0: 0.3384, 1: 0.1223, 2: 0.0428, 3: 0.7164
  pick, switched share by point, cost_blind: 0: 0.5952, 1: 0.2897, 2: 0.1542, 3: 0.8500
  largest cost cut at no less success, pick, cost_effective: bar 0.8, point 3, parent openai/gpt-5.6-luna: decision 0.8554 at 1.9081 USD, pick 0.8720 at 0.3567
  largest cost cut at no less success, size rule, cost_effective: bar 0.7, point 3, parent openai/gpt-5.6-sol: decision 0.8694 at 1.2297 USD, size rule 0.9201 at 0.9859
  largest cost cut at no less success, pick, cost_blind: bar 0.7, point 2, parent anthropic/claude-sonnet-5: decision 0.8572 at 7.9597 USD, pick 0.8572 at 3.0783
  largest cost cut at no less success, size rule, cost_blind: no row
```

### tau2-bench per domain (`DESIGN.md` 13.12)

```text
$ python research/per_item_delegation.py --dataset tau2-bench --matrix tau2-calls.jsonl
Per-item delegation paths on tau2-bench per domain: each held-out item's cheaper path by list price at its own sizes, against the per-task decision
matrix: 834 rows, 278 items, 3 tasks, 3 models; 21,600 cells, 3,192 path pairs rebuilt, each equal to its cell's inline and delegate costs and correct counts
  flavor          bar  strategy    cells  switched / items     share  cost / decision  success - decision  better
  cost_effective  0.3  pick         1800     4,702 / 82,908     0.0567           0.8947             +0.0012       9
  cost_effective  0.3  size rule     892        16 / 46,540     0.0003           1.0000             +0.0001       2
  cost_effective  0.4  pick         1800     7,351 / 82,908     0.0887           0.8657             +0.0017       8
  cost_effective  0.4  size rule     584         0 / 32,426     0.0000           1.0000             +0.0000       0
  cost_effective  0.5  pick         1800     8,442 / 82,908     0.1018           0.8658             +0.0013       8
  cost_effective  0.5  size rule     514         0 / 29,292     0.0000           1.0000             +0.0000       0
  cost_effective  0.6  pick         1800    14,810 / 82,908     0.1786           0.8542             -0.0047       4
  cost_effective  0.6  size rule     271         0 / 15,511     0.0000           1.0000             +0.0000       0
  cost_effective  0.7  pick         1800    17,353 / 82,908     0.2093           0.8452             -0.0107       4
  cost_effective  0.7  size rule      40         0 / 2,333      0.0000           1.0000             +0.0000       0
  cost_effective  0.8  pick         1800    17,453 / 82,908     0.2105           0.8447             -0.0110       4
  cost_effective  0.8  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.3  pick         1800    42,998 / 82,908     0.5186           0.4100             -0.0111       6
  cost_blind      0.3  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.4  pick         1800    42,998 / 82,908     0.5186           0.4100             -0.0111       6
  cost_blind      0.4  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.5  pick         1800    42,998 / 82,908     0.5186           0.4100             -0.0111       6
  cost_blind      0.5  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.6  pick         1800    42,998 / 82,908     0.5186           0.4100             -0.0111       6
  cost_blind      0.6  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.7  pick         1800    42,998 / 82,908     0.5186           0.4100             -0.0111       6
  cost_blind      0.7  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.8  pick         1800    42,998 / 82,908     0.5186           0.4100             -0.0111       6
  cost_blind      0.8  size rule       0         0 / 0               -           1.0000             +0.0000       0
  pick, switched share by point, cost_effective: 0: 0.2483, 1: 0.0490, 2: 0.0027, 3: 0.2637
  pick, switched share by point, cost_blind: 0: 0.7137, 1: 0.4686, 2: 0.1529, 3: 0.7394
  largest cost cut at no less success, pick, cost_effective: bar 0.5, point 3, parent openai/gpt-4.1-mini-2025-04-14: decision 0.5499 at 27.4256 USD, pick 0.5515 at 12.1733
  largest cost cut at no less success, size rule, cost_effective: bar 0.3, point 3, parent openai/gpt-4.1-2025-04-14: decision 0.5496 at 19.8837 USD, size rule 0.5502 at 19.8764
  largest cost cut at no less success, pick, cost_blind: bar 0.3, point 1, parent anthropic/claude-3-7-sonnet-20250219: decision 0.5910 at 327.4998 USD, pick 0.5910 at 49.7725
  largest cost cut at no less success, size rule, cost_blind: no row
```

### tau2-bench pooled (`DESIGN.md` 13.12)

```text
$ python research/per_item_delegation.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl
Per-item delegation paths on tau2-bench pooled: each held-out item's cheaper path by list price at its own sizes, against the per-task decision
matrix: 834 rows, 278 items, 1 task, 3 models; 7,200 cells, 1,224 path pairs rebuilt, each equal to its cell's inline and delegate costs and correct counts
  flavor          bar  strategy    cells  switched / items     share  cost / decision  success - decision  better
  cost_effective  0.3  pick          600       118 / 82,908     0.0014           0.9995             +0.0008       2
  cost_effective  0.3  size rule     550       118 / 75,999     0.0016           0.9995             +0.0008       2
  cost_effective  0.4  pick          600       118 / 82,908     0.0014           0.9995             +0.0008       2
  cost_effective  0.4  size rule     550       118 / 75,999     0.0016           0.9995             +0.0008       2
  cost_effective  0.5  pick          600    21,173 / 82,908     0.2554           0.8268             -0.0117       4
  cost_effective  0.5  size rule     132        10 / 18,262     0.0005           0.9999             +0.0000       4
  cost_effective  0.6  pick          600    22,422 / 82,908     0.2704           0.8222             -0.0139       4
  cost_effective  0.6  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_effective  0.7  pick          600    22,422 / 82,908     0.2704           0.8222             -0.0139       4
  cost_effective  0.7  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_effective  0.8  pick          600    22,422 / 82,908     0.2704           0.8222             -0.0139       4
  cost_effective  0.8  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.3  pick          600    45,226 / 82,908     0.5455           0.4621             -0.0138       6
  cost_blind      0.3  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.4  pick          600    45,226 / 82,908     0.5455           0.4621             -0.0138       6
  cost_blind      0.4  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.5  pick          600    45,226 / 82,908     0.5455           0.4621             -0.0138       6
  cost_blind      0.5  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.6  pick          600    45,226 / 82,908     0.5455           0.4621             -0.0138       6
  cost_blind      0.6  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.7  pick          600    45,226 / 82,908     0.5455           0.4621             -0.0138       6
  cost_blind      0.7  size rule       0         0 / 0               -           1.0000             +0.0000       0
  cost_blind      0.8  pick          600    45,226 / 82,908     0.5455           0.4621             -0.0138       6
  cost_blind      0.8  size rule       0         0 / 0               -           1.0000             +0.0000       0
  pick, switched share by point, cost_effective: 0: 0.3043, 1: 0.0775, 2: 0.0042, 3: 0.3271
  pick, switched share by point, cost_blind: 0: 0.8053, 1: 0.4689, 2: 0.0670, 3: 0.8408
  largest cost cut at no less success, pick, cost_effective: bar 0.6, point 2, parent openai/gpt-4.1-mini-2025-04-14: decision 0.5923 at 57.9438 USD, pick 0.5956 at 55.2195
  largest cost cut at no less success, size rule, cost_effective: bar 0.3, point 3, parent openai/gpt-4.1-2025-04-14: decision 0.5485 at 10.1082 USD, size rule 0.5535 at 10.0566
  largest cost cut at no less success, pick, cost_blind: bar 0.3, point 1, parent anthropic/claude-3-7-sonnet-20250219: decision 0.5990 at 429.7528 USD, pick 0.5990 at 62.4833
  largest cost cut at no less success, size rule, cost_blind: no row
```

## Reading it

- The cheaper path differs often. In `cost_effective` `pick` switches 0.1143 of the held-out items at bar 0.1 and 0.4022 at bar 0.8, and 0.5495 at point 3, where inline work folds into the parent's next call and so pays no separate call over C. In `cost_blind` it switches 0.5605, the same at every bar.
- Taking it everywhere trades success for cost. `pick` costs 0.8043 to 0.5710 of the decision in `cost_effective` and 0.4542 in `cost_blind`, at a mean success 0.0069 to 0.0780 and 0.0827 below it; it is better on at most 8 of a flavor and bar's 32 rows. That success is the record of the path each item takes; the block gives only its net change, not how the switched items fare on each path.
- Where a rule could fairly take it, it saves little. `size rule` changes only the row 3 cells, 9238 of the 14400 at bar 0.1 and 965 at bar 0.8; it switches 0.0609 to 0.0682 of their items, costs 0.9864 to 0.9993 of the decision, and its mean success is +0.0001 to +0.0005 against the decision's, better on 7 to 10 of the 32 rows.
- Its largest cut at no less success is at bar 0.1, point 3, parent `openai/gpt-5`: 80.9463 USD against 88.0736 at success 0.4846 against 0.4496.
- AutoBench 2026 shows the same pattern. In `cost_effective` `pick` switches 0.2136 of the held-out items at bar 0.7 and 0.3963 at bar 0.8, and 0.7164 at point 3; in `cost_blind` 0.4723 at both bars. It costs 0.8982 and 0.5777 of the decision in `cost_effective` and 0.4448 in `cost_blind`, at a mean success 0.0651, 0.1055 and 0.1145 below it, and is better on 11 or 12 of a flavor and bar's 80 rows.
- There too a rule that takes it only where the decision compared costs saves little. `size rule` changes 1024 of the 4000 cells at bar 0.7 and 204 at bar 0.8, switches 0.0870 and 0.0665 of their items, and costs 0.9886 and 0.9989 of the decision at a mean success +0.0014 and +0.0002, better on 8 and 5 of the 80 rows. Its largest cut at no less success is at bar 0.7, point 3, parent `openai/gpt-5.6-sol`: 0.9859 USD against 1.2297 at success 0.9201 against 0.8694, 19.8% of that row's cost.
- On tau2-bench the cheaper path differs less often in `cost_effective`. Per domain `pick` switches 0.0567 of the held-out items at bar 0.3 and 0.2105 at bar 0.8, and pooled 0.0014 at bars 0.3 and 0.4 and 0.2704 from bar 0.6; in `cost_blind` 0.5186 and 0.5455 at every bar. It costs 0.8947 to 0.8447 of the decision per domain and 0.9995 to 0.8222 pooled, at a mean success -0.0110 to +0.0017 and -0.0139 to +0.0008 against it, and is better on 4 to 9 of a flavor and bar's 12 rows per domain and 2 to 4 pooled.
- Most of what `pick` switches there is on cells whose mode did not come from cost: per domain at bar 0.3 it switches 4,702 items, 16 of them on the 892 cells where the decision compared costs, and 13.5 row 7 (`none_clear`) decides 6,941 of the 10,800 per-domain `cost_effective` cells (`DESIGN.md` 13.12).
- Where a rule could fairly take it, it saves almost nothing on tau2-bench. `size rule` switches 16 of the 46,540 held-out items of the 892 compared cells at bar 0.3 per domain and none at bars 0.4 to 0.7 (bar 0.8 has no such cell), and pooled 118 of 75,999 on 550 cells at bars 0.3 and 0.4 and 10 of 18,262 on 132 at bar 0.5. It costs 1.0000 of the decision at every bar per domain and no less than 0.9995 pooled. Its largest cut at no less success is at bar 0.3, point 3, parent `openai/gpt-4.1-2025-04-14` in both runs: 19.8764 USD against 19.8837 per domain and 10.0566 against 10.1082 pooled, 0.04% and 0.51% of that row's cost.

## Recommendation

- No spec row for a per-item size rule. On all three datasets the decision's per-task choice is within 1.4% (LLMRouterBench), 1.1% (AutoBench 2026) and 0.05% (tau2-bench pooled; 0.004% per domain) of a bar's summed cost under a rule that sees each item's sizes before the call, at no lower mean success. Single rows gain more on the two single-call datasets, 8.1% and 19.8% on the best ones, and at most 0.51% on tau2-bench (the `size rule` bullets of Reading it).
- Pricing each conversation on its own calls does not make the cheaper path vary more where the decision compared costs: on tau2-bench those cells switch 0.03% of their items at most per domain and 0.16% pooled, against 6.1% to 6.8% on LLMRouterBench and 6.7% to 8.7% on AutoBench 2026.
- A README Limitations line (a later backlog row): the cheaper path differs from item to item on up to 40% of the held-out items in `cost_effective`, but on all three datasets a rule that takes it where the decision compared costs saves at most 1.4% of a bar's summed cost, so the gain from choosing per item that the bullet on where delegation pays names is small on this evidence.

## Regenerate

```bash
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python research/per_item_delegation.py --matrix llmrouterbench-matrix.jsonl
python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens --registry autobench-pool.json
python research/per_item_delegation.py --dataset autobench --matrix autobench-tokens.jsonl --registry autobench-pool.json
python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls
python research/per_item_delegation.py --dataset tau2-bench --matrix tau2-calls.jsonl
python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all
python research/per_item_delegation.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl
```

The LLMRouterBench converter downloads the pinned 1.28 GB file once into its cache and checks its sha256 (`DESIGN.md` 12.18); the script then takes about 40 seconds, most of it the 13.9 run. The AutoBench converter does the same for its pinned files (`DESIGN.md` 12.9); the script takes about 6 seconds on that matrix. The tau2-bench converter downloads its 12 pinned run files once and checks each sha256 (`DESIGN.md` 12.14); the script takes about a second on each of its two matrices.
