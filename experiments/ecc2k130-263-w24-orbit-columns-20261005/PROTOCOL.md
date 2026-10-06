# Frozen W24 Frobenius-column experiment

This exact stage experiment asks how many unknown logarithm columns the
**actual** trace-zero W24 factor base saves by folding sign and the source
curve's order-131 Frobenius action. The previous census measured 8,393,232
sign-folded columns but did not establish that the base is Frobenius-closed.
The optimistic `ceil(B/262)` policy floor is therefore not an observed
matrix dimension. The transported copy of this exact source base has the
same orbit partition under the conjugate action, because the verified
degree-263 isogeny is an isomorphism on the prime-order subgroup. Native
descendant W24 is a different base and is outside this experiment.

The pinned inputs in [CONFIG.json](CONFIG.json) are the merged W24 source
mask stream and the verified route. The source stream is the ascending,
unique list of all 8,393,232 rational nonzero W24 masks, one per signed
`[4]`-projected subgroup class. Its raw and gzip SHA-256 digests must both
match. The field is `GF(2^131)` with modulus
`t^131+t^13+t^2+t+1`, and `W24` has basis
`t^j + Tr(t^j)` for `1 <= j <= 24`. No target point, scalar, or relation
query is selected here. This is a matrix-column geometry measurement, not
a complete IC candidate; `candidate_id` and all PDP, rank, target, and
speedup fields remain `null`.

For each mask `a`, reconstruct its nonzero `w` and traverse powers
`w^(2^k)` and `(1/w)^(2^k)` for `1 <= k <= 65`. A power contributes an
undirected edge `(a,b)` only when its value is an element of the frozen
source mask set. After multiplication by four, signed classes associated
with `w` and `1/w` coincide: the reciprocal is translation by rational
order-four torsion. Frobenius commutes with `[4]`. Thus each edge is an
equality of logarithm unknowns up to the known Frobenius eigenvalue and
possibly a sign. The two traversals cover signed classes; powers above 65
give reverse edges because the group action has prime order 131. Record
direct and reciprocal edge counts separately, deduplicate edges, and
compute connected components over all 8,393,232 masks. The number of
components is the exact **potential orbit-representative count** for this
base; the saving is sign-folded columns minus components. It is not yet a
priced relation-matrix implementation: that needs correct scalar/sign
labels, row rewriting, recognition costs, and a full-rank relation study.
Retain the largest component and a component-size histogram, and bind the
edge list or an equivalent lossless component map by SHA-256.

The producer must reject a malformed stream, duplicate/out-of-order mask,
wrong digest, zero or non-W24 element, or resource-limit breach. Freeze a
one-worker 4-GiB RSS and 3,600-second wall envelope for each backend.
Preserve a failure/timeout receipt; do not convert it into zero savings.
Run the full scan with both the native ARM PMULL arithmetic and the portable
bitwise fallback when available, compare exact component labels after
canonicalization, and keep source, compiler, backend, timing, and peak-RSS
records. Timing on a contended host is diagnostic and cannot support a CPU
speedup claim. Save `./sage --runtime-info` before any Sage verification.

An independent checked-Sage verifier must exhaust the pinned W10
control: reconstruct every signed projected point; compare a direct point
Frobenius orbit partition against the `w`/reciprocal rule; verify the
producer's component count and partition. At full W24, independently
replay seeded direct and reciprocal edges as point equalities and verify
that all listed edge endpoints belong to the frozen mask stream. The two
full native backends must give identical output. Any disagreement leaves
the result unverified.

The predeclared decision is whether the exact saving reaches 1% of the
8,393,232 sign-only columns. Below 1%, deprioritize Frobenius folding for
this W24 base in favor of the outstanding natural-query PDP/rank gate;
at or above 1%, measure the cost of constructing and using the quotient
before crediting it in an IC candidate. Neither outcome implies a DLP
speedup. The W28 and descendant-native column policies need their own
measurements. Publish the raw record, independent verification, failures,
decision, and catalog pointer together in this PR after the protocol is
committed. Any change to the protocol after seeing the full result must be
identified as retrospective.
