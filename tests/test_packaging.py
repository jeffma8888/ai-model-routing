"""DESIGN 3 v1.114: the PEP 561 marker ships as package data, and the version has one source."""

import ast
import importlib.metadata
import re
import sys
from pathlib import Path

import pytest

import model_routing

if sys.version_info >= (3, 11):
    import tomllib
else:  # pytest itself depends on tomli before 3.11
    tomllib = pytest.importorskip("tomli")

ROOT = Path(__file__).resolve().parent.parent
PACKAGE = ROOT / "model_routing"


def pyproject():
    return tomllib.loads((ROOT / "pyproject.toml").read_text(encoding="utf-8"))


def version_bindings(source):
    """Every node of the module source that binds the name __version__."""
    return [node for node in ast.walk(ast.parse(source))
            if isinstance(node, ast.Name) and node.id == "__version__"
            and isinstance(node.ctx, ast.Store)]


def test_py_typed_marker_is_an_empty_file_in_the_package():
    marker = PACKAGE / "py.typed"
    assert marker.is_file()
    assert marker.read_bytes() == b""


def test_package_data_is_the_data_files_and_the_marker():
    assert pyproject()["tool"]["setuptools"]["package-data"] == {
        "model_routing": ["data/*.json", "py.typed"]}


def test_pyproject_reads_the_version_from_the_package():
    config = pyproject()
    assert "version" not in config["project"]
    assert "version" in config["project"].get("dynamic", [])
    assert config["tool"]["setuptools"].get("dynamic", {}).get("version") == {
        "attr": "model_routing.__version__"}


def test_version_is_one_top_level_string_literal():
    source = (PACKAGE / "__init__.py").read_text(encoding="utf-8")
    assert len(version_bindings(source)) == 1
    top = [node for node in ast.parse(source).body if isinstance(node, ast.Assign)
           and [getattr(t, "id", None) for t in node.targets] == ["__version__"]]
    assert len(top) == 1
    assert isinstance(top[0].value, ast.Constant) and isinstance(top[0].value.value, str)
    assert top[0].value.value == model_routing.__version__
    assert re.fullmatch(r"[0-9]+\.[0-9]+\.[0-9]+", model_routing.__version__)


def test_version_bindings_counts_every_binding():
    assert len(version_bindings('__version__ = "1.0.0"\n')) == 1
    assert len(version_bindings('__version__ = "1.0.0"\n__version__ = "2.0.0"\n')) == 2
    assert len(version_bindings('def f():\n    __version__ = "2.0.0"\n')) == 1
    assert len(version_bindings('print(__version__)\n')) == 0


def test_installed_metadata_agrees_with_the_package():
    try:
        installed = importlib.metadata.version("ai-model-routing")
    except importlib.metadata.PackageNotFoundError:
        pytest.skip("ai-model-routing is not installed in this interpreter")
    assert installed == model_routing.__version__, (
        "the installed metadata differs from model_routing.__version__; reinstall: "
        "pip install -e .")
