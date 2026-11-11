# Do held-out items' cheaper delegation paths differ from the per-task decision?

## Facts

- Question: on the LLMRouterBench delegation evidence (`DESIGN.md` 13.13), how often is a held-out item's cheaper path, inline or delegated, by list price at that item's own sizes, not the path the per-task `DESIGN.md` 13.5 decision took, and what would taking it give?
- Rule, stated before any number: an item's cheaper path is the one whose `DESIGN.md` 13.9 list-price cost at its recorded sizes is lower, the decision's mode on an exact tie; `pick` takes it on every cell, `size rule` only on the cells where the decision compared the two paths' costs (see Method).
- Reads the converter's matrix of the pinned LLMRouterBench file, the committed `evidence/llmrouterbench-delegation/registry.json`, and its `results.json`, whose summary the rerun must equal. No library code, harness or results file changes.
- Short answer: often, but where a rule could fairly take it, it saves little. In `cost_effective` an item's cheaper path is not the decision's mode on 11% to 40% of the held-out items (bars 0.1 to 0.8), and `pick` cuts the summed cost by 20% to 43% at a mean success 0.7 to 7.8 points lower. On the cells where the decision compared costs, 6.1% to 6.8% of items switch, and `size rule` cuts the summed cost by at most 1.4%, at no lower mean success.
- Recommendation: no spec row for a per-item size rule now; a README Limitations line, a later backlog row, after the AutoBench and tau2-bench matrices are measured the same way (a new row).

## Method

- A cell is one (bar, flavor, point, parent, seed, task) of the 13.9 run that `evidence/llmrouterbench-delegation/results.py` makes: its 4 bars, 50 seeds, the 4 base points of `DESIGN.md` 13.10, both flavors and every parent of the 8 priced pool models. The script reruns it and stops unless its summary is the committed one.
- For each held-out item of a cell the script rebuilds the cost 13.9 charges always inline (the parent at its own input and output tokens on that item, with the point's context, carry turns and calls) and always delegating (brief and result on the parent, the work at the cell's delegate's own tokens on that item). It stops unless the exact sum of each over the held-out half is the cell's cost of that path, and the parent's and the delegate's correct counts are the cell's.
- An item's cheaper path is the path with the lower rebuilt cost; on an exact tie it is the cell's mode. An item is switched when its cheaper path is not the cell's mode.
- `pick` takes every switched item's cheaper path on every cell. `size rule` does so only on the cells whose decision came from 13.5 row 3 by cost, reason `delegate_cheaper` or `inline_cheaper`: there both paths clear the bar on the calibration half, so a rule that also sees each item's sizes could choose either. On every other cell the mode comes from 13.4 or from the bounds, so `size rule` keeps it; in `cost_blind` that is every cell.
- An item's success is the record of the path it takes: the parent's on inline, the delegate's on delegate. A strategy's row (bar, flavor, point, parent) averages its cells over seeds as the 13.9 summary does. Since each item takes its cheaper path, `pick` costs no more than either fixed policy, a floor for any rule that chooses between the two paths item by item; its success has no such bound.
- Columns: `cells` the cells a strategy may change; `switched / items` the switched items over the held-out items of those cells, then their `share`; `cost / decision` the strategy's summed row cost over the decision's, over the 32 rows of the flavor and bar; `success - decision` the mean over those rows of the strategy's success minus the decision's; `better` the rows whose success is at least the decision's at a lower cost.

## Results

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

## Reading it

- The cheaper path differs often. In `cost_effective` `pick` switches 0.1143 of the held-out items at bar 0.1 and 0.4022 at bar 0.8, and 0.5495 at point 3, where inline work folds into the parent's next call and so pays no separate call over C. In `cost_blind` it switches 0.5605, the same at every bar.
- Taking it everywhere trades success for cost. `pick` costs 0.8043 to 0.5710 of the decision in `cost_effective` and 0.4542 in `cost_blind`, at a mean success 0.0069 to 0.0780 and 0.0827 below it; it is better on at most 8 of a flavor and bar's 32 rows. That success is the record of the path each item takes, so the cheaper path is often the one that fails more.
- Where a rule could fairly take it, it saves little. `size rule` changes only the row 3 cells, 9238 of the 14400 at bar 0.1 and 965 at bar 0.8; it switches 0.0609 to 0.0682 of their items, costs 0.9864 to 0.9993 of the decision, and its mean success is +0.0001 to +0.0005 against the decision's, better on 7 to 10 of the 32 rows.
- Its largest cut at no less success is at bar 0.1, point 3, parent `openai/gpt-5`: 80.9463 USD against 88.0736 at success 0.4846 against 0.4496.

## Recommendation

- No spec row for a per-item size rule now. On this matrix the decision's per-task choice is within 1.4% of the cost of a rule that sees each item's sizes before the call, at the same success, so the gain that the README Limitations bullet on where delegation pays names exists here but is small.
- Measure the AutoBench (13.10) and tau2-bench (13.12) matrices the same way first (a new backlog row), since tau2-bench prices each conversation on its own calls, where sizes may vary more from item to item; then a README Limitations line with the numbers of all three.

## Regenerate

```bash
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python research/per_item_delegation.py --matrix llmrouterbench-matrix.jsonl
```

The converter downloads the pinned 1.28 GB file once into its cache and checks its sha256 (`DESIGN.md` 12.18). The script takes about 40 seconds, most of it the 13.9 run.
