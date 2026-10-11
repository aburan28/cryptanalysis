# A succinct orbit atlas funds fewer tau-two digits

The radix-1024 full atlas now stores one three-byte code per six-unit
orbit, addressed by a bitset and rank directory. The resulting
**1,053,128-byte full atlas** covers all 1,048,576 residues with
83,051 full-window seeds. It uses 64,674 exponent-two residue codes,
compared with 118,842 for the cache-budgeted direct-code control.
The source-pinned native evaluator retains **65,793,200 bytes**,
1,315,664 bytes below the RunPod CPU's reported 64 MiB L3 capacity.

The [proof](PROOF.md) specifies canonicalization, rank lookup, inverse
unit composition, digit norm, and the expanded tau cover. The
[independent cover check](independent-check.json) rederives every cycle
and segment. The [atlas verifier](atlas-independent-check.json)
decodes all 1,048,576 full residues and 80,521 terminal pairs.
Construction and the [input law](input-check.json) were frozen before
the new disjoint 4,096-scalar panel was drawn.

| Exact property or same-panel operation | Minimum direct | Budgeted direct | Orbit quotient |
| --- | ---: | ---: | ---: |
| Full-window seeds | 73,417 | 77,513 | 83,051 |
| Full atlas bytes | 4,487,980 | 4,504,364 | 1,053,128 |
| Affine slots, including terminal | 890,292 | 939,444 | 1,005,900 |
| Native retained bytes | 61,829,108 | 64,991,220 | 65,793,200 |
| Exponent-two full residues | 167,994 | 118,842 | 64,674 |
| Scalars in frozen panel | 4,096 | 4,096 | 4,096 |
| Mixed additions | 49,152 | 49,152 | 49,152 |
| Grouped gauge rotations | 18,207 | 17,500 | 16,546 |
| Outer tau images with nonidentity input | 7,738 | 7,307 | 6,425 |
| Point-output SHA-256 | `0db9f3ef3e45ca6e0f66b5b97d238967d2bafa348536e00803d9b6251150ba8b` | same | same |

The [paired group receipt](group-check.json) verifies integer
reconstruction, all three point outputs, and independent binary point
multiplication for every scalar. The native targeted test passed all
4,096 cases against the budgeted direct and two-image controls,
including separate binary checks on the first 128 cases. It reported
49,152 mixed additions, 16,546 grouped rotations, and the retained
size shown above.

The quotient decoder canonicalizes six unit images and computes a rank
for each full digit. These operations are part of the scalar evaluation
and must be charged in any runtime comparison. The RunPod CPU's L3 is
shared and the current pod lacks a host-level isolation receipt; the
capacity above is a representation budget. A controlled paired timing
study must use the same panel and resource envelope, with table setup
reported separately from scalar evaluation.
