# Longtail-SWE as delegation evidence (2026-11-19)

## Facts

- Question: none of the five delegation results files holds an agent run on a repository issue. Can nebius/Longtail-SWE-trajectories, whose runs record their token totals, the statement they start from and the patch they end with, score the inline-or-sub-agent decision (DESIGN 13.5) with each registry model as the parent and the four as the delegate pool?
- Data: nebius/Longtail-SWE-trajectories at revision dfd6075c56b7841b9c254cc70a57e39c1df0076c (CC BY 4.0), the four pinned files of the converter `evidence/longtail-swe/convert.py` (12.25), read outside the repo; of each run only counts are kept (the characters of its user prompt and its patch, its model calls, its token totals and its events with a usage record), and no statement, message or patch is printed, kept or committed
- Script: [longtail_delegation.py](longtail_delegation.py), `python research/longtail_delegation.py` (it needs `pyarrow`, the `evidence` extra); tests/test_research_longtail_delegation.py checks the block against a fresh run where the files are cached
- Short answer: not as the 13.9 harness reads a row. A run's token totals sum its model calls (median 38), so its input plus output is over the model's window on 111 to 186 of each model's 194 rows, the harness refuses the one-call rows at its first cell, and the release records no per-call tokens (0 usage or tokens keys on its events). The brief and the result can be sized from the data: a median 1,244 and 4,863 tokens at characters over 4, rounded up

## Method

The converter's `fetch`, `run_records` and `convert` give the 12.26 matrix (run 0, the issues whose statement matches the release, the four registry models), and the script gives each row the input and output totals of its run's `usage.tokens`. A size in tokens is its characters over 4, rounded up, the ratio `research/livecodebench-cost.md` uses for English text (code tokenizes differently, and differently per vendor). The brief is the run's one `user` prompt, the statement the run starts from, and the result its `model_patch`; the points take their `median_low` over the matrix's rows. `model_routing.evaluate_delegation` then runs at bars 0.7 and 0.8, with the seeds, flavors, calibration fraction, `min_samples` and confidence of `evidence/longtail-swe/results.json`, at contexts 8,000, 64,000 and 200,000 in a separate inline call and 8,000 folded into the next call, carry turns 1. The block is the script's output.

## Results

```text
nebius/Longtail-SWE-trajectories at dfd6075: the 12.26 matrix (run 0, 194 items, 4 models, 776 rows) as delegation evidence
Sizes over the 776 rows, tokens = characters / 4, rounded up
  brief, the run's user prompt: median 1,244, 10th to 90th percentile 698 to 2,319
  result, the run's model_patch: median 4,863, 10th to 90th percentile 1,054 to 13,870; 1 empty
  run input tokens: median 2,568,100, 10th to 90th percentile 560,972 to 12,625,225
  run output tokens: median 24,803, 10th to 90th percentile 12,219 to 59,980
  model calls a run: median 38, 10th to 90th percentile 18 to 90
  usage or tokens keys on events or their messages, all 2,424 runs of the four files: 0
Context window against each run's input plus output
model                      window      over  median input  median calls  median input a call
anthropic/claude-opus-5.5  1,000,000  154 of 194     2,805,515            48               57,075
openai/gpt-5.6-luna        1,050,000  186 of 194     8,773,667            69              127,155
openai/gpt-5.6-sol         1,050,000  149 of 194     2,162,868            32               64,430
openai/gpt-6.1-sol         1,050,000  111 of 194     1,189,593            25               47,651
13.9 harness, each row one call of its run's totals, bars 0.7 0.8, 50 seeds, points (carry turns 1, brief 1,244, result 4,863): 0 context 8,000 separate; 1 context 64,000 separate; 2 context 200,000 separate; 3 context 8,000 folded
  refused: no model fits the delegated work: task 'issue_resolution', parent 'anthropic/claude-opus-5.5', point 0
```

## Reading it

- The brief and the result: by the characters-over-4 rule the user prompt is a median 1,244 tokens (10th to 90th percentile 698 to 2,319) and the patch a median 4,863 (1,054 to 13,870), with 1 empty patch, sizes the delegation results files state as assumptions instead.
- A run is many calls: a median 38 model calls (18 to 90), whose summed reads make its input total a median 2,568,100 tokens (560,972 to 12,625,225), against a median 24,803 output tokens.
- Read as one call, the work does not fit: a run's input plus output is over its model's 4.1 context window, 1,000,000 or 1,050,000 tokens, on 154 (`anthropic/claude-opus-5.5`), 186 (`openai/gpt-5.6-luna`), 149 (`openai/gpt-5.6-sol`) and 111 (`openai/gpt-6.1-sol`) of 194 rows. The harness reads a row without per-call sizes as one call, and its context checks read the calibration half's median input and output as that call's sizes (13.9), medians of run totals like the 2,568,100 above, so 13.4 blocks inline and 13.3 finds no delegate whose window holds the work, and it refuses at its first cell (parent `anthropic/claude-opus-5.5`, point 0).
- Per call the sizes are far smaller, but whether each call fits is unknown: a run's input over its model calls has a median of 47,651 to 127,155 tokens by model, a mean per call, which says nothing of a run's largest call or of its last call's read, the one 13.4 checks. The harness's per-call mode (13.9 v1.74) prices and checks work call by call but needs each call's input and output, and the release holds each run's totals only: 0 of the events, or of their messages, carry a usage or tokens key, over all 2,424 runs of the four files.

## Recommendation

- No results file and no README or Limitations change now: the decision is not scored, so there is no finding to state.
- Row R50b: score the decision per call, under a stated split of each run's totals into its model calls that the 13.2 per-call rule accepts (call j reads the inputs and outputs of the calls before it), specified in DESIGN first; the brief and result sizes above carry over. A split is an assumption, not a measurement, so whether a call fits its window stays unverified under it too. A delegation results file would follow only if that scores the decision.
