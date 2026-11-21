"""DESIGN 12.28 v1.528 (row STRAT3h): the LiveCodeBench slice results.

One file, ``evidence/livecodebench/slices-difficulty.json``, holds ``model-routing evaluate
--slice-by difficulty --flavor cost_blind`` on the 12.17 matrix with each problem's difficulty
(12.16 v1.526), reduced by the RouterBench results script (12.7, slices v1.521). The evidence
RESULTS.md gains a ``## Slices`` section whose every number these tests build from the file or,
where a bullet says so, from the pinned files. The tests that read the file were committed before
it under strict xfail (v1.528); the commit that adds it (v1.529) removes the marks. The pinned-file
tests read the 67 files once per module when they are in the default cache and skip otherwise, as
CI never downloads them.
"""

import json
import re
from collections import Counter
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows, split_items, wilson_lower_bound
from test_evidence_livecodebench_results import BARS, CONFIG, ITEMS, TASK, load, model_ids

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "livecodebench"
FILE = FOLDER / "slices-difficulty.json"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
DESIGN = ROOT / "DESIGN.md"
SLICES = {"1-easy": 238, "2-medium": 279, "3-hard": 196}
HEADINGS = ["Source and licence", "Results", "Reading it", "Slices", "Cascades", "Regenerate"]  # Cascades v1.554
TABLE = "python evidence/routerbench/results.py --table evidence/livecodebench/slices-difficulty.json"
COMMANDS = [
    "python evidence/livecodebench/convert.py --out livecodebench-labels.jsonl --labels",
    "model-routing evaluate --outcomes livecodebench-labels.jsonl --bar 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9"
    " --seeds 50 --flavor cost_blind --slice-by difficulty --json > livecodebench-slices-difficulty.json",
    "python evidence/routerbench/results.py --evaluate livecodebench-slices-difficulty.json"
    " --out evidence/livecodebench/slices-difficulty.json",
]
OPENING = "The committed numbers but those of `## Slices` and `## Cascades` are in [results.json](results.json)."  # v1.554


@pytest.fixture()
def rs():
    return load("routerbench_results_lcb_slices", ROOT / "evidence" / "routerbench" / "results.py")


@pytest.fixture(scope="module")
def cv():
    return load("livecodebench_convert_for_slices", FOLDER / "convert.py")


def committed():
    return json.loads(FILE.read_text(encoding="utf-8"))


def r3(value):
    return "-" if value is None else f"{value:.3f}"


def summary_of(results, bar, strategy):
    rows = [r for r in results["slice_summary"] if (r["bar"], r["strategy"]) == (bar, strategy)]
    assert len(rows) == 1, (bar, strategy)
    return rows[0]


def slice_of(results, bar, name, strategy):
    rows = [r for r in results["per_slice"] if (r["bar"], r["slice"], r["strategy"]) == (bar, name, strategy)]
    assert len(rows) == 1, (bar, name, strategy)
    return rows[0]


def one(values):
    values = set(values)
    assert len(values) == 1, values
    return values.pop()


def section():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert text.count("\n## Slices\n") == 1
    return text.split("\n## Slices\n", 1)[1].split("\n## ", 1)[0]


def regenerate_block():
    return "```bash\n" + "\n".join(COMMANDS) + "\n```"


def file_phrases(results):
    """The numbers of the `## Slices` paragraphs and bullets that the file gives, each in its words."""
    sliced = one(r3(summary_of(results, bar, "sliced")["success"]) for bar in BARS)
    pooled = one(r3(summary_of(results, bar, "pooled")["success"]) for bar in BARS)
    per = {name: one(r3(slice_of(results, bar, name, "pooled")["success"]) for bar in BARS) for name in SLICES}
    for bar in (0.7, 0.8):
        below = [name for name in SLICES if slice_of(results, bar, name, "pooled")["below_bar_rate"] > 0]
        assert below == ["3-hard"], bar
    assert all(slice_of(results, bar, "1-easy", "sliced")["cleared_rate"] == 1.0 for bar in BARS)
    hard = {bar: slice_of(results, bar, "3-hard", "sliced")["cleared_rate"] for bar in (0.7, 0.8, 0.9)}
    assert hard[0.7] > 0 and hard[0.8] == hard[0.9] == 0.0
    for name in ("1-easy", "2-medium"):
        assert slice_of(results, 0.9, name, "sliced")["bar_violation_rate"] == 0.0, name
    cleared = [r3(summary_of(results, bar, "sliced")["cleared_rate"]) for bar in (0.7, 0.8, 0.9)]
    sizes = list(results["tasks"][TASK]["slices"].items())
    return [
        f"Problems per slice, of the {results['tasks'][TASK]['items']}: "
        + ", ".join(f"{k} `{name}`" for name, k in sizes[:-1]) + f" and {sizes[-1][1]} `{sizes[-1][0]}`.",
        f"the sliced route's held-out success is {sliced} at every bar, against the pooled route's {pooled}",
        f"The pooled route's held-out success is {per['1-easy']} on `1-easy`, {per['2-medium']} on `2-medium` "
        f"and {per['3-hard']} on `3-hard`, at every bar, so the task's {pooled} hides a slice far below it",
        f"some slice fell below it on {r3(summary_of(results, 0.7, 'pooled')['slice_miss_rate'])} of them at "
        f"bar 0.7 and on {r3(summary_of(results, 0.8, 'pooled')['slice_miss_rate'])} at bar 0.8, and `3-hard` "
        "is the only slice whose `below_bar_rate` is above 0 there",
        f"`1-easy` clears on every seed at every bar, while `3-hard` clears on {r3(hard[0.7])} of the seeds at "
        f"bar 0.7 and on none at 0.8 or 0.9, so the sliced `cleared_rate` is {cleared[0]}, {cleared[1]} and "
        f"{cleared[2]} at bars 0.7, 0.8 and 0.9",
        f"At bar 0.9 `2-medium` clears on {r3(slice_of(results, 0.9, '2-medium', 'sliced')['cleared_rate'])} of "
        f"the seeds, where the pooled route clears on {r3(summary_of(results, 0.9, 'pooled')['cleared_rate'])} "
        "of them, and no cleared `1-easy` or `2-medium` seed falls below the bar on held-out",
        f"at bar 0.7 the sliced `3-hard` route's `bar_violation_rate` is "
        f"{r3(slice_of(results, 0.7, '3-hard', 'sliced')['bar_violation_rate'])}, against the pooled route's "
        f"{r3(slice_of(results, 0.7, '3-hard', 'pooled')['bar_violation_rate'])} there",
    ]


def pinned_phrases(rows):
    """The numbers of the bullets that the pinned files give, each in its words."""
    by_slice, overall, level = {}, Counter(), {}
    for r in rows:
        level[r["item"]] = r["difficulty"]
        by_slice.setdefault(r["difficulty"], Counter())[r["model"]] += bool(r["correct"])
        overall[r["model"]] += bool(r["correct"])
    best = {name: max(by_slice[name].values()) for name in SLICES}
    top = max(overall.values())
    (leader,) = [m for m, k in overall.items() if k == top]
    (hard_leader,) = [m for m, k in by_slice["3-hard"].items() if k == best["3-hard"]]
    items = sorted(level)
    halves = {name: [] for name in SLICES}
    for seed in range(50):
        cal = split_items(items, seed)[0]
        counts = Counter(level[i] for i in cal)
        for name in SLICES:
            halves[name].append(counts[name])
    low, high = min(min(v) for v in halves.values()), max(max(v) for v in halves.values())
    assert low >= CONFIG["min_samples"]
    return [
        f"In sample, on all {len(items)} problems, the best model on each level solves {best['1-easy']} of "
        f"{SLICES['1-easy']} `1-easy`, {best['2-medium']} of {SLICES['2-medium']} `2-medium` and "
        f"{best['3-hard']} of {SLICES['3-hard']} `3-hard` problems, {sum(best.values())} in all, against {top} "
        f"for the best single model, `{leader}`, so even a perfect pick per level gains at most "
        f"{sum(best.values()) - top} of the {len(items)} problems",
        f"the best model on `3-hard`, `{hard_leader}`, solves {best['3-hard'] / SLICES['3-hard']:.3f} of its "
        f"{SLICES['3-hard']} problems",
        f"Each slice's calibration half holds {low} to {high} problems over the 50 seeds (`3-hard` "
        f"{min(halves['3-hard'])} to {max(halves['3-hard'])}), never under `min_samples` {CONFIG['min_samples']}",
    ]


# --- the spec ---------------------------------------------------------------------------------

def test_design_12_28_specifies_the_slice_file():
    text = DESIGN.read_text(encoding="utf-8")
    heading = ("\n### 12.28 LiveCodeBench slice results (`evidence/livecodebench/slices-difficulty.json`, "
               "v1.528)\n")
    assert text.count(heading) == 1
    body = text.split(heading, 1)[1].split("\n## ", 1)[0]
    assert text.index("\n### 12.27 ") < text.index(heading) < text.index("\n## 13. ")
    for words in ("`--slice-by difficulty`", "`--flavor cost_blind`", *COMMANDS,
                  "gains `## Slices`, after `## Reading it` and before `## Regenerate`",
                  "`tests/test_evidence_livecodebench_slices.py`", "- Workflow (v1.530, row STRAT3i): ", "(row STRAT4)",
                  "238 (`1-easy`), 279 (`2-medium`) and 196 (`3-hard`)", "77 to 153 items over the 50 seeds",
                  "(in sample, 3 of 713)"):
        assert words in body, words


# --- the committed file -----------------------------------------------------------------------

def test_the_slice_file_is_small_reduced_and_pinned(rs, cv):
    assert FILE.stat().st_size < 300_000
    text = FILE.read_text(encoding="utf-8")
    results = json.loads(text)
    assert text == json.dumps(rs.reduce(results), indent=2) + "\n"
    assert list(results) == ["config", "tasks", "summary", "per_task", "per_slice", "slice_summary"]
    assert results["config"] == CONFIG
    models = model_ids(cv)
    assert len(models) == 67
    assert results["tasks"] == {TASK: {"items": ITEMS, "models": models, "slices": SLICES}}
    plain = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert results["summary"] == plain["summary"] and results["per_task"] == plain["per_task"]
    keys = [(r["bar"], r["flavor"], r["task"], r["slice"], r["strategy"]) for r in results["per_slice"]]
    assert keys == [(bar, "cost_blind", TASK, name, st) for bar in BARS for name in SLICES
                    for st in ("pooled", "sliced")]
    assert len(set(keys)) == 54
    summary_keys = [(r["bar"], r["flavor"], r["strategy"]) for r in results["slice_summary"]]
    assert summary_keys == [(bar, "cost_blind", st) for bar in BARS for st in ("pooled", "sliced")]
    assert len(summary_keys) == 18
    for row in results["per_slice"] + results["slice_summary"]:
        assert row["cost_usd"] == 0
    for row in results["per_task"] + results["per_slice"]:
        assert sum(row["routed_models"].values()) == 50
        assert set(row["routed_models"]) <= set(models)


# --- the RESULTS.md section -------------------------------------------------------------------

def test_results_md_slices_section_sits_in_place_and_shows_the_table(rs):
    results = committed()
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert re.findall(r"^## (.+)$", text, flags=re.M) == HEADINGS
    opening = text.split("\n## Source and licence\n", 1)[0]
    assert opening.count(OPENING) == 1
    body = section()
    assert "[slices-difficulty.json](slices-difficulty.json)" in body
    assert "(README.md#problem-difficulty-for-the-slice-evidence)" in body
    third = rs.table(results).split("\n\n")[2]
    assert body.count(f"From `{TABLE}`, its third table:\n\n```text\n{third}\n```") == 1
    assert body.count(regenerate_block()) == 1
    assert body.index("\nReading it:\n") < body.index(regenerate_block())
    assert text.isascii()


def test_results_md_slices_numbers_are_the_file():
    results = committed()
    body = section()
    for phrase in file_phrases(results):
        assert phrase in body, phrase
    assert "Read these rates as resampling estimates for this pool, never as a guarantee (DESIGN 12.3)" in body


def test_file_phrases_follow_the_file():
    fake = json.loads(json.dumps(committed()))
    for r in fake["slice_summary"]:
        if r["strategy"] == "sliced":
            r["success"] = 0.5
    said = file_phrases(fake)[1]
    assert said.startswith("the sliced route's held-out success is 0.500 at every bar")
    # Review iter-374 should-fix 1: one source value per phrase moves that phrase and no other.
    def every_bar(name, strategy, key):
        def change(results):
            for bar in BARS:
                slice_of(results, bar, name, strategy)[key] = 0.5
        return change
    moves = {
        0: lambda results: results["tasks"][TASK]["slices"].update({"3-hard": 197}),
        2: every_bar("1-easy", "pooled", "success"),
        3: lambda results: summary_of(results, 0.7, "pooled").update({"slice_miss_rate": 0.5}),
        4: lambda results: slice_of(results, 0.7, "3-hard", "sliced").update({"cleared_rate": 0.5}),
        5: lambda results: slice_of(results, 0.9, "2-medium", "sliced").update({"cleared_rate": 0.5}),
        6: lambda results: slice_of(results, 0.7, "3-hard", "pooled").update({"bar_violation_rate": 0.5}),
    }
    base = file_phrases(committed())
    for index, change in moves.items():
        moved = json.loads(json.dumps(committed()))
        change(moved)
        said = file_phrases(moved)
        assert [k for k in range(len(base)) if said[k] != base[k]] == [index], index
        assert "0.500" in said[index] or "197" in said[index], index
    slice_of(fake, 0.8, "3-hard", "sliced")["cleared_rate"] = 0.02
    with pytest.raises(AssertionError):
        file_phrases(fake)


# --- the pinned files, only when already cached -----------------------------------------------

@pytest.fixture(scope="module")
def labelled(cv):
    folder = cv.default_cache_dir()
    if not all((folder / path).is_file() for path in cv.FILES):
        pytest.skip("the 67 pinned LiveCodeBench files are not in the default cache")
    extracts = []
    for path, (size, sha) in cv.FILES.items():
        cv.verify(folder / path, size, sha)
        extracts.append(cv.extract(cv.read_file(folder / path), path.split("/", 1)[0], labels=True))
    rows, report = cv.convert(extracts, labels=True)
    assert report["items"] == ITEMS and report["labels"] == {"difficulty": SLICES}
    return rows


def test_real_slice_file_regenerates_byte_identical(rs, labelled):
    result = evaluate(outcomes_from_rows(labelled, slice_by="difficulty"), bars=BARS, seeds=range(50),
                      flavors=("cost_blind",))
    result.pop("cells")
    assert json.dumps(rs.reduce(result), indent=2) + "\n" == FILE.read_text(encoding="utf-8")


def test_real_pinned_numbers_are_in_the_section(labelled):
    committed()
    body = section()
    for phrase in pinned_phrases(labelled):
        assert phrase in body, phrase


def test_real_hard_slice_best_rate_clears_0_7_on_no_calibration_half(labelled):
    """Bullet (4), v1.529: a rate of at most the best `3-hard` rate has a Wilson lower bound under 0.7 on
    every `3-hard` calibration half of the 50 seeds, so a `3-hard` route clears 0.7 only on a half above
    that rate (review iter-374 should-fix 2: a half of 147 or more would clear it)."""
    committed()
    level = {r["item"]: r["difficulty"] for r in labelled}
    hits = Counter(r["model"] for r in labelled if r["difficulty"] == "3-hard" and r["correct"])
    best = round(max(hits.values()) / SLICES["3-hard"], 3)  # the stated 0.776 (review iter-374 nit 1)
    items = sorted(level)
    sizes = {sum(1 for i in split_items(items, seed)[0] if level[i] == "3-hard") for seed in range(50)}
    for n in sizes:
        k = max(j for j in range(n + 1) if j / n <= best)
        assert wilson_lower_bound(k, n, 0.95) < 0.7, n
    assert best == 0.776 and (min(sizes), max(sizes)) == (77, 117)
    assert ("a rate of at most 0.776 has a 95% Wilson lower bound (DESIGN 5.3) under 0.7 on every `3-hard` "
            "calibration half of the 50 seeds (77 to 117 problems)") in section()
