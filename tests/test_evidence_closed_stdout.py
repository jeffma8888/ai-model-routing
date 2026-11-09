"""A closed stdout at interpreter exit (DESIGN 12.6, 12.9, 12.11, 12.14, 12.16 and 13.11, v1.150).

Each evidence CLI prints its report with ``flush=True`` before it renames ``<out>.part``, and turns a
``BrokenPipeError`` from that print into one ``error:`` line and exit 2. A failed flush leaves the
report's bytes in the stdout buffer, so before v1.151 the interpreter's own flush at exit tried them
again and the process exited 120 with two more stderr lines. These tests run each script's ``main``
in a child process whose stdout is the write end of a pipe with its read end closed. The child loads
the script from its path and stubs the functions that read data, so nothing is downloaded or read
from the cache, and the report is a 10-character or a 100,000-character string.
"""

import errno
import json
import os
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]

# per script: the lines run after the module `m` is loaded, with `tmp` (a folder) and `SIZE` set
STUBS = {
    "evidence/routerbench/convert.py": """
        m.fetch = lambda cache: None
        m.load_frame = lambda path: None
        m.frame_columns = lambda frame: None
        m.convert = lambda columns, pass_score, min_items: ([], {"report": "x" * SIZE})
    """,
    "evidence/autobench-2026/convert.py": """
        folder = tmp / "files"
        folder.mkdir()
        (folder / "frozen_params.json").write_text('{"top_k": 1, "delta_signal": 0.3}')
        (folder / "pool.json").write_text("[]")
        m.fetch = lambda cache: folder
        m.read_csv = lambda path: []
        m.convert = lambda *args: ([], {"report": "x" * SIZE})
    """,
    "evidence/autobench-2026/judges.py": """
        folder = tmp / "files"
        folder.mkdir()
        (folder / "pool.json").write_text("[]")
        m.convert.fetch = lambda cache: folder
        m.convert.read_csv = lambda path: []
        m.judge_matrix = lambda *args: ([], {"report": "x" * SIZE})
    """,
    "evidence/tau2-bench/convert.py": """
        m.fetch = lambda cache: tmp
        m.read_run = lambda path: None
        m.extract = lambda *args: None
        m.convert = lambda extracts, task_by: ([], {"report": "x" * SIZE})
    """,
    "evidence/livecodebench/convert.py": """
        m.fetch = lambda cache: tmp
        m.read_file = lambda path: None
        m.extract = lambda *args: None
        m.convert = lambda extracts: ([], {"report": "x" * SIZE})
    """,
    "evidence/trail/summary.py": """
        m.fetch = lambda cache: tmp
        m.read_trace = lambda path: None
        m.runs = lambda trace, name: None
        m.summarize = lambda runs: {"report": "x" * SIZE, "runs": []}
    """,
}

CHILD = """
import importlib.util, sys
from pathlib import Path
SIZE = {size}
tmp = Path({tmp!r})
spec = importlib.util.spec_from_file_location("evidence_cli", {path!r})
m = importlib.util.module_from_spec(spec)
spec.loader.exec_module(m)
{stub}
sys.exit(m.main(["--out", str(tmp / "out.jsonl")]))
"""

SIZES = (10, 100_000)  # a report that fits the stdout buffer, and one longer than any buffer size the interpreter picks


def run_child(script, size, tmp, stdout):
    src = CHILD.format(size=size, tmp=str(tmp), path=str(ROOT / script), stub=textwrap.dedent(STUBS[script]))
    return subprocess.run([sys.executable, "-c", src], stdout=stdout, stderr=subprocess.PIPE,
                          cwd=str(tmp), timeout=120)


@pytest.mark.skipif(not hasattr(os, "pipe") or os.name != "posix", reason="needs a POSIX pipe")
@pytest.mark.parametrize("size", SIZES)
@pytest.mark.parametrize("script", sorted(STUBS))
def test_closed_stdout_exits_2_with_one_error_line(script, size, tmp_path):
    out = tmp_path / "out.jsonl"
    out.write_text("old\n")
    read_end, write_end = os.pipe()
    os.close(read_end)
    try:
        proc = run_child(script, size, tmp_path, write_end)
    finally:
        os.close(write_end)
    err = proc.stderr.decode()
    lines = err.splitlines()
    assert len(lines) == 1, err
    assert lines[0].startswith("error: ") and f"[Errno {errno.EPIPE}]" in lines[0], err
    assert proc.returncode == 2, err
    assert out.read_text() == "old\n"
    assert not (tmp_path / "out.jsonl.part").exists()


@pytest.mark.parametrize("script", sorted(STUBS))
def test_open_stdout_prints_the_report_and_exits_0(script, tmp_path):
    proc = run_child(script, SIZES[1], tmp_path, subprocess.PIPE)
    assert proc.returncode == 0, proc.stderr.decode()
    assert proc.stderr == b""
    assert json.loads(proc.stdout) == {"report": "x" * SIZES[1]}
    report = {"report": "x" * SIZES[1]}
    written = json.dumps(dict(report, runs=[]), indent=2) + "\n" if script == "evidence/trail/summary.py" else ""
    assert (tmp_path / "out.jsonl").read_text() == written
    assert not (tmp_path / "out.jsonl.part").exists()
