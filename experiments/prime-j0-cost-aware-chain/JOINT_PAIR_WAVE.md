# Affine wavefront evaluation of bounded Eisenstein pairs

The bounded pair atlas performs two or four independent mixed Jacobian
additions per scalar, then converts each result to affine with one field
inversion. For a batch of public scalars sharing a prepared base point,
equal pair positions can instead be evaluated across all lanes. The
existing elliptic-curve batch addition shares one inversion across a
block of affine additions.

The [frozen design](joint-pair-wave-design.json) fixes blocks of 128,
the same pair digits and bounded point tables, and both compact point
records from [the width experiment](JOINT_PAIR_WIDTH.md). The first
nonzero term can be copied into an identity accumulator. Later waves
call the existing batch addition once per block when at least one lane
needs a real addition. This changes field arithmetic and the output
schedule, while preserving the exact scalar and group-add count.

An earlier [hot-orbit screen](joint-pair-hot-screen.json) explains this
direction. Selecting 2,048 lower-pair orbits per position by frequency
covered about 42–43% of their uses on the selection fixture but only
18–19% on disjoint scalars. The sparse table would need a second
addition for almost every cold pair. Those addition counts and table
bytes are predictions; no sparse native candidate was built. The
wavefront experiment keeps the complete bounded pair atlas and tests
an arithmetic change instead.

| Curve | Pair positions | Training scalars | Serial output inversions | Maximum wave output inversions per 4,096-scalar case |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 2 | 16,384 | 16,384 | 32 |
| `j0-56` | 4 | 16,384 | 16,384 | 96 |

The wave bounds follow from `ceil(4096/128)` blocks and at most one
inversion for each pair position after the first. They are predictions,
not observations. The evaluator must charge all online recoding,
lookups, batch additions, field rotations, and output work. Prepared
tables and fixture loading remain outside its measured online interval.

The [fresh fixture](joint-pair-wave-inputs/inputs.json) excludes every
scalar in fifteen earlier fixtures. Both the
[release panel](joint-pair-wave-native-panel.json) and
[warnings-as-errors UBSan panel](joint-pair-wave-ubsan-panel.json)
passed 48 native arms in rotating order: both wavefront formats, their
matching serial controls, packed single-window plane, and fixed comb9.
Every arm independently replayed 4,096 outputs per case, and each pair
arm verified its complete prepared table. The Python model checked
eight subgroup-base relations, 32,768 scalar identities, 184 group
decompositions, and the exact
inversion-wave count from subgroup partial sums. The C suite passed
2,312,787 checks in both builds, including block sizes 1, 2, 7, and
128, identity input, and forced scalar fallback.

| Curve | Scalars | Pair additions, serial and wave | Serial output inversions | Wave output inversions | Online field rotations in 16-byte mode |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 16,384 | 32,729 | 16,384 | 128 | 22,305 |
| `j0-56` | 16,384 | 65,438 | 16,384 | 384 | 44,914 |

All paired output digests matched, and there were zero fallbacks. The
24-byte formats also matched unit-action additions; the 16-byte
formats matched field-rotation counts. Wave scratch is 8,320 bytes per
128-lane block, including action words, query points, inversion
scratch, and active flags. The [isolated manifest producer](make_joint_pair_wave_isolated_manifest.py)
passes local schema checks for each wave mode against its same-width
serial control with 199 custody artifacts, eight cases, and 24 paired
repetitions. The local macOS timing fields are exploratory, and no
controlled wall-time ratio exists yet.

Batched inversion and affine wavefront addition are established ideas;
this experiment evaluates their combination with the bounded
Eisenstein pair atlas. It is a public-scalar batch-throughput study,
not a one-target DLP speedup claim. Controlled CPU timing requires a
host-level isolation receipt under
[the repository gate](../../docs/ISOLATED_BENCHMARKS.md).
