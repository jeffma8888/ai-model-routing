"""v1.23 README evidence at a glance (DESIGN 12.8), written before the README list.

The README evidence section opens with a short list, one bullet per subsection. Every
number and model ID in it is built here from the committed results files (four since v1.28,
which adds the AutoBench judges bullet), at the rounding of the subsection tables, and every word that depends on the data (no routed row
reaches or beats, every seed, more, less) is asserted against those files, so the list cannot
drift from them or keep a claim a regenerated file no longer supports.
"""

import copy
import json
import math
import re
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
HEADING = "\n## Evidence: held-out results on public data\n"
FILES = {"RouterBench": ROOT / "evidence" / "routerbench" / "results.json",
         "AutoBench": ROOT / "evidence" / "autobench-2026" / "results.json",
         "AutoBench judges": ROOT / "evidence" / "autobench-judges" / "results.json",
         "Delegation on AutoBench": ROOT / "evidence" / "delegation" / "results.json"}
LEAD = ("Results at a glance, each number from the committed results of the subsection it "
        "links:")
LUNA = "model:openai/gpt-5.6-luna"
RESULT_VALUE = re.compile(r"(?<![\w.])\d+\.\d{3,}(?![\w.])")


def committed():
    return {name: json.loads(path.read_text(encoding="utf-8")) for name, path in FILES.items()}


def anchor(heading):
    """GitHub's anchor for a heading (DESIGN 12.8, v1.23)."""
    return "#" + re.sub(r"[^\w\- ]", "", heading.lower()).replace(" ", "-")


def summary_row(results, bar, flavor, strategy):
    rows = [r for r in results["summary"]
            if (r["bar"], r["flavor"], r["strategy"]) == (bar, flavor, strategy)]
    assert len(rows) == 1, (bar, flavor, strategy)
    return rows[0]


def words(items):
    return items[0] if len(items) == 1 else ", ".join(items[:-1]) + " and " + items[-1]


def link(name):
    return f"- [{name}]({anchor(name)}): "


def lowest_bar_against_best(results, noun):
    """The RouterBench claim (v1.23), also used for the judges (v1.28) with noun "judge"."""
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == first and r["strategy"].startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    low = summary_row(results, config["bars"][0], "cost_effective", "routed")
    routed = [summary_row(results, bar, flavor, "routed")
              for bar in config["bars"] for flavor in config["flavors"]]
    assert max(r["success"] for r in routed) < best["success"], "a routed row reaches it"
    return (f"at bar {config['bars'][0]}, `cost_effective` routing reaches "
            f"held-out success {low['success']:.3f} at {low['cost_usd'] / best['cost_usd']:.3f} of "
            f"the cost of the best single {noun}, `{best['strategy'][len('model:'):]}`; no routed "
            f"row at any bar reaches that {noun}'s held-out success")


def routerbench_bullet(results):
    return link("RouterBench") + lowest_bar_against_best(results, "model")


def judges_bullet(results):
    return (link("AutoBench judges") + "choosing a judge, scored by agreement with the other "
            "judges and not a human label, " + lowest_bar_against_best(results, "judge"))


def autobench_bullet(results):
    config = results["config"]
    luna = summary_row(results, config["bars"][0], config["flavors"][0], LUNA)
    for bar in config["bars"]:
        for flavor in config["flavors"]:
            r = summary_row(results, bar, flavor, "routed")
            beats = (r["success"] >= luna["success"] and r["cost_usd"] <= luna["cost_usd"]
                     and (r["success"] > luna["success"] or r["cost_usd"] < luna["cost_usd"]))
            assert not beats, f"bar {bar} {flavor} beats it"
    return (link("AutoBench") + f"no routed row beats always calling `{LUNA[len('model:'):]}` "
            f"on held-out success and cost together ({luna['success']:.3f} at "
            f"{luna['cost_usd']:.4f} USD)")


def delegation_bullet(results):
    config = results["config"]
    rows = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
            for r in results["summary"]}
    parents = config["parents"]
    bar, flavor = 0.8, "cost_effective"
    assert bar in config["bars"] and flavor in config["flavors"]
    # v1.40 (DESIGN 12.8): the claim is made on the points with inline work in a call of its own
    points = [i for i, p in enumerate(config["points"]) if p["inline_separate_call"]]
    assert points, "no point with inline work in a call of its own"
    sizes = [f"{config['points'][i]['context_tokens']:,}" for i in points]

    def mean(point, strategy, key):
        return (math.fsum(rows[(bar, flavor, point, p, strategy)][key] for p in parents)
                / len(parents))

    def same(strategy):
        values = {f"{mean(i, strategy, 'success'):.3f}" for i in points}
        assert len(values) == 1, (strategy, values)
        return values.pop()

    for i in points:
        for p in parents:
            dec, dlg = (rows[(bar, flavor, i, p, s)] for s in ("decision", "delegate"))
            assert dec["delegate_rate"] == 1.0, f"not every seed delegates at point {i}"
            assert (dec["success"], dec["cost_usd"]) == (dlg["success"], dlg["cost_usd"]), \
                f"not always delegating at point {i}"
    more = [size for i, size in zip(points, sizes)
            if mean(i, "decision", "cost_usd") > mean(i, "inline", "cost_usd")]
    less = [size for i, size in zip(points, sizes)
            if mean(i, "decision", "cost_usd") < mean(i, "inline", "cost_usd")]
    assert more and less and more + less == sizes, f"more at {more}, less at {less}"
    return (link("Delegation on AutoBench") + f"at bar {bar}, with the brief assumed to carry the "
            f"whole question and inline work in a parent call of its own, the `{flavor}` decision "
            f"delegates on every seed for each of the {len(parents)} parents, so it scores and costs the same as always delegating; its "
            f"mean held-out success over the parents is {same('decision')} against "
            f"{same('inline')} for always inline, and it costs more than always inline at "
            f"{words(more)} context tokens but less at {words(less)}")


BULLETS = {"RouterBench": routerbench_bullet, "AutoBench": autobench_bullet,
           "AutoBench judges": judges_bullet, "Delegation on AutoBench": delegation_bullet}


def glance(files):
    """The list the README evidence section opens with (DESIGN 12.8, v1.23)."""
    return "\n".join([LEAD, ""] + [BULLETS[name](files[name]) for name in FILES]) + "\n"


def evidence_section():
    readme = README.read_text(encoding="utf-8")
    assert readme.count(HEADING) == 1
    return readme.split(HEADING, 1)[1].split("\n## ", 1)[0]


# --- the README ------------------------------------------------------------------------------

def test_readme_opens_the_evidence_section_with_the_glance_list():
    intro = evidence_section().split("\n### ", 1)[0]
    paragraphs = intro.strip("\n").split("\n\n")
    assert len(paragraphs) == 3, paragraphs[1:]
    assert not paragraphs[0].startswith(("- ", "Results at a glance"))
    assert "\n\n".join(paragraphs[1:]) + "\n" == glance(committed())


def test_each_glance_bullet_links_its_subsection_in_heading_order():
    section = evidence_section()
    headings = re.findall(r"^### (.*)$", section, re.M)
    assert headings == list(FILES)
    intro = section.split("\n### ", 1)[0]
    links = re.findall(r"^- \[([^\]]+)\]\((#[^)]+)\): ", intro, re.M)
    assert links == [(h, anchor(h)) for h in headings]


# --- the builder -----------------------------------------------------------------------------

def test_anchor_rule_gives_the_anchors_the_readme_already_links():
    readme = README.read_text(encoding="utf-8")
    for heading in ("Evidence: held-out results on public data", "Inline or sub-agent",
                    "Delegation on AutoBench", "AutoBench judges"):
        assert f"]({anchor(heading)})" in readme, heading
    assert anchor("Evidence: held-out results on public data") == \
        "#evidence-held-out-results-on-public-data"
    assert anchor("Delegation on AutoBench") == "#delegation-on-autobench"
    assert anchor("AutoBench judges") == "#autobench-judges"


def test_each_bullet_holds_at_most_two_result_values():
    for name, bullet in zip(FILES, glance(committed()).splitlines()[2:]):
        assert bullet.startswith(link(name)), bullet
        assert len(RESULT_VALUE.findall(bullet)) == 2, bullet


def test_the_glance_numbers_are_those_of_the_committed_files():
    files = committed()
    text = glance(files)
    for needle in ("held-out success 0.735 at 0.341 of the cost", "`openai/gpt-4-1106-preview`",
                   "(0.872 at 0.3092 USD)", "for each of the 20 parents",
                   "over the parents is 0.855 against 0.670 for always inline",
                   "at 8,000 context tokens but less at 64,000 and 200,000",
                   "held-out success 0.816 at 0.518 of the cost of the best single judge, "
                   "`tencent/hy3`; no routed row at any bar reaches that judge's"):
        assert needle in text, needle
    changed = copy.deepcopy(files)
    summary_row(changed["AutoBench"], 0.6, "cost_effective", LUNA)["cost_usd"] = 0.3095
    assert "(0.872 at 0.3092 USD)" not in glance(changed)


def raise_routerbench(files):
    best = max((r for r in files["RouterBench"]["summary"] if r["strategy"].startswith("model:")),
               key=lambda r: r["success"])
    summary_row(files["RouterBench"], 0.9, "cost_blind", "routed")["success"] = best["success"]


def raise_judges(files):
    best = max((r for r in files["AutoBench judges"]["summary"]
                if r["strategy"].startswith("model:")), key=lambda r: r["success"])
    summary_row(files["AutoBench judges"], 0.8, "cost_effective", "routed")["success"] = \
        best["success"]


def beat_luna(files):
    luna = summary_row(files["AutoBench"], 0.6, "cost_effective", LUNA)
    row = summary_row(files["AutoBench"], 0.7, "cost_effective", "routed")
    row["success"], row["cost_usd"] = luna["success"], luna["cost_usd"] / 2


def delegation_rows(files, point, strategy):
    return [r for r in files["Delegation on AutoBench"]["summary"]
            if (r["bar"], r["flavor"], r["point"], r["strategy"])
            == (0.8, "cost_effective", point, strategy)]


def cheap_decision(files):
    for r in delegation_rows(files, 0, "decision"):
        r["cost_usd"] = 0.0


def costly_paths(files):
    for strategy in ("decision", "delegate"):
        for r in delegation_rows(files, 2, strategy):
            r["cost_usd"] = 1000.0


def worse_decision(files):
    for r in delegation_rows(files, 1, "decision"):
        r["success"] -= 0.02


def one_seed_inline(files):
    delegation_rows(files, 1, "decision")[0]["delegate_rate"] = 0.98


def worse_paths(files):
    for strategy in ("decision", "delegate"):
        for r in delegation_rows(files, 1, strategy):
            r["success"] -= 0.02


@pytest.mark.parametrize("change, match", [
    (raise_routerbench, "a routed row reaches it"),
    (raise_judges, "a routed row reaches it"),
    (beat_luna, "bar 0.7 cost_effective beats it"),
    (cheap_decision, "not always delegating at point 0"),
    (costly_paths, r"more at \['8,000', '200,000'\], less at \['64,000'\]"),
    (worse_decision, "not always delegating at point 1"),
    (one_seed_inline, "not every seed delegates at point 1"),
    (worse_paths, r"\('decision', \{"),
])
def test_a_file_that_breaks_a_claim_fails_the_builder(change, match):
    files = committed()
    glance(files)
    change(files)
    with pytest.raises(AssertionError, match=match):
        glance(files)
