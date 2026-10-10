# Exact W14 ten-source factor-base geometry on ECC2K-130

The W14 linear-source construction yields **164,400 distinct projected
subgroup points** before sign/Frobenius folding and **8,160 effective
columns** across ten Frobenius rotations on the exact degree-131 challenge
curve `EC1N131Ckb1heb5f1998f20b`. The source has 8,220 rational nonzero
masks. All 45 pairs of rotated 14-dimensional source spaces have rank 28;
the projected points have 82,200 distinct x-coordinates, each giving the
two signs of an odd-order subgroup point.

| Exact geometry, same curve and field | Seven-source W19 | Ten-source W14 |
| --- | ---: | ---: |
| Rational source masks | 262,390 | 8,220 |
| Signed points per query block | 524,780 | 16,440 |
| Actual usable projected factor-base points `B` | 3,673,460 | 164,400 |
| Signed-Frobenius columns `K` | 262,151 | 8,160 |
| Uniform-sum expected representations per point, prediction | 16.11 | 2,119.09 |

The prediction in the last row is `(2 × rational_masks)^m / r`, for
`m=7` or `m=10` and the official prime subgroup order
`r=680564733841876926932320129493409985129`. It assumes independent,
uniformly distributed group sums; it is a density screen, not a measured
solver yield or rank rate. The W19 comparator uses the previously frozen
[exact census](../n41_seven_linear_source_20261009/support_receipt.json).

The [frozen protocol](support_protocol.json) binds the official input,
source and executable hashes, ten rotations `[0,13,26,39,52,65,78,91,104,117]`,
and a 120-second/4-GiB enumeration envelope. The native
[mask/orbit map](support_w14.tsv) and [receipt](support_receipt.json) record
8,220 rational masks, 8,160 source Frobenius orbits, 124 direct source
orbit-overlap incidences, zero reciprocal-Frobenius incidences, and
164,400 union points. The [checked-Sage field audit](sage_support_audit.json)
recomputes rationality for all 16,383 nonzero masks, reconstructs every
source alias from subspace intersections, checks the reciprocal condition,
and verifies every rotated-space rank. The [checked-Sage group audit](sage_group_audit.json)
uses the exact binary-curve doubling identity
`x(2P)=x(P)^2+x(P)^(-2)` twice to enumerate all 82,200 projected
x-coordinates, verifies that identity on eight independently lifted and
multiplied points, and checks their subgroup order. Its first version used
generic point lifting for every mask and was
[interrupted for this exact rewrite](group_audit_attempt_v1.json).

The next gate is a full ten-source S3 decomposition control on an exact
degree-41 public point with comparable source density, followed by a frozen
N131 planted assignment and one unpinned published-point query if the
formula and resource limits fit. Measure verified ordinary relation yield
and novel row rank before promoting the method to a complete IC candidate.
This remains a `Q` proposal with `candidate_id: null`.
