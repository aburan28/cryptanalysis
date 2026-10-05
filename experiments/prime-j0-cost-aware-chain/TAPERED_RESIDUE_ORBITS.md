# Tapered complete residue-orbit tables for public scalar multiplication

This experiment replaces the selected 2,048-hot-orbit τ⁸ point table with a
**complete** table of residue orbits for each prepared block. The width varies
by block: the larger 56-bit subgroup uses widths `(12,12,12,8,8)`, so its
shortest Eisenstein representative can usually be evaluated with only three
mixed additions while the last two narrow blocks retain a 52-step exact
span. The smaller subgroup uses `(10,10,10,10)`. These schedules are frozen
parameters, not an automatic device-specific routing rule. The candidate
uses only the first shortest lattice representative; it does not perform the
second recode from the reference arm in PR #284.

For even width `w=2s`, `τ^w=(-3)^s ω^s=3^s u_w`, where `u_w` is one of the six
cheap units. The residue is `(a mod 3^s,b mod 3^s)`. Six unit actions partition
all residues into complete orbits. For each orbit's least-key representative,
center both coordinates modulo `3^s`, perform the established τ-NAF recode,
and retain its first `w` digits. Their exact sum is correction `C`; it has the
same residue as the representative. Store the point `[τ^offset C]P` once for
that orbit and block. At lookup, a packed map supplies the orbit ID and a
deterministic unit code; applying that unit to both `C` and the stored point
recovers the chosen correction for the actual residue. Then

`(a,b) = C' + τ^w q`, with `q = u_w^(-1) ((a,b)-C') / 3^s`.

This identity is checked for every explored block. A residual tail beyond
the prepared schedule uses the existing exact positional fallback. The
complete tables have 1,095, 9,843, and 88,575 point orbits at widths 8, 10,
and 12. A direct packed `uint32` lookup uses 17 bits for the orbit ID and
the remaining bits for the six-unit code. Its storage, correction pairs,
per-point table, construction work, and all online lookups are reported
separately. At 32 bytes per affine point, the frozen schedules contain
39,372 entries (1,259,904 point bytes) and 267,915 entries (8,573,280
point bytes), respectively, before the shared positional seed table and
static maps. The larger table is a deliberate memory/setup tradeoff.

Complete τ-adic digit sets, redundant representations, and fixed-base
precomputation are established prior art; see [Heuberger and Krenn's
analysis](https://doi.org/10.1016/j.jnt.2012.08.029) and [symmetric digit
sets](https://eprint.iacr.org/2013/705.pdf). This protocol tests a particular
tapered orbit-table construction and makes no academic novelty claim. It is
variable-time and intended only for public research scalars.

## Prospective evaluation gate

Commit this protocol, `make_tau_wide_orbits.py`, the disjoint exploratory
screen, and its report, then open a draft PR before generating any fresh
evaluation scalars. Use 4,096 exactly uniform scalars per curve and
generator/`37P` case from SplitMix64 state
`20271217 ^ (curve_index << 32) ^ point_index`. Freeze independent generic
output digests before candidate replay. Compare the new tapered arm with
`fused-hot-steer-gated2-batch128` on identical points and inputs, alternating
execution order. Preserve raw failures and out-of-span fallbacks.

The operation gate requires all 16,384 outputs to match generic
multiplication; every C addition, unit rotation, fallback, and table/setup
counter to match an independent Python model; at least **2% fewer mixed
additions in each smaller-subgroup case** and **25% fewer in each 56-bit
case**; exact reporting of point-table bytes, packed-map bytes, preparation
additions and inversions, temporary memory, and online scratch. A loss in
setup-inclusive work or memory is retained as such, not hidden by online
addition savings.

This is a fixed-point batch throughput diagnostic, not a one-target rho
result. CPU wall speed requires five paired AB/BA repetitions on a physical
Linux host that passes `docs/ISOLATED_BENCHMARKS.md`, with all recoding,
lookup, rotations, additions, fallback, and output normalization inside the
online interval. For one-target rho use, any target-dependent table build
must also be charged to that target. The RunPod CPU pod tested in PR #284
failed the host isolation gate; its result cannot promote a timing claim.

## Exploratory screen

`screen_tapered_residue.py` uses seed `20271001`, 2,000 scalars per subgroup
and ω-eigenvalue law, and exact toy-curve point replay. Its operations are
diagnostics for choosing the prospective gate, not the fresh evaluation.
The machine-readable source hashes and all four law rows are in
`tapered-residue-screen.json`.

| Exploratory law | Reference adds | Tapered adds | Saved | Tail fallbacks |
| --- | ---: | ---: | ---: | ---: |
| 32-bit subgroup, ω root 1 (used by C) | 4,141 | 3,998 | 3.45% | 0 |
| 32-bit subgroup, ω root 2 | 4,130 | 3,996 | 3.24% | 0 |
| 56-bit subgroup, ω root 1 | 12,854 | 9,839 | 23.46% | 0 |
| 56-bit subgroup, ω root 2 (used by C) | 9,943 | 6,020 | 39.45% | 0 |

The screen also replayed 232 exact point results on two small j=0 subgroup
controls. These savings exclude point-table construction and were obtained
without a qualifying CPU host. They justify a native implementation and a
fresh panel; they do not establish a wall-time improvement.
