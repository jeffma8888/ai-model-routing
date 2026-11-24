"""Measured quality: Wilson lower bounds, the items a bar needs, and per (task, model) counts,
token totals, cache totals and trial times."""

from __future__ import annotations

import json
from fractions import Fraction
from math import ceil, floor, isfinite, sqrt
from pathlib import Path
from statistics import NormalDist
from typing import Dict, Iterable, List, Optional, Sequence, Tuple, Union

from .procedures import is_procedure_id
from .tasks import is_slice_name, parse_cascade_id

PathLike = Union[str, Path]

_TOKEN_KEYS = ("input_tokens", "output_tokens", "token_trials")
_CACHE_PAIRS = (("cached_input_tokens", "cached_trials"),
                ("cache_write_tokens", "cache_write_trials"))
_OUTCOME_KEYS = ("task", "model", "item")  # DESIGN 4.3 v1.602, as the outcome matrix (12.1)
_HEX = frozenset("0123456789abcdef")


def _is_int(value: object) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _check_counts(successes: int, trials: int) -> None:
    if successes < 0 or trials < 0 or successes > trials:
        raise ValueError(
            f"invalid counts: successes={successes}, trials={trials}")


def _is_procedure_key(model_id: object) -> bool:
    return isinstance(model_id, str) and model_id.startswith("proc:")


def _is_cascade_key(model_id: object) -> bool:
    """A key holding '>' is a cascade's, unless it is a procedure's (DESIGN 4.3 v1.577)."""
    return isinstance(model_id, str) and ">" in model_id and not _is_procedure_key(model_id)


def _is_cost(value: object) -> bool:
    """A finite number >= 0 that a float can hold, never a bool (DESIGN 4.3 v1.577)."""
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        return False
    try:
        value = float(value)
    except OverflowError:  # an int too large for a float (review iter-424 should-fix 1)
        return False
    return isfinite(value) and value >= 0


def _check_cost(model_id: object, trials: int, cost_usd: object,
                has_tokens: bool) -> Optional[float]:
    """Validate ``cost_usd`` for this key: required for a procedure key, refused for any other."""
    if not _is_procedure_key(model_id):
        if cost_usd is not None:
            raise ValueError(f"cost_usd is only for a procedure key, got model {model_id!r}")
        return None
    if not is_procedure_id(model_id):
        raise ValueError(f"model {model_id!r} starts with 'proc:' but is no valid procedure id")
    if has_tokens:
        raise ValueError(f"a procedure key holds no token totals: {model_id!r}")
    if not _is_cost(cost_usd):
        raise ValueError(f"cost_usd must be a finite number >= 0 on procedure {model_id!r}, "
                         f"got {cost_usd!r}")
    if trials == 0 and cost_usd != 0:
        raise ValueError(f"cost_usd must be 0 with 0 trials on procedure {model_id!r}, "
                         f"got {cost_usd!r}")
    return float(cost_usd)


def _check_escalated(model_id: object, trials: int, escalated: Optional[int],
                     has_tokens: bool) -> Optional[int]:
    """Validate ``escalated`` for this key: a count for a cascade, ``None`` for a model (DESIGN 7)."""
    if not _is_cascade_key(model_id):
        if escalated is not None:
            raise ValueError(f"escalated is only for a cascade key, got model {model_id!r}")
        return None
    if parse_cascade_id(model_id) is None:
        raise ValueError(f"model {model_id!r} holds '>' but is no valid cascade id")
    if has_tokens:
        raise ValueError(f"a cascade key holds no token totals: {model_id!r}")
    if not _is_int(escalated) or not 0 <= escalated <= trials:
        raise ValueError(f"escalated must be an integer from 0 to trials={trials} on cascade "
                         f"{model_id!r}, got {escalated!r}")
    return escalated


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


def _check_cache(n: int, input_tokens: Optional[int], cached: Optional[int],
                 cached_trials: Optional[int], write: Optional[int],
                 write_trials: Optional[int]) -> Tuple[int, int, int, int]:
    """Validate the optional cache totals of one ``add``; return them with their trial counts.

    Each count is a total over its own trials, from 1 to this call's ``n`` token trials and
    defaulting to it, and the counts given sum to at most ``input_tokens``, since a call's
    cached reads and cache writes are input tokens of it (DESIGN 4.3 v1.588). Zeros when
    neither count is given.
    """
    out = []
    for name, count, trials_name, trials in (
            ("cached_input_tokens", cached, "cached_trials", cached_trials),
            ("cache_write_tokens", write, "cache_write_trials", write_trials)):
        if count is None:
            if trials is not None:
                raise ValueError(f"{trials_name} needs {name}")
            out += [0, 0]
            continue
        if n == 0:
            raise ValueError(f"{name} needs input_tokens and output_tokens")
        if not _is_int(count) or count < 0:
            raise ValueError(f"{name} must be an integer >= 0, got {count!r}")
        k = n if trials is None else trials
        if not _is_int(k) or not 1 <= k <= n:
            raise ValueError(f"{trials_name} must be an integer from 1 to token_trials={n}, "
                             f"got {k!r}")
        out += [count, k]
    if out[0] + out[2] > (input_tokens or 0):
        raise ValueError(f"cached_input_tokens {out[0]} plus cache_write_tokens {out[2]} is over "
                         f"input_tokens {input_tokens!r}, which counts every input token")
    return out[0], out[1], out[2], out[3]


def _check_latencies(trials: int, latencies_ms: object) -> Optional[Tuple[float, ...]]:
    """Validate ``latencies_ms``: ``None``, or 1 to ``trials`` times, each as ``cost_usd`` is
    checked; return them as floats (DESIGN 4.3 v1.626)."""
    if latencies_ms is None:
        return None
    if not isinstance(latencies_ms, (list, tuple)):
        raise ValueError(f"latencies_ms must be a list or tuple of times, got {latencies_ms!r}")
    if not 1 <= len(latencies_ms) <= trials:
        raise ValueError(f"latencies_ms must hold 1 to trials={trials} times, "
                         f"got {len(latencies_ms)}")
    for value in latencies_ms:
        if not _is_cost(value):
            raise ValueError(f"latencies_ms values must be finite numbers >= 0, got {value!r}")
    return tuple(float(value) for value in latencies_ms)


def wilson_lower_bound(successes: int, trials: int, confidence: float = 0.95) -> float:
    """Return the lower end of the two-sided Wilson score interval.

    Returns 0.0 when ``trials`` is 0, and exactly 0.0 when ``successes`` is 0, where the
    formula is 0 but floating point can leave a residue that differs by platform (DESIGN 4.3
    v1.568). Raises ``ValueError`` for negative counts or ``successes > trials``.
    """
    _check_counts(successes, trials)
    if trials == 0:
        return 0.0
    z = NormalDist().inv_cdf(1 - (1 - confidence) / 2)  # first, so a bad confidence still raises
    if successes == 0:  # the formula's value for z >= 0, with no floating-point residue
        return 0.0
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
    mean tokens per call on the task (DESIGN 4.3, 5.2). A cascade key (its ``id`` holds
    ``>``) holds no token totals but an escalation count, the trials on which its cheap
    model handed the call up (DESIGN 7 v1.532). A procedure key (its ``id`` starts with
    ``proc:``) holds no token totals but the summed cost of its trials (DESIGN 4.3 v1.577).
    Any key may hold the time in milliseconds of each timed trial (DESIGN 4.3 v1.626).
    """

    def __init__(self) -> None:
        self._counts: Dict[Tuple[str, str], Tuple[int, int]] = {}
        self._tokens: Dict[Tuple[str, str], Tuple[int, int, int]] = {}
        self._escalated: Dict[Tuple[str, str], int] = {}
        self._cost: Dict[Tuple[str, str], float] = {}
        self._cache: Dict[Tuple[str, str], Tuple[int, int, int, int]] = {}
        self._latency: Dict[Tuple[str, str], List[float]] = {}

    def get(self, task: str, model_id: str) -> Tuple[int, int]:
        """Return ``(successes, trials)``, or ``(0, 0)`` when nothing is recorded."""
        return self._counts.get((task, model_id), (0, 0))

    def add(self, task: str, model_id: str, successes: int, trials: int, *,
            input_tokens: Optional[int] = None, output_tokens: Optional[int] = None,
            token_trials: Optional[int] = None, escalated: Optional[int] = None,
            cost_usd: Optional[float] = None, cached_input_tokens: Optional[int] = None,
            cached_trials: Optional[int] = None, cache_write_tokens: Optional[int] = None,
            cache_write_trials: Optional[int] = None,
            latencies_ms: Optional[Sequence[float]] = None) -> None:
        """Add these counts, and any token totals, to the existing ones for the key.

        ``input_tokens`` and ``output_tokens`` go together and are totals over
        ``token_trials`` of these ``trials`` (default: all of them). ``escalated``, how many
        of these trials escalated, is required for a cascade key and refused for any other;
        ``cost_usd``, these trials' summed cost, likewise for a procedure key (DESIGN 4.3
        v1.577). ``cached_input_tokens`` and ``cache_write_tokens``, the cached reads and the
        cache writes of these calls, each need the token totals and are totals over their own
        trials, ``cached_trials`` and ``cache_write_trials`` of these token trials (DESIGN 4.3
        v1.588). ``latencies_ms`` is 1 to ``trials`` times in milliseconds, one per timed trial,
        on any key (DESIGN 4.3 v1.626). Raises ``ValueError`` and adds nothing when any
        argument is invalid.
        """
        _check_counts(successes, trials)
        n = _check_tokens(trials, input_tokens, output_tokens, token_trials)
        e = _check_escalated(model_id, trials, escalated, input_tokens is not None)
        c = _check_cost(model_id, trials, cost_usd, input_tokens is not None)
        cache = _check_cache(n, input_tokens, cached_input_tokens, cached_trials,
                             cache_write_tokens, cache_write_trials)
        times = _check_latencies(trials, latencies_ms)
        key = (task, model_id)
        if c is not None and not isfinite(self._cost.get(key, 0.0) + c):  # review iter-424 must-fix 1
            raise ValueError(f"cost_usd {c!r} would take the summed cost of {model_id!r} on "
                             f"{task!r} past the largest float")
        s, t = self.get(task, model_id)
        self._counts[key] = (s + successes, t + trials)
        if e is not None:
            self._escalated[key] = self._escalated.get(key, 0) + e
        if c is not None:
            self._cost[key] = self._cost.get(key, 0.0) + c
        if n:
            i, o, k = self.tokens(task, model_id)
            self._tokens[key] = (i + input_tokens, o + output_tokens, k + n)
        if any(cache):  # a count given has at least one trial, so only no count is all zeros
            held = self.cache_tokens(task, model_id)
            self._cache[key] = (held[0] + cache[0], held[1] + cache[1],
                                held[2] + cache[2], held[3] + cache[3])
        if times is not None:
            self._latency.setdefault(key, []).extend(times)

    def tokens(self, task: str, model_id: str) -> Tuple[int, int, int]:
        """Return ``(input_tokens, output_tokens, token_trials)``, ``(0, 0, 0)`` when none."""
        return self._tokens.get((task, model_id), (0, 0, 0))

    def cache_tokens(self, task: str, model_id: str) -> Tuple[int, int, int, int]:
        """Return ``(cached_input_tokens, cached_trials, cache_write_tokens,
        cache_write_trials)``, ``(0, 0, 0, 0)`` when none are recorded (DESIGN 4.3 v1.588)."""
        return self._cache.get((task, model_id), (0, 0, 0, 0))

    def mean_cache_tokens(self, task: str, model_id: str) -> Tuple[Optional[int], Optional[int]]:
        """Return the mean cached reads and cache writes per reporting call, each rounded down.

        Integer arithmetic; ``None`` for a count no trial reported, so it is unknown and never
        0. Rounded down a cached-read mean never over-states the cached share; a write mean
        rounded down moves under one token per call to the input price (DESIGN 4.3 v1.588).
        """
        cached, cached_trials, write, write_trials = self.cache_tokens(task, model_id)
        return (cached // cached_trials if cached_trials else None,
                write // write_trials if write_trials else None)

    def latencies(self, task: str, model_id: str) -> Tuple[float, ...]:
        """Return the key's times in milliseconds sorted ascending, ``()`` when none
        (DESIGN 4.3 v1.626)."""
        return tuple(sorted(self._latency.get((task, model_id), ())))

    def p95_latency_ms(self, task: str, model_id: str) -> Optional[float]:
        """Return the 95th percentile of the key's times by ``report``'s nearest-rank rule,
        ``None`` when none is recorded (DESIGN 4.3 v1.626, 8.3)."""
        times = self.latencies(task, model_id)
        if not times:
            return None
        return times[max(0, ceil(0.95 * len(times)) - 1)]

    def escalations(self, task: str, cascade_id: str) -> int:
        """Return how many of a cascade's trials escalated, 0 when nothing is recorded."""
        return self._escalated.get((task, cascade_id), 0)

    def cost(self, task: str, model_id: str) -> float:
        """Return a procedure key's summed cost in USD, 0.0 when none is recorded."""
        return self._cost.get((task, model_id), 0.0)

    def mean_cost(self, task: str, model_id: str) -> Optional[float]:
        """Return a procedure key's cost per trial, ``None`` with no trials or no such key."""
        key = (task, model_id)
        trials = self.get(task, model_id)[1]
        if key not in self._cost or trials == 0:
            return None
        return self._cost[key] / trials

    def mean_tokens(self, task: str, model_id: str) -> Optional[Tuple[int, int]]:
        """Return the mean input and output tokens per recorded call, each rounded up.

        Integer arithmetic, never a float; ``None`` when no token counts are recorded.
        """
        i, o, k = self.tokens(task, model_id)
        if k == 0:
            return None
        return -(-i // k), -(-o // k)

    def merge(self, other: "Stats") -> "Stats":
        """Return a new Stats with the summed counts, token totals, cache totals, escalations
        and costs, and both sides' times."""
        merged = Stats()
        for source in (self, other):
            for key, (s, t) in source._counts.items():
                merged.add(*key, s, t, escalated=source._escalated.get(key),
                           cost_usd=source._cost.get(key))
            for key, (i, o, k) in source._tokens.items():
                a, b, n = merged._tokens.get(key, (0, 0, 0))
                merged._tokens[key] = (a + i, b + o, n + k)
            for key, values in source._cache.items():  # DESIGN 4.3 v1.588
                held = merged._cache.get(key, (0, 0, 0, 0))
                merged._cache[key] = tuple(x + y for x, y in zip(held, values))
            for key, values in source._latency.items():  # DESIGN 4.3 v1.626
                merged._latency.setdefault(key, []).extend(values)
        return merged

    def items(self):
        """Yield ``((task, model_id), (successes, trials))`` sorted by key."""
        return sorted(self._counts.items())

    @classmethod
    def load(cls, path: PathLike) -> "Stats":
        """Load stats from ``{"stats": [{"task", "model", "successes", "trials"}]}``.

        A row may also carry ``input_tokens``, ``output_tokens`` and ``token_trials``,
        all three or none, and then ``cached_input_tokens`` with ``cached_trials``, and
        ``cache_write_tokens`` with ``cache_write_trials``, each pair both keys or neither
        (DESIGN 4.3 v1.588). A cascade row (its ``model`` holds ``>``) carries ``escalated``
        and no token keys, and no other row carries ``escalated``. A procedure row (its
        ``model`` starts with ``proc:``) carries ``cost_usd`` and no token keys; any other
        row's ``cost_usd`` is ignored (DESIGN 4.3 v1.577).
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
            for count_key, trials_key in _CACHE_PAIRS:  # DESIGN 4.3 v1.588
                if count_key not in row and trials_key not in row:
                    continue
                if count_key not in row or trials_key not in row:
                    raise ValueError(f"{path}: a stats row carries {count_key} and {trials_key} "
                                     f"together or neither: {row!r}")
                if not present:
                    raise ValueError(f"{path}: {count_key} needs {', '.join(_TOKEN_KEYS)}: {row!r}")
                if not (_is_int(row[count_key]) and _is_int(row[trials_key])):  # review iter-436 must-fix 1
                    raise ValueError(f"{path}: {count_key} and {trials_key} must be integers: {row!r}")
                tokens[count_key] = row[count_key]
                tokens[trials_key] = row[trials_key]
            if "escalated" in row:
                if not _is_cascade_key(model_id):
                    raise ValueError(f"{path}: only a cascade row carries escalated: {row!r}")
                tokens["escalated"] = row["escalated"]
            if _is_procedure_key(model_id):
                if "cost_usd" not in row:
                    raise ValueError(f"{path}: a procedure row needs cost_usd: {row!r}")
                tokens["cost_usd"] = row["cost_usd"]
            if "latencies_ms" in row:  # DESIGN 4.3 v1.626: null is no array, never no time
                if not isinstance(row["latencies_ms"], list):
                    raise ValueError(f"{path}: latencies_ms must be a JSON array of times: {row!r}")
                tokens["latencies_ms"] = row["latencies_ms"]
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
            if (task, model_id) in self._cost:  # a procedure key, even at 0 (DESIGN 4.3 v1.577)
                row["cost_usd"] = self._cost[(task, model_id)]
            if (task, model_id) in self._escalated:  # .add sets it for every cascade key, even at 0
                row["escalated"] = self._escalated[(task, model_id)]
            i, o, k = self.tokens(task, model_id)
            if k:
                row.update(input_tokens=i, output_tokens=o, token_trials=k)
            cached, cached_trials, write, write_trials = self.cache_tokens(task, model_id)
            if cached_trials:  # DESIGN 4.3 v1.588, after the token keys
                row.update(cached_input_tokens=cached, cached_trials=cached_trials)
            if write_trials:
                row.update(cache_write_tokens=write, cache_write_trials=write_trials)
            times = self.latencies(task, model_id)
            if times:  # DESIGN 4.3 v1.626, the row's last key
                row["latencies_ms"] = list(times)
            rows.append(row)
        Path(path).write_text(json.dumps({"stats": rows}, indent=2) + "\n", encoding="utf-8")


def calibrate_from_results(rows: Iterable[dict]) -> Stats:
    """Count one trial per row; a row is correct by ``correct`` or ``prediction == gold``.

    ``correct`` must be a real boolean. A row may carry ``input_tokens`` and
    ``output_tokens``, both or neither, and then adds one token trial with those counts, and
    beside them ``cached_input_tokens`` and ``cache_write_tokens``, either or both, that call's
    own cache counts (DESIGN 4.3 v1.588).
    A row with a ``slice`` adds its trial under ``<task>`` and ``<task>@<slice>``
    (DESIGN 4.3 v1.511). A cascade row (its ``model`` holds ``>``) carries a boolean
    ``escalated`` and no token counts, and no other row carries ``escalated`` (DESIGN 7). A
    procedure row carries ``cost_usd``, its trial's cost, and no token counts; any other row's
    ``cost_usd`` is ignored (DESIGN 4.3 v1.577). Any row may carry ``latency_ms``, its trial's
    time in milliseconds (DESIGN 4.3 v1.626).
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
        for count_key, _ in _CACHE_PAIRS:  # DESIGN 4.3 v1.588: this one trial's own counts
            if count_key in row:
                if not has_in:
                    raise ValueError(f"{count_key} needs input_tokens and output_tokens: {row!r}")
                if not _is_int(row[count_key]) or row[count_key] < 0:  # review iter-436 must-fix 1
                    raise ValueError(f"{count_key} must be an integer >= 0: {row!r}")
                tokens[count_key] = row[count_key]
        if _is_procedure_key(model_id):
            if has_in:
                raise ValueError(f"a procedure row carries no token counts: {row!r}")
            if "escalated" in row:
                raise ValueError(f"only a cascade row carries 'escalated': {row!r}")
            if "cost_usd" not in row or not _is_cost(row["cost_usd"]):
                raise ValueError(f"a procedure row needs 'cost_usd', a finite number >= 0: {row!r}")
            tokens["cost_usd"] = row["cost_usd"]
        elif _is_cascade_key(model_id):
            if has_in:
                raise ValueError(f"a cascade row carries no token counts: {row!r}")
            if type(row.get("escalated")) is not bool:
                raise ValueError(f"a cascade row needs 'escalated' true or false: {row!r}")
            tokens["escalated"] = 1 if row["escalated"] else 0
        elif "escalated" in row:
            raise ValueError(f"only a cascade row carries 'escalated': {row!r}")
        if "latency_ms" in row:  # DESIGN 4.3 v1.626: this one trial's time, on any key
            if not _is_cost(row["latency_ms"]):
                raise ValueError(f"'latency_ms' must be a finite number >= 0: {row!r}")
            tokens["latencies_ms"] = [row["latency_ms"]]
        slice_name = row.get("slice")
        keys = [task]
        if slice_name is not None:
            if not is_slice_name(slice_name) or not isinstance(task, str) or "@" in task:
                raise ValueError(f"'slice' must be a non-empty string without '@' on a task "
                                 f"without '@': {row!r}")
            keys.append(f"{task}@{slice_name}")
        for key in keys:
            stats.add(key, model_id, 1 if correct else 0, 1, **tokens)
    return stats


def item_outcomes(rows: Iterable[dict], *, dataset_sha256: str) -> List[dict]:
    """One outcome record per result row, in row order, for a paired check (DESIGN 4.3 v1.602).

    Each row is checked as `calibrate_from_results` checks it and must also carry ``task``,
    ``model`` and ``item``, each a non-empty string; ``dataset_sha256`` is 64 lowercase hex
    digits, the sha256 of the labeled file's bytes. A record holds ``task``, ``slice`` (None when
    the row has none), ``route`` (the row's ``model``), ``item``, ``correct`` and
    ``dataset_sha256``, in that order. Every check runs before a record is returned, and no row
    is changed.
    """
    if (not isinstance(dataset_sha256, str) or len(dataset_sha256) != 64
            or not set(dataset_sha256) <= _HEX):
        raise ValueError(f"dataset_sha256 must be 64 lowercase hex digits, got {dataset_sha256!r}")
    rows = list(rows)
    calibrate_from_results(rows)  # the same checks, the same messages, before any record
    for row in rows:
        for key in _OUTCOME_KEYS:
            value = row.get(key)
            if not isinstance(value, str) or not value:
                raise ValueError(f"an outcome row needs a non-empty string {key!r}: {row!r}")
    records = []
    for row in rows:
        if "correct" in row:
            correct = row["correct"]
        else:
            correct = row["prediction"] == row["gold"]
        records.append({"task": row["task"], "slice": row.get("slice"), "route": row["model"],
                        "item": row["item"], "correct": bool(correct),
                        "dataset_sha256": dataset_sha256})
    return records
