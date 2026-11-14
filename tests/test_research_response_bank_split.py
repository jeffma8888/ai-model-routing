"""research/response-bank-split.md and research/response_bank_split.py (DESIGN 12.21 v1.375, row R27).

The script calibrates on the release's own 256 calibration tasks and scores on its 13,059 evaluation
tasks, one fixed split, with the evaluator's own cell, and prints it beside the committed 50-seed
means of evidence/response-bank/results.json. When the four pinned files are cached, the note's
Results block is compared byte for byte with a fresh run on the converter's rows; on every machine
the committed columns of that block are rebuilt from the committed file, its split columns from the
evidence README, and its report is checked on a small hand-made matrix worked out by hand.
Committed before the script and the note under strict xfail until v1.376.
"""

import ast
import contextlib
import importlib.util
import io
import json
import re
from pathlib import Path

import pytest

from model_routing import outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "response_bank_split.py"
NOTE = ROOT / "research" / "response-bank-split.md"
INDEX = ROOT / "research" / "README.md"
RESULTS = ROOT / "evidence" / "response-bank" / "results.json"
EVIDENCE_README = ROOT / "evidence" / "response-bank" / "README.md"
COMMAND = "$ python research/response_bank_split.py --matrix response-bank-matrix.jsonl"
CONVERT = "python evidence/response-bank/convert.py --out response-bank-matrix.jsonl"
SECTIONS = ["## Facts", "## Method", "## Results", "## Reading it", "## Recommendation", "## Limits",
            "## Regenerate"]
# DESIGN section numbers: the only numbers of the note's prose that are not in the script's output
ALLOWED = {"5.3", "12.2", "12.3", "12.7", "12.20", "12.21"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?%?")
RED = pytest.mark.xfail(strict=True, raises=(FileNotFoundError, AssertionError),
                        reason="research/response_bank_split.py and its note land in v1.376")
pytestmark = RED


def _load():
    spec = importlib.util.spec_from_file_location("research_response_bank_split", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rbs():
    return _load()


def run(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


def note():
    return NOTE.read_text(encoding="utf-8")


def results_block(text):
    section = text.split("\n## Results\n", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"^```text\n(.*?)^```$", section, re.M | re.S)
    assert len(blocks) == 1, "one text block in ## Results"
    return blocks[0]


def committed():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def summary_row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"] if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1
    return rows[0]


def best_single(results, bar, flavor):
    rows = [r for r in results["summary"] if (r["bar"], r["flavor"]) == (bar, flavor)
            and r["strategy"].startswith("model:")]
    return min(rows, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))


# --- the pinned run (skips where the four pinned files are not cached, as in CI) ---

def test_note_results_block_is_the_script_output(rbs, response_bank_pinned):
    code, _, err, rows = response_bank_pinned
    assert (code, err) == (0, "")
    code, out, err = run(rbs, ["--matrix", str(rows)])
    assert (code, err) == (0, "")
    assert results_block(note()) == COMMAND + "\n" + out


# --- the note, on every machine ---

def test_note_sections_in_order():
    assert re.findall(r"^## .*$", note(), re.M) == SECTIONS
    assert note().startswith("# ")


def test_prose_numbers_are_in_the_results_block():
    text = note()
    known = set(NUMBER.findall(results_block(text))) | ALLOWED
    prose = re.sub(r"^```[a-z]*\n.*?^```$", "", text, flags=re.M | re.S)
    prose = re.sub(r"https?://\S+", "", prose)
    prose = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", prose)
    prose = re.sub(r"`[^`\n]*`", "", prose)
    stray = sorted(set(NUMBER.findall(prose)) - known)
    assert not stray, stray


def test_committed_columns_are_the_committed_file():
    block, results = results_block(note()), committed()
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    best = best_single(results, *first)
    found = re.findall(r"^  best single model: \S+ [\d.]+ here; (\S+) ([\d.]+) in the committed means over "
                       r"(\d+) seeds$", block, re.M)
    assert found == [(best["strategy"][len("model:"):], f"{best['success']:.3f}", str(len(config["seeds"])))]
    for s in ("oracle", "best_on_calibration", "cheapest"):
        r = summary_row(results, *first, s)
        found = re.findall(rf"^  {s}: [\d.]+ at [\d.]+ of the best's cost here; ([\d.]+) at ([\d.]+) committed$",
                           block, re.M)
        assert found == [(f"{r['success']:.3f}", f"{r['cost_usd'] / best['cost_usd']:.3f}")], s
    lines = re.findall(r"^  (0\.\d+) +(cost_effective|cost_blind) +(.*)$", block, re.M)
    assert [(float(b), f) for b, f, _ in lines] == [(b, f) for f in config["flavors"] for b in config["bars"]]
    for bar, flavor, rest in lines:
        fields = rest.split()
        assert len(fields) == 9 and fields[4] == "of", rest
        r = summary_row(results, float(bar), flavor, "routed")
        assert fields[6:] == [f"{r['success']:.3f}", f"{r['cost_usd'] / best['cost_usd']:.3f}",
                              f"{r['cleared_rate']:.3f}"], (bar, flavor)


def test_split_columns_are_the_evidence_readme_and_the_committed_halves():
    block, results = results_block(note()), committed()
    readme = EVIDENCE_README.read_text(encoding="utf-8")
    table = dict((t, (int(c.replace(",", "")), int(e.replace(",", ""))))
                 for t, c, e in re.findall(r"^\| `?([a-z_]+)`? \| ([\d,]+) \| ([\d,]+) \| [\d,]+ \|$", readme, re.M))
    assert sorted(table) == sorted(results["tasks"])
    rows = re.findall(r"^  ([a-z_]+) +(\d+) +(\d+) +(\d+) +(yes|no) +([\d.]+) \((\S+), (\d+) of (\d+)\)$",
                      block, re.M)
    assert [r[0] for r in rows] == sorted(results["tasks"])
    floor = results["config"]["min_samples"]
    for task, cal, held, half, below, _, _, _, n in rows:
        assert (int(cal), int(held)) == table[task], task
        assert int(half) == int(results["tasks"][task]["items"] * results["config"]["calibration_fraction"])
        assert below == ("yes" if int(cal) < floor else "no") and n == cal, task
    total = re.findall(r"^  all +(\d+) +(\d+)$", block, re.M)
    assert total == [(str(sum(c for c, _ in table.values())), str(sum(e for _, e in table.values())))]


def test_a_task_below_min_samples_never_clears():
    block = results_block(note())
    below = set(re.findall(r"^  ([a-z_]+) +\d+ +\d+ +\d+ +yes ", block, re.M))
    assert "aime" in below
    picks = re.findall(r"^    0\.\d+ (?:cost_effective|cost_blind): (.*)$", block, re.M)
    assert len(picks) == 4
    for line in picks:
        for task, model in (p.split(" ", 1) for p in line.split(", ")):
            if task in below:
                assert not model.endswith("*"), line


def test_regenerate_section_states_the_commands():
    section = note().split("\n## Regenerate\n", 1)[1]
    assert "python -m pip install -e ." in section
    assert CONVERT in section
    assert COMMAND[2:] in section


def test_note_names_what_it_reads():
    text = note()
    for name in ("`evidence/response-bank/results.json`", "`scores_cal.jsonl`", "`scores_eval.jsonl`",
                 "`evidence/response-bank/convert.py`"):
        assert name in text, name


def test_research_index_row_and_bullet():
    text = INDEX.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines()
            if line.startswith("| [response-bank-split.md](response-bank-split.md) | ")]
    assert len(rows) == 1
    assert "[response_bank_split.py](response_bank_split.py)" in rows[0]
    assert sum(1 for line in text.splitlines() if line.startswith("- `research/response-bank-split.md` ")) == 1


def test_script_imports_only_the_standard_library_and_named_model_routing_parts():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names, private = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module if node.module.startswith("model_routing") else node.module.split(".")[0])
            if node.module == "model_routing.evaluate":
                private |= {a.name for a in node.names}
    assert names <= {"argparse", "importlib", "json", "sys", "pathlib", "model_routing",
                     "model_routing.evaluate", "model_routing.stats"}, names
    assert private == {"_cell", "_split_sums", "_strategies", "_summary"}, private


# --- a hand-made matrix, every number worked out by hand ---

def _rows():
    rows = []
    for k in range(30):
        rows.append({"task": "t", "item": f"t:c{k:02d}", "model": "v/a", "correct": True, "cost_usd": 2.0})
        rows.append({"task": "t", "item": f"t:c{k:02d}", "model": "v/b", "correct": True, "cost_usd": 1.0})
    for k in range(4):
        rows.append({"task": "t", "item": f"t:e{k}", "model": "v/a", "correct": True, "cost_usd": 2.0})
        rows.append({"task": "t", "item": f"t:e{k}", "model": "v/b", "correct": k < 2, "cost_usd": 1.0})
    return rows


CALIBRATION = {f"t:c{k:02d}" for k in range(30)}


def _committed():
    def row(strategy, success, cost, cleared=None):
        return {"bar": 0.8, "flavor": "cost_effective", "strategy": strategy, "success": success,
                "cost_usd": cost, "below_bar_rate": 0.0, "cleared_rate": cleared, "bar_violation_rate": None}
    return {"config": {"bars": [0.8], "seeds": [0, 1], "flavors": ["cost_effective"], "calibration_fraction": 0.5,
                       "min_samples": 30, "confidence": 0.95},
            "tasks": {"t": {"items": 34, "models": ["v/a", "v/b"]}},
            "summary": [row("routed", 0.6, 1.5, 0.5), row("oracle", 0.95, 2.4), row("best_on_calibration", 0.6, 1.5),
                        row("cheapest", 0.6, 1.5), row("model:v/a", 0.9, 3.0), row("model:v/b", 0.6, 1.5)]}


def test_report_on_a_hand_made_matrix(rbs):
    # Both models are right on all 30 calibration items, so each has the Wilson bound 30 / (30 + 1.96^2)
    # = 0.886 at 0.95 and clears 0.8; cost_effective takes the cheaper v/b, right on 2 of the 4
    # evaluation items at 1.0 each, against v/a's 4 of 4 at 2.0 each; the oracle pays v/b on the two
    # items it gets right and v/a on the other two, 6.0, 0.750 of the best single model's 8.0
    lines = [" ".join(line.split()) for line in rbs.report(outcomes_from_rows(_rows()), CALIBRATION, _committed())]
    for want in ("t 30 4 17 no 0.886 (v/b, 30 of 30)", "all 30 4", "v/a 1.000 8.0000", "v/b 0.500 4.0000",
                 "best single model: v/a 1.000 here; v/a 0.900 in the committed means over 2 seeds",
                 "oracle: 1.000 at 0.750 of the best's cost here; 0.950 at 0.800 committed",
                 "best_on_calibration: 0.500 at 0.500 of the best's cost here; 0.600 at 0.500 committed",
                 "cheapest: 0.500 at 0.500 of the best's cost here; 0.600 at 0.500 committed",
                 "0.8 cost_effective 0.500 4.0000 0.500 1 of 1 0.600 0.500 0.500",
                 "0.8 cost_effective: t v/b*"):
        assert want in lines, want


@pytest.mark.parametrize("change, message", [
    (lambda rows, cal: (rows, cal | {"t:zz"}), "calibration task_ids are not in the matrix"),
    (lambda rows, cal: (rows, cal | {f"t:e{k}" for k in range(4)}), "the release's calibration or evaluation"),
    (lambda rows, cal: (rows[:-1], cal), "incomplete matrix"),
])
def test_release_split_refusals(rbs, change, message):
    rows, cal = change(_rows(), set(CALIBRATION))
    with pytest.raises(ValueError, match=message):
        rbs.release_split(outcomes_from_rows(rows), cal, _committed()["config"])


def test_report_refuses_other_tasks_than_the_committed_file(rbs):
    other = _committed()
    other["tasks"] = {"u": other["tasks"]["t"]}
    with pytest.raises(ValueError, match="not the committed file's"):
        rbs.report(outcomes_from_rows(_rows()), CALIBRATION, other)


def _root(tmp_path):
    root = tmp_path / "root"
    (root / "evidence" / "response-bank").mkdir(parents=True)
    (root / "evidence" / "response-bank" / "convert.py").write_bytes(
        (ROOT / "evidence" / "response-bank" / "convert.py").read_bytes())
    (root / "evidence" / "response-bank" / "results.json").write_text(json.dumps(_committed()), encoding="utf-8")
    matrix = tmp_path / "matrix.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in _rows()), encoding="utf-8")
    return root, matrix


def test_a_missing_calibration_file_is_one_error_line(rbs, tmp_path):
    root, matrix = _root(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    code, out, err = run(rbs, ["--matrix", str(matrix), "--cache", str(cache), "--root", str(root)])
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1 and "scores_cal.jsonl" in err


def test_a_calibration_file_off_its_pin_is_one_error_line(rbs, tmp_path):
    root, matrix = _root(tmp_path)
    cache = tmp_path / "cache"
    cache.mkdir()
    (cache / "scores_cal.jsonl").write_text("{}\n", encoding="utf-8")
    code, out, err = run(rbs, ["--matrix", str(matrix), "--cache", str(cache), "--root", str(root)])
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1


def test_an_error_holding_a_newline_is_escaped(rbs, tmp_path):
    root, _ = _root(tmp_path)
    code, out, err = run(rbs, ["--matrix", str(tmp_path / "no\nsuch\r.jsonl"), "--cache", str(tmp_path),
                               "--root", str(root)])
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1 and "\r" not in err
    assert "no\\nsuch\\r.jsonl" in err
