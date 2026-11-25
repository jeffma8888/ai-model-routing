"""DESIGN 8.3 and 10 v1.640 (row PIN1b): `report` puts pinned spend apart from routed spend.

`report(records, by="basis")` groups each record under its `basis` as a string (`measured`,
`prior`, `pinned`), a record without the key under `"None"`; `by="pinned_by"` groups it under its
pin tag as a string, a record without the key or with `null` under `"(none)"`. `report --by` takes
both. With any other `by`, a log with no pin keeps every v1.639 byte.
"""

import contextlib
import hashlib
import io
import itertools
import json
from pathlib import Path

import pytest

from model_routing import Completion, Executor, FakeProvider, Model, Monitor, Registry, Router, Stats, Task, report
from model_routing.cli import main
from model_routing.demo import run_demo

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "judge"}]
KEYS = "use model, task, flavor, family, pricing_basis, basis, pinned_by or tag:<key>"


def rec(call_id, attempt, final, outcome, model, cost, basis="measured", **extra):
    out = {"call_id": call_id, "task": "t", "flavor": "cost_effective", "model": model, "family": "x",
           "attempt": attempt, "final": final, "outcome": outcome, "latency_ms": 10.0,
           "input_tokens": 100, "output_tokens": 20, "cost_usd": cost, "routing_cost_usd": cost,
           "below_bar": False}
    if basis is not None:
        out["basis"] = basis
    out.update(extra)
    return out


# Calls, by hand: r1 measured, an error on x/cheap then a fallback answer on x/mid (0.01 + 0.10);
# r2 measured (0.02); n1 measured with a null pinned_by (0.03); p1 prior (0.05); k1 and k2 pinned by
# ticket-42 (0.30, and 0.20 under the bar); k3 pinned by contract-7, an error (0.04); old, a record
# without `basis` (0.01); and a refused budget record, which report drops.
LOG = [
    rec("r1", 0, False, "error", "x/cheap", 0.01),
    rec("r1", 1, True, "ok", "x/mid", 0.10),
    rec("r2", 0, True, "ok", "x/cheap", 0.02),
    rec("n1", 0, True, "ok", "x/cheap", 0.03, pinned_by=None),
    rec("p1", 0, True, "ok", "x/new", 0.05, basis="prior"),
    rec("k1", 0, True, "ok", "x/mid", 0.30, basis="pinned", pinned_by="ticket-42"),
    rec("k2", 0, True, "ok", "x/low", 0.20, basis="pinned", pinned_by="ticket-42", below_bar=True),
    rec("k3", 0, True, "error", "y/other", 0.04, basis="pinned", pinned_by="contract-7"),
    rec("old", 0, True, "ok", "x/cheap", 0.01, basis=None),
    {"call_id": "k4", "task": "t", "tags": {}, "budget_event": "refused", "model": "x/mid",
     "cost_usd": 9.0},
]

FIELDS = ("group", "calls", "attempts", "ok", "errors", "failed_calls", "fallback_calls",
          "below_bar_calls", "cost_usd")


def rows(by, records=LOG):
    return [tuple(r[k] for k in FIELDS) for r in report(records, by=by)]


# --- report ------------------------------------------------------------------------------------

def test_by_basis_puts_the_pinned_calls_in_a_row_apart_from_the_routed_ones():
    assert rows("basis") == [
        ("pinned", 3, 3, 2, 1, 1, 0, 1, 0.54),
        ("measured", 3, 4, 3, 1, 0, 1, 0, 0.16),
        ("prior", 1, 1, 1, 0, 0, 0, 0, 0.05),
        ("None", 1, 1, 1, 0, 0, 0, 0, 0.01),
    ]


def test_by_pinned_by_gives_one_row_per_tag_and_the_rest_under_none():
    assert rows("pinned_by") == [
        ("ticket-42", 2, 2, 2, 0, 0, 0, 1, 0.5),
        ("(none)", 5, 6, 5, 1, 0, 1, 0, 0.22),
        ("contract-7", 1, 1, 0, 1, 1, 0, 0, 0.04),
    ]


def test_a_hand_written_pinned_by_that_is_not_a_string_is_read_as_its_str_and_a_none_tag_shares_none():
    log = [rec("a", 0, True, "ok", "x/mid", 0.5, basis="pinned", pinned_by=7),
           rec("b", 0, True, "ok", "x/mid", 0.25, basis="pinned", pinned_by="(none)"),
           rec("c", 0, True, "ok", "x/cheap", 0.125)]
    assert [(g, c, cost) for g, c, *_, cost in rows("pinned_by", log)] == [("7", 1, 0.5), ("(none)", 2, 0.375)]


def test_the_two_keys_read_audits_cache_and_shadow_as_any_by_does():
    audits = {"k1": True, "k2": False, "k3": True}
    [pinned] = [r for r in report(LOG, by="basis", audits=audits) if r["group"] == "pinned"]
    # k3's final attempt is an error, so it is no success; k2's audit says wrong
    assert (pinned["audited_calls"], pinned["correct_calls"], pinned["cost_per_success_usd"]) == (3, 1, 0.54)


def test_cache_counts_and_shadow_spend_sit_in_the_rows_of_the_two_keys():
    # review iter-494 should-fix 1: a pinned record with a cached count, and a routed call with its
    # shadow, whose record carries the routed basis and no pinned_by (7 v1.607, v1.639)
    log = [rec("k1", 0, True, "ok", "x/mid", 0.30, basis="pinned", pinned_by="ticket-42", cached_input_tokens=80),
           rec("r1", 0, True, "ok", "x/cheap", 0.02, cached_input_tokens=50, pair_id="r1", shadow=False),
           rec("s1", 0, True, "ok", "x/mid", 0.08, pair_id="r1", shadow=True)]
    keys = ("group", "calls", "cost_usd", "cached_input_tokens", "cache_counted_input_tokens",
            "cache_hit_rate", "shadow_calls", "shadow_cost_usd")
    for by, groups in (("pinned_by", ("ticket-42", "(none)")), ("basis", ("pinned", "measured"))):
        got = [tuple(r[k] for k in keys) for r in report(log, by=by, cache=True, shadow=True)]
        assert got == [(groups[0], 1, 0.3, 80, 100, 0.8, 0, 0.0), (groups[1], 1, 0.02, 50, 100, 0.5, 1, 0.08)]


def test_an_unknown_key_names_basis_and_pinned_by_right_after_pricing_basis():
    with pytest.raises(ValueError) as caught:
        report([], by="reason")
    assert str(caught.value) == f"unknown report key 'reason'; {KEYS}"


# --- on an executor's log ----------------------------------------------------------------------

def model(model_id, family, price):
    return Model(model_id, family, price, 2 * price, 100_000)


MODELS = [model("x/cheap", "x", 0.1), model("y/other", "y", 0.5), model("x/mid", "x", 1.0)]


def executor(monitor):
    stats = Stats()
    for model_id in ("x/cheap", "y/other", "x/mid"):
        stats.add("t", model_id, 99, 100)
    task = Task(name="t", bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200)
    route = Router(Registry(MODELS), {"t": task}, stats)
    provider = FakeProvider({m.id: (lambda messages: Completion("ok", 1000, 200)) for m in MODELS})
    ticks, ids = itertools.count(), itertools.count()
    return Executor(route, provider, monitor=monitor, clock=lambda: float(next(ticks)),
                    now=lambda: "2026-11-25T00:00:00Z", id_factory=lambda: f"call-{next(ids)}")


def pinned_log(monitor):
    run = executor(monitor)
    for _ in range(3):
        run.call("t", MESSAGES)                                      # routed: x/cheap, measured
    for _ in range(2):
        run.call("t", MESSAGES, pin_route="x/mid", pinned_by="ticket-42")
    run.call("t", MESSAGES, pin_route="y/other", pinned_by="contract-7")
    return monitor.records


def test_an_executor_log_splits_three_routed_and_three_pinned_calls_by_hand_count():
    records = pinned_log(Monitor())
    # per call 1,000 input and 200 output tokens: x/cheap 0.00014, x/mid 0.0014, y/other 0.0007
    assert [(r["group"], r["calls"], r["attempts"], r["cost_usd"]) for r in report(records, by="basis")] == [
        ("pinned", 3, 3, 0.0035), ("measured", 3, 3, 0.00042)]
    assert [(r["group"], r["calls"], r["cost_usd"]) for r in report(records, by="pinned_by")] == [
        ("ticket-42", 2, 0.0028), ("contract-7", 1, 0.0007), ("(none)", 3, 0.00042)]


def logged(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def test_report_by_basis_and_pinned_by_on_the_command_line(tmp_path):
    log = tmp_path / "calls.jsonl"
    pinned_log(Monitor(log))
    for by, groups in (("basis", ["pinned", "measured"]),
                       ("pinned_by", ["ticket-42", "contract-7", "(none)"])):
        code, out, err = cli("report", "--log", str(log), "--by", by)
        lines = out.splitlines()
        assert (code, err) == (0, "")
        assert lines[0].split()[:3] == [by, "calls", "attempts"] and set(lines[1]) <= {"-", " "}
        assert [line.split()[0] for line in lines[2:]] == groups
        code, out, err = cli("report", "--log", str(log), "--by", by, "--json")
        assert (code, err) == (0, "") and json.loads(out) == report(logged(log), by=by)


def test_an_unknown_key_on_the_command_line_exits_2_naming_the_keys(tmp_path):
    log = tmp_path / "calls.jsonl"
    pinned_log(Monitor(log))
    assert cli("report", "--log", str(log), "--by", "reason") == (2, "", f"error: unknown report key 'reason'; {KEYS}\n")


# --- a log with no pin -------------------------------------------------------------------------

# sha256 of `model-routing report --log <demo>/calls.jsonl --by KEY [--json]`, taken at 4460d73
# (v1.639) before this slice; a slice that changes the demo's log restates them with its reason.
V1_639 = {
    ("model", False): "910a55cf1979d4207fcfc9d9a772e1fa7fea9ec21e2bbf10a0a5e5971389a53f",
    ("model", True): "1e6634fba72443c81fe5d68dd580dc12fa2a6b928f4700b91d5684203accc5b5",
    ("task", False): "838fc5d083167c8b883a43c991d33b0421682b1153629d1aa42fab941cb49d73",
    ("task", True): "dca57a0ed883a6ae5d53646254cb423eae7b5028103554c98dd3c12eaef1c469",
    ("flavor", False): "a5b5050bee35fd248c5cf2aa8b10755bef2a49e97af96932faf6eae0ba175f66",
    ("flavor", True): "972ad7125c416e905afe0c9bb1ffc9eb9bf55214b74ea3ca60e59209e1be7902",
    ("family", False): "347fdc6c981c9f1739050e879c728fb519ae611c65f67c9919ff3438dbbc486e",
    ("family", True): "0460cc6cab73344fe57a00c22f9b9605e4e2de43a0f2dad6f91fb5256e518fd0",
    ("pricing_basis", False): "21b16ca5e317f7841166523b281eb47f5f1ca348ce7bf4b9fde546dd7c4a1d2c",
    ("pricing_basis", True): "d119e1ecdffe4bdf7c5930cff47ffbf1bb2c42f2dd449b27eab3528b146739ca",
    ("tag:delegated", False): "4e8bd99361dc0a070b8be90c70a147965a5fcf4f8a0fd2c26e61acae81beec15",
    ("tag:delegated", True): "b61bf7188c6e6891942010875ff3f2dc61be88afc2d956721ea4534a19ebb6b8",
}


@pytest.fixture(scope="module")
def demo_log(tmp_path_factory):
    out = tmp_path_factory.mktemp("pinned-report") / "demo"
    run_demo(out)
    return out / "calls.jsonl"


def test_the_demo_log_keeps_every_v1_639_report_byte_by_every_other_key(demo_log):
    for (by, as_json), digest in V1_639.items():
        code, out, err = cli("report", "--log", str(demo_log), "--by", by, *(["--json"] if as_json else []))
        assert (code, err, hashlib.sha256(out.encode()).hexdigest()) == (0, "", digest), (by, as_json)


def test_the_demo_log_by_basis_is_its_routed_calls_alone(demo_log):
    records = logged(demo_log)
    by_flavor = report(records, by="flavor")
    [row] = report(records, by="basis")
    assert row["group"] == "measured"
    assert row["calls"] == sum(r["calls"] for r in by_flavor) and row["attempts"] == len(records)
    total = 0.0
    for r in records:   # in log order with +=, as report adds (review iter-494 nit 2)
        total += float(r["cost_usd"])
    assert row["cost_usd"] == round(total, 6)
    [none] = report(records, by="pinned_by")
    assert (none["group"], none["calls"]) == ("(none)", row["calls"])


# --- the docs ----------------------------------------------------------------------------------

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_design_states_v1_640_in_8_3_and_10_and_5_2_points_to_it():
    design = read("DESIGN.md")
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    assert eight3.count("\n- v1.640 `by=\"basis\"` and `by=\"pinned_by\"` (row PIN1b, 8.1 v1.639, 7 v1.639): ") == 1
    assert eight3.count("names `basis` and then `pinned_by` right after `pricing_basis`") == 1
    # review iter-494 should-fix 2: the keys that keep their bytes are the ones v1.639 took
    assert eight3.count("With every `by` v1.639 took, every row is v1.639's, key for key") == 1
    assert eight3.count("and the keys the v1.584 and v1.640 bullets below add; anything else raises") == 1
    assert ten.count("With every `--by` v1.639 took, the output keeps v1.639's bytes") == 1
    [status] = [x for x in design.splitlines() if x.startswith("Status: ")]
    assert status.count("with every key v1.639 took every output keeping its bytes (row PIN1b)") == 1
    assert ten.count("\n  - v1.640 `--by basis` and `--by pinned_by` (row PIN1b): ") == 1
    assert design.count("`report` putting pinned spend apart from routed spend (row PIN1b, which v1.640 adds, "
                        "8.3 and 10); the README paragraph (row PIN1c).") == 1
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.640 (")]
    assert line.startswith("- v1.640 (2026-11-25): spec, code and tests (8.3, 10, row PIN1b). ")
    assert line.endswith("; with every key v1.639 took every output keeps its bytes.")
    assert len(line.encode("utf-8")) <= 600
