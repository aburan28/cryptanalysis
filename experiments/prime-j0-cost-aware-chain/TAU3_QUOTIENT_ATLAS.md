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
fixture with seed `0xC06A81A219386D55`, excluding every earlier fixture
including the fused positional panel. Commit its generic reference digests
and the [paired runner](check_tau3_atlas_panel.py) before
executing either arm. Compare `tau3-fused-pos` and `tau3-atlas-pos` in
alternating order, preserve all raw failures, and require all 16 arms to
match the reference, zero candidate fallbacks, and exact equality of online
addition, rotation, and inversion counts in all eight cases. CPU timing
ratios remain exploratory without a host-level isolation receipt.

## Native old-fixture controls

The native map verifier exhausts all 6,561 entries and checks the exact
six-digit correction and action against the original C recoder. The curve
suite passes 2,306,779 checks, including identity, subgroup-order,
small-order, and over-capacity fallback cases. On the older compact
positional fixture, the [native differential
receipt](tau3-atlas-native-design.json) has identical original and atlas
action digests and group-operation counts across 32,768 scalars, with 16
generic-verified outputs and no fallbacks. Its [read-only
audit](audit_tau3_atlas_native_design.py) passes. The map adds exactly
26,244 static bytes to the parent implementation. Local elapsed times in
the receipt are exploratory and do not establish a CPU speedup.

## Prospective disjoint panel

The [new fixture](tau3-atlas-inputs.json) and its [read-only
audit](audit_tau3_atlas_inputs.py) establish 32,768 new scalars disjoint
from all earlier fixtures and eight generic reference output digests. They
were committed before either paired arm ran. The frozen
[runner](check_tau3_atlas_panel.py) alternated `tau3-fused-pos` and
`tau3-atlas-pos` first position by case. Its [raw
receipt](tau3-atlas-panel.json) and [read-only
audit](audit_tau3_atlas_panel.py) retain all 16 arms.

All 16 arms matched their generic outputs; all eight frozen operation gates
passed with zero fallbacks. The atlas matched the original recoder's action
digest, additions, rotations, and output inversions in every case. Across
the four points, each mode used 47,768 additions and 32,200 rotations on
`glv-j0-32`, and 97,713 additions and 65,911 rotations on `j0-56`.
The atlas retains the same 43,904 and 76,832 prepared-point bytes, plus
26,244 additional static map bytes.

Local `online_ms` is highly variable: the atlas was lower in seven paired
cases and higher in one. These are single, unisolated executions on a
contended host and cannot establish a CPU speedup. The next performance
gate requires a host-level isolation receipt and repeated paired runs.

After the panel, the repository's changed-line `clang-format` gate required
formatting of four C files and a merge of the parent PR's formatting update.
The original panel retains the source hashes from its frozen execution. The
[format custody receipt](tau3-atlas-format-equivalence.json) records
before/after source hashes and confirms the rebuilt benchmark binary is
**byte-identical** to the measured binary. The [read-only
audit](audit_tau3_atlas_format.py) checks the historical Git blobs, current
sources, and benchmark binary when available. The curve test still passes
2,306,779 checks; its executable hash changed with source line positions and
is recorded separately.
