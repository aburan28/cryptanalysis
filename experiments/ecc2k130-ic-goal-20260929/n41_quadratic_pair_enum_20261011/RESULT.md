# Quadratic reciprocal enumeration for binary pair relaxations

The halftrace pair equation reduces exactly to at most two trace-zero reciprocal candidates per seed-sum/product choice. On the frozen N41 W6 instance, the quadratic enumerator produced the same **128,656 curve points** as the complete linear-map enumerator and repeated all nine target queries with the same hit/miss statuses. This removes the need to build and solve an `n × n` binary linear system for each product coefficient when the goal is trace-zero pair enumeration.

## Derivation

Let `F(z)=z²` on `GF(2^n)` for odd `n`, and let `H(w)=Σ_{i=0}^{(n-1)/2} w^(2^(2i))`. Then `(F+1)H(w)=w+Tr(w)`. The relaxed pair equation is

`p z + H((s+z)²) + ε = 0`, with `ε ∈ GF(2)`.

Applying `F+1` and requiring `Tr(z)=0` gives

`(p²+1) z² + p z = s² + Tr(s)`.  (1)

For every fixed `p,s`, equation (1) is a genuine quadratic or a nonzero linearized monomial: its coefficients cannot both vanish. It therefore has at most two solutions in the field. For each such `z`, compute `ε = pz + H((s+z)²)` and retain it exactly when `ε ∈ GF(2)` and `z ≠ 0`. The resulting points are lifted on `y²+xy=x³+1`, with both signs. The residual check makes the reduction exact; applying `F+1` alone would lose one bit of the original equation.

The same argument with `Tr(z)` unconstrained gives at most two roots for each trace bit, so the kernel of `z ↦ pz+H(z²)` has at most four elements and binary nullity at most two for every `p`. This proves the rank floor `n-2` underlying the prior N41 rank census, without enumerating all `p`.

## Complete N41 comparison

The [frozen protocol](protocol.json) binds the source, executable, field helper, exact nine-point input, and prior receipt. The native comparison enumerated both constructions independently into point sets, compared all points, then ran the nine frozen group joins using the quadratic set. The [receipt](receipt.json) records:

| Quantity | Value |
| --- | ---: |
| Linear-map point set | 128,656 |
| Quadratic point set | 128,656 |
| Complete point-set equality | true |
| Quadratic roots inspected | 128,385 |
| Roots passing trace/residual checks | 128,385 |
| Positive query | `RELAXED_SUM_HIT`, 21,713 probes |
| Eight target-derived controls | `COMPLETE_RELAXED_NO_SUM`, 128,656 probes each |
| Linear-map enumeration in this process | 2.376019125 s |
| Quadratic enumeration in this process | 4.211611541 s |

The local wall times are exploratory and this run has no host-isolation receipt. The quadratic code uses two field inversions per product coefficient and repeated halftrace evaluation; the linear-map implementation is faster in this N41 run. The exact reduction is useful for a target-conditioned constraint encoding because it removes the 41 reciprocal bits from the per-pair linear solve while preserving a complete witness path. For a low-power monomial W15 span at N131, the product span has dimension at most 29; direct enumeration still scales as roughly `2^29 × 2^15` coefficient choices, so the next experiment must make the target constrain these choices before enumeration.

This is a component result (`candidate_id: null`). The original positive point and all eight controls are the frozen right-middle inputs from the preceding [direct join](../n41_direct_relaxed_pair_join_20261011/RESULT.md). The comparison inherits its Sage check of the positive group witnesses; full native point-set equality and replay of the nine queries test the new enumerator against that independently verified result.
