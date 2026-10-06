# Full-query integration gates

This is a proposed next experiment. The native residual API is not yet wired
into a complete query, and no timing is attributed to it.

The existing round42 producer first eliminates the lifted quadratic system,
then seeks a constant or degree-one multiplier contradiction. When the affine
projection has fewer pivots than residual variables, `projection_identity`
returns to the bounded Macaulay constructor and finally exact enumeration.
The round34 checker enumerates the entire residual cube whenever neither
contradiction format is present. Partial-affine certificates address that
specific fallback; they do not replace complete-basis certification.

## Proposed proof record

A new version must distinguish a branch's original-equation affine witnesses
from its existing constant and multiplier contradiction witnesses. A partial
record needs a branch index, an explicit witness count, and bounded equation
bit vectors. Branches must be sorted and unique, records cannot overlap with
contradiction records, lengths and high bits must be checked before use, and
missing records must invoke the unchanged complete fallback. There is no
trusted rank, pivot list, root count, or producer evaluation table in a record.

For every partial record, the checker specializes its independently decoded
original ANFs, derives the affine rows, reduces them independently, and counts
all actual roots in their solution space. The global path must still prove
that the submitted roots are distinct actual roots and that their count is
complete. The existing basis-vanishing, staircase-cardinality and reducedness
checks remain charged and required. A residual-root pass alone cannot mark
the global basis verified.

Proof, work, assignment and output limits apply across the whole query, not
just separately to each residual call. A budget failure is inconclusive;
retaining a prefix of roots is never a verified complete result. Symmetry
sharing requires the current exact fresh-coefficient symmetry guard, and the
checker must validate each expanded record against its own original branch.

## Initial integration choice

Start by adding partial records only at the current rank-deficient fallback.
Keep both unchanged contradiction formats and compare with a forced-disabled
partial arm. Reuse affine rows that the producer has already derived; calling
the standalone elimination routine again would charge duplicate work.
The checker continues to derive all rows independently.

Measure actual rank, witness count, original candidate count, remaining
candidate count, proof bytes, proof-generation time, independent checking
time, and complete-query wall time. Preserve rank-zero, full-rank,
inconsistent, many-root and budget-failure cases. Lower assignment counts
cannot substitute for a measured complete-query improvement.

## Memory before widening

At ten residual variables the complete quadratic support has 56 monomials.
With twenty fixed variables, a single 32-bit feature table needs
56 * 2^20 * 4 = 234,881,024 bytes (224 MiB), before the second independent
table, proofs, roots or GPU buffers. This exceeds the current 64 MiB table
guard. The isolated ten-variable controls do not establish a supported
30-variable query.

A separate bounded tiling design must specialize both independent tables
without caching target answers, visit every fixed-variable branch exactly
once, handle tile boundaries and symmetry aliases, retain original-equation
proof semantics, and charge conversions and transfers. Raising the existing
memory guard alone is not the next implementation step.

One bounded specialization reference splits a fixed assignment into high
tile bits and low offset bits. For each original term, reject it in a tile
when its high-bit monomial does not divide that tile's high assignment;
otherwise XOR its coefficient into the low-mask ANF. Apply the low-variable
Boolean transform inside the tile. This is exact but can repeat input scans,
so their cost must be charged. Producer and checker need separate decoders
and transform implementations. Any later Gray-code reuse needs its own
fresh-coefficient and tile-boundary controls.

If proof checking is streamed, the checker must own an ordered coverage
cursor and require every tile of the fixed domain exactly once. It must
reject omitted, duplicated, reordered, overlapping or extra tiles. No
intermediate success may escape as a verified query result; only complete
domain coverage followed by the global root/basis checks permits success.
Proof retention or durable replay costs also belong in the declared
experiment boundary, rather than disappearing behind the streaming API.

## Measurement and promotion

Freeze full inputs, both source/binary identities, proof version, fallback
policy and analysis protocol before timing. Charge fresh proof production,
transport, independent complete checking, original-equation checks and curve
replay in one complete query. First compare with the strongest retained
complete-query CPU and Metal paths under the same load/resource protocol.
Any repeated advantage is specific to those inputs and that device. General
F4/F5 comparison and the separately named same-point single-target IC/rho
experiment remain subsequent gates.
