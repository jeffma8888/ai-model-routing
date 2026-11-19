# Delegation evidence on Longtail-SWE

The inline-or-sub-agent decision (`Router.decide_delegation`, `DESIGN.md` 13.5), next to always working inline and always delegating, scored by `evaluate_delegation` (`DESIGN.md` 13.9) on held-out issues of nebius/Longtail-SWE-trajectories' one task, each item one agent run on an issue of an open-source repository, split into its model calls by a stated rule, with each of the four registry models as the parent (`DESIGN.md` 13.18).

This folder holds the script, `results.py`; the committed output, [results.json](results.json); and what it says, with the split stated as an assumption and the commands that regenerate it, [RESULTS.md](RESULTS.md). It holds no registry: the script prices the four models at this checkout's `model_routing/data/models.json`, whose rows the converter prices the runs with.

## Inputs

- The four pinned files of the Longtail-SWE converter, [`../longtail-swe/convert.py`](../longtail-swe/convert.py), whose `fetch` the script calls and whose 12.26 matrix it reads, at run 0, through the research scripts below; no matrix file is written, and the files are not committed. The dataset's source, pinned revision and licence are in [the Longtail-SWE evidence README](../longtail-swe/README.md), and the attribution CC BY 4.0 asks for is in [RESULTS.md](RESULTS.md)
- The split rule of [`../../research/longtail_per_call.py`](../../research/longtail_per_call.py) and the four points and per-run counts of [`../../research/longtail_delegation.py`](../../research/longtail_delegation.py), which `results.py` loads by file path; their notes are [longtail-per-call.md](../../research/longtail-per-call.md) and [longtail-delegation.md](../../research/longtail-delegation.md)
- The `--table` mode of [`../delegation/results.py`](../delegation/results.py) prints the tables

## Regenerate

The commands are in the `## Regenerate` block of [RESULTS.md](RESULTS.md#regenerate).
