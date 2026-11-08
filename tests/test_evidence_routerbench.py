"""v1.6 RouterBench converter contract (DESIGN 12.6), written before the converter exists.

The converter is a script outside the package (``evidence/routerbench/convert.py``),
so it is loaded from its path by an autouse fixture before any other test code runs.
The tests were held under a module-level strict xfail until the converter landed;
the implementing commit removed that marker. Only the tests that build a real frame
need pandas; they skip without it.
"""

import hashlib
import importlib.util
import io
import json
import math
import os
import pickle
import pickletools
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

SCRIPT = Path(__file__).resolve().parents[1] / "evidence" / "routerbench" / "convert.py"
REAL_COLUMNS = [
    "WizardLM/WizardLM-13B-V1.2", "claude-instant-v1", "claude-v1", "claude-v2",
    "gpt-3.5-turbo-1106", "gpt-4-1106-preview", "meta/code-llama-instruct-34b-chat",
    "meta/llama-2-70b-chat", "mistralai/mistral-7b-chat", "mistralai/mixtral-8x7b-chat",
    "zero-one-ai/Yi-34B-Chat"]
PINNED_GLOBALS = {
    ("builtins", "slice"), ("numpy", "dtype"), ("numpy", "ndarray"),
    ("numpy.core.multiarray", "_reconstruct"), ("numpy.core.numeric", "_frombuffer"),
    ("pandas._libs.internals", "_unpickle_block"), ("pandas.core.frame", "DataFrame"),
    ("pandas.core.indexes.base", "Index"), ("pandas.core.indexes.base", "_new_Index"),
    ("pandas.core.indexes.range", "RangeIndex"),
    ("pandas.core.internals.managers", "BlockManager")}
CALLED = []


def load_cv():
    if not SCRIPT.is_file():
        raise ModuleNotFoundError(f"no converter at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("routerbench_convert", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def cv():
    return load_cv()


def mark_called(*args):
    CALLED.append(args)
    return "ran"


class Payload:
    """Unpickling this calls ``target(*args)``; a restricted loader must refuse it first."""

    def __init__(self, target, *args):
        self.target, self.args = target, args

    def __reduce__(self):
        return self.target, self.args


def columns(rows, models=("claude-v2", "meta/llama-2-70b-chat")):
    """rows: (sample_id, eval_name, {model: (score, cost)})."""
    out = {"sample_id": [r[0] for r in rows], "eval_name": [r[1] for r in rows]}
    for m in models:
        out[m] = [r[2][m][0] for r in rows]
        out[m + "|total_cost"] = [r[2][m][1] for r in rows]
    return out


def binary_task(name, n, prefix=None):
    prefix = prefix or name
    return [(f"{prefix}.{i}", name, {"claude-v2": (1.0, 0.002), "meta/llama-2-70b-chat":
                                     (float(i % 2), 0.0005)}) for i in range(n)]


# Pinned source -------------------------------------------------------------

def test_source_is_pinned(cv):
    assert cv.REVISION == "784021482c3f320c6619ed4b3bb3b41a21424fcb"
    assert cv.FILENAME == "routerbench_0shot.pkl"
    assert cv.SIZE == 99567659
    assert cv.SHA256 == "ba4f77f19517610a707c374e99322d7750c30fc4ae7ff5527888595a1e65d36d"
    assert cv.URL == ("https://huggingface.co/datasets/withmartian/routerbench/resolve/"
                      "784021482c3f320c6619ed4b3bb3b41a21424fcb/routerbench_0shot.pkl")


def test_default_cache_is_outside_the_repo(cv):
    path = cv.default_cache_dir()
    assert path == Path.home() / ".cache" / "ai-model-routing-evidence" / "routerbench"
    assert SCRIPT.parents[2] not in path.parents


def test_verify_accepts_matching_size_and_hash(cv, tmp_path):
    f = tmp_path / "x.pkl"
    f.write_bytes(b"routerbench")
    cv.verify(f, size=11, sha256=hashlib.sha256(b"routerbench").hexdigest())


@pytest.mark.parametrize("size,digest", [(12, None), (11, "0" * 64)])
def test_verify_rejects_a_wrong_size_or_hash(cv, tmp_path, size, digest):
    f = tmp_path / "x.pkl"
    f.write_bytes(b"routerbench")
    digest = digest or hashlib.sha256(b"routerbench").hexdigest()
    with pytest.raises(ValueError, match=str(size) if size != 11 else "0" * 64):
        cv.verify(f, size=size, sha256=digest)


def test_fetch_reuses_a_verified_file_without_network(cv, tmp_path, monkeypatch):
    f = tmp_path / cv.FILENAME
    f.write_bytes(b"cached")
    monkeypatch.setattr(cv, "SIZE", 6)
    monkeypatch.setattr(cv, "SHA256", hashlib.sha256(b"cached").hexdigest())

    def no_network(*a, **k):
        raise AssertionError("fetch must not download a file that already verifies")
    monkeypatch.setattr(cv.urllib.request, "urlopen", no_network)
    assert cv.fetch(tmp_path) == f


def test_fetch_downloads_to_part_then_renames_only_after_verify(cv, tmp_path, monkeypatch):
    monkeypatch.setattr(cv, "SIZE", 5)
    monkeypatch.setattr(cv, "SHA256", hashlib.sha256(b"fresh").hexdigest())
    monkeypatch.setattr(cv.urllib.request, "urlopen", lambda url, timeout=None: io.BytesIO(b"fresh"))
    assert cv.fetch(tmp_path).read_bytes() == b"fresh"
    assert not (tmp_path / (cv.FILENAME + ".part")).exists()
    monkeypatch.setattr(cv.urllib.request, "urlopen", lambda url, timeout=None: io.BytesIO(b"other"))
    with pytest.raises(ValueError):
        cv.fetch(tmp_path / "second")
    assert not (tmp_path / "second" / cv.FILENAME).exists()
    assert not (tmp_path / "second" / (cv.FILENAME + ".part")).exists()


def test_fetch_refuses_a_present_file_that_fails_verify(cv, tmp_path, monkeypatch):
    (tmp_path / cv.FILENAME).write_bytes(b"tampered")
    monkeypatch.setattr(cv.urllib.request, "urlopen", lambda *a, **k: io.BytesIO(b"x"))
    with pytest.raises(ValueError, match=cv.FILENAME):
        cv.fetch(tmp_path)
    assert (tmp_path / cv.FILENAME).read_bytes() == b"tampered"


# Restricted unpickling -------------------------------------------------------

def test_allow_list_is_exactly_the_pinned_files_globals(cv):
    assert set(cv.ALLOWED_GLOBALS) == PINNED_GLOBALS
    assert all(isinstance(m, str) and isinstance(n, str) for m, n in cv.ALLOWED_GLOBALS)


@pytest.mark.parametrize("protocol", range(pickle.HIGHEST_PROTOCOL + 1))
def test_a_disallowed_callable_is_refused_before_it_runs(cv, protocol):
    CALLED.clear()
    blob = pickle.dumps(Payload(mark_called, "x"), protocol=protocol)
    with pytest.raises(pickle.UnpicklingError, match="mark_called"):
        cv.restricted_load(io.BytesIO(blob))
    assert CALLED == []


@pytest.mark.parametrize("module,name", [
    ("os", "system"), ("builtins", "eval"), ("builtins", "exec"), ("builtins", "getattr"),
    ("builtins", "__import__"), ("subprocess", "Popen"), ("numpy", "load"),
    ("numpy.testing._private.utils", "runstring"), ("pandas.io.pickle", "read_pickle"),
    ("pandas.core.frame", "eval"), ("numpy.core.multiarray", "scalar")])
def test_dangerous_and_lookalike_globals_are_refused(cv, module, name):
    blob = b"\x80\x02c" + f"{module}\n{name}\n".encode() + b")R."
    with pytest.raises(pickle.UnpicklingError, match=f"{module}.{name}".replace(".", r"\.")):
        cv.restricted_load(io.BytesIO(blob))


def test_an_allowed_global_loads(cv):
    assert cv.restricted_load(io.BytesIO(pickle.dumps(slice(1, 9, 2), protocol=5))) == slice(1, 9, 2)


def test_python2_names_are_not_mapped_onto_allowed_ones(cv):
    blob = pickle.dumps(slice(1, 9, 2), protocol=2)
    assert b"__builtin__" in blob
    with pytest.raises(pickle.UnpicklingError, match="__builtin__"):
        cv.restricted_load(io.BytesIO(blob))


def test_persistent_ids_are_refused(cv):
    blob = b"\x80\x02X\x03\x00\x00\x00pid" + b"Q."
    pickletools.dis(blob, out=io.StringIO())
    with pytest.raises(pickle.UnpicklingError):
        cv.restricted_load(io.BytesIO(blob))


# Model IDs ---------------------------------------------------------------

def test_model_ids_are_provider_neutral_and_distinct(cv):
    ids = [cv.model_id(c) for c in REAL_COLUMNS]
    assert cv.model_id("claude-v2") == "anthropic/claude-v2"
    assert cv.model_id("gpt-4-1106-preview") == "openai/gpt-4-1106-preview"
    assert cv.model_id("meta/llama-2-70b-chat") == "meta/llama-2-70b-chat"
    assert len(set(ids)) == 11 and all(i.count("/") == 1 for i in ids)


@pytest.mark.parametrize("bad", ["mystery-model", "", "llama-2", "/", "meta/", "/llama", "a/b/c"])
def test_an_unknown_column_is_an_error_not_a_guess(cv, bad):
    with pytest.raises(ValueError):
        cv.model_id(bad)


def test_load_frame_reports_anything_but_a_refusal_as_value_error(cv, tmp_path):
    empty = tmp_path / "empty.pkl"
    empty.write_bytes(b"")
    with pytest.raises(ValueError, match="empty.pkl"):
        cv.load_frame(empty)
    bad_args = tmp_path / "bad.pkl"
    bad_args.write_bytes(b"\x80\x04cbuiltins\nslice\n(K\x01K\x02K\x03K\x04tR.")
    with pytest.raises(ValueError, match="bad.pkl"):
        cv.load_frame(bad_args)
    refused = tmp_path / "refused.pkl"
    refused.write_bytes(b"\x80\x02cos\nsystem\n)R.")
    with pytest.raises(pickle.UnpicklingError, match="os.system"):
        cv.load_frame(refused)


def test_a_non_frame_is_a_value_error(cv):
    with pytest.raises(ValueError, match="slice"):
        cv.frame_columns(slice(1, 2))


def test_negative_zero_cost_is_written_as_zero(cv):
    src = columns(binary_task("alpha", 2))
    src["claude-v2|total_cost"][0] = -0.0
    rows, _ = cv.convert(src, min_items=1)
    assert json.dumps(rows[0]["cost_usd"]) == "0.0"


# Conversion ------------------------------------------------------------------

def test_rows_are_the_complete_sorted_matrix(cv):
    rows, report = cv.convert(columns(binary_task("alpha", 3)), min_items=1)
    assert [list(r) for r in rows] == [["task", "item", "model", "correct", "cost_usd"]] * 6
    assert [(r["item"], r["model"], r["correct"], r["cost_usd"]) for r in rows] == [
        ("alpha.0", "anthropic/claude-v2", True, 0.002),
        ("alpha.0", "meta/llama-2-70b-chat", False, 0.0005),
        ("alpha.1", "anthropic/claude-v2", True, 0.002),
        ("alpha.1", "meta/llama-2-70b-chat", True, 0.0005),
        ("alpha.2", "anthropic/claude-v2", True, 0.002),
        ("alpha.2", "meta/llama-2-70b-chat", False, 0.0005)]
    assert all(r["task"] == "alpha" and type(r["correct"]) is bool and type(r["cost_usd"]) is float
               for r in rows)
    assert report == {"models": ["anthropic/claude-v2", "meta/llama-2-70b-chat"],
                      "kept": {"alpha": 3}, "dropped_graded": {}, "dropped_small": {}, "rows": 6}


def test_source_row_order_does_not_matter(cv):
    src = binary_task("beta", 5) + binary_task("alpha", 4)
    a = cv.convert(columns(src), min_items=1)
    b = cv.convert(columns(list(reversed(src))), min_items=1)
    assert a == b and list(a[1]["kept"]) == ["alpha", "beta"]


def graded_source():
    graded = [("g.0", "gsm", {"claude-v2": (0.75, 0.01), "meta/llama-2-70b-chat": (0.25, 0.001)}),
              ("g.1", "gsm", {"claude-v2": (1.0, 0.01), "meta/llama-2-70b-chat": (0.5, 0.001)})]
    return binary_task("alpha", 2) + graded


def test_graded_tasks_are_dropped_without_a_pass_score(cv):
    rows, report = cv.convert(columns(graded_source()), min_items=1)
    assert {r["task"] for r in rows} == {"alpha"}
    assert report["dropped_graded"] == {"gsm": 2} and report["kept"] == {"alpha": 2}


def test_a_pass_score_keeps_graded_tasks_and_thresholds_them(cv):
    rows, report = cv.convert(columns(graded_source()), pass_score=0.5, min_items=1)
    got = {(r["item"], r["model"]): r["correct"] for r in rows if r["task"] == "gsm"}
    assert got == {("g.0", "anthropic/claude-v2"): True, ("g.0", "meta/llama-2-70b-chat"): False,
                   ("g.1", "anthropic/claude-v2"): True, ("g.1", "meta/llama-2-70b-chat"): True}
    assert report["kept"] == {"alpha": 2, "gsm": 2} and report["dropped_graded"] == {}


@pytest.mark.parametrize("pass_score", [0.5, 1, 1e-9])
def test_binary_tasks_do_not_depend_on_the_pass_score(cv, pass_score):
    src = columns(binary_task("alpha", 6))
    assert cv.convert(src, pass_score=pass_score, min_items=1)[0] == cv.convert(src, min_items=1)[0]


def test_small_tasks_are_dropped_and_reported(cv):
    rows, report = cv.convert(columns(binary_task("big", 5) + binary_task("tiny", 4)), min_items=5)
    assert {r["task"] for r in rows} == {"big"}
    assert report["dropped_small"] == {"tiny": 4} and report["rows"] == 10


def test_default_min_items_is_100(cv):
    rows, report = cv.convert(columns(binary_task("t99", 99) + binary_task("t100", 100)))
    assert report["kept"] == {"t100": 100} and report["dropped_small"] == {"t99": 99}


def bad(cv, src, match, **kw):
    with pytest.raises(ValueError, match=match):
        cv.convert(src, **kw)


@pytest.mark.parametrize("value", [math.nan, -0.1, 1.5, True, "1", None])
def test_an_invalid_score_names_the_item_and_column(cv, value):
    src = columns(binary_task("alpha", 3))
    src["claude-v2"][1] = value
    bad(cv, src, r"alpha\.1.*claude-v2|claude-v2.*alpha\.1", min_items=1)


@pytest.mark.parametrize("value", [math.nan, math.inf, -1e-9, False, "0.1", None])
def test_an_invalid_cost_names_the_item_and_column(cv, value):
    src = columns(binary_task("alpha", 3))
    src["meta/llama-2-70b-chat|total_cost"][2] = value
    bad(cv, src, r"alpha\.2.*llama|llama.*alpha\.2", min_items=1)


def test_structural_errors(cv):
    src = columns(binary_task("alpha", 3))
    src["claude-v2"].append(1.0)
    bad(cv, src, "length", min_items=1)
    src = columns(binary_task("alpha", 3))
    src["sample_id"][2] = "alpha.0"
    bad(cv, src, r"alpha\.0", min_items=1)
    for key, value in (("sample_id", ""), ("sample_id", 7), ("eval_name", ""), ("eval_name", None)):
        src = columns(binary_task("alpha", 3))
        src[key][0] = value
        bad(cv, src, key, min_items=1)
    src = columns(binary_task("alpha", 3))
    src["mystery-model"] = src.pop("claude-v2")
    src["mystery-model|total_cost"] = src.pop("claude-v2|total_cost")
    bad(cv, src, "mystery-model", min_items=1)
    src = columns(binary_task("alpha", 3))
    src["anthropic/claude-v2"] = list(src["claude-v2"])
    src["anthropic/claude-v2|total_cost"] = list(src["claude-v2|total_cost"])
    bad(cv, src, "anthropic/claude-v2", min_items=1)


@pytest.mark.parametrize("kw", [{"pass_score": 0}, {"pass_score": 1.01}, {"pass_score": math.nan},
                                {"pass_score": True}, {"pass_score": "0.5"}, {"min_items": 0},
                                {"min_items": True}, {"min_items": 2.0}])
def test_invalid_options(cv, kw):
    bad(cv, columns(binary_task("alpha", 3)), "pass_score|min_items", **kw)


def test_output_feeds_the_evaluator(cv):
    rows, _ = cv.convert(columns(binary_task("alpha", 120)))
    outcomes = outcomes_from_rows(json.loads(json.dumps(r)) for r in rows)
    result = evaluate(outcomes, bars=[0.9], seeds=[0, 1])
    assert result["tasks"] == {"alpha": {"items": 120, "models": ["anthropic/claude-v2",
                                                                   "meta/llama-2-70b-chat"]}}
    assert {c["models"]["routed"] for c in result["cells"]} == {"anthropic/claude-v2"}


def test_write_jsonl_round_trips(cv, tmp_path):
    rows, _ = cv.convert(columns(binary_task("alpha", 3)), min_items=1)
    out = tmp_path / "m.jsonl"
    cv.write_jsonl(rows, out)
    text = out.read_text(encoding="utf-8")
    assert text.endswith("\n") and [json.loads(line) for line in text.splitlines()] == rows


# pandas frames -------------------------------------------------------------

def tiny_frame(pd):
    src = columns(binary_task("alpha", 3))
    frame = {"sample_id": src["sample_id"], "prompt": ["p0", "p1", "p2"],
             "eval_name": src["eval_name"]}
    for m in ("claude-v2", "meta/llama-2-70b-chat"):
        frame[m] = src[m]
        frame[m + "|model_response"] = ["r", "r", "r"]
        frame[m + "|total_cost"] = src[m + "|total_cost"]
    frame["oracle_model_to_route_to"] = ["claude-v2"] * 3
    return pd.DataFrame(frame), src


def test_frame_columns_reads_only_ids_scores_and_costs(cv):
    pd = pytest.importorskip("pandas")
    frame, src = tiny_frame(pd)
    got = cv.frame_columns(frame)
    assert got == src and all(type(v) is list for v in got.values())
    assert cv.convert(got, min_items=1) == cv.convert(src, min_items=1)


def test_frame_columns_structural_errors(cv):
    pd = pytest.importorskip("pandas")
    frame, _ = tiny_frame(pd)
    for drop, match in (("sample_id", "sample_id"), ("eval_name", "eval_name"),
                        ("claude-v2|total_cost", "claude-v2")):
        with pytest.raises(ValueError, match=match):
            cv.frame_columns(frame.drop(columns=[drop]))
    with pytest.raises(ValueError, match="model"):
        cv.frame_columns(frame[["sample_id", "prompt", "eval_name", "oracle_model_to_route_to"]])


# CLI -----------------------------------------------------------------------------

@pytest.mark.parametrize("args", [["--out", "m.jsonl", "--pass-score", "0"],
                                  ["--out", "m.jsonl", "--pass-score", "nan"],
                                  ["--out", "m.jsonl", "--min-items", "0"],
                                  ["--out", "m.jsonl", "--min-items", "x"], []])
def test_cli_bad_options_exit_2_with_one_error_line(cv, args, tmp_path, capsys, monkeypatch):
    monkeypatch.chdir(tmp_path)

    def no_network(*a, **k):
        raise AssertionError("options are checked before any download")
    monkeypatch.setattr(cv.urllib.request, "urlopen", no_network)
    assert cv.main(args) == 2
    captured = capsys.readouterr()
    err = captured.err.strip().splitlines()
    assert len(err) == 1 and err[0].startswith("error:") and captured.out == ""
    assert not (tmp_path / "m.jsonl").exists()


def pinned_to(cv, monkeypatch, blob):
    monkeypatch.setattr(cv, "SIZE", len(blob))
    monkeypatch.setattr(cv, "SHA256", hashlib.sha256(blob).hexdigest())


@pytest.mark.parametrize("blob", [b"", pickle.dumps(slice(1, 2), protocol=5),
                                  pickle.dumps([1, 2], protocol=5),
                                  b"\x80\x04cbuiltins\nslice\n(K\x01K\x02K\x03K\x04tR."],
                         ids=["empty", "slice", "list", "bad-arguments"])
def test_cli_a_verified_file_that_is_not_a_frame_exits_2(cv, blob, tmp_path, capsys, monkeypatch):
    pinned_to(cv, monkeypatch, blob)
    (tmp_path / cv.FILENAME).write_bytes(blob)
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--cache", str(tmp_path)]) == 2
    captured = capsys.readouterr()
    err = captured.err.strip().splitlines()
    assert len(err) == 1 and err[0].startswith("error:") and captured.out == ""
    assert not out.exists() and not (tmp_path / "m.jsonl.part").exists()


def test_cli_a_failed_rename_leaves_no_part_file(cv, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cv, "fetch", lambda cache=None: tmp_path / "unused")
    monkeypatch.setattr(cv, "load_frame", lambda path: "frame")
    monkeypatch.setattr(cv, "frame_columns", lambda frame: columns(binary_task("alpha", 3)))
    out = tmp_path / "out-is-a-folder"
    out.mkdir()
    assert cv.main(["--out", str(out), "--min-items", "1"]) == 2
    captured = capsys.readouterr()
    _, report = cv.convert(columns(binary_task("alpha", 3)), min_items=1)
    # the report is printed before the rename (v1.94), so this is the one failure with it on stdout
    assert captured.out == json.dumps(report, indent=2) + "\n"
    assert len(captured.err.strip().splitlines()) == 1 and captured.err.startswith("error: ")
    assert out.is_dir() and not (tmp_path / "out-is-a-folder.part").exists()


def test_cli_success_writes_the_matrix_and_prints_the_report(cv, tmp_path, capsys, monkeypatch):
    monkeypatch.setattr(cv, "fetch", lambda cache=None: tmp_path / "unused")
    monkeypatch.setattr(cv, "load_frame", lambda path: "frame")
    monkeypatch.setattr(cv, "frame_columns", lambda frame: columns(binary_task("alpha", 3)))
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--min-items", "1"]) == 0
    rows, report = cv.convert(columns(binary_task("alpha", 3)), min_items=1)
    assert capsys.readouterr().out == json.dumps(report, indent=2) + "\n"
    assert [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()] == rows
    assert not (tmp_path / "m.jsonl.part").exists()


class BrokenStdout:
    """A closed pipe: every write and flush raises."""

    def write(self, text):
        raise BrokenPipeError(32, "Broken pipe")

    def flush(self):
        raise BrokenPipeError(32, "Broken pipe")


class BufferedBrokenStdout(BrokenStdout):
    """A buffered closed pipe: the write is kept, so only the flush raises."""

    def write(self, text):
        return len(text)


@pytest.mark.parametrize("stdout", [BrokenStdout, BufferedBrokenStdout])
def test_cli_a_failed_stdout_is_one_error_line_and_leaves_out(cv, tmp_path, capsys, monkeypatch, stdout):
    monkeypatch.setattr(cv, "fetch", lambda cache=None: tmp_path / "unused")
    monkeypatch.setattr(cv, "load_frame", lambda path: "frame")
    monkeypatch.setattr(cv, "frame_columns", lambda frame: columns(binary_task("alpha", 3)))
    out = tmp_path / "m.jsonl"
    out.write_text("old\n")
    monkeypatch.setattr("sys.stdout", stdout())
    assert cv.main(["--out", str(out), "--min-items", "1"]) == 2
    err = capsys.readouterr().err
    assert len(err.splitlines()) == 1 and err.startswith("error: ")
    assert out.read_text() == "old\n"
    assert not (tmp_path / "m.jsonl.part").exists()


def test_cli_a_cached_file_that_fails_verify_exits_2_and_is_not_replaced(cv, tmp_path, capsys,
                                                                         monkeypatch):
    def no_network(*a, **k):
        raise AssertionError("a present file that fails verify is an error, not a re-download")
    monkeypatch.setattr(cv.urllib.request, "urlopen", no_network)
    (tmp_path / cv.FILENAME).write_bytes(b"not the pinned file")
    assert cv.main(["--out", str(tmp_path / "m.jsonl"), "--cache", str(tmp_path)]) == 2
    err = capsys.readouterr().err.strip().splitlines()
    assert len(err) == 1 and err[0].startswith("error:") and cv.FILENAME in err[0]
    assert not (tmp_path / "m.jsonl").exists()
    assert (tmp_path / cv.FILENAME).read_bytes() == b"not the pinned file"


# Optional check against the real pinned file (never runs in CI) ------------------

@pytest.mark.skipif(not os.environ.get("ROUTERBENCH_PKL"), reason="set ROUTERBENCH_PKL to the pinned file")
def test_the_pinned_file_converts(cv):
    pytest.importorskip("pandas")
    path = Path(os.environ["ROUTERBENCH_PKL"])
    cv.verify(path)
    frame = cv.load_frame(path)
    assert len(frame) == 36497 and frame["eval_name"].nunique() == 86
    rows, report = cv.convert(cv.frame_columns(frame))
    assert len(report["models"]) == 11 and report["rows"] == len(rows) == 311091
    assert len(report["kept"]) == 65 and sum(report["kept"].values()) == 28281
    assert report["dropped_graded"] == {"chinese_idioms": 15, "consensus_summary": 362,
                                        "grade-school-math": 7450, "mtbench": 41,
                                        "mtbench-math": 20, "mtbench-reference": 19}
    assert len(report["dropped_small"]) == 15
    assert max(report["dropped_small"].values()) < 100 <= min(report["kept"].values())
