"""An offline, deterministic demonstration with clearly fictional models."""

from __future__ import annotations

import json
import math
import random
from dataclasses import fields
from pathlib import Path
from typing import Callable, Dict, List, Optional, Sequence, Union

from .budget import Budget, BudgetLedger
from .delegation import DELEGATE
from .executor import AllModelsFailed, Executor, estimate_prompt_tokens, json_validator
from .monitor import Monitor, report
from .procedures import Procedure, ProcedureResult
from .providers import Completion, FakeProvider, ProviderError
from .registry import Model, Registry, self_hosted_prices
from .router import Router
from .stats import calibrate_from_results
from .tasks import Task

DEMO_TASK = "demo_faithfulness_judge"
GENERATOR = "demo/cedar-writer"
CALIBRATION_ITEMS = 300
CALLS_PER_FLAVOR = 200
OUTAGE_RATE = 0.15
MARKER = ".model-routing-demo"
OUTPUTS = ("calls.jsonl", "stats.json", "outcomes.jsonl", "models.json", "tasks.json")
DELEGATION_PARENT = "demo/atlas-max"
DELEGATION_CONTEXT_TOKENS = 60_000

JUDGES = (
    (Model("demo/atlas-max", "atlas", 10.0, 50.0, 200_000), 0.96),
    (Model("demo/birch-pro", "birch", 4.0, 20.0, 128_000), 0.93),
    (Model("demo/atlas-mid", "atlas", 2.0, 10.0, 200_000), 0.91),
    (Model("demo/birch-nano", "birch", 0.10, 0.50, 32_000), 0.74),
)
GENERATOR_MODEL = Model(GENERATOR, "cedar", 3.0, 15.0, 128_000)


class _SimulatedClock:
    """A clock the fake provider advances by each call's simulated latency."""

    def __init__(self) -> None:
        self.seconds = 0.0

    def __call__(self) -> float:
        return self.seconds

    def timestamp(self) -> str:
        whole = int(self.seconds)
        millis = min(999, int((self.seconds - whole) * 1000))
        hours, rest = divmod(whole, 3600)
        minutes, seconds = divmod(rest, 60)
        return f"2026-01-01T{hours % 24:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}Z"


def _calibration_rows(rng: random.Random) -> List[dict]:
    gold = [rng.choice(("faithful", "unfaithful")) for _ in range(CALIBRATION_ITEMS)]
    rows = []
    for model, accuracy in JUDGES:
        for label in gold:
            if rng.random() < accuracy:
                prediction = label
            else:
                prediction = "unfaithful" if label == "faithful" else "faithful"
            rows.append({"task": DEMO_TASK, "model": model.id,
                         "prediction": prediction, "gold": label})
    return rows


def _outcome_lines(calibration_rows: List[dict], task: Task) -> str:
    """The calibration set as an outcome matrix (DESIGN 11, 12.1); draws no random numbers."""
    cost = {model.id: model.cost(task.expected_input_tokens, task.expected_output_tokens)
            for model, _ in JUDGES}
    # _calibration_rows emits each judge's items in gold-label order, so a per-judge
    # counter gives item IDs that line up across judges
    seen: Dict[str, int] = {}
    lines = []
    for row in calibration_rows:
        n = seen.get(row["model"], 0)
        seen[row["model"]] = n + 1
        lines.append(json.dumps({"task": row["task"], "item": f"item-{n:03d}",
                                 "model": row["model"],
                                 "correct": row["prediction"] == row["gold"],
                                 "cost_usd": cost[row["model"]]}) + "\n")
    return "".join(lines)


def _registry_json(registry: Registry) -> str:
    """The demo's registry in the models.json format (DESIGN 9, 11 v1.9)."""
    rows = [{"id": m.id, "family": m.family, "price_in": m.price_in, "price_out": m.price_out,
             "context_window": m.context_window} for m in registry.models]
    return json.dumps({"note": "Fictional demo models; the prices are made up.",
                       "currency": "USD", "models": rows}, indent=2) + "\n"


def _tasks_json(task: Task) -> str:
    """The demo's task in the tasks file format (DESIGN 4.2, 11 v1.9)."""
    row = {f.name: getattr(task, f.name) for f in fields(Task)}
    row["exclude_families"] = list(task.exclude_families)
    if not row["slices"]:
        del row["slices"]
    if row["cascades"]:
        row["cascades"] = [{"cheap": c.cheap, "strong": c.strong, "signal": c.signal}
                           for c in task.cascades]
    else:
        del row["cascades"]
    if row["failure_policy"] == "none":  # DESIGN 4.2 v1.567
        del row["failure_policy"]
    return json.dumps({"tasks": [row]}, indent=2) + "\n"


def _script(registry: Registry, rng: random.Random, clock: _SimulatedClock,
            state: Dict[str, str]):
    def judge(model_id: str):
        def respond(messages: List[dict]) -> Completion:
            if model_id == state["primary"] and rng.random() < OUTAGE_RATE:
                clock.seconds += rng.uniform(1.0, 3.0)
                raise ProviderError("simulated outage: HTTP 503")
            clock.seconds += rng.uniform(0.4, 2.5)
            verdict = rng.choice(("faithful", "unfaithful"))
            text = json.dumps({"verdict": verdict, "reason": "simulated"})
            return Completion(text, rng.randint(850, 1150), rng.randint(120, 260))
        return respond
    return {model.id: judge(model.id) for model in registry.models}


def _hand_off(router: Router, provider: FakeProvider, monitor: Monitor,
              clock: _SimulatedClock, state: Dict[str, str], validate, flavor: str,
              ledger: Optional[BudgetLedger] = None) -> dict:
    """One inline-or-sub-agent decision, its hand-off run when it delegates (DESIGN 11 v1.12)."""
    decision = router.decide_delegation(
        DEMO_TASK, DELEGATION_PARENT, flavor, context_tokens=DELEGATION_CONTEXT_TOKENS,
        brief_tokens=400, result_tokens=60, generator_model=GENERATOR)
    first = len(monitor.records)
    if decision.mode == DELEGATE:
        state["primary"] = decision.route.primary
        executor = Executor(router, provider, monitor=monitor, clock=clock,
                            now=clock.timestamp, id_factory=lambda: f"{flavor}-delegated-0001",
                            ledger=ledger)
        brief = [
            {"role": "system", "content": "Judge whether the answer is faithful "
                                          "to the source. Reply in JSON with a verdict."},
            {"role": "user", "content": "Brief from the parent: one synthetic item."},
        ]
        try:
            executor.call_delegated(decision, brief,
                                    tags={"suite": "demo", "dataset": "synthetic"},
                                    validate=validate)
        except AllModelsFailed:
            pass
    records = _attempts(monitor.records[first:])
    return {
        "parent": decision.parent,
        "context_tokens": DELEGATION_CONTEXT_TOKENS,
        "mode": decision.mode,
        "model": decision.model,
        "reason": decision.reason,
        "inline_cost_usd": decision.inline_cost_usd,
        "delegate_cost_usd": decision.delegate_cost_usd,
        "hand_off_calls": sum(1 for r in records if r["final"]),
        "hand_off_cost_usd": round(sum(r["cost_usd"] for r in records), 6),
    }


def _attempts(records: List[dict]) -> List[dict]:
    """The attempt records of ``records``, without the budget records (DESIGN 11 v1.599)."""
    return [record for record in records if "budget_event" not in record]


def run_demo(out_dir: Union[str, Path], seed: int = 7,
             budgets: Optional[Sequence[Budget]] = None) -> dict:
    """Run the offline demo and write its output files (``OUTPUTS``) to ``out_dir``.

    Four fictional judges in two families are calibrated on a 300-item
    synthetic labeled set, routed in both flavors, and each flavor runs 200
    judge calls with a simulated outage on a share of the primary's calls.
    ``outcomes.jsonl`` holds the calibration set as an outcome matrix for
    ``model-routing evaluate``; ``models.json`` and ``tasks.json`` hold the demo's
    registry and task, so ``select`` and ``delegate`` can run on the output.
    Then a ``demo/atlas-max`` parent 60,000 tokens into a session asks, in each
    flavor, whether to do one more check inline or hand it to a sub-agent; a
    delegated check runs through ``Executor.call_delegated`` and its records,
    tagged ``delegated`` and ``parent``, follow the judge calls in ``calls.jsonl``.
    Returns ``{flavor: {primary, fallbacks, calls, fallback_calls, cost_usd,
    delegation}}``, where the first five count the 200 judge calls only; the
    result is deterministic for a given seed.

    An empty marker file ``.model-routing-demo`` records that the folder holds
    demo output. If any of those files already exists without
    that marker, ``FileExistsError`` is raised and nothing is modified; with
    the marker, the previous demo output is replaced.

    ``budgets``, None or a list or tuple of :class:`Budget`, puts every call of the run under
    one :class:`BudgetLedger` of them; a ``BudgetExceeded`` ends the run (DESIGN 11 v1.599).
    """
    ledger = None if budgets is None else BudgetLedger(budgets)  # checked before any write
    out = Path(out_dir)
    marker = out / MARKER
    if not marker.exists():
        existing = [name for name in OUTPUTS if (out / name).exists()]
        if existing:
            raise FileExistsError(
                f"{out} already contains {', '.join(existing)} not written by the demo; "
                f"choose an empty folder")
    out.mkdir(parents=True, exist_ok=True)
    marker.write_bytes(b"")
    log_path = out / "calls.jsonl"
    if log_path.exists():
        log_path.unlink()
    rng = random.Random(seed)

    registry = Registry([model for model, _ in JUDGES] + [GENERATOR_MODEL])
    task = Task(DEMO_TASK, bar=0.85, min_samples=50, expected_input_tokens=1000,
                expected_output_tokens=200, max_fallbacks=2, timeout_s=30.0)
    calibration_rows = _calibration_rows(rng)
    stats = calibrate_from_results(calibration_rows)
    stats.save(out / "stats.json")
    (out / "outcomes.jsonl").write_text(_outcome_lines(calibration_rows, task),
                                        encoding="utf-8")
    (out / "models.json").write_text(_registry_json(registry), encoding="utf-8")
    (out / "tasks.json").write_text(_tasks_json(task), encoding="utf-8")
    router = Router(registry, {task.name: task}, stats)

    clock = _SimulatedClock()
    state = {"primary": ""}
    provider = FakeProvider(_script(registry, rng, clock, state))
    monitor = Monitor(log_path)
    validate = json_validator("verdict")

    summary = {}
    for flavor in ("cost_effective", "cost_blind"):
        decision = router.select(task.name, flavor=flavor, generator_model=GENERATOR)
        state["primary"] = decision.primary
        counter = iter(range(1, CALLS_PER_FLAVOR + 1))
        executor = Executor(router, provider, monitor=monitor, clock=clock,
                            now=clock.timestamp,
                            id_factory=lambda f=flavor, c=counter: f"{f}-{next(c):04d}",
                            ledger=ledger)
        first = len(monitor.records)
        for item in range(CALLS_PER_FLAVOR):
            messages = [
                {"role": "system", "content": "Judge whether the answer is faithful "
                                              "to the source. Reply in JSON with a verdict."},
                {"role": "user", "content": f"Synthetic item {item}."},
            ]
            try:
                executor.call(task.name, messages, flavor=flavor, generator_model=GENERATOR,
                              tags={"suite": "demo", "dataset": "synthetic"},
                              validate=validate)
            except AllModelsFailed:
                pass
        records = _attempts(monitor.records[first:])
        finals = [r for r in records if r["final"]]
        summary[flavor] = {
            "primary": decision.primary,
            "fallbacks": list(decision.fallbacks),
            "calls": len(finals),
            "fallback_calls": sum(1 for r in finals if r["attempt"] > 0),
            "cost_usd": round(sum(r["cost_usd"] for r in records), 6),
        }
    # after every judge call, so their records and random draws are unchanged (v1.12)
    for flavor in summary:
        summary[flavor]["delegation"] = _hand_off(router, provider, monitor, clock, state,
                                                  validate, flavor, ledger)
    return summary


# v1.580 (DESIGN 11, row PROC1d): a recurring job routed between an agent route and a procedure
PROCEDURE_TASK = "demo_job_summary"
PROCEDURE_MODEL = "demo/atlas-mid"
PROCEDURE_JOBS = 40
PROCEDURE_CALLS = 20
PROCEDURE_TOOL_COST_USD = 0.00001
_TURN_OUTPUT_TOKENS = 20
_RESULT_TOKENS = 12
_SHAPE = "Write one line: "
_NOW = "2026-01-01T00:00:00.000Z"


def _job_amounts(i: int) -> List[int]:
    return [(31 * i + 17 * k) % 100 for k in range(30 + (7 * i) % 20)]


def _job_polls(i: int) -> int:
    return 2 + i % 4


def _payload(amounts: List[int]) -> str:
    return "\n".join(f"row {k}: amount {a}" for k, a in enumerate(amounts))


def _answer(i: int, amounts: List[int]) -> str:
    return f"job {i}: {len(amounts)} rows, total {sum(amounts)}"


def _job_messages(i: int) -> List[dict]:
    return [{"role": "user", "content": f"Run job {i} and report its row count and total."}]


def _job_number(messages: List[dict]) -> int:
    return int(messages[0]["content"].split()[2])


def _job_check(i: int) -> Callable[[str], bool]:
    expected = _answer(i, _job_amounts(i))
    return lambda text: text == expected


class _JobService:
    """Fictional jobs: done at their ``_job_polls``-th status poll; an early fetch is partial."""

    def __init__(self) -> None:
        self.polls: Dict[int, int] = {}

    def submit(self, i: int) -> int:
        self.polls[i] = 0
        return i

    def poll(self, i: int) -> bool:
        self.polls[i] += 1
        return self.polls[i] >= _job_polls(i)

    def fetch(self, i: int) -> str:
        amounts = _job_amounts(i)
        done = self.polls[i] >= _job_polls(i)
        return _payload(amounts if done else amounts[:len(amounts) // 2])


def _job_procedure(version: str, max_polls: Optional[int]) -> Procedure:
    """Submit, poll in code (at most ``max_polls`` times, or until done), fetch, count, shape."""
    service = _JobService()

    def fn(messages: List[dict], call: Callable[[List[dict]], str]) -> ProcedureResult:
        i = _job_number(messages)
        job = service.submit(i)
        polls, done = 0, False
        while not done and (max_polls is None or polls < max_polls):
            done = service.poll(job)
            polls += 1
        raw = service.fetch(job)
        amounts = [int(line.rsplit(" ", 1)[1]) for line in raw.split("\n")]
        tool_calls = polls + 2  # the submit, the polls and the fetch
        text = call([{"role": "user", "content": f"{_SHAPE}{_answer(i, amounts)}."}])
        return ProcedureResult(text, tool_calls=tool_calls,
                               tool_cost_usd=tool_calls * PROCEDURE_TOOL_COST_USD)

    return Procedure("job-summary", version, fn, max_model_calls=1, max_tool_calls=8,
                     model=PROCEDURE_MODEL)


def _agent_run(messages: List[dict]) -> Completion:
    """One agent run billed as its turns: submit, each poll, fetch, answer (DESIGN 11 v1.580)."""
    i = _job_number(messages)
    amounts, polls = _job_amounts(i), _job_polls(i)
    payload_tokens = -(-len(_payload(amounts)) // 4)
    context, input_tokens = estimate_prompt_tokens(messages), 0
    turns = polls + 3
    for turn in range(turns):
        input_tokens += context
        context += _TURN_OUTPUT_TOKENS
        if turn <= polls:  # the submit turn and each poll turn return a short result
            context += _RESULT_TOKENS
        elif turn == polls + 1:  # the fetch turn returns the raw payload
            context += payload_tokens
    rows = len(amounts) - (1 if i % 20 == 19 else 0)
    return Completion(f"job {i}: {rows} rows, total {sum(amounts)}", input_tokens,
                      _TURN_OUTPUT_TOKENS * turns)


def _job_script(messages: List[dict]) -> Completion:
    content = messages[0]["content"]
    if content.startswith(_SHAPE):
        return Completion(content[len(_SHAPE):-1], estimate_prompt_tokens(messages),
                          _TURN_OUTPUT_TOKENS)
    return _agent_run(messages)


def run_procedure_demo() -> dict:
    """Route a fictional submit, poll and fetch job between an agent route and a procedure.

    The agent route, ``demo/atlas-mid``, does the job by model turns, the raw rows in its
    context after the fetch; the procedures poll in code and send their one model call only
    what they counted. ``job-summary@1`` fetches before some jobs are done and ``job-summary@2``
    does not. Each route runs 40 jobs to calibrate; then three ``cost_effective`` decisions show
    an unmeasured procedure and one under the bar left out and the one that clears the bar
    routed, and 20 more jobs run through the executor with that procedure and without it.
    Returns ``{"task", "bar", "stages", "routed"}`` (DESIGN 11 v1.580); writes no file, draws no
    random number and reads no clock, so every run returns the same.
    """
    registry = Registry([model for model, _ in JUDGES if model.id == PROCEDURE_MODEL])
    model = registry.get(PROCEDURE_MODEL)
    task = Task(PROCEDURE_TASK, bar=0.8, min_samples=30, max_fallbacks=1)
    provider = FakeProvider({PROCEDURE_MODEL: _job_script})
    early, fixed = _job_procedure("1", 3), _job_procedure("2", None)

    rows: Dict[str, List[dict]] = {PROCEDURE_MODEL: []}
    for i in range(PROCEDURE_JOBS):
        completion = provider.complete(PROCEDURE_MODEL, _job_messages(i), task.timeout_s)
        rows[PROCEDURE_MODEL].append({
            "task": PROCEDURE_TASK, "model": PROCEDURE_MODEL,
            "correct": _job_check(i)(completion.text),
            "input_tokens": completion.input_tokens, "output_tokens": completion.output_tokens})
    for proc in (early, fixed):
        rows[proc.id] = []
        for i in range(PROCEDURE_JOBS):
            spent: List[float] = []

            def call(messages: List[dict]) -> str:
                completion = provider.complete(PROCEDURE_MODEL, messages, task.timeout_s)
                spent.append(model.cost(completion.input_tokens, completion.output_tokens))
                return completion.text

            run = proc.run(_job_messages(i), call)
            rows[proc.id].append({
                "task": PROCEDURE_TASK, "model": proc.id, "correct": _job_check(i)(run.output),
                "cost_usd": math.fsum(spent) + run.tool_cost_usd})

    def router(*routes: str) -> Router:
        stats = calibrate_from_results([row for route in routes for row in rows[route]])
        return Router(registry, {task.name: task}, stats)

    stages = []
    for stage, proc, routes in (("cold", fixed, (PROCEDURE_MODEL,)),
                                ("below_bar", early, (PROCEDURE_MODEL, early.id)),
                                ("admitted", fixed, (PROCEDURE_MODEL, early.id, fixed.id))):
        decision = router(*routes).select(PROCEDURE_TASK, flavor="cost_effective",
                                          procedures=[proc])
        reason = next(c.reason for c in decision.candidates if c.model_id == proc.id)
        stages.append({"stage": stage, "procedure": proc.id, "reason": reason,
                       "primary": decision.primary})

    admitted = router(PROCEDURE_MODEL, early.id, fixed.id)
    routed = {}
    for path, procedures in (("procedure", [fixed]), ("agent", [])):
        monitor = Monitor()
        counter = iter(range(1, PROCEDURE_CALLS + 1))
        executor = Executor(admitted, provider, monitor=monitor, clock=lambda: 0.0,
                            now=lambda: _NOW,
                            id_factory=lambda p=path, c=counter: f"{p}-{next(c):04d}")
        route = None
        for i in range(PROCEDURE_JOBS, PROCEDURE_JOBS + PROCEDURE_CALLS):
            try:
                decision = executor.call(PROCEDURE_TASK, _job_messages(i),
                                         flavor="cost_effective", validate=_job_check(i),
                                         procedures=procedures).decision
            except AllModelsFailed as exc:
                decision = exc.decision
            route = decision.primary if route is None else route
        row = report(monitor.records, by="task")[0]
        routed[path] = {
            "route": route, "calls": row["calls"], "fallback_calls": row["fallback_calls"],
            "failed_calls": row["failed_calls"],
            "cost_usd": round(sum(r["cost_usd"] for r in monitor.records), 6),
            "input_tokens": sum(r["input_tokens"] for r in monitor.records),
        }
    return {"task": PROCEDURE_TASK, "bar": task.bar, "stages": stages, "routed": routed}


# v1.585 (DESIGN 11, row SELF1d): a fine-tune its owner serves, priced from its hour
SELF_HOSTED_TASK = "demo_clause_review"
SELF_HOSTED_MODEL = "demo/birch-nano-ft"
SELF_HOSTED_ROW = {
    "id": SELF_HOSTED_MODEL, "base_model": "demo/birch-nano", "context_window": 32000,
    "pricing_basis": "self_hosted", "deployment": "self_hosted", "usd_per_hour": 2.0,
    "tokens_per_hour_in": 18000000, "tokens_per_hour_out": 1800000, "utilization": 0.5,
    "input_cost_share": 0.5,
}
SELF_HOSTED_IDLE_UTILIZATION = 0.02
SELF_HOSTED_ITEMS = 60
SELF_HOSTED_CALLS = 20
_SELF_HOSTED_LISTED = ("demo/atlas-mid", "demo/birch-nano")
_MISSES = {"demo/atlas-mid": (40, 38), "demo/birch-nano": (4, 3), SELF_HOSTED_MODEL: (10, 9)}


def _clause_messages(i: int) -> List[dict]:
    return [{"role": "user", "content": f"Review the tag given to clause {i}."}]


def _clause_gold(i: int) -> str:
    return "accept" if i % 3 else "reject"


def _clause_check(i: int) -> Callable[[str], bool]:
    gold = _clause_gold(i)
    return lambda text: text == gold


def _reviewer(model_id: str) -> Callable[[List[dict]], Completion]:
    """A model's fake answers: the gold one, but the other when ``i % every == miss``."""
    every, miss = _MISSES[model_id]

    def answer(messages: List[dict]) -> Completion:
        # the item number is the last word of _clause_messages's one message, before its period
        i = int(messages[0]["content"].rsplit(" ", 1)[1].rstrip("."))
        gold = _clause_gold(i)
        text = gold if i % every != miss else ("reject" if gold == "accept" else "accept")
        return Completion(text, 1000, 200)

    return answer


def _fine_tune(utilization: float) -> Model:
    """The model ``SELF_HOSTED_ROW`` gives at ``utilization``, as Registry.load reads the row."""
    row = SELF_HOSTED_ROW
    price_in, price_out = self_hosted_prices(row["usd_per_hour"], row["tokens_per_hour_in"],
                                             row["tokens_per_hour_out"], utilization,
                                             row["input_cost_share"])
    return Model(row["id"], "birch", price_in, price_out, row["context_window"],
                 pricing_basis=row["pricing_basis"], deployment=row["deployment"],
                 base_model=row["base_model"])


def run_self_hosted_demo() -> dict:
    """Route a fictional fine-tune that its owner serves against a list-priced model.

    ``demo/birch-nano-ft`` is a fine-tune of ``demo/birch-nano`` priced from 2 USD an hour of
    serving (``SELF_HOSTED_ROW``); ``demo/atlas-mid`` has list prices. Each model answers 60
    clause reviews to calibrate; then four ``cost_effective`` decisions show the fine-tune
    unmeasured and not routed, measured over the bar and the primary, the dearer route when
    the same hour is used a fiftieth of the time, and kept off its base's output, and 20 more
    reviews run through the executor with the fine-tune and without it, their spend split by
    ``pricing_basis``. Returns ``{"task", "bar", "row", "prices", "stages", "routed"}`` (DESIGN
    11 v1.585); writes no file, draws no random number and reads no clock, so every run returns
    the same.
    """
    listed = [model for model, _ in JUDGES if model.id in _SELF_HOSTED_LISTED]
    fine_tune = _fine_tune(SELF_HOSTED_ROW["utilization"])
    registry = Registry(listed + [fine_tune])
    task = Task(SELF_HOSTED_TASK, bar=0.75)
    provider = FakeProvider({model.id: _reviewer(model.id) for model in registry.models})

    rows: Dict[str, List[dict]] = {}
    for model in registry.models:
        rows[model.id] = []
        for i in range(SELF_HOSTED_ITEMS):
            completion = provider.complete(model.id, _clause_messages(i), task.timeout_s)
            rows[model.id].append({
                "task": SELF_HOSTED_TASK, "model": model.id,
                "correct": _clause_check(i)(completion.text),
                "input_tokens": completion.input_tokens,
                "output_tokens": completion.output_tokens})
    every = [model.id for model in registry.models]

    def router(models: Registry, measured: List[str]) -> Router:
        stats = calibrate_from_results([row for model_id in measured for row in rows[model_id]])
        return Router(models, {task.name: task}, stats)

    stages = []
    for stage, utilization, measured, generator in (
            ("cold", SELF_HOSTED_ROW["utilization"], every[:2], None),
            ("admitted", SELF_HOSTED_ROW["utilization"], every, None),
            ("idle", SELF_HOSTED_IDLE_UTILIZATION, every, None),
            ("generator_base", SELF_HOSTED_ROW["utilization"], every, "demo/birch-nano")):
        models = Registry(listed + [_fine_tune(utilization)])
        decision = router(models, measured).select(SELF_HOSTED_TASK, flavor="cost_effective",
                                                   generator_model=generator)
        candidate = next(c for c in decision.candidates if c.model_id == SELF_HOSTED_MODEL)
        stages.append({"stage": stage, "utilization": utilization, "reason": candidate.reason,
                       "list_cost": round(candidate.list_cost, 6), "primary": decision.primary})

    routed = {}
    for path, models in (("self_hosted", registry), ("list_only", Registry(listed))):
        monitor = Monitor()
        counter = iter(range(1, SELF_HOSTED_CALLS + 1))
        executor = Executor(router(models, every), provider, monitor=monitor,
                            clock=lambda: 0.0, now=lambda: _NOW,
                            id_factory=lambda p=path, c=counter: f"{p}-{next(c):04d}")
        route = None
        for i in range(SELF_HOSTED_ITEMS, SELF_HOSTED_ITEMS + SELF_HOSTED_CALLS):
            try:
                decision = executor.call(SELF_HOSTED_TASK, _clause_messages(i),
                                         flavor="cost_effective",
                                         validate=_clause_check(i)).decision
            except AllModelsFailed as exc:
                decision = exc.decision
            route = decision.primary if route is None else route
        row = report(monitor.records, by="task")[0]
        routed[path] = {
            "route": route, "calls": row["calls"], "fallback_calls": row["fallback_calls"],
            "failed_calls": row["failed_calls"],
            "cost_usd": round(sum(r["cost_usd"] for r in monitor.records), 6),
            "spend": [{"pricing_basis": group["group"], "calls": group["calls"],
                       "cost_usd": group["cost_usd"]}
                      for group in report(monitor.records, by="pricing_basis")],
        }
    return {"task": SELF_HOSTED_TASK, "bar": task.bar, "row": dict(SELF_HOSTED_ROW),
            "prices": [fine_tune.price_in, fine_tune.price_out], "stages": stages,
            "routed": routed}
