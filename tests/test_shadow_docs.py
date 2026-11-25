"""DESIGN 5.2 v1.619 (row CANARY1e): the README paragraphs on shadow calls, the note's GitHub line
and the defaults.

README `## Running it in production` gains, after the paragraphs on promotion checks and before
the sentence on threads, two paragraphs on shadow calls (DESIGN 4.2, 7, 8.1, 8.3 and 10, v1.607 to
v1.618): what `shadow_rate` and `shadow_route` do, what a shadow costs and how `report --shadow`
keeps it apart, the wait a `shadow_runner` spares, and the pairs `model-routing pairs` writes and
what reads them, with GitHub's canary sentence quoted from the note. The note's GitHub
`In this library` line names the shadow share as shipped. With no shadow field nothing CANARY1
added runs: no evidence or research script or committed JSON file names a shadow field, the
twelve README transcripts keep their v1.606 bytes, and a demo run writes no shadow key. A docs
slice: no package module changes, so these tests passed when they were written.
"""

import hashlib
import json
import re
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from model_routing import (
    Completion, Executor, FakeProvider, Model, Monitor, Registry, Router, Stats, Task, load_records,
    pair_results, report, shadow_pairs,
)
from model_routing.cli import main
from model_routing.demo import run_demo

ROOT = Path(__file__).resolve().parents[1]
BLOCK = re.compile(r"```text\n(\$ model-routing [^\n]*\n.*?)```", re.S)  # gates.py's and tests/test_readme.py's
FIRST = "A share of routed calls can also go to a reference route, so a quality loss nobody labelled shows up in pairs to label. "
SECOND = "Every record of a shadowed call carries `pair_id`, the routed call's ID, `shadow`, and `checked`, "
PROMOTE_END = "and `promote` changed no route or file."
THREADS = "One `Executor`, with its `Monitor` and `BudgetLedger`, can serve every request thread of a process: "
GITHUB = "### Test a model before the switch, and re-run the tests on the models in production every day"
ANCHOR = "test-a-model-before-the-switch-and-re-run-the-tests-on-the-models-in-production-every-day"
# The README's twelve transcripts at 713c6b6 (v1.606, the last version before row CANARY1a), in order:
# the first words after `$ model-routing `, UTF-8 bytes and sha256 of each block as BLOCK finds it
# (`git show 713c6b6:README.md`).
V1_606 = [
    ("demo --out ./demo-run", 831, "f69bc5dfcde9ceaf73ed8bb3860890dbb19d048c3ac4a335d335cbd0ef473386"),
    ("report --log demo-run/calls.jsonl --by flavor", 558,
     "334cb0a03a936478a0760f4c53652a5110573489bdffe051a01eb54a12c709df"),
    ("report --log demo-run/calls.jsonl --by tag:delegated", 561,
     "80bd11068d7f3540f4cd7e143e58064fa7769d6524f9f61259538a79bd24d317"),
    ("evaluate --outcomes demo-run/outcomes.jsonl", 1674,
     "b8fccf3c0bfd789b81298be36d738ce4c13663064e6ffb5bcc611998d9b3703a"),
    ("delegate demo_faithfulness_judge --parent demo/atlas-max ", 497,
     "af84b703b60f980a9c07a199f9bd6254f5506bb2aa8fd0fa42bbc92d6b5ab752"),
    ("delegate demo_faithfulness_judge --parent demo/atlas-mid ", 507,
     "dd5266e190e138fb43026b2fbce8c8a5d38ccedbd9d4e9e367f791c0f2bd9b21"),
    ("delegate demo_faithfulness_judge --parent demo/atlas-mid ", 526,
     "73cab9fca1ba1095fe49dfc3fa108034a88428e08232f698c3bd0a4aca0fd1a3"),
    ("delegate demo_faithfulness_judge --parent demo/atlas-mid ", 517,
     "dc4089f103cbf4cf7dd9dda5b6155e17b5b012708fc2151eec8efea995db3d07"),
    ("plan --success 0.9 --bar 0.8", 151, "eb9d65cfbe81762ef35843efb7586bf654a434ded8a0ead650d2d3b978ee8c40"),
    ("plan --success 1.0 --bar 0.8", 151, "430d2477b67822e29f3fe46c5cece7b4cfce6d661e05b41d757f5cba89116e39"),
    ("calibrate --results demo-run/outcomes.jsonl --stats demo-run/paired-stats.json ", 715,
     "c2e9b34940b3bb906c710aa9ef39a86bddfe256af2c3bed81b1c28513f2752f6"),
    ("promote --task demo_faithfulness_judge --challenger demo/atlas-max ", 947,
     "ca9e4a3666d42ace672fecd6b806b0bc2d5007abb6e49ca2803dc63e0f11cc95"),
]
# What CANARY1 added (v1.607 to v1.618): the task fields, the executor's keywords, the record keys
# and the functions that read them.
SHADOW_NAMES = ("shadow_rate", "shadow_route", "shadow_runner", "shadow_pairs", "pair_results", "pair_id",
                '"shadow"', '"checked"', "--shadow", "model-routing pairs")
PAIR_KEYS = ("pair_id", "shadow", "checked")

CHEAP, MID, BEST = "fiction/cheap", "fiction/mid", "fiction/best"
MESSAGES = [{"role": "user", "content": "judge"}]


def read(name):
    return (ROOT / name).read_text(encoding="utf-8")


def production():
    """README `## Running it in production`, its heading line through the line before the next `## `."""
    return read("README.md").split("\n## Running it in production\n", 1)[1].split("\n## ", 1)[0]


def part(opening):
    """The paragraph of the production section that starts with ``opening``, up to its blank line."""
    body = production()
    assert body.count("\n\n" + opening) == 1, opening
    return opening + body.split("\n\n" + opening, 1)[1].split("\n\n", 1)[0]


def router(**fields):
    """cost_effective routes cheap first; the default shadow route is best, whose bound is highest."""
    task = Task("judge", bar=0.7, min_samples=10, **fields)
    stats = Stats()
    for model_id, (successes, trials) in ((CHEAP, (90, 100)), (MID, (95, 100)), (BEST, (100, 100))):
        stats.add(task.name, model_id, successes, trials)
    registry = Registry([Model(CHEAP, "small", 1.0, 2.0, 8000), Model(MID, "medium", 3.0, 6.0, 8000),
                         Model(BEST, "large", 10.0, 20.0, 8000)])
    return Router(registry, {task.name: task}, stats)


def provider():
    return FakeProvider({model_id: (lambda text: lambda messages: Completion(text, 1000, 200))(model_id)
                         for model_id in (CHEAP, MID, BEST)})


def shadowed_log(path, validate):
    """Three calls shadowed at rate 1 through a pool's submit, the pool shut down before the log is read."""
    pool = ThreadPoolExecutor(max_workers=1)
    executor = Executor(router(shadow_rate=1.0), provider(), monitor=Monitor(path), shadow_runner=pool.submit)
    texts = [executor.call("judge", MESSAGES, validate=validate).text for _ in range(3)]
    pool.shutdown(wait=True)
    return texts, load_records(path)


# --- the paragraphs ---------------------------------------------------------------------------

def test_the_two_paragraphs_follow_the_promotion_check_and_precede_the_sentence_on_threads():
    paragraphs = production().strip().split("\n\n")
    first = next(k for k, p in enumerate(paragraphs) if p.startswith(FIRST))
    assert paragraphs[first - 1].endswith(PROMOTE_END)
    assert paragraphs[first + 1].startswith(SECOND)
    assert paragraphs[first + 2].startswith(THREADS)
    # v1.625 (row POL1d): the paragraph on a tenant's policy follows it (tests/test_policy_cli.py), and from
    # v1.630 (row LAT1c) the one on the latency bar ends the section (tests/test_latency_docs.py)
    assert paragraphs[first + 3].startswith("A tenant's rules hold whatever a route costs. ")
    assert read("README.md").count(FIRST) == 1 and read("README.md").count(SECOND) == 1


def test_the_first_paragraph_says_what_a_shadow_is_costs_and_waits_for():
    text = part(FIRST)
    for clause in (
            "A task's `shadow_rate`, from 0, the default, to 1, is the share of its calls the executor shadows",
            # v1.648 (row PROD1gb): the hard rules, the primary, a fallback's or a hand-up's answer and what a
            # runner spares the call are DESIGN 7's (tests/test_readme_trim.py)
            "by default the registry model that clears the bar with the highest lower bound; a named one need not "
            "clear the bar, so a challenger can be shadowed before it is admitted. Once",
            "the caller gets only the routed result: a shadow's provider error, invalid output or budget refusal "
            "never fails the call.",
            "The draw comes from `Executor(..., random=...)`, so a test can fix it.",
            # iter 459 sub-bullet: DESIGN 7 v1.609
            "A call answered by the shadow route's own model sends no shadow, while a procedure whose `model` is the "
            "shadow route is still shadowed.",
            "Each shadow is one more provider call at the shadow route's price, so at a `shadow_rate` of 0.05 about "
            "one call in twenty is paid twice;",
            "so a budget with `tags={\"shadow\": \"true\"}` caps the shadows' spend on its own.",
            # iter 462 sub-bullet: DESIGN 10 v1.611
            "The default `report` counts a shadow as a call of its own, while `report --shadow` keeps shadows out of "
            "the routed columns and adds `shadow_calls`, `shadow_failed_calls` and `shadow_cost_usd`.",
            # SCOUT iter 460 and iter 468 sub-bullets: DESIGN 7 v1.617
            "With no `shadow_runner` the shadow runs before `.call` returns, so the caller waits for it too.",
            "`Executor(..., shadow_runner=pool.submit)`, with `pool` a `ThreadPoolExecutor`, runs it on another "
            "thread; a job not yet run has no shadow record and gives no pair, so call "
            "`pool.shutdown(wait=True)` before you read the log or end the process",
            "(`DESIGN.md` 4.2, 7, 8.1 and 8.3)."):
        assert text.count(clause) == 1, clause
    assert "\u2014" not in text and "\u2013" not in text


def test_the_second_paragraph_says_what_writes_labels_and_reads_the_pairs():
    text = part(SECOND)
    for clause in (
            # iter 469 sub-bullet: DESIGN 8.1 and 10 v1.618
            "`checked`, whether `.call` was given an acceptance check.",
            "with `--checked`, which refuses a log whose shadowed calls ran none, so label such a log by an audits "
            "file with `--audits PATH`; with neither a pair waits for an audit of both call IDs.",
            "An error side is never labelled, and nothing reads a pair into the stats, so an unlabelled pair never "
            "changes a route.",
            "`--results RESULTS` also writes the labelled pairs as results rows, each with its side's `cost_usd` "
            "from the log and the routed call's ID as its item",
            "so `calibrate --outcomes` and then `promote` with the shadow route as `--challenger` compare the two "
            "routes on the same production calls, naming the rows file's hash with `--dataset-sha256` once the "
            "outcomes file holds the two routes' outcomes from another file too",  # review iter-471 nit 1
            "and with `--routes ROUTED SHADOW` `evaluate --outcomes` reads them as a complete outcome matrix; "
            "a cascade's rows carry `escalated` and its whole spend, which `calibrate` reads, while `evaluate` "
            "refuses them, as it needs rows of the cascade's two models too (`DESIGN.md` 8.3 and 10).",  # v1.621
            f"([production lessons](research/production-lessons.md#{ANCHOR}))",
            "there the staff get the new model's answers, while a shadow's answer reaches no one, and the post gives "
            "no count of what its checks caught."):
        assert text.count(clause) == 1, clause
    assert "\u2014" not in text and "\u2013" not in text


def test_the_readme_shows_the_pairs_synopsis_once_in_prose_and_in_no_transcript():
    # iter 463 sub-bullet: README shows the synopsis (DESIGN 10 v1.612), so tests/test_pairs_cli.py's pin moves
    readme = read("README.md")
    synopsis = "`model-routing pairs --log PATH --out FILE`"
    assert readme.count("model-routing pairs") == 1 and part(SECOND).count(synopsis) == 1
    assert not [block for block in BLOCK.findall(readme) if "model-routing pairs" in block]


def test_every_flag_the_paragraph_names_is_a_flag_of_pairs(capsys):
    with pytest.raises(SystemExit) as done:
        main(["pairs", "--help"])
    assert done.value.code == 0
    usage = " ".join(capsys.readouterr().out.split())
    for flag in ("--log PATH", "--out FILE", "[--checked]", "[--audits PATH]", "[--results RESULTS]",
                 "[--routes ROUTED SHADOW]"):
        assert flag in usage, flag
        assert flag.strip("[]") in part(SECOND), flag


def test_the_quote_is_the_notes_word_for_word_under_the_github_lesson():
    quote = re.search(r'GitHub tries a new model on its own staff before a switch: "(.+?)" \(\[production lessons\]',
                      part(SECOND)).group(1)
    note = read("research/production-lessons.md")
    lesson = note[note.index(GITHUB):].split("\n### ", 1)[0]
    assert lesson.count('"' + quote + '"') == 1
    assert quote.startswith("We also conduct live internal evaluations, similar to canary testing")
    slug = re.sub(r"[^\w\- ]", "", GITHUB[4:].strip().lower()).replace(" ", "-")
    assert slug == ANCHOR


# --- the paragraphs run as they say -----------------------------------------------------------

def test_a_pool_runner_s_shadows_are_logged_tagged_and_paired_once_the_pool_has_shut_down(tmp_path):
    log = tmp_path / "calls.jsonl"
    texts, records = shadowed_log(log, validate=lambda text: True)
    assert texts == [CHEAP] * 3  # the caller gets only the routed result
    shadows = [r for r in records if r["shadow"] is True]
    assert len(records) == 6 and len(shadows) == 3
    assert {r["model"] for r in shadows} == {BEST} and all(r["tags"] == {"shadow": "true"} for r in shadows)
    assert all(r["checked"] is True for r in records)
    rows = {row["group"]: row for row in report(records, shadow=True)}
    assert (rows[CHEAP]["calls"], rows[CHEAP]["shadow_calls"]) == (3, 0)
    assert (rows[BEST]["calls"], rows[BEST]["shadow_calls"], rows[BEST]["shadow_failed_calls"]) == (0, 3, 0)
    assert rows[BEST]["shadow_cost_usd"] == pytest.approx(3 * shadows[0]["cost_usd"])
    assert sum(row["calls"] for row in report(records)) == 6  # the default report counts each shadow
    pairs = shadow_pairs(records, checked=True)
    assert len(pairs) == 3 and all(p["routed_correct"] is True and p["shadow_correct"] is True for p in pairs)
    results = pair_results(pairs, records=records, routes=(CHEAP, BEST))
    assert [row["model"] for row in results] == [CHEAP, BEST] * 3
    assert [row["item"] for row in results[::2]] == [p["pair_id"] for p in pairs]
    assert all("cost_usd" in row for row in results)
    out, rows_file = tmp_path / "pairs.jsonl", tmp_path / "rows.jsonl"
    assert main(["pairs", "--log", str(log), "--out", str(out), "--checked", "--results", str(rows_file),
                 "--routes", CHEAP, BEST]) == 0
    assert [json.loads(line) for line in rows_file.read_text(encoding="utf-8").splitlines()] == results


def test_checked_refuses_a_log_whose_shadowed_calls_ran_no_check_and_an_unlabelled_pair_adds_no_row(tmp_path, capsys):
    log = tmp_path / "calls.jsonl"
    _, records = shadowed_log(log, validate=None)
    assert all(r["checked"] is False for r in records)
    with pytest.raises(ValueError):
        shadow_pairs(records, checked=True)
    out = tmp_path / "pairs.jsonl"
    assert main(["pairs", "--log", str(log), "--out", str(out), "--checked"]) == 2 and not out.exists()
    capsys.readouterr()
    unlabelled = shadow_pairs(records)
    assert len(unlabelled) == 3 and pair_results(unlabelled) == []
    audits = {p[key]: True for p in unlabelled for key in ("pair_id", "shadow_call_id")}
    assert len(pair_results(shadow_pairs(records, audits=audits))) == 6


# --- the note -------------------------------------------------------------------------------

def test_the_notes_github_line_names_the_shadow_share_as_shipped():
    note = read("research/production-lessons.md")
    [line] = [x for x in note.splitlines() if x.startswith("- In this library: the caller calls a task, not a model, ")]
    assert ("A set share of routed calls can also go to a reference route: from v1.607 a task's `shadow_rate` sends "
            "that share of its calls to its `shadow_route` as well, the caller getting only the routed answer, and "
            "from v1.615 `model-routing pairs --results` turns a monitor log's labeled pairs into results rows that "
            "`calibrate --outcomes` and `promote` read, so a quality loss nobody labeled shows up in pairs to "
            "label. ") in line
    # v1.635 (row M1e): the drift check, the change this line still planned at v1.619, shipped at v1.634
    # (tests/test_drift_docs.py), so the line names no change still planned
    assert " The change still planned: " not in line and " The changes: " not in line
    assert (line.index("from v1.603 `model-routing promote`") < line.index("from v1.607 a task's `shadow_rate`")
            < line.index("From v1.634 the drift check is `model-routing drift`: "))


# --- no shadow field, no change -------------------------------------------------------------

def test_no_evidence_or_research_script_or_committed_json_names_a_shadow_field():
    paths = [*sorted((ROOT / "evidence").rglob("*.py")), *sorted((ROOT / "research").rglob("*.py")),
             *sorted((ROOT / "evidence").rglob("*.json")), *sorted((ROOT / "model_routing" / "data").glob("*.json"))]
    assert len([p for p in paths if p.suffix == ".py"]) > 2 and len([p for p in paths if p.suffix == ".json"]) > 30
    for path in paths:
        source = path.read_text(encoding="utf-8")
        for name in SHADOW_NAMES:
            assert name not in source, (path, name)
    # CI's evidence job regenerates its files and fails on any byte that differs
    assert read(".github/workflows/evidence.yml").count("run: git diff --exit-code -- evidence/") == 1


def test_the_twelve_transcripts_keep_their_v1_606_bytes_and_name_nothing_canary1_added():
    blocks = BLOCK.findall(read("README.md"))
    assert len(blocks) == len(V1_606) == 12
    for block, (words, size, digest) in zip(blocks, V1_606):
        assert block.startswith("$ model-routing " + words), words
        assert len(block.encode("utf-8")) == size, words
        assert hashlib.sha256(block.encode("utf-8")).hexdigest() == digest, words
        for name in SHADOW_NAMES:
            assert name not in block, (words, name)


def test_a_demo_run_writes_no_shadow_key(tmp_path):
    run_demo(tmp_path)
    [task] = json.loads((tmp_path / "tasks.json").read_text(encoding="utf-8"))["tasks"]
    assert "shadow_rate" not in task and "shadow_route" not in task
    records = [json.loads(line) for line in (tmp_path / "calls.jsonl").read_text(encoding="utf-8").splitlines()]
    assert len(records) > 400
    for record in records:
        assert not [key for key in PAIR_KEYS if key in record], record["call_id"]
        assert "shadow" not in record["tags"]


# --- DESIGN and the changelog -----------------------------------------------------------------

def test_design_states_the_paragraphs_and_the_changelog_the_version():
    design = read("DESIGN.md")
    five2 = design[design.index("### 5.2 "):design.index("### 5.3 ")]
    [mine] = [line for line in five2.splitlines() if line.startswith("- v1.619 README and note (row CANARY1e): ")]
    for kept in ("after the paragraphs on promotion checks and before the sentence on threads, two paragraphs on shadow calls",
                 "(7 v1.617, review iter-468 should-fix 1)", "`checked` included (8.1 v1.618)",
                 "the synopsis `model-routing pairs --log PATH --out FILE`", "(10 v1.612 and v1.615)",
                 "since `pair_outcomes` refuses two hashes (4.7 v1.603, review iter-471 nit 1)",
                 "keeps the drift check as the change still planned", "README's package line says `about 7,000 lines`",
                 "Defaults (tests/test_shadow_docs.py)", "the README's twelve transcripts keep their v1.606 bytes",
                 "No package module or evidence file changes"):
        assert mine.count(kept) == 1, kept
    seven = design[design.index("## 7. "):design.index("## 8. ")]
    assert seven.count("the README and the note's line (row CANARY1e, which v1.619 adds, 5.2).\n") == 1
    assert seven.count("the README paragraph (row CANARY1e, which v1.619 adds, 5.2).\n") == 1
    assert "(row CANARY1e)." not in seven
    eight3 = design[design.index("### 8.3 "):design.index("## 9. ")]
    assert "and the README and the note's line are row CANARY1e's (5.2 v1.619). " in eight3
    ten = design[design.index("## 10. "):design.index("## 11. ")]
    assert "README shows no synopsis of `pairs` until v1.619 (5.2, row CANARY1e). " in ten
    [line] = [x for x in read("CHANGELOG.md").splitlines() if x.startswith("- v1.619 (")]
    assert line.startswith("- v1.619 (2026-11-24): docs and tests (5.2, 7, 8.3, 10, row CANARY1e). ")
    assert len(line.encode("utf-8")) <= 600
