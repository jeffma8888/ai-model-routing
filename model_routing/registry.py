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
_VARIANT_KEYS = ("reasoning_effort", "harness", "context_policy", "items_per_call",
                 "provider_options")
_PRICING_BASES = ("list", "self_hosted")
_DEPLOYMENTS = ("api", "self_hosted")
_HOUR_KEYS = ("usd_per_hour", "tokens_per_hour_in", "tokens_per_hour_out", "utilization",
              "input_cost_share")


def _is_price(value) -> bool:
    return (isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value >= 0)


def _json_copy(value, at: str):
    """A new plain copy of a JSON value: mappings as dicts, lists and tuples as lists (DESIGN 4.1 v1.574).

    Raises ``ValueError`` naming ``at`` for anything else: a non-``str`` mapping key, a float that is
    not finite, or a value of another type.
    """
    if value is None or isinstance(value, (bool, int, str)):
        return value
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ValueError(f"{at} must be a finite float, got {value!r}")
        return value
    if isinstance(value, (list, tuple)):
        return [_json_copy(item, f"{at}[{index}]") for index, item in enumerate(value)]
    if isinstance(value, Mapping):
        copied = {}
        for key, item in value.items():
            if not isinstance(key, str):
                raise ValueError(f"a key in {at} must be a string, got {key!r}")
            copied[key] = _json_copy(item, f"{at}[{key!r}]")
        return copied
    raise ValueError(f"{at} must be None, a bool, an int, a finite float, a string, a list or a "
                     f"mapping, got {type(value).__name__}")


def self_hosted_prices(usd_per_hour, tokens_per_hour_in, tokens_per_hour_out, utilization,
                       input_cost_share) -> Tuple[float, float]:
    """``(price_in, price_out)`` in USD per 1M tokens of a model you serve (DESIGN 4.1 v1.581).

    The hour is split between input and output by ``input_cost_share``, and each side's share is
    spread over the tokens it handles in the used part of the hour, so an hour fully used at these
    throughputs is charged once. The throughputs describe one workload, and the split is an
    approximation: a unit that reads and writes in the same hour has no one price of each.
    """
    values = {"usd_per_hour": usd_per_hour, "tokens_per_hour_in": tokens_per_hour_in,
              "tokens_per_hour_out": tokens_per_hour_out, "utilization": utilization,
              "input_cost_share": input_cost_share}
    for name, value in values.items():
        try:
            finite = _is_price(value)
        except OverflowError:  # an int too large for a float (review iter-428 should-fix 2)
            finite = False
        if not finite:
            raise ValueError(f"{name} must be a finite number >= 0, got {value!r}")
    for name in ("tokens_per_hour_in", "tokens_per_hour_out"):
        if values[name] <= 0:
            raise ValueError(f"{name} must be above 0, got {values[name]!r}")
    if not 0 < utilization <= 1:
        raise ValueError(f"utilization must be in (0, 1], got {utilization!r}")
    if not input_cost_share <= 1:
        raise ValueError(f"input_cost_share must be in [0, 1], got {input_cost_share!r}")
    derived = {}
    for name, share, tokens in (("price_in", input_cost_share, tokens_per_hour_in),
                                ("price_out", 1 - input_cost_share, tokens_per_hour_out)):
        try:
            price = float(usd_per_hour) * share / (float(tokens) * utilization) * 1_000_000
        except ZeroDivisionError:  # the product underflowed to 0
            price = math.inf
        if not math.isfinite(price):  # review iter-428 must-fix 2: a price that could never rank
            raise ValueError(f"the derived {name} is not a finite number: the hour, throughput and "
                             "utilization leave a float's range")
        derived[name] = price
    return derived["price_in"], derived["price_out"]


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

    ``reasoning_effort``, ``harness`` and ``context_policy`` are labels: the library sets no effort
    from them and compacts nothing, and a variant's route has its own stats. ``items_per_call`` is how many items one call of the route handles, so a
    measured route is priced per item, its mean call over that number (4.1 and 5.2 v1.573).
    ``provider_options`` is sent: the executor passes a copy to the provider on each call of the
    route (4.1, 6 and 7 v1.574), for example ``{"reasoning_effort": "high"}``.
    """

    name: str
    reasoning_effort: Optional[str] = None
    harness: Optional[str] = None
    context_policy: Mapping[str, object] = field(default_factory=dict)
    items_per_call: int = 1
    provider_options: Mapping[str, object] = field(default_factory=dict)

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
        k = self.items_per_call
        if not isinstance(k, int) or isinstance(k, bool) or k < 1:  # DESIGN 4.1 v1.573
            raise ValueError(f"items_per_call must be an int >= 1, got {k!r}")
        options = self.provider_options
        if not isinstance(options, Mapping):  # DESIGN 4.1 v1.574
            raise ValueError(f"provider_options must be a mapping, got {type(options).__name__}")
        if any(not isinstance(key, str) or not key for key in options):
            raise ValueError("a provider_options key must be a non-empty string")
        object.__setattr__(self, "provider_options", _json_copy(options, "provider_options"))


@dataclass(frozen=True)
class Model:
    """A routable model with list prices in USD per 1M tokens.

    ``aliases`` maps a provider name to that provider's ID for this model.
    ``price_valid_until`` is the last day, as ``YYYY-MM-DD``, on which the vendor
    states these prices, or ``None`` when no end date is stated. ``price_tiers`` holds the
    higher prices of long prompts, thresholds rising, each below ``context_window``.
    ``variant`` names a setup of the model, whose ``id`` is then ``<base>@<name>`` (4.1 v1.572).
    ``pricing_basis`` is ``"list"`` (a vendor's page) or ``"self_hosted"`` (prices derived from an
    hour of your own serving by ``self_hosted_prices``; 4.1 v1.581).
    ``deployment`` is where it runs, ``"api"`` or ``"self_hosted"``, ``None`` meaning ``"self_hosted"``
    for a self-hosted-priced model and ``"api"`` otherwise; ``base_model`` names a fine-tune's base,
    whose family a ``Registry`` requires it to have (4.1 v1.582).
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
    pricing_basis: str = "list"
    deployment: Optional[str] = None
    base_model: Optional[str] = None

    def __post_init__(self):
        if not isinstance(self.pricing_basis, str) or self.pricing_basis not in _PRICING_BASES:
            raise ValueError(f"pricing_basis must be 'list' or 'self_hosted', got {self.pricing_basis!r}")
        if self.pricing_basis == "self_hosted" and self.price_tiers:  # DESIGN 4.1 v1.581
            raise ValueError("a self_hosted model holds no price tiers: an hour costs the same "
                             "whatever a prompt's length")
        deployment = self.deployment
        if deployment is None:  # DESIGN 4.1 v1.582: a self-hosted-priced model is served by its owner
            deployment = "self_hosted" if self.pricing_basis == "self_hosted" else "api"
            object.__setattr__(self, "deployment", deployment)
        if not isinstance(deployment, str) or deployment not in _DEPLOYMENTS:
            raise ValueError(f"deployment must be 'api' or 'self_hosted', got {deployment!r}")
        base = self.base_model
        if base is not None and (not isinstance(base, str) or not base):
            raise ValueError(f"base_model must be None or a non-empty string, got {base!r}")
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

    @property
    def items_per_call(self) -> int:
        """How many items one call handles: its variant's, 1 without one (DESIGN 4.1 v1.573)."""
        return 1 if self.variant is None else self.variant.items_per_call

    @property
    def provider_options(self) -> Dict[str, object]:
        """A new copy of its variant's provider options, ``{}`` without one (DESIGN 4.1 v1.574)."""
        if self.variant is None:
            return {}
        return _json_copy(self.variant.provider_options, "provider_options")

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


def _load_prices(row) -> Tuple[str, float, float]:
    """A models.json row's basis and prices: list prices, or ones derived from its hour (DESIGN 4.1 v1.581)."""
    basis = row.get("pricing_basis")
    basis = "list" if basis is None else basis
    if not isinstance(basis, str) or basis not in _PRICING_BASES:
        raise ValueError(f"pricing_basis must be 'list' or 'self_hosted', got {basis!r}")
    if basis == "list":
        named = [key for key in _HOUR_KEYS if key in row]
        if named:
            raise ValueError(f"{', '.join(named)} needs pricing_basis 'self_hosted'; a list row "
                             "states price_in and price_out")
        return basis, float(row["price_in"]), float(row["price_out"])
    if any(key in row for key in ("price_in", "price_out", "price_tiers")):
        raise ValueError("a self_hosted row's prices are derived from its hour, so it takes no "
                         "price_in, price_out or price_tiers")
    missing = [key for key in _HOUR_KEYS if row.get(key) is None]
    if missing:
        raise ValueError(f"a self_hosted row needs {', '.join(missing)}")
    price_in, price_out = self_hosted_prices(*(row[key] for key in _HOUR_KEYS))
    return basis, price_in, price_out


def _load_family(row, rows_by_id) -> str:
    """A row's family: its own, or a fine-tune row's base row's when it leaves it out (DESIGN 4.1 v1.582)."""
    name = row.get("base_model")
    if row.get("family") is not None or name is None:
        return str(row["family"])  # as before v1.582: absent is a KeyError, null the string "None"
    if not isinstance(name, str) or not name:  # Model's message, with or without a family (review iter-429 nit 1)
        raise ValueError(f"base_model must be None or a non-empty string, got {name!r}")
    base = rows_by_id.get(name)
    if base is None:
        raise ValueError(f"base_model {name!r} is not a row of this file, so the row has no family")
    if base.get("family") is None:
        raise ValueError(f"the row of base_model {name!r} states no family, so this row has none")
    return str(base["family"])


def _check_base(model: "Model", by_id: Mapping[str, "Model"]) -> None:
    """A fine-tune's base is a registry model, no variant, naming no base, of its family (DESIGN 4.1 v1.582)."""
    name = model.base_model
    if name == model.base_id:
        raise ValueError(f"model {model.id!r} names itself as its base_model")
    base = by_id.get(name)
    if base is None:
        raise ValueError(f"base_model {name!r} of {model.id!r} is not a model of this registry")
    if base.variant is not None:
        raise ValueError(f"base_model {name!r} of {model.id!r} is a variant; name its base's row")
    if base.base_model is not None:
        raise ValueError(f"base_model {name!r} of {model.id!r} names a base_model itself; name the "
                         "model it was trained from")
    if model.family != base.family:
        raise ValueError(f"model {model.id!r} has family {model.family!r}, but a fine-tune has its "
                         f"base's family {base.family!r}")


_VARIANT_AGREES = ("family", "pricing_basis", "deployment", "base_model")


def _check_variant(model: "Model", by_id: Mapping[str, "Model"]) -> None:
    """A variant whose base is a registry model has its family, basis, deployment and base (DESIGN 4.1 v1.583)."""
    base = by_id.get(model.base_id)
    if base is None:  # a variant routed alone, as v1.572 allows
        return
    differ = [f"{name} {getattr(model, name)!r} (its base's {getattr(base, name)!r})"
              for name in _VARIANT_AGREES if getattr(model, name) != getattr(base, name)]
    if differ:  # prices, tiers, window and aliases stay free: a provider option may change them
        raise ValueError(f"variant {model.id!r} differs from its base model {base.id!r} in "
                         f"{', '.join(differ)}; a variant has its base's family, pricing_basis, "
                         "deployment and base_model")


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
        for model in ordered:  # DESIGN 4.1 v1.582, after the duplicate check
            if model.base_model is not None:
                _check_base(model, by_id)
        for model in ordered:  # DESIGN 4.1 v1.583, after the base checks
            if model.variant is not None:
                _check_variant(model, by_id)
        self._models = ordered
        self._by_id = by_id

    @classmethod
    def load(cls, path: PathLike) -> "Registry":
        """Load a registry from a models.json file.

        Extra keys of a row are ignored, but for an hourly key on a list row (DESIGN 4.1 v1.581).
        A fine-tune row may leave out its family, taking its base row's (4.1 v1.582).
        """
        raw = json.loads(Path(path).read_text(encoding="utf-8"))
        if not isinstance(raw, dict) or not isinstance(raw.get("models"), list):
            raise ValueError(f"{path}: expected an object with a 'models' list")
        rows_by_id = {}
        for row in raw["models"]:  # a fine-tune row's base may come after it (DESIGN 4.1 v1.582)
            if isinstance(row, dict) and "id" in row:
                rows_by_id.setdefault(str(row["id"]), row)
        models = []
        for row in raw["models"]:
            try:
                if not isinstance(row, dict):  # review iter-428 must-fix 1: before any row.get
                    raise TypeError(f"a model row must be an object, got {type(row).__name__}")
                basis, price_in, price_out = _load_prices(row)
                base = Model(
                    id=str(row["id"]),
                    family=_load_family(row, rows_by_id),
                    price_in=price_in,
                    price_out=price_out,
                    context_window=int(row["context_window"]),
                    aliases=dict(row.get("aliases") or {}),
                    price_valid_until=row.get("price_valid_until"),
                    price_tiers=_load_tiers(row.get("price_tiers")),
                    pricing_basis=basis,
                    deployment=row.get("deployment"),
                    base_model=row.get("base_model"),
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
        try:
            return cls(models)
        except ValueError as exc:  # DESIGN 4.1 v1.582: a registry check names the file too
            raise ValueError(f"{path}: {exc}") from exc

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
