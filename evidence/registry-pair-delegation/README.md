# Delegation evidence on the registry pair

The inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5), next to always working inline and always delegating, scored by `evaluate_delegation` (`DESIGN.md` 13.9) on held-out items of superlinked/train-a-router-reasoning's 31 tasks, each item one graded call, with each of the registry's own two models, `openai/gpt-6-luna` and `openai/gpt-6.1-sol`, as the parent, each row's cost given tokens at the `low` end of the inline re-read (`DESIGN.md` 13.17).

This folder holds the script, `results.py`; the committed output, [results.json](results.json); and what it says, with the `high` end's moves and the commands that regenerate it, [RESULTS.md](RESULTS.md). It holds no registry: the script prices both models at this checkout's `model_routing/data/models.json`, whose two rows the converter requires to carry the release's prices.

## Inputs

- The default outcome matrix of the registry-pair converter, [`../registry-pair/convert.py`](../registry-pair/convert.py), both models on every item, to whose rows `results.py` gives input and output tokens in place of their cost. It is not committed; the dataset's source, pinned revision and licence are in [the registry-pair evidence README](../registry-pair/README.md), and the attribution the dataset card asks for is in [RESULTS.md](RESULTS.md)
- The four base grid points of [`../delegation/results.py`](../delegation/results.py), which `results.py` loads by file path; that script's `--table` mode prints the tables

## Regenerate

The commands are in the `## Regenerate` block of [RESULTS.md](RESULTS.md#regenerate).
