"""Measured quality: Wilson lower bounds and per (task, model) counts."""

from __future__ import annotations

import json
from math import sqrt
from pathlib import Path
from statistics import NormalDist
from typing import Dict, Iterable, Tuple, Union

PathLike = Union[str, Path]


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_counts(successes: int, trials: int) -> None:
    if successes < 0 or trials < 0 or successes > trials:
        raise ValueError(
            f"invalid counts: successes={successes}, trials={trials}")


def wilson_lower_bound(successes: int, trials: int, confidence: float = 0.95) -> float:
    """Return the lower end of the two-sided Wilson score interval.

    Returns 0.0 when ``trials`` is 0. Raises ``ValueError`` for negative
    counts or ``successes > trials``.
    """
    _check_counts(successes, trials)
    if trials == 0:
        return 0.0
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)
    n = trials
    p = successes / n
    lb = (p + z * z / (2 * n) - z * sqrt(p * (1 - p) / n + z * z / (4 * n * n))) / (1 + z * z / n)
    return max(0.0, lb)


class Stats:
    """In-memory map from ``(task, model_id)`` to ``(successes, trials)``."""

    def __init__(self) -> None:
        self._counts: Dict[Tuple[str, str], Tuple[int, int]] = {}

    def get(self, task: str, model_id: str) -> Tuple[int, int]:
        """Return ``(successes, trials)``, or ``(0, 0)`` when nothing is recorded."""
        return self._counts.get((task, model_id), (0, 0))

    def add(self, task: str, model_id: str, successes: int, trials: int) -> None:
        """Add these counts to the existing ones for ``(task, model_id)``."""
        _check_counts(successes, trials)
        s, t = self.get(task, model_id)
        self._counts[(task, model_id)] = (s + successes, t + trials)

    def merge(self, other: "Stats") -> "Stats":
        """Return a new Stats holding the summed counts of both operands."""
        merged = Stats()
        for source in (self, other):
            for (task, model_id), (s, t) in source._counts.items():
                merged.add(task, model_id, s, t)
        return merged

    def items(self):
        """Yield ``((task, model_id), (successes, trials))`` sorted by key."""
        return sorted(self._counts.items())

    @classmethod
    def load(cls, path: PathLike) -> "Stats":
        """Load stats from ``{"stats": [{"task", "model", "successes", "trials"}]}``."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("stats"), list):
            raise ValueError(f"{path}: expected an object with a 'stats' list")
        stats = cls()
        for row in raw["stats"]:
            if not isinstance(row, dict):
                raise ValueError(f"{path}: each stats row must be an object, got {row!r}")
            try:
                task, model_id = row["task"], row["model"]
                successes, trials = row["successes"], row["trials"]
            except KeyError as exc:
                raise ValueError(f"{path}: stats row missing {exc}: {row!r}") from None
            if not (_is_int(successes) and _is_int(trials)):
                raise ValueError(f"{path}: successes and trials must be integers: {row!r}")
            stats.add(str(task), str(model_id), successes, trials)
        return stats

    def save(self, path: PathLike) -> None:
        """Write stats as JSON with rows sorted by (task, model)."""
        rows = [{"task": task, "model": model_id, "successes": s, "trials": t}
                for (task, model_id), (s, t) in self.items()]
        Path(path).write_text(json.dumps({"stats": rows}, indent=2) + "\n", encoding="utf-8")


def calibrate_from_results(rows: Iterable[dict]) -> Stats:
    """Count one trial per row; a row is correct by ``correct`` or ``prediction == gold``.

    ``correct`` must be a real boolean. Every row is validated before the
    returned Stats exists, so a bad row anywhere raises ``ValueError``.
    """
    stats = Stats()
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"result row must be an object, got {row!r}")
        if "correct" in row:
            correct = row["correct"]
            if type(correct) is not bool:
                raise ValueError(f"'correct' must be true or false, got {correct!r}")
        elif "prediction" in row and "gold" in row:
            correct = row["prediction"] == row["gold"]
        else:
            raise ValueError(f"result row needs 'correct' or both 'prediction' and 'gold': {row!r}")
        try:
            task, model_id = row["task"], row["model"]
        except KeyError as exc:
            raise ValueError(f"result row missing {exc}: {row!r}") from None
        stats.add(task, model_id, 1 if correct else 0, 1)
    return stats
