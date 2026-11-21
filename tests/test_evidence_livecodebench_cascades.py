"""DESIGN 7 v1.548 (row ESC3k): the LiveCodeBench cascade replay, evidence/livecodebench/cascades.py.

The script turns 12.16 matrix rows and the v1.534 kind of each failed first sample into cascade rows in
the 12.1 v1.538 format. These tests were committed before it under a module-level strict xfail whose
error is the one loading a missing file by path raises, FileNotFoundError, and the implementing commit
removed the mark. Every test uses synthetic rows and kinds; none reads the pinned files."""

import copy
import importlib.util
import math
import re
from pathlib import Path

import pytest

from model_routing import Cascade, evaluate, outcomes_from_rows

pytestmark = pytest.mark.xfail(strict=True, raises=FileNotFoundError)

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "livecodebench" / "cascades.py"
RESEARCH = ROOT / "research" / "escalation_public_tests.py"
P, PN = "public-test-failed", "public-test-failed-or-no-test"

_loaded = []


def m():
    if not _loaded:
        spec = importlib.util.spec_from_file_location("livecodebench_cascades", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _loaded.append(module)
    return _loaded[0]


def test_signals_and_kinds_are_the_esc1c_ones():
    assert m().SIGNALS == (P, PN)
    assert m().KINDS == ("public", "other", "input_only", "no_test", "unread")
    text = RESEARCH.read_text(encoding="utf-8")
    assert re.search(r'^KINDS = \("public", "other", "input_only", "no_test", "unread"\)$', text, re.M)


TABLE = [(None, P, False), (None, PN, False), ("public", P, True), ("public", PN, True),
         ("other", P, False), ("other", PN, False), ("input_only", P, False), ("input_only", PN, False),
         ("no_test", P, False), ("no_test", PN, True)]


@pytest.mark.parametrize("kind,signal,want", TABLE)
def test_escalates_on_each_kind_and_signal(kind, signal, want):
    assert m().escalates(kind, signal) is want


@pytest.mark.parametrize("signal", ["public-test-failed ", "", None, 1, "calls-over-10", "PUBLIC-TEST-FAILED",
                                    b"public-test-failed"])
def test_escalates_refuses_an_unknown_signal_before_the_kind(signal):
    with pytest.raises(ValueError) as info:
        m().escalates("bogus", signal)
    assert "unknown signal" in str(info.value) and repr(signal) in str(info.value)


@pytest.mark.parametrize("kind", ["private", "", 0, False, "Public", ("public",)])
def test_escalates_refuses_an_unknown_kind(kind):
    with pytest.raises(ValueError, match="unknown kind"):
        m().escalates(kind, P)


@pytest.mark.parametrize("signal", [P, PN])
def test_escalates_refuses_an_unread_sample(signal):
    with pytest.raises(ValueError, match="no readable metadata"):
        m().escalates("unread", signal)


# --- cascade_cell

def cell(correct, cost=0.0, **extra):
    return {"correct": correct, "cost_usd": cost, **extra}


def test_cascade_cell_keeps_the_cheap_sample_when_the_signal_does_not_fire():
    for kind, cheap in ((None, cell(True, 0.25)), ("other", cell(False, 0.25)), ("no_test", cell(False, 0.25))):
        got = m().cascade_cell(cheap, cell(True, 0.5, difficulty="1-easy"), kind, P)
        assert got == {"correct": cheap["correct"], "cost_usd": 0.25, "escalated": False}
        assert list(got) == ["correct", "cost_usd", "escalated"]


@pytest.mark.parametrize("kind,signal", [("public", P), ("public", PN), ("no_test", PN)])
@pytest.mark.parametrize("strong", [True, False])
def test_cascade_cell_hands_a_failed_sample_up_and_adds_both_costs(kind, signal, strong):
    got = m().cascade_cell(cell(False, 0.1), cell(strong, 0.2), kind, signal)
    assert got == {"correct": strong, "cost_usd": math.fsum([0.1, 0.2]), "escalated": True}
    assert list(got) == ["correct", "cost_usd", "escalated"]
    zero = m().cascade_cell(cell(False), cell(True), kind, signal)
    assert zero == {"correct": True, "cost_usd": 0.0, "escalated": True}


@pytest.mark.parametrize("kind,correct", [(None, False), ("public", True), ("other", True), ("no_test", True)])
def test_cascade_cell_refuses_a_kind_that_disagrees_with_the_label(kind, correct):
    with pytest.raises(ValueError):
        m().cascade_cell(cell(correct), cell(True), kind, PN)


def test_cascade_cell_checks_the_signal_and_kind_first():
    with pytest.raises(ValueError, match="unknown signal"):
        m().cascade_cell(cell(True), cell(True), "public", "transfer")
    with pytest.raises(ValueError, match="no readable metadata"):
        m().cascade_cell(cell(True), cell(True), "unread", P)


# --- cascade_rows

C, S, W = "x/cheap", "y/strong", "z/weak"
CID, NID = f"{C}>{S}@{P}", f"{C}>{S}@{PN}"
T = "code_generation"


def row(item, model, correct, difficulty="1-easy"):
    r = {"task": T, "item": item, "model": model, "correct": correct, "cost_usd": 0.0}
    if difficulty is not None:
        r["difficulty"] = difficulty
    return r


def matrix(difficulty=True):
    d = (lambda v: v) if difficulty else (lambda v: None)
    return [row("a", C, True, d("1-easy")), row("a", S, True, d("1-easy")),
            row("b", C, False, d("2-medium")), row("b", S, True, d("2-medium")),
            row("c", C, False, d("3-hard")), row("c", S, False, d("3-hard")),
            row("d", C, False, d("3-hard")), row("d", S, True, d("3-hard"))]


KINDS_OF = {(C, "b"): "public", (C, "c"): "public", (C, "d"): "no_test"}


def test_cascade_rows_add_one_row_per_cascade_and_item_sorted():
    rows, kinds = matrix(), dict(KINDS_OF)
    before = (copy.deepcopy(rows), copy.deepcopy(kinds))
    got = m().cascade_rows(rows, kinds, [Cascade(C, S, P), Cascade(C, S, PN)])
    def c(item, cid, correct, up, difficulty):
        return {"task": T, "item": item, "model": cid, "correct": correct, "cost_usd": 0.0, "escalated": up,
                "difficulty": difficulty}
    assert got == [
        rows[0], c("a", CID, True, False, "1-easy"), c("a", NID, True, False, "1-easy"), rows[1],
        rows[2], c("b", CID, True, True, "2-medium"), c("b", NID, True, True, "2-medium"), rows[3],
        rows[4], c("c", CID, False, True, "3-hard"), c("c", NID, False, True, "3-hard"), rows[5],
        rows[6], c("d", CID, False, False, "3-hard"), c("d", NID, True, True, "3-hard"), rows[7],
    ]
    assert all(list(r) == ["task", "item", "model", "correct", "cost_usd", "escalated", "difficulty"]
               for r in got if ">" in r["model"])
    assert (rows, kinds) == before and not any(r is s for r in got for s in rows)


def test_cascade_rows_without_difficulty_and_in_any_input_order():
    rows = list(reversed(matrix(difficulty=False)))
    got = m().cascade_rows(rows, KINDS_OF, [Cascade(C, S, PN)])
    keys = [(r["task"], r["item"], r["model"]) for r in got]
    assert keys == sorted(keys) and len(got) == 12
    assert all(list(r) == ["task", "item", "model", "correct", "cost_usd", "escalated"] for r in got if ">" in r["model"])
    assert [r for r in got if ">" not in r["model"]] == sorted(rows, key=lambda r: (r["task"], r["item"], r["model"]))
    assert m().cascade_rows(matrix(), {}, []) == matrix()


def test_cascade_rows_read_one_shot_iterables_once():
    listed = m().cascade_rows(matrix(), KINDS_OF, [Cascade(C, S, P)])
    got = m().cascade_rows(iter(matrix()), KINDS_OF, iter([Cascade(C, S, P)]))
    assert got == listed and len(got) == 12


def test_cascade_rows_ignore_kinds_of_a_model_no_cascade_starts_on():
    kinds = {**KINDS_OF, (S, "c"): "unread", (W, "q"): "bogus"}
    assert m().cascade_rows(matrix(), kinds, [Cascade(C, S, P)]) == m().cascade_rows(matrix(), KINDS_OF,
                                                                                     [Cascade(C, S, P)])


def _bad(kind):
    rows, kinds, cascades = matrix(), dict(KINDS_OF), [Cascade(C, S, P)]
    if kind == "repeated row":
        rows.append(dict(rows[0]))
    elif kind == "not a Cascade":
        cascades = [(C, S, P)]
    elif kind == "repeated cascade":
        cascades = cascades * 2
    elif kind == "unknown signal":
        cascades = [Cascade(C, S, "calls-over-10")]
    elif kind == "cheap with no row":
        cascades = [Cascade(W, S, P)]
    elif kind == "strong with no row":
        cascades = [Cascade(C, W, P)]
    elif kind == "item only the cheap has":
        rows = [r for r in rows if (r["model"], r["item"]) != (S, "b")]
    elif kind == "item only the strong has":
        rows = [r for r in rows if (r["model"], r["item"]) != (C, "b")]
        kinds.pop((C, "b"))
    elif kind == "difficulty on one row only":
        del rows[3]["difficulty"]
    elif kind == "two difficulties":
        rows[3]["difficulty"] = "3-hard"
    elif kind == "kind for a correct row":
        kinds[(C, "a")] = "other"
    elif kind == "None kind for a correct row":
        kinds[(C, "a")] = None
    elif kind == "no kind for a failed row":
        del kinds[(C, "b")]
    elif kind == "unknown kind":
        kinds[(C, "b")] = "private"
    elif kind == "unread kind":
        kinds[(C, "b")] = "unread"
    return rows, kinds, cascades


KINDS_BAD = ["repeated row", "not a Cascade", "repeated cascade", "unknown signal", "cheap with no row",
             "strong with no row", "item only the cheap has", "item only the strong has",
             "difficulty on one row only", "two difficulties", "kind for a correct row",
             "None kind for a correct row", "no kind for a failed row", "unknown kind", "unread kind"]


@pytest.mark.parametrize("kind", KINDS_BAD)
def test_cascade_rows_refuse_before_any_output(kind):
    rows, kinds, cascades = _bad(kind)
    with pytest.raises(ValueError) as info:
        m().cascade_rows(rows, kinds, cascades)
    if kind not in ("repeated row", "not a Cascade"):
        assert cascades[0].id in str(info.value)


def test_a_later_cascade_with_a_bad_kind_refuses_the_whole_call():
    kinds = dict(KINDS_OF)
    rows = matrix() + [row(i, W, False, r["difficulty"]) for i, r in (("a", matrix()[0]), ("b", matrix()[2]),
                                                                       ("c", matrix()[4]), ("d", matrix()[6]))]
    with pytest.raises(ValueError) as info:
        m().cascade_rows(rows, kinds, [Cascade(C, S, P), Cascade(W, S, P)])
    assert f"{W}>{S}@{P}" in str(info.value)


def test_the_rows_run_through_the_offline_evaluator_by_difficulty():
    rows, kinds = [], {}
    for k in range(120):
        item = f"q{k:03d}"
        level = ("1-easy", "2-medium")[k % 2]
        cheap = k % 4 != 1          # the cheap model fails a quarter, all of them 2-medium
        private = k % 8 == 1        # half of those fail on a private case only
        rows.append(row(item, C, cheap, level))
        rows.append(row(item, S, k % 16 != 9, level))
        if not cheap:
            kinds[(C, item)] = "other" if private else "public"
    got = m().cascade_rows(rows, kinds, [Cascade(C, S, P)])
    outcomes = outcomes_from_rows(got, slice_by="difficulty")
    cas = [o for o in outcomes if o.model == CID]
    assert len(cas) == 120 and sum(o.escalated for o in cas) == 15
    assert {o.slice for o in cas} == {"1-easy", "2-medium"}
    by = {(o.item, o.model): o for o in outcomes}
    assert all(by[(o.item, C)].correct <= o.correct for o in cas)
    assert sum(o.correct for o in cas) == 120 - 15 - 0 and sum(by[(o.item, C)].correct for o in cas) == 90
    result = evaluate(outcomes, bars=[0.8], seeds=range(3), flavors=("cost_blind",), min_samples=10)
    model_rows = {r["strategy"]: r for r in result["summary"]}
    assert model_rows[f"model:{CID}"]["escalation_share"] is not None
    assert 0 < model_rows[f"model:{CID}"]["escalation_share"] < 1
    assert model_rows[f"model:{CID}"]["success"] >= model_rows[f"model:{C}"]["success"]
    assert all(r["cost_usd"] == 0 for r in result["summary"])
