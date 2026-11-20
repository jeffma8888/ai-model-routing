"""DESIGN 7 v1.540 (row ESC3b): the tau2-bench cascade replay CLI and its prices.

`evidence/tau2-bench/cascades.py --out PATH [--cache DIR]` reads the 12 pinned run files and each
domain's write tools and writes the 12.14 matrix with one row per cascade and item added, its cascades
each pair of the four agents with the cheap one at the lower input list price of
`evidence/tau2-bench/prices.json`. These tests were committed before the code under a module-level
strict xfail whose error is the one a missing function of the loaded script raises, AttributeError, and
the implementing commit removed the mark. The stub tests need no download; when the run files and the
tool files are in the default cache (CI never downloads them), `main` runs on them once and its report
is checked against research/escalation.md `## Measured signals (row ESC1b)` and its single-model rows
against the 12.14 default matrix's digest pinned in tests/test_evidence_tau2_calls.py."""

import contextlib
import datetime
import hashlib
import io
import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

from model_routing import Cascade

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "tau2-bench" / "cascades.py"
PRICES = ROOT / "evidence" / "tau2-bench" / "prices.json"
NOTE = ROOT / "research" / "escalation.md"
# the 12.14 default matrix (trial 0, one task per domain, no token keys), the `()` pin of
# tests/test_evidence_tau2_calls.py test_pinned_matrices_without_calls_are_the_v175_bytes_when_cached
DEFAULT_MATRIX_SHA256 = "b2fccfd79c9afa172c4069dfa25a2026c58c50ade0ba5ad9873088a4dd7794b9"
MINI, O4, G41, SONNET = ("openai/gpt-4.1-mini-2025-04-14", "openai/o4-mini-2025-04-16",
                         "openai/gpt-4.1-2025-04-14", "anthropic/claude-3-7-sonnet-20250219")
AGENTS = (MINI, O4, G41, SONNET)

_loaded = []


def m():
    if not _loaded:
        spec = importlib.util.spec_from_file_location("tau2_cascades_cli", SCRIPT)
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        _loaded.append(module)
    return _loaded[0]


# --- the price file

def test_price_file_holds_the_four_agents_read_on_the_day():
    as_of, prices = m().load_prices(PRICES)
    assert as_of == "2026-11-20"
    assert prices == {MINI: 0.4, O4: 1.1, G41: 2.0, SONNET: 3}
    doc = json.loads(PRICES.read_text(encoding="utf-8"))
    sources = {entry["id"]: entry["source"] for entry in doc["models"]}
    for model in (MINI, O4, G41):
        page = model.split("/")[1].rsplit("-", 3)[0]
        assert sources[model] == f"https://platform.openai.com/docs/models/{page}"
    assert sources[SONNET] == ("https://github.com/sierra-research/tau2-bench/tree/"
                               f"{m().convert.REVISION}/data/tau2/results/final")
    assert m().PRICES == PRICES


def _doc(**change):
    doc = {"as_of": "2026-11-20", "note": "n",
           "models": [{"id": "v/a", "price_in": 1, "source": "https://x.example/a", "notes": ""},
                      {"id": "v/b", "price_in": 2.5, "source": "https://x.example/b", "notes": ""}]}
    doc.update(change)
    return doc


def _entry(**change):
    entry = {"id": "v/c", "price_in": 1, "source": "https://x.example/c", "notes": ""}
    entry.update(change)
    for key in [k for k, v in change.items() if v is _DROP]:
        del entry[key]
    return entry


_DROP = object()
BAD_PRICES = {
    "not-json": "{",
    "not-object": [],
    "extra-top-key": _doc(extra=1),
    "no-note": {"as_of": "2026-11-20", "models": _doc()["models"]},
    "bad-date": _doc(as_of="2026-02-30"),
    "date-form": _doc(as_of="2026-11-2"),
    "date-not-str": _doc(as_of=20261120),
    "note-not-str": _doc(note=None),
    "models-empty": _doc(models=[]),
    "models-not-list": _doc(models={"id": "v/a"}),
    "entry-not-object": _doc(models=["v/a"]),
    "entry-extra-key": _doc(models=[_entry(price_out=2)]),
    "entry-missing-key": _doc(models=[_entry(notes=_DROP)]),
    "id-empty": _doc(models=[_entry(id="")]),
    "id-not-str": _doc(models=[_entry(id=7)]),
    "id-repeated": _doc(models=[_entry(), _entry(price_in=2)]),
    "price-bool": _doc(models=[_entry(price_in=True)]),
    "price-negative": _doc(models=[_entry(price_in=-0.1)]),
    "price-str": _doc(models=[_entry(price_in="1")]),
    "price-huge-int": _doc(models=[_entry(price_in=10 ** 400)]),
    "price-nan": _doc(models=[_entry(price_in=float("nan"))]),  # json.dumps writes NaN, json.loads reads it
    "source-http": _doc(models=[_entry(source="http://x.example/c")]),
    "source-not-str": _doc(models=[_entry(source=None)]),
    "notes-not-str": _doc(models=[_entry(notes=1)]),
}


@pytest.mark.parametrize("case", list(BAD_PRICES))
def test_load_prices_refuses_a_bad_file(case, tmp_path):
    path = tmp_path / "prices.json"
    body = BAD_PRICES[case]
    path.write_text(body if isinstance(body, str) else json.dumps(body), encoding="utf-8")
    with pytest.raises(ValueError, match="prices.json"):
        m().load_prices(path)


def test_load_prices_refuses_a_file_that_is_not_utf8(tmp_path):
    path = tmp_path / "prices.json"
    path.write_bytes(b'{"as_of": "\xff"}')
    with pytest.raises(ValueError, match="prices.json"):
        m().load_prices(path)


def test_load_prices_reads_a_good_file(tmp_path):
    path = tmp_path / "p.json"
    path.write_text(json.dumps(_doc()), encoding="utf-8")
    assert m().load_prices(path) == ("2026-11-20", {"v/a": 1, "v/b": 2.5})


# --- pair_cascades

def test_pair_cascades_gives_each_pair_and_signal_with_the_cheap_model_first():
    prices = {MINI: 0.4, O4: 1.1, G41: 2.0, SONNET: 3}
    got = m().pair_cascades(list(AGENTS), prices)
    assert len(got) == 42 and all(isinstance(c, Cascade) for c in got)
    assert [c.id for c in got] == sorted(c.id for c in got)
    assert len({c.id for c in got}) == 42
    pairs = {(c.cheap, c.strong) for c in got}
    assert pairs == {(MINI, O4), (MINI, G41), (MINI, SONNET), (O4, G41), (O4, SONNET), (G41, SONNET)}
    for pair in pairs:
        assert sorted(c.signal for c in got if (c.cheap, c.strong) == pair) == sorted(m().SIGNALS)
    assert m().pair_cascades([SONNET, MINI], {MINI: 0.4, SONNET: 3})[0].cheap == MINI


@pytest.mark.parametrize("models, prices, words", [
    (["v/a", "v/b"], {"v/a": 1}, "v/b"),
    (["v/a"], {"v/a": 1, "v/b": 2}, "v/b"),
    (["v/a", "v/b"], {"v/a": 2, "v/b": 2.0}, "v/a"),
])
def test_pair_cascades_refuses_a_missing_price_an_unused_price_and_a_tie(models, prices, words):
    with pytest.raises(ValueError, match=re.escape(words)):
        m().pair_cascades(models, prices)


# --- run_calls

TOOLS = {"airline": {"book": "WRITE", "look": "READ", "transfer_to_human_agents": "GENERIC"}}


def greeting():
    return {"role": "assistant", "content": "Hi", "cost": 0.0, "usage": None, "tool_calls": None}


def agent(prompt, completion, cost, *tools):
    return {"role": "assistant", "content": "ok", "cost": cost,
            "usage": {"prompt_tokens": prompt, "completion_tokens": completion},
            "tool_calls": [{"id": f"c{i}", "name": t, "arguments": {}} for i, t in enumerate(tools)] or None}


def user():
    return {"role": "user", "content": "help", "cost": 0.001, "usage": None}


def sim(task, reward, messages, trial=0):
    cost = sum(msg["cost"] for msg in messages if msg["role"] == "assistant")
    return {"task_id": task, "trial": trial, "reward_info": {"reward": reward}, "agent_cost": cost,
            "messages": messages}


def stub_run(llm, simulations, domain="airline", tasks=("1", "2")):
    return {"info": {"environment_info": {"domain_name": domain}, "agent_info": {"llm": llm},
                     "user_info": {"llm": "gpt-4.1-2025-04-14"}},
            "tasks": [{"id": t} for t in tasks], "simulations": simulations}


def test_run_calls_reads_each_trial_0_conversation():
    run = stub_run("gpt-4.1-mini-2025-04-14", [
        sim("1", 1, [greeting(), user(), agent(100, 10, 0.25, "look"), agent(200, 20, 0.5, "book")]),
        sim("2", 0, [greeting(), user(), agent(50, 5, 0.125, "transfer_to_human_agents")]),
        sim("1", 0, [greeting(), agent(1, 1, 9.0)], trial=1),
    ])
    e, calls, greetings = m().run_calls(run, TOOLS)
    assert e["agent"] == MINI and sorted(e["cells"]) == ["1", "2"]
    assert greetings == 2
    assert calls == {
        (MINI, "airline|1"): [
            {"cost_usd": 0.25, "prompt_tokens": 100, "completion_tokens": 10, "write": False, "transfer": False},
            {"cost_usd": 0.5, "prompt_tokens": 200, "completion_tokens": 20, "write": True, "transfer": False}],
        (MINI, "airline|2"): [
            {"cost_usd": 0.125, "prompt_tokens": 50, "completion_tokens": 5, "write": False, "transfer": True}],
    }


def test_run_calls_at_another_trial():
    run = stub_run("gpt-4.1-mini-2025-04-14", [
        sim("1", 1, [greeting(), agent(1, 1, 0.5)]),
        sim("1", 0, [greeting(), agent(3, 4, 0.75, "book")], trial=1),
    ], tasks=("1",))
    e, calls, greetings = m().run_calls(run, TOOLS, trial=1)
    assert e["trial"] == 1 and greetings == 1
    assert calls == {(MINI, "airline|1"): [
        {"cost_usd": 0.75, "prompt_tokens": 3, "completion_tokens": 4, "write": True, "transfer": False}]}


def test_run_calls_refuses_a_domain_with_no_tools():
    run = stub_run("gpt-4.1-mini-2025-04-14", [sim("1", 1, [greeting()])], domain="shop", tasks=("1",))
    with pytest.raises(ValueError, match="shop"):
        m().run_calls(run, TOOLS)


def test_run_calls_names_the_run_task_and_trial_of_a_bad_message():
    bad = greeting()
    bad["cost"] = 0.5
    run = stub_run("gpt-4.1-mini-2025-04-14", [sim("1", 1, [bad])], tasks=("1",))
    with pytest.raises(ValueError, match=re.escape(f"airline {MINI} task '1' trial 0: ")):
        m().run_calls(run, TOOLS)


# --- main on stubs

TOOLS_SOURCE = '''
@is_tool(ToolType.WRITE)
def book(self, x):
    pass

@is_tool(ToolType.READ)
def look(self):
    pass

@is_tool(ToolType.GENERIC)
def transfer_to_human_agents(self, summary):
    pass
'''


def _stub_cli(tmp_path, monkeypatch, fetch_error=None):
    """Two agents on two airline tasks: the cheap one hands task 1 up on every calls-over-1 signal."""
    folder = tmp_path / "cache"
    folder.mkdir()
    runs = {
        "cheap.json": stub_run("gpt-4.1-mini-2025-04-14", [
            sim("1", 0, [greeting(), user(), agent(1000, 100, 0.25, "look"), agent(2000, 50, 0.5, "look")]),
            sim("2", 1, [greeting(), user(), agent(800, 20, 0.125, "book"), agent(900, 10, 0.25)]),
        ]),
        "strong.json": stub_run("gpt-4.1-2025-04-14", [
            sim("1", 1, [greeting(), agent(500, 50, 1.5)]),
            sim("2", 1, [greeting(), agent(400, 40, 1.25, "transfer_to_human_agents")]),
        ]),
    }
    for name, run in runs.items():
        (folder / name).write_text(json.dumps(run), encoding="utf-8")
    prices = tmp_path / "prices.json"
    prices.write_text(json.dumps({"as_of": "2026-11-20", "note": "stub", "models": [
        {"id": MINI, "price_in": 0.4, "source": "https://x.example/mini", "notes": ""},
        {"id": G41, "price_in": 2.0, "source": "https://x.example/g41", "notes": ""}]}), encoding="utf-8")

    def fetch(cache_dir=None):
        if fetch_error is not None:
            raise fetch_error
        return folder

    def fetch_tools(where, convert):
        assert Path(where) == folder / "tools" and convert is m().convert
        return {"airline": TOOLS_SOURCE}

    monkeypatch.setattr(m().convert, "FILES", {name: (0, "") for name in sorted(runs)})
    monkeypatch.setattr(m().convert, "fetch", fetch)
    monkeypatch.setattr(m().signals, "fetch_tools", fetch_tools)
    monkeypatch.setattr(m(), "PRICES", prices)


def test_main_writes_the_rows_and_the_report_on_stubs(tmp_path, monkeypatch, capsys):
    _stub_cli(tmp_path, monkeypatch)
    monkeypatch.setattr(m(), "SIGNALS", ("calls-over-1", "calls-over-1-no-write", "transfer"))
    out = tmp_path / "rows.jsonl"
    assert m().main(["--out", str(out)]) == 0
    report = json.loads(capsys.readouterr().out)
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert not (tmp_path / "rows.jsonl.part").exists()
    over, clean, transfer = (f"{MINI}>{G41}@{s}" for s in ("calls-over-1", "calls-over-1-no-write", "transfer"))
    assert list(report) == ["revision", "prices_as_of", "models", "trial", "kept", "agent_calls", "greetings",
                            "model_rows", "cascades", "cascade_rows", "rows", "escalated"]
    assert report["revision"] == m().convert.REVISION and report["prices_as_of"] == "2026-11-20"
    assert report["models"] == [G41, MINI] and report["trial"] == 0 and report["kept"] == {"airline": 2}
    assert (report["agent_calls"], report["greetings"]) == (6, 4)
    assert (report["model_rows"], report["cascades"], report["cascade_rows"], report["rows"]) == (4, 3, 6, 10)
    assert report["escalated"] == {"airline": {over: 2, clean: 1, transfer: 0}}
    assert [(r["item"], r["model"]) for r in rows] == sorted((r["item"], r["model"]) for r in rows)
    by = {(r["item"], r["model"]): r for r in rows}
    # handed up after call 1: 0.25 + (1000 + 100) * 2.0 / 1e6 + 1.5
    assert by[("airline|1", over)] == {"task": "airline", "item": "airline|1", "model": over, "correct": True,
                                       "cost_usd": math.fsum([0.25, 1100 * 2.0 / 1_000_000, 1.5]),
                                       "escalated": True}
    assert by[("airline|2", clean)] == {"task": "airline", "item": "airline|2", "model": clean, "correct": True,
                                        "cost_usd": 0.375, "escalated": False}
    assert by[("airline|2", MINI)] == {"task": "airline", "item": "airline|2", "model": MINI, "correct": True,
                                       "cost_usd": 0.375}


def test_main_turns_a_fetch_error_into_one_line_and_exit_2(tmp_path, monkeypatch, capsys):
    _stub_cli(tmp_path, monkeypatch, fetch_error=OSError("x.json: download failed: boom"))
    out = tmp_path / "rows.jsonl"
    assert m().main(["--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err == "error: x.json: download failed: boom\n"
    assert not out.exists() and not (tmp_path / "rows.jsonl.part").exists()


def test_main_refuses_a_price_file_that_misses_an_agent(tmp_path, monkeypatch, capsys):
    _stub_cli(tmp_path, monkeypatch)
    m().PRICES.write_text(json.dumps({"as_of": "2026-11-20", "note": "stub", "models": [
        {"id": MINI, "price_in": 0.4, "source": "https://x.example/mini", "notes": ""}]}), encoding="utf-8")
    out = tmp_path / "rows.jsonl"
    assert m().main(["--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and len(captured.err.splitlines()) == 1 and G41 in captured.err
    assert not out.exists() and not (tmp_path / "rows.jsonl.part").exists()


def _nothing_written(code, tmp_path, capsys, out, old=None):
    assert code == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("error: ") and len(captured.err.splitlines()) == 1
    if old is None:
        assert not out.exists()
    else:
        assert out.read_text(encoding="utf-8") == old
    assert not (tmp_path / "rows.jsonl.part").exists()
    return captured.err


def test_a_failed_print_leaves_an_old_out_and_no_part(tmp_path, monkeypatch, capsys):
    # review iter-386 should-fix 1: the rename comes after the print, and the part is always removed
    _stub_cli(tmp_path, monkeypatch)
    out = tmp_path / "rows.jsonl"
    out.write_text("old\n", encoding="utf-8")

    def boom(text):
        assert (tmp_path / "rows.jsonl.part").exists()
        raise BrokenPipeError("broken pipe")

    monkeypatch.setattr(m().convert, "print_report", boom)
    _nothing_written(m().main(["--out", str(out)]), tmp_path, capsys, out, old="old\n")


def test_a_failed_write_leaves_no_part(tmp_path, monkeypatch, capsys):
    _stub_cli(tmp_path, monkeypatch)
    out = tmp_path / "rows.jsonl"

    def boom(rows, path):
        Path(path).write_text("half", encoding="utf-8")
        raise OSError("disk full")

    monkeypatch.setattr(m().convert, "write_jsonl", boom)
    err = _nothing_written(m().main(["--out", str(out)]), tmp_path, capsys, out)
    assert err == "error: disk full\n"


def test_a_bad_price_file_downloads_nothing(tmp_path, monkeypatch, capsys):
    # review iter-386 should-fix 2: PRICES is read after the --out check and before any download
    _stub_cli(tmp_path, monkeypatch)
    m().PRICES.write_text("{", encoding="utf-8")
    fetched = []
    monkeypatch.setattr(m().convert, "fetch", lambda cache_dir=None: fetched.append(cache_dir))
    out = tmp_path / "rows.jsonl"
    err = _nothing_written(m().main(["--out", str(out)]), tmp_path, capsys, out)
    assert fetched == [] and "prices.json" in err


@pytest.mark.parametrize("failure", ["fetch_tools", "tool_types"])
def test_a_tools_failure_is_one_line_and_writes_nothing(failure, tmp_path, monkeypatch, capsys):
    _stub_cli(tmp_path, monkeypatch)
    if failure == "fetch_tools":
        def fetch_tools(where, convert):
            raise OSError("airline-tools.py: download failed: boom")
    else:
        def fetch_tools(where, convert):
            return {"airline": "def f(:\n"}
    monkeypatch.setattr(m().signals, "fetch_tools", fetch_tools)
    out = tmp_path / "rows.jsonl"
    err = _nothing_written(m().main(["--out", str(out)]), tmp_path, capsys, out)
    assert "airline-tools.py" in err


def test_report_lists_every_cascade_for_every_kept_task():
    # review iter-386 nit 4: a task with no kept item still gets its cascades, each at 0
    cascade = Cascade(MINI, G41, "transfer")
    row = {"task": "a", "item": "a|1", "model": cascade.id, "correct": True, "cost_usd": 1.0, "escalated": True}
    matrix = {"models": [MINI, G41], "trial": 0, "kept": {"a": 1, "b": 0}}
    got = m().report("2026-11-20", matrix, [cascade], [], [row], {}, 0)
    assert got["escalated"] == {"a": {cascade.id: 1}, "b": {cascade.id: 0}}


def test_main_refuses_an_unknown_option_with_exit_2(capsys):
    assert m().main(["--out", "x.jsonl", "--trial", "1"]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("error: ") and len(captured.err.splitlines()) == 1


# --- the pinned files, when cached

def _note_block():
    text = NOTE.read_text(encoding="utf-8")
    body = text.split("## Measured signals (row ESC1b)\n", 1)[1]
    return body.split("```text\n", 1)[1].split("\n```", 1)[0].splitlines()


def esc1b():
    """From the note's ESC1b block: (agent calls, greetings), {(domain, agent): transfer runs} and
    {(domain, agent, N): (over, wrote)}."""
    lines = _note_block()
    found = re.search(r"with a usage \(an agent call\): ([\d,]+) .* of them the run's first message: ([\d,]+)",
                      next(line for line in lines if line.startswith("agent messages: ")))
    totals = tuple(int(g.replace(",", "")) for g in found.groups())
    transfer, grid = {}, {}
    head = lines.index("runs over N agent calls, each cell over/pass/wrote (wrote: a write call among its "
                       "first N calls)")
    ns = [int(n) for n in re.findall(r"N=(\d+)", lines[head + 1])]
    first = next(k for k, line in enumerate(lines) if "calls_median" in line)
    for line in lines[first + 2:]:
        if not line:
            break
        part = line.split()
        transfer[(part[0], part[1])] = int(part[7])
    for line in lines[head + 3:]:
        if not line:
            break
        part = line.split()
        for n, cell in zip(ns, part[2:]):
            over, _, wrote = (int(x) for x in cell.split("/"))
            grid[(part[0], part[1], n)] = (over, wrote)
    return totals, transfer, grid


@pytest.fixture(scope="module")
def pinned(tmp_path_factory):
    convert = m().convert
    folder = convert.default_cache_dir()
    names = [folder / name for name in convert.FILES]
    names += [folder / "tools" / f"{domain}-tools.py" for domain in m().signals.TOOL_FILES]
    if not all(path.is_file() for path in names):
        pytest.skip("the 12 pinned tau2-bench run files or the 3 tool files are not in the default cache")
    out = tmp_path_factory.mktemp("cascades") / "rows.jsonl"
    buffer = io.StringIO()
    with contextlib.redirect_stdout(buffer):
        code = m().main(["--out", str(out)])
    assert code == 0
    return json.loads(buffer.getvalue()), out


def test_pinned_report_counts(pinned):
    report, _ = pinned
    (calls, greetings), _, _ = esc1b()
    assert report["revision"] == m().convert.REVISION and report["prices_as_of"] == "2026-11-20"
    assert report["models"] == sorted(AGENTS) and report["trial"] == 0
    assert report["kept"] == {"airline": 50, "retail": 114, "telecom": 114}
    # exit 0 means agent_calls refused no greeting: each of the 1,112 (a null usage) costs 0 (v1.539)
    assert (report["agent_calls"], report["greetings"]) == (calls, greetings) == (17360, 1112)
    assert (report["model_rows"], report["cascades"], report["cascade_rows"], report["rows"]) == (
        1112, 42, 11676, 12788)


def test_pinned_escalated_items_are_the_esc1b_counts_of_the_cheap_agent(pinned):
    report, _ = pinned
    _, transfer, grid = esc1b()
    cascades = m().pair_cascades(list(AGENTS), m().load_prices(PRICES)[1])
    want = {}
    for domain in ("airline", "retail", "telecom"):
        for c in cascades:
            kind, n = m().parse_signal(c.signal)
            if kind == "transfer":
                count = transfer[(domain, c.cheap)]
            else:
                over, wrote = grid[(domain, c.cheap, n)]
                count = over if kind == "calls-over" else over - wrote
            want.setdefault(domain, {})[c.id] = count
    assert report["escalated"] == want
    assert want["telecom"][f"{MINI}>{G41}@calls-over-20-no-write"] == 51
    assert want["airline"][f"{O4}>{SONNET}@transfer"] == 21
    written = {}  # review iter-386 nit 1: the written file's flags, not only the report's counts
    for line in pinned[1].read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        if "escalated" in row:
            by_task = written.setdefault(row["task"], {})
            by_task[row["model"]] = by_task.get(row["model"], 0) + row["escalated"]
    assert written == want


def test_pinned_single_model_rows_are_the_default_matrix(pinned):
    _, out = pinned
    lines = out.read_text(encoding="utf-8").splitlines()
    single = [line for line in lines if ">" not in json.loads(line)["model"]]
    assert len(lines) == 12788 and len(single) == 1112
    assert hashlib.sha256("".join(line + "\n" for line in single).encode()).hexdigest() == DEFAULT_MATRIX_SHA256
    cascade = [json.loads(line) for line in lines if ">" in json.loads(line)["model"]]
    assert {tuple(row) for row in cascade} == {("task", "item", "model", "correct", "cost_usd", "escalated")}


def test_as_of_is_a_real_date():
    as_of, _ = m().load_prices(PRICES)
    assert datetime.date.fromisoformat(as_of).isoformat() == as_of
