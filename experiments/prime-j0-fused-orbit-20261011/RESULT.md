# An aligned orbit record fuses digit and point lookup

The full radix-1024 atlas now stores the signed canonical digit with
each direct-index class code. The exact
[construction receipt](atlas-receipt.json) records a **1,730,332-byte**
full atlas and a projected **66,470,372-byte** complete native table.
The independent [atlas check](atlas-check.json) decoded all
**1,048,576** full residues and found zero differences from the
direct-index control in digit, seed, tau exponent, or unit. The
exponent-two residue count remains 64,674.

The fused record removes runtime seed-table access and tau-digit
reconstruction from each full digit. The point-table seed and terminal
data remain available for construction and exact final handling.
Native retained size, fresh-panel point replay, and isolated runtime
comparison are the next evidence gates; the size above is a
construction projection.
