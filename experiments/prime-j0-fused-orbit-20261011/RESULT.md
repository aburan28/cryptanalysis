# An aligned orbit record fuses digit and point lookup

The full radix-1024 atlas now stores the signed canonical digit with
each direct-index class code. The exact
[construction receipt](atlas-receipt.json) records a **1,730,332-byte**
full atlas and a projected **66,470,372-byte** complete native table.
The independent [atlas check](atlas-check.json) decoded all
**1,048,576** full residues and found zero differences from the
direct-index control in digit, seed, tau exponent, or unit. The
exponent-two residue count remains 64,674.

The [fresh scalar panel](fresh-inputs.json) contains 4,096 scalars
disjoint from all prior panels. Its [input check](input-check.json)
passed, and the [paired group replay](group-check.json) produced the
same 4,096 independently checked curve points for fused and direct-index
lookups. Each variant used 49,152 mixed additions, 16,563 gauge
rotations, and 6,442 outer tau images. These are operation counts, not
host-isolated runtime measurements.

The fused record removes runtime seed-table access and tau-digit
reconstruction from each full digit. The point-table seed and terminal
data remain available for construction and exact final handling.
Native retained size and source-pinned Linux correctness replay are the
next evidence gates; the size above is a construction projection.
Runtime comparison requires the host isolation receipt described in the
[protocol](PROTOCOL.md).
