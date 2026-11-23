"""DESIGN 4.3 v1.593 (row CI32): one hash for every pinned decision.

`z` can differ in its last bit by platform (4.3 v1.592), so a bound at 1 or more successes can
too, and a pin of its exact bytes holds on one platform and fails on another. Every test that
hashes a JSON value in one expression does it through tests/decision_hash.py, which rounds the
bounds first; a site that hashes a value holding no bound, or the exact bytes on purpose, is
listed in ``NO_BOUND`` with what it hashes. A value hashed in two steps (its JSON bytes bound to
a name, then hashed) is not found by the pattern; this guard checks the one-expression form only.
"""

import hashlib
import json
import re
from pathlib import Path

import pytest

import model_routing.stats as stats_module
from decision_hash import BOUND_DIGITS, BOUND_KEYS, PLATFORM_Z, FixedZ, decision_sha256, neutral
from model_routing import wilson_lower_bound

ROOT = Path(__file__).resolve().parents[1]
TESTS = ROOT / "tests"
JSON_HASH = re.compile(r"sha256\(\s*json\.dumps\(")
NO_BOUND = {
    ("test_cache_cascades.py",
     "exact.add(hashlib.sha256(json.dumps(decisions, sort_keys=True).encode()).hexdigest())"):
        "the exact bytes, to show that they differ under the two values of `z`",
    ("test_delegation_observed_point.py",
     'assert sha256(json.dumps(kept, sort_keys=True).encode("utf-8")) == ROWS_0_1_SHA256'):
        "summary rows read from a committed results file, not computed by the test",
    ("test_evidence_results.py",
     'digest = hashlib.sha256(json.dumps(items, sort_keys=True).encode("utf-8")).hexdigest()'):
        "each task's item count, integers",
    ("test_evidence_llmrouterbench.py",
     'assert one["query"] == hashlib.sha256(json.dumps("q1", ensure_ascii=False, '
     'sort_keys=True).encode()).hexdigest()'):
        "the converter's query ID, a hash of the query text",
}


def json_hash_sites(directory=TESTS):
    """(file name, the stripped line where it starts) for each one-expression JSON hash, outside
    the helper and this file, whose own sites hash on purpose or are strings."""
    sites = []
    for path in sorted(directory.glob("*.py")):
        if path.name in ("decision_hash.py", Path(__file__).name):
            continue
        text = path.read_text(encoding="utf-8")
        lines = text.splitlines()
        for match in JSON_HASH.finditer(text):
            sites.append((path.name, lines[text.count("\n", 0, match.start())].strip()))
    return sites


def test_every_json_hash_in_the_tests_goes_through_the_helper_or_holds_no_bound():
    assert [site for site in json_hash_sites() if site not in NO_BOUND] == []


def test_each_listed_site_is_still_there_once():
    sites = json_hash_sites()
    assert {site: sites.count(site) for site in NO_BOUND} == dict.fromkeys(NO_BOUND, 1)


def test_a_new_pin_without_the_helper_is_found_even_over_two_lines(tmp_path):
    (tmp_path / "test_new.py").write_text(
        "import hashlib, json\n"
        "def sha(value):\n"
        "    return hashlib.sha256(\n"
        "        json.dumps(value, sort_keys=True).encode()).hexdigest()\n"
        "def ok(value):\n"
        "    return decision_sha256(value)\n", encoding="utf-8")
    (tmp_path / "decision_hash.py").write_text(
        "hashlib.sha256(json.dumps(neutral(value)).encode())\n", encoding="utf-8")
    assert json_hash_sites(tmp_path) == [("test_new.py", "return hashlib.sha256(")]


def test_neutral_rounds_each_bound_key_at_any_depth_and_nothing_else():
    x = 0.12345678901234567
    value = {"routing_cost": x, "parent_quality_lb": x, "delegate_quality_lb": None,
             "expected_cost_per_success_usd": x, "trials": 3,
             "candidates": ({"quality_lb": x, "list_cost": x}, [{"quality_lb": 0.0}])}
    assert BOUND_DIGITS == 12 and BOUND_KEYS == {
        "quality_lb", "parent_quality_lb", "delegate_quality_lb", "expected_cost_per_success_usd"}
    assert neutral(value) == {
        "routing_cost": x, "parent_quality_lb": 0.123456789012, "delegate_quality_lb": None,
        "expected_cost_per_success_usd": 0.123456789012, "trials": 3,
        "candidates": [{"quality_lb": 0.123456789012, "list_cost": x}, [{"quality_lb": 0.0}]]}
    assert value["candidates"][0]["quality_lb"] == x  # the value itself is not changed


@pytest.mark.parametrize("sort_keys", [True, False])
def test_a_value_without_a_bound_hashes_as_its_plain_json(sort_keys):
    value = {"b": [1, 2.5, None, "x"], "a": {"cost_usd": 0.12345678901234567, "rate": 1 / 3}}
    plain = hashlib.sha256(json.dumps(value, sort_keys=sort_keys).encode()).hexdigest()
    assert decision_sha256(value, sort_keys=sort_keys) == plain


def test_a_bound_one_bit_apart_under_the_two_values_of_z_hashes_the_same(monkeypatch):
    bounds = []
    for z in PLATFORM_Z:
        monkeypatch.setattr(stats_module, "NormalDist", FixedZ(z))
        bounds.append(wilson_lower_bound(37, 40))
    assert bounds[0] != bounds[1]
    assert len({decision_sha256({"quality_lb": b}) for b in bounds}) == 1


def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four = design[design.index("### 4.3 "):design.index("### 4.4 ")]
    assert four.count("  - v1.593 (row CI32): every test that hashes a decision or an "
                      "evaluation's result hashes it through one helper, tests/decision_hash.py,") == 1
    # v1.594 (row CACHE1d) heads the Status line now; tests/test_design_status.py checks that the
    # line holds one clause for each of the five highest changelog versions, this one among them
    assert "; v1.593, spec and tests: every test that pins a hash" in design.splitlines()[2]
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.593 (")]
    assert len(mine) == 1 and "(4.3, row CI32)" in mine[0]
