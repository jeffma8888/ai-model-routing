# Delegation evidence on the LLM Routing Response Bank

The inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5), next to always working inline and always delegating, scored by `evaluate_delegation` (`DESIGN.md` 13.9) on held-out items of the LLM Routing Response Bank's 4 task families, each item one recorded call, with each of its 5 models as the parent (`DESIGN.md` 13.14).

This folder holds the script, `results.py`; the registry of the 5 models, with the list prices (for each model the input and output pair its bills give on its responses with no cache read) and context windows their calls are priced and checked at, [registry.json](registry.json); the committed output, [results.json](results.json); and what it says, with the commands that regenerate it, [RESULTS.md](RESULTS.md).

## Inputs

- The default outcome matrix of the response-bank converter, [`../response-bank/convert.py`](../response-bank/convert.py), over all 5 models, from which `results.py` drops the 4 `mmlu_pro` items with a null token count (`select_rows`, loaded by file path from [`../llmrouterbench-delegation/results.py`](../llmrouterbench-delegation/results.py)). It is not committed; the dataset's source, pinned revision and licence are in [the response-bank evidence README](../response-bank/README.md), and the attribution its terms ask for is in [RESULTS.md](RESULTS.md)
- `registry.json` above, and the four base grid points of [`../delegation/results.py`](../delegation/results.py), which `results.py` loads by file path; that script's `--table` mode prints the tables

## Regenerate

The commands are in the `## Regenerate` block of [RESULTS.md](RESULTS.md#regenerate).
