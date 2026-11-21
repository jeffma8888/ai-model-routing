"""DESIGN 7 v1.551 (row ESC3o): the LiveCodeBench cascade replay CLI on the pinned files.

`python evidence/livecodebench/cascades.py --out PATH [--cache DIR] [--release NAME]` downloads the 67
kept files with the converter's `fetch` and the release files with `fetch_release` of
research/escalation_public_tests.py, writes the 12.16 `--labels` matrix of the kept problems those files
hold with the cascade rows of `setting_cascades`, and prints a report. These tests were committed before
the code under a module-level strict xfail whose error, AttributeError, is the one a missing attribute of
a loaded script raises, and the implementing commit removed the mark. They write stub kept files and
release lines, with their sizes and sha256, into a temporary cache, so nothing downloads; one, skipped
unless the 67 kept files and test3.jsonl are cached, compares the report with the ESC1c table of
research/escalation.md.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "livecodebench" / "cascades.py"
NOTE = ROOT / "research" / "escalation.md"
P, PN = "public-test-failed", "public-test-failed-or-no-test"
LOW, HIGH, GPT = "openai/o4-mini-low", "openai/o4-mini-high", "openai/gpt-4-0613"
FOLDERS = {"O4-Mini (Low)": LOW, "O4-Mini (High)": HIGH, "GPT-4-0613": GPT}
KEYS = ["submissions", "release", "task", "items", "difficulty", "models", "cascades", "rows", "kinds",
        "escalated"]
LEVEL = {"q1": "easy", "q2": "medium", "q3": "hard", "q4": "easy", "q5": "medium", "q6": "hard",
         "q7": "easy", "q8": "hard"}
# the release file of each problem; q7 is in no kept file and q8 in one kept file only
WHERE = {"test.jsonl": ["q1", "q2"], "test2.jsonl": ["q3"], "test3.jsonl": ["q4", "q5"],
         "test4.jsonl": ["q6", "q7"]}
PUBLIC = {"inputs": "1\n", "expected": "2\n", "output": "3\n", "error_code": -2}
OTHER = {"inputs": "9\n", "expected": "8\n", "output": "7\n", "error_code": -2}
NO_TEST = {"error_code": -4, "error_message": "boom"}
# per folder and problem: (first sample passed, its failing test's metadata)
SAMPLES = {
    "O4-Mini (Low)": {"q1": (True, None), "q2": (False, PUBLIC), "q3": (False, OTHER), "q4": (False, NO_TEST),
                      "q5": (True, None), "q6": (False, PUBLIC)},
    "O4-Mini (High)": {"q1": (True, None), "q2": (True, None), "q3": (True, None), "q4": (True, None),
                       "q5": (True, None), "q6": (False, PUBLIC), "q8": (True, None)},
    "GPT-4-0613": {"q1": (False, OTHER), "q2": (True, None), "q3": (False, PUBLIC), "q4": (True, None),
                   "q5": (False, NO_TEST), "q6": (True, None)},
}

_loaded = []


def m():
    if not _loaded:
        spec = importlib.util.spec_from_file_location("livecodebench_cascades_cli", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _loaded.append(module)
    return _loaded[0]


def _pin(path):
    return (path.stat().st_size, hashlib.sha256(path.read_bytes()).hexdigest())


def _record(qid, passed, meta):
    rec = {"question_id": qid, "contest_date": "2024-06-01T00:00:00", "difficulty": LEVEL[qid],
           "graded_list": [passed, not passed], "code_list": ["x"]}
    rec["metadata"] = [json.dumps({"execution time": 0.1} if passed else meta), "{}"]
    return rec


def _line(qid, empty=False):
    cases = [{"input": "1\n", "output": "2\n", "testtype": "stdin"}, {"input": "4\n", "output": "5\n",
                                                                      "testtype": "stdin"}]
    cases = [] if empty else cases  # v1.552: a problem with no public case, as abc350_c of test2.jsonl
    return json.dumps({"question_id": qid, "contest_date": "2024-06-01T00:00:00",
                       "public_test_cases": json.dumps(cases), "metadata": "{}",
                       "private_test_cases": "never read"})


class NoNetwork(AssertionError):
    pass


def _no_network(*args, **kwargs):
    raise NoNetwork("a stub run opened a URL")


def stub(tmp_path, monkeypatch, where=None, samples=None, empty=()):
    """A temporary cache of stub kept files and release files, pinned by their own size and sha256."""
    mod = m()
    cache = tmp_path / "cache"
    files = {}
    for folder, cells in sorted((samples or SAMPLES).items()):
        path = cache / folder / "Scenario.json"
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps([_record(q, *cell) for q, cell in cells.items()]), encoding="utf-8")
        files[f"{folder}/Scenario.json"] = _pin(path)
    pins = dict(mod.public_tests.RELEASE_FILES)
    (cache / "release").mkdir()
    for name, qids in (where or WHERE).items():
        path = cache / "release" / name
        path.write_text("".join(_line(q, q in empty) + "\n" for q in qids), encoding="utf-8")
        pins[name] = _pin(path)
    monkeypatch.setattr(mod.convert, "FILES", dict(sorted(files.items())))
    monkeypatch.setattr(mod.public_tests, "RELEASE_FILES", pins)
    monkeypatch.setattr(urllib.request, "urlopen", _no_network)
    return cache


def run(argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = m().main(argv)
    return code, out.getvalue(), err.getvalue()


def _rows(path):
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines()]


def _tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


# --- a run on stub files -------------------------------------------------------------------------------

def test_a_run_writes_the_matrix_with_the_cascade_rows(tmp_path, monkeypatch):
    cache = stub(tmp_path, monkeypatch)
    code, out, err = run(["--out", str(tmp_path / "m.jsonl"), "--cache", str(cache)])
    assert (code, err) == (0, "")
    rows = _rows(tmp_path / "m.jsonl")
    cid = {s: f"{LOW}>{HIGH}@{s}" for s in (P, PN)}
    assert [(r["item"], r["model"]) for r in rows] == sorted(
        (q, model) for q in ("q1", "q2", "q3", "q4", "q5", "q6") for model in [LOW, HIGH, GPT] + list(cid.values()))
    assert all(r["task"] == "code_generation" and r["cost_usd"] == 0.0 for r in rows)
    assert {r["item"]: r["difficulty"] for r in rows} == {
        "q1": "1-easy", "q2": "2-medium", "q3": "3-hard", "q4": "1-easy", "q5": "2-medium", "q6": "3-hard"}
    got = {(r["model"], r["item"]): (r["correct"], r["escalated"]) for r in rows if "escalated" in r}
    assert got == {
        (cid[P], "q1"): (True, False), (cid[P], "q2"): (True, True), (cid[P], "q3"): (False, False),
        (cid[P], "q4"): (False, False), (cid[P], "q5"): (True, False), (cid[P], "q6"): (False, True),
        (cid[PN], "q1"): (True, False), (cid[PN], "q2"): (True, True), (cid[PN], "q3"): (False, False),
        (cid[PN], "q4"): (True, True), (cid[PN], "q5"): (True, False), (cid[PN], "q6"): (False, True)}
    assert not (tmp_path / "m.jsonl.part").exists()


def test_a_problem_with_no_public_case_is_read_and_never_handed_up_on_a_public_test(tmp_path, monkeypatch):
    # v1.552 (row ESC3p): q2's release line has public_test_cases "[]"; the low run's failed q2 sample
    # recorded the inputs and expected of the other problems' first public case, so it is now `other`
    cache = stub(tmp_path, monkeypatch, empty=("q2",))
    code, out, err = run(["--out", str(tmp_path / "m.jsonl"), "--cache", str(cache)])
    assert (code, err) == (0, "")
    report = json.loads(out)
    zero = dict.fromkeys(("failed",) + m().KINDS, 0)
    assert report["items"] == 6
    assert report["kinds"][LOW] == {**zero, "failed": 4, "public": 1, "other": 2, "no_test": 1}
    assert report["escalated"] == {f"{LOW}>{HIGH}@{P}": 1, f"{LOW}>{HIGH}@{PN}": 2}
    rows = {(r["model"], r["item"]): r for r in _rows(tmp_path / "m.jsonl")}
    for signal in (P, PN):
        assert {k: rows[(f"{LOW}>{HIGH}@{signal}", "q2")][k] for k in ("correct", "escalated")} == {
            "correct": False, "escalated": False}


def test_the_report_states_the_revisions_items_kinds_and_hand_ups(tmp_path, monkeypatch):
    cache = stub(tmp_path, monkeypatch)
    code, out, _ = run(["--out", str(tmp_path / "m.jsonl"), "--cache", str(cache)])
    report = json.loads(out)
    assert code == 0 and list(report) == KEYS and out == json.dumps(report, indent=2) + "\n"
    mod = m()
    assert report["submissions"] == mod.convert.REVISION
    assert report["release"] == {"revision": mod.public_tests.RELEASE_REVISION, "files": list(mod.RELEASE)}
    assert (report["task"], report["items"], report["models"], report["cascades"], report["rows"]) == (
        "code_generation", 6, 3, 2, 30)
    assert report["difficulty"] == {"1-easy": 2, "2-medium": 2, "3-hard": 2}
    zero = dict.fromkeys(("failed",) + mod.KINDS, 0)
    assert report["kinds"] == {
        GPT: {**zero, "failed": 3, "public": 1, "other": 1, "no_test": 1},
        HIGH: {**zero, "failed": 1, "public": 1},
        LOW: {**zero, "failed": 4, "public": 2, "other": 1, "no_test": 1}}
    assert list(report["kinds"][LOW]) == ["failed", "public", "other", "input_only", "no_test", "unread"]
    assert report["escalated"] == {f"{LOW}>{HIGH}@{P}": 2, f"{LOW}>{HIGH}@{PN}": 3}


def test_release_reads_only_the_named_files_in_release_order(tmp_path, monkeypatch):
    cache = stub(tmp_path, monkeypatch)
    seen = []
    real = m().public_tests.fetch_release
    monkeypatch.setattr(m().public_tests, "fetch_release",
                        lambda folder, names, convert: seen.append(list(names)) or real(folder, names, convert))
    code, out, _ = run(["--out", str(tmp_path / "m.jsonl"), "--cache", str(cache), "--release", "test3.jsonl",
                        "--release", "test.jsonl"])
    report = json.loads(out)
    assert code == 0 and seen == [["test.jsonl", "test3.jsonl"]]
    assert report["release"]["files"] == ["test.jsonl", "test3.jsonl"]
    assert report["items"] == 4 and report["rows"] == 4 * 5
    assert sorted({r["item"] for r in _rows(tmp_path / "m.jsonl")}) == ["q1", "q2", "q4", "q5"]
    assert report["kinds"][LOW]["failed"] == 2 and report["escalated"] == {f"{LOW}>{HIGH}@{P}": 1,
                                                                          f"{LOW}>{HIGH}@{PN}": 2}


def test_a_cached_file_is_checked_and_a_bad_one_refused(tmp_path, monkeypatch):
    cache = stub(tmp_path, monkeypatch)
    (cache / "release" / "test2.jsonl").write_text(_line("q3") + "\n" + _line("q9") + "\n", encoding="utf-8")
    old = tmp_path / "m.jsonl"
    old.write_text("old\n", encoding="utf-8")
    code, out, err = run(["--out", str(old), "--cache", str(cache)])
    assert (code, out) == (2, "") and err.startswith("error: test2.jsonl: size ")
    assert old.read_text(encoding="utf-8") == "old\n" and not (tmp_path / "m.jsonl.part").exists()


# --- refusals -------------------------------------------------------------------------------------------

class Fetched(Exception):
    pass


@pytest.mark.parametrize("argv, needle", [
    (["--release", "test5.jsonl"], "--release 'test5.jsonl'"),
    (["--release", "x.jsonl"], "--release 'x.jsonl'"),
    (["--release", ""], "--release ''"),
    (["--release", "test3.jsonl", "--release", "test3.jsonl"], "--release 'test3.jsonl'"),
])
def test_a_bad_release_fetches_nothing(argv, needle, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(m().convert, "fetch", lambda *a, **k: calls.append(a) or (_ for _ in ()).throw(Fetched()))
    monkeypatch.setattr(m().public_tests, "fetch_release", lambda *a, **k: calls.append(a))
    code, out, err = run(["--out", "m.jsonl"] + argv)
    assert (code, out, calls) == (2, "", [])
    assert len(err.splitlines()) == 1 and err.startswith("error: " + needle)
    assert _tree(tmp_path) == []


@pytest.mark.parametrize("argv", [[], ["--out", "m.jsonl", "--bogus"], ["--out", "m.jsonl", "--release"]])
def test_an_unknown_or_missing_option_fetches_nothing(argv, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    calls = []
    monkeypatch.setattr(m().convert, "fetch", lambda *a, **k: calls.append(a))
    code, out, err = run(argv)
    assert (code, out, calls) == (2, "", []) and len(err.splitlines()) == 1 and err.startswith("error: ")
    assert _tree(tmp_path) == []


def test_out_is_checked_before_release(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    code, _, err = run(["--out", "", "--release", "x.jsonl"])
    assert code == 2 and err.startswith("error: --out must end in a file name")


def test_a_problem_in_two_release_files_is_refused_naming_it(tmp_path, monkeypatch):
    where = dict(WHERE, **{"test4.jsonl": ["q6", "q7", "q4"]})
    cache = stub(tmp_path, monkeypatch, where=where)
    (tmp_path / "m.jsonl.part").write_text("stale\n", encoding="utf-8")
    code, out, err = run(["--out", str(tmp_path / "m.jsonl"), "--cache", str(cache)])
    assert (code, out) == (2, "") and err == "error: test4.jsonl: question_id q4 is in two release files\n"
    assert not (tmp_path / "m.jsonl").exists() and not (tmp_path / "m.jsonl.part").exists()


def test_all_four_files_must_hold_every_kept_problem(tmp_path, monkeypatch):
    cache = stub(tmp_path, monkeypatch, where=dict(WHERE, **{"test4.jsonl": ["q7"]}))
    code, _, err = run(["--out", str(tmp_path / "m.jsonl"), "--cache", str(cache)])
    assert code == 2 and err == "error: 1 kept problems are in no release file, the first q6\n"
    code, out, _ = run(["--out", str(tmp_path / "m.jsonl"), "--cache", str(cache), "--release", "test.jsonl"])
    assert code == 0 and json.loads(out)["items"] == 2


def test_no_kept_problem_in_the_files_read_is_refused(tmp_path, monkeypatch):
    cache = stub(tmp_path, monkeypatch, where=dict(WHERE, **{"test4.jsonl": ["q7"]}))
    code, _, err = run(["--out", str(tmp_path / "m.jsonl"), "--cache", str(cache), "--release", "test4.jsonl"])
    assert code == 2 and err == "error: no kept problem is in the release files read\n"


def test_a_failed_print_leaves_out_as_it_was(tmp_path, monkeypatch):
    cache = stub(tmp_path, monkeypatch)
    old = tmp_path / "m.jsonl"
    old.write_text("old\n", encoding="utf-8")

    def broken(text):
        raise BrokenPipeError("pipe closed")
    monkeypatch.setattr(m().convert, "print_report", broken)
    code, _, err = run(["--out", str(old), "--cache", str(cache)])
    assert code == 2 and err == "error: pipe closed\n"
    assert old.read_text(encoding="utf-8") == "old\n" and not (tmp_path / "m.jsonl.part").exists()


# --- through the loaded code -------------------------------------------------------------------------

def test_the_downloads_and_reads_go_through_the_loaded_code(tmp_path, monkeypatch):
    cache = stub(tmp_path, monkeypatch)
    mod = m()
    calls = []
    for owner, name in ((mod.convert, "fetch"), (mod.convert, "read_file"), (mod.public_tests, "fetch_release"),
                        (mod.public_tests, "read_release"), (mod.convert, "write_jsonl")):
        real = getattr(owner, name)
        monkeypatch.setattr(owner, name, lambda *a, _real=real, _name=name, **k: calls.append(_name) or _real(*a, **k))
    assert run(["--out", str(tmp_path / "m.jsonl"), "--cache", str(cache)])[0] == 0
    assert calls == (["fetch", "fetch_release"] + ["read_release"] * 4 + ["read_file"] * 3 + ["write_jsonl"])


def test_fetch_release_downloads_each_named_file_by_its_pin(tmp_path, monkeypatch):
    pt = m().public_tests
    seen = []
    monkeypatch.setattr(pt, "_download", lambda url, target, size, sha256, convert: seen.append(
        (url, target, size, sha256, convert)) or target)
    got = pt.fetch_release(tmp_path, ["test.jsonl", "test4.jsonl"], m().convert)
    base = f"https://huggingface.co/datasets/{pt.RELEASE_REPO}/resolve/{pt.RELEASE_REVISION}/"
    assert seen == [(base + name, tmp_path / "release" / name, *pt.RELEASE_FILES[name], m().convert)
                    for name in ("test.jsonl", "test4.jsonl")]
    assert got == {name: tmp_path / "release" / name for name in ("test.jsonl", "test4.jsonl")}


def test_the_research_fetch_reads_its_sample_through_fetch_release(tmp_path, monkeypatch):
    pt = m().public_tests
    seen, downloads = [], []
    monkeypatch.setattr(pt, "_download", lambda url, target, *rest: downloads.append(url) or target)
    real = pt.fetch_release
    monkeypatch.setattr(pt, "fetch_release", lambda folder, names, convert: seen.append(tuple(names)) or real(
        folder, names, convert))
    paths = pt.fetch(tmp_path, m().convert)
    assert seen == [pt.SAMPLE] and list(paths) == list(pt.SAMPLE) + list(pt.RUNNER_FILES)
    assert len(downloads) == len(pt.SAMPLE) + len(pt.RUNNER_FILES)


def test_design_and_changelog_state_the_cli():
    assert "v1.551" in m().main.__doc__ and "v1.551" in m().public_tests.fetch_release.__doc__
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    for phrase in ("`python evidence/livecodebench/cascades.py --out PATH [--cache DIR] [--release NAME]`",
                   "`public_tests.fetch_release(folder, names, convert)`", "No runner file is read",
                   "a stale one included", "with `--release test3.jsonl` the report's `kinds` are the table"):
        assert phrase in text, phrase
    log = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in log if line.startswith("- v1.551 (")]
    assert len(mine) == 1 and "(7, row ESC3o)" in mine[0]


# --- the cached files -----------------------------------------------------------------------------------

def _table():
    """{model: {failed, public, other, input_only, no_test, unread}} of research/escalation.md's ESC1c block."""
    text = NOTE.read_text(encoding="utf-8")
    block = text.split("\n## Public tests matched (row ESC1c)\n", 1)[1].split("```text\n", 1)[1].split("```", 1)[0]
    lines = block.splitlines()
    head = next(k for k, line in enumerate(lines) if line.startswith("model ") and "public_share" in line)
    table = {}
    for line in lines[head + 2:]:
        if not line.strip():
            break
        cells = line.split()
        if cells[0] != "all":
            table[cells[0]] = dict(zip(("failed", "public", "other", "input_only", "no_test", "unread"),
                                       (int(c.replace(",", "")) for c in cells[2:8])))
    return table


def _cached():
    convert = m().convert
    root = convert.default_cache_dir()
    return (root / "release" / "test3.jsonl").exists() and all((root / name).exists() for name in convert.FILES)


@pytest.mark.skipif(not _cached(), reason="the 67 kept files and test3.jsonl are not in the default cache")
def test_the_test3_report_is_the_esc1c_table(tmp_path):
    code, out, err = run(["--out", str(tmp_path / "m.jsonl"), "--release", "test3.jsonl"])
    assert (code, err) == (0, "")
    report = json.loads(out)
    table = _table()
    assert len(table) == 67 and report["kinds"] == table
    assert (report["items"], report["models"], report["cascades"], report["rows"]) == (101, 67, 22, 101 * 89)
    assert report["difficulty"] == {"1-easy": 34, "2-medium": 39, "3-hard": 28}
    assert len(_rows(tmp_path / "m.jsonl")) == 101 * 89
    for cid, n in report["escalated"].items():
        cheap, signal = cid.split(">")[0], cid.split("@")[1]
        assert n == table[cheap]["public"] + (table[cheap]["no_test"] if signal == PN else 0), cid
