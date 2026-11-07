"""v1.72 variant point 2 of the delegation results (DESIGN 13.10), written before the code.

Variant point 2 is variant point 0 (folded work at 64,000 context tokens) with ``work_calls`` set
to ``VARIANT_OBSERVED_WORK_CALLS``, the median of the TRAIL sub-agent runs' model calls in the
committed ``evidence/trail/summary.json`` (DESIGN 13.11), rounded up with ``math.ceil`` when it is
not a whole number. It is a cost sensitivity at an observed size, never a measured hand-off.

The tests that need the new script were committed in v1.72 under strict xfail markers, each naming
what the v1.71 script raised: ``AttributeError`` where a test reads ``VARIANT_OBSERVED_WORK_CALLS``
and ``AssertionError`` where it expects three variant points. v1.73 implements the point,
regenerates ``variants.json`` and removes the markers. The other tests held before and after: the
summary's median, the stated point on a small matrix, SHA-256 pins of ``results.json`` and of the
committed summary rows of variant points 0 and 1 (taken on v1.71), and, only when the pinned
AutoBench files are already in the default cache, the window facts DESIGN 13.10 states for K = 15.
"""

import hashlib
import importlib.util
import json
import math
import statistics
from pathlib import Path

import pytest

from model_routing import Model, Registry, evaluate_delegation

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "delegation" / "results.py"
RESULTS = ROOT / "evidence" / "delegation" / "results.json"
VARIANTS_FILE = ROOT / "evidence" / "delegation" / "variants.json"
TRAIL = ROOT / "evidence" / "trail" / "summary.json"
RESULTS_MD = ROOT / "evidence" / "delegation" / "RESULTS.md"
README = ROOT / "README.md"
VARIANTS_COMMAND = "$ python evidence/delegation/results.py --table evidence/delegation/variants.json"
KEYS = ["config", "tasks", "summary"]
STRATEGIES = ("decision", "inline", "delegate")
POINT_KEYS = ["context_tokens", "brief_tokens", "result_tokens", "carry_turns",
              "inline_separate_call", "work_calls"]
V0 = {"context_tokens": 64000, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
      "inline_separate_call": False, "work_calls": 2}
V1 = {"context_tokens": 200000, "brief_tokens": 500, "result_tokens": 500, "carry_turns": 1,
      "inline_separate_call": True, "cached_read_ratio": 0.1}
V2 = dict(V0, work_calls=15)
VARIANTS = [V0, V1, V2]
# taken on v1.71 (03e7760): the bytes of results.json, and json.dumps(rows, sort_keys=True) of the
# committed variants.json summary rows of variant points 0 and 1, in file order
RESULTS_SHA256 = "6ece3a3c8e22c8fb70c1dae2fcc7844ee41dace1103ecbf3e620a3032146cabf"
ROWS_0_1_SHA256 = "6537acbfd64ffe023b42d7526d75f98fd046c7296d16dd77f05e80ad7acfc3a2"


def trail_median():
    return json.loads(TRAIL.read_text(encoding="utf-8"))["stats"]["model_calls"]["median"]


def observed():
    """The stated rule: the TRAIL median of the runs' model calls, rounded up (DESIGN 13.10)."""
    return math.ceil(trail_median())


@pytest.fixture
def dr():
    spec = importlib.util.spec_from_file_location("delegation_results_observed", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def tiny():
    """The 80-item, two-model matrix of tests/test_delegation_variants.py."""
    registry = Registry([
        Model(id="v/strong", family="S", price_in=3.0, price_out=12.0, context_window=1_000_000),
        Model(id="v/cheap", family="C", price_in=0.1, price_out=0.4, context_window=100_000)])
    rows = []
    for i in range(80):
        rows.append({"task": "all", "item": f"q{i}", "model": "v/strong", "correct": i % 10 != 0,
                     "input_tokens": 200 + i, "output_tokens": 900 + 3 * i})
        rows.append({"task": "all", "item": f"q{i}", "model": "v/cheap", "correct": i % 3 != 0,
                     "input_tokens": 180 + i, "output_tokens": 700 + 2 * i})
    return rows, registry


def sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


# --- plain: true before and after v1.73 ------------------------------------------------------------

def test_the_trail_median_is_the_median_of_the_committed_runs_and_a_whole_number():
    summary = json.loads(TRAIL.read_text(encoding="utf-8"))
    calls = [run["model_calls"] for run in summary["runs"]]
    assert len(calls) == summary["run_count"] == 60
    assert summary["stats"]["model_calls"]["median"] == statistics.median(calls) == 15.0
    # whole, so the rounding rule does not yet move K
    assert float(observed()) == trail_median()
    assert V2["work_calls"] == observed() == 15


def test_the_stated_point_is_variant_point_0_at_the_observed_size_with_work_calls_last():
    assert {k: v for k, v in V2.items() if k != "work_calls"} == {
        k: v for k, v in V0.items() if k != "work_calls"}
    rows, registry = tiny()
    result = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=VARIANTS, seeds=range(5))
    assert result["config"]["points"] == VARIANTS
    assert [list(p) for p in result["config"]["points"]] == [
        POINT_KEYS, POINT_KEYS[:5] + ["cached_read_ratio"], POINT_KEYS]


def test_the_stated_point_costs_more_inline_than_variant_point_0_for_every_parent():
    # from 2 to 15 folded calls the inline path re-reads C in 14 calls, not 1 (DESIGN 13.2)
    rows, registry = tiny()
    result = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=[V0, V2], seeds=range(10))
    inline = {(r["bar"], r["flavor"], r["parent"], r["point"]): (r["cost_usd"], r["success"])
              for r in result["summary"] if r["strategy"] == "inline"}
    groups = {key[:3] for key in inline}
    assert len(groups) == 2 * 2 * 2
    for group in groups:
        (k15, s15), (k2, s2) = inline[group + (1,)], inline[group + (0,)]
        assert k15 > k2, group
        assert s15 == s2, group


def test_results_json_keeps_its_bytes():
    assert sha256(RESULTS.read_bytes()) == RESULTS_SHA256


def test_the_committed_rows_of_variant_points_0_and_1_keep_their_values():
    variants = json.loads(VARIANTS_FILE.read_text(encoding="utf-8"))
    assert variants["config"]["points"][:2] == [V0, V1]
    config = variants["config"]
    kept = [r for r in variants["summary"] if r["point"] in (0, 1)]
    assert len(kept) == (len(config["bars"]) * len(config["flavors"]) * 2 * len(config["parents"])
                         * len(STRATEGIES)) == 480
    assert sha256(json.dumps(kept, sort_keys=True).encode("utf-8")) == ROWS_0_1_SHA256


def test_real_window_checks_drop_no_parent_or_delegate_at_the_observed_size(tmp_path):
    path = ROOT / "evidence" / "autobench-2026" / "convert.py"
    spec = importlib.util.spec_from_file_location("autobench_convert_observed", path)
    cv = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cv)
    folder = cv.default_cache_dir()
    if not all((folder / n).is_file() for n in cv.FILES):
        pytest.skip("pinned AutoBench files are not in the default cache")
    for name, (size, sha) in cv.FILES.items():
        cv.verify(folder / name, size, sha)
    params = json.loads((folder / "frozen_params.json").read_text(encoding="utf-8"))
    pool = json.loads((folder / "pool.json").read_text(encoding="utf-8"))
    rows, report = cv.convert(cv.read_csv(folder / "matrix.csv"),
                              cv.read_csv(folder / "questions.csv"), pool, params["delta_signal"],
                              params["top_k"], task_by="all", tokens=True)
    assert report["kept"] == {"all": 203}
    models = cv.pool_registry(pool)["models"]
    path = tmp_path / "pool-registry.json"
    path.write_text(json.dumps(cv.pool_registry(pool)), encoding="utf-8")
    registry = Registry.load(path)
    result = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=[V2], seeds=range(50))
    cells = result["cells"]
    assert len(cells) == 2 * 2 * len(models) * 50
    sums = [c["expected_input_tokens"] + c["expected_output_tokens"] for c in cells]
    smallest = min(m["context_window"] for m in models)
    assert [m["id"] for m in models if m["context_window"] == smallest] == ["openai/gpt-oss-120b"]
    k, c, b = V2["work_calls"], V2["context_tokens"], V2["brief_tokens"]
    assert (min(sums), max(sums), smallest) == (1331, 1678, 131000)
    assert c + k * max(sums) == 89170 < smallest  # 13.4 rule 3, the parent's last work call
    assert b + k * max(sums) == 25670 < smallest  # 5.2 rule 5, the delegate's last call
    assert all(cell["inline_allowed"] for cell in cells)
    assert not any(cell["reason"] == "parent_context_full" for cell in cells)
    assert (smallest - c) // max(sums) == 39 and c + 31 * max(sums) == 116018


# --- v1.72 script tests, plain since v1.73 ---------------------------------------------------------

def test_the_observed_work_calls_constant_is_the_rounded_up_trail_median(dr):
    k = dr.VARIANT_OBSERVED_WORK_CALLS
    assert type(k) is int and k == observed() == 15


def test_variant_points_append_variant_point_0_at_the_observed_size(dr):
    got = dr.variant_points()
    assert got == VARIANTS
    assert [list(p) for p in got] == [POINT_KEYS, POINT_KEYS[:5] + ["cached_read_ratio"], POINT_KEYS]
    assert got[2] == dict(got[0], work_calls=observed())
    assert dr.variant_points() is not dr.variant_points()


def test_run_on_the_variants_grid_has_three_points_and_keeps_points_0_and_1(dr):
    rows, registry = tiny()
    got = dr.run(rows, registry, grid="variants")
    assert got["config"]["points"] == VARIANTS
    full = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=VARIANTS, seeds=range(50))
    assert got == {key: full[key] for key in KEYS}
    two = evaluate_delegation(rows, registry, bars=[0.7, 0.8], points=VARIANTS[:2], seeds=range(50))
    assert [r for r in got["summary"] if r["point"] < 2] == two["summary"]


def test_the_variants_table_prints_15_calls_for_the_third_point(dr):
    rows, registry = tiny()
    lines = dr.table(dr.run(rows, registry, grid="variants")).split("\n")
    assert lines[0].split()[:6] == ["bar", "flavor", "context", "separate", "calls", "cached"]
    body = [line.split() for line in lines[2:]]
    assert [tuple(row[2:6]) for row in body] == [
        ("64000", "False", "2", "1.0"), ("200000", "True", "1", "0.1"),
        ("64000", "False", "15", "1.0")] * 4


# --- v1.73: the committed file's third bullet, in RESULTS.md and the README ------------------

def committed(path):
    return json.loads(path.read_text(encoding="utf-8"))


def observed_reading(variants):
    """The third Variant points bullet: variant point 2 against variant point 0 (DESIGN 13.10)."""
    rows = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
            for r in variants["summary"]}
    points = variants["config"]["points"]
    k0, k2 = points[0]["work_calls"], points[2]["work_calls"]
    assert (k0, k2) == (2, observed())
    assert points[2] == dict(points[0], work_calls=k2)
    parents = variants["config"]["parents"]
    n = len(parents)
    bars = variants["config"]["bars"]
    assert bars == [0.7, 0.8]

    def values(at, bar, strategy, key):
        return [rows[(bar, "cost_effective", at, p, strategy)][key] for p in parents]

    def mean(at, bar, strategy, key):
        return math.fsum(values(at, bar, strategy, key)) / n

    for bar in bars:
        for at in (0, 2):
            assert all(r == 1.0 for r in values(at, bar, "decision", "delegate_rate")), (at, bar)
        assert mean(2, bar, "inline", "cost_usd") > mean(2, bar, "decision", "cost_usd"), bar
    for at in (0, 2):
        assert mean(at, 0.7, "inline", "cost_usd") == mean(at, 0.8, "inline", "cost_usd"), at
    ratio = mean(2, 0.7, "inline", "cost_usd") / mean(0, 0.7, "inline", "cost_usd")

    def pair(bar, strategy, key, places):
        return (f"{mean(2, bar, strategy, key):.{places}f} against "
                f"{mean(0, bar, strategy, key):.{places}f}")

    def costs(bar):
        return ", ".join(f"{label} {pair(bar, s, 'cost_usd', 4)}"
                         for label, s in (("the decision", "decision"), ("always inline", "inline"),
                                          ("always delegating", "delegate")))

    c = points[2]["context_tokens"]
    return (f"With the work in {k2} folded calls at {c:,} context tokens (variant point 2, the "
            f"median size of TRAIL's sub-agent runs) instead of {k0} (variant point 0), "
            f"`cost_effective` still delegates on every seed for every parent at both bars: its "
            f"mean delegated share over the {n} parents is {mean(2, 0.7, 'decision', 'delegate_rate'):.3f} "
            f"at bar 0.7 and {mean(2, 0.8, 'decision', 'delegate_rate'):.3f} at bar 0.8, against "
            f"{mean(0, 0.7, 'decision', 'delegate_rate'):.3f} and "
            f"{mean(0, 0.8, 'decision', 'delegate_rate'):.3f} at variant point 0. Its mean held-out "
            f"success is {pair(0.7, 'decision', 'success', 3)} at bar 0.7 and "
            f"{pair(0.8, 'decision', 'success', 3)} at bar 0.8: a delegate's input over its calls "
            "grows with the square of their number and its output only in step with it, so more "
            "calls can change which delegate that clears the bar costs least (`DESIGN.md` 13.3). "
            f"Mean costs in USD, variant point 2 against variant point 0: at bar 0.7 {costs(0.7)}; "
            f"at bar 0.8 {costs(0.8)}. On the inline path {k2 - 1} of the {k2} calls re-read the "
            f"{c:,}-token context, so always inline costs {ratio:.1f} times as much as at variant "
            "point 0, and it stays above the decision's at both bars")


def bullets(text):
    return [line for line in text.split("\n") if line.startswith("- ")]


def test_observed_reading_refuses_a_file_where_the_decision_keeps_work_inline():
    variants = committed(VARIANTS_FILE)
    for row in variants["summary"]:
        if (row["bar"], row["flavor"], row["point"], row["strategy"]) == (
                0.8, "cost_effective", 2, "decision"):
            row["delegate_rate"] = 0.98
            break
    with pytest.raises(AssertionError):
        observed_reading(variants)


def test_results_md_variant_part_shows_variant_point_2_and_its_bullet(dr):
    md = RESULTS_MD.read_text(encoding="utf-8")
    part = md.split("\n## Variant points\n", 1)[1].split("\n## ", 1)[0]
    variants = committed(VARIANTS_FILE)
    table = f"```text\n{VARIANTS_COMMAND}\n{dr.table(variants)}\n```\n"
    bullet = f"- {observed_reading(variants)}"
    assert len(bullets(part)) == 3 and bullets(part)[2] == bullet
    assert part.index(table) < part.index(bullet) < part.index("```bash\n")
    for phrase in ("Variant point 2 is variant point 0 with the work in 15 calls (`work_calls` 15)",
                   "[the TRAIL summary](../trail/RESULTS.md)", "`DESIGN.md` 13.11",
                   "rounded up when it is not a whole number", "never a measured hand-off",
                   "whether the 15 calls succeed together is not measured",
                   "the bar is held per call"):
        assert phrase in part, phrase


def test_readme_subsection_shows_variant_point_2_and_its_bullet(dr):
    text = README.read_text(encoding="utf-8")
    section = text.split("\n## Evidence: held-out results on public data\n", 1)[1].split("\n## ", 1)[0]
    sub = section.split("\n### Delegation on AutoBench\n", 1)[1].split("\n### ", 1)[0]
    variants = committed(VARIANTS_FILE)
    table = f"```text\n{VARIANTS_COMMAND}\n{dr.table(variants)}\n```\n"
    bullet = f"- {observed_reading(variants)}"
    lines = sub.split("\n")
    assert lines.count(bullet) == 1
    at = lines.index(bullet)
    assert lines[at - 1].startswith("- With the parent's reads of its ") and lines[at + 1] == ""
    assert sub.index(table) < sub.index(bullet) < sub.index("```bash\n")
    for phrase in ("Variant point 2 is variant point 0 with the work in 15 calls (`work_calls` 15)",
                   "[evidence/trail/RESULTS.md](evidence/trail/RESULTS.md)",
                   "never a measured hand-off",
                   "whether the 15 calls succeed together is not measured",
                   "the bar is held per call"):
        assert phrase in sub, phrase
