"""DESIGN 3 v1.121: with no TOML parser, only the tests that read pyproject.toml skip."""

import importlib.metadata
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
PACKAGING = ROOT / "tests" / "test_packaging.py"
PARSER = "tomllib" if sys.version_info >= (3, 11) else "tomli"
TOML_TESTS = {
    "test_package_data_is_the_data_files_and_the_marker",
    "test_pyproject_reads_the_version_from_the_package",
}
ALWAYS_PASS = {
    "test_py_typed_marker_is_an_empty_file_in_the_package",
    "test_version_is_one_top_level_string_literal",
    "test_version_bindings_counts_every_binding",
}
INSTALLED = "test_installed_metadata_agrees_with_the_package"
ALL_TESTS = TOML_TESTS | ALWAYS_PASS | {INSTALLED}

# The child blocks the parser after pytest has read its own configuration and before
# collection, then writes each test's outcome and skip reason as JSON.
CHILD = r'''
import json
import sys

import pytest

blocked, out, target = sys.argv[1], sys.argv[2], sys.argv[3]
outcomes = {}


class Recorder:
    def pytest_sessionstart(self, session):
        if blocked:
            sys.modules[blocked] = None

    def pytest_collectreport(self, report):
        if report.outcome != "passed":
            outcomes["collect " + report.nodeid] = [report.outcome, str(report.longrepr)]

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or report.outcome != "passed":
            reason = ""
            if report.skipped and isinstance(report.longrepr, tuple):
                reason = report.longrepr[2]
            outcomes[report.nodeid.rsplit("::", 1)[-1]] = [report.outcome, reason]


code = pytest.main([target, "-q", "-p", "no:cacheprovider"], plugins=[Recorder()])
with open(out, "w", encoding="utf-8") as handle:
    json.dump({"exit": int(code), "outcomes": outcomes}, handle)
'''


def run_child(tmp_path, blocked):
    out = tmp_path / ("blocked.json" if blocked else "open.json")
    # PYTEST_ADDOPTS from the parent could change the child's test set.
    env = {key: value for key, value in os.environ.items() if key != "PYTEST_ADDOPTS"}
    done = subprocess.run(
        [sys.executable, "-c", CHILD, blocked, str(out), str(PACKAGING)],
        cwd=ROOT, env=env, capture_output=True, text=True, timeout=300)
    assert out.is_file(), done.stdout + done.stderr
    return json.loads(out.read_text(encoding="utf-8"))


def installed():
    try:
        importlib.metadata.version("ai-model-routing")
    except importlib.metadata.PackageNotFoundError:
        return False
    return True


def test_blocking_the_toml_parser_skips_only_the_pyproject_tests(tmp_path):
    as_is = run_child(tmp_path, "")
    blocked = run_child(tmp_path, PARSER)
    assert set(as_is["outcomes"]) == ALL_TESTS, as_is
    assert set(blocked["outcomes"]) == ALL_TESTS, blocked
    assert as_is["exit"] == 0 and blocked["exit"] == 0
    for name in TOML_TESTS:
        # The run with no block needs the parser; pytest itself depends on tomli before 3.11.
        assert as_is["outcomes"][name] == ["passed", ""], (name, as_is["outcomes"][name])
        outcome, reason = blocked["outcomes"][name]
        assert outcome == "skipped" and repr(PARSER) in reason, (name, reason)
    for name in ALWAYS_PASS:
        assert as_is["outcomes"][name] == ["passed", ""]
    if installed():
        assert as_is["outcomes"][INSTALLED] == ["passed", ""]
    else:
        outcome, reason = as_is["outcomes"][INSTALLED]
        assert outcome == "skipped" and "is not installed" in reason, reason
    for name in ALL_TESTS - TOML_TESTS:
        assert blocked["outcomes"][name] == as_is["outcomes"][name], name
