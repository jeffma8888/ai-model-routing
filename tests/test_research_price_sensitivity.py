"""research/price-sensitivity.md and research/price_sensitivity.py (DESIGN 12.22 v1.403, row R35).

The note's numbers are the script's lines on the LLMRouterBench matrix, compared byte for byte when
the pinned file is cached (the session fixture `llmrouterbench_pinned` of tests/conftest.py, which
CI never fills). On a small matrix the script's picks are checked against `evaluate` run on rows
whose one model's costs are scaled, its lines against values built here, and its exits.
"""

import contextlib
import hashlib
import importlib.util
import io
import json
import math
import re
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "price_sensitivity.py"
NOTE = ROOT / "research" / "price-sensitivity.md"
INDEX = ROOT / "research" / "README.md"
DESIGN = ROOT / "DESIGN.md"
RESULTS = "evidence/llmrouterbench/results.json"
COMMAND = "$ python research/price_sensitivity.py --matrix llmrouterbench-matrix.jsonl"
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl",
    COMMAND[2:],
]
SECTIONS = ["Facts", "Method", "Results", "Reading it", "Recommendation", "Limits", "Regenerate"]
BULLET = "- A price error, on LLMRouterBench (v1.403, row R35): "
# DESIGN section numbers: the only numbers of the note's prose not in the script's lines
ALLOWED = {"12.3", "12.18", "12.19", "12.22"}
NUMBER = re.compile(r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
FACTORS = (0.5, 2.0)
CONFIG = {"bars": [0.6, 0.3, 0.5], "seeds": list(range(6)), "flavors": ["cost_effective", "cost_blind"],
          "calibration_fraction": 0.5, "min_samples": 10, "confidence": 0.95}
# per task: (items, {model: (percent correct, cost per call)}); doubling v/z's cost puts it above
# v/y's and halving v/y's puts it below v/z's, so where both clear a bar the cheaper one changes
TINY = {"a": (120, {"v/x": (90, 0.03), "v/y": (70, 0.02), "v/z": (62, 0.012)}),
        "b": (100, {"v/x": (85, 0.03), "v/y": (60, 0.02), "v/z": (50, 0.012)})}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ps():
    return _load("research_price_sensitivity", SCRIPT)


def tiny_rows(scale=None, factor=1.0):
    """Two tasks; correctness from a hash, so the halves vary by seed; `scale`'s costs times `factor`."""
    rows = []
    for task, (n, models) in TINY.items():
        for i in range(n):
            for model, (pct, cost) in models.items():
                h = int(hashlib.sha256(f"{task}|{i}|{model}".encode()).hexdigest(), 16)
                c = cost * (1 + i % 3)
                rows.append({"task": task, "item": f"{task}{i}", "model": model, "correct": h % 100 < pct,
                             "cost_usd": c * factor if model == scale else c})
    return rows


def run_evaluate(rows, bars=None, flavors=None):
    return evaluate(outcomes_from_rows(rows), bars=bars or CONFIG["bars"], seeds=CONFIG["seeds"],
                    flavors=flavors or CONFIG["flavors"], calibration_fraction=CONFIG["calibration_fraction"],
                    min_samples=CONFIG["min_samples"], confidence=CONFIG["confidence"])


def committed(rows):
    result = run_evaluate(rows)
    return {"config": result["config"], "summary": result["summary"]}


def pooled(cells, picks):
    """Means over seeds of the pooled held-out success and cost of the models `picks` names."""
    success, cost = [], []
    for seed in CONFIG["seeds"]:
        cs = [c for c in cells if c["seed"] == seed]
        right = sum(round(c["success"]["model:" + picks[c["task"], seed]] * c["held_out_items"]) for c in cs)
        success.append(right / sum(c["held_out_items"] for c in cs))
        cost.append(math.fsum(c["cost_usd"]["model:" + picks[c["task"], seed]] for c in cs))
    return math.fsum(success) / len(success), math.fsum(cost) / len(cost)


def expected_lines(rows):
    """The script's lines on `rows`, built from `evaluate` runs on rows with one model's costs scaled."""
    bars = [min(CONFIG["bars"]), max(CONFIG["bars"])]
    base = run_evaluate(rows, bars, ["cost_effective"])
    models = sorted({r["model"] for r in rows})
    n_cells = len(TINY) * len(CONFIG["seeds"])
    lines = [f"LLMRouterBench (evidence/tiny/results.json): 2 tasks, 3 models, 220 items, 6 seeds, flavor "
             f"cost_effective, bars {bars[0]} and {bars[1]}, the lowest and highest of 3",
             "the router is built with one model's calibration mean cost times 0.5 or 2.0, every other model's "
             "as recorded, and each pick is scored at the recorded held-out costs"]
    for bar in bars:
        cells = [c for c in base["cells"] if c["bar"] == bar]
        was = {(c["task"], c["seed"]): c["models"]["routed"] for c in cells}
        success, cost = pooled(cells, was)
        lines.append(f"bar {bar}: committed routed success {success:.4f}, cost {cost:.4f}; per model and factor, "
                     f"the cells of {n_cells} whose routed model changes, the held-out success with its gap "
                     f"and the cost with its ratio to the committed row")
        changed, gaps, ratios = [], [], []
        for model in models:
            parts = []
            for factor in FACTORS:
                scaled = run_evaluate(tiny_rows(model, factor), [bar], ["cost_effective"])
                now = {(c["task"], c["seed"]): c["models"]["routed"] for c in scaled["cells"]}
                k = sum(now[key] != was[key] for key in was)
                s, x = pooled(cells, now)
                changed.append(k)
                gaps.append(s - success)
                ratios.append(x / cost)
                parts.append(f"times {factor}: {k} of {n_cells} cells change ({100 * k / n_cells:.1f}%), "
                             f"success {s:.4f} ({s - success:+.4f}), cost {x:.4f} ({x / cost:.3f})")
            lines.append(f"  {model}: " + "; ".join(parts))
        lines.append(f"  over the {len(changed)}: cells changed {min(changed)} to {max(changed)}, success gap "
                     f"{min(gaps):+.4f} to {max(gaps):+.4f}, cost ratio {min(ratios):.3f} to {max(ratios):.3f}")
    return lines


def test_pooled_by_hand(ps):
    def cell(seed, task, held, success, cost):
        return {"seed": seed, "task": task, "held_out_items": held,
                "success": {"model:v/a": success[0], "model:v/b": success[1]},
                "cost_usd": {"model:v/a": cost[0], "model:v/b": cost[1]}}
    cells = [cell(0, "s", 10, (0.5, 0.9), (1.0, 4.0)), cell(0, "t", 30, (0.2, 0.6), (2.0, 8.0)),
             cell(1, "s", 20, (0.25, 0.75), (1.5, 6.0)), cell(1, "t", 20, (0.5, 1.0), (3.0, 9.0))]
    picks = {("s", 0): "v/a", ("t", 0): "v/b", ("s", 1): "v/b", ("t", 1): "v/a"}
    # seed 0: (5 + 18) / 40 = 0.575 at 1.0 + 8.0; seed 1: (15 + 10) / 40 = 0.625 at 6.0 + 3.0
    assert ps.pooled(cells, [0, 1], picks) == (pytest.approx(0.6, abs=1e-15), 9.0)


def test_picks_are_evaluate_on_scaled_costs(ps):
    rows = tiny_rows()
    outcomes = outcomes_from_rows(rows)
    bar = max(CONFIG["bars"])
    base = run_evaluate(rows, [bar], ["cost_effective"])
    sums = ps.calibration(outcomes, sorted(TINY), CONFIG["seeds"], CONFIG["calibration_fraction"])
    flips = 0
    for model in ("v/x", "v/y", "v/z"):
        for factor in FACTORS:
            scaled = run_evaluate(tiny_rows(model, factor), [bar], ["cost_effective"])
            want = {(c["task"], c["seed"]): c["models"]["routed"] for c in scaled["cells"]}
            got = ps.picks(sums, base["cells"], model, factor, CONFIG["min_samples"], CONFIG["confidence"])
            assert got == want
            flips += sum(c["models"]["routed"] != want[c["task"], c["seed"]] for c in base["cells"])
    assert flips > 0


def test_report_lines_on_a_small_matrix(ps):
    rows = tiny_rows()
    lines = ps.report(outcomes_from_rows(rows), committed(rows), rel="evidence/tiny/results.json")
    assert lines == expected_lines(rows)
    # the matrix exercises the counts: some factor changes some pick, and not every one
    counts = [int(n) for n in re.findall(r": (\d+) of 12 cells change", "\n".join(lines))]
    assert len(counts) == 12 and 0 < max(counts) < 12 and min(counts) == 0


@pytest.mark.parametrize("key", ["success", "cost_usd"])
@pytest.mark.parametrize("bar", [0.3, 0.6])
def test_report_stops_when_a_routed_row_is_not_the_committed_one(ps, bar, key):
    rows = tiny_rows()
    record = committed(rows)
    hit = [r for r in record["summary"] if (r["bar"], r["flavor"], r["strategy"]) == (bar, "cost_effective", "routed")]
    assert len(hit) == 1
    hit[0][key] *= 1 + 1e-9
    with pytest.raises(ValueError, match="committed"):
        ps.report(outcomes_from_rows(rows), record)


def test_report_stops_when_the_rebuilt_router_differs(ps, monkeypatch):
    rows = tiny_rows()
    monkeypatch.setattr(ps, "route", lambda *args, **kwargs: "v/none")
    with pytest.raises(ValueError, match="routed model"):
        ps.report(outcomes_from_rows(rows), committed(rows))


def test_report_needs_cost_effective_in_the_config(ps):
    rows = tiny_rows()
    record = committed(rows)
    record["config"]["flavors"] = ["cost_blind"]
    with pytest.raises(ValueError, match="cost_effective"):
        ps.report(outcomes_from_rows(rows), record)


def _tree(tmp_path, rows):
    path = tmp_path / RESULTS
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(committed(rows)), encoding="utf-8")
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return ["--root", str(tmp_path), "--matrix", str(matrix)]


def _main(ps, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ps.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_main_prints_the_report(ps, tmp_path):
    rows = tiny_rows()
    code, out, err = _main(ps, _tree(tmp_path, rows))
    assert (code, err) == (0, "")
    assert out == "\n".join(ps.report(outcomes_from_rows(rows), committed(rows))) + "\n"
    assert out.startswith(f"LLMRouterBench ({RESULTS}): 2 tasks, ")


@pytest.mark.parametrize("break_it", ["matrix", "results", "key", "row"])
def test_main_exits_2_with_one_error_line(ps, tmp_path, break_it):
    rows = tiny_rows()
    argv = _tree(tmp_path, rows)
    if break_it == "matrix":
        argv[argv.index("--matrix") + 1] = str(tmp_path / "missing.jsonl")
    elif break_it == "results":
        (tmp_path / RESULTS).write_text("not json", encoding="utf-8")
    elif break_it == "key":
        (tmp_path / RESULTS).write_text(json.dumps({"summary": []}), encoding="utf-8")
    else:
        (tmp_path / "m.jsonl").write_text(json.dumps({"task": "t", "item": "i", "model": "m"}) + "\n",
                                          encoding="utf-8")
    code, out, err = _main(ps, argv)
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1


def test_script_is_standard_library_and_model_routing():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^(?:from|import) ([\w.]+)", text, flags=re.M)}
    assert imports <= {"argparse", "json", "math", "sys", "pathlib", "model_routing"}
    assert text.isascii()


def _blocks(text, lang):
    return re.findall(rf"^```{lang}\n(.*?)^```$", text, flags=re.M | re.S)


def _prose(note):
    prose = re.sub(r"^```\w*\n.*?^```$", "", note, flags=re.M | re.S)
    return re.sub(r"\]\([^)]*\)|`[^`]*`", "", prose)


def _section(note, name):
    return note.split(f"\n## {name}\n", 1)[1].split("\n## ", 1)[0]


def test_note_quotes_its_commands_and_links():
    note = NOTE.read_text(encoding="utf-8")
    assert note.startswith("# How far a price error moves `cost_effective` routing\n\n")
    assert not note.split("\n", 2)[2].startswith("#")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == SECTIONS
    assert _blocks(note, "bash") == ["\n".join(REGENERATE) + "\n"]
    [text] = _blocks(note, "text")
    assert text.startswith(COMMAND + "\n")
    assert note.isascii()
    for link in ("../DESIGN.md", "../evidence/llmrouterbench/RESULTS.md", "price_sensitivity.py",
                 "llmrouterbench-seeds.md"):
        assert f"]({link})" in note, link


def test_facts_states_the_finding_before_any_number():
    note = NOTE.read_text(encoding="utf-8")
    first = [x for x in _section(note, "Facts").split("\n") if x.startswith("- ")][0]
    assert NUMBER.findall(_prose(first)) == [], first


def test_every_number_of_the_prose_is_in_the_output_or_allowed():
    note = NOTE.read_text(encoding="utf-8")
    [text] = _blocks(note, "text")
    printed = set(NUMBER.findall(text))
    assert sorted({n for n in NUMBER.findall(_prose(note)) if n not in printed and n not in ALLOWED}) == []


def test_the_recommendation_names_the_follow_on_row():
    assert "row DOC30" in _section(NOTE.read_text(encoding="utf-8"), "Recommendation")


def test_the_research_index_lists_the_note():
    index = INDEX.read_text(encoding="utf-8").split("\n")
    rows = [x for x in index if x.startswith("| [price-sensitivity.md](price-sensitivity.md) | ")]
    assert len(rows) == 1 and "[price_sensitivity.py](price_sensitivity.py)" in rows[0]
    assert sum(x.startswith("- `research/price-sensitivity.md` ") for x in index) == 1


def test_the_design_bullet_is_in_12_22_and_under_1900_bytes():
    text = DESIGN.read_text(encoding="utf-8")
    start, end = text.index("### 12.22 "), text.index("\n## 13. ")
    lines = [line for line in text[start:end].splitlines() if line.startswith(BULLET)]
    assert len(lines) == 1
    assert len(lines[0].encode("utf-8")) < 1900



# --- README Limitations' prices bullet (DESIGN 9 v1.417, row DOC30) ----------------------------

README = ROOT / "README.md"
PRICES = "- Prices are a dated snapshot. "
REFRESH = ("Refresh `models.json` yourself, and check that the model your gateway actually serves "
           "matches the ID you calibrated. ")
DESIGN_9 = (
    "- v1.417 a price error in the README (row DOC30, the Recommendation of the 12.22 v1.403 note): README "
    "Limitations' prices bullet gives, in one sentence right after the one that asks the reader to refresh "
    "`models.json` and check the model the gateway serves, how far a wrong price moves `cost_effective` routing, "
    "from `research/price-sensitivity.md`, which it links: on LLMRouterBench, with one model's price halved or "
    "doubled, one model at a time, the most picks that changed, one per (task, seed) cell, as a count of the cells and "
    "a share, the range of the held-out success gap and, apart from it, the highest cost ratio, at the lowest committed "
    "bar and then at the highest; "
    "then that a price is to be refreshed whenever its vendor changes it, most of all for a task with a low bar, at "
    "no fixed interval, since the note measures what a wrong price does, not how often prices change. Its numbers "
    "are the note's own: the two bars, the cells per bar, which are its tasks times its seeds, each bar's highest "
    "changed count, success gap range and highest cost ratio from its closing `over the` line, and each share, that "
    "count over the cells to one decimal, the share the script prints beside it, all of which "
    "tests/test_research_price_sensitivity.py reads "
    "from the note's Results block to build the sentence, pinned once in that place; the bars are the lowest and "
    "highest of `evidence/llmrouterbench/results.json`. No code, cost, committed result or README transcript changes\n")
SPAN = re.compile(
    r"^bar ([\d.]+): committed .*? the cells of (\d+) whose .*?^  over the \d+: cells changed \d+ to (\d+), "
    r"success gap ([+-][\d.]+) to ([+-][\d.]+), cost ratio [\d.]+ to ([\d.]+)$", flags=re.M | re.S)


def note_spans():
    """Per bar of the note's Results block, lowest first: (bar, cells, most changed, gap from, gap to, top ratio)."""
    [text] = _blocks(NOTE.read_text(encoding="utf-8"), "text")
    spans = SPAN.findall(text)
    assert len(spans) == 2 and spans[0][1] == spans[1][1]
    low, high = spans
    assert f"bars {low[0]} and {high[0]}, the lowest and highest of " in text
    # the cells are one per task and seed, as the sentence says (review iter-278 should-fix 1)
    [(tasks, seeds)] = re.findall(r"^LLMRouterBench .*?: (\d+) tasks, .*?, (\d+) seeds, ", text, flags=re.M)
    assert int(low[1]) == int(tasks) * int(seeds)
    assert "with one model's calibration mean cost times 0.5 or 2.0, every other model's as recorded" in text
    for bar, cells, most, *_ in spans:
        share = f"{100 * int(most) / int(cells):.1f}%"
        # the share the sentence gives is the one the script prints for that count
        assert f": {most} of {cells} cells change ({share})" in text.split(f"\nbar {bar}: ", 1)[1].split("\nbar ", 1)[0]
    return spans


def price_error_sentence():
    (lo, cells, most_lo, g_lo, g_hi, r_lo), (hi, _, most_hi, h_lo, h_hi, r_hi) = note_spans()
    def share(most):
        return f"{100 * int(most) / int(cells):.1f}%"
    return (
        "A wrong price moves `cost_effective` routing most at a low bar: on LLMRouterBench "
        "([research/price-sensitivity.md](research/price-sensitivity.md)), one model's price halved or doubled, "
        f"one model at a time, changed up to {most_lo} of the {cells} picks, one per task and seed ({share(most_lo)}), "
        f"at the lowest committed bar, {lo}, moving held-out success by {g_lo} to {g_hi} and the cost up to {r_lo} "
        f"times, and up to {most_hi} ({share(most_hi)}) at the highest, {hi}, by {h_lo} to {h_hi} and up to {r_hi} "
        "times, so refresh a price "
        "whenever its vendor changes it, most of all for a task with a low bar (the note measures what a wrong "
        "price does, not how often prices change, so it sets no fixed interval). ")


def test_the_note_bars_are_the_lowest_and_highest_committed():
    bars = json.loads((ROOT / RESULTS).read_text(encoding="utf-8"))["config"]["bars"]
    (lo, *_), (hi, *_) = note_spans()
    assert (float(lo), float(hi)) == (min(bars), max(bars))


def test_readme_limitations_give_the_price_error_after_the_refresh_sentence():
    sentence = price_error_sentence()
    readme = README.read_text(encoding="utf-8")
    limits = readme.split("\n## Limitations and non-goals (v1)\n", 1)[1].split("\n## ", 1)[0]
    [bullet] = [x for x in limits.split("\n") if x.startswith(PRICES)]
    assert bullet.count(sentence) == 1
    assert bullet.index(PRICES + REFRESH) == 0
    assert bullet.index(sentence) == len(PRICES + REFRESH)
    assert bullet[len(PRICES + REFRESH + sentence):].startswith("A row whose vendor states an end date ")
    # Limitations links the note in this sentence alone
    assert limits.count("](research/price-sensitivity.md)") == 1


def test_design_9_states_the_limitations_sentence_and_12_22_points_to_it():
    text = DESIGN.read_text(encoding="utf-8")
    s9 = text[text.index("\n## 9. Data files\n"):text.index("\n## 10. ")]
    assert s9.count(DESIGN_9) == 1
    # no number of the sentence is written into the clause, so the clause cannot go stale
    assert NUMBER.findall(DESIGN_9.split(": README Limitations' prices bullet", 1)[1]) == []
    start, end = text.index("### 12.22 "), text.index("\n## 13. ")
    [line] = [x for x in text[start:end].splitlines() if x.startswith(BULLET)]
    assert line.endswith("; README Limitations links it (9 v1.417)")


# --- the pinned file, only when already cached (one session read, tests/conftest.py) ----------

@pytest.fixture(scope="module")
def output(ps, llmrouterbench_pinned):
    """The script's lines on the matrix the session fixture wrote from the cached pinned file."""
    code, report, rows = llmrouterbench_pinned
    assert code == 0 and report["rows"] == 156858
    status, out, err = _main(ps, ["--matrix", str(rows)])
    assert (status, err) == (0, "")
    return out


def test_note_results_block_is_the_script_output(output):
    [text] = _blocks(NOTE.read_text(encoding="utf-8"), "text")
    assert text == COMMAND + "\n" + output


def test_each_unscaled_row_is_the_committed_row(output):
    record = json.loads((ROOT / RESULTS).read_text(encoding="utf-8"))
    bars = [min(record["config"]["bars"]), max(record["config"]["bars"])]
    found = re.findall(r"^bar ([\d.]+): committed routed success ([\d.]+), cost ([\d.]+);", output, flags=re.M)
    assert [float(b) for b, _, _ in found] == bars
    for bar, success, cost in found:
        [row] = [r for r in record["summary"]
                 if (r["bar"], r["flavor"], r["strategy"]) == (float(bar), "cost_effective", "routed")]
        assert (success, cost) == (f"{row['success']:.4f}", f"{row['cost_usd']:.4f}")
