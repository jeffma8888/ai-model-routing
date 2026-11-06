# Delegation on AutoBench 2026: inline or sub-agent on held-out questions

What the inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5) does on questions it never saw, next to always working inline and always delegating, measured by `evaluate_delegation` (`DESIGN.md` 13.9) on the public [AutoBench Router Benchmark 2026](https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10) matrix at revision [4375518](https://huggingface.co/datasets/AutoBench/router-benchmark-2026-10/tree/43755180be7d8097068982d7a3f37fc04cd15379) (licence CC-BY-4.0; the card asks users to cite its paper). The matrix and its labels are those of [the AutoBench results](../autobench-2026/RESULTS.md): 20 models from 2026, 203 questions pooled into one task, `all`, and a Delta-Hit label on every answer. The file behind every number here is [results.json](results.json) (202,337 bytes), made by `evidence/delegation/results.py` (`DESIGN.md` 13.10): one summary row per (bar, flavor, point, parent, strategy), with no per-seed cells.

## Method

- Every one of the 20 pool models is tried as the parent. For each of 50 seeds the questions are split in half by the seeded hash of `DESIGN.md` 12.2. The decision is made from the calibration half only (each model's accepted count there and its own mean input and output tokens per answer there, which price it, with the median input and output tokens of all the half's answers as the task's expected sizes for the context-window checks), at bar 0.7 and at bar 0.8, in both flavors, and scored on the held-out half
- Three strategies are scored on the same held-out questions: `decision` (inline on the parent, or delegated to the decision's model), `inline` (the parent does every question itself, even where its context is full) and `delegate` (every question goes to the routed delegate)
- Held-out success is the share of the held-out answers the label accepts, and held-out cost the total list-price cost of the held-out half from each answer's own input and output tokens, each averaged over the 50 seeds
- The grid fixes what no public matrix records, at three points that differ only in the context the parent already holds: C = 8,000, 64,000 and 200,000 tokens, each with a 500-token brief (B), a 500-token result (R), one later parent call that re-reads them (T = 1), and inline work in a parent call of its own (`inline_separate_call` True). At 200,000 tokens `meta/muse-glimmer-30b` and `openai/gpt-oss-120b` (context windows of 131,072 and 131,000 tokens) have no room, so the decision must delegate for them there

## What is measured and what is assumed

- Measured, from the matrix: whether each model's answer to each question was accepted, and the input and output tokens of that call (the output tokens include reasoning tokens)
- From the pool registry (`convert.py --registry`): list prices, families and context windows. Every cost is a list-price estimate, never a billed cost
- Assumed, the grid: C, B, R, T and `inline_separate_call`. Results are stated per point and never pooled across points
- Assumed, quality: the delegate is credited with its recorded answer to the whole question, as if a brief of B tokens carried everything the item needs; the parent is credited with its recorded answer as if C more tokens of context did not change it. Neither a lossy brief nor long-context degradation is measured, and each would lower one path's success. So these numbers show what the decision rule does under these assumptions, not the quality of a real hand-off
- One call per path and no prompt caching (`DESIGN.md` 13.8)

## Results

Means over the 20 parents. `dec_` is the decision, `inl_` always inline and `del_` always delegating; success is held-out success, cost the held-out half's list-price cost in USD, and `delegated` the share of seeds on which the decision delegates. Inline does not depend on the bar or the flavor:

```text
$ python evidence/delegation/results.py --table evidence/delegation/results.json
bar  flavor          context  dec_success  dec_cost  inl_success  inl_cost  del_success  del_cost  delegated
---  --------------  -------  -----------  --------  -----------  --------  -----------  --------  ---------
0.7  cost_effective  8000     0.869        0.6282    0.670        1.6931    0.869        0.6282    1.000
0.7  cost_effective  64000    0.869        0.6282    0.670        6.1849    0.869        0.6282    1.000
0.7  cost_effective  200000   0.869        0.6282    0.670        17.0936   0.869        0.6282    1.000
0.7  cost_blind      8000     0.857        2.5582    0.670        1.6931    0.857        2.4768    0.944
0.7  cost_blind      64000    0.857        3.0624    0.670        6.1849    0.857        2.4768    0.944
0.7  cost_blind      200000   0.857        4.2869    0.670        17.0936   0.857        2.4768    0.944
0.8  cost_effective  8000     0.855        2.1372    0.670        1.6931    0.855        2.1372    1.000
0.8  cost_effective  64000    0.855        2.1372    0.670        6.1849    0.855        2.1372    1.000
0.8  cost_effective  200000   0.855        2.1372    0.670        17.0936   0.855        2.1372    1.000
0.8  cost_blind      8000     0.857        2.5582    0.670        1.6931    0.857        2.4768    0.944
0.8  cost_blind      64000    0.857        3.0624    0.670        6.1849    0.857        2.4768    0.944
0.8  cost_blind      200000   0.857        4.2869    0.670        17.0936   0.857        2.4768    0.944
```

One row per parent at bar 0.8 and C = 64,000 tokens (point 1):

```text
$ python evidence/delegation/results.py --table evidence/delegation/results.json --bar 0.8 --point 1
flavor          parent                             delegated  dec_success  dec_cost  inl_success  inl_cost  del_success  del_cost
--------------  ---------------------------------  ---------  -----------  --------  -----------  --------  -----------  --------
cost_effective  anthropic/claude-sonnet-5          1.000      0.855        2.7387    0.859        16.6988   0.855        2.7387
cost_effective  deepseek/deepseek-v4-flash-0731    1.000      0.855        1.8511    0.681        0.6201    0.855        1.8511
cost_effective  google/gemini-3.7-flash            1.000      0.855        1.9969    0.774        3.1107    0.855        1.9969
cost_effective  google/gemma-4-31b-it              1.000      0.855        1.8744    0.489        0.9465    0.855        1.8744
cost_effective  meta/muse-glimmer-30b              1.000      0.855        1.9728    0.554        2.4668    0.855        1.9728
cost_effective  meta/muse-spark-1.2                1.000      0.855        2.2949    0.705        9.5289    0.855        2.2949
cost_effective  minimax/minimax-m3                 1.000      0.855        1.9475    0.769        2.4575    0.855        1.9475
cost_effective  moonshotai/kimi-k2.6               1.000      0.855        2.0512    0.776        5.2375    0.855        2.0512
cost_effective  nvidia/nemotron-3-ultra-550b-a55b  1.000      0.855        2.1300    0.603        4.7090    0.855        2.1300
cost_effective  nvidia/nemotron-3.5-lightning      1.000      0.855        1.8521    0.415        0.6851    0.855        1.8521
cost_effective  openai/gpt-5.6-luna                1.000      0.855        1.9272    0.872        1.7156    0.855        1.9272
cost_effective  openai/gpt-5.6-sol                 1.000      0.855        2.7387    0.882        16.9574   0.855        2.7387
cost_effective  openai/gpt-oss-120b                1.000      0.855        1.8486    0.442        0.3645    0.855        1.8486
cost_effective  qwen/qwen3.5-9b                    1.000      0.855        1.8536    0.276        0.8792    0.855        1.8536
cost_effective  qwen/qwen3.8-max                   1.000      0.855        2.5358    0.853        14.9602   0.855        2.5358
cost_effective  tencent/hy3                        1.000      0.855        1.8793    0.683        1.0119    0.855        1.8793
cost_effective  xai/grok-4.3                       1.000      0.855        2.2061    0.558        8.9374    0.855        2.2061
cost_effective  xai/grok-4.6                       1.000      0.855        2.5358    0.689        15.1797   0.855        2.5358
cost_effective  zai/glm-5.2                        1.000      0.855        2.1757    0.756        7.4250    0.855        2.1757
cost_effective  zai/glm-5.3                        1.000      0.855        2.3329    0.755        9.8066    0.855        2.3329
cost_blind      anthropic/claude-sonnet-5          0.880      0.857        4.6467    0.859        16.6988   0.857        3.0783
cost_blind      deepseek/deepseek-v4-flash-0731    1.000      0.857        2.1907    0.681        0.6201    0.857        2.1907
cost_blind      google/gemini-3.7-flash            1.000      0.857        2.3365    0.774        3.1107    0.857        2.3365
cost_blind      google/gemma-4-31b-it              1.000      0.857        2.2140    0.489        0.9465    0.857        2.2140
cost_blind      meta/muse-glimmer-30b              1.000      0.857        2.3124    0.554        2.4668    0.857        2.3124
cost_blind      meta/muse-spark-1.2                1.000      0.857        2.6345    0.705        9.5289    0.857        2.6345
cost_blind      minimax/minimax-m3                 1.000      0.857        2.2870    0.769        2.4575    0.857        2.2870
cost_blind      moonshotai/kimi-k2.6               0.980      0.857        2.4859    0.776        5.2375    0.857        2.3908
cost_blind      nvidia/nemotron-3-ultra-550b-a55b  1.000      0.857        2.4696    0.603        4.7090    0.857        2.4696
cost_blind      nvidia/nemotron-3.5-lightning      1.000      0.857        2.1917    0.415        0.6851    0.857        2.1917
cost_blind      openai/gpt-5.6-luna                0.760      0.858        2.5326    0.872        1.7156    0.857        2.2668
cost_blind      openai/gpt-5.6-sol                 0.300      0.862        12.3167   0.882        16.9574   0.857        3.0783
cost_blind      openai/gpt-oss-120b                1.000      0.857        2.1881    0.442        0.3645    0.857        2.1881
cost_blind      qwen/qwen3.5-9b                    1.000      0.857        2.1932    0.276        0.8792    0.857        2.1932
cost_blind      qwen/qwen3.8-max                   0.960      0.857        3.4216    0.853        14.9602   0.857        2.8754
cost_blind      tencent/hy3                        1.000      0.857        2.2189    0.683        1.0119    0.857        2.2189
cost_blind      xai/grok-4.3                       1.000      0.857        2.5457    0.558        8.9374    0.857        2.5457
cost_blind      xai/grok-4.6                       1.000      0.857        2.8754    0.689        15.1797   0.857        2.8754
cost_blind      zai/glm-5.2                        1.000      0.857        2.5153    0.756        7.4250    0.857        2.5153
cost_blind      zai/glm-5.3                        1.000      0.857        2.6725    0.755        9.8066    0.857        2.6725
```

The quality assumption above credits every hand-off with a lossless brief. The break-even table puts a number on how much a lossy one may lose, from the same file with no new run. `del_margin` is always delegating's held-out success minus always inline's: the success every hand-off could lose before always delegating does no better than always inline. `dec_breakeven` is the decision's held-out success minus always inline's, divided by its `delegated` share: the drop in held-out success on the seeds it delegates at which the decision falls to always inline's success (exact here, where all 203 questions are one task; `-` where the decision never delegates). A value below zero means the hand-off already scores below always inline with a lossless brief. At bar 0.8 and C = 64,000 tokens (point 1):

```text
$ python evidence/delegation/results.py --breakeven evidence/delegation/results.json --bar 0.8 --point 1
flavor          parent                             delegated  dec_success  inl_success  del_success  del_margin  dec_breakeven
--------------  ---------------------------------  ---------  -----------  -----------  -----------  ----------  -------------
cost_effective  anthropic/claude-sonnet-5          1.000      0.855        0.859        0.855        -0.003      -0.003
cost_effective  deepseek/deepseek-v4-flash-0731    1.000      0.855        0.681        0.855        0.175       0.175
cost_effective  google/gemini-3.7-flash            1.000      0.855        0.774        0.855        0.081       0.081
cost_effective  google/gemma-4-31b-it              1.000      0.855        0.489        0.855        0.366       0.366
cost_effective  meta/muse-glimmer-30b              1.000      0.855        0.554        0.855        0.302       0.302
cost_effective  meta/muse-spark-1.2                1.000      0.855        0.705        0.855        0.150       0.150
cost_effective  minimax/minimax-m3                 1.000      0.855        0.769        0.855        0.087       0.087
cost_effective  moonshotai/kimi-k2.6               1.000      0.855        0.776        0.855        0.079       0.079
cost_effective  nvidia/nemotron-3-ultra-550b-a55b  1.000      0.855        0.603        0.855        0.252       0.252
cost_effective  nvidia/nemotron-3.5-lightning      1.000      0.855        0.415        0.855        0.440       0.440
cost_effective  openai/gpt-5.6-luna                1.000      0.855        0.872        0.855        -0.016      -0.016
cost_effective  openai/gpt-5.6-sol                 1.000      0.855        0.882        0.855        -0.027      -0.027
cost_effective  openai/gpt-oss-120b                1.000      0.855        0.442        0.855        0.413       0.413
cost_effective  qwen/qwen3.5-9b                    1.000      0.855        0.276        0.855        0.579       0.579
cost_effective  qwen/qwen3.8-max                   1.000      0.855        0.853        0.855        0.003       0.003
cost_effective  tencent/hy3                        1.000      0.855        0.683        0.855        0.173       0.173
cost_effective  xai/grok-4.3                       1.000      0.855        0.558        0.855        0.298       0.298
cost_effective  xai/grok-4.6                       1.000      0.855        0.689        0.855        0.167       0.167
cost_effective  zai/glm-5.2                        1.000      0.855        0.756        0.855        0.099       0.099
cost_effective  zai/glm-5.3                        1.000      0.855        0.755        0.855        0.100       0.100
cost_blind      anthropic/claude-sonnet-5          0.880      0.857        0.859        0.857        -0.002      -0.002
cost_blind      deepseek/deepseek-v4-flash-0731    1.000      0.857        0.681        0.857        0.177       0.177
cost_blind      google/gemini-3.7-flash            1.000      0.857        0.774        0.857        0.083       0.083
cost_blind      google/gemma-4-31b-it              1.000      0.857        0.489        0.857        0.368       0.368
cost_blind      meta/muse-glimmer-30b              1.000      0.857        0.554        0.857        0.304       0.304
cost_blind      meta/muse-spark-1.2                1.000      0.857        0.705        0.857        0.152       0.152
cost_blind      minimax/minimax-m3                 1.000      0.857        0.769        0.857        0.089       0.089
cost_blind      moonshotai/kimi-k2.6               0.980      0.857        0.776        0.857        0.081       0.083
cost_blind      nvidia/nemotron-3-ultra-550b-a55b  1.000      0.857        0.603        0.857        0.254       0.254
cost_blind      nvidia/nemotron-3.5-lightning      1.000      0.857        0.415        0.857        0.442       0.442
cost_blind      openai/gpt-5.6-luna                0.760      0.858        0.872        0.857        -0.015      -0.019
cost_blind      openai/gpt-5.6-sol                 0.300      0.862        0.882        0.857        -0.025      -0.069
cost_blind      openai/gpt-oss-120b                1.000      0.857        0.442        0.857        0.415       0.415
cost_blind      qwen/qwen3.5-9b                    1.000      0.857        0.276        0.857        0.581       0.581
cost_blind      qwen/qwen3.8-max                   0.960      0.857        0.853        0.857        0.004       0.005
cost_blind      tencent/hy3                        1.000      0.857        0.683        0.857        0.175       0.175
cost_blind      xai/grok-4.3                       1.000      0.857        0.558        0.857        0.300       0.300
cost_blind      xai/grok-4.6                       1.000      0.857        0.689        0.857        0.168       0.168
cost_blind      zai/glm-5.2                        1.000      0.857        0.756        0.857        0.101       0.101
cost_blind      zai/glm-5.3                        1.000      0.857        0.755        0.857        0.102       0.102
```

## Reading it

- At bar 0.7, `cost_effective` delegates on every seed for every parent and holds a mean held-out success of 0.869 at 0.6282 USD at every point
- At bar 0.8, `cost_effective` delegates on every seed for every parent, so it scores and costs the same as always delegating: a mean held-out success over the 20 parents of 0.855 at every point, against 0.670 for always inline
- At bar 0.8 the `cost_effective` decision costs more than always inline at 8,000 context tokens (2.1372 against 1.6931 USD) and far less at 200,000 (2.1372 against 17.0936), where the parent's own call for the work re-reads the whole context
- With `openai/gpt-5.6-sol` as the parent at bar 0.8 and 64,000 context tokens, always inline scores 0.882 at 16.9574 USD; `cost_effective` delegates on 100.0% of seeds and scores 0.855 at 2.7387 USD, 16% of the inline cost: a strong, expensive parent gives up a little held-out success for a large saving
- With `openai/gpt-5.6-luna` as the parent at bar 0.8 and 64,000 context tokens, `cost_blind` delegates on 76.0% of seeds and scores 0.858 against 0.872 inline, at 2.5326 against 1.7156 USD. `cost_blind` never compares cost: outside a full context it decides on the lower bounds alone (`DESIGN.md` 13.5 rows 2, 4, 5 and 7), and a higher bound on the calibration half is not always a higher rate on the held-out half
- At bar 0.8 and 64,000 context tokens, `cost_effective` delegates on every seed for every parent, so `dec_breakeven` equals `del_margin`: a lossy brief may lower the delegated held-out success by a mean of 0.186 over the 20 parents before the decision does no better than always inline. The minimum is -0.027, with `openai/gpt-5.6-sol` as the parent, and 3 of the 20 parents are below zero: they already score higher inline than the delegate does with a lossless brief

## Regenerate

The run takes a few seconds; the dataset downloads into a cache folder outside the repo (see [the AutoBench evidence README](../autobench-2026/README.md)):

```bash
python -m pip install -e .
python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens --registry autobench-pool.json
python evidence/delegation/results.py --matrix autobench-tokens.jsonl --registry autobench-pool.json --out evidence/delegation/results.json
python evidence/delegation/results.py --table evidence/delegation/results.json
python evidence/delegation/results.py --table evidence/delegation/results.json --bar 0.8 --point 1
```
