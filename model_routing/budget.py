"""In-process budgets: a USD limit per scope, held before each provider call (DESIGN 4.6)."""

from __future__ import annotations

import itertools
import json
import math
import threading
from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Tuple, Union

BUDGET_MODES = ("warn", "refuse", "downgrade")
BUDGET_WINDOWS = ("total", "day", "month")
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


def _instant(at) -> datetime:
    """``at``, an ISO 8601 timestamp, as an aware UTC datetime; no offset reads as UTC (4.6)."""
    if not isinstance(at, str):
        raise ValueError(f"at must be None or an ISO 8601 timestamp str, got {at!r}")
    text = at[:-1] + "+00:00" if at.endswith("Z") else at
    try:
        stamp = datetime.fromisoformat(text)
        if stamp.tzinfo is None:
            return stamp.replace(tzinfo=timezone.utc)
        return stamp.astimezone(timezone.utc)
    except (ValueError, OverflowError):
        raise ValueError(f"at must be None or an ISO 8601 timestamp str, got {at!r}") from None


@dataclass(frozen=True)
class Budget:
    """A spend limit in USD on the calls of one scope (DESIGN 4.6 v1.595).

    A call is in scope when ``task`` is None or its task, and its tags hold every pair of
    ``tags``. ``warn`` notes each first crossing of half, 80 percent and all of the limit;
    ``refuse`` raises :class:`BudgetExceeded` before a provider call whose estimate would take
    the spend and the holds of calls in flight over the limit; ``downgrade`` raises it too, and
    the executor moves the call to the next route entry that clears the bar (7 v1.596).
    ``window`` is ``total``, the ledger's whole life, ``day`` or ``month``, a UTC calendar day
    or month (4.6 v1.596).
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
            raise ValueError(f"budget {self.name!r} window must be one of {BUDGET_WINDOWS}, "
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
    """A ``refuse`` or ``downgrade`` budget would be passed by the next provider call, not made.

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


_Slot = Tuple[str, Optional[str]]  # a budget's name and its window's label, None for total


class BudgetLedger:
    """Each budget's settled spend per window and the holds of calls in flight, under one lock.

    A ``day`` or ``month`` budget reads its window from the ``at`` its methods take, an ISO 8601
    timestamp (the current UTC time when None); a ``total`` budget has one window (4.6 v1.596).
    """

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
        self._spent: Dict[_Slot, float] = {}
        self._holds: Dict[int, Tuple[Tuple[_Slot, ...], float]] = {}
        self._keys = itertools.count()
        self._fired: Dict[_Slot, set] = {}
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

    @staticmethod
    def _slots(budgets: Sequence[Budget], at) -> Tuple[_Slot, ...]:
        """Each budget's name and the label of its window that holds ``at`` (4.6 v1.596)."""
        instant = None if at is None else _instant(at)
        slots = []
        for budget in budgets:
            if budget.window == "total":
                slots.append((budget.name, None))
                continue
            if instant is None:
                instant = datetime.now(timezone.utc)
            label = f"{instant.year:04d}-{instant.month:02d}"
            if budget.window == "day":
                label += f"-{instant.day:02d}"
            slots.append((budget.name, label))
        return tuple(slots)

    def spent_usd(self, name: str, at: Optional[str] = None) -> float:
        """The settled spend of ``name``'s window that holds ``at``."""
        self._known(name)
        [slot] = self._slots([self._by_name[name]], at)
        with self._lock:
            return self._spent.get(slot, 0.0)

    def held_usd(self, name: str, at: Optional[str] = None) -> float:
        """The live holds of ``name``'s window that holds ``at``."""
        self._known(name)
        [slot] = self._slots([self._by_name[name]], at)
        with self._lock:
            return self._held(slot)

    def _held(self, slot: _Slot) -> float:
        return math.fsum(amount for slots, amount in self._holds.values() if slot in slots)

    def reserve(self, task: str, tags: Mapping[str, str], estimate_usd: float,
                model: Optional[str] = None, at: Optional[str] = None) -> _Hold:
        """Hold ``estimate_usd`` on every budget that applies, or raise :class:`BudgetExceeded`.

        ``refuse`` budgets are checked first, then ``downgrade`` ones, each in the ledger's order.
        """
        estimate = _amount(estimate_usd, "estimate_usd")
        with self._lock:
            scope = [budget for budget in self._budgets if budget.applies(task, tags)]
            slots = self._slots(scope, at)
            for mode in ("refuse", "downgrade"):
                for budget, slot in zip(scope, slots):
                    if budget.mode != mode:
                        continue
                    spent, held = self._spent.get(slot, 0.0), self._held(slot)
                    if spent + held + estimate > budget.limit_usd:
                        raise BudgetExceeded(budget, spent, held, estimate, model)
            key = next(self._keys)
            self._holds[key] = (slots, estimate)
            return _Hold(key)

    def settle(self, hold: _Hold, cost_usd: float) -> None:
        """Release ``hold`` and add ``cost_usd`` to each budget it was held on, in its window."""
        cost = _amount(cost_usd, "cost_usd")
        with self._lock:
            entry = self._holds.pop(hold.key, None) if isinstance(hold, _Hold) else None
            if entry is None:
                raise ValueError("this hold is settled already or was never reserved here")
            self._add(entry[0], cost)

    def charge(self, task: str, tags: Mapping[str, str], cost_usd: float,
               at: Optional[str] = None) -> None:
        """Add a cost spent without a hold to each budget that applies, in the window that holds
        ``at``; never refuses."""
        cost = _amount(cost_usd, "cost_usd")
        with self._lock:
            self._add(self._slots([b for b in self._budgets if b.applies(task, tags)], at), cost)

    def _add(self, slots: Tuple[_Slot, ...], cost: float) -> None:
        for slot in slots:
            spent = self._spent.get(slot, 0.0) + cost
            self._spent[slot] = spent
            name, label = slot
            budget = self._by_name[name]
            if budget.mode != "warn":
                continue
            fired = self._fired.setdefault(slot, set())
            for share in WARN_SHARES:
                if share not in fired and spent >= share * budget.limit_usd:
                    fired.add(share)
                    event = {"budget": name, "share": share, "spent_usd": spent,
                             "limit_usd": budget.limit_usd}
                    if label is not None:  # 4.6 v1.596: a day or month budget's window
                        event["window"] = label
                    self._events.append(event)


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
