# Exact high-prefix inverse for W14 pair outputs on ECC2K-130

An exact projected inverse recovers usable W14 source pairs from only the
**top 96 polynomial-basis bits** of a pair-output coordinate: the lower
35 bits may be unspecified. On the frozen panel it recovered **32 of 32**
independently constructed pairs and returned no pair for **32 of 32**
uniform field controls at that width. Every case at width 35 completed
with at most 256 projected coefficient vectors; the complete 960-query
panel took **40.010 s** and 21,610,496 bytes peak process RSS. An
independent checked-Sage audit recomputed all 15 invariant-row masks,
21 projected rank cases, and all 32 positive raw group sums. This is
proposal `Q20261010223000` with `candidate_id: null` until a full
target-conditioned IC pipeline is specified.

## Exact prefix theorem and algorithm

The [frozen source oracle](../n131_w14_polynomial_pair_inverse_20261010/RESULT.md)
uses `GF(2)[t]/(t^131+t^13+t²+t+1)` and
`y²+xy=x³+1`, with subgroup order
`680564733841876926932320129493409985129`. For one same-rotation
W14 source pair, write `s=a XOR b` for its 14-bit seed-sum mask,
`p=w_a w_b` in the 27-dimensional span of `t²,...,t²⁸`, and
`z=1/(x(P_a+P_b)+1)`. With `A(z)=z²+z`, the exact S3 identity is

`z² = u_s² + A(z) p`.

Suppose only the polynomial coefficients of `z` at degrees `b..130`
are known. Let `I_b` contain every output coordinate unchanged in
both `z²` and `A(z)t^d`, for all changes to degrees `0..b-1` of `z`
and all `d=2..28`. Squaring and multiplication by a fixed `t^d`
are binary linear, so testing each missing basis bit computes **all**
invariant rows exactly. For `b≤52`, every coordinate of degree at least
`2b+27` is invariant; the exact mask also retains degree 1. At `b=35`,
`I_b={1,97,...,130}` has 35 coordinates.

Projecting the pair equation onto `I_b` gives a binary linear system
in the **14 seed-sum and 27 product coefficients**. Every usable pair
whose output has the supplied prefix yields a solution. An inconsistent
system therefore rejects the entire prefix soundly. When its nullity is
at most eight, the [partial inverse](prefix.py) enumerates all coefficient
solutions, applies the source oracle's exact fixed-sum mask-pair inverse,
then tests all raw sign choices against the output prefix. This returns
**every** admissible pair for that prefix, including distinct folded-column
filtering, for regular pair outputs. Larger nullities are explicitly
`RANK_FALLBACK`, not negative decisions. A pair at Frobenius rotation `r`
can use this unrotated interface after applying inverse Frobenius to its
output coordinate.

The [protocol](protocol.json) binds the existing 32 positive pair outputs,
32 uniform field controls, exact W14 support, independent field code,
checked Sage runtime, executable sources, 120-second wall cap, and
4-GiB memory cap. The factor-base policy has five rotations each used
twice, **B=82,200** actual usable projected points, and **K=8,160**
folded columns. This experiment measures the local pair-output inverse;
its `target_count` is zero.

| Missing low bits `b` | Invariant rows | Positive pairs recovered | Uniform prefixes returning pairs | Decision status |
| ---: | ---: | ---: | ---: | --- |
| 0 | 131 | 32/32 | 0/32 | All complete |
| 24 | 57 | 32/32 | 0/32 | All complete |
| 31 | 43 | 32/32 | 0/32 | All complete |
| 32 | 41 | 32/32 | 0/32 | All complete |
| 34 | 37 | 32/32 | 0/32 | All complete |
| **35** | **35** | **32/32** | **0/32** | **All complete** |
| 36 | 33 | 15/15 decided; 17 fallback | 0/26 decided; 6 fallback | Partial |
| 40 | 25 | —; 32 fallback | —; 32 fallback | All fallbacks |
| 48 | 9 | —; 32 fallback | —; 32 fallback | All fallbacks |

At `b=35`, 21 uniform controls failed the projected linear system; the
other 11 passed that necessary test and were rejected by complete
fixed-sum/group-prefix inversion. The 32/32 positive recovery and 0/32
uniform hit rates have one-sided exact 95% bounds of at least 91.1% and
at most 8.9%, respectively, for their respective frozen input laws.
These panel rates do not estimate target-conditioned relation yield.
At `b=36`, fallbacks preserve uncertainty; the empty pair lists in
fallback rows are not rejection results.

The [run receipt](result.json) records each prefix, projected rank,
nullity, coefficient-vector count, fixed-sum calls, returned pairs,
query wall, and terminal status. Setup took 0.249 s, invariant-mask
construction 0.327 s, and the 960 exact/partial queries 39.415 s;
the complete panel wall was 40.010 s. The median `b=35` positive query
was 48.414 ms and the uniform query was 0.229 ms. These CPU times are
algorithmic diagnostics on an unisolated host. The full-output `b=0`
pair sets agree exactly with all 64 queries of the frozen source oracle.
The [independent checked-Sage audit](sage_audit.json) verifies the
invariant-row derivatives, selected projected ranks and consistency,
and all positive raw curve sums. The [terminal verifier](verify.py)
checks hashes, caps, complete statuses, and audit binding.

## Target-coupled next gate

The inverse gives an exact early filter once the upper S3 target chain
specifies a pair-output prefix. The next experiment must make that
prefix **target-conditioned**: couple the five pair-output variables to
the public target, expose their high-coordinate constraints before
expanding source masks, and measure how many candidate families the
prefix inverse removes on an unpinned N41 control. Then freeze a
source-bound 600-second/4-GiB N131 query. An ordinary N131 relation,
useful rank, factor-base logs, fresh target descent, and matched
single-target rho comparison remain the subsequent goal gates.
