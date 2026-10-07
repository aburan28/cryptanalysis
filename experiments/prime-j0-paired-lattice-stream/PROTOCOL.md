# Paired lattice representatives for a joint prime-field τ stream

## Frozen hypothesis

The existing joint `aP+bQ` evaluator chooses the shortest Eisenstein
lattice representative of `a` and `b` independently. It then pays for
the maximum of their two τ-stream lengths, plus both streams' nonzero
digits. Nearby exact representatives of either scalar can change those
costs without changing its subgroup action. Choose the two representatives
**together** to reduce the joint evaluation cost, with no new point table.

For each nonzero scalar, enumerate all 25 translations in the `[-2,2]²`
neighborhood of the existing rounded lattice coordinates. Convert each
to the existing `(1,τ)` basis and recode with the existing width-four
digit table. All enumerated values are exact members of the same scalar
coset modulo the declared subgroup order. Keep an empty stream for zero
scalars or identity points. Score every pair of candidate streams using

`C = 6 × (max(length_a,length_b) − 1) + 11 × (weight_a+weight_b)
     + rotations_a+rotations_b`.

The constants approximate the field-multiplication work of the existing
Jacobian τ map, mixed addition, and unit rotation; they are fixed *before*
measurement and are not CPU timings. Break ties by lower τ steps, lower
mixed additions, lower rotations, lower total coordinate L1 length,
then enumeration order. The chosen streams enter exactly the same prepared
18-point tables and one Horner accumulator as the current joint control.
Count the extra scalar reductions/recodings and all scored pairs; do not
hide their work in a point-operation claim.

## Gates

Test exact `aP+bQ` versus the generic group operation and existing joint
stream on both study curves, including zero, identity, order boundaries,
`UINT64_MAX`, equal and opposite points, and cancellation. Commit source,
checker, and a fresh fixture generator before generating a held-out
1,024-pair panel per curve. Freeze the fixture bytes and generic digests
before evaluating either τ arm. Retain every failed trial, paired order,
source/fixture hashes, preparation, recoding effort, τ steps, additions,
rotations, output inversions and exact replay.

The evaluation question is whether lower point work survives the recoding
overhead; report both. Local CPU wall time is exploratory without the
host-level isolation receipt. This is an opt-in research candidate, not
automatic rho routing or a claim of academic novelty. Joint τ recoding
has prior work on binary Koblitz curves, and cost-aware lattice-rep
selection already exists elsewhere in this repository for single scalars.
