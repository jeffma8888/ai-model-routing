# Design: ai-model-routing

Status: v1.0 spec, 2026-10-29. This file is the contract that tests are written from. Module paths, names, fields, formats and exit codes below are binding; anything not pinned here is the implementer's choice.

## 1. Problem
- Eval and judge calls are a large share of model spend in a team that evaluates seriously: every candidate output, on every test case, on every rubric, gets judged, often more than once
- Sending every judge call to the strongest model wastes money; sending it to the cheapest model silently weakens the evals that every later decision trusts
- The fix is to route per task: measure each candidate model on a labeled calibration set for that task, and pick the cheapest model whose measured quality clears the task's bar with statistical confidence, with fallback when a call fails, a log of every attempt, and cost rolled up by any tag

## 2. Two flavors, one algorithm
- `cost_effective`: among models that clear the bar, pick the one with the lowest expected cost per call; ties go to higher quality
- `cost_blind`: identical pipeline, but the router treats token cost as 0, so among models that clear the bar it picks the highest quality. Fallback, monitoring and attribution are unchanged; the log still records list-price cost so spend stays visible
- The flavor changes exactly one thing: the `routing_cost` used to rank candidates

## 3. Package layout (Python 3.10+, standard library only)
```
model_routing/
  __init__.py     re-exports every public name below
  registry.py     Model, Registry
  tasks.py        Task, load_tasks
  stats.py        wilson_lower_bound, Stats, calibrate_from_results
  priors.py       Priors
  router.py       Candidate, RouteDecision, Router, NoModelClearsBar, reason codes
  providers.py    Completion, ProviderError, Provider, FakeProvider, OpenAICompatibleProvider
  executor.py     Attempt, CallResult, Executor, AllModelsFailed
  monitor.py      Monitor, load_records, report
  demo.py         run_demo
  cli.py          main
  data/
    models.json         public list prices and context windows (section 9)
    priors.json         leaderboard-derived priors (section 9)
    example_tasks.json  three judge tasks used by the CLI defaults and docs
tests/            owned by the QA author; the implementer never edits it
```
- `json_validator` (section 7) lives in `executor.py`
- `model_routing.DATA_DIR` is the `pathlib.Path` of the packaged `data/` folder

## 4. Data model

### 4.1 Model and Registry (`registry.py`)
- `@dataclass(frozen=True) class Model`: `id: str`, `family: str`, `price_in: float` (USD per 1M input tokens), `price_out: float` (USD per 1M output tokens), `context_window: int`, `aliases: dict[str, str]` (default empty; provider name to that provider's model ID)
- `Model.cost(input_tokens: int, output_tokens: int) -> float` returns `(input_tokens * price_in + output_tokens * price_out) / 1_000_000`
- `class Registry`: `Registry(models: Iterable[Model])`; `Registry.load(path) -> Registry` reads the models.json format (section 9); `.models -> tuple[Model, ...]` in file order; `.get(model_id) -> Model` raises `KeyError` for an unknown ID; duplicate IDs raise `ValueError` at construction

### 4.2 Task (`tasks.py`)
- `@dataclass(frozen=True) class Task` fields and defaults:
  - `name: str`
  - `bar: float` (required, in [0, 1]; the minimum acceptable agreement with gold labels)
  - `min_samples: int = 30` (fewer measured trials than this can never clear the bar)
  - `confidence: float = 0.95`
  - `independent_of_generator: bool = True` (exclude the generator's model AND its family)
  - `exclude_families: tuple[str, ...] = ()`
  - `expected_input_tokens: int = 1000`, `expected_output_tokens: int = 200`
  - `on_no_model: str = "refuse"` (or `"best_available"`)
  - `max_fallbacks: int = 2`
  - `prior_category: str | None = None`
  - `timeout_s: float = 60.0`
- Invalid values raise `ValueError` at construction: bar outside [0, 1], `min_samples < 1`, confidence outside (0, 1), unknown `on_no_model`, negative token counts or `max_fallbacks`
- `load_tasks(path) -> dict[str, Task]` reads `{"tasks": [ {field: value, ...}, ... ]}`; JSON lists become tuples; duplicate names raise `ValueError`

### 4.3 Quality statistics (`stats.py`)
- `wilson_lower_bound(successes: int, trials: int, confidence: float = 0.95) -> float`
  - z = `NormalDist().inv_cdf(1 - (1 - confidence) / 2)` (two-sided interval, lower end); p = successes / trials
  - LB = `(p + z*z/(2n) - z*sqrt(p*(1-p)/n + z*z/(4n*n))) / (1 + z*z/n)`, clamped to `>= 0.0`
  - returns `0.0` when `trials == 0`; raises `ValueError` when `successes < 0`, `trials < 0` or `successes > trials`
  - reference values at confidence 0.95 (to 6 decimals): (27, 30) 0.743789; (45, 50) 0.786398; (90, 100) 0.825634; (170, 200) 0.793944; (10, 10) 0.722467; (0, 10) 0.0
- `class Stats`: in-memory map from `(task, model_id)` to `(successes, trials)`
  - `Stats()`; `.get(task, model_id) -> tuple[int, int]` returns `(0, 0)` when absent; `.add(task, model_id, successes, trials)` accumulates (adds to existing counts) and validates like `wilson_lower_bound`
  - `Stats.load(path)` and `.save(path)` use `{"stats": [{"task": ..., "model": ..., "successes": int, "trials": int}, ...]}`; save writes rows sorted by (task, model)
  - `.merge(other: Stats) -> Stats` returns a new Stats with summed counts
- `calibrate_from_results(rows: Iterable[dict]) -> Stats`: each row has `task`, `model`, and either `correct` (bool) or both `prediction` and `gold` (correct when equal with `==`); a row with neither raises `ValueError`. Each row is one trial

### 4.4 Priors (`priors.py`)
- Leaderboard numbers are not agreement rates, so priors NEVER clear a bar. They only order candidates when nothing has been measured (cold start) and tell you which models to calibrate first
- `Priors.load(path)` reads `{"categories": {name: {"metric": str, "source": str, "as_of": str, "scores": {model_id: number}}}}`; `Priors(categories: dict)` takes the same inner dict
- `.score(category, model_id) -> float | None`; unknown category or model returns `None`
- `.ranked(category) -> list[str]` model IDs by descending score, ties by ascending ID

## 5. Routing (`router.py`)

### 5.1 Types
- Reason codes (module constants with these exact string values): `EXCLUDED_MODEL = "excluded_model"`, `EXCLUDED_FAMILY = "excluded_family"`, `GENERATOR = "generator"`, `GENERATOR_FAMILY = "generator_family"`, `CONTEXT_TOO_SMALL = "context_too_small"`, `INSUFFICIENT_SAMPLES = "insufficient_samples"`, `BELOW_BAR = "below_bar"`, `PASSES = "passes"`
- `@dataclass(frozen=True) class Candidate`: `model_id`, `family`, `successes`, `trials`, `quality_lb: float`, `routing_cost: float`, `list_cost: float`, `eligible: bool`, `passes: bool`, `reason: str`
- `@dataclass(frozen=True) class RouteDecision`: `task: str`, `flavor: str`, `primary: str`, `fallbacks: tuple[str, ...]`, `below_bar: bool`, `basis: str` (`"measured"` or `"prior"`), `candidates: tuple[Candidate, ...]` (one per registry model, registry order); `.to_dict()` returns plain JSON-able types (tuples become lists, candidates become dicts)
- `class NoModelClearsBar(Exception)` with attribute `.candidates` (the tuple above)
- Flavor names: `"cost_effective"`, `"cost_blind"`; anything else raises `ValueError`

### 5.2 `Router(registry, tasks: dict[str, Task], stats: Stats, priors: Priors | None = None)`
The constructor stores its arguments as attributes `.registry`, `.tasks`, `.stats`, `.priors`.
`.select(task_name, flavor="cost_effective", generator_model=None, exclude_models=()) -> RouteDecision`; unknown task raises `KeyError`. Steps, in order, per registry model (the first rule that applies sets `reason`):
1. ID in `exclude_models`: `excluded_model`
2. family in `task.exclude_families`: `excluded_family`
3. `independent_of_generator` and ID equals `generator_model`: `generator`
4. `independent_of_generator` and family equals the generator's family (generator looked up in the registry; an unknown generator ID raises `KeyError`): `generator_family`
5. `context_window < expected_input_tokens + expected_output_tokens`: `context_too_small`
6. measured `trials < task.min_samples`: `insufficient_samples` (still eligible for the cold-start path below)
7. `wilson_lower_bound(successes, trials, task.confidence) < task.bar`: `below_bar`
8. otherwise `passes`
- `eligible` is True for reasons 6 to 8; `passes` only for 8
- `list_cost = model.cost(expected_input_tokens, expected_output_tokens)`; `routing_cost = list_cost` for `cost_effective`, `0.0` for `cost_blind`
- `quality_lb = wilson_lower_bound(successes, trials, confidence)` for every candidate (0.0 when unmeasured)

### 5.3 Choosing
- If any candidate passes: sort passing candidates by `(routing_cost, -quality_lb, model_id)`; `primary` is the first; `fallbacks` are the next `max_fallbacks`; `below_bar=False`; `basis="measured"`
- Else if `on_no_model == "refuse"`: raise `NoModelClearsBar`
- Else (`best_available`): among eligible candidates with `trials > 0`, sort by `(-quality_lb, routing_cost, model_id)`; if that list is non-empty use it (`basis="measured"`); otherwise, if the router has priors and the task has `prior_category`, use eligible candidates that have a prior score, sorted by `(-score, routing_cost, model_id)` (`basis="prior"`); `primary` is the first, `fallbacks` the next `max_fallbacks`, `below_bar=True`; if both lists are empty raise `NoModelClearsBar`
- Note: in `cost_blind` the passing sort reduces to `(-quality_lb, model_id)`, so the best measured model wins

## 6. Providers (`providers.py`)
- `@dataclass(frozen=True) class Completion`: `text: str`, `input_tokens: int`, `output_tokens: int`
- `class ProviderError(Exception)`: any failure a fallback should handle (timeout, rate limit, 5xx, bad response)
- `class Provider(Protocol)`: `complete(self, model_id: str, messages: list[dict], timeout_s: float) -> Completion`
- `FakeProvider(script: dict[str, Callable[[list[dict]], Completion]])`: calls `script[model_id](messages)`; an exception raised by the callable propagates unchanged; a model ID not in the script raises `ProviderError`. `.calls` is a list of `(model_id, messages)` in call order
- `OpenAICompatibleProvider(base_url: str, api_key_env: str = "OPENAI_API_KEY", model_map: dict[str, str] | None = None)`: POSTs `{"model": mapped_id, "messages": messages}` to `base_url.rstrip("/") + "/chat/completions"` with `Authorization: Bearer <key>` via `urllib.request`, reads `choices[0].message.content` and `usage.prompt_tokens` / `usage.completion_tokens`; any network, HTTP or parse failure raises `ProviderError`. Works with any OpenAI-compatible endpoint (vendor APIs, gateways, local servers). Tests must not touch the network: it accepts an optional `opener` callable (default `urllib.request.urlopen`) for injection

## 7. Execution with fallback (`executor.py`)
- `@dataclass(frozen=True) class Attempt`: `model: str`, `outcome: str` (`"ok"`, `"error"` or `"invalid"`), `error: str | None` (exception class name and message for errors, `"validation failed"` for invalid), `latency_ms: float`, `input_tokens: int`, `output_tokens: int`, `cost_usd: float`
- `@dataclass(frozen=True) class CallResult`: `call_id: str`, `text: str`, `model: str`, `attempts: tuple[Attempt, ...]`, `decision: RouteDecision`
- `class AllModelsFailed(Exception)` with `.attempts` and `.decision`
- `Executor(router, provider, monitor=None, clock=time.monotonic, now=None, id_factory=None)`; `now` returns an ISO 8601 UTC string (default: current UTC time); `id_factory` returns a call ID (default: `uuid.uuid4().hex`)
- `.call(task_name, messages, flavor="cost_effective", generator_model=None, exclude_models=(), tags=None, validate=None) -> CallResult`
  1. `decision = router.select(...)` (its exceptions propagate)
  2. for each model in `(primary, *fallbacks)`: time `provider.complete(model, messages, task.timeout_s)` with `clock`
     - `ProviderError` raised: attempt outcome `error`, tokens 0, cost 0.0; continue. Any other exception propagates (it is a bug, not an outage)
     - `validate` given and `validate(text)` is falsy: outcome `invalid`, tokens and cost from the completion; continue
     - otherwise: outcome `ok`; stop
  3. every attempt is passed to `monitor.record(...)` (when a monitor is given) as it happens, using the record schema in 8.1
  4. no `ok` attempt: raise `AllModelsFailed`
- `cost_usd` of an attempt is the list-price cost of its actual tokens: `registry.get(model).cost(input_tokens, output_tokens)`
- Helper `json_validator(*required_keys) -> Callable[[str], bool]`: True when the text parses as a JSON object containing every key

## 8. Monitoring and cost attribution (`monitor.py`)

### 8.1 Record schema (one JSON object per attempt)
`ts` (str), `call_id` (str), `task` (str), `flavor` (str), `model` (str), `family` (str), `attempt` (int, 0-based index within the call), `final` (bool, True on the call's last attempt), `outcome` (str), `error` (str or null), `latency_ms` (float), `input_tokens` (int), `output_tokens` (int), `cost_usd` (float, list price, recorded in both flavors), `routing_cost_usd` (float: equals `cost_usd` in `cost_effective`, `0.0` in `cost_blind`), `below_bar` (bool), `basis` (str), `tags` (object of string to string; `{}` when none)

### 8.2 `Monitor(path=None)`
- `.record(rec: dict)` appends to `.records` (a list) and, when `path` is set, appends one JSON line to that file
- `load_records(path) -> list[dict]` reads a JSONL file, skipping blank lines

### 8.3 `report(records, by="model") -> list[dict]`
- `by` is `"model"`, `"task"`, `"flavor"`, `"family"`, or `"tag:<key>"` (records without that tag group under `"(none)"`); anything else raises `ValueError`
- Attempt-level sums per group use each attempt's own value: `attempts`, `ok`, `errors`, `invalid`, `input_tokens`, `output_tokens`, `cost_usd`, `routing_cost_usd` (costs rounded to 6 decimals)
- Call-level metrics use the call's FINAL attempt to pick the group: `calls` (calls whose final attempt is in the group), `failed_calls` (final outcome not ok), `fallback_calls` (final attempt index > 0), `fallback_rate` (`fallback_calls / calls`, 0.0 when no calls)
- `p50_latency_ms`, `p95_latency_ms`: nearest-rank percentile over the group's `ok` attempts (sorted ascending, index `ceil(q * n) - 1`), `None` when there are none
- Each row is a dict with key `group` plus the keys above; rows sorted by descending `cost_usd`, then `group`

## 9. Data files
- `model_routing/data/models.json`: `{"version": str, "as_of": "YYYY-MM-DD", "currency": "USD", "models": [{"id", "family", "price_in", "price_out", "context_window", "source"}]}`; IDs are provider-neutral (`vendor/model-name`); map them to a provider's IDs with `aliases`; extra keys such as `notes` are allowed and ignored by `Registry.load`; `aliases` is optional
- `model_routing/data/priors.json`: format in 4.4; each category cites one public leaderboard with its date
- `model_routing/data/example_tasks.json`: three judge tasks (`faithfulness_judge`, `code_correctness_judge`, `pairwise_preference_judge`) whose generator-independence and bars are realistic

## 10. CLI (`model-routing`, entry point `model_routing.cli:main(argv=None) -> int`)
- `select TASK [--flavor cost_effective|cost_blind] [--generator MODEL] [--exclude MODEL ...] [--registry PATH] [--tasks PATH] [--stats PATH] [--priors PATH] [--json]`
  - prints primary, fallbacks, basis, below_bar and a candidate table; `--json` prints `RouteDecision.to_dict()`
- `calibrate --results PATH --stats PATH`: reads results JSONL (section 4.3 rows), merges into the stats file (created if missing), prints per (task, model) counts and lower bounds
- `report --log PATH [--by KEY] [--json]`
- `demo [--out DIR]`: runs `run_demo` and prints its summary
- Defaults: `--registry` and `--priors` and `--tasks` point at the packaged files under `model_routing.DATA_DIR`; `--stats stats.json` in the current directory (a missing stats file means empty stats; a missing priors file means no priors)
- Exit codes: 0 success; 2 bad input (missing file, bad JSON, unknown task or model, invalid value); 3 `NoModelClearsBar` on `select`

## 11. Demo (`demo.py`)
- `run_demo(out_dir: str | Path, seed: int = 7) -> dict` uses `FakeProvider` and clearly fictional models (`demo/` prefix) so no one mistakes simulated accuracy for a real measurement: four judges in two families with different prices and true accuracies, one generator in a third family
- Steps: build a 300-item synthetic labeled calibration set; calibrate every judge; select in both flavors; run 200 judge calls per flavor with a simulated outage on a fraction of the primary's calls; write `calls.jsonl` and `stats.json` to `out_dir`
- Returns a summary dict with keys `cost_effective` and `cost_blind`, each holding `primary`, `fallbacks`, `calls`, `fallback_calls`, `cost_usd`; deterministic for a given seed

## 12. Non-goals for v1 (two-way doors, deferred)
- Native vendor SDK adapters (the OpenAI-compatible adapter covers gateways), async execution, streaming
- Learned or contextual routers (per-prompt difficulty prediction); v1 routes per task
- Online drift detection beyond re-calibrating from audited results; budgets and alerts
- Price refresh automation
