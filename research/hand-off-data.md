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
