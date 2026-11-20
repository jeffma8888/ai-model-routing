"""Which escalation signals do the pinned tau2-bench runs record, and how does success change with them?

Usage: python research/escalation_signals.py [--cache DIR]

Reads the 12 pinned tau2-bench run files that evidence/tau2-bench/convert.py downloads, each checked
by size and sha256 before it is read, one at a time, and each domain's agent tools,
`src/tau2/domains/<domain>/tools.py` at the same pinned commit, downloaded into DIR/tools (DIR is the
converter's cache folder unless --cache names another) and checked the same way. A write tool is one
that tools.py decorates `@is_tool(ToolType.WRITE)`. An agent call is an agent message with a usage; the
agent message without one is its fixed greeting, the run's first message. At trial 0, the converter's
default, it prints per (domain, agent): runs, passes (the converter's labels), agent calls per run
(median, max), the share of agent messages with a usage, the runs that call transfer_to_human_agents
and how many of them pass, and the runs with a write call; then for each N of GRID, per (domain, agent)
and pooled per domain, the runs over N agent calls, how many pass, and how many made a write call among
their first N calls. Standard library only. Read by research/escalation.md (DESIGN 7 v1.533, row ESC1b).
"""

from __future__ import annotations

import argparse
import ast
import importlib.util
import statistics
import sys
import urllib.request
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
CONVERT = _ROOT / "evidence" / "tau2-bench" / "convert.py"
TRIAL = 0
GRID = (5, 10, 15, 20, 30)
TRANSFER = "transfer_to_human_agents"
TOOLS_PATH = "src/tau2/domains/{domain}/tools.py"
TIMEOUT = 60
# domain: (bytes, sha256) of its tools.py at the converter's pinned REVISION, read 2026-11-20
TOOL_FILES = {
    "airline": (31167, "6ec01c8c362ab0242eff658fc79547cf9519b93422ab113b6930cb627d202779"),
    "retail": (31325, "d0a9afdd44dbb1e7b1b4d19e0acf8ba9e3c99db78f775383a4b63fe5b0ccf52a"),
    "telecom": (29207, "d9d080a61b99a47523c838fe8036451ff7dfbd285946b3e87554e1033cbac44a"),
}


def _load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tool_types(source: str, label: str) -> dict:
    """{tool name: its ToolType member} for each function `source` decorates `@is_tool(ToolType.X)`.

    A commented-out decorator is no decorator, so its function is no tool. An is_tool decorator that is
    not a call of the bare name `is_tool` (`@is_tool`, `@x.is_tool(...)`), one whose one argument is not
    `ToolType.X`, a name decorated twice, or a source with no tool is a ValueError."""
    try:
        tree = ast.parse(source)
    except SyntaxError as exc:
        raise ValueError(f"{label}: not valid Python ({exc.msg})") from exc
    found = {}
    for node in ast.walk(tree):
        if not isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            continue
        for dec in node.decorator_list:
            func = dec.func if isinstance(dec, ast.Call) else dec
            named = (isinstance(func, ast.Name) and func.id == "is_tool") or (
                isinstance(func, ast.Attribute) and func.attr == "is_tool")
            if not named:
                continue
            if not (isinstance(dec, ast.Call) and isinstance(dec.func, ast.Name)):
                raise ValueError(f"{label}: {node.name}: is_tool is not called by its bare name")
            arg = dec.args[0] if len(dec.args) == 1 and not dec.keywords else None
            if not (isinstance(arg, ast.Attribute) and isinstance(arg.value, ast.Name) and arg.value.id == "ToolType"):
                raise ValueError(f"{label}: {node.name}: is_tool takes no single ToolType.X argument")
            if node.name in found:
                raise ValueError(f"{label}: tool {node.name} is decorated twice")
            found[node.name] = arg.attr
    if not found:
        raise ValueError(f"{label}: no function is decorated @is_tool")
    return found


def fetch_tools(folder, convert) -> dict:
    """{domain: tools.py text} for each domain of TOOL_FILES, downloaded into `folder` once and verified."""
    folder = Path(folder)
    folder.mkdir(parents=True, exist_ok=True)
    sources = {}
    for domain, (size, sha256) in TOOL_FILES.items():
        target = folder / f"{domain}-tools.py"
        if target.exists():
            convert.verify(target, size, sha256)
        else:
            part = target.with_name(target.name + ".part")
            url = (f"https://raw.githubusercontent.com/{convert.REPO}/{convert.REVISION}/"
                   + TOOLS_PATH.format(domain=domain))
            try:
                with urllib.request.urlopen(url, timeout=TIMEOUT) as response:
                    part.write_bytes(response.read())
            except Exception as exc:
                part.unlink(missing_ok=True)
                raise OSError(f"{target.name}: download failed: {exc}") from exc
            try:
                convert.verify(part, size, sha256)
            except BaseException:
                part.unlink(missing_ok=True)
                raise
            part.replace(target)
        sources[domain] = target.read_text(encoding="utf-8")
    return sources


def _tool_names(value, at) -> list:
    if value is None:
        return []
    if not isinstance(value, list):
        raise ValueError(f"{at}: tool_calls is not a list")
    names = []
    for call in value:
        name = call.get("name") if isinstance(call, dict) else None
        if not isinstance(name, str) or not name:
            raise ValueError(f"{at}: a tool call has no name")
        names.append(name)
    return names


def reduce_run(run, tools: dict, convert, trial: int = TRIAL) -> dict:
    """One parsed run file at `trial`: its domain, agent, message counts and per run, in task order,
    (agent calls, passed, called transfer_to_human_agents, the 1-based agent call of its first write call
    or None). The labels are the converter's: `convert.extract` checks the run, reads each reward and,
    with `tokens=True`, checks that each usage holds int token counts, so every agent call can be priced."""
    e = convert.extract(run, trial, tokens=True)
    domain, agent = e["domain"], e["agent"]
    if domain not in tools:
        raise ValueError(f"{domain}: no tools file is pinned for this domain")
    writes = {name for name, kind in tools[domain].items() if kind == "WRITE"}
    where = f"{domain} {agent}"
    runs = {}
    messages = without_first = without_later = 0
    for entry in run["simulations"]:
        if entry["trial"] != trial:
            continue
        at = f"{where} task {entry['task_id']!r} trial {trial}"
        listed = entry.get("messages")
        if not isinstance(listed, list):
            raise ValueError(f"{at}: messages is not a list")
        calls, transfer, first_write = 0, False, None
        for k, message in enumerate(listed):
            if not isinstance(message, dict):
                raise ValueError(f"{at}: a message is a {type(message).__name__}, not an object")
            if message.get("role") != "assistant":
                continue
            messages += 1
            if "usage" not in message:
                raise ValueError(f"{at}: an agent message has no usage key")
            names = _tool_names(message.get("tool_calls"), at)
            if message["usage"] is None:
                if names:
                    raise ValueError(f"{at}: an agent message without a usage calls a tool")
                if k == 0:
                    without_first += 1
                else:
                    without_later += 1
                continue
            calls += 1
            transfer = transfer or TRANSFER in names
            if first_write is None and writes.intersection(names):
                first_write = calls
        runs[entry["task_id"]] = (calls, e["cells"][entry["task_id"]]["correct"], transfer, first_write)
    return {"domain": domain, "agent": agent, "runs": [runs[t] for t in sorted(runs)], "messages": messages,
            "without_first": without_first, "without_later": without_later}


def _share(part: int, whole: int) -> str:
    return f"{part / whole:.3f}" if whole else "n/a"


def _median(values) -> str:
    return f"{statistics.median(values):g}" if values else "n/a"


def report(reduced: list, tools: dict, revision: str) -> list:
    """Lines for the reduce_run dicts of every run file and the tool_types of every domain."""
    rows = sorted(reduced, key=lambda r: (r["domain"], r["agent"]))
    messages = sum(r["messages"] for r in rows)
    first = sum(r["without_first"] for r in rows)
    later = sum(r["without_later"] for r in rows)
    calls = messages - first - later
    width = max([len("agent")] + [len(r["agent"]) for r in rows])
    dom = max([len("domain")] + [len(r["domain"]) for r in rows])
    lines = [
        f"tau2-bench at {revision}, {len(rows)} run files, trial {TRIAL}",
        f"agent messages: {messages:,}, with a usage (an agent call): {calls:,} ({_share(calls, messages)}); "
        f"without one: {first + later:,}, of them the run's first message: {first:,}",
        "",
        f"{'domain':<{dom}}  {'agent':<{width}}  runs  pass  calls_median  calls_max  usage_share  "
        "transfer  transfer_pass  write_runs",
        f"{'-' * dom}  {'-' * width}  ----  ----  ------------  ---------  -----------  "
        "--------  -------------  ----------",
    ]
    for r in rows:
        n = [c for c, _, _, _ in r["runs"]]
        transfer = [ok for _, ok, t, _ in r["runs"] if t]
        wrote = sum(w is not None for _, _, _, w in r["runs"])
        with_usage = r["messages"] - r["without_first"] - r["without_later"]
        lines.append(f"{r['domain']:<{dom}}  {r['agent']:<{width}}  {len(r['runs']):>4}  "
                     f"{sum(ok for _, ok, _, _ in r['runs']):>4}  {_median(n):>12}  {max(n, default=0):>9}  "
                     f"{_share(with_usage, r['messages']):>11}  {len(transfer):>8}  {sum(transfer):>13}  "
                     f"{wrote:>10}")
    lines += ["", "pooled over each domain's agents (no_transfer: runs that never call transfer_to_human_agents)",
              f"{'domain':<{dom}}  runs  pass  pass_rate  transfer  transfer_pass  transfer_rate  "
              "no_transfer  no_transfer_rate  write_runs",
              f"{'-' * dom}  ----  ----  ---------  --------  -------------  -------------  "
              "-----------  ----------------  ----------"]
    for domain in sorted({r["domain"] for r in rows}):
        pooled = [run for r in rows if r["domain"] == domain for run in r["runs"]]
        passed = sum(ok for _, ok, _, _ in pooled)
        transfer = [ok for _, ok, t, _ in pooled if t]
        other = [ok for _, ok, t, _ in pooled if not t]
        wrote = sum(w is not None for _, _, _, w in pooled)
        lines.append(f"{domain:<{dom}}  {len(pooled):>4}  {passed:>4}  {_share(passed, len(pooled)):>9}  "
                     f"{len(transfer):>8}  {sum(transfer):>13}  {_share(sum(transfer), len(transfer)):>13}  "
                     f"{len(other):>11}  {_share(sum(other), len(other)):>16}  {wrote:>10}")
    cell = 10
    lines += ["", "runs over N agent calls, each cell over/pass/wrote (wrote: a write call among its first N calls)",
              f"{'domain':<{dom}}  {'agent':<{width}}" + "".join(f"  {'N=' + str(n):>{cell}}" for n in GRID),
              f"{'-' * dom}  {'-' * width}" + "".join(f"  {'-' * cell}" for _ in GRID)]
    for r in rows:
        cells = []
        for n in GRID:
            over = [(ok, w) for c, ok, _, w in r["runs"] if c > n]
            wrote = sum(w is not None and w <= n for _, w in over)
            cells.append(f"{len(over)}/{sum(ok for ok, _ in over)}/{wrote}")
        lines.append(f"{r['domain']:<{dom}}  {r['agent']:<{width}}" + "".join(f"  {c:>{cell}}" for c in cells))
    lines += ["", "pooled over each domain's agents (no_write: runs over N with no write call among their first N calls)",
              f"{'domain':<{dom}}   N  over  pass_over  no_write  pass_no_write  at_most  pass_at_most",
              f"{'-' * dom}  --  ----  ---------  --------  -------------  -------  ------------"]
    for domain in sorted({r["domain"] for r in rows}):
        pooled = [run for r in rows if r["domain"] == domain for run in r["runs"]]
        for n in GRID:
            over = [(ok, w) for c, ok, _, w in pooled if c > n]
            clean = [ok for ok, w in over if w is None or w > n]
            under = [ok for c, ok, _, _ in pooled if c <= n]
            lines.append(f"{domain:<{dom}}  {n:>2}  {len(over):>4}  {_share(sum(ok for ok, _ in over), len(over)):>9}  "
                         f"{len(clean):>8}  {_share(sum(clean), len(clean)):>13}  {len(under):>7}  "
                         f"{_share(sum(under), len(under)):>12}")
    shown = TOOLS_PATH.format(domain="<domain>")
    lines += ["", f"write tools ({shown} at {revision[:8]}, @is_tool(ToolType.WRITE)):"]
    for domain in sorted(tools):
        names = sorted(name for name, kind in tools[domain].items() if kind == "WRITE")
        lines.append(f"  {domain} ({len(names)}): {', '.join(names)}")
    kinds = {domain: tools[domain].get(TRANSFER, "absent") for domain in sorted(tools)}
    lines.append(f"{TRANSFER}: " + ", ".join(f"{domain} {kind}" for domain, kind in kinds.items()))
    return lines


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--cache", default=None, help="download folder (default: the converter's)")
    args = parser.parse_args(argv)
    try:
        convert = _load(CONVERT, "tau2_bench_convert")
        folder = convert.fetch(args.cache)
        sources = fetch_tools(folder / "tools", convert)
        tools = {domain: tool_types(text, f"{domain}-tools.py") for domain, text in sources.items()}
        reduced = [reduce_run(convert.read_run(folder / name), tools, convert) for name in convert.FILES]
    except (OSError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    print("\n".join(report(reduced, tools, convert.REVISION)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
