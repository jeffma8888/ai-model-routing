# Escalation: start on a cheap model, hand up on a signal (2026-11-20)

Question: how can a call start on a cheap model and hand the work up to a stronger one when a signal appears during the work, without weakening the library's guarantee that a route clears its task's bar on measured data, and which public data, with no API key, can test it?

Short answer: treat a cascade (a cheap model, a named signal the caller computes, and a strong model) as one routing candidate with calibration rows of its own. It clears a bar only when the Wilson lower bound of its own measured successes does, so it never inherits the strong model's pass. Its expected cost is the cheap model's cost plus the measured escalation share times the strong model's cost of re-reading the context so far, uncached, and answering. `DESIGN.md` 7 v1.532 specifies it for row ESC2. Of the converted public datasets, tau2-bench is the one that records both a signal a harness can count during the work (the agent calls made so far) and the tokens of each call, so row ESC3 runs there first with the signal "more than N agent calls". LiveCodeBench may give the failed-check signal (a failed public test case), success only, since it records no cost; row ESC1b checks that and measures both signals before ESC3.

## Facts

- The idea comes from the cascade pattern in [prior-art.md](prior-art.md) (FrugalGPT, AutoMix, Trust or Escalate): try the cheap model first, escalate when a score says so
- What the library has today: the executor's fallback (`DESIGN.md` 7) moves to the next model of a route when the caller's `validate` check fails, and every model of that route clears the bar on its own (5.3); the below-bar option (5.3 v1.201) adds models under the bar that only the check vouches for
- What is new: the cheap model of a cascade need not clear the bar; the cascade as a whole must, measured as a whole
- The signal is the caller's: only the caller's harness sees its tests, tool calls or services, so the library names a signal and calls the caller's function on the cheap model's result
- The spec is `DESIGN.md` 7 v1.532; no code reads it until row ESC2
- No results file, package, README or workflow change in this note

## Why a cascade is one candidate

- A cascade's success on a task is `P(kept and the cheap answer passes) + P(escalated and the strong answer passes)`. The items that escalate are the ones the signal picks, often the hard ones, so the strong model's rate on them is not its rate on the task, and a cheap answer the signal keeps but that is wrong counts against the cascade and never shows in the strong model's rate
- So a cascade gets trials of its own: one item run through the whole cascade is one trial, a success when the final answer passes the task's check, whichever model gave it. Its Wilson lower bound, at the task's or slice's bar and `min_samples`, admits it exactly as a model's admits a model, and priors never admit it
- Cost: `cheap cost + p x strong cost`, with `p` the share of the cascade's own calibration rows that escalated. The cheap model's tokens count on every row, whether it escalated or not and whether its answer was right. The hand-up is priced as the strong model reading the context so far, the input and the cheap model's output, as uncached input: a prompt cache belongs to one model, so a hand-up that carries the cheap model's work reads it again at the strong model's full input price. The executor of `DESIGN.md` 7 v1.532 starts the strong model fresh, which reads only the input, so for it the price is an upper bound, the conservative assumption
- Each cascade with its own signal threshold is its own candidate (`calls-over-10` and `calls-over-20` are two), so choosing a threshold is the same choice among measured candidates the router already makes among models

## Signals the public data can test

| Dataset (`DESIGN.md`) | What a row records | Signal a replay can compute | Cost of the cheap part | Use |
|---|---|---|---|---|
| tau2-bench (12.14) | per (task, agent, trial) a conversation: each agent message with its `tool_calls` and, on most, a `usage` of prompt and completion tokens (12.14 sums those that are not null), and a program-checked reward; four 2025 agents in three domains | more than N agent calls, counted as the run goes; the agent's own `transfer_to_human_agents` call, offered in all three domains, which some tasks' policies require, so it can end a correct run as well as a stuck one | each call priced from its own `usage` at list price | ESC3 first |
| Longtail-SWE (12.25) | per (task, model, run) token totals and a test-checked label; a run sums a median 38 model calls ([longtail-delegation.md](longtail-delegation.md)) and the release records no per-call tokens | more than N model calls | needs the stated split of [longtail-per-call.md](longtail-per-call.md), an assumption the release cannot check | second for the call-count signal |
| LiveCodeBench (12.16) | per (problem, model) a graded list of samples; in the smallest kept file, `O1-Mini-2024-09-12` (3,636,170 bytes, 880 problems), read on 2026-11-20, 236 of the 278 failed first samples hold in `metadata` the failing test's `inputs`, `expected` and `output` and an `error_code`, 35 an `error` in place of `output`, and 7 no test at all (only an error code and message), while each of the 602 passed ones holds only its `execution time`; whether the failing test is one of the problem's public test cases is not recorded | a failed public test, a check the caller can run, only if the failing test can be matched against the public test cases of the problem release, which this repo does not pin | none: the files record no cost (12.16, [livecodebench-cost.md](livecodebench-cost.md)), so `cost_blind` only | ESC3 second, success only, if ESC1b finds the match |
| LLMRouterBench (12.18) | per (item, model) a score and a cost | on `livecodebench` a caller holds the public test cases, but the records keep no test-level result ([check-fallback.md](check-fallback.md)) | recorded | no: only the record's own score, the upper bound check-fallback.md measures |
| RouterBench, AutoBench 2026, the response bank, the registry pair (12.6, 12.9, 12.20, 12.23) | one answer per (item, model) and no run-time trace | only a check on the answer, which their labels make with an answer key a caller lacks | recorded | no |
| TRAIL (13.11) | real hand-offs with per-call tokens | call counts | recorded | no: no success label |
| AgentsSci ([hand-off-data.md](hand-off-data.md), not converted) | the same solver answering directly and under three protocols that spend more calls | the protocol's extra calls | per-item tokens for one of ten settings | no: more effort on one model, not a hand-up to a stronger one |

- A second service touched: no converted dataset records which service a call touches, so no public replay tests it; a caller who sees it can still pass it as a signal
- The model saying it is stuck: the nearest public trace is tau2-bench's `transfer_to_human_agents`, above; ESC1b counts how often a run that calls it passes

## What row ESC3 runs

- Dataset: tau2-bench, the 12 pinned run files of 12.14, trial 0, one task per domain as in 12.15
- Cascades: each pair of the four agents with the cheap one at the lower list price, and the signal `calls-over-N` for each N of a grid ESC1b fixes from the call counts
- A row of the replay: escalated when the cheap run makes more than N agent calls; correct is the strong run's reward when escalated and the cheap run's otherwise; cost is the list-price cost of the cheap run's first N calls (all of them when it does not escalate) plus, when escalated, the prompt and completion tokens of its Nth call as the strong model's uncached input and the strong run's list-price cost
- Compared at the same bars, held-out: the best single model, the routed row of 12.15 and the best cascade, each with its success and cost, and the escalation share. The sliced route exists only where slices are committed (12.27, 12.28), so it is compared on LiveCodeBench, if ESC1b clears it there
- Limits the README part states: a signal measured on a benchmark may not exist in your product. The strong run in the data starts fresh, with its own simulated user, so the replay assumes a hand-up that restarts the conversation; a write the cheap agent made before the hand-up would stay in a real system's state, which the replay cannot see (ESC1b says which tools write)

## What row ESC2 implements

- `DESIGN.md` 7 v1.532: a `Cascade(cheap, strong, signal)` with an `id` of `cheap>strong@signal`; `Task.cascades`; a cascade's own trials and escalations in `Stats`; candidates after the registry models when `select` is asked for them, each ruled by rules 1 to 5 on both models and by its own Wilson bound; the routing cost above; the executor running the cheap model, the caller's signal, then the strong model; and two record keys, `cascade` and `escalated`

## Not settled here (row ESC1b)

- The measured signals: on tau2-bench the agent calls per run and how a run's success falls with them, the share of agent messages with a `usage`, the runs that call `transfer_to_human_agents` and their success, and which tools of each domain write to its state, all from the pinned files and the pinned repo
- On LiveCodeBench, whether a failed sample's failing test can be matched against the release's public test cases at a pinned revision, and in what order the release's runner checks public and private cases
- Then the dataset and signal above stand or change before ESC3
