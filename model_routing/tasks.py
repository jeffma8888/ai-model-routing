"""Task definitions: the quality bar and routing constraints of one kind of call."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple, Union

PathLike = Union[str, Path]

ON_NO_MODEL_CHOICES = ("refuse", "best_available")
FAILURE_POLICIES = ("none", "retry_same")
LATENCY_UNKNOWN_CHOICES = ("allow", "deny")  # DESIGN 4.2 v1.628
SLICE_KEYS = ("bar", "min_samples", "expected_input_tokens", "expected_output_tokens")
CASCADE_KEYS = ("cheap", "strong", "signal")
_SIGNAL = re.compile(r"[a-z0-9][a-z0-9._-]*")


def _is_bar_ms(value) -> bool:
    """A latency bar (DESIGN 4.2 v1.628): a finite int or float above 0 that is not a bool."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        value = float(value)
    except OverflowError:  # an int too large for a float
        return False
    return math.isfinite(value) and value > 0


def is_slice_name(value) -> bool:
    """A slice name (DESIGN 4.2 v1.511): a non-empty str that holds no '@'."""
    return isinstance(value, str) and value != "" and "@" not in value


def _check_slice(task_name: str, name, values) -> Dict[str, object]:
    if not is_slice_name(name):
        raise ValueError(f"task {task_name!r}: slice name must be a non-empty string "
                         f"without '@', got {name!r}")
    if not isinstance(values, Mapping):
        raise ValueError(f"task {task_name!r}: slice {name!r} must be a mapping")
    for key, value in values.items():
        if key not in SLICE_KEYS:
            raise ValueError(f"task {task_name!r}: slice {name!r} has unknown key {key!r}")
        if isinstance(value, bool):
            ok = False
        elif key == "bar":
            ok = isinstance(value, (int, float)) and 0 <= value <= 1
        elif key == "min_samples":
            ok = isinstance(value, int) and value >= 1
        else:
            ok = isinstance(value, int) and value >= 0
        if not ok:
            raise ValueError(f"task {task_name!r}: slice {name!r} has invalid {key} {value!r}")
    return dict(values)


@dataclass(frozen=True)
class Cascade:
    """A cheap model, a signal the caller computes on its result, and a strong model.

    The call starts on ``cheap`` and is handed up to ``strong`` when the signal fires. A
    cascade is one routing candidate named by its ``id``, with calibration of its own
    (DESIGN 7 v1.532). Invalid fields raise ``ValueError`` at construction.
    """

    cheap: str
    strong: str
    signal: str

    def __post_init__(self) -> None:
        for name in CASCADE_KEYS:
            value = getattr(self, name)
            if not isinstance(value, str) or value == "":
                raise ValueError(f"cascade {name} must be a non-empty string, got {value!r}")
        for name in ("cheap", "strong"):
            value = getattr(self, name)
            if ">" in value or "@" in value:
                raise ValueError(f"cascade {name} model ID must not contain '>' or '@', "
                                 f"got {value!r}")
        if self.cheap == self.strong:
            raise ValueError(f"cascade cheap and strong must differ, both are {self.cheap!r}")
        if _SIGNAL.fullmatch(self.signal) is None:
            raise ValueError(f"cascade signal must match [a-z0-9][a-z0-9._-]*, "
                             f"got {self.signal!r}")

    @property
    def id(self) -> str:
        """``<cheap>><strong>@<signal>``, the cascade's model ID in stats and decisions."""
        return f"{self.cheap}>{self.strong}@{self.signal}"


def parse_cascade_id(value) -> Optional[Cascade]:
    """The ``Cascade`` whose ``id`` is ``value``, or ``None`` when it names none (DESIGN 7)."""
    if not isinstance(value, str) or value.count(">") != 1:
        return None
    cheap, rest = value.split(">")
    if rest.count("@") != 1:
        return None
    strong, signal = rest.split("@")
    try:
        return Cascade(cheap, strong, signal)
    except ValueError:
        return None


@dataclass(frozen=True)
class Task:
    """A routing task.

    ``bar`` is the minimum acceptable success rate against the task's
    acceptance check (for a judge, agreement with gold labels), judged on
    the Wilson lower bound at ``confidence``. ``slices`` maps a slice name to
    that slice's own ``bar``, ``min_samples`` and token sizes, each one it does
    not give coming from the task (DESIGN 4.2 v1.511). ``cascades`` holds the task's
    cascades, stored as a tuple with no two of one ``id`` (DESIGN 7 v1.532).
    ``failure_policy`` says what the caller does when a call's result fails the check:
    ``"none"`` or ``"retry_same"``, which ranks the routes by expected cost per success
    (DESIGN 4.2 and 5.3 v1.567). ``shadow_rate`` is the share of the task's calls also sent to
    a shadow route, ``shadow_route`` that route's model ID or None for the default
    (DESIGN 4.2 and 7 v1.607). ``max_p95_ms`` is the highest 95th-percentile time in milliseconds a
    route may take on the task's calls, None for no bar, and ``latency_unknown`` says whether a route
    whose time is unknown is ``"allow"``-ed or ``"deny"``-ed under it (DESIGN 4.2 and 5.2 v1.628).
    ``min_self_consistency`` is the lowest share of a route's rerun items every rerun graded alike that
    the route may have, None for no minimum (DESIGN 4.2 and 5.2 v1.668). ``min_delegation_follow`` is the
    lowest share of the task's advised hand-offs, per parent, its agent should take, under which
    ``delegation_follow`` flags a row; it routes nothing (DESIGN 4.2 and 8.3 v1.688). ``max_delegation_depth``
    is the deepest a sub-agent doing the task's work may sit in a tree of hand-offs, the root at 0, None for no
    cap (DESIGN 4.2 and 13.5 v1.691).
    Invalid values raise ``ValueError`` at construction.
    """

    name: str
    bar: float
    min_samples: int = 30
    confidence: float = 0.95
    independent_of_generator: bool = True
    exclude_families: Tuple[str, ...] = ()
    expected_input_tokens: int = 1000
    expected_output_tokens: int = 200
    on_no_model: str = "refuse"
    max_fallbacks: int = 2
    prior_category: Optional[str] = None
    timeout_s: float = 60.0
    fallback_below_bar: bool = False
    slices: Mapping[str, Mapping[str, object]] = field(default_factory=dict, hash=False)
    cascades: Tuple[Cascade, ...] = ()
    failure_policy: str = "none"
    shadow_rate: float = 0.0
    shadow_route: Optional[str] = None
    max_p95_ms: Optional[float] = None
    latency_unknown: str = "allow"
    min_self_consistency: Optional[float] = None
    min_delegation_follow: Optional[float] = None
    max_delegation_depth: Optional[int] = None

    def __post_init__(self) -> None:
        if not isinstance(self.exclude_families, tuple):
            object.__setattr__(self, "exclude_families", tuple(self.exclude_families))
        try:
            if not 0.0 <= self.bar <= 1.0:
                raise ValueError(f"task {self.name!r}: bar must be in [0, 1], got {self.bar}")
            if self.min_samples < 1:
                raise ValueError(f"task {self.name!r}: min_samples must be >= 1")
            if not 0.0 < self.confidence < 1.0:
                raise ValueError(f"task {self.name!r}: confidence must be in (0, 1)")
            if self.expected_input_tokens < 0 or self.expected_output_tokens < 0:
                raise ValueError(f"task {self.name!r}: token counts must be >= 0")
            if self.max_fallbacks < 0:
                raise ValueError(f"task {self.name!r}: max_fallbacks must be >= 0")
        except TypeError as exc:
            raise ValueError(f"task {self.name!r}: {exc}") from exc
        if self.on_no_model not in ON_NO_MODEL_CHOICES:
            raise ValueError(
                f"task {self.name!r}: on_no_model must be one of {ON_NO_MODEL_CHOICES}")
        if type(self.fallback_below_bar) is not bool:
            raise ValueError(f"task {self.name!r}: fallback_below_bar must be a bool, "
                             f"got {self.fallback_below_bar!r}")
        if not isinstance(self.slices, Mapping):
            raise ValueError(f"task {self.name!r}: slices must be a mapping")
        if self.slices and "@" in self.name:
            raise ValueError(f"task {self.name!r}: a task whose name holds '@' has no slices")
        object.__setattr__(self, "slices", {name: _check_slice(self.name, name, values)
                                            for name, values in self.slices.items()})
        try:
            cascades = tuple(self.cascades)
        except TypeError:
            raise ValueError(f"task {self.name!r}: cascades must be an iterable of Cascade, "
                             f"got {self.cascades!r}") from None
        ids = set()
        for cascade in cascades:
            if not isinstance(cascade, Cascade):
                raise ValueError(f"task {self.name!r}: each cascade must be a Cascade, "
                                 f"got {cascade!r}")
            if cascade.id in ids:
                raise ValueError(f"task {self.name!r}: duplicate cascade {cascade.id!r}")
            ids.add(cascade.id)
        object.__setattr__(self, "cascades", cascades)
        if not isinstance(self.failure_policy, str) or self.failure_policy not in FAILURE_POLICIES:
            raise ValueError(f"task {self.name!r}: failure_policy must be one of "
                             f"{FAILURE_POLICIES}, got {self.failure_policy!r}")
        rate = self.shadow_rate  # DESIGN 4.2 v1.607
        if isinstance(rate, bool) or not isinstance(rate, (int, float)) \
                or not 0.0 <= rate <= 1.0:  # NaN and the infinities fail the range (iter-456 nit 1)
            raise ValueError(f"task {self.name!r}: shadow_rate must be a finite number in "
                             f"[0, 1] that is not a bool, got {rate!r}")
        if self.shadow_route is not None \
                and (not isinstance(self.shadow_route, str) or not self.shadow_route):
            raise ValueError(f"task {self.name!r}: shadow_route must be None or a non-empty "
                             f"str, got {self.shadow_route!r}")
        if self.max_p95_ms is not None and not _is_bar_ms(self.max_p95_ms):  # DESIGN 4.2 v1.628
            raise ValueError(f"task {self.name!r}: max_p95_ms must be None or a finite number above 0 "
                             f"that is not a bool, got {self.max_p95_ms!r}")
        if not isinstance(self.latency_unknown, str) or self.latency_unknown not in LATENCY_UNKNOWN_CHOICES:
            raise ValueError(f"task {self.name!r}: latency_unknown must be one of "
                             f"{LATENCY_UNKNOWN_CHOICES}, got {self.latency_unknown!r}")
        least = self.min_self_consistency  # DESIGN 4.2 v1.668
        if least is not None and (isinstance(least, bool) or not isinstance(least, (int, float))
                                  or not 0.0 <= least <= 1.0):  # NaN and the infinities fail the range
            raise ValueError(f"task {self.name!r}: min_self_consistency must be None or a finite number in "
                             f"[0, 1] that is not a bool, got {least!r}")
        follow = self.min_delegation_follow  # DESIGN 4.2 v1.688
        if follow is not None and (isinstance(follow, bool) or not isinstance(follow, (int, float))
                                   or not 0.0 <= follow <= 1.0):  # NaN and the infinities fail the range
            raise ValueError(f"task {self.name!r}: min_delegation_follow must be None or a finite number in "
                             f"[0, 1] that is not a bool, got {follow!r}")
        cap = self.max_delegation_depth  # DESIGN 4.2 v1.691
        if cap is not None and (isinstance(cap, bool) or not isinstance(cap, int) or cap < 0):
            raise ValueError(f"task {self.name!r}: max_delegation_depth must be None or an int >= 0 "
                             f"that is not a bool, got {cap!r}")


_TASK_FIELDS = {f.name for f in fields(Task)}


def _load_cascades(path: PathLike, value) -> Tuple[Cascade, ...]:
    """A task row's ``cascades``: a JSON list of objects with exactly the three keys."""
    if not isinstance(value, list):
        raise ValueError(f"{path}: 'cascades' must be a list of objects, got {value!r}")
    cascades = []
    for obj in value:
        if not isinstance(obj, dict) or sorted(obj) != sorted(CASCADE_KEYS):
            raise ValueError(f"{path}: each cascade must be an object with exactly the keys "
                             f"{', '.join(CASCADE_KEYS)}, got {obj!r}")
        try:
            cascade = Cascade(**obj)
        except ValueError as exc:
            raise ValueError(f"{path}: {exc}") from None
        if any(c.id == cascade.id for c in cascades):
            raise ValueError(f"{path}: duplicate cascade {cascade.id!r}")
        cascades.append(cascade)
    return tuple(cascades)


def load_tasks(path: PathLike) -> Dict[str, Task]:
    """Load ``{"tasks": [...]}`` from JSON into a dict keyed by task name."""
    raw = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(raw, dict) or not isinstance(raw.get("tasks"), list):
        raise ValueError(f"{path}: expected an object with a 'tasks' list")
    tasks: Dict[str, Task] = {}
    for row in raw["tasks"]:
        if not isinstance(row, dict):
            raise ValueError(f"{path}: each task must be an object")
        unknown = set(row) - _TASK_FIELDS
        if unknown:
            raise ValueError(f"{path}: unknown task fields {sorted(unknown)}")
        values = {k: tuple(v) if isinstance(v, list) else v for k, v in row.items()}
        if "cascades" in row:
            values["cascades"] = _load_cascades(path, row["cascades"])
        try:
            task = Task(**values)
        except TypeError as exc:
            raise ValueError(f"{path}: invalid task {row!r}: {exc}") from exc
        if task.name in tasks:
            raise ValueError(f"{path}: duplicate task name {task.name!r}")
        tasks[task.name] = task
    return tasks
