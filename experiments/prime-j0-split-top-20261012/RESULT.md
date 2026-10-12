# Radix-671 split-top scalar format

Twelve radix-671 unit-orbit windows and two bounded terminal coordinate
tables cover the complete secp256k1 scalar range with **1,044,625 affine
point entries**, or **66,856,000 point payload bytes** at 64 bytes per
entry. The design screen audited all 450,241 residues and reconstructed
all 4,096 frozen design scalars. Lean proves universal arithmetic coverage,
the terminal bound, exact split reconstruction, and subgroup congruence.

The low terminal table has 65,536 entries for `[-128,127]^2`. The high
table has 78,597 entries for `[-184,184] × [-106,106]`. The ordinary
windows have 900,492 entries. Retained memory also includes the residue
atlas, plans, constants, and table containers; a native implementation must
measure that complete footprint.

| Design panel measure | Radix 943 | Radix 929 | Split-top radix 671 |
| --- | ---: | ---: | ---: |
| Scalar cases | 4,096 | 4,096 | 4,096 |
| Affine point entries | 1,926,717 | 1,863,085 | **1,044,625** |
| Affine payload bytes | 123,309,888 | 119,237,440 | **66,856,000** |
| Selected terms | 53,248 | 53,248 | 57,343 |
| Gauge rotations | 9,027 | 9,016 | 9,588 |
| Modeled ordinary-path products | 484,163 | 484,152 | 525,674 |

The split format uses one extra selected term in nearly every case. Its
source model charges 41,522 additional ordinary-path products across the
panel relative to radix 929, while the point payload falls by 52,381,440
bytes. This is a memory and operation frontier point; cache behavior and
complete online time require a native implementation on an isolated host.

After freezing the design and holdout generator in commits `997e24e58` and
`74edd0785`, a new 512-scalar holdout was drawn from seed `20261012671`.
The split-table decomposition reconstructed every scalar, and 512/512 final
points matched independently generated secp256k1 fixture points after the
selected term points were summed with a separate affine group law. Its point
stream SHA-256 is
`c6e43ec4d2d9dfd0efba21a1d208c55aa2de6413451e19e1b19af36053e7d9b3`.

| Independent holdout measure | Radix 943 | Radix 929 | Split-top radix 671 |
| --- | ---: | ---: | ---: |
| Scalar and point cases | 512 | 512 | **512** |
| Selected terms | 6,656 | 6,656 | 7,168 |
| Modeled ordinary-path products | 60,551 | 60,534 | 65,707 |
| Final points verified by split replay | — | — | **512/512** |

The [holdout receipt](holdout-replay.json) binds the immutable input,
source, plan, and point-stream hashes; [per-case rows](holdout-rows.jsonl)
retain both controls and each terminal split. The native implementation and
complete retained-memory and online measurements remain the next gates.
