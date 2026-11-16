# The registry's own pair on public data: superlinked/train-a-router-reasoning

## Facts

- Question: what does the router give on public data for the registry's own two models, `openai/gpt-6-luna` and `openai/gpt-6.1-sol`, at the registry's own prices?
- Data: [superlinked/train-a-router-reasoning](https://huggingface.co/datasets/superlinked/train-a-router-reasoning) at revision `63336f25fc54597a8e161a7245613f91bd60177e` (last modified 2026-10-21), both models at medium reasoning effort, one row per question with each model's correctness and cost.
- Split: the release's own, 3,056 calibration questions calibrate and 3,043 final ones score, 31 tasks, one per (dataset, task) pair, and no family of related questions in both splits.
- Alone on the final split: `openai/gpt-6-luna` 0.886 held-out success for 0.462583 USD, `openai/gpt-6.1-sol` 0.926 for 4.266642 USD.
- `cost_effective` at bar 0.8: 0.912 held-out at 0.487 of `openai/gpt-6.1-sol`'s cost, 22 of 31 tasks on `openai/gpt-6-luna`; at bar 0.9: 0.920 at 0.798, 13 tasks on it.
- `cost_blind` at every bar: 0.922 at 0.864, the `best_on_calibration` row.
- No cleared task fell below its bar on the final split, at any bar in either flavor.
- No routed row reaches `openai/gpt-6.1-sol` alone (0.926).
- The per-question oracle: 0.936 at 0.207, above every routed row and above `openai/gpt-6.1-sol` alone.
- Recommendation: a routing results file for this dataset, as row E24, its README subsection after row DOC28.

## Method

- Files, each checked by size and sha256 before it is read, and downloaded at the pinned revision into `~/.cache/ai-model-routing-evidence/registry-pair` (or `--cache`) when absent:

| File | Bytes | sha256 |
|---|---|---|
| `pair.json` | 2,473 | `4b4cc5f936fe8a8018b6845bfa9bd29b7d18ec428489d15ebab62554c4cd11b4` |
| `recordings/grades-calibration.json` | 3,777,170 | `2f47b9df61b131879f30b4ea36693a8ce8bc43e46afd17d7fbd5d7a93922e8ac` |
| `recordings/grades-final.json` | 3,742,778 | `8d66442ad94b5e846a856084adfaba7a2915bab6253008e93ed44348dc264a5f` |

- Licence, from the dataset card at that revision: `license: other`, `license_name: mixed-mit-and-apache-2.0`, and in its Licenses section `This is a collection with multiple upstream licenses, not a relicensing of its components. Preserve the included notices when redistributing them.` Its table gives `MIT` for the MMLU-Pro and BIG-Bench Hard questions and `Apache-2.0` for the KOR-Bench questions and for `Example code and study-specific metadata`. This note commits no question text and no row of the dataset: it prints counts, sums and rates.
- Models: `pair.json` names `gpt-6-luna` as the cheap arm and `gpt-6.1-sol` as the strong arm; the script checks that each is in `model_routing/data/models.json` as `openai/<model>` at the pair's input and output prices per million tokens, or exits 2. The release grades by `strict declared label/string equality`, an invalid or incomplete answer counting as wrong and charged, and its costs are token counts at those list prices.
- Halves: the release's calibration split calibrates and its final split scores, not the 12.2 seeded halves of the joined set. The card says the final routing policies `were frozen before the original final answer collection` and that related question families `remain in one split`, which seeded halves of items would not keep (the script counts the families of each split and those in both); the two splits are about the same size, so each task's calibration count is close to the half 12.2 would draw.
- Router: the 12.3 evaluator's own cell on one fixed split, one task per (dataset, task) pair, a space in a task name made an underscore, at the bars, `min_samples` and `confidence` of `evidence/routerbench/results.json`, the committed file whose tasks are also mostly MMLU subjects, in both flavors. The strategies are those of 12.3: routed, the per-question oracle, `best_on_calibration`, `cheapest` and each model alone; a task below `min_samples` never clears and takes the 5.3 fallback.

## Results

```text
$ python research/registry_pair.py
superlinked/train-a-router-reasoning at 63336f2 (grades-calibration.json calibrates, grades-final.json scores): 31 tasks, 2 models, bars 0.6 0.7 0.8 0.9, min_samples 30, confidence 0.95 (evidence/routerbench/results.json config)
  cheap: openai/gpt-6-luna at 0.10 and 0.50 USD per million input and output tokens, the registry's prices, reasoning medium
  strong: openai/gpt-6.1-sol at 2 and 10 USD per million input and output tokens, the registry's prices, reasoning medium
  families: calibration 3,056 questions in 2,779, final 3,043 in 2,788, 0 in both splits
  task                                         cal  final  below min_samples  cheap right  strong right  cheap bound  strong bound
  bbh/boolean_expressions                       46     46  no                          46            46        0.923         0.923
  bbh/date_understanding                        46     46  no                          41            43        0.770         0.825
  bbh/formal_fallacies                          46     46  no                          46            46        0.923         0.923
  bbh/logical_deduction_five_objects            46     46  no                          46            46        0.923         0.923
  bbh/logical_deduction_seven_objects           46     46  no                          46            46        0.923         0.923
  bbh/logical_deduction_three_objects           46     46  no                          46            46        0.923         0.923
  bbh/navigate                                  47     46  no                          47            47        0.924         0.924
  bbh/object_counting                           46     46  no                          46            46        0.923         0.923
  bbh/reasoning_about_colored_objects           46     46  no                          46            45        0.923         0.887
  bbh/temporal_sequences                        46     46  no                          46            46        0.923         0.923
  bbh/tracking_shuffled_objects_five_objects    47     45  no                          45            47        0.858         0.924
  bbh/tracking_shuffled_objects_seven_objects   48     45  no                          45            48        0.832         0.926
  bbh/tracking_shuffled_objects_three_objects   46     46  no                          45            46        0.887         0.923
  bbh/web_of_lies                               46     46  no                          46            46        0.923         0.923
  korbench/cipher                               40     40  no                          34            34        0.709         0.709
  korbench/counterfactual                       40     40  no                          37            37        0.801         0.801
  korbench/logic                                10     10  yes                          8             9        0.490         0.596
  mmlupro/biology                              137    137  no                         120           124        0.810         0.844
  mmlupro/business                             152    151  no                         138           143        0.851         0.891
  mmlupro/chemistry                            220    220  no                         193           204        0.827         0.885
  mmlupro/computer_science                      76     75  no                          69            72        0.822         0.872
  mmlupro/economics                            162    161  no                         145           146        0.838         0.846
  mmlupro/engineering                          188    187  no                         152           167        0.746         0.835
  mmlupro/health                               156    156  no                         129           132        0.760         0.781
  mmlupro/history                               71     70  no                          52            57        0.619         0.696
  mmlupro/law                                  214    214  no                         153           161        0.651         0.690
  mmlupro/math                                 263    263  no                         249           253        0.913         0.931
  mmlupro/other                                179    178  no                         149           156        0.771         0.815
  mmlupro/philosophy                            93     93  no                          71            81        0.668         0.788
  mmlupro/physics                              254    253  no                         229           242        0.859         0.919
  mmlupro/psychology                           153    153  no                         130           137        0.785         0.837
  all                                          3,056 3,043
  single models on the final split, held-out success and cost (USD):
    openai/gpt-6-luna    0.886  0.462583
    openai/gpt-6.1-sol   0.926  4.266642
  oracle: 0.936 at 0.207 of openai/gpt-6.1-sol's cost
  best_on_calibration: 0.922 at 0.864 of openai/gpt-6.1-sol's cost
  cheapest: 0.886 at 0.108 of openai/gpt-6.1-sol's cost
  bar  flavor          routed  cost (USD)  cost / strong  cleared   tasks on cheap  cleared below the bar on final
  0.6  cost_effective  0.886   0.479661    0.112          30 of 31              30   0
  0.7  cost_effective  0.898   1.025460    0.240          28 of 31              27   0
  0.8  cost_effective  0.912   2.077228    0.487          25 of 31              22   0
  0.9  cost_effective  0.920   3.404776    0.798          15 of 31              13   0
  0.6  cost_blind      0.922   3.688022    0.864          30 of 31              12   0
  0.7  cost_blind      0.922   3.688022    0.864          28 of 31              12   0
  0.8  cost_blind      0.922   3.688022    0.864          25 of 31              12   0
  0.9  cost_blind      0.922   3.688022    0.864          15 of 31              12   0
  tasks routed to openai/gpt-6-luna (* cleared, else the best available fallback):
    0.6 cost_effective: bbh/boolean_expressions*, bbh/date_understanding*, bbh/formal_fallacies*, bbh/logical_deduction_five_objects*, bbh/logical_deduction_seven_objects*, bbh/logical_deduction_three_objects*, bbh/navigate*, bbh/object_counting*, bbh/reasoning_about_colored_objects*, bbh/temporal_sequences*, bbh/tracking_shuffled_objects_five_objects*, bbh/tracking_shuffled_objects_seven_objects*, bbh/tracking_shuffled_objects_three_objects*, bbh/web_of_lies*, korbench/cipher*, korbench/counterfactual*, mmlupro/biology*, mmlupro/business*, mmlupro/chemistry*, mmlupro/computer_science*, mmlupro/economics*, mmlupro/engineering*, mmlupro/health*, mmlupro/history*, mmlupro/law*, mmlupro/math*, mmlupro/other*, mmlupro/philosophy*, mmlupro/physics*, mmlupro/psychology*
    0.7 cost_effective: bbh/boolean_expressions*, bbh/date_understanding*, bbh/formal_fallacies*, bbh/logical_deduction_five_objects*, bbh/logical_deduction_seven_objects*, bbh/logical_deduction_three_objects*, bbh/navigate*, bbh/object_counting*, bbh/reasoning_about_colored_objects*, bbh/temporal_sequences*, bbh/tracking_shuffled_objects_five_objects*, bbh/tracking_shuffled_objects_seven_objects*, bbh/tracking_shuffled_objects_three_objects*, bbh/web_of_lies*, korbench/cipher*, korbench/counterfactual*, mmlupro/biology*, mmlupro/business*, mmlupro/chemistry*, mmlupro/computer_science*, mmlupro/economics*, mmlupro/engineering*, mmlupro/health*, mmlupro/math*, mmlupro/other*, mmlupro/physics*, mmlupro/psychology*
    0.8 cost_effective: bbh/boolean_expressions*, bbh/formal_fallacies*, bbh/logical_deduction_five_objects*, bbh/logical_deduction_seven_objects*, bbh/logical_deduction_three_objects*, bbh/navigate*, bbh/object_counting*, bbh/reasoning_about_colored_objects*, bbh/temporal_sequences*, bbh/tracking_shuffled_objects_five_objects*, bbh/tracking_shuffled_objects_seven_objects*, bbh/tracking_shuffled_objects_three_objects*, bbh/web_of_lies*, korbench/cipher, korbench/counterfactual*, mmlupro/biology*, mmlupro/business*, mmlupro/chemistry*, mmlupro/computer_science*, mmlupro/economics*, mmlupro/math*, mmlupro/physics*
    0.9 cost_effective: bbh/boolean_expressions*, bbh/formal_fallacies*, bbh/logical_deduction_five_objects*, bbh/logical_deduction_seven_objects*, bbh/logical_deduction_three_objects*, bbh/navigate*, bbh/object_counting*, bbh/reasoning_about_colored_objects*, bbh/temporal_sequences*, bbh/web_of_lies*, korbench/cipher, korbench/counterfactual, mmlupro/math*
    0.6 cost_blind: bbh/boolean_expressions*, bbh/formal_fallacies*, bbh/logical_deduction_five_objects*, bbh/logical_deduction_seven_objects*, bbh/logical_deduction_three_objects*, bbh/navigate*, bbh/object_counting*, bbh/reasoning_about_colored_objects*, bbh/temporal_sequences*, bbh/web_of_lies*, korbench/cipher*, korbench/counterfactual*
    0.7 cost_blind: bbh/boolean_expressions*, bbh/formal_fallacies*, bbh/logical_deduction_five_objects*, bbh/logical_deduction_seven_objects*, bbh/logical_deduction_three_objects*, bbh/navigate*, bbh/object_counting*, bbh/reasoning_about_colored_objects*, bbh/temporal_sequences*, bbh/web_of_lies*, korbench/cipher*, korbench/counterfactual*
    0.8 cost_blind: bbh/boolean_expressions*, bbh/formal_fallacies*, bbh/logical_deduction_five_objects*, bbh/logical_deduction_seven_objects*, bbh/logical_deduction_three_objects*, bbh/navigate*, bbh/object_counting*, bbh/reasoning_about_colored_objects*, bbh/temporal_sequences*, bbh/web_of_lies*, korbench/cipher, korbench/counterfactual*
    0.9 cost_blind: bbh/boolean_expressions*, bbh/formal_fallacies*, bbh/logical_deduction_five_objects*, bbh/logical_deduction_seven_objects*, bbh/logical_deduction_three_objects*, bbh/navigate*, bbh/object_counting*, bbh/reasoning_about_colored_objects*, bbh/temporal_sequences*, bbh/web_of_lies*, korbench/cipher, korbench/counterfactual
```

## Reading it

- `cost_effective` gives up a little success for most of the cost: at bar 0.6 it puts 30 of 31 tasks on `openai/gpt-6-luna`, 0.886 at 0.112 of the strong model's cost, and each step up the bar moves tasks to `openai/gpt-6.1-sol`, to 0.920 at 0.798 at bar 0.9.
- No routed row reaches the strong model alone on the final split: what routing saves by moving a task to the cheap model it pays for in success on that task, as the single-model rows show over all tasks (0.886 against 0.926); the oracle's 0.936 needs a choice per question, which task-level routing does not make.
- `cost_blind` gives one row at every bar, 0.922 at 0.864: it takes `openai/gpt-6-luna` on 12 tasks, each a `bbh` or `korbench` task where that model's calibration bound is at least the strong model's, so it costs less than the strong model alone and scores a little less.
- Every cleared task held its bar on the final split (the last column is 0 in every row), so on this pair a cleared task's calibration bound, with `min_samples` 30, was a safe floor for its final-split success.
- `korbench/logic` has 10 calibration questions, below `min_samples`, so it never clears and takes the 5.3 fallback, `openai/gpt-6.1-sol`, the higher bound; it is the task left out of 30 of 31 at bar 0.6.

## Recommendation

- Yes: make this dataset a routing results file, as row E24: a converter under `evidence/registry-pair/` pinned as the other converters are (this revision and the three files' sizes and sha256), writing the outcome matrix of both splits, and a committed results file with its RESULTS.md. It is the one public dataset whose models and prices are the registry's own, its card names only `MIT` and `Apache-2.0` components, and its graded files are small.
- E24 also decides the split of that file: the 12.3 seeded halves of the joined set, like every other committed file, would put related questions in both halves, and the release's split, this note's, has no 12.3 option; E24 states its choice and why.
- Its README subsection waits for room in the Evidence section, row DOC28.

## Limits

- Two models from one vendor, so each task has one choice between a cheaper and a stronger model; per-question routing, which the release itself studies, is out of scope, and the oracle row is only its ceiling.
- The costs are the release's estimates from token counts at frozen list prices, the registry's own; a price change moves both models' costs.
- The card says that repeating the recipe on published outcomes `is a reproduction, not a new blind test`, that public benchmark contamination `has not been ruled out`, and that KOR-Bench contributes `only nine independent families to the final split`.
- One fixed split and no seeds, so no spread over splits; the `bbh` and `korbench` tasks have few questions each.
- The training split, `recordings/grades-train.json`, is not read.

## Regenerate

```text
python -m pip install -e .
python research/registry_pair.py
```
