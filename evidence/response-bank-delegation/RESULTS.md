# Delegation on the LLM Routing Response Bank: inline or sub-agent on held-out single calls

What the inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5) does on items it never saw, next to always working inline and always delegating, measured by `evaluate_delegation` (`DESIGN.md` 13.9) on the public [LLM Routing Response Bank](https://huggingface.co/datasets/Lurume/llm-routing-response-bank) at revision [`547beb31ecd8f12b116b87eb4f56feee73edda6c`](https://huggingface.co/datasets/Lurume/llm-routing-response-bank/tree/547beb31ecd8f12b116b87eb4f56feee73edda6c) (2026-09-17). Each item is one benchmark question, which every model answered in one recorded call labelled by the response's `quality`, as on AutoBench and LLMRouterBench and unlike the multi-call conversations of tau2-bench. The rows come from the converter described in [the response-bank evidence README](../response-bank/README.md), at its defaults; the models' list prices and windows are in [registry.json](registry.json), with the pages and the checks behind them in [the research note](../../research/delegation-datasets.md); the committed results are [results.json](results.json). Every cost is a list-price estimate, never a billed cost.

Licence: the dataset card names no standard licence, and the dataset's LICENSE file calls ODC-BY-4.0 (Open Data Commons Attribution License v4.0) its planned licence, saying that until its final wording "you may use, redistribute, and build on this data under ODC-BY-4.0 terms with attribution to this dataset repository"; its per-family terms are quoted in [the response-bank routing results](../response-bank/RESULTS.md). Attribution, as those terms ask: these results derive from the LLM Routing Response Bank, from the dataset repository https://huggingface.co/datasets/Lurume/llm-routing-response-bank; the card's Citation section reads "To be added." at this revision, so the repository is named instead. This repo commits no part of the dataset: `results.json` holds only the run's settings, item counts and mean results.

## Method

- Matrix: the converter's default output, the one the routing results read: 5 models on the items of 4 benchmark families, one task per family, each row a success when the response's `quality` is 1 (`DESIGN.md` 12.20). As the size of the work's input the script reads the converter's input count, the part of the prompt not read from the cache (Assumed)
- The pool is all five models of [the response-bank routing results](../response-bank/RESULTS.md), each priced at the input and output pair its bills give on its responses with no cache read, so no model of those results is left out. They are `deepseek/deepseek-v4-flash`, `deepseek/deepseek-v4-pro`, `moonshotai/kimi-k2.7-code`, `z-ai/glm-5.3` and `z-ai/glm-5.3-flash`; a vendor page states the same pair for the last three (`DESIGN.md` 13.14)
- 4 items are dropped for a null token count (4 in `mmlu_pro`), so 13,311 items remain. They are `mmlu_pro:10969`, `mmlu_pro:10990`, `mmlu_pro:11007` and `mmlu_pro:7872`, which hold the six cells the converter marks `missing`, with no response and so no token counts; pricing them at a count of 0 would make work of unknown size free. The routing results keep them, each `missing` cell a miss at no cost. That leaves 66,555 rows: `aime` 30, `gpqa_diamond` 198, `livecodebench` 1,055 and `mmlu_pro` 12,028 items
- Every one of the 5 models is tried as the parent. For each of 50 seeds each task's items are split in half by the seeded hash of `DESIGN.md` 12.2. The decision is made from the calibration half only, at bars 0.8 and 0.9, the bars of the routing results (every tenth strictly inside the span of the per-task, per-model success rates, 0.767 to 0.967), in both flavors, and scored on the held-out half. It prices the parent and each delegate candidate at that model's own rounded-up mean input and output tokens on the calibration half, and the two window checks read the task's expected sizes, the low medians of input and output tokens over the calibration rows of every model (`DESIGN.md` 13.9), which sum to 1,265 to 11,045 tokens over the cells
- Three strategies are scored on the same held-out items: `decision` (inline on the parent, or delegated to the decision's model), `inline` (the parent does every item itself) and `delegate` (every item goes to the routed delegate). Held-out success is the share of held-out items that passed, and held-out cost the list-price cost of the held-out half, each item priced on the tokens of the model doing the work on each path; both are averaged over the seeds
- The grid is the four base points of [the AutoBench delegation results](../delegation/RESULTS.md), each with a 500-token brief (B), a 500-token result (R) and one later parent call that re-reads them (T = 1): points 0 to 2 put inline work in parent calls of their own with C = 8,000, 64,000 and 200,000 tokens of context the parent already holds, and point 3 (C = 8,000) folds inline work into the parent's next call instead (`inline_separate_call` False; `DESIGN.md` 13.2 prices the folded calls)
- `aime` has 30 items, so its calibration half holds 10 to 21 over the seeds, under the default `min_samples` of 30 on all 50: no model clears a bar there, and all 2,000 `aime` cells of each flavor are 13.5 row 7 (`none_clear`).
- Outside `aime`, 60 of each flavor's 3,000 cells at bar 0.8 and 2,980 of its 3,000 at bar 0.9 are `none_clear`: at bar 0.9 no model clears `livecodebench` or `mmlu_pro` on any seed, and a model clears `gpqa_diamond` on 1 of the 50 seeds.
- Inline is blocked on no cell: at point 2, C = 200,000 is under every parent's window, 262,144 for `moonshotai/kimi-k2.7-code` and 1,000,000 for the other four.
- Of the 8,000 `cost_effective` cells, 5,040 `none_clear`, 2,062 `delegate_cheaper`, 848 `parent_below_bar` and 50 `inline_cheaper`. `none_clear` is 13.5 row 7: no model clears the bar, so the calibration bounds decide, not cost.

## Assumed

- The lossless brief of `DESIGN.md` 13.9: the delegate is credited with its own recorded answer, as if a brief of B tokens carried what it needs, and the parent with its own as if C more tokens of context did not change it
- Every cost is a list price of the registry applied to the recorded token counts, never a bill. Each model is priced at the pair its bills give on its responses with no cache read, so on those responses the two agree; summed over the kept rows a model's list cost is 0.9999 (`deepseek/deepseek-v4-flash`), 0.9995 (`deepseek/deepseek-v4-pro`), 0.9901 (`moonshotai/kimi-k2.7-code`), 0.9855 (`z-ai/glm-5.3`) and 0.9824 (`z-ai/glm-5.3-flash`) of its bills. No input and output pair reproduces every bill within 1e-09 USD without a cache-read price as well (0.0028, 0.003625, 0.19, 0.26 and 0.03 USD per 1M tokens, in the same order), which the registry does not hold. For the two DeepSeek models the vendor page, opened 2026-11-12, states other prices than their bills give; the registry keeps the bills' pair, as for every model
- A row's input tokens are `usage.input`, the part of the prompt not read from the cache, not the whole prompt, which the converter does not keep. What that misses is on `mmlu_pro`, where 25,478 of the 60,154 responses read from the cache: there the work's input is a whole-set `median_low` of 980 tokens against 1,281 for the whole prompt. The research note counts the (parent, delegate) pairs for which the cheaper path, inline or delegated, differs between the 4 families at the four base points: 10, 3, 1 and 16 of the 25 with `usage.input`, and 10, 3, 1 and 14 with the whole prompt
- The windows are the vendor pages': 1M, read as 1,000,000, for the two DeepSeek and the two GLM models, and 262,144 for `moonshotai/kimi-k2.7-code` (`DESIGN.md` 13.14)
- The 4 dropped items (Method) are not scored on any path
- The vendor pages, opened 2026-11-12, say the name `deepseek-v4-flash` is retired, its requests now served by DeepSeek-V4.1-Flash-1017, and that the K2 series of `moonshotai/kimi-k2.7-code` is closed to new users from October 31, 2026 and retires by the end of December 2026, so a reader may no longer be able to call some of these models. These prices only reprice their recorded calls
- The limits of `DESIGN.md` 13.8: each item's success is its one recorded label, and the bar is held per call

## Results

Means over the 5 parents. `dec_` is the decision, `inl_` always inline and `del_` always delegating; success is held-out success, cost the held-out half's list-price cost in USD, `delegated` the share of seeds on which the decision delegates, and `separate` whether inline work takes parent calls of its own (`True`) or folds into the next call (`False`). Inline does not depend on the bar or the flavor:

```text
$ python evidence/delegation/results.py --table evidence/response-bank-delegation/results.json
bar  flavor          context  separate  dec_success  dec_cost  inl_success  inl_cost  del_success  del_cost  delegated
---  --------------  -------  --------  -----------  --------  -----------  --------  -----------  --------  ---------
0.8  cost_effective  8000     True      0.847        20.7429   0.861        101.6277  0.847        20.7429   1.000
0.8  cost_effective  64000    True      0.847        20.7429   0.861        330.6613  0.847        20.7429   1.000
0.8  cost_effective  200000   True      0.847        20.7429   0.861        886.8857  0.847        20.7429   1.000
0.8  cost_effective  8000     False     0.847        20.2117   0.861        53.9250   0.847        20.7429   0.950
0.8  cost_blind      8000     True      0.874        87.0202   0.861        101.6277  0.874        75.1274   0.743
0.8  cost_blind      64000    True      0.874        151.1970  0.861        330.6613  0.874        75.1274   0.743
0.8  cost_blind      200000   True      0.874        307.0548  0.861        886.8857  0.874        75.1274   0.743
0.8  cost_blind      8000     False     0.874        73.9500   0.861        53.9250   0.874        75.1274   0.743
0.9  cost_effective  8000     True      0.874        75.1256   0.861        101.6277  0.874        75.1256   1.000
0.9  cost_effective  64000    True      0.874        75.1256   0.861        330.6613  0.874        75.1256   1.000
0.9  cost_effective  200000   True      0.874        75.1256   0.861        886.8857  0.874        75.1256   1.000
0.9  cost_effective  8000     False     0.874        73.0889   0.861        53.9250   0.874        75.1256   0.954
0.9  cost_blind      8000     True      0.874        87.0202   0.861        101.6277  0.874        75.1274   0.743
0.9  cost_blind      64000    True      0.874        151.1970  0.861        330.6613  0.874        75.1274   0.743
0.9  cost_blind      200000   True      0.874        307.0548  0.861        886.8857  0.874        75.1274   0.743
0.9  cost_blind      8000     False     0.874        73.9500   0.861        53.9250   0.874        75.1274   0.743
```

Per parent at bar 0.8 and point 0:

```text
$ python evidence/delegation/results.py --table evidence/response-bank-delegation/results.json --bar 0.8 --point 0
flavor          parent                      delegated  dec_success  dec_cost  inl_success  inl_cost  del_success  del_cost
--------------  --------------------------  ---------  -----------  --------  -----------  --------  -----------  --------
cost_effective  deepseek/deepseek-v4-flash  1.000      0.847        8.6727    0.861        54.9199   0.847        8.6727
cost_effective  deepseek/deepseek-v4-pro    1.000      0.847        14.5582   0.872        79.8013   0.847        14.5582
cost_effective  moonshotai/kimi-k2.7-code   1.000      0.847        31.8155   0.871        160.7643  0.847        31.8155
cost_effective  z-ai/glm-5.3                1.000      0.847        39.1307   0.855        193.9135  0.847        39.1307
cost_effective  z-ai/glm-5.3-flash          1.000      0.847        9.5373    0.845        18.7394   0.847        9.5373
cost_blind      deepseek/deepseek-v4-flash  0.640      0.874        63.4376   0.861        54.9199   0.874        63.0572
cost_blind      deepseek/deepseek-v4-pro    0.410      0.874        81.7461   0.872        79.8013   0.874        68.9426
cost_blind      moonshotai/kimi-k2.7-code   0.675      0.874        132.4781  0.871        160.7643  0.874        86.2000
cost_blind      z-ai/glm-5.3                1.000      0.874        93.5152   0.855        193.9135  0.874        93.5152
cost_blind      z-ai/glm-5.3-flash          0.990      0.874        63.9239   0.845        18.7394   0.874        63.9217
```

## Reading it

- In `cost_effective` the decision delegates on every seed for every parent at points 0 to 2 at every bar (`delegate_rate` 1.0 on all 30 of their decision rows); at point 3, the work folded into the parent's next call, its rate averaged over the 5 parents is 0.950 and 0.954 at bars 0.8 and 0.9.
- At bar 0.8 and point 0 (8,000 context tokens), averaged over the 5 parents, the `cost_effective` decision costs 20.7429 USD on a held-out half against 101.6277 for always inline (4.90 times as much), with held-out success 0.847 against 0.861.
- At bar 0.9 and point 0 it costs 75.1256 USD against 101.6277 for always inline, with held-out success 0.874 against 0.861.
- At bar 0.8 and point 0 the `cost_effective` decision costs more than always inline for no parent.
- `results.json` is 69,970 bytes.

## Regenerate

The converter downloads the four pinned files (1,018,191,580 bytes) into `~/.cache/ai-model-routing-evidence/response-bank/` on its first run and checks each against its pinned size and sha256 (`DESIGN.md` 12.20); the matrix it writes is not committed.

```bash
python -m pip install -e .
python evidence/response-bank/convert.py --out response-bank-matrix.jsonl
python evidence/response-bank-delegation/results.py --matrix response-bank-matrix.jsonl --registry evidence/response-bank-delegation/registry.json --out evidence/response-bank-delegation/results.json
python evidence/delegation/results.py --table evidence/response-bank-delegation/results.json
python evidence/delegation/results.py --table evidence/response-bank-delegation/results.json --bar 0.8 --point 0
```
