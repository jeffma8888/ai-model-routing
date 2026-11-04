# RouterBench evidence

RouterBench (Martian and collaborators) recorded, for 36,497 prompts from 86 evals (MMLU subjects, HellaSwag, ARC, Winogrande, MBPP, GSM8K, MT-Bench and more), each of 11 models' answer, a correctness score and the cost of the call. That is enough to test routing offline with no API key: `convert.py` turns it into the outcome matrix that `model-routing evaluate` reads (DESIGN 12.1 and 12.6).

## Source

- Dataset: https://huggingface.co/datasets/withmartian/routerbench, file `routerbench_0shot.pkl`
- Pinned revision: `784021482c3f320c6619ed4b3bb3b41a21424fcb`, 99,567,659 bytes, sha256 `ba4f77f19517610a707c374e99322d7750c30fc4ae7ff5527888595a1e65d36d`
- Licence: the RouterBench code is MIT licensed (https://github.com/withmartian/routerbench). The dataset card states no licence for the data. This repo commits no part of the dataset: the converter downloads it into `~/.cache/ai-model-routing-evidence/routerbench/`, outside the repo

## Safety

- Size and sha256 are checked before anything is unpickled; a cached file that fails the check is an error, never silently replaced
- The file is a pickle, so it is loaded with a restricted unpickler that resolves only the 11 globals this exact file references (pandas frame, index and block internals, numpy arrays, `builtins.slice`), found by a static opcode scan that runs no code. Anything else is refused

## Regenerate the matrix

```bash
python -m pip install -e ".[evidence]"
python evidence/routerbench/convert.py --out routerbench-matrix.jsonl
model-routing evaluate --outcomes routerbench-matrix.jsonl --bar 0.8
```

The converter prints a JSON report of what it kept and dropped. With the default options on the pinned file it keeps 65 of the 86 evals, 28,281 prompts, and writes 311,091 rows (11 models per prompt). Checked with Python 3.10, pandas 2.3.3 and numpy 2.2.6; numpy 2 prints a `DeprecationWarning` about `numpy.core`, because the file was written by an older numpy.

Results of `model-routing evaluate` on this matrix at bars 0.6 to 0.9 over 50 seeds, with the commands that regenerate them: [RESULTS.md](RESULTS.md) and [results.json](results.json).

## What is dropped, and why

- Graded evals: six evals have scores other than 0 and 1 (`grade-school-math`, 7,450 prompts, scored in steps of 0.25; `consensus_summary`, 362; `mtbench`, 41; `mtbench-math`, 20; `mtbench-reference`, 19; `chinese_idioms`, 15). The dataset does not document what a partial score means, so they are left out by default. `--pass-score T` keeps them, counting a call as correct when its score is at least `T`; that threshold is your choice and should be reported with any result
- Small evals: 15 evals with fewer than 100 prompts (`--min-items`, default 100), so every calibration and held-out half has about 50 items

## Reading it

- The models date from 2023 and the costs are the ones the dataset recorded, at that time's prices
- A task is one eval (`eval_name`): routing here is per task, not per prompt
- Model IDs are written as `vendor/model`: columns that already have a `/` are kept as is, `claude-` columns get `anthropic/` and `gpt-` columns get `openai/`
