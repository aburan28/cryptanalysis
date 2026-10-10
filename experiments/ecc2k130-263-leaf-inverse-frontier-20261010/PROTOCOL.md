# Frozen x-only versus z-only projective-S3 leaf frontier

The [single-block frontier](../ecc2k130-263-projective-s3-frontier-20261010/RESULT.md)
found that freeing one leaf x/z pair from a fully checked exceptional
six-summand witness reached the 120-second CryptoMiniSat cap on both the
ECC2K-130 source and oriented degree-263 descendant, while freeing one
projective state solved with 0–13 conflicts. This gate separates the two
leaf-coordinate constraints without changing the parent XCNF or group
witness. It is a fixed-witness diagnostic, not an ordinary-query yield
screen; the held-out stream stays closed.

The parent's exact leaf equations are `w z = 1` and
`u (x + alpha) = alpha`, plus the trace constraint on `z`. For each curve,
leaf 0 and leaf 5 have two paired cells: free only its 131 `x` input bits
or free only its 131 `z` input bits. Fix every other external bit to the
parent verified positive model, including the six masks, the other leaf
coordinates, four projective states and target selector. Each new cell has
2,115 fixed units, compared with 2,246 in the fully fixed parent and 1,984
in the earlier x/z-pair release. Reconstruct each full input byte-for-byte
from the archived parent base and the new unit delta. Pin parent source,
audit, solver binary, order, and resource policy in `CONFIG.json`.

Commit this protocol, configuration, builder, runner, and independent audit
before running. Then commit the eight exact unit deltas and full-input
hashes before the first solver cell. Run once in configuration order, using
CryptoMiniSat 5.14.7 with one thread, native XOR, a 120-second internal
limit, 150-second external wall guard, and 4-GiB sampled-RSS guard. Save
lossless complete stdout, stderr, exit/guard status, wall, memory peak,
exact conflicts when printed, and search progress. A SAT assignment needs
independent verification of all ordinary clauses and native XORs, all leaf
coordinates, intermediate states, and the signed exact-target group sum.
Preserve capped and failed attempts separately; do not relabel an
indeterminate search as UNSAT.

The primary decision is whether x-only, z-only, both, or neither reaches
verified SAT on both curves under the same cap. A bounded x-only cell points
to `u`-inverse/S3 coupling; a bounded z-only cell points to the `w` inverse
or trace constraint. If both singleton coordinates solve but their joint
release stays bounded, test cross-coordinate solver heuristics under a new
frozen protocol. A curve-specific difference calls for a matched
source/descendant constants audit. Only a compact selective encoding that
passes these controls should be taken to a frozen ordinary query; useful
relation rank remains the promotion measure. `candidate_id` stays `null`.
