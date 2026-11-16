"""research/reread-sensitivity.md and research/reread_sensitivity.py (DESIGN 12.22 v1.413, row R38).

The script's item costs are checked against costs worked by hand at sigma 0.5 and W = 2 B; its report
on a hand-built AutoBench-shaped matrix, run end to end through `main` against a root whose committed
13.10 files are that matrix's, against a brute force that rebuilds each cell's router from the public
API and prices each held-out item in exact fractions; its exits on a summary that is not the committed
one, a re-decided cell or a held-out sum that is not the run's, a tiered model and per-call rows. The
note's results block is the script's output on the pinned AutoBench files, compared byte for byte when
they are cached, which CI never does; every number of the note's prose is in that block.
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
SCRIPT = ROOT / "research" / "reread_sensitivity.py"
NOTE = ROOT / "research" / "reread-sensitivity.md"
INDEX = ROOT / "research" / "README.md"
DESIGN = ROOT / "DESIGN.md"
FOLDER = ROOT / "evidence" / "delegation"
COMMAND = ("$ python research/reread_sensitivity.py --matrix autobench-tokens.jsonl"
           " --registry autobench-pool.json")
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/autobench-2026/convert.py --out autobench-tokens.jsonl --task-by all --tokens"
    " --registry autobench-pool.json",
    COMMAND[2:],
]
SECTIONS = ["Facts", "Method", "Results", "Reading it", "Recommendation", "Limits", "Regenerate"]
BULLET = "- The re-read share and the brief's output, on AutoBench (v1.413, row R38): "
# DESIGN section numbers: the only numbers of the note's prose not in the script's lines
ALLOWED = {"12.22", "13.1", "13.2", "13.5", "13.9", "13.10"}
NUMBER = re.compile(r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
SETTINGS = (("sigma 0", 0.0, 1), ("sigma 0.5", 0.5, 1), ("W = 2 B", 1.0, 2))

# Parent v/p at 1 and 2 USD per million input and output tokens, delegate v/d at 1 and 1. At the
# folded base point 3 (C = 8,000, B = R = 500, T = 1, K = 1) inline costs P(S_in, S_out) +
# P(S_in + sigma * S_out, 0) = 2 * 100 + (2 + sigma) * S_out and delegating P(0, W) + D(500 + 100,
# 100) + 2 * P(1,000, 0) = 2 W + 2,700, so with v/p's outputs about 1,400 the parent's pick moves
# from delegate to inline as sigma falls to 0 or W doubles, and sits at a tie near sigma 0.5.
P = Model("v/p", "fam-p", 1.0, 2.0, 1_000_000)
D = Model("v/d", "fam-d", 1.0, 1.0, 1_000_000)


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rs():
    return _load("research_reread_sensitivity", SCRIPT)


@pytest.fixture(scope="module")
def dr():
    return _load("research_reread_results", FOLDER / "results.py")


def _rows():
    rows = []
    for j in range(80):
        rows.append({"task": "t", "item": f"i{j:02d}", "model": "v/p", "correct": j % 10 != 0,
                     "input_tokens": 100, "output_tokens": 1200 + 40 * (j % 11)})
        rows.append({"task": "t", "item": f"i{j:02d}", "model": "v/d", "correct": j % 20 != 0,
                     "input_tokens": 100, "output_tokens": 100})
    return rows


def _registry_file(path, models):
    entries = [dict(dataclasses.asdict(m), source="https://example.org/prices") for m in models]
    for e in entries:
        if not e["price_tiers"]:
            del e["price_tiers"]
    path.write_text(json.dumps({"version": "1", "as_of": "2026-01-01", "currency": "USD",
                                "models": entries}), encoding="utf-8")
    return path


def _root(tmp_path, dr, rows, registry):
    folder = tmp_path / "root" / "evidence" / "delegation"
    folder.mkdir(parents=True)
    (folder / "results.py").write_text((FOLDER / "results.py").read_text(encoding="utf-8"), encoding="utf-8")
    for name, grid in (("results.json", "base"), ("variants.json", "variants")):
        (folder / name).write_text(json.dumps(dr.run(rows, registry, grid), indent=2) + "\n", encoding="utf-8")
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return tmp_path / "root", matrix, _registry_file(tmp_path / "pool.json", registry.models)


def _main(rs, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = rs.main(argv)
    return code, out.getvalue(), err.getvalue()


# --- the item costs, worked by hand ----------------------------------------------------------
# K = 2, C = 100, B = 10, R = 20, T = 1, S_in = 30, S_out = 40, sigma = 0.5, W = 20, so w_in = 3,
# w_out = 1 and each work call's re-read of the earlier output is 0.5 * 40 = 20 tokens:
#   delegate         = P(0, 20) + D(2 * 10 + 3 * 30 + 20, 2 * 40) + 2 * P(30, 0) = 40 + 210 + 60 = 310
#   inline, separate = P(2 * 100 + 90 + 20, 80) + 2 * P(2 * (30 + 20), 0) = 470 + 200 = 670
#   inline, folded   = P(100 + 90 + 20, 80) + 1 * P(100, 0) = 370 + 100 = 470
#   separate, rho 0.5 = P(100 + 90 + 20, 80) + 2 * P(100, 0) = 370 + 200 = 570
# each in millionths of a USD.
HAND = {"context_tokens": 100, "brief_tokens": 10, "result_tokens": 20, "carry_turns": 1,
        "inline_separate_call": True, "work_calls": 2}


@pytest.mark.parametrize("path, point, want", [
    ("delegate", HAND, 310),
    ("inline", HAND, 670),
    ("inline", dict(HAND, inline_separate_call=False), 470),
    ("inline", dict(HAND, cached_read_ratio=0.5), 570),
])
def test_item_cost_by_hand(rs, path, point, want):
    assert rs.item_cost(P, D, point, path, 30, 40, 0.5, 20) == pytest.approx(want / 1e6, rel=1e-12)


# --- the brute force -------------------------------------------------------------------------
def _cost(m, i, o):
    return (Fraction(i) * Fraction(m.price_in) + Fraction(o) * Fraction(m.price_out)) / 1_000_000


def _exact(p, d, point, path, tin, tout, sigma, w):
    """13.2 at sigma and W in fractions, written apart from the script's float expression."""
    c, b, r, t = (point[k] for k in ("context_tokens", "brief_tokens", "result_tokens", "carry_turns"))
    k, s = point.get("work_calls", 1), Fraction(sigma)
    reread = Fraction(k * (k - 1) // 2) * s * tout
    if path == "delegate":
        return _cost(p, 0, w) + _cost(d, k * b + k * (k + 1) // 2 * tin + reread, k * tout) + (1 + t) * _cost(p, b + r, 0)
    separate = point["inline_separate_call"]
    reads = Fraction(k * c if separate else (k - 1) * c) * Fraction(point.get("cached_read_ratio", 1))
    work = _cost(p, reads + k * (k + 1) // 2 * tin + reread, k * tout)
    return work + ((1 + t) if separate else t) * _cost(p, k * (tin + s * tout), 0)


def _expected(rows, registry, dr, grid, name):
    """The report lines of one committed file, by a router rebuilt from the public API per cell."""
    points = dr.points() if grid == "base" else dr.variant_points()
    full = evaluate_delegation(rows, registry, bars=list(dr.BARS), points=points, seeds=range(dr.SEEDS))
    by = {(r["item"], r["model"]): r for r in rows}
    items = list(dict.fromkeys(r["item"] for r in rows))
    models = sorted({r["model"] for r in rows})
    halves = {seed: split_items(items, seed, 0.5) for seed in range(dr.SEEDS)}

    def decide(cell, point, sigma, w):
        cal = halves[cell["seed"]][0]
        stats = Stats()
        for m in models:
            stats.add("t", m, sum(by[i, m]["correct"] for i in cal), len(cal),
                      input_tokens=sum(by[i, m]["input_tokens"] for i in cal),
                      output_tokens=sum(by[i, m]["output_tokens"] for i in cal))
        task = Task(name="t", bar=cell["bar"], min_samples=30, confidence=0.95, independent_of_generator=False,
                    expected_input_tokens=statistics.median_low([by[i, m]["input_tokens"] for i in cal for m in models]),
                    expected_output_tokens=statistics.median_low([by[i, m]["output_tokens"] for i in cal for m in models]),
                    on_no_model="best_available", max_fallbacks=0)
        got = Router(registry, {"t": task}, stats).decide_delegation(
            "t", cell["parent"], cell["flavor"], **point, output_reread_share=sigma, brief_output_tokens=w)
        return got.mode, got.model

    def held(cell, point, pick, sigma, w):
        p, d = registry.get(cell["parent"]), registry.get(pick[1])
        hits = [by[i, pick[1]] for i in halves[cell["seed"]][1]]
        return (sum(h["correct"] for h in hits), len(hits),
                sum(_exact(p, d, point, pick[0], h["input_tokens"], h["output_tokens"], sigma, w) for h in hits))

    cells = full["cells"]
    for cell in cells:
        point = points[cell["point"]]
        assert decide(cell, point, 1.0, point["brief_tokens"]) == (cell["mode"], cell["model"])
    lines = [f"AutoBench 2026, {grid} grid (`evidence/delegation/{name}`): {len(cells):,} cells, 2 bars, 2 flavors, "
             f"{len(points)} points, 2 parents, 50 seeds; every cell's decision and held-out sum reproduced at sigma 1.0 "
             "and W = B",
             "  flavor          bar  setting    changed / cells  share  to inline  success gap  cost ratio  all cost ratio"]
    by_point = {label: [0] * len(points) for label, _, _ in SETTINGS}
    why = {label: [] for label, _, _ in SETTINGS}
    for flavor in ("cost_effective", "cost_blind"):
        for bar in dr.BARS:
            sel = [c for c in cells if (c["flavor"], c["bar"]) == (flavor, bar)]
            for label, sigma, factor in SETTINGS:
                changed = inline = new_hits = old_hits = n = 0
                new_cost = old_cost = all_new = all_old = Fraction(0)
                for cell in sel:
                    point = points[cell["point"]]
                    w = factor * point["brief_tokens"]
                    was = (cell["mode"], cell["model"])
                    pick = decide(cell, point, sigma, w)
                    old, new = held(cell, point, was, sigma, w), held(cell, point, pick, sigma, w)
                    all_new, all_old = all_new + new[2], all_old + old[2]
                    if pick != was:
                        changed += 1
                        inline += pick[0] == "inline"
                        by_point[label][cell["point"]] += 1
                        why[label].append((cell["reason"], cell["seed"], cell["parent"]))
                        new_hits, old_hits, n = new_hits + new[0], old_hits + old[0], n + old[1]
                        new_cost, old_cost = new_cost + new[2], old_cost + old[2]
                gap = f"{(new_hits - old_hits) / n:+.4f}" if changed else "-"
                ratio = f"{float(new_cost / old_cost):.3f}" if changed else "-"
                lines.append(f"  {flavor:<14}  {bar:<3}  {label:<9}  {changed:>7} / {len(sel):<5,}  "
                             f"{100 * changed / len(sel):>4.1f}%  {inline:>9}  {gap:>11}  {ratio:>10}  "
                             f"{float(all_new / all_old):>14.3f}")
    for label, _, _ in SETTINGS:
        lines.append(f"  changed cells by point, {label}: " + ", ".join(f"{i}: {n}" for i, n in enumerate(by_point[label])))
    for label, _, _ in SETTINGS:
        changed = why[label]
        if not changed:
            lines.append(f"  changed cells by reason, {label}: none")
            continue
        reasons = {r: sum(x[0] == r for x in changed) for r in {x[0] for x in changed}}
        parents = {p: sum(x[2] == p for x in changed) for p in {x[2] for x in changed}}
        top = min(parents, key=lambda p: (-parents[p], p))
        seeds = len({x[1] for x in changed})
        lines.append(f"  changed cells by reason, {label}: "
                     + ", ".join(f"{r} {reasons[r]}" for r in sorted(reasons, key=lambda r: (-reasons[r], r)))
                     + f"; {seeds} seed{'s' * (seeds != 1)}, {len(parents)} parent{'s' * (len(parents) != 1)}, "
                     f"the most {parents[top]} of {top}")
    return lines


@pytest.fixture(scope="module")
def hand(rs, dr, tmp_path_factory):
    rows, registry = _rows(), Registry([P, D])
    root, matrix, pool = _root(tmp_path_factory.mktemp("hand"), dr, rows, registry)
    code, out, err = _main(rs, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    return rows, registry, root, matrix, pool, code, out, err


def test_report_on_a_hand_matrix_is_the_brute_force(rs, dr, hand):
    rows, registry, _, _, _, code, out, err = hand
    assert (code, err) == (0, "")
    want = ["The re-read share and the brief's output on the AutoBench 2026 delegation results: each cell "
            "re-decided at sigma 0, sigma 0.5 and W = 2 B, both picks scored at that setting's costs"]
    want += _expected(rows, registry, dr, "base", "results.json")
    want += _expected(rows, registry, dr, "variants", "variants.json")
    assert out.split("\n") == want + [""]


def test_the_hand_matrix_moves_a_decision_at_each_setting(hand):
    out = hand[6]
    for label in ("sigma 0", "sigma 0.5", "W = 2 B"):
        line = next(x for x in out.split("\n") if x.startswith(f"  changed cells by point, {label}: "))
        counts = [int(x.split(": ")[1]) for x in line.split(": ", 1)[1].split(", ")]
        assert counts[3] > 0 and counts[:3] == [0, 0, 0], line


def _edited(tmp_path, root, name, edit):
    path = root / "evidence" / "delegation" / name
    data = json.loads(path.read_text(encoding="utf-8"))
    edit(data)
    path.write_text(json.dumps(data), encoding="utf-8")


def test_exits_2_when_a_summary_is_not_the_committed_one(rs, dr, tmp_path):
    root, matrix, pool = _root(tmp_path, dr, _rows(), Registry([P, D]))
    _edited(tmp_path, root, "variants.json", lambda d: d["summary"][0].update(cost_usd=d["summary"][0]["cost_usd"] * 2))
    code, out, err = _main(rs, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    assert (code, out) == (2, "")
    assert err == "error: evidence/delegation/variants.json: the run's summary is not the committed one\n"


def test_exits_2_when_a_cell_re_decided_at_the_defaults_moves(rs, hand, monkeypatch):
    _, _, root, matrix, pool, *_ = hand
    real = rs.Run.decide
    monkeypatch.setattr(rs.Run, "decide", lambda self, cell, point, sigma, w: (
        ("inline", cell["parent"]) if cell["point"] == 1 and cell["seed"] == 3 else real(self, cell, point, sigma, w)))
    code, out, err = _main(rs, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    assert (code, out) == (2, "")
    assert err == ("error: evidence/delegation/results.json: a cell re-decided at sigma 1.0 and W = B is not "
                   "the run's: cost_effective, bar 0.7, point 1, parent v/d, seed 3\n")


def test_exits_2_when_a_held_out_sum_at_the_defaults_moves(rs, hand, monkeypatch):
    _, _, root, matrix, pool, *_ = hand
    real = rs.item_cost
    monkeypatch.setattr(rs, "item_cost", lambda *a: real(*a) * (1 + 1e-9))
    code, out, err = _main(rs, ["--matrix", str(matrix), "--registry", str(pool), "--root", str(root)])
    assert (code, out) == (2, "")
    assert err.startswith("error: evidence/delegation/results.json: a held-out sum at sigma 1.0 and W = B is not "
                          "the run's: ") and err.count("\n") == 1


def test_refusals(rs, dr, tmp_path):
    rows = _rows()
    root, matrix, pool = _root(tmp_path, dr, rows, Registry([P, D]))
    tiered = json.loads(pool.read_text(encoding="utf-8"))
    tiered["models"][1]["price_tiers"] = [{"above_input_tokens": 500_000, "price_in": 2.0, "price_out": 4.0}]
    (tmp_path / "tiered.json").write_text(json.dumps(tiered), encoding="utf-8")
    calls = tmp_path / "calls.jsonl"
    calls.write_text("".join(json.dumps(dict(r, call_input_tokens=[r["input_tokens"]],
                                             call_output_tokens=[r["output_tokens"]])) + "\n" for r in rows),
                     encoding="utf-8")
    for argv, want in [
        (["--matrix", str(tmp_path / "none.jsonl"), "--registry", str(pool)], f"error: {tmp_path / 'none.jsonl'}: no such file\n"),
        (["--matrix", str(matrix), "--registry", str(tmp_path / "tiered.json")], "error: model 'v/d' has price tiers, which are not priced here\n"),
        (["--matrix", str(calls), "--registry", str(pool)], "error: task 't': rows with per-call sizes are not priced here\n"),
    ]:
        code, out, err = _main(rs, argv + ["--root", str(root)])
        assert (code, out, err) == (2, "", want), argv


def test_script_is_standard_library_and_model_routing():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^\s*(?:from|import) (\S+)", text, flags=re.M)}
    assert imports == {"argparse", "collections", "importlib", "json", "sys", "math", "pathlib", "model_routing"}


# --- the note --------------------------------------------------------------------------------
def _section(note, name):
    return note.split(f"\n## {name}\n", 1)[1].split("\n## ", 1)[0]


def _prose(note):
    return re.sub(r"```.*?```", "", note, flags=re.S)


def test_note_has_its_sections_command_and_regenerate():
    note = NOTE.read_text(encoding="utf-8")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == SECTIONS
    results = _section(note, "Results")
    assert results.count("```text\n" + COMMAND + "\n") == 1
    regenerate = _section(note, "Regenerate")
    assert "```bash\n" + "\n".join(REGENERATE) + "\n```" in regenerate
    for link in ("../evidence/delegation/RESULTS.md", "ledger-cost-model.md"):
        assert f"]({link})" in note, link


def test_facts_states_the_finding_before_any_number():
    first = _section(NOTE.read_text(encoding="utf-8"), "Facts").strip().split("\n")[0]
    assert first.startswith("- ") and NUMBER.findall(first) == [], first


def test_every_number_of_the_prose_is_in_the_output_or_allowed():
    note = NOTE.read_text(encoding="utf-8")
    block = note.split(COMMAND + "\n", 1)[1].split("\n```", 1)[0]
    printed = set(NUMBER.findall(block))
    assert sorted({n for n in NUMBER.findall(_prose(note)) if n not in printed and n not in ALLOWED}) == []


def _table(block):
    """{(grid, flavor, bar, setting): (changed, cells, to inline, all cost ratio)} and the by-point lines."""
    rows, points, grid = {}, {}, None
    for line in block.split("\n"):
        if line.startswith("AutoBench 2026, "):
            grid = line.split(", ", 2)[1].split(" ")[0]
        found = re.match(r"  (cost_\w+) +(0\.\d) +(sigma 0\.5|sigma 0|W = 2 B) +(\d+) / ([\d,]+) +[\d.]+% +(\d+) .* ([\d.]+)$", line)
        if found:
            f, bar, label, changed, cells, inline, ratio = found.groups()
            rows[grid, f, bar, label] = (int(changed), int(cells.replace(",", "")), int(inline), float(ratio))
        found = re.match(r"  changed cells by point, (.+?): (.+)$", line)
        if found:
            points[grid, found.group(1)] = [int(x.split(": ")[1]) for x in found.group(2).split(", ")]
    return rows, points


def test_the_facts_claims_hold_in_the_block():
    note = NOTE.read_text(encoding="utf-8")
    rows, points = _table(note.split(COMMAND + "\n", 1)[1].split("\n```", 1)[0])
    assert len(rows) == 24 and len(points) == 6
    # no cost_blind cell moves; every base-grid change is to inline and at point 3; no variant change is
    # to inline, W = 2 B changes no variant cell, and every variant change is at variant point 2
    assert all(v[0] == 0 for k, v in rows.items() if k[1] == "cost_blind")
    assert all(v[2] == v[0] for k, v in rows.items() if k[0] == "base")
    assert all(p[:3] == [0, 0, 0] for (g, _), p in points.items() if g == "base")
    assert all(v[2] == 0 for k, v in rows.items() if k[0] == "variants")
    assert all(v[0] == 0 for k, v in rows.items() if k[0] == "variants" and k[3] == "W = 2 B")
    assert all(p[:2] == [0, 0] for (g, _), p in points.items() if g == "variants")
    # the Recommendation's bounds: at most 0.7% of a file, flavor and bar's cells, all-cells ratio 1.000 to 1.003
    assert max(round(100 * v[0] / v[1], 1) for v in rows.values()) == 0.7
    assert (min(v[3] for v in rows.values()), max(v[3] for v in rows.values())) == (1.0, 1.003)
    rec = _section(note, "Recommendation")
    assert "more than 0.7% of the cells" in rec and "at most 1.003" in rec


def test_the_note_says_from_13_2_which_terms_sigma_scales():
    method = _section(NOTE.read_text(encoding="utf-8"), "Method")
    for phrase in ("`w_out * sigma * S_out`", "`K * (S_in + sigma * S_out)`", "`P.cost(0, W)`"):
        assert phrase in method, phrase


def test_the_research_index_lists_the_note():
    index = INDEX.read_text(encoding="utf-8")
    assert index.count("| [reread-sensitivity.md](reread-sensitivity.md) | ") == 1
    assert index.count("- `research/reread-sensitivity.md` ") == 1


def test_the_design_bullet_is_in_12_22():
    text = DESIGN.read_text(encoding="utf-8")
    section = text.split("\n### 12.22 ", 1)[1].split("\n## 13. ", 1)[0]
    bullet = [line for line in section.splitlines() if line.startswith(BULLET)]
    assert len(bullet) == 1
    for phrase in ("`research/reread-sensitivity.md`", "`research/reread_sensitivity.py`", "sigma 1.0 and W = B",
                   "sigma 0, sigma 0.5 and W = 2 B", "13.2 costs", "`## Results` block"):
        assert phrase in bullet[0], phrase


@pytest.fixture(scope="module")
def output(rs, tmp_path_factory):
    cv = _load("research_reread_autobench_convert", ROOT / "evidence" / "autobench-2026" / "convert.py")
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
    return rs.run(matrix, registry, ROOT)


def test_note_results_block_is_the_script_output(output):
    note = NOTE.read_text(encoding="utf-8")
    block = note.split(COMMAND + "\n", 1)[1].split("\n```", 1)[0]
    assert block.split("\n") == output
