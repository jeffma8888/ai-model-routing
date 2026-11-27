"""DESIGN 5.2 v1.680 (row PROD1j): the pair route in README `## Running it in production`.

No code changes. The section ends with one paragraph of at most 600 bytes, right after the one on the
self-consistency minimum (v1.675), on routing a delegating harness's root and sub-agent models as a pair:
`select_pair` (5.2 v1.670) or `model-routing select-pair` (10 v1.676) admits `<root>+<leaf>` only on its own
runs, each side is priced at its tokens there from a results row's four side token keys (4.3 v1.672, 5.2
v1.671), and `Executor.call_pair` runs the caller's harness on the pair (7 v1.678), with one pointer to
DESIGN.md and a link to the Harvey lesson on the orchestrator. Each claim is checked here on the command line
and the library beside the words that state it, on a fixture of two roots and one leaf: each model alone at
40 of 40, the strong root's pair at 39 of 40 with side tokens, the cheap root's pair with no run. The bytes
are tests/test_readme_trim.py's v1.680 block, and every README transcript keeps its bytes (gates.py).

DESIGN 5.2 v1.682 (row PROD1k, review iter-538 should-fix 1): the paragraph says `Executor.call_pair` runs the
harness on the pair, held and settled on your budgets (7 v1.681, row DEL1g), within its 600 bytes by a shorter
pricing clause; the hold and the settle are checked here on the same fixture, and the bytes are
tests/test_readme_trim.py's v1.682 block.
"""

import argparse
import contextlib
import io
import json
from datetime import date
from pathlib import Path

from test_readme_production import PRODUCTION, PRODUCTION_CAP, link_problems, paragraphs, size

import pytest

from model_routing import (Budget, BudgetExceeded, BudgetLedger, Executor, FakeProvider, Monitor, Registry, Router,
                           Stats, load_tasks)
from model_routing.cli import _build_parser, main

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 27)
CONSISTENCY_LEAD = "A judge can also be held to grading alike on reruns. "
LESSON = "The orchestrator gets the strong model; the readers can be cheap"
ANCHOR = "research/production-lessons.md#the-orchestrator-gets-the-strong-model-the-readers-can-be-cheap"
PARAGRAPH = (
    "A delegating harness's root and sub-agent models can be routed as a pair: `select_pair` or "
    "`model-routing select-pair TASK --root MODEL ... --leaf MODEL ...` admits `<root>+<leaf>` only on its own runs, "
    "each side priced from a results row's `root_input_tokens`, `root_output_tokens`, "
    "`leaf_input_tokens` and `leaf_output_tokens`, and `Executor.call_pair` runs the harness on the pair, "
    "held and settled on your budgets (`DESIGN.md` 4.3, 5.2, 7 and 10). "
    f"For Harvey [the orchestrator gets the strong model]({ANCHOR}).")
STRONG, CHEAP, LEAF = "r/strong", "r/cheap", "l/cheap"
PRICES = {STRONG: (10.0, 30.0), CHEAP: (0.2, 0.6), LEAF: (0.1, 0.3)}  # USD per million input and output tokens
SIDES = {"root_input_tokens": 1200, "root_output_tokens": 300, "leaf_input_tokens": 5000, "leaf_output_tokens": 800}
N = 40
MESSAGES = [{"role": "user", "content": "review the data room"}]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def says(words):
    assert PARAGRAPH.count(words) == 1, words


def run(argv):
    """`main(argv)` at TODAY as (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, today=TODAY)
    return code, out.getvalue(), err.getvalue()


def make(d, sides=True):
    """The fixture's files, calibrated by `model-routing calibrate`; with ``sides`` each pair row carries the
    four side token keys, else none."""
    d.mkdir(exist_ok=True)
    rows = [{"id": m, "family": m.split("/")[1], "price_in": p[0], "price_out": p[1], "context_window": 100_000}
            for m, p in PRICES.items()]
    (d / "models.json").write_text(json.dumps({"models": rows}), encoding="utf-8")
    task = {"name": "t", "bar": 0.8, "min_samples": 30, "expected_input_tokens": 1000, "expected_output_tokens": 200}
    (d / "tasks.json").write_text(json.dumps({"tasks": [task]}), encoding="utf-8")
    results = [{"task": "t", "model": m, "correct": True} for m in PRICES for _ in range(N)]
    results += [{"task": "t", "model": f"{STRONG}+{LEAF}", "correct": i > 0, **(SIDES if sides else {})}
                for i in range(N)]
    (d / "results.jsonl").write_text("".join(json.dumps(r) + "\n" for r in results), encoding="utf-8")
    code, _, err = run(["calibrate", "--results", str(d / "results.jsonl"), "--stats", str(d / "stats.json")])
    assert (code, err) == (0, "")
    return ["--registry", str(d / "models.json"), "--tasks", str(d / "tasks.json"), "--stats", str(d / "stats.json")]


def select_pair(base):
    code, out, err = run(["select-pair", "t", "--root", STRONG, CHEAP, "--leaf", LEAF, "--json", *base])
    assert (code, err) == (0, "")
    return json.loads(out)


def by_id(data):
    return {c["model_id"]: c for c in data["candidates"]}


# --- README -------------------------------------------------------------------------------------

def test_the_paragraph_follows_the_one_on_the_self_consistency_minimum_inside_the_cap():
    text = read("README.md")
    found = paragraphs(text, PRODUCTION)
    # placed by its neighbour (v1.655, row T30); tests/test_readme_trim.py names the section's last paragraph
    assert text.count(PARAGRAPH) == 1 and found.count(PARAGRAPH) == 1
    at = found.index(PARAGRAPH)
    assert at > 0 and found[at - 1].startswith(CONSISTENCY_LEAD)
    assert len(PARAGRAPH.encode("utf-8")) <= 600  # 600 from v1.682 (row PROD1k), 587 at v1.680
    assert size(text, PRODUCTION) <= PRODUCTION_CAP == 30_000
    assert "\u2014" not in PARAGRAPH and "\u2013" not in PARAGRAPH and "```" not in PARAGRAPH
    assert link_problems(text) == []


def test_it_names_each_part_of_the_pair_route():
    for name in ("`select_pair`", "`model-routing select-pair TASK --root MODEL ... --leaf MODEL ...`",
                 "`<root>+<leaf>`", "`root_input_tokens`", "`root_output_tokens`", "`leaf_input_tokens`",
                 "`leaf_output_tokens`", "`Executor.call_pair`"):
        says(name)
    # README.md named neither the method nor the command before v1.680 (row PROD1j)
    text = read("README.md")
    assert text.count("select_pair") == 1 and text.count("call_pair") == 1
    assert text.count("`model-routing select-pair") == 1


def test_the_link_is_the_lesson_that_holds_harvey_s_two_gaps():
    says("For Harvey [the orchestrator gets the strong model]")
    assert PARAGRAPH.count("](") == 1 and PARAGRAPH.endswith(f"]({ANCHOR}).")
    note = read("research/production-lessons.md")
    lesson = note.split(f"\n### {LESSON}\n", 1)[1].split("\n### ", 1)[0]
    [result] = [line for line in lesson.splitlines() if line.startswith("- Result: ")]
    assert "the gap between the highest- and lowest-scoring roots averaged about 38 percentage points" in result
    assert "the corresponding gap between sub-agent models averaged about 8 points" in result
    # the paragraph quotes nothing, so the note alone holds the quotes
    assert '"' not in PARAGRAPH


def test_the_command_and_its_two_options_are_the_parser_s():
    says("`model-routing select-pair TASK --root MODEL ... --leaf MODEL ...`")
    parser = _build_parser()
    [sub] = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    pair = sub.choices["select-pair"]
    options = {o: a for a in pair._actions for o in a.option_strings}
    for flag in ("--root", "--leaf"):
        assert options[flag].metavar == "MODEL" and options[flag].required and options[flag].nargs == "+"
    # TASK is its one positional, and no other option is required
    assert [a.dest for a in pair._actions if not a.option_strings] == ["task"]
    assert {o for o, a in options.items() if a.required} == {"--root", "--leaf"}


# --- its claims, each beside its words ------------------------------------------------------------

def test_a_pair_is_admitted_only_on_its_own_runs(tmp_path):
    says("admits `<root>+<leaf>` only on its own runs")
    data = select_pair(make(tmp_path))
    found = by_id(data)
    assert list(found) == [f"{STRONG}+{LEAF}", f"{CHEAP}+{LEAF}"]
    # the cheap root and the leaf each clear the bar alone at 40 of 40, yet their pair has no run of its own
    saved = Stats.load(tmp_path / "stats.json")
    assert saved.get("t", CHEAP) == saved.get("t", LEAF) == (N, N)
    assert (found[f"{CHEAP}+{LEAF}"]["trials"], found[f"{CHEAP}+{LEAF}"]["reason"]) == (0, "insufficient_samples")
    assert (found[f"{STRONG}+{LEAF}"]["successes"], found[f"{STRONG}+{LEAF}"]["trials"]) == (N - 1, N)
    assert found[f"{STRONG}+{LEAF}"]["reason"] == "passes"
    # so the dearer pair is the primary, though the cheap one costs less at the task's sizes
    assert (data["primary"], data["fallbacks"]) == (f"{STRONG}+{LEAF}", [])
    assert found[f"{CHEAP}+{LEAF}"]["list_cost"] < found[f"{STRONG}+{LEAF}"]["list_cost"]


def test_each_side_is_priced_at_its_tokens_from_the_four_keys_of_a_results_row(tmp_path):
    # v1.682 (row PROD1k) cut `at its tokens there` from these words to make room for the budgets clause
    says("each side priced from a results row's `root_input_tokens`, `root_output_tokens`, "
         "`leaf_input_tokens` and `leaf_output_tokens`")
    pair = f"{STRONG}+{LEAF}"
    # by hand: the root at 1,200 and 300 tokens, (1200 * 10 + 300 * 30) / 1e6 = 0.021, the leaf at 5,000 and 800,
    # (5000 * 0.1 + 800 * 0.3) / 1e6 = 0.00074
    assert abs(by_id(select_pair(make(tmp_path / "sides")))[pair]["list_cost"] - 0.02174) < 1e-12
    # with no side keys each side is priced at the task's 1,000 and 200 tokens: 0.016 + 0.00016
    assert abs(by_id(select_pair(make(tmp_path / "none", sides=False)))[pair]["list_cost"] - 0.01616) < 1e-12
    saved = Stats.load(tmp_path / "sides" / "stats.json")
    assert saved.get("t", pair) == (N - 1, N)


def router_for(d):
    return Router(Registry.load(d / "models.json"), load_tasks(d / "tasks.json"), Stats.load(d / "stats.json"))


def test_the_executor_runs_the_harness_on_the_pair(tmp_path):
    # `your harness` until v1.682 (row PROD1k), which says `the harness`, the one of the paragraph's lead
    says("`Executor.call_pair` runs the harness on the pair")
    make(tmp_path)
    router = router_for(tmp_path)
    calls = []

    def harness(root, leaf, messages):
        calls.append((root, leaf, messages))
        return {"text": "report", **SIDES}

    monitor = Monitor()
    result = Executor(router, FakeProvider({}), monitor=monitor).call_pair("t", [STRONG, CHEAP], [LEAF], MESSAGES,
                                                                           harness)
    assert calls == [(STRONG, LEAF, MESSAGES)]
    assert (result.text, result.model, result.decision.primary) == ("report", f"{STRONG}+{LEAF}", f"{STRONG}+{LEAF}")
    [record] = monitor.records
    assert record["model"] == f"{STRONG}+{LEAF}" and {k: record[k] for k in SIDES} == SIDES


def test_the_pair_is_held_and_settled_on_your_budgets(tmp_path):
    says("runs the harness on the pair, held and settled on your budgets")
    # no side keys, so the hold is the pair's estimate at the task's 1,000 and 200 tokens: 0.016 + 0.00016;
    # the harness returns the side tokens, so the settle is 0.021 + 0.00074 (7 v1.681)
    make(tmp_path, sides=False)
    ledger = BudgetLedger([Budget("cap", 1.0, "warn")])
    held = []

    def harness(root, leaf, messages):
        held.append(ledger.held_usd("cap"))
        return {"text": "report", **SIDES}

    monitor = Monitor()
    ex = Executor(router_for(tmp_path), FakeProvider({}), monitor=monitor, ledger=ledger)
    result = ex.call_pair("t", [STRONG, CHEAP], [LEAF], MESSAGES, harness)
    assert result.model == f"{STRONG}+{LEAF}" and len(held) == 1 and abs(held[0] - 0.01616) < 1e-12
    [record] = monitor.records
    assert abs(record["cost_usd"] - 0.02174) < 1e-12
    assert ledger.spent_usd("cap") == record["cost_usd"] and ledger.held_usd("cap") == 0.0


def test_a_refuse_budget_under_the_estimate_refuses_the_pair_before_the_harness(tmp_path):
    says("held and settled on your budgets")
    make(tmp_path, sides=False)
    ledger = BudgetLedger([Budget("cap", 0.01, "refuse")])
    calls = []

    def harness(root, leaf, messages):
        calls.append((root, leaf))
        return {"text": "report", **SIDES}

    ex = Executor(router_for(tmp_path), FakeProvider({}), monitor=Monitor(), ledger=ledger)
    with pytest.raises(BudgetExceeded):
        ex.call_pair("t", [STRONG, CHEAP], [LEAF], MESSAGES, harness)
    assert calls == [] and ledger.spent_usd("cap") == 0.0 and ledger.held_usd("cap") == 0.0


# --- DESIGN ---------------------------------------------------------------------------------------

def test_the_pointer_names_each_subsection_that_states_a_claim():
    says("(`DESIGN.md` 4.3, 5.2, 7 and 10).")
    design = read("DESIGN.md")
    starts = {"4.3": "### 4.3 ", "5.2": "### 5.2 ", "7": "## 7. ", "10": "## 10. "}
    ends = {"4.3": "### 4.4 ", "5.2": "### 5.3 ", "7": "## 8. ", "10": "## 11. "}
    part = {k: design[design.index("\n" + v):design.index("\n" + ends[k], design.index("\n" + v))]
            for k, v in starts.items()}
    assert "\n- v1.672 a pair's side tokens from a results row (row DEL1bb" in part["4.3"]
    assert "\n- v1.670 a root and sub-agent pair (row DEL1a" in part["5.2"]
    assert "\n- v1.671 each side at its tokens inside the pair (row DEL1ba" in part["5.2"]
    assert "\n- v1.678 a pair through the executor (row DEL1e, 5.2 v1.670): `.call_pair(" in part["7"]
    # v1.682 (row PROD1k): the budgets clause is 7 v1.681's
    assert "\n- v1.681 a pair call under a budget ledger (row DEL1g, 7 v1.678, v1.595 to v1.598): " in part["7"]
    assert "\n- v1.682 README pair paragraph and budgets (row PROD1k, " in part["5.2"]
    assert "\n- v1.676 `select-pair TASK --root MODEL [MODEL ...] --leaf MODEL [MODEL ...]" in part["10"]
    assert "\n- v1.680 README pair route (row PROD1j; " in part["5.2"]
    # review iter-538 should-fix 2: 10 v1.676's Not-in-this-version clause names the version that adds it
    assert "README's paragraph on the pair route (row PROD1j, which v1.680 adds in 5.2); " in part["10"]
    assert "README's paragraph on the pair route (row PROD1j);" not in design
