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

## Frozen operation result

Draft PR #284 opened with the protocol commit `6151f864` before any of the
`20270717` evaluation scalars were generated. The fixture in
`gated2-steer-inputs.json` and its four binary scalar files fixes the public
inputs and generic output digests. `check_gated2_steer_panel.py` replays both
arms in alternating order, checks all outputs, and independently predicts
executed additions, second recodes, and selected substitutions. The raw
stdout, failures, setup figures, source hashes, and model predictions are in
`gated2-steer-panel.json`.

| Curve and point | Carry-steer adds | Gated-two adds | Saving | Second recodes / 4,096 |
| --- | ---: | ---: | ---: | ---: |
| `glv-j0-32`, generator | 8,654 | 8,496 | 1.83% | 260 |
| `glv-j0-32`, `37P` | 8,608 | 8,460 | 1.72% | 244 |
| `j0-56`, generator | 20,838 | 20,305 | 2.56% | 816 |
| `j0-56`, `37P` | 20,781 | 20,273 | 2.44% | 758 |

All 16,384 outputs match generic multiplication, and every operation
counter matches the independent model. The second recode ran on 5.96%–19.92%
of scalars. Both arms had the same point-preparation operation counts and
prepared bytes (300,144 B or 431,216 B by curve), used the same 13,122-byte
static map, and needed no out-of-span fallback. The frozen operation gate
passes. The updated `test_curve` passed 412,487 checks, and the 14 locally
runnable CTest cases passed.

This is a public fixed-point **batch throughput** experiment. The second
recode is inside the online timer, but no controlled CPU timing ratio or
one-target rho benefit is established. A bounded RunPod CPU-pod preflight
failed the physical isolation gate: its container exposed cgroup v1, no
isolated CPU partition, and no `nohz_full` CPUs. The failure and cleanup are
recorded in `runpod-isolation-preflight-20261004.json`. The pod was stopped
and deleted without running a timing panel. A qualifying host must replay
the paired frozen manifest, then measure one complete target-dependent rho
solve before asserting an end-to-end speedup.
