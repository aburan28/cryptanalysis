# Orbit-quotiented paired-row tau comb: frozen experiment protocol

## Construction

Keep the existing public-scalar hex9 selector, width-six digit atlas,
13-column schedule, and 1,024-point base table. Pair the first twelve rows as
`(0,1), (2,3), (4,5), (6,7), (8,9), (10,11)`; leave the sparse top row and its
two-point repair unchanged. For each pair of rows with bases `P` and `Q`,
precompute one affine point

`T[o,p,v] = D_o(P) + v D_p(Q)`

for every pair of 81 digit orbits `o,p` and each of the six units `v` in
`{+1,-1} × {1,omega,omega^2}`. There are exactly `81*81*6 = 39,366`
entries per row pair, `236,196` total. If the two selected row digits are
`u D_o` and `w D_p`, use `u T[o,p,u^-1 w]`. The unit action commutes with
point addition, so this replaces two selected points with their exact sum.
Single nonzero rows use the existing table. The top-row repair is evaluated
exactly as before.

The online evaluator must account for all pair-index computation, unit maps,
table access, scalar selection, recoding, point arithmetic, affine output,
and result verification. Table construction and normalization are reusable
fixed-generator preparation and are recorded separately. The method is
variable-time and is restricted to public scalars.

## Frozen inputs and gates

- Parent: commit `5bbf3142d7be14bc3254ec348324909cc722c402` (PR #527).
- Design screen: 2,048 independent scalars from Python `random.Random(2026100993).randrange(n)`.
- Fresh validation: 2,048 scalars from seed `20261009113`, plus all 214
  frozen parent scalars, all 129 independently expected benchmark fixtures,
  and boundary values `0,1,n-1,n,n+1`.
- Correctness: every selected representative and point must equal the parent
  hex9 output; at least 256 fresh points plus boundaries must also match an
  independent secp256k1 reference. Every precomputed pair entry used in a
  correctness sample must equal the direct two-addend result.
- Operation comparison: count actual mixed additions and tau maps in both
  binaries over identical scalars. Report total and paired distributions,
  including repairs and every failure. A proxy improvement requires exact
  agreement between predicted pair fusions and observed addition counts.
- Resource record: include exact affine table count, total table bytes, peak
  resident memory during preparation, and preparation wall time. A variant
  needing more than 256 MiB peak additional memory or more than 60 seconds of
  local preparation remains a diagnostic until its layout is improved.
- CPU wall time: compare complete online intervals only through the isolated
  benchmark service with a passing host-level preflight and noise gates.
  Preserve failed rows; do not infer a speedup from point-operation counts.

## Design-screen observation

On the 2,048-scalar design screen, 50,306 row digits occupied 26,624
columns. The six fixed pairs co-occurred 7,395 times, an exact potential
reduction of 7,395 mixed additions if all corresponding pair points are
available. An unrestricted within-column pairing oracle could fuse 19,305
digit pairs, but would require a much larger family of row-pair tables.
The fixed-pair result is the implemented target; the oracle is a bound.

A separate 4,096/4,096 design/holdout screen at seed `2026100997` found
that a table containing only the 14,716 raw digit-pair patterns observed in
the design half covered 163 of 14,697 fixed-pair co-occurrences in the
holdout half. The proposed table therefore covers the complete orbit-pair
alphabet instead of using an observed-pattern cache.
