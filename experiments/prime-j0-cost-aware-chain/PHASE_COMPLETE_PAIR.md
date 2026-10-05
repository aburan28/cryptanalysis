# Phase-complete exact-pair table: prospective scalar experiment

## Question

The [121-orbit pair evaluator](TAIL_PAIR_FUSED.md) uses one mixed point
addition for each nonzero two-position contribution, but rotates its affine
point at most once per contribution. Can expanding each prepared orbit into
its six exact signed unit images remove those field multiplications and
simplify the online addition loop enough to justify a larger point table?
This is a public-scalar, repeated-fixed-point experiment on the same two
ordinary prime-field `j=0` instances. It is not an isolated CPU speedup,
one-target rho result, or academic novelty claim. Precomputed digit sets are
established prior art; see [Heuberger and Krenn](https://arxiv.org/abs/1110.0966)
and [Heuberger and Mazzoli](https://eprint.iacr.org/2013/705.pdf).

## Exact table and algebra

Keep the preceding policy, gate, 121 orbit representatives, lattice
reduction, and scalar word stream unchanged. For every representative
`c_i`, prepare the six points `±ω^j c_i P`, `j∈{0,1,2}`, in a fixed layout
`6i+3×negative+j`. The 121 already-normalized orbit points cost 103
additional group additions, 148 unit rotations, and one extra batch
inversion beyond the common 18-seed setup. Generate the other images with
exactly two `x`-coordinate multiplications per orbit and inexpensive copies
and `y` negations; no further group addition or inversion is needed. The
table has 726 affine entries, or 23,232 bytes at 32 bytes per point.
Keep preparation and the full prepared-structure size separate from online
work. Independently verify all 726 entries against ordinary scalar
multiplication, including identity and small-order controls.

At pair position `q`, the existing contribution `c` is multiplied by
`(−ω)^q` during Horner evaluation because `τ²=−3ω`. The old word already
contains orbit, power, and sign. Its exact-table index is

`6×orbit + 3×(sign XOR (q mod 2)) + ((power+q) mod 3)`.

The selected affine point is added once; the online evaluator performs no
unit rotation or point negation. Preserve the same tripling/addition stream,
including zero contributions and exceptional identity results. This table
is for public scalars: the policy and point-table addresses depend on the
scalar.

## Design screen and prospective gate

The [design screen](phase-complete-pair-screen.json) uses the eight already
measured cases in `tail-pair-fused-panel.json`; those inputs are design data
for this experiment. It checks all 726 contribution words at all six
positions (4,356 algebraic index checks). A counterfactual operation score
simply subtracts the recorded online rotations while holding the preceding
word stream and all triples/additions fixed. The resulting design-data
scores are 6.99%–7.18% below `tail-double-residue` on `glv-j0-32` and
3.78%–3.84% below it on `j0-56`. These are predictions from earlier
operation counts, not measurements of this evaluator or CPU time. The extra
242 setup rotations and 19,360 table bytes relative to the 121-orbit
candidate are also not in that online score.

Before implementing or running the native candidate, freeze a separate
eight-case fixture: 4,096 scalars for each point `P`, `37P`, `101P`, and
`103P` on each curve. Generate with SplitMix64 seed
`0xA24BAED4963EE407` and the same 64-bit rejection law. Reject scalar
values present in all six earlier orbit-graph/τ-tail manifests, including
`tail-pair-fused-inputs.json`, and earlier accepted values on the same curve.
Freeze file hashes and generic reference output digests. Commit and push
this protocol, the algebraic screen, and the fixture before the first native
candidate run.

Pair `tail-pair-fused` with `tail-pair-complete` on identical frozen inputs,
rotating arm order across cases. Preserve every raw status, failure,
timeout, and zero-gain case. Outside the online timer, reconstruct every
word stream exactly, replay all 32,768 outputs with generic scalar
multiplication, and verify all 726 prepared points per case. The acceptance
gate is eight verified cases, identical triples and mixed additions for each
pair, zero candidate online rotations, and a strictly lower frozen weighted
evaluation score in all eight cases. Report point setup operations,
inversions, full prepared/table/static bytes, online operations, online and
setup intervals, verification time, and raw stdout/stderr/status.

The online interval starts at the first scalar reduction after each point's
table is prepared and ends after the final affine output of 4,096 public
scalars. Recoding, lookups, group operations, conversion, and output storage
are included. Point-dependent preparation and independent verification are
reported separately. A one-target rho comparison must charge point setup
for a newly supplied target. Local macOS wall times are exploratory. A CPU
speed claim requires at least five paired AB/BA repetitions and an auditable
host-level isolation receipt under the repository's CPU gate.

## Reproduction after implementation

```sh
python3 experiments/prime-j0-cost-aware-chain/screen_phase_complete_pair.py
python3 experiments/prime-j0-cost-aware-chain/make_phase_complete_pair_inputs.py \
  --bench build-cost-aware/ca_tau_chain_bench
```

Append the held-out result below without changing the protocol above.

## Frozen-panel operation result (2026-10-05)

The disjointness audit confirmed 32,768 unique curve-scalars absent from all
six pinned earlier fixture manifests. The native evaluator passed generic
output and exact recode checks for every input; all 726 prepared exact points
per case matched generic scalar multiplication. The direct curve test passed
2,291,922 checks, including identity and small-order controls. The complete
local CTest suite passed 15/15. An optional address/undefined-behavior
sanitizer build succeeded, but its full curve test was stopped after more
than seven minutes of severe host contention and has no pass result. The
[raw receipt](phase-complete-pair-panel.json)
retains the paired commands, statuses, outputs, operation counts, exploratory
local timings, and source/binary hashes.

Each score covers 4,096 public scalar multiplications and uses the frozen
`10 × triples + 16 × mixed additions + rotations` model. The two arms have
identical triples and mixed additions on every case; the complete table
removes all recorded online rotations. The model excludes online recoder
arithmetic and point-dependent preparation.

| Curve and point | 121-orbit score | Complete-table score | Modeled saving |
| --- | ---: | ---: | ---: |
| glv-j0-32, P | 439,025 | 432,036 | 1.59% |
| glv-j0-32, 37P | 439,568 | 432,514 | 1.60% |
| glv-j0-32, 101P | 439,206 | 432,168 | 1.60% |
| glv-j0-32, 103P | 439,579 | 432,544 | 1.60% |
| j0-56, P | 1,139,921 | 1,121,042 | 1.66% |
| j0-56, 37P | 1,139,990 | 1,121,190 | 1.65% |
| j0-56, 101P | 1,141,683 | 1,122,790 | 1.65% |
| j0-56, 103P | 1,140,982 | 1,122,230 | 1.64% |

All eight cases passed the prospective operation gate. Per prepared point,
the complete table has the same 103 extra mixed additions and two total
preparation inversions as the orbit table; setup rotations increase from
148 to 390. The affine table grows from 3,872 to 23,232 bytes, and the full
prepared structure from 4,976 to 24,336 bytes. Both arms use the same
33,289-byte generated policy. Their benchmark binary retains earlier arms,
so these sizes describe active arm data rather than the whole binary.
There is no qualified isolation receipt, calibrated CPU timing ratio,
single-target rho solve, or academic novelty claim for this format.
