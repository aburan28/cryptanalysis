# Six-step quotient atlas for fused positional tau

This is a recoder change for the [width-three fused positional tau
candidate](TAU3_FUSED_POSITIONAL.md). It keeps the same prepared points,
orbit actions, group operations, and variable-time public-scalar scope.

Since `τ⁶ = −27`, six width-three decisions give an exact correction
`C = Σ_{i=0}⁵ dᵢτⁱ`. The next coefficient state is `(C−z)/27` for
`z = a+bτ`. The six decisions depend only on `(a mod 81,b mod 81)`: the
difference between two such states is divisible by `τ⁸`, and after at most
five divisions remains divisible by `τ³`, the digit-selection modulus.
This yields one 6,561-entry lookup per block. An entry stores two signed-byte
correction coefficients and a packed orbit action, so the C table is
26,244 bytes. This replaces up to six successive digit lookups, signed
remainders, and exact divisions with one atlas lookup and two divisions by
27. Point preparation is identical to the parent candidate.

The generated table is a candidate optimization, not a CPU speedup claim or
an academic novelty claim. The existing width-four [four-decision
atlas](README.md) and published width-w tau recoding are related precedents.

## Freeze and gates

Freeze the [generator](make_tau3_atlas.py), generated header, and
[read-only design audit](audit_tau3_atlas_design.py) before native changes.
The audit regenerates all 6,561 entries and compares 100,000 signed
coefficient action streams to the original width-three recoder. Native work
must check exact action-stream agreement on the older fixture and include
identity, subgroup-order, small-order, and forced over-capacity cases.

After freezing native source, generate a new disjoint 8 × 4,096-scalar
fixture, excluding every earlier fixture including the fused positional
panel. Commit its generic reference digests and the paired runner before
executing either arm. Compare `tau3-fused-pos` and `tau3-atlas-pos` in
alternating order, preserve all raw failures, and require all 16 arms to
match the reference, zero candidate fallbacks, and exact equality of online
addition, rotation, and inversion counts in all eight cases. CPU timing
ratios remain exploratory without a host-level isolation receipt.
