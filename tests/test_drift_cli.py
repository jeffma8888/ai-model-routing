"""DESIGN 10 v1.634 (row M1c): the drift check on the command line.

`model-routing drift --log PATH --audits PATH [--window Nd] [--stats PATH] [--json]` prints the rows
of `drift_check` (8.3 v1.633) for the audited calls of the last N UTC days (default 30) of the logs,
the window ending with the command's date, `today`, against the stats file or, without `--stats`,
every audited call of the logs. `select ... --window Nd --log PATH --audits PATH` reads that window's
stats instead of `--stats`, so a route at 0.92 all-time and 0.70 in the window loses admission. Without
the options every `select` output is v1.633's bytes: the sha256 of every `select` output over the
shipped tasks in both flavors was taken on c3e0c6c (v1.633), and no README transcript, evidence or
research script or workflow passes `--window` or runs `drift`, so every transcript and evidence file
keeps its bytes.
"""

import contextlib
import hashlib
import io
import json
from datetime import date
from pathlib import Path

import pytest

from model_routing import DATA_DIR, Stats, drift_check, load_tasks
from model_routing.cli import main
from model_routing.monitor import audited_results, load_audits, load_logs
from model_routing.stats import calibrate_from_results, wilson_lower_bound

ROOT = Path(__file__).resolve().parents[1]
TODAY = date(2026, 11, 24)
SINCE, UNTIL = "2026-10-26T00:00:00+00:00", "2026-11-25T00:00:00+00:00"   # 30d ending TODAY
OLD, NEW = "2026-10-01T12:00:00.000+00:00", "2026-11-20T12:00:00.000+00:00"
CHEAP, MID = "x/cheap", "x/mid"
# v1.633 (c3e0c6c): sha256 of every select output over the shipped tasks, both flavors, text and --json
SHIPPED_SHA256 = "fb20a8bfad8cd31441e018ab8538d34ec9e011b839258652acbd58bd32d65a99"


def run(argv):
    """`main(argv)` at TODAY as (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv, today=TODAY)
    return code, out.getvalue(), err.getvalue()


def rec(call_id, model, ts, task="judge"):
    return {"ts": ts, "call_id": call_id, "task": task, "flavor": "cost_effective", "model": model,
            "family": model.split("/")[0], "attempt": 0, "final": True, "outcome": "ok", "error": None,
            "latency_ms": 5.0, "input_tokens": 1000, "output_tokens": 200, "cost_usd": 0.001,
            "routing_cost_usd": 0.001, "below_bar": False, "basis": "measured", "tags": {}, "slice": None}


def calls(prefix, model, ts, right, wrong):
    """`right + wrong` calls of `model` at `ts` and their audits, the first `right` correct."""
    records = [rec(f"{prefix}{k}", model, ts) for k in range(right + wrong)]
    return records, {r["call_id"]: k < right for k, r in enumerate(records)}


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return str(path)


@pytest.fixture
def files(tmp_path):
    """A cheap and a mid route on one task; all-time 460/500 and 470/500 in stats.json; in the log
    the cheap route's 40 calls in the window are 28 right (0.70), the mid route's 40 all right, and
    60 older calls of the cheap route all right."""
    (tmp_path / "models.json").write_text(json.dumps({"models": [
        {"id": CHEAP, "family": "x", "price_in": 0.1, "price_out": 0.2, "context_window": 100_000},
        {"id": MID, "family": "x", "price_in": 1.0, "price_out": 2.0, "context_window": 100_000}]}),
        encoding="utf-8")
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [
        {"name": "judge", "bar": 0.8, "min_samples": 30, "expected_input_tokens": 1000,
         "expected_output_tokens": 200}]}), encoding="utf-8")
    stats = Stats()
    stats.add("judge", CHEAP, 460, 500)
    stats.add("judge", MID, 470, 500)
    stats.save(tmp_path / "stats.json")
    records, audits = [], {}
    for part in (calls("old", CHEAP, OLD, 60, 0), calls("c", CHEAP, NEW, 28, 12), calls("m", MID, NEW, 40, 0)):
        records += part[0]
        audits.update(part[1])
    write_jsonl(tmp_path / "calls.jsonl", records)
    write_jsonl(tmp_path / "audits.jsonl", [{"call_id": k, "correct": v} for k, v in audits.items()])
    return tmp_path


def paths(d):
    return {"log": str(d / "calls.jsonl"), "audits": str(d / "audits.jsonl"), "stats": str(d / "stats.json"),
            "tasks": str(d / "tasks.json"), "registry": str(d / "models.json")}


def drift_argv(d, *extra, stats=True):
    p = paths(d)
    return (["drift", "--log", p["log"], "--audits", p["audits"], "--tasks", p["tasks"]]
            + (["--stats", p["stats"]] if stats else []) + list(extra))


def select_argv(d, *extra):
    p = paths(d)
    return ["select", "judge", "--registry", p["registry"], "--tasks", p["tasks"], "--stats", p["stats"]] + list(extra)


def window_stats(d, since=SINCE, until=UNTIL):
    p = paths(d)
    return calibrate_from_results(audited_results(load_logs([p["log"]]), load_audits(p["audits"]),
                                                  since=since, until=until))


# --- the options ---------------------------------------------------------------------------------

@pytest.mark.parametrize("command, shown", [("drift", ["--window Nd", "--stats PATH", "--audits PATH"]),
                                            ("select", ["--window Nd", "--log PATH", "--audits PATH"])])
def test_each_command_names_its_options_in_its_help(command, shown, capsys):
    with pytest.raises(SystemExit) as stop:
        main([command, "--help"], today=TODAY)
    assert stop.value.code == 0
    text = capsys.readouterr().out
    assert all(option in text for option in shown)


def test_delegate_gains_no_window(capsys):
    with pytest.raises(SystemExit):
        main(["delegate", "--help"], today=TODAY)
    assert "--window" not in capsys.readouterr().out


# --- drift ---------------------------------------------------------------------------------------

def test_drift_json_is_drift_check_on_the_stats_file_and_the_windows_stats_and_writes_no_file(files):
    before = sorted(p.name for p in files.iterdir())
    code, out, err = run(drift_argv(files, "--json"))
    assert (code, err) == (0, "")
    data = json.loads(out)
    assert list(data) == ["since", "until", "stats", "rows"]
    assert (data["since"], data["until"], data["stats"]) == (SINCE, UNTIL, paths(files)["stats"])
    expected = drift_check(Stats.load(files / "stats.json"), window_stats(files), load_tasks(files / "tasks.json"))
    assert data["rows"] == expected
    assert out == json.dumps({"since": SINCE, "until": UNTIL, "stats": paths(files)["stats"], "rows": expected},
                             indent=2) + "\n"
    assert sorted(p.name for p in files.iterdir()) == before


def test_a_route_at_0_92_all_time_and_0_70_in_the_window_is_flagged_and_loses_admission(files):
    code, out, _ = run(drift_argv(files, "--json"))
    rows = {r["route"]: r for r in json.loads(out)["rows"]}
    assert (rows[CHEAP]["all_time_successes"], rows[CHEAP]["all_time_trials"]) == (460, 500)
    assert (rows[CHEAP]["window_successes"], rows[CHEAP]["window_trials"]) == (28, 40)
    assert rows[CHEAP]["flag"] == "fell_below" and rows[MID]["flag"] is None
    code, out, _ = run(select_argv(files, "--json"))
    assert (code, json.loads(out)["primary"]) == (0, CHEAP)
    p = paths(files)
    code, out, err = run(select_argv(files, "--json", "--window", "30d", "--log", p["log"], "--audits", p["audits"]))
    decision = json.loads(out)
    assert (code, err, decision["primary"]) == (0, "", MID)
    [cheap] = [c for c in decision["candidates"] if c["model_id"] == CHEAP]
    assert cheap["passes"] is False and (cheap["successes"], cheap["trials"]) == (28, 40)


@pytest.mark.parametrize("json_flag", [[], ["--json"]])
def test_select_window_prints_what_select_stats_prints_on_the_windows_stats(files, json_flag):
    window_stats(files).save(files / "window.json")
    p = paths(files)
    on_file = run(["select", "judge", "--registry", p["registry"], "--tasks", p["tasks"],
                   "--stats", str(files / "window.json")] + json_flag)
    windowed = run(select_argv(files, "--window", "30d", "--log", p["log"], "--audits", p["audits"], *json_flag))
    assert windowed == on_file and windowed[0] == 0


def test_select_window_does_not_read_the_stats_file(files):
    (files / "stats.json").write_text("not json", encoding="utf-8")
    p = paths(files)
    code, out, err = run(select_argv(files, "--json", "--window", "30d", "--log", p["log"], "--audits", p["audits"]))
    assert (code, err, json.loads(out)["primary"]) == (0, "", MID)


def test_the_text_output_byte_for_byte(files):
    code, out, err = run(drift_argv(files))
    assert (code, err) == (0, "")
    lb = {(s, t): f"{wilson_lower_bound(s, t, 0.95):.3f}" for s, t in [(460, 500), (28, 40), (470, 500), (40, 40)]}
    width = max(len(v) for v in lb.values())
    assert width == 5
    lines = [
        f"since:    {SINCE}",
        f"until:    {UNTIL}",
        f"all_time: {paths(files)['stats']}",
        "",
        "task   route    all_time  all_time_lb  window  window_lb  bar  min_samples  flag",
        "-----  -------  --------  -----------  ------  ---------  ---  -----------  ----------",
        f"judge  x/cheap  460/500   {lb[460, 500]}        28/40   {lb[28, 40]}      0.8  30           fell_below",
        f"judge  x/mid    470/500   {lb[470, 500]}        40/40   {lb[40, 40]}      0.8  30           -",
    ]
    assert out == "\n".join(lines) + "\n"


def test_without_stats_the_all_time_side_is_every_audited_call_of_the_logs(files):
    code, out, err = run(drift_argv(files, "--json", stats=False))
    assert (code, err) == (0, "")
    data = json.loads(out)
    assert data["stats"] is None
    rows = {r["route"]: r for r in data["rows"]}
    assert (rows[CHEAP]["all_time_successes"], rows[CHEAP]["all_time_trials"]) == (88, 100)
    assert (rows[MID]["all_time_successes"], rows[MID]["all_time_trials"]) == (40, 40)
    assert data["rows"] == drift_check(window_stats(files, None, None), window_stats(files),
                                       load_tasks(files / "tasks.json"))
    code, text, _ = run(drift_argv(files, stats=False))
    assert text.splitlines()[2] == "all_time: every audited call of the logs"


def test_a_rise_is_flagged_once(tmp_path, files):
    """The mid route's 30 older calls all wrong: 40 of 70 all-time is below the bar, and 40 of 40 in
    the window clears it, so its one row says rose_above."""
    records, audits = calls("w", MID, OLD, 0, 30)
    log = write_jsonl(tmp_path / "more.jsonl", records)
    extra = write_jsonl(tmp_path / "audits-more.jsonl",
                        [{"call_id": k, "correct": v} for k, v in {**load_audits(files / "audits.jsonl"), **audits}.items()])
    p = paths(files)
    code, out, err = run(["drift", "--log", p["log"], "--log", log, "--audits", extra, "--tasks", p["tasks"], "--json"])
    assert (code, err) == (0, "")
    mid = [r for r in json.loads(out)["rows"] if r["route"] == MID]
    assert len(mid) == 1
    assert (mid[0]["all_time_successes"], mid[0]["all_time_trials"], mid[0]["flag"]) == (40, 70, "rose_above")


def test_the_default_window_is_30_days_and_the_option_sets_it(files):
    for extra, since, trials in (([], SINCE, 40), (["--window", "30d"], SINCE, 40),
                                 (["--window", "60d"], "2026-09-26T00:00:00+00:00", 100)):   # 60d holds the older calls too
        code, out, _ = run(drift_argv(files, "--json", *extra))
        data = json.loads(out)
        assert (code, data["since"], data["until"]) == (0, since, UNTIL)
        rows = {r["route"]: r for r in data["rows"]}
        assert rows[CHEAP]["window_trials"] == trials   # review iter-487 nit 1: each case


@pytest.mark.parametrize("ts, inside", [
    ("2026-11-24T00:00:00Z", True), ("2026-11-24T23:59:59.999Z", True),
    ("2026-11-23T23:59:59.999Z", False), ("2026-11-25T00:00:00Z", False),
    ("2026-11-24T20:00:00-08:00", False),          # 04:00 UTC on the 25th
    ("2026-11-24T05:00:00+08:00", False),          # 21:00 UTC on the 23rd
    ("2026-11-24T12:00:00", True),                 # no offset reads as UTC
])
def test_a_one_day_window_is_todays_utc_day(tmp_path, ts, inside):
    log = write_jsonl(tmp_path / "calls.jsonl", [rec("a", CHEAP, ts)])
    audits = write_jsonl(tmp_path / "audits.jsonl", [{"call_id": "a", "correct": True}])
    tasks = tmp_path / "tasks.json"
    tasks.write_text(json.dumps({"tasks": [{"name": "judge", "bar": 0.8, "min_samples": 1}]}), encoding="utf-8")
    code, out, err = run(["drift", "--log", log, "--audits", audits, "--tasks", str(tasks), "--window", "1d", "--json"])
    data = json.loads(out)
    assert (code, err) == (0, "")
    assert (data["since"], data["until"]) == ("2026-11-24T00:00:00+00:00", UNTIL)
    assert data["rows"][0]["window_trials"] == (1 if inside else 0)
    assert data["rows"][0]["all_time_trials"] == 1


def test_drift_exits_0_with_no_row_and_prints_the_header(tmp_path):
    log = write_jsonl(tmp_path / "calls.jsonl", [])
    audits = write_jsonl(tmp_path / "audits.jsonl", [])
    code, out, err = run(["drift", "--log", log, "--audits", audits])
    assert (code, err) == (0, "")
    assert out.splitlines()[4:] == ["task  route  all_time  all_time_lb  window  window_lb  bar  min_samples  flag",
                                    "----  -----  --------  -----------  ------  ---------  ---  -----------  ----"]


# --- refusals ------------------------------------------------------------------------------------

@pytest.mark.parametrize("text", ["0d", "30", "d", "-1d", "1.5d", "30 d", "30D", "+3d", " 3d", "3d ", "٣d"])
@pytest.mark.parametrize("command", ["drift", "select"])
def test_a_bad_window_is_a_usage_error(files, command, text):
    p = paths(files)
    argv = drift_argv(files) if command == "drift" else select_argv(files, "--log", p["log"], "--audits", p["audits"])
    code, out, err = run(argv + [f"--window={text}"])   # = form: argparse reads a bare -1d as an option
    assert (code, out) == (2, "")
    assert err.splitlines()[-1] == f"error: argument --window: must be a number of days such as 30d, got {text!r}"
    if not text.startswith("-"):
        assert run(argv + ["--window", text]) == (code, out, err)


@pytest.mark.parametrize("text", ["740000d", "99999999999d"])
def test_a_window_past_the_dates_python_holds_exits_2(files, text):
    code, out, err = run(drift_argv(files, "--window", text))
    assert (code, out, err) == (2, "", f"error: --window {text} reaches past the dates Python can hold\n")


@pytest.mark.parametrize("extra, message", [
    (["--window", "30d"], "error: --window needs --log and --audits: the window's stats come from the logs' audited calls"),
    (["--window", "30d", "--log", "L"], "error: --window needs --log and --audits: the window's stats come from the logs' audited calls"),
    (["--window", "30d", "--audits", "A"], "error: --window needs --log and --audits: the window's stats come from the logs' audited calls"),
    (["--log", "L"], "error: --log and --audits need --window: select reads them only for a window's stats"),
    (["--audits", "A", "--log", "L"], "error: --log and --audits need --window: select reads them only for a window's stats"),
])
def test_select_window_needs_both_files_and_they_need_it_before_any_file_is_read(tmp_path, extra, message):
    code, out, err = run(["select", "judge", "--registry", str(tmp_path / "missing.json")] + extra)
    assert (code, out, err) == (2, "", message + "\n")


def test_drift_needs_a_log_and_an_audits_file(files):
    p = paths(files)
    for argv in (["drift", "--audits", p["audits"]], ["drift", "--log", p["log"]]):
        code, out, err = run(argv)
        assert (code, out) == (2, "") and err.splitlines()[-1].startswith("error: the following arguments are required")


@pytest.mark.parametrize("command", ["drift", "select"])
@pytest.mark.parametrize("which", ["log", "audits"])
def test_a_missing_file_exits_2_with_one_line(files, command, which):
    p = {**paths(files), which: str(files / "missing.jsonl")}
    argv = (["drift", "--log", p["log"], "--audits", p["audits"], "--tasks", p["tasks"]] if command == "drift"
            else ["select", "judge", "--registry", p["registry"], "--tasks", p["tasks"], "--window", "30d",
                  "--log", p["log"], "--audits", p["audits"]])
    code, out, err = run(argv)
    assert (code, out) == (2, "") and err.count("\n") == 1 and err.startswith("error: ")
    assert "missing.jsonl" in err


def test_a_named_stats_file_that_is_missing_exits_2(files):
    code, out, err = run(drift_argv(files, stats=False) + ["--stats", str(files / "nope.json")])
    assert (code, out) == (2, "") and err.count("\n") == 1 and "nope.json" in err


def test_a_log_audited_results_refuses_exits_2_with_its_message(tmp_path, files):
    """A second final record of call c0, another model's, so `load_logs` keeps it (it repeats no
    record) and `audited_results` refuses the call (review iter-487 should-fix 1)."""
    p = paths(files)
    twice = write_jsonl(tmp_path / "twice.jsonl", [rec("c0", MID, NEW)])
    code, out, err = run(["drift", "--log", p["log"], "--log", twice, "--audits", p["audits"], "--tasks", p["tasks"]])
    assert (code, out) == (2, "")
    assert err == "error: call_id 'c0' has more than one final record, so its audit cannot be joined\n"


# --- no option keeps every byte ------------------------------------------------------------------

def test_no_window_keeps_every_shipped_select_output_of_v1_633(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    tasks = [t["name"] for t in json.loads((DATA_DIR / "example_tasks.json").read_text(encoding="utf-8"))["tasks"]]
    digest = hashlib.sha256()
    for task in tasks:
        for flavor in ("cost_effective", "cost_blind"):
            for json_flag in ([], ["--json"]):
                code, out, err = run(["select", task, "--flavor", flavor] + json_flag)
                digest.update(f"{code}\n{out}\n{err}\n".encode("utf-8"))
    assert len(tasks) == 8 and digest.hexdigest() == SHIPPED_SHA256


def test_no_readme_transcript_script_or_workflow_passes_a_window_or_runs_drift():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    commands = [line for line in readme.splitlines() if line.startswith("$ model-routing")]
    told = [line for line in readme.splitlines() if line.lstrip().startswith("model-routing ")]
    assert len(commands) >= 12 and len(told) >= 3
    assert not [c for c in commands + told if "--window" in c or c.lstrip("$ ").startswith("model-routing drift")]
    scripts = [p for folder in ("evidence", "research", ".github") for p in (ROOT / folder).rglob("*")
               if p.is_file() and p.suffix in (".py", ".yml", ".yaml", ".sh")]
    assert len(scripts) >= 20
    assert [str(p.relative_to(ROOT)) for p in scripts
            if "--window" in (t := p.read_text(encoding="utf-8")) or "model-routing drift" in t] == []


# --- the docs ------------------------------------------------------------------------------------

def test_design_and_changelog_state_v1_634():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    ten = design[design.index("## 10. CLI"):design.index("## 11. Demo")]
    assert ten.count("\n- v1.634 `drift --log PATH [--log PATH ...] --audits PATH [--window Nd] [--stats PATH] "
                     "[--tasks PATH] [--json]` and `select ... [--window Nd --log PATH [--log PATH ...] --audits PATH]` "
                     "(row M1c, 8.3 v1.632 and v1.633)") == 1
    [synopsis] = [x for x in ten.splitlines() if x.startswith("- `select TASK ")]
    assert "[--priors PATH] [--window Nd --log PATH [--log PATH ...] --audits PATH] [--json]" in synopsis
    section = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert "and the `drift` command and `select --window` v1.634 (10)." in section
    assert "the `drift` command and `select --window`, which v1.634 adds (10), and DESIGN 14's deferral" in section
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.count("\n- v1.634 (2026-11-24): spec, code and tests (10, row M1c).") == 1
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "  cli.py        model-routing select | calibrate | report | demo | evaluate | delegate | plan | promote | pairs | drift\n" in readme
