# Where the per-task delegation decision pays on the committed evidence

## Facts

- Question: does the per-task `DESIGN.md` 13.5 decision, inline or delegate, beat a fixed policy, always inline or always delegate, on the committed delegation evidence?
- Reads only the summary rows of the four committed delegation files: `evidence/delegation/results.json` (AutoBench), `evidence/tau2-bench-delegation/results.json` and `evidence/tau2-bench-delegation/pooled.json` (tau2-bench per domain and pooled) and `evidence/llmrouterbench-delegation/results.json` (LLMRouterBench). No library code, harness or results file changes.
- Short answer: rarely, and never on both success and cost. In `cost_effective` the decision equals always delegating on 403 of the 432 rows, every row at the three points where inline work is a call of its own among them. In `cost_blind` a fixed policy has a higher held-out success at no more cost on 106 of the 432 rows. On no row of either flavor is the decision better than both fixed policies.
- Recommendation: a README Limitations line, and no spec row.

## Method

- A row is one (bar, flavor, point, parent) of a file's `summary`, which holds three strategies for it (`DESIGN.md` 13.9): `decision`, `inline` (the parent works inline on every item, even where 13.4 blocks it) and `delegate` (every item delegated to the route's primary, the model the decision delegates to). Each has a held-out `success` and a list-price `cost_usd`, both means over the file's seeds.
- The rule, stated before the counts it gives. The decision's (success, cost) pair is compared with each fixed policy's, exactly as floats, and the row takes the first class that applies:
  - `= delegate`: equal to always delegate's pair in both; `= inline` likewise. The per-task choice changed nothing there. The script checks that these are exactly the rows whose `delegate_rate` is 1.0 (`= delegate`) or 0.0 (`= inline`), so the decision took that one path on every (task, seed) cell of the row.
  - `better`: a success at least both fixed policies' and a cost at most both.
  - `beaten on success`: a fixed policy has a higher success at no more cost. `beaten on cost`: one has the same success at a lower cost.
  - `trade-off`: otherwise, so a fixed policy that costs less also succeeds less, and one that succeeds more also costs more.
- A changed row is a row of the last four classes. Its gain is the decision's success minus the higher of the two fixed policies' successes; `top success` counts the changed rows with a gain above 0, and each file and flavor names its changed row with the largest gain. Against always delegate alone, the script counts the changed rows that cost less than it and, of those, the ones at no less success.
- Cost counts in both flavors, since `cost_usd` is the same list-price cost of each path whatever the flavor (13.9). `cost_blind` chooses without it, so there `beaten on cost` is the flavor working as defined, and `beaten on success` is the class that counts against it.

## Results

```text
$ python research/where_delegation_pays.py
Where the per-task delegation decision pays: each summary row (bar, flavor, point, parent) of the four committed delegation files, the decision against always inline and always delegate
AutoBench (`evidence/delegation/results.json`): 320 rows, 1 task, bars 0.7 0.8, 4 points, 20 parents
  flavor          bar   rows  = delegate  = inline  better  beaten on success  beaten on cost  trade-off  top success
  cost_effective  0.7     80          76         1       0                  1               0          2            0
  cost_effective  0.8     80          76         0       0                  1               0          3            0
  cost_blind      0.7     80          60         0       0                  3              10          7            0
  cost_blind      0.8     80          60         0       0                  3              10          7            0
  changed rows by point, cost_effective: 0: 0, 1: 0, 2: 0, 3: 7
  against always delegate, cost_effective: 7 changed rows, 6 cheaper (3 of them at no less success), 1 not cheaper
  largest gain, cost_effective: bar 0.8, point 3, parent qwen/qwen3.8-max: decision 0.8554 at 2.5125 USD, inline 0.8528 at 1.5549, delegate 0.8554 at 2.5358, gain +0.0000
  changed rows by point, cost_blind: 0: 10, 1: 10, 2: 10, 3: 10
  against always delegate, cost_blind: 40 changed rows, 10 cheaper (10 of them at no less success), 30 not cheaper
  largest gain, cost_blind: bar 0.7, point 0, parent moonshotai/kimi-k2.6: decision 0.8572 at 2.4095 USD, inline 0.7760 at 2.1614, delegate 0.8572 at 2.3908, gain +0.0000
tau2-bench (`evidence/tau2-bench-delegation/results.json`): 144 rows, 3 tasks, bars 0.3 0.4 0.5 0.6 0.7 0.8, 4 points, 3 parents
  flavor          bar   rows  = delegate  = inline  better  beaten on success  beaten on cost  trade-off  top success
  cost_effective  0.3     12          12         0       0                  0               0          0            0
  cost_effective  0.4     12          12         0       0                  0               0          0            0
  cost_effective  0.5     12          12         0       0                  0               0          0            0
  cost_effective  0.6     12          12         0       0                  0               0          0            0
  cost_effective  0.7     12          12         0       0                  0               0          0            0
  cost_effective  0.8     12          12         0       0                  0               0          0            0
  cost_blind      0.3     12           1         0       0                  8               3          0            0
  cost_blind      0.4     12           1         0       0                  8               3          0            0
  cost_blind      0.5     12           1         0       0                  8               3          0            0
  cost_blind      0.6     12           1         0       0                  8               3          0            0
  cost_blind      0.7     12           1         0       0                  8               3          0            0
  cost_blind      0.8     12           1         0       0                  8               3          0            0
  changed rows by point, cost_effective: 0: 0, 1: 0, 2: 0, 3: 0
  against always delegate, cost_effective: no changed row
  largest gain, cost_effective: no changed row
  changed rows by point, cost_blind: 0: 18, 1: 18, 2: 12, 3: 18
  against always delegate, cost_blind: 66 changed rows, 0 cheaper (0 of them at no less success), 66 not cheaper
  largest gain, cost_blind: bar 0.3, point 0, parent openai/gpt-4.1-mini-2025-04-14: decision 0.5898 at 49.1346 USD, inline 0.5485 at 17.5937, delegate 0.5910 at 48.1281, gain -0.0013
tau2-bench pooled (`evidence/tau2-bench-delegation/pooled.json`): 144 rows, 1 task, bars 0.3 0.4 0.5 0.6 0.7 0.8, 4 points, 3 parents
  flavor          bar   rows  = delegate  = inline  better  beaten on success  beaten on cost  trade-off  top success
  cost_effective  0.3     12          12         0       0                  0               0          0            0
  cost_effective  0.4     12          12         0       0                  0               0          0            0
  cost_effective  0.5     12          12         0       0                  0               0          0            0
  cost_effective  0.6     12          12         0       0                  0               0          0            0
  cost_effective  0.7     12          12         0       0                  0               0          0            0
  cost_effective  0.8     12          12         0       0                  0               0          0            0
  cost_blind      0.3     12           1         0       0                  6               3          2            0
  cost_blind      0.4     12           1         0       0                  6               3          2            0
  cost_blind      0.5     12           1         0       0                  6               3          2            0
  cost_blind      0.6     12           1         0       0                  6               3          2            0
  cost_blind      0.7     12           1         0       0                  6               3          2            0
  cost_blind      0.8     12           1         0       0                  6               3          2            0
  changed rows by point, cost_effective: 0: 0, 1: 0, 2: 0, 3: 0
  against always delegate, cost_effective: no changed row
  largest gain, cost_effective: no changed row
  changed rows by point, cost_blind: 0: 18, 1: 18, 2: 12, 3: 18
  against always delegate, cost_blind: 66 changed rows, 12 cheaper (0 of them at no less success), 54 not cheaper
  largest gain, cost_blind: bar 0.3, point 0, parent openai/gpt-4.1-2025-04-14: decision 0.5972 at 64.0484 USD, inline 0.5622 at 59.6628, delegate 0.5990 at 61.7233, gain -0.0019
LLMRouterBench (`evidence/llmrouterbench-delegation/results.json`): 256 rows, 9 tasks, bars 0.1 0.3 0.5 0.8, 4 points, 8 parents
  flavor          bar   rows  = delegate  = inline  better  beaten on success  beaten on cost  trade-off  top success
  cost_effective  0.1     32          26         0       0                  0               0          6            1
  cost_effective  0.3     32          27         0       0                  0               0          5            1
  cost_effective  0.5     32          26         0       0                  0               0          6            1
  cost_effective  0.8     32          28         0       0                  0               0          4            0
  cost_blind      0.1     32          19         0       0                  4               3          6            0
  cost_blind      0.3     32          19         0       0                  4               3          6            0
  cost_blind      0.5     32          19         0       0                  4               3          6            0
  cost_blind      0.8     32          19         0       0                  4               3          6            0
  changed rows by point, cost_effective: 0: 0, 1: 0, 2: 0, 3: 21
  against always delegate, cost_effective: 21 changed rows, 21 cheaper (6 of them at no less success), 0 not cheaper
  largest gain, cost_effective: bar 0.1, point 3, parent openai/gpt-5-chat: decision 0.4846 at 66.5694 USD, inline 0.4710 at 32.9471, delegate 0.4496 at 88.0736, gain +0.0135
  changed rows by point, cost_blind: 0: 16, 1: 16, 2: 4, 3: 16
  against always delegate, cost_blind: 52 changed rows, 12 cheaper (4 of them at no less success), 40 not cheaper
  largest gain, cost_blind: bar 0.1, point 0, parent deepseek/deepseek-r1-0528: decision 0.5906 at 226.2996 USD, inline 0.4728 at 146.2874, delegate 0.5906 at 225.4591, gain +0.0000
All four files
  flavor          bar   rows  = delegate  = inline  better  beaten on success  beaten on cost  trade-off  top success
  cost_effective  all    432         403         1       0                  2               0         26            3
  cost_blind      all    432         208         0       0                106              68         50            0
```

## Reading it

- `cost_effective`: the decision equals always delegating on 403 of 432 rows and always inline on 1, and is better than both fixed policies on none. Every row at points 0, 1 and 2 is `= delegate`, so there the decision delegates on every cell for every parent and bar; every changed row and the one `= inline` row are at point 3, the one point where inline work folds into the parent's next call. With a separate inline call the parent re-reads its whole context for the work, which a delegate does not (13.2), so at the other three points the inline path carries a cost the delegate path does not. On tau2-bench, per domain and pooled, the decision changes nothing at any point.
- Where it changes something in `cost_effective`, it sits between the two fixed policies. On LLMRouterBench all 21 changed rows cost less than always delegate, 6 of them at no less success, and 3 of the 26 trade-offs over the four files have a higher success than both. The largest gain is at bar 0.1, point 3, with `openai/gpt-5-chat` as the parent: 0.4846 at 66.5694 USD, against always delegate's 0.4496 at 88.0736 and always inline's 0.4710 at 32.9471, so +0.0135 over the better fixed policy at a cost between the two. On AutoBench 2 changed rows are beaten on success and the largest gain is +0.0000.
- `cost_blind`: the decision equals always delegating on 208 of 432 rows and is beaten on success on 106, a fixed policy there having more held-out success at no more cost, and no changed row has a higher success than both. The flavor chooses by calibration bounds alone (13.5 row 4), and a held-out half can rank the parent and its delegate the other way, as routing on a calibration half can rank models ([where-routing-pays.md](where-routing-pays.md)). The 68 rows beaten on cost alone have a fixed policy's success at a higher cost, which `cost_blind` does not weigh.
- So on this evidence the per-task decision is close to a fixed policy: in `cost_effective` it is always delegating except where the work folds into the parent's next call, and there it trades success against cost without beating both fixed policies.

## Recommendation

- A README Limitations line, next to the bullet on the datasets the delegation evidence reads: on the committed delegation files the `cost_effective` decision equals always delegating on 403 of 432 rows, every row where inline work is a call of its own among them, and is better than both fixed policies on none, while in `cost_blind` a fixed policy has more held-out success at no more cost on 106 of 432. So the evidence shows how the decision prices the two paths at the stated sizes, not a gain from choosing per task; such a gain needs work whose cheaper path differs from item to item, as where it folds into the parent's next call.
- No spec row: each class above follows from 13.2 and 13.5 as written, and a summary row cannot say which 13.5 row chose a path on which cell, so these files point to no rule to change. The cells would say it, and the results files do not keep them (13.10).

## Limits

- Summary rows only: each is a mean over seeds and, on the tau2-bench per-domain file and on LLMRouterBench, pooled over tasks, so a decision that gains on one task and loses on another nets out in its row. The cells that would show it are not in the files.
- The 13.9 assumptions hold here too: a brief that carries everything the item needs, a parent whose answers its context does not change, and list prices.
- Always delegate still routes: each cell delegates to that cell's route primary, so it is not one fixed model, and this note compares the inline-or-delegate choice alone.
- The rows of one file are not independent: a file's bars of one flavor often repeat the same rows, as its `cost_blind` lines show, so a count is of rows, not of separate trials.

## Regenerate

```text
python research/where_delegation_pays.py
```

The script reads only the four committed files, so its output is the Results block above on any checkout; `tests/test_research_where_delegation_pays.py` compares the two byte for byte.
