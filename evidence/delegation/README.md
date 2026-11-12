# Delegation evidence on AutoBench 2026

The inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5), next to always working inline and always delegating, scored by `evaluate_delegation` (`DESIGN.md` 13.9) on held-out AutoBench 2026 questions, with each of the 20 pool models as the parent (`DESIGN.md` 13.10).

This folder holds the script, `results.py`; its committed output on the four base grid points, [results.json](results.json); its output on the variant points, [variants.json](variants.json); and what they say, with the commands that regenerate them, [RESULTS.md](RESULTS.md).

## Inputs

- The outcome matrix with token counts and the pool registry that the AutoBench converter, [`../autobench-2026/convert.py`](../autobench-2026/convert.py), writes with `--task-by all --tokens --registry`. The matrix and registry are not committed; the dataset's source, pinned revision and licence are in [the AutoBench evidence README](../autobench-2026/README.md)
- The `--table` mode reads a committed results file instead, and also prints the tables of [the tau2-bench delegation results](../tau2-bench-delegation/RESULTS.md) and [the LLMRouterBench delegation results](../llmrouterbench-delegation/RESULTS.md), whose scripts load this one by file path

## Regenerate

The commands are in the `## Regenerate` block of [RESULTS.md](RESULTS.md#regenerate), and those of `variants.json` in its [Variant points](RESULTS.md#variant-points) part.
