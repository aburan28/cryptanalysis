# Held-out gauge-trellis scalar-stage result

The implementation and serial checker were frozen in `f2ee6322`; the
independently generated 1,024-pair inputs and affine output digests were
frozen in `91894552` before either panel ran. Release and UBSan panels
both pass every output replay. The checked-in table was regenerated
byte-for-byte, and `test_joint_tau` checks every table transition against
the direct recurrence, plus scalar boundaries, identity, equal and opposite
points, and random pairs on both curves.

| Curve; 1,024 paired inputs | `paired2` | Global gauge | Gauge trellis |
| --- | ---: | ---: | ---: |
| `glv-j0-32` rotations | 4,719 | 4,033 | 3,714 |
| `j0-56` rotations | 10,550 | 9,206 | 7,875 |
| `glv-j0-32` table lookups | 0 | 0 | 6,100 |
| `j0-56` table lookups | 0 | 0 | 14,099 |

The trellis uses the exact same two-neighbor pair and chosen streams as
`paired2`: on `glv-j0-32`, both have 13,536 τ steps and 7,601 mixed
additions; on `j0-56`, both have 33,667 and 16,221. It saves 1,005 and
2,675 coordinate rotations respectively. The global-gauge arm may choose
a different stream pair, so its rotation column is a same-input comparator,
not an identical-stream attribution. The trellis uses 1,104 prepared bytes,
the same as `paired2` and global gauge.

This is an **operation-count and correctness result for a 1,024-pair
scalar-stage diagnostic**, not a one-target rho solve. The table search,
backtracking, branch work, and memory traffic are excluded from the simple
`6*tau_steps + 11*mixed_adds + rotations` field-operation model. In the
unisolated Release panel, the two trellis `online_ms` values were
`0.972,0.964` versus `0.892,0.917` for global gauge on `glv-j0-32`, and
`2.053,1.992` versus `1.888,1.936` on `j0-56`. These local timings do not
show a speedup and cannot support a controlled CPU ratio. Raw trials,
failure fields, correctness digests, binary and source hashes are retained
in `panel-release.json` and `panel-ubsan.json`; both set
`cpu_speedup_claim` and `isolation_receipt` to `null`.

The candidate stays opt-in. A full one-target rho comparison with a valid
host-level isolation receipt is required before claiming a wall-time gain
or changing automatic routing. Academic novelty is unproved.
