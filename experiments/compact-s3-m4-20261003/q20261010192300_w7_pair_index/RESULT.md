# Larger bases lower fixed-index work, but remain above the challenge

Q20261010192300 applies Q1422's fixed, target-independent explicit
S3 pair-output index law to the N131 weight-seven base estimate from
Q20261010190000. **The conditional weight-seven point requires at least
`2^84.180` logical key insertions and lookups**, 23.180 bits above an
abstract `2^61` action count under Q1422's uniform-target, fixed-partner,
K-rank-row assumptions. The 95% sampling endpoints change this to
`2^84.175`–`2^84.186`; this interval does not cover projection collisions
or model error. The calculation reproduced Q1422's exact weight-six
integer count before evaluating larger bases, and an independent verifier
recomputed all six rows.

| N131 normal-x bound | Base status | K columns | log₂ maximum keys M | log₂ necessary lookups L | log₂ insertions + lookups T | Gap over `2^61` actions |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| ≤5 | exact Q1413 | 1,181,807 | 47.379 | 92.761 | **92.761** | +31.761 bits |
| ≤6 | exact Q1413/Q1422 control | 25,036,774 | 56.189 | 88.356 | **88.356** | +27.356 bits |
| ≤7 | sampled conditional point | 452,374,878 | 64.539 | 84.180 | **84.180** | +23.180 bits |
| ≤8 | half-rational extrapolation | 7,054,723,878 | 72.465 | 80.217 | **80.224** | +19.224 bits |

The exact curve is `EC1N131Ckb1h6816f880945e`, prime subgroup order
`680564733841876926932320129493409985129`, and `isogeny: "none"`
(`ISO0`). Q20261010192300 retains null IC candidate/run IDs; the
weight-seven and weight-eight B/K values are conditional, not enumerated
factor-base records. Q1422's independently proved global relaxation of
this same index law is `2^78.552` actions for **any** permitted K, still
17.552 bits above `2^61`. Thus tuning the base size alone cannot make
this fixed explicit-index family fit the challenge.

For K columns, Q1422 grants as many as `M=min(U,K(131K+1))` distinct
pair-output keys in the universe `U=(r−1)/262`. A uniform nonzero target
and fixed partner schedule require at least `L=ceil(KU/(2M))` lookups for
a half chance of K hits, with every hit optimistically novel. All table
rows lie below the unconstrained index-size optimum, so the maximum M
minimizes `T=M+L`. At the weight-seven point, just storing one 17-byte
canonical key per granted index state would take at least
455,740,028,364,452,019,594 bytes, before witnesses and table overhead.

These are **necessary logical index actions** for Q1422's specified
nonadaptive family, not calibrated field operations or a complete-solve
`2^x`. They do not bound implicit algebraic PDP solvers, adaptive
target-dependent search, or guided nonuniform queries. The useful next
measurement remains an ordinary N83 four-point relation and its rank
novelty from a compact implicit solver, with all failed attempts charged.
