# What a fallback on a failed check buys on LLMRouterBench

The executor tries a route's models in turn and moves to the next one when the caller's `validate` check fails ([DESIGN.md](../DESIGN.md), Execution with fallback), and a router fills the route with the next `max_fallbacks` models of the list it sorts (5.3). No committed results row measures that move: each routed row scores the primary alone, and on LLMRouterBench [the committed results](../evidence/llmrouterbench/RESULTS.md) put the per-item oracle well above every routed row, a gap they put down to routing per benchmark, not per prompt. LLMRouterBench records every pool model on every item, so a check-driven fallback can be replayed exactly. This note does that, and its numbers are the output of [check_fallback.py](check_fallback.py), which stops unless the replay with no fallback is the committed routed row.

## Facts

- Every number here is an upper bound: the replay's check is the record's own score, a check that never passes a wrong answer or fails a right one, while a caller's check at call time can only do worse, and on every task but `arenahard` and `livecodebench` the score is made against an answer key a caller does not hold
- Data: the 12.18 matrix, 9 tasks, 13 models and 12,066 items, with the committed config at bars 0.1 and 0.8, the lowest and highest of 8, and 50 seeds; the oracle reaches 0.8207 at 33.6900
- Two fallbacks, the `max_fallbacks` of every packaged task: `cost_blind` success rises from 0.6147 to 0.7542 at bar 0.1 and to 0.7500 at bar 0.8, recovering 0.678 and 0.657 of the gap to the oracle, at 2.069 and 2.009 times the cost; `cost_effective` from 0.5528 to 0.6803 at bar 0.1 (0.476 of the gap, 3.522 times the cost) and from 0.6060 to 0.7470 at bar 0.8 (0.657, 2.063 times)
- Every listed model: success 0.8056 at bar 0.1 and 0.8120 at bar 0.8 in both flavors, 0.927 to 0.960 of the gap, at 2.454 to 8.772 times the cost of no fallback and 2.758 to 3.511 attempts per item
- When a model clears the bar the list holds only the models that clear it (5.3), so at bar 0.8 the whole list falls short of the oracle on the four tasks where some model clears it on some seed, `aime`, `gpqa`, `livecodebench` and `mmlupro`, and reaches it on the five where none does and the route holds all 13 models; on `livecodebench`, with routes of 1 to 2 models, success moves only from 0.8634 to 0.8641, against an oracle of 0.9200
- `arenahard`, the one task whose score needs no answer key, gains the most at bar 0.8: from 0.6576 in `cost_effective` and 0.6581 in `cost_blind` to 0.9768, the oracle's, with every listed model

## Checks per task

Each record keeps only its score; how the score was made is read from the scoring code in the dataset's code repository at the commit linked, the evaluator for each benchmark.

| task | how the record's score is made | a check at call time without the answer key |
|---|---|---|
| `aime` | the final answer in the output, graded against the reference answer by a math-equivalence test ([aime.py](https://github.com/ynulihao/LLMRouterBench/blob/811df08b1b37646064eeb8cb6acfd498bf99885a/evaluation/AIME/aime.py)) | no: the test needs the reference answer |
| `arc-agi` | the output grids, matched cell for cell with the expected test grids ([arc_agi.py](https://github.com/ynulihao/LLMRouterBench/blob/811df08b1b37646064eeb8cb6acfd498bf99885a/evaluation/ARC_AGI/arc_agi.py)) | no: the match needs the expected grids |
| `arenahard` | a judge model compares the answer with a baseline model's answer, twice with the order swapped, and scores it `1` when better, `0.5` when level and `0` when worse, a `0.5` counting as a miss here (12.18) ([arenahard.py](https://github.com/ynulihao/LLMRouterBench/blob/811df08b1b37646064eeb8cb6acfd498bf99885a/evaluation/ArenaHard/arenahard.py)) | yes, at a price: a baseline answer and two judge calls per attempt, and the judge's errors are the check's |
| `gpqa` | the option letter the output names, compared with the key ([gpqa.py](https://github.com/ynulihao/LLMRouterBench/blob/811df08b1b37646064eeb8cb6acfd498bf99885a/evaluation/GPQA/gpqa.py)) | no: only a format check, that a letter is named |
| `hle` | a grader model compares the output's final answer with the reference answer ([hle.py](https://github.com/ynulihao/LLMRouterBench/blob/811df08b1b37646064eeb8cb6acfd498bf99885a/evaluation/HLE/hle.py)) | no: the grader is given the reference answer |
| `livecodebench` | the program in the output, run on the problem's public and private test cases, scored `1` when every case passes ([livecodebench.py](https://github.com/ynulihao/LLMRouterBench/blob/811df08b1b37646064eeb8cb6acfd498bf99885a/evaluation/LiveCodeBench/livecodebench.py)) | in part: a caller holding the public test cases can run those, not the private ones, so its check passes some programs the score fails |
| `livemathbench` | as `aime`, the final answer graded against the reference answer by a math-equivalence test ([livemathbench.py](https://github.com/ynulihao/LLMRouterBench/blob/811df08b1b37646064eeb8cb6acfd498bf99885a/evaluation/LiveMathBench/livemathbench.py)) | no: the test needs the reference answer |
| `mmlupro` | the option letter the output names, compared with the key ([mmlupro.py](https://github.com/ynulihao/LLMRouterBench/blob/811df08b1b37646064eeb8cb6acfd498bf99885a/evaluation/MMLUPro/mmlupro.py)) | no: only a format check, that a letter is named |
| `simpleqa` | a grader model grades the output against the reference answer, and only its top grade is a success ([simpleqa.py](https://github.com/ynulihao/LLMRouterBench/blob/811df08b1b37646064eeb8cb6acfd498bf99885a/evaluation/SimpleQA/simpleqa.py)) | no: the grader is given the reference answer |

## Method

- The script reads the config of `evidence/llmrouterbench/results.json` and runs `evaluate` (12.3) with it at its lowest and highest bars on the matrix the 12.18 converter writes, the matrix the committed file was made from (12.19)
- For each cell (a bar, flavor, seed and task) it rebuilds the router 12.3 builds, from the calibration half's counts and mean costs, with `max_fallbacks` 0, 2 and 12, the number of pool models minus one, which gives the whole list 5.3 sorts: every model that clears the bar when one does, else every model, best calibration bound first. The route is the primary then the fallbacks, and the script stops unless each route's primary is the cell's routed model
- On each held-out item the route's models are tried in turn until a record scores 1, as the executor moves on when `validate` fails, and every attempt's recorded cost is spent, the failed ones too; success is the items some attempt scores 1 on over the held-out items, pooled over a seed's tasks and averaged over the seeds as 12.3's `summary` does, and so are the cost and the attempts per item
- With `max_fallbacks` 0 each row is the committed routed row, pooled and per task, and the oracle the committed oracle row; the script stops otherwise
- The share of the gap recovered is (a route's success minus no fallback's) over (the oracle's minus no fallback's), on the means over seeds

## Results

```text
$ python research/check_fallback.py --matrix llmrouterbench-matrix.jsonl
LLMRouterBench (evidence/llmrouterbench/results.json): 9 tasks, 13 models, 12,066 items, 50 seeds, bars 0.1 and 0.8, the lowest and highest of 8
a route is the router's primary then its next max_fallbacks models (5.3); each held-out item is tried down its route until a record scores 1, and every attempt's cost is spent
oracle: success 0.8207, cost 33.6900
cost_effective bar 0.1:
  max_fallbacks 0: success 0.5528, cost 39.4802, 1.000 times no fallback's, attempts per item 1.000, routes of 1 to 1 models, gap to the oracle recovered 0.000
  max_fallbacks 2: success 0.6803, cost 139.0409, 3.522 times no fallback's, attempts per item 1.818, routes of 3 to 3 models, gap to the oracle recovered 0.476
  max_fallbacks 12: success 0.8056, cost 346.3341, 8.772 times no fallback's, attempts per item 3.340, routes of 4 to 13 models, gap to the oracle recovered 0.944
cost_effective bar 0.8:
  max_fallbacks 0: success 0.6060, cost 154.0269, 1.000 times no fallback's, attempts per item 1.000, routes of 1 to 1 models, gap to the oracle recovered 0.000
  max_fallbacks 2: success 0.7470, cost 317.8018, 2.063 times no fallback's, attempts per item 1.653, routes of 1 to 3 models, gap to the oracle recovered 0.657
  max_fallbacks 12: success 0.8120, cost 425.8001, 2.764 times no fallback's, attempts per item 3.511, routes of 1 to 13 models, gap to the oracle recovered 0.960
cost_blind bar 0.1:
  max_fallbacks 0: success 0.6147, cost 173.4190, 1.000 times no fallback's, attempts per item 1.000, routes of 1 to 1 models, gap to the oracle recovered 0.000
  max_fallbacks 2: success 0.7542, cost 358.7288, 2.069 times no fallback's, attempts per item 1.660, routes of 3 to 3 models, gap to the oracle recovered 0.678
  max_fallbacks 12: success 0.8056, cost 425.5299, 2.454 times no fallback's, attempts per item 2.758, routes of 4 to 13 models, gap to the oracle recovered 0.927
cost_blind bar 0.8:
  max_fallbacks 0: success 0.6147, cost 173.4190, 1.000 times no fallback's, attempts per item 1.000, routes of 1 to 1 models, gap to the oracle recovered 0.000
  max_fallbacks 2: success 0.7500, cost 348.4775, 2.009 times no fallback's, attempts per item 1.639, routes of 1 to 3 models, gap to the oracle recovered 0.657
  max_fallbacks 12: success 0.8120, cost 448.2524, 2.585 times no fallback's, attempts per item 3.491, routes of 1 to 13 models, gap to the oracle recovered 0.958
per task at bar 0.8, held-out success with max_fallbacks 0 and 12, and the oracle's:
  aime (60 items): cost_effective from 0.8294 to 0.9471, cost_blind from 0.8304 to 0.9471, routes of 1 to 13 models; oracle 0.9655
  arc-agi (400 items): cost_effective from 0.5230 to 0.6465, cost_blind from 0.5230 to 0.6465, routes of 13 to 13 models; oracle 0.6465
  arenahard (749 items): cost_effective from 0.6576 to 0.9768, cost_blind from 0.6581 to 0.9768, routes of 13 to 13 models; oracle 0.9768
  gpqa (198 items): cost_effective from 0.8334 to 0.9403, cost_blind from 0.8334 to 0.9403, routes of 1 to 13 models; oracle 0.9689
  hle (2,157 items): cost_effective from 0.2603 to 0.5066, cost_blind from 0.2603 to 0.5066, routes of 13 to 13 models; oracle 0.5066
  livecodebench (1,055 items): cost_effective from 0.8634 to 0.8641, cost_blind from 0.8634 to 0.8641, routes of 1 to 2 models; oracle 0.9200
  livemathbench (121 items): cost_effective from 0.7602 to 0.8429, cost_blind from 0.7631 to 0.8429, routes of 13 to 13 models; oracle 0.8429
  mmlupro (3,000 items): cost_effective from 0.8400 to 0.9370, cost_blind from 0.8746 to 0.9370, routes of 4 to 9 models; oracle 0.9499
  simpleqa (4,326 items): cost_effective from 0.5346 to 0.8431, cost_blind from 0.5346 to 0.8431, routes of 13 to 13 models; oracle 0.8431
```

## Reading it

- Most of the gap between routing per task and the oracle is within reach of a fallback after the call, if the check is good: the whole list recovers 0.927 to 0.960 of it. Routing still picks one first model per task; what reaches the other items is the move to the next model when a check fails, which needs no prediction of which items are hard
- Every failed attempt is paid for. Two fallbacks cost 2.009 to 3.522 times no fallback, the whole list 2.454 to 8.772 times, while the oracle, which pays only the cheapest model that succeeds, spends 33.6900. `cost_effective` multiplies its cost the most, since its primary is cheap and its fallbacks dearer, but it ends cheaper: with the whole list both flavors try the same models and reach the same success, 0.8056 at bar 0.1 and 0.8120 at bar 0.8, and `cost_effective` tries the cheap ones first, at 346.3341 against 425.5299 at bar 0.1 and 425.8001 against 448.2524 at bar 0.8
- A high bar leaves the fallback nowhere to go. When some model clears the bar, 5.3 fills the route with models that clear it only, so where one model clears it a failed check ends the call with every model failed instead of trying a model below the bar. At bar 0.8 each task whose whole-list routes hold all 13 models reaches its oracle exactly, `arc-agi`, `arenahard`, `hle`, `livemathbench` and `simpleqa`, while `livecodebench`, with routes of 1 to 2 models, barely moves, and `mmlupro`, with 4 to 9, ends at 0.9370 against 0.9499. Whether a route should go on below the bar after its clearing models fail is a design question for a backlog row, not a change made here
- The check is what a caller lacks. Only `arenahard`'s score is made without an answer key, by a judge against a baseline answer, so its gain, from 0.6576 to 0.9768, is the one a caller could chase at call time, for the judge's calls on top and with that judge's errors; `livecodebench`'s public tests are a weaker check than its score; on the seven other tasks a caller can check the format of an answer, not whether it is right
- So the README Limitations' first bullet, which says the library routes per task and has no confidence-based cascade, leaves out the per-call move it already makes on a failed check; its wording is a backlog row, not an edit made here, and a cascade on the model's confidence stays a separate question

## Limits

- An upper bound: a real check passes some wrong answers and fails some right ones, and a check that calls a model costs calls the records do not hold, so a caller's gain is smaller and its cost larger
- How each score was made is read from the scoring code at the commit linked above, not from the records, which keep only the score; this note takes that code to be what scored the records
- Each record was made alone, so a fallback model never sees the failed answer, as the executor sends every model the same messages; the matrix has no latency, so the time each failed attempt adds is not counted
- Two bars, the lowest and highest committed ones; the 50 seeds re-split the same 12,066 items, so they do not show how the numbers move on new items
- A success is a record scored 1, so an `arenahard` level judgment counts as a miss (12.18), and a cost is the record's own `cost`, as in the committed results

## Regenerate

```bash
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python research/check_fallback.py --matrix llmrouterbench-matrix.jsonl
```

The converter downloads the pinned file into its cache folder on its first run and checks it; the script reads only the matrix and the committed results file. `tests/test_research_check_fallback.py` compares the Results block with a fresh run when the pinned file is cached.
