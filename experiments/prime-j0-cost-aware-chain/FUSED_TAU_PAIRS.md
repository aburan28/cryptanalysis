# Fused eight-digit τ point table for repeated fixed-base multiplication

## Prospective question

Can a per-point table indexed by **two** four-digit τ residue-atlas patterns
reduce complete prepared-scalar online time relative to the positional τ
table with block-normalized outputs? This is a variable-time, public-scalar
research path for repeated multiplication of one point. It makes no CPU
speedup or academic novelty claim before controlled evidence and prior-art
review. The table's construction belongs to setup and is charged when it
depends on the target point, including a rho solve involving a new `Q`.

The related prior art includes [endomorphism-based symmetric digit sets on
ordinary prime-field curves](https://eprint.iacr.org/2013/705.pdf) and
[τ-adic/double-base scalar expansions](https://eprint.iacr.org/2008/388.pdf).
These establish the broader recoding and precomputation setting. The
particular atlas-indexed pair table here is an implementation hypothesis;
its academic novelty remains unresolved.

This protocol is frozen before its held-out scalar files, generated pair
map, C fused table, or benchmark results are produced. It builds on the
four-step residue-atlas protocol and the positional/batch-output branches.

## Exact representation

Write the minimum-L1 Eisenstein representative as `a + bτ`, with the exact
width-4 digit rule and `τ⁴ = 9ω²`. The residue atlas maps each coefficient
pair modulo 81 to one of 217 four-digit patterns: zero, or one of 54 slots
at one of four positions. One atlas lookup emits a pattern and the exact
quotient after removing its digit contribution. Two successive lookups
give pattern IDs `(u,v)` for eight digits.

Of the `217² = 47,089` ordered pairs, **29,593** satisfy the width-4
spacing rule: one zero/zero pair, 432 single-digit pairs, and
`10 × 54² = 29,160` two-digit pairs. For two nonzero digits at positions
`i` in the first half and `4+j` in the second, validity requires `j >= i`.
Generate a 47,089-entry `uint16_t` map, with `65535` for invalid pairs and
compact IDs `0..29592` for valid pairs in lexicographic `(u,v)` order.
Exhaustively compare this map against the exact `recode(expand(digits))` rule.
The map occupies 94,178 bytes.

For block position `q`, precompute the exact affine point

`F[q,u,v] = τ^(8q) (C_u + τ⁴ C_v) P`,

where `C_u` and `C_v` are the integer digit sums of the two patterns. Build
the constituent positional points with the existing global positional
preparer; form the 29,160 two-digit sums per block in Jacobian coordinates
and normalize each block with one batch inversion. Identity and single-digit
entries must preserve their canonical point values. One block holds 29,593
`ca_elem` entries (946,976 bytes at 32 bytes each); the frozen candidates
use four blocks for `glv-j0-32` and six for `j0-56`. Their affine table
budgets are 3,787,904 and 5,681,856 bytes, respectively, plus the map,
positional seeds, and temporary construction scratch. Allocate the large
table on the heap. Any scalar exceeding the prepared block span must use
the existing positional evaluator and increment a recorded fallback count.

After reducing a scalar to `(a,b)`, repeatedly take two atlas lookups,
advance each by the exact τ⁴ quotient, and fetch the compact pair ID. Add
one `F[q,u,v]` for each nonzero eight-digit block. Use the existing
block-normalized affine-output routine for batches. Count all point adds,
rotations, output inversions, setup operations, memory, fallback cases, and
independent scalar replays. The output must equal `ca_group_mul` for every
scalar, including zero, order multiples, small-order points, and boundary
values. The portable C path remains available when preparation fails.

## Frozen workload and claim gate

After this protocol is committed and its PR opened, generate four new
4,096-scalar files on the two curves and the generator/`37P` points used by
the positional panel. Use SplitMix64 state
`20261010 XOR (curve_index << 32) XOR point_index`, reduce each value modulo
the subgroup order, and save the little-endian `u64` sequence and SHA-256.
Freeze each generic-multiplier output digest before benchmarking. The paired
reference is `pos-batch128`; the candidate is `fused-batch128`, on identical
input, point, build, and resource limits. Both arms independently replay all
4,096 results; retain failures and raw stdout/stderr/exit status. The online
interval begins before the first scalar's reduction and ends after the last
affine output; it includes recoding, lookups, additions, output normalization,
and storage. Report per-point setup wall time and operations separately,
then report setup-inclusive total and the measured break-even scalar count.

The 4,096-scalar panel measures repeated fixed-base throughput, not one-call
latency. For rho, count any new-target table preparation and all fallback
work inside the one-target online interval; do not replace the one-target
rho metric with a batch throughput ratio. Predictive operation models stay
separate from measured wall time. Promote a CPU speedup only after at least
five AB/BA pairs pass the repository's host-level CPU/NUMA isolation and
noise gates, with raw failures, uncertainty, and correctness retained. An
ordinary-host result is exploratory.
