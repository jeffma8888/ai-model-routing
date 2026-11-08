# When neither path clears the bar

Question: when no path clears the task's bar, should the delegation decision (`DESIGN.md` 13.5) still choose by the calibration bounds, as row 7 does, choose by cost, or refuse? Short answer: keep row 7. In `cost_effective` its choice ties always delegating for the highest held-out success of the paths measured here on all three committed delegation runs, and already costs less than working inline; taking the cheaper path instead loses 0.131 of held-out success on AutoBench to save 35.4% of the cost. Refusing, the default, declines work that row 7's path did at the bar on 94.1% of the AutoBench row 7 cells, but only on 35.5% and 23.5% of the tau2-bench ones, so README Limitations now says what row 7 gives on agentic work.

## Facts

- Row 7 (`none_clear`) decides 16.6% of the AutoBench cells and, on tau2-bench, 64.3% per domain and 50.7% pooled, the same share in both flavors of each run
- In `cost_effective` row 7 delegates on 1,308 of the 1,326 AutoBench row 7 cells and on every tau2-bench one, and its held-out success equals always delegating's: 0.861, 0.515 and 0.594
- Working inline on those cells scores 0.677, 0.510 and 0.573, at 0.064192, 1.550578 and 1.451617 USD per held-out item against row 7's 0.023511, 0.304005 and 0.421111
- Taking the path with the lower forecast cost moves held-out success by -0.131, -0.003 and -0.008 and the cost per item by -35.4%, -10.9% and -12.8%
- `refuse` (row 6) answers none of these cells. In `cost_effective` row 7's path reaches the bar on the held-out half on 94.1% of them on AutoBench, 35.5% per domain and 23.5% pooled on tau2-bench
- Recommendation: keep row 7 and keep `refuse` as the default; one README Limitations bullet says what row 7 gives on agentic work

## Method

- Runs: the three committed delegation runs, rerun in process with their own scripts' bars, base points and registries and 50 seeds, keeping the cells that their results files drop: [AutoBench](../evidence/delegation/RESULTS.md) (`DESIGN.md` 13.10, bars 0.7 and 0.8) and [tau2-bench](../evidence/tau2-bench-delegation/RESULTS.md) (13.12, bars 0.3 to 0.8), per domain and pooled. Every model of a run is tried as the parent
- A cell is one (bar, flavor, point, parent, seed, task). Its `reason` is `none_clear` when inline is allowed, neither the parent's nor the delegate's calibration bound clears the bar, and the task's `on_no_model` is `best_available`, which the harness sets ([DESIGN.md](../DESIGN.md) 13.9)
- Four paths are scored on the held-out halves of the row 7 cells: `decision` (row 7's choice), `inline` (the parent), `delegate` (the routed delegate, itself the best available model below the bar) and, in `cost_effective` only, `cheaper`: delegate when the decision's forecast `delegate_cost_usd` is below its `inline_cost_usd`, else inline, the rule a cost-first row 7 would apply. A cell keeps no forecast cost, so [no_path_clears.py](no_path_clears.py) rebuilds each row 7 `cost_effective` decision from its calibration half as 13.9 states it, and stops unless the rebuilt mode, model and reason are the cell's
- Success is the held-out items a path answered correctly over the held-out items, pooled over the row 7 cells; cost per item is the list-price cost of those items over their number. "At the bar or above" counts the cells whose held-out success is at least the bar, that is the cells on which the path did on the held-out half what the bar asks
- `refuse` (row 6) has no path to score: on every row 7 cell `decide_delegation` would raise `NoModelClearsBar`, and the router would not do the work

## Results

```text
$ python research/no_path_clears.py --autobench autobench-tokens.jsonl --autobench-registry autobench-pool.json --tau2 tau2-calls.jsonl --tau2-pooled tau2-calls-all.jsonl
AutoBench (13.10 results.json): 16,000 cells, bars 0.7, 0.8
  cost_effective: none_clear on 1,326 of 8,000 cells (16.6%)
    decision delegates on 1,308 and works inline on 18; 136,188 held-out items
    forecast cost lower for delegating on 608, for inline on 718
    decision  success 0.861  cost per item 0.023511 USD  held-out success at the bar or above on 1,248 (94.1%)
    inline    success 0.677  cost per item 0.064192 USD  held-out success at the bar or above on 316 (23.8%)
    delegate  success 0.861  cost per item 0.023554 USD  held-out success at the bar or above on 1,248 (94.1%)
    cheaper   success 0.730  cost per item 0.015179 USD  held-out success at the bar or above on 674 (50.8%)
    cheaper against decision: success -0.131, cost per item -35.4%
    decision's held-out success at least the better path's on 1,216 (91.7%)
  cost_blind: none_clear on 1,326 of 8,000 cells (16.6%)
    decision delegates on 1,250 and works inline on 76; 136,188 held-out items
    decision  success 0.861  cost per item 0.029942 USD  held-out success at the bar or above on 1,248 (94.1%)
    inline    success 0.677  cost per item 0.064192 USD  held-out success at the bar or above on 316 (23.8%)
    delegate  success 0.861  cost per item 0.023554 USD  held-out success at the bar or above on 1,248 (94.1%)
    decision's held-out success at least the better path's on 1,222 (92.2%)
tau2-bench per domain (13.12 results.json): 21,600 cells, bars 0.3, 0.4, 0.5, 0.6, 0.7, 0.8
  cost_effective: none_clear on 6,941 of 10,800 cells (64.3%)
    decision delegates on 6,941 and works inline on 0; 294,019 held-out items
    forecast cost lower for delegating on 6,011, for inline on 930
    decision  success 0.515  cost per item 0.304005 USD  held-out success at the bar or above on 2,464 (35.5%)
    inline    success 0.510  cost per item 1.550578 USD  held-out success at the bar or above on 2,369 (34.1%)
    delegate  success 0.515  cost per item 0.304005 USD  held-out success at the bar or above on 2,464 (35.5%)
    cheaper   success 0.512  cost per item 0.270901 USD  held-out success at the bar or above on 2,370 (34.1%)
    cheaper against decision: success -0.003, cost per item -10.9%
    decision's held-out success at least the better path's on 5,225 (75.3%)
  cost_blind: none_clear on 6,941 of 10,800 cells (64.3%)
    decision delegates on 4,273 and works inline on 2,668; 294,019 held-out items
    decision  success 0.517  cost per item 0.774167 USD  held-out success at the bar or above on 2,499 (36.0%)
    inline    success 0.510  cost per item 1.550578 USD  held-out success at the bar or above on 2,369 (34.1%)
    delegate  success 0.518  cost per item 0.353000 USD  held-out success at the bar or above on 2,519 (36.3%)
    decision's held-out success at least the better path's on 5,205 (75.0%)
tau2-bench pooled (13.12 pooled.json): 7,200 cells, bars 0.3, 0.4, 0.5, 0.6, 0.7, 0.8
  cost_effective: none_clear on 1,826 of 3,600 cells (50.7%)
    decision delegates on 1,826 and works inline on 0; 252,186 held-out items
    forecast cost lower for delegating on 1,520, for inline on 306
    decision  success 0.594  cost per item 0.421111 USD  held-out success at the bar or above on 429 (23.5%)
    inline    success 0.573  cost per item 1.451617 USD  held-out success at the bar or above on 283 (15.5%)
    delegate  success 0.594  cost per item 0.421111 USD  held-out success at the bar or above on 429 (23.5%)
    cheaper   success 0.586  cost per item 0.367237 USD  held-out success at the bar or above on 385 (21.1%)
    cheaper against decision: success -0.008, cost per item -12.8%
    decision's held-out success at least the better path's on 1,554 (85.1%)
  cost_blind: none_clear on 1,826 of 3,600 cells (50.7%)
    decision delegates on 1,263 and works inline on 563; 252,186 held-out items
    decision  success 0.599  cost per item 0.827708 USD  held-out success at the bar or above on 450 (24.6%)
    inline    success 0.573  cost per item 1.451617 USD  held-out success at the bar or above on 283 (15.5%)
    delegate  success 0.602  cost per item 0.443925 USD  held-out success at the bar or above on 462 (25.3%)
    decision's held-out success at least the better path's on 1,587 (86.9%)
```

## Reading it

- Row 7 is common on agentic data: it decides 64.3% of the tau2-bench `cost_effective` cells per domain and 50.7% pooled, against 16.6% on AutoBench. Part of it is airline's short calibration halves (the tau2-bench RESULTS.md says so); the rest is bars that no agent's calibration bound reaches
- Bound first picks well. In `cost_effective` row 7's held-out success is at least that of the better of inline and delegating on 91.7% of the AutoBench row 7 cells, 75.3% per domain and 85.1% pooled, and over all its cells it ties always delegating and beats inline on every run
- Cost first would lose quality where row 7 is closest to the bar. On AutoBench the forecast favours inline on 718 of the 1,326 cells, while over the row 7 cells the parent scores far below the delegate (inline 0.677 against 0.861), so `cheaper` falls to 0.730 and reaches the bar on 50.8% of the cells against row 7's 94.1%. On tau2-bench it saves 10.9% per domain and 12.8% pooled for a loss of 0.003 and 0.008, small since row 7 already delegates and the forecast favours delegating on 6,011 of 6,941 and 1,520 of 1,826 cells
- Refusing pays only where the bar is a hard requirement. On AutoBench row 7's path met the bar on the held-out half on 1,248 of 1,326 cells (94.1%): the calibration bound missed it by a margin the held-out half closed, and refusing would decline that work. On tau2-bench it met it on 2,464 of 6,941 per domain (35.5%) and 429 of 1,826 pooled (23.5%), so there row 7 mostly hands back a path below the bar, which `below_bar` flags on every such decision
- `cost_blind` never compares cost (13.5 rows 4 and 7): on tau2-bench per domain its row 7 works inline on 2,668 of 6,941 cells, so it costs 0.774167 USD per item against 0.353000 for always delegating, for a held-out success of 0.517 against 0.518

## Recommendation

- Keep 13.5 row 7 as it is: no spec row and no version bump. Its bound-first order ties always delegating for the highest held-out success of the paths measured here in `cost_effective` on all three runs, and already costs less than working inline, while a cost-first row 7 would trade 0.131 of held-out success for a 35.4% saving on AutoBench, the opposite of what `best_available` asks for
- Keep `refuse` as the default of `Task.on_no_model`. The harness sets `best_available` so that every cell has a path to score (13.9); that is a choice of the evidence, not a recommendation for agentic tasks
- Say it in README Limitations: on the tau2-bench runs row 7 decides most `cost_effective` cells and takes a path whose held-out success is below the bar on most of them, while the default raises `NoModelClearsBar`

## Limits

- The runs' assumptions hold here too: a lossless brief, list prices and an assumed grid of context and hand-off sizes (the two RESULTS.md files say each)
- "At the bar or above" reads a point estimate on one held-out half, not a bound, and the 50 seeds re-split the same items, so the cells are not independent samples
- Only the four paths above are measured. A rule between them, for example refusing only when the bound misses the bar by more than a margin, is not

## Regenerate

The converters download the pinned files into a cache outside the repo and check each file's size and hash before reading it (see the two RESULTS.md files); the matrices they write are not committed, and the script takes about ten seconds.

```bash
python -m pip install -e .
python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens --registry autobench-pool.json
python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls
python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all
python research/no_path_clears.py --autobench autobench-tokens.jsonl --autobench-registry autobench-pool.json --tau2 tau2-calls.jsonl --tau2-pooled tau2-calls-all.jsonl
```
