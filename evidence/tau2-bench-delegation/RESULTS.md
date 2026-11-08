# Delegation on tau2-bench: inline or sub-agent on held-out conversations

What the inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5) does on agent conversations it never saw, next to always working inline and always delegating, measured by `evaluate_delegation` (`DESIGN.md` 13.9) on the public [tau2-bench](https://github.com/sierra-research/tau2-bench) paper results at revision [`033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f`](https://github.com/sierra-research/tau2-bench/tree/033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f) (licence MIT, "Copyright (c) 2025 Sierra Research"). Each item is one customer-service conversation of an agent with a simulated user, labelled by the run's own program checks, and priced here on its own agent calls. The rows come from the converter described in [the tau2-bench evidence README](../tau2-bench/README.md), run with `--calls`; the agents' list prices and windows are in [registry.json](registry.json), with the vendor pages and the checks behind them in [the research note](../../research/delegation-datasets.md); the committed results are [results.json](results.json). Every cost is a list-price estimate, never a billed cost.

## Method

- Matrix: the converter's `--calls` output at trial 0, one task per domain (airline 50, retail 114, telecom 114 conversations), 3 agents and 834 rows. Each row is one agent's whole conversation on one item, with its success label (`reward_info.reward` of 1) and each of its agent calls' new input and output tokens (`DESIGN.md` 12.14); `openai/o4-mini-2025-04-16` is left out because its new input is negative on 2,962 of its calls (its reasoning is not re-read)
- Every agent is tried as the parent. For each of 50 seeds each domain's conversations are split in half by the seeded hash of `DESIGN.md` 12.2. The decision is made from the calibration half only, at bars 0.3 to 0.8 (the bars of [the tau2-bench routing results](../tau2-bench/RESULTS.md)) in both flavors, and scored on the held-out half. It forecasts the work as the calibration half's median call count (`expected_work_calls`: 10 to 12 on airline, 11 to 12 on retail, 17 to 19 on telecom) at each model's rounded-up mean new input and output per call (`DESIGN.md` 13.9 v1.74)
- Three strategies are scored on the same held-out conversations: `decision` (inline on the parent, or delegated to the decision's model), `inline` (the parent does every conversation itself) and `delegate` (every conversation goes to the routed delegate). Held-out success is the share of held-out conversations that passed, and held-out cost the list-price cost of the held-out half, each conversation priced on the calls of the model doing the work on each path; both are averaged over the seeds
- The grid is the four base points of [the AutoBench delegation results](../delegation/RESULTS.md), each with a 500-token brief (B), a 500-token result (R) and one later parent call that re-reads them (T = 1): points 0 to 2 put inline work in parent calls of their own with C = 8,000, 64,000 and 200,000 tokens of context the parent already holds, and point 3 (C = 8,000) folds inline work into the parent's next call instead (`inline_separate_call` False; `DESIGN.md` 13.2 prices the folded calls)
- Airline has 50 conversations, so at the default `min_samples` of 30 its calibration half is under 30 on 40 of the 50 seeds: no agent clears a bar there on those seeds, and every airline cell of them is 13.5 row 7 (`none_clear`) unless 13.4 blocks inline
- At point 2, C = 200,000 alone fills the assumed 200,000-token window of `anthropic/claude-3-7-sonnet-20250219`, so inline is blocked (`parent_context_full`) on all 1,800 of that parent's point 2 cells and on no other cell. The block follows from the assumed window
- Of the 10,800 `cost_effective` cells, 6,941 `none_clear`, 2,301 `delegate_cheaper`, 900 `parent_context_full` and 658 `parent_below_bar`. `none_clear` is 13.5 row 7: no agent clears the bar, so the calibration bounds decide, not cost. No cell is `inline_cheaper`
- A second run pools the three domains into one task (the converter's `--task-by all`: the same 834 rows as one task of 278 conversations) and writes [pooled.json](pooled.json) with the same script, registry, bars, points and seeds. Its calibration half holds 114 to 158 conversations over the 50 seeds, over `min_samples` on every seed, but a pooled bound mixes three kinds of job that the per-domain tasks keep apart, so the pooled run is a sensitivity of this reading, not its main result

## Assumed

- The lossless brief of `DESIGN.md` 13.9: the delegate is credited with its own whole conversation, as if a brief of B tokens carried what it needs, and the parent with its own as if C more tokens of context did not change it
- The first call's read, the system prompt with the domain policy and the tool schemas, is the work's own input on both paths, and B is the hand-off alone (`DESIGN.md` 13.9 v1.74)
- List price over-states the recorded costs of `openai/gpt-4.1-2025-04-14` 2.25 times and of `openai/gpt-4.1-mini-2025-04-14` 2.35 times (prompt caching, inferred from those costs in the research note) and those of `anthropic/claude-3-7-sonnet-20250219` 1.0 times, so every cost is a list-price estimate, and the gap between the two vendors' agents is about a factor of two wider than recorded
- `openai/o4-mini-2025-04-16` is left out, with its 2,962 negative new inputs
- The 200,000-token context window of `anthropic/claude-3-7-sonnet-20250219` is assumed: no current vendor page states it, and its prices are the ones its recorded costs give exactly
- Each conversation is read at trial 0 only. At trials 1 and 2 the converter also leaves out `openai/gpt-4.1-mini-2025-04-14`, so a trial sensitivity would compare 2 agents there; it is not run
- The agents are 2025 snapshots: the model pages list the two GPT-4.1 snapshots as Deprecated and o4-mini as Shut down, and Claude 3.7 Sonnet was retired on the Claude API on February 19, 2026. These prices only reprice their recorded runs
- Airline's calibration half is under `min_samples` on 40 of the 50 seeds (Method)
- The limits of `DESIGN.md` 13.8: each conversation's success is its one recorded reward, and the bar is held per call, not for a conversation's calls together

## Results

Means over the 3 parents. `dec_` is the decision, `inl_` always inline and `del_` always delegating; success is held-out success, cost the held-out half's list-price cost in USD, `delegated` the share of seeds on which the decision delegates, and `separate` whether inline work takes parent calls of its own (`True`) or folds into the next call (`False`). Inline does not depend on the bar or the flavor:

```text
$ python evidence/delegation/results.py --table evidence/tau2-bench-delegation/results.json
bar  flavor          context  separate  dec_success  dec_cost  inl_success  inl_cost  del_success  del_cost  delegated
---  --------------  -------  --------  -----------  --------  -----------  --------  -----------  --------  ---------
0.3  cost_effective  8000     True      0.550        19.8422   0.574        67.1856   0.550        19.8422   1.000
0.3  cost_effective  64000    True      0.550        19.8422   0.574        276.8994  0.550        19.8422   1.000
0.3  cost_effective  200000   True      0.550        19.8422   0.574        786.2041  0.550        19.8422   1.000
0.3  cost_effective  8000     False     0.550        19.8422   0.574        62.8021   0.550        19.8422   1.000
0.3  cost_blind      8000     True      0.589        62.3515   0.574        67.1856   0.591        48.9710   0.616
0.3  cost_blind      64000    True      0.589        161.3417  0.574        276.8994  0.591        48.9710   0.616
0.3  cost_blind      200000   True      0.589        114.3397  0.574        786.2041  0.591        48.9710   0.822
0.3  cost_blind      8000     False     0.589        60.2068   0.574        62.8021   0.591        48.9710   0.616
0.4  cost_effective  8000     True      0.548        26.9990   0.574        67.1856   0.548        26.9990   1.000
0.4  cost_effective  64000    True      0.548        26.9990   0.574        276.8994  0.548        26.9990   1.000
0.4  cost_effective  200000   True      0.548        26.9990   0.574        786.2041  0.548        26.9990   1.000
0.4  cost_effective  8000     False     0.548        26.9990   0.574        62.8021   0.548        26.9990   1.000
0.4  cost_blind      8000     True      0.589        62.3515   0.574        67.1856   0.591        48.9710   0.616
0.4  cost_blind      64000    True      0.589        161.3417  0.574        276.8994  0.591        48.9710   0.616
0.4  cost_blind      200000   True      0.589        114.3397  0.574        786.2041  0.591        48.9710   0.822
0.4  cost_blind      8000     False     0.589        60.2068   0.574        62.8021   0.591        48.9710   0.616
0.5  cost_effective  8000     True      0.550        28.2685   0.574        67.1856   0.550        28.2685   1.000
0.5  cost_effective  64000    True      0.550        28.2685   0.574        276.8994  0.550        28.2685   1.000
0.5  cost_effective  200000   True      0.550        28.2685   0.574        786.2041  0.550        28.2685   1.000
0.5  cost_effective  8000     False     0.550        28.2685   0.574        62.8021   0.550        28.2685   1.000
0.5  cost_blind      8000     True      0.589        62.3515   0.574        67.1856   0.591        48.9710   0.616
0.5  cost_blind      64000    True      0.589        161.3417  0.574        276.8994  0.591        48.9710   0.616
0.5  cost_blind      200000   True      0.589        114.3397  0.574        786.2041  0.591        48.9710   0.822
0.5  cost_blind      8000     False     0.589        60.2068   0.574        62.8021   0.591        48.9710   0.616
0.6  cost_effective  8000     True      0.570        38.1436   0.574        67.1856   0.570        38.1436   1.000
0.6  cost_effective  64000    True      0.570        38.1436   0.574        276.8994  0.570        38.1436   1.000
0.6  cost_effective  200000   True      0.570        38.1436   0.574        786.2041  0.570        38.1436   1.000
0.6  cost_effective  8000     False     0.570        38.1436   0.574        62.8021   0.570        38.1436   1.000
0.6  cost_blind      8000     True      0.589        62.3515   0.574        67.1856   0.591        48.9710   0.616
0.6  cost_blind      64000    True      0.589        161.3417  0.574        276.8994  0.591        48.9710   0.616
0.6  cost_blind      200000   True      0.589        114.3397  0.574        786.2041  0.591        48.9710   0.822
0.6  cost_blind      8000     False     0.589        60.2068   0.574        62.8021   0.591        48.9710   0.616
0.7  cost_effective  8000     True      0.586        43.4666   0.574        67.1856   0.586        43.4666   1.000
0.7  cost_effective  64000    True      0.586        43.4666   0.574        276.8994  0.586        43.4666   1.000
0.7  cost_effective  200000   True      0.586        43.4666   0.574        786.2041  0.586        43.4666   1.000
0.7  cost_effective  8000     False     0.586        43.4666   0.574        62.8021   0.586        43.4666   1.000
0.7  cost_blind      8000     True      0.589        62.3515   0.574        67.1856   0.591        48.9710   0.616
0.7  cost_blind      64000    True      0.589        161.3417  0.574        276.8994  0.591        48.9710   0.616
0.7  cost_blind      200000   True      0.589        114.3397  0.574        786.2041  0.591        48.9710   0.822
0.7  cost_blind      8000     False     0.589        60.2068   0.574        62.8021   0.591        48.9710   0.616
0.8  cost_effective  8000     True      0.586        43.7120   0.574        67.1856   0.586        43.7120   1.000
0.8  cost_effective  64000    True      0.586        43.7120   0.574        276.8994  0.586        43.7120   1.000
0.8  cost_effective  200000   True      0.586        43.7120   0.574        786.2041  0.586        43.7120   1.000
0.8  cost_effective  8000     False     0.586        43.7120   0.574        62.8021   0.586        43.7120   1.000
0.8  cost_blind      8000     True      0.589        62.3515   0.574        67.1856   0.591        48.9710   0.616
0.8  cost_blind      64000    True      0.589        161.3417  0.574        276.8994  0.591        48.9710   0.616
0.8  cost_blind      200000   True      0.589        114.3397  0.574        786.2041  0.591        48.9710   0.822
0.8  cost_blind      8000     False     0.589        60.2068   0.574        62.8021   0.591        48.9710   0.616
```

One row per (flavor, parent) at bar 0.3 and point 0:

```text
$ python evidence/delegation/results.py --table evidence/tau2-bench-delegation/results.json --bar 0.3 --point 0
flavor          parent                                delegated  dec_success  dec_cost  inl_success  inl_cost  del_success  del_cost
--------------  ------------------------------------  ---------  -----------  --------  -----------  --------  -----------  --------
cost_effective  anthropic/claude-3-7-sonnet-20250219  1.000      0.550        20.6437   0.612        124.3004  0.550        20.6437
cost_effective  openai/gpt-4.1-2025-04-14             1.000      0.550        19.8837   0.562        59.6628   0.550        19.8837
cost_effective  openai/gpt-4.1-mini-2025-04-14        1.000      0.550        18.9993   0.548        17.5937   0.550        18.9993
cost_blind      anthropic/claude-3-7-sonnet-20250219  0.380      0.591        86.8263   0.612        124.3004  0.591        49.7725
cost_blind      openai/gpt-4.1-2025-04-14             0.673      0.588        51.0936   0.562        59.6628   0.591        49.0125
cost_blind      openai/gpt-4.1-mini-2025-04-14        0.793      0.590        49.1346   0.548        17.5937   0.591        48.1281
```

The pooled run, means over the 3 parents:

```text
$ python evidence/delegation/results.py --table evidence/tau2-bench-delegation/pooled.json
bar  flavor          context  separate  dec_success  dec_cost  inl_success  inl_cost  del_success  del_cost  delegated
---  --------------  -------  --------  -----------  --------  -----------  --------  -----------  --------  ---------
0.3  cost_effective  8000     True      0.548        10.0668   0.574        67.1856   0.548        10.0668   1.000
0.3  cost_effective  64000    True      0.548        10.0668   0.574        276.8994  0.548        10.0668   1.000
0.3  cost_effective  200000   True      0.548        10.0668   0.574        786.2041  0.548        10.0668   1.000
0.3  cost_effective  8000     False     0.548        10.0668   0.574        62.8021   0.548        10.0668   1.000
0.3  cost_blind      8000     True      0.597        78.3064   0.574        67.1856   0.599        61.6818   0.647
0.3  cost_blind      64000    True      0.597        192.8724  0.574        276.8994  0.599        61.6818   0.647
0.3  cost_blind      200000   True      0.597        91.0208   0.574        786.2041  0.599        61.6818   0.940
0.3  cost_blind      8000     False     0.597        75.8335   0.574        62.8021   0.599        61.6818   0.647
0.4  cost_effective  8000     True      0.548        10.0668   0.574        67.1856   0.548        10.0668   1.000
0.4  cost_effective  64000    True      0.548        10.0668   0.574        276.8994  0.548        10.0668   1.000
0.4  cost_effective  200000   True      0.548        10.0668   0.574        786.2041  0.548        10.0668   1.000
0.4  cost_effective  8000     False     0.548        10.0668   0.574        62.8021   0.548        10.0668   1.000
0.4  cost_blind      8000     True      0.597        78.3064   0.574        67.1856   0.599        61.6818   0.647
0.4  cost_blind      64000    True      0.597        192.8724  0.574        276.8994  0.599        61.6818   0.647
0.4  cost_blind      200000   True      0.597        91.0208   0.574        786.2041  0.599        61.6818   0.940
0.4  cost_blind      8000     False     0.597        75.8335   0.574        62.8021   0.599        61.6818   0.647
0.5  cost_effective  8000     True      0.586        55.3235   0.574        67.1856   0.586        55.3235   1.000
0.5  cost_effective  64000    True      0.586        55.3235   0.574        276.8994  0.586        55.3235   1.000
0.5  cost_effective  200000   True      0.586        55.3235   0.574        786.2041  0.586        55.3235   1.000
0.5  cost_effective  8000     False     0.586        55.3235   0.574        62.8021   0.586        55.3235   1.000
0.5  cost_blind      8000     True      0.597        78.3064   0.574        67.1856   0.599        61.6818   0.647
0.5  cost_blind      64000    True      0.597        192.8724  0.574        276.8994  0.599        61.6818   0.647
0.5  cost_blind      200000   True      0.597        91.0208   0.574        786.2041  0.599        61.6818   0.940
0.5  cost_blind      8000     False     0.597        75.8335   0.574        62.8021   0.599        61.6818   0.647
0.6  cost_effective  8000     True      0.592        58.7867   0.574        67.1856   0.592        58.7867   1.000
0.6  cost_effective  64000    True      0.592        58.7867   0.574        276.8994  0.592        58.7867   1.000
0.6  cost_effective  200000   True      0.592        58.7867   0.574        786.2041  0.592        58.7867   1.000
0.6  cost_effective  8000     False     0.592        58.7867   0.574        62.8021   0.592        58.7867   1.000
0.6  cost_blind      8000     True      0.597        78.3064   0.574        67.1856   0.599        61.6818   0.647
0.6  cost_blind      64000    True      0.597        192.8724  0.574        276.8994  0.599        61.6818   0.647
0.6  cost_blind      200000   True      0.597        91.0208   0.574        786.2041  0.599        61.6818   0.940
0.6  cost_blind      8000     False     0.597        75.8335   0.574        62.8021   0.599        61.6818   0.647
0.7  cost_effective  8000     True      0.592        58.7867   0.574        67.1856   0.592        58.7867   1.000
0.7  cost_effective  64000    True      0.592        58.7867   0.574        276.8994  0.592        58.7867   1.000
0.7  cost_effective  200000   True      0.592        58.7867   0.574        786.2041  0.592        58.7867   1.000
0.7  cost_effective  8000     False     0.592        58.7867   0.574        62.8021   0.592        58.7867   1.000
0.7  cost_blind      8000     True      0.597        78.3064   0.574        67.1856   0.599        61.6818   0.647
0.7  cost_blind      64000    True      0.597        192.8724  0.574        276.8994  0.599        61.6818   0.647
0.7  cost_blind      200000   True      0.597        91.0208   0.574        786.2041  0.599        61.6818   0.940
0.7  cost_blind      8000     False     0.597        75.8335   0.574        62.8021   0.599        61.6818   0.647
0.8  cost_effective  8000     True      0.592        58.7867   0.574        67.1856   0.592        58.7867   1.000
0.8  cost_effective  64000    True      0.592        58.7867   0.574        276.8994  0.592        58.7867   1.000
0.8  cost_effective  200000   True      0.592        58.7867   0.574        786.2041  0.592        58.7867   1.000
0.8  cost_effective  8000     False     0.592        58.7867   0.574        62.8021   0.592        58.7867   1.000
0.8  cost_blind      8000     True      0.597        78.3064   0.574        67.1856   0.599        61.6818   0.647
0.8  cost_blind      64000    True      0.597        192.8724  0.574        276.8994  0.599        61.6818   0.647
0.8  cost_blind      200000   True      0.597        91.0208   0.574        786.2041  0.599        61.6818   0.940
0.8  cost_blind      8000     False     0.597        75.8335   0.574        62.8021   0.599        61.6818   0.647
```

`cost_effective` reasons per bar in each run, counted from in-process runs that keep the cells (neither results file keeps them; a test rebuilds this table when the pinned files are cached):

| bar | run | cells | `none_clear` | `delegate_cheaper` | `parent_context_full` | `parent_below_bar` |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| 0.3 | per domain | 1,800 | 561 | 892 | 150 | 197 |
| 0.3 | pooled | 600 | 0 | 550 | 50 | 0 |
| 0.4 | per domain | 1,800 | 1,001 | 584 | 150 | 65 |
| 0.4 | pooled | 600 | 0 | 550 | 50 | 0 |
| 0.5 | per domain | 1,800 | 1,100 | 514 | 150 | 36 |
| 0.5 | pooled | 600 | 176 | 132 | 50 | 242 |
| 0.6 | per domain | 1,800 | 1,111 | 271 | 150 | 268 |
| 0.6 | pooled | 600 | 550 | 0 | 50 | 0 |
| 0.7 | per domain | 1,800 | 1,518 | 40 | 150 | 92 |
| 0.7 | pooled | 600 | 550 | 0 | 50 | 0 |
| 0.8 | per domain | 1,800 | 1,650 | 0 | 150 | 0 |
| 0.8 | pooled | 600 | 550 | 0 | 50 | 0 |
| all | per domain | 10,800 | 6,941 | 2,301 | 900 | 658 |
| all | pooled | 3,600 | 1,826 | 1,232 | 300 | 242 |

## Reading it

- In `cost_effective` the decision delegates on every seed for every parent at every bar and point (`delegate_rate` 1.0 on all 72 decision rows).
- At bar 0.3 and point 0 (8,000 context tokens), averaged over the 3 parents, the `cost_effective` decision costs 19.8422 USD on a held-out half against 67.1856 for always inline (3.39 times as much), with held-out success 0.550 against 0.574.
- At that bar and point the `cost_effective` decision costs more than always inline for `openai/gpt-4.1-mini-2025-04-14` (18.9993 against 17.5937).
- `results.json` is 132,475 bytes.
- Pooled, the `cost_effective` decision again delegates on every seed for every parent at every bar and point; at bar 0.3 and point 0, averaged over the 3 parents, it costs 10.0668 USD on a held-out half against 19.8422 per domain, with held-out success 0.548 against 0.550. Always inline has the same held-out success and cost in both runs, since the split reads only the seed and the item ID (`DESIGN.md` 12.2).
- The cost comparison (`DESIGN.md` 13.5 row 3: both paths clear the bar, so their costs are compared) is reached on 2,301 of the 10,800 `cost_effective` cells per domain (21.3%) and on 1,232 of the 3,600 pooled (34.2%); no cell of either run is `inline_cheaper`.
- `pooled.json` is 126,695 bytes.

## Regenerate

The converter downloads the 12 pinned run files into a cache outside the repo and checks each one's size and SHA-256 before reading it (see [the tau2-bench evidence README](../tau2-bench/README.md)); the matrix it writes is not committed.

```bash
python -m pip install -e .
python evidence/tau2-bench/convert.py --out tau2-calls.jsonl --calls
python evidence/tau2-bench-delegation/results.py --matrix tau2-calls.jsonl --registry evidence/tau2-bench-delegation/registry.json --out evidence/tau2-bench-delegation/results.json
python evidence/delegation/results.py --table evidence/tau2-bench-delegation/results.json
python evidence/delegation/results.py --table evidence/tau2-bench-delegation/results.json --bar 0.3 --point 0
```

The pooled run:

```bash
python evidence/tau2-bench/convert.py --out tau2-calls-all.jsonl --calls --task-by all
python evidence/tau2-bench-delegation/results.py --matrix tau2-calls-all.jsonl --registry evidence/tau2-bench-delegation/registry.json --out evidence/tau2-bench-delegation/pooled.json
python evidence/delegation/results.py --table evidence/tau2-bench-delegation/pooled.json
```
