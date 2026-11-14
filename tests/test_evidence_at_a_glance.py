"""v1.23 README evidence at a glance (DESIGN 12.8), written before the README list.

The README evidence section opens with a short list, one bullet per subsection. Every
number and model ID in it is built here from the committed results files (four since v1.28,
which adds the AutoBench judges bullet, five since v1.55, which adds tau2-bench, six since
v1.65, which adds LiveCodeBench, seven since v1.80, which adds delegation on tau2-bench, eight
since v1.164, which adds LLMRouterBench, nine since v1.200, which adds delegation on LLMRouterBench,
ten since v1.297, which adds the LLM Routing Response Bank), at the rounding of the subsection tables, and every word that depends on the data (no routed row
reaches or beats, every seed, more, less) is asserted against those files, so the list cannot
drift from them or keep a claim a regenerated file no longer supports.

v1.258 (row DOC15): a second paragraph after the routing pointer links the two delegation notes, its
figures read from their committed results blocks, so it runs in CI where the pinned files are not cached.

v1.328 (row R29): the per-item note reruns the response bank too, so the delegation paragraph's
cut is the one of its five blocks and `on the datasets of the first three, ` goes; the tests that
read the paragraph or the note's blocks were strict xfails until v1.329 landed the block.

v1.384 (row DOC27, DESIGN 12.21 Seeds in the README): the response-bank bullet says its `cost_blind`
gain and cost ratio are means over the committed seeds and that the gain holds on most of them, a
claim checked on the Results block of research/response-bank-seeds.md, which gives the count.
"""

import copy
import decimal
import importlib.util
import json
import math
import re
from pathlib import Path

import pytest

from test_research_response_bank_seeds import NOTE as SEEDS_NOTE, blind_seeds, seeds_block

ROOT = Path(__file__).resolve().parents[1]
README = ROOT / "README.md"
HEADING = "\n## Evidence: held-out results on public data\n"
FILES = {"RouterBench": ROOT / "evidence" / "routerbench" / "results.json",
         "AutoBench": ROOT / "evidence" / "autobench-2026" / "results.json",
         "AutoBench judges": ROOT / "evidence" / "autobench-judges" / "results.json",
         "tau2-bench": ROOT / "evidence" / "tau2-bench" / "results.json",
         "LiveCodeBench": ROOT / "evidence" / "livecodebench" / "results.json",
         "LLMRouterBench": ROOT / "evidence" / "llmrouterbench" / "results.json",
         "LLM Routing Response Bank": ROOT / "evidence" / "response-bank" / "results.json",
         "Delegation on AutoBench": ROOT / "evidence" / "delegation" / "results.json",
         "Delegation on tau2-bench": ROOT / "evidence" / "tau2-bench-delegation" / "results.json",
         "Delegation on LLMRouterBench": ROOT / "evidence" / "llmrouterbench-delegation" / "results.json",
         "Delegation on the LLM Routing Response Bank":
             ROOT / "evidence" / "response-bank-delegation" / "results.json"}
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


# v1.303: the first seven bullets are the seven files the note reads (six, LLMRouterBench the sixth,
# from v1.166), and the datasets it passes on are built from them in test_the_pointer_names_...
POINTER = ("Why routing costs less than the best single model on some of the first seven datasets in the list "
           "above, never reaches its held-out success on the first five and passes it on LLMRouterBench and "
           "the LLM Routing Response Bank: [research/where-routing-pays.md](research/where-routing-pays.md) "
           "sets each dataset's tasks, calibration halves and picks beside the best single model, read from "
           "the same files")
NOTE_FILES = 7
COUNT = {7: "seven"}
# a dataset name the README gives with an article
ARTICLE = {"LLM Routing Response Bank": "the "}
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


def response_bank_bullet(results, block=None):
    """v1.296 (DESIGN 12.8): at the lowest bar cost_effective reaches a held-out success at a share of
    the best single model's cost (12.7) and costs less than the cheapest single model (12.15) for more
    success at 3 decimals; cost_blind passes the best model's success at 3 decimals at every bar, at
    more than twice its cost. v1.384 (12.21 Seeds in the README): both in the mean over the committed
    seeds, and on most of them by the seeds note's `block`, which holds the committed seeds."""
    config = results["config"]
    n = len(config["seeds"])
    seeds, above, _below = blind_seeds(seeds_block(SEEDS_NOTE) if block is None else block)
    assert seeds == n, "the seeds note's seeds are not the committed file's"
    assert n / 2 < above < n, "cost_blind is not above on most seeds and below on the rest"
    first = (config["bars"][0], config["flavors"][0])
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == first and r["strategy"].startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    cheapest = min(models, key=lambda r: (r["cost_usd"], -r["success"], r["strategy"]))
    low = summary_row(results, config["bars"][0], "cost_effective", "routed")
    assert low["cost_usd"] < cheapest["cost_usd"], "the lowest bar costs no less than the cheapest model"
    assert float(f"{low['success']:.3f}") > float(f"{cheapest['success']:.3f}"), \
        "the lowest bar has no more success than the cheapest model"
    blind = [summary_row(results, bar, "cost_blind", "routed") for bar in config["bars"]]
    assert all(float(f"{r['success']:.3f}") > float(f"{best['success']:.3f}") for r in blind), \
        "cost_blind is not above the best model"
    assert all(r["cost_usd"] > 2 * best["cost_usd"] for r in blind), "cost_blind costs twice the best model or less"
    return (link("LLM Routing Response Bank") + f"at bar {config['bars'][0]}, `cost_effective` routing "
            f"reaches held-out success {low['success']:.3f} at {low['cost_usd'] / best['cost_usd']:.3f} of "
            f"the cost of the best single model, `{best['strategy'][len('model:'):]}`, and costs less than "
            f"always calling the cheapest model, `{cheapest['strategy'][len('model:'):]}`, for more held-out "
            "success; `cost_blind` routing passes the best single model's held-out success at every bar in "
            f"the mean over {n} seeds, and on most of them ([seed by seed](research/response-bank-seeds.md)), "
            "but at more than twice its cost in the mean")


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


def llmrouterbench_delegation_bullet(results):
    """Delegation on LLMRouterBench (v1.200): at the lowest bar and point 0 every `cost_effective`
    decision row delegates on every seed, the decision's mean cost over the parents is below
    always inline's for no less held-out success at 3 decimals, and it costs more than always
    inline for some parents but not all, a count that the bullet states."""
    config = results["config"]
    bar, parents, flavor = config["bars"][0], config["parents"], "cost_effective"
    point = config["points"][0]
    assert point["inline_separate_call"] is True, "LLMRouterBench delegation: point 0 folds inline work"
    rows = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
            for r in results["summary"]}
    decision = [rows[(bar, flavor, 0, p, "decision")] for p in parents]
    assert all(r["delegate_rate"] == 1.0 for r in decision), \
        "LLMRouterBench delegation: not every seed delegates at the lowest bar and point 0"

    def mean(strategy, key):
        return math.fsum(rows[(bar, flavor, 0, p, strategy)][key] for p in parents) / len(parents)

    dec_cost, inl_cost = mean("decision", "cost_usd"), mean("inline", "cost_usd")
    assert dec_cost < inl_cost, "LLMRouterBench delegation: the decision costs no less than always inline"
    assert float(f"{mean('decision', 'success'):.3f}") >= float(f"{mean('inline', 'success'):.3f}"), \
        "LLMRouterBench delegation: the decision has less held-out success"
    more = [p for p in parents
            if rows[(bar, flavor, 0, p, "decision")]["cost_usd"] > rows[(bar, flavor, 0, p, "inline")]["cost_usd"]]
    assert 0 < len(more) < len(parents), f"LLMRouterBench delegation: dearer than inline for {len(more)} parents"
    return (link("Delegation on LLMRouterBench") + f"at bar {bar} and {point['context_tokens']:,} context tokens, "
            f"with inline work in a parent call of its own, the `{flavor}` decision delegates on every seed for "
            f"each of the {len(parents)} parents; its mean cost over the parents is {dec_cost:.4f} USD against "
            f"{inl_cost:.4f} for always inline, for no less held-out success, but it costs more than always "
            f"inline for {len(more)} of the {len(parents)} parents")


def response_bank_delegation_bullet(results):
    """Delegation on the LLM Routing Response Bank (v1.316): at the lowest bar and point 0 every
    `cost_effective` decision row delegates on every seed and costs less than its parent's always inline row,
    and the decision's mean held-out success over the parents is below always inline's at 3 decimals, the
    unfavourable result the bullet states without the two values, since a bullet holds two (v1.23, v1.317)."""
    name = "Delegation on the LLM Routing Response Bank"
    config = results["config"]
    bar, parents, flavor = config["bars"][0], config["parents"], "cost_effective"
    point = config["points"][0]
    assert point["inline_separate_call"] is True, "response-bank delegation: point 0 folds inline work"
    rows = {(r["bar"], r["flavor"], r["point"], r["parent"], r["strategy"]): r
            for r in results["summary"]}
    decision = [rows[(bar, flavor, 0, p, "decision")] for p in parents]
    assert all(r["delegate_rate"] == 1.0 for r in decision), \
        "response-bank delegation: not every seed delegates at the lowest bar and point 0"
    dearer = [p for p in parents
              if rows[(bar, flavor, 0, p, "decision")]["cost_usd"] >= rows[(bar, flavor, 0, p, "inline")]["cost_usd"]]
    assert not dearer, f"response-bank delegation: the decision costs no less than inline for {dearer}"

    def mean(strategy, key):
        return math.fsum(rows[(bar, flavor, 0, p, strategy)][key] for p in parents) / len(parents)

    dec_cost, inl_cost = mean("decision", "cost_usd"), mean("inline", "cost_usd")
    dec_success, inl_success = f"{mean('decision', 'success'):.3f}", f"{mean('inline', 'success'):.3f}"
    assert float(dec_success) < float(inl_success), \
        "response-bank delegation: the decision has no less held-out success"
    return (link(name) + f"at bar {bar} and {point['context_tokens']:,} context tokens, with inline work in a "
            f"parent call of its own, the `{flavor}` decision delegates on every seed for each of the "
            f"{len(parents)} parents and costs less than always inline for each; its mean cost over the parents "
            f"is {dec_cost:.4f} USD against {inl_cost:.4f} for always inline, for less held-out success")


BULLETS = {"RouterBench": routerbench_bullet, "AutoBench": autobench_bullet,
           "AutoBench judges": judges_bullet, "tau2-bench": tau2_bullet,
           "LiveCodeBench": livecodebench_bullet, "LLMRouterBench": llmrouterbench_bullet,
           "LLM Routing Response Bank": response_bank_bullet,
           "Delegation on AutoBench": delegation_bullet,
           "Delegation on tau2-bench": tau2_delegation_bullet,
           "Delegation on LLMRouterBench": llmrouterbench_delegation_bullet,
           "Delegation on the LLM Routing Response Bank": response_bank_delegation_bullet}


def glance(files):
    """The list the README evidence section opens with (DESIGN 12.8, v1.23)."""
    return "\n".join([LEAD, ""] + [BULLETS[name](files[name]) for name in FILES]) + "\n"


def evidence_section():
    readme = README.read_text(encoding="utf-8")
    assert readme.count(HEADING) == 1
    return readme.split(HEADING, 1)[1].split("\n## ", 1)[0]


# --- the README ------------------------------------------------------------------------------

@pytest.mark.xfail(strict=True, reason="v1.385 lands the README wording (row DOC27)")
def test_readme_opens_the_evidence_section_with_the_glance_list():
    intro = evidence_section().split("\n### ", 1)[0]
    paragraphs = intro.strip("\n").split("\n\n")
    # v1.258: a fifth paragraph, the delegation pointer, is checked below
    assert len(paragraphs) == 5, paragraphs[1:]
    assert not paragraphs[0].startswith(("- ", "Results at a glance"))
    assert "\n\n".join(paragraphs[1:3]) + "\n" == glance(committed())
    # v1.124: one paragraph after the bullets links the note on where routing pays
    assert paragraphs[3] == POINTER


def test_the_pointer_link_resolves_to_the_note():
    target = re.findall(r"\]\(([^)]+)\)", POINTER)
    assert target == ["research/where-routing-pays.md"]
    assert (README.parent / target[0]).is_file()


def passes_best(results):
    """v1.303: whether some routed row is above the held-out success of the best single model of 12.7."""
    config = results["config"]
    first = (config["bars"][0], config["flavors"][0])
    models = [r for r in results["summary"]
              if (r["bar"], r["flavor"]) == first and r["strategy"].startswith("model:")]
    best = min(models, key=lambda r: (-r["success"], r["cost_usd"], r["strategy"]))
    return any(summary_row(results, bar, flavor, "routed")["success"] > best["success"]
               for bar in config["bars"] for flavor in config["flavors"])


def routing_pointer(files):
    """v1.303 (DESIGN 12.8): the paragraph after the bullets, its count of the note's files and the
    datasets where routing passes the best single model built from the files; the others must be
    the first five."""
    names = list(FILES)[:NOTE_FILES]
    passing = [n for n in names if passes_best(files[n])]
    assert [n for n in names if n not in passing] == names[:5], passing
    return ("Why routing costs less than the best single model on some of the first "
            f"{COUNT[len(names)]} datasets in the list above, never reaches its held-out success on the "
            f"first five and passes it on {words([ARTICLE.get(n, '') + n for n in passing])}: "
            "[research/where-routing-pays.md](research/where-routing-pays.md) sets each dataset's tasks, "
            "calibration halves and picks beside the best single model, read from the same files")


def test_the_pointer_names_the_files_the_note_reads():
    """v1.303: the first seven bullets are the note's seven datasets, in its order (six from
    v1.166), and the pointer is built from their files; the LLMRouterBench and response-bank claims
    are those their bullets assert, and the note's tests check on the files that no routed row of
    the first five reaches the best single model."""
    text = WHERE_SCRIPT.read_text(encoding="utf-8")
    block = text.split("DATASETS = (\n", 1)[1].split("\n)\n", 1)[0]
    listed = re.findall(r'^    \("([^"]+)", "([^"]+)"\),$', block, re.M)
    assert listed == [(n, str(FILES[n].relative_to(ROOT))) for n in list(FILES)[:NOTE_FILES]]
    assert list(FILES)[5:NOTE_FILES] == ["LLMRouterBench", "LLM Routing Response Bank"]
    files = committed()
    assert routing_pointer(files) == POINTER
    llmrouterbench_bullet(files["LLMRouterBench"])
    response_bank_bullet(files["LLM Routing Response Bank"])


def test_the_pointer_fails_when_the_seventh_file_stops_passing():
    """v1.303: a seventh file whose routed rows all fall below the best single model leaves the
    datasets routing does not pass other than the first five, so the builder fails."""
    files = committed()
    results = files["LLM Routing Response Bank"]
    for r in results["summary"]:
        if r["strategy"] == "routed":
            r["success"] = 0.0
    with pytest.raises(AssertionError):
        routing_pointer(files)
    assert routing_pointer(committed()) == POINTER


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


def lrbd_rows(files, strategy):
    return [r for r in files["Delegation on LLMRouterBench"]["summary"]
            if (r["bar"], r["flavor"], r["point"], r["strategy"]) == (0.1, "cost_effective", 0, strategy)]


def lrbd_one_seed_inline(files):
    lrbd_rows(files, "decision")[-1]["delegate_rate"] = 0.98


def lrbd_dearer(files):
    for r in lrbd_rows(files, "decision"):
        r["cost_usd"] = 1000.0


def lrbd_worse(files):
    for r in lrbd_rows(files, "decision"):
        r["success"] = 0.1


def lrbd_dearer_for_none(files):
    for r in lrbd_rows(files, "inline"):
        r["cost_usd"] = 1000.0


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
    (lrbd_one_seed_inline, "LLMRouterBench delegation: not every seed delegates"),
    (lrbd_dearer, "LLMRouterBench delegation: the decision costs no less than always inline"),
    (lrbd_worse, "LLMRouterBench delegation: the decision has less held-out success"),
    (lrbd_dearer_for_none, "LLMRouterBench delegation: dearer than inline for 0 parents"),
])
def test_a_file_that_breaks_a_claim_fails_the_builder(change, match):
    files = committed()
    glance(files)
    change(files)
    with pytest.raises(AssertionError, match=match):
        glance(files)



# --- v1.296 (row E20e): the response-bank bullet (v1.297: in FILES and BULLETS) -------------

RESPONSE_BANK = FILES["LLM Routing Response Bank"]


def response_bank():
    return json.loads(RESPONSE_BANK.read_text(encoding="utf-8"))


def rbank_rows(results, flavor):
    return [r for r in results["summary"] if (r["flavor"], r["strategy"]) == (flavor, "routed")]


def rbank_low_dearer(results):
    cheapest = summary_row(results, 0.8, "cost_effective", "model:z-ai/glm-5.3-flash")
    rbank_rows(results, "cost_effective")[0]["cost_usd"] = cheapest["cost_usd"]


def rbank_low_no_more(results):
    rbank_rows(results, "cost_effective")[0]["success"] = 0.8454


def rbank_blind_not_above(results):
    rbank_rows(results, "cost_blind")[-1]["success"] = 0.8724


def rbank_blind_cheap(results):
    rbank_rows(results, "cost_blind")[0]["cost_usd"] = 54.5


def test_the_response_bank_bullet_is_built_from_the_committed_file():
    bullet = response_bank_bullet(response_bank())
    assert bullet == ("- [LLM Routing Response Bank](#llm-routing-response-bank): at bar 0.8, `cost_effective` "
                      "routing reaches held-out success 0.847 at 0.201 of the cost of the best single model, "
                      "`deepseek/deepseek-v4-pro`, and costs less than always calling the cheapest model, "
                      "`z-ai/glm-5.3-flash`, for more held-out success; `cost_blind` routing passes the best "
                      "single model's held-out success at every bar in the mean over 50 seeds, and on most of "
                      "them ([seed by seed](research/response-bank-seeds.md)), but at more than twice its cost "
                      "in the mean")
    assert len(RESULT_VALUE.findall(bullet)) == 2


SEEDS_42 = "above on 42, equal on 0, below on 8 of 50 seeds"


@pytest.mark.parametrize("new, match", [
    ("above on 50, equal on 0, below on 0 of 50 seeds", "cost_blind is not above on most seeds"),
    ("above on 25, equal on 0, below on 25 of 50 seeds", "cost_blind is not above on most seeds"),
    ("above on 42, equal on 0, below on 7 of 49 seeds", "the seeds note's seeds are not the committed file's"),
])
def test_a_seeds_block_that_breaks_the_glance_claim_fails_its_bullet(new, match):
    """v1.384: the bullet's `on most of them` needs more than half the committed seeds and fewer
    than all; each case edits every line of the note's block that gives cost_blind's line."""
    block = seeds_block(SEEDS_NOTE)
    assert block.count(SEEDS_42) == 4
    response_bank_bullet(response_bank(), block)
    with pytest.raises(AssertionError, match=match):
        response_bank_bullet(response_bank(), block.replace(SEEDS_42, new))


@pytest.mark.parametrize("change, match", [
    (rbank_low_dearer, "the lowest bar costs no less than the cheapest model"),
    (rbank_low_no_more, "the lowest bar has no more success than the cheapest model"),
    (rbank_blind_not_above, "cost_blind is not above the best model"),
    (rbank_blind_cheap, "cost_blind costs twice the best model or less"),
])
def test_a_file_that_breaks_a_response_bank_claim_fails_its_bullet(change, match):
    results = response_bank()
    response_bank_bullet(results)
    change(results)
    with pytest.raises(AssertionError, match=match):
        response_bank_bullet(results)


@pytest.mark.xfail(strict=True, reason="v1.385 lands the README wording (row DOC27)")
def test_the_glance_list_holds_the_response_bank_bullet_after_llmrouterbench():
    lines = evidence_section().split("\n### ", 1)[0].splitlines()
    bullet = response_bank_bullet(response_bank())
    assert bullet in lines
    assert lines[lines.index(bullet) - 1].startswith(link("LLMRouterBench"))
    assert anchor("LLM Routing Response Bank") == "#llm-routing-response-bank"

# --- v1.258 (row DOC15): where delegation pays, at a glance -----------------------------------

DESIGN = ROOT / "DESIGN.md"
PAYS_NOTE = ROOT / "research" / "where-delegation-pays.md"
PAYS_SCRIPT = ROOT / "research" / "where_delegation_pays.py"
PER_ITEM_NOTE = ROOT / "research" / "per-item-delegation.md"
PAYS_LINK = "[research/where-delegation-pays.md](research/where-delegation-pays.md)"
PER_ITEM_LINK = "[research/per-item-delegation.md](research/per-item-delegation.md)"
# v1.323 (row R28): the first note reads all four delegation subsections' files; v1.328 (row R29): the second's
# five blocks rerun all four datasets
DELEGATION = ("Delegation on AutoBench", "Delegation on tau2-bench", "Delegation on LLMRouterBench",
              "Delegation on the LLM Routing Response Bank")
PER_ITEM_COMMAND = "$ python research/per_item_delegation.py "
# the five runs of the per-item note: no --dataset is LLMRouterBench (DESIGN 13.8 v1.227 to v1.233, v1.328)
PER_ITEM_RUNS = [None, "autobench", "tau2-bench", "tau2-bench-pooled", "response-bank"]
# every line of a block's table, between its header and its first `pick, switched share by point` line
TABLE_ROW = re.compile(r"^  (cost_effective|cost_blind) +(\d\.\d) +(pick|size rule) +\d+ +[\d,]+ / [\d,]+ +"
                       r"(?:-|\d\.\d{4}) +(\d\.\d{4}) +([+-]\d\.\d{4}) +\d+$")
TABLE_END = "  pick, switched share by point, "


def pays_totals(note):
    """{flavor: {column: count}} from the `All five files` lines (`All four files` to v1.322) of the note's
    `## Results` block."""
    section = note.split("\n## Results\n", 1)[1].split("\n## ", 1)[0]
    blocks = re.findall(r"^```text\n(.*?)^```$", section, re.M | re.S)
    assert len(blocks) == 1, "one text block in ## Results"
    lines = blocks[0].split("\nAll five files\n", 1)[1].splitlines()
    columns = re.split(r"  +", lines[0].strip())
    assert columns[:2] == ["flavor", "bar"] and "= delegate" in columns and "better" in columns, columns
    totals = {}
    for line in lines[1:]:
        flavor, *values = re.split(r"  +", line.strip())
        assert values[0] == "all" and len(values) == len(columns) - 1, line
        totals[flavor] = dict(zip(columns[2:], map(int, values[1:])))
    assert sorted(totals) == ["cost_blind", "cost_effective"], totals
    return totals


def per_item_blocks(note):
    """{--dataset value or None: block text} for the note's text blocks of the per-item script."""
    blocks = {}
    for block in re.findall(r"^```text\n(.*?)^```$", note, re.M | re.S):
        command = block.split("\n", 1)[0]
        if not command.startswith(PER_ITEM_COMMAND):
            continue
        found = re.search(r"--dataset (\S+)", command)
        name = found[1] if found else None
        assert name not in blocks, command
        blocks[name] = block
    return blocks


def table_rows(block):
    """(flavor, bar, strategy, cost / decision, success - decision) of every table line of a per-item block. Fails
    closed (DESIGN 12.8 v1.260, review iter-176 must-fix 1): each line from the header to the first `pick, switched
    share by point` line must be a table row, and both strategies of both flavors must give the same bars, each
    once, so a malformed or missing row fails instead of being skipped."""
    lines = block.splitlines()
    heads = [k for k, line in enumerate(lines) if line.startswith("  flavor ")]
    ends = [k for k, line in enumerate(lines) if line.startswith(TABLE_END)]
    assert len(heads) == 1 and ends and ends[0] > heads[0], "no table between a header and its end"
    rows = []
    for line in lines[heads[0] + 1:ends[0]]:
        found = TABLE_ROW.match(line)
        assert found, f"not a table row: {line!r}"
        rows.append(found.groups())
    bars = {(f, k): [r[1] for r in rows if (r[0], r[2]) == (f, k)]
            for f in ("cost_effective", "cost_blind") for k in ("pick", "size rule")}
    first = bars[("cost_effective", "pick")]
    assert first and len(set(first)) == len(first) and all(b == first for b in bars.values()), \
        f"the strategies' bars differ: {bars}"
    return rows


def size_rule_cut(note):
    """One minus the smallest `cost_effective` `size rule` `cost / decision` of the note's blocks, as a percent to
    two significant figures (DESIGN 13.8 v1.236 rounding), after checking that none loses mean success."""
    blocks = per_item_blocks(note)
    assert sorted(blocks, key=str) == sorted(PER_ITEM_RUNS, key=str), sorted(blocks, key=str)
    rows = []
    for name in PER_ITEM_RUNS:
        rows += [(decimal.Decimal(cost), success) for flavor, _bar, strategy, cost, success in table_rows(blocks[name])
                 if (flavor, strategy) == ("cost_effective", "size rule")]
    assert all(success.startswith("+") for _cost, success in rows), "a size rule row loses mean success"
    value = (1 - min(cost for cost, _success in rows)) * 100
    step = decimal.Decimal(1).scaleb(value.adjusted() - 1)
    return format(value.quantize(step, decimal.ROUND_HALF_UP).normalize(), "f")


def better_rows():
    """(flavor, decision, inline, delegate) (success, cost) pairs of every `better` row of the committed files the
    first note's script reads (DESIGN 12.8 v1.323)."""
    spec = importlib.util.spec_from_file_location("where_delegation_pays_for_glance", PAYS_SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    rows = []
    for _, rel in module.DATASETS:
        for key, group in module.rows_of(json.loads((ROOT / rel).read_text(encoding="utf-8")), rel).items():
            if module.classify(group["decision"], group["inline"], group["delegate"]) == "better":
                rows.append((key[1],) + tuple(module.pair(group[s]) for s in module.STRATEGIES))
    return rows


def delegation_pointer(pays_note, per_item_note):
    """The paragraph after the routing pointer (DESIGN 12.8 v1.258, v1.323), its figures from the two notes."""
    totals = pays_totals(pays_note)
    effective = totals["cost_effective"]
    assert totals["cost_blind"]["better"] == 0, "a `cost_blind` row is better than both"
    better = better_rows()
    assert len(better) == effective["better"], (better, effective)
    for flavor, decision, inline, delegate in better:
        assert flavor == "cost_effective" and decision[0] == delegate[0], "a `better` row is not at delegating's success"
        assert decision[1] < min(inline[1], delegate[1]), "a `better` row costs no less than a fixed policy"
    return ("Whether choosing per task between inline work and a sub-agent beats a fixed policy, on the datasets of "
            f"the four delegation bullets above: {PAYS_LINK} finds the `cost_effective` decision equal to always "
            f"delegating on {effective['= delegate']:,} of their {effective['rows']:,} (bar, point, parent) rows and "
            f"better than both fixed policies on {effective['better']:,}, each a `cost_effective` row at always "
            "delegating's held-out success for less cost than either, and "
            f"{PER_ITEM_LINK} finds that taking each held-out item's cheaper path only on the cells where the "
            f"decision chose by cost cuts a bar's summed cost by at most {size_rule_cut(per_item_note)}%, at no lower "
            "mean success")


def notes():
    return PAYS_NOTE.read_text(encoding="utf-8"), PER_ITEM_NOTE.read_text(encoding="utf-8")


def test_design_specifies_the_delegation_pointer():
    text = DESIGN.read_text(encoding="utf-8")
    section = text.split("\n### 12.8 ", 1)[1].split("\n### ", 1)[0]
    bullets = [line for line in section.splitlines()
               if line.startswith("- Where delegation pays at a glance (v1.258, row DOC15): ")]
    assert len(bullets) == 1
    for phrase in ("`research/where-delegation-pays.md`", "`research/per-item-delegation.md`", "`All five files`",
                   "`= delegate`", "`better`", "`size rule` `cost / decision`", "13.5 row 3", "`success - decision`",
                   "two significant figures", "fifth and last paragraph", "strict xfail", "No library code",
                   "(v1.328, row R29)", "drops `on the datasets of the first three, `"):
        assert phrase in bullets[0], phrase
    assert "then (v1.258) a blank line and the one paragraph of the where-delegation-pays-at-a-glance bullet " \
           "below, and by nothing else." in section


def test_the_delegation_pointer_follows_the_routing_one():
    intro = evidence_section().split("\n### ", 1)[0]
    paragraphs = intro.strip("\n").split("\n\n")
    assert len(paragraphs) == 5, paragraphs[3:]
    assert paragraphs[3] == POINTER
    assert paragraphs[4] == delegation_pointer(*notes())


def test_the_delegation_pointer_figures_on_the_committed_notes():
    """The figures the paragraph gives on the committed notes, beside the counts each note's prose states."""
    pays, per_item = notes()
    effective = pays_totals(pays)["cost_effective"]
    facts = pays.split("\n## Facts\n", 1)[1].split("\n## ", 1)[0]
    assert f"on {effective['= delegate']} of the {effective['rows']} rows" in facts
    cut = size_rule_cut(per_item)
    recommendation = per_item.split("\n## Recommendation\n", 1)[1].split("\n## ", 1)[0]
    assert f"saves at most {cut}% of a bar's summed cost" in recommendation
    text = delegation_pointer(pays, per_item)
    # the second finding is the size rule's, not choosing the path on every item (DESIGN 12.8 v1.258)
    assert "only on the cells where the decision chose by cost" in text


def test_the_delegation_pointer_links_resolve_in_order():
    text = delegation_pointer(*notes())
    targets = re.findall(r"\]\(([^)]+)\)", text)
    assert targets == ["research/where-delegation-pays.md", "research/per-item-delegation.md"]
    assert all((README.parent / t).is_file() for t in targets)


def test_the_delegation_bullets_are_the_subsections_the_notes_read():
    # v1.323: the first note reads the four delegation subsections' files; v1.328: the second note's five blocks
    # rerun all four datasets (tau2-bench per domain and pooled)
    assert tuple(FILES)[-4:] == DELEGATION
    folders = {str(FILES[name].parent.relative_to(ROOT)) for name in DELEGATION}
    text = PAYS_SCRIPT.read_text(encoding="utf-8")
    block = text.split("DATASETS = (\n", 1)[1].split("\n)\n", 1)[0]
    paths = re.findall(r'^    \("[^"]+", "([^"]+)"\),$', block, re.M)
    assert len(paths) == 5, paths
    assert {p.rsplit("/", 1)[0] for p in paths} == folders
    assert sorted(per_item_blocks(PER_ITEM_NOTE.read_text(encoding="utf-8")), key=str) == \
        sorted(PER_ITEM_RUNS, key=str)


def _break_better(pays):
    old = "  cost_blind      all    472         216         0       0"
    assert pays.count(old) == 1
    return pays.replace(old, "  cost_blind      all    472         216         0       1")


def _break_better_effective(pays):
    """v1.325 (review iter-214 nit 1): a moved `cost_effective` `better` count no longer matches the files."""
    old = "  cost_effective  all    472         441         1       2"
    assert pays.count(old) == 1
    return pays.replace(old, "  cost_effective  all    472         441         1       3")


def _break_size_rule(per_item):
    old = "0.0609           0.9864             +0.0005"
    assert per_item.count(old) == 1
    return per_item.replace(old, "0.0609           0.9864             -0.0005")


def _drop_a_block(per_item):
    old = "$ python research/per_item_delegation.py --dataset tau2-bench-pooled "
    assert per_item.count(old) == 1
    return per_item.replace(old, "$ python research/other.py --dataset tau2-bench-pooled ")


# review iter-176 must-fix 1: a non-minimum LLMRouterBench row with a tab after `size rule` and a loss in mean
# success was skipped by the old prefilter, leaving the paragraph unchanged
TABBED = "  cost_effective  0.3  size rule    7150   259,159 / 3,991,675  0.0649           0.9975             +0.0005"


def _tab_a_row(per_item):
    assert per_item.count(TABBED) == 1
    return per_item.replace(TABBED, TABBED.replace("size rule    ", "size rule\t").replace("+0.0005", "-0.0005"))


def _drop_a_row(per_item):
    assert per_item.count(TABBED + "       9\n") == 1
    return per_item.replace(TABBED + "       9\n", "")


def _end_the_table(per_item):
    """The LLMRouterBench block, the first, loses both lines that end its table."""
    for flavor in ("cost_effective", "cost_blind"):
        old = f"  pick, switched share by point, {flavor}: "
        assert per_item.count(old) == 5
        per_item = per_item.replace(old, f"  pick switched share by point, {flavor}: ", 1)
    return per_item


def _move_the_cut(per_item):
    """v1.328: the response bank's bar 0.8 `size rule` row, the smallest `cost / decision` of the five blocks (from
    v1.332 the line from its flavor on, since the block's `all` `size rule` line repeats its columns)."""
    old = "  cost_effective  0.8  size rule    2108   853,995 / 6,462,124  0.1322           0.9431             +0.0013"
    assert per_item.count(old) == 1
    return per_item.replace(old, old.replace("0.9431", "0.9331"))


@pytest.mark.parametrize("change, which, match", [
    (_break_better, 0, "a `cost_blind` row is better than both"),
    (_break_better_effective, 0, r"'better': 3"),
    (_break_size_rule, 1, "a size rule row loses mean success"),
    (_drop_a_block, 1, r"\[None, 'autobench', 'response-bank', 'tau2-bench'\]"),
    (_tab_a_row, 1, r"not a table row: '  cost_effective  0\.3  size rule\\t"),
    (_drop_a_row, 1, "the strategies' bars differ"),
    (_end_the_table, 1, "no table between a header and its end"),
])
def test_a_note_that_breaks_a_claim_fails_the_pointer(change, which, match):
    texts = list(notes())
    delegation_pointer(*texts)
    texts[which] = change(texts[which])
    with pytest.raises(AssertionError, match=match):
        delegation_pointer(*texts)


def test_a_moved_figure_moves_the_pointer():
    pays, per_item = notes()
    before = delegation_pointer(pays, per_item)
    after = delegation_pointer(pays, _move_the_cut(per_item))
    assert before != after and "at most 6.7%" in after


# --- v1.316 (row E21d): the response-bank delegation bullet -----------------------------------

RB_DELEGATION = ROOT / "evidence" / "response-bank-delegation" / "results.json"


def rb_delegation():
    return json.loads(RB_DELEGATION.read_text(encoding="utf-8"))


def rbd_rows(results, strategy):
    return [r for r in results["summary"]
            if (r["bar"], r["flavor"], r["point"], r["strategy"]) == (0.8, "cost_effective", 0, strategy)]


def rbd_one_seed_inline(results):
    rbd_rows(results, "decision")[-1]["delegate_rate"] = 0.98


def rbd_one_parent_dearer(results):
    rbd_rows(results, "decision")[0]["cost_usd"] = 1000.0


def rbd_no_less_success(results):
    for r in rbd_rows(results, "decision"):
        r["success"] = 0.9


def test_the_response_bank_delegation_bullet_is_built_from_the_committed_file():
    assert response_bank_delegation_bullet(rb_delegation()) == (
        "- [Delegation on the LLM Routing Response Bank](#delegation-on-the-llm-routing-response-bank): at bar "
        "0.8 and 8,000 context tokens, with inline work in a parent call of its own, the `cost_effective` decision "
        "delegates on every seed for each of the 5 parents and costs less than always inline for each; its mean "
        "cost over the parents is 20.7429 USD against 101.6277 for always inline, for less held-out success")


@pytest.mark.parametrize("change, match", [
    (rbd_one_seed_inline, "response-bank delegation: not every seed delegates"),
    (rbd_one_parent_dearer, r"response-bank delegation: the decision costs no less than inline for \['deepseek/"),
    (rbd_no_less_success, "response-bank delegation: the decision has no less held-out success"),
])
def test_a_file_that_breaks_a_response_bank_delegation_claim_fails_its_bullet(change, match):
    results = rb_delegation()
    response_bank_delegation_bullet(results)
    change(results)
    with pytest.raises(AssertionError, match=match):
        response_bank_delegation_bullet(results)


def test_the_glance_list_ends_with_the_response_bank_delegation_bullet():
    assert anchor("Delegation on the LLM Routing Response Bank") == "#delegation-on-the-llm-routing-response-bank"
    lines = evidence_section().split("\n### ", 1)[0].split("\n")
    bullet = response_bank_delegation_bullet(rb_delegation())
    assert bullet in lines
    at = lines.index(bullet)
    assert lines[at - 1].startswith(link("Delegation on LLMRouterBench"))
    assert lines[at + 1] == ""


def test_the_delegation_pointer_names_the_four_delegation_bullets():
    intro = evidence_section().split("\n### ", 1)[0]
    assert ("Whether choosing per task between inline work and a sub-agent beats a fixed policy, on the datasets of "
            "the four delegation bullets above: ") in intro
    assert ", and " + PER_ITEM_LINK + " finds " in intro and "on the datasets of the first three" not in intro
