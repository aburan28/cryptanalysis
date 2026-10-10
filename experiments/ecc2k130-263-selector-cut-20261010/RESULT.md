# Selector-derived coordinates verify four full-x controls; ordinary Q0 branches remain capped

Computing a W24 leaf's x and inverse-coordinate z directly from its fixed
24-bit selector made all four archived full-x source/degree-263 descendant
controls `SAT_VERIFIED_GROUP`. Each model satisfied the complete native-XOR
XCNF and reproduced the exact signed six-leaf target. The same exact cut was
tested as a paired one-fixed-leaf branch on eight target-independent common
masks for the public Q0 point. All 32 ordinary attempts entered search and
ended `BOUNDED_UNKNOWN`: 15 reached 2,001–2,002 conflicts, and 17 reached
the 45-second external wall guard before printing a final conflict count.
The [independent audit](runs/R1/audit.json) reconstructed all 36 frozen
inputs and checked their raw transcripts and every SAT model.

The [protocol](PROTOCOL.md), [source pins](source.json), producer, and auditor
were committed as `962a8f9b3` before mask selection or cell construction.
The eight masks, all 36 unit deltas, and every complete XCNF SHA-256 were
frozen in `ad1a98f08` before solver launch. The input preflight independently
recomputed all eight masks and 36 deltas. Each selected mask is rational and
has a nonidentity fourfold subgroup projection on both curves. The paired
factor bases each contain `B=16,772,828` usable points, or `M=8,386,414`
signed x-classes, before any orbit folding. Curve IDs are
`EC1N131Ckb1h136f03e58c98` and `EC1N131Cbinh833014327b07`; the oriented
degree-263 route is `IW1E263d1hadee4e69fa3d`. The public workload is
`eee7f6ee5f6b`, query index zero. Q1420 remains a design proposal with
`candidate_id: null`.

The control producer read the archived selector units in each full-x release,
computed `w=sum_j s_j*b_j`, `u=halftrace(w)`, `z=w^-1`, and
`x=alpha+alpha*u^-1`, and appended the derived x units. The released leaf's
archived input contained **no x units**; its already fixed z units were
checked against the derivation. For an ordinary cell, `selector_only` fixes
24 bits of leaf 0; `coordinate_cut` fixes those same bits plus the derived
131 x and 131 z bits. The remaining five leaves and four raw target-lift
choices stay free. The mask law takes eight midpoint quantiles of the first
mask among six sorted selectors and advances to the first jointly usable
mask. The selected masks are `179349`, `570206`, `1014847`, `1532862`,
`2157614`, `2954152`, `4081183`, and `6203137`.

All cells used one thread, the pinned CryptoMiniSat 5.14.7 executable,
native-XOR XCNF, and a sampled 4-GiB RSS guard. Controls used 20,000
conflicts and 30/40-second internal/external wall limits, matching the
archived full-x ladder. Ordinary branches used 2,000 conflicts and
120/45-second internal/external limits, with the exact default Gaussian
flags from the earlier [component panel](../ecc2k130-263-gauss-components-20261010/RESULT.md).
The [runtime receipt](runs/R1/runtime-info.json) records the subprocess
and preparation timing boundaries, binary hash, and host state.

| Fixed control | Derived-x outcome | Solver wall s | Child CPU s | Peak sampled RSS MiB | Final conflicts |
| --- | --- | ---: | ---: | ---: | ---: |
| Source x0 | `SAT_VERIFIED_GROUP` | 3.454 | 0.585 | 131.31 | 0 |
| Descendant x0 | `SAT_VERIFIED_GROUP` | 7.008 | 0.677 | 132.05 | 0 |
| Source x5 | `SAT_VERIFIED_GROUP` | 7.761 | 0.727 | 132.17 | 0 |
| Descendant x5 | `SAT_VERIFIED_GROUP` | 7.780 | 0.688 | 131.83 | 0 |

Each source control model passed 359,658 ordinary clauses and 225,325 native
XORs; each descendant model passed 359,100 ordinary clauses and 229,902
native XORs. The decoded six masks and finite S3 intermediates matched the
archived witness; exactly one sign assignment, all plus, gave its raw target.
The archived matched full-x releases had reached their 20,000-conflict or
wall limits. This status change checks conditional leaf derivation on the
fixed witness; it is not a free-selector relation-yield measurement.

| Public Q0 branch arm | Attempts | Conflict caps | Wall caps | Verified decompositions | Preparation wall sum s | Solver wall sum s | Child CPU sum s | Peak sampled RSS MiB |
| --- | ---: | ---: | ---: | ---: | ---: | ---: | ---: | ---: |
| Source, selector only | 8 | 3 | 5 | 0 | 5.142 | 344.428 | 23.373 | 179.20 |
| Source, coordinate cut | 8 | 3 | 5 | 0 | 5.181 | 329.971 | 22.532 | 177.08 |
| Descendant, selector only | 8 | 5 | 3 | 0 | 2.454 | 277.766 | 18.953 | 186.80 |
| Descendant, coordinate cut | 8 | 4 | 4 | 0 | 2.433 | 281.023 | 19.132 | 180.09 |

The ordinary sequence spent **1,248.398 seconds** in recorded preparation
plus solver wall intervals across its four arms. Mask selection took another
16.143 seconds before the branch cells and is reusable precomputation;
preparation includes archive decompression and full-input verification for
each branch. Model verification and this audit are outside those intervals.
All 32 bounded cells have restart evidence (290 printed restart rows in
total). Their final conflict counts are unknown when the wall guard fired.
Child CPU includes the solver and repeated `ps` RSS-sampler subprocesses.
The host lacks a CPU-isolation receipt, and each cell was run once; the wall
and CPU figures are exploratory stage costs, not controlled timing ratios.
The 32 attempts reuse eight masks, two curves, and one public query, so their
zero verified rows are not 32 independent samples of natural relation yield.
No row was available for a rank test; matrix work and target descent are
unmeasured in this panel.

The separate [uniform-group-sum calculation](runs/R1/uniform_model.json)
quantifies this particular one-mask branch policy under an explicit model.
With `M=8,386,414` signed classes and subgroup order
`r=680564733841876926932320129493409985129`, there are at most
`2^6 * binomial(M+5,6)` signed sorted six-mask tuples. Four raw lifts out
of a group of order `4r` give probability `1/r` per signed tuple **if** each
sum is marginally uniform. That model gives at most 45.4398 expected
representation assignments across the unrestricted six-mask space. Fixing the first
mask leaves at most `2^6 * binomial(M+4,5)` signed continuations, or
`3.25096e-5` expected representations per mask. For the eight fixed first
masks, the expected count is at most `2.60077e-4`, and Markov's inequality
gives the same upper bound on the chance of at least one representation
*under that model*. These are exact combinatorial counts with a stated
distributional assumption, not an empirical Q0 yield estimate or a theorem
about the fixed public point. Even at the most favorable first-mask bound,
more than 30,760 distinct masks would be needed for this upper expected
count to reach one; that is a branch-coverage calculation, not a time
extrapolation.

The cut is correct and effective when a selector is already fixed, but
serial one-mask fresh-solver branching has sparse expected representation
coverage and did not resolve any of the eight public-Q0 branches within
their caps. It should not be promoted from this panel. The next controlled
encoding gate is a target-independent **free-selector** strengthening. The
existing W24 equations imply the simple quadratic field identity
`alpha*x*z=(x+alpha)^2`: since `w=u(u+1)`, `z=1/w`, and
`x=alpha*(u+1)/u`, both sides equal `alpha^2/u^2`. Its RHS is field-linear
in x bits in characteristic two. The [identity replay](runs/R1/identity.json)
passed direct arithmetic checks on all 16 selected curve/mask pairs. Adding
it as a redundant XCNF constraint still needs an exact frozen comparison
on controls and held-out ordinary queries, including its construction and
search costs.
Any later multi-mask or incremental branch policy must charge every mask
and failed solve before it can answer the one-target IC question.

Replay the recorded derivation and archive checks with:

```sh
python3 -B experiments/ecc2k130-263-selector-cut-20261010/uniform_model.py --write
python3 -B experiments/ecc2k130-263-selector-cut-20261010/identity.py --write
python3 -B experiments/ecc2k130-263-selector-cut-20261010/audit.py --write
```
