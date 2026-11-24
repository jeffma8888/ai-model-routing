"""The one hash for a pinned decision (DESIGN 4.3 v1.593, rows CI31 and CI32).

`z` in `wilson_lower_bound` can differ in its last bit by platform (4.3 v1.592), and so can a
bound at 1 or more successes and a value divided by one. ``decision_sha256`` hashes a value
with each of those rounded to ``BOUND_DIGITS`` decimals, so a pin holds on every platform;
every other value is hashed exact. tests/test_decision_hash_pins.py fails when a test hashes a
JSON value without it, unless that site is on its list of values that hold no bound.
"""

import hashlib
import json

# decimals, not significant digits: a last-bit difference rounds away while a value is well
# under 1e3 (a double's spacing reaches 1e-12 near 1e4); a bound is in [0, 1] and every pinned
# cost per success is far under 1 USD (review iter-441 nit 2)
BOUND_DIGITS = 12
# a decision's bound, a delegation decision's two, and the cost per success divided by one
BOUND_KEYS = frozenset({"quality_lb", "parent_quality_lb", "delegate_quality_lb",
                        "expected_cost_per_success_usd"})
# `NormalDist().inv_cdf(0.975)` on the machine that wrote v1.591's tests and on the CI runners
PLATFORM_Z = (1.9599639845400534, 1.9599639845400536)


def neutral(value):
    """``value`` with each float under a ``BOUND_KEYS`` key rounded, every other value as it is."""
    if isinstance(value, dict):
        return {key: round(item, BOUND_DIGITS)
                if key in BOUND_KEYS and isinstance(item, float) else neutral(item)
                for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [neutral(item) for item in value]
    return value


def candidate_fields(candidate):
    """``dataclasses.asdict(candidate)`` less ``p95_latency_ms`` when it is None (DESIGN 5.1 v1.628).

    A pin computed before v1.628 hashed a candidate's fields when `Candidate` had none for a time; a
    call whose task sets no bar leaves that field None, so dropping it keeps such a pin's meaning.
    """
    import dataclasses
    data = dataclasses.asdict(candidate)
    if data.get("p95_latency_ms", 0) is None:
        del data["p95_latency_ms"]
    return data


def decision_sha256(value, *, sort_keys=True):
    """The sha256 of ``value``'s JSON, its bounds rounded first (``neutral``)."""
    return hashlib.sha256(json.dumps(neutral(value), sort_keys=sort_keys).encode()).hexdigest()


class FixedZ:
    """Stands in for `NormalDist` in model_routing.stats, its `inv_cdf` always ``z``."""

    def __init__(self, z):
        self.z = z

    def __call__(self):
        return self

    def inv_cdf(self, p):
        return self.z
