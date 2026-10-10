# Frozen single-block projective-S3 SAT frontier

The verified exceptional six-summand witness has a SAT model when all 2,246
external input bits are fixed. Releasing all leaf coordinates or all four
projective states separately produced bounded searches on both the ECC2K-130
source and oriented degree-263 descendant. This gate tests whether a *single*
leaf pair or projective state is already hard, using the same archived XCNF,
six masks, target lift, and checked group witness as those controls.

[`CONFIG.json`](CONFIG.json) pins the parent source, audited evidence, solver
binary, cell order, and resource caps. Each cell begins with the parent's
fixed-positive unit set and removes exactly one input block: leaf 0 or 5
removes its 131-bit `x` and 131-bit `z` words (1,984 units remain), while
state 0 or 3 removes its 131-bit `t` word and finite flag (2,114 units
remain). The remaining fixed units and parent base XCNF are identical for
all four modes on a curve. Both curves use the same modes. This is a
development witness control; the held-out ordinary-query stream stays closed.

Before any solver cell, commit this protocol, configuration, builder, runner,
and auditor. Construct each unit delta and full input from the parent archive,
record both hashes and validate the released-variable set against the named
input map. Run the eight cells once in configuration order with pinned
CryptoMiniSat 5.14.7, native XOR, one thread, 120-second internal limit,
150-second external wall guard, and 4-GiB RSS guard. Preserve complete solver
stdout losslessly, stderr, exit/guard status, wall, peak RSS, and search
progress. No retry or changed seed is part of this gate.

For SAT, independently check every ordinary clause and native XOR, decode
the selected leaf masks, x/z values and projective states, and replay the
signed group sum to the exact target. A bounded search is `BOUNDED_UNKNOWN`
with its cap; it is not a negative mathematical result. Compare each cell
with the parent's fully fixed, leaf-free, and intermediate-free controls.
If the singleton cells solve but a whole block remains bounded, the next
encoding should address cross-block propagation, with functional leaf
inversion or explicit projective addition as two hypotheses to test. If a
singleton itself stalls, focus the next change on that exact equation block.
Curve-specific differences direct the next test to codomain constants or
native-base geometry. These solver-stage controls do not estimate natural
relation yield or single-target IC time; the proposal retains
`candidate_id: null` until the complete pipeline is specified.
