# Gated second representative after carry steering

The carry-steered τ⁸ format chooses a cheaper valid digit pair within each
residue class, propagating an exact carry into the next block. This experiment
adds a second choice at the scalar level: the two shortest Eisenstein lattice
representatives of the same scalar modulo the subgroup order. The first is
always recoded. The second is recoded only if the first steered stream has a
remaining cold two-digit block or exceeds the prepared span. Choose the
second only when it fits and either the first overflows or it has strictly
fewer predicted mixed additions.
Ties retain the first. If neither fits, use the exact positional fallback.

The two representatives encode the same scalar, and every τ⁸ substitution
satisfies the quotient identity in `CARRY_STEERED_TAU8.md`. This makes the
choice exact regardless of the cost model. Preparation uses the same
2,048-entry-per-block hot-orbit table and the same 13,122-byte static
residue map. The second lattice search, recoding, and comparisons are charged
to the online interval. The scheme is variable-time and limited to public
research scalars. It combines established redundant τ-adic and lattice
recoding ideas; academic novelty is unestablished.

## Prospective evaluation gate

Freeze the rule, fallback, exploratory screen, and gate in a commit and open
a draft PR before generating fresh evaluation scalars. Use 4,096 exactly
uniform scalars per curve/point case from SplitMix64 state
`20270717 ^ (curve_index << 32) ^ point_index`, with the same two registered
curves and generator/`37P` points as the carry-steered panel. Freeze generic
output digests first. Alternate arm order between `fused-hot-steer-batch128`
and `fused-hot-steer-gated2-batch128` on each paired case.

The operation gate requires all 16,384 outputs to match generic
multiplication; every C addition, second-recode, and selected substitution
total to match an independent Python model; at least **1% fewer executed
mixed additions in each case**; second recoding on at most **30% of nonzero
scalars in each case**; and identical per-point setup operations and prepared
bytes. Preserve raw failures, out-of-span fallback counts, and static-map
bytes. These gates do not establish CPU speed. That requires five paired
AB/BA repetitions on a qualifying isolated physical host, with the second
recode and any fallback inside the charged interval.

## Exploratory feasibility

The disjoint `20270501` screen in `gated-dual-steer-screen.json` evaluates
5,000 scalars for each subgroup/eigenvalue law. On the eigenvalues actually
used by the C benchmark, gating retained 49% of the always-two addition
saving on the smaller subgroup and 98% on the 56-bit subgroup, while
performing the second recode for 6.0% and 20.0% of scalars. These are
algorithmic diagnostics that selected the prospective gate, not frozen
candidate measurements. They omit native recoding cost and host isolation.
