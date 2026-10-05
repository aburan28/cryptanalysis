# Retrospective equal-size W24 column audit

This is an exact deterministic reanalysis of the already frozen W24 orbit
partition in parent PR #301 and the selected equal-size source prefix in
PR #305. The selection and the full partition were both visible before this
protocol was written, so this is **retrospective**, not a new prospective
performance test. It makes no timing-ratio or IC speedup claim.

Read and hash both complete archived W24 mask streams. The source prefix is
the first 8,386,414 ascending masks, with last mask `16763440`; the native
descendant uses all 8,386,414 masks. Check the selected source-prefix digest
and the full-stream digests. Restrict the full source sign-plus-Frobenius
component map to the selected prefix. Because every component label is its
minimum mask, every retained member's label remains in the prefix. Count
potential source log columns as singleton selected masks plus distinct
nontrivial labels. Check the parent full partition and reciprocal-zero
receipts before using their map. Transported source columns have the same
abstract partition, with map and recognition cost still unknown.

An independent pure-Python verifier must recompute direct overlap edges from
the GF(2) nullspace of each `W24 ∩ Frobenius^-k(W24)` for powers 1–65,
restrict both edge endpoints to the selected prefix, and recover the same
partition. The full-scan parent backends already found zero reciprocal
overlaps; a subset cannot create new reciprocal overlaps. This verifier
must state that it does not independently re-enumerate the reciprocal
channel. Keep source hashes and all exact counts in both receipts.

For the native descendant, check its exact unnormalized codomain model. The
coordinate-square map sends it to its coefficient-squared conjugate. Check
that its `j` invariant differs from its square, so this conjugate is not even
isomorphic to the original curve. This rules out **direct coordinate
Frobenius folding** on that native curve. It does not rule out a
transport-induced subgroup action or other charged symmetries. Record the
native sign-only column count, but leave the cost and applicability of an
induced quotient unknown. A checked-Sage mathematical control must verify
the `j` statement on the exact route codomain and a public generator.

All output is stage geometry. Keep `candidate_id`, PDP yield, verified rank,
actual final matrix columns, factor logs, target descent, recovered scalar,
online time, and rho ratio `null`. No measured CPU speedup follows from
these deterministic counts.
