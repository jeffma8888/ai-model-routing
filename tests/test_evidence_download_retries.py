"""DESIGN.md 12.13 v1.406 (row CI23): each of the download functions the `evidence` job calls tries a
missing file up to `ATTEMPTS = 3` times, at once, each attempt rewriting `<name>.part` from its first
byte. An attempt whose `urlopen` or read raises an `Exception` other than a `ValueError` (13.15 and
`fetch_tools`: any `Exception`) is retried, and the last attempt's error is raised as each module
raised it before; a download that fails `verify` and a `BaseException` are never retried. Each
module's own fetch tests keep their cases: a failure on every attempt is the same error after three
calls.

v1.545 (row ESC3h): the functions are nine, the `fetch` of 12.9, 12.14, 12.16, 12.18, 12.20, 12.23,
12.25 and 13.15 and `fetch_tools` in research/escalation_signals.py, which the job calls through
evidence/tau2-bench/cascades.py for the three `tools.py` files; until v1.545 it tried each once, and
12.23 and 12.25 retried from v1.443 and v1.489 but were not tested here.
"""

import functools
import hashlib
import importlib.util
import io
import re
import time
import urllib.parse
import urllib.request
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "DESIGN.md"
SCRIPTS = {
    "autobench": "evidence/autobench-2026/convert.py",
    "tau2": "evidence/tau2-bench/convert.py",
    "livecodebench": "evidence/livecodebench/convert.py",
    "llmrouterbench": "evidence/llmrouterbench/convert.py",
    "response_bank": "evidence/response-bank/convert.py",
    "ledger": "evidence/ledger-handoff/results.py",
    "registry_pair": "evidence/registry-pair/convert.py",
    "longtail_swe": "evidence/longtail-swe/convert.py",
    "tools": "research/escalation_signals.py",  # fetch_tools, called through evidence/tau2-bench/cascades.py
}
SECTIONS = ("12.9", "12.14", "12.16", "12.18", "12.20", "12.23", "12.25", "13.15")  # each `fetch` of SCRIPTS
WRAPS_NONE = {"autobench"}  # 12.9 raises a download error as it is, not as an OSError naming the file
# 13.15 and fetch_tools report every download error, a ValueError included, as one
WRAPS_VALUE_ERROR = {"ledger", "tools"}
WORKFLOW = ROOT / ".github" / "workflows" / "evidence.yml"
BODY = b'{"a": 1}\n'
OTHER = b'{"a": 2}\n'  # the same size, another sha256


def load(key):
    spec = importlib.util.spec_from_file_location(f"retries_{key}", ROOT / SCRIPTS[key])
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def pin(key, mod, monkeypatch, cache):
    """Pin one file holding BODY (for 12.9 its SHA256SUMS too); return {url: body} in download
    order and the path the file lands at."""
    entry = (len(BODY), hashlib.sha256(BODY).hexdigest())
    if key == "llmrouterbench":
        monkeypatch.setattr(mod, "SIZE", entry[0])
        monkeypatch.setattr(mod, "SHA256", entry[1])
        return {mod.URL: BODY}, cache / mod.FILE
    if key == "autobench":
        sums = f"{entry[1]}  m.csv\n".encode()
        monkeypatch.setattr(mod, "FILES", {"m.csv": entry, mod.SUMS: (len(sums), hashlib.sha256(sums).hexdigest())})
        return {mod.BASE_URL + "m.csv": BODY, mod.BASE_URL + mod.SUMS: sums}, cache / "m.csv"
    if key == "tau2":
        monkeypatch.setattr(mod, "FILES", {"a.json": entry})
        return {mod.BASE_URL + "a.json": BODY}, cache / "a.json"
    if key == "livecodebench":
        monkeypatch.setattr(mod, "FILES", {"A b/x.json": entry})
        return {mod.BASE_URL + urllib.parse.quote("A b/x.json"): BODY}, cache / "A b" / "x.json"
    if key == "response_bank":
        monkeypatch.setattr(mod, "FILES", {"scores_cal.jsonl": entry})
        return {mod.url("scores_cal.jsonl"): BODY}, cache / "scores_cal.jsonl"
    if key in ("registry_pair", "longtail_swe"):
        monkeypatch.setattr(mod, "FILES", {"a.json": entry})
        return {mod.url("a.json"): BODY}, cache / "a.json"
    if key == "tools":
        # fetch_tools(folder, convert) takes the 12.14 converter for its verify, REPO and REVISION
        convert = load("tau2")
        monkeypatch.setattr(mod, "TOOL_FILES", {"airline": entry})
        monkeypatch.setattr(mod, "fetch", functools.partial(mod.fetch_tools, convert=convert), raising=False)
        url = (f"https://raw.githubusercontent.com/{convert.REPO}/{convert.REVISION}/"
               "src/tau2/domains/airline/tools.py")
        return {url: BODY}, cache / "airline-tools.py"
    assert key == "ledger"
    monkeypatch.setattr(mod, "FILES", {"data/ledger/a.jsonl": entry})
    return {mod.BASE_URL + "data/ledger/a.jsonl": BODY}, cache / "a.jsonl"


class Broken:
    """A response that gives a few bytes and then fails, as a read that times out mid-file does."""

    def __init__(self, error):
        self.error = error
        self.reads = 0

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self, *args):
        self.reads += 1
        if self.reads == 1:
            return b"partial bytes, longer than the file"
        raise self.error


def serve(monkeypatch, served, failures, url_failures=None):
    """A urlopen whose first len(failures) calls for the first URL of `served` (or, with
    `url_failures`, for each URL it maps) fail, each with its failure (raised at the open, or
    mid-read for a Broken), and whose later calls serve `served` by URL; returns the calls, each its
    URL, or (URL, timeout) for a timeout other than 60, with a ("sleep", seconds) entry for any
    pause, since the attempts follow one another at once (review iter-266 should-fix 3 and nit 5)."""
    pending = {url: list(fs) for url, fs in (url_failures or {next(iter(served)): failures}).items()}
    calls = []

    def urlopen(url, timeout=None):
        calls.append(url if timeout == 60 else (url, timeout))
        if pending.get(url):
            failure = pending[url].pop(0)
            if isinstance(failure, Broken):
                return failure
            raise failure
        return io.BytesIO(served[url])

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
    monkeypatch.setattr(time, "sleep", lambda seconds: calls.append(("sleep", seconds)))
    return calls


def setup(key, monkeypatch, tmp_path):
    mod = load(key)
    cache = tmp_path / "cache"
    served, dest = pin(key, mod, monkeypatch, cache)
    return mod, cache, served, dest, next(iter(served))


FAILURES = {
    "at-open": lambda: [TimeoutError("The read operation timed out"), ConnectionResetError("reset")],
    # RuntimeError stands in for an HTTP protocol error such as http.client.IncompleteRead, not an OSError
    "mid-read": lambda: [Broken(TimeoutError("The read operation timed out")), Broken(RuntimeError("incomplete read"))],
}


@pytest.mark.parametrize("key", list(SCRIPTS))
def test_each_module_tries_three_times(key):
    assert load(key).ATTEMPTS == 3


def test_each_script_the_job_runs_that_downloads_is_tested_here():
    # v1.545 (row ESC3h): a downloader the workflow runs outside SCRIPTS would be outside the rule's tests,
    # as fetch_tools was, through cascades.py, until v1.545 (cascades.py itself holds no urlopen).
    run = sorted(set(re.findall(r"^\s+python (\S+\.py)\b", WORKFLOW.read_text(encoding="utf-8"), re.M)))
    assert "evidence/tau2-bench/cascades.py" in run and len(run) > 10
    downloading = {path for path in run if "urlopen" in (ROOT / path).read_text(encoding="utf-8")}
    assert downloading == set(SCRIPTS.values()) - {SCRIPTS["tools"]}
    cascades = (ROOT / "evidence" / "tau2-bench" / "cascades.py").read_text(encoding="utf-8")
    assert '"research" / "escalation_signals.py"' in cascades and "signals.fetch_tools(" in cascades


@pytest.mark.parametrize("kind", list(FAILURES))
@pytest.mark.parametrize("key", list(SCRIPTS))
def test_a_download_that_fails_twice_is_retried_and_kept(key, kind, monkeypatch, tmp_path):
    mod, cache, served, dest, first = setup(key, monkeypatch, tmp_path)
    calls = serve(monkeypatch, served, FAILURES[kind]())
    mod.fetch(cache)
    assert calls == [first] * 3 + list(served)[1:]
    assert dest.read_bytes() == BODY  # the third attempt rewrote the part file from its first byte
    assert not list(cache.rglob("*.part"))


def test_each_file_has_its_own_three_attempts(monkeypatch, tmp_path):
    # Review iter-266 nit 6: 12.9 downloads two files, so a count shared across files, or a retry of
    # the first file alone, fails here: each of the two fails twice and is kept on its third attempt.
    mod, cache, served, dest, first = setup("autobench", monkeypatch, tmp_path)
    second = list(served)[1]
    failures = {url: [TimeoutError("The read operation timed out"), ConnectionResetError("reset")] for url in served}
    calls = serve(monkeypatch, served, [], url_failures=failures)
    mod.fetch(cache)
    assert calls == [first] * 3 + [second] * 3
    assert dest.read_bytes() == BODY and not list(cache.rglob("*.part"))


@pytest.mark.parametrize("key", list(SCRIPTS))
def test_a_failure_on_every_attempt_raises_the_last_error_after_three_calls(key, monkeypatch, tmp_path):
    mod, cache, served, dest, first = setup(key, monkeypatch, tmp_path)
    errors = [TimeoutError(f"attempt {n}") for n in (1, 2, 3)]
    calls = serve(monkeypatch, served, errors)  # a fourth call would be served, and fetch would return
    with pytest.raises(OSError) as caught:
        mod.fetch(cache)
    assert calls == [first] * 3
    if key in WRAPS_NONE:
        assert caught.value is errors[2]
    else:
        assert caught.value.__cause__ is errors[2]
        assert str(caught.value).endswith(": download failed: attempt 3")
    assert not dest.exists() and not list(cache.rglob("*.part"))


@pytest.mark.parametrize("key", list(SCRIPTS))
def test_a_download_that_fails_verify_is_not_retried(key, monkeypatch, tmp_path):
    mod, cache, served, dest, first = setup(key, monkeypatch, tmp_path)
    calls = serve(monkeypatch, {**served, first: OTHER}, [])
    with pytest.raises(ValueError, match="sha256"):
        mod.fetch(cache)
    assert calls == [first]
    assert not dest.exists() and not list(cache.rglob("*.part"))


@pytest.mark.parametrize("key", list(SCRIPTS))
def test_a_value_error_is_retried_only_where_it_is_a_failed_download(key, monkeypatch, tmp_path):
    mod, cache, served, dest, first = setup(key, monkeypatch, tmp_path)
    calls = serve(monkeypatch, served, [ValueError(f"attempt {n}") for n in (1, 2, 3)])
    if key in WRAPS_VALUE_ERROR:
        with pytest.raises(OSError, match=": download failed: attempt 3$"):
            mod.fetch(cache)
        assert calls == [first] * 3
    else:
        with pytest.raises(ValueError, match="^attempt 1$"):
            mod.fetch(cache)
        assert calls == [first]
    assert not dest.exists() and not list(cache.rglob("*.part"))


@pytest.mark.parametrize("key", list(SCRIPTS))
def test_an_interrupt_is_not_retried(key, monkeypatch, tmp_path):
    mod, cache, served, dest, first = setup(key, monkeypatch, tmp_path)
    calls = serve(monkeypatch, served, [Broken(KeyboardInterrupt())])
    with pytest.raises(KeyboardInterrupt):
        mod.fetch(cache)
    assert calls == [first]
    assert not dest.exists() and not list(cache.rglob("*.part"))


def test_design_states_the_retry_rule():
    bullets = [line for line in DESIGN.read_text(encoding="utf-8").splitlines()
               if line.startswith("- Time limit and retries (")]
    assert len(bullets) == 1
    for phrase in ("Retries (v1.406, row CI23; `fetch_tools` v1.545): each of them tries a missing file up to "
                   "`ATTEMPTS = 3` times, at once",
                   # v1.545 (row ESC3h): the list names every function SCRIPTS tests
                   "the nine download functions the job calls (the `fetch` of " + ", ".join(SECTIONS[:-1])
                   + f" and {SECTIONS[-1]}, and `fetch_tools`) each open a file with `urlopen(..., timeout=60)`",
                   "(in 13.15 and `fetch_tools` any `Exception`, since they report each as a failed download)",
                   "each attempt rewriting `<name>.part` from its first byte",
                   "a download that fails `verify` (bytes unlike the pin mean the source moved, while a short read "
                   "raises and is retried) or a `BaseException` is never retried",
                   # v1.442 (row CI24): run 43751236072 is now an earlier basis run, which the
                   # bullet no longer names (v1.391), so the Why sentence names its commit.
                   "Why: the run on `937399a` (2026-11-15), the first of the "):
        assert phrase in bullets[0], phrase
    assert "Retries: none in the converters" not in bullets[0]
    assert "six `fetch` functions" not in bullets[0] and len(SECTIONS) + 1 == len(SCRIPTS) == 9
    assert "43751236072" not in bullets[0]
    # Review iter-266 must-fix 1: 12.18 and 12.20 said their fetch had no retry.
    assert "with no retry" not in DESIGN.read_text(encoding="utf-8")
