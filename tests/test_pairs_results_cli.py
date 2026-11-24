"""`model-routing pairs ... --results RESULTS [--routes ROUTED SHADOW]` writes the pairs' labeled
results rows (DESIGN 10 v1.615, row CANARY1n; the rows are `pair_results`, 8.3 v1.613 and v1.614)."""

import hashlib
import json
import os
from pathlib import Path

import pytest

from model_routing import load_audits, load_records, pair_results, paired_promotion, shadow_pairs
from model_routing.cli import main

ROOT = Path(__file__).resolve().parents[1]
CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
ITEMS = [f"p{i}" for i in range(8)]
COST_CHEAP = {i: (n + 1) / 1000 for n, i in enumerate(ITEMS)}
COST_BEST = {i: (n + 1) / 100 for n, i in enumerate(ITEMS)}
OK_CHEAP = {"p0": True, "p1": True, "p2": True, "p3": False, "p4": True, "p5": True,
            "p6": False, "p7": True}
OK_BEST = {i: i != "p5" for i in ITEMS}


def rec(call_id, model, cost, *, pair_id, shadow=False, attempt=0, final=True, outcome="ok"):
    return {"ts": "2026-11-23T00:00:00Z", "call_id": call_id, "task": "judge",
            "flavor": "cost_effective", "model": model, "attempt": attempt, "final": final,
            "outcome": outcome, "cost_usd": cost, "tags": {"shadow": "true"} if shadow else {},
            "slice": None, "pair_id": pair_id, "shadow": shadow}


def hand_log():
    """Eight pairs routed on CHEAP and shadowed on BEST; p8 and p10 answered by MID, a fallback,
    shadowed on BEST; p9's shadow erred, so its pair has a None side."""
    log = []
    for i in ITEMS:
        log += [rec(i, CHEAP, COST_CHEAP[i], pair_id=i),
                rec(i + "-s", BEST, COST_BEST[i], pair_id=i, shadow=True)]
    for i in ("p8", "p10"):
        log += [rec(i, CHEAP, 0.0035, pair_id=i, final=False, outcome="invalid"),
                rec(i, MID, 0.0045, pair_id=i, attempt=1),
                rec(i + "-s", BEST, 0.045, pair_id=i, shadow=True)]
    log += [rec("p9", CHEAP, 0.0011, pair_id="p9"),
            rec("p9-s", BEST, 0.0, pair_id="p9", shadow=True, outcome="error")]
    return log


AUDITS = [{"call_id": i, "correct": OK_CHEAP[i]} for i in ITEMS] + \
         [{"call_id": i + "-s", "correct": OK_BEST[i]} for i in ITEMS] + \
         [{"call_id": c, "correct": v} for c, v in (("p8", True), ("p8-s", False), ("p10", True),
                                                    ("p10-s", True), ("p9", True))]


def write_jsonl(path, values):
    path.write_text("".join(json.dumps(v) + "\n" for v in values), encoding="utf-8")
    return path


def lines_of(values):
    return "".join(json.dumps(v) + "\n" for v in values)


@pytest.fixture
def log(tmp_path):
    return write_jsonl(tmp_path / "calls.jsonl", hand_log())


@pytest.fixture
def audits(tmp_path):
    return write_jsonl(tmp_path / "audits.jsonl", AUDITS)


def run(capsys, *argv):
    code = main(["pairs", *[str(a) for a in argv]])
    captured = capsys.readouterr()
    return code, captured.out, captured.err


def row(model, item, correct, cost):
    return {"task": "judge", "model": model, "item": item, "correct": correct, "cost_usd": cost}


# --- the file it writes --------------------------------------------------------------------------

def test_results_are_pair_results_of_the_pairs_with_the_log_one_json_dumps_per_line(
        tmp_path, capsys, log, audits):
    out, results = tmp_path / "pairs.jsonl", tmp_path / "rows.jsonl"
    code, stdout, stderr = run(capsys, "--log", log, "--out", out, "--audits", audits,
                               "--results", results)
    assert (code, stderr) == (0, "")
    records = load_records(log)
    pairs = shadow_pairs(records, audits=load_audits(audits))
    assert out.read_bytes() == lines_of(pairs).encode("utf-8")  # FILE is v1.612's
    rows = pair_results(pairs, records=records)
    assert results.read_bytes() == lines_of(rows).encode("utf-8")
    expected = []
    for i in ITEMS:
        expected += [row(CHEAP, i, OK_CHEAP[i], COST_CHEAP[i]), row(BEST, i, OK_BEST[i], COST_BEST[i])]
    expected += [row(MID, "p8", True, 0.0045), row(BEST, "p8", False, 0.045),
                 row(MID, "p10", True, 0.0045), row(BEST, "p10", True, 0.045)]
    assert [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()] == expected
    assert stdout == (f"wrote 11 pairs to {out}: 10 with both sides labelled\n"
                      f"wrote 20 results rows to {results}\n")


def test_routes_keeps_one_route_pair_and_counts_and_names_the_labelled_pairs_left_out(
        tmp_path, capsys, log, audits):
    out, results = tmp_path / "pairs.jsonl", tmp_path / "rows.jsonl"
    code, stdout, stderr = run(capsys, "--log", log, "--out", out, "--audits", audits,
                               "--results", results, "--routes", CHEAP, BEST)
    assert (code, stderr) == (0, "")
    records = load_records(log)
    pairs = shadow_pairs(records, audits=load_audits(audits))
    rows = pair_results(pairs, records=records, routes=(CHEAP, BEST))
    assert results.read_bytes() == lines_of(rows).encode("utf-8")
    assert [r["item"] for r in rows] == [i for i in ITEMS for _ in (0, 1)]
    # M = 10 = K / 2 + L = 8 + 2; p9, with a None side, is in neither
    assert stdout == (f"wrote 11 pairs to {out}: 10 with both sides labelled\n"
                      f"wrote 16 results rows to {results}: routed {CHEAP}, shadow {BEST}\n"
                      "labelled pairs of other route pairs left out: 2\n"
                      f"  routed {MID}, shadow {BEST}: 2\n")


def test_left_out_route_pairs_are_sorted_and_none_gives_a_zero_line(tmp_path, capsys, log, audits):
    results = tmp_path / "rows.jsonl"
    code, stdout, _ = run(capsys, "--log", log, "--out", tmp_path / "p.jsonl", "--audits", audits,
                          "--results", results, "--routes", MID, BEST)
    assert code == 0
    assert stdout.splitlines()[1:] == [
        f"wrote 4 results rows to {results}: routed {MID}, shadow {BEST}",
        "labelled pairs of other route pairs left out: 8", f"  routed {CHEAP}, shadow {BEST}: 8"]
    log2 = write_jsonl(tmp_path / "calls2.jsonl", [r for r in hand_log() if r["pair_id"] not in ("p8", "p10")])
    code, stdout, _ = run(capsys, "--log", log2, "--out", tmp_path / "p2.jsonl", "--audits", audits,
                          "--results", tmp_path / "rows2.jsonl", "--routes", CHEAP, BEST)
    assert code == 0
    assert stdout.splitlines()[2:] == ["labelled pairs of other route pairs left out: 0"]


def test_routes_in_the_other_order_keeps_no_pair(tmp_path, capsys, log, audits):
    results = tmp_path / "rows.jsonl"
    code, stdout, _ = run(capsys, "--log", log, "--out", tmp_path / "p.jsonl", "--audits", audits,
                          "--results", results, "--routes", BEST, CHEAP)
    assert code == 0 and results.read_bytes() == b""
    assert stdout.splitlines()[1:3] == [f"wrote 0 results rows to {results}: routed {BEST}, shadow {CHEAP}",
                                        "labelled pairs of other route pairs left out: 10"]


def test_checked_gives_every_routed_row_true(tmp_path, capsys, log):
    results = tmp_path / "rows.jsonl"
    code, _, stderr = run(capsys, "--log", log, "--out", tmp_path / "p.jsonl", "--checked",
                          "--results", results, "--routes", CHEAP, BEST)
    assert (code, stderr) == (0, "")
    rows = [json.loads(line) for line in results.read_text(encoding="utf-8").splitlines()]
    assert len(rows) == 16 and all(r["correct"] for r in rows)  # every side answered ok


def test_an_unlabelled_run_gives_an_empty_results_file(tmp_path, capsys, log):
    results = tmp_path / "rows.jsonl"
    results.write_text("older rows\n", encoding="utf-8")
    code, stdout, stderr = run(capsys, "--log", log, "--out", tmp_path / "p.jsonl", "--results", results)
    assert (code, stderr) == (0, "")
    assert results.read_bytes() == b""  # replaced whole, never appended to
    assert stdout.splitlines()[1] == f"wrote 0 results rows to {results}"


def test_the_results_line_prints_results_as_a_path_prints_it(tmp_path, capsys, log, audits):
    code, stdout, _ = run(capsys, "--log", log, "--out", tmp_path / "p.jsonl", "--audits", audits,
                          "--results", f"{tmp_path}/./rows.jsonl")
    assert code == 0
    assert stdout.splitlines()[1] == f"wrote 20 results rows to {tmp_path / 'rows.jsonl'}"


# --- the round trip: calibrate --outcomes, then promote ------------------------------------------

def test_calibrate_outcomes_then_promote_read_the_file_it_writes(tmp_path, capsys, log, audits):
    results = tmp_path / "rows.jsonl"
    assert run(capsys, "--log", log, "--out", tmp_path / "p.jsonl", "--audits", audits,
               "--results", results, "--routes", CHEAP, BEST)[0] == 0
    models = [{"id": m, "family": f, "price_in": pin, "price_out": pout, "context_window": 100000,
               "source": "https://example.org/prices"}
              for m, f, pin, pout in ((CHEAP, "small", 1.0, 2.0), (MID, "medium", 3.0, 6.0),
                                      (BEST, "large", 10.0, 20.0))]
    (tmp_path / "models.json").write_text(json.dumps(
        {"version": "1", "as_of": "2026-01-01", "currency": "USD", "models": models}))
    (tmp_path / "tasks.json").write_text(json.dumps({"tasks": [
        {"name": "judge", "bar": 0.4, "min_samples": 5, "expected_input_tokens": 1000,
         "expected_output_tokens": 100}]}))
    stats, outcomes = tmp_path / "stats.json", tmp_path / "outcomes.jsonl"
    assert main(["calibrate", "--results", str(results), "--stats", str(stats),
                 "--outcomes", str(outcomes)]) == 0
    digest = hashlib.sha256(results.read_bytes()).hexdigest()
    assert capsys.readouterr().out.endswith(f"appended 16 outcomes to {outcomes}, dataset_sha256 {digest}\n")
    assert main(["promote", "--task", "judge", "--challenger", BEST, "--margin", "0.05",
                 "--outcomes", str(outcomes), "--registry", str(tmp_path / "models.json"),
                 "--tasks", str(tmp_path / "tasks.json"), "--stats", str(stats),
                 "--priors", str(tmp_path / "none.json"), "--json"]) == 0  # no priors file: none
    data = json.loads(capsys.readouterr().out)
    # by hand: CHEAP right on 6 of the 8 items (0.75), BEST on 7 (0.875); CHEAP is the primary
    check = paired_promotion(OK_CHEAP, OK_BEST, margin=0.05, cheaper=False, alpha=0.05, min_pairs=5)
    assert (data["current"], data["challenger"], data["dataset_sha256"]) == (CHEAP, BEST, digest)
    assert (data["pairs"], data["current_rate"], data["challenger_rate"]) == (8, 0.75, 0.875)
    assert (data["decision"], data["basis"], data["p_value"]) == (check.decision, check.basis, check.p_value)


# --- refusals: exit 2, one error line, nothing on stdout, neither file created nor changed -------

def _cascade_pair(tmp, shadowed_on=None):
    # review iter-466 should-fix 1: a cascade's pair beside the CHEAP, BEST ones; from v1.621
    # (row CANARY2) a routed cascade is read from the log, while a shadow record that ran a
    # cascade is refused whatever --routes says, since pair_results checks every pair first
    cascade = "fiction/cheap>fiction/mid"
    extra = [dict(rec("c1", CHEAP, 0.002, pair_id="c1"), cascade=cascade),
             rec("c1-s", BEST, 0.02, pair_id="c1", shadow=True)]
    if shadowed_on is not None:
        extra = [rec("c1", CHEAP, 0.002, pair_id="c1"),
                 rec("c1-s", shadowed_on, 0.02, pair_id="c1", shadow=True)]
    return write_jsonl(tmp / "calls.jsonl", hand_log() + extra)


def _two_faults(tmp):
    # review iter-466 should-fix 2: shadow_pairs' fault (two shadows of p0) is named before
    # pair_results' (p1's routed record has no cost_usd)
    bad = hand_log()
    bad.append(rec("p0-s2", BEST, 0.01, pair_id="p0", shadow=True))
    del bad[2]["cost_usd"]
    return write_jsonl(tmp / "calls.jsonl", bad)


def _cost_missing(tmp):
    bad = hand_log()
    del bad[0]["cost_usd"]
    return write_jsonl(tmp / "calls.jsonl", bad)


REFUSALS = {
    "routes without results": (lambda tmp: ["--routes", CHEAP, BEST],
                               "error: --routes needs --results: it picks the route pair of the rows "
                               "--results writes\n"),
    "equal routes": (lambda tmp: ["--results", tmp / "rows.jsonl", "--routes", CHEAP, CHEAP],
                     f"error: --routes needs two different non-empty routes, got {CHEAP!r} {CHEAP!r}\n"),
    "an empty route": (lambda tmp: ["--results", tmp / "rows.jsonl", "--routes", "", BEST],
                       f"error: --routes needs two different non-empty routes, got '' {BEST!r}\n"),
    "an empty shadow route": (lambda tmp: ["--results", tmp / "rows.jsonl", "--routes", CHEAP, ""],
                              f"error: --routes needs two different non-empty routes, got {CHEAP!r} ''\n"),
    "a cascade shadow whatever --routes says": (
        lambda tmp: ["--log", _cascade_pair(tmp, "a/x>b/y@s"), "--results", tmp / "rows.jsonl",
                     "--routes", CHEAP, BEST],
        "error: pair 12: shadow_route 'a/x>b/y@s' is a cascade's or a procedure's, which the "
        "executor never shadows on, since it shadows on a registry model only, so the pair is not "
        "of a monitor log\n"),
    "shadow_pairs before pair_results": (
        lambda tmp: ["--log", _two_faults(tmp), "--results", tmp / "rows.jsonl"],
        "error: pair_id 'p0' has more than one shadow record\n"),
    "results names the log": (lambda tmp: ["--results", tmp / "calls.jsonl"],
                              f"error: --results {{tmp}}/calls.jsonl names the log, the audits file or "
                              "--out\n"),
    "results names the audits file": (lambda tmp: ["--results", tmp / "audits.jsonl"],
                                      f"error: --results {{tmp}}/audits.jsonl names the log, the audits "
                                      "file or --out\n"),
    "results names out": (lambda tmp: ["--results", f"{tmp}/./pairs.jsonl"],
                          f"error: --results {{tmp}}/./pairs.jsonl names the log, the audits file or "
                          "--out\n"),
    "a cost pair_results refuses": (lambda tmp: ["--log", _cost_missing(tmp), "--results", tmp / "rows.jsonl"],
                                    "error: pair 1: the routed final record's cost_usd must be a finite "
                                    "number >= 0, got None\n"),
}


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("case", sorted(REFUSALS))
def test_a_refusal_exits_two_and_writes_neither_file(tmp_path, capsys, log, audits, case, existing):
    extra, message = REFUSALS[case]
    extra = extra(tmp_path)
    out, results = tmp_path / "pairs.jsonl", tmp_path / "rows.jsonl"
    if existing:
        out.write_text("an older pair file\n", encoding="utf-8")
        results.write_text("older rows\n", encoding="utf-8")
    argv = ["--out", out, "--audits", audits] + ([] if "--log" in extra else ["--log", log]) + extra
    before = {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    code, stdout, stderr = run(capsys, *argv)
    assert (code, stdout) == (2, "")
    assert stderr == message.replace("{tmp}", str(tmp_path))
    assert {p: p.read_bytes() for p in tmp_path.iterdir() if p.is_file()} == before


def test_a_routed_cascade_pair_is_read_from_the_log_where_v1_615_exited_2(tmp_path, capsys, audits):
    # DESIGN 10 v1.621 (row CANARY2): the pair is unlabelled, so it gives no row and the
    # labelled pairs' rows are those of the log without it
    out, results = tmp_path / "pairs.jsonl", tmp_path / "rows.jsonl"
    code, stdout, stderr = run(capsys, "--log", _cascade_pair(tmp_path), "--out", out,
                               "--audits", audits, "--results", results, "--routes", CHEAP, BEST)
    assert (code, stderr) == (0, "")
    assert results.read_text(encoding="utf-8") == lines_of(
        [r for i in ITEMS for r in (row(CHEAP, i, OK_CHEAP[i], COST_CHEAP[i]),
                                    row(BEST, i, OK_BEST[i], COST_BEST[i]))])
    assert stdout.startswith(f"wrote 12 pairs to {out}: 10 with both sides labelled\n")


def test_the_route_checks_come_before_any_path_is_read(tmp_path, capsys):
    absent = tmp_path / "absent.jsonl"
    code, stdout, stderr = run(capsys, "--log", absent, "--out", absent, "--routes", CHEAP, CHEAP)
    assert (code, stdout) == (2, "")
    assert stderr == "error: --routes needs --results: it picks the route pair of the rows --results writes\n"
    code, _, stderr = run(capsys, "--log", absent, "--out", absent, "--results", absent,
                          "--routes", CHEAP, CHEAP)
    assert stderr == f"error: --routes needs two different non-empty routes, got {CHEAP!r} {CHEAP!r}\n"
    assert not absent.exists()


def test_a_results_that_names_the_log_is_refused_before_the_log_is_read(tmp_path, capsys):
    # review iter-466 should-fix 2: right after the FILE check, so an absent log is never read
    absent = tmp_path / "absent.jsonl"
    code, stdout, stderr = run(capsys, "--log", absent, "--out", tmp_path / "p.jsonl",
                               "--results", absent)
    assert (code, stdout) == (2, "")
    assert stderr == f"error: --results {absent} names the log, the audits file or --out\n"
    assert sorted(tmp_path.iterdir()) == []


def test_a_dangling_symlink_is_left_as_it_was(tmp_path, capsys, log, audits):
    # review iter-466 should-fix 3: the target this run created is removed, the link kept
    out = tmp_path / "pairs.jsonl"
    out.symlink_to(tmp_path / "target.jsonl")
    code, stdout, _ = run(capsys, "--log", log, "--out", out, "--audits", audits,
                          "--results", tmp_path / "missing" / "rows.jsonl")
    assert (code, stdout) == (2, "")
    assert out.is_symlink() and not (tmp_path / "target.jsonl").exists()


@pytest.mark.skipif(not os.path.exists("/dev/null"), reason="no /dev/null")
def test_a_device_file_serves_as_out(tmp_path, capsys, log, audits):
    # review iter-466 should-fix 4: only a regular file is truncated, as open("w") let it
    results = tmp_path / "rows.jsonl"
    code, stdout, stderr = run(capsys, "--log", log, "--out", "/dev/null", "--audits", audits,
                               "--results", results)
    assert (code, stderr) == (0, "")
    assert stdout == ("wrote 11 pairs to /dev/null: 10 with both sides labelled\n"
                      f"wrote 20 results rows to {results}\n")
    assert len(results.read_text(encoding="utf-8").splitlines()) == 20


def test_an_empty_log_gives_empty_files_and_a_zero_left_out_line(tmp_path, capsys):
    # review iter-466 nit 6
    log = tmp_path / "calls.jsonl"
    log.write_text("", encoding="utf-8")
    out, results = tmp_path / "pairs.jsonl", tmp_path / "rows.jsonl"
    code, stdout, stderr = run(capsys, "--log", log, "--out", out, "--checked", "--results", results,
                               "--routes", CHEAP, BEST)
    assert (code, stderr) == (0, "")
    assert out.read_bytes() == b"" and results.read_bytes() == b""
    assert stdout == (f"wrote 0 pairs to {out}: 0 with both sides labelled\n"
                      f"wrote 0 results rows to {results}: routed {CHEAP}, shadow {BEST}\n"
                      "labelled pairs of other route pairs left out: 0\n")


@pytest.mark.parametrize("existing", [False, True])
@pytest.mark.parametrize("where", ["a directory", "a missing directory"])
def test_a_results_that_cannot_be_opened_leaves_both_files_as_they_were(
        tmp_path, capsys, log, audits, where, existing):
    out = tmp_path / "pairs.jsonl"
    if existing:
        out.write_text("an older pair file\n", encoding="utf-8")
    results = tmp_path / "rows"
    if where == "a directory":
        results.mkdir()
    else:
        results = results / "rows.jsonl"
    before = {p: (p.read_bytes() if p.is_file() else None) for p in tmp_path.rglob("*")}
    code, stdout, stderr = run(capsys, "--log", log, "--out", out, "--audits", audits,
                               "--results", results)
    assert (code, stdout) == (2, "")
    assert stderr.startswith("error: ") and stderr.count("\n") == 1
    assert {p: (p.read_bytes() if p.is_file() else None) for p in tmp_path.rglob("*")} == before


def test_routes_takes_two_values(tmp_path, capsys, log):
    code, stdout, stderr = run(capsys, "--log", log, "--out", tmp_path / "p.jsonl",
                               "--results", tmp_path / "r.jsonl", "--routes", CHEAP)
    assert (code, stdout) == (2, "")
    assert "error: argument --routes: expected 2 arguments" in stderr


# --- the spec ------------------------------------------------------------------------------------

def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    assert ten.count("- v1.615 `pairs ... [--results RESULTS] [--routes ROUTED SHADOW]` (row CANARY1n, 8.3 v1.614): ") == 1
    for text in ("`error: --routes needs --results: it picks the route pair of the rows --results writes`",
                 "`error: --routes needs two different non-empty routes, got 'A' 'B'`",
                 "`error: --results RESULTS names the log, the audits file or --out`",
                 "`wrote K results rows to RESULTS`", "`: routed ROUTED, shadow SHADOW`",
                 "`labelled pairs of other route pairs left out: L`", "`  routed A, shadow B: n`",
                 "(review iter-465 should-fix 2)", "(review iter-466 nit 3)",
                 "never the link (review iter-466 should-fix 3)", "(should-fix 4)", "(nit 2)"):
        assert text in ten, text
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert "`pairs --results RESULTS --routes ROUTED SHADOW` counts and names them (10 v1.615, row CANARY1n)." in eight3
    assert "a command that prints them is row CANARY1n's" not in eight3
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.615 (")]
    assert len(mine) == 1 and "(8.3, 10, row CANARY1n)" in mine[0]
