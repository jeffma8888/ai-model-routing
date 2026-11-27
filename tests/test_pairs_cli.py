"""`model-routing pairs` writes the pair file of a monitor log (DESIGN 10 v1.612, row CANARY1k;
the pair records are `shadow_pairs`, 8.3 v1.610)."""

import json
from pathlib import Path

import pytest

from model_routing import (
    Completion, Executor, FakeProvider, Model, Monitor, ProviderError, Registry, Router, Stats,
    Task, load_audits, load_records, shadow_pairs,
)
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"


def router():
    """cost_effective routes cheap first; the default shadow route is best."""
    task = Task("judge", bar=0.7, min_samples=10, shadow_rate=1.0)
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (MID, (95, 100)),
                                          (BEST, (100, 100))):
        stats.add(task.name, model_id, successes, trials)
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000),
                         Model(BEST, "large", 10.0, 20.0, 8000)])
    return Router(registry, {task.name: task}, stats)


def answers(*texts):
    queue = list(texts)

    def complete(messages):
        if not queue:
            raise ProviderError("outage")
        return Completion(queue.pop(0), 1000, 200)
    return complete


def shadowed_log(path):
    """A real shadowed run with a validate: shadows answer ok, invalid, then err (call-0/1,
    call-2/3, call-4/5), written by a Monitor to ``path``."""
    ids = iter(f"call-{i}" for i in range(1000))
    ticks = iter(float(i) for i in range(10_000))
    script = {CHEAP: answers("cheap", "cheap", "cheap"), BEST: answers("best", "bad")}
    executor = Executor(router(), FakeProvider(script), monitor=Monitor(path),
                        clock=lambda: next(ticks), now=lambda: "2026-11-23T00:00:00Z",
                        id_factory=lambda: next(ids), random=lambda: 0.0)
    for _ in range(3):
        executor.call("judge", MESSAGES, validate=lambda text: text != "bad")
    return path


def lines_of(pairs):
    return "".join(json.dumps(p) + "\n" for p in pairs)


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def run(capsys, *argv):
    code = main(["pairs", *[str(a) for a in argv]])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --- the file it writes --------------------------------------------------------------------------

def test_unlabelled_the_file_is_shadow_pairs_one_json_dumps_per_line(tmp_path, capsys):
    log = shadowed_log(tmp_path / "calls.jsonl")
    out = tmp_path / "pairs.jsonl"
    code, stdout, stderr = run(capsys, "--log", log, "--out", out)
    assert (code, stderr) == (0, "")
    expected = shadow_pairs(load_records(log))
    assert len(expected) == 3
    assert out.read_bytes() == lines_of(expected).encode("utf-8")
    assert stdout == f"wrote 3 pairs to {out}: 0 with both sides labelled\n"


def test_checked_labels_by_the_acceptance_check(tmp_path, capsys):
    log = shadowed_log(tmp_path / "calls.jsonl")
    out = tmp_path / "pairs.jsonl"
    code, stdout, stderr = run(capsys, "--log", log, "--out", out, "--checked")
    assert (code, stderr) == (0, "")
    expected = shadow_pairs(load_records(log), checked=True)
    assert out.read_bytes() == lines_of(expected).encode("utf-8")
    pairs = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert [(p["routed_correct"], p["shadow_correct"]) for p in pairs] == [
        (True, True), (True, False), (True, None)]  # the third shadow erred: no answer
    assert stdout == f"wrote 3 pairs to {out}: 2 with both sides labelled\n"


def test_audits_label_by_call_id(tmp_path, capsys):
    log = shadowed_log(tmp_path / "calls.jsonl")
    audits = write_jsonl(tmp_path / "audits.jsonl", [
        {"call_id": "call-0", "correct": False}, {"call_id": "call-1", "correct": True},
        {"call_id": "call-3", "correct": True}, {"call_id": "call-5", "correct": True}])
    out = tmp_path / "pairs.jsonl"
    code, stdout, stderr = run(capsys, "--log", log, "--out", out, "--audits", audits)
    assert (code, stderr) == (0, "")
    expected = shadow_pairs(load_records(log), audits=load_audits(audits))
    assert out.read_bytes() == lines_of(expected).encode("utf-8")
    pairs = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    # call-2 is unaudited, call-3 invalid (false whatever its audit), call-5 an error side
    assert [(p["routed_correct"], p["shadow_correct"]) for p in pairs] == [
        (False, True), (None, False), (None, None)]
    assert stdout == f"wrote 3 pairs to {out}: 1 with both sides labelled\n"


def test_the_file_is_replaced_whole_never_appended_to(tmp_path, capsys):
    log = shadowed_log(tmp_path / "calls.jsonl")
    out = tmp_path / "pairs.jsonl"
    out.write_text("an older pair file\n", encoding="utf-8")
    assert run(capsys, "--log", log, "--out", out)[0] == 0
    first = out.read_bytes()
    assert first == lines_of(shadow_pairs(load_records(log))).encode("utf-8")
    assert run(capsys, "--log", log, "--out", out)[0] == 0
    assert out.read_bytes() == first


def test_a_log_with_no_shadow_record_gives_an_empty_file(tmp_path, capsys):
    log = write_jsonl(tmp_path / "calls.jsonl", [
        {"call_id": "c1", "task": "judge", "model": CHEAP, "attempt": 0, "final": True,
         "outcome": "ok"}])
    out = tmp_path / "pairs.jsonl"
    code, stdout, stderr = run(capsys, "--log", log, "--out", out)
    assert (code, stdout, stderr) == (0, f"wrote 0 pairs to {out}: 0 with both sides labelled\n", "")
    assert out.read_bytes() == b""


def test_budget_records_are_dropped_as_shadow_pairs_drops_them(tmp_path, capsys):
    log = shadowed_log(tmp_path / "calls.jsonl")
    with log.open("a", encoding="utf-8") as handle:
        handle.write(json.dumps({"budget_event": "refused", "call_id": "call-9", "shadow": True,
                                 "pair_id": "call-9"}) + "\n")
    out = tmp_path / "pairs.jsonl"
    assert run(capsys, "--log", log, "--out", out)[0] == 0
    assert out.read_bytes() == lines_of(shadow_pairs(load_records(log))).encode("utf-8")
    assert len(out.read_text(encoding="utf-8").splitlines()) == 3


# --- refusals: exit 2, one error line, nothing on stdout, FILE neither created nor changed -------

def two_shadows_one_pair(tmp_path):
    rec = {"task": "judge", "attempt": 0, "final": True, "outcome": "ok", "slice": None,
           "pair_id": "p1"}
    return write_jsonl(tmp_path / "calls.jsonl", [
        {**rec, "call_id": "p1", "model": CHEAP, "shadow": False},
        {**rec, "call_id": "s1", "model": BEST, "shadow": True},
        {**rec, "call_id": "s2", "model": BEST, "shadow": True}])


REFUSALS = {
    "both labels": lambda tmp: (["--log", shadowed_log(tmp / "calls.jsonl"), "--checked",
                                 "--audits", write_jsonl(tmp / "audits.jsonl", [])],
                                "error: pass --checked or --audits, not both: their labels could "
                                "disagree\n"),
    "missing log": lambda tmp: (["--log", tmp / "absent.jsonl"], None),
    "bad log line": lambda tmp: (["--log", _text(tmp / "calls.jsonl", "{not json\n")], None),
    "log line not an object": lambda tmp: (["--log", _text(tmp / "calls.jsonl", "[1]\n")], None),
    "missing audits": lambda tmp: (["--log", shadowed_log(tmp / "calls.jsonl"), "--audits",
                                    tmp / "absent.jsonl"], None),
    "bad audits line": lambda tmp: (["--log", shadowed_log(tmp / "calls.jsonl"), "--audits",
                                     write_jsonl(tmp / "audits.jsonl", [{"call_id": "call-0"}])],
                                    None),
    "two shadows of one pair": lambda tmp: (["--log", two_shadows_one_pair(tmp)],
                                            "error: pair_id 'p1' has more than one shadow record\n"),
}


def _text(path, text):
    path.write_text(text, encoding="utf-8")
    return path


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_a_refusal_exits_two_and_writes_nothing(tmp_path, capsys, case, existing):
    argv, message = REFUSALS[case](tmp_path)
    out = tmp_path / "pairs.jsonl"
    if existing:
        out.write_text("an older pair file\n", encoding="utf-8")
    code, stdout, stderr = run(capsys, *argv, "--out", out)
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: ") and stderr.count("\n") == 1 and stderr.endswith("\n")
    if message is not None:
        assert stderr == message
    if existing:
        assert out.read_text(encoding="utf-8") == "an older pair file\n"
    else:
        assert not out.exists()


def test_the_flag_pair_is_refused_before_any_path_is_read(tmp_path, capsys):
    code, stdout, stderr = run(capsys, "--log", tmp_path / "absent.jsonl", "--out", tmp_path / "p.jsonl",
                               "--checked", "--audits", tmp_path / "absent-audits.jsonl")
    assert (code, stdout) == (2, "")
    assert stderr == "error: pass --checked or --audits, not both: their labels could disagree\n"


@pytest.mark.parametrize("alias", ["same", "dot", "symlink"])
@pytest.mark.parametrize("target", ["log", "audits"])
def test_a_file_that_names_the_log_or_the_audits_file_is_refused(tmp_path, capsys, target, alias):
    log = shadowed_log(tmp_path / "calls.jsonl")
    audits = write_jsonl(tmp_path / "audits.jsonl", [{"call_id": "call-0", "correct": True}])
    before = {log: log.read_bytes(), audits: audits.read_bytes()}
    named = {"log": log, "audits": audits}[target]
    if alias == "same":
        alias = str(named)
    elif alias == "dot":   # a string, since pathlib drops a "." part: the same file once resolved
        alias = f"{tmp_path}/./{named.name}"
    else:
        link = tmp_path / "link.jsonl"
        link.symlink_to(named)
        alias = str(link)
    code, stdout, stderr = run(capsys, "--log", log, "--audits", audits, "--out", alias)
    assert (code, stdout) == (2, "")
    assert stderr == f"error: --out {alias} names the log or the audits file\n"
    assert {p: p.read_bytes() for p in before} == before


def test_a_file_that_names_a_missing_log_is_refused_before_the_log_is_read(tmp_path, capsys):
    log = tmp_path / "absent.jsonl"
    code, stdout, stderr = run(capsys, "--log", log, "--out", log)
    assert (code, stdout) == (2, "")
    assert stderr == f"error: --out {log} names the log or the audits file\n"
    assert not log.exists()


@pytest.mark.parametrize("where", ["a directory", "a missing directory"])
def test_a_file_that_cannot_be_opened_exits_two_and_writes_nothing(tmp_path, capsys, where):
    # review iter-463 nit 1: main's OSError handler, after every check and before any write
    log = shadowed_log(tmp_path / "calls.jsonl")
    out = tmp_path / "pairs"
    if where == "a directory":
        out.mkdir()
    else:
        out = out / "pairs.jsonl"
    before = sorted(p.name for p in tmp_path.rglob("*"))
    code, stdout, stderr = run(capsys, "--log", log, "--out", out)
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: ") and stderr.count("\n") == 1
    assert sorted(p.name for p in tmp_path.rglob("*")) == before


def test_the_wrote_line_prints_file_as_a_path_prints_it(tmp_path, capsys):
    # review iter-463 nit 2: as calibrate --outcomes prints its FILE; a refusal prints FILE as given
    log = shadowed_log(tmp_path / "calls.jsonl")
    code, stdout, stderr = run(capsys, "--log", log, "--out", f"{tmp_path}/./pairs.jsonl")
    assert (code, stderr) == (0, "")
    assert stdout == f"wrote 3 pairs to {tmp_path / 'pairs.jsonl'}: 0 with both sides labelled\n"


@pytest.mark.parametrize("missing", ["--log", "--out"])
def test_log_and_out_are_required(tmp_path, capsys, missing):
    argv = {"--log": str(tmp_path / "calls.jsonl"), "--out": str(tmp_path / "pairs.jsonl")}
    argv.pop(missing)
    code, stdout, stderr = run(capsys, *[x for kv in argv.items() for x in kv])
    assert (code, stdout) == (2, "")
    assert f"error: the following arguments are required: {missing}" in stderr


# --- the other commands and the spec ------------------------------------------------------------

def test_report_on_the_same_log_is_unchanged_by_the_command(tmp_path, capsys):
    log = shadowed_log(tmp_path / "calls.jsonl")
    assert main(["report", "--log", str(log), "--shadow"]) == 0
    before = capsys.readouterr()
    assert run(capsys, "--log", log, "--out", tmp_path / "pairs.jsonl")[0] == 0
    assert main(["report", "--log", str(log), "--shadow"]) == 0
    assert capsys.readouterr() == before


def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    assert ten.count("- v1.612 `pairs --log PATH --out FILE [--checked] [--audits PATH]` (row CANARY1k): ") == 1
    assert "`wrote N pairs to FILE: M with both sides labelled`" in ten
    assert "`error: pass --checked or --audits, not both: their labels could disagree`" in ten
    assert "`error: --out FILE names the log or the audits file`" in ten
    assert "while a refusal prints FILE as given (review iter-463 nit 2). " in ten
    assert "nothing on stdout and nothing written (review iter-463 nit 1). " in ten
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert "is the pair file, which `pairs` writes (10 v1.612, row CANARY1k); " in eight3
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.612 (")]
    assert len(mine) == 1 and "(8.3, 10, row CANARY1k)" in mine[0]


def test_readme_names_the_command_in_its_layout_and_its_synopsis_in_the_production_section():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    # v1.634 (row M1c) names drift after pairs
    # v1.661 (row JUDGE1ba) appends consensus-labels, v1.676 (row DEL1c) select-pair
    assert "  cli.py        model-routing select | calibrate | report | demo | evaluate | delegate | plan | promote | pairs | drift | consensus-labels | select-pair\n" in readme
    # v1.619 (row CANARY1e): the synopsis, once, in the second paragraph on shadow calls (tests/test_shadow_docs.py)
    production = readme.split("\n## Running it in production\n", 1)[1].split("\n## ", 1)[0]
    # v1.659 (row PROD1): step 8 of the walk-through names it too (tests/test_readme_walkthrough.py)
    assert readme.count("model-routing pairs") == 2
    assert production.count("`model-routing pairs --log PATH --out FILE`") == 2
