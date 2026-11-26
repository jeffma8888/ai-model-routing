"""DESIGN 10 v1.661 (row JUDGE1ba): `model-routing consensus-labels` on the command line.

`consensus-labels --grades FILE --judges A,B --reruns N --out FILE [--min-agreement M]
[--generator MODEL [--registry PATH]]` reads the reference judges' recorded grades, calls
`consensus_labels` (4.3 v1.660), prints each task's items, kept items, agreement and whether it
passes, and writes the label rows whole as JSONL only when every task passes; a task under the
minimum exits 3 with no file created or changed, and bad input exits 2 with one `error:` line,
nothing on stdout and no file. The grades are synthetic, with a known truth per item, so each
count is computed by hand. No model is called, and no README transcript, evidence or research
script or workflow runs the command, so every transcript and evidence file keeps its bytes.
"""

import contextlib
import io
import json
from pathlib import Path

import pytest

from model_routing import DATA_DIR
from model_routing.cli import main
from model_routing.stats import consensus_labels

ROOT = Path(__file__).resolve().parents[1]
A, B = "vendor-a/judge-large", "vendor-b/judge-large"
GEN = "vendor-g/writer"


def run(argv):
    """`main(argv)` as (exit code, stdout, stderr)."""
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = main(argv)
    return code, out.getvalue(), err.getvalue()


def rows_for(task, item, grades_a, grades_b):
    return ([{"task": task, "item": item, "judge": A, "rerun": r, "grade": g} for r, g in enumerate(grades_a)]
            + [{"task": task, "item": item, "judge": B, "rerun": r, "grade": g} for r, g in enumerate(grades_b)])


def faithfulness():
    """Ten items, two reruns each: A and B agree on both reruns of q1 to q9 (truth: odd items
    pass), and on q10 B's second rerun differs, so 9 of 10 are kept, 0.9, the default minimum."""
    rows = []
    for i in range(1, 11):
        truth = "pass" if i % 2 else "fail"
        other = "fail" if truth == "pass" else "pass"
        rows += rows_for("faithfulness", f"q{i}", [truth, truth], [truth, truth if i < 10 else other])
    return rows


def relevance():
    """Two items: r1 kept (both say 1), r2 dropped (A says 1, B says 0), so 1 of 2, 0.5."""
    return rows_for("relevance", "r1", [1, 1], [1, 1]) + rows_for("relevance", "r2", [1, 1], [0, 0])


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
    return path


def argv(grades, out, *more):
    return ["consensus-labels", "--grades", str(grades), "--judges", f"{A},{B}", "--reruns", "2",
            "--out", str(out), *more]


def registry_file(path, family_a="fam-a"):
    row = {"price_in": 3.0, "price_out": 15.0, "context_window": 100_000}
    path.write_text(json.dumps({"models": [dict(row, id=A, family=family_a), dict(row, id=B, family="fam-b"),
                                           dict(row, id=GEN, family="fam-g")]}), encoding="utf-8")
    return path


PASS_TABLE = ("task          items  kept  agreement  passes\n"
              "------------  -----  ----  ---------  ------\n"
              "faithfulness  10     9     0.9000     yes\n")


def test_the_command_and_its_options_are_in_the_help(capsys):
    with pytest.raises(SystemExit) as top:
        main(["--help"])
    assert top.value.code == 0
    assert "consensus-labels" in capsys.readouterr().out
    with pytest.raises(SystemExit) as own:
        main(["consensus-labels", "--help"])
    assert own.value.code == 0
    text = capsys.readouterr().out
    for option in ("--grades FILE", "--judges A,B", "--reruns N", "--out FILE", "--min-agreement M",
                   "--generator MODEL", "--registry PATH"):
        assert option in text, option


def test_every_task_passing_writes_the_label_rows_and_prints_the_table(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    out = tmp_path / "labels.jsonl"
    code, stdout, stderr = run(argv(grades, out))
    assert (code, stderr) == (0, "")
    assert stdout == PASS_TABLE + f"\nwrote 9 label rows to {out}, every task at or above --min-agreement 0.9\n"
    labels = consensus_labels(faithfulness(), [A, B], reruns=2)["labels"]
    assert out.read_bytes() == "".join(json.dumps(row) + "\n" for row in labels).encode("utf-8")
    first = json.loads(out.read_text(encoding="utf-8").splitlines()[0])
    assert first == {"task": "faithfulness", "item": "q1", "gold": "pass", "label_source": "consensus",
                     "consensus_models": [A, B], "reruns": 2, "agreement": 0.9}
    assert [json.loads(line)["item"] for line in out.read_text(encoding="utf-8").splitlines()] == \
        [f"q{i}" for i in range(1, 10)]


def test_the_file_is_replaced_whole_never_appended_to(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    out = tmp_path / "labels.jsonl"
    out.write_text("an older label file\n" * 50, encoding="utf-8")
    assert run(argv(grades, out))[0] == 0
    labels = consensus_labels(faithfulness(), [A, B], reruns=2)["labels"]
    assert out.read_text(encoding="utf-8") == "".join(json.dumps(row) + "\n" for row in labels)


def test_the_minimum_is_the_option_and_is_printed_as_a_float(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    out = tmp_path / "labels.jsonl"
    code, stdout, stderr = run(argv(grades, out, "--min-agreement", "0.85"))
    assert (code, stderr) == (0, "")
    assert stdout.endswith(f"\nwrote 9 label rows to {out}, every task at or above --min-agreement 0.85\n")
    code, stdout, stderr = run(argv(grades, out, "--min-agreement", "0"))
    assert (code, stderr) == (0, "")
    assert stdout.endswith(f"\nwrote 9 label rows to {out}, every task at or above --min-agreement 0.0\n")


def test_a_task_under_the_minimum_exits_3_and_writes_no_file(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness() + relevance())
    out = tmp_path / "labels.jsonl"
    code, stdout, stderr = run(argv(grades, out))
    assert code == 3
    assert stdout == ("task          items  kept  agreement  passes\n"
                      "------------  -----  ----  ---------  ------\n"
                      "faithfulness  10     9     0.9000     yes\n"
                      "relevance     2      1     0.5000     no\n")
    assert stderr == "error: under --min-agreement 0.9 on task relevance: wrote no labels\n"
    assert not out.exists()
    out.write_text("kept as it was\n", encoding="utf-8")
    assert run(argv(grades, out))[0] == 3
    assert out.read_text(encoding="utf-8") == "kept as it was\n"


def test_every_task_under_the_minimum_is_named_in_the_table_order(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", relevance() + faithfulness())
    code, stdout, stderr = run(argv(grades, tmp_path / "labels.jsonl", "--min-agreement", "0.95"))
    assert code == 3
    assert stdout.splitlines()[2].startswith("relevance ")
    assert stderr == "error: under --min-agreement 0.95 on task relevance, faithfulness: wrote no labels\n"
    assert not (tmp_path / "labels.jsonl").exists()


def test_a_generator_with_a_registry_of_other_families_changes_nothing(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    reg = registry_file(tmp_path / "models.json")
    out = tmp_path / "labels.jsonl"
    code, stdout, stderr = run(argv(grades, out, "--generator", GEN, "--registry", str(reg)))
    assert (code, stderr) == (0, "")
    assert stdout == PASS_TABLE + f"\nwrote 9 label rows to {out}, every task at or above --min-agreement 0.9\n"


def test_a_reference_judge_of_the_generators_family_is_refused(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    reg = registry_file(tmp_path / "models.json", family_a="fam-g")
    out = tmp_path / "labels.jsonl"
    code, stdout, stderr = run(argv(grades, out, "--generator", GEN, "--registry", str(reg)))
    assert (code, stdout) == (2, "")
    assert stderr == (f"error: reference judge {A!r} is of the generator's family 'fam-g', "
                      "so it may favour the generator's outputs\n")
    assert not out.exists()


def test_without_registry_the_generator_is_read_from_the_packaged_file(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    packaged = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))["models"][0]["id"]
    code, stdout, stderr = run(argv(grades, tmp_path / "labels.jsonl", "--generator", packaged))
    assert (code, stdout) == (2, "")
    assert stderr == f"error: reference judge {A!r} is not a model of the registry\n"
    code, stdout, stderr = run(argv(grades, tmp_path / "labels.jsonl", "--generator", "vendor-x/none"))
    assert (code, stdout) == (2, "")
    assert stderr == "error: generator_model 'vendor-x/none' is not a model of the registry\n"
    assert not (tmp_path / "labels.jsonl").exists()


@pytest.mark.parametrize("more, line", [
    (["--judges", A], f"error: judges must be a list or tuple of two or more distinct non-empty names, got [{A!r}]"),
    (["--judges", f"{A},{A}"],
     f"error: judges must be a list or tuple of two or more distinct non-empty names, got [{A!r}, {A!r}]"),
    (["--judges", f"{A},"], f"error: judges must be a list or tuple of two or more distinct non-empty names, got [{A!r}, '']"),
    (["--reruns", "0"], "error: reruns must be an integer of at least 1, got 0"),
    (["--min-agreement", "1.5"], "error: min_agreement must be a finite number in [0, 1], got 1.5"),
    (["--min-agreement", "nan"], "error: min_agreement must be a finite number in [0, 1], got nan"),
    (["--min-agreement", "-0.1"], "error: min_agreement must be a finite number in [0, 1], got -0.1"),
])
def test_a_bad_option_value_exits_2_with_nothing_written(tmp_path, more, line):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    out = tmp_path / "labels.jsonl"
    code, stdout, stderr = run(argv(grades, out) + more)
    assert (code, stdout, stderr) == (2, "", line + "\n")
    assert not out.exists()


@pytest.mark.parametrize("more, last", [
    (["--reruns", "two"], "error: argument --reruns: invalid int value: 'two'"),
    (["--min-agreement", "high"], "error: argument --min-agreement: invalid float value: 'high'"),
])
def test_a_value_of_the_wrong_kind_is_a_usage_error(tmp_path, more, last):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    out = tmp_path / "labels.jsonl"
    code, stdout, stderr = run(argv(grades, out) + more)
    assert (code, stdout) == (2, "")
    assert stderr.startswith("usage: ") and stderr.splitlines()[-1] == last
    assert not out.exists()


@pytest.mark.parametrize("missing", ["--grades", "--judges", "--reruns", "--out"])
def test_each_required_option_is_required(tmp_path, missing):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    full = argv(grades, tmp_path / "labels.jsonl")
    at = full.index(missing)
    code, stdout, stderr = run(full[:at] + full[at + 2:])
    assert (code, stdout) == (2, "")
    assert stderr.splitlines()[-1] == f"error: the following arguments are required: {missing}"


def test_a_registry_without_a_generator_is_refused_before_any_file_is_read(tmp_path):
    out = tmp_path / "labels.jsonl"
    code, stdout, stderr = run(argv(tmp_path / "absent.jsonl", out, "--registry", str(tmp_path / "absent.json")))
    assert (code, stdout) == (2, "")
    assert stderr == ("error: --registry needs --generator: the registry is read only to check the reference "
                      "judges' family\n")
    assert not out.exists()


def test_out_naming_an_input_is_refused_and_leaves_it_as_it_was(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    before = grades.read_bytes()
    code, stdout, stderr = run(argv(grades, grades))
    assert (code, stdout, stderr) == (2, "", f"error: --out {grades} names the grades file or the registry\n")
    assert grades.read_bytes() == before
    reg = registry_file(tmp_path / "models.json")
    reg_before = reg.read_bytes()
    code, stdout, stderr = run(argv(grades, reg, "--generator", GEN, "--registry", str(reg)))
    assert (code, stdout, stderr) == (2, "", f"error: --out {reg} names the grades file or the registry\n")
    assert reg.read_bytes() == reg_before


def test_a_missing_or_bad_grades_file_exits_2(tmp_path):
    out = tmp_path / "labels.jsonl"
    code, stdout, stderr = run(argv(tmp_path / "absent.jsonl", out))
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: ") and "absent.jsonl" in stderr and stderr.count("\n") == 1
    bad = tmp_path / "bad.jsonl"
    bad.write_text(json.dumps(faithfulness()[0]) + "\n{not json\n", encoding="utf-8")
    code, stdout, stderr = run(argv(bad, out))
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: ") and "bad.jsonl:2" in stderr and stderr.count("\n") == 1
    assert not out.exists()


def test_a_missing_registry_exits_2(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    out = tmp_path / "labels.jsonl"
    code, stdout, stderr = run(argv(grades, out, "--generator", GEN, "--registry", str(tmp_path / "absent.json")))
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: ") and "absent.json" in stderr and stderr.count("\n") == 1
    assert not out.exists()


def test_repeated_or_missing_grades_exit_2_naming_the_cell(tmp_path):
    out = tmp_path / "labels.jsonl"
    rows = faithfulness()
    grades = write_jsonl(tmp_path / "grades.jsonl", rows + [dict(rows[0])])
    code, stdout, stderr = run(argv(grades, out))
    assert (code, stdout) == (2, "")
    assert stderr == f"error: task 'faithfulness', item 'q1', judge {A!r}: rerun 0 is graded twice\n"
    grades = write_jsonl(tmp_path / "grades.jsonl", rows[:1] + rows[2:])
    code, stdout, stderr = run(argv(grades, out))
    assert (code, stdout) == (2, "")
    assert stderr == f"error: task 'faithfulness', item 'q1', judge {A!r}: rerun 1 is missing\n"
    grades = write_jsonl(tmp_path / "grades.jsonl", [dict(rows[0], grade=0.5)] + rows[1:])
    code, stdout, stderr = run(argv(grades, out))
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: a grade row needs a 'grade' that is a string, a boolean or an integer: ")
    assert not out.exists()


def test_a_file_that_cannot_be_opened_exits_2_with_nothing_on_stdout(tmp_path):
    grades = write_jsonl(tmp_path / "grades.jsonl", faithfulness())
    out = tmp_path / "no-such-dir" / "labels.jsonl"
    code, stdout, stderr = run(argv(grades, out))
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: ") and stderr.count("\n") == 1
    assert not out.parent.exists()


def test_design_and_changelog_state_the_command():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert ("\n- v1.661 `consensus-labels --grades FILE --judges A,B --reruns N --out FILE [--min-agreement M] "
            "[--generator MODEL [--registry PATH]]` (row JUDGE1ba, 4.3 v1.660): ") in design
    assert ("on `promote` a challenger the bar does not admit (v1.603), and on `consensus-labels` a task whose "
            "share of items kept is under `--min-agreement` (v1.661); 4 ") in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    assert sum(line.startswith("- v1.661 (2026-11-26): spec, code, docs and tests (10, row JUDGE1b, first part). ")
               for line in changelog) == 1


def test_readme_layout_names_the_command():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ("  cli.py        model-routing select | calibrate | report | demo | evaluate | delegate | plan | "
            "promote | pairs | drift | consensus-labels\n") in readme


def test_the_production_note_states_the_command_as_shipped():
    text = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    line = [line for line in text.splitlines() if line.startswith("- In this library: judge calls are its first case")]
    assert len(line) == 1
    assert "The changes: a command that writes the labels" not in line[0]
    assert line[0].endswith(
        "its labels measure agreement with those judges, not correctness. From v1.661 `model-routing "
        "consensus-labels` writes those labels to a file only when every task's share of items kept reaches "
        "the minimum. The changes: stats that say where their labels came from; and a self-consistency "
        "minimum, so a judge whose reruns disagree is excluded whatever its bound.")


def test_no_transcript_or_script_runs_the_command():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert "$ model-routing consensus-labels" not in readme
    for folder in ("evidence", "research", ".github"):
        for path in (ROOT / folder).rglob("*"):
            if path.is_file() and path.suffix in (".py", ".yml", ".yaml", ".sh"):
                assert "consensus-labels" not in path.read_text(encoding="utf-8"), path
