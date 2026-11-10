"""Convert the LiveCodeBench submissions into the evaluator's outcome matrix (DESIGN 12.16).

Usage: python evidence/livecodebench/convert.py --out PATH [--cache DIR]

Standard library only. The 67 kept files of the pinned commit are downloaded into a cache outside
the repo, each checked by size and sha256 before it is read, and read one at a time. A problem's
label is its test cases passing for the first sample (``graded_list[0]``); the items are the
question ids every kept file has. The files carry no cost, so every row has ``cost_usd`` 0.0 and
the matrix feeds ``cost_blind`` only. Nothing is kept but model, question id, contest date and
label: no problem text and no generated code.
"""

import argparse
import hashlib
import json
import os
import re
import sys
import urllib.parse
import urllib.request
from pathlib import Path

REVISION = "6ca212e9c2039373f6e5069d37ffa9db66e23736"
LICENCE = "MIT"
BASE_URL = f"https://raw.githubusercontent.com/LiveCodeBench/submissions/{REVISION}/"
TASK = "code_generation"
TIMEOUT = 60
# "<folder>/<file name>": (bytes, sha256), in ascending path order
FILES = {
    'Claude-3-Haiku/Scenario.codegeneration_10_0.2_eval_all.json': (21175537, 'd4dde49c99058f4fac9e9faeb739c59e3024b062d29c1fa8a875a92ef5e15edb'),
    'Claude-3.5-Sonnet-20240620/Scenario.codegeneration_10_0.2_eval_all.json': (17342354, '8227e0e70d72d808bf65809f905052f36ebb82e504b69908fb31d7e7ac7f3a92'),
    'Claude-3.5-Sonnet-20241022/Scenario.codegeneration_10_0.2_eval_all.json': (29896047, '1b900ac47a147006ea2f8c258d60a6ee9dd8dff378ebcd926f322466179d99b1'),
    'Claude-3.7-Sonnet/Scenario.codegeneration_1_0.2_eval_all.json': (40780648, '1b8334f503ad2d13eaa2b3ea15b46a289706276d40e96f3274442e0d8184620f'),
    'Claude-Opus-4 (Thinking)/Scenario.codegeneration_1_0.2_eval_all.json': (15447145, 'd9b959036c9952161dcbdd515a225a2d2a03c747469dd50ac2b6561d42b04714'),
    'Claude-Opus-4/Scenario.codegeneration_1_0.2_eval_all.json': (5707347, 'a75e46288b0457ebd2ce7fee3f06d69fdeda4b00742defe3b13c46887892db91'),
    'Claude-Sonnet-4 (Thinking)/Scenario.codegeneration_1_0.2_eval_all.json': (19133477, '339db7aab7be74a509e25fcf75bc42adff3f6e4829d8d5a3359864de0e1d8188'),
    'Claude-Sonnet-4/Scenario.codegeneration_1_0.2_eval_all.json': (6096105, 'caa412a80e12e51bd2737a99c557691241b5acf2f4e404f2db0556417efcf600'),
    'Codestral-Latest/Scenario.codegeneration_10_0.2_eval_all.json': (16698489, 'f3b7ad09528d9046451b5fe0e3f67f26912c5fd4d6fdf0db22ba5b0af0d0cd2b'),
    'DSCoder-1.3b-Ins/Scenario.codegeneration_10_0.2_eval_all.json': (8972584, 'f78ad8f239ff5144c81709ecab72dca1eee19b40b21ba1a2fcf92501c8dae017'),
    'DSCoder-33b-Ins/Scenario.codegeneration_10_0.2_eval_all.json': (10124550, 'af10caa8fe47deaa745f410768864f8813e234c02872b247cb9c076dd872575f'),
    'DSCoder-6.7b-Ins/Scenario.codegeneration_10_0.2_eval_all.json': (11257116, 'f972642519aa1e346f73dffe6f0b2387b406a1548d216bc84fe9e19c7e53a127'),
    'DeepCoder-14B-Preview/Scenario.codegeneration_10_0.2_eval_all.json': (51800914, '52870bf12c83f9245cccb41d5b65a65fd8f9d18895063a1cde3354346f93b048'),
    'DeepSeek-R1-0528/Scenario.codegeneration_10_0.6_eval_all.json': (55720447, '403fb6060512b10766fba5e1c16ba320191355e8d7e920f01e5be69bcde25231'),
    'DeepSeek-R1-Lite-Preview/Scenario.codegeneration_10_0.2_eval_all.json': (36340580, 'd432c2668f49d8baf1ec512d73ade2a8133e5108043d6e9a1a44912bb3e74f5e'),
    'DeepSeek-R1-Preview/Scenario.codegeneration_10_0.2_eval_all.json': (37086048, '7a363a772c47d00a63db99d0f444e28e9ec6f0f8f26adc50b9190fc908332a99'),
    'DeepSeek-V3/Scenario.codegeneration_10_0.2_eval_all.json': (36242668, '88548117b84bf567fdadb159cfc65f9c0a6bf7da8b2fe5679829c95334abd661'),
    'EXAONE-4.0-32B/Scenario.codegeneration_4_0.6_eval_all.json': (23877444, '019bc78e1685fbe411149cb6c69244d2bafe04304cfd72f60bab3c5b27b3dc6f'),
    'GPT-4-0613/Scenario.codegeneration_10_0.2_eval_all.json': (9600263, 'bd0ab24c9f8da86bf010f90e55d052ecf513922649c2f181b742d21cbfa37189'),
    'GPT-4-Turbo-1106/Scenario.codegeneration_10_0.2_eval_all.json': (14387341, '73e2e8e25b92fe23a578d3fe6c29f83a48dc5dbee9c3d5e7d907f75f7f0ac650'),
    'GPT-4-Turbo-2024-04-09/Scenario.codegeneration_10_0.2_eval_all.json': (28049953, 'fc46d2a4fdd42caa0f7ec30366c318ddcded2334a0b3128752b5f15c4793bf97'),
    'GPT-4O-2024-05-13/Scenario.codegeneration_10_0.2_eval_all.json': (17904865, '072871af75fcb2b00efad273372f7f701363576f1e2cd2f57dc19c97b3f2d362'),
    'GPT-4O-2024-08-06/Scenario.codegeneration_10_0.2_eval_all.json': (32778775, '5d072bd884756779f22f6e9239b142f82ff87dd2d76f7647f732be2a55efb0ec'),
    'GPT-4O-mini-2024-07-18/Scenario.codegeneration_10_0.2_eval_all.json': (24796617, '37b922fae87f97c957e9a2554ddabdaa777d876758bad86e7aabb2f26ebf4972'),
    'Gemini-2.5-Flash-04-17/Scenario.codegeneration_1_0.2_eval_all.json': (9298858, '2b81892984e212d9937942aafb9e478e985600e50114d7fa86fba2b5f53486cf'),
    'Gemini-2.5-Flash-05-20/Scenario.codegeneration_1_0.2_eval_all.json': (16026288, '75957e8b682cf4bf75f4b24953038f7e374c0f9c592d8f7577117d7ea060057c'),
    'Gemini-2.5-Pro-03-25/Scenario.codegeneration_1_0.2_eval_all.json': (12182339, 'a336ec7c2d9d83fa331c43633be5abc08817441cf2d9d18d362b7924ea610b29'),
    'Gemini-2.5-Pro-05-06/Scenario.codegeneration_1_0.2_eval_all.json': (15665903, '7e0cae96e609e085beeb66d56b74e9186d948c65c803427f1a5d022401982026'),
    'Gemini-2.5-Pro-06-05/Scenario.codegeneration_1_0.2_eval_all.json': (13420908, '19be5460eda197621738c871cd496d79b1d1fa3c653a5a7742fd4985abfd2d39'),
    'Gemini-Exp-1206/Scenario.codegeneration_10_0.2_eval_all.json': (19858737, '5555e4cde78f48a6b6ee3391964bb9b9d379a61b0bd9f71137548c5fcddc7b71'),
    'Gemini-Flash-1.5-002/Scenario.codegeneration_10_0.2_eval_all.json': (15723216, '46150890d210451f966408536d2cdf2434f044811ad85faff496e4b4d6f0e0b5'),
    'Gemini-Flash-2.0-Exp/Scenario.codegeneration_1_0.2_eval_all.json': (6955936, '9c0b4f222c428d627ae8fee677a031b203b30e45a396a1c41ad8358ebb5bc42c'),
    'Gemini-Flash-2.0-Thinking-01-21/Scenario.codegeneration_1_0.2_eval_all.json': (20903075, '227f75adcf0502e1942b9178b353f0665617a86ce525e64fde26f5a4330574b1'),
    'Gemini-Flash-2.0-Thinking-12-19/Scenario.codegeneration_1_0.2_eval_all.json': (20546068, '72e58004bd0f09835bb3f2600c41c3bce2e1ad815662ee9a4a294185d543812a'),
    'Gemini-Flash-2.0-Thinking/Scenario.codegeneration_10_0.2_eval_all.json': (23667385, 'd79024201d8a77db19135d94a1812ffde2c02ffb7ed7ef1d53f69f8018c61687'),
    'Gemini-Pro-1.5-002/Scenario.codegeneration_10_0.2_eval_all.json': (15887371, 'c6650177f41ab56596e5085077a2edf1444170bc1a804c447cd2fd900449e1ba'),
    'Grok-3-Mini (High)/Scenario.codegeneration_1_0.4_eval_all.json': (4361019, '834f0311cc6d0610b9c1840e9cb26a80ced4ef08b3400ee2926881e8036a4fab'),
    'Kimi-k1.6-IOI-high/Scenario.codegeneration_1_1.0_eval_all.json': (4099066, 'ef3a96fce0c8fd83417bc11a55200c3159d39b1936960959ebb67f15b0bd9b58'),
    'Kimi-k1.6-IOI/Scenario.codegeneration_10_0.8_eval_all.json': (30401298, '59583d3fbc343920e48fa7c9c257e0ec5e564c152e066c0b6560546a061b8013'),
    'LLama3.3-70b-Ins/Scenario.codegeneration_10_0.2_eval_all.json': (16031611, '91708bc6db33d239ad4b8c75424448035263b73b2dc44a428f2b1300affc4071'),
    'Llama-3_1-Nemotron-Nano-8B-v1/Scenario.codegeneration_1_eval_all.json': (19558899, 'cf3729eaf6e9b5164951fbf82506ce05ca95f52d2130c3c9ec3955958913aadf'),
    'Llama-3_1-Nemotron-Ultra-253B-v1/Scenario.codegeneration_1_eval_all.json': (5107907, '9e31c5feba8b56bf7515684c415c0c7e5e1f31d3a2f896f24ef9fabe66d8dba3'),
    'MetaStone-L1-7B/Scenario.codegeneration_10_0.6_eval_all.json': (54754997, '499f395db1cba305790446a6251c6b9822d78b757ca447d29e41b9dd4b338219'),
    'Mistral-Large/Scenario.codegeneration_10_0.2_eval_all.json': (20707461, '73a67f7b514f6fb94bdbe0a7762d4d7e9daeacf8d155ae81a53a8e2719ea0469'),
    'O1-2024-12-17 (High)/Scenario.codegeneration_1_0.2_eval_all.json': (5693027, '52c10c62c5408faeda5cedac221b71251564dd307bc61512df28e33aa902e642'),
    'O1-2024-12-17 (Low)/Scenario.codegeneration_1_0.2_eval_all.json': (6554308, '96cf54b1f7b19d8d202641e1915aa5ef663c06811ed06a99893123b79f077234'),
    'O1-2024-12-17 (Med)/Scenario.codegeneration_1_0.2_eval_all.json': (6342959, '2cfef88d6130d0700dc75e8a9470680dff81fffce4e9d78d88600e99125e9d46'),
    'O1-Mini-2024-09-12/Scenario.codegeneration_1_0.2_eval_all.json': (3636170, '9e7c9d729cc464af3e532af9faa1ec8ea993839567e4c952bfa7fb92e094d78b'),
    'O1-Preview-2024-09-12/Scenario.codegeneration_1_0.2_eval_all.json': (3799086, '916568014b99be062ca202efb6390fb8cfb8dc750ad4d88611df4cd44c6bc84e'),
    'O3 (High)/Scenario.codegeneration_1_0.2_eval_all.json': (5316324, 'a7c900595d6ca6eba133e03e9e4fd24b0047a87e8a8302935ba2b83f0b834ff7'),
    'O3-Mini-2025-01-31 (High)/Scenario.codegeneration_1_0.2_eval_all.json': (7234096, '37440ebbcbb947c5bf8b19eab872f1e0386013e00fcabf6a2eb074c56ca9774d'),
    'O3-Mini-2025-01-31 (Low)/Scenario.codegeneration_1_0.2_eval_all.json': (6836877, '4f4bed0e765eb9ff8fbc909a78225f9c40c41775aeae670e5ef9ddd42a24d3b5'),
    'O3-Mini-2025-01-31 (Med)/Scenario.codegeneration_1_0.2_eval_all.json': (7150157, '428773c6bf3445ee9ca2f7cadaea18a6e328e82ce68e5ef6d0e19a0ba5243f42'),
    'O4-Mini (High)/Scenario.codegeneration_1_0.2_eval_all.json': (5566694, '533249d34528071b3cd4ca50c756b61518a37cc90f6d4b3a931ca9dce421b06b'),
    'O4-Mini (Low)/Scenario.codegeneration_1_0.2_eval_all.json': (5289377, '1ccf62bb019c8a9176bfc7e1625b36ad4f82a1029d636fe949c4b8133bbcea59'),
    'O4-Mini (Medium)/Scenario.codegeneration_1_0.2_eval_all.json': (5449673, 'd045f8bcdfec799803fa8734f9a51aa2c589f0759ff509470320cde550b33ed3'),
    'OpenReasoning-Nemotron-32B/Scenario.codegeneration_10_0.6_eval_all.json': (22370156, '5aec11207b7d6ff37f6220513e5fcc9df8a6d837bc46a0163f1ff95ae0955e61'),
    'QwQ-32B-Preview/Scenario.codegeneration_1_0.2_eval_all.json': (31532692, '7a6ac226b050b3d29e7cceb900c80a6c13872a87099be72b1726b747c7962b8b'),
    'QwQ-32B_temp/Scenario.codegeneration_1_0.2_eval_all.json': (44575245, '616906647f8c31136f1bb2e8924a0fe9587ef085ee77781c963f029d738c6fe6'),
    'QwQ-Max-Preview/Scenario.codegeneration_1_0.6_eval_all.json': (30801371, 'dd3c3c428ef04e07892cd2a1308cfd1cadcce61e3f37454076b6813d854e0a62'),
    'Qwen2-Ins-72B/Scenario.codegeneration_10_0.2_eval_all.json': (12353225, '5ce1e7b71388887353264034a15425c2debabfc775a18f231aea215ceb388381'),
    'Qwen2.5-Coder-Ins-32B/Scenario.codegeneration_10_0.2_eval_all.json': (15265370, 'b3cee20f0bfcfeccf4350c75244eaeb9ab73385a732d433629845177d6231822'),
    'Qwen2.5-Coder-Ins-7B/Scenario.codegeneration_10_0.2_eval_all.json': (10858879, '586707158f8d1648964f54f0290dc42c94806b12684ea03b537202008170c992'),
    'Qwen2.5-Ins-32B/Scenario.codegeneration_10_0.2_eval_all.json': (12135021, '39c766b34f6a412fac0c9e382bed7ea5d2b8a45874b67d6bb998455edc6a183c'),
    'Qwen2.5-Ins-72B/Scenario.codegeneration_10_0.2_eval_all.json': (12705443, '6555e98ea20a4aa5d2ac2439cc62065001280366e11815c0c29f32fe31228f68'),
    'Qwen2.5-Ins-7B/Scenario.codegeneration_10_0.2_eval_all.json': (10517624, 'b9b11acc6b1beadcb25067000bb619cbe1a7c53c859882606d04550cdb018179'),
    'Qwen3-235B-A22B/Scenario.codegeneration_1_0.6_eval_all.json': (45188691, '4b64e46c8f1a3e7ae14906b28e685624f05becaafe6422be7743f8a04c77b7b9'),
}
# the other 6 files at REVISION, never downloaded: "<folder>/<file name>": skip_reason, ascending
DROPPED = {
    'AzeroGPT-64b/Scenario.codegeneration_10_0.2_eval_all.json': 'no vendor rule',
    'DeepSeek-V3 copy/Scenario.codegeneration_10_0.2_eval_all.json': 'copy of another folder',
    'Gemini-Flash-2.0-Exp (N=10)/Scenario.codegeneration_10_0.2_eval_all.json': '10-sample run',
    'Gemini-Flash-2.0-Exp (N=10)/Scenario.codegeneration_1_0.2_eval_all.json': '10-sample run',
    'O1-2024-12-17 (Low)_prompt_old/Scenario.codegeneration_1_0.2_eval_all.json': 'superseded prompt',
    'XBai-o4-medium/Scenario.codegeneration_1_0.6_eval_all.json': 'no vendor rule',
}

VENDORS = (
    (r"Claude-", "anthropic"),
    (r"(GPT-|O[134]([- ]|$))", "openai"),
    (r"Gemini-", "google"),
    (r"(DeepSeek-|DSCoder-)", "deepseek"),
    (r"(Qwen|QwQ-)", "qwen"),
    (r"(Llama-3_1-Nemotron-|OpenReasoning-Nemotron-)", "nvidia"),
    (r"LLama", "meta-llama"),
    (r"(Mistral-|Codestral-)", "mistralai"),
    (r"Grok-", "xai"),
    (r"Kimi-", "moonshotai"),
    (r"EXAONE-", "lgai"),
    (r"DeepCoder-", "agentica"),
    (r"MetaStone-", "metastone"),
)
SLUG = re.compile(r"[a-z0-9][a-z0-9._-]*")
DATE = re.compile(r"(\d{4}-\d{2}-\d{2})(T.*)?")


def model_id(folder) -> str:
    """`vendor/model` from a folder name by the first VENDORS pattern that matches its start."""
    if not isinstance(folder, str) or not folder:
        raise ValueError(f"folder name must be a non-empty string, got {folder!r}")
    if "/" in folder:
        raise ValueError(f"folder name {folder!r} contains '/'")
    if not folder.isascii():  # before lower(): U+212A, the Kelvin sign, lowercases to an ASCII k
        raise ValueError(f"folder name {folder!r} is not ASCII")
    for pattern, vendor in VENDORS:
        if re.match(pattern, folder):
            slug = folder.lower().replace(" (", "-").replace(")", "").replace(" ", "-")
            if not SLUG.fullmatch(slug):
                raise ValueError(f"folder name {folder!r} gives no valid model name")
            return f"{vendor}/{slug}"
    raise ValueError(f"no vendor rule matches folder {folder!r}")


def skip_reason(folder):
    """Why a folder is not kept, by the first rule that matches, or None for a kept folder."""
    if not isinstance(folder, str) or not folder:
        raise ValueError(f"folder name must be a non-empty string, got {folder!r}")
    if folder.endswith(" copy"):
        return "copy of another folder"
    if "(N=10)" in folder:
        return "10-sample run"
    if folder.endswith("_prompt_old"):
        return "superseded prompt"
    try:
        model_id(folder)
    except ValueError:
        return "no vendor rule"
    return None


def extract(records, folder) -> dict:
    """One parsed file reduced to its model and, per question id, the first sample, date and sample count."""
    model = model_id(folder)
    if not isinstance(records, list) or not records:
        raise ValueError(f"{folder}: the file must hold a non-empty list of problems")
    cells = {}
    for i, rec in enumerate(records):
        if not isinstance(rec, dict):
            raise ValueError(f"{folder}: entry {i} is not an object")
        qid = rec.get("question_id")
        if not isinstance(qid, str) or not qid:
            raise ValueError(f"{folder}: entry {i} has no question_id string")
        if qid in cells:
            raise ValueError(f"{folder}: question_id {qid} repeats")
        date = rec.get("contest_date")
        m = DATE.fullmatch(date) if isinstance(date, str) else None
        if m is None:
            raise ValueError(f"{folder}: question_id {qid}: contest_date {date!r} is not a date")
        graded = rec.get("graded_list")
        if not isinstance(graded, list) or not graded or not all(isinstance(g, bool) for g in graded):
            raise ValueError(f"{folder}: question_id {qid}: graded_list must be a non-empty list of booleans")
        cells[qid] = {"correct": graded[0], "contest_date": m.group(1), "samples": len(graded)}
    return {"folder": folder, "model": model, "cells": dict(sorted(cells.items()))}


def convert(extracts) -> tuple:
    """Rows over the question ids every extract has, sorted by (item, model), and a report."""
    if not isinstance(extracts, (list, tuple)) or not extracts:
        raise ValueError("extracts must be a non-empty list or tuple")
    by_model = {}
    for ex in extracts:
        if ex["model"] in by_model:
            raise ValueError(f"two files give model {ex['model']}")
        by_model[ex["model"]] = ex
    dates = {}
    for model in sorted(by_model):
        for qid, cell in by_model[model]["cells"].items():
            if dates.setdefault(qid, cell["contest_date"]) != cell["contest_date"]:
                raise ValueError(f"question_id {qid} has contest dates {dates[qid]} and {cell['contest_date']}")
    models = sorted(by_model)
    common = set(by_model[models[0]]["cells"])
    for model in models[1:]:
        common &= set(by_model[model]["cells"])
    items = sorted(common)
    if not items:
        raise ValueError("no question id is common to every file")
    rows = [{"task": TASK, "item": qid, "model": model, "correct": by_model[model]["cells"][qid]["correct"], "cost_usd": 0.0}
            for qid in items for model in models]
    report = {
        "models": models,
        "task": TASK,
        "items": len(items),
        "contest_dates": [min(dates[q] for q in items), max(dates[q] for q in items)],
        "dropped_not_common": {m: len(by_model[m]["cells"]) - len(items) for m in models},
        "samples": {m: sorted({c["samples"] for c in by_model[m]["cells"].values()}) for m in models},
        "rows": len(rows),
    }
    return rows, report


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "livecodebench"


def verify(path, size: int, sha256: str) -> None:
    path = Path(path)
    if path.stat().st_size != size:
        raise ValueError(f"{path.name}: size {path.stat().st_size}, expected {size}")
    digest = hashlib.sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1 << 20), b""):
            digest.update(block)
    if digest.hexdigest() != sha256:
        raise ValueError(f"{path.name}: sha256 {digest.hexdigest()}, expected {sha256}")


def fetch(cache_dir=None) -> Path:
    """Return the cache folder once every file in FILES is in it and verified."""
    root = Path(cache_dir) if cache_dir is not None else default_cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    for name, (size, sha256) in FILES.items():
        dest = root / name
        if dest.exists():
            verify(dest, size, sha256)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        part = dest.with_name(dest.name + ".part")
        try:
            try:
                with urllib.request.urlopen(BASE_URL + urllib.parse.quote(name), timeout=TIMEOUT) as resp, open(part, "wb") as out:
                    for block in iter(lambda: resp.read(1 << 20), b""):
                        out.write(block)
            except ValueError:
                raise
            except Exception as exc:
                raise OSError(f"{name}: download failed: {exc}") from exc
            verify(part, size, sha256)
            part.replace(dest)
        finally:
            if part.exists():
                part.unlink()
    return root


def read_file(path):
    """One UTF-8 JSON file; invalid UTF-8, invalid JSON, nesting too deep or a number past the int-string
    digit limit is a ValueError naming it."""
    try:
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    except (ValueError, RecursionError) as exc:  # JSONDecodeError, UnicodeDecodeError and the digit limit's error
        raise ValueError(f"{Path(path).name}: not valid UTF-8 JSON ({type(exc).__name__}: {exc})") from exc


def write_jsonl(rows, path) -> None:
    with open(path, "w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps(row) + "\n")


class _Parser(argparse.ArgumentParser):
    def error(self, message):
        raise ValueError(message)


def print_report(text: str) -> None:
    """Print `text` to stdout and flush it. After a BrokenPipeError, point the stdout file descriptor at
    os.devnull and re-raise: the failed flush leaves the bytes in the stdout buffer, and the interpreter's
    own flush at exit would try them again and fail with two more stderr lines and exit status 120
    (DESIGN 13.11 v1.150; the Python `signal` module docs' note on SIGPIPE)."""
    try:
        print(text, flush=True)
    except BrokenPipeError:
        _stdout_to_devnull()
        raise


def _stdout_to_devnull() -> None:
    """Point the stdout file descriptor at os.devnull; a stdout with none (a stand-in object), or one the
    redirect fails on, is left as it is."""
    try:
        fd = sys.stdout.fileno()
        devnull = os.open(os.devnull, os.O_WRONLY)
    except (AttributeError, OSError, ValueError):  # io.UnsupportedOperation is both of the last two
        return
    try:
        os.dup2(devnull, fd)
    except OSError:
        pass
    finally:
        os.close(devnull)


def _check_out(value, option="--out"):
    """The path an output option names, or a ValueError for a bad one, checked before any download (12.14 v1.174)."""
    if value.rsplit("/", 1)[-1] in ("", ".", ".."):
        raise ValueError(f"{option} must end in a file name, got {value!r}")
    out = Path(value)
    for path in (out, out.with_name(out.name + ".part")):
        if path.is_dir():  # a link to a folder included
            raise ValueError(f"{option} {value!r}: {str(path)!r} is a folder")
    if not out.parent.is_dir():
        raise ValueError(f"{option} {value!r}: folder {str(out.parent)!r} does not exist")
    return out


def main(argv=None) -> int:
    parser = _Parser(prog="convert.py", description="LiveCodeBench submissions to an outcome matrix")
    parser.add_argument("--out", required=True, help="output JSONL path")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {default_cache_dir()})")
    try:
        args = parser.parse_args(argv)
        out = _check_out(args.out)
        part = out.with_name(out.name + ".part")
        try:  # on any failure from here on, <out>.part goes, a stale one from an earlier run included
            root = fetch(args.cache)
            extracts = [extract(read_file(root / name), name.split("/")[0]) for name in FILES]
            rows, report = convert(extracts)
            write_jsonl(rows, part)
            # print before the rename, so a write to stdout that fails leaves --out as it was (v1.94)
            print_report(json.dumps(report, indent=2))
            part.replace(out)
        finally:
            part.unlink(missing_ok=True)
    except (ValueError, OSError) as exc:
        msg = str(exc).replace("\r", "\\r").replace("\n", "\\n")
        print(f"error: {msg}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
