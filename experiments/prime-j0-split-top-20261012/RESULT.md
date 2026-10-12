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

The design source, per-scalar rows, input and plan hashes, theorem modules,
proof audit, and protocol are frozen in this directory. A new independent
holdout and native evaluator are subsequent verification steps.
