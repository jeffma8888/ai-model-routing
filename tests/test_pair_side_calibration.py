"""DESIGN 4.3 v1.672 (row DEL1bb, the second part of row DEL1b): a pair's side tokens from a results row.

A `calibrate_from_results` row may carry `root_input_tokens`, `root_output_tokens`,
`leaf_input_tokens` and `leaf_output_tokens`, all four or none, each an int that is not a bool, at
least 0, and then adds one side trial with them under its key, under both keys for a sliced row, as
`.add(..., side_trials=1)` adds it (4.3 v1.671). A partial set, null, a bool, a float, a string or a
negative value, or the four on a cascade or procedure row, raise `ValueError` naming the row before
the returned `Stats` exists. A row without them builds v1.671's `Stats` and file bytes.
"""

import json
from pathlib import Path

import pytest

import model_routing
from model_routing import Router, Stats, Task, calibrate_from_results, item_outcomes
from test_pair_side_tokens import sides
from test_select_pair import LEAVES, N, PAIRS, ROOTS, by_id, registry, router

ROOT = Path(__file__).resolve().parents[1]
SIDES = ("root_input_tokens", "root_output_tokens", "leaf_input_tokens", "leaf_output_tokens")
PAIR = "r/strong+l/cheap"
SHA = "0" * 64


def side(root_in, root_out, leaf_in, leaf_out):
    return dict(zip(SIDES, (root_in, root_out, leaf_in, leaf_out)))


def row(item="q1", correct=True, model=PAIR, **extra):
    return {"task": "t", "model": model, "item": item, "correct": correct, **extra}


def saved(stats, path):
    stats.save(path)
    return path.read_bytes()


# --- a row with the four, and one without ----------------------------------------------------

def test_a_row_with_the_four_adds_one_side_trial_and_the_means_round_up():
    stats = calibrate_from_results([row("q1", True, **side(40, 10, 900, 150)),
                                    row("q2", False, **side(21, 5, 1000, 201))])
    assert stats.get("t", PAIR) == (1, 2)
    assert stats.side_tokens("t", PAIR) == (61, 15, 1900, 351, 2)
    # ceil(61 / 2) = 31, ceil(15 / 2) = 8, 1900 / 2 = 950, ceil(351 / 2) = 176
    assert stats.mean_side_tokens("t", PAIR) == ((31, 8), (950, 176))
    assert stats.tokens("t", PAIR) == (0, 0, 0)


def test_the_stats_are_add_s_with_one_side_trial_a_row_apart_from_its_tokens_and_cache_counts(tmp_path):
    rows = [row("q1", True, input_tokens=1000, output_tokens=200, cached_input_tokens=300,
                **side(40, 10, 960, 190)),
            row("q2", False, **side(0, 0, 7, 0)),
            row("q3", True, input_tokens=5, output_tokens=6)]
    stats = calibrate_from_results(rows)
    by_hand = Stats()
    by_hand.add("t", PAIR, 1, 1, input_tokens=1000, output_tokens=200, cached_input_tokens=300,
                **side(40, 10, 960, 190), side_trials=1)
    by_hand.add("t", PAIR, 0, 1, **side(0, 0, 7, 0), side_trials=1)
    by_hand.add("t", PAIR, 1, 1, input_tokens=5, output_tokens=6)
    assert saved(stats, tmp_path / "a.json") == saved(by_hand, tmp_path / "b.json")
    assert stats.tokens("t", PAIR) == (1005, 206, 2)
    assert stats.cache_tokens("t", PAIR) == (300, 1, 0, 0)
    assert stats.side_tokens("t", PAIR) == (40, 10, 967, 190, 2)


def test_a_row_without_the_four_builds_v1_671_s_stats_and_bytes(tmp_path):
    rows = [row("q1", True, input_tokens=100, output_tokens=20), row("q2", False)]
    stats = calibrate_from_results(rows)
    by_hand = Stats()
    by_hand.add("t", PAIR, 1, 1, input_tokens=100, output_tokens=20)
    by_hand.add("t", PAIR, 0, 1)
    assert saved(stats, tmp_path / "a.json") == saved(by_hand, tmp_path / "b.json")
    assert stats.side_tokens("t", PAIR) == (0, 0, 0, 0, 0)
    assert stats.mean_side_tokens("t", PAIR) is None
    written = json.loads((tmp_path / "a.json").read_text(encoding="utf-8"))["stats"][0]
    assert not set(SIDES) & set(written) and "side_trials" not in written


def test_a_row_s_side_trials_is_not_read():
    stats = calibrate_from_results([row("q1", True, side_trials=7, **side(1, 2, 3, 4)),
                                    row("q2", True, side_trials=7)])
    assert stats.side_tokens("t", PAIR) == (1, 2, 3, 4, 1)
    assert stats.get("t", PAIR) == (2, 2)


# --- checks ------------------------------------------------------------------------------------

@pytest.mark.parametrize("given", [SIDES[:1], SIDES[:2], SIDES[:3], SIDES[1:], SIDES[3:]],
                         ids=["root input", "the root's two", "three", "all but root input", "leaf output"])
def test_a_partial_set_is_refused_naming_the_row(given):
    bad = row("q2", True, **{key: 1 for key in given})
    with pytest.raises(ValueError, match="together or none") as raised:
        calibrate_from_results([row("q1", True, **side(1, 1, 1, 1)), bad])
    assert repr(bad) in str(raised.value)


@pytest.mark.parametrize("position, value", [(0, None), (1, True), (2, False), (3, 1.0), (0, "1"), (2, -1),
                                             (1, [1])],
                         ids=["null", "true", "false", "a float", "a string", "negative", "a list"])
def test_a_bad_value_is_refused_naming_the_row(position, value):
    counts = [1, 1, 1, 1]
    counts[position] = value
    bad = row("q2", True, **side(*counts))
    with pytest.raises(ValueError, match="side token counts must be integers >= 0") as raised:
        calibrate_from_results([row("q1", True, **side(1, 1, 1, 1)), bad])
    assert repr(bad) in str(raised.value)


def test_null_read_from_json_is_refused_and_not_taken_for_none_given():
    bad = json.loads('{"task": "t", "model": "r/strong+l/cheap", "correct": true, "root_input_tokens": null,'
                     ' "root_output_tokens": null, "leaf_input_tokens": null, "leaf_output_tokens": null}')
    with pytest.raises(ValueError, match="side token counts must be integers >= 0"):
        calibrate_from_results([bad])


@pytest.mark.parametrize("model_id, extra", [("x/a>x/b@low", {"escalated": False}),
                                             ("proc:p@1", {"cost_usd": 0.5})], ids=["cascade", "procedure"])
def test_a_cascade_or_procedure_row_with_the_four_is_refused(model_id, extra):
    assert calibrate_from_results([row("q1", True, model=model_id, **extra)]).get("t", model_id) == (1, 1)
    bad = row("q1", True, model=model_id, **extra, **side(1, 1, 1, 1))
    with pytest.raises(ValueError, match="a cascade or procedure row carries no side tokens") as raised:
        calibrate_from_results([bad])
    assert repr(bad) in str(raised.value)


def test_item_outcomes_runs_the_same_checks():
    good = [row("q1", True, **side(1, 1, 1, 1))]
    assert len(item_outcomes(good, dataset_sha256=SHA)) == 1
    with pytest.raises(ValueError, match="together or none"):
        item_outcomes(good + [row("q2", True, root_input_tokens=1)], dataset_sha256=SHA)


# --- slices and reruns -------------------------------------------------------------------------

def test_a_sliced_row_adds_its_side_trial_under_both_keys():
    stats = calibrate_from_results([row("q1", True, slice="long", **side(1, 2, 3, 4)),
                                    row("q2", False, **side(10, 20, 30, 40))])
    assert stats.side_tokens("t", PAIR) == (11, 22, 33, 44, 2)
    assert stats.side_tokens("t@long", PAIR) == (1, 2, 3, 4, 1)
    assert stats.get("t@long", PAIR) == (1, 1)


def test_a_rerun_above_0_is_checked_and_adds_no_side_trial():
    rows = [row("q1", True, rerun=0, **side(10, 10, 10, 10)), row("q1", True, rerun=1, **side(99, 99, 99, 99))]
    stats = calibrate_from_results(rows)
    assert stats.side_tokens("t", PAIR) == (10, 10, 10, 10, 1)
    assert stats.consistency("t", PAIR) == (1, 1)
    with pytest.raises(ValueError, match="together or none"):
        calibrate_from_results([rows[0], row("q1", True, rerun=1, leaf_output_tokens=1)])


# --- 5.2 v1.671: select_pair prices each side at the tokens read from the rows ----------------

def test_select_pair_on_calibrated_rows_is_the_decision_on_add_s_side_tokens():
    # root 50 in, 200 out per trial at 10 and 30 per million: (500 + 6000) / 1e6 = 0.0065
    # leaf 4,000 in, 100 out at 0.1 and 0.3 per million: (400 + 30) / 1e6 = 0.00043
    rows = []
    for (root, leaf), wins in PAIRS.items():
        extra = side(50, 200, 4000, 100) if (root, leaf) == ("r/strong", "l/cheap") else {}
        rows += [row(f"p{k}", k < wins, model=f"{root}+{leaf}", **extra) for k in range(N)]
    rows += [row(f"s{k}", True, model=model_id) for model_id in ROOTS + LEAVES for k in range(N)]
    task = Task("t", bar=0.8, min_samples=30)
    decision = Router(registry(), {"t": task}, calibrate_from_results(rows)).select_pair("t", ROOTS, LEAVES)
    priced = by_id(decision)[PAIR]
    assert priced.list_cost == pytest.approx(0.0065 + 0.00043, rel=1e-12)
    by_hand = router(pair_extra={("r/strong", "l/cheap"): sides(50, 200, 4000, 100)})
    assert decision.to_dict() == by_hand.select_pair("t", ROOTS, LEAVES).to_dict()


# --- the docs say it ---------------------------------------------------------------------------

def test_design_4_3_states_v1_672_and_the_v1_671_lists_point_to_it():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four_three = text.split("\n### 4.3 ", 1)[1].split("\n### 4.4 ", 1)[0]
    assert "\n- v1.672 a pair's side tokens from a results row (row DEL1bb, the second part of row DEL1b):" in four_three
    assert "`calibrate_from_results` reading each side's tokens from a results row that names both models (row DEL1bb, which ships in v1.672)" in four_three
    assert "side tokens read from a results row by `calibrate_from_results` (row DEL1bb, which ships in 4.3 v1.672)" in text
    doc = model_routing.calibrate_from_results.__doc__
    assert "``root_input_tokens``" in doc and "(DESIGN 4.3 v1.672)" in doc


def test_no_readme_evidence_or_research_file_writes_the_four():
    paths = [ROOT / "README.md", *(ROOT / ".github" / "workflows").glob("*"),
             *(path for path in (ROOT / "evidence").rglob("*") if path.is_file()),
             *(path for path in (ROOT / "research").rglob("*") if path.is_file())]
    assert len(paths) > 50
    for path in paths:
        assert not any(key.encode() in path.read_bytes() for key in SIDES), path
