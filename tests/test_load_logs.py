"""`load_logs` and `--log PATH` once per log: the logs of many processes as one record stream
(DESIGN 8.2 and 10 v1.620, row PROD1d)."""

import json
from pathlib import Path

import pytest

import model_routing
from model_routing import (
    Completion, Executor, FakeProvider, Model, Monitor, ProviderError, Registry, Router, Stats,
    Task, load_logs, load_records, pair_results, report, shadow_pairs,
)
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
MESSAGES = [{"role": "user", "content": "judge"}]
CHEAP, BEST = "fiction/cheap", "fiction/best"


def router(**fields):
    """cost_effective routes cheap first; the default shadow route is best."""
    task = Task("judge", bar=0.7, min_samples=10, **fields)
    stats = Stats()
    stats.add(task.name, CHEAP, 90, 100)
    stats.add(task.name, BEST, 100, 100)
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000),
                         Model(BEST, "large", 10.0, 20.0, 8000)])
    return Router(registry, {task.name: task}, stats)


def answers(*texts):
    queue = list(texts)

    def complete(messages):
        if not queue:
            raise ProviderError("outage")
        return Completion(queue.pop(0), 1000, 200)
    return complete


def process_log(path, prefix, calls, script, **fields):
    """One process: its own Executor and Monitor on ``path``, call IDs ``<prefix>-<i>``."""
    ids = iter(f"{prefix}-{i}" for i in range(1000))
    ticks = iter(float(i) for i in range(10_000))
    executor = Executor(router(**fields), FakeProvider(script), monitor=Monitor(path),
                        clock=lambda: next(ticks), now=lambda: "2026-11-24T00:00:00Z",
                        id_factory=lambda: next(ids), random=lambda: 0.0)
    for _ in range(calls):
        executor.call("judge", MESSAGES, validate=lambda text: text != "bad")
    return path


def write_jsonl(path, rows):
    path.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return path


def two_processes(tmp):
    """Process a: 2 calls on cheap; process b: 1 call whose cheap attempt fails over to best."""
    a = process_log(tmp / "a.jsonl", "a", 2, {CHEAP: answers("x", "y"), BEST: answers()})
    b = process_log(tmp / "b.jsonl", "b", 1, {CHEAP: answers(), BEST: answers("z")})
    return a, b


def split_pair(tmp):
    """A shadowed run whose shadow records went to another file, as a rotation or a second
    process's log leaves them: the routed records in routed.jsonl, the shadow's in shadow.jsonl."""
    whole = process_log(tmp / "whole.jsonl", "c", 2,
                        {CHEAP: answers("cheap", "cheap"), BEST: answers("best", "bad")},
                        shadow_rate=1.0)
    records = load_records(whole)
    routed = write_jsonl(tmp / "routed.jsonl", [r for r in records if r.get("shadow") is not True])
    shadow = write_jsonl(tmp / "shadow.jsonl", [r for r in records if r.get("shadow") is True])
    return whole, routed, shadow


def run(capsys, *argv):
    code = main([str(a) for a in argv])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


# --- load_logs ------------------------------------------------------------------------------

def test_two_monitors_logs_read_as_their_concatenation_in_the_order_given(tmp_path):
    a, b = two_processes(tmp_path)
    assert load_logs([a, b]) == load_records(a) + load_records(b)
    assert load_logs((str(b), a)) == load_records(b) + load_records(a)
    assert [r["call_id"] for r in load_logs([a, b])] == ["a-0", "a-1", "b-0", "b-0"]


def test_one_path_is_load_records(tmp_path):
    a, _ = two_processes(tmp_path)
    doubled = write_jsonl(tmp_path / "doubled.jsonl", load_records(a) * 2)
    assert load_logs([a]) == load_records(a)
    assert load_logs([doubled]) == load_records(doubled)  # no record compared within a file


def test_a_record_in_an_earlier_file_is_refused_naming_both_places(tmp_path):
    a, b = two_processes(tmp_path)
    copy = write_jsonl(tmp_path / "copy.jsonl", load_records(b)[1:])
    with pytest.raises(ValueError) as info:
        load_logs([a, a])
    assert f"{a}:1" in str(info.value) and "given twice" in str(info.value)
    with pytest.raises(ValueError) as info:
        load_logs([b, copy])
    assert f"{copy}:1" in str(info.value) and f"{b}:2" in str(info.value)


def test_a_reformatted_copy_is_the_same_record(tmp_path):
    a, _ = two_processes(tmp_path)
    reordered = [dict(reversed(list(r.items()))) for r in load_records(a)]
    copy = tmp_path / "copy.jsonl"
    copy.write_text("".join(json.dumps(r, indent=None, separators=(",", ":")) + "\n"
                            for r in reordered), encoding="utf-8")
    with pytest.raises(ValueError, match="copy of one"):
        load_logs([a, copy])


def test_a_call_id_in_two_files_is_one_calls_records(tmp_path):
    _, b = two_processes(tmp_path)
    first, last = load_records(b)
    assert (first["call_id"], first["attempt"], last["attempt"]) == ("b-0", 0, 1)
    before = write_jsonl(tmp_path / "before.jsonl", [first])
    after = write_jsonl(tmp_path / "after.jsonl", [last])
    joined = load_logs([before, after])
    assert joined == [first, last]
    assert report(joined) == report(load_records(b))


def test_bad_paths_raise_before_any_file_is_opened(tmp_path):
    absent = tmp_path / "absent.jsonl"
    for bad in ("calls.jsonl", Path("calls.jsonl"), [], (), None, [absent, 3], {absent: 1}):
        with pytest.raises(ValueError, match="paths"):
            load_logs(bad)


def test_a_bad_later_element_raises_before_the_first_file_is_read(tmp_path, monkeypatch):
    # review iter-472 should-fix 1: an existing first path, and no file is read at all
    a, _ = two_processes(tmp_path)
    import model_routing.monitor as monitor

    def no_read(path):
        raise AssertionError(f"{path} was read before the paths were checked")
    monkeypatch.setattr(monitor, "_numbered_objects", no_read)
    for bad in ([a, 3], (a, None), [a, str(a), b"calls.jsonl"]):
        with pytest.raises(ValueError, match="paths"):
            load_logs(bad)


def test_a_missing_or_bad_file_raises_as_load_records_does(tmp_path):
    a, _ = two_processes(tmp_path)
    with pytest.raises(OSError):
        load_logs([a, tmp_path / "absent.jsonl"])
    bad = tmp_path / "bad.jsonl"
    bad.write_text("\n{not json\n", encoding="utf-8")
    with pytest.raises(ValueError, match=f"{bad}:2"):
        load_logs([a, bad])


def test_a_pair_split_across_two_files_is_joined(tmp_path):
    whole, routed, shadow = split_pair(tmp_path)
    expected = shadow_pairs(load_records(whole), checked=True)
    assert len(expected) == 2
    assert shadow_pairs(load_logs([routed, shadow]), checked=True) == expected
    assert shadow_pairs(load_logs([shadow, routed]), checked=True) == expected
    records = load_logs([routed, shadow])
    assert pair_results(expected, records=records) == pair_results(expected,
                                                                   records=load_records(whole))


def test_exported_right_after_load_audits():
    names = model_routing.__all__
    assert names[names.index("load_audits") + 1] == "load_logs"
    assert names[names.index("load_records") + 1] == "load_audits"


# --- report --log PATH --log PATH -----------------------------------------------------------

def test_report_sums_over_every_log(tmp_path, capsys):
    a, b = two_processes(tmp_path)
    code, out, err = run(capsys, "report", "--log", a, "--log", b, "--json")
    assert (code, err) == (0, "")
    assert json.loads(out) == report(load_records(a) + load_records(b))
    assert sum(row["calls"] for row in json.loads(out)) == 3


def test_report_text_of_one_log_keeps_its_bytes(tmp_path, capsys):
    a, _ = two_processes(tmp_path)
    empty = write_jsonl(tmp_path / "empty.jsonl", [])
    one = run(capsys, "report", "--log", a)
    assert one[0] == 0 and one[2] == ""
    assert run(capsys, "report", "--log", a, "--log", empty) == one
    assert run(capsys, "report", "--log", a, "--json")[1] == json.dumps(
        report(load_records(a)), indent=2) + "\n"


@pytest.mark.parametrize("order", ["first", "last"])
def test_report_a_missing_log_exits_2_wherever_it_is(tmp_path, capsys, order):
    a, _ = two_processes(tmp_path)
    logs = [tmp_path / "absent.jsonl", a] if order == "first" else [a, tmp_path / "absent.jsonl"]
    code, out, err = run(capsys, "report", "--log", logs[0], "--log", logs[1])
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and "absent.jsonl" in err and err.count("\n") == 1


def test_report_a_log_given_twice_exits_2(tmp_path, capsys):
    a, _ = two_processes(tmp_path)
    code, out, err = run(capsys, "report", "--log", a, "--log", a)
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and f"{a}:1" in err and err.count("\n") == 1


# --- pairs --log PATH --log PATH ------------------------------------------------------------

def test_pairs_joins_a_pair_split_across_two_logs(tmp_path, capsys):
    whole, routed, shadow = split_pair(tmp_path)
    out, rows = tmp_path / "pairs.jsonl", tmp_path / "rows.jsonl"
    code, stdout, err = run(capsys, "pairs", "--log", routed, "--log", shadow, "--out", out,
                            "--checked", "--results", rows)
    assert (code, err) == (0, "")
    assert stdout.startswith("wrote 2 pairs to ")
    pairs = shadow_pairs(load_records(whole), checked=True)
    assert out.read_text(encoding="utf-8") == "".join(json.dumps(p) + "\n" for p in pairs)
    assert rows.read_text(encoding="utf-8") == "".join(
        json.dumps(r) + "\n" for r in pair_results(pairs, records=load_records(whole)))


def test_pairs_out_or_results_naming_any_log_exits_2(tmp_path, capsys):
    _, routed, shadow = split_pair(tmp_path)
    before = shadow.read_bytes()
    code, stdout, err = run(capsys, "pairs", "--log", routed, "--log", shadow, "--out", shadow)
    assert (code, stdout) == (2, "") and "names the log" in err
    code, stdout, err = run(capsys, "pairs", "--log", routed, "--log", shadow,
                            "--out", tmp_path / "p.jsonl", "--results", shadow)
    assert (code, stdout) == (2, "") and "names the log" in err
    assert shadow.read_bytes() == before and not (tmp_path / "p.jsonl").exists()


def test_pairs_a_missing_or_repeated_log_exits_2_writing_nothing(tmp_path, capsys):
    _, routed, shadow = split_pair(tmp_path)
    out = tmp_path / "pairs.jsonl"
    for logs in ([tmp_path / "absent.jsonl", routed], [routed, routed]):
        code, stdout, err = run(capsys, "pairs", "--log", logs[0], "--log", logs[1], "--out", out)
        assert (code, stdout) == (2, "") and err.startswith("error: ")
        assert not out.exists()


def test_pairs_a_missing_second_log_exits_2_keeping_out_and_results(tmp_path, capsys):
    # review iter-472 should-fix 2: the second flag, which argparse kept alone until v1.620
    _, routed, _ = split_pair(tmp_path)
    out, rows = tmp_path / "pairs.jsonl", tmp_path / "rows.jsonl"
    out.write_text("old pairs\n", encoding="utf-8")
    rows.write_text("old rows\n", encoding="utf-8")
    code, stdout, err = run(capsys, "pairs", "--log", routed, "--log", tmp_path / "absent.jsonl",
                            "--out", out, "--checked", "--results", rows)
    assert (code, stdout) == (2, "")
    assert err.startswith("error: ") and "absent.jsonl" in err and err.count("\n") == 1
    assert out.read_text(encoding="utf-8") == "old pairs\n"
    assert rows.read_text(encoding="utf-8") == "old rows\n"


# --- the spec and the README ----------------------------------------------------------------

def test_design_changelog_and_readme_state_the_rule():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    assert "- v1.620 `load_logs(paths) -> list[dict]` (row PROD1d)" in design
    assert "  - v1.620 `--log PATH` once per log (row PROD1d)" in design
    assert "- v1.620 `pairs --log PATH [--log PATH ...]` (row PROD1d, 8.2 v1.620)" in design
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8")
    assert changelog.rstrip("\n").split("\n")[-1].startswith("- v1.620 (2026-11-24): spec, code")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    section = readme.split("## Running it in production", 1)[1].split("\n## ", 1)[0]
    sentence = [line for line in section.split("\n") if line.startswith("One `Executor`, with its")]
    assert len(sentence) == 1
    assert sentence[0].endswith(
        "and each process needs a log of its own, which `report` and `pairs` "
        "read together when given `--log PATH` once per log (a rotated log's files oldest first), "
        "refusing a record found in two of them, since a log given twice would count it twice.")
