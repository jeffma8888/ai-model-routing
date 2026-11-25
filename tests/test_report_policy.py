"""DESIGN 8.3 and 10 v1.643 (row POL2b): `report` gives each tenant's spend a row.

`report(records, by="policy")` groups each record under its `policy` label (8.1 v1.642) as a string,
a record without the key or with `null` under `"(none)"`, as `pinned_by` does (v1.640). `report --by`
takes it. With every key v1.642 took, every row keeps its bytes, whether or not the records carry
`policy`. `select --policy FILE` and `delegate --policy FILE` reading `name` are tested in
tests/test_policy_cli.py.
"""

import contextlib
import hashlib
import io
import itertools
import json
from pathlib import Path

import pytest

from model_routing import Completion, Executor, FakeProvider, Model, Monitor, Policy, Registry, Router, Stats, Task, report
from model_routing.cli import main
from model_routing.demo import run_demo

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "judge"}]
KEYS = "use model, task, flavor, family, pricing_basis, basis, pinned_by, policy or tag:<key>"
DIGEST = "sha256:" + "ab" * 32
OLD_KEYS = ("model", "task", "flavor", "family", "pricing_basis", "basis", "pinned_by", "tag:tenant")


def rec(call_id, attempt, final, outcome, model, cost, **extra):
    out = {"call_id": call_id, "task": "t", "flavor": "cost_effective", "model": model, "family": "x",
           "attempt": attempt, "final": final, "outcome": outcome, "latency_ms": 10.0,
           "input_tokens": 100, "output_tokens": 20, "cost_usd": cost, "routing_cost_usd": cost,
           "below_bar": False, "basis": "measured"}
    out.update(extra)
    return out


# Calls, by hand: a1 under tenant-a, an error on x/cheap then a fallback answer on x/mid (0.01 + 0.10);
# a2 under tenant-a, under the bar (0.02); d1 and d2 under an unnamed policy, d2 an error (0.05, 0.04);
# n1 under none (0.03) and n2 with a null policy (0.06); and a refused budget record of tenant-a,
# which carries `policy` from v1.642 and which report drops.
LOG = [
    rec("a1", 0, False, "error", "x/cheap", 0.01, policy="tenant-a"),
    rec("a1", 1, True, "ok", "x/mid", 0.10, policy="tenant-a"),
    rec("a2", 0, True, "ok", "x/cheap", 0.02, policy="tenant-a", below_bar=True),
    rec("d1", 0, True, "ok", "y/other", 0.05, policy=DIGEST),
    rec("d2", 0, True, "error", "y/other", 0.04, policy=DIGEST),
    rec("n1", 0, True, "ok", "x/cheap", 0.03),
    rec("n2", 0, True, "ok", "x/cheap", 0.06, policy=None),
    {"call_id": "a3", "task": "t", "policy": "tenant-a", "tags": {}, "budget_event": "refused",
     "model": "x/mid", "cost_usd": 9.0},
]

FIELDS = ("group", "calls", "attempts", "ok", "errors", "failed_calls", "fallback_calls",
          "below_bar_calls", "cost_usd")


def rows(by, records=LOG):
    return [tuple(r[k] for k in FIELDS) for r in report(records, by=by)]


def strip(records):
    return [{k: v for k, v in r.items() if k != "policy"} for r in records]


# --- report ------------------------------------------------------------------------------------

def test_by_policy_gives_one_row_per_label_and_the_rest_under_none():
    # 0.09 twice: "(none)" sorts before "sha256:" by group, as the cost ties
    assert rows("policy") == [
        ("tenant-a", 2, 3, 2, 1, 0, 1, 1, 0.13),
        ("(none)", 2, 2, 2, 0, 0, 0, 0, 0.09),
        (DIGEST, 2, 2, 1, 1, 1, 0, 0, 0.09),
    ]


def test_a_refused_budget_record_with_a_policy_is_in_no_row():
    budget = [r for r in LOG if "budget_event" in r]
    assert len(budget) == 1 and budget[0]["policy"] == "tenant-a"
    assert rows("policy", [r for r in LOG if "budget_event" not in r]) == rows("policy")
    assert report(budget, by="policy") == []


def test_a_hand_written_label_that_is_not_a_string_is_read_as_its_str_and_a_none_name_shares_none():
    log = [rec("a", 0, True, "ok", "x/mid", 0.5, policy=7),
           rec("b", 0, True, "ok", "x/mid", 0.25, policy="(none)"),
           rec("c", 0, True, "ok", "x/cheap", 0.125)]
    assert [(g, c, cost) for g, c, *_, cost in rows("policy", log)] == [("7", 1, 0.5), ("(none)", 2, 0.375)]


def test_audits_read_the_key_as_any_by_does():
    audits = {"a1": True, "a2": False, "d1": True, "d2": True}
    got = {r["group"]: (r["audited_calls"], r["correct_calls"], r["cost_per_success_usd"])
           for r in report(LOG, by="policy", audits=audits)}
    # a1's fallback answer is right and charged with its error; a2's audit says wrong; d2 failed;
    # neither (none) call is audited, so its cost per success is None
    assert got == {"tenant-a": (2, 1, 0.13), DIGEST: (2, 1, 0.09), "(none)": (0, 0, None)}


def test_cache_counts_and_shadow_spend_sit_in_the_row_of_their_label():
    log = [rec("a1", 0, True, "ok", "x/cheap", 0.02, policy="tenant-a", cached_input_tokens=50,
               pair_id="a1", shadow=False),
           rec("s1", 0, True, "ok", "x/mid", 0.08, policy="tenant-a", pair_id="a1", shadow=True),
           rec("n1", 0, True, "ok", "x/mid", 0.30, cached_input_tokens=80)]
    keys = ("group", "calls", "cost_usd", "cached_input_tokens", "cache_counted_input_tokens",
            "cache_hit_rate", "shadow_calls", "shadow_cost_usd")
    got = [tuple(r[k] for k in keys) for r in report(log, by="policy", cache=True, shadow=True)]
    assert got == [("(none)", 1, 0.3, 80, 100, 0.8, 0, 0.0), ("tenant-a", 1, 0.02, 50, 100, 0.5, 1, 0.08)]


def test_every_other_key_reads_the_rows_of_the_log_with_policy_stripped():
    for by in OLD_KEYS:
        for options in ({}, {"audits": {"a1": True}, "cache": True, "shadow": True}):
            assert report(LOG, by=by, **options) == report(strip(LOG), by=by, **options), (by, options)


def test_an_unknown_key_names_policy_right_after_pinned_by():
    with pytest.raises(ValueError) as caught:
        report([], by="reason")
    assert str(caught.value) == f"unknown report key 'reason'; {KEYS}"


# --- two tenants on one executor ---------------------------------------------------------------

def model(model_id, family, price):
    return Model(model_id, family, price, 2 * price, 100_000)


MODELS = [model("x/cheap", "x", 0.1), model("y/other", "y", 0.5), model("x/mid", "x", 1.0)]
TENANT_A = Policy(allowed_families=("x",), name="tenant-a")   # keeps the route: x/cheap
TENANT_B = Policy(allowed_routes=("y/other",))                 # unnamed: its label is a digest


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


def tenants_log(monitor):
    run = executor(monitor)
    for _ in range(3):
        run.call("t", MESSAGES)
    for _ in range(2):
        run.call("t", MESSAGES, policy=TENANT_A)
    run.call("t", MESSAGES, policy=TENANT_B)
    return monitor.records


def test_two_tenants_on_one_executor_split_their_spend_by_hand_count():
    records = tenants_log(Monitor())
    assert TENANT_B.label.startswith("sha256:") and len(TENANT_B.label) == 71
    assert [(r["model"], r.get("policy")) for r in records] == (
        [("x/cheap", None)] * 3 + [("x/cheap", "tenant-a")] * 2 + [("y/other", TENANT_B.label)])
    # per call 1,000 input and 200 output tokens: x/cheap 0.00014, y/other 0.0007
    assert [(r["group"], r["calls"], r["attempts"], r["cost_usd"]) for r in report(records, by="policy")] == [
        (TENANT_B.label, 1, 1, 0.0007), ("(none)", 3, 3, 0.00042), ("tenant-a", 2, 2, 0.00028)]
    for by in OLD_KEYS:
        assert report(records, by=by) == report(strip(records), by=by), by


def logged(path):
    return [json.loads(line) for line in Path(path).read_text(encoding="utf-8").splitlines()]


def cli(*argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(list(argv))
    return code, out.getvalue(), err.getvalue()


def test_report_by_policy_on_the_command_line(tmp_path):
    log = tmp_path / "calls.jsonl"
    tenants_log(Monitor(log))
    code, out, err = cli("report", "--log", str(log), "--by", "policy")
    lines = out.splitlines()
    assert (code, err) == (0, "")
    assert lines[0].split()[:3] == ["policy", "calls", "attempts"] and set(lines[1]) <= {"-", " "}
    assert [line.split()[0] for line in lines[2:]] == [TENANT_B.label, "(none)", "tenant-a"]
    code, out, err = cli("report", "--log", str(log), "--by", "policy", "--json")
    assert (code, err) == (0, "") and json.loads(out) == report(logged(log), by="policy")


def test_an_unknown_key_on_the_command_line_exits_2_naming_the_keys(tmp_path):
    log = tmp_path / "calls.jsonl"
    tenants_log(Monitor(log))
    assert cli("report", "--log", str(log), "--by", "reason") == (2, "", f"error: unknown report key 'reason'; {KEYS}\n")


# --- a log with no policy ----------------------------------------------------------------------

# sha256 of `model-routing report --log <demo>/calls.jsonl --by KEY [--json]`, taken at efe346a
# (v1.642) before this slice; a slice that changes the demo's log restates them with its reason.
V1_642 = {
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
    ("basis", False): "0bd04820c34a693367ff78623698f736149191832157cdf6ddda7875a4a02d36",
    ("basis", True): "752215ea7c5669b632e6950473317f8c4908c710ff3296daa104d7d180a60da0",
    ("pinned_by", False): "3c604c6837caa2b19ce62cff051f7fff0dd952420d42089d60b9d597122a3354",
    ("pinned_by", True): "890e7312a680dba31f06144c4c1082022dbc628b2f4f5218881dd9c030223876",
    ("tag:delegated", False): "4e8bd99361dc0a070b8be90c70a147965a5fcf4f8a0fd2c26e61acae81beec15",
    ("tag:delegated", True): "b61bf7188c6e6891942010875ff3f2dc61be88afc2d956721ea4534a19ebb6b8",
}


@pytest.fixture(scope="module")
def demo_log(tmp_path_factory):
    out = tmp_path_factory.mktemp("policy-report") / "demo"
    run_demo(out)
    return out / "calls.jsonl"


def test_the_demo_log_keeps_every_v1_642_report_byte_by_every_other_key(demo_log):
    for (by, as_json), digest in V1_642.items():
        code, out, err = cli("report", "--log", str(demo_log), "--by", by, *(["--json"] if as_json else []))
        assert (code, err, hashlib.sha256(out.encode()).hexdigest()) == (0, "", digest), (by, as_json)


def test_the_demo_log_by_policy_is_one_none_row_of_every_call(demo_log):
    records = logged(demo_log)
    assert not any("policy" in r for r in records)
    [row] = report(records, by="policy")
    [basis] = report(records, by="basis")
    assert row == dict(basis, group="(none)")


# --- the docs ----------------------------------------------------------------------------------

def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_design_states_v1_643_in_8_3_10_and_13_7():
    design = read("DESIGN.md")
    seven = design[design.index("## 7. "):design.index("## 8. ")]
    eight1 = design[design.index("### 8.1 "):design.index("### 8.2 ")]
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    cli_ = design[design.index("### 13.7 "):design.index("### 13.8 ")]
    assert eight3.count("and the keys the v1.584, v1.640 and v1.643 bullets below add; anything else raises") == 1
    assert eight3.count("\n- v1.643 `by=\"policy\"` (row POL2b, 8.1 v1.642, 5.1 v1.642): ") == 1
    assert eight3.count(f"so its list reads `{KEYS}`") == 1
    assert eight3.count("With every `by` v1.642 took, every row is v1.642's, key for key") == 1
    assert ten.count("\n  - v1.643 `--by policy` (row POL2b): ") == 1
    assert ten.count("With every `--by` v1.642 took, the output keeps v1.642's bytes") == 1
    assert ten.count("\n- v1.643 `select ... [--policy FILE]` reads `name` (row POL2b, 5.1 v1.642): ") == 1
    assert ten.count("`error: FILE: unknown policy keys K; a policy holds allowed_routes, allowed_families, "
                     "region, require_zdr and name`") == 1
    assert cli_.count("\n- v1.643 `--policy FILE` reads `name` (row POL2b): read as `select --policy` reads it "
                      "(10 v1.643), with the same exit 2 lines") == 1
    assert seven.count("reading `name` (row POL2b, which v1.643 adds, 8.3, 10 and 13.7); the README sentence, "
                       "which v1.644 adds (5.2).") == 1   # v1.644, row POL2c
    assert eight1.count("`report` (8.3) read no `policy` key in v1.642, so its rows and the CLI `report` output "
                        "were unchanged; from v1.643 `by=\"policy\"` groups by it (8.3 v1.643, row POL2b).") == 1
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.643 (")]
    assert line.startswith("- v1.643 (2026-11-25): spec, code and tests (8.3, 10, 13.7, row POL2b). ")
    assert line.endswith("; with every key v1.642 took every output keeps its bytes.")
    assert len(line.encode("utf-8")) <= 600
