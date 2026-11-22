"""DESIGN 11 v1.580 (row PROC1d): the procedure demo, the README paragraph and the note's line.

`model_routing.demo.run_procedure_demo()` routes a fictional submit, poll and fetch job between an
agent route that does it by model turns and a procedure that does it in code: an unmeasured
version is not routed, a version measured under the bar is not routed, and the version that clears
the bar is the primary, its one model call never holding the raw rows. The contract tests were
written under strict xfail and the implementing commit removed the marks; the unmarked guards pin
what v1.580 keeps and passed before and after it.
"""

import hashlib
import re
from pathlib import Path


import model_routing
from model_routing import demo as demo_module
from model_routing import run_demo

ROOT = Path(__file__).resolve().parent.parent
AGENT = "demo/atlas-mid"
V1 = "proc:job-summary@1+demo/atlas-mid"
V2 = "proc:job-summary@2+demo/atlas-mid"
# run_demo's files, computed on an archive of 6f00e21 (v1.579), whose run_demo this slice keeps;
# calls.jsonl's is the one tests/test_cascade_executor.py pins since v1.536 (review iter-427 nit 3)
DEMO_SHA256 = {
    "calls.jsonl": "4f111326781939140bebe04e0841a66306cac48492bc6c95f4bc2211fa92b351",
    "stats.json": "91f0394b0fe8b15dd9ced30216c65e01c15ea6c1cd1e76b2a85beaa19f1f4b79",
    "outcomes.jsonl": "5490bfdc336c30558f21dfd2e047fc5af923399ed9239f33ac10b9105c6918ec",
    "models.json": "00aceac37c9ca8fff3f8b00d01e819df88cc3b474dc7c12c61f3e8ddf4004124",
    "tasks.json": "81793ea3b26dae535cbbdd18f754c22fa870d19d76f33c659340ad06f034f806",
}
SHAPING = re.compile(r"Write one line: job [0-9]+: [0-9]+ rows, total [0-9]+\.")


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
    # by hand (review iter-427): each @2 call is 11 tokens in and 20 out at 2.0 and 10.0 USD per
    # million, 0.000222, plus its polls + 2 tool calls at 0.00001; jobs 40 to 59 need 110 tool calls
    assert (proc["cost_usd"], proc["input_tokens"]) == (0.00554, 220)
    assert (agent["cost_usd"], agent["input_tokens"]) == (0.059292, 16646)


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
        assert SHAPING.fullmatch(content), content  # what it counted, never the rows (nit 2)


def test_the_demo_is_the_same_on_every_run():
    assert run() == run()


def test_the_calibration_counts_and_tool_calls_of_each_route():
    # DESIGN 11 v1.580 (review iter-427 nit 1): the agent passes 38 of 40, @1 20 of 40, @2 40 of 40
    passed, tools = {}, {}
    for version, polls in (("1", 3), ("2", None)):
        proc = demo_module._job_procedure(version, polls)
        runs = [proc.run(demo_module._job_messages(i), lambda m: demo_module._job_script(m).text)
                for i in range(40)]
        passed[version] = [demo_module._job_check(i)(r.output) for i, r in enumerate(runs)]
        tools[version] = [r.tool_calls for r in runs]
    agent = [demo_module._job_check(i)(demo_module._agent_run(demo_module._job_messages(i)).text)
             for i in range(40)]
    assert [i for i in range(40) if not agent[i]] == [19, 39]
    assert [i for i in range(40) if not passed["1"][i]] == [i for i in range(40) if i % 4 >= 2]
    assert all(passed["2"])
    # the submit, the polls and the fetch: @1 stops at 3 polls, @2 at the job's 2 + i % 4
    assert tools["1"] == [2 + min(3, 2 + i % 4) for i in range(40)]
    assert tools["2"] == [2 + 2 + i % 4 for i in range(40)]
    assert demo_module.PROCEDURE_TOOL_COST_USD == 0.00001


def test_an_agent_run_bills_its_turns():
    # job 0 by hand (review iter-427): 2 polls, 5 turns; the request 12 tokens, the payload 131
    completion = demo_module._agent_run(demo_module._job_messages(0))
    assert (completion.text, completion.input_tokens, completion.output_tokens) == (
        "job 0: 30 rows, total 1395", 12 + 44 + 76 + 108 + 259, 100)
    misread = demo_module._agent_run(demo_module._job_messages(59)).text
    assert misread == "job 59: 42 rows, total 2098"  # one row fewer, the true total (nit 4)


def test_run_demo_keeps_its_bytes_and_the_procedure_demo_is_not_api(tmp_path):
    run_demo(tmp_path)
    for name, digest in DEMO_SHA256.items():
        assert hashlib.sha256((tmp_path / name).read_bytes()).hexdigest() == digest, name
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
