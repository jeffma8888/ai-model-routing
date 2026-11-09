"""Measured quality: Wilson lower bounds, the items a bar needs, and per (task, model) counts
and token totals."""

from __future__ import annotations

import json
from fractions import Fraction
from math import floor, isfinite, sqrt
from pathlib import Path
from statistics import NormalDist
from typing import Dict, Iterable, Optional, Tuple, Union

PathLike = Union[str, Path]

_TOKEN_KEYS = ("input_tokens", "output_tokens", "token_trials")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_counts(successes: int, trials: int) -> None:
    if successes < 0 or trials < 0 or successes > trials:
        raise ValueError(
            f"invalid counts: successes={successes}, trials={trials}")


def _check_tokens(trials: int, input_tokens: Optional[int], output_tokens: Optional[int],
                  token_trials: Optional[int]) -> int:
    """Validate optional token totals over ``token_trials`` of ``trials``; return that count.

    Returns 0 when no totals are given (DESIGN 4.3).
    """
    if (input_tokens is None) != (output_tokens is None):
        raise ValueError("input_tokens and output_tokens must be given together")
    if input_tokens is None:
        if token_trials is not None:
            raise ValueError("token_trials needs input_tokens and output_tokens")
        return 0
    for name, value in (("input_tokens", input_tokens), ("output_tokens", output_tokens)):
        if not _is_int(value) or value < 0:
            raise ValueError(f"{name} must be an integer >= 0, got {value!r}")
    n = trials if token_trials is None else token_trials
    if not _is_int(n) or not 1 <= n <= trials:
        raise ValueError(f"token_trials must be an integer from 1 to trials={trials}, got {n!r}")
    return n


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


def _check_rate(name: str, value: object) -> None:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not isfinite(value) \
            or not 0.0 <= value <= 1.0:
        raise ValueError(f"{name} must be a finite number in [0, 1], got {value!r}")


def _planned_successes(success: float, items: int) -> int:
    """The successes of ``items`` items at rate ``success``: the floor of the exact decimal (4.3)."""
    return floor(Fraction(repr(float(success))) * items)


def items_needed(success: float, bar: float, confidence: float = 0.95,
                 max_items: int = 10_000) -> Optional[int]:
    """Return the labelled items a model at rate ``success`` needs to clear ``bar``, or None.

    The smallest n in 1..max_items from which every count up to ``max_items`` gives a
    Wilson lower bound at or above ``bar``, with the successes at a count rounded down
    (DESIGN 4.3). ``None`` when ``max_items`` items do not clear. Raises ``ValueError``
    for an invalid argument.
    """
    _check_rate("success", success)
    _check_rate("bar", bar)
    if isinstance(confidence, bool) or not isinstance(confidence, (int, float)) \
            or not isfinite(confidence) or not 0.0 < confidence < 1.0:
        raise ValueError(f"confidence must be a finite number in (0, 1), got {confidence!r}")
    if not _is_int(max_items) or max_items < 1:
        raise ValueError(f"max_items must be an integer >= 1, got {max_items!r}")
    needed = None
    for n in range(max_items, 0, -1):
        if wilson_lower_bound(_planned_successes(success, n), n, confidence) < bar:
            break
        needed = n
    return needed


class Stats:
    """In-memory map from ``(task, model_id)`` to ``(successes, trials)``.

    A key may also hold measured token totals: the summed input and output tokens of
    ``token_trials`` of its trials. The router prices a model that has them at its own
    mean tokens per call on the task (DESIGN 4.3, 5.2).
    """

    def __init__(self) -> None:
        self._counts: Dict[Tuple[str, str], Tuple[int, int]] = {}
        self._tokens: Dict[Tuple[str, str], Tuple[int, int, int]] = {}

    def get(self, task: str, model_id: str) -> Tuple[int, int]:
        """Return ``(successes, trials)``, or ``(0, 0)`` when nothing is recorded."""
        return self._counts.get((task, model_id), (0, 0))

    def add(self, task: str, model_id: str, successes: int, trials: int, *,
            input_tokens: Optional[int] = None, output_tokens: Optional[int] = None,
            token_trials: Optional[int] = None) -> None:
        """Add these counts, and any token totals, to the existing ones for the key.

        ``input_tokens`` and ``output_tokens`` go together and are totals over
        ``token_trials`` of these ``trials`` (default: all of them). Raises
        ``ValueError`` and adds nothing when any argument is invalid.
        """
        _check_counts(successes, trials)
        n = _check_tokens(trials, input_tokens, output_tokens, token_trials)
        key = (task, model_id)
        s, t = self.get(task, model_id)
        self._counts[key] = (s + successes, t + trials)
        if n:
            i, o, k = self.tokens(task, model_id)
            self._tokens[key] = (i + input_tokens, o + output_tokens, k + n)

    def tokens(self, task: str, model_id: str) -> Tuple[int, int, int]:
        """Return ``(input_tokens, output_tokens, token_trials)``, ``(0, 0, 0)`` when none."""
        return self._tokens.get((task, model_id), (0, 0, 0))

    def mean_tokens(self, task: str, model_id: str) -> Optional[Tuple[int, int]]:
        """Return the mean input and output tokens per recorded call, each rounded up.

        Integer arithmetic, never a float; ``None`` when no token counts are recorded.
        """
        i, o, k = self.tokens(task, model_id)
        if k == 0:
            return None
        return -(-i // k), -(-o // k)

    def merge(self, other: "Stats") -> "Stats":
        """Return a new Stats holding the summed counts and token totals of both operands."""
        merged = Stats()
        for source in (self, other):
            for key, (s, t) in source._counts.items():
                merged.add(*key, s, t)
            for key, (i, o, k) in source._tokens.items():
                a, b, n = merged._tokens.get(key, (0, 0, 0))
                merged._tokens[key] = (a + i, b + o, n + k)
        return merged

    def items(self):
        """Yield ``((task, model_id), (successes, trials))`` sorted by key."""
        return sorted(self._counts.items())

    @classmethod
    def load(cls, path: PathLike) -> "Stats":
        """Load stats from ``{"stats": [{"task", "model", "successes", "trials"}]}``.

        A row may also carry ``input_tokens``, ``output_tokens`` and ``token_trials``,
        all three or none.
        """
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
            present = [k for k in _TOKEN_KEYS if k in row]
            if present and len(present) != len(_TOKEN_KEYS):
                raise ValueError(f"{path}: a stats row carries all of {', '.join(_TOKEN_KEYS)} "
                                 f"or none: {row!r}")
            if present and not all(_is_int(row[k]) for k in _TOKEN_KEYS):
                raise ValueError(f"{path}: token keys must be integers: {row!r}")
            tokens = {k: row[k] for k in present}
            try:
                stats.add(str(task), str(model_id), successes, trials, **tokens)
            except ValueError as exc:
                raise ValueError(f"{path}: {exc}: {row!r}") from None
        return stats

    def save(self, path: PathLike) -> None:
        """Write stats as JSON with rows sorted by (task, model)."""
        rows = []
        for (task, model_id), (s, t) in self.items():
            row = {"task": task, "model": model_id, "successes": s, "trials": t}
            i, o, k = self.tokens(task, model_id)
            if k:
                row.update(input_tokens=i, output_tokens=o, token_trials=k)
            rows.append(row)
        Path(path).write_text(json.dumps({"stats": rows}, indent=2) + "\n", encoding="utf-8")


def calibrate_from_results(rows: Iterable[dict]) -> Stats:
    """Count one trial per row; a row is correct by ``correct`` or ``prediction == gold``.

    ``correct`` must be a real boolean. A row may carry ``input_tokens`` and
    ``output_tokens``, both or neither, and then adds one token trial with those counts.
    Every row is validated before the returned Stats exists, so a bad row anywhere
    raises ``ValueError``.
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
        has_in, has_out = "input_tokens" in row, "output_tokens" in row
        if has_in != has_out:
            raise ValueError(f"result row needs input_tokens and output_tokens or neither: {row!r}")
        tokens = {}
        if has_in:
            tokens = {"input_tokens": row["input_tokens"], "output_tokens": row["output_tokens"]}
            if not all(_is_int(v) and v >= 0 for v in tokens.values()):
                raise ValueError(f"token counts must be integers >= 0: {row!r}")
        stats.add(task, model_id, 1 if correct else 0, 1, **tokens)
    return stats
