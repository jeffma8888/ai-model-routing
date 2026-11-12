"""DESIGN 4.1, 9 and 13.2 v1.212 (row P1): long-prompt price tiers.

A `models.json` row can carry `price_tiers`, each a `PriceTier(above_input_tokens, price_in,
price_out)`. `Model.cost` prices one call: a call whose input is over a tier's threshold pays
the last such tier's prices on all of its tokens. `Model.base_cost` keeps the linear price at
`price_in` and `price_out`; from v1.219 the 13.2 decision prices a tiered model per call
(tests/test_delegation_tiers.py), and from v1.222 the 13.9 held-out costs do too
(tests/test_delegation_eval_tiers.py)."""

import dataclasses
import json
import math
from pathlib import Path

import pytest

import model_routing
from model_routing import (DATA_DIR, Completion, Executor, FakeProvider, Model, Registry,
                           Router, Stats, Task, outcomes_from_rows)

ROOT = Path(__file__).resolve().parents[1]
TASK = "t"


def tier(above, price_in, price_out):
    return model_routing.PriceTier(above, price_in, price_out)


def linear(tokens_in, tokens_out, price_in, price_out):
    return (tokens_in * price_in + tokens_out * price_out) / 1_000_000


def two_tiers():
    """Base 1/4; over 50,000 input tokens 3/9; over 200,000 input tokens 5/15."""
    return Model("t/long", "t", 1.0, 4.0, 1_000_000,
                 price_tiers=(tier(50_000, 3.0, 9.0), tier(200_000, 5.0, 15.0)))


def pair(with_tiers, above=50_000):
    """A parent and a delegate, each with a tier over ``above`` input tokens, or none."""
    big = (tier(above, 3.0, 9.0),) if with_tiers else ()
    small = (tier(above, 0.3, 0.9),) if with_tiers else ()
    return Registry([Model("t/long", "t", 1.0, 4.0, 1_000_000, price_tiers=big),
                     Model("s/small", "s", 0.1, 0.4, 1_000_000, price_tiers=small)])


def task(**fields):
    base = {"name": TASK, "bar": 0.7, "min_samples": 20, "independent_of_generator": False,
            "expected_input_tokens": 2_000, "expected_output_tokens": 500}
    base.update(fields)
    return Task(**base)


def router(registry, the_task):
    stats = Stats()
    for model in registry.models:
        stats.add(TASK, model.id, 95, 100)
    return Router(registry, {TASK: the_task}, stats)


def test_design_specifies_price_tiers():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for fragment in [
        "- v1.212 `@dataclass(frozen=True) class PriceTier`: `above_input_tokens: int`",
        "- v1.212 `Model.price_tiers: tuple[PriceTier, ...]`, default `()`, the last field",
        "- v1.212 the tier of a call: `Model.cost` prices one call. Its tier is the last of",
        "- v1.212 `Model.base_cost(input_tokens, output_tokens) -> float` returns the v1.211",
        "- v1.212 `Registry.load` reads the optional `price_tiers` key of a row",
        "`anthropic/claude-haiku-5.5`, `above_input_tokens` 100000, `price_in` 0.5, "
        "`price_out` 2.5",
        "`openai/gpt-6-astra`, 272000, 20 and 75",
        "- v1.212 every `Model.cost` that 13.2 and 13.9 name is `Model.base_cost` (4.1)",
        "- v1.212 (2026-11-10): spec and tests (row P1).",
    ]:
        assert text.count(fragment) == 1, fragment


def test_no_packaged_task_reaches_the_first_packaged_threshold():
    """Why every README transcript keeps its bytes: the lowest packaged threshold is 100,000."""
    raw = json.loads((DATA_DIR / "example_tasks.json").read_text(encoding="utf-8"))
    sizes = [row["expected_input_tokens"] for row in raw["tasks"]]
    assert len(sizes) == 8 and max(sizes) < 100_000  # v1.282: eight packaged tasks


def test_price_tier_fields_and_float_prices():
    t = tier(100_000, 1, 2)
    assert (t.above_input_tokens, t.price_in, t.price_out) == (100_000, 1.0, 2.0)
    assert type(t.price_in) is float and type(t.price_out) is float
    assert dataclasses.asdict(t) == {"above_input_tokens": 100_000, "price_in": 1.0,
                                     "price_out": 2.0}
    assert "PriceTier" in model_routing.__all__
    assert model_routing.PriceTier is model_routing.registry.PriceTier


@pytest.mark.parametrize("args", [
    (0, 1.0, 1.0), (-1, 1.0, 1.0), (True, 1.0, 1.0), (100_000.0, 1.0, 1.0), ("100000", 1.0, 1.0),
    (None, 1.0, 1.0), (1, -0.5, 1.0), (1, 1.0, -0.5), (1, math.nan, 1.0), (1, 1.0, math.inf),
    (1, True, 1.0), (1, 1.0, False), (1, "1", 1.0), (1, 1.0, None),
])
def test_price_tier_refuses_bad_values(args):
    with pytest.raises(ValueError):
        tier(*args)


def test_model_default_has_no_tiers_and_positional_fields_keep_their_meaning():
    model = Model("a/b", "a", 1.0, 2.0, 10, {"p": "b"}, "2026-12-31")
    assert model.price_tiers == ()
    assert (model.aliases, model.price_valid_until) == ({"p": "b"}, "2026-12-31")
    assert [f.name for f in dataclasses.fields(Model)][-1] == "price_tiers"


@pytest.mark.parametrize("tiers", [
    "list", "not a tier", "equal", "falling", "at the window", "over the window",
])
def test_model_refuses_bad_tier_lists(tiers):
    values = {
        "list": [tier(10, 1.0, 1.0)],
        "not a tier": (tier(10, 1.0, 1.0), (20, 1.0, 1.0)),
        "equal": (tier(10, 1.0, 1.0), tier(10, 2.0, 2.0)),
        "falling": (tier(20, 1.0, 1.0), tier(10, 2.0, 2.0)),
        "at the window": (tier(1_000, 1.0, 1.0),),
        "over the window": (tier(1_001, 1.0, 1.0),),
    }[tiers]
    with pytest.raises(ValueError):
        Model("a/b", "a", 1.0, 2.0, 1_000, price_tiers=values)


def test_a_tier_just_below_the_window_is_allowed():
    assert Model("a/b", "a", 1.0, 2.0, 1_000, price_tiers=(tier(999, 1.0, 1.0),)).price_tiers


@pytest.mark.parametrize("tokens_in, tokens_out, price_in, price_out", [
    (0, 0, 1.0, 4.0),
    (50_000, 1_000, 1.0, 4.0),      # at the first threshold: not over it
    (50_001, 1_000, 3.0, 9.0),      # one over: the whole call at the first tier
    (200_000, 10, 3.0, 9.0),        # at the second threshold
    (200_001, 10, 5.0, 15.0),       # one over: the last tier it is over
    (999_999, 7, 5.0, 15.0),
])
def test_cost_prices_one_call_at_the_last_tier_its_input_is_over(tokens_in, tokens_out,
                                                                  price_in, price_out):
    model = two_tiers()
    assert model.cost(tokens_in, tokens_out) == linear(tokens_in, tokens_out, price_in, price_out)
    assert model.base_cost(tokens_in, tokens_out) == linear(tokens_in, tokens_out, 1.0, 4.0)


@pytest.mark.parametrize("tokens_in, tokens_out", [
    (0, 0), (1, 1), (3_000, 150), (89_000, 1_500), (1_049_999, 128_000), (12_345.5, 0),
])
def test_without_tiers_cost_and_base_cost_are_the_v1_211_value(tokens_in, tokens_out):
    model = Model("a/b", "a", 0.1, 0.5, 1_050_000)
    assert model.cost(tokens_in, tokens_out) == linear(tokens_in, tokens_out, 0.1, 0.5)
    assert model.base_cost(tokens_in, tokens_out) == model.cost(tokens_in, tokens_out)


def write(tmp_path, rows):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": rows}), encoding="utf-8")
    return path


def row(model_id, **extra):
    base = {"id": model_id, "family": "a", "price_in": 1, "price_out": 2,
            "context_window": 1_000_000}
    base.update(extra)
    return base


def test_registry_load_reads_price_tiers(tmp_path):
    path = write(tmp_path, [
        row("a/tiered", price_tiers=[{"above_input_tokens": 100_000, "price_in": 0.5,
                                      "price_out": 2.5, "note": "ignored"},
                                     {"above_input_tokens": 500_000, "price_in": 1,
                                      "price_out": 3}]),
        row("a/null", price_tiers=None),
        row("a/absent"),
        row("a/empty", price_tiers=[]),
    ])
    registry = Registry.load(path)
    assert registry.get("a/tiered").price_tiers == (tier(100_000, 0.5, 2.5),
                                                    tier(500_000, 1.0, 3.0))
    for model_id in ("a/null", "a/absent", "a/empty"):
        assert registry.get(model_id).price_tiers == ()


@pytest.mark.parametrize("value", [
    "tiers", {"above_input_tokens": 1, "price_in": 1, "price_out": 1},
    [[100_000, 0.5, 2.5]], [{"price_in": 1, "price_out": 1}],
    [{"above_input_tokens": 1, "price_out": 1}], [{"above_input_tokens": 1, "price_in": 1}],
    [{"above_input_tokens": True, "price_in": 1, "price_out": 1}],
    [{"above_input_tokens": 1, "price_in": "1", "price_out": 1}],
    [{"above_input_tokens": 2, "price_in": 1, "price_out": 1},
     {"above_input_tokens": 1, "price_in": 1, "price_out": 1}],
    [{"above_input_tokens": 1_000_000, "price_in": 1, "price_out": 1}],
])
def test_registry_load_refuses_bad_price_tiers_naming_the_file(tmp_path, value):
    path = write(tmp_path, [row("a/bad", price_tiers=value)])
    with pytest.raises(ValueError, match="models.json"):
        Registry.load(path)


def test_asdict_round_trips_a_tiered_model(tmp_path):
    model = two_tiers()
    path = write(tmp_path, [dataclasses.asdict(model)])
    assert Registry.load(path).get("t/long") == model


def test_packaged_registry_tiers():
    raw = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))
    assert (raw["version"], raw["as_of"]) == ("2026.10.29", "2026-10-29")
    registry = Registry.load(DATA_DIR / "models.json")
    expected = {"anthropic/claude-haiku-5.5": (tier(100_000, 0.5, 2.5),),
                "openai/gpt-6-astra": (tier(272_000, 20.0, 75.0),)}
    assert len(registry) == 12 and "xai/grok-4.7" in registry
    for model in registry.models:
        assert model.price_tiers == expected.get(model.id, ()), model.id
    haiku = registry.get("anthropic/claude-haiku-5.5")
    astra = registry.get("openai/gpt-6-astra")
    assert (haiku.price_in, haiku.price_out, astra.price_in, astra.price_out) == (0.1, 0.5, 10, 50)
    assert haiku.cost(100_000, 1_000) == linear(100_000, 1_000, 0.1, 0.5)
    assert haiku.cost(100_001, 1_000) == linear(100_001, 1_000, 0.5, 2.5)
    assert astra.cost(272_001, 1_000) == linear(272_001, 1_000, 20.0, 75.0)
    grok = registry.get("xai/grok-4.7")
    assert grok.cost(300_000, 1_000) == linear(300_000, 1_000, 2.0, 6.0)


def test_router_prices_one_call_of_the_task_sizes_at_its_tier():
    registry = pair(True)
    decision = router(registry, task(expected_input_tokens=60_000,
                                     expected_output_tokens=1_000)).select(TASK)
    costs = {c.model_id: c.list_cost for c in decision.candidates}
    assert costs == {"t/long": linear(60_000, 1_000, 3.0, 9.0),
                     "s/small": linear(60_000, 1_000, 0.3, 0.9)}


def test_executor_records_the_tier_price_of_each_attempt():
    registry = pair(True)
    provider = FakeProvider({m.id: (lambda messages: Completion("ok", 60_000, 1_000))
                             for m in registry.models})
    result = Executor(router(registry, task()), provider).call(
        TASK, [{"role": "user", "content": "hello"}])
    assert result.model == "s/small"
    assert result.attempts[0].cost_usd == linear(60_000, 1_000, 0.3, 0.9)


def test_evaluate_prices_a_token_form_row_as_one_call():
    rows = [{"task": TASK, "item": "i1", "model": "t/long", "correct": True,
             "input_tokens": 60_000, "output_tokens": 1_000},
            {"task": TASK, "item": "i2", "model": "t/long", "correct": True,
             "input_tokens": 40_000, "output_tokens": 1_000}]
    outcomes = outcomes_from_rows(rows, pair(True))
    assert [o.cost_usd for o in outcomes] == [linear(60_000, 1_000, 3.0, 9.0),
                                              linear(40_000, 1_000, 1.0, 4.0)]


README_HEADER = ("Pricing notes (a row's `price_tiers` in `models.json` prices a long-prompt tier "
                 "whose page states its rates; see Limitations):")
README_NOTES = [
    "- claude-haiku-5.5: short-prompt tier, prompts up to 100K tokens; longer prompts cost 0.50 "
    "in and 2.50 out, and its `models.json` row prices them as a tier over 100,000 input tokens",
    "- gpt-6-astra: prompts over 272K input tokens are billed at 2x input and 1.5x output, and "
    "its `models.json` row prices them as a tier over 272,000 input tokens at 20 in and 75 out",
    "- grok-4.7: price for context up to 200K tokens; higher beyond that, at rates its page does "
    "not state, so its `models.json` row has no tier and a longer call is costed at 2 / 6",
]
README_LIMITATION = (
    "- A long-prompt tier is costed per call where `models.json` gives its rates (`price_tiers`, `DESIGN.md` 4.1): a call whose input is over the tier's threshold pays the tier's prices on all of its input and output tokens, as the claude-haiku-5.5 and gpt-6-astra pages state, and the inline-or-delegate cost and the held-out costs of the delegation evidence price each work call and each later parent call at its own tier (`DESIGN.md` 13.2, 13.9). Only grok-4.7 over 200K input tokens stays at the base prices, so a call there is under-costed: its page says the rates are higher without stating them. The parent's own output in a later call, its next step after the work, is charged on neither path, since no input gives it a size, so where a path's additions take that call over a threshold the higher price of that output is left out. A task whose line is a whole conversation, such as `tool_calling_support_agent`, is costed as one call of the conversation's summed sizes, so a tiered model can be costed at its higher price although each of its calls is shorter")


def section(text, heading):
    lines = text.split("\n")
    start = lines.index(heading)
    end = next(i for i in range(start + 1, len(lines)) if lines[i].startswith("## "))
    return lines[start + 1:end]


def test_readme_pricing_notes_and_limitation():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    lines = text.split("\n")
    assert lines.count(README_HEADER) == 1
    notes = [line for line in lines[lines.index(README_HEADER) + 1:][:12]
             if line.startswith("- ")]
    assert [notes[0], notes[1], notes[3]] == README_NOTES
    limitations = section(text, "## Limitations and non-goals (v1)")
    assert limitations.count(README_LIMITATION) == 1
    assert not any("Cost is linear" in line or "is not modelled, so long-context" in line
                   for line in lines)
    # v1.242 (row P1d): the parent's own output is uncharged, not at the base prices
    assert not any("Two costs stay at the base prices" in line for line in lines)
