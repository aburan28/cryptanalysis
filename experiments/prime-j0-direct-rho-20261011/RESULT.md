# Direct norm-seven bucket combination in XYZZ coordinates

The radix-1024 fixed-base evaluator now has a direct XYZZ implementation
of `rho=1+tau`. It combines the norm-seven bucket once at the end while
retaining the priority cover's 67,338 seeds and 54,339,936-byte native
table. On a new 4,096-scalar panel, every direct-path point matched the
folded path, direct-index control, and fused control. The first 128 also
matched independent binary multiplication. The final native CLI suite
passed 142/142 tests, and the independent edge fixture passed 10/10.

## Instance and frozen inputs

The curve is secp256k1: `y^2=x^3+7` over
`p=0xfffffffffffffffffffffffffffffffffffffffffffffffffffffffefffffc2f`.
The generator is
`G=(79be667ef9dcbbac55a06295ce870b07029bfcdb2dce28d959f2815b16f81798,
483ada7726a3c4655da4fbfc0e1108a8fd17b448a68554199c47d08ffb10d4b8)`;
its subgroup order is
`n=0xfffffffffffffffffffffffffffffffebaaedce6af48a03bbfd25e8cd0364141`.
The fixed-base table and priority atlas are those of the stacked dual-orbit
candidate. The full atlas SHA-256 is
`73dd615b65686ca51c866e28968d0f1c79c7367982730c5c3d115f11b72337c7`.

The panel contains 4,096 deterministic uniform 256-bit scalars from Python's
`random.Random` with seed `20261011045217`. Its generator rejected values
whose reductions modulo `n` collide with any earlier frozen fixed-base panel
or with another value in this panel. The input file SHA-256 is
`543a3cb41f27d72d1b36cded1bc34443337e44d4016fad990a0127ff1ac0867e`;
the scalar-stream SHA-256 is
`b4dee884a5c9dbc53bd13c73a5eedd037c9b52f9e3d520808a185f81faaca881`.
The atlas replay found an active `rho` map in the twelve full windows for
3,081 of the 4,096 scalars, with zero terminal-bound failures.

## Arithmetic comparison

The [derivation](DERIVATION.md) transports Proposition 3.2 of Xu et al.
from Jacobian coordinates into XYZZ coordinates. Both evaluators use the
same recoded terms, seed points, atlas, unit-gauge schedule, and retained
bytes. They differ only in the final four-bucket combination:

| Final path, ordinary nonidentity case | `add_xyzz` calls | `tau` calls | direct `rho` calls | Retained bytes |
| --- | ---: | ---: | ---: | ---: |
| Folded priority cover | 4 | 2 | 0 | 54,339,936 |
| Direct XYZZ `rho` | 3 | 2 | 1 | 54,339,936 |

The source-call model counts `add_xyzz` as 12 general field
multiplications and 2 squarings, and direct `rho` as 9 general
multiplications, 5 squarings, and 2 fixed-constant Solinas products.
The nominal final-path change is `-3M + 3S + 2C`. The model covers the
ordinary nonidentity path; it does not price field additions, cache effects,
or exceptional branch paths. The inherited native `additions=49,152` value
is the sum of `max(0, nonidentity recoded terms - 1)`, not a measured
point-addition count. Gauge rotations were 20,504 for both variants on
this panel because they share the recoding and gauge schedule.

## Verification and replay

The new direct `rho` method matched `P+tau(P)` across identity, affine,
and projective-gauge group points, and its XYZZ scale invariant passed.
The paired native test checked all 4,096 outputs and their representative
metadata. The final CLI binary independently verified ten edge-fixture
outputs. [native-check.json](native-check.json) binds the input, generated
source, materialization, binary, and compressed raw test logs. These are
correctness and static operation records; a CPU wall-time comparison needs
the strict host-isolation and paired-run receipt in
`docs/ISOLATED_BENCHMARKS.md`.

The source-pinned Linux correctness job
`20261011T050536Z_prime-j0-direct-rho-xyzz-linux-e3e025a_fVp62V`
was accepted by the serial RunPod runner and reported `queued` at commit
`e3e025a7fee7cf679e5fd0fad20696fc87aad91c`. The job records a host
probe and complete native replay when it reaches the front of the queue.

The next optimization question is whether carry-aware selection among the
cover's multiple valid representations can reduce active norm-seven and
unit-gauge branches at the same retained-table budget. Its scalar-dependent
selection cost must be charged in any eventual paired timing result.
