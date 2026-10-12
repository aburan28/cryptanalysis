# One-target unit-steered τ rho result

Implementation, full tests, the independent affine fixture generator,
serial checker, and isolated-manifest generator were frozen in
`3b4edaba`. The fresh public `glv-j0-32` target
`(273297133, 3297348304)` was frozen in `fbd19351` before a solver
invocation. Its fixture scalar is `19638558` relative to base
`(481899190, 1998487369)`; the rho seed is
`10153710805100644059`. Solver arguments contained the public point
and seed, never the scalar. Each of six serial Release and six serial
UBSan runs used a fresh distinguished-point table, recovered the
scalar, and independently replayed it.

All three modes recorded 3,266 reference-equivalent rho operations,
78 table entries, eight table evaluations, four restarts, and 824
startup budget operations. The two paired modes each recorded 157 τ
steps, 93 mixed additions, the same recodings and pair scores, one
table-output batch inversion, and four restart-output inversions.

| Target-dependent cost | `paired2-batch` | Unit-steered batch |
| --- | ---: | ---: |
| Prepared object bytes | 1,104 | 1,104 |
| Preparation coordinate rotations | 0 | 0 |
| Evaluation coordinate rotations | 64 | 19 |
| Gauge changes selected inside τ | 0 | 40 |
| Table output inversions | 1 | 1 |
| Restart output inversions | 4 | 4 |

This complete one-target solve saves 45 counted coordinate
multiplications relative to `paired2-batch`. Each gauge change selects
a different constant in an existing τ Z-coordinate multiplication;
it does not add a field multiplication or alter the scalar streams.
The Release build passed all 16 CTest tests. UBSan `curve` and
`joint_tau` tests and the complete serial UBSan solve panel passed.

The unisolated Release `online_ms` pairs in frozen order were
`0.327,0.338` for generic rho, `0.340,0.277` for `paired2-batch`,
and `0.300,0.291` for unit-steered batch. The cross-order variation
prevents a local CPU conclusion. `panel-release.json` and
`panel-ubsan.json` retain raw trials, failures, correctness and replay
fields, source/binary hashes, and null speedup fields. The host has no
qualifying isolation receipt, so no controlled ratio is available.
`make_isolated_manifest.py` binds this same target to the strict serial
runner for the primary paired one-target comparison.

The backend remains opt-in. Automatic routing and a CPU wall-time
speedup claim require a passing host-level isolation and noise receipt.
Academic novelty of this coordinate steering remains unproved.
