# One-slot alternate digit atlas result

`alternate_digit_atlas.py` and its protocol were frozen in `58120082`
before execution. The output `alternate-digit-atlas-result.json` records
the source and original 64-case fixture hashes. It enumerates 133 distinct
one-slot replacement unit orbits with norm at most 400. The closed-ball
termination check accepts 127 and retains six cycle witnesses. It exactly
reconstructs all 64 short coefficient pairs for each accepted table.

The best **evaluator-only** candidate replaces slot 6 with orbit
`(-11,5)`, saving 187 `M+S` across the 64 design cases before seed
construction. That is 2.92 units per scalar. Thirty-one one-slot changes
have positive evaluator-only savings. They are not full one-use wins.

Every positive candidate except slot 5 `(-10,6)` requires at least five
point additions to construct the nine distinct seed orbits, because the
replacement is not a double or τ image of any other required seed. The
other three nonbase seeds require at least doubles. The resulting point
cost is at least `5*11 + 3*7 = 76`, versus 72 currently. At least one
unit rotation (or a more expensive τ operation) is necessary to generate
an off-integer seed from the input point. Including the nine orbit-image
multiplications gives at least `76+1+9=86`, versus the current 83.
Across 64 one-use scalars, that adds at least 192 units, exceeding the
best evaluator saving of 187.

The exceptional slot 5 candidate `(-10,6)` is double of existing seed
8 and saves 153 evaluator units. The unchanged slot 6 can then be
formed as `4P−(2P−4τP)`, replacing its current doubling with a
projective addition. In the existing representations this is a
14-unit addition, so preparation increases by three units per scalar
(`+192` across 64) and the straightforward one-slot chain loses at
least 39 units. A differently scheduled chain or a fused formula is
not ruled out. The other lower bounds apply only to the one-result
double/τ/add and unit-rotation source-count model. Full CPU timing
requires separate evidence.

The joint replacement in `JOINT_ATLAS_PROTOCOL.md` resolves the slot 5
dependency by replacing slot 6 as well, allowing two cheap doublings
from seed 8. Its held-out evaluation is a separate gate.

No CPU speedup or academic novelty is claimed.
