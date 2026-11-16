# Whether the re-read share and the brief's output move a committed delegation decision

v1.404 and v1.405 give `decide_delegation` the two inputs that [the ledger runs' note](ledger-cost-model.md) found missing: `output_reread_share` (sigma), the share of each work call's output that later calls re-read, and `brief_output_tokens` (W), what the call that writes the brief writes. Every committed delegation result keeps sigma at 1.0 and W at the brief's size B (13.1), so no note said whether either input changes a decision that [the AutoBench delegation results](../evidence/delegation/RESULTS.md) report. This note reruns both AutoBench grids, re-decides every cell at sigma 0, sigma 0.5 and W = 2 B, and scores the committed pick and the new one at that setting's costs.

## Facts

- Neither input moves the AutoBench delegation results: each changes a few `cost_effective` decisions, where the two paths cost about the same, changes no `cost_blind` decision, and leaves the cost over all the cells of a file, flavor and bar within a few thousandths of the committed picks' cost at the same setting
- Data: the AutoBench 2026 matrix and pool that evidence/delegation/results.py runs, its base grid (16,000 cells: 2 bars, 2 flavors, 4 points, 20 parents, 50 seeds) and its variant grid (12,000 cells, 3 points); every cell's decision and held-out sum is reproduced at sigma 1.0 and W = B before either input is varied
- Base grid, `cost_effective`, bar 0.7: sigma 0 changes 19 of 4,000 cells (0.5%), sigma 0.5 changes 5 (0.1%) and W = 2 B changes 18 (0.5%), every one to inline; the new picks score -0.1348, -0.1132 and -0.1269 in held-out success against the committed picks, at 1.049, 1.188 and 1.089 times their cost. At bar 0.8 each setting changes 1 cell, to inline, at +0.0000 in success and 0.829 to 0.943 times the cost. Every changed base-grid cell is at point 3, where inline work is folded into the parent's next call
- Variant grid: only at bar 0.8 in `cost_effective`, where sigma 0 and sigma 0.5 each change 20 of 3,000 cells (0.7%), all at variant point 2, the longest run, and none to inline: the work goes to another delegate, for +0.0500 in held-out success at 1.092 and 1.128 times the cost; W = 2 B changes none
- Over all the cells of a file, flavor and bar the cost ratio is 1.000 to 1.003

## Method

- The matrix, registry, bars, seeds and points are the ones evidence/delegation/results.py runs (13.10). `evaluate_delegation` (13.9) runs each grid, and its config, tasks and summary must be the committed file's, or the script exits 2
- Each cell (bar, flavor, point, parent, seed) is re-decided by `decide_delegation` with the run's own calibration half and router, the 13.9 ones, so sigma and W are the only inputs that differ. At sigma 1.0 and W = B the re-decided mode and model must be the cell's, and the held-out correct count and cost the script computes for them must be the cell's decision's, or the script exits 2
- What sigma scales, from 13.2 (v1.404): each re-read of a work call's output S_out and nothing else. Each read `w_out * S_out` is `w_out * sigma * S_out` and each read `K * (S_in + S_out)` is `K * (S_in + sigma * S_out)`; the written outputs, the brief B, the result R and every read of the context C keep their sizes. W is the decision turn's output on the delegated path, `P.cost(0, W)` in 13.2 (v1.410), and every read of the brief stays B
- So at one work call, the base grid, w_out is 0 and sigma lowers only the inline path's cost, through the parent's calls after the work, which re-read its output; the delegated path's cost and the delegate's pick do not move. At more work calls, variant points 0 and 2, sigma also lowers each candidate delegate's cost in the delegate's own pick, so it can move the model the work goes to. W raises only the delegated path's cost
- A cell changes when its mode or its model changes. Both picks of a changed cell are scored on the cell's held-out half at that setting's 13.2 list-price costs, the bill a caller would see whose model really re-reads that share or writes that much: the committed pick against the one the decision makes once told
- Columns: `changed / cells` and `share` count the changed cells, `to inline` those whose new mode is inline; `success gap` is the new picks' held-out correct count minus the committed picks', over the changed cells' held-out items; `cost ratio` is the new picks' held-out cost over the committed picks' on the changed cells, and `all cost ratio` the same over every cell

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
```

## Reading it

- The changes sit where the two paths cost about the same. At point 3 the folded inline work adds no read of the context, so the 13.5 cost comparison is close and a lower inline cost (sigma) or a higher delegated one (W) tips a few cells to inline; where inline work is a call of its own, points 0 to 2, its read of the context makes inline far dearer and nothing moves. Most of the changed base-grid cells are one parent's, whose inline cost sits closest to its delegate's
- The new base-grid picks are not better on the held-out half. At bar 0.7 they lose success, since the parent is right less often than its delegate, which `cost_effective` allows for a path that clears the bar; and they cost more, since a decision made at calibration-mean sizes next to a tie can land on either side of it on the held-out items
- The variant cells are one seed's 20 parents at variant point 2 and bar 0.8, where no model clears the bar (13.5, reason `none_clear`) and two models tie on their calibration bound, so the cost breaks the tie, and at many work calls sigma moves that cost. The new delegate is right more often there, at a higher cost
- `cost_blind` never compares the paths' costs (13.5), and no `cost_blind` cell moves on either grid

## Recommendation

- Keep every committed delegation result at sigma 1.0 and W = B, and README Limitations' sentences on the two inputs as they are: on AutoBench neither input changes more than 0.7% of the cells of a file, flavor and bar, and the cost over all of them moves by a factor of at most 1.003
- Run the same check on the other delegation datasets before saying it holds there: LLMRouterBench and the LLM Routing Response Bank, whose rows are single calls priced as here, and tau2-bench, whose rows carry per-call sizes that this script does not price (rows R38b to R38d)

## Limits

- One dataset, AutoBench 2026, whose grids fix the brief's size and the work-call counts, so the note measures the two inputs only at those points
- Three settings. A model's own sigma and W are its caller's to measure; the ledger runs give one pair
- The held-out cost is 13.2's list-price approximation at each setting, not a measured bill
- The script re-decides with the 13.9 helpers `_calibrate` and `_router`, which the package does not export; the check at sigma 1.0 and W = B is what keeps the two in step

## Regenerate

```bash
python -m pip install -e .
python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens --registry autobench-pool.json
python research/reread_sensitivity.py --matrix autobench-tokens.jsonl --registry autobench-pool.json
```
