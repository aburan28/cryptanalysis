# Sparse hot-orbit table for prime-field double-scalar multiplication

## Frozen design

The 486-entry unit-orbit table from PR #420 saves online mixed additions
but costs an additional 486 preparation additions, one inversion, and
15,552 bytes. Test a fixed 64-entry variant. For each named curve, count
the 486 relative-unit digit-pair slots on the **old** 1,024-pair fixture
from PR #419. Select the 64 most frequent slots, breaking ties by lower
slot number. Commit the selected indices before generating the new
evaluation fixture. The old fixture is training data only.

Prepare just the 64 selected point sums, retaining a 486-slot index map.
At a selected overlap, use one mixed addition. At a missed overlap, use
the original two mixed additions. All singleton positions follow the
joint τ stream. The dense 486-entry orbit table and the no-pair-table
joint stream are frozen controls. Preparation is tied to the ordered
`(P,Q)` points; a rho use must charge it to its single target.

## Evaluation gate

Generate 1,024 fresh scalar pairs per curve with a new seed after the
selection is committed. Freeze the little-endian bytes and generic
output digests before evaluating any of the three arms on them. Run
`joint, hot64, dense, dense, hot64, joint` per curve, retaining raw
failures. Require all answers to match independent generic replay, and
require exact τ, overlap, hit/miss, mixed-add, rotation, preparation and
memory counters. Unit tests also cover identity, opposite points,
cancellation, scalar boundaries, and unsupported curves.

Report savings per 1,024 evaluations and lower-bound preparation break-even
in mixed-addition equivalents, including misses. Keep inversion and cache
costs separate. Host-level isolation is required before promoting any CPU
wall-time comparison; local timing is exploratory. Academic novelty is
unproved, and no automatic rho routing follows from this diagnostic.
