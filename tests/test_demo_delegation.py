"""v1.12: the demo makes one inline-or-sub-agent decision per flavor and runs the
delegated one through Executor.call_delegated (DESIGN 11)."""

import hashlib
import json

import pytest
from model_routing import Executor, Registry, Router, Stats, load_records, load_tasks, report, run_demo
from model_routing.cli import main

# Output of the v1.11 demo at seed 7, before it made any delegation decision:
# its 455 call records, its other files and its summary must not change
V111_CALL_RECORDS = 455
V111_CALLS_SHA256 = "1df2e1cd0d463a7c8721d52fe11dc2526acd8583a455c36a326ce4064db544af"
V111_FILE_SHA256 = {
    "stats.json": "91f0394b0fe8b15dd9ced30216c65e01c15ea6c1cd1e76b2a85beaa19f1f4b79",
    "outcomes.jsonl": "5490bfdc336c30558f21dfd2e047fc5af923399ed9239f33ac10b9105c6918ec",
    "models.json": "00aceac37c9ca8fff3f8b00d01e819df88cc3b474dc7c12c61f3e8ddf4004124",
    # v1.202 (DESIGN 11): every 4.2 field, so the v1.11 file plus `"fallback_below_bar": false` last
    "tasks.json": "81793ea3b26dae535cbbdd18f754c22fa870d19d76f33c659340ad06f034f806",
}
V111_SUMMARY = {
    "cost_effective": {"primary": "demo/atlas-mid", "fallbacks": ["demo/birch-pro", "demo/atlas-max"],
                       "calls": 200, "fallback_calls": 25, "cost_usd": 0.864982},
    "cost_blind": {"primary": "demo/atlas-max", "fallbacks": ["demo/atlas-mid", "demo/birch-pro"],
                   "calls": 200, "fallback_calls": 30, "cost_usd": 3.379358},
}
V111_STDOUT_HEAD = [
    "model-routing demo (fictional demo/ models, simulated outages)",
    "",
    "cost_effective:",
    "  primary:        demo/atlas-mid",
    "  fallbacks:      demo/birch-pro, demo/atlas-max",
    "  calls:          200",
    "  fallback calls: 25",
    "  list-price USD: 0.8650",
    "",
    "cost_blind:",
    "  primary:        demo/atlas-max",
    "  fallbacks:      demo/atlas-mid, demo/birch-pro",
    "  calls:          200",
    "  fallback calls: 30",
    "  list-price USD: 3.3794",
    "",
    "cost_effective spent 26% of what cost_blind spent",
]
DELEGATION_KEYS = ["parent", "context_tokens", "mode", "model", "reason", "inline_cost_usd",
                   "delegate_cost_usd", "hand_off_calls", "hand_off_cost_usd"]
TAGS = {"suite": "demo", "dataset": "synthetic", "delegated": "true", "parent": "demo/atlas-max"}


def sha256(data):
    return hashlib.sha256(data).hexdigest()


@pytest.fixture(scope="module")
def demo_run(tmp_path_factory):
    out = tmp_path_factory.mktemp("demo") / "run"
    return out, run_demo(out)


def decide(out, flavor):
    from model_routing import demo
    router = Router(Registry.load(out / "models.json"), load_tasks(out / "tasks.json"),
                    Stats.load(out / "stats.json"))
    return router.decide_delegation(demo.DEMO_TASK, "demo/atlas-max", flavor,
                                    context_tokens=60_000, brief_tokens=400, result_tokens=60,
                                    generator_model=demo.GENERATOR)


def test_demo_names_the_parent_and_context_of_its_delegation_question():
    from model_routing import demo
    assert demo.DELEGATION_PARENT == "demo/atlas-max"
    assert demo.DELEGATION_CONTEXT_TOKENS == 60_000


def test_demo_summary_keeps_every_v111_value_and_adds_delegation_last(demo_run):
    _, summary = demo_run
    assert list(summary) == ["cost_effective", "cost_blind"]
    for flavor, values in summary.items():
        assert list(values) == ["primary", "fallbacks", "calls", "fallback_calls", "cost_usd",
                                "delegation"]
    assert {f: {k: v for k, v in s.items() if k != "delegation"}
            for f, s in summary.items()} == V111_SUMMARY


def test_demo_keeps_its_v111_records_and_files_byte_identical(demo_run):
    out, _ = demo_run
    lines = (out / "calls.jsonl").read_bytes().splitlines(keepends=True)
    assert len(lines) > V111_CALL_RECORDS
    assert sha256(b"".join(lines[:V111_CALL_RECORDS])) == V111_CALLS_SHA256
    for name, digest in V111_FILE_SHA256.items():
        assert sha256((out / name).read_bytes()) == digest, name


def test_demo_delegation_summary_is_decide_delegation_on_its_own_output(demo_run):
    out, summary = demo_run
    for flavor in summary:
        entry = summary[flavor]["delegation"]
        assert list(entry) == DELEGATION_KEYS
        decision = decide(out, flavor)
        assert entry["parent"] == decision.parent == "demo/atlas-max"
        assert entry["context_tokens"] == 60_000
        for key in ("mode", "model", "reason", "inline_cost_usd", "delegate_cost_usd"):
            assert entry[key] == getattr(decision, key), (flavor, key)


def test_demo_seed_7_delegates_in_cost_effective_and_stays_inline_in_cost_blind(demo_run):
    _, summary = demo_run
    ce, cb = summary["cost_effective"]["delegation"], summary["cost_blind"]["delegation"]
    assert (ce["mode"], ce["model"], ce["reason"]) == ("delegate", "demo/atlas-mid", "delegate_cheaper")
    assert ce["delegate_cost_usd"] < ce["inline_cost_usd"]
    assert ce["hand_off_calls"] == 1 and ce["hand_off_cost_usd"] > 0
    assert (cb["mode"], cb["model"], cb["reason"]) == ("inline", "demo/atlas-max", "inline_as_good")
    assert cb["hand_off_calls"] == 0 and cb["hand_off_cost_usd"] == 0.0


def test_demo_hand_off_records_follow_the_judge_calls_tagged_delegated_and_parent(demo_run):
    from model_routing import demo
    out, summary = demo_run
    records = load_records(out / "calls.jsonl")
    judged, handed = records[:V111_CALL_RECORDS], records[V111_CALL_RECORDS:]
    assert not any("delegated" in r["tags"] or "parent" in r["tags"] for r in judged)
    route = decide(out, "cost_effective").route
    order = [route.primary, *route.fallbacks]
    assert [r["model"] for r in handed] == order[:len(handed)]
    assert [r["attempt"] for r in handed] == list(range(len(handed)))
    assert [r["final"] for r in handed] == [False] * (len(handed) - 1) + [True]
    for r in handed:
        assert r["call_id"] == "cost_effective-delegated-0001"
        assert (r["task"], r["flavor"], r["basis"]) == (demo.DEMO_TASK, "cost_effective", route.basis)
        assert r["below_bar"] is route.below_bar
        assert r["tags"] == TAGS
    entry = summary["cost_effective"]["delegation"]
    assert sum(r["final"] for r in handed) == entry["hand_off_calls"]
    assert round(sum(r["cost_usd"] for r in handed), 6) == entry["hand_off_cost_usd"]
    rows = {row["group"]: row for row in report(records, by="tag:delegated")}
    assert set(rows) == {"true", "(none)"}
    assert rows["true"]["calls"] == 1 and rows["(none)"]["calls"] == 400


def test_demo_runs_its_hand_off_through_call_delegated(tmp_path, monkeypatch):
    seen = []
    original = Executor.call_delegated

    def spy(self, decision, messages, tags=None, validate=None):
        seen.append((decision.flavor, decision.mode, decision.parent, dict(tags or {}),
                     validate is not None))
        return original(self, decision, messages, tags=tags, validate=validate)

    monkeypatch.setattr(Executor, "call_delegated", spy)
    run_demo(tmp_path / "demo")
    assert seen == [("cost_effective", "delegate", "demo/atlas-max",
                     {"suite": "demo", "dataset": "synthetic"}, True)]


def test_cli_demo_prints_the_inline_or_sub_agent_lines_after_the_spend_line(tmp_path, capsys):
    summary = run_demo(tmp_path / "reference")
    capsys.readouterr()
    out = tmp_path / "demo"
    assert main(["demo", "--out", str(out)]) == 0
    lines = capsys.readouterr().out.rstrip("\n").split("\n")
    cost = summary["cost_effective"]["delegation"]["hand_off_cost_usd"]
    assert lines == V111_STDOUT_HEAD + [
        "",
        "inline or sub-agent, a demo/atlas-max parent at 60,000 context tokens:",
        "  cost_effective: delegate to demo/atlas-mid (delegate_cheaper), "
        "inline 0.632000 vs delegate 0.029400 USD",
        "  cost_blind:     inline on demo/atlas-max (inline_as_good), "
        "inline 0.632000 vs delegate 0.048600 USD",
        f"  hand-off calls: 1, list-price USD {cost:.4f}",
        f"log: {out / 'calls.jsonl'}",
    ]


def test_cli_demo_sums_hand_offs_and_prints_a_missing_delegate_cost_as_a_dash(tmp_path, capsys,
                                                                              monkeypatch):
    from model_routing import cli

    def entry(mode, model, reason, delegate_cost, calls, cost):
        return {"parent": "demo/birch-nano", "context_tokens": 1_234_567, "mode": mode,
                "model": model, "reason": reason, "inline_cost_usd": 0.5,
                "delegate_cost_usd": delegate_cost, "hand_off_calls": calls,
                "hand_off_cost_usd": cost}

    def fake_run_demo(out_dir):
        base = {"primary": "demo/a", "fallbacks": [], "calls": 1, "fallback_calls": 0,
                "cost_usd": 1.0}
        return {"cost_effective": dict(base, delegation=entry(
                    "delegate", "demo/a", "parent_below_bar", 0.25, 1, 0.0012)),
                "cost_blind": dict(base, delegation=entry(
                    "inline", "demo/birch-nano", "only_parent_clears", None, 0, 0.0)),
                "extra_flavor_for_order": dict(base, delegation=entry(
                    "delegate", "demo/b", "delegate_better", 0.125, 1, 0.0025))}

    monkeypatch.setattr(cli, "run_demo", fake_run_demo)
    assert main(["demo", "--out", str(tmp_path / "x")]) == 0
    lines = capsys.readouterr().out.rstrip("\n").split("\n")
    start = lines.index("inline or sub-agent, a demo/birch-nano parent at 1,234,567 context tokens:")
    assert lines[start - 1] == ""
    assert lines[start + 1:] == [
        "  cost_effective: delegate to demo/a (parent_below_bar), inline 0.500000 vs delegate 0.250000 USD",
        "  cost_blind:     inline on demo/birch-nano (only_parent_clears), inline 0.500000 vs delegate - USD",
        "  extra_flavor_for_order: delegate to demo/b (delegate_better), inline 0.500000 vs delegate 0.125000 USD",
        "  hand-off calls: 2, list-price USD 0.0037",
        f"log: {tmp_path / 'x' / 'calls.jsonl'}",
    ]
