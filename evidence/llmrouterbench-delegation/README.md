# Delegation evidence on LLMRouterBench

The inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5), next to always working inline and always delegating, scored by `evaluate_delegation` (`DESIGN.md` 13.9) on held-out LLMRouterBench items of 9 benchmarks, each item one recorded call, with each of the 8 priced pool models as the parent (`DESIGN.md` 13.13).

This folder holds the script, `results.py`; the registry of the 8 models, with the list prices and context windows their calls are priced and checked at, [registry.json](registry.json); the committed output, [results.json](results.json); and what it says, with the commands that regenerate it, [RESULTS.md](RESULTS.md).

## Inputs

- The default outcome matrix of the LLMRouterBench converter, [`../llmrouterbench/convert.py`](../llmrouterbench/convert.py), over its 13-model pool, which `results.py` reduces to the 8 models of `registry.json`, dropping the 10 items with a null token count (`select_rows`). It is not committed; the dataset's source, pinned revision and licence are in [the LLMRouterBench evidence README](../llmrouterbench/README.md)
- `registry.json` above, and the four base grid points of [`../delegation/results.py`](../delegation/results.py), which `results.py` loads by file path; that script's `--table` mode prints the tables

## Regenerate

The commands are in the `## Regenerate` block of [RESULTS.md](RESULTS.md#regenerate).
