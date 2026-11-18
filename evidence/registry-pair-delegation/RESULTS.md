# Delegation on the registry pair: inline or sub-agent on held-out questions

What the inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5) does on items it never saw, next to always working inline and always delegating, measured by `evaluate_delegation` (`DESIGN.md` 13.9) on the public [superlinked/train-a-router-reasoning](https://huggingface.co/datasets/superlinked/train-a-router-reasoning) at revision [`63336f25fc54597a8e161a7245613f91bd60177e`](https://huggingface.co/datasets/superlinked/train-a-router-reasoning/tree/63336f25fc54597a8e161a7245613f91bd60177e) (last modified 2026-10-21), the first delegation evidence whose two models and prices are the registry's own, `openai/gpt-6-luna` and `openai/gpt-6.1-sol`. Each item is one question, which both models answered in one graded call, marked right or wrong by the release's strict declared-label equality, as on AutoBench, LLMRouterBench and the response bank. The rows come from the converter described in [the registry-pair evidence README](../registry-pair/README.md), at its defaults, the matrix of [the registry-pair routing results](../registry-pair/RESULTS.md); the models' list prices are this checkout's registry, `model_routing/data/models.json`; the research note behind the token rule is [registry-pair-delegation.md](../../research/registry-pair-delegation.md); the committed results are [results.json](results.json). Every cost is a list-price estimate, never a billed cost.

Licence: the dataset card at the pinned revision names no single licence: its metadata reads `license: other` and `license_name: mixed-mit-and-apache-2.0`, and its Licenses section says "This is a collection with multiple upstream licenses, not a relicensing of its components. Preserve the included notices when redistributing them."; its component table is quoted in [the registry-pair routing results](../registry-pair/RESULTS.md). Attribution, as the card asks: these results derive from superlinked/train-a-router-reasoning at revision `63336f25fc54597a8e161a7245613f91bd60177e`; its questions come from the upstream benchmarks MMLU-Pro (TIGER-Lab/MMLU-Pro), BIG-Bench Hard (suzgunmirac/BIG-Bench-Hard) and KOR-Bench (KOR-Bench/KOR-Bench), and the card also asks to cite Laya (convaiinnovations/laya). This repo commits no part of the dataset: `results.json` holds only the run's settings, item counts and mean results.

## Method

- Matrix: the converter's default output, the one the routing results read: the 2 models on 6,099 items of 31 tasks, one task per (dataset, task) pair, so 12,198 rows, each a success when the release marks the answer right, with the release's estimated cost of the call and no token counts (`DESIGN.md` 12.23)
- Tokens: both models list output at five times input, `openai/gpt-6-luna` at 0.1 and 0.5 and `openai/gpt-6.1-sol` at 2 and 10 USD per 1M input and output tokens, so a row's cost fixes E, the cost over the input price, its input-equivalent tokens in + 5 * out, but not in + out, what the inline path's later calls re-read. Each row takes the `low` end, the fewest tokens that cost E: in = E % 5 and out = E // 5, with E rounded to the nearest whole token, a half to the even one. On the pinned files E is not a whole token on 134 of the 12,198 rows and exactly halfway on 40, rounding moves a row's cost by at most 0.000001 USD, and no row rounds to E = 0 (`DESIGN.md` 13.17). So each path's work costs the row's own cost, and only the re-read is a bound (Assumed, and The high end below)
- Each of the 2 models is tried as the parent; the delegate is the `DESIGN.md` 13.3 pick, the other model or a fresh instance of the parent's own
- For each of 50 seeds each task's items are split in half by the seeded hash of `DESIGN.md` 12.2, over the release's two splits joined, as the routing results split them. That gives up what the release's split keeps, each family of related questions in one split: seeded halves can part 808 of the 6,099 items, in 276 shared families. The research note's run on the release's own split is the family-held counterpart (The high end)
- The decision is made from the calibration half only, at bars 0.8 and 0.9, the bars of the response-bank delegation results (`DESIGN.md` 13.14), in both flavors, and scored on the held-out half. It prices the parent and each delegate candidate at that model's own rounded-up mean input and output tokens on the calibration half (`DESIGN.md` 13.9)
- Three strategies are scored on the same held-out items: `decision` (inline on the parent, or delegated to the decision's model), `inline` (the parent does every item itself) and `delegate` (every item goes to the routed delegate). Held-out success is the share of held-out items that passed, and held-out cost the list-price cost of the held-out half, each item priced on the tokens of the model doing the work on each path; both are averaged over the seeds
- The grid is the four base points of [the AutoBench delegation results](../delegation/RESULTS.md), each with a 500-token brief (B), a 500-token result (R) and one later parent call that re-reads them (T = 1): points 0 to 2 put inline work in parent calls of their own with C = 8,000, 64,000 and 200,000 tokens of context the parent already holds, and point 3 (C = 8,000) folds inline work into the parent's next call instead (`inline_separate_call` False; `DESIGN.md` 13.2 prices the folded calls)

## Assumed

- The lossless brief of `DESIGN.md` 13.9: the delegate is credited with its own recorded answer, as if a brief of B tokens carried what it needs, and the parent with its own as if C more tokens of context did not change it
- Every cost is a list price of the registry: the release estimated each call's cost from its token counts at the registry's prices, never a bill, and the rows keep that estimate, not the counts
- The inline re-read is bounded, not measured: a row's split between input and output tokens is not in the release, so the rows take the `low` end, which under-states the re-read, and a saving from delegating that they show holds at any split. Output that a model's history drops, such as its reasoning (`DESIGN.md` 13.2), would put the true re-read below the low end's. The high end's moves are below
- `DESIGN.md` 13.9 prices each path at each model's mean input and output tokens on the calibration half, each rounded up, so the low end's under-statement holds to under one token of each mean, not exactly (`DESIGN.md` 13.17)
- Two models from one vendor; the release's caveats on contamination and on KOR-Bench's few question families, which [the registry-pair research note](../../research/registry-pair.md) quotes, apply here too
- The limits of `DESIGN.md` 13.8: each item's success is its one recorded label, and the bar is held per call

## Results

Means over the 2 parents. `dec_` is the decision, `inl_` always inline and `del_` always delegating; success is held-out success, cost the held-out half's list-price cost in USD, `delegated` the share of seeds on which the decision delegates, and `separate` whether inline work takes parent calls of its own (`True`) or folds into the next call (`False`). Inline does not depend on the bar or the flavor:

```text
$ python evidence/delegation/results.py --table evidence/registry-pair-delegation/results.json
bar  flavor          context  separate  dec_success  dec_cost  inl_success  inl_cost  del_success  del_cost  delegated
---  --------------  -------  --------  -----------  --------  -----------  --------  -----------  --------  ---------
0.8  cost_effective  8000     True      0.906        17.8866   0.903        28.8911   0.906        17.8866   1.000
0.8  cost_effective  64000    True      0.906        17.8866   0.903        207.8337  0.906        17.8866   1.000
0.8  cost_effective  200000   True      0.906        17.8866   0.903        642.4083  0.906        17.8866   1.000
0.8  cost_effective  8000     False     0.914        4.5603    0.903        2.8488    0.906        17.8866   0.160
0.8  cost_blind      8000     True      0.919        31.1444   0.903        28.8911   0.918        20.7646   0.336
0.8  cost_blind      64000    True      0.919        200.8193  0.903        207.8337  0.918        20.7646   0.336
0.8  cost_blind      200000   True      0.919        612.8869  0.903        642.4083  0.918        20.7646   0.336
0.8  cost_blind      8000     False     0.919        6.4732    0.903        2.8488    0.918        20.7646   0.336
0.9  cost_effective  8000     True      0.917        20.2852   0.903        28.8911   0.917        20.2852   1.000
0.9  cost_effective  64000    True      0.917        20.2852   0.903        207.8337  0.917        20.2852   1.000
0.9  cost_effective  200000   True      0.917        20.2852   0.903        642.4083  0.917        20.2852   1.000
0.9  cost_effective  8000     False     0.919        6.1650    0.903        2.8488    0.917        20.2852   0.316
0.9  cost_blind      8000     True      0.919        31.1444   0.903        28.8911   0.918        20.7646   0.336
0.9  cost_blind      64000    True      0.919        200.8193  0.903        207.8337  0.918        20.7646   0.336
0.9  cost_blind      200000   True      0.919        612.8869  0.903        642.4083  0.918        20.7646   0.336
0.9  cost_blind      8000     False     0.919        6.4732    0.903        2.8488    0.918        20.7646   0.336
```

Per parent at bar 0.8 and point 0:

```text
$ python evidence/delegation/results.py --table evidence/registry-pair-delegation/results.json --bar 0.8 --point 0
flavor          parent              delegated  dec_success  dec_cost  inl_success  inl_cost  del_success  del_cost
--------------  ------------------  ---------  -----------  --------  -----------  --------  -----------  --------
cost_effective  openai/gpt-6-luna   1.000      0.906        4.8767    0.884        3.0841    0.906        4.8767
cost_effective  openai/gpt-6.1-sol  1.000      0.906        30.8964   0.921        54.6982   0.906        30.8964
cost_blind      openai/gpt-6-luna   0.657      0.918        7.9276    0.884        3.0841    0.918        7.7548
cost_blind      openai/gpt-6.1-sol  0.016      0.921        54.3612   0.921        54.6982   0.918        33.7745
```

## Reading it

- In `cost_effective` the decision delegates on every seed for every parent at points 0 to 2 at every bar (`delegate_rate` 1.0 on all 12 of their decision rows); at point 3, the work folded into the parent's next call, its rate averaged over the 2 parents is 0.160 and 0.316 at bars 0.8 and 0.9.
- At bar 0.8 and point 0 (8,000 context tokens), averaged over the 2 parents, the `cost_effective` decision costs 17.8866 USD on a held-out half against 28.8911 for always inline (1.62 times as much), with held-out success 0.906 against 0.903.
- At bar 0.9 and point 0 it costs 20.2852 USD against 28.8911 for always inline, with held-out success 0.917 against 0.903.
- At bar 0.8 and point 0 the `cost_effective` decision costs more than always inline for 1 of the 2 parents: `openai/gpt-6-luna` (4.8767 against 3.0841 USD, held-out success 0.906 against 0.884).
- `results.json` is 33,994 bytes.

## The high end

The tables above price every row at the `low` end (Method). [The research note](../../research/registry-pair-delegation.md) runs the decision at both ends once, on the release's own split (its calibration split calibrating and its final split scoring, so each family of questions stays in one half), at revision `63336f2` with no seeds, so its numbers compare with each other, not with the tables above, which average 50 seeded halves. Its Results block, at the same bars, flavors and four points:

- 4 of the 32 (parent, flavor, bar, point) groups have a task whose mode or delegate differs between the ends, at most 1 of the 31 tasks in one group, all at point 3, where inline work folds into the parent's next call.
- `openai/gpt-6-luna` as parent, `cost_effective`, bar 0.8, point 3: the decision delegates 9 of 31 tasks at the low end and 10 at the high end, at 3.730746 and 3.927148 USD for held-out success 0.912 at both ends; always inline costs 0.555591 and 0.925166.
- `openai/gpt-6-luna` as parent, `cost_effective`, bar 0.9, point 3: the decision delegates 18 of 31 tasks at the low end and 19 at the high end, at 6.670466 and 6.745057 USD for held-out success 0.920 at both ends; always inline costs 0.555591 and 0.925166.
- `openai/gpt-6.1-sol` as parent, `cost_effective`, bar 0.8, point 3: the decision delegates 0 of 31 tasks at the low end and 1 at the high end, at 5.129796 and 8.672121 USD for held-out success 0.926 and 0.925; always inline costs 5.129796 and 8.533284.
- `openai/gpt-6.1-sol` as parent, `cost_effective`, bar 0.9, point 3: the decision delegates 1 of 31 tasks at the low end and 2 at the high end, at 5.506934 and 9.021779 USD for held-out success 0.926 and 0.925; always inline costs 5.129796 and 8.533284.
- Always delegating has the same held-out success and cost at both ends in every group, and always inline the same success; always inline costs more at the high end, by one amount at every bar, flavor and context when inline work takes a call of its own: 0.739149 USD with `openai/gpt-6-luna` as parent and 6.806976 with `openai/gpt-6.1-sol`, and 0.369575 and 3.403488 folded into the next call.

## Regenerate

The converter downloads the three pinned files (7,522,421 bytes) into `~/.cache/ai-model-routing-evidence/registry-pair/` on its first run and checks each against its pinned size and sha256 (`DESIGN.md` 12.23); the matrix it writes is not committed. The results script then runs in about 3 seconds. The `evidence` workflow reruns these commands on GitHub and fails if `results.json` changes by a byte (`DESIGN.md` 12.13, v1.472).

```bash
python -m pip install -e .
python evidence/registry-pair/convert.py --out registry-pair-matrix.jsonl
python evidence/registry-pair-delegation/results.py --matrix registry-pair-matrix.jsonl --out evidence/registry-pair-delegation/results.json
python evidence/delegation/results.py --table evidence/registry-pair-delegation/results.json
python evidence/delegation/results.py --table evidence/registry-pair-delegation/results.json --bar 0.8 --point 0
```
