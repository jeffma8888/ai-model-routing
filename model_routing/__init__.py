"""Route each repeated kind of model call to the cheapest model that clears a measured bar.

``cost_effective`` picks the cheapest passing model; ``cost_blind`` picks the
highest-quality passing model. Both share fallback, monitoring and cost
attribution.
"""

from pathlib import Path

DATA_DIR = Path(__file__).resolve().parent / "data"

from .registry import Model, PriceTier, Registry, Variant, self_hosted_prices  # noqa: E402
from .tasks import Cascade, Task, load_tasks  # noqa: E402
from .stats import Stats, calibrate_from_results, items_needed, wilson_lower_bound  # noqa: E402
from .priors import Priors  # noqa: E402
from .router import (  # noqa: E402
    BELOW_BAR, CASCADE_UNKNOWN_MODEL, CHEAPER_PER_SUCCESS, CONTEXT_TOO_SMALL, EXCLUDED_FAMILY, EXCLUDED_MODEL,
    GENERATOR, GENERATOR_FAMILY, INSUFFICIENT_SAMPLES, OUT_OF_SCOPE, PASSES, PROCEDURE_UNKNOWN_MODEL, Candidate,
    NoModelClearsBar,
    RouteDecision, Router,
)
from .providers import (  # noqa: E402
    Completion, FakeProvider, OpenAICompatibleProvider, Provider, ProviderError,
)
from .executor import (  # noqa: E402
    AllModelsFailed, Attempt, CallResult, Executor, estimate_prompt_tokens, json_validator,
)
from .monitor import Monitor, load_audits, load_records, report  # noqa: E402
from .demo import run_demo  # noqa: E402
from .evaluate import Outcome, evaluate, load_outcomes, outcomes_from_rows, split_items  # noqa: E402
from .delegation import DelegationDecision  # noqa: E402
from .delegation_eval import evaluate_delegation  # noqa: E402
from .procedures import Procedure, ProcedureLimitError, ProcedureResult, ProcedureRun  # noqa: E402
from .budget import Budget, BudgetExceeded, BudgetLedger, billing_bound, load_budgets  # noqa: E402

__version__ = "0.1.0"

__all__ = [
    "DATA_DIR", "Model", "PriceTier", "Registry", "Variant", "self_hosted_prices", "Task", "load_tasks", "Cascade", "Stats",
    "calibrate_from_results", "wilson_lower_bound", "items_needed", "Priors", "Candidate",
    "RouteDecision", "Router", "NoModelClearsBar", "EXCLUDED_MODEL", "EXCLUDED_FAMILY",
    "GENERATOR", "GENERATOR_FAMILY", "CONTEXT_TOO_SMALL", "INSUFFICIENT_SAMPLES",
    "BELOW_BAR", "PASSES", "CASCADE_UNKNOWN_MODEL", "CHEAPER_PER_SUCCESS", "PROCEDURE_UNKNOWN_MODEL", "OUT_OF_SCOPE", "Completion", "ProviderError", "Provider", "FakeProvider",
    "OpenAICompatibleProvider", "Attempt", "CallResult", "Executor", "AllModelsFailed",
    "json_validator", "estimate_prompt_tokens", "Monitor", "load_records", "load_audits", "report",
    "run_demo",
    "main", "Outcome", "outcomes_from_rows", "load_outcomes", "split_items", "evaluate",
    "DelegationDecision", "evaluate_delegation",
    "Procedure", "ProcedureResult", "ProcedureRun", "ProcedureLimitError",
    "Budget", "BudgetLedger", "BudgetExceeded", "load_budgets", "billing_bound",
]


def __getattr__(name):
    if name == "main":
        from .cli import main
        return main
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
