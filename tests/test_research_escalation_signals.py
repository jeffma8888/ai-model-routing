"""Row ESC1b (DESIGN 7 v1.533): research/escalation_signals.py and the note section it feeds.

The script reads the 12 pinned tau2-bench run files and each domain's pinned tools.py, and prints the
agent calls, transfers and write calls per run and, for each N of its grid, the runs over N calls and
their passes. research/escalation.md `## Measured signals (row ESC1b)` holds its output, compared byte for
byte when the run files and the tool files are already in the default cache (CI never downloads them),
and every number of that section's prose is in the block, so the other tests need no download; the
reduction, report and error exit are checked on small stubs."""

import ast
import contextlib
import importlib.util
import io
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "escalation_signals.py"
NOTE = ROOT / "research" / "escalation.md"
DESIGN = ROOT / "DESIGN.md"
CHANGELOG = ROOT / "CHANGELOG.md"
CONVERT = ROOT / "evidence" / "tau2-bench" / "convert.py"
COMMAND = "$ python research/escalation_signals.py"
MEASURED = "Measured signals (row ESC1b)"
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")
VERSION = re.compile(r"\bv\d+\.\d+\b")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def sig():
    return _load("research_escalation_signals", SCRIPT)


@pytest.fixture(scope="module")
def convert():
    return _load("tau2_convert_for_signals", CONVERT)


TOOLS = '''
class Tools(ToolKitBase):
    @is_tool(ToolType.WRITE)
    def book(self, x):
        pass

    @is_tool(ToolType.READ)
    def look(self):
        pass

    # @is_tool(ToolType.THINK)
    def think(self):
        pass

    @staticmethod
    def helper():
        pass

    @is_tool(ToolType.GENERIC)
    def transfer_to_human_agents(self, summary):
        pass
'''


def test_tool_types_reads_each_decorated_function(sig):
    assert sig.tool_types(TOOLS, "t") == {"book": "WRITE", "look": "READ", "transfer_to_human_agents": "GENERIC"}


@pytest.mark.parametrize("source", [
    "def f():\n    pass\n",
    "@is_tool('WRITE')\ndef f():\n    pass\n",
    "@is_tool(ToolType.WRITE, x=1)\ndef f():\n    pass\n",
    "class A:\n    @is_tool(ToolType.READ)\n    def f(self):\n        pass\n"
    "class B:\n    @is_tool(ToolType.READ)\n    def f(self):\n        pass\n",
    "def f(:\n",
    "@is_tool\ndef f():\n    pass\n",
    "@kit.is_tool(ToolType.READ)\ndef f():\n    pass\n",
])
def test_tool_types_rejects_what_it_cannot_read(sig, source):
    with pytest.raises(ValueError, match="^t: "):
        sig.tool_types(source, "t")


def agent(usage=True, tools=()):
    calls = [{"id": str(k), "name": name, "arguments": {}} for k, name in enumerate(tools)] or None
    return {"role": "assistant", "content": "x", "tool_calls": calls,
            "usage": {"prompt_tokens": 10, "completion_tokens": 2} if usage else None}


def run(simulations, domain="shop"):
    tasks = sorted({s["task_id"] for s in simulations})
    return {"info": {"environment_info": {"domain_name": domain}, "agent_info": {"llm": "gpt-x"},
                     "user_info": {"llm": "gpt-y"}},
            "tasks": [{"id": t} for t in tasks], "simulations": simulations}


def sim(task, reward, messages, trial=0):
    return {"task_id": task, "trial": trial, "reward_info": {"reward": reward}, "agent_cost": 0.01,
            "messages": messages}


SHOP = {"shop": {"buy": "WRITE", "look": "READ", "transfer_to_human_agents": "GENERIC"}}
USER = {"role": "user", "content": "hi"}


def stub_run():
    return run([
        sim("b", 1, [agent(False), USER, agent(tools=["look"]), {"role": "tool", "content": "ok"},
                     agent(tools=["buy", "look"]), agent()]),
        sim("a", 0, [agent(False), USER, agent(tools=["transfer_to_human_agents"])]),
        sim("a", 1, [agent(False), agent(tools=["buy"])], trial=1),
        sim("c", 1, [USER, agent(False), agent()]),
    ])


def test_reduce_run_counts_calls_transfers_and_the_first_write(sig, convert):
    got = sig.reduce_run(stub_run(), SHOP, convert)
    assert got == {"domain": "shop", "agent": "openai/gpt-x",
                   "runs": [(1, False, True, None), (3, True, False, 2), (1, True, False, None)],
                   "messages": 8, "without_first": 2, "without_later": 1}


@pytest.mark.parametrize("message", [
    {"role": "assistant", "content": "x", "tool_calls": None},
    {"role": "assistant", "content": "x", "tool_calls": [{"name": "look"}], "usage": None},
    {"role": "assistant", "content": "x", "tool_calls": [{"id": "1"}], "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
    {"role": "assistant", "content": "x", "tool_calls": "look", "usage": {"prompt_tokens": 1, "completion_tokens": 1}},
    {"role": "assistant", "content": "x", "tool_calls": None, "usage": {"prompt_tokens": 1}},
    "not an object",
])
def test_reduce_run_rejects_a_message_it_cannot_read(sig, convert, message):
    with pytest.raises(ValueError, match="^shop openai/gpt-x task 'a' trial 0: "):
        sig.reduce_run(run([sim("a", 1, [agent(False), message])]), SHOP, convert)


def test_reduce_run_rejects_a_domain_with_no_pinned_tools(sig, convert):
    with pytest.raises(ValueError, match="^mall: no tools file is pinned"):
        sig.reduce_run(run([sim("a", 1, [agent()])], domain="mall"), SHOP, convert)


def test_report_on_a_stub(sig, convert):
    one = sig.reduce_run(stub_run(), SHOP, convert)
    lines = sig.report([one], SHOP, "0123456789abcdef")
    assert lines[:3] == [
        "tau2-bench at 0123456789abcdef, 1 run files, trial 0",
        "agent messages: 8, with a usage (an agent call): 5 (0.625); without one: 3, of them the run's first message: 2",
        "",
    ]
    assert lines[3].split() == ["domain", "agent", "runs", "pass", "calls_median", "calls_max", "usage_share",
                                "transfer", "transfer_pass", "write_runs"]
    assert lines[5].split() == ["shop", "openai/gpt-x", "3", "2", "1", "3", "0.625", "1", "0", "1"]
    pooled = next(k for k, line in enumerate(lines) if line.startswith("pooled over each domain's agents (no_transfer"))
    assert lines[pooled + 3].split() == ["shop", "3", "2", "0.667", "1", "0", "0.000", "2", "1.000", "1"]
    grid = next(k for k, line in enumerate(lines) if line.startswith("runs over N agent calls"))
    assert lines[grid + 1].split() == ["domain", "agent"] + [f"N={n}" for n in sig.GRID]
    assert lines[grid + 3].split() == ["shop", "openai/gpt-x", "0/0/0", "0/0/0", "0/0/0", "0/0/0", "0/0/0"]
    rows = next(k for k, line in enumerate(lines) if line.startswith("pooled over each domain's agents (no_write"))
    assert lines[rows + 3].split() == ["shop", "5", "0", "n/a", "0", "n/a", "3", "0.667"]
    assert lines[-3:] == ["write tools (src/tau2/domains/<domain>/tools.py at 01234567, @is_tool(ToolType.WRITE)):",
                          "  shop (1): buy", "transfer_to_human_agents: shop GENERIC"]


def test_report_grid_counts_a_write_only_among_the_first_n_calls(sig):
    # review iter-378 should-fix 4: a run of exactly N calls is not over N, and a first write at call N is
    # among the first N, so `c > n` and `w <= n` are pinned at both boundaries
    reduced = [{"domain": "d", "agent": "v/m", "messages": 60, "without_first": 5, "without_later": 0,
                "runs": [(12, True, False, 3), (12, False, False, 11), (8, True, False, None),
                         (10, True, False, 10), (11, False, False, 10)]}]
    lines = sig.report(reduced, {"d": {"w": "WRITE"}}, "f" * 40)
    grid = next(k for k, line in enumerate(lines) if line.startswith("runs over N agent calls"))
    assert lines[grid + 3].split()[2:] == ["5/3/1", "3/1/2", "0/0/0", "0/0/0", "0/0/0"]
    rows = next(k for k, line in enumerate(lines) if line.startswith("pooled over each domain's agents (no_write"))
    assert lines[rows + 4].split() == ["d", "10", "3", "0.333", "1", "0.000", "2", "1.000"]
    assert lines[-1] == "transfer_to_human_agents: d absent"


def test_main_turns_a_fetch_error_into_one_line_and_exit_2(sig, tmp_path, monkeypatch, capsys):
    fake = tmp_path / "convert.py"
    fake.write_text("FILES = {}\n\ndef fetch(cache_dir=None):\n    raise OSError('x.json: download failed: boom')\n",
                    encoding="utf-8")
    monkeypatch.setattr(sig, "CONVERT", fake)
    assert sig.main(["--cache", str(tmp_path)]) == 2
    assert capsys.readouterr() == ("", "error: x.json: download failed: boom\n")


def test_tool_files_are_pinned_for_the_three_domains(sig):
    assert list(sig.TOOL_FILES) == ["airline", "retail", "telecom"]
    for size, sha256 in sig.TOOL_FILES.values():
        assert isinstance(size, int) and size > 0 and re.fullmatch(r"[0-9a-f]{64}", sha256)
    assert sig.GRID == (5, 10, 15, 20, 30)


def test_script_is_standard_library_only():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add(node.module.split(".")[0])
    stdlib = getattr(sys, "stdlib_module_names", None) or {
        "__future__", "argparse", "ast", "importlib", "statistics", "sys", "urllib", "pathlib"}
    assert names and names <= set(stdlib) | {"__future__"}


def _note():
    return NOTE.read_text(encoding="utf-8")


def _measured():
    text = _note()
    head = f"\n## {MEASURED}\n"
    assert text.count(head) == 1
    return text.split(head, 1)[1].split("\n## ", 1)[0]


def _block(section):
    return section.split("```text\n", 1)[1].split("\n```", 1)[0]


def test_measured_block_starts_with_the_command():
    assert _block(_measured()).splitlines()[0] == COMMAND


def test_measured_prose_number_tokens_appear_in_the_block():
    section = _measured()
    block = _block(section)
    prose = VERSION.sub(" ", DATE.sub(" ", section.replace(block, "")))
    known = set(NUMBER.findall(block)) | {"7", "12.14"}
    assert not sorted(set(NUMBER.findall(prose)) - known)


def test_measured_section_sets_esc3_signal_and_grid():
    section = _measured()
    for phrase in ("- Decision for row ESC3:", "`calls-over-N-no-write`", "`calls-over-N`",
                   "N = 10, 15 and 20", "a third signal, `transfer`", "an empty cell is no result"):
        assert phrase in section, phrase
    plan = _note().split("\n## What row ESC3 runs\n", 1)[1].split("\n## ", 1)[0]
    assert "`calls-over-N-no-write`" in plan and "N = 10, 15 and 20" in plan and "`transfer`" in plan


def test_the_spec_bullet_follows_the_escalation_bullet_in_design_7():
    text = DESIGN.read_text(encoding="utf-8")
    start = text.index("\n## 7. Execution with fallback (`executor.py`)\n")
    part = text[start:text.index("\n## 8. ", start)]
    head = "- v1.533 escalation signals measured (row ESC1b; research only, no package change):"
    assert part.count(head) == 1 and part.index("- v1.532 escalation (row ESC1a;") < part.index(head)
    spec = part[part.index(head):]
    for phrase in ("`research/escalation_signals.py`", "`TOOL_FILES`", "`@is_tool(ToolType.WRITE)`",
                   "an agent call is an agent message with a `usage`", "`GRID = (5, 10, 15, 20, 30)`",
                   "`over/pass/wrote`", "`calls-over-N-no-write`", "N = 10, 15 and 20", "(row ESC1c)",
                   "`tokens=True`", "`no_transfer`", "the third signal `transfer`", "among the first N"):
        assert phrase in spec, phrase


def test_the_changelog_line_names_the_row():
    mine = [line for line in CHANGELOG.read_text(encoding="utf-8").splitlines() if line.startswith("- v1.533 (")]
    assert len(mine) == 1 and "(7, row ESC1b)" in mine[0] and "`research/escalation_signals.py`" in mine[0]


def _cached():
    convert = _load("tau2_convert_cached_check", CONVERT)
    sig = _load("research_escalation_signals_cached_check", SCRIPT) if SCRIPT.exists() else None
    root = convert.default_cache_dir()
    runs = all((root / name).exists() for name in convert.FILES)
    return bool(sig) and runs and all((root / "tools" / f"{d}-tools.py").exists() for d in sig.TOOL_FILES)


@pytest.mark.skipif(not _cached(), reason="the pinned tau2-bench run and tool files are not in the default cache")
def test_note_measured_block_is_the_script_output(sig):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert sig.main([]) == 0
    assert _block(_measured()) == COMMAND + "\n" + out.getvalue().rstrip("\n")
