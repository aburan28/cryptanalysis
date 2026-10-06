# Follow-up hypotheses and promotion gates

These are proposals, not implemented algorithms or measured wins.

## Exact symmetry inside a query

Test exchanging the first two coordinate blocks before attempting a full
three-block orbit method. With `L = 2^ell`, unordered fixed-block pairs number
`L*(L+1)/2`, compared with `L^2` ordered pairs. This is an exact reduction in
representative count when the packed original equations are invariant under
that exchange. It does not imply the same factor in complete-query time.

Check coefficient-wise symmetry on **each fresh original input**, including
all equation bits and cancellation, before using it. A successful check makes
the residual equations for `(a,b)` identical to those for `(b,a)`. The first
prototype can solve representatives, copy their actual contradiction
identities, and transport/expand roots into the existing full certificate
format. The unchanged independent checker then validates every identity and
every actual root against the original equations. This avoids relying on a
producer's assertion about symmetry. Failure of the input symmetry check
must select the complete existing path.

Tests must include asymmetric perturbations, equal blocks, repeated roots
under an orbit, empty and unit ideals, width boundaries, fresh target reuse,
and budget failures during representative work and output expansion. Count
actual representative reductions separately from represented branches.
Account for symmetry checking, root transport, sorting, certificate expansion,
and the unchanged independent checker in complete-query time. Pair with the
strongest applicable round34 CPU and requested Metal arms on the same inputs.

A full six-element coordinate-permutation reduction is a different problem:
permutations can exchange a fixed block with the free residual block. Sorting
all three coordinates restricts the residual domain, so a failed search in
that domain is not a contradiction identity for the unrestricted equations.
Do not extend the two-block reasoning to sixfold proof reuse without an exact
domain/completeness argument and corresponding independent checker.

## More work per GPU launch within one target

First extend constant elimination from at most 31 features to the 36/45/55
quadratic features for residual dimensions 8/9/10. Keep explicit capability
checks, source/binary receipts, bounded allocations and CPU fallback. Measure
this stage's share of complete time before claiming it can solve the new
bottleneck: round34's affine elimination remains a separate CPU stage.

For affine elimination, compare threadgroup-cooperative row reduction on a
small tile of independent branches with a thread-per-branch design. The
latter can spill substantial private pivot storage: a nine-variable cubic
layout has 130 columns, and a dense tracked pivot set includes both cubic
rows and ten equation-combination coefficients. Freeze actual device-memory
and operation limits, compact only successful proofs, and validate the
original identities independently on the CPU. Count launch, synchronization,
transfers, output compaction, proof copies and checking inside the query.
Do not substitute throughput across unrelated targets for one-query latency.

Keep a proof-budget exhaustion control and the existing degree-one
counterexample. Successful compilation, device availability or matrix-only
speedups are not enough to enable automatic device routing. Require repeated
complete-query wins against the best paired CPU implementation, with no
correctness or limit regression, on each claimed physical device.

## Asymptotic and IC questions remain separate

Changing branch representatives by a constant factor, improving storage,
and accelerating bounded low-degree elimination do not establish a lower
asymptotic exponent. A broader algorithm claim needs an applicability theorem,
complexity analysis including failed branches and proof generation/checking,
and difficult examples outside the planted controls. General F4/signature
baselines and high-regularity systems remain necessary comparisons.

After a component is promoted, rerun complete recovery for one previously
unseen public target, paired with rho on that same point and resource envelope.
Use the repository's immutable candidate/workload/run manifests, separate
reusable setup, retain all failed attempts, independently verify the recovered
scalar, and report the full charged online interval. Component improvements
alone cannot answer this end-to-end question.
