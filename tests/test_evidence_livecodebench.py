"""LiveCodeBench converter contract (DESIGN 12.16, v1.60 and v1.61), written before the converter and kept as its tests.

The converter is a standard-library script outside the package (``evidence/livecodebench/convert.py``),
so it is loaded from its path by an autouse fixture. Every test uses small synthetic problem lists
shaped like a submission file (a JSON list of problem objects), except the evidence README tests,
which read the committed README, and the last, which reads the pinned files only when all 67 are
already in the default cache and skips otherwise (CI never downloads them).
"""

import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import random
import urllib.request
from pathlib import Path

import pytest

from model_routing import evaluate, outcomes_from_rows

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "livecodebench" / "convert.py"
EVIDENCE_README = ROOT / "evidence" / "livecodebench" / "README.md"
REVISION = "6ca212e9c2039373f6e5069d37ffa9db66e23736"
BASE_URL = f"https://raw.githubusercontent.com/LiveCodeBench/submissions/{REVISION}/"
PINNED = [
    ('Claude-3-Haiku/Scenario.codegeneration_10_0.2_eval_all.json', 21175537, 'd4dde49c99058f4fac9e9faeb739c59e3024b062d29c1fa8a875a92ef5e15edb', 'anthropic/claude-3-haiku'),
    ('Claude-3.5-Sonnet-20240620/Scenario.codegeneration_10_0.2_eval_all.json', 17342354, '8227e0e70d72d808bf65809f905052f36ebb82e504b69908fb31d7e7ac7f3a92', 'anthropic/claude-3.5-sonnet-20240620'),
    ('Claude-3.5-Sonnet-20241022/Scenario.codegeneration_10_0.2_eval_all.json', 29896047, '1b900ac47a147006ea2f8c258d60a6ee9dd8dff378ebcd926f322466179d99b1', 'anthropic/claude-3.5-sonnet-20241022'),
    ('Claude-3.7-Sonnet/Scenario.codegeneration_1_0.2_eval_all.json', 40780648, '1b8334f503ad2d13eaa2b3ea15b46a289706276d40e96f3274442e0d8184620f', 'anthropic/claude-3.7-sonnet'),
    ('Claude-Opus-4 (Thinking)/Scenario.codegeneration_1_0.2_eval_all.json', 15447145, 'd9b959036c9952161dcbdd515a225a2d2a03c747469dd50ac2b6561d42b04714', 'anthropic/claude-opus-4-thinking'),
    ('Claude-Opus-4/Scenario.codegeneration_1_0.2_eval_all.json', 5707347, 'a75e46288b0457ebd2ce7fee3f06d69fdeda4b00742defe3b13c46887892db91', 'anthropic/claude-opus-4'),
    ('Claude-Sonnet-4 (Thinking)/Scenario.codegeneration_1_0.2_eval_all.json', 19133477, '339db7aab7be74a509e25fcf75bc42adff3f6e4829d8d5a3359864de0e1d8188', 'anthropic/claude-sonnet-4-thinking'),
    ('Claude-Sonnet-4/Scenario.codegeneration_1_0.2_eval_all.json', 6096105, 'caa412a80e12e51bd2737a99c557691241b5acf2f4e404f2db0556417efcf600', 'anthropic/claude-sonnet-4'),
    ('Codestral-Latest/Scenario.codegeneration_10_0.2_eval_all.json', 16698489, 'f3b7ad09528d9046451b5fe0e3f67f26912c5fd4d6fdf0db22ba5b0af0d0cd2b', 'mistralai/codestral-latest'),
    ('DSCoder-1.3b-Ins/Scenario.codegeneration_10_0.2_eval_all.json', 8972584, 'f78ad8f239ff5144c81709ecab72dca1eee19b40b21ba1a2fcf92501c8dae017', 'deepseek/dscoder-1.3b-ins'),
    ('DSCoder-33b-Ins/Scenario.codegeneration_10_0.2_eval_all.json', 10124550, 'af10caa8fe47deaa745f410768864f8813e234c02872b247cb9c076dd872575f', 'deepseek/dscoder-33b-ins'),
    ('DSCoder-6.7b-Ins/Scenario.codegeneration_10_0.2_eval_all.json', 11257116, 'f972642519aa1e346f73dffe6f0b2387b406a1548d216bc84fe9e19c7e53a127', 'deepseek/dscoder-6.7b-ins'),
    ('DeepCoder-14B-Preview/Scenario.codegeneration_10_0.2_eval_all.json', 51800914, '52870bf12c83f9245cccb41d5b65a65fd8f9d18895063a1cde3354346f93b048', 'agentica/deepcoder-14b-preview'),
    ('DeepSeek-R1-0528/Scenario.codegeneration_10_0.6_eval_all.json', 55720447, '403fb6060512b10766fba5e1c16ba320191355e8d7e920f01e5be69bcde25231', 'deepseek/deepseek-r1-0528'),
    ('DeepSeek-R1-Lite-Preview/Scenario.codegeneration_10_0.2_eval_all.json', 36340580, 'd432c2668f49d8baf1ec512d73ade2a8133e5108043d6e9a1a44912bb3e74f5e', 'deepseek/deepseek-r1-lite-preview'),
    ('DeepSeek-R1-Preview/Scenario.codegeneration_10_0.2_eval_all.json', 37086048, '7a363a772c47d00a63db99d0f444e28e9ec6f0f8f26adc50b9190fc908332a99', 'deepseek/deepseek-r1-preview'),
    ('DeepSeek-V3/Scenario.codegeneration_10_0.2_eval_all.json', 36242668, '88548117b84bf567fdadb159cfc65f9c0a6bf7da8b2fe5679829c95334abd661', 'deepseek/deepseek-v3'),
    ('EXAONE-4.0-32B/Scenario.codegeneration_4_0.6_eval_all.json', 23877444, '019bc78e1685fbe411149cb6c69244d2bafe04304cfd72f60bab3c5b27b3dc6f', 'lgai/exaone-4.0-32b'),
    ('GPT-4-0613/Scenario.codegeneration_10_0.2_eval_all.json', 9600263, 'bd0ab24c9f8da86bf010f90e55d052ecf513922649c2f181b742d21cbfa37189', 'openai/gpt-4-0613'),
    ('GPT-4-Turbo-1106/Scenario.codegeneration_10_0.2_eval_all.json', 14387341, '73e2e8e25b92fe23a578d3fe6c29f83a48dc5dbee9c3d5e7d907f75f7f0ac650', 'openai/gpt-4-turbo-1106'),
    ('GPT-4-Turbo-2024-04-09/Scenario.codegeneration_10_0.2_eval_all.json', 28049953, 'fc46d2a4fdd42caa0f7ec30366c318ddcded2334a0b3128752b5f15c4793bf97', 'openai/gpt-4-turbo-2024-04-09'),
    ('GPT-4O-2024-05-13/Scenario.codegeneration_10_0.2_eval_all.json', 17904865, '072871af75fcb2b00efad273372f7f701363576f1e2cd2f57dc19c97b3f2d362', 'openai/gpt-4o-2024-05-13'),
    ('GPT-4O-2024-08-06/Scenario.codegeneration_10_0.2_eval_all.json', 32778775, '5d072bd884756779f22f6e9239b142f82ff87dd2d76f7647f732be2a55efb0ec', 'openai/gpt-4o-2024-08-06'),
    ('GPT-4O-mini-2024-07-18/Scenario.codegeneration_10_0.2_eval_all.json', 24796617, '37b922fae87f97c957e9a2554ddabdaa777d876758bad86e7aabb2f26ebf4972', 'openai/gpt-4o-mini-2024-07-18'),
    ('Gemini-2.5-Flash-04-17/Scenario.codegeneration_1_0.2_eval_all.json', 9298858, '2b81892984e212d9937942aafb9e478e985600e50114d7fa86fba2b5f53486cf', 'google/gemini-2.5-flash-04-17'),
    ('Gemini-2.5-Flash-05-20/Scenario.codegeneration_1_0.2_eval_all.json', 16026288, '75957e8b682cf4bf75f4b24953038f7e374c0f9c592d8f7577117d7ea060057c', 'google/gemini-2.5-flash-05-20'),
    ('Gemini-2.5-Pro-03-25/Scenario.codegeneration_1_0.2_eval_all.json', 12182339, 'a336ec7c2d9d83fa331c43633be5abc08817441cf2d9d18d362b7924ea610b29', 'google/gemini-2.5-pro-03-25'),
    ('Gemini-2.5-Pro-05-06/Scenario.codegeneration_1_0.2_eval_all.json', 15665903, '7e0cae96e609e085beeb66d56b74e9186d948c65c803427f1a5d022401982026', 'google/gemini-2.5-pro-05-06'),
    ('Gemini-2.5-Pro-06-05/Scenario.codegeneration_1_0.2_eval_all.json', 13420908, '19be5460eda197621738c871cd496d79b1d1fa3c653a5a7742fd4985abfd2d39', 'google/gemini-2.5-pro-06-05'),
    ('Gemini-Exp-1206/Scenario.codegeneration_10_0.2_eval_all.json', 19858737, '5555e4cde78f48a6b6ee3391964bb9b9d379a61b0bd9f71137548c5fcddc7b71', 'google/gemini-exp-1206'),
    ('Gemini-Flash-1.5-002/Scenario.codegeneration_10_0.2_eval_all.json', 15723216, '46150890d210451f966408536d2cdf2434f044811ad85faff496e4b4d6f0e0b5', 'google/gemini-flash-1.5-002'),
    ('Gemini-Flash-2.0-Exp/Scenario.codegeneration_1_0.2_eval_all.json', 6955936, '9c0b4f222c428d627ae8fee677a031b203b30e45a396a1c41ad8358ebb5bc42c', 'google/gemini-flash-2.0-exp'),
    ('Gemini-Flash-2.0-Thinking-01-21/Scenario.codegeneration_1_0.2_eval_all.json', 20903075, '227f75adcf0502e1942b9178b353f0665617a86ce525e64fde26f5a4330574b1', 'google/gemini-flash-2.0-thinking-01-21'),
    ('Gemini-Flash-2.0-Thinking-12-19/Scenario.codegeneration_1_0.2_eval_all.json', 20546068, '72e58004bd0f09835bb3f2600c41c3bce2e1ad815662ee9a4a294185d543812a', 'google/gemini-flash-2.0-thinking-12-19'),
    ('Gemini-Flash-2.0-Thinking/Scenario.codegeneration_10_0.2_eval_all.json', 23667385, 'd79024201d8a77db19135d94a1812ffde2c02ffb7ed7ef1d53f69f8018c61687', 'google/gemini-flash-2.0-thinking'),
    ('Gemini-Pro-1.5-002/Scenario.codegeneration_10_0.2_eval_all.json', 15887371, 'c6650177f41ab56596e5085077a2edf1444170bc1a804c447cd2fd900449e1ba', 'google/gemini-pro-1.5-002'),
    ('Grok-3-Mini (High)/Scenario.codegeneration_1_0.4_eval_all.json', 4361019, '834f0311cc6d0610b9c1840e9cb26a80ced4ef08b3400ee2926881e8036a4fab', 'xai/grok-3-mini-high'),
    ('Kimi-k1.6-IOI-high/Scenario.codegeneration_1_1.0_eval_all.json', 4099066, 'ef3a96fce0c8fd83417bc11a55200c3159d39b1936960959ebb67f15b0bd9b58', 'moonshotai/kimi-k1.6-ioi-high'),
    ('Kimi-k1.6-IOI/Scenario.codegeneration_10_0.8_eval_all.json', 30401298, '59583d3fbc343920e48fa7c9c257e0ec5e564c152e066c0b6560546a061b8013', 'moonshotai/kimi-k1.6-ioi'),
    ('LLama3.3-70b-Ins/Scenario.codegeneration_10_0.2_eval_all.json', 16031611, '91708bc6db33d239ad4b8c75424448035263b73b2dc44a428f2b1300affc4071', 'meta-llama/llama3.3-70b-ins'),
    ('Llama-3_1-Nemotron-Nano-8B-v1/Scenario.codegeneration_1_eval_all.json', 19558899, 'cf3729eaf6e9b5164951fbf82506ce05ca95f52d2130c3c9ec3955958913aadf', 'nvidia/llama-3_1-nemotron-nano-8b-v1'),
    ('Llama-3_1-Nemotron-Ultra-253B-v1/Scenario.codegeneration_1_eval_all.json', 5107907, '9e31c5feba8b56bf7515684c415c0c7e5e1f31d3a2f896f24ef9fabe66d8dba3', 'nvidia/llama-3_1-nemotron-ultra-253b-v1'),
    ('MetaStone-L1-7B/Scenario.codegeneration_10_0.6_eval_all.json', 54754997, '499f395db1cba305790446a6251c6b9822d78b757ca447d29e41b9dd4b338219', 'metastone/metastone-l1-7b'),
    ('Mistral-Large/Scenario.codegeneration_10_0.2_eval_all.json', 20707461, '73a67f7b514f6fb94bdbe0a7762d4d7e9daeacf8d155ae81a53a8e2719ea0469', 'mistralai/mistral-large'),
    ('O1-2024-12-17 (High)/Scenario.codegeneration_1_0.2_eval_all.json', 5693027, '52c10c62c5408faeda5cedac221b71251564dd307bc61512df28e33aa902e642', 'openai/o1-2024-12-17-high'),
    ('O1-2024-12-17 (Low)/Scenario.codegeneration_1_0.2_eval_all.json', 6554308, '96cf54b1f7b19d8d202641e1915aa5ef663c06811ed06a99893123b79f077234', 'openai/o1-2024-12-17-low'),
    ('O1-2024-12-17 (Med)/Scenario.codegeneration_1_0.2_eval_all.json', 6342959, '2cfef88d6130d0700dc75e8a9470680dff81fffce4e9d78d88600e99125e9d46', 'openai/o1-2024-12-17-med'),
    ('O1-Mini-2024-09-12/Scenario.codegeneration_1_0.2_eval_all.json', 3636170, '9e7c9d729cc464af3e532af9faa1ec8ea993839567e4c952bfa7fb92e094d78b', 'openai/o1-mini-2024-09-12'),
    ('O1-Preview-2024-09-12/Scenario.codegeneration_1_0.2_eval_all.json', 3799086, '916568014b99be062ca202efb6390fb8cfb8dc750ad4d88611df4cd44c6bc84e', 'openai/o1-preview-2024-09-12'),
    ('O3 (High)/Scenario.codegeneration_1_0.2_eval_all.json', 5316324, 'a7c900595d6ca6eba133e03e9e4fd24b0047a87e8a8302935ba2b83f0b834ff7', 'openai/o3-high'),
    ('O3-Mini-2025-01-31 (High)/Scenario.codegeneration_1_0.2_eval_all.json', 7234096, '37440ebbcbb947c5bf8b19eab872f1e0386013e00fcabf6a2eb074c56ca9774d', 'openai/o3-mini-2025-01-31-high'),
    ('O3-Mini-2025-01-31 (Low)/Scenario.codegeneration_1_0.2_eval_all.json', 6836877, '4f4bed0e765eb9ff8fbc909a78225f9c40c41775aeae670e5ef9ddd42a24d3b5', 'openai/o3-mini-2025-01-31-low'),
    ('O3-Mini-2025-01-31 (Med)/Scenario.codegeneration_1_0.2_eval_all.json', 7150157, '428773c6bf3445ee9ca2f7cadaea18a6e328e82ce68e5ef6d0e19a0ba5243f42', 'openai/o3-mini-2025-01-31-med'),
    ('O4-Mini (High)/Scenario.codegeneration_1_0.2_eval_all.json', 5566694, '533249d34528071b3cd4ca50c756b61518a37cc90f6d4b3a931ca9dce421b06b', 'openai/o4-mini-high'),
    ('O4-Mini (Low)/Scenario.codegeneration_1_0.2_eval_all.json', 5289377, '1ccf62bb019c8a9176bfc7e1625b36ad4f82a1029d636fe949c4b8133bbcea59', 'openai/o4-mini-low'),
    ('O4-Mini (Medium)/Scenario.codegeneration_1_0.2_eval_all.json', 5449673, 'd045f8bcdfec799803fa8734f9a51aa2c589f0759ff509470320cde550b33ed3', 'openai/o4-mini-medium'),
    ('OpenReasoning-Nemotron-32B/Scenario.codegeneration_10_0.6_eval_all.json', 22370156, '5aec11207b7d6ff37f6220513e5fcc9df8a6d837bc46a0163f1ff95ae0955e61', 'nvidia/openreasoning-nemotron-32b'),
    ('QwQ-32B-Preview/Scenario.codegeneration_1_0.2_eval_all.json', 31532692, '7a6ac226b050b3d29e7cceb900c80a6c13872a87099be72b1726b747c7962b8b', 'qwen/qwq-32b-preview'),
    ('QwQ-32B_temp/Scenario.codegeneration_1_0.2_eval_all.json', 44575245, '616906647f8c31136f1bb2e8924a0fe9587ef085ee77781c963f029d738c6fe6', 'qwen/qwq-32b_temp'),
    ('QwQ-Max-Preview/Scenario.codegeneration_1_0.6_eval_all.json', 30801371, 'dd3c3c428ef04e07892cd2a1308cfd1cadcce61e3f37454076b6813d854e0a62', 'qwen/qwq-max-preview'),
    ('Qwen2-Ins-72B/Scenario.codegeneration_10_0.2_eval_all.json', 12353225, '5ce1e7b71388887353264034a15425c2debabfc775a18f231aea215ceb388381', 'qwen/qwen2-ins-72b'),
    ('Qwen2.5-Coder-Ins-32B/Scenario.codegeneration_10_0.2_eval_all.json', 15265370, 'b3cee20f0bfcfeccf4350c75244eaeb9ab73385a732d433629845177d6231822', 'qwen/qwen2.5-coder-ins-32b'),
    ('Qwen2.5-Coder-Ins-7B/Scenario.codegeneration_10_0.2_eval_all.json', 10858879, '586707158f8d1648964f54f0290dc42c94806b12684ea03b537202008170c992', 'qwen/qwen2.5-coder-ins-7b'),
    ('Qwen2.5-Ins-32B/Scenario.codegeneration_10_0.2_eval_all.json', 12135021, '39c766b34f6a412fac0c9e382bed7ea5d2b8a45874b67d6bb998455edc6a183c', 'qwen/qwen2.5-ins-32b'),
    ('Qwen2.5-Ins-72B/Scenario.codegeneration_10_0.2_eval_all.json', 12705443, '6555e98ea20a4aa5d2ac2439cc62065001280366e11815c0c29f32fe31228f68', 'qwen/qwen2.5-ins-72b'),
    ('Qwen2.5-Ins-7B/Scenario.codegeneration_10_0.2_eval_all.json', 10517624, 'b9b11acc6b1beadcb25067000bb619cbe1a7c53c859882606d04550cdb018179', 'qwen/qwen2.5-ins-7b'),
    ('Qwen3-235B-A22B/Scenario.codegeneration_1_0.6_eval_all.json', 45188691, '4b64e46c8f1a3e7ae14906b28e685624f05becaafe6422be7743f8a04c77b7b9', 'qwen/qwen3-235b-a22b'),
]
DROPPED = {
    "AzeroGPT-64b/Scenario.codegeneration_10_0.2_eval_all.json": "no vendor rule",
    "DeepSeek-V3 copy/Scenario.codegeneration_10_0.2_eval_all.json": "copy of another folder",
    "Gemini-Flash-2.0-Exp (N=10)/Scenario.codegeneration_10_0.2_eval_all.json": "10-sample run",
    "Gemini-Flash-2.0-Exp (N=10)/Scenario.codegeneration_1_0.2_eval_all.json": "10-sample run",
    "O1-2024-12-17 (Low)_prompt_old/Scenario.codegeneration_1_0.2_eval_all.json": "superseded prompt",
    "XBai-o4-medium/Scenario.codegeneration_1_0.6_eval_all.json": "no vendor rule",
}
# bytes and sha256 of the 6 dropped files at REVISION, for the evidence README table (v1.61);
# the converter never downloads them
DROPPED_PINS = {
    "AzeroGPT-64b/Scenario.codegeneration_10_0.2_eval_all.json": (19352799, "f2afe8bf8937d36fab7a7a95e426f6a845be3485f941610eda4e94126784748b"),
    "DeepSeek-V3 copy/Scenario.codegeneration_10_0.2_eval_all.json": (28351686, "06e7b8340903a1154fea69cf63a7deed78ef575f72a95b5d16537a6b6436b142"),
    "Gemini-Flash-2.0-Exp (N=10)/Scenario.codegeneration_10_0.2_eval_all.json": (23790224, "0eeba1e8eb984976c9e4dafa03c1f000cebf6d646c5f1e4690b3f0e2f3a7a3f8"),
    "Gemini-Flash-2.0-Exp (N=10)/Scenario.codegeneration_1_0.2_eval_all.json": (6955936, "9c0b4f222c428d627ae8fee677a031b203b30e45a396a1c41ad8358ebb5bc42c"),
    "O1-2024-12-17 (Low)_prompt_old/Scenario.codegeneration_1_0.2_eval_all.json": (4932645, "81104861ab7d19b18cc8581187a30bf93174b7479518282645960225d05acc55"),
    "XBai-o4-medium/Scenario.codegeneration_1_0.6_eval_all.json": (36137643, "8f80d42f61beee24468a744839df254888f9ce8192bd7563a3d530f515795cc8"),
}
EXTRACT_KEYS = ["folder", "model", "cells"]
CELL_KEYS = ["correct", "contest_date", "samples"]
ROW_KEYS = ["task", "item", "model", "correct", "cost_usd"]
REPORT_KEYS = ["models", "task", "items", "contest_dates", "dropped_not_common", "samples", "rows"]
STDLIB = {"argparse", "hashlib", "json", "re", "sys", "urllib", "pathlib"}


def load_cv():
    if not SCRIPT.is_file():
        raise ModuleNotFoundError(f"no converter at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("lcb_convert", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def cv():
    return load_cv()


def problem(qid, graded=(True,), date="2024-01-02T00:00:00", **extra):
    rec = {"question_title": "t", "question_content": "problem text", "platform": "atcoder",
           "question_id": qid, "contest_id": "c", "contest_date": date, "starter_code": "",
           "difficulty": "easy", "output_list": ["code out"] * len(graded),
           "code_list": ["code"] * len(graded), "graded_list": list(graded),
           "pass@1": sum(graded) / len(graded) if graded else 0.0, "metadata": ["{}"] * len(graded)}
    rec.update(extra)
    return rec


# --- source pins -------------------------------------------------------------------------

def test_source_constants(cv):
    assert cv.REVISION == REVISION
    assert cv.LICENCE == "MIT"
    assert cv.BASE_URL == BASE_URL
    assert cv.TASK == "code_generation"


def test_files_pinned_in_path_order(cv):
    assert list(cv.FILES) == [p for p, _, _, _ in PINNED]
    assert list(cv.FILES) == sorted(cv.FILES)
    for path, size, sha, _ in PINNED:
        assert cv.FILES[path] == (size, sha)
    assert len(cv.FILES) == 67
    assert sum(size for size, _ in cv.FILES.values()) == 1_233_548_121


def test_dropped_files_and_reasons(cv):
    assert cv.DROPPED == DROPPED
    assert list(cv.DROPPED) == sorted(cv.DROPPED)
    assert not set(cv.FILES) & set(cv.DROPPED)
    assert len(cv.FILES) + len(cv.DROPPED) == 73
    for path, reason in DROPPED.items():
        assert cv.skip_reason(path.split("/")[0]) == reason
    for path, _, _, _ in PINNED:
        assert cv.skip_reason(path.split("/")[0]) is None


def test_one_file_per_kept_folder(cv):
    folders = [p.split("/")[0] for p in cv.FILES]
    assert len(set(folders)) == len(folders)


def test_default_cache_dir(cv):
    assert cv.default_cache_dir() == Path.home() / ".cache" / "ai-model-routing-evidence" / "livecodebench"


def test_standard_library_only():
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            names.add(node.module.split(".")[0])
    assert names <= STDLIB, names - STDLIB


# --- model ids ---------------------------------------------------------------------------

@pytest.mark.parametrize("path,model", [(p, m) for p, _, _, m in PINNED])
def test_model_id_of_every_kept_folder(cv, path, model):
    assert cv.model_id(path.split("/")[0]) == model


def test_model_ids_unique(cv):
    ids = [cv.model_id(p.split("/")[0]) for p in cv.FILES]
    assert len(set(ids)) == len(ids) == 67


@pytest.mark.parametrize("folder,expected", [
    ("O3 (High)", "openai/o3-high"),
    ("O1-Mini-2024-09-12", "openai/o1-mini-2024-09-12"),
    ("GPT-4O-mini-2024-07-18", "openai/gpt-4o-mini-2024-07-18"),
    ("Llama-3_1-Nemotron-Nano-8B-v1", "nvidia/llama-3_1-nemotron-nano-8b-v1"),
    ("LLama3.3-70b-Ins", "meta-llama/llama3.3-70b-ins"),
    ("Claude-Opus-4 (Thinking)", "anthropic/claude-opus-4-thinking"),
])
def test_model_id_rule(cv, folder, expected):
    assert cv.model_id(folder) == expected


@pytest.mark.parametrize("folder", ["", None, 7, "AzeroGPT-64b", "XBai-o4-medium", "Oracle-1",
                                    "O5-Mini", "a/Claude-3", "Claude-3/x", "Claude-3 (\u00dcnicode)",
                                    "Claude-3 \u00e9", "Claude-3-\u212a", "GPT-4-\u212aelvin"])
def test_model_id_refuses(cv, folder):
    with pytest.raises(ValueError):
        cv.model_id(folder)


@pytest.mark.parametrize("folder,reason", [
    ("DeepSeek-V3 copy", "copy of another folder"),
    ("Gemini-Flash-2.0-Exp (N=10)", "10-sample run"),
    ("O1-2024-12-17 (Low)_prompt_old", "superseded prompt"),
    ("AzeroGPT-64b", "no vendor rule"),
    ("Claude-3-Haiku", None),
    ("QwQ-32B_temp", None),
    ("Gemini-Flash-2.0-Exp (N=10) copy", "copy of another folder"),
    ("O1-2024-12-17 (N=10)_prompt_old", "10-sample run"),
    ("AzeroGPT-64b_prompt_old", "superseded prompt"),
    ("AzeroGPT-64b copy", "copy of another folder"),
])
def test_skip_reason(cv, folder, reason):
    assert cv.skip_reason(folder) == reason


@pytest.mark.parametrize("folder", ["", None, 7])
def test_skip_reason_refuses_non_names(cv, folder):
    with pytest.raises(ValueError):
        cv.skip_reason(folder)


# --- extract -----------------------------------------------------------------------------

def test_extract_shape_and_first_sample(cv):
    recs = [problem("b2", graded=(False, True, True), date="2024-02-03T00:00:00"),
            problem("a1", graded=(True,), date="2023-05-07"),
            problem("c3", graded=(True, False, False, False))]
    ex = cv.extract(recs, "Claude-3-Haiku")
    assert list(ex) == EXTRACT_KEYS
    assert ex["folder"] == "Claude-3-Haiku" and ex["model"] == "anthropic/claude-3-haiku"
    assert list(ex["cells"]) == ["a1", "b2", "c3"]
    assert ex["cells"]["a1"] == {"correct": True, "contest_date": "2023-05-07", "samples": 1}
    assert ex["cells"]["b2"] == {"correct": False, "contest_date": "2024-02-03", "samples": 3}
    assert ex["cells"]["c3"]["correct"] is True and ex["cells"]["c3"]["samples"] == 4
    for cell in ex["cells"].values():
        assert list(cell) == CELL_KEYS


def test_extract_keeps_no_problem_text_or_code(cv):
    ex = cv.extract([problem("a1")], "Claude-3-Haiku")
    blob = json.dumps(ex)
    for word in ("problem text", "code out", "question_content", "code_list", "output_list", "atcoder", "easy"):
        assert word not in blob


def test_extract_does_not_modify_input(cv):
    recs = [problem("a1"), problem("b2", graded=(False,))]
    before = copy.deepcopy(recs)
    cv.extract(recs, "Claude-3-Haiku")
    assert recs == before


@pytest.mark.parametrize("records", [
    {}, [], "x", None,
    [1],
    [problem("a1", question_id=None)],
    [problem("a1", question_id="")],
    [problem("a1", question_id=5)],
    [problem("a1"), problem("a1")],
    [problem("a1", date="2024/01/02")],
    [problem("a1", date="")],
    [problem("a1", date=None)],
    [problem("a1", date="2024-01-02 00:00:00")],
    [problem("a1", graded=())],
    [problem("a1", graded_list=None)],
    [problem("a1", graded_list="True")],
    [problem("a1", graded_list=[1])],
    [problem("a1", graded_list=[True, None])],
    [problem("a1", graded_list=[True, 0])],
])
def test_extract_refuses(cv, records):
    with pytest.raises(ValueError):
        cv.extract(records, "Claude-3-Haiku")


def test_extract_refuses_missing_keys(cv):
    for key in ("question_id", "contest_date", "graded_list"):
        rec = problem("a1")
        del rec[key]
        with pytest.raises(ValueError):
            cv.extract([rec], "Claude-3-Haiku")


def test_extract_messages_name_folder_and_question(cv):
    with pytest.raises(ValueError, match=r"Claude-3-Haiku.*q9"):
        cv.extract([problem("a1"), problem("q9", graded_list=[1])], "Claude-3-Haiku")
    with pytest.raises(ValueError, match=r"Claude-3-Haiku.*q9"):
        cv.extract([problem("q9"), problem("q9")], "Claude-3-Haiku")


def test_extract_refuses_folder_without_vendor(cv):
    with pytest.raises(ValueError):
        cv.extract([problem("a1")], "AzeroGPT-64b")


# --- convert -----------------------------------------------------------------------------

def three_models(cv):
    a = cv.extract([problem("p1"), problem("p2", graded=(False,)), problem("p3", date="2024-03-01")], "Claude-3-Haiku")
    b = cv.extract([problem("p2"), problem("p1", graded=(False, True)), problem("p4", date="2025-01-01")], "O3 (High)")
    c = cv.extract([problem("p1", graded=(True,) * 10), problem("p2"), problem("p3", date="2024-03-01")], "Gemini-Exp-1206")
    return [a, b, c]


def test_convert_rows_and_report(cv):
    rows, report = cv.convert(three_models(cv))
    assert [list(r) for r in rows] == [ROW_KEYS] * 6
    assert [(r["item"], r["model"]) for r in rows] == [
        ("p1", "anthropic/claude-3-haiku"), ("p1", "google/gemini-exp-1206"), ("p1", "openai/o3-high"),
        ("p2", "anthropic/claude-3-haiku"), ("p2", "google/gemini-exp-1206"), ("p2", "openai/o3-high")]
    assert [r["correct"] for r in rows] == [True, True, False, False, True, True]
    assert all(r["task"] == "code_generation" for r in rows)
    assert all(type(r["cost_usd"]) is float and r["cost_usd"] == 0.0 for r in rows)
    assert list(report) == REPORT_KEYS
    assert report == {
        "models": ["anthropic/claude-3-haiku", "google/gemini-exp-1206", "openai/o3-high"],
        "task": "code_generation", "items": 2, "contest_dates": ["2024-01-02", "2024-01-02"],
        "dropped_not_common": {"anthropic/claude-3-haiku": 1, "google/gemini-exp-1206": 1, "openai/o3-high": 1},
        "samples": {"anthropic/claude-3-haiku": [1], "google/gemini-exp-1206": [1, 10], "openai/o3-high": [1, 2]},
        "rows": 6}


def test_convert_order_independent_and_input_unchanged(cv):
    exs = three_models(cv)
    before = copy.deepcopy(exs)
    first = cv.convert(exs)
    shuffled = list(exs)
    random.Random(4).shuffle(shuffled)
    assert cv.convert(shuffled) == first
    assert exs == before


def test_convert_contest_date_range(cv):
    a = cv.extract([problem("p1", date="2023-05-07"), problem("p2", date="2024-10-05")], "Claude-3-Haiku")
    b = cv.extract([problem("p2", date="2024-10-05T00:00:00"), problem("p1", date="2023-05-07T00:00:00")], "O3 (High)")
    _, report = cv.convert([a, b])
    assert report["contest_dates"] == ["2023-05-07", "2024-10-05"]
    assert report["dropped_not_common"] == {"anthropic/claude-3-haiku": 0, "openai/o3-high": 0}


@pytest.mark.parametrize("bad", ["none", "empty", "tuple-empty", "dup", "str", "dict"])
def test_convert_refuses(cv, bad):
    exs = three_models(cv)
    arg = {"none": None, "empty": [], "tuple-empty": (), "dup": exs + [exs[0]], "str": "x",
           "dict": {e["model"]: e for e in exs}}[bad]
    with pytest.raises(ValueError):
        cv.convert(arg)


def test_convert_accepts_a_tuple(cv):
    exs = three_models(cv)
    assert cv.convert(tuple(exs)) == cv.convert(exs)


def test_convert_refuses_conflicting_contest_dates(cv):
    a = cv.extract([problem("p1", date="2024-01-02")], "Claude-3-Haiku")
    b = cv.extract([problem("p1", date="2024-01-03")], "O3 (High)")
    with pytest.raises(ValueError, match="p1"):
        cv.convert([a, b])


def test_convert_refuses_no_common_item(cv):
    a = cv.extract([problem("p1")], "Claude-3-Haiku")
    b = cv.extract([problem("p2")], "O3 (High)")
    with pytest.raises(ValueError):
        cv.convert([a, b])


def test_rows_form_a_matrix_the_evaluator_accepts_in_cost_blind(cv):
    exs = []
    for k, folder in enumerate(["Claude-3-Haiku", "O3 (High)", "Gemini-Exp-1206"]):
        recs = [problem(f"q{i:03d}", graded=((i * (k + 2)) % 5 != 0,)) for i in range(80)]
        exs.append(cv.extract(recs, folder))
    rows, report = cv.convert(exs)
    result = evaluate(outcomes_from_rows(rows), bars=[0.7], seeds=range(3), flavors=("cost_blind",))
    assert result["config"]["flavors"] == ["cost_blind"]
    assert {c["flavor"] for c in result["cells"]} == {"cost_blind"}
    assert all(v == 0.0 for c in result["cells"] for v in c["cost_usd"].values())
    assert result["tasks"] == {"code_generation": {"items": 80, "models": report["models"]}}


# --- verify, fetch, read -----------------------------------------------------------------

def test_verify(cv, tmp_path):
    f = tmp_path / "a.json"
    f.write_bytes(b"[]")
    cv.verify(f, 2, hashlib.sha256(b"[]").hexdigest())
    with pytest.raises(ValueError, match="a.json"):
        cv.verify(f, 3, hashlib.sha256(b"[]").hexdigest())
    with pytest.raises(ValueError, match="a.json"):
        cv.verify(f, 2, "0" * 64)


def fake_files(monkeypatch, cv, contents):
    files = {name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in sorted(contents.items())}
    monkeypatch.setattr(cv, "FILES", files)
    return files


def test_fetch_downloads_quoted_urls_into_folders(cv, monkeypatch, tmp_path):
    data = {"O3 (High)/S_1.json": b"[1]", "Claude-3-Haiku/S_10.json": b"[2]"}
    fake_files(monkeypatch, cv, data)
    seen = []

    def urlopen(url, timeout=None):
        seen.append((url, timeout))
        name = [n for n in data if url.endswith(urllib.request.quote(n))][0]
        return io.BytesIO(data[name])

    monkeypatch.setattr(cv.urllib.request, "urlopen", urlopen)
    assert cv.fetch(tmp_path) == tmp_path
    assert seen == [(BASE_URL + "Claude-3-Haiku/S_10.json", 60), (BASE_URL + "O3%20%28High%29/S_1.json", 60)]
    for name, body in data.items():
        assert (tmp_path / name).read_bytes() == body
    assert not list(tmp_path.rglob("*.part"))
    seen.clear()
    cv.fetch(tmp_path)
    assert seen == []


def test_fetch_bad_present_file_is_kept_and_refused(cv, monkeypatch, tmp_path):
    fake_files(monkeypatch, cv, {"A/x.json": b"[1]"})
    (tmp_path / "A").mkdir()
    (tmp_path / "A" / "x.json").write_bytes(b"[9]")
    with pytest.raises(ValueError, match="x.json"):
        cv.fetch(tmp_path)
    assert (tmp_path / "A" / "x.json").read_bytes() == b"[9]"


def test_fetch_bad_download_leaves_no_part(cv, monkeypatch, tmp_path):
    fake_files(monkeypatch, cv, {"A/x.json": b"[1]"})
    monkeypatch.setattr(cv.urllib.request, "urlopen", lambda url, timeout=None: io.BytesIO(b"[2]"))
    with pytest.raises(ValueError):
        cv.fetch(tmp_path)
    assert not (tmp_path / "A" / "x.json").exists()
    assert not list(tmp_path.rglob("*.part"))


def test_fetch_wraps_download_errors_as_oserror(cv, monkeypatch, tmp_path):
    fake_files(monkeypatch, cv, {"A/x.json": b"[1]"})

    def boom(url, timeout=None):
        raise RuntimeError("protocol")

    monkeypatch.setattr(cv.urllib.request, "urlopen", boom)
    with pytest.raises(OSError, match="x.json"):
        cv.fetch(tmp_path)
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.parametrize("data", [b"\xff\xfe", b"[1,", b"[" * 100000])
def test_read_file_refuses(cv, tmp_path, data):
    f = tmp_path / "bad.json"
    f.write_bytes(data)
    with pytest.raises(ValueError, match="bad.json"):
        cv.read_file(f)


# --- CLI ---------------------------------------------------------------------------------

def cli_files(monkeypatch, cv, tmp_path):
    data = {"Claude-3-Haiku/S.json": json.dumps([problem("p1"), problem("p2", graded=(False,))]).encode(),
            "O3 (High)/S.json": json.dumps([problem("p2"), problem("p1")]).encode()}
    fake_files(monkeypatch, cv, data)
    cache = tmp_path / "cache"
    for name, body in data.items():
        (cache / name).parent.mkdir(parents=True, exist_ok=True)
        (cache / name).write_bytes(body)
    return cache


def test_main_writes_matrix_and_prints_report(cv, monkeypatch, tmp_path, capsys):
    cache = cli_files(monkeypatch, cv, tmp_path)
    out = tmp_path / "m.jsonl"
    assert cv.main(["--out", str(out), "--cache", str(cache)]) == 0
    rows = [json.loads(line) for line in out.read_text().splitlines()]
    assert [(r["item"], r["model"], r["correct"]) for r in rows] == [
        ("p1", "anthropic/claude-3-haiku", True), ("p1", "openai/o3-high", True),
        ("p2", "anthropic/claude-3-haiku", False), ("p2", "openai/o3-high", True)]
    report = json.loads(capsys.readouterr().out)
    assert list(report) == REPORT_KEYS and report["rows"] == 4
    assert out.read_text(encoding="utf-8") == "".join(json.dumps(r) + "\n" for r in rows)
    assert not out.with_name("m.jsonl.part").exists()


@pytest.mark.parametrize("argv", [[], ["--out", ""], ["--out", "."], ["--out", "/"], ["--out", "x", "--bogus"]])
def test_main_bad_options(cv, monkeypatch, argv, capsys):
    monkeypatch.setattr(cv, "fetch", lambda *a, **k: pytest.fail("fetched on a bad option"))
    assert cv.main(argv) == 2  # a return value, never SystemExit from argparse
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1 and captured.err.startswith("error: ")


def failing_fetch(*a, **k):
    raise OSError("down\nload failed")


@pytest.mark.parametrize("how", ["fetch", "data"])
def test_main_failure_removes_a_stale_part(cv, monkeypatch, tmp_path, capsys, how):
    cache = cli_files(monkeypatch, cv, tmp_path)
    if how == "fetch":
        monkeypatch.setattr(cv, "fetch", failing_fetch)
    else:
        bad = json.dumps([problem("p1", graded_list=[])]).encode()
        (cache / "O3 (High)/S.json").write_bytes(bad)
        monkeypatch.setattr(cv, "FILES", dict(cv.FILES, **{"O3 (High)/S.json": (len(bad), hashlib.sha256(bad).hexdigest())}))
    out = tmp_path / "m.jsonl"
    out.write_text("old\n")
    part = out.with_name("m.jsonl.part")
    part.write_text("stale\n")
    assert cv.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and len(captured.err.splitlines()) == 1 and captured.err.startswith("error: ")
    if how == "fetch":
        assert "down\\nload failed" in captured.err
    assert out.read_text() == "old\n"
    assert not part.exists()


def test_main_bad_data_leaves_out_untouched(cv, monkeypatch, tmp_path, capsys):
    cache = cli_files(monkeypatch, cv, tmp_path)
    bad = json.dumps([problem("p1", graded_list=["yes\nno"])]).encode()
    (cache / "O3 (High)/S.json").write_bytes(bad)
    monkeypatch.setattr(cv, "FILES", dict(cv.FILES, **{"O3 (High)/S.json": (len(bad), hashlib.sha256(bad).hexdigest())}))
    out = tmp_path / "m.jsonl"
    out.write_text("old\n")
    assert cv.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and len(captured.err.splitlines()) == 1 and captured.err.startswith("error: ")
    assert out.read_text() == "old\n"
    assert not out.with_name("m.jsonl.part").exists()


# --- the evidence README (DESIGN 12.16, v1.61) -------------------------------------------

# The README's default counts as written; test_pinned_files_when_cached builds the same phrases
# from the converter report and rows on the pinned files
README_COUNTS = [
    "reports 67 models, keeps the 713 problems every kept file has, with contest dates 2023-05-07 to 2024-10-05, and writes 47,771 rows",
    "0 for 12 models, 163 for 1, 167 for 22 and 342 for 32",
    "1 for 34 models, 10 for 32 and 4 for 1",
    "from 0.093 (`deepseek/dscoder-1.3b-ins`) to 0.913 (`openai/o4-mini-high`)",
]


def spread(counts, key):
    """'a for n models, b for m and c for k' from {value: models}, ordered by key."""
    parts = [f"{value} for {n}" for value, n in sorted(counts.items(), key=key)]
    parts[0] += " models"
    return ", ".join(parts[:-1]) + " and " + parts[-1]


def test_spread():
    assert spread({163: 1, 0: 12}, key=lambda kv: kv[0]) == "0 for 12 models and 163 for 1"
    assert spread({4: 1, 1: 34, 10: 32}, key=lambda kv: -kv[1]) == "1 for 34 models, 10 for 32 and 4 for 1"


def test_evidence_readme():
    text = EVIDENCE_README.read_text(encoding="utf-8")
    for needle in ["https://github.com/LiveCodeBench/submissions", REVISION, "MIT", "Copyright (c) 2025 LiveCodeBench",
                   "~/.cache/ai-model-routing-evidence/livecodebench/", "1,353,069,054 bytes", "1,233,548,121 bytes",
                   "`graded_list[0]`", "`cost_usd`", "`cost_blind`", "`cost_effective`", "`code_generation`",
                   "`openai/o3-high`", "python evidence/livecodebench/convert.py --out", "--cache", "DESIGN 12.16",
                   "contamination", "LeetCode, AtCoder and Codeforces",
                   "Every row has `cost_usd` 0.0, which is what `cost_blind` assumes of every model's token cost",
                   "the 0.0 is never a measured or list-price cost",
                   "`cost_effective` is never run on this matrix: with every cost equal it would rank every model as equally cheap",
                   "`DeepSeek-V3 copy`, whose file differs from the one in `DeepSeek-V3`",
                   "its `_1_` file has the sha256 of the kept `Gemini-Flash-2.0-Exp` file",
                   "a fixed table of name prefixes gives the vendor", "so `O3 (High)` is `openai/o3-high`",
                   "the problem text, the starter code and the generated code are never kept", *README_COUNTS]:
        assert needle in text, needle
    rows = [f"| `{path}` | {size:,} | `{sha}` |" for path, size, sha, _ in PINNED]
    at = [text.find(row) for row in rows]
    assert -1 not in at and at == sorted(at), "kept-file table rows missing or out of FILES order"
    dropped = [f"| `{path}` | {DROPPED_PINS[path][0]:,} | `{DROPPED_PINS[path][1]}` | {reason} |" for path, reason in DROPPED.items()]
    at = [text.find(row) for row in dropped]
    assert -1 not in at and at == sorted(at), "dropped-file table rows missing or out of DROPPED order"
    assert text.isascii() and "\u2013" not in text and "\u2014" not in text


def test_dropped_pins_back_the_readme_duplicate_claims():
    assert list(DROPPED_PINS) == list(DROPPED)
    kept = {path: (size, sha) for path, size, sha, _ in PINNED}
    assert DROPPED_PINS["Gemini-Flash-2.0-Exp (N=10)/Scenario.codegeneration_1_0.2_eval_all.json"] == \
        kept["Gemini-Flash-2.0-Exp/Scenario.codegeneration_1_0.2_eval_all.json"]
    assert DROPPED_PINS["DeepSeek-V3 copy/Scenario.codegeneration_10_0.2_eval_all.json"][1] != \
        kept["DeepSeek-V3/Scenario.codegeneration_10_0.2_eval_all.json"][1]
    assert sum(size for size, _ in DROPPED_PINS.values()) + sum(size for _, size, _, _ in PINNED) == 1_353_069_054


# --- the pinned files, when cached -------------------------------------------------------

def test_pinned_files_when_cached(cv, tmp_path):
    cache = cv.default_cache_dir()
    if not all((cache / name).is_file() for name in cv.FILES):
        pytest.skip("the 67 pinned LiveCodeBench files are not in the default cache")
    out = tmp_path / "m.jsonl"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert cv.main(["--out", str(out)]) == 0
    report = json.loads(buf.getvalue())
    assert report["models"] == sorted(m for _, _, _, m in PINNED)
    assert report["items"] == 713 and report["rows"] == 47_771
    assert report["contest_dates"] == ["2023-05-07", "2024-10-05"]
    counts = sorted(report["dropped_not_common"].values())
    assert counts.count(0) == 12 and counts.count(163) == 1 and counts.count(167) == 22 and counts.count(342) == 32
    samples = [tuple(v) for v in report["samples"].values()]
    assert samples.count((1,)) == 34 and samples.count((10,)) == 32 and samples.count((4,)) == 1
    rows = [json.loads(line) for line in out.read_text(encoding="utf-8").splitlines()]
    hits = {}
    for row in rows:
        hits.setdefault(row["model"], []).append(row["correct"])
    rates = sorted((sum(v) / len(v), m) for m, v in hits.items())
    (low, low_model), (high, high_model) = rates[0], rates[-1]
    assert rates[0][0] < rates[1][0] and rates[-2][0] < rates[-1][0]  # one model at each end
    dropped = {}
    for n in report["dropped_not_common"].values():
        dropped[n] = dropped.get(n, 0) + 1
    by_samples = {}
    for v in report["samples"].values():
        by_samples[",".join(map(str, v))] = by_samples.get(",".join(map(str, v)), 0) + 1
    built = [f"reports {len(report['models'])} models, keeps the {report['items']} problems every kept file has, with contest "
             f"dates {report['contest_dates'][0]} to {report['contest_dates'][1]}, and writes {report['rows']:,} rows",
             spread(dropped, key=lambda kv: kv[0]),
             spread(by_samples, key=lambda kv: -kv[1]),
             f"from {round(low, 3)} (`{low_model}`) to {round(high, 3)} (`{high_model}`)"]
    assert built == README_COUNTS
