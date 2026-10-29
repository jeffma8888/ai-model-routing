"""Task definitions: the quality bar and routing constraints of one kind of call."""

from __future__ import annotations

import json
from dataclasses import dataclass, fields
from pathlib import Path
from typing import Dict, Optional, Tuple, Union

PathLike = Union[str, Path]

ON_NO_MODEL_CHOICES = ("refuse", "best_available")


@dataclass(frozen=True)
class Task:
    """A routing task.

    ``bar`` is the minimum acceptable agreement with gold labels, judged on
    the Wilson lower bound at ``confidence``. Invalid values raise
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
