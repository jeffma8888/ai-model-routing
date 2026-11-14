"""research/no-model-clears.md and research/no_model_clears.py (DESIGN 12.8 v1.144).

The note's numbers are the script's lines on the routing datasets that record a cost, compared
byte for byte when the pinned files and pandas are present (CI never downloads them). The script's
report, its check against the committed results file and its exits are tested on a small matrix.

DESIGN 12.8 v1.341 (row R32): the script also reads LLMRouterBench (12.19) and the LLM Routing
Response Bank (12.21), six datasets in all; the note gains a dated section on the two, and the
README Limitations bullet and the research index row list the script's `DATASETS` by name.
"""

import contextlib
import importlib.util
import io
import json
import math
import re
from pathlib import Path

import pytest

from model_routing import Registry, evaluate, load_outcomes, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "no_model_clears.py"
NOTE = ROOT / "research" / "no-model-clears.md"
INDEX = ROOT / "research" / "README.md"
README = ROOT / "README.md"
COMMAND = ("$ python research/no_model_clears.py --routerbench routerbench-matrix.jsonl "
           "--autobench autobench-matrix.jsonl --judges autobench-judges.jsonl "
           "--judges-registry autobench-models.json --tau2 tau2-matrix.jsonl "
           "--llmrouterbench llmrouterbench-matrix.jsonl --response-bank response-bank-matrix.jsonl")
REGENERATE = [
    'python -m pip install -e ".[evidence]"',
    "python evidence/routerbench/convert.py --out routerbench-matrix.jsonl",
    "python evidence/autobench-2026/convert.py --out autobench-matrix.jsonl --task-by all",
    "python evidence/autobench-2026/judges.py --out autobench-judges.jsonl --registry autobench-models.json",
    "python evidence/tau2-bench/convert.py --out tau2-matrix.jsonl",
    "python evidence/llmrouterbench/convert.py --out llmrouterbench-matrix.jsonl",
    "python evidence/response-bank/convert.py --out response-bank-matrix.jsonl",
    COMMAND[2:],
]
DATASETS = [("RouterBench", "evidence/routerbench/results.json"),
            ("AutoBench", "evidence/autobench-2026/results.json"),
            ("AutoBench judges", "evidence/autobench-judges/results.json"),
            ("tau2-bench", "evidence/tau2-bench/results.json"),
            ("LLMRouterBench", "evidence/llmrouterbench/results.json"),
            ("LLM Routing Response Bank", "evidence/response-bank/results.json")]
# DESIGN section and row numbers: the only numbers of the note's prose not in the script's lines
ALLOWED = {"5.3", "12.3", "12.7", "12.10", "12.12", "12.15", "12.19", "12.21", "13.5", "7"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?%?")
DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}\b")
SECTION = "LLMRouterBench and the response bank (2026-11-13)"
# v1.341: how the bullet and the index row name each dataset of the script's DATASETS
PROSE_NAME = {"AutoBench judges": "the AutoBench judges", "LLM Routing Response Bank": "the LLM Routing Response Bank"}
COUNT_WORD = {4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight"}
CONFIG = {"bars": [0.5, 0.75], "seeds": [0, 1, 2, 3], "flavors": ["cost_effective", "cost_blind"],
          "calibration_fraction": 0.5, "min_samples": 10, "confidence": 0.95}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def nmc():
    return _load("research_no_model_clears", SCRIPT)


def tiny_rows():
    """Two tasks, three models: `v/strong` clears 0.5 everywhere and `v/cheap` on `easy` only; nothing clears 0.75."""
    rows = []
    for task, n in (("easy", 200), ("hard", 160)):
        for i in range(n):
            for model, ok, cost in (("v/strong", i % 10 < 7, 0.03), ("v/mid", i % 10 < 6, 0.01),
                                    ("v/cheap", (i % 20 < 13) if task == "easy" else (i % 10 < 3), 0.001)):
                rows.append({"task": task, "item": f"{task}{i}", "model": model, "correct": ok,
                             "cost_usd": cost * (1 + i % 3)})
    return rows


def committed(rows):
    result = evaluate(outcomes_from_rows(rows), bars=CONFIG["bars"], seeds=CONFIG["seeds"])
    return {"config": result["config"], "summary": result["summary"]}


def whole(cells, seeds, pick):
    per_seed_success, per_seed_cost = [], []
    for seed in seeds:
        cs = [c for c in cells if c["seed"] == seed]
        correct = sum(round(c["success"][pick(c)] * c["held_out_items"]) for c in cs)
        per_seed_success.append(correct / sum(c["held_out_items"] for c in cs))
        per_seed_cost.append(math.fsum(c["cost_usd"][pick(c)] for c in cs))
    return math.fsum(per_seed_success) / len(seeds), math.fsum(per_seed_cost) / len(seeds)


def test_report_lines_on_a_small_matrix(nmc):
    rows = tiny_rows()
    outcomes = outcomes_from_rows(rows)
    lines = nmc.report("tiny", "evidence/tiny/results.json", outcomes, committed(rows))
    assert lines[0] == "tiny (evidence/tiny/results.json): 2 tasks, 3 models, bars 0.5, 0.75, 4 seeds"
    cells = [c for c in evaluate(outcomes, bars=CONFIG["bars"], seeds=CONFIG["seeds"],
                                 flavors=["cost_effective"])["cells"]]
    at = {bar: [c for c in cells if c["bar"] == bar] for bar in CONFIG["bars"]}
    out = iter(lines[1:])
    for bar in CONFIG["bars"]:
        mine = at[bar]
        none = [c for c in mine if not c["cleared"]]
        held = sum(c["held_out_items"] for c in none)
        by_task = ", ".join(f"{t} {sum(c['task'] == t for c in none)}" for t in ("easy", "hard"))
        head = (f"  bar {bar}: no model clears on {len(none):,} of {len(mine):,} cost_effective cells "
                f"({len(none) / len(mine):.1%})")
        if not none:
            assert next(out) == head
            continue
        assert next(out) == f"{head}, {held:,} held-out items; by task: {by_task}"
        boc = sum(c["models"]["routed"] == c["models"]["best_on_calibration"] for c in none)
        cheap = sum(c["models"]["routed"] == c["models"]["cheapest"] for c in none)
        assert next(out) == (f"    the routed model is best_on_calibration's on {boc:,} and the cheapest "
                             f"model's on {cheap:,}")
        for label, strategy in (("fallback", "routed"), ("cheapest", "cheapest"),
                                ("best_on_calibration", "best_on_calibration")):
            correct = sum(round(c["success"][strategy] * c["held_out_items"]) for c in none)
            cost = math.fsum(c["cost_usd"][strategy] for c in none)
            met = sum(c["success"][strategy] >= bar for c in none)
            assert next(out) == (f"    {label:<20} success {correct / held:.3f}  cost per item "
                                 f"{cost / held:.6f} USD  at the bar or above on {met:,} "
                                 f"({met / len(none):.1%})")
        s0, c0 = whole(mine, CONFIG["seeds"], lambda c: "routed")
        s1, c1 = whole(mine, CONFIG["seeds"], lambda c: "routed" if c["cleared"] else "cheapest")
        assert next(out) == (f"    whole row: routed success {s0:.3f} at {c0:.4f} USD; with the cheapest "
                             f"model as the fallback {s1:.3f} at {c1:.4f} USD (success {s1 - s0:+.3f}, "
                             f"cost {c1 / c0 - 1:+.1%})")
    assert next(out, None) is None
    assert any("no model clears on 0 of" in x for x in lines) and any("by task: easy" in x for x in lines)


def test_report_counts_tasks_when_there_are_more_than_five(nmc):
    rows = [dict(r, task=f"{r['task']}{k}", item=f"{r['item']}-{k}") for r in tiny_rows() for k in range(3)]
    lines = nmc.report("six", "evidence/six/results.json", outcomes_from_rows(rows), committed(rows))
    heads = [x for x in lines if x.startswith("  bar 0.75: ")]
    assert len(heads) == 1 and heads[0].endswith("; tasks with such a cell: 6 of 6")
    assert not any("by task:" in x for x in lines)


@pytest.mark.parametrize("key, delta", [("success", 1e-9), ("cost_usd", 1e-9)])
def test_report_stops_when_the_routed_row_is_not_the_committed_one(nmc, key, delta):
    rows = tiny_rows()
    record = committed(rows)
    for r in record["summary"]:
        if (r["bar"], r["flavor"], r["strategy"]) == (0.75, "cost_effective", "routed"):
            r[key] = r[key] * (1 + delta)
    with pytest.raises(ValueError, match="committed"):
        nmc.report("tiny", "evidence/tiny/results.json", outcomes_from_rows(rows), record)


# the script's matrix options in DATASETS order (v1.343, review iter-222 should-fix 1)
OPTIONS = ["--routerbench", "--autobench", "--judges", "--tau2", "--llmrouterbench", "--response-bank"]


def own_rows(rows, k):
    """Dataset k's own matrix: its own task names and every cost times k + 1, so a dataset that
    reads another's matrix gets another routed cost than its committed file's."""
    return [dict(r, task=f"{r['task']}-d{k}", cost_usd=r["cost_usd"] * (k + 1)) for r in rows]


def _tree(tmp_path, rows):
    argv = ["--root", str(tmp_path)]
    for k, ((_, rel), option) in enumerate(zip(DATASETS, OPTIONS)):
        mine = own_rows(rows, k)
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(committed(mine)), encoding="utf-8")
        matrix = tmp_path / f"m{k}.jsonl"
        matrix.write_text("".join(json.dumps(r) + "\n" for r in mine), encoding="utf-8")
        argv += [option, str(matrix)]
    registry = tmp_path / "models.json"
    registry.write_text(json.dumps({"models": [
        {"id": m, "family": m, "price_in": 1.0, "price_out": 2.0, "context_window": 100_000}
        for m in ("v/strong", "v/mid", "v/cheap")]}), encoding="utf-8")
    return argv + ["--judges-registry", str(registry)]


def _main(nmc, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = nmc.main(argv)
        except SystemExit as exc:  # argparse refusing an option
            code = exc.code
    return code, out.getvalue(), err.getvalue()


def test_script_datasets_are_the_six_in_order(nmc):
    assert [(name, rel) for name, rel, _ in nmc.DATASETS] == DATASETS
    assert ["--" + option.replace("_", "-") for _, _, option in nmc.DATASETS] == OPTIONS


def test_main_prints_the_six_reports_in_order(nmc, tmp_path):
    rows = tiny_rows()
    code, out, err = _main(nmc, _tree(tmp_path, rows))
    assert (code, err) == (0, "")
    outcomes = {name: outcomes_from_rows(own_rows(rows, k)) for k, (name, _) in enumerate(DATASETS)}
    blocks = [nmc.report(name, rel, outcomes[name], committed(own_rows(rows, k)))
              for k, (name, rel) in enumerate(DATASETS)]
    assert out == "\n\n".join("\n".join(b) for b in blocks) + "\n"
    assert out == "\n".join(nmc.run(outcomes, tmp_path)) + "\n"
    for k, (name, rel) in enumerate(DATASETS):
        assert f"{name} ({rel}): 2 tasks, 3 models" in out and f"by task: easy-d{k} " in out


@pytest.mark.parametrize("a, b", list(zip(OPTIONS, OPTIONS[1:])))
def test_main_reads_each_matrix_for_its_own_option(nmc, tmp_path, a, b):
    """Two options swapped: a dataset reads the other's matrix, whose routed cost is not its committed one."""
    argv = _tree(tmp_path, tiny_rows())
    i, j = argv.index(a) + 1, argv.index(b) + 1
    argv[i], argv[j] = argv[j], argv[i]
    code, out, err = _main(nmc, argv)
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.endswith("is not the committed one\n") and err.count("\n") == 1


@pytest.mark.parametrize("break_it", ["matrix", "results", "key", "row"])
def test_main_exits_2_with_one_error_line(nmc, tmp_path, break_it):
    rows = tiny_rows()
    argv = _tree(tmp_path, rows)
    if break_it == "matrix":
        argv[argv.index("--response-bank") + 1] = str(tmp_path / "missing.jsonl")
    elif break_it == "results":
        (tmp_path / DATASETS[4][1]).write_text("not json", encoding="utf-8")
    elif break_it == "key":
        (tmp_path / DATASETS[1][1]).write_text(json.dumps({"summary": []}), encoding="utf-8")
    else:
        (tmp_path / "m5.jsonl").write_text(json.dumps({"task": "t", "item": "i", "model": "m"}) + "\n",
                                           encoding="utf-8")
    code, out, err = _main(nmc, argv)
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1


def test_script_is_standard_library_and_model_routing():
    text = SCRIPT.read_text(encoding="utf-8")
    imports = {m.split(".")[0] for m in re.findall(r"^(?:from|import) ([\w.]+)", text, flags=re.M)}
    assert imports <= {"__future__", "argparse", "json", "math", "sys", "pathlib", "model_routing"}
    assert text.isascii()


def _blocks(text, lang):
    return re.findall(rf"^```{lang}\n(.*?)^```$", text, flags=re.M | re.S)


def test_note_quotes_its_commands_and_links():
    note = NOTE.read_text(encoding="utf-8")
    assert note.startswith("# When no model clears the bar\n")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == [
        "Facts", "Method", "Results", "Reading it", SECTION, "Recommendation", "Limits", "Regenerate"]
    assert _blocks(note, "bash") == ["\n".join(REGENERATE) + "\n"]
    [text] = _blocks(note, "text")
    assert text.startswith(COMMAND + "\n")
    assert note.isascii()
    for link in ("../DESIGN.md", "../evidence/routerbench/RESULTS.md", "../evidence/autobench-2026/RESULTS.md",
                 "../evidence/autobench-judges/RESULTS.md", "../evidence/tau2-bench/RESULTS.md",
                 "../evidence/llmrouterbench/RESULTS.md", "../evidence/response-bank/RESULTS.md",
                 "no_model_clears.py", "no-path-clears.md"):
        assert f"]({link})" in note, link


def test_every_number_of_the_prose_is_in_the_output_or_allowed():
    note = NOTE.read_text(encoding="utf-8")
    [text] = _blocks(note, "text")
    prose = re.sub(r"^```\w*\n.*?^```$", "", note, flags=re.M | re.S)
    prose = re.sub(r"\]\([^)]*\)|`[^`]*`", "", prose)
    prose = DATE.sub("", prose)
    printed = set(NUMBER.findall(text))
    assert sorted({n for n in NUMBER.findall(prose) if n not in printed and n not in ALLOWED}) == []


def test_readme_limitations_and_research_index_link_the_note():
    readme = README.read_text(encoding="utf-8")
    limits = readme[readme.index("## Limitations and non-goals (v1)\n"):readme.index("\n## Layout\n")]
    bullets = [x for x in limits.split("\n") if "(research/no-model-clears.md)" in x]
    assert len(bullets) == 1 and bullets[0].startswith("- When no model clears the bar")
    assert limits.index("\n- When neither path clears the bar") < limits.index("\n" + bullets[0])
    index = INDEX.read_text(encoding="utf-8")
    assert sum(x.startswith("| [no-model-clears.md](no-model-clears.md) | ") for x in index.split("\n")) == 1
    assert "[no_model_clears.py](no_model_clears.py)" in index
    assert sum(x.startswith("- `research/no-model-clears.md` ") for x in index.split("\n")) == 1


def _named(names):
    """The datasets in prose: `A, B and C`, a `the` before the two names that take one."""
    prose = [PROSE_NAME.get(n, n) for n in names]
    return ", ".join(prose[:-1]) + " and " + prose[-1]


def test_named_lists_the_names_in_order():
    assert _named(["X", "AutoBench judges", "Y"]) == "X, the AutoBench judges and Y"


def test_bullet_and_index_row_list_the_script_datasets(nmc):
    names = [name for name, _, _ in nmc.DATASETS]
    count, listed = COUNT_WORD[len(names)], _named(names)
    readme = README.read_text(encoding="utf-8")
    limits = readme[readme.index("## Limitations and non-goals (v1)\n"):readme.index("\n## Layout\n")]
    [bullet] = [x for x in limits.split("\n") if "(research/no-model-clears.md)" in x]
    assert bullet.endswith(f" measures it on the {count} routing datasets that record a cost, {listed}, "
                           "and recommends keeping the rule")
    [row] = [x for x in INDEX.read_text(encoding="utf-8").split("\n")
             if x.startswith("| [no-model-clears.md](no-model-clears.md) | ")]
    assert f"(Short answer: keep 5.3. On the {count} routing datasets that record a cost ({listed}) " in row
    for text in (bullet, row):
        assert not re.search(r"\b(?:" + "|".join(w for k, w in COUNT_WORD.items() if k != len(names))
                             + r") routing datasets\b", text)


# --- the pinned files, only when already cached ------------------------------------------------

@pytest.fixture(scope="module")
def output(nmc, tmp_path_factory, llmrouterbench_pinned, response_bank_pinned):
    """The script's lines on the six datasets, their matrices built in process from the cached files
    (the LLMRouterBench and response-bank matrices are the session fixtures' converter output, v1.341)."""
    pytest.importorskip("pandas")
    rb = _load("r8_routerbench_convert", ROOT / "evidence" / "routerbench" / "convert.py")
    ab = _load("r8_autobench_convert", ROOT / "evidence" / "autobench-2026" / "convert.py")
    jm = _load("r8_autobench_judges", ROOT / "evidence" / "autobench-2026" / "judges.py")
    t2 = _load("r8_tau2_convert", ROOT / "evidence" / "tau2-bench" / "convert.py")
    pkl, a_dir, t_dir = rb.default_cache_dir() / rb.FILENAME, ab.default_cache_dir(), t2.default_cache_dir()
    if (not pkl.is_file() or not all((a_dir / n).is_file() for n in ab.FILES)
            or not all((t_dir / n).is_file() for n in t2.FILES)):
        pytest.skip("the pinned RouterBench, AutoBench and tau2-bench files are not in the default cache")
    rb.verify(pkl)
    for name, (size, sha) in ab.FILES.items():
        ab.verify(a_dir / name, size, sha)
    params = json.loads((a_dir / "frozen_params.json").read_text(encoding="utf-8"))
    pool = json.loads((a_dir / "pool.json").read_text(encoding="utf-8"))
    matrix, questions = ab.read_csv(a_dir / "matrix.csv"), ab.read_csv(a_dir / "questions.csv")
    registry = tmp_path_factory.mktemp("r8") / "autobench-models.json"
    registry.write_text(json.dumps(ab.pool_registry(pool)), encoding="utf-8")
    extracts = []
    for name, (size, sha) in t2.FILES.items():
        t2.verify(t_dir / name, size, sha)
        extracts.append(t2.extract(t2.read_run(t_dir / name), trial=0))
    outcomes = {
        "RouterBench": outcomes_from_rows(rb.convert(rb.frame_columns(rb.load_frame(pkl)))[0]),
        "AutoBench": outcomes_from_rows(ab.convert(matrix, questions, pool, params["delta_signal"],
                                                   params["top_k"], task_by="all")[0]),
        "AutoBench judges": outcomes_from_rows(jm.judge_matrix(matrix, pool)[0], Registry.load(registry)),
        "tau2-bench": outcomes_from_rows(t2.convert(extracts)[0])}
    lrb_code, _report, lrb_path = llmrouterbench_pinned
    bank_code, _out, _err, bank_path = response_bank_pinned
    assert (lrb_code, bank_code) == (0, 0)
    outcomes["LLMRouterBench"] = load_outcomes(str(lrb_path))
    outcomes["LLM Routing Response Bank"] = load_outcomes(str(bank_path))
    return "\n".join(nmc.run(outcomes, ROOT)) + "\n"


def test_output_holds_the_six_datasets_in_order(output):
    heads = [x.split(" (")[0] for x in output.split("\n") if x and not x.startswith(" ")]
    assert heads == [name for name, _ in DATASETS]
    for name, rel in DATASETS:
        assert f"\n{name} ({rel}): " in "\n" + output


def test_note_results_block_is_the_script_output(output):
    [text] = _blocks(NOTE.read_text(encoding="utf-8"), "text")
    assert text == COMMAND + "\n" + output


def test_the_fallback_is_best_on_calibration_on_every_cell_where_no_model_clears(output):
    heads = re.findall(r"no model clears on ([\d,]+) of [\d,]+ cost_effective cells \([\d.]+%\), "
                       r"[\d,]+ held-out items.*\n    the routed model is best_on_calibration's on ([\d,]+) ",
                       output)
    assert len(heads) >= 10 and all(a == b for a, b in heads)


def test_the_fallback_is_best_on_calibration_on_both_new_datasets(output):
    for name in ("LLMRouterBench", "LLM Routing Response Bank"):
        block = output[output.index(f"{name} ("):]
        block = block[:block.index("\n\n")] if "\n\n" in block else block
        heads = re.findall(r"no model clears on ([\d,]+) of [\d,]+ cost_effective cells \([\d.]+%\), "
                           r"[\d,]+ held-out items.*\n    the routed model is best_on_calibration's on ([\d,]+) ",
                           block)
        assert heads and all(a == b for a, b in heads), name
