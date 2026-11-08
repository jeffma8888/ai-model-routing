# Research behind the defaults

Public evidence gathered on 2026-10-27 to 2026-10-29, and for datasets.md, hand-off-data.md and delegation-datasets.md on 2026-11-06. Nearly every claim in these files cites a public URL and a date; the few textbook statistics references cited without a link are flagged as such in the Gaps section of prior-art.md. Vendor documentation rarely shows a publication date, so those entries record the date the page was opened.

| File | Question it answers |
|---|---|
| [judge-benchmarks.md](judge-benchmarks.md) | Is there public evidence on how well current models work as judges? (Short answer: almost none for the current generation, and what exists shows planted-error misses, self-preference and agreement that does not track human judgment) |
| [datasets.md](datasets.md) | Which public dataset could be the third source of committed evidence, with every model's per-item outcome on a coding or agentic task checked by a program? (Short answer: the tau2-bench paper results, MIT, with a per-item cost, but only four 2025 agent models) |
| [hand-off-data.md](hand-off-data.md) | Is there public data that records a parent agent handing work to a sub-agent, with per-call token counts and a success label, to measure what the delegation evidence assumes? (Short answer: no; TRAIL records real hand-offs with per-call token counts, but no success label and no run of the same work inline) |
| [delegation-datasets.md](delegation-datasets.md) | Can the delegation evidence run on a second dataset, tau2-bench, or on a dataset with no cost? (Short answer: not without a harness change: each tau2-bench item is a conversation of 2 to 100 model calls, which the harness prices as one call or with one call count per grid point, and the OpenAI agents' recorded costs fit a prompt-cache discount, inferred from the costs; a `cost_blind`-only run would repeat the routing choice) |
| [no-path-clears.md](no-path-clears.md) | When no path clears the task's bar, should the delegation decision choose by calibration bound (`DESIGN.md` 13.5 row 7), by cost, or refuse? (Short answer: keep row 7, whose choice scores highest on the held-out halves of the committed delegation runs, and keep `refuse` as the default; on tau2-bench row 7 decides most `cost_effective` cells and mostly takes a path below the bar, which README Limitations says. Its numbers are the output of [no_path_clears.py](no_path_clears.py)) |
| [livecodebench-cost.md](livecodebench-cost.md) | Could the LiveCodeBench evidence carry a cost read from the length of its output text? (Short answer: not yet. On the OpenAI reasoning runs the visible output is about the same length at every reasoning setting, while their reasoning tokens are billed and not shown, so a text-length cost would price those settings alike; five vendors' current pages are read: the four that speak of billing say reasoning is billed as output, but the five name only `o4-mini` of the 67; their pricing pages list by their own name only the two Claude 4 models, with and without thinking, and `o3`; the pricing pages of `mistralai`, `moonshotai`, `qwen` and `meta-llama` list none of their runs, the four other open-weight families give no first-party price, and eight families' reasoning pages are not read yet, so the evidence stays `cost_blind`. Its numbers are the output of [livecodebench_cost.py](livecodebench_cost.py)) |
| [prior-art.md](prior-art.md) | What do existing routers, gateways and papers already do, and what is left for a per-task calibrated judge router? |

How the files feed the library:

- `model_routing/data/models.json`: vendor list prices and context windows, each row with its source URL, as of 2026-10-29
- `model_routing/data/priors.json`: three public leaderboards (Terminal-Bench 4.0, GDPval-AA, ARC-AGI-3), each with its source and date. Used only to order candidates at cold start, never to admit a model
- The default rules (generator isolation on, priors never admit, a conservative lower bound with a minimum sample count) follow from the findings in judge-benchmarks.md and prior-art.md
- `research/datasets.md` picked the third evidence dataset, the tau2-bench paper results, now committed under `evidence/tau2-bench/`
- `research/hand-off-data.md` is why the delegation evidence states its context and hand-off sizes as a grid and assumes a lossless brief
- `research/delegation-datasets.md` is why the delegation evidence read one dataset, the AutoBench matrix, until the tau2-bench conversations were priced on their own calls (`DESIGN.md` 13.12)
- `research/no-path-clears.md` is why `DESIGN.md` 13.5 row 7 stays as it is and `refuse` stays the default of `on_no_model`
- `research/livecodebench-cost.md` measures what a cost read from output length would see on the LiveCodeBench files, and why that evidence stays `cost_blind` for now

Caveats that apply to everything here:

- Leaderboards measure the models on someone else's tasks and harness; a gap of a point or two on one leaderboard is not a reliable ranking
- Headline numbers in papers are self-reported on the authors' benchmarks, usually with older models
- Prices and model versions change; treat every number as a dated snapshot
