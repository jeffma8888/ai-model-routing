# Public data with real hand-offs (as of 2026-11-06)

Question: is there a public dataset that records a parent agent handing work to a sub-agent, with per-call token counts and a success label for the parent's task, so that the delegation evidence could measure what it now assumes? The committed delegation results (`DESIGN.md` 13.9 and 13.10) come from single-call AutoBench answers with a stated grid for the parent's context C, the brief B, the result R and the later parent calls T, and they credit the delegate with its answer to the whole question, as if the brief lost nothing. The break-even table in `evidence/delegation/RESULTS.md` only bounds how lossy a brief may be before delegating stops paying.

Method: every revision below is the commit or dataset SHA that the GitHub or Hugging Face API returned on 2026-11-06. Licences are as the repo's LICENSE file, the API's licence field or the dataset card states them ("none stated" if absent). Sizes are the API's file sizes. Files were downloaded outside the repo and read with the standard-library `json` module; nothing from them is committed. Counts are from those reads unless a line says they come from a card.

The 13.1 inputs named below are those of `Router.decide_delegation`: the context C (`context_tokens`), the brief B (`brief_tokens`), the result R (`result_tokens`), the work's own input and output tokens per call, the number of work calls K (`work_calls`), the later parent calls T (`carry_turns`) and whether inline work takes a parent call of its own (`inline_separate_call`).

## Summary

- None of the four candidates can test the lossless-brief assumption. None runs the same work both inline and through a sub-agent, so none can show what a brief loses
- TRAIL comes closest: MIT, real hand-offs from a manager agent to a search sub-agent, and per-call token counts (1,507 model-call spans with prompt and completion counts in its GAIA traces). Its 60 sub-agent runs make 3 to 31 model calls each (median 15), so real delegated work is far more calls than the one or two the committed grid assumes. But its files hold no success label, and the manager and the sub-agent are the same model
- Who&When records 689 hand-off messages in 57 of its 58 hand-crafted multi-agent logs, but without token counts, and every log was picked because it failed
- MAD (CC-BY-4.0) has the most traces, 1,642 over 7 multi-agent frameworks, but each trace is free text, with no structured success label or token counts
- A fifth candidate, read on 2026-11-12 ([its own section](#agentssci-protocol-routing-2026-11-12)): AgentsSci's protocol-routing data (CC-BY-4.0) pairs one direct answer with three protocols that spend more calls of the same solver (one of self-correction, two multi-agent) on 15,088 (setting, problem) rows, which measures escalation, not a hand-off: no brief or result is recorded, and per-item tokens cover one of its ten settings
- A search on 2026-11-14 ([its own section](#a-fresh-search-for-paired-inline-and-delegated-runs-2026-11-14)) finds two releases that run the same work two ways on the same items, each with a program-checked success label per path: the Attention Tax, Handoff Tax ledger runs (data CC BY 4.0), one open model on a synthetic ledger task, 300 items done in one context and as a serial chain of fresh contexts linked by notes (a successor takes over; no parent reads a result back), with per-call token counts, where the chain solves more items at every depth on far fewer prompt tokens and a 100-item probe shows no aggregate loss from a short note against the full history, though items are lost and gained both ways; and the TokenSave runs (CC-BY-4.0), 12 code-search questions worked inline and through sub-agents with a per-run cost, where a sub-agent on the parent's own model costs more than working inline. It recommends a converter for the ledger runs (row E23)
- So the delegation evidence keeps its stated grid. The section after the four candidates says what the smallest dataset that could test the assumption would have to record

## Candidates

### 1. TRAIL (closest; no success label in the files)

- URL: https://github.com/patronus-ai/trail-benchmark, folder `benchmarking/data`. The gated Hugging Face dataset https://huggingface.co/datasets/PatronusAI/TRAIL lists trace files under the same names (the first 39 GAIA names it lists match the GitHub ones); its files were not read
- Revision: GitHub 0ffbed9db859b4a66250dc783fa4dccf86869595 (commit date 2025-05-14); Hugging Face b424ce63d5973d5dcd7169b1bc3c07ccdee276d1 (last modified 2025-05-15)
- Licence: MIT (the GitHub repo's LICENSE file and API licence field, and the dataset card). The Hugging Face copy is gated: its card asks users "to not reshare this dataset outside of a gated or private repository on the HF hub", and says it must not be used to train systems "intended to automate human evaluation". The GitHub copy is public. A converter would commit only derived numbers, as this repo does for every dataset
- Files: 117 GAIA traces (111,205,744 bytes) and 31 SWE-bench traces (74,366,103 bytes), one JSON file each, plus annotation files in `benchmarking/processed_annotations_gaia` and `benchmarking/processed_annotations_swe_bench`. The card's text says 118 and 30; its `dataset_info` block says 117 and 31, as the files do
- What it records: OpenTelemetry spans from a smolagents system. Every GAIA trace has a top agent span, `CodeAgent.run` (117 in 117 traces); in the one trace whose attributes were read in full it lists one managed agent, `search_agent` ("A team member that will search the internet to answer your question"). In 47 of the 117 GAIA traces the top agent hands work to a sub-agent: 60 sub-agent runs in all (`ToolCallingAgent.run` spans inside the top agent's run). Each model call is a span (name ending `__call__`) with `llm.token_count.prompt` and `llm.token_count.completion`: 1,507 such spans over the 117 GAIA traces. The 1,507 spans that carry a model name all name `o3-mini` (`openai/o3-mini`)
- The 60 sub-agent runs: 3 to 31 model calls each (median 15); 5,508 to 357,993 prompt tokens per run (median 94,868.5) and 1,990 to 21,188 completion tokens (median 8,343.5); the first model call of each run reads 549 to 765 prompt tokens. The run's recorded input (`input.value`, the brief with the framework's wrapping) is 1,448 to 2,418 characters, and its recorded output (`output.value`) 384 to 4,345
- Annotations: each trace has located errors (keys `category`, `description`, `evidence`, `impact`, `location`) and scores such as `reliability_score`, `instruction_adherence_score` and `plan_opt_score`, each with a reasoning text. These grade the trace, not whether its answer is right
- What it lacks: a success label. The files hold each run's final answer, but not the GAIA reference answers (the string `true_answer` occurs in all 117 GAIA traces, but as a column name in a dataset description); a label would need the answers from the GAIA validation set, a separate dataset not checked here. No GAIA task is also run without the sub-agent, and the sub-agent is the same model as its parent, so a cheaper delegate is never tried. The SWE-bench traces were not scanned for sub-agent runs
- 13.1 inputs it could measure: K directly, as the model calls per sub-agent run. Everything else only as observed usage, not as the 13.1 inputs themselves: each call's `llm.token_count.prompt` counts everything that call read (the sub-agent's instructions, the brief and the run's history so far), while 13.1 and 13.2 take the new input S_in each call adds and grow the context from it, so summed or mean prompt counts would double-count the context if used as S_in. The spans also hold each call's input messages (`llm.input_messages.*` in the trace read), so the new input per call could be split off by message, but only as text unless a tokenizer is assumed. C is approximated only by the top agent's prompt count on the call that hands off; B and R only as text lengths (the input and output values). Not `inline_separate_call` (no inline run), and not T without parsing which later calls re-read the result

### 2. Who&When (failure logs only; no token counts)

- URL: https://github.com/mingyin1/Agents_Failure_Attribution, folder `Who&When` (the counts below are from this copy). The Hugging Face dataset https://huggingface.co/datasets/Kevin355/Who_and_When holds a `Who&When` folder with the same two subfolders, beside two parquet files
- Revision: GitHub b2bae5c5b06d681d04ea5e9b63b7a30525c04925 (commit date 2026-01-06); Hugging Face 59b9fcba1aaed7bbf206b5f4d3c68b8face2f49c (last modified 2025-12-21)
- Licence: MIT on GitHub (the repo's LICENSE file and API licence field); none stated in the Hugging Face card data or tags
- Files: `Algorithm-Generated` (126 JSON files) and `Hand-Crafted` (58), each a log of one question from GAIA or AssistantBench, as the card says; the one file sized here, `Algorithm-Generated/1.json` from the Hugging Face copy, is 11,626 bytes
- What it records: the card calls them "184 annotated failure tasks", each with the agent the annotators hold responsible, the decisive step and a reason. The card names Magentic-One among the hand-crafted systems, and in the 58 Hand-Crafted logs an orchestrator addresses one agent at a time: 57 of them hold such messages, 689 in all (602 `Orchestrator (-> WebSurfer)`, 41 to `Assistant`, 36 to `FileSurfer`, 10 to `ComputerTerminal`). The 126 Algorithm-Generated logs come from CaptainAgent systems, as the card says: named experts take turns, and no message's speaker name contains `->`
- Labels: `is_correct` is False in all 126 Algorithm-Generated logs; none of the 58 Hand-Crafted logs has an `is_correct` key, and all 58 have a key named `is_corrected` instead. Every log is a failure picked for annotation, so no success rate can be read from them
- What it lacks: token counts (each message has `content` and `role`, plus `name` in the Algorithm-Generated logs), model IDs per call, cost, successful runs, and any run of the same question without hand-offs
- 13.1 inputs it could measure: the number of hand-offs per task, and B and R only as message text lengths. Not C, the work's own tokens, K, T or `inline_separate_call`

### 3. MAD, the MAST traces (most traces; free text)

- URL: https://huggingface.co/datasets/mcemri/MAST-Data (code: https://github.com/multi-agent-systems-failure-taxonomy/MAST)
- Revision: 95118ac951421753cf1deb87ddea3b01e693c41b (last modified 2026-08-13)
- Licence: CC-BY-4.0 (the card and the API tags). The GitHub code repo has no licence in its API licence field
- Files: `MAD_full_dataset.json` (199,574,367 bytes, 1,642 records) and `MAD_human_labelled_dataset.json` (2,662,908 bytes, 19 records)
- What it records: per record `mas_name`, `llm_name`, `benchmark_name`, `trace_id`, `trace` (keys `key`, `index`, `trajectory`) and `mast_annotation`, the 14 failure-mode codes of the MAST taxonomy, which the card says "are produced by an LLM judge, not by human labelling". Frameworks: AG2 597, MetaGPT 430, ChatDev 330, Magentic 195, OpenManus 30, AppWorld 30, HyperAgent 30. Models as the card names them: GPT-4o 751 and GPT-4o-mini 168 (`openai/gpt-4o`, `openai/gpt-4o-mini`), and three named by family only, Claude 323, Qwen 200 and CodeLlama 200. Benchmarks: ProgramDev-v2 400, ProgramDev 390, GSM 223, Olympiad 206, GAIA 195, MMLU 168, Test-C 30, SWE-Bench-Lite 30
- What it lacks: a structured success label (words such as "success" occur in the trajectory text of many records, but no field holds an outcome) and structured token counts. The string `prompt_tokens` occurs in the trajectory text of 330 records (all 330 ChatDev ones) and 2 HyperAgent ones, so token counts might be parsed from those logs; that parse was not attempted. No task is run both with and without hand-offs
- 13.1 inputs it could measure: possibly per-call token counts in the ChatDev logs, after a text parser; nothing else without one

### 4. HAL traces (not taken: no stated licence)

- URL: https://huggingface.co/datasets/agent-evals/hal_traces
- Revision: e7dcedc82b4f4bc819a170fd6616bdb44841c71e (last modified 2026-02-01)
- Licence: none stated. The card data and tags have no licence, and the dataset has no README (`README.md` at that revision is "Entry not found")
- Files: the API lists 381 files; the first 14 after `.gitattributes` are zip archives named by benchmark, agent and model (for example `assistantbench_assistantbench_browser_agent_gpt5_1754598271_UPLOAD.zip`). None was opened
- It stays out by the rule `research/datasets.md` applies to SWE-bench experiments and the two routing datasets: no results from a dataset without a stated licence

## What the smallest dataset that could test the lossless brief would record

- One task with a program check (tests passing, a database state, an exact answer), so the label needs no judge
- Each item run three ways, each scored by the same check on the parent's final output: inline (the parent does the work with its context); delegated (the parent writes a brief, the delegate does the work from the brief alone, the parent uses the result); and a matched control, the same delegate on the same subtask with the same tools, call budget and parent integration, given the parent's full context in place of the brief. Delegated minus the control is then the brief's loss, measured, where the committed evidence assumes it is zero; delegated against inline is the decision's real trade. The delegate's own work should be scored too, apart from the parent's task. The delegate's one-call answer to the whole item, which AutoBench records and the committed evidence credits, is not that control: it differs from the delegated path in call pattern and parent integration as well as in the brief, so a gap against it is an end-to-end gap, not the brief's loss
- Every model call in order, with its model ID (`vendor/model`), its path (inline, delegated or control), its role (parent or delegate), prompt tokens, cached prompt tokens and completion tokens, plus the links that tie each hand-off to its brief and its result and the message boundaries inside each call's prompt, with the new input counted apart from the context it re-reads. Only then are C, B, R, the work's own S_in and S_out, K and `inline_separate_call` read from the records instead of a grid, and T needs one more mark: which parent call is the next one after the work and which later calls still re-read what the work left
- The brief and the result as text, or at least their token counts, so the brief's length can be set against its loss
- One delegate is enough to measure the brief's loss, and it may be the parent's own model: `DESIGN.md` 13.2 shows delegating to the parent's own model can save the re-reads of a large context. A second delegate with a lower list price than the parent is optional; it would also test the price side of the `cost_effective` decision, which TRAIL cannot, since its sub-agent is its parent's model
- At least 60 items per (parent, delegate) pair, and more in practice: the evaluator's seeded split is a hash threshold, not an exact half, so at 60 items a calibration half reaches the default `min_samples` of 30 (`model_routing/evaluate.py`) on some seeds only. The tau2-bench airline task shows the spread: 50 items give calibration halves of 16 to 35 over seeds 0 to 49 (`DESIGN.md` 12.14). Check the calibration count per seed
- A stated licence and a pinned revision, as for every dataset here

## Recommendation

- Keep the stated grid and the lossless-brief caveat in the README and `DESIGN.md` 13.9: no candidate measures the brief's loss
- TRAIL is the one candidate worth a converter, and only to report real sub-agent sizes beside the grid: its 60 runs make 3 to 31 model calls (median 15) against the grid's one or two, and read 5,508 to 357,993 prompt tokens per run. That would set observed sub-agent usage beside the sizes the grid assumes (as usage, not as the 13.1 inputs, for the reason given under TRAIL), not measure the brief's loss or the decision's outcome
- Look again when a public agent benchmark publishes paired inline and delegated runs with per-call usage, or adds a sub-agent mode to a test-checked benchmark whose per-item results are already public, as tau2-bench publishes its paper runs

## AgentsSci protocol routing (2026-11-12)

Question: the 2026-11-11 survey of [datasets.md](datasets.md) names AgentsSci/EMNLP_Cost-Aware-Protocol-Routing as a lead for the delegation evidence, since it runs each problem both as one direct answer and under three protocols that spend more calls, one of self-correction and two multi-agent. Does a protocol record a hand-off in the `DESIGN.md` 13 sense, a parent passing a brief to a sub-agent and reading back its result, and could the delegation evidence use the data?

### Source

- URL: https://huggingface.co/datasets/AgentsSci/EMNLP_Cost-Aware-Protocol-Routing; the paper is https://arxiv.org/abs/2608.14927 (v1 submitted 2026-08-14; the card says Findings of EMNLP 2026)
- Revision: 8d0aff6cbccf280235374fe635f9f4c212237e39 (last modified 2026-10-30), the revision the 2026-11-11 survey read, re-read from the Hugging Face API on 2026-11-12; not gated
- Licence: CC-BY-4.0 (the card data and the API tag `license:cc-by-4.0`). The card says that project-authored content, "all derived measurements" among it, is CC-BY-4.0, and that no upstream problem text or gold answers are included, so each benchmark's own licence (Apache-2.0 for OmniMath, MIT for JEEBench and SciBench, CC-BY-SA-4.0 for LAB-Bench) governs only its own content
- Files: 46, 20,677,913 bytes by the API's file tree at that revision, 28 of them CSV. All 46 were fetched from `https://huggingface.co/datasets/AgentsSci/EMNLP_Cost-Aware-Protocol-Routing/resolve/<revision>/<path>` into a folder outside the repo, and `shasum -a 256 -c registry/checksums.sha256` in that folder reports OK for all 44 files the release's own manifest lists. The counts below read two of them: `data/matched_labels.csv` (2,814,373 bytes, sha256 e2080688cad5bf5b2b5de70ac461949add14fcefd76e4fde3cee93bf5fb08579) and `data/costs/omnimath_per_protocol_costs.csv` (395,362 bytes, sha256 4c239eaeee7543c5b7b57158ebdbaf40046926b7281a72038f93037435332ae6). Nothing from them is committed

### What a row records

- The default config, `matched_labels`, holds 15,088 rows of 15 columns, one per (setting, problem): `baseline_correct`, `single_correct`, `per_correct` and `broadcast_correct`, each 0 or 1 ("judged correct", `docs/schema.md` says, without saying how; `registry/models.csv` gives `openai/gpt-oss-120b` the role `actor_and_evaluator`), and `oracle_label`, the first protocol in the order Baseline, Single, PER, Broadcast that succeeded
- A setting is one benchmark condition with one solver: 5 conditions (OmniMath competition math, 4,181 problems; LAB-Bench text with no tools, 1,542; LAB-Bench strict in-prompt evidence, 741; SciBench text only, 565; JEEBench text only, 515) by 2 open-weight solvers, `openai/gpt-oss-120b` and `google/gemma-4-31B-it`: 10 settings over 6,803 distinct problems. Neither solver is in `model_routing/data/models.json`
- The protocols, as `registry/protocols.csv` describes them: Baseline, "A single direct one-shot solver call followed by evaluation. No revision, no second agent."; Single, "One solver iterates on its own answer with evaluator feedback (iterative self-correction)."; PER, "Hierarchical planner-executor-reviewer: a planner decomposes, an executor solves, a reviewer checks."; Broadcast, "Multi-agent deliberation in which peers exchange proposals over a shared broadcast channel."
- The paper's abstract runs every problem under the four protocols "while holding the solver fixed within each setting", so the model that solves is the same in all four. Which model fills the other roles is not stated: `registry/models.csv` gives the role `actor_and_evaluator` to `openai/gpt-oss-120b` alone and `actor` to `google/gemma-4-31B-it`, so in the five Gemma settings the evaluator may be a second model
- Not released, as the card says: problem text, gold answers, raw generations (so no message between agents), and per-problem cost for nine of the ten settings

### Is a protocol a hand-off in the DESIGN 13 sense

- No. `DESIGN.md` 13 decides, for a parent that already holds a context of C tokens, whether to do one piece of work itself or to write a brief of B tokens to a delegate the router picks and read back R tokens. Here the work is the whole problem, no parent holds a context before it, and the model doing the work never changes
- Single is one agent revising its own answer, and Broadcast several agents on one problem. PER comes closest: a planner's decomposition goes to an executor, whose solution a reviewer checks, so a brief and a result pass inside one protocol run. But neither the plan, the solution nor the review is released as text or as a token count, and the abstract holds the solver fixed within each setting, so no brief can be measured and no delegate cheaper than the solver is tried
- So each row pairs the same model's direct answer with three paths that spend more calls on the same problem: a paired outcome of escalation, not of delegation

### Where the direct answer and each protocol differ

Per setting, the problems each protocol solves, and for each protocol the problems Baseline solves and it fails (lost) and the problems it solves and Baseline fails (gained), from the command below:

| benchmark condition | solver | n | Baseline | Single | PER | Broadcast | Single lost, gained | PER lost, gained | Broadcast lost, gained |
|---|---|---|---|---|---|---|---|---|---|
| JEEBench text only | gemma-4-31B-it | 515 | 363 | 419 | 494 | 506 | 1, 57 | 1, 132 | 2, 145 |
| JEEBench text only | gpt-oss-120b | 515 | 214 | 285 | 471 | 489 | 7, 78 | 1, 258 | 2, 277 |
| LAB-Bench strict in-prompt evidence | gemma-4-31B-it | 741 | 329 | 431 | 514 | 662 | 16, 118 | 5, 190 | 1, 334 |
| LAB-Bench strict in-prompt evidence | gpt-oss-120b | 741 | 141 | 224 | 353 | 550 | 24, 107 | 15, 227 | 3, 412 |
| LAB-Bench text, no tools | gemma-4-31B-it | 1,542 | 647 | 1,153 | 1,311 | 1,404 | 19, 525 | 10, 674 | 11, 768 |
| LAB-Bench text, no tools | gpt-oss-120b | 1,542 | 471 | 858 | 914 | 1,253 | 33, 420 | 28, 471 | 13, 795 |
| OmniMath competition math | gemma-4-31B-it | 4,181 | 2,901 | 3,593 | 3,790 | 3,888 | 19, 711 | 26, 915 | 9, 996 |
| OmniMath competition math | gpt-oss-120b | 4,181 | 2,376 | 3,294 | 3,561 | 3,730 | 40, 958 | 26, 1,211 | 11, 1,365 |
| SciBench text only | gemma-4-31B-it | 565 | 397 | 448 | 516 | 501 | 2, 53 | 0, 119 | 0, 104 |
| SciBench text only | gpt-oss-120b | 565 | 351 | 408 | 494 | 507 | 10, 67 | 0, 143 | 0, 156 |
| all | | 15,088 | 8,190 | 11,113 | 12,418 | 13,490 | 171, 3,094 | 112, 4,340 | 52, 5,352 |

### Tokens and cost

- Only the `costs_omnimath` config (`data/costs/omnimath_per_protocol_costs.csv`) has per-item numbers, and for one setting, OmniMath with `openai/gpt-oss-120b`: 4,155 of its 4,181 problems (the card says 26 were dropped as 13 duplicate-text pairs), each with every protocol's total tokens and model calls, and all 4,155 join `matched_labels` on `problem_id`. The totals are summed over every call of the protocol, with no split into input and output tokens, and the file holds no price or cost, so no list price can be applied to them
- In that setting, per item: Baseline takes a mean of 18,432.0 total tokens (median 17,236, 1,112 to 52,656) in a mean of 9.67 model calls (median 9, 1 to 42; 152 items in one call), so the recorded direct path is itself several calls; Single a mean of 48,309.2 (median 40,399) in 18.04 calls (median 17, 2 to 66); PER a mean of 402,241.5 (median 337,815) in 99.91 calls (median 64, 6 to 31,662); Broadcast a mean of 619,645.2 (median 412,918) in 135.14 calls (median 106, 8 to 806). PER takes more tokens than Baseline on all 4,155 items, Broadcast on 4,154 and Single on 3,710
- The other nine settings carry tokens only in aggregate tables: `avg_tokens_k` in `data/aggregate/main_routing_heldout.csv` and `avg_tokens` in `data/router/six_setting_text_metadata_verification.csv`

The command, Python's standard library on the two files above, with that download folder as its one argument:

```python
import csv, os, statistics as st, sys
D = sys.argv[1]
rows = list(csv.DictReader(open(os.path.join(D, "data/matched_labels.csv"))))
P = ["single", "per", "broadcast"]
print(len(rows), "rows,", len({r["setting_id"] for r in rows}), "settings,", len({r["problem_id"] for r in rows}), "problems")
for s in sorted({r["setting_id"] for r in rows}) + ["all"]:
    g = [r for r in rows if s in ("all", r["setting_id"])]
    ok = [sum(int(r[k + "_correct"]) for r in g) for k in ["baseline"] + P]
    diff = [(sum(r["baseline_correct"] == "1" and r[k + "_correct"] == "0" for r in g),
             sum(r["baseline_correct"] == "0" and r[k + "_correct"] == "1" for r in g)) for k in P]
    print(s, len(g), *ok, "|", *diff)
c = list(csv.DictReader(open(os.path.join(D, "data/costs/omnimath_per_protocol_costs.csv"))))
print(len(c), "cost rows,", {r["setting_id"] for r in c})
for k in ["baseline"] + P:
    t = [int(r[k + "_total_tokens"]) for r in c]; m = [int(r[k + "_model_calls"]) for r in c]
    print(k, "tokens mean %.1f median %s min %d max %d" % (st.mean(t), st.median(t), min(t), max(t)),
          "| calls mean %.2f median %s min %d max %d" % (st.mean(m), st.median(m), min(m), max(m)),
          "| one-call items", sum(x == 1 for x in m))
lab = {r["problem_id"] for r in rows if r["setting_id"] == "omnimath2__competition_math_4181__gpt_oss_120b"}
print("cost rows joined to labels:", sum(r["problem_id"] in lab for r in c))
for k in P:
    print(k, "items with more tokens than baseline:", sum(int(r[k + "_total_tokens"]) > int(r["baseline_total_tokens"]) for r in c))
```

### Recommendation (2026-11-12)

- No converter. The `DESIGN.md` 13.9 harness picks a delegate from a pool of models by its answers and prices both paths at list price; this release has two open-weight solvers, one per setting, neither priced in the registry, no parent context, brief or result, and per-item tokens, with no input and output split, for one setting only. A per-item comparison of the two paths would compare a direct answer with more calls of the same model on the whole problem, a choice `Router.decide_delegation` does not make
- What it shows beside TRAIL: spending more calls of the same model on a problem solves many problems the direct answer fails (3,094 to 5,352 of the 15,088 rows, by protocol) and loses few (52 to 171), and on the one setting with per-item tokens it takes a median of 64 (PER) and 106 (Broadcast) model calls per problem, counted over the whole protocol, against 9 for the direct answer. That is the value of escalation, which the committed delegation evidence does not model, not a measured hand-off
- The Summary's finding stands: no dataset found so far runs the same work inline and through a sub-agent with a brief, so the delegation evidence keeps its stated grid and the lossless-brief caveat

## A fresh search for paired inline and delegated runs (2026-11-14)

Question: has a public release since the searches above run one piece of work both inline and through a sub-agent, or by a single agent and a multi-agent system on the same items, with a success label for each path and token counts or costs for each path? README Limitations says the `cost_effective` decision equals always delegating on 441 of the 472 (bar, point, parent) rows of the delegation results files, so a gain from choosing per task needs work whose cheaper path differs from item to item, and only paired runs can show where it does.

### Sources searched (all read on 2026-11-14)

- Hugging Face dataset search, newest first: `https://huggingface.co/api/datasets?search=<term>&sort=lastModified&direction=-1&limit=60` for `multi-agent` (60 results), `single-agent` (14), `subagent` (32), `sub-agent` (32), `delegation` (17), `orchestrator` (43) and `agent-traces` (60). Each dataset whose name or card fits the question was read through `https://huggingface.co/api/datasets/<id>` and its card
- arXiv, newest first: `https://export.arxiv.org/api/query?search_query=<query>&sortBy=submittedDate&sortOrder=descending&max_results=60` for `abs:subagent`, `abs:"sub-agent" AND abs:delegat*` (no result), `abs:"single-agent" AND abs:"multi-agent" AND abs:cost` and `abs:"multi-agent" AND abs:"single agent" AND abs:tokens`: 58 distinct papers published from 2026-10-01. For the three whose abstract compares paths on the same items and gives their token ratio, the full text at `https://arxiv.org/html/<id>v1` was searched for GitHub, Hugging Face, Zenodo and OSF links; a fourth names its repository in its arXiv comment
- GitHub repository search, `https://api.github.com/search/repositories?q=<query>&sort=updated` (through `gh search repos`), six queries with no repository found: `multi-agent dual-control tau2`, `single-agent multi-agent trajectories ledgers`, `subagent inline delegation benchmark`, `agent architecture SOP cost success`, `single agent vs multi-agent financial review memos` and `subagent traces dataset`; then the GitHub API for the two repositories the papers link
- Revisions are those the Hugging Face or GitHub API returned on 2026-11-14. Files were downloaded outside the repo and read with the standard-library `json` and `csv` modules; nothing from them is committed

### Candidates

| Release | Revision | Licence | Items and models | Same items on both paths | Success per path | Size per path |
|---|---|---|---|---|---|---|
| Attention Tax, Handoff Tax ledger runs | d891b4e | data CC BY 4.0, code MIT | 300 (depth, item) pairs, one context against a serial chain of fresh contexts, and a 100-item hand-off probe; one model, `openai/gpt-oss-20b` | yes | yes, `final_ok` per item | yes, prompt, completion and reasoning tokens per call |
| TokenSave sub-agent runs | 33c600a, 0e36e9e | CC-BY-4.0 | 12 questions, 3 runs per path; `anthropic/claude-opus-5.5`, `anthropic/claude-haiku-5.5` | yes | yes, `recall` per run | cost and output tokens per run, no input tokens |
| Dual-control tau2-bench runs | 41c2f6c | data CC BY 4.0, code MIT | 7,950 conversations of six models, by its README | yes, by its README | yes, by its README | yes, by its README; the data is not downloadable yet |
| MultiAgent-Entropy raw data | cc0de80 | MIT | 44,781 rows by its card; Qwen3, Llama-3.1 and Llama-3.2 open models | yes | yes | the base model's answer tokens and all agents' tokens; not read whole |

### 1. The Attention Tax, Handoff Tax ledger runs (closest: the same work in one context and as a serial chain of fresh contexts, one model)

- URL: https://github.com/akshitanchan/attention-handoff-tax, the code and data of https://arxiv.org/abs/2610.06069 (v1 submitted 2026-10-05; its arXiv comment names the repository)
- Revision: d891b4eb92abf039431be850646830b486f9e5af (committed 2026-10-04), the default branch's HEAD by the GitHub API
- Licence: the LICENSE file gives MIT for the code and CC BY 4.0 for `data/`, `config/` and `results/`; the API's licence field reads `NOASSERTION`, since the file holds both
- Files read: `data/ledger/single.jsonl` (4,187,684 bytes), `data/ledger/decomposed.jsonl` (6,227,860) and `data/ledger/handoff.jsonl` (1,005,220), each with the sha256 the repository's `SHA256SUMS` lists, and the three `config/ledger/*.json` run settings
- The task: an item is a list of L ledger transactions with one model call per transaction; each call's record holds its output, the balance and the flags `fmt_ok`, `inc_ok` and `abs_ok`, and each item `final_ok` and `all_inc_ok` (the paper's abstract scores step-level and final-balance accuracy). The run settings give 100 items per depth, depths 20, 50 and 100, `m` 5, `s` 300, temperature 0.7 and `openai/gpt-oss-20b` at low reasoning effort in every call
- The two paths: `single` makes each step's call with the whole history so far in its prompt; `decomposed` runs each chunk of five steps in a fresh conversation that starts from a note the previous chunk's conversation wrote (`notes`, each a call of its own with its `text` and its `note_tokens`; `code/ledger_experiment.py` at that revision: "the fresh agent starts from the balance stated in the handoff note"). The 300 (depth, item) keys of the two files are the same
- So the hand-off is serial: a successor takes over the work from a note, and no parent resumes to read a result back. It is a surrogate for the `DESIGN.md` 13 hand-off, a parent writing a brief to a delegate and reading its result, not that hand-off itself
- The probe, `handoff.jsonl`: 100 items, 12 steps of history each, then 5 more steps four ways: in the same conversation (`history`), or in a fresh conversation started from a note of budget 100, 300 or 900 tokens that the first conversation wrote. That is close to the matched control [the smallest dataset](#what-the-smallest-dataset-that-could-test-the-lossless-brief-would-record) asks for, the same continued work once with the full context and once with a brief in its place, with one model as writer and reader, but for a successor rather than a delegate whose result a parent reads
- Counts, from this command in the repository's root folder at that revision:

```python
import json, statistics as st
read = lambda p: [json.loads(l) for l in open(p) if l.strip()]
S = {(r["L"], r["item"]): r for r in read("data/ledger/single.jsonl")}
D = {(r["L"], r["item"]): r for r in read("data/ledger/decomposed.jsonl")}
calls = lambda r: r["steps"] + r.get("notes", [])
tot = lambda r, k: sum(c[k] for c in calls(r))
for L in (20, 50, 100):
    ks = [k for k in S if k[0] == L]
    s, d = [S[k] for k in ks], [D[k] for k in ks]
    print(L, len(ks), "ok", sum(r["final_ok"] for r in s), sum(r["final_ok"] for r in d),
          "lost", sum(S[k]["final_ok"] > D[k]["final_ok"] for k in ks),
          "gained", sum(S[k]["final_ok"] < D[k]["final_ok"] for k in ks),
          "prompt", st.median(tot(r, "prompt_tokens") for r in s), st.median(tot(r, "prompt_tokens") for r in d),
          "completion", st.median(tot(r, "completion_tokens") for r in s), st.median(tot(r, "completion_tokens") for r in d),
          "notes", st.median(len(r["notes"]) for r in d), st.median(n["note_tokens"] for r in d for n in r["notes"]))
H = read("data/ledger/handoff.jsonl")
ok = lambda y, f: all(t[f] for t in y["steps"])
for c in ("history", "note_100", "note_300", "note_900"):
    x = [r["conditions"][c] for r in H]
    print(c, len(x), "all inc_ok", sum(ok(y, "inc_ok") for y in x), "all abs_ok", sum(ok(y, "abs_ok") for y in x),
          "prompt", st.median(sum(t["prompt_tokens"] for t in y["steps"]) for y in x),
          "note", st.median(y["note_tokens"] for y in x) if c != "history" else "-")
    if c != "history":
        h = [r["conditions"]["history"] for r in H]
        print(" ", c, "abs_ok lost", sum(ok(a, "abs_ok") > ok(b, "abs_ok") for a, b in zip(h, x)),
              "gained", sum(ok(a, "abs_ok") < ok(b, "abs_ok") for a, b in zip(h, x)),
              "note balance kept", sum(r["conditions"][c]["note_balance"] == r["pre"][-1]["balance"] for r in H))
```

```text
20 100 ok 49 64 lost 18 gained 33 prompt 87471.0 38006.0 completion 762.5 1608.0 notes 3.0 163.0
50 100 ok 4 18 lost 3 gained 17 prompt 517315.0 101419.0 completion 2339.0 4729.0 notes 9.0 176.0
100 100 ok 0 10 lost 0 gained 10 prompt 2029808.0 206613.0 completion 10262.0 10057.0 notes 19.0 174.0
history 100 all inc_ok 73 all abs_ok 54 prompt 30827.0 note -
note_100 100 all inc_ok 79 all abs_ok 58 prompt 7840.5 note 137.0
  note_100 abs_ok lost 9 gained 13 note balance kept 100
note_300 100 all inc_ok 77 all abs_ok 59 prompt 8077.0 note 180.5
  note_300 abs_ok lost 8 gained 13 note balance kept 99
note_900 100 all inc_ok 80 all abs_ok 60 prompt 8412.5 note 249.5
  note_900 abs_ok lost 5 gained 11 note balance kept 100
```

- Reading it: the hand-off path solves more items at every depth (64 against 49 at depth 20, 18 against 4 at 50, 10 against 0 at 100) and loses 18, 3 and 0 of the items the single path solves. Its median prompt tokens per item are 38,006 against 87,471, 101,419 against 517,315 and 206,613 against 2,029,808. Its median completion tokens are higher at depths 20 and 50 (1,608 against 762.5 and 4,729 against 2,339), the notes' own calls, and about level at 100 (10,057 against 10,262). The median note is 163 to 176 tokens
- In the probe aggregate continuation success is not lower from a note: from a note of budget 100, 300 or 900 tokens, 79, 77 and 80 of the 100 items keep every continued step `inc_ok` and 58, 59 and 60 every step `abs_ok`, against 73 and 54 with the history, at a median of 7,840.5 to 8,412.5 prompt tokens over the five steps against 30,827. Per item it is not lossless: the three note arms lose 9, 8 and 5 of the 54 items the history keeps all `abs_ok` and gain 13, 13 and 11, and the balance a note states equals the twelfth history step's balance on 100, 99 and 100 of the items. So these runs show no aggregate loss from a short note, not a zero loss; the repository's `code/analyse_ledger.py` measures a note's balance preservation apart from the context load
- Limits: a synthetic task and one open model in every role, so the delegate is never cheaper per token than the parent and no delegate is chosen from a pool; no price is recorded, and the model has no row in `model_routing/data/models.json`

### 2. TokenSave sub-agent runs (the same questions inline and delegated, 12 questions)

- URLs: https://huggingface.co/datasets/JOHNISKING/claude-subagent-effort at 33c600a195a0eca3aae95c831af09a2c09591c19 (last modified 2026-11-06) and https://huggingface.co/datasets/JOHNISKING/claude-subagent-model-by-version at 0e36e9e6738f7bcc912d79b55c337ad9cdb87620 (2026-11-08), both by the Hugging Face API; not gated
- Licence: CC-BY-4.0 (each card and its API tag)
- Files read: `claude-subagent-effort.csv` (43,177 bytes, sha256 5d44619d07a3f95164bbb392b667e3c08303e8318532a4ac47fd9f041c340fe5) and `claude-subagent-model-by-version.csv` (28,730 bytes, sha256 b5432409b3db03ac34e99078a8c840f4378ffd9a045cbd95db473d93848f6958)
- What a row records: one headless run of a coding-agent CLI, read and search tools only, on one of 12 "find every place" code-search questions in 6 open-source repositories (card), with `recall` (the share of the question's key items its answer names, 151 key items over the 12 questions, scored by a program on file and function or class), `api_cost_usd`, `output_tokens`, `subagent_calls` and `subagent_models`. No input token count; the second file splits the cost by model
- The paths: in the first file, condition `C0` is the question alone and `C1` to `C3` add an instruction to search with sub-agents at three effort settings, with `anthropic/claude-opus-5.5` or `anthropic/claude-haiku-5.5` as the parent (`claude-opus-5-5` and `claude-haiku-5-5` in the files, which the command maps to those IDs) and each sub-agent on the parent's own model, 3 runs per question; in the second, parts `B` (the default setting) and `D` (the setting that moves the sub-agent to Haiku 5.5) run the same 12 questions 3 times with an Opus 5.5 parent
- Counts, from this command in the folder holding the two files:

```python
import csv, statistics as st
e = list(csv.DictReader(open("claude-subagent-effort.csv")))
v = list(csv.DictReader(open("claude-subagent-model-by-version.csv")))
ID = {"claude-opus-5-5": "anthropic/claude-opus-5.5", "claude-haiku-5-5": "anthropic/claude-haiku-5.5"}
cost = lambda x: round(st.mean(float(r["api_cost_usd"]) for r in x), 6)
for m in ("claude-opus-5-5", "claude-haiku-5-5"):
    inline = {(r["question"], r["rep"]): r for r in e if r["model"] == m and r["condition"] == "C0"}
    for c in ("C0", "C1", "C2", "C3"):
        x = [r for r in e if r["model"] == m and r["condition"] == c]
        cheaper = sum(float(r["api_cost_usd"]) < float(inline[r["question"], r["rep"]]["api_cost_usd"]) for r in x)
        print(ID[m], c, len(x), "sub-agent runs", sum(int(r["subagent_calls"]) > 0 for r in x),
              "recall 1", sum(float(r["recall"]) == 1 for r in x), "cost", cost(x), "cheaper than inline", cheaper)
for p, s in (("B", ""), ("D", "CLAUDE_CODE_SUBAGENT_MODEL=haiku; CLAUDE_CODE_SUBAGENT_MODEL_FORCE=1")):
    x = [r for r in v if r["part"] == p and r["setting"] == s]
    print(p, len(x), "questions", len({r["question"] for r in x}), "sub-agent", sorted({ID[r["subagent_models"]] for r in x}),
          "recall 1", sum(float(r["recall"]) == 1 for r in x), "cost", cost(x))
```

```text
anthropic/claude-opus-5.5 C0 36 sub-agent runs 0 recall 1 35 cost 0.158908 cheaper than inline 0
anthropic/claude-opus-5.5 C1 36 sub-agent runs 36 recall 1 34 cost 0.386112 cheaper than inline 0
anthropic/claude-opus-5.5 C2 36 sub-agent runs 36 recall 1 33 cost 0.509315 cheaper than inline 0
anthropic/claude-opus-5.5 C3 36 sub-agent runs 36 recall 1 36 cost 0.482508 cheaper than inline 0
anthropic/claude-haiku-5.5 C0 36 sub-agent runs 0 recall 1 31 cost 0.005603 cheaper than inline 0
anthropic/claude-haiku-5.5 C1 36 sub-agent runs 36 recall 1 31 cost 0.009771 cheaper than inline 1
anthropic/claude-haiku-5.5 C2 36 sub-agent runs 36 recall 1 32 cost 0.010505 cheaper than inline 1
anthropic/claude-haiku-5.5 C3 36 sub-agent runs 36 recall 1 33 cost 0.012075 cheaper than inline 0
B 36 questions 12 sub-agent ['anthropic/claude-opus-5.5'] recall 1 36 cost 0.379338
D 36 questions 12 sub-agent ['anthropic/claude-haiku-5.5'] recall 1 36 cost 0.153385
```

- Reading it: with an Opus 5.5 parent, 35 of the 36 inline runs find every key item at a mean of 0.158908 USD; with sub-agents on Opus 5.5, 34, 33 and 36 do at 0.386112 to 0.509315, and no delegated run costs less than its inline pair (the same question and run number); with a Haiku 5.5 sub-agent under the same parent (part `D`), 36 of 36 do at 0.153385, about the inline cost. With a Haiku 5.5 parent, 31 of 36 inline runs find every item at 0.005603, and 31 to 33 delegated runs at 0.009771 to 0.012075, 2 of the 108 delegated runs costing less than their inline pair
- Limits: 12 questions, so each half of the evaluator's seeded split holds about six questions and 18 runs, below the default `min_samples` of 30; inline success is near its ceiling; no input tokens, so C, B and R cannot be read; each run starts from a fresh session, so the runs measure only work with a small parent context; and the Haiku sub-agent arm is a separate set of runs, with the same questions, repositories and scorer by its card

### 3. Dual-control tau2-bench runs (all three by its README; not downloadable yet)

- URL: https://github.com/ethanyyang/agent-scaling-dual-control at 41c2f6ca83ea988338ac17fb414b343293a2f1b7 (committed 2026-10-18), the repository the full text of https://arxiv.org/abs/2610.27655 (v1 submitted 2026-10-20) links
- Licence: MIT for the code (the API's licence field) and CC BY 4.0 for the data (`LICENSE-DATA` and the README's badges)
- What its README and `data/README.md` say it holds: on tau2-bench's airline, retail and telecom domains, the stock single-agent system against a centralized multi-agent system built from the same model, for six models from three families, 7,950 simulated conversations, each run a tau2-bench `results.json` with per-call token usage. That would be the same tasks on both paths, the tau2-bench reward per path and the size of every call, on the benchmark of `DESIGN.md` 12.14
- Not readable on 2026-11-14: `data/download.sh` sets `ZENODO_RECORD` to `TODO_ZENODO_RECORD_ID` and stops there, the README's data badge says the DOI is pending, and `data/simulations` holds one empty file and no run. `data/INVENTORY.csv` lists 95 runs in 12 groups, 13 of them in `grid-sas` and 15 in `grid-mas`

### Read and set aside

- AgenticFinLab/multiagent-entropy-rawdata (https://huggingface.co/datasets/AgenticFinLab/multiagent-entropy-rawdata at cc0de80449f720b745af3e1e2ff7308999e9902f, last modified 2026-06-09, MIT; the raw data of https://arxiv.org/abs/2602.04234): its card gives `merged_datasets/master.csv` (140,640,059 bytes by the API) 44,781 rows of 254 columns, and its first 6,000 bytes, read with an HTTP range request, name per (dataset, model, sample, architecture) `is_finally_correct`, `base_model_is_finally_correct`, `base_model_answer_token_count` and `sample_all_agents_token_count`. Its card lists the architectures `single` and six multi-agent ones, each row naming one `model_name`, and its supported-model list names Qwen3 0.6B to 14B, Llama-3.2-3B-Instruct, Llama-3.1-8B-Instruct and RL-trained models, none in the registry. So the same items, a success per path and a token count per path, but, as in AgentsSci, one model spending more calls on the whole problem, and no column name in the bytes read is a brief or a result. Not read whole
- the-illusion-of-multi-agent-advantages/smfr-dataset (https://huggingface.co/datasets/the-illusion-of-multi-agent-advantages/smfr-dataset at a2ee35176d4889791d45147934b198a2559f9406, 2026-11-06, CC-BY-4.0): 604 synthetic stock-trading reasoning problems with answers and a worked chain of thought (card), no model outputs, so no model and no path
- suad240176/masrs-multi-agent-evaluation-results (https://huggingface.co/datasets/suad240176/masrs-multi-agent-evaluation-results at 544166425cc9e91a9ab770920db3230397b37e6a, 2026-10-19, MIT): a thesis package, 60 clinical scenarios answered by a single retrieval baseline and by a multi-agent system, scored by ROUGE, F1 and Likert ratings with total tokens per system (card), its models not named in the card: the same items and a size per path, but no program-checked success label
- rmems/delegation-planning-trajectories (https://huggingface.co/datasets/rmems/delegation-planning-trajectories at 9cca2794ad70df336492ba0a2dfd73fa300cbf4b, 2026-10-22, Apache-2.0): 7 records generated by a program, with no model, by its card; plans, sub-agent claims and planner checks, with no inline run and no token count (its card's schema)
- UdeM-Mila-Subagents/swesmith-multi-agent-trajectories (https://huggingface.co/datasets/UdeM-Mila-Subagents/swesmith-multi-agent-trajectories at c7a5bb923b8fc0bf5be532f584b1c8c59587665b, 2026-05-01): no card and no licence tag, one data file of 493,205,559 bytes, its item count and models not stated; not read, as HAL was not
- Papers since 2026-10-01 that compare paths on the same items but name no per-item release: https://arxiv.org/abs/2611.12953 (four architectures of one model on 13 enterprise procedures, the coordinated arms at 1.4 to 4.7 times the single agent's tokens by its abstract; its full text links only a multi-agent framework) and https://arxiv.org/abs/2610.27488 (one agent against a team of three of the same model on 300 synthetic memos with four models, the team at 2.2 to 2.4 times the tokens; its full text links no data)

### Recommendation (2026-11-14)

- A converter for the ledger runs (row E23): of the two releases found that run the same work two ways on the same items, the only one with enough items for the evaluator's seeded split (100 per depth), per-call token counts on both paths and the note recorded, and with a probe that compares a note against the full context, where the committed delegation evidence assumes a brief loses nothing. Its hand-off is serial, so the converter would report its paths as a surrogate beside the 13.9 grid, measured for a successor rather than a delegate whose result a parent reads, and would state the probe's paired losses and gains without calling the note lossless. Its data is CC BY 4.0, the licence of AutoBench and AgentsSci, which asks for attribution only, so no licence question is open. It would set measured paths beside the 13.9 grid; it cannot test a cheaper delegate or the `cost_effective` choice of a delegate model, since one model fills every role, and its cost needs a list price for `openai/gpt-oss-20b`, which the registry lacks
- No converter for the TokenSave runs: 12 questions are too few for the evaluator's split. What they show is the other side of the decision: with a parent context that starts fresh, a sub-agent on the parent's own model cost less than its inline pair in 2 of the 216 pairs, while the runs finding every key item went from 35 inline to 33 to 36 with an Opus 5.5 parent and from 31 to 31 to 33 with a Haiku 5.5 parent; a Haiku 5.5 sub-agent under an Opus 5.5 parent cost about what inline work did
- Read the dual-control runs once `data/download.sh` names a Zenodo record: they would pair a single-agent and a multi-agent system of six models on tau2-bench tasks with per-call usage
- The Summary's finding changes: two releases now run the same work two ways on the same items, the ledger runs in one context and as a serial chain of fresh contexts with one open model on a synthetic task, and the TokenSave runs inline and through sub-agents on 12 questions, so the delegation evidence keeps its stated grid and the lossless-brief caveat until a converter reports them
