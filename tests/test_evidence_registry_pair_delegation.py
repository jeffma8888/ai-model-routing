"""evidence/registry-pair-delegation/results.py and results.json (DESIGN 13.17 v1.468, row E25a).

The 13.9 harness on the registry's own pair, superlinked/train-a-router-reasoning at the 12.23 pin: the 12.23
converter's rows carry each model's correctness and the release's cost estimate, no token counts, so the
script gives each row the `low` end of 13.16 v1.466 (E = cost_usd * 10^6 / price_in rounded to a whole token,
a half to the even one; in = E % 5, out = E // 5), then runs `evaluate_delegation` at the 13.14 config on the
12.24 split. Offline, the token rule is checked on costs worked by hand, the refusals, the run's config and the
CLI on hand-made rows, and the committed file's shape; when the three pinned files are in the default cache,
the converter runs in process once per module and the file is rebuilt byte for byte (never a download here).


DESIGN 13.17 v1.470 (row E25b): RESULTS.md, built by tests from results.json (its tables and 13.13's five
Reading it bullets, by 13.14's builder) and from research/registry-pair-delegation.md's Results block (its
`## The high end` bullets), and the `input price` refusal (review iter-333 nit 2). v1.471 writes RESULTS.md and
the refusal and removes the strict xfails that held their tests in v1.470.
"""

import contextlib
import importlib.util
import io
import json
import math
import re
from decimal import Decimal
from fractions import Fraction
from pathlib import Path
from types import SimpleNamespace

import pytest

from model_routing import Registry
from test_evidence_registry_pair_results import FILES, ITEMS
from test_evidence_llmrouterbench_delegation import fenced, section
from test_evidence_response_bank_delegation import reading_bullets as response_bank_reading_bullets

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "registry-pair-delegation"
SCRIPT = FOLDER / "results.py"
RESULTS = FOLDER / "results.json"
CONVERTER = ROOT / "evidence" / "registry-pair" / "convert.py"
NOTE_SCRIPT = ROOT / "research" / "registry_pair_delegation.py"
DELEGATION_SCRIPT = ROOT / "evidence" / "delegation" / "results.py"
MODELS_JSON = ROOT / "model_routing" / "data" / "models.json"
CHEAP, STRONG = "openai/gpt-6-luna", "openai/gpt-6.1-sol"
BARS = [0.8, 0.9]
FLAVORS = ["cost_effective", "cost_blind"]
STRATEGIES = ["decision", "inline", "delegate"]
SIZE = 33_994  # 13.17 Committed
RESULTS_MD = FOLDER / "RESULTS.md"
NOTE = ROOT / "research" / "registry-pair-delegation.md"
REVISION = "63336f25fc54597a8e161a7245613f91bd60177e"
DATASET = "https://huggingface.co/datasets/superlinked/train-a-router-reasoning"
TABLE_CMD = "$ python evidence/delegation/results.py --table evidence/registry-pair-delegation/results.json"
PARENT_CMD = TABLE_CMD + " --bar 0.8 --point 0"
REGENERATE = [
    "python -m pip install -e .",
    "python evidence/registry-pair/convert.py --out registry-pair-matrix.jsonl",
    "python evidence/registry-pair-delegation/results.py --matrix registry-pair-matrix.jsonl "
    "--out evidence/registry-pair-delegation/results.json",
    TABLE_CMD[2:],
    PARENT_CMD[2:],
]
HEADINGS = ["## Method", "## Assumed", "## Results", "## Reading it", "## The high end", "## Regenerate"]
METHOD_PHRASES = ("`openai/gpt-6-luna`", "`openai/gpt-6.1-sol`", "0.1 and 0.5", "2 and 10", "E % 5", "E // 5",
                  "6,099 items", "31 tasks", "12,198 rows", "134", "40", "0.000001", "808", "276", "50 seeds",
                  "0.8 and 0.9", "rounded-up mean", "`decision`", "`inline`", "`delegate`", "C = 8,000")
ASSUMED_PHRASES = ("lossless", "list price", "never a bill", "bounded, not measured", "reasoning", "rounded up",
                   "one vendor", "contamination", "`DESIGN.md` 13.8")


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rpd():
    return load("registry_pair_delegation_results", SCRIPT)


@pytest.fixture(scope="module")
def registry():
    return Registry.load(MODELS_JSON)


def points():
    return load("delegation_results_for_registry_pair", DELEGATION_SCRIPT).points()


def run_main(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


def row(task, item, model, correct, cost):
    return {"task": task, "item": item, "model": model, "correct": correct, "cost_usd": cost}


def hand_rows():
    """Six items of one task, each priced so that E is a whole token, both models on each."""
    rows = []
    for n in range(6):
        rows.append(row("t/one", f"q{n}", CHEAP, n % 3 != 0, (100 + n) * 0.1 / 10 ** 6))
        rows.append(row("t/one", f"q{n}", STRONG, True, (40 + n) * 2.0 / 10 ** 6))
    return rows


def write_jsonl(path, rows, extra=""):
    path.write_text("\n".join(json.dumps(r) for r in rows) + "\n" + extra, encoding="utf-8")


# --- the token rule (13.17 Token rule) -------------------------------------------------------------------

@pytest.mark.parametrize("cost, price, want", [
    (0.0000123, 0.1, (3, 24)),     # E = 123
    (1.25e-06, 0.1, (2, 2)),       # E = 12.5, a half, to 12
    (1.35e-06, 0.1, (4, 2)),       # E = 13.5, a half, to 14
    (0.000101, 2.0, (0, 10)),      # E = 50.5, to 50
    (0.000103, 2.0, (2, 10)),      # E = 51.5, to 52
    (0.0000100001, 2.0, (0, 1)),   # E = 5.00005, to 5
    (0.0, 2.0, (0, 0)),
    (0, 0.1, (0, 0)),
])
def test_the_token_rule_by_hand(rpd, cost, price, want):
    assert rpd.tokens(cost, price) == want
    got_in, got_out = want
    e = Fraction(repr(cost)) * 10 ** 6 / Fraction(str(price))
    # the work cost at list price is the rounded E at the input price, never more than half a token away
    assert abs(Fraction(got_in + rpd.RATIO * got_out) - e) <= Fraction(1, 2)


@pytest.mark.parametrize("cost", [True, False, "0.1", None, math.nan, math.inf, -1e-06])
def test_the_token_rule_refuses_a_bad_cost(rpd, cost):
    with pytest.raises(ValueError) as caught:
        rpd.tokens(cost, 0.1)
    assert str(caught.value).startswith("cost_usd")


def test_the_constants(rpd):
    assert (rpd.RATIO, rpd.BARS, rpd.SEEDS, rpd.KEYS) == (5, (0.8, 0.9), 50, ("config", "tasks", "summary"))
    assert Path(rpd.REGISTRY).resolve() == MODELS_JSON


# --- matrix (13.17 Matrix and Refused) -------------------------------------------------------------------

def test_matrix_by_hand(rpd, registry):
    rows = [row("bbh/navigate", "a", CHEAP, True, 0.0000123), row("bbh/navigate", "a", STRONG, False, 0.000103)]
    before = json.dumps(rows)
    got = rpd.matrix(rows, registry)
    assert got == [
        {"task": "bbh/navigate", "item": "a", "model": CHEAP, "correct": True, "input_tokens": 3, "output_tokens": 24},
        {"task": "bbh/navigate", "item": "a", "model": STRONG, "correct": False, "input_tokens": 2,
         "output_tokens": 10},
    ]
    assert [list(r) for r in got] == [["task", "item", "model", "correct", "input_tokens", "output_tokens"]] * 2
    assert json.dumps(rows) == before


def edited_registry(tmp_path, change):
    data = json.loads(MODELS_JSON.read_text(encoding="utf-8"))
    for m in data["models"]:
        if m["id"] == CHEAP:
            change(m)
    path = tmp_path / "models.json"
    path.write_text(json.dumps(data), encoding="utf-8")
    return Registry.load(path)


@pytest.mark.parametrize("change", [
    lambda m: m.update(price_out=0.6),
    lambda m: m.update(price_tiers=[{"above_input_tokens": 100000, "price_in": 0.2, "price_out": 1.0}]),
])
def test_matrix_refuses_a_model_off_the_ratio(rpd, tmp_path, change):
    with pytest.raises(ValueError) as caught:
        rpd.matrix(hand_rows(), edited_registry(tmp_path, change))
    assert str(caught.value).startswith("output price") and CHEAP in str(caught.value)


def test_matrix_refuses_a_model_not_in_the_registry(rpd, registry):
    with pytest.raises(ValueError) as caught:
        rpd.matrix([row("t/one", "q0", "example/none", True, 0.0001)], registry)
    assert str(caught.value).startswith("model not in the registry") and "example/none" in str(caught.value)


# --- run and the CLI (13.17 Config and CLI) --------------------------------------------------------------

def test_run_passes_the_13_14_config(rpd, registry):
    result = rpd.run(rpd.matrix(hand_rows(), registry), registry)
    assert list(result) == ["config", "tasks", "summary"]
    assert result["config"] == {"bars": BARS, "seeds": list(range(50)), "flavors": FLAVORS, "points": points(),
                                "parents": [CHEAP, STRONG], "calibration_fraction": 0.5, "min_samples": 30,
                                "confidence": 0.95}
    assert result["tasks"] == {"t/one": {"items": 6, "models": [CHEAP, STRONG]}}


def test_the_cli_writes_the_run(rpd, registry, tmp_path):
    matrix = tmp_path / "m.jsonl"
    write_jsonl(matrix, hand_rows(), extra="\n")
    out = tmp_path / "r.json"
    code, stdout, stderr = run_main(rpd, ["--matrix", str(matrix), "--out", str(out)])
    assert (code, stdout, stderr) == (0, "", "")
    want = json.dumps(rpd.run(rpd.matrix(hand_rows(), registry), registry), indent=2) + "\n"
    assert out.read_text(encoding="utf-8") == want
    assert sorted(p.name for p in tmp_path.iterdir()) == ["m.jsonl", "r.json"]


def test_the_cli_refuses_an_out_that_names_an_input(rpd, tmp_path, monkeypatch):
    matrix = tmp_path / "m.jsonl"
    write_jsonl(matrix, hand_rows())
    before = matrix.read_bytes()
    code, _, stderr = run_main(rpd, ["--matrix", str(matrix), "--out", str(matrix)])
    assert code == 2 and stderr.startswith("error: --out") and "--matrix" in stderr
    assert matrix.read_bytes() == before
    part = tmp_path / "r.json.part"  # the `.part` file of `--out` names the matrix
    part.write_bytes(before)
    code, _, stderr = run_main(rpd, ["--matrix", str(part), "--out", str(tmp_path / "r.json")])
    assert code == 2 and stderr.startswith("error: --out") and part.read_bytes() == before
    assert not (tmp_path / "r.json").exists()
    copy = tmp_path / "models.json"
    copy.write_bytes(MODELS_JSON.read_bytes())
    monkeypatch.setattr(rpd, "REGISTRY", copy)
    code, _, stderr = run_main(rpd, ["--matrix", str(matrix), "--out", str(copy)])
    assert code == 2 and stderr.startswith("error: --out") and stderr.count("\n") == 1
    assert copy.read_bytes() == MODELS_JSON.read_bytes()


def test_the_cli_names_an_invalid_line(rpd, tmp_path):
    matrix = tmp_path / "m.jsonl"
    matrix.write_text(json.dumps(hand_rows()[0]) + "\nnot json\n", encoding="utf-8")
    out = tmp_path / "r.json"
    code, stdout, stderr = run_main(rpd, ["--matrix", str(matrix), "--out", str(out)])
    assert code == 1 and stdout == "" and stderr.startswith(f"error: {matrix}:2: invalid JSON:")
    assert stderr.count("\n") == 1 and not out.exists() and not (tmp_path / "r.json.part").exists()


def test_the_cli_error_is_one_line(rpd, tmp_path):
    matrix = tmp_path / "m.jsonl"
    write_jsonl(matrix, [row("t/one", "q0", "example/a\nb", True, 0.0001)])
    code, _, stderr = run_main(rpd, ["--matrix", str(matrix), "--out", str(tmp_path / "r.json")])
    assert code == 1 and stderr.startswith("error: model not in the registry") and stderr.count("\n") == 1
    assert sorted(p.name for p in tmp_path.iterdir()) == ["m.jsonl"]


# --- the committed file (13.17 Committed) ----------------------------------------------------------------

def committed():
    return RESULTS.read_text(encoding="utf-8")


def test_the_committed_file_is_its_own_dump_and_small():
    text = committed()
    assert len(text.encode("utf-8")) == SIZE < 300_000
    assert text == json.dumps(json.loads(text), indent=2) + "\n"


def test_the_committed_file_has_the_config_tasks_and_rows():
    data = json.loads(committed())
    assert list(data) == ["config", "tasks", "summary"]
    assert data["config"] == {"bars": BARS, "seeds": list(range(50)), "flavors": FLAVORS, "points": points(),
                              "parents": [CHEAP, STRONG], "calibration_fraction": 0.5, "min_samples": 30,
                              "confidence": 0.95}
    assert data["tasks"] == {t: {"items": n, "models": [CHEAP, STRONG]} for t, n in sorted(ITEMS.items())}
    assert len(data["tasks"]) == 31 and sum(ITEMS.values()) == 6099
    keys = [(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]) for r in data["summary"]]
    assert len(keys) == len(set(keys)) == 96
    assert set(keys) == {(b, f, p, parent, s) for b in BARS for f in FLAVORS for p in range(4)
                         for parent in (CHEAP, STRONG) for s in STRATEGIES}
    assert all(r["cost_usd"] > 0 and 0 <= r["success"] <= 1 for r in data["summary"])


# --- the pinned files, only when already cached (the converter's main, once per module) ------------------

@pytest.fixture(scope="module")
def real_rows(tmp_path_factory):
    cv = load("registry_pair_convert_for_delegation", CONVERTER)
    cache = cv.default_cache_dir()
    if not all((cache / name).is_file() for name in FILES):
        pytest.skip("the pinned files are not in the default cache")
    out = tmp_path_factory.mktemp("registry-pair-delegation") / "rows.jsonl"
    with contextlib.redirect_stdout(io.StringIO()):
        assert cv.main(["--out", str(out)]) == 0
    with open(out, encoding="utf-8") as f:
        return [json.loads(line) for line in f]


def test_the_committed_file_is_a_fresh_run(rpd, registry, real_rows):
    result = rpd.run(rpd.matrix(real_rows, registry), registry)
    assert json.dumps(result, indent=2) + "\n" == committed()


def test_the_token_rule_is_the_note_scripts_low_end_on_every_row(rpd, registry, real_rows):
    note = load("registry_pair_delegation_note_for_results", NOTE_SCRIPT)
    whole = halves = zero = 0
    largest = Fraction(0)
    for r in real_rows:
        price = registry.get(r["model"]).price_in
        exact, change, low, _ = note.tokens(SimpleNamespace(model=r["model"], cost_usd=r["cost_usd"]), registry)
        assert rpd.tokens(r["cost_usd"], price) == low, r["item"]
        whole += exact.denominator == 1
        halves += exact - math.floor(exact) == Fraction(1, 2)
        zero += low == (0, 0)
        largest = max(largest, change)
    assert (len(real_rows), len(real_rows) - whole, halves, zero) == (12198, 134, 40, 0)
    assert largest == Fraction(1, 10 ** 6)


# --- the input price (13.17 Refused, v1.470, review iter-333 nit 2) ---------------------------------------

def test_matrix_refuses_a_model_priced_at_zero(rpd, tmp_path):
    with pytest.raises(ValueError) as caught:
        rpd.matrix(hand_rows(), edited_registry(tmp_path, lambda m: m.update(price_in=0, price_out=0)))
    assert str(caught.value).startswith("input price") and CHEAP in str(caught.value)


# --- RESULTS.md (13.17 RESULTS.md, v1.470, row E25b) -------------------------------------------------------

@pytest.fixture(scope="module")
def dr():
    return load("delegation_results_tables_for_registry_pair", DELEGATION_SCRIPT)


def reading_bullets(results):
    """13.13's five Reading it bullets by 13.14's builder, the last naming this folder's results.json."""
    return response_bank_reading_bullets(results)[:4] + [f"`results.json` is {len(RESULTS.read_bytes()):,} bytes."]


NOTE_ROW = re.compile(
    r"^  (low|high) +(\S+) +(cost_effective|cost_blind) +(0\.\d) +C ([\d,]+) (separate|folded) +([\d.]+) +([\d.]+) +"
    r"(\d+) of (\d+) +([\d.]+) +([\d.]+) +([\d.]+) +([\d.]+) +(\d+) of (\d+)$")
NOTE_ENDS = re.compile(
    r"^  ends compared: (\d+) of (\d+) \(parent, flavor, bar, point\) groups have a task whose mode or delegate "
    r"differs between the ends, at most (\d+) of (\d+) tasks in one group, at point (\d+)$")
NOTE_FIELDS = ("dec_success", "dec_cost", "delegated", "tasks", "inl_success", "inl_cost", "del_success", "del_cost",
               "other", "of")


def note_results():
    """The note's Results block: {(end, parent, flavor, bar, point): fields}, in its order, and its ends line."""
    block = fenced(section(NOTE.read_text(encoding="utf-8"), "## Results"), "text")[0]
    index = {(p["context_tokens"], p["inline_separate_call"]): k for k, p in enumerate(points())}
    rows, ends = {}, []
    for line in block.split("\n"):
        m = NOTE_ROW.match(line)
        if m:
            g = m.groups()
            point = index[(int(g[4].replace(",", "")), g[5] == "separate")]
            rows[(g[0], g[1], g[2], g[3], point)] = dict(zip(NOTE_FIELDS, g[6:]))
        e = NOTE_ENDS.match(line)
        if e:
            ends.append(tuple(int(x) for x in e.groups()))
    assert len(ends) == 1
    return rows, ends[0]


def high_end_bullets(rows, ends):
    """The `## The high end` bullets: the ends line, each group whose decision delegates another count of
    tasks at the two ends, and always delegating and always inline at the two ends."""
    groups, of, most, tasks, at = ends
    low = [(key[1:], fields) for key, fields in rows.items() if key[0] == "low"]
    assert len(low) == of == len(rows) - len(low)
    moved = [(key, lo, rows[("high",) + key]) for key, lo in low if lo["delegated"] != rows[("high",) + key]["delegated"]]
    assert len(moved) == groups
    assert max(abs(int(lo["delegated"]) - int(hi["delegated"])) for _, lo, hi in moved) == most
    assert {key[3] for key, _, _ in moved} == {at} and all(f["tasks"] == str(tasks) for f in rows.values())
    bullets = [f"{groups} of the {of} (parent, flavor, bar, point) groups have a task whose mode or delegate differs "
               f"between the ends, at most {most} of the {tasks} tasks in one group, all at point {at}, where inline "
               "work folds into the parent's next call."]
    for (parent, flavor, bar, point), lo, hi in moved:
        bullets.append(f"`{parent}` as parent, `{flavor}`, bar {bar}, point {point}: the decision delegates "
                       f"{lo['delegated']} of {tasks} tasks at the low end and {hi['delegated']} at the high end, at "
                       f"{lo['dec_cost']} and {hi['dec_cost']} USD for held-out success {lo['dec_success']} and "
                       f"{hi['dec_success']}; always inline costs {lo['inl_cost']} and {hi['inl_cost']}.")
    for key, lo in low:
        hi = rows[("high",) + key]
        assert (lo["del_success"], lo["del_cost"], lo["inl_success"]) == (hi["del_success"], hi["del_cost"], hi["inl_success"])
    separate = [p["inline_separate_call"] for p in points()]

    def gap(parent, apart):
        gaps = {Decimal(rows[("high",) + key]["inl_cost"]) - Decimal(lo["inl_cost"])
                for key, lo in low if key[0] == parent and separate[key[3]] == apart}
        assert len(gaps) == 1 and min(gaps) > 0
        return str(gaps.pop())

    parents = list(dict.fromkeys(key[0] for key, _ in low))
    assert parents == [CHEAP, STRONG]
    bullets.append("Always delegating has the same held-out success and cost at both ends in every group, and always "
                   "inline the same success; always inline costs more at the high end, by one amount at every bar, "
                   f"flavor and context of a separate call: {gap(CHEAP, True)} USD with `{CHEAP}` as parent and "
                   f"{gap(STRONG, True)} with `{STRONG}`, and {gap(CHEAP, False)} and {gap(STRONG, False)} folded "
                   "into the next call.")
    return bullets


def test_reading_bullets_on_the_committed_numbers():
    """Plain: 13.14's builder on the committed file gives the numbers 13.17 v1.470 states."""
    bullets = reading_bullets(json.loads(committed()))
    assert "all 12 of their decision rows" in bullets[0] and "0.160 and 0.316 at bars 0.8 and 0.9." in bullets[0]
    assert bullets[1] == ("At bar 0.8 and point 0 (8,000 context tokens), averaged over the 2 parents, the "
                          "`cost_effective` decision costs 17.8866 USD on a held-out half against 28.8911 for always "
                          "inline (1.62 times as much), with held-out success 0.906 against 0.903.")
    assert bullets[2] == ("At bar 0.9 and point 0 it costs 20.2852 USD against 28.8911 for always inline, with "
                          "held-out success 0.917 against 0.903.")
    assert bullets[3] == ("At bar 0.8 and point 0 the `cost_effective` decision costs more than always inline for 1 of "
                          "the 2 parents: `openai/gpt-6-luna` (4.8767 against 3.0841 USD, held-out success 0.906 "
                          "against 0.884).")
    assert bullets[4] == "`results.json` is 33,994 bytes."


def test_high_end_bullets_on_the_note_numbers():
    """Plain: the builder on the note's Results block gives the moves 13.17 v1.470 states."""
    bullets = high_end_bullets(*note_results())
    assert len(bullets) == 6
    assert bullets[0].startswith("4 of the 32 (parent, flavor, bar, point) groups") and "at most 1 of the 31" in bullets[0]
    assert bullets[1] == ("`openai/gpt-6-luna` as parent, `cost_effective`, bar 0.8, point 3: the decision delegates 9 "
                          "of 31 tasks at the low end and 10 at the high end, at 3.730746 and 3.927148 USD for held-out "
                          "success 0.912 and 0.912; always inline costs 0.555591 and 0.925166.")
    assert [b.split(":")[0] for b in bullets[2:5]] == [
        "`openai/gpt-6-luna` as parent, `cost_effective`, bar 0.9, point 3",
        "`openai/gpt-6.1-sol` as parent, `cost_effective`, bar 0.8, point 3",
        "`openai/gpt-6.1-sol` as parent, `cost_effective`, bar 0.9, point 3"]
    assert "by one amount" in bullets[5]
    for amount in ("0.739149 USD", "6.806976 with", "0.369575 and 3.403488 folded"):
        assert amount in bullets[5], amount


def test_results_md_structure():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert text.split("\n")[0] == "# Delegation on the registry pair: inline or sub-agent on held-out questions"
    text.encode("ascii")
    assert "\u2013" not in text and "\u2014" not in text
    for needle in (DATASET, REVISION, "2026-10-21", "license: other", "mixed-mit-and-apache-2.0",
                   "not a relicensing of its components", "(results.json)", "(../registry-pair/README.md)",
                   "(../registry-pair/RESULTS.md)", "(../../research/registry-pair-delegation.md)",
                   "`model_routing/data/models.json`"):
        assert needle in text, needle
    assert [line for line in text.split("\n") if line.startswith("## ")] == HEADINGS
    method = section(text, "## Method")
    for phrase in METHOD_PHRASES:
        assert phrase in method, phrase
    assumed = section(text, "## Assumed")
    for phrase in ASSUMED_PHRASES:
        assert phrase in assumed, phrase


def test_results_md_tables_are_the_committed_file(dr):
    results = json.loads(committed())
    blocks = fenced(section(RESULTS_MD.read_text(encoding="utf-8"), "## Results"), "text")
    assert len(blocks) == 2
    assert blocks[0] == TABLE_CMD + "\n" + dr.table(results).rstrip("\n")
    assert blocks[1] == PARENT_CMD + "\n" + dr.parent_table(results, 0.8, 0).rstrip("\n")


def test_results_md_reading_it_is_built_from_the_committed_file():
    reading = section(RESULTS_MD.read_text(encoding="utf-8"), "## Reading it")
    assert [line[2:] for line in reading.split("\n") if line.startswith("- ")] == reading_bullets(json.loads(committed()))


def test_results_md_high_end_is_built_from_the_note():
    high = section(RESULTS_MD.read_text(encoding="utf-8"), "## The high end")
    assert [line[2:] for line in high.split("\n") if line.startswith("- ")] == high_end_bullets(*note_results())
    opening = high[:high.index("\n- ")]
    for needle in ("`low` end", "(../../research/registry-pair-delegation.md)", "release's own split", "`63336f2`",
                   "no seeds", "50 seeded halves"):
        assert needle in opening, needle


def test_results_md_regenerate_block():
    regenerate = section(RESULTS_MD.read_text(encoding="utf-8"), "## Regenerate")
    blocks = fenced(regenerate, "bash")
    assert len(blocks) == 1 and blocks[0].split("\n") == REGENERATE
    before = regenerate[:regenerate.index("```bash")]
    for needle in ("7,522,421", "`~/.cache/ai-model-routing-evidence/registry-pair/`", "sha256", "not committed"):
        assert needle in before, needle
