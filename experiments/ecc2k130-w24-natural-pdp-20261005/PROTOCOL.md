# Frozen ECC2K-130 source W24 six-summand PDP gate

This protocol tests whether a concrete SAT point-decomposition implementation
can find a natural six-summand relation on the exact source W24 base in the
[equal-size four-policy workload](../ecc2k130-263-equal-w24-workload-20261005/RESULT.md).
It is a stage gate for proposal `Q1420`, not an `IC1` candidate or a claim
that index calculus beats rho. The frozen one-target input is source point
index zero in `primary_workload.json`, workload ID `eee7f6ee5f6b`. No other
target or alternate base is selected after seeing solver output.

The input hashes, binary hash, limits, and exact base size are in
[CONFIG.json](CONFIG.json). Work in the source field
`GF(2^131)` with modulus `t^131+t^13+t^2+t+1` on
`y^2+xy=x^3+1`. The source base is the first 8,386,414 ascending rational
W24 masks, ending at `16763440`: 16,772,828 distinct usable subgroup points
before sign folding. For each six-summand slot, choose a 24-bit nonzero mask
at or below that bound and set
`w=sum(mask_j*(t^(j+1)+Tr(t^(j+1))))`. Require `w*v=1` and `Tr(v)=0`.
The latter is exactly the source rational-lift test `Tr(1/w)=0`, not a
post-solve heuristic. Set `u=H(w)`, where the odd-degree half-trace
`H(w)=sum_{i=0}^{65}w^(4^i)` satisfies `u^2+u=w`, and
`x=1+1/u`. Either sign of a rational point with this x is admitted. The
subgroup factor-base point is `[4]P`; both signs are in the declared B.
Repeated masks are allowed and must be retained in relation coefficients.

Let the frozen public source point be `Q`, subgroup order be `r`, and
`R=[4^(-1) mod r]Q`. In this cofactor-four curve, the four raw targets in
fixed order are `R+T` for `T=O,(0,1),(1,0),(1,1)`. The implementation must
verify `[4](R+T)=Q` for all four before building SAT. Two selector bits
choose one fiber in a *single* ordinary-query formula. A fiber with
`x=1` or infinity makes this nonexceptional encoding unsupported; record
the failure rather than replacing that fiber or target.

Represent all nonexceptional x-coordinates by `x=1+1/u`. Introduce four
unrestricted, nonzero intermediate u values and impose five consecutive S3
links from six leaf u values to the selected raw target u. A link on
`u1,u2,z` is

`(z^2+z)(u1^2+u1)(u2^2+u2) + (u1+u2+z)^2 = 0`.

This is the denominator-cleared Semaev S3 identity for this exact curve;
every intermediate denominator must be nonzero. The fixed chain order is
`(((((P1+P2)+P3)+P4)+P5)+P6)`. Do not add a zero-sum W constraint,
Frobenius rotation, selected favorable fiber, or known target scalar. Build
one native-XOR XCNF with Karatsuba field multipliers, one worker, seed zero,
and the CryptoMiniSat binary pinned in the config. A SAT assignment is only
a candidate until independent group replay succeeds.

First profile the formula and run a planted correctness control using the
first six published source control masks in `base_selection.json` in their
published order. For each mask, choose the rational y with the smaller
polynomial-basis integer encoding, sum the six raw points, and pin all six
masks while solving the same chain construction against that raw sum. If an
intermediate is exceptional, or the control does not return a verified SAT
witness under 30 seconds and 100,000 conflicts, record failure and do not
run the natural target. This control does not estimate ordinary yield.

If the control passes, run exactly one ordinary formula for the frozen Q
with a 600-second and 2,000,000-conflict bound. The formula build has a
300-second bound; the builder checks its RSS at regular gate intervals and
the solver child is polled every 500 ms and killed above a 4 GiB RSS cap.
This host does not support lowering `RLIMIT_AS`, so the receipt must state
the observed peak and monitor outcome; a failed monitor invalidates the run.
Keep XCNF hash, source and binary hashes, variable/gate/clause counts,
construction and solve durations, solver exit/status, timeout/OOM/failure,
and any full model. For each model, independently reconstruct every mask,
check it belongs to the frozen base, enumerate rational sign choices,
verify the raw six-point sum against the selected fiber, verify the six
projected points and `[4]sum=Q`, and separately check the public Q against
its withheld fixture scalar. Preserve an invalid model as a failure row;
do not call SAT alone a verified relation. A single model is the limit;
zero models under the bound means *unresolved*, not zero natural yield.

The target-dependent fiber calculation is charged to target query time;
formula build and solve are charged to target PDP; independent group replay
is charged to target relation check. Include all failed attempts in these
stage costs. Sage arithmetic and independent replay must use the checked
repository launcher, with `--runtime-info` saved before the workload and
outside the timed interval. Host-level CPU isolation is unverified, so any
wall timing is an exploratory stage diagnostic. This run measures neither
useful matrix rank nor a recovered discrete logarithm. `candidate_id`,
complete single-target online time, and rho speedup remain `null`. The
transported and native-descendant policies remain for paired follow-up on
the same workload once this source solver passes its controls.
