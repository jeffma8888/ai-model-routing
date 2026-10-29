# Research behind the defaults

Public evidence gathered on 2026-10-27 to 2026-10-29. Every claim in these files cites a public URL and a date. Vendor documentation rarely shows a publication date, so those entries record the date the page was opened.

| File | Question it answers |
|---|---|
| [judge-benchmarks.md](judge-benchmarks.md) | Is there public evidence on how well current models work as judges? (Short answer: almost none for the current generation, and what exists shows planted-error misses, self-preference and agreement that does not track human judgment) |
| [prior-art.md](prior-art.md) | What do existing routers, gateways and papers already do, and what is left for a per-task calibrated judge router? |

How the files feed the library:

- `model_routing/data/models.json`: vendor list prices and context windows, each row with its source URL, as of 2026-10-29
- `model_routing/data/priors.json`: three public leaderboards (Terminal-Bench 4.0, GDPval-AA, ARC-AGI-3), each with its source and date. Used only to order candidates at cold start, never to admit a model
- The default rules (generator isolation on, priors never admit, a conservative lower bound with a minimum sample count) follow from the findings in both files

Caveats that apply to everything here:

- Leaderboards measure the models on someone else's tasks and harness; a gap of a point or two on one leaderboard is not a reliable ranking
- Headline numbers in papers are self-reported on the authors' benchmarks, usually with older models
- Prices and model versions change; treat every number as a dated snapshot
