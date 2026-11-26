"""DESIGN 11 v1.585 (row SELF1d): the self-hosted demo, the README paragraph and the note's line.

`model_routing.demo.run_self_hosted_demo()` routes a fictional fine-tune that its owner serves,
priced from its hour, against a list-priced model by measured success: unmeasured it is not
routed, once its own runs clear the bar it is the primary, the same hour used a fiftieth of the
time makes it the dearer route, and it never judges its base's output. The contract tests were
written under strict xfail and the implementing commit removed the marks; the unmarked guards
pin what v1.585 keeps and passed before and after it.
"""

import hashlib
import json
from pathlib import Path

import pytest

import model_routing
from model_routing import Registry, run_demo, self_hosted_prices
from model_routing import demo as demo_module

ROOT = Path(__file__).resolve().parent.parent
FT = "demo/birch-nano-ft"
BASE = "demo/birch-nano"
LIST = "demo/atlas-mid"
ROW = {
    "id": FT, "base_model": BASE, "context_window": 32000, "pricing_basis": "self_hosted",
    "deployment": "self_hosted", "usd_per_hour": 2.0, "tokens_per_hour_in": 18000000,
    "tokens_per_hour_out": 1800000, "utilization": 0.5, "input_cost_share": 0.5,
}
# run_demo's files, as tests/test_procedure_demo.py pins them since v1.580; this slice keeps them
DEMO_SHA256 = {
    "calls.jsonl": "4f111326781939140bebe04e0841a66306cac48492bc6c95f4bc2211fa92b351",
    "stats.json": "91f0394b0fe8b15dd9ced30216c65e01c15ea6c1cd1e76b2a85beaa19f1f4b79",
    "outcomes.jsonl": "5490bfdc336c30558f21dfd2e047fc5af923399ed9239f33ac10b9105c6918ec",
    "models.json": "00aceac37c9ca8fff3f8b00d01e819df88cc3b474dc7c12c61f3e8ddf4004124",
    "tasks.json": "81793ea3b26dae535cbbdd18f754c22fa870d19d76f33c659340ad06f034f806",
}


def run():
    return demo_module.run_self_hosted_demo()


def readme_part():
    # v1.604 (row PROD1a): the paragraph moved to `## Running it in production`, word for word
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return text.split("\n## Running it in production\n", 1)[1].split("\n## ", 1)[0]


def paragraph():
    found = [p for p in readme_part().split("\n\n") if p.startswith("A model you train or serve yourself")]
    assert len(found) == 1
    return found[0]


def test_the_summary_keys_task_and_row():
    summary = run()
    assert list(summary) == ["task", "bar", "row", "prices", "stages", "routed"]
    assert (summary["task"], summary["bar"]) == ("demo_clause_review", 0.75)
    assert summary["row"] == ROW and list(summary["row"]) == list(ROW)
    assert summary["row"] is not demo_module.SELF_HOSTED_ROW
    assert demo_module.SELF_HOSTED_ROW == ROW


def test_the_row_loads_as_the_routed_fine_tune(tmp_path):
    listed = {m.id: m for m, _ in demo_module.JUDGES}
    rows = [{"id": m.id, "family": m.family, "price_in": m.price_in, "price_out": m.price_out,
             "context_window": m.context_window} for m in (listed[LIST], listed[BASE])]
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": rows + [ROW]}), encoding="utf-8")
    loaded = Registry.load(path).get(FT)
    assert loaded == demo_module._fine_tune(0.5)
    assert (loaded.family, loaded.pricing_basis, loaded.deployment, loaded.base_model) == (
        "birch", "self_hosted", "self_hosted", BASE)
    prices = run()["prices"]
    assert prices == [loaded.price_in, loaded.price_out]
    assert prices == list(self_hosted_prices(2.0, 18000000, 1800000, 0.5, 0.5))
    # by hand: 2 USD x 0.5 / (18,000,000 x 0.5) x 1e6 = 1/9; 2 x 0.5 / (1,800,000 x 0.5) x 1e6 = 10/9
    assert prices == pytest.approx([1 / 9, 10 / 9], rel=1e-12)
    idle = demo_module._fine_tune(0.02)
    assert (idle.price_in, idle.price_out) == pytest.approx((25 / 9, 250 / 9), rel=1e-12)


def test_the_fine_tune_is_routed_only_once_its_own_runs_clear_the_bar():
    # by hand: 1,000 in and 200 out at 1/9 and 10/9 USD per 1M is 0.000333...; at 0.02, 25 times
    # that, 0.008333..., over demo/atlas-mid's 1,000 x 2.0 + 200 x 10.0 per 1M, 0.004
    assert run()["stages"] == [
        {"stage": "cold", "utilization": 0.5, "reason": "insufficient_samples",
         "list_cost": 0.000333, "primary": LIST},
        {"stage": "admitted", "utilization": 0.5, "reason": "passes", "list_cost": 0.000333,
         "primary": FT},
        {"stage": "idle", "utilization": 0.02, "reason": "passes", "list_cost": 0.008333,
         "primary": LIST},
        {"stage": "generator_base", "utilization": 0.5, "reason": "generator_family",
         "list_cost": 0.000333, "primary": LIST},
    ]


def test_the_routed_paths_and_their_spend_by_basis():
    routed = run()["routed"]
    assert list(routed) == ["self_hosted", "list_only"]
    # the fine-tune misses items 69 and 79 and demo/atlas-mid answers both; alone, demo/atlas-mid
    # misses item 78 and has no fallback, since demo/birch-nano is under the bar
    assert routed["self_hosted"] == {
        "route": FT, "calls": 20, "fallback_calls": 2, "failed_calls": 0, "cost_usd": 0.014667,
        "spend": [{"pricing_basis": "list", "calls": 2, "cost_usd": 0.008},
                  {"pricing_basis": "self_hosted", "calls": 18, "cost_usd": 0.006667}],
    }
    assert routed["list_only"] == {
        "route": LIST, "calls": 20, "fallback_calls": 0, "failed_calls": 1, "cost_usd": 0.08,
        "spend": [{"pricing_basis": "list", "calls": 20, "cost_usd": 0.08}],
    }


def test_each_attempt_on_the_fine_tune_names_its_basis_and_its_base_family(monkeypatch):
    monitors = []

    class Recording(demo_module.Monitor):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            monitors.append(self)

    monkeypatch.setattr(demo_module, "Monitor", Recording)
    run()
    records = [r for m in monitors for r in m.records]
    assert len(records) == 42  # 20 + 2 fallback attempts, then 20 on demo/atlas-mid alone
    ft = [r for r in records if r["model"] == FT]
    assert len(ft) == 20
    assert all(r["pricing_basis"] == "self_hosted" and r["family"] == "birch" for r in ft)
    assert all("pricing_basis" not in r for r in records if r["model"] != FT)
    assert {r["call_id"] for r in records} == (
        {f"self_hosted-{n:04d}" for n in range(1, 21)} | {f"list_only-{n:04d}" for n in range(1, 21)})
    assert {r["ts"] for r in records} == {"2026-01-01T00:00:00.000Z"}


def test_the_calibration_counts_of_each_model():
    passed = {}
    for model_id in (LIST, BASE, FT):
        answer = demo_module._reviewer(model_id)
        passed[model_id] = [demo_module._clause_check(i)(answer(demo_module._clause_messages(i)).text)
                            for i in range(60)]
    assert [i for i in range(60) if not passed[LIST][i]] == [38]
    assert [i for i in range(60) if not passed[BASE][i]] == list(range(3, 60, 4))
    assert [i for i in range(60) if not passed[FT][i]] == list(range(9, 60, 10))
    completion = demo_module._reviewer(FT)(demo_module._clause_messages(3))
    assert (completion.text, completion.input_tokens, completion.output_tokens) == ("reject", 1000, 200)
    assert demo_module._clause_messages(7) == [
        {"role": "user", "content": "Review the tag given to clause 7."}]


def test_the_demo_is_the_same_on_every_run():
    assert run() == run()


def test_run_demo_keeps_its_bytes_and_the_self_hosted_demo_is_not_api(tmp_path):
    run_demo(tmp_path)
    for name, digest in DEMO_SHA256.items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest, name
    assert "run_self_hosted_demo" not in model_routing.__all__


def test_the_readme_paragraph_on_self_hosted_models():
    text = paragraph()
    for key in ('`"pricing_basis": "self_hosted"`', "`usd_per_hour`", "`tokens_per_hour_in`",
                "`tokens_per_hour_out`", "`utilization`", "`input_cost_share`", '`"base_model"`',
                '`"deployment"`', "`report --by pricing_basis`",
                "`model_routing.demo.run_self_hosted_demo()`",
                "`DESIGN.md` 4.1, 5.1, 8.1, 8.3, 10 and 11"):  # review iter-433 nit 1
        assert key in text, key
    # v1.652 (row PROD1gbbbbb): the hour used a fiftieth of the time is DESIGN 11's (tests/test_readme_trim.py
    # DROPPED_V1_652); v1.653 (row PROD1h) brings back the one workload and the hour's split (review iter-507 should-fix 3)
    assert text.count("so it is routed like any model. Its throughputs describe one workload, and its split of "
                      "the hour between input and output is an approximation you choose. A fine-tune ") == 1
    # v1.648 (row PROD1gb): what each field means, how the row is admitted, why an hour has no one price per
    # token and that the demo's fine-tune never judges its base are DESIGN 4.1's and 11's
    # (tests/test_readme_trim.py)
    assert text.count("gives `usd_per_hour`, `tokens_per_hour_in`, `tokens_per_hour_out`, `utilization` and "
                      "`input_cost_share`. The loader derives its prices per million tokens from them, so it is "
                      "routed like any model. ") == 1
    assert text.count("it is the primary at a twelfth of the list model's cost a call. Harvey reports ") == 1
    assert ("(research/production-lessons.md#your-own-trained-model-is-a-candidate-kept-to-the-tasks-"
            "it-was-measured-on)") in text
    # every quote in the paragraph is one of the note's checked quotes, word for word
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    quotes = text.split('"')[1::2]
    harvey = [q for q in quotes if " " in q]
    assert harvey == ["completes tasks competitively with leading frontier models while reducing "
                      "cost per query by 90%."]
    assert all(f'"{q}"' in note for q in harvey)
    readme = readme_part()
    assert readme.index("Recurring tool work can be a route") < readme.index(text)


def test_the_production_note_states_deployment_and_base_model_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    lesson = text.split("\n### Your own trained model is a candidate, kept to the tasks it was "
                        "measured on\n", 1)[1].split("\n### ", 1)[0]
    lines = [line for line in lesson.splitlines() if line.startswith("- In this library: ")]
    assert len(lines) == 1
    line = lines[0]
    assert "A fine-tune names its base with `base_model` and is judged as its base's family" in line
    assert "`deployment` records whether a model runs on a vendor's endpoint or on servers you run" in line
    assert "`model_routing.demo.run_self_hosted_demo()`" in line
    # v1.586 (row SCOPE1): the task scope ships, so the line states it
    assert "`scope_tasks`, task names or glob patterns, keeps a model built for some tasks off the others" in line
    assert "The change still planned" not in line


def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    eleven = design[design.index("## 11. "):design.index("## 12. ")]
    assert eleven.count("- v1.585 (row SELF1d): `run_self_hosted_demo() -> dict`") == 1
    assert "0.014667 USD, 0.008 under `list` and 0.006667 under `self_hosted`" in eleven
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.585 (")]
    assert len(mine) == 1
    assert "(11, row SELF1d). `run_self_hosted_demo()`" in mine[0]
    assert ("Changes `test_only_the_registry_reads_the_basis_yet` and "
            "`test_only_the_registry_reads_the_keys_yet`.") in mine[0]
