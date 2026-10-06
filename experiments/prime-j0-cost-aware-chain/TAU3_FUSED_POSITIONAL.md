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
| glv-j0-32 | 62,323 | 47,705 | 23.46% | 43,904 |
| j0-56 | 134,062 | 97,709 | 27.12% | 76,832 |

The first native old-data check exposed a 14-addition discrepancy in the
initial Python screen. The C lattice reducer uses `r − endo_lambda`; the
screen had passed `endo_lambda` to its independent representative helper.
The corrected screen above uses the C lattice eigenvalue. The generated
digit and orbit map is unchanged. This correction was made before any new
fixture was generated or prospective arm was run.

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

## Native old-data controls

The first native run exposed the lattice-eigenvalue mismatch described
above; after correction, its addition and rotation counts match the Python
screen exactly. The native curve suite passes 2,306,609 checks, including
all map entries, every prepared orbit point on the tested curves, the
identity, subgroup-order multiples, a small-order subgroup, and a forced
over-capacity generic fallback. On the older frozen fixture, the
[native differential receipt](tau3-fused-native-design.json) verifies all
32,768 outputs and compares every C action stream to the Python generator.
The [read-only audit](audit_tau3_native_design.py) replays the compressed
native traces and passes. The smaller curve prepares 1,372 point slots with
27 triples, 60 tau steps, 1,296 projective additions, 864 unit rotations,
and two normalization inversions. The larger prepares 2,401 slots with
54 triples, 105 tau steps, 2,268 additions, 1,512 rotations, and two
inversions. The selected static map is 9,826 bytes. These preparation
counts are separate from the online addition saving.

## Prospective disjoint panel

The [frozen fixture](tau3-fused-inputs.json) was committed after its
[read-only audit](audit_tau3_fused_inputs.py) confirmed 32,768 fresh scalars,
disjoint from every earlier fixture on each curve. It includes eight generic
reference output digests. Only then did the frozen
[paired runner](check_tau3_fused_panel.py) execute the 16 arms, alternating
the mode order by point case. The [raw receipt](tau3-fused-panel.json) and
[read-only panel audit](audit_tau3_fused_panel.py) retain and check every arm.
All 16 arms matched their generic output digest, all eight operation gates
passed, and there were no candidate fallbacks.

| Curve, four paired points | Compact width-four additions | Fused width-three additions | Addition saving | Compact rotations | Fused rotations | Fused point bytes |
| --- | ---: | ---: | ---: | ---: | ---: | ---: |
| glv-j0-32 | 62,420 | 47,778 | 23.46% | 40,780 | 31,877 | 43,904 |
| j0-56 | 133,989 | 97,684 | 27.10% | 87,678 | 65,901 | 76,832 |

Both modes used 16,384 output inversions per curve across the four points.
The compact table uses 6,336 and 12,096 point bytes, respectively. The fused
mode additionally uses the 9,826-byte static action map and more costly
preparation described above. Its unisolated local online times were **higher
in all eight cases**; the raw values are in the receipt. Thus the measured
operation saving has not translated into a measured CPU speedup. These local
times are exploratory because the host lacks an isolation receipt, and no
controlled speedup or one-target rho claim follows from this panel.

After the panel, the repository's changed-line `clang-format` gate required
formatting in four C files. The frozen panel retains its original source
hashes. The [format custody receipt](tau3-fused-format-equivalence.json)
records the historical and formatted source hashes; the rebuilt benchmark
binary is **byte-identical** to the measured binary. The curve test was
rerun and still passes 2,306,609 checks. The [read-only format
audit](audit_tau3_fused_format.py) checks the historical Git blobs and
current sources without altering the original measurement receipt.
