"""v1.7 RouterBench results contract (DESIGN 12.7), written before the script existed.

``evidence/routerbench/results.py`` is a standard-library script outside the package,
loaded from its path by an autouse fixture before any other test code runs. The tests
were held under a module-level strict xfail until the script landed; the implementing
commit removed that marker. They need no pandas and no download: they run on a small
synthetic matrix, on hand-made results with known answers, and on the committed
``results.json`` and ``RESULTS.md``. v1.18 also builds the RouterBench prose numbers of
RESULTS.md and the README from the committed file, and rebuilds the half sizes and the
graded-evals sensitivity numbers from the pinned pickle only when it is cached.
"""

import hashlib
import importlib.util
import json
import os
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows, split_items

FOLDER = Path(__file__).resolve().parents[1] / "evidence" / "routerbench"
README = Path(__file__).resolve().parents[1] / "README.md"
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


def load_convert():
    spec = importlib.util.spec_from_file_location("routerbench_convert", FOLDER / "convert.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def readme_tables(results):
    """The two RouterBench tables of the README evidence section (DESIGN 12.8, v1.10)."""
    config = results["config"]
    rows = {(r["bar"], r["flavor"], r["strategy"]): r for r in results["summary"]}
    first = (config["bars"][0], config["flavors"][0])
    models = [r for (bar, flavor, strategy), r in rows.items()
              if (bar, flavor) == first and strategy.startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    cheapest = rows[first + ("cheapest",)]
    lines = ["| Bar | Flavor | Held-out success | Cost (USD) | Cost / best single model "
             "| Cost / cheapest model | Cleared rate | Bar-violation rate |",
             "|---|---|---|---|---|---|---|---|"]
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            r = rows[(bar, flavor, "routed")]
            lines.append(f"| {bar} | `{flavor}` | {r['success']:.3f} | {r['cost_usd']:.4f} "
                         f"| {r['cost_usd'] / best['cost_usd']:.3f} "
                         f"| {r['cost_usd'] / cheapest['cost_usd']:.1f} "
                         f"| {r['cleared_rate']:.3f} | {r['bar_violation_rate']:.3f} |")
    baselines = [
        ("Per-prompt oracle: on each prompt, the cheapest model that got it right, "
         "or the cheapest model, counted wrong, when none did", "oracle"),
        (f"Best single model (`{best['strategy'][len('model:'):]}`)", best["strategy"]),
        ("Best model on the calibration half, per eval", "best_on_calibration"),
        ("Cheapest model on the calibration half, per eval", "cheapest")]
    lines += ["", "| Baseline | Held-out success | Cost (USD) |", "|---|---|---|"]
    for label, strategy in baselines:
        r = rows[first + (strategy,)]
        lines.append(f"| {label} | {r['success']:.3f} | {r['cost_usd']:.4f} |")
    return "\n".join(lines) + "\n"


def routerbench_subsection():
    readme = README.read_text(encoding="utf-8")
    heading = "\n## Evidence: held-out results on public data\n"
    assert readme.count(heading) == 1
    section = readme.split(heading, 1)[1].split("\n## ", 1)[0]
    assert section.count("\n### RouterBench\n") == 1
    return section.split("\n### RouterBench\n", 1)[1].split("\n### ", 1)[0]


def test_readme_evidence_tables_are_the_committed_results():
    results = json.loads((FOLDER / "results.json").read_text(encoding="utf-8"))
    section = routerbench_subsection()
    assert "\n" + readme_tables(results) in section
    tasks, config = results["tasks"], results["config"]
    models = {m for t in tasks.values() for m in t["models"]}
    mmlu = sum(1 for task in tasks if task.startswith("mmlu"))
    items = sum(t["items"] for t in tasks.values())
    counts = (f"{len(models)} models, {len(tasks)} evals ({mmlu} of them MMLU subjects), "
              f"{items:,} prompts, {len(config['seeds'])} seeds")
    assert counts in section
    assert f"routed at bars {config['bars'][0]} to {config['bars'][-1]} in both flavors" in section
    assert f"keeping {len(tasks)} of the 86;" in section
    assert "from 86 evals" in (FOLDER / "README.md").read_text(encoding="utf-8")


def test_readme_evidence_links_source_revision_results_and_commands():
    section = routerbench_subsection()
    revision = load_convert().REVISION
    for needle in ("https://huggingface.co/datasets/withmartian/routerbench",
                   f"[`{revision[:7]}`](https://huggingface.co/datasets/withmartian/routerbench"
                   f"/tree/{revision})",
                   "https://github.com/withmartian/routerbench",
                   "(evidence/routerbench/RESULTS.md)", "(evidence/routerbench/results.json)",
                   "(evidence/routerbench/README.md)"):
        assert needle in section, needle
    results_md = (FOLDER / "RESULTS.md").read_text(encoding="utf-8")
    regenerate = results_md.split("## Regenerate\n\n```bash\n", 1)[1].split("```", 1)[0]
    assert regenerate.count("\n") == 5
    assert "```bash\n" + regenerate + "```" in section


# --- the RouterBench prose, built from the committed file (DESIGN 12.7, 12.8, v1.18) ---------

WORDS = {2: "two", 3: "three", 4: "four", 5: "five", 6: "six"}


def committed_results():
    return json.loads((FOLDER / "results.json").read_text(encoding="utf-8"))


def results_md():
    return (FOLDER / "RESULTS.md").read_text(encoding="utf-8")


def summary_row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"]
            if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1, (bar, flavor, strategy)
    return rows[0]


def prose_rows(results):
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == first and r["strategy"].startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    ce = [summary_row(results, bar, "cost_effective", "routed") for bar in config["bars"]]
    cb = [summary_row(results, bar, "cost_blind", "routed") for bar in config["bars"]]
    boc = summary_row(results, *first, "best_on_calibration")
    oracle = summary_row(results, *first, "oracle")
    return config, best, ce, cb, boc, oracle


def same_success_words(cb, boc):
    """The words are allowed only while they are true (DESIGN 12.7, v1.18)."""
    assert all((r["success"], r["cost_usd"]) == (cb[0]["success"], cb[0]["cost_usd"]) for r in cb)
    assert f"{cb[0]['success']:.3f}" == f"{boc['success']:.3f}"
    assert cb[0]["cost_usd"] > boc["cost_usd"]
    more = (cb[0]["cost_usd"] / boc["cost_usd"] - 1) * 100
    return f"the same success to three decimals at {more:.1f}% more cost"


def fewest_prompts(results):
    items = [t["items"] for t in results["tasks"].values()]
    return min(items), items.count(min(items))


def results_md_phrases(results):
    config, best, ce, cb, boc, oracle = prose_rows(results)
    bars, seeds, conf = config["bars"], len(config["seeds"]), config["confidence"]
    tasks = results["tasks"]
    models = {m for t in tasks.values() for m in t["models"]}
    items = sum(t["items"] for t in tasks.values())
    violations = [r["bar_violation_rate"] for r in ce]
    fewest, how_many = fewest_prompts(results)
    ratio = [r["cost_usd"] / best["cost_usd"] for r in ce]
    assert all(a < b for a, b in zip(ratio, ratio[1:])), "the cost ratio no longer rises"
    return [
        f"{len(models)} models, {len(tasks)} evals (one task each), {items:,} prompts",
        f"For each eval and each of {seeds} seeds",
        f"At bar {bars[0]} it cleared {ce[0]['cleared_rate'] * 100:.1f}% of cells and spent "
        f"{ratio[0]:.3f} of the best single model's cost for an overall success of "
        f"{ce[0]['success']:.3f} against that model's {best['success']:.3f}",
        f"at {bars[-1]} only {ce[-1]['cleared_rate'] * 100:.1f}% of cells clear",
        f"the cost ratio rises to {ratio[-1]:.3f}",
        f"success {cb[0]['success']:.3f} at {cb[0]['cost_usd'] / best['cost_usd']:.3f} of the best "
        f"single model's cost at every bar, close to `best_on_calibration` "
        f"({boc['success']:.3f} at {boc['cost_usd'] / best['cost_usd']:.3f}): "
        + same_success_words(cb, boc),
        f"`bar_violation_rate` for `cost_effective` runs from {min(violations):.3f} to "
        f"{max(violations):.3f} across the {WORDS[len(bars)]} bars, next to a nominal one-sided "
        f"{(1 - conf) / 2:.3f} for a {conf * 100:.0f}% Wilson bound on one model",
        f"{how_many} evals hold only {fewest} prompts, and their held-out halves run from",
        f"and the {seeds} seeds re-split one pool",
        f"The per-prompt oracle reaches {oracle['success']:.3f} at {oracle['cost_usd']:.4f} USD",
    ]


def test_results_md_reading_numbers_are_the_committed_results():
    text = results_md()
    for phrase in results_md_phrases(committed_results()):
        assert phrase in text, phrase
    assert "level with" not in text


def readme_reading_phrases(results):
    config, best, ce, cb, boc, oracle = prose_rows(results)
    conf = config["confidence"]
    top = max(r["success"] for r in ce + cb)
    assert oracle["success"] - top >= 0.1, "routing per task is no longer nowhere near the oracle"
    return [
        f"`cost_blind` routes each eval to the model with the highest lower bound, and at every "
        f"bar it reaches held-out success {cb[0]['success']:.3f} at {cb[0]['cost_usd']:.4f} USD "
        f"against {boc['success']:.3f} at {boc['cost_usd']:.4f} USD for the best model on the "
        f"calibration half: " + same_success_words(cb, boc),
        f"next to the nominal one-sided {(1 - conf) / 2:.3f} of a {conf * 100:.0f}% Wilson bound "
        f"on one model",
        f"The per-prompt oracle is a hindsight bound ({oracle['success']:.3f} held-out success at "
        f"{oracle['cost_usd']:.4f} USD, against at most {top:.3f} for a routed row). Routing per "
        f"task gets nowhere near it",
    ]


def test_readme_reading_it_is_the_committed_results():
    results, section = committed_results(), routerbench_subsection()
    for phrase in readme_reading_phrases(results):
        assert phrase in section, phrase
    assert "level with" not in section
    # the cost_effective bullet: "At the lower bars it gives up held-out success for a large
    # cut in cost; as the bar rises, fewer evals clear it, ... and its cost approaches that of
    # the best single model"
    assert "At the lower bars it gives up held-out success for a large cut in cost" in section
    _, best, ce, cb, _, _ = prose_rows(results)
    cleared = [r["cleared_rate"] for r in ce]
    cost = [r["cost_usd"] for r in ce]
    assert all(a > b for a, b in zip(cleared, cleared[1:]))
    assert all(a < b for a, b in zip(cost, cost[1:]))
    for low, blind in list(zip(ce, cb))[:2]:
        assert low["cost_usd"] < 0.5 * best["cost_usd"] and low["success"] < blind["success"]
    assert ce[-1]["cost_usd"] >= 0.9 * best["cost_usd"]


def test_same_success_words_refuse_a_gap_or_a_cheaper_cost_blind():
    results = committed_results()
    _, _, _, cb, boc, _ = prose_rows(results)
    assert same_success_words(cb, boc).endswith("% more cost")
    for change in ({"success": boc["success"] - 0.002}, {"cost_usd": cb[0]["cost_usd"] * 2}):
        with pytest.raises(AssertionError):
            same_success_words(cb, dict(boc, **change))
    with pytest.raises(AssertionError):
        same_success_words(cb[:1] + [dict(cb[1], cost_usd=cb[1]["cost_usd"] + 1)] + cb[2:], boc)


# --- checks on the pinned pickle, only when it is found (DESIGN 12.7, v1.18) -------------------

@pytest.fixture(scope="module")
def pinned_columns():
    cv = load_convert()
    if os.environ.get("ROUTERBENCH_PKL"):
        # an explicit request to check: a missing pandas or file fails, never skips
        if importlib.util.find_spec("pandas") is None:
            pytest.fail("ROUTERBENCH_PKL is set but pandas is not installed")
        path = Path(os.environ["ROUTERBENCH_PKL"])
    else:
        pytest.importorskip("pandas")
        path = cv.default_cache_dir() / cv.FILENAME
        if not path.is_file():
            pytest.skip("the pinned RouterBench file is not in the default cache")
    cv.verify(path)
    return cv, cv.frame_columns(cv.load_frame(path))


def test_real_smallest_eval_half_sizes_are_in_results_md(pinned_columns):
    cv, columns = pinned_columns
    results = committed_results()
    rows, report = cv.convert(columns)
    assert report["kept"] == {task: t["items"] for task, t in results["tasks"].items()}
    fewest, how_many = fewest_prompts(results)
    by_task = {}
    for r in rows:
        if report["kept"][r["task"]] == fewest:
            by_task.setdefault(r["task"], set()).add(r["item"])
    assert len(by_task) == how_many
    config = results["config"]
    held = [len(split_items(items, seed, config["calibration_fraction"])[1])
            for items in by_task.values() for seed in config["seeds"]]
    assert (f"{how_many} evals hold only {fewest} prompts, and their held-out halves run from "
            f"{min(held)} to {max(held)} prompts over the {len(config['seeds'])} seeds"
            ) in results_md()


def test_real_graded_eval_counts_are_in_results_md(pinned_columns):
    cv, columns = pinned_columns
    _, default = cv.convert(columns)
    _, graded = cv.convert(columns, pass_score=0.75)
    back = sorted(((n, t) for t, n in graded["kept"].items() if t not in default["kept"]),
                  reverse=True)
    assert len(back) == 2 and {t for _, t in back} <= set(default["dropped_graded"])
    rest = set(default["dropped_graded"]) - {t for _, t in back}
    assert rest and all(default["dropped_graded"][t] < 100 for t in rest)
    text = results_md()
    (n1, t1), (n2, t2) = back
    for phrase in (
            f"the converter drops the {WORDS[len(default['dropped_graded'])]} evals whose scores "
            f"are not just 0 or 1",
            f"With `--pass-score 0.75` a call counts as correct when its score is at least 0.75, "
            f"which brings back `{t1}` ({n1:,} prompts) and `{t2}` ({n2:,}); the other "
            f"{WORDS[len(rest)]} graded evals stay out as smaller than 100 prompts",
            f"That matrix has {len(graded['kept'])} evals, {sum(graded['kept'].values()):,} "
            f"prompts and {graded['rows']:,} rows"):
        assert phrase in text, phrase


@pytest.mark.skipif(not os.environ.get("ROUTERBENCH_PKL"),
                    reason="set ROUTERBENCH_PKL to the pinned file (an evaluate of about 20 s)")
def test_real_graded_eval_routed_numbers_are_in_results_md(pinned_columns):
    cv, columns = pinned_columns
    rows, _ = cv.convert(columns, pass_score=0.75)
    summary = evaluate(outcomes_from_rows(rows), bars=[0.8], seeds=range(50))["summary"]
    row = {(r["flavor"], r["strategy"]): r for r in summary}
    models = [r for (flavor, strategy), r in row.items()
              if flavor == "cost_effective" and strategy.startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    ce, cb = row[("cost_effective", "routed")], row[("cost_blind", "routed")]
    assert (f"At bar 0.8 with 50 seeds, `cost_effective` routed success is {ce['success']:.3f} at "
            f"{ce['cost_usd'] / best['cost_usd']:.3f} of the cost of the best single model "
            f"(`{best['strategy'][len('model:'):]}`, {best['success']:.3f}), cleared_rate "
            f"{ce['cleared_rate']:.3f} and bar_violation_rate {ce['bar_violation_rate']:.3f}; "
            f"`cost_blind` reaches {cb['success']:.3f} at {cb['cost_usd'] / best['cost_usd']:.3f} "
            f"with bar_violation_rate {cb['bar_violation_rate']:.3f}") in results_md()
