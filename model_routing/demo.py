"""An offline, deterministic demonstration with clearly fictional models."""

from __future__ import annotations

import json
import random
from pathlib import Path
from typing import Dict, List, Union

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
OUTPUTS = ("calls.jsonl", "stats.json")

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


def run_demo(out_dir: Union[str, Path], seed: int = 7) -> dict:
    """Run the offline demo and write ``calls.jsonl`` and ``stats.json`` to ``out_dir``.

    Four fictional judges in two families are calibrated on a 300-item
    synthetic labeled set, routed in both flavors, and each flavor runs 200
    judge calls with a simulated outage on a share of the primary's calls.
    Returns ``{flavor: {primary, fallbacks, calls, fallback_calls, cost_usd}}``;
    the result is deterministic for a given seed.

    An empty marker file ``.model-routing-demo`` records that the folder holds
    demo output. If ``calls.jsonl`` or ``stats.json`` already exist without
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
    stats = calibrate_from_results(_calibration_rows(rng))
    stats.save(out / "stats.json")
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
    return summary
