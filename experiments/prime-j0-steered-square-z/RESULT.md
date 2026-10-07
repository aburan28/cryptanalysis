# Held-out square-based steered τ Z result

The opt-in `paired2-free-gauge-square-z` arm uses the known square-based
Jacobian Z identity with each selected unit-steered τ constant. The source,
tests, fixture generator, panel checker, and protocol were frozen in
`e621c796`; the independent affine fixture and expected digests were
frozen in `7f0d06c2` before either candidate ran. Release and UBSan
panels then ran serially in regular, square Z, square Z, regular order
on each curve. Both panels pass and preserve each raw trial, process
return code, output digest, binary hash, and source hashes.

| Curve; 1,024 held-out scalar pairs | τ steps in each arm | Square Z steps in new arm | Mixed additions in each arm | Rotations in each arm | Free gauge transitions in each arm |
| --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 13,457 | 13,457 | 7,561 | 1,473 | 3,199 |
| `j0-56` | 33,546 | 33,546 | 16,184 | 2,085 | 8,425 |

All 1,024 outputs per curve match independently computed affine
digests, and each trial reports `verified=1`. The scalar path, selected
streams, preparation, recoding, additions, output inversions, and final
gauge corrections have equal counters in the two arms. The source-level
operation model replaces one field multiplication with one field square
per nonidentity τ step, plus modular additions and a half operation.
It is an operation substitution, not a measured full-operation saving.

The Release `online_ms` values in frozen ABBA order were:

| Curve | Regular 1 | Square Z 1 | Square Z 2 | Regular 2 |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 0.943 | 0.907 | 0.885 | 0.907 |
| `j0-56` | 2.033 | 1.833 | 1.881 | 1.998 |

UBSan showed the opposite timing direction: regular `8.640,8.620` ms
versus square Z `9.370,9.304` ms on `glv-j0-32`; regular
`17.787,18.042` ms versus square Z `19.238,19.673` ms on `j0-56`.
Neither build ran with verified host-wide CPU isolation. Both result
records therefore retain `cpu_speedup_claim: null` and
`isolation_receipt: null`. The Release build with `CA_WERROR=ON` passed
all 16 CTest tests; the UBSan `joint_tau` test passed. The output is a
scalar-stage batch diagnostic, not a one-target rho timing result.

The alternate formula is opt-in. A fresh one-target rho comparison and
an isolated benchmark receipt are required before claiming a CPU
speedup or enabling automatic routing. The Z identity comes from the
Xu--Yu--Han--Lu paper; academic novelty of the combined unit-steered
scalar scheme remains unproved.
