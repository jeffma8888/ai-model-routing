"""Route each repeated kind of model call to the cheapest model that clears a measured bar.

``cost_effective`` picks the cheapest passing model; ``cost_blind`` picks the
highest-quality passing model. Both share fallback, monitoring and cost
attribution.
"""

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

from .registry import Model, Registry  # noqa: E402
from .tasks import Task, load_tasks  # noqa: E402
from .stats import Stats, calibrate_from_results, wilson_lower_bound  # noqa: E402
from .priors import Priors  # noqa: E402
from .router import (  # noqa: E402
    BELOW_BAR, CONTEXT_TOO_SMALL, EXCLUDED_FAMILY, EXCLUDED_MODEL, GENERATOR,
    GENERATOR_FAMILY, INSUFFICIENT_SAMPLES, PASSES, Candidate, NoModelClearsBar,
    RouteDecision, Router,
)
from .providers import (  # noqa: E402
    Completion, FakeProvider, OpenAICompatibleProvider, Provider, ProviderError,
)
from .executor import AllModelsFailed, Attempt, CallResult, Executor, json_validator  # noqa: E402
from .monitor import Monitor, load_records, report  # noqa: E402
from .demo import run_demo  # noqa: E402
from .evaluate import Outcome, evaluate, load_outcomes, outcomes_from_rows, split_items  # noqa: E402
from .delegation import DelegationDecision  # noqa: E402

__version__ = "0.1.0"

__all__ = [
    "DATA_DIR", "Model", "Registry", "Task", "load_tasks", "Stats",
    "calibrate_from_results", "wilson_lower_bound", "Priors", "Candidate",
    "RouteDecision", "Router", "NoModelClearsBar", "EXCLUDED_MODEL", "EXCLUDED_FAMILY",
    "GENERATOR", "GENERATOR_FAMILY", "CONTEXT_TOO_SMALL", "INSUFFICIENT_SAMPLES",
    "BELOW_BAR", "PASSES", "Completion", "ProviderError", "Provider", "FakeProvider",
    "OpenAICompatibleProvider", "Attempt", "CallResult", "Executor", "AllModelsFailed",
    "json_validator", "Monitor", "load_records", "report", "run_demo", "main",
    "Outcome", "outcomes_from_rows", "load_outcomes", "split_items", "evaluate",
    "DelegationDecision",
]


def __getattr__(name):
    if name == "main":
        from .cli import main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
