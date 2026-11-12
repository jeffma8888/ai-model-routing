"""Small fictional fixtures shared by contract tests, and one session-scoped run of the
LLMRouterBench converter on its pinned file (DESIGN 12.19, v1.156) and of the response-bank
converter on its four pinned files (DESIGN 12.21, v1.291)."""

import contextlib
import importlib.util
import io
import json
from dataclasses import asdict
from pathlib import Path

import pytest

from model_routing import Model, Priors, Registry, Router, Stats, Task


@pytest.fixture
def model_factory():
    def make(model_id="fiction/cheap", family="small", price_in=1.0,
             price_out=2.0, context_window=8000, **kwargs):
        return Model(id=model_id, family=family, price_in=price_in,
                     price_out=price_out, context_window=context_window, **kwargs)
    return make


@pytest.fixture
def registry(model_factory):
    return Registry([
        model_factory("fiction/cheap", "small", 1.0, 2.0),
        model_factory("fiction/mid", "medium", 3.0, 6.0),
        model_factory("fiction/best", "large", 10.0, 20.0),
    ])


@pytest.fixture
def task_factory():
    def make(**overrides):
        fields = {"name": "judge", "bar": 0.7, "min_samples": 10,
                  "expected_input_tokens": 1000, "expected_output_tokens": 200}
        fields.update(overrides)
        return Task(**fields)
    return make


@pytest.fixture
def measured_stats():
    stats = Stats()
    for model_id, successes in [("fiction/cheap", 90), ("fiction/mid", 95),
                                ("fiction/best", 100)]:
        stats.add("judge", model_id, successes, 100)
    return stats


@pytest.fixture
def router(registry, task_factory, measured_stats):
    task = task_factory()
    return Router(registry, {task.name: task}, measured_stats)


@pytest.fixture
def prior_categories():
    return {"judging": {"metric": "fictional score", "source": "https://example.org/scores",
                        "as_of": "2026-01-01", "scores": {
                            "fiction/best": 90, "fiction/cheap": 80, "fiction/mid": 90}}}


@pytest.fixture
def priors(prior_categories):
    return Priors(prior_categories)


@pytest.fixture
def write_json(tmp_path):
    def write(name, value):
        path = tmp_path / name
        path.write_text(json.dumps(value), encoding="utf-8")
        return path
    return write


@pytest.fixture
def cli_files(write_json, registry, task_factory, measured_stats, tmp_path,
              prior_categories):
    models = [dict(asdict(model), source="https://example.org/prices")
              for model in registry.models]
    registry_path = write_json("models.json", {
        "version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models})
    tasks_path = write_json("tasks.json", {"tasks": [asdict(task_factory())]})
    stats_path = tmp_path / "stats.json"
    measured_stats.save(stats_path)
    priors_path = write_json("priors.json", {"categories": prior_categories})
    return {"registry": registry_path, "tasks": tasks_path,
            "stats": stats_path, "priors": priors_path}


@pytest.fixture
def record_factory():
    def make(**overrides):
        record = {
            "ts": "2026-01-01T00:00:00Z", "call_id": "call-1", "task": "judge",
            "flavor": "cost_effective", "model": "fiction/cheap", "family": "small",
            "attempt": 0, "final": True, "outcome": "ok", "error": None,
            "latency_ms": 10.0, "input_tokens": 100, "output_tokens": 10,
            "cost_usd": 0.00012, "routing_cost_usd": 0.00012,
            "below_bar": False, "basis": "measured", "tags": {},
        }
        record.update(overrides)
        return record
    return make


# --- the pinned LLMRouterBench file, read once per session (DESIGN 12.19, v1.156) ----------

LLMROUTERBENCH_CONVERTER = Path(__file__).resolve().parents[1] / "evidence" / "llmrouterbench" / "convert.py"


@pytest.fixture(scope="session")
def llmrouterbench_pinned(tmp_path_factory):
    """The converter's CLI run on the pinned tarball: (exit code, parsed report or None, rows path).

    Shared by tests/test_evidence_llmrouterbench.py and tests/test_evidence_llmrouterbench_results.py,
    so a suite run reads the 1.28 GB file at most once. Skips when the file is not in the default
    cache (CI never downloads it).
    """
    spec = importlib.util.spec_from_file_location("lrb_convert_pinned", LLMROUTERBENCH_CONVERTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    if not (module.default_cache_dir() / module.FILE).is_file():
        pytest.skip("the pinned LLMRouterBench file is not in the default cache")
    out = tmp_path_factory.mktemp("lrb") / "rows.jsonl"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        code = module.main(["--out", str(out)])
    return code, json.loads(buf.getvalue()) if code == 0 else None, out


LLMROUTERBENCH_DELEGATION_SCRIPT = (Path(__file__).resolve().parents[1] / "evidence"
                                    / "llmrouterbench-delegation" / "results.py")


@pytest.fixture(scope="session")
def llmrouterbench_delegation_full(llmrouterbench_pinned):
    """The 13.13 evaluation on the pinned rows, run once per session: (kept rows, dropped items, run).

    Shared by tests/test_evidence_llmrouterbench_delegation.py and
    tests/test_research_per_item_delegation.py (DESIGN 13.8 v1.227), so a suite run pays the
    evaluation once. Skips with ``llmrouterbench_pinned`` when the pinned file is not cached. The
    run is shared: a test must not modify it.
    """
    from model_routing import evaluate_delegation

    code, _report, path = llmrouterbench_pinned
    assert code == 0
    with open(path, encoding="utf-8") as fh:
        rows = [json.loads(line) for line in fh if line.strip()]
    spec = importlib.util.spec_from_file_location("lrb_delegation_results_session",
                                                  LLMROUTERBENCH_DELEGATION_SCRIPT)
    script = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(script)
    registry = Registry.load(LLMROUTERBENCH_DELEGATION_SCRIPT.with_name("registry.json"))
    kept, dropped = script.select_rows(rows, [m.id for m in registry.models])
    full = evaluate_delegation(kept, registry, bars=list(script.BARS), points=script.points(),
                               seeds=range(script.SEEDS))
    return kept, dropped, full


# --- the four pinned response-bank files, read once per session (DESIGN 12.21, v1.291) ------

RESPONSE_BANK_CONVERTER = Path(__file__).resolve().parents[1] / "evidence" / "response-bank" / "convert.py"


@pytest.fixture(scope="session")
def response_bank_pinned(tmp_path_factory):
    """The converter's CLI run on the four pinned files: (exit code, stdout, stderr, rows path).

    Shared by tests/test_evidence_response_bank.py and tests/test_evidence_response_bank_results.py,
    so a suite run reads the 1,018,191,580 bytes at most once. Skips when any of the four is not in
    the default cache (CI never downloads them).
    """
    spec = importlib.util.spec_from_file_location("response_bank_convert_pinned", RESPONSE_BANK_CONVERTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    cache = module.default_cache_dir()
    if not all((cache / name).is_file() for name in module.FILES):
        pytest.skip("the four pinned response-bank files are not in the default cache")
    out = tmp_path_factory.mktemp("response-bank") / "matrix.jsonl"
    stdout, stderr = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(stdout), contextlib.redirect_stderr(stderr):
        code = module.main(["--out", str(out)])
    return code, stdout.getvalue(), stderr.getvalue(), out
