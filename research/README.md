# Research behind the defaults

Public evidence gathered on 2026-10-27 to 2026-10-29, and for datasets.md and hand-off-data.md on 2026-11-06. Nearly every claim in these files cites a public URL and a date; the few textbook statistics references cited without a link are flagged as such in the Gaps section of prior-art.md. Vendor documentation rarely shows a publication date, so those entries record the date the page was opened.

| File | Question it answers |
|---|---|
| [judge-benchmarks.md](judge-benchmarks.md) | Is there public evidence on how well current models work as judges? (Short answer: almost none for the current generation, and what exists shows planted-error misses, self-preference and agreement that does not track human judgment) |
| [datasets.md](datasets.md) | Which public dataset could be the third source of committed evidence, with every model's per-item outcome on a coding or agentic task checked by a program? (Short answer: the tau2-bench paper results, MIT, with a per-item cost, but only four 2025 agent models) |
| [hand-off-data.md](hand-off-data.md) | Is there public data that records a parent agent handing work to a sub-agent, with per-call token counts and a success label, to measure what the delegation evidence assumes? (Short answer: no; TRAIL records real hand-offs with per-call token counts, but no success label and no run of the same work inline) |
| [prior-art.md](prior-art.md) | What do existing routers, gateways and papers already do, and what is left for a per-task calibrated judge router? |

How the files feed the library:

- `model_routing/data/models.json`: vendor list prices and context windows, each row with its source URL, as of 2026-10-29
- `model_routing/data/priors.json`: three public leaderboards (Terminal-Bench 4.0, GDPval-AA, ARC-AGI-3), each with its source and date. Used only to order candidates at cold start, never to admit a model
- The default rules (generator isolation on, priors never admit, a conservative lower bound with a minimum sample count) follow from the findings in judge-benchmarks.md and prior-art.md
- `research/datasets.md` picked the third evidence dataset, the tau2-bench paper results, now committed under `evidence/tau2-bench/`
- `research/hand-off-data.md` is why the delegation evidence states its context and hand-off sizes as a grid and assumes a lossless brief

Caveats that apply to everything here:

- Leaderboards measure the models on someone else's tasks and harness; a gap of a point or two on one leaderboard is not a reliable ranking
- Headline numbers in papers are self-reported on the authors' benchmarks, usually with older models
- Prices and model versions change; treat every number as a dated snapshot
