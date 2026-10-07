# One-target unit-orbit plane result

The first fixture in this directory found a stale full-suite test
expectation: `test_curve` still asserted 36 preparation coordinate
multiplications. Its `fixture.json`, `panel-release.json`, and
`panel-ubsan.json` remain development evidence. The corrected source,
full test suite, generator, checker, and isolated-manifest generator were
frozen in `3f57f0f7`. The fresh public `glv-j0-32` target
`(3744186215, 149022001)` was frozen as `fixture-v2.json` in
`bb56950b` before either v2 panel ran. Its fixture scalar is `15549974`
relative to base `(481899190, 1998487369)`; the rho seed is
`18420522076943949578`. Solver arguments contained the public target
and seed, never the scalar. All six serial Release and six serial UBSan
v2 runs used fresh distinguished-point tables, recovered the scalar,
and independently replayed it.

All arms recorded 4,794 reference-equivalent rho operations, 148 table
entries, eight table evaluations, five restarts, and 900 startup budget
operations. The paired candidate arms matched τ steps, additions,
recodings, pair scores, output inversions, and one table batch inversion.

| Target-dependent cost | `paired2-batch` | Optimized unit plane |
| --- | ---: | ---: |
| Prepared bytes | 1,104 | 1,392 |
| Preparation coordinate multiplications | 0 | 18 |
| Evaluation coordinate multiplications | 60 | 0 |
| Table output inversions | 1 | 1 |
| Restart output inversions | 5 | 5 |

The plane saves 42 counted coordinate multiplications across this complete
one-target solve relative to `paired2-batch`, while storing 288 more
bytes. The earlier plane construction would use 36 preparation
multiplications on this 18-seed setup; the identity
`beta²*x = -(x + beta*x)` replaces 18 of them with field addition and
subtraction. Unit tests verify every derived coordinate against an
independent `beta²` multiplication on both study curves, and verify
scalar boundary and cancellation cases. The corrected local Release build
passed all 16 CTest tests; the UBSan `curve` and `joint_tau` tests passed.
These are arithmetic counts, not a CPU speedup.

The unisolated Release `online_ms` values, in frozen order, were
`0.544,0.502` for generic rho, `0.498,0.464` for `paired2-batch`, and
`0.478,0.456` for the optimized plane. The host has no qualifying
isolation receipt, so no controlled wall-time ratio is available. Raw
`panel-release-v2.json` and `panel-ubsan-v2.json` retain all trials, failures,
correctness certificates, binary and source hashes, and null speedup
fields. `make_isolated_manifest.py` binds `fixture-v2.json` to the strict
serial runner for a later host-level measurement. The plane remains
opt-in; no automatic rho routing or academic novelty claim follows from
these results.
