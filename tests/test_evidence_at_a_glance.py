"""v1.23 README evidence at a glance (DESIGN 12.8), written before the README list.

The README evidence section opens with a short list, one bullet per subsection. Every
number and model ID in it is built here from the committed results files (four since v1.28,
which adds the AutoBench judges bullet, five since v1.55, which adds tau2-bench, six since
v1.65, which adds LiveCodeBench, seven since v1.80, which adds delegation on tau2-bench, eight
since v1.164, which adds LLMRouterBench), at the rounding of the subsection tables, and every word that depends on the data (no routed row
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
         "tau2-bench": ROOT / "evidence" / "tau2-bench" / "results.json",
         "LiveCodeBench": ROOT / "evidence" / "livecodebench" / "results.json",
         "LLMRouterBench": ROOT / "evidence" / "llmrouterbench" / "results.json",
         "Delegation on AutoBench": ROOT / "evidence" / "delegation" / "results.json",
         "Delegation on tau2-bench": ROOT / "evidence" / "tau2-bench-delegation" / "results.json"}
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


# v1.166: the first six bullets are the six files the note reads, LLMRouterBench the sixth
POINTER = ("Why routing costs less than the best single model on some of the first six datasets in the list "
           "above, never reaches its held-out success on the first five and passes it on LLMRouterBench: "
           "[research/where-routing-pays.md](research/where-routing-pays.md) sets each dataset's tasks, "
           "calibration halves and picks beside the best single model, read from the same files")
RED = pytest.mark.xfail(strict=True, reason="v1.166 spec ahead of the README paragraph and the script (row R12)")
WHERE_SCRIPT = ROOT / "research" / "where_routing_pays.py"


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


def tau2_bullet(results):
    """v1.55 (DESIGN 12.8): no routed row beats a single agent on both counts at trial 0, and at
    the lowest bar cost_effective costs more than the cheapest agent for no more success."""
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == first and r["strategy"].startswith("model:")]
    cheapest = min(models, key=lambda r: (r["cost_usd"], -r["success"], r["strategy"]))
    for m in models:
        for bar in config["bars"]:
            for flavor in config["flavors"]:
                r = summary_row(results, bar, flavor, "routed")
                beats = (r["success"] >= m["success"] and r["cost_usd"] <= m["cost_usd"]
                         and (r["success"] > m["success"] or r["cost_usd"] < m["cost_usd"]))
                assert not beats, f"bar {bar} {flavor} beats {m['strategy']}"
    low = summary_row(results, config["bars"][0], "cost_effective", "routed")
    assert low["cost_usd"] > cheapest["cost_usd"], "the lowest bar costs no more"
    assert low["success"] <= cheapest["success"], "the lowest bar has more success"
    return (link("tau2-bench") + "on trial 0, no routed row beats any of "
            f"the {len(models)} single agents on held-out success and cost together, and at bar "
            f"{config['bars'][0]} `cost_effective` routing costs {low['cost_usd']:.4f} USD against "
            f"{cheapest['cost_usd']:.4f} for always calling the cheapest agent, "
            f"`{cheapest['strategy'][len('model:'):]}`, for no more held-out success")


def livecodebench_bullet(results):
    """v1.65 (DESIGN 12.8): no cost recorded, so cost_blind only; one held-out success at every
    bar, below always calling the best single model of 12.7."""
    config = results["config"]
    assert config["flavors"] == ["cost_blind"], "a flavor other than cost_blind"
    first = (config["bars"][0], "cost_blind")
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == first and r["strategy"].startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    routed = [summary_row(results, bar, "cost_blind", "routed") for bar in config["bars"]]
    assert len({r["success"] for r in routed}) == 1, "the routed success differs between bars"
    assert routed[0]["success"] < best["success"], "a routed row reaches it"
    return (link("LiveCodeBench") + "the dataset records no cost, so only `cost_blind` routing "
            f"is run; it reaches held-out success {routed[0]['success']:.3f} at every bar, below "
            f"the {best['success']:.3f} of always calling the best single model, "
            f"`{best['strategy'][len('model:'):]}`")


def llmrouterbench_bullet(results):
    """v1.164 (DESIGN 12.8): cost_blind has one held-out success at every bar, above the best single
    model's of 12.7 at 3 decimals, at under half its cost at every bar; at the lowest bar
    cost_effective costs less than cost_blind and falls below that model's success."""
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == first and r["strategy"].startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    blind = [summary_row(results, bar, "cost_blind", "routed") for bar in config["bars"]]
    assert len({f"{r['success']:.3f}" for r in blind}) == 1, "the cost_blind success differs between bars"
    assert float(f"{blind[0]['success']:.3f}") > float(f"{best['success']:.3f}"), \
        "cost_blind is not above the best model"
    assert all(r["cost_usd"] / best["cost_usd"] < 0.5 for r in blind), "cost_blind costs half or more"
    low = summary_row(results, config["bars"][0], "cost_effective", "routed")
    assert low["cost_usd"] < blind[0]["cost_usd"], "the lowest bar costs no less than cost_blind"
    assert float(f"{low['success']:.3f}") < float(f"{best['success']:.3f}"), \
        "the lowest bar reaches the best model"
    return (link("LLMRouterBench") + f"`cost_blind` routing reaches held-out success "
            f"{blind[0]['success']:.3f} at every bar, above the {best['success']:.3f} of always calling "
            f"the best single model, `{best['strategy'][len('model:'):]}`, at less than half its cost; at "
            f"bar {config['bars'][0]} `cost_effective` routing costs less still and falls below that "
            "model's held-out success")


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


def tau2_delegation_bullet(results):
    """Delegation on tau2-bench (v1.80): in `cost_effective` every decision row delegates on
    every seed, and at the lowest bar and point 0 the decision's mean cost over the parents is
    below always inline's, for less held-out success at 3 decimals."""
    config = results["config"]
    bar, parents, flavor = config["bars"][0], config["parents"], "cost_effective"
    point = config["points"][0]
    assert point["inline_separate_call"] is True, "point 0 folds inline work"
    decision = [r for r in results["summary"] if (r["flavor"], r["strategy"]) == (flavor, "decision")]
    assert decision and all(r["delegate_rate"] == 1.0 for r in decision), "not every seed delegates"
    rows = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
            for r in results["summary"]}

    def mean(strategy, key):
        return math.fsum(rows[(bar, flavor, 0, p, strategy)][key] for p in parents) / len(parents)

    dec_cost, inl_cost = mean("decision", "cost_usd"), mean("inline", "cost_usd")
    assert dec_cost < inl_cost, "the decision costs no less than always inline"
    assert float(f"{mean('decision', 'success'):.3f}") < float(f"{mean('inline', 'success'):.3f}"), \
        "the decision has no less held-out success"
    return (link("Delegation on tau2-bench") + f"on trial 0, the `{flavor}` decision delegates on "
            f"every seed for each of the {len(parents)} parents at every bar and point; at bar {bar} "
            f"and {point['context_tokens']:,} context tokens, with inline work in a parent call of "
            f"its own, its mean cost over the parents is {dec_cost:.4f} USD against {inl_cost:.4f} "
            f"for always inline, for less held-out success")


BULLETS = {"RouterBench": routerbench_bullet, "AutoBench": autobench_bullet,
           "AutoBench judges": judges_bullet, "tau2-bench": tau2_bullet,
           "LiveCodeBench": livecodebench_bullet, "LLMRouterBench": llmrouterbench_bullet,
           "Delegation on AutoBench": delegation_bullet,
           "Delegation on tau2-bench": tau2_delegation_bullet}


def glance(files):
    """The list the README evidence section opens with (DESIGN 12.8, v1.23)."""
    return "\n".join([LEAD, ""] + [BULLETS[name](files[name]) for name in FILES]) + "\n"


def evidence_section():
    readme = README.read_text(encoding="utf-8")
    assert readme.count(HEADING) == 1
    return readme.split(HEADING, 1)[1].split("\n## ", 1)[0]


# --- the README ------------------------------------------------------------------------------

@RED
def test_readme_opens_the_evidence_section_with_the_glance_list():
    intro = evidence_section().split("\n### ", 1)[0]
    paragraphs = intro.strip("\n").split("\n\n")
    assert len(paragraphs) == 4, paragraphs[1:]
    assert not paragraphs[0].startswith(("- ", "Results at a glance"))
    assert "\n\n".join(paragraphs[1:3]) + "\n" == glance(committed())
    # v1.124: one paragraph after the bullets links the note on where routing pays
    assert paragraphs[3] == POINTER


def test_the_pointer_link_resolves_to_the_note():
    target = re.findall(r"\]\(([^)]+)\)", POINTER)
    assert target == ["research/where-routing-pays.md"]
    assert (README.parent / target[0]).is_file()


@RED
def test_the_pointer_names_the_files_the_note_reads():
    """v1.166: the first six bullets are the note's six datasets, in its order, and the
    LLMRouterBench claim of the pointer is the one its bullet asserts; the note's tests check
    on the files that no routed row of the first five reaches the best single model."""
    text = WHERE_SCRIPT.read_text(encoding="utf-8")
    block = text.split("DATASETS = (\n", 1)[1].split("\n)\n", 1)[0]
    listed = re.findall(r'^    \("([^"]+)", "([^"]+)"\),$', block, re.M)
    assert listed == [(n, str(FILES[n].relative_to(ROOT))) for n in list(FILES)[:6]]
    assert list(FILES)[5] == "LLMRouterBench"
    assert "never reaches its held-out success on the first five and passes it on LLMRouterBench" in POINTER
    llmrouterbench_bullet(committed()["LLMRouterBench"])


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
    assert anchor("tau2-bench") == "#tau2-bench"
    assert anchor("LiveCodeBench") == "#livecodebench"
    assert anchor("LLMRouterBench") == "#llmrouterbench"
    assert anchor("Delegation on tau2-bench") == "#delegation-on-tau2-bench"


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
                   "`tencent/hy3`; no routed row at any bar reaches that judge's",
                   "on trial 0, no routed row beats any of the 4 single agents",
                   "costs 9.1340 USD against 3.6044 for always calling the cheapest agent, "
                   "`openai/gpt-4.1-mini-2025-04-14`, for no more held-out success",
                   "only `cost_blind` routing is run; it reaches held-out success 0.902 at every "
                   "bar, below the 0.909 of always calling the best single model, "
                   "`openai/o4-mini-high`",
                   "`cost_blind` routing reaches held-out success 0.615 at every bar, above the 0.592 of "
                   "always calling the best single model, `google/gemini-2.5-pro`, at less than half its "
                   "cost; at bar 0.1 `cost_effective` routing costs less still and falls below"):
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


def tau2_beats_an_agent(files):
    best = max((r for r in files["tau2-bench"]["summary"] if r["strategy"].startswith("model:")),
               key=lambda r: r["success"])
    row = summary_row(files["tau2-bench"], 0.8, "cost_blind", "routed")
    row["success"], row["cost_usd"] = best["success"], best["cost_usd"] / 2


def tau2_more_success(files):
    summary_row(files["tau2-bench"], 0.3, "cost_effective", "routed")["success"] = 0.55


def tau2_cheaper(files):
    summary_row(files["tau2-bench"], 0.3, "cost_effective", "routed")["cost_usd"] = 1.0


def lcb_routed(files):
    return [r for r in files["LiveCodeBench"]["summary"] if r["strategy"] == "routed"]


def lcb_second_flavor(files):
    files["LiveCodeBench"]["config"]["flavors"].append("cost_effective")


def lcb_one_bar_differs(files):
    lcb_routed(files)[-1]["success"] -= 0.01


def lcb_reaches_best(files):
    best = max(r["success"] for r in files["LiveCodeBench"]["summary"]
               if r["strategy"].startswith("model:"))
    for r in lcb_routed(files):
        r["success"] = best


def lrb_rows(files, flavor):
    return [r for r in files["LLMRouterBench"]["summary"]
            if (r["flavor"], r["strategy"]) == (flavor, "routed")]


def lrb_blind_differs(files):
    lrb_rows(files, "cost_blind")[-1]["success"] -= 0.01


def lrb_blind_not_above(files):
    for r in lrb_rows(files, "cost_blind"):
        r["success"] = 0.592


def lrb_blind_half(files):
    lrb_rows(files, "cost_blind")[3]["cost_usd"] = 183.3


def lrb_low_dearer(files):
    lrb_rows(files, "cost_effective")[0]["cost_usd"] = 200.0


def lrb_low_reaches(files):
    lrb_rows(files, "cost_effective")[0]["success"] = 0.5924


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


def tau2_delegation_rows(files, strategy):
    return [r for r in files["Delegation on tau2-bench"]["summary"]
            if (r["bar"], r["flavor"], r["point"], r["strategy"])
            == (0.3, "cost_effective", 0, strategy)]


def tau2_delegation_one_seed_inline(files):
    [r for r in files["Delegation on tau2-bench"]["summary"]
     if (r["flavor"], r["strategy"]) == ("cost_effective", "decision")][-1]["delegate_rate"] = 0.98


def tau2_delegation_dearer(files):
    for r in tau2_delegation_rows(files, "decision"):
        r["cost_usd"] = 1000.0


def tau2_delegation_better(files):
    for r in tau2_delegation_rows(files, "decision"):
        r["success"] = 0.9


@pytest.mark.parametrize("change, match", [
    (raise_routerbench, "a routed row reaches it"),
    (raise_judges, "a routed row reaches it"),
    (beat_luna, "bar 0.7 cost_effective beats it"),
    (tau2_beats_an_agent, "bar 0.8 cost_blind beats model:anthropic/claude-3-7-sonnet-20250219"),
    (tau2_more_success, "the lowest bar has more success"),
    (tau2_cheaper, "the lowest bar costs no more"),
    (lcb_second_flavor, "a flavor other than cost_blind"),
    (lcb_one_bar_differs, "the routed success differs between bars"),
    (lcb_reaches_best, "a routed row reaches it"),
    (lrb_blind_differs, "the cost_blind success differs between bars"),
    (lrb_blind_not_above, "cost_blind is not above the best model"),
    (lrb_blind_half, "cost_blind costs half or more"),
    (lrb_low_dearer, "the lowest bar costs no less than cost_blind"),
    (lrb_low_reaches, "the lowest bar reaches the best model"),
    (cheap_decision, "not always delegating at point 0"),
    (costly_paths, r"more at \['8,000', '200,000'\], less at \['64,000'\]"),
    (worse_decision, "not always delegating at point 1"),
    (one_seed_inline, "not every seed delegates at point 1"),
    (worse_paths, r"\('decision', \{"),
    (tau2_delegation_one_seed_inline, "not every seed delegates"),
    (tau2_delegation_dearer, "the decision costs no less than always inline"),
    (tau2_delegation_better, "the decision has no less held-out success"),
])
def test_a_file_that_breaks_a_claim_fails_the_builder(change, match):
    files = committed()
    glance(files)
    change(files)
    with pytest.raises(AssertionError, match=match):
        glance(files)
