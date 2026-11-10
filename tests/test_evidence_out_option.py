"""The `--out` check of the evidence CLIs that download (DESIGN 12.14 v1.171 and v1.174, rows H4 and H4b).

Seven CLIs check `--out` before they fetch anything: the tau2-bench converter (12.14), the
LiveCodeBench converter (12.16), the LLMRouterBench converter (12.18), the TRAIL summary
(13.11) and, from v1.174, the RouterBench converter (12.6), the AutoBench converter (12.9) and
the AutoBench judges script (12.11), the last two also on `--registry` when it is given, after
`--out` and before their four-files check. A value whose last `/`-separated part is empty, `.`
or `..`, a path or `<path>.part` that is an existing folder (a link to one counts), or a path
whose parent is not an existing folder is a bad option: `main` returns 2 with one
`error: <option>` line and nothing on stdout, and neither fetches nor writes a file. A good
value gets past the check to `fetch`. `judges.py` fetches and checks with the `convert` module
it loads, never a copy, so its stand-in `fetch` goes on that module.

`PASSED_BEFORE` lists the cases each CLI let through to the fetch before it took the check: 27
for the four v1.170 checks, held as strict xfail (raising `Downloaded`) until v1.172, and all
twelve for each of the three v1.173 CLIs, 36, with `REGISTRY_PASSED_BEFORE` the 24 `--registry`
cases, held as strict xfail until v1.175.
"""

import importlib.util
import inspect
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLIS = {
    "tau2-bench": ROOT / "evidence" / "tau2-bench" / "convert.py",
    "livecodebench": ROOT / "evidence" / "livecodebench" / "convert.py",
    "llmrouterbench": ROOT / "evidence" / "llmrouterbench" / "convert.py",
    "trail": ROOT / "evidence" / "trail" / "summary.py",
    "routerbench": ROOT / "evidence" / "routerbench" / "convert.py",
    "autobench": ROOT / "evidence" / "autobench-2026" / "convert.py",
    "autobench-judges": ROOT / "evidence" / "autobench-2026" / "judges.py",
}
REGISTRY_CLIS = ("autobench", "autobench-judges")
_LOADED = {}


class Fetched(Exception):
    """Raised by the stand-in `fetch`: the CLI got past its option checks."""


class Downloaded(AssertionError):
    """A bad `--out` reached `fetch`, where the real CLI would have downloaded."""


def load(name):
    if name not in _LOADED:
        spec = importlib.util.spec_from_file_location(f"out_option_{name.replace('-', '_')}", CLIS[name])
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _LOADED[name] = module
    return _LOADED[name]


def owner(name):
    """The module whose `fetch` and `_check_out` the CLI calls: judges.py uses its loaded `convert`."""
    module = load(name)
    return module.convert if name == "autobench-judges" else module


def _folder(root):
    (root / "adir").mkdir()
    return str(root / "adir")


def _link(root):
    (root / "adir").mkdir()
    os.symlink(root / "adir", root / "alink")
    return "alink"


def _part_folder(root):
    (root / "m.jsonl.part").mkdir()
    return "m.jsonl"


def _file_parent(root):
    (root / "afile").write_text("keep\n", encoding="utf-8")
    return "afile/m.jsonl"


# Each case builds what it needs under the test's folder, the working directory, and returns the value.
BAD = {
    "empty": lambda root: "",
    "dot": lambda root: ".",
    "root": lambda root: "/",
    "dotdot": lambda root: "..",
    "sub-dotdot": lambda root: "sub/..",
    "sub-dot": lambda root: "sub/.",
    "trailing-slash": lambda root: "m.jsonl/",
    "folder": _folder,
    "link-to-folder": _link,
    "part-folder": _part_folder,
    "missing-parent": lambda root: "nodir/m.jsonl",
    "file-parent": _file_parent,
}

# The cases each v1.170 check lets through (to the fetch): tau2-bench refused only an empty name,
# LiveCodeBench and LLMRouterBench also a value ending in `/`, and TRAIL also a name `..`.
PASSED_BEFORE = {
    "tau2-bench": {"dotdot", "sub-dotdot", "sub-dot", "trailing-slash", "folder", "link-to-folder",
                   "part-folder", "missing-parent"},
    "livecodebench": {"dotdot", "sub-dotdot", "sub-dot", "folder", "link-to-folder", "part-folder",
                      "missing-parent"},
    "llmrouterbench": {"dotdot", "sub-dotdot", "sub-dot", "folder", "link-to-folder", "part-folder",
                       "missing-parent"},
    "trail": {"sub-dot", "folder", "link-to-folder", "part-folder", "missing-parent"},
    # v1.173: these three fetched before any --out check, so every bad value downloaded first
    "routerbench": set(BAD),
    "autobench": set(BAD),
    "autobench-judges": set(BAD),
}
REGISTRY_PASSED_BEFORE = {cli: set(BAD) for cli in REGISTRY_CLIS}
LATE = {"routerbench", "autobench", "autobench-judges"}  # the three that took the check in v1.175


def _cases():
    for cli in CLIS:
        for case in BAD:
            yield pytest.param(cli, case, id=f"{cli}-{case}")


def _registry_cases():
    for cli in REGISTRY_CLIS:
        for case in BAD:
            yield pytest.param(cli, case, id=f"{cli}-registry-{case}")


def _stand_in_fetch(calls):
    def fetch(*args, **kwargs):
        calls.append(args)
        raise Fetched("fetch called")
    return fetch


def _tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def test_the_red_cases_are_bad_cases():
    assert set(CLIS) == set(PASSED_BEFORE) and set(REGISTRY_CLIS) <= set(CLIS)
    assert set(REGISTRY_CLIS) == set(REGISTRY_PASSED_BEFORE)
    assert all(cases <= set(BAD) for cases in PASSED_BEFORE.values())
    assert all(cases <= set(BAD) for cases in REGISTRY_PASSED_BEFORE.values())
    assert sum(len(PASSED_BEFORE[cli]) for cli in CLIS if cli not in LATE) == 27
    assert sum(len(PASSED_BEFORE[cli]) for cli in LATE) == 36
    assert sum(len(cases) for cases in REGISTRY_PASSED_BEFORE.values()) == 24


def test_the_checks_are_one_check():
    sources = {cli: inspect.getsource(owner(cli)._check_out) for cli in CLIS}
    assert len(set(sources.values())) == 1, sorted(sources)


def test_judges_has_no_copy_of_the_check():
    assert "_check_out" not in vars(load("autobench-judges"))


def _refused(cli, argv, option, tmp_path, monkeypatch, capsys, value):
    calls = []
    monkeypatch.setattr(owner(cli), "fetch", _stand_in_fetch(calls))
    before = _tree(tmp_path)
    try:
        code = load(cli).main(argv)
    except Fetched:
        code = None
    if calls:  # checked first: a CLI whose cleanup masks the stand-in's error still downloaded
        raise Downloaded(f"{cli} called fetch on {option} {value!r}")
    assert code == 2  # a return value, never SystemExit from argparse
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1 and captured.err.startswith(f"error: {option} ")
    assert _tree(tmp_path) == before


@pytest.mark.parametrize("cli, case", list(_cases()))
def test_a_bad_out_is_refused_before_the_fetch(cli, case, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    value = BAD[case](tmp_path)
    _refused(cli, ["--out", value], "--out", tmp_path, monkeypatch, capsys, value)


@pytest.mark.parametrize("cli, case", list(_registry_cases()))
def test_a_bad_registry_is_refused_before_the_fetch(cli, case, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    value = BAD[case](tmp_path)
    _refused(cli, ["--out", "out.jsonl", "--registry", value], "--registry", tmp_path, monkeypatch, capsys,
             value)


@pytest.mark.parametrize("cli", REGISTRY_CLIS)
def test_out_is_checked_before_registry_and_registry_before_the_four_files(cli, tmp_path, monkeypatch, capsys):
    monkeypatch.chdir(tmp_path)
    _refused(cli, ["--out", "", "--registry", ""], "--out", tmp_path, monkeypatch, capsys, "")
    _refused(cli, ["--out", "m.jsonl", "--registry", "m.jsonl/"], "--registry", tmp_path, monkeypatch, capsys,
             "m.jsonl/")


def _good(cli, argvs, tmp_path, monkeypatch):
    monkeypatch.setattr(owner(cli), "fetch", _stand_in_fetch([]))
    for argv in argvs:
        with pytest.raises(Fetched):
            load(cli).main(argv)
    assert _tree(tmp_path) == ["old.jsonl", "sub"]
    assert (tmp_path / "old.jsonl").read_text(encoding="utf-8") == "old\n"


def _good_values(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub").mkdir()
    (tmp_path / "old.jsonl").write_text("old\n", encoding="utf-8")  # a rerun over an existing file
    return ("m.jsonl", "sub/m.jsonl", str(tmp_path / "sub" / "m.jsonl"), "old.jsonl")


@pytest.mark.parametrize("cli", list(CLIS))
def test_a_good_out_gets_past_the_check_to_the_fetch(cli, tmp_path, monkeypatch):
    values = _good_values(tmp_path, monkeypatch)
    _good(cli, [["--out", value] for value in values], tmp_path, monkeypatch)


@pytest.mark.parametrize("cli", REGISTRY_CLIS)
def test_a_good_registry_gets_past_the_check_to_the_fetch(cli, tmp_path, monkeypatch):
    values = _good_values(tmp_path, monkeypatch)
    _good(cli, [["--out", "out.jsonl", "--registry", value] for value in values], tmp_path, monkeypatch)
