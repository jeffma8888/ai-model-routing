"""The README's Python examples run (DESIGN 3, v1.360, row DOC23).

tests/test_readme.py runs every `$ model-routing` transcript of README.md; this file runs
its ```python blocks, the API's only worked examples, so a renamed export, argument or
reason code fails the suite until the README follows. The blocks run in README order in
one namespace, as one script would hold them, in a temporary directory with a
`stats.json` in which a judge from another family than the parent's clears
`faithfulness_judge`, `GATEWAY_API_KEY` set to a fake key, and `urllib.request.urlopen`
replaced by a fake that records each request and answers with a reply that passes the
first block's `json_validator`. So the real `OpenAICompatibleProvider` builds and sends
every request, and nothing reaches the network.

DESIGN 3 v1.600 (row B1d): a fourth block, at the end of `## Monitoring and cost attribution`,
makes three judge calls under a `BudgetLedger`; two reach the fake, the second's settle writes
a `warn` record and the third is refused before it is sent."""

import io
import json
import re
import urllib.request
from pathlib import Path

import pytest

import model_routing

README = Path(__file__).resolve().parent.parent / "README.md"
BLOCK = re.compile(r"^```python\n(.*?)^```", re.S | re.M)
FIRST_LINES = (
    "from model_routing import (",
    "decision = router.decide_delegation(",
    'for row in report(monitor.records, by="tag:team"):',
    "from model_routing import Budget, BudgetExceeded, BudgetLedger, budget_report",
)
URL = "https://your-gateway.example/v1/chat/completions"
PARENT = "openai/gpt-6.1-sol"
JUDGE = "anthropic/claude-haiku-5.5"
REPLY = json.dumps({"verdict": "faithful", "reason": "every claim is in the source"})
STATS = {"stats": [
    {"task": "faithfulness_judge", "model": JUDGE, "successes": 98, "trials": 100},
    {"task": "faithfulness_judge", "model": PARENT, "successes": 98, "trials": 100},
]}


def readme_text():
    if not README.exists():
        pytest.skip("README.md is not next to the tests")
    return README.read_text(encoding="utf-8")


def python_blocks(text):
    """(line of the opening fence, code) of each ```python block, in README order."""
    return [(text.count("\n", 0, m.start()) + 1, m.group(1)) for m in BLOCK.finditer(text)]


def run_blocks(text, folder, monkeypatch, capsys):
    """Run each python block of ``text`` in ``folder``, offline. Return the namespace
    after each block, the requests the provider sent, and the lines each block printed."""
    monkeypatch.chdir(folder)
    (folder / "stats.json").write_text(json.dumps(STATS), encoding="utf-8")
    monkeypatch.setenv("GATEWAY_API_KEY", "fake_key")
    sent = []

    def fake_urlopen(request, timeout=None):
        sent.append({"url": request.full_url, "auth": request.get_header("Authorization"),
                     "body": json.loads(request.data), "timeout": timeout})
        return io.BytesIO(json.dumps({
            "choices": [{"message": {"content": REPLY}}],
            "usage": {"prompt_tokens": 3000, "completion_tokens": 20},
        }).encode("utf-8"))

    monkeypatch.setattr(urllib.request, "urlopen", fake_urlopen)
    namespace = {"__name__": "readme_example"}
    after, printed = [], []
    capsys.readouterr()
    for line, code in python_blocks(text):
        exec(compile(code, f"README.md:{line}", "exec"), namespace)
        after.append(dict(namespace))
        printed.append(capsys.readouterr().out.splitlines())
    return after, sent, printed


def check(after, sent, printed, folder):
    """What the README says each block does, and its bullets say of the second and the fourth."""
    assert len(after) == len(FIRST_LINES)
    first, second, third, fourth = after
    request = {"url": URL, "auth": "Bearer fake_key", "timeout": 60.0,
               "body": {"model": "claude-haiku-5-5",
                        "messages": [{"role": "user", "content": "..."}]}}

    # block 1: the one judge that clears outside the generator's family, through
    # the gateway's own model ID
    assert first["result"].model == JUDGE
    assert first["result"].text == REPLY
    assert printed[0] == [f"{JUDGE} {REPLY}"]
    assert sent[0] == request

    # block 2: the parent wrote the answer, so inline is blocked and the hand-off runs
    decision = second["decision"]
    registry = second["router"].registry
    assert (decision.mode, decision.reason, decision.inline_allowed) == (
        "delegate", "parent_not_independent", False)
    assert decision.parent == PARENT
    assert registry.get(decision.model).family != registry.get(PARENT).family
    assert second["result"].model == decision.model == JUDGE
    assert len(sent) == 4 and sent[1] == request  # v1.600: blocks 1 and 2 send the first two
    assert printed[1] == []

    # every attempt logged, the hand-off tagged `delegated` and `parent`
    records = third["monitor"].records
    assert [r["tags"] for r in records] == [
        {"team": "search-quality", "experiment": "exp-42"},
        {"team": "search-quality", "delegated": "true", "parent": PARENT},
    ]
    lines = (folder / "calls.jsonl").read_text(encoding="utf-8").splitlines()
    assert [json.loads(x) for x in lines] == records

    # block 3: one row per team
    rows = model_routing.report(records, by="tag:team")
    assert [(r["group"], r["calls"], r["fallback_rate"]) for r in rows] == [
        ("search-quality", 2, 0.0)]
    row = rows[0]
    assert printed[2] == [" ".join(str(row[k]) for k in (
        "group", "calls", "fallback_rate", "cost_usd", "p95_latency_ms"))]

    # block 4 (v1.600, row B1d): what its bullets say. Each call is held at the judge's list price
    # for 3,000 input and the task's 150 output tokens, and the fake's reply costs 0.00031
    judge = registry.get(JUDGE)
    assert judge.cost(3000, 150) == pytest.approx(0.000375)
    assert judge.cost(3000, 20) == pytest.approx(0.00031)
    assert sent[2:] == [request, request]  # the third call is never sent
    ledger, log = fourth["ledger"], fourth["budget_log"].records
    attempts = [r for r in log if "budget_event" not in r]
    events = [r for r in log if "budget_event" in r]
    assert [(r["model"], r["outcome"]) for r in attempts] == [(JUDGE, "ok"), (JUDGE, "ok")]
    assert [r["cost_usd"] for r in attempts] == [pytest.approx(0.00031)] * 2
    assert [(r["budget"], r["budget_event"]) for r in events] == [("search-quality", "warn"),
                                                                ("judge", "refused")]
    assert [r.get("budget_event") for r in log] == [None, "warn", None, "refused"]
    assert events[0]["share"] == 0.5  # 0.00062 is 62% of the team's 0.001
    assert ledger.spent_usd("judge") == pytest.approx(0.00062)
    assert ledger.spent_usd("judge") + judge.cost(3000, 150) > 0.0009
    rows = model_routing.budget_report(log, ledger.budgets)
    assert [(r["budget"], r["spent_usd"], r["budget_used_pct"], r["warn_records"], r["refused_records"])
            for r in rows] == [("search-quality", 0.00062, 62.0, 1, 0), ("judge", 0.00062, 68.888889, 0, 1)]
    day = rows[1]["window"]
    assert re.fullmatch(r"\d{4}-\d{2}-\d{2}", day) and rows[0]["window"] == day[:7]
    assert printed[3] == [f"refused by judge {day}"] + [" ".join(str(r[k]) for k in (
        "budget", "window", "budget_used_pct", "warn_records", "refused_records")) for r in rows]
    # `report` reads the same log as before: two calls, the budget records skipped
    assert [(r["group"], r["calls"]) for r in model_routing.report(log, by="model")] == [(JUDGE, 2)]


def test_readme_python_blocks_are_the_ones_this_file_runs():
    blocks = python_blocks(readme_text())
    assert tuple(code.split("\n", 1)[0] for _, code in blocks) == FIRST_LINES


def test_readme_python_blocks_run_offline(tmp_path, monkeypatch, capsys):
    after, sent, printed = run_blocks(readme_text(), tmp_path, monkeypatch, capsys)
    check(after, sent, printed, tmp_path)


# Each case changes the README text in memory in one place (one imported name, one keyword
# or the second block's premise) and the run then fails, so the same change made in README.md
# fails test_readme_python_blocks_run_offline.
MUTANTS = [
    ("Router, Stats, json_validator, load_tasks, report,",
     "Router, Stats, json_validator, load_task, report,", ImportError),
    ('api_key_env="GATEWAY_API_KEY",', 'api_key_var="GATEWAY_API_KEY",', TypeError),
    ('validate=json_validator("verdict", "reason"),',
     'validator=json_validator("verdict", "reason"),', TypeError),
    ("context_tokens=60_000, brief_tokens=400,", "context_tokens=60_000, brief_size=400,",
     TypeError),
    ("decision, messages=[", "decision, brief=[", TypeError),
    ('report(monitor.records, by="tag:team")', 'report(monitor.records, group="tag:team")',
     TypeError),
    ('    generator_model="openai/gpt-6.1-sol",\n)\nif decision.mode',
     ")\nif decision.mode", AssertionError),
    # v1.600 (row B1d): the fourth block's keyword and its premise, a limit that refuses the third call
    ("monitor=budget_log, ledger=ledger)", "monitor=budget_log, budget=ledger)", TypeError),
    ('Budget("judge", 0.0009, "refuse",', 'Budget("judge", 0.002, "refuse",', AssertionError),
]


@pytest.mark.parametrize("old, new, error", MUTANTS, ids=[
    "import", "api_key_env", "validate", "brief_tokens", "messages", "by", "generator_model",
    "ledger", "refuse_limit"])
def test_a_changed_name_or_keyword_fails_the_run(old, new, error, tmp_path, monkeypatch,
                                                  capsys):
    text = readme_text()
    assert text.count(old) == 1
    with pytest.raises(error):
        check(*run_blocks(text.replace(old, new), tmp_path, monkeypatch, capsys), tmp_path)
