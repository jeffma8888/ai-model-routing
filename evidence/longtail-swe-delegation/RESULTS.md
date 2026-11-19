# Delegation on Longtail-SWE: inline or sub-agent on held-out agent runs, per call

What the inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5) does on issues it never saw, next to always working inline and always delegating, measured by `evaluate_delegation` (`DESIGN.md` 13.9) on the public [nebius/Longtail-SWE-trajectories](https://huggingface.co/datasets/nebius/Longtail-SWE-trajectories) at revision [`dfd6075c56b7841b9c254cc70a57e39c1df0076c`](https://huggingface.co/datasets/nebius/Longtail-SWE-trajectories/tree/dfd6075c56b7841b9c254cc70a57e39c1df0076c) (last modified 2026-11-16), the first delegation evidence whose items are agent runs on issues of open-source repositories. Each item is one issue, which each of the four registry models, `anthropic/claude-opus-5.5`, `openai/gpt-5.6-luna`, `openai/gpt-5.6-sol` and `openai/gpt-6.1-sol`, worked in one run of many model calls by the release's `swelike` scaffold, a success when the run's saved evaluation marks the issue `resolved`. The release records each run's token totals, not each call's, so each run is split into its model calls by a stated rule, an assumption (Assumed), from [longtail-per-call.md](../../research/longtail-per-call.md); the brief and result sizes come from [longtail-delegation.md](../../research/longtail-delegation.md). The matrix is the one of [the Longtail-SWE routing results](../longtail-swe/RESULTS.md), read through the converter described in [the Longtail-SWE evidence README](../longtail-swe/README.md); the models' list prices are this checkout's registry, `model_routing/data/models.json`; the committed results are [results.json](results.json). Every cost is a list-price estimate, never a billed cost.

Licence: the dataset card at the pinned revision has `license: cc-by-4.0` and says the dataset compilation is licensed under CC BY 4.0, while source repositories keep their own licences and model outputs may be subject to provider terms; [the Longtail-SWE routing results](../longtail-swe/RESULTS.md) quote the card and its LEGAL.md. Attribution, as CC BY 4.0 (https://creativecommons.org/licenses/by/4.0/) asks: these results derive from Longtail-SWE Trajectories by Nebius, nebius/Longtail-SWE-trajectories at revision `dfd6075c56b7841b9c254cc70a57e39c1df0076c`, licensed under CC BY 4.0. Changes made: the script reads, per run of the four registry models, the converter's columns and, as counts only, the lengths of the run's user prompt and of its patch, the token totals, the model-call count and the number of the run's events and messages that carry a usage record, a count the research note reports and `results.json` does not keep; it reads all three runs and keeps run 0, dropping the issues whose initial statement changed, as the converter does; it splits each run's totals into its model calls by the rule below; and `evaluate_delegation` turns those rows into the mean results below. The card asks to cite the paper [Longtail-SWE: High-Quality SWE Tasks for Underrepresented Languages](https://arxiv.org/abs/2611.10304). This repo commits no part of the dataset: `results.json` holds only the run's settings, item counts, the split's counts and mean results, and no statement, message, patch or trajectory text.

## Method

- Matrix: the converter's 12.26 matrix, the one the routing results read: the 4 models on 194 issues of one task, `issue_resolution`, at run 0 of the release's three runs per issue and model, so 776 rows; the converter drops the 8 issues whose initial statement differs from the release's (`DESIGN.md` 12.25, 12.26)
- Split: a run of K model calls (`usage.model_calls`), input total I and output total O gives call j the output O // K, call 1 also O % K, and each call the same new input, the remainder on the first and last calls, so that the K calls, each re-reading every earlier call's new input and output, read I and write O, as the per-call mode of `DESIGN.md` 13.9 (v1.74) checks (`DESIGN.md` 13.16 v1.496). A run whose input is below its outputs' re-reads would be refused and its issue dropped for all four models: on the pinned files 0 runs refused, so no issue is dropped and all 776 rows are scored
- Each of the 4 models is tried as the parent, at the registry's prices, `anthropic/claude-opus-5.5` at 4 and 20, `openai/gpt-5.6-luna` at 0.2 and 1.2, `openai/gpt-5.6-sol` at 4 and 20 and `openai/gpt-6.1-sol` at 2 and 10 USD per 1M input and output tokens; the delegate is the `DESIGN.md` 13.3 pick among the four, which may be the parent's own model
- For each of 50 seeds the 194 issues are split in half by the seeded hash of `DESIGN.md` 12.2, as the routing results split them
- The decision is made from the calibration half only, at bars 0.7 and 0.8, the per-call note's, in both flavors, and scored on the held-out half: at bar 0.7 it is below the bar on 48 of 800 cells per flavor, and at 0.8 on 736 of 800, so the file shows it both where models clear and where the below-bar rule of `DESIGN.md` 13.5 decides nearly every cell (`DESIGN.md` 13.18). It forecasts each path at a model's rounded-up mean new input and output a call on the calibration half, with the median call count as its work calls, and prices each held-out item on its own calls, each path at the calls of the model doing the work (`DESIGN.md` 13.9, v1.74)
- Three strategies are scored on the same held-out items: `decision` (inline on the parent, or delegated to the decision's model), `inline` (the parent does every item itself) and `delegate` (every item goes to the routed delegate). Held-out success is the share of held-out issues resolved, and held-out cost the list-price cost of the held-out half; both are averaged over the seeds
- The grid is the four points of the research note: a brief (B) of 1,244 tokens and a result (R) of 4,863, the lower medians over the 776 rows of the run's user prompt and of its patch, at characters over 4, rounded up, and one later parent call that re-reads them (T = 1); points 0 to 2 put inline work in parent calls of their own with C = 8,000, 64,000 and 200,000 tokens of context the parent already holds, and point 3 (C = 8,000) folds inline work into the parent's next call instead (`inline_separate_call` False; `DESIGN.md` 13.2 prices the folded calls)

## Assumed

- The split is an assumption the release cannot check: the release holds each run's totals only, so each call's new input and output, and with them the decision's sizes and what the inline path's later calls re-read of the parent's context, are the rule's, not measured ([longtail-per-call.md](../../research/longtail-per-call.md)); each run's success and token totals are measured
- The lossless brief of `DESIGN.md` 13.9: the delegate is credited with its own recorded run, as if a brief of B tokens carried what it needs, and the parent with its own as if C more tokens of context did not change it
- Every cost is a list price of the registry with no cache discount: a run's input tokens, cached ones included, at the input price and its output tokens at the output price (`DESIGN.md` 12.25), an estimate and never a bill
- No call's context window is checked: under the split a run's last call reads and writes a median 128,148 tokens, over its model's window on 1 of the 776 rows, and a run's largest real call may be larger than the split's (the research note)
- The file holds one task of 194 issues, at run 0 alone, so each seed's two halves split one pool, as in the routing results
- The limits of `DESIGN.md` 13.8: each item's success is its one recorded label, and the bar is held per call

## Results

Means over the 4 parents. `dec_` is the decision, `inl_` always inline and `del_` always delegating; success is held-out success, cost the held-out half's list-price cost in USD, `delegated` the share of seeds on which the decision delegates, and `separate` whether inline work takes parent calls of its own (`True`) or folds into the next call (`False`). Inline does not depend on the bar or the flavor:

```text
$ python evidence/delegation/results.py --table evidence/longtail-swe-delegation/results.json
bar  flavor          context  separate  dec_success  dec_cost   inl_success  inl_cost   del_success  del_cost   delegated
---  --------------  -------  --------  -----------  ---------  -----------  ---------  -----------  ---------  ---------
0.7  cost_effective  8000     True      0.812        1068.8712  0.788        1020.8487  0.812        1068.8712  1.000
0.7  cost_effective  64000    True      0.812        1068.8712  0.788        1587.2592  0.812        1068.8712  1.000
0.7  cost_effective  200000   True      0.812        1068.8712  0.788        2962.8275  0.812        1068.8712  1.000
0.7  cost_effective  8000     False     0.812        1068.8712  0.788        986.2884   0.812        1068.8712  1.000
0.7  cost_blind      8000     True      0.830        1752.6070  0.788        1020.8487  0.832        1735.5015  0.720
0.7  cost_blind      64000    True      0.830        2044.3916  0.788        1587.2592  0.832        1735.5015  0.720
0.7  cost_blind      200000   True      0.830        2753.0114  0.788        2962.8275  0.832        1735.5015  0.720
0.7  cost_blind      8000     False     0.830        1739.0279  0.788        986.2884   0.832        1735.5015  0.720
0.8  cost_effective  8000     True      0.823        1568.4337  0.788        1020.8487  0.823        1568.4337  1.000
0.8  cost_effective  64000    True      0.823        1568.4337  0.788        1587.2592  0.823        1568.4337  1.000
0.8  cost_effective  200000   True      0.823        1568.4337  0.788        2962.8275  0.823        1568.4337  1.000
0.8  cost_effective  8000     False     0.823        1568.4337  0.788        986.2884   0.823        1568.4337  1.000
0.8  cost_blind      8000     True      0.830        1752.6070  0.788        1020.8487  0.832        1735.5015  0.720
0.8  cost_blind      64000    True      0.830        2044.3916  0.788        1587.2592  0.832        1735.5015  0.720
0.8  cost_blind      200000   True      0.830        2753.0114  0.788        2962.8275  0.832        1735.5015  0.720
0.8  cost_blind      8000     False     0.830        1739.0279  0.788        986.2884   0.832        1735.5015  0.720
```

Per parent at bar 0.7 and point 0:

```text
$ python evidence/delegation/results.py --table evidence/longtail-swe-delegation/results.json --bar 0.7 --point 0
flavor          parent                     delegated  dec_success  dec_cost   inl_success  inl_cost   del_success  del_cost
--------------  -------------------------  ---------  -----------  ---------  -----------  ---------  -----------  ---------
cost_effective  anthropic/claude-opus-5.5  1.000      0.812        1071.4457  0.837        2008.7193  0.812        1071.4457
cost_effective  openai/gpt-5.6-luna        1.000      0.812        1064.7072  0.726        274.7569   0.812        1064.7072
cost_effective  openai/gpt-5.6-sol         1.000      0.812        1071.4457  0.787        1358.4070  0.812        1071.4457
cost_effective  openai/gpt-6.1-sol         1.000      0.812        1067.8864  0.804        441.5115   0.812        1067.8864
cost_blind      anthropic/claude-opus-5.5  0.040      0.832        1959.4985  0.837        2008.7193  0.832        1738.0759
cost_blind      openai/gpt-5.6-luna        1.000      0.832        1731.3374  0.726        274.7569   0.832        1731.3374
cost_blind      openai/gpt-5.6-sol         0.980      0.832        1741.8097  0.787        1358.4070  0.832        1738.0759
cost_blind      openai/gpt-6.1-sol         0.860      0.823        1577.7822  0.804        441.5115   0.832        1734.5167
```

## Reading it

- In `cost_effective` the decision delegates on every seed for every parent at points 0 to 2 at every bar (`delegate_rate` 1.0 on all 24 of their decision rows); at point 3, the work folded into the parent's next call, its rate averaged over the 4 parents is 1.000 and 1.000 at bars 0.7 and 0.8.
- At bar 0.7 and point 0 (8,000 context tokens), averaged over the 4 parents, the `cost_effective` decision costs 1068.8712 USD on a held-out half against 1020.8487 for always inline (so the decision costs 1.05 times as much), with held-out success 0.812 against 0.788.
- At bar 0.8 and point 0 it costs 1568.4337 USD against 1020.8487 for always inline, with held-out success 0.823 against 0.788.
- At bar 0.7 and point 0 the `cost_effective` decision costs more than always inline for 2 of the 4 parents: `openai/gpt-5.6-luna` (1064.7072 against 274.7569 USD, held-out success 0.812 against 0.726) and `openai/gpt-6.1-sol` (1067.8864 against 441.5115 USD, held-out success 0.812 against 0.804).
- `results.json` is 55,416 bytes.

## Regenerate

The script calls the converter's `fetch`, which downloads the four pinned files (236,605,401 bytes) into `~/.cache/ai-model-routing-evidence/longtail-swe/` when they are absent and checks each against its pinned size and sha256 (`DESIGN.md` 12.25), and reads them with `pyarrow`, which the `evidence` extra installs; it writes no matrix file. With the files cached it runs in about 9 seconds. The `evidence` workflow does not rerun this script yet, so only the test suite rebuilds `results.json`, where `pyarrow` is installed and the four files are cached.

```bash
python -m pip install -e ".[evidence]"
python evidence/longtail-swe-delegation/results.py --out evidence/longtail-swe-delegation/results.json
python evidence/delegation/results.py --table evidence/longtail-swe-delegation/results.json
python evidence/delegation/results.py --table evidence/longtail-swe-delegation/results.json --bar 0.7 --point 0
```
