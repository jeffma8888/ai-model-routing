# Registry-pair evidence

superlinked/train-a-router-reasoning graded the same 6,099 questions of MMLU-Pro, BIG-Bench Hard and KOR-Bench with two models, the registry's `openai/gpt-6-luna` and `openai/gpt-6.1-sol`, each answer marked right or wrong by strict declared-label equality, with the cost of each call estimated from its token counts at list prices that are the registry's own. So routing per task between the registry's own pair can be tested offline with no API key: `convert.py` turns the graded files into the outcome matrix that `model-routing evaluate` reads (DESIGN 12.1 and 12.23).

This folder holds the converter, `convert.py`; the committed results of `model-routing evaluate` on its default matrix at bars 0.6 to 0.9 over 50 seeds in both flavors, [results.json](results.json); and what they say, with the commands that regenerate them, [RESULTS.md](RESULTS.md).

## Source

- Dataset: https://huggingface.co/datasets/superlinked/train-a-router-reasoning, three files read:
  - `pair.json`, 2,473 bytes, sha256 `4b4cc5f936fe8a8018b6845bfa9bd29b7d18ec428489d15ebab62554c4cd11b4`
  - `recordings/grades-calibration.json`, 3,777,170 bytes, sha256 `2f47b9df61b131879f30b4ea36693a8ce8bc43e46afd17d7fbd5d7a93922e8ac`
  - `recordings/grades-final.json`, 3,742,778 bytes, sha256 `8d66442ad94b5e846a856084adfaba7a2915bab6253008e93ed44348dc264a5f`
- Pinned revision: `63336f25fc54597a8e161a7245613f91bd60177e` (last modified 2026-10-21)
- Licence: the dataset card names `license_name: mixed-mit-and-apache-2.0` and says: "This is a collection with multiple upstream licenses, not a relicensing of its components. Preserve the included notices when redistributing them." Its component table and the paragraph after it are quoted in [RESULTS.md](RESULTS.md)
- This repo commits no part of the dataset: the converter downloads it into `~/.cache/ai-model-routing-evidence/registry-pair/`, outside the repo

## The pair

The release's `pair.json` names a cheap and a strong arm and their list prices per million input and output tokens; the converter refuses the files unless each arm is in `model_routing/data/models.json` as `openai/<model>` at those prices (DESIGN 12.23). In USD per million tokens:

| arm | model | input | output |
| --- | --- | ---: | ---: |
| cheap | `openai/gpt-6-luna` | 0.1 | 0.5 |
| strong | `openai/gpt-6.1-sol` | 2 | 10 |

## Tasks

One routing task per (dataset, task) pair, each space of a task name an underscore. The release splits the questions into calibration and final sets for its own study, keeping each family of related questions in one split; the converter joins the two and the library draws its own halves by seed (DESIGN 12.23), and [RESULTS.md](RESULTS.md) sets the release split's rows beside them as the family-held check:

| task | calibration | final | items |
| --- | ---: | ---: | ---: |
| `bbh/boolean_expressions` | 46 | 46 | 92 |
| `bbh/date_understanding` | 46 | 46 | 92 |
| `bbh/formal_fallacies` | 46 | 46 | 92 |
| `bbh/logical_deduction_five_objects` | 46 | 46 | 92 |
| `bbh/logical_deduction_seven_objects` | 46 | 46 | 92 |
| `bbh/logical_deduction_three_objects` | 46 | 46 | 92 |
| `bbh/navigate` | 47 | 46 | 93 |
| `bbh/object_counting` | 46 | 46 | 92 |
| `bbh/reasoning_about_colored_objects` | 46 | 46 | 92 |
| `bbh/temporal_sequences` | 46 | 46 | 92 |
| `bbh/tracking_shuffled_objects_five_objects` | 47 | 45 | 92 |
| `bbh/tracking_shuffled_objects_seven_objects` | 48 | 45 | 93 |
| `bbh/tracking_shuffled_objects_three_objects` | 46 | 46 | 92 |
| `bbh/web_of_lies` | 46 | 46 | 92 |
| `korbench/cipher` | 40 | 40 | 80 |
| `korbench/counterfactual` | 40 | 40 | 80 |
| `korbench/logic` | 10 | 10 | 20 |
| `mmlupro/biology` | 137 | 137 | 274 |
| `mmlupro/business` | 152 | 151 | 303 |
| `mmlupro/chemistry` | 220 | 220 | 440 |
| `mmlupro/computer_science` | 76 | 75 | 151 |
| `mmlupro/economics` | 162 | 161 | 323 |
| `mmlupro/engineering` | 188 | 187 | 375 |
| `mmlupro/health` | 156 | 156 | 312 |
| `mmlupro/history` | 71 | 70 | 141 |
| `mmlupro/law` | 214 | 214 | 428 |
| `mmlupro/math` | 263 | 263 | 526 |
| `mmlupro/other` | 179 | 178 | 357 |
| `mmlupro/philosophy` | 93 | 93 | 186 |
| `mmlupro/physics` | 254 | 253 | 507 |
| `mmlupro/psychology` | 153 | 153 | 306 |

6,099 items in all, 12,198 rows (2 per item).

The converter's report on the pinned files counts 1 invalid cell (1 on `korbench/cipher`), kept as a miss with its charge, and 5,567 question families, 276 of them with two or more items, 808 items in all, 0 in both release splits and 0 across tasks (DESIGN 12.23).

## What a row keeps

Each row has `task`, `item` (the row's `id`), `model`, `correct` (the release's label equality) and `cost_usd` (the arm's estimated cost). The graded files hold hashes of each call's usage, not its counts, so a row has no token counts; the converter keeps no question, answer, usage hash or token count.

## Regenerate the matrix

```bash
python -m pip install -e .
python evidence/registry-pair/convert.py --out registry-pair-matrix.jsonl
```

The converter prints a JSON report of what it kept, reading each of the three files once.
