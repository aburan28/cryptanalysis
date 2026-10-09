# Three-bucket tau-orbit atlas for fixed-base scalar multiplication

The candidate uses the same short Eisenstein scalar representative and thirteen
integer-radix windows as the verified unit-orbit multiplier. Its table stores
one point for a selected residue seed. A lookup may use that point after a
unit action and zero, one, or two applications of the nonunit endomorphism
`tau = 1 - omega`. Selected points are accumulated in three buckets by tau
exponent; tau is applied to the completed buckets, so its online cost is
bounded by one `tau` and one `tau^2` point map per scalar rather than one map
per table lookup. This is a public-scalar, fixed-generator experiment.

## Frozen instance and mathematical gate

Use secp256k1 subgroup order `n`, the existing four-corner shortest
representative of `k` in `Z[tau]/(n)`, integer radix `R = 1021`, thirteen
windows, and the digit-length bound `D = 840`. The norm in `(a,b)` coordinates
is `N(a+b*tau) = a^2 + 3ab + 3b^2`; multiplication by tau triples the norm.
Since `gcd(R,3) = 1`, tau permutes residue classes modulo `R`. Quotient the
classes by the six units, then decompose tau's permutation into cycles.

For a cycle node `v`, let `s(v)` be its four-corner shortest digit. A stored
seed at `v` may cover its next `L(v)` nodes, where `L(v)` is the largest of
1, 2, or 3 satisfying `3^(L(v)-1) * N(s(v)) <= D^2`. For each cycle, evaluate
all three possible cut positions near a fixed origin and use a linear
shortest-path recurrence to choose the minimum number of segments. Ties favor
the smallest cut position and then the longer next segment.
The actual digit for a residue is an exact unit image of `tau^e s(v)`, where
`e` is 0, 1, or 2. Check all `R^2` residue classes for exact congruence,
unique code assignment, norm at most `D^2`, and equality of the mapped point
with the intended digit multiple.

The thirteen-window termination gate uses the exact bound

`||z_13|| <= sqrt(n/3)/R^13 + D*(1-R^-13)/(R-1) < 1`.

Check the strict inequality using integer arithmetic. Since nonzero
Eisenstein integers have norm at least one, the final coefficient is zero.
Retain each cycle's length, allowed segment lengths, selected seeds, and a
digest of the complete residue-to-seed map. A failed coverage or contraction
gate ends this candidate without a native timing claim.

## Frozen resource and correctness panel

The point-table cap is 90 MiB of retained payload, including thirteen affine
seed rows, the residue code map, seed digits, row pointers, and metadata. The
reference is U14, which uses 14 selected points, at most 13 mixed additions,
and 78,470,184 retained bytes. This candidate uses at most 13 selected points
and 12 mixed additions, plus the two bucket endomorphism maps and any bucket
merge costs. Report identity selections and bucket occupancy; do not infer
online speed from the addition count or table size.

First replay the seven boundary scalars and 512 seeded scalars from
`experiments/prime-j0-radix943-word-20261009/inputs.json`. Record the exact
input digest and every coefficient reconstruction. Then check all 129 frozen
fixture points and 128 fresh points against independent binary multiplication
in the native evaluator. Preserve failures, table-build time, and peak memory.
Only after those gates, generate a same-binary paired U14/candidate manifest
whose timer includes scalar reduction, recoding, lookups, unit maps, bucket
accumulation, tau and tau-squared bucket maps, final point addition, affine
conversion, and expected-point verification. Run CPU timing only on a host
passing `docs/ISOLATED_BENCHMARKS.md` and preserve all preflight/noise rows.
Prior-art review must cover tau-adic precomputation and endomorphism digit
orbits before an academic novelty statement.
