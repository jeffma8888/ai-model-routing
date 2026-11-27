"""DESIGN 5.1 and 5.2 v1.670 (row DEL1a, the first part of row DEL1): `Router.select_pair`.

A delegating harness runs two models, the root that plans and writes the answer and the leaf its
sub-agents run on. `select_pair(task, roots, leaves)` makes one candidate per pair `<root>+<leaf>`,
roots-major: rules 1 to 5d on the root, then on the leaf, rules 5e to 5h and 6 to 8 on the pair's own
key, so a pair is admitted only on runs of the two together. Its cost is the root's list cost plus the
leaf's, each at its own prices and its 5.2 sizes on the task, and the decision is chosen by 5.3 with
no prior. The 4 x 3 fixture is the row's: a strong root with the cheapest leaf is the cheapest
admitted pair.
"""

import json
from pathlib import Path

import pytest

import model_routing
from model_routing import Model, NoModelClearsBar, Policy, Priors, Registry, Router, Stats, Task
from model_routing.stats import wilson_lower_bound

ROOT = Path(__file__).resolve().parents[1]
N = 40
ROOTS = ["r/strong", "r/good", "r/fair", "r/weak"]
LEAVES = ["l/cheap", "l/mid", "l/dear"]
PRICES = {"r/strong": (10.0, 30.0), "r/good": (3.0, 9.0), "r/fair": (1.0, 3.0), "r/weak": (0.2, 0.6),
          "l/cheap": (0.1, 0.3), "l/mid": (1.0, 3.0), "l/dear": (10.0, 30.0)}
# successes of N trials on each pair's own key; at bar 0.8 only 39 and 40 of 40 pass
PAIRS = {("r/strong", "l/cheap"): 39, ("r/strong", "l/mid"): 40, ("r/strong", "l/dear"): 40,
         ("r/good", "l/cheap"): 30, ("r/good", "l/mid"): 34, ("r/good", "l/dear"): 39,
         ("r/fair", "l/cheap"): 28, ("r/fair", "l/mid"): 30, ("r/fair", "l/dear"): 33,
         ("r/weak", "l/cheap"): 20, ("r/weak", "l/mid"): 22, ("r/weak", "l/dear"): 25}


def cost(model_id, size_in=1000, size_out=200):
    price_in, price_out = PRICES[model_id]
    return (size_in * price_in + size_out * price_out) / 1_000_000


def registry(windows=None, extra=()):
    windows = windows or {}
    models = [Model(m, m.split("/")[1], *PRICES[m], windows.get(m, 100_000)) for m in ROOTS + LEAVES]
    return Registry(models + list(extra))


def router(pairs=PAIRS, reg=None, solo=True, priors=None, pair_extra=None, solo_extra=None, **fields):
    """Each pair's own counts; with ``solo`` each model alone at 40 of 40 on its own key too."""
    stats = Stats()
    for (root, leaf), wins in pairs.items():
        stats.add("t", f"{root}+{leaf}", wins, N, **(pair_extra or {}).get((root, leaf), {}))
    if solo:
        for model_id in ROOTS + LEAVES:
            stats.add("t", model_id, N, N, **(solo_extra or {}).get(model_id, {}))
    task = Task("t", **{"bar": 0.8, "min_samples": 30, **fields})
    return Router(reg or registry(), {"t": task}, stats, priors)


def by_id(decision):
    return {c.model_id: c for c in decision.candidates}


# --- 5.1 v1.670: the decision's shape ---------------------------------------------------------

def test_one_candidate_per_pair_roots_major_with_the_root_family_and_no_new_export():
    decision = router().select_pair("t", ROOTS, LEAVES)
    assert [c.model_id for c in decision.candidates] == [f"{r}+{l}" for r in ROOTS for l in LEAVES]
    for c in decision.candidates:
        root, leaf = c.model_id.split("+")
        assert c.family == root.split("/")[1]
        assert c.pricing_basis is None and c.cost_breakdown is None and c.cache_price_unknown == ()
        assert (c.successes, c.trials) == (PAIRS[(root, leaf)], N)
        assert c.quality_lb == wilson_lower_bound(PAIRS[(root, leaf)], N, 0.95)
    assert "select_pair" not in model_routing.__all__
    data = json.loads(json.dumps(decision.to_dict()))
    assert data["primary"] == "r/strong+l/cheap"
    assert all("pricing_basis" not in c for c in data["candidates"])


# --- 5.2 v1.670 and 5.3: the row's 4 x 3 fixture -----------------------------------------------

def test_cost_effective_takes_the_strong_root_with_the_cheapest_leaf():
    decision = router().select_pair("t", ROOTS, LEAVES)
    assert decision.primary == "r/strong+l/cheap"
    assert decision.fallbacks == ("r/strong+l/mid", "r/good+l/dear")
    assert (decision.below_bar, decision.basis, decision.flavor, decision.task) == \
        (False, "measured", "cost_effective", "t")
    passing = sorted((c for c in decision.candidates if c.passes), key=lambda c: c.list_cost)
    assert [c.model_id for c in passing] == ["r/strong+l/cheap", "r/strong+l/mid", "r/good+l/dear",
                                             "r/strong+l/dear"]
    reasons = {c.model_id: c.reason for c in decision.candidates}
    assert reasons["r/weak+l/cheap"] == "below_bar" and reasons["r/good+l/mid"] == "below_bar"


def test_cost_blind_takes_the_best_bound_ties_by_id():
    decision = router().select_pair("t", ROOTS, LEAVES, "cost_blind")
    assert decision.primary == "r/strong+l/dear"
    assert decision.fallbacks == ("r/strong+l/mid", "r/good+l/dear")
    assert all(c.routing_cost == 0.0 for c in decision.candidates)


def test_a_pair_costs_the_root_plus_the_leaf_each_at_its_own_sizes():
    decision = router().select_pair("t", ROOTS, LEAVES)
    for c in decision.candidates:
        root, leaf = c.model_id.split("+")
        assert c.list_cost == pytest.approx(cost(root) + cost(leaf), rel=1e-12)
        assert c.routing_cost == c.list_cost
    measured = {"r/strong": {"input_tokens": 500 * N, "output_tokens": 100 * N, "token_trials": N}}
    priced = by_id(router(solo_extra=measured).select_pair("t", ROOTS, LEAVES))
    assert priced["r/strong+l/cheap"].list_cost == pytest.approx(0.008 + 0.00016, rel=1e-12)
    assert priced["r/good+l/cheap"].list_cost == pytest.approx(0.0048 + 0.00016, rel=1e-12)


def test_a_pair_is_never_admitted_on_either_model_s_own_runs():
    r = router(pairs={})
    assert r.select("t").primary == "l/cheap"  # every model passes alone
    with pytest.raises(NoModelClearsBar) as caught:
        r.select_pair("t", ROOTS, LEAVES)
    assert [c.reason for c in caught.value.candidates] == ["insufficient_samples"] * 12
    assert [c.model_id for c in caught.value.candidates] == [f"{a}+{b}" for a in ROOTS for b in LEAVES]


def test_with_no_pair_passing_best_available_takes_the_best_measured_pair_below_the_bar():
    weak = {pair: wins for pair, wins in PAIRS.items() if wins < 39}
    decision = router(pairs=weak, on_no_model="best_available").select_pair("t", ROOTS, LEAVES)
    assert (decision.primary, decision.below_bar, decision.basis) == ("r/good+l/mid", True, "measured")
    with pytest.raises(NoModelClearsBar):
        router(pairs=weak).select_pair("t", ROOTS, LEAVES)


def test_no_pair_is_picked_on_a_prior():
    priors = Priors({"c": {"scores": {m: 0.99 for m in ROOTS + LEAVES}}})
    r = router(pairs={}, priors=priors, solo=False, on_no_model="best_available", prior_category="c")
    assert r.select("t").basis == "prior"
    with pytest.raises(NoModelClearsBar, match="no eligible measured or prior-scored model"):
        r.select_pair("t", ROOTS, LEAVES)


# --- 5.2 v1.670: each role keeps its own checks ------------------------------------------------

def test_an_excluded_leaf_rules_out_its_pairs():
    decision = router().select_pair("t", ROOTS, LEAVES, exclude_models=["l/cheap"])
    reasons = by_id(decision)
    assert all(reasons[f"{r}+l/cheap"].reason == "excluded_model" for r in ROOTS)
    assert not any(reasons[f"{r}+l/cheap"].eligible for r in ROOTS)
    assert decision.primary == "r/strong+l/mid"


def test_a_policy_names_the_root_and_the_leaf_never_the_pair():
    policy = Policy(allowed_routes=["r/good", "l/cheap", "l/mid", "l/dear"])
    decision = router().select_pair("t", ROOTS, LEAVES, policy=policy)
    assert all(by_id(decision)[f"r/strong+{l}"].reason == "policy_excluded" for l in LEAVES)
    assert decision.primary == "r/good+l/dear"
    pair_only = Policy(allowed_routes=["r/strong+l/cheap"])
    with pytest.raises(NoModelClearsBar) as caught:
        router().select_pair("t", ROOTS, LEAVES, policy=pair_only)
    assert [c.reason for c in caught.value.candidates] == ["policy_excluded"] * 12


def test_the_root_s_rules_come_before_the_leaf_s():
    reg = registry(windows={"r/weak": 500, "l/dear": 500})
    reasons = {c.model_id: c.reason for c in
               router(reg=reg).select_pair("t", ROOTS, LEAVES, exclude_models=["l/cheap"]).candidates}
    assert reasons["r/weak+l/cheap"] == "context_too_small"  # the root's rule 5 before the leaf's rule 1
    assert reasons["r/fair+l/cheap"] == "excluded_model"
    assert reasons["r/strong+l/dear"] == "context_too_small"  # the leaf's rule 5
    assert reasons["r/weak+l/mid"] == "context_too_small"


def test_a_generator_rules_out_its_pairs_on_either_side():
    reasons = {c.model_id: c.reason for c in
               router().select_pair("t", ROOTS, LEAVES, generator_model="l/mid").candidates}
    assert all(reasons[f"{r}+l/mid"] == "generator" for r in ROOTS)
    assert reasons["r/strong+l/cheap"] == "passes"
    root_side = {c.model_id: c.reason for c in
                 router().select_pair("t", ROOTS, LEAVES, generator_model="r/strong").candidates}
    assert all(root_side[f"r/strong+{l}"] == "generator" for l in LEAVES)


def test_rules_5e_to_5h_read_the_pair_s_own_key():
    slow_pair = {("r/strong", "l/cheap"): {"latencies_ms": [2000.0] * N}}
    fast_pair = {pair: {"latencies_ms": [100.0] * N} for pair in PAIRS if pair != ("r/strong", "l/cheap")}
    slow_root = {"r/strong": {"latencies_ms": [9000.0] * N}}
    r = router(pair_extra={**fast_pair, **slow_pair}, solo_extra=slow_root, max_p95_ms=1000.0)
    decision = r.select_pair("t", ROOTS, LEAVES)
    assert by_id(decision)["r/strong+l/cheap"].reason == "too_slow"
    assert by_id(decision)["r/strong+l/cheap"].p95_latency_ms == 2000.0
    assert decision.primary == "r/strong+l/mid"
    alike = {("r/strong", "l/dear"): {"rerun_items": N, "consistent_items": N}}
    shaky = {("r/strong", "l/mid"): {"rerun_items": N, "consistent_items": 30}}
    reasons = {c.model_id: c.reason for c in
               router(pair_extra={**alike, **shaky}, min_self_consistency=0.9).select_pair("t", ROOTS, LEAVES).candidates}
    assert reasons["r/strong+l/dear"] == "passes"
    assert reasons["r/strong+l/mid"] == "inconsistent"
    assert reasons["r/strong+l/cheap"] == "consistency_unknown"


# --- 5.2 v1.670: the checks before any candidate -----------------------------------------------

@pytest.mark.parametrize("roots, leaves", [
    ((), LEAVES), ([], LEAVES), ("r/strong", LEAVES), (["r/strong", "r/strong"], LEAVES),
    ([1], LEAVES), (ROOTS, []), (ROOTS, "l/cheap"), (ROOTS, ["l/cheap", "l/cheap"]), (ROOTS, None),
    ({"r/strong"}, LEAVES),
], ids=["empty tuple", "empty list", "a str", "a repeat", "an int", "no leaf", "a str leaf",
        "a repeated leaf", "None", "a set"])
def test_roots_and_leaves_must_be_non_empty_lists_or_tuples_of_distinct_ids(roots, leaves):
    with pytest.raises(ValueError):
        router().select_pair("t", roots, leaves)


def test_an_unknown_model_task_flavor_or_policy_is_refused():
    with pytest.raises(KeyError):
        router().select_pair("t", ["x/none"], LEAVES)
    with pytest.raises(KeyError):
        router().select_pair("t", ROOTS, ["x/none"])
    with pytest.raises(KeyError):
        router().select_pair("nope", (), LEAVES)  # the task is checked before roots
    with pytest.raises(ValueError, match="unknown flavor"):
        router().select_pair("t", ROOTS, LEAVES, "cheapest")
    with pytest.raises(ValueError, match="policy must be None or a Policy"):
        router().select_pair("t", ROOTS, LEAVES, policy={"allowed_routes": []})
    with pytest.raises(KeyError):
        router().select_pair("t", ROOTS, LEAVES, generator_model="x/none")


def test_a_registry_id_equal_to_a_pair_s_id_is_refused():
    reg = registry(extra=[Model("r/strong+l/cheap", "odd", 1.0, 1.0, 100_000)])
    with pytest.raises(ValueError, match="r/strong\\+l/cheap"):
        router(reg=reg).select_pair("t", ROOTS, LEAVES)


def test_a_model_may_be_both_a_root_and_a_leaf():
    pairs = {("r/strong", "r/strong"): 40, ("r/strong", "l/cheap"): 40}
    decision = router(pairs=pairs).select_pair("t", ["r/strong"], ["r/strong", "l/cheap"])
    assert [c.model_id for c in decision.candidates] == ["r/strong+r/strong", "r/strong+l/cheap"]
    assert decision.primary == "r/strong+l/cheap"
    assert by_id(decision)["r/strong+r/strong"].list_cost == pytest.approx(2 * cost("r/strong"), rel=1e-12)


# --- unchanged: select ignores pair keys ------------------------------------------------------

def test_select_reads_no_pair_key():
    with_pairs, without = router(), router(pairs={})
    assert with_pairs.select("t").to_dict() == without.select("t").to_dict()
    assert with_pairs.select("t", "cost_blind").to_dict() == without.select("t", "cost_blind").to_dict()


# --- research/production-lessons.md: the orchestrator line says what ships --------------------

def test_the_note_s_orchestrator_line_names_select_pair_and_what_is_planned():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    lesson = text.split("### The orchestrator gets the strong model; the readers can be cheap\n", 1)[1]
    line = next(l for l in lesson.split("\n") if l.startswith("- In this library:"))
    assert "from v1.670, `Router.select_pair(task, roots, leaves)`" in line
    assert "admitted only on runs of the two together" in line
    assert "The change: route the root and sub-agent models as a pair" not in line
    assert "its tokens inside the pair" in line
    # v1.671 (row DEL1ba): side tokens ship; v1.672 (row DEL1bb): read from a results row
    assert "and from v1.671 at its tokens inside the pair when the pair's stats hold them" in line
    assert "and from v1.672 `calibrate_from_results` reads them from a results row" in line
    assert "reading those tokens from a results row" not in line
    # v1.676 (row DEL1c): the command ships (tests/test_select_pair_cli.py); v1.677 (row DEL1d):
    # the table ships (tests/test_evaluate_pairs.py)
    assert "from v1.676 `model-routing select-pair` prints the pair's decision from the command line" in line
    assert "from v1.677 `evaluate(..., pairs=(roots, leaves))` gives each task's spread" in line
    assert "pricing each side at its tokens inside the pair" not in line
