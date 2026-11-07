"""TRAIL summary contract (DESIGN 13.11, v1.67 and v1.68), written before the script and kept as its tests.

The script is a standard-library file outside the package (``evidence/trail/summary.py``), so it is
loaded from its path by an autouse fixture. Every test uses small synthetic traces shaped like a
trace file (top keys ``trace_id`` and ``spans``, spans nested through ``child_spans``), except the
last, which reads the pinned files only when all 117 are already in the default cache and skips
otherwise (CI never downloads them).
"""

import ast
import contextlib
import copy
import hashlib
import importlib.util
import io
import json
import re
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "evidence" / "trail" / "summary.py"
REVISION = "0ffbed9db859b4a66250dc783fa4dccf86869595"
FOLDER = "benchmarking/data/GAIA"
REPO_URL = "https://github.com/patronus-ai/trail-benchmark"
BASE_URL = f"https://raw.githubusercontent.com/patronus-ai/trail-benchmark/{REVISION}/{FOLDER}/"
PINNED = [
    ('0035f455b3ff2295167a844f04d85d34.json', 112904, 'a8b31d38493a22091788f99e32beb79b801e35269f626b6a0de0446f435df38e'),
    ('0140b3f657eddf76ca82f72c49ac8e58.json', 1947451, 'e84a09e9a2bb6a4636cb25d5797ea264d70bf61c21688e13576962a097f40082'),
    ('01c5727165fc43899b3b594b9bef5f19.json', 1883610, '1c7af97a7da891b7c9af5fab49155998c18ba310392adefe3beb8efae7e1ad8a'),
    ('0242ca2533fac5b8b604a9060b3e15d6.json', 204183, '3d5e848670a47911bffaa83510f2208574e1273fe6119bc318691336cf8e1dfb'),
    ('041b7f9c8c76c2ca1a8e67c6769267c3.json', 202711, '9c64cf910af66741b60159b85fd963473f5adff9bfb29a5d7b65424b20944597'),
    ('08be1639c58e086cf0bb8c269039973d.json', 115103, '3c0e4ea703b94ccbd6841458d12a00f755ac5d1aa1589c8a4b09c49b37787009'),
    ('0adc4f3b99d9564d32811e913cc9d248.json', 141822, 'd81e7c493cd0165a26e73fafbabb6250ed2b40caafe636424aca06181bfeb60d'),
    ('0ebe673d64647ec44c370638b82d3c78.json', 96308, 'c5ae6df75d598faf1cabf435c71e6d38fd71234993779638ed51b3915115696b'),
    ('1427b326e21963a1228647ad8dff2bf4.json', 103282, '6aa519c0dda8927fc058fffb603953cba9674ae1abb2628655d1e377af9b8c8d'),
    ('14be0e98b825d2da5665e2e10f6cc927.json', 3397097, '08ed86430941f84ffcd41326f29adb535b9dd86412e98d7dce78fb8b333392d7'),
    ('18efa24e637b9423f34180d1f2041d3e.json', 173289, '600eb4162dc9f15beb893492443bab51263a453eb39ff3fb54eaf89621681631'),
    ('1dd91d388cb4889e6c1f5ea5ca06bce6.json', 215421, 'd9e013704be35d70d12981efe1f0c336bf1c67ea7c2e34a0a1b9498c38746b6c'),
    ('21f0c6c8d76ac61f4388f36ddffe1c38.json', 761074, '5e701fb4e747b7e796fc482af06dd46c62c31a0aa79e781570b238566114497e'),
    ('2209204b631e26f4cee4dc3dd995608c.json', 161082, 'c353c36ed98de9595021fffc38564cf14f61a187e0569d04d5d1778718ea2d52'),
    ('25c8275651013fe8398ef0f735eb0912.json', 117267, 'd86ff3040e09bc28a7d2f907e3e759c3012932a83eccd91917bcae7a6e6f778d'),
    ('2713fa0aa73f0c5a8b480f026c21a547.json', 112016, '8554cfe0b118a90d90706636ce8fb5e76686635823e78878354ef0529cbc1a5b'),
    ('27a6c5ebc3311542156fdde857a0035f.json', 106850, 'b5f001a41da09278702ad6ad3ee733fbb0b414fbb8762912e7117d45588f2060'),
    ('2c77a8feec544cc61a00a387ad792a13.json', 428027, 'bfd6e7a90d8f725f9330a3fb04cfe3dcbc8bd1ae9b975d8e3192f2bbf6a02576'),
    ('2cb6924caac94b32d2bf4b40bdf4ab51.json', 1294017, '2db165afbd1aebe5f462bdccd3bea7efe34aaa477e96718ad042006bc2aeb18f'),
    ('3205fa0cb2135fe671bf7cd0e5a26151.json', 1223468, '46c15dae62863ceddfb20086c718ac28e1c75b9ea1a0e76bf872d0e46c0ef4c0'),
    ('3215fc75e81bdb73706a4fb37b66427f.json', 325859, 'fcf4984dc053188415378fc37bd4c33e2bdb63ae355a2cb02e610b19fdb55c26'),
    ('331aece579d942bb4c345a86c86efb83.json', 341917, '98d88e4c5c9e03d22f2a43d4acc4157487bb139b5f7cbd789c3a2523c6d63bf2'),
    ('33cedc57294f33839f1acc3ee5182788.json', 1482985, '452a73a234d0ae503394dd138c3f86c82a8f24df4e1a3c155c978c2d719b0ae3'),
    ('3637c5845140adbf29c565923c20e94d.json', 172062, 'a25bb60ee0e450cf7770d2dea91910be5c9e4f71bfd4975c8b5d3c82c548a627'),
    ('387546b0d3e81503bd8d392c6f1b6b25.json', 1150604, 'e84f1766cf5c63112f31e250315c45e9b30f176342d2d06e771a869a788aba33'),
    ('396b6aa1ab86eb2e20d27582eb5eebd9.json', 3850721, 'a2280309f3079a3de8ae88a00abf9179a5bcb500c380e31611325b453b2a5a02'),
    ('3acaa3150977e199eddb95c64f2ada2e.json', 710863, 'cee9269e6af749801976f88d31ecbcd831b498987fdb98aae07def1af3e5f20c'),
    ('3f05ba33cd4ae18ccba6db9a5749c16f.json', 117699, '77e13ff6682f01fc02dc6cce7f6f29fb38abf26938fd835b3f07d9b7d43ee219'),
    ('41b597524173272503073a0799ac523c.json', 111153, '324d499507ef067a9d3c39afdec12aa9685f16316b1275e61e5db8e01646d320'),
    ('41bbc898aa7de0f31d2382ff57700a76.json', 355258, 'fafa19f63b0150d4c3d3f681e827f43cc747a98feb820bfe82e108c4a2d21bee'),
    ('4514626d62ed350ee7878c03f51bbe68.json', 170856, '42098ba835bda520ca4c1af1679b318d31b6ca219c36240dbcf961eadda1e23f'),
    ('4a8d094e92433f1ba1da21f602c417d9.json', 157661, '349545effc314bfb66f1d130fc647937e7ceb32c8da8e0e10c4b907347a78aab'),
    ('4ae16319f0de44a7d1e84595b41ae08d.json', 104326, '2eb75cb772183919e35a683d32a89021e81eff5e6641e1efa318f2e78c186d2c'),
    ('4c79c8ba0cf1e8fcb1c408d53016c560.json', 110797, '4750a188617b04c0bf4b633039ec0f4a6f1dabe6988c2d47ac54f51f366a41d8'),
    ('512475a321c616e45337da3575f6a185.json', 440492, '312b64754b2e2b75c7da999922f7441e802c4db66091981267715b02101d37fd'),
    ('53dba4241b22d5039c9c119871c7c8b4.json', 111542, '708401da46871a0fe1be263d7e236ae7d83e483a652c5f3fda34f20c814b8117'),
    ('59365b27641e501d105b0e8f5e7c5af7.json', 2727320, '2f86c6a062b7da8d4a606f7437850f9370f6125b08994b524ab64fd2034f63f6'),
    ('5a6c51d59f870513c68745e2e0f9269f.json', 2012000, '1e07edbab3dadd3e0506135629db1352d0ede1973b542bc4f0fb1d165e33d37a'),
    ('5b5a35053775cbf29701c171e6675853.json', 351726, 'd74231ba38fd41e6fa9df1376727e86e5c1d534d694c2f4473d69a178e63a40e'),
    ('5bbd1534b199c57861f55b58be9949a0.json', 2332912, '355c14a8ed0aa031c4a35d8f73e3c8f0a23a1f0c8c29b4ccbb3c08928f29de75'),
    ('5dc4cf8d5175f2782f46265456998d39.json', 276683, '69f320cf97cbe2a6bf9c2d9af5c7dabe3280ce81a368c2c29ab133690812493f'),
    ('5e5dc94e090341c564d582f551a0cddb.json', 98651, '18f478d7594e7a674ef0390c7aacf76d9fceae92aeb86a3f6f86e5cd82f97862'),
    ('5ec1cd43eb8ae4094e93a4892ff0f06f.json', 107243, 'cbd695bd052f53f5bc469be5ca096ad28e8fe747b396519f286ab01911756aa9'),
    ('5f3a0a7fc572f49630c069e4e5a64ae3.json', 2038572, '448b7f75cf4ba4c6bf03f2e1322eea1ff503ce85e18e66cb87b2d6d422feb596'),
    ('62df2a06b647ca730391602dbf62f843.json', 118111, '971f74434274dcc320c0a48f5df6432b5b471a78a68d665269616b9207339ee0'),
    ('63ac9e03bf750e58eecbc5b148d8d215.json', 215613, '3f791af084cf95ab47e10dc8ef64165774ac50e137d90e8856a703c2a99fc57e'),
    ('672d36d8ecc4816738433c75136eb99d.json', 457442, 'bd102c94f882966ce2de3e66f1930403fe794735afd00f8932a1c4a869ee1a2d'),
    ('6cc6dc35a28bbed6cfd873756094bc16.json', 4455935, '3bf275fa692e460283d3838232023d043c7c40fa4c3309fe4426688be33e005a'),
    ('6d5b91f06e5a7377d4798be65fe46e97.json', 204247, '93ab881af8c20288d3a09ba0218acb0c107336b5adf48ff45015a058a5054577'),
    ('6e64c2e543327a7c2f2ce3d26ced94d1.json', 180673, 'b548db1abcc853b82004ef1a482e3f474f63f549a39d9053d91cccfcef38e5d1'),
    ('6f0ede30602ae3fe2ced3f9fabb008a6.json', 113916, 'b1747586c5edcf1df0de5840d98a92d7991d3ad7ea374eacba5211cddcc7835d'),
    ('72877db591837666d500b459fb3cf29d.json', 121491, '24188f2793a9a902ea176f355d1dc518ec4e9733de71ac9b0e9e362a01f55170'),
    ('75121379e11c550f3ca58e17c972266b.json', 126997, '5e25910f09f686cbbd9f9362e6765fb16ea39264e2f376a866c93fb4c0b7a91a'),
    ('772605f0794b0fa96bc942a8a7736571.json', 776653, '0867fcbe73baf772e5e1271a492f0778ddcd711a9caddfe3ab537d2f74ca3d74'),
    ('7bf0addde339e4cac9dd3b772232a7e0.json', 328299, '924cb726299c95847df510326a80b1170e0ade6096b8c40f86e8b46bf76666eb'),
    ('7c98d39b2699d41fa913f8fbe60c04ed.json', 107615, '85a7ee419fe42ea186924d4b1e52d019b88b7c41760c596189c9fdd84d6eae3e'),
    ('7ee8e8df6e8cd101d9af8a4a4f6ceedb.json', 429936, 'e3a70008f0f1ec229f38ba3992b908915170b4311aae6d83f56392bc88e158b6'),
    ('85c14ced5177cdad83f1f1f898a1c6c7.json', 268536, '3f060340213e1de7847ef285a87e44c9dfc7957ff3e413bc9376ca3899248ac8'),
    ('860f9d45f2e50bfecb190bb26eff1f32.json', 8509773, '875115e7df807b89d1ed076cccac5966711a593e10f273379086561e11420983'),
    ('876eb108c8650d4ada63a8d39aa1e96c.json', 264076, '1ffc0da2330ec763b1e54032dd8f9210fa61bb13f97b5b86b11a15538d802fb6'),
    ('88c63c780aba1f23c3c5345aa340d7e2.json', 123525, '4739dca68eb9a922644e218bd891a1849a6f1c21c2b4322ca6e19b457a5590bf'),
    ('88e4ce6a659df42a4146331fff36417c.json', 248213, 'd7286542371531a43852c81eda2405e1013c6e69153dc59ab8e83a491687c510'),
    ('911e853f02d03e976dbf0c16f653ab57.json', 105087, 'ab524c8c0ccb69ffbf4eff99ac0532e3af8434fd60d0767a357bc838f4554ab1'),
    ('915d2c66879657f694f88e0ed6f02cf5.json', 7573525, '9c2eb82fa8f7016521b30da757b4ae3aecadd77fe172fd37ee875628e27694f0'),
    ('96be1bf61f2915e52ec59173b9bd9828.json', 107678, '7c58b85ca92292c6a4f4597fc3c9f9edb0ea11767417dc933c26304bcb8ab24e'),
    ('99f6b447779ba86b3cff2caede832d59.json', 156271, 'd169bf4378edeb94d3707033f09a59ccb8ff7a7a7e7a2dc9c743a3e07588e583'),
    ('9cd6dc7c0af658a87f603b488950f409.json', 124497, '116e96e4d9a9a6dd4559c9e1ad184c83d927d730e70bc15c206a16906158bb62'),
    ('9e67afe0ff4eca1558073c2e5cfbf876.json', 104584, '4c181ba2c7b7ea1bd0f64ae7884720e78ae20c2237caaa06cf60d40d8ee0f14d'),
    ('9ec7d4a8ab8c74ab56361ef29d1b1660.json', 121140, 'ae79dad30504503a6d2fce9c4de512bd7ee2d1c99c58065e8bf91ca8988b1c40'),
    ('a041b8d88e3fedcc7d387da328f8a3b4.json', 227567, '03fb25d11fce3f8ad03c4f06d87ebf33c241c5d6db59d89476926ca9a5ad2c1a'),
    ('a32806e19bac45a34d3712ccc433ec9d.json', 1018299, '8283c0eeb589d54fc3e64e4e58b14f2e0c09123ffa6141c37f9bcb4aea28f9d6'),
    ('a4af6c6d200e6d19d7f24e1d1d688188.json', 155772, 'e4e93c154ca2dc20da16d3da7ea4a462656ae0288262113c4a03c80d4317e666'),
    ('a5c2947f441d65edf60131463fb79999.json', 2750655, 'a1ebd4ea21f9df817121b27b179cef081b45b3ffd292cb3e7c7c3d40117a9581'),
    ('a7017f40866dd77c6c0c0e98bad17f69.json', 174322, '962f13b23c5668696e5bcab73f259a70a13d8f3520ecf745aaded0ea5b63cfbb'),
    ('a96c6811716c0473b86a23321db79c34.json', 188584, '863e69b43759840fca6017582dcc9915e5dcae604eea61b7453f7eee0783d011'),
    ('a99faf782e8ad4d5f1ccdfcb7e143b9a.json', 3845890, '96b7ec09732c16e8b708cd6a1364b746edf5509b8103fdc28a95405373954d45'),
    ('aa76e85e274bb7187a186c5ed9c90b43.json', 167803, 'cbe5c2095bd1607364bece8286f5fbbb013a480e2184e198c7b69c4f99d8ec07'),
    ('ae345023ab5e1c09d49c2b2c6e311877.json', 111355, 'a031d3efdde885cb1f87a4d72ffbb2b71830a27a95018535755cc014c7315731'),
    ('b159cbc7eb989d874a0337cbee8a373c.json', 679362, 'f71aabc10a6802d4ea194ebe1886973d013f07ee471fdc80e72bd735b270caba'),
    ('b1f9b9baefa4c69d1d848e35c130e29d.json', 2478750, 'a512272b7541c3a6b5daaad8b97ec1183a7ec7abdd628bcaf38c120923129cec'),
    ('b241cb7deedf9646f01fa15095ed96d2.json', 9036173, '709e51144202b1f7ad4f42f9fdb159039225de0414d9f2344708f2ad73bf16dd'),
    ('b5576ffca7ad7cce0fc34b5aad7fc543.json', 903320, '5c057cdcfd3bfa38cbea3aa50cabfcdfad41295293da990da84dce3197c4d7dd'),
    ('b69bcf49516121f03e5809cbd776c21f.json', 4087920, '3bed8fc1d547433320d838dfae9854dd3829e31644cf1a0776c0fb14ef9fec2a'),
    ('b7f8fcd484777f9d330f24a2ff30dd25.json', 118194, 'af6cd317d57ac185f36413544ce2404139877403f6bcfe727014b4148ae5b9f9'),
    ('b810534e7915119254ea6977a72493ae.json', 173274, '51ad4e57872449d3e20dcc7c11b5a86fd8fd68c5f334835b960b1d4258d05a20'),
    ('b93b2145c5e2022c56bc2a50d5e94d8a.json', 1064160, '4d156f200843e036c9009f019d21f17d4133bd91ba0c8d61deb67c871daf9f66'),
    ('bc9c8f8dc13a51d0cd6762bd325ab17e.json', 1696406, 'bb68236e3c4c9cf0373883362c5b093f18e6900e33451d65dd6ebca2bdda1115'),
    ('bcaad76af172d10d2c7e4c257bf20d27.json', 113895, '07ded1cf1151d6a055eb12b2dc473452def3f8ed4015de6b5d6cd221a58df7c7'),
    ('c60ad8608dd94271a6c6805eedfa26a8.json', 2972518, '94d794072fdb255d783d3352e5d12fa14c5afeea2705b4b4b46f34c0c5b8fd8b'),
    ('cac8b6b2d84841d9a5177e399f0595b4.json', 854106, 'c5c3b6664e27d0f103b3085193ce19a5dee66f9f93a1f494069d17db339b41ba'),
    ('cbefff615c15f4de61bd0ffd1ce97d2e.json', 169953, 'e80fd77e59adcb2c42c528f69a1fe3f106d5fa5746595e8a16958931ec7e28cf'),
    ('d277cf50c742ad43ddf128587f59b363.json', 710279, 'dbc750c856f15a619585e174d6817588c1b20ee16d5bf83cbed0cee43b451f2a'),
    ('d2868d12880a41ad5ed1fb3bb39159d5.json', 355786, 'cbd3fdd9ea9988ba7b00e0d249da35b0d2fe2b6046930c5c8109272e49131a46'),
    ('d67a8ae853c0b8ed0e55f7fafe4e2f64.json', 170339, 'afd20683f9da19cb5b5404ae22d9e99a45a4dd5bb96ed498df8121db74f1f5d5'),
    ('d7f2f823ff4d4d8bbec1039c6c302a06.json', 292878, '6cd21bdb86236b0bb8ffead2341cf82d17c36c089596e92e5294cedd74721eea'),
    ('d857dc7d137db732306e97c3820652bd.json', 170423, 'fb468f7302815aefab6d3a644df7ac188939e9d48b01dc2ee9f0d19b6e0de0f4'),
    ('d9a8dff7edce2d1b15ed4769886d9a2a.json', 276896, '3ca2f62a48912baae315d32f7ad87453db4ef2a1e48da2e1287a2274a22cc2a3'),
    ('dbc070b918d4a052c0b686081408fb52.json', 102623, '99b6b6379c943b7ae477998c0591714d9fa3b1d0cb80a5b448315668edee7369'),
    ('dcb89b6b049d424caf4c3e5fcd22c84c.json', 3338420, 'c0287f8677e9acfe5fcce46b34b6cdd81d6c9a148bb9c980f062fbaf8fdf59dc'),
    ('e491d73ca2fd8a2a6f8984feb1c408a3.json', 249861, 'd3537742e037d1d5f8e193e043749fb7aed7442f85fe24217f5576f35618d7c8'),
    ('e6ca28af6722fc00fc7294d1b291bea4.json', 112656, '6324f9dd35dea90e13a81ef37883214fec07a2a3cb8739679ba74f1f4b0e6874'),
    ('e7d5dd0d36db95a40a4fbe258edd0aba.json', 1408978, '63853055044bdb1255aff09feeb4f4ef258422000f6856e224f5e4bf12963151'),
    ('ea313eef484bb042ddb079771359c8e6.json', 632861, '53c477e46fa02f8c358c9eddf359ad31c81cf818ae6408a66b5fce0fa3273f80'),
    ('eb42da715add1437eced9e494b0f62f7.json', 505204, '88279ddb5b4b5f7919b3656477d8cd72d0232573c54efa44216482cae17d0d4e'),
    ('ee9335fbe7329b273a8d922bd3f73b84.json', 1323231, 'e680c967f3ede89032e43b491be97740d07f91e37fad614c0f7813e92873cdbb'),
    ('ee939c276d2bdab808593f5121c52faf.json', 3002309, '441d4e245dd87ad758ded90f189cd1fdd2dea3fdd1c10a1273e81746285af1b8'),
    ('ef0207e4427fe22aeb1c2105932b74d7.json', 1599241, 'ac0430e426a62d7cbdabc22d82f0ea4960043a81b254e98fa45b4d88a26acc2a'),
    ('f04b425c107f7b972209528a46c407d9.json', 719807, '29df504c8f68f6dd5d37a60f093c7ed2ed68f60d4f98643292a3343c09f13115'),
    ('f2de3b74884dc2312bb0fbf7c9867a9c.json', 104805, '958d2c59363fae288e4beac0f7d760b315692d98469e3c9f55a5ea1892dd5f12'),
    ('f39aec9b8a61fd2aaed5849cc00bc165.json', 100117, '964fec0bd1817cdf2c435f049670e2f9482c16de8f22d943fcadfa04c1731436'),
    ('f510c80d120dc75e4259704184ee802d.json', 121292, '1223349d5ccf99a135a6a8d1de138dfe64374ab0af8cf9483e9717a7eb7bf687'),
    ('f5a297c9b9bc74ca0b1060b1c4c99c0f.json', 984343, 'af25caf28c81067b5cc34e09098992ec2e235b16db5a3d55a9b377fbef3cc868'),
    ('f75d18151ad96809e922a80ebe2a171e.json', 112683, 'd29c66139e5b924a62dd6559a755247029ec26cb6c7ed1b4b244176e0a0bbb1c'),
    ('f84e4dfe98f92d8d39a1e00115cd77df.json', 3438830, '67bdbe76123a1f6f68c8f1ee5d5485232976603c01214dedfe96eafe2387ff65'),
    ('fa31e4af04a2469c88d6e8845e8aac69.json', 190224, '29e1db654ef84b9c0b7f170ab81004d9e42258e39a84934e4a53ca1e548909cb'),
    ('fb3333ca30eb8af56d4f31839ca9e317.json', 112681, '85a14cc5fb25f8f7a04a168aa3cc9f67d968678517fb36b0109e96d6f09917c2'),
    ('fcdcb46c7df316b571138b53bd3c822a.json', 279982, 'ca47fb705fdf307d88e9740e364edfd2cdbd10f1e0f6867f5984de3e790e8c55'),
]
RUN_KEYS = ["trace_id", "span_id", "model_calls", "prompt_tokens", "completion_tokens", "first_call_prompt_tokens"]
SUMMARY_KEYS = ["source", "traces", "traces_with_runs", "run_count", "stats", "runs"]
STAT_KEYS = ["model_calls", "prompt_tokens", "completion_tokens", "first_call_prompt_tokens"]
STDLIB = {"argparse", "hashlib", "json", "statistics", "sys", "urllib", "pathlib"}
TID = "0123456789abcdef0123456789abcdef"
NAME = TID + ".json"


def load_tr():
    if not SCRIPT.is_file():
        raise ModuleNotFoundError(f"no script at {SCRIPT.name}")
    spec = importlib.util.spec_from_file_location("trail_summary", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture(autouse=True)
def tr():
    return load_tr()


def span(name, sid, *children, **attrs):
    return {"timestamp": "2025-03-19T16:48:09.190915Z", "span_id": sid, "parent_span_id": None,
            "span_name": name, "span_attributes": dict(attrs), "child_spans": list(children)}


def call(sid, prompt, completion):
    return span("LiteLLMModel.__call__", sid, **{"llm.token_count.prompt": str(prompt),
                                                 "llm.token_count.completion": str(completion),
                                                 "llm.model_name": "o3-mini"})


def sample_trace(tid=TID):
    """main > answer > CodeAgent.run holding two sub-agent runs, r1 (3 calls) and r2 (1 call)."""
    r1 = span("ToolCallingAgent.run", "r1",
              call("c", 5, 3),
              span("Step 1", "s11", call("d", 7, 4), span("SearchInformationTool", "t1")),
              call("e", 9, 5),
              **{"llm.token_count.prompt": "999", "llm.token_count.completion": "999"})
    r2 = span("ToolCallingAgent.run", "r2", call("f", 100, 6))
    top = span("CodeAgent.run", "top",
               call("a", 10, 1),
               span("Step 1", "s1", call("b", 20, 2), r1),
               span("Step 2", "s2", r2))
    outside = span("LiteLLMModel.__call__", "x")  # no token counts, outside any run
    return {"trace_id": tid, "spans": [span("main", "m", span("answer_single_question", "q", top, outside))]}


def run_row(trace_id, span_id, calls, prompt, completion, first):
    return {"trace_id": trace_id, "span_id": span_id, "model_calls": calls, "prompt_tokens": prompt,
            "completion_tokens": completion, "first_call_prompt_tokens": first}


def find(trace, sid):
    stack = list(trace["spans"])
    while stack:
        s = stack.pop()
        if s["span_id"] == sid:
            return s
        stack.extend(s.get("child_spans", []))
    raise KeyError(sid)


# --- source pins -------------------------------------------------------------------------

def test_source_constants(tr):
    assert tr.REVISION == REVISION
    assert tr.LICENCE == "MIT"
    assert tr.FOLDER == FOLDER
    assert tr.REPO_URL == REPO_URL
    assert tr.BASE_URL == BASE_URL


def test_files_pinned_in_name_order(tr):
    assert list(tr.FILES) == [n for n, _, _ in PINNED]
    assert list(tr.FILES) == sorted(tr.FILES)
    for name, size, sha in PINNED:
        assert tr.FILES[name] == (size, sha)
        assert re.fullmatch(r"[0-9a-f]{32}\.json", name)
    assert len(tr.FILES) == 117
    assert sum(size for size, _ in tr.FILES.values()) == 111_205_744
    assert min(size for size, _ in tr.FILES.values()) == 96_308
    assert max(size for size, _ in tr.FILES.values()) == 9_036_173


def test_default_cache_dir(tr):
    assert tr.default_cache_dir() == Path.home() / ".cache" / "ai-model-routing-evidence" / "trail"


def test_standard_library_only(tr):
    tree = ast.parse(SCRIPT.read_text(encoding="utf-8"))
    names = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names |= {a.name.split(".")[0] for a in node.names}
        elif isinstance(node, ast.ImportFrom):
            assert node.level == 0
            names.add(node.module.split(".")[0])
    assert names <= STDLIB
    assert "model_routing" not in names


def test_script_never_names_the_gated_copy(tr):
    text = SCRIPT.read_text(encoding="utf-8")
    assert "huggingface" not in text.lower()


# --- verify, fetch, read_trace -------------------------------------------------------------

def test_verify(tr, tmp_path):
    f = tmp_path / "a.json"
    f.write_bytes(b"{}")
    tr.verify(f, 2, hashlib.sha256(b"{}").hexdigest())
    with pytest.raises(ValueError, match="a.json"):
        tr.verify(f, 3, hashlib.sha256(b"{}").hexdigest())
    with pytest.raises(ValueError, match="a.json"):
        tr.verify(f, 2, "0" * 64)


def fake_files(monkeypatch, tr, contents):
    files = {name: (len(data), hashlib.sha256(data).hexdigest()) for name, data in sorted(contents.items())}
    monkeypatch.setattr(tr, "FILES", files)
    return files


def test_fetch_downloads_into_the_cache(tr, monkeypatch, tmp_path):
    data = {"b" * 32 + ".json": b"{\"x\": 1}", "a" * 32 + ".json": b"{\"x\": 2}"}
    fake_files(monkeypatch, tr, data)
    seen = []

    def urlopen(url, timeout=None):
        seen.append((url, timeout))
        return io.BytesIO(data[url[len(BASE_URL):]])

    monkeypatch.setattr(tr.urllib.request, "urlopen", urlopen)
    cache = tmp_path / "cache"
    assert tr.fetch(cache) == cache
    assert seen == [(BASE_URL + "a" * 32 + ".json", 60), (BASE_URL + "b" * 32 + ".json", 60)]
    for name, body in data.items():
        assert (cache / name).read_bytes() == body
    assert not list(cache.rglob("*.part"))
    seen.clear()
    tr.fetch(cache)
    assert seen == []


def test_fetch_bad_present_file_is_kept_and_refused(tr, monkeypatch, tmp_path):
    fake_files(monkeypatch, tr, {NAME: b"{}"})
    (tmp_path / NAME).write_bytes(b"[]")
    with pytest.raises(ValueError, match=NAME):
        tr.fetch(tmp_path)
    assert (tmp_path / NAME).read_bytes() == b"[]"


def test_fetch_bad_download_leaves_no_part(tr, monkeypatch, tmp_path):
    fake_files(monkeypatch, tr, {NAME: b"{}"})
    monkeypatch.setattr(tr.urllib.request, "urlopen", lambda url, timeout=None: io.BytesIO(b"[]"))
    with pytest.raises(ValueError):
        tr.fetch(tmp_path)
    assert not (tmp_path / NAME).exists()
    assert not list(tmp_path.rglob("*.part"))


def test_fetch_wraps_download_errors_as_oserror(tr, monkeypatch, tmp_path):
    fake_files(monkeypatch, tr, {NAME: b"{}"})

    def boom(url, timeout=None):
        raise RuntimeError("protocol")

    monkeypatch.setattr(tr.urllib.request, "urlopen", boom)
    with pytest.raises(OSError, match=NAME):
        tr.fetch(tmp_path)
    assert not list(tmp_path.rglob("*.part"))


@pytest.mark.parametrize("data", [b"\xff\xfe", b"{\"a\":", b"[" * 100000])
def test_read_trace_refuses(tr, tmp_path, data):
    f = tmp_path / "bad.json"
    f.write_bytes(data)
    with pytest.raises(ValueError, match="bad.json"):
        tr.read_trace(f)


def test_read_trace_names_the_file_for_a_number_past_the_int_limit(tr, tmp_path):
    limit = sys.get_int_max_str_digits() if hasattr(sys, "get_int_max_str_digits") else 0
    if not limit:
        pytest.skip("this interpreter converts digit strings of any length")
    f = tmp_path / "bad.json"
    f.write_bytes(b'{"a": ' + b"1" * (limit + 1) + b"}")
    with pytest.raises(ValueError, match="bad.json"):
        tr.read_trace(f)


def test_read_trace_reads_json(tr, tmp_path):
    f = tmp_path / NAME
    f.write_text(json.dumps(sample_trace()), encoding="utf-8")
    assert tr.read_trace(f) == sample_trace()


# --- runs ----------------------------------------------------------------------------------

def test_runs_in_walk_order(tr):
    assert tr.runs(sample_trace(), NAME) == [run_row(TID, "r1", 3, 21, 12, 5), run_row(TID, "r2", 1, 100, 6, 100)]


def test_run_keys_in_order(tr):
    for row in tr.runs(sample_trace(), NAME):
        assert list(row) == RUN_KEYS
        for key in RUN_KEYS[2:]:
            assert type(row[key]) is int


def test_run_span_own_counts_are_never_read(tr):
    trace = sample_trace()
    attrs = find(trace, "r1")["span_attributes"]
    attrs["llm.token_count.prompt"] = "not a number"
    attrs["llm.token_count.completion"] = True
    assert tr.runs(trace, NAME)[0] == run_row(TID, "r1", 3, 21, 12, 5)


def test_int_counts_are_accepted(tr):
    trace = sample_trace()
    find(trace, "d")["span_attributes"].update({"llm.token_count.prompt": 7, "llm.token_count.completion": 0})
    assert tr.runs(trace, NAME)[0] == run_row(TID, "r1", 3, 21, 8, 5)


def test_counts_up_to_the_int64_max_are_accepted(tr):
    trace = sample_trace()
    find(trace, "d")["span_attributes"].update({"llm.token_count.prompt": str(INT64_MAX),
                                               "llm.token_count.completion": INT64_MAX})
    find(trace, "e")["span_attributes"]["llm.token_count.prompt"] = "0" * 18 + "9"
    assert tr.runs(trace, NAME)[0] == run_row(TID, "r1", 3, 5 + INT64_MAX + 9, 3 + INT64_MAX + 5, 5)


def test_a_deep_tree_of_spans_is_walked_without_recursion(tr):
    trace = sample_trace()
    node = call("deep", 2, 1)
    for i in range(5000):
        node = span("Step", f"n{i}", node)
    find(trace, "r2")["child_spans"].append(node)
    assert tr.runs(trace, NAME)[1] == run_row(TID, "r2", 2, 102, 7, 100)


def test_first_call_is_first_in_walk_order_not_by_timestamp(tr):
    trace = sample_trace()
    find(trace, "c")["timestamp"] = "2099-01-01T00:00:00Z"
    assert tr.runs(trace, NAME)[0]["first_call_prompt_tokens"] == 5


def test_any_span_name_ending_in_dot_call_is_a_model_call(tr):
    trace = sample_trace()
    find(trace, "f")["span_name"] = "OpenAIServerModel.__call__"
    find(trace, "s11")["child_spans"].append(span("VisitTool", "v", **{"llm.token_count.prompt": "1000"}))
    find(trace, "s11")["child_spans"].append(span("helper__call__", "hc", **{"llm.token_count.prompt": "x"}))
    assert tr.runs(trace, NAME) == [run_row(TID, "r1", 3, 21, 12, 5), run_row(TID, "r2", 1, 100, 6, 100)]


def test_logs_events_and_links_are_never_walked(tr):
    trace = sample_trace()
    hidden = span("ToolCallingAgent.run", "hidden", call("h", 1, 1))
    top = find(trace, "top")
    top["logs"] = [hidden]
    top["events"] = [copy.deepcopy(hidden)]
    top["links"] = [copy.deepcopy(hidden)]
    assert [r["span_id"] for r in tr.runs(trace, NAME)] == ["r1", "r2"]


def test_calls_outside_runs_are_never_read(tr):
    trace = sample_trace()
    find(trace, "a")["span_attributes"] = "junk"
    find(trace, "b")["span_attributes"]["llm.token_count.prompt"] = "-3"
    assert len(tr.runs(trace, NAME)) == 2


def test_missing_child_spans_means_no_children(tr):
    trace = sample_trace()
    for sid in ("c", "d", "e", "f", "t1"):
        del find(trace, sid)["child_spans"]
    assert len(tr.runs(trace, NAME)) == 2


def test_trace_without_runs(tr):
    trace = {"trace_id": TID, "spans": [span("main", "m", span("CodeAgent.run", "top", call("a", 1, 1)))]}
    assert tr.runs(trace, NAME) == []
    assert tr.runs({"trace_id": TID, "spans": []}, NAME) == []


def test_runs_does_not_modify_its_input(tr):
    trace = sample_trace()
    before = copy.deepcopy(trace)
    tr.runs(trace, NAME)
    assert trace == before


def broken(edit):
    trace = sample_trace()
    edit(trace)
    return trace


INT64_MAX = 2**63 - 1
BAD_COUNTS = ["", "1.5", "-1", " 7", "7 ", "1e3", "\u0661\u0662", True, False, -1, 1.0, None, [7],
              "1" * 5000, "9" * 19, str(INT64_MAX + 1), "0" * 19 + "7", INT64_MAX + 1]


@pytest.mark.parametrize("trace", [
    None, [], "x",
    {"spans": []},
    {"trace_id": 7, "spans": []},
    {"trace_id": "f" * 32, "spans": []},
    {"trace_id": TID + ".json", "spans": []},
    {"trace_id": TID},
    {"trace_id": TID, "spans": {}},
    {"trace_id": TID, "spans": ["span"]},
])
def test_runs_refuses_a_bad_trace(tr, trace):
    with pytest.raises(ValueError, match=re.escape(NAME)):
        tr.runs(trace, NAME)


@pytest.mark.parametrize("sid,key,value", [
    ("t1", "span_name", None),
    ("s11", "span_name", 3),
    ("s11", "child_spans", {}),
    ("s11", "child_spans", "x"),
    ("t1", "child_spans", None),
])
def test_runs_refuses_a_bad_span(tr, sid, key, value):
    trace = broken(lambda t: find(t, sid).__setitem__(key, value))
    with pytest.raises(ValueError, match=re.escape(NAME)) as err:
        tr.runs(trace, NAME)
    assert sid in str(err.value)


@pytest.mark.parametrize("value", ["", None, 3])
def test_runs_refuses_a_bad_span_id(tr, value):
    trace = broken(lambda t: find(t, "d").__setitem__("span_id", value))
    with pytest.raises(ValueError, match=re.escape(NAME)):
        tr.runs(trace, NAME)


def test_runs_refuses_a_span_that_is_not_a_dict(tr):
    trace = broken(lambda t: find(t, "s11")["child_spans"].append("span"))
    with pytest.raises(ValueError, match=re.escape(NAME)):
        tr.runs(trace, NAME)


def test_runs_refuses_a_run_outside_the_top_agent(tr):
    trace = sample_trace()
    trace["spans"].append(span("ToolCallingAgent.run", "loose", call("l", 1, 1)))
    with pytest.raises(ValueError, match="loose"):
        tr.runs(trace, NAME)


def test_runs_refuses_a_run_inside_a_run(tr):
    trace = broken(lambda t: find(t, "s11")["child_spans"].append(
        span("ToolCallingAgent.run", "inner", call("i", 1, 1))))
    with pytest.raises(ValueError, match="inner"):
        tr.runs(trace, NAME)


def test_runs_refuses_a_run_with_no_model_call(tr):
    trace = broken(lambda t: find(t, "s2").__setitem__("child_spans", [span("ToolCallingAgent.run", "empty",
                                                                               span("Step 1", "e1"))]))
    with pytest.raises(ValueError, match="empty"):
        tr.runs(trace, NAME)


@pytest.mark.parametrize("key", ["llm.token_count.prompt", "llm.token_count.completion"])
@pytest.mark.parametrize("value", BAD_COUNTS)
def test_runs_refuses_a_bad_count(tr, key, value):
    trace = sample_trace()
    bad = find(trace, "e")
    bad["span_id"] = "call-e"
    bad["span_attributes"][key] = value
    with pytest.raises(ValueError, match=re.escape(NAME)) as err:
        tr.runs(trace, NAME)
    assert "call-e" in str(err.value)


@pytest.mark.parametrize("key", ["llm.token_count.prompt", "llm.token_count.completion"])
def test_runs_refuses_a_missing_count(tr, key):
    trace = broken(lambda t: find(t, "c")["span_attributes"].pop(key))
    with pytest.raises(ValueError, match=re.escape(NAME)):
        tr.runs(trace, NAME)


@pytest.mark.parametrize("value", [None, [], "attrs"])
def test_runs_refuses_call_attributes_that_are_not_a_dict(tr, value):
    trace = broken(lambda t: find(t, "f").__setitem__("span_attributes", value))
    with pytest.raises(ValueError, match=re.escape(NAME)):
        tr.runs(trace, NAME)


# --- summarize -----------------------------------------------------------------------------

def three_traces():
    t1 = [run_row("a" * 32, "r1", 3, 21, 12, 5), run_row("a" * 32, "r2", 1, 100, 6, 100)]
    t3 = [run_row("c" * 32, "r1", 4, 50, 2, 9)]
    return [t1, [], t3]


def test_summarize(tr):
    per_trace = three_traces()
    s = tr.summarize(per_trace)
    assert list(s) == SUMMARY_KEYS
    assert s["source"] == {"repo": REPO_URL, "folder": FOLDER, "revision": REVISION, "licence": "MIT"}
    assert list(s["source"]) == ["repo", "folder", "revision", "licence"]
    assert (s["traces"], s["traces_with_runs"], s["run_count"]) == (3, 2, 3)
    assert list(s["stats"]) == STAT_KEYS
    assert s["stats"] == {
        "model_calls": {"min": 1, "median": 3.0, "max": 4},
        "prompt_tokens": {"min": 21, "median": 50.0, "max": 100},
        "completion_tokens": {"min": 2, "median": 6.0, "max": 12},
        "first_call_prompt_tokens": {"min": 5, "median": 9.0, "max": 100},
    }
    assert s["runs"] == per_trace[0] + per_trace[2]


def test_summarize_types_and_even_median(tr):
    per_trace = [[run_row("a" * 32, "r1", 3, 21, 12, 5)], [run_row("b" * 32, "r1", 4, 22, 13, 6)]]
    s = tr.summarize(per_trace)
    assert s["stats"]["model_calls"] == {"min": 3, "median": 3.5, "max": 4}
    assert s["stats"]["prompt_tokens"]["median"] == 21.5
    for stat in s["stats"].values():
        assert list(stat) == ["min", "median", "max"]
        assert type(stat["min"]) is int and type(stat["max"]) is int and type(stat["median"]) is float


def test_summarize_takes_a_tuple_and_keeps_the_input(tr):
    per_trace = three_traces()
    before = copy.deepcopy(per_trace)
    assert tr.summarize(tuple(per_trace)) == tr.summarize(per_trace)
    assert per_trace == before


def test_summarize_is_json_stable(tr):
    s = tr.summarize(three_traces())
    assert json.loads(json.dumps(s, indent=2)) == s


@pytest.mark.parametrize("per_trace", [
    [], (), None, "x", {"a": []},
    [[], []],
    [[run_row("a" * 32, "r1", 1, 1, 1, 1)], "runs"],
    [[run_row("a" * 32, "r1", 1, 1, 1, 1)], [run_row("a" * 32, "r1", 2, 2, 2, 2)]],
    [[run_row("a" * 32, "r1", 1, 1, 1, 1), run_row("a" * 32, "r1", 1, 1, 1, 1)]],
])
def test_summarize_refuses(tr, per_trace):
    with pytest.raises(ValueError):
        tr.summarize(per_trace)


# --- CLI -----------------------------------------------------------------------------------

def cli_files(monkeypatch, tr, tmp_path):
    a, b, c = "a" * 32, "b" * 32, "c" * 32
    data = {f"{t}.json": json.dumps(sample_trace(t)).encode() for t in (a, c)}
    data[f"{b}.json"] = json.dumps({"trace_id": b, "spans": [span("main", "m")]}).encode()
    fake_files(monkeypatch, tr, data)
    cache = tmp_path / "cache"
    cache.mkdir()
    for name, body in data.items():
        (cache / name).write_bytes(body)
    return cache


def test_main_writes_summary_and_prints_it_without_runs(tr, monkeypatch, tmp_path, capsys):
    cache = cli_files(monkeypatch, tr, tmp_path)
    out = tmp_path / "summary.json"
    assert tr.main(["--out", str(out), "--cache", str(cache)]) == 0
    expected = tr.summarize([tr.runs(sample_trace("a" * 32), "a" * 32 + ".json"), [],
                             tr.runs(sample_trace("c" * 32), "c" * 32 + ".json")])
    assert out.read_text(encoding="utf-8") == json.dumps(expected, indent=2) + "\n"
    printed = capsys.readouterr().out
    assert printed.strip() == json.dumps({k: v for k, v in expected.items() if k != "runs"}, indent=2)
    assert (expected["traces"], expected["traces_with_runs"], expected["run_count"]) == (3, 2, 4)
    assert not out.with_name("summary.json.part").exists()


@pytest.mark.parametrize("argv", [[], ["--out", ""], ["--out", "."], ["--out", "/"], ["--out", ".."], ["--out", "x/"],
                                  ["--out", "x", "--bogus"], ["--cache", "c"]])
def test_main_bad_options(tr, monkeypatch, argv, capsys):
    monkeypatch.setattr(tr, "fetch", lambda *a, **k: pytest.fail("fetched on a bad option"))
    assert tr.main(argv) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1 and captured.err.startswith("error: ")


def test_main_bad_data_leaves_out_untouched(tr, monkeypatch, tmp_path, capsys):
    cache = cli_files(monkeypatch, tr, tmp_path)
    name = "c" * 32 + ".json"
    trace = sample_trace("c" * 32)
    find(trace, "e")["span_id"] = "e\nline"
    find(trace, "e\nline")["span_attributes"]["llm.token_count.prompt"] = "x"
    bad = json.dumps(trace).encode()
    (cache / name).write_bytes(bad)
    monkeypatch.setattr(tr, "FILES", dict(tr.FILES, **{name: (len(bad), hashlib.sha256(bad).hexdigest())}))
    out = tmp_path / "summary.json"
    out.write_text("old\n")
    out.with_name("summary.json.part").write_text("stale")
    assert tr.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1 and captured.err.startswith("error: ")
    assert "e\\nline" in captured.err
    assert out.read_text() == "old\n"
    assert not out.with_name("summary.json.part").exists()


def test_main_bad_first_file_leaves_out_untouched(tr, monkeypatch, tmp_path, capsys):
    cache = cli_files(monkeypatch, tr, tmp_path)
    name = "a" * 32 + ".json"
    trace = sample_trace("a" * 32)
    find(trace, "c")["span_attributes"]["llm.token_count.completion"] = "1.5"
    bad = json.dumps(trace).encode()
    (cache / name).write_bytes(bad)
    monkeypatch.setattr(tr, "FILES", dict(tr.FILES, **{name: (len(bad), hashlib.sha256(bad).hexdigest())}))
    out = tmp_path / "summary.json"
    out.write_text("old\n")
    assert tr.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and len(captured.err.splitlines()) == 1
    assert name in captured.err
    assert out.read_text() == "old\n"
    assert not out.with_name("summary.json.part").exists()


def test_main_missing_out_folder_is_one_error_line(tr, monkeypatch, tmp_path, capsys):
    cache = cli_files(monkeypatch, tr, tmp_path)
    out = tmp_path / "no-such-folder" / "summary.json"
    assert tr.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == ""
    assert len(captured.err.splitlines()) == 1 and captured.err.startswith("error: ")
    assert not out.parent.exists()


class BrokenStdout:
    def write(self, text):
        raise BrokenPipeError(32, "Broken pipe")

    def flush(self):
        raise BrokenPipeError(32, "Broken pipe")


def test_main_failed_stdout_is_one_error_line_and_leaves_out(tr, monkeypatch, tmp_path, capsys):
    cache = cli_files(monkeypatch, tr, tmp_path)
    out = tmp_path / "summary.json"
    out.write_text("old\n")
    monkeypatch.setattr(sys, "stdout", BrokenStdout())
    assert tr.main(["--out", str(out), "--cache", str(cache)]) == 2
    err = capsys.readouterr().err
    assert len(err.splitlines()) == 1 and err.startswith("error: ")
    assert out.read_text() == "old\n"
    assert not out.with_name("summary.json.part").exists()


def test_main_hash_mismatch_is_one_error_line(tr, monkeypatch, tmp_path, capsys):
    cache = cli_files(monkeypatch, tr, tmp_path)
    (cache / ("a" * 32 + ".json")).write_bytes(b"{}")
    out = tmp_path / "summary.json"
    assert tr.main(["--out", str(out), "--cache", str(cache)]) == 2
    captured = capsys.readouterr()
    assert captured.out == "" and len(captured.err.splitlines()) == 1
    assert not out.exists()


# --- the pinned files, when cached ---------------------------------------------------------

def test_pinned_files_when_cached(tr, tmp_path):
    cache = tr.default_cache_dir()
    if not all((cache / name).is_file() for name in tr.FILES):
        pytest.skip("the 117 pinned TRAIL traces are not in the default cache")
    out = tmp_path / "summary.json"
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        assert tr.main(["--out", str(out)]) == 0
    printed = json.loads(buf.getvalue())
    summary = json.loads(out.read_text(encoding="utf-8"))
    assert printed == {k: v for k, v in summary.items() if k != "runs"}
    assert (summary["traces"], summary["traces_with_runs"], summary["run_count"]) == (117, 47, 60)
    assert summary["stats"] == {
        "model_calls": {"min": 3, "median": 15.0, "max": 31},
        "prompt_tokens": {"min": 5508, "median": 94868.5, "max": 357993},
        "completion_tokens": {"min": 1990, "median": 8343.5, "max": 21188},
        "first_call_prompt_tokens": {"min": 549, "median": 594.5, "max": 765},
    }
    per_trace = {}
    for run in summary["runs"]:
        per_trace[run["trace_id"]] = per_trace.get(run["trace_id"], 0) + 1
    assert sorted(per_trace.values()).count(1) == 38
    assert sorted(per_trace.values()).count(2) == 5
    assert sorted(per_trace.values()).count(3) == 4
    assert [r["trace_id"] for r in summary["runs"]] == sorted(r["trace_id"] for r in summary["runs"])
