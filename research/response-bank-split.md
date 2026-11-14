# The LLM Routing Response Bank on its own calibration split

## Facts

- Question: what does the router give on the LLM Routing Response Bank when it calibrates on the release's own 256 calibration tasks (`scores_cal.jsonl`) and is scored on its 13,059 evaluation tasks (`scores_eval.jsonl`), instead of on the seeded halves of the joined set that `evidence/response-bank/results.json` averages over 50 seeds?
- Short answer: the `cost_effective` result at the lowest bar holds. At 0.8 it gets 0.846 held-out success at 0.195 of the best single model's cost, against 0.847 at 0.201 in the committed means.
- What does not hold: with 256 calibration items only `livecodebench` and `mmlu_pro` clear 0.8 and no task clears 0.9, and `cost_blind` gets 0.871, below the best single model's 0.872, where the committed means put it at 0.874, above that model.
- Recommendation: one `## Sensitivity` bullet in `evidence/response-bank/RESULTS.md` with this split's rows; the committed run stays as it is. No spec row yet.
- Its numbers are the output of `research/response_bank_split.py`, in `## Results`.

## Method

- `evidence/response-bank/convert.py` joins the release's calibration and evaluation files (12.20), and the committed run draws its own seeded halves of each family (12.2), so every committed row is a mean over 50 splits of the joined set.
- This script keeps the release's split instead: a family's calibration items are the `task_id`s of `scores_cal.jsonl`, read from the converter's cache folder after a check against its pinned size and sha256, and every other item is scored.
- Each cell is the evaluator's own (`_split_sums`, `_cell` and `_summary` of `model_routing/evaluate.py`, 12.3) at the committed file's bars, `min_samples` and confidence, so only the split differs from the committed run.
- Each cost is a response's billed `official_usd`, summed over the scored items. The two runs score different numbers of items, so the comparison uses each cost as a share of the best single model's cost on the same items (12.7), never the totals.

## Results

```text
$ python research/response_bank_split.py --matrix response-bank-matrix.jsonl
LLM Routing Response Bank on the release's own split (scores_cal.jsonl calibrates, the evaluation tasks score): 4 tasks, 5 models, bars 0.8 0.9, min_samples 30, confidence 0.95 (evidence/response-bank/results.json config)
  task           calibration  evaluation  committed half  below min_samples  highest calibration bound
  aime           8            22          15              yes                0.676 (deepseek/deepseek-v4-flash, 8 of 8)
  gpqa_diamond   32           166         99              no                 0.682 (deepseek/deepseek-v4-flash, 27 of 32)
  livecodebench  88           967         527             no                 0.831 (deepseek/deepseek-v4-pro, 80 of 88)
  mmlu_pro       128          11,904      6,016           no                 0.834 (z-ai/glm-5.3-flash, 115 of 128)
  all            256          13,059
  single models on the evaluation split, held-out success and cost (USD):
    deepseek/deepseek-v4-flash   0.861  43.3917
    deepseek/deepseek-v4-pro     0.872  52.1218
    moonshotai/kimi-k2.7-code    0.871  136.6360
    z-ai/glm-5.3                 0.855  128.3791
    z-ai/glm-5.3-flash           0.845  11.5956
  best single model: deepseek/deepseek-v4-pro 0.872 here; deepseek/deepseek-v4-pro 0.872 in the committed means over 50 seeds
  oracle: 0.938 at 0.294 of the best's cost here; 0.938 at 0.294 committed
  best_on_calibration: 0.849 at 0.385 of the best's cost here; 0.874 at 2.104 committed
  cheapest: 0.846 at 0.195 of the best's cost here; 0.847 at 0.199 committed
  bar  flavor          routed  cost (USD)  cost / best  cleared  committed routed  committed cost / best  committed cleared
  0.8  cost_effective  0.846   10.1420     0.195        2 of 4   0.847             0.201                  0.735
  0.9  cost_effective  0.849   20.0671     0.385        0 of 4   0.874             2.104                  0.005
  0.8  cost_blind      0.871   27.8202     0.534        2 of 4   0.874             2.104                  0.735
  0.9  cost_blind      0.871   27.8202     0.534        0 of 4   0.874             2.104                  0.005
  routed picks per task (* cleared, else the best available fallback):
    0.8 cost_effective: aime deepseek/deepseek-v4-flash, gpqa_diamond deepseek/deepseek-v4-flash, livecodebench z-ai/glm-5.3-flash*, mmlu_pro z-ai/glm-5.3-flash*
    0.9 cost_effective: aime deepseek/deepseek-v4-flash, gpqa_diamond deepseek/deepseek-v4-flash, livecodebench deepseek/deepseek-v4-pro, mmlu_pro z-ai/glm-5.3-flash
    0.8 cost_blind: aime deepseek/deepseek-v4-flash, gpqa_diamond deepseek/deepseek-v4-flash, livecodebench deepseek/deepseek-v4-pro*, mmlu_pro deepseek/deepseek-v4-flash*
    0.9 cost_blind: aime deepseek/deepseek-v4-flash, gpqa_diamond deepseek/deepseek-v4-flash, livecodebench deepseek/deepseek-v4-pro, mmlu_pro deepseek/deepseek-v4-flash
```

## Reading it

- Calibration sizes: the release gives the four families 8, 32, 88 and 128 calibration items, against expected halves of 15, 99, 527 and 6,016 in the committed run. `aime`, at 8, is below `min_samples` 30, so it never clears here, as in the committed run.
- What clears: at 0.8, `livecodebench` and `mmlu_pro` in both flavors, 2 of 4 tasks; `gpqa_diamond`, whose highest calibration bound is 0.682, does not. At 0.9 no task clears, since the highest bound on any task is 0.834 (`mmlu_pro`, 115 of 128). The committed means clear 0.735 of their cells at 0.8 and 0.005 at 0.9.
- `cost_effective` at 0.8: 0.846 at 0.195 of the best single model's cost, against 0.847 at 0.201 committed. Both tasks that clear go to `z-ai/glm-5.3-flash`, the cheapest single model (11.5956 USD on the scored items), so the cheap pick does not need halves of thousands of items.
- Where nothing clears, the router keeps the model with the highest calibration bound (5.3), so the routed `cost_effective` row at 0.9 is the `best_on_calibration` row: 0.849 at 0.385 here, where it sends `mmlu_pro` to `z-ai/glm-5.3-flash`, against 0.874 at 2.104 committed.
- `cost_blind`: 0.871 at 0.534 at both bars, below `deepseek/deepseek-v4-pro`, the best single model at 0.872 on both runs. The committed means put `cost_blind` at 0.874, above that model, but at 2.104 of its cost. So the committed `cost_blind` gain over the best single model needs the larger halves, or the mean over seeds; one split cannot say which.
- The per-item oracle is 0.938 at 0.294 on both runs.

## Recommendation

- Add one `## Sensitivity` bullet to `evidence/response-bank/RESULTS.md` (12.21) with this split's `cost_effective` row at 0.8, its `cost_blind` row and the tasks that clear, built from this note's Results block by a test. It is the one held-out test on this dataset whose split the library did not draw, it backs the `cost_effective` result on the authors' own items, and it shows a limit the committed means hide: at 256 calibration items `cost_blind` does not pass the best single model.
- Keep the committed run as it is: the joined set and the seeded halves give every family but `aime` a calibration half far above `min_samples`, and a mean over 50 seeds, which one split cannot.

## Limits

- One split: the committed rows are means over 50 seeds and this is one draw, so a gap of a few thousandths here may be the draw alone.
- Different items: the scored side here holds 13,059 items and each committed held-out half about half of the joined set, so only the cost shares and the success rates are compared, never the totals.
- `mmlu_pro` holds 11,904 of the 13,059 scored items, so the pooled rows mostly measure it, as in the committed run.
- The highest-bound column breaks a tie in the bound by the lower mean calibration cost; the router's own tie rule may differ, and the routed picks lines show what it chose.

## Regenerate

```bash
python -m pip install -e .
python evidence/response-bank/convert.py --out response-bank-matrix.jsonl
python research/response_bank_split.py --matrix response-bank-matrix.jsonl
```

The convert command downloads the four pinned files into the converter's cache folder (12.20), where the script reads `scores_cal.jsonl`; `--cache` names another folder.
