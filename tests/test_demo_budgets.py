"""``model-routing demo --budgets FILE`` and exit code 4 (DESIGN 10 and 11 v1.599, row B1f)."""

import contextlib
import io
import json
import math
from pathlib import Path

import pytest
from model_routing import Budget, budget_report, load_budgets, load_records, run_demo
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
HEADERS = ["budget", "window", "mode", "limit_usd", "spent_usd", "budget_used_pct",
           "warn_records", "refused_records"]


def write_budgets(path, rows):
    path.write_text(json.dumps({"budgets": rows}), encoding="utf-8")
    return path


def run_cli(capsys, *argv):
    code = main(["demo", *argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def attempt_lines(path):
    return [line for line in path.read_text(encoding="utf-8").splitlines()
            if "budget_event" not in json.loads(line)]


def table(rows):
    """The block's table, formatted here apart from the CLI's own code."""
    cells = [HEADERS] + [[r["budget"], "total" if r["window"] is None else r["window"], r["mode"],
                          f"{r['limit_usd']:.6f}", f"{r['spent_usd']:.6f}",
                          f"{r['budget_used_pct']:.1f}", str(r["warn_records"]),
                          str(r["refused_records"])] for r in rows]
    widths = [max(len(row[i]) for row in cells) for i in range(len(HEADERS))]
    out = ["  ".join(c.ljust(w) for c, w in zip(row, widths)).rstrip() for row in cells]
    out.insert(1, "  ".join("-" * w for w in widths))
    return out


@pytest.fixture(scope="module")
def baseline(tmp_path_factory):
    """The demo without the option: its stdout lines, summary and log."""
    out = tmp_path_factory.mktemp("baseline") / "demo"
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        assert main(["demo", "--out", str(out)]) == 0
    return {"out": out, "stdout": buffer.getvalue(), "summary": run_demo(out.parent / "again"),
            "calls": (out / "calls.jsonl").read_text(encoding="utf-8")}


def test_design_states_the_option_the_exit_code_and_the_ledger():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    ten = text[text.index("## 10. CLI"):text.index("## 11. Demo")]
    assert ten.count("- `demo [--out DIR] [--budgets FILE]`: runs `run_demo` and prints its summary") == 1
    assert ten.count("  - v1.599 `--budgets FILE` (row B1f): reads FILE with `load_budgets` (4.6) "
                     "before the demo writes anything") == 1
    assert "; 4 a `BudgetExceeded` that ends a call of `demo --budgets` (v1.599)\n" in ten
    eleven = text[text.index("## 11. Demo"):text.index("## 12. ")]
    assert eleven.count("- v1.599 (row B1f): `run_demo(out_dir, seed=7, budgets=None)`. ") == 1
    four6 = text[text.index("### 4.6 Budgets"):text.index("## 5. ")]
    assert ("- Not in this version: the README paragraph (row B1d); the crossings and refusals in "
            "the monitor log and `budget_used_pct` are v1.598's (7 and 8, row B1e), and the "
            "`demo --budgets FILE` option with exit code 4 on a refusal v1.599's (10 and 11, row "
            "B1f).") in four6
    fourteen = text[text.index("## 14. "):text.index("## 15. ")]
    assert "row B1f" not in fourteen
    assert fourteen.count("v1.599's `demo --budgets` with exit code 4") == 1
    lines = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert sum(line.startswith("- v1.599 (2026-11-23): ") for line in lines) == 1


def test_main_names_exit_code_4():
    import model_routing.cli as cli
    assert cli.EXIT_BUDGET == 4
    assert "4 a budget refused a call" in cli.main.__doc__


def test_warn_budgets_keep_the_summary_and_attempt_lines_and_add_the_block(tmp_path, capsys,
                                                                            baseline):
    path = write_budgets(tmp_path / "budgets.json", [
        {"name": "demo-total", "limit_usd": 5.0, "mode": "warn"},
        {"name": "judge-day", "limit_usd": 2.0, "mode": "warn", "window": "day",
         "tags": {"suite": "demo"}},
        {"name": "hand-offs", "limit_usd": 0.001, "mode": "warn", "tags": {"delegated": "true"}},
    ])
    out = tmp_path / "demo"
    code, stdout, stderr = run_cli(capsys, "--out", str(out), "--budgets", str(path))
    assert (code, stderr) == (0, "")
    log = load_records(out / "calls.jsonl")
    rows = budget_report(log, load_budgets(path))
    assert [(r["budget"], r["window"], r["warn_records"], r["refused_records"]) for r in rows] == [
        ("demo-total", None, 2, 0), ("judge-day", "2026-01-01", 3, 0), ("hand-offs", None, 3, 0)]
    base = baseline["stdout"].splitlines()
    assert base[-1].startswith("log: ")
    expected = base[:-1] + ["", "budgets:"] + table(rows) + [f"log: {out / 'calls.jsonl'}"]
    assert stdout.splitlines() == expected
    # the attempt lines are v1.598's, in order; the budget records sit among them
    assert attempt_lines(out / "calls.jsonl") == baseline["calls"].splitlines()
    warns = [r for r in log if r.get("budget_event") == "warn"]
    assert len(warns) == 8 and all(r["ts"].startswith("2026-01-01T") for r in warns)
    spend = math.fsum(r["cost_usd"] for r in log if "budget_event" not in r)
    assert rows[0]["spent_usd"] == round(spend, 6) and 0.8 * 5.0 <= spend < 5.0


def test_run_demo_with_warn_budgets_returns_the_same_summary(tmp_path, baseline):
    budgets = (Budget("hand-offs", 0.001, "warn", tags={"delegated": "true"}),
               Budget("all", 0.01, "warn"))
    summary = run_demo(tmp_path / "demo", budgets=budgets)
    assert summary == baseline["summary"]
    assert summary["cost_effective"]["delegation"]["hand_off_calls"] == 1


def test_run_demo_with_budgets_none_writes_the_same_files(tmp_path, baseline):
    out = tmp_path / "demo"
    assert run_demo(out, budgets=None) == baseline["summary"]
    for name in ("calls.jsonl", "stats.json", "outcomes.jsonl", "models.json", "tasks.json"):
        assert (out / name).read_bytes() == (baseline["out"] / name).read_bytes(), name


@pytest.mark.parametrize("row, window", [
    ({"name": "cap", "limit_usd": 1.0, "mode": "refuse"}, None),
    ({"name": "cap", "limit_usd": 0.5, "mode": "refuse", "window": "day"}, "2026-01-01"),
    ({"name": "cap", "limit_usd": 1.0, "mode": "refuse", "strict": True}, None),
], ids=["total", "day", "strict"])
def test_a_refusal_ends_the_demo_with_exit_4_and_one_stderr_line(tmp_path, capsys, baseline,
                                                                    row, window):
    path = write_budgets(tmp_path / "budgets.json", [row])
    out = tmp_path / "demo"
    code, stdout, stderr = run_cli(capsys, "--out", str(out), "--budgets", str(path))
    assert (code, stdout) == (4, "")
    assert stderr.endswith("\n") and stderr.count("\n") == 1
    assert stderr.startswith(f"error: budget 'cap' ({row['limit_usd']!r} USD) ")
    log = load_records(out / "calls.jsonl")
    last = log[-1]
    assert (last["budget_event"], last["budget"], last["mode"]) == ("refused", "cap", "refuse")
    assert last.get("window") == window and last["unbounded"] is row.get("strict", False)
    assert sum("budget_event" in r for r in log) == 1
    assert f"refuses a call of {last['model']!r}" in stderr
    attempts = attempt_lines(out / "calls.jsonl")
    assert attempts == baseline["calls"].splitlines()[:len(attempts)]
    assert math.fsum(json.loads(line)["cost_usd"] for line in attempts) <= row["limit_usd"]


def test_a_downgrade_budget_moves_calls_and_records_the_moves(tmp_path, capsys):
    path = write_budgets(tmp_path / "budgets.json", [
        {"name": "blind", "limit_usd": 1.0, "mode": "downgrade"}])
    out = tmp_path / "demo"
    code, stdout, stderr = run_cli(capsys, "--out", str(out), "--budgets", str(path))
    log = load_records(out / "calls.jsonl")
    moved = [r for r in log if "budget_moves" in r]
    assert moved and all(m["budget"] == "blind" for r in moved for m in r["budget_moves"])
    if code == 4:
        assert stdout == "" and stderr.startswith("error: budget 'blind' (1.0 USD) ")
        assert log[-1]["budget_event"] == "refused"
    else:
        assert code == 0 and stderr == "" and "\nbudgets:\n" in stdout


def test_an_empty_budgets_list_prints_the_header_and_rule(tmp_path, capsys, baseline):
    path = write_budgets(tmp_path / "budgets.json", [])
    out = tmp_path / "demo"
    code, stdout, _ = run_cli(capsys, "--out", str(out), "--budgets", str(path))
    assert code == 0
    base = baseline["stdout"].splitlines()
    assert stdout.splitlines() == base[:-1] + ["", "budgets:"] + table([]) + [base[-1].replace(
        str(baseline["out"]), str(out))]
    assert (out / "calls.jsonl").read_text(encoding="utf-8") == baseline["calls"]


@pytest.mark.parametrize("content", [
    None,
    "{not json",
    json.dumps({"budgets": [{"name": "x", "limit_usd": 1.0, "mode": "refuse", "extra": 1}]}),
    json.dumps({"budgets": [{"name": "x", "limit_usd": 0, "mode": "refuse"}]}),
    json.dumps({"budgets": [{"name": "x", "limit_usd": 1.0, "mode": "warn"},
                            {"name": "x", "limit_usd": 2.0, "mode": "warn"}]}),
], ids=["missing", "bad-json", "unknown-key", "zero-limit", "repeated-name"])
def test_a_bad_budgets_file_exits_2_and_writes_nothing(tmp_path, capsys, content):
    path = tmp_path / "budgets.json"
    if content is not None:
        path.write_text(content, encoding="utf-8")
    out = tmp_path / "demo"
    code, stdout, stderr = run_cli(capsys, "--out", str(out), "--budgets", str(path))
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: ") and stderr.count("\n") == 1
    assert not out.exists()


@pytest.mark.parametrize("budgets", ["budgets.json", [{"name": "x"}], {"x": 1}],
                         ids=["str", "list-of-dict", "dict"])
def test_run_demo_refuses_a_bad_budgets_value_before_writing(tmp_path, budgets):
    out = tmp_path / "demo"
    with pytest.raises(ValueError):
        run_demo(out, budgets=budgets)
    assert not out.exists()
