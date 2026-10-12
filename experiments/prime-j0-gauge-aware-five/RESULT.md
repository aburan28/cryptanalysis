# Held-out gauge-aware lattice search result

The implementation, tests, independent affine fixture generator,
checker, and protocol were frozen in `0782e44e`; fresh 1,024-pair
fixtures and output digests were frozen in `16162d93` before either
candidate ran. Release and UBSan ran the serial baseline, scored two,
scored five, scored five, scored two, baseline order on each curve.
Both panels pass. All outputs match the independent affine digest,
and every raw trial, failure field, binary hash, source hash, and
counter is retained.

| Curve; 1,024 pairs | Arm | τ steps | Mixed adds | Rotations | Recode attempts | Weighted score |
| --- | --- | ---: | ---: | ---: | ---: | ---: |
| `glv-j0-32` | Baseline free gauge | 13,518 | 7,598 | 1,486 | 4,084 | 166,172 |
| `glv-j0-32` | Scored two neighbors | 13,526 | 7,594 | 1,325 | 4,084 | 166,015 |
| `glv-j0-32` | Scored five neighbors | 13,329 | 7,415 | 1,227 | 10,210 | 162,766 |
| `j0-56` | Baseline free gauge | 33,616 | 16,237 | 2,017 | 4,084 | 382,320 |
| `j0-56` | Scored two neighbors | 33,610 | 16,240 | 1,826 | 4,084 | 382,126 |
| `j0-56` | Scored five neighbors | 33,459 | 15,899 | 1,663 | 10,210 | 377,306 |

The frozen weighted score is `6 * tau_steps + 11 * mixed_adds +
rotations`; its weights are a heuristic, not a full field-operation
count. The two-neighbor score saves 157 and 194 weighted units across
the two curves, less than 0.1%. The five-neighbor search saves 3,406
and 5,014 weighted units, about 2.0% and 1.3%, while requiring
6,126 extra recodings and 21,426 extra pair scores per panel. All
arms use the same 1,104-byte prepared table, preparation counts, and
output inversion count.

The Release `online_ms` values in frozen order were
`0.949, 0.961, 1.471, 1.483, 0.982, 0.951` on `glv-j0-32`
and `2.028, 1.981, 3.053, 2.856, 1.916, 2.005` on `j0-56`.
UBSan values are preserved in the raw panel. These runs lack verified
host-wide CPU and NUMA isolation; both panels set
`cpu_speedup_claim: null` and `isolation_receipt: null`.
The five-neighbor arm's substantial extra recoding makes it a poor
current CPU choice despite the lower heuristic score. The two-neighbor
arm needs a controlled one-target rho run before any speed claim.

Release with `CA_WERROR=ON` passed all 16 CTest tests; UBSan
`joint_tau` passed. This is a scalar-stage diagnostic, not a
single-target online speedup result. Academic novelty remains
unproved; the search combines known τ-adic digit recoding with the
existing free-gauge evaluator.
