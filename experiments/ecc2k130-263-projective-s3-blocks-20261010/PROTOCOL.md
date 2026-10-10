# Frozen projective-S3 SAT search-block isolation

The full six-summand native-XOR circuit in the [parent SAT gate](../ecc2k130-263-projective-s3-sat-20261010/RESULT.md)
encodes and independently replays the exceptional cancellation witness on
the ECC2K-130 source and degree-263 descendant-native curves. Both fixed
models are SAT, while the cells with only six leaf masks fixed reach their
120-second internal cap. This experiment isolates which unfixed input block
makes that search difficult, using the **same archived base XCNF and target**
for each curve. It is a witness-control workload; ordinary-query relation
yield and rank are separate measurements.

`CONFIG.json` pins the parent commit, every source/input digest needed for
this control, the solver binary, order, and caps before any new solver run.
The parent archive-only audit must pass. For each policy decompress and verify
the parent control-base XCNF and load its named input-variable map and checked
group witness. Append sorted DIMACS unit clauses to form two exact inputs:

1. `intermediate_free`: fix six ordered 24-bit masks and six 131-bit x/z
   pairs, plus target choice zero; leave all four projective intermediate
   131-bit x words and finite flags to the solver. Exactly 1,718 input bits
   are fixed.
2. `leaf_free`: fix the same six masks, all four projective intermediate x
   words and finite flags, plus target choice zero; leave the six leaf x/z
   pairs to the solver. Exactly 674 input bits are fixed.

The parent fixed-positive control fixes all 2,246 bits; its mask-only control
fixes 146. Reuse those archived rows without rerunning them. Save the exact
unit deltas, full-input SHA-256 digests, source digests, and construction
receipts. Every new full XCNF is derived byte-for-byte from the parent base
and delta; keep the parent gzip archive as the shared immutable base.

Run the four cells in `CONFIG.json` order, once each, with the pinned
CryptoMiniSat 5.14.7 binary, one thread, 120-second internal cap, 150-second
external wall cap, and 4-GiB external RSS guard. Preserve complete stdout,
stderr, exit code, actual cap status, wall, and peak RSS. A model is accepted
only after independent replay of every ordinary clause and native XOR,
decoded leaves and intermediates, and exact group sum via the parent
independent binary group law. An explicit `s INDETERMINATE` or guard stop is
`BOUNDED_UNKNOWN`; preserve producer failures and OOMs separately. No silent
retry or alternate seed is permitted. Archive the complete stdout losslessly
and verify its raw digest before removing the large local original.

The primary decision is structural: compare the two bounded statuses and
search traces against the parent mask-only cell on each curve. If just one
released block stalls on both curves, focus the next encoding/solver change
there. If both separate blocks solve but the combined cell stalls, test
cross-block propagation or incremental assumptions. If both stall, inspect
the first unresolved equations and alternative encodings. Curve-specific
differences direct attention to the codomain constants and base geometry.
These are solver-stage diagnostics on an unisolated host; no wall-time
speedup is promoted. `candidate_id`, natural relation yield, novel rank,
single-target online IC time, and matched rho ratio remain null.
