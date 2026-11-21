# Production lessons: cutting model cost at equal or better quality

What public write-ups from teams that run language models in production found about cutting model cost while keeping or raising quality, and what this library does with each lesson. This version reads Harvey's engineering blog; the write-ups of other teams follow in later versions of this note.

Every quote below was checked word for word against its page as fetched on 2026-11-21, and each is under 40 words. A fact whose page could not be fetched is left out. The numbers are each author's own, measured on its own tasks, models and prices with data it does not publish, so this repository reproduces none of them; its own evidence is the committed results under `evidence/`. Model names inside quotes are the authors' product names, not this library's `vendor/model` IDs.

Each lesson gives the mechanism, the result with its source, and what this library does with it: what it does today, and the change that would turn the lesson into routing behavior or measurement, or why the library does not take it. A change named here is planned, not shipped, unless the text says the library does it today.

## What the sources do not say

- No Harvey post read here says that Harvey first sent everything to frontier models and then hit a cost wall. The posts say that frontier agents cost too much and run too slowly for production legal work, that Harvey ran on OpenAI models before it added others, and that it moved high-volume work to smaller, faster or self-trained models.
- None of them gives a cost saving from routing between models as such. The cuts they give come from trained models, harness changes and cheaper graders, each against a baseline the post names.

## Harvey

### No single best model: route per task and per step

- Mechanism: Harvey added Anthropic and Google models to its OpenAI ones, routes to a model automatically by default, lets a user pick one, and chooses a model for each step of a workflow, "independently choosing the model best suited to plan, orchestrate, and execute each task across a complex system." ([model offerings](https://www.harvey.ai/blog/expanding-harveys-model-offerings))
- Result: "there is no longer a single “best” model, but an array of premier models, each particularly suited to different legal tasks and preferences." ([model offerings](https://www.harvey.ai/blog/expanding-harveys-model-offerings)) The same post: "Even on a relatively straightforward three-step process, completing 80% of the work at each step means only completing about half of the overall work." ([model offerings](https://www.harvey.ai/blog/expanding-harveys-model-offerings))
- In this library: it routes per task today. Each task has its own bar, and the router takes the cheapest model whose Wilson lower bound clears it. It sets no bar for a chain of steps, and three steps that each pass 0.8 of the time pass about 0.51 together. The change: a bar for a whole multi-step workflow, met by a combination of step routes admitted on whole-workflow outcomes, so a step may need a stronger model than its own bar asks for.

### Count the cost of finished work, not of one call

- Mechanism: Harvey states cost per Review Table cell, per data room and per query, and "But cost is a function of both token prices and tokens used." ([Tenet update](https://www.harvey.ai/blog/post-training-update-harvey-tenet))
- Result: "average cost per cell fell by 54.8% compared to Claude Sonnet 5 on the same tasks." ([Review Table models](https://www.harvey.ai/blog/training-frontier-review-table-models-with-applied-compute)) At the same time "the AC Review Table model reached 0.903 on our benchmark, compared with 0.867 for Fable 5 and 0.857 for GPT-5.6-Sol." ([Review Table models](https://www.harvey.ai/blog/training-frontier-review-table-models-with-applied-compute))
- In this library: `cost_effective` prices a call at the model's list prices and its mean tokens per call on the task (the task's expected tokens until the stats hold token counts), and ranks only the models that clear the bar. It does not price a failure, so where a failed call is retried, the cheapest model per call can cost the most per success. The change: cost per successful outcome as the `cost_effective` objective for a task whose failed calls are retried, and as a column of the reports.

### Quality per token

- Mechanism: "intelligence-per-token, which is measured as the mean rubric criteria points that an agent completes successfully per 100k inference tokens." ([Tenet update](https://www.harvey.ai/blog/post-training-update-harvey-tenet))
- Result: "Our model scores 190.8 in our intelligence-per-token metric against 129.3 for the best frontier configuration and 37.2 for equivalently sized models." ([Tenet update](https://www.harvey.ai/blog/post-training-update-harvey-tenet))
- In this library: not taken as a routing rule. The router admits a model on its success rate against the task's bar and only then compares cost, so one number that folds success and tokens together could rank a cheaper model that misses the bar above one that clears it. The tokens a model spends already enter its cost through its mean tokens per call.

### Your own trained model is a candidate, kept to the tasks it was measured on

- Mechanism: Harvey trains models for single jobs and exposes them to its main model: "These capabilities are each trained separately and can be deployed as tools and sub-agents that our model can route to in order to tackle specific tasks." ([Tenet update](https://www.harvey.ai/blog/post-training-update-harvey-tenet))
- Result: its Firm Knowledge model "completes tasks competitively with leading frontier models while reducing cost per query by 90%." ([Tenet update](https://www.harvey.ai/blog/post-training-update-harvey-tenet)) The gains are uneven: "Small regressions in low-representation domains suggest a clear direction for data balancing and targeted training." ([legal agent](https://www.harvey.ai/blog/training-a-legal-agent-with-applied-compute)) Training has its own cost: "The model was trained on approximately 150 NVIDIA B300 GPUs over the course of 2 months." ([Tenet update](https://www.harvey.ai/blog/post-training-update-harvey-tenet))
- In this library: a model is a registry row priced from a vendor's list price. The changes: a registry row for a model you host, priced from your own hourly cost and throughput instead of a vendor page, and a task scope, so a model built for some tasks is never a candidate on others, not even at cold start. Task slices, which the router reads today, let a team check such a model on each part of a task where its gains may differ.

### Choose a cheap judge by agreement with strong judges, then batch its criteria

- Mechanism: two strong graders define the labels where they agree, "GPT-5.5 xhigh and Opus 4.8 Max agreed on more than 95% of criteria across runs. We treated that agreement set as the frontier consensus" ([legal agent](https://www.harvey.ai/blog/training-a-legal-agent-with-applied-compute)), and cheaper graders are scored against it and on "a 98.9% per-criterion self-consistency floor across three reruns" ([legal agent](https://www.harvey.ai/blog/training-a-legal-agent-with-applied-compute))
- Result: "GPT-5 Mini and Sonnet preserved most of the frontier signal, staying above 97% alignment with the consensus." ([legal agent](https://www.harvey.ai/blog/training-a-legal-agent-with-applied-compute)) Then "Switching to GPT-5 Mini and batching criteria produced 40x cost reduction at 16 criteria per group and 100x reduction when all criteria were grouped together." ([legal agent](https://www.harvey.ai/blog/training-a-legal-agent-with-applied-compute))
- In this library: judge calls are its first case, and it calibrates a judge on labeled items. The changes: labels built from the items where every run of the chosen strong judges agrees, for a team with no human labels; a self-consistency minimum, so a judge whose reruns disagree is excluded whatever its bound; and the number of criteria per call measured as a setting of the judge, as in the lesson on measured setups below.

### The orchestrator gets the strong model; the readers can be cheap

- Mechanism: a root model hands the reading of a large data room to sub-agents and writes the report from their results.
- Result: "Holding the sub-agent model fixed while varying the root model, the gap between the highest- and lowest-scoring roots averaged about 38 percentage points." ([M&A diligence agents](https://www.harvey.ai/blog/post-training-rlm-agents-for-m-and-a-diligence)) Against that, "Holding the root fixed while varying the sub-agents, the corresponding gap between sub-agent models averaged about 8 points" ([M&A diligence agents](https://www.harvey.ai/blog/post-training-rlm-agents-for-m-and-a-diligence)), while "With Opus 5 orchestrating, for example, the root accounts for 3.8% of input tokens and 1.1% of output tokens" ([M&A diligence agents](https://www.harvey.ai/blog/post-training-rlm-agents-for-m-and-a-diligence))
- In this library: the delegation decision chooses, per task, inline work or a sub-agent and the sub-agent's model. The change: route the root and sub-agent models as a pair, each pair admitted on its own runs and priced by each side's tokens, so a strong root with cheap readers can be chosen directly.

### Under-delegation is a failure you can measure, and depth needs a cap

- Mechanism: Harvey forced delegation with a harness, then trained the root model to delegate.
- Result: without the harness, "In the traces, both agents stop reading early and write shorter memos, and neither spawns sub-agents despite having the ability to." ([M&A diligence agents](https://www.harvey.ai/blog/post-training-rlm-agents-for-m-and-a-diligence)) With it, "Across seven models, the RLM harness raises mean pass rate from 23.3% to 62.4%, a gain of 39.1 percentage points." ([M&A diligence agents](https://www.harvey.ai/blog/post-training-rlm-agents-for-m-and-a-diligence)), at a price: "Moving to the RLM harness raises generation cost per data room for six of the seven baseline models" ([M&A diligence agents](https://www.harvey.ai/blog/post-training-rlm-agents-for-m-and-a-diligence)) After training, "The post-trained root makes 64% more sub-agent calls per data room." ([M&A diligence agents](https://www.harvey.ai/blog/post-training-rlm-agents-for-m-and-a-diligence)) A second level of sub-agents failed: "In four of the ten regressions, the depth-2 run reads the data room but never writes the report." ([M&A diligence agents](https://www.harvey.ai/blog/post-training-rlm-agents-for-m-and-a-diligence))
- In this library: the delegation decision says when to delegate, but nothing checks that the agent then did. The changes: log the advised mode beside the mode the agent took and report the share of advised hand-offs it skipped, and a cap on delegation depth.

### Effort, harness and batch size are part of the measured setup

- Mechanism: Harvey fixes the reasoning effort and the harness of a comparison, "All models are evaluated at minimal reasoning effort to meet product latency requirements." ([Review Table models](https://www.harvey.ai/blog/training-frontier-review-table-models-with-applied-compute))
- Result: "At this matched level of answer quality, the agentic harness used 50.3% fewer input tokens and 28.6% fewer output tokens" ([Review Table models](https://www.harvey.ai/blog/training-frontier-review-table-models-with-applied-compute)) One harness does not suit every model: "We found that our approach had a mixed effect on other models, with some scoring better (Fable 5: +7.7%) and some regressing (GPT-5.6 Sol: -4.2%)." ([Tenet update](https://www.harvey.ai/blog/post-training-update-harvey-tenet))
- In this library: stats are kept per task and model, so the runs of one model at two efforts or in two harnesses pool into one success rate and one mean cost. The change: route a measured setup, a model plus a named variant (an effort, a harness or a number of criteria per call), each with its own stats and price.

### Latency moves work to smaller models

- Mechanism: for high-volume features Harvey takes faster models, "And sometimes the right model is not the largest one. For high-volume product surfaces like Vault, the challenge is balancing quality with latency." ([multi-model by design](https://www.harvey.ai/blog/why-harvey-is-multi-model-by-design))
- Result: at the other end, "Frontier intelligence is expensive to run. On LAB, reaching the top of the closed-source leaderboard runs to roughly $50 per task and over 20 minutes of latency." ([open legal agents](https://www.harvey.ai/blog/post-training-open-legal-agents-with-baseten-research))
- In this library: the monitor reports p50 and p95 latency per group, and a task sets a timeout per call, but no task can exclude a model for being too slow. The change: a latency bar per task on each model's measured p95, applied like the success bar.

### Switch models only on locked data and a significant result

- Mechanism: "once a collection of evaluation samples is “published,” it becomes locked, ensuring that iterative experiments have a fixed baseline for comparing new features, models, or methods." ([scaling evaluation](https://www.harvey.ai/blog/scaling-ai-evaluation-through-expertise)) Changes also pass nightly checks: "We run a suite of lightweight canary evaluations nightly to validate the day's code changes before they go to production" ([scaling evaluation](https://www.harvey.ai/blog/scaling-ai-evaluation-through-expertise))
- Result: in a blind expert comparison "The mean rating improved by over 10% (from 5.10 to 5.63), and the median score rose from 5 to 6" ([scaling evaluation](https://www.harvey.ai/blog/scaling-ai-evaluation-through-expertise)), and "the feedback helped validate our decision to shift more workloads to GPT-4.1" ([scaling evaluation](https://www.harvey.ai/blog/scaling-ai-evaluation-through-expertise))
- In this library: the Wilson bound needs evidence before a model is admitted, but the stats do not record which labeled dataset they came from, so a challenger and the model it would replace can be compared on different labels. The change: record the labeled file's hash with the stats, and an advisory paired check of a challenger against the current route on the same items before a route changes.

### Tenant policy and provider health are routing inputs

- Mechanism: "Harvey allows workspace administrators to determine which models are available to their organization." ([multi-model by design](https://www.harvey.ai/blog/why-harvey-is-multi-model-by-design)) Availability differs by region: "Opus 4.6 is available to our customers in Australia, where certain other frontier models have not yet been deployed." ([multi-model by design](https://www.harvey.ai/blog/why-harvey-is-multi-model-by-design)) A user can "pick the particular model used by Harvey’s model systems to support their work, or choose “auto” to have Harvey select for them." ([model offerings](https://www.harvey.ai/blog/expanding-harveys-model-offerings))
- Result: "If one provider experiences capacity constraints, service degradation, or an outage, Harvey can route work to an alternative model without disrupting the user's workflow." ([multi-model by design](https://www.harvey.ai/blog/why-harvey-is-multi-model-by-design))
- In this library: the executor moves to the next model of the route when a call fails or the caller's check rejects its answer, and a task can exclude model families. The changes: a policy of allowed models, families and region, applied before cost so that a fallback never leaves the allowed set, and a pinned call that skips the ranking but keeps the hard checks, with the pin logged.

## Sources

Each page was fetched on 2026-11-21.

- https://www.harvey.ai/blog/expanding-harveys-model-offerings (Harvey blog: the providers it added, automatic routing, the per-step choice and the user's model pick)
- https://www.harvey.ai/blog/why-harvey-is-multi-model-by-design (Harvey blog: smaller models for high-volume features, rerouting on an outage, workspace allow-lists and regions)
- https://www.harvey.ai/blog/scaling-ai-evaluation-through-expertise (Harvey blog: locked evaluation sets, nightly canary checks and the blind expert comparison)
- https://www.harvey.ai/blog/post-training-update-harvey-tenet (Harvey blog: cost as price times tokens, intelligence per token, the Firm Knowledge model and its training)
- https://www.harvey.ai/blog/training-frontier-review-table-models-with-applied-compute (Harvey blog: the Review Table model's cost per cell and quality, and the agentic harness's tokens)
- https://www.harvey.ai/blog/training-a-legal-agent-with-applied-compute (Harvey blog: judge selection by consensus, self-consistency, batched criteria and uneven gains by domain)
- https://www.harvey.ai/blog/post-training-rlm-agents-for-m-and-a-diligence (Harvey blog: root and sub-agent models, under-delegation and the depth-2 regressions)
- https://www.harvey.ai/blog/post-training-open-legal-agents-with-baseten-research (Harvey blog: the cost and latency of frontier agents on LAB)
