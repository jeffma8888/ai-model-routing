"""DESIGN 10 and 5.2 v1.703 (row CACHE3d, the remainder of row CACHE3): `select --session-route` on the command
line and README's paragraph on a session's switch.

`model-routing select TASK --session-route ROUTE [--session-warm]` passes `session_route=ROUTE` and
`session_warm` to `select` (5.2 v1.695), so a session's next call is priced for the cache its last call warmed
without Python. The text output gains a `session:` line right after `below_bar:` and, under the policy `none`, a
`pick:` line for `stay_warm`; `--json` prints `RouteDecision.to_dict()`, which holds the v1.695 keys. Without the
two options every output keeps its v1.702 bytes: `V1_702_DIGEST` was computed on the package at e799012, before
v1.703, over this module's fixture. The fixture is tests/test_session_cache.py's two models, each measured at a
context of L tokens a call, all but 1,000 of them cached, so the warm route stays first past L = 11,000.
"""

import argparse
import hashlib
import json
from dataclasses import asdict, replace
from datetime import date
from pathlib import Path

import pytest

from test_readme_production import PRODUCTION, PRODUCTION_CAP, link_problems, paragraphs, size
from test_readme_walkthrough import command_problems
from test_session_cache import CHEAP, NEW, OUT, REGISTRY, TASK, TRIALS, WARM

from model_routing import NoModelClearsBar, Router, Stats
from model_routing.cli import _build_parser, _candidate_table, main

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 1, 1)
RETRY = replace(TASK, name="r", failure_policy="retry_same")
STRICT = replace(TASK, name="s", bar=0.99)
TASKS = (TASK, RETRY, STRICT)
MISS_LEAD = "A `Monitor(path, tasks=..., on_anomaly=...)` writes a `cache_miss` anomaly record "
BUDGET_LEAD = "A budget tracks what the executor spends and can warn, refuse or move a call. "
PARAGRAPH = (
    "A switch mid-session starts cold: `model-routing select TASK --session-route ROUTE --session-warm` prices "
    "each other route's cached reads at the input price, ROUTE's too without `--session-warm`, and gives "
    "`stay_warm` when ROUTE is first only because a switch costs more (`DESIGN.md` 5.2 and 10).")
# sha256 of the text and --json outputs of `select` without the options on this fixture, each task and flavor at
# contexts 10,999 and 11,001, taken on v1.702 (e799012), before v1.703
V1_702_DIGEST = "5698b1374632e0adf33ec3a53649407764b1d9fd8ef9618d8f2f81521a7ba572"


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def says(words):
    assert PARAGRAPH.count(words) == 1, words


def stats(context):
    """Each model, on each task, read ``context`` tokens a call, all but NEW of them cached, and wrote OUT."""
    held = Stats()
    for task in TASKS:
        for model_id in (WARM, CHEAP):
            held.add(task.name, model_id, 95, TRIALS, input_tokens=context * TRIALS,
                     output_tokens=OUT * TRIALS, cached_input_tokens=(context - NEW) * TRIALS)
    return held


def files(tmp_path, context):
    models = [dict(asdict(model), source="https://example.org/prices") for model in REGISTRY.models]
    registry = tmp_path / "models.json"
    registry.write_text(json.dumps({"version": "1", "as_of": "2026-01-01", "currency": "USD",
                                    "models": models}), encoding="utf-8")
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps({"tasks": [asdict(task) for task in TASKS]}), encoding="utf-8")
    stats_path = tmp_path / f"stats-{context}.json"
    stats(context).save(stats_path)
    return ["--registry", str(registry), "--tasks", str(tasks), "--stats", str(stats_path),
            "--priors", str(tmp_path / "no-priors.json")]


def run(capsys, argv):
    code = main(argv, today=TODAY)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def router(context):
    return Router(REGISTRY, {task.name: task for task in TASKS}, stats(context))


def header(decision, *lines):
    """The text output's lines down to ``below_bar:``, then ``lines``, the blank line and the table."""
    return "\n".join([f"task:      {decision.task}", f"flavor:    {decision.flavor}",
                      f"primary:   {decision.primary}", f"fallbacks: {', '.join(decision.fallbacks)}",
                      f"basis:     {decision.basis}", f"below_bar: {str(decision.below_bar).lower()}",
                      *lines, "", _candidate_table(decision.candidates, REGISTRY), ""])


# --- the parser -------------------------------------------------------------------------------------

def test_select_alone_takes_the_two_options():
    parser = _build_parser()
    [sub] = [a for a in parser._actions if isinstance(a, argparse._SubParsersAction)]
    options = {o: a for a in sub.choices["select"]._actions for o in a.option_strings}
    route, warm = options["--session-route"], options["--session-warm"]
    assert (route.metavar, route.default, route.required, route.nargs) == ("ROUTE", None, False, None)
    assert isinstance(warm, argparse._StoreTrueAction) and warm.default is False and not warm.required
    for name, command in sub.choices.items():
        if name != "select":
            flags = {o for a in command._actions for o in a.option_strings}
            assert "--session-route" not in flags and "--session-warm" not in flags, name


@pytest.mark.parametrize("command", [["select-pair", "t", "--root", WARM, "--leaf", CHEAP],
                                     ["delegate", "t", "--parent", WARM, "--context-tokens", "1",
                                      "--brief-tokens", "1", "--result-tokens", "1"]])
@pytest.mark.parametrize("extra", [["--session-route", WARM], ["--session-warm"]])
def test_select_pair_and_delegate_refuse_them(capsys, command, extra):
    code, out, err = run(capsys, command + extra)
    assert (code, out) == (2, "")
    assert err.startswith("usage: model-routing [-h]\n")   # argparse's top-level usage, as for any command
    assert err.endswith(f"error: unrecognized arguments: {' '.join(extra)}\n")


# --- what it passes -----------------------------------------------------------------------------------

@pytest.mark.parametrize("context, primary, pick", [(11_001, WARM, "stay_warm"), (10_999, CHEAP, None)])
def test_json_is_the_warm_session_s_decision(tmp_path, capsys, context, primary, pick):
    code, out, err = run(capsys, ["select", "t", "--json", "--session-route", WARM, "--session-warm"]
                         + files(tmp_path, context))
    assert (code, err) == (0, "")
    decision = router(context).select("t", session_route=WARM, session_warm=True)
    assert json.loads(out) == decision.to_dict() and out == json.dumps(decision.to_dict(), indent=2) + "\n"
    data = json.loads(out)
    assert (data["primary"], data.get("pick_reason"), data["session_pricing"]) == (primary, pick, "warm")
    assert list(data)[-2:] == ["session_pricing", "candidates"]


def test_without_session_warm_every_route_is_priced_cold(tmp_path, capsys):
    code, out, err = run(capsys, ["select", "t", "--json", "--session-route", WARM] + files(tmp_path, 11_001))
    assert (code, err) == (0, "")
    decision = router(11_001).select("t", session_route=WARM)
    assert json.loads(out) == decision.to_dict()
    data = json.loads(out)
    assert (data["primary"], data["session_pricing"], "pick_reason" in data) == (CHEAP, "conservative", False)
    # both routes cold: each one's cached-read part is 0, its context at the input price
    for row in data["candidates"]:
        assert row["cost_breakdown"]["cached_read_usd"] == 0.0, row["model_id"]


def test_a_route_no_registry_holds_makes_every_route_a_switch(tmp_path, capsys):
    code, out, err = run(capsys, ["select", "t", "--json", "--session-route", "fiction/gone", "--session-warm"]
                         + files(tmp_path, 11_001))
    assert (code, err) == (0, "")
    decision = router(11_001).select("t", session_route="fiction/gone", session_warm=True)
    assert json.loads(out) == decision.to_dict()
    assert decision.primary == CHEAP and decision.pick_reason is None and decision.session_pricing == "warm"
    assert all(c.cost_breakdown[1] == 0.0 for c in decision.candidates)


# --- the text output ----------------------------------------------------------------------------------

def test_the_text_output_under_the_policy_none(tmp_path, capsys):
    code, out, err = run(capsys, ["select", "t", "--session-route", WARM, "--session-warm"]
                         + files(tmp_path, 11_001))
    assert (code, err) == (0, "")
    decision = router(11_001).select("t", session_route=WARM, session_warm=True)
    assert decision.failure_policy == "none" and decision.pick_reason == "stay_warm"
    assert out == header(decision, f"session:   {WARM}, warm", "pick:      stay_warm")


@pytest.mark.parametrize("context, extra, line", [(10_999, ["--session-warm"], f"session:   {WARM}, warm"),
                                                  (11_001, [], f"session:   {WARM}, conservative")])
def test_no_pick_line_when_the_session_moves_nothing(tmp_path, capsys, context, extra, line):
    code, out, err = run(capsys, ["select", "t", "--session-route", WARM] + extra + files(tmp_path, context))
    assert (code, err) == (0, "")
    decision = router(context).select("t", session_route=WARM, session_warm=bool(extra))
    assert decision.pick_reason is None and decision.primary == CHEAP
    assert out == header(decision, line) and "\npick:" not in out


def test_the_text_output_under_retry_same(tmp_path, capsys):
    code, out, err = run(capsys, ["select", "r", "--session-route", WARM, "--session-warm"]
                         + files(tmp_path, 11_001))
    assert (code, err) == (0, "")
    decision = router(11_001).select("r", session_route=WARM, session_warm=True)
    assert (decision.primary, decision.pick_reason) == (WARM, "stay_warm")
    cost = f"${decision.expected_cost_per_success_usd:.6f}"
    assert out == header(decision, f"session:   {WARM}, warm",
                         f"policy:    retry_same, expected cost per success {cost} "
                         "(an estimate assuming independent retries)",
                         "pick:      stay_warm")
    assert out.count("\npick:") == 1


def test_exit_3_prints_the_candidates_so_priced(tmp_path, capsys):
    code, out, err = run(capsys, ["select", "s", "--session-route", WARM, "--session-warm"]
                         + files(tmp_path, 11_001))
    assert (code, out) == (3, "")
    with pytest.raises(NoModelClearsBar) as caught:
        router(11_001).select("s", session_route=WARM, session_warm=True)
    assert err == f"error: {caught.value}\n{_candidate_table(caught.value.candidates, REGISTRY)}\n"
    by_id = {c.model_id: c for c in caught.value.candidates}
    assert by_id[CHEAP].cost_breakdown[1] == 0.0 and by_id[WARM].cost_breakdown[1] > 0.0


# --- bad options ------------------------------------------------------------------------------------

def test_an_empty_route_is_a_usage_error(tmp_path, capsys):
    code, out, err = run(capsys, ["select", "t", "--session-route", ""] + files(tmp_path, 11_001))
    assert (code, out) == (2, "")
    assert err.startswith("usage: model-routing select ")
    assert err.splitlines()[-1] == "error: argument --session-route: must be a non-empty route ID, got ''"


def test_session_warm_alone_exits_2_before_any_file_is_read(tmp_path, capsys):
    missing = ["--registry", str(tmp_path / "none.json"), "--tasks", str(tmp_path / "none.json")]
    code, out, err = run(capsys, ["select", "t", "--session-warm"] + missing)
    assert (code, out) == (2, "")
    assert err == ("error: --session-warm needs --session-route: only the route a session's last call ran on "
                   "can be warm\n")


def test_session_warm_alone_with_good_files_exits_2_the_same(tmp_path, capsys):
    code, out, err = run(capsys, ["select", "t", "--session-warm"] + files(tmp_path, 11_001))
    assert (code, out) == (2, "")
    assert err.splitlines() == ["error: --session-warm needs --session-route: only the route a session's last "
                                "call ran on can be warm"]


def test_a_route_with_no_value_is_argparse_s_error(tmp_path, capsys):
    code, out, err = run(capsys, ["select", "t"] + files(tmp_path, 11_001) + ["--session-route"])
    assert (code, out) == (2, "")
    assert err.splitlines()[-1] == "error: argument --session-route: expected one argument"


# --- without the options --------------------------------------------------------------------------

def outputs_without_a_session(tmp_path, capsys):
    """Every text and --json output of `select` on this fixture without the two options, in a fixed order."""
    parts = []
    for context in (10_999, 11_001):
        paths = files(tmp_path, context)
        for task in TASKS:
            for flavor in ("cost_effective", "cost_blind"):
                for extra in ([], ["--json"]):
                    code, out, err = run(capsys, ["select", task.name, "--flavor", flavor] + extra + paths)
                    parts.append(f"{context} {task.name} {flavor} {extra} {code}\n{out}\x00{err}\x00")
    return "".join(parts)


def test_without_the_options_every_output_keeps_its_v1_702_bytes(tmp_path, capsys):
    joined = outputs_without_a_session(tmp_path, capsys)
    assert "session" not in joined and "stay_warm" not in joined
    assert hashlib.sha256(joined.encode("utf-8")).hexdigest() == V1_702_DIGEST


# --- README -------------------------------------------------------------------------------------------

def test_the_paragraph_follows_the_cache_miss_one_inside_the_cap():
    text = read("README.md")
    found = paragraphs(text, PRODUCTION)
    # placed by its neighbours (v1.655, row T30); tests/test_readme_trim.py names the section's last paragraph
    assert text.count(PARAGRAPH) == 1 and found.count(PARAGRAPH) == 1
    at = found.index(PARAGRAPH)
    assert found[at - 1].startswith(MISS_LEAD) and found[at + 1].startswith(BUDGET_LEAD)
    assert len(PARAGRAPH.encode("utf-8")) == 296 <= 300
    assert size(text, PRODUCTION) <= PRODUCTION_CAP == 30_000
    assert "\u2014" not in PARAGRAPH and "\u2013" not in PARAGRAPH and "```" not in PARAGRAPH
    assert "](" not in PARAGRAPH and link_problems(text) == []


def test_its_command_is_the_parser_s():
    command = "model-routing select TASK --session-route ROUTE --session-warm"
    says(f"`{command}`")
    # review iter-564 should-fix 1: the real parser reads it, a fictional task and route in place of TASK and ROUTE,
    # since tests/test_readme_walkthrough.py's command_problems reads options only
    words = command.split()[1:]
    args = _build_parser().parse_args([{"TASK": "t", "ROUTE": WARM}.get(w, w) for w in words])
    assert (args.command, args.task, args.session_route, args.session_warm) == ("select", "t", WARM, True)
    [sub] = [a for a in _build_parser()._actions if isinstance(a, argparse._SubParsersAction)]
    options = {o: a for a in sub.choices["select"]._actions for o in a.option_strings}
    assert options["--session-route"].metavar == words[words.index("--session-route") + 1] == "ROUTE"
    assert [a.dest for a in sub.choices["select"]._actions if not a.option_strings] == ["task"]
    assert command_problems(command.replace(" TASK", "")) == []
    # README named neither option before v1.703 (row CACHE3d); this paragraph names each where it says
    text = read("README.md")
    assert text.count("--session-route") == 1 and text.count("--session-warm") == 2
    assert text.count("stay_warm") == 1


def test_a_switch_prices_each_other_route_s_cached_reads_at_the_input_price(tmp_path, capsys):
    says("A switch mid-session starts cold: ")
    says("prices each other route's cached reads at the input price")
    code, out, _ = run(capsys, ["select", "t", "--json", "--session-route", WARM, "--session-warm"]
                       + files(tmp_path, 11_001))
    rows = {row["model_id"]: row for row in json.loads(out)["candidates"]}
    cheap, warm = REGISTRY.get(CHEAP), REGISTRY.get(WARM)
    assert code == 0 and rows[CHEAP]["cost_breakdown"]["cached_read_usd"] == 0.0
    assert rows[CHEAP]["cost_breakdown"]["uncached_input_usd"] == pytest.approx(11_001 * cheap.price_in / 1e6)
    assert rows[WARM]["cost_breakdown"]["cached_read_usd"] == pytest.approx((11_001 - NEW) * warm.price_cached_in / 1e6)


def test_route_s_too_without_session_warm(tmp_path, capsys):
    says("ROUTE's too without `--session-warm`")
    code, out, _ = run(capsys, ["select", "t", "--json", "--session-route", WARM] + files(tmp_path, 11_001))
    rows = {row["model_id"]: row for row in json.loads(out)["candidates"]}
    assert code == 0 and rows[WARM]["cost_breakdown"]["cached_read_usd"] == 0.0
    assert rows[WARM]["cost_breakdown"]["uncached_input_usd"] == pytest.approx(11_001 * REGISTRY.get(WARM).price_in / 1e6)


def test_stay_warm_only_when_a_switch_keeps_route_first(tmp_path, capsys):
    says("gives `stay_warm` when ROUTE is first only because a switch costs more")
    for context, pick in ((11_001, "stay_warm"), (10_999, None)):
        code, out, _ = run(capsys, ["select", "t", "--json", "--session-route", WARM, "--session-warm"]
                           + files(tmp_path, context))
        assert code == 0 and json.loads(out).get("pick_reason") == pick
        # without the session the cheap route is first at both lengths
        assert router(context).select("t").primary == CHEAP


# --- DESIGN and the changelog ---------------------------------------------------------------------------

def part(design, start, end):
    at = design.index("\n" + start)
    return design[at:design.index("\n" + end, at)]


def test_design_10_states_the_options():
    ten = part(read("DESIGN.md"), "## 10. ", "## 11. ")
    lines = ten.splitlines()
    assert lines[1].startswith("## 10. CLI ")
    assert lines[2].startswith("- `select TASK [--flavor cost_effective|cost_blind] [--generator MODEL] ")
    assert lines[2].count(" [--policy FILE] [--session-route ROUTE [--session-warm]] [--registry PATH] ") == 1
    [mine] = [x for x in lines if x.startswith("- v1.703 `select ... [--session-route ROUTE [--session-warm]]` "
                                               "(row CACHE3d, the remainder of row CACHE3, 5.2 v1.695): ")]
    assert lines[lines.index(mine) + 1].startswith("  - Order of checks, ")
    assert lines[lines.index(mine) - 1].startswith("  - Tests (tests/test_select_label_sources.py): ")
    for kept in ("`error: argument --session-route: must be a non-empty route ID, got ''`",
                 "`error: --session-warm needs --session-route: only the route a session's last call ran on can "
                 "be warm`",
                 "`session:   ROUTE, warm` with `--session-warm` or `session:   ROUTE, conservative` without it",
                 "`pick:      stay_warm`", "taken on v1.702 (e799012)"):
        assert ten.count(kept) == 1, kept
    for line in lines:
        assert len(line.encode("utf-8")) <= 6_000 and "\u2014" not in line and "\u2013" not in line


def test_design_5_2_states_the_paragraph_and_lifts_the_deferrals():
    design = read("DESIGN.md")
    five2 = part(design, "### 5.2 ", "### 5.3 ")
    lines = five2.splitlines()
    [mine] = [x for x in lines if x.startswith("- v1.703 README session pricing (row CACHE3d, the remainder of "
                                               "row CACHE3; ")]
    assert lines[lines.index(mine) - 1].startswith("- v1.694 README cache-miss check (row CACHE2c, ")
    for kept in ("right after the one on the cache-miss check (v1.694), before the first on budgets",
                 "The new paragraph is 296 bytes, the twelfth entry of tests/test_readme_trim.py's `LATER`",
                 "so the section is 28,641 bytes by the 12.8 measure, 1,359 under v1.629's 30,000-byte cap, "
                 "which stays",
                 "the section less `LATER` stays 20,343"):
        assert mine.count(kept) == 1, kept
    assert len(mine.encode("utf-8")) <= 6_000 and "\u2014" not in mine and "\u2013" not in mine
    # the deferrals that named this row name the version that adds it
    seven = part(design, "## 7. ", "## 8. ")
    assert five2.count("README's sentence (row CACHE3d, which v1.703 adds in 10 and 5.2)") == 1
    assert seven.count("README's sentence (row CACHE3d, which v1.703 adds in 10 and 5.2)") == 1
    assert "(row CACHE3d)" not in five2 and "(row CACHE3d)" not in seven
    assert five2.count("`select_pair` and `decide_delegation` pass no session, nor does any command but "
                       "`select` with `--session-route` (10 v1.703)") == 1


def test_the_changelog_states_the_version():
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.703 (")]
    assert line.startswith("- v1.703 (2026-11-28): spec, code and tests (5.2, 7, 10, row CACHE3d). ")
    assert line.count("so the section is 28,641 bytes, 1,359 under the 30,000-byte cap") == 1
    assert line.split("). ", 1)[1].count(". ") == 1   # two sentences after the lead (review iter-564 must-fix 1)
    assert len(line.encode("utf-8")) <= 600 and "\u2014" not in line and "\u2013" not in line
