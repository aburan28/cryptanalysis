# Held-out unit-steered τ scalar-stage result

The implementation, unit tests, independent affine fixture generator,
checker, and protocol were frozen in `9f8da6d1`; fresh 1,024-pair
inputs and expected digests for both curves were frozen in `aaddb914`
before any τ arm ran. Both serial Release and UBSan panels pass and
retain every raw trial, including return codes and verification fields.
The Release build with `CA_WERROR=ON` passed all 16 CTest tests; the
UBSan `joint_tau` test passed. The unit test recomputes all 24 gauge
choices and verifies edge and random point outputs against generic
group arithmetic on both curves.

| Curve; 1,024 scalar pairs | `paired2` rotations | Gauge trellis rotations | Unit-steered rotations | Free gauge changes |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32` | 4,785 | 3,740 | 1,565 | 3,206 |
| `j0-56` | 10,607 | 7,884 | 2,000 | 8,534 |

The steered path and both controls use the same selected digit streams,
1,104-byte prepared object, τ counts, mixed-add counts, recodings, pair
scores, and output inversion counts. On `glv-j0-32` each has 13,488 τ
steps and 7,612 mixed additions; on `j0-56` each has 33,628 and 16,203.
The steered path saves **3,220** and **8,607** counted coordinate
multiplications against `paired2`, or **2,175** and **5,884** against the
trellis, across the respective 1,024-pair panels. Its rotation totals
include 119 and 104 final inverse-unit corrections. The gauge changes
themselves are selected constants inside existing τ Z-coordinate
updates and require no additional field multiplication.

The unisolated Release `online_ms` pairs, in frozen order, were
`0.902,0.908` versus `0.895,0.915` for `paired2` and steered τ on
`glv-j0-32`, and `1.938,1.930` versus `1.934,1.911` on `j0-56`.
These short, contended-host measurements do not establish a CPU win;
`cpu_speedup_claim` and `isolation_receipt` are `null` in both raw
panels. The simple field-operation model omits recoding, branching,
and table access. This is a batch scalar-stage diagnostic, not a
one-target rho result.

The candidate remains opt-in. A fresh public one-target rho solve on a
qualifying isolated host is required before an end-to-end CPU speedup
or automatic routing claim. Academic novelty has not been established;
the unit digit set and τ formula build on existing endomorphism work.
