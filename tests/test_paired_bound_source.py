"""DESIGN 4.7 v1.606 (row GATE1e, review iter-449 should-fix 1): the paired lower bound's source.

`paired_promotion`'s `lower_bound` is the adjusted Wald interval of Bonett and Price (2012,
Journal of Educational and Behavioral Statistics 37(4), 479 to 488). DESIGN 4.7 cites the paper by
its DOI and a public implementation whose documentation attributes its adjustment to the paper,
`Wald_CI_BonettPrice_paired_2x2` of the CRAN
package contingencytables 3.1.1, at a pinned commit; README `## Running it in production` cites the
paper in its promotion paragraph. `wald_bonett_price` below ports that R function line by line, its
names kept, so a change to the bound that leaves the cited formula fails here. A docs slice: no
package module changes, so these tests passed when they were written.
"""

import math
import re
from pathlib import Path
from statistics import NormalDist

import pytest

from model_routing import paired_promotion

ROOT = Path(__file__).resolve().parents[1]
DOI = "https://doi.org/10.3102/1076998611411915"
SOURCE = ("https://github.com/cran/contingencytables/blob/c5b154fd4aec99f99c0e1548caa7a68d65be6709/"
          "R/Wald_CI_BonettPrice_paired_2x2.R")
CITATION = ("  - v1.606 (row GATE1e, review iter-449 should-fix 1): the source is Douglas G. Bonett and Robert M. "
            "Price, \"Adjusted Wald Confidence Interval for a Difference of Binomial Proportions Based on Paired "
            "Data\", Journal of Educational and Behavioral Statistics 37(4), 2012, pages 479 to 488 (" + DOI + "). "
            "The paper's text was not read here; the formula was compared term by term with a public "
            "implementation whose documentation attributes its pseudo-frequency adjustment to Bonett and Price "
            "(2012), `Wald_CI_BonettPrice_paired_2x2` of the CRAN package "
            "contingencytables 3.1.1 (" + SOURCE + "). ")
# v1.647 (row PROD1g): the README names the paper; DESIGN 4.7 names the interval
README_CLAUSE = ("on a paired lower bound above `-M` "
                 "([Bonett and Price, 2012](" + DOI + ")); `hold` otherwise;")


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def section_4_7():
    text = read("DESIGN.md")
    return text.split("\n### 4.7 Promotion checks", 1)[1].split("\n## ", 1)[0].split("\n### ", 1)[0]


def wald_bonett_price(n, alpha=0.05):
    """The R function at SOURCE, line by line: `n` a 2x2 table as [[n11, n12], [n21, n22]]."""
    N = sum(n[0]) + sum(n[1])
    estimate = (n[0][1] - n[1][0]) / N
    pi12tilde = (n[0][1] + 1) / (N + 2)
    pi21tilde = (n[1][0] + 1) / (N + 2)
    SE = math.sqrt((pi12tilde + pi21tilde - (pi12tilde - pi21tilde) ** 2) / (N + 2))
    z = NormalDist(0, 1).inv_cdf(1 - alpha / 2)
    L = pi12tilde - pi21tilde - z * SE
    U = pi12tilde - pi21tilde + z * SE
    L = max(-1, L)
    U = min(U, 1)
    return {"lower": L, "upper": U, "estimate": estimate}


def check(n, b, c, alpha):
    """`paired_promotion` on n pairs: b right only for the current route, c only for the challenger,
    the rest split between both right and both wrong."""
    both = (n - b - c + 1) // 2
    current = {f"i{k}": k < b + both for k in range(n)}
    challenger = {f"i{k}": (k < both) or (b + both <= k < b + both + c) for k in range(n)}
    return paired_promotion(current, challenger, margin=0.03, cheaper=True, alpha=alpha, min_pairs=1)


def table(n, b, c):
    """The 2x2 table with the challenger's outcome as its row and the current route's as its column,
    success first, as DESIGN 4.7 v1.606 maps it."""
    both = (n - b - c + 1) // 2
    return [[both, c], [b, n - b - c - both]]


# --- the citation lines -----------------------------------------------------------------------

def test_design_4_7_cites_the_paper_and_the_implementation_it_was_compared_with():
    text = section_4_7()
    assert text.count("\n" + CITATION) == 1
    assert "the adjusted Wald interval of Bonett and Price (2012), the Wald interval for paired outcomes with one " \
           "added to each discordant count and two to the pairs" in text
    assert re.search(r"/blob/[0-9a-f]{40}/R/", SOURCE)
    assert "\u2014" not in text and "\u2013" not in text


def test_design_4_7_maps_each_term_of_the_function():
    text = section_4_7()
    for clause in ("its `n[1, 2]` is `c` and its `n[2, 1]` is `b`, so its `pi12tilde` and `pi21tilde` are `ct` and "
                   "`bt`, its `SE` is the square root above, its `qnorm(1 - alpha / 2)` is `z`, its lower limit "
                   "`pi12tilde - pi21tilde - z * SE` is the one above, and its `max(-1, L)` is the clip at -1.0;",
                   "its `estimate`, `(n[1, 2] - n[2, 1]) / N` with `N` the pairs, is `difference`, which is not "
                   "adjusted, while the interval is centred on the adjusted difference `ct - bt` in both."):
        assert text.count(clause) == 1, clause


def test_the_readme_paragraph_cites_the_paper_once():
    text = read("README.md")
    production = text.split("\n## Running it in production\n", 1)[1].split("\n## ", 1)[0]
    assert production.count(README_CLAUSE) == 1
    assert text.count(DOI) == 1


def test_the_changelog_line_names_the_source():
    # the v1.606 line, not the file's last one, so a later version's line keeps this test (iter 456)
    [last] = [line for line in read("CHANGELOG.md").split("\n") if line.startswith("- v1.606 (")]
    assert last.startswith("- v1.606 (2026-11-23): docs and tests (4.7, 5.2, row GATE1e, review iter-449 "
                           "should-fix 1). ")
    assert "the adjusted Wald interval of Bonett and Price (2012)" in last
    assert "`Wald_CI_BonettPrice_paired_2x2` of the CRAN package contingencytables 3.1.1" in last


# --- the formula ------------------------------------------------------------------------------

GRID = [(n, b, c) for n in (1, 2, 3, 5, 8, 13, 30) for b in range(n + 1) for c in range(n + 1 - b)]


@pytest.mark.parametrize("alpha", [0.05, 0.01, 0.2])
def test_the_bound_is_the_ported_function_on_every_table_of_a_grid(alpha):
    for n, b, c in GRID:
        found = check(n, b, c, alpha)
        assert (found.pairs, found.current_only, found.challenger_only) == (n, b, c)
        ported = wald_bonett_price(table(n, b, c), alpha)
        assert math.isclose(found.lower_bound, ported["lower"], rel_tol=0.0, abs_tol=1e-15), (n, b, c, alpha)
        assert math.isclose(found.difference, ported["estimate"], rel_tol=0.0, abs_tol=1e-15), (n, b, c)


@pytest.mark.parametrize("n, b, c, lower", [(30, 0, 0, -0.0866), (30, 2, 2, -0.1500), (91, 0, 0, None),
                                            (442, 22, 22, None), (300, 12, 24, None)])
def test_the_numbers_the_readme_states_are_the_ported_function(n, b, c, lower):
    ported = wald_bonett_price(table(n, b, c))["lower"]
    assert math.isclose(check(n, b, c, 0.05).lower_bound, ported, rel_tol=0.0, abs_tol=1e-15)
    if lower is not None:
        assert f"{ported:.4f}" == f"{lower:.4f}"


def test_the_clip_is_the_functions():
    # one pair the current route alone got right: the unclipped limit is below -1 at a small alpha
    ported = wald_bonett_price(table(1, 1, 0), alpha=1e-6)
    assert ported["lower"] == -1
    assert check(1, 1, 0, 1e-6).lower_bound == -1.0
