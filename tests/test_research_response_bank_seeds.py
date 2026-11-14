"""research/response-bank-seeds.md and `--dataset response-bank` of research/llmrouterbench_seeds.py
(DESIGN 12.21 v1.381, row R33).

The note's Results block is the script's output on the response-bank matrix, compared byte for byte
when the four pinned files are cached (the session fixture `response_bank_pinned` of
tests/conftest.py, which CI never fills). Its `## Facts`, `## Reading it` and `## Recommendation`
are built whole from that block by `built_sections`, so those checks run in CI too. The option is
tested on a small matrix.
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

from model_routing import evaluate, load_outcomes, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "llmrouterbench_seeds.py"
NOTE = ROOT / "research" / "response-bank-seeds.md"
LRB_NOTE = ROOT / "research" / "llmrouterbench-seeds.md"
INDEX = ROOT / "research" / "README.md"
RESULTS = "evidence/response-bank/results.json"
LRB_RESULTS = "evidence/llmrouterbench/results.json"
NAME = "LLM Routing Response Bank"
COMMAND = "$ python research/llmrouterbench_seeds.py --dataset response-bank --matrix response-bank-matrix.jsonl"
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/response-bank/convert.py --out response-bank-matrix.jsonl",
    COMMAND[2:],
]
HEADINGS = ["Facts", "Method", "Results", "Reading it", "Recommendation", "Limits", "Regenerate"]
BUILT = ("Facts", "Reading it", "Recommendation")
# DESIGN section numbers: the only numbers of the prose outside the built sections
ALLOWED = {"12.2", "12.3", "12.7", "12.20", "12.21"}
NUMBER = re.compile(r"(?<![\w.])[+-]?\d+(?:,\d{3})*(?:\.\d+)?%?")
CONFIG = {"bars": [0.5, 0.65], "seeds": list(range(6)), "flavors": ["cost_effective", "cost_blind"],
          "calibration_fraction": 0.5, "min_samples": 10, "confidence": 0.95}
TINY = {"a": (120, {"v/x": (72, 0.03), "v/y": (55, 0.02), "v/z": (45, 0.001)}),
        "b": (100, {"v/x": (50, 0.03), "v/y": (66, 0.02), "v/z": (40, 0.001)})}


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lrs():
    return _load("research_llmrouterbench_seeds_rb", SCRIPT)


def tiny_rows():
    rows = []
    for task, (n, models) in TINY.items():
        for i in range(n):
            for model, (pct, cost) in models.items():
                h = int(hashlib.sha256(f"{task}|{i}|{model}".encode()).hexdigest(), 16)
                rows.append({"task": task, "item": f"{task}{i}", "model": model, "correct": h % 100 < pct,
                             "cost_usd": cost * (1 + i % 3)})
    return rows


def committed(rows):
    result = evaluate(outcomes_from_rows(rows), bars=CONFIG["bars"], seeds=CONFIG["seeds"],
                      flavors=CONFIG["flavors"], calibration_fraction=CONFIG["calibration_fraction"],
                      min_samples=CONFIG["min_samples"], confidence=CONFIG["confidence"])
    return {"config": result["config"], "summary": result["summary"]}


def _tree(tmp_path, rows, rel=RESULTS):
    path = tmp_path / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(committed(rows)), encoding="utf-8")
    matrix = tmp_path / "m.jsonl"
    matrix.write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return ["--root", str(tmp_path), "--matrix", str(matrix)]


def _main(lrs, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        try:
            code = lrs.main(argv)
        except SystemExit as exc:
            code = exc.code
    return code, out.getvalue(), err.getvalue()


# --- the option, on a small matrix ------------------------------------------------------------

def test_the_datasets(lrs):
    assert lrs.DATASETS == {"llmrouterbench": ("LLMRouterBench", LRB_RESULTS), "response-bank": (NAME, RESULTS)}
    assert lrs.RESULTS == LRB_RESULTS


def test_response_bank_reads_its_own_file_and_names_itself(lrs, tmp_path):
    rows = tiny_rows()
    code, out, err = _main(lrs, ["--dataset", "response-bank"] + _tree(tmp_path, rows))
    assert (code, err) == (0, "")
    default = lrs.report(outcomes_from_rows(rows), committed(rows), rel=RESULTS)
    assert default[0].startswith(f"LLMRouterBench ({RESULTS}): 2 tasks, ")
    assert out == "\n".join([NAME + default[0][len("LLMRouterBench"):]] + default[1:]) + "\n"
    assert out.startswith(f"{NAME} ({RESULTS}): 2 tasks, 3 models, 220 items, ")


def test_response_bank_never_reads_the_llmrouterbench_file(lrs, tmp_path):
    argv = ["--dataset", "response-bank"] + _tree(tmp_path, tiny_rows(), rel=LRB_RESULTS)
    code, out, err = _main(lrs, argv)
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1 and RESULTS in err


@pytest.mark.parametrize("key", ["success", "cost_usd"])
def test_response_bank_row_not_the_committed_one_exits_2(lrs, tmp_path, key):
    argv = ["--dataset", "response-bank"] + _tree(tmp_path, tiny_rows())
    path = tmp_path / RESULTS
    record = json.loads(path.read_text(encoding="utf-8"))
    row = next(r for r in record["summary"] if r["strategy"] == "routed")
    row[key] *= 1 + 1e-9
    path.write_text(json.dumps(record), encoding="utf-8")
    code, out, err = _main(lrs, argv)
    assert (code, out) == (2, "")
    assert err.startswith(f"error: {RESULTS}: the routed ") and "is not the committed one" in err


# --- the note, from its Results block -----------------------------------------------------------

HEAD = re.compile(rf"^{NAME} \({re.escape(RESULTS)}\): (?P<tasks>\d+) tasks, (?P<models>\d+) models, "
                  r"(?P<items>[\d,]+) items, bars (?P<bars>[\d., ]+), (?P<seeds>\d+) seeds, "
                  r"held-out items per seed (?P<held_low>[\d,]+) to (?P<held_high>[\d,]+)$")
BEST = re.compile(r"^best single model \(12\.7\): (?P<best>\S+); a gap is a row's pooled held-out success "
                  r"on a seed minus (?P=best)'s on the same halves$")
LINE = re.compile(r"^(?P<label>[^:]+): (?P<rest>above on (?P<above>\d+), equal on (?P<equal>\d+), "
                  r"below on (?P<below>\d+) of (?P<seeds>\d+) seeds; gap lowest (?P<lowest>[+-]\d\.\d{4}), "
                  r"median (?P<median>[+-]\d\.\d{4}), highest (?P<highest>[+-]\d\.\d{4}), "
                  r"mean (?P<mean>[+-]\d\.\d{4}); cost over the best single model's "
                  r"(?P<low>\d+\.\d{3}) to (?P<high>\d+\.\d{3}))$")
SIGNS = re.compile(r"^  seeds whose gap has one sign at every bar: (?P<signs>\d+) of (?P<seeds>\d+); "
                   r"\(task, seed\) cells routed to one model at every bar: (?P<cells>[\d,]+) of (?P<all>[\d,]+)$")


def _match(pattern, line):
    found = pattern.match(line)
    if found is None:
        raise ValueError(f"not a line the note reads: {line!r}")
    return found


def parse(block):
    """The Results block (command line, then output) as the header, the best single model's match,
    the `best_on_calibration` line and, per flavor, its bar lines and its one-sign line."""
    lines = block.rstrip("\n").split("\n")
    if lines[0] != COMMAND:
        raise ValueError("the block does not open with the note's command line")
    head, best = _match(HEAD, lines[1]), _match(BEST, lines[2])
    boc = _match(LINE, lines[3])
    if boc["label"] != "best_on_calibration (every bar and flavor)":
        raise ValueError("no best_on_calibration line")
    bars = head["bars"].split(", ")
    flavors, k = {}, 4
    for flavor in ("cost_effective", "cost_blind"):
        if lines[k] != f"{flavor} routed:":
            raise ValueError(f"no {flavor} routed: line")
        at = {}
        for bar in bars:
            found = _match(LINE, lines[k + 1 + len(at)])
            if found["label"] != f"  bar {bar}":
                raise ValueError(f"no bar {bar} line under {flavor}")
            at[bar] = found
        flavors[flavor] = (at, _match(SIGNS, lines[k + 1 + len(bars)]))
        k += 2 + len(bars)
    if k != len(lines):
        raise ValueError("lines after the cost_blind block")
    return head, best, boc, bars, flavors


def built_sections(block):
    """`## Facts`, `## Reading it` and `## Recommendation` of the note, each a list of bullets, built
    from the Results block; a ValueError for a block whose signs or equal lines they would misread."""
    head, best, boc, bars, flavors = parse(block)
    if len(bars) != 2:
        raise ValueError("the sentences read two bars")
    low_bar, high_bar = bars
    (ce, ce_signs), (cb, cb_signs) = flavors["cost_effective"], flavors["cost_blind"]
    blind = cb[low_bar]
    n = int(head["seeds"])
    if not (cb[high_bar]["rest"] == blind["rest"] == boc["rest"] == ce[high_bar]["rest"]):
        raise ValueError("cost_blind at both bars, best_on_calibration and cost_effective at the higher bar differ")
    if not (int(blind["equal"]) == 0 and 0 < int(blind["below"]) < int(blind["above"])):
        raise ValueError("cost_blind is not above on most seeds and below on the rest")
    if not (float(blind["lowest"]) < 0 < float(blind["median"]) and float(blind["mean"]) > 0
            and max(abs(float(blind["lowest"])), abs(float(blind["highest"]))) < 0.01):
        raise ValueError("the cost_blind gaps are not a few thousandths either side of 0 with a positive median and mean")
    if not (float(blind["low"]) < 1 and float(blind["high"]) > 2):
        raise ValueError("the cost_blind cost ratio does not run from under 1 to over 2")
    if not (cb_signs["signs"] == cb_signs["seeds"] and cb_signs["cells"] == cb_signs["all"]):
        raise ValueError("cost_blind does not keep one sign and one model at every bar")
    low = ce[low_bar]
    if not (int(low["below"]) == n and float(low["highest"]) < 0 and float(low["high"]) < 1):
        raise ValueError("cost_effective at the lower bar is not below on every seed for less cost")
    if int(ce_signs["signs"]) != int(ce[high_bar]["below"]):
        raise ValueError("the cost_effective seeds of one sign are not those below at the higher bar")
    facts = [
        "The committed gain is a mean, not a gain on every seed: `best_on_calibration`, `cost_blind` routing "
        "at both bars and `cost_effective` routing at the higher bar pass the best single model on most "
        "seeds' own halves but fall below it on the rest, while on LLMRouterBench the same rows pass it on "
        "every seed ([llmrouterbench-seeds.md](llmrouterbench-seeds.md))",
        f"Data: the 12.20 matrix, {head['tasks']} tasks, {head['models']} models and {head['items']} items, "
        f"run with the committed config, bars {low_bar} and {high_bar} and {n} seeds, each seed holding "
        f"{head['held_low']} to {head['held_high']} held-out items; the best single model is "
        f"`{best['best']}` (12.7)",
        f"`cost_blind`: above on {blind['above']} of the {n} seeds and below on {blind['below']}, with a gap "
        f"of {blind['lowest']} on the lowest seed, {blind['median']} at the median and {blind['highest']} on "
        f"the highest, against the committed mean of {blind['mean']}, at {blind['low']} to {blind['high']} "
        f"of that model's cost on the same halves; all {cb_signs['all']} (task, seed) cells keep one routed "
        f"model at both bars, so its line is the same at both",
        f"`best_on_calibration`, and `cost_effective` routing at bar {high_bar}, give that same line",
        f"`cost_effective` at bar {low_bar}: below on all {n} seeds, from {low['lowest']} to "
        f"{low['highest']}, at {low['low']} to {low['high']} of that model's cost; {ce_signs['signs']} of the {n} "
        f"seeds keep one sign at both bars, those below at bar {high_bar} too, and {ce_signs['cells']} of "
        f"the {ce_signs['all']} cells keep one routed model",
    ]
    reading = [
        f"The mean hides seeds that lose: in `cost_blind` the median seed gains {blind['median']}, but "
        f"{blind['below']} of the {n} seeds fall below the best single model, the lowest to a gap of "
        f"{blind['lowest']}, so on a new split of these items routing would likely pass that model, but not "
        f"surely, and by a few thousandths either way",
        f"The cost moves more than the success: from seed to seed `cost_blind` costs {blind['low']} to "
        f"{blind['high']} times what the best single model costs on the same halves, so on some seed it costs "
        f"less than that model and on others more than twice as much",
        f"`cost_effective` at bar {low_bar} buys its saving with success on every seed, below the best single "
        f"model on all {n} at {low['low']} to {low['high']} of its cost; at bar {high_bar} it falls back on "
        f"nearly every cell to the model `best_on_calibration` takes, which is why it gives `cost_blind`'s "
        f"line there ([the committed results](../evidence/response-bank/RESULTS.md) say why)",
        "On LLMRouterBench the lowest seed's gain is more than half the mean, a gain on every split; here "
        "the lowest seed is below the best single model, a gain on most splits",
    ]
    recommendation = [
        f"README.md's response-bank bullet in Results at a glance says `cost_blind` routing passes the best "
        f"single model's held-out success at every bar; that holds for the committed mean, a gap of "
        f"{blind['mean']}, and on {blind['above']} of the {n} seeds, not on every one. Keep `passes`, but say "
        f"it is a mean and on how many seeds it holds, for example `passes the best single model's held-out "
        f"success in the mean over {n} seeds, on {blind['above']} of them`; its `more than twice its cost` is "
        f"the ratio of the mean costs, while seed by seed the cost runs from {blind['low']} to "
        f"{blind['high']} of that model's, so say it is a mean too",
        "The README Limitations bullet on where routing pays and [where-routing-pays.md](where-routing-pays.md) "
        "count the response bank as one of the two routing datasets with a routed row above the best single "
        "model; keep it there, since its mean is above, and add that its gain holds on most seeds while "
        "LLMRouterBench's holds on every one",
        "Make these wording changes in a change of their own; this note changes no README line",
    ]
    return {"Facts": facts, "Reading it": reading, "Recommendation": recommendation}


def _note():
    return NOTE.read_text(encoding="utf-8")


def _blocks(text, lang):
    return re.findall(rf"^```{lang}\n(.*?)^```$", text, flags=re.M | re.S)


def _section(note, heading):
    return note.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def _prose(text):
    prose = re.sub(r"^```\w*\n.*?^```$", "", text, flags=re.M | re.S)
    return re.sub(r"\]\([^)]*\)|`[^`]*`", "", prose)


def test_note_shape_commands_and_links():
    note = _note()
    assert note.startswith("# The response-bank gain, seed by seed\n\n")
    assert not note.split("\n", 2)[2].startswith("#")
    assert re.findall(r"^## (.+)$", note, flags=re.M) == HEADINGS
    assert _blocks(note, "bash") == ["\n".join(REGENERATE) + "\n"]
    [text] = _blocks(note, "text")
    assert text.startswith(COMMAND + "\n")
    assert note.isascii()
    for link in ("../DESIGN.md", "../evidence/response-bank/RESULTS.md", "llmrouterbench_seeds.py",
                 "llmrouterbench-seeds.md", "where-routing-pays.md", "response-bank-split.md"):
        assert f"]({link})" in note, link


def test_built_sections_are_the_note_s():
    note = _note()
    [text] = _blocks(note, "text")
    for heading, bullets in built_sections(text).items():
        assert _section(note, heading) == "\n" + "".join(f"- {b}\n" for b in bullets), heading


def test_facts_states_the_finding_before_any_number():
    [text] = _blocks(_note(), "text")
    assert NUMBER.findall(_prose(built_sections(text)["Facts"][0])) == []


def test_every_other_number_of_the_prose_is_a_section_number():
    note = _note()
    for heading in BUILT:
        note = note.replace(f"\n## {heading}\n" + _section(note, heading), f"\n## {heading}\n")
    assert sorted(n for n in set(NUMBER.findall(_prose(note))) if n not in ALLOWED) == []


# Each case breaks one condition alone (review iter-242 should-fix 1 and 2): its edits, each
# (old, new, count) with count -1 for every copy, and the start of the message of the check it hits,
# the first that fails, so a deleted clause fails its case. The first three change one of the four
# equal lines alone: `cost_effective` at bar 0.9 (the first copy), `cost_blind` at bar 0.9 (the
# last bar line) and `best_on_calibration`.
CB_09 = "  bar 0.9: above on 42, equal on 0, below on 8 of 50 seeds; gap lowest -0.0032"
CB_END = "0.958 to 2.327\n  seeds whose gap has one sign at every bar: 50 of 50"  # the last cost_blind bar line's end
REFUSALS = [
    ([(CB_09, CB_09[:-1] + "3", 1)], "cost_blind at both bars, best_on_calibration and cost_effective"),
    ([(CB_END, CB_END.replace("2.327", "2.328"), 1)], "cost_blind at both bars, best_on_calibration and cost_effective"),
    ([("(every bar and flavor): above on 42", "(every bar and flavor): above on 43", 1),
      ("(every bar and flavor): above on 43, equal on 0, below on 8", "(every bar and flavor): above on 42, equal on 1, below on 7", 1)],
     "cost_blind at both bars, best_on_calibration and cost_effective"),
    ([("above on 42, equal on 0, below on 8", "above on 41, equal on 1, below on 8", -1)],
     "cost_blind is not above on most seeds"),
    ([("above on 42, equal on 0, below on 8", "above on 8, equal on 0, below on 42", -1),
      ("one sign at every bar: 8 of 50", "one sign at every bar: 42 of 50", -1)], "cost_blind is not above on most seeds"),
    ([("gap lowest -0.0032", "gap lowest +0.0001", -1)], "the cost_blind gaps are not"),
    ([("median +0.0026", "median -0.0026", -1)], "the cost_blind gaps are not"),
    ([("mean +0.0022", "mean -0.0022", -1)], "the cost_blind gaps are not"),
    ([("highest +0.0059", "highest +0.0159", -1)], "the cost_blind gaps are not"),
    ([("0.958 to 2.327", "1.058 to 2.327", -1)], "the cost_blind cost ratio"),
    ([("0.958 to 2.327", "0.958 to 1.927", -1)], "the cost_blind cost ratio"),
    ([("one sign at every bar: 50 of 50", "one sign at every bar: 49 of 50", -1)], "cost_blind does not keep"),
    ([("routed to one model at every bar: 200 of 200", "routed to one model at every bar: 199 of 200", -1)],
     "cost_blind does not keep"),
    ([("bar 0.8: above on 0, equal on 0, below on 50", "bar 0.8: above on 1, equal on 0, below on 49", -1)],
     "cost_effective at the lower bar"),
    ([("highest -0.0203", "highest +0.0003", -1)], "cost_effective at the lower bar"),
    ([("0.174 to 0.241", "0.174 to 1.241", -1)], "cost_effective at the lower bar"),
    ([("one sign at every bar: 8 of 50", "one sign at every bar: 9 of 50", -1)], "the cost_effective seeds of one sign"),
]


def test_builder_builds_the_note_s_block():
    [text] = _blocks(_note(), "text")
    assert set(built_sections(text)) == set(BUILT)


@pytest.mark.parametrize("edits, message", REFUSALS)
def test_builder_refuses_a_block_it_would_misread(edits, message):
    [text] = _blocks(_note(), "text")
    for old, new, count in edits:
        assert text.count(old) >= 1 if count == -1 else text.count(old) >= count, old
        text = text.replace(old, new, count)
    with pytest.raises(ValueError, match="^" + re.escape(message)):
        built_sections(text)


def test_the_llmrouterbench_claims_hold_on_that_note_s_block():
    """Facts bullet 1 and Reading it bullet 4 speak of LLMRouterBench (review iter-242 should-fix 4):
    there `best_on_calibration`, `cost_blind` at every bar and `cost_effective` at the highest bar
    are above on every seed, and each `cost_blind` line's lowest gap is more than half its mean."""
    [text] = _blocks(LRB_NOTE.read_text(encoding="utf-8"), "text")
    lines = text.rstrip("\n").split("\n")
    boc = LINE.match(lines[3])
    assert boc and boc["label"] == "best_on_calibration (every bar and flavor)"
    ce = lines.index("cost_effective routed:")
    cb = lines.index("cost_blind routed:")
    blind = [LINE.match(x) for x in lines[cb + 1:-1]]
    highest_ce = LINE.match(lines[cb - 2])
    assert len(blind) == cb - ce - 2 and all(blind) and highest_ce
    for row in [boc, highest_ce] + blind:
        assert row["above"] == row["seeds"], row["label"]
    for row in blind:
        assert float(row["lowest"]) > float(row["mean"]) / 2 > 0, row["label"]
    assert "the same rows pass it on every seed" in built_sections(_blocks(_note(), "text")[0])["Facts"][0]


# --- the LLMRouterBench note and the index ----------------------------------------------------

def test_llmrouterbench_note_no_longer_calls_it_the_one_such_dataset():
    note = LRB_NOTE.read_text(encoding="utf-8")
    opening = note.split("\n\n", 2)[1]
    assert "the one routing dataset" not in note
    assert NAME in opening and "](response-bank-seeds.md)" in opening
    limits = note[note.index("\n## Limits\n"):note.index("\n## Regenerate\n")]
    assert sum("](response-bank-seeds.md)" in x for x in limits.split("\n")) == 1


def index_row(block):
    """The research/README.md row, its numbers built from the Results block (review iter-242
    should-fix 5); `built_sections` first, so its checks hold for the row's sentences too."""
    built_sections(block)
    head, _best, _boc, bars, flavors = parse(block)
    blind = flavors["cost_blind"][0][bars[0]]
    return ("| [response-bank-seeds.md](response-bank-seeds.md) | Does the response-bank gain over the best single model "
            "hold on each seed, or only in the mean over seeds that the committed results give? (Short answer: only in "
            "the mean and on most seeds. `cost_blind` routing at both bars and `best_on_calibration` pass that model on "
            f"{blind['above']} of the {head['seeds']} seeds' own halves and fall below it on {blind['below']}, by a few "
            f"thousandths either way, while `cost_effective` routing at bar {bars[0]} is below it on every seed; the note "
            "recommends saying in the README that the response-bank gain is a mean. Its numbers are the output of "
            "[llmrouterbench_seeds.py](llmrouterbench_seeds.py) with `--dataset response-bank`) |")


def test_research_index_lists_the_note():
    index = INDEX.read_text(encoding="utf-8").split("\n")
    rows = [x for x in index if x.startswith("| [response-bank-seeds.md](response-bank-seeds.md) | ")]
    assert rows == [index_row(_blocks(_note(), "text")[0])]
    assert sum(x.startswith("- `research/response-bank-seeds.md` ") for x in index) == 1


# --- the pinned files, only when already cached (one session read, tests/conftest.py) -------------

@pytest.fixture(scope="module")
def output(lrs, response_bank_pinned):
    """The script's lines on the matrix the session fixture wrote from the cached pinned files."""
    code, _stdout, _stderr, rows = response_bank_pinned
    assert code == 0
    status, out, err = _main(lrs, ["--dataset", "response-bank", "--matrix", str(rows)])
    assert (status, err) == (0, "")
    return out


def test_note_results_block_is_the_script_output(output):
    [text] = _blocks(_note(), "text")
    assert text == COMMAND + "\n" + output


def test_means_over_seeds_are_the_committed_rows(lrs, response_bank_pinned):
    """Rebuilt here, apart from the script's own check: each row's per-seed pooled success and cost,
    averaged over the seeds, is the committed summary row at every bar and flavor. Independent of the
    script's code, not of its method: it pools the same `evaluate` cells the same way (review iter-242
    should-fix 6)."""
    code, _stdout, _stderr, rows = response_bank_pinned
    assert code == 0
    record = json.loads((ROOT / RESULTS).read_text(encoding="utf-8"))
    config = record["config"]
    result = evaluate(load_outcomes(str(rows)), bars=config["bars"], seeds=config["seeds"],
                      flavors=config["flavors"], calibration_fraction=config["calibration_fraction"],
                      min_samples=config["min_samples"], confidence=config["confidence"])
    best = "model:" + lrs.best_single_model(record["summary"], rel=RESULTS)
    checked = 0
    for row in record["summary"]:
        if row["strategy"] not in ("routed", "best_on_calibration", best):
            continue
        cells = [c for c in result["cells"] if (c["bar"], c["flavor"]) == (row["bar"], row["flavor"])]
        success, cost = [], []
        for seed in config["seeds"]:
            cs = [c for c in cells if c["seed"] == seed]
            success.append(sum(round(c["success"][row["strategy"]] * c["held_out_items"]) for c in cs)
                           / sum(c["held_out_items"] for c in cs))
            cost.append(math.fsum(c["cost_usd"][row["strategy"]] for c in cs))
        assert math.fsum(success) / len(success) == pytest.approx(row["success"], rel=1e-12, abs=0)
        assert math.fsum(cost) / len(cost) == pytest.approx(row["cost_usd"], rel=1e-12, abs=0)
        checked += 1
    assert checked == 3 * len(config["bars"]) * len(config["flavors"])
