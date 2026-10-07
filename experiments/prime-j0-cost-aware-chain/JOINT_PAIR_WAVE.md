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

| Curve | Pair positions | Training scalars | Serial output inversions | Maximum wave output inversions per 4,096-scalar case |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 2 | 16,384 | 16,384 | 32 |
| `j0-56` | 4 | 16,384 | 16,384 | 96 |

The wave bounds follow from `ceil(4096/128)` blocks and at most one
inversion for each pair position after the first. They are predictions,
not observations. The evaluator must charge all online recoding,
lookups, batch additions, field rotations, and output work. Prepared
tables and fixture loading remain outside its measured online interval.

Batched inversion and affine wavefront addition are established ideas;
this experiment evaluates their combination with the bounded
Eisenstein pair atlas. It is a public-scalar batch-throughput study,
not a one-target DLP speedup claim. Controlled CPU timing requires a
host-level isolation receipt under
[the repository gate](../../docs/ISOLATED_BENCHMARKS.md).
