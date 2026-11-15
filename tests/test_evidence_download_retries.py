"""DESIGN.md 12.13 v1.406 (row CI23): each of the six `fetch` functions the `evidence` job calls
(12.9, 12.14, 12.16, 12.18, 12.20 and 13.15) tries a missing file up to `ATTEMPTS = 3` times, at
once, each attempt rewriting `<name>.part` from its first byte. An attempt whose `urlopen` or read
raises an `Exception` other than a `ValueError` (13.15: any `Exception`) is retried, and the last
attempt's error is raised as each module raised it before; a download that fails `verify` and a
`BaseException` are never retried. Each module's own fetch tests keep their cases: a failure on
every attempt is the same error after three calls.
"""

import hashlib
import importlib.util
import io
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
}
WRAPS_NONE = {"autobench"}  # 12.9 raises a download error as it is, not as an OSError naming the file
WRAPS_VALUE_ERROR = {"ledger"}  # 13.15 reports every download error, a ValueError included, as one
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


def serve(monkeypatch, served, failures):
    """A urlopen whose first len(failures) calls fail, each with its failure (raised at the open, or
    mid-read for a Broken), and whose later calls serve `served` by URL; returns the URLs asked for."""
    calls = []

    def urlopen(url, timeout=None):
        calls.append(url)
        assert timeout == 60
        if len(calls) <= len(failures):
            failure = failures[len(calls) - 1]
            if isinstance(failure, Broken):
                return failure
            raise failure
        return io.BytesIO(served[url])

    monkeypatch.setattr(urllib.request, "urlopen", urlopen)
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


@pytest.mark.parametrize("kind", list(FAILURES))
@pytest.mark.parametrize("key", list(SCRIPTS))
def test_a_download_that_fails_twice_is_retried_and_kept(key, kind, monkeypatch, tmp_path):
    mod, cache, served, dest, first = setup(key, monkeypatch, tmp_path)
    calls = serve(monkeypatch, served, FAILURES[kind]())
    mod.fetch(cache)
    assert calls == [first] * 3 + list(served)[1:]
    assert dest.read_bytes() == BODY  # the third attempt rewrote the part file from its first byte
    assert not list(cache.rglob("*.part"))


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
    for phrase in ("Retries (v1.406, row CI23): each of the six `fetch` functions tries a missing file up to "
                   "`ATTEMPTS = 3` times, at once",
                   "each attempt rewriting `<name>.part` from its first byte",
                   "a download that fails `verify` or a `BaseException` is never retried",
                   "run 43751236072 on `937399a`"):
        assert phrase in bullets[0], phrase
    assert "Retries: none in the converters" not in bullets[0]
