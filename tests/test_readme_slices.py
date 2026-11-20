"""README `## Split a task into slices` (DESIGN 5.2 v1.531, row STRAT4).

The part says in plain words why a task's success rate can hide a weak slice and how to split a
task; its tasks-file block loads with `load_tasks`; every number of its evidence bullets is read
here from the committed slice results (DESIGN 12.27, 12.28) or the AutoBench results.json (12.10);
and it links the RESULTS.md sections that hold the commands instead of holding them, so the README
evidence sentence keeps its count (12.13). tests/test_readme.py runs its `plan` transcript."""

import json
import re
from pathlib import Path

import pytest

from model_routing import load_tasks

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DESIGN = ROOT / "DESIGN.md"
AB = ROOT / "evidence" / "autobench-2026"
LCB = ROOT / "evidence" / "livecodebench"
HEADING = "\n## Split a task into slices\n"
AB_FILES = ("slices-difficulty", "slices-skill", "slices-difficulty-min10", "slices-skill-min10")


def readme_text():
    if not README.exists():
        pytest.skip("README.md is not next to the tests")
    return README.read_text(encoding="utf-8")


def section(text=None):
    text = readme_text() if text is None else text
    assert text.count(HEADING) == 1
    return text.split(HEADING, 1)[1].split("\n## ", 1)[0]


def load(path):
    return json.loads(path.read_text(encoding="utf-8"))


def summary_row(data, bar, flavor, strategy):
    rows = [r for r in data["slice_summary"] if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1, (bar, flavor, strategy)
    return rows[0]


def f3(value):
    return f"{value:.3f}"


def test_the_part_sits_between_use_it_in_code_and_monitoring():
    text = readme_text()
    assert (text.index("\n## Use it in code\n") < text.index(HEADING)
            < text.index("\n## Monitoring and cost attribution\n"))


def test_the_mix_example_and_its_arithmetic():
    body = section()
    quick_share, quick, deep = 0.8, 0.99, 0.64
    average = quick_share * quick + (1 - quick_share) * deep
    assert f"{average:.0%}" == "92%" and average >= 0.85
    assert abs((1 - deep) - 1 / 3) < 0.05  # fails 36% of the deep ones, about a third
    for words in ("is an average over the mix of its calibration items",
                  "80% of a support task's tickets are quick fixes and 20% are deep investigations",
                  "right on 99% of the quick ones and 64% of the deep ones averages 92%",
                  "it clears a 0.85 bar while failing about a third of the deep tickets",
                  "if the mix shifts toward deep tickets the bar stops holding"):
        assert words in body, words


def test_the_part_says_how_to_split_a_task_and_check_the_split():
    body = section()
    for words in ("something known before the call", "the library never classifies", '`"slice": "deep"`',
                  "`support@deep`", "the task's own counts still cover every line",
                  '`Router.select(..., slice="deep")`', '`Executor.call(..., slice="deep")`',
                  "`model-routing select --slice S`", "admitted only on that slice's own counts",
                  "`insufficient_samples` on every slice", "the task's `on_no_model` applies",
                  "Each log record carries the call's `slice`", "`model-routing evaluate --slice-by FIELD`",
                  "`pooled` (the task's route, scored on each slice's held-out items)",
                  "`sliced` (each slice routed on its own calibration items)", "`slice_miss_rate`"):
        assert words in body, words


def test_the_tasks_file_block_loads(tmp_path):
    blocks = re.findall(r"```json\n(.*?)```", section(), re.S)
    assert len(blocks) == 1
    path = tmp_path / "tasks.json"
    path.write_text(blocks[0], encoding="utf-8")
    task = load_tasks(path)["support"]
    assert task.bar == 0.85 and task.slices == {"deep": {"bar": 0.9}}


def test_the_part_links_the_slices_sections_and_holds_no_commands():
    body = section()
    for folder, label in ((AB, "AutoBench"), (LCB, "LiveCodeBench")):
        assert (folder / "RESULTS.md").read_text(encoding="utf-8").count("\n## Slices\n") == 1
        assert f"[{label}](evidence/{folder.name}/RESULTS.md#slices)" in body
    assert "```bash" not in body  # so the evidence sentence's file count stays (DESIGN 12.13)


def test_the_livecodebench_numbers_are_the_committed_ones():
    body = section()
    data = load(LCB / "slices-difficulty.json")
    by_slice = {}
    for row in data["per_slice"]:
        if row["strategy"] == "pooled":
            by_slice.setdefault(row["slice"], set()).add(f3(row["success"]))
    assert sorted(by_slice) == ["1-easy", "2-medium", "3-hard"]
    assert all(len(values) == 1 for values in by_slice.values())  # the same at every bar
    easy, medium, hard = (min(by_slice[name]) for name in ("1-easy", "2-medium", "3-hard"))
    pooled = {f3(r["success"]) for r in data["slice_summary"] if r["strategy"] == "pooled"}
    sliced = {f3(r["success"]) for r in data["slice_summary"] if r["strategy"] == "sliced"}
    assert len(pooled) == 1 and len(sliced) == 1
    (pooled,), (sliced,) = pooled, sliced
    assert (f"On LiveCodeBench the task's route scores {pooled} on held-out problems, but {easy} on `1-easy`, "
            f"{medium} on `2-medium` and {hard} on `3-hard`") in body
    assert f"The sliced LiveCodeBench route scores {sliced} against the pooled {pooled}" in body


def test_the_autobench_numbers_are_the_committed_ones():
    body = section()
    files = {name: load(AB / f"{name}.json") for name in AB_FILES}
    diff, diff10 = files["slices-difficulty"], files["slices-difficulty-min10"]
    miss = summary_row(diff, 0.6, "cost_effective", "pooled")["slice_miss_rate"]
    assert (f"of the seeds on which the `cost_effective` route cleared and met bar 0.6 on the whole task, some "
            f"difficulty level fell below it on {f3(miss)}") in body
    task = diff["tasks"]["all"]
    counts = task["slices"]
    assert len(counts) == 5
    assert (f"five difficulty levels hold {min(counts.values())} to {max(counts.values())} of its {task['items']} "
            f"questions each") in body
    assert diff["config"]["min_samples"] == 30 and diff10["config"]["min_samples"] == 10
    cleared = [summary_row(f, 0.6, "cost_effective", "sliced")["cleared_rate"] for f in (diff, diff10)]
    assert f"a level clears bar 0.6 on its own counts in {f3(cleared[0])} of the (level, seed) pairs" in body
    assert f"At `--min-samples 10` it clears in {f3(cleared[1])} of them" in body
    violation = [summary_row(f, 0.8, "cost_effective", "sliced")["bar_violation_rate"] for f in (diff, diff10)]
    assert (f"at bar 0.8 the share of cleared pairs that fall below the bar on held-out questions rises from "
            f"{f3(violation[0])} to {f3(violation[1])}") in body


def test_no_sliced_autobench_row_beats_the_best_single_model():
    body = section()
    results = load(AB / "results.json")
    luna = {(r["success"], r["cost_usd"]) for r in results["summary"]
            if r["strategy"] == "model:openai/gpt-5.6-luna"}
    assert len(luna) == 1
    ((success, cost),) = luna
    assert f"always calling `openai/gpt-5.6-luna` ({f3(success)} at {cost:.4f} USD)" in body
    for name in AB_FILES:
        for row in load(AB / f"{name}.json")["slice_summary"]:
            if row["strategy"] == "sliced":
                assert not (row["success"] >= success and row["cost_usd"] <= cost), (name, row)


def test_the_small_slice_sentence_reads_the_transcript():
    body = section()
    blocks = re.findall(r"```text\n(\$ model-routing [^\n]*\n.*?)```", body, re.S)
    assert len(blocks) == 1 and blocks[0].startswith("$ model-routing plan --success 1.0 --bar 0.8\n")
    items = re.search(r"^items: +(\d+)$", blocks[0], re.M).group(1)
    assert f"even a model that is right every time needs {items} of them before its lower bound clears 0.8" in body


def test_design_names_the_part():
    text = DESIGN.read_text(encoding="utf-8")
    routing = text.split("\n## 5. ", 1)[1].split("\n## 6. ", 1)[0]
    bullets = [line for line in routing.split("\n")
               if line.startswith("- v1.531 README (row STRAT4): `## Split a task into slices`")]
    assert len(bullets) == 1
    for words in ("`tests/test_readme_slices.py`", "`plan --success 1.0 --bar 0.8`", "holds no `bash` block",
                  "still counts 14 files"):
        assert words in bullets[0], words
    readme = readme_text()
    assert "fails if one of the 14 results files those commands write changes by a byte" in readme
