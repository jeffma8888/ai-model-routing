# Where the per-task delegation decision pays on the committed evidence

## Facts

- Question: does the per-task `DESIGN.md` 13.5 decision, inline or delegate, beat a fixed policy, always inline or always delegate, on the committed delegation evidence?
- Reads only the summary rows of the four committed delegation files: `evidence/delegation/results.json` (AutoBench), `evidence/tau2-bench-delegation/results.json` and `evidence/tau2-bench-delegation/pooled.json` (tau2-bench per domain and pooled) and `evidence/llmrouterbench-delegation/results.json` (LLMRouterBench). No library code, harness or results file changes.
- Short answer: rarely, and never on both success and cost. In `cost_effective` the decision equals always delegating on 403 of the 432 rows, every row at the three points where inline work is a call of its own among them. In `cost_blind` a fixed policy has a higher held-out success at no more cost on 106 of the 432 rows. On no row of either flavor is the decision better than both fixed policies.
- Which 13.5 row chose: in `cost_effective` every cell where inline work is a call of its own delegates on all four runs, as a condition from 13.2 on the parent's prices and the point's sizes says it must, and the cost comparison of row 3 chose on under a third of those cells (`## Which 13.5 row chose`).
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

- `cost_effective`: the decision equals always delegating on 403 of 432 rows and always inline on 1, and is better than both fixed policies on none. Every row at points 0, 1 and 2 is `= delegate`, so there the decision delegates on every cell for every parent and bar; every changed row and the one `= inline` row are at point 3, the one point where inline work folds into the parent's next call. With a separate inline call the parent re-reads its whole context for the work, which a delegate does not (13.2); delegating at the other three points is consistent with that cost, and `## Which 13.5 row chose` below counts the cells by the row that chose: the condition it states from 13.2 holds for every parent there, so every such cell delegates. On tau2-bench, per domain and pooled, the decision changes nothing at any point.
- Where it changes something in `cost_effective`, it sits between the two fixed policies. On LLMRouterBench all 21 changed rows cost less than always delegate, 6 of them at no less success, and 3 of the 26 trade-offs over the four files have a higher success than both. The largest gain is at bar 0.1, point 3, with `openai/gpt-5-chat` as the parent: 0.4846 at 66.5694 USD, against always delegate's 0.4496 at 88.0736 and always inline's 0.4710 at 32.9471, so +0.0135 over the better fixed policy at a cost between the two. On AutoBench 2 changed rows are beaten on success and the largest gain is +0.0000.
- `cost_blind`: the decision equals always delegating on 208 of 432 rows and is beaten on success on 106, a fixed policy there having more held-out success at no more cost, and no changed row has a higher success than both. No 13.5 row compares cost in this flavor, so it chooses by the calibration bounds alone, and a held-out half can rank the parent and its delegate the other way, as routing on a calibration half can rank models ([where-routing-pays.md](where-routing-pays.md)). The 68 rows beaten on cost alone have a fixed policy's success at a higher cost, which `cost_blind` does not weigh.
- So on this evidence the per-task decision is close to a fixed policy: in `cost_effective` it is always delegating except where the work folds into the parent's next call, and there it trades success against cost without beating both fixed policies.

## Which 13.5 row chose

- The question the summary rows leave open: which 13.5 row made the `cost_effective` decision delegate wherever inline work is a parent call of its own. `research/delegation_reasons.py` reruns each run as `research/per_item_delegation.py` does (the same 13.9 run on the same matrix, checked against the same committed summary) and counts its cells by the row and `reason` that chose their path.
- The condition, from 13.2 and stated before the counts. With inline work in a call of its own, inline minus delegating to the parent's own model is, in exact arithmetic, `p_in * K * (rho * C - B) - p_out * B + (1 + T) * p_in * (K * (S_in + S_out) - B - R)`, with `p_in` and `p_out` the parent's list prices per token and `S_in` and `S_out` its sizes. Where the parent passes the delegate's `select`, the `cost_effective` delegate costs no more on its work than the parent's own model would (13.3), and where no candidate passes, the 5.3 order gives a primary whose bound is at least the parent's and, at an equal bound, whose work costs no more. So a separate inline call costs more than delegating at every size when `slack * p_in > B * p_out`, with `slack = K * (rho * C - B) - (1 + T) * (B + R)` tokens: a parent whose output price is under `slack / B` times its input price. A positive slack also makes `B < C`, so 13.5 row 5 cannot occur, and rows 1 and 2 delegate by definition; so at a point and parent that meet it, every `cost_effective` cell of a 13.9 run delegates. The script prints, per point, the slack and the parents that meet it, then a check line.

```text
$ python research/delegation_reasons.py --matrix llmrouterbench-matrix.jsonl
Which 13.5 row chose each cell's path on LLMRouterBench: the cells of the 13.9 run by flavor, point, row and reason
run: 115,200 cells (4 bars, 2 flavors, 4 points, 8 parents, 50 seeds, 9 tasks)
condition (DESIGN.md 13.8 v1.253): a separate inline call costs more than delegating at every size when slack * p_in > B * p_out, slack = K * (rho * C - B) - (1 + T) * (B + R)
  point 0: C 8,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 5,500, slack / B 11.0000; met by 8 of 8 parents, highest ratio 8.0000 (openai/gpt-5)
  point 1: C 64,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 61,500, slack / B 123.0000; met by 8 of 8 parents, highest ratio 8.0000 (openai/gpt-5)
  point 2: C 200,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 197,500, slack / B 395.0000; met by 8 of 8 parents, highest ratio 8.0000 (openai/gpt-5)
  point 3: C 8,000, B 500, R 500, T 1, folded, K 1, rho 1: does not apply (folded)
cells by 13.5 row and reason
  cost_effective  point 0  14,400 cells: row 2 parent_below_bar delegate 2,257; row 3 delegate_cheaper delegate 7,239; row 7 none_clear delegate 4,904
  cost_effective  point 1  14,400 cells: row 1 parent_context_full delegate 1,092; row 2 parent_below_bar delegate 2,038; row 3 delegate_cheaper delegate 6,851; row 7 none_clear delegate 4,419
  cost_effective  point 2  14,400 cells: row 1 parent_context_full delegate 12,600; row 2 parent_below_bar delegate 3; row 3 delegate_cheaper delegate 1,184; row 7 none_clear delegate 613
  cost_effective  point 3  14,400 cells: row 2 parent_below_bar delegate 2,257; row 3 delegate_cheaper delegate 4,647; row 3 inline_cheaper inline 2,592; row 7 none_clear delegate 4,692; row 7 none_clear inline 212
  cost_blind      point 0  14,400 cells: row 2 parent_below_bar delegate 2,257; row 4 delegate_better delegate 5,995; row 4 inline_as_good inline 1,244; row 7 none_clear delegate 4,256; row 7 none_clear inline 648
  cost_blind      point 1  14,400 cells: row 1 parent_context_full delegate 1,092; row 2 parent_below_bar delegate 2,038; row 4 delegate_better delegate 5,607; row 4 inline_as_good inline 1,244; row 7 none_clear delegate 3,771; row 7 none_clear inline 648
  cost_blind      point 2  14,400 cells: row 1 parent_context_full delegate 12,600; row 2 parent_below_bar delegate 3; row 4 delegate_better delegate 77; row 4 inline_as_good inline 1,107; row 7 none_clear delegate 36; row 7 none_clear inline 577
  cost_blind      point 3  14,400 cells: row 2 parent_below_bar delegate 2,257; row 4 delegate_better delegate 5,995; row 4 inline_as_good inline 1,244; row 7 none_clear delegate 4,256; row 7 none_clear inline 648
check, cost_effective: 43,200 cells at a separate point whose parent meets the condition, 43,200 of them delegate
```

```text
$ python research/delegation_reasons.py --dataset autobench --matrix autobench-tokens.jsonl --registry autobench-pool.json
Which 13.5 row chose each cell's path on AutoBench 2026: the cells of the 13.9 run by flavor, point, row and reason
run: 16,000 cells (2 bars, 2 flavors, 4 points, 20 parents, 50 seeds, 1 task)
condition (DESIGN.md 13.8 v1.253): a separate inline call costs more than delegating at every size when slack * p_in > B * p_out, slack = K * (rho * C - B) - (1 + T) * (B + R)
  point 0: C 8,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 5,500, slack / B 11.0000; met by 20 of 20 parents, highest ratio 6.0000 (nvidia/nemotron-3-ultra-550b-a55b)
  point 1: C 64,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 61,500, slack / B 123.0000; met by 20 of 20 parents, highest ratio 6.0000 (nvidia/nemotron-3-ultra-550b-a55b)
  point 2: C 200,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 197,500, slack / B 395.0000; met by 20 of 20 parents, highest ratio 6.0000 (nvidia/nemotron-3-ultra-550b-a55b)
  point 3: C 8,000, B 500, R 500, T 1, folded, K 1, rho 1: does not apply (folded)
cells by 13.5 row and reason
  cost_effective  point 0  2,000 cells: row 2 parent_below_bar delegate 1,353; row 3 delegate_cheaper delegate 307; row 7 none_clear delegate 340
  cost_effective  point 1  2,000 cells: row 2 parent_below_bar delegate 1,353; row 3 delegate_cheaper delegate 307; row 7 none_clear delegate 340
  cost_effective  point 2  2,000 cells: row 1 parent_context_full delegate 200; row 2 parent_below_bar delegate 1,187; row 3 delegate_cheaper delegate 307; row 7 none_clear delegate 306
  cost_effective  point 3  2,000 cells: row 2 parent_below_bar delegate 1,353; row 3 delegate_cheaper delegate 208; row 3 inline_cheaper inline 99; row 7 none_clear delegate 322; row 7 none_clear inline 18
  cost_blind      point 0  2,000 cells: row 2 parent_below_bar delegate 1,353; row 4 delegate_better delegate 214; row 4 inline_as_good inline 93; row 7 none_clear delegate 321; row 7 none_clear inline 19
  cost_blind      point 1  2,000 cells: row 2 parent_below_bar delegate 1,353; row 4 delegate_better delegate 214; row 4 inline_as_good inline 93; row 7 none_clear delegate 321; row 7 none_clear inline 19
  cost_blind      point 2  2,000 cells: row 1 parent_context_full delegate 200; row 2 parent_below_bar delegate 1,187; row 4 delegate_better delegate 214; row 4 inline_as_good inline 93; row 7 none_clear delegate 287; row 7 none_clear inline 19
  cost_blind      point 3  2,000 cells: row 2 parent_below_bar delegate 1,353; row 4 delegate_better delegate 214; row 4 inline_as_good inline 93; row 7 none_clear delegate 321; row 7 none_clear inline 19
check, cost_effective: 6,000 cells at a separate point whose parent meets the condition, 6,000 of them delegate
```

```text
$ python research/delegation_reasons.py --dataset tau2-bench --matrix tau2-calls.jsonl
Which 13.5 row chose each cell's path on tau2-bench per domain: the cells of the 13.9 run by flavor, point, row and reason
run: 21,600 cells (6 bars, 2 flavors, 4 points, 3 parents, 50 seeds, 3 tasks)
condition (DESIGN.md 13.8 v1.253): a separate inline call costs more than delegating at every size when slack * p_in > B * p_out, slack = K * (rho * C - B) - (1 + T) * (B + R)
  point 0: C 8,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 5,500, slack / B 11.0000; met by 3 of 3 parents, highest ratio 5.0000 (anthropic/claude-3-7-sonnet-20250219)
  point 1: C 64,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 61,500, slack / B 123.0000; met by 3 of 3 parents, highest ratio 5.0000 (anthropic/claude-3-7-sonnet-20250219)
  point 2: C 200,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 197,500, slack / B 395.0000; met by 3 of 3 parents, highest ratio 5.0000 (anthropic/claude-3-7-sonnet-20250219)
  point 3: C 8,000, B 500, R 500, T 1, folded, K 1, rho 1: does not apply (folded)
cells by 13.5 row and reason
  cost_effective  point 0  2,700 cells: row 2 parent_below_bar delegate 169; row 3 delegate_cheaper delegate 638; row 7 none_clear delegate 1,893
  cost_effective  point 1  2,700 cells: row 2 parent_below_bar delegate 169; row 3 delegate_cheaper delegate 638; row 7 none_clear delegate 1,893
  cost_effective  point 2  2,700 cells: row 1 parent_context_full delegate 900; row 2 parent_below_bar delegate 151; row 3 delegate_cheaper delegate 387; row 7 none_clear delegate 1,262
  cost_effective  point 3  2,700 cells: row 2 parent_below_bar delegate 169; row 3 delegate_cheaper delegate 638; row 7 none_clear delegate 1,893
  cost_blind      point 0  2,700 cells: row 2 parent_below_bar delegate 169; row 4 delegate_better delegate 350; row 4 inline_as_good inline 288; row 7 none_clear delegate 1,143; row 7 none_clear inline 750
  cost_blind      point 1  2,700 cells: row 2 parent_below_bar delegate 169; row 4 delegate_better delegate 350; row 4 inline_as_good inline 288; row 7 none_clear delegate 1,143; row 7 none_clear inline 750
  cost_blind      point 2  2,700 cells: row 1 parent_context_full delegate 900; row 2 parent_below_bar delegate 151; row 4 delegate_better delegate 325; row 4 inline_as_good inline 62; row 7 none_clear delegate 844; row 7 none_clear inline 418
  cost_blind      point 3  2,700 cells: row 2 parent_below_bar delegate 169; row 4 delegate_better delegate 350; row 4 inline_as_good inline 288; row 7 none_clear delegate 1,143; row 7 none_clear inline 750
check, cost_effective: 8,100 cells at a separate point whose parent meets the condition, 8,100 of them delegate
```

```text
$ python research/delegation_reasons.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl
Which 13.5 row chose each cell's path on tau2-bench pooled: the cells of the 13.9 run by flavor, point, row and reason
run: 7,200 cells (6 bars, 2 flavors, 4 points, 3 parents, 50 seeds, 1 task)
condition (DESIGN.md 13.8 v1.253): a separate inline call costs more than delegating at every size when slack * p_in > B * p_out, slack = K * (rho * C - B) - (1 + T) * (B + R)
  point 0: C 8,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 5,500, slack / B 11.0000; met by 3 of 3 parents, highest ratio 5.0000 (anthropic/claude-3-7-sonnet-20250219)
  point 1: C 64,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 61,500, slack / B 123.0000; met by 3 of 3 parents, highest ratio 5.0000 (anthropic/claude-3-7-sonnet-20250219)
  point 2: C 200,000, B 500, R 500, T 1, separate, K 1, rho 1: slack 197,500, slack / B 395.0000; met by 3 of 3 parents, highest ratio 5.0000 (anthropic/claude-3-7-sonnet-20250219)
  point 3: C 8,000, B 500, R 500, T 1, folded, K 1, rho 1: does not apply (folded)
cells by 13.5 row and reason
  cost_effective  point 0  900 cells: row 2 parent_below_bar delegate 61; row 3 delegate_cheaper delegate 341; row 7 none_clear delegate 498
  cost_effective  point 1  900 cells: row 2 parent_below_bar delegate 61; row 3 delegate_cheaper delegate 341; row 7 none_clear delegate 498
  cost_effective  point 2  900 cells: row 1 parent_context_full delegate 300; row 2 parent_below_bar delegate 59; row 3 delegate_cheaper delegate 209; row 7 none_clear delegate 332
  cost_effective  point 3  900 cells: row 2 parent_below_bar delegate 61; row 3 delegate_cheaper delegate 341; row 7 none_clear delegate 498
  cost_blind      point 0  900 cells: row 2 parent_below_bar delegate 61; row 4 delegate_better delegate 200; row 4 inline_as_good inline 141; row 7 none_clear delegate 321; row 7 none_clear inline 177
  cost_blind      point 1  900 cells: row 2 parent_below_bar delegate 61; row 4 delegate_better delegate 200; row 4 inline_as_good inline 141; row 7 none_clear delegate 321; row 7 none_clear inline 177
  cost_blind      point 2  900 cells: row 1 parent_context_full delegate 300; row 2 parent_below_bar delegate 59; row 4 delegate_better delegate 187; row 4 inline_as_good inline 22; row 7 none_clear delegate 300; row 7 none_clear inline 32
  cost_blind      point 3  900 cells: row 2 parent_below_bar delegate 61; row 4 delegate_better delegate 200; row 4 inline_as_good inline 141; row 7 none_clear delegate 321; row 7 none_clear inline 177
check, cost_effective: 2,700 cells at a separate point whose parent meets the condition, 2,700 of them delegate
```

- `cost_effective`: every cell at points 0, 1 and 2 delegates on all four runs. The check lines count 43,200, 6,000, 8,100 and 2,700 cells whose parent meets the condition, every parent of every pool at all three points, and all of them delegate. By row, those 60,000 cells are row 3 `delegate_cheaper` on 18,749, row 7 `none_clear` on 17,298, row 1 `parent_context_full` on 15,092 and row 2 `parent_below_bar` on 8,861.
- So the cost comparison of row 3 chose on under a third of those cells, and always for delegating, as the condition says it must: the highest output-to-input price ratio of each pool, 8 on LLMRouterBench, 6 on AutoBench 2026 and 5 on tau2-bench, is under the 11 of point 0, the point with the least slack. The other cells delegate without comparing the two paths' costs in row 3: the parent's window cannot hold the work (row 1, most of them at point 2, where C is 200,000), the parent is below the bar and a delegate clears it (row 2), or no path clears and the primary has the higher bound or, at an equal bound, the lower cost (row 7, where the condition again rules inline out).
- At the folded point 3, outside the condition, row 3 goes inline on 2,592 LLMRouterBench cells and 99 AutoBench 2026 cells and row 7 on 212 and 18: these inline cells are behind the changed rows and the one `= inline` row of the Results above. On tau2-bench, per domain and pooled, point 3 has the counts of point 0, every cell delegating.
- `cost_blind` compares no cost, so row 4 keeps the parent inline on an equal bound (`inline_as_good`) and row 7 keeps it inline where its bound is the best, at every point; those inline cells are why its rows at points 0, 1 and 2 are not all `= delegate`.
- Recommended for the README `Inline or sub-agent` subsection, one sentence: "With inline work in a call of its own, `cost_effective` delegates whenever `C - B - (1 + T) * (B + R)` is above `B` times the parent's output price over its input price, since that call re-reads the parent's whole context; at a 500-token brief and result and one later call, any `C > 2,500 + 500 * p_out / p_in`, and every `cost_effective` cell of the committed delegation runs at such a point delegates."

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

The `## Which 13.5 row chose` blocks rerun the delegation runs on the converters' matrices, which need the pinned source files (each converter downloads and verifies them):

```text
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python research/delegation_reasons.py --matrix llmrouterbench-matrix.jsonl
python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens --registry autobench-pool.json
python research/delegation_reasons.py --dataset autobench --matrix autobench-tokens.jsonl --registry autobench-pool.json
python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls
python research/delegation_reasons.py --dataset tau2-bench --matrix tau2-calls.jsonl
python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all
python research/delegation_reasons.py --dataset tau2-bench-pooled --matrix tau2-calls-all.jsonl
```

`tests/test_research_delegation_reasons.py` compares each of those blocks with the script's output where the pinned files are cached.
