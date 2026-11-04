"""An offline, deterministic demonstration with clearly fictional models."""

from __future__ import annotations

import json
import random
from dataclasses import fields
from pathlib import Path
from typing import Dict, List, Union

from .delegation import DELEGATE
from .executor import AllModelsFailed, Executor, json_validator
from .monitor import Monitor
from .providers import Completion, FakeProvider, ProviderError
from .registry import Model, Registry
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
              clock: _SimulatedClock, state: Dict[str, str], validate, flavor: str) -> dict:
    """One inline-or-sub-agent decision, its hand-off run when it delegates (DESIGN 11 v1.12)."""
    decision = router.decide_delegation(
        DEMO_TASK, DELEGATION_PARENT, flavor, context_tokens=DELEGATION_CONTEXT_TOKENS,
        brief_tokens=400, result_tokens=60, generator_model=GENERATOR)
    first = len(monitor.records)
    if decision.mode == DELEGATE:
        state["primary"] = decision.route.primary
        executor = Executor(router, provider, monitor=monitor, clock=clock,
                            now=clock.timestamp, id_factory=lambda: f"{flavor}-delegated-0001")
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
    records = monitor.records[first:]
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


def run_demo(out_dir: Union[str, Path], seed: int = 7) -> dict:
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
    """
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
                            id_factory=lambda f=flavor, c=counter: f"{f}-{next(c):04d}")
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
        records = monitor.records[first:]
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
                                                  validate, flavor)
    return summary
