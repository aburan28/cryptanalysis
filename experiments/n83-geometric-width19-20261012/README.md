# Exact shifted N83 width-19 factor-base geometry

The complete shifted width-19 base has **43,552,922 distinct usable
subgroup points before folding**, represented by **262,367
signed-Frobenius columns**. The scan examined all 524,288 x seeds,
found 262,376 valid lifts, no identity projections, and nine duplicate
orbit seeds. [Independent Sage replay](independent_sage_replay.json)
reconstructed every seed, lift, cofactor projection and canonical key
in a separate polynomial field representation; its result is `PASS`.

The field is GF(2^83), the curve is `y² + xy = x³ + 1`, and the subgroup
order is 2,417,851,639,230,796,216,685,689. The raw x seeds are
`gamma_82 + span(gamma_1,...,gamma_19)`. Each valid lift is multiplied
by cofactor four, identity is dropped, and the resulting set is closed
under sign and all 83 Frobenius powers. The exact key file, counts,
source hashes and allocation law are frozen in [frontier.json](frontier.json)
and [protocol.json](protocol.json).

| Width | Valid x lifts | Folded columns K | Usable points B | Five-subset first moment | Full pair-root plus cached XY payload |
| --- | ---: | ---: | ---: | ---: | ---: |
| 18, prior | 130,817 | 130,813 | 21,714,958 | 16,641,170,632.3 | 136.35 TB |
| 19 | 262,376 | 262,367 | 43,552,922 | 540,101,636,092.1 | 548.49 TB |

The first moment is `binom(B,5)/r` under the uniform-sum combinatorial
model; ordinary relation yield and rank are measured separately. A
complete pair-root allocation needs `83 K²` states and 96 bytes per
state for root records and cached coordinates, beyond the declared
8 GiB cap. The neighboring [width-19 decomposition
experiment](../n83-geometric-m5-karatsuba19-20261012/README.md) uses
the 5,509,707-byte canonical key file and a compact canonical-x cache.

The checked Sage launcher produced the [runtime receipt](sage_runtime_info.json).
Exact enumeration took 197.55 seconds and full independent replay
346.76 seconds on the local exploratory host. The receipt counts are
computationally checked; a faithful Lean encoding of this finite
enumeration and its field/curve bridge remains an open formalization
obligation. The preceding Karatsuba split identity has a checked Lean
proof in the width-16 topology experiment.

Run the read-only audit from the repository root:

```sh
python3 experiments/n83-geometric-width19-20261012/verify.py
```
