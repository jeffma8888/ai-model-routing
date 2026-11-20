"""README `## Start cheap, escalate on a signal` (DESIGN 7 v1.543, row ESC3d).

The part says in plain words when a cascade helps and how one is routed and priced (DESIGN 7
v1.532); its tasks-file block loads with `load_tasks` and its calibration line folds with
`calibrate_from_results`; every number of its evidence bullets is read here from the committed
tau2-bench cascade results (DESIGN 12.29) or, for the route without cascades, the 12.15
results.json; and it links the RESULTS.md section that holds the commands instead of holding them,
so the README evidence sentence keeps its count (12.13)."""

import json
import re
from pathlib import Path

import pytest

from model_routing import Cascade, calibrate_from_results, load_tasks
from test_evidence_tau2_cascade_results import beats, replay, row, task_row, to_cascade

ROOT = Path(__file__).resolve().parent.parent
README = ROOT / "README.md"
DESIGN = ROOT / "DESIGN.md"
FOLDER = ROOT / "evidence" / "tau2-bench"
HEADING = "\n## Start cheap, escalate on a signal\n"


def readme_text():
    if not README.exists():
        pytest.skip("README.md is not next to the tests")
    return README.read_text(encoding="utf-8")


def section(text=None):
    text = readme_text() if text is None else text
    assert text.count(HEADING) == 1
    return text.split(HEADING, 1)[1].split("\n## ", 1)[0]


def flat():
    return " ".join(section().split())


def load(name):
    return json.loads((FOLDER / name).read_text(encoding="utf-8"))


def r3(value):
    return f"{value:.3f}"


def usd(value):
    return f"{value:.4f} USD"


def first_block(results):
    b0 = results["config"]["bars"][0]
    return [r for r in results["summary"] if (r["bar"], r["flavor"]) == (b0, "cost_effective")]


def test_the_part_sits_between_slices_and_monitoring():
    text = readme_text()
    assert (text.index("\n## Split a task into slices\n") < text.index(HEADING)
            < text.index("\n## Monitoring and cost attribution\n"))
    assert section().isascii() and "\u2013" not in section() and "\u2014" not in section()


def test_the_part_says_what_a_cascade_is_and_how_it_is_priced():
    body = flat()
    for words in ("you can tell which only after the cheap model has tried",
                  "A cascade starts the call on a cheap model and hands it up to a strong one when such a signal "
                  "fires on the cheap model's result",
                  "one more candidate with calibration of its own, so it clears a bar only by its own measured "
                  "successes, never by the strong model's",
                  "priced as the cheap model's call plus, for its measured share of hand-ups, a strong-model call "
                  "that reads the input and the cheap model's answer as uncached input"):
        assert words in body, words


def test_the_tasks_block_and_the_calibration_line_load(tmp_path):
    body = section()
    blocks = re.findall(r"```json\n(.*?)```", body, re.S)
    assert len(blocks) == 1
    path = tmp_path / "tasks.json"
    path.write_text(blocks[0], encoding="utf-8")
    task = load_tasks(path)["support"]
    assert task.bar == 0.85
    assert task.cascades == (Cascade("anthropic/claude-haiku-5.5", "anthropic/claude-opus-5.5", "needs-human"),)
    lines = re.findall(r"`(\{\"task\": [^`]*\})`", body)
    assert len(lines) == 1
    line = json.loads(lines[0])
    assert line["model"] == task.cascades[0].id
    stats = calibrate_from_results([line])
    assert stats.get("support", line["model"]) == (1, 1) and stats.escalations("support", line["model"]) == 0
    with pytest.raises(ValueError):  # a cascade line carries no token counts (DESIGN 7 v1.532)
        calibrate_from_results([dict(line, input_tokens=10, output_tokens=2)])
    assert "A cascade line carries no token counts, since its two models' tokens would mix" in " ".join(body.split())


def test_the_part_says_how_to_call_and_check_a_cascade():
    body = flat()
    for words in ("Its ID is `cheap>strong@signal`", '`Executor.call(..., signals={"needs-human": needs_human})`',
                  "`Router.select(..., cascades=True)`", "without it no route names one",
                  "keeps the cheap model's answer when the signal is false",
                  "when it is true, or the cheap call fails, the strong model starts fresh on the same messages",
                  "`validate` checks whichever answer the entry keeps",
                  "Each log record names the model it called, and the records of a cascade entry's attempts also "
                  "carry `cascade` and `escalated`",
                  "a cascade's row names its ID as `model`, gives the whole cascade's `cost_usd` and a true or false "
                  "`escalated`", "`escalation_share`: of the held-out items in the cells routed to a cascade, the "
                  "share the cheap model handed up"):
        assert words in body, words


def test_the_part_links_the_cascades_section_and_holds_no_commands():
    body = section()
    assert (FOLDER / "RESULTS.md").read_text(encoding="utf-8").count("\n## Cascades\n") == 1
    assert "[tau2-bench cascade results](evidence/tau2-bench/RESULTS.md#cascades)" in body
    assert "```bash" not in body and "$ model-routing" not in body  # the evidence count stays (DESIGN 12.13)


def test_the_replay_numbers_are_the_committed_ones():
    results, body = load("cascades.json"), flat()
    first = first_block(results)
    cascades = [r for r in first if ">" in r["strategy"]]
    agents = [r for r in first if r["strategy"].startswith("model:") and ">" not in r["strategy"]]
    signals = list(replay().SIGNALS)
    parsed = [replay().parse_signal(s) for s in signals]
    ns = sorted({n for kind, n in parsed if kind == "calls-over"})
    assert sorted(n for kind, n in parsed if kind == "calls-over-no-write") == ns and ("transfer", None) in parsed
    assert len(parsed) == 2 * len(ns) + 1
    words = ", ".join(str(n) for n in ns[:-1]) + f" and {ns[-1]}"
    assert (f"The replay pairs the {len(agents)} agents into {len(cascades)} cascades, the cheap agent of each pair "
            f"the one at the lower input list price, on {len(signals)} signals read from the cheap run's own calls: "
            f"more than N agent calls for N of {words}, each also in a form that needs no write among the first N "
            f"calls, and the agent's call to transfer to a human agent") in body
    assert f"averaged over the {len(results['config']['seeds'])} seeds" in body
    # review iter-388 must-fix 1: a handed-up row is not only recorded spend, it adds the re-read
    assert ("on a handed-up conversation it adds the conversation so far, read once more as the strong agent's "
            "uncached input at its input list price") in body
    calls = [{"cost_usd": 0.25, "prompt_tokens": 1000, "completion_tokens": 100, "write": False, "transfer": False},
             {"cost_usd": 0.5, "prompt_tokens": 2000, "completion_tokens": 200, "write": False, "transfer": False},
             {"cost_usd": 0.75, "prompt_tokens": 3000, "completion_tokens": 300, "write": False, "transfer": False}]
    cheap, strong = {"correct": True, "cost_usd": 0.3}, {"correct": False, "cost_usd": 1.5}
    cell = replay().cascade_cell(calls, cheap, strong, "calls-over-2", 2.0)
    recorded = 0.25 + 0.5 + 1.5
    assert cell["escalated"] and abs(cell["cost_usd"] - recorded - (2000 + 200) * 2.0 / 1e6) < 1e-12


def test_the_fixed_cascade_numbers_are_the_committed_ones():
    results, body = load("cascades.json"), flat()
    first = first_block(results)
    cascades = [r for r in first if ">" in r["strategy"]]
    agents = [r for r in first if r["strategy"].startswith("model:") and ">" not in r["strategy"]]
    best = min(agents, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    winners = [r for r in cascades if beats(r, best)]
    cheap = min(winners, key=lambda r: (r["cost_usd"], r["strategy"]))
    assert (f"Always calling `{best['strategy'][6:]}` scores {r3(best['success'])} at {usd(best['cost_usd'])}, and "
            f"{len(winners)} of the {len(cascades)} cascades beat it on success and cost together") in body
    assert (f"The cheapest of them, `{cheap['strategy'][6:]}`, scores {r3(cheap['success'])} at "
            f"{r3(cheap['cost_usd'] / best['cost_usd'])} of its cost, handing up {r3(cheap['escalation_share'])} of "
            f"the conversations") in body


def test_the_routed_numbers_are_the_committed_ones():
    results, before, body = load("cascades.json"), load("results.json"), flat()
    bars = results["config"]["bars"]
    assert bars == before["config"]["bars"]
    b0 = bars[0]
    a, b = row(results, b0, "cost_effective", "routed"), row(before, b0, "cost_effective", "routed")
    assert beats(a, b)
    assert (f"At bar {b0} the `cost_effective` route with the cascades as candidates scores {r3(a['success'])} at "
            f"{usd(a['cost_usd'])}, against {r3(b['success'])} at {usd(b['cost_usd'])} without them") in body
    rest = bars[1:]
    for bar in rest:  # "scores higher but costs more" at every other bar
        a, b = row(results, bar, "cost_effective", "routed"), row(before, bar, "cost_effective", "routed")
        assert a["success"] > b["success"] and a["cost_usd"] > b["cost_usd"], bar
    assert f"at bars {rest[0]} to {rest[-1]} it scores higher but costs more" in body
    assert "Routing with cascades paid at the lowest bar only" in body
    blind = {(r3(row(results, bar, "cost_blind", "routed")["success"]),
              usd(row(results, bar, "cost_blind", "routed")["cost_usd"])) for bar in bars}
    old = {(r3(row(before, bar, "cost_blind", "routed")["success"]),
            usd(row(before, bar, "cost_blind", "routed")["cost_usd"])) for bar in bars}
    assert len(blind) == len(old) == 1
    ((s, c),), ((s0, c0),) = blind, old
    assert f"`cost_blind` scores {s} at {c} at every bar, against {s0} at {c0}" in body
    for data in (results, before):  # "no routed row, with cascades or without, beats a single agent"
        singles = [r for r in data["summary"] if r["strategy"].startswith("model:") and ">" not in r["strategy"]]
        assert len(singles) == 4 * len(bars) * 2
        for r in data["summary"]:
            if r["strategy"] == "routed":
                assert not any(beats(r, m) for m in singles), (r["bar"], r["flavor"])
    assert "no routed row, with cascades or without, beats a single agent on both counts" in body


def test_the_per_domain_numbers_are_the_committed_ones():
    results, body = load("cascades.json"), flat()
    b0, seeds = results["config"]["bars"][0], len(results["config"]["seeds"])
    counts = {task: to_cascade([task_row(results, b0, "cost_effective", task)]) for task in results["tasks"]}
    assert sorted(counts) == ["airline", "retail", "telecom"]
    order = sorted(counts, key=lambda t: (-counts[t], t))
    first, *others = order
    assert (f"At bar {b0} the `cost_effective` route sends `{first}` to a cascade on {counts[first]} of the {seeds} "
            f"seeds, " + ", ".join(f"`{t}` on {counts[t]}" for t in others[:-1])
            + f" and `{others[-1]}` on {counts[others[-1]]}") in body


def test_the_part_states_the_limits():
    body = flat()
    for words in ("this is a replay of recorded runs, not a live one",
                  "A signal measured on a benchmark may not exist in your product",
                  "The strong run in the data is a fresh conversation, so the replay restarts the conversation at "
                  "the hand-up, as the executor does",
                  "`calls-over-N` and `transfer` may hand up a run in which the cheap agent already wrote",
                  "which the replay assumes undone", "only the `-no-write` signals never hand such a run up",
                  # review iter-388 should-fix 2: -no-write does not make a telecom hand-up state-safe
                  "but in telecom the user's own device actions change state too, and no signal counts them"):
        assert words in body, words
    r = replay()  # the -no-write rule the part states, on the replay itself (DESIGN 7 v1.539)
    calls = [{"cost_usd": 0.0, "prompt_tokens": 1, "completion_tokens": 1, "write": k == 0, "transfer": False}
             for k in range(11)]
    assert r.hand_up(calls, "calls-over-10-no-write") is None and r.hand_up(calls, "calls-over-10") == 10


def test_design_names_the_part():
    text = DESIGN.read_text(encoding="utf-8")
    execution = text.split("\n## 7. ", 1)[1].split("\n## 8. ", 1)[0]
    bullets = [line for line in execution.split("\n")
               if line.startswith("- v1.543 README (row ESC3d): `## Start cheap, escalate on a signal`")]
    assert len(bullets) == 1
    for words in ("`tests/test_readme_cascades.py`", "the 12.15 results.json", "holds no `bash` block and no transcript",
                  "still counts 14 files", "the re-read at the strong agent's input price",
                  "telecom's user device actions", "only a cascade entry's records carry"):
        assert words in bullets[0], words
    sub = text.split("\n### 12.29 ", 1)[1].split("\n## ", 1)[0]
    assert "- README (v1.543, 7): README `## Start cheap, escalate on a signal` (row ESC3d)" in sub
    assert "the README part (row ESC3d)" not in sub
    assert "fails if one of the 14 results files those commands write changes by a byte" in readme_text()
