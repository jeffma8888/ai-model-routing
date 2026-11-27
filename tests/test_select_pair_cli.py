"""DESIGN 10 v1.676 (row DEL1c, the third part of row DEL1): `model-routing select-pair`.

`select-pair TASK --root MODEL ... --leaf MODEL ...` prints `Router.select_pair`'s decision (5.2
v1.670) as `select` prints one, through the same code, with `--flavor`, `--generator`, `--exclude`,
`--policy`, `--registry`, `--tasks`, `--stats` and `--json`, and no priors, slice, per-call size or
window. It exits 3 with the candidate table on stderr when no pair can be chosen, and warns on an
expired price for each root and leaf of an eligible pair. The fixture is the DEL1a one of
tests/test_select_pair.py: four roots, three leaves, each pair's own counts of 40 and each model
alone at 40 of 40, at bar 0.8, so only the pairs at 39 and 40 of 40 pass. `select` keeps its bytes:
the sha256 of its outputs on this fixture was taken on a5ec3c4 (v1.675).
"""

import contextlib
import hashlib
import io
import json
from datetime import date
from pathlib import Path

import pytest

from model_routing import Policy, Registry, Router, Stats, load_tasks
from model_routing.cli import _build_parser, main
from model_routing.stats import wilson_lower_bound
from test_select_pair import LEAVES, N, PAIRS, PRICES, ROOTS

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 26)
# v1.675 (a5ec3c4): sha256 of every select output on this fixture, tasks t, r and u, both flavors,
# text and --json, with and without the label sources
SELECT_SHA256 = "e8d939504ef0cf494ed75cf135a9461bc163842533bb76000433fe51934dd7e3"
OPTIONS = {"-h", "--help", "--root", "--leaf", "--flavor", "--generator", "--exclude", "--policy",
           "--registry", "--tasks", "--stats", "--json"}
EXPIRED = ("warning: list price of {} was stated valid through 2026-01-31; check the vendor page "
           "and update the registry")


def run(argv):
    """`main(argv)` at TODAY as (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, today=TODAY)
    return code, out.getvalue(), err.getvalue()


def model_row(model_id, expired=()):
    row = {"id": model_id, "family": model_id.split("/")[1], "price_in": PRICES[model_id][0],
           "price_out": PRICES[model_id][1], "context_window": 100_000}
    if model_id in expired:
        row["price_valid_until"] = "2026-01-31"
    return row


def write_stats(path, pairs=PAIRS, sources=None, extra=None):
    """Each pair's own counts of N and each model alone at N of N, ``sources`` a key's label sources
    and ``extra`` a pair key's other `Stats.add` fields on task t."""
    stats = Stats()
    for (root, leaf), wins in pairs.items():
        key = f"{root}+{leaf}"
        stats.add("t", key, wins, N, label_sources=(sources or {}).get(key), **(extra or {}).get(key, {}))
        stats.add("r", key, wins, N)
        stats.add("u", key, wins, N)
    for model_id in ROOTS + LEAVES:
        for task in ("t", "r", "u"):
            stats.add(task, model_id, N, N, label_sources=(sources or {}).get(model_id) if task == "t" else None)
    stats.save(path)
    return str(path)


@pytest.fixture
def files(tmp_path):
    return make_files(tmp_path)


def make_files(d, expired=(), order=ROOTS + LEAVES):
    (d / "models.json").write_text(json.dumps({"models": [model_row(m, expired) for m in order]}),
                                   encoding="utf-8")
    common = {"bar": 0.8, "min_samples": 30, "expected_input_tokens": 1000, "expected_output_tokens": 200}
    (d / "tasks.json").write_text(json.dumps({"tasks": [
        dict(common, name="t"),
        dict(common, name="r", failure_policy="retry_same"),
        dict(common, name="u", fallback_below_bar=True)]}), encoding="utf-8")
    write_stats(d / "stats.json")
    return d


def base(d, stats="stats.json"):
    return ["--registry", str(d / "models.json"), "--tasks", str(d / "tasks.json"), "--stats", str(d / stats)]


def pair(d, task="t", roots=ROOTS, leaves=LEAVES, *more, stats="stats.json"):
    return run(["select-pair", task, "--root", *roots, "--leaf", *leaves, *base(d, stats), *more])


def router(d, stats="stats.json"):
    return Router(Registry.load(d / "models.json"), load_tasks(d / "tasks.json"), Stats.load(d / stats))


def wilson(wins, n, z=1.959963984540054):
    """The Wilson score interval's lower end written out, z the 0.975 normal quantile."""
    p = wins / n
    return (p + z * z / (2 * n) - z * (p * (1 - p) / n + z * z / (4 * n * n)) ** 0.5) / (1 + z * z / n)


def cost(model_id):
    """One call at the task's 1000 input and 200 output tokens, prices per million tokens."""
    price_in, price_out = PRICES[model_id]
    return (1000 * price_in + 200 * price_out) / 1_000_000


# --- the command and its options -----------------------------------------------------------------

def test_the_command_takes_exactly_its_options():
    parser = _build_parser()
    sub = next(a for a in parser._actions if hasattr(a, "choices") and isinstance(a.choices, dict))
    assert "select-pair" in sub.choices
    options = {flag for action in sub.choices["select-pair"]._actions for flag in action.option_strings}
    assert options == OPTIONS
    required = {action.dest for action in sub.choices["select-pair"]._actions if action.required}
    assert required == {"task", "root", "leaf"}


@pytest.mark.parametrize("flag, value", [("--priors", "p.json"), ("--slice", "s"), ("--prompt-tokens", "10"),
                                         ("--window", "30d")])
def test_select_s_other_options_are_unrecognized(files, flag, value):
    code, out, err = pair(files, "t", ROOTS, LEAVES, flag, value)
    assert (code, out) == (2, "")
    assert err.startswith("usage: model-routing [-h]\n")   # argparse's top-level usage, as for any command
    assert err.endswith(f"error: unrecognized arguments: {flag} {value}\n")


# --- the text output -----------------------------------------------------------------------------

TABLE = """\
model             family  measured  quality_lb  list_cost  routing_cost  reason
----------------  ------  --------  ----------  ---------  ------------  ---------
r/strong+l/cheap  strong  39/40     0.871       0.016160   0.016160      passes
r/strong+l/mid    strong  40/40     0.912       0.017600   0.017600      passes
r/strong+l/dear   strong  40/40     0.912       0.032000   0.032000      passes
r/good+l/cheap    good    30/40     0.598       0.004960   0.004960      below_bar
r/good+l/mid      good    34/40     0.709       0.006400   0.006400      below_bar
r/good+l/dear     good    39/40     0.871       0.020800   0.020800      passes
r/fair+l/cheap    fair    28/40     0.546       0.001760   0.001760      below_bar
r/fair+l/mid      fair    30/40     0.598       0.003200   0.003200      below_bar
r/fair+l/dear     fair    33/40     0.681       0.017600   0.017600      below_bar
r/weak+l/cheap    weak    20/40     0.352       0.000480   0.000480      below_bar
r/weak+l/mid      weak    22/40     0.398       0.001920   0.001920      below_bar
r/weak+l/dear     weak    25/40     0.470       0.016320   0.016320      below_bar"""

HEAD = """\
task:      t
flavor:    cost_effective
primary:   r/strong+l/cheap
fallbacks: r/strong+l/mid, r/good+l/dear
basis:     measured
below_bar: false
"""


def test_cost_effective_prints_the_decision_and_one_row_per_pair_roots_major(files):
    code, out, err = pair(files)
    assert (code, err) == (0, "")
    assert out == HEAD + "\n" + TABLE + "\n"


def test_each_row_is_the_hand_computed_pair():
    """Each row's counts are the fixture's, its bound the Wilson bound at 0.95 written out here to 3
    places, and its cost the root's call plus the leaf's at 1000 input and 200 output tokens, to 6
    places."""
    rows = [line.split() for line in TABLE.split("\n")[2:]]
    assert [row[0] for row in rows] == [f"{r}+{l}" for r in ROOTS for l in LEAVES]
    for model_id, family, measured, bound, list_cost, routing_cost, reason in rows:
        root, leaf = model_id.split("+")
        wins = PAIRS[(root, leaf)]
        assert family == root.split("/")[1] and measured == f"{wins}/{N}"
        assert bound == f"{wilson(wins, N):.3f}"
        assert wilson(wins, N) == pytest.approx(wilson_lower_bound(wins, N, 0.95), rel=1e-12)
        assert list_cost == routing_cost == f"{cost(root) + cost(leaf):.6f}"
        assert reason == ("passes" if wins >= 39 else "below_bar")
    # by hand: r/strong 0.016 + l/cheap 0.00016; r/good 0.0048 + l/dear 0.016; r/weak 0.00032 + l/cheap 0.00016
    assert (cost("r/strong") + cost("l/cheap"), cost("r/good") + cost("l/dear"),
            cost("r/weak") + cost("l/cheap")) == pytest.approx((0.01616, 0.0208, 0.00048), rel=1e-12)


def test_cost_blind_takes_the_best_bound_with_every_routing_cost_zero(files):
    code, out, err = pair(files, "t", ROOTS, LEAVES, "--flavor", "cost_blind")
    assert (code, err) == (0, "")
    assert out.split("\n")[:7] == ["task:      t", "flavor:    cost_blind", "primary:   r/strong+l/dear",
                                   "fallbacks: r/strong+l/mid, r/good+l/dear", "basis:     measured",
                                   "below_bar: false", ""]
    rows = [line.split() for line in out.split("\n")[9:-1]]
    assert len(rows) == 12 and all(row[5] == "0.000000" for row in rows)
    assert [row[:5] + row[6:] for row in rows] == [row[:5] + row[6:] for row in
                                                   (line.split() for line in TABLE.split("\n")[2:])]


@pytest.mark.parametrize("flavor", ["cost_effective", "cost_blind"])
def test_json_is_the_library_decision(files, flavor):
    code, out, err = pair(files, "t", ROOTS, LEAVES, "--flavor", flavor, "--json")
    assert (code, err) == (0, "")
    want = router(files).select_pair("t", ROOTS, LEAVES, flavor).to_dict()
    assert out == json.dumps(want, indent=2) + "\n"
    assert json.loads(out)["primary"] == {"cost_effective": "r/strong+l/cheap", "cost_blind": "r/strong+l/dear"}[flavor]


def test_root_and_leaf_may_each_be_given_more_than_once(files):
    once = pair(files)
    twice = run(["select-pair", "t", "--root", "r/strong", "r/good", "--leaf", "l/cheap", "--root", "r/fair",
                 "r/weak", "--leaf", "l/mid", "l/dear", *base(files)])
    assert twice == once
    order = pair(files, "t", ["r/weak", "r/strong"], ["l/dear", "l/cheap"], "--json")
    assert [c["model_id"] for c in json.loads(order[1])["candidates"]] == [
        "r/weak+l/dear", "r/weak+l/cheap", "r/strong+l/dear", "r/strong+l/cheap"]


def test_exclude_generator_and_policy_reach_select_pair(files):
    r = router(files)
    code, out, err = pair(files, "t", ROOTS, LEAVES, "--exclude", "l/cheap", "--json")
    assert (code, err) == (0, "")
    assert json.loads(out) == r.select_pair("t", ROOTS, LEAVES, exclude_models=["l/cheap"]).to_dict()
    assert json.loads(out)["primary"] == "r/strong+l/mid"
    code, out, err = pair(files, "t", ROOTS, LEAVES, "--generator", "l/mid", "--json")
    assert (code, err) == (0, "")
    assert json.loads(out) == r.select_pair("t", ROOTS, LEAVES, generator_model="l/mid").to_dict()
    assert all(c["reason"] == "generator" for c in json.loads(out)["candidates"] if c["model_id"].endswith("+l/mid"))
    allowed = {"allowed_routes": ["r/good", "l/cheap", "l/mid", "l/dear"]}
    (files / "policy.json").write_text(json.dumps(allowed), encoding="utf-8")
    code, out, err = pair(files, "t", ROOTS, LEAVES, "--policy", str(files / "policy.json"))
    assert (code, err) == (0, "")
    assert out.split("\n")[2:4] == ["primary:   r/good+l/dear", "fallbacks: (none)"]
    code, data, err = pair(files, "t", ROOTS, LEAVES, "--policy", str(files / "policy.json"), "--json")
    assert json.loads(data) == r.select_pair("t", ROOTS, LEAVES, policy=Policy(**allowed)).to_dict()


def test_a_below_bar_fallback_is_marked(files):
    code, out, err = pair(files, "u", ["r/good"], ["l/dear", "l/mid"])
    assert (code, err) == (0, "")
    assert out.split("\n")[2:6] == ["primary:   r/good+l/dear", "fallbacks: r/good+l/mid (below bar)",
                                    "basis:     measured", "below_bar: false"]


def test_a_retry_same_task_prints_its_policy_line(files):
    """By hand: r/strong+l/cheap costs 0.01616 at a bound of 0.871187 for 39 of 40, so 0.018549 a
    success; r/strong+l/mid 0.0176 at 0.912378 for 40 of 40 is 0.019290, so no `pick:` line."""
    code, out, err = pair(files, "r")
    assert (code, err) == (0, "")
    assert out.split("\n")[2:9] == [
        "primary:   r/strong+l/cheap", "fallbacks: r/strong+l/mid, r/good+l/dear", "basis:     measured",
        "below_bar: false",
        "policy:    retry_same, expected cost per success $0.018549 (an estimate assuming independent retries)",
        "", TABLE.split("\n")[0]]
    assert 0.01616 / wilson(39, N) == pytest.approx(0.018549, abs=5e-7)


def test_a_retry_same_task_prints_pick_when_the_cheapest_per_success_pair_is_not_the_cheapest(files):
    """By hand: r/strong+l/cheap costs 0.01616 at 0.871187 (39 of 40), 0.018549 a success, and
    r/weak+l/dear 0.01632 at 0.912378 (40 of 40), 0.017887, so the dearer call is the primary."""
    write_stats(files / "two.json", pairs={("r/strong", "l/cheap"): 39, ("r/weak", "l/dear"): 40})
    code, out, err = pair(files, "r", ["r/strong", "r/weak"], ["l/cheap", "l/dear"], stats="two.json")
    assert (code, err) == (0, "")
    assert out.split("\n")[:9] == [
        "task:      r", "flavor:    cost_effective", "primary:   r/weak+l/dear", "fallbacks: r/strong+l/cheap",
        "basis:     measured", "below_bar: false",
        "policy:    retry_same, expected cost per success $0.017887 (an estimate assuming independent retries)",
        "pick:      cheaper_per_success", ""]
    assert (0.01632 / wilson(40, N), 0.01616 / wilson(39, N)) == pytest.approx((0.017887, 0.018549), abs=5e-7)


def test_the_labels_line_reads_the_primary_pair_s_key_alone(files):
    write_stats(files / "tagged.json", sources={"r/strong+l/cheap": {"consensus": 30, "human": 9},
                                                "r/strong+l/mid": {"human": 40}, "l/cheap": {"human": 40}})
    code, out, err = pair(files, stats="tagged.json")
    assert (code, err) == (0, "")
    assert out == HEAD + "labels:    consensus 30, human 9 of 40 trials\n\n" + TABLE + "\n"
    code, data, err = pair(files, "t", ROOTS, LEAVES, "--json", stats="tagged.json")
    keys = list(json.loads(data))
    assert keys[-2:] == ["label_sources", "candidates"]
    assert json.loads(data)["label_sources"] == {"consensus": 30, "human": 9}


# --- exit 3 and exit 2 ---------------------------------------------------------------------------

def test_no_pair_measured_exits_3_with_the_table_on_stderr(files):
    write_stats(files / "solo.json", pairs={})
    code, out, err = pair(files, stats="solo.json")
    assert (code, out) == (3, "")
    lines = err.split("\n")
    assert lines[0] == "error: no model clears the bar 0.8 for task 't'"
    assert lines[1].split() == ["model", "family", "measured", "quality_lb", "list_cost", "routing_cost", "reason"]
    assert [line.split()[0] for line in lines[3:-1]] == [f"{r}+{l}" for r in ROOTS for l in LEAVES]
    assert all(line.split()[-1] == "insufficient_samples" for line in lines[3:-1])
    assert lines[-1] == ""


@pytest.mark.parametrize("argv, line", [
    (["select-pair", "t", "--leaf", "l/cheap"], "error: the following arguments are required: --root"),
    (["select-pair", "t", "--root", "r/strong"], "error: the following arguments are required: --leaf"),
    (["select-pair", "t", "--root", "--leaf", "l/cheap"], "error: argument --root: expected at least one argument"),
], ids=["no root", "no leaf", "an empty root"])
def test_a_usage_error_prints_the_usage_line_and_exits_2(files, argv, line):
    code, out, err = run(argv + base(files))
    assert (code, out) == (2, "")
    assert err.startswith("usage: model-routing select-pair") and err.endswith(line + "\n")


@pytest.mark.parametrize("more, line", [
    (["--exclude", "x/none"], "error: unknown model: 'x/none'"),
    (["--generator", "x/none"], "error: unknown model: 'x/none'"),
    (["--flavor", "cheapest"], "error: unknown flavor 'cheapest'; expected one of ('cost_effective', 'cost_blind')"),
], ids=["an unknown exclude", "an unknown generator", "an unknown flavor"])
def test_a_bad_option_exits_2_with_one_line(files, more, line):
    code, out, err = pair(files, "t", ROOTS, LEAVES, *more)
    assert (code, out, err) == (2, "", line + "\n")


@pytest.mark.parametrize("task, roots, leaves, line", [
    ("nope", ROOTS, LEAVES, "error: unknown task: 'nope'"),
    ("t", ["x/none"], LEAVES, "error: unknown model: 'x/none'"),
    ("t", ROOTS, ["l/cheap", "x/none"], "error: unknown model: 'x/none'"),
    ("t", ["r/good", "r/good"], LEAVES, "error: roots names a model twice: ['r/good', 'r/good']"),
    ("t", ROOTS, ["l/mid", "l/mid"], "error: leaves names a model twice: ['l/mid', 'l/mid']"),
], ids=["an unknown task", "an unknown root", "an unknown leaf", "a root twice", "a leaf twice"])
def test_select_pair_s_own_checks_exit_2_with_its_message(files, task, roots, leaves, line):
    code, out, err = pair(files, task, roots, leaves)
    assert (code, out, err) == (2, "", line + "\n")


def test_the_registry_then_the_tasks_then_the_ids_come_first(files):
    """A missing registry before a missing tasks file, both before an unknown ID or task; and an
    unknown --exclude ID before an unknown task, which select_pair checks (review iter-534 should-fix 3)."""
    gone = str(files / "gone.json")
    code, out, err = run(["select-pair", "nope", "--root", "x/none", "--leaf", "l/cheap", "--exclude", "x/none",
                          "--registry", gone, "--tasks", gone, "--stats", str(files / "stats.json")])
    assert (code, out, err) == (2, "", f"error: [Errno 2] No such file or directory: {gone!r}\n")
    code, out, err = run(["select-pair", "nope", "--root", "x/none", "--leaf", "l/cheap", "--exclude", "x/none",
                          "--registry", str(files / "models.json"), "--tasks", gone])
    assert (code, out, err) == (2, "", f"error: [Errno 2] No such file or directory: {gone!r}\n")
    code, out, err = pair(files, "nope", ["x/none"], LEAVES, "--exclude", "x/other")
    assert (code, out, err) == (2, "", "error: unknown model: 'x/other'\n")
    code, out, err = pair(files, "nope", ["x/none"], LEAVES)
    assert (code, out, err) == (2, "", "error: unknown task: 'nope'\n")


def test_a_missing_stats_file_is_empty_stats(files):
    code, out, err = pair(files, stats="none.json")
    assert (code, out) == (3, "")
    assert err.startswith("error: no model clears the bar 0.8 for task 't'\n")
    assert err.count("insufficient_samples") == 12


def test_the_id_checks_come_before_the_policy_file(files):
    code, out, err = pair(files, "t", ROOTS, LEAVES, "--exclude", "x/none", "--policy", str(files / "missing.json"))
    assert (code, out, err) == (2, "", "error: unknown model: 'x/none'\n")
    (files / "bad.json").write_text("[]", encoding="utf-8")
    code, out, err = pair(files, "t", ROOTS, LEAVES, "--policy", str(files / "bad.json"))
    assert (code, out) == (2, "")
    assert err == f"error: {files / 'bad.json'}: expected a JSON object of policy keys, got array\n"


def test_a_registry_id_equal_to_a_pair_s_is_refused(files):
    rows = [model_row(m) for m in ROOTS + LEAVES] + [
        {"id": "r/good+l/mid", "family": "odd", "price_in": 1.0, "price_out": 1.0, "context_window": 100_000}]
    (files / "models.json").write_text(json.dumps({"models": rows}), encoding="utf-8")
    code, out, err = pair(files)
    assert (code, out) == (2, "")
    assert err == "error: registry model 'r/good+l/mid' has the id of a pair\n"


# --- price warnings ------------------------------------------------------------------------------

def test_an_expired_side_of_an_eligible_pair_warns_in_registry_order(tmp_path):
    d = make_files(tmp_path, expired=("r/weak", "l/cheap"))
    code, out, err = pair(d)
    assert code == 0 and out == HEAD + "\n" + TABLE + "\n"
    assert err == EXPIRED.format("r/weak") + "\n" + EXPIRED.format("l/cheap") + "\n"
    (tmp_path / "leaves-first").mkdir()
    leaves_first = make_files(tmp_path / "leaves-first", expired=("r/weak", "l/cheap"), order=LEAVES + ROOTS)
    code, out, err = pair(leaves_first)   # registry file order, not roots then leaves (review iter-534 nit 2)
    assert code == 0 and out == HEAD + "\n" + TABLE + "\n"
    assert err == EXPIRED.format("l/cheap") + "\n" + EXPIRED.format("r/weak") + "\n"


SLOW = {f"r/weak+{leaf}": {"latencies_ms": [2000.0] * N} for leaf in LEAVES}
FAST = {f"{root}+{leaf}": {"latencies_ms": [100.0] * N} for root in ROOTS[:3] for leaf in LEAVES}
SHAKY = {f"r/weak+{leaf}": {"rerun_items": N, "consistent_items": 20} for leaf in LEAVES}
ALIKE = {f"{root}+{leaf}": {"rerun_items": N, "consistent_items": N} for root in ROOTS[:3] for leaf in LEAVES}


@pytest.mark.parametrize("field, extra, reason", [
    ({"max_p95_ms": 1000.0}, {**SLOW, **FAST}, "too_slow"),
    ({"min_self_consistency": 0.9}, {**SHAKY, **ALIKE}, "inconsistent"),
], ids=["a time bar", "a self-consistency bar"])
def test_a_side_whose_pairs_a_bar_on_the_pair_key_rules_out_does_not_warn(tmp_path, field, extra, reason):
    """Rules 5e to 5h read the pair's own key, so each r/weak pair is ruled out there while r/weak
    alone is 40 of 40 and fast or alike on its own key (review iter-534 should-fix 2)."""
    d = make_files(tmp_path, expired=("r/weak", "l/cheap"))
    common = {"bar": 0.8, "min_samples": 30, "expected_input_tokens": 1000, "expected_output_tokens": 200}
    (d / "bar.json").write_text(json.dumps({"tasks": [dict(common, name="t", **field)]}), encoding="utf-8")
    write_stats(d / "bar-stats.json", extra=extra)
    code, out, err = run(["select-pair", "t", "--root", *ROOTS, "--leaf", *LEAVES, "--registry", str(d / "models.json"),
                          "--tasks", str(d / "bar.json"), "--stats", str(d / "bar-stats.json")])
    assert code == 0 and out.split("\n")[2] == "primary:   r/strong+l/cheap"
    rows = {line.split()[0]: line.split()[-1] for line in out.split("\n")[9:-1]}
    assert [rows[f"r/weak+{leaf}"] for leaf in LEAVES] == [reason] * 3
    assert err == EXPIRED.format("l/cheap") + "\n"


def test_a_side_a_policy_rules_out_does_not_warn(tmp_path):
    d = make_files(tmp_path, expired=("r/weak", "l/cheap"))
    (d / "policy.json").write_text(json.dumps({"allowed_routes": ROOTS[:3] + LEAVES}), encoding="utf-8")
    code, out, err = pair(d, "t", ROOTS, LEAVES, "--policy", str(d / "policy.json"))
    assert code == 0 and out.split("\n")[2] == "primary:   r/strong+l/cheap"
    assert err == EXPIRED.format("l/cheap") + "\n"


def test_a_side_whose_id_holds_a_plus_warns_by_its_own_id(tmp_path):
    """The sides come from the pair order, not from splitting the pair ID at `+` (review iter-534 nit 3)."""
    rows = [{"id": "v/a+b", "family": "a", "price_in": 1.0, "price_out": 3.0, "context_window": 100_000,
             "price_valid_until": "2026-01-31"},
            {"id": "v/c", "family": "c", "price_in": 0.1, "price_out": 0.3, "context_window": 100_000}]
    (tmp_path / "models.json").write_text(json.dumps({"models": rows}), encoding="utf-8")
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [{"name": "t", "bar": 0.8, "min_samples": 30}]}),
                                         encoding="utf-8")
    stats = Stats()
    stats.add("t", "v/a+b+v/c", N, N)
    stats.save(tmp_path / "stats.json")
    code, out, err = run(["select-pair", "t", "--root", "v/a+b", "--leaf", "v/c", *base(tmp_path)])
    assert code == 0 and out.split("\n")[2] == "primary:   v/a+b+v/c"
    assert err == EXPIRED.format("v/a+b") + "\n"


def test_a_side_all_of_whose_pairs_are_ruled_out_does_not_warn(tmp_path):
    d = make_files(tmp_path, expired=("r/weak", "l/cheap"))
    code, out, err = pair(d, "t", ROOTS, LEAVES, "--exclude", "l/cheap")
    assert code == 0 and out.split("\n")[2] == "primary:   r/strong+l/mid"
    assert err == EXPIRED.format("r/weak") + "\n"   # r/weak+l/mid and r/weak+l/dear are eligible
    code, out, err = pair(d, "t", ROOTS, LEAVES, "--generator", "r/weak", "--exclude", "l/cheap")
    assert (code, err) == (0, "")


def test_exit_3_warns_after_the_table(tmp_path):
    d = make_files(tmp_path, expired=("l/dear",))
    write_stats(d / "solo.json", pairs={})
    code, out, err = pair(d, stats="solo.json")
    assert (code, out) == (3, "")
    assert err.endswith("insufficient_samples\n" + EXPIRED.format("l/dear") + "\n")


# --- unchanged: select keeps its bytes -----------------------------------------------------------

def test_select_keeps_every_byte_of_v1_675_on_this_fixture(files):
    write_stats(files / "tagged.json", sources={"l/cheap": {"consensus": 30, "human": 10}})
    digest = hashlib.sha256()
    for stats in ("stats.json", "tagged.json"):
        for task in ("t", "r", "u"):
            for flavor in ("cost_effective", "cost_blind"):
                for json_flag in ([], ["--json"]):
                    code, out, err = run(["select", task, "--flavor", flavor, *base(files, stats),
                                          "--priors", str(files / "none.json"), *json_flag])
                    digest.update(f"{code}\n{out}\n{err}\n".encode("utf-8"))
    assert digest.hexdigest() == SELECT_SHA256


# --- the docs ------------------------------------------------------------------------------------

def test_readme_layout_names_the_command_and_no_transcript_runs_it():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ("  cli.py        model-routing select | calibrate | report | demo | evaluate | delegate | plan | promote "
            "| pairs | drift | consensus-labels | select-pair\n") in readme
    assert "$ model-routing select-pair" not in readme


def test_design_and_changelog_state_v1_676():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert design.count("- v1.676 `select-pair TASK --root MODEL [MODEL ...] --leaf MODEL [MODEL ...] ") == 1
    assert design.count("a `select-pair` command (row DEL1c, which v1.676 adds in 10);") == 2
    assert "3 `NoModelClearsBar` on `select`, `select-pair` (v1.676) and `delegate`" in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    # v1.677 (row DEL1d) follows it, so the line is found by its opening, not read as the last
    assert changelog.count("\n- v1.676 (2026-11-26): spec, code and tests (10, row DEL1c, the third part of row DEL1). ") == 1


def test_the_note_s_orchestrator_line_states_the_command_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    lesson = text.split("### The orchestrator gets the strong model; the readers can be cheap\n", 1)[1]
    line = next(l for l in lesson.split("\n") if l.startswith("- In this library:"))
    assert "from v1.676 `model-routing select-pair` prints the pair's decision from the command line" in line
    assert "a `select-pair` command and a table" not in line
    # v1.677 (row DEL1d): the table ships, so the line goes on past the command
    assert "from the command line; and from v1.677 `evaluate(..., pairs=(roots, leaves))`" in line
