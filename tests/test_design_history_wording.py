"""DESIGN 9, 12.7, 12.8, 12.10, 12.12, 12.17, 12.19 and 13.10 v1.463 (row DOC39a): history bullets read as history.

Reviews iter-305, iter-307, iter-309 and iter-318 found DESIGN bullets that a later version superseded
still worded in the present tense, or a cap a later version lowered given without saying it was the cap
then, and one 12.8 sentence that listed what a subsection over its cap sheds without pointing to the shed
order of the room bullet after it. Each test here pins one of those fixes on its whole line, found by the
line's opening text, so the old wording cannot come back beside the new.
"""
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
DESIGN = ROOT / "DESIGN.md"


def line(opening):
    """The one DESIGN.md line that starts with `opening`."""
    found = [text for text in DESIGN.read_text(encoding="utf-8").splitlines() if text.startswith(opening)]
    assert len(found) == 1, (opening, len(found))
    return found[0]


def test_the_unheld_doc19_trim_bullets_give_their_cap_as_the_cap_then():
    # Review iter-305 nit 5: 6,500 was the routing cap to v1.443 (12.8 v1.444 lowered it to 5,000).
    for row, size in (("v1.372, row DOC19k", "4,731"), ("v1.370, row DOC19j", "5,078"),
                      ("v1.368, row DOC19i", "5,691"), ("v1.365, row DOC19h", "6,194")):
        text = line(f"- README trim ({row}, to the 12.8 v1.334 size budget): ")
        assert text.count(f"({size} at 0b3e142, cap 6,500 then)") == 1
        assert "cap 6,500)" not in text


def test_the_12_8_over_cap_sentence_points_to_the_room_bullet_order():
    # Review iter-305 nit 4: the room bullet, the next line, gives the shed order (its Limits bullet first).
    lines = DESIGN.read_text(encoding="utf-8").splitlines()
    at = [i for i, text in enumerate(lines) if text.startswith("  - Everything else in a subsection (")]
    assert len(at) == 1
    text = lines[at[0]]
    assert text.endswith(". A subsection still over its cap after these sheds in the room bullet's order "
                         "below (v1.444), never a table")
    assert "keeps one Reading-it bullet or shortens its source lines" not in text
    room = lines[at[0] + 1]
    assert room.startswith("  - Room for one more subsection (v1.444, row DOC28a): ")
    assert "A part over its cap sheds, in this order and only until it fits: its Limits bullet" in room
    assert "It never sheds a table" in room


def test_the_12_19_v1_358_bullet_gives_the_shape_to_v1_445():
    # Review iter-307 nit 1: v1.446 (row DOC28c) trimmed the subsection again.
    text = line("- README trim (v1.358, row DOC19f, to the 12.8 v1.334 size budget): ")
    assert ("from v1.359 to v1.445 the README subsection `### LLMRouterBench` was 6,469 bytes by that budget's "
            "measure (8,093 at 0b3e142, cap 6,500) and held, in this order: ") in text
    assert text.endswith(", and the subsection's only bullets after its tables were the three it kept")
    for old in ("from v1.359 the README subsection", "is 6,469 bytes", "are the three it keeps"):
        assert old not in text
    after = line("- README trim (v1.446, row DOC28c, to the 12.8 v1.444 routing cap of 5,000 bytes): ")
    assert "holds what v1.359 held but" in after and "v1.359 holds" not in after


def test_the_13_10_v1_72_bullet_gives_the_trail_sentence_to_v1_447():
    # Review iter-309 nit 5: v1.448 (row DOC28e) replaced the opening of that sentence.
    text = line("- v1.72, committed by v1.73 with the code: ")
    assert text.count("To v1.447 its 13.11 TRAIL sentence opened \"Real sub-agent runs make more model calls") == 1
    assert "TRAIL sentence opens" not in text
    assert ("The 12.13 workflow needs no new line: its regenerate block holds the `--grid variants` command and "
            "its `Compare` line names `variants.json`, and the push that commits the file runs it.") in text


def test_the_9_v1_212_bullet_gives_its_readme_clause_as_v1_212_wrote_it():
    # Review iter-318 nit 3: the grok-4.7 note and the Limitations bullet were restated, last by 9 v1.455.
    text = line("- v1.212 `price_tiers` (format in 4.1) is optional")
    assert text.count("README, as v1.212 wrote it (restated since, last by v1.455 below): the pricing notes "
                      "under the capability table opened with ") == 1
    for new in ("the grok-4.7 note added that its page did not state the higher rates, so its row had no tier",
                "was replaced by one that said a tier is priced per call",
                "named the two costs that stayed at the base prices (grok-4.7 above 200K"):
        assert text.count(new) == 1, new
    for old in ("so its row has no tier", "names the two costs that stay at the base prices", "is replaced by one"):
        assert old not in text
    assert line("- v1.455 the `xai/grok-4.7` tier (row P4): ")
