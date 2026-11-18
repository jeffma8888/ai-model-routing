"""Ledger hand-off results contract (DESIGN 13.15, v1.394, row E23), written before the script and kept as its tests.

The script is a standard-library file outside the package (``evidence/ledger-handoff/results.py``), so
it is loaded from its path by an autouse fixture. The tests use small synthetic files shaped like the
six pinned files (two run settings checks, ``single.jsonl`` and ``decomposed.jsonl`` keyed by
``(L, item)``, and the ``handoff.jsonl`` probe with its four arms), the committed results file and
RESULTS.md, except one, which rebuilds the committed file from the pinned files only when all six are
already in the default cache and skips otherwise (CI never downloads them).

DESIGN 13.15 v1.396 (row E23b): the README evidence opening ends with a paragraph built from the committed
results file, its sixth and last before the first ``###``; ``readme_paragraph`` builds it and refuses a file
that would make its ``but`` or ``yet`` one-sided.

DESIGN 13.15 v1.462 (row DOC29): README Limitations holds, directly after the per-item bullet, a bullet on
the three limits of RESULTS.md ``## Limits``, built from the committed results file; ``limitations_bullet``
builds it and refuses a file that would make one of those limits false.
"""

import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
FOLDER = ROOT / "evidence" / "ledger-handoff"
SCRIPT = FOLDER / "results.py"
RESULTS = FOLDER / "results.json"
RESULTS_MD = FOLDER / "RESULTS.md"
DESIGN = ROOT / "DESIGN.md"
README = ROOT / "README.md"
EVIDENCE = "## Evidence: held-out results on public data"
REVISION = "d891b4eb92abf039431be850646830b486f9e5af"
REPO_URL = "https://github.com/akshitanchan/attention-handoff-tax"
MODEL = "openai/gpt-oss-20b"
REGENERATE = "python evidence/ledger-handoff/results.py --out evidence/ledger-handoff/results.json"
# the six lines of the repository's SHA256SUMS at REVISION that the converter reads, with each file's bytes
SHA256SUMS = """\
910f1b73f19c5027d70f5d2082c222ee2b625b2a6bfdbf8dd322de4f58219dca  config/ledger/config_decomposed.json
bb57bd79b2488e938719b917db888c5bdac5bf6d8597d5e0a084e17b266a4d90  config/ledger/config_handoff.json
7829ba29b1f8396d328d61d8d1ec44abcd74832d67048e439c79cd41af644418  config/ledger/config_single.json
3f88ba82edea7da4a78e06b7859ee49e8da8d2f2ff1a99e2ac2a09332819f39a  data/ledger/decomposed.jsonl
b146c4adc0a21b1ca4658a6a6b65d1d5840357a5db0b224570389203bb1f9cc9  data/ledger/handoff.jsonl
f7554b7be15e8706b923852202552369d633f02ab536a7644c473ffb5e2c7d4b  data/ledger/single.jsonl
"""
SIZES = {"config/ledger/config_decomposed.json": 427, "config/ledger/config_handoff.json": 424,
         "config/ledger/config_single.json": 423, "data/ledger/decomposed.jsonl": 6227860,
         "data/ledger/handoff.jsonl": 1005220, "data/ledger/single.jsonl": 4187684}
STDLIB = {"argparse", "hashlib", "json", "os", "statistics", "sys", "urllib", "pathlib"}
ARMS = ["history", "note_100", "note_300", "note_900"]


def load_lh():
    if not SCRIPT.is_file():
        raise ModuleNotFoundError(f"no script at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("ledger_handoff_results", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def lh():
    return load_lh()


def step(prompt, completion=1, inc=1, abs_=1, balance=0):
    return {"t": 1, "kind": "tx", "prompt_tokens": prompt, "completion_tokens": completion, "reasoning_tokens": 0,
            "finish_reason": "stop", "balance": balance, "fmt_ok": 1, "inc_ok": inc, "abs_ok": abs_,
            "output": "", "tail": ""}


def note(tokens, prompt, completion):
    return {"after_t": 5, "note_tokens": tokens, "prompt_tokens": prompt, "completion_tokens": completion,
            "reasoning_tokens": 0, "finish_reason": "stop", "text": "balance"}


def run(depth, item, ok, steps, notes=None):
    row = {"key": f"{depth}-{item}", "system": "x", "L": depth, "item": item, "final_ok": ok, "all_inc_ok": ok,
           "steps": [step(p, c) for p, c in steps]}
    if notes is not None:
        row["notes"] = [note(*n) for n in notes]
    return row


def arm(flags, prompts, budget=None, note_tokens=0, note_prompt=0, balance=0):
    obj = {"steps": [step(p, 1, inc, abs_) for (inc, abs_), p in zip(flags, prompts)]}
    if budget is not None:
        obj.update({"s": budget, "note_tokens": note_tokens, "note_finish": "stop", "note_balance": balance,
                    "note_prompt_tokens": note_prompt, "note_completion_tokens": 1, "note_reasoning_tokens": 0,
                    "note_text": "balance"})
    return obj


def probe_item(item, last, history, n100, n300, n900):
    pre = [step(5, balance=1), step(5, balance=last)]
    return {"key": str(item), "B": 2, "m": 2, "item": item, "pre": pre,
            "conditions": {"history": arm(*history), "note_100": arm(*n100), "note_300": arm(*n300),
                           "note_900": arm(*n900)}}


def sample():
    """Synthetic records: depth 9 first in each file (one item), then depth 5 (three items)."""
    single = [run(9, 0, 0, [(100, 10)]), run(5, 0, 1, [(10, 1), (20, 2)]), run(5, 1, 1, [(40, 4)]),
              run(5, 2, 0, [(50, 5), (60, 6)])]
    chain = [run(9, 0, 0, [(50, 5)], []), run(5, 0, 0, [(5, 1)], [(7, 3, 9)]), run(5, 1, 0, [(6, 1)], []),
             run(5, 2, 1, [(7, 2)], [(11, 4, 12), (13, 5, 14)])]
    ok, inc_only, none, off_on, lose = [(1, 1), (1, 1)], [(1, 1), (1, 0)], [(1, 0), (0, 0)], [(0, 0), (1, 0)], [(0, 0), (0, 0)]
    handoff = [
        probe_item(0, 50, (ok, [100, 100]), (inc_only, [20, 20], 100, 10, 30, 50), (ok, [30, 30], 300, 20, 30, 49),
                   (ok, [40, 40], 900, 30, 30, 50)),
        probe_item(1, 7, (none, [150, 150]), (ok, [25, 25], 100, 12, 40, 7), (off_on, [35, 35], 300, 22, 40, 7),
                   (ok, [45, 45], 900, 32, 40, 7)),
        probe_item(2, -3, (ok, [200, 200]), (lose, [30, 30], 100, 14, 50, -3), (ok, [40, 40], 300, 24, 50, -3),
                   (ok, [50, 50], 900, 34, 50, 0)),
    ]
    configs = {name: {"command": command, "model": MODEL} for command, name in
               (("single", "config_single.json"), ("decomposed", "config_decomposed.json"),
                ("handoff", "config_handoff.json"))}
    return {"single": single, "chain": chain, "handoff": handoff, "configs": configs}


def write(root, data):
    root.mkdir(parents=True, exist_ok=True)
    for name, obj in data["configs"].items():
        (root / name).write_text(json.dumps(obj), encoding="utf-8")
    for name, rows in (("single.jsonl", data["single"]), ("decomposed.jsonl", data["chain"]),
                       ("handoff.jsonl", data["handoff"])):
        (root / name).write_text("".join(json.dumps(r) + "\n" for r in rows), encoding="utf-8")
    return root


EXPECTED_DEPTHS = [
    {"depth": 5, "items": 3, "final_ok": {"single": 2, "chain": 1}, "chain_lost": 2, "chain_gained": 1,
     "median_prompt_tokens": {"single": 40.0, "chain": 8.0}, "median_completion_tokens": {"single": 4.0, "chain": 10.0},
     "median_notes": 1.0, "median_note_tokens": 11.0},
    {"depth": 9, "items": 1, "final_ok": {"single": 0, "chain": 0}, "chain_lost": 0, "chain_gained": 0,
     "median_prompt_tokens": {"single": 100.0, "chain": 50.0}, "median_completion_tokens": {"single": 10.0, "chain": 5.0},
     "median_notes": 0.0, "median_note_tokens": None},
]
EXPECTED_PROBE = {"items": 3, "pre_steps": 2, "steps": 2, "arms": [
    {"arm": "history", "all_inc_ok": 2, "all_abs_ok": 2, "median_prompt_tokens": 300.0},
    {"arm": "note_100", "note_budget": 100, "all_inc_ok": 2, "all_abs_ok": 1, "inc_ok_lost": 1, "inc_ok_gained": 1,
     "abs_ok_lost": 2, "abs_ok_gained": 1, "note_balance_kept": 3, "median_prompt_tokens": 50.0,
     "median_note_tokens": 12.0, "median_note_prompt_tokens": 40.0},
    {"arm": "note_300", "note_budget": 300, "all_inc_ok": 2, "all_abs_ok": 2, "inc_ok_lost": 0, "inc_ok_gained": 0,
     "abs_ok_lost": 0, "abs_ok_gained": 0, "note_balance_kept": 2, "median_prompt_tokens": 70.0,
     "median_note_tokens": 22.0, "median_note_prompt_tokens": 40.0},
    {"arm": "note_900", "note_budget": 900, "all_inc_ok": 3, "all_abs_ok": 3, "inc_ok_lost": 0, "inc_ok_gained": 1,
     "abs_ok_lost": 0, "abs_ok_gained": 1, "note_balance_kept": 2, "median_prompt_tokens": 90.0,
     "median_note_tokens": 32.0, "median_note_prompt_tokens": 40.0},
]}


def test_source_constants(lh):
    assert lh.REVISION == REVISION
    assert lh.REPO_URL == REPO_URL
    assert lh.BASE_URL == f"https://raw.githubusercontent.com/akshitanchan/attention-handoff-tax/{REVISION}/"
    assert lh.MODEL == MODEL
    assert lh.LICENCE == "CC BY 4.0 (data and config), MIT (code)"


def test_files_are_the_sha256sums_lines_in_path_order(lh):
    pinned = {path: (SIZES[path], digest) for digest, path in (line.split("  ") for line in SHA256SUMS.splitlines())}
    assert lh.FILES == pinned
    assert list(lh.FILES) == sorted(lh.FILES)
    assert len({Path(path).name for path in lh.FILES}) == len(lh.FILES)


def test_default_cache_dir(lh):
    assert lh.default_cache_dir() == Path.home() / ".cache" / "ai-model-routing-evidence" / "ledger-handoff"


def test_standard_library_only(lh):
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {alias.name.split(".")[0] for alias in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module.split(".")[0])
    assert names <= STDLIB, names - STDLIB


def test_verify(lh, tmp_path):
    path = tmp_path / "f.jsonl"
    path.write_bytes(b"abc")
    lh.verify(path, 3, hashlib.sha256(b"abc").hexdigest())
    with pytest.raises(ValueError, match="size 3, expected 4"):
        lh.verify(path, 4, hashlib.sha256(b"abc").hexdigest())
    with pytest.raises(ValueError, match="sha256"):
        lh.verify(path, 3, "0" * 64)


def fake_files(monkeypatch, lh, contents):
    monkeypatch.setattr(lh, "FILES", {path: (len(body), hashlib.sha256(body).hexdigest())
                                      for path, body in contents.items()})


def test_fetch_downloads_each_file_under_its_base_name(lh, monkeypatch, tmp_path):
    contents = {"data/ledger/a.jsonl": b"{}\n", "config/ledger/b.json": b"{}"}
    fake_files(monkeypatch, lh, contents)
    urls = []

    def urlopen(url, timeout=None):
        urls.append(url)
        return io.BytesIO(contents[url[len(lh.BASE_URL):]])

    monkeypatch.setattr(lh.urllib.request, "urlopen", urlopen)
    cache = tmp_path / "cache"
    assert lh.fetch(cache) == cache
    assert urls == [lh.BASE_URL + path for path in contents]
    assert (cache / "a.jsonl").read_bytes() == b"{}\n" and (cache / "b.json").read_bytes() == b"{}"
    assert not list(cache.rglob("*.part"))
    lh.fetch(cache)
    assert len(urls) == 2  # verified files present are not downloaded again


def test_fetch_keeps_and_refuses_a_bad_present_file(lh, monkeypatch, tmp_path):
    fake_files(monkeypatch, lh, {"data/ledger/a.jsonl": b"good"})
    (tmp_path / "a.jsonl").write_bytes(b"evil")
    with pytest.raises(ValueError, match="sha256"):
        lh.fetch(tmp_path)
    assert (tmp_path / "a.jsonl").read_bytes() == b"evil"


def test_fetch_bad_download_leaves_no_part(lh, monkeypatch, tmp_path):
    fake_files(monkeypatch, lh, {"data/ledger/a.jsonl": b"good"})
    monkeypatch.setattr(lh.urllib.request, "urlopen", lambda url, timeout=None: io.BytesIO(b"bad!"))
    with pytest.raises(ValueError, match="sha256"):
        lh.fetch(tmp_path)
    assert not list(tmp_path.iterdir())


@pytest.mark.parametrize("error", [RuntimeError, ValueError])
def test_fetch_wraps_download_errors_as_oserror(lh, monkeypatch, tmp_path, error):
    fake_files(monkeypatch, lh, {"data/ledger/a.jsonl": b"good"})

    def boom(url, timeout=None):
        raise error("no network")

    monkeypatch.setattr(lh.urllib.request, "urlopen", boom)
    with pytest.raises(OSError, match="data/ledger/a.jsonl: download failed: no network"):
        lh.fetch(tmp_path)
    assert not list(tmp_path.iterdir())


def test_build_on_synthetic_files(lh, tmp_path):
    got = lh.build(write(tmp_path, sample()))
    assert got["source"] == {"repo": REPO_URL, "revision": REVISION, "licence": lh.LICENCE,
                             "files": {path: {"bytes": size, "sha256": digest}
                                       for path, (size, digest) in lh.FILES.items()}}
    assert got["model"] == MODEL
    assert got["depths"] == EXPECTED_DEPTHS
    assert got["probe"] == EXPECTED_PROBE
    assert list(got) == ["source", "model", "depths", "probe"]
    assert [list(row) for row in got["probe"]["arms"]] == [list(row) for row in EXPECTED_PROBE["arms"]]


def broken(change):
    data = sample()
    change(data)
    return data


def set_in(rows, index, key, value):
    rows[index][key] = value


REFUSALS = {
    "final_ok 2": (lambda d: set_in(d["single"], 1, "final_ok", 2), "single.jsonl:2: final_ok is not 0 or 1"),
    "final_ok true": (lambda d: set_in(d["chain"], 0, "final_ok", True), "decomposed.jsonl:1: final_ok is not 0 or 1"),
    "negative prompt": (lambda d: d["single"][0]["steps"][0].update(prompt_tokens=-1),
                        r"single.jsonl:1: steps\[0\]: prompt_tokens is outside 0"),
    "float completion": (lambda d: d["chain"][2]["steps"][0].update(completion_tokens=1.0),
                         r"decomposed.jsonl:3: steps\[0\]: completion_tokens is not an int"),
    "no steps": (lambda d: set_in(d["single"], 2, "steps", []), "single.jsonl:3: steps is not a non-empty list"),
    "no notes list": (lambda d: d["chain"][1].pop("notes"), "decomposed.jsonl:2: notes is not a list"),
    "note tokens": (lambda d: d["chain"][1]["notes"][0].pop("note_tokens"),
                    r"decomposed.jsonl:2: notes\[0\]: note_tokens is not an int"),
    "repeated key": (lambda d: set_in(d["single"], 2, "item", 0), r"single.jsonl:3: \(L, item\) \(5, 0\) repeats"),
    "different keys": (lambda d: set_in(d["chain"], 0, "item", 4),
                       r"single.jsonl and decomposed.jsonl hold different \(L, item\) keys, the first \(9, 0\)"),
    "config model": (lambda d: d["configs"]["config_single.json"].update(model="other/model"),
                     "config_single.json: model is 'other/model'"),
    "config command": (lambda d: d["configs"]["config_handoff.json"].update(command="single"),
                       "config_handoff.json: command is 'single'"),
    "missing arm": (lambda d: d["handoff"][1]["conditions"].pop("note_300"), "handoff.jsonl:2: conditions is not"),
    "extra arm": (lambda d: d["handoff"][0]["conditions"].update(note_50={}), "handoff.jsonl:1: conditions is not"),
    "budget": (lambda d: d["handoff"][2]["conditions"]["note_900"].update(s=300), "handoff.jsonl:3: note_900: s is not 900"),
    "probe flag": (lambda d: d["handoff"][0]["conditions"]["history"]["steps"][1].update(abs_ok=None),
                   r"handoff.jsonl:1: history: steps\[1\]: abs_ok is not 0 or 1"),
    "note balance": (lambda d: d["handoff"][0]["conditions"]["note_100"].update(note_balance="50"),
                     "handoff.jsonl:1: note_100: note_balance is not an int"),
    "repeated probe item": (lambda d: set_in(d["handoff"], 2, "item", 1), "handoff.jsonl:3: item 1 repeats"),
    "probe lengths": (lambda d: d["handoff"][2]["conditions"]["note_300"]["steps"].pop(),
                      "handoff.jsonl: the items hold continued steps lists of different lengths"),
}


@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_build_refuses(lh, tmp_path, case):
    change, message = REFUSALS[case]
    with pytest.raises(ValueError, match=message):
        lh.build(write(tmp_path, broken(change)))


def test_read_lines_names_the_line(lh, tmp_path):
    root = write(tmp_path, sample())
    (root / "single.jsonl").write_text(json.dumps(sample()["single"][0]) + "\n\n[1]\n", encoding="utf-8")
    with pytest.raises(ValueError, match="single.jsonl:3: not a JSON object"):
        lh.build(root)
    (root / "single.jsonl").write_bytes(b"{\n")
    with pytest.raises(ValueError, match="single.jsonl:1: not valid UTF-8 JSON"):
        lh.build(root)
    (root / "handoff.jsonl").write_bytes(b"\n")
    (root / "single.jsonl").write_text("".join(json.dumps(r) + "\n" for r in sample()["single"]), encoding="utf-8")
    with pytest.raises(ValueError, match="handoff.jsonl: no record"):
        lh.build(root)


def call_main(lh, argv):
    out, err = io.StringIO(), io.StringIO()
    with contextlib.redirect_stdout(out), contextlib.redirect_stderr(err):
        code = lh.main(argv)
    return code, out.getvalue(), err.getvalue()


def test_main_writes_and_prints_the_results_file(lh, monkeypatch, tmp_path):
    root = write(tmp_path / "cache", sample())
    monkeypatch.setattr(lh, "fetch", lambda cache=None: root)
    out = tmp_path / "results.json"
    code, stdout, stderr = call_main(lh, ["--out", str(out)])
    assert (code, stderr) == (0, "")
    text = json.dumps(lh.build(root), indent=2) + "\n"
    assert out.read_text(encoding="utf-8") == text
    assert stdout == text
    assert not (tmp_path / "results.json.part").exists()


def test_main_checks_out_before_any_download(lh, monkeypatch, tmp_path):
    def fetch(cache=None):
        raise AssertionError("fetched")

    monkeypatch.setattr(lh, "fetch", fetch)
    for value in (str(tmp_path) + "/", str(tmp_path / "no" / "r.json"), str(tmp_path)):
        code, stdout, stderr = call_main(lh, ["--out", value])
        assert (code, stdout) == (2, "")
        assert stderr.startswith("error: --out") and stderr.count("\n") == 1


def test_main_failure_leaves_no_file(lh, monkeypatch, tmp_path):
    data = broken(lambda d: set_in(d["single"], 0, "final_ok", 3))
    root = write(tmp_path / "cache", data)
    monkeypatch.setattr(lh, "fetch", lambda cache=None: root)
    out = tmp_path / "results.json"
    (tmp_path / "results.json.part").write_text("stale", encoding="utf-8")
    code, stdout, stderr = call_main(lh, ["--out", str(out)])
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: single.jsonl:1: final_ok") and stderr.count("\n") == 1
    assert not out.exists() and not (tmp_path / "results.json.part").exists()


def committed():
    return json.loads(RESULTS.read_text(encoding="utf-8"))


def test_committed_results_numbers():
    got = committed()
    assert RESULTS.stat().st_size < 300_000
    assert got["source"]["revision"] == REVISION and got["model"] == MODEL
    rows = {row["depth"]: row for row in got["depths"]}
    assert list(rows) == [20, 50, 100] and all(row["items"] == 100 for row in rows.values())
    assert [rows[d]["final_ok"]["single"] for d in rows] == [49, 4, 0]
    assert [rows[d]["final_ok"]["chain"] for d in rows] == [64, 18, 10]
    assert [rows[d]["chain_lost"] for d in rows] == [18, 3, 0]
    assert [rows[d]["chain_gained"] for d in rows] == [33, 17, 10]
    arms = {row["arm"]: row for row in got["probe"]["arms"]}
    assert list(arms) == ARMS and got["probe"]["items"] == 100
    assert [arms[a]["all_inc_ok"] for a in ARMS] == [73, 79, 77, 80]
    assert [arms[a]["all_abs_ok"] for a in ARMS] == [54, 58, 59, 60]
    assert [(arms[a]["abs_ok_lost"], arms[a]["abs_ok_gained"]) for a in ARMS[1:]] == [(9, 13), (8, 13), (5, 11)]
    assert [arms[a]["note_balance_kept"] for a in ARMS[1:]] == [100, 99, 100]
    assert [(arms[a]["inc_ok_lost"], arms[a]["inc_ok_gained"]) for a in ARMS[1:]] == [(9, 15), (11, 15), (7, 14)]
    medians = [(rows[d]["median_prompt_tokens"]["single"], rows[d]["median_prompt_tokens"]["chain"],
                rows[d]["median_completion_tokens"]["single"], rows[d]["median_completion_tokens"]["chain"],
                rows[d]["median_notes"], rows[d]["median_note_tokens"]) for d in rows]
    assert medians == [(87471.0, 38006.0, 762.5, 1608.0, 3.0, 163.0), (517315.0, 101419.0, 2339.0, 4729.0, 9.0, 176.0),
                       (2029808.0, 206613.0, 10262.0, 10057.0, 19.0, 174.0)]
    assert [arms[a]["median_prompt_tokens"] for a in ARMS] == [30827.0, 7840.5, 8077.0, 8412.5]
    assert [(arms[a]["median_note_tokens"], arms[a]["median_note_prompt_tokens"]) for a in ARMS[1:]] == [
        (137.0, 5093.0), (180.5, 5093.0), (249.5, 5093.0)]


def test_committed_results_rebuild_from_the_pinned_files(lh, tmp_path):
    cache = lh.default_cache_dir()
    if not all((cache / Path(path).name).is_file() for path in lh.FILES):
        pytest.skip("the six pinned files are not all in the default cache")
    out = tmp_path / "results.json"
    code, stdout, stderr = call_main(lh, ["--out", str(out), "--cache", str(cache)])
    assert (code, stderr) == (0, "")
    assert out.read_bytes() == RESULTS.read_bytes()


def number(value):
    if value is None:
        return "-"
    if isinstance(value, float) and value.is_integer():
        value = int(value)
    return f"{value:,}" if isinstance(value, int) else f"{value:,.1f}"


def test_results_md_tables_are_the_committed_numbers():
    text = RESULTS_MD.read_text(encoding="utf-8")
    lines = set(text.splitlines())
    got = committed()
    for row in got["depths"]:
        cells = [row["depth"], row["items"], row["final_ok"]["single"], row["final_ok"]["chain"], row["chain_lost"],
                 row["chain_gained"], row["median_prompt_tokens"]["single"], row["median_prompt_tokens"]["chain"],
                 row["median_completion_tokens"]["single"], row["median_completion_tokens"]["chain"],
                 row["median_notes"], row["median_note_tokens"]]
        assert "| " + " | ".join(number(c) for c in cells) + " |" in lines, row["depth"]
    for row in got["probe"]["arms"]:
        cells = [row["arm"]] + [number(row.get(key)) for key in (
            "note_budget", "all_inc_ok", "all_abs_ok", "inc_ok_lost", "inc_ok_gained", "abs_ok_lost", "abs_ok_gained",
            "note_balance_kept", "median_prompt_tokens", "median_note_tokens", "median_note_prompt_tokens")]
        assert "| `" + cells[0] + "` | " + " | ".join(cells[1:]) + " |" in lines, row["arm"]


def test_results_md_names_a_surrogate_and_its_source():
    text = RESULTS_MD.read_text(encoding="utf-8")
    assert "surrogate" in text
    assert "lossless" not in text.lower()
    for needle in (REPO_URL, REVISION, "CC BY 4.0", "MIT", MODEL, REGENERATE, "DESIGN.md` 13.15"):
        assert needle in text, needle
    # v1.397 (row E23c): the line after the regenerate command says the workflow reruns it
    at = text.splitlines().index(f"- Regenerate (standard library only; about 11 MB downloaded into "
                                 f"`~/.cache/ai-model-routing-evidence/ledger-handoff`): `{REGENERATE}`")
    assert text.splitlines()[at + 1].startswith(
        "- The `evidence` workflow reruns this command on GitHub and fails if `results.json` changes by a byte. ")
    assert "regenerated by hand" not in text
    for arm, lost, gained in (("note_100", 9, 13), ("note_300", 8, 13), ("note_900", 5, 11)):
        assert f"`{arm}` loses {lost} and gains {gained}" in text, arm


def design_13_15():
    text = DESIGN.read_text(encoding="utf-8")
    start = text.index("### 13.15 ")
    end = text.index("\n### 13.16 ", start)  # 13.16 follows it from v1.461 (row DOC38c)
    return text[start:end]


def test_design_specifies_the_converter():
    spec = design_13_15()
    assert spec.startswith("### 13.15 Measured hand-off paths: the ledger runs (`evidence/ledger-handoff/results.py`, v1.394)")
    for needle in (REPO_URL, REVISION, "surrogate", MODEL, "SHA256SUMS", "no price", "Router.decide_delegation",
                   "`chain_lost`", "`note_balance_kept`", "`median_note_prompt_tokens`", "tests/test_evidence_ledger_handoff.py"):
        assert needle in spec, needle


def test_script_docstring_names_its_spec(lh):
    assert "DESIGN 13.15" in lh.__doc__ and "surrogate" in lh.__doc__


def test_sample_is_not_mutated_by_build(lh, tmp_path):
    data = sample()
    before = copy.deepcopy(data)
    lh.build(write(tmp_path, data))
    assert data == before


# --- the README paragraph (DESIGN 13.15 v1.396, row E23b) -------------------------------------

LINK = "[evidence/ledger-handoff/RESULTS.md](evidence/ledger-handoff/RESULTS.md)"


def listed(values, last="and"):
    """Values in file order, joined by `, ` and, before the last, ` and ` (or `last`), integers with commas."""
    words = [f"{value:,}" for value in values]
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + f" {last} " + words[-1]


def readme_paragraph(results):
    """The sixth and last paragraph of the README evidence opening, built from a ledger results file."""
    depths, probe = results["depths"], results["probe"]
    items = {row["items"] for row in depths}
    if len(items) != 1:
        raise ValueError("the depths differ in items")
    history, notes = probe["arms"][0], probe["arms"][1:]
    if history["arm"] != "history":
        raise ValueError("the first probe arm is not `history`")
    if not any(row["chain_lost"] for row in depths):
        raise ValueError("no depth has a chain loss, so `but loses` is one-sided")
    if not any(arm["inc_ok_lost"] for arm in notes):
        raise ValueError("no note arm loses an `inc_ok` item, so `yet loses` is one-sided")
    return (f"Whether work survives a hand-off to a fresh context, measured with `{results['model']}` in every role "
            f"and not priced: {LINK} sets a chain of fresh contexts linked by notes, a surrogate for a sub-agent "
            "hand-off and not that hand-off, against one context holding the whole history, on "
            f"{items.pop():,} ledger items at each depth. The chain solves "
            f"{listed(row['final_ok']['chain'] for row in depths)} against "
            f"{listed(row['final_ok']['single'] for row in depths)} at depths of "
            f"{listed(row['depth'] for row in depths)} steps, but loses "
            f"{listed(row['chain_lost'] for row in depths)} of the items the one context solves. In its probe of "
            f"{probe['items']:,} items {probe['pre_steps']:,} steps in, continuing {probe['steps']:,} steps from a "
            f"note of budget {listed((arm['note_budget'] for arm in notes), 'or')} tokens keeps every continued step "
            f"`inc_ok` on {listed(arm['all_inc_ok'] for arm in notes)} items against {history['all_inc_ok']:,} with "
            f"the history, yet loses {listed(arm['inc_ok_lost'] for arm in notes)} of the items the history keeps "
            f"and gains {listed(arm['inc_ok_gained'] for arm in notes)}")


def opening_paragraphs():
    readme = README.read_text(encoding="utf-8")
    assert readme.count("\n" + EVIDENCE + "\n") == 1
    section = readme.split("\n" + EVIDENCE + "\n", 1)[1].split("\n## ", 1)[0]
    return section.split("\n### ", 1)[0].strip("\n").split("\n\n")


def test_listed_joins_in_order():
    assert listed([7]) == "7"
    assert listed([1, 2]) == "1 and 2"
    assert listed([1000, 2, 3]) == "1,000, 2 and 3"
    assert listed([100, 300, 900], "or") == "100, 300 or 900"


def test_readme_ends_the_evidence_opening_with_the_ledger_paragraph():
    paragraphs = opening_paragraphs()
    assert len(paragraphs) == 6, paragraphs[4:]
    assert paragraphs[5] == readme_paragraph(committed())


def test_readme_paragraph_states_the_committed_numbers():
    text = readme_paragraph(committed())
    for needle in (f"`{MODEL}`", "a surrogate for a sub-agent hand-off and not that hand-off", "on 100 ledger items",
                   "The chain solves 64, 18 and 10 against 49, 4 and 0 at depths of 20, 50 and 100 steps",
                   "but loses 18, 3 and 0 of the items", "In its probe of 100 items 12 steps in, continuing 5 steps",
                   "budget 100, 300 or 900 tokens", "`inc_ok` on 79, 77 and 80 items against 73 with the history",
                   "yet loses 9, 11 and 7 of the items the history keeps and gains 15, 15 and 14"):
        assert needle in text, needle
    assert "lossless" not in text.lower()


def test_readme_paragraph_link_resolves():
    assert LINK in readme_paragraph(committed())
    assert RESULTS_MD.is_file()


def test_readme_paragraph_follows_the_file():
    got = copy.deepcopy(committed())
    got["depths"][1]["final_ok"]["chain"] = 1234
    got["probe"]["arms"].append(dict(got["probe"]["arms"][-1], note_budget=2700, all_inc_ok=81, inc_ok_lost=6,
                                     inc_ok_gained=13))
    text = readme_paragraph(got)
    assert "The chain solves 64, 1,234 and 10 against" in text
    assert "budget 100, 300, 900 or 2,700 tokens" in text
    assert "on 79, 77, 80 and 81 items" in text and "loses 9, 11, 7 and 6" in text and "gains 15, 15, 14 and 13" in text


@pytest.mark.parametrize("change, message", [
    (lambda r: r["depths"][2].update(items=99), "differ in items"),
    (lambda r: r["probe"]["arms"].reverse(), "first probe arm"),
    (lambda r: [row.update(chain_lost=0) for row in r["depths"]], "`but loses`"),
    (lambda r: [arm.update(inc_ok_lost=0) for arm in r["probe"]["arms"][1:]], "`yet loses`"),
])
def test_readme_paragraph_refuses_a_one_sided_file(change, message):
    got = copy.deepcopy(committed())
    change(got)
    with pytest.raises(ValueError, match=message):
        readme_paragraph(got)


def test_design_specifies_the_readme_paragraph():
    spec = design_13_15()
    bullets = [line for line in spec.splitlines() if line.startswith("- README (v1.396, row E23b): ")]
    assert len(bullets) == 1
    for needle in ("the sixth and last before the first `###` (12.8)", "a surrogate for a sub-agent hand-off",
                   "{chain `final_ok`}", "{`chain_lost`}", "{`inc_ok_lost`}", "{`inc_ok_gained`}", "` or ` for the budgets",
                   "never reading as a lossless hand-off", "one-sided", "8,000-byte cap"):
        assert needle in bullets[0], needle
    # v1.397 (row E23c): the workflow reruns the regenerate line, so nothing says it is regenerated by hand
    assert "From v1.397 its regenerate line says the `evidence` workflow reruns it on GitHub" in spec
    assert "Not in the `evidence` workflow yet" not in spec and "regenerated by hand" not in spec
    text = DESIGN.read_text(encoding="utf-8")
    section = text.split("\n### 12.8 ", 1)[1].split("\n### ", 1)[0]
    assert "then (v1.396) a blank line and the 13.15 README paragraph, and by nothing else." in section


# --- the README Limitations bullet (DESIGN 13.15 v1.462, row DOC29) ---------------------------

LIMITATIONS = "## Limitations and non-goals (v1)"
PER_ITEM = "- Choosing the path per item instead would add little "
SPREAD_SHARE = 20  # refuse a spread over 1/20 (5%) of the probe's items, 5 at 100: more could rank one note budget
REGISTRY = ROOT / "model_routing" / "data" / "models.json"


def note_spread(probe):
    """The largest difference between two note arms' all-`inc_ok` counts or between their all-`abs_ok` counts."""
    notes = probe["arms"][1:]
    if not notes:
        raise ValueError("the probe has no note arm")
    return max(max(arm[key] for arm in notes) - min(arm[key] for arm in notes) for key in ("all_inc_ok", "all_abs_ok"))


def registry_ids():
    return {row["id"] for row in json.loads(REGISTRY.read_text(encoding="utf-8"))["models"]}


def limitations_bullet(results, registry=None):
    """The README Limitations bullet on the ledger runs' three limits, built from a ledger results file."""
    depths, probe = results["depths"], results["probe"]
    items = {row["items"] for row in depths}
    if len(items) != 1:
        raise ValueError("the depths differ in items")
    if probe["items"] not in items:
        raise ValueError("the probe's items differ from the depths' items, so `and in the probe` does not hold")
    if probe["arms"][0]["arm"] != "history":
        raise ValueError("the first probe arm is not `history`")
    spread = note_spread(probe)
    if spread * SPREAD_SHARE > probe["items"]:
        raise ValueError(f"the note arms differ by {spread} items, over 5% of the probe's {probe['items']:,}, so "
                         "`ranks no note budget` may not hold")
    if results["model"] in (registry_ids() if registry is None else registry):
        raise ValueError(f"the registry has a row for {results['model']}, so `no price` does not hold")
    return ("- The ledger runs (" + LINK + ") measure work handed to a fresh context, not a delegation decision, and "
            "have three limits. First, a synthetic ledger task with one open model, "
            f"`{results['model']}`, in every role (one run per item at temperature 0.7), so the delegate is never "
            "cheaper per token than the parent and none is chosen from a pool, and on the probe's "
            f"{probe['items']:,} items the note arms' all-`inc_ok` and all-`abs_ok` counts differ by at most "
            f"{spread:,}, which ranks no note budget above another. Second, the hand-off is serial: on "
            f"{items.pop():,} items at each of depths {listed(row['depth'] for row in depths)} and in the probe, a "
            "successor takes over from a note and no parent reads a result back. Third, no price, since "
            "`models.json` has no row for that model. So they show what a note carries forward and at how many "
            "prompt and completion tokens, but not the cost or the success of a delegate whose result a parent "
            "reads, and no `Router.decide_delegation` decision is set beside them (`DESIGN.md` 13.15)")


def limitations_bullets():
    readme = README.read_text(encoding="utf-8")
    assert readme.count("\n" + LIMITATIONS + "\n") == 1
    limits = readme.split("\n" + LIMITATIONS + "\n", 1)[1].split("\n## ", 1)[0]
    return [line for line in limits.splitlines() if line.startswith("- ")]


def test_readme_limitations_name_the_ledger_runs_after_the_per_item_bullet():
    bullets = limitations_bullets()
    per_item = [i for i, b in enumerate(bullets) if b.startswith(PER_ITEM)]
    assert len(per_item) == 1
    assert bullets[per_item[0] + 1] == limitations_bullet(committed())
    assert sum(b.startswith("- The ledger runs (") for b in bullets) == 1
    assert sum(LINK in b for b in bullets) == 1


def test_limitations_bullet_states_the_committed_numbers():
    assert MODEL not in registry_ids()
    assert note_spread(committed()["probe"]) == 3  # all-inc_ok 79, 77 and 80; all-abs_ok 58, 59 and 60
    text = limitations_bullet(committed())
    for needle in (f"one open model, `{MODEL}`, in every role", "on the probe's 100 items",
                   "counts differ by at most 3, which ranks no note budget above another",
                   "on 100 items at each of depths 20, 50 and 100 and in the probe",
                   "no parent reads a result back", "Third, no price, since `models.json` has no row for that model",
                   "not the cost or the success of a delegate whose result a parent reads"):
        assert needle in text, needle
    assert "lossless" not in text.lower()


def test_limitations_bullet_follows_the_file():
    got = copy.deepcopy(committed())
    got["model"] = "acme/ledger-1"
    for row in got["depths"]:
        row["items"] = 1200
    got["depths"].append(dict(got["depths"][-1], depth=200))
    got["probe"]["items"] = 1200
    got["probe"]["arms"][3]["all_abs_ok"] = 62  # 58 to 62 on all-abs_ok, over the 3 of all-inc_ok
    text = limitations_bullet(got)
    assert "one open model, `acme/ledger-1`, in every role (one run per item at temperature 0.7), so " in text
    assert "on the probe's 1,200 items" in text and "differ by at most 4, which" in text
    assert "on 1,200 items at each of depths 20, 50, 100 and 200 and in the probe" in text


@pytest.mark.parametrize("change, registry, message", [
    (lambda r: r["depths"][2].update(items=99), set(), "differ in items"),
    (lambda r: r["probe"]["arms"].reverse(), set(), "first probe arm"),
    (lambda r: r["probe"].update(items=99), set(), "probe's items differ"),
    (lambda r: r["probe"]["arms"][1].update(all_inc_ok=86), set(), "differ by 9 items, over 5% of the probe's 100"),
    (lambda r: r["probe"]["arms"][2].update(all_abs_ok=53), set(), "differ by 7 items, over 5% of the probe's 100"),
    (lambda r: r["probe"]["arms"][1].update(all_inc_ok=83), set(), "differ by 6 items, over 5% of the probe's 100"),
    (lambda r: [row.update(items=40) for row in r["depths"]] and r["probe"].update(items=40), set(),
     "differ by 3 items, over 5% of the probe's 40"),
    (lambda r: r["probe"].update(arms=r["probe"]["arms"][:1]), set(), "no note arm"),
    (lambda r: None, {MODEL}, "`no price`"),
])
def test_limitations_bullet_refuses_a_file_that_breaks_a_limit(change, registry, message):
    got = copy.deepcopy(committed())
    change(got)
    with pytest.raises(ValueError, match=message):
        limitations_bullet(got, registry)


def test_limitations_bullet_holds_at_the_spread_cap():
    got = copy.deepcopy(committed())
    got["probe"]["arms"][1]["all_inc_ok"] = 82  # 77 to 82
    assert "differ by at most 5, which" in limitations_bullet(got, set())


def test_results_md_limits_hold_the_bullets_three_limits():
    text = RESULTS_MD.read_text(encoding="utf-8")
    limits = text.split("\n## Limits\n", 1)[1].split("\n## ", 1)[0]
    bullets = [line for line in limits.splitlines() if line.startswith("- ")]
    assert len(bullets) == 3
    assert bullets[0].startswith("- A synthetic ledger task and one open model in every role, one run per item at "
                                 "temperature 0.7 (the run settings), so the delegate is never cheaper per token than "
                                 "the parent and none is chosen from a pool")
    assert bullets[0].endswith("which ranks no note budget above another")
    assert bullets[1].startswith("- The hand-off is serial: a successor takes over from a note and no parent reads a "
                                 "result back, so these runs measure what a brief carries forward, not the cost or the "
                                 "success of a delegate whose result a parent reads")
    assert bullets[2].startswith(f"- No price: the registry (`model_routing/data/models.json`) has no row for `{MODEL}`")


def test_design_specifies_the_limitations_bullet():
    spec = design_13_15()
    bullets = [line for line in spec.splitlines() if line.startswith("- README Limitations (v1.462, row DOC29): ")]
    assert len(bullets) == 1
    assert bullets[0].startswith("- README Limitations (v1.462, row DOC29): directly after the per-item bullet "
                                 "(13.8 v1.236), ")
    template = bullets[0].split(' "', 1)[1].split('". ', 1)[0]
    filled = (template.replace("{model}", MODEL).replace("{probe `items`}", "100").replace("{spread}", "3")
              .replace("{items}", "100").replace("{depth}", "20, 50 and 100"))
    assert "- " + filled == limitations_bullet(committed())
    for needle in ("{spread} is the largest difference between two note arms'", "whose {spread} is over 5",
                   "whose `model` has a `models.json` row is refused", "RESULTS.md `## Limits` to state it"):
        assert needle in bullets[0], needle
    assert "from v1.462 (row DOC29) it builds the Limitations bullet above from the committed results file" in spec
