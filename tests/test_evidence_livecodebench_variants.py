"""DESIGN 12.32 v1.575 (row VAR1b): the LiveCodeBench variant results.

``evidence/livecodebench-variants/variants.py`` takes the 12.16 matrix and keeps the runs of each
model the submissions hold at two or more reasoning settings, each renamed to a route of its model,
``vendor/model@variant`` (4.1 v1.572), the run with no setting as the base route. One file,
``evidence/livecodebench-variants/results.json``, holds 12.17's ``cost_blind`` run on those 13
routes, reduced by the RouterBench results script (12.7). Its RESULTS.md, the README paragraph on
variants and the two measured-setup lines of research/production-lessons.md quote it; these tests
build every number they give from the file. The tests were committed before the script and the
file, and failed there. The pinned-file test runs the converter and the script once when the 67
kept files are in the default cache and skips otherwise, as CI never downloads them.
"""

import contextlib
import copy
import io
import json
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows
from test_evidence_livecodebench_results import BARS, CONFIG, ITEMS, TASK, load

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "livecodebench-variants"
SCRIPT = FOLDER / "variants.py"
FILE = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
BASE_RESULTS = ROOT / "evidence" / "livecodebench" / "results.json"
README = ROOT / "README.md"
NOTE = ROOT / "research" / "production-lessons.md"
DESIGN = ROOT / "DESIGN.md"
HEADINGS = ["Source and licence", "Results", "Reading it", "Limits", "Regenerate"]
TABLE = "python evidence/routerbench/results.py --table evidence/livecodebench-variants/results.json"
COMMANDS = [
    "python evidence/livecodebench/convert.py --out livecodebench-matrix.jsonl",
    "python evidence/livecodebench-variants/variants.py --matrix livecodebench-matrix.jsonl"
    " --out livecodebench-variants.jsonl",
    "model-routing evaluate --outcomes livecodebench-variants.jsonl --bar 0.1 0.2 0.3 0.4 0.5 0.6 0.7 0.8 0.9"
    " --seeds 50 --flavor cost_blind --json > livecodebench-variants-evaluate.json",
    "python evidence/routerbench/results.py --evaluate livecodebench-variants-evaluate.json"
    " --out evidence/livecodebench-variants/results.json",
]
ROUTES = {
    "anthropic/claude-opus-4": "anthropic/claude-opus-4",
    "anthropic/claude-opus-4-thinking": "anthropic/claude-opus-4@thinking",
    "anthropic/claude-sonnet-4": "anthropic/claude-sonnet-4",
    "anthropic/claude-sonnet-4-thinking": "anthropic/claude-sonnet-4@thinking",
    "openai/o1-2024-12-17-high": "openai/o1-2024-12-17@high",
    "openai/o1-2024-12-17-low": "openai/o1-2024-12-17@low",
    "openai/o1-2024-12-17-med": "openai/o1-2024-12-17@medium",
    "openai/o3-mini-2025-01-31-high": "openai/o3-mini-2025-01-31@high",
    "openai/o3-mini-2025-01-31-low": "openai/o3-mini-2025-01-31@low",
    "openai/o3-mini-2025-01-31-med": "openai/o3-mini-2025-01-31@medium",
    "openai/o4-mini-high": "openai/o4-mini@high",
    "openai/o4-mini-low": "openai/o4-mini@low",
    "openai/o4-mini-medium": "openai/o4-mini@medium",
}
# a setting's place on its scale, as DESIGN 7 v1.550 orders them: none < low < medium < high, none < thinking
RANK = {None: 0, "low": 1, "medium": 2, "high": 3, "thinking": 1}
OPENING = [
    "What `model-routing evaluate` measures when the LiveCodeBench runs of one model at two or more reasoning "
    "settings are routed as variants of that model, `vendor/model@variant` (`DESIGN.md` 4.1), each a route with "
    "its own stats",
    "This is `cost_blind` evidence only, as in [the LiveCodeBench results](../livecodebench/RESULTS.md): the "
    "submissions record no cost, no token counts and no list price, so every `cost_usd` is 0.0",
    "The committed numbers are in [results.json](results.json)",
]
SOURCE = [
    "Repo: https://github.com/LiveCodeBench/submissions (archived), pinned revision "
    "[`6ca212e9c2039373f6e5069d37ffa9db66e23736`](https://github.com/LiveCodeBench/submissions/tree/"
    "6ca212e9c2039373f6e5069d37ffa9db66e23736)",
    "Licence: MIT, as the repo's LICENSE file states, with the line \"Copyright (c) 2025 LiveCodeBench\"",
]
LIMITS = [
    "- No cost or token count is recorded, so this file makes no cost claim and cannot show a lower setting as the "
    "cheaper route.",
    "- Each setting is one run, under its submission folder's label, so a gap between two settings is one run's, "
    "not a mean over reruns.",
    "- The routes are 13 of the 67 runs of the LiveCodeBench results, so the `routed`, `oracle`, "
    "`best_on_calibration` and `cheapest` rows are not those of their results.json; each `model:` row is, under "
    "its route ID.",
]
_loaded = []


def script():
    if not _loaded:
        _loaded.append(load("livecodebench_variants_for_tests", SCRIPT))
    return _loaded[0]


@pytest.fixture()
def rs():
    return load("routerbench_results_lcb_variants", ROOT / "evidence" / "routerbench" / "results.py")


def committed():
    return json.loads(FILE.read_text(encoding="utf-8"))


def r3(value):
    return f"{value:.3f}"


def split(route):
    model, _, variant = route.partition("@")
    return model, (variant or None)


def label(route):
    variant = split(route)[1]
    return "base" if variant is None else f"`@{variant}`"


def held_out(data):
    """Each route's held-out success, checked to be the same at every bar."""
    seen = {}
    for row in data["summary"]:
        if row["strategy"].startswith("model:"):
            seen.setdefault(row["strategy"][len("model:"):], set()).add(row["success"])
    assert all(len(values) == 1 for values in seen.values())
    return {route: values.pop() for route, values in sorted(seen.items())}


def by_model(data):
    """Each model's routes, lowest held-out success first, then route ID."""
    success = held_out(data)
    models = {}
    for route in success:
        models.setdefault(split(route)[0], []).append(route)
    return {m: sorted(rs_, key=lambda r: (success[r], r)) for m, rs_ in sorted(models.items())}, success


def facts(data):
    models, success = by_model(data)
    gaps = {m: success[r[-1]] - success[r[0]] for m, r in models.items()}
    widest = max(sorted(gaps), key=lambda m: gaps[m])
    top = {m: max(r, key=lambda x: (RANK[split(x)[1]], x)) for m, r in models.items()}
    not_top = [m for m in models if models[m][-1] != top[m]]
    return models, success, gaps, widest, top, not_top


def routed_rows(data):
    return [r for r in data["per_task"] if r["strategy"] == "routed"]


def reading(data, base):
    """The `## Reading it` bullets, every number from the file and, for (3), results.json."""
    models, success, gaps, widest, top, not_top = facts(data)
    parts = []
    for m, routes_ in models.items():
        listed = ", ".join(f"{label(r)} {r3(success[r])}" for r in routes_)
        parts.append(f"`{m}` {listed}, a gap of {r3(gaps[m])}")
    one = ("- Each model's routes, from the lowest held-out success to the highest, the same at every bar: "
           + "; ".join(parts) + f". The widest gap is `{widest}`'s.")
    if not_top:
        two = "- The highest setting is not the best route of " + "; ".join(
            f"`{m}`: {label(models[m][-1])} {r3(success[models[m][-1]])} against {label(top[m])} "
            f"{r3(success[top[m]])}" for m in not_top) + "."
    else:
        two = "- Every model's highest setting is its best route."
    rows = routed_rows(data)
    assert len({r["success"] for r in rows}) == 1
    chosen = {m for r in rows for m in r["routed_models"]}
    assert all(sum(r["routed_models"].values()) == 50 for r in rows)
    base_rows = [r for r in base["per_task"] if r["strategy"] == "routed"]
    assert len({r["success"] for r in base_rows}) == 1
    at_top = [r for r in data["summary"] if r["strategy"] == "routed" and r["bar"] == BARS[-1]][0]
    base_top = [r for r in base["summary"] if r["strategy"] == "routed" and r["bar"] == BARS[-1]][0]
    names = " and ".join(f"`{m}`" for m in sorted(chosen))
    three = (f"- Routed, held-out success is {r3(rows[0]['success'])} at every bar, with all 50 seeds routed to "
             f"{names} wherever a route cleared, against {r3(base_rows[0]['success'])} for the routed row of the "
             f"67 runs in [results.json](../livecodebench/results.json); at bar 0.9 the `cleared_rate` is "
             f"{r3(at_top['cleared_rate'])} here and {r3(base_top['cleared_rate'])} there.")
    parts = []
    for m, routes_ in models.items():
        mean = sum(success[r] for r in routes_) / len(routes_)
        parts.append(f"`{m}` {r3(mean)}, {r3(mean - success[routes_[0]])} over its lowest route and "
                     f"{r3(success[routes_[-1]] - mean)} under its highest")
    four = ("- One success rate keyed by the model's name, with its calls spread evenly over its settings, would "
            "read the mean of its routes: " + "; ".join(parts) + ".")
    return [one, two, three, four]


def section(text, heading):
    body = text.split(f"\n## {heading}\n", 1)[1]
    return body.split("\n## ", 1)[0]


def readme_sentence(data):
    models, success, gaps, widest, top, not_top = facts(data)
    best = "; ".join(f"`{m}` does best at {label(models[m][-1])}, not {label(top[m])}" for m in not_top)
    return (f"On public data, [LiveCodeBench's runs](evidence/livecodebench-variants/RESULTS.md) of "
            f"{len(models)} models at two or three reasoning settings, routed as {len(success)} variants, put one "
            f"model's settings up to {r3(gaps[widest])} apart in held-out success (`{widest}`), and {best}; no "
            f"cost is recorded there.")


def note_sentences(data):
    models, success, gaps, widest, top, not_top = facts(data)
    link = "([LiveCodeBench variant results](../evidence/livecodebench-variants/RESULTS.md))"
    harvey = (f"On LiveCodeBench's public runs of {len(models)} models at two or three reasoning settings, "
              f"routed as {len(success)} variants, one model's settings are up to {r3(gaps[widest])} apart in "
              f"held-out success, and the highest setting is not always the best route {link}; those runs record "
              f"no cost.")
    effort = []
    for m in ("openai/o4-mini", "openai/o3-mini-2025-01-31"):
        by_setting = {split(r)[1]: success[r] for r in models[m]}
        effort.append(f"`{m}` {', '.join(r3(by_setting[v]) for v in ('low', 'medium'))} and "
                      f"{r3(by_setting['high'])}")
    uber = (f"On LiveCodeBench's public runs, {effort[0]} of held-out problems at low, medium and high effort, "
            f"and {effort[1]}, with no cost recorded {link}.")
    return harvey, uber


# --- the script --------------------------------------------------------------------------------

def test_routes_maps_each_run_of_a_model_at_two_settings_to_a_route_of_that_model():
    got = script().routes(["O4-Mini (Low)", "O4-Mini (High)", "O3 (High)", "Claude-Opus-4",
                           "Claude-Opus-4 (Thinking)", "GPT-4O-2024-08-06"])
    assert got == {"openai/o4-mini-low": "openai/o4-mini@low", "openai/o4-mini-high": "openai/o4-mini@high",
                   "anthropic/claude-opus-4": "anthropic/claude-opus-4",
                   "anthropic/claude-opus-4-thinking": "anthropic/claude-opus-4@thinking"}


def test_med_and_medium_are_one_variant_and_a_base_with_one_run_is_left_out():
    got = script().routes(["O1-2024-12-17 (Med)", "O1-2024-12-17 (Low)", "O4-Mini (Medium)", "O4-Mini (Low)",
                           "Claude-Sonnet-4"])
    assert got == {"openai/o1-2024-12-17-med": "openai/o1-2024-12-17@medium",
                   "openai/o1-2024-12-17-low": "openai/o1-2024-12-17@low",
                   "openai/o4-mini-medium": "openai/o4-mini@medium", "openai/o4-mini-low": "openai/o4-mini@low"}


@pytest.mark.parametrize("folders, message", [
    (["O4-Mini (Low)", "O4-Mini (Low)", "O4-Mini (High)"], "folder 'O4-Mini (Low)' is repeated"),
    (["O4-Mini (Med)", "O4-Mini (Medium)"], "O4-Mini: 'O4-Mini (Med)' and 'O4-Mini (Medium)' are both medium"),
])
def test_routes_refuses_a_repeated_folder_and_two_runs_at_one_variant(folders, message):
    with pytest.raises(ValueError) as caught:
        script().routes(folders)
    assert str(caught.value) == message


def test_routes_on_the_kept_files_gives_the_13_routes_of_5_models():
    convert = script().convert
    got = script().routes(name.split("/")[0] for name in convert.FILES)
    assert got == ROUTES
    assert len({split(r)[0] for r in got.values()}) == 5


def test_variant_rows_keeps_the_runs_of_the_routes_in_order_as_new_dicts():
    rows = [{"task": "t", "item": "1", "model": "openai/o4-mini-low", "correct": True, "cost_usd": 0.0},
            {"task": "t", "item": "1", "model": "openai/gpt-4o-2024-08-06", "correct": True, "cost_usd": 0.0},
            {"task": "t", "item": "2", "model": "openai/o4-mini-high", "correct": False, "cost_usd": 0.0,
             "difficulty": "1-easy"}]
    before = copy.deepcopy(rows)
    got = script().variant_rows(rows, ROUTES)
    assert got == [dict(rows[0], model="openai/o4-mini@low"), dict(rows[2], model="openai/o4-mini@high")]
    assert [list(r) for r in got] == [list(rows[0]), list(rows[2])]
    assert rows == before and all(g is not r for g in got for r in rows)


def test_main_writes_the_variant_rows_and_prints_the_count(tmp_path, capsys):
    matrix = tmp_path / "m.jsonl"
    rows = [{"task": "t", "item": "1", "model": m, "correct": True, "cost_usd": 0.0} for m in
            ("openai/o4-mini-low", "openai/o3-high", "anthropic/claude-opus-4")]
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    out = tmp_path / "v.jsonl"
    assert script().main(["--matrix", str(matrix), "--out", str(out)]) == 0
    assert capsys.readouterr().out == "2 rows, 13 routes of 5 models\n"
    assert [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()] == [
        dict(rows[0], model="openai/o4-mini@low"), rows[2]]


@pytest.mark.parametrize("text, message", [
    (None, "No such file"),
    ('{"model": "openai/o4-mini-low"}\n[1]\n', "line 2 is not a JSON object"),
    ('{"model": "openai/o4-mini-low"}\nnot json\n', "line 2 is not JSON"),
    ('{"model": "openai/o3-high"}\n', "holds no run of the 13 routes"),
])
def test_main_refuses_a_bad_matrix_and_writes_nothing(tmp_path, capsys, text, message):
    matrix = tmp_path / "m.jsonl"
    if text is not None:
        matrix.write_text(text, encoding="utf-8")
    out = tmp_path / "v.jsonl"
    assert script().main(["--matrix", str(matrix), "--out", str(out)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and captured.err.startswith("error: ") and message in captured.err
    assert not out.exists()


# --- the committed file ------------------------------------------------------------------------

def test_the_file_is_the_reduced_run_on_the_13_routes(rs):
    text = FILE.read_text(encoding="utf-8")
    assert len(text.encode("utf-8")) < 300_000
    data = json.loads(text)
    assert json.dumps(rs.reduce(data), indent=2) + "\n" == text
    assert data["config"] == CONFIG
    assert data["tasks"] == {TASK: {"items": ITEMS, "models": sorted(ROUTES.values())}}
    assert all(r["cost_usd"] == 0.0 for r in data["summary"] + data["per_task"])
    assert len(data["per_task"]) == len(BARS)
    assert all(sum(r["routed_models"].values()) == 50 for r in data["per_task"])


def test_each_route_row_is_the_row_of_the_run_it_renames():
    data, base = committed(), json.loads(BASE_RESULTS.read_text(encoding="utf-8"))
    rows = {(r["bar"], r["flavor"], r["strategy"]): r for r in base["summary"]}
    checked = 0
    for row in data["summary"]:
        if row["strategy"].startswith("model:"):
            run = {v: k for k, v in ROUTES.items()}[row["strategy"][len("model:"):]]
            assert dict(row, strategy="model:" + run) == rows[(row["bar"], row["flavor"], "model:" + run)]
            checked += 1
    assert checked == 13 * len(BARS)


# --- RESULTS.md --------------------------------------------------------------------------------

def test_the_results_md_holds_its_sections_in_order():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert text.startswith("# LiveCodeBench variant results\n\n")
    assert [line[3:] for line in text.splitlines() if line.startswith("## ")] == HEADINGS
    opening = " ".join(text.split("\n## ", 1)[0].split())
    for words in OPENING:
        assert words in opening, words
    source = " ".join(section(text, "Source and licence").split())
    for words in SOURCE:
        assert words in source, words


def test_the_results_section_is_the_table_as_table_prints_it(rs):
    body = section(RESULTS_MD.read_text(encoding="utf-8"), "Results")
    assert f"```text\n$ {TABLE}\n{rs.table(committed())}```\n" in body


def test_the_reading_bullets_are_built_from_the_file():
    body = section(RESULTS_MD.read_text(encoding="utf-8"), "Reading it")
    bullets = [line for line in body.splitlines() if line.startswith("- ")]
    assert bullets == reading(committed(), json.loads(BASE_RESULTS.read_text(encoding="utf-8")))


def test_the_limits_and_the_regenerate_block():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert [line for line in section(text, "Limits").splitlines() if line.startswith("- ")] == LIMITS
    block = "```bash\npython -m pip install -e .\n" + "\n".join(COMMANDS) + "\n" + TABLE + "\n```\n"
    assert block in section(text, "Regenerate")


def test_the_readme_and_the_note_quote_the_file():
    data = committed()
    readme = README.read_text(encoding="utf-8")
    assert "(LiveCodeBench variants: evidence/livecodebench-variants/RESULTS.md)" in readme
    paragraph = [line for line in readme.splitlines() if line.startswith("One model run two ways can be two routes.")]
    assert len(paragraph) == 1 and paragraph[0].endswith(" " + readme_sentence(data))
    note = NOTE.read_text(encoding="utf-8").splitlines()
    harvey, uber = note_sentences(data)
    lines = [line for line in note if line.startswith("- In this library: a registry row can name variants")]
    assert len(lines) == 1 and lines[0].endswith(" " + harvey)
    lines = [line for line in note if line.startswith("- In this library: as in the Harvey lesson on measured setups")]
    assert len(lines) == 1 and lines[0].endswith(" " + uber)


def test_design_12_32_names_the_script_the_file_and_the_row():
    text = DESIGN.read_text(encoding="utf-8")
    assert ("### 12.32 LiveCodeBench variant results (`evidence/livecodebench-variants/results.json`, v1.575)\n"
            in text)
    body = text.split("### 12.32 ", 1)[1].split("\n## ", 1)[0]
    assert "(row VAR1b)" in body and "`evidence/livecodebench-variants/variants.py`" in body
    for command in COMMANDS:
        assert f"`{command}`" in body, command


# --- the pinned files, only when already cached ------------------------------------------------

def _cached():
    convert = script().convert
    root = convert.default_cache_dir()
    return all((root / name).is_file() for name in convert.FILES)


def test_pinned_files_rebuild_the_file_byte_for_byte(rs, tmp_path):
    if not _cached():
        pytest.skip("the 67 kept LiveCodeBench files are not in the default cache")
    matrix, out = tmp_path / "m.jsonl", tmp_path / "v.jsonl"
    with contextlib.redirect_stdout(io.StringIO()):
        assert script().convert.main(["--out", str(matrix)]) == 0
        assert script().main(["--matrix", str(matrix), "--out", str(out)]) == 0
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 13 * ITEMS
    result = evaluate(outcomes_from_rows(rows), bars=BARS, seeds=range(50), flavors=("cost_blind",))
    result.pop("cells")
    assert json.dumps(rs.reduce(result), indent=2) + "\n" == FILE.read_text(encoding="utf-8")
