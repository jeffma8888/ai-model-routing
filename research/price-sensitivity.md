# How far a price error moves `cost_effective` routing

README Limitations says prices are a dated snapshot and asks the reader to refresh `models.json`, but no note said how much a stale or wrong price changes what `cost_effective` routing picks and what the picks then score and cost. `cost_effective` takes the cheapest of the models whose calibration bound clears the bar, so a price error matters only where it reorders the models that clear. This note reruns the LLMRouterBench routing evaluation behind [the committed results](../evidence/llmrouterbench/RESULTS.md), whose cost is recorded per call, with one model's price halved or doubled at a time ([DESIGN.md](../DESIGN.md) 12.22). Its numbers are the output of [price_sensitivity.py](price_sensitivity.py), which stops unless its unscaled rows are the committed ones; [llmrouterbench-seeds.md](llmrouterbench-seeds.md) reads the same evaluation seed by seed.

## Facts

- A wrong price for one model moves `cost_effective` routing most at the lowest bar, where it can change a large share of the picks, move the held-out success either way and raise the cost, and barely at all at the highest bar, where it changes few picks and moves neither success nor cost by more than a few thousandths
- Data: the 12.18 matrix, 9 tasks, 13 models and 12,066 items, flavor `cost_effective`, 50 seeds, bars 0.1 and 0.8, the lowest and highest of 8, so 450 (task, seed) cells per bar; each model's calibration mean cost times 0.5 and times 2.0 in turn, 26 runs per bar
- Bar 0.1, where the committed row has success 0.5528 at cost 39.4802: the 26 runs change 0 to 177 of the 450 cells, with a success gap of -0.0236 to +0.0182 and a cost ratio of 1.000 to 1.829. Halving `deepseek/deepseek-v3-0324`'s price changes 177 cells (39.3%) and gives a gap of -0.0236 (success 0.5293) at 1.009 times the cost; halving `openai/gpt-5`'s changes 50 (11.1%) for +0.0182 (0.5711) at 1.829 times; doubling `deepseek/deepseek-r1-0528`'s or halving `z-ai/glm-4.6`'s changes 51 (11.3%) at 1.362 times; `qwen/qwen3-235b-a22b-2507` changes 100 (22.2%) halved and 133 (29.6%) doubled
- Bar 0.8, where the committed row has success 0.6060 at cost 154.0269: the 26 runs change 0 to 48 cells, with a gap of -0.0030 to +0.0001 and a ratio of 1.000 to 1.002; the most, 48 cells (10.7%) for a gap of -0.0030, come from doubling `deepseek/deepseek-v3.1-terminus`'s price or halving `qwen/qwen3-235b-a22b-2507`'s
- `anthropic/claude-sonnet-4`, `google/gemini-2.5-flash`, `internlm/intern-s1` and `moonshotai/kimi-k2-0905` change no pick at either bar or factor

## Method

- The script reads the config of `evidence/llmrouterbench/results.json` (its bars, seeds, `calibration_fraction`, `min_samples` and `confidence`) and runs `evaluate` (12.3) with flavor `cost_effective` at the lowest and highest bars on the matrix the 12.18 converter writes, the matrix the committed file was made from (12.19)
- For each cell, a (task, seed) split at a bar, it rebuilds the router 12.3 builds, each model with its calibration count and priced at its mean calibration cost, then multiplies one model's mean by 0.5 or 2.0 and asks the router again. Both factors are powers of two, so a scaled mean is exactly the mean of the scaled costs: the router `evaluate` would build on a matrix with that model's costs scaled, which a test checks on a small matrix
- Unscaled, the rebuilt router must pick each cell's routed model and the pooled rows must be the committed `routed` rows, or the script stops
- A pick is scored on the held-out half at the recorded costs: the error is in the price the router believes, and the bill is the one the dataset recorded. A row's success and cost pool a seed's 9 task halves and average over the 50 seeds, as 12.3's summary does; the gap is that success minus the committed row's, a gap that rounds to zero keeping its sign, and the ratio is the cost over the committed row's
- The scale stands for any error in the price the router uses: a stale snapshot, a vendor change not yet copied or a wrong row

## Results

```text
$ python research/price_sensitivity.py --matrix llmrouterbench-matrix.jsonl
LLMRouterBench (evidence/llmrouterbench/results.json): 9 tasks, 13 models, 12,066 items, 50 seeds, flavor cost_effective, bars 0.1 and 0.8, the lowest and highest of 8
the router is built with one model's calibration mean cost times 0.5 or 2.0, every other model's as recorded, and each pick is scored at the recorded held-out costs
bar 0.1: committed routed success 0.5528, cost 39.4802; per model and factor, the cells of 450 whose routed model changes, the held-out success with its gap and the cost with its ratio to the committed row
  anthropic/claude-sonnet-4: times 0.5: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000)
  deepseek/deepseek-r1-0528: times 0.5: 1 of 450 cells change (0.2%), success 0.5528 (-0.0000), cost 39.4928 (1.000); times 2.0: 51 of 450 cells change (11.3%), success 0.5522 (-0.0006), cost 53.7659 (1.362)
  deepseek/deepseek-v3-0324: times 0.5: 177 of 450 cells change (39.3%), success 0.5293 (-0.0236), cost 39.8281 (1.009); times 2.0: 44 of 450 cells change (9.8%), success 0.5538 (+0.0010), cost 39.4906 (1.000)
  deepseek/deepseek-v3.1-terminus: times 0.5: 177 of 450 cells change (39.3%), success 0.5494 (-0.0035), cost 39.8537 (1.009); times 2.0: 56 of 450 cells change (12.4%), success 0.5388 (-0.0141), cost 39.5231 (1.001)
  google/gemini-2.5-flash: times 0.5: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000)
  google/gemini-2.5-pro: times 0.5: 3 of 450 cells change (0.7%), success 0.5528 (-0.0000), cost 39.6343 (1.004); times 2.0: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000)
  internlm/intern-s1: times 0.5: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000)
  moonshotai/kimi-k2-0905: times 0.5: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000)
  openai/gpt-5: times 0.5: 50 of 450 cells change (11.1%), success 0.5711 (+0.0182), cost 72.2013 (1.829); times 2.0: 3 of 450 cells change (0.7%), success 0.5528 (-0.0000), cost 39.6343 (1.004)
  openai/gpt-5-chat: times 0.5: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000); times 2.0: 13 of 450 cells change (2.9%), success 0.5525 (-0.0003), cost 39.4894 (1.000)
  qwen/qwen3-235b-a22b-2507: times 0.5: 100 of 450 cells change (22.2%), success 0.5510 (-0.0019), cost 39.5674 (1.002); times 2.0: 133 of 450 cells change (29.6%), success 0.5437 (-0.0091), cost 39.7008 (1.006)
  qwen/qwen3-235b-a22b-thinking-2507: times 0.5: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000); times 2.0: 1 of 450 cells change (0.2%), success 0.5528 (-0.0000), cost 39.4928 (1.000)
  z-ai/glm-4.6: times 0.5: 51 of 450 cells change (11.3%), success 0.5522 (-0.0006), cost 53.7659 (1.362); times 2.0: 0 of 450 cells change (0.0%), success 0.5528 (+0.0000), cost 39.4802 (1.000)
  over the 26: cells changed 0 to 177, success gap -0.0236 to +0.0182, cost ratio 1.000 to 1.829
bar 0.8: committed routed success 0.6060, cost 154.0269; per model and factor, the cells of 450 whose routed model changes, the held-out success with its gap and the cost with its ratio to the committed row
  anthropic/claude-sonnet-4: times 0.5: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000)
  deepseek/deepseek-r1-0528: times 0.5: 4 of 450 cells change (0.9%), success 0.6060 (-0.0000), cost 154.0699 (1.000); times 2.0: 10 of 450 cells change (2.2%), success 0.6061 (+0.0001), cost 154.1468 (1.001)
  deepseek/deepseek-v3-0324: times 0.5: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000)
  deepseek/deepseek-v3.1-terminus: times 0.5: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000); times 2.0: 48 of 450 cells change (10.7%), success 0.6030 (-0.0030), cost 154.0809 (1.000)
  google/gemini-2.5-flash: times 0.5: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000)
  google/gemini-2.5-pro: times 0.5: 5 of 450 cells change (1.1%), success 0.6060 (-0.0000), cost 154.3545 (1.002); times 2.0: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000)
  internlm/intern-s1: times 0.5: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000)
  moonshotai/kimi-k2-0905: times 0.5: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000)
  openai/gpt-5: times 0.5: 9 of 450 cells change (2.0%), success 0.6061 (+0.0001), cost 154.1346 (1.001); times 2.0: 5 of 450 cells change (1.1%), success 0.6060 (-0.0000), cost 154.3545 (1.002)
  openai/gpt-5-chat: times 0.5: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000)
  qwen/qwen3-235b-a22b-2507: times 0.5: 48 of 450 cells change (10.7%), success 0.6030 (-0.0030), cost 154.0809 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000)
  qwen/qwen3-235b-a22b-thinking-2507: times 0.5: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000); times 2.0: 4 of 450 cells change (0.9%), success 0.6060 (-0.0000), cost 154.0699 (1.000)
  z-ai/glm-4.6: times 0.5: 1 of 450 cells change (0.2%), success 0.6060 (-0.0000), cost 154.0392 (1.000); times 2.0: 0 of 450 cells change (0.0%), success 0.6060 (+0.0000), cost 154.0269 (1.000)
  over the 26: cells changed 0 to 48, success gap -0.0030 to +0.0001, cost ratio 1.000 to 1.002
```

## Reading it

- The more models clear a bar, the more the pick turns on the price order, so a price error moves the most picks at the lowest bar; at the highest bar the pick turns on which models clear, and a price error reorders few of them
- A moved pick need not lose success: the router picked the cheapest clearing model by the recorded prices, and a wrong price makes it take another clearing model, which may score better or worse on the held-out half. Halving `deepseek/deepseek-v3-0324`'s price takes it on 177 cells at about the same cost and a gap of -0.0236; halving `openai/gpt-5`'s takes a stronger, dearer model on 50 cells, +0.0182 for 1.829 times the cost, a trade a caller who wants it makes with a higher bar or `cost_blind`, not with a wrong price
- No cost ratio is below 1.000, and the highest are 1.829 at bar 0.1 and 1.002 at bar 0.8: where some model clears, the committed pick is the cheapest clearing model at the recorded calibration costs, so a pick that a wrong price moves costs no less on the calibration half, more unless two models tie there, and here the held-out half follows it
- So a stale price is cheap to carry at a high bar, and at a low one it can cost a gap of -0.0236 or 1.829 times the bill, depending on which model it belongs to

## Recommendation

- Add a sentence to the prices bullet of README Limitations (follow-on row DOC30): on LLMRouterBench, one model's price halved or doubled changed up to 39.3% of the `cost_effective` picks at the lowest bar, for a success gap of -0.0236 to +0.0182 and up to 1.829 times the cost, and at most 10.7%, -0.0030 and 1.002 times at the highest; so refresh `models.json` whenever a vendor changes the price of a model in the pool, most of all for a task with a low bar. The note gives no fixed interval: it measures what a price error does, not how often prices change
- No change to the router: it cannot tell a wrong price from a right one, and the size of the effect depends on the pool and the bar, which only the caller knows

## Limits

- One dataset, whose recorded per-call costs stand for prices, and its pool of 13 models; a pool whose prices sit closer together or further apart moves differently
- One model at a time and the factors 0.5 and 2.0 alone; errors in several prices at once, or smaller ones, are not measured
- `cost_effective` alone, and the lowest and highest of the 8 bars
- A ratio is rounded to three decimals, so a held-out cost change under a thousandth of the committed cost shows as 1.000

## Regenerate

```bash
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python research/price_sensitivity.py --matrix llmrouterbench-matrix.jsonl
```
