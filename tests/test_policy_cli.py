"""DESIGN 10, 13.7 and 5.2 v1.625 (row POL1d): a tenant's policy on the command line and in the docs.

`model-routing select --policy FILE` and `delegate --policy FILE` read one JSON object whose keys
are among the four `Policy` fields (5.1 v1.622), build `Policy(**object)` and pass it to `select`
(5.2 v1.622) or `decide_delegation` (13.1 v1.624). The file is read once the other files are loaded
and the model IDs checked; a value that is not an object, an unknown key or a value `Policy` refuses
exits 2 with one `error:` line naming the file. The output keeps its form, so the candidate table
names each ruled-out model's reason, and a ruled-out model's expired price never warns. With `{}`,
or without the option, every output is v1.624's bytes: the sha256 of every `select` and `delegate`
output over the shipped tasks in both flavors was taken on 1cb1645 (v1.624), and no README transcript,
evidence or research script or workflow passes the option, so every transcript and evidence file
keeps its bytes. README `## Running it in production` ends with a paragraph on the policy and
research/production-lessons.md's Harvey lesson says the library applies it today.
"""

import contextlib
import hashlib
import io
import json
import re
from datetime import date
from pathlib import Path

import pytest

from model_routing import DATA_DIR, Policy, Registry, Router, Stats, load_tasks
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 24)
REGION = "eu-west"


def row(model_id, family, price, regions=(REGION,), zdr=True, **extra):
    out = {"id": model_id, "family": family, "price_in": price, "price_out": 2 * price,
           "context_window": 100_000}
    if regions:
        out["regions"] = list(regions)
    if zdr is not None:
        out["zero_data_retention"] = zdr
    out.update(extra)
    return out


ROWS = [
    row("x/nowhere", "x", 0.05, regions=()),                         # cheapest, states no region
    row("y/cheap", "y", 0.1, price_valid_until="2026-01-31"),        # the disabled family, an expired price
    row("x/keep", "x", 0.3, zdr=None),                               # states no retention rule
    row("x/small", "x", 0.5),
    row("x/mid", "x", 1.0),
    row("x/big", "x", 2.0),
]
COUNTS = {"x/nowhere": 96, "y/cheap": 97, "x/keep": 99, "x/small": 95, "x/mid": 98, "x/big": 100}
TENANT = {"allowed_families": ["x"], "region": REGION, "require_zdr": True}
RULED_OUT = {"x/nowhere": "region_unavailable", "y/cheap": "policy_excluded", "x/keep": "zdr_required"}
ALLOWED = {"x/small", "x/mid", "x/big"}
WORK = ["--context-tokens", "2000", "--brief-tokens", "1000", "--result-tokens", "1000", "--fold-inline"]
EXPIRED = ("warning: list price of y/cheap was stated valid through 2026-01-31; check the vendor page "
           "and update the registry")
# v1.624 (1cb1645): sha256 of every select and delegate output over the shipped tasks, both flavors
SHIPPED_SHA256 = "ce921d5321e6d9e9378b73880623e19dadf1855015ca827a5dd68e8235a17bf5"


def run(argv):
    """`main(argv)` at TODAY as (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, today=TODAY)
    return code, out.getvalue(), err.getvalue()


@pytest.fixture
def files(tmp_path):
    (tmp_path / "models.json").write_text(json.dumps({"models": ROWS}), encoding="utf-8")
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [
        {"name": "t", "bar": 0.8, "min_samples": 30, "expected_input_tokens": 1000,
         "expected_output_tokens": 200}]}), encoding="utf-8")
    stats = Stats()
    for model_id, successes in COUNTS.items():
        stats.add("t", model_id, successes, 100)
    stats.save(tmp_path / "stats.json")
    return tmp_path


def base(d):
    return ["--registry", str(d / "models.json"), "--tasks", str(d / "tasks.json"),
            "--stats", str(d / "stats.json")]


def policy_file(d, value, name="policy.json"):
    path = d / name
    path.write_text(value if isinstance(value, str) else json.dumps(value), encoding="utf-8")
    return str(path)


def router(d):
    return Router(Registry.load(d / "models.json"), load_tasks(d / "tasks.json"), Stats.load(d / "stats.json"))


def table_reasons(text):
    """model -> reason from a candidate table (the last column)."""
    rows = [line.split() for line in text.splitlines() if line.split() and line.split()[0] in COUNTS]
    return {cells[0]: cells[-1] for cells in rows}


# --- the option ----------------------------------------------------------------------------------

@pytest.mark.parametrize("command", ["select", "delegate"])
def test_each_command_names_policy_file_in_its_help(command, capsys):
    with pytest.raises(SystemExit) as stop:
        main([command, "--help"], today=TODAY)
    assert stop.value.code == 0
    assert "--policy FILE" in capsys.readouterr().out


@pytest.mark.parametrize("flavor, primary", [("cost_effective", "x/small"), ("cost_blind", "x/big")])
def test_a_tenant_in_one_region_with_one_family_disabled_gets_the_cheapest_allowed_route(files, flavor, primary):
    path = policy_file(files, TENANT)
    code, out, err = run(["select", "t", "--flavor", flavor, "--policy", path, "--json", *base(files)])
    assert (code, err) == (0, "")       # y/cheap's expired price is not read: the policy rules it out
    decision = json.loads(out)
    assert decision["primary"] == primary and set(decision["fallbacks"]) == ALLOWED - {primary}  # nit 1
    assert {c["model_id"]: c["reason"] for c in decision["candidates"] if not c["eligible"]} == RULED_OUT
    expected = router(files).select("t", flavor=flavor, policy=Policy(**TENANT))
    assert out == json.dumps(expected.to_dict(), indent=2) + "\n"
    code, text, err = run(["select", "t", "--flavor", flavor, "--policy", path, *base(files)])
    assert (code, err) == (0, "") and f"primary:   {primary}\n" in text
    reasons = table_reasons(text)
    assert {m: reasons[m] for m in RULED_OUT} == RULED_OUT
    assert all(reasons[m] == "passes" for m in ALLOWED)


def test_without_a_policy_the_cheapest_model_wins_and_its_expired_price_warns(files):
    code, out, err = run(["select", "t", *base(files)])
    assert code == 0 and "primary:   x/nowhere\n" in out and "fallbacks: y/cheap, x/keep\n" in out
    assert err == EXPIRED + "\n"


def test_an_empty_object_is_no_policy(files):
    for argv in (["select", "t"], ["select", "t", "--json"], ["select", "t", "--flavor", "cost_blind"],
                 ["delegate", "t", "--parent", "y/cheap", *WORK], ["delegate", "t", "--parent", "x/big", *WORK, "--json"]):
        assert run(argv + ["--policy", policy_file(files, {})] + base(files)) == run(argv + base(files))


def test_an_allow_list_that_names_no_route_exits_3_with_the_table(files):
    path = policy_file(files, {"allowed_routes": ["nope/none"]})
    code, out, err = run(["select", "t", "--policy", path, *base(files)])
    assert (code, out) == (3, "")
    assert err.startswith("error: ") and set(table_reasons(err).values()) == {"policy_excluded"}
    assert len(table_reasons(err)) == len(ROWS) and "warning" not in err


# --- a bad file ----------------------------------------------------------------------------------

BAD = [
    ("[]", "expected a JSON object of policy keys, got array"),
    ('"eu-west"', "expected a JSON object of policy keys, got string"),
    ("3", "expected a JSON object of policy keys, got number"),
    ("true", "expected a JSON object of policy keys, got boolean"),
    ("null", "expected a JSON object of policy keys, got null"),
    ('{"regoin": "eu-west", "zdr": true, "region": 3}',
     "unknown policy keys ['regoin', 'zdr']; a policy holds allowed_routes, allowed_families, region and require_zdr"),
    ('{"region": 3}', "region must be None or a non-empty string, got 3"),
    ('{"region": ""}', "region must be None or a non-empty string, got ''"),
    ('{"require_zdr": 1}', "require_zdr must be a bool, got 1"),
    ('{"allowed_routes": "x/small"}', "allowed_routes must be None or a list or tuple of non-empty strings, got 'x/small'"),
    ('{"allowed_families": [""]}', "allowed_families must be None or a list or tuple of non-empty strings, got ['']"),
]


@pytest.mark.parametrize("command", ["select", "delegate"])
@pytest.mark.parametrize("text, message", BAD, ids=[t for t, _ in BAD])
def test_a_bad_policy_file_exits_2_with_one_line_naming_it(files, command, text, message):
    path = policy_file(files, text)
    argv = ["select", "t"] if command == "select" else ["delegate", "t", "--parent", "x/big", *WORK]
    code, out, err = run(argv + ["--policy", path] + base(files))
    assert (code, out) == (2, "")
    assert err == f"error: {path}: {message}\n"


@pytest.mark.parametrize("text", ["", "{", "{'region': 'eu-west'}"])
def test_bad_json_exits_2_with_one_line(files, text):
    code, out, err = run(["select", "t", "--policy", policy_file(files, text), *base(files)])
    assert (code, out) == (2, "") and err.startswith("error: ") and err.count("\n") == 1


def test_a_missing_policy_file_exits_2_with_one_line(files):
    missing = str(files / "absent.json")
    for argv in (["select", "t"], ["delegate", "t", "--parent", "x/big", *WORK]):
        code, out, err = run(argv + ["--policy", missing] + base(files))
        assert (code, out) == (2, "") and err.startswith("error: ") and err.count("\n") == 1
        assert "absent.json" in err


def test_the_model_ids_are_checked_before_the_policy_file_is_read(files):
    bad = policy_file(files, "[]")
    code, out, err = run(["select", "t", "--exclude", "nope/x", "--policy", bad, *base(files)])
    assert (code, out, err) == (2, "", "error: unknown model: 'nope/x'\n")
    code, out, err = run(["select", "t", "--generator", "nope/g", "--policy", bad, *base(files)])  # nit 3
    assert (code, out, err) == (2, "", "error: unknown model: 'nope/g'\n")
    code, out, err = run(["delegate", "t", "--parent", "nope/x", *WORK, "--policy", bad, *base(files)])
    assert (code, out, err) == (2, "", "error: unknown model: 'nope/x'\n")


# --- delegate --------------------------------------------------------------------------------------

@pytest.mark.parametrize("parent, reason", [("y/cheap", "parent_policy_excluded"),
                                            ("x/nowhere", "parent_region_unavailable"),
                                            ("x/keep", "parent_zdr_required")])
def test_delegate_names_the_parent_the_policy_rules_out(files, parent, reason):
    path = policy_file(files, TENANT)
    code, out, err = run(["delegate", "t", "--parent", parent, *WORK, "--policy", path, "--json", *base(files)])
    assert code == 0
    decision = json.loads(out)
    assert (decision["mode"], decision["reason"]) == ("delegate", reason) and decision["model"] in ALLOWED
    expected = router(files).decide_delegation(
        "t", parent, "cost_effective", context_tokens=2000, brief_tokens=1000, result_tokens=1000,
        inline_separate_call=False, policy=Policy(**TENANT))
    assert out == json.dumps(expected.to_dict(), indent=2) + "\n"
    code, text, err = run(["delegate", "t", "--parent", parent, *WORK, "--policy", path, *base(files)])
    assert code == 0 and f"reason:              {reason}\n" in text and "mode:                delegate\n" in text
    # v1.411: the parent's expired price warns on every run, a policy that rules it out included
    assert err == (EXPIRED + "\n" if parent == "y/cheap" else "")


def test_without_a_policy_the_same_parent_works_inline(files):
    code, out, _ = run(["delegate", "t", "--parent", "y/cheap", *WORK, *base(files)])
    assert code == 0 and "mode:                inline\n" in out


def test_delegate_with_no_allowed_route_exits_3_with_the_delegates_table(files):
    path = policy_file(files, {"allowed_routes": ["nope/none"]})
    code, out, err = run(["delegate", "t", "--parent", "x/big", *WORK, "--policy", path, *base(files)])
    assert (code, out) == (3, "")
    assert err.startswith("error: ") and set(table_reasons(err).values()) == {"policy_excluded"}


# --- no policy keeps every byte --------------------------------------------------------------------

def shipped_digest(extra=()):
    """sha256 over every `select` and `delegate` output (text and --json) on the shipped files, each
    shipped task in both flavors, run in a directory with no stats.json."""
    tasks = [t["name"] for t in json.loads((DATA_DIR / "example_tasks.json").read_text(encoding="utf-8"))["tasks"]]
    digest = hashlib.sha256()
    for task in tasks:
        for flavor in ("cost_effective", "cost_blind"):
            for argv in (["select", task, "--flavor", flavor],
                         ["delegate", task, "--parent", "anthropic/claude-opus-5.5", "--context-tokens", "60000",
                          "--brief-tokens", "2000", "--result-tokens", "1000", "--flavor", flavor]):
                for json_flag in ([], ["--json"]):
                    code, out, err = run(argv + json_flag + list(extra))
                    digest.update(f"{code}\n{out}\n{err}\n".encode("utf-8"))
    return digest.hexdigest()


def test_no_policy_and_an_empty_one_keep_every_shipped_output_of_v1_624(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert shipped_digest() == SHIPPED_SHA256
    assert shipped_digest(["--policy", policy_file(tmp_path, {})]) == SHIPPED_SHA256


def test_no_readme_transcript_script_or_workflow_passes_a_policy():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    commands = [line for line in readme.splitlines() if line.startswith("$ model-routing")]
    # review iter-477 nit 2: and the indented `model-routing ...` instruction lines
    told = [line for line in readme.splitlines() if line.lstrip().startswith("model-routing ")]
    assert len(commands) >= 12 and len(told) >= 3 and not [c for c in commands + told if "--policy" in c]
    scripts = [p for folder in ("evidence", "research", ".github") for p in (ROOT / folder).rglob("*")
               if p.is_file() and p.suffix in (".py", ".yml", ".yaml", ".sh")]
    assert len(scripts) >= 20
    assert [str(p.relative_to(ROOT)) for p in scripts if "--policy" in p.read_text(encoding="utf-8")] == []


# --- the docs --------------------------------------------------------------------------------------

POLICY_PARAGRAPH = (
    "A tenant's rules hold whatever a route costs. A `Policy(allowed_routes=None, allowed_families=None, "
    "region=None, require_zdr=False)`, passed as `policy=` to `select`, `Executor.call` or "
    "`decide_delegation`, or as a JSON object of those keys in a file to `model-routing select --policy FILE` "
    "or `delegate --policy FILE`, rules out before cost every route outside the allowed route IDs or "
    "families, every model whose `models.json` row does not list `region` in its `regions`, and, with "
    "`require_zdr`, every model whose row does not state `\"zero_data_retention\": true`, so the primary, "
    "each fallback, a cascade's legs, a procedure's model, a budget's downgrade, a shadow call and a "
    "delegate stay inside the allowed set, and a parent the policy rules out does not work inline. The "
    "candidate table names each ruled-out model's reason, `policy_excluded`, `region_unavailable` or "
    "`zdr_required`. A row's `regions` and `zero_data_retention` are what the registry's owner states, "
    "not a certification: the library checks only that the row states them, and a value a row leaves "
    "out fails closed. On one shared `Executor` each call may carry its own tenant's policy.")  # should-fix 1
HARVEY_LINE = (
    "- In this library: from v1.622 a tenant's `Policy`, its allowed route IDs and model families, the "
    "region its calls must be served in and whether they need zero data retention, rules out every model "
    "a route reaches before cost, in `select`, and from v1.623 and v1.624 in the executor and the "
    "delegation decision, so no primary, fallback, cascade leg, shadow call or sub-agent leaves the "
    "allowed set, and a parent model the policy rules out does not work inline; from v1.625 "
    "`select --policy FILE` and `delegate --policy FILE` read one from a JSON file. A registry row's "
    "regions and retention are what the registry's owner states, not a certification, and a value a "
    "row leaves out fails closed. The executor still moves to the next model of the route when a call "
    "fails or the caller's check rejects its answer, and a task can exclude model families. From v1.639 "
    "a call can pin its route: `Executor.call` with `pin_route` and a `pinned_by` tag skips the ranking "
    "but keeps the hard checks, runs a route under the bar only with `allow_below_bar=True`, and logs the "
    "tag on each record, with `basis` `pinned`.")  # v1.639, row PIN1a
OLD_HARVEY = ("- In this library: the executor moves to the next model of the route when a call fails or the "
              "caller's check rejects its answer, and a task can exclude model families. The changes: a policy "
              "of allowed models, families and region,")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def test_the_production_section_holds_the_paragraph_on_the_policy_after_the_threads_one():
    text = read("README.md")
    body = text.split("\n## Running it in production\n", 1)[1].split("\n## ", 1)[0]
    paragraphs = body.strip().split("\n\n")
    assert POLICY_PARAGRAPH in paragraphs and text.count(POLICY_PARAGRAPH) == 1  # v1.630: anchored on content
    assert paragraphs[paragraphs.index(POLICY_PARAGRAPH) - 1].startswith("One `Executor`, with its `Monitor` and `BudgetLedger`, ")
    assert "\u2014" not in POLICY_PARAGRAPH and "\u2013" not in POLICY_PARAGRAPH


def test_the_note_says_the_library_applies_the_policy_today():
    note = read("research/production-lessons.md")
    lesson = note.split("\n### Tenant policy and provider health are routing inputs\n", 1)[1].split("\n### ", 1)[0]
    [line] = [x for x in lesson.splitlines() if x.startswith("- In this library: ")]
    assert line == HARVEY_LINE and note.count(HARVEY_LINE) == 1
    assert OLD_HARVEY not in note and '"' not in HARVEY_LINE   # the note reads double-quoted text as a quote


def test_design_and_the_changelog_state_v1_625():
    design = read("DESIGN.md")
    ten = design.split("\n## 10. ", 1)[1].split("\n## 11. ", 1)[0]
    [synopsis] = [x for x in ten.splitlines() if x.startswith("- `select TASK ")]
    assert "[--slice S] [--policy FILE] [--registry PATH]" in synopsis
    assert ten.count("\n- v1.625 `select ... [--policy FILE]` (row POL1d): reads FILE as UTF-8 JSON, ") == 1
    assert ten.count("\n  - Tests (tests/test_policy_cli.py): ") == 1
    cli = design.split("\n### 13.7 CLI\n", 1)[1].split("\n### 13.8 ", 1)[0]
    assert "[--exclude MODEL ...] [--policy FILE] [--registry PATH]" in cli
    assert cli.count("\n- v1.625 `--policy FILE` (row POL1d; v1.624 took none): ") == 1
    assert "takes no `--policy`" not in design
    five2 = design.split("\n### 5.2 ", 1)[1].split("\n### 5.3 ", 1)[0]
    assert five2.count("the note's Harvey line are row POL1d (which v1.625 adds, 5.2, 10 and 13.7)") == 1
    assert five2.count("\n- v1.625 README and note (row POL1d): ") == 1
    seven = design.split("\n## 7. ", 1)[1].split("\n## 8. ", 1)[0]
    assert seven.count("the note's Harvey line (row POL1d, which v1.625 adds, 5.2, 10 and 13.7).") == 1
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.625 (")]
    assert line.startswith("- v1.625 (2026-11-24): spec, code, docs and tests (5.2, 7, 10, 13.7, row POL1d). ")
    assert re.search(r"not a certification\. ", line)
