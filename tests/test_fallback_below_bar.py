"""DESIGN 4.2, 5.1, 5.3 and 10 v1.201 (row S2): the opt-in below-bar fallback on `Task`.

With `fallback_below_bar` on and some model clearing the bar, the fallbacks go on after the
clearing models with the eligible measured models under the bar, in the 5.3 `best_available`
order, up to `max_fallbacks` in all, and the decision names those in `below_bar_fallbacks`. Off by
default, where every decision is v1.200's. The orders below are written out by hand; the seeded
check compares the router with the below-bar route of research/below_bar_fallback.py, which the
note measured."""

import dataclasses
import importlib.util
import json
import random
from pathlib import Path

import pytest

from model_routing import (DATA_DIR, Model, NoModelClearsBar, Registry, Router, Stats, Task,
                           load_tasks)
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
V1_200_KEYS = ["task", "flavor", "primary", "fallbacks", "below_bar", "basis", "candidates"]

# (id, family, price_in, context_window, successes, trials); bar 0.7, min_samples 20
MODELS = [
    ("p/cheap", "p1", 1.0, 8000, 95, 100),    # passes, cheapest passing
    ("p/dear", "p2", 5.0, 8000, 99, 100),     # passes, best bound
    ("b/close", "b1", 2.0, 8000, 70, 100),    # below_bar, bound about 0.604
    ("b/far", "b2", 0.5, 8000, 50, 100),      # below_bar, bound about 0.404
    ("b/tie1", "b3", 3.0, 8000, 60, 100),     # below_bar, same bound as b/tie2, dearer
    ("b/tie2", "b4", 1.0, 8000, 60, 100),     # below_bar
    ("s/few", "s1", 4.0, 8000, 10, 10),       # insufficient_samples with trials, bound about 0.722
    ("u/none", "u1", 0.1, 8000, 0, 0),        # insufficient_samples, unmeasured: never added
    ("x/excl", "x1", 0.1, 8000, 98, 100),     # excluded by the caller: never added
    ("c/small", "c1", 0.1, 100, 98, 100),     # context_too_small: never added
]


def build(max_fallbacks=10, on=True, bar=0.7, on_no_model="refuse", **extra):
    registry = Registry([Model(m, fam, price, 2.0, window) for m, fam, price, window, _, _ in MODELS])
    stats = Stats()
    for m, _, _, _, succ, trials in MODELS:
        if trials:
            stats.add("t", m, succ, trials)
    fields = dict(name="t", bar=bar, min_samples=20, independent_of_generator=False,
                  max_fallbacks=max_fallbacks, on_no_model=on_no_model, **extra)
    if on:
        fields["fallback_below_bar"] = True
    task = Task(**fields)
    return Router(registry, {"t": task}, stats)


def route(decision):
    return (decision.primary, *decision.fallbacks)


# ---- 4.2 the field ----------------------------------------------------------------------------

def test_the_field_is_last_and_off_by_default():
    names = [f.name for f in dataclasses.fields(Task)]
    assert names[-1] == "fallback_below_bar"
    assert Task("t", 0.5).fallback_below_bar is False
    assert Task("t", 0.5, fallback_below_bar=True).fallback_below_bar is True


@pytest.mark.parametrize("value", [1, 0, "true", None, 1.0])
def test_a_value_that_is_not_a_bool_raises_valueerror(value):
    with pytest.raises(ValueError, match="fallback_below_bar"):
        Task("t", 0.5, fallback_below_bar=value)


def test_load_tasks_reads_true_and_false_and_refuses_a_string(tmp_path):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "fallback_below_bar": True},
                                          {"name": "b", "bar": 0.5, "fallback_below_bar": False},
                                          {"name": "c", "bar": 0.5}]}), encoding="utf-8")
    tasks = load_tasks(path)
    assert [tasks[k].fallback_below_bar for k in "abc"] == [True, False, False]
    path.write_text(json.dumps({"tasks": [{"name": "a", "bar": 0.5, "fallback_below_bar": "yes"}]}),
                    encoding="utf-8")
    with pytest.raises(ValueError):
        load_tasks(path)


def test_no_packaged_task_sets_the_option():
    rows = json.loads((DATA_DIR / "example_tasks.json").read_text(encoding="utf-8"))["tasks"]
    assert rows and all("fallback_below_bar" not in row for row in rows)


# ---- 5.3 the order ----------------------------------------------------------------------------

def test_cost_effective_fills_the_places_with_the_best_bounds_under_the_bar():
    decision = build(max_fallbacks=5).select("t", exclude_models=("x/excl",))
    assert decision.primary == "p/cheap"
    assert decision.fallbacks == ("p/dear", "s/few", "b/close", "b/tie2", "b/tie1")
    assert decision.below_bar_fallbacks == ("s/few", "b/close", "b/tie2", "b/tie1")
    assert decision.below_bar is False and decision.basis == "measured"


def test_every_eligible_measured_model_and_nothing_else_with_room_for_all():
    decision = build(max_fallbacks=20).select("t", exclude_models=("x/excl",))
    assert route(decision) == ("p/cheap", "p/dear", "s/few", "b/close", "b/tie2", "b/tie1", "b/far")
    reasons = {c.model_id: c.reason for c in decision.candidates}
    assert reasons["u/none"] == "insufficient_samples" and "u/none" not in route(decision)
    assert reasons["x/excl"] == "excluded_model" and reasons["c/small"] == "context_too_small"


def test_cost_blind_ties_on_the_bound_go_by_model_id():
    decision = build(max_fallbacks=20).select("t", flavor="cost_blind", exclude_models=("x/excl",))
    assert route(decision) == ("p/dear", "p/cheap", "s/few", "b/close", "b/tie1", "b/tie2", "b/far")
    assert decision.below_bar_fallbacks == ("s/few", "b/close", "b/tie1", "b/tie2", "b/far")


@pytest.mark.parametrize("max_fallbacks, fallbacks, below", [
    (0, (), ()),
    (1, ("p/dear",), ()),
    (2, ("p/dear", "s/few"), ("s/few",)),
])
def test_below_bar_models_take_only_the_places_the_passing_list_leaves(max_fallbacks, fallbacks, below):
    decision = build(max_fallbacks=max_fallbacks).select("t", exclude_models=("x/excl",))
    assert decision.primary == "p/cheap"
    assert decision.fallbacks == fallbacks and decision.below_bar_fallbacks == below


def test_one_passing_model_then_only_models_under_the_bar():
    decision = build(max_fallbacks=2).select("t", exclude_models=("x/excl", "p/dear"))
    assert route(decision) == ("p/cheap", "s/few", "b/close")
    assert decision.below_bar_fallbacks == ("s/few", "b/close")


def test_option_off_keeps_the_passing_fallbacks_alone():
    decision = build(max_fallbacks=5, on=False).select("t", exclude_models=("x/excl",))
    assert route(decision) == ("p/cheap", "p/dear")
    assert decision.below_bar_fallbacks == ()


def test_nothing_passes_the_option_changes_nothing():
    for flavor in ("cost_effective", "cost_blind"):
        on = build(bar=0.99, on_no_model="best_available").select("t", flavor)
        off = build(bar=0.99, on_no_model="best_available", on=False).select("t", flavor)
        assert on == off and on.below_bar is True and on.below_bar_fallbacks == ()
        for router in (build(bar=0.99), build(bar=0.99, on=False)):
            with pytest.raises(NoModelClearsBar):
                router.select("t", flavor)


def _load_research():
    path = ROOT / "research" / "below_bar_fallback.py"
    spec = importlib.util.spec_from_file_location("research_below_bar_for_s2", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_route_is_the_research_below_bar_route_on_seeded_cells():
    research = _load_research()
    rng = random.Random(151)
    checked = 0
    for cell in range(300):
        n = rng.randint(1, 8)
        models = [f"m/{k}" for k in range(n)]
        registry = Registry([Model(m, f"f{k}", rng.choice([0.5, 1.0, 2.0, 3.0]), 1.0, 8000)
                             for k, m in enumerate(models)])
        stats = Stats()
        for m in models:
            trials = rng.choice([0, 5, 30, 60])
            if trials:
                stats.add("t", m, rng.randint(0, trials), trials)
        bar = rng.choice([0.3, 0.5, 0.7])
        k = rng.randint(0, n)
        common = dict(name="t", bar=bar, min_samples=10, independent_of_generator=False,
                      on_no_model="best_available")
        whole = Router(registry, {"t": Task(**common, max_fallbacks=n)}, stats)
        opted = Router(registry, {"t": Task(**common, max_fallbacks=k, fallback_below_bar=True)}, stats)
        for flavor in ("cost_effective", "cost_blind"):
            try:
                full = whole.select("t", flavor)
            except NoModelClearsBar:
                with pytest.raises(NoModelClearsBar):
                    opted.select("t", flavor)
                continue
            decision = opted.select("t", flavor)
            assert route(decision) == research.routes(full, k)[1], (cell, flavor)
            passing = {c.model_id for c in decision.candidates if c.passes}
            expected = () if decision.below_bar else tuple(m for m in decision.fallbacks if m not in passing)
            assert decision.below_bar_fallbacks == expected
            checked += 1
    assert checked > 300


# ---- the default changes no decision on the packaged tasks ------------------------------------

def _packaged_cells():
    registry = Registry.load(DATA_DIR / "models.json")
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    rng = random.Random(1201)
    stats = Stats()
    for name in tasks:
        for model in registry.models:
            trials = rng.choice([0, 20, 60, 200])
            if trials:
                stats.add(name, model.id, rng.randint(trials // 2, trials), trials)
    router = Router(registry, tasks, stats)
    for name, task in tasks.items():
        for flavor in ("cost_effective", "cost_blind"):
            try:
                yield task, router.select(name, flavor)
            except NoModelClearsBar:
                continue


def test_default_route_on_the_packaged_tasks_is_the_v1_200_rule():
    seen = 0
    for task, decision in _packaged_cells():
        passing = sorted((c for c in decision.candidates if c.passes),
                         key=lambda c: (c.routing_cost, -c.quality_lb, c.model_id))
        if passing:
            assert route(decision) == tuple(c.model_id for c in passing[:1 + task.max_fallbacks])
            seen += 1
        assert list(decision.to_dict()) == V1_200_KEYS
    assert seen >= 7


def test_default_decisions_on_the_packaged_tasks_have_no_below_bar_fallback():
    cells = list(_packaged_cells())
    assert cells
    for task, decision in cells:
        assert task.fallback_below_bar is False
        assert decision.below_bar_fallbacks == ()


# ---- 5.1 the dict and 10 the CLI --------------------------------------------------------------

def test_to_dict_has_the_key_after_fallbacks_only_when_not_empty():
    on = build(max_fallbacks=2).select("t", exclude_models=("x/excl",)).to_dict()
    assert list(on) == V1_200_KEYS[:4] + ["below_bar_fallbacks"] + V1_200_KEYS[4:]
    assert on["below_bar_fallbacks"] == ["s/few"]
    json.dumps(on)
    off = build(max_fallbacks=2, on=False).select("t", exclude_models=("x/excl",)).to_dict()
    assert list(off) == V1_200_KEYS


def _cli_files(tmp_path, on):
    registry = {"version": "1", "as_of": "2026-01-01", "currency": "USD", "models": [
        {"id": m, "family": fam, "price_in": price, "price_out": 2.0, "context_window": window,
         "source": "https://example.org/prices"} for m, fam, price, window, _, _ in MODELS]}
    task = {"name": "t", "bar": 0.7, "min_samples": 20, "independent_of_generator": False,
            "max_fallbacks": 2}
    if on:
        task["fallback_below_bar"] = True
    stats = {"stats": [{"task": "t", "model": m, "successes": s, "trials": n}
                       for m, _, _, _, s, n in MODELS if n]}
    paths = {}
    for key, data in (("registry", registry), ("tasks", {"tasks": [task]}), ("stats", stats)):
        paths[key] = tmp_path / f"{key}.json"
        paths[key].write_text(json.dumps(data), encoding="utf-8")
    paths["priors"] = tmp_path / "no-priors.json"
    args = ["select", "t", "--exclude", "x/excl"]
    for key, path in paths.items():
        args += [f"--{key}", str(path)]
    return args


def test_select_marks_each_below_bar_fallback(tmp_path, capsys):
    assert main(_cli_files(tmp_path, True)) == 0
    lines = capsys.readouterr().out.split("\n")
    assert lines[3] == "fallbacks: p/dear, s/few (below bar)"
    assert main(_cli_files(tmp_path, True) + ["--json"]) == 0
    assert json.loads(capsys.readouterr().out)["below_bar_fallbacks"] == ["s/few"]


def test_select_without_the_option_prints_the_plain_line(tmp_path, capsys):
    assert main(_cli_files(tmp_path, False)) == 0
    lines = capsys.readouterr().out.split("\n")
    assert lines[3] == "fallbacks: p/dear"
    assert main(_cli_files(tmp_path, False) + ["--json"]) == 0
    assert list(json.loads(capsys.readouterr().out)) == V1_200_KEYS


# ---- README -----------------------------------------------------------------------------------

def _rules_section():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    start = text.index("### Rules that protect quality\n")
    end = text.index("\n## ", start)
    return text[start:end]


def test_readme_rules_name_the_option_and_link_the_note():
    hits = [line for line in _rules_section().split("\n") if "`fallback_below_bar`" in line]
    assert len(hits) == 1
    line = hits[0]
    for words in ("`below_bar_fallbacks`", "`(below bar)`", "`validate`", "0.0042", "1.029", "1.031",
                  "bar 0.8", "upper bound", "[research/below-bar-fallback.md](research/below-bar-fallback.md)"):
        assert words in line, words
    note = (ROOT / "research" / "below-bar-fallback.md").read_text(encoding="utf-8")
    assert ("adds 0.0042 of success, `cost_effective` from 0.7470 to 0.7512 at 1.031 times the cost "
            "and `cost_blind` from 0.7500 to 0.7542 at 1.029 times") in note
