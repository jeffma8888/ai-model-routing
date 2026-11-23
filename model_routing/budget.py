"""In-process budgets: a USD limit per scope, held before each provider call (DESIGN 4.6)."""

from __future__ import annotations

import itertools
import json
import math
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

BUDGET_MODES = ("warn", "refuse")
BUDGET_WINDOWS = ("total",)
WARN_SHARES = (0.5, 0.8, 1.0)
_FIELDS = ("name", "limit_usd", "mode", "window", "task", "tags")
_REQUIRED = ("name", "limit_usd", "mode")


def _amount(value, what: str) -> float:
    """``value`` as a float when it is an int or float, not a bool, finite and >= 0."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{what} must be a finite number >= 0, got {value!r}")
    try:
        number = float(value)
    except OverflowError:
        raise ValueError(f"{what} must be a finite number >= 0, got {value!r}") from None
    if not math.isfinite(number) or number < 0:
        raise ValueError(f"{what} must be a finite number >= 0, got {value!r}")
    return number


@dataclass(frozen=True)
class Budget:
    """A spend limit in USD on the calls of one scope (DESIGN 4.6 v1.595).

    A call is in scope when ``task`` is None or its task, and its tags hold every pair of
    ``tags``. ``warn`` notes each first crossing of half, 80 percent and all of the limit;
    ``refuse`` raises :class:`BudgetExceeded` before a provider call whose estimate would take
    the spend and the holds of calls in flight over the limit. ``window`` is ``total``, the
    ledger's whole life, the one window of this version.
    """

    name: str
    limit_usd: float
    mode: str
    window: str = "total"
    task: Optional[str] = None
    tags: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.name, str) or not self.name:
            raise ValueError(f"budget name must be a non-empty str, got {self.name!r}")
        limit = _amount(self.limit_usd, f"budget {self.name!r} limit_usd")
        if limit <= 0:
            raise ValueError(f"budget {self.name!r} limit_usd must be above 0, "
                             f"got {self.limit_usd!r}")
        object.__setattr__(self, "limit_usd", limit)
        if self.mode not in BUDGET_MODES:
            raise ValueError(f"budget {self.name!r} mode must be one of {BUDGET_MODES}, "
                             f"got {self.mode!r}")
        if self.window not in BUDGET_WINDOWS:
            raise ValueError(f"budget {self.name!r} window must be 'total' in this version, "
                             f"got {self.window!r}")
        if self.task is not None and (not isinstance(self.task, str) or not self.task):
            raise ValueError(f"budget {self.name!r} task must be None or a non-empty str, "
                             f"got {self.task!r}")
        if not isinstance(self.tags, Mapping) or not all(
                isinstance(key, str) and isinstance(value, str)
                for key, value in self.tags.items()):
            raise ValueError(f"budget {self.name!r} tags must map str to str, "
                             f"got {self.tags!r}")
        object.__setattr__(self, "tags", dict(self.tags))

    def applies(self, task: str, tags: Mapping[str, str]) -> bool:
        """True when a call of ``task`` with ``tags`` is in this budget's scope."""
        if self.task is not None and task != self.task:
            return False
        return all(key in tags and tags[key] == value for key, value in self.tags.items())


class BudgetExceeded(Exception):
    """A ``refuse`` budget would be passed by the next provider call, which was not made.

    ``attempts`` and ``decision`` are the call's attempts before the refusal and its route,
    set by the executor (DESIGN 7 v1.595); ``()`` and None as ``reserve`` raises it.
    """

    def __init__(self, budget: Budget, spent_usd: float, held_usd: float,
                 estimate_usd: float, model: Optional[str]):
        super().__init__(
            f"budget {budget.name!r} ({budget.limit_usd!r} USD) refuses a call of {model!r}: "
            f"{spent_usd!r} spent, {held_usd!r} held by calls in flight, "
            f"{estimate_usd!r} estimated for this one")
        self.budget = budget
        self.spent_usd = spent_usd
        self.held_usd = held_usd
        self.estimate_usd = estimate_usd
        self.model = model
        self.attempts: tuple = ()
        self.decision = None


@dataclass(frozen=True)
class _Hold:
    key: int


class BudgetLedger:
    """Each budget's settled spend and the holds of calls in flight, under one lock (4.6)."""

    def __init__(self, budgets: Sequence[Budget] = ()):
        if not isinstance(budgets, (list, tuple)):
            raise ValueError(f"budgets must be a list or tuple of Budget, "
                             f"got {type(budgets).__name__}")
        names = set()
        for budget in budgets:
            if not isinstance(budget, Budget):
                raise ValueError(f"budgets must hold Budget objects, got {budget!r}")
            if budget.name in names:
                raise ValueError(f"budget name {budget.name!r} is repeated")
            names.add(budget.name)
        self._budgets: Tuple[Budget, ...] = tuple(budgets)
        self._by_name = {budget.name: budget for budget in self._budgets}
        self._lock = threading.Lock()
        self._spent: Dict[str, float] = {name: 0.0 for name in self._by_name}
        self._holds: Dict[int, Tuple[Tuple[str, ...], float]] = {}
        self._keys = itertools.count()
        self._fired: Dict[str, set] = {name: set() for name in self._by_name}
        self._events: List[dict] = []

    @property
    def budgets(self) -> Tuple[Budget, ...]:
        return self._budgets

    @property
    def events(self) -> Tuple[dict, ...]:
        with self._lock:
            return tuple(dict(event) for event in self._events)

    def _known(self, name: str) -> None:
        if name not in self._by_name:
            raise ValueError(f"no budget named {name!r}")

    def spent_usd(self, name: str) -> float:
        self._known(name)
        with self._lock:
            return self._spent[name]

    def held_usd(self, name: str) -> float:
        self._known(name)
        with self._lock:
            return self._held(name)

    def _held(self, name: str) -> float:
        return math.fsum(amount for names, amount in self._holds.values() if name in names)

    def reserve(self, task: str, tags: Mapping[str, str], estimate_usd: float,
                model: Optional[str] = None) -> _Hold:
        """Hold ``estimate_usd`` on every budget that applies, or raise :class:`BudgetExceeded`."""
        estimate = _amount(estimate_usd, "estimate_usd")
        with self._lock:
            scope = [budget for budget in self._budgets if budget.applies(task, tags)]
            for budget in scope:
                if budget.mode != "refuse":
                    continue
                spent, held = self._spent[budget.name], self._held(budget.name)
                if spent + held + estimate > budget.limit_usd:
                    raise BudgetExceeded(budget, spent, held, estimate, model)
            key = next(self._keys)
            self._holds[key] = (tuple(budget.name for budget in scope), estimate)
            return _Hold(key)

    def settle(self, hold: _Hold, cost_usd: float) -> None:
        """Release ``hold`` and add ``cost_usd`` to each budget it was held on."""
        cost = _amount(cost_usd, "cost_usd")
        with self._lock:
            entry = self._holds.pop(hold.key, None) if isinstance(hold, _Hold) else None
            if entry is None:
                raise ValueError("this hold is settled already or was never reserved here")
            self._add(entry[0], cost)

    def charge(self, task: str, tags: Mapping[str, str], cost_usd: float) -> None:
        """Add a cost spent without a hold to each budget that applies; never refuses."""
        cost = _amount(cost_usd, "cost_usd")
        with self._lock:
            self._add(tuple(b.name for b in self._budgets if b.applies(task, tags)), cost)

    def _add(self, names: Tuple[str, ...], cost: float) -> None:
        for name in names:
            spent = self._spent[name] + cost
            self._spent[name] = spent
            budget = self._by_name[name]
            if budget.mode != "warn":
                continue
            for share in WARN_SHARES:
                if share not in self._fired[name] and spent >= share * budget.limit_usd:
                    self._fired[name].add(share)
                    self._events.append({"budget": name, "share": share, "spent_usd": spent,
                                         "limit_usd": budget.limit_usd})


def load_budgets(path: Union[str, Path]) -> Tuple[Budget, ...]:
    """Read ``{"budgets": [{field: value, ...}, ...]}`` into budgets (DESIGN 4.6 v1.595)."""
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict) or not isinstance(data.get("budgets"), list):
        raise ValueError(f"{path}: expected an object with a 'budgets' list")
    budgets = []
    for row in data["budgets"]:
        if not isinstance(row, dict):
            raise ValueError(f"{path}: each budget must be an object, got {row!r}")
        unknown = sorted(set(row) - set(_FIELDS))
        missing = [name for name in _REQUIRED if name not in row]
        if unknown or missing:
            raise ValueError(f"{path}: budget {row.get('name')!r} has unknown keys {unknown} "
                             f"or lacks {missing}")
        budgets.append(Budget(**row))
    BudgetLedger(budgets)  # a repeated name raises ValueError
    return tuple(budgets)
