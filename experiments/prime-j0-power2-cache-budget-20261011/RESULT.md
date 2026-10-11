# Cache-budgeted tau cover reduces grouped rotations within 64 MiB

The radix-1024 three-image atlas spends 4,096 extra full-window seeds to
replace 8,192 exponent-two unit classes with exponent-one classes. It
retains **64,991,220 bytes** in the source-pinned native evaluator, below
the RunPod CPU's reported 67,108,864-byte L3 capacity by 2,117,644
bytes. This is an exact representation-size result; the host-isolated
paired runtime experiment remains to be run.

The deterministic transformation replaces the first 4,096 disjoint
adjacent pairs of admissible length-three tau segments with three
length-two segments. The [proof](PROOF.md) gives the exponent-two lower
bound for a fixed seed budget, and the [construction screen](screen.json)
binds the selected cover plan. The [independent plan check](independent-check.json)
rebuilds every cycle, while the [atlas check](atlas-independent-check.json)
decodes all 1,048,576 full residues and 80,521 terminal pairs.

| Exact property or same-panel operation | Minimum three-image | Cache-budgeted three-image |
| --- | ---: | ---: |
| Full-window seeds | 73,417 | 77,513 |
| Affine slots, including terminal | 890,292 | 939,444 |
| Native retained bytes | 61,829,108 | 64,991,220 |
| Exponent-two full residues | 167,994 | 118,842 |
| Scalars in fresh disjoint panel | 4,096 | 4,096 |
| Mixed additions | 49,152 | 49,152 |
| Grouped gauge rotations | 18,200 | 17,518 |
| Outer tau images with nonidentity input | 7,720 | 7,278 |
| Point-output SHA-256 | `440ea7800c71331061b6cd44327bbbb7bfb53ecdade0c0717f19f3e37fb5d2dd` | same |

The [input receipt](input-check.json) verifies that the panel was drawn
after the construction freeze and is disjoint from previous panels. The
[group receipt](group-check.json) checks integer reconstruction, both
atlas outputs, grouped tau buckets, and independent binary point
multiplication for every scalar. A source-pinned native Rust test passed
all 4,096 cases against the two-image control and checked the first 128
with a separate binary point path. It reported 49,152 mixed additions,
17,518 grouped rotations, and the exact retained-byte count above.

The cache capacity is shared by the host, and the current pod has no
host-wide isolation receipt. Its capacity therefore defines a design
budget, not a demonstrated cache hit rate. The next experiment pairs
this candidate with the minimum-memory three-image control on the same
frozen panel in an auditable isolated environment, charging all table
construction and setup separately from the evaluation interval.
