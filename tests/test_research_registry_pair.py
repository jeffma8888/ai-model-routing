"""research/registry-pair.md and research/registry_pair.py (DESIGN 12.22 v1.430, row R40).

The script runs the router on the registry's own pair, `openai/gpt-6-luna` and `openai/gpt-6.1-sol`,
on superlinked/train-a-router-reasoning at a pinned revision: the release's calibration split
calibrates and its final split scores, one task per (dataset, task), at the bars and options of
evidence/routerbench/results.json. When the three pinned files are in the script's default cache,
the note's Results block is compared byte for byte with a fresh run (never a download here); on
every machine the report is checked on a hand-made pair worked out by hand, the refusals and the
download path offline, and each prose number of the note against its Results block.

DESIGN 12.22 v1.467 (row R41): `--train` also reads the release's training split, pinned apart from
FILES, and calibrates on it alone and joined with the calibration split, each scored on the final
split. Its block in the note's dated section is compared with a fresh run when the four files are
cached, and its report is checked on a hand-made training split worked out by hand.
"""

import ast
import contextlib
import hashlib
import importlib.util
import io
import json
import re
from pathlib import Path

import pytest

from model_routing import Registry

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "registry_pair.py"
NOTE = ROOT / "research" / "registry-pair.md"
INDEX = ROOT / "research" / "README.md"
COMMAND = "$ python research/registry_pair.py"
TRAIN_COMMAND = "$ python research/registry_pair.py --train"
TRAIN_HEADING = "## Calibrated on the training split (2026-11-18)"
TRAIN_PIN = (11354942, "76b7eb8b8b53ec108ceebfe1caa116a08d8db0b94a21d8c5de911734aa0b0f36")
SECTIONS = ["## Facts", "## Method", "## Results", "## Reading it", "## Recommendation", "## Limits",
            TRAIN_HEADING, "## Regenerate"]
# DESIGN section numbers: the only numbers of the note's prose that are not in the script's output
ALLOWED = {"5.3", "12.2", "12.3", "12.22", "12.24"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?%?")
CHEAP, STRONG = "openai/gpt-6-luna", "openai/gpt-6.1-sol"


def _load():
    spec = importlib.util.spec_from_file_location("research_registry_pair", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def rp():
    return _load()


def run(module, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = module.main(argv)
    return code, out.getvalue(), err.getvalue()


def note():
    return NOTE.read_text(encoding="utf-8")


def results_block(text, heading="## Results"):
    section = text.split(f"\n{heading}\n", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"^```text\n(.*?)^```$", section, re.M | re.S)
    assert len(blocks) == 1, f"one text block in {heading}"
    return blocks[0]


def train_block(text):
    return results_block(text, TRAIN_HEADING)


TRAIN_ROUTED = re.compile(r"^  (0\.\d+) +(cost_effective|cost_blind) +(calibration|train|train\+calibration) +([\d.]+) "
                          r"+([\d.]+) +([\d.]+) +(\d+) of (\d+) +(\d+) +(\d+)$", re.M)


ROUTED = re.compile(r"^  (0\.\d+) +(cost_effective|cost_blind) +([\d.]+) +([\d.]+) +([\d.]+) +(\d+) of (\d+) "
                    r"+(\d+) +(\d+)$", re.M)


def routed_rows(block):
    return {(b, f): rest for b, f, *rest in ROUTED.findall(block)}


def single(block, model):
    found = re.findall(rf"^    {re.escape(model)} +([\d.]+) +([\d.]+)$", block, re.M)
    assert len(found) == 1, model
    return found[0]


def baseline(block, name):
    found = re.findall(rf"^  {name}: ([\d.]+) at ([\d.]+) of {re.escape(STRONG)}'s cost$", block, re.M)
    assert len(found) == 1, name
    return found[0]


# --- the pinned run (skips where the three pinned files are not cached, as in CI) ---

def test_note_results_block_is_the_script_output(rp):
    cache = rp.default_cache_dir()
    if not all((cache / name).is_file() for name in rp.FILES):
        pytest.skip("the three pinned files are not in the default cache")
    code, out, err = run(rp, [])
    assert (code, err) == (0, "")
    assert results_block(note()) == COMMAND + "\n" + out


# --- the note, on every machine ---

def test_note_sections_in_order():
    assert re.findall(r"^## .*$", note(), re.M) == SECTIONS
    assert note().startswith("# ")


def test_prose_numbers_are_in_the_results_block():
    # v1.467: a number of the prose may come from either block, the dated section's included
    text = note()
    known = set(NUMBER.findall(results_block(text))) | set(NUMBER.findall(train_block(text))) | ALLOWED
    prose = re.sub(r"^```[a-z]*\n.*?^```$", "", text, flags=re.M | re.S)
    prose = re.sub(r"https?://\S+", "", prose)
    prose = re.sub(r"\b\d{4}-\d{2}-\d{2}\b", "", prose)
    # the pin table's byte counts are the script's FILES, which test_note_states_the_pins_and_the_licence checks
    prose = re.sub(r"^\| `[^`\n]+` \| [\d,]+ \| `[0-9a-f]{64}` \|$", "", prose, flags=re.M)
    prose = re.sub(r"`[^`\n]*`", "", prose)
    stray = sorted(set(NUMBER.findall(prose)) - known)
    assert not stray, stray


def test_facts_are_built_from_the_block():
    text, block = note(), results_block(note())
    rows = routed_rows(block)
    assert sorted(rows) == sorted((b, f) for b in ("0.6", "0.7", "0.8", "0.9") for f in ("cost_effective", "cost_blind"))
    head = re.findall(r"^  families: calibration ([\d,]+) questions in [\d,]+, final ([\d,]+) in [\d,]+, (\d+) in both "
                      r"splits$", block, re.M)
    tasks = re.findall(r"^\S+ at \w+ \([^)]*\): (\d+) tasks, ", block, re.M)
    assert len(head) == 1 and len(tasks) == 1
    cal, final, both = head[0]
    assert (f"- Split: the release's own, {cal} calibration questions calibrate and {final} final ones score, "
            f"{tasks[0]} tasks, one per (dataset, task) pair, and {'no' if both == '0' else both} famil"
            f"{'y' if both in ('0', '1') else 'ies'} of related questions in both splits.") in text
    (s1, c1), (s2, c2) = single(block, CHEAP), single(block, STRONG)
    assert (f"- Alone on the final split: `{CHEAP}` {s1} held-out success for {c1} USD, `{STRONG}` {s2} for "
            f"{c2} USD.") in text
    e8, e9 = rows["0.8", "cost_effective"], rows["0.9", "cost_effective"]
    assert (f"- `cost_effective` at bar 0.8: {e8[0]} held-out at {e8[2]} of `{STRONG}`'s cost, {e8[5]} of "
            f"{e8[4]} tasks on `{CHEAP}`; at bar 0.9: {e9[0]} at {e9[2]}, {e9[5]} tasks on it.") in text
    blind = {(rows[b, "cost_blind"][0], rows[b, "cost_blind"][2]) for b in ("0.6", "0.7", "0.8", "0.9")}
    assert blind == {baseline(block, "best_on_calibration")}
    (bs, bc), = blind
    assert f"- `cost_blind` at every bar: {bs} at {bc}, the `best_on_calibration` row." in text
    assert all(r[6] == "0" for r in rows.values())
    assert "- No cleared task fell below its bar on the final split, at any bar in either flavor." in text
    os_, oc = baseline(block, "oracle")
    assert all(float(r[0]) < float(os_) for r in rows.values()) and float(s2) < float(os_)
    assert (f"- The per-question oracle: {os_} at {oc}, above every routed row and above `{STRONG}` alone.") in text
    assert all(float(r[0]) < float(s2) for r in rows.values())
    assert f"- No routed row reaches `{STRONG}` alone ({s2})." in text


def test_note_states_the_pins_and_the_licence(rp):
    text = note()
    assert f"`{rp.REVISION}`" in text
    for name, (size, sha256) in rp.FILES.items():
        assert f"| `{name}` | {size:,} | `{sha256}` |" in text, name
    for quote in ("`license: other`", "`license_name: mixed-mit-and-apache-2.0`",
                  "`This is a collection with multiple upstream licenses, not a relicensing of its components. "
                  "Preserve the included notices when redistributing them.`"):
        assert quote in text, quote


def test_regenerate_section_states_the_commands():
    section = note().split("\n## Regenerate\n", 1)[1]
    assert "python -m pip install -e ." in section
    assert COMMAND[2:] + "\n" in section and TRAIN_COMMAND[2:] + "\n" in section


def test_recommendation_names_the_next_row():
    section = note().split("\n## Recommendation\n", 1)[1].split("\n## ", 1)[0]
    assert "row E24" in section and "row DOC28" in section


def test_research_index_row_and_bullet():
    text = INDEX.read_text(encoding="utf-8")
    rows = [line for line in text.splitlines() if line.startswith("| [registry-pair.md](registry-pair.md) | ")]
    assert len(rows) == 1
    assert "[registry_pair.py](registry_pair.py)" in rows[0]
    assert sum(1 for line in text.splitlines() if line.startswith("- `research/registry-pair.md` ")) == 1


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
    assert names <= {"argparse", "hashlib", "json", "math", "sys", "urllib", "pathlib", "model_routing",
                     "model_routing.evaluate", "model_routing.stats"}, names
    assert private == {"_cell", "_split_sums", "_strategies", "_summary"}, private


# --- a hand-made pair, every number worked out by hand ---

IDS = {"cheap": "v/cheap", "strong": "v/strong"}
CONFIG = {"bars": [0.8], "flavors": ["cost_effective", "cost_blind"], "min_samples": 30, "confidence": 0.95}


def _pair(cheap_in="0.10"):
    def arm(name):
        return {"model": name, "settings": {"reasoning": {"effort": "medium"}}}
    return {"format": "routerbench-openai-pair-v1", "arms": {"cheap": arm("gpt-6-luna"), "strong": arm("gpt-6.1-sol")},
            "prices_usd_per_million": {"gpt-6-luna": {"input": cheap_in, "output": "0.50"},
                                       "gpt-6.1-sol": {"input": "2", "output": "10"}}}


def _row(split, k, cheap, strong, family, task="t x"):
    return {"id": f"{split}:{task[0]}{k}", "role": split, "dataset": "d", "task": task, "family": family,
            "cheap_correct": int(cheap), "cheap_cost_usd": 1.0, "strong_correct": int(strong), "strong_cost_usd": 2.0}


def _grades():
    cal = [_row("calibration", k, k > 0, True, f"f{k}") for k in range(30)]
    cal += [_row("calibration", k, True, k > 0, f"h{k}", "u") for k in range(10)]
    final = [_row("final", k, k < 2, True, f"g{k // 2}") for k in range(4)]
    final += [_row("final", k, k < 2, True, "g2", "u") for k in range(4)]
    def wrap(split, rows):
        return {"format": "routerbench-paired-grades-v1", "split": split, "rows": rows}
    return wrap("calibration", cal), wrap("final", final)


def test_report_on_a_hand_made_pair(rp):
    # d/t_x, calibration: v/cheap right on 29 of 30, Wilson bound at 0.95 (29 + 1.92 - 1.96 * sqrt(29 / 30 +
    # 0.9604)) / 33.8416 = 0.833; v/strong 30 of 30, 30 / 33.8416 = 0.886; both clear 0.8. cost_effective takes
    # the cheaper v/cheap (mean 1.0 against 2.0), right on 2 of its 4 final items, and cost_blind v/strong's
    # higher bound, right on 4. d/u (review iter-293 should-fix 1): 10 calibration items, below min_samples
    # 30, so it never clears; v/cheap 10 of 10, 10 / 13.8416 = 0.722, v/strong 9 of 10, 0.596, so both
    # flavors fall back to v/cheap, right on 2 of 4. cost_effective: 4 of 8 for 8.0, half v/strong's 16.0,
    # 1 of 2 cleared, and 1 cleared task below the bar (d/t_x at 0.500), where counting every cell below the
    # bar gives 2; cost_blind: 6 of 8 for 12.0, 0.750, 0 cleared below the bar, where every cell gives 1.
    # The oracle pays v/cheap on the four items it gets right and v/strong on the other four, 12.0, 0.750 of
    # 16.0; best_on_calibration is v/strong on d/t_x (30 > 29) and v/cheap on d/u (10 > 9), 6 of 8 for 12.0;
    # cheapest is v/cheap on both. Families: 40 calibration, 3 final (g0, g1, g2)
    pair = _pair()
    pair["arms"]["cheap"]["model"], pair["arms"]["strong"]["model"] = "cheap", "strong"
    pair["prices_usd_per_million"] = {"cheap": {"input": "1", "output": "2"}, "strong": {"input": "3", "output": "4"}}
    cal, final = _grades()
    lines = [" ".join(line.split()) for line in rp.report(pair, IDS, cal, final, CONFIG)]
    for want in ("families: calibration 40 questions in 40, final 8 in 3, 0 in both splits",
                 "d/t_x 30 4 no 29 30 0.833 0.886", "d/u 10 4 yes 10 9 0.722 0.596", "all 40 8",
                 "v/cheap 0.500 8.000000", "v/strong 1.000 16.000000",
                 "oracle: 1.000 at 0.750 of v/strong's cost", "best_on_calibration: 0.750 at 0.750 of v/strong's cost",
                 "cheapest: 0.500 at 0.500 of v/strong's cost",
                 "0.8 cost_effective 0.500 8.000000 0.500 1 of 2 2 1", "0.8 cost_blind 0.750 12.000000 0.750 1 of 2 1 0",
                 "0.8 cost_effective: d/t_x*, d/u", "0.8 cost_blind: d/u",
                 "cheap: v/cheap at 1 and 2 USD per million input and output tokens, the registry's prices, reasoning medium"):
        assert want in lines, want


def test_check_pair_against_the_registry(rp):
    registry = Registry.load(ROOT / "model_routing" / "data" / "models.json")
    assert rp.check_pair(_pair(), registry) == {"cheap": CHEAP, "strong": STRONG}
    with pytest.raises(ValueError, match="not the registry's"):
        rp.check_pair(_pair(cheap_in="0.20"), registry)
    other = _pair()
    other["arms"]["strong"]["model"] = "gpt-0-none"
    other["prices_usd_per_million"]["gpt-0-none"] = {"input": "2", "output": "10"}
    with pytest.raises(ValueError, match="is not in the registry"):
        rp.check_pair(other, registry)
    with pytest.raises(ValueError, match="format"):
        rp.check_pair(dict(_pair(), format="other"), registry)


@pytest.mark.parametrize("change, message", [
    (lambda c, f: (dict(c, split="final"), f), "format"),
    (lambda c, f: ({**c, "rows": c["rows"] + c["rows"][:1]}, f), "repeated"),
    (lambda c, f: ({**c, "rows": [dict(c["rows"][0], role="final")] + c["rows"][1:]}, f), "role"),
    (lambda c, f: ({**c, "rows": [dict(c["rows"][0], cheap_correct=2)] + c["rows"][1:]}, f), "correct"),
    (lambda c, f: ({**c, "rows": [dict(c["rows"][0], cheap_correct=True)] + c["rows"][1:]}, f), "correct"),
    # review iter-293 nit 3: 0 or 1 as an int, never the float 1.0
    (lambda c, f: ({**c, "rows": [dict(c["rows"][0], cheap_correct=1.0)] + c["rows"][1:]}, f), "correct"),
    (lambda c, f: ({**c, "rows": [dict(c["rows"][0], strong_cost_usd=-1.0)] + c["rows"][1:]}, f), "cost"),
    (lambda c, f: ({**c, "rows": [dict(c["rows"][0], strong_cost_usd=float("nan"))] + c["rows"][1:]}, f), "cost"),
    (lambda c, f: (c, {**f, "rows": [dict(f["rows"][0], id="calibration:t0")] + f["rows"][1:]}), "in both splits"),
    (lambda c, f: (c, {**f, "rows": [dict(r, task="u") for r in f["rows"]]}), "split is empty"),
])
def test_refusals(rp, change, message):
    cal, final = change(*_grades())
    with pytest.raises(ValueError, match=message):
        rp.report(_pair(), IDS, cal, final, CONFIG)


def _tiny_pins(rp, monkeypatch, tmp_path):
    blobs = {name: json.dumps({"name": name}).encode() for name in rp.FILES}
    monkeypatch.setattr(rp, "FILES", {name: (len(b), hashlib.sha256(b).hexdigest()) for name, b in blobs.items()})
    return blobs


class _Response(io.BytesIO):
    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def test_fetch_downloads_an_absent_file_at_the_pinned_revision(rp, monkeypatch, tmp_path):
    blobs = _tiny_pins(rp, monkeypatch, tmp_path)
    asked = []

    def opener(url, timeout):
        asked.append(url)
        return _Response(blobs[url.split(f"/resolve/{rp.REVISION}/", 1)[1]])
    paths = rp.fetch(tmp_path, opener)
    assert sorted(asked) == sorted(rp.url(name) for name in blobs)
    assert all(u.startswith(f"https://huggingface.co/datasets/{rp.REPO}/resolve/{rp.REVISION}/") for u in asked)
    assert {n: p.read_bytes() for n, p in paths.items()} == blobs
    assert not list(tmp_path.rglob("*.part"))
    assert rp.fetch(tmp_path, lambda *a, **k: pytest.fail("a cached file is never downloaded")) == paths


def test_fetch_refuses_a_download_off_its_pin_and_keeps_nothing(rp, monkeypatch, tmp_path):
    _tiny_pins(rp, monkeypatch, tmp_path)
    with pytest.raises(ValueError, match="pair.json: size"):
        rp.fetch(tmp_path, lambda url, timeout: _Response(b"{}"))
    assert [p for p in tmp_path.rglob("*") if p.is_file()] == []


def test_a_cached_file_off_its_pin_is_one_error_line(rp, monkeypatch, tmp_path):
    blobs = _tiny_pins(rp, monkeypatch, tmp_path)
    for name, b in blobs.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b)
    (tmp_path / "pair.json").write_bytes(blobs["pair.json"][:-1] + b" ")
    code, out, err = run(rp, ["--cache", str(tmp_path)])
    assert (code, out) == (2, "")
    assert err.startswith("error: pair.json: sha256 ") and err.count("\n") == 1


def test_an_error_holding_a_newline_is_escaped(rp, monkeypatch, tmp_path):
    blobs = _tiny_pins(rp, monkeypatch, tmp_path)
    for name, b in blobs.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b)
    code, out, err = run(rp, ["--cache", str(tmp_path), "--root", str(tmp_path / "no\nsuch\r")])
    assert (code, out) == (2, "")
    assert err.startswith("error: ") and err.count("\n") == 1 and "\r" not in err
    assert "no\\nsuch\\r" in err


# --- the training split (DESIGN 12.22 v1.467, row R41) ---

def test_note_train_block_is_the_script_output(rp):
    cache = rp.default_cache_dir()
    if not all((cache / name).is_file() for name in [*rp.FILES, rp.TRAIN]):
        pytest.skip("the four pinned files are not in the default cache")
    code, out, err = run(rp, ["--train"])
    assert (code, err) == (0, "")
    assert train_block(note()) == TRAIN_COMMAND + "\n" + out


def test_the_training_file_is_pinned_apart_from_the_three(rp):
    # the default run, the 13.16 delegation script and the 12.23 converter read FILES and download nothing more
    assert rp.TRAIN == "recordings/grades-train.json" and rp.TRAIN not in rp.FILES
    assert rp.TRAIN_PIN == TRAIN_PIN
    section = note().split(f"\n{TRAIN_HEADING}\n", 1)[1].split("\n## ", 1)[0]
    assert f"| `{rp.TRAIN}` | {TRAIN_PIN[0]:,} | `{TRAIN_PIN[1]}` |" in section
    assert "`manifest.json`" in section and "`oid`" in section and "12.24" in section


def test_train_facts_are_built_from_the_block():
    text, block = note(), train_block(note())
    rows = {(b, f, k): rest for b, f, k, *rest in TRAIN_ROUTED.findall(block)}
    bars, sets = ("0.6", "0.7", "0.8", "0.9"), ("calibration", "train", "train+calibration")
    assert sorted(rows) == sorted((b, f, k) for b in bars for f in ("cost_effective", "cost_blind") for k in sets)
    head = re.findall(r"^  families: train ([\d,]+) questions in [\d,]+, (\d+) of them in the final split and (\d+) in "
                      r"the calibration split$", block, re.M)
    total = re.findall(r"^  all +([\d,]+) +([\d,]+) +([\d,]+) +([\d,]+)$", block, re.M)
    assert len(head) == 1 and len(total) == 1
    n_train, in_final, _ = head[0]
    tasks = rows["0.6", "cost_effective", "calibration"][4]

    def clears(k):
        found = [rows[b, "cost_effective", k][3] for b in bars]
        return ", ".join(found[:-1]) + " and " + found[-1]
    blind = {(rows[b, "cost_blind", k][0], rows[b, "cost_blind", k][2]) for b in bars for k in sets[1:]}
    assert len(blind) == 1
    (bs, bc), = blind
    s2 = single(results_block(text), STRONG)[0]
    assert bs == s2
    assert (f"- Calibrated on the training split ({n_train} questions, {'none' if in_final == '0' else in_final} of its "
            f"families in the final split) or on it joined with the calibration split ({total[0][2]}), and scored on the "
            f"same final split: at bars 0.6 to 0.9 `cost_effective` clears {clears('train')} of {tasks} tasks on the "
            f"training split and {clears('train+calibration')} joined, against {clears('calibration')}; no cleared task "
            f"falls below its bar; `cost_blind` gives {bs} at {bc} at every bar on both, the success of `{STRONG}` alone."
            ) in text
    assert all(r[6] == "0" for r in rows.values())
    assert block.endswith("  cleared tasks below the bar on the final split:\n    none\n")
    e8, t8 = rows["0.8", "cost_effective", "calibration"], rows["0.8", "cost_effective", "train"]
    assert (f"- More calibration data: the results file (DESIGN 12.24) keeps its two splits; `cost_effective` at bar 0.8 "
            f"gives {t8[0]} at {t8[2]} on the training split against {e8[0]} at {e8[2]}.") in text


# d/t_x: 30 training rows, v/cheap right on 27 (k >= 3), v/strong on all 30; d/u: 5, v/cheap right on 3, v/strong on 5.
# One d/t_x family is a calibration one (f0) and the d/u family is a final one (g2)
def _train():
    rows = [dict(_row("train", k, k >= 3, True, "f0" if k == 0 else f"k{k}"), role="train") for k in range(30)]
    rows += [dict(_row("train", k, k < 3, True, "g2", "u"), role="train") for k in range(5)]
    return {"format": "routerbench-paired-grades-v1", "split": "train", "rows": rows}


def test_train_report_on_a_hand_made_split(rp):
    # Wilson bounds at 0.95 (z^2 = 3.8415). d/t_x: v/cheap 27 of 30 on training, (0.9 + 0.0640 - 1.96 * sqrt(0.003 +
    # 0.001067)) / 1.1280 = 0.744, under 0.8, so only v/strong (30 of 30, 0.886) clears and both flavors take it,
    # right on 4 of 4 final items; joined, v/cheap 56 of 60, (0.9333 + 0.0320 - 1.96 * sqrt(0.001037 + 0.000267)) /
    # 1.0640 = 0.841, which clears, so cost_effective takes the cheaper v/cheap (2 of 4 right, 0.500, under the bar)
    # and cost_blind v/strong's higher bound (60 of 60, 60 / 63.8415 = 0.940). d/u: 5 training items and 15 joined,
    # both below min_samples 30, so it never clears and falls back to the higher bound, v/strong on both (5 of 5
    # against 3 of 5, 14 of 15 against 13 of 15), right on 4 of 4. So cost_effective on training: 8 of 8 for 16.0,
    # 1.000, 0 on cheap; joined: 6 of 8 for 12.0, 0.750, 1 on cheap, d/t_x cleared below the bar; cost_blind on both:
    # 8 of 8 for 16.0. best_on_calibration on training and joined: v/strong on both tasks (30 > 27, 5 > 3; 60 > 56,
    # 14 > 13), 1.000 at 1.000. The calibration rows are test_report_on_a_hand_made_pair's. Families: 35 training
    # questions in 31 (f0, k1 to k29, g2), g2 in the final split and f0 in the calibration split
    cal, final = _grades()
    lines = [" ".join(line.split()) for line in rp.train_report(IDS, cal, final, _train(), CONFIG)]
    for want in ("families: train 35 questions in 31, 1 of them in the final split and 1 in the calibration split",
                 "d/t_x 30 30 60 4 no, no", "d/u 5 10 15 4 yes, yes", "all 35 40 75 8",
                 "best_on_calibration, calibrated on calibration: 0.750 at 0.750 of v/strong's cost",
                 "best_on_calibration, calibrated on train: 1.000 at 1.000 of v/strong's cost",
                 "best_on_calibration, calibrated on train+calibration: 1.000 at 1.000 of v/strong's cost",
                 "0.8 cost_effective calibration 0.500 8.000000 0.500 1 of 2 2 1",
                 "0.8 cost_effective train 1.000 16.000000 1.000 1 of 2 0 0",
                 "0.8 cost_effective train+calibration 0.750 12.000000 0.750 1 of 2 1 1",
                 "0.8 cost_blind calibration 0.750 12.000000 0.750 1 of 2 1 0",
                 "0.8 cost_blind train 1.000 16.000000 1.000 1 of 2 0 0",
                 "0.8 cost_blind train+calibration 1.000 16.000000 1.000 1 of 2 0 0",
                 "0.8 cost_effective train: d/t_x cheap* -> strong*, d/u cheap -> strong",
                 "0.8 cost_effective train+calibration: d/u cheap -> strong",
                 "0.8 cost_blind train: d/u cheap -> strong", "0.8 cost_blind train+calibration: d/u cheap -> strong",
                 "0.8 cost_effective calibration: d/t_x 0.500", "0.8 cost_effective train+calibration: d/t_x 0.500"):
        assert want in lines, want
    assert "none" not in lines and lines[0].endswith(", bars 0.8, min_samples 30, confidence 0.95 "
                                                     "(evidence/routerbench/results.json config)")


@pytest.mark.parametrize("change, message", [
    (lambda t: dict(t, split="calibration"), "format"),
    (lambda t: {**t, "rows": [dict(t["rows"][0], role="final")] + t["rows"][1:]}, "role"),
    (lambda t: {**t, "rows": t["rows"] + t["rows"][:1]}, "repeated"),
    (lambda t: {**t, "rows": [dict(t["rows"][0], id="calibration:u0")] + t["rows"][1:]}, "training and calibration"),
    (lambda t: {**t, "rows": [dict(t["rows"][0], id="final:t0")] + t["rows"][1:]}, "in both splits"),
    (lambda t: {**t, "rows": [r for r in t["rows"] if r["task"] != "u"]}, "split is empty"),
])
def test_train_refusals(rp, change, message):
    cal, final = _grades()
    with pytest.raises(ValueError, match=message):
        rp.train_report(IDS, cal, final, change(_train()), CONFIG)


def test_fetch_reads_the_training_file_only_when_asked(rp, monkeypatch, tmp_path):
    blobs = _tiny_pins(rp, monkeypatch, tmp_path)
    blobs[rp.TRAIN] = json.dumps({"name": rp.TRAIN}).encode()
    pins = {**rp.FILES, rp.TRAIN: (len(blobs[rp.TRAIN]), hashlib.sha256(blobs[rp.TRAIN]).hexdigest())}
    asked = []

    def opener(url, timeout):
        asked.append(url)
        return _Response(blobs[url.split(f"/resolve/{rp.REVISION}/", 1)[1]])
    assert list(rp.fetch(tmp_path, opener)) == list(rp.FILES) and rp.url(rp.TRAIN) not in asked
    paths = rp.fetch(tmp_path, opener, files=pins)
    assert asked[len(rp.FILES):] == [rp.url(rp.TRAIN)]
    assert list(paths) == list(pins) and paths[rp.TRAIN].read_bytes() == blobs[rp.TRAIN]


def test_main_train_runs_on_cached_files(rp, monkeypatch, tmp_path):
    # the hand-made pair at the registry's own models and prices, written as the four cached files under tiny pins
    cal, final = _grades()
    blobs = {"pair.json": _pair(), "recordings/grades-calibration.json": cal, "recordings/grades-final.json": final,
             rp.TRAIN: _train()}
    blobs = {name: json.dumps(value).encode() for name, value in blobs.items()}
    pins = {name: (len(b), hashlib.sha256(b).hexdigest()) for name, b in blobs.items()}
    monkeypatch.setattr(rp, "FILES", {name: pins[name] for name in rp.FILES})
    monkeypatch.setattr(rp, "TRAIN_PIN", pins[rp.TRAIN])
    for name, b in blobs.items():
        (tmp_path / name).parent.mkdir(parents=True, exist_ok=True)
        (tmp_path / name).write_bytes(b)
    code, out, err = run(rp, ["--cache", str(tmp_path), "--train"])
    assert (code, err) == (0, "")
    lines = [" ".join(line.split()) for line in out.splitlines()]
    assert lines[0].endswith(", bars 0.6 0.7 0.8 0.9, min_samples 30, confidence 0.95 "
                             "(evidence/routerbench/results.json config)")
    assert "families: train 35 questions in 31, 1 of them in the final split and 1 in the calibration split" in lines
    assert "0.8 cost_effective train 1.000 16.000000 1.000 1 of 2 0 0" in lines
    code, out, err = run(rp, ["--cache", str(tmp_path)])
    assert (code, err) == (0, "") and "families: train" not in out
