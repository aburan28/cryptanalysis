# Joint prime-field τ stream for public double-scalar multiplication

## Frozen question

For a j=0 curve over Fp with p=1 (mod 3), can one prepared τ-adic stream
evaluate `aP+bQ` with less point work than two independent streams using
the **same** point tables and digit recoder? The intended application is
target-dependent multiplier setup in a one-target rho solve. This is an
algorithmic candidate, not a claim that it is faster on a CPU.

The field arithmetic and width-four τ digit alphabet come from the existing
`src/ec_tau.c` implementation of the Xu–Yu–Han–Lu construction supplied with
the project. Joint τ-adic double-scalar recoding has prior art on binary
Koblitz curves, for example [Adikari–Dimitrov–Cintra](https://arxiv.org/abs/1801.08589).
The present experiment tests the composition on these prime-field curves;
academic novelty is unproved.

## Exact algorithm

Let `τ=1−ω` and reduce `a` and `b` independently into the existing exact
Eisenstein lattice representative modulo the subgroup order. Recode each
representative with the existing width-four τ digit table, obtaining
`aP = Σ_i τ^i A_i` and `bQ = Σ_i τ^i B_i`, where `A_i` and `B_i` are either
zero or unit rotations of one of nine prepared seed points. Prepare the nine
seeds for `P` and the nine seeds for `Q` in projective coordinates, then
normalize all 18 with **one** batch inversion. Both comparison arms receive
this identical prepared object.

The joint arm uses one Horner state `R`. For each position from high to low,
apply `τ(R)` once, then add nonzero `A_i` and `B_i` in that fixed order.
The control arm evaluates the two digit streams in separate Horner states,
adds the projective states once, then performs the same final affine
conversion. Thus the control uses approximately the sum of both stream
lengths in τ steps; the joint arm uses at most their maximum. Both must
retain the same scalar reductions and exact digit streams. A final point
equality or group-operation count alone cannot prove the two paths are
mathematically equivalent, so tests also reconstruct both scalar identities.

The implementation is variable-time and restricted to public research
scalars. The caller establishes subgroup membership for both points;
preparation checks that both are on the curve. It must reject unsupported
curves without changing the output.
Identity points, zero scalars, maximal 64-bit scalar inputs, equal inputs,
and overlapping nonzero digit positions are required cases.

## Measurement and promotion

The first gate is exact output versus ordinary `aP+bQ`, the shared-table
control, and independent scalar replay on both named j=0 study subgroups.
Record preparation additions, doublings, τ maps, inversions and bytes;
online τ maps, mixed and full additions, rotations and output inversions.
The implementation uses the same scalar reduction and recoder in both arms,
with no fallback. These first counters do not resolve the internal cost of
scalar reduction or digit recoding. Keep all failures. A fresh fixture must
be frozen before the prospective panel is run.

For a rho integration, charge the target-dependent joint preparation,
all multiplier evaluations, walk, collision recovery, and scalar replay to
the same single target. Compare with the existing one-target rho solver on
the same public point and resource envelope. A change in setup operations
is only a phase diagnostic. CPU wall-time speedup requires the host-level
receipt in `docs/ISOLATED_BENCHMARKS.md`; local timing is exploratory.
