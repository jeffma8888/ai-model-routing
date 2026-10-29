# Prior art in model routing and LLM-as-judge calibration

Status: complete, 2026-10-29. Sources checked on that date; older sources are flagged with their publication date.

## Summary

- Per-prompt learned routing (a classifier predicts which model will answer a given prompt well) is the dominant research paradigm: RouteLLM (preference data, 2024), Hybrid LLM (difficulty predictor, ICLR 2024), Not Diamond (pre-trained and custom routers, vendor), and most October 2026 arXiv routing papers
- Cascades (try the cheap model, escalate on low confidence) are the second standard pattern: FrugalGPT (2023), AutoMix (2023), "Trust or Escalate" cascaded selective evaluation for judges (2024), and confidence-based small-to-large routing (2026-10-16)
- Production gateways (LiteLLM, Portkey, OpenRouter) route on operator rules, price, latency, rate limits or market popularity, not on measured accuracy; their strength is fallback, retries, cooldowns and per-key or per-tag spend logging
- OpenRouter's current Auto Router classifies the prompt into about 30 task types and ranks models by community share of spend over a trailing 7 day window, with a cost_tier band and automatic fallbacks (vendor docs, opened 2026-10-29)
- LiteLLM's beta Auto Routing (since v1.94.0) maps a complexity tier to a pinned model or a Thompson-sampled pool; tiers are operator configured, there is no measured accept bar (vendor docs, opened 2026-10-29)
- No system opened this session selects a model by requiring a Wilson lower confidence bound on agreement with gold labels to clear a per-task bar with a minimum sample count. The closest relatives are Shnitzer et al. 2023 (benchmark-trained correctness predictors), Hybrid LLM (quality threshold at test time) and "Trust or Escalate" (user-specified human agreement level, guaranteed via selective evaluation)
- LLM-as-judge bias is well documented: position, verbosity and self-enhancement bias (Zheng et al. 2023, NeurIPS D&B), self-preference linked to self-recognition (Panickssery et al. 2024-04), position bias across 15 judges (Shi et al. 2024-06), 12 bias types in CALM (2024-10), and 2026 multicalibration and position-debiasing fixes (CaLLM 2026-10-13, DIAL 2026-09-25)
- Judge calibration against human labels has a theoretical limit: when the judge is no more accurate than the model being evaluated, no debiasing can cut required ground truth labels by more than half (Dorner et al., v3 2026-01-06); prediction-powered inference (2023) gives valid confidence intervals when few gold labels are combined with many judge predictions
- Excluding the generator's own model and family from judging is standard advice from the self-preference literature, not a novelty; packaging it as a routing rule is a small engineering convenience
- The honest positioning for this project: a small, standard-library implementation that combines (a) per-task measured agreement with a conservative confidence bound as the admission criterion, (b) cost or quality ranking among admitted models, and (c) gateway-style fallback and tag-level cost attribution. Parts (b) and (c) are standard practice; part (a) is uncommon in shipped tooling but is a straightforward application of known statistics, and the papers above should be cited as prior art

## Systems

Each subsection answers the same five questions: what it routes on, whether it uses a measured quality bar, fallback, monitoring and cost attribution, source.

### FrugalGPT (LLM cascades)
- Routes on: a cascade. Query goes to the cheapest model first; a learned scoring function (a small regression model over the query plus the candidate answer) decides whether to accept the answer or escalate to the next, more expensive model. The paper also covers prompt adaptation and LLM approximation (caching, fine-tuning a cheaper model)
- Measured quality bar: yes, indirectly. The cascade's acceptance thresholds and the model ordering are tuned on a labeled training set under a per-query budget; the quality signal is the scorer's confidence, not a per-task agreement rate with a confidence interval. Headline claim: matches the best single model (GPT-4 at the time) with up to 98 percent cost reduction on their benchmarks
- Fallback: escalation on low score is the mechanism; outages and API errors are not addressed
- Monitoring and cost attribution: not addressed beyond the cost accounting used in experiments
- Source: https://arxiv.org/abs/2305.05176 (paper, 2023-05-09; older than 120 days, foundational). Source type: paper

### RouteLLM (LMSYS / UC Berkeley)
- Routes on: per-prompt binary routing between a strong and a weak model. Four router families (similarity-weighted Elo, matrix factorization, BERT classifier, causal LLM classifier) trained on Chatbot Arena human preference data plus augmented data. A threshold on the predicted win probability sets the cost-quality point
- Measured quality bar: a routing threshold is chosen so that a target fraction of calls goes to the strong model, or to hit a target quality on a benchmark (MT Bench, MMLU, GSM8K). The quality notion is "percentage of the strong model's quality recovered", not a per-task agreement rate with a lower confidence bound. Headline claim: over 2x cost reduction at equal quality on some benchmarks, and transfer when strong and weak models are swapped
- Fallback: not addressed (research framework, open source release includes an OpenAI-compatible server)
- Monitoring and cost attribution: not addressed beyond reported experiments
- Source: https://arxiv.org/abs/2406.18665 (paper; v1 2024-06-26, v4 2025-02-23; older than 120 days). Source type: paper. Code: https://github.com/lm-sys/RouteLLM

### RouterBench (Martian and collaborators)
- Routes on: it is a benchmark, not a router. Provides over 405k inference outcomes (prompt, model, response, correctness, cost) across 11 models and 8 datasets so routers can be evaluated offline without re-running models, plus a theoretical framing of routing as a cost-quality Pareto problem (non-decreasing convex hull, AIQ metric)
- Measured quality bar: the benchmark scores routers on the cost-quality curve; it introduces the idea of evaluating routers against an oracle and against a "zero router" (random interpolation between models). Confidence intervals on quality are not part of the headline metric
- Fallback, monitoring, cost attribution: not applicable
- Source: https://arxiv.org/abs/2403.12031 (paper; v2 2024-03-28; older than 120 days). Source type: paper

### Hybrid LLM (Microsoft, ICLR 2024) and quality-aware routing papers
- Routes on: a per-query difficulty predictor (a small BERT-style model) that estimates whether the small model's answer will be within a quality margin of the large model's. A tunable threshold trades quality for cost at test time; "quality-aware" means the router is trained on the observed quality gap, including label noise handling for non-deterministic quality
- Measured quality bar: yes, the training signal is a measured quality difference on a labeled set (BART score against reference answers in the paper), and the threshold is set for a desired quality level. The guarantee is in expectation over the training distribution, not a per-task confidence bound. Headline claim: up to 40 percent fewer calls to the large model with no drop in response quality
- Fallback, monitoring, cost attribution: not addressed
- Source: https://arxiv.org/abs/2404.14618 (paper, 2024-04-22; older than 120 days). Source type: paper
- Related work in the same family (not opened individually this session, listed as pointers): AutoMix (self-verification then routing, 2023), Zooter (reward-model distilled router, 2023), LLM-Blender (ensemble then rank, 2023), MetaLLM, "Large Language Model Routing with Benchmark Datasets" (Shnitzer et al., 2023, which trains per-benchmark correctness predictors from benchmark data, the closest in spirit to using labeled sets to pick a model)

### Not Diamond
- Routes on: a per-prompt learned router. Two pre-trained routers (Chat, Code) trained on cross-domain data, and custom routers trained on the customer's own evaluation data (prompt plus per-model score). Request-time tradeoff: quality (default), cost, latency, or a 0 to 10 cost_quality_tradeoff blend (pre-trained router only), framed as Pareto optimization
- Measured quality bar: custom routers are trained on measured scores for your task, which is a measured-quality input. The output is a per-prompt prediction, not a per-task accept/reject bar, and the docs do not expose confidence intervals or minimum sample counts
- Fallback: the API returns a model selection and a session ID; executing the call, retries and fallbacks are left to the client (or the SDK wrapper). Not described on the pages opened
- Monitoring and cost attribution: session IDs let you trace which model was selected per query; cost attribution per tag was not found in the pages opened
- Source: https://docs.notdiamond.ai/docs/what-is-model-routing and https://docs.notdiamond.ai/docs/key-concepts (vendor docs, opened 2026-10-29; page dates not shown). Source type: vendor

### Martian
- Routes on: Martian co-authored RouterBench and historically sold a "Model Router" that predicted per-prompt model performance. As of 2026-10-29 the public site describes Martian as an interpretability research lab; the docs site offers a Gateway (unified access to 200+ models, usage dashboard with model performance and request history) and ARES (an evaluation suite). A public description of a current routing algorithm was not found on the pages opened
- Measured quality bar: not found
- Fallback: not found
- Monitoring and cost attribution: dashboard with real-time usage, model performance and request history (vendor claim)
- Source: https://withmartian.com and https://docs.withmartian.com (vendor, opened 2026-10-29; page dates not shown). Source type: vendor

### OpenRouter Auto Router
- Routes on: a lightweight in-flight classifier assigns each prompt one of about 30 task types (for example code:debugging, math, customer_support); the router then ranks models by the OpenRouter community's share of spend for that task type over a trailing 7-day window ("wisdom of the market"), filtered by a cost_tier band (low, medium, high, xhigh, max), allowed and excluded model patterns, and account restrictions. Session stickiness keeps multi-turn conversations on one model
- Measured quality bar: no. The quality proxy is aggregate spend share, which is a popularity signal, not a measured accuracy. The older cost_quality_tradeoff parameter is deprecated
- Fallback: the top surviving models become primary plus fallbacks; if classification or rankings are unavailable the router degrades to a default model set. Separate Model Fallbacks feature for fixed lists
- Monitoring and cost attribution: response reports the model actually used; opt-in router metadata header exposes the classified task type; you pay the selected model's standard rate with no router fee; provider.max_price caps per request
- Source: https://openrouter.ai/docs/features/model-routing (vendor docs, opened 2026-10-29; page date not shown, content describes the current spend-share design). Source type: vendor

### LiteLLM Router and Proxy
- Routes on: deployment-level strategies within a model group: simple-shuffle (weighted or rpm/tpm weighted, recommended default), usage-based (rate-limit aware), latency-based, least-busy, lowest-cost, custom strategy, and routing groups that bind different strategies to different model names. A separate beta Auto Routing feature (since v1.94.0) classifies each request into tiers (SIMPLE, MEDIUM, COMPLEX, REASONING) via heuristics, an LLM classifier, keyword rules or a plugin, and maps each tier to a pinned model, a random pool or a Thompson-sampled pool
- Measured quality bar: no. Tier mapping is operator configured; the complexity classifier is a heuristic or LLM judgment of the prompt, not a measured accuracy on labeled data. Thompson-sampled pools learn from online feedback but no accept/reject bar with a confidence bound is described
- Fallback: mature. Cooldowns on failing deployments (allowed_fails), retries with fixed or exponential backoff, order-based priority tiers, cross-group fallbacks (max_fallbacks default 5), dedicated fallback paths for context window and content policy errors, weighted failover within a group, session affinity with re-pinning rules
- Monitoring and cost attribution: spend tracking per key, user, team and request tags, backed by a model cost map; x-litellm-response-cost header per response; spend logs record model_group and the member deployment that served it; a documented workflow for debugging cost discrepancies
- Source: https://docs.litellm.ai/docs/routing, https://docs.litellm.ai/docs/proxy/auto_routing, https://docs.litellm.ai/docs/proxy/cost_tracking (vendor docs, opened 2026-10-29; page dates not shown). Source type: vendor

### Portkey AI Gateway (and similar gateways)
- Routes on: declarative Gateway Configs with three strategies: fallback (ordered targets), loadbalance (weighted), and conditional (rules over request metadata, request parameters or URL path, with a default target). Conditions are operator written, for example "metadata.plan == paid then fine-tuned model"
- Measured quality bar: no; routing is rule based. Quality is whatever the operator encodes
- Fallback: first-class strategy; retries and timeouts configurable per target
- Monitoring and cost attribution: Portkey's product is logging, metadata tagging and cost dashboards per metadata key (vendor positioning; the specific cost pages were not opened this session)
- Source: https://portkey.ai/docs/product/ai-gateway/conditional-routing (vendor docs, opened 2026-10-29; page date not shown). Source type: vendor
- Similar gateways (not opened this session): Kong AI Gateway, Cloudflare AI Gateway, Helicone, Vercel AI Gateway. They share the rule-based routing plus fallback plus spend-logging shape

## Judge bias and calibration literature

### Bias catalogue
- Zheng et al., "Judging LLM-as-a-Judge with MT-Bench and Chatbot Arena" (NeurIPS 2023 Datasets and Benchmarks; arXiv v1 2023-06-09, v4 2023-10-15). Names position bias, verbosity bias, self-enhancement bias and limited reasoning ability. Reports that GPT-4 as judge reached over 80 percent agreement with human preferences, the same level as human-human agreement, on MT-Bench and Chatbot Arena. Mitigations: swap positions and only count consistent verdicts, few-shot judging, reference-guided judging. Source: https://arxiv.org/abs/2306.05685 (paper)
- Panickssery, Bowman, Feng, "LLM Evaluators Recognize and Favor Their Own Generations" (arXiv 2024-04-15). Shows a causal link between a model's ability to recognize its own outputs and self-preference; fine-tuning to increase self-recognition increases self-preference. Direct justification for independent_of_generator in this project. Source: https://arxiv.org/abs/2404.13076 (paper)
- Wataoka et al., "Self-Preference Bias in LLM-as-a-Judge" (arXiv v1 2024-10-29, v2 2025-06-21). Proposes a quantitative metric for self-preference and finds GPT-4 exhibits a significant degree of it; links the bias to lower perplexity of the judge's own style. Source: https://arxiv.org/abs/2410.21819 (paper)
- Shi et al., "Judging the Judges: A Systematic Study of Position Bias in LLM-as-a-Judge" (arXiv v1 2024-06-12). 15 judges, MT-Bench and DevBench, 22 tasks; metrics repetition stability, position consistency and preference fairness; position bias depends on judge, task and the quality gap between answers. Source: https://arxiv.org/abs/2406.07791 (paper)
- Ye et al., "Justice or Prejudice? Quantifying Biases in LLM-as-a-Judge" (arXiv 2024-10-03). CALM framework quantifying 12 bias types (including position, verbosity, self-enhancement, authority, bandwagon, refinement-aware). Source: https://arxiv.org/abs/2410.02736 (paper)
- Chen et al., "Humans or LLMs as the Judge? A Study on Judgement Biases" (arXiv v1 2024-02-16). Misinformation oversight, gender, authority and beauty bias in both human and LLM judges. Source: https://arxiv.org/abs/2402.10669 (paper)
- Gu et al., "A Survey on LLM-as-a-Judge" (arXiv v1 2024-11-23, v3 2025-01-09). Consolidated taxonomy of reliability threats and mitigations. Source: https://arxiv.org/abs/2411.15594 (paper)
- Tan et al., "JudgeBench: A Benchmark for Evaluating LLM-based Judges" (arXiv v1 2024-10-16, v2 2025-04-05). Argues that crowdsourced preference agreement is a poor proxy where factual or logical correctness is at stake and tests judges on objectively verifiable pairs. Relevant because this project's bar is agreement with gold labels, which is the right target for correctness-style judge tasks and a weaker fit for taste tasks. Source: https://arxiv.org/abs/2410.12784 (paper)
- 2026 mitigations: "A CaLLM Judge is a Better Judge" (arXiv 2026-10-13) applies multicalibration so that each documented bias becomes a miscalibration on a subgroup to be corrected, https://arxiv.org/abs/2610.18108; "DIAL: Position-Debiased LLM Judges with Adaptive Human Preference Calibration" (arXiv 2026-09-25) separates judge-specific position effects and calibrates toward a human target using limited human comparisons, https://arxiv.org/abs/2609.31215 (papers; abstracts read via the arXiv API)

### Calibration against human labels, agreement metrics and confidence intervals
- Agreement metrics in common use: raw agreement rate (what this project's bar measures), Cohen's kappa for two raters on categorical labels, Krippendorff's alpha for many raters, Spearman or Kendall correlation for scores, and pairwise win-rate agreement with position swap (Zheng et al. 2023). The judge literature mostly reports raw agreement and correlation; kappa is reported less often than it should be given label imbalance
- Confidence intervals: this project uses the Wilson score interval lower bound on a Bernoulli agreement rate (Wilson 1927; recommended over the Wald interval by Brown, Cai and DasGupta 2001, "Interval Estimation for a Binomial Proportion", Statistical Science 16(2), not opened this session). This is textbook statistics and should be described as such
- Prediction-powered inference (Angelopoulos et al., arXiv 2023-01-23, published in Science 2023) gives valid confidence intervals for a population quantity when a small gold-labeled set is combined with many model predictions, with no assumptions on the predictor. It is the principled way to get tighter intervals than this project's gold-only Wilson bound when judge calls are cheap and gold labels are scarce. Source: https://arxiv.org/abs/2301.09633 (paper)
- Dorner, Nastl, Hardt, "Limits to scalable evaluation at the frontier: LLM as Judge won't beat twice the data" (arXiv v1 2024-10-17, v3 2026-01-06). When the judge is no more accurate than the evaluated model, no debiasing method can reduce the required amount of ground truth labels by more than half. Implication for this project: calibration sets must be real gold labels, and a judge that is weaker than the generator should not be expected to be rescued by statistics. Source: https://arxiv.org/abs/2410.13341 (paper)
- Jung et al., "Trust or Escalate: LLM Judges with Provable Guarantees for Human Agreement" (arXiv 2024-07-25). Selective evaluation: estimate judge confidence (Simulated Annotators), abstain or escalate when confidence is low, and guarantee a user-specified human agreement level; Cascaded Selective Evaluation starts with cheaper judges and escalates to stronger ones only when needed. This is the closest published relative to "cheapest judge that clears an agreement bar", operating per instance rather than per task. Source: https://arxiv.org/abs/2407.18370 (paper)
- "From Self-Confidence to Statistical Accuracy: Scaling Human-in-the-Loop Evaluation with Direct and LLM-Assisted Auditing" (arXiv 2026-10-26) studies how calibration quality and inference cost of LLM judges determine whether they help a human audit reach statistical accuracy. Source: https://arxiv.org/abs/2610.35698 (paper; abstract only)
- Leaderboard fragility: Alzahrani et al., "When Benchmarks are Targets" (arXiv v1 2024-02-01) shows MMLU-style rankings shift by up to 8 positions under minor perturbations such as answer order. Supports DESIGN.md 4.4: leaderboard priors order candidates for cold start but never clear a bar. Source: https://arxiv.org/abs/2402.01781 (paper)

### 2026 routing work (arXiv, October 2026, abstracts read via the arXiv API on 2026-10-29)
- "Predictable performance is suboptimal, and what it means for model routing" (2026-10-22): a performance predictor only beats the candidate model's own self-confidence when the candidate is suboptimal on the task or the predictor adds significant capacity. Relevant caution for anyone planning v2 per-prompt routing. https://arxiv.org/abs/2610.31428
- "Who Pays for Efficient Inference? Confidence-Based Small-to-Large LLM Routing Across Tasks and Languages" (2026-10-16): 72 configurations, 42,288 predictions; confidence-based escalation helps on reading comprehension and topic classification (AUC 0.61 to 0.71) and gives no consistent gain on MMLU-ProX-Lite (AUC 0.51). Shows that cascade benefit is task dependent, which supports measuring per task. https://arxiv.org/abs/2610.23249
- "Chance-Constrained Personalized LLM Routing with Online Preference Learning" (2026-10-15): constrained contextual bandit that minimizes cost subject to a high-probability quality constraint; the online analogue of this project's offline bar. https://arxiv.org/abs/2610.22695
- "COMPASS: Routing via Capability-Oriented Model Profiling with Adaptive Search, Selection, and Tool Use" (2026-10-20): an agentic router that reads performance and cost evidence through tools and adapts to new models by reading new evaluation records; reports 69.85 percent at 139.57 USD vs RLCascadeRouter 69.14 percent at 180.22 USD on LLMRouterBench (self-reported). https://arxiv.org/abs/2610.27822
- Others in the same week: RouterWorld (latency-aware, 2026-10-19), RouteWeaver (2026-10-14), VeriRouter (verifiable routing with ZK proofs, 2026-10-12), carbon-aware routing (2026-10-26), security-conditioned model-and-budget selection (2026-10-13). Titles and dates from the arXiv API; not read in full

## Where a per-task calibrated judge router fits

What is standard practice (do not claim as new):
- Routing to a cheaper model when quality allows, with a cost-quality tradeoff knob: FrugalGPT, RouteLLM, Hybrid LLM, Not Diamond, OpenRouter cost_tier, LiteLLM auto routing tiers
- Ordered fallbacks, retries, cooldowns and per-attempt logging: LiteLLM, Portkey, OpenRouter
- Spend logging by key, user, team or tag: LiteLLM, Portkey and every gateway
- Excluding the generator from judging its own output: a direct consequence of the self-preference literature (Zheng et al. 2023; Panickssery et al. 2024)
- Using labeled data to decide which model to use for a task: Shnitzer et al. 2023, Hybrid LLM, Not Diamond custom routers, COMPASS 2026
- Wilson score intervals for binomial proportions: textbook statistics

What is uncommon in the surveyed systems and is a fair thing to highlight, stated modestly:
- An explicit per-task admission criterion: a model is eligible only if the lower end of a confidence interval on its measured agreement with gold labels clears a task-specific bar, with a minimum trial count; priors from public leaderboards can never clear the bar. The surveyed routers optimize an expected tradeoff or a per-prompt prediction; none of the opened systems gate on a conservative bound with a minimum sample size per task. "Trust or Escalate" offers a stronger per-instance guarantee for pairwise judging but needs a confidence estimator and a cascade; this project is the simpler per-task version
- Treating judge and eval calls as the workload. Routers above target end-user prompts. The judge literature is about biases and agreement but does not package model selection; this project sits at the intersection and is small enough to audit
- Two flavors that share one pipeline (cost_effective vs cost_blind) so that spend stays visible even when the team chooses quality; a convenience, not a research contribution

What this project does not do, which the prior art does:
- No per-prompt difficulty prediction or confidence-based cascade (DESIGN.md 12 defers this); FrugalGPT, RouteLLM, Hybrid LLM and most 2026 papers are per-prompt
- No online learning or drift detection (chance-constrained bandits, LiteLLM Thompson-sampled pools)
- No debiasing of the judge itself (position swap, multicalibration, DIAL); agreement is measured as is, so position and verbosity bias in the calibration set flow into the measured rate
- No tighter intervals from unlabeled judge calls (prediction-powered inference)

Suggested README sentence: "Routing on cost and quality, fallbacks and spend attribution are standard (see prior-art.md). What this library adds is small: each candidate must clear a per-task agreement bar with a Wilson lower bound over at least min_samples gold-labeled trials before it can be chosen, and leaderboard numbers can only order candidates, never admit them."

## Gaps

- Martian's current routing algorithm, pricing and fallback behavior: not found on the public pages opened; the site now positions Martian as an interpretability lab
- Not Diamond custom router training page returned HTTP 404 at the URL tried; details of how custom routers use evaluation scores (threshold, confidence) not found
- Portkey cost dashboard and retry pages not opened; the claim about per-metadata cost reporting is from product positioning only
- Full texts of the October 2026 routing and judge papers were not read; only titles, dates and abstracts via the arXiv API
- Brown, Cai and DasGupta 2001 and Cohen 1960 / Krippendorff cited from memory as standard references, not opened this session
- No independent benchmark comparing shipped routers (Not Diamond, OpenRouter Auto, LiteLLM auto routing) on the same workload was found; RouterBench covers research routers on 2024 models
- A public web search for 2026 routing work returned no results through the search tool; the arXiv API was used instead

## Caveats

- Vendor documentation pages do not show publication dates; "opened 2026-10-29" records when the content was checked, not when it was written
- All research papers listed are older than the brief's 120 day window except the October 2026 arXiv items and Dorner et al. v3 (2026-01-06); dates are given per item
- Headline numbers from papers (98 percent cost reduction, 2x cost reduction, 40 percent fewer large-model calls, over 80 percent judge-human agreement) are self-reported on the authors' benchmarks with 2023 to 2024 models; they do not transfer to the model set in the brief. Benchmark saturation and contamination affect every leaderboard-derived prior (Alzahrani et al. 2024)
- Shipped routers (OpenRouter spend share, LiteLLM tiers) are described from their docs, which are vendor claims; no independent measurement of their routing quality was found
- The arXiv API search for October 2026 papers used two queries; coverage of 2026 routing work is a sample, not a census
- No scores for the models named in the brief are reported here because this file surveys methods, not model quality; per-model numbers belong in the priors research file
