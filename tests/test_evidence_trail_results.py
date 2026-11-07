"""Committed TRAIL files contract (DESIGN 13.11, v1.70), written before the files and kept as their tests.

``evidence/trail/summary.json``, its ``RESULTS.md``, the README delegation sentence and Layout line,
and the TRAIL figures of ``research/hand-off-data.md``, each built from the committed summary. Every
test reads a committed TRAIL file before any assertion that could fail, so each one failed with ``FileNotFoundError`` under a
strict xfail until v1.71 committed the files and removed the mark. One test reads the pinned traces only when all 117 are already in the
default cache and skips otherwise (CI never downloads them).
"""

import importlib.util
import json
import re
import statistics
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "trail"
SCRIPT = FOLDER / "summary.py"
SUMMARY = FOLDER / "summary.json"
RESULTS_MD = FOLDER / "RESULTS.md"
README = ROOT / "README.md"
HAND_OFF = ROOT / "research" / "hand-off-data.md"
WORKFLOW = ROOT / ".github" / "workflows" / "evidence.yml"
DELEGATION = ROOT / "evidence" / "delegation"
REVISION = "0ffbed9db859b4a66250dc783fa4dccf86869595"
REPO_URL = "https://github.com/patronus-ai/trail-benchmark"
COMMAND = "python evidence/trail/summary.py --out evidence/trail/summary.json"
STATS = ["model_calls", "prompt_tokens", "completion_tokens", "first_call_prompt_tokens"]
RUN_KEYS = ["trace_id", "span_id", "model_calls", "prompt_tokens", "completion_tokens",
            "first_call_prompt_tokens"]
INDENT = " " * 16
DELEGATION_LAYOUT = INDENT + "(delegation on AutoBench: evidence/delegation/RESULTS.md)\n"
TRAIL_LAYOUT = INDENT + "(TRAIL sub-agent sizes: evidence/trail/RESULTS.md)\n"


def load_script():
    spec = importlib.util.spec_from_file_location("trail_summary_results", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def committed():
    return json.loads(SUMMARY.read_text(encoding="utf-8"))


def num(value):
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}"


def grouped(summary):
    per_trace, seen = [], {}
    for run in summary["runs"]:
        if run["trace_id"] not in seen:
            seen[run["trace_id"]] = []
            per_trace.append(seen[run["trace_id"]])
        seen[run["trace_id"]].append(run)
    return per_trace + [[] for _ in range(summary["traces"] - len(per_trace))]


def counts_sentence(summary):
    return (f"In {summary['traces_with_runs']} of the {summary['traces']} GAIA traces the top agent "
            "(`CodeAgent.run`) hands work to a sub-agent (`ToolCallingAgent.run`), "
            f"{summary['run_count']} sub-agent runs in all.")


def split_sentence(summary):
    per_trace = {}
    for run in summary["runs"]:
        per_trace[run["trace_id"]] = per_trace.get(run["trace_id"], 0) + 1
    counts = sorted(per_trace.values())
    assert sorted(set(counts)) == [1, 2, 3]
    return (f"{counts.count(1)} traces hold one run, {counts.count(2)} two and "
            f"{counts.count(3)} three.")


def commit_date():
    note = HAND_OFF.read_text(encoding="utf-8")
    dates = re.findall(rf"GitHub {REVISION} \(commit date (\d{{4}}-\d{{2}}-\d{{2}})\)", note)
    assert len(dates) == 1
    return dates[0]


def stats_table(summary):
    rows = ["| count | min | median | max |", "|---|---|---|---|"]
    for key in STATS:
        s = summary["stats"][key]
        rows.append(f"| `{key}` | {num(s['min'])} | {num(s['median'])} | {num(s['max'])} |")
    return "\n".join(rows) + "\n"


def readme_sentence(summary):
    calls = summary["stats"]["model_calls"]
    return ("Real sub-agent runs make more model calls than the grid's one, or two at variant "
            "point 0 below (`work_calls`): in the public TRAIL traces (licence MIT), the top agent "
            f"hands work to a sub-agent {summary['run_count']} times in "
            f"{summary['traces_with_runs']} of {summary['traces']} GAIA traces, and each of those "
            f"runs makes {num(calls['min'])} to {num(calls['max'])} model calls (median "
            f"{num(calls['median'])}), observed usage only, since TRAIL has no success label and no "
            "run of a task without its sub-agent "
            "([evidence/trail/RESULTS.md](evidence/trail/RESULTS.md), `DESIGN.md` 13.11).")


def hand_off_figures(summary, files):
    st = summary["stats"]
    mc, pt, ct, fc = (st[k] for k in STATS)
    n, t = summary["run_count"], summary["traces"]
    calls = f"{num(mc['min'])} to {num(mc['max'])} model calls"
    return [
        f"{len(files)} GAIA traces ({sum(size for size, _ in files.values()):,} bytes)",
        f"Its {n} sub-agent runs make {calls} each (median {num(mc['median'])})",
        f"In {summary['traces_with_runs']} of the {t} GAIA traces the top agent hands work to a "
        f"sub-agent: {n} sub-agent runs in all",
        f"The {n} sub-agent runs: {calls} each (median {num(mc['median'])}); {num(pt['min'])} to "
        f"{num(pt['max'])} prompt tokens per run (median {num(pt['median'])}) and "
        f"{num(ct['min'])} to {num(ct['max'])} completion tokens (median {num(ct['median'])}); the "
        f"first model call of each run reads {num(fc['min'])} to {num(fc['max'])} prompt tokens",
        f"its {n} runs make {calls} (median {num(mc['median'])}) against the grid's one or two, "
        f"and read {num(pt['min'])} to {num(pt['max'])} prompt tokens per run",
    ]


def committed_work_calls():
    base = json.loads((DELEGATION / "results.json").read_text(encoding="utf-8"))["config"]["points"]
    variants = json.loads((DELEGATION / "variants.json").read_text(encoding="utf-8"))["config"]["points"]
    return [p.get("work_calls", 1) for p in base], [p.get("work_calls", 1) for p in variants]


def readme_delegation():
    text = README.read_text(encoding="utf-8")
    section = text.split("\n## Evidence: held-out results on public data\n", 1)[1].split("\n## ", 1)[0]
    marker = "\n### Delegation on AutoBench\n"
    assert section.count(marker) == 1
    return section.split(marker, 1)[1].split("\n### ", 1)[0]


# --- summary.json -----------------------------------------------------------------------------

def test_summary_is_small_canonical_and_self_consistent():
    text = SUMMARY.read_text(encoding="utf-8")
    assert SUMMARY.stat().st_size < 300_000
    summary = json.loads(text)
    assert text == json.dumps(summary, indent=2) + "\n"
    tr = load_script()
    assert list(summary) == ["source", "traces", "traces_with_runs", "run_count", "stats", "runs"]
    assert summary["source"] == {"repo": tr.REPO_URL, "folder": tr.FOLDER,
                                 "revision": tr.REVISION, "licence": tr.LICENCE}
    assert (summary["source"]["repo"], summary["source"]["revision"]) == (REPO_URL, REVISION)
    assert summary["traces"] == len(tr.FILES)
    runs = summary["runs"]
    assert summary["run_count"] == len(runs) > 0
    assert all(list(run) == RUN_KEYS for run in runs)
    assert summary["traces_with_runs"] == len({run["trace_id"] for run in runs})
    assert {run["trace_id"] + ".json" for run in runs} <= set(tr.FILES)
    assert list(summary["stats"]) == STATS
    for key in STATS:
        values = [run[key] for run in runs]
        assert summary["stats"][key] == {"min": min(values),
                                         "median": float(statistics.median(values)),
                                         "max": max(values)}
    assert tr.summarize(grouped(summary)) == summary


def test_summary_regenerates_byte_identical_when_cached(tmp_path, capsys):
    expected = SUMMARY.read_bytes()
    tr = load_script()
    cache = tr.default_cache_dir()
    if not all((cache / name).is_file() for name in tr.FILES):
        pytest.skip("the 117 pinned TRAIL traces are not in the default cache")
    out = tmp_path / "summary.json"
    assert tr.main(["--out", str(out)]) == 0
    capsys.readouterr()
    assert out.read_bytes() == expected


# --- RESULTS.md -------------------------------------------------------------------------------

def test_results_md_states_the_counts_table_source_command_and_caveats():
    summary = committed()
    md = RESULTS_MD.read_text(encoding="utf-8")
    tr = load_script()
    assert md.startswith("# TRAIL sub-agent sizes\n")
    assert md.count(counts_sentence(summary)) == 1
    assert md.count(counts_sentence(summary) + " " + split_sentence(summary)) == 1
    assert md.count(stats_table(summary)) == 1
    total = sum(size for size, _ in tr.FILES.values())
    for phrase in (f"[summary.json](summary.json) ({SUMMARY.stat().st_size:,} bytes)",
                   REPO_URL, f"[`{REVISION}`]({REPO_URL}/tree/{REVISION}) (commit date {commit_date()})",
                   "`benchmarking/data/GAIA`", "Licence: MIT", "Copyright (c) 2025 patronus-ai",
                   f"```bash\n{COMMAND}\n```\n", f"{len(tr.FILES)} pinned files ({total:,} bytes)",
                   "observed usage, not the inputs of DESIGN 13.1",
                   "must never be read as K times the work's input per call",
                   "\n- No success label", "\n- No run of a task without its sub-agent",
                   "\n- The sub-agent is its parent's model", "feed no decision and no results file",
                   "The `evidence` workflow does not rerun it"):
        assert phrase in md, phrase
    assert md.count("```bash\n") == 1
    assert not (FOLDER / "README.md").exists()


def test_stats_table_writes_whole_medians_without_a_decimal():
    RESULTS_MD.read_text(encoding="utf-8")
    summary = {"stats": {k: {"min": 1, "median": 2.0, "max": 1234} for k in STATS}}
    assert "| `model_calls` | 1 | 2 | 1,234 |\n" in stats_table(summary)
    assert num(94868.5) == "94,868.5" and num(15.0) == "15" and num(357993) == "357,993"


def test_workflow_does_not_rerun_the_trail_script():
    assert "The `evidence` workflow does not rerun it" in RESULTS_MD.read_text(encoding="utf-8")
    assert "evidence/trail" not in WORKFLOW.read_text(encoding="utf-8")


# --- README and research ----------------------------------------------------------------------

def test_readme_delegation_sentence_is_built_from_the_summary_and_the_points():
    summary = committed()
    base, variants = committed_work_calls()
    assert set(base) == {1} and variants[0] == 2
    assert summary["stats"]["model_calls"]["min"] > max(base + variants)
    sub = readme_delegation()
    sentence = readme_sentence(summary)
    assert sub.count(sentence) == 1
    assert sub.index("[research/hand-off-data.md]") < sub.index(sentence) < sub.index("```text\n")


def test_readme_layout_names_the_trail_results_after_the_delegation_line():
    RESULTS_MD.read_text(encoding="utf-8")
    text = README.read_text(encoding="utf-8")
    layout = text.split("\n## Layout\n", 1)[1].split("\n## ", 1)[0]
    assert layout.count(TRAIL_LAYOUT) == 1 and layout.count(DELEGATION_LAYOUT) == 1
    assert layout.index(DELEGATION_LAYOUT) + len(DELEGATION_LAYOUT) == layout.index(TRAIL_LAYOUT)


def test_research_hand_off_numbers_are_the_summary():
    summary = committed()
    note = HAND_OFF.read_text(encoding="utf-8")
    for figure in hand_off_figures(summary, load_script().FILES):
        assert figure in note, figure
