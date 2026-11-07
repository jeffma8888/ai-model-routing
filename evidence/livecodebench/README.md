# LiveCodeBench evidence

The LiveCodeBench submissions record, for dozens of models, the program each wrote for dated contest problems and whether it passed the problem's test cases. That is enough to test routing offline with no API key, on a coding task whose label comes from test cases rather than a judge: `convert.py` turns the files into the outcome matrix that `model-routing evaluate` reads (DESIGN 12.1), one routing task, `code_generation`. The files record no cost, so the matrix is evidence for the `cost_blind` flavor only. The converter's full contract is DESIGN 12.16.

The routing results on this matrix, `cost_blind` only, are in [RESULTS.md](RESULTS.md), with the committed numbers in [results.json](results.json) (DESIGN 12.17).

## Source and licence

- Repo: https://github.com/LiveCodeBench/submissions (archived)
- Pinned revision: [`6ca212e9c2039373f6e5069d37ffa9db66e23736`](https://github.com/LiveCodeBench/submissions/tree/6ca212e9c2039373f6e5069d37ffa9db66e23736)
- Licence: MIT, as the repo's LICENSE file states, with the line "Copyright (c) 2025 LiveCodeBench"
- This repo commits no part of the files: the converter downloads them into `~/.cache/ai-model-routing-evidence/livecodebench/`, one folder per model folder, outside the repo

At the pinned revision the repo holds 73 JSON files in 72 model folders, 1,353,069,054 bytes in all. The converter reads 67 of them, one per kept folder, 1,233,548,121 bytes. The repo has no checksum file, so the pins in `convert.py` are the only trust root: each file is checked by size and sha256 before it is read, and a cached file that fails is an error, never silently replaced.

| File | Bytes | sha256 |
| --- | --- | --- |
| `Claude-3-Haiku/Scenario.codegeneration_10_0.2_eval_all.json` | 21,175,537 | `d4dde49c99058f4fac9e9faeb739c59e3024b062d29c1fa8a875a92ef5e15edb` |
| `Claude-3.5-Sonnet-20240620/Scenario.codegeneration_10_0.2_eval_all.json` | 17,342,354 | `8227e0e70d72d808bf65809f905052f36ebb82e504b69908fb31d7e7ac7f3a92` |
| `Claude-3.5-Sonnet-20241022/Scenario.codegeneration_10_0.2_eval_all.json` | 29,896,047 | `1b900ac47a147006ea2f8c258d60a6ee9dd8dff378ebcd926f322466179d99b1` |
| `Claude-3.7-Sonnet/Scenario.codegeneration_1_0.2_eval_all.json` | 40,780,648 | `1b8334f503ad2d13eaa2b3ea15b46a289706276d40e96f3274442e0d8184620f` |
| `Claude-Opus-4 (Thinking)/Scenario.codegeneration_1_0.2_eval_all.json` | 15,447,145 | `d9b959036c9952161dcbdd515a225a2d2a03c747469dd50ac2b6561d42b04714` |
| `Claude-Opus-4/Scenario.codegeneration_1_0.2_eval_all.json` | 5,707,347 | `a75e46288b0457ebd2ce7fee3f06d69fdeda4b00742defe3b13c46887892db91` |
| `Claude-Sonnet-4 (Thinking)/Scenario.codegeneration_1_0.2_eval_all.json` | 19,133,477 | `339db7aab7be74a509e25fcf75bc42adff3f6e4829d8d5a3359864de0e1d8188` |
| `Claude-Sonnet-4/Scenario.codegeneration_1_0.2_eval_all.json` | 6,096,105 | `caa412a80e12e51bd2737a99c557691241b5acf2f4e404f2db0556417efcf600` |
| `Codestral-Latest/Scenario.codegeneration_10_0.2_eval_all.json` | 16,698,489 | `f3b7ad09528d9046451b5fe0e3f67f26912c5fd4d6fdf0db22ba5b0af0d0cd2b` |
| `DSCoder-1.3b-Ins/Scenario.codegeneration_10_0.2_eval_all.json` | 8,972,584 | `f78ad8f239ff5144c81709ecab72dca1eee19b40b21ba1a2fcf92501c8dae017` |
| `DSCoder-33b-Ins/Scenario.codegeneration_10_0.2_eval_all.json` | 10,124,550 | `af10caa8fe47deaa745f410768864f8813e234c02872b247cb9c076dd872575f` |
| `DSCoder-6.7b-Ins/Scenario.codegeneration_10_0.2_eval_all.json` | 11,257,116 | `f972642519aa1e346f73dffe6f0b2387b406a1548d216bc84fe9e19c7e53a127` |
| `DeepCoder-14B-Preview/Scenario.codegeneration_10_0.2_eval_all.json` | 51,800,914 | `52870bf12c83f9245cccb41d5b65a65fd8f9d18895063a1cde3354346f93b048` |
| `DeepSeek-R1-0528/Scenario.codegeneration_10_0.6_eval_all.json` | 55,720,447 | `403fb6060512b10766fba5e1c16ba320191355e8d7e920f01e5be69bcde25231` |
| `DeepSeek-R1-Lite-Preview/Scenario.codegeneration_10_0.2_eval_all.json` | 36,340,580 | `d432c2668f49d8baf1ec512d73ade2a8133e5108043d6e9a1a44912bb3e74f5e` |
| `DeepSeek-R1-Preview/Scenario.codegeneration_10_0.2_eval_all.json` | 37,086,048 | `7a363a772c47d00a63db99d0f444e28e9ec6f0f8f26adc50b9190fc908332a99` |
| `DeepSeek-V3/Scenario.codegeneration_10_0.2_eval_all.json` | 36,242,668 | `88548117b84bf567fdadb159cfc65f9c0a6bf7da8b2fe5679829c95334abd661` |
| `EXAONE-4.0-32B/Scenario.codegeneration_4_0.6_eval_all.json` | 23,877,444 | `019bc78e1685fbe411149cb6c69244d2bafe04304cfd72f60bab3c5b27b3dc6f` |
| `GPT-4-0613/Scenario.codegeneration_10_0.2_eval_all.json` | 9,600,263 | `bd0ab24c9f8da86bf010f90e55d052ecf513922649c2f181b742d21cbfa37189` |
| `GPT-4-Turbo-1106/Scenario.codegeneration_10_0.2_eval_all.json` | 14,387,341 | `73e2e8e25b92fe23a578d3fe6c29f83a48dc5dbee9c3d5e7d907f75f7f0ac650` |
| `GPT-4-Turbo-2024-04-09/Scenario.codegeneration_10_0.2_eval_all.json` | 28,049,953 | `fc46d2a4fdd42caa0f7ec30366c318ddcded2334a0b3128752b5f15c4793bf97` |
| `GPT-4O-2024-05-13/Scenario.codegeneration_10_0.2_eval_all.json` | 17,904,865 | `072871af75fcb2b00efad273372f7f701363576f1e2cd2f57dc19c97b3f2d362` |
| `GPT-4O-2024-08-06/Scenario.codegeneration_10_0.2_eval_all.json` | 32,778,775 | `5d072bd884756779f22f6e9239b142f82ff87dd2d76f7647f732be2a55efb0ec` |
| `GPT-4O-mini-2024-07-18/Scenario.codegeneration_10_0.2_eval_all.json` | 24,796,617 | `37b922fae87f97c957e9a2554ddabdaa777d876758bad86e7aabb2f26ebf4972` |
| `Gemini-2.5-Flash-04-17/Scenario.codegeneration_1_0.2_eval_all.json` | 9,298,858 | `2b81892984e212d9937942aafb9e478e985600e50114d7fa86fba2b5f53486cf` |
| `Gemini-2.5-Flash-05-20/Scenario.codegeneration_1_0.2_eval_all.json` | 16,026,288 | `75957e8b682cf4bf75f4b24953038f7e374c0f9c592d8f7577117d7ea060057c` |
| `Gemini-2.5-Pro-03-25/Scenario.codegeneration_1_0.2_eval_all.json` | 12,182,339 | `a336ec7c2d9d83fa331c43633be5abc08817441cf2d9d18d362b7924ea610b29` |
| `Gemini-2.5-Pro-05-06/Scenario.codegeneration_1_0.2_eval_all.json` | 15,665,903 | `7e0cae96e609e085beeb66d56b74e9186d948c65c803427f1a5d022401982026` |
| `Gemini-2.5-Pro-06-05/Scenario.codegeneration_1_0.2_eval_all.json` | 13,420,908 | `19be5460eda197621738c871cd496d79b1d1fa3c653a5a7742fd4985abfd2d39` |
| `Gemini-Exp-1206/Scenario.codegeneration_10_0.2_eval_all.json` | 19,858,737 | `5555e4cde78f48a6b6ee3391964bb9b9d379a61b0bd9f71137548c5fcddc7b71` |
| `Gemini-Flash-1.5-002/Scenario.codegeneration_10_0.2_eval_all.json` | 15,723,216 | `46150890d210451f966408536d2cdf2434f044811ad85faff496e4b4d6f0e0b5` |
| `Gemini-Flash-2.0-Exp/Scenario.codegeneration_1_0.2_eval_all.json` | 6,955,936 | `9c0b4f222c428d627ae8fee677a031b203b30e45a396a1c41ad8358ebb5bc42c` |
| `Gemini-Flash-2.0-Thinking-01-21/Scenario.codegeneration_1_0.2_eval_all.json` | 20,903,075 | `227f75adcf0502e1942b9178b353f0665617a86ce525e64fde26f5a4330574b1` |
| `Gemini-Flash-2.0-Thinking-12-19/Scenario.codegeneration_1_0.2_eval_all.json` | 20,546,068 | `72e58004bd0f09835bb3f2600c41c3bce2e1ad815662ee9a4a294185d543812a` |
| `Gemini-Flash-2.0-Thinking/Scenario.codegeneration_10_0.2_eval_all.json` | 23,667,385 | `d79024201d8a77db19135d94a1812ffde2c02ffb7ed7ef1d53f69f8018c61687` |
| `Gemini-Pro-1.5-002/Scenario.codegeneration_10_0.2_eval_all.json` | 15,887,371 | `c6650177f41ab56596e5085077a2edf1444170bc1a804c447cd2fd900449e1ba` |
| `Grok-3-Mini (High)/Scenario.codegeneration_1_0.4_eval_all.json` | 4,361,019 | `834f0311cc6d0610b9c1840e9cb26a80ced4ef08b3400ee2926881e8036a4fab` |
| `Kimi-k1.6-IOI-high/Scenario.codegeneration_1_1.0_eval_all.json` | 4,099,066 | `ef3a96fce0c8fd83417bc11a55200c3159d39b1936960959ebb67f15b0bd9b58` |
| `Kimi-k1.6-IOI/Scenario.codegeneration_10_0.8_eval_all.json` | 30,401,298 | `59583d3fbc343920e48fa7c9c257e0ec5e564c152e066c0b6560546a061b8013` |
| `LLama3.3-70b-Ins/Scenario.codegeneration_10_0.2_eval_all.json` | 16,031,611 | `91708bc6db33d239ad4b8c75424448035263b73b2dc44a428f2b1300affc4071` |
| `Llama-3_1-Nemotron-Nano-8B-v1/Scenario.codegeneration_1_eval_all.json` | 19,558,899 | `cf3729eaf6e9b5164951fbf82506ce05ca95f52d2130c3c9ec3955958913aadf` |
| `Llama-3_1-Nemotron-Ultra-253B-v1/Scenario.codegeneration_1_eval_all.json` | 5,107,907 | `9e31c5feba8b56bf7515684c415c0c7e5e1f31d3a2f896f24ef9fabe66d8dba3` |
| `MetaStone-L1-7B/Scenario.codegeneration_10_0.6_eval_all.json` | 54,754,997 | `499f395db1cba305790446a6251c6b9822d78b757ca447d29e41b9dd4b338219` |
| `Mistral-Large/Scenario.codegeneration_10_0.2_eval_all.json` | 20,707,461 | `73a67f7b514f6fb94bdbe0a7762d4d7e9daeacf8d155ae81a53a8e2719ea0469` |
| `O1-2024-12-17 (High)/Scenario.codegeneration_1_0.2_eval_all.json` | 5,693,027 | `52c10c62c5408faeda5cedac221b71251564dd307bc61512df28e33aa902e642` |
| `O1-2024-12-17 (Low)/Scenario.codegeneration_1_0.2_eval_all.json` | 6,554,308 | `96cf54b1f7b19d8d202641e1915aa5ef663c06811ed06a99893123b79f077234` |
| `O1-2024-12-17 (Med)/Scenario.codegeneration_1_0.2_eval_all.json` | 6,342,959 | `2cfef88d6130d0700dc75e8a9470680dff81fffce4e9d78d88600e99125e9d46` |
| `O1-Mini-2024-09-12/Scenario.codegeneration_1_0.2_eval_all.json` | 3,636,170 | `9e7c9d729cc464af3e532af9faa1ec8ea993839567e4c952bfa7fb92e094d78b` |
| `O1-Preview-2024-09-12/Scenario.codegeneration_1_0.2_eval_all.json` | 3,799,086 | `916568014b99be062ca202efb6390fb8cfb8dc750ad4d88611df4cd44c6bc84e` |
| `O3 (High)/Scenario.codegeneration_1_0.2_eval_all.json` | 5,316,324 | `a7c900595d6ca6eba133e03e9e4fd24b0047a87e8a8302935ba2b83f0b834ff7` |
| `O3-Mini-2025-01-31 (High)/Scenario.codegeneration_1_0.2_eval_all.json` | 7,234,096 | `37440ebbcbb947c5bf8b19eab872f1e0386013e00fcabf6a2eb074c56ca9774d` |
| `O3-Mini-2025-01-31 (Low)/Scenario.codegeneration_1_0.2_eval_all.json` | 6,836,877 | `4f4bed0e765eb9ff8fbc909a78225f9c40c41775aeae670e5ef9ddd42a24d3b5` |
| `O3-Mini-2025-01-31 (Med)/Scenario.codegeneration_1_0.2_eval_all.json` | 7,150,157 | `428773c6bf3445ee9ca2f7cadaea18a6e328e82ce68e5ef6d0e19a0ba5243f42` |
| `O4-Mini (High)/Scenario.codegeneration_1_0.2_eval_all.json` | 5,566,694 | `533249d34528071b3cd4ca50c756b61518a37cc90f6d4b3a931ca9dce421b06b` |
| `O4-Mini (Low)/Scenario.codegeneration_1_0.2_eval_all.json` | 5,289,377 | `1ccf62bb019c8a9176bfc7e1625b36ad4f82a1029d636fe949c4b8133bbcea59` |
| `O4-Mini (Medium)/Scenario.codegeneration_1_0.2_eval_all.json` | 5,449,673 | `d045f8bcdfec799803fa8734f9a51aa2c589f0759ff509470320cde550b33ed3` |
| `OpenReasoning-Nemotron-32B/Scenario.codegeneration_10_0.6_eval_all.json` | 22,370,156 | `5aec11207b7d6ff37f6220513e5fcc9df8a6d837bc46a0163f1ff95ae0955e61` |
| `QwQ-32B-Preview/Scenario.codegeneration_1_0.2_eval_all.json` | 31,532,692 | `7a6ac226b050b3d29e7cceb900c80a6c13872a87099be72b1726b747c7962b8b` |
| `QwQ-32B_temp/Scenario.codegeneration_1_0.2_eval_all.json` | 44,575,245 | `616906647f8c31136f1bb2e8924a0fe9587ef085ee77781c963f029d738c6fe6` |
| `QwQ-Max-Preview/Scenario.codegeneration_1_0.6_eval_all.json` | 30,801,371 | `dd3c3c428ef04e07892cd2a1308cfd1cadcce61e3f37454076b6813d854e0a62` |
| `Qwen2-Ins-72B/Scenario.codegeneration_10_0.2_eval_all.json` | 12,353,225 | `5ce1e7b71388887353264034a15425c2debabfc775a18f231aea215ceb388381` |
| `Qwen2.5-Coder-Ins-32B/Scenario.codegeneration_10_0.2_eval_all.json` | 15,265,370 | `b3cee20f0bfcfeccf4350c75244eaeb9ab73385a732d433629845177d6231822` |
| `Qwen2.5-Coder-Ins-7B/Scenario.codegeneration_10_0.2_eval_all.json` | 10,858,879 | `586707158f8d1648964f54f0290dc42c94806b12684ea03b537202008170c992` |
| `Qwen2.5-Ins-32B/Scenario.codegeneration_10_0.2_eval_all.json` | 12,135,021 | `39c766b34f6a412fac0c9e382bed7ea5d2b8a45874b67d6bb998455edc6a183c` |
| `Qwen2.5-Ins-72B/Scenario.codegeneration_10_0.2_eval_all.json` | 12,705,443 | `6555e98ea20a4aa5d2ac2439cc62065001280366e11815c0c29f32fe31228f68` |
| `Qwen2.5-Ins-7B/Scenario.codegeneration_10_0.2_eval_all.json` | 10,517,624 | `b9b11acc6b1beadcb25067000bb619cbe1a7c53c859882606d04550cdb018179` |
| `Qwen3-235B-A22B/Scenario.codegeneration_1_0.6_eval_all.json` | 45,188,691 | `4b64e46c8f1a3e7ae14906b28e685624f05becaafe6422be7743f8a04c77b7b9` |

The other 6 files are never downloaded. A folder is dropped by the first of these rules that matches its name: a name ending in ` copy` (`DeepSeek-V3 copy`, whose file differs from the one in `DeepSeek-V3`, as the two sha256 values show; the folder without the suffix is kept); a name containing `(N=10)` (its `_1_` file has the sha256 of the kept `Gemini-Flash-2.0-Exp` file); a name ending in `_prompt_old`; and a name that states no vendor (`AzeroGPT-64b`, `XBai-o4-medium`), for which the converter guesses none.

| File | Bytes | sha256 | Reason |
| --- | --- | --- | --- |
| `AzeroGPT-64b/Scenario.codegeneration_10_0.2_eval_all.json` | 19,352,799 | `f2afe8bf8937d36fab7a7a95e426f6a845be3485f941610eda4e94126784748b` | no vendor rule |
| `DeepSeek-V3 copy/Scenario.codegeneration_10_0.2_eval_all.json` | 28,351,686 | `06e7b8340903a1154fea69cf63a7deed78ef575f72a95b5d16537a6b6436b142` | copy of another folder |
| `Gemini-Flash-2.0-Exp (N=10)/Scenario.codegeneration_10_0.2_eval_all.json` | 23,790,224 | `0eeba1e8eb984976c9e4dafa03c1f000cebf6d646c5f1e4690b3f0e2f3a7a3f8` | 10-sample run |
| `Gemini-Flash-2.0-Exp (N=10)/Scenario.codegeneration_1_0.2_eval_all.json` | 6,955,936 | `9c0b4f222c428d627ae8fee677a031b203b30e45a396a1c41ad8358ebb5bc42c` | 10-sample run |
| `O1-2024-12-17 (Low)_prompt_old/Scenario.codegeneration_1_0.2_eval_all.json` | 4,932,645 | `81104861ab7d19b18cc8581187a30bf93174b7479518282645960225d05acc55` | superseded prompt |
| `XBai-o4-medium/Scenario.codegeneration_1_0.6_eval_all.json` | 36,137,643 | `8f80d42f61beee24468a744839df254888f9ce8192bd7563a3d530f515795cc8` | no vendor rule |

## What counts as a success, and why there is no cost

- A problem is a success for a model when `graded_list[0]` is true: the first sample of the model's program passed the problem's test cases. The matrix takes one boolean per (item, model), so later samples are not scored; the number of samples is read from `graded_list`, not from the file name
- There is no cost: the files carry no cost, no token counts and no list price. Every row has `cost_usd` 0.0, which is what `cost_blind` assumes of every model's token cost, and the 0.0 is never a measured or list-price cost. `cost_effective` is never run on this matrix: with every cost equal it would rank every model as equally cheap, so its rows would say nothing about cost
- The items are the problems every kept file has. The files' problem sets nest, each inside the next, so the items are the problems of the smallest files, and a problem given two contest dates is an error
- Model IDs come from a rule over the folder name: a fixed table of name prefixes gives the vendor (for example `Claude-` anthropic, `GPT-` or `O1`, `O3` and `O4` openai, `Gemini-` google, `DeepSeek-` and `DSCoder-` deepseek), then the name is lowercased with ` (` written as `-`, `)` removed and other spaces written as `-`, so `O3 (High)` is `openai/o3-high`. Each reasoning-effort or thinking setting is a model of its own, since a router would choose between them. A name that is not ASCII, that no rule covers, or that gives a model name outside `[a-z0-9][a-z0-9._-]*` is an error, not a guess
- Only the model, the question id, the contest date and the label are kept from each problem; the problem text, the starter code and the generated code are never kept

## Regenerate the matrix

```bash
python -m pip install -e .
python evidence/livecodebench/convert.py --out livecodebench-matrix.jsonl
```

`--cache DIR` downloads somewhere other than the default folder. No extra is needed: the converter is standard library only. It prints a JSON report of what it kept. `model-routing evaluate` with `--flavor cost_blind` runs `cost_blind` alone on it (DESIGN 12.4); [RESULTS.md](RESULTS.md) gives the bars, seeds and commands of the committed results.

With the default options on the pinned files the converter reports 67 models, keeps the 713 problems every kept file has, with contest dates 2023-05-07 to 2024-10-05, and writes 47,771 rows. The number of a model's own problems that are not kept is 0 for 12 models, 163 for 1, 167 for 22 and 342 for 32. The number of samples per problem is 1 for 34 models, 10 for 32 and 4 for 1. On the 713 problems the models' first-sample success rates run from 0.093 (`deepseek/dscoder-1.3b-ins`) to 0.913 (`openai/o4-mini-high`). Reading and converting the 67 cached files takes about 3 seconds.

## Reading it

- The models date from 2023 to 2025 and the 713 problems from 2023-05-07 to 2024-10-05, so many problems predate a model's training data: the contamination LiveCodeBench dates its problems to expose. A later model's rate on old problems can overstate what it does on new ones
- A label is the test cases passing for the first sample at the run's own sampling settings, and the runs do not share them: they drew 1, 4 or 10 samples per problem
- The problems come from LeetCode, AtCoder and Codeforces, so nothing of them is kept but the question id and the contest date
- With no cost, this matrix says which model clears a bar, never what it costs
