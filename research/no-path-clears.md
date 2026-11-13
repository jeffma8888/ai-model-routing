# When neither path clears the bar

Question: when no path clears the task's bar, should the delegation decision (`DESIGN.md` 13.5) still choose by the calibration bounds, as row 7 does, choose by cost, or refuse? Short answer: keep row 7. In `cost_effective` its choice ties always delegating for the highest held-out success of the paths measured here on all five committed delegation runs, of four datasets, and already costs less than working inline; taking the cheaper path instead loses 0.131 of held-out success on AutoBench and 0.135 on LLMRouterBench to save 35.4% and 45.8% of the cost. Refusing, the default, declines work that row 7's path did at the bar on 94.1% of the AutoBench row 7 cells and 54.4% of the response-bank ones, but only on 35.5% and 23.5% of the tau2-bench ones and 34.6% of the LLMRouterBench ones, so README Limitations says what row 7 gives on agentic work.

## Facts

- Row 7 (`none_clear`) decides 16.6% of the AutoBench cells, on tau2-bench 64.3% per domain and 50.7% pooled, 25.8% of the LLMRouterBench cells and 63.0% of the response-bank ones, the same share in both flavors of each run
- In `cost_effective` row 7 delegates on 1,308 of the 1,326 AutoBench row 7 cells, on every tau2-bench one, on 14,628 of the 14,840 LLMRouterBench ones and on 4,994 of the 5,040 response-bank ones, and its held-out success equals always delegating's: 0.861, 0.515, 0.594, 0.414 and 0.875
- Working inline on those cells scores 0.677, 0.510, 0.573, 0.243 and 0.861, at 0.064192, 1.550578, 1.451617, 0.051037 and 0.051705 USD per held-out item against row 7's 0.023511, 0.304005, 0.421111, 0.051008 and 0.011215
- Taking the path with the lower forecast cost moves held-out success by -0.131, -0.003, -0.008, -0.135 and -0.004 and the cost per item by -35.4%, -10.9%, -12.8%, -45.8% and -17.1%
- `refuse` (row 6) answers none of these cells. In `cost_effective` row 7's path reaches the bar on the held-out half on 94.1% of them on AutoBench, 35.5% per domain and 23.5% pooled on tau2-bench, 34.6% on LLMRouterBench and 54.4% on the response bank
- Recommendation: keep row 7 and keep `refuse` as the default; one README Limitations bullet says what row 7 gives on agentic work

## Method

- Runs: the five committed delegation runs, rerun in process with their own scripts' bars, base points and registries and 50 seeds, keeping the cells that their results files drop: [AutoBench](../evidence/delegation/RESULTS.md) (`DESIGN.md` 13.10, bars 0.7 and 0.8), [tau2-bench](../evidence/tau2-bench-delegation/RESULTS.md) (13.12, bars 0.3 to 0.8), per domain and pooled, [LLMRouterBench](../evidence/llmrouterbench-delegation/RESULTS.md) (13.13, bars 0.1, 0.3, 0.5 and 0.8) and the [LLM Routing Response Bank](../evidence/response-bank-delegation/RESULTS.md) (13.14, bars 0.8 and 0.9). The last two run on the rows their scripts' `select_rows` keeps, and the script stops unless each of their reruns has the config, tasks and summary of its committed `results.json`. Every model of a run is tried as the parent
- A cell is one (bar, flavor, point, parent, seed, task). Its `reason` is `none_clear` when inline is allowed, neither the parent's nor the delegate's calibration bound clears the bar, and the task's `on_no_model` is `best_available`, which the harness sets ([DESIGN.md](../DESIGN.md) 13.9)
- Four paths are scored on the held-out halves of the row 7 cells: `decision` (row 7's choice), `inline` (the parent), `delegate` (the routed delegate, itself the best available model below the bar) and, in `cost_effective` only, `cheaper`: delegate when the decision's forecast `delegate_cost_usd` is below its `inline_cost_usd`, else inline, the rule a cost-first row 7 would apply. A cell keeps no forecast cost, so [no_path_clears.py](no_path_clears.py) rebuilds each row 7 `cost_effective` decision from its calibration half as 13.9 states it, and stops unless the rebuilt mode, model and reason are the cell's
- Success is the held-out items a path answered correctly over the held-out items, pooled over the row 7 cells; cost per item is the list-price cost of those items over their number. "At the bar or above" counts the cells whose held-out success is at least the bar, that is the cells on which the path did on the held-out half what the bar asks. Each flavor's block also gives, per bar, the row 7 cells at that bar and on how many of them the decision's held-out success is at the bar or above
- `refuse` (row 6) has no path to score: on every row 7 cell `decide_delegation` would raise `NoModelClearsBar`, and the router would not do the work

## Results

```text
$ python research/no_path_clears.py --autobench autobench-tokens.jsonl --autobench-registry autobench-pool.json --tau2 tau2-calls.jsonl --tau2-pooled tau2-calls-all.jsonl --llmrouterbench llmrouterbench-matrix.jsonl --response-bank response-bank-matrix.jsonl
AutoBench (13.10 results.json): 16,000 cells, bars 0.7, 0.8
  cost_effective: none_clear on 1,326 of 8,000 cells (16.6%)
    bar 0.7: none_clear on 0 of 4,000 cells
    bar 0.8: none_clear on 1,326 of 4,000 cells, the decision's held-out success at the bar or above on 1,248 (94.1%)
    decision delegates on 1,308 and works inline on 18; 136,188 held-out items
    forecast cost lower for delegating on 608, for inline on 718
    decision  success 0.861  cost per item 0.023511 USD  held-out success at the bar or above on 1,248 (94.1%)
    inline    success 0.677  cost per item 0.064192 USD  held-out success at the bar or above on 316 (23.8%)
    delegate  success 0.861  cost per item 0.023554 USD  held-out success at the bar or above on 1,248 (94.1%)
    cheaper   success 0.730  cost per item 0.015179 USD  held-out success at the bar or above on 674 (50.8%)
    cheaper against decision: success -0.131, cost per item -35.4%
    decision's held-out success at least the better path's on 1,216 (91.7%)
  cost_blind: none_clear on 1,326 of 8,000 cells (16.6%)
    bar 0.7: none_clear on 0 of 4,000 cells
    bar 0.8: none_clear on 1,326 of 4,000 cells, the decision's held-out success at the bar or above on 1,248 (94.1%)
    decision delegates on 1,250 and works inline on 76; 136,188 held-out items
    decision  success 0.861  cost per item 0.029942 USD  held-out success at the bar or above on 1,248 (94.1%)
    inline    success 0.677  cost per item 0.064192 USD  held-out success at the bar or above on 316 (23.8%)
    delegate  success 0.861  cost per item 0.023554 USD  held-out success at the bar or above on 1,248 (94.1%)
    decision's held-out success at least the better path's on 1,222 (92.2%)
tau2-bench per domain (13.12 results.json): 21,600 cells, bars 0.3, 0.4, 0.5, 0.6, 0.7, 0.8
  cost_effective: none_clear on 6,941 of 10,800 cells (64.3%)
    bar 0.3: none_clear on 561 of 1,800 cells, the decision's held-out success at the bar or above on 550 (98.0%)
    bar 0.4: none_clear on 1,001 of 1,800 cells, the decision's held-out success at the bar or above on 759 (75.8%)
    bar 0.5: none_clear on 1,100 of 1,800 cells, the decision's held-out success at the bar or above on 418 (38.0%)
    bar 0.6: none_clear on 1,111 of 1,800 cells, the decision's held-out success at the bar or above on 121 (10.9%)
    bar 0.7: none_clear on 1,518 of 1,800 cells, the decision's held-out success at the bar or above on 385 (25.4%)
    bar 0.8: none_clear on 1,650 of 1,800 cells, the decision's held-out success at the bar or above on 231 (14.0%)
    decision delegates on 6,941 and works inline on 0; 294,019 held-out items
    forecast cost lower for delegating on 6,011, for inline on 930
    decision  success 0.515  cost per item 0.304005 USD  held-out success at the bar or above on 2,464 (35.5%)
    inline    success 0.510  cost per item 1.550578 USD  held-out success at the bar or above on 2,369 (34.1%)
    delegate  success 0.515  cost per item 0.304005 USD  held-out success at the bar or above on 2,464 (35.5%)
    cheaper   success 0.512  cost per item 0.270901 USD  held-out success at the bar or above on 2,370 (34.1%)
    cheaper against decision: success -0.003, cost per item -10.9%
    decision's held-out success at least the better path's on 5,225 (75.3%)
  cost_blind: none_clear on 6,941 of 10,800 cells (64.3%)
    bar 0.3: none_clear on 561 of 1,800 cells, the decision's held-out success at the bar or above on 550 (98.0%)
    bar 0.4: none_clear on 1,001 of 1,800 cells, the decision's held-out success at the bar or above on 766 (76.5%)
    bar 0.5: none_clear on 1,100 of 1,800 cells, the decision's held-out success at the bar or above on 425 (38.6%)
    bar 0.6: none_clear on 1,111 of 1,800 cells, the decision's held-out success at the bar or above on 107 (9.6%)
    bar 0.7: none_clear on 1,518 of 1,800 cells, the decision's held-out success at the bar or above on 406 (26.7%)
    bar 0.8: none_clear on 1,650 of 1,800 cells, the decision's held-out success at the bar or above on 245 (14.8%)
    decision delegates on 4,273 and works inline on 2,668; 294,019 held-out items
    decision  success 0.517  cost per item 0.774167 USD  held-out success at the bar or above on 2,499 (36.0%)
    inline    success 0.510  cost per item 1.550578 USD  held-out success at the bar or above on 2,369 (34.1%)
    delegate  success 0.518  cost per item 0.353000 USD  held-out success at the bar or above on 2,519 (36.3%)
    decision's held-out success at least the better path's on 5,205 (75.0%)
tau2-bench pooled (13.12 pooled.json): 7,200 cells, bars 0.3, 0.4, 0.5, 0.6, 0.7, 0.8
  cost_effective: none_clear on 1,826 of 3,600 cells (50.7%)
    bar 0.3: none_clear on 0 of 600 cells
    bar 0.4: none_clear on 0 of 600 cells
    bar 0.5: none_clear on 176 of 600 cells, the decision's held-out success at the bar or above on 176 (100.0%)
    bar 0.6: none_clear on 550 of 600 cells, the decision's held-out success at the bar or above on 253 (46.0%)
    bar 0.7: none_clear on 550 of 600 cells, the decision's held-out success at the bar or above on 0 (0.0%)
    bar 0.8: none_clear on 550 of 600 cells, the decision's held-out success at the bar or above on 0 (0.0%)
    decision delegates on 1,826 and works inline on 0; 252,186 held-out items
    forecast cost lower for delegating on 1,520, for inline on 306
    decision  success 0.594  cost per item 0.421111 USD  held-out success at the bar or above on 429 (23.5%)
    inline    success 0.573  cost per item 1.451617 USD  held-out success at the bar or above on 283 (15.5%)
    delegate  success 0.594  cost per item 0.421111 USD  held-out success at the bar or above on 429 (23.5%)
    cheaper   success 0.586  cost per item 0.367237 USD  held-out success at the bar or above on 385 (21.1%)
    cheaper against decision: success -0.008, cost per item -12.8%
    decision's held-out success at least the better path's on 1,554 (85.1%)
  cost_blind: none_clear on 1,826 of 3,600 cells (50.7%)
    bar 0.3: none_clear on 0 of 600 cells
    bar 0.4: none_clear on 0 of 600 cells
    bar 0.5: none_clear on 176 of 600 cells, the decision's held-out success at the bar or above on 176 (100.0%)
    bar 0.6: none_clear on 550 of 600 cells, the decision's held-out success at the bar or above on 274 (49.8%)
    bar 0.7: none_clear on 550 of 600 cells, the decision's held-out success at the bar or above on 0 (0.0%)
    bar 0.8: none_clear on 550 of 600 cells, the decision's held-out success at the bar or above on 0 (0.0%)
    decision delegates on 1,263 and works inline on 563; 252,186 held-out items
    decision  success 0.599  cost per item 0.827708 USD  held-out success at the bar or above on 450 (24.6%)
    inline    success 0.573  cost per item 1.451617 USD  held-out success at the bar or above on 283 (15.5%)
    delegate  success 0.602  cost per item 0.443925 USD  held-out success at the bar or above on 462 (25.3%)
    decision's held-out success at least the better path's on 1,587 (86.9%)
LLMRouterBench (13.13 results.json): 115,200 cells, bars 0.1, 0.3, 0.5, 0.8
  cost_effective: none_clear on 14,840 of 57,600 cells (25.8%)
    bar 0.1: none_clear on 600 of 14,400 cells, the decision's held-out success at the bar or above on 600 (100.0%)
    bar 0.3: none_clear on 1,800 of 14,400 cells, the decision's held-out success at the bar or above on 600 (33.3%)
    bar 0.5: none_clear on 4,250 of 14,400 cells, the decision's held-out success at the bar or above on 1,681 (39.6%)
    bar 0.8: none_clear on 8,190 of 14,400 cells, the decision's held-out success at the bar or above on 2,256 (27.5%)
    decision delegates on 14,628 and works inline on 212; 10,487,981 held-out items
    forecast cost lower for delegating on 5,046, for inline on 9,794
    decision  success 0.414  cost per item 0.051008 USD  held-out success at the bar or above on 5,137 (34.6%)
    inline    success 0.243  cost per item 0.051037 USD  held-out success at the bar or above on 2,635 (17.8%)
    delegate  success 0.414  cost per item 0.051147 USD  held-out success at the bar or above on 5,137 (34.6%)
    cheaper   success 0.279  cost per item 0.027632 USD  held-out success at the bar or above on 3,012 (20.3%)
    cheaper against decision: success -0.135, cost per item -45.8%
    decision's held-out success at least the better path's on 14,355 (96.7%)
  cost_blind: none_clear on 14,840 of 57,600 cells (25.8%)
    bar 0.1: none_clear on 600 of 14,400 cells, the decision's held-out success at the bar or above on 600 (100.0%)
    bar 0.3: none_clear on 1,800 of 14,400 cells, the decision's held-out success at the bar or above on 600 (33.3%)
    bar 0.5: none_clear on 4,250 of 14,400 cells, the decision's held-out success at the bar or above on 1,681 (39.6%)
    bar 0.8: none_clear on 8,190 of 14,400 cells, the decision's held-out success at the bar or above on 2,299 (28.1%)
    decision delegates on 12,319 and works inline on 2,521; 10,487,981 held-out items
    decision  success 0.414  cost per item 0.065393 USD  held-out success at the bar or above on 5,180 (34.9%)
    inline    success 0.243  cost per item 0.051037 USD  held-out success at the bar or above on 2,635 (17.8%)
    delegate  success 0.414  cost per item 0.051150 USD  held-out success at the bar or above on 5,161 (34.8%)
    decision's held-out success at least the better path's on 14,456 (97.4%)
LLM Routing Response Bank (13.14 results.json): 16,000 cells, bars 0.8, 0.9
  cost_effective: none_clear on 5,040 of 8,000 cells (63.0%)
    bar 0.8: none_clear on 1,060 of 4,000 cells, the decision's held-out success at the bar or above on 1,040 (98.1%)
    bar 0.9: none_clear on 3,980 of 4,000 cells, the decision's held-out success at the bar or above on 1,700 (42.7%)
    decision delegates on 4,994 and works inline on 46; 6,669,680 held-out items
    forecast cost lower for delegating on 4,396, for inline on 644
    decision  success 0.875  cost per item 0.011215 USD  held-out success at the bar or above on 2,740 (54.4%)
    inline    success 0.861  cost per item 0.051705 USD  held-out success at the bar or above on 1,660 (32.9%)
    delegate  success 0.875  cost per item 0.011291 USD  held-out success at the bar or above on 2,740 (54.4%)
    cheaper   success 0.870  cost per item 0.009297 USD  held-out success at the bar or above on 2,679 (53.2%)
    cheaper against decision: success -0.004, cost per item -17.1%
    decision's held-out success at least the better path's on 4,676 (92.8%)
  cost_blind: none_clear on 5,040 of 8,000 cells (63.0%)
    bar 0.8: none_clear on 1,060 of 4,000 cells, the decision's held-out success at the bar or above on 1,036 (97.7%)
    bar 0.9: none_clear on 3,980 of 4,000 cells, the decision's held-out success at the bar or above on 1,708 (42.9%)
    decision delegates on 3,604 and works inline on 1,436; 6,669,680 held-out items
    decision  success 0.875  cost per item 0.023288 USD  held-out success at the bar or above on 2,744 (54.4%)
    inline    success 0.861  cost per item 0.051705 USD  held-out success at the bar or above on 1,660 (32.9%)
    delegate  success 0.875  cost per item 0.011292 USD  held-out success at the bar or above on 2,780 (55.2%)
    decision's held-out success at least the better path's on 4,728 (93.8%)
```

## Reading it

- Row 7 is common on agentic data, and wherever a task's calibration half is under `min_samples` or the bar is high: it decides 64.3% of the tau2-bench `cost_effective` cells per domain and 50.7% pooled, against 16.6% on AutoBench. Part of it is airline's short calibration halves (the tau2-bench RESULTS.md says so); the rest is bars that no agent's calibration bound reaches. The response bank, not agentic, has it on 63.0% of its cells, for `aime`'s short halves and its higher bar (the dated section below)
- Bound first picks well. In `cost_effective` row 7's held-out success is at least that of the better of inline and delegating on 91.7% of the AutoBench row 7 cells, 75.3% per domain and 85.1% pooled on tau2-bench, 96.7% on LLMRouterBench and 92.8% on the response bank, and over all its cells it ties always delegating and beats inline on every run
- Cost first would lose quality where the parent scores far below the delegate. On AutoBench the forecast favours inline on 718 of the 1,326 cells, while over the row 7 cells the parent scores far below the delegate (inline 0.677 against 0.861), so `cheaper` falls to 0.730 and reaches the bar on 50.8% of the cells against row 7's 94.1%. On tau2-bench it saves 10.9% per domain and 12.8% pooled for a loss of 0.003 and 0.008, small since row 7 already delegates and the forecast favours delegating on 6,011 of 6,941 and 1,520 of 1,826 cells
- Refusing pays only where the bar is a hard requirement. On AutoBench row 7's path met the bar on the held-out half on 1,248 of 1,326 cells (94.1%): the calibration bound missed it by a margin the held-out half closed, and refusing would decline that work. On tau2-bench it met it on 2,464 of 6,941 per domain (35.5%) and 429 of 1,826 pooled (23.5%), so there row 7 mostly hands back a path below the bar, which `below_bar` flags on every such decision
- `cost_blind` never compares cost (13.5 rows 4 and 7): on tau2-bench per domain its row 7 works inline on 2,668 of 6,941 cells, so it costs 0.774167 USD per item against 0.353000 for always delegating, for a held-out success of 0.517 against 0.518

## LLMRouterBench and the response bank (2026-11-13)

- On LLMRouterBench row 7 decides 14,840 of the 57,600 cells of each flavor (25.8%), more of them the higher the bar: 600 at bar 0.1, 1,800 at 0.3, 4,250 at 0.5 and 8,190 at 0.8, of 14,400 at each. In `cost_effective` the decision's held-out success is at the bar or above on all 600 at bar 0.1, on 600 at 0.3 (33.3%), 1,681 at 0.5 (39.6%) and 2,256 at 0.8 (27.5%), 5,137 in all (34.6%), so there row 7 mostly takes a path below the bar, as on tau2-bench
- Its path is the delegate on 14,628 of the 14,840 `cost_effective` cells, scoring 0.414 against inline's 0.243 at about the same cost per item (0.051008 against 0.051037 USD). The forecast favours inline on 9,794 of them, so `cheaper` would fall to 0.279 for 45.8% less cost, the largest loss of success of the five runs
- On the response bank row 7 decides 5,040 of the 8,000 cells of each flavor (63.0%): 1,060 of the 4,000 at bar 0.8 and 3,980 of the 4,000 at bar 0.9. Every `aime` cell is among them, since its calibration halves are under the default `min_samples` (its RESULTS.md says so), and at bar 0.9 nearly every other cell is too. In `cost_effective` the decision's held-out success is at the bar or above on 1,040 at bar 0.8 (98.1%) and 1,700 at 0.9 (42.7%), 2,740 in all (54.4%)
- There row 7 delegates on 4,994 of the 5,040 `cost_effective` cells, scoring 0.875 against inline's 0.861 at 0.011215 against 0.051705 USD per item, and `cheaper` would save 17.1% for a loss of 0.004
- So the two runs leave the recommendation as it was: in `cost_effective` row 7 ties always delegating on both and beats inline, and a cost-first row 7 would lose the most success on LLMRouterBench, where the parent is weakest. The bar matters more than the dataset: at the lowest bar of each of the two, row 7's path meets the bar on nearly every cell (100.0% and 98.1%), at the highest on 27.5% and 42.7%

## Recommendation

- Keep 13.5 row 7 as it is: no spec row and no version bump. Its bound-first order ties always delegating for the highest held-out success of the paths measured here in `cost_effective` on all five runs, and already costs less than working inline, while a cost-first row 7 would trade 0.131 of held-out success for a 35.4% saving on AutoBench and 0.135 for 45.8% on LLMRouterBench, the opposite of what `best_available` asks for
- Keep `refuse` as the default of `Task.on_no_model`. The harness sets `best_available` so that every cell has a path to score (13.9); that is a choice of the evidence, not a recommendation for agentic tasks
- Say it in README Limitations: on the tau2-bench runs row 7 decides most `cost_effective` cells and takes a path whose held-out success is below the bar on most of them, while the default raises `NoModelClearsBar`

## Limits

- The runs' assumptions hold here too: a lossless brief, list prices and an assumed grid of context and hand-off sizes (the four RESULTS.md files say each)
- "At the bar or above" reads a point estimate on one held-out half, not a bound, and the 50 seeds re-split the same items, so the cells are not independent samples
- Only the four paths above are measured. A rule between them, for example refusing only when the bound misses the bar by more than a margin, is not

## Regenerate

The converters download the pinned files into a cache outside the repo and check each file's size and hash before reading it (see the four RESULTS.md files); the matrices they write are not committed, and the script takes about forty seconds, most of it the LLMRouterBench run.

```bash
python -m pip install -e .
python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens --registry autobench-pool.json
python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls
python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python evidence/response-bank/convert.py --out response-bank-matrix.jsonl
python research/no_path_clears.py --autobench autobench-tokens.jsonl --autobench-registry autobench-pool.json --tau2 tau2-calls.jsonl --tau2-pooled tau2-calls-all.jsonl --llmrouterbench llmrouterbench-matrix.jsonl --response-bank response-bank-matrix.jsonl
```
