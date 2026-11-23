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
_FIELDS = ("name", "limit_usd", "mode", "window", "task", "tags", "strict")
OUTPUT_MAXIMUM_KEYS = ("max_tokens", "max_completion_tokens", "max_output_tokens")
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
    or month (4.6 v1.596). A ``strict`` budget, ``refuse`` or ``downgrade``, checks and holds each
    call's :func:`billing_bound` and refuses a call with none (4.6 v1.597).
    """

    name: str
    limit_usd: float
    mode: str
    window: str = "total"
    task: Optional[str] = None
    tags: Mapping[str, str] = field(default_factory=dict)
    strict: bool = False

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
        if not isinstance(self.strict, bool):
            raise ValueError(f"budget {self.name!r} strict must be a bool, got {self.strict!r}")
        if self.strict and self.mode == "warn":
            raise ValueError(f"budget {self.name!r} is strict, so its mode must be refuse or "
                             "downgrade: a warn budget refuses nothing")

    def applies(self, task: str, tags: Mapping[str, str]) -> bool:
        """True when a call of ``task`` with ``tags`` is in this budget's scope."""
        if self.task is not None and task != self.task:
            return False
        return all(key in tags and tags[key] == value for key, value in self.tags.items())


class BudgetExceeded(Exception):
    """A ``refuse`` or ``downgrade`` budget would be passed by the next provider call, not made.

    ``attempts`` and ``decision`` are the call's attempts before the refusal and its route,
    set by the executor (DESIGN 7 v1.595); ``()`` and None as ``reserve`` raises it.
    ``unbounded`` is True when a strict budget refused a call with no billing bound (4.6 v1.597).
    ``window`` is the label of the window its check read, None for a ``total`` budget (v1.598).
    """

    def __init__(self, budget: Budget, spent_usd: float, held_usd: float,
                 estimate_usd: float, model: Optional[str], unbounded: bool = False,
                 window: Optional[str] = None):
        if unbounded:
            message = (f"budget {budget.name!r} ({budget.limit_usd!r} USD) is strict and refuses "
                       f"a call of {model!r}, whose billing has no bound: {spent_usd!r} spent, "
                       f"{held_usd!r} held by calls in flight")
        else:
            message = (f"budget {budget.name!r} ({budget.limit_usd!r} USD) refuses a call of "
                       f"{model!r}: {spent_usd!r} spent, {held_usd!r} held by calls in flight, "
                       f"{estimate_usd!r} estimated for this one")
        super().__init__(message)
        self.unbounded = unbounded
        self.budget = budget
        self.spent_usd = spent_usd
        self.held_usd = held_usd
        self.estimate_usd = estimate_usd
        self.model = model
        self.window = window
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
        self._holds: Dict[int, Tuple[Tuple[_Slot, float], ...]] = {}  # each slot and its amount
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
        return math.fsum(amount for pairs in self._holds.values()
                         for held, amount in pairs if held == slot)

    def reserve(self, task: str, tags: Mapping[str, str], estimate_usd: float,
                model: Optional[str] = None, at: Optional[str] = None,
                bound_usd: Optional[float] = None) -> _Hold:
        """Hold ``estimate_usd`` on every budget that applies, or raise :class:`BudgetExceeded`.

        ``refuse`` budgets are checked first, then ``downgrade`` ones, each in the ledger's order.
        A strict budget checks and holds ``bound_usd`` instead, refusing when it is None (v1.597).
        """
        estimate = _amount(estimate_usd, "estimate_usd")
        bound = None if bound_usd is None else _amount(bound_usd, "bound_usd")
        with self._lock:
            scope = [budget for budget in self._budgets if budget.applies(task, tags)]
            slots = self._slots(scope, at)
            for mode in ("refuse", "downgrade"):
                for budget, slot in zip(scope, slots):
                    if budget.mode != mode:
                        continue
                    spent, held = self._spent.get(slot, 0.0), self._held(slot)
                    if budget.strict and bound is None:
                        raise BudgetExceeded(budget, spent, held, estimate, model, unbounded=True,
                                             window=slot[1])
                    amount = bound if budget.strict else estimate
                    if spent + held + amount > budget.limit_usd:
                        raise BudgetExceeded(budget, spent, held, amount, model, window=slot[1])
            key = next(self._keys)
            self._holds[key] = tuple((slot, bound if budget.strict else estimate)
                                     for budget, slot in zip(scope, slots))
            return _Hold(key)

    def settle(self, hold: _Hold, cost_usd: float) -> Tuple[dict, ...]:
        """Release ``hold`` and add ``cost_usd`` to each budget it was held on, in its window;
        the warn events the add appended, each a new dict (4.6 v1.598)."""
        cost = _amount(cost_usd, "cost_usd")
        with self._lock:
            return self._add(tuple(slot for slot, _ in self._release(hold)), cost)

    def settle_unpriced(self, hold: _Hold) -> Tuple[dict, ...]:
        """Release ``hold`` of a call whose cost is not known: a strict budget adds the bound it
        held and any other 0.0, in the hold's window (4.6 v1.597); its warn events (v1.598)."""
        with self._lock:
            events: Tuple[dict, ...] = ()
            for slot, amount in self._release(hold):
                events += self._add((slot,), amount if self._by_name[slot[0]].strict else 0.0)
            return events

    def _release(self, hold: _Hold) -> Tuple[Tuple[_Slot, float], ...]:
        entry = self._holds.pop(hold.key, None) if isinstance(hold, _Hold) else None
        if entry is None:
            raise ValueError("this hold is settled already or was never reserved here")
        return entry

    def charge(self, task: str, tags: Mapping[str, str], cost_usd: float,
               at: Optional[str] = None) -> Tuple[dict, ...]:
        """Add a cost spent without a hold to each budget that applies, in the window that holds
        ``at``; never refuses. Returns the warn events the add appended (v1.598)."""
        cost = _amount(cost_usd, "cost_usd")
        with self._lock:
            return self._add(self._slots([b for b in self._budgets if b.applies(task, tags)], at),
                             cost)

    def _add(self, slots: Tuple[_Slot, ...], cost: float) -> Tuple[dict, ...]:
        start = len(self._events)
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
        return tuple(dict(event) for event in self._events[start:])


def billing_bound(model) -> Optional[float]:
    """The most one call of ``model`` can cost by ``Model.cost``, or None with no output maximum.

    The largest of the ``max_tokens``, ``max_completion_tokens`` and ``max_output_tokens`` its
    ``provider_options`` hold, each an int >= 1, caps the output, and the context window less it
    the input; the bound is the largest cost at that output over the input and each price tier
    threshold under it, the input all uncached, all cached reads or all cache writes (4.6 v1.597).
    """
    options = model.provider_options
    caps = [options[key] for key in OUTPUT_MAXIMUM_KEYS if key in options]
    if not caps or not all(type(cap) is int and cap >= 1 for cap in caps):
        return None
    out = max(caps)
    top = max(model.context_window - out, 0)
    inputs = sorted({top, *(tier.above_input_tokens for tier in model.price_tiers
                            if tier.above_input_tokens < top)})
    return max(cost for size in inputs for cost in (
        model.cost(size, out), model.cost(size, out, cached_input_tokens=size),
        model.cost(size, out, cache_write_tokens=size)))


def load_budgets(path: Union[str, Path]) -> Tuple[Budget, ...]:
    """Read ``{"budgets": [{field: value, ...}, ...]}`` into budgets (DESIGN 4.6 v1.595 and v1.597)."""
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
