# Fifteen-window weighted digit-budget candidate

Mode 156 combines a 15-window `8^6,9^9` bit schedule, a full `D=512`
radix-512 two-bucket `tau` atlas for the first eight nine-bit windows, and
the tight `D=363` atlas at the final window. It retains **233,423** affine
seed points and **17,511,596 bytes** including atlases, container overhead,
and the Solinas unit constants. The exact termination proof and atlas
construction are in [`PROOF.md`](PROOF.md) and `build_atlas.py`.

The source was frozen at `c6d5d695eaf298dad9c345e943a0a9e8cd614150`
before drawing a disjoint 4,096-scalar panel with seed `20261010156` and
scalar digest `cdbf376e0ba2bd7874cbbe458e816dd16778ccc0d1c724cc798d2622dc4c7b3a`.
Independent affine binary multiplication supplied every expected point.
Both candidate and paired mode 155 reproduced all 4,096 points, ten edge
cases, and 129 fixed cases. The complete release suite passed **130 tests**;
the rebuilt standalone binary hash matches the replay receipt.

| Source-level measure on the fresh panel | Mode 156 | Mode 155 | Change |
| --- | ---: | ---: | ---: |
| Charged mixed additions | 57,343 | 61,439 | 4,096 fewer |
| Generic field multiplies | 499,704 | 532,472 | 32,768 fewer |
| Generic field squares | 126,974 | 135,166 | 8,192 fewer |
| Solinas constant products | 40,981 | 43,665 | 2,684 fewer |
| Source-loop limb products | 23,502,971 | 25,039,263 | **1,536,292 fewer** |
| Charged retained bytes | 17,511,596 | 8,336,624 | 9,174,972 more |

The exact product model counts 36 integer products for each generic
Montgomery multiply or square and 23 for each fixed Solinas product. A
temporary counter build produced the raw operation log; its patch, log,
receipt, and independent atlas-decoding count are retained here. The
shipping source contains no counters. `verify.py` checks the source-bound
point replay and `verify_ops.py` checks the paired operation record.

These are correctness and source-operation results. CPU wall-time ratios
require the host-level isolation receipt in
[`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md).
