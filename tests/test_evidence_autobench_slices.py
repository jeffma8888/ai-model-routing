"""DESIGN 12.27 v1.523 (row STRAT3f): the AutoBench slice results.

Four files, ``evidence/autobench-2026/slices-*.json``, hold ``model-routing evaluate --slice-by``
on the 12.10 matrix with each question's labels (12.9 v1.518), by difficulty and by skill, at the
default ``min_samples`` 30 and at ``--min-samples 10``, reduced by the RouterBench results script
(12.7, slices v1.521). The evidence RESULTS.md gains a ``## Slices`` section whose every number these
tests build from the four files. The tests that read the files were committed before them under strict
xfail (v1.523); the commit that adds the files (v1.524) removes the marks. One test reads the pinned
AutoBench files when they are in the default cache, rebuilds the four files in process and requires the
committed bytes; CI never downloads them, so there it skips.
"""

import importlib.util
import json
import re
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows, wilson_lower_bound
from test_evidence_autobench_results import CONFIG, LUNA, MODELS, pinned

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "autobench-2026"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
DESIGN = ROOT / "DESIGN.md"
# name after `slices-` -> (the --slice-by field, min_samples)
FILES = {"difficulty": ("difficulty", 30), "skill": ("skill", 30),
         "difficulty-min10": ("difficulty", 10), "skill-min10": ("skill", 10)}
SLICES = {"difficulty": {"1-very-simple": 48, "2-simple": 50, "3-unmarked": 42, "4-difficult": 33,
                         "5-very-difficult": 30},
          "skill": {"coding": 15, "creative_synthesis": 23, "math_reasoning": 43, "planning_agentic": 31,
                    "world_knowledge": 91}}
HEADINGS = ["Results", "Next to the dataset's headline", "Reading it", "Sensitivity", "Slices", "Caveats",
            "Regenerate"]


def path(name):
    return FOLDER / f"slices-{name}.json"


def load(name):
    return json.loads(path(name).read_text(encoding="utf-8"))


@pytest.fixture()
def rs():
    spec = importlib.util.spec_from_file_location("routerbench_results_ab_slices",
                                                  ROOT / "evidence" / "routerbench" / "results.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def r3(value):
    return "-" if value is None else f"{value:.3f}"


def summary_of(results, bar, flavor, strategy):
    rows = [r for r in results["slice_summary"]
            if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1, (bar, flavor, strategy)
    return rows[0]


def section():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert text.count("\n## Slices\n") == 1
    return text.split("\n## Slices\n", 1)[1].split("\n## ", 1)[0]


def regenerate_block():
    lines = ["python evidence/autobench-2026/convert.py --out autobench-labels.jsonl --task-by all --labels"]
    for name, (field, min_samples) in FILES.items():
        extra = "" if min_samples == 30 else f" --min-samples {min_samples}"
        lines.append(f"model-routing evaluate --outcomes autobench-labels.jsonl --bar 0.6 0.7 0.8 0.9 --seeds 50"
                     f" --slice-by {field}{extra} --json > autobench-slices-{name}.json")
        lines.append(f"python evidence/routerbench/results.py --evaluate autobench-slices-{name}.json"
                     f" --out evidence/autobench-2026/slices-{name}.json")
    return "```bash\n" + "\n".join(lines) + "\n```"


def luna_sentence(files, luna):
    beats = []
    for name in FILES:
        for r in files[name]["slice_summary"]:
            if r["strategy"] != "sliced":
                continue
            if (r["success"] >= luna["success"] and r["cost_usd"] <= luna["cost_usd"]
                    and (r["success"] > luna["success"] or r["cost_usd"] < luna["cost_usd"])):
                beats.append(f"`slices-{name}.json` bar {r['bar']} `{r['flavor']}`")
    head = (f"`openai/gpt-5.6-luna` alone (held-out success {luna['success']:.3f} at "
            f"{luna['cost_usd']:.4f} USD)")
    if not beats:
        return f"No sliced row in the four files beats {head} on both counts"
    return f"These sliced rows beat {head} on both counts: " + ", ".join(beats)


def slice_phrases(files, results):
    """The numbers of the `## Slices` paragraphs and bullets, each in its words, from the four files."""
    d, s, d10, s10 = (files[n] for n in ("difficulty", "skill", "difficulty-min10", "skill-min10"))
    ce = "cost_effective"
    pooled = {n: summary_of(files[n], 0.6, ce, "pooled") for n in FILES}
    pd06, ps06 = r3(pooled["difficulty"]["slice_miss_rate"]), r3(pooled["skill"]["slice_miss_rate"])
    pd07 = r3(summary_of(d, 0.7, ce, "pooled")["slice_miss_rate"])
    ps07 = r3(summary_of(s, 0.7, ce, "pooled")["slice_miss_rate"])
    sd, ss = summary_of(d, 0.6, ce, "sliced"), summary_of(s, 0.6, ce, "sliced")
    sd10, ss10 = summary_of(d10, 0.6, ce, "sliced"), summary_of(s10, 0.6, ce, "sliced")
    p = pooled["difficulty"]
    # Only `world_knowledge` clears at 0.6 by skill at 30, and on every seed.
    clears = {r["slice"]: r["cleared_rate"] for r in s["per_slice"]
              if (r["bar"], r["flavor"], r["strategy"]) == (0.6, ce, "sliced")}
    assert clears == {"coding": 0.0, "creative_synthesis": 0.0, "math_reasoning": 0.0,
                      "planning_agentic": 0.0, "world_knowledge": 1.0}
    # Review iter-371 should-fix 1: the most seeds on which a difficulty level clears at 0.6.
    most = max(r["cleared_rate"] for r in d["per_slice"]
               if (r["bar"], r["flavor"], r["strategy"]) == (0.6, ce, "sliced"))
    assert 0 < most < 0.5
    # Review iter-371 should-fix 2: a perfect score on 10 calibration questions clears 0.7, not 0.8.
    assert 0.7 <= wilson_lower_bound(10, 10, 0.95) < 0.8 and d10["config"]["min_samples"] == 10
    # No slice clears at 0.9 in any file.
    for name in FILES:
        for r in files[name]["per_slice"]:
            if r["bar"] == 0.9 and r["strategy"] == "sliced":
                assert r["cleared_rate"] == 0.0, (name, r["slice"])
    fewest = []
    for bar in (0.6, 0.7, 0.8, 0.9):
        n = 1
        while wilson_lower_bound(n, n, 0.95) < bar:
            n += 1
        fewest.append(n)
    assert fewest == [6, 9, 16, 35]
    v = {n: r3(summary_of(files[n], 0.8, ce, "sliced")["bar_violation_rate"]) for n in FILES}
    luna = next(r for r in results["summary"]
                if (r["bar"], r["flavor"], r["strategy"]) == (0.6, ce, LUNA))
    sizes = []
    sizes_all = [k for field in ("difficulty", "skill") for k in files[field]["tasks"]["all"]["slices"].values()]
    for field in ("difficulty", "skill"):
        counts = files[field]["tasks"]["all"]["slices"]
        sizes.append(f"by {field} " + ", ".join(f"{k} `{name}`" for name, k in list(counts.items())[:-1])
                     + f" and {list(counts.values())[-1]} `{list(counts)[-1]}`")
    return [
        f"Questions per slice, of the {results['tasks']['all']['items']}: {sizes[0]}; {sizes[1]}.",
        f"some slice fell below it on {pd06} of them at bar 0.6 by difficulty and {ps06} by skill, "
        f"and on {pd07} and {ps07} at bar 0.7",
        f"at bar 0.6 its `cleared_rate` is {r3(sd['cleared_rate'])} by difficulty and "
        f"{r3(ss['cleared_rate'])} by skill, where only `world_knowledge`, with "
        f"{SLICES['skill']['world_knowledge']} questions, clears, on every seed",
        f"held-out success {r3(sd['success'])} at {sd['cost_usd']:.4f} USD by difficulty and "
        f"{r3(ss['success'])} at {ss['cost_usd']:.4f} USD by skill, against the pooled route's "
        f"{r3(p['success'])} at {p['cost_usd']:.4f} USD",
        f"at bar 0.6 the sliced `cleared_rate` is {r3(sd10['cleared_rate'])} by difficulty and "
        f"{r3(ss10['cleared_rate'])} by skill",
        f"the sliced `cost_effective` route reaches {r3(sd10['success'])} at {sd10['cost_usd']:.4f} USD by "
        f"difficulty and {r3(ss10['success'])} at {ss10['cost_usd']:.4f} USD by skill, with a "
        f"`slice_miss_rate` of {r3(sd10['slice_miss_rate'])} and {r3(ss10['slice_miss_rate'])} against the "
        f"pooled route's {r3(pooled['difficulty-min10']['slice_miss_rate'])} and "
        f"{r3(pooled['skill-min10']['slice_miss_rate'])}",
        f"at bar 0.8 the sliced `cost_effective` `bar_violation_rate` is {v['difficulty-min10']} by "
        f"difficulty and {v['skill-min10']} by skill, against {v['difficulty']} and {v['skill']} at 30",
        f"a perfect score needs at least {fewest[0]}, {fewest[1]}, {fewest[2]} and {fewest[3]} calibration "
        f"questions for a Wilson lower bound of 0.6, 0.7, 0.8 and 0.9",
        "so at `--min-samples 10` a perfect score on 10 calibration questions already clears 0.7, and no slice "
        "clears at 0.9 in any file",
        f"By difficulty each level clears on at most {r3(most)} of the seeds. On a seed where a slice does not "
        "clear, its route is the model with the highest lower bound on that slice's few calibration questions "
        "(DESIGN 5.3), so over all 50 seeds",
        "Read these violation rates as resampling estimates for this matrix, never as a guarantee",
        # Review iter-371 nit 3: the slice sizes, from the files.
        f"A slice's held-out half holds about half of its {min(sizes_all)} to {max(sizes_all)} questions",
        luna_sentence(files, luna),
    ]


# --- the spec ---------------------------------------------------------------------------------

def test_design_12_27_specifies_the_slice_files():
    text = DESIGN.read_text(encoding="utf-8")
    heading = "\n### 12.27 AutoBench slice results (`evidence/autobench-2026/slices-*.json`, v1.523)\n"
    assert text.count(heading) == 1
    body = text.split(heading, 1)[1].split("\n## ", 1)[0]
    assert text.index("\n### 12.26 ") < text.index(heading) < text.index("\n## 13. ")
    for name in FILES:
        assert f"slices-{name}.json`" in body, name
    for words in ("`--slice-by difficulty` or `--slice-by skill`", "at `--min-samples 10`",
                  "gains `## Slices`, after `## Sensitivity` and before `## Caveats`",
                  "`tests/test_evidence_autobench_slices.py`", "- Workflow (v1.525, row STRAT3g): ", "(row STRAT4)",
                  "6, 9, 16 and 35 (`wilson_lower_bound`)"):
        assert words in body, words


# --- the committed files ----------------------------------------------------------------------

@pytest.mark.parametrize("name", list(FILES))
def test_each_slice_file_is_small_reduced_and_pinned(rs, name):
    field, min_samples = FILES[name]
    assert path(name).stat().st_size < 300_000
    text = path(name).read_text(encoding="utf-8")
    results = json.loads(text)
    assert text == json.dumps(rs.reduce(results), indent=2) + "\n"
    assert list(results) == ["config", "tasks", "summary", "per_task", "per_slice", "slice_summary"]
    assert results["config"] == {**CONFIG, "min_samples": min_samples}
    assert results["tasks"] == {"all": {"items": 203, "models": MODELS, "slices": SLICES[field]}}
    plain = json.loads(RESULTS.read_text(encoding="utf-8"))
    assert results["summary"] == plain["summary"] and results["per_task"] == plain["per_task"]
    keys = [(r["bar"], r["flavor"], r["task"], r["slice"], r["strategy"]) for r in results["per_slice"]]
    expected = [(bar, flavor, "all", sl, st) for bar in CONFIG["bars"] for flavor in CONFIG["flavors"]
                for sl in SLICES[field] for st in ("pooled", "sliced")]
    assert keys == expected and len(keys) == 80
    summary_keys = [(r["bar"], r["flavor"], r["strategy"]) for r in results["slice_summary"]]
    assert summary_keys == [(bar, flavor, st) for bar in CONFIG["bars"] for flavor in CONFIG["flavors"]
                            for st in ("pooled", "sliced")]
    for row in results["per_task"] + results["per_slice"]:
        assert sum(row["routed_models"].values()) == 50
        assert set(row["routed_models"]) <= set(MODELS)


# --- the RESULTS.md section -------------------------------------------------------------------

def test_results_md_slices_section_sits_in_place_and_shows_the_tables(rs):
    files = {name: load(name) for name in FILES}
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert re.findall(r"^## (.+)$", text, flags=re.M) == HEADINGS
    opening = text.split("\n## Results\n", 1)[0]
    assert "The file behind every number here but those of `## Slices` is [results.json](results.json)" in opening
    body = section()
    for name in FILES:
        assert f"[slices-{name}.json](slices-{name}.json)" in body, name
    for name in ("difficulty", "skill"):
        third = rs.table(files[name]).split("\n\n")[2]
        command = f"python evidence/routerbench/results.py --table evidence/autobench-2026/slices-{name}.json"
        block = f"From `{command}`, its third table:\n\n```text\n{third}\n```"
        assert body.count(block) == 1, name
    assert body.count(regenerate_block()) == 1
    assert body.index("\nReading it:\n") < body.index(regenerate_block())


def test_results_md_slices_numbers_are_the_files():
    files = {name: load(name) for name in FILES}
    results = json.loads(RESULTS.read_text(encoding="utf-8"))
    body = section()
    for phrase in slice_phrases(files, results):
        assert phrase in body, phrase
    assert "a slice miss is partly sampling noise" in body


# --- the pinned files, only when already cached -----------------------------------------------

@pytest.fixture(scope="module")
def labelled_rows():
    spec = importlib.util.spec_from_file_location("autobench_convert_slices", FOLDER / "convert.py")
    cv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cv)
    matrix, questions, pool, params = pinned(cv)
    rows, report = cv.convert(matrix, questions, pool, params["delta_signal"], params["top_k"],
                              task_by="all", labels=True)
    assert report["models"] == MODELS and report["kept"] == {"all": 203}
    return rows


@pytest.mark.parametrize("name", list(FILES))
def test_real_slice_files_regenerate_byte_identical(rs, labelled_rows, name):
    field, min_samples = FILES[name]
    result = evaluate(outcomes_from_rows(labelled_rows, slice_by=field), bars=CONFIG["bars"],
                      seeds=range(50), min_samples=min_samples)
    result.pop("cells")
    assert json.dumps(rs.reduce(result), indent=2) + "\n" == path(name).read_text(encoding="utf-8")
