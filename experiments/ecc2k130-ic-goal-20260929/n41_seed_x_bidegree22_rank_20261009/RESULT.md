# Full rank for compact seed-quadratic times coordinate-quadratic N41 constraints

The exact two-pair N41 suffix support has **full rank 64,859/64,859** in the tensor feature family

`{seed monomial of degree ≤2} × {x monomial of degree ≤2}`.

The [frozen rank run](rank_result.json) used 80,000 distinct exact sign-orbit suffix sums sampled without replacement and reached nullity zero. Because these rows are a subset of the complete exact support, **no nonzero Boolean equation in this declared bidegree-(2,2) family holds on every suffix sum**. The [independent audit](audit.json) matched the first 256 rows' feature digest, mapped all 80,000 sampled records back to the exact source, and replayed 64 sampled sums and all 128 source points with checked Sage arithmetic.

## Instance and feature map

The instance is `EC1N41Ckb1h7d5e80d3c4d0` over `GF(2)[t]/(t^41+t^3+1)` with curve `y²+xy=x³+1` and subgroup order `549756390943`. The exact suffix support comes from the W6 point domains at rotations 20 and 30 of the frozen four-window base (`B=256`, folded `K=26`). Each suffix pair domain has 1,956 distinct-column states. The prior [exact orbit file](../n41_seed_bin_quadratic_filter_20261009/x_orbits.bin) contains 1,583,568 sign-orbit `x` coordinates, their two six-bit pair seed sums, and pair-state witnesses. The [sample protocol](protocol.json) binds that source by SHA-256 and selects 80,000 record indices with the frozen `random.sample` seed `20261010000000`; the [sample receipt](sample_receipt.json) records all 3,969 seed bins represented.

Write the 12 seed bits as `u=(s_0,…,s_5,t_0,…,t_5)` and the 40 variable coordinate bits as `v=(x_1,…,x_40)`. The field encoding has `x_0=0` on the declared subgroup, so it is omitted. The seed features are the constant, 12 linear terms, and 66 squarefree quadratic terms: 79 total. The `x` features are the constant, 40 linear terms, and 780 squarefree quadratic terms: 821 total. Their ordered products yield **79×821=64,859** columns. These are Boolean functions, with repeated variables reduced by `b²=b` before feature enumeration. The [rank source](rank.cpp) writes the exact 80,000-by-64,859 GF(2) matrix and performs M4RI echelon reduction.

## Exact result and checks

| Frozen record | Result |
| --- | ---: |
| Exact sample rows | 80,000, without replacement |
| Seed bins covered | 3,969/3,969 |
| Tensor feature columns | 64,859 |
| GF(2) rank | **64,859** |
| Right-kernel dimension | **0** |
| Active matrix entries written | 424,140,089 |
| Native matrix population | 3.321 s |
| Native M4RI rank | 187.882 s |
| Native total / bounded wrapper | 191.204 s / 191.598 s |
| Native peak RSS | 653,574,144 B |
| Independent exact-source rows checked | 80,000 |
| Independent Sage group sums replayed | 64 |
| Independent source points checked | 128 |

The rank run used one worker under its frozen 300-second and 4-GiB caps. The [bounded control receipt](rank_control.json) records `EXIT_SUCCESS`, binary and input hashes, stdout and stderr hashes, and observed RSS. The [Sage runtime receipt](sage-runtime-info.json) was saved before the independent Sage audit. The auditor regenerated 1,089,341 active feature positions across the first 256 sampled rows; its 64-bit digest agrees exactly with the native producer. It also reconstructed both 1,956-state pair domains, checked all source points in the subgroup, and verified the recorded `x` and seed sums for 64 spaced sample rows. Local CPU wall times are exploratory stage measurements without host-isolation evidence.

The preceding [seed-bin filter experiment](../n41_seed_bin_quadratic_filter_20261009/RESULT.md) found a public N41 relation using 16 bin-specific quadratic equations and then independently proved `rank(bin)=min(bin size,821)` in all 3,969 bins. Those equations arise from finite-support interpolation. The full-rank result here closes the compact global alternative in which the coefficients of a quadratic `x` equation are quadratic functions of the 12 seed bits. It does not constrain equations involving pair-output coordinates, target `y`, higher seed degree, or another exact factor-base geometry.

The next constructive experiment should carry exact seed-conditioned **pair-output** membership through a target-coupled balanced S3 tree while at least four pair outputs remain free. Its first rank or elimination check should distinguish structural equations from finite-support interpolation as done here. The whole W18 search needs a source-bound 600-second/4-GiB projection before an ordinary degree-131 public-point query.
