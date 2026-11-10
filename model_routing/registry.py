"""Model metadata and the registry of routable models."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, Union

PathLike = Union[str, Path]
_ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


def _is_price(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


@dataclass(frozen=True)
class PriceTier:
    """The prices, in USD per 1M tokens, of a call whose input is over ``above_input_tokens``.

    Such a call pays ``price_in`` on all of its input tokens and ``price_out`` on all of its
    output tokens (DESIGN 4.1, v1.212).
    """

    above_input_tokens: int
    price_in: float
    price_out: float

    def __post_init__(self):
        above = self.above_input_tokens
        if not isinstance(above, int) or isinstance(above, bool) or above < 1:
            raise ValueError(f"above_input_tokens must be an int >= 1, got {above!r}")
        for name in ("price_in", "price_out"):
            value = getattr(self, name)
            if not _is_price(value):
                raise ValueError(f"{name} must be a finite number >= 0, got {value!r}")
            object.__setattr__(self, name, float(value))


@dataclass(frozen=True)
class Model:
    """A routable model with list prices in USD per 1M tokens.

    ``aliases`` maps a provider name to that provider's ID for this model.
    ``price_valid_until`` is the last day, as ``YYYY-MM-DD``, on which the vendor
    states these prices, or ``None`` when no end date is stated. ``price_tiers`` holds the
    higher prices of long prompts, thresholds rising, each below ``context_window``.
    """

    id: str
    family: str
    price_in: float
    price_out: float
    context_window: int
    aliases: Dict[str, str] = field(default_factory=dict)
    price_valid_until: Optional[str] = None
    price_tiers: Tuple[PriceTier, ...] = ()

    def __post_init__(self):
        value = self.price_valid_until
        if value is not None:
            if not isinstance(value, str) or not _ISO_DAY.fullmatch(value):
                raise ValueError(f"price_valid_until must be a YYYY-MM-DD string, got {value!r}")
            try:
                date.fromisoformat(value)
            except ValueError:
                raise ValueError(f"price_valid_until is not a real day: {value!r}") from None
        tiers = self.price_tiers
        if not isinstance(tiers, tuple):
            raise ValueError(f"price_tiers must be a tuple of PriceTier, got {tiers!r}")
        previous = 0
        for tier in tiers:
            if not isinstance(tier, PriceTier):
                raise ValueError(f"price_tiers must hold PriceTier values, got {tier!r}")
            if tier.above_input_tokens <= previous:
                raise ValueError("price_tiers thresholds must rise strictly, got "
                                 f"{tier.above_input_tokens} after {previous}")
            previous = tier.above_input_tokens
        if tiers and previous >= self.context_window:
            raise ValueError(f"price tier threshold {previous} is not below the context window "
                             f"{self.context_window}")

    def price_expired(self, today: date) -> bool:
        """Return True when the stated price end date is before ``today``."""
        if isinstance(today, datetime):  # before the date check: datetime is a date subclass
            today = today.date()
        elif not isinstance(today, date):
            raise TypeError(f"today must be a datetime.date, got {type(today).__name__}")
        if self.price_valid_until is None:
            return False
        return today > date.fromisoformat(self.price_valid_until)

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return the list-price cost in USD of one call with these token counts.

        The call pays the prices of the last tier whose threshold its input is over, on all
        of its tokens, or ``price_in`` and ``price_out`` when it is over none.
        """
        price_in, price_out = self.price_in, self.price_out
        for tier in self.price_tiers:
            if input_tokens > tier.above_input_tokens:
                price_in, price_out = tier.price_in, tier.price_out
        return (input_tokens * price_in + output_tokens * price_out) / 1_000_000

    def base_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return the cost at ``price_in`` and ``price_out`` whatever the tiers.

        Linear, for a total of several calls or a token increment, which has no one call's
        size (DESIGN 13.2 v1.212).
        """
        return (input_tokens * self.price_in + output_tokens * self.price_out) / 1_000_000


def _load_tiers(value) -> Tuple[PriceTier, ...]:
    """The ``price_tiers`` of a models.json row: absent or null is no tier (DESIGN 4.1)."""
    if value is None:
        return ()
    if not isinstance(value, list):
        raise ValueError(f"price_tiers must be a list of objects, got {value!r}")
    tiers = []
    for item in value:
        if not isinstance(item, dict):
            raise ValueError(f"a price tier must be an object, got {item!r}")
        tiers.append(PriceTier(item["above_input_tokens"], item["price_in"], item["price_out"]))
    return tuple(tiers)


class Registry:
    """An ordered, ID-unique collection of models."""

    def __init__(self, models: Iterable[Model]):
        ordered = tuple(models)
        by_id: Dict[str, Model] = {}
        for model in ordered:
            if model.id in by_id:
                raise ValueError(f"duplicate model id: {model.id!r}")
            by_id[model.id] = model
        self._models = ordered
        self._by_id = by_id

    @classmethod
    def load(cls, path: PathLike) -> "Registry":
        """Load a registry from a models.json file; extra keys are ignored."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("models"), list):
            raise ValueError(f"{path}: expected an object with a 'models' list")
        models = []
        for row in raw["models"]:
            try:
                models.append(Model(
                    id=str(row["id"]),
                    family=str(row["family"]),
                    price_in=float(row["price_in"]),
                    price_out=float(row["price_out"]),
                    context_window=int(row["context_window"]),
                    aliases=dict(row.get("aliases") or {}),
                    price_valid_until=row.get("price_valid_until"),
                    price_tiers=_load_tiers(row.get("price_tiers")),
                ))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{path}: invalid model row {row!r}: {exc}") from exc
        return cls(models)

    @property
    def models(self) -> Tuple[Model, ...]:
        """All models in insertion (file) order."""
        return self._models

    def expired_prices(self, today: date) -> Tuple[Model, ...]:
        """The models whose stated price end date is before ``today``, in file order."""
        return tuple(model for model in self._models if model.price_expired(today))

    def get(self, model_id: str) -> Model:
        """Return the model with this ID; raise ``KeyError`` if unknown."""
        try:
            return self._by_id[model_id]
        except KeyError:
            raise KeyError(f"unknown model: {model_id!r}") from None

    def __contains__(self, model_id: object) -> bool:
        return model_id in self._by_id

    def __len__(self) -> int:
        return len(self._models)
