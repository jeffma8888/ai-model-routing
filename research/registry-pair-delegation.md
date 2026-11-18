# The registry's own pair as delegation evidence: superlinked/train-a-router-reasoning

## Facts

- Question: can the release whose two models and prices are the registry's own, `openai/gpt-6-luna` and `openai/gpt-6.1-sol`, score the inline-or-sub-agent decision, each model as the parent, when its rows give a USD cost and no token counts?
- Answer: yes, with one input bounded rather than measured. Both models list output at five times input, so a row's cost fixes its input-equivalent tokens, E, but not how many tokens the inline path's later calls re-read, which lies between `E / 5` and E; the script prices every row at both ends.
- The ends barely move the decision: 4 of 32 (parent, flavor, bar, point) groups have a task whose mode or delegate differs between them, at most 1 of 31 tasks in one group, all at point 3, the folded one.
- `openai/gpt-6-luna` as parent, `cost_effective`, in a separate call at context 8,000: the decision delegates 31 of 31 tasks at bar 0.8 (9 of them to the other model) for 0.912 held-out success at 4.650378 USD, against 0.886 at 3.082999 to 3.822148 inline; at context 200,000 inline costs 61.508599 to 62.247748 and the decision the same 4.650378.
- `openai/gpt-6.1-sol` as parent, `cost_effective`, in a separate call at context 8,000: the decision delegates 31 of 31 tasks at bar 0.8 (22 of them to the other model) for 0.912 at 30.668028 USD, against 0.926 at 54.680950 to 61.487926 inline; at bar 0.9 0.920 at 33.071926, 13 to the other model.
- Folded into the next call at context 8,000, `openai/gpt-6.1-sol` stays inline: 0 of 31 tasks delegated at the low end and 1 at the high end, at bar 0.8.
- Recommendation: a delegation results file for this dataset, as row E25, priced at the low end, its README subsection after a room row.

## Method

- Files, the three that `research/registry_pair.py` pins, each checked by size and sha256 before it is read through that script's `fetch`, loaded from its own folder by path, and downloaded at the pinned revision `63336f25fc54597a8e161a7245613f91bd60177e` into `~/.cache/ai-model-routing-evidence/registry-pair` (or `--cache`) when absent:

| File | Bytes | sha256 |
|---|---|---|
| `pair.json` | 2,473 | `4b4cc5f936fe8a8018b6845bfa9bd29b7d18ec428489d15ebab62554c4cd11b4` |
| `recordings/grades-calibration.json` | 3,777,170 | `2f47b9df61b131879f30b4ea36693a8ce8bc43e46afd17d7fbd5d7a93922e8ac` |
| `recordings/grades-final.json` | 3,742,778 | `8d66442ad94b5e846a856084adfaba7a2915bab6253008e93ed44348dc264a5f` |

- Licence, from the dataset card at that revision, as `research/registry-pair.md` quotes it: `license: other`, `license_name: mixed-mit-and-apache-2.0`. This note commits no question text and no row of the dataset: it prints counts, sums and rates.
- Models and prices: that script's `check_pair` checks that each arm is in `model_routing/data/models.json` as `openai/<model>` at the pair's input and output prices; this script then checks that each model's output price is five times its input price and that neither has price tiers, or exits 2. Its `outcomes` reads each row's correctness (an invalid answer counts as wrong) and cost.
- Tokens: a row's cost is `in * price_in + out * price_out` per million tokens, with `price_out = 5 * price_in`, so `E = cost / price_in` (per million) is `in + 5 * out`, while the inline path's later calls re-read `in + out` (DESIGN 13.2). The `low` end prices a row as `in = E % 5` and `out = E // 5`, the fewest tokens that cost E; the `high` end as `in = E` and `out = 0`. Both give the row's own cost, E rounded to the nearest whole token where the release's cache categories make it fractional; the Results block gives how many rows that is and the largest cost change.
- The hand-off: the four points of the committed `evidence/response-bank-delegation/results.json`, which the other three delegation results files also use: a brief and a result of 500 tokens each and one carry turn, at a parent context of 8,000, 64,000 or 200,000 tokens with inline work in a call of its own, or 8,000 with it folded into the parent's next call. These sizes are assumed, as in every delegation results file (DESIGN 13.9); no public matrix records them.
- Decision: the 13.9 harness's own cell (`_calibrate`, `_router`, `_cell` and `_summary` of `model_routing/delegation_eval.py`) on the release's split, the calibration split calibrating and the final split scoring, one task per (dataset, task) pair as `research/registry-pair.md` makes them, both models as parents, at that file's bars 0.8 and 0.9, both flavors, `min_samples` and confidence. Each line gives the decision's, always inline's and always delegating's held-out success and summed cost, the tasks the decision delegates, and the tasks whose delegate (the 13.3 pick, which may be the parent's own model) is the other model.

## Results

```text
$ python research/registry_pair_delegation.py
superlinked/train-a-router-reasoning at 63336f2 as delegation evidence (grades-calibration.json calibrates, grades-final.json scores): bars 0.8 0.9, min_samples 30, confidence 0.95, the points of evidence/response-bank-delegation/results.json
  point 0: context 8,000, brief 500, result 500, carry turns 1, inline in a separate call
  point 1: context 64,000, brief 500, result 500, carry turns 1, inline in a separate call
  point 2: context 200,000, brief 500, result 500, carry turns 1, inline in a separate call
  point 3: context 8,000, brief 500, result 500, carry turns 1, inline folded into the next call
  cheap: openai/gpt-6-luna at 0.1 and 0.5 USD per million input and output tokens, output 5 times input; median E 756.0 input-equivalent tokens a question
  strong: openai/gpt-6.1-sol at 2.0 and 10.0 USD per million input and output tokens, output 5 times input; median E 510.0 input-equivalent tokens a question
  E not a whole token: 134 of 12,198 row costs; the largest cost change of rounding 0.000001000 USD
  ends: low prices a row as in = E % 5 and out = E // 5, high as in = E and out = 0
  end   parent              flavor          bar  point              decision     cost (USD)  delegated  inline  cost (USD)   delegate  cost (USD)  other delegate
  low   openai/gpt-6-luna   cost_effective  0.8  C 8,000 separate   0.912      4.650378  31 of 31   0.886     3.082999  0.912     4.650378   9 of 31
  low   openai/gpt-6-luna   cost_effective  0.8  C 64,000 separate  0.912      4.650378  31 of 31   0.886    20.123799  0.912     4.650378   9 of 31
  low   openai/gpt-6-luna   cost_effective  0.8  C 200,000 separate 0.912      4.650378  31 of 31   0.886    61.508599  0.912     4.650378   9 of 31
  low   openai/gpt-6-luna   cost_effective  0.8  C 8,000 folded     0.912      3.730746   9 of 31   0.886     0.555591  0.912     4.650378   9 of 31
  low   openai/gpt-6-luna   cost_effective  0.9  C 8,000 separate   0.920      7.054276  31 of 31   0.886     3.082999  0.920     7.054276  18 of 31
  low   openai/gpt-6-luna   cost_effective  0.9  C 64,000 separate  0.920      7.054276  31 of 31   0.886    20.123799  0.920     7.054276  18 of 31
  low   openai/gpt-6-luna   cost_effective  0.9  C 200,000 separate 0.920      7.054276  31 of 31   0.886    61.508599  0.920     7.054276  18 of 31
  low   openai/gpt-6-luna   cost_effective  0.9  C 8,000 folded     0.920      6.670466  18 of 31   0.886     0.555591  0.920     7.054276  18 of 31
  low   openai/gpt-6-luna   cost_blind      0.8  C 8,000 separate   0.922      7.771801  19 of 31   0.886     3.082999  0.922     7.587372  19 of 31
  low   openai/gpt-6-luna   cost_blind      0.8  C 64,000 separate  0.922     10.795801  19 of 31   0.886    20.123799  0.922     7.587372  19 of 31
  low   openai/gpt-6-luna   cost_blind      0.8  C 200,000 separate 0.922     18.139801  19 of 31   0.886    61.508599  0.922     7.587372  19 of 31
  low   openai/gpt-6-luna   cost_blind      0.8  C 8,000 folded     0.922      7.328586  19 of 31   0.886     0.555591  0.922     7.587372  19 of 31
  low   openai/gpt-6-luna   cost_blind      0.9  C 8,000 separate   0.922      7.771801  19 of 31   0.886     3.082999  0.922     7.587372  19 of 31
  low   openai/gpt-6-luna   cost_blind      0.9  C 64,000 separate  0.922     10.795801  19 of 31   0.886    20.123799  0.922     7.587372  19 of 31
  low   openai/gpt-6-luna   cost_blind      0.9  C 200,000 separate 0.922     18.139801  19 of 31   0.886    61.508599  0.922     7.587372  19 of 31
  low   openai/gpt-6-luna   cost_blind      0.9  C 8,000 folded     0.922      7.328586  19 of 31   0.886     0.555591  0.922     7.587372  19 of 31
  low   openai/gpt-6.1-sol  cost_effective  0.8  C 8,000 separate   0.912     30.668028  31 of 31   0.926    54.680950  0.912    30.668028  22 of 31
  low   openai/gpt-6.1-sol  cost_effective  0.8  C 64,000 separate  0.912     30.668028  31 of 31   0.926   395.496950  0.912    30.668028  22 of 31
  low   openai/gpt-6.1-sol  cost_effective  0.8  C 200,000 separate 0.912     30.668028  31 of 31   0.926  1223.192950  0.912    30.668028  22 of 31
  low   openai/gpt-6.1-sol  cost_effective  0.8  C 8,000 folded     0.926      5.129796   0 of 31   0.926     5.129796  0.912    30.668028  22 of 31
  low   openai/gpt-6.1-sol  cost_effective  0.9  C 8,000 separate   0.920     33.071926  31 of 31   0.926    54.680950  0.920    33.071926  13 of 31
  low   openai/gpt-6.1-sol  cost_effective  0.9  C 64,000 separate  0.920     33.071926  31 of 31   0.926   395.496950  0.920    33.071926  13 of 31
  low   openai/gpt-6.1-sol  cost_effective  0.9  C 200,000 separate 0.920     33.071926  31 of 31   0.926  1223.192950  0.920    33.071926  13 of 31
  low   openai/gpt-6.1-sol  cost_effective  0.9  C 8,000 folded     0.926      5.506934   1 of 31   0.926     5.129796  0.920    33.071926  13 of 31
  low   openai/gpt-6.1-sol  cost_blind      0.8  C 8,000 separate   0.926     54.315042   1 of 31   0.926    54.680950  0.922    33.605022  12 of 31
  low   openai/gpt-6.1-sol  cost_blind      0.8  C 64,000 separate  0.926    389.979042   1 of 31   0.926   395.496950  0.922    33.605022  12 of 31
  low   openai/gpt-6.1-sol  cost_blind      0.8  C 200,000 separate 0.926   1205.163042   1 of 31   0.926  1223.192950  0.922    33.605022  12 of 31
  low   openai/gpt-6.1-sol  cost_blind      0.8  C 8,000 folded     0.926      5.506934   1 of 31   0.926     5.129796  0.922    33.605022  12 of 31
  low   openai/gpt-6.1-sol  cost_blind      0.9  C 8,000 separate   0.926     54.315042   1 of 31   0.926    54.680950  0.922    33.605022  12 of 31
  low   openai/gpt-6.1-sol  cost_blind      0.9  C 64,000 separate  0.926    389.979042   1 of 31   0.926   395.496950  0.922    33.605022  12 of 31
  low   openai/gpt-6.1-sol  cost_blind      0.9  C 200,000 separate 0.926   1205.163042   1 of 31   0.926  1223.192950  0.922    33.605022  12 of 31
  low   openai/gpt-6.1-sol  cost_blind      0.9  C 8,000 folded     0.926      5.506934   1 of 31   0.926     5.129796  0.922    33.605022  12 of 31
  high  openai/gpt-6-luna   cost_effective  0.8  C 8,000 separate   0.912      4.650378  31 of 31   0.886     3.822148  0.912     4.650378   9 of 31
  high  openai/gpt-6-luna   cost_effective  0.8  C 64,000 separate  0.912      4.650378  31 of 31   0.886    20.862948  0.912     4.650378   9 of 31
  high  openai/gpt-6-luna   cost_effective  0.8  C 200,000 separate 0.912      4.650378  31 of 31   0.886    62.247748  0.912     4.650378   9 of 31
  high  openai/gpt-6-luna   cost_effective  0.8  C 8,000 folded     0.912      3.927148  10 of 31   0.886     0.925166  0.912     4.650378   9 of 31
  high  openai/gpt-6-luna   cost_effective  0.9  C 8,000 separate   0.920      7.054276  31 of 31   0.886     3.822148  0.920     7.054276  18 of 31
  high  openai/gpt-6-luna   cost_effective  0.9  C 64,000 separate  0.920      7.054276  31 of 31   0.886    20.862948  0.920     7.054276  18 of 31
  high  openai/gpt-6-luna   cost_effective  0.9  C 200,000 separate 0.920      7.054276  31 of 31   0.886    62.247748  0.920     7.054276  18 of 31
  high  openai/gpt-6-luna   cost_effective  0.9  C 8,000 folded     0.920      6.745057  19 of 31   0.886     0.925166  0.920     7.054276  18 of 31
  high  openai/gpt-6-luna   cost_blind      0.8  C 8,000 separate   0.922      7.860559  19 of 31   0.886     3.822148  0.922     7.587372  19 of 31
  high  openai/gpt-6-luna   cost_blind      0.8  C 64,000 separate  0.922     10.884559  19 of 31   0.886    20.862948  0.922     7.587372  19 of 31
  high  openai/gpt-6-luna   cost_blind      0.8  C 200,000 separate 0.922     18.228559  19 of 31   0.886    62.247748  0.922     7.587372  19 of 31
  high  openai/gpt-6-luna   cost_blind      0.8  C 8,000 folded     0.922      7.372966  19 of 31   0.886     0.925166  0.922     7.587372  19 of 31
  high  openai/gpt-6-luna   cost_blind      0.9  C 8,000 separate   0.922      7.860559  19 of 31   0.886     3.822148  0.922     7.587372  19 of 31
  high  openai/gpt-6-luna   cost_blind      0.9  C 64,000 separate  0.922     10.884559  19 of 31   0.886    20.862948  0.922     7.587372  19 of 31
  high  openai/gpt-6-luna   cost_blind      0.9  C 200,000 separate 0.922     18.228559  19 of 31   0.886    62.247748  0.922     7.587372  19 of 31
  high  openai/gpt-6-luna   cost_blind      0.9  C 8,000 folded     0.922      7.372966  19 of 31   0.886     0.925166  0.922     7.587372  19 of 31
  high  openai/gpt-6.1-sol  cost_effective  0.8  C 8,000 separate   0.912     30.668028  31 of 31   0.926    61.487926  0.912    30.668028  22 of 31
  high  openai/gpt-6.1-sol  cost_effective  0.8  C 64,000 separate  0.912     30.668028  31 of 31   0.926   402.303926  0.912    30.668028  22 of 31
  high  openai/gpt-6.1-sol  cost_effective  0.8  C 200,000 separate 0.912     30.668028  31 of 31   0.926  1229.999926  0.912    30.668028  22 of 31
  high  openai/gpt-6.1-sol  cost_effective  0.8  C 8,000 folded     0.925      8.672121   1 of 31   0.926     8.533284  0.912    30.668028  22 of 31
  high  openai/gpt-6.1-sol  cost_effective  0.9  C 8,000 separate   0.920     33.071926  31 of 31   0.926    61.487926  0.920    33.071926  13 of 31
  high  openai/gpt-6.1-sol  cost_effective  0.9  C 64,000 separate  0.920     33.071926  31 of 31   0.926   402.303926  0.920    33.071926  13 of 31
  high  openai/gpt-6.1-sol  cost_effective  0.9  C 200,000 separate 0.920     33.071926  31 of 31   0.926  1229.999926  0.920    33.071926  13 of 31
  high  openai/gpt-6.1-sol  cost_effective  0.9  C 8,000 folded     0.925      9.021779   2 of 31   0.926     8.533284  0.920    33.071926  13 of 31
  high  openai/gpt-6.1-sol  cost_blind      0.8  C 8,000 separate   0.926     61.067058   1 of 31   0.926    61.487926  0.922    33.605022  12 of 31
  high  openai/gpt-6.1-sol  cost_blind      0.8  C 64,000 separate  0.926    396.731058   1 of 31   0.926   402.303926  0.922    33.605022  12 of 31
  high  openai/gpt-6.1-sol  cost_blind      0.8  C 200,000 separate 0.926   1211.915058   1 of 31   0.926  1229.999926  0.922    33.605022  12 of 31
  high  openai/gpt-6.1-sol  cost_blind      0.8  C 8,000 folded     0.926      8.882942   1 of 31   0.926     8.533284  0.922    33.605022  12 of 31
  high  openai/gpt-6.1-sol  cost_blind      0.9  C 8,000 separate   0.926     61.067058   1 of 31   0.926    61.487926  0.922    33.605022  12 of 31
  high  openai/gpt-6.1-sol  cost_blind      0.9  C 64,000 separate  0.926    396.731058   1 of 31   0.926   402.303926  0.922    33.605022  12 of 31
  high  openai/gpt-6.1-sol  cost_blind      0.9  C 200,000 separate 0.926   1211.915058   1 of 31   0.926  1229.999926  0.922    33.605022  12 of 31
  high  openai/gpt-6.1-sol  cost_blind      0.9  C 8,000 folded     0.926      8.882942   1 of 31   0.926     8.533284  0.922    33.605022  12 of 31
  ends compared: 4 of 32 (parent, flavor, bar, point) groups have a task whose mode or delegate differs between the ends, at most 1 of 31 tasks in one group, at point 3
```

## Reading it

- The pair can score the decision: the work cost of each path is the row's own cost, the hand-off sizes are the grid's, and the one quantity the rows lack, the tokens the inline path re-reads after its work, has two ends that each reproduce the row's cost. Only 4 of 32 groups see any task move between the ends, by at most 1 of 31 tasks, all at point 3, the folded one, where the re-read is a larger share of the inline cost.
- `openai/gpt-6-luna` as parent: in a separate call the decision delegates every task at both bars, sending 9 (bar 0.8) or 18 (bar 0.9) to the other model and the rest to a fresh instance of itself, since a brief and a result of 500 tokens cost less than re-reading 8,000. So it buys 0.912 or 0.920 held-out success over inline's 0.886, at 4.650378 or 7.054276 USD against 3.082999 to 3.822148 inline at context 8,000, and at context 64,000 or 200,000 for less than inline costs.
- `openai/gpt-6.1-sol` as parent: in a separate call the decision delegates every task, 22 (bar 0.8) or 13 (bar 0.9) to the other model, for 0.912 or 0.920 at 30.668028 or 33.071926 USD, against 0.926 inline at 54.680950 to 61.487926 at context 8,000: about half the cost, for a lower success. Folded at context 8,000 it stays inline.
- `cost_blind` gives the same rows at both bars: with `openai/gpt-6-luna` as parent 0.922, 19 of 31 tasks delegated; with `openai/gpt-6.1-sol` 0.926, 1 of 31.

## Recommendation

- Yes: a delegation results file for this dataset, as row E25, the first whose models and prices are the registry's own. Its converter reuses the routing converter's pinned files and writes each row at the low end, the one that under-states the inline path's re-read, so a delegation saving it shows holds at any split of a row's tokens; its RESULTS.md states the high end's moves beside it. E25 states its split as the routing results file does.
- Its README subsection waits for a room row: the Evidence section is near its byte budget.

## Limits

- The inline re-read is bounded, not measured: a row's split between input and output tokens is not in the release, and output that the model's history drops (its reasoning, DESIGN 13.2) would put the true re-read below the low end's.
- The hand-off sizes, the parent's context and the carry turn are the grid's assumptions, and the delegate is credited with its recorded answer to the whole question, as in every delegation results file; no lossy brief is measured.
- Two models from one vendor, one fixed split and no seeds, so no spread over splits; the release's caveats on contamination and on KOR-Bench's few families, which `research/registry-pair.md` quotes, apply here too.

## Regenerate

```text
python -m pip install -e .
python research/registry_pair_delegation.py
```
