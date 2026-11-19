"""Longtail-SWE's pool: the four registry models and the release's other configs at their vendors' list prices (DESIGN 12.22, v1.497, row R53).

evidence/longtail-swe/convert.py (12.25) reads only the four registry models' files. This script reads all eleven
parquet files of the release at the pinned revision from `--cache` (default: the converter's), each checked by size
and sha256 (an absent one is downloaded), prices each run of a model `LIST_PRICES` names from its tokens at the list
prices its vendor's page stated when read (the four registry models at `models.json`'s), leaves out the model
`UNPRICED` names, builds the 12.25 matrix at run 0 on that pool, evaluates it with the 12.26 config and prints it beside
the committed four-model file evidence/longtail-swe/results.json. It loads the converter as a module of its own and
widens that module's `FILES` and `VENDORS`, so the converter's file is unchanged. Needs `pyarrow` as the converter does.
Run: python research/longtail_pool.py
"""
import argparse
import importlib.util
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from model_routing import evaluate, outcomes_from_rows  # noqa: E402

RUN = 0
BARS = [0.6, 0.7, 0.8, 0.9]  # the 12.26 config
SEEDS = 50
FLAVORS = ["cost_effective", "cost_blind"]
COMMITTED = ROOT / "evidence" / "longtail-swe" / "results.json"


def load(name, path):
    spec = importlib.util.spec_from_file_location(name, path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


CONVERT = load("longtail_swe_convert_for_pool", ROOT / "evidence" / "longtail-swe" / "convert.py")
RESULTS = load("routerbench_results_for_pool", ROOT / "evidence" / "routerbench" / "results.py")

READ = "2026-11-19"  # the day each page below was read
DEEPSEEK = "https://api-docs.deepseek.com/quick_start/pricing"
MOONSHOT = "https://platform.moonshot.ai/docs/pricing/chat"
QWEN = "https://www.alibabacloud.com/help/en/model-studio/model-pricing"
ZAI = "https://docs.z.ai/guides/overview/pricing"
# USD per 1M tokens (input, output) and the vendor page that states them, read on READ: the input price is the
# page's uncached one, as 12.25 prices every input token with no cache discount
LIST_PRICES = {
    "deepseek/deepseek-v4.1-flash": (0.3, 1.2, DEEPSEEK),  # `deepseek-flash`, version DeepSeek-V4.1-Flash-1017, peak
    "moonshotai/kimi-k3": (3.0, 15.0, MOONSHOT),
    "moonshotai/kimi-k3.1-pro": (2.0, 10.0, MOONSHOT),
    "qwen/qwen3.6-27b": (0.6, 3.6, QWEN),  # International, thinking mode
    "qwen/qwen3.8-27b": (0.5, 3.0, QWEN),  # International
    "z-ai/glm-5.3-flash": (0.15, 0.5, ZAI),
}
# a model whose vendor page states no price of its own: its file is checked and counted, never priced
UNPRICED = {"deepseek/deepseek-v4-flash": DEEPSEEK}
# the release's other seven parquet files, (size, sha256) as the tree API gave them on 2026-11-18
EXTRA = {
    "data/swelike__deepseek-v4-flash-max.parquet": (95517954, "25f291389a4afb3c65ed4a6a3f06c6dcac19c177891a085e51630331e027a703"),
    "data/swelike__deepseek-v4.1-flash-max.parquet": (128638805, "bfdee0faa1bd3d5d91010d8e229c595c0519bc2210d0294a034b0610f9efefa0"),
    "data/swelike__glm-5.3-flash-max.parquet": (104093005, "e4561cb6fba17cfb90d8c7da76c50334c541557c098aa4e0ec0a25058a3d1c0b"),
    "data/swelike__kimi-k3-max.parquet": (72324912, "3a8e0fd992f008009f278f6763f2457e574423222b46671dda1f355ae43d6687"),
    "data/swelike__kimi-k3.1-pro-max.parquet": (73139661, "0b72fb476aeba3e2c8e890d93172f33cdd60da34d09ffe0e023d2c08d7e07dfd"),
    "data/swelike__qwen3.6-27b-thinking.parquet": (42542761, "c412e932656b0eb9b6b0df19eda21e489004cd51b02b1019c024796645f16df8"),
    "data/swelike__qwen3.8-27b-xhigh.parquet": (84747991, "3605de55ec2518cdf8400f328e81bb3d6e24726205df95ffe4594288ea760fa6"),
}
FOUR = dict(CONVERT.FILES)  # the converter's own four, before widening
CONVERT.FILES = dict(sorted({**FOUR, **EXTRA}.items()))
CONVERT.VENDORS = CONVERT.VENDORS + (
    ("deepseek", re.compile(r"deepseek-[a-z0-9.-]+")),
    ("moonshotai", re.compile(r"kimi-[a-z0-9.-]+")),
    ("qwen", re.compile(r"qwen[0-9][a-z0-9.-]*")),
    ("z-ai", re.compile(r"glm-[a-z0-9.-]+")),
)


def model_id(canonical) -> str:
    """The provider-neutral ID of a canonical name, by a regex over it (the converter's two and four more)."""
    return CONVERT.model_id(canonical)


def registry() -> dict:
    """`models.json` with a row per `LIST_PRICES` model; a vendor price never replaces a registry row."""
    reg = json.loads(CONVERT.REGISTRY.read_text(encoding="utf-8"))
    ids = {m.get("id") for m in reg["models"]}
    clash = sorted(ids & set(LIST_PRICES))
    if clash:
        raise ValueError(f"already in the registry: {clash[0]}")
    extra = [{"id": k, "price_in": p_in, "price_out": p_out} for k, (p_in, p_out, _) in LIST_PRICES.items()]
    return {**reg, "models": reg["models"] + extra}


def refused(rows) -> int:
    """The runs whose token record the converter's `tokens` refuses (no input or output count)."""
    n = 0
    for row in rows:
        try:
            CONVERT.tokens(row.get("trajectory"))
        except ValueError:
            n += 1
    return n


def records(cache=None) -> tuple:
    """The pool's records in `FILES` order, and per `UNPRICED` model its runs and refused runs."""
    paths = CONVERT.fetch(cache)
    reg = registry()
    out, left = [], {}
    for name in CONVERT.FILES:
        rows = CONVERT.read_rows(paths[name])
        try:
            ids = {model_id(r.get("canonical_model")) if isinstance(r, dict) else None for r in rows}
            if ids & set(UNPRICED):
                if len(ids) != 1:
                    raise ValueError("a left-out model shares its file with another")
                left[ids.pop()] = (len(rows), refused(rows))
                continue
            out += CONVERT.run_records(rows, reg)
        except ValueError as exc:
            raise ValueError(f"{name}: {exc}") from None
    return out, left


def collect(recs) -> tuple:
    """The converter's report on the pool and the reduced 12.26 result of its matrix."""
    rows, report = CONVERT.convert(recs, RUN)
    result = evaluate(outcomes_from_rows(rows), bars=BARS, seeds=range(SEEDS))
    return report, RESULTS.reduce({k: v for k, v in result.items() if k != "cells"})


def num(value, places=3) -> str:
    return "-" if value is None else f"{value:.{places}f}"


def row_of(rows, bar, flavor, strategy) -> dict:
    found = [r for r in rows if r["bar"] == bar and r["flavor"] == flavor and r["strategy"] == strategy]
    if len(found) != 1:
        raise ValueError(f"{len(found)} rows for {bar} {flavor} {strategy}, not one")
    return found[0]


def price_of(model, reg) -> tuple:
    if model in LIST_PRICES:
        return LIST_PRICES[model]
    entry = next(m for m in reg["models"] if m.get("id") == model)
    return (entry["price_in"], entry["price_out"], "models.json")


def same(a, b, keys) -> bool:
    return all(a[k] == b[k] for k in keys)


ROUTED_KEYS = ("success", "cost_usd", "cleared_rate", "below_bar_rate", "bar_violation_rate")


def per_task_routed(result, bar, flavor) -> dict:
    rows = [r for r in result["per_task"] if r["bar"] == bar and r["flavor"] == flavor and r["strategy"] == "routed"]
    if len(rows) != 1:
        raise ValueError(f"{len(rows)} per-task routed rows for {bar} {flavor}, not one")
    return rows[0]


def block(report, pool, left, committed) -> str:
    """The note's `## Results` block."""
    models = report["models"]
    reg = registry()
    items = report["tasks"][CONVERT.TASK]["items"]
    out = [f"Pool: {len(models)} models, the 12.25 matrix at run {RUN} ({items} items, {report['rows']} rows, "
           f"{len(report['dropped_statement'])} dropped for a changed statement), under the 12.26 config "
           f"(bars {' '.join(map(str, BARS))}, {SEEDS} seeds, both flavors)", "",
           f"List prices, USD per 1M tokens, and their source (pages read {READ})",
           "model                          input  output  source"]
    for m in models:
        p_in, p_out, src = price_of(m, reg)
        out.append(f"{m:<30} {p_in:>5g} {p_out:>7g}  {src}")
    for m, (runs, bad) in sorted(left.items()):
        out.append(f"left out: {m} ({runs} runs, {bad} with no token counts), no price of its own at {UNPRICED[m]}")
    out += ["", f"Files read beyond the converter's {len(FOUR)}, size and sha256 from the tree API (2026-11-18)"]
    out += [f"{name} {size} {sha}" for name, (size, sha) in EXTRA.items()]
    first = pool["summary"]
    out += ["", f"Each model at run {RUN}: resolved of {items} (unscored), held-out success and cost in USD over {SEEDS} "
            f"seeds (bar {BARS[0]}, {FLAVORS[0]})", "model                          resolved   success      cost"]
    for m in models:
        r = row_of(first, BARS[0], FLAVORS[0], f"model:{m}")
        out.append(f"{m:<30} {report['resolved'][m]:>4} ({len(report['unscored'][m])}) {num(r['success']):>9} "
                   f"{num(r['cost_usd'], 2):>9}")
    out += ["", f"Baselines, the pool beside the committed four-model file (bar {BARS[0]}, {FLAVORS[0]})",
            "strategy             pool success     cost   four success     cost"]
    for s in ("best_on_calibration", "cheapest", "oracle"):
        p = row_of(first, BARS[0], FLAVORS[0], s)
        f = row_of(committed["summary"], BARS[0], FLAVORS[0], s)
        out.append(f"{s:<20} {num(p['success']):>12} {num(p['cost_usd'], 2):>8} {num(f['success']):>14} "
                   f"{num(f['cost_usd'], 2):>8}")
    out += ["", "Routed, the pool beside the committed four-model file (success, cost, cleared rate, bar-violation rate)",
            "bar  flavor          pool success     cost cleared violation   four success     cost cleared violation"]
    equal = picks_equal = 0
    for bar in BARS:
        for flavor in FLAVORS:
            p = row_of(first, bar, flavor, "routed")
            f = row_of(committed["summary"], bar, flavor, "routed")
            equal += same(p, f, ROUTED_KEYS)
            picks_equal += (per_task_routed(pool, bar, flavor)["routed_models"]
                            == per_task_routed(committed, bar, flavor)["routed_models"])
            out.append(f"{bar:<4} {flavor:<15} {num(p['success']):>12} {num(p['cost_usd'], 2):>8} {num(p['cleared_rate']):>7} "
                       f"{num(p['bar_violation_rate']):>9} {num(f['success']):>12} {num(f['cost_usd'], 2):>8} "
                       f"{num(f['cleared_rate']):>7} {num(f['bar_violation_rate']):>9}")
    n = len(BARS) * len(FLAVORS)
    out += [f"routed rows exactly equal (all five rates and the cost): {equal} of {n}; "
            f"per-task routed models exactly equal: {picks_equal} of {n}"]
    out += ["", f"Routed models of the pool, seeds of {SEEDS} per model"]
    for bar in BARS:
        for flavor in FLAVORS:
            picks = sorted(per_task_routed(pool, bar, flavor)["routed_models"].items(), key=lambda kv: (-kv[1], kv[0]))
            out.append(f"{bar:<4} {flavor:<15} " + ", ".join(f"{m} {k}" for m, k in picks))
    return "\n".join(out) + "\n"


PRICE = re.compile(r"^(\S+/\S+) +(\S+) +(\S+)  (\S+)$")
LEFT = re.compile(r"^left out: (\S+) \((\d+) runs, (\d+) with no token counts\)")
MODEL = re.compile(r"^(\S+/\S+) +(\d+) \((\d+)\) +(\S+) +(\S+)$")
BASE = re.compile(r"^(best_on_calibration|cheapest|oracle) +(\S+) +(\S+) +(\S+) +(\S+)$")
EQUAL = re.compile(r"^routed rows exactly equal \(all five rates and the cost\): (\d+) of (\d+); "
                   r"per-task routed models exactly equal: (\d+) of (\d+)$")
PICKS = re.compile(r"^(0\.\d+) +(cost_\w+) +(\S+/.*)$")


def facts_from_block(text) -> dict:
    """The block's prices, left-out models, model rows, baselines, equal counts and routed models, read back
    from its text, so `reading` states only what the block holds."""
    f = {"prices": {}, "left": {}, "alone": {}, "base": {}, "equal": None, "picks": {}}
    for line in text.split("\n"):
        if m := PRICE.match(line):
            f["prices"][m.group(1)] = (float(m.group(2)), float(m.group(3)), m.group(4))
        elif m := LEFT.match(line):
            f["left"][m.group(1)] = (int(m.group(2)), int(m.group(3)))
        elif m := MODEL.match(line):
            f["alone"][m.group(1)] = (int(m.group(2)), int(m.group(3)), m.group(4), m.group(5))
        elif m := BASE.match(line):
            f["base"][m.group(1)] = m.groups()[1:]
        elif m := EQUAL.match(line):
            f["equal"] = tuple(int(g) for g in m.groups())
        elif m := PICKS.match(line):
            pairs = re.findall(r"(\S+/\S+) (\d+)", m.group(3))
            f["picks"][(float(m.group(1)), m.group(2))] = {k: int(v) for k, v in pairs}
    return f


def _and(words) -> str:
    words = list(words)
    return words[0] if len(words) == 1 else ", ".join(words[:-1]) + " and " + words[-1]


def reading(f) -> str:
    """The note's `## Reading it` bullets, every number and comparison from `facts_from_block`."""
    added = [m for m, p in f["prices"].items() if p[2] != "models.json"]
    own = [m for m, p in f["prices"].items() if p[2] == "models.json"]
    equal, n, picks_equal, n2 = f["equal"]
    routed = sorted({m for picks in f["picks"].values() for m in picks if m in added})
    out = [f"- Routed rows: on {equal} of {n} (bar, flavor) rows the pool's routed success, cost and rates equal the "
           f"committed four-model file's exactly, and on {picks_equal} of {n2} its per-task routed models do; "
           + ("no added model is routed on any seed at any bar or flavor." if not routed
              else _and(f"`{m}`" for m in routed) + " is routed on some seed.")]
    s = {m: float(f["alone"][m][2]) for m in f["alone"]}
    c = {m: float(f["alone"][m][3]) for m in f["alone"]}
    lo, hi = min(added, key=lambda m: (s[m], m)), max(added, key=lambda m: (s[m], m))
    clo, chi = min(added, key=lambda m: (c[m], m)), max(added, key=lambda m: (c[m], m))
    over = [r for r in own if all(s[r] >= s[a] and c[r] <= c[a] for a in added)]
    text = (f"- Each added model alone: held-out success {f['alone'][lo][2]} (`{lo}`) to {f['alone'][hi][2]} (`{hi}`), "
            f"held-out cost {f['alone'][clo][3]} (`{clo}`) to {f['alone'][chi][3]} (`{chi}`) USD; ")
    if over:
        text += (_and(f"`{r}` ({f['alone'][r][2]} for {f['alone'][r][3]})" for r in over)
                 + (" has" if len(over) == 1 else " each have")
                 + " at least the held-out success of every added model for no more held-out cost.")
    else:
        text += "no registry model has at least the held-out success of every added model for no more held-out cost."
    out.append(text)
    low = min(f["prices"], key=lambda m: (f["prices"][m][0], f["prices"][m][1], m))
    least = min(f["alone"], key=lambda m: (c[m], m))
    if low != least and all(f["prices"][low][i] <= f["prices"][m][i] for m in f["prices"] for i in (0, 1)):
        out.append(f"- A list price is not a cost: `{low}` has the pool's lowest input and output prices "
                   f"({f['prices'][low][0]:g} and {f['prices'][low][1]:g}) but a held-out cost of {f['alone'][low][3]}, "
                   f"{c[low] / c[least]:.2f} times that of `{least}` ({f['alone'][least][3]} at "
                   f"{f['prices'][least][0]:g} and {f['prices'][least][1]:g}), the least held-out cost of the pool.")
    o = f["base"]["oracle"]
    word = "above" if float(o[0]) > float(o[2]) else "below" if float(o[0]) < float(o[2]) else "level with"
    out.append(f"- The 12.3 oracle is at {o[0]} for {o[1]} on the pool, {word} the four-model file's {o[2]} for {o[3]}"
               + (": an added model resolves some held-out issue that no registry model does, but the router, which "
                  "sends the one task to one model per seed, cannot take it." if word == "above" else "."))
    for m, (runs, bad) in sorted(f["left"].items()):
        out.append(f"- Left out: `{m}`, {runs} runs, {bad} of them with no token counts; no matrix holds a run of it.")
    return "\n".join(out) + "\n"


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def main(argv=None) -> int:
    parser = _Parser(prog="longtail_pool.py", description="Longtail-SWE's eleven configs at list prices")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {CONVERT.default_cache_dir()})")
    try:
        args = parser.parse_args(argv)
        recs, left = records(args.cache)
        report, pool = collect(recs)
        committed = json.loads(COMMITTED.read_text(encoding="utf-8"))
        text = block(report, pool, left, committed)
    except (ValueError, OSError, ImportError) as exc:
        msg = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {msg}", file=sys.stderr)
        return 2
    sys.stdout.write(text)
    return 0


if __name__ == "__main__":
    sys.exit(main())
