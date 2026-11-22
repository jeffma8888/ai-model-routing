"""Model metadata and the registry of routable models."""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field, replace
from datetime import date, datetime
from pathlib import Path
from typing import Dict, Iterable, Mapping, Optional, Tuple, Union

PathLike = Union[str, Path]
_ISO_DAY = re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")
_VARIANT_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]*")
_VARIANT_KEYS = ("reasoning_effort", "harness", "context_policy")


def _is_price(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def _tier_prices(model, input_tokens) -> Tuple[float, float]:
    """The prices of one call that reads ``input_tokens``: the last tier it is over, else the base.

    ``Model.cost`` and the per-call delegation costs of DESIGN 13.2 v1.219 read them.
    """
    price_in, price_out = model.price_in, model.price_out
    for tier in model.price_tiers:
        if input_tokens > tier.above_input_tokens:
            price_in, price_out = tier.price_in, tier.price_out
    return price_in, price_out


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
class Variant:
    """A named setup of a model: labels of how the caller's harness runs it (DESIGN 4.1 v1.572).

    The library sets no effort and compacts nothing; a variant's route has its own stats.
    """

    name: str
    reasoning_effort: Optional[str] = None
    harness: Optional[str] = None
    context_policy: Mapping[str, object] = field(default_factory=dict)

    def __post_init__(self):
        if not isinstance(self.name, str) or not _VARIANT_NAME.fullmatch(self.name):
            raise ValueError(f"a variant name must match [A-Za-z0-9][A-Za-z0-9._-]*, "
                             f"got {self.name!r}")
        for key in ("reasoning_effort", "harness"):
            value = getattr(self, key)
            if value is not None and (not isinstance(value, str) or not value):
                raise ValueError(f"{key} must be None or a non-empty string, got {value!r}")
        policy = self.context_policy
        if not isinstance(policy, Mapping):
            raise ValueError(f"context_policy must be a mapping, got {policy!r}")
        for key, value in policy.items():
            if not isinstance(key, str) or not key:
                raise ValueError(f"a context_policy key must be a non-empty string, got {key!r}")
            if not (value is None or isinstance(value, (str, int))
                    or (isinstance(value, float) and math.isfinite(value))):
                raise ValueError(f"context_policy[{key!r}] must be None, a bool, an int, a "
                                 f"finite float or a string, got {value!r}")
        object.__setattr__(self, "context_policy", dict(policy))


@dataclass(frozen=True)
class Model:
    """A routable model with list prices in USD per 1M tokens.

    ``aliases`` maps a provider name to that provider's ID for this model.
    ``price_valid_until`` is the last day, as ``YYYY-MM-DD``, on which the vendor
    states these prices, or ``None`` when no end date is stated. ``price_tiers`` holds the
    higher prices of long prompts, thresholds rising, each below ``context_window``.
    ``variant`` names a setup of the model, whose ``id`` is then ``<base>@<name>`` (4.1 v1.572).
    """

    id: str
    family: str
    price_in: float
    price_out: float
    context_window: int
    aliases: Dict[str, str] = field(default_factory=dict)
    price_valid_until: Optional[str] = None
    price_tiers: Tuple[PriceTier, ...] = ()
    variant: Optional[Variant] = None

    def __post_init__(self):
        variant = self.variant
        if variant is not None:  # DESIGN 4.1 v1.572; an id without a variant is v1.571's
            if not isinstance(variant, Variant):
                raise ValueError(f"variant must be None or a Variant, got {variant!r}")
            text = self.id if isinstance(self.id, str) else ""
            base, _, name = text.rpartition("@")
            if name != variant.name or not base or "@" in base:
                raise ValueError(f"model id {self.id!r} must be <base>@{variant.name}, its "
                                 "base non-empty and holding no '@'")
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

    @property
    def base_id(self) -> str:
        """The model's ID without ``@<variant name>`` (DESIGN 4.1 v1.572)."""
        return self.id if self.variant is None else self.id.rpartition("@")[0]

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
        price_in, price_out = _tier_prices(self, input_tokens)
        return (input_tokens * price_in + output_tokens * price_out) / 1_000_000

    def base_cost(self, input_tokens: int, output_tokens: int) -> float:
        """Return the cost at ``price_in`` and ``price_out`` whatever the tiers.

        Linear: every delegation cost term of a model without tiers and the 13.9 held-out
        costs use it (DESIGN 13.2 v1.212 and v1.219).
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


def _load_variants(value) -> Tuple[Variant, ...]:
    """The ``variants`` of a models.json row, in its order: absent or null is none (DESIGN 4.1)."""
    if value is None:
        return ()
    if not isinstance(value, dict):
        raise ValueError(f"variants must be an object of variant objects, got {value!r}")
    variants = []
    for name, settings in value.items():
        if not isinstance(settings, dict):
            raise ValueError(f"variant {name!r} must be an object, got {settings!r}")
        unknown = sorted(set(settings) - set(_VARIANT_KEYS))
        if unknown:
            raise ValueError(f"variant {name!r} has keys {unknown}; a variant takes only "
                             f"{', '.join(_VARIANT_KEYS)}")
        variants.append(Variant(name, **{key: setting for key, setting in settings.items()
                                         if setting is not None}))  # null is absent, as on a row
    return tuple(variants)


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
                base = Model(
                    id=str(row["id"]),
                    family=str(row["family"]),
                    price_in=float(row["price_in"]),
                    price_out=float(row["price_out"]),
                    context_window=int(row["context_window"]),
                    aliases=dict(row.get("aliases") or {}),
                    price_valid_until=row.get("price_valid_until"),
                    price_tiers=_load_tiers(row.get("price_tiers")),
                )
                if "@" in base.id:
                    raise ValueError("a row id must not hold '@', which joins a model and "
                                     "its variant (DESIGN 4.1 v1.572)")
                models.append(base)
                models.extend(replace(base, id=f"{base.id}@{variant.name}",
                                      aliases=dict(base.aliases), variant=variant)
                              for variant in _load_variants(row.get("variants")))
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
