"""DESIGN 7 v1.532 and v1.535 (row ESC2a): cascades, part 1, the types and the stats.

A cascade starts a call on a cheap model and hands it up to a strong one when a signal the
caller computes fires on the cheap model's result (DESIGN 7 v1.532, research/escalation.md).
Row ESC2a ships its types and its calibration: `Cascade` (exported), `Task.cascades` and
`load_tasks`, the escalation count `Stats` keeps beside a cascade's counts and in its file,
and `calibrate_from_results` on a cascade row. The candidates and cost (row ESC2b) and the
executor and records (row ESC2c) come later. The tests were written under strict xfail and the
implementing commit removed the marks; the three guards at the end pin what v1.535 keeps, every
output made without a cascade, and passed before and after it.
"""

import dataclasses
import hashlib
import json
import re

import pytest

import model_routing
from model_routing import (
    DATA_DIR, NoModelClearsBar, Priors, Registry, Router, Stats, Task, calibrate_from_results,
    evaluate, load_outcomes, load_tasks, run_demo,
)

CHEAP, STRONG, SIGNAL = "fiction/cheap", "fiction/best", "public-test-failed"
CASCADE_ID = "fiction/cheap>fiction/best@public-test-failed"
OTHER = {"cheap": "fiction/mid", "strong": STRONG, "signal": "calls-over-15"}

# sha256 of each file run_demo writes and of its summary and the evaluate result on its
# outcomes, at v1.534 (db6d282), computed in iter 381 before any v1.535 code existed
V1_534_DEMO_SHA256 = {
    ".model-routing-demo": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "calls.jsonl": "4f111326781939140bebe04e0841a66306cac48492bc6c95f4bc2211fa92b351",
    "models.json": "00aceac37c9ca8fff3f8b00d01e819df88cc3b474dc7c12c61f3e8ddf4004124",
    "outcomes.jsonl": "5490bfdc336c30558f21dfd2e047fc5af923399ed9239f33ac10b9105c6918ec",
    "stats.json": "91f0394b0fe8b15dd9ced30216c65e01c15ea6c1cd1e76b2a85beaa19f1f4b79",
    "tasks.json": "81793ea3b26dae535cbbdd18f754c22fa870d19d76f33c659340ad06f034f806",
}
V1_534_SUMMARY_SHA256 = "7ba0f6e68b0227b1d6a51e7a6f4605b1d94abd1e2261b8583abf2ead465966ab"
V1_534_EVALUATE_SHA256 = "a450f41369bc28d532cdeb099e31abd1495889b9e02940583fa95147c950a220"
# the 16 select outputs (8 example tasks, both flavors, empty Stats, packaged priors)
V1_534_EXAMPLE_SELECT_SHA256 = "2369381cc7a44f66de6512014c0ec9c5ca6df5a65074ca9239b14d114255d4da"


def sha(value) -> str:
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def cascade(cheap=CHEAP, strong=STRONG, signal=SIGNAL):
    return model_routing.Cascade(cheap, strong, signal)


def write_tasks(tmp_path, rows):
    path = tmp_path / "tasks.json"
    path.write_text(json.dumps({"tasks": rows}), encoding="utf-8")
    return path


def write_stats(tmp_path, rows):
    path = tmp_path / "stats.json"
    path.write_text(json.dumps({"stats": rows}), encoding="utf-8")
    return path


# --- Cascade -------------------------------------------------------------------------------

def test_cascade_is_exported_frozen_and_named_by_its_id():
    from model_routing import Cascade
    c = cascade()
    assert "Cascade" in model_routing.__all__
    assert model_routing.__all__.index("Cascade") == model_routing.__all__.index("load_tasks") + 1
    assert [f.name for f in dataclasses.fields(Cascade)] == ["cheap", "strong", "signal"]
    assert (c.cheap, c.strong, c.signal) == (CHEAP, STRONG, SIGNAL)
    assert c.id == CASCADE_ID
    assert c == cascade() and hash(c) == hash(cascade())
    with pytest.raises(dataclasses.FrozenInstanceError):
        c.cheap = "fiction/mid"


@pytest.mark.parametrize("signal", ["s", "0", "public-test-failed", "calls.over_15", "a-b.c_d9"])
def test_a_signal_of_the_pattern_is_accepted(signal):
    assert cascade(signal=signal).id == f"{CHEAP}>{STRONG}@{signal}"


@pytest.mark.parametrize("args", [
    ("", STRONG, SIGNAL), (CHEAP, "", SIGNAL), (CHEAP, STRONG, ""),
    (1, STRONG, SIGNAL), (CHEAP, None, SIGNAL), (CHEAP, STRONG, 7),
    (CHEAP, CHEAP, SIGNAL),
    ("fiction>cheap", STRONG, SIGNAL), (CHEAP, "fiction@best", SIGNAL),
    ("fiction@cheap", STRONG, SIGNAL), (CHEAP, "fiction>best", SIGNAL),
    (CHEAP, STRONG, "Public"), (CHEAP, STRONG, "-x"), (CHEAP, STRONG, ".x"),
    (CHEAP, STRONG, "a b"), (CHEAP, STRONG, "a@b"), (CHEAP, STRONG, "a>b"), (CHEAP, STRONG, "s\n"),
])
def test_a_bad_cascade_is_a_value_error(args):
    with pytest.raises(ValueError):
        model_routing.Cascade(*args)


# --- Task.cascades and load_tasks ----------------------------------------------------------

def test_cascades_is_the_last_task_field_and_defaults_to_an_empty_tuple():
    assert [f.name for f in dataclasses.fields(Task)][-2:] == ["slices", "cascades"]
    assert Task("t", 0.8).cascades == ()


def test_a_positional_task_keeps_its_meaning_and_stores_a_tuple():
    c = cascade()
    task = Task("t", 0.8, 30, 0.95, True, (), 1000, 200, "refuse", 2, None, 60.0, False, {}, [c])
    assert task.cascades == (c,) and type(task.cascades) is tuple
    assert task.fallback_below_bar is False and task.slices == {}
    assert hash(task) == hash(Task("t", 0.8, cascades=(cascade(),)))
    assert task == Task("t", 0.8, cascades=(cascade(),))


@pytest.mark.parametrize("value", [
    (cascade, cascade),  # two cascades with one id (built inside the test)
    ({"cheap": CHEAP, "strong": STRONG, "signal": SIGNAL},),
    (CASCADE_ID,),
    "abc",
    None,
    5,
])
def test_a_bad_cascades_value_is_a_value_error_naming_the_task(value):
    if isinstance(value, tuple) and value and callable(value[0]):
        value = tuple(make() for make in value)
    with pytest.raises(ValueError, match="'t'"):
        Task("t", 0.8, cascades=value)


def test_load_tasks_reads_cascades_and_a_row_without_it_gets_none(tmp_path):
    path = write_tasks(tmp_path, [
        {"name": "t", "bar": 0.8, "cascades": [{"cheap": CHEAP, "strong": STRONG, "signal": SIGNAL},
                                              OTHER]},
        {"name": "u", "bar": 0.9},
    ])
    tasks = load_tasks(path)
    assert tasks["t"].cascades == (cascade(), cascade(**OTHER))
    assert [c.id for c in tasks["t"].cascades] == [CASCADE_ID, "fiction/mid>fiction/best@calls-over-15"]
    assert tasks["u"].cascades == ()


@pytest.mark.parametrize("value", [
    {"cheap": CHEAP, "strong": STRONG, "signal": SIGNAL},
    "x",
    None,
    ["x"],
    [[CHEAP, STRONG, SIGNAL]],
    [{"cheap": CHEAP, "strong": STRONG}],
    [{"cheap": CHEAP, "strong": STRONG, "signal": SIGNAL, "bar": 0.9}],
    [{"cheap": CHEAP, "strong": CHEAP, "signal": SIGNAL}],
    [{"cheap": 1, "strong": STRONG, "signal": SIGNAL}],
    [{"cheap": CHEAP, "strong": STRONG, "signal": SIGNAL}] * 2,
])
def test_load_tasks_refuses_a_bad_cascades_value_naming_the_file(tmp_path, value):
    good = tmp_path / "good"
    good.mkdir()
    assert load_tasks(write_tasks(good, [{"name": "t", "bar": 0.8, "cascades": []}]))["t"].cascades == ()
    path = write_tasks(tmp_path, [{"name": "t", "bar": 0.8, "cascades": value}])
    with pytest.raises(ValueError, match=re.escape(str(path))):
        load_tasks(path)


def test_no_packaged_task_has_a_cascade():
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    assert len(tasks) == 8
    assert all(task.cascades == () for task in tasks.values())


def test_the_demo_tasks_file_holds_cascades_only_for_a_task_that_has_one():
    from model_routing.demo import _tasks_json
    plain = json.loads(_tasks_json(Task("t", 0.8)))["tasks"][0]
    assert "cascades" not in plain and "slices" not in plain
    task = Task("t", 0.8, cascades=(cascade(), cascade(**OTHER)))
    row = json.loads(_tasks_json(task))["tasks"][0]
    assert list(row)[-1] == "cascades"
    assert row["cascades"] == [{"cheap": CHEAP, "strong": STRONG, "signal": SIGNAL}, OTHER]


# --- Stats ---------------------------------------------------------------------------------

def test_add_keeps_the_escalation_count_beside_the_counts():
    stats = Stats()
    stats.add("t", CASCADE_ID, 3, 4, escalated=2)
    stats.add("t", CASCADE_ID, 1, 2, escalated=1)
    stats.add("t", CASCADE_ID, 0, 1, escalated=0)
    stats.add("u", CASCADE_ID, 2, 2, escalated=2)
    stats.add("t", CHEAP, 5, 6, input_tokens=60, output_tokens=12)
    assert stats.get("t", CASCADE_ID) == (4, 7)
    assert stats.escalations("t", CASCADE_ID) == 3
    assert stats.escalations("u", CASCADE_ID) == 2
    assert stats.escalations("t", CHEAP) == 0
    assert stats.escalations("v", CASCADE_ID) == 0
    assert stats.tokens("t", CASCADE_ID) == (0, 0, 0)
    assert stats.tokens("t", CHEAP) == (60, 12, 6)
    assert stats.items() == [(("t", CHEAP), (5, 6)), (("t", CASCADE_ID), (4, 7)),
                             (("u", CASCADE_ID), (2, 2))]


@pytest.mark.parametrize("model_id, extra", [
    (CASCADE_ID, {}),
    (CASCADE_ID, {"escalated": None}),
    (CASCADE_ID, {"escalated": True}),
    (CASCADE_ID, {"escalated": False}),
    (CASCADE_ID, {"escalated": 1.0}),
    (CASCADE_ID, {"escalated": "1"}),
    (CASCADE_ID, {"escalated": -1}),
    (CASCADE_ID, {"escalated": 5}),
    (CASCADE_ID, {"escalated": 1, "input_tokens": 10, "output_tokens": 5}),
    (CHEAP, {"escalated": 0}),
    ("fiction/cheap>", {"escalated": 0}),
    ("fiction/cheap>fiction/best", {"escalated": 0}),
    ("fiction/cheap>fiction/best", {}),
    ("fiction/cheap>fiction/best@Signal", {"escalated": 0}),
    ("a>b>c@s", {"escalated": 0}),
    ("a>a@s", {"escalated": 0}),
])
def test_add_refuses_a_bad_escalation_and_adds_nothing(model_id, extra):
    stats = Stats()
    with pytest.raises(ValueError):
        stats.add("t", model_id, 3, 4, **extra)
    assert stats.items() == []
    assert stats.escalations("t", model_id) == 0


def test_merge_sums_the_escalations_and_leaves_both_operands():
    a, b = Stats(), Stats()
    a.add("t", CASCADE_ID, 3, 4, escalated=2)
    a.add("t", CHEAP, 1, 2, input_tokens=20, output_tokens=4)
    b.add("t", CASCADE_ID, 1, 3, escalated=3)
    b.add("u", CASCADE_ID, 0, 1, escalated=0)
    merged = a.merge(b)
    assert merged.get("t", CASCADE_ID) == (4, 7) and merged.escalations("t", CASCADE_ID) == 5
    assert merged.get("u", CASCADE_ID) == (0, 1) and merged.escalations("u", CASCADE_ID) == 0
    assert merged.tokens("t", CHEAP) == (20, 4, 2)
    assert a.escalations("t", CASCADE_ID) == 2 and b.escalations("t", CASCADE_ID) == 3


def test_save_writes_escalated_right_after_trials_on_cascade_rows_only(tmp_path):
    stats = Stats()
    stats.add("t", CASCADE_ID, 3, 4, escalated=2)
    stats.add("t", CHEAP, 1, 2, input_tokens=20, output_tokens=4)
    stats.add("t", STRONG, 2, 2)
    path = tmp_path / "stats.json"
    stats.save(path)
    rows = json.loads(path.read_text(encoding="utf-8"))["stats"]
    assert [row["model"] for row in rows] == [STRONG, CHEAP, CASCADE_ID]
    assert [list(row) for row in rows] == [
        ["task", "model", "successes", "trials"],
        ["task", "model", "successes", "trials", "input_tokens", "output_tokens", "token_trials"],
        ["task", "model", "successes", "trials", "escalated"],
    ]
    assert rows[2] == {"task": "t", "model": CASCADE_ID, "successes": 3, "trials": 4, "escalated": 2}
    loaded = Stats.load(path)
    assert loaded.items() == stats.items()
    assert loaded.escalations("t", CASCADE_ID) == 2
    again = tmp_path / "again.json"
    loaded.save(again)
    assert again.read_bytes() == path.read_bytes()


def test_a_stats_with_no_cascade_saves_v1_534_bytes(tmp_path):
    stats = Stats()
    stats.add("t", CHEAP, 1, 2, input_tokens=20, output_tokens=4)
    stats.add("t", STRONG, 2, 2)
    path = tmp_path / "stats.json"
    stats.save(path)
    assert path.read_text(encoding="utf-8") == (
        '{\n  "stats": [\n'
        '    {\n      "task": "t",\n      "model": "fiction/best",\n      "successes": 2,\n'
        '      "trials": 2\n    },\n'
        '    {\n      "task": "t",\n      "model": "fiction/cheap",\n      "successes": 1,\n'
        '      "trials": 2,\n      "input_tokens": 20,\n      "output_tokens": 4,\n'
        '      "token_trials": 2\n    }\n  ]\n}\n')
    assert Stats.load(path).items() == stats.items()


@pytest.mark.parametrize("row", [
    {"model": CASCADE_ID},
    {"model": CASCADE_ID, "escalated": None},
    {"model": CASCADE_ID, "escalated": True},
    {"model": CASCADE_ID, "escalated": 1.0},
    {"model": CASCADE_ID, "escalated": "1"},
    {"model": CASCADE_ID, "escalated": 3},
    {"model": CASCADE_ID, "escalated": -1},
    {"model": CASCADE_ID, "escalated": 1, "input_tokens": 1, "output_tokens": 1, "token_trials": 1},
    {"model": CHEAP, "escalated": 0},
    {"model": CHEAP, "escalated": None},
    {"model": CHEAP, "escalated": False},
    {"model": "fiction/cheap>fiction/best", "escalated": 0},
])
def test_stats_load_refuses_a_bad_escalation_row_naming_the_file(tmp_path, row):
    path = write_stats(tmp_path, [{"task": "t", "successes": 1, "trials": 2, **row}])
    with pytest.raises(ValueError, match=re.escape(str(path))):
        Stats.load(path)


# --- calibrate_from_results ----------------------------------------------------------------

def test_calibrate_from_results_counts_a_cascade_row_with_its_escalation():
    rows = [
        {"task": "t", "model": CASCADE_ID, "item": "a", "correct": True, "escalated": False,
         "cost_usd": 0.001},
        {"task": "t", "model": CASCADE_ID, "item": "b", "correct": True, "escalated": True,
         "cost_usd": 0.004},
        {"task": "t", "model": CASCADE_ID, "item": "c", "correct": False, "escalated": True,
         "cost_usd": 0.004},
        {"task": "t", "model": CASCADE_ID, "item": "d", "correct": True, "escalated": False,
         "cost_usd": 0.001},
        {"task": "t", "model": CASCADE_ID, "item": "e", "correct": True, "escalated": True,
         "slice": "deep", "cost_usd": 0.005},
        {"task": "t", "model": CHEAP, "item": "a", "correct": True, "input_tokens": 100,
         "output_tokens": 20},
    ]
    stats = calibrate_from_results(rows)
    assert stats.get("t", CASCADE_ID) == (4, 5) and stats.escalations("t", CASCADE_ID) == 3
    assert stats.get("t@deep", CASCADE_ID) == (1, 1)
    assert stats.escalations("t@deep", CASCADE_ID) == 1
    assert stats.tokens("t", CASCADE_ID) == (0, 0, 0)
    assert stats.get("t", CHEAP) == (1, 1) and stats.tokens("t", CHEAP) == (100, 20, 1)


GOOD = {"task": "t", "model": CASCADE_ID, "correct": True, "escalated": False}


@pytest.mark.parametrize("bad", [
    {"task": "t", "model": CHEAP, "correct": True, "escalated": False},
    {"task": "t", "model": CHEAP, "correct": True, "escalated": None},
    {"task": "t", "model": CASCADE_ID, "correct": True},
    {"task": "t", "model": CASCADE_ID, "correct": True, "escalated": None},
    {"task": "t", "model": CASCADE_ID, "correct": True, "escalated": 1},
    {"task": "t", "model": CASCADE_ID, "correct": True, "escalated": "true"},
    {"task": "t", "model": CASCADE_ID, "correct": True, "escalated": True, "input_tokens": 10,
     "output_tokens": 2},
    {"task": "t", "model": "fiction/cheap>fiction/best", "correct": True, "escalated": True},
])
def test_calibrate_from_results_refuses_a_bad_escalation(bad):
    with pytest.raises(ValueError):
        calibrate_from_results([GOOD, bad, GOOD])


# --- guards: every output made without a cascade is v1.534's -------------------------------

def test_with_no_cascade_the_demo_writes_v1_534_bytes(tmp_path):
    out = tmp_path / "demo"
    summary = run_demo(out)
    digests = {f.name: hashlib.sha256(f.read_bytes()).hexdigest() for f in sorted(out.iterdir())}
    assert digests == V1_534_DEMO_SHA256
    assert sha(summary) == V1_534_SUMMARY_SHA256
    result = evaluate(load_outcomes(out / "outcomes.jsonl"), bars=[0.8, 0.9])
    assert sha(result) == V1_534_EVALUATE_SHA256


def test_with_no_cascade_the_example_tasks_route_as_in_v1_534():
    registry = Registry.load(DATA_DIR / "models.json")
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    priors = Priors.load(DATA_DIR / "priors.json")
    out = []
    for name in tasks:
        for flavor in ("cost_effective", "cost_blind"):
            try:
                out.append(Router(registry, tasks, Stats(), priors).select(name, flavor).to_dict())
            except NoModelClearsBar as exc:
                out.append(str(exc))
    assert len(out) == 16
    assert sha(out) == V1_534_EXAMPLE_SELECT_SHA256
