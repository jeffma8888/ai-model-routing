"""DESIGN 12.30 v1.553 (row ESC3m): the LiveCodeBench cascade results.

One file, ``evidence/livecodebench/cascades.json``, holds ``model-routing evaluate --flavor
cost_blind`` at the 12.17 bars and seeds on the matrix that ``evidence/livecodebench/cascades.py
--out`` writes (DESIGN 7 v1.551 and v1.552: the 12.16 ``--labels`` matrix of the 713 kept problems
plus one row per problem and cascade for 22 cascades), reduced by the RouterBench results script
(12.7), with no ``--slice-by``: the sliced file is over 300,000 bytes (row ESC3q). The LiveCodeBench
RESULTS.md gains a ``## Cascades`` section whose every number these tests build from the file, or
from ``results.json`` where it says 12.17 and ``slices-difficulty.json`` where it says 12.28. The
tests that read the file were committed before it under strict xfail (v1.553); the commit that adds
it (v1.554) removed the marks. The pinned-file test runs the replay once when the 67 kept files and
the four release files are in the default cache and skips otherwise, as CI never downloads them.
"""

import contextlib
import io
import json
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows
from test_evidence_livecodebench_results import BARS, CONFIG, ITEMS, TASK, load

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "livecodebench"
FILE = FOLDER / "cascades.json"
RESULTS = FOLDER / "results.json"
SLICES = FOLDER / "slices-difficulty.json"
RESULTS_MD = FOLDER / "RESULTS.md"
DESIGN = ROOT / "DESIGN.md"
SCRIPT = FOLDER / "cascades.py"
HEADINGS = ["Source and licence", "Results", "Reading it", "Slices", "Cascades", "Regenerate"]
TABLE = "python evidence/routerbench/results.py --table evidence/livecodebench/cascades.json"
COMMANDS = [
    "python evidence/livecodebench/cascades.py --out livecodebench-cascades.jsonl",
    "model-routing evaluate --outcomes livecodebench-cascades.jsonl --bar 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9"
    " --seeds 50 --flavor cost_blind --json > livecodebench-cascades-evaluate.json",
    "python evidence/routerbench/results.py --evaluate livecodebench-cascades-evaluate.json"
    " --out evidence/livecodebench/cascades.json",
]
OPENING = "The committed numbers but those of `## Slices` and `## Cascades` are in [results.json](results.json)."
SINGLE = ("routed", "oracle", "best_on_calibration", "cheapest")
RULES = [
    "A cascade starts a problem on a cheap model and hands it up to a strong one when a signal fires on the cheap "
    "model's first sample (DESIGN 7)",
    "`public-test-failed` fires when the sample fails one of the problem's public test cases, the check a caller can "
    "run, and `public-test-failed-or-no-test` when it does or its record holds no test at all, so a sample with no "
    "recorded test is counted both ways, kept and handed up, as a bound",
    "A row whose signal does not fire is the cheap model's first sample and its label; a row handed up takes the "
    "strong model's",
    "A sample that fails a public case fails the problem, so a hand-up never turns a right answer wrong",
    "The submissions record no cost, so every cost is 0.0 and this is `cost_blind` evidence only, as above",
    "A row's `escalation_share` counts, over its seeds whose strategy names a cascade, the held-out problems handed up "
    "over those seeds' held-out problems, so for `routed` it is how often the cheap model handed up a problem routed "
    "to a cascade, and `-` means that no seed named one",
]
LIMITS = [
    "a signal measured on a benchmark may not exist in your product",
    "the strong row is the strong model's own first sample, a run that never saw the cheap sample or the failed "
    "case, so the replay assumes a hand-up that starts the problem over",
    "a wrong answer that only a private case finds stays on the cheap model",
    "no cost is recorded, so neither the strong model's run after a hand-up nor the public tests are priced",
]
BASELINES = ("The `cheapest`, `best_on_calibration` and `oracle` rows and the 67 single-model rows are those of "
             "[results.json](results.json) at every bar: the cascades change the `routed` rows and add one `model:` "
             "row each")
_loaded = []


def replay():
    if not _loaded:
        _loaded.append(load("livecodebench_cascades_for_results", SCRIPT))
    return _loaded[0]


def cascade_ids():
    convert = replay().convert
    return [c.id for c in replay().setting_cascades(name.split("/")[0] for name in convert.FILES)]


@pytest.fixture()
def rs():
    return load("routerbench_results_lcb_cascades", ROOT / "evidence" / "routerbench" / "results.py")


def committed():
    return json.loads(FILE.read_text(encoding="utf-8"))


def old():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def sliced():
    return json.loads(SLICES.read_text(encoding="utf-8"))


def r3(value):
    return "-" if value is None else f"{value:.3f}"


def row(results, bar, strategy):
    rows = [r for r in results["summary"] if (r["bar"], r["strategy"]) == (bar, strategy)]
    assert len(rows) == 1, (bar, strategy)
    return rows[0]


def task_row(results, bar):
    rows = [r for r in results["per_task"] if (r["bar"], r["task"]) == (bar, TASK)]
    assert len(rows) == 1 and rows[0]["strategy"] == "routed", bar
    return rows[0]


def sliced_row(bar):
    rows = [r for r in sliced()["slice_summary"] if (r["bar"], r["strategy"]) == (bar, "sliced")]
    assert len(rows) == 1, bar
    return rows[0]


def one(values):
    values = set(values)
    assert len(values) == 1, values
    return values.pop()


def to_cascade(rows):
    return sum(n for r in rows for model, n in r["routed_models"].items() if ">" in model)


def models(results, bar=BARS[0]):
    """{model id: its `model:` summary row at `bar`}, the cascades' ids holding a `>`."""
    return {r["strategy"][6:]: r for r in results["summary"]
            if r["bar"] == bar and r["strategy"].startswith("model:")}


def section():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert text.count("\n## Cascades\n") == 1
    return text.split("\n## Cascades\n", 1)[1].split("\n## ", 1)[0]


def table_block(rs, results):
    return "```text\n" + rs.table(results).split("\n\n", 1)[0] + "\n```"


def regenerate_block():
    return "```bash\n" + "\n".join(COMMANDS) + "\n```"


def phrases(results, before):
    """The numbers of the `## Cascades` paragraph and bullets, each in its words, from the file and, for the 12.17
    and 12.28 rows, from results.json and slices-difficulty.json."""
    seeds = len(results["config"]["seeds"])
    by = models(results)
    cascades = {name: r for name, r in by.items() if ">" in name}
    singles = {name: r for name, r in by.items() if ">" not in name}
    pairs = sorted({name.split("@")[0] for name in cascades})
    signals = list(replay().SIGNALS)
    out = [f"The {len(cascades)} cascades are the {len(pairs)} pairs of one model at two reasoning settings, the "
           f"lower setting the cheap model (DESIGN 7 v1.550), each on the {len(signals)} signals, so the router has "
           f"{len(results['tasks'][TASK]['models'])} candidates, the {len(singles)} models and the cascades, and the "
           f"matrix gains {len(cascades) * ITEMS:,} rows, one per problem and cascade"]
    # (1) routed against 12.17 and 12.28 at every bar
    now = one(r3(row(results, bar, "routed")["success"]) for bar in BARS)
    then = one(r3(row(before, bar, "routed")["success"]) for bar in BARS)
    cut = one(r3(sliced_row(bar)["success"]) for bar in BARS)
    taken = one(to_cascade([task_row(results, bar)]) for bar in BARS)
    share = one(r3(task_row(results, bar)["escalation_share"]) for bar in BARS)
    names = one(tuple(sorted(m for m in task_row(results, bar)["routed_models"] if ">" in m)) for bar in BARS)
    assert len(names) == 1
    top = BARS[-1]
    out.append(f"With cascades the route holds {now} held-out success at every bar, against {then} for 12.17's routed "
               f"row and {cut} for 12.28's `sliced` row, each the same at every bar. A cascade takes {taken} of the "
               f"{seeds} seeds at every bar, each time `{names[0]}`, and the routed `escalation_share` is {share}. At bar "
               f"{top} the route clears on {r3(row(results, top, 'routed')['cleared_rate'])} of the seeds and "
               f"{r3(row(results, top, 'routed')['bar_violation_rate'])} of those fall below it on held-out, against "
               f"{r3(row(before, top, 'routed')['cleared_rate'])} and {r3(row(before, top, 'routed')['bar_violation_rate'])} "
               f"for 12.17's")
    # (2) the best single model and the cascades above it
    best_name, best = min(singles.items(), key=lambda kv: (-kv[1]["success"], kv[0]))
    above = sorted(((n, r) for n, r in cascades.items() if r["success"] > best["success"]),
                   key=lambda kv: (-kv[1]["success"], kv[0]))
    assert above
    words = []
    for name, r in above:
        pair, signal = name.split("@")
        other = cascades[pair + "@" + next(s for s in signals if s != signal)]
        words.append(f"`{name}` {r3(r['success'])}, `escalation_share` {r3(r['escalation_share'])}, against "
                     f"{r3(other['success'])} and {r3(other['escalation_share'])} for its pair on "
                     f"`{next(s for s in signals if s != signal)}`")
    out.append(f"The best single model, `{best_name}`, holds {r3(best['success'])}. {len(above)} of the "
               f"{len(cascades)} cascades {'holds' if len(above) == 1 else 'hold'} more: " + "; ".join(words))
    # the closing sentence holds only while each such cascade is on the bound's upper end and its twin is not above
    # the best model (review iter-399 nit 1)
    assert len(above) == 1 and above[0][0].endswith("@" + signals[1])
    assert cascades[above[0][0].split("@")[0] + "@" + signals[0]]["success"] <= best["success"]
    out.append("So the one cascade that beats the best model does so only when a sample with no recorded test is "
               "handed up too, the bound's upper end")
    # (3) the two signals as the no_test bound, and each cascade against its two models
    gaps = {p: cascades[p + "@" + signals[1]]["success"] - cascades[p + "@" + signals[0]]["success"] for p in pairs}
    assert all(g >= 0 for g in gaps.values())
    wide = max(gaps, key=lambda p: (gaps[p], p))
    up = sum(1 for g in gaps.values() if g > 0)
    over_cheap = sum(1 for n, r in cascades.items() if r["success"] > singles[n.split(">")[0]]["success"])
    over_strong = sum(1 for n, r in cascades.items()
                      if r["success"] > singles[n.split(">")[1].split("@")[0]]["success"])
    out.append(f"On {up} of the {len(pairs)} pairs the `{signals[1]}` row holds a higher held-out success than the "
               f"`{signals[0]}` row, by at most {r3(gaps[wide])} (`{wide}`)")
    out.append(f"{over_cheap} of the {len(cascades)} cascades hold a higher held-out success than their cheap model, "
               f"and {over_strong} a higher one than their strong model")
    return out


def single_rows(results):
    """The summary rows that range over the single models (12.3 v1.538), keyed, without the cascade key."""
    found = {}
    for r in results["summary"]:
        if r["strategy"] == "routed" or ">" in r["strategy"]:
            continue
        r = dict(r)
        assert r.pop("escalation_share") is None, r["strategy"]
        found[r["bar"], r["strategy"]] = r
    return found


# --- the spec, before the file

def test_design_12_30_specifies_the_cascade_results():
    text = DESIGN.read_text(encoding="utf-8")
    assert text.count("\n### 12.30 LiveCodeBench cascade results (`evidence/livecodebench/cascades.json`, v1.553)\n") == 1
    body = text.split("\n### 12.30 ", 1)[1].split("\n## ", 1)[0]
    for words in ["`evidence/routerbench/results.py` (12.7), unchanged", "63,457 rows (713 x 89)",
                  "12.17's, bars `0.1` to `0.9` by tenths, 50 seeds, `--flavor cost_blind`",
                  "reduces to 305,789 bytes, over 300,000", "row ESC3q",
                  "`evidence/livecodebench/RESULTS.md` gains `## Cascades`, after `## Slices` and before `## Regenerate`",
                  "`tests/test_evidence_livecodebench_cascade_results.py`",
                  "`pytest.mark.xfail(strict=True, raises=FileNotFoundError)`",
                  "- Workflow (v1.559, row ESC3i): "] + COMMANDS[:1]:
        assert words in body, words
    for command in COMMANDS[1:]:
        assert f"`{command}`" in body, command
    for limit in LIMITS:
        assert limit in body, limit


def test_the_rules_the_section_states_are_the_replays():
    """The paragraph's signal, hand-up, cost and cascade-set rules, checked on the replay itself (DESIGN 7 v1.548,
    v1.550)."""
    r = replay()
    first, second = r.SIGNALS
    assert [r.escalates(kind, first) for kind in (None, "public", "other", "input_only", "no_test")] == [
        False, True, False, False, False]
    assert [r.escalates(kind, second) for kind in (None, "public", "other", "input_only", "no_test")] == [
        False, True, False, False, True]
    cheap, strong = {"correct": False, "cost_usd": 0.0}, {"correct": True, "cost_usd": 0.0}
    assert r.cascade_cell(cheap, strong, "public", first) == {"correct": True, "cost_usd": 0.0, "escalated": True}
    assert r.cascade_cell(cheap, strong, "other", first) == {"correct": False, "cost_usd": 0.0, "escalated": False}
    with pytest.raises(ValueError):  # a passed sample has no kind, so it is never handed up
        r.cascade_cell({"correct": True, "cost_usd": 0.0}, strong, "public", first)
    ids = cascade_ids()
    assert len(ids) == 22 and len({i.split("@")[0] for i in ids}) == 11
    assert sorted(i.split("@")[1] for i in ids) == sorted(list(r.SIGNALS) * 11)


# --- the committed file

def test_the_file_is_small_reduced_and_holds_the_config_and_the_tasks(rs):
    text = FILE.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 300_000
    results = json.loads(text)
    assert text == json.dumps(rs.reduce(results), indent=2) + "\n"
    assert list(results) == ["config", "tasks", "summary", "per_task"]
    assert results["config"] == CONFIG
    ids = sorted(old()["tasks"][TASK]["models"] + cascade_ids())
    assert len(ids) == 89
    assert results["tasks"] == {TASK: {"items": ITEMS, "models": ids}}


def test_the_rows_have_unique_keys_the_cascade_key_last_and_fifty_seeds():
    results = committed()
    summary = [(r["bar"], r["flavor"], r["strategy"]) for r in results["summary"]]
    assert len(summary) == len(set(summary)) == 837
    per_task = [(r["bar"], r["flavor"], r["task"]) for r in results["per_task"]]
    assert len(per_task) == len(set(per_task)) == 9
    assert all(list(r)[-1] == "escalation_share" for r in results["summary"] + results["per_task"])
    assert all(r["strategy"] == "routed" and sum(r["routed_models"].values()) == 50 for r in results["per_task"])


def test_each_model_row_is_the_same_at_every_bar():
    results = committed()
    by = {}
    for r in results["summary"]:
        if r["strategy"].startswith("model:"):
            by.setdefault(r["strategy"], set()).add((r["success"], r["cost_usd"], r["escalation_share"]))
    assert len(by) == 89 and all(len(v) == 1 for v in by.values())


def test_the_single_model_rows_are_those_of_results_json():
    found, before = single_rows(committed()), {}
    for r in old()["summary"]:
        if r["strategy"] != "routed":
            before[r["bar"], r["strategy"]] = r
    assert len(found) == len(before) == 9 * 70
    assert found == before


def test_a_routed_escalation_share_is_none_exactly_when_no_seed_routes_to_a_cascade():
    for r in committed()["per_task"]:
        assert (r["escalation_share"] is None) == (to_cascade([r]) == 0), r["bar"]


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
    assert "[cascades.json](cascades.json)" in body


def test_each_number_of_the_section_is_the_file():
    results = committed()
    body = " ".join(section().split())
    for words in phrases(results, old()):
        assert words in body, words


def test_the_section_states_the_rules_the_limits_and_that_the_baselines_are_unchanged():
    committed()
    body = " ".join(section().split())
    for words in RULES + LIMITS + [BASELINES]:
        assert words in body, words


# --- the pinned files, only when already cached

def _cached():
    convert = replay().convert
    root = convert.default_cache_dir()
    return (all((root / "release" / name).is_file() for name in replay().RELEASE)
            and all((root / name).is_file() for name in convert.FILES))


@pytest.fixture(scope="module")
def pinned_rows(tmp_path_factory):
    if not _cached():
        pytest.skip("the 67 kept LiveCodeBench files or the four release files are not in the default cache")
    out = tmp_path_factory.mktemp("lcb-cascade-results") / "rows.jsonl"
    with contextlib.redirect_stdout(io.StringIO()):
        assert replay().main(["--out", str(out)]) == 0
    return [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]


def test_pinned_rows_rebuild_the_file_byte_for_byte(rs, pinned_rows):
    text = FILE.read_text(encoding="utf-8")
    result = evaluate(outcomes_from_rows(pinned_rows), bars=BARS, seeds=range(50), flavors=("cost_blind",))
    result.pop("cells")
    assert json.dumps(rs.reduce(result), indent=2) + "\n" == text
