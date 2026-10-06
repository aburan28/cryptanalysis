# N83 candidate screen: cost accounting and promotion gates

This screen compares complete-pipeline *prospects* on the same exact N83
subgroup. It does not assign an `IC1` candidate ID: no proposal here has a
frozen, verified decomposition solver, relation collector, final matrix solve,
factor-log precomputation, and target descent. The public target remains
unselected, so these geometry rows are not one-target workload runs.

The [machine ledger](cost_screen.py) leaves every missing price `null`.
Its output is a screen artifact, not a version-2 empirical run row. An exact
tuple count divided by the subgroup order is a counting diagnostic; even a
ratio above one neither proves coverage nor predicts useful relation yield.
Planted SAT instances establish correctness of a positive control only.

## Complete one-target bill

Freeze one previously unseen public point `Q`, its subgroup/field encoding,
hardware envelope, worker count, memory and wall limits, code hashes, target
and query seeds, and the reusable precomputation state. Once that state is
ready, time one exclusive target-dependent interval:

```
T_online,1 = T_target_query + T_target_PDP + T_target_relation_check
           + T_target_descent + T_target_recovery_check
```

Charge every failed, timed-out, and repeated target-dependent attempt. Include
target-specific map evaluation or conversion in `target_query`. Keep scalar
replay in the result and, for this screen's eventual primary comparison, in
`target_recovery_check`. A complete row requires all five times, a verified
`[k]G=Q`, and the same-point verified rho online interval under the same
resource envelope. The only primary speedup is `rho_online_ns/T_online,1`.
If any component or paired rho result is missing, leave the speedup `null`.

The separately disclosed empty-cache bill is:

```
T_cold = T_setup + T_isogeny + T_factor_base + T_precompute
       + T_queries + T_PDP + T_relation_check + T_matrix_build
       + T_relation_LA + T_target_descent + T_recovery_check
```

Record wall time, CPU time, peak and retained memory, I/O bytes, and worker
occupancy by phase. Do not replace an unmeasured phase by zero. The target
input point is already given: known-scalar fixture construction is outside
both intervals. Index construction, factor logs, matrix solving, cache
warming, and base construction are reusable preparation and belong in the
cold bill, not the online interval. If they are performed after `Q` arrives
and depend on `Q`, charge them online. A secondary multi-target amortization
needs its own named workload and shared-cost denominator; it cannot answer
the one-target question.

Operation counts must carry units. Preserve group additions, field operations,
Boolean propagation/conflicts, Macaulay operations, matrix nonzeros and
iterations, and bytes moved separately. A scalar total in group-operation
equivalents requires a frozen calibration of all charged operations and
conversion/transfer costs before measuring. Only then report supplementary
`S=C_total/sqrt(r)` and compare it with a declared rho operation reference.
Wall time remains the primary empirical metric. CPU timing ratios on this
contended host are exploratory until the isolated-host receipt in
[`docs/ISOLATED_BENCHMARKS.md`](../../docs/ISOLATED_BENCHMARKS.md) passes.

## What the geometry does and does not price

`B` counts distinct usable subgroup points in one slot before orbit folding.
`K` counts global signed-Frobenius orbit classes that meet that slot. For the
shifted slots, each slot is a Frobenius image of the same base, so its `B` and
`K` are equal. The exact ordered tuple count is `B^m`. For the invariant full
W4 base, the existing five-sum diagnostic uses unordered multisets
`binomial(B+4,5)`. Both are divided by `r`; `min(1, count/r)` is only a support
ceiling. The two tuple models have different symmetry assumptions and cannot
be treated as measured coverage or compared as equal PDP costs.
The nominal Boolean coordinate count is `m*d` for shifted slots and `5*83`
for the unrestricted normal-mask W4 encoding; equations and auxiliaries can
make actual SAT or Macaulay instances much larger.

For a proposed *explicit* index over one distinct pair of shifted slots,
there are `B^2` logical input pairs. If an implementation stores every pair
as a compressed 83-bit sum point (12 bytes including sign) and two fixed-width
indices, its raw payload is `B^2*(12+2*ceil(ceil(log2(B))/8))` bytes. This
conditional size excludes hash overhead, duplicates, disk structures, I/O,
and build/search time. It is not a lower bound on every possible solver; a
SAT or polynomial solver may materialize no pair index. The existing W4 root
index has its own measured pair-state loop count and is reported separately.

The actual matrix needs a rank trajectory, not just `K`. At each frozen rank
checkpoint, retain ordinary-query counts for verified decompositions,
verified relations, duplicates, dependencies, timeouts, OOMs, and zero-yield
cells. If `c_j` is mean charged attempt cost and the probabilities are
measured on the same ordinary-query stream, the local diagnostic is
`c_j/(p_coverage,j*p_solve|coverage,j*p_novel|solved,j)`.
Integrate observed attempts and costs along the changing rank trajectory;
do not multiply one optimistic yield by `K`. If a denominator is zero or
censored, the cost estimate is unknown or bounded, never finite by fiat.
Report binomial intervals for yield and paired intervals for cost, including
timeouts as non-completions under the declared cap.

## Decisions this screen can support

The N83 W4 SAT result is a verified planted circuit control with a bounded
unknown solve under its original cap; it supplies no ordinary-query yield.
The shifted-base measurements can reject an impractical explicit index or
show a smaller matrix, but they cannot promote an IC speed claim. A next
solver pilot must first pass planted replay and small-field false-lift
controls, then run frozen ordinary queries at equal caps. Only a measured
stage survivor proceeds to relation rank, factor logs, one unseen target,
and a same-point rho run. Preserve every failed stage row.

For an alternative with smaller `B`, seven or eight Frobenius-shifted slots
can keep the total Boolean coordinate count near 83 while reducing per-pair
index size; the higher-arity solver, tuple support, and matrix `K` must be
measured afresh. This is a new design axis, not a predicted speedup.
