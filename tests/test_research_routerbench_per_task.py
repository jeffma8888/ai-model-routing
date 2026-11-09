"""research/routerbench-per-task.md and research/routerbench_per_task.py (DESIGN 12.8 v1.146).

The note's numbers are the script's lines on the pinned RouterBench file, compared byte for byte
when the file and pandas are present (CI never downloads it). The script's report is rebuilt here on
a small matrix with the 12.2 split computed apart from `evaluate`, and its exits are tested with the
converter's reader replaced.
"""

import contextlib
import importlib.util
import io
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import median_low

import pytest

from model_routing import evaluate, outcomes_from_rows, split_items
from model_routing.stats import items_needed, wilson_lower_bound

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "routerbench_per_task.py"
NOTE = ROOT / "research" / "routerbench-per-task.md"
INDEX = ROOT / "research" / "README.md"
PAYS = ROOT / "research" / "where-routing-pays.md"
COMMAND = "$ python research/routerbench_per_task.py"
REGENERATE = ['python -m pip install -e ".[evidence]"',
              "python evidence/routerbench/convert.py --out routerbench-matrix.jsonl",
              COMMAND[2:]]
# DESIGN section numbers: the only numbers of the note's prose not in the script's lines
ALLOWED = {"4.3", "5.3", "12.2", "12.3", "12.6", "12.7", "12.8"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?%?")
CONFIG = {"bars": [0.5, 0.75], "seeds": [0, 1, 2, 3]}
TASKS = ("mmlu-a", "mmlu-b", "other")
MODELS = ("v/alt", "v/cheap", "v/top")
WIDTHS = ((40, "<"), (5, ">"), (4, ">"), (33, "<"), (4, ">"), (7, "<"), (6, "<"), (6, "<"), (9, "<"),
          (5, ">"), (6, ">"))
GROUP_WIDTHS = ((6, "<"), (5, ">"), (35, "<"), (7, "<"), (10, "<"), (9, ">"))


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rpt():
    return _load("research_routerbench_per_task", SCRIPT)


def tiny_rows():
    """`v/top` is the best single model; `v/alt` beats it by 0.15 on `mmlu-b`; `v/cheap` ties it on `other`."""
    rows = []
    for task in TASKS:
        for i in range(120):
            for model, ok, cost in (
                    ("v/top", i % 10 < 8, 0.02),
                    ("v/alt", (i % 20 < 19) if task == "mmlu-b" else (i % 10 < 5), 0.01),
                    ("v/cheap", (i % 10 < 8) if task == "other" else (i % 10 < 3), 0.001)):
                rows.append({"task": task, "item": f"{task}-{i}", "model": model, "correct": ok,
                             "cost_usd": cost * (1 + i % 3)})
    return rows


def committed(rows):
    result = evaluate(outcomes_from_rows(rows), bars=CONFIG["bars"], seeds=CONFIG["seeds"], min_samples=10)
    return {"config": result["config"], "summary": result["summary"]}


def _fmt(values, widths):
    return "  " + "  ".join(f"{v:{a}{w}}" for v, (w, a) in zip(values, widths))


def _split_view(rows):
    """Per (task, seed): held-out correct count and fsum cost per model, and the oracle's, from 12.2 alone."""
    by = {}
    for r in rows:
        by.setdefault(r["task"], {}).setdefault(r["item"], {})[r["model"]] = r
    view = {}
    for task, items in by.items():
        for seed in CONFIG["seeds"]:
            cal, held = split_items(items, seed, 0.5)
            ok = {m: sum(items[i][m]["correct"] for i in held) for m in MODELS}
            cost = {m: math.fsum(items[i][m]["cost_usd"] for i in held) for m in MODELS}
            right, spend = 0, []
            for i in held:
                good = [items[i][m]["cost_usd"] for m in MODELS if items[i][m]["correct"]]
                right += bool(good)
                spend.append(min(good) if good else min(items[i][m]["cost_usd"] for m in MODELS))
            view[task, seed] = {"cal": len(cal), "held": len(held), "ok": ok, "cost": cost,
                                "oracle": (right, math.fsum(spend))}
    return view


def _held_best(v):
    return min(MODELS, key=lambda m: (-v["ok"][m], v["cost"][m], m))


def expected_lines(rows):
    """The report rebuilt from the rows and the 12.2 split; only the routed and calibration picks come from `evaluate`."""
    result = evaluate(outcomes_from_rows(rows), bars=[0.5], seeds=CONFIG["seeds"], flavors=["cost_blind"],
                      min_samples=10)
    picks = {(c["task"], c["seed"]): c["models"] for c in result["cells"]}
    view = _split_view(rows)
    seeds = CONFIG["seeds"]
    ok, cost, items = Counter(), {}, Counter()
    for r in rows:
        ok[r["task"], r["model"]] += r["correct"]
        cost.setdefault((r["task"], r["model"]), []).append(r["cost_usd"])
        items[r["task"]] += r["model"] == "v/top"
    single = "v/top"
    s_single = math.fsum(sum(view[t, s]["ok"][single] for t in TASKS) / sum(view[t, s]["held"] for t in TASKS)
                         for s in seeds) / len(seeds)
    c_single = math.fsum(math.fsum(view[t, s]["cost"][single] for t in TASKS) for s in seeds) / len(seeds)
    out = [f"RouterBench (tiny): 3 evals, 3 models, {sum(items.values()):,} items, 4 seeds, "
           f"calibration_fraction 0.5, confidence 0.95",
           f"best single model (12.7): v/top, held-out success {s_single:.4f} at {c_single:.4f} USD",
           "per eval: its items and calibration half (median over seeds), its best model on all its items, "
           "the models tied on that count, that model's success and the best single model's on all items, "
           "the margin, the Wilson shortfall of that success at the half, the seeds on which it is also the "
           "best on the held-out half, and the models that are that best on some seed",
           _fmt(("eval", "items", "half", "best on all items", "tied", "success", "single", "margin",
                 "shortfall", "seeds", "models"), WIDTHS)]
    best, info = {}, {}
    for t in TASKS:
        top = min(MODELS, key=lambda m: (-ok[t, m], math.fsum(cost[t, m]), m))
        best[t] = top
        n = items[t]
        half = median_low([view[t, s]["cal"] for s in seeds])
        sb, sg = ok[t, top] / n, ok[t, single] / n
        sf = sb - wilson_lower_bound(round(sb * half), half, 0.95)
        hb = Counter(_held_best(view[t, s]) for s in seeds)
        info[t] = (sb - sg, sf, ok[t, top] > ok[t, single])
        out.append(_fmt((t, n, half, top, sum(ok[t, m] == ok[t, top] for m in MODELS), f"{sb:.3f}",
                         f"{sg:.3f}", f"{sb - sg:+.3f}", f"{sf:.3f}", hb[top], len(hb)), WIDTHS))
    others = [t for t in TASKS if best[t] != single]
    higher = [t for t in others if info[t][2]]
    out.append(f"evals whose best model on all items is not v/top: {len(others)} ({', '.join(others)}); "
               f"with a higher success than it: {len(higher)}; higher by more than the shortfall: "
               f"{sum(info[t][0] > info[t][1] for t in higher)}")
    top_t = max(higher, key=lambda t: (info[t][0], t))
    out.append(f"largest margin: {info[top_t][0]:+.3f} on {top_t} ({best[top_t]}), shortfall {info[top_t][1]:.3f}")
    moved = {k: [key for key, p in picks.items() if p[k] != single] for k in ("routed", "best_on_calibration")}
    out.append(f"routed (cost_blind, bar 0.5) takes another model on {len(moved['routed']):,} of 12 eval and "
               f"seed cells, on {len({t for t, _ in moved['routed']})} evals; best_on_calibration on "
               f"{len(moved['best_on_calibration']):,}, on {len({t for t, _ in moved['best_on_calibration']})} evals")
    out.append("held-out success and cost over 4 seeds, as 12.3's summary computes them; vs single: the mean "
               "correct held-out items per seed minus the best single model's")
    out.append(_fmt(("group", "evals", "strategy", "success", "cost (USD)", "vs single"), GROUP_WIDTHS))

    def pick_ok(t, s, label):
        v = view[t, s]
        if label == "oracle (per prompt)":
            return v["oracle"]
        m = {"best single model": single, "routed (cost_blind, bar 0.5)": picks[t, s]["routed"],
             "best_on_calibration": picks[t, s]["best_on_calibration"], "per-eval best on all items": best[t],
             "per-eval best on each held-out half": _held_best(v)}[label]
        return v["ok"][m], v["cost"][m]

    for group, members in (("all", TASKS), ("mmlu", TASKS[:2]), ("other", TASKS[2:])):
        for label in ("best single model", "routed (cost_blind, bar 0.5)", "best_on_calibration",
                      "per-eval best on all items", "per-eval best on each held-out half", "oracle (per prompt)"):
            succ, spent, gap = [], [], []
            for s in seeds:
                right = sum(pick_ok(t, s, label)[0] for t in members)
                succ.append(right / sum(view[t, s]["held"] for t in members))
                spent.append(math.fsum(pick_ok(t, s, label)[1] for t in members))
                gap.append(right - sum(view[t, s]["ok"][single] for t in members))
            out.append(_fmt((group, len(members), label, f"{math.fsum(succ) / 4:.4f}",
                             f"{math.fsum(spent) / 4:.4f}", f"{sum(gap) / 4:+.1f}"), GROUP_WIDTHS))
    out.append("what another dataset needs, at a success of 0.8: the calibration half from which the Wilson "
               "shortfall is within the margin (items_needed, 4.3), and the share of items that evals with that "
               "margin over the best single model must hold for a gain of 0.01 in success")
    for margin in (0.02, 0.05, 0.1):
        out.append(f"  margin {margin}: half {items_needed(0.8, round(0.8 - margin, 2), 0.95):,}; "
                   f"share of items {0.01 / margin:.2f}")
    return out


def test_report_on_a_small_matrix(rpt):
    rows = tiny_rows()
    assert rpt.report(rows, committed(rows), "tiny") == expected_lines(rows)


def test_small_matrix_names_the_two_evals_another_model_leads(rpt):
    lines = rpt.report(tiny_rows(), committed(tiny_rows()), "tiny")
    assert ("evals whose best model on all items is not v/top: 2 (mmlu-b, other); with a higher success than "
            "it: 1; higher by more than the shortfall: 1") in lines
    [largest] = [x for x in lines if x.startswith("largest margin: ")]
    assert largest.startswith("largest margin: +0.150 on mmlu-b (v/alt), shortfall 0.")
    rows = {x.split()[0]: x.split() for x in lines[4:7]}
    assert sorted(rows) == list(TASKS)
    assert rows["mmlu-a"][3:5] == ["v/top", "1"] and rows["mmlu-b"][3:5] == ["v/alt", "1"]
    assert rows["other"][3:5] == ["v/cheap", "2"] and rows["other"][7] == "+0.000"


@pytest.mark.parametrize("strategy", ["routed", "oracle", "best_on_calibration", "model:v/alt"])
@pytest.mark.parametrize("key", ["success", "cost_usd"])
def test_report_stops_when_a_row_is_not_the_committed_one(rpt, strategy, key):
    rows = tiny_rows()
    record = committed(rows)
    for r in record["summary"]:
        if (r["bar"], r["flavor"], r["strategy"]) == (0.5, "cost_blind", strategy):
            r[key] = r[key] * (1 + 1e-9)
    with pytest.raises(ValueError, match="committed"):
        rpt.report(rows, record, "tiny")


def _tree(tmp_path, rows):
    path = tmp_path / "evidence" / "routerbench" / "results.json"
    path.parent.mkdir(parents=True)
    path.write_text(json.dumps(committed(rows)), encoding="utf-8")
    return ["--root", str(tmp_path), "--cache", str(tmp_path / "cache")]


def _main(rpt, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = rpt.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_main_prints_the_report_of_the_rows_the_reader_returns(rpt, tmp_path, monkeypatch):
    rows = tiny_rows()
    seen = []
    monkeypatch.setattr(rpt, "load_rows", lambda cache: seen.append(cache) or rows)
    code, out, err = _main(rpt, _tree(tmp_path, rows))
    assert (code, err) == (0, "")
    conv = rpt.converter()
    source = f"{conv.FILENAME} at revision {conv.REVISION}"
    assert out == "\n".join(rpt.report(rows, committed(rows), source)) + "\n"
    assert seen == [Path(tmp_path / "cache")]


def test_load_rows_checks_the_pinned_file_before_reading_it(rpt, tmp_path):
    conv = rpt.converter()
    with pytest.raises(OSError):
        rpt.load_rows(tmp_path)
    (tmp_path / conv.FILENAME).write_bytes(b"not the pinned file")
    with pytest.raises(ValueError, match="bytes"):
        rpt.load_rows(tmp_path)


@pytest.mark.parametrize("break_it", ["no file", "wrong size", "results", "key", "row"])
def test_main_exits_2_with_one_error_line(rpt, tmp_path, monkeypatch, break_it):
    rows = tiny_rows()
    argv = _tree(tmp_path, rows)
    results = tmp_path / "evidence" / "routerbench" / "results.json"
    if break_it == "wrong size":
        (tmp_path / "cache").mkdir()
        (tmp_path / "cache" / rpt.converter().FILENAME).write_bytes(b"x")
    elif break_it != "no file":
        monkeypatch.setattr(rpt, "load_rows", lambda cache: rows)
        if break_it == "results":
            results.write_text("not json", encoding="utf-8")
        elif break_it == "key":
            results.write_text(json.dumps({"summary": []}), encoding="utf-8")
        else:
            record = committed(rows)
            for r in record["summary"]:
                if (r["flavor"], r["strategy"]) == ("cost_blind", "model:v/top"):
                    r["success"] += 0.001
            results.write_text(json.dumps(record), encoding="utf-8")
    code, out, err = _main(rpt, argv)
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1


def test_script_is_standard_library_model_routing_and_the_converter():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^(?:from|import) ([\w.]+)", text, flags=re.M)}
    assert imports <= {"__future__", "argparse", "collections", "importlib", "json", "math", "pickle",
                       "statistics", "sys", "pathlib", "model_routing"}
    assert '"evidence" / "routerbench" / "convert.py"' in text
    assert text.isascii()


def _blocks(text, lang):
    return re.findall(rf"^```{lang}\n(.*?)^```$", text, flags=re.M | re.S)


def test_note_quotes_its_commands_and_links():
    note = NOTE.read_text(encoding="utf-8")
    assert note.startswith("# Each RouterBench eval's own best model\n")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == [
        "Facts", "Method", "Results", "Reading it", "What another dataset needs", "Limits", "Regenerate"]
    assert _blocks(note, "bash") == ["\n".join(REGENERATE) + "\n"]
    [text] = _blocks(note, "text")
    assert text.startswith(COMMAND + "\n")
    assert note.isascii()
    for link in ("../DESIGN.md", "../evidence/routerbench/RESULTS.md", "routerbench_per_task.py",
                 "where-routing-pays.md"):
        assert f"]({link})" in note, link


def test_every_number_of_the_prose_is_in_the_output_or_allowed():
    note = NOTE.read_text(encoding="utf-8")
    [text] = _blocks(note, "text")
    prose = re.sub(r"^```\w*\n.*?^```$", "", note, flags=re.M | re.S)
    prose = re.sub(r"\]\([^)]*\)|`[^`]*`", "", prose)
    printed = set(NUMBER.findall(text))
    assert sorted({n for n in NUMBER.findall(prose) if n not in printed and n not in ALLOWED}) == []


def test_where_routing_pays_limits_and_the_research_index_link_the_note():
    pays = PAYS.read_text(encoding="utf-8")
    limits = pays[pays.index("\n## Limits\n"):pays.index("\n## Regenerate\n")]
    bullets = [x for x in limits.split("\n") if "](routerbench-per-task.md)" in x]
    assert len(bullets) == 1 and "per-task single-model rows" in bullets[0]
    index = INDEX.read_text(encoding="utf-8")
    assert sum(x.startswith("| [routerbench-per-task.md](routerbench-per-task.md) | ")
               for x in index.split("\n")) == 1
    assert "[routerbench_per_task.py](routerbench_per_task.py)" in index
    assert sum(x.startswith("- `research/routerbench-per-task.md` ") for x in index.split("\n")) == 1


# --- the pinned file, only when already cached -------------------------------------------------

@pytest.fixture(scope="module")
def output(rpt):
    """The script's lines on the pinned RouterBench file, read through the converter from the default cache."""
    pytest.importorskip("pandas")
    conv = rpt.converter()
    if not (conv.default_cache_dir() / conv.FILENAME).is_file():
        pytest.skip("the pinned RouterBench file is not in the default cache")
    rows = rpt.load_rows(conv.default_cache_dir())
    record = json.loads((ROOT / "evidence" / "routerbench" / "results.json").read_text(encoding="utf-8"))
    return "\n".join(rpt.report(rows, record, f"{conv.FILENAME} at revision {conv.REVISION}")) + "\n"


def test_note_results_block_is_the_script_output(output):
    [text] = _blocks(NOTE.read_text(encoding="utf-8"), "text")
    assert text == COMMAND + "\n" + output


def test_no_eval_has_another_model_ahead_by_more_than_its_shortfall(output):
    [line] = [x for x in output.split("\n") if x.startswith("evals whose best model on all items is not ")]
    assert line.endswith("; higher by more than the shortfall: 0")
    rows = {x[17:52].strip(): float(x[54:61]) for x in output.split("\n") if x.startswith("  all   ")}
    assert len(rows) == 6
    single = rows["best single model"]
    assert 0 <= rows["per-eval best on all items"] - single < 0.001
    assert 0 <= rows["per-eval best on each held-out half"] - single < 0.001
