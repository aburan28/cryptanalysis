# Exact Frobenius occupancy of the ECC2K-130 W24 source base

This experiment independently replays the **potential log-column quotient**
of the frozen `Q1420` source W24 base under sign and degree-two Frobenius,
then applies the same count to its verified degree-263 transport. The
[published full-source scan](../ecc2k130-263-w24-orbit-columns-20261005/RESULT.md)
and [selected-prefix audit](../ecc2k130-equal-w24-orbit-columns-20261005/RESULT.md)
already give **8,384,348** selected source orbit classes. Their independent
nullspace verifiers cover direct Frobenius overlaps; the reciprocal-overlap
channel has two matching complete native backends but no independent full
enumerator. This protocol addresses that verification gap. The base has exactly
8,386,414 selected signed classes, or 16,772,828 usable subgroup points.
Its full signed-Frobenius orbits need not lie inside the base, so dividing
that point count by 262 does not give its matrix width. The proposed output
is an independently computed exact class count and occupancy histogram,
with the point-map and resource costs kept in their existing separate
receipts. A disagreement with the published count must preserve both raw
results and trigger point-law checks before a ledger update.

## Frozen input and comparison boundary

[`CONFIG.json`](CONFIG.json) binds the source curve
`EC1N131Ckb1h136f03e58c98`, field modulus
`t^131+t^13+t^2+t+1`, selected ascending-mask stream, its compressed and
raw hashes, the equal-size W24 parent configuration, and oriented route
`IW1E263d1hadee4e69fa3d`. Verify every hash and count before assigning an
orbit. The source prefix ends at mask `16763440`; the native descendant
selection is a different geometry and is outside this census. The source
and transported bases have the same group-level orbit occupancy under the
conjugated action. Their evaluation, base-construction, membership, and
transport costs remain separate implementation measurements.

The source curve is defined over `F_2`. For its W24 construction,
`w=u²+u`, `x=1+1/u`, and the projected base point is `[4]Q(w)`. Its
Frobenius image is `[4]Q(w²)`. The already verified order-four translation
rule identifies the same signed projected point only for parameters `w`
and `1/w`. Thus two selected masks share a signed-Frobenius column exactly
when their field elements satisfy `v=w^(2^k)` or
`v=(w^(-1))^(2^k)` for some `0 <= k < 131`. The producer must implement
this equivalence on actual selected rational masks; it must not assume the
whole 131-point signed-class orbit was selected.

## Mathematical preflight and acceptance gates

Independently compute `Tr(t^j)` for `1 <= j <= 24`, all 130 nonidentity
Frobenius images of the W24 basis, and the dimensions of
`W24 ∩ Frob^k(W24)` over `F_2`. An exploratory integer preflight, performed
before this protocol, found zero traces and nonzero intersection dimensions
only at `k=±1,±2,±3,±4` modulo 131, with dimensions `12,6,4,1` in that
order. Enumerating the union of these eight kernel subspaces gave 8,143
nonzero masks with any direct Frobenius overlap and a maximum of five W24
members in one direct Frobenius orbit. These are preflight values to replay
independently, not the selected-base census result.

The full signed orbit is the union of the direct orbit of `w` and the
direct orbit of `1/w`. Consequently, successful independent verification of
the five-member direct bound also proves **at most ten selected signed
classes per signed-Frobenius orbit**, and at least
`ceil(8386414/10) = 838642` columns for either the selected source base or
its exact transport. This is a matrix-width floor, not an observed matrix
rank or timing. If any independent field calculation or point control
contradicts the equivalence or bound, invalidate this inference and retain
the raw failure.

## Exact census and independent replay

Decode the archived little-endian `uint32` mask stream; require strict
ascending order, the frozen full and selected counts, the selected boundary
mask, and all three compressed/raw/selected SHA-256 digests. Build a bitset
for the selected prefix. In ascending mask order, visit each unassigned
mask, enumerate the 131 Frobenius conjugates of `w` and the 131 conjugates
of `1/w`, keep only selected masks, and assign their whole class once.
Record the direct-only orbit count separately. Require class sizes from one
through ten, the sum of class sizes to equal 8,386,414, and every selected
mask to be assigned exactly once. Save all non-singleton groups, sorted by
their smallest selected mask, as raw JSONL; singleton groups are implied
by the checked archive. Save the histogram and a digest of the raw group
file. A timeout, memory failure, or arithmetic mismatch is a retained run
status, not a completed count.

An independently written second full enumerator must reconstruct the mask
bitset and all class assignments using a separate field-reduction and
inversion implementation. Its count, histogram, and non-singleton groups
must agree byte-for-byte. Also select 128 distinct archived mask indices
with the frozen SHA-256 audit domain in `CONFIG.json`; checked Sage must
reconstruct their group points and verify representative Frobenius/sign
identities against the exact curve. Run all new Sage jobs through
`/Volumes/SSD990/cryptanalysis/sage` and save `--runtime-info` before the
workload. Preserve exact source and input hashes, command, exit status,
wall and CPU time, peak RSS, raw output, and independent certificates.
Each full enumerator has one worker, 1,800 seconds, and 4 GiB peak RSS.
Host timing is a reproducibility diagnostic until a qualifying isolation
receipt exists.

The independent count will check the existing `Q1420` factor-base column
ledger. The native descendant and its pullback require their
own conjugated-action occupancy census; this source result supplies no
native column count. The frozen one-target workload remains
`eee7f6ee5f6b`; this base census does not query it or change its target
law. Natural W24/m6 PDP yield, novel relation rank, final matrix solving,
target logarithm, and paired rho still require the separately specified
end-to-end experiments.
