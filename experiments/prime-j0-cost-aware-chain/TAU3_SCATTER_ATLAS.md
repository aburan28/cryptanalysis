# Orbit-indexed scattered τ action atlas

The [direct residual-pair selector](TAU3_SCATTER_DIRECT.md) still searches a
sorted list whenever it tests a cross-position pair. This experiment changes
the action format while keeping the frozen point table and deterministic
selector unchanged. A raw pair of three-step digit patterns maps to one of
505 common-unit orbits and a unit code. For each prepared position pair, a
dense `uint16_t` row maps the orbit rank directly to the prepared point slot;
`65535` means that action is absent. Online lookup uses an orbit-code array,
a position-pair index, and one slot-array access. No binary search is needed
for cross-position pairs.

[`tau3-scatter-atlas-design.json`](tau3-scatter-atlas-design.json) froze this
layout after training-scalar pair-probe counts were inspected. On the larger
curve, the 12 busiest of 60 position pairs received only 41.43% of probes.
The full 60-row table uses 60,600 slot bytes; all atlas arrays together add
76,540 static bytes. The reported static map grows from 34,927 to 111,467
bytes. Prepared point storage and preparation additions remain identical to
the direct selector: 2,494 point slots and 2,418 additions on `glv-j0-32`,
or 4,802 slots and 4,669 additions on `j0-56`.

## Frozen verification

[`make_tau3_scatter_atlas_inputs.py`](make_tau3_scatter_atlas_inputs.py)
generated a new 32,768-scalar fixture after the layout was frozen, excluding
every scalar in six earlier fixtures. The exact and direct Python checkers
each verified every scalar identity and 184 independent point outputs. The
atlas uses the direct selector, so its addition counts must be identical:

| Curve | Complete-table additions | Exact matching | Direct and atlas additions | Direct saving |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 47,713 | 44,208 | 44,242 | 3,471 (7.28%) |
| `j0-56` | 97,702 | 93,157 | 93,538 | 4,164 (4.26%) |

[`make_tau3_scatter_atlas.py`](make_tau3_scatter_atlas.py) generates the
static tables from the frozen point-table design. The native verifier checks
all 3,025 raw pattern pairs against the original orbit and unit maps, checks
every populated dense slot against its original entry, and checks that every
original entry appears in the dense table. The fresh 32-arm native panel
rotated complete-table, exact, direct, and atlas modes across the cases.
Every arm independently verified all 4,096 output points; all four output
digests matched per case, all operation counts matched the Python models,
and there were no fallbacks. The release and warnings-as-errors
UndefinedBehaviorSanitizer `test_curve` suites each passed 2,311,796 checks;
the UBSan native panel passed all 32 arms.

The local native receipt keeps timing fields as exploratory diagnostics.
There is no isolated-host CPU speedup claim. The larger static map may affect
cache behavior, so operation equivalence alone cannot establish a runtime
gain. This variable-time mode is intended for public scalars.

## Isolated replay

[`make_tau3_scatter_atlas_isolated_manifest.py`](make_tau3_scatter_atlas_isolated_manifest.py)
binds the fresh fixture, source and generated-table hashes, the verified
output digest, and one native binary to the serial isolated benchmark
service. Its default reference is `tau3-scatter-direct-pos`; use
`--reference-mode tau3-fused-pos` for the complete-table comparison or
`--reference-mode tau3-scatter-pos` for exact matching. It requests three
alternating-order repetitions for each of the eight 4,096-scalar cases.
The measured quantity is online batch latency after table preparation and
before independent replay. A nonqualifying host receipt cannot support a
CPU speedup claim.
