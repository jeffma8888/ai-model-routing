"""research/registry-pair.md and research/registry_pair.py (DESIGN 12.22 v1.430, row R40).

The script runs the router on the registry's own pair, `openai/gpt-6-luna` and `openai/gpt-6.1-sol`,
on superlinked/train-a-router-reasoning at a pinned revision: the release's calibration split
calibrates and its final split scores, one task per (dataset, task), at the bars and options of
evidence/routerbench/results.json. When the three pinned files are in the script's default cache,
the note's Results block is compared byte for byte with a fresh run (never a download here); on
every machine the report is checked on a hand-made pair worked out by hand, the refusals and the
download path offline, and each prose number of the note against its Results block.
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
SECTIONS = ["## Facts", "## Method", "## Results", "## Reading it", "## Recommendation", "## Limits",
            "## Regenerate"]
# DESIGN section numbers: the only numbers of the note's prose that are not in the script's output
ALLOWED = {"5.3", "12.2", "12.3", "12.22"}
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


def results_block(text):
    section = text.split("\n## Results\n", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"^```text\n(.*?)^```$", section, re.M | re.S)
    assert len(blocks) == 1, "one text block in ## Results"
    return blocks[0]


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
    text = note()
    known = set(NUMBER.findall(results_block(text))) | ALLOWED
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
    assert COMMAND[2:] in section


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


def _row(split, k, cheap, strong, family):
    return {"id": f"{split}:{k}", "role": split, "dataset": "d", "task": "t x", "family": family,
            "cheap_correct": int(cheap), "cheap_cost_usd": 1.0, "strong_correct": int(strong), "strong_cost_usd": 2.0}


def _grades():
    cal = [_row("calibration", k, k > 0, True, f"f{k}") for k in range(30)]
    final = [_row("final", k, k < 2, True, f"g{k // 2}") for k in range(4)]
    def wrap(split, rows):
        return {"format": "routerbench-paired-grades-v1", "split": split, "rows": rows}
    return wrap("calibration", cal), wrap("final", final)


def test_report_on_a_hand_made_pair(rp):
    # Calibration: v/cheap right on 29 of 30, Wilson bound at 0.95 (29 + 1.92 - 1.96 * sqrt(29 / 30 + 0.9604))
    # / 33.8416 = 0.833; v/strong 30 of 30, 30 / 33.8416 = 0.886; both clear 0.8. cost_effective takes the
    # cheaper v/cheap (mean 1.0 against 2.0), right on 2 of the 4 final items for 4.0, half v/strong's 8.0,
    # and, cleared at 0.500 < 0.8, one cleared task below the bar; cost_blind takes v/strong's higher bound.
    # The oracle pays v/cheap on the two items it gets right and v/strong on the other two, 6.0, 0.750 of
    # 8.0; best_on_calibration is v/strong (30 > 29) and cheapest v/cheap. 30 calibration families, 2 final
    pair = _pair()
    pair["arms"]["cheap"]["model"], pair["arms"]["strong"]["model"] = "cheap", "strong"
    pair["prices_usd_per_million"] = {"cheap": {"input": "1", "output": "2"}, "strong": {"input": "3", "output": "4"}}
    cal, final = _grades()
    lines = [" ".join(line.split()) for line in rp.report(pair, IDS, cal, final, CONFIG)]
    for want in ("families: calibration 30 questions in 30, final 4 in 2, 0 in both splits",
                 "d/t_x 30 4 no 29 30 0.833 0.886", "all 30 4", "v/cheap 0.500 4.000000", "v/strong 1.000 8.000000",
                 "oracle: 1.000 at 0.750 of v/strong's cost", "best_on_calibration: 1.000 at 1.000 of v/strong's cost",
                 "cheapest: 0.500 at 0.500 of v/strong's cost",
                 "0.8 cost_effective 0.500 4.000000 0.500 1 of 1 1 1", "0.8 cost_blind 1.000 8.000000 1.000 1 of 1 0 0",
                 "0.8 cost_effective: d/t_x*", "0.8 cost_blind: none",
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
    (lambda c, f: ({**c, "rows": [dict(c["rows"][0], strong_cost_usd=-1.0)] + c["rows"][1:]}, f), "cost"),
    (lambda c, f: ({**c, "rows": [dict(c["rows"][0], strong_cost_usd=float("nan"))] + c["rows"][1:]}, f), "cost"),
    (lambda c, f: (c, {**f, "rows": [dict(f["rows"][0], id="calibration:0")] + f["rows"][1:]}), "in both splits"),
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
