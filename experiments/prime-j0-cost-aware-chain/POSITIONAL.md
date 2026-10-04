# Positional τ table for repeated public scalar multiplication

## Frozen question and algorithm

The 25-representative selector in PR #252 reduces modeled curve operations,
but it performs 25 scalar recodings. This separate candidate changes the
**point format** for a fixed public base point used many times. It keeps the
baseline minimum-L1 Eisenstein representative and width-4 τ digit stream,
then moves all position-dependent tripling into reusable precomputation.
Fixed-base combs and τ recoding are prior art; this experiment makes no
academic novelty claim.

Start with the existing nine affine seed points `S_j` and nine `τS_j` from
`ca_ec_tau4_prepare`. For each pair index `q=0,...,63`, store affine
`T[q][0][j] = 3^q S_j` and `T[q][1][j] = 3^q τS_j`. Form the next layer by
the same j=0 Jacobian tripling formula used in the prepared evaluator, then
batch-normalize each 18-point layer. A nonzero width-4 digit at τ position
`i=2q+parity` selects `T[q][parity][seed]`. Apply the existing unit rotation
`(power+q) mod 3` and sign `digit.sign × (−1)^q`, then mixed-add it to the
accumulator. No tripling occurs in the online scalar evaluation. Reject a
scalar requiring `q>=64` rather than silently truncating its chain.

The table has exactly `64 × 2 × 9 = 1,152` `ca_elem` entries, currently
36,864 bytes, plus the original prepared table. Measure and report all
table construction, normalization, memory, and scalar recoding costs. The
primary workload is repeated scalars on one prepared base: preparation is
recorded separately, and the online interval begins before the first
scalar recoding and ends after the last affine result is produced. Cold
single-call accounting includes the table build and is supplementary.

## Frozen held-out panel and decision

After this protocol is committed and its stacked PR is opened, generate four
new 4,096-scalar lists. Use the exact two curves and points in
[INTEGRATION.md](INTEGRATION.md), with SplitMix64 and little-endian unsigned
64-bit storage as specified there, replacing the initial seed by
`20261005`. Use one state per curve/point with
`20261005 XOR (curve_index << 32) XOR point_index`; preserve every reduced
scalar and its order. Commit the files, SHA-256 hashes, and an independent
generic-multiplication output digest before any isolated timing.

For each case, compare the baseline prepared τ path and this positional path
on the identical point and scalar list. Independently replay every output
with `ca_group_mul`, preserve raw errors, and record online additions,
rotations, triplings, precompute triples, table memory, and preparation time.
Use the isolated benchmark service with at least five AB/BA paired
repetitions and the same host-level noise gates as PR #252 before making a
wall-time claim. A complete verified panel and zero online triplings are
necessary correctness gates. Promote this format for repeated-base work only
if the isolated paired online wall result beats baseline; report cold cost
and the break-even target count separately. The algorithm is variable-time
and intended for public rho or research scalars.
