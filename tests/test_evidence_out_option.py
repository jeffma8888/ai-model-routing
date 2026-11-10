"""The `--out` check of the evidence CLIs that check it before downloading (DESIGN 12.14 v1.171, row H4).

Four CLIs check `--out` before they fetch anything: the tau2-bench converter (12.14), the
LiveCodeBench converter (12.16), the LLMRouterBench converter (12.18) and the TRAIL summary
(13.11). A value whose last `/`-separated part is empty, `.` or `..`, a path or `<out>.part`
that is an existing folder (a link to one counts), or a path whose parent is not an existing
folder is a bad option: `main` returns 2 with one `error: --out` line and nothing on stdout,
and neither fetches nor writes a file. A good value gets past the check to `fetch`.

`PASSED_BEFORE` lists the 27 cases the four v1.170 checks let through to the fetch; they were
held as strict xfail (raising `Downloaded`) until v1.172 put the check in.
"""

import importlib.util
import os
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
CLIS = {
    "tau2-bench": ROOT / "evidence" / "tau2-bench" / "convert.py",
    "livecodebench": ROOT / "evidence" / "livecodebench" / "convert.py",
    "llmrouterbench": ROOT / "evidence" / "llmrouterbench" / "convert.py",
    "trail": ROOT / "evidence" / "trail" / "summary.py",
}
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
}


def _cases():
    for cli in CLIS:
        for case in BAD:
            yield pytest.param(cli, case, id=f"{cli}-{case}")


def _stand_in_fetch(calls):
    def fetch(*args, **kwargs):
        calls.append(args)
        raise Fetched("fetch called")
    return fetch


def _tree(root):
    return sorted(str(p.relative_to(root)) for p in root.rglob("*"))


def test_the_red_cases_are_bad_cases():
    assert set(CLIS) == set(PASSED_BEFORE)
    assert all(cases <= set(BAD) for cases in PASSED_BEFORE.values())
    assert sum(len(cases) for cases in PASSED_BEFORE.values()) == 27


@pytest.mark.parametrize("cli, case", list(_cases()))
def test_a_bad_out_is_refused_before_the_fetch(cli, case, tmp_path, monkeypatch, capsys):
    module = load(cli)
    calls = []
    monkeypatch.setattr(module, "fetch", _stand_in_fetch(calls))
    monkeypatch.chdir(tmp_path)
    value = BAD[case](tmp_path)
    before = _tree(tmp_path)
    try:
        code = module.main(["--out", value])
    except Fetched:
        code = None
    if calls:  # checked first: a CLI whose cleanup masks the stand-in's error still downloaded
        raise Downloaded(f"{cli} called fetch on --out {value!r}")
    assert code == 2  # a return value, never SystemExit from argparse
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1 and captured.err.startswith("error: --out ")
    assert _tree(tmp_path) == before


@pytest.mark.parametrize("cli", list(CLIS))
def test_a_good_out_gets_past_the_check_to_the_fetch(cli, tmp_path, monkeypatch):
    module = load(cli)
    monkeypatch.setattr(module, "fetch", _stand_in_fetch([]))
    monkeypatch.chdir(tmp_path)
    (tmp_path / "sub").mkdir()
    for value in ("m.jsonl", "sub/m.jsonl", str(tmp_path / "sub" / "m.jsonl")):
        with pytest.raises(Fetched):
            module.main(["--out", value])
    assert _tree(tmp_path) == ["sub"]
