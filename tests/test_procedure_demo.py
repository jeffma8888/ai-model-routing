"""DESIGN 11 v1.580 (row PROC1d): the procedure demo, the README paragraph and the note's line.

`model_routing.demo.run_procedure_demo()` routes a fictional submit, poll and fetch job between an
agent route that does it by model turns and a procedure that does it in code: an unmeasured
version is not routed, a version measured under the bar is not routed, and the version that clears
the bar is the primary, its one model call never holding the raw rows. The contract tests were
written under strict xfail and the implementing commit removed the marks; the unmarked guards pin
what v1.580 keeps and passed before and after it.
"""

import hashlib
from pathlib import Path


import model_routing
from model_routing import demo as demo_module
from model_routing import run_demo

ROOT = Path(__file__).resolve().parent.parent
AGENT = "demo/atlas-mid"
V1 = "proc:job-summary@1+demo/atlas-mid"
V2 = "proc:job-summary@2+demo/atlas-mid"
# the demo's calls.jsonl, unchanged since v1.536 (tests/test_cascade_executor.py)
DEMO_CALLS_SHA256 = "4f111326781939140bebe04e0841a66306cac48492bc6c95f4bc2211fa92b351"


def run():
    return demo_module.run_procedure_demo()


def readme_part():
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    part = text.split("\n## How a model is chosen\n", 1)[1].split("\n## ", 1)[0]
    return part.split("\n### The quality bar", 1)[0]


def test_the_summary_keys_and_task():
    summary = run()
    assert list(summary) == ["task", "bar", "stages", "routed"]
    assert (summary["task"], summary["bar"]) == ("demo_job_summary", 0.8)


def test_the_procedure_is_routed_only_once_its_own_runs_clear_the_bar():
    assert run()["stages"] == [
        {"stage": "cold", "procedure": V2, "reason": "insufficient_samples", "primary": AGENT},
        {"stage": "below_bar", "procedure": V1, "reason": "below_bar", "primary": AGENT},
        {"stage": "admitted", "procedure": V2, "reason": "passes", "primary": V2},
    ]


def test_the_routed_procedure_answers_every_call_and_costs_less_than_the_agent():
    routed = run()["routed"]
    assert list(routed) == ["procedure", "agent"]
    keys = ["route", "calls", "fallback_calls", "failed_calls", "cost_usd", "input_tokens"]
    assert [list(routed[path]) for path in routed] == [keys, keys]
    proc, agent = routed["procedure"], routed["agent"]
    assert (proc["route"], proc["calls"], proc["fallback_calls"], proc["failed_calls"]) == (
        V2, 20, 0, 0)
    # the agent misreads job 59 (59 % 20 == 19) and has no route to fall back to
    assert (agent["route"], agent["calls"], agent["fallback_calls"], agent["failed_calls"]) == (
        AGENT, 20, 0, 1)
    assert 0 < proc["cost_usd"] < agent["cost_usd"]
    assert 0 < proc["input_tokens"] < agent["input_tokens"]


def test_the_raw_rows_never_enter_a_model_call_of_a_procedure(monkeypatch):
    providers = []

    class Recording(demo_module.FakeProvider):
        def __init__(self, script):
            super().__init__(script)
            providers.append(self)

    monkeypatch.setattr(demo_module, "FakeProvider", Recording)
    run()
    calls = [(model, messages) for provider in providers for model, messages in provider.calls]
    assert {model for model, _ in calls} == {AGENT}
    shaping = [m for _, m in calls if m[0]["content"].startswith("Write one line: ")]
    agent_runs = [m for _, m in calls if m[0]["content"].startswith("Run job ")]
    assert len(calls) == len(shaping) + len(agent_runs)
    # @1 and @2 on jobs 0 to 39, then @2 on jobs 40 to 59; the agent on 0 to 39 and 40 to 59
    assert (len(shaping), len(agent_runs)) == (100, 60)
    for messages in shaping:
        assert len(messages) == 1
        content = messages[0]["content"]
        assert "amount" not in content and "\n" not in content
        assert content.endswith(" total " + content.rsplit(" total ", 1)[1])


def test_the_demo_is_the_same_on_every_run():
    assert run() == run()


def test_run_demo_keeps_its_bytes_and_the_procedure_demo_is_not_api(tmp_path):
    run_demo(tmp_path)
    digest = hashlib.sha256((tmp_path / "calls.jsonl").read_bytes()).hexdigest()
    assert digest == DEMO_CALLS_SHA256
    assert "run_procedure_demo" not in model_routing.__all__


def test_the_readme_paragraph_on_procedures():
    part = readme_part()
    assert "`model_routing.demo.run_procedure_demo()`" in part
    assert "`proc:<name>@<version>+<model>`" in part
    assert "`select(..., procedures=[...])`" in part and "`Executor.call(..., procedures=[...])`" in part
    assert "`DESIGN.md` 4.5, 5.2, 7 and 11" in part
    assert ('"the loop runs in a subprocess, and only the summary comes back."' in part)
    assert ("(research/production-lessons.md#keep-tool-schemas-and-polling-out-of-the-models-context)"
            in part)
    # row PROC1d: no skill-only precision number exists in the sources, so none is claimed
    assert "precision" not in part.split("\n\nRecurring tool work can be a route", 1)[1]


def test_the_production_note_states_procedures_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert "a script that does recurring work is outside its choice. The change:" not in text
    lines = [line for line in text.splitlines()
             if line.startswith("- In this library: it routes model calls and prices")]
    assert len(lines) == 1
    assert ("A fixed procedure for recurring work is a route candidate beside the model routes "
            "today") in lines[0]
    assert "`model_routing.demo.run_procedure_demo()`" in lines[0]
