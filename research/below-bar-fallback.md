# Should a route go on below the bar after its clearing models fail?

When some model clears a task's bar, the router fills the route with the clearing models alone ([DESIGN.md](../DESIGN.md), Choosing, 5.3), so a call on which all of them fail the caller's check ends with every model failed. [check-fallback.md](check-fallback.md) found that at a high bar this leaves the fallback short of the per-item oracle on the tasks where one or a few models clear. This note replays the alternative on the same LLMRouterBench records: a route that goes on, after the clearing models, to the rest of the eligible measured models in the order the router uses when none clears. Its numbers are the output of [below_bar_fallback.py](below_bar_fallback.py), which stops unless the replay with no fallback is the committed routed row.

## Facts

- Every number here is an upper bound, as in check-fallback.md: the replay's check is the record's own score, a check that never passes a wrong answer or fails a right one, and a caller's check at call time can only do worse
- Data: the 12.18 matrix, 9 tasks, 13 models and 12,066 items, with the committed config at bars 0.1 and 0.8, the lowest and highest of 8, and 50 seeds; the oracle reaches 0.8207 at 33.6900; a model clears the bar in 425 of the 450 cells of each flavor at bar 0.1 and in 115 at bar 0.8
- Two fallbacks, the `max_fallbacks` of every packaged task: the below-bar route is the 5.3 route on every cell at bar 0.1, and at bar 0.8 it differs on 64 of 450 cells and adds 0.0042 of success, `cost_effective` from 0.7470 to 0.7512 at 1.031 times the cost and `cost_blind` from 0.7500 to 0.7542 at 1.029 times, 0.057 and 0.060 of the gap the 5.3 route leaves to the oracle
- Every listed model: the below-bar route reaches the oracle's 0.8207 at both bars in both flavors, where the 5.3 route stops at 0.8056 at bar 0.1 and 0.8120 at bar 0.8, so it adds 0.0151 and 0.0086, at 1.043 to 1.121 times the cost of the 5.3 route
- Per task with every listed model, the gain at bar 0.8 is on the four tasks where some model clears: `livecodebench` from 0.8641 to 0.9200 at 1.538 and 1.539 times the cost, `gpqa` from 0.9403 to 0.9689, `aime` from 0.9471 to 0.9655 and `mmlupro` from 0.9370 to 0.9499; at bar 0.1 it is on `hle`, from 0.4231 to 0.5066, and `arc-agi`, from 0.6422 to 0.6465
- Each success the below-bar route adds is a held-out item on which every model of the 5.3 route failed, a call the executor ends with `AllModelsFailed`, now answered by a model under the bar; no call that a model of the 5.3 route answers changes, since the 5.3 route is the first part of the below-bar route

## Method

- The script reads the config of `evidence/llmrouterbench/results.json` and runs `evaluate` (12.3) with it at its lowest and highest bars on the matrix the 12.18 converter writes, the matrix the committed file was made from (12.19)
- For each cell (a bar, flavor, seed and task) it rebuilds the router 12.3 builds, from the calibration half's counts and mean costs, as [check_fallback.py](check_fallback.py) does, with every other model a fallback, so the decision lists the whole list 5.3 sorts: every model that clears the bar when one does, cheapest first in `cost_effective`, else every eligible measured model, best calibration bound first. It stops unless the decision's primary is the cell's routed model
- The 5.3 route is that list cut after the primary and `max_fallbacks` more models. The below-bar route is the same list, then every other eligible measured model sorted as 5.3 sorts them when none clears, by calibration bound, then routing cost, then ID, cut the same way. When no model clears the bar the two are the same, since the list already holds every eligible measured model
- On each held-out item a route's models are tried in turn until a record scores 1, as the executor moves on when `validate` fails, and every attempt's recorded cost is spent; success, cost and attempts per item are pooled over a seed's tasks and averaged over the seeds as 12.3's `summary` does, with `max_fallbacks` 2 and 12, the number of pool models minus one
- The success the below-bar route adds is its success minus the 5.3 route's, which is the share of held-out items answered by a model under the bar; the share recovered is that over the oracle's success minus the 5.3 route's
- With `max_fallbacks` 0 each row is the committed routed row, pooled and per task, and the oracle the committed oracle row; the script stops otherwise

## Results

```text
$ python research/below_bar_fallback.py --matrix llmrouterbench-matrix.jsonl
LLMRouterBench (evidence/llmrouterbench/results.json): 9 tasks, 13 models, 12,066 items, 50 seeds, bars 0.1 and 0.8, the lowest and highest of 8
the 5.3 route is the router's primary then its next max_fallbacks models, from the clearing models alone when one clears; the below-bar route goes on after those to every other eligible measured model in the best_available order, up to max_fallbacks fallbacks; each held-out item is tried down a route until a record scores 1, and every attempt's cost is spent
oracle: success 0.8207, cost 33.6900
cost_effective bar 0.1: no fallback success 0.5528, cost 39.4802; a model clears the bar in 425 of 450 cells
  max_fallbacks 2: 5.3 route success 0.6803, cost 139.0409, routes of 3 to 3 models; below-bar route success 0.6803, cost 139.0409, routes of 3 to 3 models, attempts per item 1.818; it differs in 0 of 450 cells, adds success 0.0000 at 1.000 times the cost and recovers 0.000 of the 5.3 route's gap to the oracle
  max_fallbacks 12: 5.3 route success 0.8056, cost 346.3341, routes of 4 to 13 models; below-bar route success 0.8207, cost 388.1847, routes of 13 to 13 models, attempts per item 4.262; it differs in 100 of 450 cells, adds success 0.0151 at 1.121 times the cost and recovers 1.000 of the 5.3 route's gap to the oracle
cost_effective bar 0.8: no fallback success 0.6060, cost 154.0269; a model clears the bar in 115 of 450 cells
  max_fallbacks 2: 5.3 route success 0.7470, cost 317.8018, routes of 1 to 3 models; below-bar route success 0.7512, cost 327.5492, routes of 3 to 3 models, attempts per item 1.674; it differs in 64 of 450 cells, adds success 0.0042 at 1.031 times the cost and recovers 0.057 of the 5.3 route's gap to the oracle
  max_fallbacks 12: 5.3 route success 0.8120, cost 425.8001, routes of 1 to 13 models; below-bar route success 0.8207, cost 444.8599, routes of 13 to 13 models, attempts per item 3.700; it differs in 115 of 450 cells, adds success 0.0086 at 1.045 times the cost and recovers 1.000 of the 5.3 route's gap to the oracle
cost_blind bar 0.1: no fallback success 0.6147, cost 173.4190; a model clears the bar in 425 of 450 cells
  max_fallbacks 2: 5.3 route success 0.7542, cost 358.7288, routes of 3 to 3 models; below-bar route success 0.7542, cost 358.7288, routes of 3 to 3 models, attempts per item 1.660; it differs in 0 of 450 cells, adds success 0.0000 at 1.000 times the cost and recovers 0.000 of the 5.3 route's gap to the oracle
  max_fallbacks 12: 5.3 route success 0.8056, cost 425.5299, routes of 4 to 13 models; below-bar route success 0.8207, cost 467.3830, routes of 13 to 13 models, attempts per item 3.680; it differs in 100 of 450 cells, adds success 0.0151 at 1.098 times the cost and recovers 1.000 of the 5.3 route's gap to the oracle
cost_blind bar 0.8: no fallback success 0.6147, cost 173.4190; a model clears the bar in 115 of 450 cells
  max_fallbacks 2: 5.3 route success 0.7500, cost 348.4775, routes of 1 to 3 models; below-bar route success 0.7542, cost 358.7288, routes of 3 to 3 models, attempts per item 1.660; it differs in 64 of 450 cells, adds success 0.0042 at 1.029 times the cost and recovers 0.060 of the 5.3 route's gap to the oracle
  max_fallbacks 12: 5.3 route success 0.8120, cost 448.2524, routes of 1 to 13 models; below-bar route success 0.8207, cost 467.3830, routes of 13 to 13 models, attempts per item 3.680; it differs in 115 of 450 cells, adds success 0.0086 at 1.043 times the cost and recovers 1.000 of the 5.3 route's gap to the oracle
per task with max_fallbacks 12, held-out success with the 5.3 route and the below-bar route, the cost of the second over the first's, and the oracle's:
bar 0.1:
  aime (60 items): cost_effective from 0.9655 to 0.9655 at 1.000 times, cost_blind from 0.9655 to 0.9655 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.9655
  arc-agi (400 items): cost_effective from 0.6422 to 0.6465 at 1.051 times, cost_blind from 0.6422 to 0.6465 at 1.047 times, the routes differ in 100 of 100 cells; oracle 0.6465
  arenahard (749 items): cost_effective from 0.9768 to 0.9768 at 1.000 times, cost_blind from 0.9768 to 0.9768 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.9768
  gpqa (198 items): cost_effective from 0.9689 to 0.9689 at 1.000 times, cost_blind from 0.9689 to 0.9689 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.9689
  hle (2,157 items): cost_effective from 0.4231 to 0.5066 at 1.183 times, cost_blind from 0.4231 to 0.5066 at 1.179 times, the routes differ in 100 of 100 cells; oracle 0.5066
  livecodebench (1,055 items): cost_effective from 0.9200 to 0.9200 at 1.000 times, cost_blind from 0.9200 to 0.9200 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.9200
  livemathbench (121 items): cost_effective from 0.8429 to 0.8429 at 1.000 times, cost_blind from 0.8429 to 0.8429 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.8429
  mmlupro (3,000 items): cost_effective from 0.9499 to 0.9499 at 1.000 times, cost_blind from 0.9499 to 0.9499 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.9499
  simpleqa (4,326 items): cost_effective from 0.8431 to 0.8431 at 1.000 times, cost_blind from 0.8431 to 0.8431 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.8431
bar 0.8:
  aime (60 items): cost_effective from 0.9471 to 0.9655 at 1.078 times, cost_blind from 0.9471 to 0.9655 at 1.065 times, the routes differ in 10 of 100 cells; oracle 0.9655
  arc-agi (400 items): cost_effective from 0.6465 to 0.6465 at 1.000 times, cost_blind from 0.6465 to 0.6465 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.6465
  arenahard (749 items): cost_effective from 0.9768 to 0.9768 at 1.000 times, cost_blind from 0.9768 to 0.9768 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.9768
  gpqa (198 items): cost_effective from 0.9403 to 0.9689 at 1.076 times, cost_blind from 0.9403 to 0.9689 at 1.075 times, the routes differ in 20 of 100 cells; oracle 0.9689
  hle (2,157 items): cost_effective from 0.5066 to 0.5066 at 1.000 times, cost_blind from 0.5066 to 0.5066 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.5066
  livecodebench (1,055 items): cost_effective from 0.8641 to 0.9200 at 1.538 times, cost_blind from 0.8641 to 0.9200 at 1.539 times, the routes differ in 100 of 100 cells; oracle 0.9200
  livemathbench (121 items): cost_effective from 0.8429 to 0.8429 at 1.000 times, cost_blind from 0.8429 to 0.8429 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.8429
  mmlupro (3,000 items): cost_effective from 0.9370 to 0.9499 at 1.296 times, cost_blind from 0.9370 to 0.9499 at 1.105 times, the routes differ in 100 of 100 cells; oracle 0.9499
  simpleqa (4,326 items): cost_effective from 0.8431 to 0.8431 at 1.000 times, cost_blind from 0.8431 to 0.8431 at 1.000 times, the routes differ in 0 of 100 cells; oracle 0.8431
```

## Reading it

- With the packaged two fallbacks the question barely arises. The below-bar route differs from the 5.3 route only on a cell where fewer than three models clear, none at bar 0.1 and 64 of 450 at bar 0.8, and there it adds 0.0042 of success at 1.029 and 1.031 times the cost
- With the whole list it closes the gap the 5.3 route leaves to the oracle: trying every model with a perfect check is the oracle's success, 0.8207, where the 5.3 route stops at 0.8056 and 0.8120, for 1.043 to 1.121 times the cost. The gain sits where few models clear the bar: `livecodebench` at bar 0.8, from 0.8641 to 0.9200, and `hle` at bar 0.1, from 0.4231 to 0.5066
- What it trades is the bar. Without it, a call whose clearing models all fail the check ends with every model failed, which the caller sees; with it, the call is answered by a model the calibration half cannot show clears the bar, and only the check vouches for that answer. A perfect check makes the answer right, as here; a check that passes wrong answers makes these the riskiest answers of the route, since they are the items on which every clearing model's record scores 0
- On this dataset the check is what is missing. The gain lands on `aime`, `gpqa`, `livecodebench` and `mmlupro` at bar 0.8 and on `hle` and `arc-agi` at bar 0.1, whose scores are made against an answer key, `livecodebench`'s in part ([check-fallback.md](check-fallback.md), Checks per task); `arenahard`, the one task whose check a caller can run, never changes, since its whole-list routes hold all 13 models at both bars

## Recommendation

Offer it as an option on `Task`, off by default, because the default must keep the bar's promise, that every call is answered by a model that clears the bar or fails where the caller can see it, while a caller who holds a check that tells right from wrong, such as tests for generated code or an exact match for extracted fields, turns calls that end with every model failed into answered calls for a small extra cost, 1.029 to 1.121 times here. With the option on, the decision should say which fallbacks are below the bar and each attempt's record should carry it, so the monitor can count the calls the bar did not cover. The option is a spec change of its own, with tests first; nothing in the library changes here.

## Limits

- An upper bound: a real check passes some wrong answers and fails some right ones, and a check that calls a model costs calls the records do not hold
- Each record was made alone, so a model under the bar never sees the failed answers before it, as the executor sends every model the same messages; the matrix has no latency, so the time the extra attempts add is not counted
- Two bars, the lowest and highest committed ones; the 50 seeds re-split the same 12,066 items, so they do not show how the numbers move on new items
- One dataset: how much a below-bar route adds depends on how many models clear the bar, which here is the 425 and 115 cells above
- A success is a record scored 1, so an `arenahard` level judgment counts as a miss (12.18), and a cost is the record's own `cost`, as in the committed results

## Regenerate

```bash
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python research/below_bar_fallback.py --matrix llmrouterbench-matrix.jsonl
```

The converter downloads the pinned file into its cache folder on its first run and checks it; the script reads only the matrix and the committed results file. `tests/test_research_below_bar_fallback.py` compares the Results block with a fresh run when the pinned file is cached.
