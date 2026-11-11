# Delegation on LLMRouterBench: inline or sub-agent on held-out single calls

What the inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5) does on items it never saw, next to always working inline and always delegating, measured by `evaluate_delegation` (`DESIGN.md` 13.9) on the public [LLMRouterBench](https://huggingface.co/datasets/NPULH/LLMRouterBench) records at revision [`b95870f9e60c589e82f7972c91ffa8de9ca89f85`](https://huggingface.co/datasets/NPULH/LLMRouterBench/tree/b95870f9e60c589e82f7972c91ffa8de9ca89f85) (licence MIT, "Copyright (c) 2025-2026 LLMRouterBench contributors"). Each item is one benchmark question, which every model answered in one recorded call labelled by the record's score, as on AutoBench and unlike the multi-call conversations of tau2-bench. The rows come from the converter described in [the LLMRouterBench evidence README](../llmrouterbench/README.md), at its defaults; the models' list prices and windows are in [registry.json](registry.json), with the pages and the checks behind them in [the research note](../../research/delegation-datasets.md); the committed results are [results.json](results.json). Every cost is a list-price estimate, never a billed cost.

## Method

- Matrix: the converter's default output, 13 models on the items of 9 benchmarks, one task per benchmark (`DESIGN.md` 12.18). The script keeps the rows of the 8 models the registry prices: `anthropic/claude-sonnet-4`, `openai/gpt-5`, `openai/gpt-5-chat` and `z-ai/glm-4.6` at the list price of a vendor page, and `deepseek/deepseek-r1-0528`, `deepseek/deepseek-v3-0324`, `deepseek/deepseek-v3.1-terminus` and `internlm/intern-s1` at the one price pair their recorded costs give within 1e-9 USD on every kept item, since no vendor page found prices them (`DESIGN.md` 13.13). 13.9 needs every model of the rows in the registry, so the other 5 models, with neither a page price nor an exact pair, are left out
- The pool leaves out `google/gemini-2.5-pro`, the best single model of [the LLMRouterBench routing results](../llmrouterbench/RESULTS.md), since no vendor page prices it and its recorded costs give no exact price pair.
- 10 items are dropped for a null token count (5 in `hle` and 5 in `simpleqa`), so 12,056 items remain. The 10 are the items on which `openai/gpt-5`'s output count is null; pricing them at a count of 0 would make their output free. That leaves 96,448 rows: `aime` 60, `arc-agi` 400, `arenahard` 749, `gpqa` 198, `hle` 2,152, `livecodebench` 1,055, `livemathbench` 121, `mmlupro` 3,000 and `simpleqa` 4,321 items
- `swe-bench` is left out. Narrowing the converter's own pool to the 8 models would add it as a tenth task (split `verified`, 500 items), but on its items the registry prices miss the recorded costs by up to 0.790308 USD (`anthropic/claude-sonnet-4`) for every model but `openai/gpt-5`, so the exact pairs hold on the 9 benchmarks only, and its prompts reach 263,446 input tokens, against at most 16,563 on the 9, above the window of 7 of the 8 models. The routing results read the same 9 benchmarks
- Every one of the 8 models is tried as the parent. For each of 50 seeds each task's items are split in half by the seeded hash of `DESIGN.md` 12.2. The decision is made from the calibration half only, at bars 0.1, 0.3, 0.5 and 0.8 (every other bar of the routing results from their lowest, then their highest; all eight would make a results file of about 456,000 bytes, over this repo's limit of about 300 KB) in both flavors, and scored on the held-out half. It prices the parent and each delegate candidate at that model's own rounded-up mean input and output tokens on the calibration half, and the two window checks read the task's expected sizes, the low medians of input and output tokens over the calibration rows of every model (`DESIGN.md` 13.9), which sum to 377 to 6,803 tokens over the cells
- Three strategies are scored on the same held-out items: `decision` (inline on the parent, or delegated to the decision's model), `inline` (the parent does every item itself) and `delegate` (every item goes to the routed delegate). Held-out success is the share of held-out items that passed, and held-out cost the list-price cost of the held-out half, each item priced on the tokens of the model doing the work on each path; both are averaged over the seeds
- The grid is the four base points of [the AutoBench delegation results](../delegation/RESULTS.md), each with a 500-token brief (B), a 500-token result (R) and one later parent call that re-reads them (T = 1): points 0 to 2 put inline work in parent calls of their own with C = 8,000, 64,000 and 200,000 tokens of context the parent already holds, and point 3 (C = 8,000) folds inline work into the parent's next call instead (`inline_separate_call` False; `DESIGN.md` 13.2 prices the folded calls)
- `aime` has 60 items, so its calibration half holds 22 to 42 over the seeds and is under the default `min_samples` of 30 on 25 of the 50: no model clears a bar there on those seeds, and every `aime` cell of them is 13.5 row 7 (`none_clear`) unless 13.4 blocks inline
- At point 2, C = 200,000 alone fills the window of every parent but `openai/gpt-5` (400,000), so inline is blocked (`parent_context_full`) on all 3,600 point 2 cells of each of the other 7. At point 1 (C = 64,000) it is blocked on 2,184 of the 3,600 cells of `internlm/intern-s1`, whose 65,536-token window leaves 1,536 tokens past C, and on no other cell
- Of the 57,600 `cost_effective` cells, 19,921 `delegate_cheaper`, 14,840 `none_clear`, 13,692 `parent_context_full`, 6,555 `parent_below_bar` and 2,592 `inline_cheaper`. `none_clear` is 13.5 row 7: no model clears the bar, so the calibration bounds decide, not cost.

## Assumed

- The lossless brief of `DESIGN.md` 13.9: the delegate is credited with its own recorded answer, as if a brief of B tokens carried what it needs, and the parent with its own as if C more tokens of context did not change it
- Every cost is a list price of the registry applied to the recorded token counts, never a recorded cost. For the four page-priced models the recorded costs are 0.906 (`openai/gpt-5`), 0.967 (`openai/gpt-5-chat`), 0.996 (`z-ai/glm-4.6`) and 1.000 (`anthropic/claude-sonnet-4`) of list price on the same counts; the other four are priced at the pair their recorded costs give, so for them the two agree
- The windows of the three DeepSeek models (163,840) and `internlm/intern-s1` (65,536) are the open weights' position limit, `max_position_embeddings` at a pinned Hugging Face revision, not the window of the service that recorded the costs, which the dataset does not name. The 200,000-token window of `anthropic/claude-sonnet-4` is inferred from the Claude page's sentence on every Claude model outside its 1M-token list, since the page does not name it. The `z-ai/glm-4.6` page writes 200K, read here as 200,000; read as 204,800, it would leave that parent 4,800 tokens of room at point 2
- The 10 dropped items (Method) are not scored on any path
- The 8 models are 2025 snapshots, as are all 13 of the dataset's pool: the model pages list `openai/gpt-5` as Deprecated and `openai/gpt-5-chat` as Shut down, and `anthropic/claude-sonnet-4` has the retirement date June 15, 2026. These prices only reprice their recorded calls
- An `arenahard` score of 0.5 counts as a miss, since a success is a score of 1 (`DESIGN.md` 12.18)
- The limits of `DESIGN.md` 13.8: each item's success is its one recorded score, and the bar is held per call

## Results

Means over the 8 parents. `dec_` is the decision, `inl_` always inline and `del_` always delegating; success is held-out success, cost the held-out half's list-price cost in USD, `delegated` the share of seeds on which the decision delegates, and `separate` whether inline work takes parent calls of its own (`True`) or folds into the next call (`False`). Inline does not depend on the bar or the flavor:

```text
$ python evidence/delegation/results.py --table evidence/llmrouterbench-delegation/results.json
bar  flavor          context  separate  dec_success  dec_cost  inl_success  inl_cost   del_success  del_cost  delegated
---  --------------  -------  --------  -----------  --------  -----------  ---------  -----------  --------  ---------
0.1  cost_effective  8000     True      0.450        69.5970   0.445        133.3194   0.450        69.5970   1.000
0.1  cost_effective  64000    True      0.450        69.5970   0.445        441.4268   0.450        69.5970   1.000
0.1  cost_effective  200000   True      0.450        69.5970   0.445        1189.6878  0.450        69.5970   1.000
0.1  cost_effective  8000     False     0.445        61.8219   0.445        75.9449    0.450        69.5970   0.718
0.1  cost_blind      8000     True      0.591        248.3151  0.445        133.3194   0.591        239.6925  0.869
0.1  cost_blind      64000    True      0.591        300.8536  0.445        441.4268   0.591        239.6925  0.869
0.1  cost_blind      200000   True      0.591        427.2685  0.445        1189.6878  0.591        239.6925  0.883
0.1  cost_blind      8000     False     0.591        237.2439  0.445        75.9449    0.591        239.6925  0.869
0.3  cost_effective  8000     True      0.525        148.5838  0.445        133.3194   0.525        148.5838  1.000
0.3  cost_effective  64000    True      0.525        148.5838  0.445        441.4268   0.525        148.5838  1.000
0.3  cost_effective  200000   True      0.525        148.5838  0.445        1189.6878  0.525        148.5838  1.000
0.3  cost_effective  8000     False     0.523        144.3870  0.445        75.9449    0.525        148.5838  0.780
0.3  cost_blind      8000     True      0.591        248.3151  0.445        133.3194   0.591        239.6925  0.869
0.3  cost_blind      64000    True      0.591        300.8536  0.445        441.4268   0.591        239.6925  0.869
0.3  cost_blind      200000   True      0.591        427.2685  0.445        1189.6878  0.591        239.6925  0.883
0.3  cost_blind      8000     False     0.591        237.2439  0.445        75.9449    0.591        239.6925  0.869
0.5  cost_effective  8000     True      0.559        179.0738  0.445        133.3194   0.559        179.0738  1.000
0.5  cost_effective  64000    True      0.559        179.0738  0.445        441.4268   0.559        179.0738  1.000
0.5  cost_effective  200000   True      0.559        179.0738  0.445        1189.6878  0.559        179.0738  1.000
0.5  cost_effective  8000     False     0.555        175.2834  0.445        75.9449    0.559        179.0738  0.814
0.5  cost_blind      8000     True      0.591        248.3151  0.445        133.3194   0.591        239.6925  0.869
0.5  cost_blind      64000    True      0.591        300.8536  0.445        441.4268   0.591        239.6925  0.869
0.5  cost_blind      200000   True      0.591        427.2685  0.445        1189.6878  0.591        239.6925  0.883
0.5  cost_blind      8000     False     0.591        237.2439  0.445        75.9449    0.591        239.6925  0.869
0.8  cost_effective  8000     True      0.582        221.6676  0.445        133.3194   0.582        221.6676  1.000
0.8  cost_effective  64000    True      0.582        221.6676  0.445        441.4268   0.582        221.6676  1.000
0.8  cost_effective  200000   True      0.582        221.6676  0.445        1189.6878  0.582        221.6676  1.000
0.8  cost_effective  8000     False     0.582        218.7178  0.445        75.9449    0.582        221.6676  0.910
0.8  cost_blind      8000     True      0.591        248.3151  0.445        133.3194   0.591        239.6925  0.869
0.8  cost_blind      64000    True      0.591        300.8536  0.445        441.4268   0.591        239.6925  0.869
0.8  cost_blind      200000   True      0.591        427.2685  0.445        1189.6878  0.591        239.6925  0.883
0.8  cost_blind      8000     False     0.591        237.2439  0.445        75.9449    0.591        239.6925  0.869
```

Per parent at bar 0.1 and point 0:

```text
$ python evidence/delegation/results.py --table evidence/llmrouterbench-delegation/results.json --bar 0.1 --point 0
flavor          parent                           delegated  dec_success  dec_cost  inl_success  inl_cost  del_success  del_cost
--------------  -------------------------------  ---------  -----------  --------  -----------  --------  -----------  --------
cost_effective  anthropic/claude-sonnet-4        1.000      0.450        124.2506  0.374        226.1756  0.450        124.2506
cost_effective  deepseek/deepseek-r1-0528        1.000      0.450        55.3636   0.473        146.2874  0.450        55.3636
cost_effective  deepseek/deepseek-v3-0324        1.000      0.450        48.5201   0.409        19.1648   0.450        48.5201
cost_effective  deepseek/deepseek-v3.1-terminus  1.000      0.450        49.1231   0.432        22.1792   0.450        49.1231
cost_effective  internlm/intern-s1               1.000      0.450        46.6510   0.370        38.3437   0.450        46.6510
cost_effective  openai/gpt-5                     1.000      0.450        88.0736   0.592        328.5498  0.450        88.0736
cost_effective  openai/gpt-5-chat                1.000      0.450        88.0736   0.471        98.7323   0.450        88.0736
cost_effective  z-ai/glm-4.6                     1.000      0.450        56.7202   0.439        187.1223  0.450        56.7202
cost_blind      anthropic/claude-sonnet-4        1.000      0.591        294.3461  0.374        226.1756  0.591        294.3461
cost_blind      deepseek/deepseek-r1-0528        0.902      0.591        226.2996  0.473        146.2874  0.591        225.4591
cost_blind      deepseek/deepseek-v3-0324        1.000      0.591        218.6156  0.409        19.1648   0.591        218.6156
cost_blind      deepseek/deepseek-v3.1-terminus  0.991      0.591        219.1998  0.432        22.1792   0.591        219.2186
cost_blind      internlm/intern-s1               1.000      0.591        216.7465  0.370        38.3437   0.591        216.7465
cost_blind      openai/gpt-5                     0.064      0.591        326.2266  0.592        328.5498  0.591        258.1691
cost_blind      openai/gpt-5-chat                1.000      0.591        258.1691  0.471        98.7323   0.591        258.1691
cost_blind      z-ai/glm-4.6                     0.991      0.591        226.9178  0.439        187.1223  0.591        226.8157
```

## Reading it

- In `cost_effective` the decision delegates on every seed for every parent at points 0 to 2 at every bar (`delegate_rate` 1.0 on all 96 of their decision rows); at point 3, the work folded into the parent's next call, its rate averaged over the 8 parents is 0.718, 0.780, 0.814 and 0.910 at bars 0.1, 0.3, 0.5 and 0.8.
- At bar 0.1 and point 0 (8,000 context tokens), averaged over the 8 parents, the `cost_effective` decision costs 69.5970 USD on a held-out half against 133.3194 for always inline (1.92 times as much), with held-out success 0.450 against 0.445.
- At bar 0.8 and point 0 it costs 221.6676 USD against 133.3194 for always inline, with held-out success 0.582 against 0.445.
- At bar 0.1 and point 0 the `cost_effective` decision costs more than always inline for 3 of the 8 parents: `deepseek/deepseek-v3-0324` (48.5201 against 19.1648 USD, held-out success 0.450 against 0.409), `deepseek/deepseek-v3.1-terminus` (49.1231 against 22.1792 USD, held-out success 0.450 against 0.432) and `internlm/intern-s1` (46.6510 against 38.3437 USD, held-out success 0.450 against 0.370).
- `results.json` is 230,012 bytes.

## Regenerate

The converter downloads the pinned file (about 1.28 GB) into `~/.cache/ai-model-routing-evidence/llmrouterbench/` on its first run and checks it against its pinned size and sha256 (`DESIGN.md` 12.18); the matrix it writes is not committed.

```bash
python -m pip install -e .
python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl
python evidence/llmrouterbench-delegation/results.py --matrix llmrouterbench-matrix.jsonl --registry evidence/llmrouterbench-delegation/registry.json --out evidence/llmrouterbench-delegation/results.json
python evidence/delegation/results.py --table evidence/llmrouterbench-delegation/results.json
python evidence/delegation/results.py --table evidence/llmrouterbench-delegation/results.json --bar 0.1 --point 0
```
