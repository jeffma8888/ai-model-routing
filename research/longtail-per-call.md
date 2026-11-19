# Longtail-SWE per call, under a stated split of each run's totals (2026-11-19)

## Facts

- Question: [longtail-delegation.md](longtail-delegation.md) finds that the 13.9 harness cannot read a Longtail-SWE run's token totals as one call, and that the release records no per-call tokens. If each run is split into its model calls by a stated rule, can the harness score the inline-or-sub-agent decision (DESIGN 13.5) per call, with each registry model as the parent and the four as the delegate pool, and what does it find against always inline and always delegating?
- Data: nebius/Longtail-SWE-trajectories at revision dfd6075c56b7841b9c254cc70a57e39c1df0076c (CC BY 4.0), the four pinned files of the converter `evidence/longtail-swe/convert.py` (12.25), read outside the repo through `research/longtail_delegation.py`, which keeps counts only; no statement, message or patch is printed, kept or committed
- Script: [longtail_per_call.py](longtail_per_call.py), `python research/longtail_per_call.py` (it needs `pyarrow`, the `evidence` extra); tests/test_research_longtail_per_call.py checks the split on hand cases and the block against a fresh run where the files are cached
- Short answer: yes, under the split, which is an assumption the release cannot check. It refuses 0 runs, and the last call of a run reads and writes a median 128,148 tokens, over its model's window on 1 of 776 rows. In `cost_effective` the decision delegates every cell at bars 0.7 and 0.8 and so equals always delegating on 32 of 32 rows; at bar 0.8 the decision is below the bar on 736 of 800 cells

## Method

The split is the assumption this note adds (DESIGN 13.16 v1.496). A run of K model calls (`usage.model_calls`), input total I and output total O gives call j the output b_j = O // K, call 1 also O % K, and each call the same new input a = L // T, where T = K (K + 1) / 2 and L = I - sum (K - j) b_j is what the K calls read less their re-reads of earlier outputs; the remainder r = L % T goes r // K to call 1 and r % K to call K. Then the K calls read I and write O, as the harness's per-call mode (13.9 v1.74) checks: call j reads every earlier call's new input and output and its own new input. Equal new input a call is the 13.2 model the decision forecasts with. A run with L below 0 would be refused and its item dropped for all four models. The split rows go to `model_routing.evaluate_delegation` at bars 0.7 and 0.8, with the seeds, flavors, calibration fraction, `min_samples` and confidence of `evidence/longtail-swe/results.json` and the four points of [longtail-delegation.md](longtail-delegation.md): contexts 8,000, 64,000 and 200,000 in a separate inline call and 8,000 folded into the next call, carry turns 1, and the brief and result its medians of the user prompt and the patch at characters over 4, rounded up. Always inline is the parent's own run; always delegating is the decision's delegate's run with the brief read on each of its calls. The block is the script's output.

## Results

```text
nebius/Longtail-SWE-trajectories at dfd6075: the 12.26 matrix (run 0, 194 items, 4 models, 776 rows), each run split into its model calls
Split: runs refused (input below their outputs' re-reads) 0, items dropped 0, rows kept 776
  new input a call: median 2,506, 10th to 90th percentile 1,471 to 3,965
  output a call: median 642, 10th to 90th percentile 451 to 921
  last call's read plus write: median 128,148, 10th to 90th percentile 57,732 to 308,617
Context window against the last call's read plus write
model                      window      over  median last call
anthropic/claude-opus-5.5  1,000,000    0 of 194           113,085
openai/gpt-5.6-luna        1,050,000    1 of 194           252,069
openai/gpt-5.6-sol         1,050,000    0 of 194           126,061
openai/gpt-6.1-sol         1,050,000    0 of 194            92,972
13.9 harness per call, bars 0.7 0.8, 50 seeds, 83 to 115 held-out items, points (carry turns 1, brief 1,244, result 4,863): 0 context 8,000 separate; 1 context 64,000 separate; 2 context 200,000 separate; 3 context 8,000 folded
  decision sizes over the cells: new input a call 2,501 to 2,737, output a call 631 to 682, work calls 35 to 41
  cost_effective, cells whose decision is below the bar: bar 0.7 48 of 800; bar 0.8 736 of 800
  cost_blind, cells whose decision is below the bar: bar 0.7 48 of 800; bar 0.8 736 of 800
success and cost (USD summed over the held-out items), means over seeds
flavor          bar  point  parent                     delegated  decision        inline          delegate
cost_effective  0.7  0      anthropic/claude-opus-5.5       1.00  0.812    1,071  0.837    2,009  0.812    1,071
cost_effective  0.7  0      openai/gpt-5.6-luna             1.00  0.812    1,065  0.726      275  0.812    1,065
cost_effective  0.7  0      openai/gpt-5.6-sol              1.00  0.812    1,071  0.787    1,358  0.812    1,071
cost_effective  0.7  0      openai/gpt-6.1-sol              1.00  0.812    1,068  0.804      442  0.812    1,068
cost_effective  0.7  1      anthropic/claude-opus-5.5       1.00  0.812    1,071  0.837    3,166  0.812    1,071
cost_effective  0.7  1      openai/gpt-5.6-luna             1.00  0.812    1,065  0.726      357  0.812    1,065
cost_effective  0.7  1      openai/gpt-5.6-sol              1.00  0.812    1,071  0.787    2,091  0.812    1,071
cost_effective  0.7  1      openai/gpt-6.1-sol              1.00  0.812    1,068  0.804      735  0.812    1,068
cost_effective  0.7  2      anthropic/claude-opus-5.5       1.00  0.812    1,071  0.837    5,976  0.812    1,071
cost_effective  0.7  2      openai/gpt-5.6-luna             1.00  0.812    1,065  0.726      556  0.812    1,065
cost_effective  0.7  2      openai/gpt-5.6-sol              1.00  0.812    1,071  0.787    3,870  0.812    1,071
cost_effective  0.7  2      openai/gpt-6.1-sol              1.00  0.812    1,068  0.804    1,449  0.812    1,068
cost_effective  0.7  3      anthropic/claude-opus-5.5       1.00  0.812    1,071  0.837    1,957  0.812    1,071
cost_effective  0.7  3      openai/gpt-5.6-luna             1.00  0.812    1,065  0.726      269  0.812    1,065
cost_effective  0.7  3      openai/gpt-5.6-sol              1.00  0.812    1,071  0.787    1,300  0.812    1,071
cost_effective  0.7  3      openai/gpt-6.1-sol              1.00  0.812    1,068  0.804      419  0.812    1,068
cost_effective  0.8  0      anthropic/claude-opus-5.5       1.00  0.823    1,571  0.837    2,009  0.823    1,571
cost_effective  0.8  0      openai/gpt-5.6-luna             1.00  0.823    1,564  0.726      275  0.823    1,564
cost_effective  0.8  0      openai/gpt-5.6-sol              1.00  0.823    1,571  0.787    1,358  0.823    1,571
cost_effective  0.8  0      openai/gpt-6.1-sol              1.00  0.823    1,567  0.804      442  0.823    1,567
cost_effective  0.8  1      anthropic/claude-opus-5.5       1.00  0.823    1,571  0.837    3,166  0.823    1,571
cost_effective  0.8  1      openai/gpt-5.6-luna             1.00  0.823    1,564  0.726      357  0.823    1,564
cost_effective  0.8  1      openai/gpt-5.6-sol              1.00  0.823    1,571  0.787    2,091  0.823    1,571
cost_effective  0.8  1      openai/gpt-6.1-sol              1.00  0.823    1,567  0.804      735  0.823    1,567
cost_effective  0.8  2      anthropic/claude-opus-5.5       1.00  0.823    1,571  0.837    5,976  0.823    1,571
cost_effective  0.8  2      openai/gpt-5.6-luna             1.00  0.823    1,564  0.726      556  0.823    1,564
cost_effective  0.8  2      openai/gpt-5.6-sol              1.00  0.823    1,571  0.787    3,870  0.823    1,571
cost_effective  0.8  2      openai/gpt-6.1-sol              1.00  0.823    1,567  0.804    1,449  0.823    1,567
cost_effective  0.8  3      anthropic/claude-opus-5.5       1.00  0.823    1,571  0.837    1,957  0.823    1,571
cost_effective  0.8  3      openai/gpt-5.6-luna             1.00  0.823    1,564  0.726      269  0.823    1,564
cost_effective  0.8  3      openai/gpt-5.6-sol              1.00  0.823    1,571  0.787    1,300  0.823    1,571
cost_effective  0.8  3      openai/gpt-6.1-sol              1.00  0.823    1,567  0.804      419  0.823    1,567
cost_blind      0.7  0      anthropic/claude-opus-5.5       0.04  0.832    1,959  0.837    2,009  0.832    1,738
cost_blind      0.7  0      openai/gpt-5.6-luna             1.00  0.832    1,731  0.726      275  0.832    1,731
cost_blind      0.7  0      openai/gpt-5.6-sol              0.98  0.832    1,742  0.787    1,358  0.832    1,738
cost_blind      0.7  0      openai/gpt-6.1-sol              0.86  0.823    1,578  0.804      442  0.832    1,735
cost_blind      0.7  1      anthropic/claude-opus-5.5       0.04  0.832    3,071  0.837    3,166  0.832    1,738
cost_blind      0.7  1      openai/gpt-5.6-luna             1.00  0.832    1,731  0.726      357  0.832    1,731
cost_blind      0.7  1      openai/gpt-5.6-sol              0.98  0.832    1,756  0.787    2,091  0.832    1,738
cost_blind      0.7  1      openai/gpt-6.1-sol              0.86  0.823    1,619  0.804      735  0.832    1,735
cost_blind      0.7  2      anthropic/claude-opus-5.5       0.04  0.832    5,770  0.837    5,976  0.832    1,738
cost_blind      0.7  2      openai/gpt-5.6-luna             1.00  0.832    1,731  0.726      556  0.832    1,731
cost_blind      0.7  2      openai/gpt-5.6-sol              0.98  0.832    1,792  0.787    3,870  0.832    1,738
cost_blind      0.7  2      openai/gpt-6.1-sol              0.86  0.823    1,719  0.804    1,449  0.832    1,735
cost_blind      0.7  3      anthropic/claude-opus-5.5       0.04  0.832    1,909  0.837    1,957  0.832    1,738
cost_blind      0.7  3      openai/gpt-5.6-luna             1.00  0.832    1,731  0.726      269  0.832    1,731
cost_blind      0.7  3      openai/gpt-5.6-sol              0.98  0.832    1,741  0.787    1,300  0.832    1,738
cost_blind      0.7  3      openai/gpt-6.1-sol              0.86  0.823    1,575  0.804      419  0.832    1,735
cost_blind      0.8  0      anthropic/claude-opus-5.5       0.04  0.832    1,959  0.837    2,009  0.832    1,738
cost_blind      0.8  0      openai/gpt-5.6-luna             1.00  0.832    1,731  0.726      275  0.832    1,731
cost_blind      0.8  0      openai/gpt-5.6-sol              0.98  0.832    1,742  0.787    1,358  0.832    1,738
cost_blind      0.8  0      openai/gpt-6.1-sol              0.86  0.823    1,578  0.804      442  0.832    1,735
cost_blind      0.8  1      anthropic/claude-opus-5.5       0.04  0.832    3,071  0.837    3,166  0.832    1,738
cost_blind      0.8  1      openai/gpt-5.6-luna             1.00  0.832    1,731  0.726      357  0.832    1,731
cost_blind      0.8  1      openai/gpt-5.6-sol              0.98  0.832    1,756  0.787    2,091  0.832    1,738
cost_blind      0.8  1      openai/gpt-6.1-sol              0.86  0.823    1,619  0.804      735  0.832    1,735
cost_blind      0.8  2      anthropic/claude-opus-5.5       0.04  0.832    5,770  0.837    5,976  0.832    1,738
cost_blind      0.8  2      openai/gpt-5.6-luna             1.00  0.832    1,731  0.726      556  0.832    1,731
cost_blind      0.8  2      openai/gpt-5.6-sol              0.98  0.832    1,792  0.787    3,870  0.832    1,738
cost_blind      0.8  2      openai/gpt-6.1-sol              0.86  0.823    1,719  0.804    1,449  0.832    1,735
cost_blind      0.8  3      anthropic/claude-opus-5.5       0.04  0.832    1,909  0.837    1,957  0.832    1,738
cost_blind      0.8  3      openai/gpt-5.6-luna             1.00  0.832    1,731  0.726      269  0.832    1,731
cost_blind      0.8  3      openai/gpt-5.6-sol              0.98  0.832    1,741  0.787    1,300  0.832    1,738
cost_blind      0.8  3      openai/gpt-6.1-sol              0.86  0.823    1,575  0.804      419  0.832    1,735
cost_effective: decision = always delegating on 32 of 32 rows; at or above always inline's success for less cost on 7
cost_blind: decision = always delegating on 8 of 32 rows; at or above always inline's success for less cost on 4
```

## Reading it

- The split fits the data: it refuses 0 runs, so no item is dropped and all 776 rows are scored. A call adds a median 2,506 tokens of new input (10th to 90th percentile 1,471 to 3,965) and writes a median 642 (451 to 921), and a run's last call reads and writes a median 128,148 tokens (57,732 to 308,617), over its model's window on 1 of 194 rows of `openai/gpt-5.6-luna` and 0 of each other model's. These are the split's sizes, not measured ones: a run's largest call may be larger.
- The harness scores every cell. Over the calibration halves the decision works with 2,501 to 2,737 tokens of new input a call, 631 to 682 of output and 35 to 41 work calls, and 83 to 115 items are held out per seed.
- The bar binds: the decision is below the bar on 48 of 800 cells at bar 0.7 and on 736 of 800 at bar 0.8 in each flavor, so at 0.8 nearly every cell is decided by the below-bar rule of 13.5, between the parent and the delegate by their lower bounds, not by a model that clears.
- In `cost_effective` the decision delegates on every cell (1.00 on each row) and equals always delegating on 32 of 32 rows: at bar 0.7 a success of 0.812 for 1,065 to 1,071 USD summed over the held-out items, at bar 0.8 0.823 for 1,564 to 1,571, whichever the parent. Always inline is 0.837 on `anthropic/claude-opus-5.5`, 0.804 on `openai/gpt-6.1-sol`, 0.787 on `openai/gpt-5.6-sol` and 0.726 on `openai/gpt-5.6-luna`, so delegating raises the success of the three other parents and lowers the strongest one's; it is at or above always inline's success for less cost on 7 of the 32 rows.
- In `cost_blind` the decision equals always delegating on 8 of 32 rows, those of `openai/gpt-5.6-luna`, delegates on 0.04 of the cells of `anthropic/claude-opus-5.5` (0.832 against its inline 0.837), and at or above always inline's success for less cost on 4.
- The context point moves only the inline cost, since a run's work calls re-read the parent's context (all K of them in a separate call, all but the last when folded): `anthropic/claude-opus-5.5` inline costs 1,957 USD folded at 8,000 and 5,976 at 200,000 in a separate call, while the delegated path stays at the same cost at every point.

## Recommendation

- The decision is scorable per call under the split, so a delegation results file on Longtail-SWE becomes possible: row E27, the first delegation file on agent runs on repository issues, with the split stated in its RESULTS.md as an assumption, after the README room rows. No results file, README or Limitations change in this note.
- What the split decides: each call's new input, which sets the decision's sizes and what the inline path's later turns re-read of the work. The held-out success and the run totals are measured; whether each call fits its window stays unverified.
