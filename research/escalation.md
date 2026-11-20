# Escalation: start on a cheap model, hand up on a signal (2026-11-20)

Question: how can a call start on a cheap model and hand the work up to a stronger one when a signal appears during the work, without weakening the library's guarantee that a route clears its task's bar on measured data, and which public data, with no API key, can test it?

Short answer: treat a cascade (a cheap model, a named signal the caller computes, and a strong model) as one routing candidate with calibration rows of its own. It clears a bar only when the Wilson lower bound of its own measured successes does, so it never inherits the strong model's pass. Its expected cost is the cheap model's cost plus the measured escalation share times the strong model's cost of re-reading the context so far, uncached, and answering. `DESIGN.md` 7 v1.532 specifies it for row ESC2. Of the converted public datasets, tau2-bench is the one that records both a signal a harness can count during the work (the agent calls made so far) and the tokens of each call, so row ESC3 runs there first with the signal "more than N agent calls". Measured by row ESC1b, the call count tells in telecom and, at 10 calls, in airline, not in retail, and many runs write to the domain's state before the hand-up, so ESC3 escalates only a run with no write call yet (`calls-over-N-no-write`, N of 10, 15 and 20), and tries the agent's own transfer to a human as a third signal. LiveCodeBench gives the failed-check signal, a failed public test case, success only, since it records no cost: row ESC1c matched the failing tests its runner recorded against the public cases of the pinned problem release, and the signal `public-test-failed` is never wrong when it fires but finds about three in five of the failures.

## Facts

- The idea comes from the cascade pattern in [prior-art.md](prior-art.md) (FrugalGPT, AutoMix, Trust or Escalate): try the cheap model first, escalate when a score says so
- What the library has today: the executor's fallback (`DESIGN.md` 7) moves to the next model of a route when the caller's `validate` check fails, and every model of that route clears the bar on its own (5.3); the below-bar option (5.3 v1.201) adds models under the bar that only the check vouches for
- What is new: the cheap model of a cascade need not clear the bar; the cascade as a whole must, measured as a whole
- The signal is the caller's: only the caller's harness sees its tests, tool calls or services, so the library names a signal and calls the caller's function on the cheap model's result
- The spec is `DESIGN.md` 7 v1.532; no code reads it until row ESC2
- `## Measured signals (row ESC1b)` holds the output of `research/escalation_signals.py` (`DESIGN.md` 7 v1.533) on the pinned tau2-bench files
- `## Public tests matched (row ESC1c)` holds the output of `research/escalation_public_tests.py` (`DESIGN.md` 7 v1.534) on one pinned LiveCodeBench problem release file
- No results file, package, README or workflow change in this note

## Why a cascade is one candidate

- A cascade's success on a task is `P(kept and the cheap answer passes) + P(escalated and the strong answer passes)`. The items that escalate are the ones the signal picks, often the hard ones, so the strong model's rate on them is not its rate on the task, and a cheap answer the signal keeps but that is wrong counts against the cascade and never shows in the strong model's rate
- So a cascade gets trials of its own: one item run through the whole cascade is one trial, a success when the final answer passes the task's check, whichever model gave it. Its Wilson lower bound, at the task's or slice's bar and `min_samples`, admits it exactly as a model's admits a model, and priors never admit it
- Cost: `cheap cost + p x strong cost`, with `p` the share of the cascade's own calibration rows that escalated. The cheap model's tokens count on every row, whether it escalated or not and whether its answer was right. The hand-up is priced as the strong model reading the context so far, the input and the cheap model's output, as uncached input: a prompt cache belongs to one model, so a hand-up that carries the cheap model's work reads it again at the strong model's full input price. The executor of `DESIGN.md` 7 v1.532 starts the strong model fresh, which reads only the input, so for it the price is an upper bound, the conservative assumption
- Each cascade with its own signal threshold is its own candidate (`calls-over-10` and `calls-over-20` are two), so choosing a threshold is the same choice among measured candidates the router already makes among models

## Signals the public data can test

| Dataset (`DESIGN.md`) | What a row records | Signal a replay can compute | Cost of the cheap part | Use |
|---|---|---|---|---|
| tau2-bench (12.14) | per (task, agent, trial) a conversation: each agent message with its `tool_calls` and, on most, a `usage` of prompt and completion tokens (12.14 sums those that are not null), and a program-checked reward; four 2025 agents in three domains | more than N agent calls, counted as the run goes, and whether a write call came first; the agent's own `transfer_to_human_agents` call, offered in all three domains, which some tasks' policies require, so it can end a correct run as well as a stuck one | each call priced from its own `usage` at list price | ESC3 first |
| Longtail-SWE (12.25) | per (task, model, run) token totals and a test-checked label; a run sums a median 38 model calls ([longtail-delegation.md](longtail-delegation.md)) and the release records no per-call tokens | more than N model calls | needs the stated split of [longtail-per-call.md](longtail-per-call.md), an assumption the release cannot check | second for the call-count signal |
| LiveCodeBench (12.16) | per (problem, model) a graded list of samples; in the smallest kept file, `O1-Mini-2024-09-12` (3,636,170 bytes, 880 problems), read on 2026-11-20, 236 of the 278 failed first samples hold in `metadata` the failing test's `inputs`, `expected` and `output` and an `error_code`, 35 an `error` in place of `output`, and 7 no test at all (only an error code and message), while each of the 602 passed ones holds only its `execution time`; whether the failing test is one of the problem's public test cases is not recorded | a failed public test, a check the caller can run: the recorded failing test matched against the public cases of the pinned problem release (row ESC1c) | none: the files record no cost (12.16, [livecodebench-cost.md](livecodebench-cost.md)), so `cost_blind` only | ESC3 second, success only, signal `public-test-failed` (row ESC1c) |
| LLMRouterBench (12.18) | per (item, model) a score and a cost | on `livecodebench` a caller holds the public test cases, but the records keep no test-level result ([check-fallback.md](check-fallback.md)) | recorded | no: only the record's own score, the upper bound check-fallback.md measures |
| RouterBench, AutoBench 2026, the response bank, the registry pair (12.6, 12.9, 12.20, 12.23) | one answer per (item, model) and no run-time trace | only a check on the answer, which their labels make with an answer key a caller lacks | recorded | no |
| TRAIL (13.11) | real hand-offs with per-call tokens | call counts | recorded | no: no success label |
| AgentsSci ([hand-off-data.md](hand-off-data.md), not converted) | the same solver answering directly and under three protocols that spend more calls | the protocol's extra calls | per-item tokens for one of ten settings | no: more effort on one model, not a hand-up to a stronger one |

- A second service touched: no converted dataset records which service a call touches, so no public replay tests it; a caller who sees it can still pass it as a signal
- The model saying it is stuck: the nearest public trace is tau2-bench's `transfer_to_human_agents`, above; measured below, it ends many correct runs, so it is no stuck signal

## What row ESC3 runs

- Dataset: tau2-bench, the 12 pinned run files of 12.14, trial 0, one task per domain as in 12.15
- Cascades: each pair of the four agents with the cheap one at the lower list price, and the signal `calls-over-N-no-write`, with the signal `calls-over-N` beside it, for N = 10, 15 and 20, and the signal `transfer` (`## Measured signals (row ESC1b)`)
- A row of the replay: escalated when the cheap run makes more than N agent calls (for `calls-over-N-no-write`, with no write call among its first N; for `transfer`, when it calls `transfer_to_human_agents`, its calls up to that one standing for the first N); correct is the strong run's reward when escalated and the cheap run's otherwise; cost is the list-price cost of the cheap run's first N calls (all of them when it does not escalate) plus, when escalated, the prompt and completion tokens of its Nth call as the strong model's uncached input and the strong run's list-price cost
- Compared at the same bars, held-out: the best single model, the routed row of 12.15 and the best cascade, each with its success and cost, and the escalation share. The sliced route exists only where slices are committed (12.27, 12.28), so it is compared on LiveCodeBench, which ESC1c keeps as the second dataset, success only, with the signal `public-test-failed`
- Limits the README part states: a signal measured on a benchmark may not exist in your product. The strong run in the data starts fresh, with its own simulated user, so the replay assumes a hand-up that restarts the conversation; a write the cheap agent made before the hand-up would stay in a real system's state, which the replay cannot see, so `calls-over-N-no-write` never hands such a run up and `calls-over-N` and `transfer` are labelled for it. In telecom the user's own device actions (`src/tau2/domains/telecom/user_tools.py` at the same commit), which the agent asks for, change state too, and no signal here counts them

## What row ESC2 implements

- `DESIGN.md` 7 v1.532: a `Cascade(cheap, strong, signal)` with an `id` of `cheap>strong@signal`; `Task.cascades`; a cascade's own trials and escalations in `Stats`; candidates after the registry models when `select` is asked for them, each ruled by rules 1 to 5 on both models and by its own Wilson bound; the routing cost above; the executor running the cheap model, the caller's signal, then the strong model; and two record keys, `cascade` and `escalated`

## Measured signals (row ESC1b)

`research/escalation_signals.py` reads the 12 pinned run files of 12.14 at trial 0 and, at the same commit, each domain's tool definitions; its output on the cached files, 2026-11-20:

```text
$ python research/escalation_signals.py
tau2-bench at 033bf082f48e4a3c6a1256208e93cf2ce9c3bb6f, 12 run files, trial 0
agent messages: 18,472, with a usage (an agent call): 17,360 (0.940); without one: 1,112, of them the run's first message: 1,112

domain   agent                                 runs  pass  calls_median  calls_max  usage_share  transfer  transfer_pass  write_runs
-------  ------------------------------------  ----  ----  ------------  ---------  -----------  --------  -------------  ----------
airline  anthropic/claude-3-7-sonnet-20250219    50    27          13.5         51        0.934         8              8          37
airline  openai/gpt-4.1-2025-04-14               50    29            10         23        0.909         9              8          36
airline  openai/gpt-4.1-mini-2025-04-14          50    25            10         25        0.914        10             10          35
airline  openai/o4-mini-2025-04-16               50    28            11         29        0.915        21             13          28
retail   anthropic/claude-3-7-sonnet-20250219   114    91            13         24        0.932         7              5         104
retail   openai/gpt-4.1-2025-04-14              114    84            11         21        0.918         5              3         104
retail   openai/gpt-4.1-mini-2025-04-14         114    78            12         21        0.924         5              4         101
retail   openai/o4-mini-2025-04-16              114    79            13         29        0.929         9              7         101
telecom  anthropic/claude-3-7-sonnet-20250219   114    50            17        100        0.948        73             16          73
telecom  openai/gpt-4.1-2025-04-14              114    42            16         99        0.946        63             14          60
telecom  openai/gpt-4.1-mini-2025-04-14         114    49            23        100        0.965        67             14          54
telecom  openai/o4-mini-2025-04-16              114    49            19         34        0.948        84             20          88

pooled over each domain's agents (no_transfer: runs that never call transfer_to_human_agents)
domain   runs  pass  pass_rate  transfer  transfer_pass  transfer_rate  no_transfer  no_transfer_rate  write_runs
-------  ----  ----  ---------  --------  -------------  -------------  -----------  ----------------  ----------
airline   200   109      0.545        48             39          0.812          152             0.461         136
retail    456   332      0.728        26             19          0.731          430             0.728         410
telecom   456   190      0.417       287             64          0.223          169             0.746         275

runs over N agent calls, each cell over/pass/wrote (wrote: a write call among its first N calls)
domain   agent                                        N=5        N=10        N=15        N=20        N=30
-------  ------------------------------------  ----------  ----------  ----------  ----------  ----------
airline  anthropic/claude-3-7-sonnet-20250219     48/25/2     35/17/9      15/7/9       4/3/1       3/2/3
airline  openai/gpt-4.1-2025-04-14                46/27/4     21/9/12       3/1/2       1/1/1       0/0/0
airline  openai/gpt-4.1-mini-2025-04-14           47/23/3     23/10/9       6/2/5       2/0/2       0/0/0
airline  openai/o4-mini-2025-04-16                43/24/3    27/11/10       4/3/1       1/1/0       0/0/0
retail   anthropic/claude-3-7-sonnet-20250219    114/91/0    93/75/32    36/30/31       5/4/5       0/0/0
retail   openai/gpt-4.1-2025-04-14               113/83/0    66/45/45       9/7/9       1/1/1       0/0/0
retail   openai/gpt-4.1-mini-2025-04-14          114/78/1    81/52/33    16/12/14       1/1/1       0/0/0
retail   openai/o4-mini-2025-04-16               114/79/2    88/61/29    30/21/23       5/4/5       0/0/0
telecom  anthropic/claude-3-7-sonnet-20250219    114/50/1   111/48/59    75/25/47     28/9/20       3/0/2
telecom  openai/gpt-4.1-2025-04-14               114/42/0   107/38/34    68/17/31     22/4/16       1/0/0
telecom  openai/gpt-4.1-mini-2025-04-14          114/49/7   106/43/34    95/35/34    72/18/21     27/4/10
telecom  openai/o4-mini-2025-04-16              114/49/18   101/37/69    79/23/63    36/13/30       1/0/1

pooled over each domain's agents (no_write: runs over N with no write call among their first N calls)
domain    N  over  pass_over  no_write  pass_no_write  at_most  pass_at_most
-------  --  ----  ---------  --------  -------------  -------  ------------
airline   5   184      0.538       172          0.552       16         0.625
airline  10   106      0.443        66          0.576       94         0.660
airline  15    28      0.464        11          0.727      172         0.558
airline  20     8      0.625         4          1.000      192         0.542
airline  30     3      0.667         0            n/a      197         0.543
retail    5   455      0.727       452          0.728        1         1.000
retail   10   328      0.710       189          0.730      128         0.773
retail   15    91      0.769        14          0.857      365         0.718
retail   20    12      0.833         0            n/a      444         0.725
retail   30     0        n/a         0            n/a      456         0.728
telecom   5   456      0.417       430          0.409        0           n/a
telecom  10   425      0.391       229          0.279       31         0.774
telecom  15   317      0.315       142          0.190      139         0.647
telecom  20   158      0.278        71          0.169      298         0.490
telecom  30    32      0.125        19          0.158      424         0.439

write tools (src/tau2/domains/<domain>/tools.py at 033bf082, @is_tool(ToolType.WRITE)):
  airline (6): book_reservation, cancel_reservation, send_certificate, update_reservation_baggages, update_reservation_flights, update_reservation_passengers
  retail (7): cancel_pending_order, exchange_delivered_order_items, modify_pending_order_address, modify_pending_order_items, modify_pending_order_payment, modify_user_address, return_delivered_order_items
  telecom (6): disable_roaming, enable_roaming, refuel_data, resume_line, send_payment_request, suspend_line
transfer_to_human_agents: airline GENERIC, retail GENERIC, telecom GENERIC
```

- The only agent messages without a `usage` are each run's first message, the agent's fixed greeting (1,112 of 18,472, one per run), and the script reads every other one's token counts through the converter's check, so a replay prices the cheap run's first N calls from their own tokens
- The call count tells in telecom and, at 10 calls, in airline, not in retail. Pooled over the four agents, telecom runs over 10 calls pass at 0.391 against 0.774 at most 10, and over 20 at 0.278 against 0.490; airline runs over 10 at 0.443 against 0.660; retail runs over 10 at 0.710 against 0.773, a small gap at these counts, and over 15 at 0.769 against 0.718, so there the count says little and a hand-up pays for runs that would have passed. Airline tells only at 10: over 15 its runs pass at 0.464 against 0.558, on 28 runs, and over 20 at 0.625 against 0.542, on 8. The four agents run the same tasks, so the pooled runs are not independent samples
- Many runs write before the hand-up. Of the runs over 10 calls, only 66 of 106 in airline, 189 of 328 in retail and 229 of 425 in telecom made no write call among their first 10; the others had changed the domain's state (a booking, an order, a line) by then. The data's strong run starts fresh on an untouched state, so a replay that hands those runs up assumes the cheap agent's writes undone, which no real system gets for free. In telecom the runs over N with no write yet pass less often than all runs over N (0.279 against 0.391 at 10, 0.169 against 0.278 at 20), so waiting for no write still picks the hard runs
- `transfer_to_human_agents` is a `GENERIC` tool in all three domains. In airline and retail a run that calls it is often a correct one: 39 of 48 such runs pass in airline (0.812, against the domain's 0.545) and 19 of 26 in retail (0.731 against 0.728). In telecom it separates runs sharply: the 287 of 456 that call it pass at 0.223 and the 169 that do not at 0.746, a wider gap than the call count's
- The grid: at N = 5 nearly every run is over (184 of 200 in airline, 455 and 456 of 456 in retail and telecom), so a cascade there is the strong model plus the cheap model's waste; at N = 30 only 3, 0 and 32 are over, so it almost never escalates
- Decision for row ESC3: the dataset stays tau2-bench, one task per domain, so retail's result shows a signal that says little there. The signal becomes `calls-over-N-no-write`: escalate when the cheap run passes N agent calls with no write call among the first N, and leave a run that wrote first on the cheap model, as a harness that sees its own tool calls can; `calls-over-N` runs beside it, labelled as a replay that assumes the cheap agent's writes undone. The grid is N = 10, 15 and 20; under the no-write rule only telecom escalates a usable share at 15 and 20 (142 and 71 runs, against 11 and 4 in airline and 14 and 0 in retail), so in ESC3 an empty cell is no result. ESC3 adds a third signal, `transfer`: escalate when the cheap run calls `transfer_to_human_agents`, labelled as `calls-over-N` is, since a run may write before it transfers; the counts above say it may help in telecom and cost passes in airline and retail

## Public tests matched (row ESC1c)

`research/escalation_public_tests.py` reads one release file of the problems, `test3.jsonl` of `livecodebench/code_generation_lite` at a pinned revision, the runner's `lcb_runner/benchmarks/code_generation.py` and `lcb_runner/evaluation/testing_util.py` at a pinned commit of LiveCodeBench/LiveCodeBench, and the 67 kept submission files of 12.16; its output on the cached files, 2026-11-20:

```text
$ python research/escalation_public_tests.py
problem release livecodebench/code_generation_lite at 0fe84c3912ea0c4d4a78037083943e8f0c4dd505, read: test3.jsonl
runner LiveCodeBench/LiveCodeBench at 28fef95ea8c9f7a547c8329f2cd3d32b92c1fa24: public cases before private ones (get_evaluation_sample), the failing case recorded by truncatefn at 300 characters
submissions at 6ca212e9c2039373f6e5069d37ffa9db66e23736: 67 kept files, 713 problems in every one (the 12.16 kept problems)
sample problems: 101, contest dates 2024-06-01 to 2024-08-10, public cases per problem 2 to 4 (median 3), among the 12.16 kept problems: 101
call-based (a func_name, cases recorded parsed): 48, standard input (recorded as text): 53

model                                    problems  failed  public  other  input_only  no_test  unread  public_share  public_of_tested
---------------------------------------  --------  ------  ------  -----  ----------  -------  ------  ------------  ----------------
agentica/deepcoder-14b-preview                101      20       0      0           0        0      20         0.000               n/a
anthropic/claude-3-haiku                      101      80      66     13           0        1       0         0.825             0.835
anthropic/claude-3.5-sonnet-20240620          101      61      44     16           0        1       0         0.721             0.733
anthropic/claude-3.5-sonnet-20241022          101      54      27     27           0        0       0         0.500             0.500
anthropic/claude-3.7-sonnet                   101      36      13     23           0        0       0         0.361             0.361
anthropic/claude-opus-4                       101      30      15     15           0        0       0         0.500             0.500
anthropic/claude-opus-4-thinking              101      23      10     13           0        0       0         0.435             0.435
anthropic/claude-sonnet-4                     101      31      15     16           0        0       0         0.484             0.484
anthropic/claude-sonnet-4-thinking            101      26       5     21           0        0       0         0.192             0.192
deepseek/deepseek-r1-0528                     101      13       0      0           0       13       0         0.000               n/a
deepseek/deepseek-r1-lite-preview             101      30      18      6           0        6       0         0.600             0.750
deepseek/deepseek-r1-preview                  101      20       6     14           0        0       0         0.300             0.300
deepseek/deepseek-v3                          101      40      26     11           0        3       0         0.650             0.703
deepseek/dscoder-1.3b-ins                     101      93      70      5           0       18       0         0.753             0.933
deepseek/dscoder-33b-ins                      101      75      62      9           0        4       0         0.827             0.873
deepseek/dscoder-6.7b-ins                     101      84      71     11           0        2       0         0.845             0.866
google/gemini-2.5-flash-04-17                 101      21       9     10           0        2       0         0.429             0.474
google/gemini-2.5-flash-05-20                 101      14       7      6           0        1       0         0.500             0.538
google/gemini-2.5-pro-03-25                   101      15       3      9           0        3       0         0.200             0.250
google/gemini-2.5-pro-05-06                   101      11       5      6           0        0       0         0.455             0.455
google/gemini-2.5-pro-06-05                   101      11       3      7           0        1       0         0.273             0.300
google/gemini-exp-1206                        101      52      24     22           0        6       0         0.462             0.522
google/gemini-flash-1.5-002                   101      60      34     24           0        2       0         0.567             0.586
google/gemini-flash-2.0-exp                   101      56      26     26           0        4       0         0.464             0.500
google/gemini-flash-2.0-thinking              101      46      17     26           0        3       0         0.370             0.395
google/gemini-flash-2.0-thinking-01-21        101      39       8     29           0        2       0         0.205             0.216
google/gemini-flash-2.0-thinking-12-19        101      39      13     24           0        2       0         0.333             0.351
google/gemini-pro-1.5-002                     101      61      37     23           0        1       0         0.607             0.617
lgai/exaone-4.0-32b                           101      16       3     12           0        1       0         0.188             0.200
meta-llama/llama3.3-70b-ins                   101      65      41     20           0        4       0         0.631             0.672
metastone/metastone-l1-7b                     101      40      29      1           0       10       0         0.725             0.967
mistralai/codestral-latest                    101      69      52     15           0        2       0         0.754             0.776
mistralai/mistral-large                       101      61      43     17           0        1       0         0.705             0.717
moonshotai/kimi-k1.6-ioi                      101      15       6      8           0        1       0         0.400             0.429
moonshotai/kimi-k1.6-ioi-high                 101      13       5      7           0        1       0         0.385             0.417
nvidia/llama-3_1-nemotron-nano-8b-v1          101      34      16      4           0       14       0         0.471             0.800
nvidia/llama-3_1-nemotron-ultra-253b-v1       101      17       8      9           0        0       0         0.471             0.471
nvidia/openreasoning-nemotron-32b             101      17       7     10           0        0       0         0.412             0.412
openai/gpt-4-0613                             101      71      61     10           0        0       0         0.859             0.859
openai/gpt-4-turbo-1106                       101      65      41     23           0        1       0         0.631             0.641
openai/gpt-4-turbo-2024-04-09                 101      58      38     18           0        2       0         0.655             0.679
openai/gpt-4o-2024-05-13                      101      56      34     21           0        1       0         0.607             0.618
openai/gpt-4o-2024-08-06                      101      59      40     19           0        0       0         0.678             0.678
openai/gpt-4o-mini-2024-07-18                 101      63      44     19           0        0       0         0.698             0.698
openai/o1-2024-12-17-high                     101      12       6      6           0        0       0         0.500             0.500
openai/o1-2024-12-17-low                      101      17       7      9           0        1       0         0.412             0.438
openai/o1-2024-12-17-med                      101      19      10      9           0        0       0         0.526             0.526
openai/o1-mini-2024-09-12                     101      32      17     14           0        1       0         0.531             0.548
openai/o1-preview-2024-09-12                  101      47      23     23           0        1       0         0.489             0.500
openai/o3-high                                101      12       4      4           0        4       0         0.333             0.500
openai/o3-mini-2025-01-31-high                101      16       5      7           0        4       0         0.312             0.417
openai/o3-mini-2025-01-31-low                 101      19       9      7           0        3       0         0.474             0.562
openai/o3-mini-2025-01-31-med                 101      17       7      5           0        5       0         0.412             0.583
openai/o4-mini-high                           101       9       6      3           0        0       0         0.667             0.667
openai/o4-mini-low                            101      19       9      8           0        2       0         0.474             0.529
openai/o4-mini-medium                         101      10       4      4           0        2       0         0.400             0.500
qwen/qwen2-ins-72b                            101      76      59     17           0        0       0         0.776             0.776
qwen/qwen2.5-coder-ins-32b                    101      61      44     11           0        6       0         0.721             0.800
qwen/qwen2.5-coder-ins-7b                     101      80      67     11           0        2       0         0.838             0.859
qwen/qwen2.5-ins-32b                          101      62      44     17           0        1       0         0.710             0.721
qwen/qwen2.5-ins-72b                          101      59      40     17           0        2       0         0.678             0.702
qwen/qwen2.5-ins-7b                           101      77      68      8           0        1       0         0.883             0.895
qwen/qwen3-235b-a22b                          101      15       0      0           0        0      15         0.000               n/a
qwen/qwq-32b-preview                          101      40      22      9           0        9       0         0.550             0.710
qwen/qwq-32b_temp                             101      23       3     13           0        7       0         0.130             0.188
qwen/qwq-max-preview                          101      15       0      0           0        0      15         0.000               n/a
xai/grok-3-mini-high                          101      15       3     11           0        1       0         0.200             0.214
all                                         6,767   2,612   1,559    838           0      165      50         0.597             0.650

public matches by the 0-based index of the matched case: 0: 1,207, 1: 248, 2: 99, 3: 5
```

- Which release: the problems every kept file has are the 713 that 12.16 keeps; the dataset card's `release_v4` is 713 problems, and the dataset's loader, `code_generation_lite.py` at the same revision, reads it from `ALLOWED_FILES["release_v4"]`, `test.jsonl` to `test4.jsonl`. Those four files are large (`DESIGN.md` 7 v1.534 pins their sizes), so the script reads the smallest, `test3.jsonl`, whose 101 problems are all among the 713: the counts are for that stated sample, 101 of the 713 problems in every kept file
- The runner's order: at the pinned commit `get_evaluation_sample` lists a problem's public cases before its private ones, and the grader returns at the first failing case and records its input and expected output through `truncatefn` at 300 characters: as raw text for a standard-input problem, and for a call-based one (its metadata names a `func_name`) as `str` of the JSON-parsed input lines and output, since `grade_call_based` parses a case before it runs it. The script checks those lines in the pinned files and compares each failing test with a public case in the same recorded form, through a copy of `truncatefn`; of the 101 problems, 48 are call-based and 53 standard input. It never decodes the private cases, which the release stores as a pickle
- The match: of the 2,612 failed first samples on the 101 problems, 1,559 (0.597) failed on a public case, their recorded input and expected output equal to one of the problem's public cases, 1,207 of them on its first; 838 hold a test that matches no public case, so by the runner's order they passed every public case and failed a private one. No failing test matched a public input with another expected output (`input_only` 0 in every file), so the recorded tests and the release's public cases agree. Over the failed samples that hold a test the public share is 0.650
- What the match leaves out: 165 samples hold no test, the entry the runner's `run_test` returns, an `error_code` and `error_message` with no `inputs`, when testing itself raises, among them all 13 of `deepseek/deepseek-r1-0528`; and three files hold no readable metadata, 50 samples: `agentica/deepcoder-14b-preview` (20, its metadata one string, not a list), `qwen/qwen3-235b-a22b` and `qwen/qwq-max-preview` (15 each, no metadata). The script does not confirm that each of the 838 is a private case, only that it is no public one
- What a caller sees: a caller who runs a problem's public cases on the cheap answer runs the same cases in the same order, so it sees the failure the runner recorded for these 1,559, except where a time limit decides a case and the caller's machine is faster or slower
- Decision for row ESC3: LiveCodeBench stays its second dataset, success only (`cost_blind`, since the files record no cost), with the signal `public-test-failed`: escalate when the cheap model's first sample fails a public case. The signal is never wrong when it fires, since a sample that fails a public case fails the problem, but it misses every failure only a private case finds, here 838 of 2,612, so a cascade keeps those wrong answers on the cheap model and its own success is measured, never assumed. ESC3 needs the public cases of all 713 kept problems, `test.jsonl` to `test4.jsonl`, or keeps to these 101; it counts a `no_test` sample both ways, escalated and kept, as a bound, and a file with no readable metadata is never a cheap model there
