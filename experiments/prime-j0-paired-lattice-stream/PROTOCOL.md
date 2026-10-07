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

## Development refinement, frozen before held-out generation

An exploratory run on the old PR #419 fixture showed that 25 neighbors per
scalar save point work but spend heavily on recoding. Before making the new
held-out fixture, add two explicitly named constrained searches with the
same score and prepared points:

- `paired5`: rounded lattice center and four axial neighbors. Recode all
  five representatives per nonzero scalar and score all pairs.
- `paired2`: inspect the coordinate L1 lengths of those five axial choices;
  recode only the best two per nonzero scalar and score at most four pairs.
  Ties use the fixed axial order `(-1,0),(0,-1),(0,0),(0,1),(1,0)`.

All three use the existing four-decision τ residue atlas, whose output is
checked against the canonical digit generator. The `paired` arm retains
the original 25-by-25 search. The three searches are an adaptive design
family motivated by old-fixture development, so they require a **new**
held-out fixture for evaluation. Do not use old-fixture local wall times
as a result. The held-out paired order is `joint, paired2, paired5,
paired, paired, paired5, paired2, joint` on each curve.

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
automatic rho routing or a claim of academic novelty.
[Joint τ recoding on binary Koblitz curves](https://arxiv.org/abs/1801.08589)
and [endomorphism lattice decomposition](https://arxiv.org/abs/1310.5250)
have prior work; cost-aware lattice-rep selection already exists elsewhere
in this repository for single scalars.
