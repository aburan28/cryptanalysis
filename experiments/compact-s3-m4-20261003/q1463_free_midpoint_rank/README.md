# Q1463: free-midpoint linear-span screen

Q1463 tests whether a cheap linear-span relaxation can constrain both pair
midpoints before either is fixed. It is a posthoc diagnostic on Q1456's
archived SAT partial states, not a new point-decomposition solver. The
[protocol](protocol.json) froze the three input receipts, exact curve and
factor-base identities, field bridges, code hashes, a checked Sage runtime,
and the 4,096-pair cap before [the result](result.json) was produced.
This remains proposal `Q1463`, with `candidate_id: null`, `run_id: null`,
`isogeny: "none"`, and stage code `PDP4hybrid`.

For one pair, write its partial normal-basis leaves as
`a=a0+sum(ai*ei)` and `b=b0+sum(bj*ej)`. With midpoint `u` still free,
the chained link is

`S3(a,b,u)=(ab)^2 + u*ab + u^2*(a+b)^2 + 1`.

At the zero choice for the free midpoint bits, the coefficient of the
relaxed monomial `ai*bj` is `(ei*ej)^2`. Squaring is an invertible linear
map over `F_(2^n)`, so these coefficients have the same binary rank as the
products `ei*ej`. Q1463 ranks them for both leaf pairs in **every** archived
free-midpoint state. This deliberately treats monomials as independent and
allows all completions, even ones beyond the weight limit; it is a sound
necessary-condition relaxation. A full-rank pair has no linear equation
left with which that relaxation can reject the state. With nonzero target
preimage `t`, the free midpoint columns in the final link `S3(u,v,t)`
project as `t^2*ek^2` and span the final field equation. Thus the combined
three-link independent-monomial span is full when both pair ranks are full.

| Archived input | Partial states | Pair-product coefficient ranks | States with both exact midpoint sets enumerated | Exact midpoint affine ranks |
| --- | ---: | --- | ---: | --- |
| N53 known-satisfiable selected preimage | 21 | 53/53 in every state | 6 | 53/53 in every bounded state |
| N53 ordinary full target | 21 | 53/53 in every state | 6 | 53/53 in every bounded state |
| N83 ordinary full target | 23 | 83/83 in every state | 1 | 83/83 in the bounded state |

For the bounded states, Q1463 enumerates all nonzero leaf completions
within the exact W≤4 or W≤6 base rule, computes all `S3` midpoint roots,
and ranks the affine differences of each distinct midpoint set. The
[independent Sage replay](verification.json) recomputes the smallest raw
N53 and N83 states: their midpoint cardinalities are `[674, 626]` and
`[1521, 1521]`, and their affine ranks are `[53, 53]` and `[83, 83]`.
All 13 archived bounded rows agree on midpoint cardinalities with Q1460;
the 12 N53 rows contain repeated state patterns across the two workloads.

**Decision.** An unrestricted linearized monomial-span filter cannot
reject any of these 65 archived free-midpoint states. A filter based only
on a proper affine subspace containing each exact midpoint set also cannot
reject the 13 bounded rows: their affine hulls are the full field. This
does not exclude weight-aware nonlinear constraints, relations between
monomials, or a joint bilinear test of both midpoint sets and the target.
It does not measure ordinary relation yield or the cost of a successful
decomposition. N83 remains without a verified ordinary relation from this
solver, and the complete N131 `2^x` remains unknown; challenge dispatch
stays closed.

Reproduce the stage, including the independent Sage control, with:

```sh
python3 experiments/compact-s3-m4-20261003/q1463_free_midpoint_rank/freeze_protocol.py --check
python3 experiments/compact-s3-m4-20261003/q1463_free_midpoint_rank/build.py
python3 experiments/compact-s3-m4-20261003/q1463_free_midpoint_rank/run_screen.py --check
/Volumes/SSD990/cryptanalysis/sage -python experiments/compact-s3-m4-20261003/q1463_free_midpoint_rank/verify_sage.py --check
```
