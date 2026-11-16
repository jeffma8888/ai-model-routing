"""Dated list prices expire visibly (DESIGN 4.1, 9, 10 and 13.7, v1.15; the warning's scope and
`evaluate`, 10, 12.4 and 13.7, v1.411, row P2b)."""

import json
import re
from dataclasses import asdict
from datetime import date, datetime
from pathlib import Path

import pytest

from model_routing import DATA_DIR, Model, Registry
from model_routing.cli import main
from model_routing.stats import Stats

ON = date(2026, 11, 21)
BEFORE = date(2026, 11, 20)
AFTER = date(2026, 11, 22)
README = Path(__file__).resolve().parent.parent / "README.md"


def warning(model_id, day):
    return (f"warning: list price of {model_id} was stated valid through {day}; "
            "check the vendor page and update the registry")


# 4.1: the field, the check and the registry helper


def test_price_valid_until_defaults_to_none_and_never_expires(model_factory):
    model = model_factory()
    assert model.price_valid_until is None
    for today in (date(1970, 1, 1), ON, date(9999, 12, 31)):
        assert model.price_expired(today) is False


def test_price_is_valid_through_the_stated_day_and_expired_the_day_after(model_factory):
    model = model_factory(price_valid_until="2026-11-21")
    assert model.price_valid_until == "2026-11-21"
    assert model.price_expired(BEFORE) is False
    assert model.price_expired(ON) is False
    assert model.price_expired(AFTER) is True
    assert model.price_expired(date(2027, 1, 1)) is True


def test_a_datetime_today_counts_as_its_own_date(model_factory):
    model = model_factory(price_valid_until="2026-11-21")
    assert model.price_expired(datetime(2026, 11, 21, 23, 59, 59)) is False
    assert model.price_expired(datetime(2026, 11, 22, 0, 0, 0)) is True


@pytest.mark.parametrize("today", ["2026-11-22", 20261122, None, 1.5])
def test_today_that_is_not_a_date_raises_typeerror(model_factory, today):
    model = model_factory(price_valid_until="2026-11-21")
    with pytest.raises(TypeError):
        model.price_expired(today)


@pytest.mark.parametrize("value", [
    "2026-11-31", "2026-02-30", "0000-01-01", "2026/11/21", "20261121", "2026-11-21T00:00",
    " 2026-11-21", "2026-11-21\n", "2026-1-21", "", "\uff12\uff10\uff12\uff16-11-21", "2026-W47-6",
    date(2026, 11, 21), 20261121, 2026.1121, True, ["2026-11-21"],
])
def test_an_invalid_price_valid_until_raises_valueerror(model_factory, value):
    with pytest.raises(ValueError):
        model_factory(price_valid_until=value)


def test_the_field_comes_after_aliases_so_positional_construction_still_works():
    model = Model("fiction/a", "f", 1.0, 2.0, 8000, {"api": "a"}, "2026-11-21")
    assert model.aliases == {"api": "a"}
    assert model.price_valid_until == "2026-11-21"
    assert Model("fiction/b", "f", 1.0, 2.0, 8000).price_valid_until is None


def test_expired_prices_lists_past_models_in_file_order(model_factory):
    registry = Registry([
        model_factory("fiction/late", price_valid_until="2026-12-31"),
        model_factory("fiction/plain"),
        model_factory("fiction/soon", price_valid_until="2026-11-21"),
        model_factory("fiction/old", price_valid_until="2026-01-01"),
    ])
    assert [m.id for m in registry.expired_prices(BEFORE)] == ["fiction/old"]
    assert [m.id for m in registry.expired_prices(ON)] == ["fiction/old"]
    assert [m.id for m in registry.expired_prices(AFTER)] == ["fiction/soon", "fiction/old"]
    assert [m.id for m in registry.expired_prices(date(2027, 1, 1))] == [
        "fiction/late", "fiction/soon", "fiction/old"]
    assert isinstance(registry.expired_prices(AFTER), tuple)


def row(model_id, **extra):
    return dict({"id": model_id, "family": "f", "price_in": 1.0, "price_out": 2.0,
                 "context_window": 8000, "source": "https://example.org/prices"}, **extra)


def write_registry(path, rows):
    path.write_text(json.dumps({"version": "1", "as_of": "2026-01-01", "currency": "USD",
                                "models": rows}), encoding="utf-8")
    return path


def test_registry_load_reads_the_key_and_treats_absent_or_null_as_none(tmp_path):
    path = write_registry(tmp_path / "models.json", [
        row("fiction/a", price_valid_until="2026-11-21"), row("fiction/b"),
        row("fiction/c", price_valid_until=None)])
    registry = Registry.load(path)
    assert [m.price_valid_until for m in registry.models] == ["2026-11-21", None, None]


@pytest.mark.parametrize("value", ["2026-13-01", "Nov 21 2026", 20261121, {"day": 21}])
def test_registry_load_rejects_an_invalid_value_naming_the_file(tmp_path, value):
    path = write_registry(tmp_path / "models.json", [row("fiction/a", price_valid_until=value)])
    with pytest.raises(ValueError, match="invalid model row"):
        Registry.load(path)


def test_asdict_rows_round_trip_through_json_and_registry_load(tmp_path, model_factory):
    models = [model_factory("fiction/a", price_valid_until="2026-11-21"),
              model_factory("fiction/b")]
    path = write_registry(tmp_path / "models.json", [asdict(m) for m in models])
    assert Registry.load(path).models == tuple(models)


# 9: the packaged registry


DATED_NOTE = re.compile(r"through (?:at least )?([0-9]{4}-[0-9]{2}-[0-9]{2})")


def test_each_packaged_row_carries_the_end_date_its_notes_state():
    raw = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))
    for r in raw["models"]:
        stated = DATED_NOTE.findall(r.get("notes", ""))
        assert len(stated) <= 1, r["id"]
        assert r.get("price_valid_until") == (stated[0] if stated else None), r["id"]
    registry = Registry.load(DATA_DIR / "models.json")
    assert registry.expired_prices(date.fromisoformat(raw["as_of"])) == ()


def test_dated_note_reads_the_promotional_wording():
    assert DATED_NOTE.findall("promotional price, stated through at least 2026-11-21") == [
        "2026-11-21"]
    assert DATED_NOTE.findall("price for context up to 200K tokens") == []


def test_the_readme_pricing_note_names_the_same_end_date():
    if not README.exists():
        pytest.skip("README.md is not next to the tests")
    text = README.read_text(encoding="utf-8")
    for model in Registry.load(DATA_DIR / "models.json").models:
        if model.price_valid_until is not None:
            name = model.id.split("/", 1)[1]
            notes = [line for line in text.splitlines() if line.startswith(f"- {name}: ")]
            assert len(notes) == 1, name
            assert model.price_valid_until in notes[0]
            assert "price_valid_until" in notes[0]


# 10 and 13.7: the CLI warns on stderr, after everything else


@pytest.fixture
def dated_files(cli_files, write_json):
    """cli_files with fiction/mid priced through ON and fiction/best through 2026-12-31."""
    models = json.loads(cli_files["registry"].read_text(encoding="utf-8"))["models"]
    for m in models:
        m.pop("price_valid_until", None)
    models[1]["price_valid_until"] = "2026-11-21"
    models[2]["price_valid_until"] = "2026-12-31"
    cli_files["registry"] = write_json("dated-models.json", {
        "version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models})
    return cli_files


def select_args(files, *extra):
    args = ["select", "judge"]
    for flag, path in files.items():
        args.extend(["--" + flag, str(path)])
    return args + list(extra)


def delegate_args(files, *extra):
    args = ["delegate", "judge", "--parent", "fiction/best", "--context-tokens", "1000",
            "--brief-tokens", "100", "--result-tokens", "50"]
    for flag, path in files.items():
        args.extend(["--" + flag, str(path)])
    return args + list(extra)


def run(capsys, args, today):
    code = main(args, today=today)
    captured = capsys.readouterr()
    return code, captured.out, captured.err


@pytest.mark.parametrize("build", [select_args, delegate_args])
@pytest.mark.parametrize("json_flag", [(), ("--json",)])
def test_cli_warns_once_per_expired_model_in_file_order_and_leaves_stdout_alone(
        dated_files, capsys, build, json_flag):
    args = build(dated_files, *json_flag)
    code, out_before, err_before = run(capsys, args, BEFORE)
    assert code == 0 and err_before == ""
    code, out_on, err_on = run(capsys, args, ON)
    assert code == 0 and err_on == "" and out_on == out_before
    code, out_after, err_after = run(capsys, args, AFTER)
    assert code == 0 and out_after == out_before
    assert err_after.splitlines() == [warning("fiction/mid", "2026-11-21")]
    code, out_later, err_later = run(capsys, args, date(2027, 1, 1))
    assert code == 0 and out_later == out_before
    assert err_later.splitlines() == [warning("fiction/mid", "2026-11-21"),
                                      warning("fiction/best", "2026-12-31")]
    if json_flag:
        json.loads(out_later)


# 10 v1.411 (row P2b): a run warns only for a model whose price its result can depend on


@pytest.mark.parametrize("build", [select_args, delegate_args])
def test_cli_does_not_warn_for_an_excluded_model(dated_files, capsys, build):
    code, out, err = run(capsys, build(dated_files, "--exclude", "fiction/mid"), AFTER)
    assert code == 0 and err == ""
    code, out, err = run(capsys, build(dated_files, "--exclude", "fiction/mid"), date(2027, 1, 1))
    assert code == 0
    assert err.splitlines() == [warning("fiction/best", "2026-12-31")]


@pytest.mark.parametrize("build", [select_args, delegate_args])
def test_cli_still_warns_for_an_eligible_model_it_did_not_choose(dated_files, capsys, build):
    code, out, err = run(capsys, build(dated_files, "--json"), AFTER)
    assert code == 0
    decision = json.loads(out)
    chosen = decision["primary"] if build is select_args else decision["model"]
    assert chosen != "fiction/mid"
    assert err.splitlines() == [warning("fiction/mid", "2026-11-21")]


@pytest.mark.parametrize("build", [select_args, delegate_args])
@pytest.mark.parametrize("rule, reason", [("family", "excluded_family"), ("generator", "generator"),
                                          ("generator-family", "generator_family"),
                                          ("window", "context_too_small")])
def test_cli_does_not_warn_for_a_model_rules_2_to_5_rule_out(
        dated_files, write_json, task_factory, capsys, build, rule, reason):
    extra = []
    if rule == "family":
        dated_files["tasks"] = write_json("family-tasks.json", {
            "tasks": [asdict(task_factory(exclude_families=("medium",)))]})
    elif rule == "generator":
        extra = ["--generator", "fiction/mid"]
    elif rule == "generator-family":
        models = json.loads(dated_files["registry"].read_text(encoding="utf-8"))["models"]
        models[0]["family"] = "medium"
        dated_files["registry"] = write_json("same-family.json", {
            "version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models})
        extra = ["--generator", "fiction/cheap"]
    else:
        models = json.loads(dated_files["registry"].read_text(encoding="utf-8"))["models"]
        models[1]["context_window"] = 500
        dated_files["registry"] = write_json("small-window.json", {
            "version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models})
    code, out, err = run(capsys, build(dated_files, *extra, "--json"), AFTER)
    assert code == 0 and err == ""
    decision = json.loads(out)
    candidates = decision["candidates"] if build is select_args else decision["route"]["candidates"]
    assert {c["model_id"]: c["reason"] for c in candidates}["fiction/mid"] == reason


@pytest.mark.parametrize("build", [select_args, delegate_args])
def test_cli_exit_three_skips_an_excluded_model(dated_files, tmp_path, capsys, build):
    dated_files["stats"] = tmp_path / "absent-stats.json"
    code, out, err = run(capsys, build(dated_files, "--exclude", "fiction/mid"), AFTER)
    assert code == 3 and out == ""
    lines = err.splitlines()
    assert lines[0].startswith("error: ")
    assert any(line.startswith("fiction/mid") for line in lines[1:])
    assert "warning:" not in err


def test_delegate_warns_for_its_parent_even_when_excluded(dated_files, capsys):
    args = delegate_args(dated_files, "--exclude", "fiction/mid", "--json")
    args[args.index("--parent") + 1] = "fiction/mid"
    code, out, err = run(capsys, args, AFTER)
    assert code == 0
    assert json.loads(out)["route"] is not None
    assert err.splitlines() == [warning("fiction/mid", "2026-11-21")]


def test_delegate_exit_three_still_warns_for_an_excluded_parent(dated_files, tmp_path, capsys):
    dated_files["stats"] = tmp_path / "absent-stats.json"
    args = delegate_args(dated_files, "--exclude", "fiction/mid")
    args[args.index("--parent") + 1] = "fiction/mid"
    code, out, err = run(capsys, args, AFTER)
    assert code == 3 and out == ""
    lines = err.splitlines()
    assert lines[0].startswith("error: ")
    assert lines[-1] == warning("fiction/mid", "2026-11-21")
    assert sum(line.startswith("warning: ") for line in lines) == 1


def test_delegate_with_no_route_warns_for_its_parent_alone(dated_files, tmp_path, capsys):
    stats = Stats()
    stats.add("judge", "fiction/best", 100, 100)
    dated_files["stats"] = tmp_path / "parent-only-stats.json"
    stats.save(dated_files["stats"])
    code, out, err = run(capsys, delegate_args(dated_files, "--exclude", "fiction/best", "--json"),
                         date(2027, 1, 1))
    assert code == 0
    decision = json.loads(out)
    assert decision["route"] is None and decision["mode"] == "inline"
    assert err.splitlines() == [warning("fiction/best", "2026-12-31")]


def test_design_states_the_v1_411_scope_and_the_evaluate_warning():
    text = (Path(__file__).resolve().parent.parent / "DESIGN.md").read_text(encoding="utf-8")
    section = text[text.index("\n## 10. CLI"):text.index("\n## 11. ")]
    assert section.count("\n- v1.411 warning scope (row P2b): ") == 1
    assert section.count("\n- v1.411 `evaluate` (12.4): ") == 1
    assert "is left open" not in section
    assert "so each of these prices is one the decision used" not in section


@pytest.mark.parametrize("build", [select_args, delegate_args])
def test_cli_rows_without_the_field_never_warn(cli_files, capsys, build):
    for today in (date(1970, 1, 1), AFTER, date(9999, 12, 31)):
        code, _, err = run(capsys, build(cli_files), today)
        assert code == 0 and err == ""


@pytest.mark.parametrize("build", [select_args, delegate_args])
def test_cli_exit_three_prints_the_warning_after_the_candidate_table(
        dated_files, tmp_path, capsys, build):
    dated_files["stats"] = tmp_path / "absent-stats.json"
    code, out, err = run(capsys, build(dated_files), AFTER)
    assert code == 3 and out == ""
    lines = err.splitlines()
    assert lines[0].startswith("error: ")
    assert any(line.startswith("fiction/mid") for line in lines[1:-1])
    assert lines[-1] == warning("fiction/mid", "2026-11-21")
    assert sum(line.startswith("warning: ") for line in lines) == 1


@pytest.mark.parametrize("build", [select_args, delegate_args])
@pytest.mark.parametrize("kind", ["unknown-task", "unknown-exclude", "bad-flavor"])
def test_cli_exit_two_prints_no_warning_and_the_error_stays_last(
        dated_files, capsys, build, kind):
    args = build(dated_files)
    if kind == "unknown-task":
        args[1] = "no_such_task"
    elif kind == "unknown-exclude":
        args += ["--exclude", "fiction/absent"]
    else:
        args += ["--flavor", "cheapest"]
    code, out, err = run(capsys, args, date(2027, 1, 1))
    assert code == 2
    assert "warning:" not in err
    assert err.splitlines()[-1].startswith("error: ")


@pytest.mark.parametrize("build", [select_args, delegate_args])
def test_cli_today_defaults_to_the_real_date(cli_files, write_json, capsys, build):
    models = json.loads(cli_files["registry"].read_text(encoding="utf-8"))["models"]
    models[0]["price_valid_until"] = "2000-01-01"
    models[1]["price_valid_until"] = "9999-12-31"
    models[2].pop("price_valid_until", None)
    cli_files["registry"] = write_json("default-today.json", {
        "version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models})
    assert main(build(cli_files)) == 0
    assert capsys.readouterr().err.splitlines() == [warning("fiction/cheap", "2000-01-01")]


@pytest.mark.parametrize("today", ["2026-11-22", 20261122])
def test_cli_today_that_is_not_a_date_raises_typeerror_before_any_output(
        dated_files, capsys, today):
    with pytest.raises(TypeError):
        main(select_args(dated_files), today=today)
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == ""


def test_other_commands_do_not_take_a_registry_warning(tmp_path, capsys, record_factory):
    log = tmp_path / "calls.jsonl"
    log.write_text(json.dumps(record_factory()) + "\n", encoding="utf-8")
    assert main(["report", "--log", str(log)], today=date(9999, 12, 31)) == 0
    assert capsys.readouterr().err == ""


# 10 and 12.4 v1.411 (row P2b): evaluate warns for the models of its token-form rows


def write_outcomes(path, token_form):
    """40 items of task t for the three fiction models; a row is in token form when
    token_form(model, n) is true, and carries cost_usd otherwise."""
    with path.open("w", encoding="utf-8") as fh:
        for n in range(40):
            for model_id in ("fiction/cheap", "fiction/mid", "fiction/best"):
                row = {"task": "t", "item": f"i{n:02d}", "model": model_id, "correct": n % 4 != 0}
                if token_form(model_id, n):
                    row.update(input_tokens=1000, output_tokens=200)
                else:
                    row["cost_usd"] = 0.001
                fh.write(json.dumps(row) + "\n")
    return path


def evaluate_args(files, outcomes, *extra):
    return ["evaluate", "--outcomes", str(outcomes), "--registry", str(files["registry"]),
            "--seeds", "2", *extra]


@pytest.mark.parametrize("json_flag", [(), ("--json",)])
def test_evaluate_warns_once_per_expired_model_with_a_token_form_row(
        dated_files, tmp_path, capsys, json_flag):
    outcomes = write_outcomes(tmp_path / "outcomes.jsonl", lambda m, n: m == "fiction/mid"
                              or (m == "fiction/best" and n == 7))
    args = evaluate_args(dated_files, outcomes, *json_flag)
    code, out_before, err = run(capsys, args, BEFORE)
    assert code == 0 and err == "" and out_before
    code, out, err = run(capsys, args, ON)
    assert code == 0 and err == "" and out == out_before
    code, out, err = run(capsys, args, AFTER)
    assert code == 0 and out == out_before
    assert err.splitlines() == [warning("fiction/mid", "2026-11-21")]
    code, out, err = run(capsys, args, date(2027, 1, 1))
    assert code == 0 and out == out_before
    assert err.splitlines() == [warning("fiction/mid", "2026-11-21"),
                                warning("fiction/best", "2026-12-31")]
    if json_flag:
        json.loads(out)


@pytest.mark.parametrize("which", ["none", "undated"])
def test_evaluate_never_warns_for_rows_that_carry_cost_usd(dated_files, tmp_path, capsys, which):
    token_form = (lambda m, n: False) if which == "none" else (lambda m, n: m == "fiction/cheap")
    outcomes = write_outcomes(tmp_path / "outcomes.jsonl", token_form)
    code, out, err = run(capsys, evaluate_args(dated_files, outcomes), date(9999, 12, 31))
    assert code == 0 and out and err == ""


@pytest.mark.parametrize("kind", ["incomplete", "bad-json"])
def test_evaluate_exit_two_prints_no_warning_and_the_error_stays_last(
        dated_files, tmp_path, capsys, kind):
    outcomes = write_outcomes(tmp_path / "outcomes.jsonl", lambda m, n: m == "fiction/mid")
    with outcomes.open("a", encoding="utf-8") as fh:
        if kind == "incomplete":
            fh.write(json.dumps({"task": "t", "item": "extra", "model": "fiction/mid",
                                 "correct": True, "input_tokens": 1, "output_tokens": 1}) + "\n")
        else:
            fh.write("{not json\n")
    code, out, err = run(capsys, evaluate_args(dated_files, outcomes), date(2027, 1, 1))
    assert code == 2 and out == ""
    assert "warning:" not in err
    assert err.splitlines()[-1].startswith("error: ")


def test_the_warning_text_has_no_placeholder_left():
    assert not re.search(r"MODEL|YYYY", warning("fiction/mid", "2026-11-21"))
