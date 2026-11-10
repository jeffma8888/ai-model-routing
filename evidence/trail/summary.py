"""Summarize the sub-agent runs of the TRAIL GAIA traces (DESIGN 13.11).

Usage: python evidence/trail/summary.py --out PATH [--cache DIR]

Standard library only. The 117 GAIA trace files of the public GitHub copy of TRAIL, at a pinned
commit, are downloaded into a cache outside the repo, each checked by size and sha256 before it is
read, and read one at a time. A sub-agent run is a ``ToolCallingAgent.run`` span inside the top
``CodeAgent.run``; its model calls are the spans of its subtree whose name ends in ``.__call__``.
Per run the summary keeps the number of model calls, the sums of their prompt and completion counts
and the first call's prompt count, then the min, median and max of each. These are observed usage,
never 13.1 inputs: each call's prompt count is everything that call read, the run's history included.
"""

import argparse
import hashlib
import json
import os
import statistics
import sys
import urllib.request
from pathlib import Path

REVISION = "0ffbed9db859b4a66250dc783fa4dccf86869595"
FOLDER = "benchmarking/data/GAIA"
LICENCE = "MIT"
REPO_URL = "https://github.com/patronus-ai/trail-benchmark"
BASE_URL = f"https://raw.githubusercontent.com/patronus-ai/trail-benchmark/{REVISION}/{FOLDER}/"
TIMEOUT = 60
RUN = "ToolCallingAgent.run"
TOP = "CodeAgent.run"
CALL_SUFFIX = ".__call__"
COUNT_KEYS = ("llm.token_count.prompt", "llm.token_count.completion")
MAX_COUNT = 2**63 - 1  # the largest signed 64-bit integer
MAX_DIGITS = len(str(MAX_COUNT))  # 19
STAT_KEYS = ("model_calls", "prompt_tokens", "completion_tokens", "first_call_prompt_tokens")
# "<trace id>.json": (bytes, sha256), in ascending name order
FILES = {
    '0035f455b3ff2295167a844f04d85d34.json': (112904, 'a8b31d38493a22091788f99e32beb79b801e35269f626b6a0de0446f435df38e'),
    '0140b3f657eddf76ca82f72c49ac8e58.json': (1947451, 'e84a09e9a2bb6a4636cb25d5797ea264d70bf61c21688e13576962a097f40082'),
    '01c5727165fc43899b3b594b9bef5f19.json': (1883610, '1c7af97a7da891b7c9af5fab49155998c18ba310392adefe3beb8efae7e1ad8a'),
    '0242ca2533fac5b8b604a9060b3e15d6.json': (204183, '3d5e848670a47911bffaa83510f2208574e1273fe6119bc318691336cf8e1dfb'),
    '041b7f9c8c76c2ca1a8e67c6769267c3.json': (202711, '9c64cf910af66741b60159b85fd963473f5adff9bfb29a5d7b65424b20944597'),
    '08be1639c58e086cf0bb8c269039973d.json': (115103, '3c0e4ea703b94ccbd6841458d12a00f755ac5d1aa1589c8a4b09c49b37787009'),
    '0adc4f3b99d9564d32811e913cc9d248.json': (141822, 'd81e7c493cd0165a26e73fafbabb6250ed2b40caafe636424aca06181bfeb60d'),
    '0ebe673d64647ec44c370638b82d3c78.json': (96308, 'c5ae6df75d598faf1cabf435c71e6d38fd71234993779638ed51b3915115696b'),
    '1427b326e21963a1228647ad8dff2bf4.json': (103282, '6aa519c0dda8927fc058fffb603953cba9674ae1abb2628655d1e377af9b8c8d'),
    '14be0e98b825d2da5665e2e10f6cc927.json': (3397097, '08ed86430941f84ffcd41326f29adb535b9dd86412e98d7dce78fb8b333392d7'),
    '18efa24e637b9423f34180d1f2041d3e.json': (173289, '600eb4162dc9f15beb893492443bab51263a453eb39ff3fb54eaf89621681631'),
    '1dd91d388cb4889e6c1f5ea5ca06bce6.json': (215421, 'd9e013704be35d70d12981efe1f0c336bf1c67ea7c2e34a0a1b9498c38746b6c'),
    '21f0c6c8d76ac61f4388f36ddffe1c38.json': (761074, '5e701fb4e747b7e796fc482af06dd46c62c31a0aa79e781570b238566114497e'),
    '2209204b631e26f4cee4dc3dd995608c.json': (161082, 'c353c36ed98de9595021fffc38564cf14f61a187e0569d04d5d1778718ea2d52'),
    '25c8275651013fe8398ef0f735eb0912.json': (117267, 'd86ff3040e09bc28a7d2f907e3e759c3012932a83eccd91917bcae7a6e6f778d'),
    '2713fa0aa73f0c5a8b480f026c21a547.json': (112016, '8554cfe0b118a90d90706636ce8fb5e76686635823e78878354ef0529cbc1a5b'),
    '27a6c5ebc3311542156fdde857a0035f.json': (106850, 'b5f001a41da09278702ad6ad3ee733fbb0b414fbb8762912e7117d45588f2060'),
    '2c77a8feec544cc61a00a387ad792a13.json': (428027, 'bfd6e7a90d8f725f9330a3fb04cfe3dcbc8bd1ae9b975d8e3192f2bbf6a02576'),
    '2cb6924caac94b32d2bf4b40bdf4ab51.json': (1294017, '2db165afbd1aebe5f462bdccd3bea7efe34aaa477e96718ad042006bc2aeb18f'),
    '3205fa0cb2135fe671bf7cd0e5a26151.json': (1223468, '46c15dae62863ceddfb20086c718ac28e1c75b9ea1a0e76bf872d0e46c0ef4c0'),
    '3215fc75e81bdb73706a4fb37b66427f.json': (325859, 'fcf4984dc053188415378fc37bd4c33e2bdb63ae355a2cb02e610b19fdb55c26'),
    '331aece579d942bb4c345a86c86efb83.json': (341917, '98d88e4c5c9e03d22f2a43d4acc4157487bb139b5f7cbd789c3a2523c6d63bf2'),
    '33cedc57294f33839f1acc3ee5182788.json': (1482985, '452a73a234d0ae503394dd138c3f86c82a8f24df4e1a3c155c978c2d719b0ae3'),
    '3637c5845140adbf29c565923c20e94d.json': (172062, 'a25bb60ee0e450cf7770d2dea91910be5c9e4f71bfd4975c8b5d3c82c548a627'),
    '387546b0d3e81503bd8d392c6f1b6b25.json': (1150604, 'e84f1766cf5c63112f31e250315c45e9b30f176342d2d06e771a869a788aba33'),
    '396b6aa1ab86eb2e20d27582eb5eebd9.json': (3850721, 'a2280309f3079a3de8ae88a00abf9179a5bcb500c380e31611325b453b2a5a02'),
    '3acaa3150977e199eddb95c64f2ada2e.json': (710863, 'cee9269e6af749801976f88d31ecbcd831b498987fdb98aae07def1af3e5f20c'),
    '3f05ba33cd4ae18ccba6db9a5749c16f.json': (117699, '77e13ff6682f01fc02dc6cce7f6f29fb38abf26938fd835b3f07d9b7d43ee219'),
    '41b597524173272503073a0799ac523c.json': (111153, '324d499507ef067a9d3c39afdec12aa9685f16316b1275e61e5db8e01646d320'),
    '41bbc898aa7de0f31d2382ff57700a76.json': (355258, 'fafa19f63b0150d4c3d3f681e827f43cc747a98feb820bfe82e108c4a2d21bee'),
    '4514626d62ed350ee7878c03f51bbe68.json': (170856, '42098ba835bda520ca4c1af1679b318d31b6ca219c36240dbcf961eadda1e23f'),
    '4a8d094e92433f1ba1da21f602c417d9.json': (157661, '349545effc314bfb66f1d130fc647937e7ceb32c8da8e0e10c4b907347a78aab'),
    '4ae16319f0de44a7d1e84595b41ae08d.json': (104326, '2eb75cb772183919e35a683d32a89021e81eff5e6641e1efa318f2e78c186d2c'),
    '4c79c8ba0cf1e8fcb1c408d53016c560.json': (110797, '4750a188617b04c0bf4b633039ec0f4a6f1dabe6988c2d47ac54f51f366a41d8'),
    '512475a321c616e45337da3575f6a185.json': (440492, '312b64754b2e2b75c7da999922f7441e802c4db66091981267715b02101d37fd'),
    '53dba4241b22d5039c9c119871c7c8b4.json': (111542, '708401da46871a0fe1be263d7e236ae7d83e483a652c5f3fda34f20c814b8117'),
    '59365b27641e501d105b0e8f5e7c5af7.json': (2727320, '2f86c6a062b7da8d4a606f7437850f9370f6125b08994b524ab64fd2034f63f6'),
    '5a6c51d59f870513c68745e2e0f9269f.json': (2012000, '1e07edbab3dadd3e0506135629db1352d0ede1973b542bc4f0fb1d165e33d37a'),
    '5b5a35053775cbf29701c171e6675853.json': (351726, 'd74231ba38fd41e6fa9df1376727e86e5c1d534d694c2f4473d69a178e63a40e'),
    '5bbd1534b199c57861f55b58be9949a0.json': (2332912, '355c14a8ed0aa031c4a35d8f73e3c8f0a23a1f0c8c29b4ccbb3c08928f29de75'),
    '5dc4cf8d5175f2782f46265456998d39.json': (276683, '69f320cf97cbe2a6bf9c2d9af5c7dabe3280ce81a368c2c29ab133690812493f'),
    '5e5dc94e090341c564d582f551a0cddb.json': (98651, '18f478d7594e7a674ef0390c7aacf76d9fceae92aeb86a3f6f86e5cd82f97862'),
    '5ec1cd43eb8ae4094e93a4892ff0f06f.json': (107243, 'cbd695bd052f53f5bc469be5ca096ad28e8fe747b396519f286ab01911756aa9'),
    '5f3a0a7fc572f49630c069e4e5a64ae3.json': (2038572, '448b7f75cf4ba4c6bf03f2e1322eea1ff503ce85e18e66cb87b2d6d422feb596'),
    '62df2a06b647ca730391602dbf62f843.json': (118111, '971f74434274dcc320c0a48f5df6432b5b471a78a68d665269616b9207339ee0'),
    '63ac9e03bf750e58eecbc5b148d8d215.json': (215613, '3f791af084cf95ab47e10dc8ef64165774ac50e137d90e8856a703c2a99fc57e'),
    '672d36d8ecc4816738433c75136eb99d.json': (457442, 'bd102c94f882966ce2de3e66f1930403fe794735afd00f8932a1c4a869ee1a2d'),
    '6cc6dc35a28bbed6cfd873756094bc16.json': (4455935, '3bf275fa692e460283d3838232023d043c7c40fa4c3309fe4426688be33e005a'),
    '6d5b91f06e5a7377d4798be65fe46e97.json': (204247, '93ab881af8c20288d3a09ba0218acb0c107336b5adf48ff45015a058a5054577'),
    '6e64c2e543327a7c2f2ce3d26ced94d1.json': (180673, 'b548db1abcc853b82004ef1a482e3f474f63f549a39d9053d91cccfcef38e5d1'),
    '6f0ede30602ae3fe2ced3f9fabb008a6.json': (113916, 'b1747586c5edcf1df0de5840d98a92d7991d3ad7ea374eacba5211cddcc7835d'),
    '72877db591837666d500b459fb3cf29d.json': (121491, '24188f2793a9a902ea176f355d1dc518ec4e9733de71ac9b0e9e362a01f55170'),
    '75121379e11c550f3ca58e17c972266b.json': (126997, '5e25910f09f686cbbd9f9362e6765fb16ea39264e2f376a866c93fb4c0b7a91a'),
    '772605f0794b0fa96bc942a8a7736571.json': (776653, '0867fcbe73baf772e5e1271a492f0778ddcd711a9caddfe3ab537d2f74ca3d74'),
    '7bf0addde339e4cac9dd3b772232a7e0.json': (328299, '924cb726299c95847df510326a80b1170e0ade6096b8c40f86e8b46bf76666eb'),
    '7c98d39b2699d41fa913f8fbe60c04ed.json': (107615, '85a7ee419fe42ea186924d4b1e52d019b88b7c41760c596189c9fdd84d6eae3e'),
    '7ee8e8df6e8cd101d9af8a4a4f6ceedb.json': (429936, 'e3a70008f0f1ec229f38ba3992b908915170b4311aae6d83f56392bc88e158b6'),
    '85c14ced5177cdad83f1f1f898a1c6c7.json': (268536, '3f060340213e1de7847ef285a87e44c9dfc7957ff3e413bc9376ca3899248ac8'),
    '860f9d45f2e50bfecb190bb26eff1f32.json': (8509773, '875115e7df807b89d1ed076cccac5966711a593e10f273379086561e11420983'),
    '876eb108c8650d4ada63a8d39aa1e96c.json': (264076, '1ffc0da2330ec763b1e54032dd8f9210fa61bb13f97b5b86b11a15538d802fb6'),
    '88c63c780aba1f23c3c5345aa340d7e2.json': (123525, '4739dca68eb9a922644e218bd891a1849a6f1c21c2b4322ca6e19b457a5590bf'),
    '88e4ce6a659df42a4146331fff36417c.json': (248213, 'd7286542371531a43852c81eda2405e1013c6e69153dc59ab8e83a491687c510'),
    '911e853f02d03e976dbf0c16f653ab57.json': (105087, 'ab524c8c0ccb69ffbf4eff99ac0532e3af8434fd60d0767a357bc838f4554ab1'),
    '915d2c66879657f694f88e0ed6f02cf5.json': (7573525, '9c2eb82fa8f7016521b30da757b4ae3aecadd77fe172fd37ee875628e27694f0'),
    '96be1bf61f2915e52ec59173b9bd9828.json': (107678, '7c58b85ca92292c6a4f4597fc3c9f9edb0ea11767417dc933c26304bcb8ab24e'),
    '99f6b447779ba86b3cff2caede832d59.json': (156271, 'd169bf4378edeb94d3707033f09a59ccb8ff7a7a7e7a2dc9c743a3e07588e583'),
    '9cd6dc7c0af658a87f603b488950f409.json': (124497, '116e96e4d9a9a6dd4559c9e1ad184c83d927d730e70bc15c206a16906158bb62'),
    '9e67afe0ff4eca1558073c2e5cfbf876.json': (104584, '4c181ba2c7b7ea1bd0f64ae7884720e78ae20c2237caaa06cf60d40d8ee0f14d'),
    '9ec7d4a8ab8c74ab56361ef29d1b1660.json': (121140, 'ae79dad30504503a6d2fce9c4de512bd7ee2d1c99c58065e8bf91ca8988b1c40'),
    'a041b8d88e3fedcc7d387da328f8a3b4.json': (227567, '03fb25d11fce3f8ad03c4f06d87ebf33c241c5d6db59d89476926ca9a5ad2c1a'),
    'a32806e19bac45a34d3712ccc433ec9d.json': (1018299, '8283c0eeb589d54fc3e64e4e58b14f2e0c09123ffa6141c37f9bcb4aea28f9d6'),
    'a4af6c6d200e6d19d7f24e1d1d688188.json': (155772, 'e4e93c154ca2dc20da16d3da7ea4a462656ae0288262113c4a03c80d4317e666'),
    'a5c2947f441d65edf60131463fb79999.json': (2750655, 'a1ebd4ea21f9df817121b27b179cef081b45b3ffd292cb3e7c7c3d40117a9581'),
    'a7017f40866dd77c6c0c0e98bad17f69.json': (174322, '962f13b23c5668696e5bcab73f259a70a13d8f3520ecf745aaded0ea5b63cfbb'),
    'a96c6811716c0473b86a23321db79c34.json': (188584, '863e69b43759840fca6017582dcc9915e5dcae604eea61b7453f7eee0783d011'),
    'a99faf782e8ad4d5f1ccdfcb7e143b9a.json': (3845890, '96b7ec09732c16e8b708cd6a1364b746edf5509b8103fdc28a95405373954d45'),
    'aa76e85e274bb7187a186c5ed9c90b43.json': (167803, 'cbe5c2095bd1607364bece8286f5fbbb013a480e2184e198c7b69c4f99d8ec07'),
    'ae345023ab5e1c09d49c2b2c6e311877.json': (111355, 'a031d3efdde885cb1f87a4d72ffbb2b71830a27a95018535755cc014c7315731'),
    'b159cbc7eb989d874a0337cbee8a373c.json': (679362, 'f71aabc10a6802d4ea194ebe1886973d013f07ee471fdc80e72bd735b270caba'),
    'b1f9b9baefa4c69d1d848e35c130e29d.json': (2478750, 'a512272b7541c3a6b5daaad8b97ec1183a7ec7abdd628bcaf38c120923129cec'),
    'b241cb7deedf9646f01fa15095ed96d2.json': (9036173, '709e51144202b1f7ad4f42f9fdb159039225de0414d9f2344708f2ad73bf16dd'),
    'b5576ffca7ad7cce0fc34b5aad7fc543.json': (903320, '5c057cdcfd3bfa38cbea3aa50cabfcdfad41295293da990da84dce3197c4d7dd'),
    'b69bcf49516121f03e5809cbd776c21f.json': (4087920, '3bed8fc1d547433320d838dfae9854dd3829e31644cf1a0776c0fb14ef9fec2a'),
    'b7f8fcd484777f9d330f24a2ff30dd25.json': (118194, 'af6cd317d57ac185f36413544ce2404139877403f6bcfe727014b4148ae5b9f9'),
    'b810534e7915119254ea6977a72493ae.json': (173274, '51ad4e57872449d3e20dcc7c11b5a86fd8fd68c5f334835b960b1d4258d05a20'),
    'b93b2145c5e2022c56bc2a50d5e94d8a.json': (1064160, '4d156f200843e036c9009f019d21f17d4133bd91ba0c8d61deb67c871daf9f66'),
    'bc9c8f8dc13a51d0cd6762bd325ab17e.json': (1696406, 'bb68236e3c4c9cf0373883362c5b093f18e6900e33451d65dd6ebca2bdda1115'),
    'bcaad76af172d10d2c7e4c257bf20d27.json': (113895, '07ded1cf1151d6a055eb12b2dc473452def3f8ed4015de6b5d6cd221a58df7c7'),
    'c60ad8608dd94271a6c6805eedfa26a8.json': (2972518, '94d794072fdb255d783d3352e5d12fa14c5afeea2705b4b4b46f34c0c5b8fd8b'),
    'cac8b6b2d84841d9a5177e399f0595b4.json': (854106, 'c5c3b6664e27d0f103b3085193ce19a5dee66f9f93a1f494069d17db339b41ba'),
    'cbefff615c15f4de61bd0ffd1ce97d2e.json': (169953, 'e80fd77e59adcb2c42c528f69a1fe3f106d5fa5746595e8a16958931ec7e28cf'),
    'd277cf50c742ad43ddf128587f59b363.json': (710279, 'dbc750c856f15a619585e174d6817588c1b20ee16d5bf83cbed0cee43b451f2a'),
    'd2868d12880a41ad5ed1fb3bb39159d5.json': (355786, 'cbd3fdd9ea9988ba7b00e0d249da35b0d2fe2b6046930c5c8109272e49131a46'),
    'd67a8ae853c0b8ed0e55f7fafe4e2f64.json': (170339, 'afd20683f9da19cb5b5404ae22d9e99a45a4dd5bb96ed498df8121db74f1f5d5'),
    'd7f2f823ff4d4d8bbec1039c6c302a06.json': (292878, '6cd21bdb86236b0bb8ffead2341cf82d17c36c089596e92e5294cedd74721eea'),
    'd857dc7d137db732306e97c3820652bd.json': (170423, 'fb468f7302815aefab6d3a644df7ac188939e9d48b01dc2ee9f0d19b6e0de0f4'),
    'd9a8dff7edce2d1b15ed4769886d9a2a.json': (276896, '3ca2f62a48912baae315d32f7ad87453db4ef2a1e48da2e1287a2274a22cc2a3'),
    'dbc070b918d4a052c0b686081408fb52.json': (102623, '99b6b6379c943b7ae477998c0591714d9fa3b1d0cb80a5b448315668edee7369'),
    'dcb89b6b049d424caf4c3e5fcd22c84c.json': (3338420, 'c0287f8677e9acfe5fcce46b34b6cdd81d6c9a148bb9c980f062fbaf8fdf59dc'),
    'e491d73ca2fd8a2a6f8984feb1c408a3.json': (249861, 'd3537742e037d1d5f8e193e043749fb7aed7442f85fe24217f5576f35618d7c8'),
    'e6ca28af6722fc00fc7294d1b291bea4.json': (112656, '6324f9dd35dea90e13a81ef37883214fec07a2a3cb8739679ba74f1f4b0e6874'),
    'e7d5dd0d36db95a40a4fbe258edd0aba.json': (1408978, '63853055044bdb1255aff09feeb4f4ef258422000f6856e224f5e4bf12963151'),
    'ea313eef484bb042ddb079771359c8e6.json': (632861, '53c477e46fa02f8c358c9eddf359ad31c81cf818ae6408a66b5fce0fa3273f80'),
    'eb42da715add1437eced9e494b0f62f7.json': (505204, '88279ddb5b4b5f7919b3656477d8cd72d0232573c54efa44216482cae17d0d4e'),
    'ee9335fbe7329b273a8d922bd3f73b84.json': (1323231, 'e680c967f3ede89032e43b491be97740d07f91e37fad614c0f7813e92873cdbb'),
    'ee939c276d2bdab808593f5121c52faf.json': (3002309, '441d4e245dd87ad758ded90f189cd1fdd2dea3fdd1c10a1273e81746285af1b8'),
    'ef0207e4427fe22aeb1c2105932b74d7.json': (1599241, 'ac0430e426a62d7cbdabc22d82f0ea4960043a81b254e98fa45b4d88a26acc2a'),
    'f04b425c107f7b972209528a46c407d9.json': (719807, '29df504c8f68f6dd5d37a60f093c7ed2ed68f60d4f98643292a3343c09f13115'),
    'f2de3b74884dc2312bb0fbf7c9867a9c.json': (104805, '958d2c59363fae288e4beac0f7d760b315692d98469e3c9f55a5ea1892dd5f12'),
    'f39aec9b8a61fd2aaed5849cc00bc165.json': (100117, '964fec0bd1817cdf2c435f049670e2f9482c16de8f22d943fcadfa04c1731436'),
    'f510c80d120dc75e4259704184ee802d.json': (121292, '1223349d5ccf99a135a6a8d1de138dfe64374ab0af8cf9483e9717a7eb7bf687'),
    'f5a297c9b9bc74ca0b1060b1c4c99c0f.json': (984343, 'af25caf28c81067b5cc34e09098992ec2e235b16db5a3d55a9b377fbef3cc868'),
    'f75d18151ad96809e922a80ebe2a171e.json': (112683, 'd29c66139e5b924a62dd6559a755247029ec26cb6c7ed1b4b244176e0a0bbb1c'),
    'f84e4dfe98f92d8d39a1e00115cd77df.json': (3438830, '67bdbe76123a1f6f68c8f1ee5d5485232976603c01214dedfe96eafe2387ff65'),
    'fa31e4af04a2469c88d6e8845e8aac69.json': (190224, '29e1db654ef84b9c0b7f170ab81004d9e42258e39a84934e4a53ca1e548909cb'),
    'fb3333ca30eb8af56d4f31839ca9e317.json': (112681, '85a14cc5fb25f8f7a04a168aa3cc9f67d968678517fb36b0109e96d6f09917c2'),
    'fcdcb46c7df316b571138b53bd3c822a.json': (279982, 'ca47fb705fdf307d88e9740e364edfd2cdbd10f1e0f6867f5984de3e790e8c55'),
}


def default_cache_dir() -> Path:
    return Path.home() / ".cache" / "ai-model-routing-evidence" / "trail"


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
        part = dest.with_name(dest.name + ".part")
        try:
            try:
                with urllib.request.urlopen(BASE_URL + name, timeout=TIMEOUT) as resp, open(part, "wb") as out:
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


def read_trace(path):
    """One UTF-8 JSON file; invalid UTF-8, invalid JSON or nesting too deep is a ValueError naming it.

    ``json`` raises a plain ValueError, not a JSONDecodeError, for a number with more digits than
    the interpreter converts to an int, so every ValueError is caught, not only JSONDecodeError.
    """
    try:
        with open(path, "rb") as f:
            return json.loads(f.read().decode("utf-8"))
    except (ValueError, RecursionError) as exc:
        raise ValueError(f"{Path(path).name}: not valid UTF-8 JSON ({type(exc).__name__}: {exc})") from exc


def _kind(value) -> str:
    """A short description of a refused value that never converts a long int to a string."""
    if isinstance(value, str):
        return repr(value) if len(value) <= 40 else f"a string of {len(value)} characters"
    return type(value).__name__


def _count(attrs: dict, key: str, where: str) -> int:
    value = attrs.get(key)
    if isinstance(value, str) and value and len(value) <= MAX_DIGITS and value.isascii() and value.isdigit():
        number = int(value)  # at most 19 digits, so far below any int-string limit
    elif isinstance(value, int) and not isinstance(value, bool):
        number = value
    else:
        raise ValueError(f"{where}: {key} is not a count of at most {MAX_DIGITS} ASCII digits or an int ({_kind(value)})")
    if not 0 <= number <= MAX_COUNT:
        raise ValueError(f"{where}: {key} is outside 0 to 2**63 - 1")
    return number


def runs(trace, name: str) -> list:
    """The sub-agent runs of one parsed trace file named ``name``, in depth-first file order."""
    if not isinstance(trace, dict):
        raise ValueError(f"{name}: not a JSON object")
    trace_id = trace.get("trace_id")
    if not isinstance(trace_id, str) or trace_id + ".json" != name:
        raise ValueError(f"{name}: trace_id is not a string equal to the file name without .json")
    spans = trace.get("spans")
    if not isinstance(spans, list):
        raise ValueError(f"{name}: spans is not a list")
    found = []
    # each entry: (span, below the top agent, the run it lies in or None); popped last first,
    # so children are pushed in reverse to be visited in list order
    stack = [(s, False, None) for s in reversed(spans)]
    while stack:
        node, in_top, run = stack.pop()
        if not isinstance(node, dict):
            raise ValueError(f"{name}: a span is not a JSON object")
        span_id = node.get("span_id")
        if not isinstance(span_id, str) or not span_id:
            raise ValueError(f"{name}: a span_id is not a non-empty string")
        where = f"{name}: span {span_id}"
        span_name = node.get("span_name")
        if not isinstance(span_name, str):
            raise ValueError(f"{where}: span_name is not a string")
        children = node.get("child_spans", [])
        if not isinstance(children, list):
            raise ValueError(f"{where}: child_spans is not a list")
        if span_name == RUN:
            if run is not None:
                raise ValueError(f"{where}: a {RUN} span inside the run {run['span_id']}, whose model calls it would share")
            if not in_top:
                raise ValueError(f"{where}: a {RUN} span with no {TOP} ancestor")
            run = {"trace_id": trace_id, "span_id": span_id, "model_calls": 0, "prompt_tokens": 0,
                   "completion_tokens": 0, "first_call_prompt_tokens": None}
            found.append(run)
        elif run is not None and span_name.endswith(CALL_SUFFIX):
            attrs = node.get("span_attributes")
            if not isinstance(attrs, dict):
                raise ValueError(f"{where}: span_attributes is not a JSON object")
            prompt, completion = (_count(attrs, key, where) for key in COUNT_KEYS)
            run["model_calls"] += 1
            run["prompt_tokens"] += prompt
            run["completion_tokens"] += completion
            if run["first_call_prompt_tokens"] is None:
                run["first_call_prompt_tokens"] = prompt
        below_top = in_top or span_name == TOP
        stack.extend((child, below_top, run) for child in reversed(children))
    for run in found:
        if not run["model_calls"]:
            raise ValueError(f"{name}: span {run['span_id']}: a {RUN} span with no model call")
    return found


def summarize(per_trace) -> dict:
    """Counts and min, median and max over the runs of every trace read (one ``runs`` list each)."""
    if not isinstance(per_trace, (list, tuple)) or not per_trace:
        raise ValueError("per_trace must be a non-empty list or tuple of runs lists")
    rows, seen = [], set()
    for entry in per_trace:
        if not isinstance(entry, list):
            raise ValueError("an entry of per_trace is not a list")
        for row in entry:
            key = (row["trace_id"], row["span_id"])
            if key in seen:
                raise ValueError(f"run {key[1]} of trace {key[0]} repeats")
            seen.add(key)
            rows.append(dict(row))
    if not rows:
        raise ValueError("no trace has a sub-agent run")
    stats = {}
    for key in STAT_KEYS:
        values = [row[key] for row in rows]
        stats[key] = {"min": min(values), "median": float(statistics.median(values)), "max": max(values)}
    return {
        "source": {"repo": REPO_URL, "folder": FOLDER, "revision": REVISION, "licence": LICENCE},
        "traces": len(per_trace),
        "traces_with_runs": sum(1 for entry in per_trace if entry),
        "run_count": len(rows),
        "stats": stats,
        "runs": rows,
    }


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
    parser = _Parser(prog="summary.py", description="TRAIL GAIA sub-agent runs to a small summary")
    parser.add_argument("--out", required=True, help="output JSON path")
    parser.add_argument("--cache", default=None, help=f"download folder (default: {default_cache_dir()})")
    try:
        args = parser.parse_args(argv)
        out = _check_out(args.out)
        part = out.with_name(out.name + ".part")
        try:  # on any failure from here on, <out>.part goes, a stale one from an earlier run included
            root = fetch(args.cache)
            summary = summarize([runs(read_trace(root / name), name) for name in FILES])
            with open(part, "w", encoding="utf-8") as f:
                f.write(json.dumps(summary, indent=2) + "\n")
            # print before the rename, so a write to stdout that fails leaves --out as it was
            print_report(json.dumps({key: value for key, value in summary.items() if key != "runs"}, indent=2))
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
