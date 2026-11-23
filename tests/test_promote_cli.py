"""`model-routing promote` and `pair_outcomes` (DESIGN 4.7 and 10 v1.603, row GATE1c).

The command pairs a challenger's per-item outcomes with those of `select`'s primary on one labeled
file's hash, requires the challenger's own admission and prints `paired_promotion`'s decision. It
is advisory: no route or file changes.
"""

import copy
import hashlib
import json
from dataclasses import asdict
from datetime import date
from pathlib import Path

import pytest

import model_routing
from model_routing import pair_outcomes, paired_promotion
from model_routing.cli import main

ROOT = Path(__file__).resolve().parent.parent
TODAY = date(2026, 1, 2)
STRONG, CHEAP, WEAK = "fiction/a-strong", "fiction/b-cheap", "fiction/c-weak"
H1 = hashlib.sha256(b"one").hexdigest()
H2 = hashlib.sha256(b"two").hexdigest()


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def setup(tmp_path, *results, min_samples=10, slices=None, expired=None, variants=None, **task_extra):
    """Write a registry and a task file, calibrate each results list with --outcomes, return args."""
    models = [{"id": m, "family": m.split("-")[1], "price_in": pin, "price_out": pout,
               "context_window": 100000, "source": "https://example.org/prices"}
              for m, pin, pout in ((STRONG, 10.0, 20.0), (CHEAP, 1.0, 2.0), (WEAK, 0.5, 1.0))]
    if expired is not None:
        models[0]["price_valid_until"] = expired
    if variants is not None:
        models[0]["variants"] = variants
    (tmp_path / "models.json").write_text(json.dumps(
        {"version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models}))
    task = {"name": "t", "bar": 0.5, "min_samples": min_samples, "expected_input_tokens": 1000,
            "expected_output_tokens": 100}
    if slices:
        task["slices"] = slices
    task.update(task_extra)
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [task]}))
    for n, rows in enumerate(results):
        path = tmp_path / f"results{n}.jsonl"
        write_jsonl(path, rows)
        assert main(["calibrate", "--results", str(path), "--stats", str(tmp_path / "stats.json"),
                     "--outcomes", str(tmp_path / "outcomes.jsonl")]) == 0
    return ["--registry", str(tmp_path / "models.json"), "--tasks", str(tmp_path / "tasks.json"),
            "--stats", str(tmp_path / "stats.json"), "--priors", str(tmp_path / "none.json"),
            "--outcomes", str(tmp_path / "outcomes.jsonl")]


def rows(model, right, items, **extra):
    return [dict({"task": "t", "model": model, "item": f"q{i}", "correct": i in right}, **extra)
            for i in items]


def win_rows():
    # 40 items: the cheap route right on q10 to q39, the strong one on all but q0, the weak on 3
    return (rows(CHEAP, set(range(10, 40)), range(40)) + rows(STRONG, set(range(1, 40)), range(40))
            + rows(WEAK, {0, 1, 2}, range(40)))


def promote(files, challenger, *extra, margin="0.02"):
    return main(["promote", "--task", "t", "--challenger", challenger, "--margin", margin, *files,
                 *extra], today=TODAY)


def run_json(capsys, files, challenger, *extra, margin="0.02"):
    assert promote(files, challenger, "--json", *extra, margin=margin) == 0
    return json.loads(capsys.readouterr().out)


def file_hash(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


# --- the decisions -------------------------------------------------------------------------------

def test_a_clear_win_promotes_as_superior_and_prints_every_line(tmp_path, capsys):
    files = setup(tmp_path, win_rows())
    capsys.readouterr()
    assert promote(files, STRONG) == 0
    out = capsys.readouterr()
    assert out.err == ""
    assert out.out.splitlines() == [
        "task:                 t",
        "flavor:               cost_effective",
        "current:              fiction/b-cheap",
        "challenger:           fiction/a-strong",
        f"dataset_sha256:       {file_hash(tmp_path / 'results0.jsonl')}",
        "current_list_cost:    0.001200",
        "challenger_list_cost: 0.012000",
        "decision:             promote",
        "basis:                superior",
        "pairs:                40",
        "unpaired:             0",
        "current_only:         0",
        "challenger_only:      9",
        "current_rate:         0.750000",
        "challenger_rate:      0.975000",
        "difference:           0.225000",
        "p_value:              0.003906",
        "lower_bound:          0.073734",
        "margin:               0.02",
        "cheaper:              false",
        "alpha:                0.05",
        "min_pairs:            10",
    ]


def test_json_holds_the_keys_in_order_and_the_check_unrounded(tmp_path, capsys):
    files = setup(tmp_path, win_rows())
    capsys.readouterr()
    data = run_json(capsys, files, STRONG)
    assert list(data) == ["task", "slice", "flavor", "current", "challenger", "dataset_sha256",
                          "current_list_cost", "challenger_list_cost", "decision", "basis", "pairs",
                          "unpaired", "current_only", "challenger_only", "current_rate",
                          "challenger_rate", "difference", "p_value", "lower_bound", "margin",
                          "cheaper", "alpha", "min_pairs"]
    assert data["slice"] is None
    current = {f"q{i}": i >= 10 for i in range(40)}
    challenger = {f"q{i}": i >= 1 for i in range(40)}
    check = asdict(paired_promotion(current, challenger, margin=0.02, min_pairs=10))
    assert {k: data[k] for k in check} == check
    assert data["p_value"] == 2 / 512


def test_a_cheaper_non_inferior_challenger_promotes_under_cost_blind(tmp_path, capsys):
    same = set(range(6, 60))  # both right on 54 of 60, so b = c = 0
    files = setup(tmp_path, rows(STRONG, same, range(60)) + rows(CHEAP, same, range(60)))
    capsys.readouterr()
    data = run_json(capsys, files, CHEAP, "--flavor", "cost_blind", margin="0.05")
    assert (data["current"], data["cheaper"]) == (STRONG, True)
    assert (data["decision"], data["basis"], data["pairs"]) == ("promote", "non_inferior", 60)
    assert data["lower_bound"] == pytest.approx(-0.044707, abs=1e-6)
    tight = run_json(capsys, files, CHEAP, "--flavor", "cost_blind", margin="0.02")
    assert (tight["decision"], tight["basis"]) == ("hold", None)


def test_cheaper_is_per_item_so_a_batched_route_dearer_per_call_is_cheaper(tmp_path, capsys):
    # review iter-452 must-fix 1: four items a call at 2,000 in and 200 out tokens is 0.024 a call
    # and 0.006 an item, against the single-item route's 0.012 a call at the task's sizes
    batch = STRONG + "@batch"
    same = set(range(6, 60))
    files = setup(tmp_path, rows(STRONG, same, range(60))
                  + rows(batch, same, range(60), input_tokens=2000, output_tokens=200),
                  variants={"batch": {"items_per_call": 4}})
    capsys.readouterr()
    data = run_json(capsys, files, batch, "--flavor", "cost_blind", margin="0.05")
    assert (data["current"], data["challenger"]) == (STRONG, batch)
    assert (data["current_list_cost"], data["challenger_list_cost"]) == pytest.approx((0.012, 0.006))
    assert (data["cheaper"], data["decision"], data["basis"]) == (True, "promote", "non_inferior")


def test_a_retry_same_task_can_have_a_cheaper_challenger_under_cost_effective(tmp_path, capsys):
    # review iter-452 should-fix 1: its primary is the cheapest per success (0.0012 / 0.863 against
    # 0.0006 / 0.377), so the cheaper weak route passes beside it and is checked as cheaper
    files = setup(tmp_path, rows(CHEAP, set(range(3, 60)), range(60)) + rows(WEAK, set(range(30)), range(60)),
                  bar=0.3, failure_policy="retry_same")
    capsys.readouterr()
    data = run_json(capsys, files, WEAK)
    assert (data["flavor"], data["current"], data["cheaper"]) == ("cost_effective", CHEAP, True)
    # the cheap route alone right on q30 to q59, the weak one alone on q0 to q2
    assert (data["decision"], data["current_only"], data["challenger_only"]) == ("hold", 30, 3)


def test_a_low_power_tie_holds(tmp_path, capsys):
    files = setup(tmp_path, rows(CHEAP, set(range(2, 12)), range(12))
                  + rows(STRONG, set(range(12)) - {2}, range(12)))
    capsys.readouterr()
    data = run_json(capsys, files, STRONG)
    assert (data["current"], data["decision"], data["basis"]) == (CHEAP, "hold", None)
    assert (data["current_only"], data["challenger_only"], data["p_value"]) == (1, 2, 1.0)
    assert data["cheaper"] is False


def test_too_few_shared_items_give_insufficient_overlap(tmp_path, capsys):
    files = setup(tmp_path, rows(CHEAP, set(range(20)), range(20))
                  + rows(STRONG, set(range(10, 30)), range(10, 30)), min_samples=15)
    capsys.readouterr()
    data = run_json(capsys, files, STRONG)
    assert (data["decision"], data["pairs"], data["unpaired"], data["min_pairs"]) == (
        "insufficient_overlap", 10, 20, 15)
    assert data["p_value"] is None and data["lower_bound"] is None
    assert promote(files, STRONG) == 0
    out = capsys.readouterr().out.splitlines()
    assert "p_value:              n/a" in out and "basis:                n/a" in out


def test_the_slice_reads_only_its_records_and_its_min_samples(tmp_path, capsys):
    deep = rows(CHEAP, set(range(6)), range(6), slice="deep") + rows(STRONG, set(range(6)), range(6), slice="deep")
    easy = (rows(CHEAP, set(range(6, 21)), range(6, 21), slice="easy")
            + rows(STRONG, set(range(6, 21)), range(6, 21), slice="easy"))
    files = setup(tmp_path, deep + easy, slices={"deep": {"min_samples": 5}})
    capsys.readouterr()
    pooled = run_json(capsys, files, STRONG)
    assert (pooled["slice"], pooled["pairs"], pooled["min_pairs"]) == (None, 21, 10)
    sliced = run_json(capsys, files, STRONG, "--slice", "deep")
    assert (sliced["slice"], sliced["pairs"], sliced["min_pairs"]) == ("deep", 6, 5)
    assert promote(files, STRONG, "--slice", "deep") == 0
    assert capsys.readouterr().out.splitlines()[:2] == ["task:                 t",
                                                        "slice:                deep"]


def test_a_file_calibrated_twice_pairs_as_once(tmp_path, capsys):
    (tmp_path / "a").mkdir()
    (tmp_path / "b").mkdir()
    files_once, files_twice = setup(tmp_path / "a", win_rows()), setup(tmp_path / "b", win_rows(), win_rows())
    capsys.readouterr()
    once, twice = run_json(capsys, files_once, STRONG), run_json(capsys, files_twice, STRONG)
    keys = ["decision", "basis", "pairs", "unpaired", "current_only", "challenger_only", "p_value"]
    assert [twice[k] for k in keys] == [once[k] for k in keys]
    assert twice["dataset_sha256"] == once["dataset_sha256"]


# --- refusals ------------------------------------------------------------------------------------

def last_error(capsys):
    out = capsys.readouterr()
    assert out.out == ""
    lines = out.err.splitlines()
    assert lines[-1].startswith("error: ")
    return lines


def test_differing_hashes_are_refused_and_a_named_one_must_hold_both_routes(tmp_path, capsys):
    files = setup(tmp_path, rows(CHEAP, set(range(10, 40)), range(40)),
                  rows(STRONG, set(range(1, 40)), range(40)))
    capsys.readouterr()
    assert promote(files, STRONG) == 2
    lines = last_error(capsys)
    assert len(lines) == 1 and "carry 2 dataset hashes" in lines[0]
    one, two = file_hash(tmp_path / "results0.jsonl"), file_hash(tmp_path / "results1.jsonl")
    assert f"({', '.join(sorted([one, two]))})" in lines[0]
    assert promote(files, STRONG, "--dataset-sha256", one) == 2
    assert last_error(capsys) == [f"error: route {STRONG!r} has no outcome on task 't' "
                                  f"with dataset_sha256 {one}"]


def test_a_named_hash_picks_one_labeled_file(tmp_path, capsys):
    files = setup(tmp_path, win_rows(), rows(STRONG, set(range(40, 50)), range(40, 50)))
    capsys.readouterr()
    assert promote(files, STRONG) == 2
    capsys.readouterr()
    first = file_hash(tmp_path / "results0.jsonl")
    data = run_json(capsys, files, STRONG, "--dataset-sha256", first)
    assert (data["dataset_sha256"], data["pairs"], data["decision"]) == (first, 40, "promote")


def test_an_unadmitted_challenger_exits_3(tmp_path, capsys):
    files = setup(tmp_path, win_rows())
    capsys.readouterr()
    assert promote(files, WEAK) == 3
    assert last_error(capsys) == [f"error: challenger {WEAK} is not admitted on task t: below_bar"]
    (tmp_path / "s").mkdir()
    sliced = setup(tmp_path / "s", rows(CHEAP, set(range(12)), range(12), slice="deep"))
    capsys.readouterr()
    assert promote(sliced, STRONG, "--slice", "deep") == 3
    assert last_error(capsys) == [
        f"error: challenger {STRONG} is not admitted on task t slice deep: insufficient_samples"]


def test_no_route_clearing_the_bar_exits_3_naming_the_challenger(tmp_path, capsys):
    files = setup(tmp_path, rows(CHEAP, set(), range(12)) + rows(STRONG, {0}, range(12)))
    capsys.readouterr()
    assert promote(files, STRONG) == 3
    assert last_error(capsys) == [f"error: challenger {STRONG} is not admitted on task t: below_bar"]


def test_the_current_route_as_challenger_is_refused(tmp_path, capsys):
    files = setup(tmp_path, win_rows())
    capsys.readouterr()
    assert promote(files, CHEAP) == 2
    assert last_error(capsys) == [f"error: current and challenger must differ, both are {CHEAP!r}"]


def test_conflicting_repeats_are_refused(tmp_path, capsys):
    files = setup(tmp_path, win_rows() + [{"task": "t", "model": STRONG, "item": "q5", "correct": False}])
    capsys.readouterr()
    assert promote(files, STRONG) == 2
    assert last_error(capsys) == [f"error: route {STRONG!r} has conflicting outcomes for item 'q5' "
                                  "on task 't'"]


@pytest.mark.parametrize("extra, needle", [
    (["--margin", "1.5"], "margin must be a number in [0, 1)"),
    (["--margin", "nan"], "margin must be a number in [0, 1)"),
    (["--alpha", "0"], "alpha must be a number strictly between 0 and 1"),
])
def test_a_bad_margin_or_alpha_exits_2_before_any_file_is_read(tmp_path, capsys, extra, needle):
    args = ["promote", "--task", "t", "--challenger", STRONG, "--margin", "0.02",
            "--outcomes", str(tmp_path / "missing.jsonl"), "--registry", str(tmp_path / "missing.json"),
            *extra]
    assert main(args, today=TODAY) == 2
    lines = last_error(capsys)
    assert len(lines) == 1 and needle in lines[0]


def test_unknown_task_challenger_or_a_bad_outcome_line_exit_2(tmp_path, capsys):
    files = setup(tmp_path, win_rows())
    capsys.readouterr()
    assert promote(files, "fiction/none") == 2
    assert last_error(capsys) == ["error: unknown model: 'fiction/none'"]
    assert main(["promote", "--task", "nope", "--challenger", STRONG, "--margin", "0.02", *files],
                today=TODAY) == 2
    assert "unknown task" in last_error(capsys)[0]
    with (tmp_path / "outcomes.jsonl").open("a", encoding="utf-8") as handle:
        handle.write('{"task": "t"}\n')
    assert promote(files, STRONG) == 2
    assert "outcome record 121" in last_error(capsys)[0]


def test_promote_changes_no_file(tmp_path, capsys):
    files = setup(tmp_path, win_rows())
    before = {p.name: p.read_bytes() for p in tmp_path.iterdir()}
    for challenger in (STRONG, WEAK, CHEAP):
        promote(files, challenger)
        promote(files, challenger, "--json")
    assert {p.name: p.read_bytes() for p in tmp_path.iterdir()} == before


def test_expired_prices_warn_only_after_a_decision(tmp_path, capsys):
    files = setup(tmp_path, win_rows(), expired="2026-01-01")
    capsys.readouterr()
    assert promote(files, STRONG) == 0
    out = capsys.readouterr()
    assert out.err.splitlines() == [f"warning: list price of {STRONG} was stated valid through "
                                    "2026-01-01; check the vendor page and update the registry"]
    assert promote(files, WEAK) == 3
    assert len(last_error(capsys)) == 1


# --- pair_outcomes -------------------------------------------------------------------------------

def rec(route, item, correct, *, task="t", slice=None, sha=H1):
    return {"task": task, "slice": slice, "route": route, "item": item, "correct": correct,
            "dataset_sha256": sha}


def test_pair_outcomes_returns_both_maps_in_first_read_order_and_the_hash():
    records = [rec("x", "q2", True), rec("y", "q1", False), rec("x", "q1", False),
               rec("z", "q9", True), rec("x", "q9", True, task="other"), rec("y", "q2", True)]
    kept = copy.deepcopy(records)
    current, challenger, sha = pair_outcomes(iter(records), task="t", current="x", challenger="y")
    assert list(current.items()) == [("q2", True), ("q1", False)]
    assert list(challenger.items()) == [("q1", False), ("q2", True)]
    assert sha == H1 and records == kept


def test_pair_outcomes_filters_by_slice_and_by_a_named_hash():
    records = [rec("x", "a", True, slice="deep"), rec("y", "a", True, slice="deep"),
               rec("x", "b", True, slice="easy"), rec("y", "b", False, slice="easy", sha=H1)]
    cur, chal, _ = pair_outcomes(records, task="t", current="x", challenger="y", slice="deep")
    assert (cur, chal) == ({"a": True}, {"a": True})
    cur, chal, _ = pair_outcomes(records, task="t", current="x", challenger="y")
    assert (cur, chal) == ({"a": True, "b": True}, {"a": True, "b": False})
    mixed = records + [rec("x", "c", True, sha=H2)]
    with pytest.raises(ValueError, match="carry 2 dataset hashes"):
        pair_outcomes(mixed, task="t", current="x", challenger="y")
    assert pair_outcomes(mixed, task="t", current="x", challenger="y", dataset_sha256=H1)[0] == {
        "a": True, "b": True}
    with pytest.raises(ValueError, match="route 'x' has no outcome on task 't' slice 'deep' with dataset_sha256"):
        pair_outcomes(mixed, task="t", current="x", challenger="y", slice="deep", dataset_sha256=H2)


def test_pair_outcomes_counts_an_agreeing_repeat_once_and_refuses_a_conflict():
    records = [rec("x", "a", True), rec("x", "a", True), rec("y", "a", False)]
    assert pair_outcomes(records, task="t", current="x", challenger="y")[0] == {"a": True}
    with pytest.raises(ValueError, match="route 'y' has conflicting outcomes for item 'a' on task 't'"):
        pair_outcomes(records + [rec("y", "a", True)], task="t", current="x", challenger="y")


def test_pair_outcomes_refuses_a_route_with_no_record():
    with pytest.raises(ValueError, match="route 'y' has no outcome on task 't'$"):
        pair_outcomes([rec("x", "a", True)], task="t", current="x", challenger="y")


@pytest.mark.parametrize("bad", [
    "not a dict", {"task": "t"}, dict(rec("x", "a", True), task=""), dict(rec("x", "a", True), route=1),
    dict(rec("x", "a", True), item=None), dict(rec("x", "a", True), slice=""),
    dict(rec("x", "a", True), slice="a@b"), dict(rec("x", "a", True), correct="true"),
    dict(rec("x", "a", True), correct=1), dict(rec("x", "a", True), dataset_sha256=H1.upper()),
    dict(rec("x", "a", True), dataset_sha256=H1[:63]),
])
def test_pair_outcomes_checks_every_record_first(bad):
    # the bad record is of another task and comes last, so only a check of every record finds it
    with pytest.raises(ValueError, match="outcome record 3"):
        pair_outcomes([rec("x", "a", True), rec("y", "a", True), bad], task="other",
                      current="x", challenger="y")


@pytest.mark.parametrize("kwargs", [
    {"task": ""}, {"task": 1}, {"current": ""}, {"challenger": None}, {"challenger": "x"},
    {"slice": ""}, {"slice": "a@b"}, {"dataset_sha256": "abc"}, {"dataset_sha256": H1.upper()},
])
def test_pair_outcomes_checks_its_arguments(kwargs):
    args = dict({"task": "t", "current": "x", "challenger": "y"}, **kwargs)
    with pytest.raises(ValueError):
        pair_outcomes([rec("x", "a", True), rec("y", "a", True)], **args)


def test_pair_outcomes_is_keyword_only():
    with pytest.raises(TypeError):
        pair_outcomes([], "t", "x", "y")


# --- exports and docs ----------------------------------------------------------------------------

def test_pair_outcomes_is_exported_after_item_outcomes():
    names = model_routing.__all__
    assert names[names.index("item_outcomes") + 1] == "pair_outcomes"
    assert model_routing.pair_outcomes is model_routing.promotion.pair_outcomes


def test_design_and_changelog_name_the_contract():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    # review iter-453 nit 1: the Status line keeps five versions (tests/test_design_status.py), so the
    # version is pinned by its changelog line, which stays
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert sum(line.startswith("- v1.603 (2026-11-23): spec, code and tests (3, 4.7, 10, row GATE1c). ")
               for line in changelog) == 1
    assert "  promotion.py    paired_promotion, PromotionCheck (v1.601, 4.7), pair_outcomes (v1.603, 4.7)\n" in design
    seven = design[design.index("### 4.7 "):design.index("## 5. ")]
    assert ("- v1.603 `pair_outcomes(records, *, task, current, challenger, slice=None, dataset_sha256=None) "
            "-> tuple[dict, dict, str]` (row GATE1c): ") in seven
    assert "`model_routing.__all__` gains `pair_outcomes`, after `item_outcomes`.\n" in seven
    assert "(row GATE1c), which v1.603 adds (10); the README paragraph (row GATE1d).\n" in seven
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    assert "- v1.603 `promote --task T --challenger ROUTE --margin M --outcomes FILE [--slice S] " in ten
    assert "`error: challenger ROUTE is not admitted on task T: REASON`" in ten
    assert "(4.7, review iter-449 should-fix 3(a))" in ten
    for finding in ("must-fix 1", "should-fix 1", "should-fix 2"):
        assert f"(review iter-452 {finding})" in ten
    assert "and on `promote` a challenger the bar does not admit (v1.603);" in ten
    lines = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in lines if line.startswith("- v1.603 (2026-11-23): ")]
    assert len(mine) == 1 and "(3, 4.7, 10, row GATE1c)" in mine[0]


def test_the_note_names_the_command_as_shipped():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    locked = note[note.index("### Switch models only on locked data and a significant result"):]
    line = [x for x in locked.splitlines() if x.startswith("- In this library: ")][0]
    assert line.endswith("From v1.603 `model-routing promote` pairs the challenger's outcomes with the current "
                         "route's on that hash, requires the bar to admit the challenger first, and prints the "
                         "check's decision without changing a route.")
    assert "The change still planned" not in line
    assert note.count("its comparison `paired_promotion` from v1.601 and the command that runs it, "
                      "`model-routing promote`, from v1.603.") == 1
    assert "the command that runs it planned" not in note


def test_the_readme_layout_names_the_subcommand():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ("  cli.py        model-routing select | calibrate | report | demo | evaluate | delegate | plan "
            "| promote\n") in readme
