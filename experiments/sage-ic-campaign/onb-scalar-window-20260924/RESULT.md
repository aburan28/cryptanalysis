# Result: faster ONB scalar calls in both local and IC runner copies

The table reports baseline/candidate ratios for **complete `Curve.mul`
calls**, including signed-digit recoding and odd-multiple precomputation.
Each entry is the ratio of paired twelve-round medians on one deterministic
public point and scalar. Inputs were checked for exact equality and curve
membership after every call. The confirmation uses independent seeds and
crosses local and tracked-runner field degrees.

| Phase | Curve copy / field degree | 16-bit control | 32 bits | 64 bits | 131 bits |
| --- | --- | ---: | ---: | ---: | ---: |
| Primary | Local ONB / 53 | 0.997x | 1.193x | 1.203x | 1.222x |
| Primary | Tracked IC `AuditField` / 131 | 1.009x | 1.367x | 1.151x | 1.266x |
| Confirmation | Local ONB / 131 | 1.009x | 1.146x | 1.156x | 1.275x |
| Confirmation | Tracked IC `AuditField` / 53 | 0.993x | 1.140x | 1.132x | 1.206x |

The geometric mean for 32–131-bit cells is 1.232x in the primary run and
1.175x in confirmation. Each long-scalar cell improved. The 16-bit path uses
the original loop and remained within 1% of its paired baseline. Process
peak RSS across cells was 21.7–24.6 MiB, within the declared 512 MiB cap.

The mechanism is fewer affine additions. For one separate 131-bit scalar
diagnostic on the tracked `AuditField`, the binary loop used 193 field
inversions and 386 field multiplications; the signed window used 160 and
320, respectively. These are logical operation counts, not a calibrated IC
cost unit. An independent exhaustive small-field and long-scalar test passed
on both local and runner copies, including negative scalars and order-two
points. Five selected runner IC arithmetic tests passed. The broader runner
test attempt ran 30 tests and had three missing-prerequisite errors:
`pysat` for two SAT tests and an absent `ecc2k130-fixed.json` fixture for
one. The output logs are retained.

The tracked IC runner invokes `Curve.mul` in setup, subgroup checks,
relation construction, and final recovery checks, so the optimized calls
lie on a real runner path. No complete index-calculus workload has been
rerun with all exclusive phase costs, and no verified DLP total or
rho-boundary speedup is claimed from these scalar-call ratios.
