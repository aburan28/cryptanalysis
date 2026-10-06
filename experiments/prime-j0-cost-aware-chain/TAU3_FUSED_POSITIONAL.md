# Width-three fused positional tau candidate

## Construction

Let `τ = 1 − ω` on the prime-field `j=0` curve. In the basis `(a,b)` for
`a+bτ`, multiplication by `τ` is `(−3b,a+3b)` and exact division is
`(a+b,−a/3)` when `3|a`. The ideal `(τ³)` consists exactly of coordinate
pairs `(9u,3v)`, so `(a mod 9,b mod 3)` gives 27 residue slots. Its 18 slots
coprime to `τ` are represented by the six-unit orbits of `1`, `2`, and
`1+τ`. Selecting the matching digit, subtracting it, and dividing by `τ`
produces a width-three expansion: at most one nonzero digit in every three
consecutive positions. The [generator](make_tau3_fused.py) fixes all digit
IDs, residue slots, and tie rules.

Group six consecutive tau digits into one positional block. Each half has
55 patterns (zero or one of 18 digits at one of three positions). Exactly
2,053 ordered pairs are valid under width-three spacing. Quotienting by the
six curve units leaves 343 orbits, including zero: 18 one-digit and 324
two-digit orbits. The generated map stores an orbit ID and a unit code for
every ordered pair. A prepared point for each orbit at each block position
allows one online mixed addition per nonzero six-digit block, plus at most
one field multiplication for unit rotation. The identity `τ⁶ = −27` makes
the position progression exact; it does not require an online radix step.

Prepare `1`, `2`, and `1+τ` times the base point, their tau images at the
six within-block positions, and each selected orbit representative point.
The block count is one spare block plus the number of base-729 digits in
`r−1`. This gives four and seven blocks on the study curves, hence 1,372
and 2,401 affine table slots (43,904 and 76,832 bytes). A scalar requiring
more blocks must use the generic multiplier and report a fallback. The map
uses 27 residue entries and 3,025 pair entries; count map bytes separately
from prepared points.

This is a new **candidate implementation**, not a proven academic novelty
claim. Width-w tau nonadjacent forms and symmetric digit sets for prime-field
`j=0` curves have [prior art](https://eprint.iacr.org/2013/705.pdf).
The exact six-step positional orbit table must be checked against that and
other work before claiming novelty. The mode is variable-time and applies
to public scalars in a prepared-point research workload.

## Retrospective design screen

The generated header SHA-256 is
`a2f8940844b27c45b79721e776f0dfa128d3c817fca3a08083e6ef589f9cedcc`.
The [read-only audit](audit_tau3_fused_design.py) checked all 2,053 valid
pair transformations, byte-for-byte regeneration, and termination,
width-three spacing, and exact reconstruction for all 90,601 coefficient
pairs in `[-150,150]²`. The [screen](tau3-fused-screen.json) reused an older
fixture; these are predictions, not a prospective native result:

| Curve | Compact width-four additions, four points | Predicted fused width-three additions | Predicted saving | Prepared point bytes |
| --- | ---: | ---: | ---: | ---: |
| glv-j0-32 | 62,323 | 47,757 | 23.37% | 43,904 |
| j0-56 | 134,062 | 97,715 | 27.11% | 76,832 |

The full six-step table is larger and more expensive to prepare than the
compact width-four positional table. The screen counts one addition for
each nonzero fused block and assumes every prepared orbit point is correct.
It does not measure preparation cost, recoding overhead, memory traffic, or
CPU time. A lower addition count alone cannot establish a CPU or rho win.

## Native and held-out protocol

Freeze this generator, map, screen, audit, and protocol before the native
implementation. Native tests must check all map states and unit actions,
exact point outputs against generic multiplication, identity, subgroup-order
and small-order cases, and an explicit over-capacity generic fallback. Match
every native action stream on the old design fixture to this frozen Python
recoder before generating new inputs. Record preparation operations,
inversions, point bytes, static map bytes, online additions/rotations,
fallbacks, conversion, and output replay.

Then freeze the native implementation and a new disjoint 8 × 4,096-scalar
fixture before comparing `tau3-fused-pos` with `pos-compact`. Use seed
`0xF12C804D9387A61B`, SplitMix64 rejection sampling, the same four points
per curve, and exclude all prior fixture scalars. Commit generic-reference
output digests and paired runner before either arm runs. The prospective
operation gate requires verified outputs on all 16 arms, zero candidate
fallbacks, and strictly fewer candidate mixed additions in all eight cases.
The online interval starts with the first scalar reduction after point
preparation and ends after the final affine output. Save every raw failure,
timeout, and output digest. Controlled CPU timing needs host-level isolation
and at least five paired AB/BA repetitions; the local Mac panel is
algorithmic evidence only.
