"""Leaderboard-derived priors used only to order cold-start candidates."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Dict, List, Optional, Union

PathLike = Union[str, Path]


class Priors:
    """Public leaderboard scores per category.

    Priors never clear a bar; they order candidates when nothing has been
    measured and suggest which models to calibrate first.
    """

    def __init__(self, categories: Dict[str, dict]):
        self.categories = categories

    @classmethod
    def load(cls, path: PathLike) -> "Priors":
        """Load ``{"categories": {name: {"metric", "source", "as_of", "scores"}}}``."""
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("categories"), dict):
            raise ValueError(f"{path}: expected an object with a 'categories' object")
        return cls(raw["categories"])

    def score(self, category: str, model_id: str) -> Optional[float]:
        """Return the model's score in the category, or ``None`` if either is unknown."""
        data = self.categories.get(category)
        if not isinstance(data, dict):
            return None
        return data.get("scores", {}).get(model_id)

    def ranked(self, category: str) -> List[str]:
        """Return model IDs by descending score, ties by ascending ID."""
        data = self.categories.get(category)
        if not isinstance(data, dict):
            return []
        scores = data.get("scores", {})
        return sorted(scores, key=lambda model_id: (-scores[model_id], model_id))
