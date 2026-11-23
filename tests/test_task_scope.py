"""DESIGN 4.1, 5.1, 5.2 and 9 v1.586 (row SCOPE1): keep a specialized model to the tasks it was measured on.

`Model.scope_tasks` holds task names or glob patterns. On a task none of them matches, the model's
candidate is `out_of_scope` (rule 5a), not eligible, so a model built for some tasks gets no call on
the others, cold start included; on a task in its scope it is admitted on its own counts, and on a
sliced call on that slice's counts alone. The contract tests were written under strict xfail and the
implementing commit removed the marks; the unmarked guards pin what v1.586 keeps and passed before
and after it.
"""

import dataclasses
import json
import os
from pathlib import Path

import pytest

import model_routing
from model_routing import (BELOW_BAR, CONTEXT_TOO_SMALL, DATA_DIR, EXCLUDED_FAMILY, EXCLUDED_MODEL, GENERATOR,
                           GENERATOR_FAMILY, INSUFFICIENT_SAMPLES, PASSES,
                           Cascade, Model, NoModelClearsBar, Priors, Procedure, ProcedureResult, Registry, Router,
                           Stats, Task, Variant)

ROOT = Path(__file__).resolve().parents[1]
PACKAGE = ROOT / "model_routing"
CELL, SUMMARY = "review_table_cell", "contract_summary"
FT, LIST = "acme/rt", "v/strong"


def out_of_scope():
    return model_routing.OUT_OF_SCOPE


def fine_tune(scope=(CELL,), **extra):
    return Model(FT, "acme", 0.1, 0.2, 100_000, scope_tasks=scope, **extra)


def strong():
    return Model(LIST, "v", 2.0, 10.0, 100_000)


def task(name, **extra):
    return Task(name=name, bar=0.8, min_samples=30, expected_input_tokens=1000, expected_output_tokens=200,
                **extra)


def router(models, counts=None, tasks=(CELL, SUMMARY), priors=None, **task_extra):
    stats = Stats()
    for key, model_id, successes, trials in (counts if counts is not None else
                                             [(t, m.id, 95, 100) for t in tasks for m in models]):
        stats.add(key, model_id, successes, trials)
    return Router(Registry(models), {name: task(name, **task_extra) for name in tasks}, stats, priors)


def reasons(decision_or_error):
    return {c.model_id: c.reason for c in decision_or_error.candidates}


def test_out_of_scope_is_exported_after_procedure_unknown_model():
    assert model_routing.OUT_OF_SCOPE == "out_of_scope"
    names = model_routing.__all__
    assert names.index("OUT_OF_SCOPE") == names.index("PROCEDURE_UNKNOWN_MODEL") + 1


def test_scope_tasks_is_the_last_field_and_defaults_to_every_task():
    # the last field until v1.587 adds the two cache prices after it (DESIGN 4.1)
    assert [f.name for f in dataclasses.fields(Model)][-6:] == ["pricing_basis", "deployment", "base_model",
                                                                "scope_tasks", "price_cached_in", "price_cache_write"]
    plain = strong()
    assert plain.scope_tasks == ()
    assert list(dataclasses.asdict(plain))[-3] == "scope_tasks"
    assert dataclasses.asdict(fine_tune(("a", "b*")))["scope_tasks"] == ("a", "b*")
    assert fine_tune(("a", "a")).scope_tasks == ("a", "a")  # a repeated pattern is kept


@pytest.mark.parametrize("value", [["review_table_cell"], "review_table_cell", ("",), (1,), (None,),
                                   ("a", b"b"), None, {"a"}])
def test_a_scope_is_a_tuple_of_non_empty_strings(value):
    with pytest.raises(ValueError, match="scope_tasks"):
        fine_tune(value)


def test_a_scoped_fine_tune_is_primary_on_its_task_and_out_of_scope_elsewhere():
    models = [fine_tune(), strong()]
    on_cell = router(models).select(CELL, "cost_effective")
    assert reasons(on_cell) == {FT: PASSES, LIST: PASSES}
    assert (on_cell.primary, on_cell.fallbacks) == (FT, (LIST,))
    costs = {c.model_id: c.list_cost for c in on_cell.candidates}
    assert costs == {FT: pytest.approx(0.00014), LIST: pytest.approx(0.004)}
    assert {c.model_id: round(c.quality_lb, 6) for c in on_cell.candidates} == {FT: 0.88825, LIST: 0.88825}
    on_summary = router(models).select(SUMMARY, "cost_effective")
    assert reasons(on_summary) == {FT: out_of_scope(), LIST: PASSES}
    assert (on_summary.primary, on_summary.fallbacks) == (LIST, ())
    ruled_out = [c for c in on_summary.candidates if c.model_id == FT][0]
    assert (ruled_out.eligible, ruled_out.passes, ruled_out.successes, ruled_out.trials) == (False, False, 95, 100)
    assert on_summary.to_dict()["candidates"][0]["reason"] == "out_of_scope"
    assert router(models).select(SUMMARY, "cost_blind").primary == LIST


@pytest.mark.parametrize("pattern, cell, summary", [
    ("review_*", PASSES, "out"), ("*_cell", PASSES, "out"), ("contract_summar?", "out", PASSES),
    ("[cr]*", PASSES, PASSES), ("Review_*", "out", "out"), ("review", "out", "out"),
])
def test_patterns_are_case_sensitive_globs_over_the_task_name(pattern, cell, summary, monkeypatch):
    # review iter-434 should-fix 2: fold case as Windows does, so `fnmatch` in place of
    # `fnmatchcase` would match `Review_*` here
    monkeypatch.setattr(os.path, "normcase", lambda text: text.lower())
    picked = {name: reasons(router([fine_tune((pattern,)), strong()]).select(name))[FT]
              for name in (CELL, SUMMARY)}
    want = {CELL: cell, SUMMARY: summary}
    assert picked == {name: out_of_scope() if value == "out" else value for name, value in want.items()}


def test_any_pattern_of_several_admits_the_task():
    picked = router([fine_tune(("nothing", CELL)), strong()]).select(CELL)
    assert reasons(picked)[FT] == PASSES


def test_no_cold_start_call_out_of_scope():
    # unmeasured everywhere: the prior would pick the fine-tune first, but only on its own task
    priors = Priors({"legal": {"scores": {FT: 0.99, LIST: 0.5}}})
    models = [fine_tune(), strong()]
    cold = router(models, counts=[], priors=priors, on_no_model="best_available", prior_category="legal")
    on_cell = cold.select(CELL)
    assert (on_cell.basis, on_cell.primary, on_cell.fallbacks) == ("prior", FT, (LIST,))
    on_summary = cold.select(SUMMARY)
    assert reasons(on_summary) == {FT: out_of_scope(), LIST: INSUFFICIENT_SAMPLES}
    assert (on_summary.basis, on_summary.primary, on_summary.fallbacks) == ("prior", LIST, ())
    # a few trials of its own: the best_available measured list never holds it out of scope
    few = router(models, counts=[(SUMMARY, FT, 10, 10), (SUMMARY, LIST, 5, 10)],
                 on_no_model="best_available")
    picked = few.select(SUMMARY)
    assert (picked.basis, picked.below_bar, picked.primary, picked.fallbacks) == ("measured", True, LIST, ())
    # refuse: nothing else measured, so nothing clears the bar, and the candidates say why
    with pytest.raises(NoModelClearsBar) as caught:
        router(models, counts=[(SUMMARY, FT, 100, 100)]).select(SUMMARY)
    assert reasons(caught.value) == {FT: out_of_scope(), LIST: INSUFFICIENT_SAMPLES}


def test_no_below_bar_fallback_place_out_of_scope():
    counts = [(SUMMARY, LIST, 95, 100), (SUMMARY, FT, 70, 100), (SUMMARY, "w/mid", 60, 100)]
    models = [fine_tune(), strong(), Model("w/mid", "w", 1.0, 2.0, 100_000)]
    picked = router(models, counts=counts, fallback_below_bar=True).select(SUMMARY)
    assert reasons(picked) == {FT: out_of_scope(), LIST: PASSES, "w/mid": BELOW_BAR}
    assert (picked.primary, picked.fallbacks, picked.below_bar_fallbacks) == (LIST, ("w/mid",), ("w/mid",))


def test_the_rules_before_5a_keep_their_reasons():
    models = [fine_tune(), strong()]
    excluded = router(models).select(SUMMARY, exclude_models=[FT])
    assert reasons(excluded)[FT] == EXCLUDED_MODEL
    # review iter-434 should-fix 3: rules 2, 3 and 4 come before 5a too
    assert reasons(router(models, exclude_families=("acme",)).select(SUMMARY))[FT] == EXCLUDED_FAMILY
    judged = router(models + [Model("acme/gen", "acme", 1.0, 1.0, 100_000)], independent_of_generator=True)
    assert reasons(judged.select(SUMMARY, generator_model=FT))[FT] == GENERATOR
    assert reasons(judged.select(SUMMARY, generator_model="acme/gen"))[FT] == GENERATOR_FAMILY
    narrow = Model(FT, "acme", 0.1, 0.2, 1000, scope_tasks=(CELL,))
    assert reasons(router([narrow, strong()]).select(SUMMARY))[FT] == CONTEXT_TOO_SMALL
    assert reasons(router([narrow, strong()]).select(CELL))[FT] == CONTEXT_TOO_SMALL


def test_on_a_slice_the_scope_reads_the_task_or_its_slice_key():
    deep, quick = f"{CELL}@deep", f"{CELL}@quick"
    counts = [(CELL, FT, 95, 100), (CELL, LIST, 95, 100), (deep, LIST, 95, 100), (quick, LIST, 95, 100),
              (quick, FT, 95, 100)]
    whole = router([fine_tune((CELL,)), strong()], counts=counts)
    # scoped to the task: in scope on every slice, but admitted only by the slice's own counts
    assert reasons(whole.select(CELL, slice="deep"))[FT] == INSUFFICIENT_SAMPLES
    measured = router([fine_tune((CELL,)), strong()], counts=counts + [(deep, FT, 95, 100)])
    assert measured.select(CELL, slice="deep").primary == FT
    # scoped to one slice: that slice alone, never the unsliced task nor another slice
    one = router([fine_tune((deep,)), strong()], counts=counts + [(deep, FT, 95, 100)])
    assert one.select(CELL, slice="deep").primary == FT
    assert reasons(one.select(CELL))[FT] == out_of_scope()
    assert reasons(one.select(CELL, slice="quick"))[FT] == out_of_scope()
    starred = router([fine_tune(("*@deep",)), strong()], counts=counts + [(deep, FT, 95, 100)])
    assert starred.select(CELL, slice="deep").primary == FT
    assert reasons(starred.select(CELL))[FT] == out_of_scope()
    # review iter-434 should-fix 1: a pattern without '@' reads the task name, never the slice's
    table = f"{SUMMARY}@table_cell"
    by_slice = router([fine_tune(("*_cell",)), strong()],
                      counts=[(table, FT, 95, 100), (table, LIST, 95, 100)])
    assert reasons(by_slice.select(SUMMARY, slice="table_cell"))[FT] == out_of_scope()
    keyed = router([fine_tune(("*@table_cell",)), strong()],
                   counts=[(table, FT, 95, 100), (table, LIST, 95, 100)])
    assert keyed.select(SUMMARY, slice="table_cell").primary == FT
    # an unsliced task whose name holds '@' is matched by its whole name
    odd = router([fine_tune(("odd@name",)), strong()], tasks=("odd@name",))
    assert reasons(odd.select("odd@name"))[FT] == PASSES


def test_a_cascade_or_procedure_naming_a_scoped_model_is_out_of_scope_too():
    cascade = Cascade(FT, LIST, "low-confidence")
    tasks = {name: task(name, cascades=(cascade,)) for name in (CELL, SUMMARY)}
    proc = Procedure("shape", "v1", lambda ctx: ProcedureResult("ok"), max_model_calls=1, max_tool_calls=0,
                     model=FT)
    stats = Stats()
    for name in (CELL, SUMMARY):
        for route in (FT, LIST):
            stats.add(name, route, 95, 100)
        stats.add(name, cascade.id, 95, 100, escalated=10)
        stats.add(name, proc.id, 95, 100, cost_usd=0.01)
    routed = Router(Registry([fine_tune(), strong()]), tasks, stats)
    on_cell = reasons(routed.select(CELL, cascades=True, procedures=[proc]))
    assert (on_cell[cascade.id], on_cell[proc.id]) == (PASSES, PASSES)
    on_summary = reasons(routed.select(SUMMARY, cascades=True, procedures=[proc]))
    assert on_summary == {FT: out_of_scope(), LIST: PASSES, cascade.id: out_of_scope(), proc.id: out_of_scope()}
    # review iter-434 should-fix 4: the strong model of a cascade is checked too
    upward = Cascade(LIST, FT, "low-confidence")
    tasks_up = {name: task(name, cascades=(upward,)) for name in (CELL, SUMMARY)}
    for name in (CELL, SUMMARY):
        stats.add(name, upward.id, 95, 100, escalated=10)
    routed_up = Router(Registry([fine_tune(), strong()]), tasks_up, stats)
    assert reasons(routed_up.select(CELL, cascades=True))[upward.id] == PASSES
    assert reasons(routed_up.select(SUMMARY, cascades=True))[upward.id] == out_of_scope()


def test_the_delegate_obeys_the_scope():
    models = [fine_tune(), strong(), Model("p/parent", "p", 5.0, 25.0, 200_000)]
    routed = router(models)
    kwargs = dict(context_tokens=2000, brief_tokens=300, result_tokens=200)
    assert routed.decide_delegation(CELL, "p/parent", "cost_effective", **kwargs).model == FT
    assert routed.decide_delegation(SUMMARY, "p/parent", "cost_effective", **kwargs).model == LIST


def _load(tmp_path, rows):
    path = tmp_path / "models.json"
    path.write_text(json.dumps({"models": rows}), encoding="utf-8")
    return Registry.load(path)


def _row(model_id, **extra):
    return dict({"id": model_id, "family": "v", "price_in": 1.0, "price_out": 2.0, "context_window": 100_000},
                **extra)


def test_a_row_reads_its_scope_and_its_variants_keep_it(tmp_path):
    registry = _load(tmp_path, [_row("v/a", scope_tasks=[CELL, "review_*"], variants={"high": {}}),
                                _row("v/b"), _row("v/c", scope_tasks=None), _row("v/d", scope_tasks=[])])
    assert registry.get("v/a").scope_tasks == (CELL, "review_*")
    assert registry.get("v/a@high").scope_tasks == (CELL, "review_*")
    assert {registry.get(m).scope_tasks for m in ("v/b", "v/c", "v/d")} == {()}


@pytest.mark.parametrize("value", [CELL, [""], [1], [None], {"a": 1}, 3, [[CELL]]])
def test_a_refused_scope_names_the_file(tmp_path, value):
    with pytest.raises(ValueError, match="models.json.*scope_tasks"):
        _load(tmp_path, [_row("v/a", scope_tasks=value)])


def test_scoped_and_unscoped_models_round_trip_through_asdict(tmp_path):
    registry = _load(tmp_path, [_row("v/a", scope_tasks=[CELL]), _row("v/b")])
    back = _load(tmp_path, [dataclasses.asdict(m) for m in registry.models])
    assert back.models == registry.models
    assert json.loads(json.dumps(dataclasses.asdict(registry.get("v/b"))))["scope_tasks"] == []
    # review iter-434 must-fix 1: a self-hosted model or a variant is refused as before v1.586
    hosted = Model("v/h", "v", 1.0, 2.0, 100_000, pricing_basis="self_hosted", scope_tasks=(CELL,))
    variant = Model("v/a@hi", "v", 1.0, 2.0, 100_000, variant=Variant("hi"), scope_tasks=(CELL,))
    for model in (hosted, variant):
        with pytest.raises(ValueError, match="models.json"):
            _load(tmp_path, [dataclasses.asdict(model)])


def test_without_a_scope_every_model_is_a_candidate_on_every_task():
    # the defaults v1.586 keeps: an unscoped fine-tune is routed on both tasks, as before
    models = [Model(FT, "acme", 0.1, 0.2, 100_000), strong()]
    for name in (CELL, SUMMARY):
        picked = router(models).select(name)
        assert (picked.primary, picked.fallbacks, reasons(picked)) == (FT, (LIST,), {FT: PASSES, LIST: PASSES})


def test_no_packaged_row_or_evidence_file_names_a_scope():
    raw = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))
    assert not any("scope_tasks" in r for r in raw["models"])
    named = [path for path in (ROOT / "evidence").rglob("*") if path.is_file()
             and path.suffix in (".json", ".py", ".md") and "scope_tasks" in path.read_text(encoding="utf-8")]
    assert named == []


def test_explicit_empty_scopes_load_as_the_packaged_models(tmp_path):
    raw = json.loads((DATA_DIR / "models.json").read_text(encoding="utf-8"))
    for value in ([], None):
        explicit = [dict(r, scope_tasks=value) for r in raw["models"]]
        assert _load(tmp_path, explicit).models == Registry.load(DATA_DIR / "models.json").models


def test_only_the_registry_and_the_router_read_the_field():
    # so every evidence script, the demo, the executor's records, the reports and the CLI output
    # keep their bytes on an unscoped registry (row SCOPE1's defaults)
    naming = {path.name for path in PACKAGE.glob("*.py") if "scope_tasks" in path.read_text(encoding="utf-8")}
    assert naming == {"registry.py", "router.py"}


def _section(heading):
    text = (ROOT / "README.md").read_text(encoding="utf-8")
    return text.split(f"\n## {heading}\n", 1)[1].split("\n## ", 1)[0]


def _readme_part():
    # v1.604 (row PROD1a): the scope paragraph moved to `## Running it in production`, word for word
    return _section("Running it in production")


def test_the_readme_names_the_rule_and_the_reason():
    part = _readme_part()
    found = [p for p in part.split("\n\n") if p.startswith("A model built for some tasks can be kept to them.")]
    assert len(found) == 1
    text = found[0]
    for key in ('`"scope_tasks"`', "`out_of_scope`", "`<task>@<slice>`", "`DESIGN.md` 4.1 and 5.2",
                "(research/production-lessons.md#your-own-trained-model-is-a-candidate-kept-to-the-tasks-"
                "it-was-measured-on)"):
        assert key in text, key
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    quotes = [q for q in text.split('"')[1::2] if " " in q]
    assert quotes == ["These capabilities are each trained separately and can be deployed as tools and "
                      "sub-agents that our model can route to in order to tackle specific tasks."]
    assert all(f'"{q}"' in note for q in quotes)
    assert part.index("A model you train or serve yourself") < part.index(text)
    chosen = _section("How a model is chosen")  # the reason list and the flowchart stay there
    assert "`context_too_small`, `out_of_scope`, `insufficient_samples`" in chosen
    assert "Outside the model's scope_tasks?" in chosen.split("```mermaid", 1)[1].split("```", 1)[0]


def test_the_production_note_states_the_scope_as_shipped():
    note = (ROOT / "research" / "production-lessons.md").read_text(encoding="utf-8")
    assert "task scope" not in note
    lesson = note.split("\n### Your own trained model is a candidate, kept to the tasks it was "
                        "measured on\n", 1)[1].split("\n### ", 1)[0]
    line = [x for x in lesson.splitlines() if x.startswith("- In this library: ")]
    assert len(line) == 1
    assert ("`scope_tasks`, task names or glob patterns, keeps a model built for some tasks off the others: "
            "on any other task its candidate is `out_of_scope`") in line[0]
    replit = note.split("\n### Train a small model of your own for a narrow, high-volume job\n", 1)[1]
    replit_line = [x for x in replit.split("\n### ", 1)[0].splitlines() if x.startswith("- In this library: ")]
    assert len(replit_line) == 1
    assert "and its `scope_tasks` keeps a model trained for one job off the others" in replit_line[0]


def test_design_and_the_changelog_state_the_version():
    design = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    four = design[design.index("### 4.1 "):design.index("### 4.2 ")]
    assert four.count("- v1.586 task scope (row SCOPE1): `Model` gains a last field, `scope_tasks") == 1
    assert four.count("- v1.586 `Registry.load` reads the optional `scope_tasks` key of a row") == 1
    one = design[design.index("### 5.1 "):design.index("### 5.2 ")]
    assert one.count("- v1.586 task scope (row SCOPE1): `OUT_OF_SCOPE = \"out_of_scope\"`") == 1
    two = design[design.index("### 5.2 "):design.index("### 5.3 ")]
    assert two.count("- v1.586 task scope (row SCOPE1): rule 5a, after rule 5 and before rule 6") == 1
    assert "on `review_table_cell` the fine-tune is the primary at 0.00014 a call against 0.004" in two
    nine = design[design.index("## 9. "):design.index("## 10. ")]
    assert nine.count("- v1.586 `scope_tasks` (format in 4.1, row SCOPE1) is optional") == 1
    changelog = (ROOT / "CHANGELOG.md").read_text(encoding="utf-8").splitlines()
    mine = [line for line in changelog if line.startswith("- v1.586 (")]
    assert len(mine) == 1 and "(4.1, 5.1, 5.2, 9, row SCOPE1)" in mine[0]
