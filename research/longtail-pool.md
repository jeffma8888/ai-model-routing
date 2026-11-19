# Longtail-SWE's other configs at their vendors' list prices (2026-11-19)

## Facts

- Question: `evidence/longtail-swe/results.json` (DESIGN 12.26) routes among the four registry models alone, and the release holds seven more configs, two of which resolve about as many issues as `openai/gpt-5.6-luna`. Priced from their vendors' own pages, does any of them change a routed row, at the cheap end where `cost_effective` routing pays above all?
- Data: nebius/Longtail-SWE-trajectories at revision dfd6075c56b7841b9c254cc70a57e39c1df0076c (CC BY 4.0), all eleven parquet files, the converter's four and the seven the block lists, read outside the repo; nothing of the dataset is committed but the counts and rates below
- Script: [longtail_pool.py](longtail_pool.py), `python research/longtail_pool.py` (it needs `pyarrow`, the `evidence` extra); tests/test_research_longtail_pool.py compares the block with a fresh run on the cached files
- Prices: six of the seven from their vendors' own pages, read on 2026-11-19, each the page's uncached input price and its output price in USD per 1M tokens, as 12.25 prices every input token alike: https://api-docs.deepseek.com/quick_start/pricing for `deepseek-v4.1-flash`, the peak rate of `deepseek-flash`, model version DeepSeek-V4.1-Flash-1017 (the off-peak rate is half); https://platform.moonshot.ai/docs/pricing/chat for `kimi-k3.1-pro` and `kimi-k3`; https://www.alibabacloud.com/help/en/model-studio/model-pricing, its International rows, for `qwen3.8-27b` and `qwen3.6-27b` (thinking mode, the same output price); and https://docs.z.ai/guides/overview/pricing for GLM-5.3-Flash. The block gives each price beside its page
- Left out: `deepseek-v4-flash`. Its page says the model behind that legacy name is retired and its requests are now served by DeepSeek-V4.1-Flash-1017 at the Flash price, so no page states a price of the model whose runs the release holds; the 49 runs with no token counts are all its own
- Short answer: no. The six priced models change no routed row: every routed row of the pool, and its per-task routed models, equals the committed four-model file's exactly at every bar and flavor, because `openai/gpt-5.6-luna` and `openai/gpt-6.1-sol` each have at least every added model's held-out success for less held-out cost. The lowest list prices do not make the cheapest runs, and only the oracle moves (the bullets of `## Reading it` give each number, built from the block by the script's `reading`)

## Method

The script loads `evidence/longtail-swe/convert.py` (12.25) as a module of its own and widens that module's `FILES` by the release's other seven files and its `VENDORS` by four regexes over the canonical name (`deepseek-` to `deepseek/`, `kimi-` to `moonshotai/`, `qwen` and a digit to `qwen/`, `glm-` to `z-ai/`), so the converter's own file is unchanged. Each file is checked by size and sha256 (an absent one is downloaded). Each run of a priced model is priced from its tokens by the 12.25 rule, every input token at the input price, cached ones included, and every output token at the output price, an estimate and not a bill; the four registry models keep the `models.json` prices, and a vendor price for a model `models.json` already holds stops the script. The left-out model's file is checked and its runs counted, the ones the converter's `tokens` refuses among them, but none is priced; a run of a priced model that `tokens` refuses stops the script, so no run's tokens are guessed. The converter then builds its matrix at run 0 on the ten models (an issue whose statement changed for any model is dropped for all), and `model_routing.evaluate` scores it with the 12.26 config: bars 0.6, 0.7, 0.8 and 0.9, 50 seeds, both flavors, `evidence/routerbench/results.py` reducing the result. The block is the script's output.

## Results

```text
Pool: 10 models, the 12.25 matrix at run 0 (194 items, 1940 rows, 8 dropped for a changed statement), under the 12.26 config (bars 0.6 0.7 0.8 0.9, 50 seeds, both flavors)

List prices, USD per 1M tokens, and their source (pages read 2026-11-19)
model                          input  output  source
anthropic/claude-opus-5.5          4      20  models.json
deepseek/deepseek-v4.1-flash     0.3     1.2  https://api-docs.deepseek.com/quick_start/pricing
moonshotai/kimi-k3                 3      15  https://platform.moonshot.ai/docs/pricing/chat
moonshotai/kimi-k3.1-pro           2      10  https://platform.moonshot.ai/docs/pricing/chat
openai/gpt-5.6-luna              0.2     1.2  models.json
openai/gpt-5.6-sol                 4      20  models.json
openai/gpt-6.1-sol                 2      10  models.json
qwen/qwen3.6-27b                 0.6     3.6  https://www.alibabacloud.com/help/en/model-studio/model-pricing
qwen/qwen3.8-27b                 0.5       3  https://www.alibabacloud.com/help/en/model-studio/model-pricing
z-ai/glm-5.3-flash              0.15     0.5  https://docs.z.ai/guides/overview/pricing
left out: deepseek/deepseek-v4-flash (606 runs, 49 with no token counts), no price of its own at https://api-docs.deepseek.com/quick_start/pricing

Files read beyond the converter's 4, size and sha256 from the tree API (2026-11-18)
data/swelike__deepseek-v4-flash-max.parquet 95517954 25f291389a4afb3c65ed4a6a3f06c6dcac19c177891a085e51630331e027a703
data/swelike__deepseek-v4.1-flash-max.parquet 128638805 bfdee0faa1bd3d5d91010d8e229c595c0519bc2210d0294a034b0610f9efefa0
data/swelike__glm-5.3-flash-max.parquet 104093005 e4561cb6fba17cfb90d8c7da76c50334c541557c098aa4e0ec0a25058a3d1c0b
data/swelike__kimi-k3-max.parquet 72324912 3a8e0fd992f008009f278f6763f2457e574423222b46671dda1f355ae43d6687
data/swelike__kimi-k3.1-pro-max.parquet 73139661 0b72fb476aeba3e2c8e890d93172f33cdd60da34d09ffe0e023d2c08d7e07dfd
data/swelike__qwen3.6-27b-thinking.parquet 42542761 c412e932656b0eb9b6b0df19eda21e489004cd51b02b1019c024796645f16df8
data/swelike__qwen3.8-27b-xhigh.parquet 84747991 3605de55ec2518cdf8400f328e81bb3d6e24726205df95ffe4594288ea760fa6

Each model at run 0: resolved of 194 (unscored), held-out success and cost in USD over 50 seeds (bar 0.6, cost_effective)
model                          resolved   success      cost
anthropic/claude-opus-5.5       162 (0)     0.837   1745.31
deepseek/deepseek-v4.1-flash    139 (0)     0.714    637.96
moonshotai/kimi-k3              126 (0)     0.655   5055.78
moonshotai/kimi-k3.1-pro        140 (0)     0.723   1090.71
openai/gpt-5.6-luna             140 (0)     0.726    252.57
openai/gpt-5.6-sol              152 (0)     0.787   1143.62
openai/gpt-6.1-sol              155 (1)     0.804    357.50
qwen/qwen3.6-27b                 31 (0)     0.154    414.32
qwen/qwen3.8-27b                 89 (0)     0.459   1248.59
z-ai/glm-5.3-flash               93 (0)     0.479    577.26

Baselines, the pool beside the committed four-model file (bar 0.6, cost_effective)
strategy             pool success     cost   four success     cost
best_on_calibration         0.823  1541.05          0.823  1541.05
cheapest                    0.726   252.57          0.726   252.57
oracle                      0.959   303.76          0.953   379.50

Routed, the pool beside the committed four-model file (success, cost, cleared rate, bar-violation rate)
bar  flavor          pool success     cost cleared violation   four success     cost cleared violation
0.6  cost_effective         0.740   278.72   1.000     0.000        0.740   278.72   1.000     0.000
0.6  cost_blind             0.832  1705.82   1.000     0.000        0.832  1705.82   1.000     0.000
0.7  cost_effective         0.805  1005.68   0.940     0.021        0.805  1005.68   0.940     0.021
0.7  cost_blind             0.832  1705.82   0.940     0.000        0.832  1705.82   0.940     0.000
0.8  cost_effective         0.823  1541.05   0.080     1.000        0.823  1541.05   0.080     1.000
0.8  cost_blind             0.832  1705.82   0.080     1.000        0.832  1705.82   0.080     1.000
0.9  cost_effective         0.823  1541.05   0.000         -        0.823  1541.05   0.000         -
0.9  cost_blind             0.832  1705.82   0.000         -        0.832  1705.82   0.000         -
routed rows exactly equal (all five rates and the cost): 8 of 8; per-task routed models exactly equal: 8 of 8

Routed models of the pool, seeds of 50 per model
0.6  cost_effective  openai/gpt-5.6-luna 38, openai/gpt-6.1-sol 12
0.6  cost_blind      anthropic/claude-opus-5.5 48, openai/gpt-5.6-sol 1, openai/gpt-6.1-sol 1
0.7  cost_effective  openai/gpt-6.1-sol 24, anthropic/claude-opus-5.5 21, openai/gpt-5.6-sol 4, openai/gpt-5.6-luna 1
0.7  cost_blind      anthropic/claude-opus-5.5 48, openai/gpt-5.6-sol 1, openai/gpt-6.1-sol 1
0.8  cost_effective  anthropic/claude-opus-5.5 42, openai/gpt-6.1-sol 7, openai/gpt-5.6-sol 1
0.8  cost_blind      anthropic/claude-opus-5.5 48, openai/gpt-5.6-sol 1, openai/gpt-6.1-sol 1
0.9  cost_effective  anthropic/claude-opus-5.5 42, openai/gpt-6.1-sol 7, openai/gpt-5.6-sol 1
0.9  cost_blind      anthropic/claude-opus-5.5 48, openai/gpt-5.6-sol 1, openai/gpt-6.1-sol 1
```

## Reading it

- Routed rows: on 8 of 8 (bar, flavor) rows the pool's routed success, cost and rates equal the committed four-model file's exactly, and on 8 of 8 its per-task routed models do; no added model is routed on any seed at any bar or flavor.
- Each added model alone: held-out success 0.154 (`qwen/qwen3.6-27b`) to 0.723 (`moonshotai/kimi-k3.1-pro`), held-out cost 414.32 (`qwen/qwen3.6-27b`) to 5055.78 (`moonshotai/kimi-k3`) USD; `openai/gpt-5.6-luna` (0.726 for 252.57) and `openai/gpt-6.1-sol` (0.804 for 357.50) each have at least the held-out success of every added model for no more held-out cost.
- A list price is not a cost: `z-ai/glm-5.3-flash` has the pool's lowest input and output prices (0.15 and 0.5) but a held-out cost of 577.26, 2.29 times that of `openai/gpt-5.6-luna` (252.57 at 0.2 and 1.2), the least held-out cost of the pool.
- The 12.3 oracle is at 0.959 for 303.76 on the pool, above the four-model file's 0.953 for 379.50: an added model resolves some held-out issue that no registry model does, but the router, which sends the one task to one model per seed, cannot take it.
- Left out: `deepseek/deepseek-v4-flash`, 606 runs, 49 of them with no token counts; no matrix holds a run of it.

## Recommendation

Nothing for the README or a results file now. A second results file on the pool would repeat the committed file's routed rows exactly, and its size, `Regenerate` line and cached-file test would buy no new number. When the README's Longtail-SWE subsection lands (row E26e), one clause linking this note can say that the release's six other priced models change no routed row. A later price cut that makes an added model's held-out cost fall below `openai/gpt-5.6-luna`'s at no lower held-out success would show on a rerun of the script.

## Limits

- The prices are one day's read of four vendor pages, and the registry's four are `models.json`'s. A run's cost is its tokens at list prices with no cache discount (12.25), so a run that re-reads a cached context may cost less at its vendor's cache rates, which the 12.25 rule does not apply
- Run 0 alone, one task, and the 8 issues dropped for a changed statement, as in the committed file
- `deepseek-v4-flash` is out of the pool, so the oracle and the routed rows above never see its runs
