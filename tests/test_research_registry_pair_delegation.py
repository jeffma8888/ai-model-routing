"""research/registry-pair-delegation.md and research/registry_pair_delegation.py (DESIGN 13.16 v1.466, row R42).

The script asks whether superlinked/train-a-router-reasoning, whose rows give each of the registry's own two models'
correctness and USD cost and no token counts, can score the 13.5 inline-or-sub-agent decision, each model as the
parent. Both models list output at five times input, so a row's cost fixes E = in + 5 * out (input-equivalent
tokens) and the script prices every row at both ends of what the inline path re-reads, `low` (out = E // 5) and
`high` (in = E), on the release's split at the points of evidence/response-bank-delegation/results.json. When the
three pinned files are in the default cache the note's Results block is compared byte for byte with a fresh run
(never a download here); on every machine the two ends and the report are checked on hand-made rows worked out by
hand, the refusals offline, and each prose number of the note against its Results block.
"""

import ast
import contextlib
import dataclasses
import importlib.util
import io
import re
from fractions import Fraction
from pathlib import Path

import pytest

from model_routing import Outcome, PriceTier, Registry

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "registry_pair_delegation.py"
NOTE = ROOT / "research" / "registry-pair-delegation.md"
INDEX = ROOT / "research" / "README.md"
COMMAND = "$ python research/registry_pair_delegation.py"
SECTIONS = ["## Facts", "## Method", "## Results", "## Reading it", "## Recommendation", "## Limits",
            "## Regenerate"]
# DESIGN section numbers: the only numbers of the note's prose that are not in the script's output
ALLOWED = {"13.2", "13.3", "13.9"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?%?")
CHEAP, STRONG = "openai/gpt-6-luna", "openai/gpt-6.1-sol"
ROW = re.compile(r"^  (low|high) +(\S+) +(cost_effective|cost_blind) +(0\.\d) +(C [\d,]+ (?:separate|folded)) +"
                 r"([\d.]+) +([\d.]+) +(\d+) of (\d+) +([\d.]+) +([\d.]+) +([\d.]+) +([\d.]+) +(\d+) of (\d+)$", re.M)


def _load():
    spec = importlib.util.spec_from_file_location("research_registry_pair_delegation", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rpd():
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


def rows(block):
    """{(end, parent, flavor, bar, point): (decision success, cost, delegated, tasks, inline success, cost,
    delegate success, cost, other delegate)}."""
    found = {}
    for m in ROW.findall(block):
        key, rest = m[:5], m[5:]
        assert key not in found, key
        found[key] = rest[:4] + rest[4:8] + rest[8:9]
    return found


# --- the pinned run (skips where the three pinned files are not cached, as in CI) ---

def test_note_results_block_is_the_script_output(rpd):
    cache = rpd.RP.default_cache_dir()
    if not all((cache / name).is_file() for name in rpd.RP.FILES):
        pytest.skip("the three pinned files are not in the default cache")
    code, out, err = run(rpd, [])
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
    # the pin table's byte counts are the pinned FILES, which test_note_states_the_pins checks
    prose = re.sub(r"^\| `[^`\n]+` \| [\d,]+ \| `[0-9a-f]{64}` \|$", "", prose, flags=re.M)
    prose = re.sub(r"`[^`\n]*`", "", prose)
    stray = sorted(set(NUMBER.findall(prose)) - known)
    assert not stray, stray


def test_the_block_has_every_line_of_the_grid():
    found = rows(results_block(note()))
    points = ("C 8,000 separate", "C 64,000 separate", "C 200,000 separate", "C 8,000 folded")
    assert sorted(found) == sorted((e, p, f, b, q) for e in ("low", "high") for p in (CHEAP, STRONG)
                                   for f in ("cost_effective", "cost_blind") for b in ("0.8", "0.9") for q in points)


def test_facts_are_built_from_the_block():
    text, block = note(), results_block(note())
    found = rows(block)
    ends = re.findall(r"^  ends compared: (\d+) of (\d+) \(parent, flavor, bar, point\) groups have a task whose mode "
                      r"or delegate differs between the ends, at most (\d+) of (\d+) tasks in one group, at point "
                      r"(\d+)$", block, re.M)
    assert len(ends) == 1
    moved, groups, most, tasks, point = ends[0]
    assert (f"- The ends barely move the decision: {moved} of {groups} (parent, flavor, bar, point) groups have a task "
            f"whose mode or delegate differs between them, at most {most} of {tasks} tasks in one group, all at "
            f"point {point}, the folded one.") in text
    assert point == "3" and re.search(r"^  point 3: .*, inline folded into the next call$", block, re.M)
    for parent, bar2, other2 in ((CHEAP, None, None), (STRONG, "0.9", None)):
        sep = {e: found[e, parent, "cost_effective", "0.8", "C 8,000 separate"] for e in ("low", "high")}
        far = {e: found[e, parent, "cost_effective", "0.8", "C 200,000 separate"] for e in ("low", "high")}
        # the decision and the delegate path are the same at both ends; only the inline cost moves
        assert sep["low"][:4] == sep["high"][:4] and sep["low"][6:] == sep["high"][6:]
        d = sep["low"]
        lead = (f"- `{parent}` as parent, `cost_effective`, in a separate call at context 8,000: the decision "
                f"delegates {d[2]} of {d[3]} tasks at bar 0.8 ({d[8]} of them to the other model) for {d[0]}")
        if parent == CHEAP:
            assert far["low"][:4] == far["high"][:4] and far["low"][:2] == d[:2]
            assert (lead + f" held-out success at {d[1]} USD, against {d[4]} at {sep['low'][5]} to {sep['high'][5]} "
                    f"inline; at context 200,000 inline costs {far['low'][5]} to {far['high'][5]} and the decision "
                    f"the same {far['low'][1]}.") in text
        else:
            nine = found["low", parent, "cost_effective", "0.9", "C 8,000 separate"]
            assert nine[:4] == found["high", parent, "cost_effective", "0.9", "C 8,000 separate"][:4]
            assert (lead + f" at {d[1]} USD, against {d[4]} at {sep['low'][5]} to {sep['high'][5]} inline; at bar "
                    f"0.9 {nine[0]} at {nine[1]}, {nine[8]} to the other model.") in text
    fold = {e: found[e, STRONG, "cost_effective", "0.8", "C 8,000 folded"] for e in ("low", "high")}
    assert (f"- Folded into the next call at context 8,000, `{STRONG}` stays inline: {fold['low'][2]} of "
            f"{fold['low'][3]} tasks delegated at the low end and {fold['high'][2]} at the high end, at bar 0.8.") in text


def test_note_states_the_pins(rpd):
    text = note()
    assert f"`{rpd.RP.REVISION}`" in text
    for name, (size, sha256) in rpd.RP.FILES.items():
        assert f"| `{name}` | {size:,} | `{sha256}` |" in text, name
    for quote in ("`license: other`", "`license_name: mixed-mit-and-apache-2.0`"):
        assert quote in text, quote


def test_regenerate_section_states_the_commands():
    section = note().split("\n## Regenerate\n", 1)[1]
    assert "python -m pip install -e ." in section
    assert COMMAND[2:] in section


def test_recommendation_names_the_next_row():
    section = note().split("\n## Recommendation\n", 1)[1].split("\n## ", 1)[0]
    assert "row E25" in section and "room row" in section


def test_research_index_row_and_bullet():
    text = INDEX.read_text(encoding="utf-8")
    found = [line for line in text.splitlines()
             if line.startswith("| [registry-pair-delegation.md](registry-pair-delegation.md) | ")]
    assert len(found) == 1
    assert "[registry_pair_delegation.py](registry_pair_delegation.py)" in found[0]
    assert sum(1 for line in text.splitlines() if line.startswith("- `research/registry-pair-delegation.md` ")) == 1


def test_script_imports_only_the_standard_library_and_named_model_routing_parts():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names, private = set(), set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module if node.module.startswith("model_routing") else node.module.split(".")[0])
            if node.module == "model_routing.delegation_eval":
                private |= {a.name for a in node.names}
    assert names <= {"argparse", "importlib", "json", "statistics", "sys", "fractions", "pathlib", "model_routing",
                     "model_routing.delegation_eval"}, names
    assert private == {"_calibrate", "_cell", "_router", "_summary"}, private


# --- hand-made rows, every number worked out by hand ---

def registry():
    return Registry.load(ROOT / "model_routing" / "data" / "models.json")


def test_the_two_ends_by_hand(rpd):
    reg = registry()
    # 8.62e-05 USD at 0.1 per million input tokens is E = 862: low 862 % 5 = 2 in and 862 // 5 = 172 out
    assert rpd.tokens(Outcome("t", "i", CHEAP, True, 8.62e-05), reg) == (862, 0, (2, 172), (862, 0))
    # 0.001094 USD at 2 per million is E = 547
    assert rpd.tokens(Outcome("t", "i", STRONG, True, 0.001094), reg) == (547, 0, (2, 109), (547, 0))
    # a cache category's price makes E 1586.75, rounded to 1587: a 0.25-token change, 0.25 * 0.1 / 1e6 USD
    exact, change, low, high = rpd.tokens(Outcome("t", "i", CHEAP, True, 0.000158675), reg)
    assert (exact, change, low, high) == (Fraction(634700, 400), Fraction(1, 40_000_000), (2, 317), (1587, 0))
    for e, (lo, hi) in ((862, ((2, 172), (862, 0))), (1587, ((2, 317), (1587, 0)))):
        assert lo[0] + 5 * lo[1] == e == hi[0] + 5 * hi[1]


def test_check_ratio_refuses_another_ratio_or_tiers(rpd):
    reg = registry()
    ids = {"cheap": CHEAP, "strong": STRONG}
    rpd.check_ratio(reg, ids)
    for change in ({"price_out": 0.6}, {"price_tiers": (PriceTier(272_000, 0.2, 1.0),)}):
        bad = Registry(dataclasses.replace(m, **change) if m.id == CHEAP else m for m in reg.models)
        with pytest.raises(ValueError, match="is not 5 times input price"):
            rpd.check_ratio(bad, ids)


def _grades():
    def row(split, k):
        return {"id": f"{split}:{k}", "role": split, "dataset": "d", "task": "t x", "family": f"{split}{k}",
                "cheap_correct": 1, "cheap_cost_usd": 0.0001, "strong_correct": 1, "strong_cost_usd": 0.002}

    def wrap(split, n):
        return {"format": "routerbench-paired-grades-v1", "split": split, "rows": [row(split, k) for k in range(n)]}
    return wrap("calibration", 4), wrap("final", 2)


def test_report_on_hand_made_rows(rpd):
    reg = registry()
    config = {"bars": [0.5], "flavors": ["cost_effective"], "min_samples": 1, "confidence": 0.95,
              "points": [{"context_tokens": 8000, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
                          "inline_separate_call": True}]}
    cal, final = _grades()
    lines = rpd.report({}, {"cheap": CHEAP, "strong": STRONG}, cal, final, reg, config)
    found = rows("\n".join(lines) + "\n")
    # E = 1000 for both models on every row: low is 0 in and 200 out, high 1000 in and 0 out. With 4 of 4 right the
    # bound clears 0.5, so the delegate is the cheaper model. Per held item, with C 8,000, B = R = 500 and T = 1:
    # parent luna (0.1 and 0.5): inline low 8000 * 0.1 + 200 * 0.5 + 2 * 200 * 0.1 = 940 per 1e6 USD, high
    # 9000 * 0.1 + 2 * 1000 * 0.1 = 1100; delegated 500 * 0.5 + (500 * 0.1 + 1000 * 0.1) + 2 * 1000 * 0.1 = 600
    # parent sol (2 and 10): inline low 8000 * 2 + 200 * 10 + 2 * 200 * 2 = 18800, high 9000 * 2 + 2 * 1000 * 2 =
    # 22000; delegated 500 * 10 + 150 + 2 * 1000 * 2 = 9150. Two held items each, and every path is right.
    want = {CHEAP: (600, 940, 1100, "0"), STRONG: (9150, 18800, 22000, "1")}
    for parent, (dele, low, high, other) in want.items():
        for end, inline in (("low", low), ("high", high)):
            got = found[end, parent, "cost_effective", "0.5", "C 8,000 separate"]
            assert got == ("1.000", f"{2 * dele / 1e6:.6f}", "1", "1", "1.000", f"{2 * inline / 1e6:.6f}",
                           "1.000", f"{2 * dele / 1e6:.6f}", other), (end, parent, got)
    assert lines[-1] == ("  ends compared: 0 of 2 (parent, flavor, bar, point) groups have a task whose mode or "
                         "delegate differs between the ends, at most 0 of 1 tasks in one group, at point ")
    assert "  E not a whole token: 0 of 12 row costs; the largest cost change of rounding 0.000000000 USD" in lines


def test_an_error_is_one_escaped_line(rpd, monkeypatch):
    def fail(cache):
        raise ValueError("pair.json: size 1\nexpected 2")
    monkeypatch.setattr(rpd.RP, "fetch", fail)
    assert run(rpd, []) == (2, "", "error: pair.json: size 1\\nexpected 2\n")
