"""DESIGN 12.29 v1.541 (row ESC3c): the tau2-bench cascade results.

One file, ``evidence/tau2-bench/cascades.json``, holds ``model-routing evaluate`` at the 12.15
bars and seeds on the matrix that ``evidence/tau2-bench/cascades.py --out`` writes (DESIGN 7
v1.540: the 12.14 default matrix plus one row per item and cascade for 42 cascades), reduced by
the RouterBench results script (12.7). The tau2-bench RESULTS.md gains a ``## Cascades`` section
whose every number these tests build from the file, or from ``results.json`` where it says
12.15. The tests that read the file were committed before it under strict xfail (v1.541); the
commit that adds it (v1.542) removes the marks. The pinned-file test runs the replay once when
the 12 run files and the 3 tool files are in the default cache and skips otherwise, as CI never
downloads them.
"""

import contextlib
import io
import json
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows
from test_evidence_tau2_results import BARS, CONFIG, MODELS, TASKS, load

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "tau2-bench"
FILE = FOLDER / "cascades.json"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
DESIGN = ROOT / "DESIGN.md"
SCRIPT = FOLDER / "cascades.py"
HEADINGS = ["Source and licence", "Results", "Reading it", "Sensitivity", "Cascades", "Regenerate"]
TABLE = "python evidence/routerbench/results.py --table evidence/tau2-bench/cascades.json"
COMMANDS = [
    "python evidence/tau2-bench/cascades.py --out tau2-cascades.jsonl",
    "model-routing evaluate --outcomes tau2-cascades.jsonl --bar 0.3 0.4 0.5 0.6 0.7 0.8 --seeds 50"
    " --json > tau2-cascades-evaluate.json",
    "python evidence/routerbench/results.py --evaluate tau2-cascades-evaluate.json"
    " --out evidence/tau2-bench/cascades.json",
]
OPENING = ("The file behind every number here but those of `## Cascades` is [results.json](results.json)")
SINGLE = ("routed", "oracle", "best_on_calibration", "cheapest")
LIMITS = [
    "a signal measured on a benchmark may not exist in your product",
    "the strong run in the data is a fresh conversation with its own simulated user, so the replay assumes a "
    "hand-up that restarts the conversation",
    "a write the cheap agent made before the hand-up would stay in a real system, which the replay cannot see, so "
    "`calls-over-N-no-write` never hands such a run up while `calls-over-N` and `transfer` do",
    "in telecom the user's own device actions change state too, and no signal counts them",
]
_loaded = []


def replay():
    if not _loaded:
        _loaded.append(load("tau2_cascades_for_results", SCRIPT))
    return _loaded[0]


@pytest.fixture()
def rs():
    return load("routerbench_results_tau2_cascades", ROOT / "evidence" / "routerbench" / "results.py")


def committed():
    return json.loads(FILE.read_text(encoding="utf-8"))


def old():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def r3(value):
    return "-" if value is None else f"{value:.3f}"


def usd(value):
    return f"{value:.4f} USD"


def row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"] if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1, (bar, flavor, strategy)
    return rows[0]


def task_row(results, bar, flavor, task):
    rows = [r for r in results["per_task"] if (r["bar"], r["flavor"], r["task"]) == (bar, flavor, task)]
    assert len(rows) == 1 and rows[0]["strategy"] == "routed", (bar, flavor, task)
    return rows[0]


def one(values):
    values = set(values)
    assert len(values) == 1, values
    return values.pop()


def beats(a, b):
    """12.15's both-counts rule: success at least as high and cost at most as high, one strictly."""
    return (a["success"] >= b["success"] and a["cost_usd"] <= b["cost_usd"]
            and (a["success"] > b["success"] or a["cost_usd"] < b["cost_usd"]))


def to_cascade(rows):
    return sum(n for r in rows for model, n in r["routed_models"].items() if ">" in model)


def bars_words(bars):
    if not bars:
        return "at no bar"
    if len(bars) == 1:
        return f"at bar {bars[0]} only"
    return "at bars " + ", ".join(str(b) for b in bars[:-1]) + f" and {bars[-1]}"


def section():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert text.count("\n## Cascades\n") == 1
    return text.split("\n## Cascades\n", 1)[1].split("\n## ", 1)[0]


def table_block(rs, results):
    return "```text\n" + rs.table(results).split("\n\n", 1)[0] + "\n```"


def regenerate_block():
    return "```bash\n" + "\n".join(COMMANDS) + "\n```"


def phrases(results, before):
    """The numbers of the `## Cascades` paragraph and bullets, each in its words, from the file
    and, for the 12.15 rows, from results.json."""
    bars, b0, b1 = BARS, BARS[0], BARS[-1]
    seeds = len(results["config"]["seeds"])
    cells = seeds * len(results["tasks"])
    first = [r for r in results["summary"] if (r["bar"], r["flavor"]) == (b0, "cost_effective")]
    cascades = [r for r in first if ">" in r["strategy"]]
    agents = [r for r in first if r["strategy"].startswith("model:") and ">" not in r["strategy"]]
    items = sum(t["items"] for t in results["tasks"].values())
    out = [f"{len(cascades)} cascades, so the router has {one(len(t['models']) for t in results['tasks'].values())} "
           f"candidates per domain, the {len(agents)} agents and the cascades, and the matrix gains "
           f"{len(cascades) * items:,} rows, one per task and cascade"]
    # (1) cost_effective at each bar, against 12.15
    ce = {bar: (row(results, bar, "cost_effective", "routed"), row(before, bar, "cost_effective", "routed"))
          for bar in bars}
    out.append("; ".join(f"bar {bar} {r3(a['success'])} at {usd(a['cost_usd'])} against {r3(b['success'])} at "
                         f"{usd(b['cost_usd'])}" for bar, (a, b) in ce.items()))
    won = [bar for bar, (a, b) in ce.items() if beats(a, b)]
    low = to_cascade(r for r in results["per_task"] if (r["bar"], r["flavor"]) == (b0, "cost_effective"))
    high = to_cascade(r for r in results["per_task"] if (r["bar"], r["flavor"]) == (b1, "cost_effective"))
    out.append(f"It beats the 12.15 row on both counts {bars_words(won)}. A cascade takes {low} of the {cells} "
               f"(domain, seed) cells at bar {b0} and {high} at bar {b1}")
    # (2) cost_blind
    cb_s = one(r3(row(results, bar, "cost_blind", "routed")["success"]) for bar in bars)
    cb_c = one(usd(row(results, bar, "cost_blind", "routed")["cost_usd"]) for bar in bars)
    old_s = one(r3(row(before, bar, "cost_blind", "routed")["success"]) for bar in bars)
    old_c = one(usd(row(before, bar, "cost_blind", "routed")["cost_usd"]) for bar in bars)
    cb_n = one(to_cascade(r for r in results["per_task"] if (r["bar"], r["flavor"]) == (bar, "cost_blind"))
               for bar in bars)
    out.append(f"`cost_blind` routes at {cb_s} held-out success for {cb_c} at every bar, against 12.15's {old_s} "
               f"at {old_c}, with {cb_n} of the {cells} cells routed to a cascade")
    # (3) per domain at the lowest bar, cost_effective
    for task in results["tasks"]:
        a, b = task_row(results, b0, "cost_effective", task), task_row(before, b0, "cost_effective", task)
        out.append(f"`{task}`: {r3(a['success'])} at {usd(a['cost_usd'])}, `escalation_share` "
                   f"{r3(a['escalation_share'])}, {to_cascade([a])} of the {seeds} seeds routed to a cascade, "
                   f"against {r3(b['success'])} at {usd(b['cost_usd'])}")
    # (4) the best single agent and the cascades that beat it
    best = min(agents, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    out.append(f"The best single agent, `{best['strategy'][6:]}`, holds {r3(best['success'])} at "
               f"{usd(best['cost_usd'])}")
    winners = sorted((r for r in cascades if beats(r, best)), key=lambda r: (-r["success"], r["cost_usd"]))
    assert winners
    out.append(f"{len(winners)} cascades beat it on both counts: " + "; ".join(
        f"`{r['strategy'][6:]}` {r3(r['success'])} at {usd(r['cost_usd'])}, `escalation_share` "
        f"{r3(r['escalation_share'])}" for r in winners))
    cheap = min(winners, key=lambda r: (r["cost_usd"], r["strategy"]))
    out.append(f"the cheapest of them, `{cheap['strategy'][6:]}`, costs {r3(cheap['cost_usd'] / best['cost_usd'])} "
               f"of the agent's")
    # the table's vs_best_model column divides by the 12.7 `table` pick over every `model:` row
    top = min(agents + cascades, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    out.append(f"`vs_best_model` divides each cost by that of the best `model:` row, here the cascade "
               f"`{top['strategy'][6:]}`, not a single agent")
    return out


def single_rows(results):
    """The summary rows that range over the single models (12.3 v1.538), keyed, without the cascade key."""
    found = {}
    for r in results["summary"]:
        if r["strategy"] == "routed" or ">" in r["strategy"]:
            continue
        r = dict(r)
        if "escalation_share" in r:
            assert r.pop("escalation_share") is None, r["strategy"]
        found[r["bar"], r["flavor"], r["strategy"]] = r
    return found


# --- the spec, before the file

def test_design_12_29_specifies_the_cascade_results():
    text = DESIGN.read_text(encoding="utf-8")
    assert text.count("\n### 12.29 tau2-bench cascade results (`evidence/tau2-bench/cascades.json`, v1.541)\n") == 1
    body = text.split("\n### 12.29 ", 1)[1].split("\n## ", 1)[0]
    for words in ["`reduce` keeps `summary`, whose rows end with `escalation_share` (12.3 v1.538), and the routed "
                  "`per_task` rows", "12.15's, bars `0.3 0.4 0.5 0.6 0.7 0.8`, 50 seeds, both flavors",
                  "`evidence/tau2-bench/RESULTS.md` gains `## Cascades`, after `## Sensitivity` and before "
                  "`## Regenerate`", "`tests/test_evidence_tau2_cascade_results.py`",
                  "`pytest.mark.xfail(strict=True, raises=FileNotFoundError)`", "(row ESC3g)"] + COMMANDS[:1]:
        assert words in body, words
    for command in COMMANDS[1:]:
        assert f"`{command}`" in body, command


# --- the committed file

def test_the_file_is_small_reduced_and_holds_the_config_and_the_tasks(rs):
    text = FILE.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 300_000
    results = json.loads(text)
    assert text == json.dumps(rs.reduce(results), indent=2) + "\n"
    assert list(results) == ["config", "tasks", "summary", "per_task"]
    assert results["config"] == CONFIG
    _, prices = replay().load_prices(replay().PRICES)
    ids = sorted(MODELS + [c.id for c in replay().pair_cascades(MODELS, prices)])
    assert len(ids) == 46
    assert results["tasks"] == {task: {"items": n, "models": ids} for task, n in TASKS.items()}


def test_the_rows_have_unique_keys_the_cascade_key_last_and_fifty_seeds():
    results = committed()
    summary = [(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]]
    assert len(summary) == len(set(summary)) == 600
    per_task = [(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]]
    assert len(per_task) == len(set(per_task)) == 36
    assert all(list(r)[-1] == "escalation_share" for r in results["summary"] + results["per_task"])
    assert all(r["strategy"] == "routed" and sum(r["routed_models"].values()) == 50 for r in results["per_task"])


def test_each_model_row_is_the_same_at_every_bar_and_flavor():
    results = committed()
    by = {}
    for r in results["summary"]:
        if r["strategy"].startswith("model:"):
            by.setdefault(r["strategy"], set()).add((r["success"], r["cost_usd"], r["escalation_share"]))
    assert len(by) == 46 and all(len(v) == 1 for v in by.values())


def test_the_single_model_rows_are_those_of_results_json():
    found, before = single_rows(committed()), {}
    for r in old()["summary"]:
        if r["strategy"] != "routed":
            before[r["bar"], r["flavor"], r["strategy"]] = r
    assert len(found) == len(before) == 84
    assert found == before


# --- RESULTS.md

def test_results_md_holds_the_section_in_place_with_the_opening():
    committed()
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert [line[3:] for line in text.splitlines() if line.startswith("## ")] == HEADINGS
    assert OPENING in text.split("\n## ", 1)[0]
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text


def test_the_section_shows_the_first_table_block_and_the_commands(rs):
    results = committed()
    body = section()
    assert f"`{TABLE}`" in body
    assert table_block(rs, results) in body
    assert regenerate_block() in body
    assert "[cascades.json](cascades.json)" in body and "[prices.json](prices.json)" in body


def test_each_number_of_the_section_is_the_file():
    results = committed()
    body = " ".join(section().split())
    for words in phrases(results, old()):
        assert words in body, words


def test_the_section_states_the_limits_and_that_the_baselines_are_unchanged():
    committed()
    body = " ".join(section().split())
    for words in LIMITS + ["The `cheapest`, `best_on_calibration` and `oracle` rows and the 4 single-agent rows "
                           "are those of [results.json](results.json) at every bar and flavor"]:
        assert words in body, words


# --- the pinned files, only when already cached

@pytest.fixture(scope="module")
def pinned_rows(tmp_path_factory):
    convert = replay().convert
    folder = convert.default_cache_dir()
    names = [folder / name for name in convert.FILES]
    names += [folder / "tools" / f"{domain}-tools.py" for domain in replay().signals.TOOL_FILES]
    if not all(path.is_file() for path in names):
        pytest.skip("the 12 pinned tau2-bench run files or the 3 tool files are not in the default cache")
    out = tmp_path_factory.mktemp("tau2-cascade-results") / "rows.jsonl"
    with contextlib.redirect_stdout(io.StringIO()):
        assert replay().main(["--out", str(out)]) == 0
    return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]


def test_pinned_rows_rebuild_the_file_byte_for_byte(rs, pinned_rows):
    text = FILE.read_text(encoding="utf-8")
    result = evaluate(outcomes_from_rows(pinned_rows), bars=BARS, seeds=range(50))
    result.pop("cells")
    assert json.dumps(rs.reduce(result), indent=2) + "\n" == text
