"""DESIGN 12.29 v1.555 (row ESC3g): the tau2-bench cascade rows per domain.

``evidence/tau2-bench/cascades.json`` keeps a domain's row for ``routed`` alone, since the 12.7 script
drops every other ``per_task`` row. ``evidence/tau2-bench/domains.py`` reduces the same ``evaluate``
output to the ``model:`` ``per_task`` rows at its first (bar, flavor), checking that a row's success,
cost and ``escalation_share`` are the same at every other, into ``evidence/tau2-bench/cascades-domains.json``,
and prints each domain's best single agent (12.15's rule) and the cascades that beat it on both counts.
The tau2-bench RESULTS.md gains ``## Cascades by domain``, whose every number these tests build from the
file by their own rule. The tests that read the file or the script were committed before them under strict
xfail (v1.555); the commit that adds them (v1.556) removes the marks. The pinned-file test runs the replay
once when the 12 run files and the 3 tool files are in the default cache and skips otherwise.
"""

import contextlib
import io
import json
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows
from test_evidence_tau2_cascade_results import beats, r3, replay, usd
from test_evidence_tau2_results import BARS, load

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "tau2-bench"
FILE = FOLDER / "cascades-domains.json"
CASCADES = FOLDER / "cascades.json"
SCRIPT = FOLDER / "domains.py"
RESULTS_MD = FOLDER / "RESULTS.md"
DESIGN = ROOT / "DESIGN.md"
HEADING = "Cascades by domain"
TABLE = "python evidence/tau2-bench/domains.py --table evidence/tau2-bench/cascades-domains.json"
COMMAND = ("python evidence/tau2-bench/domains.py --evaluate tau2-cascades-evaluate.json"
           " --out evidence/tau2-bench/cascades-domains.json")
NUMBERS = {1: "one", 2: "two", 3: "three"}
_loaded = []


def script():
    if not _loaded:
        _loaded.append(load("tau2_cascade_domains", SCRIPT))
    return _loaded[0]


def committed():
    return json.loads(FILE.read_text(encoding="utf-8"))


def pooled():
    return json.loads(CASCADES.read_text(encoding="utf-8"))


def section():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert text.count(f"\n## {HEADING}\n") == 1
    return text.split(f"\n## {HEADING}\n", 1)[1].split("\n## ", 1)[0]


def best_and_winners(rows, task):
    """The tests' own rule: 12.15's best single agent, then the cascades that beat it, by success."""
    mine = [r for r in rows if r["task"] == task]
    best = min((r for r in mine if ">" not in r["strategy"]), key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    winners = [r for r in mine if ">" in r["strategy"] and beats(r, best)]
    winners.sort(key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    return best, winners


def name(r):
    return r["strategy"][len("model:"):]


def words(tasks):
    if not tasks:
        return "no domain"
    if len(tasks) == 1:
        return f"`{tasks[0]}` only"
    return ", ".join(f"`{t}`" for t in tasks[:-1]) + f" and `{tasks[-1]}`"


def phrases(results):
    rows, tasks = results["per_task"], results["tasks"]
    sizes = {len(t["models"]) for t in tasks.values()}
    assert len(sizes) == 1
    out = [f"{len(rows)} rows ({len(tasks)} domains of {sizes.pop()} candidates)"]
    blocks = {(r["bar"], r["flavor"]) for r in rows}
    assert len(blocks) == 1
    bar, flavor = blocks.pop()
    out.append(f"the rows at bar {bar} and `{flavor}`")  # review iter-401 nit 3
    out.append(f"Each candidate's {NUMBERS[len(tasks)]} domain costs add up to its `model:` row's cost")
    paying, counts = [], set()
    for task, info in tasks.items():
        k = sum(">" in m for m in info["models"])
        counts.add(k)
        best, winners = best_and_winners(rows, task)
        head = f"`{task}`: the best single agent, `{name(best)}`, holds {r3(best['success'])} at {usd(best['cost_usd'])}"
        if not winners:
            out.append(f"{head}, and none of the {k} cascades beats it on both counts")
            continue
        paying.append(task)
        top = winners[0]
        cheap = min(winners, key=lambda r: (r["cost_usd"], r["strategy"]))
        out.append(f"{head}, and {len(winners)} of the {k} cascades beat it on both counts: " + "; ".join(
            f"{label}, `{name(r)}`, {r3(r['success'])} at {usd(r['cost_usd'])}, "
            f"{r3(r['cost_usd'] / best['cost_usd'])} of the agent's cost, `escalation_share` {r3(r['escalation_share'])}"
            for label, r in (("the highest", top), ("the cheapest", cheap))))
    assert len(counts) == 1
    rest = [task for task in tasks if task not in paying]
    out.append(f"A cascade fixed for a domain beats its best single agent on both counts in {words(paying)}"
               + (f"; in {words(rest).replace(' only', '')} none of the {counts.pop()} does" if rest else ""))
    return out  # review iter-401 nit 2: the second half built from the domains where none pays


def hand_built():
    """Two bars, both flavors, two domains; `b` ties `a` on success at a lower cost, so it is the best agent."""
    config = {"bars": [0.3, 0.4], "flavors": ["cost_effective", "cost_blind"]}
    values = {"a": (0.5, 10.0, None), "b": (0.5, 8.0, None), "a>b@x": (0.6, 9.0, 0.2), "b>a@y": (0.6, 7.0, 0.4),
              "a>b@z": (0.5, 8.0, 0.1), "b>a@w": (0.4, 1.0, 0.9),
              # review iter-401 should-fix 1: two more winners, one tying `b>a@y` on both counts (sorted first by
              # name) and one on success at a higher cost (sorted after it), so the winners' order is exercised
              "a>b@u": (0.6, 7.0, 0.3), "b>a@v": (0.6, 7.6, 0.3)}
    per_task = []
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            for task in ("t1", "t2"):
                per_task.append({"bar": bar, "flavor": flavor, "task": task, "strategy": "routed", "success": 0.1,
                                 "cost_usd": 1.0, "below_bar_rate": 0.0, "escalation_share": None})
                for model, (success, cost, share) in values.items():
                    per_task.append({"bar": bar, "flavor": flavor, "task": task, "strategy": f"model:{model}",
                                     "success": success, "cost_usd": cost, "below_bar_rate": bar,
                                     "escalation_share": share})
    tasks = {t: {"items": 4, "models": sorted(values)} for t in ("t1", "t2")}
    return {"config": config, "tasks": tasks, "summary": [], "per_task": per_task}


# --- the spec, before the script and the file

def test_design_12_29_specifies_the_domain_rows():
    text = DESIGN.read_text(encoding="utf-8")
    body = text.split("\n### 12.29 ", 1)[1].split("\n### ", 1)[0]
    for words_ in ["- Per domain (v1.555, row ESC3g): `evidence/tau2-bench/domains.py`", f"`{COMMAND}`", f"`{TABLE}`",
                   f"`## {HEADING}`, after `## Cascades` and before `## Regenerate`",
                   "`tests/test_evidence_tau2_cascade_domains.py`", "(row ESC3s)",
                   "`pytest.mark.xfail(strict=True, raises=(FileNotFoundError, ModuleNotFoundError))`"]:
        assert words_ in body, words_


# --- the script on hand-built results

def test_reduce_keeps_the_first_blocks_model_rows():
    out = script().reduce(hand_built())
    assert list(out) == ["config", "tasks", "per_task"]
    assert len(out["per_task"]) == 16
    assert out["config"] == hand_built()["config"] and out["tasks"] == hand_built()["tasks"]  # review iter-401 nit 4
    assert all((r["bar"], r["flavor"]) == (0.3, "cost_effective") for r in out["per_task"])
    assert all(r["strategy"].startswith("model:") for r in out["per_task"])
    assert script().reduce(out) == out


def test_reduce_refuses_a_row_that_changes_with_the_block():
    for key in ("success", "cost_usd", "escalation_share"):
        result = hand_built()
        moved = next(r for r in result["per_task"] if (r["bar"], r["flavor"], r["strategy"]) == (0.4, "cost_blind", "model:a"))
        moved[key] = 0.99
        with pytest.raises(ValueError, match=key):
            script().reduce(result)
    result = hand_built()
    result["per_task"] = [r for r in result["per_task"]
                          if (r["bar"], r["flavor"], r["task"], r["strategy"]) != (0.3, "cost_effective", "t2", "model:b")]
    with pytest.raises(ValueError, match="no row for t2, model:b"):
        script().reduce(result)
    for key in ("config", "tasks", "per_task"):
        result = hand_built()
        result.pop(key)
        with pytest.raises(ValueError, match=key):
            script().reduce(result)


def test_table_gives_the_best_agent_then_the_cascades_that_beat_it():
    lines = script().table(script().reduce(hand_built())).split("\n")
    assert lines[0].split() == ["task", "candidate", "success", "cost_usd", "vs_agent", "escalation_share"]
    rows = [line.split() for line in lines[2:]]
    assert rows == [[task, *row] for task in ("t1", "t2") for row in (
        ["b", "0.500", "8.0000", "1.000", "-"], ["a>b@u", "0.600", "7.0000", "0.875", "0.300"],
        ["b>a@y", "0.600", "7.0000", "0.875", "0.400"], ["b>a@v", "0.600", "7.6000", "0.950", "0.300"])]


def test_the_cli_writes_the_file_and_refuses_bad_use(tmp_path, capsys):
    full = tmp_path / "full.json"
    full.write_text(json.dumps(hand_built()), encoding="utf-8")
    out = tmp_path / "domains.json"
    assert script().main(["--evaluate", str(full), "--out", str(out)]) == 0
    assert out.read_text(encoding="utf-8") == json.dumps(script().reduce(hand_built()), indent=2) + "\n"
    assert not list(tmp_path.glob("*.part"))
    assert script().main(["--table", str(out)]) == 0
    assert capsys.readouterr().out == script().table(script().reduce(hand_built())) + "\n"
    for argv in (["--evaluate", str(full)], ["--table", str(out), "--out", str(out)], []):
        assert script().main(argv) == 2
        err = capsys.readouterr().err
        assert len(err.splitlines()) == 1 and err.startswith("error: ")


# --- the committed file

def test_the_file_is_small_reduces_to_itself_and_holds_the_runs_config_and_tasks():
    text = FILE.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 300_000
    results = json.loads(text)
    assert text == json.dumps(script().reduce(results), indent=2) + "\n"
    assert results["config"] == pooled()["config"] and results["tasks"] == pooled()["tasks"]


def test_the_file_holds_one_row_per_domain_and_candidate_at_the_first_block():
    results = committed()
    keys = [(r["task"], r["strategy"]) for r in results["per_task"]]
    assert len(keys) == len(set(keys)) == 138
    assert set(keys) == {(t, f"model:{m}") for t, info in results["tasks"].items() for m in info["models"]}
    assert all((r["bar"], r["flavor"]) == (BARS[0], "cost_effective") for r in results["per_task"])


def test_each_candidates_domain_costs_add_up_to_its_pooled_cost():
    results, before = committed(), pooled()
    summary = {r["strategy"]: r for r in before["summary"] if (r["bar"], r["flavor"]) == (BARS[0], "cost_effective")}
    for strategy in {r["strategy"] for r in results["per_task"]}:
        total = sum(r["cost_usd"] for r in results["per_task"] if r["strategy"] == strategy)
        assert abs(total - summary[strategy]["cost_usd"]) < 1e-9, strategy


# --- RESULTS.md

def test_results_md_holds_the_section_with_its_table_and_command():
    results = committed()
    text = RESULTS_MD.read_text(encoding="utf-8")
    headings = [line[3:] for line in text.splitlines() if line.startswith("## ")]
    assert headings[headings.index("Cascades") + 1:] == [HEADING, "Regenerate"]
    assert f"`## Cascades` and `## {HEADING}`" in text.split("\n## ", 1)[0]
    body = section()
    assert "[cascades-domains.json](cascades-domains.json)" in body and f"`{TABLE}`" in body
    assert "```text\n" + script().table(results) + "\n```" in body
    # review iter-401 should-fix 1: the block's rows, in order, are the tests' own rule, not only the script's
    block = body.split("```text\n", 1)[1].split("\n```", 1)[0].split("\n")[2:]
    want = [[task, name(r)] for task in results["tasks"]
            for best, winners in [best_and_winners(results["per_task"], task)] for r in [best] + winners]
    assert [line.split()[:2] for line in block] == want
    assert body.count("```bash") == 1 and f"```bash\n{COMMAND}\n```" in body
    before = body.split("```bash", 1)[0].rstrip("\n").split("\n")[-1]
    assert "the `evidence` workflow does not rerun it yet" in before
    cascades = text.split("\n## Cascades\n", 1)[1].split("\n## ", 1)[0]
    assert f"`## {HEADING}` gives each domain's" in " ".join(cascades.split())


def test_each_number_of_the_section_is_the_file():
    results = committed()
    body = " ".join(section().split())
    for words_ in phrases(results):
        assert words_ in body, words_
    assert "add up to its `model:` row's cost in [cascades.json](cascades.json)" in body
    assert "by success, then lower cost, then name; `vs_agent` divides each cost by the agent's" in body  # nit 1


# --- the pinned files, only when already cached

@pytest.fixture(scope="module")
def pinned_result(tmp_path_factory):
    convert = replay().convert
    folder = convert.default_cache_dir()
    names = [folder / n for n in convert.FILES]
    names += [folder / "tools" / f"{domain}-tools.py" for domain in replay().signals.TOOL_FILES]
    if not all(path.is_file() for path in names):
        pytest.skip("the 12 pinned tau2-bench run files or the 3 tool files are not in the default cache")
    out = tmp_path_factory.mktemp("tau2-cascade-domains") / "rows.jsonl"
    with contextlib.redirect_stdout(io.StringIO()):
        assert replay().main(["--out", str(out)]) == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    result = evaluate(outcomes_from_rows(rows), bars=BARS, seeds=range(50))
    result.pop("cells")
    return result


def test_pinned_files_rebuild_the_file_byte_for_byte(pinned_result):
    text = FILE.read_text(encoding="utf-8")
    assert json.dumps(script().reduce(pinned_result), indent=2) + "\n" == text
