"""Replay a cascade of two LiveCodeBench models on a failed public test of the cheap sample (DESIGN 7 v1.548).

Standard library and ``model_routing``. A cascade starts a problem on the cheap model and hands it up to
the strong one when its signal fires on the cheap model's first sample: ``public-test-failed`` when the
sample fails one of the problem's public test cases, the check a caller can run, and
``public-test-failed-or-no-test`` when it does or its record holds no test at all, so such a sample is
counted both ways, kept and handed up, as a bound (research/escalation.md, ``## Public tests matched
(row ESC1c)``). A sample's kind is the one research/escalation_public_tests.py gives a failed first
sample: ``public``, ``other``, ``input_only``, ``no_test`` or ``unread``; a passed one has none. A row
replays the cascade from the two models' rows of the problem: kept, the cheap row's label and cost; handed
up, the strong row's label and the sum of both costs. The submission files record no cost, so every cost
is 0.0 and the rows feed ``cost_blind`` only. A sample that fails a public case fails the problem, so a
hand-up never turns a right answer wrong; a wrong answer only a private case finds stays on the cheap
model. This version holds the replay rule only: it downloads, reads and writes nothing (rows ESC3l, ESC3m).
"""

import math

from model_routing import Cascade

SIGNALS = ("public-test-failed", "public-test-failed-or-no-test")
KINDS = ("public", "other", "input_only", "no_test", "unread")
CORE_KEYS = ("task", "item", "model", "correct", "cost_usd", "escalated")
LABEL = "difficulty"
_MISSING = object()


def escalates(kind, signal) -> bool:
    """Whether ``signal`` hands up a first sample of ``kind`` (None for a passed one); else a ValueError."""
    if not isinstance(signal, str) or signal not in SIGNALS:
        raise ValueError(f"unknown signal {signal!r}")
    if kind is not None and (not isinstance(kind, str) or kind not in KINDS):
        raise ValueError(f"unknown kind {kind!r}")
    if kind == "unread":
        raise ValueError("a sample with no readable metadata is never a cheap model's")
    return kind == "public" or (kind == "no_test" and signal == "public-test-failed-or-no-test")


def cascade_cell(cheap, strong, kind, signal) -> dict:
    """``{"correct", "cost_usd", "escalated"}`` of one problem run through the cascade (DESIGN 7 v1.548)."""
    up = escalates(kind, signal)
    if kind is None and cheap["correct"] is not True:
        raise ValueError("a failed first sample needs a kind")
    if kind is not None and cheap["correct"] is True:
        raise ValueError(f"a passed first sample has no kind, got {kind!r}")
    if not up:
        return {"correct": cheap["correct"], "cost_usd": cheap["cost_usd"], "escalated": False}
    return {"correct": strong["correct"], "cost_usd": math.fsum([cheap["cost_usd"], strong["cost_usd"]]),
            "escalated": True}


def _key(row) -> tuple:
    return (str(row["task"]), str(row["item"]), str(row["model"]))


def cascade_rows(rows, kinds, cascades) -> list:
    """A copy of every row plus one cascade row per cascade and (task, item) of its cheap model, sorted."""
    rows = list(rows)  # read once, so a one-shot iterable of rows keeps every row
    cascades = list(cascades)
    cells = {}
    for row in rows:
        key = (row["task"], row["item"], row["model"])
        if key in cells:
            raise ValueError(f"row {key!r} is repeated")
        cells[key] = row
    items = {}
    for task, item, model in cells:
        items.setdefault(model, set()).add((task, item))
    seen = set()
    for cascade in cascades:
        if not isinstance(cascade, Cascade):
            raise ValueError(f"cascade {cascade!r} is not a Cascade")
        if cascade.id in seen:
            raise ValueError(f"cascade {cascade.id} is repeated")
        seen.add(cascade.id)
    added = []
    for cascade in cascades:
        cid = cascade.id
        if not isinstance(cascade.signal, str) or cascade.signal not in SIGNALS:
            raise ValueError(f"cascade {cid}: unknown signal {cascade.signal!r}")
        for role, model in (("cheap", cascade.cheap), ("strong", cascade.strong)):
            if model not in items:
                raise ValueError(f"cascade {cid}: its {role} model {model} has no row")
        if items[cascade.cheap] != items[cascade.strong]:
            odd = sorted(items[cascade.cheap] ^ items[cascade.strong], key=str)[0]
            raise ValueError(f"cascade {cid}: {odd!r} has a row of only one of its two models")
        for task, item in sorted(items[cascade.cheap], key=str):
            cheap = cells[(task, item, cascade.cheap)]
            strong = cells[(task, item, cascade.strong)]
            label = cheap.get(LABEL, _MISSING)
            if label != strong.get(LABEL, _MISSING):
                raise ValueError(f"cascade {cid}: the two rows of item {item!r} disagree on {LABEL!r}")
            if cheap["correct"] is True and (cascade.cheap, item) in kinds:
                raise ValueError(f"cascade {cid}: a kind is given for the passed sample ({cascade.cheap!r}, "
                                 f"{item!r})")
            try:
                cell = cascade_cell(cheap, strong, kinds.get((cascade.cheap, item)), cascade.signal)
            except ValueError as exc:
                raise ValueError(f"cascade {cid}: ({cascade.cheap!r}, {item!r}): {exc}") from None
            out = {"task": task, "item": item, "model": cid, **cell}
            if label is not _MISSING:
                out[LABEL] = label
            added.append(out)
    return sorted([dict(row) for row in rows] + added, key=_key)
