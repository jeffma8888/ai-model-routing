"""v1.3 offline evaluator contract (DESIGN section 12), written before the module exists.

They were held under a module-level strict xfail until ``evaluate.py`` landed;
the implementing commit removed that marker (DESIGN 12.5).
"""

import hashlib
import importlib
import json
import re
from math import fsum

import pytest

from model_routing import Model, Registry, Router, Stats, Task, main, wilson_lower_bound

MODELS = ("fiction/best", "fiction/cheap", "fiction/mid")
COST = {"fiction/cheap": 0.001, "fiction/mid": 0.01, "fiction/best": 0.1}
STRATEGIES = ["routed", "oracle", "best_on_calibration", "cheapest",
              "model:fiction/best", "model:fiction/cheap", "model:fiction/mid"]
EASY = [f"easy-{i:03d}" for i in range(100)]
HARD = [f"hard-{i:03d}" for i in range(100)]


def load_ev():
    return importlib.import_module("model_routing.evaluate")


def in_calibration(item, seed, fraction=0.5):
    digest = hashlib.sha256(f"{seed}:{item}".encode("utf-8")).digest()
    return int.from_bytes(digest[:8], "big") < fraction * 2 ** 64


def rows_for(task, items, rule):
    """``rule[model](item)`` says whether that model is correct on that item."""
    return [{"task": task, "item": item, "model": model,
             "correct": bool(rule[model](item)), "cost_usd": COST[model]}
            for item in items for model in MODELS]


def always(value):
    return lambda item: value


def known_rows():
    """easy: every model always right. hard: cheap always wrong, mid and best always right."""
    return (rows_for("easy", EASY, {m: always(True) for m in MODELS})
            + rows_for("hard", HARD, {"fiction/cheap": always(False),
                                      "fiction/mid": always(True),
                                      "fiction/best": always(True)}))


def cell(result, bar, flavor, seed, task):
    found = [c for c in result["cells"] if (c["bar"], c["flavor"], c["seed"], c["task"])
             == (bar, flavor, seed, task)]
    assert len(found) == 1
    return found[0]


def row(rows, **key):
    found = [r for r in rows if all(r[k] == v for k, v in key.items())]
    assert len(found) == 1, key
    return found[0]


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


# 12.2 split

def test_split_matches_the_pinned_sha256_rule():
    ev = load_ev()
    for seed in (0, 1, 7):
        calibration, held_out = ev.split_items(EASY, seed)
        assert calibration == tuple(sorted(i for i in EASY if in_calibration(i, seed)))
        assert held_out == tuple(sorted(i for i in EASY if not in_calibration(i, seed)))
        assert calibration and held_out
    assert ev.split_items(EASY, 0) != ev.split_items(EASY, 1)


def test_split_known_vector():
    ev = load_ev()
    items = list("abcdefghij")
    assert ev.split_items(items, 0) == (("d", "f", "g", "h"), ("a", "b", "c", "e", "i", "j"))
    assert ev.split_items(items, 1) == (("a", "b", "d", "e", "f", "g", "i", "j"), ("c", "h"))


def test_split_ignores_input_order_and_collapses_duplicates():
    ev = load_ev()
    shuffled = list(reversed(EASY)) + EASY[:5]
    assert ev.split_items(shuffled, 3) == ev.split_items(EASY, 3)


def test_split_fraction_sets_the_threshold():
    ev = load_ev()
    small, _ = ev.split_items(EASY, 4, calibration_fraction=0.2)
    large, _ = ev.split_items(EASY, 4, calibration_fraction=0.8)
    assert small == tuple(sorted(i for i in EASY if in_calibration(i, 4, 0.2)))
    assert set(small) < set(large)


@pytest.mark.parametrize("fraction", [0.0, 1.0, -0.1, 1.5])
def test_split_fraction_must_be_inside_the_open_unit_interval(fraction):
    ev = load_ev()
    with pytest.raises(ValueError):
        ev.split_items(EASY, 0, calibration_fraction=fraction)


# 12.1 outcome matrix

def test_rows_become_outcomes_in_input_order():
    ev = load_ev()
    outcomes = ev.outcomes_from_rows(known_rows())
    assert isinstance(outcomes, tuple) and len(outcomes) == 600
    assert outcomes[0] == ev.Outcome("easy", "easy-000", "fiction/best", True, 0.1)
    assert outcomes[-1] == ev.Outcome("hard", "hard-099", "fiction/mid", True, 0.01)


def test_token_rows_are_priced_with_the_registry(registry):
    ev = load_ev()
    rows = [{"task": "t", "item": "a", "model": "fiction/cheap", "correct": True,
             "input_tokens": 1000, "output_tokens": 500, "note": "extra keys are ignored"}]
    (outcome,) = ev.outcomes_from_rows(rows, registry)
    assert outcome.cost_usd == pytest.approx(registry.get("fiction/cheap").cost(1000, 500))
    assert outcome.cost_usd == pytest.approx(0.002)


def test_cost_usd_wins_over_token_counts(registry):
    ev = load_ev()
    rows = [{"task": "t", "item": "a", "model": "fiction/cheap", "correct": False,
             "cost_usd": 0.5, "input_tokens": 1000, "output_tokens": 500}]
    assert ev.outcomes_from_rows(rows, registry)[0].cost_usd == pytest.approx(0.5)


def test_token_rows_need_a_registry_that_knows_the_model(registry):
    ev = load_ev()
    base = {"task": "t", "item": "a", "correct": True, "input_tokens": 1, "output_tokens": 1}
    with pytest.raises(ValueError):
        ev.outcomes_from_rows([dict(base, model="fiction/cheap")])
    with pytest.raises(ValueError):
        ev.outcomes_from_rows([dict(base, model="fiction/unknown")], registry)


GOOD = {"task": "t", "item": "a", "model": "fiction/cheap", "correct": True, "cost_usd": 0.1}


@pytest.mark.parametrize("bad", [
    ["not a dict"],
    [dict(GOOD, correct="true")],
    [dict(GOOD, correct=1)],
    [{k: v for k, v in GOOD.items() if k != "correct"}],
    [{k: v for k, v in GOOD.items() if k != "task"}],
    [dict(GOOD, model="")],
    [dict(GOOD, item=5)],
    [dict(GOOD, cost_usd=-0.1)],
    [dict(GOOD, cost_usd=True)],
    [dict(GOOD, cost_usd="0.1")],
    [dict(GOOD, cost_usd=float("inf"))],
    [{k: v for k, v in GOOD.items() if k != "cost_usd"}],
    [dict({k: v for k, v in GOOD.items() if k != "cost_usd"}, input_tokens=10)],
    [dict({k: v for k, v in GOOD.items() if k != "cost_usd"}, input_tokens=1.5, output_tokens=1)],
    [dict({k: v for k, v in GOOD.items() if k != "cost_usd"}, input_tokens=-1, output_tokens=1)],
    [dict({k: v for k, v in GOOD.items() if k != "cost_usd"}, input_tokens=True, output_tokens=1)],
    [GOOD, dict(GOOD, correct=False)],
], ids=["not-dict", "correct-str", "correct-int", "no-correct", "no-task", "empty-model",
        "item-int", "cost-negative", "cost-bool", "cost-str", "cost-inf", "no-cost",
        "one-token-count", "tokens-float", "tokens-negative", "tokens-bool", "duplicate"])
def test_invalid_rows_raise_value_error(bad, registry):
    ev = load_ev()
    with pytest.raises(ValueError):
        ev.outcomes_from_rows(bad, registry)


def test_load_outcomes_skips_blank_lines_and_matches_from_rows(tmp_path):
    ev = load_ev()
    rows = known_rows()[:6]
    path = tmp_path / "outcomes.jsonl"
    path.write_text(json.dumps(rows[0]) + "\n\n" + "".join(json.dumps(r) + "\n" for r in rows[1:]),
                    encoding="utf-8")
    assert ev.load_outcomes(path) == ev.outcomes_from_rows(rows)


@pytest.mark.parametrize("bad_line", ["{not json", "[1, 2]"])
def test_load_outcomes_names_path_and_line(tmp_path, bad_line):
    ev = load_ev()
    path = tmp_path / "outcomes.jsonl"
    path.write_text(json.dumps(GOOD) + "\n\n" + bad_line + "\n", encoding="utf-8")
    with pytest.raises(ValueError, match=r"outcomes\.jsonl:3"):
        ev.load_outcomes(path)


# 12.3 evaluate: validation

def test_incomplete_matrix_names_the_missing_cell():
    ev = load_ev()
    rows = [r for r in known_rows()
            if not (r["task"] == "hard" and r["item"] == "hard-042" and r["model"] == "fiction/mid")]
    with pytest.raises(ValueError, match="hard-042") as info:
        ev.evaluate(ev.outcomes_from_rows(rows), bars=[0.8], seeds=[0])
    assert "fiction/mid" in str(info.value)


@pytest.mark.parametrize("kwargs", [
    {"bars": []}, {"bars": [1.1]}, {"bars": [-0.1]}, {"seeds": []},
    {"flavors": ()}, {"flavors": ("cheap",)}, {"min_samples": 0},
    {"confidence": 1.0}, {"confidence": 0.0}, {"calibration_fraction": 0.0},
    {"calibration_fraction": 1.0}, {"bars": [float("nan")]}, {"bars": [True]},
    {"bars": ["0.8"]}, {"bars": [0.8, 0.8]}, {"seeds": [0, 0]}, {"seeds": [True]},
    {"seeds": [1.5]}, {"seeds": ["0"]},
    {"flavors": ("cost_effective", "cost_effective")},
], ids=lambda kw: next(iter(kw)) + "=" + repr(next(iter(kw.values()))))
def test_invalid_arguments_raise_value_error(kwargs):
    ev = load_ev()
    args = dict(bars=[0.8], seeds=[0])
    args.update(kwargs)
    with pytest.raises(ValueError):
        ev.evaluate(ev.outcomes_from_rows(known_rows()), **args)


def test_no_outcomes_raise_value_error():
    ev = load_ev()
    with pytest.raises(ValueError):
        ev.evaluate((), bars=[0.8], seeds=[0])


def test_a_split_with_an_empty_side_names_task_and_seed():
    ev = load_ev()
    rows = rows_for("tiny", ["only-item"], {m: always(True) for m in MODELS})
    with pytest.raises(ValueError, match="tiny") as info:
        ev.evaluate(ev.outcomes_from_rows(rows), bars=[0.8], seeds=[5])
    assert re.search(r"\b5\b", str(info.value))


# 12.3 evaluate: known answers

def test_config_tasks_and_cell_order():
    ev = load_ev()
    result = ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.9, 0.8], seeds=range(2))
    assert result["config"] == {"bars": [0.9, 0.8], "seeds": [0, 1],
                                "flavors": ["cost_effective", "cost_blind"],
                                "calibration_fraction": 0.5, "min_samples": 30,
                                "confidence": 0.95}
    assert result["tasks"] == {"easy": {"items": 100, "models": list(MODELS)},
                               "hard": {"items": 100, "models": list(MODELS)}}
    order = [(c["bar"], c["flavor"], c["seed"], c["task"]) for c in result["cells"]]
    assert order == [(b, f, s, t) for b in (0.9, 0.8) for f in ("cost_effective", "cost_blind")
                     for s in (0, 1) for t in ("easy", "hard")]
    first = result["cells"][0]
    assert set(first) == {"bar", "flavor", "seed", "task", "calibration_items", "held_out_items",
                          "cleared", "models", "success", "cost_usd"}
    assert list(first["success"]) == STRATEGIES and list(first["cost_usd"]) == STRATEGIES
    assert set(first["models"]) == {"routed", "best_on_calibration", "cheapest"}


def test_default_seeds_are_zero_to_nine():
    ev = load_ev()
    result = ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.8])
    assert result["config"]["seeds"] == list(range(10))


@pytest.mark.parametrize("flavor,task,routed", [
    ("cost_effective", "easy", "fiction/cheap"),
    ("cost_effective", "hard", "fiction/mid"),
    ("cost_blind", "easy", "fiction/best"),
    ("cost_blind", "hard", "fiction/best"),
])
def test_routed_model_follows_the_router_rules(flavor, task, routed):
    # cost_blind ties on quality_lb break by model ID (5.3), so fiction/best wins
    ev = load_ev()
    result = ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.8], seeds=[0, 1, 2])
    for seed in (0, 1, 2):
        c = cell(result, 0.8, flavor, seed, task)
        assert c["models"]["routed"] == routed
        assert c["cleared"] is True
        assert c["success"]["routed"] == 1.0
        assert c["cost_usd"]["routed"] == pytest.approx(c["held_out_items"] * COST[routed])


def test_routed_choice_matches_router_select_on_the_calibration_split():
    ev = load_ev()
    calibration, _ = ev.split_items(HARD, 0)
    stats = Stats()
    stats.add("hard", "fiction/cheap", 0, len(calibration))
    stats.add("hard", "fiction/mid", len(calibration), len(calibration))
    stats.add("hard", "fiction/best", len(calibration), len(calibration))
    registry = Registry([Model(m, m.split("/")[0], COST[m] * 1_000_000, 0.0, 10 ** 9)
                         for m in MODELS])
    task = Task(name="hard", bar=0.8, min_samples=30, expected_input_tokens=1,
                expected_output_tokens=0, independent_of_generator=False,
                on_no_model="best_available")
    expected = Router(registry, {"hard": task}, stats).select("hard").primary
    result = ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.8], seeds=[0],
                         flavors=("cost_effective",))
    assert cell(result, 0.8, "cost_effective", 0, "hard")["models"]["routed"] == expected


def test_baselines_on_known_matrix():
    ev = load_ev()
    result = ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.8], seeds=[0, 1])
    for c in result["cells"]:
        n = c["held_out_items"]
        items = EASY if c["task"] == "easy" else HARD
        assert c["calibration_items"] == sum(in_calibration(i, c["seed"]) for i in items)
        assert c["calibration_items"] + n == 100
        assert c["models"]["cheapest"] == "fiction/cheap"
        if c["task"] == "easy":
            assert c["models"]["best_on_calibration"] == "fiction/cheap"  # tie, cheaper wins
            assert c["success"]["cheapest"] == 1.0
            assert c["cost_usd"]["oracle"] == pytest.approx(n * 0.001)
        else:
            assert c["models"]["best_on_calibration"] == "fiction/mid"
            assert c["success"]["cheapest"] == 0.0
            assert c["success"]["model:fiction/cheap"] == 0.0
            assert c["cost_usd"]["oracle"] == pytest.approx(n * 0.01)
        assert c["success"]["oracle"] == 1.0
        assert c["success"]["model:fiction/best"] == 1.0
        assert c["cost_usd"]["model:fiction/best"] == pytest.approx(n * 0.1)


def test_oracle_pays_the_cheapest_cost_when_no_model_is_right():
    ev = load_ev()
    rows = rows_for("none", EASY, {m: always(False) for m in MODELS})
    result = ev.evaluate(ev.outcomes_from_rows(rows), bars=[0.5], seeds=[0],
                         flavors=("cost_effective",))
    c = cell(result, 0.5, "cost_effective", 0, "none")
    assert c["success"]["oracle"] == 0.0
    assert c["cost_usd"]["oracle"] == pytest.approx(c["held_out_items"] * 0.001)


def test_summary_rows_on_known_matrix():
    ev = load_ev()
    seeds = [0, 1, 2]
    result = ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.8], seeds=seeds)
    held = {(s, t): cell(result, 0.8, "cost_effective", s, t)["held_out_items"]
            for s in seeds for t in ("easy", "hard")}
    keys = [(r["bar"], r["flavor"], r["strategy"]) for r in result["summary"]]
    assert keys == [(0.8, f, s) for f in ("cost_effective", "cost_blind") for s in STRATEGIES]
    routed = row(result["summary"], flavor="cost_effective", strategy="routed")
    assert set(routed) == {"bar", "flavor", "strategy", "success", "cost_usd",
                           "below_bar_rate", "cleared_rate", "bar_violation_rate"}
    assert routed["success"] == pytest.approx(1.0)
    assert routed["cleared_rate"] == 1.0 and routed["bar_violation_rate"] == 0.0
    assert routed["below_bar_rate"] == 0.0
    assert routed["cost_usd"] == pytest.approx(
        fsum(held[s, "easy"] * 0.001 + held[s, "hard"] * 0.01 for s in seeds) / len(seeds))
    cheapest = row(result["summary"], flavor="cost_effective", strategy="cheapest")
    assert cheapest["success"] == pytest.approx(
        fsum(held[s, "easy"] / (held[s, "easy"] + held[s, "hard"]) for s in seeds) / len(seeds))
    assert cheapest["below_bar_rate"] == 0.5
    assert cheapest["cleared_rate"] is None and cheapest["bar_violation_rate"] is None


def test_per_task_rows_count_routed_models_per_seed():
    ev = load_ev()
    result = ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.8], seeds=[0, 1, 2])
    keys = [(r["bar"], r["flavor"], r["task"], r["strategy"]) for r in result["per_task"]]
    assert keys == [(0.8, f, t, s) for f in ("cost_effective", "cost_blind")
                    for t in ("easy", "hard") for s in STRATEGIES]
    hard = row(result["per_task"], flavor="cost_effective", task="hard", strategy="routed")
    assert hard["routed_models"] == {"fiction/mid": 3}
    assert hard["success"] == 1.0 and hard["bar_violation_rate"] == 0.0
    cheap = row(result["per_task"], flavor="cost_effective", task="hard", strategy="cheapest")
    assert cheap["routed_models"] is None
    assert cheap["success"] == 0.0 and cheap["below_bar_rate"] == 1.0


def test_a_model_that_only_fits_the_calibration_split_is_a_bar_violation():
    ev = load_ev()
    items = [f"leaky-{i:03d}" for i in range(100)]
    calibration = [i for i in items if in_calibration(i, 0)]
    assert len(calibration) >= 30 and len(calibration) < len(items)
    rows = rows_for("leaky", items, {"fiction/cheap": lambda i: in_calibration(i, 0),
                                     "fiction/mid": always(True), "fiction/best": always(True)})
    result = ev.evaluate(ev.outcomes_from_rows(rows), bars=[0.8], seeds=[0],
                         flavors=("cost_effective",))
    c = cell(result, 0.8, "cost_effective", 0, "leaky")
    assert c["models"]["routed"] == "fiction/cheap" and c["cleared"] is True
    assert c["success"]["routed"] == 0.0
    routed = row(result["summary"], strategy="routed")
    assert routed["bar_violation_rate"] == 1.0 and routed["below_bar_rate"] == 1.0
    assert c["success"]["oracle"] == 1.0


def test_bar_violation_rate_counts_cleared_cells_only():
    # three tasks, one seed: leaky clears and misses, steady clears and holds,
    # dead never clears and misses; cleared 2/3, violations 1 of the 2 cleared
    ev = load_ev()
    leaky = [f"leaky-{i:03d}" for i in range(100)]
    steady = [f"steady-{i:03d}" for i in range(100)]
    dead = [f"dead-{i:03d}" for i in range(100)]
    for items in (leaky, steady):
        assert sum(in_calibration(i, 0) for i in items) >= 30
    rows = (rows_for("leaky", leaky, {"fiction/cheap": lambda i: in_calibration(i, 0),
                                      "fiction/mid": always(True), "fiction/best": always(True)})
            + rows_for("steady", steady, {m: always(True) for m in MODELS})
            + rows_for("dead", dead, {m: always(False) for m in MODELS}))
    result = ev.evaluate(ev.outcomes_from_rows(rows), bars=[0.8], seeds=[0],
                         flavors=("cost_effective",))
    assert [cell(result, 0.8, "cost_effective", 0, t)["cleared"]
            for t in ("dead", "leaky", "steady")] == [False, True, True]
    routed = row(result["summary"], strategy="routed")
    assert routed["cleared_rate"] == pytest.approx(2 / 3)
    assert routed["bar_violation_rate"] == 0.5
    assert routed["below_bar_rate"] == pytest.approx(2 / 3)
    per = {t: row(result["per_task"], task=t, strategy="routed") for t in ("dead", "leaky", "steady")}
    assert (per["dead"]["cleared_rate"], per["dead"]["bar_violation_rate"]) == (0.0, None)
    assert per["dead"]["below_bar_rate"] == 1.0
    assert (per["leaky"]["cleared_rate"], per["leaky"]["bar_violation_rate"]) == (1.0, 1.0)
    assert (per["steady"]["cleared_rate"], per["steady"]["bar_violation_rate"]) == (1.0, 0.0)


def test_routing_cost_is_the_mean_calibration_cost():
    # cheap costs little on seed-0 calibration items and a lot on held-out ones:
    # ranking by its overall mean would pick mid, ranking by calibration mean picks cheap
    ev = load_ev()
    items = [f"varied-{i:03d}" for i in range(100)]
    rows = rows_for("varied", items, {m: always(True) for m in MODELS})
    for r in rows:
        if r["model"] == "fiction/cheap":
            r["cost_usd"] = 0.001 if in_calibration(r["item"], 0) else 1.0
    held = [i for i in items if not in_calibration(i, 0)]
    result = ev.evaluate(ev.outcomes_from_rows(rows), bars=[0.8], seeds=[0],
                         flavors=("cost_effective",))
    c = cell(result, 0.8, "cost_effective", 0, "varied")
    assert c["models"]["routed"] == "fiction/cheap"
    assert c["models"]["cheapest"] == "fiction/cheap"
    assert c["models"]["best_on_calibration"] == "fiction/cheap"
    assert c["cost_usd"]["routed"] == pytest.approx(len(held) * 1.0)
    assert c["cost_usd"]["oracle"] == pytest.approx(len(held) * 0.01)


def test_ties_break_by_model_id():
    ev = load_ev()
    rows = [{"task": "tie", "item": f"tie-{i:03d}", "model": m, "correct": True, "cost_usd": 0.01}
            for i in range(100) for m in ("fiction/b", "fiction/a")]
    result = ev.evaluate(ev.outcomes_from_rows(rows), bars=[0.8], seeds=[0],
                         flavors=("cost_effective",))
    c = cell(result, 0.8, "cost_effective", 0, "tie")
    assert c["models"] == {"routed": "fiction/a", "best_on_calibration": "fiction/a",
                           "cheapest": "fiction/a"}


def test_confidence_reaches_the_admission_rule():
    ev = load_ev()
    n = sum(in_calibration(i, 0) for i in EASY)
    bar = (wilson_lower_bound(n, n, 0.95) + wilson_lower_bound(n, n, 0.99)) / 2
    rows = rows_for("easy", EASY, {m: always(True) for m in MODELS})
    loose = ev.evaluate(ev.outcomes_from_rows(rows), bars=[bar], seeds=[0], confidence=0.95)
    tight = ev.evaluate(ev.outcomes_from_rows(rows), bars=[bar], seeds=[0], confidence=0.99)
    assert cell(loose, bar, "cost_effective", 0, "easy")["cleared"] is True
    assert cell(tight, bar, "cost_effective", 0, "easy")["cleared"] is False
    assert tight["config"]["confidence"] == 0.99


def test_calibration_fraction_reaches_the_split():
    ev = load_ev()
    result = ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.8], seeds=[0],
                         calibration_fraction=0.2)
    c = cell(result, 0.8, "cost_effective", 0, "easy")
    assert c["calibration_items"] == sum(in_calibration(i, 0, 0.2) for i in EASY)
    assert result["config"]["calibration_fraction"] == 0.2


def test_no_model_clears_serves_best_available_and_is_not_a_violation():
    # 100% on about 50 calibration items has a Wilson lower bound near 0.93, below 0.99
    ev = load_ev()
    rows = rows_for("easy", EASY, {m: always(True) for m in MODELS})
    result = ev.evaluate(ev.outcomes_from_rows(rows), bars=[0.99], seeds=[0])
    effective = cell(result, 0.99, "cost_effective", 0, "easy")
    blind = cell(result, 0.99, "cost_blind", 0, "easy")
    assert effective["cleared"] is False and blind["cleared"] is False
    assert effective["models"]["routed"] == "fiction/cheap"
    assert blind["models"]["routed"] == "fiction/best"
    summary = row(result["summary"], flavor="cost_effective", strategy="routed")
    assert summary["cleared_rate"] == 0.0 and summary["bar_violation_rate"] is None
    assert summary["below_bar_rate"] == 0.0


def test_min_samples_above_the_calibration_size_never_clears():
    ev = load_ev()
    result = ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.8], seeds=[0],
                         min_samples=1000)
    assert all(c["cleared"] is False for c in result["cells"])
    assert cell(result, 0.8, "cost_effective", 0, "hard")["models"]["routed"] == "fiction/mid"


def test_evaluate_is_deterministic_and_independent_of_row_order():
    ev = load_ev()
    rows = known_rows()
    first = ev.evaluate(ev.outcomes_from_rows(rows), bars=[0.8, 0.9], seeds=[0, 1])
    again = ev.evaluate(ev.outcomes_from_rows(list(reversed(rows))), bars=[0.8, 0.9],
                        seeds=[0, 1])
    assert first == again
    assert json.dumps(first, sort_keys=True) == json.dumps(again, sort_keys=True)


# 12.5 exports

def test_names_are_reexported_from_the_package():
    ev = load_ev()
    import model_routing
    for name in ("Outcome", "outcomes_from_rows", "load_outcomes", "split_items", "evaluate"):
        assert name in model_routing.__all__
        assert getattr(model_routing, name) is getattr(ev, name)


# 12.4 CLI

def test_cli_json_matches_the_api_without_cells(tmp_path, capsys):
    ev = load_ev()
    path = write_jsonl(tmp_path / "outcomes.jsonl", known_rows())
    code = main(["evaluate", "--outcomes", str(path), "--bar", "0.8", "--bar", "0.9",
                 "--seeds", "2", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert set(out) == {"config", "tasks", "summary", "per_task"}
    expected = ev.evaluate(ev.load_outcomes(path), bars=[0.8, 0.9], seeds=range(2))
    expected = json.loads(json.dumps(expected))
    assert out["config"] == expected["config"]
    assert out["tasks"] == expected["tasks"]
    assert out["summary"] == expected["summary"]
    assert out["per_task"] == expected["per_task"]


def test_cli_multi_value_bar_and_admission_options_reach_config(tmp_path, capsys):
    load_ev()
    path = write_jsonl(tmp_path / "outcomes.jsonl", known_rows())
    code = main(["evaluate", "--outcomes", str(path), "--bar", "0.8", "0.9", "--seeds", "1",
                 "--min-samples", "20", "--confidence", "0.9", "--json"])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    assert out["config"]["bars"] == [0.8, 0.9]
    assert (out["config"]["min_samples"], out["config"]["confidence"]) == (20, 0.9)


def test_cli_table_names_every_flavor_and_strategy(tmp_path, capsys):
    load_ev()
    path = write_jsonl(tmp_path / "outcomes.jsonl", known_rows())
    code = main(["evaluate", "--outcomes", str(path), "--seeds", "1"])
    out = capsys.readouterr().out
    assert code == 0
    for word in ["cost_effective", "cost_blind", "bar_violation_rate", *STRATEGIES]:
        assert word in out


def test_cli_prices_token_rows_with_the_registry_option(tmp_path, capsys, cli_files):
    load_ev()
    rows = [{k: v for k, v in r.items() if k != "cost_usd"} for r in known_rows()]
    for r in rows:
        r.update(input_tokens=1000, output_tokens=0)
    path = write_jsonl(tmp_path / "outcomes.jsonl", rows)
    code = main(["evaluate", "--outcomes", str(path), "--seeds", "1", "--json",
                 "--registry", str(cli_files["registry"])])
    out = json.loads(capsys.readouterr().out)
    assert code == 0
    # conftest registry: cheap 1.0, mid 3.0 USD per 1M input tokens, so 0.001 and 0.003 a call
    held_easy = sum(not in_calibration(i, 0) for i in EASY)
    held_hard = sum(not in_calibration(i, 0) for i in HARD)
    effective = row(out["summary"], flavor="cost_effective", strategy="routed")
    assert effective["cost_usd"] == pytest.approx(held_easy * 0.001 + held_hard * 0.003)


@pytest.mark.parametrize("case", ["missing-file", "bad-row", "incomplete", "bar", "seeds",
                                  "fraction", "unpriced-tokens", "flavor", "repeated-flavor"])
def test_cli_bad_input_exits_2(tmp_path, capsys, case):
    load_ev()
    good = write_jsonl(tmp_path / "good.jsonl", known_rows())
    args = ["evaluate", "--outcomes", str(good), "--seeds", "1"]
    if case == "missing-file":
        args[2] = str(tmp_path / "absent.jsonl")
    elif case == "bad-row":
        args[2] = str(write_jsonl(tmp_path / "bad.jsonl", [dict(GOOD, correct="yes")]))
    elif case == "incomplete":
        args[2] = str(write_jsonl(tmp_path / "gap.jsonl", known_rows()[:-1]))
    elif case == "bar":
        args += ["--bar", "1.5"]
    elif case == "seeds":
        args[-1] = "0"
    elif case == "fraction":
        args += ["--calibration-fraction", "1.0"]
    elif case == "unpriced-tokens":
        row_ = {k: v for k, v in GOOD.items() if k != "cost_usd"}
        row_.update(model="fiction/not-in-registry", input_tokens=1, output_tokens=1)
        args[2] = str(write_jsonl(tmp_path / "tokens.jsonl", [row_]))
    elif case == "flavor":
        args += ["--flavor", "cheap"]
    elif case == "repeated-flavor":
        args += ["--flavor", "cost_blind", "--flavor", "cost_blind"]
    assert main(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert captured.err.strip().splitlines()[-1].startswith("error: ")


# v1.5 text layout (12.4)

def _layout(headers, rows):
    cells = [headers] + rows
    widths = [max(len(r[i]) for r in cells) for i in range(len(headers))]
    lines = ["  ".join(c.ljust(w) for c, w in zip(r, widths)).rstrip() for r in cells]
    lines.insert(1, "  ".join("-" * w for w in widths))
    return lines


def test_cli_text_layout_follows_the_summary(tmp_path, capsys):
    ev = load_ev()
    path = write_jsonl(tmp_path / "outcomes.jsonl", known_rows())
    code = main(["evaluate", "--outcomes", str(path), "--bar", "0.8", "0.9", "--seeds", "2"])
    out = capsys.readouterr().out
    assert code == 0
    result = ev.evaluate(ev.load_outcomes(path), bars=[0.8, 0.9], seeds=range(2))

    def fmt(v):
        return "-" if v is None else f"{v:.3f}"
    expected = []
    for bar in (0.8, 0.9):
        for flavor in ("cost_effective", "cost_blind"):
            if expected:
                expected.append("")
            expected.append(f"bar {bar}, {flavor}")
            rows = [[r["strategy"], fmt(r["success"]), f"{r['cost_usd']:.4f}",
                     fmt(r["below_bar_rate"]), fmt(r["cleared_rate"]),
                     fmt(r["bar_violation_rate"])]
                    for r in result["summary"] if (r["bar"], r["flavor"]) == (bar, flavor)]
            assert [r[0] for r in rows] == STRATEGIES
            expected += _layout(["strategy", "success", "cost_usd", "below_bar_rate",
                                 "cleared_rate", "bar_violation_rate"], rows)
    assert out == "\n".join(expected) + "\n"


# v1.63 --flavor (12.4)

@pytest.mark.parametrize("argv, flavors", [
    (["--flavor", "cost_blind"], ["cost_blind"]),
    (["--flavor", "cost_effective"], ["cost_effective"]),
    (["--flavor", "cost_blind", "cost_effective"], ["cost_blind", "cost_effective"]),
    (["--flavor", "cost_blind", "--flavor", "cost_effective"], ["cost_blind", "cost_effective"]),
    ([], ["cost_effective", "cost_blind"]),
])
def test_cli_flavor_option_runs_the_flavors_given_in_order(tmp_path, capsys, argv, flavors):
    ev = load_ev()
    path = write_jsonl(tmp_path / "outcomes.jsonl", known_rows())
    code = main(["evaluate", "--outcomes", str(path), "--bar", "0.8", "0.9", "--seeds", "2",
                 "--json", *argv])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    out = json.loads(captured.out)
    expected = ev.evaluate(ev.load_outcomes(path), bars=[0.8, 0.9], seeds=range(2),
                           flavors=flavors)
    expected.pop("cells")
    assert out == json.loads(json.dumps(expected))
    assert out["config"]["flavors"] == flavors
    assert [r["flavor"] for r in out["summary"]] == [
        f for _ in (0.8, 0.9) for f in flavors for _ in STRATEGIES]


def test_cli_text_with_one_flavor_has_one_table_per_bar(tmp_path, capsys):
    ev = load_ev()
    path = write_jsonl(tmp_path / "outcomes.jsonl", known_rows())
    code = main(["evaluate", "--outcomes", str(path), "--bar", "0.8", "0.9", "--seeds", "2",
                 "--flavor", "cost_blind"])
    captured = capsys.readouterr()
    assert code == 0, captured.err
    result = ev.evaluate(ev.load_outcomes(path), bars=[0.8, 0.9], seeds=range(2),
                         flavors=["cost_blind"])

    def fmt(v):
        return "-" if v is None else f"{v:.3f}"
    expected = []
    for bar in (0.8, 0.9):
        if expected:
            expected.append("")
        expected.append(f"bar {bar}, cost_blind")
        rows = [[r["strategy"], fmt(r["success"]), f"{r['cost_usd']:.4f}",
                 fmt(r["below_bar_rate"]), fmt(r["cleared_rate"]), fmt(r["bar_violation_rate"])]
                for r in result["summary"] if r["bar"] == bar]
        assert [r[0] for r in rows] == STRATEGIES
        expected += _layout(["strategy", "success", "cost_usd", "below_bar_rate",
                             "cleared_rate", "bar_violation_rate"], rows)
    assert captured.out == "\n".join(expected) + "\n"
    assert "cost_effective" not in captured.out


def test_cli_bad_flavor_error_is_one_line_naming_the_flavors(tmp_path, capsys):
    load_ev()
    path = write_jsonl(tmp_path / "outcomes.jsonl", known_rows())
    for bad in (["cheap"], ["cost_blind", "cost_blind"]):
        assert main(["evaluate", "--outcomes", str(path), "--seeds", "1", "--flavor", *bad]) == 2
        captured = capsys.readouterr()
        assert captured.out == ""
        assert captured.err == "error: flavors must be distinct names from ('cost_effective', 'cost_blind')\n"


def test_readme_evaluate_paragraph_names_the_flavor_option():
    from pathlib import Path
    text = (Path(__file__).resolve().parents[1] / "README.md").read_text(encoding="utf-8")
    section = text.split("\n### Check the choice on items the router never saw\n", 1)[1]
    paragraph = section.lstrip("\n").split("\n\n", 1)[0]
    assert paragraph.startswith("`model-routing evaluate` takes an outcome matrix")
    assert ("`--flavor` runs only the flavors given, so `--flavor cost_blind` serves a matrix "
            "that records no cost (DESIGN 12.4)") in paragraph


# v1.5 demo outcome matrix (11)

def test_demo_writes_its_calibration_set_as_an_outcome_matrix(tmp_path):
    ev = load_ev()
    from model_routing import demo
    out = tmp_path / "demo"
    summary = demo.run_demo(out)
    outcomes = ev.load_outcomes(out / "outcomes.jsonl")
    judges = [model for model, _ in demo.JUDGES]
    items = [f"item-{i:03d}" for i in range(demo.CALIBRATION_ITEMS)]
    assert len(outcomes) == len(judges) * len(items) == 1200
    assert [(o.model, o.item) for o in outcomes] == [(m.id, i) for m in judges for i in items]
    assert {o.task for o in outcomes} == {demo.DEMO_TASK}
    stats = Stats.load(out / "stats.json")
    for model in judges:
        mine = [o for o in outcomes if o.model == model.id]
        assert (sum(o.correct for o in mine), len(mine)) == stats.get(demo.DEMO_TASK, model.id)
        assert all(o.cost_usd == model.cost(1000, 200) for o in mine)
    assert summary == demo.run_demo(tmp_path / "again")
    result = ev.evaluate(outcomes, bars=[0.85], seeds=range(3))
    assert result["tasks"] == {demo.DEMO_TASK: {"items": 300,
                                                "models": sorted(m.id for m in judges)}}


def test_demo_refuses_an_outcome_file_it_did_not_write(tmp_path):
    load_ev()
    from model_routing import demo
    out = tmp_path / "mine"
    out.mkdir()
    (out / "outcomes.jsonl").write_text("keep\n", encoding="utf-8")
    with pytest.raises(FileExistsError, match="outcomes.jsonl"):
        demo.run_demo(out)
    assert sorted(p.name for p in out.iterdir()) == ["outcomes.jsonl"]
    assert (out / "outcomes.jsonl").read_text(encoding="utf-8") == "keep\n"


# --- v1.135: each split's sums once per (task, seed), shared across bars and flavors --------

ONCE_BARS = [0.25, 0.5, 0.75]
ONCE_SEEDS = range(3)
GRADED = [f"graded-{i:03d}" for i in range(200)]


def every(k, n):
    return lambda item: int(item[-3:]) % n < k


def once_outcomes():
    """known_rows plus a task on which cheap is right on 1 item in 2, mid on 3 in 4 and best on
    19 in 20, so `cost_effective` routes a different model at each of ONCE_BARS."""
    rows = known_rows() + rows_for("graded", GRADED, {"fiction/cheap": every(1, 2),
                                                       "fiction/mid": every(3, 4),
                                                       "fiction/best": every(19, 20)})
    return load_ev().outcomes_from_rows(rows)


def run_once(outcomes, bars=ONCE_BARS, flavors=("cost_effective", "cost_blind")):
    return load_ev().evaluate(outcomes, bars=bars, seeds=ONCE_SEEDS, flavors=flavors)


def test_v1135_each_split_is_summed_once_per_task_and_seed(monkeypatch):
    ev, outcomes = load_ev(), once_outcomes()
    calls = {"sum": 0, "fsum": 0}

    def counting(name, real):
        def counted(values, *start):
            calls[name] += 1
            return real(values, *start)
        return counted
    monkeypatch.setattr(ev, "sum", counting("sum", sum), raising=False)
    monkeypatch.setattr(ev, "fsum", counting("fsum", ev.fsum))
    monkeypatch.setattr(ev, "_summary", lambda *args: [])
    monkeypatch.setattr(ev, "_per_task", lambda *args: [])
    result = run_once(outcomes)
    m, splits = len(MODELS), 3 * len(ONCE_SEEDS)  # 3 tasks
    # 3 bars x 2 flavors = 6 cells per (task, seed)
    assert len(result["cells"]) == 6 * splits
    # per (task, seed): a correct count per model over C and over H, a cost per model over C
    # and over H and the oracle's cost; none per cell
    assert calls == {"sum": splits * 2 * m, "fsum": splits * (2 * m + 1)}
    # and again on a second run, so nothing is kept from one call to the next
    calls.update(sum=0, fsum=0)
    assert run_once(outcomes)["cells"] == result["cells"]
    assert calls == {"sum": splits * 2 * m, "fsum": splits * (2 * m + 1)}


def test_v1135_a_run_on_several_bars_and_flavors_is_the_runs_on_each_alone():
    outcomes = once_outcomes()
    result = run_once(outcomes)
    alone = []
    for bar in ONCE_BARS:
        for flavor in ("cost_effective", "cost_blind"):
            alone += run_once(outcomes, bars=[bar], flavors=[flavor])["cells"]
    assert result["cells"] == alone
    # the routed model moves with the bar, so a cell reads the pair of the model it names
    graded = [c for c in result["cells"]
              if (c["task"], c["flavor"]) == ("graded", "cost_effective")]
    assert {c["bar"]: c["models"]["routed"] for c in graded} == {
        0.25: "fiction/cheap", 0.5: "fiction/mid", 0.75: "fiction/best"}
    assert all(c["success"]["routed"] == c["success"]["model:" + c["models"]["routed"]]
               and c["cost_usd"]["routed"] == c["cost_usd"]["model:" + c["models"]["routed"]]
               for c in result["cells"])
    # no two cells share a dict, so a change to one cell never shows in another
    cells = result["cells"]
    assert len({id(c[k]) for c in cells for k in ("models", "success", "cost_usd")}) == 3 * len(cells)


# v1.261 (row E1c, review iter-006 should-fix items 2 and 3): 12.3 type-checks `min_samples` and
# `confidence`, and rejects a repeated (task, item, model) among the Outcomes `evaluate` is given
# directly, which a dict keyed by model used to let the last one win. Each case fails before
# v1.262: a bool, a float or a string got through or raised `TypeError`, and the messages were
# `min_samples must be >= 1` and `confidence must be in (0, 1)`.
MIN_SAMPLES_MESSAGE = "min_samples must be an integer >= 1"
CONFIDENCE_MESSAGE = "confidence must be a finite number in (0, 1)"
BAD_RUN_OPTIONS = [
    ({"min_samples": True}, MIN_SAMPLES_MESSAGE), ({"min_samples": False}, MIN_SAMPLES_MESSAGE),
    ({"min_samples": 0}, MIN_SAMPLES_MESSAGE), ({"min_samples": -3}, MIN_SAMPLES_MESSAGE),
    ({"min_samples": 2.5}, MIN_SAMPLES_MESSAGE), ({"min_samples": 30.0}, MIN_SAMPLES_MESSAGE),
    ({"min_samples": "30"}, MIN_SAMPLES_MESSAGE), ({"min_samples": None}, MIN_SAMPLES_MESSAGE),
    ({"confidence": True}, CONFIDENCE_MESSAGE), ({"confidence": False}, CONFIDENCE_MESSAGE),
    ({"confidence": 0.0}, CONFIDENCE_MESSAGE), ({"confidence": 1.0}, CONFIDENCE_MESSAGE),
    ({"confidence": 1}, CONFIDENCE_MESSAGE), ({"confidence": float("nan")}, CONFIDENCE_MESSAGE),
    ({"confidence": float("inf")}, CONFIDENCE_MESSAGE), ({"confidence": "0.95"}, CONFIDENCE_MESSAGE),
    ({"confidence": None}, CONFIDENCE_MESSAGE),
]


def option_id(case):
    kwargs = case if isinstance(case, dict) else {}
    return "-".join(f"{k}={v!r}" for k, v in kwargs.items()) or "message"


@pytest.mark.parametrize("kwargs,message", BAD_RUN_OPTIONS, ids=option_id)
def test_min_samples_and_confidence_are_type_checked(kwargs, message):
    ev = load_ev()
    with pytest.raises(ValueError, match="^" + re.escape(message)):
        ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.8], seeds=[0], **kwargs)


def test_an_int_min_samples_and_a_float_confidence_still_run():
    ev = load_ev()
    result = ev.evaluate(ev.outcomes_from_rows(known_rows()), bars=[0.8], seeds=[0],
                         min_samples=1, confidence=0.5)
    assert (result["config"]["min_samples"], result["config"]["confidence"]) == (1, 0.5)


@pytest.mark.parametrize("flip", [False, True], ids=["equal", "different"])
def test_a_repeated_outcome_given_directly_is_a_value_error(flip):
    ev = load_ev()
    rows = known_rows()
    outcomes = list(ev.outcomes_from_rows(rows))
    o = outcomes[17]
    outcomes.append(ev.Outcome(o.task, o.item, o.model, o.correct != flip, o.cost_usd))
    with pytest.raises(ValueError, match="^repeated outcome") as info:
        ev.evaluate(outcomes, bars=[0.8], seeds=[0])
    # the same message `outcomes_from_rows` gives for the same repeat (12.1)
    with pytest.raises(ValueError) as from_rows:
        ev.outcomes_from_rows(rows + [dict(rows[17], correct=rows[17]["correct"] != flip)])
    assert str(info.value) == str(from_rows.value)
    assert all(part in str(info.value) for part in (repr(o.task), repr(o.item), repr(o.model)))
