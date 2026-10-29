"""CLI exit codes, file workflows, and deterministic offline demonstration."""

import json
import re

import pytest
from model_routing import Stats, load_records, report, run_demo
from model_routing.cli import main


def select_args(files, *extra):
    args = ["select", "judge"]
    for flag, path in files.items():
        args.extend(["--" + flag, str(path)])
    return args + list(extra)


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")


def test_cli_select_text_prints_decision_fields_and_candidate_table(cli_files, capsys):
    assert main(select_args(cli_files)) == 0
    text = capsys.readouterr().out
    for required in ("fiction/cheap", "fiction/mid", "fiction/best", "measured"):
        assert required in text
    normalized = text.lower().replace("-", "_").replace(" ", "_")
    for label in ("primary", "fallback", "basis", "below_bar"):
        assert label in normalized
    assert "passes" in text


def test_cli_select_json_matches_decision_and_accepts_flavor_generator_exclusions(cli_files, capsys):
    assert main(select_args(cli_files, "--json", "--flavor", "cost_blind",
                            "--generator", "fiction/cheap", "--exclude", "fiction/mid")) == 0
    data = json.loads(capsys.readouterr().out)
    assert data["primary"] == "fiction/best"
    assert data["fallbacks"] == []
    assert data["flavor"] == "cost_blind"
    assert data["basis"] == "measured" and data["below_bar"] is False
    assert [row["reason"] for row in data["candidates"]] == ["generator", "excluded_model", "passes"]
    assert all(row["routing_cost"] == 0.0 for row in data["candidates"])


def test_cli_select_no_model_clears_bar_returns_exit_three(cli_files, tmp_path, capsys):
    cli_files["stats"] = tmp_path / "absent-stats.json"
    assert main(select_args(cli_files)) == 3


def test_cli_select_missing_priors_means_no_priors_not_bad_input(cli_files, tmp_path, capsys):
    cli_files["priors"] = tmp_path / "absent-priors.json"
    assert main(select_args(cli_files, "--json")) == 0
    assert json.loads(capsys.readouterr().out)["primary"] == "fiction/cheap"


def test_cli_select_default_packaged_paths_and_missing_default_stats(tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    assert main(["select", "faithfulness_judge", "--json"]) == 3


@pytest.mark.parametrize("kind", ["missing-registry", "missing-tasks", "bad-json", "unknown-task",
                                  "unknown-generator", "bad-task-value", "bad-flavor"])
def test_cli_select_bad_input_returns_exit_two(cli_files, tmp_path, kind):
    args = select_args(cli_files)
    if kind == "missing-registry":
        args[args.index("--registry") + 1] = str(tmp_path / "missing.json")
    elif kind == "missing-tasks":
        args[args.index("--tasks") + 1] = str(tmp_path / "missing.json")
    elif kind == "bad-json":
        cli_files["registry"].write_text("{broken")
    elif kind == "unknown-task":
        args[1] = "not-a-task"
    elif kind == "unknown-generator":
        args.extend(["--generator", "fiction/missing"])
    elif kind == "bad-task-value":
        cli_files["tasks"].write_text(json.dumps({"tasks": [{"name": "judge", "bar": 2}]}))
    elif kind == "bad-flavor":
        args.extend(["--flavor", "not-a-flavor"])
    assert main(args) == 2


def test_cli_calibrate_creates_then_merges_stats_and_prints_counts_and_bounds(tmp_path, capsys):
    results_path, stats_path = tmp_path / "results.jsonl", tmp_path / "stats.json"
    write_jsonl(results_path, [
        {"task": "judge", "model": "fiction/a", "correct": True},
        {"task": "judge", "model": "fiction/a", "prediction": "yes", "gold": "no"},
    ])
    argv = ["calibrate", "--results", str(results_path), "--stats", str(stats_path)]
    assert main(argv) == 0
    assert Stats.load(stats_path).get("judge", "fiction/a") == (1, 2)
    text = capsys.readouterr().out
    assert "judge" in text and "fiction/a" in text
    assert "1" in text and "2" in text
    assert re.search(r"0\.\d+", text), "calibrate must print a lower bound, not only integer counts"
    assert main(argv) == 0
    assert Stats.load(stats_path).get("judge", "fiction/a") == (2, 4)
    second = capsys.readouterr().out
    assert "2" in second and "4" in second


@pytest.mark.parametrize("kind", ["missing-results", "bad-json", "bad-row", "bad-existing-stats"])
def test_cli_calibrate_bad_input_returns_exit_two(tmp_path, kind):
    results_path, stats_path = tmp_path / "results.jsonl", tmp_path / "stats.json"
    if kind == "bad-json":
        results_path.write_text("{broken\n")
    elif kind == "bad-row":
        write_jsonl(results_path, [{"task": "judge", "model": "fiction/a"}])
    elif kind == "bad-existing-stats":
        write_jsonl(results_path, [{"task": "judge", "model": "fiction/a", "correct": True}])
        stats_path.write_text("bad json")
    assert main(["calibrate", "--results", str(results_path), "--stats", str(stats_path)]) == 2


def test_cli_report_json_uses_requested_group_and_text_report_prints_rows(tmp_path, record_factory, capsys):
    path = tmp_path / "calls.jsonl"
    records = [record_factory(tags={"suite": "sample"})]
    write_jsonl(path, records)
    assert main(["report", "--log", str(path), "--by", "tag:suite", "--json"]) == 0
    assert json.loads(capsys.readouterr().out) == report(records, by="tag:suite")
    assert main(["report", "--log", str(path)]) == 0
    text = capsys.readouterr().out
    assert "fiction/cheap" in text


@pytest.mark.parametrize("kind", ["missing-log", "bad-json", "bad-by"])
def test_cli_report_bad_input_returns_exit_two(tmp_path, record_factory, kind):
    path = tmp_path / "calls.jsonl"
    args = ["report", "--log", str(path)]
    if kind == "bad-json":
        path.write_text("{broken\n")
    elif kind == "bad-by":
        write_jsonl(path, [record_factory()])
        args.extend(["--by", "unknown"])
    assert main(args) == 2


def test_cli_demo_returns_success_prints_summary_and_creates_output(tmp_path, capsys):
    out = tmp_path / "demo"
    assert main(["demo", "--out", str(out)]) == 0
    text = capsys.readouterr().out
    assert "cost_effective" in text and "cost_blind" in text
    assert (out / "calls.jsonl").is_file()
    assert (out / "stats.json").is_file()


def test_run_demo_is_deterministic_and_cost_effective_is_cheaper(tmp_path):
    first = run_demo(tmp_path / "one", seed=7)
    second = run_demo(tmp_path / "two", seed=7)
    assert first == second
    assert set(first) == {"cost_effective", "cost_blind"}
    assert first["cost_effective"]["cost_usd"] < first["cost_blind"]["cost_usd"]
    for flavor, summary in first.items():
        assert set(summary) == {"primary", "fallbacks", "calls", "fallback_calls", "cost_usd"}
        assert summary["primary"].startswith("demo/")
        assert all(model.startswith("demo/") for model in summary["fallbacks"])
        assert summary["calls"] == 200
        assert 0 < summary["fallback_calls"] < 200
        assert summary["cost_usd"] > 0
    for directory in (tmp_path / "one", tmp_path / "two"):
        records = load_records(directory / "calls.jsonl")
        finals = [record for record in records if record["final"]]
        assert len(finals) == 400
        assert all(record["model"].startswith("demo/") for record in records)
        for flavor in first:
            group = [record for record in records if record["flavor"] == flavor]
            assert sum(record["final"] for record in group) == first[flavor]["calls"]
            assert sum(record["final"] and record["attempt"] > 0 for record in group) == first[flavor]["fallback_calls"]
            assert sum(record["cost_usd"] for record in group) == pytest.approx(first[flavor]["cost_usd"], abs=1e-6)
        rows = json.loads((directory / "stats.json").read_text())["stats"]
        assert len({row["model"] for row in rows}) == 4
        assert all(row["trials"] == 300 and row["model"].startswith("demo/") for row in rows)


@pytest.mark.parametrize("flag", ["--exclude", "--generator"])
def test_cli_select_unknown_registry_model_returns_two_even_if_other_models_pass(cli_files, flag):
    assert main(select_args(cli_files, flag, "fiction/unknown-model")) == 2


@pytest.mark.parametrize("exists", [False, True])
def test_cli_calibrate_bad_late_row_does_not_create_or_modify_stats(tmp_path, exists):
    results = tmp_path / "results.jsonl"
    stats = tmp_path / "stats.json"
    write_jsonl(results, [
        {"task": "judge", "model": "fiction/amber", "correct": True},
        {"task": "judge", "model": "fiction/amber", "correct": "false"},
    ])
    original = b'{"stats": [{"task": "judge", "model": "fiction/amber", "successes": 1, "trials": 2}]}\n'
    if exists:
        stats.write_bytes(original)
    assert main(["calibrate", "--results", str(results), "--stats", str(stats)]) == 2
    if exists:
        assert stats.read_bytes() == original
    else:
        assert not stats.exists()


@pytest.mark.parametrize("lines", ['{}\n\n[]\n', '{}\n{"truncated":\n'])
def test_cli_report_rejects_malformed_or_nonobject_jsonl(tmp_path, lines):
    path = tmp_path / "fiction-calls.jsonl"
    path.write_text(lines, encoding="utf-8")
    assert main(["report", "--log", str(path)]) == 2


@pytest.mark.parametrize("filename", ["calls.jsonl", "stats.json"])
def test_run_demo_refuses_to_overwrite_user_artifact_without_marker(tmp_path, filename):
    out = tmp_path / "demo"
    out.mkdir()
    artifact = out / filename
    original = b"user-owned-fictional-data\n\x00"
    artifact.write_bytes(original)
    with pytest.raises(FileExistsError):
        run_demo(out)
    assert artifact.read_bytes() == original
    assert not (out / ".model-routing-demo").exists()
    assert not (out / ("stats.json" if filename == "calls.jsonl" else "calls.jsonl")).exists()


@pytest.mark.parametrize("filename", ["calls.jsonl", "stats.json"])
def test_cli_demo_refuses_user_artifact_and_returns_two(tmp_path, filename):
    out = tmp_path / "demo"
    out.mkdir()
    artifact = out / filename
    original = b"user-owned-fictional-data\n"
    artifact.write_bytes(original)
    assert main(["demo", "--out", str(out)]) == 2
    assert artifact.read_bytes() == original
    assert not (out / ".model-routing-demo").exists()


def test_run_demo_can_replace_its_own_marked_outputs_deterministically(tmp_path):
    out = tmp_path / "demo"
    first = run_demo(out, seed=17)
    marker = out / ".model-routing-demo"
    assert marker.is_file() and marker.read_bytes() == b""
    initial = {name: (out / name).read_bytes() for name in ("calls.jsonl", "stats.json")}
    second = run_demo(out, seed=17)
    assert first == second
    assert marker.read_bytes() == b""
    assert {name: (out / name).read_bytes() for name in initial} == initial
