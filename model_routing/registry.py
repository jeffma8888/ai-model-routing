"""Model metadata and the registry of routable models."""

from __future__ import annotations

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Optional, Tuple, Union

PathLike = Union[str, Path]
_ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")


@dataclass(frozen=True)
class Model:
    """A routable model with list prices in USD per 1M tokens.

    ``aliases`` maps a provider name to that provider's ID for this model.
    ``price_valid_until`` is the last day, as ``YYYY-MM-DD``, on which the vendor
    states these prices, or ``None`` when no end date is stated.
    """

    id: str
    family: str
    price_in: float
    price_out: float
    context_window: int
    aliases: Dict[str, str] = field(default_factory=dict)
    price_valid_until: Optional[str] = None

    def __post_init__(self):
        value = self.price_valid_until
        if value is None:
            return
        if not isinstance(value, str) or not _ISO_DAY.fullmatch(value):
            raise ValueError(f"price_valid_until must be a YYYY-MM-DD string, got {value!r}")
        try:
            date.fromisoformat(value)
        except ValueError:
            raise ValueError(f"price_valid_until is not a real day: {value!r}") from None

    def price_expired(self, today: date) -> bool:
        """Return True when the stated price end date is before ``today``."""
        if isinstance(today, datetime):
            today = today.date()
        elif not isinstance(today, date):
            raise TypeError(f"today must be a datetime.date, got {type(today).__name__}")
        if self.price_valid_until is None:
            return False
        return today > date.fromisoformat(self.price_valid_until)

    def cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return the list-price cost in USD of a call with these token counts."""
        return (input_tokens * self.price_in + output_tokens * self.price_out) / 1_000_000


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
