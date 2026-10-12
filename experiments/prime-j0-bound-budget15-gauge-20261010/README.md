# Fifteen-window grouped-unit tau buckets

Mode 157 groups the selected points of each tau bucket by six-unit power
and rotates each accumulated bucket at most twice. It keeps the fifteen
window schedule, 233,423 affine seed points, and 17,511,596 charged bytes
of mode 156. The exact group identity is in [PROOF.md](PROOF.md).

The source was frozen at `ab16299685c62d590f909babee40dd9766604b72`
before drawing a disjoint 4,096-scalar panel with seed `20261010157` and
scalar digest `aef83007002d63dee4c9136351300482f9e6e1214d3bf7b40a7084aeea526c4e`.
Independent affine binary multiplication supplied every expected point.
Modes 157 and 156 reproduced all 4,096 points, ten edge cases, and 129
fixed cases. The complete release suite passed **131 tests**. The rebuilt
standalone binary hash matches the replay receipt.

| Source-level measure on the fresh panel | Gauge mode 157 | Per-term mode 156 | Sixteen-window mode 155 |
| --- | ---: | ---: | ---: |
| Charged mixed additions | 57,343 | 57,343 | 61,437 |
| Generic field multiplies | 499,704 | 499,704 | 532,456 |
| Generic field squares | 126,974 | 126,974 | 135,162 |
| Solinas constant products | 15,341 | 41,136 | 43,483 |
| Source-loop limb products | **22,913,251** | 23,506,536 | 25,034,357 |
| Charged retained bytes | 17,511,596 | 17,511,596 | 8,336,624 |

The grouping saves **25,795** Solinas products and **593,285** source-loop
limb products against mode 156 with identical generic point arithmetic.
Together with the shorter window schedule it saves **2,121,106**
source-loop limb products against mode 155 on the same panel, while
retaining 9,174,972 additional bytes. The model counts 36 source-loop
integer products for each generic Montgomery multiply or square and 23
for each fixed Solinas product. The temporary counter patch and raw log
are preserved; the shipping source contains no counters. `verify.py`
checks the source-bound point replay, and `verify_ops.py` independently
decodes the atlas to check the paired operation record.

These are correctness and source-operation results. Controlled CPU wall
timing requires an [isolated host receipt](../../docs/ISOLATED_BENCHMARKS.md).
