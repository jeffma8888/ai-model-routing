"""v1.7 RouterBench results contract (DESIGN 12.7), written before the script existed.

``evidence/routerbench/results.py`` is a standard-library script outside the package,
loaded from its path by an autouse fixture before any other test code runs. The tests
were held under a module-level strict xfail until the script landed; the implementing
commit removed that marker. They need no pandas and no download: they run on a small
synthetic matrix, on hand-made results with known answers, and on the committed
``results.json`` and ``RESULTS.md``.
"""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

FOLDER = Path(__file__).resolve().parents[1] / "evidence" / "routerbench"
SCRIPT = FOLDER / "results.py"
TABLE_COMMAND = ("$ python evidence/routerbench/results.py --table "
                 "evidence/routerbench/results.json")
MODELS = [
    "WizardLM/WizardLM-13B-V1.2", "anthropic/claude-instant-v1", "anthropic/claude-v1",
    "anthropic/claude-v2", "meta/code-llama-instruct-34b-chat", "meta/llama-2-70b-chat",
    "mistralai/mistral-7b-chat", "mistralai/mixtral-8x7b-chat", "openai/gpt-3.5-turbo-1106",
    "openai/gpt-4-1106-preview", "zero-one-ai/Yi-34B-Chat"]
# sha256 of json.dumps({task: items}, sort_keys=True) for the converter's default output;
# equal to the converter's "kept" report on the pinned file when results.json was made
TASK_ITEMS_SHA256 = "79113be5a8ef336b9e398c59fa8ec6b5fb5ab10eadfeff193d7f56e516a3193b"

def load_rs():
    if not SCRIPT.is_file():
        raise ModuleNotFoundError(f"no results script at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("routerbench_results", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def rs():
    return load_rs()


def small_result():
    rows = []
    for task in ("alpha", "beta"):
        for i in range(40):
            item = f"{task}-{i}"
            rows.append({"task": task, "item": item, "model": "v/cheap",
                         "correct": i % 4 != 0, "cost_usd": 0.001})
            rows.append({"task": task, "item": item, "model": "v/big",
                         "correct": i % 10 != 0, "cost_usd": 0.01})
    return evaluate(outcomes_from_rows(rows), bars=[0.6, 0.9], seeds=range(3), min_samples=5)


def hand_results(best_cost=4.0):
    def row(bar, flavor, strategy, success, cost, cleared=None, violation=None):
        return {"bar": bar, "flavor": flavor, "strategy": strategy, "success": success,
                "cost_usd": cost, "below_bar_rate": 0.5, "cleared_rate": cleared,
                "bar_violation_rate": violation}
    summary = []
    for bar in (0.7, 0.9):
        for flavor in ("cost_effective", "cost_blind"):
            cost = 1.0 if flavor == "cost_effective" else 4.0
            summary += [row(bar, flavor, "routed", 0.75, cost, 0.5, None if bar == 0.9 else 0.25),
                        row(bar, flavor, "oracle", 0.95, 0.5),
                        row(bar, flavor, "best_on_calibration", 0.8, 4.0),
                        row(bar, flavor, "cheapest", 0.4, 0.25),
                        row(bar, flavor, "model:v/a", 0.8, 5.0),
                        row(bar, flavor, "model:v/b", 0.8, best_cost),
                        row(bar, flavor, "model:v/c", 0.4, 0.25)]
    config = {"bars": [0.7, 0.9], "seeds": [0], "flavors": ["cost_effective", "cost_blind"],
              "calibration_fraction": 0.5, "min_samples": 30, "confidence": 0.95}
    return {"config": config, "tasks": {}, "summary": summary, "per_task": []}


HAND_TABLE = "\n".join([
    "bar  flavor          success  cost_usd  vs_best_model  cleared_rate  bar_violation_rate",
    "---  --------------  -------  --------  -------------  ------------  ------------------",
    "0.7  cost_effective  0.750    1.0000    0.250          0.500         0.250",
    "0.7  cost_blind      0.750    4.0000    1.000          0.500         0.250",
    "0.9  cost_effective  0.750    1.0000    0.250          0.500         -",
    "0.9  cost_blind      0.750    4.0000    1.000          0.500         -",
    "",
    "strategy             success  cost_usd",
    "-------------------  -------  --------",
    "oracle               0.950    0.5000",
    "best_on_calibration  0.800    4.0000",
    "cheapest             0.400    0.2500",
    "model:v/a            0.800    5.0000",
    "model:v/b            0.800    4.0000",
    "model:v/c            0.400    0.2500",
])


def test_reduce_keeps_four_keys_and_only_routed_per_task_rows(rs):
    full = small_result()
    out = rs.reduce(full)
    assert list(out) == ["config", "tasks", "summary", "per_task"]
    assert out["config"] == full["config"] and out["tasks"] == full["tasks"]
    assert out["summary"] == full["summary"]
    assert out["per_task"] == [r for r in full["per_task"] if r["strategy"] == "routed"]
    assert len(out["per_task"]) == 2 * 2 * 2
    assert rs.reduce(out) == out


def test_reduce_accepts_the_cli_output_and_leaves_its_input_alone(rs):
    full = small_result()
    full.pop("cells")
    before = json.dumps(full, sort_keys=True)
    rs.reduce(full)
    assert json.dumps(full, sort_keys=True) == before


@pytest.mark.parametrize("key", ["config", "tasks", "summary", "per_task"])
def test_reduce_names_a_missing_key(rs, key):
    full = small_result()
    del full[key]
    with pytest.raises(ValueError, match=key):
        rs.reduce(full)


def test_table_known_answer_and_best_model_tie_by_cost(rs):
    assert rs.table(hand_results()) == HAND_TABLE


def test_table_ratio_uses_the_best_model_cost(rs):
    # v/a and v/b tie on success and cost here, so either one gives the same ratios: this
    # checks the denominator, not the name tie-break, which no table output can show.
    # The known-answer test above checks that a success tie goes to the lower cost.
    results = hand_results(best_cost=5.0)
    lines = rs.table(results).splitlines()
    assert lines[2].split()[4] == "0.200"
    assert lines[3].split()[4] == "0.800"


def test_table_zero_best_cost_prints_a_dash(rs):
    results = hand_results()
    for row in results["summary"]:
        if row["strategy"].startswith("model:"):
            row["cost_usd"] = 0.0
    assert rs.table(results).splitlines()[2].split()[4] == "-"


def test_table_runs_on_a_real_evaluate_result(rs):
    text = rs.table(rs.reduce(small_result()))
    lines = text.splitlines()
    assert lines[0].split() == ["bar", "flavor", "success", "cost_usd", "vs_best_model",
                                "cleared_rate", "bar_violation_rate"]
    assert [line.split()[:2] for line in lines[2:6]] == [
        ["0.6", "cost_effective"], ["0.6", "cost_blind"],
        ["0.9", "cost_effective"], ["0.9", "cost_blind"]]
    assert lines[6] == "" and lines[7].split() == ["strategy", "success", "cost_usd"]
    assert [line.split()[0] for line in lines[9:]] == [
        "oracle", "best_on_calibration", "cheapest", "model:v/big", "model:v/cheap"]
    assert not text.endswith("\n") and all(line == line.rstrip() for line in lines)


@pytest.mark.parametrize("mutate", ["no_config", "no_summary", "no_routed", "no_model"])
def test_table_structural_errors(rs, mutate):
    results = hand_results()
    if mutate == "no_config":
        del results["config"]
    elif mutate == "no_summary":
        del results["summary"]
    elif mutate == "no_routed":
        results["summary"] = [r for r in results["summary"]
                              if not (r["strategy"] == "routed" and r["bar"] == 0.9)]
    else:
        results["summary"] = [r for r in results["summary"]
                              if not r["strategy"].startswith("model:")]
    with pytest.raises(ValueError):
        rs.table(results)


def test_cli_evaluate_writes_the_reduced_file(rs, tmp_path, capsys):
    full = small_result()
    full.pop("cells")
    src = tmp_path / "full.json"
    src.write_text(json.dumps(full, indent=2), encoding="utf-8")
    out = tmp_path / "results.json"
    assert rs.main(["--evaluate", str(src), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == json.dumps(rs.reduce(full), indent=2) + "\n"
    assert capsys.readouterr().err == ""


def test_cli_table_prints_the_table(rs, tmp_path, capsys):
    src = tmp_path / "results.json"
    src.write_text(json.dumps(hand_results()), encoding="utf-8")
    assert rs.main(["--table", str(src)]) == 0
    captured = capsys.readouterr()
    assert captured.out == HAND_TABLE + "\n" and captured.err == ""


@pytest.mark.parametrize("args", [
    [], ["--evaluate", "full.json"], ["--table", "r.json", "--out", "x.json"],
    ["--evaluate", "full.json", "--table", "r.json", "--out", "x.json"],
    ["--table", "missing.json"], ["--table", "bad.json"], ["--table", "list.json"],
    ["--table", "empty_object.json"], ["--evaluate", "empty_object.json", "--out", "x.json"],
])
def test_cli_errors_exit_2_with_one_error_line(rs, args, tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "full.json").write_text("{}", encoding="utf-8")
    (tmp_path / "r.json").write_text("{}", encoding="utf-8")
    (tmp_path / "bad.json").write_text("{not json", encoding="utf-8")
    (tmp_path / "list.json").write_text("[1, 2]", encoding="utf-8")
    (tmp_path / "empty_object.json").write_text("{}", encoding="utf-8")
    assert rs.main(args) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert len(lines) == 1 and lines[0].startswith("error: ")
    assert not (tmp_path / "x.json").exists()


@pytest.mark.parametrize("fail_at", ["write", "rename"])
@pytest.mark.parametrize("existing", [True, False])
def test_cli_a_failed_write_leaves_out_alone_and_no_part_file(rs, fail_at, existing, tmp_path,
                                                              capsys, monkeypatch):
    full = small_result()
    full.pop("cells")
    src = tmp_path / "full.json"
    src.write_text(json.dumps(full), encoding="utf-8")
    out = tmp_path / "results.json"
    if existing:
        out.write_text("previous results\n", encoding="utf-8")
    if fail_at == "write":
        real_write_text = Path.write_text

        def partial_write_text(self, data, *args, **kwargs):
            real_write_text(self, data[:10], *args, **kwargs)
            raise OSError("disk full")
        monkeypatch.setattr(Path, "write_text", partial_write_text)
    else:
        def failing_replace(self, target):
            raise OSError("rename failed")
        monkeypatch.setattr(Path, "replace", failing_replace)
    assert rs.main(["--evaluate", str(src), "--out", str(out)]) == 2
    monkeypatch.undo()
    captured = capsys.readouterr()
    assert captured.out == "" and len(captured.err.splitlines()) == 1
    assert captured.err.startswith("error: ")
    if existing:
        assert out.read_text(encoding="utf-8") == "previous results\n"
    else:
        assert not out.exists()
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        ["full.json"] + (["results.json"] if existing else []))


def test_cli_a_line_break_in_a_path_stays_on_one_error_line(rs, tmp_path, capsys):
    bad = tmp_path / "bad\ninput.json"
    bad.write_text("{not json", encoding="utf-8")
    assert rs.main(["--table", str(bad)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    lines = captured.err.splitlines()
    assert len(lines) == 1 and lines[0].startswith("error: ") and "bad\\ninput.json" in lines[0]


def test_committed_results_are_small_reduced_and_pinned(rs):
    path = FOLDER / "results.json"
    assert path.stat().st_size < 300_000
    text = path.read_text(encoding="utf-8")
    results = json.loads(text)
    assert text == json.dumps(rs.reduce(results), indent=2) + "\n"
    assert results["config"] == {
        "bars": [0.6, 0.7, 0.8, 0.9], "seeds": list(range(50)),
        "flavors": ["cost_effective", "cost_blind"], "calibration_fraction": 0.5,
        "min_samples": 30, "confidence": 0.95}
    assert len(results["tasks"]) == 65
    assert all(t["models"] == MODELS for t in results["tasks"].values())
    items = {task: t["items"] for task, t in results["tasks"].items()}
    assert sum(items.values()) == 28281 and min(items.values()) >= 100
    digest = hashlib.sha256(json.dumps(items, sort_keys=True).encode("utf-8")).hexdigest()
    assert digest == TASK_ITEMS_SHA256
    summary_keys = {(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]}
    assert len(results["summary"]) == len(summary_keys) == 4 * 2 * (4 + 11)
    task_keys = {(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]}
    assert len(results["per_task"]) == len(task_keys) == 4 * 2 * 65
    assert {task for _, _, task in task_keys} == set(items)
    assert all(sum(r["routed_models"].values()) == 50 and set(r["routed_models"]) <= set(MODELS)
               for r in results["per_task"])


def test_results_md_shows_the_table_of_the_committed_results(rs):
    results = json.loads((FOLDER / "results.json").read_text(encoding="utf-8"))
    block = "```text\n" + TABLE_COMMAND + "\n" + rs.table(results) + "\n```\n"
    assert block in (FOLDER / "RESULTS.md").read_text(encoding="utf-8")
