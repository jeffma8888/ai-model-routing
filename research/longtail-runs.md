# Longtail-SWE runs 0, 1 and 2 (2026-11-18)

## Facts

- Question: the release holds three agent runs per (issue, model), and `evidence/longtail-swe/results.json` (DESIGN 12.26) is run 0 alone. How far does one run's luck move the routed numbers?
- Data: nebius/Longtail-SWE-trajectories at revision dfd6075c56b7841b9c254cc70a57e39c1df0076c (CC BY 4.0), the four pinned files of the converter `evidence/longtail-swe/convert.py` (12.25), read outside the repo; nothing of the dataset is committed but the counts and rates below
- Script: [longtail_runs.py](longtail_runs.py), `python research/longtail_runs.py` (it needs `pyarrow`, the `evidence` extra); its run 0 is the committed results file byte for byte (tests/test_research_longtail_runs.py)
- Short answer: more than the bar does between its two lowest steps. Run 0 is the luckiest of the three for routing, and on runs 1 and 2 the routed `cost_effective` row at 0.7 clears fewer seeds, more of them under the bar

## Method

For each run the converter builds the 12.25 matrix (the same 194 issues of one task, the 4 registry models, an unscored run a miss that keeps its charge), and `model_routing.evaluate` scores it with the 12.26 config: bars 0.6, 0.7, 0.8 and 0.9, 50 seeds, both flavors, `evidence/routerbench/results.py` reducing the result. The block is the script's output.

## Results

```text
Runs 0, 1 and 2, each the 12.25 matrix (194 items, 4 models) under the 12.26 config (bars 0.6 0.7 0.8 0.9, 50 seeds, both flavors)

Resolved per model (unscored runs, a miss that keeps its charge, in brackets)
run  anthropic/claude-opus-5.5  openai/gpt-5.6-luna  openai/gpt-5.6-sol  openai/gpt-6.1-sol
0    162 (0)                    140 (0)              152 (0)             155 (1)
1    155 (0)                    140 (0)              146 (0)             151 (1)
2    156 (0)                    138 (0)              145 (0)             149 (2)

Each model alone, held-out success and cost in USD over 50 seeds (bar 0.6, cost_effective)
run  model                       success     cost
0    anthropic/claude-opus-5.5     0.837  1745.31
0    openai/gpt-5.6-luna           0.726   252.57
0    openai/gpt-5.6-sol            0.787  1143.62
0    openai/gpt-6.1-sol            0.804   357.50
1    anthropic/claude-opus-5.5     0.801  1776.40
1    openai/gpt-5.6-luna           0.724   263.49
1    openai/gpt-5.6-sol            0.755  1094.06
1    openai/gpt-6.1-sol            0.783   351.22
2    anthropic/claude-opus-5.5     0.807  1761.14
2    openai/gpt-5.6-luna           0.717   247.54
2    openai/gpt-5.6-sol            0.746  1133.34
2    openai/gpt-6.1-sol            0.773   350.28

best_on_calibration (the same at every bar and flavor)
run  success     cost
0      0.823  1541.05
1      0.775  1341.31
2      0.793  1603.24

Routed
run  bar  flavor          success     cost cleared below_bar violation
0    0.6  cost_effective    0.740   278.72   1.000     0.000     0.000
0    0.6  cost_blind        0.832  1705.82   1.000     0.000     0.000
0    0.7  cost_effective    0.805  1005.68   0.940     0.020     0.021
0    0.7  cost_blind        0.832  1705.82   0.940     0.000     0.000
0    0.8  cost_effective    0.823  1541.05   0.080     0.260     1.000
0    0.8  cost_blind        0.832  1705.82   0.080     0.160     1.000
0    0.9  cost_effective    0.823  1541.05   0.000     0.980         -
0    0.9  cost_blind        0.832  1705.82   0.000     0.980         -
1    0.6  cost_effective    0.733   282.32   1.000     0.000     0.000
1    0.6  cost_blind        0.782  1527.19   1.000     0.000     0.000
1    0.7  cost_effective    0.772  1041.60   0.640     0.020     0.031
1    0.7  cost_blind        0.782  1527.19   0.640     0.020     0.031
1    0.8  cost_effective    0.775  1341.31   0.000     0.780         -
1    0.8  cost_blind        0.782  1527.19   0.000     0.700         -
1    0.9  cost_effective    0.775  1341.31   0.000     1.000         -
1    0.9  cost_blind        0.782  1527.19   0.000     1.000         -
2    0.6  cost_effective    0.730   292.20   1.000     0.000     0.000
2    0.6  cost_blind        0.800  1702.86   1.000     0.000     0.000
2    0.7  cost_effective    0.783  1334.84   0.680     0.120     0.176
2    0.7  cost_blind        0.800  1702.86   0.680     0.040     0.059
2    0.8  cost_effective    0.793  1603.24   0.020     0.480     1.000
2    0.8  cost_blind        0.800  1702.86   0.020     0.420     1.000
2    0.9  cost_effective    0.793  1603.24   0.000     1.000         -
2    0.9  cost_blind        0.800  1702.86   0.000     1.000         -

Routed spread over runs 0 to 2: lowest to highest
bar  flavor          success        cost              violation
0.6  cost_effective  0.730 to 0.740  278.72 to 292.20  0.000 to 0.000
0.6  cost_blind      0.782 to 0.832  1527.19 to 1705.82  0.000 to 0.000
0.7  cost_effective  0.772 to 0.805  1005.68 to 1334.84  0.021 to 0.176
0.7  cost_blind      0.782 to 0.832  1527.19 to 1705.82  0.000 to 0.059
0.8  cost_effective  0.775 to 0.823  1341.31 to 1603.24  1.000 to 1.000
0.8  cost_blind      0.782 to 0.832  1527.19 to 1705.82  1.000 to 1.000
0.9  cost_effective  0.775 to 0.823  1341.31 to 1603.24  -
0.9  cost_blind      0.782 to 0.832  1527.19 to 1705.82  -
```

## Reading it

- Routed `cost_effective` at 0.7 is at 0.805 success for 1005.68 on run 0, but 0.772 to 0.805 for 1005.68 to 1334.84 over the three runs; its cleared rate falls from 0.940 to 0.640 and 0.680, and its bar-violation rate rises from 0.021 to 0.031 and 0.176. One run moves the routed row about as much as the step from bar 0.6 to 0.7 does.
- Every model resolves fewer issues after run 0: `anthropic/claude-opus-5.5` 162, then 155 and 156; `openai/gpt-6.1-sol` 155, then 151 and 149, so alone it is at 0.804, 0.783 and 0.773 held out, for 357.50, 351.22 and 350.28. On run 1 it beats routed `cost_effective` at 0.7 (0.783 against 0.772, for 351.22 against 1041.60); on run 2 routing is ahead, 0.783 against 0.773, for 1334.84 against 350.28.
- At 0.8 the cleared rate is 0.080, 0.000 and 0.020, and on runs 0 and 2 every cleared cell is under its bar (violation 1.000), so the 12.26 complementary-halves finding holds on each run that clears a cell at all.
- `cost_blind` is at 0.782 to 0.832 for 1527.19 to 1705.82, above `best_on_calibration` on every run (0.823, 0.775 and 0.793).
- The unscored runs are 1, 1 and 2, all `openai/gpt-6.1-sol`.

## Limits

- The three runs are three agent attempts on the same 194 issues, not new issues, so they show run-to-run noise, not how the numbers generalize
- One task and one pool per run: each seed's two halves split the same items (12.26), so the 50 seeds of a run are not independent
- The cost is each run's tokens at the registry's list prices with no cache discount, an estimate and not a bill (12.25)
