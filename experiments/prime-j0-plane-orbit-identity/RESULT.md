# One-target unit-orbit plane result

The code, checker, and independent affine fixture generator were frozen in
`624258f0`; the fresh public `glv-j0-32` target
`(2060147312, 243589286)` was frozen in `5e4afc9d` before the solver ran.
Its fixture scalar is `9635738` relative to base
`(481899190, 1998487369)`, with rho seed `10144766359363707224`.
Solver arguments contained the public target point and seed, never the
scalar. Each of the six serial Release and six serial UBSan runs used a
fresh distinguished-point table, recovered the scalar, and independently
replayed it.

All arms recorded 10,668 reference-equivalent rho operations, 339 table
entries, eight table evaluations, ten restarts, and 1,260 startup budget
operations. The paired candidate arms also matched τ steps, additions,
recodings, pair scores, output inversions, and one table batch inversion.

| Target-dependent cost | `paired2-batch` | Optimized unit plane |
| --- | ---: | ---: |
| Prepared bytes | 1,104 | 1,392 |
| Preparation coordinate multiplications | 0 | 18 |
| Evaluation coordinate multiplications | 88 | 0 |
| Table output inversions | 1 | 1 |
| Restart output inversions | 10 | 10 |

The plane saves 70 counted coordinate multiplications across this complete
one-target solve relative to `paired2-batch`, while storing 288 more
bytes. The earlier plane construction would use 36 preparation
multiplications on this same 18-seed setup; the identity
`beta²*x = -(x + beta*x)` replaces 18 of them with field addition and
subtraction. Unit tests verify every derived coordinate against an
independent `beta²` multiplication on both study curves, and verify
scalar boundary and cancellation cases. These are arithmetic counts, not
a CPU speedup.

The unisolated Release `online_ms` values, in frozen order, were
`1.100,1.177` for generic rho, `1.108,1.076` for `paired2-batch`, and
`1.093,1.041` for the optimized plane. The host has no qualifying
isolation receipt, so no controlled wall-time ratio is available. Raw
`panel-release.json` and `panel-ubsan.json` retain all trials, failures,
correctness certificates, binary and source hashes, and null speedup
fields. `make_isolated_manifest.py` binds this target to the strict
serial runner for a later host-level measurement. The plane remains
opt-in; no automatic rho routing or academic novelty claim follows from
these results.
