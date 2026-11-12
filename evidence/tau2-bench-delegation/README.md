# Delegation evidence on tau2-bench

The inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5), next to always working inline and always delegating, scored by `evaluate_delegation` (`DESIGN.md` 13.9) on held-out tau2-bench agent conversations, each priced on its own agent calls, with each of the 3 kept agents as the parent (`DESIGN.md` 13.12).

This folder holds the script, `results.py`; the registry of the 3 agents, with the list prices and context windows their calls are priced and checked at, [registry.json](registry.json); the committed output with one task per domain (`airline`, `retail` and `telecom`), [results.json](results.json); the same run with the three domains pooled into one task, a sensitivity, [pooled.json](pooled.json); and what they say, with the commands that regenerate them, [RESULTS.md](RESULTS.md).

## Inputs

- The per-call outcome matrix that the tau2-bench converter, [`../tau2-bench/convert.py`](../tau2-bench/convert.py), writes with `--calls`, and with `--calls --task-by all` for `pooled.json`. It is not committed; the dataset's source, pinned files and licence are in [the tau2-bench evidence README](../tau2-bench/README.md)
- `registry.json` above, and the four base grid points of [`../delegation/results.py`](../delegation/results.py), which `results.py` loads by file path; that script's `--table` mode prints the tables

## Regenerate

The commands, with the pooled run, are in the `## Regenerate` block of [RESULTS.md](RESULTS.md#regenerate).
