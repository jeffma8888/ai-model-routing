# Does the 13.2 re-read rule predict the ledger runs' prompt tokens?

## Facts

- Question: does the work-call rule of `DESIGN.md` 13.2, by which each call re-reads every earlier input and whole output on its path, predict the prompt tokens of runs that record them per call?
- Data: the ledger runs that `evidence/ledger-handoff/results.py` reads (`DESIGN.md` 13.15), `data/ledger/single.jsonl` and `data/ledger/decomposed.jsonl` of https://github.com/akshitanchan/attention-handoff-tax at d891b4eb92abf039431be850646830b486f9e5af, CC BY 4.0 for the data; one model, `openai/gpt-oss-20b`, in every call; 300 items, 100 at each of depths 20, 50 and 100, the same keys on both paths
- Answer: the rule over-predicts every item on both paths, the most on the whole-history path and the more the deeper the item, since the runs' history keeps each call's reply and not its reasoning while 13.2 re-reads each earlier output whole; re-reading the reply alone leaves a small gap that does not grow with depth
- Recommendation: keep the re-read structure; let a caller state how much of each output later calls re-read (follow-on row D11); charge the brief's output at the completion of the call that writes it, and its reads at the brief's own size
- Read on 2026-11-15, with the run code at the same revision, `code/ledger_experiment.py`, read for what the history keeps

## The rule

13.2 (the work-call bullet of v1.219, the K-call totals of v1.38): call j of a path's K calls reads X + j * S_in + (j - 1) * S_out tokens, X the path's base context, S_in each call's new input and S_out each call's output, so every earlier input and every earlier output is re-read in full and nothing is summarised between calls. On these runs:

- X + S_in is a context's first prompt, as measured
- S_in is the run settings' `k`, the tokens the run pads each transaction message to by its own counter (`tiktoken/o200k_base`), the same in both settings files
- S_out of an earlier call is its `completion_tokens`, the measured output (13.2 v1.33)

So call j of a context is predicted to read its first prompt + (j - 1) * k + the completions of the calls before it in that context. On `single` an item is one context. On the chain (`decomposed`) a context ends at each note's `after_t` and the next starts again from its own first prompt (the system message, the note with its `OK` reply, then the first transaction); a note's own call reads its context's whole history with no transaction, as one more call would, since 13.2 gives the note request no size. The `reply` rule is the same with each earlier completion less its `reasoning_tokens`: the run code appends only the reply text to the history, so no later call re-reads the reasoning.

## Method

- `research/ledger_cost_model.py` reads the pinned files through the 13.15 converter, loaded by path: `fetch` checks each file by size and sha256, and `read_json`, `check_config`, `read_lines` and `ledger` read and check them; the two settings files must give one `k`
- Measured is the sum of an item's `prompt_tokens`, its note calls included on the chain, as the converter builds the medians of `evidence/ledger-handoff/results.json`
- Per depth and path it prints the median measured and predicted sums and, per item, measured over predicted as a median, the 10th to 90th percentile (`statistics.quantiles`, n = 10, inclusive) and the highest; then single over chain for the medians under each rule; then the chain notes' median share of an item's measured prompt tokens, with the median completion of a note's call and the median note size
- No price: one model makes every call, so a ratio of tokens is what any price would scale

## Results

```text
$ python research/ledger_cost_model.py
k = 400 tokens per transaction; ratios are measured over predicted, median (10th to 90th percentile, highest)

depth 20, 100 items
  single: measured 87,471.0, 13.2 rule 94,742.5, ratio 0.923 (0.907 to 0.930, highest 0.943); reply rule 90,930.0, ratio 0.962 (0.958 to 0.964, highest 0.966)
  chain: measured 38,006.0, 13.2 rule 39,861.5, ratio 0.954 (0.948 to 0.959, highest 0.962); reply rule 38,629.0, ratio 0.984 (0.982 to 0.985, highest 0.987)
  single over chain, medians: measured 2.30, 13.2 rule 2.38, reply rule 2.35
  chain notes: 19.1% of an item's measured prompt tokens (median); a note's call wrote a median of 281.0 completion tokens for a note of 163.0

depth 50, 100 items
  single: measured 517,315.0, 13.2 rule 571,766.5, ratio 0.903 (0.870 to 0.914, highest 0.923); reply rule 539,300.0, ratio 0.959 (0.956 to 0.961, highest 0.964)
  chain: measured 101,419.0, 13.2 rule 106,544.0, ratio 0.953 (0.946 to 0.959, highest 0.962); reply rule 102,909.5, ratio 0.985 (0.984 to 0.986, highest 0.988)
  single over chain, medians: measured 5.10, 13.2 rule 5.37, reply rule 5.24
  chain notes: 22.1% of an item's measured prompt tokens (median); a note's call wrote a median of 314.0 completion tokens for a note of 176.0

depth 100, 100 items
  single: measured 2,029,808.0, 13.2 rule 2,365,424.5, ratio 0.859 (0.791 to 0.891, highest 0.900); reply rule 2,118,375.0, ratio 0.958 (0.956 to 0.961, highest 0.963)
  chain: measured 206,613.0, 13.2 rule 217,150.5, ratio 0.952 (0.945 to 0.956, highest 0.960); reply rule 209,751.5, ratio 0.986 (0.985 to 0.986, highest 0.987)
  single over chain, medians: measured 9.82, 13.2 rule 10.89, reply rule 10.10
  chain notes: 23.0% of an item's measured prompt tokens (median); a note's call wrote a median of 320.0 completion tokens for a note of 174.0
```

## Reading it

- The 13.2 rule over-predicts every item: no item's measured prompt tokens reach its prediction, the highest ratio being 0.943 on `single` and 0.962 on the chain
- On `single` the gap grows with depth: the median ratio is 0.923, 0.903 and 0.859 at depths 20, 50 and 100, and the 10th percentile falls to 0.791 at depth 100. Each call is charged the reasoning of every call before it, so the over-charge grows with the number of calls before each one
- Re-reading the reply alone, the median ratio is 0.962, 0.959 and 0.958 on `single` and 0.984, 0.985 and 0.986 on the chain, flat with depth. What is left is a constant per call: each call's prompt grows by a little less than k and the earlier completion less its reasoning, which k, the 400 tokens each transaction is padded to by the run's counter, being more than a transaction adds to the measured prompt would explain, and so would a reply counted larger than the history holds it; these runs do not tell the two apart
- The rule over-states the whole-history path more than the chain, so it over-states what the fresh contexts save: single over chain is 9.82 measured at depth 100 against 10.89 by the rule and 10.10 by the reply rule, 2.30, 2.38 and 2.35 at depth 20 and 5.10, 5.37 and 5.24 at depth 50
- The chain's note calls are a median 19.1%, 22.1% and 23.0% of an item's measured prompt tokens at depths 20, 50 and 100, and a note's call wrote a median of 281.0 to 320.0 completion tokens for a note of 163.0 to 176.0

## Recommendation

- Keep the re-read structure. With the reasoning set aside, each call does re-read every earlier input and reply in full: the reply rule's median ratios, 0.958 to 0.986, are flat with depth on both paths
- Let a caller say how much of each output later calls re-read. For a model whose history drops its reasoning, 13.2 charges every later call for tokens it never reads, and the over-charge grows with the number of calls (a median 0.923 to 0.859 on `single`), so it over-states the cost of the path with more re-reads, here the whole history, and would tilt an inline-or-delegate choice toward delegating; no result here recomputes a decision. Follow-on row D11: an optional input, the share of S_out that a later call re-reads, whose default keeps every committed result byte for byte, with these runs as its first measured case and README Limitations stating the over-statement until it ships
- Charge the brief's output at the completion of the call that writes it, and keep the brief's own size for its reads. 13.2 uses B three times: once as the parent's output, and as what the delegate and the parent's later calls read. Here a note's call wrote a median of 281.0 to 320.0 completion tokens for notes of 163.0 to 176.0, the size the next context reads, so one B taken from the brief's size under-states its output charge on a reasoning model and one taken from the completion over-states every read; D11 should give the output charge its own size where 13.1 defines B. The note calls' reads, a median 19.1% to 23.0% of the chain's prompt tokens, need no change: the chain makes them because no parent persists, while the 13.2 decision turn is a parent call made on both paths

## Limits

- One synthetic task and one open model at low reasoning effort; a model whose history keeps its reasoning makes the 13.2 rule the right one, and another host may count tokens differently
- k is the run's padding target by its own counter, not a measured count per message, one of the two causes the flat gap of the reply rule allows; the note request's tokens are left out of the note calls' prediction, as 13.2 has no size for them
- Tokens only: no price and no prompt caching, which would make each re-read cheaper still (13.2 v1.41 prices only the parent's cached reads of its context)
- The chain is a surrogate for the 13 hand-off (13.15): no parent reads a result back, so the result size R and the parent's later calls are not tested

## Regenerate

`python research/ledger_cost_model.py` (standard library). It downloads nothing when the six files of `evidence/ledger-handoff/results.py` are in that converter's cache, `~/.cache/ai-model-routing-evidence/ledger-handoff`, and otherwise the converter's `fetch` downloads them, about 11 MB, and checks each by size and sha256.
