"""Task definitions: the quality bar and routing constraints of one kind of call."""

from __future__ import annotations

import json
from dataclasses import dataclass, field, fields
from pathlib import Path
from typing import Dict, Mapping, Optional, Tuple, Union

PathLike = Union[str, Path]

ON_NO_MODEL_CHOICES = ("refuse", "best_available")
SLICE_KEYS = ("bar", "min_samples", "expected_input_tokens", "expected_output_tokens")


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
class Task:
    """A routing task.

    ``bar`` is the minimum acceptable success rate against the task's
    acceptance check (for a judge, agreement with gold labels), judged on
    the Wilson lower bound at ``confidence``. ``slices`` maps a slice name to
    that slice's own ``bar``, ``min_samples`` and token sizes, each one it does
    not give coming from the task (DESIGN 4.2 v1.511). Invalid values raise
    ``ValueError`` at construction.
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


_TASK_FIELDS = {f.name for f in fields(Task)}


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
        try:
            task = Task(**values)
        except TypeError as exc:
            raise ValueError(f"{path}: invalid task {row!r}: {exc}") from exc
        if task.name in tasks:
            raise ValueError(f"{path}: duplicate task name {task.name!r}")
        tasks[task.name] = task
    return tasks
