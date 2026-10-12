# Packed separator solves the 21-variable S3 middle link exactly

The packed Boolean factor solver completed the frozen `GF(2^9)` S3 chains
with three through six summands. The four-, five-, and six-summand chains all
used width 21, matching the explicit `2n+ell` separator bound at `n=9`,
`ell=3`. Optimized and UBSan runs returned identical assignments, and each
assignment was checked against every original Boolean equation. The
245-system small random panel agreed with exhaustive enumeration, including
satisfiable and unsatisfiable cases and explicit width/state-cap controls.

| Summands | Boolean variables | Width | Factor states | Elimination states | Peak packed-factor words | Local optimized solve ms |
| ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| 3 | 18 | 15 | 136,196 | 72,702 | 2,129 | 1.90 |
| 4 | 30 | 21 | 19,010,564 | 4,265,982 | 297,041 | 129.88 |
| 5 | 42 | 21 | 37,884,932 | 8,459,262 | 591,953 | 345.25 |
| 6 | 54 | 21 | 56,755,520 | 12,652,542 | 886,805 | 733.38 |

The state counts are deterministic. The 886,805 packed-factor words in the
six-summand row represent 7,094,440 bytes of factor table payload; witness
tables account for another 98,853 words. The local wall times include Python
equation packing, native solve, and independent ANF replay, but exclude S3
fixture construction. They are exploratory on a contended macOS M4 Pro host.
All runs used a 21-variable bag cap and 100-million-state combined
factor/elimination cap; neither cap was reached.

The full ordinary-target semantic screen fixed the same `n=9`, `m=4`,
`ell=3`, `b=1`, modulus `515` curve and the three distinct factor-base points
whose abscissae lie in the declared subspace. Independent enumeration of all
finite four-point sums reached target abscissae `0` and `1`. With one local
point-lift ANF constraint on every summand and intermediate block, the packed
solver classified all 512 field abscissae identically: two satisfiable and
510 unsatisfiable. Both satisfying assignments replayed as actual point sums
with finite intermediates. Every constrained solve retained width 21.

The screen also records a concrete obstruction to treating bare S3 equations
as a point-decomposition oracle. Target abscissa `2` is unreachable in the
enumerated point set, yet its unlifted S3 chain has a satisfying Boolean
assignment (`202045979`). The block-local lift constraints make that query
unsatisfiable without increasing width. This is a necessary semantic filter
for the proposed separator algorithm; point replay remains part of positive
verification.

The [raw panel](evidence/panel/report.json), [512-target screen](evidence/semantic.json),
[test log](evidence/tests.log), and [source/binary receipt](evidence/build-receipt.json)
are bound by the byte-checked [evidence manifest](evidence/manifest.json),
SHA-256 `c699a2d1c009201c0a48d16f6aff75ed6dfaa91a24ce5677440a0a6f7f8bd345`.
The executable-source commit is `53e1ef9a59efabb74d5492e3cd8b81761e06a29f`.

The next experiment is a proof-carrying F4/F5 projection for a width-21
local block, with the same lift constraints and actual point replay. A matched
ordinary-query comparison must include factor construction, projection,
certificate composition, all failed queries, and the complete target-dependent
interval. The packed-factor solver supplies an exact baseline for that test.
