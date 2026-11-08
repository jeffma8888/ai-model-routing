"""research/livecodebench-cost.md and research/livecodebench_cost.py (DESIGN 12.17 v1.96).

The note's `text` block is the script's output on the 67 pinned LiveCodeBench files, compared byte
for byte when they are already in the default cache (CI never downloads them). Every number of the
note's prose must be in that block, so the other tests need no download; the script's reduction,
report and error exit are checked on small stubs.
"""

import ast
import contextlib
import datetime
import importlib.util
import io
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "research" / "livecodebench_cost.py"
NOTE = ROOT / "research" / "livecodebench-cost.md"
INDEX = ROOT / "research" / "README.md"
CONVERT = ROOT / "evidence" / "livecodebench" / "convert.py"
COMMAND = "$ python research/livecodebench_cost.py"
SECTIONS = ["## Facts", "## Method", "## Results", "## Reading it", "## Vendor pages", "## Prices", "## Limits",
            "## Regenerate"]
# DESIGN 12.17 v1.98: the vendors read, in order, each with its own domain
VENDORS = [("openai", "openai.com"), ("anthropic", "anthropic.com"), ("google", "google.dev"),
           ("xai", "x.ai"), ("deepseek", "deepseek.com")]
TABLE_HEADER = "| vendor | page, read | what it says of reasoning and its billing | models among the 67 it names |"
# DESIGN 12.17 v1.100: one row per model of the Results block, in its order
PRICES_HEADER = "| model | pricing page, read | listed as | input | output |"
PRICE = re.compile(r"\$\d+\.\d{2}")
# DESIGN 12.17 v1.102: three more families' pricing pages, each on its maker's domain, and the runs
# named by an alias, which count as not listed
PRICE_FAMILIES = [("mistralai", "mistral.ai"), ("moonshotai", "moonshot.ai"), ("qwen", "alibabacloud.com"),
                  ("meta-llama", "meta.ai")]
# DESIGN 12.17 v1.105: the families whose own domain gives no per-token price, each read on its runs'
# model cards under its own account on huggingface.co, and the own sites their bullets cite
CARD_FAMILIES = [("agentica", "agentica-org"), ("lgai", "LGAI-EXAONE"), ("metastone", "MetaStoneTec"),
                 ("nvidia", "nvidia")]
OWN_SITES = {"agentica": "agentica-project.com", "lgai": "lgresearch.ai", "nvidia": "nvidia.com"}
NO_SITE = "the card links no site of the family's own"
NO_PRICE = "no first-party price"
ALIASES = ["mistralai/codestral-latest", "mistralai/mistral-large"]
# DESIGN 12.17 v1.107: the eight families `## Vendor pages` reads after the five vendors, in order, each
# with the domains of its own pages and its own account on huggingface.co
EIGHT = [("agentica", ("agentica-project.com",), "agentica-org"), ("lgai", ("lgresearch.ai",), "LGAI-EXAONE"),
         ("meta-llama", ("meta.ai", "llama.com"), "meta-llama"), ("metastone", (), "MetaStoneTec"),
         ("mistralai", ("mistral.ai",), None), ("moonshotai", ("moonshot.ai", "kimi.ai"), None),
         ("nvidia", ("nvidia.com",), "nvidia"), ("qwen", ("alibabacloud.com",), "Qwen")]
# DESIGN section numbers: the only numbers of the note's prose that are not in the script's output
ALLOWED = {"12.16", "12.17"}
NUMBER = re.compile(r"(?<![\w.])\d+(?:,\d{3})*(?:\.\d+)?%?")
URL = re.compile(r"https?://\S+")
DATE = re.compile(r"\d{4}-\d{2}-\d{2}")


def _load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="module")
def lcc():
    return _load("research_livecodebench_cost", SCRIPT)


def rec(qid, text, outputs):
    return {"question_id": qid, "question_content": text, "output_list": outputs}


def test_reduce_file_reads_the_first_sample_and_counts_an_empty_string(lcc):
    cells = lcc.reduce_file([rec("a", "xyz", ["abcd</think>", "z" * 50]), rec("b", "pq", "")], "F")
    assert cells == {"a": (3, 12, True, False), "b": (2, 0, False, True)}


@pytest.mark.parametrize("records", [
    [], None, {"a": 1}, ["x"],
    [rec("a", "x", ["y"]), rec("a", "x", ["y"])],
    [{"question_content": "x", "output_list": ["y"]}],
    [rec("", "x", ["y"])],
    [rec("a", 5, ["y"])],
    [rec("a", "x", [])],
    [rec("a", "x", [1])],
    [rec("a", "x", None)],
    [rec("a", "x", "y")],
])
def test_reduce_file_rejects_what_it_cannot_read(lcc, records):
    with pytest.raises(ValueError, match="^F: "):
        lcc.reduce_file(records, "F")


def stub(differ=False):
    """Four folders: a (Low)/(High) pair, and a bare folder with a (Thinking) run; q9 is in one only."""
    reduced = {
        "M (Low)": {"q1": (10, 100, False, False), "q2": (30, 300, False, False), "q3": (20, 200, False, False)},
        "M (High)": {"q1": (10, 110, False, False), "q2": (30, 95, False, False), "q3": (20, 0, False, True)},
        "N": {"q1": (11 if differ else 10, 40, False, False), "q2": (30, 41, False, False),
              "q3": (20, 42, False, False), "q9": (5, 1, False, False)},
        "N (Thinking)": {"q1": (10, 4000, True, False), "q2": (30, 4100, True, False), "q3": (20, 900, False, False)},
    }
    return reduced


def model_of(folder):
    return "v/" + folder.lower().replace(" (", "-").replace(")", "")


def test_report_on_a_stub(lcc):
    lines = lcc.report(stub(), model_of)
    assert lines[:5] == [
        "4 files, 3 question ids in every file",
        "problem text: median 20 characters, from 10 to 30; files whose text differs from M (High)'s on some id: 0",
        "first samples recorded as an empty string, counted as 0 characters: 1 (in 1 file)",
        "output tokens estimated at 4 characters per token",
        "",
    ]
    assert lines[5].split() == ["model", "median_output_chars", "think_marker", "est_output_tokens"]
    assert set(lines[6]) == {"-", " "}
    assert [line.split() for line in lines[7:11]] == [
        ["v/m-high", "95", "0.000", "24"],
        ["v/m-low", "200", "0.000", "50"],
        ["v/n", "41", "0.000", "10"],
        ["v/n-thinking", "4,000", "0.667", "1,000"],
    ]
    assert lines[11:] == [
        "",
        "models with the marker in at least half their first samples: 1 of 4",
        "median output characters per model: from 41 to 4,000 (97.6 times)",
        "",
        "runs of one model at more than one reasoning setting (median output characters):",
        "  M: High 95  Low 200 (longest over shortest 2.11)",
        "  N: none 41  Thinking 4,000 (longest over shortest 97.56)",
    ]


def test_report_says_files_for_more_than_one(lcc):
    reduced = stub()
    reduced["N"]["q2"] = (30, 0, False, True)
    assert lcc.report(reduced, model_of)[2] == (
        "first samples recorded as an empty string, counted as 0 characters: 2 (in 2 files)")


def test_report_counts_a_file_whose_problem_text_differs(lcc):
    assert lcc.report(stub(differ=True), model_of)[1].endswith("files whose text differs from M (High)'s on some id: 1")


def test_main_turns_a_fetch_error_into_one_line_and_exit_2(lcc, tmp_path, monkeypatch, capsys):
    fake = tmp_path / "convert.py"
    fake.write_text("FILES = {}\n\ndef fetch(cache_dir=None):\n    raise OSError('x.json: download failed: boom')\n",
                    encoding="utf-8")
    monkeypatch.setattr(lcc, "CONVERT", fake)
    assert lcc.main(["--cache", str(tmp_path)]) == 2
    out, err = capsys.readouterr()
    assert (out, err) == ("", "error: x.json: download failed: boom\n")


def test_script_is_standard_library_only():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom) and node.level == 0:
            names.add(node.module.split(".")[0])
    stdlib = getattr(sys, "stdlib_module_names", None) or {
        "__future__", "argparse", "importlib", "re", "statistics", "sys", "pathlib"}
    assert names and names <= set(stdlib) | {"__future__"}


def _note():
    return NOTE.read_text(encoding="utf-8")


def _results_block(text):
    section = text.split("\n## Results\n", 1)[1].split("\n## ", 1)[0]
    return section.split("```text\n", 1)[1].split("\n```", 1)[0]


def test_note_sections_in_order():
    headings = [line for line in _note().splitlines() if line.startswith("## ")]
    assert headings == SECTIONS


def test_note_results_block_starts_with_the_command():
    assert _results_block(_note()).splitlines()[0] == COMMAND


def test_note_prose_numbers_are_in_the_results_block():
    text = _note()
    block = _results_block(text)
    prose = text.replace(block, "").split("\n## Regenerate\n", 1)[0]
    # DESIGN 12.17 v1.100: in `## Prices` a number written $N.NN is a price from the page it cites
    head, prices = prose.split("\n## Prices\n", 1)
    prices, tail = prices.split("\n## ", 1)
    prose = head + "\n" + PRICE.sub(" ", prices) + "\n## " + tail
    prose = DATE.sub(" ", URL.sub(" ", prose))
    known = set(NUMBER.findall(block)) | ALLOWED
    missing = sorted({n for n in NUMBER.findall(prose)} - known)
    assert not missing


def _block_models(block):
    """The model column of the Results block's table: the first word of each row under its header."""
    lines = block.splitlines()
    start = next(i for i, line in enumerate(lines) if line.split()[:1] == ["model"]) + 2
    end = next(i for i in range(start, len(lines)) if not lines[i].strip())
    return [lines[i].split()[0] for i in range(start, end)]


def _vendor_rows():
    section = _note().split("\n## Vendor pages\n", 1)[1].split("\n## ", 1)[0]
    rows = [line for line in section.splitlines() if line.startswith("|")]
    assert rows[0] == TABLE_HEADER
    assert set(rows[1]) <= {"|", "-", " "}
    cells = [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in rows[2:]]
    assert all(len(row) == 4 for row in cells)
    return cells


def test_vendor_pages_rows_in_order():
    # DESIGN 12.17 v1.107: the five vendors, then the eight families
    assert [row[0] for row in _vendor_rows()] == [vendor for vendor, _ in VENDORS] + [f for f, _, _ in EIGHT]


def test_vendor_pages_each_cites_its_own_domain_and_a_date_read():
    domains = dict(VENDORS)
    for vendor, page, _, _ in _vendor_rows():
        if vendor not in domains:
            continue
        urls = [url.rstrip(",;.") for url in URL.findall(page)]
        assert urls, vendor
        for url in urls:
            host = url.split("://", 1)[1].split("/", 1)[0]
            assert url.startswith("https://") and (host == domains[vendor] or host.endswith("." + domains[vendor])), url
        read = re.search(r"\bread (\d{4}-\d{2}-\d{2})\b", page)
        assert read, vendor
        datetime.date.fromisoformat(read.group(1))


def test_vendor_pages_quote_each_page():
    for vendor, _, said, _ in _vendor_rows():
        assert re.search(r'"[^"]{12,}"', said), vendor


def test_vendor_pages_name_only_models_in_the_results_block():
    models = _block_models(_results_block(_note()))
    assert len(models) == 67
    named = []
    for vendor, _, _, cell in _vendor_rows():
        if cell == "none" or cell.startswith("none;"):
            continue
        ids = re.match(r"^((?:`[^`]+`(?:, )?)+)", cell)
        assert ids, vendor
        found = re.findall(r"`([^`]+)`", ids.group(1))
        assert all(m in models and m.startswith(vendor + "/") for m in found), found
        named += found
    assert len(named) == len(set(named))


def _section(name):
    return _note().split("\n" + name + "\n", 1)[1].split("\n## ", 1)[0]


def test_vendor_pages_rows_are_the_13_prefixes():
    # DESIGN 12.17 v1.107: every family has a row, and none is left unread
    models = _block_models(_results_block(_note()))
    prefixes = sorted({m.split("/", 1)[0] for m in models})
    named = [row[0] for row in _vendor_rows()]
    assert len(prefixes) == 13 and len(named) == 13
    assert sorted(named) == prefixes
    assert "The other eight families" not in _section("## Vendor pages")


def test_vendor_pages_eight_families_cite_their_own_pages_and_a_date_read():
    # DESIGN 12.17 v1.107: the family's own domains, or a model card under its own account
    rows = {row[0]: row for row in _vendor_rows()}
    for family, domains, account in EIGHT:
        page = rows[family][1]
        urls = [url.rstrip(",;.") for url in URL.findall(page)]
        assert urls, family
        for url in urls:
            host = url.split("://", 1)[1].split("/", 1)[0]
            card = account and re.fullmatch(r"https://huggingface\.co/" + re.escape(account) + r"/[^/\s]+", url)
            own = url.startswith("https://") and any(host == d or host.endswith("." + d) for d in domains)
            assert card or own, url
        read = re.search(r"\bread (\d{4}-\d{2}-\d{2})\b", page)
        assert read, family
        datetime.date.fromisoformat(read.group(1))


def test_vendor_pages_card_families_cite_the_cards_of_their_price_rows():
    # DESIGN 12.17 v1.107: the four card families of `## Prices` cite exactly those cards
    rows = {row[0]: row for row in _vendor_rows()}
    for family, _ in CARD_FAMILIES:
        cards = {url.rstrip(",;.") for url in URL.findall(rows[family][1]) if "huggingface.co/" in url}
        priced = {row[1].split(", read ", 1)[0] for row in _price_rows() if row[0].strip("`").startswith(family + "/")}
        assert cards == priced, family


def test_vendor_pages_set_each_card_run_beside_its_marker_share():
    # DESIGN 12.17 v1.107: one bullet names every run of the card families with its think_marker share;
    # v1.109 (review iter-106 should-fix 2): each ID followed by its own share in brackets
    block = _results_block(_note())
    share = {line.split()[0]: line.split()[2] for line in block.splitlines()
             if line.split()[:1] and "/" in line.split()[0] and len(line.split()) == 4}
    runs = [m for m in _block_models(block) if m.split("/", 1)[0] in dict(CARD_FAMILIES)]
    bullets = [line for line in _section("## Vendor pages").splitlines() if line.startswith("- ")]
    found = [b for b in bullets if all("`" + run + "`" in b for run in runs)]
    assert len(found) == 1
    assert all("`" + run + "` (" + share[run] + ")" in found[0] for run in runs)


def _price_rows():
    rows = [line for line in _section("## Prices").splitlines() if line.startswith("|")]
    assert rows[0] == PRICES_HEADER
    assert set(rows[1]) <= {"|", "-", " "}
    cells = [[cell.strip() for cell in row.strip().strip("|").split("|")] for row in rows[2:]]
    assert all(len(row) == 5 for row in cells)
    return cells


def test_prices_one_row_per_model_in_the_results_block_order():
    models = _block_models(_results_block(_note()))
    assert [row[0] for row in _price_rows()] == ["`" + m + "`" for m in models]


def _card_families():
    """The backticked prefixes in the parenthesis after the four card families' phrase of `## Prices`."""
    found = re.search(r"the four families whose own domain gives no per-token price \(([^)]*)\)", _section("## Prices"))
    assert found
    return re.findall(r"`([^`]+)`", found.group(1))


def test_prices_families_read_are_the_13_prefixes():
    # DESIGN 12.17 v1.105: every family is read, the four card families named in the intro in order
    models = _block_models(_results_block(_note()))
    prefixes = sorted({m.split("/", 1)[0] for m in models})
    cards = _card_families()
    assert cards == [family for family, _ in CARD_FAMILIES]
    assert sorted(cards + [family for family, _ in VENDORS + PRICE_FAMILIES]) == prefixes
    assert not [row for row in _price_rows() if "not read" in row[1] or row[2] == "not read"]


def test_prices_page_cells_cite_the_vendor_page_and_a_date_read():
    domains = dict(VENDORS + PRICE_FAMILIES)
    accounts = dict(CARD_FAMILIES)
    pages = {}
    cards = []
    for model, page, listed, price_in, price_out in _price_rows():
        vendor = model.strip("`").split("/", 1)[0]
        found = re.fullmatch(r"(https://\S+), read (\d{4}-\d{2}-\d{2})", page)
        assert found, model
        datetime.date.fromisoformat(found.group(2))
        if vendor in accounts:
            # DESIGN 12.17 v1.105: the run's own model card under the family's account
            assert re.fullmatch(r"https://huggingface\.co/" + re.escape(accounts[vendor]) + r"/[^/\s]+",
                                found.group(1)), model
            assert (listed, price_in, price_out) == (NO_PRICE, "-", "-"), model
            cards.append(found.group(1))
            continue
        host = found.group(1).split("://", 1)[1].split("/", 1)[0]
        assert host == domains[vendor] or host.endswith("." + domains[vendor]), model
        assert pages.setdefault(vendor, page) == page, model
    assert sorted(pages) == sorted(domains)
    assert len(cards) == len(set(cards)) == sum(m.split("/", 1)[0] in accounts
                                                for m in _block_models(_results_block(_note())))


def test_prices_listed_cells_carry_a_quoted_name_and_two_prices():
    for model, page, listed, price_in, price_out in _price_rows():
        if listed in ("not listed", NO_PRICE):
            assert (price_in, price_out) == ("-", "-"), model
        else:
            assert re.fullmatch(r'"[^"]+"', listed), model
            assert PRICE.fullmatch(price_in) and PRICE.fullmatch(price_out), model


def test_prices_alias_runs_are_not_listed():
    rows = {row[0].strip("`"): row for row in _price_rows()}
    for model in ALIASES:
        assert rows[model][2:] == ["not listed", "-", "-"], model
    assert all(rows[m][2] == "not listed" for m in rows if m.endswith("latest"))


def test_prices_intro_compares_word_order_as_written():
    # DESIGN 12.17 v1.102 (review iter-104 nit 1)
    assert "Word order is compared as written" in _section("## Prices").split("\n|", 1)[0]


def _price_bullets():
    return [line for line in _section("## Prices").splitlines() if line.startswith("- ")]


def test_prices_one_bullet_per_family_read():
    bullets = _price_bullets()
    for family, _ in VENDORS + PRICE_FAMILIES + CARD_FAMILIES:
        assert sum(b.startswith("- " + family + ": ") for b in bullets) == 1, family


def test_prices_card_family_bullets_cite_their_own_site_and_no_price():
    # DESIGN 12.17 v1.105
    for family, _ in CARD_FAMILIES:
        bullet = next(b for b in _price_bullets() if b.startswith("- " + family + ": "))
        assert not PRICE.search(bullet), family
        if family not in OWN_SITES:
            assert NO_SITE in bullet, family
            continue
        site = OWN_SITES[family]
        hosts = [u.split("://", 1)[1].split("/", 1)[0] for u in URL.findall(bullet)]
        assert any(h == site or h.endswith("." + site) for h in hosts), family
        assert re.search(r"read \d{4}-\d{2}-\d{2}", bullet), family


def test_prices_urls_are_on_the_families_domains_only():
    # DESIGN 12.17 v1.105: no host's price, so no URL off the families' own domains and huggingface.co
    allowed = [domain for _, domain in VENDORS + PRICE_FAMILIES] + list(OWN_SITES.values())
    allowed += ["llama.com", "huggingface.co"]
    for url in URL.findall(_section("## Prices")):
        host = url.split("://", 1)[1].split("/", 1)[0]
        assert url.startswith("https://") and any(host == d or host.endswith("." + d) for d in allowed), url


def test_note_regenerate_block():
    section = _note().split("\n## Regenerate\n", 1)[1]
    commands = section.split("```bash\n", 1)[1].split("\n```", 1)[0].splitlines()
    assert commands == [COMMAND[2:]]


def test_research_index_links_the_note():
    index = INDEX.read_text(encoding="utf-8")
    assert "| [livecodebench-cost.md](livecodebench-cost.md) |" in index


def _cached():
    convert = _load("livecodebench_convert_for_cost", CONVERT)
    root = convert.default_cache_dir()
    return all((root / name).exists() for name in convert.FILES)


@pytest.mark.skipif(not _cached(), reason="the 67 pinned LiveCodeBench files are not in the default cache")
def test_note_results_block_is_the_script_output(lcc):
    out = io.StringIO()
    with contextlib.redirect_stdout(out):
        assert lcc.main([]) == 0
    assert _results_block(_note()) == COMMAND + "\n" + out.getvalue().rstrip("\n")
