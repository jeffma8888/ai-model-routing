"""research/delegation-price-sensitivity.md and research/delegation_price_sensitivity.py (DESIGN 12.22 v1.424,
row R39).

The script's report on a hand-built AutoBench-shaped matrix of three models, run end to end through `main`
against a root whose committed 13.10 files are that matrix's, is checked against a brute force that rebuilds
each cell's router from the public API on a registry with one model's prices scaled, and prices each held-out
item at the committed prices in exact fractions; `scaled` changes one model's two prices and nothing else; the
script exits 2 where research/reread_sensitivity.py's `checked` does. The note's Results block is the script's
output on the pinned AutoBench files, compared byte for byte when they are cached, which CI never does; every
number of the note's prose is in a Facts bullet this file builds from that block, or a DESIGN section number.
"""

import contextlib
import dataclasses
import importlib.util
import io
import json
import re
import statistics
from fractions import Fraction
from pathlib import Path

import pytest

from model_routing import Model, Registry, Router, Stats, Task, evaluate_delegation, split_items

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "delegation_price_sensitivity.py"
NOTE = ROOT / "research" / "delegation-price-sensitivity.md"
INDEX = ROOT / "research" / "README.md"
DESIGN = ROOT / "DESIGN.md"
FOLDER = ROOT / "evidence" / "delegation"
COMMAND = ("$ python research/delegation_price_sensitivity.py --matrix autobench-tokens.jsonl"
           " --registry autobench-pool.json")
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens"
    " --registry autobench-pool.json",
    COMMAND[2:],
]
SECTIONS = ["Facts", "Method", "Results", "Reading it", "Recommendation", "Limits", "Regenerate"]
BULLET = "- A price error in a delegation decision, on AutoBench (v1.424, row R39): "
ALLOWED = {"12.22", "13.2", "13.5", "13.9", "13.10"}
NUMBER = re.compile(r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
FACTORS = (0.5, 2.0)
TITLE = ("One model's list price halved or doubled on the AutoBench 2026 delegation results: each cell re-decided "
         "with that model's input and output prices times 0.5 or 2.0, both picks scored at the committed prices")
HEADER = ("  flavor          bar  runs moving  most changed / cells  share  to inline  success gap  cost ratio  "
          "all cost ratio  by")

# Parent v/p at 1 and 2 USD per million input and output tokens, delegates v/d at 1 and 1 and v/e at 0.8 and
# 0.8, each right on most items, so at bar 0.7 `cost_effective` hands work to v/e, the cheapest delegate
# that clears, until v/d's prices are halved or v/e's doubled; at the folded point 3 inline and delegating
# cost about the same for v/p, so halving or doubling v/p's prices moves some cells between the two paths.
P = Model("v/p", "fam-p", 1.0, 2.0, 1_000_000)
D = Model("v/d", "fam-d", 1.0, 1.0, 1_000_000)
E = Model("v/e", "fam-e", 0.8, 0.8, 1_000_000)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def ps():
    return _load("research_delegation_price_sensitivity", SCRIPT)


@pytest.fixture(scope="module")
def dr():
    return _load("research_delegation_price_results", FOLDER / "results.py")


def _rows():
    rows = []
    for j in range(80):
        item = f"i{j:02d}"
        rows.append({"task": "t", "item": item, "model": "v/p", "correct": j % 10 != 0,
                     "input_tokens": 100, "output_tokens": 1200 + 40 * (j % 11)})
        rows.append({"task": "t", "item": item, "model": "v/d", "correct": j % 20 != 0,
                     "input_tokens": 100, "output_tokens": 100})
        rows.append({"task": "t", "item": item, "model": "v/e", "correct": j % 8 != 3,
                     "input_tokens": 100, "output_tokens": 110 + 10 * (j % 3)})
    return rows


def _root(tmp_path, dr, rows, registry):
    folder = tmp_path / "root" / "evidence" / "delegation"
    folder.mkdir(parents=True)
    (folder / "results.py").write_text((FOLDER / "results.py").read_text(encoding="utf-8"), encoding="utf-8")
    for name, grid in (("results.json", "base"), ("variants.json", "variants")):
        (folder / name).write_text(json.dumps(dr.run(rows, registry, grid), indent=2) + "\n", encoding="utf-8")
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    entries = [dict(dataclasses.asdict(m), source="https://example.org/prices") for m in registry.models]
    for e in entries:
        del e["price_tiers"]
    pool = tmp_path / "pool.json"
    pool.write_text(json.dumps({"version": "1", "as_of": "2026-01-01", "currency": "USD", "models": entries}),
                    encoding="utf-8")
    return tmp_path / "root", matrix, pool


def _main(ps, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = ps.main(argv)
    return code, out.getvalue(), err.getvalue()


# --- the brute force -------------------------------------------------------------------------
def _cost(m, i, o):
    return (Fraction(i) * Fraction(m.price_in) + Fraction(o) * Fraction(m.price_out)) / 1_000_000


def _exact(p, d, point, path, tin, tout):
    """13.2 (the 13.9 cost) in fractions, written apart from the scripts' float expressions."""
    c, b, r, t = (point[k] for k in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns"))
    k = point.get("work_calls", 1)
    w_in, w_out = k * (k + 1) // 2, k * (k - 1) // 2
    if path == "delegate":
        return _cost(p, 0, b) + _cost(d, k * b + w_in * tin + w_out * tout, k * tout) + (1 + t) * _cost(p, b + r, 0)
    separate = point["inline_separate_call"]
    reads = Fraction(k * c if separate else (k - 1) * c) * Fraction(point.get("cached_read_ratio", 1))
    work = _cost(p, reads + w_in * tin + w_out * tout, k * tout)
    return work + ((1 + t) if separate else t) * _cost(p, k * (tin + tout), 0)


def _expected(rows, registry, dr, grid, name):
    """The report lines of one committed file: each run's routers rebuilt from the public API per seed and bar
    on a registry built here with one model's prices scaled, each held-out sum in fractions at the committed
    prices."""
    points = dr.points() if grid == "base" else dr.variant_points()
    cells = evaluate_delegation(rows, registry, bars=list(dr.BARS), points=points, seeds=range(dr.SEEDS))["cells"]
    by = {(r["task"], r["item"], r["model"]): r for r in rows}
    items = list(dict.fromkeys(r["item"] for r in rows))
    models = sorted({r["model"] for r in rows})
    halves = {seed: split_items(items, seed, 0.5) for seed in range(dr.SEEDS)}
    runs = [(m, f) for m in models for f in FACTORS]

    def router(prices, seed, bar):
        cal = halves[seed][0]
        stats = Stats()
        for m in models:
            stats.add("t", m, sum(by["t", i, m]["correct"] for i in cal), len(cal),
                      input_tokens=sum(by["t", i, m]["input_tokens"] for i in cal),
                      output_tokens=sum(by["t", i, m]["output_tokens"] for i in cal))
        task = Task(name="t", bar=bar, min_samples=30, confidence=0.95, independent_of_generator=False,
                    expected_input_tokens=statistics.median_low([by["t", i, m]["input_tokens"] for i in cal for m in models]),
                    expected_output_tokens=statistics.median_low([by["t", i, m]["output_tokens"] for i in cal for m in models]),
                    on_no_model="best_available", max_fallbacks=0)
        return Router(prices, {"t": task}, stats)

    sums = {}

    def held(cell, pick):
        key = (cell["seed"], cell["point"], cell["parent"], pick)
        if key not in sums:
            point = points[cell["point"]]
            p, d = registry.get(cell["parent"]), registry.get(pick[1])
            hits = [by["t", i, pick[1]] for i in halves[cell["seed"]][1]]
            sums[key] = (sum(h["correct"] for h in hits), len(hits),
                         sum(_exact(p, d, point, pick[0], h["input_tokens"], h["output_tokens"]) for h in hits))
        return sums[key]

    new = {}
    for m, f in runs:
        prices = Registry([Model(x.id, x.family, x.price_in * f, x.price_out * f, x.context_window) if x.id == m
                           else x for x in registry.models])
        routers = {(s, b): router(prices, s, b) for s in range(dr.SEEDS) for b in dr.BARS}
        new[m, f] = [routers[c["seed"], c["bar"]].decide_delegation("t", c["parent"], c["flavor"], **points[c["point"]])
                     for c in cells]
    lines = [f"AutoBench 2026, {grid} grid (`evidence/delegation/{name}`): {len(cells):,} cells, {len(dr.BARS)} bars, "
             f"2 flavors, {len(points)} points, {len(models)} parents, {dr.SEEDS} seeds, {len(models)} models, so "
             f"{len(runs)} runs; every cell's decision and held-out sum reproduced at the committed prices", HEADER]
    by_point, by_model = [0] * len(points), {r: [0, 0] for r in runs}
    for flavor in ("cost_effective", "cost_blind"):
        for bar in dr.BARS:
            sel = [i for i, c in enumerate(cells) if (c["flavor"], c["bar"]) == (flavor, bar)]
            stats = []
            for r in runs:
                changed = inline = hits_new = hits_old = n = 0
                cost_new = cost_old = all_new = all_old = Fraction(0)
                for i in sel:
                    was = (cells[i]["mode"], cells[i]["model"])
                    pick = (new[r][i].mode, new[r][i].model)
                    old, now = held(cells[i], was), held(cells[i], pick)
                    all_new, all_old = all_new + now[2], all_old + old[2]
                    if pick != was:
                        changed += 1
                        inline += pick[0] == "inline"
                        by_point[cells[i]["point"]] += 1
                        hits_new, hits_old, n = hits_new + now[0], hits_old + old[0], n + old[1]
                        cost_new, cost_old = cost_new + now[2], cost_old + old[2]
                by_model[r][0] += changed
                by_model[r][1] += inline
                stats.append((changed, r, inline, f"{(hits_new - hits_old) / n:+.4f}" if changed else "-",
                              f"{float(cost_new / cost_old):.3f}" if changed else "-", f"{float(all_new / all_old):.3f}"))
            moving = sum(s[0] > 0 for s in stats)
            top = max(stats, key=lambda s: s[0])  # the first of the largest, in run order
            if top[0] == 0:
                top = (0, None, 0, "-", "-", "1.000")
            by_run = "-" if top[1] is None else f"{top[1][0]} times {top[1][1]}"
            lines.append(f"  {flavor:<14}  {bar:<3}  {moving:>6} / {len(runs):<3}  {top[0]:>12,} / {len(sel):<5,}  "
                         f"{100 * top[0] / len(sel):>4.1f}%  {top[2]:>9}  {top[3]:>11}  {top[4]:>10}  {top[5]:>14}  "
                         f"{by_run}")
    lines.append(f"  changed cells by point, all {len(runs)} runs: " + ", ".join(f"{i}: {n:,}" for i, n in enumerate(by_point)))
    for m in models:
        (a, ai), (b, bi) = by_model[m, 0.5], by_model[m, 2.0]
        lines.append(f"  {m}: times 0.5 changes {a:,} cells ({ai:,} to inline), times 2.0 changes {b:,} ({bi:,} to inline)")
    return lines


@pytest.fixture(scope="module")
def hand(ps, dr, tmp_path_factory):
    rows, registry = _rows(), Registry([P, D, E])
    root, matrix, pool = _root(tmp_path_factory.mktemp("hand"), dr, rows, registry)
    code, out, err = _main(ps, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    return rows, registry, root, matrix, pool, code, out, err


def test_report_on_a_hand_matrix_is_the_brute_force(dr, hand):
    rows, registry, _, _, _, code, out, err = hand
    assert (code, err) == (0, "")
    want = [TITLE] + _expected(rows, registry, dr, "base", "results.json") + _expected(rows, registry, dr, "variants",
                                                                                      "variants.json")
    assert out.split("\n") == want + [""]


def test_the_hand_matrix_moves_cells_both_ways_and_no_cost_blind_cell(hand):
    out = hand[6].split("\n")
    table = _table("\n".join(out))
    effective = [v for k, v in table.items() if k[1] == "cost_effective"]
    assert all(v["moving"] > 0 for v in effective)
    assert all(v["most"] == 0 and v["by"] is None for k, v in table.items() if k[1] == "cost_blind")
    base = [line for line in out[1:out.index(next(x for x in out if x.startswith("AutoBench 2026, variants")))]]
    changes = {m: (int(a), int(ai), int(b), int(bi)) for m, a, ai, b, bi in
               (re.match(MODEL_LINE, x).groups() for x in base if re.match(MODEL_LINE, x))}
    # the delegates' errors move work between delegates; the parent's moves it between the paths
    assert changes["v/d"][0] > 0 and changes["v/e"][2] > 0 and changes["v/d"][1] == changes["v/e"][3] == 0
    assert changes["v/p"][1] + changes["v/p"][3] > 0


def test_scaled_changes_one_models_prices_only(ps):
    registry = Registry([P, D, dataclasses.replace(E, aliases={"x": "e"}, price_valid_until="2026-12-01")])
    for factor in FACTORS:
        got = ps.scaled(registry, "v/e", factor)
        assert [m.id for m in got.models] == ["v/p", "v/d", "v/e"]
        assert got.get("v/p") == P and got.get("v/d") == D
        assert got.get("v/e") == dataclasses.replace(registry.get("v/e"), price_in=0.8 * factor, price_out=0.8 * factor)


def test_exits_2_where_the_reread_check_does(ps, dr, tmp_path):
    root, matrix, pool = _root(tmp_path, dr, _rows(), Registry([P, D, E]))
    path = root / "evidence" / "delegation" / "variants.json"
    data = json.loads(path.read_text(encoding="utf-8"))
    data["summary"][0]["cost_usd"] *= 2
    path.write_text(json.dumps(data), encoding="utf-8")
    code, out, err = _main(ps, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    assert (code, out, err) == (2, "", "error: evidence/delegation/variants.json: the run's summary is not the committed one\n")
    code, out, err = _main(ps, ["--matrix", str(tmp_path / "none.jsonl"), "--registry", str(pool), "--root", str(root)])
    assert (code, out, err) == (2, "", f"error: {tmp_path / 'none.jsonl'}: no such file\n")


def test_script_is_standard_library_and_model_routing():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^\s*(?:from|import) (\S+)", text, flags=re.M)}
    assert imports == {"argparse", "dataclasses", "importlib", "sys", "math", "pathlib", "model_routing"}
    assert '"reread_sensitivity.py"' in text


# --- the note --------------------------------------------------------------------------------
TABLE_LINE = (r"  (cost_\w+) +(0\.\d) +(\d+) / (\d+) +([\d,]+) / ([\d,]+) +([\d.]+)% +([\d,]+) +(\S+) +(\S+) +(\S+)  "
              r"(-|\S+ times (?:0\.5|2\.0))$")
MODEL_LINE = r"  (\S+): times 0\.5 changes ([\d,]+) cells \(([\d,]+) to inline\), times 2\.0 changes ([\d,]+) \(([\d,]+) to inline\)$"
GRID_LINE = (r"AutoBench 2026, (base|variants) grid \(`evidence/delegation/\w+\.json`\): ([\d,]+) cells, (\d+) bars, "
             r"(\d+) flavors, (\d+) points, (\d+) parents, (\d+) seeds, (\d+) models, so (\d+) runs; ")


def _section(note, name):
    return note.split(f"\n## {name}\n", 1)[1].split("\n## ", 1)[0]


def _prose(note):
    return re.sub(r"```.*?```", "", note, flags=re.S)


def _block(note):
    return note.split(COMMAND + "\n", 1)[1].split("\n```", 1)[0]


def _table(block):
    """{(grid, flavor, bar): the row's values}, the grid as the header line names it."""
    rows, grid = {}, None
    for line in block.split("\n"):
        found = re.match(GRID_LINE, line)
        if found:
            grid = found.group(1)
        found = re.match(TABLE_LINE, line)
        if found:
            f, bar, moving, runs, most, cells, share, inline, gap, ratio, whole, by = found.groups()
            rows[grid, f, bar] = {"moving": int(moving), "runs": int(runs), "most": most, "cells": cells,
                                  "share": share, "inline": int(inline.replace(",", "")), "gap": gap, "ratio": ratio,
                                  "all": whole, "by": None if by == "-" else by.rsplit(" times ", 1)}
            rows[grid, f, bar]["most"] = int(most.replace(",", ""))
            rows[grid, f, bar]["most_text"] = most
    return rows


def _grids(block):
    """{grid: (header values, {model: (halved, halved to inline, doubled, doubled to inline)})}."""
    out, grid = {}, None
    for line in block.split("\n"):
        found = re.match(GRID_LINE, line)
        if found:
            grid = found.group(1)
            out[grid] = (found.groups()[1:], {})
        found = re.match(MODEL_LINE, line)
        if found:
            out[grid][1][found.group(1)] = tuple(int(x.replace(",", "")) for x in found.groups()[1:])
    return out


def _verb(factor):
    return {"0.5": "halving", "2.0": "doubling"}[factor]


def _inline(n):
    return "none to inline" if n == 0 else f"{n:,} of them to inline"


def facts(note):
    """The Facts bullets that hold numbers, built from the note's Results block."""
    block = _block(note)
    table, grids = _table(block), _grids(block)
    assert set(grids) == {"base", "variants"} and len(table) == 8
    # no run moves a cost_blind cell, on either grid or bar
    assert all(v["moving"] == 0 and v["most"] == 0 for k, v in table.items() if k[1] == "cost_blind")
    (cells, bars, flavors, points, parents, seeds, models, runs), _ = grids["base"]
    (v_cells, _b, _f, v_points, _p, _s, v_models, v_runs), _ = grids["variants"]
    assert (models, runs) == (v_models, v_runs) and int(runs) == 2 * int(models)
    out = [f"- Data: the AutoBench 2026 matrix and pool that evidence/delegation/results.py runs, its base grid "
           f"({cells} cells: {bars} bars, {flavors} flavors, {points} points, {parents} parents, {seeds} seeds) and its "
           f"variant grid ({v_cells} cells, {v_points} points), with the {models} models of the pool, each model's "
           f"input and output prices times 0.5 and times 2.0 in turn, so {runs} runs per grid; every cell's decision "
           "and held-out sum is reproduced at the committed prices before any price is scaled"]
    for grid, name in (("base", "Base grid"), ("variants", "Variant grid")):
        parts = []
        for bar in ("0.7", "0.8"):
            v = table[grid, "cost_effective", bar]
            model, factor = v["by"]
            parts.append(f"at bar {bar} {v['moving']} of the {v['runs']} runs move a cell, and the most, "
                         f"{_verb(factor)} `{model}`'s prices, moves {v['most_text']} of {v['cells']} cells "
                         f"({v['share']}%), {_inline(v['inline'])}, for a held-out success gap of {v['gap']} at "
                         f"{v['ratio']} times their cost and {v['all']} times the cost over all the bar's cells")
        out.append(f"- {name}, `cost_effective`: " + "; ".join(parts))
    by_model = grids["base"][1]
    moved = [m for m, c in by_model.items() if c[0] or c[2]]
    v_moved = [m for m, c in grids["variants"][1].items() if c[0] or c[2]]
    totals = sorted(((c[i], m, f) for m, c in by_model.items() for i, f in ((0, "0.5"), (2, "2.0"))),
                    key=lambda x: (-x[0], x[1], x[2]))
    inline = sum(c[1] + c[3] for c in by_model.values())
    changed = sum(c[0] + c[2] for c in by_model.values())
    v_inline = sum(c[1] + c[3] for c in grids["variants"][1].values())
    v_changed = sum(c[0] + c[2] for c in grids["variants"][1].values())
    out.append(f"- By model: {len(moved)} of the {models} models move a base-grid cell at one factor or the other "
               f"and {int(models) - len(moved)} move none at either; on the variant grid {len(v_moved)} move a cell. "
               f"Over every flavor and bar of the base grid the runs that move the most are {_verb(totals[0][2])} "
               f"`{totals[0][1]}`'s prices ({totals[0][0]:,} cells) and {_verb(totals[1][2])} `{totals[1][1]}`'s "
               f"({totals[1][0]:,})")
    out.append(f"- Of the {changed:,} cells the base grid's runs change, {inline:,} go inline; of the variant grid's "
               f"{v_changed:,}, {v_inline:,}; the rest go to another delegate")
    return out


def test_note_has_its_sections_command_and_regenerate():
    note = NOTE.read_text(encoding="utf-8")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == SECTIONS
    assert _section(note, "Results").count("```text\n" + COMMAND + "\n") == 1
    assert "```bash\n" + "\n".join(REGENERATE) + "\n```" in _section(note, "Regenerate")
    for link in ("../evidence/delegation/RESULTS.md", "price-sensitivity.md", "reread-sensitivity.md",
                 "delegation_price_sensitivity.py"):
        assert f"]({link})" in note, link


def test_facts_states_the_finding_before_any_number():
    first = _section(NOTE.read_text(encoding="utf-8"), "Facts").strip().split("\n")[0]
    assert first.startswith("- ") and NUMBER.findall(first) == [], first


def test_the_facts_bullets_are_built_from_the_block():
    note = NOTE.read_text(encoding="utf-8")
    bullets = _section(note, "Facts").strip().split("\n")
    for bullet in facts(note):
        assert bullet in bullets, bullet


def test_every_number_of_the_prose_is_in_a_built_bullet_or_allowed():
    """Outside the built bullets the prose holds no result: only DESIGN section numbers, the exit status, and the
    block's parameters (its title's dataset year and factors, and its bars); a code span is a name, not a number."""
    note = NOTE.read_text(encoding="utf-8")
    block = _block(note)
    parameters = set(NUMBER.findall(block.split("\n", 1)[0])) | {k[2] for k in _table(block)}
    assert parameters == {"2026", "0.5", "2.0", "0.7", "0.8"}
    prose = _prose(note)
    for bullet in facts(note):
        assert prose.count(bullet) == 1, bullet
        prose = prose.replace(bullet, "")
    prose = re.sub(r"`[^`]*`", "", prose)
    assert sorted({n for n in NUMBER.findall(prose) if n not in ALLOWED | parameters | {"2"}}) == []
    assert re.findall(r"(?<![\w.])2(?![\w.])", prose) == ["2"] and "the script exits 2" in prose


def test_the_note_says_no_cost_blind_cell_moves_and_how_picks_are_scored():
    note = NOTE.read_text(encoding="utf-8")
    assert "- No run moves a `cost_blind` cell, on either grid or bar" in _section(note, "Facts")
    method = _section(note, "Method")
    for phrase in ("`price_in` and `price_out`", "committed prices", "`_router`", "`checked`"):
        assert phrase in method, phrase


def test_the_research_index_lists_the_note():
    index = INDEX.read_text(encoding="utf-8")
    assert index.count("| [delegation-price-sensitivity.md](delegation-price-sensitivity.md) | ") == 1
    assert index.count("- `research/delegation-price-sensitivity.md` ") == 1


def test_the_design_bullet_is_in_12_22():
    text = DESIGN.read_text(encoding="utf-8")
    section = text.split("\n### 12.22 ", 1)[1].split("\n## 13. ", 1)[0]
    bullet = [line for line in section.splitlines() if line.startswith(BULLET)]
    assert len(bullet) == 1
    for phrase in ("`research/delegation-price-sensitivity.md`", "`research/delegation_price_sensitivity.py`",
                   "`research/reread_sensitivity.py`, loaded from its own folder by path", "`inputs` and `checked`",
                   "exit 2", "at the committed prices", "0.5 and 2.0", "`price_in` and `price_out` times the factor",
                   "committed 13.2 costs", "tests/test_research_delegation_price_sensitivity.py", "`## Results` block"):
        assert phrase in bullet[0], phrase
    # the last bullet of 12.22, after the re-read bullet
    lines = section.rstrip("\n").split("\n")
    assert lines[-1] == bullet[0] and lines[-2].startswith("- The re-read share and the brief's output, ")


@pytest.fixture(scope="module")
def output(ps, tmp_path_factory):
    cv = _load("research_delegation_price_autobench_convert", ROOT / "evidence" / "autobench-2026" / "convert.py")
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("pinned AutoBench files are not in the default cache")
    for name, (size, sha) in cv.FILES.items():
        cv.verify(folder / name, size, sha)
    params = json.loads((folder / "frozen_params.json").read_text(encoding="utf-8"))
    pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
    rows, _report = cv.convert(cv.read_csv(folder / "matrix.csv"), cv.read_csv(folder / "questions.csv"),
                               pool, params["delta_signal"], params["top_k"], task_by="all", tokens=True)
    tmp = tmp_path_factory.mktemp("pinned")
    matrix = tmp / "autobench-tokens.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    registry = tmp / "autobench-pool.json"
    registry.write_text(json.dumps(cv.pool_registry(pool)), encoding="utf-8")
    return ps.run(matrix, registry, ROOT)


def test_note_results_block_is_the_script_output(output):
    assert _block(NOTE.read_text(encoding="utf-8")).split("\n") == output
