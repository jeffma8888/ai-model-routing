"""Registry, task, public API, and packaged-data contract tests."""

import importlib
import json
from dataclasses import FrozenInstanceError, asdict
from pathlib import Path
from urllib.parse import urlparse

import pytest
import model_routing
from model_routing import DATA_DIR, Model, Registry, Task, load_tasks, Priors


def test_model_cost_uses_per_million_input_and_output_prices(model_factory):
    model = model_factory(price_in=2.5, price_out=7.0)
    assert model.cost(1000, 300) == pytest.approx(0.0046)
    assert model.cost(0, 0) == 0.0
    assert model.cost(1_000_000, 0) == 2.5
    assert model.cost(0, 1_000_000) == 7.0


def test_model_defaults_aliases_and_is_frozen(model_factory):
    model = model_factory()
    assert model.aliases == {}
    assert model_factory(aliases={"api": "wire-model"}).aliases == {"api": "wire-model"}
    with pytest.raises(FrozenInstanceError):
        model.family = "changed"


def test_registry_preserves_input_order_and_get_returns_model(model_factory):
    models = [model_factory("fiction/z"), model_factory("fiction/a")]
    registry = Registry(iter(models))
    assert registry.models == tuple(models)
    assert isinstance(registry.models, tuple)
    assert registry.get("fiction/a") == models[1]


def test_registry_unknown_id_raises_keyerror(registry):
    with pytest.raises(KeyError):
        registry.get("fiction/unknown")


def test_registry_duplicate_ids_raise_valueerror(model_factory):
    with pytest.raises(ValueError):
        Registry([model_factory(), model_factory(price_in=9.0)])


def test_registry_load_accepts_metadata_sources_aliases_and_preserves_order(write_json):
    path = write_json("registry.json", {
        "version": "1.0", "as_of": "2026-01-01", "currency": "USD", "models": [
            {"id": "fiction/z", "family": "z", "price_in": 1.5, "price_out": 4.0,
             "context_window": 12000, "source": "https://example.org/z",
             "aliases": {"endpoint": "z-wire"}},
            {"id": "fiction/a", "family": "a", "price_in": 2.0, "price_out": 5.0,
             "context_window": 6000, "source": "https://example.org/a"},
        ]})
    registry = Registry.load(path)
    assert [m.id for m in registry.models] == ["fiction/z", "fiction/a"]
    assert registry.get("fiction/z") == Model("fiction/z", "z", 1.5, 4.0, 12000,
                                              {"endpoint": "z-wire"})
    assert registry.get("fiction/a").aliases == {}


def test_task_defaults_and_frozen_dataclass():
    task = Task("judge", 0.8)
    assert asdict(task) == {
        "name": "judge", "bar": 0.8, "min_samples": 30, "confidence": 0.95,
        "independent_of_generator": True, "exclude_families": (),
        "expected_input_tokens": 1000, "expected_output_tokens": 200,
        "on_no_model": "refuse", "max_fallbacks": 2, "prior_category": None,
        "timeout_s": 60.0, "fallback_below_bar": False,
    }
    with pytest.raises(FrozenInstanceError):
        task.bar = 0.1


@pytest.mark.parametrize("overrides", [
    {"bar": -0.01}, {"bar": 1.01}, {"min_samples": 0}, {"min_samples": -1},
    {"confidence": 0}, {"confidence": 1}, {"confidence": -0.1}, {"confidence": 1.1},
    {"on_no_model": "guess"}, {"expected_input_tokens": -1},
    {"expected_output_tokens": -1}, {"max_fallbacks": -1},
])
def test_task_invalid_values_raise_valueerror(task_factory, overrides):
    with pytest.raises(ValueError):
        task_factory(**overrides)


@pytest.mark.parametrize("bar", [0.0, 1.0])
def test_task_accepts_boundary_bars_zero_tokens_and_zero_fallbacks(task_factory, bar):
    task = task_factory(bar=bar, min_samples=1, expected_input_tokens=0,
                        expected_output_tokens=0, max_fallbacks=0,
                        on_no_model="best_available")
    assert task.bar == bar
    assert task.max_fallbacks == 0


def test_load_tasks_converts_json_lists_to_tuples_and_applies_defaults(write_json):
    path = write_json("tasks.json", {"tasks": [
        {"name": "first", "bar": 0.8, "exclude_families": ["one", "two"],
         "timeout_s": 4.5, "prior_category": "judging"},
        {"name": "second", "bar": 0.9}]})
    tasks = load_tasks(path)
    assert tasks == {"first": Task("first", 0.8, exclude_families=("one", "two"),
                                   timeout_s=4.5, prior_category="judging"),
                     "second": Task("second", 0.9)}


def test_load_tasks_duplicate_names_raise_valueerror(write_json):
    path = write_json("tasks.json", {"tasks": [{"name": "same", "bar": 0.2},
                                              {"name": "same", "bar": 0.9}]})
    with pytest.raises(ValueError):
        load_tasks(path)


def test_load_tasks_validates_each_task(write_json):
    path = write_json("tasks.json", {"tasks": [{"name": "bad", "bar": 2}]})
    with pytest.raises(ValueError):
        load_tasks(path)


@pytest.mark.parametrize("module,names", [
    ("registry", "Model Registry"), ("tasks", "Task load_tasks"),
    ("stats", "wilson_lower_bound Stats calibrate_from_results"), ("priors", "Priors"),
    ("router", "Candidate RouteDecision Router NoModelClearsBar EXCLUDED_MODEL EXCLUDED_FAMILY "
               "GENERATOR GENERATOR_FAMILY CONTEXT_TOO_SMALL INSUFFICIENT_SAMPLES BELOW_BAR PASSES"),
    ("providers", "Completion ProviderError Provider FakeProvider OpenAICompatibleProvider"),
    ("executor", "Attempt CallResult Executor AllModelsFailed json_validator"),
    ("monitor", "Monitor load_records report"), ("demo", "run_demo"), ("cli", "main"),
])
def test_public_names_are_reexported_from_package(module, names):
    source = importlib.import_module("model_routing." + module)
    for name in names.split():
        assert getattr(model_routing, name) is getattr(source, name)


def test_packaged_data_dir_and_models_load_with_positive_prices_and_source_urls():
    assert isinstance(DATA_DIR, Path)
    assert DATA_DIR.is_dir()
    path = DATA_DIR / "models.json"
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(raw["version"], str)
    assert raw["currency"] == "USD"
    assert len(raw["as_of"]) == 10
    registry = Registry.load(path)
    assert registry.models
    assert len(registry.models) == len(raw["models"])
    for row, model in zip(raw["models"], registry.models):
        assert model.id == row["id"]
        assert "/" in model.id
        assert model.price_in > 0 and model.price_out > 0
        assert model.context_window > 0
        url = urlparse(row["source"])
        assert url.scheme in {"https", "http"} and url.netloc


JUDGE_TASKS = {"faithfulness_judge", "code_correctness_judge", "pairwise_preference_judge"}
NON_JUDGE_TASKS = {"support_ticket_triage", "invoice_field_extraction", "unit_test_codegen",
                   "tool_calling_support_agent",  # the agent task from v1.90
                   "math_final_answer"}  # the exact-answer math task from v1.282


def test_packaged_example_tasks_cover_judge_and_non_judge_domains():
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    assert set(tasks) == JUDGE_TASKS | NON_JUDGE_TASKS
    for name in JUDGE_TASKS:
        assert tasks[name].independent_of_generator is True
    for name in NON_JUDGE_TASKS:
        assert tasks[name].independent_of_generator is False


def _all_passing_stats(tasks, registry):
    from model_routing import Stats
    stats = Stats()
    for task in tasks.values():
        for model in registry.models:
            stats.add(task.name, model.id, 1000, 1000)
    return stats


def test_every_packaged_task_routes_in_both_flavors():
    from model_routing import Router
    registry = Registry.load(DATA_DIR / "models.json")
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    router = Router(registry, tasks, _all_passing_stats(tasks, registry),
                    Priors.load(DATA_DIR / "priors.json"))
    for name, task in tasks.items():
        for flavor in ("cost_effective", "cost_blind"):
            decision = router.select(name, flavor=flavor)
            assert decision.basis == "measured" and decision.below_bar is False
            assert len(decision.fallbacks) == min(task.max_fallbacks, len(registry.models) - 1)
        cheapest = min(registry.models,
                       key=lambda m: (m.cost(task.expected_input_tokens,
                                             task.expected_output_tokens), m.id))
        assert router.select(name, flavor="cost_effective").primary == cheapest.id


def test_new_task_bars_are_reachable_exactly_at_min_samples():
    from model_routing import Router, Stats
    registry = Registry.load(DATA_DIR / "models.json")
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    model = registry.models[0].id
    for name in NON_JUDGE_TASKS:
        n = tasks[name].min_samples
        short = Stats()
        short.add(name, model, n - 1, n - 1)
        candidates = _candidates_or_refusal(Router(registry, tasks, short), name)
        assert {c.model_id: c.reason for c in candidates}[model] == "insufficient_samples"
        full = Stats()
        full.add(name, model, n, n)
        decision = Router(registry, tasks, full).select(name)
        assert {c.model_id: c.reason for c in decision.candidates}[model] == "passes"
        assert decision.primary == model


def _candidates_or_refusal(router, name):
    from model_routing import NoModelClearsBar
    try:
        return router.select(name).candidates
    except NoModelClearsBar as exc:
        return exc.candidates


def test_judge_task_isolation_is_a_no_op_without_a_generator():
    from model_routing import Router
    registry = Registry.load(DATA_DIR / "models.json")
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    assert tasks["faithfulness_judge"].independent_of_generator is True
    decision = Router(registry, tasks, _all_passing_stats(tasks, registry)).select(
        "faithfulness_judge")
    assert all(c.reason == "passes" for c in decision.candidates)


def test_non_judge_task_does_not_exclude_the_generator_family():
    from model_routing import Router
    registry = Registry.load(DATA_DIR / "models.json")
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    router = Router(registry, tasks, _all_passing_stats(tasks, registry))
    generator = registry.models[0]
    decision = router.select("unit_test_codegen", generator_model=generator.id)
    reasons = {c.model_id: c.reason for c in decision.candidates}
    assert reasons[generator.id] == "passes"
    assert all(reason == "passes" for reason in reasons.values())


def test_packaged_priors_load_with_public_source_date_and_metric():
    path = DATA_DIR / "priors.json"
    priors = Priors.load(path)
    raw = json.loads(path.read_text(encoding="utf-8"))
    assert raw["categories"]
    for category, data in raw["categories"].items():
        assert data["metric"] and data["as_of"]
        assert urlparse(data["source"]).scheme in {"https", "http"}
        assert data["scores"]
        for model, score in data["scores"].items():
            assert priors.score(category, model) == score


# v1.90: the tool-calling agent task (DESIGN 9)

ROOT = Path(__file__).resolve().parents[1]
AGENT_TASK = "tool_calling_support_agent"
TAU2_CONVERTER = ROOT / "evidence" / "tau2-bench" / "convert.py"


def _design_section_9():
    text = (ROOT / "DESIGN.md").read_text(encoding="utf-8")
    start = text.index("\n## 9. Data files\n")
    return text[start:text.index("\n## 10. ", start)]


def _agent_bullet():
    section = _design_section_9()
    start = section.index("\n- v1.90 `tool_calling_support_agent`")
    end = section.index("\n- ", start + 1) if "\n- " in section[start + 1:] else len(section)
    return section[start:end]


def test_agent_task_values_are_the_design_9_ones():
    task = load_tasks(DATA_DIR / "example_tasks.json")[AGENT_TASK]
    assert task == Task(AGENT_TASK, 0.7, min_samples=50, independent_of_generator=False,
                        expected_input_tokens=89000, expected_output_tokens=1500,
                        on_no_model="refuse", max_fallbacks=2, prior_category=None,
                        timeout_s=120.0)
    assert task.confidence == 0.95 and task.exclude_families == ()
    codegen = load_tasks(DATA_DIR / "example_tasks.json")["unit_test_codegen"]
    assert task.bar == codegen.bar and task.timeout_s == codegen.timeout_s
    others = [t for t in load_tasks(DATA_DIR / "example_tasks.json").values() if t.name != MATH_TASK]
    assert task.timeout_s == max(t.timeout_s for t in others)  # v1.282: the longest until the math task
    assert "the longest of the packaged tasks until v1.282 gave `math_final_answer` 440.0:" in _agent_bullet()
    raw = json.loads((DATA_DIR / "example_tasks.json").read_text(encoding="utf-8"))["tasks"]
    assert [row["name"] for row in raw][-2] == AGENT_TASK
    assert "prior_category" not in raw[-2]


def test_agent_task_min_samples_clause_is_the_wilson_threshold():
    from model_routing import wilson_lower_bound
    task = load_tasks(DATA_DIR / "example_tasks.json")[AGENT_TASK]
    n = task.min_samples
    k = min(s for s in range(n + 1) if wilson_lower_bound(s, n, task.confidence) >= task.bar)
    built = (f"At {n} a model clears {task.bar:g} only with {k} or more successes (Wilson lower bound "
             f"{wilson_lower_bound(k, n, task.confidence):.4f} at {k} and "
             f"{wilson_lower_bound(k - 1, n, task.confidence):.4f} at {k - 1}, 4.3)")
    assert built in _agent_bullet()
    assert f"`min_samples` {n}:" in _agent_bullet() and f"`bar` {task.bar:g}," in _agent_bullet()


def test_agent_task_fits_every_packaged_window_and_passes_in_both_flavors():
    from model_routing import Router
    registry = Registry.load(DATA_DIR / "models.json")
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    task = tasks[AGENT_TASK]
    smallest = min(m.context_window for m in registry.models)
    assert task.expected_input_tokens + task.expected_output_tokens <= smallest
    assert f"Every packaged window is at least {smallest:,} tokens, so no packaged model fails it" in _agent_bullet()
    router = Router(registry, tasks, _all_passing_stats(tasks, registry),
                    Priors.load(DATA_DIR / "priors.json"))
    for flavor in ("cost_effective", "cost_blind"):
        decision = router.select(AGENT_TASK, flavor=flavor)
        assert [c.reason for c in decision.candidates] == ["passes"] * len(registry.models)
        assert decision.basis == "measured" and decision.below_bar is False


def test_agent_task_refuses_without_passing_stats():
    from model_routing import NoModelClearsBar, Router, Stats
    registry = Registry.load(DATA_DIR / "models.json")
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    router = Router(registry, tasks, Stats(), Priors.load(DATA_DIR / "priors.json"))
    with pytest.raises(NoModelClearsBar) as caught:
        router.select(AGENT_TASK)
    assert {c.reason for c in caught.value.candidates} == {"insufficient_samples"}


README_STEP_1 = ("1. **Define the task** in a tasks file. `model_routing/data/example_tasks.json` ships three judge "
                 "tasks and five from other domains (`support_ticket_triage`, `invoice_field_extraction`, "
                 "`unit_test_codegen`, `tool_calling_support_agent`, `math_final_answer`):")
README_STEP_2 = ("For `tool_calling_support_agent` a line is one whole conversation: `correct` means the checks on "
                 "its end state passed, and its token counts are the sums over the conversation's model calls.")
README_STEP_2_MATH = ("For `math_final_answer` a line can give the final answer as `prediction` and the key's answer "
                      "as `gold`, both in one form (for example an integer), so the `==` comparison is the "
                      "exact-answer check.")


def test_readme_calibrate_steps_name_the_agent_task():
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    assert ("\n" + README_STEP_1 + "\n") in readme
    step_2 = ("   For `unit_test_codegen`, `correct` means the generated tests ran and passed; for an extraction "
              "task it might mean every field matched exactly. " + README_STEP_2 + " " + README_STEP_2_MATH
              + " The library only counts.")
    assert step_2 in readme
    assert '"' + README_STEP_2 + '"' in _agent_bullet()
    assert '"' + README_STEP_2_MATH + '"' in _math_bullet()
    names = ["support_ticket_triage", "invoice_field_extraction", "unit_test_codegen", AGENT_TASK, MATH_TASK]
    assert all(f"`{n}`" in README_STEP_1 for n in names) and set(names) == NON_JUDGE_TASKS


def _load_tau2_converter():
    import importlib.util
    spec = importlib.util.spec_from_file_location("tau2_convert_for_tasks", TAU2_CONVERTER)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _whole(x):
    return f"{int(x):,}" if x == int(x) else f"{x:,}"


def test_agent_task_sizes_and_bar_from_tau2_bench_when_cached():
    """v1.90: the DESIGN 9 token medians and retail rates, rebuilt from the pinned files at trial 0."""
    import statistics
    cv = _load_tau2_converter()
    folder = cv.default_cache_dir()
    if not all((folder / name).is_file() for name in cv.FILES):
        pytest.skip("the 12 pinned tau2-bench run files are not in the default cache")
    cv.fetch(folder)
    inputs, outputs, retail = [], [], []
    for name in cv.FILES:
        extract = cv.extract(cv.read_run(folder / name), trial=0, tokens=True)
        cells = extract["cells"].values()
        inputs += [cell["input_tokens"] for cell in cells]
        outputs += [cell["output_tokens"] for cell in cells]
        if extract["domain"] == "retail":
            retail.append(round(sum(cell["correct"] for cell in cells) / len(cells), 3))
    task = load_tasks(DATA_DIR / "example_tasks.json")[AGENT_TASK]
    med_in, med_out = statistics.median(inputs), statistics.median(outputs)
    assert task.expected_input_tokens == int(float(f"{med_in:.2g}"))
    assert task.expected_output_tokens == int(float(f"{med_out:.2g}"))
    built = (f"`expected_input_tokens` {task.expected_input_tokens:,} and `expected_output_tokens` "
             f"{task.expected_output_tokens:,}, to two significant figures the medians of the {len(inputs):,} "
             f"trial-0 conversations of the four tau2-bench agents read with `--tokens` (12.14), each the sum over "
             f"the conversation's agent calls: {_whole(med_in)} input and {_whole(med_out)} output tokens, against "
             f"means of {statistics.fmean(inputs):,.1f} and {statistics.fmean(outputs):,.1f}, which conversations "
             f"of up to {max(inputs):,} input tokens pull up.")
    assert built in _agent_bullet()
    above = sorted(rate for rate in retail if rate >= task.bar)
    words = {1: "one", 2: "two", 3: "three", 4: "four"}
    assert len(retail) == 4 and 0 < len(above) < 4
    clause = (f"below {words[len(above)]} of the four retail ones ("
              + " and ".join(f"{rate:g}" for rate in above) + ")")
    assert clause in _agent_bullet()


# v1.282: the exact-answer math task (DESIGN 9)

MATH_TASK = "math_final_answer"
WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five", 6: "six", 7: "seven", 8: "eight",
         9: "nine", 10: "ten", 11: "eleven", 12: "twelve"}


def _math_bullet():
    section = _design_section_9()
    start = section.index("\n- v1.282 `math_final_answer`")
    end = section.index("\n- ", start + 1) if "\n- " in section[start + 1:] else len(section)
    return section[start:end]


def _threshold(n, task):
    from model_routing import wilson_lower_bound
    return min(s for s in range(n + 1) if wilson_lower_bound(s, n, task.confidence) >= task.bar)


def test_math_task_values_are_the_design_9_ones():
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    task = tasks[MATH_TASK]
    assert task == Task(MATH_TASK, 0.8, min_samples=100, independent_of_generator=False,
                        expected_input_tokens=160, expected_output_tokens=5500,
                        on_no_model="best_available", max_fallbacks=2,
                        prior_category="abstract_reasoning", timeout_s=440.0)
    assert task.confidence == 0.95 and task.exclude_families == () and task.fallback_below_bar is False
    assert task.bar == tasks["code_correctness_judge"].bar
    assert task.min_samples == tasks["support_ticket_triage"].min_samples
    raw = json.loads((DATA_DIR / "example_tasks.json").read_text(encoding="utf-8"))["tasks"]
    assert [row["name"] for row in raw][-1] == MATH_TASK
    assert raw[-1]["prior_category"] == "abstract_reasoning"
    priors = json.loads((DATA_DIR / "priors.json").read_text(encoding="utf-8"))["categories"]
    assert priors["abstract_reasoning"]["metric"].startswith("ARC-AGI-3 ")
    bullet = _math_bullet()
    assert f"`bar` {task.bar:g}, the bar of `code_correctness_judge`." in bullet
    assert f"`min_samples` {task.min_samples}, as for `support_ticket_triage`:" in bullet
    assert "  - `on_no_model` `best_available`: a final answer changes no record" in bullet
    assert "  - `prior_category` `abstract_reasoning` (ARC-AGI-3, 4.4), the closest packaged category" in bullet


def test_math_task_timeout_is_the_codegen_limit_scaled_by_its_output():
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    task, codegen = tasks[MATH_TASK], tasks["unit_test_codegen"]
    assert task.timeout_s == codegen.timeout_s * task.expected_output_tokens / codegen.expected_output_tokens
    assert task.timeout_s == max(t.timeout_s for t in tasks.values())
    assert [t.name for t in tasks.values() if t.timeout_s == task.timeout_s] == [MATH_TASK]
    built = (f"`timeout_s` {task.timeout_s:.1f}, the longest of the packaged tasks: the {codegen.timeout_s:g} s "
             f"of `unit_test_codegen` scaled by the ratio of the two tasks' expected outputs, "
             f"{task.expected_output_tokens:,} to {codegen.expected_output_tokens:,}, since")
    assert built in _math_bullet()


def test_math_task_min_samples_clause_is_the_wilson_threshold():
    from model_routing import wilson_lower_bound
    task = load_tasks(DATA_DIR / "example_tasks.json")[MATH_TASK]
    n = task.min_samples
    k = _threshold(n, task)
    built = (f"At {n} a model clears {task.bar:g} only with {k} or more successes (Wilson lower bound "
             f"{wilson_lower_bound(k, n, task.confidence):.4f} at {k} and "
             f"{wilson_lower_bound(k - 1, n, task.confidence):.4f} at {k - 1}, 4.3), a rate of {k / n:g},")
    assert built in _math_bullet()
    k60 = _threshold(60, task)
    assert f"at 60, the size of `aime`, it needs {k60} ({k60 / 60:.3f}), above all 13 rates" in _math_bullet()


def test_math_task_routes_on_priors_without_stats_and_on_stats_with_them():
    from model_routing import Router, Stats
    registry = Registry.load(DATA_DIR / "models.json")
    tasks = load_tasks(DATA_DIR / "example_tasks.json")
    priors = Priors.load(DATA_DIR / "priors.json")
    for flavor in ("cost_effective", "cost_blind"):
        cold = Router(registry, tasks, Stats(), priors).select(MATH_TASK, flavor=flavor)
        assert cold.basis == "prior" and cold.below_bar is True and len(cold.fallbacks) == 2
        assert {c.reason for c in cold.candidates} == {"insufficient_samples"}
        warm = Router(registry, tasks, _all_passing_stats(tasks, registry), priors).select(MATH_TASK, flavor=flavor)
        assert [c.reason for c in warm.candidates] == ["passes"] * len(registry.models)
        assert warm.basis == "measured" and warm.below_bar is False


def test_select_runs_on_the_math_task_without_stats(capsys):
    from model_routing.cli import main
    assert main(["select", MATH_TASK]) == 0
    out = capsys.readouterr().out
    assert f"task:      {MATH_TASK}\n" in out
    assert "basis:     prior\n" in out and "below_bar: true\n" in out
    assert "`model-routing select math_final_answer` with no stats gives a route with `basis: prior`" in _math_bullet()


def test_math_task_values_from_llmrouterbench_aime_when_cached(llmrouterbench_pinned):
    """v1.282: the DESIGN 9 rates and token sizes, rebuilt from the converter's `aime` rows of the pinned file."""
    import statistics
    code, report, path = llmrouterbench_pinned
    assert code == 0 and report["tasks"]["aime"]["half_scores"] == 0
    with open(path, encoding="utf-8") as fh:
        cells = [row for row in (json.loads(line) for line in fh if line.strip()) if row["task"] == "aime"]
    models = sorted({c["model"] for c in cells})
    items = report["tasks"]["aime"]["items"]
    assert len(models) == 13 and items == 60 and len(cells) == items * len(models) == 780
    task = load_tasks(DATA_DIR / "example_tasks.json")[MATH_TASK]
    bullet = _math_bullet()
    assert (f"come from the {len(cells)} `aime` cells of the pinned LLMRouterBench file "
            f"({len(models)} models, {items} items, 12.18)") in bullet
    rates = {m: round(sum(c["correct"] for c in cells if c["model"] == m) / items, 3) for m in models}
    above = sorted((m for m in models if rates[m] > task.bar), key=lambda m: (-rates[m], m))
    below = [m for m in models if rates[m] < task.bar]
    assert len(above) + len(below) == len(models) and len(above) >= 2
    built = (f"On the {items} items the {len(models)} models reach {min(rates.values()):g} to "
             f"{max(rates.values()):g}, and {task.bar:g} is below {WORDS[len(above)]} of those rates ("
             + ", ".join(f"`{m}` {rates[m]:g}" for m in above[:-1])
             + f" and `{above[-1]}` {rates[above[-1]]:g}) and above the other {WORDS[len(below)]}")
    assert built in bullet
    k = _threshold(task.min_samples, task)
    best = max(rates.values())
    assert [m for m in models if rates[m] >= k / task.min_samples] == [above[0]]
    assert f"which only the best `aime` rate ({best:g}) reaches" in bullet
    assert _threshold(60, task) / 60 > best
    paid = [c for c in cells if c["cost_usd"] > 0]
    rest = [c for c in cells if c["cost_usd"] == 0]
    assert len(paid) + len(rest) == len(cells)  # review iter-191: the two sets hold every cell
    assert rest and all(not c["correct"] and c["output_tokens"] == 0 for c in rest)
    inputs = [c["input_tokens"] for c in paid]
    outputs = [c["output_tokens"] for c in paid]
    med_in, med_out = statistics.median(inputs), statistics.median(outputs)
    assert task.expected_input_tokens == int(float(f"{med_in:.2g}"))
    assert task.expected_output_tokens == int(float(f"{med_out:.2g}"))
    per = {}
    for c in paid:
        per.setdefault(c["model"], []).append(c["output_tokens"])
    medians = {m: statistics.median(v) for m, v in per.items()}
    lo = min(medians, key=lambda m: (medians[m], m))
    hi = max(medians, key=lambda m: (medians[m], m))
    built = (f"`expected_input_tokens` {task.expected_input_tokens:,} and `expected_output_tokens` "
             f"{task.expected_output_tokens:,}, to two significant figures the medians of the {len(paid):,} cells "
             f"with a `cost_usd` above 0, each one call's `prompt_tokens` and `completion_tokens` (12.18): "
             f"{_whole(med_in)} input and {_whole(med_out)} output tokens, against means of "
             f"{statistics.fmean(inputs):,.1f} and {statistics.fmean(outputs):,.1f}, which outputs of up to "
             f"{max(outputs):,} tokens pull up. The other {len(rest)} cells, all misses, record 0 output tokens "
             f"and a cost of 0 ({sum(c['input_tokens'] == 0 for c in rest)} of them 0 input tokens too), so they "
             f"give no size. Per model the median output runs from {_whole(medians[lo])} (`{lo}`) to "
             f"{_whole(medians[hi])} tokens (`{hi}`), {medians[hi] / medians[lo]:.1f} times as many,")
    assert built in bullet
