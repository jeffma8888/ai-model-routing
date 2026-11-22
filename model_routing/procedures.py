"""A recurring job's fixed steps as code with declared bounds (DESIGN 4.5 v1.576, row PROC1a).

A procedure runs polling, batching and result shaping in code instead of model turns. It is a
bounded callable, not an agent runtime: it declares at most how many model calls and tool calls
one run makes, and its route ID names its version and the one model route it calls, so a new
version or another model is another route with its own stats.
"""

from __future__ import annotations

import math
import re
from dataclasses import dataclass, field
from typing import Callable, List, Optional

_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")  # the variant-name pattern (DESIGN 4.1)


def _is_count(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 0


def _model_ok(model: object) -> bool:
    """A procedure's model: a non-empty str without '+' or whitespace, never a 'proc:' ID."""
    return (isinstance(model, str) and bool(model) and "+" not in model
            and not any(ch.isspace() for ch in model) and not model.startswith("proc:"))


def is_procedure_id(value: object) -> bool:
    """True when ``value`` is a route ID a :class:`Procedure` can have (DESIGN 4.3 v1.577)."""
    if not isinstance(value, str) or not value.startswith("proc:"):
        return False
    head, plus, model = value[len("proc:"):].partition("+")
    name, at, version = head.partition("@")
    return (bool(at) and bool(_NAME.fullmatch(name)) and bool(_NAME.fullmatch(version))
            and (not plus or _model_ok(model)))


class ProcedureLimitError(Exception):
    """A procedure's run went past one of its declared bounds, or used a dead call handle."""


@dataclass(frozen=True)
class ProcedureResult:
    """What a procedure's ``fn`` returns: its output and the tool calls it made and their cost."""

    output: str
    tool_calls: int = 0
    tool_cost_usd: float = 0.0

    def __post_init__(self) -> None:
        if not isinstance(self.output, str):
            raise ValueError(f"output must be a str, got {type(self.output).__name__}")
        if not _is_count(self.tool_calls):
            raise ValueError(f"tool_calls must be an integer >= 0, got {self.tool_calls!r}")
        cost = self.tool_cost_usd
        if isinstance(cost, bool) or not isinstance(cost, (int, float)) \
                or not math.isfinite(cost) or cost < 0:
            raise ValueError(f"tool_cost_usd must be a finite number >= 0, got {cost!r}")
        object.__setattr__(self, "tool_cost_usd", float(cost))


@dataclass(frozen=True)
class ProcedureRun:
    """One run of a procedure: its route ID, its output and what it used."""

    route: str
    output: str
    model_calls: int
    tool_calls: int
    tool_cost_usd: float


@dataclass(frozen=True)
class Procedure:
    """``Procedure(name, version, fn, *, max_model_calls, max_tool_calls, model=None)``.

    ``fn(input, handle)`` returns a :class:`ProcedureResult`; ``handle(messages)`` makes one
    model call of the route ``model`` names. ``model`` is None exactly when
    ``max_model_calls`` is 0. Invalid values raise ``ValueError`` (DESIGN 4.5).
    """

    name: str
    version: str
    fn: Callable
    max_model_calls: int = field(kw_only=True)
    max_tool_calls: int = field(kw_only=True)
    model: Optional[str] = field(default=None, kw_only=True)

    def __post_init__(self) -> None:
        for label in ("name", "version"):
            value = getattr(self, label)
            if not isinstance(value, str) or not _NAME.fullmatch(value):
                raise ValueError(f"procedure {label} must match {_NAME.pattern}, got {value!r}")
        if not callable(self.fn):
            raise ValueError(f"procedure fn must be callable, got {type(self.fn).__name__}")
        for label in ("max_model_calls", "max_tool_calls"):
            value = getattr(self, label)
            if not _is_count(value):
                raise ValueError(f"{label} must be an integer >= 0, got {value!r}")
        model = self.model
        if model is not None and not _model_ok(model):
            raise ValueError(f"procedure model must be None or a registry route ID without '+', "
                             f"whitespace or a 'proc:' start, got {model!r}")
        if (model is None) != (self.max_model_calls == 0):
            raise ValueError("a procedure names a model exactly when max_model_calls is above 0, "
                             f"got model {model!r} and max_model_calls {self.max_model_calls}")

    @property
    def id(self) -> str:
        """The route ID: ``proc:<name>@<version>``, then ``+<model>`` when it names one."""
        base = f"proc:{self.name}@{self.version}"
        return base if self.model is None else f"{base}+{self.model}"

    def run(self, value: object, call: Callable[[List[dict]], str]) -> ProcedureRun:
        """Run ``fn`` once on ``value`` with a call handle bounded by ``max_model_calls``.

        The handle refuses a call over the bound, or any call once the run has ended, with
        :class:`ProcedureLimitError` before ``call`` is reached; exceptions of ``fn`` and
        ``call`` propagate unchanged (DESIGN 4.5 v1.576). A handle is for one thread.
        """
        route = self.id
        state = {"calls": 0, "open": True}

        def handle(messages: List[dict]) -> str:
            if not state["open"]:
                raise ProcedureLimitError(f"{route}: call handle used after its run ended")
            if state["calls"] >= self.max_model_calls:
                raise ProcedureLimitError(f"{route}: model call {state['calls'] + 1} is over "
                                          f"max_model_calls {self.max_model_calls}")
            state["calls"] += 1
            return call(messages)

        try:
            result = self.fn(value, handle)
        finally:
            state["open"] = False
        if not isinstance(result, ProcedureResult):
            raise ValueError(f"{route}: fn must return a ProcedureResult, "
                             f"got {type(result).__name__}")
        if result.tool_calls > self.max_tool_calls:
            raise ProcedureLimitError(f"{route}: {result.tool_calls} tool calls are over "
                                      f"max_tool_calls {self.max_tool_calls}")
        return ProcedureRun(route, result.output, state["calls"], result.tool_calls,
                            result.tool_cost_usd)
