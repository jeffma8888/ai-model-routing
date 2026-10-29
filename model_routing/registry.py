"""Model metadata and the registry of routable models."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, Iterable, Tuple, Union

PathLike = Union[str, Path]


@dataclass(frozen=True)
class Model:
    """A routable model with list prices in USD per 1M tokens.

    ``aliases`` maps a provider name to that provider's ID for this model.
    """

    id: str
    family: str
    price_in: float
    price_out: float
    context_window: int
    aliases: Dict[str, str] = field(default_factory=dict)

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
                ))
            except (KeyError, TypeError, ValueError) as exc:
                raise ValueError(f"{path}: invalid model row {row!r}: {exc}") from exc
        return cls(models)

    @property
    def models(self) -> Tuple[Model, ...]:
        """All models in insertion (file) order."""
        return self._models

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
